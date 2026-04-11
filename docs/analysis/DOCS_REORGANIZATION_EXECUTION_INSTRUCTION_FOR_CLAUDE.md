# Docs Reorganization Execution Instruction For Claude

> asof: 2026-04-11
> status: pending_execution
> purpose: `docs/` 폴더를 "새 세션이 프로젝트 흐름을 빠르게 복원할 수 있는 구조"로 재정비하기 위한 실행 지시문
> audience: Claude Code 또는 후속 문서 정리 세션 담당 AI

---

## 0. 이 문서의 성격

이 문서는 단순 아이디어 메모가 아니라, Claude가 실제로 순차 실행할 수 있도록 작성된 **문서 구조 정리 실행 지시문**이다.

중요:

- 이 작업의 핵심은 문서를 많이 남기는 것이 아니라, **프로젝트 흐름 복원용 핵심 문서를 적게, 강하게 유지**하는 것이다.
- 사용자는 `docs/` 관리를 매우 중요하게 여기며, 새 세션의 AI가 프로젝트의 현재 위치를 **문서만 보고 정확히 복원**할 수 있어야 한다.
- 따라서 이 작업은 "문서 정리"가 아니라 **프로젝트 운영 정보 구조 재설계**에 가깝다.

---

## 1. 최우선 목표

사용자가 명시한 필수 축은 아래 3개다.

1. **전체 플랜**
2. **각 단계별 성과 모음**
3. **handoff 시 점검해야 하는 파일 목록**

따라서 Claude는 `docs/`를 아래 3개의 정식 진입 문서 중심으로 재정렬해야 한다.

### 1.1 최종적으로 유지할 핵심 3문서

#### A. `docs/MASTER_PLAN_CURRENT.md`

역할:

- 현재 프로젝트의 "전체 플랜" 단일 진실원
- 지금 어느 챕터인지, 다음에 무엇을 할지, 무엇이 금지사항인지, 최신 대표 수치가 무엇인지 한 번에 보여주는 문서

반드시 포함할 항목:

- 현재 챕터 / 현재 Step / 상태
- 최신 운영 baseline
- 최신 대표 성능 수치
- 현재 verdict
- 절대 금지사항 / 불변조건
- 다음 1~2개 Step
- 반드시 먼저 읽어야 할 관련 문서 링크

#### B. `docs/analysis/STEP_RESULTS_INDEX.md`

역할:

- 단계별 성과 모음 인덱스
- P204부터 현재까지 각 단계가 무엇을 했고, 무엇이 성공/실패했고, 어떤 문서를 보면 되는지 요약

반드시 포함할 항목:

- 단계 ID
- 단계 목적
- 대표 결과 수치
- verdict / 상태
- 상세 문서 링크
- 최신성 여부
- 관련 산출물 링크

#### C. `docs/handoff/HANDOFF_REQUIRED_FILES.md`

역할:

- 새 세션 handoff 시 반드시 읽어야 하는 파일 목록
- "항상 읽을 것", "현재 챕터에서 추가로 읽을 것", "최신 산출물 확인용"을 분리한 문서

반드시 포함할 항목:

- Always Read
- Current Chapter Read
- Latest Artifact Check
- 읽지 말아야 할 것 / 선택 참조

---

## 2. 문서 구조 재정렬 기본 철학

Claude는 아래 원칙으로 문서를 정리한다.

### 2.1 top-level `docs/`는 최소화한다

top-level에는 아래처럼 "프로젝트 진입에 반드시 필요한 문서"만 남기는 방향으로 관리한다.

유지 대상 기본안:

- `docs/README.md`
- `docs/MASTER_PLAN_CURRENT.md` 신규
- `docs/docs_governance.md`
- `docs/docs_inventory.md`
- `docs/structure_baseline.md`
- `docs/OCI_EVIDENCE_RESOLVER_GUIDE_V1.md` 유지 여부는 현재 레퍼런스 가치 기준으로 판단하되, 우선은 유지

### 2.2 상세 문서는 하위 폴더로 보낸다

- 설계 / 성과 / 비교 / 계획 문서 → `docs/analysis/`
- closeout / handoff / 세션 인계 문서 → `docs/handoff/`
- 계약 문서 → `docs/contracts/`
- 더 이상 current truth가 아닌 문서 → `docs/archive/`

