# POC5-14 개발 PLAN V1 — 같은 종목 · 여러 계좌 평가값 정정

작성 2026-10-14 · 작성자: 개발자(VSCode Claude) · 수신: 설계자
근거: `docs/ai_design/POC5/POC5-13_HOLDINGS_AND_MARKET_RISK_EVIDENCE_INTEGRATION_PLAN_DECISION_2026-10-14.md` §4(Q4 (a) 별도 정정 · 조사 · PLAN 까지)
결함: `DEF-HOLDINGS-EVIDENCE-MULTIROW-VALUATION`(BACKLOG · 2026-10-14 등록)

```text
STATUS   = PLAN PASS(설계자 2026-10-15 · Q1 (a) A + C · Q2 (b) OCI 과거 발송 기록 확인 안 함 · Q3 (a) 기록만 · 판정 원문 docs/ai_design/POC5/POC5-14_HOLDINGS_EVIDENCE_MULTIROW_VALUATION_FIX_PLAN_DECISION_2026-10-15.md) → 판정 반영 §5 → 구현 → 검증자 r1 VERIFIED(2026-10-15) · 결과서 docs/ai_result/POC5/POC5-14_HOLDINGS_EVIDENCE_MULTIROW_VALUATION_FIX_RESULT.md
SCOPE    = 공유 보유 근거 builder 의 행 짝짓기 · 요약(composer)의 종목 합산 — PC 코드만 · 새 ID · DB · API 경로 0
           OCI 정기 알림(보유 브리핑 · 보유 위험 · 시장 브리핑) 경로는 이 builder 를 쓰지 않음(§1-3)
```

## 1. 조사 결과 (읽기 전용 · 저장소 · 라이브 DB 변경 0)

### 1-1. 덮어쓰는 곳과 잘못되는 값

- `app/holdings_market_evidence.py:478` `enrich_holdings(holdings, market_quotes)` 는 줄마다 맞게 계산한다(`app/holdings_enrich.py:95-136`).
- 그 다음 `:479` `enriched_by_ticker = {e.ticker: e for e in enriched_list}` 가 종목마다 **마지막 줄만** 남긴다.
- `:513` 이 보유 줄마다 이 사전을 찾고, `:553-563` 이 값을 넣는다.
- 필드별 영향

  | 필드 | 영향 | 이유 |
  |---|---|---|
  | `evaluation_amount` | 줄별로 틀림 | 수량 × 가격(`holdings_enrich.py:109`) |
  | `pnl_rate_pct` | 줄별로 틀림 | 그 줄 평단에 따라 달라짐(`:110-113`) |
  | `current_price` · `price_asof` | 틀리지 않음 | 종목 시세라 모든 줄이 같은 값 |
  | `quantity` · `avg_buy_price` · `account_group` | 틀리지 않음 | 그 줄 자신의 값 |

- 같은 builder 안의 다른 종목 키 사전(`candidates_by_ticker` · `stm_map` · NAV · 구성종목)은 원래 종목 값이라 맞다.
- **두 번째 결함 — 요약도 종목 합산이 아니다**: `app/market_summary_composer.py`
  - `select_top_holdings` 는 `:51-59` 에서 모든 줄의 `evaluation_amount` 를 더해 합계를 만든다.
  - 이어 `:61-67` 에서 종목마다 첫 줄만 남기고, `:77-87` 에서 그 한 줄의 평가 · 비중 · 손익을 종목 값으로 쓴다.
  - `summarize_holdings`(`:137-163`)도 같은 합계를 쓴다.
  - 그래서 builder 만 고치면, 여러 줄 종목은 첫 계좌 값만 보인다(§1-4).
  - `:46` 주석('evidence 는 이미 종목당 한 줄')은 사실이 아니다.
  - `coverage.need_check` 는 영향이 없다. 값이 있는지만 보는데, 시세가 종목 단위라 줄마다 같다.

### 1-2. 기존 행 구분

- `enrich_holdings` 는 입력 한 줄에 출력 한 줄이다. 순서와 길이가 같고, 시세가 없는 줄도 빠지지 않는다(`holdings_enrich.py:95` · `:142-187`).
- 출력의 `source_index` 는 원래 보유 배열의 위치다(`:31-34` · `:58` · `:185` · `/holdings/enriched` 에도 나감).
- `Holding` 모델에는 ID 가 없다(`app/holdings.py:99-105`). (종목 · 계좌 · 평단) 셋은 늘 보장되는 키가 아니다(`unique_triple` 이 켜졌을 때만).
- 결론: 위치(= `source_index`)가 늘 존재하는 유일한 구분이다. builder 는 같은 목록을 enrich 에 넣고 같은 순서로 돌므로 위치로 짝지을 수 있다. **새 ID · DB 구조는 필요 없다.**

