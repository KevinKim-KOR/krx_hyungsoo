"""POC4-01 작업 6 — 전략 성과지표 · 거래비용 분해 (설계자 판정 2026-09-24 §3-2 · §3-3).

기존 판정(A1~A5 · R1~R4)은 그대로 두고, 결과에 `strategy_performance` 블록 하나를 더한다.
평가 기록은 **읽기만** 한다 — 이 블록을 빼면 결과 canonical hash 가 이전 기준선과 같아야 한다.

전략 — A2 와 같은 바스켓: 월말 점수 상위 10%(필터 universe) 동일가중 · 다음 거래일 진입 ·
다음 월말 다음 거래일 청산. 기간끼리 겹치지 않는다(다음 진입일 = 이번 청산일).

산식 (설계자 §3-3 — 차감 수익률을 복리 누적해 상대 equity 를 만들지 않는다)

```text
절대 equity    Π(1 + 비용 차감 후 전략수익률)
benchmark      Π(1 + KODEX200 수익률)
relative       전략 equity / benchmark equity
active return  비용 차감 후 전략수익률 − KODEX200 수익률   (추적오차 · 정보비율에만)
Sharpe_0rf     무위험수익률 자료가 없어 0 으로 둔다 — 이름에 0rf 를 붙인다
```

전략수익률 = 상위 10% 초과수익 평균(`top_decile_mean`) + 같은 기간 KODEX200 수익률. 초과수익이
`ETF 수익률 − KODEX200 수익률`(`forward_excess`)이므로 더하면 ETF 원수익률 평균이다.
"""

from __future__ import annotations

import math
import statistics
from datetime import date
from typing import Optional, Sequence

from app.ml_score_validity_eval import PRICE_BASIS_LABEL
from app.ml_score_validity_metrics import cost_drag, replaced_fraction

SCHEMA = "strategy_performance.v1"

# --- 거래비용 (설계자 §3-2) --------------------------------------------------------
TRANSACTION_TAX_BP = 0.0
COMMISSION_BP = 1.5
SLIPPAGE_BP_GRID = (5.0, 10.0, 25.0, 50.0)
PRIMARY_SLIPPAGE_BP = 10.0
STRESS_SLIPPAGE_BP = 50.0
LEGACY_ALL_IN_BP = 25.0
COST_NOTES = {
    "transaction_tax_bp": "국내 상장 ETF 매매는 증권거래세를 징수하지 않는다(공시 확인 · 설계자)",
    "commission_bp": "ASSUMPTION — 증권사 수수료 가정 · 법정 수치가 아니다",
    "slippage_bp": "ASSUMPTION — 호가 자료가 없어 5·10·25·50bp 민감도로 본다(50bp = 저유동성 스트레스)",
    "excluded": "배당소득세 · 매매차익 과세는 거래 시점 비용과 성격이 달라 이번 거래비용에서 제외",
    "turnover": "월별 비용 = 그 달 실측 교체비율 × 편도비용 × 2 · 첫 달은 직전 바스켓이 없어 0 "
    "(A2 와 같은 규칙)",
}


def cost_scenarios() -> list[dict]:
    """legacy all-in 25bp 1개 + 분해 시나리오 4개(슬리피지 grid)."""
    out = [
        {
            "name": "legacy_all_in_25bp",
            "one_way_bp": LEGACY_ALL_IN_BP,
            "commission_bp": None,
            "slippage_bp": None,
            "transaction_tax_bp": None,
            "role": "LEGACY_COMPARISON",
        }
    ]
    for slip in SLIPPAGE_BP_GRID:
        role = (
            "PRIMARY"
            if slip == PRIMARY_SLIPPAGE_BP
            else "STRESS" if slip == STRESS_SLIPPAGE_BP else "SENSITIVITY"
        )
        out.append(
            {
                "name": f"decomposed_slippage_{int(slip)}bp",
                "one_way_bp": COMMISSION_BP + slip + TRANSACTION_TAX_BP,
                "commission_bp": COMMISSION_BP,
                "slippage_bp": slip,
                "transaction_tax_bp": TRANSACTION_TAX_BP,
                "role": role,
            }
        )
    return out


# --- 지표 (순수 함수) ------------------------------------------------------------


def equity_curve(returns: Sequence[float]) -> list[float]:
    """1.0 에서 시작해 기간마다 (1 + r) 을 곱한 값. 반환 길이 = 기간 수."""
    out, level = [], 1.0
    for r in returns:
        level *= 1.0 + r
        out.append(level)
    return out


def max_drawdown(equity: Sequence[float]) -> Optional[float]:
    """최대 낙폭(음수 · 0 이면 낙폭 없음). 시작값 1.0 을 첫 고점으로 본다."""
    if not equity:
        return None
    peak, worst = 1.0, 0.0
    for level in equity:
        peak = max(peak, level)
        worst = min(worst, level / peak - 1.0)
    return worst


def cagr(end_equity: float, days: int) -> Optional[float]:
    if days <= 0 or end_equity <= 0:
        return None
    return end_equity ** (365.25 / days) - 1.0


def _std(values: Sequence[float]) -> Optional[float]:
    return statistics.stdev(values) if len(values) >= 2 else None


def annualized_volatility(returns: Sequence[float], ppy: float) -> Optional[float]:
    sd = _std(returns)
    return None if sd is None else sd * math.sqrt(ppy)


def annualized_ratio(returns: Sequence[float], ppy: float) -> Optional[float]:
    """평균 / 표준편차 × √(연간 기간 수). Sharpe_0rf · 정보비율에 같이 쓴다."""
    sd = _std(returns)
    if sd is None or sd == 0:
        return None
    return statistics.fmean(returns) / sd * math.sqrt(ppy)


