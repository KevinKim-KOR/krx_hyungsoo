# Contract 5: Reconciliation Reports (SEALED)

## Overview
This document defines the **Sealed** specification for "Contract 5" Reconciliation Reports.
This schema is **Immutable**. Changes require a V2 specification.
Goal: Ensure strict decoupling between Reconciler (Backend Engine) and User Interface/AI Agents.

## 1. Absolute Constraints
- **C5-A1. Schema Freeze**: `REPORT_HUMAN_V1` and `REPORT_AI_V1` keys/types are fixed.
- **C5-A2. SSOT**: Reports must be generated ONLY from `recon_summary.json` and `recon_daily.jsonl`.
- **C5-A3. Envelope**: All APIs must return an Envelope object (`status`, `schema`, `asof`, `data`).
- **C5-A4. KPI 5**: Human Report KPIs are limited to exactly 5 specific keys.
- **C5-A5. AI Budget**: AI Report `data` size must not exceed **1200 characters**.

## 2. Artifact Definitions

### 2.1 Human Report (`REPORT_HUMAN_V1`)
**Purpose**: UI Rendering (Dashboard Header, KPIs, Top Issues).
**Path**: `reports/phase_c/report_human_v1.json`
**Schema**:
```json
{
  "contract_id": "CONTRACT_5",
  "schema_version": "REPORT_HUMAN_V1",
  "policy_id": "TRADE_COUNT_POLICY_V1",
  "asof": "ISO8601",
  "headline": {
      "period": "YYYY-MM-DD~YYYY-MM-DD",
      "status_badge": "GREEN|AMBER|RED|CRITICAL",
      "trade_count": { "L1_actions": int, "L2_trades": int, "delta": int }
  },
  "integrity_summary": {
      "critical_total": int,
      "warning_total": int,
      "info_total": int,
      "top_codes": [{"code": str, "count": int}]
  },
  "kpis": [
      { "key": "gate_open_days", "label_ko": "시장 개장", "value": int, "unit": "days", "severity": "GREEN" },
      { "key": "executed_days", "label_ko": "체결 발생", "value": int, "unit": "days", "severity": "GREEN" },
      { "key": "chop_blocked_days", "label_ko": "횡보장 방어", "value": int, "unit": "days", "severity": "AMBER" },
      { "key": "bear_blocked_days", "label_ko": "하락장 방어", "value": int, "unit": "days", "severity": "RED" },
      { "key": "no_data_days", "label_ko": "데이터 누락", "value": int, "unit": "days", "severity": "CRITICAL" }
  ],
  "top_issues": [
      { "code": str, "title_ko": str, "count": int, "drilldown": { "filter_keys": [], "filter_values": [] } }
  ],
  "pointers": {
      "recon_summary_path": str,
      "reocn_daily_path": str,
      "provenance_hash8": str
  }
}
```

### 2.2 AI Report (`REPORT_AI_V1`)
**Purpose**: Context for AI Agents (ChatGPT).
**Path**: `reports/phase_c/report_ai_v1.json`
**Budget**: Max 1200 chars.
**Schema**:
```json
{
  "contract_id": "CONTRACT_5",
  "schema_version": "REPORT_AI_V1",
  "asof": "ISO8601",
  "kpi_vector": {
      "gate_open_days": int,
      "executed_days": int,
      "mdd_pct": float(optional),
      "L2_trades": int,
      "no_data_days": int
  },
  "integrity_flags": {
      "critical_total": int,
      "critical_codes": [str]
  },
  "constraints_hint": {
      "policy_id": "TRADE_COUNT_POLICY_V1",
      "gatekeeper_schema": "GATEKEEPER_DECISION_V3",
      "tuning_allowed": false
  }
}
```

## 3. Error Codes (Critical)
- `IC_REPORT_SCHEMA_MISMATCH`: API returns invalid schema.
- `IC_REPORT_NOT_READY`: File missing or generation incomplete.
- `IC_AI_REPORT_BUDGET_EXCEEDED`: AI Report > 1200 chars.
- `IC_RECON_NOT_READY`: Underlying Reconciler data missing.
- `IC_RECON_NON_DETERMINISTIC`: Reconciler output unstable.
- `IC_PROVENANCE_MISSING`: Source file hash/mtime missing.

## 4. UI Rules
- Header/KPIs source: `/api/report/human`
- Daily Table source: `/api/recon/daily`
- **Stop Screen**: Active if `.status != 'ready'` in either endpoint.
- **Legacy Fallback**: If array returned (legacy), show INFO banner but render if possible.