### 1-3. 이 값이 쓰이는 곳 — 공유 경로 존재 vs 실제 본문에 실림

| 경로 | 공유 builder 사용 | 잘못된 값이 실제 출력에 실림 |
|---|---|---|
| PC `GET /holdings/market-evidence/latest`(`app/api_holdings_market_evidence.py:237-250`) | 예 | 응답 값은 틀림. 화면에는 안 보임 — 「오늘의 투자 점검」 최대 3개 비중 · 손익은 이미 종목 합산 값으로 바꿔 보임(`JudgmentQueueSection.tsx:184-191`). 「확인 근거」 · 「ETF 비교하기」 · 「요즘 잘 오르는 ETF」는 정상 보유 평가 응답을 씀 |
| PC 보유 초안 메시지(`POST /runs/generate-from-holdings` → `app/draft.py:189-195` · `:282` → `app/draft_message.py:381-388` '비중 · 손익') | 예 | **본문에 실림(코드 · 재현으로 확인)** — 「개발·실험용」 수동 버튼 · 승인 뒤 LEGACY OCI 수신함 경로로만 발송 가능 |
| PC 3-PUSH 패키지 내보내기(`app/three_push_package_exporter.py:87`) | 예(시세 없음) | 실리지 않음 — 평가값이 모두 없어 '자료 확인 필요' |
| OCI 정기 보유 브리핑 · 보유 위험 · 시장 브리핑(`runner_dispatch.py:65-116` · `select_holdings` 가 종목 합산 · 수량 가중 평단) | 아니오 | **실리지 않음(코드로 확인)** |
| 예전 런타임 근거 줄(`app/runtime_evidence/holdings_evidence.py:186-195` '평가수익률 · 평가금액') | 예 | 지금 발송 경로에서는 닿지 않음(정기 3종은 이 경로를 건너뜀 · `runner_evidence.py:15-20,47-48`) |
| 결정 초안 미리보기(`app/api_decision_draft_preview.py:54-137`) · 원장 · AI 세션 | 미리보기는 예(단기 흐름 등 근거); 미리보기의 평가 · 비중 · 손익은 정상 enrich 결과의 자체 종목 합산 | 평가 · 비중 · 손익 영향 없음(검증자 호출처 표기 정정 · 2026-10-15) |

- **실제로 발송된 적이 있는지**
  - 이 PC 의 실행 기록 `state/runs` 는 156건(2026-08-12 ~ 09-21)이다. 모두 `FAILED` 이고 메시지 본문이 있는 기록은 0건이다(읽기 전용 확인 2026-10-14).
  - `docs/PROGRAM_TRUTH.md` 에는 이 수신함 경로가 LEGACY 로 적혀 있다(OCI cron 에 `daily_ops` 없음 · 수신함 0 · 2026-10-12 기록).
  - OCI 수신함 · 발송 기록은 이번에 다시 보지 않았다. 그래서 실제 발송 여부는 **확인 안 함**이다.

### 1-4. 재현 (두 계좌 fixture · 임시 DB · 저장소 밖 스크립트)

- 조건: 069500 시세 35,000
  - 0번 줄: 일반 10주 @ 30,000
  - 1번 줄: ISA 30주 @ 32,000
  - 2번 줄: 367760(시세 10,000) 일반 20주 @ 9,000

| | builder 결과 | 정상 |
|---|---|---|
| 0번 줄 평가 · 손익 | 1,050,000 · +9.38%(1번 줄 값 복사) | 350,000 · +16.67% |
| 요약 합계 | 2,300,000 | 1,600,000 |
| 최대 3개 069500 | 1,050,000 · 비중 45.7% · +9.38% | 1,400,000 · 87.5% · +11.11% |
| 최대 3개 367760(한 줄 종목) | 비중 8.7% | 12.5% |

- 0 · 1번 줄 순서를 바꾸면 결과가 달라진다(069500 350,000 · 38.9% · +16.67% / 367760 22.2%). 즉 보유 파일 줄 순서에 따라 틀린 값이 바뀐다.
- builder 만 고친 경우(위치 짝짓기 모의): 줄별 값과 합계는 맞는다. 하지만 최대 3개 069500 은 첫 줄 값(350,000 · 21.9% · +16.67%)이다. 요약도 고쳐야 87.5% · +11.11% 가 된다.
- PC 응답 사본(`app/pc_price_basis.py:177,218-220`)은 같은 잘못된 줄로 요약을 다시 만든다. 그래서 같은 결과다.
- 초안 메시지 실제 문구(`build_message_text` 실행): `비중 45.7% / 손익 +9.38%`(069500) · `비중 8.7%`(367760)
- 재현 스크립트(저장소 밖): `/private/tmp/poc514_repro/repro_multirow_valuation.py` · `/private/tmp/poc514_mapping/repro.py` · `fix_sim.py` · `/private/tmp/poc514_taskB/repro.py`

