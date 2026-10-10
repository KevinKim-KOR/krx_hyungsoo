# POC5-06 개발 결과서 — MANUAL_REENTRY_REVIEW_AND_ML_EVIDENCE (수동 재진입 검토 · ML 근거 · 설계 개정 2)

작성 2026-10-10 · 갱신 2026-10-10(검증자 r1 REJECTED 정정 · r2 VERIFIED · 설계자 RESULT PASS_TO_DEPLOY · 커밋 · PC 실화면 · 종료) · 작성자: 개발자(VSCode Claude) · 수신: 검증자(Codex)

```text
STATUS                 = IMPLEMENTED_VERIFIED_DEPLOYED_CLOSED — 검증자 r2 VERIFIED · 설계자 RESULT PASS_TO_DEPLOY(2026-10-10) · 구현 커밋 `21706285` push(사용자 승인) · PC 재기동 · 최종 실화면 사용자 확인 · 산출물 · 부수효과 개발자 확인 → 종료(§10 · 설계자 재판정 없음 · 설계 §11-4)
DESIGNER_RESULT        = PASS_TO_DEPLOY(2026-10-10 · IMPLEMENTATION ACCEPTED_CURRENT_SCOPE · OUTSIDE_CHANGES ACCEPTED 5 · KNOWN_LIMITATIONS ACCEPTED_CURRENT_SCOPE 6 · CODE_REWORK NOT_REQUIRED · RESULT_RESUBMIT NOT_REQUIRED · 문서 정정 = §6-1 판단 3 hash 설명 1문장(반영) · OCI_PULL NOT_REQUIRED · 실화면 통과하면 설계자 재판정 없이 종료) — 원문 = 설계서 §11 · 끝에 전달문 원문
VERIFIER               = r2 VERIFIED(2026-10-10 · A-1 ~ A-4 통과 · B-1 ~ B-6 없음 · 위험 NONE · 범위 폭주 NONE · 검증자 격리 사본에서 백엔드 관련 130 · 화면 384 통과) · r1 REJECTED(2026-10-10 · A-1 · A-3 · B-1 · 위험 MEDIUM — 손상된 원장 사본(필수 표 없음 · 결과 표 생성 기록 뒤 표 없음)을 OK 로 반환해 기존 평가 · 결과가 '평가 없음' · '집계 중'으로 보임) → 정정(§6-3) · 결과서 KS-10 테스트 최대 608 → 609 는 검증자가 직접 정정
STEP_ID                = POC5-06 수동 재진입 검토 · ML 근거(설계 개정 2)
DESIGN                 = docs/ai_design/POC5/POC5-06_MANUAL_REENTRY_REVIEW_AND_ML_EVIDENCE_DESIGN_V1.md (개정 2 · §10 PLAN 판정 PASS_TO_IMPLEMENT_WITH_CORRECTIONS · §11 RESULT 판정 PASS_TO_DEPLOY · 끝에 전달문 원문 3건)
PLAN                   = docs/ai_plan/POC5/POC5-06_MANUAL_REENTRY_REVIEW_AND_ML_EVIDENCE_PLAN_V1.md (판정 반영 = 본문 정정 + §7)
PREDECESSOR            = POC5-05
BASE_COMMIT(코드 기준)  = ae5fa38c
MOCKUP                 = 사용자 확인 완료("목업 확인했습니다. 좋습니다.") — 그 뒤 설계 대조 · 독립 검토로 화면 5곳이 바뀜(§7-1 · 실화면에서 다시 확인)
API                    = 신규 로컬 2 경로(GET /holdings/trade-history/reentry-review · POST /holdings/trade-history/reentry-review/ml) · 기존 경로 변경 0
OCI_CODE               = 변경 0(OCI 에서 도는 파일 변경 없음) → OCI pull · 첫 영업일 확인 없음(설계 §7 · §10-6)
DEPENDENCY             = 신규 0 — scikit-learn 1.9.0 · numpy 2.4.6 은 requirements.txt 기존 고정 버전
TESTS                  = 백엔드 새 2파일 43건 · vitest 새 1파일 12건 + 기존 1파일 수정 — §8
REVIEW                 = 독립 검토 1회(읽기 전용) — DEFECT 1 · CONTRACT_GAP 4 · NIT 5 · TEST_GAP 5 → 모두 반영 또는 판단 기록(§6-2)
KS-10                  = 트리거 0 — 백엔드 최대 app/holdings_market_flow.py 593(591 → 593) · 새 패키지 최대 app/reentry_review/review.py 411 · 테스트 최대 685(tests/test_poc5_06_reentry_review.py · r1 정정 뒤) · 프론트 최대 HoldingsManageView.tsx 762(761 → 762) · 새 컴포넌트 최대 229
BACKEND_FULL_REGRESSION= 3301 passed / 0 failed · exit 0 · 406.27s(2026-10-10 22:04:05 ~ 22:10:55 · r1 정정 뒤 최종 백엔드 코드) · PC state/logs 1,155파일 해시 동일(§8-5)
```

## 0. 요약

「종목 관리」 [History] 의 보유 기간마다 [재진입 검토] 버튼을 두고, 누르면 재진입 검토 창이 History 창 자리를 대신 연다(창 하나 · '← History' 로 복귀).

