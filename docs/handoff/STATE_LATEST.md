# KRX Alertor Modular — STATE_LATEST (Handoff)

> **Status**: UI-First Operations Active (P146+)
> **Architecture**: PC (Control Plane) ↔ OCI (Execution Plane)
> **Primary Runbook**: [runbook_ui_daily_ops_v1.md](../../docs/runbooks/runbook_ui_daily_ops_v1.md)

---

## 1. 현재 운영 3요소 (The 3 Elements)

이 3가지 요소가 매일 아침 순환해야 시스템이 정상 작동합니다.

| 순서 | Action | 주체 | 방향 | 설명 |
|:---:|---|---|:---:|---|
| **1** | **PUSH** (Settings) | PC | PC → OCI | `Universe`, `Strategy Params` 등 **설정값(Config)**을 OCI로 전송하여 동기화합니다. |
| **2** | **Auto Ops** (Run) | PC | Trigger | PC에서 OCI에게 **"매매 사이클 실행"** 명령을 내립니다. (OCI가 스스로 리포트 생성) |
| **3** | **PULL** (Sync) | PC | OCI → PC | OCI의 **실행 결과(Summary/Stage)**와 메타데이터를 PC로 가져와 화면을 갱신합니다. |

---

## 2. 토큰의 진실 (Token Source of Truth)

UI에 표시되는 힌트는 단순 참고용이며, **서버가 인정하는 유일한 진실**은 아래와 같습니다.

#### `EXPORT_CONFIRM_TOKEN`
- **정의**: `reports/live/order_plan_export/latest/order_plan_export_latest.json` 파일 내의 `confirm_token` 필드.
- **용도**: 
    - **Ticket 생성**: 최종 매매 티켓을 생성할 때 이 토큰이 일치해야 합니다.
    - **Draft 제출**: Operator Dashboard에서 Draft를 제출할 때 검증되는 값입니다.
- **생성 시점**: Auto Ops 실행 시 (Execution Prep 단계) 생성됩니다.
- **주의**: 이 토큰이 없거나 불일치하면 **Ticket 생성이 차단(Block)**됩니다.

---

## 3. Plan ID 검증 규칙 (Blocking Logic)

`plan_id`는 전체 매매 파이프라인의 무결성을 보장하는 핵심 키입니다.

| 아티팩트 | 역할 | 차단 여부 (Blocking) | 설명 |
|---|---|---|---|
| **Order Plan** | 원본 계획 | - | 모든 ID의 근원 (Source). |
| **Export** | 검증용 사본 | **CRITICAL** | `Ticket.plan_id`와 다르면 **즉시 차단**. (매매 의도 변조 방지) |
| **Prep** | 사전 점검 | Warning | `Prep.plan_id` 불일치는 경고 로그를 남기지만, 진행을 막지는 않습니다. |

---

## 4. UI 기준 1회전 절차 (Quick Reference)

자세한 내용은 [runbook_ui_daily_ops_v1.md](../../docs/runbooks/runbook_ui_daily_ops_v1.md)를 참조하십시오.

1.  **PC Cockpit**: `settings` 탭에서 파라미터 확인 후 **PUSH**.
2.  **PC Cockpit**: `ops` 탭에서 **Run Auto Ops Cycle** 클릭 (OCI 실행).
3.  **PC Cockpit**: 1~5분 대기 후 **PULL** 클릭. (상태 `NO_ACTION` / `GENERATED` 확인)
4.  **OCI Dashboard** (필요시): `http://<OCI_IP>:8000/operator` 접속 → **Security Token** 확인.
5.  **PC Cockpit**: (매매 발생 시) Ticket 생성 및 최종 승인.

---

## 5. 아키텍처 원칙 (Principles)
- **Air Gap Control**: PC는 OCI의 실행 결과를 "당겨올(Pull)" 뿐, OCI가 PC로 데이터를 밀어넣지 못합니다.
- **Fail-Closed**: 토큰, Plan ID, 파일 경로 중 하나라도 어긋나면 시스템은 **"멈춤(Block)"**을 선택합니다.
- **Systemd Only**: OCI 백엔드는 오직 `systemd`로만 관리합니다. (수동 실행 절대 금지)
