# POC6-14 개발 PLAN V1 — 전향 ML 비교 결과의 PC 조회

작성 2026-10-30 · 작성자: 개발자(VSCode Claude) · 수신: 설계자

```text
STATUS   = PLAN 제출(2026-10-30 · 설계 §10 네 묶음 · 질문 3) · 전체 화면 목업(로컬 전용)
           → 설계자 PASS_WITH_REQUIRED_CORRECTIONS(2026-10-30 · Q1 · Q2 · Q3 권장안 수용 · 보고 상태 · 머리말 범위 · 가짜 시각 보완 · 재제출 없음)
           → 보완 반영 = 이 문서 §6 · 목업 정정 · 기존 「ML 실험」 카드 모양 맞춤 → **사용자 목업 확인(2026-10-30 '괜찮은 것 같습니다')** → 구현
           · 사용자 의견 '하나의 메뉴에 기능이 계속 추가 — 폴더(메뉴) 구분 필요' → 설계자 전달(§7 · 14 구현은 판정 위치대로 진행)
           → 구현 → 사용자 실화면 확인(2026-10-30) → 검증자 r1 · r2 REJECTED → 정정 → r3 VERIFIED → 설계자 RESULT PASS(2026-10-31 · 결과서 §13) → 구현 커밋 89afeba6 push → IMPLEMENTED_VERIFIED_CLOSED(2026-11-01 · 결과서 §14)
DESIGN   = docs/ai_design/POC6/POC6-14_FORWARD_MODEL_COMPARISON_PC_VIEW_DESIGN_V1.md
DECISION = docs/ai_design/POC6/POC6-14_FORWARD_MODEL_COMPARISON_PC_VIEW_PLAN_DECISION_2026-10-30.md(판정이 본 PLAN SHA-256 = 제출 파일과 같음)
조사     = 2026-10-30 12:57 ~ 13:10 KST(약 13분 · 상한 60분) · 06 · 13 · 「진단·상태」 접점만 · 코드 읽기 + 06 연구 폴더 읽기 전용
           · 목업 자료 생성 스크립트(저장소 밖)의 읽기 전후 연구 폴더 JSON 22개 해시 같음 · 외부 조회 · 실행 · 학습 · 모델 열기 0
구현     = 0(판정 · 목업 확인 전 착수 안 함)
```

## 1. 현재 파일 · 읽기 접점(설계 §10-1)

연구 폴더 = `app.ml_evidence.forward_artifacts.ROOT_REL` = `state/ml/research/poc6_06`(06 `protocol.ROOT` 와 같은 상수 · 서버가 정함 · 클라이언트 지정 없음).

| 자료 | 경로 · 칸 | 읽는 방법 |
|---|---|---|
| 고정 표본 | `cohort_v1/cohort.json` — `tickers`(24) · `selected[].name`(선정 당시 이름) · `selected_at` · `cohort_id` | JSON 읽기. 종목명은 여기서(시장 DB · 보유 파일 안 읽음) |
| 예측 | `predictions/<D>/<run>.json` — `record_type` · `D` · `model.model_version` · `times`(published_at · close_cutoff_at · input_cutoff) · `entries[]`(ticker · role · `input.source`(object · observed_at · available_at) · `methods{M: status · pred · raw · reason}`) · `not_predicted` | **`records.prediction_docs` · `records.primaries` 그대로 재사용** — 영수증(해시 · id · D · 확인 < 마감) · 재시도 연결 · 진단/부가 분리를 새로 판정하지 않음 |
| 공개 확인 | `predictions/<D>/<run>.receipt.json` — confirmed_at · prediction_sha256 | 위 함수 안에서 검사(`_receipt`) |
| 성숙 결과 | `targets/<D>/<ticker>.json`(MATURED 만 · `target` · `target_end`) | `records.targets` 재사용. **지금은 폴더 없음(성숙 0)** |
| 성숙 대기 상태 | **종목별 파일 없음**. `runs/<id>.json` 의 `maturity.open[]`(ticker · D · status · tried)에만 남음 · **예정일 칸 없음** | 가장 늦은 회차(`finished_at`)부터 그 (종목 · D) 가 있는 첫 회차의 상태 · 회차 id · 시각 |
| 비교 보고 | `reports/<run_id>.json` — generated_at · counts · per_date · main(`HGB_vs_MEDIAN_RIDGE` · `MLP_CPU_vs_MEDIAN_RIDGE` · `ALL_FOUR` 각각 rows · dates · tickers · excluded_rows · mae_pp · `deep_loss_le_8pct`) · by_ticker · by_month · by_model_version · notes | JSON 읽기만(재계산 없음) |