- **열 때(GET · 읽기 전용)**: 학습 · 외부 조회 · 쓰기 0 · scikit-learn import 0. 세 부분 —
  1. 내 거래: 선택 · 이전 기간 · 마지막 실제 매도일(입력 정정 종료일은 매도일이 아님) · 매수일 미상 안내.
  2. 저장된 근거: 기준일 저장 종가의 feature 다섯 값 · 05 시장 흐름 · PC 원장 사본의 같은 종목 알림(관측만 된 알림은 건수 + 펼치기) · '연관 근거'(사업군 대표 · 기초지수 묶음 구성) · 이동 링크(자동 실행 없음).
  3. ML 검토: [ML 검토 실행] 버튼만.
- **누를 때(POST)**: 선택 ETF 하나로 D20('이후 20거래일 최저 종가 변화(연구 추정)')을 StandardScaler → Ridge 로 한 번 학습. 3구간 검증 · 학습 중앙값 기준과 MAE %p 비교 · 연구 산출물 `state/ml/research/poc5_06/<생성시각>_<id>/review.json · input_snapshot.json`.
- **읽기 기준**: 보유 문서는 한 번 읽은 문서 · 시세 DB 는 `mode=ro` 읽기 트랜잭션 1개(05 시장 흐름과 공유) · 원장 사본은 `mode=ro` 읽기 트랜잭션 1개.
- **기반 문서**: 설계자 §10-1 확정문을 PROJECT_ORIGIN_INTENT §9.5 · ASSUMPTIONS Q6 · POC5-00 설계 · PLAN · STATE 에 날짜 붙여 덧붙였다(원래 문장 보존).

## 1. 처리한 요구사항

| 항목 | 상태 | 근거 |
|---|---|---|
| §10-1 Q-A 기반 문서 한정 예외 | DONE | 확정문 그대로 · 원래 문장 보존 · Q6 해결 표시 없음 · POC4-03 재개 트리거 충족 주장 없음(PLAN §7) |
| §7 선택 실행 | DONE | GET 은 sklearn 미import(별도 프로세스 시험) · 산출물 0 · 보유 · 시세 · 원장 hash 불변 · POST 는 서버 문서의 ticker 하나만 |
| §7 거래 경계 | DONE | 계좌 · 기간 분리 · 매수일 미상 안내 · 입력 정정 종료 = 실제 매도일만(`test_closed_by_adjustment_keeps_real_sell_only`) |
| §7 목표 계산 | DONE | 알려진 경로 D20 · 전부 상승 0 · +20 경계 · 축 · 누락 · 경계 제외(`tests/test_poc5_06_reentry_model.py`) |
| §7 누수 차단 | DONE | 구간 b 시작 뒤 가격을 바꿔도 구간 1..b 의 학습 입력 · 정답 전부 불변(세 구간 모두) · 표준화 fit 크기 = 학습 표본 수 |
| §7 학습 · 비교 | DONE | 학습 구간만 표준화 · 고정 Ridge · [-1, 0] 제한(직접 시험) · 학습 중앙값 기준 · 같은 유효 날짜 · 유효 날짜 수가 다른 구간에서도 전체 = 표본별 평균 |
| §7 부족 · 장애 | DONE | DATA_SHORT · NOT_ETF · NO_PRICE(시세 없음 · ETF 목록 없음) · PRICE_BASIS_UNCONFIRMED · AXIS_UNCERTAIN · 늦은 기준일 · 시세 DB 오류(500) · 원장 NO_COPY · READ_FAILED(읽기 실패 · 사본 손상 = 04 판정과 같은 규칙 6경로 + 연결 값 해석 불가) · 정상 '성숙 전' · '동기화 전' · 저장 실패(500 · 반쪽 폴더 없음) 각각 시험 |
| §7 평가 선택 | DONE | 피드백 추가 전후 ML 결과 · hash 동일 · 산출물에는 event_id · feedback_seq · helpfulness 만 |
| §7 부수효과 | DONE | 시험 자료 = tmp · 라이브 확인은 읽기 전용 + 산출물 tmp(§8-4) · 전체 회귀 전후 라이브 해시 동일(§8-5) |
| §10-2 Q-B 연구 축 | DONE | 파일 있는 해 = 파일(KOSPI 누락일 무관) · 없는 해 = 평일 ∩ KOSPI 저장일 · KOSPI 최신일 < t → AXIS_UNCERTAIN · 축 날짜 · 연도별 방식 · 건너뛴 평일이 hash · snapshot 에 · 축 표기가 결과 · 입력 snapshot 모두에 |
| §10-3 Q-C 가격 경계 | DONE | 라벨만 바뀐 연속 창 사용 · 절대 1e-6 · FDR→NAVER_FDR 재전환 · change 누락 · 기준일 feature 창이 깨지면(축 공백 포함) PRICE_BASIS_UNCONFIRMED · 부분 검사 안내 |
| §10-4 Q-D 원장 연결 | DONE | SUBJECT · SECTOR_REPRESENTATIVE · INDEX_GROUP_MEMBER · 결과는 그 종목 series 만 · 알림 수 = event 수(item 여러 개는 '항목 N개') · values_json · 손익률 미반환 |
| §10-5 기본값 | DONE | 한 번 읽은 보유 문서 + 05 adapter · revision + 문서 hash 표시 · 평가 = 알림 전체 · 메모는 화면만 · hash 에 fetched_at 포함(결정성 · 추정값 불변 따로 시험) · AXIS_UNCERTAIN '이른 경우' |
| §10-6 시험 추가 | DONE | 위 항목 + 모델 · 기준을 다른 날짜로 비교하는 변이 잡힘(§8-3) |
| §2 화면 · 문구 | DONE | '저장 종가 YYYY-MM-DD 기준' · 늦으면 '이 날짜 기준 검토'(창 위 + 추정값 옆) · 열위 문구 · 매수/매도 지시 아님 · 신뢰구간 · 확률 없음 · [재매수(매매 창)] = 05 창(ML 연결 없음) |
| §6 산출물 | DONE | 새 폴더 · 두 파일 · canonical sha256 · 라이브러리 버전 · pickle 없음 · 임시 폴더에 다 쓴 뒤 이름 바꿈 |
| §7 PC 재기동 · 실화면(현재 보유 ETF 하나) | DONE | 2026-10-10 PC 재기동 · KODEX 200(069500) 실화면 사용자 확인 · 산출물 · 부수효과 개발자 확인(§10) |

