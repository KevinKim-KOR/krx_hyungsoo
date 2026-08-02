# POC3-05 Holdings Risk Evidence Foundation V1 — 개발 PLAN

* 문서 종류: 개발 PLAN (모호점 질문 포함 · 설계자 회신용)
* 대응 설계서: `docs/ai_design/POC3/POC3-05_HOLDINGS_RISK_EVIDENCE_FOUNDATION_V1_DESIGN_V1.md`
* 작성일: 2026-08-02
* 기준 revision: `026e6cd0` (선행 승인·알림 역할분리 PASS/CLOSED)
* 상태: **개발 PLAN 확정 (설계자 Q1~Q7 답변 + 레드팀 PASS 반영, 2026-08-02).** PLAN 먼저 커밋 후 B구간 착수(A=계약 확정 = 본 사실확인+Q반영으로 완료).
* 레드팀: **PASS** (별도 revision 식별자 없음 — 사용자 확인 2026-08-02).
* 성격: 기존 evidence **읽기 전용 재사용**. 신규 API·DB·source·factor·formula·threshold·label 0건(설계서 §8·§9-13). 위험 구간 분류 모델 아님(§2.1).
* 용어: 사용자 화면·본 PLAN 전반에서 "기존 주식 신호" → **"기존 주의 신호"** 통일(설계자 지시).

---

## 0. 기반 문서 확인 완료

- `STATE_LATEST`(= 승인·알림 역할분리 CLOSED · 이 설계서가 다음 Step) · `PROJECT_ORIGIN_INTENT` · `KILL_SWITCHES` 확인.
- 사용자 화면 명칭 = **`보유 ETF 확인 근거`** (내부 Risk Evidence). `위험`·`손절`·`매도` 등 금지어(§3.1) 미사용.
- Evidence 사용 경계(§4)·경계값 재계산 금지(§3.3 -10%·§3.4 MA20/60) 확인.

---

## 1. 개발 전 사실 확인 결과 (설계서 §6 — 실측 완료)

### 1.1 종목별 evidence는 이미 한 번에 조회됨 (N+1 없음) [확인]
`GET /holdings/market-evidence/latest` → `HoldingsMarketEvidenceResponse` (`lib/api/holdings.ts:211`):
- `holdings: HoldingsMarketEvidenceItem[]` — **종목별 배열 1회 조회** (AC-12 N+1 없음 충족 가능).
- 각 item(`:180`): `ticker`·`name`·`account_group`·`holding{quantity·avg_buy_price·evaluation_amount·pnl_rate_pct}`·`topn_match`·`returns`·`excess_return`·`short_term_momentum`·`constituents_overlap`·`nav_discount`·`evidence_notes`.
- `summary`: total/matched_topn/not_in_topn/evidence_unavailable/constituents/nav_discount 카운트.
- `asof`·`holdings_asof`·`market_asof` 별도 제공.

### 1.2 §4 계약 필드 실측 대조 [확인]
| 설계서 §4 항목 | 실제 필드 (실측) | 상태 |
|---|---|---|
| 평가금액·평가수익 | `holding.evaluation_amount`·`holding.pnl_rate_pct` (evidence) / `EnrichedHolding.eval_amount·pnl_rate_pct·buy_weight_pct·market_weight_pct` (enriched) | DIRECT |
| 5일·20일 흐름 | `short_term_momentum.return_5d_pct`·`return_20d_pct` (+`return_10d_pct` 도 존재) | DIRECT |
| KODEX200 대비 20일 | `short_term_momentum.excess_vs_kodex200_20d_pctp` (종목별 evidence · +5d/10d 도 존재) | DIRECT |
| 데이터 상태 | 각 payload `status`: ok/partial/unavailable + `returns/excess_return/short_term_momentum` 별 status | DIRECT (구분) |
| 기존 주의 신호(급락) | **§1.3 참조** | Q1 확정: exact match 1건 |

