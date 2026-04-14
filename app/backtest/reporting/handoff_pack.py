#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/handoff_pack.py — P210-STEP10Z-2 curated handoff pack

reports/handoff/latest/ 에 AI Agent/설계자 전달용 최소 첨부 묶음을
canonical source 로부터 mirror + provenance 기록 형태로 생성한다.

핵심 원칙:
- 새 truth source 금지. 모든 값은 canonical source 에서만 유도.
- UI 는 handoff 경로를 절대 읽지 않음.
- source 검증 실패 시 즉시 fail-loud (RuntimeError).
- mirror 는 byte_copy (json/csv/md) 또는 canonical_json_emit 만 허용.

단일 책임: canonical → handoff/latest mirror + source_index + manifest.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─── Canonical source 경로 고정 ─────────────────────────────────────
# reports/ 아래 상대 경로. project_root 에 붙여 절대화.
_CANONICAL_PATHS = {
    "current_strategy_state.json": "reports/tuning/current_strategy_state.json",
    "experiment_registry.json": "reports/tuning/experiment_registry.json",
    "decision_ledger.json": "reports/tuning/decision_ledger.json",
    "dynamic_evidence_latest.md": "reports/tuning/dynamic_evidence_latest.md",
    "backtest_result.json": "reports/backtest/latest/backtest_result.json",
}

# 챕터별 focus compare source
_CHAPTER_FOCUS_COMPARE = {
    "P210": "reports/tuning/predictive_risk_compare.json",
    "P209C": "reports/tuning/contextual_guard_compare.json",
    "P209B": "reports/tuning/toxic_filter_compare.json",
    "P208": "reports/tuning/holding_structure_compare.json",
}

# 챕터별 focus training report source (ML 챕터만)
_CHAPTER_FOCUS_TRAINING = {
    "P210": "reports/tuning/predictive_risk_training_report.json",
}


