# POC5-09 개발 결과서 — STORED_VOLUME_EVIDENCE (저장 거래량 확인 근거 + PC 가격 흐름 기준일 정정)

작성 2026-10-13 · 작성자: 개발자(VSCode Claude) · 수신: 검증자(Codex)

```text
STATUS            = IMPLEMENTED_VERIFIED_CLOSED(2026-10-13) — 검증자 r1 REJECTED(2026-10-13 · 이력 부족과 기준일 불일치가 겹치는 경로에서 날짜 사유 누락 · 위험 LOW) → 정정(§6-3) → **검증자 r2 VERIFIED(2026-10-13 · 위험 NONE · 범위 폭주 NONE · 격리 사본 backend 46 · frontend 444 · 재현 API · 화면 각 1 · §8 관련 시험 합계는 검증자가 직접 정정 = §6-3 끝)** → 실화면 통과(2026-10-13 · 사용자 새로고침 확인) → 커밋 · push(사용자 승인 2026-10-13 · 커밋 번호 = `git log`) → 종료(§10)
STEP_ID           = POC5-09 저장 거래량 확인 근거 (+ 판정 §9-4 PC 가격 흐름 기준일 정정 · 설계 §10-2 보충 2건)
DESIGN            = docs/ai_design/POC5/POC5-09_STORED_VOLUME_EVIDENCE_DESIGN_V1.md (V1 · §9 PLAN 판정 CONDITIONAL_PASS · §10 검증 요청 보충 · POC5-10 판정 · 끝에 전달문 원문 3건)
PLAN              = docs/ai_plan/POC5/POC5-09_STORED_VOLUME_EVIDENCE_PLAN_V1.md (V1 · 판정 보충 = §7 · 검증 요청 보충 반영 = §8 · 재제출 없음)
BASE_COMMIT       = c5613b6c
SCOPE             = backend 새 모듈 2 · 읽기 함수 1 · API 라우트 2곳 선택 필드 / frontend 화면 2곳 + 공용 표시 1 + 문구 helper 2 · 최대 3개 비중 · 손익 합산 · 두 안내 카드 문구 / 시험 / 문서. 수집 · DB 스키마 · 의존성 · PUSH · 원장 · OCI 변경 0
CHECKS            = black · flake8 · py_compile 통과 · backend 새 시험 41 · backend 전체 회귀 = §8 · tsc 0 · eslint 0 · vitest 37파일 444 passed(직전 423 → +21) · 변이 backend 17/17 · frontend 14/14 검출
MOCKUP            = 실제 값(2026-10-13 PC 응답) · 실제 CSS · 1440 / 1000 폭 캡처 정렬 확인 → 사용자 확인 2026-10-13('이대로 구현' · 카드 항목 자리 유지)
REVIEW            = 독립 검토 1회(읽기 전용 · 2026-10-13) — HIGH 0 · MEDIUM 1 · LOW 8 → 모두 반영(§6-2)
USER_CHECK        = 실화면 통과(2026-10-13 · 새로고침 · 재기동 · OCI pull 없음)
```

## 0. 요약

- **PC 가격 흐름 기준일 정정(판정 §9-4 · 먼저 반영)**: 「확인 근거」 · 「오늘의 투자 점검」이 쓰는 `GET /holdings/market-evidence/latest` 는 공유 builder 결과의 **사본**을 정정해 돌려준다(`app/pc_price_basis.py`).
  - **날짜와 값은 같은 읽기에서**(설계 §10-2-1)
    - 종목 · KODEX200 의 최근 저장 가격 21행을 한 번 읽는다.
    - 그 행에서 날짜(기준일 · 5 · 20일 비교 기간 시작)와 5 · 10 · 20일 변화 · KODEX200 대비(builder 와 같은 산식 `_window_return_pct`)를 함께 만든다.
    - builder 가 앞서 따로 읽어 계산한 값에 나중에 읽은 날짜를 붙이지 않는다.
  - 종목 기준일 ≠ PC 비교 기준일(KODEX200 최신 저장 가격 날짜) → 5 · 10 · 20일 변화와 KODEX200 대비를 비우고 status 를 `unavailable` 로 둔다.
  - 기준일은 같고 비교 기간 시작만 다르면 → 그 KODEX200 대비만 비운다. status 는 `ok` 그대로라 자기 5일 값으로 최대 3개 후보에 남는다.
  - 최대 3개 · 자료 확인 필요 건수는 정정된 사본으로 기존 `summarize_holdings` 를 다시 불러 만든다.
  - 공유 builder · PUSH · 원장 · 가격 DB 는 그대로다.
  - 실데이터(2026-10-13): 개별주 3종목(삼성전자 · SK하이닉스 · 삼성SDI · 2026-08-12)이 빠졌다. 최대 3개 = KODEX SK하이닉스단일종목레버리지 · HANARO 미국AI메모리반도체TOP4+ · KODEX 200 · 자료 확인 필요 3건.
