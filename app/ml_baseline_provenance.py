"""POC4-01 — ML baseline 실행 출처(provenance) 기록 (설계자 결정 1·3 — 2026-09-23).

새 기준선은 "어떤 입력 + 어떤 코드 + 어떤 환경 + 어떤 인자로 만든 결과인가" 를
한 세트로 고정한다. 본 모듈은 그 기록을 만든다 — 평가 로직은 건드리지 않는다.

- 코드: git commit, `app/`·`scripts/`·requirements.txt 의 미커밋 변경 여부(게이트),
  실제로 import 된 프로젝트 모듈 전부의 raw sha256 과 정규화 AST hash
  (docstring·주석·서식 제외 — 주석 정정이 로직을 바꾸지 않았음을 보인다)
- 환경: Python · 주요 의존성 버전 · SQLite 버전 · requirements.txt sha256
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata as metadata
import json
import platform
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Optional

from app.ml_baseline_snapshot import SnapshotSession
from app.ml_score_validity_eval import (
    E1_SNAPSHOT_ASOF,
    PHASE_EVALUATION,
    PHASE_WARMUP,
    price_projection_sha256,
)
from app.ml_score_validity_report import now_iso

RUN_MANIFEST_SCHEMA = "ml_baseline_run_manifest.v1"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 고정 모듈 — 이 세 파일이 baseline 모델의 정의다 (기존 frozen_descriptor 와 같은 목록).
FROZEN_MODULES = (
    "app/ml_relative_upside_features.py",
    "app/ml_relative_upside_model.py",
    "app/ml_relative_upside_score.py",
)
# 코드 게이트 — 결과에 영향을 줄 수 있는 코드 전부. 목록을 손으로 고르면 빠뜨린다
# (예: regime 판정의 app/market_regime.py) → 폴더 단위로 본다.
CODE_GATE_PATHS = ("app", "scripts", "requirements.txt")
# 평가기 핵심 모듈 — 실제 import 된 모듈과 합쳐 hash 를 기록한다.
EVALUATOR_MODULES = (
    "scripts/run_ml_score_validity_eval_v1.py",
    "app/ml_score_validity_eval.py",
    "app/ml_score_validity_metrics.py",
    "app/ml_score_validity_report.py",
    "app/ml_score_validity_screen.py",
    "app/ml_baseline_snapshot.py",
    "app/ml_baseline_provenance.py",
    "app/market_data_store.py",
    "app/market_topn.py",
    "app/market_topn_helpers.py",
)
PACKAGES = ("torch", "numpy", "pandas", "scipy", "scikit-learn")
NORMALIZED_AST_DEFINITION = (
    "ast.parse → 모듈·클래스·함수 첫 문장 docstring 제거 → "
    "ast.dump(annotate_fields=True, include_attributes=False) 의 sha256. "
    "주석·빈 줄·서식·docstring 변경은 hash 를 바꾸지 않는다."
)


def raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized_ast_sha256_from_source(source: str) -> str:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                node.body = body[1:] or [ast.Pass()]
    dumped = ast.dump(tree, annotate_fields=True, include_attributes=False)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


def file_hashes(paths: Iterable[str], root: Path = PROJECT_ROOT) -> dict:
    out: dict = {}
    for rel in paths:
        path = root / rel
        out[rel] = {
            "raw_sha256": raw_sha256(path),
            "normalized_ast_sha256": normalized_ast_sha256_from_source(
                path.read_text(encoding="utf-8")
            ),
        }
    return out


def _git(args: list[str], root: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout


def git_state(paths: Iterable[str], root: Path = PROJECT_ROOT) -> dict:
    """HEAD 와, 기록 대상 파일 중 HEAD 와 다른(수정·미추적) 파일 목록."""
    try:
        head = _git(["rev-parse", "HEAD"], root).strip()
        status = _git(
            ["status", "--porcelain", "--untracked-files=all", "--", *paths], root
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        return {"head": None, "code_clean": False, "error": str(exc)}
    dirty = sorted(line[3:] for line in status.splitlines() if line.strip())
    return {"head": head, "code_clean": not dirty, "dirty_paths": dirty}


def environment(root: Path = PROJECT_ROOT) -> dict:
    packages: dict[str, Optional[str]] = {}
    for name in PACKAGES:
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    req = root / "requirements.txt"
    return {
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "hostname": socket.gethostname(),
        "sqlite": sqlite3.sqlite_version,
        "packages": packages,
        "requirements_txt_sha256": raw_sha256(req) if req.exists() else None,
    }


def loaded_project_modules(root: Path = PROJECT_ROOT) -> list[str]:
    """지금 프로세스에 import 된 `app/`·`scripts/` 아래 .py 파일 (상대 경로)."""
    out: set[str] = set()
    for module in list(sys.modules.values()):
        file = getattr(module, "__file__", None)
        if not file or not file.endswith(".py"):
            continue
        path = Path(file).resolve()
        for top in ("app", "scripts"):
            if path.is_relative_to(root / top):
                out.add(path.relative_to(root).as_posix())
    return sorted(out)


def evaluator_hashes(root: Path = PROJECT_ROOT) -> dict:
    paths = (set(EVALUATOR_MODULES) | set(loaded_project_modules(root))) - set(
        FROZEN_MODULES
    )
    return file_hashes(sorted(paths), root)


def code_provenance(root: Path = PROJECT_ROOT) -> dict:
    return {
        "git": git_state(CODE_GATE_PATHS, root),
        "gate_paths": list(CODE_GATE_PATHS),
        "frozen_modules": file_hashes(FROZEN_MODULES, root),
        "evaluator_modules": evaluator_hashes(root),
        "normalized_ast_definition": NORMALIZED_AST_DEFINITION,
    }


def node_info() -> dict:
    """실행 노드 정보 (PLAN §8.1) — run meta 용."""
    info = {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python": platform.python_version(),
    }
    try:
        import torch

        info["torch"] = torch.__version__
        info["device"] = "cpu"
        info["cuda_available"] = torch.cuda.is_available()
    except Exception:  # noqa: BLE001
        pass
    return info


def build_frozen_descriptor(db_path: Path) -> dict:
    """PLAN §2.1 — 재현 기술자 6종. artifact 부재(C-1)를 대체한다."""
    return {
        "score_version": "relative_upside_score.v0",
        "model_name": "relative_upside_v0_linear",
        "module_sha256": {m: raw_sha256(PROJECT_ROOT / m) for m in FROZEN_MODULES},
        "price_projection_sha256_full": price_projection_sha256(db_path=db_path),
        "price_projection_sha256_e1_cutoff": price_projection_sha256(
            db_path=db_path, cutoff_date=E1_SNAPSHOT_ASOF
        ),
        "hyperparameters": {
            "seed": 42,
            "epochs": 200,
            "learning_rate": 0.001,
            "train_split_ratio": 0.8,
            "model": "nn.Linear(7,1)",
        },
    }


def write_run_manifest(
    path: Path,
    *,
    snap: SnapshotSession,
    code: dict,
    args: argparse.Namespace,
    per_date: list[dict],
    status: str,
    canonical: Optional[str],
    result_path: Path,
    meta_path: Path,
    started: str,
    elapsed_seconds: float,
) -> dict:
    """새 기준선 한 세트(입력·코드·환경·인자·결과·평가일)를 한 파일로 묶는다."""
    m = snap.manifest
    # 실행 중 늦게 import 된 모듈까지 포함하도록 끝에서 다시 잰다.
    code = {**code, "evaluator_modules": evaluator_hashes()}
    evaluation = [r["signal_date"] for r in per_date if r["phase"] == PHASE_EVALUATION]
    manifest = {
        "schema_version": RUN_MANIFEST_SCHEMA,
        "status": status,
        # 공식 기준선 = commit 과 같은 코드 · 전체 기간 · E1 포함.
        "official": bool(
            code["git"].get("code_clean") and not args.limit_dates and not args.skip_e1
        ),
        "dataset": {
            "baseline_id": m["baseline_id"],
            "manifest_path": str(snap.manifest_path),
            "manifest_sha256": snap.manifest_sha256,
            "manifest_canonical_sha256": snap.manifest_canonical_sha256,
            "dataset_sha256": m["files"]["dataset"]["sha256"],
            "e1_score_snapshot_sha256": m["files"]["e1_score_snapshot"]["sha256"],
            "schema_sha256": m["schema_sha256"],
            "data_cutoff": m["data_cutoff"],
        },
        "code": code,
        "environment": environment(),
        "run_arguments": dict(vars(args)),
        "evaluation": {
            "count": len(evaluation),
            "dates": evaluation,
            "warmup_dates": [
                r["signal_date"] for r in per_date if r["phase"] == PHASE_WARMUP
            ],
        },
        "result": (
            {
                "path": result_path.name,
                "file_sha256": raw_sha256(result_path),
                "canonical_sha256": canonical,
            }
            if result_path.exists()
            else None
        ),
        "run_meta": {"path": meta_path.name, "file_sha256": raw_sha256(meta_path)},
        "started_at": started,
        "finished_at": now_iso(),
        "elapsed_seconds": elapsed_seconds,
    }
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest
