# -*- coding: utf-8 -*-
"""
tools/generate_push_messages.py
Push Message Generator (Phase C-P.1)

규칙:
- No Execution: subprocess, reconcile 등 실행 금지
- Active Surface: 정의된 경로 외 파일 생성 금지
- Strict SoT: Allowlist 파일만 읽기 가능
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

BASE_DIR = Path(__file__).parent.parent
REPORTS_DIR = BASE_DIR / "reports"
LATEST_DIR = REPORTS_DIR / "phase_c" / "latest"
PUSH_DIR = REPORTS_DIR / "push" / "latest"
TUNING_DIR = REPORTS_DIR / "tuning"

# Input Allowlist (Strict SoT)
ALLOWLIST = [
    LATEST_DIR / "recon_summary.json",
    LATEST_DIR / "recon_daily.jsonl",
    LATEST_DIR / "report_human.json",
    LATEST_DIR / "report_ai.json",
    TUNING_DIR / "gatekeeper_decision_latest.json",
]

# Output
OUTPUT_PATH = PUSH_DIR / "push_messages.json"


def safe_read_json(path: Path) -> Optional[Dict]:
    """안전한 JSON 읽기"""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return None


def generate_message_id() -> str:
    """Push Message ID 생성"""
    now = datetime.now()
    return f"push_{now.strftime('%Y%m%d_%H%M%S')}_{now.microsecond // 1000:03d}"


def create_push_message(
    push_type: str,
    severity: str,
    title_ko: str,
    body_ko: str,
    sources: List[Dict],
    actions: List[Dict],
    info_note: Optional[str] = None
) -> Dict:
    """Push Message 생성"""
    msg = {
        "schema": "PUSH_MESSAGE_V1",
        "message_id": generate_message_id(),
        "type": push_type,
        "severity": severity,
        "title_ko": title_ko,
        "body_ko": body_ko,
        "asof": datetime.now().isoformat(),
        "sources": sources,
        "actions": actions
    }
    if info_note:
        msg["info_note"] = info_note
    return msg


def generate_market_brief(report_human: Optional[Dict], gatekeeper: Optional[Dict]) -> Dict:
    """PUSH_MARKET_STATE_BRIEF 생성 (항상 생성)"""
    sources = []
    if report_human:
        sources.append({"file": str(LATEST_DIR / "report_human.json")})
    
    # KPI 요약 추출
    kpis = report_human.get("kpis", {}) if report_human else {}
    kpi_summary = []
    for key in ["gate_open_days", "executed_days", "chop_blocked_days", "bear_blocked_days", "no_data_days"]:
        if key in kpis:
            kpi_summary.append(f"{key}: {kpis[key]}")
    
    body = "오늘의 시장 상태 요약입니다.\n" + "\n".join(kpi_summary[:5])
    
    info_note = None
    if gatekeeper is None:
        info_note = "Gatekeeper 결정 파일이 없습니다. (정상 운영 가능)"
    
    return create_push_message(
        push_type="PUSH_MARKET_STATE_BRIEF",
        severity="INFO",
        title_ko="오늘의 시장 브리핑",
        body_ko=body[:500],
        sources=sources,
        actions=[{"id": "OPEN_DASHBOARD", "label_ko": "대시보드 열기", "target": "/"}],
        info_note=info_note
    )


def generate_diagnosis_alert(recon_summary: Dict) -> Optional[Dict]:
    """PUSH_DIAGNOSIS_ALERT 생성 (critical > 0 일 때)"""
    integrity = recon_summary.get("integrity", {})
    critical_total = integrity.get("critical_total", 0)
    
    if critical_total <= 0:
        return None
    
    issues = integrity.get("issues", [])[:5]
    issue_text = "\n".join([f"- {i.get('code', 'UNKNOWN')}: {i.get('message', '')}" for i in issues])
    
    return create_push_message(
        push_type="PUSH_DIAGNOSIS_ALERT",
        severity="CRITICAL",
        title_ko=f"시스템 무결성 경고 ({critical_total}건)",
        body_ko=f"Critical 이슈가 감지되었습니다.\n{issue_text}"[:500],
        sources=[{"file": str(LATEST_DIR / "recon_summary.json")}],
        actions=[
            {"id": "OPEN_DASHBOARD", "label_ko": "대시보드 열기", "target": "/diagnosis"},
            {
                "id": "REQUEST_RECONCILE",
                "label_ko": "재조정 요청",
                "ticket_payload": {
                    "request_type": "REQUEST_RECONCILE",
                    "payload": {"mode": "FULL", "reason": f"Integrity CRITICAL {critical_total}건 감지"}
                }
            }
        ]
    )


def generate_action_request(gatekeeper: Dict) -> Optional[Dict]:
    """PUSH_ACTION_REQUEST 생성 (HOLD/REJECT 일 때)"""
    decision = gatekeeper.get("decision", "")
    
    if decision not in ["HOLD", "REJECT"]:
        return None
    
    reason = gatekeeper.get("reason", "결정 사유 없음")
    
    return create_push_message(
        push_type="PUSH_ACTION_REQUEST",
        severity="WARNING",
        title_ko=f"Gatekeeper 결정: {decision}",
        body_ko=f"Gatekeeper가 {decision} 결정을 내렸습니다.\n사유: {reason}"[:500],
        sources=[{"file": str(TUNING_DIR / "gatekeeper_decision_latest.json")}],
        actions=[
            {"id": "OPEN_DASHBOARD", "label_ko": "대시보드 열기", "target": "/gatekeeper"},
            {
                "id": "REQUEST_REPORTS",
                "label_ko": "리포트 재생성 요청",
                "ticket_payload": {
                    "request_type": "REQUEST_REPORTS",
                    "payload": {"mode": "RE-EVALUATE", "scope": "PHASE_C_LATEST", "reason": f"Gatekeeper {decision}"}
                }
            }
        ]
    )


def run_generator():
    """메인 생성 로직"""
    print("[Generator] 시작...")
    
    # 입력 파일 읽기 (Allowlist만)
    recon_summary = safe_read_json(LATEST_DIR / "recon_summary.json")
    report_human = safe_read_json(LATEST_DIR / "report_human.json")
    gatekeeper = safe_read_json(TUNING_DIR / "gatekeeper_decision_latest.json")
    
    messages = []
    
    # 1. Market Brief (항상 생성)
    brief = generate_market_brief(report_human, gatekeeper)
    messages.append(brief)
    print(f"[Generator] MARKET_BRIEF 생성됨")
    
    # 2. Diagnosis Alert (critical > 0)
    if recon_summary:
        alert = generate_diagnosis_alert(recon_summary)
        if alert:
            messages.append(alert)
            print(f"[Generator] DIAGNOSIS_ALERT 생성됨 (CRITICAL)")
    
    # 3. Action Request (HOLD/REJECT)
    if gatekeeper:
        action = generate_action_request(gatekeeper)
        if action:
            messages.append(action)
            print(f"[Generator] ACTION_REQUEST 생성됨")
    else:
        print(f"[Generator] Gatekeeper 파일 없음 - ACTION_REQUEST SKIP")
    
    # 출력 저장
    PUSH_DIR.mkdir(parents=True, exist_ok=True)
    output = {
        "schema": "PUSH_MESSAGE_V1",
        "status": "ready",
        "asof": datetime.now().isoformat(),
        "row_count": len(messages),
        "rows": messages,
        "error": None
    }
    
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"[Generator] 저장 완료: {OUTPUT_PATH}")
    print(f"[Generator] 총 {len(messages)}개 메시지 생성")
    
    return output


if __name__ == "__main__":
    run_generator()
