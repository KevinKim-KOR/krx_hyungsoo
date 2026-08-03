"""POC3-06 §6 — 공통 판단 요약 composer (server-side · 신규 모듈).

설계자 Q3 확정: 기존 read 조합만. 신규 endpoint·DB·source·factor·threshold 0.
Dashboard read 응답과 PUSH package 가 **동일 결과**를 사용한다(§6.1·AC-2·AC-7).

구성:
- §6.2 시장 위치: KOSPI 관찰값(일간·1년·52주 고점 대비, market_regime helper) +
  기존 KODEX200 국면 라벨 + 국면 지속 거래일 수.
- §6.3 보유 요약: '오늘 먼저 볼 보유 ETF' 최대 3건. POC3-05 프론트
  `lowestFiveDayRows`/`buildRiskEvidenceRows` 와 **동일 규칙**을 Python 으로 재구현
  (Q2). status=ok & 5일 유효 종목만 5일 오름차순, 동률은 ticker 오름차순, 최대 N.
- §6.4 자료 상태: 각 자료의 status·기준일. 결측을 0·정상으로 위장하지 않는다(§9.3).

본 모듈은 순수 조립 — 외부 호출·저장 없음. 입력은 기존 evidence dict / market_context
dict / market_risk dict (모두 read-only). signal·rank 저장 0.
"""

from __future__ import annotations

from typing import Any, Optional

# '오늘 먼저 볼 보유 ETF' 최대 노출 건수 (POC3-05 Dashboard 규칙과 동일).
TOP_HOLDINGS_LIMIT = 3


def _stm_status(item: dict) -> Optional[str]:
    stm = item.get("short_term_momentum") or {}
    return stm.get("status")


def _stm_return_5d(item: dict) -> Optional[float]:
    stm = item.get("short_term_momentum") or {}
    v = stm.get("return_5d_pct")
    return v if isinstance(v, (int, float)) else None


def select_top_holdings(
    evidence_holdings: list[dict], limit: int = TOP_HOLDINGS_LIMIT
) -> list[dict]:
    """'오늘 먼저 볼 보유 ETF' 최대 N건 (§6.3 · Q2).

    프론트 `lowestFiveDayRows` 와 동일 규칙:
    - status=ok 이고 return_5d_pct 가 유효(숫자)인 ticker 만 대상.
    - return_5d_pct 오름차순, 동률은 ticker 오름차순.
    - 최대 N 건.
    - 중복 ticker 는 첫 등장만 유지(evidence 는 이미 ticker 단위).
    위험 점수·rank·signal 을 만들지 않는다 — 표시 정렬일 뿐이다.
    """
    # 평가 비중(§4.4·AC-7) = 이 ticker 평가금액 / 전체 유효 평가금액 합. 기존 저장값
    # 단순 산술(신규 산식 아님). 합이 0 이거나 계산 불가면 None(0 위장 금지).
    total_eval = 0.0
    for it in evidence_holdings:
        ev = (
            (it.get("holding") or {}).get("evaluation_amount")
            if isinstance(it, dict)
            else None
        )
        if isinstance(ev, (int, float)):
            total_eval += ev

    seen: set[str] = set()
    sortable: list[dict] = []
    for it in evidence_holdings:
        ticker = it.get("ticker")
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        r5 = _stm_return_5d(it)
        if _stm_status(it) == "ok" and r5 is not None:
            sortable.append(it)

    sortable.sort(key=lambda it: (_stm_return_5d(it), it.get("ticker") or ""))
    out: list[dict] = []
    for it in sortable[:limit]:
        stm = it.get("short_term_momentum") or {}
        holding = it.get("holding") or {}
        eval_amount = holding.get("evaluation_amount")
        market_weight = None
        if isinstance(eval_amount, (int, float)) and total_eval > 0:
            market_weight = round(eval_amount / total_eval * 100.0, 1)
        out.append(
            {
                "ticker": it.get("ticker"),
                "name": it.get("name"),
                "eval_amount": eval_amount,
                "market_weight_pct": market_weight,
                "pnl_rate_pct": holding.get("pnl_rate_pct"),
                "return_5d_pct": stm.get("return_5d_pct"),
                "return_20d_pct": stm.get("return_20d_pct"),
                "excess_vs_kodex200_20d_pctp": stm.get("excess_vs_kodex200_20d_pctp"),
            }
        )
    return out


def _need_check(item: dict) -> bool:
    """자료 확인 필요 판정 (POC3-05 §6.2 핵심 표시값 기준, evidence 측만).

    enriched 결측은 상위 요약에서 별도 집계하므로, 여기서는 evidence 측
    status/흐름값 null 만 본다. NAV·구성종목·topn 은 판정에 넣지 않는다.
    """
    stm = item.get("short_term_momentum") or {}
    status = stm.get("status")
    if status in ("partial", "unavailable", None):
        return True
    for k in ("return_5d_pct", "return_20d_pct", "excess_vs_kodex200_20d_pctp"):
        if not isinstance(stm.get(k), (int, float)):
            return True
    return False


