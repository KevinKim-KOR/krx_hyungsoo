"""보유와 후보의 구성종목 비교 — 짝 비중 · 내 보유 전체의 확인된 노출(POC6-31 STEP 4 · PLAN C21 · C24).

판정 §2 둘째 · 셋째 · Q11 (b) · Q19 (a). 읽기 전용 · 외부 호출 0 · 응답에 금액 없음(%만 · POC6-24 규칙).

```text
후보      원천일이 확인된 마지막 구성(`etf_constituents_status.read_snapshots`)의 원본 비중 순위 1 ~ 10행 중
          식별 가능한 주식(`constituent_row_kind` · 현금 · 채권 · 파생 · ETF · 종류 미확인 가림)
보유      등록 보유를 종목 단위로 합산(모든 계좌) · ETF 목록(`etf_master`)에 있으면 보유 ETF, 없으면 직접 보유
          (개별 주식 · 비교 요약 `is_stock` 과 같은 규칙)
평가 비중  그 종목 평가액 ÷ 현금 제외 보유 평가액(시세 있는 행 합 · `holdings_capital.view` 와 같은 분모)
          · 소수 넷째 자리(%)로 정해 계산 입력으로 쓴다(펼쳐 보기에 그 자릿수 그대로 · 손으로 다시 계산 가능)
          · 같은 종목 계좌 행 하나라도 시세가 없으면 그 종목 비중은 미확인(합산 · 0 으로 채우지 않음)
노출 합계일 D = 보유 ETF 중 원천일이 확인된 가장 최근 실제 구성일 · D 의 보유 ETF만 합산 · 다른 날짜는 참고
노출      주식 k = Σ(D 보유 ETF 평가 비중 × 그 ETF 안 k 편입 비중 ÷ 100) + k 직접 보유 평가 비중
          · 편입 비중 = 그 ETF 저장 행 전체 · Decimal 로 정확히 곱하고 더한 뒤 한 번 반올림(소수 둘째)
저장 범위  원천 전체 = 수집 작업이 확인 기록 끝에 남긴 표시(원천 항목 수 < 요청 깊이 30 · 버린 항목 없음 · 검토 지적
          backend#0) → 없는 주식은 '0(확인)'. 그 밖(30행 · 예전 10행 · 표시 없는 기록) = '저장 범위에서 미확인'
노출 합계일 · 시세 없는 ETF 는 합계에 못 들어가므로 노출 합계일을 정할 때 빼다(검토 지적 backend#1)
ETF 목록  못 읽거나 비면 보유 ETF · 직접 보유를 가를 수 없어 'ETF 목록 확인 불가'(0 으로 보이지 않게 · backend#5)
분모 없음  보유를 못 읽거나 시세 있는 보유가 없어도 후보 · 고른 보유의 편입 비중(짝 칸)은 보인다 · 노출만 '비중 확인
          불가'(검토 지적 frontend#2)
근거 지문  이 응답(지문 칸 제외)의 정규 JSON SHA-256 — 계산 입력 · 날짜 · 상태 · 확인 범위 · 후보 · 고른 보유 ·
          선정 조건이 모두 응답에 있다(판단 근거 미리보기가 같은 함수로 다시 계산해 대조 · STEP 5 C25)
```
"""

from __future__ import annotations

import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable, Mapping, Optional, Sequence

from app.constituent_row_kind import DOMESTIC_STOCK, STOCK_KINDS, row_kind
from app.constituents_cross_family import confirmed_rows
from app.etf_constituents_service import DEFAULT_TOP_K, LEGACY_TOP_K
from app.pc_etf_compare_groups import TOP_CONSTITUENTS

W_STEP = Decimal("0.0001")  # 평가 비중(%) 계산 입력 자릿수
R_STEP = Decimal("0.01")  # 합계 반올림(한 번)

STATUS_OK = "ok"
STATUS_HOLDINGS_UNREADABLE = "holdings_unreadable"  # 보유 목록을 읽지 못함
STATUS_NO_HOLDINGS = "no_holdings"
STATUS_NO_WEIGHT_BASIS = "no_weight_basis"  # 분모 없음 = '비중 확인 불가'
STATUS_NO_CANDIDATE_DATA = (
    "no_candidate_data"  # 후보 구성 자료 없음 · 원천 기준일 미확인
)
STATUS_NO_ETF_LIST = "no_etf_list"  # ETF 목록을 읽지 못함 · 비어 있음