### 2.3 Current Truth와 기록 문서를 절대 섞지 않는다

새 세션 AI가 가장 자주 실수하는 지점은:

- closeout 문서를 current truth처럼 읽는 것
- deprecated 문서를 현재 구조처럼 오해하는 것
- README와 inventory를 갱신하지 않고 문서만 추가하는 것

Claude는 이 혼선을 줄이는 방향으로만 문서를 재배치한다.

---

## 3. 이번 작업에서 이미 확인된 사실

아래 내용은 사용자와 GPT가 이미 합의했거나, 기존 감사 문서에서 확인된 사실이다.

### 3.1 확정적으로 잘못 배치된 문서 1건

현재:

- `docs/P207_P208_P209_CLEAN_REFACTOR_PLAN.md`

권장:

- `docs/analysis/P207_P208_P209_CLEAN_REFACTOR_PLAN.md`

근거:

- 이 문서는 closeout/handoff가 아니라 **refactor plan / 설계 문서**
- `docs_governance.md` 기준으로 설계/성과 문서는 `analysis/`가 맞다

필수 후속조치:

- `docs/handoff/P208_close_and_P209_handoff.md` 내 참조 경로 갱신
- `docs/docs_inventory.md`에 entry 추가 또는 위치 변경 반영

### 3.2 사용자 승인 없이는 건드리지 말아야 하는 문서 2건

아래 2건은 inventory에서 이미 "추가 검토 후보"로 남아 있으므로, 독단 이동 금지:

- `docs/UI_MAP.json`
- `docs/UI_WIRING_DECISION_V1.json`

원칙:

- 사용자 승인 없이는 `archive/`로 이동하지 않는다
- 필요하면 "후속 승인 필요 항목"으로만 정리한다

### 3.3 임시 감사 메모 성격의 문서

아래 문서는 현재 프로젝트 구조를 장기 설명하는 current truth 문서가 아니라, 특정 세션의 감사/읽기 기록이다.

- `docs/readme_claude.md`
- `docs/readme_gpt.md`

따라서 Claude는 이 문서들을 **장기 운영 기준 문서로 승격시키지 않는다**.

처리 원칙:

- 본 재정비가 끝날 때까지는 보존 가능
- 최종 구조가 자리 잡으면 archive 이동 또는 삭제 제안 가능
- 단, 사용자 승인 없이 삭제하지 않는다

---

## 4. Claude가 실제로 수행할 작업 범위

이번 작업은 **문서 정보 구조 재정비**다. 코드 수정 작업이 아니다.

반드시 수행할 작업:

1. `docs/MASTER_PLAN_CURRENT.md` 생성
2. `docs/analysis/STEP_RESULTS_INDEX.md` 생성
3. `docs/handoff/HANDOFF_REQUIRED_FILES.md` 생성
4. `docs/P207_P208_P209_CLEAN_REFACTOR_PLAN.md` 를 `docs/analysis/`로 이동
5. 관련 참조 경로 갱신
6. `docs/README.md` 를 새 진입 구조에 맞게 갱신
7. `docs/docs_inventory.md` 를 최신 문서 배치에 맞게 갱신
8. 필요하면 `docs/docs_governance.md` 에 최소한의 운영 규칙 보강

이번 작업에서 금지:

- 코드 로직 수정
- `znotes/` 접근
- 사용자 승인 없는 대규모 archive 이동
- `UI_MAP.json`, `UI_WIRING_DECISION_V1.json` 독단 이동
- closeout 문서를 current truth로 재분류

---

## 5. Claude가 먼저 읽어야 할 문서

실행 전 반드시 아래 순서로 읽는다.

1. `docs/docs_governance.md`
2. `docs/docs_inventory.md`
3. `docs/README.md`
4. `docs/readme_claude.md`
5. `docs/readme_gpt.md`
6. `docs/handoff/P208_close_and_P209_handoff.md`
7. `docs/handoff/P207_close_and_P208_handoff.md`
8. `docs/structure_baseline.md`

참고:

- `docs/SSOT/*` 는 필요 시 현재 상태 해석 보강용으로 읽는다
- `docs/analysis/*` 는 단계별 요약 문서 작성 시 참고한다

---