### 1.3 급락(Falling) 신호 — 자동 조회 GET 계약 부재 → 이번 Step 제외 [확인]
- **실측: falling 을 확인 근거 화면에서 자동 조회할 read 계약이 없다.**
  - `GET /universe/momentum/latest` = 정책상 **미도입**(`universeMomentum.ts:3` "신규 endpoint 추가 금지 — GET /universe/momentum/latest").
  - `falling_candidate` 는 **`POST /universe/momentum/refresh`(refreshUniverseMomentum) 응답에만** 존재 — 사용자가 UniverseRefreshPanel 갱신 버튼을 눌러야 생김.
  - holdings market-evidence 엔 falling 필드 **없음**. `universe_falling` factor_signal 은 draft_payload 안에만(run 생성 시).
- **설계자 정정**: 급락 주의 신호 영역·열·빠른 보기를 **이번 Step 에서 전부 제외.** 조회 못 한 상태를 `0건`·`일치 없음`·`정상` 으로 표현하지 않는다. POST refresh 응답·화면 캐시 재활용 금지. **신규 API·계산·데이터 계약 추가 금지.** → BACKLOG(§10.4).
- 이번 Step 표시 범위 = **5일·20일 흐름 · KODEX200 대비 20일 · 평가액·비중·손익률 · 자료 확인 필요.**

### 1.4 화면·경로 [확인]
- `오늘의 투자 점검`(TodayInvestmentCheckView) 은 이미 evidence 를 받고 "내가 가진 ETF 중 확인할 종목 = 개발 중" 으로 표시(`:14`). 이번 Step 이 그 "개발 중" 을 실제 구현.
- `HoldingsClient`(내가 가진 ETF) = 입력·저장. `JudgmentWorkbenchView` = 읽기 전용 판정. 선택 상세 가격 차트 = lazy 조회(POC3-02 계약).
- menu key·화면 전환 경로 재사용, 신규 route·독립 화면 없음(§5.4).

### 1.5 coverage·N+1 [확인]
- evidence `holdings[]` 1회 조회로 종목별 채움 → N+1 없음.
- coverage = `summary` 카운트 + 각 item status 로 "계산 가능 N/M · 확인 불가 K"(§4) 구성 가능.

---

## 2. 구현 방침 (설계자 확정 반영)

### A구간 — Evidence 계약 확정 (§7-A · 별도 코딩 아님)
- 본 §1 사실확인 + §3 Q1~Q7 확정으로 Evidence 계약 확정 = **A 완료**(설계자: A는 별도 코딩 구간 아님). §4 항목별 `DIRECT / COMPOSE_SAME_SEMANTICS / UNAVAILABLE` 는 §3-A 표.
- Falling 연결은 source 존재(§1.3) → UNAVAILABLE 아님. 핵심 Holdings evidence 완비 → BLOCKED 아님.

### B구간 — `내가 가진 ETF` 확인 근거 (§7-B · 사용자 확인 게이트)
- HoldingsClient/HoldingsView 에 **읽기 전용 "보유 ETF 확인 근거" 영역** 추가(입력·저장 영역과 시각·문맥 분리, evidence 수정·저장 기능처럼 보이지 않게).
- **ticker별 한 줄 통합**(Q7): 기존 `aggregateHoldingsByTicker` 의미 재사용. 동일 ticker 의 evidence 값·기준일이 계좌 행마다 다르면 임의 선택 없이 그 ticker 를 `자료 확인 필요`.
- 요약(기준일·coverage·자료 확인 필요) + 빠른 보기(전체 / 자료 확인 필요) + 고밀도 표: ETF명·ticker · **평가금액·평가 비중(`market_weight_pct`)·손익률**(enriched) · **5일·20일·KODEX200 대비 20일**(evidence short_term_momentum) · 기준일 · 데이터 상태. `buy_weight_pct` 제외(Q6). **급락 주의 신호 열·빠른보기 없음(§1.3 제외).**
- 선택 상세: 가격 차트(lazy) · NAV·구성종목·중복률 · unavailable 사유. **NAV/구성종목/topn 의 unavailable 은 여기서만, 목록 확인필요 판정에 미포함(Q4).**
- `최근 흐름 낮은 순` = 유효 5일 수익률 로컬 정렬(위험 점수/저장 rank/signal 아님, AC-4).

