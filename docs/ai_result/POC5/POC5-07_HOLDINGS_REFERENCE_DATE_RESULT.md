# POC5-07 개발 결과서 — HOLDINGS_REFERENCE_DATE (기존 보유의 가격 비교 기준일)

작성 2026-10-11 · 갱신 2026-10-11(검증자 r1 VERIFIED · 설계자 RESULT PASS_TO_DEPLOY · 커밋 · PC 재기동 · 최종 화면 · 종료) · 작성자: 개발자(VSCode Claude) · 수신: 검증자(Codex)

```text
STATUS                 = IMPLEMENTED_VERIFIED_DEPLOYED_CLOSED — 검증자 r1 VERIFIED · 설계자 RESULT PASS_TO_DEPLOY(2026-10-11) · 구현 커밋 `89f90f0f` push(사용자 승인) · PC 재기동 · 최종 화면 사용자 확인 · 보유 파일 불변 개발자 확인 → 종료(§11 · 설계자 재판정 없음 · 설계 §10-2)
DESIGNER_RESULT        = PASS_TO_DEPLOY(2026-10-11 · OUTSIDE_CHANGES ACCEPTED(§4 4건 + 과거 화면 설명 정정) · EARLY_LIVE_SETTING ACCEPTED_KEEP_CURRENT_DATA · 647줄 한계 수용 · OCI_PULL NOT_REQUIRED · 최종 화면 통과 뒤 재판정 없이 종료 · 버튼 크기 = 후속 POC5-UI-01) — 원문 = 설계서 §10 · 끝에 전달문 원문
VERIFIER               = r1 VERIFIED(2026-10-11 · A-1 ~ A-4 통과 · B-1 ~ B-6 없음 · 위험 NONE · 범위 폭주 NONE · 검증자 격리 사본에서 관련 백엔드 280 + 독립 검증 2 · 화면 394 통과 · PROGRAM_TRUTH 과거 화면 문구 1곳은 검증자가 직접 정정 · stage)
STEP_ID                = POC5-07 기존 보유의 가격 비교 기준일
DESIGN                 = docs/ai_design/POC5/POC5-07_HOLDINGS_REFERENCE_DATE_DESIGN_V1.md (V1 · §9 PLAN 판정 PASS_TO_IMPLEMENT · 끝에 전달문 원문 2건)
PLAN                   = docs/ai_plan/POC5/POC5-07_HOLDINGS_REFERENCE_DATE_PLAN_V1.md (판정 반영 = 본문 정정 + §7)
PREDECESSOR            = POC5-06
BASE_COMMIT(코드 기준)  = ba7d55db
MOCKUP                 = 없음(설계 §7 · 판정 §9 MOCKUP_REVIEW NOT_REQUIRED — 실화면에서 확인)
API                    = 경로 추가 0 — 기존 PUT /holdings/trade-history 에 action "reference_date" · GET 응답 필드 추가(기간 reference_date · 시장 흐름 reference_*)
OCI_CODE               = OCI 실행 파일 변경 0(§6-1) → OCI pull · 첫 영업일 확인 없음
DEPENDENCY             = 신규 0
TESTS                  = 백엔드 새 1파일 11건 · vitest 새 1파일 10건 + 기존 1파일 assertion 2곳 수정 — §8
REVIEW                 = 독립 검토 1회(읽기 전용) — DEFECT 0 · CONTRACT_GAP 2 · NIT 2 · TEST_GAP 3묶음 → 모두 반영 또는 판단 기록(§6-2)
KS-10                  = 트리거 0 — app/holdings_market_flow.py 593 → 647(근접 경고 구간 · PLAN 목표 640 초과 · 분리 기준 650 미만 · §5) · app/holdings_book.py 513 → 556 · 새 모듈 160 · 시험 최대 673 · 화면 최대 HoldingsBookSection.tsx 347 → 376
BACKEND_FULL_REGRESSION= 3312 passed / 0 failed · exit 0 · 404.44s(2026-10-11 16:24:32 ~ 16:31:20 · 검토 반영 뒤 최종 코드) · PC state/logs 1,157파일 해시 동일(§8-5)
```

## 0. 요약

실제 매수일을 모르는 기존 보유(기준잔고 · 잔고 등록으로 시작한 보유 기간)에 **가격 비교 기준일**을 둔다. 실제 매수일은 계속 '미상'이다.