## 2. 변경된 파일 목록

백엔드
- `app/reentry_review/__init__.py`: 신규 — 패키지 설명
- `app/reentry_review/models.py`: 신규 — 상태 · 문구 · 연결 종류 · 이동 링크
- `app/reentry_review/prices.py`: 신규 — 전체 종가 reader(mode=ro) · 연구 축 · 축 문제 · 경계 · `AxisSeries` · canonical hash
- `app/reentry_review/model.py`: 신규 — D20 · feature 5 · 기준일 창 판정 · 3구간 검증 · 최종 추정(sklearn 은 함수 안에서만)
- `app/reentry_review/ledger.py`: 신규 — 원장 사본 연결(mode=ro) · 사본 손상 판정(`copy_problems` · 04 `REQUIRED_TABLES` 재사용) · 산출물용 식별자
- `app/reentry_review/review.py`: 신규 — 검토 창 조립 · ML 실행 · 산출물 쓰기
- `app/api_holdings_history.py`: 수정 — 경로 2개 추가
- `app/holdings_history_view.py`: 수정 — `history_of(state, …)` · `market_flow_input_of(doc, …)` adapter(기존 함수는 이를 부름)
- `app/holdings_market_flow.py`: 수정 — `build_market_flow(…, connection=None)`(주어진 연결을 쓰고 닫지 않음)

시험
- `tests/test_poc5_06_reentry_model.py`: 신규
- `tests/test_poc5_06_reentry_review.py`: 신규

화면
- `frontend/lib/api/reentryReview.ts`: 신규 — 타입 · `fetchReentryReview` · `runReentryMl`(60초)
- `frontend/lib/api/index.ts`: 수정 — export 1줄
- `frontend/app/components/holdings_manage/ReentryReviewDialog.tsx`: 신규 — 창 · 내 거래 · 아래 줄(읽은 기준 · 매매 창)
- `frontend/app/components/holdings_manage/ReentryEvidence.tsx`: 신규 — 저장된 근거
- `frontend/app/components/holdings_manage/ReentryMlPanel.tsx`: 신규 — ML 검토
- `frontend/app/components/holdings_manage/ReentryReviewDialog.test.tsx`: 신규
- `frontend/app/components/holdings_manage/reentryFixtures.ts`: 신규 — 실제 백엔드 출력(tmp 자료 · 최종 코드로 다시 생성)
- `frontend/app/components/holdings_manage/HistoryCycle.tsx`: 수정 — [재진입 검토](매매 유무 무관)
- `frontend/app/components/holdings_manage/HistoryDialog.tsx`: 수정 — `onReview` 전달
- `frontend/app/components/holdings_manage/HoldingsBookSection.tsx`: 수정 — 창 상태 `review` · 돌아가기 · 매매 창 연결 · `onNavigate`
- `frontend/app/components/HoldingsManageView.tsx`: 수정 — `onNavigate` 전달 1줄
- `frontend/app/components/holdings_manage/MarketFlowPanel.tsx`: 수정 — 표시부 `MarketFlowView` 분리 export · 아래 문구
- `frontend/app/components/holdings_manage/MarketFlowPanel.test.tsx`: 수정 — 아래 문구
- `frontend/app/components/alert_records/format.ts`: 수정 — `outcomeCell` 인자 타입 넓힘(동작 불변)
- `frontend/app/globals.css`: 수정 — `.hmx-rv-*` · `.hmx-tag-acc` · 720px

