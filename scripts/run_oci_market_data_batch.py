"""OCI 일별 시장 데이터 배치 CLI (OCI Operational Market Data Refresh v1 · §5).

평일 하루 한 번 (POC3-02D-OPS-03 부터 **08:10 KST** · 옛 07:20) 실행:
    승인 대상(seed ∪ Holdings) 증분 시세 갱신 (FDR · timeout 명시)
    → 미국 · KOSPI · VIX 갱신
    → Universe 운영 artifact 생성 (SQLite fetcher · pykrx 경로 보존) · freshness 검증
    → KRX 목표일(T-1) 수집 (08:10 · 08:15 · 08:20 · 08:24 · 마감 08:27)
      · KOSPI 가 T-1 이 아니면 같은 시각표로 재시도(설계자 RESULT STEP 3 · ETF 와 독립)

POC3-02D-OPS-03 확정 계약 2 — **단계별 실패 격리**. FDR 한 종목 실패가 미국 · KOSPI ·
VIX · KRX 를 막지 않는다. 종료 status 는 예전 그대로(가격 파이프라인 실패 =
`failed` · 가격 소비자 fail-closed). 미국 · FDR 은 회차당 1회 — KRX 재시도는 KRX
단계 안에서만 돈다.

Spike 조건 평가와 분리 (Spike 는 이 배치를 반복하지 않는다).

사용:
    python scripts/run_oci_market_data_batch.py            # 실제 실행 (08:10)
    python scripts/run_oci_market_data_batch.py --dry-run  # 갱신·생성 없이 대상/상태만
    python scripts/run_oci_market_data_batch.py --krx-only # 09:20 KRX 전용 보강 1회

Fail-Closed: source 실패·대상 누락·저장 실패·artifact 실패·freshness 미달 시
status=failed. 기존 artifact/이전 가격으로 대체하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.three_push_runner_common import setup_logging  # noqa: E402
from app.three_push_runtime.market_data_batch import (  # noqa: E402
    FDR_STAGE_TIME_BUDGET_SECONDS,
    collect_approved_tickers,
    evaluate_freshness,
    fdr_request_timeout,
    refresh_approved_prices,
)


def _kst_today() -> date:
    from app.three_push_runtime_message_builder import kst_today_date

    return datetime.strptime(kst_today_date(), "%Y-%m-%d").date()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# 공식 CSV 는 이 폴더에서 08:00 과 **같은 resolver** 가 고른다(POC3-02D-OPS-01
# C1 · Q2). 파일명 상수로 고르지 않는다.
MARKET_META_DIR = Path("state/market_meta")


def run(mode: str = "run") -> dict:
    logger = setup_logging(
        "oci_market_data_batch", log_filename="oci_market_data_batch.log"
    )
    started = _utc_now()
    record: dict = {
        "task": "oci_market_data_batch",
        "mode": mode,
        "status": "failed",
        "reason": None,
        "started_at": started,
        "finished_at": "",
        "attempted": 0,
        "success": 0,
        "fail": 0,
        "price_data_as_of": None,
        "artifact_generated_at": None,
        "artifact_path": None,
        "freshness_ok": False,
        "freshness_reason": "",
        # POC3-02D-OPS-03 — 단계별 상태(격리 결과를 숨기지 않는다).
        "stage_status": {},
    }
    stages = record["stage_status"]

    def _write_state(status: str, completed_at: str) -> None:
        # C 확정: Spike 가 읽을 배치 실행 상태 저장 (dry-run 제외 · 실제 run 만).
        from app.three_push_runtime.market_data_batch import write_batch_state

        _bench = record.get("benchmark_refresh") or {}
        write_batch_state(
            status=status,
            price_data_as_of=record["price_data_as_of"],
            artifact_generated_at=record["artifact_generated_at"],
            refresh_date_kst=_kst_today().isoformat(),
            refresh_completed_at=completed_at,
            # POC3-OPS-02B-1 — benchmark 결과를 **영구 상태에 남긴다.**
            price_pipeline_status=record.get("price_pipeline_status"),
            benchmark_status=record.get("benchmark_status"),
            benchmark_failed=_bench.get("failed"),
            kospi_as_of=record.get("kospi_as_of"),
            vix_as_of=record.get("vix_as_of"),
            krx_sync_status=record.get("krx_sync_status"),
            krx_basis_date=record.get("krx_basis_date"),
            meta_consistency_status=record.get("meta_consistency_status"),
            stage_status=stages,
            krx_target_date=record.get("krx_target_date"),
            krx_stage_mode=record.get("krx_stage_mode"),
            krx_attempts=record.get("krx_attempts"),
            calendar_readiness=record.get("calendar_readiness"),
            krx_representatives=record.get("krx_representatives"),
            representatives_refresh_due=record.get("representatives_refresh_due"),
            krx_backfill=record.get("krx_backfill"),
            kospi_attempts=record.get("kospi_attempts"),
            kospi_retry=record.get("kospi_retry"),
        )

    def _finish(status: str, reason=None) -> dict:
        record["status"] = status
        record["reason"] = reason
        record["finished_at"] = _utc_now()
        logger.info(
            "oci market data batch 완료: status=%s reason=%s price_as_of=%s "
            "artifact_at=%s",
            status,
            reason,
            record["price_data_as_of"],
            record["artifact_generated_at"],
        )
        if mode != "dry-run":
            _write_state(status, record["finished_at"])
        return record

    # ── 1. 승인 대상 수집 ────────────────────────────────────────────────
    tickers: Optional[list] = None
    price_failure: Optional[str] = None
    try:
        tickers = collect_approved_tickers()
    except Exception as e:  # noqa: BLE001
        logger.error("승인 대상 수집 실패: %s", e)
        price_failure = f"collect_tickers_error:{type(e).__name__}"
        if mode == "dry-run":
            return _finish("failed", price_failure)
    stages["collect"] = "ok" if tickers is not None else "failed"
    if tickers is not None:
        record["attempted"] = len(tickers)
        logger.info("승인 대상 ticker: %d개", len(tickers))

    if mode == "dry-run":
        # 갱신·생성 없이 현재 상태만.
        from app.market_data_store import get_last_price_date

        dates = [get_last_price_date(t) for t in tickers]
        dates = [d for d in dates if d]
        record["price_data_as_of"] = min(dates) if dates else None
        return _finish("dry_run_success", None)

    end_date = _kst_today()
    record["calendar_readiness"] = _calendar_readiness(end_date, logger)

    # ── 2. 증분 시세 갱신 (FDR · 회차당 1회 · timeout 명시) ──────────────────
    # 확정 계약 2 — 실패해도 **여기서 끝내지 않는다.** 미국 · KOSPI · VIX · KRX 는
    # 계속 돈다. 종료 status 는 아래에서 예전처럼 `failed` 로 정한다.
    rr = None
    if tickers is not None:
        rr, price_failure = _fdr_stage(record, tickers, end_date, logger)
        stages["fdr_price"] = "ok" if price_failure is None else "failed"
    else:
        stages["fdr_price"] = "skipped"

    # ── 2-b. benchmark 갱신 (POC3-OPS-02B-1 계약 ① · 가격 실패와 무관) ────────
    kospi_retry = _benchmark_stage(record, end_date, logger)

    # ── 3~5. Universe artifact (가격이 성공한 날만 · A-1(4)) ────────────────
    if price_failure is None and rr is not None:
        price_failure = _artifact_stage(record, rr, end_date, logger)
        stages["artifact"] = "ok" if price_failure is None else "failed"
    else:
        # 실패한 가격으로 latest artifact 를 만들지 않는다(Fail-Closed · 예전과 같다).
        stages["artifact"] = "skipped"

    status, reason = _terminal_status(record, price_failure)
    # KRX 단계는 08:24 까지 기다릴 수 있다 — 가격 · 미국 결과를 **먼저** 남긴다.
    # 08:30 브리핑이 배치 상태를 읽을 때 KRX 대기 때문에 '배치 없음' 으로 보이지
    # 않게 하기 위해서다. KRX 가 끝나면 같은 파일을 다시 쓴다.
    stages["krx"] = "pending"
    _write_state(status, _utc_now())

    # ── 6. KRX 목표일 수집 (POC3-02D-OPS-03 · 확정 계약 1 · 2 · 3) ───────────
    # 설계자 RESULT STEP 3 — KOSPI 재시도는 KRX 단계 시각표의 곁 작업으로 돈다.
    _krx_stage(record, end_date, logger, side_task=kospi_retry)
    # 재시도가 KOSPI 결과를 바꿨으면 benchmark 상태 · 종료 status 를 다시 센다.
    kospi_retry.apply(record)
    status, reason = _terminal_status(record, price_failure)
    return _finish(status, reason)


def _calendar_readiness(today: date, logger) -> dict:
    """한국 · 미국 거래일 달력 올해 · 다음 해 준비 상태(확정 계약 11). 예외를 올리지 않는다.

    12월에 다음 해 파일이 없으면 `warn` — PC 「OCI 운영·적용」 상태 표가 같은 규칙으로
    보인다(`oci_startup_status`). Telegram 은 보내지 않는다.
    """
    from app.us_trading_calendar import (
        READY_OK,
        READY_UNKNOWN,
        calendar_readiness_for_dir,
    )

    try:
        ready = calendar_readiness_for_dir(today, MARKET_META_DIR)
    except Exception as e:  # noqa: BLE001
        return {"state": READY_UNKNOWN, "error": type(e).__name__}
    if ready.get("state") != READY_OK:
        logger.warning(
            "거래일 달력 준비 상태: %s (올해 없음=%s · 다음 해 없음=%s)",
            ready.get("state"),
            ready.get("missing_current"),
            ready.get("missing_next"),
        )
    return ready


def _fdr_stage(record: dict, tickers: list, end_date: date, logger):
    """FDR 증분 시세. 반환 `(RefreshResult | None, 실패 사유 | None)`."""
    try:
        # DEF-FDR-TIMEOUT — 멈춘 종목은 timeout 실패로 집계되고 다음 종목으로 간다.
        # 단계 시간 상한 — 원천 전체 불통이면 남은 종목을 시작하지 않는다(KRX 시도 보호).
        with fdr_request_timeout():
            rr = refresh_approved_prices(
                tickers,
                end_date=end_date,
                time_budget_seconds=FDR_STAGE_TIME_BUDGET_SECONDS,
            )
    except Exception as e:  # noqa: BLE001
        logger.error("시세 갱신 예외: %s", e)
        return None, f"refresh_error:{type(e).__name__}"
    record["success"] = rr.success
    record["fail"] = rr.fail
    record["price_data_as_of"] = rr.price_data_as_of
    record["price_failures"] = list(rr.failures or [])[:5]
    record["price_budget_skipped"] = len(getattr(rr, "budget_skipped", None) or [])
    logger.info(
        "시세 갱신: attempted=%d success=%d fail=%d price_as_of=%s",
        rr.attempted,
        rr.success,
        rr.fail,
        rr.price_data_as_of,
    )
    # Fail-Closed: 승인 대상 일부라도 실패하면 failed (stale 위장 금지).
    if rr.fail > 0:
        return rr, f"price_refresh_partial:fail={rr.fail}/{rr.attempted}"
    if not rr.price_data_as_of:
        return rr, "price_data_as_of_missing"
    return rr, None


def _benchmark_stage(record: dict, end_date: date, logger):
    """미국 · KOSPI · VIX. 실패는 record 에만 남긴다(ETF 가격 적재를 롤백하지 않는다).

    DEF-KOSPI-BENCHMARK-VALUE-ASOF-INTEGRITY — 설계자 확정: ETF 가격 성공과
    benchmark 성공을 **별도 상태로 기록**하고, benchmark 실패를 전체 배치 성공으로
    숨기지 않는다.

    반환: KOSPI 재시도(`KospiRetry` · 설계자 RESULT STEP 3). 이 단계의 KOSPI 조회가
    첫 시도(08:10)다. 시작 시각은 KRX 단계와 같은 시계로 잰다.
    """
    from app.market_benchmark_batch import refresh_benchmarks
    from app.market_benchmark_kospi_retry import KospiRetry, now_kst

    first_at = now_kst()
    try:
        with fdr_request_timeout():
            bench = refresh_benchmarks(end_date=end_date, logger=logger)
    except Exception as e:  # noqa: BLE001 - 예외를 올리지 않는 계약을 한 번 더 격리
        bench = {
            "status": "failed",
            "failed": [f"unexpected:{type(e).__name__}"],
            "kospi": {},
            "vix": {},
        }
    record["benchmark_refresh"] = bench
    record["benchmark_status"] = bench.get("status")
    record["kospi_as_of"] = (bench.get("kospi") or {}).get("as_of_date")
    record["vix_as_of"] = (bench.get("vix") or {}).get("as_of_date")
    record["stage_status"]["benchmark"] = bench.get("status")
    if bench.get("status") != "ok":
        logger.warning(
            "benchmark 갱신 실패: %s — ETF 가격 적재는 유지한다", bench.get("failed")
        )
    retry = KospiRetry(
        bench.get("kospi"), first_at=first_at, end_date=end_date, logger=logger
    )
    retry.apply(record)
    return retry


def _artifact_stage(record: dict, rr, end_date: date, logger) -> Optional[str]:
    """Universe artifact 생성 · 검증 · freshness · 저장. 실패 사유 또는 `None`."""
    # A-1(4): 검증(refresh_status·validate·freshness) 통과 전에는 latest 를 덮어쓰지
    # 않는다. 생성은 dict 반환까지만, 저장은 모든 검증 뒤.
    try:
        momentum_result, gen_at, refresh_status = _build_universe_artifact(
            price_data_as_of=rr.price_data_as_of
        )
    except Exception as e:  # noqa: BLE001
        logger.error("artifact 생성 실패: %s", e)
        return f"artifact_generation_error:{type(e).__name__}"
    record["artifact_generated_at"] = gen_at
    record["refresh_status"] = refresh_status
    # A-1(5): refresh_status 가 ok 가 아니면 배치 실패 (기존 latest 미변경).
    if refresh_status != "ok":
        return f"refresh_status:{refresh_status}"

    # 공용 validator 로 (저장 전) artifact 검증 (A-1(6)).
    try:
        from app.universe_bootstrap.artifact_validator import validate_artifact

        valid, reason, _meta = validate_artifact(momentum_result)
    except Exception as e:  # noqa: BLE001
        return f"artifact_validate_error:{type(e).__name__}"
    if not valid:
        return f"artifact_invalid:{reason}"

    # freshness 검증 (C 확정: 현재일 기준 7달력일 상한 · DB 순환 없음).
    verdict = evaluate_freshness(
        price_data_as_of=record["price_data_as_of"],
        artifact_generated_at=gen_at,
        current_date=end_date.isoformat(),
    )
    record["freshness_ok"] = verdict.ok
    record["freshness_reason"] = verdict.reason
    if not verdict.ok:
        return f"freshness:{verdict.reason}"

    # 모든 검증 통과 후에만 latest artifact 저장 (A-1(4)).
    try:
        from app.momentum.universe_mode import save_latest_artifact

        artifact_path = save_latest_artifact(momentum_result)
    except Exception as e:  # noqa: BLE001
        logger.error("artifact 저장 실패: %s", e)
        return f"artifact_save_error:{type(e).__name__}"
    record["artifact_path"] = str(artifact_path)
    # 가격 파이프라인은 여기까지 성공이다. **별도로** 기록한다.
    record["price_pipeline_status"] = "success"
    return None


def _terminal_status(record: dict, price_failure: Optional[str]) -> tuple:
    """종료 status — 예전 계약 그대로. KRX 결과는 status 를 바꾸지 않는다."""
    if price_failure is not None:
        return "failed", price_failure
    # POC3-OPS-02B-1 (검증자 r1 A-1) — benchmark 가 실패했는데 배치를 그냥
    # `success` 로 끝내면 **실패가 성공으로 묻힌다.** 계약 ③ 대로 ETF 가격 적재는
    # 그대로 유지하고 롤백하지 않는다 — `price_pipeline_status` 가 그것을 증명한다.
    _bstatus = record.get("benchmark_status")
    if _bstatus and _bstatus != "ok":
        _failed = (record.get("benchmark_refresh") or {}).get("failed") or []
        return (
            "success_with_benchmark_failure",
            f"benchmark_{_bstatus}:{','.join(_failed)}",
        )
    return "success", None


def _krx_stage(
    record: dict,
    today: date,
    logger,
    *,
    max_attempts: Optional[int] = None,
    side_task=None,
) -> dict:
    """KRX 전종목 목표일 수집 — 가격 적재 + 정합성 판정(POC3-OPS-02B-2 §M-2).

    응답 **하나**로 무조정 가격계열 적재와 API·CSV 정합성을 함께 한다. 08:30
    runner 는 같은 API 를 다시 호출하지 않는다. 실패해도 예외를 올리지 않고
    ETF 가격 적재를 롤백하지 않는다. `side_task` = 08:10 KOSPI 재시도(09:20 은 없음).
    """
    from app.market_briefing import krx_target_sync, meta_gate
    from app.three_push_runner_common import STATE_DIR as _STATE_DIR

    try:
        krx = krx_target_sync.sync_krx_target(
            today=today,
            meta_dir=MARKET_META_DIR,
            consistency_path=_STATE_DIR / meta_gate.CONSISTENCY_STATE_NAME,
            max_attempts=max_attempts,
            logger=logger,
            side_task=side_task,
        )
    except Exception as e:  # noqa: BLE001
        krx = {"status": f"unexpected:{type(e).__name__}", "basis_date": None}
    record["krx_sync"] = krx
    record["krx_sync_status"] = krx.get("status")
    record["krx_basis_date"] = krx.get("basis_date")
    record["krx_target_date"] = krx.get("target_date")
    record["krx_stage_mode"] = krx.get("mode")
    record["krx_attempts"] = list(krx.get("attempts") or [])
    record["meta_consistency_status"] = krx.get("consistency_status")
    # 설계자 RESULT STEP 2 · 6 — 대표 커버리지(적재 성공과 별개)와 빈 날 채우기 호출 기록.
    record["krx_representatives"] = krx.get("representatives")
    record["representatives_refresh_due"] = krx.get("representatives_refresh_due")
    record["krx_backfill"] = {
        k: krx[k] for k in ("backfill", "backfill_retry") if k in krx
    } or None
    record.setdefault("stage_status", {})["krx"] = krx.get("status")
    if krx.get("status") != krx_target_sync.STATUS_OK:
        logger.warning(
            "KRX 목표일 수집 실패: %s — ETF 가격 적재는 유지한다", krx.get("status")
        )
    # POC3-02D-OPS-01 R2 Q23 · Q24 — CSV 갱신 필요 판정을 **매회** 남긴다.
    # 정합성 JSON 은 KRX 단계가 이미 썼다(또는 T-1 판정을 지켰다). 모르면 None.
    record["meta_refresh_due"] = krx.get("refresh_due")
    record["meta_refresh_due_reason"] = krx.get("refresh_due_reason")
    record["meta_refresh_due_cycle_id"] = krx.get("refresh_due_cycle_id")
    record["official_csv_name"] = krx.get("csv_name")
    logger.info(
        "공식 CSV 갱신 판정: refresh_due=%s reason=%s cycle=%s csv=%s",
        krx.get("refresh_due", "unknown"),
        krx.get("refresh_due_reason"),
        krx.get("refresh_due_cycle_id"),
        krx.get("csv_name"),
    )
    return krx


def run_krx_only() -> dict:
    """09:20 KRX 전용 보강 1회 (확정 계약 7).

    08:27 까지 T-1 을 못 받은 날만 목표일을 조회한다(이미 받았으면 목표일 조회 0 · 창 안
    빈 거래일 중 오늘 아직 부르지 않은 날만 채운다 · PLAN STEP 3-3 · 설계자 RESULT
    STEP 6 ledger). 하루 1회(목표일 시도 기준) ·
    FDR · 미국 · KOSPI · VIX · 네이버를 부르지 않는다 · 08:30 브리핑을 다시 보내지
    않는다. **08:10 배치 상태 JSON 을 덮지 않는다** — 기록은 별도 파일이다.
    """
    from app.three_push_runtime.market_data_batch import (
        read_krx_reinforcement_state,
        write_krx_reinforcement_state,
    )

    logger = setup_logging(
        "oci_market_data_batch", log_filename="oci_market_data_batch.log"
    )
    today = _kst_today()
    record: dict = {
        "task": "oci_krx_reinforcement",
        "mode": "krx-only",
        "date_kst": today.isoformat(),
        "status": None,
        "started_at": _utc_now(),
        "finished_at": "",
        "attempted": False,
        "stage_status": {},
    }
    prev = read_krx_reinforcement_state()
    if prev and prev.get("date_kst") == today.isoformat() and prev.get("attempted"):
        # 하루 1회 — 오늘 이미 조회했다. 앞 기록을 덮지 않는다.
        record["status"] = "skipped_already_ran_today"
        record["finished_at"] = _utc_now()
        logger.info("KRX 보강 건너뜀: 오늘 이미 조회했다(%s)", prev.get("finished_at"))
        return record

    _krx_stage(record, today, logger, max_attempts=1)
    record["attempted"] = bool(record.get("krx_attempts"))
    record["status"] = record.get("krx_sync_status")
    record["finished_at"] = _utc_now()
    write_krx_reinforcement_state(record)
    logger.info(
        "KRX 보강 완료: status=%s target=%s attempted=%s",
        record["status"],
        record.get("krx_target_date"),
        record["attempted"],
    )
    return record


def _build_universe_artifact(*, price_data_as_of: str) -> tuple[dict, str, str]:
    """승인 seed + SQLite fetcher 로 Universe artifact **생성** (저장 안 함).

    - 기존 build_universe_momentum_result_scored 재사용. save 는 호출자가 검증 후.
    - fetcher 만 SQLite 로 주입 (pykrx 경로는 PC 기본값으로 보존).
    - A-1(1,2): Builder 조회 기준일(asof) 을 실제 DB 최신일(price_data_as_of) 로
      override. seed 파일 원본은 미변경 (dataclasses.replace 로 사본만).
    - A-1(4): 저장하지 않는다. refresh_status/validate/freshness 통과 후 호출자가
      save_latest_artifact 를 부른다 (실패 artifact 로 latest 덮어쓰기 방지).
    반환: (momentum_result dict, artifact_generated_at ISO, refresh_status).
    """
    from dataclasses import replace

    from app.universe_seed import load_universe_seed
    from app.universe_refresh import (
        FALLING_THRESHOLD_PCT,
        build_failure_summary_reason,
        run_universe_refresh,
        validate_seed_for_refresh,
    )
    from app.momentum.universe_mode import build_universe_momentum_result_scored
    from app.price_history_sqlite import make_sqlite_price_fetcher

    seed = load_universe_seed()
    validate_seed_for_refresh(seed)
    # A-1(1,2): 조회 기준일을 실제 DB 최신일로. evidence_as_of 도 이 값이 된다.
    seed = replace(seed, asof=price_data_as_of)

    sqlite_fetcher = make_sqlite_price_fetcher()
    scores, refresh_status = run_universe_refresh(seed, fetcher=sqlite_fetcher)
    failure_reason = (
        build_failure_summary_reason(seed, scores)
        if refresh_status == "failed"
        else None
    )
    momentum_result = build_universe_momentum_result_scored(
        seed=seed,
        scores=scores,
        refresh_status=refresh_status,
        failure_summary_reason=failure_reason,
        falling_threshold_pct=FALLING_THRESHOLD_PCT,
    )
    gen_at = datetime.now(timezone.utc).isoformat()
    # artifact 에 생성 시각 · 실제 data_source 기록 (A-3).
    summary = momentum_result.setdefault("summary", {})
    summary["artifact_generated_at"] = gen_at
    summary["data_source"] = "sqlite_etf_daily_price"
    return momentum_result, gen_at, refresh_status


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="OCI 일별 시장 데이터 배치 (승인 대상 증분 갱신 + Universe artifact)."
    )
    g = p.add_mutually_exclusive_group()
    g.add_argument(
        "--dry-run",
        action="store_true",
        help="갱신·생성 없이 대상/현재 상태만 확인.",
    )
    g.add_argument(
        "--krx-only",
        action="store_true",
        help="09:20 KRX 전용 보강 1회 (T-1 미확보 날만 조회 · FDR·미국 없음).",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    if args.krx_only:
        result = run_krx_only()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result.get("status") == "ok" else 1)
    result = run(mode="dry-run" if args.dry_run else "run")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result.get("status") in ("success", "dry_run_success") else 1)


if __name__ == "__main__":
    main()