- **최대 3개 비중 · 손익 = 종목 합산(설계 §10-2-2)**: 「확인 근거」와 같은 `aggregateHoldingsByTicker` 로 이미 받은 보유 조회를 묶어 표시한다. 예전에는 backend 요약의 같은 종목 첫 계좌 값(KODEX 200: 1.5% · -2.82%)이 나왔다.
- **화면**
  - 「확인 근거」: 목록 위 가격 흐름 기준 줄 · 기준일이 다른 행의 세 칸 '—' · 상세 맨 위 실제 날짜 사유 · '가격 흐름 기준' 줄 · 종목 저장 거래량 4칸.
  - 「오늘의 투자 점검」: 최대 3개 설명에 PC 저장 가격 기준일 · 뺀 보유 줄 · 비중 · 손익 합산 · KOSPI 카드 'KODEX200 거래량' 2 × 2 · 두 안내 카드 문구(판정 §9-3).
- **저장 거래량**
  - 기준일 D = 최신 저장 가격 날짜. 직전 20개 저장일 평균(D 제외 · 20개 모두 유효할 때만) · 평균 대비 배수 · 단위 주.
  - 배수 사유 순서는 판정 §9-2. source 는 같은 읽기의 D 행 값(판정 §9-5).
- **수집 원인(PC 갱신 대상에 보유 개별주)** 은 `POC5-10` 이다(PLAN PASS · 설계 §10-4 · §10-5 · 이 결과서 범위 밖).

## 1. 처리한 요구사항

