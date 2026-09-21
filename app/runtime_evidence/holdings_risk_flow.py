"""POC3-OPS-02A — 위험 알림 흐름 조립 (러너에서 분리).

흐름: 보유 원장 → 가격 이력·거래일 축 → 선정 → 이전 상태 → 변화 판정 → 본문

**발송 진척 상태는 여기서 전진시키지 않는다.** 러너가 Telegram 전체 발송 성공을
확인한 뒤에 전진시킨다(OPS-01A 와 같은 계약 — 미발송 악화가 발송 완료로 기록되면
안 된다). 장중(OPS-02)의 **관측 상태**는 여기서 매 회차 저장한다(설계 §15-2).

비거래일 판정·완전성 가드는 **OPS-01A 것을 그대로 재사용**한다. 신규 발명 금지.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
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
    # POC3-02C-OPS-02 — 장중 조립이 재계산 없이 쓰기 위해 그대로 넘긴다.
    holding_rows: list[dict[str, Any]] = field(default_factory=list)
    changes: Any = None
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
    out.holding_rows = holding_rows
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


_KST = timezone(timedelta(hours=9))

# 조건형 일일 상한 도달 — `holdings_risk_alert` **전체**를 막는다(설계 §6).
REASON_DAILY_CAP_BLOCKED = "intraday_daily_cap_reached"

DEFAULT_TALLY_PATH = Path("state/three_push/intraday_checkup_tally_latest.json")

DEFAULT_SECTOR_STATE_PATH = Path("state/three_push/sector_signal_state_latest.json")


def _now_kst(runtime_kst: Optional[str]) -> datetime:
    """실행 시각. 없거나 깨졌으면 현재 KST."""
    if runtime_kst:
        try:
            dt = datetime.fromisoformat(runtime_kst)
            return dt if dt.tzinfo else dt.replace(tzinfo=_KST)
        except ValueError:
            pass
    return datetime.now(_KST)


def _slot_label(runtime_kst: Optional[str]) -> str:
    """`10:30` 형식. 못 읽으면 빈 문자열 — 제목만 나간다."""
    try:
        return _now_kst(runtime_kst).strftime("%H:%M")
    except Exception:  # noqa: BLE001
        return ""


@dataclass
class RiskAssembly:
    intraday: Any = None
    """러너 §3-d 의 결과. `fail` 이 있으면 러너가 `_finish(*fail)` 한다."""

    outcome: Optional[HoldingsRiskOutcome] = None
    skip_non_trading_day: bool = False
    diagnostics: dict[str, Any] = field(default_factory=dict)
    fail: Optional[tuple[str, str, str]] = None
    message_text: str = ""
    # 러너 Gate(§5 dry-run · §6 flag · §7 duplicate)를 통과한 **뒤에만** 쓸
    # 관측·집계 내용. 조립 단계에서 바로 쓰면 dry-run 만 돌려도 라이브 파일이
    # 바뀐다(설계자 D3). `None` 이면 쓸 것이 없다(정책 비활성·조립 실패).
    intraday_records: Optional[dict[str, Any]] = None


def assemble_holdings_risk_push(
    *,
    market_quotes: dict[str, Any],
    price_refresh_diag: dict[str, Any],
    today_kst: str,
    state_path: Path,
    runtime_kst: Optional[str],
    holdings_loader: Callable[[], list[Any]],
    fetch_history: Callable[..., list[tuple[str, float]]],
    sector_state_path: Optional[Path] = None,
    tally_path: Optional[Path] = None,
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

    # ── POC3-02C-OPS-02 배선 (설계자 §14-2) ─────────────────────────────────
    #
    # 보유 급락은 **이미 위에서 끝났다.** 그 결과(`changes.new + worsened`)를
    # 받아 급등·사업군과 합친다. 장중 조립이 어떤 이유로든 실패하거나 정책이
    # 비활성이면 **위에서 만든 기존 본문을 그대로 쓴다** — 보유 경로를 막지
    # 않는다(설계 §9).
    try:
        from app.runtime_evidence.intraday_alert_flow import assemble_intraday_alert

        held_drop = list(outcome.changes.new) + [i for i, _ in outcome.changes.worsened]
        intraday = assemble_intraday_alert(
            held_drop=held_drop,
            holding_rows=outcome.holding_rows,
            market_quotes=market_quotes or {},
            today_kst=today_kst,
            now_kst=_now_kst(runtime_kst),
            state_path=sector_state_path or DEFAULT_SECTOR_STATE_PATH,
            slot_label=_slot_label(runtime_kst),
            quote_asof=outcome.diagnostics.get("risk_quote_asof"),
            base_close_date=outcome.diagnostics.get("risk_prev_trading_day"),
            logger=logger,
        )
        out.intraday = intraday
        out.diagnostics.update(intraday.diagnostics)

        # 관측 상태는 **여기서 쓰지 않는다**(설계자 D3). dry-run · flag-off ·
        # duplicate 회차가 라이브 파일을 바꾸면 안 되는데, 그 Gate 는 러너의
        # §5~§7 이라 조립보다 뒤다. 그래서 "무엇을 쓸지" 만 담아 두고, 러너가
        # Gate 를 통과한 뒤 `apply_intraday_records()` 로 실제로 쓴다.
        if intraday.diagnostics.get("intraday_policy_enabled"):
            out.intraday_records = {
                "sector_state_path": sector_state_path or DEFAULT_SECTOR_STATE_PATH,
                "tally_path": tally_path or DEFAULT_TALLY_PATH,
                "today_kst": str(today_kst or ""),
                "observed": list(intraday.observed or []),
                "unevaluable": set(intraday.unevaluable or set()),
                "runtime_kst": runtime_kst,
            }
        if intraday.skip_reason:
            out.diagnostics["intraday_skip_reason"] = intraday.skip_reason
        # 회차 집계 — **보내지 않은 회차도 센다**(설계 §8). 판정만 여기서 하고
        # 기록은 러너 Gate 뒤다(위와 같은 이유). 전송 성공 여부는 아직 모르므로
        # 잠정값이고, 성공하면 `mark_last_tick_sent` 가 정정한다.
        if out.intraday_records is not None:
            from app.runtime_evidence.intraday_checkup_tally import (
                OUTCOME_FAILED,
                OUTCOME_NO_SIGNAL,
                OUTCOME_SUPPRESSED,
            )

            # 조회 실패 — 사업군 경로가 터졌거나 커버리지가 무너졌거나 provider
            # 가 내려간 회차다. `신호 없음` 과 구분해야 §8 의 `조회 실패 N회` 가
            # 나온다(검증자 지적 — 생산 경로가 없었다). 평가 불가 회차도 정상
            # 스케줄의 운영 회차이므로 **실패 1회로 남는다**(설계자 D2).
            failed = (
                bool(intraday.sector_error)
                or intraday.sector.provider_down
                or (
                    intraday.sector.sector_count > 0 and not intraday.sector.coverage_ok
                )
            )
            suppressed = bool(
                (intraday.changes and intraday.changes.suppressed)
                or (intraday.surge_changes and intraday.surge_changes.suppressed)
                or intraday.daily_cap_reached
            )
            # `outcome` 이라는 이름을 쓰지 않는다 — 바깥의 `HoldingsRiskOutcome`
            # 을 덮어 `skip_reason` 대입이 문자열에 꽂힌다(실측으로 잡았다).
            if failed:
                tick_outcome = OUTCOME_FAILED
            elif suppressed and not intraday.will_send():
                tick_outcome = OUTCOME_SUPPRESSED
            else:
                tick_outcome = OUTCOME_NO_SIGNAL
            out.intraday_records["tick_outcome"] = tick_outcome
            # 평가 불가 범위는 관측에서 제외 — 회복으로 기록하지 않는다(D2).
            out.intraday_records["unevaluable"] = set(intraday.unevaluable or set())
        if intraday.daily_cap_reached and outcome is not None:
            # 설계 §6 — 조건형 일일 상한 4건. `holdings_risk_alert` **자체가**
            # 조건형이므로 상한에 걸리면 보유 급락 본문도 나가지 않는다.
            # 기존 본문을 그대로 두면 "이후 조건형 억제" 계약이 깨진다.
            out.message_text = ""
            # 러너의 기존 skip 분기(`skip_reason and not message_text`)를 타게
            # 한다 — 러너를 고치지 않고 상한을 강제하는 유일한 지점이다.
            outcome.skip_reason = REASON_DAILY_CAP_BLOCKED
            out.diagnostics["intraday_blocked_legacy_body"] = True
        elif intraday.will_send():
            # 통합 본문이 기존 본문을 **대체**한다. 보유 급락 내용은 그 안에
            # 「보유종목」 구역으로 들어가 있다.
            out.message_text = intraday.message_text
    except Exception as e:  # noqa: BLE001 - 보유 경로를 절대 막지 않는다
        if logger is not None:
            logger.warning("장중 조립 실패(격리): %s", e)
        out.diagnostics["intraday_error"] = f"{type(e).__name__}: {str(e)[:200]}"
    return out


# 러너 Gate 를 통과한 회차만 라이브 파일을 바꾼다(설계자 D3).
#
# ```text
# mode = send  AND  정책 enabled  AND  PUSH_AUTOSEND_*  AND  duplicate 아님
# ```
#
# 이 중 하나라도 어긋나면 `sector_signal_state_latest.json` 과
# `intraday_checkup_tally_latest.json` 을 **건드리지 않는다.** dry-run 은 메시지를
# 계산·표시할 수 있지만 라이브 상태를 바꾸면 안 되고, duplicate 회차를 세면
# 15:40 의 "장중 점검 N회" 가 같은 틱을 두 번 센다.
BLOCKED_RECORD_REASONS = frozenset(
    {"autosend_disabled", "push_kind_disabled", "duplicate_runtime"}
)


# 조립이 러너 `record` 에 pending 을 실어 두는 키. `apply_intraday_records()` 가
# 직렬화 전에 꺼내 **지운다** — 경로·set 이 섞여 있어 JSON 으로 나가면 안 된다.
PENDING_KEY = "_intraday_pending"


def apply_intraday_records(
    record: dict[str, Any],
    *,
    mode: str,
    status: str,
    reason: Optional[str],
) -> None:
    """관측·집계를 **실제로** 쓴다. 러너의 모든 종료 지점에서 한 번 호출된다.

    쓰기 실패가 발송 결과를 뒤집으면 안 되므로 예외를 삼키고 진단만 남긴다.
    """
    pending = record.pop(PENDING_KEY, None)
    if not pending:
        return
    if mode != "send" or status == "dry_run_success":
        record["intraday_records_skipped"] = "dry_run" if mode != "send" else status
        return
    if reason in BLOCKED_RECORD_REASONS:
        record["intraday_records_skipped"] = reason
        return
    try:
        from app.runtime_evidence.sector_signal_state import save_observation

        save_observation(
            pending["sector_state_path"],
            observed=list(pending.get("observed") or []),
            today_kst=pending["today_kst"],
            unevaluable=set(pending.get("unevaluable") or set()),
        )
        record["intraday_observation_saved"] = len(pending.get("observed") or [])
        record["intraday_observation_preserved"] = len(pending.get("unevaluable") or [])
    except Exception as e:  # noqa: BLE001 - 발송 결과를 뒤집지 않는다
        record["intraday_observation_error"] = f"{type(e).__name__}"
    try:
        from app.runtime_evidence.intraday_checkup_tally import record_tick

        record_tick(
            pending["tally_path"],
            today_kst=pending["today_kst"],
            outcome=pending["tick_outcome"],
            at_kst=pending.get("runtime_kst"),
        )
        record["intraday_tally_outcome"] = pending["tick_outcome"]
    except Exception as e:  # noqa: BLE001
        record["intraday_tally_error"] = f"{type(e).__name__}"