### 1-5. 지금 실제 보유에서의 크기 (2026-10-14 기록 응답 · 읽기 전용)

- 069500 세 줄
  - 정상 평가: 284,415 / 1,422,075 / 189,610원
  - 근거 응답: 세 줄 모두 189,610원
- 367760 두 줄
  - 정상 평가: 160,725 / 214,300원
  - 근거 응답: 두 줄 모두 214,300원
- 요약 합계: 12,861,060원(정상 14,134,755원 · 1,273,695원 적음)
- 지금 최대 3개(0193T0 · 000660 · 395160)는 모두 한 줄 종목이라 손익은 맞다. 그러나 비중은 합계가 틀려 부풀려진다.

  | 종목 | 응답 비중 | 정상 비중 |
  |---|---|---|
  | 0193T0 | 0.5% | 0.4% |
  | 000660 | 11.1% | 10.1% |
  | 395160 | 4.9% | 4.5% |

- 화면은 정상 값으로 바꿔 보이므로 영향이 없다. 초안 메시지를 만들면 이 값이 실린다.

## 2. 수정안 (권장: A + C)

- **A. builder 행 짝짓기**(`app/holdings_market_evidence.py:478-479 · 513`)
  - 종목 사전 대신 `zip(holdings, enriched_list)` 로 같은 위치끼리 짝짓는다.
  - 길이 · `source_index == i` 가 어긋나면 실패하게 둔다(조용히 대체하지 않음).
  - 효과: 줄별 평가 · 손익, 요약 합계, 예전 런타임 근거 줄이 맞아진다.
- **C. 요약의 종목 합산**(`app/market_summary_composer.py :: select_top_holdings` · `summarize_holdings`)
  - 종목마다 평가 합을 쓴다(한 줄이라도 없으면 없음).
  - 손익 = (평가 합 − 매입 합) ÷ 매입 합 이고, 매입 = 수량 × 평단이다.
  - 비중 = 평가 합 ÷ 전체 합이다.
  - 화면의 `aggregateHoldingsByTicker` · 결정 초안 미리보기의 `_aggregate_enriched_by_ticker` 와 같은 규칙이다.
  - 선정 · 순서(5일 낮은 순 · 최대 3개) · `need_check` · 반올림 자릿수는 그대로다.
- **함께 고칠 설명**(사실과 다른 문장)
  - `JudgmentQueueSection.tsx:186` · `TopHoldingsAggregate.test.tsx:2,66,108` 의 '첫 계좌 값'
  - `market_summary_composer.py:46` 주석
  - `app/decision_draft_preview_service.py:90` 설명(→ §5 정정: 처음에 파일 이름을 `api_decision_draft_preview.py` 로 잘못 적었음)
  - `docs/PROGRAM_TRUTH.md` 해당 줄
- **바뀌지 않는 것**
  - OCI 정기 알림 3종(이 builder 를 쓰지 않음)
  - 결정 초안 미리보기 · 원장 · 저장된 초안 · 보유 저장
  - 화면 표시값(이미 종목 합산 값을 씀)
- **배포**: PC 코드다. OCI 정기 경로는 이 함수를 부르지 않으므로 OCI pull 은 기록용이다(급하지 않음).

## 3. 시험

- 두 계좌 fixture(수량 · 평단 다름 · 줄 순서 두 가지)
  - 줄별 평가 · 손익 = `enrich_holdings` 값
  - 요약 합계 = 줄별 합
  - 최대 3개 여러 줄 종목 = 종목 합산(87.5% · +11.11%)
  - 한 줄 종목 비중이 정상(12.5%)
  - 줄 순서를 바꿔도 같은 결과
- 시세 없는 종목(모든 줄 없음) → 평가 · 비중 · 손익 없음 · `need_check` 그대로
- 길이 · 위치가 어긋난 입력 → 실패(대체값 없음)
- 선정 · 순서 · 최대 3개 · `coverage` 불변(기존 시험 그대로 통과)
- 초안 메시지 문구 · PC 응답 사본 요약이 종목 합산 값
- OCI 정기 보유 브리핑 출력 불변(같은 입력 결과 비교)
- 필수 검사(black · flake8 · py_compile · pytest 관련 + 전체 1회 · 변이)

## 4. 질문 (설계자 판단 · 권장은 (a))

