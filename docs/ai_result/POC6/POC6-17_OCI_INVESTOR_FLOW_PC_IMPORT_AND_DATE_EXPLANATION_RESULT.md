# POC6-17 개발 결과서 — OCI 수급 보관본의 PC 반영과 비교 기준일 설명

작성 2026-11-02 · 작성자: 개발자(VSCode Claude) · 수신: 사용자(실제 반영 승인) → 검증자(Codex) → 설계자

```text
STATUS   = IMPLEMENTED(2026-11-02 · 격리 구현 · 시험) — 조사 요청 V1 → 회신(원인 확인) → 설계 V1(C + B)
           → PLAN(질문 2) → 설계자 PLAN 판정 PASS_WITH_REQUIRED_CORRECTIONS(Q1 (a) · Q2 (a) · §4 보완 · 재제출 없음)
           → 구현 · 관련 시험 · 변이 5종 · 임시 DB 사본 시운전 · 실제 앱 부분 화면(읽기만) · 독립 검토 1회(7건 전부 반영 · §4-2)
           → 전체 회귀(백엔드 5,115 통과 · 프런트 1,149 통과)
           → 검증자 r1 REJECTED(2026-11-02 · F1 OCI 수집 실패 + PC 반영 실패 우선순위 · §11)
           → 개발자 정정(2026-11-02 · F1 · §4-3 · 판정 순서 조합 표 36칸 + 검증자 재현 2경로 · 변이 3종 · 관련/전체 시험)
           → 검증자 r2 VERIFIED(2026-11-02 · 격리 구현 범위 · F1 정정 확인 · §12)
           → 설계자 RESULT PASS(2026-11-02 · §13 · CHECK_REQUIRED 해석 수용 = 판정 §2 · 추가 수정 · 회귀 · 검증 라운드 없음)
           → 사용자 승인(2026-11-02 · 판정 §4 묶음 '모두 승인') → 실제 PC 반영 1회(2026-11-02 21:48:44 ~ 21:48:49 KST · (나) 단독 실행 · §14)
           → 읽기 확인(응답 · 화면 · 복사문) → 구현 커밋 · push
VERIFIER = r2 VERIFIED(2026-11-02 · §12) — 격리 구현 범위 · 실제 PC DB 반영/설계자 RESULT/사용자 승인 별도
DESIGN   = docs/ai_design/POC6/POC6-17_OCI_INVESTOR_FLOW_PC_IMPORT_AND_DATE_EXPLANATION_DESIGN_V1.md
PLAN     = docs/ai_plan/POC6/POC6-17_OCI_INVESTOR_FLOW_PC_IMPORT_AND_DATE_EXPLANATION_PLAN_V1.md(§8 = 판정 반영)
판정     = docs/ai_design/POC6/POC6-17_OCI_INVESTOR_FLOW_PC_IMPORT_AND_DATE_EXPLANATION_PLAN_DECISION_2026-11-02.md
조사     = docs/ai_design/POC6/POC6-17_MARKET_FLOW_FRESHNESS_DIAGNOSIS_REQUEST_V1.md(회신 핵심 = PLAN §0)
```

## 0. 요약

- **원인(조사 회신 · 2026-11-02 17:47 ~ 17:52 KST)**: 11-02 10:09 PC 갱신의 수급 단계만 키움 토큰 '8050 IP 미등록'으로 실패해 PC 수급이 10-22 에 멈췄다. OCI 운영 표는 10-30 이었고, 05 pull 은 보관본만 받아 PC 표에 반영하는 연결이 없었다. 끝일 D = 코스피 ∩ 수급 → 10-22.
- **C(연결)**: PC 「최신 시장 데이터 갱신」의 수급 단계는 이제 키움을 부르지 않는다. 05 보관본을 가져와(150초 상한) PC `market_investor_flow_daily`(KOSPI)에 반영한다. 원/달러 · WTI 단계, OCI 09:40 수집, 키움 공통 함수는 그대로다.
- **B(설명)**: `GET /market/flow-context` 에 `end_basis`(기간 비교 기준일을 막은 자료와 문장)와 `flow_link`(수급 연결 상태)를 더했다. 「시장 흐름 자세히」 · 대시보드 시장 흐름 줄 · KOSPI 카드 · AI 복사문 · 판단 근거 미리보기가 같은 서버 문장을 쓴다.
- **실제 PC DB 는 아직 바꾸지 않았다.** 라이브 DB 실측(18:58 · 19:33 KST): 새 표 없음 · 수급 10-22 · 3,328행 · 출처 키움 직접 조회 하나. 첫 반영은 설계 §9 순서대로 RESULT 판정 뒤 §9 승인 묶음으로 (나) 단독 실행한다.
- **임시 DB 사본 시운전**(라이브 DB 를 사본으로 떠서 실제 PC 보관본을 반영 · 19:10 KST):
  - 수급이 10-22 에서 10-30 으로 채워지고 D 가 10-30 이 된다.
  - 새 행 78개(6일 × 13분류). 기존 3,328행은 값이 그대로이고 출처 · 관측 시각만 OCI 기준으로 바뀐다(판정 §4-1).
  - 값 정정 0 · 최신 값 유지 0. 다른 표는 그대로다.

## 1. 처리한 요구사항

| 요구(설계 · 판정) | 상태 |
|---|---|
| 설계 §3 — 기존 버튼의 수급 단계만 OCI 보관본 반영으로 · 키움 직접 조회 호출 0 · 직접 조회로 대체 안 함 | DONE |
| 설계 §3 — 05 pull · 06 `run --pull` · 13 · OCI 수집 유지 · 새 일정 · 메뉴 · 공개 API 없음 | DONE(pull 은 판정 §2 잠금 보완만) |
| 설계 §4 — 공개 완료 묶음 · 수급 object 만 · 05 검증 재사용 · 관측 시각 순 정정 · 재반영 안전 · 묶음 단위 원자 반영 · 첫 실패에서 멈춤 · 보간 · 삭제 없음 · 추적 기록 | DONE |
| 설계 §5 — 서버 한 곳 공통 문장 · 네 출력 · 상태별 문구 · 원/달러 · WTI 최신 단기 날짜 보존 · 수급만 탓하지 않음 · 키 · IP · 원시 응답 비노출 · 버튼 안내 | DONE |
| 판정 §2 Q1 (a) — pull 비대기 잠금 · 잠금 뒤 임시 칸 정리 · 경합 BUSY · 잠금 잔존 없음 · 150초 초과 시 하위 전송까지 정리 · 06 경합 처리 확인 | DONE |
| 판정 §3 Q2 (a) — 가져오기 실패 · 경합 때 검증된 PC 사본 반영 · 가져오기 · 반영 결과 분리 · 일반 applied 로 정상화 안 함 · 06 확대 없음 | DONE |
| 판정 §4-1 ~ §4-4 — 같은 값도 늦은 관측이면 시각 갱신 · 초기 실패 묶음 제외 · 유한 양수 지수 · UTC Z · gap 판정 · OCI 수집 실패 우선 | DONE(OCI 수집 실패 우선은 r1 F1 로 반영 실패 · 옛 실패 · 기록 없음과의 조합까지 정정 · §4-3) |
| 판정 §5 — 새 표 격리 구현 · 첫 실제 확인 (나) | PARTIAL — 격리 구현 · 시험 · 임시 사본 시운전 완료. 실제 PC 반영은 설계 §9 순서대로 RESULT 판정 뒤 사용자 승인(§9) |
| 판정 §6 — 관련 검사 · 마지막 전체 회귀 1회 | DONE(§8) |
| 부분 화면 문구 확인 | DONE(반영 전 상태 · 읽기만 · §8-4). 반영 뒤 화면은 실제 반영 1회 뒤 확인 |

## 2. 변경된 파일 목록

보고 직전 `git status --short --untracked-files=all` 실측은 §10 에 인용한다.

- 신규 코드:
  - `app/oci_flow_import.py` — 가져오기 · 반영 · 반영 기록 표 · 단독 확인 진입점
  - `app/supply_fx_oil_basis.py` — 기준일 설명 · 수급 연결 상태 · `kst_stamp` 이동
- 신규 시험: `tests/test_poc6_17_flow_import.py`(63건)
- 수정 백엔드:
  - `app/ml_evidence/transfer.py` — pull 잠금
  - `app/supply_fx_oil_refresh.py` — PC 수급 단계 교체 · 시그니처 `client`/`sleep` → `evidence_root`/`flow_pull`
  - `app/supply_fx_oil_store.py` — 출처 상수
  - `app/supply_fx_oil_context.py` — 새 응답 칸 · AI 복사문 한 줄 · `NO_FLOW` 문구
  - `app/api_supply_fx_oil.py` — 응답 모델 칸 2개
- 수정 시험:
  - `tests/conftest.py` — 실제 pull · 라이브 반영 차단
  - `tests/test_poc6_01_supply_fx_oil_sources.py` — PC 수급 경로 시험 2건을 새 단계로
- 수정 프런트:
  - `frontend/lib/api/marketFlow.ts`
  - `frontend/app/components/marketflow/MarketFlowCard.tsx`
  - `frontend/app/components/marketflow/TodayFlowLines.tsx`
  - `frontend/app/components/today/summaryLines.ts`
  - `frontend/app/components/today/SummarySection.tsx`
  - `frontend/app/globals.css`(`.mf-basis` · `.tc-sum-note`)
- 수정 프런트 시험: `frontend/app/components/today/summaryLines.test.ts` · `frontend/app/components/marketflow/MarketFlow.test.tsx`
- 신규 문서:
  - 조사 요청 원문 · 설계 V1 원문 · PLAN 판정 원문(`docs/ai_design/POC6/`)
  - PLAN(`docs/ai_plan/POC6/`)
  - 이 결과서
