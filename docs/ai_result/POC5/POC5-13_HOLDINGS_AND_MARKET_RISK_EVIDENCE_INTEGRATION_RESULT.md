# POC5-13 개발 결과서 — HOLDINGS_AND_MARKET_RISK_EVIDENCE_INTEGRATION (보유 · 시장 위험 근거 통합 1차)

작성 2026-10-15 · 작성자: 개발자(VSCode Claude) · 수신: 검증자(Codex) · 설계자

```text
STATUS        = IMPLEMENTED_VERIFIED — 사용자 실화면 확인 완료(2026-10-15) → 검증자 r1 VERIFIED(2026-10-15 · §10) → 커밋 · push(사용자 승인 2026-10-15) → RESULT 설계자(POC5-14 RESULT 와 함께)
VERIFIER      = Codex r1 · staged 22파일 · 사용자 안내 문장 생략 승인 확인 · 운영 코드 및 시험 수정 0
STEP_ID       = POC5-13 보유 · 시장 위험 근거 통합 1차
DESIGN        = docs/ai_design/POC5/POC5-13_HOLDINGS_AND_MARKET_RISK_EVIDENCE_INTEGRATION_DESIGN_V1.md
DECISION      = docs/ai_design/POC5/POC5-13_HOLDINGS_AND_MARKET_RISK_EVIDENCE_INTEGRATION_PLAN_DECISION_2026-10-14.md (CONDITIONAL_PASS · Q1 (b) · Q2 (b) · Q3 (a) · Q4 (a))
PLAN          = docs/ai_plan/POC5/POC5-13_HOLDINGS_AND_MARKET_RISK_EVIDENCE_INTEGRATION_PLAN_V1.md (§7 판정 반영 · §8 사용자 목업 결정 B안 · 배지 파란 계열)
BASE_COMMIT   = 01e54a50 (POC5-14 커밋 · 검증자 r1 VERIFIED · push 2026-10-15) — 이 결과서의 변경 = 그 커밋 대비 staged(§9)
SCOPE         = PC 근거 응답 사본에 종목별 선택 필드 decline_band 1개 · 요약 조립 함수 · 「확인 근거」 요약 블록 · 보기 '하락 구간' · 구간 배지 · 상세 줄 ·
                「오늘의 투자 점검」 보유 칸 요약 띠(B안)
                새 API 경로 · DB · 원장 쓰기 · 외부 수집 · 의존성 · OCI · PUSH · PARAM 변경 0 · 공유 builder · DECLINE_STATE_LABEL 변경 0 · MarketDiscoveryView.tsx 변경 0
REVIEW        = 독립 검토 1회(Workflow · 정확성 · 문서 2관점 · 지적마다 반박 검증 · 2026-10-15) — 확인된 지적 2건(같은 결함 2관점 1 + 문서 1) 모두 반영(§6-7)
CHECKS        = §8
```

## 0. 요약

- **backend — PC 응답 사본에만 붙는 `decline_band`**(`app/pc_price_basis.py :: _decline_band` 신규 · `apply_pc_price_basis` 에서 종목 항목마다)
  - 값: `{judgeable, state, label, return_20d_pct_1dp, unjudged_reason}`
  - 구간: OCI 보유 알림과 같은 `classify_decline(normalize_pct(20저장일 변화))`(소수 첫째 자리 반올림 뒤 −5 · −8 · −10 경계 · 상태 코드 `D10_PLUS` · `D8_10` · `D5_8`)
  - 이름(PC 전용 · 판정 Q1 (b)): 'PC 20저장일 하락 10% 이상 / 8~10% / 5~8%'(`PC_DECLINE_LABEL`). 공유 `DECLINE_STATE_LABEL` · OCI 알림 이름은 그대로다.
  - 판정 조건(판정 Q2 (b)): 기준일 검사 통과(`price_dates.comparison != date_mismatch`) · 단기 흐름 `status == ok` · 20저장일 값이 유한한 숫자. 20일 시작일만 KODEX200 과 다른 종목(`window_mismatch`)도 자기 값으로 판정한다.
  - 판정 안 함 이유 코드(판정 순서 = 기준일 → 이력 → 값): `date_mismatch` · `insufficient_history` · `invalid_value`. 판정 안 함(`judgeable=false`)은 '구간 밖'(`judgeable=true` · `state=null`)과 구분한다.
  - 값은 이 사본이 같은 최근 21행 읽기로 다시 구한 20저장일 변화다(POC5-09 의 날짜 · 값 같은 읽기 그대로).
  - 응답 모델: `app/api_holdings_market_evidence.py :: DeclineBand` · `HoldingEvidenceItem.decline_band`(선택 필드).