# --- 조립 -------------------------------------------------------------------------


def _periods(records: Sequence[dict], benchmark_closes: dict[str, float]) -> tuple:
    """평가 기록을 **읽기만** 해서 기간별 (진입·청산·전략·벤치마크·교체비율)을 만든다."""
    periods, excluded, prev = [], [], None
    for r in records:
        tickers = r.get("top_decile_tickers") or []
        if r.get("top_decile_mean") is None:
            prev = tickers
            excluded.append(
                {"signal_date": r["signal_date"], "reason": "상위 10% 없음"}
            )
            continue
        rep = replaced_fraction(prev, tickers) if prev is not None else None
        prev = tickers
        k0 = benchmark_closes.get(r["entry_date"])
        k1 = benchmark_closes.get(r["exit_date"])
        if not k0 or not k1:
            excluded.append(
                {"signal_date": r["signal_date"], "reason": "KODEX200 종가 없음"}
            )
            continue
        bench = k1 / k0 - 1.0
        periods.append(
            {
                "signal_date": r["signal_date"],
                "entry_date": r["entry_date"],
                "exit_date": r["exit_date"],
                "benchmark_return": bench,
                "gross_return": r["top_decile_mean"] + bench,
                "replaced_fraction": rep,
            }
        )
    return periods, excluded


def _scenario_metrics(periods: list[dict], one_way_bp: float, ppy: float, days: int):
    net = [
        p["gross_return"] - cost_drag(p["replaced_fraction"], one_way_bp)
        for p in periods
    ]
    bench = [p["benchmark_return"] for p in periods]
    active = [n - b for n, b in zip(net, bench)]
    eq, beq = equity_curve(net), equity_curve(bench)
    rel = [e / b for e, b in zip(eq, beq)]
    metrics = {
        "absolute": {
            "end_equity": eq[-1],
            "cagr": cagr(eq[-1], days),
            "mdd": max_drawdown(eq),
            "annualized_volatility": annualized_volatility(net, ppy),
            "sharpe_0rf": annualized_ratio(net, ppy),
        },
        "relative": {
            "benchmark_end_equity": beq[-1],
            "benchmark_cagr": cagr(beq[-1], days),
            "benchmark_mdd": max_drawdown(beq),
            "relative_wealth_end": rel[-1],
            "relative_mdd": max_drawdown(rel),
            "mean_active_return": statistics.fmean(active),
            "tracking_error": annualized_volatility(active, ppy),
            "information_ratio": annualized_ratio(active, ppy),
        },
    }
    curves = {"strategy_equity": eq, "benchmark_equity": beq, "relative_wealth": rel}
    return metrics, curves


def build_strategy_performance(
    evaluation_records: Sequence[dict], benchmark_closes: dict[str, float]
) -> dict:
    periods, excluded = _periods(evaluation_records, benchmark_closes)
    base = {
        "schema_version": SCHEMA,
        "strategy": "모델 점수 상위 10% 동일가중 · 월말 신호 · 다음 거래일 진입 · 다음 월말 다음 "
        "거래일 청산 (A2 와 같은 바스켓 · 기간 비중첩)",
        "price_basis": PRICE_BASIS_LABEL,
        "formulas": {
            "absolute_equity": "Π(1 + 비용 차감 후 전략수익률)",
            "benchmark_equity": "Π(1 + KODEX200 수익률)",
            "relative_wealth": "전략 equity / benchmark equity",
            "active_return": "비용 차감 후 전략수익률 − KODEX200 수익률 (추적오차·정보비율에만)",
            "sharpe": "Sharpe_0rf — 무위험수익률 자료가 없어 0",
            "annualization": "연간 기간 수 = 기간 수 / (첫 진입 ~ 마지막 청산 달력일 / 365.25)",
            "mdd_granularity": "기간 말(월별) equity 기준 — 월중 낙폭은 반영하지 않는다",
        },
        "cost_model": {
            "transaction_tax_bp": TRANSACTION_TAX_BP,
            "commission_bp": COMMISSION_BP,
            "slippage_bp_grid": list(SLIPPAGE_BP_GRID),
            "primary_slippage_bp": PRIMARY_SLIPPAGE_BP,
            "primary_one_way_bp": COMMISSION_BP
            + PRIMARY_SLIPPAGE_BP
            + TRANSACTION_TAX_BP,
            "legacy_all_in_bp": LEGACY_ALL_IN_BP,
            "notes": COST_NOTES,
        },
        "periods": len(periods),
        "excluded_periods": excluded,
    }
    if not periods:
        return {**base, "status": "NO_PERIODS", "scenarios": {}}
    days = (
        date.fromisoformat(periods[-1]["exit_date"])
        - date.fromisoformat(periods[0]["entry_date"])
    ).days
    ppy = len(periods) / (days / 365.25) if days > 0 else 12.0
    scenarios, primary_curves = {}, None
    for sc in cost_scenarios():
        metrics, curves = _scenario_metrics(periods, sc["one_way_bp"], ppy, days)
        scenarios[sc["name"]] = {**sc, **metrics}
        if sc["role"] == "PRIMARY":
            primary_curves = curves
    return {
        **base,
        "status": "OK",
        "first_entry_date": periods[0]["entry_date"],
        "last_exit_date": periods[-1]["exit_date"],
        "calendar_days": days,
        "periods_per_year": ppy,
        "scenarios": scenarios,
        "primary_curves": {
            "exit_dates": [p["exit_date"] for p in periods],
            **(primary_curves or {}),
        },
    }
