# POC5-06 인계 — 수동 재진입 검토 · ML 근거 (2026-10-10)

- **작성**: 개발자(VSCode Claude) · **독자**: 다음 세션 개발자(10-12 POC5-02 · 03 확인 → 10-23 공식 R0 → 다음 설계 대응)
- **입력**
  - 설계서 `docs/ai_design/POC5/POC5-06_MANUAL_REENTRY_REVIEW_AND_ML_EVIDENCE_DESIGN_V1.md` — 개정 2 · §10 PLAN 판정 · §11 RESULT 판정 · 전달문 원문 3건
  - PLAN `docs/ai_plan/POC5/POC5-06_MANUAL_REENTRY_REVIEW_AND_ML_EVIDENCE_PLAN_V1.md`
  - 결과서 `docs/ai_result/POC5/POC5-06_MANUAL_REENTRY_REVIEW_AND_ML_EVIDENCE_RESULT.md` — §6-2 독립 검토 · §6-3 검증자 r1 정정 · §10 배포 · 종료 기록
  - 직전 인계 `docs/handoff/POC5-05_PERSONAL_HOLDINGS_TRADE_HISTORY_HANDOFF_2026-10-09.md` · 정본 `docs/PROGRAM_TRUTH.md` · 상태 `docs/STATE_LATEST.md` · `docs/backlog/BACKLOG.md` §8

```text
POC5-06   IMPLEMENTED_VERIFIED_DEPLOYED_CLOSED (2026-10-10)
          검증자 r1 REJECTED(원장 사본 손상 처리) → r2 VERIFIED(위험 NONE) · 설계자 RESULT PASS_TO_DEPLOY(지시문 외 변경 5 · 한계 6 수용)
          구현 커밋 21706285 · OCI pull 없음(OCI 파일 변경 0) · PC 재기동 · KODEX 200 실화면 사용자 확인 · 산출물 · 부수효과 개발자 확인
          ML 운영 승격 NOT_APPROVED · 승인된 운영 · 추천 모델 none(2026-10-09 PC 수동 연구 한정 예외만)
남은 운영  10-12(월) 08:10 이후  POC5-02 첫 결과 행 · POC5-03 화면 가격 결과(POC5-01B 인계 §3)
          10-23(금) 배치 완료 뒤  공식 R0 1회(POC5-04 인계 §2)
다음 설계  사용자 제안 — 기존 보유(기준잔고)의 시작일 미상 → '2026-01-02' 로 두는 안(§4 · 설계자 판단 대상)
```

---

## 1. 만든 것

- **화면 「종목 관리」**: History 의 보유 기간마다 [재진입 검토](매매 유무 무관) → 검토 창이 History 창 자리를 대신 연다('← History' 로 복귀 · 창 겹침 없음). 세 부분 — 1 내 거래 · 2 저장된 근거(기준일 feature 5 · 05 시장 흐름 · 원장 사본 같은 종목 알림 · 관측만 = 건수 + 펼치기 · 연관 근거 · 평가(메모) 먼저 · 계약 버전 · 이동 링크는 메뉴만 바꿈) · 3 ML 검토([ML 검토 실행]을 누를 때만). 아래 줄 = 읽은 기준(revision · 문서 hash 앞 12자리 · 원장 동기화 · 가격 기준일) · [매매(매매 창)] / [재매수(매매 창)] = 05 창(ML 결과 연결 없음).
- **API(로컬)**: `GET /holdings/trade-history/reentry-review`(읽기 전용 · 학습 · 외부 조회 · 쓰기 0 · scikit-learn import 0) · `POST /holdings/trade-history/reentry-review/ml`(ETF 하나 · 동기 · 화면 제한 60초).
- **ML**: D20 = '이후 20거래일 최저 종가 변화(연구 추정)' · feature 5 · StandardScaler → Ridge(alpha 1 · svd) · [-1, 0] 제한 · 연구 축 마지막 189일 = 63 × 3 구간 검증(학습 = 평가 끝이 구간 시작 전 · 구간 252 미만 = DATA_SHORT) · 학습 중앙값 기준 · MAE %p(화면 소수 2자리로 개선 / 차이 없음 / 악화).
- **모듈** `app/reentry_review/`: `prices.py`(전체 종가 reader · 연구 축 · 경계 · `AxisSeries`) · `model.py`(D20 · feature · 기준일 창 판정 · 검증 · 최종 추정) · `ledger.py`(원장 사본 연결 · 손상 판정 `copy_problems`) · `review.py`(조립 · 실행 · 산출물) · `models.py`(상태 · 문구). 05 adapter: `holdings_history_view.history_of` · `market_flow_input_of` · `holdings_market_flow.build_market_flow(connection=)`.
- **산출물**: `state/ml/research/poc5_06/<YYYYmmddTHHMMSS>_<8hex>/review.json · input_snapshot.json`(gitignore · 임시 폴더에 다 쓴 뒤 이름 바꿈). 첫 실사용 = `20261010T234350_3e4a51dc`(069500 · OK · WORSE).
- **기반 문서**: 2026-10-09 POC5-06 한정 연구 예외(설계자 §10-1 확정문) — PROJECT_ORIGIN_INTENT §9.5 · ASSUMPTIONS Q6 · POC5-00 설계 · PLAN · STATE. 원래 금지 문장은 보존.

## 2. 운영 · 사용 메모

