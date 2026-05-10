"""POC2 Step 5C + Step 6 — Momentum Engine universe mode.

설계자 결정 (Step 5C 지시문):
- universe candidates 는 외부에서 주입된 manual seed 만 사용. 엔진이 직접 수집하지
  않는다 (Step5A §3.2 universe mode 책임 범위 명확화).
- 결과는 state/universe/universe_momentum_latest.json (latest 1건 덮어쓰기) 에 저장.
  history / DB / dataset 절대 미도입.
- summary.source / source_freshness / staleness_days 는 seed 검증 결과를 그대로 반영.
- candidate_id 는 결정론적: universe|{ticker}|{universe_group}|{sector_or_theme}.

설계자 결정 (Step 6 — Universe Momentum Formula Minimal Scoring):
- universe candidates 에 pykrx 기반 1개월 기간 수익률 (one_month_return_pct) 1개를
  적용한다. 복합 점수체계 / Top N / BUY·SELL / 리밸런싱 일체 미도입.
- score_result.is_scored=True 후보에는 score_value (%) / score_unit ("%") /
  score_basis_text / ranking_basis ("one_month_return_pct") 가 포함된다.
- price_history_basis (base_date / base_close / latest_date / latest_close) 가
  scored candidate 에 포함된다. unscored 후보는 exclusion_reason 만 기록.
- summary 에 refresh_status (ok / partial / failed) / data_source ("pykrx") /
  score_basis ("one_month_return_pct") / lookback_days / fetch_window_days / top_candidate.
- rank 는 scored 후보에만 부여 (1-based, score_value 내림차순).

이 모듈은 Step5B 의 holdings_mode 와 동일한 ENGINE_ID / ENGINE_VERSION 을 사용한다
(같은 Momentum Engine 의 다른 mode 일 뿐 — Step5A 결정).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

from app.momentum.holdings_mode import ENGINE_ID, ENGINE_VERSION
from app.universe_seed import UniverseSeed, UniverseSeedItem

MODE_UNIVERSE = "universe"

LATEST_ARTIFACT_DIR = Path("state/universe")
LATEST_ARTIFACT_FILE = LATEST_ARTIFACT_DIR / "universe_momentum_latest.json"

CANDIDATE_REASON_TEXT = (
    "외부 ETF 후보군으로 등록된 항목입니다. 아직 모멘텀 산식은 적용하지 않았습니다."
)
SCORE_BASIS_TEXT = "universe 후보군 입력 확인 단계 — 아직 모멘텀 산식 미적용"

# Step 6 — pykrx 1개월 수익률 score 라벨/식별자.
DATA_SOURCE_PYKRX = "pykrx"
SCORE_BASIS_ONE_MONTH = "one_month_return_pct"
SCORE_BASIS_TEXT_ONE_MONTH = "pykrx 가격 히스토리 기반 1개월 수익률"
SCORED_CANDIDATE_REASON_TEXT = (
    "pykrx 가격 히스토리 기준 최근 1개월 수익률이 계산되었습니다."
)


def _candidate_id(item: UniverseSeedItem) -> str:
    """결정론적 candidate_id. optional 필드는 빈 토큰으로 채워 충돌 방지.

    형식: universe|{ticker}|{universe_group}|{sector_or_theme}
    """
    ug = item.universe_group or ""
    st = item.sector_or_theme or ""
    return f"universe|{item.ticker}|{ug}|{st}"


def _build_candidate(item: UniverseSeedItem) -> dict[str, Any]:
    out: dict[str, Any] = {
        "candidate_id": _candidate_id(item),
        "ticker": item.ticker,
        "name": item.name,
        "mode": MODE_UNIVERSE,
        "is_available": True,
        "score_result": {
            "is_scored": False,
            "score_basis_text": SCORE_BASIS_TEXT,
        },
        "reason_text": CANDIDATE_REASON_TEXT,
        "input_basis": {"source": "manual_seed"},
    }
    if item.universe_group is not None:
        out["universe_group"] = item.universe_group
    if item.sector_or_theme is not None:
        out["sector_or_theme"] = item.sector_or_theme
    return out


def _build_summary(seed: UniverseSeed, total: int) -> dict[str, Any]:
    if seed.source_freshness == "stale":
        reason = (
            "수동 universe 후보군 기준일이 30일을 초과했습니다. "
            "후보군은 입력 확인했지만 최신성 검토가 필요합니다."
        )
    else:
        reason = (
            f"수동 universe 후보군 {total}개를 입력 확인했습니다. "
            "아직 모멘텀 산식은 적용하지 않았습니다."
        )
    return {
        "total_candidates": total,
        "scored_candidates": 0,
        "excluded_candidates": 0,
        "source": seed.source,
        "source_freshness": seed.source_freshness,
        "staleness_days": seed.staleness_days,
        "summary_reason_text": reason,
    }


def build_universe_momentum_result(seed: UniverseSeed) -> dict[str, Any]:
    """검증된 UniverseSeed → universe mode momentum_result dict.

    반환 dict 의 mode 는 "universe", asof 는 seed.asof, summary 는 seed 의 source /
    source_freshness / staleness_days 를 그대로 반영. score 미부여, rank 미생성.
    """
    candidates = [_build_candidate(it) for it in seed.items]
    summary = _build_summary(seed, total=len(candidates))
    return {
        "engine_id": ENGINE_ID,
        "engine_version": ENGINE_VERSION,
        "mode": MODE_UNIVERSE,
        "asof": seed.asof,
        "summary": summary,
        "candidates": candidates,
    }


# ─── Step 6: scored variant ─────────────────────────────────────────────


def _build_scored_candidate(
    score: Any,  # CandidateScore (avoid circular import — duck-typed)
) -> dict[str, Any]:
    """CandidateScore → universe candidate dict (Step6 scored variant).

    is_scored=True 인 경우:
      - score_result 에 score_value / score_unit / score_basis_text / ranking_basis 포함
      - price_history_basis 포함
      - reason_text 는 "pykrx 가격 히스토리 기준 최근 1개월 수익률이 계산되었습니다."
    is_scored=False 인 경우:
      - score_result.is_scored=False + score_basis_text + exclusion_reason
      - price_history_basis 포함 안 함
      - reason_text 는 후보 입력 확인 + 사유.
    """
    item = score.item
    base: dict[str, Any] = {
        "candidate_id": _candidate_id(item),
        "ticker": item.ticker,
        "name": item.name,
        "mode": MODE_UNIVERSE,
        "is_available": True,
        "input_basis": {"source": "manual_seed"},
    }
    if item.universe_group is not None:
        base["universe_group"] = item.universe_group
    if item.sector_or_theme is not None:
        base["sector_or_theme"] = item.sector_or_theme

    if score.is_scored and score.basis is not None and score.score_value is not None:
        base["score_result"] = {
            "is_scored": True,
            "score_value": round(score.score_value, 4),
            "score_unit": "%",
            "score_basis_text": SCORE_BASIS_TEXT_ONE_MONTH,
            "ranking_basis": SCORE_BASIS_ONE_MONTH,
        }
        base["price_history_basis"] = {
            "base_date": score.basis.base_date,
            "base_close": score.basis.base_close,
            "latest_date": score.basis.latest_date,
            "latest_close": score.basis.latest_close,
        }
        base["reason_text"] = SCORED_CANDIDATE_REASON_TEXT
    else:
        base["score_result"] = {
            "is_scored": False,
            "score_basis_text": SCORE_BASIS_TEXT_ONE_MONTH,
            "exclusion_reason": score.exclusion_reason or "원인 불명",
        }
        base["reason_text"] = (
            "외부 ETF 후보로 등록되었으나 1개월 수익률 계산이 불가했습니다 "
            f"({score.exclusion_reason or '원인 불명'})."
        )
    return base


def _assign_ranks(candidates: list[dict[str, Any]]) -> None:
    """scored candidates 만 score_value 내림차순으로 1-based rank 부여.

    Tie-break: score 동점 시 ticker 오름차순. is_scored=False 후보에는 rank 키 미부여 (AC-13).
    """
    scored = [c for c in candidates if c["score_result"].get("is_scored") is True]
    scored.sort(key=lambda c: (-c["score_result"]["score_value"], c["ticker"]))
    for rank, cand in enumerate(scored, start=1):
        cand["rank"] = rank


def _build_top_candidate_dict(top: dict[str, Any]) -> dict[str, Any]:
    """summary.top_candidate 에 들어갈 축약 dict — 후보 1건 요약.

    AC-14 기준의 최소 정보. price_history_basis 는 그대로 포함 (UI 가 latest_date 사용).
    """
    out = {
        "candidate_id": top["candidate_id"],
        "ticker": top["ticker"],
        "name": top["name"],
        "score_result": top["score_result"],
        "reason_text": top.get("reason_text"),
    }
    if "price_history_basis" in top:
        out["price_history_basis"] = top["price_history_basis"]
    if "rank" in top:
        out["rank"] = top["rank"]
    return out


def build_universe_momentum_result_scored(
    seed: UniverseSeed,
    scores: list[Any],  # list[CandidateScore]
    refresh_status: str,
    failure_summary_reason: Optional[str] = None,
    lookback_days: int = 30,
    fetch_window_days: int = 45,
) -> dict[str, Any]:
    """Step 6 — pykrx scoring 결과를 반영한 universe momentum_result dict.

    refresh_status: ok | partial | failed.
    failure_summary_reason: 전체 실패 시 summary_reason_text 로 사용 (호출자가 결정).
    """
    candidates = [_build_scored_candidate(s) for s in scores]
    _assign_ranks(candidates)

    scored_count = sum(
        1 for c in candidates if c["score_result"].get("is_scored") is True
    )
    excluded_count = len(candidates) - scored_count

    summary: dict[str, Any] = {
        "total_candidates": len(candidates),
        "scored_candidates": scored_count,
        "excluded_candidates": excluded_count,
        "source": seed.source,
        "source_freshness": seed.source_freshness,
        "staleness_days": seed.staleness_days,
        "refresh_status": refresh_status,
        "data_source": DATA_SOURCE_PYKRX,
        "score_basis": SCORE_BASIS_ONE_MONTH,
        "lookback_days": lookback_days,
        "fetch_window_days": fetch_window_days,
    }

    # top_candidate 는 scored 후보 중 rank=1 인 것. 없으면 키 미포함.
    top = next(
        (c for c in candidates if c.get("rank") == 1),
        None,
    )
    if top is not None:
        summary["top_candidate"] = _build_top_candidate_dict(top)
        summary["summary_reason_text"] = (
            f"{top['name']} 가 1개월 수익률 기준 가장 높습니다 "
            f"({top['score_result']['score_value']}%, asof {seed.asof})."
        )
    else:
        # 전체 실패 — failure_summary_reason 가 있으면 사용, 없으면 기본 문구.
        summary["summary_reason_text"] = failure_summary_reason or (
            f"pykrx 가격 데이터 부족으로 1개월 점검값을 계산하지 못했습니다 "
            f"(asof {seed.asof})."
        )

    return {
        "engine_id": ENGINE_ID,
        "engine_version": ENGINE_VERSION,
        "mode": MODE_UNIVERSE,
        "asof": seed.asof,
        "summary": summary,
        "candidates": candidates,
    }


def _atomic_write(path: Path, text: str) -> None:
    """임시 파일에 쓴 후 os.replace 로 교체 — market_cache 와 동일 패턴."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=".universe_momentum_latest.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def save_latest_artifact(
    momentum_result: dict[str, Any],
    path: Optional[Path] = None,
) -> Path:
    """universe momentum_result 를 latest 1건 덮어쓰기 파일로 저장.

    path 미지정 시 모듈 attribute LATEST_ARTIFACT_FILE 을 호출 시점에 lookup —
    테스트에서 monkeypatch 로 경로를 격리할 수 있도록 default 인자 평가 시점
    이슈를 회피한다 (universe_seed.load_universe_seed 와 동일 패턴).
    """
    target = path or LATEST_ARTIFACT_FILE
    text = json.dumps(momentum_result, indent=2, ensure_ascii=False)
    _atomic_write(target, text)
    return target
