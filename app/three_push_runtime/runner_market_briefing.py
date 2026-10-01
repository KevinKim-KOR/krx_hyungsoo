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

**POC3-02D-OPS-03** — 시장 브리핑 08:30 · 배치 08:10(확정 계약 1 · 2).

- S&P500 정상 = 저장 최신 세션 == **가장 최근 완료 NYSE 세션**(확정 계약 11 ·
  `us_trading_calendar`). 아니면 전망 없음(기존 문장 `SENTENCE_NO_OUTLOOK`). 기대 세션 ·
  저장 세션을 실행 기록에 남긴다.
- 배치 실패 고지 입력(PLAN STEP 7-3 한정) = 배치 상태 JSON 없음 · `refresh_date_kst` ≠
  오늘 · FDR 가격 단계 실패. KOSPI · VIX · IXIC · SOX 실패는 넣지 않는다(PC 전용 ·
  Telegram 없음). US500 실패 · KRX T-1 부재는 본문의 자기 줄로만 알린다(같은 원인 두 줄
  금지).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app import us_trading_calendar
from app.market_briefing import flow, meta_gate
from app.three_push_runner_common import STATE_DIR

PUSH_KIND = "market_briefing"

# 공식 CSV 는 이 폴더에서 07:20 과 **같은 resolver** 가 고른다(POC3-02D-OPS-01
# C1 · Q2). 파일명 상수로 고르지 않는다.
MARKET_META_DIR = Path("state/market_meta")

# 전망 근거로 쓰는 미국 benchmark. 방향은 S&P500 **하나만** 결정한다.
SP500_BENCHMARK = "US500"


def _instant(runtime_kst: Optional[str]) -> datetime:
    """기대 세션을 잴 실행 시각. 읽을 수 없으면 지금(UTC)."""
    if runtime_kst:
        try:
            return datetime.fromisoformat(runtime_kst)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _sp500_input(
    today_kst: str,
    *,
    now: Optional[datetime] = None,
    calendar_dir: Optional[Path] = None,
    db_path: Optional[Path] = None,
    diag: Optional[dict[str, Any]] = None,
) -> tuple[Optional[float], Optional[str], bool]:
    """직전 미국 거래일의 **1일 종가 수익률**과 신선도.

    `market_benchmark_daily_price` 에서 읽는다. **08:30 에 외부 조회를 하지
    않는다** — 08:10 배치가 적재해 둔 값만 본다.

    최신·직전 **두 세션이 모두** 있어야 수익률이 성립한다. 하나라도 없으면
    `fresh=False` 로 돌려 전망을 `NONE` 으로 만든다.

    POC3-02D-OPS-03 확정 계약 11 — 최신 세션 == 기대 완료 세션 · 직전 행 == 그 바로
    앞 세션일 때만 `fresh`(`us_trading_calendar.session_check` 결과를 `diag` 에 남긴다).
    """
    diag = diag if diag is not None else {}
    try:
        from app.market_benchmark_store import fetch_benchmark_history
    except Exception:  # noqa: BLE001
        diag["reason"] = "store_unavailable"
        return None, None, False
    try:
        kw = {"db_path": db_path} if db_path is not None else {}
        rows = fetch_benchmark_history(SP500_BENCHMARK, **kw)
    except Exception:  # noqa: BLE001
        diag["reason"] = "store_read_failed"
        return None, None, False
    series = [(d, c) for d, c in (rows or []) if c and c > 0]
    check = us_trading_calendar.session_check(
        series[-1][0] if series else None,
        series[-2][0] if len(series) >= 2 else None,
        now=now or datetime.now(timezone.utc),
        calendar_dir=calendar_dir,
    )
    diag.update(check)
    if len(series) < 2:
        return None, (series[-1][0] if series else None), False
    prev_c, (last_d, last_c) = series[-2][1], series[-1]
    # 미국 세션은 한국 실행일보다 앞선다. 같은 날짜거나 미래면 쓰지 않는다(기존 가드).
    fresh = bool(check["fresh"] and last_d and last_d < today_kst)
    return (last_c / prev_c - 1.0) * 100.0, last_d, fresh


