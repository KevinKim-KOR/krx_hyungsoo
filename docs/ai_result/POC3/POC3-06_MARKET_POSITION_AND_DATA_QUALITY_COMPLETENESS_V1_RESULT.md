# POC3-06 Market Position & Data Quality Completeness v1 — 개발 결과서

* 문서 종류: 개발 결과서 (검증자 입력 · 개발자→검증자 보고)
* 대응 설계서: `docs/ai_design/POC3/POC3-06_MARKET_POSITION_AND_DATA_QUALITY_COMPLETENESS_V1_DESIGN_V1.md`
* 대응 PLAN: `docs/ai_plan/POC3/POC3-06_MARKET_POSITION_AND_DATA_QUALITY_COMPLETENESS_V1_PLAN_V2.md`
* 작성일: 2026-08-03
* 완료 커밋: PLAN `b42cc1fc` · A `eabe59c6` · **B·C `7a3e947e`** · **D `8c5bd6d1`**
* 레드팀: PASS (설계자→레드팀→개발자 경유 = 이미 통과, revision 없음)
* 자체 검수(최종): backend `pytest` **1094 passed · 4 skipped** · `black`·`flake8` 0 · frontend `tsc` 0·`eslint` 0·`vitest` 127 passed
* 사용자 실화면 확인: **C 통과** (오늘의 투자 점검 KOSPI 실제값 화면) · **E 통과** (두 PUSH 실제 Telegram 수신 확인 — "시장흐름 브리핑 받았습니다 / 홀딩스 판단 초안도 받았습니다")

---

## 1) 처리한 요구사항

설계서 §10 순차 게이트 A~E 전부 수행.

- **A구간 (계약 확정·VIX 실측)**: DONE — VIX 연결 확정(자기 기준일 표시), composer 입력 계약 충돌 없음. §11 복귀조건 미해당.
- **B구간 (공통 요약 composer + KOSPI 관찰값)**: DONE — `market_summary_composer.py`(신규) + KOSPI 일간·1년·52주 고점 대비 + 국면 지속일 helper.
- **C구간 (오늘의 투자 점검 연결)**: DONE — KOSPI `개발 중` 4항목 실제값 교체. **사용자 Dashboard 실화면 확인 통과.**
- **D구간 (PUSH·Dashboard 정합)**: DONE — 두 PUSH 가 composer/market_context 동일 결과 사용. 정합 테스트.
- **E구간 (실제 Telegram 수신)**: DONE — 두 PUSH 실제 발송(`telegram_send` ok=True) + **사용자 수신 확인.**

## 2) 변경된 파일 목록

### 신규
- `app/market_summary_composer.py` — 공통 판단 요약 composer (§6, Q3)
- `tests/test_market_summary_composer.py` — composer·helper 단위 + 프론트 규칙 동일성 (11 케이스)
- `tests/test_poc306_push_dashboard_parity.py` — PUSH·Dashboard 정합 (4 케이스)

### 수정 (backend)
- `app/market_regime.py` — `compute_kospi_position_metrics`(일간·1년·52주 고점) + `compute_regime_streak`(국면 지속일) additive
- `app/api_market_topn_models.py` — `MarketContextKospi` additive 확장 + `MarketContextRegimeStreak`
- `app/api_market_topn_service.py` — regime_streak 매핑
- `app/market_topn.py` — KOSPI 관찰값·streak 병합 (compute_topn)
- `app/draft.py` — PUSH-2 draft_payload 에 `judgment_summary` 키 + `_compose_holdings_judgment_summary`
- `app/draft_message.py` — holdings_briefing 에 `[오늘 먼저 볼 보유 ETF]` 섹션
- `app/message_market_briefing.py` — `[시장 위치]` 섹션 (맨 앞)
- `tests/test_universe_seed.py` — draft_payload 키 집합에 judgment_summary 추가(schema lock)

### 수정 (frontend)
- `frontend/app/components/TodayInvestmentCheckView.tsx` — KOSPI 일간·1년·고점 대비·지속일 실제값, `개발 중` 4항목 제거
- `frontend/app/components/TodayInvestmentCheckView.test.tsx` — 실제값·미도입 board 테스트
- `frontend/lib/api/marketEvidence.ts` — MarketContextKospi·RegimeStreak 타입 additive

## 3) 신규 추가된 의존성

없음. (신규 API·DB·source·factor·formula·threshold·label·라이브러리 0건 — AC-19.)

## 4) 지시문 외 변경

- **[데이터 품질 의심 — 별도 이슈]** KOSPI 저장 series(`market_benchmark_daily_price`)가 실제 코스피(~2,600)가 아닌 스케일(6,690대·일간 ±5~9%)로, 화면·PUSH 의 KOSPI 값(일간 -5.72%·1년 +109.71%·고점 대비 -26.59%)이 비현실적. **산식은 설계서 §6.2대로 정확**(연속 거래일·1년 전 유효거래일 실측 확인). 사용자 판정(2026-08-03): POC3-06 은 그대로 진행(저장값 정직 표시 = 설계 의도), 데이터 품질은 별도 이슈로 남김. → §13 BACKLOG.

## 5) AC 1~20 전수 대조 (실측 근거)