- **단위(실제 산출물 대조)**: `pred` · `raw` · `target` = 비율(예측 파일 `unit` 칸 = "ratio(−0.05 = −5%) · [-1, 0] 제한 후 pred · 제한 전 raw" · 목표 파일 `unit` = "ratio(−0.05 = −5%)"). `mae_pp` · `under_estimate_pp` = 이미 %p(`report.py` 가 ×100). → API 가 비율만 **한 곳에서 ×100** 해 `*_pct` 로, %p 는 그대로 `*_pp` 로 낸다. `raw` 는 응답에 넣지 않는다.
- **판 선택**: 행마다 그 주 기록의 `model.model_version`. 기준일 머리에는 판 집합(1개면 그 판 · 여러 개면 '여러 판(n)').
- **보고 선택**: `reports/*.json` 중 schema · protocol 이 맞는 것의 `generated_at` 최대. 이름(UTC 시각 접두)이 그보다 늦은 파일이 읽기 · 형식 실패면 '최신 보고 확인 필요'를 함께 낸다(조용히 숨기지 않음). 보고 `per_date` 에 선택 D 가 없으면 '보고서 확인 대기'.
- **순수 읽기 가능 여부(실측)**: `records` · `report` 를 불러온 뒤 numpy · pandas · scikit-learn · scipy · torch · joblib 이 올라오지 않았다. `protocol` 이 불러오는 `ml_evidence.forward_artifacts` · `three_push_runtime.ledger_outcome` 도 가볍다. 같은 모듈의 쓰기 함수(`write_receipt` · `report.write`)는 부르지 않는다. **06 코드 수정 · 리팩터링 없이 쓸 수 있다.**
- **동시 쓰기**: 06 은 임시 파일 → `os.link` 로만 게시하고 영수증은 예측 뒤에 쓴다. 읽는 도중 영수증이 아직 없으면 그 기록은 주 기록에 들어가지 않는다(기존 판정). 잠금 파일(`.run.lock`)은 잡지도 지우지도 않는다.
- **조회 비용**: 요청마다 예측 파일 전부 읽기 · 해시(지금 3개 · 약 320KB · 거래일마다 약 107KB 늘어 1년 약 27MB). 지금은 작아 캐시를 두지 않는다.
- **지금 PC 자료(관찰 · 화면 상수로 쓰지 않음)**: 기준일 3개(10-22 · 10-27 · 10-29) · 각 24종 · 네 방법 모두 OK · 모델 판 1개 · 성숙 0 · 보고 4개(최신 = 주 기록 72 · 비교 행 0 → MAE null).

## 2. 화면 · API 접점(설계 §10-2)

- **위치**: 사이드바 「진단·상태」 그룹의 **「ML 실험」**(`MLView.tsx` · 58줄) 화면 맨 위에 카드 1개(Q1). 기존 카드 다섯 개의 내용 · 순서는 그대로다. 그중 `MLTimeseriesReadinessCard`(POC2 준비도 7축)가 설계가 말한 예전 준비도 카드이며 06 현황으로 쓰지 않는다. 「개발·실험용」(`diagnostics` · 미리보기 · LEGACY)에는 넣지 않는다.
- **기존 06 조회 화면 · API**: 없음(`forward_compare` · `poc6_06` 을 쓰는 API · 프런트 0건) → 중복 없음 · 새로 연결.
- **새 GET 한 개**: `GET /ml/forward-comparison?d=YYYY-MM-DD`(d 생략 = 가장 최근 유효 D · 형식 오류 422 · 유효 D 목록에 없으면 404 '선택한 기준일 기록 없음'). 쓰기 · 실행 · 모델 열기 · SSH · 외부 조회 0.