- **frontend — 요약 조립 함수 하나를 두 화면이 같이 쓴다**(`holdings_risk_evidence/declineSummary.ts :: buildDeclineSummary`)
  - 종목 수 = ticker 기준(같은 종목 여러 계좌 = 1종목).
  - 비중 = 정상 `GET /holdings/enriched` 를 기존 `aggregateHoldingsByTicker` 로 묶은 종목 평가 비중 원값의 합. 근거 응답의 평가금액은 쓰지 않는다(판정 §3 · 시험에서 일부러 다른 값을 줌).
  - 평가 일부 미확인 = 종목 합산 평가금액이 비어 있는 종목이 있음 → 비중 옆 '(확인된 평가금액 기준 · 일부 평가 자료 미확인)'.
  - 평가금액이 하나도 없으면(분모 0) · 그 묶음 종목이 모두 평가 미확인이면 '확인 불가'(0% 로 채우지 않음 · §4-3).
  - 시장 국면 = 근거 응답의 `judgment_summary.market_position`(국면 · 지속일 · '이상'). 날짜는 붙이지 않는다(판정 §3 — 응답에 국면 입력 날짜 필드가 없음).
  - PC 가격 흐름 기준일 = `price_basis.reference_date`.
- **「확인 근거」**(`HoldingsRiskEvidenceSection.tsx` · 새 `DeclineSummaryBlock.tsx`)
  - 목록 위 요약 블록: 시장 국면 / PC 최근 20저장일 하락 구간 N종목 · 보유 평가 비중 P% / 구간별 '10% 이상 · 8~10% · 5~8%' 종목 수 · 비중 / 판정 범위 '구간 판정 가능 a/b종목 · PC 가격 흐름 기준일 D' / 안내('PC 저장 종가 기준 · OCI 알림과 값이 다를 수 있음' · 반올림 뒤 경계 · 표 5일 · 20일 자릿수 그대로 · 실제 기간은 상세 · 시장 국면이 종목 하락의 원인이라는 뜻 아님)
  - 보기 '전체 / 하락 구간 (N) / 자료 확인 필요 (k)' · 기본 전체 · 사용자 정렬 유지 · 받은 자료로 거름(재조회 0)
  - 종목 이름 아래 구간 배지(파란 계열 · 사용자 결정) · 구간 밖 · 판정 안 함은 배지 없음('안전' 표기 없음)
  - 상세 'PC 20저장일 하락 구간' 줄: 판정 값(소수 첫째 자리) · 실제 기간(20일 시작일 ~ 종료일) · 20일 시작일이 KODEX200 20일 시작일과 다르면 '(KODEX200 비교 기간과 달라 상대 비교는 비워 둠)'(5 · 10일만 다르면 붙이지 않음 — 20일 대비 값이 남아 있고 그 사유는 '자료 확인 안내'에 나옴) · '해당 없음 · …' · 판정하지 않음 사유(기준일 다름 · 저장 종가 21개 미만 · 값 확인 불가 · 계좌 간 흐름 값 다름)
- **「오늘의 투자 점검」**(`today/JudgmentQueueSection.tsx`) — 사용자 목업 결정 B안
  - '내가 가진 ETF N개' 제목 바로 아래 옅은 파란 띠 세 줄: 시장 국면 / PC 최근 20저장일 하락 구간 N종목 · 보유 평가 비중 P%(N · P 크고 굵게 · 평가 일부 미확인이면 괄호 문구) / 구간 판정 가능 a/b종목
  - 같은 칸 안내 문장('보유 평가는 …')은 여백 없이 한 단계 작게(`tc-hold-help` · 사용자 요청)
  - 최대 3개 선정 · 5일 정렬 · 표시값 그대로
