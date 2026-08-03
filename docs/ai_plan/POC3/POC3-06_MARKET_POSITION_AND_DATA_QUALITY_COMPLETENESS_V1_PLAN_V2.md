# POC3-06 Market Position & Data Quality Completeness v1 — 개발 PLAN_V2

* 문서 종류: 개발 PLAN (설계자 Q1~Q5 답변 반영 · 확정본)
* 대응 설계서: `docs/ai_design/POC3/POC3-06_MARKET_POSITION_AND_DATA_QUALITY_COMPLETENESS_V1_DESIGN_V1.md`
* 대체 관계: 본 PLAN_V2 가 구현 기준. PLAN_V1 은 보존하지 않음(초안 → 확정본으로 대체).
* 작성일: 2026-08-03
* 기준 revision: `a0a0b192` (POC3-05 PASS/CLOSED · push 완료)
* 레드팀: **PASS** (설계자→레드팀→개발자 경유로 도달 = 이미 통과. 레드팀은 PASS 여부만 판정·revision 없음).
* 상태: **PLAN 확정 · A구간 실측 완료 (2026-08-03).** VIX 연결 확정·composer 입력 충돌 없음(§5-A). B구간(공통 요약 composer) 착수 가능.
* 성격: 기존 KOSPI·KODEX200·VIX·Holdings·Market Evidence **저장값 read 재사용 + 공통 판단 요약 조립(server-side composer)**. 신규 endpoint·DB·table·source·factor·threshold·label 0건(§9.2·§12 AC-19).

---

## 0. 기반 문서 확인 완료

- `CLAUDE.md`(DEV_RULES) · `docs/STATE_LATEST.md`(POC3-05 CLOSED, 이 설계서가 다음 Step) · `PROJECT_ORIGIN_INTENT` · `KILL_SWITCHES` 확인.
- 사용자 표현 계약(§9.3): `Evidence`·`stale`·`unavailable`·`regime`·`snapshot`·`push_context` 비노출. 사용자 화면·PUSH 문구는 `확인 근거`·`자료 상태`·`자료 없음`·`기존 시장 국면`·`기준일`·`확인할 종목`.
- 금지(§9.2·AC-18·19): BUY·SELL·매수·매도·등급·score·threshold·신규 endpoint·DB·source.

---

## 1. 재조사하지 않는 확정 사실 (설계서 §5.1 — 그대로 신뢰)

설계서 §5.1 1~10(KOSPI close 저장·`GET /market/price-series` KOSPI read·시장 국면 KODEX200 기준·KOSPI는 이름만 바꾸면 안 됨·VIX 기존 read·`GET /holdings/market-evidence/latest` 1회 조회·POC3-05 최대 3건 규칙·unavailable 분리·PUSH `pc_evidence_snapshot→…→message_text` 흐름·급락 latest read 계약 부재)은 재조사 없이 신뢰.

**§2 실측 사실도 A구간에서 다시 전수 조사하지 않는다(설계자 지시).** A구간은 VIX 실제 상태와 composer 입력 계약의 충돌 여부만 확인한다.

---

## 2. §5.2 지정 경로 실측 결과 (완료 — A구간 재조사 없음)

