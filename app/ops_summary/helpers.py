"""Ops Summary 유틸리티 함수."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from app.ops_summary.paths import (
    KST,
    FORBIDDEN_PREFIXES,
    OPS_RUN_LATEST,
    TICKET_RESULTS,
    OPS_RISK_WINDOW_DAYS,
    OPS_RISK_MAX_EVENTS,
    TICKET_FAIL_EXCLUDE_PREFIXES,
)


def sanitize_evidence_ref(ref: str) -> Optional[str]:
    """evidence_ref 정제"""
    if not ref or not isinstance(ref, str):
        return None
    cleaned = ref.strip()
    for prefix in FORBIDDEN_PREFIXES:
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix) :]
            break
    if ".." in cleaned or not cleaned:
        return None
    return cleaned


def safe_load_json(path: Path) -> Optional[Dict]:
    """JSON 파일 안전 로드"""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def count_jsonl_lines(path: Path) -> int:
    """JSONL 라인 수"""
    if not path.exists():
        return 0
    try:
        count = 0
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
        return count
    except Exception:
        return 0


def get_latest_ops_run() -> Optional[Dict]:
    """가장 최근에 실행된 daily ops run 스냅샷 로드"""
    if not OPS_RUN_LATEST.exists():
        return None
    snapshots = sorted(OPS_RUN_LATEST.glob("*.json"), reverse=True)
    if not snapshots:
        return None
    return safe_load_json(snapshots[0])


def get_tickets_summary() -> Dict[str, int]:
    """티켓 상태별 카운트 (전체)"""
    stats = {"open": 0, "in_progress": 0, "done": 0, "failed": 0, "blocked": 0}
    if TICKET_RESULTS.exists():
        with open(TICKET_RESULTS, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                    status = row.get("status", "").lower()
                    if status in stats:
                        stats[status] += 1
                except Exception:
                    pass
    return stats


def get_tickets_recent() -> Dict[str, Any]:
    """최근 N일간 티켓 통계 (Risk Window)"""
    now = datetime.now(KST)
    start_dt = now - timedelta(days=OPS_RISK_WINDOW_DAYS)

    stats = {
        "window_days": OPS_RISK_WINDOW_DAYS,
        "max_events": OPS_RISK_MAX_EVENTS,
        "start_at": start_dt.isoformat(),
        "end_at": now.isoformat(),
        "failed": 0,
        "excluded_cleanup_failed": 0,
        "blocked": 0,
        "done": 0,
        "in_progress": 0,
        "failed_line_refs": [],
    }

    if not TICKET_RESULTS.exists():
        return stats

    events = []
    line_num = 0
    with open(TICKET_RESULTS, "r", encoding="utf-8") as f:
        for line in f:
            line_num += 1
            try:
                row = json.loads(line)
                ts_str = row.get("timestamp") or row.get("finished_at") or ""
                if not ts_str:
                    continue

                # Simple ISO parsing (minimal)
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=now.tzinfo)

                if dt >= start_dt:
                    row["_line"] = line_num
                    events.append(row)
            except Exception:
                pass

    # Recent events only
    events.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
    events = events[:OPS_RISK_MAX_EVENTS]

    for row in events:
        status = row.get("status", "").lower()
        ticket_key = row.get("ticket_key", "")

        if status == "failed":
            # Exclude check
            is_excluded = False
            for prefix in TICKET_FAIL_EXCLUDE_PREFIXES:
                if prefix and ticket_key.startswith(prefix):
                    is_excluded = True
                    break

            if is_excluded:
                stats["excluded_cleanup_failed"] += 1
            else:
                stats["failed"] += 1
                ref = f"state/tickets/ticket_results.jsonl:line{row['_line']}"
                stats["failed_line_refs"].append(ref)
        elif status == "blocked":
            stats["blocked"] += 1
        elif status == "done":
            stats["done"] += 1
        elif status == "in_progress":
            stats["in_progress"] += 1

    return stats