- **실제 PC 자료 확인**(2026-10-15 · 사용자 서버 · 읽기 전용 GET)
  - 응답 32줄 모두 `decline_band` 있음 · 29종목 · 판정 가능 29 · 구간 10% 이상 11 · 8~10% 4 · 5~8% 3 · 구간 밖 11 · 판정 안 함 0
  - 응답 32줄 모두 `decline_band.state` = 그 줄 20저장일 값에 OCI 함수를 직접 적용한 결과(불일치 0/32)
  - 화면(구현 코드 · 1440 · 1000px 캡처): 하락장 · 4거래일째 · 18종목 · 69.3% · 11종목 62.0% · 4종목 4.2% · 3종목 3.2% · 구간 판정 가능 29/29종목 · PC 가격 흐름 기준일 2026-10-14 · 보기 '하락 구간 (18)' · '자료 확인 필요 (0)'

## 1. 처리한 요구사항

| 요구사항(설계 · 판정) | 상태 | 근거 |
|---|---|---|
| 설계 §2 · §5 「오늘의 투자 점검」 보유 칸 요약 | DONE(사용자 목업 결정 B안 · 설계 §5 '한 줄'과 다름 — §4-1) | `JudgmentQueueSection.tsx` · `TodayRiskStrip.test.tsx` |
| 설계 §5 「확인 근거」 목록 위 시장 국면 · 구간별 종목 수 · 비중 · 관측 범위 | DONE | `DeclineSummaryBlock.tsx` · `HoldingsRiskEvidenceDecline.test.tsx` |
| 설계 §5 보기 '전체 / 하락 구간 / 자료 확인' · 기본 전체 · 정렬 유지 · 받은 자료로 처리 | DONE | 같은 시험(보기 · 정렬 · GET 각 1회) |
| 설계 §5 이름 주변 · 상세에 하락 구간 · 날짜 사유 · 표에 숫자 열 추가 없음 | DONE | 배지 · 상세 줄 시험 |
| 판정 Q1 (b) PC 이름 · 공유 이름 불변 · 함수 · 경계 · 상태 코드 재사용 · 안내 · 도움말 | DONE | `PC_DECLINE_LABEL` · `test_pc_labels_and_shared_oci_labels_unchanged` |
| 판정 Q1 (b) 상세 실제 기간 · 판정에 쓴 소수 첫째 자리 값 | DONE | `declineDetailText` · 시험 |
| 판정 Q2 (b) 판정 조건 · 이유 코드 · 시작일 다름 판정 · 두 보기 함께 · 판정 안 함 ≠ 구간 밖 | DONE | `test_unjudged_reasons_and_order` · `test_copy_gets_band_per_item…` · `declineSummary.test.ts`(상세 문구 · 20일 기간 다름 / 5일만 다름) · `HoldingsRiskEvidenceDecline.test.tsx`(두 보기 함께 · 구간 밖 · 판정 안 함) |
| 판정 Q3 (a) 오늘 화면 순서 · a/b 종목 기준 · 기존 '자료 확인 필요' 그대로 · '안전' 배지 없음 | DONE | `TodayRiskStrip.test.tsx` · 배지 시험 |
| 판정 §3 비중 = 정상 enriched 종목 합산 · 근거 응답 평가금액 미사용 · 부분 평가 문구 · 확인 불가 · 원값 계산 뒤 반올림 | DONE | `declineSummary.test.ts` · 화면 시험(777,777 · 999,999 · 555,555 미사용) |
| 판정 §3 'PC 가격 흐름 기준일' · 국면 줄 날짜 없음 · 시장 전체 요청 추가 없음 | DONE | 요약 블록 시험 · GET 2종만 |
| 판정 §5-4 반올림 경계 · 기간 불일치 · 판정 불가 · 복수 계좌 부분 평가 · 잘못된 응답과의 독립성 시험 | DONE | §8 |
| 판정 §5-5 공유 builder · PUSH · 보유 저장 불변 | DONE | `test_endpoint_returns_band_and_shared_builder_has_none` · 사본 입력 불변 시험 · 변경 파일 범위 |
| 설계 §8 BACKLOG · 통합지도 P-06 은 '시장 · 보유 구간 근거 연결 및 평가 비중 제공'만 해소 · Q6 확정 아님 | DONE | BACKLOG §2 항목 정리 · 통합지도 P-06 줄 |
| 사용자 실화면 확인 | DONE | 2026-10-15 사용자 '확인했습니다'(두 화면 · 구간 이름 파란 계열 포함 · §7) |

## 2. 변경된 파일 목록