| 파일 | 구분 | 책임(예상 줄 수) |
|---|---|---|
| `app/forward_compare_view.py` | 신규 | 06 읽기 함수 호출 · 회차/보고 선택 · 상태 판정 · 단위 변환 · 사유 경로 가림 · 응답 조립(≈280) |
| `app/api_ml_forward_comparison.py` | 신규 | 라우터 · 응답 모델 · 날짜 인자 검사(≈110) |
| `app/api.py` | 수정 | import · include_router 2줄(585 → 약 588 · KS-10 근접선 600 아래 · 새 책임은 별도 파일) |
| `frontend/lib/api/mlForwardComparison.ts` · `lib/api/index.ts` | 신규 · 수정 1줄 | 타입 · 요청(≈110) |
| `frontend/app/components/ml_forward/ForwardComparisonCard.tsx` | 신규 | 상태 줄 · 기준일 · 근거 · 24종 표 · 행 상세 · 복사(≈350) |
| `frontend/app/components/ml_forward/ForwardCompareReport.tsx` | 신규 | 누적 비교 두 표 · 분모 · 보고 상태(≈160) |
| `frontend/app/components/ml_forward/forwardText.ts` | 신규 | 상태 문구 · 포맷 · 복사문(화면과 같은 함수 · ≈160) |
| `frontend/app/components/MLView.tsx` | 수정 | import · 카드 1줄 |
| 시험 | 신규 | `tests/test_poc6_14_forward_view.py`(≈450) · `ml_forward/*.test.tsx`(≈350) |

- **재사용**: 도움말 = `holdings_risk_evidence/HelpPopover`(클릭 · Esc · 바깥 클릭 · Tab 으로 닫힘 · 새 팝업 없음) · 표 = `compact-table` · 버튼 = `btn-md` / `reject`(중간 40px) · 포맷 = `holdings_compare/helpers` 의 `fmtPct` · `fmtPctp`(부호는 Q2) · 복사 = `DecisionDraftPreviewCard` 의 `navigator.clipboard.writeText` + 실패 처리 방식(공용 함수가 없어 같은 방식의 작은 함수).
- **연결하지 않는 것**: POC5-24 선택 근거 초안의 ML 칸 · AI 세션 저장 · 외부 AI 전송 · PUSH · 06/13 실행 코드.
- **기반 문서**: 세 문서의 POC6-06 예외 문장 = "운영 경보 · 종목 추천 · 자동 매매의 허용이 아니며 …"(KILL_SWITCHES 148 · ORIGIN 337 · ASSUMPTIONS 56). 읽기 화면을 막는 문장이 없어 **충돌 없음 · 기반 문서 추가 없음**. 화면은 '연구용 · 운영 미채택'과 추천 아님을 밝힌다.

**응답 계약 초안**(필드 이름은 구현에서 이 표 그대로):

```text
status          OK | NO_RECORDS | CHECK_REQUIRED | READ_FAILED  (+ message · 화면 문구용 짧은 사유)
cohort          {id, size, selected_at}
dates           [{D, primary_rows}]  — 유효 주 기록이 있는 D 만 · 최근 순
selected_D      D
basis           {visible_by_min, visible_by_max, input_cutoff, close_cutoff_at, model_versions[], maturity_basis{run_id, finished_at} | null}
rows[24]        티커 순 · {ticker, name, primary(bool), why_missing?,
                 methods{MEDIAN|RIDGE|HGB|MLP_CPU: {status, pred_pct?, reason?, retried_at?}},
                 actual{state: MATURED|PENDING_NOT_DUE|PENDING_CALENDAR|DUE_DATA_MISSING|DATA_CHECK_REQUIRED|NOT_EVALUATED,
                        actual_pct?, target_end?, basis_run?, basis_at?},
                 detail{run_id, visible_by, write_started_at, model_version, input{object, observed_at, available_at}}}
report          {state: OK|WAITING|CHECK_REQUIRED|NONE, id, generated_at, dates_covered[], counts{...}, comparisons{...: rows, dates, tickers, excluded_rows, mae_pp{}, deep{rows, under_estimate_pp{}}}, newer_unreadable?}
other           {unconfirmed_forward_records, diagnostic_entries, supplementary_entries}
넣지 않음        raw · 특징값 · 가격 창 · 모델 파일 해시 · 절대 경로 · 보유 · 계정 · 키
```

## 3. 상태 · 시험(설계 §10-3)