| 요구 | 상태 | 근거 |
|---|---|---|
| §9-4-1 기준일을 실제 계산 이력에서 · PC 비교 기준일 = KODEX200 저장 기준 · 날짜 고정 없음 | DONE | `app/pc_price_basis.py` — 종목 · KODEX200 각각 `fetch_recent_price_rows(limit=21)`(`fetch_price_history` 와 같은 행 조건) · i번째 행 = `series[-(i+1)]` · 오늘 · 기대 거래일 비교 없음 |
| §10-2-1 계산값과 날짜가 같은 입력에서 | DONE | 같은 읽기로 날짜 · 값(`_flow_from_rows` · 산식 `_window_return_pct` 재사용) · 단기 흐름 메모 한 줄도 그 값에 맞춤(`_replace_short_term_note`) · 재현 시험 `test_values_and_dates_come_from_the_same_read` |
| §9-4-2 「확인 근거」 다른 기준일 행 '—' · 자료 확인 필요 · 상세 실제 날짜 사유 · KODEX200 대비 기간 일치일 때만 | DONE | backend 사본 정규화(`_normalize_item` · 판정 순서 = 기준일 비교 → 이력 길이 → 비교 기간 · 이력이 짧아도 기준일이 다르면 기준일 불일치 — 검증자 r1 정정 §6-3) · 화면 `stale()` · `evidenceGuidance(row, basis)` · `lib/priceBasis.ts` · 보유 · 시세 · NAV · 차트 유지 |
| §9-4-3 최대 3개 = 날짜 맞는 후보만 기존 선정 함수로 · 다음 종목으로 채움 · 뺀 종목은 자료 확인 사유 | DONE | `apply_pc_price_basis` → `market_summary_composer.summarize_holdings`(→ `select_top_holdings` 본문 불변) · `JudgmentQueueSection` 뺀 보유 줄 |
| §10-2-2 최대 3개 비중 · 손익 = 종목 합산(「확인 근거」 규칙 · 함수 재사용) | DONE | `today/JudgmentQueueSection.tsx` → `holdings_compare/helpers.ts :: aggregateHoldingsByTicker` · 선정 · 순서 · 5일 · 20일 · KODEX200 대비는 backend 요약 그대로 · 새 조회 0 · 시험 `today/TopHoldingsAggregate.test.tsx`(이익 / 손실 계좌 두 화면 일치) |
| §9-4-4 PC 전용 경계 · 공유 builder · OCI PUSH 선정 · 원장 · DB 불변 | DONE | 라우트에서 builder 호출 뒤 사본 처리 · 시험이 builder 반환에 08-12 값 · 기존 선정이 남아 있고, 경합이 없으면 응답 값 = builder 값임을 확인(§6-1) |
| §9-2 배수 사유 우선순위 · 평균 칸 N/20 · 가격 행 없음 한 줄 · 0 유효 | DONE | `stored_volume_evidence.compute_stored_volume_evidence` · `lib/storedVolume.volumeCells` |
| §9-3 두 카드 문구 · 배지 | DONE | `InDevelopmentSection.tsx`('저장 거래량 확인 근거' · '일부 제공' · 판정 설명) · `KospiDetailSection.tsx`('KOSPI 지수 거래량' · '미제공' · 판정 설명) · 항목 자리 유지(사용자 결정) |
| §9-5 source 조회 명시 · 공유 함수 반환 계약 불변 | DONE | 새 읽기 `market_data_store.fetch_recent_price_rows` 가 `source` 를 같이 읽는다 · 기존 `fetch_price_history` · `fetch_price_volume_history` 변경 0 |
| 설계 §3 거래량 정의 · §4 두 API 선택 필드 · 새 경로 0 · §5 표시(4칸 같은 폭 · 좁으면 2 × 2 · KODEX200 은 ETF 한 종목) | DONE | `StoredVolumeBlock.tsx` · 기존 `.wb-detail-grid` · 거래량 도움말 |
| 설계 §5 P-10 낡은 '거래량 자료 미저장' 문구 정정 | DONE | 두 카드 + 주석 2곳(`TodayInvestmentCheckView.tsx` · `today/KospiChart.tsx`) |
| 설계 §7 · 판정 §9-5 · §10-3 시험 | DONE | §8 |
| 설계 §7 기록(BACKLOG · STATE · PROGRAM_TRUTH · 통합지도) | DONE | P-10 '제공분 해소' · KOSPI 전체 거래량 · 종합 위험 분류는 미완료로 · `DEF-PRICE-EQUITY-REFRESH` 재개 |
| 판정 §9-6 수집 원인 보완 | POC5-10 | PLAN PASS(설계 §10-4) · 판정 반영 = POC5-10 PLAN §6 · 구현은 09 검증 뒤(§5-1) |

## 2. 변경된 파일 목록

backend
- `app/stored_volume_evidence.py`: 신규 — 거래량 계산 · `StoredVolumeEvidence` 응답 모델 · 한 종목 읽기
- `app/pc_price_basis.py`: 신규 — PC 화면용 사본 정정(같은 읽기로 날짜 · 값) · 최대 3개 재계산
- `app/market_data_store.py`: 수정 — 읽기 함수 `fetch_recent_price_rows` 추가(기존 함수 변경 0)
- `app/api_holdings_market_evidence.py`: 수정 — 모델 `PriceDates` · `PriceBasis` · `PriceBasisMismatch` · 항목 `price_dates` · `stored_volume` · 최상위 `price_basis` · 라우트에서 사본 처리
- `app/api_market_topn.py` · `app/api_market_topn_models.py`: 수정 — 최상위 `kodex200_stored_volume`
- `tests/test_stored_volume_evidence.py` · `tests/test_pc_price_basis.py`: 신규