- 수정 문서: `docs/PROGRAM_TRUTH.md` · `docs/STATE_LATEST.md`

## 3. 신규 추가된 의존성

없음.

## 4. 지시문 외 변경 · 구현 판단

### 4-1. 판단

1. **`refresh_market_flow` 인자 변경**: 키움 시험용 인자 `client` · `sleep` 을 없애고 `evidence_root` · `flow_pull` 을 더했다. 이 함수를 부르는 곳은 `market_refresh_service.py:448` 하나이며 인자 없이 부른다.
2. **기존 수단 재사용**:
   - pull 자식 실행 · 시간 상한 · 프로세스 그룹 정리는 `app/forward_auto/runner.run_child` 를 재사용했다(판정 §2-4).
   - pull CLI 의 `RESULT` 출력 형식과 기존 `BUSY` 종료 코드(3)를 그대로 썼다.
3. **반영 기록 · 단계 기록**:
   - 묶음별 반영 기록은 새 표 `market_investor_flow_import` 에 남긴다(판정 §5 수용 설계).
   - 단계 결과는 기존 `market_refresh_log` 에 출처 2개(`OCI_EVIDENCE_PULL_FOR_FLOW` · `OCI_EVIDENCE_KOSPI_FLOW_IMPORT`)로 남긴다.
   - 두 출처는 `MARKET_FLOW_LOG_SOURCES` 에 넣어 '마지막 전체 갱신' 조회에서 뺐다.
   - 새 표 DDL 은 반영 함수만 실행한다. OCI 일일 수집이 쓰는 `init_market_flow_tables` 에는 넣지 않았다(OCI DB 스키마 불변).
4. **가져오기 실패 분류(판정 §3)**:
   - PC 사본을 반영하는 경우: `busy` · `timeout` · `unreachable`(SSH 목록 실패 · SSH 목록 시간 초과) · `check`(pull 의 확인 필요 — 일부 전송 실패 · OCI 쪽 손상 · 충돌).
   - `failed`(pull 실행 자체의 알 수 없는 실패)는 반영하지 않는다. 기존 PC 수급을 두고 'kept_local'로 표시한다.
   - `check` 를 반영 쪽에 둔 이유: OCI 묶음 하나가 손상되면 pull 이 계속 확인 필요로 끝난다. 이때 반영을 막으면 수급이 영영 멈춘다. 입력 검사는 그대로다.
5. **`kst_stamp` 위치**: `supply_fx_oil_context.py` 에서 `supply_fx_oil_basis.py` 로 옮겼다(순환 import 방지). context 에서 같은 이름으로 다시 내보내므로 기존 import · 시험은 그대로다.
6. **`NO_FLOW` 문구**: '…(키움 인증 · 등록 IP)'를 '…(OCI 수급 보관본 반영 · POC6-17)'로 바꿨다. PC 가 키움을 더 부르지 않기 때문이다.
7. **시험 보호 장치(`tests/conftest.py`)**: 기존 자동 장치 `_neutral_market_flow_step` 에 두 가지를 더했다. 실제 pull(SSH) 실행 금지, 라이브 시장 DB · 라이브 보관소 대상 반영 금지. 안전 가드는 모든 layer 에 일괄 적용했다.
8. **단독 확인 진입점**: `python -m app.oci_flow_import` 를 `oci_flow_import.py` 안의 `main` 으로 두었다(새 도구 파일 없음 · 판정 §5 '동일 핵심 함수'). 이 진입점은 가져오기와 반영만 하고, 원/달러 · WTI 등 다른 공급자는 부르지 않는다.
9. **할 일 · 버튼 안내 조건(PLAN §4)**: 서버 `retry_helps` 가 참이어야 한다. 그리고 다음 셋 중 하나여야 한다: 수급이 기간을 막음, 반영 실패, 옛 직접 조회 실패.

### 4-2. 독립 검토(1회 · 코드 · 계약 대조 · 임시 DB 재현 4건) → 7건 전부 고침

| # | 지적 | 고친 것 | 시험 |
|---|---|---|---|
| 1 (bug) | 수급 상태가 OK · PARTIAL 이 아니면(오타 등) 조용히 영구 제외 | 명시된 `FAILED` 이고 object 가 없을 때만 제외. 그 밖의 상태는 '보관본 확인 필요(수급 상태)'로 멈춤 | `test_unknown_flow_status_is_a_problem_not_silent_exclusion` · 변이 잡힘 |
| 2 | 트랜잭션 안의 sqlite 밖 예외(64비트 넘는 정수) → 앞 범위 기록 유실 · '다시 누르기' 무한 | 순매수 64비트 범위 검사 추가. `BEGIN` 포함 모든 예외에 ROLLBACK 한 뒤 그 묶음에서 멈추고 앞 범위 보존. 예상 밖 오류 사유는 retry 대상이 아님 | 범위 2건 · `test_unexpected_error_rolls_back_that_run_and_keeps_earlier_range` |
| 3 | 가져오기 실패 분기가 OCI 수집 실패를 가림(판정 §4-4) | OCI 최근 수집 실패를 가져오기 상태보다 먼저 판단. 두 사실을 함께 쓰고 retry 없음 | `test_oci_collect_failure_outranks_pull_failure` · 변이 잡힘 |
| 4 | 손상 manifest 폴더 하나가 뒤 반영을 멈추는데 '다시 누르기'를 계속 안내 | 멈춤은 유지(설계 §4 '손상 입력 숨기지 않음'). 사유를 '묶음 목록을 읽을 수 없음'으로 바꿔 retry 없음(pull 로 되살아나지 않음) | `test_unreadable_manifest_dir_stops_without_asking_to_press_again` |
| 5 | PLAN §4 는 옛 직접 조회 실패도 할 일로 적었는데 코드는 제외 | 할 일 · 버튼 안내 조건에 `legacy_direct_failed` 를 넣어 PLAN 과 일치시킴 | 프런트 2건 |
| 6 | 알 수 없는 가져오기 실패에도 PC 사본 반영(판정 §3 '알 수 없는 예외를 PC 사본 사용으로 넘기지 않음') · SSH 시간 초과 분류 | `failed` 는 반영 안 함(§4-1-4). SSH 목록 `TimeoutExpired` → '연결 실패' | `test_unknown_pull_failure_does_not_use_pc_copies` · `run_pull` 분류 1건 · 변이 잡힘 |
| 7 | 반영한 OCI 묶음이 없는데 'OCI 수집본 기준'이라고 씀 | 반영 기록에 `APPLIED` 가 없으면 '가져오기는 정상이지만 반영한 OCI 수급 묶음이 없습니다'(retry 없음) | `test_flow_link_states_from_records` 갱신 |

검토자가 문제없다고 확인한 영역은 다음과 같다.
- 행 우선순위 · 시각 해석
- 원자성 · 실패 묶음 기록 없음
- 묶음 선택(.partial · 연구 묶음 · 같은 run_id 다른 내용)
- pull 잠금(원격 · 임시 칸 정리 전에 획득 · BUSY 쪽 원격 0 · 시간 초과 시 그룹 정리 · 잠금 해제)
- 06 `run --pull` 의 BUSY 처리(기존 pull 실패와 같게 계속 · 주 결과는 forward.run 그대로)
- GET 쓰기 0 · 시험의 라이브 경로 차단

### 4-3. 검증자 r1 정정(2026-11-02 · F1)

**원인**: `read_flow_link` 가 반영 실패(`imp['fail']`) 분기에서 바로 돌아갔다. 그래서 그 아래 'OCI 수집 실패 우선' 판단에 닿지 못했다. 독립 검토 지적 3은 가져오기 실패와의 조합만 고쳤고, 반영 실패 · 옛 직접 조회 실패 · 기록 없음과의 조합은 남아 있었다.

**고친 것**:
- 서버(`app/supply_fx_oil_basis.py`)
  - 연결 상태를 두 단계로 나눴다: `_base_link`(옛 직접 조회 · 반영 실패 · 가져오기 실패 · 반영 정상)를 먼저 만들고, 그다음 확인된 OCI 최근 수집 실패를 **읽기 실패 다음 모든 상태보다 먼저** 판단한다.
  - OCI 수집이 실패했으면 상태 `oci_collect_failed` · `retry_helps=false` 로 둔다. 문장은 'OCI의 최근 수급 수집이 실패했습니다(… 공개) · 다시 갱신해도 바뀌지 않을 수 있습니다 · ' 뒤에 원래 상태 문장을 그대로 붙여 두 사실을 함께 보인다. 예: '수급 자료 반영 실패(… · PC 표 반영 실패) · 수급 10/22까지 사용 중'.
- 화면(같은 규칙 · 모든 layer): `frontend/lib/api/marketFlow.ts :: flowRetryHelps` 를 두었다.
  - 아님이 되는 경우: 서버 `retry_helps` 가 거짓 · 상태 `oci_collect_failed` · `oci_flow_status` 가 OK · PARTIAL · 없음 외의 값.
  - 「지금 할 일」(`summaryLines.ts`)과 버튼 위치 안내(`MarketFlowCard.tsx`)가 이 함수 하나를 쓴다.
  - `retry_helps` 를 쓰는 화면은 이 두 곳뿐이다(grep).

**판정 순서 조합 표**(`test_flow_link_precedence_table` · 기본 상태 9 × OCI 최근 수급 상태 4 = 36칸):