| 경우 | 응답 · 화면 |
|---|---|
| 연구 폴더 없음 · 유효 주 기록 0 | `NO_RECORDS` '공개 확인된 연구 기록 없음'. 마감 뒤 확인 · 진단만 있으면 그 수를 함께(성과 · 표본에 넣지 않음) |
| 읽기 · 해석 실패 / schema · protocol · cohort 불일치 | `READ_FAILED` / `CHECK_REQUIRED` · 숫자 없음 · [다시 읽기]. 빈 정상 응답으로 바꾸지 않음 |
| 방법 실패(FAILED · ENV_MISMATCH · NOT_RUN_ENV · DATA_SHORT) | 그 칸 숫자 없음 + 짧은 사유(행 상세에 원문 · 절대 경로는 가림 · 200자). 다른 방법 · 이전 판 · 0 으로 대체 안 함 |
| 재시도로 채운 방법 | 값 + '재시도로 채움'(기존 연결 판정 그대로 · 재시도 공개 확인 시각) |
| OK 인데 값이 비유한 · [-1, 0] 밖 | 그 칸 '확인 필요'(숫자 내보내지 않음) |
| 성숙 대기 4종 | 설계 §4 문구 그대로 · 회차 id · 시각은 행 상세. 예정일은 저장돼 있지 않아 표시 안 함(새로 만들지 않음) |
| 아직 어느 회차도 성숙 평가를 안 한 행 | `NOT_EVALUATED` '성숙 확인 전'(Q3) |
| cohort 종목인데 그 D 주 기록 없음 | 표에 남기고 '이 기준일 주 기록 없음'(`not_predicted` 사유가 있으면 함께) |
| 보고 없음 / 선택 D 미포함 / 더 늦은 보고 손상 | `NONE` / `WAITING` '보고서 확인 대기' / `CHECK_REQUIRED` '최신 보고 확인 필요'(정상 보고는 함께) · [다시 읽기]. 보고를 만들지 않음 |
| 분모 | 방법별 예측 수 · 비교별 행 · 날짜 · 종목 · 빠진 행 · 성숙 수 · 대기 수를 각각. 하나로 합치지 않음. 비교 행 0 = '아직 비교할 결과 없음' |
| 응답 경합 | 요청마다 순번 — 늦게 온 이전 기준일 응답은 버림. 복사문은 그때 화면에 그린 응답에서만 만듦(클릭 때 조회 없음) |

- **시험(가짜 자료 · tmp 폴더 · 라이브 연구 폴더 · DB 를 열지 않음)**:
  - 백엔드: 읽기 전용(전후 파일 해시 · 잠금 파일 미생성 · `models` · `training` · `forward` 모듈이 import 되지 않음 · subprocess · 네트워크 0) · 영수증 없음 / 해시 불일치 / 마감 뒤 확인 / 진단 · 부가 / 재시도 연결 · 폴더 없음 / 보고 없음 / 더 늦은 보고 손상 / cohort 불일치 / 선택 D 없음 / 날짜 형식 · 비율 ×100 · %p 그대로 · 비유한 · 범위 밖 · 사유 경로 가림 · 응답에 절대 경로 · 보유 칸 없음 · 같은 D 다시 읽어도 같은 응답.
  - 프런트: 상태별 문구 · 0 근처 표시(Q2) · 분모 분리 · 행 상세가 그 행 아래 · 늦은 응답 버림 · 복사문 = 화면 응답 · 도움말 열고 닫기.
  - 검사: black · flake8 · py_compile · tsc · eslint · vitest + 새 · 관련 시험. 06 · 13 실행 코드 무변경이라 연구 재실행 · 학습 · 성숙 처리 · OCI 점검 없음.
  - 실제 성숙 · 방법 실패 상태가 없어 그 경우는 **가짜 자료 검증**으로 기록한다.
- **실연결**: PC 의 실제 06 폴더를 한 번 읽어 값 · 날짜 · 대기 상태 · 복사를 사용자 실화면으로 확인(새 예측 · 미래 결과 기다림 없음).

## 4. 전체 화면 목업(설계 §10-4 · 로컬 전용 · 저장소 · 공개 게시 없음)

`/private/tmp/claude-501/-Users-hyungsookim-projects-krx-hyungsoo/a6c4c2ec-40d4-4eb9-a7ff-9759f33e21bb/scratchpad/poc6_14_mock/index.html`(1440px · 1000px 캡처 = 같은 폴더 `shots/`)