| 확인 대상 | 실측 | 상태 |
|---|---|---|
| KOSPI read | `app/api_price_series.py` — `market_benchmark_daily_price` + `fetch_benchmark_history`(date ASC). `_ALLOWED_BENCHMARKS={"KOSPI"}`. AVAILABLE/NO_DATA/UNAVAILABLE 구분. | 저장 close read 가능 |
| 기존 시장 국면 | `app/market_regime.py` — **KODEX200 기준** 20d/60d 수익률·MA20/60 위치 점수(+2 상승/-2 하락). KOSPI는 보조. 순수 함수. | 동일 규칙 재사용 가능 |
| 현재 market_context 필드 | `api_market_topn_models.py` `MarketContextKospi` = **`return_20d_pct·60d·1m·3m` 만**. `daily_return_pct`·1년·52주 고점 대비 없음. KODEX200 쪽은 close·ma20/60·distance 존재. | additive 확장 대상(Q1) |
| POC3-05 요약 | `holdings_risk_evidence/helpers.ts` `buildRiskEvidenceRows`·`lowestFiveDayRows`(최대 N, status ok & 5일 유효). **프론트 TS 순수 함수.** | 백엔드 재구현 대상(Q2) |
| PUSH package | `message_market_briefing.py`·`push_context_market.py`·`push_context_holdings.py`. `pc_evidence + runtime_snapshot → push_context → builder → message_text`. | 기존 흐름 재사용 |
| 자료 상태 | `MarketContextResponse`(status·asof·warnings)·`MarketRisk*`(VIX/KODEX200 availability·as_of_date)·holdings evidence summary. 프론트 정비 큐가 이미 status별 분리. | 재사용 |
| VIX | `MarketRiskVix`(availability·as_of_date·close·change_1d/5d). 기존 FDR·SQLite read. | A구간 실측(Q5) |
| 이동 도착 key | `holdings`·`holdings_evidence`·`data_status` 존재(POC3-05). | 재사용 |

**프론트 `개발 중` 교체 대상(§3.2)**: `TodayInvestmentCheckView.tsx` L312~328·L638~644 — **KOSPI 일간 수익률·1년 수익률·최근 1년 고점 대비 위치·흐름 지속 거래일 수** 4개를 실제값으로 교체. 거래량·공격방어·SuperTrend는 미도입(보드에서 제거).

---

## 3. 모호점 — 설계자 확정 답변 반영 (2026-08-03)

**Q1. KOSPI 일간·1년·52주 고점 대비 값 → (a) 보정 확정.**
기존 `MarketContextKospi` 응답을 **additive 확장**하되, 값은 **공통 server-side composer(Q3)에서 한 번만 계산**한다. 응답 필드는 결과를 전달할 뿐 별도 계산하지 않는다. 신규 endpoint·DB 없음.

값의 의미 고정(필드명은 개발자 재량):
- **일간 수익률**: 최신 유효 거래일 close vs 직전 유효 거래일 close.
- **1년 수익률**: 최신 기준일 close vs `1년 전 날짜에 가장 가까운 이전 유효 거래일` close.
- **최근 1년 고점 대비**: `(현재 close / 최근 1년 최고 close − 1) × 100`. 고점이면 `0%`, 고점 아래면 음수.
- **1년 이력 부족 시**: 계산하지 않고 `자료 없음`.
- **표현 주의**: `high_52w_ratio_pct=95%` 같은 비율 표기 금지 — 사용자 표현 `고점 대비 -5%`와 충돌. 저장·표시 모두 "고점 대비 음수%" 의미로 통일.

**Q2. POC3-05 보유 요약(최대 3건) → (a) 확정.**
최대 3건 정렬·`자료 확인 필요` 판정 규칙을 **backend 에 동일 재구현**해 Dashboard·PUSH 가 이 결과만 사용한다. 옮기는 것은 evidence 수치 계산이 아니라 **승인된 종목 선택·요약 규칙**이다.
- Dashboard 프론트 최대 3건 계산 **제거** → composer 결과 사용.
- `확인 근거` 상세 화면은 기존 행 표시 helper 유지 가능(상세 표는 계속 프론트).
- 동일 fixture 에서 ticker·순서·상태·수치 일치를 **전환 테스트로 고정**.
- 신규 score·위험 순위·저장 rank 0.

**Q3. 공통 요약 composer 실체 → (a) 확정.**
**신규 server-side summary composer 모듈**(기존 read 조합·신규 source·DB·endpoint 0)을 만든다. 설계서 §9.1 이 명시 허용 → §11.3(신규 endpoint 필요) 복귀조건 아님. 기존 market_context read 응답과 push_context 양쪽이 이 composer 결과를 사용.