frontend
- `frontend/app/components/StoredVolumeBlock.tsx` · `frontend/lib/storedVolume.ts` · `frontend/lib/priceBasis.ts`: 신규
- `frontend/app/components/HoldingsRiskEvidenceSection.tsx` · `holdings_risk_evidence/helpers.ts`: 수정
- `frontend/app/components/today/KospiHeadline.tsx` · `JudgmentQueueSection.tsx`(뺀 보유 줄 · 비중 · 손익 합산) · `InDevelopmentSection.tsx` · `KospiDetailSection.tsx` · `KospiChart.tsx`(주석) · `TodayInvestmentCheckView.tsx`(주석): 수정
- `frontend/lib/api/market.ts` · `frontend/lib/api/holdings.ts`: 수정(선택 필드 타입)
- `frontend/app/globals.css`: 수정(거래량 칸 9줄 추가 · 네 칸은 기존 `.wb-detail-grid` 재사용)
- 시험
  - 신규: `frontend/lib/storedVolume.test.ts` · `frontend/lib/priceBasis.test.ts` · `frontend/app/components/today/StoredVolumeAndPriceBasis.test.tsx` · `frontend/app/components/today/TopHoldingsAggregate.test.tsx`
  - 수정: `HoldingsRiskEvidenceSection.test.tsx` · `holdings_risk_evidence/helpers.test.ts` · `TodayInvestmentCheckView.test.tsx`

문서
- 설계서 §9 · §10(판정 원문) · PLAN(§7 · §8) · 이 결과서(신규) · `docs/PROGRAM_TRUTH.md` · `docs/backlog/BACKLOG.md` · `docs/STATE_LATEST.md` · 통합지도 `docs/ai_design/POC3/POC3-00_PC_JUDGMENT_UI_INTEGRATED_IMPLEMENTATION_MAP_V2.md`(P-10)
- `docs/ai_plan/POC5/POC5-10_PC_HOLDINGS_EQUITY_PRICE_REFRESH_PLAN_V1.md`: 신규 — POC5-10 PLAN(PASS · 판정 반영 §6 · 코드 변경 0 · 이번 검증 대상 아님)

## 3. 신규 추가된 의존성

없음.

## 4. 지시문 외 변경

1. **`summary.evidence_unavailable_count` 재계산**(사본 · builder 와 같은 규칙: 수익률 · 단기 흐름 둘 다 unavailable)
   - 정정으로 단기 흐름이 unavailable 이 된 종목이 「ETF 비교하기」 · 대시보드의 '보유 Evidence 확인 필요 N건'과 「오늘의 투자 점검」 정비 큐에 같이 잡히게 했다.
   - 실데이터는 0 → 3이다. 정비 큐 문구는 '내가 가진 ETF와 시장 비교 자료가 오래되었습니다 (3건)'(기존 문구 그대로)이다.
2. **기간 불일치(`window_mismatch`)는 status `ok` 유지**(KODEX200 대비만 비움)
   - 기준일이 같아 자기 5 · 10 · 20일 값은 유효하므로 기존 `select_top_holdings`(status ok · 5일 값 있음) 후보에 남는다(판정 §9-4-3 · 설계 §10-3).
   - 처음 `partial` 로 두었다가 독립 검토(§6-2 M1)로 고쳤다. 지금 실데이터에는 이런 종목이 0이다.