### C구간 — Dashboard·Workbench 연결 (§7-C · 사용자 확인 게이트)
- `오늘의 투자 점검`의 "내가 가진 ETF(개발 중)" 실제 구현: 최근 5일 낮은 최대 3건(중복 ticker 제거 후, Q5·Q7) + 자료 확인 필요 건수 + 기준일·coverage + `보유 ETF 확인 근거 보기`(Holdings 이동). **급락 신호 제외.**
- Workbench 는 동일 ticker·snapshot 이면 같은 값·상태 표시(별도 계산 없음).

### 테스트
- coverage/자료확인필요 분리(Q4 기준) · 5일 정렬(로컬·유효분) · unavailable 0/정상 위장 금지 · 금지어(위험/고위험/손절/매도/청산/BUY/SELL) 비노출 · N+1 없음(2 endpoint 단일 조회) · ticker 통합 · 3화면 동일 값 · **급락 신호 열·빠른보기 비존재(제외 확인)**.

---

## 3. 설계자 확정 답변 (2026-08-02)

| 질문 | 확정 판단 |
|---|---|
| Q1 | **정정: 급락 신호 이번 Step 제외 → BACKLOG.** falling 을 자동 조회할 GET 계약이 없어(§1.3 실측) 표시 범위에서 뺀다. 0건·일치 없음·정상으로 표시 안 함. POST refresh 응답·화면 캐시 재활용 금지. 신규 API 안 만듦. (앞서 exact match (a) 답변은 자동 조회 GET 부재를 반영 못 한 것으로 설계자 정정.) |
| Q2 | **(a) 미사용.** `topn_match`(상승 후보 매칭)는 "보유 ETF 확인 근거"에 섞지 않음. |
| Q3 | `return_5d_pct`·`return_20d_pct`·`excess_vs_kodex200_20d_pctp` 사용. **10일 값 미표시.** |
| Q4 | 아래 **핵심 표시값 기준**으로 판정. NAV·구성종목·topn 상태는 목록 판정에 미포함. |
| Q5 | `status=ok` & 5일 값 유효 ticker만 오름차순, 동률 ticker 오름차순, 최대 3종목. |
| Q6 | **(b) evidence + enriched 둘 다.** 평가 비중은 설계 필수 → 생략 금지. |
| Q7 | **행 단위 기각 · ticker별 한 줄 통합**(`aggregateHoldingsByTicker` 의미 재사용). |

### 3-A. Evidence 계약 확정표 (§7-A · DIRECT/COMPOSE/UNAVAILABLE)
| 표시 항목 | source · 필드 | 분류 |
|---|---|---|
| 평가금액 | enriched `eval_amount` | DIRECT |
| 평가 비중 | enriched `market_weight_pct` (`buy_weight_pct` 제외) | DIRECT |
| 손익률 | enriched `pnl_rate_pct` | DIRECT |
| 5일 흐름 | evidence `short_term_momentum.return_5d_pct` | DIRECT |
| 20일 흐름 | evidence `short_term_momentum.return_20d_pct` | DIRECT |
| KODEX200 대비 20일 | evidence `short_term_momentum.excess_vs_kodex200_20d_pctp` | DIRECT |
| 데이터 상태 | evidence `short_term_momentum.status` + enriched `price_missing/calc_missing` | DIRECT (Q4 조합) |
| ticker 통합 | `aggregateHoldingsByTicker` 의미 | COMPOSE_SAME_SEMANTICS |
| 선택 상세 NAV/구성종목/중복률 | evidence `nav_discount`·`constituents_overlap` | DIRECT (상세 전용, 목록 판정 제외) |
| ~~기존 주의 신호(급락)~~ | ~~falling_candidate~~ | **UNAVAILABLE — 자동 조회 GET 계약 부재 → 이번 Step 제외(§1.3·§10.4)** |

### 3-C. Q4 `자료 확인 필요` 판정 기준 (핵심 표시값만)
핵심 표시값: enriched `eval_amount`·`market_weight_pct`·`pnl_rate_pct`·`price_missing`·`calc_missing` + evidence `short_term_momentum.status`·`return_5d_pct`·`return_20d_pct`·`excess_vs_kodex200_20d_pctp`.
다음 중 하나라도 해당 시 `자료 확인 필요`:
- `short_term_momentum.status` 가 `partial` 또는 `unavailable`
- 세 흐름 값(5일/20일/KODEX200 대비) 중 하나가 null·무효
- `price_missing=true` 또는 `calc_missing=true`
- 평가액·평가 비중·손익률 중 하나가 계산 불가
- 조회 자체가 `not_loaded` 또는 실패
`partial` 이면 존재 수치는 그대로 보여주되 상태는 `자료 확인 필요` 유지. **NAV·구성종목·중복률 unavailable 은 선택 상세에서만, 목록 판정 미포함**(선택 참고자료 부족으로 멀쩡한 핵심 흐름까지 확인 불가로 분류 방지). **새 날짜 threshold 로 stale 판정 안 함** — 기존 계약이 stale 직접 제공할 때만 사용.

