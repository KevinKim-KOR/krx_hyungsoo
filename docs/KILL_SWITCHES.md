# KILL SWITCHES

작성자: 사용자 본인
작성일: 2026-04-21
검토 주기: 발동 시
성격: 즉시 중단 조건

---

## 1. Hard Stops (즉시 중단)

### KS-1. Backend/Frontend 불일치
- 증상: 같은 데이터를 두 쪽이 다르게 표현
- 조치: 그 기능 작업 중단, 데이터 계약 재확인

### KS-2. 많은 기능이 UI에 표현되지 못함
- 증상: 백엔드에 기능은 있는데 화면에 없거나 접근 불가
- 조치: 신규 개발 중단, UI 정리 우선

### KS-3. 비건설적 핑퐁 3턴 초과
- 판정 기준: **3턴 안에 새 코드/산출물이 나오지 않으면 비건설적**
- 조치: 즉시 중단, 스스로 정리 후 재개

---

## 2. Soft Stops (재검토)

### KS-4. "다음에 이거할게요" 후 실행 안 됨 + AI 답변 의존 경고
- 증상 (1): 미완성 작업이 2주 이상 방치
- 증상 (2): AI 답변을 결정의 최종 닻으로 삼는 경향 — AI 가 한 말이라는 이유만으로 결정이 무게 잡히는 상태
- 조치 (1): 미완성 리스트 재확인, 1개 골라서 완료 또는 공식 폐기
- 조치 (2): AI 답변은 입력 중 하나로 다룬다. 최종 결정은 PROJECT_ORIGIN_INTENT 원칙 +
  백테스트 데이터 + 사용자 운영 경험으로 한다. AI 답변과 위 3가지가 충돌하면 후자를 우선한다.

### KS-5. 완성 이후 알림 과다
- 기준: 시간당 1건 초과 (급변 상황 제외)
- 조치: 알림 로직 재조정

### KS-6. 보유주식 교체 과다
- 기준: 수익률과 무관한 잦은 교체 (구체 숫자는 운영 중 확정)
- 조치: 교체 로직 재검토

---

## 3. AI 개입 신호 (사용자 직접 개입)

### KS-7. 벌려놓고 수습 안 됨
- 특히 문서 정리 / 폴더 정리가 요청해도 잘 안 되는 상황
- 조치: AI 지시 중단, 사용자 직접 개입

### KS-8. 자물쇠 놀이
- AI가 설계/규칙/가드레일만 계속 덧붙이며 전진 없음
- 조치: 해당 AI 세션 종료, 다른 접근으로 전환

### KS-9. 설계자 AI의 복잡도 폭증
- MongoDB 재도입 제안
- 문서 5개 이상 요구
- 엔터프라이즈 패턴 도입 제안
- 조치: "혼자 쓰는 프로젝트"임을 리마인드, 거부

### KS-10. 단일 파일 라인 수 / 책임 누적 임계 초과
- 정의:
  단일 파일이 여러 Step의 책임을 계속 흡수하여 파일명과 실제 책임이 어긋나고,
  다음 변경 시 기능 추가보다 구조 혼탁이 커질 위험이 있는 상태.
- 트리거 (다음 중 하나라도 발생):
  1. 테스트 파일이 1,500라인을 초과하고 여러 Step의 테스트가 섞임
  2. 테스트 파일이 2,500라인을 초과함
  3. 프론트 컴포넌트 파일이 900라인을 초과함
  4. 백엔드 핵심 모듈 파일이 650라인을 초과함
  5. 한 Step에서 같은 대형 파일에 신규 책임이 추가됨
  6. 파일명이 실제 책임을 설명하지 못함
  7. 검증자가 "단일 파일 책임 불명확" 또는 "구조 경고"를 보고함
- 근접 (사전 경고): 트리거 임계의 50라인 이내 (예: 백엔드 ≥600라인, 프론트 ≥850라인,
  테스트 ≥1,450라인). 근접 진입 시 추가 변경 자제 + 분리 우선 고려.
- 발동 시 조치:
  1. 다음 기능 Step 진입 중단
  2. Cleanup Step을 별도 명명
  3. 새 기능 추가 금지
  4. 테스트 의미 유지한 채 파일 분리
  5. UI/문구/데이터 계약 변경 금지
  6. 기존 테스트 개수와 검증 의미 유지
  7. STATE_LATEST / BACKLOG에 구조 경고와 처리 결과 기록