- **기록**: PC 보유 문서 `personal_trade_history.records` 에 새 종류 **REFERENCE_DATE** — payload `{reference_date: 날짜 | null}` 한 칸 · 기준잔고 / 잔고 등록 기간만 · 날짜 ≤ 저장 시각의 KST 날짜 · 정정 · 취소 대상 아님 · 같은 기간의 유효 값 = 저장 순서 마지막 기록(null = 해제).
- **계산 제외**: 무결성 검사는 거치되 기간 계산(replay)에 넣지 않는다 — 수량 · 평단 · 원가 · 손익 · 순서 · 기간 시작 / 종료 · `holdings` · OCI 적용 payload 가 기준일과 무관하다.
- **저장**: `PUT /holdings/trade-history` `action: "reference_date"` — 대상 1 ~ 200 · request_id 재시도 확인 → revision 확인 → 전부 판정 뒤 한 번 교체(`holdings_store.commit`) · 같은 값 / 미설정 해제 = 쓰기 0 · V1 첫 저장 = 기존 ID 그대로 V2.
- **화면**: 보유 표 [가격 비교 기준일 설정](기준일 없는 현재 기준잔고 · 잔고 등록 보유 일괄 · 초기값 2026-01-02) · History 기간 머리 '실제 매수일: 미상' · '가격 비교 기준일: 날짜/없음' · [수정/해제](같은 줄 안) · 시장 흐름 '가격 비교 기준일 이후 종가 변화' + 끝난 기간 '가격 비교 기준일 → 마지막 매도일'.

## 1. 처리한 요구사항