### 3-D. Q6 조회 원천
- 평가액·평가 비중(`market_weight_pct`)·손익률 = `GET /holdings/enriched`.
- 5일·20일·KODEX200 대비·상태 = `GET /holdings/market-evidence/latest`.
- 2 endpoint 조회 허용(ticker별 호출 아님 → N+1 아님). 기존 queryCache 공유. **서로 다른 기준일은 합치지 않고 각각 유지.**

### 3-E. Q7 ticker 통합
- 확인 근거 표·Dashboard·Workbench = ticker별 통합. 입력·수정 화면은 계좌·매입 행 그대로.
- 평가 관련 값 = `aggregateHoldingsByTicker` 동일 의미. 단기 흐름 = 같은 ticker 의 동일 시장 evidence 1회.
- Dashboard 최대 3건도 중복 ticker 제거 후 선정.
- **동일 ticker 의 evidence 값·기준일이 계좌 행마다 다르면 임의 선택 없이 그 ticker 를 `자료 확인 필요`.**

---

## 4. 개발 완료 후 산출물(예정)

- 수정: `HoldingsView`/`HoldingsClient`(확인 근거 영역) · `TodayInvestmentCheckView.tsx`(개발 중 → 실제) · evidence 표시 하위 컴포넌트 신설 · `JudgmentWorkbenchView`(동일 의미) · `globals.css` · 테스트.
- 백엔드·API·DB·source·factor·threshold·label·화면 전환 key **무변경**.
- 결과서: `docs/ai_result/POC3/POC3-05_HOLDINGS_RISK_EVIDENCE_FOUNDATION_V1_RESULT.md`.
- 통합지도(P-06·B-003)·STATE 정정은 **최종 Closeout**(§11).

---

## 5. 착수 계획 (확정)

1. **PLAN 먼저 커밋** (개발과 분리). 레드팀 PASS revision 기록 후.
2. **A구간 = 본 사실확인 + Q1~Q7 확정으로 완료**(별도 코딩 아님 — 설계자 명시).
3. **B구간 착수**(내가 가진 ETF 확인 근거) → 사용자 확인(1·2·3).
4. B 통과 후 **C구간**(Dashboard·Workbench 연결) → 사용자 확인(4·5·6).
5. C 통과 후 전체 검증 → 최종 PASS → 통합지도·STATE Closeout.

착수 전 소스 미수정. **BLOCKED 아님**(핵심 Holdings evidence 단일 조회 완비). **급락 신호만 자동 조회 GET 계약 부재로 이번 Step 제외**(§1.3·§6) — 개발 전체 중단 사안 아님, 나머지 범위로 B·C 진행.

---

## 6. BACKLOG 추가 (설계자 확정)

**급락 주의 신호 — 보유 ETF 일치 표시 (자동 조회 read 계약 부재)**
- 급락 신호는 자동 조회 가능한 GET 계약이 없어(GET latest 미도입 · falling_candidate 는 POST refresh 응답에만) POC3-05 표시 범위에서 제외한다. 조회하지 못한 상태를 `0건`·`일치 없음`·`정상` 으로 표현하지 않는다. 이번 Step 에서 신규 API 를 만들지 않고 나머지 기존 evidence 로 진행한다.
- **보류 사유**: 자동 조회용 read 계약 부재.
- **보류된 위험**: 보유 ETF 와 기존 급락 후보의 일치 여부를 화면에서 확인할 수 없음.
- **재검토 트리거**: 급락 후보의 안정적인 latest 저장(조회) 계약이 확인되고, 보유 판단 화면에서 필요성이 실제 운영으로 입증될 때.