- Cleanup Step 진입 시 의무: 시작 시점에 모든 .py / .tsx / .ts 파일 라인 수를 실측하고
  근접 / 트리거 파일을 명시 보고한다 (추정값 / 이전 STEP 인용 금지).
- 예외 (트리거 적용 안 함):
  - 자동 생성 파일
  - lock 파일
  - fixture 데이터
  - 외부 vendored 파일
  - 단순 JSON 예시 파일

### KS-11. 의사결정 24시간 룰
- 증상: 새 데이터 없이 기존 결정을 24시간 안에 뒤집기
- 조치: 결정 변경 시 새 데이터/근거를 ASSUMPTIONS 또는 PROJECT_ORIGIN_INTENT에 기록 후 변경
- 적용 대상: 운영 빈도, 발굴 단위, 점수체계 기준 등 시스템 방향 결정

#### KS-11 변경 근거 기록 (2026-07-20, Mobile Decision Operating Boundary Amendment v1)

**KS-11 자체는 변경/약화하지 않는다.** 다음은 "모바일 UI 무조건 후순위" → "트리거 기반 진입 (트리거 충족 시 활성화)" 로 순서를 변경한 근거를 KS-11 조치 (새 데이터/근거 기록 후 변경) 에 부합하도록 남기는 기록이다.

**변경 근거**:
- PC 에서 실제 PENDING 초안 생성과 화면 확인 완료 (Holdings–Market PENDING Judgment Draft v1, DONE 2026-07-20)
- OCI publication 완료 (Holdings Evidence · Universe Momentum Evidence · Market Discovery)
- Telegram 3-PUSH 실제 발송 완료 (Market · Holdings · Spike Controlled Send v1, 각 DONE 2026-07-18~19)
- 사용자가 PC 에 주기적으로 접근하기 어려워 판단 기록이 발생하지 않는 운영 문제 확인 (2026-07-20 사용자 확정)
- 모바일 판단 경로 없이는 판단 원장과 성과 평가도 시작할 수 없음 (canonical 순서 Step 4 Decision Outcome Ledger 진입 조건)

**기록 위치**:
- `docs/PROJECT_ORIGIN_INTENT.md` §운영 원칙 (모바일 UI 후순위 → 트리거 기반)
- `docs/ASSUMPTIONS.md` §5.1 (제품 평면별 역할 · 최소 사용자 개입 원칙)
- `docs/MASTER_PLAN.md` (모바일 판단 운영 순서 앵커 섹션)
- `docs/handoff/POC2/POC2_MOBILE_DECISION_OPERATING_SEQUENCE_ANCHOR.md` (canonical 앵커)

#### KS-11 변경 근거 기록 (2026-07-22 ~ 2026-07-24, Telegram Push Operating Boundary Amendment v1)

**KS-11 자체는 변경/약화하지 않는다.** 다음은 사용자 운영 결정 기록:

- Mobile Decision Cockpit 은 DEFERRED_BY_USER 상태로 보류
- 현재 모바일 운영 채널은 Telegram PUSH 로 제한
- **전체 PUSH 횟수를 하루 3회로 고정하지 않음** (이전 "일 3회 자동 PUSH" 전역 제한 제거)
- Market briefing 은 평일 1회 유지 — 08:30 (2026-09-29 설계자 명시 개정 · 사용자 결정 · OPS-03 배포부터 · 그 전까지 08:00)
- Holdings 평가·브리핑은 평일 하루 3개 슬롯으로 운영
- Spike/Falling Alert 는 고정 시각 발송이 아닌 조건 발생형 알림으로 운영
- 평가 실행 횟수와 사용자 알림 횟수 구분
- 각 PUSH 의 실행·발송 정책은 해당 PUSH 목적에 맞게 결정
- Telegram 운영 최신성을 위해 OCI 의 제한적 런타임 가격 조회 허용
- OCI 의 전략·factor·threshold·ML·Holdings·주문 변경 금지는 유지

