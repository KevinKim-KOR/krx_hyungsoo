# Contract: SSOT Synchronization V1

**Version**: 1.0
**Date**: 2026-02-17
**Status**: ACTIVE

---

## 1. 개요

PC(Local)와 OCI(Remote) 간의 SSOT(Single Source of Truth) 동기화를 위한 API 및 프로세스 정의.
P146.9에서 **Resilience** 강화를 위해 Timeout 설정 기능이 추가되었습니다.

---

## 2. API Endpoints

### 2.1 Pull from OCI
- **Method**: `POST /api/sync/pull`
- **Description**: OCI의 `SSOT Snapshot`을 가져와 로컬 상태를 덮어씁니다.
- **Parameters**:
  - `timeout_seconds` (Query, int, default=120): OCI 응답 대기 시간 (초). 네트워크 지연 시 증가 사용.

### 2.2 Push to OCI
- **Method**: `POST /api/sync/push`
- **Description**: 로컬 `SSOT Snapshot`을 OCI로 전송하여 강제로 덮어씁니다.
- **Payload**:
  ```json
  {
      "token": "secret_ops_token"
  }
  ```
- **Parameters**:
  - `timeout_seconds` (Query, int, default=120): OCI 응답 대기 시간.

---

## 3. Timeout Policy (P146.9)

- **Default**: 120초 (Backend Proxy)
- **Configurable**: Cockpit UI에서 사용자가 입력 가능.
- **Rationale**: OCI는 Free Tier 특성상 I/O나 네트워크가 느릴 수 있으므로, 기본 5초 타임아웃은 부적절함.

---

## 4. Health Check

- **Local**: `GET /api/ssot/snapshot` (Latency 측정용)
- **Remote**: Proxy를 통해 OCI 연결 상태 간접 확인.