**Q4. 국면 지속 거래일 수 → 허용 확정.**
기존 `market_regime.py` 규칙을 **과거 KODEX200 시계열에 그대로 재적용**하는 helper 를 만든다(신규 판정 규칙 아님). 계산 경계:
- 각 거래일 시점**까지의 데이터만** 사용해 기존 국면 라벨 재현(미래 데이터 사용 금지).
- 최신 거래일부터 같은 라벨이 이어진 거래일 수를 역산.
- 최신 라벨이 계산 불가면 `0일`이 아니라 `자료 없음`.
- 저장 이력 시작점까지 같은 라벨이면 `N거래일 이상`.
- 별도 threshold·새 라벨 0.

**Q5. VIX 처리 → A구간 실측 후 결정.**
`MarketRiskVix` availability·as_of_date 실측 후, 기존 상태 기준으로 사용 가능하면 연결(기준일 표시), 아니면 Dashboard·PUSH 해석에서 **제외 + 자료 상태에 사유 표시**. 신규 stale threshold·source 필요하면 만들지 않고 제외(§8 금지). **지금 답 불필요.**

---

## 4. 개발 범위 (설계서 §6·§7·§9.1)

1. **공통 판단 요약 composer (server-side · 신규 모듈, Q3)**: 기존 KOSPI/KODEX200/VIX/Holdings/Market Evidence read 조합 → §6.2 시장 위치(Q1 값 포함) + §6.3 보유 요약 최대 3건(Q2 규칙) + §6.4 자료 상태를 **한 번 계산**. market_context read 응답과 push_context 가 동일 결과 사용(§6.1·AC-2·AC-7).
2. **KOSPI 관찰값 산출**: 저장 series 로 Q1 4값 계산(신규 source 0). 국면 지속 거래일 수 = Q4 helper.
3. **오늘의 투자 점검 연결**: KOSPI `개발 중` 4항목 실제값 교체 + 공통 요약 한 문장. 보유 요약 최대 3건·확인 근거/데이터 상태 이동(§7.1). 거래량·공격방어·SuperTrend 보드 제거.
4. **PUSH 문구 재구성**: `market_briefing`·`holdings_briefing` 본문 앞부분 공통 요약 재구성(문구만, 종류·스케줄·승인·OCI·중복차단 불변 · AC-16·17).
5. **VIX 처리**: Q5 실측 결과 반영(§8·AC-10).

---

## 5. 개발 게이트 계획 (설계서 §10 · 확인 주체 정정 반영)

1. PLAN 확정(Q1~Q4 반영 완료) → **PLAN_V2 단독 커밋** → A구간 착수.
2. **A구간 (개발자 focused 확인)** — VIX 실제 상태(Q5) + composer 입력 계약 충돌 여부만 확인(§2 전수 재조사 금지).
3. **B구간 (개발자 focused 확인)** — 공통 시장·보유 요약 + 자료 상태 산출(Q1~Q4 반영). backend composer + 백엔드 보유 선택 규칙. 전환 테스트로 Dashboard/PUSH 동일성 고정.
4. **C구간 — 사용자 Dashboard 실화면 확인 필수** — 오늘의 투자 점검 연결 + 사용자 10초 과업(시장 위치·확인할 보유 ETF·자료 문제 구분).
5. **D구간 — preview·Dashboard 정합성 검증** — 두 PUSH preview 연결, Dashboard와 값·ticker·기준일 대조.
6. **E구간 — 사용자 승인 후 실제 Telegram 수신 확인** — 사용자 명시 승인 후 `market_briefing`·`holdings_briefing` 를 각각 1회 **실제 Telegram 수신**. **Preview 만으로는 PASS 아님. preview ≠ Telegram message_text 면 PASS/CLOSED 아님(§10).**
7. 전체 검증(AC 1~20) → RESULT·STATE·통합지도 Closeout.

