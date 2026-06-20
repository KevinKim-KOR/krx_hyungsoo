"""ML 축1 (후보 ETF 상대상승 참고점수 v0) — 점수 근거 생성 + snapshot 저장.

지시문 §8 — 점수 근거는 모델 내부 feature vector / loss 가 아니라 기존
evidence 의 사람 언어 짧은 요약. 후보당 최대 3개 표시.

지시문 §11 — 산출물 경로:
  state/ml/relative_upside_score_latest.json   (점수 + 근거)
  state/ml/relative_upside_score_run_latest.json (실행 메타 + 비교 기록)

OCI 전달 금지 / Telegram 포함 금지 / PARAM 포함 금지 (지시문 §11 끝).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.ml_relative_upside_features import CandidateFeatureRow

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ML_STATE_DIR = _PROJECT_ROOT / "state" / "ml"
SCORE_SNAPSHOT_PATH = _ML_STATE_DIR / "relative_upside_score_latest.json"
RUN_META_PATH = _ML_STATE_DIR / "relative_upside_score_run_latest.json"

SCORE_SNAPSHOT_SCHEMA = "relative_upside_score.v0"
RUN_META_SCHEMA = "relative_upside_score_run.v0"


# 사용자 화면 고지 문구 (지시문 §9 끝).
USER_NOTICE = (
    "상대상승 참고점수는 과거 데이터 기반의 후보 비교용 참고값이며, "
    "매수·매도 판단을 자동으로 제시하지 않습니다."
)


def build_reasons(row: CandidateFeatureRow) -> list[str]:
    """단일 후보의 점수 근거 — 기존 evidence 사람 언어 요약 (지시문 §8).

    최대 3개. 모델 내부 식별자 / loss / epoch / device 노출 0건.
    """
    reasons: list[str] = []

    # 1) 최근 5/10/20일 KODEX200 대비 성과 — 우위/중립/약세 1줄.
    ex5 = row.excess_return_5d
    ex10 = row.excess_return_10d
    ex20 = row.excess_return_20d
    if all(v is not None for v in (ex5, ex10, ex20)):
        # 우위 = 세 값 모두 > 0. 약세 = 세 값 모두 < 0. 그 외 = 혼조.
        if ex5 > 0 and ex10 > 0 and ex20 > 0:  # type: ignore[operator]
            reasons.append("최근 5·10·20일 KODEX200 대비 성과가 우위입니다.")
        elif ex5 < 0 and ex10 < 0 and ex20 < 0:  # type: ignore[operator]
            reasons.append("최근 5·10·20일 KODEX200 대비 성과가 약세입니다.")
        else:
            reasons.append(
                "단기 초과수익은 양호하지만 중기 흐름은 추가 확인이 필요합니다."
            )

    # 2) 20일 고점 대비 하락폭 (drawdown_20d).
    dd = row.drawdown_20d
    if dd is not None:
        # -2% 이내 = 제한적, -10% 이내 = 보통, 그 이하 = 큼.
        if dd > -0.02:
            reasons.append("최근 20일 고점 부근에서 거래되고 있습니다.")
        elif dd > -0.10:
            reasons.append("최근 20일 고점 대비 하락폭이 제한적입니다.")
        else:
            reasons.append("최근 20일 고점 대비 하락폭을 함께 확인하세요.")

    # 3) 데이터 품질 — 본 STEP 에서는 feature 가 모두 채워졌으면 "정상", 아니면
    #    "일부 확인 필요". data_quality_flag 는 compute_topn 에 더 정교한 정보가
    #    있으나 본 STEP 범위 외 (지시문 §13 포함 범위 — drawdown / score / 근거).
    feature_complete = all(
        v is not None
        for v in (
            row.return_5d,
            row.return_10d,
            row.return_20d,
            row.excess_return_5d,
            row.excess_return_10d,
            row.excess_return_20d,
            row.drawdown_20d,
        )
    )
    if feature_complete:
        # 첫 두 reason 이 모두 채워진 경우만 3번째 추가.
        if len(reasons) < 3:
            reasons.append("데이터 품질 상태가 정상입니다.")
    else:
        reasons.append("일부 데이터 확인이 필요합니다.")

    return reasons[:3]


def build_score_snapshot(
    *,
    asof_date: str,
    generated_at: str,
    status: str,
    display_scores: dict[str, float],
    raw_scores: dict[str, float],
    feature_rows: list[CandidateFeatureRow],
    simple_excess_return_ranking: list[tuple[str, Optional[float]]],
) -> dict[str, Any]:
    """점수 snapshot JSON dict.

    candidates 배열은 ticker → display_score / raw_score / drawdown_20d /
    excess_return_5/10/20d / reasons 를 포함. UI 가 점수와 근거를 함께 보여주는
    데 필요한 항목만 노출 (모델 내부 feature vector / loss / device 노출 X).
    """
    by_ticker: dict[str, CandidateFeatureRow] = {r.ticker: r for r in feature_rows}

    candidates_block: list[dict[str, Any]] = []
    for ticker in sorted(by_ticker.keys()):
        row = by_ticker[ticker]
        display = display_scores.get(ticker)
        raw = raw_scores.get(ticker)
        candidates_block.append(
            {
                "ticker": ticker,
                "asof_date": row.asof_date,
                "relative_upside_score": display,
                "relative_upside_raw_prediction": raw,
                "drawdown_20d": row.drawdown_20d,
                "excess_return_5d": row.excess_return_5d,
                "excess_return_10d": row.excess_return_10d,
                "excess_return_20d": row.excess_return_20d,
                "relative_upside_reasons": build_reasons(row),
            }
        )

    # 단순 20일 초과수익 순위 비교 기록 (지시문 AC-5).
    comparison_block: list[dict[str, Any]] = []
    simple_rank_map: dict[str, int] = {
        ticker: i + 1
        for i, (ticker, _) in enumerate(simple_excess_return_ranking)
        if ticker is not None
    }
    # ML 점수 기준 순위 (display_score 내림차순. None 은 뒤로).
    ml_rank_items = sorted(display_scores.items(), key=lambda kv: kv[1], reverse=True)
    ml_rank_map = {ticker: i + 1 for i, (ticker, _) in enumerate(ml_rank_items)}
    for ticker in sorted(set(simple_rank_map.keys()) | set(ml_rank_map.keys())):
        comparison_block.append(
            {
                "ticker": ticker,
                "simple_excess_return_20d_rank": simple_rank_map.get(ticker),
                "ml_relative_upside_score_rank": ml_rank_map.get(ticker),
            }
        )

    return {
        "schema_version": SCORE_SNAPSHOT_SCHEMA,
        "status": status,
        "asof_date": asof_date,
        "generated_at": generated_at,
        "user_notice": USER_NOTICE,
        "candidates": candidates_block,
        "simple_vs_ml_rank_comparison": comparison_block,
    }


def build_run_meta(
    *,
    asof_date: str,
    generated_at: str,
    status: str,
    train_result: Optional[Any],  # TrainResult — circular import 방지.
    candidate_count: int,
    scored_candidate_count: int,
    snapshot_path: str,
    feature_columns: tuple[str, ...],
    error: Optional[str],
) -> dict[str, Any]:
    """실행 메타 JSON dict. raw prediction 은 score snapshot 에만 보관."""
    meta: dict[str, Any] = {
        "schema_version": RUN_META_SCHEMA,
        "status": status,
        "asof_date": asof_date,
        "generated_at": generated_at,
        "snapshot_path": snapshot_path,
        "feature_columns": list(feature_columns),
        "candidate_count": candidate_count,
        "scored_candidate_count": scored_candidate_count,
        "error": error,
    }
    if train_result is not None:
        meta["model"] = {
            "model_name": "relative_upside_v0_linear",
            "train_row_count": train_result.train_row_count,
            "test_row_count": train_result.test_row_count,
            "train_date_range": list(train_result.train_date_range),
            "test_date_range": list(train_result.test_date_range),
            "train_loss_final": train_result.train_loss_final,
            "test_loss_final": train_result.test_loss_final,
            "epochs": train_result.epochs,
            "learning_rate": train_result.learning_rate,
            "device_name": train_result.device_name,
            "cuda_available": train_result.cuda_available,
            "gpu_execution_used": train_result.gpu_execution_used,
            "train_seconds": train_result.train_seconds,
        }
    return meta


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """tmp + replace 로 atomic write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def save_score_snapshot(snapshot: dict[str, Any]) -> Path:
    _atomic_write_json(SCORE_SNAPSHOT_PATH, snapshot)
    return SCORE_SNAPSHOT_PATH


def save_run_meta(meta: dict[str, Any]) -> Path:
    _atomic_write_json(RUN_META_PATH, meta)
    return RUN_META_PATH


def load_score_snapshot() -> Optional[dict[str, Any]]:
    """frontend 응답 합성용 read-only. 파일 없으면 None."""
    if not SCORE_SNAPSHOT_PATH.exists():
        return None
    try:
        data = json.loads(SCORE_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("score snapshot read 실패: %s", type(e).__name__)
        return None
    if not isinstance(data, dict):
        return None
    return data


def now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat()
