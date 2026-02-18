# DECISIONS (Append-only)

- **D-20260218-01**: UI-First Operations Active. (근거: P146 Master Plan)
- **D-20260218-02**: Operator API replaces Dashboard API. `Draft` object introduced for preview. (근거: P146.8)
- **D-20260218-03**: LIVE Submit token source is **EXPORT_CONFIRM_TOKEN** only. Prep token is informational. (근거: Security Audit)
- **D-20260218-04**: OCI Backend must run via **Systemd**. Manual `uvicorn` forbidden due to port conflicts. (근거: P146 Stability)
- **D-20260218-05**: Sync Protocol Split: SSOT(Push), Status(Pull), Artifact(On-Demand). (근거: Network Efficiency)
- **D-20260218-06**: Plan ID Validation: Ticket must match Export `plan_id`. (근거: Integrity)