| AC | 판정 | 실측 근거 |
|---:|:---:|---|
| 1 | PASS | POC3-05 보유 화면·계산 계약 불변. holdings evidence·enriched read 재사용, 신규 산식 0. |
| 2 | PASS | Dashboard·PUSH 가 `compose_judgment_summary`(단일)·`market_context`(단일) 사용. 화면별 재계산 없음(draft.py:83 composer 1회 · market_topn compute_topn 1회). |
| 3 | PASS | KOSPI 일간·1년 수익률·최근 1년 고점 대비·기준일 = `compute_kospi_position_metrics` 실제값. 화면·PUSH 표시. |
| 4 | PASS | 국면 라벨·지속 거래일 수 = KODEX200 기준(`compute_regime_streak`). "KODEX200 기준" 명시, KOSPI 흐름으로 오해 안 함. |
| 5 | PASS | MA20·MA60 대비 = 기존 저장값 단순 산술(POC3-01). 미래 예측·시장 전환 라벨 아님. |
| 6 | PASS | holdings_briefing top_holdings = POC3-05 규칙(`select_top_holdings` = `lowestFiveDayRows` 동일, 최대 3건, 5일 낮은 순). 전환 테스트 고정. |
| 7 | PASS | 같은 ticker·기준일의 평가·5일·20일·KODEX200 대비가 확인 근거·Dashboard·PUSH preview 동일 — composer 단일 결과. 정합 테스트. |
| 8 | PASS | partial·unavailable·not_loaded 는 `select_top_holdings`에서 5일 정렬 제외, `_need_check`로 자료 확인 필요 분리. |
| 9 | PASS | 결측·실패는 `자료 없음`·`자료 확인 필요`(0·정상 위장 금지). KOSPI position None 유지, 기준일 표시. |
| 10 | PASS | VIX 기존 경로 연결(A-Q5 실측 available·as_of 2026-07-03). 자기 기준일 표시, 오래된 VIX 가 KOSPI·KODEX200 요약 오염 안 함. 신규 stale threshold 0. |
| 11 | PASS | 실화면(C) — KOSPI 위치·확인할 보유 ETF·자료 문제 구분. 사용자 확인 통과. |
| 12 | PASS | Dashboard 에 전체 종목표·차트·NAV·구성종목 복제 없음(POC3-05 확인 근거 화면 담당). 오늘 화면은 요약·이동만. |
| 13 | PASS | KOSPI `개발 중` 4항목 실제값 교체(board 제거). 거래량·공격방어·SuperTrend 는 이번 단계 미도입 유지. |
| 14 | PASS | market_briefing preview `[시장 위치]` = 실제 발송 message_text, market_context(Dashboard 동일) 반영. 실제 수신 확인(E). |
| 15 | PASS | holdings_briefing preview `[오늘 먼저 볼 보유 ETF]` 최대 3건·이유·기준일 = 실제 발송 message_text. 실제 수신 확인(E). |
| 16 | PASS | preview ↔ Telegram 동일 `message_text`(Run.message_text 재사용). frontend 본문 조립 없음. `telegram_send(run.message_text)` 발송. |
| 17 | PASS | PUSH 종류·스케줄·승인·OCI·중복 차단·sent registry 계약 불변. message 문구만 additive 추가. |
| 18 | PASS | BUY·SELL·매수·매도·교체·비중·주문 지시 0(composer·message 섹션 grep 0). "매매 지시 아님" 중립 문구 유지. |
| 19 | PASS | 신규 endpoint·DB·source·시장 알고리즘·score·threshold·저장 rank 0(composer 는 기존 read 조합). |
| 20 | PASS | 사용자 실제 Dashboard(C) + 두 PUSH 실제 발송 결과(E) 확인 후 PASS. |

AC 1~20 **전부 PASS**.

## 6) 다음 검증자(Codex)에게 알릴 점

- **composer 단일 산출처**: `select_top_holdings`(backend)가 프론트 `lowestFiveDayRows`와 동일 규칙임을 **동일 fixture 전환 테스트**로 고정(test_market_summary_composer). Dashboard·PUSH 값 불일치(§11.8) 방지.
- **KOSPI 관찰값 additive**: `MarketContextKospi`에 필드만 추가, 기존 20d/60d/1m/3m 불변. 값은 composer/compute_topn 1회 계산.
- **국면 지속일 재계산**: `compute_regime_streak`가 각 과거 거래일에 기존 규칙 재적용(미래 데이터 미사용). 계산 불가 None, 이력 시작점 at_least. 신규 판정 규칙 0.
- **데이터 품질(§4)**: KOSPI 저장값 비현실적이나 산식은 정확 — 코드 결함 아님. 별도 이슈.
- **VIX**: A-Q5 실측으로 연결(available). market_risk read 그대로, 신규 source 0.

## 7) 사용자 확인이 필요한 항목

- **[완료] E 실제 Telegram 수신**: 사용자 2026-08-03 확인 — 시장흐름 브리핑·홀딩스 판단 초안 두 PUSH 모두 수신.
- **[별도 이슈] KOSPI 데이터 품질**: 향후 실제 코스피 지수 적재/검증 Step 필요(§13 BACKLOG 후보). 그 전까지 KOSPI 표시값이 비현실적이어도 산식이 아니라 데이터 문제.
- **미커밋 무관 파일**: `design/DESIGN-apple.md`·`docs.zip` — POC3-06 무관, 커밋 제외.
- **push 미실행**: 규칙상 별도 승인. POC3-06 커밋(PLAN·A·B·C·D)은 push 대기.

문서 끝.