## 6. 생성해야 할 3개 문서의 상세 템플릿

### 6.1 `docs/MASTER_PLAN_CURRENT.md`

권장 섹션:

1. 문서 목적
2. 현재 프로젝트 상태 한 줄 요약
3. 현재 챕터 / 현재 Step
4. 최신 대표 결과
5. 현재 운영 baseline
6. 절대 금지사항 / 불변조건
7. 이번 챕터 목표
8. 다음 Step
9. 반드시 먼저 읽을 문서
10. 최신 확인 산출물

반드시 지킬 점:

- "과거 모든 히스토리"를 길게 쓰지 말고, 현재 진행 기준만 남긴다
- 현재 truth만 적는다
- closeout 요약은 최대 1~2문장으로 압축하고 상세는 링크로 보낸다

### 6.2 `docs/analysis/STEP_RESULTS_INDEX.md`

권장 섹션:

1. 문서 목적
2. 단계별 결과 테이블
3. 현재 활성 챕터
4. reject 되었지만 중요한 챕터
5. 다음 진입 후보

권장 테이블 컬럼:

- Chapter / Step
- 목적
- 대표 결과
- Verdict
- 상태 (`completed`, `rejected`, `analysis_only`, `active`)
- 핵심 문서
- 핵심 산출물
- 비고

반드시 지킬 점:

- 각 단계 상세를 다시 장문으로 쓰지 않는다
- "결과 인덱스" 역할만 한다
- 상세는 기존 analysis/handoff 문서 링크로 연결한다

### 6.3 `docs/handoff/HANDOFF_REQUIRED_FILES.md`

권장 섹션:

1. 문서 목적
2. 새 세션 시작 시 항상 읽을 문서
3. 현재 챕터에서 추가로 읽을 문서
4. 최신 산출물 확인용 파일
5. 선택적으로 읽을 참고 문서
6. 읽지 말아야 할 문서 / 주의사항

반드시 지킬 점:

- "많이 읽기"가 아니라 "반드시 읽어야 할 최소 집합"을 만든다
- 파일 목록 옆에 왜 읽는지 1줄 이유를 붙인다
- 최신 챕터가 바뀌면 이 문서를 같이 갱신한다

---

## 7. README 재설계 방향

Claude는 `docs/README.md` 를 단순 폴더 소개가 아니라 **문서 진입 허브**로 만든다.

최소 포함 내용:

- Current Truth
- Start Here
- Current Chapter
- Handoff Start
- Detailed References

README에서 직접 링크해야 하는 우선 문서:

- `docs/MASTER_PLAN_CURRENT.md`
- `docs/analysis/STEP_RESULTS_INDEX.md`
- `docs/handoff/HANDOFF_REQUIRED_FILES.md`
- `docs/structure_baseline.md`
- `docs/docs_governance.md`
- `docs/docs_inventory.md`

---

## 8. inventory / governance 갱신 지침

### 8.1 `docs/docs_inventory.md`

반드시 반영할 것:

- 새로 생성한 3개 핵심 문서 entry 추가
- 이동한 `P207_P208_P209_CLEAN_REFACTOR_PLAN.md` 위치 반영
- `readme_claude.md`, `readme_gpt.md` 는 임시 감사 메모임을 드러내는 분류 또는 후속 검토 대상으로 명시

### 8.2 `docs/docs_governance.md`

필요 시 아래 규칙을 짧게 보강할 수 있다.

- 새 세션 진입용 핵심 문서는 3개 축으로 관리
- top-level `docs/` 는 최소 집합 유지
- 단계 완료 시 `STEP_RESULTS_INDEX.md` 갱신
- handoff 직전 `HANDOFF_REQUIRED_FILES.md` 갱신
- current truth와 audit memo를 구분

단, governance 문서를 장황하게 다시 쓰지 말고 **최소 보강**만 허용한다.

---

## 9. 실행 순서

Claude는 반드시 순차 처리한다.

### STEP D1 — 기준 문서 재확인

- `docs_governance.md`
- `docs_inventory.md`
- `README.md`
- `readme_claude.md`
- `readme_gpt.md`

결과:

- 현재 구조와 사용자 요구가 충돌하지 않는지 확인

### STEP D2 — 오배치 확정 문서 이동