문서
- `docs/ai_design/POC5/POC5-06_..._DESIGN_V1.md`: 신규 — 설계자 원문(1~287행 = 개정 2 그대로) + 전달문 원문
- `docs/ai_plan/POC5/POC5-06_..._PLAN_V1.md`: 신규 — PLAN + §7 판정 반영
- `docs/ai_result/POC5/POC5-06_MANUAL_REENTRY_REVIEW_AND_ML_EVIDENCE_RESULT.md`: 신규 — 이 문서
- `docs/PROJECT_ORIGIN_INTENT.md` · `docs/ASSUMPTIONS.md` · `docs/ai_design/POC5/POC5-00_..._DESIGN_V1.md` · `docs/ai_plan/POC5/POC5-00_..._PLAN_V1.md`: 수정 — §10-1 확정문 덧붙임(추가만)
- `docs/STATE_LATEST.md`: 수정 — 현재 상태 줄 · POC5 다음 줄 · §10-1 예외(POC5 · POC4 · 옛 불변 원칙)
- `docs/PROGRAM_TRUTH.md`: 수정 — 최종 반영 · §5.1 · §5.2 · §6.1 · §7.2 · §11 · 부록 A

## 3. 신규 추가된 의존성

- 없음(scikit-learn · numpy 는 기존 `requirements.txt` 고정 버전 · 설치 · 버전 변경 없음).

## 4. 지시문 외 변경

1. **05 코드 3곳(adapter)** — PLAN §2-1 머리의 '05 코드 변경 0' 과 다르다. 판정 §10-5('기존 함수가 파일을 다시 읽는다면 읽은 문서를 받는 작은 경계/adapter로 재사용' · '05 `_event`를 쓸 때도 같은 읽기 snapshot')를 지키려고 넣었다. `history_of` · `market_flow_input_of` 는 기존 `history` · `market_flow_input` 의 본문을 옮긴 것이고 기존 함수는 이를 부른다. `build_market_flow` 는 `connection` 이 없으면 기존과 같다. 05 시험 포함 전체 회귀 통과(§8-5).
2. **03 화면 `alert_records/format.ts`** — `outcomeCell` 인자 타입을 `Pick<LedgerOutcomeRow, "status" | "return_raw"> | undefined` 로 넓혔다(같은 표시 함수를 재사용하려고 · 동작 · 03 시험 불변).
3. **05 화면 문구** — [시장 흐름 보기] 아래 문구를 '재진입 판단을 돕는 근거 · ML 연구 추정은 이 기간의 [재진입 검토]에서 봅니다.' 로 바꿨다(설계 §2 의 ML 위치 안내 · 05 시험 문구 함께 수정).
4. **`MarketFlowPanel.tsx` 표시부 분리** — 검토 창에서 같은 표시를 쓰려고 `MarketFlowView` 를 export(기존 패널 동작 불변).
5. **`globals.css`** — `.hmx-rv-*`(검토 창) · `.hmx-tag-acc`(노출 분류 태그) 추가.

## 5. 알려진 한계 / 미완성

1. **PC 시세 최신성(실측 2026-10-10)** — 처음 확인 때 저장 종가 최신 2026-10-02 · 기대 완료일 2026-10-08 = 3거래일 늦음(10-06 · 07 · 08 없음 · 10-05 는 2026 거래일 파일상 휴장). 그 뒤 PC 수동 갱신(저장 `fetched_at` 2026-10-10T09:55:40Z = 18:55 KST)으로 최신 2026-10-08 = 기대 완료일 · 지금 지연 없음. OCI 운영과는 무관한 PC 수동 갱신 자료이며, 늦을 때 화면은 계약대로 '이 날짜 기준 검토'를 표시한다(늦은 경우 · 갱신 뒤 경우 모두 §8-4 에 실측).
2. **PC 원장 사본이 1일치** — 마지막 동기화 2026-10-08 10:15 · 069500 은 관측만 된 알림 2건 · 가격 결과 아직 없음(02 첫 결과 행 = 2026-10-12 예정).
3. **가격 경계 검사는 부분적** — change 가 없는 NAVER_FDR 구간은 계단을 감지할 수 없다(화면 · review 에 안내 · 설계 §10-3 수용 한계).
4. **연구 축은 근사** — 파일 없는 해는 KOSPI 저장일로 보정(069500: 2014 ~ 2025 보정 · 2026 파일 · 건너뛴 평일 167일). 건너뛴 평일이 모두 휴장은 아니다.
5. **시세 DB 읽기 실패는 창 전체 500** — 내 거래 · 원장 근거도 그 창에서는 안 보인다('← History' 로 History 는 볼 수 있음 · §6-1 판단 4).
6. **실화면 미확인** — 설계자 RESULT 뒤 PC 재기동 · 실화면(현재 보유 ETF 하나).

## 6. 다음 검증자(Codex)에게 알릴 점

### 6-1. 판단이 어려웠던 부분