| 화면 | 자료 | 보여 주는 것 |
|---|---|---|
| ① 기본 | 실제 | 상태 줄 · 기준일 선택 · 근거 · 24종 표(네 예측 · 결과 상태) · 누적 비교(비교 행 0) |
| ② 상세 · 도움말 | 실제 | 첫 행 상세(그 행 바로 아래) · [복사] · 도움말(?) 열림 · 복사되는 문장 |
| ③ 성숙 · 실패 | 가짜 | 성숙 값 · 환경 불일치 · 실패 · 재시도 · 대기 · 일정 확인 불가 · 미확보 · 확인 필요 · 주 기록 없음 · 여러 판 · MAE 두 표 |
| ④ 보고 대기 | 가짜 | 새 기준일의 '보고서 확인 대기' · '최신 보고 확인 필요' |
| ⑤ 없음 · 실패 | 가짜 | 기록 없음 · 진단만 있음 · 불러오기 실패 |

목업의 부호 표시는 Q2 권장안이다.

## 5. 질문(실제 충돌 · 없는 필드만)

- **Q1 위치**: 설계의 「진단」을 「진단·상태 › ML 실험」 화면 **맨 위 카드**로 둔다(권장 · 목업). 대안 = 같은 화면 맨 아래(기존 카드 다섯 개 뒤).
- **Q2 부호**: 기존 `fmtPct` · `fmtPctp` 를 그대로 쓰면 D20(늘 0 이하)의 0 근처가 "+0.00%" 와 "-0.00%" 로 섞여 보이고(지금 자료 130730 · 458030 행), MAE · 작게 추정한 정도(늘 0 이상)가 "+3.41%p" 처럼 차이값으로 보인다. 권장 = 같은 계열의 작은 표시 함수 하나(`forwardText.ts` · 화면과 복사 공용): 표시값 0.00 → "0.00%" · MAE · 작게 추정한 정도 → 부호 없는 %p. 대안 = 기존 함수 그대로.
- **Q3 성숙 평가 전 행**: 06 은 한 실행에서 성숙 평가를 예측 기록보다 **먼저** 한다(실측: 10-30 실행의 대기 48행 = 10-22 · 10-27 분 · 10-29 분 없음). 그래서 가장 최근 기준일은 다음 실행 전까지 어느 회차에도 상태가 없다. 설계 §4 표에 없는 경우라 '성숙 확인 전'(`NOT_EVALUATED`)으로 따로 표시한다(권장). 대안 = '결과 대기'로 합침(PENDING_NOT_DUE 와 구별 못 함).

## 6. 판정 반영(2026-10-30 · PASS_WITH_REQUIRED_CORRECTIONS)

§1 ~ §5 는 제출 원문 그대로 두고, 판정으로 바뀐 것만 여기에 적는다. 겹치면 이 절이 우선한다.

### 6-1. 질문 판정

- **Q1 수용**: 「진단·상태 › ML 실험」 맨 위 카드 · 기존 다섯 카드 내용 · 순서 그대로. 화면 소개 문장(`MLView` 의 subtitle)을 판정 문장 **"학습 자료 상태와 저장된 전향 예측·비교 결과를 확인하는 화면입니다."** 로 바꾼다(그 밖의 화면 개편 없음).
- **Q2 수용**: `forwardText.ts` 에 이 화면 · 복사 공용 표시 함수. 기존 `fmtPct` · `fmtPctp` 는 그대로 둔다(전역 동작 무변경).
  - 소수 둘째 자리로 만든 D20 이 0.00 이면 "0.00%"(+0.00% · -0.00% 섞지 않음). MAE · 작게 추정한 정도 = 부호 없는 %p.
  - **표시 전 검사(백엔드)**: 예측 · 실제 = 유한 · [-1, 0] 비율, MAE · 작게 추정한 정도 = 유한 · 0 이상. 어기면 그 값은 null + '확인 필요'(음수 MAE 를 abs 로, 양수 D20 을 반올림 0 으로 살리지 않음). null · 실패는 0 이 아니다.
  - 비교 차이값을 보일 일이 생기면 부호를 보존한다(이번 화면에는 차이값 표시 없음). '%p 는 모두 부호 제거'라는 공용 규칙을 만들지 않는다.
  - ×100 은 API 의 비율 값 한 곳뿐 · 보고의 %p 값은 다시 곱하지 않음 · 원기록 · 저장 숫자 무변경.