3. **'개발 중인 판단 기능' 배지 양식 판정식**: '개발 중'만 진한 배지였던 식을 '이번 단계 미도입'만 옅은 배지로 바꿨다. 새 배지 '일부 제공'은 진한 배지다(판정 '기존 배지 양식 재사용'). 기존 두 배지의 양식은 그대로다.
4. **상세 '가격 흐름 기준' 줄을 모든 종목에 표시**(판정 §9-4-1 '종목별 실제 계산 기준일 표시'의 위치) · 목업 확인.
5. 「확인 근거」 머리 주석 · `holdings_risk_evidence/helpers.ts` 의 `flow_unavailable` 주석 · `TodayInvestmentCheckView.tsx` 화면 계약 주석(거래량 = 개발 중 → 지금 동작)을 고쳤다.
6. **새 읽기 함수는 거래량을 저장값 그대로 돌려준다**(int 변환 없음): 저장값이 무한대여도 화면 API 가 오류(500)를 내지 않고, 계산에서 '유효하지 않음'으로 센다. 응답 `volume` 형은 정수 · 실수 모두 허용(보통 정수).
7. **'과거 저장 자료' 표시는 날짜 방향을 본다**: 거래량 기준일이 PC 비교 기준일보다 이르면 '과거 저장 자료 · PC 비교 기준일은 D', 늦으면 'PC 비교 기준일(D)보다 늦은 날짜의 자료'.
8. **PC 사본의 단기 흐름 메모 한 줄을 사본 값에 맞춤**(§10-2-1 의 부수): builder 가 만든 단기 흐름 줄('20거래일 KODEX200 대비 단기 흐름 차이 …%p.' / '단기 흐름은 데이터 부족으로 확인할 수 없습니다.')만 같은 위치에서 바꾼다. 기준일 불일치 · 비운 대비값이면 지운다. 같은 규칙 · 문구를 `_short_term_note` 에 둔다(builder 와 결합 — §6-2).

## 5. 알려진 한계 / 미완성

1. **수집 원인은 그대로 열림**: PC 수동 갱신은 여전히 보유 개별주를 받지 않는다. 3종목은 갱신해도 계속 '자료 확인 필요'로 빠진다(오용은 막힘). = `POC5-10`(PLAN PASS). 구현은 09 검증 대상 소스를 바꾸지 않도록 09 판정 뒤에 한다(설계 §10-6).
2. 정비 큐의 '내가 가진 ETF와 시장 비교 자료가 오래되었습니다 (3건)' 버튼은 '시장 자료 업데이트로'다. 1의 보완 전에는 눌러도 3건이 남는다.
3. 거래량은 2026-02-19 이후 FDR 행에만 값이 있다(그 전 `NAVER_FDR` 행은 모두 비어 있음). 새로 상장했거나 이력이 짧은 종목은 '자료 부족 (N/20)'이 된다.
4. **「요즘 잘 오르는 ETF」 보유 비교(`HoldingsCompareView`)도 같은 응답을 쓴다**: 기준일이 다른 3종목의 단기 흐름 · KODEX200 대비가 '자료 확인 필요'로 보이고 날짜 사유는 없다(날짜 사유 표시는 판정 범위인 「확인 근거」에만). 기간 불일치 종목은 status ok 라 자기 5 · 10 · 20일 값이 그대로 보이고 비운 대비값만 비어 있다.
5. **거래량 칸과 단기 흐름은 같은 읽기지만, builder 가 쓰는 다른 자료(Market Discovery 후보 · 구성종목 · NAV)는 builder 때 읽은 값이다.** 그 값들은 날짜 비교 대상이 아니다.

## 6. 다음 검증자(Codex)에게 알릴 점

1. **공유 경로 불변 · 같은 읽기**(`tests/test_pc_price_basis.py`)
   - `test_endpoint_applies_price_basis_and_keeps_shared_builder`: 같은 tmp DB 에서 builder 를 직접 불러 확인한다.
     - 08-12 종목은 builder 결과에 status ok · 5일 -20% · 최대 3개 1위로 남는다(PUSH · 초안 경로는 예전 그대로).
     - 기준일이 같은 종목은 응답 단기 흐름 · 메모 = builder 값이다(두 읽기 사이 자료가 그대로일 때).
   - `test_values_and_dates_come_from_the_same_read`: builder 가 10-08 자료로 -10% 를 낸 뒤 10-09 가 저장된 읽기로 처리하면, 응답 값은 10-09 읽기의 +5% · 날짜 10-09 · 메모도 +5% 로 바뀐다(정정 전에는 -10% 에 10-09 가 붙어 ok 였다 — 재현 확인).
   - 순수 시험은 정정 전후 입력이 같음(`ev == before`)을 확인한다.