1. **자료 부족이면 추정값을 보이지 않는다** — 설계 §5-2 는 '어느 구간이 비면 DATA_SHORT' 까지 정하고 최종 추정 표시는 정하지 않았다. 불완전 검증 옆에 추정값을 두면 검증된 값처럼 읽힐 수 있어 보수적으로 숨겼다(구간 표 · 사유는 보임). 실데이터 29종목 중 16종목이 이 상태(§8-4).
2. **판정 비교 = 화면 소수 2자리(%p)** — 화면 숫자가 같은데 '개선/악화'로 갈리지 않게 반올림 값으로 비교한다(`model.verdict` · 시험 있음).
3. **문서 hash = 읽은 문서의 정렬 JSON sha256** — PLAN §2-3 은 'v1 이면 0 + 파일 sha256', 판정 §10-5 는 '문서 hash'. 05 저장 경계(`read_document`)는 원문 바이트 hash 를 돌려주지 않아 파일을 다시 읽어야 하므로(다른 내용을 읽을 수 있음) 한 번 읽은 문서의 canonical hash 를 쓴다. 문서 hash는 한 번 읽은 문서의 canonical JSON 내용을 식별한다. 공백·키 순서 등 바이트만 달라지고 해석된 내용이 같으면 문서 hash는 같을 수 있다. V1 줄 ID의 원본 바이트 기반 생성과 이 내용 hash는 역할이 다르다(설계자 RESULT §11-1 정정문). 창 아래 줄에 앞 12자리 표시.
4. **PLAN 상태 READ_FAILED(시세 DB) · SAVE_FAILED 는 상태값이 아니라 HTTP 500 + 문구** — '시세 DB 조회 실패: …' · '연구 산출물 저장 실패: … — 결과를 보이지 않습니다.'(구분 · 정상 완료로 안 보임 계약 충족). 원장 사본은 읽기 실패 · 손상 모두 상태값 READ_FAILED(문구로 구분 · 근거 0행 · 다른 근거와 ML 은 그대로 · 산출물에 원장 상태 · 문구 기록).
5. **기준일 feature 창 판정** — 축 날짜 61일 미만 = DATA_SHORT · 그 밖(축 공백 · 무효 종가 · 허용 밖 출처 · 감지된 경계) = PRICE_BASIS_UNCONFIRMED 이고 사유를 모두 적는다(독립 검토 지적 반영 · 설계 §4 · §10-3).
6. **etf_master 표가 없으면 NO_PRICE('ETF 여부 확인 불가')** — 개별주(NOT_ETF)와 구분.

### 6-2. 독립 검토(2026-10-10 · 읽기 전용 · 1회) 반영

| 지적 | 처리 |
|---|---|
| DEFECT 가격 의미 문구 '배당을 반영하지 않은'(설계 §4 '분배금 미반영'으로 바꾸지 않음) | 정정 — '수수료 · 세금을 반영하지 않은 저장 종가 변화 · 가격 의미 = 저장 종가(네이버 계열 · 분배락 조정 흔적 · 총수익 여부 미확정)' · 시험 |
| GAP 늦은 기준일 표시가 추정값 옆에 없음(§2) | 정정 — 추정값 칸에 '이 날짜 기준 검토' 태그(POST 응답 기준) · 시험 |
| GAP 기준일 창의 축 공백이 DATA_SHORT(§4 · §10-3) | 정정 — §6-1 판단 5 · 사유 전부 · 시험 |
| GAP item 수를 알림 수로 셈(§10-4) | 정정 — 알림 = event 수 · 다르면 '(항목 N개)' · 시험 |
| GAP V1 문서 hash 미표시(§10-5) | 정정 — 아래 줄 'revision · 문서 hash' · §6-1 판단 3 · 시험 |
| NIT 입력 snapshot 에 축 표기 없음(§4) | 정정 — `axis_label` · `axis_limit_note` · `price_basis_label` · 시험 |
| NIT 저장 실패 때 review.json 만 있는 폴더가 남음 | 정정 — 임시 폴더에 다 쓴 뒤 이름 바꿈 · 실패하면 이 호출이 만든 임시 폴더만 지움 · 시험 |
| NIT 화면 문구에 내부 코드(BASIS_BREAK) | 정정 — 한국어 사유 · 시험 |
| NIT etf_master 없음이 NOT_ETF | 정정 — NO_PRICE · 시험 |
| NIT 계약 버전 미표시 · 평가가 마지막 열(§3 '먼저') | 정정 — 알림 칸에 계약 버전 · 평가 열을 알림 바로 다음 · 시험 |
| NIT READ_FAILED · SAVE_FAILED 가 500 | 유지 — §6-1 판단 4 |
| TEST 유효 날짜 수가 다른 구간 · 예측 제한 · 세 구간 누수 · API 상태 경로 · 시험 이름 | 추가 — 각 시험 · 변이로 확인(§8-3) · 이름 `test_v1_ids_kept_by_first_save_and_unknown_ids_get_404` 로 정정(첫 저장은 V1 ID 를 그대로 확정) |

같은 검토 중 개발자가 설계 대조로 찾아 먼저 고친 것 2건: 평가 칸에 **메모** 표시(설계 §3 · PLAN §2-3 '메모는 화면에만') · 같은 종목의 **관측만 된 알림은 건수 + 펼치기**(PLAN §2-3 · 판정 §10-5).

### 6-3. 검증자 r1 REJECTED(2026-10-10) 정정