| 기본 상태(OCI 실패 없음) | 기대 상태 · retry | OCI = FAILED 일 때 |
|---|---|---|
| 옛 직접 조회 실패 | legacy_direct_failed · 참 | oci_collect_failed · 거짓 · '마지막 PC 직접 조회 실패' 문장 유지 |
| 기록 없음 | no_record · 참 | 같음 · '아직 OCI 수급을 반영한 기록 없음' 유지 |
| 가져오기 정상 · 새 반영 | applied · 거짓 | 같음 · '수급은 OCI 수집본을 PC에 반영' 유지 |
| 가져오기 정상 · 새 자료 없음 | applied · 거짓 | 같음 · '새 자료 없음' 유지 |
| 반영 실패(보관본 손상) | apply_failed · 참 | 같음 · '보관본 손상' 유지 |
| 반영 실패(충돌) | apply_failed · 거짓 | 같음 · '수급 값 충돌' 유지 |
| 반영 실패(PC 표 반영 실패) | apply_failed · 참 | 같음 · 'PC 표 반영 실패' 유지 |
| 가져오기 경합 · 사본 반영 | applied_local · 참 | 같음 · 'PC에 이미 받은' 유지 |
| 가져오기 경합 · 새 자료 없음 | kept_local · 참 | 같음 · '기존 PC 수급' 유지 |

- OCI = 없음 · OK · PARTIAL 은 기본 상태 그대로다.
- 가져오기 정상 · 반영한 OCI 묶음 0 은 따로 시험한다(`test_flow_link_precedence_pull_ok_without_applied_runs`).

**검증자 재현 2경로를 시험으로 고정**:
- `test_verifier_repro_a_apply_start_error_after_oci_collect_failure`: OCI 수집 실패를 기록한 뒤 다음 실행에서 반영 시작 오류를 주입한다.
- `test_verifier_repro_b_late_older_damaged_run_after_oci_collect_failure`: 최신 FAILED 보다 오래된 묶음이 늦게 도착하고, 그 object 가 손상된 경우다.
- 두 경로 모두 `oci_collect_failed` · `retry_helps=false` 이며 원래 실패 문장이 함께 남는다.
- 화면 쪽: `summaryTasks` 에 서버가 retry 참 + `oci_flow_status=FAILED` 를 줘도 할 일 0, 같은 응답에서 버튼 위치 안내도 없다(PARTIAL 은 막지 않음). `flowRetryHelps` 진리표 7칸.

**변이 3종**(복원 = 내용 다시 쓰기 + 시각 복원). 세 개 모두 시험이 잡았다.
1. r1 이전 판정 순서(반영 실패 · 옛 실패 · 기록 없음이 먼저 반환): 7건 실패.
2. OCI 실패 때 원래 상태 문장을 버림: 9건 실패.
3. 화면 `flowRetryHelps` 의 OCI 상태 규칙 제거: 3건 실패.

**바뀌지 않은 것**: 반영 규칙 · 원자성 · pull 잠금 · 가져오기 분류 · 표 · API 칸 이름. 기존 시험 `test_oci_collect_failure_outranks_pull_failure` 는 문장 형식만 바뀌었고(두 사실을 각각 확인) 기대 상태 · retry 는 같다.

## 5. 알려진 한계 / 미완성

- **실제 PC DB 반영 전이다**(§9 승인 대기). 그래서 지금 화면은 '아직 OCI 수급을 반영한 기록 없음 · 마지막 PC 직접 조회 실패(11/2 10:09 KST · 키움 인증 실패) · 수급 10/22까지 사용 중'으로 나온다.
- **개발 서버가 `--reload` 라 새 코드는 이미 적재돼 있다.** 승인 전에 [최신 시장 데이터 갱신]을 누르면 실제 반영(새 표 생성 포함)이 일어난다. 13 자동 실행(06 `run --pull` · 평일 10:00 ~ 15:20)은 다음 실행부터 새 pull 잠금 코드를 쓴다(잠금 외 동작은 같다).
- **06 자동 실행은 보관본만 받는다.** 화면 자료(PC 수급 표)는 버튼이나 단독 실행 때만 바뀐다(설계 §3 · 안내 문구에 적음).
- **반영 기록의 `refreshed_rows` 는 묶음별 갱신 건수다.** 겹치는 날짜가 여러 묶음에 있으므로 서로 다른 행 수가 아니다. 시운전 기준으로 묶음 합계는 5,590건이고, 실제로 출처 · 시각이 바뀌는 서로 다른 행은 3,328행이다.
- **손상된 묶음 목록 하나는 그 뒤 묶음의 반영을 멈춘다.** 설계 §4 '손상 입력을 숨기지 않음'에 따른 보수적 동작이며, 이때 '다시 누르기' 할 일은 없다. 사람이 보관소를 확인해야 한다.
- 「시장 흐름 자세히」 기존 '늦음' 표시 규칙(E < D)은 그대로다. 수급이 D 를 끌어내리는 경우는 새 `end_basis` 문장이 대신 알린다.
- 기존 프런트 시험 「AI 세션 전달 초안 질문」의 act 경고는 이번 변경 전부터 있던 것이다(새 시험에서는 경고 0).

## 6. 다음 검증자(Codex)에게 알릴 점

- **r2 재검증 대상 = F1 정정(§4-3)**: 판정 순서를 '읽기 실패 → 확인된 OCI 수집 실패 → 그 밖의 상태'로 바꿨다. 화면 두 곳도 같은 규칙(`flowRetryHelps`)을 쓴다. 조합 표 36칸과 검증자 재현 2경로를 시험으로 고정했다.
- **반영 규칙의 근거는 판정 §4-1 이다.** 같은 값이라도 더 늦은 관측이면 출처 · 시각을 올린다. 그래서 첫 반영에서 기존 3,328행의 출처 · 시각이 모두 바뀐다(값은 동일 · 시운전).
- **가져오기 `check` 상태에서도 PC 사본을 반영하는 판단(§4-1-4)은 판정 §3 문구 해석이 필요한 곳이다.** → **설계자 수용 — RESULT 판정 §2 범위**(입력 검증 · 반영 대상 손상 시 멈춤 · 전송 확인 필요 표시 유지 · §13). 판정이 나열한 '망 · SSH · 시간 초과 · 경합'에 `check`(pull 확인 필요)를 더했고, `failed`(알 수 없는 실행 실패)는 뺐다.
- **`run_pull` 은 pull CLI 를 자식 프로세스로 부른다.** 그래서 시험은 가짜 `child` 와 실제 `run_child` 로 나눠 확인했다. 시간 초과 시 손자 프로세스 정리와 잠금 해제는 실제 프로세스로 봤다: `test_timed_out_pull_child_group_is_reaped_and_lock_released`.
- **06 경합 확인 방법**: 실제 `scripts/run_forward_compare.py main(["run","--pull"])` 를 pull · forward.run 가짜로 돌렸다. 결과 `pull = BUSY` · 주 상태 = forward.run 결과 그대로다(`test_06_run_pull_records_busy_without_turning_it_into_success`).
- **conftest 범위**: 새 보호 장치가 모든 시험에 적용된다. 경계 시험은 원본 `run_pull` 을 모듈 import 때 잡아(`REAL_RUN_PULL`) 가짜 `child` 와만 쓴다.
- KS-10 줄 수는 §8-2 에 적었다.

## 7. 사용자 확인이 필요한 항목

1. **§9 실제 반영 승인 묶음**(새 표 생성 · 수급 행 반영 · 단독 실행 1회 · 커밋 · push): DB 스키마 변경이므로 사용자 명시 승인이 필요하다. 설계 §9 순서대로 검증자 · RESULT 판정 뒤에 한 번에 요청한다.
2. **승인 전에는 「요즘 잘 오르는 ETF」의 [최신 시장 데이터 갱신]을 누르지 않는다.** 누르면 같은 반영이 버튼 경로로 일어난다.
3. 반영 뒤 화면(「오늘의 투자 점검」 · 시장 흐름 카드)의 문구는 개발자가 읽기만으로 확인해 보고한다. 필요하면 사용자 실화면으로 확인한다.

## 8. 검증 실측

### 8-1. 시험 · 검사(2026-11-02)

- `black --check` · `flake8` · `py_compile`(변경 Python 10개) 통과. 프런트 `tsc --noEmit` 0 · `npm run lint` 0.
- 새 시험 `tests/test_poc6_17_flow_import.py` **102건 통과**(r1 정정 뒤 · 처음 제출 63건 + 조합 표 36 + 재현 등 3). 관련 묶음(새 시험 + POC6-01 두 파일 + POC6-05 보관) **222건 통과**.
- 프런트 관련 3파일 102건 통과 · **프런트 전체 79파일 / 1,152건 통과**(r1 정정 뒤 · `npm run lint` 0 · `tsc --noEmit` 0).
- 백엔드 전체 회귀: §8-5.
- 처음 제출 변이 5종(r1 정정 변이 3종은 §4-3 · 작업 트리 복원 = 내용 다시 쓰기 + 시각 복원 · `PYTHONDONTWRITEBYTECODE=1`). 다섯 개 모두 시험이 잡았다.
  1. 같은 값의 늦은 관측 무시
  2. pull 잠금 제거
  3. 모르는 수급 상태를 제외로
  4. OCI 수집 실패 우선 제거
  5. 알 수 없는 가져오기 실패에도 반영

### 8-2. 줄 수(KS-10 · 백엔드 핵심 650 · 프런트 900 · 시험 1,500 · `wc -l`)

- 백엔드: `oci_flow_import.py` 546 · `supply_fx_oil_basis.py` 246 · `supply_fx_oil_context.py` 576 · `supply_fx_oil_refresh.py` 290 · `supply_fx_oil_store.py` 272 · `transfer.py` 546
- 프런트: `MarketFlowCard.tsx` 303 · `summaryLines.ts` 483 · `marketFlow.ts` 164
- 시험: `test_poc6_17_flow_import.py` 1,103 · `test_poc6_01_supply_fx_oil_sources.py` 845 · `conftest.py` 725 · `summaryLines.test.ts` 392 · `MarketFlow.test.tsx` 511