- `app/pc_price_basis.py`: 수정(`_decline_band` · `PC_DECLINE_LABEL` · 이유 코드 상수 · 항목마다 `decline_band` · 221 → 280줄)
- `app/api_holdings_market_evidence.py`: 수정(`DeclineBand` 모델 · 항목 선택 필드 · 271 → 284줄)
- `frontend/lib/api/holdings.ts`: 수정(`HoldingsDeclineBand` 형식 · 항목 선택 필드)
- `frontend/app/components/holdings_risk_evidence/helpers.ts`: 수정(행에 `decline_band` · 계좌 간 흐름 값이 다르면 null)
- `frontend/app/components/holdings_risk_evidence/declineSummary.ts`: **신규**(요약 조립 · 상세 줄 문구 · 112줄)
- `frontend/app/components/holdings_risk_evidence/DeclineSummaryBlock.tsx`: **신규**(「확인 근거」 요약 블록 · 44줄)
- `frontend/app/components/HoldingsRiskEvidenceSection.tsx`: 수정(요약 블록 · 보기 · 배지 · 상세 줄 · 457 → 499줄)
- `frontend/app/components/today/JudgmentQueueSection.tsx`: 수정(B안 띠 · 안내 문장 class · 306 → 339줄 · 306 = POC5-14 커밋 판)
- `frontend/app/globals.css`: 수정(요약 블록 · 배지 · 띠 · 안내 문장 스타일 · 끝에 추가)
- 시험
  - `tests/test_pc_decline_band.py`: **신규**(38)
  - `frontend/app/components/holdings_risk_evidence/declineSummary.test.ts`: **신규**(11)
  - `frontend/app/components/HoldingsRiskEvidenceDecline.test.tsx`: **신규**(7)
  - `frontend/app/components/today/TodayRiskStrip.test.tsx`: **신규**(6)
  - `frontend/app/components/HoldingsRiskEvidenceSection.test.tsx`: 수정(보기 버튼 두 개 → 세 개 단정)
  - `frontend/app/components/holdings_risk_evidence/helpers.test.ts`: 수정(행 fixture 에 `decline_band: null` — 형식 필수 필드)
  - `frontend/app/components/today/TodayFolds.test.tsx`: 수정(종목 항목 fixture 에 API 필수 필드 `short_term_momentum` — 단정 변경 없음 · §4-6)
- 문서: 이 결과서(신규) · PLAN V1(STATUS · §8) · `docs/PROGRAM_TRUTH.md` · `docs/backlog/BACKLOG.md` · `docs/STATE_LATEST.md` · 통합지도 `docs/ai_design/POC3/POC3-00_PC_JUDGMENT_UI_INTEGRATED_IMPLEMENTATION_MAP_V2.md`(P-06 줄 · 설계 §8 지시)

## 3. 신규 추가된 의존성

없음.

## 4. 지시문 외 변경 · 구현 판단

1. **오늘 화면 배치 = 사용자 목업 결정 B안**(설계자에게 알림)
   - 설계 §5 는 '기존 칸 안 요약 한 줄'이다. 사용자가 중요한 정보라 더 부각되기를 요청했고, 강조안 A · B 를 실제 PC 자료로 비교한 뒤 B안을 골랐다(PLAN §8).
   - B안은 같은 칸 안이지만 강조 띠 세 줄이고, 자리는 최대 3개 아래가 아니라 보유 칸 제목 바로 아래다. 새 카드 · 차트는 없다. 순서는 판정 Q3 그대로다.
2. **구간 배지 · 요약 구간 이름 = 파란 계열**
   - 배지는 사용자 결정(2026-10-15 · 화면에서 붉은색은 상승 · 이익에 씀)이다.
   - 같은 이유로 「확인 근거」 요약의 구간 이름 글자('10% 이상' 등)도 파란 계열로 했다(목업은 붉은색). 사용자 결정의 이유를 같은 화면 안에서 맞춘 것이라 사용자 확인 항목으로 올린다(§7).
3. **'확인 불가'를 묶음 단위로도 적용**
   - 판정 §3 은 '평가금액이 전부 없거나 분모가 0이면 확인 불가'다.
   - 구간에 든 종목이 모두 평가 미확인인 묶음도 '확인 불가'로 둔다(그 묶음 합을 0% 로 보이지 않음 · '미확인 평가금액을 0 으로 만들지 않는다'). 일부만 미확인이면 확인된 금액으로 계산하고 괄호 문구를 붙인다.