def summarize_holdings(evidence_holdings: Optional[list[dict]]) -> dict:
    """§6.3 보유 요약: 최대 3건 + coverage(전체·자료 확인 필요).

    입력 결측을 조용히 흡수하지 않는다(§9.3·B-1). evidence_holdings 가 list 가
    아니면 available=False 로 명시 — "보유 0건" 과 "자료 미확인" 을 구분한다.
    """
    if not isinstance(evidence_holdings, list):
        return {
            "available": False,
            "top_holdings": [],
            "coverage": {"total": 0, "need_check": 0, "ok": 0},
        }
    total = 0
    need = 0
    seen: set[str] = set()
    for it in evidence_holdings:
        ticker = it.get("ticker") if isinstance(it, dict) else None
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        total += 1
        if _need_check(it):
            need += 1
    return {
        "available": True,
        "top_holdings": select_top_holdings(evidence_holdings),
        "coverage": {"total": total, "need_check": need, "ok": total - need},
    }


def summarize_market_position(
    *,
    market_context: Optional[dict],
    kospi_position: Optional[dict],
    regime_streak: Optional[dict],
) -> dict:
    """§6.2 시장 위치: 기존 국면 라벨 + KOSPI 관찰값 + 지속 거래일 수.

    기존 market_context(regime_label·kodex200·kospi)는 그대로 두고, KOSPI 관찰값과
    지속일을 additive 로 얹는다. KODEX200 이 시장 국면 기준(§4.2)이며 KOSPI 는
    사용자 대표 지수 — 둘을 섞지 않는다.
    """
    # 입력 결측을 조용히 흡수하지 않는다(§9.3·B-1). market_context 가 dict 가
    # 아니거나 status=unavailable 이면 available=False 로 명시한다.
    available = isinstance(market_context, dict) and (
        market_context.get("status") not in (None, "unavailable")
    )
    mc = market_context if isinstance(market_context, dict) else {}
    kospi = mc.get("kospi") or {}
    return {
        "available": available,
        "regime_label": mc.get("regime_label"),
        "regime_code": mc.get("regime_code"),
        "regime_streak_days": (regime_streak or {}).get("streak_days"),
        "regime_streak_at_least": (regime_streak or {}).get("at_least", False),
        "kospi": {
            "status": kospi.get("status"),
            "daily_return_pct": (kospi_position or {}).get("daily_return_pct"),
            "return_1y_pct": (kospi_position or {}).get("return_1y_pct"),
            # 고점 대비: 음수%(고점이면 0). 비율(%) 표기 금지(설계자 Q1).
            "high_52w_gap_pct": (kospi_position or {}).get("high_52w_gap_pct"),
            "as_of_date": (kospi_position or {}).get("as_of_date"),
        },
        "market_asof": mc.get("asof"),
    }


def build_data_status(
    *,
    market_context: Optional[dict],
    market_risk: Optional[dict],
    evidence_asof: dict[str, Any],
) -> dict:
    """§6.4 자료 상태: 각 자료 status·기준일. 결측을 0·정상으로 위장하지 않는다.

    market_risk = build_market_risk_reference() 결과(vix/kodex200 availability·as_of).
    evidence_asof = {"holdings_asof":..., "market_asof":...}.
    """
    mc = market_context or {}
    mr = market_risk or {}
    vix = getattr(mr, "vix", None) or (mr.get("vix") if isinstance(mr, dict) else None)
    return {
        "market_context_status": mc.get("status"),
        "market_asof": mc.get("asof"),
        "kospi_status": (mc.get("kospi") or {}).get("status"),
        "kodex200_status": (mc.get("kodex200") or {}).get("status"),
        "vix_availability": (
            getattr(vix, "availability", None)
            if vix is not None and not isinstance(vix, dict)
            else (vix.get("availability") if isinstance(vix, dict) else None)
        ),
        "vix_asof": (
            getattr(vix, "as_of_date", None)
            if vix is not None and not isinstance(vix, dict)
            else (vix.get("as_of_date") if isinstance(vix, dict) else None)
        ),
        "holdings_asof": evidence_asof.get("holdings_asof"),
        "market_evidence_asof": evidence_asof.get("market_asof"),
    }


def compose_judgment_summary(
    *,
    market_context: Optional[dict],
    kospi_position: Optional[dict],
    regime_streak: Optional[dict],
    evidence_holdings: list[dict],
    market_risk: Optional[Any] = None,
    evidence_asof: Optional[dict[str, Any]] = None,
) -> dict:
    """§6 공통 판단 요약 — Dashboard read 응답·PUSH package 공용 단일 결과.

    한 번 계산해 반환한다. 화면별로 다시 계산·정렬하지 않는다(§6.1·AC-2).
    """
    return {
        "market_position": summarize_market_position(
            market_context=market_context,
            kospi_position=kospi_position,
            regime_streak=regime_streak,
        ),
        "holdings": summarize_holdings(evidence_holdings),
        "data_status": build_data_status(
            market_context=market_context,
            market_risk=market_risk,
            evidence_asof=evidence_asof or {},
        ),
    }
