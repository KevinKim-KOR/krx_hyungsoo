# OPEN QUESTIONS / ASSUMPTIONS

작성자: 사용자 본인
작성일: 2026-04-21
검토 주기: 매월 / 답변 발견 시
성격: 아직 확신 못 하는 것의 격리 보관

---

## 1. 상태 정의

- OPEN: 아직 검증 필요
- CHECKING: 현재 확인 작업 진행 중
- ANSWERED: 답 나옴, 다음 단계 진행 가능
- DROPPED: 더 이상 중요하지 않음 (폐기)

최대 활성 질문 수: **3개**. 4번째가 생기면 기존 하나를 해결하거나 드롭.
3개를 반드시 채울 필요는 없다 — 활성 질문은 실제 검증 트리거가 도달한 항목만 둔다.

---

## 2. 현재 Open Questions (3개)

### Q1. 여러 factor를 붙일 수 있는 구조의 엔진이 될 것인가?
- **상태**: OPEN
- **배경**: 원래 원했던 핵심 요구사항 (1년 뒤 목표와 직결)
- **확인 방법**: 새 프로젝트에서 첫 ML feature 추가 시 난이도 측정
- **판정 기준**: 새 factor 1개를 추가하는 데 10줄 이내로 가능한가
- **데드라인**: POC 1단계 완료 시점
- **첫 측정 evidence (2026-06-20, ML 축1 STEP)**: 첫 추가 factor `drawdown_20d`
  도입. 신규 모듈 `app/ml_relative_upside_features.py` 안에서 정의 (1줄
  계산 helper `_drawdown_from_peak` + rolling window 4줄 + dataclass 필드 1줄
  = 약 6줄). `FEATURE_COLUMNS` 튜플 + 모델 input dim (`nn.Linear(7,1)`) + raw
  feature → tensor 변환 (`_row_to_feature_tensor`) 까지 합치면 factor 1개 추가에
  ~10줄 안팎. 단 본 평가는 baseline 단일 회귀 수준의 evidence 이며, 향후 모델
  교체 시 재측정 필요. **본 evidence 만 기록하고 ANSWERED 로 승격하지 않는다**
  (지시문 §16 AC-14 — "아직 답이 확정되지 않은 질문을 ANSWERED 로 바꾸지
  않는다").
- **참조**: `docs/handoff/POC2_ML_RELATIVE_UPSIDE_SCORE_V0_CONCLUSION.md`.

### Q6. 위험 감지 = 위험 구간 분류 — factor / threshold / label 을 어떻게 확정할 것인가?
- **상태**: OPEN
- **배경**: 2026-06-06 ETF Exposure Data Unfolding 1차 — ML 방향성 2축 중
  축 2 (위험 감지 = 위험 구간 분류). 사용자 목적에 더 가까운 축이지만 본 시점
  factor / threshold / label 미확정.
- **표현 정의 (불변)**: "하락 예측"이 아니라 "위험 구간 분류". 미래 하락을 미리
  맞히는 모델을 만들지 않는다.
- **선행 조건**: 시계열 적재가 먼저. 단면 데이터로는 본 축을 다룰 수 없다.
  - NAV / 괴리율 시계열 (현재 not_integrated)
  - 변동성 지표 (현재 not_calculated)
  - 거래량 / 유동성 시계열 (현재 partial)
  - 외국인 / 기관 수급 (현재 not_collected)
  - 시장 폭 지표 (현재 not_collected)
  - 구성종목 가격 시계열 (현재 not_integrated)
  - 일별 종가 시계열 (현재 확보 — 2026-06-30 시장 시계열 Closeout STEP 완료). 요청 시작일 2014-04-07, 네이버/FDR 실측 KODEX200 최초 관측일 2014-04-09, universe 실측 normal 1007 / missing_confirm 138 / failed 0 (missing_confirm 은 기존 저장값과 명시 소스 반환값 차이 — 지시문 §8.1 자동 덮어쓰기 금지 정책 그대로). 소스: NAVER_FDR primary (`NAVER:<ticker>`) + YAHOO_FDR secondary (`YAHOO:<ticker>.KS`).
- **확인 방법**: 위 빈자리 중 하나가 채워진 뒤 (시계열 적재 STEP 완료),
  factor 후보 1~2개로 위험 구간 분류 정의가 가능한지 검증.
- **판정 기준**: 시계열 적재 → 단순 룰베이스 분류 → ML 분류 순서로 단계 검증.
  학습 / 모델은 본 질문 답이 나온 뒤 별도 결정.
- **데드라인**: 빈자리 채우기 STEP 종료 후 재평가 (시점 미확정).
- **참조**: docs/PROJECT_ORIGIN_INTENT.md §9.5 ML 방향성 2축.

### Q4. "잘 올라가는 섹터/ETF 발굴"은 어떤 단위로 작동시킬 것인가?
- **상태**: OPEN
- **배경**: 사용자의 1년 목표 핵심 — "잘 올라가는 섹터를 발굴하여 AI와 대화/판단". Step6 진행 중 "섹터 단위 발굴이 자명한 개념이 아니다"가 드러남.
- **이전 정리 (2026-04-30, Step4 해석 보강)**: 잘 올라가는 섹터/ETF 발굴은 holdings 분석 factor 와 목적은 다르지만, 완전히 별도 시스템이 아니라 같은 Momentum Engine 의 universe mode 로 다룬다 — 코드 / 핸드오프 직접 근거.
- **현재 정리 (2026-05-11)**:
  - 발굴 단위는 "잘 오르는 ETF"로 1차 시작
  - "섹터/테마 판별"은 시스템 자동화 영역 아니라 사용자가 AI 투자세션에서 직접 토론하는 영역
  - 시스템 출력은 단순 모멘텀 상위 ETF 알림까지
- **Layer A 관리 항목** (운영 첫 달 데이터로 검증할 핵심 질문 — 설계자 임의 확정 금지):
  1. **발굴 단위 세부** — "잘 오르는 ETF"를 1차 시작점으로 두되, 확정값은 아님. 운영 결과에 따라 (a) ETF 단위 유지, (b) 섹터/테마 단위 보조 추가, (c) 다른 단위로 전환 중 선택.
  2. **시간 측정 기간** — 현재 Step6 은 pykrx 1개월 수익률을 사용했으나, 1일 / 1개월 / 60일 / 120일 / 3개월 등 비교 기간은 아직 확정값이 아님. 운영 또는 백테스트 결과로 결정.
- **주의**: 위 2개 항목 모두 **"확정값 아님 / 백테스트 또는 운영 검증 필요"** 로 표시한다. 설계자가 다음 STEP 에서 임의 확정하지 않는다.
- **확인 방법**: 운영 시작 후 PUSH 3가지가 사용자 의사결정에 실제로 도움되는지
- **판정 기준**: 한 달 이상 운영 후, 받은 PUSH가 행동(매수/매도/보류)으로 연결됐는지 추적
- **데드라인**: 첫 한 달 운영 종료 시점

---

## 3. 이미 답이 나온 것 (참고용 기록)

### A-1. Phase 1 엔진 전체 구조를 살려야 하는가?
- **상태**: ANSWERED (2026-04-21)
- **답**: 아니다. ML 모듈 + OCI crontab + Telegram 연동만 살림. 나머지 새로 작성.

### A-2. MongoDB로 전환하는가?
- **상태**: REOPENED → ANSWERED (재정리) (2026-05-18)
- **이전 답 (2026-04-21)**: 아니다. JSON SSOT 유지. 향후 필요 시 SQLite/PostgreSQL 검토.
- **재오픈 사유 (2026-05-18)**: FDR + SQLite Market Data Foundation 이후 시장 시세 /
  ETF universe / 가격 이력은 SQLite 를 기준으로 관리하기로 사용자 결정이 변경되었다.
  (Market Discovery SQLite Direct Refresh STEP 의 §3.1 KS-11 문서 정합성 보정).
- **현재 답 (재정리)**: 데이터 종류별 SSOT 분리.
  - **시장 데이터** (시세 / universe / 가격 이력 / TOP N 산출 기준) → SQLite
    (`state/market/market_data.sqlite`).
  - **holdings / Run / 승인 / Telegram 흐름** → 기존 JSON SSOT 유지.
  - **MongoDB / 신규 대형 DB 도입은 여전히 금지** (PROJECT_ORIGIN_INTENT §10 #2).
  - **decision evidence 저장은 BACKLOG 유지** — 본 단계에서 SQLite 에도 별도 테이블
    신설하지 않는다.

### A-3. 친구 프로젝트를 뼈대로 삼는가?
- **상태**: ANSWERED (2026-04-21)
- **답**: 아니다. 참조(references/)로만 두고 UI 정보 배치 패턴만 학습.

### A-4. OCI 푸쉬 파이프라인이 실제로 동작하는가?
- **상태**: ANSWERED (2026-04-30)
- **기존 질문**: Q2. OCI 푸쉬 파이프라인이 실제로 동작하는가?
- **답**: 동작한다. POC1-Step3에서 실 OCI handoff와 Telegram 발송 end-to-end가 검증되었고, POC2-Step2D 종료 시점에도 사용자 디바이스 Telegram 수신까지 확인되었다.
- **남은 주의**: 이 답은 "승인 후 OCI handoff와 Telegram 수신 경로가 동작한다"는 의미다. spike_watch / holding_watch / 자연 cron / 복수 알림 경로 통합은 별도 BACKLOG 또는 별도 Step에서 검토한다.

### A-6. PC 와 OCI 의 장기 역할 분리는 어떻게 하는가?
- **상태**: ANSWERED (2026-06-20)
- **답**: **PC 분석 평면 / OCI 운영·조회 평면 분리**.
  - **PC = 분석·판단 평면**: 시장 데이터 SQLite 관리, ETF universe 갱신, 후보
    ETF 검토, ML 학습·백테스트·feature 실험, AI 투자세션, 사용자 승인,
    approved PARAM 과 published data snapshot 생성. PC 는 24시간 상시 실행을
    전제로 하지 않는다.
  - **OCI = 상시 운영·조회 평면**: latest approved PARAM 보관, 일 3회 3-PUSH
    실행, Telegram 발송. 장기 역할 — 외부 / 모바일에서 마지막 published 데이터
    와 운영 상태를 조회할 수 있는 read-only 환경으로 확장. OCI 는 ML 학습을
    수행하지 않는다.
  - **데이터 흐름**: PC SQLite 는 PC 작업용 기준 저장소로 유지. PC ML 이 OCI
    DB 를 직접 원격으로 읽지 않는다. PC 는 승인 / 발행 시점에 OCI 로 read-only
    published snapshot 을 전달한다.
- **DB 형식 미확정**: published snapshot 의 구체 형식 (versioned SQLite snapshot
  / read-only JSON artifact / 제한된 조회용 SQLite copy 등) 은 본 시점에
  확정하지 않는다. **OCI read model 구현 직전의 별도 결정**으로 남긴다. 현재
  단계에서 신규 DB 나 full DB migration 은 하지 않는다.
- **활성 Open Question 추가 없음**: 본 결정은 방향 앵커이며, 즉시 검증 트리거가
  발생하는 것이 아니다. DB 형식 결정 시점에 도달하면 그 때 별도 Q 로 승격.
- **참조**: `docs/handoff/PC_OCI_ARCHITECTURE_DIRECTION.md` (원본 결정 기록),
  `docs/PROJECT_ORIGIN_INTENT.md` §7 운영 원칙.

### A-5. "앞으로 못 나가는" 패턴이 재발할 것인가?
- **상태**: ANSWERED (2026-04-30)
- **기존 질문**: Q3. "앞으로 못 나가는" 패턴이 재발할 것인가?
- **답**: 적어도 POC2-Step2D 부터 Step3 종료까지는 KS-3 비건설적 핑퐁 패턴이 재발하지 않았다.
- **근거**: Step 단위 설계 → 검토 → 수용/기각 판단 → 개발 지시 → 구현 → 테스트 → Telegram/Push 확인 → conclusion 문서 작성까지 산출물 중심으로 진행되었다.
- **남은 주의**: 이 답은 "앞으로 영원히 막히지 않는다" 는 의미가 아니다. 새로운 단계에서 3턴 이상 산출물 없이 논쟁이 반복되면 KS-3 는 다시 발동할 수 있다.
- **추가 관찰 (2026-04-30, Step5D Cleanup 시점)**:
  POC2-Step5C 까지 진행하면서 KS-3 의 비건설적 핑퐁은 재발하지 않았다.
  그러나 단일 파일 책임 누적이라는 별도 구조 리스크가 재발 신호로 발견되었다.
  이 리스크는 Q3 재오픈이 아니라 KS-10 으로 별도 관리한다.
- **추가 관찰 (2026-05-11)**:
  - **상태**: ANSWERED (변형 패턴 주의)
  - **답**: KS-3 3턴 핑퐁은 발동 없이 진행. 다만 다른 형태의 막힘 패턴 발견.
  - **발견된 변형 (금번 발견)**: "결정의 닻이 흔들리는 패턴" — 새 데이터 없이 24시간 안에 기존 결정을 뒤집는 패턴. POC2-Step6 진행 중 발견되었으며, 운영 빈도 / 발굴 단위 / 점수체계 기준 등 시스템 방향 결정이 짧은 시간 안에 흔들리는 신호로 나타남.
  - **차단 장치**: KS-11 "의사결정 24시간 룰" (KILL_SWITCHES.md) — 새 데이터/근거 없이 24시간 안에 결정을 뒤집는 행위를 차단. 결정 변경 시 새 데이터/근거를 ASSUMPTIONS 또는 PROJECT_ORIGIN_INTENT 에 기록 후 변경한다.
  - **권고**: 분기 1회 PROJECT_ORIGIN_INTENT.md 재확인 — 결정의 닻이 흔들릴 때 PROJECT_ORIGIN_INTENT 원칙으로 복귀하는 reference 체크포인트.
  **남은 주의**: 명시적 KS 위반은 아니지만 비슷한 의도 흐름 약화는 발생 가능. 분기 1회 PROJECT_ORIGIN_INTENT 재확인 권고.

---

## 4. 장기 재검토 대상 (Phase 1 교훈)

### L-1. MDD 10% 미만 달성이 현실적 목표인가?
- **상태**: DROPPED
- **사유**: 1차 목표가 MDD 숫자가 아니라 "추천 ETF 수익률"과 "KODEX 200 초과"로 재정의됨. MDD는 2차 지표.

### L-2. GPU/큰 ML이 현재 병목을 해결하는가?
- **상태**: OPEN (ML 단계에서 재확인)
- **사유**: Phase 1에서는 Track B closeout으로 부정적 결론. 새 프로젝트 구조에서 재시도 시 다시 봐야 함.
- **첫 측정 evidence (2026-06-20, ML 축1 STEP)**: 4070 SUPER 에서 torch 단일
  선형회귀 baseline 실측 — `device_name=NVIDIA GeForce RTX 4070 SUPER`,
  `cuda_available=true`, `gpu_execution_used=true`, training 35,991 행 × 200
  epochs 학습 시간 0.256 초. 본 STEP 의 baseline 은 모델이 매우 작아 GPU 의
  필요성을 검증한다기보다 **실행 환경 자체의 GPU 사용 가능성**을 확인한
  수준이다. 큰 ML / 위험 감지 ML / 더 복잡한 모델로 가야 본 질문의 본문 ("GPU 가
  현재 병목을 해결하는가") 에 답할 수 있다. **본 evidence 만 기록하고 ANSWERED
  로 승격하지 않는다** — 향후 ML 축2 또는 더 큰 모델 시 재측정.
- **참조**: `docs/handoff/POC2_ML_RELATIVE_UPSIDE_SCORE_V0_CONCLUSION.md` §5.

### L-3. AI 토론 점수체계 검증
- **상태**: BACKLOG 이관 (2026-05-11, 이전 Q5)
- **사유**: 검증 트리거가 시스템 구조 재정렬 이후, 운영 시작 + PUSH 수신 + AI 투자세션 + 첫 매매 결정 1회 이후에야 도달한다.
- **복귀 조건**: 운영 시작 후 시스템 PUSH 를 받은 뒤, AI 투자세션을 거쳐 첫 매매 결정 또는 명시적 보류 결정 1회가 발생할 때 ASSUMPTIONS 활성 질문으로 재승격한다.
- **참조**: docs/backlog/BACKLOG.md 의 "AI 토론 점수체계 검증" 항목.
- **이력 보존**: 이전 Q5 상세 (GPT/Gemini/Claude 토론 사이클, AI 투자세션 분리 채널, Step6 첫 실전 검증 기록 — pykrx 1개월 수익률 채택) 는 BACKLOG 본문에 그대로 이관됨.

---

## 5. 이 문서 사용 규칙

1. 활성 질문 최대 3개 유지
2. 새 질문 추가 시 기존 하나 해결 또는 드롭
3. 질문 답이 나오면 섹션 3으로 이동 (삭제 금지, 기록 유지)
4. 월 1회 전체 검토
5. POC 종료 시점에 전체 재평가

---

## 6. 마지막 원칙

가정을 너무 빨리 사실로 승격시키면 실패 원인 추적이 흐려진다.
이 문서는 **질문을 질문으로 남겨두는 장치**다.

답이 안 나와도 괜찮다. "OPEN" 상태 자체가 유효한 관리다.