각 구간 개발 → (C는 사용자 Dashboard, E는 사용자 실제 수신) 확인 → 커밋. 결과서까지 만든 뒤 push.

---

## 5-A. A구간 실측 결과 (2026-08-03 · 개발자 focused 확인 완료)

### A-Q5. VIX 처리 → **연결 확정 (기준일 명시)**
`app/market_risk_reference_service.py` `_build_vix_card` 실측:
- VIX read = `market_benchmark_daily_price`(id `VIX`), SQLite-only. `availability="available"|"unavailable"`·`as_of_date`·`close`·`change_1d/5d` 계약 제공.
- **런타임 실측**: VIX `available` · as_of_date `2026-07-03` · close `15.81` · series `2014-04-08~2026-07-03`. KODEX200 as_of `2026-07-24`.
- **판정**: 기존 상태 기준으로 **사용 가능 → 연결.** 단 VIX 기준일(2026-07-03)이 KODEX200(2026-07-24)보다 오래됨 → **VIX는 자기 기준일과 함께 표시**하고, 오래된 VIX가 사용 가능한 KOSPI·KODEX200·Holdings 요약을 오염시키지 않는다(§8·AC-10).
- 신규 stale threshold 신설 없음 — 기존 `as_of_date` 비교만 사용(프론트 정비 큐가 이미 `vix.as_of_date < kodex.as_of_date` 로 "오래됨" 표시). 신규 source·CSV·API key 0.

### A-composer 입력 계약 충돌 여부 → **충돌 없음**
- 5개 입력(KOSPI `api_price_series`/benchmark read · KODEX200·VIX `market_risk_reference` · Holdings enriched · Market Evidence latest) 모두 **저장값 read 계약**이 명확(availability/status·as_of_date·close/수치). composer 가 조합만 하면 됨 — 신규 endpoint·DB·source 불요.
- **최대 3건 "오늘 먼저 볼 보유 ETF" 는 현재 어느 화면에도 렌더되지 않음**: `lowestFiveDayRows`(프론트 순수 함수)는 **테스트에서만 참조**되고 `.tsx` view 렌더 0. PUSH `push_context_holdings` 의 `review_points[:3]`(L228)은 **텍스트 리뷰포인트 slice**로 5일-낮은-순 ETF 선택과 다른 개념.
  → 즉 §6.3/AC-6 "최대 3건"은 **composer 가 처음이자 단일 산출처**가 된다. Dashboard·PUSH 별도 계산 통일(Q2)의 대상이 명확. **§11.4(화면별 파생 산식 필요)·§11.8(값 불일치) 미해당** — 오히려 composer 도입으로 단일화.
- 결론: A구간 어떤 §11 복귀조건도 미해당. B구간(공통 요약 composer + KOSPI 관찰값 + 지속일 helper) 착수 가능.

---

## 6. 설계자 복귀 조건 감시 (설계서 §11)

§11 1~10 중 하나라도 걸리면 자체 판단 없이 복귀. Q1~Q4 는 설계자 확정으로 §11.1~11.4·11.8 경계가 "additive read 조합 + 신규 composer 모듈(endpoint·DB 아님)"로 정해졌으므로 미해당. 다만 구현 중 (8) Dashboard/PUSH 값·ticker·기준일 불일치가 실제로 발생하거나, (3) composer 가 신규 endpoint·DB·source 를 요구하게 되면 즉시 복귀.

---

## 7. 하지 않는 것 (설계서 §9.2 재확인)

신규 endpoint·DB·table·cache·source·proxy / 시장 알고리즘·상태 정의·등급·threshold / Dashboard용·PUSH용 별도 계산 / signal·rank 저장 / 신규 메뉴·화면·route / 거래량·공격방어·SuperTrend / 급락 latest read 계약 / ML·백테스트 / BUY·SELL·주문 / PUSH 종류·스케줄·승인·OCI·중복차단 변경 / 모바일 UI — 전부 안 함.

문서 끝.
