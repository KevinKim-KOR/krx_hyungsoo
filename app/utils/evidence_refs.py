"""
Evidence Refs Utility (C-P.32)

Generates evidence_refs arrays for receipts and postmortems.
All refs are RAW_PATH_ONLY format for C-P.30 Resolver compatibility.
"""

from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).parent.parent.parent

# Core refs (always included if exist)
EVIDENCE_INDEX_LATEST = "reports/ops/evidence/index/evidence_index_latest.json"

# Push refs
PUSH_REFS = [
    "reports/ops/push/send/send_latest.json",
    "reports/ops/push/outbox/outbox_latest.json",
    "reports/ops/push/preview/preview_latest.json",
    "reports/ops/secrets/self_test_latest.json",
]

# Ops refs
OPS_REFS = [
    "reports/ops/scheduler/latest/ops_run_latest.json",
    "reports/ops/push/postmortem/postmortem_latest.json",
    "reports/ops/push/live_fire/live_fire_latest.json",
]

# Phase C refs



def add_if_exists(paths: List[str]) -> List[str]:
    """Filter paths to only those that exist, remove duplicates."""
    result = []
    seen = set()
    for p in paths:
        if p in seen:
            continue
        seen.add(p)
        full_path = BASE_DIR / p
        if full_path.exists():
            result.append(p)
    return result


def build_core_refs() -> List[str]:
    """Build core refs (evidence_index_latest)."""
    return add_if_exists([EVIDENCE_INDEX_LATEST])


def build_push_refs() -> List[str]:
    """Build push-related refs + core."""
    paths = [EVIDENCE_INDEX_LATEST] + PUSH_REFS
    return add_if_exists(paths)


def build_postmortem_refs() -> List[str]:
    """Build postmortem-related refs + core."""
    paths = [EVIDENCE_INDEX_LATEST] + OPS_REFS + PUSH_REFS[:2]  # send_latest, outbox_latest
    return add_if_exists(paths)


def build_ops_run_refs() -> List[str]:
    """Build ops run receipt refs + core."""
    paths = [EVIDENCE_INDEX_LATEST] + OPS_REFS + PHASE_C_REFS
    return add_if_exists(paths)


def build_execution_receipt_refs() -> List[str]:
    """Build execution receipt refs + core."""
    paths = [EVIDENCE_INDEX_LATEST] + PHASE_C_REFS
    return add_if_exists(paths)


def build_ticket_receipt_refs() -> List[str]:
    """Build ticket receipt refs + core."""
    paths = [EVIDENCE_INDEX_LATEST, "reports/phase_c/latest/recon_summary.json"]
    return add_if_exists(paths)