### 8-3. 임시 DB 사본 시운전(라이브 DB 를 SQLite backup 으로 사본 · 실제 PC 보관본 읽기 · 가짜 가져오기 'ok' · 19:10 KST)

| 항목 | 반영 전 | 반영 뒤 |
|---|---|---|
| 수급 행 · 마지막 날 | 3,328 · 10-22 · 출처 `KIWOOM_KA10051_KRX` | 3,406 · 10-30 · 출처 전부 `KIWOOM_KA10051_KRX_VIA_OCI` |
| 반영 기록 | 없음 | APPLIED 12묶음(새 78 · 정정 0 · 시각 갱신 5,590 · 같음 507 · 최신 유지 0) · EXCLUDED_NO_FLOW 2묶음(10-22 초기 '키움 인증 정보 없음') |
| 코스피 · 원/달러 · WTI 표 | 6,273 · 554 | 6,273 · 554(불변) |
| 갱신 기록 | 684 | 686(가져오기 · 반영 2행) |
| D · 기준일 문장 | 10-22 · '코스피는 10/30, 수급은 10/22까지 있어 기간 비교는 10/22까지입니다 …' | 10-30 · '기간 비교 기준일 10/30 · 코스피 · 수급 모두 10/30까지' · 연결 'applied' |

### 8-4. 실제 앱 부분 화면(18:58 KST · 반영 전 · 메뉴 이동 · 캡처만 · 버튼 누르지 않음 · `:8000` 요청 GET 11 · POST 0 · 1440px 가로 넘침 0)

- 「오늘의 투자 점검」 「지금 할 일」: 기존 '시장 자료 갱신이 필요합니다.'에 이유 한 줄이 붙는다('코스피는 10/30, 수급은 10/22까지 있어 기간 비교는 10/22까지입니다 · …'). 안내 끝에는 '수급은 OCI가 모은 자료를 이 버튼으로 PC에 반영합니다(자동 실행은 보관본만 받습니다).'가 붙는다. 버튼은 [시장 자료 갱신 화면] 하나다.
- 시장 흐름 줄 · KOSPI 카드: 같은 기준일 문장과 '수급 연결: 아직 OCI 수급을 반영한 기록 없음 · 마지막 PC 직접 조회 실패(11/2 10:09 KST · 키움 인증 실패) · 수급 10/22까지 사용 중'이 경고색으로 나온다.
- 「요즘 잘 오르는 ETF」 시장 흐름 카드: 기간 줄 아래에 기준일 문장 · 수급 연결 문장 · '이 화면의 [최신 시장 데이터 갱신]을 누르면 OCI가 모은 수급을 PC에 반영합니다(…)'가 나온다.
- 같은 서버 응답의 AI 복사문 둘째 줄은 '- [기간 비교 기준일] … · 수급 연결: …'이다.
- 캡처 저장 위치: `/private/tmp/claude-501/-Users-hyungsookim-projects-krx-hyungsoo/a6c4c2ec-40d4-4eb9-a7ff-9759f33e21bb/scratchpad/poc6_17/shots/`(로컬 전용).

### 8-5. 백엔드 전체 회귀

- **r1 정정 뒤** `pytest tests/`(`PYTHONDONTWRITEBYTECODE=1` · 2026-11-02 19:51:19 ~ 20:13:10 KST): `5154 passed, 2 skipped, 1 warning in 1309.17s (0:21:49)` · rc=0(처음 제출 5,115 + 새 시험 39).
- 끝난 뒤 라이브 DB 실측(20:13 KST): `import 표 0 · 수급 ('2026-10-22', 3328) · 출처 [('KIWOOM_KA10051_KRX',)]` — 시험이 라이브 DB 에 쓰지 않았다. 라이브 보관소에 `.pull.lock` 없음(실제 pull 0).

## 9. 실제 반영 승인 묶음(판정 §5 · 설계 §9 — RESULT 판정 뒤 한 번에 승인)

1. **기존 시장 DB(`state/market/market_data.sqlite`)**
   - 새 표 `market_investor_flow_import` 를 생성한다(DB 스키마 변경).
   - 수급 표에 새 행 78개 정도(10-23 · 10-26 ~ 10-30 × 13분류)가 들어간다. 실행 시점 보관본에 따라 늘 수 있다(11-03 09:40 OCI 수집분이 PC 에 받혀 있으면 11-02 거래일분 추가 · 10-31 · 11-01 은 주말).
   - 기존 3,328행은 값은 그대로이고 출처 · 관측 시각만 OCI 기준으로 바뀐다.
   - 반영 기록 약 14행, 갱신 기록 2행이 생긴다.
   - 그 밖의 표(가격 · 코스피 · 원/달러 · WTI · 보유 · 원장 · PARAM)는 바뀌지 않는다.
2. **05 pull 잠금 보완**: 코드 변경이며 이미 작업 트리에 있다. 실제 확인 중에는 기존 SSH 읽기(OCI `list-runs` · 필요한 object · manifest 복사)가 있고, 새 묶음이 있으면 PC 보관 사본에 쓴다.
3. **(나) 단독 실행 1회**: `.venv/bin/python -m app.oci_flow_import`. 그 뒤 `GET /market/flow-context` · 화면 · 복사문을 읽어 확인한다. 외부 공급자 호출 · OCI DB 쓰기 · 수집 · cron · 키 변경은 없다.
4. **커밋 · push**: 이 결과서 §2 · §10 의 파일 그대로(사용자 소유 handoff 문서 제외). 같은 승인 묶음에서 묻는다.

## 10. git 상태

보고 직전 `git status --short --untracked-files=all`(r1 정정 뒤 다시 stage · `git diff --cached --check` 통과 · 커밋 없음 · 파일 구성은 처음 제출과 같음):

```text
M  app/api_supply_fx_oil.py
M  app/ml_evidence/transfer.py
A  app/oci_flow_import.py
A  app/supply_fx_oil_basis.py
M  app/supply_fx_oil_context.py
M  app/supply_fx_oil_refresh.py
M  app/supply_fx_oil_store.py
M  docs/PROGRAM_TRUTH.md
M  docs/STATE_LATEST.md
A  docs/ai_design/POC6/POC6-17_MARKET_FLOW_FRESHNESS_DIAGNOSIS_REQUEST_V1.md
A  docs/ai_design/POC6/POC6-17_OCI_INVESTOR_FLOW_PC_IMPORT_AND_DATE_EXPLANATION_DESIGN_V1.md
A  docs/ai_design/POC6/POC6-17_OCI_INVESTOR_FLOW_PC_IMPORT_AND_DATE_EXPLANATION_PLAN_DECISION_2026-11-02.md
A  docs/ai_plan/POC6/POC6-17_OCI_INVESTOR_FLOW_PC_IMPORT_AND_DATE_EXPLANATION_PLAN_V1.md
A  docs/ai_result/POC6/POC6-17_OCI_INVESTOR_FLOW_PC_IMPORT_AND_DATE_EXPLANATION_RESULT.md
M  frontend/app/components/marketflow/MarketFlow.test.tsx
M  frontend/app/components/marketflow/MarketFlowCard.tsx
M  frontend/app/components/marketflow/TodayFlowLines.tsx
M  frontend/app/components/today/SummarySection.tsx
M  frontend/app/components/today/summaryLines.test.ts
M  frontend/app/components/today/summaryLines.ts
M  frontend/app/globals.css
M  frontend/lib/api/marketFlow.ts
M  tests/conftest.py
M  tests/test_poc6_01_supply_fx_oil_sources.py
A  tests/test_poc6_17_flow_import.py
?? docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md
```

- stage 25개(수정 17 · 신규 8) · 오른쪽 열(작업 트리 변경) 공백.
- `??` 는 사용자 소유 handoff 문서 1건뿐이다(stage 하지 않음).


## 11. 검증자 r1 판정(2026-11-02 · Codex)

**종합 판정: REJECTED.** 격리 구현 범위에서 F1(P2) 1건을 확인했다. 실제 PC DB 반영 · SSH/pull · 버튼 실행 · 커밋 · push는 하지 않았다. 실제 반영은 설계자 RESULT 판정과 사용자 승인 뒤라는 기존 순서를 유지한다.

### 1) A. 기능/산출물 검증

- **A-1 지시 일치: 위반(F1).** 수급 입력/정정/원자성 · pull 잠금 · 조회/실행 경계는 관련 시험에서 확인했다. 다만 PLAN 판정 §4-4의 ‘확인된 최근 OCI 수집 실패 안내가 반복 갱신 버튼 생성보다 우선’이라는 조건이 PC 반영 실패와 겹치면 깨진다.
- **A-2 보고 정확성:** stage 25개(M 17 · A 8) · 작업 파일 일치, 변경 파일/줄 수 · 의존성 추가 없음은 실측과 같다. §1의 우선순위 DONE은 F1 조합까지 충족하지 못한다. 실제 DB 사본 시운전/실화면/전체 회귀는 개발자가 제출한 근거로 구분하며 검증자의 실제 운영 확인으로 기록하지 않는다. 문서 수치 정정 없음.
- **A-3 산출물 정합성: 위반(F1).** API에 `oci_flow_status=FAILED`가 남아 있으면서도 사람에게 보이는 문구는 그 실패를 누락하고 `retry_helps=true`로 반환한다. 이 값이 실제 ‘지금 할 일’과 버튼 안내로 이어진다.
- **A-4 금지사항 위반: 없음.** 새 표는 승인된 격리 구현 범위이며 실제 생성/반영은 실행하지 않았다. 신규 패키지/공급자/API/스케줄 · OCI 쓰기 · 파일 삭제 없음.