- **Q1 — 범위**
  - (a) A + C 둘 다 고친다.
  - (b) A 만 고친다. 그러면 초안 메시지의 여러 줄 종목은 첫 계좌 값이 남는다.
- **Q2 — 발송 여부 확인**: 실제로 잘못된 값이 Telegram 에 나간 적이 있는지 확인할까.
  - (a) OCI 수신함 · 발송 기록을 읽기 전용으로 한 번 확인한다(`ssh oci-krx` 읽기 명령 · 명령별 승인).
  - (b) 확인하지 않는다(LEGACY 경로 · PC 실행 기록에 본문 0건).
- **Q3 — 범위 밖 관찰을 기록만 할까**: 모두 (a) 기록만 / (b) 이번에 포함
  - `privacy_detector._hints_by_ticker`(`:106-116`)도 종목마다 마지막 줄만 본다. 숫자에 쉼표가 있으면 찾지 못한다. 진단용이고 지금 발송 경로에서는 닿지 않는다. (→ §5 정정: 쉼표 숫자 탐지 한계는 정기 보유 브리핑 검사 경로에 있음)
  - 근거 응답 `summary.total_holdings_count` 는 줄 수(32)이고 화면 종목 수는 29다.
  - 결정 초안 미리보기가 builder 에 없는 키(`data_quality` · `overlap`)를 읽어 늘 비어 있다(`api_decision_draft_preview.py:135-136`).

## 5. 설계자 판정 반영 (2026-10-15 · PASS)

- **Q1 (a) A + C**
  - A: 보유 줄과 enrich 결과를 같은 위치로 짝짓는다. 길이 · `source_index` 가 어긋나면 실패하고, 종목 키 · 마지막 줄로 대체하지 않는다. 새 ID · 복합 키 · DB 는 만들지 않는다.
  - C: 요약이 종목 합산을 쓴다.
    - 평가 = 줄 평가금액 합
    - 매입 = Σ 수량 × 평단
    - 손익률 = (평가 − 매입) ÷ 매입 × 100. 금액을 합친 뒤 계산하고 표시할 때 반올림한다. 줄 손익률 평균 · 반올림 역산은 하지 않는다.
    - 비중 = 평가 ÷ 기존 전체 합
    - 일부 줄 평가가 없으면 평가 · 비중 · 손익은 없음이다. 매입 계산 불가 · 0 이면 손익률은 없음이다.
    - 전체 합계 결측 처리 · coverage · need_check 규칙과 선정 · 5일 정렬 · 최대 3개 · 동률 · 자릿수는 그대로다.
  - PC 사본 요약 · 수동 초안도 같은 요약을 쓴다. 사실과 다른 주석 · 시험 설명 · PROGRAM_TRUTH 문장을 고친다.
- **구현 중 판단 2건**
  - (1) 한 줄 종목은 그 줄의 평가 · 손익률을 그대로 쓴다(다시 계산하지 않음).
    - 이유: 기존 손익률은 반올림 전 평가로 계산된다. 합산 공식으로 다시 계산하면 아주 드물게 소수 둘째 자리가 갈릴 수 있다. 판정 §6 '단일 계좌 정상값 불변'을 지키기 위함이다.
  - (2) `need_check` 판정 규칙은 그대로 두고, 판정 입력(평가 · 손익 · 비중)을 종목 합산 값으로 바꾼다.
    - 이유: 화면 `computeNeedCheck` 와 같은 입력으로 맞춘다. 지금 구조에서는 시세가 종목 단위라 결과가 달라지는 실제 경우는 없다.
- **정정 2건**(검토 지적)
  - §2 설명 정정 파일은 `app/decision_draft_preview_service.py:90` 이다.
  - §4 Q3 의 privacy_detector 서술: 쉼표 숫자 탐지 한계는 정기 보유 브리핑마다 도는 개인정보 검사 경로(`holdings_selection_flow.py:315` · `:344`)에 있다. 지금 본문에는 금액 숫자가 없어 영향은 없다. '닿지 않는다'는 `_hints_by_ticker` 부분에만 맞다.
- **Q2 (b)**: OCI 과거 발송 기록은 확인하지 않는다. 결과서에 '확인하지 않음 — 수정 조건에서 제외'로 적는다.
- **Q3 (a)**: 범위 밖 관찰 3건은 BACKLOG 에 기록만 한다. `total_holdings_count` 의 의미(보유 줄 수)는 PROGRAM_TRUTH 에 적는다.
- 운영: PUSH 중단 · 시험 발송 · OCI 쓰기 · 과거 기록 재작성은 하지 않는다. PC 코드 반영으로 끝낸다(OCI pull · 다음 거래일 확인은 조건 아님).