- **Q3 수용**: 조회 응답에만 `NOT_EVALUATED`(06 에 파일 · 상태를 쓰지 않음). 뜻 = "현재 보관된 기록에서 이 행의 성숙 평가 상태를 아직 확인할 수 없음"(달력 판단 · 앞으로의 평가 보장 아님).
  - 유효 목표 → MATURED · 없으면 가장 늦은 회차 중 그 (종목 · D) 가 있는 회차의 상태 · 둘 다 없으면 NOT_EVALUATED. 날짜를 세거나 mature · run 을 부르지 않는다.
  - 회차 기록 · 목표 파일을 읽다가 난 오류 · 형식 불일치는 '성숙 확인 전'으로 숨기지 않고 READ_FAILED / CHECK_REQUIRED.
  - 표 = "성숙 확인 전" · 근거 줄 · 행 상세 · 도움말 = "이 기준일의 성숙 평가 상태 기록이 아직 없습니다".

### 6-2. 보고 상태(판정 §5) — 코드 확인 결과와 규칙

- 06 `forward.run` 순서: `_run`(성숙 평가 → 예측 · 영수증) → `report.write`(`reports/<run_id>.json`) → `runs/<run_id>.json`(칸 `report` = 보고 경로). 보고 id = 그 회차 id.
- `per_date` = 보고를 만들 때 있던 **모든 주 기록 기준일**(`report.build` 의 `forward_days` = 주 기록 D 전부) · 날짜마다 `input_ok_primary` · `matured`. 그래서 '예측 포함 기준일' = per_date 키, '성숙 비교에 들어간 기준일' = `matured > 0` 인 날짜로 나눠 보인다(06 보고 형식 변경 없음).
- 규칙:
  1. 정상 보고가 있고 비교 행 0 · MAE null → 정상 보고 · '아직 비교할 결과 없음'.
  2. 정상 보고 0개 → `NONE` '보고 없음'.
  3. 선택 D 의 대응 보고 = 그 D 의 주 기록을 쓴 회차 id 의 `reports/<run_id>.json`(여러 회차면 각각). 있고 정상 → `INCLUDED`. 파일 없음 → `RUN_REPORT_MISSING` '이 기준일을 기록한 회차의 보고가 아직 없음(작성 중이거나 만들어지지 않음 · 이 화면은 보고를 만들지 않음)'. 있으나 읽기 · 형식 실패 → `RUN_REPORT_UNREADABLE` '최신 보고 확인 필요'.
  4. 보여 주는 누적 보고 = 정상 보고 중 `generated_at` 최대. id · 생성 시각 · 분모 · 예측 포함 기준일(개수 · 범위) · 성숙 비교 기준일(개수 · 범위)을 함께 적고, 선택 D 의 성적이라고 부르지 않는다.
  5. 정상 보고보다 이름(UTC 접두)이 늦은 파일을 읽지 못하면 '최신 보고 확인 필요' + 이전 정상 보고의 id · 시각. 이름 접두는 후보를 찾는 보조일 뿐 생성 시각 인증이 아니다.
  6. per_date 에 선택 D 가 없다는 것 하나로 '미생성'이라 하지 않는다(3 의 회차 보고 참조로만).
- 시험 추가: 정상 미성숙 보고(비교 행 0) · 보고 0개 · 회차 보고 없음 · 회차 보고 손상 · 더 늦은 보고 손상.

### 6-3. 머리말 범위 · 응답 칸 보완(판정 §6)

```text
basis   {visible_by{min,max}, input_cutoff{min,max}, record_runs[], model_versions[], maturity{runs[], at{min,max}} | null}
        — 값이 하나면 그 값 · 여럿이면 범위 또는 '여러 회차(n)' · '여러 판(n)'(임의 한 행 · 최근 판을 전체 근거로 붙이지 않음)
rows[]  detail 에 그 행의 회차 · 판 · 입력 · 성숙 상태 출처(회차 id · 시각)
report  {state, id, generated_at, counts, predicted_dates{count,first,last}, matured_dates{count,first,last},
         selected_D: INCLUDED | RUN_REPORT_MISSING | RUN_REPORT_UNREADABLE, newer_unreadable[]}
```