**F1 [P2] 확인된 OCI 수집 실패가 PC 반영 실패에 가려져 다시 갱신할 일로 바뀐다.**

- 위치: `app/supply_fx_oil_basis.py:187~210`(`read_flow_link`), 전파 확인: `frontend/app/components/today/summaryLines.ts:398~432`(`summaryTasks`).
- 근거: PLAN 판정 §4-4는 확인된 최근 OCI 수급 수집 실패 안내를 반복 버튼 안내보다 우선하고, `limited_by=flows`가 함께 있어도 ‘다시 누르면 해결’ 할 일을 만들지 않도록 정했다. 설계 §5도 OCI 수집 자체 실패를 반복 클릭으로 해결된다고 안내하지 않는다고 명시한다.
- 재현 A(임시 DB/보관소): PC 수급은 10-22까지이고 OCI 최신 FAILED·object 없음 묶음을 제외 기록으로 반영한다. 이때 `oci_collect_failed`, `retry_helps=false`가 정상 출력되는 것을 먼저 확인한다. 다음 실행에서 로컬 DB 반영 시작 오류를 주입하면 `apply_failed`, `retry_helps=true`, `oci_flow_status=FAILED`로 바뀌며, 문구에는 `PC 표 반영 실패`만 남고 확인된 OCI 수집 실패가 빠진다.
- 재현 B(오류 주입 없이 임시 파일 손상): 정상 과거 수급과 그보다 최신 OCI FAILED를 먼저 기록한다. 이후 최신 FAILED보다 오래된 미반영 묶음이 늦게 도착한 상태에서 그 수급 object 사본을 손상시킨다. 다음 반영은 해당 묶음에서 정상적으로 멈추지만 연결 상태가 `apply_failed`, `retry_helps=true`, `oci_flow_status=FAILED`가 된다. 이 경우에도 여전히 가장 최신인 OCI 수집 실패 문구가 빠진다.
- 실제 출력 예: `수급 자료 반영 실패(… · PC 표 반영 실패) · 수급 10/22까지 사용 중`, `retry_helps=true`, `oci_flow_status=FAILED`.
- 두 실제 백엔드 재현에서 얻은 `flow_link` 값을 그대로 고정해 프런트 `summaryTasks`에 전달했다. 기존 다른 시장 정비 항목은 0개인데도 `시장 자료 갱신이 필요합니다` · `[시장 자료 갱신 화면]` · ‘이동 후 [최신 시장 데이터 갱신]을 눌러 주세요’가 생성된다.
- 원인: `read_flow_link`가 `imp['fail']` 분기에서 즉시 반환한다. 아래쪽의 `oci_status` 실패 우선 분기는 이 경로에서 실행되지 않는다. 제출 시험은 OCI 수집 실패와 가져오기 실패 조합을 확인했지만, OCI 수집 실패와 PC 반영 실패 조합은 다루지 않았다.
- 범위: 한 우선순위 결함이다. PC 반영 오류를 무시해야 한다는 뜻이 아니며, 두 실패를 동시에 사실대로 표시하는 기존 계약의 검증이다. 수급 값 손상/덮어쓰기나 자동 실행은 재현되지 않았다. 새 서명·동기화 구조·수집 정책·06/13 변경을 요구하지 않는다.

### 2) B. 구현 규칙/구조 품질 검증

- **B-1 암묵 fallback:** 별도 위반 없음. 날짜/시각/정수 원/지수값 검증 · 관측 시각 우선순위 · 알 수 없는 pull 실패의 PC 사본 반영 금지 확인. F1은 상태 우선순위의 기능 결함으로 A에서 판정한다.
- **B-2 단일 책임:** 위반 없음. 수급 가져오기/반영 · 기준일/상태 문장 생성 · 표시부가 분리돼 있다.
- **B-3 파일 책임 과다:** 위반 없음. 변경 백엔드 핵심 최대 `supply_fx_oil_context.py` 576줄, 프런트 모듈 최대 `summaryLines.ts` 483줄, 시험 최대 948줄. KS-10 근접/상한 미발동(`conftest.py` 725줄은 시험 fixture).
- **B-4 실험/운영 경계:** 위반 없음. PC의 승인된 수급 반영 경로에 한정돼 있고 기존 pull/export에 운영 DB 쓰기가 생기지 않았다. 06 BUSY 처리 관련 시험도 통과한다.
- **B-5 배포/실행 경로:** 새 모듈/진입점 모두 index 추적 상태이며 `python -m app.oci_flow_import` 경로와 일치한다. Dockerfile/배포 스크립트/OCI 수집 코드 변경 없음. `kst_stamp` 이동은 context에서 같은 이름을 재노출해 기존 import를 유지한다.
- **B-6 기술부채/구조적 퇴행:** F1 외 별도 구조 위반 확인 없음. 공개 목록 고정 · 묶음별 트랜잭션/기록 · 재반영 안전성 · 기존 잠금/자식 정리 함수 재사용 확인.

### 3) 기반 문서 준수

- 신규 md 5개는 승인된 조사 요청 · 설계 · 판정 · PLAN · 결과서 보관 범위다. MongoDB/엔터프라이즈 패턴/프레임워크/신규 의존성 없음.
- 17 한정 수급 반영 예외 외에 PC/OCI 경계, Q6 OPEN, 운영 ML 미승격 및 05/06/13 계약 유지. 기존 15/16을 재개하지 않았다.

### 4) 코드 안전성

- 위험 수준: **NONE**(권한/비밀/임의 실행 경계에 새 위험 확인 없음). 사용자 동작을 잘못 안내하는 기능 결함 F1은 별도로 판정한다.
- 타임아웃과 자식 프로세스 그룹 정리 · 비대기 잠금 · 원시 접속정보 대신 고정 한국어 사유 · 조회의 읽기 전용 경계를 관련 코드/시험에서 확인했다.
- 검증은 저장소 밖 index 사본·임시 DB·임시 보관소·가짜 전송을 사용했다. 실제 `.env` · 운영 DB/연구/보관본 · 사용자 handoff를 읽지 않았고 실제 SSH/공급자/갱신 버튼/서버 재시작 · DB 반영은 실행하지 않았다.

### 5) 범위 폭주

폭주 수준: **NONE**. pull 잠금은 Q1의 한정 보완이며, 수급 표 연결/상태 문장은 이번 승인 범위 안이다. `check` 뒤 검증된 PC 사본을 반영하는 해석은 개발자가 §6에 적은 설계자 RESULT 확인 항목으로 남긴다(F1과 별개).

### 6) 종합 판정 · 실행 근거

- **REJECTED — F1(P2) 1건.** 실제 PC 반영은 계속 승인 대기다.
- 기준 HEAD `437e89db00642e53bdb8f6d05e974ec2af22e67c` · stage 25개(A 8 · M 17) · unstaged 0 · 사용자 handoff 1개 제외. 검증 중 제출 소스 불변 확인.
- 백엔드 관련 **183 passed**(새 63건 포함 · 6.14초). 수급 입력/정정/롤백 · 관측 시각 · 부분/실패 · pull 경합 · 실제 자식/손자 정리 · 06 호출 · GET 쓰기 0 등을 확인했다.
- 프런트 관련 **3파일 99 passed**(2.52초). 공통 문장 · 기존 할 일 병합/억제 · 화면/복사문 · 재조회 범위 관련 시험 통과.
- 독립 백엔드 재현 **2 failed · 대조 1 passed**, 실제 출력에 연결한 독립 프런트 재현 **2 failed · 대조 1 passed**. 네 실패는 모두 같은 F1의 두 조건/출력 전파다. OCI 수집 실패가 없는 반영 오류 대조군은 기존 다시 시도 안내를 유지해 통과했다.
- 변경 Python 10파일 `black --check --workers 1` · `flake8 --jobs=1` · `py_compile` 모두 exit 0. 변경 TS/TSX 7파일 eslint · `tsc --noEmit --incremental false` · `git diff --cached --check` 모두 exit 0.
- 백엔드 전체 **5,115 passed · 2 skipped**, 프런트 전체 **1,149 passed**, 변이 5종은 개발자의 최종 제출 근거를 사용했다. 검증자는 관련/독립 재현만 실행했고 전체 회귀 · 실제 연구 · GPU · OCI 작업을 반복하지 않았다.
- 관련 시험의 Starlette/httpx deprecation 경고와 기존 AI 세션 복사 흐름의 act 경고가 있었지만 관련 시험은 통과했다. 독립 프런트 재현에는 act 경고 없음.
- 근거: `/private/tmp/poc617-r1-verify-9_sgga2b/`의 `backend-related.log`, `frontend-related.log`, `independent-precedence.log`, `frontend-independent.log`, `checks.json`, `audit.json`. 독립 시험은 그 안 `src/tests/test_verifier_poc617_precedence.py`, `src/frontend/app/components/today/VerifierOciFailure.test.ts` 및 고정 응답 `VerifierOciFailureCases.json`(저장소 밖 전용).

### 7) 사용자에게 한마디 · 검증자 수정 내역

개발자에게 이 §11을 전달해 F1 정정 후 r2 재검증을 요청하면 된다. 실제 반영 · 새 표 생성 · 갱신 버튼 · 커밋 · push는 기존 승인 순서를 유지하며 지금은 실행하지 않는다.

**검증자가 수정한 파일은 이 결과서 하나다.** 상단 STATUS/VERIFIER에 r1 판정을 기록하고 이 §11을 추가했다. 개발자 본문 · 코드 · 시험 · 설계 · PLAN · STATE · PROGRAM_TRUTH는 수정하지 않았다. 문서 수치 정정 · 실제 DB 작업 · 커밋 · push 없음.