STATE_CONFIRMED = "confirmed"
STATE_UNCONFIRMED = "unconfirmed"  # 저장 자료는 있으나 원천일 미확인(보존 자료 날짜만)
STATE_NO_DATA = "no_data"

RANGE_FULL = "full"  # 원천이 준 전체(확인 기록 끝 표시)
RANGE_DEPTH = "depth"  # 요청 깊이(30행)까지 다 받음 — 그 밖은 모름
RANGE_LEGACY = "legacy"  # 예전 10행 자료 — 그 밖은 모름
RANGE_UNVERIFIED = "unverified"  # 원천 전체 표시 없음(표시 전 기록 · 원천 항목 일부를 버림) — 그 밖은 모름
WEIGHT_UNKNOWN = (
    "weight_unknown"  # 노출 미확인 사유: 저장 행은 있으나 비중을 읽을 수 없음
)

USE_SUM = "sum"  # 노출 합계일 D 의 보유 ETF — 합산
USE_OTHER_DATE = "other_date"  # 다른 구성일 — 참고(합계 밖)
USE_UNCONFIRMED = "unconfirmed"  # 원천 기준일 미확인 — 빠짐
USE_NO_DATA = "no_data"  # 구성 자료 없음 — 빠짐
USE_NO_WEIGHT = "no_weight"  # 평가액 미확인(시세 없는 계좌 행) — 분모 밖
USE_DIRECT = "direct"  # 직접 보유(개별 주식)

PAIR_FOUND = "found"
PAIR_WEIGHT_UNKNOWN = "weight_unknown"  # 편입은 확인 · 비중을 읽을 수 없음(0 으로 보지 않음 · 검증자 r1 F10)
PAIR_ZERO = "zero"  # 0(확인)
PAIR_OUT_OF_RANGE = "out_of_range"  # 저장 범위에서 미확인
PAIR_SELF = "self"  # 고른 보유가 이 주식 자체
PAIR_NOT_APPLICABLE = "not_applicable"  # 고른 보유가 다른 개별 주식
PAIR_UNCONFIRMED = "unconfirmed"
PAIR_NO_DATA = "no_data"


def dstr(d: Optional[Decimal]) -> Optional[str]:
    """Decimal → 지수 표기 없는 글(끝 0 지움 · 계산에 쓴 자릿수 그대로)."""
    if d is None:
        return None
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def dec(v: Any) -> Optional[Decimal]:
    """저장 실수 → Decimal(짧은 표기 그대로 · 3.12 → 3.12)."""
    if v is None or isinstance(v, bool):
        return None
    try:
        d = Decimal(repr(float(v)))
    except (TypeError, ValueError):
        return None
    return d if d.is_finite() else None


def stored_range(n: int, complete: bool) -> str:
    """저장 범위 — 원천 전체 표시가 있을 때만 '원천 전체'(저장 행 수만으로는 가르지 않음 · 검토 지적 backend#0)."""
    if complete:
        return RANGE_FULL
    if n >= DEFAULT_TOP_K:
        return RANGE_DEPTH
    if n == LEGACY_TOP_K:
        return RANGE_LEGACY
    return RANGE_UNVERIFIED


def condition_of(
    *,
    screen: Optional[str],
    basis: Optional[str],
    side: Optional[str],
    rank: Optional[int],
    start_date: Optional[str],
    end_date: Optional[str],
    filters: Mapping[str, Any],
) -> dict[str, Any]:
    """선정 조건(지문에 들어감 · 화면 GET 과 미리보기 요청이 같은 함수로 만든다)."""
    return {
        "screen": screen or None,
        "basis": basis or None,
        "side": side or None,
        "rank": rank,
        "start_date": start_date or None,
        "end_date": end_date or None,
        "filters": {k: bool(filters.get(k)) for k in sorted(filters)},
    }