- **지적**: 06 원장 reader 가 필수 표를 `evaluation_run` · `signal_item` 만 확인 → `ledger_meta` · `user_feedback` · `ledger_sync_attempt` 가 없거나, 결과 표를 만든 기록(`schema_version.price_outcome`)이 있는데 `price_outcome` 이 없어도 OK · 기존 평가 = '평가 없음' · 기존 결과 = '집계 중'.
- **정정**(`app/reentry_review/ledger.py`): 손상 판정을 04 `ledger_reports.source.load_snapshot` 의 problems 와 같은 규칙으로 맞췄다(03 동기화의 손상 정의와도 같음) — 필수 6표(`REQUIRED_TABLES` 를 import 해 재사용) 중 하나라도 없거나 · 결과 표를 만든 기록 뒤 `price_outcome` 이 없으면 `READ_FAILED` · '원장 사본 손상 — <사유>' · `problems` · 근거 0행. 표가 있는 척하는 조건 분기(`user_feedback` · `ledger_sync_attempt` 없으면 0건 · 시각 없음)를 없앴다.
- **같은 부류 점검**(06 이 사본에서 읽는 것 전부): 파일 없음 = NO_COPY · SQLite 아님 · 열 없음 = SQL 오류 → READ_FAILED(읽기 실패) · 표 없음 = 위 손상 · 결과 표를 만든 기록 없이 `price_outcome` 없음 = 정상(성숙 전 · 시험) · 성공 동기화 기록 0 = 정상(시각 없음 · 시험) · **이 종목을 담은 후보 행의 `values_json` 을 해석할 수 없으면 연결을 0건으로 숨기던 것도 손상으로 바꿨다**(시험). 행 값 형식 · 관계는 03 동기화가 반영 전에 검증한다(형식 · NOT NULL · FINALIZED 관계).
- **소급 확인**: 라이브 원장 사본(읽기 전용)은 069500 · 005930 · 229200 모두 `OK`(마지막 동기화 2026-10-08 10:15:49) — 정상 사본을 손상으로 잘못 판정하지 않는다. 보유 29종목 전부는 §8-4.
- **시험**: `test_damaged_copy_is_not_read_as_empty`(6경로 — 표 5개 각각 없음 · 결과 표 생성 기록 뒤 표 없음 · ML 은 계속 OK · 산출물에 원장 상태 · 문구) · `test_unreadable_link_values_are_damage_not_zero_alerts` · `test_copy_before_outcome_table_and_before_sync_is_normal`. 변이 §8-3 3차.

## 7. 사용자 확인이 필요한 항목

1. **목업 뒤 화면 변경 5곳**(설계 대조 · 검토 반영 — 목업 확인은 이 부분에 대해 무효 · 실화면에서 확인):
   - 알림 표: '내 평가(알림 전체)' 열이 알림 바로 다음(목업은 마지막) · 평가에 메모 표시 · 알림 칸에 계약 버전.
   - 같은 종목의 관측만 된 알림 = '관측만 된 알림(본문에 안 실림) N건' 펼치기(목업은 표 안).
   - 추정값 칸에 '이 날짜 기준 검토' 태그(목업은 창 위에만).
   - 창 아래 줄에 '문서 hash 앞 12자리'.
   - 알림 수 = 알림(event) 기준 · item 이 여럿이면 '(항목 N개)'.
2. **PC 시세** — 2026-10-10 18:55 KST 갱신으로 지금 최신(2026-10-08 · §5-1). 실화면 날 다시 늦으면 갱신은 선택(누르지 않아도 그 저장일 기준으로 동작).
3. **실화면은 현재 보유 ETF 하나**(설계 §10-6) — 과거 보유 · 매도 후 변화는 시험 자료로만 확인.

## 8. 검증 실측 (2026-10-10)

### 8-1. 테스트

- `.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_poc5_06_reentry_model.py` → `17 passed` · `tests/test_poc5_06_reentry_review.py` → `26 passed`(r1 정정 뒤 · 합 43).
- 프론트: `npx vitest run` → `Test Files 31 passed (31)` · `Tests 384 passed (384)` · `npx tsc --noEmit` exit 0 · `npx eslint app lib` exit 0.

### 8-2. 정적 검사

- `black --check`(변경 · 신규 Python 11파일) → `11 files would be left unchanged.` · `flake8` exit 0 · `py_compile` exit 0.

### 8-3. 변이 시험(저장소 사본 · 핵심 계약을 되돌리면 시험이 실패하는지)

1차(구현 직후) 21건 — 모두 실패로 잡힘:

| 되돌린 계약 | 결과 |
|---|---|
| 학습 표본 = 평가 끝 대신 시작일 기준(누수) | 잡힘 |
| 표준화를 검증 표본까지 fit | 잡힘 |
| 허용 오차 1e-6 → 1e-2 | 잡힘 |
| 판정 반올림 제거 | 잡힘 |
| AXIS_UNCERTAIN 검사 제거 | 잡힘 |
| 기준일 창 깨져도 추정 | 잡힘 |
| GET 에서 sklearn import | 잡힘 |
| 저장 실패를 삼킴 | 잡힘 |
| 산출물에 메모 복사 | 잡힘 |
| 다른 series 결과까지 붙임 | 잡힘 |
| values_json 반환 | 잡힘 |
| hash 에서 fetched_at 제외 | 잡힘 |
| 정정 종료일을 매도일로 | 잡힘 |
| 화면: 창 열 때 ML 자동 실행 | 잡힘 |
| 화면: 실패 때 직전 결과 남김 | 잡힘 |
| 화면: 열위 경고 표시 제거 | 잡힘 |
| 화면: 상태와 무관하게 추정 표시 | 잡힘 |
| 화면: 메모 숨김 | 잡힘 |
| 화면: '← History' 가 창 닫기 | 잡힘 |
| 화면: 매매 없는 기간에 검토 버튼 숨김 | 잡힘 |
| 화면: 검토 창을 History 위에 겹침 | 잡힘 |