## 12. 검증자 r2 재검증(2026-11-02 · Codex)

**종합 판정: VERIFIED(격리 구현 범위).** F1 정정을 확인했고 추가 코드 결함은 확인하지 않았다. 실제 PC DB 반영/새 표 생성/단독 실행은 미실행이며, 다음은 설계자 RESULT 판정이다. 이 판정은 실제 반영 · 커밋 · push 승인을 대신하지 않는다.

### 1) A. 기능/산출물 검증

- **A-1 지시 일치: 통과.** 읽기 실패를 먼저 구분하고, 확인된 OCI 최근 수집 실패는 다른 연결 상태보다 우선하면서 PC 반영/가져오기/옛 직접 조회 실패도 문장에 함께 남긴다. 판정 §4-4의 반복 버튼 억제와 기존 다른 자료 할 일 유지 계약을 충족한다.
- **A-2 보고 정확성: 통과.** stage 25개(A 8 · M 17) · 작업 파일 일치 · 사용자 handoff 1개 제외가 실측과 같다. r1 이후 변경 11개(운영 코드 4 · 시험 3 · 문서 4), `supply_fx_oil_basis.py` 246줄 · 새 시험 파일 1,103줄 · `marketFlow.ts` 164줄도 일치한다. 문서 수치 정정 없음.
- **A-3 산출물 정합성: 통과.** 기존 독립 재현 두 경로에서 `state=oci_collect_failed`, `retry_helps=false`, `oci_flow_status=FAILED`를 유지하며 OCI 실패와 원래 반영 오류를 함께 보인다. 같은 서버 문장을 기존 공통 출력에 전달하는 경로와 화면의 반복 안내 억제도 확인했다.
- **A-4 금지사항: 위반 없음.** 승인된 새 표의 격리 구현 범위에서 검증했다. 실제 DB · 보관소 · SSH/외부 공급자 · 버튼 · OCI 쓰기/배포/cron · 커밋/push는 실행하지 않았다. 신규 의존성/공급자/API/스케줄/파일 삭제 없음.

**F1 정정 확인**

- r1 독립 백엔드 시험을 수정하지 않고 새 index 사본에 적용해 **3 passed**를 확인했다. 알려진 OCI 실패 뒤 로컬 반영 시작 오류와, 최신 FAILED보다 오래된 판의 늦은 도착/PC object 손상에서 모두 우선순위가 유지된다. OCI 실패가 없는 재시도 가능 반영 오류 대조군은 기존 안내를 유지한다.
- 제출 시험의 기본 상태 9 × OCI 상태 4 **36칸**, 반영 묶음 없음 대조, 개발자가 추가한 두 재현도 모두 통과한다. 실제 기록 읽기 실패는 `unknown`으로 남고 반복 안내를 만들지 않는다.
- r1의 잘못된 서버 출력(`state=apply_failed`, `retry_helps=true`, `oci_flow_status=FAILED`)을 고정한 독립 프런트 시험도 수정 없이 **3 passed**다. 두 문제 입력에서 `summaryTasks` 결과는 빈 목록이며 정상 대조군은 기존 `market_refresh` 할 일을 유지한다.
- `flowRetryHelps`를 「지금 할 일」과 시장 흐름 카드의 버튼 위치 안내가 함께 사용한다. 서버가 retry 참을 줘도 상태가 `oci_collect_failed`이거나 OCI 최근 상태가 FAILED이면 두 위치 모두 반복 안내를 만들지 않는다. 관련 실제 카드 시험도 통과한다.
- 반영 규칙 · 관측 시각 우선순위 · 묶음 원자성 · pull 잠금/상한/그룹 정리 · 가져오기 분류 · 06 경계는 r1과 코드가 같고 관련 시험에서 다시 통과했다.

### 2) B. 구현 규칙/구조 품질 검증

- **B-1 암묵 fallback:** 위반 없음. F1 실패 우선순위가 정정됐고, 입력 검증과 알 수 없는 pull 실패의 반영 금지 경계는 유지한다.
- **B-2 단일 책임:** 위반 없음. 기본 연결 문구와 OCI 수집 실패 우선 적용을 같은 기준일/연결 상태 모듈 안에서 분리했고, 화면 두 위치가 한 함수로 반복 가능성을 판단한다.
- **B-3 파일 책임 과다:** 위반 없음. 변경 백엔드 핵심 최대 `supply_fx_oil_context.py` 576줄, 프런트 모듈 최대 `summaryLines.ts` 483줄, 시험 최대 1,103줄. KS-10 근접/상한 미발동(`conftest.py`는 시험 fixture).
- **B-4 실험/운영 경계:** 위반 없음. 기존 pull/export에 운영 DB 쓰기가 생기지 않았고, 06/13의 실행/학습 규칙 변경 없음. PC 반영은 17의 별도 함수 경로다.
- **B-5 배포/실행 경로:** 영향 없음. 새 모듈/단독 진입점은 index 추적 상태이며 import 경로 존재. Dockerfile/배포/OCI 수집 경로 변경 없음.
- **B-6 기술부채/구조적 퇴행:** 위반 없음. F1 해소 확인. 기존 수급 값의 시각 우선순위 · 재실행 안전성 · 묶음별 트랜잭션 · 기존 잠금/자식 정리 재사용 유지.

### 3) 기반 문서 준수

승인된 조사 요청/설계/판정/PLAN/결과 문서 외 신규 md 추가 없음. MongoDB · 엔터프라이즈 패턴 · 프레임워크 · 의존성 추가 없음. 17 한정 수급 반영 예외 외 PC/OCI 경계 · Q6 OPEN · 운영 ML 미승격 · 05/06/13 및 종료된 15/16 계약 유지.

### 4) 코드 안전성

위험 수준: **NONE**. 권한/비밀/임의 실행 경계의 새 위험 확인 없음. 격리 사본 · 임시 DB/보관소 · 가짜 전송/상태만 사용하고 기존 시험 가드를 유지했다. 실제 `.env` · 운영 DB/연구/보관본 · 사용자 handoff를 읽거나 수정하지 않았고 실제 수집/SSH/pull/버튼/서버 재시작/DB 반영은 실행하지 않았다.

### 5) 범위 폭주

폭주 수준: **NONE**. 이번 정정은 F1의 서버 판단과 화면 두 안내 경로 및 시험/문서 범위 안이다. `check` 뒤 검증된 PC 사본을 쓰는 개발자 해석은 결과서 §6에 이미 명시된 설계자 RESULT 확인 항목으로 유지한다.

### 6) 종합 판정 · 실행 근거

- **VERIFIED(격리 구현 범위) — F1 정정 확인.** 실제 PC 반영/스키마 생성/연결 확인은 승인 전 미실행이다.
- 기준 HEAD `437e89db00642e53bdb8f6d05e974ec2af22e67c` · stage 25개(A 8 · M 17) · unstaged 0 · 사용자 handoff 1개 제외. 검증 중 제출 소스 불변 확인.
- 백엔드 관련 **222 passed**(새 시험 102건 포함) + 기존 독립 **3 passed** = **225 passed**(6.74초).
- 프런트 관련 **3파일 102 passed** + 기존 독립 **1파일 3 passed** = **4파일 105 passed**(2.84초). 합계 **330 passed · 실패 0**.
- 변경 Python 10파일 `black --check --workers 1` · `flake8 --jobs=1` · `py_compile`, 변경 TS/TSX 7파일 eslint · `tsc --noEmit --incremental false`, `git diff --cached --check` 모두 exit 0.
- 백엔드 전체 **5,154 passed · 2 skipped** · 프런트 전체 **1,152 passed** · 정정 변이 3종은 개발자의 최종 제출 근거를 사용했다. 검증자는 관련/독립 재현만 실행했고 전체 회귀/변이 · 실제 연구/GPU/OCI 작업을 반복하지 않았다.
- Starlette/httpx deprecation 및 기존 시장 흐름 AI 세션 전달 경로의 act 경고는 있었지만 관련 시험은 통과했다. 독립 프런트 시험에는 act 경고 없음.
- 근거: `/private/tmp/poc617-r2-verify-hxgoae7j/`의 `backend-related-and-repro.log`, `frontend-related-and-repro.log`, `checks.json`, `audit.json`, `diffs/`. 기존 독립 시험은 그 안 `src/tests/test_verifier_poc617_precedence.py`, `src/frontend/app/components/today/VerifierOciFailure.test.ts`와 고정 응답 JSON(저장소 밖 전용).
- 실제 PC DB 상태/사본 시운전/화면 날짜는 개발자 보고 근거로 구분하며, 검증자가 라이브 DB/화면을 직접 다시 확인했다고 기록하지 않는다.

### 7) 사용자에게 한마디 · 검증자 수정 내역

격리 코드 검증을 통과했다. 다음은 설계자 RESULT 판정이며, 이후 실제 PC 반영 · 단독 실행 · 커밋/push 승인 묶음을 진행하면 된다. 승인 전 갱신 버튼은 계속 실행하지 않는다.

**검증자가 수정한 파일은 이 결과서 하나다.** 상단 STATUS/VERIFIER를 r2 VERIFIED로 바꾸고 이 §12를 추가했다. r1 §11 · 개발자 본문/§4-3 · 코드 · 시험 · 설계 · PLAN · STATE · PROGRAM_TRUTH는 보존했다. 문서 수치 정정 · 실제 DB 작업 · 커밋 · push 없음.

## 13. 설계자 RESULT 판정 — 2026-11-02(원문 · 별도 파일 `docs/ai_design/POC6/POC6-17_OCI_INVESTOR_FLOW_PC_IMPORT_AND_DATE_EXPLANATION_RESULT_DECISION_2026-11-02.md`)