- `docs/P207_P208_P209_CLEAN_REFACTOR_PLAN.md`
  → `docs/analysis/P207_P208_P209_CLEAN_REFACTOR_PLAN.md`

동반 수정:

- `docs/handoff/P208_close_and_P209_handoff.md` 참조 경로
- `docs/docs_inventory.md`

### STEP D3 — 핵심 3문서 생성

- `docs/MASTER_PLAN_CURRENT.md`
- `docs/analysis/STEP_RESULTS_INDEX.md`
- `docs/handoff/HANDOFF_REQUIRED_FILES.md`

### STEP D4 — README 재구성

- 새 진입 허브 역할로 정리
- 핵심 3문서 링크 중심으로 갱신

### STEP D5 — inventory / governance 정리

- inventory 최신화
- governance 최소 보강

### STEP D6 — 임시 메모 문서 처리 제안

대상:

- `docs/readme_claude.md`
- `docs/readme_gpt.md`

이 단계에서는 삭제하지 말고, 아래 중 하나를 제안만 한다.

- 유지
- archive 이동
- 후속 삭제 후보

---

## 10. 사용자 승인 정책

이번 작업은 여러 STEP으로 나뉘므로, Claude는 **한 번에 전부 처리하지 않는다**.

반드시:

1. STEP 하나 수행
2. 결과 보고
3. 사용자 승인
4. 다음 STEP 진입

특히 승인 필수 구간:

- D2 문서 이동
- D3 핵심 3문서 생성
- D4 README 재구성
- D6 임시 메모 문서 처리

---

## 11. 최종 보고 형식

모든 STEP 종료 보고는 반드시 아래 2개 섹션으로 나눈다.

### A. 기능/산출물 검증

- 지시문 요구사항 충족 여부
- 생성/이동/갱신된 문서 목록
- 링크/참조 경로 정합성
- 금지사항 위반 여부
- commit/push 결과

### B. 구현 규칙/구조 품질 검증

- current truth / closeout / reference / archive 경계 준수 여부
- top-level `docs/` 최소화 방향 준수 여부
- 3개 핵심 문서 중심 구조가 실제로 복원 가능하게 되었는지
- inventory / governance / README 간 충돌 여부
- 임시 감사 문서와 공식 문서의 경계가 분명한지

정직한 보고 원칙:

- 구조가 덜 정리되었으면 "기능 통과 / 구조 미흡"으로 명시
- 과장 금지
- "전부 정리 완료" 같은 포괄 선언 금지

---

## 12. PASS 기준

이번 문서 재정비가 PASS로 인정되려면 아래를 만족해야 한다.

1. `docs/MASTER_PLAN_CURRENT.md` 가 존재한다
2. `docs/analysis/STEP_RESULTS_INDEX.md` 가 존재한다
3. `docs/handoff/HANDOFF_REQUIRED_FILES.md` 가 존재한다
4. `docs/README.md` 가 이 3개 문서를 진입점으로 안내한다
5. `P207_P208_P209_CLEAN_REFACTOR_PLAN.md` 가 `analysis/` 로 이동한다
6. 관련 참조 경로가 깨지지 않는다
7. `docs/docs_inventory.md` 가 최신 배치를 반영한다
8. current truth / closeout / reference / audit memo 경계가 이전보다 더 명확해진다

---

## 13. FAIL 기준

아래면 실패다.

- 핵심 3문서를 만들지 않고 README만 손봄
- 설계 문서를 계속 top-level에 둠
- inventory를 갱신하지 않음
- handoff용 최소 읽기 파일 목록이 여전히 흩어져 있음
- 감사 메모를 current truth처럼 승격시킴
- 사용자 승인 없이 `UI_MAP.json` / `UI_WIRING_DECISION_V1.json` 을 archive 이동

---

## 14. Claude가 유의해야 할 마지막 메모

사용자는 `docs/`를 단순 참고자료가 아니라 **프로젝트 흐름 복원 장치**로 본다.
따라서 이 작업의 성공 기준은 "문서가 예쁘게 정리되었는가"가 아니라,

> 새 세션의 AI가 5분 안에 현재 위치, 다음 단계, 읽어야 할 파일을 정확히 파악할 수 있는가

이다.

Claude는 이 기준으로만 판단하고 실행할 것.
