# KRX Alertor Modular — STATE_LATEST (Handoff)

> **Meta-SSoT**: [MASTER_PLAN_STATUS.md](MASTER_PLAN_STATUS.md) (Architecture/Drift Definition)
> **Protocol**: [COLLAB_PROTOCOL.md](COLLAB_PROTOCOL.md) (User-Agent Rules)

---

## 0) 오늘 결론 (2026-02-17)
- ✅ **현재 운영 상태**: [OK] (P146.9 Sync Deadlock Fixed)
- 🧩 **핵심 변경**:
    - **Sync Architecture**: `sync.py` now writes files directly to avoid Proxy Loopback Deadlock.
    - **Connectivity**: `connect_oci.bat` added for SSH Tunnel Automation.
    - **UI**: Cockpit(Streamlit) is the Primary Control Plane.

---

## 1) 정본(SSoT) 선언 및 우선순위
문서 충돌 시 아래 순서대로 정본을 판정합니다.
1. **`docs/ops/active_surface.json`**: 운영에서 “존재하는 것(화이트리스트)”의 최상위 기준.
2. **`docs/contracts/*` (Status=LOCKED/ACTIVE)**: 스키마/정책의 법전.
3. **`docs/handoff/MASTER_PLAN_STATUS.md` & `STATE_LATEST.md`**: 최신 운영 흐름 및 드리프트 선언.
4. **그 외 (`README.md`, 오래된 runbook 등)**: 단순 참고용. 충돌 시 폐기 또는 “드리프트”로 간주.

---

## 2) 충돌 표 (Drift Table)
| 영역 | 충돌(문서 간 불일치) | 정본 판정 |
|---|---|---|
| **PC↔OCI 동기화** | Runbook은 Git Push 중심 vs Code는 **API PULL/PUSH** 중심 | **API Sync (`contract_sync_v1.md`)** |
| **UI 정체성** | README(React) vs Master Plan(Streamlit) | **Streamlit Cockpit** (`pc_cockpit/cockpit.py`) |
| **브랜치** | `v1.0-golden` vs `archive-rebuild` vs `main` | **`main` (Active)** / `archive-rebuild` (Policy) |
| **Daily Ops** | `deploy/run_daily_ops.sh` vs `deploy/oci/daily_ops.sh` | **`deploy/oci/daily_ops.sh`** (`active_surface.json` 등재) |
| **AI 리포트** | `/api/report/ai` vs `reports/ops/contract5/latest` | **Contract5 (File-based JSON)** |
| **스크립트** | `start.bat` 미등재 vs `start_proxy.bat` 등재 | **`active_surface` 등재 우선**. (`start.bat`는 편의용) |

---

## 3) End-to-End 1장 체크리스트
이 4개 블록이 끊기지 않고 연결되어야 “운영 가능”합니다.

### A. Governance / SSoT
- [ ] `active_surface.json`에 없는 파일/API는 호출하지 않는다.
- [ ] `docs/contracts`에 없는 데이터 포맷은 생성하지 않는다.

### B. Safety Rails (Fail-Closed)
- [ ] 애매하면 실행/외부발송이 자동으로 막히는가?
- [ ] 토큰이 없거나 틀리면 API는 거부(401/403)하는가? (현재 MVP는 Warning)

### C. Ops Cycle (OCI)
- [ ] 09:05 KST Cron -> `deploy/oci/daily_ops.sh` 실행 확인.
- [ ] 결과물: `reports/ops/summary/ops_summary_latest.json` 생성 확인.

### D. Operator Control Plane (PC)
- [ ] **PULL**: Cockpit에서 OCI 상태를 PC로 가져오기 (Timeout 120s).
- [ ] **Review**: UI에서 Risk 및 Order Plan 확인.
- [ ] **PUSH**: 수정된 Portfolio/Settings를 OCI로 전송 (Token: `test` or `OPS_TOKEN`).
- [ ] **Submit**: 최종 Ticket 생성 및 실행 요청.

---

## 4) 토큰 2종 매핑 (Token Mapping)
| 용도 | 관련 Contract | 설명 |
|---|---|---|
| **SYNC PUSH Token** | `contract_sync_v1.md` | SSOT(Portfolio/Settings) 동기화 시 사용. (현재 `test` 등 임의값 허용) |
| **EXPORT Confirm Token** | `contract_dashboard_api_v1.md` | Order Plan Export / Execution Ticket 생성을 위한 최종 승인 토큰. (`execution_prep`의 `confirm_token`과 일치해야 함) |

---

## 5) 주요 이슈 및 해결 (Log)
- **2026-02-17 (P146.9)**:
    - **Symptom**: `PULL` Timeout (30s) / `PUSH` Timeout.
    - **Root Cause**: `sync.py` called `requests` to `localhost` (Self-call Deadlock).
    - **Fix**: Refactored to use Direct File I/O.
    - **Verify**: `curl` or Cockpit Button works within 2s.

---

## 6) 다음 단계 (Next Steps)
- **P147 (Stability)**: `stop.bat` reliability, Tunnel auto-reconnect.
- **P148 (Governance)**: UI-based Parameter Audit.