작성: 2026-11-02 · 설계자 → 개발자

**판정: PASS — 격리 구현과 검증 결과를 수용한다. `CHECK_REQUIRED` 뒤 검증된 PC 사본을 반영하는 해석도 §2 범위로 수용한다. 다음은 사용자 승인에 따른 실제 PC 반영 1회와 종료 처리다.**

대상: `docs/ai_result/POC6/POC6-17_OCI_INVESTOR_FLOW_PC_IMPORT_AND_DATE_EXPLANATION_RESULT.md`
판정 대상 첨부 SHA256: `cda5053166e3b41c6480cab3e61244c5019dc8904d3bf70410b3280d48c19208`

#### 1. 수용 근거와 확인 범위

설계자는 첨부 결과서 408줄 전체와 사용자 전달문을 검토했다. 실제 코드·PC DB·보관소·실화면·OCI를 직접 재현하지 않았다. 아래 근거의 주체를 구분한다.

| 근거 | 주체와 이번 수용 범위 |
|---|---|
| 독립 검토 7건 정정, 새 수급 반영·기준일 설명·pull 잠금 구현 | 개발자 보고와 검증자의 코드·관련 시험 확인 |
| r1 F1: OCI 수집 실패가 PC 반영 실패에 가려짐 | 검증자의 독립 재현. r2에서 같은 재현을 수정 없이 통과했고 두 사실 표시·반복 안내 억제를 확인 |
| r2 VERIFIED(격리 구현 범위) | 검증자 관련·독립 검사 합계 330건 통과, 추가 코드 결함 없음, 코드 안전성·범위 폭주 NONE |
| 전체 회귀: 백엔드 5,154 통과·2 제외, 프런트 1,152 통과 | 개발자 제출 근거. 검증자가 전체 회귀를 반복한 것으로 적지 않음 |
| 임시 DB 시운전: 수급 10-22 → 10-30, D도 10-30, 신규 78행 | 실제 PC 보관본을 사용한 개발자 사본 시운전. 라이브 DB 반영 성공 증거와 구분 |
| 실제 앱의 반영 전 문구·GET 읽기·POST 없음 | 개발자 확인. 반영 뒤 화면 확인은 아직 남음 |
| 실제 PC DB: 새 표 없음, 수급 10-22·3,328행 | 개발자 실측 보고. 실제 반영·배포 완료로 해석하지 않음 |

검증된 코드·시험을 고칠 차단 조건은 남기지 않는다. 이번 PASS는 실제 PC DB 쓰기·커밋·push에 대한 사용자 승인을 대신하지 않는다.

#### 2. 설계자 확인 항목 — `CHECK_REQUIRED` 해석 수용

PLAN 판정 §3은 통신·시간 초과·경합을 명시했다. 개발자는 pull의 `CHECK_REQUIRED`도 **실제 수급 반영 입력을 별도로 검증하는 경로**로 보냈다. 이 확대를 결과서에 공개했으며, 다음 구분에 따라 수용한다.

1. **pull 전체 결과와 PC 수급 입력의 유효성은 별개다.** 어떤 원격 묶음의 전송·검증 문제가 전체 pull을 확인 필요로 만들었다고 해서 PC의 모든 기존 수급 사본이 무효가 되는 것은 아니다.
2. 반영할 공개 완료 묶음의 manifest·참조·hash·수급 내용·시각·단위와 기존 반영 기록의 충돌 검사는 그대로 수행한다. `CHECK_REQUIRED`를 입력 검증 면제나 손상 파일 사용 허가로 해석하지 않는다.
3. **반영 대상의 손상·누락·충돌이면 그 묶음에서 멈춘다.** 이전 완료 범위는 보존하지만 문제 묶음을 건너뛰어 뒤의 값만 넣고 전부 성공이라고 쓰지 않는다. 명시된 FAILED·object 없음 묶음의 제외와 구분한다.
4. 같은 run_id의 manifest 충돌, 읽을 수 없는 묶음 목록, 알 수 없는 실행 실패(`failed`)의 처리 경계도 유지한다. 알 수 없는 예외를 모두 PC 사본 반영으로 넘기지 않는다.
5. 사용할 수 있는 PC 사본을 반영해도 **원격 전송·검증의 확인 필요는 남긴다.** `applied_local` 등으로 가져오기 결과와 반영 결과를 분리하고, 실제 사용한 자료일을 표시한다. OCI 최신 자료와 일치·전체 pull 정상·원격 보관소 정상으로 표현하지 않는다.
6. 확인된 최신 OCI 수급 수집 실패는 다른 상태와 함께 표시하고 반복 클릭 안내를 억제한다. 이 수집 실패 판단도 현재 확보한 기록의 시각에 근거한 것으로, 실시간 OCI 상태 확인으로 확대하지 않는다.

이는 **검증된 이전 사본의 제한된 사용을 허용하는 운영 판단**이다. 원격의 손상·충돌을 해결했다는 판단은 아니다. 이런 문제가 실제로 남으면 실패/확인 필요와 사람이 점검할 범위를 기록하며, 이번 승인으로 원격 원본을 고치거나 삭제하지 않는다.

검증자가 확인한 입력 거절·원자성·실패 노출을 유지하는 현재 구현을 수용하므로, 이 해석 문구를 반영하기 위한 추가 코드 수정·재실행·검증자 라운드는 요구하지 않는다.

#### 3. 구현 판단과 남는 경계

- `market_investor_flow_import`와 수급 표의 묶음별 원자 반영, 같은 값도 최신 관측이면 출처·시각 갱신, 과거 판의 덮어쓰기 방지를 수용한다.
- 가져오기·반영을 별도 단계 기록으로 남기고 마지막 전체 시장 갱신 조회에서 두 보조 출처를 제외하는 판단을 수용한다.
- pull 잠금과 기존 자식 프로세스 그룹 정리 재사용, 06 경합 처리의 기존 규약 유지, `kst_stamp` 이동과 기존 이름 재노출, 조회의 쓰기 0을 수용한다.
- 서버 공통 기준일·연결 설명과 화면의 공통 `flowRetryHelps`를 통한 반복 안내 판단을 수용한다. 원래 기간 계산식과 자료별 최신 단기 날짜는 유지한다.
- 실제 연결 상태는 여전히 PC 반영 시점 기준이다. **06 자동 실행은 보관본만 받으며, PC 수급 표는 기존 갱신 버튼 또는 이번 단독 확인 함수에서 반영한다.**
- 손상된 반영 대상이나 읽을 수 없는 묶음 목록은 후속 반영을 멈출 수 있다. 이를 감추기 위해 자동 삭제·입력 건너뛰기·직접 키움 조회 대체를 추가하지 않는다.
- 원/달러·WTI 수집, OCI 09:40 수집·DB, 키움 공통 함수, 06·13 실행/학습 규칙에 대한 별도 변경·배포는 이번 종료 조건이 아니다.

#### 4. 실제 적용 승인 묶음 — 결과서 §9 수용

개발자는 아래 실제 범위를 사용자가 한 번에 검토·승인할 수 있게 제시한다. 동일 범위를 이미 승인받았다면 재승인하지 않는다. 현재 전달된 보고에서는 아직 승인·실제 반영 전이다.

1. **PC 시장 DB:** 새 반영 기록 표 생성, 수급 신규 행 반영, 기존 동일값 행의 출처·관측시각 갱신, 반영/갱신 기록 추가.
2. **실제 가져오기:** 기존 OCI 보관 경로 SSH 읽기·필요한 파일의 PC 보관 사본 쓰기. pull 잠금 보완은 실제 호출부터 적용된다.
3. **(나) 단독 확인 1회:** `.venv/bin/python -m app.oci_flow_import`. 새 수급 반영과 같은 핵심 함수를 사용하며 원/달러·WTI 등 다른 공급자를 호출하지 않는다.
4. **읽기 확인과 커밋·push:** 실제 결과·문서 정리·판정 원문을 포함한 파일 목록을 확인한다. 사용자 소유 handoff, 연구 산출물·로컬 연구 브랜치는 포함하지 않는다.

현재 보고의 기준값은 신규 78행·기존 동일값 3,328행의 출처/시각 갱신이다. 실행 시점의 정상 보관본이 늘었거나 기존 값이 정정됐다면 **실제 범위와 근거**를 기록한다. 승인된 대상·정정 규칙 안의 변화와 대상 밖 쓰기를 구분하며 숫자를 예상값에 맞추지 않는다.

본 판정 원문 추가와 종료 기록 정리로 최종 파일 수는 현재 stage 25개와 달라질 수 있다. 커밋 직전에 실측한 파일 목록과 수를 사용한다. OCI DB 쓰기·코드 pull 배포·cron·키·IP 등록 변경·외부 공급자 수집은 이 묶음에 포함하지 않는다.

실제 승인 전에는 갱신 버튼으로 선행 반영하지 않는다. 승인 후에는 단독 확인 경로를 사용하므로 전체 시장 갱신 버튼을 이어서 누를 필요 없다.

#### 5. 실제 확인과 종료 조건

승인 뒤 한 번 실행하고 다음을 기록한다.