2. **builder 와 결합된 곳**
   - 단기 흐름 메모 두 문구와 규칙(`_short_term_note` · `FLOW_SHORT_NOTE`)
   - 산식 `short_term_momentum._window_return_pct`(밑줄 이름 재사용 · 새 산식 없음)
   - builder 문구가 바뀌면 메모 교체가 조용히 '추가'로 바뀐다 — 시험이 실제 문구로 확인한다.
3. **최대 3개 비중 · 손익**
   - backend `judgment_summary.top_holdings` 의 비중 · 손익(첫 계좌 값)을 화면이 쓰지 않는다. POC3-06 §6.1 '프론트 재계산 금지'의 예외다(이 두 칸만 · 설계 §10-2-2 승인).
   - 선정 · 순서 · 5일 · 20일 · KODEX200 대비는 backend 요약 그대로다. PUSH 공유 선정은 바뀌지 않는다.
4. **캐시(설계 §10-3)**
   - 이번 변이는 `PYTHONDONTWRITEBYTECODE=1` 로 돌리고, 복원 뒤 `os.utime` 으로 수정 시각을 올렸다.
   - 복원 뒤 `app/__pycache__/pc_price_basis.cpython-312.pyc` 머리(원본 수정 시각 · 크기)와 바이트코드가 지금 원본 컴파일 결과와 같음을 확인했다.
   - 검증 때는 `PYTHONDONTWRITEBYTECODE=1` 또는 `__pycache__` 삭제 뒤 시험을 권한다.
5. `flow_unavailable` 은 builder(자료 부족 · 메모 있음)와 사본 정정(기준일 불일치 · 메모 없음) 두 곳에서 생긴다. 안내의 '사유 있음' 판정은 기준일 사유(`price_dates`)를 먼저 본다.
6. 판정 §9-4-2 '—'는 기준일 불일치 행에만 적용했다. 다른 이유로 값이 없는 행은 예전처럼 '자료 확인 필요' 글자다.

### 6-3. 검증자 r1 REJECTED 정정 (2026-10-13)

- **지적(재현됨)**: 종목 저장 가격이 08-12 · 20행, KODEX200 이 10-08 · 21행 이상이면 응답이 `comparison="unavailable"` · `date_mismatch=[]` 였다.
  - 원인: `_normalize_item` 이 이력 부족(21행 미만)을 기준일 비교보다 먼저 판정했다.
  - 결과: 날짜 불일치 사유 · 뺀 보유 목록 · 세 칸 '—' 가 빠졌다(오래된 값은 최대 3개에서 빠져 있었음 · 위험 LOW).
- **정정**: 판정 순서를 **기준일 비교 → 이력 길이 → 비교 기간**으로 바꿨다(`app/pc_price_basis.py :: _normalize_item` 의 상태 표 docstring).
  - 종목 · KODEX200 에 저장 가격이 1행 이상 있고 기준일이 다르면, 이력이 짧아도 `date_mismatch` 다.
  - 저장 가격이 없거나(종목 0행 · KODEX200 0행) 기준일이 같고 이력이 짧을 때만 `unavailable` 이다.
- **같은 부류 전수**: 종목 행 수(0 · 짧음 · 21) × KODEX200 행 수(0 · 짧음 · 21) × 기준일(같음 · 다름) × 비교 기간(같음 · 다름)의 10가지 조합을 `test_state_matrix_date_before_history` 로 시험한다. 확인 항목은 판정 · 상태 · 값 · 메모 · 뺀 목록 · 최대 3개 · 입력 불변이다.
  - 검증자 재현 경로는 실제 GET 으로 확인한다(`test_endpoint_short_and_old_history_is_date_mismatch`).
  - 정정 전 순서로 되돌리는 변이에서 4건이 실패했다(검출).
- 화면 코드는 바뀌지 않았다(백엔드 판정이 `date_mismatch` 를 주면 기존 '—' · 날짜 사유 · 뺀 보유 줄이 그대로 동작). 이력이 짧아 20일 시작일이 없을 때의 '가격 흐름 기준' 문구('20일 확인 불가 ~ 기준일') 단언을 `lib/priceBasis.test.ts` 에 더했다.
- **검증자 수치 정정 (2026-10-13)**: §8에 남아 있던 관련 시험 합계 35를 실측 46(새 시험 41 + 기존 API 시험 5)으로 정정했다. 문서 숫자만 정정했으며 코드 · 시험 변경은 없다.

