# 개발자 최종 지시문
## POC3-REF-02 Source Fact Verification

> 출처: 설계자 최종 지시문 (레드팀 PASS). 사용자가 채팅으로 개발자에게 전달(2026-08-01). 본 파일은 검증자 대조용 원본 지시문 보존본 — 개발자가 임의 편집하지 않는다.

### 1. 역할

당신은 개발자다.

이번 작업은 기능 개발이나 canonical 문서 반영이 아니다.
레드팀을 통과한 통합지도와 갱신안이 실제 저장소·소스와 일치하는지 확인하고 사실만 보고한다.

귀속·5분류·진행 순서는 변경하지 않는다.
설계 전제와 실제 소스가 충돌하면 임의로 고치지 말고 중단한다.

---

### 2. 현재 상태

- 현재 Step: `POC3-REF-02`
- 현재 상태: `REDTEAM_PASS / SOURCE_VERIFICATION_PENDING`
- canonical 반영: 아직 수행하지 않음
- 다음 Step 후보: `POC3-03 Navigation Information Architecture v1`
- `POC3-03` 개발 진입: 금지
- 별도로 생성됐던 `STATE_LATEST.md`, `BACKLOG.md`,
  `investment_model_v2_docs_canonical_20260731.zip`: 사용 금지

---

### 3. 입력 문서

레드팀 PASS를 받은 아래 세 파일을 기준으로 확인한다.

1. `POC3-00_PC_JUDGMENT_UI_INTEGRATED_IMPLEMENTATION_MAP_V2.md`
2. `STATE_LATEST_UPDATE_PROPOSAL_20260731.md`
3. `BACKLOG_UPDATE_PROPOSAL_20260731.md`

비교 대상:

- 실제 저장소의 `docs/STATE_LATEST.md`
- 실제 저장소의 `docs/backlog/BACKLOG.md`
- 실제 저장소의 `docs/handoff/STATE_LATEST.md`
- 기존 POC3-00 V1 또는 POC3 마스터 문서
- 현재 Git revision과 실제 소스·테스트·운영 근거

반드시 레드팀에 전달된 정확한 세 파일을 사용한다.
설계자가 이전에 직접 만든 교체본이나 ZIP을 입력으로 사용하지 않는다.

---

### 4. 단일 목표

통합지도에 기록된 완료·미구현·후속 개발 판정과 canonical 갱신 전제가 현재 실제 소스에 부합하는지 확인한다.

이번 작업의 결과는 다음 둘 중 하나다.

1. `VERIFIED_MATCH`
   - 설계 전제와 실제 저장소가 일치
   - 다음 게이트는 설계자의 canonical 반영 지시문 작성

2. `SOURCE_CONFLICT`
   - 하나 이상의 설계 전제가 실제 소스와 충돌
   - 파일을 수정하지 않고 설계자에게 반환

---

### 5. 우선 확인 경로

전체 저장소를 처음부터 무차별 조사하지 않는다.

다음 파일과 직접 호출 관계부터 확인한다.

#### POC3 화면·route

- `frontend/app/components/LeftSidebar.tsx`
- `frontend/app/components/MainPanel.tsx`
- `frontend/app/components/TodayInvestmentCheckView.tsx`
- `frontend/app/components/JudgmentWorkbenchView.tsx`
- `frontend/app/components/workbench/`
- `frontend/lib/api/queryCache.ts`
- `frontend/lib/api/dashboardKeys.ts`
- `frontend/lib/api/priceSeries.ts`
- `app/api.py`
- `app/api_price_series.py`
- 위 파일의 직접 테스트와 직접 호출자

파일명이 현재 소스와 다르면 동일 책임의 실제 파일을 찾아 경로 차이를 보고한다.

#### 문서

- `docs/STATE_LATEST.md`
- `docs/backlog/BACKLOG.md`
- `docs/handoff/STATE_LATEST.md`
- POC3-01 개발 결과서
- POC3-02 최신 conclusion 또는 handoff
- POC3-REF-01 결과서
- 기존 POC3 통합지도 또는 마스터 V1
- 세 레드팀 PASS 문서가 참조하는 직접 관련 문서

직접 호출 관계나 계약 위치를 찾을 수 없을 때만 해당 지점에 한해 검색 범위를 넓힌다.

---

### 6. 확인 범위

#### 6.1 최신 완료 상태

다음을 실제 소스·route·테스트·Git 이력과 대조한다.

- POC3-01 오늘의 투자 점검
  - 화면 컴포넌트 존재
  - 기본 진입 및 메뉴 route 연결
  - 사용자 실화면 확인 완료 상태를 뒤집는 현재 소스 충돌 유무

