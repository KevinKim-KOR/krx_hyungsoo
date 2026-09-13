"""POC3-OPS-02B-2 — 시장 브리핑 **전용** runner helper.

설계자 §M-6 확정 — 러너에는 **최소 호출 배선만** 둔다. 조립·판정·상태 저장을
여기서 끝내고 러너는 세 번 호출한다.

**건드리지 않는 것**

- 보유 브리핑(§3-c)·급락 알림(§3-d) 분기
- 공통 `record_send_success` 계약
- 다른 push_kind 의 어떤 경로도

**판정 순서** — `assemble` 은 조립만 하고, `decide` 는 러너가 **flag guard 뒤**
(§6-c)에서 호출한다. 앞에서 끊으면 `push_kind_disabled` 를 `non_trading_day` 가
가로챈다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from app.market_briefing import flow, meta_gate
from app.three_push_runner_common import STATE_DIR

PUSH_KIND = "market_briefing"

MARKET_META_DIR = Path("state/market_meta")
OFFICIAL_ETF_CSV = "krx_etf_basic_20260909.csv"

# 전망 근거로 쓰는 미국 benchmark. 방향은 S&P500 **하나만** 결정한다.
SP500_BENCHMARK = "US500"


def _sp500_input(today_kst: str) -> tuple[Optional[float], Optional[str], bool]:
    """직전 미국 거래일의 **1일 종가 수익률**과 신선도.

    `market_benchmark_daily_price` 에서 읽는다. **08:00 에 외부 조회를 하지
    않는다** — 07:20 배치가 적재해 둔 값만 본다.

    최신·직전 **두 세션이 모두** 있어야 수익률이 성립한다. 하나라도 없으면
    `fresh=False` 로 돌려 전망을 `NONE` 으로 만든다.
    """
    try:
        from app.market_benchmark_store import fetch_benchmark_history
    except Exception:  # noqa: BLE001
        return None, None, False
    try:
        rows = fetch_benchmark_history(SP500_BENCHMARK)
    except Exception:  # noqa: BLE001
        return None, None, False
    series = [(d, c) for d, c in (rows or []) if c and c > 0]
    if len(series) < 2:
        return None, (series[-1][0] if series else None), False
    (prev_d, prev_c), (last_d, last_c) = series[-2], series[-1]
    _ = prev_d
    # 미국 세션은 한국 실행일보다 앞선다. 같은 날짜거나 미래면 쓰지 않는다.
    fresh = bool(last_d and last_d < today_kst)
    return (last_c / prev_c - 1.0) * 100.0, last_d, fresh


def assemble(
    record: dict[str, Any],
    *,
    push_kind: str,
    today_kst: str,
    runtime_kst: Optional[str],
    logger: Any = None,
    state_dir: Optional[Path] = None,
    meta_dir: Optional[Path] = None,
    db_path: Optional[Path] = None,
) -> Optional[flow.BriefingOutcome]:
    """러너 §3-e. 시장 브리핑이 아니면 `None`.

    **판정하지 않는다** — `skip_reason` 을 담아 돌려주기만 한다.
    """
    if push_kind != PUSH_KIND:
        return None
    sdir = state_dir or STATE_DIR
    mdir = meta_dir or MARKET_META_DIR
    ret, asof, fresh = _sp500_input(today_kst)
    outcome = flow.assemble_market_briefing(
        today_kst=today_kst,
        runtime_kst=runtime_kst,
        state_path=sdir / flow.STATE_NAME,
        consistency_path=sdir / meta_gate.CONSISTENCY_STATE_NAME,
        official_csv_path=mdir / OFFICIAL_ETF_CSV,
        sp500_return_pct=ret,
        sp500_asof=asof,
        sp500_fresh=fresh,
        db_path=db_path,
    )
    record.update(outcome.diagnostics)
    record["message_text_length"] = len(outcome.message_text)
    return outcome


def decide(
    outcome: Optional[flow.BriefingOutcome], *, logger: Any = None
) -> Optional[tuple[str, str, Optional[str]]]:
    """러너 §6-c. **flag guard 뒤에서** 호출한다.

    반환이 `None` 이면 발송으로 진행한다.
    """
    if outcome is None:
        return None
    if outcome.fail is not None:
        return outcome.fail
    if outcome.skip_reason:
        if logger is not None:
            logger.info("시장 브리핑 skip: %s", outcome.skip_reason)
        return ("skipped", outcome.skip_reason, None)
    if not outcome.message_text:
        return ("skipped", flow.REASON_NO_PUBLISHABLE, None)
    return None


def save_state_after_send(
    outcome: Optional[flow.BriefingOutcome],
    *,
    today_kst: str,
    runtime_kst: Optional[str],
    record: Optional[dict[str, Any]] = None,
    state_dir: Optional[Path] = None,
) -> None:
    """러너 §8. **Telegram 전체 성공 뒤에만** 호출한다.

    저장 실패를 발송 실패로 기록하지 않는다 — 발송 사실과 저장 실패를 **분리**해
    남긴다(설계 §6).
    """
    if outcome is None or not outcome.fingerprint:
        return
    sdir = state_dir or STATE_DIR
    try:
        flow.save_state(
            sdir / flow.STATE_NAME,
            fingerprint=outcome.fingerprint,
            sent_date_kst=today_kst,
            runtime_kst=runtime_kst,
        )
    except Exception as e:  # noqa: BLE001
        if record is not None:
            record["state_write_failed"] = f"{type(e).__name__}"
        return
    if record is not None:
        record["market_briefing_state_saved"] = True


__all__ = [
    "MARKET_META_DIR",
    "OFFICIAL_ETF_CSV",
    "PUSH_KIND",
    "SP500_BENCHMARK",
    "assemble",
    "decide",
    "save_state_after_send",
]
