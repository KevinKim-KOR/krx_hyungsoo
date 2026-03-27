"""Ops Summary 경로 상수 및 설정."""

import os
from datetime import timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Input paths
OPS_RUN_LATEST = BASE_DIR / "reports" / "ops" / "daily" / "snapshots"
HEALTH_LATEST = (
    BASE_DIR / "reports" / "ops" / "evidence" / "health" / "health_latest.json"
)
EVIDENCE_INDEX_LATEST = (
    BASE_DIR / "reports" / "ops" / "evidence" / "index" / "evidence_index_latest.json"
)
SEND_LATEST = BASE_DIR / "reports" / "ops" / "push" / "send" / "send_latest.json"
OUTBOX_LATEST = BASE_DIR / "reports" / "ops" / "push" / "outbox" / "outbox_latest.json"
EMERGENCY_STOP_FILE = BASE_DIR / "state" / "emergency_stop.json"
GATE_FILE = BASE_DIR / "state" / "execution_gate.json"
SENDER_ENABLE_FILE = BASE_DIR / "state" / "real_sender_enable.json"
TICKET_REQUESTS = BASE_DIR / "state" / "tickets" / "ticket_requests.jsonl"
TICKET_RESULTS = BASE_DIR / "state" / "tickets" / "ticket_results.jsonl"
STRATEGY_BUNDLE_LATEST = (
    BASE_DIR / "state" / "strategy_bundle" / "latest" / "strategy_bundle_latest.json"
)
RECO_LATEST = BASE_DIR / "reports" / "live" / "reco" / "latest" / "reco_latest.json"
CYCLE_LATEST = (
    BASE_DIR / "reports" / "live" / "cycle" / "latest" / "live_cycle_latest.json"
)
PORTFOLIO_LATEST = BASE_DIR / "state" / "portfolio" / "latest" / "portfolio_latest.json"
ORDER_PLAN_LATEST = (
    BASE_DIR / "reports" / "live" / "order_plan" / "latest" / "order_plan_latest.json"
)
CONTRACT5_LATEST = (
    BASE_DIR / "reports" / "ops" / "contract5" / "latest" / "ai_report_latest.json"
)

# Output paths
SUMMARY_DIR = BASE_DIR / "reports" / "ops" / "summary"
SUMMARY_LATEST = SUMMARY_DIR / "latest" / "ops_summary_latest.json"
SUMMARY_SNAPSHOTS_DIR = SUMMARY_DIR / "snapshots"

# Risk Window Configuration (D-P.52)
OPS_RISK_WINDOW_DAYS = int(os.environ.get("OPS_RISK_WINDOW_DAYS", "3"))
OPS_RISK_MAX_EVENTS = int(os.environ.get("OPS_RISK_MAX_EVENTS", "200"))
TICKET_FAIL_EXCLUDE_PREFIXES = os.environ.get(
    "OPS_TICKET_FAIL_EXCLUDE_PREFIXES", "AUTO_CLEANUP_,MANUAL_CLEANUP,REAPER_"
).split(",")

# Risk Configuration (D-P.59)
PORTFOLIO_STALE_DAYS = int(os.environ.get("PORTFOLIO_STALE_DAYS", "7"))

# Forbidden prefixes to strip
FORBIDDEN_PREFIXES = ["json:", "file://", "file:", "http://", "https://"]

# Risk Severity Map (P106)
SEVERITY_MAP = {"CRITICAL": 0, "BLOCKED": 0, "WARN": 1, "INFO": 2, "OK": 3}

RISK_CODE_MAP = {
    "EMERGENCY_STOP": "CRITICAL",
    "EVIDENCE_HEALTH_FAIL": "CRITICAL",
    "PORTFOLIO_INCONSISTENT": "CRITICAL",
    "EVIDENCE_HEALTH_WARN": "WARN",
    "TICKETS_FAILED": "WARN",
    "NO_PORTFOLIO": "WARN",
    "PORTFOLIO_STALE_WARN": "WARN",
    "ORDER_PLAN_NO_RECO": "WARN",
    "ORDER_PLAN_BLOCKED": "WARN",
    "CONTRACT5_REPORT_BLOCKED": "WARN",
    "CONTRACT5_REPORT_EMPTY": "INFO",
    "NO_BUNDLE": "WARN",
    "BUNDLE_STALE_WARN": "WARN",
    "NO_RECO_YET": "WARN",
    "RECO_EMPTY": "WARN",
    "STALE_BUNDLE_BLOCKS_RECO": "WARN",
}
