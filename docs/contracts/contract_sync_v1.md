# Contract: Sync Protocol V1

**Version**: 1.1 (Refined Types)
**Date**: 2026-02-18
**Status**: ACTIVE

---

## 1. 개요

PC(Control)와 OCI(Execution) 간의 데이터 동기화 프로토콜을 정의합니다.
동기화는 목적에 따라 3가지 유형으로 엄격히 분리됩니다.

| 유형 | 방향 | 내용 | Trigger |
|---|---|---|---|
| **SSOT Sync** | PC → OCI | 설정 및 계획 (Config/Portfolio) | **PUSH** Button |
| **Status Sync** | OCI → PC | 운영 상태 및 요약 (Summary/Stage) | **PULL** Button |
| **Artifact Delivery** | OCI → PC | 개별 리포트 파일 (Report/Ticket) | **View** Action |

---

## 2. Type 1: SSOT Sync (PUSH)

PC의 설정을 OCI로 전송하여 실행 환경을 구성합니다.

- **Endpoint**: `POST /api/sync/push`
- **Payload**:
  - `strategy_params`: 전략 파라미터 전체
  - `universe`: 투자 유니버스
  - `portfolio` (Optional): 수동 포트폴리오 조정 시
- **Behavior**: OCI의 `state/` 디렉토리에 **Atomic Overwrite** 합니다.

---

## 3. Type 2: Status Sync (PULL)

OCI의 현재 운영 상태를 PC 대시보드에 반영합니다.

- **Endpoint**: `POST /api/sync/pull`
- **Scope**:
  - `ops_summary_latest.json`: 전체 진행 단계(Stage) 및 요약
  - `manifest.json`: 최신 아티팩트 목록 (버전 확인용)
- **Anti-Pattern**:
  - ❌ **Full Mirroring**: `reports/` 폴더 전체를 긁어오지 않습니다. (느림/비효율)

---

## 4. Type 3: Artifact Delivery (On-Demand)

사용자가 상세 내용을 확인하려 할 때만 개별 파일을 전송합니다.

- **Endpoint**: `GET /api/artifact/read?path=...`
- **Content**:
  - `ticket_{date}.md`: 매매 티켓 상세
  - `report_{id}.html`: 전략 리포트 시각화
- **Cache**: PC는 `cache/` 디렉토리에 이를 임시 저장할 수 있습니다.

---

## 5. Timeout Policy

네트워크 지연(OCI Free Tier)을 고려하여 타임아웃을 이원화합니다.

| Layer | Timeout | 설명 |
|---|---|---|
| **Client (UI)** | **5s** (Connect) | 서버 연결 자체의 타임아웃. 즉각적인 피드백. |
| **Server (Proxy)** | **120s** (Read) | OCI 내부 처리 및 SSH 터널링 대기 시간. (`timeout_seconds` 파라미터로 제어) |

> ⚠️ **Note**: PULL 작업이 120초를 초과하면 PC는 "Unknown/Timeout" 상태를 표시하지만, OCI 작업은 계속 진행될 수 있습니다.
