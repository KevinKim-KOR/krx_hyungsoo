"""JSON 파일 기반 run 저장소.

state/runs/{run_id}.json 형태로 보관. POC 단계이므로 가벼운 파일 IO 만 사용.
MongoDB/SQLite 도입은 금지 (KS-9, 이식금지 1번 준수).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.models import Run

STORE_DIR = Path("state/runs")


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