# ─── helper ──────────────────────────────────────────────────────────
def _sha256_of_file(path: Path) -> str:
    """파일 전체 SHA256 hex digest."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_source_timestamps(path: Path) -> Tuple[Optional[str], Optional[str]]:
    """JSON/md 파일에서 generated_at / asof 추출.

    JSON: top-level 또는 meta.* 에서 generated_at / asof 필드 검색.
    MD: 첫 30줄 내 "- generated_at:" / "- asof:" / "> asof:" 패턴 파싱.

    둘 다 None 일 수 있음 — fail-loud 책임은 _validate_source 가 진다.
    """
    generated_at: Optional[str] = None
    asof: Optional[str] = None
    if not path.exists():
        return None, None

    if path.suffix == ".json":
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                generated_at = data.get("generated_at")
                asof = data.get("asof")
                # nested meta.* 도 검색 (e.g. backtest_result.json)
                meta = data.get("meta")
                if isinstance(meta, dict):
                    if generated_at is None:
                        generated_at = meta.get("generated_at")
                    if asof is None:
                        asof = meta.get("asof")
        except Exception:
            pass
    elif path.suffix == ".md":
        try:
            with open(path, encoding="utf-8") as f:
                head = f.read(4096)
            for line in head.splitlines()[:30]:
                s = line.strip()
                if s.startswith("- generated_at:"):
                    generated_at = s.split(":", 1)[1].strip()
                elif s.startswith("- asof:"):
                    asof = s.split(":", 1)[1].strip()
                elif s.startswith("> asof:"):
                    asof = s.split(":", 1)[1].strip()
        except Exception:
            pass
    return generated_at, asof


def _validate_source(source_path: Path, logical_name: str) -> Tuple[str, str]:
    """source 파일 존재 + SHA256 + timestamp(generated_at OR asof) 검증.

    실패 시 fail-loud (RuntimeError). 통과 시 (generated_at, asof) 반환.
    둘 중 적어도 하나는 반드시 채워져 있어야 한다.
    """
    if not source_path.exists():
        raise RuntimeError(
            f"P210-STEP10Z-2: handoff canonical source 누락:"
            f" {logical_name} = {source_path}"
        )
    try:
        _sha256_of_file(source_path)
    except Exception as e:
        raise RuntimeError(
            f"P210-STEP10Z-2: handoff canonical source SHA256 계산 실패:"
            f" {logical_name} = {source_path}: {e}"
        ) from e

    generated_at, asof = _read_source_timestamps(source_path)
    if generated_at is None and asof is None:
        raise RuntimeError(
            f"P210-STEP10Z-2: handoff canonical source 에"
            f" generated_at / asof 둘 다 없음:"
            f" {logical_name} = {source_path}."
            f" provenance 추적 불가."
        )
    return generated_at, asof


def _detect_active_chapter(project_root: Path) -> str:
    """현재 활성 챕터 감지. predictive_risk_compare.json 이 있으면 P210.

    우선순위: P210 > P209C > P209B > P208.
    """
    for chap, rel in _CHAPTER_FOCUS_COMPARE.items():
        if (project_root / rel).exists():
            return chap
    raise RuntimeError(
        "P210-STEP10Z-2: 활성 챕터 focus compare 파일이 하나도 없음."
        f" 확인 대상: {list(_CHAPTER_FOCUS_COMPARE.values())}"
    )


# ─── mirror 실행 ────────────────────────────────────────────────────
def _rel_to_root(path: Path, project_root: Path) -> str:
    """모든 provenance 경로를 repo-root 기준 POSIX 상대경로로 정규화."""
    return path.resolve().relative_to(project_root.resolve()).as_posix()


def _mirror_file(
    source_path: Path,
    handoff_path: Path,
    logical_name: str,
    chapter_tag: str,
    copied_at: str,
    project_root: Path,
) -> Dict[str, Any]:
    """source 파일을 handoff 경로로 byte_copy + provenance entry 반환.

    경로 정규화: handoff_path / source_path 모두 repo-root 기준 POSIX 표기.
    timestamp fail-loud: _validate_source 가 generated_at/asof 둘 다 없으면 raise.
    """
    generated_at, asof = _validate_source(source_path, logical_name)
    source_sha = _sha256_of_file(source_path)

    handoff_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, handoff_path)

    copy_sha = _sha256_of_file(handoff_path)
    # byte_copy 모드에서 SHA 가 일치하지 않으면 무결성 실패
    if copy_sha != source_sha:
        raise RuntimeError(
            f"P210-STEP10Z-2: handoff mirror 무결성 실패 (SHA mismatch):"
            f" {logical_name}"
            f" source={source_sha[:12]} copy={copy_sha[:12]}"
        )

    return {
        "handoff_path": _rel_to_root(handoff_path, project_root),
        "source_path": _rel_to_root(source_path, project_root),
        "source_generated_at": generated_at,
        "source_asof": asof,
        "source_sha256": source_sha,
        "copied_at": copied_at,
        "copy_sha256": copy_sha,
        "copy_mode": "byte_copy",
        "chapter_tag": chapter_tag,
    }


# ─── handoff_manifest 구성 ───────────────────────────────────────────
def _build_manifest(
    project_root: Path,
    chapter_tag: str,
    provenance_entries: List[Dict[str, Any]],
    include_training_report: bool,
) -> Dict[str, Any]:
    """handoff_manifest.json payload. canonical 값에서만 유도."""
    # current_strategy_state.json 에서 main/research/next 요약 추출
    state_path = project_root / _CANONICAL_PATHS["current_strategy_state.json"]
    if not state_path.exists():
        raise RuntimeError(
            "P210-STEP10Z-2: current_strategy_state.json canonical sibling 미생성."
            " experiment_registry generator 가 먼저 실행되어야 함."
        )
    with open(state_path, encoding="utf-8") as f:
        state = json.load(f)

    required = [
        "current_strategy_state.json",
        "experiment_registry.json",
        "dynamic_evidence_latest.md",
        "backtest_result.json",
        "chapter_focus_compare.json",
    ]
    optional = ["decision_ledger.json"]
    if include_training_report:
        optional.append("chapter_focus_training_report.json")

    return {
        "pack_generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "chapter_tag": chapter_tag,
        "main_run_summary": state["current_main_run"],
        "research_candidate_summary": state["current_research_candidate"],
        "next_planned_chapter": state["next_planned_chapter"],
        "required_attachments": required,
        "optional_attachments": optional,
        "notes": [
            "handoff/latest 는 canonical 의 read-only mirror. UI 는 읽지 않음.",
            "모든 값은 reports/tuning/* 및 reports/backtest/latest/* 에서 유도.",
            "provenance 는 source_index.json 참조.",
            "새 truth source 생성 금지.",
        ],
        "provenance_entry_count": len(provenance_entries),
    }


# ─── Public API ──────────────────────────────────────────────────────
def generate_handoff_pack(project_root: Path) -> None:
    """reports/handoff/latest/ 에 curated mirror + manifest + index 생성.

    실행 시점: canonical 산출물 생성이 모두 끝난 뒤 마지막에 호출.
    실패 시 RuntimeError 로 즉시 중단 (fail-loud).
    """
    handoff_dir = project_root / "reports" / "handoff" / "latest"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    copied_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")

    # 1. 활성 챕터 감지
    chapter_tag = _detect_active_chapter(project_root)
    include_training = chapter_tag in _CHAPTER_FOCUS_TRAINING

    # 2. mirror 수행 + provenance 수집
    provenance_entries: List[Dict[str, Any]] = []

    # 2a. 고정 canonical 5개
    for logical_name, rel_path in _CANONICAL_PATHS.items():
        src = project_root / rel_path
        dst = handoff_dir / logical_name
        entry = _mirror_file(
            src, dst, logical_name, chapter_tag, copied_at, project_root
        )
        provenance_entries.append(entry)

    # 2b. chapter_focus_compare
    focus_compare_rel = _CHAPTER_FOCUS_COMPARE[chapter_tag]
    focus_compare_src = project_root / focus_compare_rel
    focus_compare_dst = handoff_dir / "chapter_focus_compare.json"
    entry = _mirror_file(
        focus_compare_src,
        focus_compare_dst,
        "chapter_focus_compare.json",
        chapter_tag,
        copied_at,
        project_root,
    )
    provenance_entries.append(entry)

    # 2c. chapter_focus_training_report (ML 챕터만)
    if include_training:
        training_rel = _CHAPTER_FOCUS_TRAINING[chapter_tag]
        training_src = project_root / training_rel
        training_dst = handoff_dir / "chapter_focus_training_report.json"
        entry = _mirror_file(
            training_src,
            training_dst,
            "chapter_focus_training_report.json",
            chapter_tag,
            copied_at,
            project_root,
        )
        provenance_entries.append(entry)

    # 3. source_index.json
    (handoff_dir / "source_index.json").write_text(
        json.dumps(
            {
                "generated_at": copied_at,
                "chapter_tag": chapter_tag,
                "entries": provenance_entries,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # 4. handoff_manifest.json
    manifest = _build_manifest(
        project_root=project_root,
        chapter_tag=chapter_tag,
        provenance_entries=provenance_entries,
        include_training_report=include_training,
    )
    (handoff_dir / "handoff_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    logger.info(
        f"[P210-STEP10Z-2] handoff pack 생성 완료:"
        f" chapter={chapter_tag}, files={len(provenance_entries)},"
        f" training={include_training}"
    )