- 실제 실행·가져오기·반영 결과와 시각, 사용 묶음·수급 자료일, 신규·값 정정·관측시각 갱신·같음·최신 유지 건수.
- 묶음별 누적 갱신 건수와 서로 다른 행 수를 구분한다. 사본 시운전의 **5,590건은 묶음별 관측시각 갱신 합계**, 기존 서로 다른 행은 **3,328행**이라는 설명을 유지한다.
- 수급 표와 반영 기록, 시장 흐름 응답의 D·`end_basis`·`flow_link`, 대시보드·시장 흐름 자세히·복사문을 읽어 확인한다. 미리보기는 같은 `ai_text` 연결을 재사용한다.
- 이전 입력과 같으면 수급과 공통 D가 10-30까지 반영되는지 확인한다. 더 나중 자료가 들어오면 공통 날짜 정의로 결과를 판단한다. 코스피 등 다른 표의 날짜를 임의로 밀지 않는다.
- 격리 시험에서 확인한 비대상 표 불변과 실제 DB의 행 수·기간 등 요약 대조를 구분한다. 실제 요약 조회만으로 전체 내용의 독립 검증을 했다고 쓰지 않는다. 확인만을 위한 전 DB 대용량 해시·복제·전체 회귀는 추가하지 않는다.
- 실제 화면의 반영 뒤 문구와 실패/기간 제한 안내를 개발자가 확인해 보고한다. 사용자의 전체 화면 재확인을 종료의 필수 대기로 만들지 않는다.

**검증된 코드로 실제 PC 반영과 위 읽기 확인을 마치고, 승인된 커밋·push·종료 기록까지 성공하면 추가 RESULT 재판정 없이 `IMPLEMENTED_VERIFIED_CLOSED`로 종료할 수 있다.**

허용된 `CHECK_REQUIRED → 검증된 PC 사본 반영` 경로로 끝났다면 그 전송 확인 필요는 별도 남은 상태로 기록한다. 이 경로를 사용했다는 이유만으로 정상 연결 전체가 증명된 것은 아니다. 반영·표시 확인이 성공했다는 기능 종료와 OCI 최신 확인/원격 보관소 정상 여부를 구분한다.

반영 자체가 실패하거나 입력 손상·충돌로 실제 목표를 확인하지 못하면 성공으로 닫지 말고, 완료된 범위와 차단 지점을 짧게 보고한다. 반복 실제 실행·원격 복구·새 원천 수집을 자동으로 붙이지 않는다.

검증된 코드가 그대로이고 실제 확인·기록 정리만 진행한 경우 추가 학습·회귀·검증자 재검증은 없다. 코드 결함으로 수정이 필요해지면 그 변경에 필요한 검사 범위만 정한다.

#### 6. 기록과 최종 보고

- 본 판정 원문을 보관하고 결과서에 추가한다. 결과서 §6의 해석 질문은 ‘설계자 수용 — 본 판정 §2 범위’로 연결하되 당시 원문·r1·r2 기록을 지우지 않는다.
- PLAN·STATE·PROGRAM_TRUTH는 실제 진행 시점에 맞춘다. 실제 반영 전 상태를 미리 CLOSED나 최신화 성공으로 바꾸지 않는다.
- 종료 보고에는 구현/종료 커밋·push 결과, 실제 반영 시각·상태·자료일·D, 실제 가져오기 상태와 남은 제한을 짧게 적는다. 재판정 요청은 아니다.
- POC6-15·16 종료, 05 보관·06 전향 기록·13 일정, Q6 OPEN·운영 ML 미승격·미완료 요구를 유지한다. 새 연구·전체 자료 동기화·새 UI 단계·handoff를 자동으로 열지 않는다.

#### 개발자 전달문

POC6-17 RESULT는 PASS입니다(격리 구현 수용·실제 PC 반영 전). CHECK_REQUIRED 뒤 PC 사본 반영은 본 판정 §2처럼 입력 검증과 전송 확인 필요를 유지하는 범위로 수용합니다. 추가 코드 수정·전체 회귀·검증자 라운드는 요구하지 않습니다. 결과서 §9를 본 판정 §4와 함께 한 번에 승인받은 뒤, (나) 단독 실제 반영 1회와 읽기 확인·커밋·push·종료 기록을 진행해 주세요. §5 조건을 충족하면 추가 RESULT 재판정 없이 닫고 사실만 짧게 보고하면 됩니다.

## 14. 실제 PC 반영 1회(2026-11-02 · 사용자 승인 · 판정 §4 · §5)

- **승인**(2026-11-02): 사용자가 판정 §4 묶음 '모두 승인'을 선택했다. 범위: 새 표 생성 · 수급 반영 · 실제 가져오기 · 단독 실행 1회 · 읽기 확인 · 구현 커밋 · push · 종료 기록 커밋 · push.
- **실행**: `.venv/bin/python -m app.oci_flow_import`(2026-11-02 21:48:44 ~ 21:48:49 KST) → `RESULT {"refresh_id": "manual-20261102T124844Z", "problems": []}` · rc=0.
  - 다른 공급자 호출 · OCI DB 쓰기 · 갱신 버튼 · 서버 재기동은 없었다.
- **가져오기**: `OCI_EVIDENCE_PULL_FOR_FLOW` 1행 · 성공 1 · 실패 0 · 4.219초.
  - PC 보관 묶음은 18개 그대로다(새로 받은 묶음 없음 · 06 이 11-02 10:06 에 이미 받음). 그래서 이번 반영 입력은 11-02 09:40 OCI 수집까지다.
  - `CHECK_REQUIRED` 경로는 쓰지 않았다(가져오기 정상).
  - pull 잠금 파일 `state/ml/evidence/.pull.lock`(0바이트 · 잠금용 · 보관 대상 아님)이 생겼다.
- **반영**: `OCI_EVIDENCE_KOSPI_FLOW_IMPORT` 1행 · 시도 12 · 성공 12 · 실패 0 · 0.096초. 반영 기록(새 표) 14행:
  - APPLIED · OK 12묶음(`20261022T122253Z_6acf5d74` ~ `20261102T004001Z_8184eb7c` · 마지막 자료일 10-30 · 반영 시각 2026-11-02T12:48:49Z).
  - EXCLUDED_NO_FLOW · FAILED 2묶음(10-22 초기 '키움 인증 정보 없음').
- **건수**:
  - 새 행 78(10-23 · 10-26 · 10-27 · 10-28 · 10-29 · 10-30 × 13분류) · 값 정정 0 · 최신 값 유지 0.
  - 관측 시각 갱신 5,590건은 **묶음별 합계**다. 실제로 출처 · 관측 시각이 바뀐 서로 다른 기존 행은 **3,328행 전부**이고, 값은 그대로다.
  - 같음 507건(묶음별 합계).
- **수급 표(21:49 KST)**:
  - 반영 전: 3,328행 · 2025-09-30 ~ 2026-10-22 · 출처 `KIWOOM_KA10051_KRX`.
  - 반영 뒤: 3,406행 · 2025-09-30 ~ 2026-10-30 · 출처 전부 `KIWOOM_KA10051_KRX_VIA_OCI` · `collected_at` = OCI 관측 시각(2026-10-22T12:23:01Z ~ 2026-11-02T00:40:09Z).
  - 사본 시운전(§8-3)과 같은 수치다.
- **표 행 수 요약 대조(전 · 뒤 · 전체 내용 검증 아님)**: 바뀐 표는 셋뿐이다.
  - `market_investor_flow_daily` 3,328 → 3,406
  - `market_investor_flow_import` 없음 → 14
  - `market_refresh_log` 684 → 686
  - 그 밖의 12개 표(ETF 가격 1,436,375 · 코스피 등 지수 6,273 · 원/달러 · WTI 554 · NAV · 구성종목 · ML 특징 등)는 행 수가 같다. 코스피 · 원/달러 · WTI 마지막 날짜는 10-30 그대로다.
- **시장 흐름 응답(21:49 KST)**:
  - `D = 2026-10-30` · 1M · 3M · 6M · YTD 기간 끝 모두 10-30.
  - `end_basis = {limited_by: null, text: '기간 비교 기준일 10/30 · 코스피 · 수급 모두 10/30까지'}`.
  - `flow_link = {state: applied, retry_helps: false, oci_flow_status: OK, text: '수급은 OCI 수집본을 PC에 반영(11/2 21:48 KST · 10/30까지)'}`.
  - 오늘 첫 줄: '시장 흐름 6개월(10/30까지): 코스피 -13.16% · 외국인 누적 순매도 -153.6조원 · 최근 20거래일 일평균 매도 감소 …'.
  - AI 복사문(6개월) 둘째 줄: '- [기간 비교 기준일] 기간 비교 기준일 10/30 · 코스피 · 수급 모두 10/30까지 · 수급 연결: 수급은 OCI 수집본을 PC에 반영(…)'. 판단 근거 미리보기는 같은 `ai_text` 를 쓴다.
- **실제 화면(21:49 KST · 메뉴 이동 · 캡처만 · `:8000` GET 11 · POST 0 · 1440px 가로 넘침 0)**:
  - 「오늘의 투자 점검」: 「지금 할 일」이 없어졌다(반영 전에는 수급 기간 제한 이유가 붙은 '시장 자료 갱신이 필요합니다.'). 시장 흐름 줄은 '6개월(10/30까지)'이고 경고 설명 줄이 없다. KOSPI 카드의 설명 줄도 없다.
  - 「요즘 잘 오르는 ETF」 시장 흐름 카드: '기간 2026-05-04 ~ 2026-10-30 · 끝일 D 10/30' 아래에 기준일 문장과 '수급 연결: 수급은 OCI 수집본을 PC에 반영(11/2 21:48 KST · 10/30까지)'(경고색 아님)이 나온다. 버튼 위치 안내는 없다.
- **남은 제한**:
  - PC 수급 표는 버튼 · 단독 실행 때만 바뀐다(06 자동 실행은 보관본만 받는다).
  - 오늘(11-02) 거래일 수급은 OCI 11-03 09:40 수집 뒤 다음 반영에서 들어온다.
  - 판정 §2 의 `CHECK_REQUIRED` 경로는 이번에 쓰이지 않았다.