1. **상태 구분**: DATA_SHORT(축 61일 미만 · 검증 구간 학습 252 미만 — 추정값 안 보임) · PRICE_BASIS_UNCONFIRMED(기준일 60거래일 창의 축 공백 · 무효 종가 · 허용 밖 출처 · 감지된 경계 — 사유 전부) · AXIS_UNCERTAIN · NOT_ETF(개별주) · NO_PRICE(시세 없음 · ETF 목록 표 없음 = '확인 불가') · 원장 NO_COPY / READ_FAILED(읽기 실패 · 손상 — 다른 근거 · ML 은 그대로). 시세 DB 읽기 실패 · 산출물 저장 실패 = HTTP 500(결과 미표시 · '← History' 로 History 는 볼 수 있음).
2. **원장 사본 손상 판정 = 04 `ledger_reports.source` 와 같은 규칙** — 필수 6표 중 없음 · 결과 표를 만든 기록(`schema_version.price_outcome`) 뒤 `price_outcome` 없음 + 이 종목 후보 행의 `values_json` 해석 불가. 결과 표를 만든 기록 없이 `price_outcome` 없음 = 정상(성숙 전). 성공 동기화 기록 0 = 정상(시각 없음).
3. **PC 시세**: 「요즘 잘 오르는 ETF」 [최신 시장 데이터 갱신](전체 ETF · 약 1.5 ~ 2.5분)이 수동 갱신 경로. 늦으면 화면은 '이 날짜 기준 검토'(창 위 + 추정값 옆). 2026-10-10 18:55 KST 갱신으로 2026-10-08 까지 있음(10-05 는 2026 거래일 파일상 휴장).
4. **라이브 자료를 시험용으로 바꾸지 않는다** — 메모 · 다중 item · 지연 상태는 tmp 자료 · 화면 시험(`frontend/app/components/holdings_manage/reentryFixtures.ts` = 실제 백엔드 출력 · 바뀌면 다시 생성).
5. 결과 해석: 069500 은 단순 기준보다 오차가 큰 WORSE(정상 연구 결과). 29종목 OK 10 · DATA_SHORT 16 · NOT_ETF 3 은 모델 성능 · 투자 유효성 판정이 아니다(설계 §11-2).

## 3. 다음 개발자 주의 (이번 단계 교훈)

1. **'정상 자료 없음'과 '손상'을 가르는 규칙은 기존 판정을 먼저 찾아 같은 규칙으로** — 이번 r1 은 06 reader 가 필수 표를 2개만 보고 나머지 표 없음을 '평가 없음' · '집계 중'으로 받은 것. 04 `REQUIRED_TABLES` · 03 동기화 손상 정의가 이미 있었다. 새 reader 는 그 판정을 재사용하고, 표가 있는 척하는 조건 분기(`if "표" in present`)를 두지 않는다.
2. 설계 대조는 표 · 문구 한 줄씩 — 메모 표시 · 관측 행 펼치기 · 평가 먼저 · 추정값 옆 지연 표시 · 알림 수 = event 수가 목업 확인 뒤에 나왔다. 목업 단계에서 설계 §2 · §3 · PLAN §2-3 문장을 화면 요소와 1:1 로 대조한다.
3. 변이 시험은 저장소 사본(scratchpad)에서 — 같은 집합이 되는 변이(예: 유효 날짜 dict 로 다시 거르기)는 의미 없는 변이이므로 결과서에 그렇게 적고 다른 변이로 바꾼다.
4. 시험 파일: `tests/test_poc5_06_reentry_review.py` 685 · `tests/test_poc5_06_reentry_model.py` 341(KS-10 근접선 1,450 여유).
5. `git add -A docs/` 금지 — 사용자 소유 untracked `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md`.

## 4. 다음 단계

- **10-12(월) 08:10 이후**: POC5-02 첫 결과 행(OCI 읽기 전용) · POC5-03 화면 가격 결과 표시 확인 → 02 · 03 종료(POC5-01B 인계 §3). 그 뒤 원장 사본을 동기화하면 06 검토 창의 가격 결과 칸도 채워진다.
- **10-23(금) 배치 완료 뒤**: 공식 R0 1회(POC5-04 인계 §2).
- **사용자 제안 → 설계자 판단(2026-10-10)**: "지금 보유하고 있는 종목들의 최초 거래일시를 모르니 2026-01-02로 해두면 어떨까"(사용자는 실제 매매를 더 넣어 가며 쓸 계획). 사실:
  - 현재 기존 32줄은 기준잔고(BASELINE · 첫 저장 때 확정)이고 기준잔고 · 잔고 등록(REGISTER) 기록은 **수량 · 평단 두 칸만 허용**한다(`app/holdings_book.py :: PAYLOAD_KEYS`). 파일에 날짜를 직접 넣으면 무결성 검사에서 **손상**으로 판정된다 — 파일 수기 편집 금지.
  - 방법에 따라 의미가 다르다 — (가) 기준잔고에 '기준일' 칸 추가(매수일 아님 표기 · 기록 형식 · 무결성 · 05 시장 흐름 · 06 내 거래 표시 변경) / (나) 2026-01-02 매수(BUY)로 바꿔 쓰기(실제와 다른 매수 기록 · 05 시장 흐름이 2026-01-02 종가 기준 '매수 전후 변화'로 계산 · 06 '매수일 미상' 안내 사라짐) / (다) 그대로 두고 앞으로의 실제 매매만 날짜와 함께 입력(지금 구조로 가능).
  - OCI 적용 payload(5필드)는 어느 쪽이든 영향 없음. ML(D20)은 개인 거래 · 날짜를 쓰지 않는다.
  - 설계서가 오면 바로 코딩하지 말고 PLAN 먼저(`docs/ai_plan/POC5/`).
