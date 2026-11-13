"""POC6-29 보완 2차 — ③ 전일 자료 보충([최신 자료 갱신] 묶음 작업 · PLAN §10-4 · S 판정 Q-S2 · Q-S3).

② 시장 전체 갱신이 6시간 대기(`skipped_cooldown`)로 건너뛰었을 때만 묶음 작업이 부른다. 모자란 항목만 기존 경로로 받는다:

| 항목 | 대상(받기 전 저장일) | 경로(기존 함수 그대로) |
|---|---|---|
| 코스피 공식 종가 | 직전 국내 거래일보다 이름 | `refresh_kospi_benchmark`(KRX) |
| 투자자 수급 | 직전 국내 거래일보다 이름 | PC 보관소에 기준일을 채운 미반영 묶음이 있으면 가져오기 없이 반영 |
|  |  | (`refresh_flows_from_oci(skip_pull=True)`) · 없으면 가져오기 + 반영 |
| VIX | 미국 완료 거래일(`last_settled_us_date`)보다 이름 | `refresh_pc_vix` |
| 원/달러 · WTI | 원/달러가 직전 국내 거래일보다 이름(POC6-27 최신성 규칙 · WTI 는 함께 받음) | `refresh_fx_wti` |

KODEX 200 · ETF 전체 가격 · NAV 는 받지 않는다(6시간 대기 그대로 · Q-S3). 시작 확인 · 표시는 전체 갱신과 같은 잠금
(`market_refresh_service._service.lock`) 안에서 하고, 도는 동안 전체 갱신 · VIX 다시 받기 시작은 `prevday_running` 으로
거절된다. 전체 갱신 상태 · 마지막 성공 시각 · '마지막 전체 갱신'(코스피 기록 행)은 건드리지 않는다 — 코스피 기록 행은
남기지 않고, 원/달러 · WTI · 수급 기록 행은 기존 시장 흐름 출처(마지막 전체 갱신 계산에서 이미 빠지는 출처)로 남긴다.
결과는 `state/market_cache/prevday_fill_latest.json`(아침 기준 읽기가 마지막 시도 사유로 읽음).
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import tempfile
import time
import uuid
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from app.market_benchmark_store import refresh_kospi_benchmark
from app.market_data_store import DEFAULT_DB_PATH, log_refresh
from app.market_refresh_state_store import VIX_RETRY_SCOPE, read_state
from app.ml_evidence import store as evidence_store
from app.oci_flow_import import _flow_section, refresh_flows_from_oci
from app.pc_vix_refresh import last_settled_us_date, refresh_pc_vix
from app.supply_fx_oil_calc import md
from app.supply_fx_oil_refresh import collection_start, refresh_fx_wti
from app.supply_fx_oil_store import (
    FX_WTI_LOG_SOURCE,
    USDKRW,
    WTI,
    read_benchmark_series,
    read_investor_flows,
    read_macro_series,
)
from app.trading_day_lag import expected_previous_trading_day

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
PREVDAY_FILE = Path("state/market_cache/prevday_fill_latest.json")
LABELS = {
    "kospi": "코스피 공식 종가",
    "flows": "투자자 수급",
    "vix": "VIX",
    "usdkrw": "원/달러",
    "wti": "WTI",
}
ERROR_TEXT = "받는 중 오류가 났습니다"


def stored_dates(db_path: Path) -> dict[str, Optional[str]]:
    """자료별 저장 마지막 날짜(읽기 전용 · 없으면 None)."""
    kospi = read_benchmark_series("KOSPI", db_path=db_path)
    vix = read_benchmark_series("VIX", db_path=db_path)
    flows, _ = read_investor_flows(db_path=db_path)
    fx, _ = read_macro_series(USDKRW, db_path=db_path)
    oil, _ = read_macro_series(WTI, db_path=db_path)
    flow_dates = [d for pts in flows.values() for d, _ in pts]
    return {
        "kospi": kospi[-1][0] if kospi else None,
        "flows": max(flow_dates) if flow_dates else None,
        "vix": vix[-1][0] if vix else None,
        "usdkrw": fx[-1][0] if fx else None,
        "wti": oil[-1][0] if oil else None,
    }


def _done_runs(db_path: Path) -> set[str]:
    """이미 반영 · 제외 기록이 있는 묶음(읽기 전용 · 표 없으면 빈 집합)."""
    p = Path(db_path)
    if not p.exists():
        return set()
    try:
        uri = f"file:{p.resolve()}?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as con:
            row = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='market_investor_flow_import'"
            ).fetchone()
            if not row:
                return set()
            return {
                r[0]
                for r in con.execute(
                    "SELECT evidence_run_id FROM market_investor_flow_import"
                )
            }
    except sqlite3.Error:
        logger.exception("prevday: import table unreadable")
        return set()


def local_flow_bundles(root: Path, db_path: Path) -> list[dict[str, Any]]:
    """PC 보관소의 수급 구역 있는 공개 완료 묶음(run_id 순) — 받은 마지막 날짜 · 반영 여부 · 상태."""
    try:
        runs, _problems = evidence_store.list_runs(Path(root))
    except Exception:  # noqa: BLE001 — 보관소를 못 읽으면 '없음'(가져오기 경로로 간다)
        logger.exception("prevday: evidence store unreadable")
        return []
    done = _done_runs(db_path)
    out = []
    for run in runs:
        f = _flow_section(run.manifest)
        if f is None:
            continue
        rec = [d for d in (f.get("received") or []) if isinstance(d, str)]
        out.append(
            {
                "run_id": run.run_id,
                "status": f.get("status"),
                "last_date": max(rec) if rec else None,
                "applied": run.run_id in done,
            }
        )
    return out


def local_flow_cover(
    root: Path, db_path: Path, expected: str
) -> Optional[dict[str, Any]]:
    """기준일을 채운 미반영 공개 묶음(OK · PARTIAL)이 PC 보관소에 있으면 그 묶음(가장 최근) · 없으면 None."""
    cover = [
        b
        for b in local_flow_bundles(root, db_path)
        if not b["applied"]
        and b["status"] in ("OK", "PARTIAL")
        and b["last_date"] is not None
        and b["last_date"] >= expected
    ]
    return cover[-1] if cover else None


def kospi_reason(error: Optional[str]) -> tuple[str, str]:
    """`refresh_kospi_benchmark` 의 error → (상태, 화면 사유). 확인된 결과만 말한다(공개 예정 시각 추정 없음)."""
    e = str(error or "")
    if e.startswith("source_stale"):
        return "unchanged", "KRX 에 아직 기준일 자료가 없음"
    if e == "api_key_missing":
        return "failed", "설정 확인 필요(KRX 키 없음)"
    if e == "expected_date_unknown":
        return "failed", "기준일 확인 불가(거래일 달력)"
    if e.startswith("fetch_failed"):
        return "failed", "KRX 받기 실패"
    return "failed", "KRX 자료 확인 필요"


def _flow_reason(problems: list[str]) -> str:
    head = "투자자 수급("
    texts = [
        p.removeprefix(head).removesuffix(")") if p.startswith(head) else p
        for p in problems
    ]
    return " · ".join(dict.fromkeys(texts)) or ERROR_TEXT


def _item(key: str, status: str, before: Optional[str], **extra: Any) -> dict:
    return {
        "label": LABELS[key],
        "status": status,
        "before": before,
        "after": before,
        "reason": None,
        **extra,
    }


def _now_iso(now: datetime) -> str:
    return now.astimezone(KST).isoformat(timespec="seconds")


def _write(result: dict[str, Any]) -> None:
    """임시 파일에 쓴 뒤 교체(빠른 시세 저장과 같은 방식 · 실패하면 원래 파일 그대로)."""
    text = json.dumps(result, ensure_ascii=False, indent=2)
    PREVDAY_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=".prevday_fill_latest.", suffix=".tmp", dir=str(PREVDAY_FILE.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, PREVDAY_FILE)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def read_prevday() -> Optional[dict[str, Any]]:
    """마지막 ③ 결과(없음 · 읽지 못함 = None)."""
    try:
        data = json.loads(PREVDAY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def skipped(reason: str) -> dict[str, Any]:
    """실행하지 않음(파일에 쓰지 않음 · 묶음 작업 단계 결과로만)."""
    return {"status": "skipped", "reason": reason, "id": None, "items": {}}


def _try(key: str, fn: Callable[[], Any]) -> tuple[Any, bool]:
    try:
        return fn(), True
    except Exception:  # noqa: BLE001 — 항목마다 격리(다른 항목 계속)
        logger.exception("prevday: %s step failed", key)
        return None, False


def run_prevday_fill(
    *,
    db_path: Path = DEFAULT_DB_PATH,
    now: Optional[datetime] = None,
    evidence_root: Optional[Path] = None,
    calendar_dir: Optional[Path] = None,
    kospi_refresher: Optional[Callable[[], dict]] = None,
    flows_refresher: Optional[Callable[[bool], list[str]]] = None,
    vix_refresher: Optional[Callable[[], Optional[str]]] = None,
    fxwti_refresher: Optional[Callable[[], list[str]]] = None,
) -> dict[str, Any]:
    """③ 실행. 결과 = {status: done · skipped, id, expected_date, started_at, finished_at, items{…}}."""
    from app import market_refresh_service as svc

    now = now or datetime.now(timezone.utc)
    root = Path(evidence_root or evidence_store.EVIDENCE_ROOT)
    with svc._service.lock:
        if svc._service.state.status == "running":
            return skipped("시장 전체 갱신이 진행 중입니다 — 같은 수집에서 받습니다")
        row = read_state(db_path=db_path, scope=VIX_RETRY_SCOPE)
        if row is not None and row.last_attempt_status == "running":
            return skipped("VIX 다시 받기가 진행 중입니다")
        if svc._service.prevday_running:
            return skipped(svc.PREVDAY_RUNNING_TEXT)
        svc._service.prevday_running = True
    pid = f"prevday_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    started = _now_iso(now)
    try:
        items = _fill(
            pid,
            db_path=db_path,
            now=now,
            root=root,
            calendar_dir=calendar_dir,
            kospi_refresher=kospi_refresher,
            flows_refresher=flows_refresher,
            vix_refresher=vix_refresher,
            fxwti_refresher=fxwti_refresher,
        )
    finally:
        with svc._service.lock:
            svc._service.prevday_running = False
    result = {
        "status": "done",
        "reason": None,
        "id": pid,
        "expected_date": items.pop("_expected"),
        "started_at": started,
        "finished_at": _now_iso(datetime.now(timezone.utc)),
        "items": items,
    }
    try:
        _write(result)
    except (
        Exception
    ):  # noqa: BLE001 — 기록 실패는 결과에 남기고 화면은 묶음 작업 결과로 본다
        logger.exception("prevday: result file write failed")
        result["reason"] = "결과 기록을 저장하지 못했습니다"
    return result


def _fill(
    pid: str,
    *,
    db_path: Path,
    now: datetime,
    root: Path,
    calendar_dir: Optional[Path],
    kospi_refresher,
    flows_refresher,
    vix_refresher,
    fxwti_refresher,
) -> dict[str, Any]:
    today: date = now.astimezone(KST).date()
    expected = expected_previous_trading_day(
        today.isoformat(), calendar_dir=calendar_dir
    )
    before = stored_dates(db_path)
    items: dict[str, Any] = {"_expected": expected}
    late = {
        k: expected is not None and (before[k] is None or before[k] < expected)
        for k in ("kospi", "flows", "usdkrw")
    }
    # 코스피 공식 종가 — KRX(기존 전체 갱신과 같은 함수 · 코스피 기록 행은 남기지 않음)
    if expected is None:
        items["kospi"] = _item(
            "kospi", "failed", before["kospi"], reason="기준일 확인 불가(거래일 달력)"
        )
    elif not late["kospi"]:
        items["kospi"] = _item("kospi", "already", before["kospi"])
    else:
        fn = kospi_refresher or (
            lambda: refresh_kospi_benchmark(
                end_date=today, db_path=db_path, calendar_dir=calendar_dir
            )
        )
        res, ok = _try("kospi", fn)
        status, reason = (
            ("failed", ERROR_TEXT)
            if not ok
            else (
                ("fetched", None)
                if (res or {}).get("status") == "ok"
                else kospi_reason((res or {}).get("error"))
            )
        )
        items["kospi"] = _item("kospi", status, before["kospi"], reason=reason)
    # 투자자 수급 — PC 보관소 먼저(기준일을 채운 미반영 묶음) · 없으면 가져오기 + 반영
    if expected is None or not late["flows"]:
        items["flows"] = _item(
            "flows", "already" if expected else "failed", before["flows"], via=None
        )
        if expected is None:
            items["flows"]["reason"] = "기준일 확인 불가(거래일 달력)"
    else:
        cover = local_flow_cover(root, db_path, expected)
        via = "local" if cover else "pull"

        def _flows() -> list[str]:
            if flows_refresher is not None:
                return flows_refresher(cover is not None)
            return refresh_flows_from_oci(
                db_path=db_path,
                refresh_id=pid,
                asof=today.isoformat(),
                root=root,
                skip_pull=cover is not None,
            )

        problems, ok = _try("flows", _flows)
        items["flows"] = _item("flows", "pending", before["flows"], via=via)
        if not ok:
            items["flows"].update(status="failed", reason=ERROR_TEXT)
        elif problems:
            items["flows"].update(status="failed", reason=_flow_reason(problems))
        else:
            items["flows"]["status"] = "applied"
    # VIX — 미국 완료 거래일 기준(기존 함수 · 기록 행 없음)
    settled = last_settled_us_date(now).isoformat()
    if before["vix"] is not None and before["vix"] >= settled:
        items["vix"] = _item("vix", "already", before["vix"])
    else:
        msg, ok = _try(
            "vix",
            vix_refresher or (lambda: refresh_pc_vix(db_path=db_path, now_utc=now)),
        )
        items["vix"] = _item(
            "vix",
            "fetched" if ok and msg is None else "failed",
            before["vix"],
            reason=None if ok and msg is None else (msg or ERROR_TEXT),
        )
    # 원/달러 · WTI — 원/달러가 늦을 때 함께(기록 행 = 기존 시장 흐름 출처 · 이 ③ id)
    if not late["usdkrw"]:
        items["usdkrw"] = _item("usdkrw", "already", before["usdkrw"])
        items["wti"] = _item(
            "wti", "skipped", before["wti"], reason="원/달러가 최신이라 함께 받지 않음"
        )
    else:
        t0 = time.perf_counter()

        def _fx() -> list[str]:
            if fxwti_refresher is not None:
                return fxwti_refresher()
            kdates = [d for d, _ in read_benchmark_series("KOSPI", db_path=db_path)]
            return refresh_fx_wti(
                db_path=db_path, now_utc=now, start=collection_start(kdates, today)
            )

        bad, ok = _try("fx_wti", _fx)
        bad = ["원/달러 · WTI(오류)"] if not ok else list(bad or [])
        try:
            log_refresh(
                run_id=f"market-flow-fxwti-{pid}",
                source=FX_WTI_LOG_SOURCE,
                asof=today.isoformat(),
                attempted=1,
                success=0 if bad else 1,
                fail=1 if bad else 0,
                runtime_seconds=round(time.perf_counter() - t0, 3),
                error_summary=", ".join(bad)[:200] or None,
                db_path=db_path,
            )
        except Exception:  # noqa: BLE001 — 기록 실패도 보충을 멈추지 않는다
            logger.exception("prevday: fx/wti log failed")
        reason = ", ".join(bad) or None
        for k in ("usdkrw", "wti"):
            items[k] = _item(
                k, "failed" if bad else "fetched", before[k], reason=reason
            )
    after = stored_dates(db_path)
    for k in LABELS:
        it = items[k]
        it["after"] = after[k]
        changed = (after[k] or "") > (it["before"] or "")
        if it["status"] in ("fetched", "applied") and not changed:
            it["status"] = "unchanged"
            if k == "flows":
                newest = [
                    b for b in local_flow_bundles(root, db_path) if b["last_date"]
                ]
                it["reason"] = (
                    f"OCI 수집본에 기준일 자료 없음(마지막 수집본 {md(newest[-1]['last_date'])}까지)"
                    if newest
                    else "OCI 수집본에 기준일 자료 없음"
                )
            elif k == "kospi":
                it["reason"] = "KRX 에 아직 기준일 자료가 없음"
            else:
                it["reason"] = it["reason"] or "원천에 새 완료 자료 없음"
        elif changed and it["status"] in ("failed", "unchanged"):
            it["status"] = "fetched"  # 일부 실패여도 날짜는 나아짐(사유는 남김)
    return items