**기록 위치**:
- `docs/PROJECT_ORIGIN_INTENT.md` (§운영 원칙 · OCI 작업 빈도 · OCI 평면 역할)
- `docs/ASSUMPTIONS.md` §5.2 (Telegram PUSH 목적별 독립 운영 · 평가/알림 구분)
- `docs/MASTER_PLAN.md` (Telegram PUSH 운영 경계 정정 섹션)
- `docs/handoff/POC2/POC2_TELEGRAM_PUSH_OPERATING_BOUNDARY_AMENDMENT_V1_CONCLUSION.md`

#### KS-11 변경 근거 기록 (2026-07-26, OCI Autonomous Market Data Boundary Amendment)

**KS-11 자체는 변경/약화하지 않는다.** 다음은 OCI 역할 경계 정정 근거 (문서 전용 · 코드 변경 없음):

- **변경 근거**: PC 없이 Spike 를 반복 운영하려면 OCI 가 승인 대상의 일별 시세를 스스로 갱신하고 운영 artifact 를 생성해야 함이 실측으로 확인됨.
  - builder (`build_universe_momentum_result_scored`) 가 pykrx 를 직접 호출 (SQLite 미경유)
  - OCI `market_data.sqlite` 에 승인 seed·Holdings 시세는 있으나 적재가 2026-07-03 에서 중단 → artifact 신선도 상한이 곧 Spike 차단 원인 (seed 부재 아님)
  - 이번 정정 **이전** OCI 는 "실행 시점 현재가 조회" 까지만 허용되어 있어, PC 비의존 Spike 운영 불가 (본 정정으로 승인 대상 자율 시세 갱신·운영 artifact 생성까지 확장)
