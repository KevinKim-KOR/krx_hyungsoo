"""ML 축1 — 후보 ETF 상대상승 참고점수 v0 생성 CLI.

실행:
  python scripts/run_ml_relative_upside_score_v0.py
  python scripts/run_ml_relative_upside_score_v0.py --candidates 069500,229200,360750

본 스크립트가 하는 것:
  1. SQLite etf_daily_price 전체 universe 시계열 read.
  2. KODEX200 (069500) 기준 5/10/20일 수익률 + 초과수익 + drawdown_20d feature 계산.
  3. 학습 (walk-forward 1회 split, torch GPU). target = 이후 20거래일 KODEX200 대비 상대수익.
  4. 추론 — 현재 후보 ETF 의 raw prediction.
  5. 후보군 내 0~100 정규화 → display score.
  6. 점수 근거 사람 언어 요약 (지시문 §8) + simple 20d 초과수익 순위 비교 기록.
  7. state/ml/relative_upside_score_latest.json + run_latest.json 저장.

본 스크립트가 하지 않는 것:
  - OCI 전달 / Telegram 발송 / PARAM 포함 (지시문 §11 끝).
  - 매수/매도/threshold/버킷 판단 (지시문 §14 제외 범위).
  - 기존 ml_baseline_v0_report_latest.json 덮어쓰기 (별도 경로).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.market_data_store import (  # noqa: E402
    fetch_price_history,
    list_etf_tickers,
)
from app.ml_relative_upside_features import (  # noqa: E402
    KODEX200_TICKER,
    build_feature_rows_for_ticker,
    build_kodex200_series,
    is_complete_for_inference,
)
from app.ml_relative_upside_model import (  # noqa: E402
    normalize_to_display_scores,
    predict_raw_scores,
    train_walk_forward,
)
from app.ml_relative_upside_score import (  # noqa: E402
    build_run_meta,
    build_score_snapshot,
    now_iso_utc,
    save_run_meta,
    save_score_snapshot,
)


def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("ml_relative_upside_score_v0")
    if not logger.handlers:
        h = logging.StreamHandler()
        h.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logger.addHandler(h)
    logger.setLevel(logging.INFO)
    return logger


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ML 축1 — 상대상승 참고점수 v0")
    p.add_argument(
        "--candidates",
        default=None,
        help="추론 대상 ticker 콤마 구분 (default: 모든 ticker, KODEX200 제외)",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    logger = _setup_logger()

    # 1. 전체 universe ticker.
    all_tickers = list_etf_tickers()
    logger.info("etf universe tickers: %d", len(all_tickers))

    if KODEX200_TICKER not in all_tickers:
        # KODEX200 없으면 초과수익 계산 불가 → failed snapshot 저장 후 종료.
        meta = build_run_meta(
            asof_date="",
            generated_at=now_iso_utc(),
            status="failed",
            train_result=None,
            candidate_count=0,
            scored_candidate_count=0,
            snapshot_path="",
            feature_columns=(),
            error=f"KODEX200 ({KODEX200_TICKER}) not in etf_daily_price",
        )
        save_run_meta(meta)
        logger.error("KODEX200 (%s) 없음 — 종료", KODEX200_TICKER)
        return 2

    # 2. 모든 ticker 시계열 read.
    prices: dict[str, list[tuple[str, float]]] = {}
    for ticker in all_tickers:
        history = fetch_price_history(ticker)
        if history:
            prices[ticker] = history

    kodex_map = build_kodex200_series(prices)
    logger.info("kodex map dates: %d", len(kodex_map))

    # 3. 학습 데이터 — 모든 ticker × 모든 asof_index 의 feature row (target 포함).
    training_rows = []
    for ticker, history in prices.items():
        if ticker == KODEX200_TICKER:
            continue  # KODEX200 자체는 학습 대상 X (비교 기준).
        rows = build_feature_rows_for_ticker(
            ticker, history, kodex_map, include_future_target=True
        )
        training_rows.extend(rows)
    logger.info("training row pool: %d", len(training_rows))

    # 4. 학습.
    model, train_result = train_walk_forward(training_rows)
    logger.info(
        "train done: rows=%d/%d device=%s gpu=%s train_loss=%.6f test_loss=%.6f sec=%.2f",
        train_result.train_row_count,
        train_result.test_row_count,
        train_result.device_name,
        train_result.gpu_execution_used,
        train_result.train_loss_final,
        train_result.test_loss_final,
        train_result.train_seconds,
    )

    # 5. 추론 대상 ticker — 사용자 지정 or 전체 universe (KODEX200 제외).
    if args.candidates:
        target_tickers = [t.strip() for t in args.candidates.split(",") if t.strip()]
    else:
        target_tickers = [t for t in all_tickers if t != KODEX200_TICKER]

    # 6. 추론 — 각 ticker 의 **최신 asof** feature row 만 사용 (지시문 §6.3 — 추론
    #    시점에 미래 데이터 없음).
    inference_rows = []
    for ticker in target_tickers:
        history = prices.get(ticker)
        if not history:
            continue
        rows = build_feature_rows_for_ticker(
            ticker, history, kodex_map, include_future_target=False
        )
        # 최신 asof row 만.
        latest_complete = next(
            (r for r in reversed(rows) if is_complete_for_inference(r)), None
        )
        if latest_complete is not None:
            inference_rows.append(latest_complete)

    asof_date = (
        max((r.asof_date for r in inference_rows), default="") if inference_rows else ""
    )
    logger.info("inference candidates: %d (asof=%s)", len(inference_rows), asof_date)

    # 7. raw prediction + display score.
    if model is None or not inference_rows:
        # 학습 데이터 부족 또는 유효 후보 0건 — 기존 정상 score snapshot 을
        # 빈/failed/unavailable snapshot 으로 덮어쓰지 않는다 (UI 카드 계약 —
        # "실패 시 기존 점수 유지", AC).
        # run meta 만 갱신해서 이력 추적 가능하게 한다. 기존 SCORE_SNAPSHOT_PATH
        # 는 그대로 유지.
        status = "unavailable" if model is not None else "failed"
        generated_at = now_iso_utc()
        meta = build_run_meta(
            asof_date=asof_date,
            generated_at=generated_at,
            status=status,
            train_result=train_result,
            candidate_count=len(inference_rows),
            scored_candidate_count=0,
            snapshot_path="",  # snapshot 저장 안 함 — 빈 경로로 명시.
            feature_columns=train_result.feature_columns,
            error=(
                "model is None (insufficient training data)"
                if model is None
                else "no valid inference candidates"
            ),
        )
        save_run_meta(meta)
        logger.warning(
            "status=%s — score snapshot 미갱신 (기존 점수 보존), run meta 만 저장",
            status,
        )
        return 0

    raw_scores = predict_raw_scores(model, inference_rows)
    display_scores = normalize_to_display_scores(raw_scores)

    # 8. simple 20d 초과수익 순위 (AC-5).
    simple_ranking = sorted(
        [
            (r.ticker, r.excess_return_20d)
            for r in inference_rows
            if r.excess_return_20d is not None
        ],
        key=lambda kv: kv[1],  # type: ignore[arg-type,return-value]
        reverse=True,
    )

    # 9. snapshot 저장.
    generated_at = now_iso_utc()
    snapshot = build_score_snapshot(
        asof_date=asof_date,
        generated_at=generated_at,
        status="ok",
        display_scores=display_scores,
        raw_scores=raw_scores,
        feature_rows=inference_rows,
        simple_excess_return_ranking=simple_ranking,
    )
    snapshot_path = save_score_snapshot(snapshot)
    meta = build_run_meta(
        asof_date=asof_date,
        generated_at=generated_at,
        status="ok",
        train_result=train_result,
        candidate_count=len(inference_rows),
        scored_candidate_count=len(display_scores),
        snapshot_path=str(snapshot_path),
        feature_columns=train_result.feature_columns,
        error=None,
    )
    save_run_meta(meta)

    print(
        json.dumps(
            {
                "status": "ok",
                "asof_date": asof_date,
                "candidate_count": len(inference_rows),
                "scored_candidate_count": len(display_scores),
                "snapshot_path": str(snapshot_path),
                "device": train_result.device_name,
                "gpu_execution_used": train_result.gpu_execution_used,
                "train_seconds": round(train_result.train_seconds, 3),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
