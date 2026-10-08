"""POC3-OPS-01A — 보유 브리핑 선정·변화 판정 흐름 (러너에서 분리).

러너(`scripts/run_three_push_runtime_oci.py`)가 KS-10 임계(650줄)를 넘지 않도록
보유 브리핑 전용 분기를 여기로 옮긴다. 정책 판정은 그대로 두고 **조립만** 한다.

흐름 (PLAN §3 · §4):
  보유 원장 로드 → 가격 이력 로드 → 선정 → 이전 상태 로드 → 변화 판정
  → 본문 렌더. 전체 발송 조건(OPEN · 변화 없음 · 비교 불가)에서 선정 0건이면
    `no_selection` skip 지시 · 변화 없음이면 현재 상태 전체 · MIDDAY·CLOSE 에서
    빠진 종목은 '정상 해소' 변화분으로 보낸다.

변화 없음 skip(`no_change`)은 2026-09-18 운영분까지 적용 · 2026-09-18 밤
`02C-OPS-01` OCI 반영으로 폐지(새 계약 첫 운영일 2026-09-21). 같은 날짜·같은 슬롯 재실행은 registry 가 막는다.

**상태 저장은 여기서 하지 않는다.** 러너가 Telegram 전체 발송 성공을 확인한 뒤에
저장한다 (PLAN §4.6 — 미발송 신호가 발송 완료로 기록되면 안 된다).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from app.runtime_evidence.holdings_price_basis import (
    PriceBasisSource,
    load_basis_history,
)
from app.runtime_evidence.holdings_selection import (
    LOOKBACK_TRADING_DAYS,
    SelectedTicker,
    reference_trading_day,
    select_holdings,
)
from app.runtime_evidence.holdings_selection_render import render_changes, render_full
from app.runtime_evidence.holdings_selection_source import (
    average_buy_prices,
    load_holding_rows,
)
from app.runtime_evidence.holdings_selection_state import (
    ChangeSet,
    compute_changes,
    load_state,
)

FIRST_SLOT_ID = "OPEN"
# 15:40 슬롯 — 장중 점검 요약이 여기 붙는다(POC3-02C-OPS-02 §8).
LAST_SLOT_ID = "CLOSE"

# 슬롯 → 화면 표기 시각 (cron 과 동일). 확정 계약이 `09:15/12:30/15:40` 이라
# 내부 식별자(`OPEN`)를 그대로 헤더에 노출하지 않는다.
SLOT_TIME_LABEL = {"OPEN": "09:15", "MIDDAY": "12:30", "CLOSE": "15:40"}


# POC5-05 Q-A — 정상 빈 보유(전량매도) skip 사유. 보유 브리핑 · 위험 알림(대표 0) 공용.
REASON_NO_HOLDINGS = "no_holdings"


def should_skip_no_holdings(
    price_refresh_diag: dict[str, Any], holdings_loader: Callable[[], list[Any]]
) -> bool:
    """조회 대상 0 이 **정상 빈 보유** 때문인가 (POC5-05 Q-A).

    셋 다 맞을 때만 True — 이번 실행의 조회 대상이 0 · 보유 파일이 있다 · loader 가
    `[]` 를 돌려준다. `holdings.load()` 는 파일 없음도 `[]` 라 파일 존재로 구분한다.

    파일 없음 · 손상 · 조회 실패는 False 다 — 정상 빈 보유로 숨기지 않고 기존 경로
    (완전성 가드 · 조립 실패)가 그대로 실패로 끝낸다. 조회 대상이 있으면 loader 를
    부르지 않는다 — 비어 있지 않은 보유 · 대표가 있는 위험 알림은 동작이 그대로다.
    """
    if price_refresh_diag.get("target_tickers"):
        return False
    from app import holdings as _holdings_mod

    if not _holdings_mod.HOLDINGS_FILE.exists():
        return False
    try:
        return len(holdings_loader()) == 0
    except Exception:  # noqa: BLE001 - 손상 · 조회 실패는 정상 빈 보유가 아니다
        return False


def slot_label_for(slot_id: Optional[str]) -> str:
    return SLOT_TIME_LABEL.get(slot_id or "", "")


def format_quote_asof(runtime_kst: Optional[str]) -> Optional[str]:
    """ISO-8601 → `YYYY-MM-DD HH:MM`. 확정 헤더 형식."""
    if not runtime_kst or len(runtime_kst) < 16:
        return runtime_kst
    return f"{runtime_kst[:10]} {runtime_kst[11:16]}"


def check_non_trading_day(
    *,
    market_quotes: dict[str, Any],
    today_kst: str,
    price_refresh_diag: dict[str, Any],
    logger: Any = None,
) -> tuple[bool, dict[str, Any], str]:
    """비거래일 판정 (PLAN §9). 반환 `(skip 여부, evidence, reason)`.

    신규 휴장일 캘린더·신규 외부 조회 없음. 이미 가져온 quote 의 `price_asof`
    하나만 본다. 완전성은 **고유 ticker 집합 일치**로 본다 (설계자 확정
    2026-09-05) — 보유는 행 수(32)와 고유 ticker 수(29)가 달라 건수 비교가
    성립하지 않는다.
    """
    from app.three_push_runtime.non_trading_day import detect_non_trading_day

    result = detect_non_trading_day(
        market_quotes or {},
        today_kst=today_kst,
        target_tickers=price_refresh_diag.get("target_tickers") or (),
        success_tickers=price_refresh_diag.get("success_tickers") or (),
        failed_tickers=price_refresh_diag.get("failed_tickers") or (),
    )
    if result.is_non_trading_day and logger is not None:
        logger.info(
            "비거래일 판정 — 발송 skip (quote %d건 전부 %s 체결)",
            result.quote_count,
            result.max_price_asof,
        )
    return result.is_non_trading_day, result.evidence(), result.reason


@dataclass
class HoldingsSelectionOutcome:
    """러너가 그대로 쓸 수 있는 결과.

    `skip_reason` 이 있으면 러너는 그 사유로 skip 한다 (Telegram 미호출).
    `save_state_on_send` 가 True 면 발송 성공 후 상태를 저장한다.
    """

    message_text: str = ""
    selected: list[SelectedTicker] = field(default_factory=list)
    changes: Optional[ChangeSet] = None
    diagnostics: dict[str, Any] = field(default_factory=dict)
    skip_reason: Optional[str] = None
    save_empty_state: bool = False
    save_state_on_send: bool = False
    error: Optional[str] = None
    # POC5-01B — 평가한 전 종목의 이미 계산된 값(원장 기록용 · diagnostics 미포함).
    observations: list[dict[str, Any]] = field(default_factory=list)


def build_holdings_selection(
    *,
    holdings_loader: Callable[[], list[Any]],
    fetch_history: Callable[..., list[tuple[str, float]]],
    market_quotes: dict[str, Any],
    state_path: Path,
    slot_id: Optional[str],
    runtime_kst: Optional[str],
    today_kst: Optional[str] = None,
    logger: Any = None,
    calendar_dir: Optional[Path] = None,
    price_basis_source: Optional[PriceBasisSource] = None,
) -> HoldingsSelectionOutcome:
    """선정 → 변화 판정 → 본문. 예외는 `error` 로 돌려 러너가 failed 처리한다.

    20거래일 기준일은 **거래일 캘린더**로 정한다(POC3-02D-OPS-03 확정 계약 10 ·
    `trading_day_axis`). 저장 가격 축을 쓰면 배치 실패일에 21거래일 전이 된다.

    과거 종가는 자산 유형별 한 계열이다(설계자 RESULT STEP 1 · `holdings_price_basis`):
    ETF = KRX 무조정 · 개별주 = KRX 공식 종가(POC3-02D-OPS-04 항목 1 · `fetch_history` 는 더 읽지
    않는다). `price_basis_source` 가 없으면 운영 원천(공식 ETF 마스터 CSV · KRX 무조정 ETF 표 ·
    KRX 개별주 표)을 쓴다.
    """
    out = HoldingsSelectionOutcome()
    # 조립 전 구간 전체를 감싼다. 가격 이력 조회 예외가 밖으로 새면 러너의
    # 정상 실패 기록 경로(`_finish("failed", ...)`)를 우회한다 (검증자 지적).
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
        base_day = reference_trading_day(axis_dates, today_kst, LOOKBACK_TRADING_DAYS)
        observations: list[dict[str, Any]] = []
        selected = select_holdings(
            holdings=holding_rows,
            price_history=basis.history,
            market_quotes=market_quotes or {},
            today_kst=today_kst,
            axis_dates=axis_dates,
            avg_buy_prices=average_buy_prices(holding_rows),
            observations=observations,
        )
    except Exception as e:  # noqa: BLE001
        out.error = f"{type(e).__name__}: {str(e)[:200]}"
        return out
    out.selected = selected
    out.observations = observations
    out.diagnostics = {
        "holdings_loaded_count": len(holding_rows),
        "holdings_unique_ticker_count": len(tickers),
        "holdings_selected_count": len(selected),
        # 설계자 확정 — 기준일은 거래일 축에서 고른다. 진단에 남겨 사후 확인 가능.
        # POC3-02D-OPS-03 — 축은 캘린더다(마지막 = 기대 T-1).
        "holdings_base_trading_day": base_day,
        "holdings_trading_day_axis_len": len(axis_dates),
        "holdings_axis_last_trading_day": axis_dates[-1] if axis_dates else None,
        # 설계자 RESULT STEP 1-5 — 종목별 자산 유형 · price_source · price_basis.
        "holdings_price_basis": basis.evidence,
    }

    # 실행일을 **명시로 넘긴다**. 넘기지 않으면 `load_state` 가 실제 오늘 날짜로
    # 비교해, 이 함수가 받은 `today_kst` 와 어긋나면 조용히 `date_mismatch`
    # fallback 이 된다(POC3-02B-OPS-03 작업 중 발견). 운영에서는 두 값이 같아
    # 동작이 바뀌지 않지만, 계약을 코드로 맞춘다.
    previous = load_state(state_path, today_kst=today_kst)
    changes = compute_changes(
        selected=selected,
        previous=previous,
        is_first_slot=(slot_id or FIRST_SLOT_ID) == FIRST_SLOT_ID,
    )
    out.changes = changes
    out.diagnostics["selection_state_fallback"] = changes.fallback
    if changes.fallback and logger is not None:
        logger.warning(
            "이전 상태 비교 불가 (%s) — 전체 현재 상태 발송", changes.fallback
        )

    # 변화가 없어도 **슬롯마다 보낸다** (설계자 2026-09-16 · POC3-02B-OPS-03).
    #
    # 이전 계약은 직전 슬롯과 같으면 `no_change` 로 막았다. 그런데 보유 브리핑은
    # 09:15·12:30·15:40 **정기** PUSH 다. 실측(2026-09-16 MIDDAY)에서 오전과
    # 달라진 게 없다는 이유로 낮 브리핑이 통째로 빠졌다. 사용자는 "낮에도 내
    # 종목이 어떤지" 를 보려고 그 시각을 정한 것이다.
    #
    # 변화가 없으면 **변화분 대신 현재 상태 전체**를 보낸다 — 보낼 내용이
    # 없는 것이 아니라 "달라진 게 없다" 는 것이 오늘의 상태다.
    #
    # 같은 날짜·같은 슬롯 재실행 차단은
    # `registry_key(..., slot_id=...)` 가 이미 한다. 여기서 또 막지 않는다.
    content_unchanged = not changes.has_change
    out.diagnostics["content_unchanged"] = content_unchanged
    send_full = changes.full_send or content_unchanged

    # 선정 0건 — 전달할 내용이 없다. 빈 상태만 저장하고 미발송.
    if send_full and not selected:
        out.skip_reason = "no_selection"
        out.save_empty_state = True
        return out

    slot_label = slot_label_for(slot_id)
    if send_full:
        out.message_text = render_full(
            selected,
            slot_label=slot_label,
            base_close_date=base_day,
            quote_asof=format_quote_asof(runtime_kst),
        )
    else:
        names = {r["ticker"]: r["name"] for r in holding_rows if r.get("ticker")}
        out.message_text = render_changes(
            changes, slot_label=slot_label, resolved_names=names
        )
    # POC3-02C-OPS-02 §8 — **15:40 슬롯 말미에 장중 점검 요약 한 줄.**
    # 별도 메시지를 만들지 않는다. 집계 실패가 브리핑을 막으면 안 되므로
    # 예외를 삼킨다.
    #
    # OPS-03 §1 — **정책이 꺼져 있으면 줄 자체를 붙이지 않는다.**
    # 전에는 활성 여부를 보지 않아, 비활성인데도 집계 파일이 없다는 이유로
    # `장중 점검 확인 불가` 가 매 15:40 브리핑에 붙었다(실측). 그러면 "기능이
    # 꺼짐" 과 "켜져 있는데 집계를 못 읽음" 을 같은 문구로 말하게 된다.
    #
    # ```text
    # 비활성 · NOT_CONFIGURED       줄 없음
    # 활성 + 정상 집계               장중 점검 N회 · 알림 M건 …
    # 활성 + 누락·손상·읽기 실패     장중 점검 확인 불가
    # ```
    if out.message_text and (slot_id or "") == LAST_SLOT_ID:
        try:
            from app.runtime_evidence.holdings_risk_flow import DEFAULT_TALLY_PATH
            from app.runtime_evidence.intraday_alert_flow import (
                active_policy,
                config_read_error,
            )
            from app.runtime_evidence.intraday_checkup_tally import (
                load_tally,
                render_summary_line,
            )

            if active_policy(logger) is None:
                # 설정을 못 읽은 장애는 꺼짐과 구분해 남긴다(설계자 RESULT STEP 2).
                out.diagnostics["intraday_checkup_summary_omitted"] = (
                    "policy_disabled"
                    if config_read_error(logger) is None
                    else "intraday_config_unavailable"
                )
            else:
                line = render_summary_line(
                    load_tally(DEFAULT_TALLY_PATH, today_kst=today_kst)
                )
                if line:
                    out.message_text = f"{out.message_text}\n\n{line}"
                    out.diagnostics["intraday_checkup_summary"] = line
        except Exception as e:  # noqa: BLE001
            out.diagnostics["intraday_checkup_summary_error"] = f"{type(e).__name__}"

    out.diagnostics["message_text_length"] = len(out.message_text)

    # 안전 신호 보존 — 보유 브리핑이 evidence 경로를 타지 않게 되면서
    # `private_fields_exposed` 가 사라지면 개인 값 노출을 아무도 안 본다.
    # 새 본문에 대해 같은 탐지기를 그대로 돌린다.
    try:
        out.diagnostics.update(
            detect_privacy_on_body(out.message_text, holdings_loader=holdings_loader)
        )
    except Exception as e:  # noqa: BLE001
        # 검사 자체가 실패하면 정상으로 통과시키지 않는다.
        out.error = f"privacy_check_failed: {type(e).__name__}: {str(e)[:150]}"
        return out
    out.save_state_on_send = True
    return out


def detect_privacy_on_body(
    message_text: str, *, holdings_loader: Callable[[], list[Any]]
) -> dict[str, Any]:
    """본문에 개인 값·raw 식별자가 들어갔는지.

    **검사 실패는 흐름을 막는다.** 호출부가 예외를 `out.error` 로 바꿔 러너가
    `holdings_selection_error` 로 끝낸다. (이전 docstring 은 "실패해도 흐름을 막지
    않는다" 였는데 실제 동작과 반대였다 — 검증자 r2 지적.)
    """
    from app.runtime_evidence.privacy_detector import (
        detect_private_values_exposed,
        detect_raw_identifier_exposed,
    )

    # **fail-open 금지.** 예외를 False 로 바꾸면 검사 실패가 "노출 없음" 으로
    # 기록돼 안전 신호가 거짓이 된다. 예외는 그대로 올려 러너가 failed 로 끝낸다.
    notes = message_text.splitlines()
    holdings = holdings_loader()
    return {
        "private_fields_exposed": bool(detect_private_values_exposed(holdings, notes)),
        "raw_identifier_exposed": bool(detect_raw_identifier_exposed(notes)),
    }


def today_quote_exists(
    market_quotes: dict[str, Any], today_kst: str, target_tickers: Any
) -> bool:
    """**대상 종목 중** 오늘 체결된 quote 가 하나라도 있는가.

    `target_tickers` 는 **필수**다. 기본값을 두지 않는다 — r5 에서 대상 밖 종목의
    시세가 Fail-Closed 가드를 통과했고(`target={A,B,C}`·`success={A,B,X}` 에서 X 만
    오늘 시세), r6 에서 기본값 `None` 을 남겼더니 인자를 빠뜨린 호출이 **조용히
    그 위험한 동작으로 되돌아갔다**(검증자 B-1). 보유하지도 않은 종목의 체결이
    발송 여부를 정하면 안 되므로, 누락은 조용히 넘기지 않고 **즉시 실패**시킨다.

    Raises:
        ValueError: `target_tickers` 가 None 일 때.
    """
    if target_tickers is None:
        raise ValueError(
            "today_quote_exists: target_tickers 는 필수다. "
            "생략하면 대상 밖 종목의 시세까지 세어 Fail-Closed 가드가 뚫린다."
        )
    target = set(target_tickers)
    for ticker, q in (market_quotes or {}).items():
        if ticker not in target:
            continue
        raw = getattr(q, "price_asof", None)
        if isinstance(raw, str) and raw[:10] == today_kst:
            return True
    return False


def check_incomplete_without_today(
    *,
    market_quotes: dict[str, Any],
    today_kst: str,
    skip_non_trading_day: bool,
    non_trading_day_reason: str,
    target_tickers: Any,
    logger: Any = None,
) -> Optional[str]:
    """ "일부 성공했지만 오늘 quote 0건" → Fail-Closed (설계자 확정 표).

    휴장일인지 조회 장애인지 구분할 수 없다. 미발송 · state 불변.
    반환: 차단해야 하면 사유 detail, 아니면 None.

    `target_tickers` 는 **필수**다. 검증을 **함수 진입부에서** 한다 — 조기 반환
    뒤에 두면 `skip_non_trading_day=True` 와 `reason == "traded_today"` 두 분기가
    `None` 을 그대로 통과시켜, "명시적 None 은 ValueError" 계약이 실제로는 일부
    경로에서만 성립한다(검증자 r7 재현).

    Raises:
        ValueError: `target_tickers` 가 None 일 때.
    """
    if target_tickers is None:
        raise ValueError(
            "check_incomplete_without_today: target_tickers 는 필수다. "
            "생략하면 대상 밖 종목의 시세까지 세어 Fail-Closed 가드가 뚫린다."
        )
    if skip_non_trading_day or non_trading_day_reason == "traded_today":
        return None
    if today_quote_exists(market_quotes, today_kst, target_tickers):
        return None
    if logger is not None:
        logger.error(
            "보유 시세 불완전 + 오늘 체결 quote 0건 — 휴장/장애 구분 불가, 미발송"
        )
    return f"reason={non_trading_day_reason}"


@dataclass
class HoldingsAssembly:
    """러너 §3-c 의 결과. `fail` 이 있으면 러너가 `_finish(*fail)` 한다."""

    outcome: Optional["HoldingsSelectionOutcome"] = None
    skip_non_trading_day: bool = False
    diagnostics: dict[str, Any] = field(default_factory=dict)
    fail: Optional[tuple[str, str, str]] = None
    message_text: str = ""


def assemble_holdings_push(
    *,
    market_quotes: dict[str, Any],
    price_refresh_diag: dict[str, Any],
    today_kst: str,
    state_path: Path,
    slot_id: Optional[str],
    runtime_kst: Optional[str],
    holdings_loader: Callable[[], list[Any]],
    fetch_history: Callable[..., list[tuple[str, float]]],
    logger: Any = None,
    calendar_dir: Optional[Path] = None,
    price_basis_source: Optional[PriceBasisSource] = None,
) -> HoldingsAssembly:
    """보유 브리핑 §3-c 전체 — 비거래일 판정 → 완전성 가드 → 선정·본문 조립.

    러너가 KS-10 임계를 넘지 않도록 옮겼다. **판정 순서는 그대로다**:
    비거래일 판정이 선정보다 앞선다(휴장일에 정상 종목을 데이터 지연으로 분류하지
    않기 위해). skip **결정**은 여기서 하지 않고 `skip_non_trading_day` 로 돌려
    러너가 enable flag guard 뒤(§6-c)에서 판단한다. 정상 빈 보유는 그 앞에서
    `no_holdings` skip 지시로 끝난다(POC5-05 Q-A).
    """
    out = HoldingsAssembly()
    # POC5-05 Q-A — 정상 빈 보유(전량매도)면 조회 대상이 0 이라 비거래일 판정 · 완전성
    # 가드가 성립하지 않는다(대상 0 → `quote_incomplete` → 실패). 그래서 **가드 앞에서**
    # 선정 0(`no_selection`)과 같은 결의 skip 으로 돌린다 — 빈 상태 저장 · 미발송 ·
    # 판정은 flag guard 뒤(§6-c). 파일 없음 · 손상은 여기서 걸리지 않는다.
    if should_skip_no_holdings(price_refresh_diag, holdings_loader):
        out.outcome = HoldingsSelectionOutcome(
            skip_reason=REASON_NO_HOLDINGS,
            save_empty_state=True,
            diagnostics={
                "holdings_loaded_count": 0,
                "holdings_unique_ticker_count": 0,
                "holdings_selected_count": 0,
            },
        )
        out.diagnostics.update(out.outcome.diagnostics)
        return out

    skip_ntd, ntd_evidence, ntd_reason = check_non_trading_day(
        market_quotes=market_quotes or {},
        today_kst=today_kst,
        price_refresh_diag=price_refresh_diag,
        logger=logger,
    )
    out.skip_non_trading_day = skip_ntd
    out.diagnostics["non_trading_day_evidence"] = ntd_evidence
    out.diagnostics["non_trading_day_reason"] = ntd_reason

    blocked = check_incomplete_without_today(
        market_quotes=market_quotes or {},
        today_kst=today_kst,
        skip_non_trading_day=skip_ntd,
        non_trading_day_reason=ntd_reason,
        target_tickers=price_refresh_diag.get("target_tickers") or (),
        logger=logger,
    )
    if blocked is not None:
        out.fail = ("failed", "holdings_quotes_incomplete_no_today", blocked)
        return out
    if skip_ntd:
        return out

    outcome = build_holdings_selection(
        holdings_loader=holdings_loader,
        fetch_history=fetch_history,
        market_quotes=market_quotes or {},
        state_path=state_path,
        slot_id=slot_id,
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
            logger.error("보유 선정 조립 실패: %s", outcome.error)
        out.fail = ("failed", "holdings_selection_error", outcome.error[:400])
        return out
    out.message_text = outcome.message_text
    return out
