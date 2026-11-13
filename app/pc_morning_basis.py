"""POC6-29 보완 2차 — 아침 요약 기준(`GET /market/morning-basis` · PLAN §10-1 · §10-5 · S 판정 Q-S4 · §3).

읽기 전용(저장값 · 기록 · 달력 · PC 보관소 목록만 · 외부 조회 0 · 쓰기 0). 「오늘의 투자 점검」 아침 요약 · 갱신 끝 줄 ·
근거 접기 ③(전일 자료 미완료) · 당일 판정이 이 응답 하나로 준비 상태 · 판정 근거를 읽는다.

- 기준일 = 오늘(KST)의 직전 국내 거래일(`expected_previous_trading_day` · 거래일 달력 + 평일 기본).
- 필수 3 = 코스피 공식 종가(저장일 ≥ 기준일) · KODEX 200 판정 근거(**기준일 행이 마감 뒤 저장** — 최신 행이 오늘이라는
  사실만으로 충족 아님 · S 판정 §3) · 투자자 수급(저장일 ≥ 기준일). 해외(VIX · 원/달러 · WTI)는 각 원천 기준으로 함께 싣되
  필수가 아니다(VIX = 미국 마감 판정 · 원/달러 = POC6-27 국내 T-1 대비 · WTI = 관측일만).
- 아침 판정 = 기준일까지 자른 KODEX 200 이력으로 기존 산식(`compute_market_context` · `compute_regime_streak` ·
  `kodex200_return_dates`)을 그대로 계산 · 실제 산출 기준일(`basis_date`)을 돌려준다. 기준일 근거가 확인되지 않으면
  `unconfirmed`(판정 칸 없음).
- 당일 판정(형수님 결정 2026-11-13 · 검증자 F8) = 저장된 KODEX 200 이력 전체로 같은 산식 + 그 판정이 쓴 끝 행의 저장
  시점. KODEX 200 이력 · 저장 시각은 SQL 한 문장으로 한 번만 읽고(`_kodex_rows`), 항목 · 아침 판정 · 당일 판정을 모두
  그 결과에서 만든다 — 판정 값과 저장 시점이 다른 저장본에서 오지 않는다.
- 사유는 확인된 결과만(마지막 시도 기록 · ③ 결과 파일 · 수급 연결 상태 · PC 보관소 목록). 공개 · 수집 예정 시각을
  추정하지 않는다. 대기 다음 시각은 ETF 전체 갱신이 실제로 대기 중일 때만.
- 코스피 상세(`kospi_detail` · 설계자 지시 · 형수님 결정 2026-11-14 · POC6-29-1 결과서 §5) = 저장된 KOSPI 공식 종가 전체로 시장 판정
  응답과 같은 산식(20 · 60거래일 = KODEX 200 거래일 축 `return_by_trading_days` · 1년 · 최근 1년 고점 대비 =
  `compute_kospi_position_metrics`) + 20 · 60거래일의 실제 계산 시작일. 최신성(기대 직전 거래일) 판정과 무관하게 저장값이 있으면
  주말 · 장 시작 전에도 읽힌다. 시장 판정 응답(`market_context.kospi`)의 엄격 규칙 · 그 값을 쓰는 곳은 그대로.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter

from app import market_refresh_service as svc
from app.market_benchmark_store import KOSPI_ID, KOSPI_SOURCE
from app.market_data_store import (
    DEFAULT_DB_PATH,
    latest_refresh_log,
)
from app.market_freshness_rows import _kr_item
from app.market_benchmark_freshness import return_by_trading_days
from app.market_regime import (
    LOOKBACK_20D,
    LOOKBACK_60D,
    REGIME_BEAR_MAX_SCORE,
    REGIME_BULL_MIN_SCORE,
    SCORE_THRESHOLD_20D_PCT,
    SCORE_THRESHOLD_60D_PCT,
    _round_pct,
    compute_kospi_position_metrics,
    compute_market_context,
    compute_regime_streak,
    kodex200_return_dates,
)
from app.ml_evidence import store as evidence_store
from app.pc_etf_compare_periods import STATE_AFTER_CLOSE, STATE_INTRADAY, price_state
from app.pc_prevday_fill import (
    kospi_reason,
    local_flow_bundles,
    read_prevday,
    stored_dates,
)
from app.pc_vix_refresh import vix_freshness
from app.supply_fx_oil_basis import read_flow_link
from app.supply_fx_oil_calc import md
from app.supply_fx_oil_store import (
    FLOW_IMPORT_LOG_SOURCE,
    USDKRW,
    WTI,
    read_benchmark_collected_at,
    read_benchmark_series,
    read_macro_series,
)
from app.trading_day_lag import expected_previous_trading_day

logger = logging.getLogger(__name__)
router = APIRouter(tags=["market"])

KST = timezone(timedelta(hours=9))
KODEX200 = "069500"
NOT_YET = "아직 받지 않음 — [최신 자료 갱신]"


def _kst(iso: Optional[str]) -> Optional[str]:
    """UTC · 시간대 있는 ISO → KST ISO(초까지). 해석 불가 · 시간대 없음 = None."""
    if not isinstance(iso, str) or not iso.strip():
        return None
    try:
        dt = datetime.fromisoformat(iso.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(KST).isoformat(timespec="seconds")


def _hm(iso_kst: Optional[str]) -> str:
    return iso_kst[11:16] if iso_kst else "?"


def _today(attempt_kst: Optional[str], today: str) -> bool:
    return bool(attempt_kst) and attempt_kst[:10] == today


def _ro_one(db_path: Path, sql: str, args: tuple = ()) -> Optional[tuple]:
    p = Path(db_path)
    if not p.exists():
        return None
    try:
        with closing(sqlite3.connect(f"file:{p.resolve()}?mode=ro", uri=True)) as con:
            return con.execute(sql, args).fetchone()
    except sqlite3.Error:
        return None


def _kodex_rows(db_path: Path) -> list[tuple[str, float, Optional[str]]]:
    """KODEX 200 (date, close, fetched_at) 날짜 오름차순 — 한 문장 한 번 읽기(같은 저장본 · 기존 이력 거르기와 같음:
    close 가 null · 0 이하 제외). 파일이 없으면 빈 목록 · 읽기 오류는 그대로 올려 응답이 '읽지 못함'이 된다."""
    p = Path(db_path)
    if not p.exists():
        return []
    with closing(sqlite3.connect(f"file:{p.resolve()}?mode=ro", uri=True)) as con:
        rows = con.execute(
            "SELECT date, close, fetched_at FROM etf_daily_price "
            "WHERE ticker = ? AND close IS NOT NULL AND close > 0 ORDER BY date ASC",
            (KODEX200,),
        ).fetchall()
    return [(r[0], float(r[1]), r[2]) for r in rows]


def _prev_item(prev: Optional[dict], key: str) -> Optional[dict]:
    if not prev or prev.get("status") != "done":
        return None
    it = (prev.get("items") or {}).get(key)
    if not isinstance(it, dict):
        return None
    return {**it, "at": _kst(prev.get("finished_at"))}


def _base(key, label, required, stored, expected, source, received_at) -> dict:
    return {
        "key": key,
        "label": label,
        "required": required,
        "stored_date": stored,
        "expected_date": expected,
        "met": False,
        "state": "check",
        "behind": None,
        "source": source,
        "received_at": received_at,
        "reason": None,
        "last_attempt": None,
    }


def _kr(key, label, required, stored, expected, cal, source, received_at) -> dict:
    out = _base(key, label, required, stored, expected, source, received_at)
    f = _kr_item(key, label, stored, expected, cal)
    out.update(state=f["state"], behind=f["behind"], met=f["state"] == "fresh")
    if f["state"] == "check":
        out["reason"] = f["reason"]
    return out


def _kospi_item(db_path, stored, expected, cal, today, prev) -> dict:
    it = _kr(
        "kospi",
        "코스피 공식 종가",
        True,
        stored,
        expected,
        cal,
        "KRX 공식 종가",
        _kst(read_benchmark_collected_at("KOSPI", db_path=db_path)),
    )
    full = latest_refresh_log(source=KOSPI_SOURCE, db_path=db_path)
    cands = []
    if full:
        ok = bool(full.get("success_count"))
        cands.append(
            {
                "at": _kst(full.get("created_at")),
                "via": "full",
                "status": "ok" if ok else "failed",
                "text": None if ok else kospi_reason(full.get("error_summary"))[1],
            }
        )
    p = _prev_item(prev, "kospi")
    if p and p.get("status") not in ("already", "skipped"):
        cands.append(
            {
                "at": p["at"],
                "via": "prevday",
                "status": p["status"],
                "text": p.get("reason"),
            }
        )
    _attempt(it, cands, today)
    return it


def _attempt(it: dict, cands: list[dict], today: str) -> None:
    """가장 최근 시도를 싣고, 미충족이면 사유 = 오늘 시도 중 사유가 있는 가장 최근 것(확인된 결과) · 없으면 '아직 받지 않음'.

    같은 때 사유 없는 시도(예: ③ 이 반영은 했지만 기준일에 못 미침)와 사유 있는 기록(수급 연결 상태)이 겹쳐도
    고르는 순서에 따라 사유가 사라지지 않게 사유 있는 것만 본다.
    """
    cands = [c for c in cands if c.get("at")]
    it["last_attempt"] = max(cands, key=lambda c: c["at"]) if cands else None
    if it["met"] or it["reason"]:
        return
    told = [c for c in cands if c.get("text") and _today(c["at"], today)]
    if told:
        c = max(told, key=lambda c: c["at"])
        it["reason"] = f"{c['text']} · {_hm(c['at'])} 확인"
    else:
        it["reason"] = NOT_YET


def _flows_item(db_path, stored, expected, cal, today, prev, root) -> dict:
    row = _ro_one(
        db_path,
        "SELECT max(applied_at) FROM market_investor_flow_import WHERE result = 'APPLIED'",
    )
    it = _kr(
        "flows",
        "투자자 수급",
        True,
        stored,
        expected,
        cal,
        "OCI 수집 → PC 반영",
        _kst(row[0]) if row else None,
    )
    cands = []
    imp = latest_refresh_log(source=FLOW_IMPORT_LOG_SOURCE, db_path=db_path)
    if imp:
        link = read_flow_link(db_path, stored)
        cands.append(
            {
                "at": _kst(imp.get("created_at")),
                "via": "prevday" if "prevday_" in str(imp.get("run_id")) else "full",
                "status": "ok" if link.get("state") == "applied" else "failed",
                "text": link.get("text"),
            }
        )
    p = _prev_item(prev, "flows")
    if p and p.get("status") not in ("already", "skipped"):
        cands.append(
            {
                "at": p["at"],
                "via": "prevday",
                "status": p["status"],
                "text": p.get("reason"),
            }
        )
    _attempt(it, cands, today)
    if not it["met"] and it["reason"] == NOT_YET and expected:
        local = [
            b
            for b in local_flow_bundles(root, db_path)
            if (b["last_date"] or "") >= expected
        ]
        if local:
            it["reason"] = (
                f"{NOT_YET}(PC 보관소에 {md(local[-1]['last_date'])}까지 있음)"
            )
    return it


def _kodex_item(rows, expected, cooldown_next) -> dict:
    latest = rows[-1][0] if rows else None
    hit = next((r for r in rows if r[0] == expected), None) if expected else None
    row = (hit[1], hit[2]) if hit else None
    st = price_state(expected, row[1]) if row else None
    it = _base(
        "kodex200",
        "KODEX 200 판정 근거",
        True,
        latest,
        expected,
        "FDR 일별 가격",
        st["fetched_at_kst"] if st else None,
    )
    it["basis_row"] = (
        {"date": expected, "close": row[0], "state": st["state"]} if row else None
    )
    if expected is None:
        it["reason"] = "기준일 확인 불가(거래일 달력)"
        return it
    it["met"] = bool(st) and st["state"] == STATE_AFTER_CLOSE
    it["state"] = "fresh" if it["met"] else "late"
    if it["met"]:
        return it
    # 저장 상태대로 적는다(검증자 F6 — 시각을 해석하지 못한 행을 '장중'으로 단정하지 않음).
    head = "KODEX 200 근거 미확인"
    if row:
        head += (
            f" · {md(expected)} 장중 저장값만 있음"
            if st["state"] == STATE_INTRADAY
            else f" · {md(expected)} 가격의 저장 시점 확인 불가"
        )
    it["reason"] = (
        f"{head} · ETF 전체 갱신 다음 {_hm(cooldown_next)}"
        if cooldown_next
        else f"{head} — [최신 자료 갱신]"
    )
    return it


def _vix_item(db_path, stored, now) -> dict:
    f = vix_freshness(
        stored, now
    )  # 기준 = 미국 마감이 지난 마지막 평일(기존 판정 그대로)
    it = _base(
        "vix",
        "VIX",
        False,
        stored,
        f["compare_date"],
        "FDR(미국 VIX)",
        _kst(read_benchmark_collected_at("VIX", db_path=db_path)),
    )
    it.update(state=f["state"], behind=f["weekdays_behind"], met=f["state"] == "fresh")
    return it


def _macro_item(key, label, series, db_path, stored, expected, cal) -> dict:
    _pts, at = read_macro_series(series, db_path=db_path)
    if key == "wti":
        it = _base(key, label, False, stored, None, "Yahoo", _kst(at))
        it.update(state="observed", met=stored is not None)
        return it
    return _kr(key, label, False, stored, expected, cal, "Yahoo", _kst(at))


def morning_regime(
    rows: list[tuple[str, float, Optional[str]]],
    expected: Optional[str],
    kodex: dict[str, Any],
) -> dict[str, Any]:
    """기준일까지의 KODEX 200 이력으로 기존 산식 · 근거가 확인되지 않으면 unconfirmed."""
    base = {
        "status": "unconfirmed",
        "basis_date": expected,
        "reason": None,
        "context": None,
    }
    if expected is None:
        return {**base, "reason": "기준일 확인 불가(거래일 달력)"}
    if not kodex["met"]:
        return {**base, "reason": f"KODEX 200 {md(expected)} 마감 가격 미확인"}
    hist = [(d, c) for d, c, _at in rows if d <= expected]  # 항목과 같은 한 번 읽기
    ctx = compute_market_context(asof=expected, kodex200_history=hist)
    k = ctx.get("kodex200")
    if not isinstance(k, dict) or k.get("status") != "ok":
        return {**base, "reason": "KODEX 200 판정 근거 부족(저장 이력)", "context": ctx}
    ctx["regime_streak"] = compute_regime_streak(hist)
    k.update(kodex200_return_dates(hist))
    return {**base, "status": "ok", "context": ctx}


def _kospi_rows(db_path: Path) -> list[tuple[str, float]]:
    """KOSPI 공식 종가 (date, close) 날짜 오름차순 — 같은 응답의 다른 저장값 읽기와 같은 함수
    (`read_benchmark_series` · 읽기 전용 · close 가 null · 0 이하 제외 · 파일 · 표가 없으면 빈 목록 — KOSPI 를 아직 한 번도
    받지 않은 PC 에서도 응답 전체가 '읽지 못함'이 되지 않게 · 독립 검토 2026-11-14)."""
    return read_benchmark_series(KOSPI_ID, db_path=db_path)


def kospi_detail(
    kodex_rows: list[tuple[str, float, Optional[str]]],
    kospi: list[tuple[str, float]],
) -> dict[str, Any]:
    """「시장 수치와 거래량」 코스피 수익률 · 위치 — 저장된 KOSPI 공식 종가 끝 행 기준 · 실제 계산 기간과 함께.

    20 · 60거래일 = 시장 판정 응답(`market_regime.compute_kospi_metrics`)과 같은 축
    (KODEX 200 저장 거래일 · close > 0) · 같은 함수(`return_by_trading_days`) · 같은 반올림.
    시작일 = 그 함수가 쓰는 축의 lookback 칸(`axis[i - n]`).
    1년 · 최근 1년 고점 대비 = 같은 함수(`compute_kospi_position_metrics`). 기대 직전 거래일과 맞는지는 보지 않는다
    (그 판정 · 배지는 화면 머리 줄 · 자료 상태가 맡는다)."""
    base: dict[str, Any] = {
        "status": "unavailable",
        "as_of_date": None,
        "r20": None,
        "r60": None,
        "return_1y_pct": None,
        "high_52w_gap_pct": None,
        "reason": None,
    }
    if not kospi:
        return {**base, "reason": "저장된 코스피 공식 종가 없음"}
    as_of = kospi[-1][0]
    axis = [r[0] for r in kodex_rows]
    pos = compute_kospi_position_metrics(
        kospi
    )  # 1년 · 고점 대비는 거래일 날짜 목록이 필요 없다
    if as_of not in axis:
        # 그날 KODEX 200 저장 가격이 없으면(PC 가 꺼져 시장 전체 갱신 전 · ③ 보충으로 코스피만 들어온 날 등) 20 · 60거래일만
        # 계산하지 않는다 — 시장 판정 응답과 같은 날짜 목록이라 그 날짜가 빠지면 같은 값을 만들 수 없음(대신하지 않음).
        return {
            **base,
            "status": "ok",
            "as_of_date": as_of,
            "return_1y_pct": pos.get("return_1y_pct"),
            "high_52w_gap_pct": pos.get("high_52w_gap_pct"),
            "reason": f"{md(as_of)} KODEX 200 저장 가격이 없어 20 · 60거래일은 계산하지 못했습니다",
        }
    i = axis.index(as_of)

    def win(n: int) -> Optional[dict[str, Any]]:
        pct = return_by_trading_days(
            kospi, trading_days=axis, lookback=n, as_of_date=as_of
        )
        if pct is None:
            return None
        return {"start_date": axis[i - n], "end_date": as_of, "pct": _round_pct(pct)}

    return {
        **base,
        "status": "ok",
        "as_of_date": as_of,
        "r20": win(LOOKBACK_20D),
        "r60": win(LOOKBACK_60D),
        "return_1y_pct": pos.get("return_1y_pct"),
        "high_52w_gap_pct": pos.get("high_52w_gap_pct"),
    }


def today_regime(rows: list[tuple[str, float, Optional[str]]]) -> dict[str, Any]:
    """당일 판정 — 저장된 이력 전체(끝 행까지)로 시장 판정 응답과 같은 기존 산식 · 끝 행의 저장 시점을 함께."""
    base: dict[str, Any] = {
        "status": "unconfirmed",
        "basis_date": None,
        "reason": None,
        "context": None,
        "basis_row": None,
    }
    if not rows:
        return {**base, "reason": "KODEX 200 저장 가격 없음"}
    d, c, at = rows[-1]
    st = price_state(d, at)
    base.update(
        basis_date=d,
        basis_row={
            "date": d,
            "close": c,
            "state": st["state"],
            "fetched_at_kst": st["fetched_at_kst"],
        },
    )
    hist = [(r[0], r[1]) for r in rows]
    ctx = compute_market_context(asof=d, kodex200_history=hist)
    k = ctx.get("kodex200")
    if not isinstance(k, dict) or k.get("status") != "ok":
        return {**base, "reason": "KODEX 200 판정 근거 부족(저장 이력)"}
    ctx["regime_streak"] = compute_regime_streak(hist)
    k.update(kodex200_return_dates(hist))
    return {**base, "status": "ok", "context": ctx}


# 설계자 RESULT 재판정 V3 D1(2026-11-13) — 판정 표 [?] 의 점수 산식 설명이 쓰는 기존 판정 상수(읽기만 · 화면에 숫자를
# 따로 적지 않음). 산식 = `market_regime._score_kodex200` · 경계 = `_label_from_score`.
SCORE_RULE = {
    "return_20d_pct": SCORE_THRESHOLD_20D_PCT,
    "return_60d_pct": SCORE_THRESHOLD_60D_PCT,
    "bull_min": REGIME_BULL_MIN_SCORE,
    "bear_max": REGIME_BEAR_MAX_SCORE,
}


def build_morning_basis(
    *,
    db_path: Path = DEFAULT_DB_PATH,
    now: Optional[datetime] = None,
    calendar_dir: Optional[Path] = None,
    evidence_root: Optional[Path] = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(KST).date().isoformat()
    root = Path(evidence_root or evidence_store.EVIDENCE_ROOT)
    try:
        expected = expected_previous_trading_day(today, calendar_dir=calendar_dir)
        stored = stored_dates(db_path)
        prev = read_prevday()
        snap = svc.get_state_snapshot(db_path=db_path)
        cd = int(snap.cooldown_remaining_seconds or 0)
        cooldown_next = (
            (now + timedelta(seconds=cd)).astimezone(KST).isoformat(timespec="seconds")
            if cd > 0
            else None
        )
        rows = _kodex_rows(
            db_path
        )  # KODEX 200 은 이 한 번만 읽는다(항목 · 아침 · 당일 판정 공통)
        kodex = _kodex_item(rows, expected, cooldown_next)
        items = [
            _kospi_item(db_path, stored["kospi"], expected, calendar_dir, today, prev),
            kodex,
            _flows_item(
                db_path, stored["flows"], expected, calendar_dir, today, prev, root
            ),
            _vix_item(db_path, stored["vix"], now),
            _macro_item(
                "usdkrw",
                "원/달러",
                USDKRW,
                db_path,
                stored["usdkrw"],
                expected,
                calendar_dir,
            ),
            _macro_item(
                "wti", "WTI", WTI, db_path, stored["wti"], expected, calendar_dir
            ),
        ]
        regime = morning_regime(rows, expected, kodex)
        today_reg = today_regime(rows)
        kdetail = kospi_detail(rows, _kospi_rows(db_path))
        if kodex["met"] and regime["status"] != "ok":
            # 검증자 F5 — 기준일 마감 가격이 있어도 판정을 계산하지 못하면 '판정 근거'는 미충족
            # (준비 상태 · 끝 줄 · 화면이 같은 판단 · 다시 받아도 이력이 늘지 않으면 그대로라 갱신 안내 없음).
            kodex.update(
                met=False,
                state="late",
                reason=(
                    f"KODEX 200 근거 미확인 · {md(expected)} 마감 가격은 있으나 "
                    f"{(regime['reason'] or '판정 계산 불가').removeprefix('KODEX 200 ')}"
                ),
            )
    except Exception:  # noqa: BLE001 — 읽기 실패는 화면이 '확인 필요'로 보이게
        logger.exception("morning basis: build failed")
        return {
            "status": "invalid",
            "message": "아침 요약 기준을 읽지 못했습니다",
            "today": today,
            "expected_date": None,
            "ready": False,
            "missing": [],
            "items": [],
            "morning_regime": None,
            "today_regime": None,
            "kospi_detail": None,
            "score_rule": SCORE_RULE,
            "full_refresh": None,
        }
    missing = [i["key"] for i in items if i["required"] and not i["met"]]
    return {
        "status": "ok",
        "message": None,
        "today": today,
        "expected_date": expected,
        "ready": expected is not None and not missing,
        "missing": missing,
        "items": items,
        "morning_regime": regime,
        "today_regime": today_reg,
        "kospi_detail": kdetail,
        "score_rule": SCORE_RULE,
        "full_refresh": {
            "cooldown_remaining_seconds": cd,
            "next_available_at": cooldown_next,
        },
    }


@router.get("/market/morning-basis")
def get_morning_basis() -> dict[str, Any]:
    return build_morning_basis(db_path=DEFAULT_DB_PATH)  # 모듈 속성(시험이 바꿔 끼움)
