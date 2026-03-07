# UI Tabs & Modules Audit (Cockpit)

As of P174-Final, the UI is grouped into three top-level tabs. The advanced panel holds legacy or unverified tools.
UI adjustments are frozen unless critical bugs occur.

## Top-Level Routing
- **🚀 데일리 운영 (P144)**: `[사용됨]` (Daily execution, OCI Sync)
- **🧭 워크플로우 (P170)**: `[사용됨]` (Unified Parameters, Backtest, Tuning, Ops Sync)
- **🛠️ 정비창 (Advanced)**: `[사용됨]` (Container for legacy/unused modules)

## Modules inside Advanced Panel (`render_advanced_panel`)
- **Current Parameters**: `[대체됨(P170)]` (Fully migrated to P170)
- **Recommendations (P135)**: `[미사용/미검증]` (Maintained for reference only)
- **Holdings Timing (P136)**: `[미사용/미검증]` (Maintained for reference only)
- **Portfolio Editor (P136.5)**: `[미사용/미검증]` (Maintained for reference only)
- **Param Review (P138)**: `[미사용/미검증]` (Maintained for reference only)
- **Guardrails (P160)**: `[미사용/미검증]` (Maintained for reference only)
- **백테스트 (P165)**: `[대체됨(P170)]` (Migrated to P170 workflow)
- **튜닝 (P167)**: `[대체됨(P170)]` (Migrated to P170 workflow)

*Note: None of the [미사용/미검증] components have been deleted to comply with the "Keep in Advanced" rule.*