- POC3-02 Judgment Workbench
  - 화면·선택 가격 차트·API 연결 존재
  - `c2b7df13` revision 존재 및 관련 변경 포함 여부
  - 현재 route에서 실제 진입 가능한 구조인지

- POC3-REF-01
  - `16d56702` revision 존재 여부
  - 조사 결과 문서의 현재 위치와 상태

사용자의 실화면 PASS 자체를 개발자가 재판정하지 않는다.
현재 소스가 해당 완료 사실과 명백히 충돌하는지만 확인한다.

#### 6.2 BACKLOG의 완료 17개

아래 17개를 모두 확인한다.

- B-013 NAV·괴리율 source 진단
- B-019 refresh 실패 안내·재시도 UX
- B-030 레버리지·인버스·합성 필터
- B-031 Data Status 실제 연결
- B-040 holdings 편집 UX
- B-049 Telegram split 발송
- B-056 역할별 페이지 분리
- B-060 timezone·사람이 읽는 시각
- B-069 OCI handoff artifact 고도화
- B-073 OCI holdings source 부재 해소
- B-075 운영 결과·snapshot·변화 기록
- B-076 비동기 universe refresh
- B-079 ML dataset 저장
- B-091 운영 빈도 문서 정합성
- B-100 spike all-unavailable test fixture
- B-101 PUSH2 금지문구 substring test
- B-102 저빈도 scheduler 운영

각 항목마다 다음을 보고한다.

- 실제 구현 또는 해소 근거
- 파일·함수·route·테스트 또는 운영 근거
- 직접 호출자 존재 여부
- `MATCH / CONFLICT / SOURCE_NOT_APPLICABLE` 판정

소스만으로 확인할 수 없는 OCI ACTIVE 등의 운영 사실은 억지로 PASS나 FAIL 처리하지 않는다.
현재 저장소에 남은 운영 증거의 위치와 추가 실측 필요 여부를 보고한다.

#### 6.3 확정 개발 3개

다음 항목이 이미 완전히 구현된 기능인지 확인한다.

- B-003 위험 evidence 급락·국면 경계 검증
- B-072 전달 결과 대시보드
- B-105 Dashboard 캐시 무효화 실제 컴포넌트 통합 테스트

기반 코드나 일부 구현이 존재하는 것은 충돌이 아니다.
통합지도가 “향후 Step에서 해결할 필요가 있다”고 본 결함이 이미 완전히 닫혔는지가 판단 기준이다.

#### 6.4 후속 개발 16개

다음 항목에 동일 책임의 완료 구현이 이미 존재하는지 확인한다.

- B-001
- B-004
- B-006
- B-007
- B-037
- B-038
- B-078
- B-082
- B-083
- B-085
- B-086
- B-092
- B-097
- B-098
- B-103
- B-104

완료 구현이 확인되면 해당 파일·호출 경로를 충돌로 보고한다.
구현 여부를 근거 없이 추정하지 않는다.

#### 6.5 항목 수와 문서 적용 안전성

다음을 기계적으로 검산한다.

- 기존 BACKLOG 실제 항목: 105개
- 완료: 17개
- 확정 개발: 3개
- 후속 개발: 16개
- 조건부 보류: 65개
- 제외·폐기: 4개
- 합계: 105개
- B-001~B-105의 중복·누락: 0개
- 조건부 보류 65개가 갱신안에 모두 남아 있는지
- 다른 분류 40개가 BACKLOG 잔존 대상으로 잘못 포함되지 않았는지
- P/F/B 전체 `orphan_count = 0`이 실제 입력 문서 기준으로 성립하는지

또한 다음을 확인한다.

- 실제 저장소의 canonical 문서가 입력 스냅샷 이후 변경됐는지
- 기존 POC3 마스터 V1의 정확한 경로와 참조자
- V1을 V2로 교체할 경우 유실되는 현재 유효 결정이 있는지
- `STATE_LATEST_UPDATE_PROPOSAL`이 기존 history를 훼손하지 않는지
- `BACKLOG_UPDATE_PROPOSAL`이 조건부 보류 65개 외 항목을 잘못 남기거나 삭제하지 않는지
- `docs/handoff/STATE_LATEST.md`를 redirect로 정리할 때 필요한 최신 정보가 유실되지 않는지
- 임시 갱신안 두 파일을 반영 후 제거해도 참조가 깨지지 않는지

---

### 7. 금지사항

이번 작업에서는 다음을 하지 않는다.

- 소스 코드 수정
- 문서 수정·추가·삭제·이동
- canonical 반영
- 통합지도 상태를 `CANONICAL` 또는 `CLOSED`로 변경
- BACKLOG 분류 변경
- POC3 장기 순서 변경
- `POC3-03` 설계 또는 구현
- 신규 API·DB·source·산식·threshold 추가
- commit·push·deploy
- 기존 사용자 변경사항 stage 또는 정리
- 설계 충돌을 개발자 판단으로 해소