2차(검토 반영 뒤) 16건 — 15건 잡힘 · 1건(기준 오차를 `ys` 의 유효 날짜로 거르기)은 원래 코드와 같은 집합이라 의미 없는 변이 → 기준 오차를 학습 날짜로 바꾼 변이로 대체해 잡힘:

| 되돌린 계약 | 결과 |
|---|---|
| 기준일 창 축 공백 = 자료 부족 | 잡힘 |
| 사유 하나만 표시 | 잡힘 |
| 전체 MAE = 구간 평균의 평균 | 잡힘 |
| 기준 오차를 다른 날짜(학습 날짜)로 | 잡힘(2건) |
| 예측 [-1, 0] 제한 제거 | 잡힘 |
| 구간 3 학습에 누수 | 잡힘 |
| 반쪽 산출물 폴더 남김 | 잡힘 |
| etf_master 없음 = 개별주 | 잡힘 |
| snapshot 축 표기 제거 | 잡힘 |
| 늦은 가격 표시 끔 | 잡힘 |
| '배당' 문구 복귀 | 잡힘 |
| 화면: 추정값 옆 날짜 기준 표시 제거 | 잡힘 |
| 화면: 알림 건수 = item 수 | 잡힘 |
| 화면: 평가 열을 끝으로 | 잡힘 |
| 화면: 문서 hash 표시 제거 | 잡힘 |

3차(검증자 r1 정정 뒤) 6건 — 모두 잡힘:

| 되돌린 계약 | 결과 |
|---|---|
| 필수 6표 검사 제거 | 잡힘(5건) |
| 결과 표 생성 기록 뒤 표 없음 검사 제거 | 잡힘 |
| 결과 표 없음을 늘 손상으로(성숙 전도 손상) | 잡힘 |
| values_json 해석 불가 = 연결 없음 | 잡힘 |
| 손상이어도 근거 반환 | 잡힘(6건) |
| 산출물에 원장 상태 문구 빠짐 | 잡힘(6건) |

### 8-4. 라이브 읽기 전용 확인(r1 정정 뒤 최종 코드 · 산출물은 scratchpad 로 돌림 · 2026-10-10 PC 시세 갱신 뒤)

- 보유 V1 · 32줄 · 종목 29. 줄마다 GET 1회 → 원장 `OK` 32(손상 오판 0). 종목마다 POST 1회 → `OK 10`(`IMPROVED 7` · `WORSE 3`) · `DATA_SHORT 16` · `NOT_ETF 3`.
- 069500: GET 0.372초 · 가격 `OK` · t 2026-10-08 = 기대 완료일(지연 없음) · 원장 `OK`(SUBJECT 관측 2). POST 1.23초 · `OK` · 학습 표본 2,904(제외 `BASIS_BREAK` 80) · 구간(학습 / 유효 검증) 2,775 / 63 · 2,838 / 11 · 2,869 / 35 · MAE 모델 4.37 / 기준 4.36 %p → `WORSE`('단순 기준보다 검증 오차 큼') · 추정 −3.48% · 기준 −2.02% · 최종 학습 2,904(2014-07-10 ~ 2026-09-07) · 축 3,064일(2014 ~ 2025 KOSPI 보정 · 2026 파일 · 건너뛴 평일 167일).
- 시세 갱신 전 같은 확인(검토 반영 뒤 코드 · 2026-10-10 17시대): t 2026-10-02 · 기대 완료일 2026-10-08 → GET · POST 모두 `stale` · '이 날짜 기준 검토' · 069500 POST `OK` · MAE 4.37 / 4.33 `WORSE` · 추정 −2.58% — 늦은 자료에서도 그 저장일 기준 연구가 계약대로 동작함을 실자료로 확인.
- 라이브 `state/holdings/holdings_latest.json` · `state/decision/decision_evidence.sqlite` · `state/market/market_data.sqlite` sha256 전후 동일 · `state/ml/research/` 목록 전후 동일 · scratchpad 산출물 29폴더 · 임시 폴더 0.
- 설계 §10-3 의 시제품 수치(−1.75% · 6.11/6.65)는 경계 없는 시제품 값이며 위가 확정 규칙의 실제 계산 값이다.

### 8-5. 백엔드 전체 회귀 · 라이브 보호

