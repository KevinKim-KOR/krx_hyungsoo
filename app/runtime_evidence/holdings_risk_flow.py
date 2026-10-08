"""POC3-OPS-02A — 위험 알림 흐름 조립 (러너에서 분리).

흐름: 보유 원장 → 가격 이력·거래일 축 → 선정 → 이전 상태 → 변화 판정 → 본문

**발송 진척 상태는 여기서 전진시키지 않는다.** 러너가 Telegram 전체 발송 성공을
확인한 뒤에 전진시킨다(OPS-01A 와 같은 계약 — 미발송 악화가 발송 완료로 기록되면
안 된다). 장중(02C-OPS-02)의 **관측 상태**는 여기서 쓸 내용만 정하고, 러너 Gate
를 통과한 회차에 `apply_intraday_records()` 가 쓴다(설계자 D3).

비거래일 판정·완전성 가드는 **OPS-01A 것을 그대로 재사용**한다. 신규 발명 금지.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from app.runtime_evidence.holdings_price_basis import (
    PriceBasisSource,
    load_basis_history,
)
from app.runtime_evidence.holdings_risk import (
    RiskTicker,
    previous_trading_day,
    select_risk_holdings,
)
from app.runtime_evidence.holdings_risk_render import render_risk_alert
from app.runtime_evidence.holdings_risk_state import (
    LoadedRiskState,
    RiskChangeSet,
    compute_risk_changes,
    load_risk_state,
    merge_worst,
)
from app.runtime_evidence.holdings_selection_flow import (
    REASON_NO_HOLDINGS,
    check_incomplete_without_today,
    check_non_trading_day,
    format_quote_asof,
    should_skip_no_holdings,
)
from app.runtime_evidence.holdings_selection_source import (
    average_buy_prices,
    load_holding_rows,
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
    # POC3-02D-OPS-01 C4 — `save_entries` 를 만든 **이전 상태**. 통합 본문이 보유
    # 급락을 구역 상한에서 자르면 같은 이전 상태로 저장 대상을 다시 계산한다.
    previous_state: Optional[LoadedRiskState] = None
    # POC3-02C-OPS-02 — 장중 조립이 재계산 없이 쓰기 위해 그대로 넘긴다.
    holding_rows: list[dict[str, Any]] = field(default_factory=list)
    changes: Any = None
    today_kst: Optional[str] = None
    # (ticker, 종목명) — 본문 `데이터 확인 필요` 그룹에 그대로 실린다.
    unavailable: list[tuple[str, str]] = field(default_factory=list)
    # POC5-01B — 평가한 전 보유 종목의 이미 계산된 값(원장 기록용 · diagnostics 미포함).
    evaluated: list[dict[str, Any]] = field(default_factory=list)


def build_holdings_risk_alert(
    *,
    holdings_loader: Callable[[], list[Any]],
    fetch_history: Callable[..., list[tuple[str, float]]],
    market_quotes: dict[str, Any],
    state_path: Path,
    runtime_kst: Optional[str],
    today_kst: Optional[str] = None,
    logger: Any = None,
    calendar_dir: Optional[Path] = None,
    price_basis_source: Optional[PriceBasisSource] = None,
) -> HoldingsRiskOutcome:
    """선정 → 변화 판정 → 본문. 예외는 `error` 로 돌려 러너가 failed 처리한다.

    POC3-02D-OPS-03 — 거래일 축은 캘린더다(`trading_day_axis` · 확정 계약 10).
    `직전 종가` 날짜(= 네이버 전일 대비의 기준일)와 `고점 대비` 20거래일 구간이
    배치 실패일에 하루 밀리지 않는다 — 그 구간 종가가 빠지면 보조값만 생략된다.

    `고점 대비` 구간 종가는 자산 유형별 한 계열이다(설계자 RESULT STEP 1 ·
    `holdings_price_basis`). 급락 판정(Naver 등락률)은 그대로다.
    """
    out = HoldingsRiskOutcome(today_kst=today_kst)
    try:
        holding_rows = load_holding_rows(holdings_loader)
        tickers = sorted({r["ticker"] for r in holding_rows})
        basis = load_basis_history(
            tickers,
            fetch_history=fetch_history,
            market_quotes=market_quotes or {},
            today_kst=today_kst,
            calendar_dir=calendar_dir,
            source=price_basis_source,
        )
        axis_dates = basis.axis
        prev_day = previous_trading_day(axis_dates, today_kst)
        evaluated: list[dict[str, Any]] = []
        selected, unavailable = select_risk_holdings(
            holdings=holding_rows,
            price_history=basis.history,
            market_quotes=market_quotes or {},
            today_kst=today_kst,
            axis_dates=axis_dates,
            avg_buy_prices=average_buy_prices(holding_rows),
            evaluated=evaluated,
        )
    except Exception as e:  # noqa: BLE001
        out.error = f"{type(e).__name__}: {str(e)[:200]}"
        return out

    out.selected = selected
    out.evaluated = evaluated
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
        # 설계자 RESULT STEP 1-5 — 종목별 자산 유형 · price_source · price_basis.
        "risk_price_basis": basis.evidence,
    }

    previous = load_risk_state(state_path, today_kst=today_kst)
    out.previous_state = previous
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
    """러너 §3-d 의 결과. `fail` 이 있으면 러너가 `_finish(*fail)` 한다.

    `intraday` 는 **통합 본문이 구 본문을 대체한 회차에만** 채운다(POC3-02D-OPS-02
    Q2). 러너는 이 값으로 전송 성공 뒤 장중 발송 진척을 저장하므로, 통합 본문이
    나가지 않는 회차(정책 비활성 · 일일 상한 · 신호 없음 · 조립 뒤 예외)는 `None`
    이다.
    """

    outcome: Optional[HoldingsRiskOutcome] = None
    skip_non_trading_day: bool = False
    diagnostics: dict[str, Any] = field(default_factory=dict)
    fail: Optional[tuple[str, str, str]] = None
    message_text: str = ""
    # 러너 Gate(§5 dry-run · §6 flag · §7 duplicate)를 통과한 **뒤에만** 쓸
    # 관측·집계 내용. 조립 단계에서 바로 쓰면 dry-run 만 돌려도 라이브 파일이
    # 바뀐다(설계자 D3). `None` 이면 쓸 것이 없다(정책 비활성·조립 실패).
    intraday_records: Optional[dict[str, Any]] = None
    # POC5-01B — 원장이 읽는 장중 조립 결과(일일 상한 · 신호 없음 회차 포함 · 같은 객체).
    # `intraday`(본문 대체 회차만 · 발송 진척 저장용)와 뜻이 다르다. 격리 경로는 None.
    intraday_eval: Any = None


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
    calendar_dir: Optional[Path] = None,
    price_basis_source: Optional[PriceBasisSource] = None,
) -> RiskAssembly:
    """러너 §3-d 전체 — 비거래일·완전성 가드 → 선정·변화·본문 조립.

    러너가 KS-10 임계를 넘지 않도록 옮겼다. **판정 순서는 그대로다**:
    비거래일·완전성이 선정보다 앞선다. skip **결정**은 여기서 하지 않고
    러너가 flag guard 뒤(§6-c)에서 판단한다. 정상 빈 보유 + 대표 0 은 그 앞에서
    `no_holdings` 로 끝난다(POC5-05 Q-A).
    """
    out = RiskAssembly()
    # POC5-05 Q-A — 정상 빈 보유(전량매도): 사업군 대표가 있으면 조회 대상이 대표라
    # 아래 기존 경로(가드 · 선정 · 장중 조립)를 그대로 탄다(보유 행 0). 대표도 없으면
    # 조회 대상이 0 이라 가드가 성립하지 않는다 → **가드 앞에서** `no_holdings` skip
    # 지시. 판정은 러너 §6-c(`skip_reason` · 본문 없음). 파일 없음 · 손상은 여기서
    # 걸리지 않는다.
    if should_skip_no_holdings(price_refresh_diag, holdings_loader):
        out.outcome = HoldingsRiskOutcome(
            today_kst=today_kst,
            skip_reason=REASON_NO_HOLDINGS,
            diagnostics={
                "risk_holdings_loaded_count": 0,
                "risk_unique_ticker_count": 0,
                "risk_selected_count": 0,
            },
        )
        out.diagnostics.update(out.outcome.diagnostics)
        return out

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
        calendar_dir=calendar_dir,
        price_basis_source=price_basis_source,
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
            # POC3-02D-OPS-01 C3 — 실행 시각(헤더 HH:MM · 구 본문 '시세' 와 같은 값).
            # 전에는 채우는 곳이 없는 진단 키를 읽어 늘 `현재가 —` 가 나갔다(사용자
            # 실수신 원문 2026-09-27 확인 · 설계자 R2 Q9 (a)).
            quote_asof=format_quote_asof(runtime_kst),
            base_close_date=outcome.diagnostics.get("risk_prev_trading_day"),
            logger=logger,
            calendar_dir=calendar_dir,
        )
        out.intraday_eval = intraday
        # POC3-02D-OPS-01 C4 — 저장 대상을 **본문에 실린 것** 기준으로 다시 계산한다.
        # 구역 상한에 잘린 보유 급락을 worst 로 저장하면 한 번도 안 나간 신호가
        # 그날 억제되고(신규), 악화 알림이 사라진다(OPS-02A · 설계 §14-2).
        # 이번 회차 보낼 대상이 아니던 선정분(억제분)은 그대로 넣는다.
        #
        # 여기서 예외가 나면 아래 격리 경로가 되어 구 본문 + 위험 상태 전체
        # 저장이고, 사업군 발송 상태·관측·집계는 쓰지 않는다(OPS-02 Q2).
        carried_save: Optional[dict[str, dict[str, Any]]] = None
        if intraday.will_send() and not intraday.daily_cap_reached:
            carried = {getattr(i, "ticker", None) for i in intraday.plan.held_drop}
            pending_drop = {i.ticker for i in held_drop}
            carried_save = merge_worst(
                selected=[
                    i
                    for i in outcome.selected
                    if i.ticker in carried or i.ticker not in pending_drop
                ],
                previous=outcome.previous_state,
            )
        # `out.intraday` 는 여기서 대입하지 **않는다**(OPS-02 Q2) — 아래 본문 대체
        # 분기에서만 대입한다. 전에는 여기서 대입해, 이 아래(진단 갱신 · 회차 결과
        # 분류)에서 예외가 나 구 본문만 나가도 사업군·급등 신호가 발송 완료로
        # 기록됐다(OPS-01 결과서 §8 결함 2).
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
        # 잠정값이고, `apply_intraday_records()` 가 최종 status 로 확정한다(C5).
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
            # POC3-02D-OPS-03 확정 계약 13 — 추세 기준일(T-1) 미확인으로 진입 검토
            # 구역을 뺀 회차. 15:40 요약에 센다(틱마다 따로 경고하지 않는다).
            out.intraday_records["entry_omitted"] = bool(intraday.sector.entry_omitted)
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
            # 발송 진척 저장 대상은 **이 분기에서만** 넘긴다(OPS-02 Q2 · 계약 7·8).
            # 러너는 전체 전송 성공 뒤 `intraday.sent_signals`(본문에 실린 것)만
            # 발송 완료로 기록한다(`runner_evidence`).
            out.intraday = intraday
            # C4 — 러너는 `outcome`(`_rasm.outcome`)의 `save_entries` 를 저장한다.
            # `out`(`RiskAssembly`)에 넣으면 새 속성만 붙고 저장에 반영되지 않는다.
            if carried_save is not None:
                outcome.save_entries = carried_save
    except Exception as e:  # noqa: BLE001 - 보유 경로를 절대 막지 않는다
        if logger is not None:
            logger.warning("장중 조립 실패(격리): %s", e)
        out.diagnostics["intraday_error"] = f"{type(e).__name__}: {str(e)[:200]}"
        # OPS-02 Q2 — 구 본문만 나가는 회차다. 조립 뒤 어느 지점에서 터졌든 장중
        # 발송 진척 · 관측 · 집계를 쓰지 않는다(조립 전 예외와 같은 경로). 보유
        # 급락 D* 는 구 본문 기준(`save_entries` 전체)으로 전송 성공 뒤에만 저장된다.
        out.intraday = None
        out.intraday_records = None
        out.intraday_eval = None
    # POC3-02D-OPS-01 C6 — 조립된 최종 본문(통합 또는 구 본문)의 **분할 전** 길이.
    # 이 종류는 legacy evidence 단계를 건너뛰어 러너 초기값 0 이 남았다. 뜻은
    # 다른 종류와 같다(`holdings_selection_flow`). 발송 여부는 status 로 본다.
    out.diagnostics["message_text_length"] = len(out.message_text)
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
        from app.runtime_evidence.intraday_checkup_tally import (
            OUTCOME_SEND_FAILED,
            OUTCOME_SENT,
            record_tick,
        )

        # POC3-02D-OPS-01 C5 — 회차 결과를 **최종 status** 로 확정한다. 조립 시점
        # 값은 잠정값이다. pending 이 있는 failed 는 조립 뒤 발송 전 출구 4곳
        # (금지 문구 · raw 식별자 · registry 손상 · Telegram 실패 — 실제 부분
        # 전송도 `sent=False`)뿐이다. 잠정값(`신호 없음`·`조회 실패`)으로 두면
        # 발송 실패가 숨는다. 부분 전송 성공은 발송 완료가 아니므로 잠정값 유지.
        tick_outcome = pending["tick_outcome"]
        if status == "failed":
            tick_outcome = OUTCOME_SEND_FAILED
        elif status == "sent" and not record.get("partial_delivery"):
            tick_outcome = OUTCOME_SENT
        record_tick(
            pending["tally_path"],
            today_kst=pending["today_kst"],
            outcome=tick_outcome,
            at_kst=pending.get("runtime_kst"),
            entry_omitted=bool(pending.get("entry_omitted")),
        )
        record["intraday_tally_outcome"] = tick_outcome
    except Exception as e:  # noqa: BLE001
        record["intraday_tally_error"] = f"{type(e).__name__}"