### 6-2. 독립 검토(2026-10-13 · 읽기 전용 · 1회) 반영

HIGH 0. 날짜 키 · 공유 경로 불변 · 최대 3개 · 거래량 계산 · 문구 · P-10 기록은 문제 없음으로 확인됐다. 지적 9건은 모두 반영했다(설계 §10 보충 2건은 그 뒤 별도 반영 — §1).

| 지적 | 반영 |
|---|---|
| M1 기간 불일치 종목이 최대 3개에서 설명 없이 빠짐(status `partial`) | status `ok` 유지 · 대비값만 비움 → 자기 5일 값으로 후보 유지(§4-2) · 시험 갱신 · PLAN §7-2 · §7-4 정정 |
| L2 날짜 키 = 실제 계산 날짜를 지키는 시험 없음 | `test_price_dates_equal_short_term_momentum_dates` — 창 안 가격 없는 행 · 종가 0 행을 넣고 `compute_short_term_momentum_batch` 의 날짜와 같음 · 변이 '읽기에서 close>0 조건 뺌' 검출 |
| L3 입력 불변 단언이 정정 없는 경우에만 | 기준일 불일치 · 기간 불일치 · 같은 읽기 시험에도 `ev == before` |
| L4 「요즘 잘 오르는 ETF」 보유 비교 영향 문서 누락 | §5-4 · PROGRAM_TRUTH 기록 |
| L5 '과거 저장 자료'가 날짜 방향을 안 봄 | 날짜 비교로 두 문구(§4-7) · 시험 추가 |
| L6 결과서 staged 표현 · 자리표시 | STATUS 정정 · §8 · §9 실측으로 채움 |
| L7 PROGRAM_TRUTH '검증자 확인'이 완료로 읽힘 | '검증자 확인 대기'로 |
| L8 낡은 주석이 남음(`TodayInvestmentCheckView.tsx:13`) | 그 줄을 지금 동작으로 고침 |
| L9 무한대 거래량이 화면 API 를 500 으로 만들 수 있음 | 새 읽기 함수가 저장값 그대로 · 계산에서 무효 처리(§4-6) · 시험 `test_reader_infinite_volume_is_invalid_not_error` |

## 7. 사용자 확인 — 실화면 통과 (2026-10-13 · 새로고침)

- 사용자 확인 항목: 「확인 근거」 기준 줄 · 개별주 3종목 '—' · 상세 날짜 사유 · 가격 흐름 기준 · 거래량 4칸(과거 저장 자료) · 정상 ETF 거래량 / 「오늘의 투자 점검」 최대 3개(SK하이닉스 없음 · KODEX 200 비중 14.0% · 손익 +23.88%) · 뺀 보유 줄 · KODEX200 거래량 · 두 카드 문구 → 사용자 "확인했습니다"(2026-10-13).
- 개발자 사전 확인: 오늘의 투자 점검 PC 화면 캡처에서 KODEX 200 '비중 14.0% · 손익 +23.88%'(「확인 근거」 합산과 같음) · 뺀 보유 줄 · 기준일 설명을 봤다(2026-10-13 · 합산 정정 뒤).

## 8. 검증 실측 (2026-10-13)

- backend: `black --check` · `flake8` · `py_compile` 통과(바뀐 · 새 .py 8개)
  - `tests/test_stored_volume_evidence.py` 18 · `tests/test_pc_price_basis.py` 23(상태 조합 10 · r1 재현 API 1 포함) — 41 passed
  - 관련 기존 `test_api_holdings_market_evidence` 포함 46 passed(새 두 파일 41 + 기존 API 시험 5)
  - 전체 회귀(검증자 r1 정정 뒤 · 마지막): **3428 passed**(2026-10-13 · 410.48초 · 경고 1 = 기존 httpx 사용 중단 안내 · 직전 3417 + 새 시험 11)
    - §10 보충 반영 뒤(r1 전) = 3417 passed(416.10초).
  - 그 전 기록
    - 독립 검토 반영 전 = 3413 passed.
    - 반영 뒤 1회 = 1 failed · 3414 passed. 실패 원인은 직전 변이('사유 순서 바꿈' · 같은 크기 · 같은 초 복원)가 남긴 `.pyc` 였고, 단독 실행은 통과했다.
    - 원본 수정 시각 갱신 · `.pyc` 삭제 뒤 = 3415 passed(코드 변경 없음).
