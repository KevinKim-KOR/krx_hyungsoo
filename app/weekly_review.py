"""POC6-32 — 「주간 ETF 점검」 조립(PLAN V1 · V2 확정 2026-11-17 · 읽기 전용).

③ 고른 후보 묶음(R1 ~ R4) · 행 자료 부족 사유 · 저장 묶음은 `weekly_candidate_review`.

입력(목록 요약 · 공통 시장 근거 · 노출 계산 · 마지막 기록)은 모두 인자다 — 외부 호출 · 쓰기 · 새 판정 규칙 없음.
- ① 시장 = 공통 시장 근거(`market_evidence` · 일일 복사와 같은 칸) — 화면이 그 칸을 그린다(V1 목록 요약 판정 줄 ·
  시장 흐름 두 번째 읽기 없음 · PLAN V2 S3).
- 조건 = 1개월 · 상위 30 · 인버스 · 레버리지 · 합성 · 선물 제외 · 다른 화면 설정과 따로(판정 Q1).
- 흐름 묶음 = 같은 기초지수 계열(`index_family.family_of` · 공식 기초지수명이 같거나 계열 사전으로 확인된 것) ·
  지수명 없음 = 단독 · 대표 = 묶음에서 가장 높은 순위 · 행 순서 = 대표의 원래 순위 · 첫 화면 3행(판정 Q2 · Q3).
  '같은 공식 기초지수' 글자는 구성원의 공식 기초지수명이 모두 같을 때만 · 다르면 '같은 지수 계열 · 공식 기초지수명이
  다른 상품 포함'(`index_names_differ` · 복사 글 · 화면이 상품마다 공식 지수명을 보임 · PLAN I-6 · I-29).
  지수가 다른 상품은 자동으로 묶지 않는다(겹침은 「ETF 구성종목」).
- 보유 겹침 = 기존 노출 계산(`constituents_pair_exposure`) 결과를 '확인 범위 먼저' 글로 옮긴다(판정 Q4 ·
  계산 본체 · 지문 변경 없음 · 범위별 비중은 응답의 넷째 자리 비중을 정확한 소수 덧셈).
- 화면 · 복사 · 넘기기가 이 응답 하나를 같이 쓴다(판정 §3-1 · 같은 검토 건).
- 화면 글자는 '후보' 대신 'ETF'(「오늘의 투자 점검」 AC-7 · POC6-16 판정 선례) · 메뉴 이름 「후보리스트」만 그대로.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Mapping, Optional, Sequence

from app import constituents_pair_exposure as px
from app import weekly_candidate_review as wcr
from app.index_family import family_of
from app.supply_fx_oil_calc import md

SOURCE_SCREEN = "today_weekly_review"
BASIS = "one_month"
SIDE = "top"
FILTERS = {
    "exclude_inverse": True,
    "exclude_leveraged": True,
    "exclude_synthetic": True,
    "exclude_futures": True,
}
FIRST_ROWS = 3
FILTERS_TEXT = "인버스 · 레버리지 · 합성 · 선물 제외"
NOT_ZERO = "'겹침 없음'이 아닙니다"
_RANGE_ROWS = {px.RANGE_DEPTH: "상위 30행", px.RANGE_LEGACY: "상위 10행"}


def _ok(c: Mapping[str, Any]) -> Optional[float]:
    return c.get("value") if c.get("status") == "ok" else None


def price_line(ps: Mapping[str, Any]) -> str:
    """목록 끝날 가격 상태(화면 `priceStateLine` 과 같은 뜻 · 저장 시각 범위는 뺌)."""
    head = f"{md(ps['end_date'])} 가격 = "
    unknown = (
        f" · 마감값 확인 필요 {ps['unknown_count']}개"
        if ps.get("unknown_count")
        else ""
    )
    if ps.get("intraday_count"):
        return f"{head}장중 저장값 포함 · 잠정(장중 {ps['intraday_count']}개{unknown})"
    if ps.get("after_close_count"):
        return f"{head}마감 뒤 저장{unknown}"
    return f"{head}PC 저장 가격 · 마감값 확인 필요"


def condition_of(summary: Mapping[str, Any]) -> dict[str, Any]:
    per = summary["period"]
    n = len(summary["top"])
    line = (
        f"1개월 상위 {n}개(선정 순서) · {md(per['start'])} → {md(per['end'])} · "
        f"{FILTERS_TEXT} · {price_line(summary['price_state'])}"
    )
    return {
        "basis": BASIS,
        "side": SIDE,
        "n": n,
        "filters": dict(FILTERS),
        "start": per["start"],
        "end": per["end"],
        "line": line,
    }


# ── ② 먼저 볼 ETF 흐름 ────────────────────────────────────────────────────────
def _kept(c: Mapping[str, Any]) -> Optional[float]:
    """값 = 비교 가능(ok) · 기간 다름(값 유지 · V2 W5 · Q3 (a)). 값 없음만 None."""
    return c.get("value") if c.get("status") in ("ok", "period_differs") else None


def _period(c: Mapping[str, Any]) -> dict[str, Any]:
    st = c.get("status")
    return {
        "status": st if st in ("ok", "period_differs") else "missing",
        "start": c.get("start"),
        "end": c.get("end"),
    }


def _member(r: Mapping[str, Any], official_ok: bool = True) -> dict[str, Any]:
    c = r["classification"]
    crit = r["criteria"]
    ep = r.get("end_price") or {}
    return {
        "rank": r["rank"],
        "ticker": r["ticker"],
        "name": r["name"],
        "held": bool(r.get("held")),
        "index_name": c.get("index_name"),
        "one_month": _kept(crit["one_month"]),
        "three_month": _kept(crit["three_month"]),
        # 실제 기간 · 상태(기간 다름이면 값 + 실제 기간 · '확인 불가'로 쓰지 않음 · V2 W5)
        "periods": {
            "one_month": _period(crit["one_month"]),
            "three_month": _period(crit["three_month"]),
        },
        "end_price": {"date": ep.get("date"), "state": ep.get("state") or "unknown"},
        "lack": wcr.lack_of(r, official_ok),
    }


def flows_of(
    top: Sequence[Mapping[str, Any]], official_ok: bool = True
) -> list[dict[str, Any]]:
    """상위 목록 → 흐름 행(같은 공식 기초지수 = 한 묶음 · 대표 순위 순 · 판정 Q2 · Q3).

    행 · 묶음 안 ETF 마다 자료 부족 사유(`lack` · 충분하면 빈 목록 · V2 I-11) — 묶음 행 = 구성원 사유를 겹치지 않게 모음.
    """
    buckets: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for r in sorted(top, key=lambda x: x["rank"]):
        m = _member(r, official_ok)
        fam = family_of(m["index_name"])
        key = f"idx:{fam}" if fam else f"etf:{m['ticker']}"
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(m)
    rows = []
    for key in order:
        ms = buckets[key]
        rep = ms[0]
        if len(ms) == 1:
            note = (
                f"기초지수 {rep['index_name']}"
                if rep["index_name"]
                else "공식 기초지수 확인 불가 · 단독 표시"
            )
            rows.append(
                {
                    "key": key,
                    "kind": "single",
                    "title": rep["name"] or rep["ticker"],
                    "index_name": rep["index_name"],
                    "members": ms,
                    "rep": rep["ticker"],
                    "rep_rank": rep["rank"],
                    "note": note,
                    "lack": list(rep["lack"]),
                }
            )
            continue
        names = sorted({m["index_name"] for m in ms if m["index_name"]})
        note = (
            f"같은 공식 기초지수를 따르는 {len(ms)}개 상품"
            if len(names) == 1
            else f"같은 지수 계열 · 공식 기초지수명이 다른 상품 포함(지수명 {len(names)}개) · {len(ms)}개 상품"
        )
        rows.append(
            {
                "key": key,
                "kind": "group",
                "title": rep["index_name"],
                "index_name": rep["index_name"],
                # 구성원의 공식 기초지수명이 서로 다름(계열 사전으로 묶임) — 상품마다 공식 지수명을 보인다(I-29)
                "index_names_differ": len(names) > 1,
                "members": ms,
                "rep": rep["ticker"],
                "rep_rank": rep["rank"],
                "note": note,
                "lack": list(dict.fromkeys(x for m in ms for x in m["lack"])),
            }
        )
    return rows


def ranks_text(ms: Sequence[Mapping[str, Any]]) -> str:
    return " · ".join(str(m["rank"]) for m in ms)


# ── ③ 고른 ETF 와 내 보유의 겹침 ─────────────────────────────────────────────
def _dsum(vals: Sequence[Optional[str]]) -> Decimal:
    return sum((Decimal(v) for v in vals if v is not None), Decimal(0))


def _q(d: Decimal) -> str:
    return str(d.quantize(px.R_STEP, rounding=ROUND_HALF_UP))


def _pct2(d: Decimal) -> str:
    """소수 둘째 자리 반올림(노출 계산 서버 글 `pct2` 와 같은 규칙)."""
    return f"{_q(d)}%"


_STATUS_TEXT = {
    px.STATUS_NO_ETF_LIST: "확인 불가 — ETF 목록을 읽지 못해 보유 ETF 와 직접 보유를 가를 수 없습니다(겹침 없음이라는 뜻 아님)",
    px.STATUS_HOLDINGS_UNREADABLE: "보유 목록을 읽지 못했습니다 — 내 보유 노출 확인 불가(겹침 없음이라는 뜻 아님)",
    px.STATUS_NO_HOLDINGS: "등록 보유 없음 — 내 보유 노출을 계산할 대상이 없습니다",
    px.STATUS_NO_WEIGHT_BASIS: "비중 확인 불가 — 시세가 확인된 보유가 없어 분모(현금 제외 보유 평가액)를 정하지 못했습니다",
}


def _no_data_text(cand: Mapping[str, Any]) -> str:
    if cand.get("state") == px.STATE_UNCONFIRMED:
        why = f"구성 원천 기준일 미확인({cand.get('asof')} 보존 자료)"
    else:
        why = "구성 자료 없음"
    # 「ETF 구성종목」은 V2 에서 메뉴가 아니라 상세 화면 — 이 ETF 의 [구성종목 보기]에서 연다(PLAN V2 S4 · R5)
    return f"자료 없음 — 이 ETF 의 {why} · [구성종목 보기]에서 수집(겹침 없음이라는 뜻 아님)"


def _range_lines(scope: Mapping[str, Any]) -> list[str]:
    used = [e for e in scope["etfs"] if e["use"] == px.USE_SUM]
    part = [e for e in used if e["range"] != px.RANGE_FULL]
    lines = []
    if part:
        kinds = sorted({_RANGE_ROWS.get(e["range"], "저장된 행") for e in part})
        where = kinds[0] if len(kinds) == 1 else "저장된 상위 행"
        lines.append(
            f"보유 평가액의 {_pct2(_dsum([e['weight'] for e in part]))}(보유 ETF {len(part)}개)에 "
            f"해당하는 ETF 는 {where} 밖 구성이 미확인 — {NOT_ZERO}"
        )
    for key, why in (
        ("other_date", "구성일이 달라 합계에서 뺐습니다"),
        ("unconfirmed", "구성 원천 기준일 미확인이라 합계에서 뺐습니다"),
        ("no_data", "구성 자료가 없어 확인 불가"),
    ):
        g = scope[key]
        if g["count"]:
            lines.append(
                f"보유 평가액의 {_pct2(Decimal(g['weight'] or '0'))}(보유 ETF {g['count']}개)는 {why}"
            )
    if scope["no_weight"]["count"]:
        lines.append(
            f"시세가 없어 비중을 모르는 보유 {scope['no_weight']['count']}개(분모 밖)"
        )
    return lines


def _date_line(body: Mapping[str, Any]) -> str:
    d, b = body["dates"], body.get("basis") or {}
    cand = md(d["candidate"]) if d.get("candidate") else "확인 불가"
    if body["status"] != px.STATUS_OK:
        # 노출을 계산하지 않은 상태 — 노출 합계 · 보유 평가 날짜를 '없음'으로 쓰지 않는다(검토 F3)
        why = (
            "보유 목록을 읽지 못함"
            if body["status"] == px.STATUS_HOLDINGS_UNREADABLE
            else "계산하지 않음"
        )
        return f"기준일: 고른 ETF 구성 {cand} · 노출 합계 확인 불가({why}) · 금액 없음"
    pd = b.get("price_date") or {}
    if pd.get("state") == "KNOWN":
        when = (
            md(pd["min"])
            if pd["min"] == pd["max"]
            else f"{md(pd['min'])} ~ {md(pd['max'])}"
        )
    else:
        when = "확인 불가"
    exp = md(d["exposure"]) if d.get("exposure") else "구성 자료 없음(직접 보유만)"
    base = "부분 평가액" if b.get("partial") else "현금 제외 보유 평가액"
    return f"기준일: 고른 ETF 구성 {cand} · 노출 합계 {exp} · 보유 평가 {when}({base}) · 금액 없음"


def _unknown_share(ex: Mapping[str, Any], *, weight_unknown: bool) -> Decimal:
    """한 주식의 노출 합계에서 빠진 보유 ETF 평가 비중(저장 범위 밖 · 편입 비중 확인 불가를 나눔)."""
    return _dsum(
        [
            u["holding_weight"]
            for u in ex.get("unknown") or []
            if (u["range"] == px.WEIGHT_UNKNOWN) == weight_unknown
        ]
    )


def overlap_of(
    selected: Mapping[str, Any], body: Optional[Mapping[str, Any]], error: bool = False
) -> dict[str, Any]:
    """고른 ETF 의 보유 겹침 글(판정 Q4 · 범위 먼저 · 보유 이름 · 금액 없음)."""
    out: dict[str, Any] = {
        "ticker": selected["ticker"],
        "name": selected["name"],
        "rank": selected["rank"],
        "state": "error" if error else (body or {}).get("status"),
        "warn_lines": [],
        "lines": [],
        "date_line": None,
        "numbers": None,
    }
    if error or body is None:
        out["warn_lines"] = [
            "보유 겹침을 계산하지 못했습니다 — [다시 읽기]로 다시 시도(겹침 없음이라는 뜻 아님)"
        ]
        return out
    st = body["status"]
    if st == px.STATUS_NO_CANDIDATE_DATA:
        out["state"] = "no_data"
        out["warn_lines"] = [_no_data_text(body["candidate"])]
        return out
    if st != px.STATUS_OK:
        out["warn_lines"] = [_STATUS_TEXT.get(st, "보유 겹침 확인 불가")]
        if body["candidate"].get("state") != px.STATE_CONFIRMED:
            out["warn_lines"].append(_no_data_text(body["candidate"]))
        out["date_line"] = _date_line(body)
        return out
    scope = body["scope"]
    out["warn_lines"] = _range_lines(scope)
    stocks = body["stocks"]
    vals = [
        Decimal(s["exposure"]["value"])
        for s in stocks
        if s["exposure"]["value"] is not None
    ]
    oor = [_unknown_share(s["exposure"], weight_unknown=False) for s in stocks]
    wun = [_unknown_share(s["exposure"], weight_unknown=True) for s in stocks]
    no_val = len(stocks) - len(vals)
    if not stocks:
        out["lines"].append(
            "고른 ETF 의 주요 행에 주식이 없어 보유 노출을 계산하지 않았습니다"
        )
    else:
        rng = f"{_pct2(min(vals))} ~ {_pct2(max(vals))}" if vals else "확인 불가"
        extra = f" · 확인 불가 {no_val}개" if no_val and vals else ""
        miss = (
            f" · 주식마다 저장 범위에서 미확인 몫 {_pct2(min(oor))} ~ {_pct2(max(oor))}"
            if any(oor)
            else ""
        ) + (
            f" · 편입 비중 확인 불가 몫 {_pct2(min(wun))} ~ {_pct2(max(wun))}"
            if any(wun)
            else ""
        )
        out["lines"].append(
            f"확보된 행으로 계산한 주요 주식별 보유 노출 범위 {rng}(주식 {len(stocks)}개{extra}{miss})"
        )
    full = _dsum(
        [
            e["weight"]
            for e in scope["etfs"]
            if e["use"] == px.USE_SUM and e["range"] == px.RANGE_FULL
        ]
    ) + Decimal(scope["direct"]["weight"] or "0")
    out["lines"].append(
        "분모 = 현금 제외 보유 평가액 · 원천 전체 구성이 확인된 ETF 와 직접 보유의 평가 비중 "
        f"{_pct2(full)}"
    )
    out["date_line"] = _date_line(body)
    out["numbers"] = {
        "min": _q(min(vals)) if vals else None,
        "max": _q(max(vals)) if vals else None,
        "stocks": len(stocks),
        "no_value": no_val,
        "full_confirmed": _q(full),
    }
    return out


# ── 넘기기 · 저장(판정 Q7 · 기존 칸만 · 정의 밖 칸은 저장 때 버려지므로 넣지 않음) ─────────────────
def _same_item(
    status_ok: bool,
    start: Optional[str],
    end: Optional[str],
    etf: Optional[float],
    kodex: Optional[float],
) -> dict[str, Any]:
    if not status_ok or etf is None or kodex is None:
        return {
            "status": "unavailable",
            "reason": "candidate_period_unknown",
            "start_date": start,
            "end_date": end,
            "candidate_return_pct": etf,
            "kodex200_return_pct": None,
            "diff_pctp": None,
        }
    return {
        "status": "ok",
        "reason": None,
        "start_date": start,
        "end_date": end,
        "candidate_return_pct": etf,
        "kodex200_return_pct": kodex,
        "diff_pctp": round(etf - kodex, 4),
    }


def candidate_snapshot(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    """AI 세션 저장 목록(30개 · 순위 · 코드 · 1 · 3개월 · 같은 기간 KODEX 200 실제 기간 · 기존 칸 그대로)."""
    k3 = summary["kodex200"].get("three_month_return_pct")
    w3 = (summary.get("criteria_periods") or {}).get("three_month") or {}
    out = []
    for r in summary["top"]:
        c1, c3 = r["criteria"]["one_month"], r["criteria"]["three_month"]
        same = r["criteria"]["same_kodex_1m"]
        three_ok = c3.get("status") == "ok" and (c3.get("start"), c3.get("end")) == (
            w3.get("start"),
            w3.get("end"),
        )
        out.append(
            {
                "rank": r["rank"],
                "ticker": r["ticker"],
                "name": r["name"],
                "daily_return_pct": None,
                "one_month_return_pct": _ok(c1),
                "three_month_return_pct": _ok(c3),
                "tags": list(r.get("tags") or []),
                "same_period_kodex200": {
                    "one_month": _same_item(
                        same.get("status") == "ok",
                        same.get("start"),
                        same.get("end"),
                        same.get("etf_return_pct"),
                        same.get("kodex200_return_pct"),
                    ),
                    "three_month": _same_item(
                        three_ok, c3.get("start"), c3.get("end"), _ok(c3), k3
                    ),
                },
            }
        )
    return out


COMMON_KEYS = (
    "status",
    "message",
    "generated_at",
    "review_date",
    "basis",
    "fields",
    "evidence_items",
    "data_status",
)


def common_snapshot(mev: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    """공통 시장 근거 그대로(지표별 칸 · 근거 줄 · 자료 상태 — 주간 복사 글의 시장 [근거 n] 과 같은 줄 · PLAN V2 §4-3
    '시장 근거 칸 = 공통 시장 근거 칸'). 일일 글(`daily_text`)은 넣지 않는다(일일 복사는 저장 안 함 · 판정 Q8 (a)).
    받지 못했으면(None) '읽지 못함'(빈 칸을 '없음'으로 쓰지 않음)."""
    if mev is None:
        return {"status": "unavailable", "message": "공통 시장 근거를 읽지 못함"}
    return {k: mev.get(k) for k in COMMON_KEYS}


def market_snapshot(
    summary: Mapping[str, Any], common: Optional[Mapping[str, Any]] = None
) -> dict[str, Any]:
    """AI 세션 `market_context_snapshot`(자유 칸) — 이 한 장이 보인 시장 근거와 날짜.

    `common` = 공통 시장 근거(`build_market_evidence` 응답) → `common_snapshot` 으로 저장 — 화면 ① · 복사 글의 시장
    [근거 n] 과 같은 칸(PLAN V2 §4-3 '시장 근거 칸 = 공통 시장 근거 칸'). 다시 열 때 오늘 시세 · 수집 시각은 이 칸에
    남은 값만 쓴다(판정 Q6 · Q7). 목록 쪽 같은 기간 KODEX 200(목록 근거)만 따로 둔다 — V1 의 목록 요약 판정 ·
    시장 흐름 줄은 화면 ①이 공통 근거로 바뀌어 저장하지 않는다(한 기록에 시장 근거 한 벌)."""
    return {
        "source": SOURCE_SCREEN,
        "common": common_snapshot(common),
        "kodex200_same_period": {
            "start": summary["period"]["start"],
            "end": summary["period"]["end"],
            "return_pct": summary["kodex200"]["basis_return_pct"],
        },
    }
