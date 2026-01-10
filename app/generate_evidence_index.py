"""
Evidence Index Generator (C-P.31)

Generates an index of all evidence items from various sources.
- Atomic write: .tmp → os.replace()
- No full JSONL load: uses linecache/enumerate
- Read-only: no engine execution
"""

import json
import hashlib
import os
import linecache
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

BASE_DIR = Path(__file__).parent.parent

# Output paths
EVIDENCE_INDEX_DIR = BASE_DIR / "reports" / "ops" / "evidence" / "index"
EVIDENCE_INDEX_LATEST = EVIDENCE_INDEX_DIR / "evidence_index_latest.json"
EVIDENCE_SNAPSHOTS_DIR = EVIDENCE_INDEX_DIR / "snapshots"

# Source files (strict allowlist)
SOURCES = {
    "ticket_receipts": BASE_DIR / "state" / "tickets" / "ticket_receipts.jsonl",
    "ops_run_latest": BASE_DIR / "reports" / "ops" / "scheduler" / "latest" / "ops_run_latest.json",
    "send_latest": BASE_DIR / "reports" / "ops" / "push" / "send" / "send_latest.json",
    "postmortem_latest": BASE_DIR / "reports" / "ops" / "push" / "postmortem" / "postmortem_latest.json",
    "self_test_latest": BASE_DIR / "reports" / "ops" / "secrets" / "self_test_latest.json",
    "recon_summary": BASE_DIR / "reports" / "phase_c" / "latest" / "recon_summary.json",
}

MAX_JSONL_LINES = 20  # 최근 N줄만 읽음


def generate_evidence_id(ref: str) -> str:
    """sha256(ref)[:12]"""
    return hashlib.sha256(ref.encode()).hexdigest()[:12]


def determine_severity(kind: str, data: Dict) -> str:
    """Determine severity based on data content"""
    if kind == "PUSH_POSTMORTEM":
        if data.get("overall_safety_status") not in [None, "SAFE"]:
            return "WARN"
    elif kind == "PUSH_SEND":
        if data.get("http_status") not in [None, 200]:
            return "WARN"
    elif kind == "OPS_RUN":
        status = data.get("overall_status")
        if status in ["STOPPED", "FAILED"]:
            return "ERROR"
        elif status == "BLOCKED":
            return "WARN"
    elif kind == "SECRETS_SELF_TEST":
        if data.get("result") not in [None, "OK", "PASS"]:
            return "WARN"
    return "INFO"


def read_jsonl_last_n_lines(path: Path, n: int) -> List[Dict]:
    """Read last N lines of JSONL without loading entire file"""
    if not path.exists():
        return []
    
    lines = []
    try:
        # Count total lines first
        line_count = 0
        with open(path, 'r', encoding='utf-8') as f:
            for _ in f:
                line_count += 1
        
        # Read last N lines using enumerate
        start_line = max(1, line_count - n + 1)
        with open(path, 'r', encoding='utf-8') as f:
            for idx, line in enumerate(f, start=1):
                if idx >= start_line:
                    try:
                        data = json.loads(line.strip())
                        data['_line_no'] = idx
                        lines.append(data)
                    except json.JSONDecodeError:
                        pass
    except Exception:
        pass
    
    return lines


