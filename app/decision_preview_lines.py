"""POC5-23 — 판단 근거 미리보기의 묶음별 글 줄(순수 함수 · 조회는 시장 참고 1회만).

`app/decision_draft_preview_service.py` 가 묶음 순서대로 부른다. 값은 화면 API 응답에서 온 것만 옮긴다 —
새 산식 · 점수 · 결론 없음 · 값이 없으면 그 묶음 안에 사유. 문구 · 표시 정밀도는 화면 helper 와 같다
(`lib/samePeriodKodex.ts` · `holdings_risk_evidence/priceVolatility.ts` · `lib/storedVolume.ts` ·
`holdings_risk_evidence/declineSummary.ts` · 「ETF 구성종목」 중복률 'Top 10 기준').
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from app.etf_nav_fetcher import (
    DISCOUNT_CHECK_THRESHOLD_PCT,
    DISCOUNT_WARNING_THRESHOLD_PCT,
)
from app.market_risk_reference_service import build_market_risk_reference
from app.preview_number_format import (
    fmt_exact,
    intl_fixed,
    math_round_grouped,
    to_fixed,
)

BASIS_LABEL = {"daily": "일간", "one_month": "1개월", "three_month": "3개월"}
# 화면 `lib/samePeriodKodex.ts` 와 같은 문구(POC5-22).
SAME_PERIOD_LIMIT = "저장 종가로 계산하며 가격 조정 기준의 연속성은 검사하지 않습니다."
SAME_REASON = {
    "candidate_period_unknown": "후보 기간 확인 불가",
    "kodex200_start_price_missing": "KODEX200 시작일 가격 없음",
    "kodex200_end_price_missing": "KODEX200 끝일 가격 없음",
}
# 화면 `holdings_risk_evidence/priceVolatility.ts` 와 같은 문구(POC5-16).
VOL_COMPARISON = {
    "higher": "직전보다 커짐",
    "lower": "직전보다 작아짐",
    "same": "직전과 같음",
}
VOL_REASON = {
    "insufficient_history": "자료 부족",
    "invalid_price": "가격 확인 필요",
    "basis_unconfirmed": "가격 기준 확인 필요",
}
# 화면 `lib/storedVolume.ts` 배수 사유(POC5-09).
VOLUME_RATIO_REASON = {
    "volume_missing": "자료 없음",
    "avg_insufficient": "자료 부족",
    "avg_zero": "계산 불가",
}
SHORT_NOTE_HOLDING = (
    "단기 차이는 이 종목과 KODEX200 을 각각 저장일 수로 센 구간의 변화율 차이입니다"
    "(1 · 3개월 동일 기간 비교와 다름 · 보유는 시작 · 끝 날짜가 KODEX200 과 다르면 비움)."
)
SHORT_NOTE_CANDIDATE = (
    "단기 차이는 이 종목과 KODEX200 을 각각 저장일 수로 센 구간의 변화율 차이입니다"
    "(1 · 3개월 동일 기간 비교와 다름 · 후보는 날짜 일치를 따로 검사하지 않음 — 위 두 날짜 참고)."
)
# NAV 괴리 경고 코드(`etf_nav_fetcher.classify_discount_flag`)의 한국어 — AI 글에 영문 코드를 넣지 않는다.
NAV_FLAG_TEXT = {
    "discount_check_needed": f"괴리율 절대값 {DISCOUNT_CHECK_THRESHOLD_PCT:g}% 이상 · 확인 필요",
    "discount_warning": f"괴리율 절대값 {DISCOUNT_WARNING_THRESHOLD_PCT:g}% 이상 · 경고",
}
HOLDING_OVERLAP_SCOPE = (
    "구성종목 겹침(이 ETF 저장 구성종목 상위 10건 ↔ 구성종목이 저장된 "
    "현재 1개월 상위 10 후보에 2번 이상 나오는 종목)"
)
HOLDING_OVERLAP_LIMIT = (
    "후보 구성종목이 저장된 경우만 비교한 Top 10 기준 값이며 "
    "내 보유 ETF 사이의 중복이나 ETF 전체 구성종목을 조사한 값이 아닙니다."
)
OVERLAP_LIMIT = (
    "각 ETF 저장 구성종목 상위 10건끼리 비교한 값(Top 10 기준)이며 "
    "ETF 전체 구성종목을 조사한 값이 아닙니다."
)
AI_REQUEST = [
    "위 관측값을 ① 함께 확인되는 사실 ② 가능한 다른 해석 ③ 추가로 확인할 사항으로 나눠 정리해 주세요.",
    "날짜가 다른 값은 그 차이를 함께 짚고, 매수 · 매도 결론이나 위험 등급은 만들지 말아 주세요.",
]


# ─── 숫자 · 글 조각 ─────────────────────────────────────────────────────


def one_line(value: Any) -> str:
    """이름 · 사유 같은 저장 글을 한 줄로(묶음 경계 = 빈 줄이라 글 안 줄바꿈을 없앤다)."""
    return " ".join(str(value).split())


def fmt_pct(value: Optional[float], unit: str = "%", plus_zero: bool = False) -> str:
    """퍼센트 글 = toFixed(2) + 부호. 0 의 부호는 그 값이 나오는 화면 규칙을 따른다(검증자 r1 옆칸).

    plus_zero=True — 「보유와 비교」 카드 · 상세 · 「확인 근거」(`v >= 0 ? "+"` → '+0.00%'):
    단기 변화율 · 단기 차이 · 1 · 3개월 수익률 · NAV 괴리율 · 평가비중 · 손익률 · 일간 등락.
    plus_zero=False — 동일 기간 비교 `fmtSigned` · 시장 위험 참고 카드(`v > 0 ? "+"` → '0.00%').
    """
    if value is None:
        return "미확인"
    sign = "+" if (value >= 0 if plus_zero else value > 0) else ""
    return f"{sign}{to_fixed(value, 2)}{unit}"


def _fmt_int(value: Optional[float]) -> str:
    # 화면 NAV · 시장가 = Math.round(v).toLocaleString("ko-KR").
    return "미확인" if value is None else math_round_grouped(value)


def _span(start: Optional[str], end: Optional[str], sep: str = "→") -> str:
    return f" ({start} {sep} {end})" if start and end else ""


# ─── 묶음 ──────────────────────────────────────────────────────────────


def market_lines(
    regime: Optional[dict[str, Any]], db_path: Path
) -> tuple[list[str], Optional[str], Optional[str]]:
    """regime = {label, streak_days, at_least, asof} 또는 None(판정 불가)."""
    lines: list[str] = []
    if regime and regime.get("label"):
        streak = regime.get("streak_days")
        st = (
            f" · {streak}거래일째{' 이상' if regime.get('at_least') else ''}"
            if isinstance(streak, int)
            else ""
        )
        lines.append(
            f"시장 국면: {one_line(regime['label'])}{st} "
            f"(KODEX200 {regime.get('asof') or '날짜 확인 불가'} 기준)"
        )
    else:
        lines.append("시장 국면: 판정 불가")
    ref = build_market_risk_reference(db_path=db_path)
    k, v = ref.kodex200, ref.vix
    if k.availability == "available":
        lines.append(f"KODEX200 {k.as_of_date} · 전일 대비 {fmt_pct(k.change_1d_pct)}")
    else:
        lines.append("KODEX200: 자료 없음")
    if v.availability == "available":
        lines.append(
            f"VIX {v.as_of_date}(미국 날짜) · 전일 대비 {fmt_pct(v.change_1d_pct)} · "
            f"5거래일 {fmt_pct(v.change_5d_pct)}"
        )
    else:
        lines.append("VIX: 자료 없음")
    return lines, k.as_of_date, v.as_of_date


def _short_diffs(stm: dict[str, Any], fill: str) -> str:
    parts = []
    for n in (5, 10, 20):
        e = stm.get(f"excess_vs_kodex200_{n}d_pctp")
        parts.append(
            f"{n}저장일 {fmt_pct(e, '%p', plus_zero=True) if e is not None else fill}"
        )
    return " · ".join(parts)


def _returns_line(stm: dict[str, Any], start: Optional[str], end: Optional[str]) -> str:
    return (
        f"변화율 5저장일 {fmt_pct(stm.get('return_5d_pct'), plus_zero=True)} · "
        f"10저장일 {fmt_pct(stm.get('return_10d_pct'), plus_zero=True)} · "
        f"20저장일 {fmt_pct(stm.get('return_20d_pct'), plus_zero=True)}{_span(start, end)}"
    )


def _decline_line(band: Optional[dict[str, Any]]) -> str:
    if not band:
        return "PC 20저장일 하락 구간: 확인 불가"
    if band.get("judgeable"):
        v = band.get("return_20d_pct_1dp")
        val = f" (20저장일 {to_fixed(v, 1)}%)" if isinstance(v, (int, float)) else ""
        if band.get("state"):
            return f"{band.get('label')}{val}"
        return f"PC 20저장일 하락 구간: 해당 없음{val}"
    reason = {
        "date_mismatch": "기준일이 KODEX200 과 다름",
        "insufficient_history": "저장 종가 부족",
    }.get(band.get("unjudged_reason") or "", "값 확인 필요")
    return f"PC 20저장일 하락 구간: 판정하지 않음({reason})"


def holding_flow_lines(
    item: dict[str, Any], reference_date: Optional[str]
) -> list[str]:
    pd_ = item.get("price_dates") or {}
    stm = item.get("short_term_momentum") or {}
    if pd_.get("comparison") == "date_mismatch":
        return [
            f"값 없음 — 이 종목 마지막 저장일({pd_.get('end_date') or '확인 불가'})이 "
            f"PC 비교 기준일(KODEX200 {reference_date or '확인 불가'})과 다릅니다."
        ]
    if stm.get("status") != "ok":
        return ["값 없음 — 이 종목이나 KODEX200 의 저장 종가가 부족합니다(21개 필요)."]
    return [
        _returns_line(stm, pd_.get("start_date_20d"), pd_.get("end_date")),
        f"단기 KODEX200 차이(저장일 수 기준) {_short_diffs(stm, '시작일 달라 비움')}",
        _decline_line(item.get("decline_band")),
        SHORT_NOTE_HOLDING,
    ]


def candidate_flow_lines(cand: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    rets = cand.get("returns") or {}
    parts = []
    for key, label in (("one_month", "1개월"), ("three_month", "3개월")):
        r = rets.get(key) or {}
        parts.append(
            f"{label} {fmt_pct(r.get('return_pct'), plus_zero=True)}"
            f"{_span(r.get('price_start_date'), r.get('price_end_date'))}"
        )
    lines.append(" · ".join(parts))
    stm = cand.get("short_term_momentum") or {}
    if stm.get("status") != "ok":
        lines.append("단기 흐름: 값 없음 — 저장 종가가 부족합니다(21개 필요).")
        return lines
    sd = stm.get("start_dates") or {}
    kd = stm.get("kodex200_start_dates") or {}
    lines.append(_returns_line(stm, sd.get("twenty_d"), stm.get("end_date")))
    k20 = _span(kd.get("twenty_d"), stm.get("kodex200_end_date"))
    lines.append(
        f"단기 KODEX200 차이(저장일 수 기준) {_short_diffs(stm, '미확인')}"
        + (f" · KODEX200 20저장일{k20}" if k20 else "")
    )
    lines.append(SHORT_NOTE_CANDIDATE)
    return lines


def same_period_lines(sp: Optional[dict[str, Any]], holding: bool) -> list[str]:
    if not sp:
        if holding:
            return [
                "1개월 · 3개월: 값 없음 — 동일 기간 비교는 현재 1개월 상위 10 후보에 든 보유 종목만 제공합니다."
            ]
        return ["1개월 · 3개월: 값 없음"]
    lines: list[str] = []
    any_ok = False
    for key, label in (("one_month", "1개월"), ("three_month", "3개월")):
        it = sp.get(key)
        if not it:
            lines.append(f"{label}: 값 없음")
        elif it.get("status") == "ok":
            any_ok = True
            lines.append(
                f"{label} {fmt_pct(it.get('diff_pctp'), '%p')} "
                f"(후보 {fmt_pct(it.get('candidate_return_pct'))} · "
                f"KODEX200 {fmt_pct(it.get('kodex200_return_pct'))} · "
                f"사용 종가 {it.get('start_date')} → {it.get('end_date')})"
            )
        else:
            reason = SAME_REASON.get(it.get("reason") or "", "계산 불가")
            lines.append(
                f"{label}: 계산 불가 — {reason}"
                f"{_span(it.get('start_date'), it.get('end_date'))}"
            )
    if any_ok:
        lines.append(SAME_PERIOD_LIMIT)
    return lines


def volume_lines(
    sv: Optional[dict[str, Any]], reference_date: Optional[str]
) -> list[str]:
    if not sv:
        return ["거래량 자료 없음"]
    if sv.get("status") != "ok":
        return ["저장 가격 자료 없음"]
    vol = sv.get("volume")
    vol_s = f"{fmt_exact(vol)}주" if vol is not None else "자료 없음"
    avg = sv.get("avg_prev20")
    avg_s = (
        f"{intl_fixed(avg, 2)}주"
        if sv.get("avg_status") == "ok" and avg is not None
        else f"자료 부족 ({sv.get('valid_count')}/{sv.get('window_size')})"
    )
    ratio = sv.get("ratio")
    rs = sv.get("ratio_status")
    ratio_s = (
        f"{intl_fixed(ratio, 2)}배"
        if rs == "ok" and ratio is not None
        else VOLUME_RATIO_REASON.get(rs or "", "자료 없음")
    )
    lines = [
        f"{sv.get('asof_date')} 거래량 {vol_s} · "
        f"직전 {sv.get('window_size')}개 저장일 평균 {avg_s} · 평균 대비 {ratio_s}"
    ]
    if sv.get("window_start_date") and sv.get("window_end_date"):
        lines.append(
            f"비교 구간 {sv['window_start_date']} ~ {sv['window_end_date']} · "
            f"유효 {sv.get('valid_count')}/{sv.get('window_size')}"
        )
    asof = sv.get("asof_date")
    if reference_date and asof and asof != reference_date:
        lines.append(
            f"과거 저장 자료 · PC 비교 기준일은 {reference_date}"
            if asof < reference_date
            else f"PC 비교 기준일({reference_date})보다 늦은 날짜의 자료"
        )
    return lines


def _vol_cell(w: Optional[dict[str, Any]], reason: Optional[str]) -> str:
    if w:
        return f"{to_fixed(w['value_pct'], 2)}%"
    return VOL_REASON.get(reason or "", "확인 불가")


def volatility_lines(
    pv: Optional[dict[str, Any]], reference_date: Optional[str]
) -> list[str]:
    if not pv:
        return ["가격 흔들림 자료 없음"]
    st = pv.get("status")
    if st == "reference_unavailable":
        return ["값 숨김 — PC 가격 흐름 기준일을 확인할 수 없습니다."]
    if st == "date_mismatch":
        return [
            f"값 숨김 — 이 종목의 마지막 유효 가격일({pv.get('end_date') or '확인 불가'})이 "
            f"PC 가격 흐름 기준일({reference_date or '확인 불가'})과 다릅니다."
        ]
    rec, prev = pv.get("recent"), pv.get("previous")
    head = (
        f"최근 20구간 {_vol_cell(rec, pv.get('recent_reason'))} · "
        f"직전 20구간 {_vol_cell(prev, pv.get('previous_reason'))}"
    )
    comp = pv.get("comparison")
    if comp:
        head += f" · {VOL_COMPARISON.get(comp, comp)}"
    lines = [head + " (하루 가격 변화의 표준편차)"]
    periods = []
    if rec:
        periods.append(f"최근 {rec['start_date']} ~ {rec['end_date']}")
    if prev:
        periods.append(f"직전 {prev['start_date']} ~ {prev['end_date']}")
    if not periods and pv.get("end_date"):
        periods.append(f"마지막 유효 가격일 {pv['end_date']}")
    lines.append(" · ".join([*periods, "PC 저장 종가"]))
    note = {
        "unavailable": "최근 · 직전 20구간 모두 계산하지 못했습니다.",
        "recent_only": "직전 20구간은 계산하지 못해 비교하지 않습니다.",
        "previous_only": "최근 20구간은 계산하지 못해 비교하지 않습니다.",
    }.get(st or "")
    if note:
        lines.append(note)
    return lines


def nav_line(nav: Optional[dict[str, Any]]) -> str:
    """화면과 같은 규칙 — ok · partial 이면 값을 보이고 partial 은 '부분 자료'를 숨기지 않는다."""
    nav = nav or {}
    if (
        nav.get("status") in ("ok", "partial")
        and nav.get("discount_rate_pct") is not None
    ):
        line = (
            f"NAV 괴리율 {fmt_pct(nav.get('discount_rate_pct'), plus_zero=True)} "
            f"(NAV {_fmt_int(nav.get('nav'))} · 시장가 {_fmt_int(nav.get('market_price'))}"
            f"{' · ' + nav['asof'] if nav.get('asof') else ''})"
        )
        if nav.get("status") == "partial":
            msg = f" · {one_line(nav['message'])}" if nav.get("message") else ""
            line += f" — 부분 자료{msg}"
        flag = nav.get("flag")
        if flag:
            line += f" — {NAV_FLAG_TEXT.get(flag, '확인 필요')}"
        return line
    return "NAV 괴리율: 자료 없음"


def _core_item(o: dict[str, Any]) -> str:
    name = one_line(o.get("name") or o.get("ticker") or "이름 없음")
    w = o.get("weight_pct")
    count = o.get("market_core_count")
    weight = f" {to_fixed(w, 2)}%" if w is not None else ""
    repeat = f"(후보 {count}개에 반복)" if count else ""
    return f"{name}{weight}{repeat}"


def holding_overlap_lines(
    item: dict[str, Any], constituents_asof: Optional[str]
) -> list[str]:
    """보유 근거 `constituents_overlap` 의 실제 뜻 그대로(판정 §2 — '내 보유 ETF 사이 중복' 아님).

    builder 는 구성종목이 저장된 상위 후보만으로 '반복 종목'을 만든다 — 그래서 일치 0건을 '없음'으로
    쓰지 않고 '비교 범위 한정'으로 적는다.
    """
    ov = item.get("constituents_overlap") or {}
    status = ov.get("status")
    if status == "ok":
        items = ov.get("overlap_with_market_core") or []
        asof = f" · 이 ETF 구성종목 {constituents_asof}" if constituents_asof else ""
        body = (
            ", ".join(_core_item(o) for o in items)
            if items
            else "일치 0건(비교 범위 한정 · 겹침이 없다는 뜻 아님)"
        )
        return [f"{HOLDING_OVERLAP_SCOPE}: {body}{asof}", HOLDING_OVERLAP_LIMIT]
    if status == "constituents_unavailable":
        return [
            "구성종목 겹침: 확인 불가 — 이 ETF 의 구성종목 자료가 저장돼 있지 않습니다(겹침 없음이라는 뜻 아님)."
        ]
    if status == "market_core_unavailable":
        return [
            "구성종목 겹침: 확인 불가 — 비교할 현재 후보의 구성종목 자료가 없습니다."
        ]
    return ["구성종목 겹침: 확인 불가"]


def candidate_overlap_lines(
    direct: Optional[dict[str, Any]], ov: Optional[dict[str, Any]]
) -> list[str]:
    lines: list[str] = []
    if direct is None:
        lines.append("직접 보유: 확인 불가 — 보유 목록을 읽지 못했습니다.")
    else:
        lines.append(
            "직접 보유: 있음(이미 보유 중)" if direct.get("held") else "직접 보유: 없음"
        )
    if ov is None:
        lines.append(
            "보유 ETF 와 구성종목 중복: 확인 불가 — 보유 목록을 읽지 못했습니다."
        )
        return lines
    head = "보유 ETF 와 구성종목 중복"
    if not ov.get("candidate_available"):
        lines.append(
            f"{head}: 비교하지 않음 — 이 후보의 구성종목 자료가 저장돼 있지 않습니다(중복 없음이라는 뜻 아님)."
        )
        return lines
    held = ov.get("held_etf_count") or 0
    if held == 0:
        lines.append(
            f"{head}: 비교할 보유 ETF 없음 (후보 구성종목 {ov.get('candidate_asof')})"
        )
        return lines
    pairs = ov.get("pairs") or []
    lines.append(
        f"{head}(Top 10 기준): 비교 가능 {len(pairs)}/{held}개 · 후보 구성종목 {ov.get('candidate_asof')}"
    )
    hit = [p for p in pairs if (p.get("common_count_top10") or 0) > 0]
    hit.sort(
        key=lambda p: (
            -(
                p.get("weighted_overlap_pct")
                if p.get("weighted_overlap_pct") is not None
                else -1.0
            ),
            -(p.get("common_count_top10") or 0),
        )
    )
    for p in hit:
        rate = p.get("weighted_overlap_pct")
        rate_s = (
            f"비중 중복률 {to_fixed(rate, 2)}%"
            if rate is not None
            else "비중 중복률 확인 불가"
        )
        common = ", ".join(
            one_line(h.get("name") or h.get("ticker") or "이름 없음")
            for h in p.get("common_holdings") or []
        )
        lines.append(
            f"{one_line(p.get('name') or p['ticker'])}({p['ticker']} · {p.get('asof')}): "
            f"공통 {p.get('common_count_top10')}종목 · {rate_s} — {common}"
        )
    zero = len(pairs) - len(hit)
    if zero:
        lines.append(f"상위 10 공통 종목이 없는 쌍: {zero}개(그 쌍만의 결과)")
    missing = ov.get("missing") or []
    if missing:
        lines.append(f"구성종목 자료가 없는 보유 ETF {len(missing)}개는 비교하지 않음")
    lines.append(OVERLAP_LIMIT)
    return lines


def daily_check_line(d: Optional[dict[str, Any]]) -> str:
    d = d or {}
    if not d or d.get("status") == "unavailable":
        return "일간 등락 점검: 자료 없음"
    span = _span(d.get("price_start_date"), d.get("price_end_date"))
    span = span.replace(" (", " · ").replace(")", "") if span else ""
    val = fmt_pct(d.get("daily_return_pct"), plus_zero=True)
    if d.get("flag"):
        why = one_line(d["message"]) if d.get("message") else "확인 필요"
        return f"일간 등락 점검: {why} ({val}{span})"
    return f"일간 등락 점검: 이상 표시 없음 ({val}{span})"