- frontend: `npx tsc --noEmit` exit 0 · `npm run lint` exit 0 · `npx vitest run` **37파일 444 passed**(직전 423 → +21)
  - 내역: storedVolume 4 · priceBasis 3 · helpers +3 · 확인 근거 화면 +4 · 오늘의 투자 점검 새 파일 5 · 최대 3개 합산 새 파일 2
  - 기존 AC-13 시험은 판정 문구로 단언만 바꿨다.
- 변이(저장소 파일 임시 변경 → 시험 → 복원)
  - frontend 14/14 검출: 기준일 다른 행 '—' 안 함 · 날짜 사유 빼기 · 날짜 사유를 사유로 안 봄 · 배수 사유 바꿈 · 과거 저장 자료 안 함 · 뺀 보유 줄 없앰 · 2칸 배치 빠짐 · KODEX200 제목 바꿈 · 일부 제공 배지 양식 되돌림 · 평균 소수 자리 0 · 기준 줄에 뺀 종목 안 씀 · 기준일 비교 없이 과거 표시 · 최대 3개 비중에 첫 계좌 값 · 최대 3개 손익에 첫 계좌 값
  - backend 17/17 검출: 기준일 비교 없앰 · 기간 비교 없앰 · 메모 안 지움 · 기준일 불일치에도 status 유지 · 최대 3개 재계산 안 함 · 깊은 사본 대신 얕은 사본 · 읽기에서 close>0 조건 뺌 · 평균에 기준일 포함 · 0 거래량 무효 · 유효 20개 미만도 평균 · 사유 순서 바꿈 · 거래량 필드 안 붙임 · 라우트가 사본 정정 안 함 · builder 값 유지(다시 구하지 않음) · 단기 흐름 메모 안 바꿈 · 기준일 불일치에 '데이터 부족' 붙임 · 이력 부족을 기준일 비교보다 먼저 판정(r1 정정 전 순서 · 4건 실패)
  - 마지막 6종(§10 보충분 · r1 정정분)은 `PYTHONDONTWRITEBYTECODE=1` · 복원 뒤 `os.utime`.
- 실데이터 확인(PC API 읽기만 · 2026-10-13)
  - `price_basis.reference_date` = 2026-10-08 · KODEX200 20일 비교 기간 시작 2026-09-07 · 뺀 종목 3(2026-08-12)
  - 최대 3개 위 그대로 · `coverage` total 29 · need_check 3
  - KODEX 200 거래량 23,162,524주 · 평균 23,710,207.85주 · 0.98배 · 출처 FinanceDataReader
  - §10-2-1 정정 전후 응답의 단기 흐름 · 메모 차이 0 / 32항목(두 읽기 사이 자료 변화 없음)
- 라이브 DB · 보유 파일 시험 접근 0(tmp DB · 기존 격리 fixture). OCI 변경 0.

## 9. git 상태

(보고 직전 실측 · 보고 메시지에 인용)

## 10. 종료 (2026-10-13)

- 코드 · 시험 · 문서 · 종료 기록을 한 커밋으로 push했다(사용자 승인 2026-10-13 · 커밋 번호 = `git log`). PC 화면은 자동 다시 읽기로 이미 반영됐다. OCI pull 은 없다.
- 이어서 `POC5-10` PC 보유 개별주 수집 대상 보완(PLAN PASS · `docs/ai_plan/POC5/POC5-10_PC_HOLDINGS_EQUITY_PRICE_REFRESH_PLAN_V1.md` §6)을 구현한다. `DEF-PRICE-EQUITY-REFRESH` 수집 원인은 그때까지 열림이다.

