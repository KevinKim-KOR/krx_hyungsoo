# Smoke Test 체크리스트 V1.1

**Version**: 1.1 (UI-First)
**Date**: 2026-02-18
**Status**: ACTIVE

---

## 개요
이 테스트는 **PC Cockpit**과 **OCI Operator Dashboard**를 통해 시스템의 E2E 건전성을 확인합니다.
더 이상 CLI나 JSON 파일을 직접 열어보지 않고, **UI 동작**만으로 판단합니다.

---

## 🏗️ Phase 1: Connectivity (연결성)

- [ ] **PC Cockpit 접속**: `http://localhost:8501` 정상 로딩.
- [ ] **System Connectivity**: 메인 화면 하단 "Check Connectivity" 클릭.
    - [ ] `Backend Latency`: 초록색 (OK)
    - [ ] `SSH Tunnel`: 정상 (에러 메시지 없음)
- [ ] **Status Bar**: 상단 Status가 `UNKNOWN`이 아닌 상태 (`NO_ACTION`, `GENERATED` 등).

## 🚀 Phase 2: Configuration Sync (설정 동기화)

- [ ] **Settings 변경**: Cockpit > Settings 탭에서 `Momentum Period`를 임의 값(예: 99)으로 변경.
- [ ] **PUSH 실행**: `📤 PUSH (OCI)` 클릭.
- [ ] **확인**: 
    - [ ] Toast: "Push Success" 확인.
    - [ ] (검증) 페이지 새로고침 후 OCI 값이 유지되는지 확인 (Read-back).

## 🤖 Phase 3: Auto Ops Trigger (실행)

- [ ] **Run Cycle**: Cockpit > Ops 탭 > `▶️ Run Auto Ops Cycle` 클릭.
- [ ] **Toast**: "Auto Ops Triggered on OCI" 확인.
- [ ] **Time check**: 1분 후 `⬇ PULL (OCI)` 클릭.
    - [ ] 상단 **As Of** 시간이 현재 시간으로 갱신되었는지 확인.

## 🛡️ Phase 4: Operator Dashboard (OCI)

- [ ] **접속 Redirect**: 브라우저에서 `http://localhost:8001` (또는 OCI IP:8000) 접속.
    - [ ] `/operator` 경로로 자동 리다이렉트 되는지 확인.
- [ ] **Security Token**: 우측 상단 Security Token 상태 표시 (Lock 아이콘).

## 📝 Phase 5: Draft Logic (승인 로직)

- [ ] **Generate Draft**: (Ticket이 있는 경우) `Draft Manager` > `Generate Draft` 클릭.
    - [ ] Preview JSON이 화면에 표시되는지 확인.
    - [ ] `plan_id`, `action` 필드가 정상적인지 확인.

## 🚦 Phase 6: Mode-Specific UI (토큰)

- [ ] **DRY_RUN 모드**:
    - [ ] Submit 영역에 **Token 입력창이 숨겨져 있는지** 확인. (Auto-Fill)
- [ ] **LIVE 모드**:
    - [ ] Submit 영역에 **Token 입력창이 보이고, 필수 입력**인지 확인.

---

## ✅ Pass Criteria
위 6개 Phase를 모두 통과하면 **배포 성공(Go-Live Ready)**으로 간주합니다.