- **정정 내용**: OCI 에 `승인 seed ticker ∪ 현재 Holdings ticker` 한정 일별 시세 증분 갱신 + 승인 seed·PARAM·기존 산식 기반 운영 artifact 생성 (= Operational Derived Evidence) 허용.
- **PC 비의존 OCI 운영 목적**: Market·Holdings 는 이미 OCI 자율 운영 중. Spike 도 PC 상시 구동 없이 반복 운영하기 위한 경계 확장.
- **유지되는 금지**: seed 임의 변경 · 전체 시장 후보 탐색 · 신규 factor·threshold · PARAM 생성·승격 · 전략 변경 · ML · Holdings 수량·평단 변경 · 자동 주문. Published Evidence read-only 유지.
  > 2026-10-20 POC5-27 한정 해석: 사용자가 PC에서 명시 승인한 현행 허용 PARAM 값을 OCI 로컬 도구가 그대로 검증·발행·활성 확인하는 경로를 허용한다. PC의 OCI DB 직접 접속·개방과 OCI의 자율 PARAM 계산·선정·생성/승격 금지는 유지한다. 근거는 POC5-27 PLAN §1~§5의 소스 대조 및 사용자 원격 쓰기 구현 승인이다. 이 허용은 새 정책 생성·ML·seed 변경·자동 발송으로 확대되지 않는다. (출처: `docs/ai_design/POC5/POC5-27_PC_TO_OCI_RUNTIME_PARAM_ACTIVATION_PLAN_DECISION_2026-10-20.md` §1)
  > 2026-10-22 POC6-05 연구 증거 수집·보관 한정 예외: 기존 ETF 마스터의 유효 국내 상장 ETF를 seed·현재 보유 여부와 독립적으로 조회하여, 원천별 수신 창·실제 확보 시각·정정 판과 함께 OCI `state/ml/evidence/`에 보존할 수 있다. POC6-01의 원/달러·WTI·코스피 투자자 순매수 수집과 두 시장 흐름 표 반영, 허용된 기존 연구 증거의 추가 보관·PC 전송을 포함한다. 기존 OCI 운영 가격 표의 갱신 대상 확대, 후보 탐색, ML 학습·추론, PUSH/PARAM·선정/경보 기준 변경은 허용하지 않는다. 다른 단계의 전체 시장 수집·ML 예외로 확대하지 않는다. (출처: `docs/ai_design/POC6/POC6-05_CONTINUOUS_MARKET_DATA_AND_ML_EVIDENCE_RETENTION_PLAN_DECISION_2026-10-22.md` §2)
  > 연구 한정 예외(2026-10-22, POC6-06 PLAN 판정): 보유·seed·사용자 평가와 독립된 고정 ETF 표본 최대 24종을 대상으로, PC에서 기존 MEDIAN·RIDGE·HGB·MLP의 고정 recipe를 사용한 전향 D20 예측 기록·성숙 결과 비교 및 월 최대 1회 조건부 재학습을 허용한다. MLP는 이번 단계에서 CPU로 실행한다. 초기 장기 자료의 추가 조회와 OCI 증거 보관은 명시한 사용자 승인 범위로 수행한다. OCI는 수집·보관 역할을 유지한다. 이 예외는 운영 경보·종목 추천·자동 매매의 허용이 아니며, ML_OPERATION_PROMOTION=NOT_APPROVED, CURRENT_DEPLOYABLE_ML_MODEL=none, Q6 OPEN을 유지한다. 기존 POC6-02·04 결과와 미완료 요구 #3·#55·#57·#62는 변경하지 않는다. (출처: `docs/ai_design/POC6/POC6-06_HOLDINGS_INDEPENDENT_FORWARD_MODEL_COMPARISON_PLAN_DECISION_2026-10-22.md` §1)
  > 2026-10-24 POC6-08 연구 한정 예외: 기반 문서의 미래 하락 추정·ML 연구 제한에 대해, 본 POC6-08의 고정 표본·고정 입력 조합·PC 회고 D20 비교만 허용한다. 운영 경보·매매·새 모델 탐색 허용으로 확대하지 않는다. (출처: `docs/ai_design/POC6/POC6-08_VOLUME_AND_RELATIVE_STRENGTH_FEATURE_VALUE_PLAN_DECISION_2026-10-24.md` §5)
  > 2026-10-25 POC6-09 연구 한정 예외: POC6-09는 POC6-08의 고정 시험 예측·정답·기존 입력을 재학습 없이 분석하여, 큰 하락에 해당한 종목을 같은 검토 수에서 모으는 효용을 회고 비교하는 PC 연구로만 허용한다. 새 모델·입력·전향 예측·운영 위험 분류·알림 연결은 허용하지 않으며 Q6 OPEN과 운영 ML 미승격은 유지한다. (출처: `docs/ai_design/POC6/POC6-09_EXISTING_MODEL_REVIEW_PRIORITY_VALIDATION_PLAN_DECISION_2026-10-25.md` §5)
  > 2026-10-26 POC6-10 연구 한정 예외: 외부 참고 구조(친구 저장소는 참조만 · 코드·DB·브로커·발송 모듈 import 없음)를 바탕으로 한 고정 주간 추세 규칙 하나와 비교 기준 둘을, 봉인 KRX 한 판의 기준가 중립 합성 가격지수와 PC 연구 전용 Backtrader로 고정 공식 묶음 1회 회고 계산하는 PC 연구만 허용한다. 설계 및 PLAN 판정의 비중 축소 취소·전량 매도 이연·슬롯/현금·평가 시각 계약을 따른다. 결과는 가격지수 사례 판정이며 실제 계좌 수익·운영 매매 지시·종목 추천·PARAM·seed 변경·ML 학습·승격이 아니다. 설치는 유효한 사용자 승인, 공개 배포는 라이선스 조건 확인과 사용자 승인 범위 안에서 처리한다. 05 보관·06 전향 기록·월별 학습, Q6 OPEN, ML_OPERATION_PROMOTION=NOT_APPROVED, CURRENT_DEPLOYABLE_ML_MODEL=none을 유지한다. (출처: `docs/ai_design/POC6/POC6-10_REFERENCE_WEEKLY_TREND_BASELINE_PLAN_DECISION_2026-10-26.md` §6)
  > 2026-10-26 POC6-11 연구 한정 예외: POC6-11 H1에 한해 기존 봉인 KRX 자료로 가격·거래량 30열, 60거래일 상대성과 순위와 CPU LightGBM을 연구한다. 고정 주간 모의 운용의 합성 가격지수 결과만 비교하며 실계좌/추천 출력/OCI/PUSH/기존 전향 모델에는 적용하지 않는다. Q6 OPEN과 운영 ML 미승격은 유지한다. (출처: `docs/ai_design/POC6/POC6-11_WEEKLY_ETF_RELATIVE_RETURN_SELECTION_PLAN_DECISION_2026-10-26.md` §6)