def read_json_file(path: Path) -> Optional[Dict]:
    """Read JSON file if exists"""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def generate_evidence_index() -> Dict[str, Any]:
    """Generate the evidence index"""
    now = datetime.now()
    asof = now.isoformat()
    items: List[Dict] = []
    seen_refs = set()
    
    # 1. Ticket Receipts (JSONL, last N lines)
    ticket_lines = read_jsonl_last_n_lines(SOURCES["ticket_receipts"], MAX_JSONL_LINES)
    for line_data in reversed(ticket_lines):  # 최신 순
        line_no = line_data.get('_line_no', 0)
        ref = f"state/tickets/ticket_receipts.jsonl:line{line_no}"
        if ref in seen_refs:
            continue
        seen_refs.add(ref)
        
        items.append({
            "evidence_id": generate_evidence_id(ref),
            "created_at": line_data.get("created_at") or line_data.get("asof") or asof,
            "title": f"Ticket Receipt #{line_no}: {line_data.get('ticker', 'N/A')}",
            "kind": "TICKET_RECEIPT",
            "severity": determine_severity("TICKET_RECEIPT", line_data),
            "ref": ref,
            "tags": [line_data.get("status", "UNKNOWN")],
            "ticket_line_ref": ref
        })
    
    # 2. Ops Run Latest
    ops_data = read_json_file(SOURCES["ops_run_latest"])
    if ops_data:
        ref = "reports/ops/scheduler/latest/ops_run_latest.json"
        if ref not in seen_refs:
            seen_refs.add(ref)
            items.append({
                "evidence_id": generate_evidence_id(ref),
                "created_at": ops_data.get("asof") or asof,
                "title": f"Ops Run: {ops_data.get('overall_status', 'N/A')}",
                "kind": "OPS_RUN",
                "severity": determine_severity("OPS_RUN", ops_data),
                "ref": ref,
                "tags": [ops_data.get("overall_status", "UNKNOWN")]
            })
    
    # 3. Send Latest
    send_data = read_json_file(SOURCES["send_latest"])
    if send_data:
        ref = "reports/ops/push/send/send_latest.json"
        if ref not in seen_refs:
            seen_refs.add(ref)
            items.append({
                "evidence_id": generate_evidence_id(ref),
                "created_at": send_data.get("asof") or asof,
                "title": f"Push Send: {send_data.get('result', 'N/A')}",
                "kind": "PUSH_SEND",
                "severity": determine_severity("PUSH_SEND", send_data),
                "ref": ref,
                "tags": []
            })
    
    # 4. Postmortem Latest
    postmortem_data = read_json_file(SOURCES["postmortem_latest"])
    if postmortem_data:
        ref = "reports/ops/push/postmortem/postmortem_latest.json"
        if ref not in seen_refs:
            seen_refs.add(ref)
            items.append({
                "evidence_id": generate_evidence_id(ref),
                "created_at": postmortem_data.get("asof") or asof,
                "title": f"Postmortem: {postmortem_data.get('overall_safety_status', 'N/A')}",
                "kind": "PUSH_POSTMORTEM",
                "severity": determine_severity("PUSH_POSTMORTEM", postmortem_data),
                "ref": ref,
                "tags": []
            })
    
    # 5. Self Test Latest
    self_test_data = read_json_file(SOURCES["self_test_latest"])
    if self_test_data:
        ref = "reports/ops/secrets/self_test_latest.json"
        if ref not in seen_refs:
            seen_refs.add(ref)
            items.append({
                "evidence_id": generate_evidence_id(ref),
                "created_at": self_test_data.get("asof") or asof,
                "title": f"Secrets Self-Test: {self_test_data.get('result', 'N/A')}",
                "kind": "SECRETS_SELF_TEST",
                "severity": determine_severity("SECRETS_SELF_TEST", self_test_data),
                "ref": ref,
                "tags": []
            })
    
    # 6. Recon Summary
    recon_data = read_json_file(SOURCES["recon_summary"])
    if recon_data:
        ref = "reports/phase_c/latest/recon_summary.json"
        if ref not in seen_refs:
            seen_refs.add(ref)
            items.append({
                "evidence_id": generate_evidence_id(ref),
                "created_at": recon_data.get("asof") or asof,
                "title": "Phase C Recon Summary",
                "kind": "PHASE_C_LATEST",
                "severity": "INFO",
                "ref": ref,
                "tags": []
            })
    
    # Sort by created_at desc
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    return {
        "schema": "EVIDENCE_INDEX_V1",
        "asof": asof,
        "row_count": len(items),
        "rows": items
    }


def save_evidence_index(index: Dict[str, Any]) -> Dict[str, Any]:
    """Save index using atomic write"""
    # Ensure directories exist
    EVIDENCE_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Atomic write to latest
    tmp_path = EVIDENCE_INDEX_LATEST.with_suffix('.json.tmp')
    tmp_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding='utf-8')
    os.replace(str(tmp_path), str(EVIDENCE_INDEX_LATEST))
    
    # Save snapshot
    now = datetime.now()
    snapshot_name = f"evidence_index_{now.strftime('%Y%m%d_%H%M%S')}.json"
    snapshot_path = EVIDENCE_SNAPSHOTS_DIR / snapshot_name
    snapshot_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding='utf-8')
    
    return {
        "result": "OK",
        "generated": True,
        "row_count": index["row_count"],
        "latest_path": str(EVIDENCE_INDEX_LATEST.relative_to(BASE_DIR)),
        "snapshot_path": str(snapshot_path.relative_to(BASE_DIR))
    }


def regenerate_index() -> Dict[str, Any]:
    """Main entry point for regenerating the index"""
    index = generate_evidence_index()
    return save_evidence_index(index)


if __name__ == "__main__":
    result = regenerate_index()
    print(json.dumps(result, indent=2))