4. **이유 코드 범위**
   - `insufficient_history` 는 이 사본 단기 흐름이 `ok` 가 아닌 모든 경우다. 종목 저장 가격 0행 · 종목이나 KODEX200 저장 종가 21개 미만이 여기 든다. 상세 문구는 '이 종목이나 KODEX200 의 저장 종가가 21개보다 적어 …'로 둘 다를 적었다.
   - `invalid_value` 는 status ok 인데 20저장일 값이 없음 · NaN · 무한대 · bool · 문자열인 경우다.
5. **상세 줄 자리**: PLAN §3 은 '상세 맨 위'였다. 사용자가 확인한 목업대로 '자료 확인 안내' 다음 · '가격 흐름 기준' 앞에 둔다(자료 확인 사유가 먼저 보이는 POC5-UI-02 배치 유지).
6. **기존 시험 fixture 보충**(단정 변경 없음)
   - `TodayFolds.test.tsx :: item()` 은 `as unknown as` 로 필수 필드 `short_term_momentum` 을 뺀 부분 항목이었다. 오늘 보유 칸이 「확인 근거」와 같은 행 조립 함수로 종목 항목을 묶게 되면서 그 필드를 읽는다. API 응답 모델에서는 필수 필드라 fixture 에 값 없는 ok 흐름을 넣었다.
   - `helpers.test.ts :: row()` 에 `decline_band: null`(행 형식에 필드 추가).
7. **시장 국면 이름**: 기존 `regimeLabelKo(regime_code, regime_label)`(KOSPI 카드와 같은 함수)를 쓰고, 지속일 문구는 시장 브리핑 · KOSPI 카드와 같은 ' · N거래일째( 이상)'다.
8. **오늘 화면 띠에는 'OCI 알림과 값이 다를 수 있음' 안내 문장을 두지 않았다**: 판정 Q1 '요약 근처에 늘 표시'는 「확인 근거」 요약 블록에 둔다(PLAN §3 목업 · 사용자가 확인한 B안 띠도 세 줄만). 띠의 이름 자체가 'PC 최근 20저장일 …'이라 OCI 알림 이름('20거래일 …')과 구분된다. 오늘 화면에도 안내가 필요한지는 설계자 판단으로 올린다(§7).

## 5. 알려진 한계 / 미완성

1. **POC5-14 와 같은 작업 트리에서 만들었다**
   - POC5-14 검증 동안 POC5-13 변경은 stage 하지 않았다. POC5-14 가 커밋 · push(`01e54a50`)된 뒤 POC5-13 을 stage 했다(§9).
   - 두 단계가 같이 바꾼 파일: `JudgmentQueueSection.tsx`(14 = 주석 · 13 = 띠) · `PROGRAM_TRUTH.md` · `BACKLOG.md` · `STATE_LATEST.md` · POC5-13 PLAN. 이 파일들의 POC5-14 부분은 이미 그 커밋에 있다. 그래서 지금 staged 차이는 POC5-13 부분만이다.
2. **PC 와 OCI 값은 다를 수 있다**(설계 §3 계약 차이 · 판정 Q1)
   - PC = 저장 종가(ETF 는 FinanceDataReader 배당 조정 계열 · 개별주 FDR) · 저장 행 20구간.
   - OCI = 당일 Naver 시세 · KRX 무조정 · 달력 T−20.
   - 「확인 근거」 요약 블록 안내에 늘 적었다(오늘 화면 띠에는 안내 문장 없음 · §4-8). 두 화면 모두 구간 이름이 'PC …'로 OCI 알림 이름과 다르다.