- `caffeinate -i .venv/bin/python -m pytest tests/ -q -p no:cacheprovider` → `3301 passed, 1 warning in 406.27s (0:06:46)` · exit 0 · 2026-10-10 22:04:05 ~ 22:10:55(r1 정정 뒤 최종 코드).
- 회귀 직전 · 직후 `state/` · `logs/` 전체 파일 sha256 비교(같은 범위 · 1,155파일 = state 1,153 + logs 2) → 바뀜 0 · 사라짐 0 · 새로 생김 0.
- 백엔드 코드 마지막 수정 22:03:22(회귀 시작 전) · 화면 타입 22:04:02(백엔드 회귀와 무관 · vitest · tsc 는 §8-1). 회귀 시작 뒤 바뀐 것은 시험 1파일의 주석 · 줄바꿈(black 맞춤 · 22:04:43)뿐 → POC5-06 두 파일 다시 실행 `43 passed`.
- 시험 수 변화: 검토 반영 전 3,284 → 검토 반영 뒤 3,293(+9) → r1 정정 뒤 3,301(+8 = 손상 6경로 · 연결 값 해석 불가 · 정상 성숙 전 · 동기화 전). 세 번 모두 라이브 해시 동일.

## 9. git 상태

- r1 정정 결과서 제출 직전 실측(`git status --short --untracked-files=all`): 이 단계 파일 35개가 모두 staged(오른쪽 칸 공백 · `A` 17 · `M` 18 — §2 목록과 같음) · `??` 1건 = `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md`(사용자 소유 · 이 단계와 무관 · stage 하지 않음).
- 커밋 전(설계자 RESULT 판정 · 사용자 승인 뒤 커밋 · push). 최신 커밋은 `git log` 로 실측.

## 10. 배포 · 종료 기록 (2026-10-10)

- **커밋 · push**: 구현 커밋 `21706285`(`git show --stat`: `35 files changed, 5199 insertions(+), 48 deletions(-)`) · push `ae5fa38c..21706285 main -> main`(사용자 승인 2026-10-10). OCI 에서 도는 파일 변경 0 → OCI pull · 첫 영업일 확인 없음(설계 §11-4).
- **PC 재기동**: 백엔드 · 화면 dev 서버 새 프로세스(백엔드 시작 2026-10-10 23:42:34). 재기동 전에도 자동 반영 서버가 새 경로를 응답함을 읽기 전용 GET 으로 확인(KODEX 200 · 가격 2026-10-08 · 원장 OK · revision 0 · 문서 hash `b8643c0d044f`).
- **최종 실화면(설계 §11-3)**: 사용자 확인 완료(2026-10-10 · KODEX 200(069500) · History → [재진입 검토] → 수동 ML 실행 → History 복귀 · 화면 배치 · 가독성 · 버튼 동작). §7-1 변경 5곳 중 실자료로 보이지 않는 '이 날짜 기준 검토'(가격 최신) · '항목 N개'(다중 item 없음) · 메모(평가 없음)는 화면 시험 근거(설계 §11-3 — 실제 평가 · 거래 · 시세를 바꾸지 않음).
- **산출물(개발자 확인)**: `state/ml/research/poc5_06/20261010T234350_3e4a51dc/`(gitignore) — `review.json` · `input_snapshot.json` 두 파일 · 임시 폴더 0 · 069500 · 일반 계좌 · `OK` · t 2026-10-08 · 지연 없음 · 학습 표본 2,904(제외 `BASIS_BREAK` 80) · 구간 2,775 / 63 · 2,838 / 11 · 2,869 / 35 · MAE 4.37 / 4.36 %p `WORSE` · 추정 −3.48% · 기준 −2.02% · 읽은 기준 V1 · revision 0 · 문서 hash `b8643c0d044f` · 원장 동기화 2026-10-08 10:15:49 · scikit-learn 1.9.0 · numpy 2.4.6 · 1.562초 · 입력 가격 3,065행 · 축 표기 · 원장 OK 2건 · 산출물에 `values_json` · `profit_loss_pct` · 메모 없음.
- **부수효과(개발자 확인)**: 실화면 전후 `state/holdings/holdings_latest.json` · `state/holdings/holdings_apply_status_latest.json`(OCI 적용 기록) · `state/decision/decision_evidence.sqlite`(원장 사본) · `state/market/market_data.sqlite` sha256 4개 모두 같음.
- **종료 조건(설계 §11-4)**: PC 재기동 · §11-3 확인 통과 → `IMPLEMENTED_VERIFIED_DEPLOYED_CLOSED`. 모델 MAE 우위 · 새 거래 · 원장 동기화 · +20 성숙 · 시세 갱신은 종료 조건이 아니다.
- **종료 뒤 사용자 제안(2026-10-10 · 다음 설계 후보 · 이번 단계 변경 0)**: "지금 보유하고 있는 종목들의 최초 거래일시를 모르니 2026-01-02로 해두면 어떨까" — 현재 기준잔고(BASELINE) · 잔고 등록(REGISTER) 기록은 수량 · 평단 두 칸뿐이라 날짜를 넣을 자리가 없다(`app/holdings_book.py` 기록 종류별 허용 칸). 넣는 방법에 따라 의미가 달라져(기준일 칸 추가 = 기록 형식 변경 / 2026-01-02 매수(BUY)로 바꿔 쓰기 = 실제와 다른 매수 기록 · 05 시장 흐름이 '매수 전후 변화'로 계산됨) 설계자 판단 대상 — 인계 §4 · `docs/backlog/BACKLOG.md` §8.
- **인계**: `docs/handoff/POC5-06_MANUAL_REENTRY_REVIEW_AND_ML_EVIDENCE_HANDOFF_2026-10-10.md`.
