"""JSON 파일 기반 run 저장소.

state/runs/{run_id}.json 형태로 보관. POC 단계이므로 가벼운 파일 IO 만 사용.
MongoDB/SQLite 도입은 금지 (KS-9, 이식금지 1번 준수).

POC1 Step 3 추가:
- HANDOFF_STAGING_DIR: SCP 전송 전 로컬에 임시로 만드는 handoff artifact
  (1 run = 1 file). 전송 성공 후 HANDOFF_PROCESSED_DIR 로 이동
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models import Run

STORE_DIR = Path("state/runs")
HANDOFF_STAGING_DIR = Path("state/poc1_handoff")
HANDOFF_PROCESSED_DIR = Path("state/poc1_handoff_processed")


def _ensure_dir() -> None:
    STORE_DIR.mkdir(parents=True, exist_ok=True)


def save(run: Run) -> None:
    _ensure_dir()
    path = STORE_DIR / f"{run.run_id}.json"
    path.write_text(
        json.dumps(run.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load(run_id: str) -> Run:
    path = STORE_DIR / f"{run_id}.json"
    if not path.exists():
        raise KeyError(f"run_id not found: {run_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return Run.from_dict(data)


def list_runs() -> list[Run]:
    _ensure_dir()
    runs: list[Run] = []
    for p in sorted(STORE_DIR.glob("*.json"), reverse=True):
        data = json.loads(p.read_text(encoding="utf-8"))
        runs.append(Run.from_dict(data))
    return runs


def write_handoff_artifact(run: Run, approved_at: str) -> Path:
    """SCP 전송 전 로컬 staging artifact 를 작성하고 경로를 돌려준다.

    설계자 결정 handoff 규약:
    - 필수: run_id / asof / draft_payload
    - 보조: approved_at
    - 1 run = 1 file. JSON 포맷.
    """
    HANDOFF_STAGING_DIR.mkdir(parents=True, exist_ok=True)
    artifact: dict[str, Any] = {
        "run_id": run.run_id,
        "asof": run.asof,
        "approved_at": approved_at,
        "draft_payload": run.draft_payload,
    }
    path = HANDOFF_STAGING_DIR / f"{run.run_id}.json"
    path.write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def archive_handoff_artifact(run_id: str) -> None:
    """전송 성공한 staging artifact 를 processed/ 로 이동한다.

    실패 시(파일 없음 등) 조용히 무시 — handoff 자체의 실패는
    delivery 레이어 책임이며 store 는 단순 파일 이동만 담당.
    """
    src = HANDOFF_STAGING_DIR / f"{run_id}.json"
    if not src.exists():
        return
    HANDOFF_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    dst = HANDOFF_PROCESSED_DIR / f"{run_id}.json"
    src.replace(dst)
