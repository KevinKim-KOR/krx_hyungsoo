"""OCI 일별 시장 데이터 배치 CLI (OCI Operational Market Data Refresh v1 · §5).

평일 하루 한 번 (기본 07:20 KST) 실행:
    승인 대상(seed ∪ Holdings) 증분 시세 갱신
    → SQLite 저장 검증
    → Universe 운영 artifact 생성 (SQLite fetcher · pykrx 경로 보존)
    → freshness 검증

Spike 조건 평가와 분리 (Spike 는 이 배치를 반복하지 않는다).

사용:
    python scripts/run_oci_market_data_batch.py            # 실제 실행
    python scripts/run_oci_market_data_batch.py --dry-run  # 갱신·생성 없이 대상/상태만

Fail-Closed: source 실패·대상 누락·저장 실패·artifact 실패·freshness 미달 시
status=failed. 기존 artifact/이전 가격으로 대체하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.three_push_runner_common import setup_logging  # noqa: E402
from app.three_push_runtime.market_data_batch import (  # noqa: E402
    collect_approved_tickers,
    evaluate_freshness,
    refresh_approved_prices,
)


def _kst_today() -> date:
    from app.three_push_runtime_message_builder import kst_today_date

    return datetime.strptime(kst_today_date(), "%Y-%m-%d").date()


def run(mode: str = "run") -> dict:
    logger = setup_logging(
        "oci_market_data_batch", log_filename="oci_market_data_batch.log"
    )
    started = datetime.now(timezone.utc).isoformat()
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
    }

    def _finish(status: str, reason=None) -> dict:
        record["status"] = status
        record["reason"] = reason
        record["finished_at"] = datetime.now(timezone.utc).isoformat()
        logger.info(
            "oci market data batch 완료: status=%s reason=%s price_as_of=%s "
            "artifact_at=%s",
            status,
            reason,
            record["price_data_as_of"],
            record["artifact_generated_at"],
        )
        # C 확정: Spike 가 읽을 배치 실행 상태 저장 (dry-run 제외 · 실제 run 만).
        if mode != "dry-run":
            from app.three_push_runtime.market_data_batch import write_batch_state

            write_batch_state(
                status=status,
                price_data_as_of=record["price_data_as_of"],
                artifact_generated_at=record["artifact_generated_at"],
                refresh_date_kst=_kst_today().isoformat(),
                refresh_completed_at=record["finished_at"],
            )
        return record

    # ── 1. 승인 대상 수집 ────────────────────────────────────────────────
    try:
        tickers = collect_approved_tickers()
    except Exception as e:  # noqa: BLE001
        logger.error("승인 대상 수집 실패: %s", e)
        return _finish("failed", f"collect_tickers_error:{type(e).__name__}")
    record["attempted"] = len(tickers)
    logger.info("승인 대상 ticker: %d개", len(tickers))

    if mode == "dry-run":
        # 갱신·생성 없이 현재 상태만.
        from app.market_data_store import get_last_price_date

        dates = [get_last_price_date(t) for t in tickers]
        dates = [d for d in dates if d]
        record["price_data_as_of"] = min(dates) if dates else None
        return _finish("dry_run_success", None)

    # ── 2. 증분 시세 갱신 ────────────────────────────────────────────────
    end_date = _kst_today()
    try:
        rr = refresh_approved_prices(tickers, end_date=end_date)
    except Exception as e:  # noqa: BLE001
        logger.error("시세 갱신 예외: %s", e)
        return _finish("failed", f"refresh_error:{type(e).__name__}")
    record["success"] = rr.success
    record["fail"] = rr.fail
    record["price_data_as_of"] = rr.price_data_as_of
    logger.info(
        "시세 갱신: attempted=%d success=%d fail=%d price_as_of=%s",
        rr.attempted,
        rr.success,
        rr.fail,
        rr.price_data_as_of,
    )
    # Fail-Closed: 승인 대상 일부라도 실패하면 failed (stale 위장 금지).
    if rr.fail > 0:
        return _finish("failed", f"price_refresh_partial:fail={rr.fail}/{rr.attempted}")
    if not rr.price_data_as_of:
        return _finish("failed", "price_data_as_of_missing")

    # ── 3. Universe 운영 artifact 생성 (저장하지 않음 · A-1(4)) ───────────
    # A-1(4): 검증(refresh_status·validate·freshness) 통과 전에는 latest 를 덮어쓰지
    # 않는다. 생성은 dict 반환까지만, 저장은 §5 에서.
    try:
        momentum_result, gen_at, refresh_status = _build_universe_artifact(
            price_data_as_of=rr.price_data_as_of
        )
    except Exception as e:  # noqa: BLE001
        logger.error("artifact 생성 실패: %s", e)
        return _finish("failed", f"artifact_generation_error:{type(e).__name__}")
    record["artifact_generated_at"] = gen_at
    record["refresh_status"] = refresh_status
    # A-1(5): refresh_status 가 ok 가 아니면 배치 실패 (기존 latest 미변경).
    if refresh_status != "ok":
        return _finish("failed", f"refresh_status:{refresh_status}")

    # ── 3-b. 공용 validator 로 (저장 전) artifact 검증 (A-1(6)) ───────────
    try:
        from app.universe_bootstrap.artifact_validator import validate_artifact

        valid, reason, _meta = validate_artifact(momentum_result)
    except Exception as e:  # noqa: BLE001
        return _finish("failed", f"artifact_validate_error:{type(e).__name__}")
    if not valid:
        return _finish("failed", f"artifact_invalid:{reason}")

    # ── 4. freshness 검증 (C 확정: 현재일 기준 7달력일 상한 · DB 순환 없음) ──
    verdict = evaluate_freshness(
        price_data_as_of=record["price_data_as_of"],
        artifact_generated_at=gen_at,
        current_date=end_date.isoformat(),
    )
    record["freshness_ok"] = verdict.ok
    record["freshness_reason"] = verdict.reason
    if not verdict.ok:
        return _finish("failed", f"freshness:{verdict.reason}")

    # ── 5. 모든 검증 통과 후에만 latest artifact 저장 (A-1(4)) ────────────
    try:
        from app.momentum.universe_mode import save_latest_artifact

        artifact_path = save_latest_artifact(momentum_result)
    except Exception as e:  # noqa: BLE001
        logger.error("artifact 저장 실패: %s", e)
        return _finish("failed", f"artifact_save_error:{type(e).__name__}")
    record["artifact_path"] = str(artifact_path)

    # 설계자 C 확정문: 배치 최종 성공 status = "success" (Spike guard 가 이 값 검증).
    return _finish("success", None)


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
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="갱신·생성 없이 대상/현재 상태만 확인.",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    result = run(mode="dry-run" if args.dry_run else "run")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result.get("status") in ("success", "dry_run_success") else 1)


if __name__ == "__main__":
    main()
