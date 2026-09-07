"""POC3-OPS-02A — 위험 알림 흐름 조립 (러너에서 분리).

흐름: 보유 원장 → 가격 이력·거래일 축 → 선정 → 이전 상태 → 변화 판정 → 본문

**상태 저장은 여기서 하지 않는다.** 러너가 Telegram 전체 발송 성공을 확인한 뒤에
저장한다(OPS-01A 와 같은 계약 — 미발송 악화가 발송 완료로 기록되면 안 된다).

비거래일 판정·완전성 가드는 **OPS-01A 것을 그대로 재사용**한다. 신규 발명 금지.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from app.runtime_evidence.holdings_risk import (
    RiskTicker,
    previous_trading_day,
    select_risk_holdings,
)
from app.runtime_evidence.holdings_risk_render import render_risk_alert
from app.runtime_evidence.holdings_risk_state import (
    RiskChangeSet,
    compute_risk_changes,
    load_risk_state,
    merge_worst,
)
from app.runtime_evidence.holdings_selection_flow import (
    check_incomplete_without_today,
    check_non_trading_day,
    format_quote_asof,
)
from app.runtime_evidence.holdings_selection_source import (
    average_buy_prices,
    load_holding_rows,
    load_price_history,
    load_trading_day_axis,
)

# 실행 시각 → 화면 표기 없음. 위험 알림은 슬롯 개념이 없고 7틱마다 돈다.
# 헤더에는 실행 시각(HH:MM)을 그대로 쓴다.


def slot_label_from_runtime(runtime_kst: Optional[str]) -> str:
    """`2026-09-07T10:30:12+09:00` → `10:30`. 없으면 빈 문자열."""
    if not isinstance(runtime_kst, str) or len(runtime_kst) < 16:
        return ""
    return runtime_kst[11:16]


@dataclass
class HoldingsRiskOutcome:
    selected: list[RiskTicker] = field(default_factory=list)
    changes: Optional[RiskChangeSet] = None
    message_text: str = ""
    skip_reason: Optional[str] = None
    error: Optional[str] = None
    diagnostics: dict[str, Any] = field(default_factory=dict)
    save_entries: Optional[dict[str, dict[str, Any]]] = None
    today_kst: Optional[str] = None
    # (ticker, 종목명) — 본문 `데이터 확인 필요` 그룹에 그대로 실린다.
    unavailable: list[tuple[str, str]] = field(default_factory=list)


def build_holdings_risk_alert(
    *,
    holdings_loader: Callable[[], list[Any]],
    fetch_history: Callable[..., list[tuple[str, float]]],
    market_quotes: dict[str, Any],
    state_path: Path,
    runtime_kst: Optional[str],
    today_kst: Optional[str] = None,
    logger: Any = None,
) -> HoldingsRiskOutcome:
    """선정 → 변화 판정 → 본문. 예외는 `error` 로 돌려 러너가 failed 처리한다."""
    out = HoldingsRiskOutcome(today_kst=today_kst)
    try:
        holding_rows = load_holding_rows(holdings_loader)
        tickers = sorted({r["ticker"] for r in holding_rows})
        history = load_price_history(tickers, fetch_history=fetch_history)
        axis_dates = load_trading_day_axis(fetch_history=fetch_history)
        prev_day = previous_trading_day(axis_dates, today_kst)
        selected, unavailable = select_risk_holdings(
            holdings=holding_rows,
            price_history=history,
            market_quotes=market_quotes or {},
            today_kst=today_kst,
            axis_dates=axis_dates,
            avg_buy_prices=average_buy_prices(holding_rows),
        )
    except Exception as e:  # noqa: BLE001
        out.error = f"{type(e).__name__}: {str(e)[:200]}"
        return out

    out.selected = selected
    # PLAN §4.6 부분 실패 · §4.7 결손 — 진단에만 남기지 않고 **본문까지** 보낸다.
    # 이름은 보유 원장에서 찾는다. 여러 계좌에 같은 ticker 가 있어도 한 번만.
    name_by_ticker: dict[str, str] = {}
    for row in holding_rows:
        t = row.get("ticker")
        if t and row.get("name"):
            name_by_ticker[t] = row["name"]
    out.unavailable = [(t, name_by_ticker.get(t, t)) for t in unavailable]

    out.diagnostics = {
        "risk_holdings_loaded_count": len(holding_rows),
        "risk_unique_ticker_count": len(tickers),
        "risk_selected_count": len(selected),
        "risk_prev_trading_day": prev_day,
        "risk_data_unavailable_tickers": unavailable,
    }

    previous = load_risk_state(state_path, today_kst=today_kst)
    changes = compute_risk_changes(selected=selected, previous=previous)
    out.changes = changes
    out.diagnostics["risk_state_fallback"] = changes.fallback
    out.diagnostics["risk_new_count"] = len(changes.new)
    out.diagnostics["risk_worsened_count"] = len(changes.worsened)
    out.diagnostics["risk_suppressed_count"] = len(changes.suppressed)
    if changes.fallback and logger is not None:
        logger.info(
            "위험 상태 비교 불가/초기화 (%s) — 선정분 전체 신규", changes.fallback
        )

    # 저장할 entries 는 **발송 여부와 무관하게** 계산해 둔다. 실제 저장은 러너가
    # 발송 성공 뒤에만 한다.
    out.save_entries = merge_worst(selected=selected, previous=previous)

    if not changes.has_send:
        # 신규·악화 없음 — 완화·해소·동일 구간은 발송하지 않는다.
        out.skip_reason = "no_new_or_worsened"
        return out

    out.message_text = render_risk_alert(
        changes,
        slot_label=slot_label_from_runtime(runtime_kst),
        held_ticker_count=len(tickers),
        quote_asof=format_quote_asof(runtime_kst),
        base_close_date=prev_day,
        unavailable=out.unavailable,
    )
    return out


def check_risk_preconditions(
    *,
    market_quotes: dict[str, Any],
    price_refresh_diag: dict[str, Any],
    today_kst: str,
    logger: Any = None,
) -> tuple[bool, dict[str, Any], str, Optional[str]]:
    """비거래일·완전성 가드. **OPS-01A 것을 그대로 재사용**한다.

    반환: `(비거래일 skip 여부, evidence, reason, 차단 detail|None)`
    """
    skip_ntd, evidence, reason = check_non_trading_day(
        market_quotes=market_quotes or {},
        today_kst=today_kst,
        price_refresh_diag=price_refresh_diag,
        logger=logger,
    )
    blocked = check_incomplete_without_today(
        market_quotes=market_quotes or {},
        today_kst=today_kst,
        skip_non_trading_day=skip_ntd,
        non_trading_day_reason=reason,
        target_tickers=price_refresh_diag.get("target_tickers") or (),
        logger=logger,
    )
    return skip_ntd, evidence, reason, blocked


@dataclass
class RiskAssembly:
    """러너 §3-d 의 결과. `fail` 이 있으면 러너가 `_finish(*fail)` 한다."""

    outcome: Optional[HoldingsRiskOutcome] = None
    skip_non_trading_day: bool = False
    diagnostics: dict[str, Any] = field(default_factory=dict)
    fail: Optional[tuple[str, str, str]] = None
    message_text: str = ""


def assemble_holdings_risk_push(
    *,
    market_quotes: dict[str, Any],
    price_refresh_diag: dict[str, Any],
    today_kst: str,
    state_path: Path,
    runtime_kst: Optional[str],
    holdings_loader: Callable[[], list[Any]],
    fetch_history: Callable[..., list[tuple[str, float]]],
    logger: Any = None,
) -> RiskAssembly:
    """러너 §3-d 전체 — 비거래일·완전성 가드 → 선정·변화·본문 조립.

    러너가 KS-10 임계를 넘지 않도록 옮겼다. **판정 순서는 그대로다**:
    비거래일·완전성이 선정보다 앞선다. skip **결정**은 여기서 하지 않고
    러너가 flag guard 뒤(§6-c)에서 판단한다.
    """
    out = RiskAssembly()
    skip_ntd, ntd_evidence, ntd_reason, blocked = check_risk_preconditions(
        market_quotes=market_quotes or {},
        price_refresh_diag=price_refresh_diag,
        today_kst=today_kst,
        logger=logger,
    )
    out.skip_non_trading_day = skip_ntd
    out.diagnostics["non_trading_day_evidence"] = ntd_evidence
    out.diagnostics["non_trading_day_reason"] = ntd_reason

    if blocked is not None:
        out.fail = ("failed", "holdings_quotes_incomplete_no_today", blocked)
        return out
    if skip_ntd:
        return out

    outcome = build_holdings_risk_alert(
        holdings_loader=holdings_loader,
        fetch_history=fetch_history,
        market_quotes=market_quotes or {},
        state_path=state_path,
        runtime_kst=runtime_kst,
        today_kst=today_kst,
        logger=logger,
    )
    out.outcome = outcome
    out.diagnostics.update(outcome.diagnostics)
    if outcome.error:
        if logger is not None:
            logger.error("위험 알림 조립 실패: %s", outcome.error)
        out.fail = ("failed", "holdings_risk_error", outcome.error[:400])
        return out
    out.message_text = outcome.message_text
    return out