| 항목 | 상태 | 근거 |
|---|---|---|
| §1 · §2 일괄 설정(초기값 2026-01-02 · 사용자 실행 · 대상 = 현재 기준잔고 / 잔고 등록 · 기준일 없음 · 대상 없음 안내 · 덮어쓰기 없음) | DONE | `ReferenceDateDialog.tsx` · 대상 목록과 같은 조회의 revision(§6-2 #2) · vitest |
| §2 History 기간별 표시 · 수정 / 해제 · 종료 기간 · 재매수 새 기간 미복사 · BUY 기간 기존 표시 · 날짜 ≤ KST 오늘 · 휴장일 허용 | DONE | `ReferenceDateEditor.tsx` · `test_accounts_rebuy_buy_cycles_and_no_change` · `test_input_rules` · vitest |
| §3 한 문서 · REFERENCE_DATE · 계산 불참 · 정정 / 취소 대상 아님 · 기준잔고 / 잔고 등록 기간만 · 저장 경계 재사용 · request_id 재시도 · 한 번 저장 · V1 첫 전환 · 무결성 · 변경 없음 | DONE | `app/holdings_book.py` · `app/holdings_reference_date.py` · §8 시험 |
| §4 시장 흐름(누를 때만 · 기준일 → 마지막 저장일 · 끝난 기간 기준일 → 마지막 매도일 · 매수 / 손익 표현 없음 · 05 규칙 재사용 · 정정 종료 가상 매도일 없음) | DONE | `app/holdings_market_flow.py` · `test_market_flow_reference_items` · vitest |
| §5 OCI payload / hash / pending_apply 불변 · 원장 · 04 · 06 ML 불변 · OCI 실행 경로 | DONE | §6-1 · `test_v1_first_set_keeps_ids_calc_and_oci_payload` · `test_reads_do_not_write_and_reentry_ml_is_unchanged` |
| §6-1 ~ §6-5 확인 | DONE | §8-1 표 |
| §9-2-1 저장일 상한 = recorded_at 의 KST 날짜 · KST 자정 시험 | DONE | `holdings_book.kst_day` · `test_integrity_rules_and_kst_midnight` |
| §9-2-2 History '실제 매수일: 미상' + '가격 비교 기준일' 함께 · purchase_date_unknown 이 기준일 항목을 숨기지 않음 | DONE | `ReferenceDateEditor` · 시장 흐름 '실제 매수일: 미상' 줄 · vitest |
| §7 PC 재기동 · 실화면 | DONE | 실제 일괄 설정(2026-10-11 16:39 · §10) · PC 재기동 · 최종 화면 사용자 확인(§11) |

## 2. 변경된 파일 목록

백엔드
- `app/holdings_book.py`: 수정 — `REFERENCE` · `KINDS` · `PAYLOAD_KEYS` · `kst_day` · payload 검사 · 기준잔고 / 잔고 등록 기간 연결 검사 · `compute` 계산 제외 + 기간 `reference_date`
- `app/holdings_reference_date.py`: 신규 — 요청 검사(`normalize`) · 저장(`apply_reference_dates`)
- `app/api_holdings_history.py`: 수정 — PUT 의 action 분기 1개
- `app/holdings_history.py`: 수정 — 409 관련 기록 문구에 '가격 비교 기준일 날짜 / 해제'
- `app/holdings_history_view.py`: 수정 — 기간 보기 · 시장 흐름 입력에 `reference_date`
- `app/holdings_market_flow.py`: 수정 — 입력 검사 · `_since`(기존 `_event` 본문 분리) · `_reference_flow` · `_holding_period` 기준일 시작 · 응답 `reference_date` · `reference_flow` · `reference_note`

시험
- `tests/test_poc5_07_reference_date.py`: 신규

화면
- `frontend/lib/api/holdingsHistory.ts`: 수정 — 타입 · `putReferenceDate` · `DEFAULT_REFERENCE_DATE`
- `frontend/app/components/holdings_manage/ReferenceDateDialog.tsx`: 신규 — 일괄 설정 창 · `referenceTargets`
- `frontend/app/components/holdings_manage/ReferenceDateEditor.tsx`: 신규 — History 기간 머리 줄 · 수정 / 해제
- `frontend/app/components/holdings_manage/HistoryCycle.tsx`: 수정 — 기준일 줄 · 기준일이 있으면 [시장 흐름 보기]
- `frontend/app/components/holdings_manage/HistoryDialog.tsx`: 수정 — revision · 저장 뒤 다시 읽기 전달
- `frontend/app/components/holdings_manage/HoldingsBookSection.tsx`: 수정 — 버튼 · 창 상태 · 대상 목록과 같은 조회의 revision
- `frontend/app/components/holdings_manage/MarketFlowPanel.tsx`: 수정 — 기준일 항목 · 끝난 기간 문구 · '실제 매수일: 미상' 줄 · 안내
- `frontend/app/components/holdings_manage/ReferenceDate.test.tsx`: 신규
- `frontend/app/components/holdings_manage/referenceFixtures.ts`: 신규 — 실제 백엔드 출력(tmp 시세 DB)
- `frontend/app/components/holdings_manage/HistoryDialog.test.tsx`: 수정 — 기준잔고 · 잔고 등록 기간 '버튼 없음' 2곳을 '버튼 = [수정/해제] 하나'로(설계 §2 새 버튼 · 정정 / 취소 / 시장 흐름 없음 의도 유지)
- `frontend/app/globals.css`: 수정 — `.hmx-ref-row` 3줄

문서
- `docs/ai_design/POC5/POC5-07_..._DESIGN_V1.md`: 신규 — 설계자 원문(§9 PLAN 판정 포함) + 전달문 원문
- `docs/ai_plan/POC5/POC5-07_..._PLAN_V1.md`: 신규 — PLAN + §7 판정 반영
- `docs/ai_result/POC5/POC5-07_HOLDINGS_REFERENCE_DATE_RESULT.md`: 신규 — 이 문서
- `docs/PROGRAM_TRUTH.md`: 수정 — 최종 반영 · §5.1 · §5.2 · §6.1 · §7.2 · 부록 A(+ POC5-06 종료 때 남은 §5.1 '검증 대기' 문구 1곳 정정 · §4)
- `docs/STATE_LATEST.md`: 수정 — 현재 상태 줄 · POC5 다음 줄
- `docs/backlog/BACKLOG.md`: 수정 — §8 사용자 제안 항목에 진행 1줄

## 3. 신규 추가된 의존성

- 없음.

## 4. 지시문 외 변경

1. **기준일이 있으면 매매 없는 기간에도 [시장 흐름 보기]** — 기존 05 는 매매가 있는 기간에만 버튼을 뒀다. 지금 보유 32기간은 모두 매매 없는 기준잔고라 이대로면 설계 §4('[시장 흐름 보기]를 누를 때만 · 기준일 이후 종가 변화')를 볼 수 없어 조건에 '기준잔고 / 잔고 등록 기간 + 기준일 있음'을 더했다.
2. **`HistoryDialog.test.tsx` assertion 2곳** — 기준잔고 · 잔고 등록 기간의 '버튼 없음'을 '버튼 = [수정/해제] 하나'로(설계 §2 의 새 버튼 · 기존 의도 = 정정 / 취소 / 시장 흐름 없음 유지).
3. **`holdings_history._related_text`** — 409 문구의 관련 기록이 REFERENCE_DATE 면 '매수일 미상'이 아니라 '가격 비교 기준일 날짜 / 해제'로.
4. **PROGRAM_TRUTH §5.1 의 POC5-06 '검증 대기' 1곳** — POC5-06 종료(2026-10-10) 때 남은 문구를 '종료 2026-10-10'으로 정정(같은 패턴 grep 결과 이 1곳뿐).

## 5. 알려진 한계 / 미완성

1. **`app/holdings_market_flow.py` 647줄** — KS-10 백엔드 근접 경고(600 이상) 구간 · PLAN §2-4 목표 640 초과(7줄) · 분리 기준 650 미만이라 PLAN 대로 분리하지 않았다. 다음에 이 파일에 기능을 더하면 문구 · 상수(`REASONS` · `PERIOD_REASONS` · `NOTES` · 기준일 문구)를 먼저 분리해야 한다.
2. 실제 일괄 설정 · 최종 화면 확인 모두 완료(§10 · §11). 해제는 비교 설정만 지우는 동작이며 V1 복구가 아니다(배포 전 V1 백업 `state/holdings/backup/holdings_latest_pre_POC5-05_20261009.json` 은 그대로 둔다).
3. 화면 표시용 06 '내 거래'에는 기준일을 넣지 않았다(PLAN §2-6-5 · 판정 수용 · 06 창의 시장 흐름에는 기준일 항목이 보임).

## 6. 다음 검증자(Codex)에게 알릴 점

### 6-1. OCI 실행 경로 · 판단

- **OCI 실행 파일 변경 0**: `git diff --stat` 에 `app/holdings.py` · `app/three_push_runtime/*` · `app/runtime_evidence/*` · `scripts/run_holdings_publication.py` · `scripts/run_three_push_runtime_oci.py` 없음. `app/holdings.py` 는 이력 문서일 때만 함수 안에서 `holdings_book` 을 불러오고(`_check_history_consistency`), OCI 보유 파일은 허용 5필드 기존 형식이라 이 경로를 타지 않는다.
- **판단 1 — 요청 칸 엄격**: `reference_date` 칸이 빠진 요청을 '해제'로 받지 않고 422(해제 = null 명시) · 알 수 없는 칸도 422(독립 검토 NIT 반영).
- **판단 2 — 저장일 상한**: 무결성은 recorded_at 을 시간대 있는 시각으로 읽어 KST 날짜로 바꾼다(시간대 없으면 손상). 기존 매매 기록의 거래일 검사(`recorded_at[:10]`)는 손대지 않았다 — 지금 저장 시각은 늘 `+09:00` 이라 두 축이 같다.
- **판단 3 — 끝난 기간의 기준일 항목**: 기준일 → 마지막 저장일 항목은 끝난 기간에도 함께 보인다(PLAN §2-6-4 · 판정 수용).

### 6-2. 독립 검토(2026-10-11 · 읽기 전용 · 1회) 반영

| 지적 | 처리 |
|---|---|
| GAP 시장 흐름이 기준일 구간을 '보유 기간'이라 부르고 '매수일 미상' 문구가 사라짐(§1 · §9-1) | 정정 — 기준일 구간 문구 = '가격 비교 기준일 X → 마지막 매도일 Y 종가 변화'(보유 기간이라 부르지 않음) · 기준일 항목이 있으면 '실제 매수일: 미상 — 매수 전후 변화는 계산하지 않습니다' 줄 · vitest |
| GAP 일괄 창의 대상 목록과 revision 이 다른 조회(§9-1 '대상 목록과 revision 으로 보장') | 정정 — 대상 목록을 읽은 같은 `GET /holdings/trade-history` 의 revision 을 보낸다 · vitest(부모 revision 7 · 목록 revision 0 → 0 전송) |
| NIT `reference_date` 칸 없음 = 해제 | 정정 — 422(§6-1 판단 1) · 시험 |
| NIT `_validated` 반환 주석 · 줄 수 | 정정(주석) · 줄 수는 §5-1 |
| TEST 잔고 등록 기간 · 입력 정정 종료 기간 API | 추가 — `test_register_period_and_adjustment_closed_period` |
| TEST 저장 순서 vs 저장 시각 | 추가 — `test_last_stored_record_wins_not_latest_recorded_at` |
| TEST 일괄 안 매수 기간 422 · 외부 조회 막기 · 편집기 재시도 ID · 편집기 오늘 이후 | 추가 — 일괄 혼합 422 + 쓰기 0 · socket 연결 막기 · vitest 2건(편집기에 오늘 이후 저장 막기 추가) |

## 7. 사용자 확인이 필요한 항목

1. **실제 일괄 설정 — 완료**(2026-10-11 16:39:27 · 2026-01-02 · 32기간 · §10). 설계자가 RESULT 전 실행을 수용했고 현재 데이터를 유지한다.
2. **최종 화면 확인 — 완료**(2026-10-11 · §11).

## 8. 검증 실측 (2026-10-11)

### 8-1. 테스트

- `.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_poc5_07_reference_date.py` → `11 passed`. 관련 회귀(`tests/test_poc5_05_*.py` · `test_poc5_06_*.py` · `test_poc5_07_*.py` · `test_holdings_oci_apply.py` · `test_holdings_apply_status.py` · `test_run_holdings_publication.py`) → `280 passed`(검토 반영 뒤 최종 코드).
- 프론트: `npx vitest run` → `Test Files 32 passed (32)` · `Tests 394 passed (394)` · `npx tsc --noEmit` exit 0 · `npx eslint app lib` exit 0.

| 설계 §6 | 시험 |
|---|---|
| 1 계산 불변 | `test_v1_first_set_keeps_ids_calc_and_oci_payload`(V1 첫 전환 · ID · 계산 · payload · pending_apply False) · `test_v2_with_trades_set_change_clear_keep_calc`(매수 · 분할매도 · 전량매도 뒤 설정 → 수정 → 해제 · 종료 기간) · `test_register_period_and_adjustment_closed_period` |
| 2 일괄 원자성 | `test_bulk_is_one_write_and_retries_conflicts_leave_no_partial`(재시도 쓰기 0 · 같은 ID 다른 내용 409 · 오래된 revision 409 · 없는 기간 409 · 교체 직전 실패 = 파일 그대로 · 임시 파일 0) · 일괄 혼합 422 |
| 3 구분 | `test_accounts_rebuy_buy_cycles_and_no_change`(다른 계좌 · 재매수 미복사 · BUY 422 · 같은 값 / 미설정 해제 = 변경 없음 · 사건 / 취소 목록에 없음) |
| 4 날짜 · 표시 | `test_input_rules` · `test_market_flow_reference_items`(휴장 → 다음 거래일 · 종가 없음 · 마지막 저장일 < 기준일 · 기준일 > 매도일 · 추가매수 뒤 매도 = 기준일 시작 · 정정 종료 NO_SELL · 개별주 · 읽기 전용) · 설정 · History 열기 때 학습 · 시세 DB · 소켓 연결 0 |
| 5 06 ML 불변 | `test_reads_do_not_write_and_reentry_ml_is_unchanged`(같은 가격 자료 · 결과 · canonical hash 같음 · 문서 hash 만 다름) |
| 무결성 | `test_integrity_rules_and_kst_midnight`(칸 누락 · 추가 칸 · 잘못된 날짜 · KST 저장일 이후 · 시간대 없음 · supersedes · 다른 줄 기간 · 알 수 없는 종류 · VOID 대상 · UTC 전날 15시대 = KST 다음날 허용 · 공용 읽기 경로) · `test_reference_on_buy_started_cycle_is_corrupt` · `test_last_stored_record_wins_not_latest_recorded_at` |

### 8-2. 정적 검사

- `black --check`(변경 · 신규 Python 7파일) → `7 files would be left unchanged.` · `flake8` exit 0 · `py_compile` exit 0.

### 8-3. 변이 시험(저장소 사본)

1차 22건 — 21건 잡힘 · 1건(기간 시작 = 첫 매수 우선) 처음엔 안 잡힘(시험 자료의 끝난 기간에 매수가 없어 같은 결과) → '기준잔고 기간 추가매수 뒤 매도' 시험 추가 후 잡힘:

| 되돌린 계약 | 결과 |
|---|---|
| 계산 경로에서 기준일 미제외 | 잡힘 |
| 유효 값 = 첫 기록 | 잡힘 |
| KST 변환 없이 문자열 앞 10자 | 잡힘 |
| 기준잔고 기간 연결 검사 제거 | 잡힘 |
| payload 칸 누락 허용 | 잡힘 |
| 재시도 확인을 revision 뒤로 | 잡힘 |
| 같은 값도 기록 | 잡힘 |
| 매수 기간 허용 | 잡힘 |
| 미래 날짜 허용 | 잡힘 |
| 겹친 대상 허용 | 잡힘 |
| 매수일 미상이면 보유 기간 숨김 | 잡힘 |
| 기간 시작 = 첫 매수 우선 | 잡힘(시험 추가 뒤) |
| 기준일 항목 없음 | 잡힘 |
| History 에 기준일 없음 | 잡힘 |
| 시장 흐름 입력에 기준일 없음 | 잡힘 |
| 화면: 일괄 대상에 기준일 있는 기간 포함 | 잡힘 |
| 화면: 기준일 있어도 매매 없으면 시장 흐름 버튼 없음 | 잡힘 |
| 화면: 해제가 날짜를 보냄 | 잡힘 |
| 화면: 기준일 있으면 매수일 미상 숨김 | 잡힘 |
| 화면: 재시도마다 새 저장 ID(일괄) | 잡힘 |
| 화면: 기준일 항목 표시 안 함 | 잡힘 |

2차(검토 반영) 9건 — 모두 잡힘: 잔고 등록 기간 거절 · 저장 시각 순 유효 값 · 매수 기간은 건너뛰고 나머지 저장 · `reference_date` 칸 없어도 받음 · 화면: 기준일 구간을 보유 기간으로 · '실제 매수일: 미상' 줄 없음 · 일괄 revision = 부모 보유 · 편집기 오늘 이후 허용 · 편집기 재시도 새 ID.

### 8-4. 라이브 보유 사본 확인(읽기 전용 · 사본은 scratchpad)

- 라이브 `state/holdings/holdings_latest.json` 을 scratchpad 로 복사해 그 사본에 실행: 대상 32(모두 기준잔고 · 보유 중) → `V2` · revision 1 · changed 32 · 사본 기록 `BASELINE 32 · REFERENCE_DATE 32` · virtual 0.
- 계산(기간 ID · 상태 · 수량 · 원가 · 평단 · 손익 · 사건) 같음 · 줄 / 기간 ID 그대로 · OCI 적용 payload sha256 같음 · 같은 날짜 재설정 = changed 0 · revision 그대로.
- KODEX 200(069500) 시장 흐름: 기준일 2026-01-02(거래일 그대로 · 연도 파일) → 마지막 저장일 2026-10-08 · ETF `OK` +68.79% · KOSPI `OK` +53.75% · 보유 기간 = `CYCLE_OPEN`.
- 06 ML(069500 · 산출물 scratchpad): 설정 전후 결과 · canonical sha256 같음 · 문서 hash 만 다름 · 추정 −3.48%.
- 라이브 보유 · OCI 적용 기록 · 원장 사본 · 시세 DB sha256 전후 같음 · `state/ml/research/` 목록 전후 같음.

### 8-5. 백엔드 전체 회귀 · 라이브 보호

- `caffeinate -i .venv/bin/python -m pytest tests/ -q -p no:cacheprovider` → `3312 passed, 1 warning in 404.44s (0:06:44)` · exit 0 · 2026-10-11 16:24:32 ~ 16:31:20.
- 회귀 직전 · 직후 `state/` · `logs/` 전체 파일 sha256 비교(1,157파일 = state 1,155 + logs 2) → 바뀜 0 · 사라짐 0 · 새로 생김 0. (POC5-06 때보다 2파일 많은 것은 POC5-06 실화면 연구 산출물 `state/ml/research/poc5_06/20261010T234350_3e4a51dc/` 2파일.)
- 코드 · 시험 마지막 수정 16:23:13(회귀 시작 전) — 회귀 시작 뒤 코드 변경 0(문서만).
- 시험 수: POC5-06 종료 때 3,301 → 3,312(+11 = 이번 POC5-07 백엔드 시험).

## 9. git 상태

- 결과서 제출 직전 실측(`git status --short --untracked-files=all`): 이 단계 파일 24개가 모두 staged(오른쪽 칸 공백 · `A` 9 · `M` 15 — §2 목록과 같음) · `??` 1건 = `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md`(사용자 소유 · 이 단계와 무관 · stage 하지 않음).
- 커밋 전(설계자 RESULT 판정 · 사용자 승인 뒤 커밋 · push). 최신 커밋은 `git log` 로 실측.

## 10. 실화면 · 실제 설정 기록 (2026-10-11 · 설계자 RESULT 전)

- **순서**: 사용자가 검증자 VERIFIED 뒤 · 설계자 RESULT 판정 · 커밋 전에, 자동 반영 중인 PC 서버(작업 트리 코드)로 「종목 관리」 [가격 비교 기준일 설정] → [설정]을 실행했다(사용자 보고 "가격 비교 기준일 설정->설정 완료했습니다."). 설계 §7 · §9-3 순서(RESULT → 커밋 · push → PC 재기동 → 실화면)와 다르다 — 실제 설정 결과는 아래처럼 계약과 같다.
- **개발자 읽기 전용 확인(라이브)**: `state/holdings/holdings_latest.json` = schema 2 · revision 1 · 기록 `BASELINE 32 · REFERENCE_DATE 32`(모두 `2026-01-02` · request_id 1개 · 저장 2026-10-11T16:39:27+09:00 · 기준잔고 확정 시각 같음 · virtual 0) · `holdings` 32줄 = 배포 전 V1 백업의 5필드와 같음 · History 32기간 모두 기준일 `2026-01-02` · 실제 매수일(start_date) 0건(미상 유지) · OCI 적용 기록 `OCI_APPLIED` · 현재 payload sha256 = 마지막 적용 sha256 · `pending_apply` = False(OCI 미적용 변경 없음).
- **사용자 의견(2026-10-11)**: "화면들의 버튼 크기가 다 제각각인 것은 아쉽네요" — 이번 단계 변경 0 · 사용자 결정 = 별도 항목으로 기록(`docs/backlog/BACKLOG.md` §10 '버튼 크기 통일(전 화면)' · 실측 7가지 크기) · 설계자 결정 = 후속 **POC5-UI-01**(큰 버튼 48px 기본 · 중간 40px · 설계 §10-3) — 07 종료 조건 아님.
- **설계자 판정(§10-2)**: RESULT 전 실제 설정 수용 · 현재 V2 데이터 유지 · 회귀 시험 구간 해시 불변과 그 뒤 정상 설정 저장은 다른 시점(위반 아님). 이후 커밋 · push · PC 재기동 · 최종 화면 확인 완료 → 종료(§11).

## 11. 배포 · 종료 기록 (2026-10-11)

- **커밋 · push**: 구현 커밋 `89f90f0f`(`git show --stat`: `24 files changed, 2625 insertions(+), 45 deletions(-)`) · push `ba7d55db..89f90f0f main -> main`(사용자 승인 2026-10-11). OCI 실행 파일 변경 0 → OCI pull · 첫 영업일 확인 없음(설계 §10).
- **PC 재기동**: 백엔드 새 프로세스(시작 2026-10-11 18:41:58).
- **최종 화면(설계 §10-2)**: 사용자 확인 완료(2026-10-11) — History 기간 머리 '실제 매수일: 미상' · '가격 비교 기준일: 2026-01-02' · [수정/해제] 입력 · 취소 표시(실제 기준일 변경 없음) · 매매 없는 기간의 [시장 흐름 보기] · '가격 비교 기준일 이후 종가 변화' · 일괄 설정 창 '설정할 보유가 없습니다'.
- **부수효과(개발자 확인)**: 최종 화면 확인 전후 `state/holdings/holdings_latest.json` · `state/holdings/holdings_apply_status_latest.json` sha256 같음 · 보유 문서 revision 1 · 기록 `BASELINE 32 · REFERENCE_DATE 32` 그대로.
- **종료 조건(설계 §10-2)**: 코드 변경 없이 최종 화면 통과 → `IMPLEMENTED_VERIFIED_DEPLOYED_CLOSED`(설계자 · 검증자 재왕복 없음).
- **후속**: 버튼 크기 통일 = `POC5-UI-01`(설계 §10-3 · 큰 48px 기본 · 중간 40px · 07 종료 조건 아님) · `app/holdings_market_flow.py` 647줄 — 다음 기능 추가 때 문구 · 상수 분리 먼저.
- **인계**: `docs/handoff/POC5-07_HOLDINGS_REFERENCE_DATE_HANDOFF_2026-10-11.md`.

