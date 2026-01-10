"""
Evidence Health Checker (C-P.33)

Validator Single Source: ref 검증은 반드시 ref_validator.py만 사용
No Execution: 검사 + 리포트 생성만 허용
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

BASE_DIR = Path(__file__).parent.parent

# SLO 설정
SLO = {
    "window_days": 7,
    "min_resolvable_rate": 0.98,
    "min_required_refs_per_receipt": 1
}

# 체크 대상 Inputs
TICKET_RECEIPTS_FILE = BASE_DIR / "state" / "tickets" / "ticket_receipts.jsonl"
SEND_LATEST_FILE = BASE_DIR / "reports" / "ops" / "push" / "send" / "send_latest.json"
POSTMORTEM_LATEST_FILE = BASE_DIR / "reports" / "ops" / "push" / "postmortem" / "postmortem_latest.json"
EVIDENCE_INDEX_LATEST_FILE = BASE_DIR / "reports" / "ops" / "evidence" / "index" / "evidence_index_latest.json"

# 결과 저장 경로
HEALTH_DIR = BASE_DIR / "reports" / "ops" / "evidence" / "health"
HEALTH_LATEST_FILE = HEALTH_DIR / "health_latest.json"
HEALTH_SNAPSHOTS_DIR = HEALTH_DIR / "snapshots"

MAX_RECEIPTS_TO_CHECK = 20  # 최근 N개만


def read_jsonl_last_n_lines(path: Path, n: int) -> List[Dict]:
    """JSONL 최근 N줄만 읽기 (enumerate 사용, 전체 로드 금지)"""
    if not path.exists():
        return []
    
    lines = []
    try:
        line_count = 0
        with open(path, 'r', encoding='utf-8') as f:
            for _ in f:
                line_count += 1
        
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


def safe_load_json(path: Path) -> Dict:
    """JSON 파일 안전 로드"""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def validate_refs(refs: List[str]) -> Dict:
    """evidence_refs 검증 (공용 Validator 사용!)"""
    from app.utils.ref_validator import validate_and_resolve_ref
    
    stats = {"total": 0, "ok": 0, "fail": 0, "fail_reasons": []}
    
    for ref in refs:
        stats["total"] += 1
        result = validate_and_resolve_ref(ref)
        
        if result.decision == "OK":
            stats["ok"] += 1
        else:
            stats["fail"] += 1
            stats["fail_reasons"].append({
                "ref": ref,
                "decision": result.decision,
                "reason": result.reason
            })
    
    return stats


def calculate_decision(rate: float) -> str:
    """SLO 기반 결정"""
    if rate >= SLO["min_resolvable_rate"]:
        return "PASS"
    elif rate >= 0.90:
        return "WARN"
    else:
        return "FAIL"


def run_evidence_health_check() -> Dict[str, Any]:
    """Evidence Health Check 실행"""
    now = datetime.now()
    asof = now.isoformat()
    period_from = (now - timedelta(days=SLO["window_days"])).isoformat()
    
    checks = []
    all_fail_reasons = []
    total_pass = 0
    total_warn = 0
    total_fail = 0
    
    # === Check 1: ticket_receipts evidence_refs 존재율 및 resolvable ===
    receipts = read_jsonl_last_n_lines(TICKET_RECEIPTS_FILE, MAX_RECEIPTS_TO_CHECK)
    
    if receipts:
        refs_found = 0
        all_refs = []
        for r in receipts:
            refs = r.get("evidence_refs", [])
            if refs:
                refs_found += 1
                all_refs.extend(refs)
        
        refs_stats = validate_refs(all_refs)
        resolvable_rate = refs_stats["ok"] / refs_stats["total"] if refs_stats["total"] > 0 else 1.0
        decision = calculate_decision(resolvable_rate)
        
        checks.append({
            "name": "ticket_receipts_resolvable",
            "decision": decision,
            "reason": f"{resolvable_rate*100:.1f}% resolvable ({refs_stats['ok']}/{refs_stats['total']})",
            "stats": refs_stats
        })
        
        if decision == "PASS": total_pass += 1
        elif decision == "WARN": total_warn += 1
        else: total_fail += 1
        
        all_fail_reasons.extend(refs_stats["fail_reasons"])
    else:
        checks.append({
            "name": "ticket_receipts_resolvable",
            "decision": "WARN",
            "reason": "No receipts found",
            "stats": {"total": 0, "ok": 0, "fail": 0}
        })
        total_warn += 1
    
    # === Check 2: send_latest evidence_refs ===
    send_data = safe_load_json(SEND_LATEST_FILE)
    if send_data:
        refs = send_data.get("evidence_refs", [])
        if refs:
            refs_stats = validate_refs(refs)
            resolvable_rate = refs_stats["ok"] / refs_stats["total"] if refs_stats["total"] > 0 else 1.0
            decision = calculate_decision(resolvable_rate)
        else:
            refs_stats = {"total": 0, "ok": 0, "fail": 0}
            decision = "WARN"
        
        checks.append({
            "name": "send_latest_resolvable",
            "decision": decision,
            "reason": f"{refs_stats['ok']}/{refs_stats['total']} resolvable" if refs_stats["total"] > 0 else "No evidence_refs",
            "stats": refs_stats
        })
        
        if decision == "PASS": total_pass += 1
        elif decision == "WARN": total_warn += 1
        else: total_fail += 1
        
        all_fail_reasons.extend(refs_stats.get("fail_reasons", []))
    else:
        checks.append({
            "name": "send_latest_resolvable",
            "decision": "WARN",
            "reason": "send_latest.json not found",
            "stats": {"total": 0, "ok": 0, "fail": 0}
        })
        total_warn += 1
    
    # === Check 3: postmortem_latest evidence_refs ===
    postmortem_data = safe_load_json(POSTMORTEM_LATEST_FILE)
    if postmortem_data:
        refs = postmortem_data.get("evidence_refs", [])
        if isinstance(refs, list) and refs:
            refs_stats = validate_refs(refs)
            resolvable_rate = refs_stats["ok"] / refs_stats["total"] if refs_stats["total"] > 0 else 1.0
            decision = calculate_decision(resolvable_rate)
        else:
            refs_stats = {"total": 0, "ok": 0, "fail": 0}
            decision = "WARN"
        
        checks.append({
            "name": "postmortem_latest_resolvable",
            "decision": decision,
            "reason": f"{refs_stats['ok']}/{refs_stats['total']} resolvable" if refs_stats["total"] > 0 else "No evidence_refs (or object format)",
            "stats": refs_stats
        })
        
        if decision == "PASS": total_pass += 1
        elif decision == "WARN": total_warn += 1
        else: total_fail += 1
        
        all_fail_reasons.extend(refs_stats.get("fail_reasons", []))
    else:
        checks.append({
            "name": "postmortem_latest_resolvable",
            "decision": "WARN",
            "reason": "postmortem_latest.json not found",
            "stats": {"total": 0, "ok": 0, "fail": 0}
        })
        total_warn += 1
    
    # === Check 4: evidence_index_latest 존재 ===
    if EVIDENCE_INDEX_LATEST_FILE.exists():
        checks.append({
            "name": "evidence_index_exists",
            "decision": "PASS",
            "reason": "evidence_index_latest.json exists",
            "stats": {}
        })
        total_pass += 1
    else:
        checks.append({
            "name": "evidence_index_exists",
            "decision": "WARN",
            "reason": "evidence_index_latest.json not found",
            "stats": {}
        })
        total_warn += 1
    
    # === Summary ===
    overall_decision = "PASS"
    if total_fail > 0:
        overall_decision = "FAIL"
    elif total_warn > 0:
        overall_decision = "WARN"
    
    # Top fail reasons
    reason_counts = {}
    for fr in all_fail_reasons:
        key = fr["decision"]
        reason_counts[key] = reason_counts.get(key, 0) + 1
    top_fail_reasons = [{"reason": k, "count": v} for k, v in sorted(reason_counts.items(), key=lambda x: -x[1])]
    
    report = {
        "schema": "EVIDENCE_HEALTH_REPORT_V1",
        "asof": asof,
        "period": {
            "from": period_from,
            "to": asof
        },
        "summary": {
            "total": len(checks),
            "pass": total_pass,
            "warn": total_warn,
            "fail": total_fail,
            "decision": overall_decision
        },
        "checks": checks,
        "top_fail_reasons": top_fail_reasons[:5]
    }
    
    return report


def save_health_report(report: Dict) -> Dict:
    """Health Report 저장 (Atomic Write)"""
    HEALTH_DIR.mkdir(parents=True, exist_ok=True)
    HEALTH_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Atomic write latest
    tmp_file = HEALTH_LATEST_FILE.with_suffix('.json.tmp')
    tmp_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    os.replace(str(tmp_file), str(HEALTH_LATEST_FILE))
    
    # Snapshot
    now = datetime.now()
    snapshot_name = f"health_{now.strftime('%Y%m%d_%H%M%S')}.json"
    snapshot_path = HEALTH_SNAPSHOTS_DIR / snapshot_name
    snapshot_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    
    return {
        "result": "OK",
        "decision": report["summary"]["decision"],
        "health_latest_path": str(HEALTH_LATEST_FILE.relative_to(BASE_DIR)),
        "snapshot_path": str(snapshot_path.relative_to(BASE_DIR))
    }


def regenerate_health_report() -> Dict:
    """Health Report 재생성"""
    report = run_evidence_health_check()
    return save_health_report(report)


if __name__ == "__main__":
    result = regenerate_health_report()
    print(json.dumps(result, indent=2))
