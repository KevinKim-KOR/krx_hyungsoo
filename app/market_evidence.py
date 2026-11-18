"""POC6-32 V2 — 공통 시장 근거(`GET /market/evidence` · PLAN §4-1 · §4-2 · §6 · §9 I-16 · I-23 · I-24).

일일 · 주간 복사가 같은 시장 근거를 쓰도록 기존 조회를 같은 `now` 로 모아 지표별 칸(값 · 단위 · 출처 · 기준일 · 갱신
상태 · 기간이면 실제 시작 · 끝)을 만든다. 글은 `app/market_evidence_text.py` 가 이 칸만 읽어 만든다. 새 계산 규칙 없음 ·
외부 조회 0 · 시장 DB 파일이 없으면 아무 읽기 없이 `unavailable`(기존 읽기 함수가 파일 · 표를 만들기 때문 · r1 F3) ·
있으면 기존 읽기 함수가 표 확인(빠진 시장 표만 그 함수가 만듦). 쓰는 조회: `build_morning_basis`(KODEX 200 아침 · 당일 판정) ·
`build_market_flow_context`(코스피 · 수급 · 원/달러 · WTI · 사건 · 해석 · VIX 6개월) · 기존 VIX 카드(최신 · 직전 ·
5개 관측 · VIX 만 읽음) · 빠른 시세 저장 파일(검토일 KST 의 저장 시세 + 마지막 시도 성공일 때만 · 판정 Q7 · I-24) ·
`app/market_evidence_reads.py`(60거래일 다섯 분류 합 · 코스피 종가 출처 · 읽기 전용). 60거래일 합이 시장 흐름 응답의
외국인 · 개인 · 기관계 합과 다르면(그 사이 자료가 바뀜) 그 줄은 '확인 불가'. 읽기 하나가 실패하면 그 칸만 '확인 불가'
+ [자료 상태]에 실패(다른 칸은 그대로). 판정 · 코스피 · 수급 셋 다 못 읽으면 `unavailable`(글 없음 · 예전 글 안 씀 · I-23).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from app import market_data_store
from app import market_evidence_reads as reads
from app import market_evidence_text as text
from app.market_freshness_rows import _kr_item
from app.market_risk_reference_service import _build_vix_card
from app.pc_morning_basis import build_morning_basis
from app.pc_quick_quotes import read_quick_quotes
from app.pc_vix_refresh import vix_freshness
from app.supply_fx_oil_context import build_market_flow_context

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))
Obj = Optional[Mapping[str, Any]]

SIX = "6M"
KOSPI_PERIOD_CODES = ("1M", "3M", "6M")
WINDOW_60 = 60
WIN_KEYS = ("foreign", "individual", "institution")  # 시장 흐름 응답의 60거래일 창 칸
# 판정 Q10 · PLAN I-16 — 다섯 분류만 줄에 싣고 국가 · 지자체는 집계 구분에 그 기간 합만 적는다.
FLOW60 = (
    ("foreign", "외국인"),
    ("individual", "개인"),
    ("institution", "기관계"),
    ("other_corp", "기타법인"),
    ("native_foreign", "내국인대우외국인"),
)
NATION = "nation"
SCOPE_60 = (
    "KRX 코스피 종합 · 억원 단위 반올림 · 외국인 = 내국인대우외국인 제외 · "
    "기관계 = 금융투자 등 세부 7 합 · 세부는 따로 더하지 않음"
)
MACRO = {
    "usdkrw": ("원/달러", "원", "런던 날짜", "야후 원/달러 일봉 종가"),
    "wti": ("WTI", "달러", "뉴욕 날짜 · 근월물 선물", "야후 WTI 근월물 선물 일봉 종가"),
}
QUICK_OK = ("updated", "unchanged")
MARKET_STATUS = {"OPEN": "장중", "CLOSE": "마감"}
NO_FLOW_READ = "시장 흐름 자료를 읽지 못함"
NO_FLOW = "투자자별 수급 자료 없음"
NO_KOSPI = "코스피 저장 자료가 없어 계산하지 않음"
NO_DB = "시장 DB 파일이 없어 시장 근거를 만들지 않았습니다"
NOT_SAME_60 = (
    "시장 흐름 응답과 다시 읽은 60거래일 합이 다름"
    "(자료 갱신 중일 수 있음 · [요약 다시 읽기] 뒤 다시 확인)"
)


def _na(reason: str, **extra: Any) -> dict[str, Any]:
    return {"status": "unavailable", "reason": reason, **extra}


def _flow_gap(flow: Obj) -> Optional[str]:
    """시장 흐름 칸을 계산하지 않은 사유(못 읽음 · 코스피가 없어 일찍 끝남 · '없음'으로 쓰지 않음) · 계산했으면 None."""
    if flow is None:
        return NO_FLOW_READ
    return None if flow.get("D") else NO_KOSPI


def _roll(statuses: list[str]) -> str:
    if all(s == "ok" for s in statuses):
        return "ok"
    return "unavailable" if all(s == "unavailable" for s in statuses) else "partial"


def _get(obj: Obj, *path: str) -> Any:
    for k in path:
        obj = (obj or {}).get(k)
    return obj


# ── KODEX 200 시장 판정 ───────────────────────────────────────────────────────
def _ret(k: Mapping[str, Any], n: int, start: str) -> dict[str, Any]:
    v = k.get(f"return_{n}d_pct")
    return {
        "value": v,
        "unit": "%",
        "start": k.get(start),
        "end": k.get("return_end_date"),
    }


def _ma(k: Mapping[str, Any], n: int) -> dict[str, Any]:
    p, d = k.get(f"ma{n}_position"), k.get(f"ma{n}_distance_pct")
    return {"value": k.get(f"ma{n}"), "position": p, "distance_pct": d}


def _regime_entry(reg: Obj, row: Mapping[str, Any], missing: str) -> dict[str, Any]:
    """row = {price_date, price_state, saved_at_kst}(판정 가격 행)."""
    if not reg:
        return _na(missing, **row)
    if reg.get("status") != "ok" or not reg.get("context"):
        return _na(reg.get("reason") or "근거 확인 불가", **row)
    c = reg["context"]
    k = c.get("kodex200") or {}
    s = c.get("regime_streak") or {}
    return {
        "status": "ok",
        "label": c.get("regime_label"),
        "code": c.get("regime_code"),
        "score": c.get("regime_score"),
        "streak_days": s.get("streak_days"),
        "at_least": bool(s.get("at_least")),
        **row,
        "source": "KODEX 200 저장 일별 가격",
        "r20": _ret(k, 20, "return_1m_start_date"),
        "r60": _ret(k, 60, "return_3m_start_date"),
        "ma20": _ma(k, 20),
        "ma60": _ma(k, 60),
    }


def regime_block(morning: Obj) -> dict[str, Any]:
    if not morning or morning.get("status") != "ok":
        why = (morning or {}).get("message") or "아침 요약 기준을 읽지 못했습니다"
        return _na(why, same_basis=False, today=None, morning=None)
    items = morning.get("items") or []
    item = next((i for i in items if i.get("key") == "kodex200"), {})
    krow = item.get("basis_row") or {}
    tr, mr = morning.get("today_regime"), morning.get("morning_regime")
    trow = _get(tr, "basis_row") or {}
    today = _regime_entry(
        tr,
        {
            "price_date": trow.get("date") or _get(tr, "basis_date"),
            "price_state": trow.get("state"),
            "saved_at_kst": trow.get("fetched_at_kst"),
        },
        "당일 판정 칸 없음",
    )
    mor = _regime_entry(
        mr,
        {
            "price_date": krow.get("date") or _get(mr, "basis_date"),
            "price_state": krow.get("state"),
            "saved_at_kst": item.get("received_at"),
        },
        "아침 판정 칸 없음",
    )
    return {
        "status": _roll([today["status"], mor["status"]]),
        "same_basis": text.common_row(morning) is not None,
        "today": today,
        "morning": mor,
    }


# ── 코스피 ───────────────────────────────────────────────────────────────────
def _obs(flow: Obj, key: str) -> Optional[dict]:
    for row in (flow or {}).get("short_lines") or []:
        if row.get("key") == key and isinstance(row.get("obs"), dict):
            return row["obs"]
    return None


def _period(flow: Obj, code: str) -> dict:
    return _get(flow, "periods", code) or {}


def _kospi_period(c: Obj, sources: Obj) -> dict[str, Any]:
    """시장 흐름 응답의 기간 변화(from_date · from → to_date · to · pct) + 시작 · 끝 종가 출처."""
    if not c:
        return _na("기간을 덮는 저장 값 없음")
    s_label, s_off = reads.source_label(sources, c["from_date"])
    e_label, e_off = reads.source_label(sources, c["to_date"])
    src = {"start_source": s_label, "start_official": s_off}
    return {
        "status": "ok",
        **c,
        "unit": "%",
        **src,
        "end_source": e_label,
        "end_official": e_off,
    }


def kospi_block(flow: Obj, sources: Obj, expected: Optional[str]) -> dict[str, Any]:
    if flow is None:
        return _na(NO_FLOW_READ, value=None, periods={})
    obs = _obs(flow, "kospi")
    if not obs:
        return _na("코스피 저장 자료 없음", value=None, periods={})
    label, official = reads.source_label(sources, obs["date"])
    periods = {
        code: _kospi_period(_period(flow, code).get("kospi"), sources)
        for code in KOSPI_PERIOD_CODES
    }
    late = text.is_real_date(expected) and obs["date"] < expected
    return {
        "status": _roll([p["status"] for p in periods.values()]),
        "value": obs["value"],
        "unit": "pt",
        "date": obs["date"],
        "source": label,
        "official": official,
        "prev": obs.get("d1"),
        "expected_date": expected,
        "expected_missing": bool(late),
        "collected_at": _get(flow, "series", "kospi", "collected_at"),
        "periods": periods,
    }


# ── 수급 ───────────────────────────────────────────────────────────────────
def r60_window(flow: Obj) -> Optional[tuple[str, str]]:
    """시장 흐름 응답의 60거래일 창(시작 · 끝) — 창이 온전한 분류가 하나도 없으면 None."""
    r60 = _get(flow, "windows", "r60") or {}
    win = next((r60[k] for k in WIN_KEYS if r60.get(k)), None)
    return (win["from"], win["to"]) if win else None


def _r60_block(flow: Mapping[str, Any], f60: Obj, f60_err: Optional[str]) -> dict:
    win = r60_window(flow)
    if not win:
        return _na("60거래일 창의 수급이 온전하지 않음")
    if f60 is None:
        return _na(f60_err or "60거래일 합을 다시 읽지 못함(저장 표 없음)")
    r60 = _get(flow, "windows", "r60") or {}
    inv = f60.get("investors") or {}
    sums = [(round(r60[k]["sum"]), _get(inv, k, "sum")) for k in WIN_KEYS if r60.get(k)]
    if f60.get("expected") != WINDOW_60 or any(a != b for a, b in sums):
        return _na(NOT_SAME_60)

    def one(k: str, label: str) -> dict[str, Any]:
        v = inv.get(k) or {}
        days, part = v.get("days", 0), bool(v.get("partial"))
        return {
            "key": k,
            "label": label,
            "value": v.get("sum", 0),
            "days": days,
            "partial": part,
        }

    nation = inv.get(NATION) or {}
    return {
        "status": "ok",
        "start": win[0],
        "end": win[1],
        "expected": f60["expected"],
        "unit": "원",
        "investors": [one(k, label) for k, label in FLOW60],
        "nation": {"value": nation.get("sum", 0), "days": nation.get("days", 0)},
        "scope": SCOPE_60,
    }


def flows_block(flow: Obj, f60: Obj, f60_err: Optional[str] = None) -> dict[str, Any]:
    if flow is None:
        why = NO_FLOW_READ
        return _na(why, six=_na(why), w20=_na(why), r60=_na(why))
    base = {
        "source": "투자자별 순매수(OCI 수집 → PC 반영)",
        "unit": "원",
        "latest_date": _get(flow, "series", "flows", "E"),
        "observed_at": _get(flow, "series", "flows", "collected_at"),
    }
    if not flow.get("D"):
        # 공통 비교일(D)이 없어도 수급 최신 날짜는 남긴다 — 화면 대조(basis.flow_date)가 늘 '근거 다름'으로 멈추지 않게
        why = NO_KOSPI
        return _na(why, **base, six=_na(why), w20=_na(why), r60=_na(why))
    if not flow.get("has_flows"):
        return _na(
            NO_FLOW, **base, six=_na(NO_FLOW), w20=_na(NO_FLOW), r60=_na(NO_FLOW)
        )
    p6 = _period(flow, SIX)
    f = _get(p6, "investors", "foreign")
    six = _na("6개월 수급 합 없음")
    if f:  # 합 · 확보 일수 · 있어야 할 일수 · 부분 집계(시장 흐름 응답 그대로)
        start = p6.get("start") or p6.get("boundary")
        cover = {"covered": bool(p6.get("covered", True)), "unit": "원"}
        six = {"status": "ok", **f, "start": start, "end": p6.get("end"), **cover}
    f20 = _get(flow, "windows", "foreign20")  # {recent, previous}: {sum, avg, from, to}
    w20 = _na("20거래일 창의 수급이 온전하지 않음")
    if f20:
        w20 = {"status": "ok", **f20, "trend": _get(flow, "windows", "trend")}
    r60 = _r60_block(flow, f60, f60_err)
    status = _roll([six["status"], w20["status"], r60["status"]])
    return {"status": status, **base, "six": six, "w20": w20, "r60": r60}


# ── 원/달러 · WTI · VIX ──────────────────────────────────────────────────────
def macro_block(flow: Obj, key: str) -> dict[str, Any]:
    label, unit, basis, source = MACRO[key]
    head = {"label": label, "unit": unit, "date_basis": basis, "source": source}
    gap = _flow_gap(flow)
    if gap:
        return _na(gap, **head)
    obs = _obs(flow, key)
    if not obs:
        return _na("저장 자료 없음", **head)
    return {
        "status": "ok",
        **head,
        "value": obs["value"],
        "date": obs["date"],
        "prev": obs.get("d1"),
        "d5": obs.get("d5"),
        "six": _period(flow, SIX).get(key),
        "collected_at": _get(flow, "series", key, "collected_at"),
    }


def vix_block(card: Obj, fresh: Obj, flow: Obj, read_failed: bool = False) -> dict:
    base = {"unit": "", "date_basis": "미국 날짜", "source": "미국 VIX 일별 종가"}
    if read_failed:
        return _na("VIX 저장 자료를 읽지 못함", **base)
    if not card or card.get("availability") != "available" or card.get("close") is None:
        return _na("VIX 저장 자료 없음", **base)
    s = list(card.get("series") or [])
    ok = bool(s) and s[-1][0] == card.get("as_of_date")

    def at(n: int, key: str) -> Optional[dict]:
        if not ok or len(s) < n + 1:
            return None
        return {"date": s[-1 - n][0], "value": s[-1 - n][1], "pct": card.get(key)}

    six = _period(flow, SIX).get("vix")
    return {
        "status": "ok",
        **base,
        "value": card["close"],
        "date": card.get("as_of_date"),
        "prev": at(1, "change_1d_pct"),
        "d5": at(5, "change_5d_pct"),
        "six": six,
        # 6개월 값이 없을 때의 사유 — 시장 흐름을 못 읽음 · 계산 안 함을 '저장 값 없음'으로 쓰지 않음(BE-2)
        "six_reason": None if six else (_flow_gap(flow) or "기간을 덮는 저장 값 없음"),
        "freshness": dict(fresh) if fresh else None,
        "collected_at": _get(flow, "vix_basis", "collected_at"),
    }


# ── 해석 · 오늘 시세 · 사건 · 자료 상태 ──────────────────────────────────────────
def interpretation_block(flow: Obj) -> dict[str, Any]:
    it = _get(flow, "interpretation", SIX)
    p6 = _period(flow, SIX)
    if flow is None or not it or not p6:
        return _na(_flow_gap(flow) or "6개월 해석 자료 없음")
    return {
        "status": "ok",
        "period": SIX,
        "start": p6.get("start") or p6.get("boundary"),
        "end": p6.get("end"),
        "rows": [list(r) for r in it.get("rows") or []],
        "notes": list(it.get("notes") or []),
    }


def quick_block(quick: Obj, review_date: str) -> dict[str, Any]:
    """검토일(KST)의 저장 시세이고 마지막 시도가 성공(updated · unchanged)인 항목만(판정 Q7 · I-24)."""
    q = quick or {}
    shown, missing = [], []
    for it in q.get("items") or []:
        quote = it.get("quote") or {}
        if (
            q.get("status") == "ok"
            and quote.get("trade_date") == review_date
            and _get(it, "last_attempt", "status") in QUICK_OK
            and quote.get("value") is not None
        ):
            ms = quote.get("market_status")
            shown.append(
                {
                    **{k: it.get(k) for k in ("code", "name", "kind")},
                    **quote,
                    "status_text": MARKET_STATUS.get(ms or "", "장 상태 확인 필요"),
                }
            )
        else:
            missing.append(it.get("name"))
    return {
        "review_date": review_date,
        "status": q.get("status") or "invalid",
        "source": "네이버 시세(공식 종가 · 수급 통계 아님)",
        "shown": shown,
        "missing": missing,
    }


def events_block(flow: Obj) -> dict[str, Any]:
    gap = _flow_gap(flow)  # 큰 변화 확인을 하지 않았으면 '없음'으로 쓰지 않는다(BE-1)
    if flow is None or gap:
        return _na(gap or NO_FLOW_READ, items=[])
    chk = flow.get("event_check") or {}
    return {
        "status": "ok",
        "items": [dict(e) for e in flow.get("events") or []],
        "unchecked_text": chk.get("unchecked_text"),
        "empty_text": chk.get("empty_text"),
    }


def _regime_fresh(regime: Mapping[str, Any], expected: Optional[str]) -> dict:
    """시장 판정 행 — 당일 판정 가격일이 기대일 이상이면 최신(화면 확인 창과 같은 비교 · 늦은 거래일 수 없음)."""
    t = regime.get("today") or {}
    last = t.get("price_date") if t.get("status") == "ok" else None
    if last is None:
        return {"state": "check", "reason": t.get("reason") or regime.get("reason")}
    if not text.is_real_date(last) or not text.is_real_date(expected):
        return {"state": "check", "reason": "기대 기준일 확인 불가"}
    state = "late" if last < expected else "fresh"
    return {"state": state, "last_date": last, "expected": expected}


def data_status_block(
    *, review_date: str, expected: Optional[str], f: Mapping[str, Any], flow: Obj
) -> dict[str, Any]:
    """[자료 상태]의 판정 행 — 지금 일일 복사와 같은 범위(코스피 · 시장 판정 · 외국인 수급 · 원/달러).
    코스피는 시장 흐름 응답의 원/달러 · 수급 행과 같은 함수 · 같은 기대일로 판정한다."""
    kospi = _kr_item("kospi", "코스피", f["kospi"].get("date"), expected, None)
    if (
        flow is None
    ):  # 읽기 실패를 '자료 없음'으로 쓰지 않음(BE-2 · 수급 · 원/달러 행과 같은 사유)
        kospi = {**kospi, "state": "check", "reason": NO_FLOW_READ}
    rows = [
        kospi,
        {"label": "시장 판정(KODEX 200)", **_regime_fresh(f["regime"], expected)},
    ]
    items = {i.get("key"): i for i in _get(flow, "freshness", "items") or []}
    for key, label in (("flows", "외국인 수급"), ("usdkrw", "원/달러(런던 날짜)")):
        it = items.get(key)
        if flow is None:
            it = {"state": "check", "reason": NO_FLOW_READ}
        elif not it or it.get("state") == "observed":
            it = {"state": "check", "reason": "기준일 판정 자료 없음"}
        rows.append({**it, "label": label})
    return {"today": review_date, "expected": expected, "rows": rows}


# ── 조립 ───────────────────────────────────────────────────────────────────
def _basis(f: Mapping[str, Any], flow: Obj) -> dict[str, Any]:
    """화면과 복사 근거 대조용(시장 판정 이름 · 가격일 · 상태 · 코스피 · 수급 기준일)."""
    today = _get(f, "regime", "today") or {}
    return {
        "regime_label": today.get("label") if today.get("status") == "ok" else None,
        "regime_price_date": today.get("price_date"),
        "regime_price_state": today.get("price_state"),
        "kospi_date": _get(f, "kospi", "date"),
        "flow_date": _get(f, "flows", "latest_date"),
        "common_end_date": _get(flow, "D"),
    }


def _out(
    now: datetime, status: str, f: Mapping[str, Any], flow: Obj, **kw: Any
) -> dict:
    ok = status != "unavailable"
    return {
        "status": status,
        "message": kw.get("message"),
        "generated_at": now.astimezone(KST).isoformat(timespec="seconds"),
        "review_date": now.astimezone(KST).date().isoformat(),
        "basis": _basis(f, flow),
        "fields": dict(f),
        "daily_text": text.daily_text(f) if ok else None,
        "evidence_items": text.evidence_items(f) if ok else [],
        "data_status": kw.get("parts") or (text.status_parts(f) if f else []),
    }


def assemble(
    *,
    morning: Obj,
    flow: Obj,
    vix: Obj,
    vix_fresh: Obj,
    quick: Obj,
    kospi_sources: Obj,
    flow60: Obj,
    now: datetime,
    read_errors: Optional[list[str]] = None,
    flow60_error: Optional[str] = None,
    vix_failed: bool = False,
) -> dict[str, Any]:
    """입력은 모두 인자(순수) — 시험은 합성 응답으로 이 함수를 부른다."""
    review_date = now.astimezone(KST).date().isoformat()
    expected = _get(flow, "freshness", "expected_kr") or _get(morning, "expected_date")
    f: dict[str, Any] = {
        "regime": regime_block(morning),
        "kospi": kospi_block(flow, kospi_sources, expected),
        "flows": flows_block(flow, flow60, flow60_error),
        "usdkrw": macro_block(flow, "usdkrw"),
        "wti": macro_block(flow, "wti"),
        "vix": vix_block(vix, vix_fresh, flow, vix_failed),
        "interpretation": interpretation_block(flow),
        "events": events_block(flow),
        "quick": quick_block(quick, review_date),
        "read_errors": list(read_errors or []),
    }
    f["data_status"] = data_status_block(
        review_date=review_date, expected=expected, f=f, flow=flow
    )
    core = [f[k]["status"] for k in ("regime", "kospi", "flows")]
    rest = [f[k]["status"] for k in ("usdkrw", "wti", "vix", "interpretation")]
    if all(s == "unavailable" for s in core):
        why = "시장 판정 · 코스피 · 수급 자료를 모두 읽지 못해 시장 근거를 만들지 않았습니다"
        return _out(now, "unavailable", f, flow, message=why)
    whole = core + rest + [f["events"]["status"]]
    return _out(now, "ok" if all(s == "ok" for s in whole) else "partial", f, flow)


def _kospi_dates(flow: Obj) -> list[str]:
    obs = _obs(flow, "kospi")
    out = [obs["date"]] if obs else []
    for code in KOSPI_PERIOD_CODES:
        c = _period(flow, code).get("kospi")
        if c:
            out += [c["from_date"], c["to_date"]]
    return out


def build_market_evidence(
    *, now: Optional[datetime] = None, db_path: Optional[Path] = None
) -> dict[str, Any]:
    """`GET /market/evidence` — 기존 조회를 같은 `now` 로 읽어 `assemble` 에 넘긴다(읽기 실패는 그 칸만)."""
    now = now or datetime.now(timezone.utc)
    db = Path(db_path) if db_path else market_data_store.DEFAULT_DB_PATH
    if not db.exists():  # 만들지 않음(r1 F3)
        return _out(now, "unavailable", {}, None, message=NO_DB, parts=[NO_DB])
    errors: list[str] = []

    def read(what: str, fn: Callable[[], Any]) -> tuple[Any, bool]:
        try:
            return fn(), False
        except Exception:  # noqa: BLE001 — 그 칸만 '확인 불가'(다른 칸은 그대로)
            logger.exception("market evidence: %s", what)
            errors.append(what)
            return None, True

    morning, _ = read(
        "아침 요약 기준 읽기 실패", lambda: build_morning_basis(db_path=db, now=now)
    )
    flow, _ = read(
        "시장 흐름 자료 읽기 실패",
        lambda: build_market_flow_context(db_path=db, now=now),
    )
    card = lambda: reads.vix_card(_build_vix_card(db_path=db))  # noqa: E731
    vix, vix_failed = read("VIX 읽기 실패", card)
    fresh = vix_freshness(vix.get("as_of_date"), now) if vix else None
    quick, _ = read("오늘 시세 저장 파일 읽기 실패", read_quick_quotes)
    sources = None
    if flow:
        dates = _kospi_dates(flow)
        src = lambda: reads.kospi_sources(dates, db_path=db)  # noqa: E731
        sources, _ = read("코스피 종가 출처 읽기 실패", src)
    win, flow60, f60_failed = r60_window(flow), None, False
    if win:
        keys = tuple(k for k, _ in FLOW60) + (NATION,)
        sums = lambda: reads.investor_sums(*win, keys, db_path=db)  # noqa: E731
        flow60, f60_failed = read("60거래일 수급 다시 읽기 실패", sums)
    try:
        return assemble(
            morning=morning,
            flow=flow,
            vix=vix,
            vix_fresh=fresh,
            quick=quick,
            kospi_sources=sources,
            flow60=flow60,
            now=now,
            read_errors=errors,
            flow60_error="60거래일 합을 다시 읽지 못함" if f60_failed else None,
            vix_failed=vix_failed,
        )
    except Exception:  # noqa: BLE001 — 조립 실패 = 글 없음(예전 글로 대신하지 않음)
        logger.exception("market evidence: assemble failed")
        why = "시장 근거를 만들지 못했습니다"
        return _out(now, "unavailable", {}, None, message=why, parts=errors + [why])
