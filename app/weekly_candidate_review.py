"""POC6-32 V2 — 「주간 ETF 점검」 ③ 「선택한 후보 검토」 칸 · ② 행 자료 부족 · 저장 묶음(PLAN V2 §3-1 · §4-3 · §9).

후보 하나를 고르면 보유 한 종목을 고르는 단계 없이 후보 자체의 근거를 줄마다 낸다(판정 V2 Q11 (d) · Q12 (c)).
- R1 어떤 상품인가: 공식 기준정보(`etf_official_info` · CSV 글자 그대로 · 파일 날짜) + 구성 요약(원천일이 확인된 최신 구성 ·
  없으면 저장 최신 구성 + '원천 기준일 미확인' · 보유와 무관하게 읽음 · 상태 넷 = 미수집 · 원천 기준일 미확인 ·
  상위 N행만 확인 · 전체 확인(I-9) · 주식 상위 3개와 '상위 3개 합'(주식만 · I-10)).
- R2 실제로 올랐나: 1 · 3개월 값 · 실제 시작 → 끝 · 방향(소수 둘째 자리 0.00 = 변화 없음 · I-7) · '같은 기간 국내시장
  (KODEX 200) 대비' = 기간이 공통 기간과 같고 두 쪽 끝일 가격 상태가 확인돼 같을 때만(둘 다 장중 = 잠정 비교 · I-8) ·
  기간 다름 = 값 + 실제 기간 + '기간 다름 · 국내시장 대비 안 함'(Q3 (a)).
- R3 더 확인할 것: 빈 자료 · 기준일이 다른 자료(가격 끝일 상태 · 구성 기준일 · 공식 기준정보 파일 날짜) · 보유 겹침 확인 범위.
- R4 내 보유에 무엇이 겹치나 = V1 겹침 그대로(`weekly_review.overlap_of`) + 후보끼리 중복률과 다른 값이라는 한 줄.
- ② 행 자료 부족(I-11) = 가격(1 · 3개월 값 없음 · 기간 다름 · 끝일 상태 모름) · 상품(공식 기준정보 없음) · 행마다 새 읽기 없음.
- 저장 묶음(I-13) = `data_quality_snapshot` · `constituent_snapshot`(기존 자유 칸 · 표 변경 없음).
시스템이 정하는 것은 가격 방향과 비교 가능 범위다 — 쓸 만한지는 사용자가 기록한다(판단 낱말 없음). 금액 없음.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from types import SimpleNamespace
from typing import Any, Iterable, Mapping, Optional, Sequence

from app import etf_official_info as eoi
from app.constituent_row_kind import KIND_LABEL, STOCK_KINDS, row_kind
from app.constituents_cross_family import confirmed_rows
from app.etf_constituents_analysis import compute_concentration
from app.pc_etf_compare_groups import constituent_key
from app.pc_etf_compare_periods import (
    CRIT_OK,
    CRIT_PERIOD_DIFFERS,
    STATE_AFTER_CLOSE,
    STATE_INTRADAY,
    STATE_UNKNOWN,
)
from app.supply_fx_oil_calc import md

SIDE = "top"
TOP_STOCKS = 3

C_NOT_COLLECTED = "not_collected"
C_SOURCE_UNCONFIRMED = "source_unconfirmed"
C_TOP_ROWS = "top_rows"
C_FULL = "full"
C_ERROR = "error"  # 읽기 실패(자료 상태가 아님 · '미수집'으로 바꾸지 않음)

PERIODS = (("one_month", "1m", "1개월"), ("three_month", "3m", "3개월"))
PRICE_LABEL = {
    STATE_INTRADAY: "장중 저장값 · 잠정",
    STATE_AFTER_CLOSE: "마감 뒤 저장",
    STATE_UNKNOWN: "마감값 확인 필요",
}
DIR_LABEL = {"up": "올랐음", "down": "내렸음", "flat": "변화 없음"}
OVERLAP_NOTE = (
    "내 보유 평가액 기준 노출 — 「ETF 구성종목」 목록의 후보끼리 중복률과 다른 값"
)
DETAIL_HINT = "이동평균 · 거래량 · 흔들림 등 상세 근거는 [판단 근거 보기]"
_C2 = Decimal("0.01")


# ── R1 구성 요약(보유와 무관하게 읽음) ─────────────────────────────────────────
def _plain_rows(crs: Iterable[Any]) -> list[dict[str, Any]]:
    """저장 행(`ConstituentRow`) → 확인 행과 같은 칸의 사전."""
    return [
        {
            "rank": r.rank,
            "ticker": r.constituent_ticker or None,
            "name": r.constituent_name or None,
            "weight_pct": r.weight_pct,
            "key": r.constituent_key or None,
            "isin": r.constituent_isin or None,
            "reuters": r.constituent_reuters_code or None,
            "market_type": r.market_type,
        }
        for r in crs
    ]


def constituents_of(
    snap: Optional[Mapping[str, Any]],
    latest: Optional[tuple[str, Sequence[Any], bool]],
    etf_tickers: Optional[set[str]],
) -> dict[str, Any]:
    """구성 요약(순수) — 한 읽기(`weekly_candidate_reads`)의 사본에서: 원천일이 확인된 최신 구성(`snap['confirmed']` ·
    `read_snapshots` 모양) · 없으면 저장 최신 구성(`latest` = (날짜, 저장 행, 원천일 확인) · `read_analysis_rows` 모양).
    저장 최신 구성의 확인이 잡히면(원천 전체 표시는 이 사본으로 모름) '상위 N행만 확인'(보수적)."""
    conf = (snap or {}).get("confirmed")
    if conf:
        state = C_FULL if conf.get("complete") else C_TOP_ROWS
        return detail_of(state, conf["asof"], confirmed_rows(conf), etf_tickers)
    if latest is None:
        return detail_of(C_NOT_COLLECTED, None, [], etf_tickers)
    asof, crs, ok = latest
    state = C_TOP_ROWS if ok else C_SOURCE_UNCONFIRMED
    return detail_of(state, asof, _plain_rows(crs), etf_tickers)


def _sum2(ws: Sequence[Optional[float]]) -> Optional[float]:
    """정확한 소수 합(소수 둘째 자리) — 비중을 읽을 수 없는 행이 있으면 None(0 으로 채우지 않음)."""
    if not ws or any(w is None for w in ws):
        return None
    total = sum((Decimal(repr(float(w))) for w in ws if w is not None), Decimal(0))
    return float(total.quantize(_C2, rounding=ROUND_HALF_UP))


def _state_label(state: str, n: int) -> str:
    return {
        C_NOT_COLLECTED: "미수집",
        C_SOURCE_UNCONFIRMED: "원천 기준일 미확인",
        C_TOP_ROWS: f"상위 {n}행만 확인",
        C_FULL: "전체 확인",
        C_ERROR: "구성 자료를 읽지 못함",
    }[state]


def _cons_line(d: Mapping[str, Any]) -> str:
    st, n = d["state"], d["stored_rows"]
    if st == C_NOT_COLLECTED:
        return "구성 자료 없음(미수집) — [구성종목 보기]에서 수집"
    if st == C_ERROR:
        return (
            "구성 자료를 읽지 못함 — [다시 읽기]로 다시 시도(구성 없음이라는 뜻 아님)"
        )
    if d["stocks_known"]:
        parts = [f"주식 {d['stock_rows']}"] + [
            f"{o['label']} {o['count']}" for o in d["other_rows"]
        ]
        rows = f"저장 {n}행({' · '.join(parts)})"
    else:
        rows = f"저장 {n}행(ETF 목록을 읽지 못해 주식 행을 가를 수 없음)"
    tail = {
        C_FULL: f"(원천 항목 {n}개를 모두 받음)",
        C_TOP_ROWS: "(그 밖 구성은 미확인)",
        C_SOURCE_UNCONFIRMED: "(이 저장 자료가 원천 기준일과 맞는지 확인 기록 없음)",
    }[st]
    return f"구성 기준일 {md(d['asof'])} · {rows} · {d['state_label']}{tail}"


def detail_of(
    state: str,
    asof: Optional[str],
    rows: Sequence[Mapping[str, Any]],
    etf_tickers: Optional[set[str]],
) -> dict[str, Any]:
    """구성 한 벌 → 요약 + 저장 행 전체 + 집중(Top 1 · 3 · 5 · 10 · 기존 정의 = 주식 아닌 행도 더함)."""
    known = bool(etf_tickers)
    out_rows = []
    for r in rows:
        kind = row_kind(r, set(etf_tickers or ())) if known else None
        stock = (
            None
            if not known
            else (kind in STOCK_KINDS and constituent_key(r) is not None)
        )
        out_rows.append(
            {
                "rank": r["rank"],
                "name": r.get("name") or r.get("ticker") or r.get("key"),
                "weight_pct": r.get("weight_pct"),
                "is_stock": stock,
                "kind_label": KIND_LABEL.get(kind) if kind else None,
            }
        )
    stocks = [r for r in out_rows if r["is_stock"]]
    top = stocks[:TOP_STOCKS]
    other = Counter(r["kind_label"] for r in out_rows if r["is_stock"] is False)
    n = len(out_rows)
    d: dict[str, Any] = {
        "state": state,
        "state_label": _state_label(state, n),
        "asof": asof,
        "stored_rows": n,
        "stocks_known": known,
        "stock_rows": len(stocks) if known else None,
        "other_rows": [{"label": k, "count": c} for k, c in sorted(other.items())],
        "top_n": n if state in (C_TOP_ROWS, C_FULL) else None,
        "top_stocks": [{"name": r["name"], "weight_pct": r["weight_pct"]} for r in top],
        "top3_sum_pct": _sum2([r["weight_pct"] for r in top]),
        "rows": out_rows,
        "concentration": compute_concentration(
            [SimpleNamespace(weight_pct=r["weight_pct"]) for r in out_rows]
        ),
    }
    d["line"] = _cons_line(d)
    return d


def error_detail() -> dict[str, Any]:
    return detail_of(C_ERROR, None, [], None)


def summary_of(detail: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    """주간 응답에 싣는 구성 요약(저장 행 전체 · 집중은 상세 경로에서)."""
    d = detail if detail is not None else error_detail()
    return {k: v for k, v in d.items() if k not in ("rows", "concentration")}


# ── ② 행 자료 부족(I-11) ─────────────────────────────────────────────────────
def lack_of(row: Mapping[str, Any], official_ok: bool = True) -> list[str]:
    """가격 · 상품 자료 부족 사유(충분하면 빈 목록) — 행에 이미 있는 칸만(새 읽기 없음)."""
    out = []
    crit = row.get("criteria") or {}
    for key, _, label in PERIODS:
        c = crit.get(key) or {}
        if c.get("status") == CRIT_PERIOD_DIFFERS:
            out.append(f"{label} 기간 다름")
        elif c.get("status") != CRIT_OK or c.get("value") is None:
            out.append(f"{label} 수익률 없음")
    state = (row.get("end_price") or {}).get("state") or STATE_UNKNOWN
    if state == STATE_UNKNOWN:
        out.append("가격 끝일 상태 모름")
    if not (row.get("classification") or {}).get("index_name"):
        out.append(
            "공식 기준정보 없음" if official_ok else "공식 기준정보 파일 읽기 실패"
        )
    return out


# ── R2 실제로 올랐나 ─────────────────────────────────────────────────────────
def _r2(v: Optional[float]) -> Optional[Decimal]:
    if v is None:
        return None
    return Decimal(repr(float(v))).quantize(_C2, rounding=ROUND_HALF_UP)


def direction_of(v: Optional[float]) -> Optional[str]:
    d = _r2(v)
    if d is None:
        return None
    return "up" if d > 0 else ("down" if d < 0 else "flat")


def market_phrase(
    direction: str, diff: float, kodex: Optional[float], provisional: bool
) -> str:
    """국내시장 대비 문구(I-7 · 소수 둘째 자리 기준). 내렸고 차이가 음수인데 국내시장이 내리지 않았으면 '더 내림'이 아니라
    '낮음'(국내시장은 내리지 않음)."""
    dd, k = _r2(diff), _r2(kodex)
    if dd is None:
        return f"{DIR_LABEL[direction]} · 국내시장 대비 확인 불가"
    gap = f"{abs(dd):.2f}%p"
    if dd == 0:
        s = f"{DIR_LABEL[direction]} · 국내시장과 같음"
    elif direction == "up":
        s = (
            f"올랐고 국내시장보다 {gap} 높음"
            if dd > 0
            else f"올랐지만 국내시장보다 {gap} 낮음"
        )
    elif direction == "down":
        if dd > 0:
            s = f"내렸지만 국내시장보다 {gap} 덜 내림"
        elif k is not None and k < 0:
            s = f"내렸고 국내시장보다 {gap} 더 내림"
        else:
            s = f"내렸고 국내시장보다 {gap} 낮음"
    else:
        s = f"변화 없음 · 국내시장보다 {gap} {'높음' if dd > 0 else '낮음'}"
    return s + (" · 잠정 비교" if provisional else "")


def _no(reason: str) -> dict[str, Any]:
    return {
        "value_pct": None,
        "diff_pp": None,
        "comparable": False,
        "provisional": False,
        "reason": reason,
    }


def _market(
    key: str,
    crit: Mapping[str, Any],
    row: Mapping[str, Any],
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    """같은 기간 국내시장(KODEX 200) 대비 — 판정 순서: 기간 → 값 → 국내시장 값 → 끝일 → 가격 상태."""
    if crit.get("status") == CRIT_PERIOD_DIFFERS:
        return _no("기간 다름")
    if crit.get("status") != CRIT_OK or crit.get("value") is None:
        return _no("수익률 자료 없음")
    if key == "one_month":
        same = (row.get("criteria") or {}).get("same_kodex_1m") or {}
        if same.get("status") != CRIT_OK or same.get("kodex200_return_pct") is None:
            return _no("국내시장(KODEX 200) 같은 날짜 가격 없음")
        kodex, diff = same["kodex200_return_pct"], same.get("value")
    else:
        w3 = (summary.get("criteria_periods") or {}).get("three_month") or {}
        if (crit.get("start"), crit.get("end")) != (w3.get("start"), w3.get("end")):
            return _no("기간 다름")
        kodex = (summary.get("kodex200") or {}).get("three_month_return_pct")
        if kodex is None:
            return _no("국내시장(KODEX 200) 같은 날짜 가격 없음")
        diff = round(crit["value"] - kodex, 4)
    ep = row.get("end_price") or {}
    kp = (summary.get("regime") or {}).get("price") or {}
    if not ep.get("date") or not kp.get("date"):
        return _no("가격 끝일 확인 불가")
    if ep["date"] != crit.get("end") or kp["date"] != crit.get("end"):
        return _no("가격 끝일이 기간 끝과 다름")
    es, ks = ep.get("state") or STATE_UNKNOWN, kp.get("state") or STATE_UNKNOWN
    if STATE_UNKNOWN in (es, ks):
        return _no("가격 끝일 저장 상태 확인 필요")
    if es != ks:
        return _no(
            f"가격 상태 다름(이 ETF {PRICE_LABEL[es]} · KODEX 200 {PRICE_LABEL[ks]})"
        )
    return {
        "value_pct": kodex,
        "diff_pp": diff,
        "comparable": True,
        "provisional": es == STATE_INTRADAY,
        "reason": None,
    }


def returns_of(
    row: Mapping[str, Any], summary: Mapping[str, Any]
) -> list[dict[str, Any]]:
    out = []
    cp = summary.get("criteria_periods") or {}
    for key, code, label in PERIODS:
        c = (row.get("criteria") or {}).get(key) or {}
        status = c.get("status")
        value = c.get("value") if status in (CRIT_OK, CRIT_PERIOD_DIFFERS) else None
        direction = direction_of(value)
        m = _market(key, c, row, summary)
        if direction is None:
            phrase = "수익률 확인 불가"
        elif status == CRIT_PERIOD_DIFFERS:
            phrase = f"{DIR_LABEL[direction]} · 기간 다름 · 국내시장 대비 안 함"
        elif m["comparable"]:
            phrase = market_phrase(
                direction, m["diff_pp"], m["value_pct"], m["provisional"]
            )
        else:
            phrase = f"{DIR_LABEL[direction]} · 국내시장 대비 안 함({m['reason']})"
        out.append(
            {
                "period": code,
                "label": label,
                "value_pct": value,
                "start": c.get("start"),
                "end": c.get("end"),
                "status": (
                    status if status in (CRIT_OK, CRIT_PERIOD_DIFFERS) else "missing"
                ),
                "direction": direction,
                "common": cp.get(key),
                "market": m,
                "phrase": phrase,
            }
        )
    return out


def price_note(row: Mapping[str, Any], summary: Mapping[str, Any]) -> str:
    ep = row.get("end_price") or {}
    kp = (summary.get("regime") or {}).get("price") or {}

    def one(p: Mapping[str, Any]) -> str:
        if not p.get("date"):
            return "끝일 확인 불가"
        return f"{md(p['date'])} {PRICE_LABEL[p.get('state') or STATE_UNKNOWN]}"

    if (ep.get("date"), ep.get("state")) == (kp.get("date"), kp.get("state")):
        return f"가격 = {one(ep)}(이 ETF · KODEX 200 같음)"
    return f"가격 = 이 ETF {one(ep)} · KODEX 200 {one(kp)}"


# ── R3 더 확인할 것 ──────────────────────────────────────────────────────────
def _days(a: Optional[str], b: Optional[str]) -> Optional[int]:
    try:
        return (date.fromisoformat(str(b)[:10]) - date.fromisoformat(str(a)[:10])).days
    except (TypeError, ValueError):
        return None


def checks_of(
    *,
    row: Mapping[str, Any],
    end_date: str,
    returns: Sequence[Mapping[str, Any]],
    product: Mapping[str, Any],
    constituents: Mapping[str, Any],
    overlap: Optional[Mapping[str, Any]],
    generated_at: str,
) -> list[str]:
    out = []
    for r in returns:
        if r["status"] == CRIT_PERIOD_DIFFERS:
            cm = r.get("common") or {}
            common = (
                f" · 공통 {md(cm['start'])} → {md(cm['end'])}"
                if cm.get("start") and cm.get("end")
                else ""
            )
            out.append(
                f"{r['label']} 기간 다름(실제 {md(r['start'])} → {md(r['end'])}{common}) — 국내시장 대비 안 함"
            )
        elif r["status"] != CRIT_OK or r["value_pct"] is None:
            out.append(f"{r['label']} 수익률 자료 없음 — 확인 불가")
        elif not r["market"]["comparable"]:
            out.append(f"{r['label']} 국내시장 대비 안 함 — {r['market']['reason']}")
        elif r["market"]["provisional"]:
            out.append(f"{r['label']} 국내시장 대비는 잠정 — 두 가격 모두 장중 저장값")
    ep = row.get("end_price") or {}
    st = ep.get("state") or STATE_UNKNOWN
    if not ep.get("date"):
        out.append("가격 끝일 확인 불가")
    elif st != STATE_AFTER_CLOSE:
        out.append(f"가격 끝일 {md(ep['date'])} = {PRICE_LABEL[st]}")
    cs = constituents["state"]
    if cs == C_NOT_COLLECTED:
        out.append(
            "구성 자료 없음(미수집) — [구성종목 보기]에서 수집(겹침 없음이라는 뜻 아님)"
        )
    elif cs == C_ERROR:
        out.append("구성 자료를 읽지 못함 — [다시 읽기]로 다시 시도")
    elif cs == C_SOURCE_UNCONFIRMED:
        out.append(
            f"구성 원천 기준일 미확인({md(constituents['asof'])} 저장 자료) — [구성종목 보기]에서 다시 수집"
        )
    elif cs == C_TOP_ROWS:
        out.append(
            f"구성 상위 {constituents['stored_rows']}행만 확인 — 그 밖 구성은 미확인"
        )
    if constituents.get("asof") and constituents["asof"] != end_date:
        out.append(
            f"구성 기준일 {md(constituents['asof'])} · 가격 끝일 {md(end_date)} — 기준일이 다름"
        )
    csv = product.get("csv") or {}
    if not product.get("found"):
        why = product.get("missing_reason") or eoi.WHY_NOT_IN_CSV
        out.append(f"{why} — 공식 기초지수 · 상품 구조 확인 불가")
    if csv.get("ok") and csv.get("asof"):
        age = _days(csv["asof"], generated_at)
        ago = f"{age}일 전 · " if age is not None and age >= 0 else ""
        out.append(
            f"공식 기준정보 파일 {csv['asof']}({ago}그 뒤 바뀐 상품 정보는 확인 불가)"
        )
    if overlap and overlap.get("state") != "no_data":
        out += list(overlap.get("warn_lines") or [])
    out.append(DETAIL_HINT)
    return out


def review_of(
    *,
    row: Mapping[str, Any],
    summary: Mapping[str, Any],
    product: Mapping[str, Any],
    constituents: Mapping[str, Any],
    overlap: Optional[Mapping[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    """③ 「선택한 후보 검토」 한 묶음(입력은 모두 인자 · 순수)."""
    returns = returns_of(row, summary)
    return {
        "ticker": row["ticker"],
        "name": row["name"],
        "rank": row["rank"],
        "side": SIDE,
        "product": dict(product),
        "constituents": dict(constituents),
        "returns": returns,
        "price_note": price_note(row, summary),
        "checks": checks_of(
            row=row,
            end_date=summary["end_date"],
            returns=returns,
            product=product,
            constituents=constituents,
            overlap=overlap,
            generated_at=generated_at,
        ),
        "overlap": overlap,
        "overlap_note": OVERLAP_NOTE,
    }


def product_of(
    ticker: str, official_info: Optional[Mapping[str, Any]]
) -> dict[str, Any]:
    """조회 결과에서 한 종목 + 파일 정보. 조회 결과가 없으면 '공식 기준정보 파일을 읽지 못함'(빈 값을 '없음'으로 쓰지 않음)."""
    info = official_info or eoi.build_lookup(
        {}, eoi.csv_meta(False, None, None), [], None
    )
    item = (info.get("items") or {}).get(ticker)
    if item is None:
        item = eoi.build_lookup({}, info.get("csv") or {}, [ticker], None)["items"][
            ticker
        ]
    return {**item, "csv": dict(info.get("csv") or {})}


# ── 저장 묶음(I-13 · I-32 · 기존 자유 칸) ──────────────────────────────────────
RETURN_KEYS = ("period", "value_pct", "start", "end", "status", "direction", "phrase")
MARKET_KEYS = ("value_pct", "diff_pp", "comparable", "provisional", "reason")


def _end_price(p: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "date": (p or {}).get("date"),
        "state": (p or {}).get("state") or STATE_UNKNOWN,
    }


def saved_returns(review: Mapping[str, Any]) -> list[dict[str, Any]]:
    """③ R2 결과 그대로(기간 · 값 · 방향 · 국내시장 대비 · 문구) — '당시 검토'가 화면과 같은 대비를 보이게(I-32)."""
    return [
        {
            **{k: r.get(k) for k in RETURN_KEYS},
            "market": {k: (r.get("market") or {}).get(k) for k in MARKET_KEYS},
        }
        for r in review.get("returns") or []
    ]


def data_quality_snapshot(
    *,
    summary: Mapping[str, Any],
    condition: Mapping[str, Any],
    selected: Optional[Mapping[str, Any]],
    flows: Sequence[Mapping[str, Any]],
    review: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """검토 조건 · 고른 ETF(+ R2 결과) · 공통 기간 · 기간 다름 값 · 자료 부족 · 30행과 KODEX 200 끝 가격 상태
    (I-13 · I-32 — '당시 검토'가 저장된 상태로 I-8 가격 상태 규칙을 적용)."""
    cp = summary.get("criteria_periods") or {}
    differs = []
    for r in summary["top"]:
        for key, code, _ in PERIODS:
            c = (r.get("criteria") or {}).get(key) or {}
            if c.get("status") == CRIT_PERIOD_DIFFERS:
                differs.append(
                    {
                        "ticker": r["ticker"],
                        "rank": r["rank"],
                        "period": code,
                        "value_pct": c.get("value"),
                        "start": c.get("start"),
                        "end": c.get("end"),
                    }
                )
    lack = [
        {"ticker": m["ticker"], "rank": m["rank"], "lack": list(m["lack"])}
        for f in flows
        for m in f["members"]
        if m.get("lack")
    ]
    sel = None
    if selected:
        sel = {**{k: selected[k] for k in ("ticker", "name", "rank")}, "side": SIDE}
        if review is not None:
            sel["returns"] = saved_returns(review)
    return {
        "condition": dict(condition),
        "selected": sel,
        "common_periods": {
            "one_month": cp.get("one_month"),
            "three_month": cp.get("three_month"),
        },
        "period_differs_values": differs,
        "lack": sorted(lack, key=lambda x: x["rank"]),
        "price_states": {
            "rows": {
                r["ticker"]: _end_price(r.get("end_price")) for r in summary["top"]
            },
            "kodex200": _end_price((summary.get("regime") or {}).get("price")),
        },
        "evidence_list": [],
    }


def constituent_snapshot(review: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    if review is None:
        return {}
    return {
        "selected": {
            "ticker": review["ticker"],
            "name": review["name"],
            "rank": review["rank"],
            "side": review["side"],
        },
        "product": review["product"],
        "constituents": review["constituents"],
    }