- **현재 상태**: 경계 정의만 · 구현 전. `spike_operation = DISABLED` (구현 시점까지) · `market_holdings_operation = ACTIVE`.

**기록 위치**:
- `docs/PROJECT_ORIGIN_INTENT.md` (OCI 승인 대상 자율 시세 갱신·운영 artifact 생성)
- `docs/ASSUMPTIONS.md` §5.2 (OCI 역할 · Operational Derived Evidence · Fail-Closed)
- `docs/MASTER_PLAN.md` (OCI 자율 시장 데이터 경계 정정 섹션)
- `docs/handoff/POC2/POC2_OCI_AUTONOMOUS_MARKET_DATA_BOUNDARY_AMENDMENT_CONCLUSION.md`

#### KS-11 변경 근거 기록 (2026-09-26, POC5-00 운영 신호·판단 결과 원장 — Decision Outcome Ledger 선행 gate superseded)

**KS-11 자체는 변경/약화하지 않는다.** 다음은 '실제 판단 1건 · First Real Decision Cycle PASS 뒤 Decision Outcome Ledger' 순서를 바꾼 근거다(문서 기록 · POC5-01B 에서 정리).

- **변경 근거(새 데이터)**: POC5-00 PLAN §1-10 실측 — 원장 테이블 0 · 기존 실행 기록과 종목 단위 연결 0% · PUSH 가 무엇을 판단 · 전달했는지 남지 않는다. 판단 사이클의 '실제 판단 1건' 을 증명하려면 그 판단을 담을 원장이 먼저 있어야 한다.
- **결정**: 설계자 보완 판정 · 사용자 승인(2026-09-26 · POC5-00 Q27) — POC5 가 기존 Decision Outcome Ledger 미결 항목을 이어받아 완성한다 · 중복 원장 없음 · 기존 선행 gate(POC3-00 지도 S-05 · P-19 · MASTER_PLAN canonical 순서 3 → 5)는 superseded.
- **유지되는 것**: 투자 판단 자동화 금지 · 성공 임계 · 단일 성공 라벨 없음 · 과거 성과 backfill 금지(POC5-00 Q29) · PC · OCI 역할 경계.

**기록 위치**:
- `docs/ASSUMPTIONS.md` §3 A-7
- `docs/MASTER_PLAN.md` (현재 canonical 순서 5번 주석)
- `docs/STATE_LATEST.md` §6 Next action (canonical 순서 5번 주석)
- `docs/ai_design/POC3/POC3-00_PC_JUDGMENT_UI_INTEGRATED_IMPLEMENTATION_MAP_V2.md` (S-05 · P-19 · P-20 · Lane POC4 · POC5 · B-038 · B-103 주석)
- `docs/ai_plan/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_PLAN_V1.md` §2-9

사용자 요청만으로 KS-11 예외를 허용하지 않는다. 본 기록은 규칙 변경이 아니라 운영 정책 결정 근거의 문서화이다.

---

## 4. 이식 금지 (Phase 1 교훈)

1. MongoDB 자체 호스팅
2. Google OAuth
3. 친구 프로젝트(momentum-etf-main)의 구조/규모 통째 복제 금지
   - MongoDB, OAuth, 5계좌 운영, 다국가 대응 등 도입 금지
   - Next.js 자체는 허용 (사용자 판단)
   - 단, 친구 코드를 그대로 베끼지 말고 사용자 프로젝트에 맞게 새로 작성
4. 친구 프로젝트 통째 복제
5. 실시간 외부 API 의존 강화
6. "혹시 필요할까" 아카이브 레이어

---

## 5. 판정 후 행동

Kill Switch 발동 시:
- 즉시 중단
- 발동 일시 + 상황 기록 (간단히)
- 조언자(Claude)에게 상황 공유
- 재개 조건 정의 후 재개

Kill Switch는 토론 대상 아님. 발동하면 멈춤.

---

## 6. 이 문서 유지 원칙

- 신규 Kill Switch 추가 시 기존 하나는 검토해서 삭제/통합
- 총 항목 수 12개를 넘지 않음 (현재 11개 + 이식금지 6개 — KS-10 Step5D Cleanup 시점 추가,
  KS-11 의사결정 24시간 룰 POC2-Step6 종료 시점 추가)
- 발동 없이 6개월 지나면 해당 항목 재검토