### 6-4. 목업 정정(판정 §6 · 사용자 확인 대상)

- 소개 문장 · '성숙 확인 전' 문구 · 보고 상태 문구 · 머리말 범위 반영.
- 가짜 ③(2026-12-02 시점): D 2026-11-03 · 입력 OCI 11-04 09:40 · 공개 확인 11-04 10:05(23종) · 12:05(1종 · 늦게 들어온 입력) · 마감 11-04 15:30 · 목표 끝 12-01(D 뒤 20거래일) · 성숙 평가 12-02 10:05 회차 · 보고 12-02 10:05 · 예측 포함 기준일 10-22 ~ 12-01 · 성숙 비교 기준일 10-22 ~ 11-03. 이 날짜에 맞지 않는 '결과 대기'는 빼고 실제 자료(D = 10-27) 화면으로 보인다.
- 가짜 ④(2026-11-02 시점): D 2026-10-30(금) · 입력 11-02 09:40 · 공개 확인 11-02 10:05 · 마감 11-02 15:30 · 회차 보고 없음 · 회차 보고 손상 두 예시.
- 실제 ①b 추가: D = 10-27 선택(결과 대기 · 최근 성숙 평가 10-30 10:05 회차).
- 가짜 화면은 서로 다른 미래 상황의 예시라는 표시를 유지하고, 날짜를 맞추려고 06 을 실행하지 않는다.
- **모양 맞춤(사용자 질문 2026-10-30 '다른 것과 동일한가')**: 실제 「ML 실험」 화면(개발 서버 · 읽기만)을 캡처해 대조했다. 기존 카드 네 개의 공통 부품으로 바꾼다 — 카드 머리 = `card` + `h2` + `helper`(회색 설명) · 상태 = `ml-readiness-badge`(available · partial · missing 둥근 꼬리표) · 표 = `market-topn-table`(바깥 테두리 없음) · 안내 = `message info` / `message error` · 버튼 = 기존 파란 버튼('다시 불러오기') · 근거 = 굵은 값 한 줄. §2 의 `compact-table` · 새 배지 · 새 상자는 쓰지 않는다. 설계 · 판정이 정한 ? 도움말(`HelpPopover`) · 행 바로 아래 상세 · [복사](중간 버튼)는 유지. 새 CSS 는 표의 숫자 칸 오른쪽 정렬 · 선택 행 정도로 최소.

## 7. 사용자 목업 확인 · 메뉴 구성 의견(2026-10-30)

- **목업 확인**: 판정 반영 목업 6종(실제 3 · 가짜 3)과 기존 「ML 실험」 카드 모양으로 맞춘 판(실제 앱 화면과 나란히 보기)을 보고 사용자가 "네 괜찮은 것 같습니다". 판정 §8-2 에 따라 구현을 시작한다.
- **사용자 의견(원문)**: "폴더 구분을 좀 해야겠다는 생각이 드는 것 같네요. 하나의 메뉴에 기능이 계속 추가되는 것 같은데 이 부분은 설계자에게 한 번 얘기해주세요."
- **현재 사실(개발자 확인 · 판단 없음)**: 「진단·상태」 그룹 = 데이터 상태 · ML 실험 · 받은 알림 기록 · 개발·실험용. 「ML 실험」(2026-08-16 사용자 지시로 세 화면의 ML 카드를 모은 화면)의 카드 5개 = ① ML 최소 데이터 레인 — feature 적재 상태 ② ML feature sanity check ③ ML evidence 갱신(실행 버튼) ④ ML baseline v0 룩백 검증 ⑤ 상대상승 참고점수 계산(relative_upside_v0 REJECT · 연구용). 2026-10-30 화면 기준 ①② ④ 의 자료 기준일 = 2026-08-27 · ③ 마지막 갱신 실행 = 2026-08-30. 14 카드가 들어가면 6개. POC6-02 ~ 11 연구 결과는 화면이 없다(CLI · 결과서).
- **처리**: 메뉴 · 화면 구분은 설계자 판단으로 넘긴다. 그동안 14 는 판정 Q1 위치(「ML 실험」 맨 위)로 구현한다. 카드는 독립 부품이라 위치가 바뀌면 연결만 옮긴다. 승인 없는 메뉴 개편은 하지 않는다.