확인을 위해 필요한 명령은 읽기 전용으로 수행한다.
전체 회귀·frontend build는 요구하지 않는다.
기존 focused test가 특정 구현 사실 확인에 꼭 필요한 경우에만 실행하고 결과를 보고한다.

---

### 8. 중단 조건

다음 중 하나라도 발견하면 즉시 `SOURCE_CONFLICT`로 중단한다.

1. 완료 항목이 실제 소스에 없고 사용자·운영 결정으로도 해소되지 않음
2. 확정 개발 또는 후속 개발 항목이 이미 완전히 구현·검증됨
3. 실제 BACKLOG 항목 수 또는 5분류 합계가 설계와 다름
4. B-001~B-105에 중복이나 누락이 있음
5. 입력 스냅샷 이후 canonical 문서가 변경돼 갱신안 적용 시 최신 내용을 덮어씀
6. 기존 V1 제거 시 V2에 없는 현재 유효 결정이 유실됨
7. 문서 경로나 참조 구조가 갱신안의 전제와 다름
8. 현재 source route만으로 POC3-03 경계를 유지할 수 없다는 사실이 확인됨

충돌 발견 후 파일을 고쳐 맞추지 않는다.

---

### 9. 완료 기준 AC

- AC-1: 레드팀 PASS 세 파일과 실제 저장소를 대조했다.
- AC-2: POC3-01·02·REF-01의 실제 경로와 Git 근거를 확인했다.
- AC-3: 완료 17개를 전부 개별 확인했다.
- AC-4: 확정 개발 3개의 기존 완료 구현 여부를 확인했다.
- AC-5: 후속 개발 16개의 중복 완료 구현 여부를 확인했다.
- AC-6: 105개 항목과 5분류 합계를 검산했다.
- AC-7: V1 교체, STATE·BACKLOG 갱신, redirect 정리의 적용 안전성을 확인했다.
- AC-8: 소스·문서·Git 파일 변경이 0건이다.
- AC-9: 충돌이 있으면 수정 없이 정확한 근거와 함께 반환했다.
- AC-10: 다음 게이트를 `canonical 반영 지시문 작성` 또는 `설계자 재판정` 중 하나로 명확히 보고했다.

---

### 10. 개발 완료 보고 JSON

아래 형식으로만 최종 보고한다.

```json
{
  "task": "POC3-REF-02_SOURCE_FACT_VERIFICATION",
  "status": "VERIFIED_MATCH | SOURCE_CONFLICT | BLOCKED",
  "current_revision": "",
  "working_tree_before": {
    "clean": false,
    "existing_changes": []
  },
  "files_modified": [],
  "poc3_state_checks": [
    {
      "id": "POC3-01",
      "result": "MATCH | CONFLICT | SOURCE_NOT_APPLICABLE",
      "evidence": []
    },
    {
      "id": "POC3-02",
      "result": "MATCH | CONFLICT",
      "evidence": []
    },
    {
      "id": "POC3-REF-01",
      "result": "MATCH | CONFLICT",
      "evidence": []
    }
  ],
  "completed_backlog_checks": {
    "expected": 17,
    "checked": 0,
    "matched": 0,
    "conflicts": 0,
    "source_not_applicable": 0,
    "items": []
  },
  "confirmed_development_checks": {
    "expected": 3,
    "checked": 0,
    "already_completed": [],
    "items": []
  },
  "followup_development_checks": {
    "expected": 16,
    "checked": 0,
    "already_completed": [],
    "items": []
  },
  "classification_counts": {
    "total": 0,
    "completed": 0,
    "confirmed_development": 0,
    "followup_development": 0,
    "conditional_hold": 0,
    "excluded_or_discarded": 0,
    "duplicate_ids": [],
    "missing_ids": [],
    "orphan_count": 0
  },
  "canonical_application_safety": {
    "state_latest_safe": false,
    "backlog_safe": false,
    "handoff_redirect_safe": false,
    "v1_replacement_safe": false,
    "proposal_cleanup_safe": false,
    "details": []
  },
  "focused_tests_run": [],
  "conflicts": [],
  "stopped_without_changes": true,
  "recommended_next_gate": "DESIGNER_CANONICAL_APPLICATION_INSTRUCTION | DESIGNER_REJUDGMENT"
}
```

개발자가 `VERIFIED_MATCH`를 보고하더라도 아직 `POC3-REF-02 PASS / CLOSED`는 아니다. 그 결과를 설계자가 판정한 뒤 canonical 반영 지시문을 별도로 작성한다.

> 입력 문서 세 파일은 `docs/ref/` 에 있다(사용자 배치).