3. **자료 부족 상태는 지금 실제 자료에 없다**: 기준일 다름 · 이력 부족 · 20일 시작일 다름 · 평가 미확인이 모두 0건이다. 이 경우는 격리 시험 · 수정 목업 fixture 로만 확인했다.
4. **계좌 간 흐름 값 충돌(`evidence_conflict`)은 지금 구조에서 생기지 않는다**: 단기 흐름은 종목 단위다. 생기면 판정 안 함으로 둔다(시험).
5. **이전 백엔드 응답(필드 없음)**: 화면은 판정 가능 0 · 0종목으로 보이고 배지 · 구간 판정을 만들지 않는다(시험). PC 서버가 자동 다시 읽기로 새 코드를 쓰므로 실제로는 생기지 않는다.
6. **KS-10**: 「확인 근거」 499줄 · 오늘 보유 칸 339줄(근접 850 아래) · `app/pc_price_basis.py` 280줄(근접 600 아래).
7. **「현재 제공 범위와 남은 기능」 안내 카드는 그대로 뒀다**: '내가 가진 ETF의 위험 신호 · 개발 중 · 보유 ETF 중 먼저 점검할 종목과 그 이유를 찾는 기능.'(`today/InDevelopmentSection.tsx:15-17`). P-06 전체(종합 위험 구간 분류)는 미완료라 '개발 중'은 맞다. 설명 문장을 이번 기능에 맞게 바꿀지는 설계 범위 밖이라 설계자 판단으로 남긴다(POC5-UI-02 판정 '두 안내 카드 그대로').

## 6. 다음 검증자(Codex)에게 알릴 점

1. **OCI 함수와 같은 판정**
   - 경계 시험: −4.94 · −4.95 · −5.0 · −7.95 · −7.96 · −8.0 · −9.95 · −9.96 · −10.0 · −12.3 · 0.0 · 3.1 을 `ok` · `window_mismatch` 두 비교 상태에서 확인(24).
   - 각 값의 구간 = 단정 상수 = `classify_decline(normalize_pct(v))`(세 값이 모두 같아야 통과).
   - 실제 응답 32줄 대조: 불일치 0.
2. **공유 builder 불변**
   - 실제 GET 시험이 같은 tmp DB 로 공유 builder 를 직접 불러 `decline_band` 가 없음을 확인한다.
   - 사본 적용 시험은 입력(공유 builder 결과 모양)이 바뀌지 않음을 확인한다.
   - `DECLINE_STATE_LABEL` 값은 시험으로 고정했다.
3. **가져오기 경로**: `app/pc_price_basis.py` 가 `app.runtime_evidence.holdings_selection` 을 가져오면 `app/runtime_evidence/__init__.py`(composer → `holdings_market_evidence`)가 먼저 실행된다. `holdings_market_evidence` 는 `pc_price_basis` 를 가져오지 않아 순환이 없다(새 프로세스에서 `import app.pc_price_basis` 먼저 실행 확인). PC 선례: `app/ledger_copy/views.py:29`. 함수 · 상수만 쓰고 러너 · 상태 저장 · 발송은 부르지 않는다.
4. **변이**(저장소 밖 사본 · 복원 = 내용 쓰기 + `os.utime` · `PYTHONDONTWRITEBYTECODE=1`)
   - backend 9/9 검출: 반올림 없이 판정 · 20일 시작일 다름을 판정 안 함 · 기준일 다름도 값으로 판정 · 판정 순서 뒤집기 · 공유 OCI 이름 사용 · 유한값 검사 없음 · bool 검사 없음 · 사본 정정 전 값으로 판정 · 필드 안 붙임
   - frontend 15/15 검출(검토 반영 2종 포함 · 5 · 10일만 달라도 비교 기간 사유 · 하락 구간 보기에서 자료 확인 필요 종목 제외): 하락 구간 보기가 판정 가능 종목 · 구간 종목 모두 미평가여도 0% · 평가 전부 없음도 0%(처음 생존 → 빈 구간 · 0종목 '확인 불가' 단정 보충 뒤 검출) · 일부 평가 미확인 표시 없음 · 계좌 간 충돌도 구간 판정 · 띠 없음 · 배지 붉은 계열 · 판정 가능 = 필드 있음 · '이상' 빠짐 · 20일 기간 다름 사유 없음 · 비중이 다른 값 · 판정 안 함을 '해당 없음'으로 · 하락 구간 보기 버튼 없음