def holding_weights(enriched: Sequence[Any], etf_tickers: set[str]) -> dict[str, Any]:
    """보유 행 → 종목 단위 평가 비중(금액은 여기서만 쓰고 돌려주지 않음)."""
    priced = [
        Decimal(repr(r.eval_amount)) for r in enriched if r.eval_amount is not None
    ]
    total = sum(priced, Decimal(0))
    groups: dict[str, list[Any]] = {}
    for r in enriched:
        groups.setdefault(r.ticker, []).append(r)
    items = []
    for tk, rows in groups.items():
        known = all(r.eval_amount is not None for r in rows)
        w = None
        if known and total > 0:
            amount = sum((Decimal(repr(r.eval_amount)) for r in rows), Decimal(0))
            w = (amount / total * 100).quantize(W_STEP, rounding=ROUND_HALF_UP)
        items.append(
            {"ticker": tk, "name": rows[0].name, "weight": w, "etf": tk in etf_tickers}
        )
    return {
        "items": items,
        "rows": len(enriched),
        "priced_rows": len(priced),
        "denominator": total > 0,
    }


def _etf_state(snap: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    snap = snap or {}
    conf = snap.get("confirmed")
    if conf:
        rows = confirmed_rows(conf)
        return {
            "state": STATE_CONFIRMED,
            "asof": conf["asof"],
            "stored_rows": len(rows),
            "range": stored_range(len(rows), bool(conf.get("complete"))),
            "rows": rows,
        }
    latest = snap.get("latest")
    if latest:
        return {
            "state": STATE_UNCONFIRMED,
            "asof": latest["asof"],
            "stored_rows": int(latest["rows"]),
            "range": None,
            "rows": [],
        }
    return {
        "state": STATE_NO_DATA,
        "asof": None,
        "stored_rows": 0,
        "range": None,
        "rows": [],
    }


def _find(rows: Iterable[Mapping[str, Any]], key: str) -> Optional[Mapping[str, Any]]:
    return next((r for r in rows if r["match_key"] == key), None)


def _is_direct_match(row: Mapping[str, Any], kind: str, ticker: str) -> bool:
    """직접 보유 주식 = 국내 주식 행의 종목코드(또는 대조 키)가 보유 종목코드와 같을 때."""
    return kind == DOMESTIC_STOCK and ticker in (row.get("ticker"), row.get("key"))


def _stored_sum(rows: Iterable[Mapping[str, Any]]) -> Optional[str]:
    """저장 행 비중 합 — 비중을 읽을 수 없는 행이 하나라도 있으면 None(0 으로 채우지 않음 · F10)."""
    ws = [dec(r["weight_pct"]) for r in rows]
    if any(w is None for w in ws):
        return None
    return dstr(sum(ws, Decimal(0)))


def _pair(
    sel: Optional[dict[str, Any]], row: Mapping[str, Any], kind: str
) -> Optional[dict[str, Any]]:
    """고른 보유 쪽 칸 — 없으면 None(고른 보유가 없는 화면)."""
    if sel is None:
        return None
    if not sel["etf"]:
        if _is_direct_match(row, kind, sel["ticker"]):
            return {"state": PAIR_SELF}
        return {"state": PAIR_NOT_APPLICABLE}
    st = sel["cons"]
    if st["state"] == STATE_UNCONFIRMED:
        return {"state": PAIR_UNCONFIRMED, "asof": st["asof"]}
    if st["state"] == STATE_NO_DATA:
        return {"state": PAIR_NO_DATA}
    hit = _find(st["rows"], row["match_key"])
    if hit is not None:
        w = dec(hit["weight_pct"])
        if w is None:
            return {"state": PAIR_WEIGHT_UNKNOWN}
        return {"state": PAIR_FOUND, "weight": dstr(w)}
    if st["range"] == RANGE_FULL:
        return {"state": PAIR_ZERO}
    return {
        "state": PAIR_OUT_OF_RANGE,
        "stored_rows": st["stored_rows"],
        "stored_sum": _stored_sum(st["rows"]),
    }


def _exposure(
    row: Mapping[str, Any],
    kind: str,
    used: Sequence[dict[str, Any]],
    direct: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    terms, unknown, zero = [], [], []
    total = Decimal(0)
    for e in used:
        hit = _find(e["cons"]["rows"], row["match_key"])
        c = dec(hit["weight_pct"]) if hit is not None else None
        if hit is not None and c is None:
            # 편입은 확인됐으나 비중을 읽을 수 없음 — 합계에 0 으로 넣지 않고 미확인(검증자 STEP 4~5 r1 F10)
            unknown.append(
                {
                    "ticker": e["ticker"],
                    "name": e["name"],
                    "holding_weight": dstr(e["weight"]),
                    "range": WEIGHT_UNKNOWN,
                    "stored_rows": e["cons"]["stored_rows"],
                }
            )
        elif hit is not None:
            w = e["weight"]
            product = w * c / 100
            total += product
            terms.append(
                {
                    "ticker": e["ticker"],
                    "name": e["name"],
                    "holding_weight": dstr(w),
                    "constituent_weight": dstr(c),
                    "product": dstr(product),
                }
            )
        elif e["cons"]["range"] == RANGE_FULL:
            zero.append(e["ticker"])
        else:
            unknown.append(
                {
                    "ticker": e["ticker"],
                    "name": e["name"],
                    "holding_weight": dstr(e["weight"]),
                    "range": e["cons"]["range"],
                    "stored_rows": e["cons"]["stored_rows"],
                }
            )
    direct_terms = []
    for d in direct:
        if _is_direct_match(row, kind, d["ticker"]):
            total += d["weight"]
            direct_terms.append(
                {"ticker": d["ticker"], "name": d["name"], "weight": dstr(d["weight"])}
            )
    # 확인한 부분이 하나라도 있어야 수치(편입 비중을 읽은 ETF · 원천 전체라 없음이 확인된 ETF · 직접 보유) —
    # 계산에 들어간 보유가 없거나 전부 미확인이면 0.00% 가 아니라 '확인 불가'(검증자 STEP 4~5 r1 F10).
    covered = bool(terms or zero or direct)
    return {
        "terms": terms,
        "direct": direct_terms,
        "zero_confirmed": zero,
        "unknown": unknown,
        "unknown_weight": dstr(
            sum((Decimal(u["holding_weight"]) for u in unknown), Decimal(0))
        ),
        "raw": dstr(total) if covered else None,
        # 합계 뒤 한 번 반올림한 표시값(소수 둘째 자리 고정 · 확인된 0 은 0.00) · 확인한 부분이 없으면 None.
        "value": (
            format(total.quantize(R_STEP, rounding=ROUND_HALF_UP), "f")
            if covered
            else None
        ),
    }


def _reference(
    row: Mapping[str, Any], others: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    out = []
    for e in others:
        hit = _find(e["cons"]["rows"], row["match_key"])
        if hit is None:
            continue
        c = dec(hit["weight_pct"])  # 읽을 수 없으면 None(0 으로 채우지 않음 · F10)
        out.append(
            {
                "ticker": e["ticker"],
                "name": e["name"],
                "asof": e["cons"]["asof"],
                "holding_weight": dstr(e["weight"]),
                "constituent_weight": dstr(c),
                "product": dstr(e["weight"] * c / 100) if c is not None else None,
            }
        )
    return out


def _sum_of(entries: Iterable[dict[str, Any]]) -> str:
    return dstr(sum((e["weight"] for e in entries), Decimal(0)))


def _range_counts(entries: Iterable[dict[str, Any]]) -> dict[str, Any]:
    full = [
        e["cons"]["stored_rows"] for e in entries if e["cons"]["range"] == RANGE_FULL
    ]
    es = list(entries)
    return {
        "depth": sum(1 for e in es if e["cons"]["range"] == RANGE_DEPTH),
        "legacy": sum(1 for e in es if e["cons"]["range"] == RANGE_LEGACY),
        "unverified": sum(1 for e in es if e["cons"]["range"] == RANGE_UNVERIFIED),
        "full": len(full),
        "full_min": min(full) if full else None,
        "full_max": max(full) if full else None,
    }


def fingerprint(body: Mapping[str, Any]) -> str:
    text = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build(
    *,
    candidate: str,
    holding: Optional[str],
    condition: Mapping[str, Any],
    hw: Optional[Mapping[str, Any]],
    price_date: Optional[Mapping[str, Any]],
    names: Mapping[str, Optional[str]],
    etf_tickers: set[str],
    snaps: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """계산 본체(입력은 모두 인자 · 부작용 없음). `hw` = `holding_weights` 결과 · None = 보유 읽기 실패 ·
    `etf_tickers` 가 비면 ETF 목록 확인 불가."""
    cst = _etf_state(snaps.get(candidate))
    body: dict[str, Any] = {
        "status": STATUS_OK,
        "condition": dict(condition),
        "candidate": {
            "ticker": candidate,
            "name": names.get(candidate),
            "state": cst["state"],
            "asof": cst["asof"],
            "stored_rows": cst["stored_rows"],
            "held": False,
            "held_weight": None,
            "held_use": None,
        },
        "holding": None,
        "dates": {"candidate": None, "holding": None, "exposure": None},
        "basis": None,
        "scope": None,
        "stocks": [],
        "candidate_top_rows": 0,
        "candidate_non_stock_rows": 0,
    }
    if cst["state"] == STATE_CONFIRMED:
        body["dates"]["candidate"] = cst["asof"]
    if not etf_tickers:
        body["status"] = STATUS_NO_ETF_LIST
        return _seal(body)
    entries = _entries(hw, snaps)
    if hw is not None:
        body["basis"] = {
            "rows": hw["rows"],
            "priced_rows": hw["priced_rows"],
            "partial": hw["priced_rows"] < hw["rows"],
            "price_date": dict(price_date) if price_date else None,
        }
        body["dates"]["exposure"] = _assign_uses(entries)
    sel = _select(body, holding, entries, etf_tickers, names, snaps)
    cand_entry = next((e for e in entries if e["ticker"] == candidate), None)
    if cand_entry is not None:
        body["candidate"].update(
            held=True,
            held_weight=dstr(cand_entry["weight"]),
            held_use=cand_entry["use"],
        )
    if hw is not None:
        body["scope"] = _scope(entries)
    if hw is None:
        body["status"] = STATUS_HOLDINGS_UNREADABLE
    elif not entries:
        body["status"] = STATUS_NO_HOLDINGS
        return _seal(body)
    elif not hw["denominator"]:
        body["status"] = STATUS_NO_WEIGHT_BASIS
    elif cst["state"] != STATE_CONFIRMED:
        body["status"] = STATUS_NO_CANDIDATE_DATA
    if cst["state"] != STATE_CONFIRMED:
        return _seal(body)
    # 보유를 못 읽거나 분모가 없어도 짝 칸(편입 비중)은 보인다 — 노출만 계산하지 않음(None · frontend#2).
    exposed = body["status"] == STATUS_OK
    used = [e for e in entries if e["use"] == USE_SUM]
    others = [e for e in entries if e["use"] == USE_OTHER_DATE]
    direct = [e for e in entries if e["use"] == USE_DIRECT]
    top = cst["rows"][:TOP_CONSTITUENTS]
    body["candidate_top_rows"] = len(top)
    for row in top:
        kind = row_kind(row, etf_tickers)
        if row["match_key"] is None or kind not in STOCK_KINDS:
            body["candidate_non_stock_rows"] += 1
            continue
        body["stocks"].append(
            {
                "key": row["match_key"],
                "name": row["name"] or row["match_key"],
                "rank": row["rank"],
                "candidate_weight": dstr(dec(row["weight_pct"])),
                "pair": _pair(sel, row, kind),
                "exposure": _exposure(row, kind, used, direct) if exposed else None,
                "reference": _reference(row, others) if exposed else [],
            }
        )
    return _seal(body)


def _entries(
    hw: Optional[Mapping[str, Any]], snaps: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    if hw is None:
        return []
    return [
        {**it, "cons": _etf_state(snaps.get(it["ticker"])) if it["etf"] else None}
        for it in hw["items"]
    ]


def _assign_uses(entries: list[dict[str, Any]]) -> Optional[str]:
    """보유마다 쓰임(합산 · 참고 · 빠짐 사유)을 정하고 노출 합계일을 돌려준다.

    노출 합계일 = 합산할 수 있는(시세 있는) 보유 ETF 중 원천일이 확인된 가장 최근 구성일(검토 지적 backend#1 — 시세 없는
    ETF 의 날짜가 합계일이 되면 합산할 ETF 가 하나도 없게 된다).
    """
    dates = [
        e["cons"]["asof"]
        for e in entries
        if e["etf"]
        and e["weight"] is not None
        and e["cons"]["state"] == STATE_CONFIRMED
    ]
    exposure_date = max(dates) if dates else None
    for e in entries:
        if e["weight"] is None:
            e["use"] = USE_NO_WEIGHT
        elif not e["etf"]:
            e["use"] = USE_DIRECT
        elif e["cons"]["state"] == STATE_UNCONFIRMED:
            e["use"] = USE_UNCONFIRMED
        elif e["cons"]["state"] == STATE_NO_DATA:
            e["use"] = USE_NO_DATA
        elif e["cons"]["asof"] == exposure_date:
            e["use"] = USE_SUM
        else:
            e["use"] = USE_OTHER_DATE
    return exposure_date


def _select(
    body: dict[str, Any],
    holding: Optional[str],
    entries: list[dict[str, Any]],
    etf_tickers: set[str],
    names: Mapping[str, Optional[str]],
    snaps: Mapping[str, Mapping[str, Any]],
) -> Optional[dict[str, Any]]:
    """고른 보유 칸을 채우고 짝 비교에 쓸 값을 돌려준다(없으면 None)."""
    if not holding:
        return None
    sel_entry = next((e for e in entries if e["ticker"] == holding), None)
    sel_etf = holding in etf_tickers
    sel_cons = (
        sel_entry["cons"]
        if sel_entry is not None and sel_entry["cons"] is not None
        else (_etf_state(snaps.get(holding)) if sel_etf else None)
    )
    body["holding"] = {
        "ticker": holding,
        "name": (sel_entry or {}).get("name") or names.get(holding),
        "kind": "etf" if sel_etf else "stock",
        "held": sel_entry is not None,
        "weight": dstr(sel_entry["weight"]) if sel_entry else None,
        "state": sel_cons["state"] if sel_cons else None,
        "asof": sel_cons["asof"] if sel_cons else None,
        "stored_rows": sel_cons["stored_rows"] if sel_cons else None,
        "range": sel_cons["range"] if sel_cons else None,
    }
    if sel_cons and sel_cons["state"] == STATE_CONFIRMED:
        body["dates"]["holding"] = sel_cons["asof"]
    return {"ticker": holding, "etf": sel_etf, "cons": sel_cons}


def _scope(entries: list[dict[str, Any]]) -> dict[str, Any]:
    def pick(use: str) -> list[dict[str, Any]]:
        return [e for e in entries if e["use"] == use]

    used, others = pick(USE_SUM), pick(USE_OTHER_DATE)
    return {
        "holdings": len(entries),
        "included": {"count": len(used), "weight": _sum_of(used)},
        "direct": {"count": len(pick(USE_DIRECT)), "weight": _sum_of(pick(USE_DIRECT))},
        "other_date": {
            "count": len(others),
            "weight": _sum_of(others),
            "dates": sorted({e["cons"]["asof"] for e in others}, reverse=True),
        },
        "unconfirmed": {
            "count": len(pick(USE_UNCONFIRMED)),
            "weight": _sum_of(pick(USE_UNCONFIRMED)),
        },
        "no_data": {
            "count": len(pick(USE_NO_DATA)),
            "weight": _sum_of(pick(USE_NO_DATA)),
        },
        "no_weight": {"count": len(pick(USE_NO_WEIGHT))},
        "ranges": _range_counts(used),
        "etfs": [
            {
                "ticker": e["ticker"],
                "name": e["name"],
                "weight": dstr(e["weight"]),
                "use": e["use"],
                "state": e["cons"]["state"],
                "asof": e["cons"]["asof"],
                "stored_rows": e["cons"]["stored_rows"],
                "range": e["cons"]["range"],
            }
            for e in sorted(
                (x for x in entries if x["etf"]),
                key=lambda x: (x["weight"] is None, -(x["weight"] or 0), x["ticker"]),
            )
        ],
    }


def _seal(body: dict[str, Any]) -> dict[str, Any]:
    return {**body, "fingerprint": fingerprint(body)}
