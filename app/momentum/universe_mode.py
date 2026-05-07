"""POC2 Step 5C — Momentum Engine universe mode (점수 미부여, latest artifact 저장).

설계자 결정 (Step 5C 지시문):
- universe candidates 는 외부에서 주입된 manual seed 만 사용. 엔진이 직접 수집하지
  않는다 (Step5A §3.2 universe mode 책임 범위 명확화).
- 이번 Step 에서는 점수 미부여: score_result.is_scored = False, rank 생성 안 함.
- reason_text 에는 "아직 모멘텀 산식 미적용" 취지가 들어간다.
- 결과는 state/universe/universe_momentum_latest.json (latest 1건 덮어쓰기) 에 저장.
  history / DB / dataset 절대 미도입.
- summary.source / source_freshness / staleness_days 는 seed 검증 결과를 그대로 반영.
- candidate_id 는 결정론적: universe|{ticker}|{universe_group}|{sector_or_theme}.
  optional 필드가 없으면 빈 토큰으로 채운다.

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