5. **화면 조회 수**: 「확인 근거」는 기존 두 GET(보유 · 근거)만 쓰고, 보기 전환 · 정렬 · 상세 선택 뒤에도 각 1회다(시험). 오늘 화면 띠는 부모(`TodayInvestmentCheckView` · 이번에 바뀌지 않음 · 자동 조회 4종 그대로)가 받은 보유 · 근거 응답(props)만 쓰고 조회 함수를 부르지 않는다(코드 · 시험은 props 렌더).
6. **판정 안 함 ≠ 구간 밖**: 화면 '하락 구간' 보기는 `state` 가 있는 종목만, '판정 가능' 수는 `judgeable` 만 센다. 상세 문구도 '해당 없음'과 '판정하지 않음'을 나눈다(변이 F1 · F8 · F12).
7. **독립 검토 반영**(확인된 지적 2건 반영 · 반박된 지적 5건 중 2건은 서술만 정확히 함)
   - 상세 줄의 비교 기간 사유가 `comparison == window_mismatch` 이면 늘 붙어, 5 · 10일만 다르고 20일 기간은 같은 종목에도 붙었다(표의 KODEX200 대비 20일 값은 남아 있어 같은 화면에서 어긋남). → `declineDetailText(row, basis)` 가 20일 시작일을 `price_basis.kodex200_start_date_20d` 와 비교할 때만 붙인다(`evidenceGuidance` 와 같은 비교). 시험 2건(20일 다름 · 5일만 다름).
   - 결과서가 '두 보기 함께'를 화면 시험 근거로 적었지만 그런 시험이 없었다. → 20일 시작일이 다른 구간 종목이 '하락 구간 (2)' · '자료 확인 필요 (2)' 두 보기에 함께 나오고 상세에 사유가 보이는 화면 시험을 추가했다.
   - 반박된 지적 중 오늘 화면 띠의 OCI 차이 안내(같은 내용 2건)는 판단 사항으로 §4-8 · §5-2 에 적었고, 오늘 화면 조회 수 서술은 §6-5 · PROGRAM_TRUTH 에서 '추가 조회 0'으로 정확히 했다. PLAN 머리 SCOPE(제출 당시 내용 유지 · 결정은 §7 · §8) · BASE_COMMIT 은 POC5-14 커밋 뒤 그 커밋으로 바꿨다.

## 7. 사용자 확인

- **실화면 확인 완료**(2026-10-15 · 사용자 '확인했습니다' · PC 서버 자동 다시 읽기 · 독립 검토 반영 뒤 코드)
  - 「오늘의 투자 점검」: '내가 가진 ETF 29개' 아래 파란 띠 세 줄 · 안내 문장 간격
  - 「확인 근거」: 목록 위 요약 블록 · 보기 '하락 구간 (18)' · 이름 아래 파란 배지 · 종목을 눌렀을 때 상세 'PC 20저장일 하락 구간' 줄
  - 지시문 외 판단인 요약 블록 구간 이름 글자 파란 계열(§4-2)도 같은 확인에 포함(이의 없음).
- **설계자에게 알릴 것(RESULT 때)**: 오늘 화면 B안(설계 §5 '한 줄'과 다른 사용자 결정 · §4-1) · 배지 · 구간 이름 파란 계열 · 묶음 단위 '확인 불가'(§4-3) · 상세 줄 자리(§4-5) · 오늘 화면 띠에 OCI 차이 안내 문장 없음(§4-8).
- **검증 중 사용자 승인 범위 확인(2026-10-15)**: 오늘 화면 B안에서 'PC 저장 종가 기준 · OCI 알림과 값이 다를 수 있음' 안내 문장을 생략한 것도 승인했는지 검증자가 확인했고, 사용자는 **'생략도 승인했습니다'**라고 답했다. §4-8의 생략은 사용자 승인 범위에 포함된다. 「확인 근거」 요약 블록의 상시 안내는 유지한다. 설계자 RESULT 때는 미승인 질문이 아니라 사용자 결정으로 전달한다.

## 8. 검증 실측 (2026-10-15 · 최종 코드)

- backend: `black --check` · `flake8` 통과(변경 · 신규 파이썬 3개) · `py_compile` 통과
  - `tests/test_pc_decline_band.py` 38 passed
  - 관련 묶음(PC 사본 · 근거 API · OCI 구간 함수 · POC5-14 다중 계좌) 118 passed
  - 전체 회귀(마지막 1회): **3587 passed**(2026-10-15 · 405.98초 · 경고 1 = 기존 httpx 사용 중단 안내 · POC5-14 작업 트리 3549 + 새 시험 38)
- frontend: `npx tsc --noEmit` 종료 0 · `npm run lint` 종료 0 · `npx vitest run` 전체 **46 files · 541 passed**(검토 반영 뒤 최종 · 새 시험 파일 3개 24건 포함)
- 실제 PC 응답(읽기 전용 GET · 2026-10-15): §0
- 구현 화면 캡처(저장소 밖 사본 = 저장소와 같은 화면 코드 + 메뉴 · API 전환 2파일 · 실제 백엔드를 GET 만 넘기는 중계기 · 쓰기 거부 0건): 1440 · 1000px 두 메뉴
- 시험의 라이브 DB 접근 0(임시 DB) · 외부 호출 0