def batch_failure_reasons(state: Optional[dict[str, Any]], today_kst: str) -> list[str]:
    """PLAN STEP 7-3 — 뒤 PUSH 판단에 영향을 주는 08:10 배치 실패 사유. 없으면 `[]`.

    `stage_status.fdr_price`(POC3-02D-OPS-03 배치)가 있으면 그것만 본다 — `failed` ·
    `skipped`(대상 수집 실패로 FDR 을 못 돌림). 옛 상태 파일이면 `status == "failed"`.
    benchmark(KOSPI · VIX · IXIC · SOX · US500) · KRX 필드는 보지 않는다.
    """
    if not isinstance(state, dict):
        return ["batch_state_missing"]
    if state.get("refresh_date_kst") != today_kst:
        return ["batch_not_today"]
    stages = state.get("stage_status")
    if isinstance(stages, dict) and "fdr_price" in stages:
        if stages.get("fdr_price") != "ok":
            return [f"fdr_price_{stages.get('fdr_price')}"]
        return []
    return ["batch_failed"] if state.get("status") == "failed" else []


def _batch_failure(
    today_kst: str, batch_state_path: Optional[Path] = None
) -> list[str]:
    """배치 상태 JSON(`market_data_batch.read_batch_state` · Spike 와 같은 파일)을 읽는다."""
    try:
        from app.three_push_runtime.market_data_batch import read_batch_state

        state = read_batch_state(batch_state_path)
    except Exception:  # noqa: BLE001 - 읽기 실패 = 상태 없음
        state = None
    return batch_failure_reasons(state, today_kst)


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
    batch_state_path: Optional[Path] = None,
) -> Optional[flow.BriefingOutcome]:
    """러너 §3-e. 시장 브리핑이 아니면 `None`.

    **판정하지 않는다** — `skip_reason` 을 담아 돌려주기만 한다.
    """
    if push_kind != PUSH_KIND:
        return None
    sdir = state_dir or STATE_DIR
    mdir = meta_dir or MARKET_META_DIR
    sp_diag: dict[str, Any] = {}
    ret, asof, fresh = _sp500_input(
        today_kst, now=_instant(runtime_kst), calendar_dir=mdir, diag=sp_diag
    )
    batch_failure = _batch_failure(today_kst, batch_state_path)
    outcome = flow.assemble_market_briefing(
        today_kst=today_kst,
        runtime_kst=runtime_kst,
        state_path=sdir / flow.STATE_NAME,
        consistency_path=sdir / meta_gate.CONSISTENCY_STATE_NAME,
        meta_dir=mdir,
        sp500_return_pct=ret,
        sp500_asof=asof,
        sp500_fresh=fresh,
        db_path=db_path,
        logger=logger,
        batch_failure=batch_failure,
    )
    record.update(outcome.diagnostics)
    record["message_text_length"] = len(outcome.message_text)
    # 확정 계약 11 — 기대 세션 · 저장 세션을 실행 기록에 남긴다(지금까지 없었다).
    record["sp500_asof"] = asof
    record["sp500_fresh"] = fresh
    record["sp500_expected_session"] = sp_diag.get("expected_session")
    record["sp500_session_check"] = sp_diag
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

    CSV 갱신 안내를 보낸 주기(R2 Q24)도 여기서만 남긴다 — 전체 성공이 아니면
    다음 실제 발송에 다시 붙는다.
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
            refresh_notice_cycle_id=outcome.refresh_notice_cycle_id,
        )
    except Exception as e:  # noqa: BLE001
        if record is not None:
            record["state_write_failed"] = f"{type(e).__name__}"
        return
    if record is not None:
        record["market_briefing_state_saved"] = True


__all__ = [
    "MARKET_META_DIR",
    "PUSH_KIND",
    "SP500_BENCHMARK",
    "assemble",
    "batch_failure_reasons",
    "decide",
    "save_state_after_send",
]