## 9. git 상태

- 검증 기준 HEAD: `01e54a50dae7c60c5d4cc3b87576b8c5c9dee012`(POC5-14).
- 검증 시작 시 staged **22파일(A 7 · M 15)** · unstaged 0. 작업 파일과 index가 일치했다.
- 사용자 소유 비추적 인계 문서 1개는 검증·stage에서 제외했다.
- 검증자가 바꾼 파일은 이 결과서뿐이며, 상태 메타·사용자 승인 기록·검증 근거를 반영했다. 운영 코드·시험·그 밖의 파일 수정 0. 커밋·push·OCI 작업 없음.

## 10. 검증자 r1 판정 (2026-10-15)

**종합 판정: VERIFIED**

- **A-1 지시 일치: 통과.** 소수 첫째 자리 반올림 후 OCI 공유 함수로 구간을 판정한다. 기준일 → 이력 → 값 순서, 20일 시작일 차이 허용, 판정 불가와 구간 밖 구분, 정상 enriched 응답의 종목 합산 비중, 부분 평가·확인 불가 표시를 확인했다. 오늘 화면 B안과 안내 문장 생략은 사용자 승인 범위로 확인했다(§7). 새 보기에 따른 목록 추가 조회가 없고 기존 최대 3개 선정은 유지된다.
- **A-2 보고 정확성 / A-3 산출물 정합성: 통과.** staged 22파일과 보고된 변경을 대조했다. 줄 수는 PC 사본 280 · 근거 API 284 · 확인 근거 499 · 오늘 보유 칸 339 · 요약 함수 112 · 요약 블록 44로 일치한다. 개발자 전체 회귀·변이·실데이터 보고와 검증자 직접 실행 근거는 아래에서 구분한다.
- **A-4 금지사항: 없음.** 새 API 경로·의존성·DB·외부 수집·OCI·PUSH·PARAM 변경이 없다. 공유 builder와 OCI 구간 함수·이름표는 HEAD 대비 변경되지 않았다. 새 필드는 PC 응답 사본에만 붙는다.
- **B-1~B-6: 위반 없음.** 판정·요약·표시 책임이 분리돼 있고, 새 암묵 대체값·과대 파일·실험 경로 유입·배포 경로 누락·구조적 퇴행은 발견하지 못했다. 새 운영 소스는 모두 index에 포함되며, 파일 이동·실행 경로·배포 스크립트 변경은 없다.
- **기반 문서 / 안전성 / 범위:** P-06은 부분 완료를 유지하고 종합 위험 계약은 미확정으로 남겼다. 새 문서는 승인된 결과서이며 신규 라이브러리·프레임워크 도입이 없다. 코드 안전성 위험 **NONE**, 범위 폭주 **NONE**.

### 검증자 직접 실행

- 저장소 밖 staged 사본에서 backend 관련 5파일 **118 passed**, frontend 관련 8파일 **87 passed**.
- 변경 Python 3파일 `black --check`·`flake8`·문법 검사, frontend 전체 `tsc --noEmit --incremental false`, 변경 TS/TSX 12파일 ESLint, `git diff --cached --check`: 모두 통과.
- 새 프로세스에서 PC 사본 모듈을 먼저 import한 뒤 API 모듈 import가 성공했고, 판정·반올림 함수가 OCI 공유 함수 객체와 같음을 확인했다. 이 확인에서 운영 state/logs·DB·네트워크 접근 차단 기록 0건.
- 전체 회귀 **3587 passed**, 전체 vitest **541 passed**, 변이 backend 9/9·frontend 15/15, 실제 PC 응답 32줄 대조는 **개발자 §6·§8 근거**다. 검증자는 전체 회귀·변이를 반복하지 않았고 라이브 DB·서버·OCI를 조회하지 않았다. 실화면 배치·색 확인은 사용자 확인 기록을 따른다.
- 최종 source/index 범위 확인 뒤 판정을 확정한다. 다음 순서는 설계자 RESULT 판정이며, 커밋·push는 사용자 별도 승인 대상이다.
