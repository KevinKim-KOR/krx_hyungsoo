# POC6-27 개발 PLAN V1 — 「오늘의 투자 점검」 개편

작성 2026-11-09 · 작성자: 개발자(VSCode Claude) · 수신: 설계자

```text
STATUS = PLAN 제출 → 설계자 판정 PASS_WITH_REQUIRED_CORRECTIONS(2026-11-09 · Q1 ~ Q11 선택 · 필수 보완) → 이 PLAN 에 반영 완료(§2 · §3 · §4 · §7 · §8)
         → 격리 작업 사본에서 구현(§8)
PLAN 판정 = docs/ai_design/POC6/POC6_27_TODAY_CHECK_REVISION_PLAN_DECISION_2026-11-09.md(이 PLAN 보다 우선)
DESIGN = docs/ai_design/POC6/POC6_27_TODAY_CHECK_REVISION_DESIGN_V1.md(설계자 「개발 PLAN 작성 기준서」 원문 보관)
MOCKUP = docs/ai_plan/POC6/POC6_27_TODAY_CHECK_REVISION_MOCKUP.html(이 PLAN 기준 화면 전체 · 11/9 실제 값 · 보유 종목명 · 금액 가림 · [Q…] 표시는 실화면에서 뺌)
범위   = 기준서 §0 다섯 쟁점 + 판정 §4 필수 기준. 저장 자료의 재배치와 기존 동작의 연결.
사용자 결정 = ① KOSPI 차트는 시장 흐름 안 코스피 수치 바로 아래 · 외국인 수급 위(2026-11-09 · 기준서 §0 · §1-4 반영)
              ② 「자료 최신화 필요」 · 「OCI 운영 스케줄 확인」 두 카드는 기본 접힘 · 필요할 때 펼침(2026-11-09 목업 확인 뒤 · 기준서 이후 결정)
              ③ '최근 큰 변화'는 시장 흐름에 바로 보이게(외국인 수급 아래 · 지금 화면처럼 늘 보임 · 2026-11-09 목업 확인 뒤)
```

## 0. 기반 문서 대조

- 목적: 주간 검토 화면의 읽기 순서 정리. 새 점수 · 등급 · 매매 신호 · 자동 갱신 · 자동 주문은 만들지 않는다(PROJECT_ORIGIN_INTENT · 기준서 범위).
- 외부 조회 · 새 의존성 · DB 표 변경 · OCI 쓰기 · Telegram 발송: **0**. 백엔드는 기존 계산 결과를 응답 칸으로 더 내보내는 것과, PC 원장 사본 읽기 1개만 바뀐다.
- KS-10(파일 크기):
  - `MarketDiscoveryView.tsx`는 871줄로 **근접(≥850)** 상태다. 쟁점 5에서 시장 갱신 로직을 공용 hook으로 빼서 줄인다.
  - `supply_fx_oil_context.py`는 576줄이다(백엔드 근접 600). 새 칸 조립은 새 작은 모듈에 둔다.
  - 그 밖에 바뀌는 파일은 모두 임계에서 멀다(실측은 §6).
- 열린 가정(ASSUMPTIONS Q1 ~ Q3)과는 연관이 없다.

## 1. 지금 호출 경로(읽기 전용 대조 · 2026-11-09)

| 동작 | 지금 경로 | 근거 |
|---|---|---|
| 화면 진입(8개 GET) | ① 시장 판정 · 목록 `GET /market/topn/latest?n=10&basis=one_month&order=desc&exclude_*=true`(고정 키 `DASH_KEY_MARKET`)<br>② `/holdings/enriched`<br>③ `/holdings/market-evidence/latest`<br>④ `/market/nav-discount/latest`<br>⑤ `/market/price-series?benchmark=KOSPI`<br>⑥ `/market/flow-context`<br>⑦ `/ml/forward-comparison`<br>⑧ `/oci/startup-status`(백엔드 기동 때 1회 읽은 캐시) | `TodayInvestmentCheckView.tsx` · `OciStatusOneLine.tsx` |
| [요약 다시 읽기] | ⑤ · ⑥ · ② · ③ · ④ · ⑦을 강제로 다시 읽는다. ① · ⑧은 다시 읽지 않는다. 6개 조회 실행 추적에서 외부 연결 · 쓰기 0을 확인했다(11/9). | 같은 파일 `onSummaryReload` |
| [업데이트](보유 현재가) | `POST /holdings/market/refresh`(보유 종목 시세 · 네이버) → ② · ③ · ④를 다시 읽는다. 응답 `ok_count` · `fail_count`는 지금 화면에서 쓰지 않는다. | `onLightRefresh` · `lib/api/holdings.ts` |
| 시장 갱신 | 「요즘 잘 오르는 ETF」에만 있다. `POST /market/refresh` → `GET /market/refresh/status` 반복 조회 → 완료 때 `MARKET_INVALIDATION_KEYS` 무효화 + 다시 읽기. 상태는 running · completed · failed · skipped_cooldown · idle이다. **화면을 떠나면 반복 조회가 멈추고, 돌아와도 진행을 이어받지 않는다.** VIX 다시 받기와 겹치는 경우를 처리한다. | `MarketDiscoveryView.tsx` 290 ~ 432 |
| 시장 흐름 응답 | 구조값: `periods`(1M · 3M · 6M · YTD · `kospi` from/to/diff/pct · `investors` sum/days/expected/partial) · `series`(kospi · usdkrw · wti 전체 점 · E · collected_at) · `status[]`(자료별 E) · `end_basis`(D · kospi_E · flows_E · limited_by)<br>**문장만 있는 것**: `short_lines[]`(text · flags), `events[]`(date · series · kind · text), `windows`(lines · trend 문장) | `supply_fx_oil_context.py` · `supply_fx_oil_calc.py` |
| 시장 판정 응답 | `market_context.kospi`: return_20d_pct · return_60d_pct(거래일 축) · daily_return_pct · as_of_date · display_state<br>`regime_code` · `regime_label` · `regime_streak` · `asof`<br>판정 입력은 KODEX200 · KOSPI 저장 이력뿐이라 목록 조건(기간 · 정렬 · 제외)과 무관하다. | `market_topn.py` 339 ~ 375 |
| OCI 기동 상태 | 기동 때 SSH 읽기 1회. 응답은 overall · summary_line · jobs(문장) · note다. **예약된 알림 종류 목록은 저장하지 않는다**(판정에만 쓰고 버림). | `oci_startup_status.py` 165 ~ 297(`refresh_snapshot`) · `api_oci_startup_status.py` |
| PC 알림 원장 | `GET /decision-ledger/alerts?date&kind`는 **보냄 · 일부 보냄만**, 날짜를 안 주면 사본의 가장 최근 하루만 돌려준다(건너뜀 · 실패 제외). `sync`는 has_copy · last_success_at · last_failure_*다. 새로고침은 `POST /decision-ledger/sync`(사용자 버튼 · OCI SSH 1회). 사본 마지막 성공: 10/23 14:27 KST. | `ledger_copy/views.py :: list_alerts` |
| 국내 기대 기준일 | `trading_day_lag.expected_previous_trading_day(today_kst, calendar_dir)`: 직전 거래일(T-1)을 달력으로 정하고, 달력이 없는 해는 평일로 대신한다. KOSPI 화면 판정(`kospi_freshness` · 정확 일치)이 이미 쓰고 있다. | `trading_day_lag.py` 178 · `market_benchmark_freshness.py` 148 |
| 미국 기대 기준일 | `pc_vix_refresh.vix_freshness`: 미국 동부 16:30 마감이 지난 마지막 평일과 비교한다. 상태는 fresh · one_weekday_behind · update_check · date_check이다. 화면은 앞의 둘이면 안내를 내지 않는다. | `pc_vix_refresh.py` 48 |
| 원/달러 · WTI 날짜 | 화면 한계 문구 기준: 원/달러는 Yahoo KRW=X 일봉의 **런던 날짜**, WTI는 Yahoo CL=F의 **뉴욕 날짜**다. 수급은 키움 ka10051, 정수 원 단위다(억원 반올림 원천). | `supply_fx_oil_context.py` LIMITS |

## 2. 화면 배치(위 → 아래 · 판정 반영)

| 순서 | 내용 | 지금 구성요소에서 |
|---|---|---|
| 1 | 제목 · [요약 다시 읽기] [?] [보유 현재가 업데이트] [최신 시장 데이터 갱신] · 그 아래 작은 글씨로 실제 읽은 시각 · 다시 읽기 결과(Q8 (a)) | 부제 삭제. 늘 보이던 안내 문장은 [?] 안으로 옮김. OCI 한 줄은 3번 카드로 옮김. |
| 2 | 자료 최신화 필요(대상이 있을 때만) · **기본 접힘(사용자 결정 ②)** | 쟁점 2의 판정 결과 + 바로 조치할 확인 실패(Q2 (a) 보완). 접힌 줄은 제목 · 건수 요약 · [펼치기]. 요약은 지연 정도가 모두 같으면 'N건 · K거래일 늦음', 섞이면 '늦음 N건 · 기준 확인 필요 M건'(판정 §2). 펼치면 자료별 마지막 날짜 · 기대일과 기준 · 사유 · 해당 갱신 버튼. |
| 3 | OCI 운영 스케줄 확인 · **기본 접힘(사용자 결정 ②)** | 쟁점 3. 접힌 줄은 '예약 n/3 확인'(누락 · 확인 불가는 따로 셈) · 발송 한마디(Q6) · [펼치기]. |
| 4 | 지금 확인할 내용 › **시장 흐름**: 판정 배지 · KODEX 200 기준일 · [AI용 시장 정보 복사] → 코스피 종가 줄 · 저점 문장 → 20 · 60거래일 · 6개월 칸 → **KOSPI 차트(기존 `KospiChart` · 최근 최대 120개 저장일 · 기간 줄 · Q9 (a))** → 외국인 수급 → **최근 큰 변화(늘 보임 · 사용자 결정 ③)** → [시장 근거와 다른 변화 보기](Q1 (a) 나머지 지표 · 원/달러 · WTI · 사건 전체 · 자료별 기준일)<br>그 아래 **보유 점검 \| 잘 오르는 ETF** 두 칸 | `SummarySection`의 시장 줄을 새 `MarketFlowBlock`으로 바꿈. 기존 `KospiHeadline` 카드는 차트가 빠진 채 펼침 안으로 들어감. |
| 5 | 자료 확인 · 연구 | 기존 dataRow · researchRow + 「자료 확인」 펼침 목록(구성종목 · NAV · VIX 등 기존 정비 항목 · 기존 사유 · 이동 버튼 · Q2 (a)) |
| 6 | 보유 자세히 \| 잘 오르는 ETF 자세히(좌우) | `JudgmentQueueSection`을 두 칸으로 나눔. 보유 쪽은 실제 종목명 · 선정 이유, ETF 쪽은 같은 응답의 앞 3개(쟁점 4). |
| 7 | 현재 제공 범위와 남은 기능(접힘) | 그대로 |

- **두 카드 접힘**: 펼침 상태는 「현재 제공 범위와 남은 기능」처럼 화면 안 상태만이다(저장 없음 · 다시 들어오면 접힘).
- **최근 큰 변화(사용자 결정 ③ · 판정 §2)**: 지금 서버 줄(`today_lines[1]`)과 같은 고르기 규칙(최신순 2건 · '외 N건' · `event_check` 문구)을 쓴다.
  - **상단 저점 문장을 실제로 표시했고**, 코스피 범위 이탈 사건의 발생일 · 방향 · 비교일 · 기준값이 저점 문장과 **모두 일치할 때만** 그 1건을 빼고 고른다. 같은 날의 다른 종류 사건은 그대로 둔다.
  - 문장은 날짜와 변화를 먼저 쓴다. 예: '11/5 코스피 종가 5,383.80이 10/26 저점 5,469.47을 밑돌았습니다', '11/4 WTI가 7.97달러 하락했습니다 · 평소 변화의 3.4배'.
  - 11/9 사례는 7 − 1 − 2 = **외 4건**이다. 관측 개수 · 중복 제외 개수와 전체 사건은 [시장 근거와 다른 변화 보기] 안과 AI 원문에 남긴다.
  - 사건이 없으면 기존 `empty_text`다. 구조 칸이 없는 옛 응답이면 기존 원문 줄에 '괄호 안 = 비교 기준값' 안내를 붙여 보인다.
- **차트 기간(Q9 (a))**: 기존 `KospiChart`의 최근 최대 120개 저장일과 기간 줄을 그대로 쓴다(기준서의 '시계열 전체'는 판정으로 정정).

## 3. 쟁점별 계획

### 쟁점 1 — 저점 · 외국인 일평균(시장 흐름 응답에 구조 칸 추가 · 기존 칸 · 문장 그대로)

- **재사용**: 계산은 이미 있다. 서버가 `short_term()`에서 d1 · d5 · range(bound · bound_date)를, `window()`에서 sum · avg · from · to를 만든 뒤 문장으로만 내보낸다. 이 dict를 그대로 응답 칸으로 붙인다(새 계산 없음 · 문장 파싱 없음).
- **최소 응답 필드**(모두 선택 칸 · 추가만):
  - `short_lines[]` += `key`(kospi · usdkrw · wti · foreign · institution) + `obs`
    - 가격 줄: `{date, value, unit, d1:{from_date, diff, pct}|null, d5:{…}|null, range:{dir, bound, bound_date}|null}`
    - 수급 줄: `{date, value, unit:"원", ratio, base_from, base_to, note}`
  - `events[]` += `key`, `value`(사건일 관측값), `unit`
    - 범위 사건: `dir`, `bound`, `bound_date`
    - 확대 사건: `delta`, `ratio`, `base_from`, `base_to`, `zero_base`
  - `windows` += `foreign20: {recent:{sum, avg, from, to}, previous:{…}}|null` + `r60: {foreign, individual, institution}`(각 `{sum, from, to}|null`). 단위는 원이다.
- **실제 종가와 비교 기준값 구분**: 화면 · 복사문은 '종가 = `obs.value`(그날)', '최근 저점 = `range.bound`(직전 20개 저장 종가 최저 · `bound_date`)'로 칸을 나눠 쓴다. 저점 문장은 `range.dir`이 '아래'일 때만 쓰고, '위'일 때는 '최근 고점을 넘었다'로 쓴다. '직전 거래일'이라는 말은 `bound_date`가 `d1.from_date`와 같을 때만 쓰고, 다르면 기준값의 실제 날짜(M/D)를 적는다(판정 §4).
- **그 밖의 값은 기존 구조 칸**:
  - 20 · 60거래일 = 시장 판정 응답 `market_context.kospi`(as_of_date 기준)
  - 6개월 = `periods['6M'].kospi`, 외국인 6개월 = `periods['6M'].investors.foreign`(partial이면 '부분 집계 n/m일')
- **호환**: 기존 text · flags · lines · trend · `ai_text` · `today_lines`는 한 글자도 바꾸지 않는다(같은 fixture로 이전 · 이후 문장이 같은지 시험). 새 칸이 없는 응답(옛 서버)은 화면이 문장을 해석하지 않고 해당 값을 '확인 불가'로 둔다.
- **파일**: 칸 조립은 새 모듈 `app/supply_fx_oil_fields.py`(약 80줄)에 둔다. `supply_fx_oil_context.py`는 호출 몇 줄만 늘어 약 590줄이다. 응답 모델(`api_supply_fx_oil.py`)은 기존 dict 칸이 그대로 통과하므로 바꾸지 않는다(새 최상위 칸은 `freshness` 하나 · 쟁점 2).

### 쟁점 2 — 자료별 최신성(서버가 기대일을 정하고 화면은 비교만)

- **최소 응답 필드**: `/market/flow-context`에 최상위 `freshness` 하나를 더한다. 계산은 새 모듈 `app/market_freshness_rows.py`(약 90줄)에서 기존 함수만 부른다.
  ```text
  freshness = {
    today_kst, expected_kr (국내 T-1 · expected_previous_trading_day), expected_kr_basis ("calendar" | "weekday_fallback" | null),
    items: [{key, label, last_date, expected, basis: "kr_t1" | "observed_only", state: "fresh" | "late" | "check" | "observed", behind, reason}]
  }   # items = 수급 · 원/달러 · WTI (KOSPI 는 기존 시장 판정 응답의 판정을 그대로 씀)
  ```
- **자료별 규칙(판정 §3 · §4 반영)**:

  | 자료 | 마지막 자료일 | 기대 기준일과 출처 | 판정 |
  |---|---|---|---|
  | 코스피 | 시장 판정 응답 `kospi.as_of_date` | 기존 `kospi_freshness`(국내 T-1 · 정확 일치) | 기존 kospiStatus 그대로(휴장일 · 지연 문구 재사용) |
  | 외국인 수급 | `status[flows].E` | 국내 T-1 | E ≥ 기대일이면 최신, E < 기대일이면 'n거래일 늦음'(기존 거래일 축으로 셈), 기대일을 못 정하거나 날짜가 깨지면 '기준 확인 필요' |
  | 원/달러(Q4 (a) 범위 한정) | `status[usdkrw].E` | 국내 T-1 — '국내 T-1 대비'라는 기준을 원/달러 실제 관측일(런던 날짜)과 나눠 적는다 | 수급과 같은 세 상태. 국내 휴장 중의 더 최근 값(E > 기대일)은 최신. 원천의 공표 · 수집 지연 원인은 추론하지 않는다. |
  | WTI(판정 §4) | `status[wti].E` | **없음** — VIX 마감 · 1평일 허용 규칙을 쓰지 않는다 | 'observed'(관측일만 표시). WTI 날짜만으로 지연 경고 · 확인 창을 만들지 않는다. 시장 흐름 응답 실패 · 자료 없음은 기존 확인 필요 처리. |
  | KODEX200 시장 판정 | 시장 판정 `asof` | `expected_kr` | 화면 비교(E ≥ 기대일) |
  | 보유 현재가(Q5 (a) 보완) | `/holdings/enriched` 행 `price_asof` | `expected_kr` | `price_source`가 `naver`인 행의 `price_asof`는 네이버 `localTradedAt` = 실제 체결 시각이다(`market_naver.py` 101 ~ 122). 그 KST 날짜가 기대일 이상이면 최신, 이전이면 늦음. 시세가 없거나 다른 출처 · 읽을 수 없는 시각이면 '기준 확인 필요'. 보유 근거 가격 기준일은 따로 표시한다. |
  | 보유 근거 가격 기준일 | `price_basis.reference_date` | `expected_kr` | 화면 비교 |
  | VIX | 기존 정비 기준(`vix_freshness`) | — | 그대로(「자료 확인」 목록 · 판정 §4) |
  | NAV · 구성종목 · 연구 | — | — | 기준서 §2대로 진행 여부를 묻는 조건에 넣지 않는다(「자료 확인」 줄에만) |

- **평일 대체 표시**: 기대일을 정한 해에 달력 파일이 없어 평일 대체를 썼으면 `expected_kr_basis = "weekday_fallback"`이고, 화면에 '평일 기준(달력 없음)'을 함께 적는다(판정 §4).

- **공통 비교 종료일**은 기존 `end_basis`(D · limited_by · 문장)를 그대로 '가격은 11/6까지, 수급과 함께 보는 비교는 11/5까지'에 쓴다. 최신성 판정과는 따로 표시한다.
- **수급 지연의 구조**: 수급은 OCI 수집본을 PC가 [최신 시장 데이터 갱신] 때 반영한다(POC6-17 · `flow_link`). 그래서 국내 T-1 기준을 쓰면 OCI 수집 · PC 반영 전에는 '늦음'으로 보인다. 11/9 사례의 늦은 원인(OCI 보관본이 11/8 17:18 반영 때 11/5까지였음 · `oci_flow_status` OK)은 이번 범위에서 조사하지 않는다(기준서 '지연 원인 확인 전').
- **확인 방법**: 기대일 계산에 쓰는 '오늘'과 달력을 주입할 수 있게 해서 fixture로 시험한다.
  - 11/9(월) → 기대 11/6, 수급 11/5 = 1거래일 늦음
  - 국내 휴장일 다음 날
  - 국내 휴장인 평일에 원/달러 E가 기대일보다 뒤 → 최신
  - 달력이 없는 해(평일 대체 · 기준 표시)
  - 기대일 None → 기준 확인 필요
  - 깨진 날짜
  - WTI는 날짜와 무관하게 'observed'(지연 판정 없음)

### 쟁점 3 — OCI 예약과 발송(두 줄 묶음 분리)

- **예약(기동 스냅샷 · 최소 변경)**:
  - 스냅샷에 `scheduled_kinds: list[str] | None`를 둔다. 이미 읽은 `crontab -l`의 `--push-kind` 목록을 버리지 않고 보관하는 것이고, 접속하지 못했으면 None이다.
  - 응답에 `schedule: [{kind, label, state: "registered" | "missing" | "unknown"}]` 3줄(시장 브리핑 · 보유 브리핑 · 장중 급등락)을 더한다.
  - 기존 overall · summary_line · jobs는 그대로 둔다.
  - **OCI 추가 접속 0.** 값은 백엔드가 다음에 기동할 때 채워진다.
- **발송(PC 원장 사본 · 새 읽기 1개)**:
  - 기존 `/alerts`는 건너뜀 · 실패를 빼고 하루만 주기 때문에, 설계 §5의 '장중 급등락 13:30 건너뜀'을 보일 수 없다.
  - 그래서 `GET /decision-ledger/latest-by-kind`를 더한다. 사본에서 종류별 마지막 FINALIZED 실행 1건(time_kst · delivery_status 원문 · status)과 `sync`를 읽는다. 사본 읽기만 하고 SSH는 없다.
  - 사본 최신화는 기존 「받은 알림 기록」의 [원장 새로고침]이 한다(이 화면에는 그곳으로 가는 이동만).
- **표시 규칙(Q6 (a) 정정)**: 종류마다 '오늘 기록'은 **사본 마지막 동기화가 오늘(KST)이고 그 종류의 실행 행 발생일(KST)도 오늘일 때만**이다. 같은 날 동기화했어도 실행 행이 과거면 과거 날짜의 기록이다.
  - 접힌 줄: 오늘 기록이 없으면 '발송 확인 불가'.
  - 펼친 곳: 실행 발생일시 · 실행 결과(서버 원문의 대응어 — sent 보냄 · partial 일부 보냄 · skipped 건너뜀 · failed 실패 · 그 밖은 원문) · 마지막 동기화 시각을 칸을 나눠 적는다. 예: '10/23 08:30 보냄' + '사본 동기화 10/23 14:27'.
  - 응답의 `today_kst`는 서버가 정한다.
- **실패 · 결측**:
  - 예약: OCI 접속 실패 · 환경 미설정이면 3줄 모두 '확인 불가'다. 확인 실패를 '누락'으로 세지 않는다(접힌 줄 '예약 0/3 확인 · 확인 불가 3').
  - 발송: 조회 실패('불러오지 못함')와 사본 없음(has_copy false · '사본 없음')을 다른 상태로 둔다. 발송 여부를 모르면 늘 [받은 알림 기록] 이동을 둔다.
- **확인 방법**: 스냅샷 파싱 단위 시험(전부 등록 · 하나 누락 · 등록 0 · 접속 실패)과 tmp 사본 DB 시험(보냄 · 건너뜀 · 일부 · 실패 · 사본 없음 · 같은 시각 정렬). 라이브 DB는 열지 않는다.

### 쟁점 4 — 확인 창 · AI 복사 · ETF 조건

- **확인 창 대상**
  - [요약 다시 읽기]: 코스피 · 수급 · 원/달러 · WTI · 보유 현재가 · 보유 근거 기준일
  - [AI용 시장 정보 복사]: 시장 판정 · 코스피 · 수급 · 원/달러 · WTI
  - NAV · 구성종목 · 연구는 넣지 않는다.
- **판정 시점(Q3 (a) 보완)**: 기존 6개 저장 자료 조회를 쓰되, 결과를 바로 반영하지 않고 받아 둔 뒤 판정한다. **사용자가 고르기 전에는 새 조회값 · 성공 시각을 화면 · 공유 캐시에 반영하지 않는다.**
  - 판정 대상: 받아 둔 6개 결과 + 화면에 함께 쓰는 **시장 판정 · 코스피 기간 수치의 기존 스냅샷**(①은 다시 읽지 않고 기준일만 대조 · OCI 다시 조회 없음).
  - 모두 최신이고 실패가 없으면 바로 반영한다.
  - 늦음 · 기준 확인 필요 · 조회 실패가 하나라도 있으면 창을 띄운다. 자료마다 마지막 저장일 · 기대 기준일과 기준(있을 때) · 사유를 한 줄씩 적는다. 조회 실패는 '불러오지 못함 · 남겨 둘 값의 기준일 · 실패 사유'로 적는다.
  - [이 자료로 계속]: 창에 제시한 **바로 그 결과**를 반영한다(다시 조회하지 않음). 실패한 원천은 지금처럼 이전 값 + 그 시각을 남기고 '다시 읽기 실패'로 표시한다. 해당 줄에는 기준일과 '늦음 · 기준 확인 필요' 표시를 남긴다.
  - [취소]: 받아 둔 결과를 버린다. **이전 화면 · 공유 캐시 · 성공 시각을 그대로 보존**한다. 상단 두 최신화 버튼은 그대로 누를 수 있다.
  - 창이 열려 있는 동안 [요약 다시 읽기] · [AI용 시장 정보 복사]는 다시 실행되지 않는다.
  - 공유 캐시(`queryCache.ts` 214줄)에 '캐시를 건드리지 않고 받기 · 받은 값 반영 · 실패 표시' 함수(약 30줄)를 더한다.
- **AI 복사**:
  - 새 `lib/todayMarketCopyText.ts`가 기준서 §6 고정 프롬프트(글자 그대로) + 근거 줄을 만든다. 근거 줄 형식은 §6 '이번 사례' 블록과 같고, 값은 시장 판정 응답 · 시장 흐름 구조 칸 · `freshness`에서 가져온다.
  - 빠진 값은 '확인 불가'로, 늦은 자료는 [자료 상태] 줄로 적는다.
  - 복사는 현재 화면 값으로만 한다(다시 읽기 없음).
  - 늦은 자료가 있으면 창을 띄우고, [이 자료로 계속]을 누른 그 클릭에서 복사한다.
  - 복사가 실패하면 기존 문구 '복사하지 못했습니다 — 아래 글을 직접 선택해 복사하세요.'와 함께 글 상자를 펼친다. 성공처럼 보이지 않게 한다.
  - 기존 「요즘 잘 오르는 ETF」 [AI Sessions로 넘기기]는 바꾸지 않는다.
- **ETF 조건 공유(기준서 §4 그대로)**:
  - 새 `lib/marketConditionStore.ts`(탭 메모리 · 저장 없음)가 기간 · 방향 · 제외 4종을 들고 있다.
  - 탭을 처음 열면 기존 저장 기본 기간(`readMarketBasisPref` · localStorage), 기본 방향 desc, 기본 제외 4종으로 시작한다.
  - 「요즘 잘 오르는 ETF」에서 조건을 바꾸면 store에 쓴다. 「오늘의 투자 점검」은 store 조건으로 `/market/topn/latest`를 조건별 키로 읽는다.
  - 무효화: 지금 `MARKET_INVALIDATION_KEYS`의 `DASH_KEY_MARKET`은 조건까지 든 키 전체(`…?n=10&basis=one_month…`)다. `invalidateQueries`는 그 문자열로 시작하는 키만 지우므로, 조건이 다른 키는 잡히지 않는다. 그래서 무효화 목록에 조건 키 공통 앞부분(`dashboard:market/topn/latest`) 하나를 더한다(`dashboardKeys.ts` 1줄).
  - 위 요약에는 실제 응답의 basis · order · filters · 기간을 적는다.
  - 아래 3개는 같은 응답의 앞 3개다. 오름차순이면 '수익률 낮은 순'으로 쓴다(판정 §4 · 지금 `candidateLabel`의 '상위'는 방향을 보지 않아 함께 고침).
  - 이동 버튼은 store 조건 그대로 「요즘 잘 오르는 ETF」를 연다. 조건 조회가 실패하면 '불러오지 못함'과 요청한 조건을 적는다. 다른 조건의 이전 목록을 대신 보이지 않는다(보인다면 그 목록의 실제 조건을 같이 적는다는 판정 기준은 이 선택으로 해당 없음).
  - 시장 판정 배지는 조건과 무관하다(§1 대조). 「ETF 비교하기」(n=30 · 자체 키)는 바꾸지 않는다.

### 쟁점 5 — 상단 최신화 버튼

- **[보유 현재가 업데이트]**: 기존 `onLightRefresh`(`POST /holdings/market/refresh` → ② · ③ · ④ 다시 읽기)의 위치와 이름만 바꾼다. 이번에 더하는 것은 다음과 같다.
  - 응답 `ok_count` · `fail_count`로 전건 실패('보유 현재가를 받지 못했습니다 n건')와 일부 실패('일부 실패 n건')를 나눠 표시한다(지금은 쓰지 않던 칸).
  - 끝난 뒤 보유 현재가 기준 시각(`price_asof` 최소 ~ 최대)을 보여 준다.
  - [요약 다시 읽기]와 서로 막는 지금 규칙은 그대로 둔다.
- **[최신 시장 데이터 갱신]**:
  - 「요즘 잘 오르는 ETF」의 시작 · 상태 반복 조회 · 완료 처리를 공용 hook `useMarketRefresh.ts`(탭 메모리 상태)로 옮긴다. 두 화면이 같은 hook을 쓴다.
  - 화면 진입 때 `GET /market/refresh/status` 1회로 진행 중인 갱신을 이어받는다(**지금 「요즘 잘 오르는 ETF」 동작도 같이 바뀜 · Q7**).
  - 실행 중 · 쿨다운 · VIX 다시 받기 중(상태 응답 `vix_retry`)에는 버튼을 막는다.
  - 완료 처리:
    - 무효화 → 다시 읽기를 한 뒤, 다시 읽기 **전후의 자료별 기준일**을 비교해 '코스피 11/6 → 11/9 · 수급 11/5 그대로'처럼 적는다. 비교 대상은 시장 흐름 `status[].E` · 시장 판정 `kospi.as_of_date` · VIX.
    - `error_summary`가 있으면 '일부 실패: …'이고, failed면 '실패: …'다.
  - VIX 다시 받기 버튼 자체는 「요즘 잘 오르는 ETF」에만 둔다. `MarketDiscoveryView.tsx`는 871줄에서 약 720줄로 준다.

## 4. 질문 판정 결과(설계자 2026-11-09 · 판정서 §3)

| Q | 판정 | 이 PLAN 에 반영한 곳 |
|---|---|---|
| Q1 KOSPI 카드 나머지 지표 | (a) 수용 — [시장 근거와 다른 변화 보기] 안 | §2-4 |
| Q2 지금 할 일 · 업데이트 목록 | (a) 보완 수용 — 늦은 자료 · 바로 조치할 확인 실패는 상단 카드 · 버튼, 구성종목 · NAV · VIX 등은 「자료 확인」(기존 사유 · 이동). 「지금 할 일」에 있던 갱신 · 다시 읽기 경로에 계속 도달할 수 있어야 함 | §2-2 · §2-5 · 아래 '「지금 할 일」 경로 보존' |
| Q3 확인 창 판정 시점 | (a) 보완 수용 — 고르기 전 화면 · 캐시 · 성공 시각 반영 금지 · [취소] = 모두 보존 | 쟁점 4 |
| Q4 원/달러 기준일 | (a) 범위 한정 — '국내 T-1 대비' 기준과 실제 관측일을 나눠 표시 · 원인 추론 없음 | 쟁점 2 |
| Q5 보유 현재가 기준일 | (a) 보완 — 관측 시각(naver localTradedAt)인 행만 비교 · 나머지 '기준 확인 필요' | 쟁점 2 |
| Q6 PUSH 발송 | (a) 정정 — 당일 동기화 + 실행 행 발생일 오늘 · 접힌 줄 '발송 확인 불가' · 펼친 곳 실제 날짜 · 시각 | 쟁점 3 |
| Q7 시장 갱신 이어받기 | (a) 수용 | 쟁점 5 |
| Q8 읽은 시각 · 결과 | (a) 수용 — 실화면에서 [Q…] 표시 뺌 | §2-1 |
| Q9 차트 기간 | (a) 수용 — 최근 최대 120개 저장일 | §2 |
| Q10 단계 번호 | POC6-27 수용 | — |
| Q11 구현 묶음 | (a) 한 단계 · 결과 1회 검증 | §8 |

- **「지금 할 일」 경로 보존(Q2 보완)**: 지금 「지금 할 일」(`summaryLines.ts :: summaryTasks`)의 할 일은 네 종류다. 개편 뒤에는 같은 판정 함수를 그대로 써서 상단 「자료 최신화 필요」 안에 할 일로 넣고, 버튼만 이 화면의 동작으로 바꾼다.

  | 할 일(지금 판정 그대로) | 지금 버튼 | 개편 뒤 |
  |---|---|---|
  | `market_refresh` 시장 자료 갱신(VIX · KOSPI · 보유 비교 자료 · 수급 연결 `retry_helps`) | 「요즘 잘 오르는 ETF」로 이동 | 카드 안 [최신 시장 데이터 갱신](상단 버튼과 같은 작업) |
  | `holdings_price` 보유 현재가 다시 받기 | 정비 목록 [업데이트] 위치로 스크롤 | 카드 안 [보유 현재가 업데이트](상단 버튼과 같은 작업) |
  | `read_failed` 첫 조회 실패 · 응답 손상(상태 모름) | [요약 다시 읽기] | 카드 안 [요약 다시 읽기] · '기준 확인 필요'로 셈 |
  | `market_unknown` 시장 판정 · 목록 모름 | 없음(새로 고침 안내) | 그대로(문구만) |

  - 정비 항목 자체(구성종목 · NAV · VIX 등 기존 사유 · 이동 버튼)는 「자료 확인」 펼침 목록에 그대로 둔다.
  - 시험으로 네 할 일의 버튼 · 안내가 개편 뒤에도 나오는지 확인한다.

## 5. 하지 않는 것

PUSH 문안 · OCI 코드 · cron · Telegram, 수급 지연 원인 조사, 새 점수 · 등급, 자동 갱신 · 자동 원장 새로고침, 기존 응답 칸 · 문장 변경, 「ETF 비교하기」 · 「AI 투자 세션」 변경, 새 의존성.

## 6. 바뀔 파일(예상 · 줄 수는 11/9 실측 → 예상)

- **백엔드**
  - 새 `app/supply_fx_oil_fields.py`(~80)
  - 새 `app/market_freshness_rows.py`(~90)
  - `app/supply_fx_oil_context.py`(576 → ~590)
  - `app/oci_startup_status.py`(407 → ~420)
  - `app/api_oci_startup_status.py`(84 → ~100)
  - `app/ledger_copy/views.py`(307 → ~340)
  - `app/api_decision_ledger.py`(210 → ~235)
- **프론트**
  - `TodayInvestmentCheckView.tsx`(308)
  - `today/SummarySection.tsx`(131)
  - `today/summaryLines.ts`(483 · 시장 줄 분리로 감소)
  - `today/JudgmentQueueSection.tsx`(371 → 두 칸 분리)
  - `today/KospiHeadline.tsx`(296 → Q1에 따라 펼침 부품으로)
  - 새 `today/MarketFlowBlock.tsx`
  - 새 `today/FreshnessCard.tsx`
  - 새 `today/OciScheduleCard.tsx`
  - 새 `today/StaleConfirmDialog.tsx`
  - 새 `lib/todayFreshness.ts`
  - 새 `lib/todayMarketCopyText.ts`
  - 새 `lib/marketConditionStore.ts`
  - 새 `useMarketRefresh.ts`
  - `MarketDiscoveryView.tsx`(871 → ~720)
  - `lib/api/queryCache.ts`(214 → ~240)
  - `lib/api/marketFlow.ts` · `lib/api/oci*` · `lib/api/decisionLedger*`(타입) · `lib/api/dashboardKeys.ts`(무효화 앞부분 1줄)
- **시험**: 각 대상의 기존 시험 파일 옆에 새 시험 파일을 둔다(새 백엔드 시험은 tmp DB · 고정 fixture · 라이브 DB 열지 않음).
- **문서**: PROGRAM_TRUTH(오늘 화면 · 시장 흐름 응답 · OCI 응답 · 원장 읽기) · STATE_LATEST · 결과서.

## 7. 시험 · 완료 기준 확인

- **백엔드**
  - 새 칸 단위 시험: 11/5 · 11/6 사례 fixture에서 `obs.value` 5,059.69 ≠ `range.bound` 5,383.80(11/5) · 일평균 · 60거래일, 그리고 결측 · 자료 부족 시 null
  - 기존 문장 불변 시험
  - 최신성 표 시험(쟁점 2 사례 전부)
  - OCI · 원장 시험(쟁점 3)
  - black · flake8 · py_compile, 마지막에 전체 pytest 1회(백그라운드)
- **프론트(vitest)**
  - 배치 순서: 시장 흐름 안 '코스피 수치 → 차트 → 외국인 수급'
  - 자료 최신화 카드: 대상이 없으면 숨김, 있으면 자료별 줄
  - 확인 창: 최신이면 창 없음 · 늦으면 창 · 계속하면 반영과 표시 · 취소하면 이전 값 유지
  - AI 복사: 고정 프롬프트 글자 일치 · 빠진 값 '확인 불가' · 복사 실패 대체
  - 조건 공유: 메뉴 왕복 유지 · 새로 고침 초기화 · 낮은 순 표시
  - 갱신 진행: 다시 마운트 때 이어받기 · 중복 실행 막기 · 부분 실패 · 기준일 전후 표시
  - 옛 서버 응답(새 칸 없음)이면 '확인 불가'
  - **판정 §4 필수 시험**: 요약 [취소] 때 캐시 · 성공 시각 유지 / 당일 동기화와 과거 실행 구분 / 정확히 일치한 사건만 중복 제거(같은 날 다른 종류 보존 · 기준값 다르면 제외 안 함) / 두 카드 재진입 시 접힘 / 최근 최대 120개 차트가 코스피 수치와 외국인 수급 사이 / 조건 메뉴 왕복 유지 · 새로 고침 초기화 / WTI 날짜로 경고 · 확인 창이 생기지 않음 / 보유 갱신 전건 실패 · 일부 실패 구분
  - 새 `freshness` · 하위 칸이 **실제 GET 응답**(TestClient · 응답 모델 통과)에 실리는지 확인
  - tsc · eslint
- **실화면**: 형수님이 11/9 같은 자료로 위 순서 · 문장 · 버튼 동작을 확인한다(레이아웃은 자동 시험으로 잡히지 않음).
- **검증 대상**: 백엔드 응답 변경과 화면 동작(기준서 §0). 결과서 `docs/ai_result/POC6/POC6_27_TODAY_CHECK_REVISION_RESULT.md`.

## 8. 구현 환경(판정 §4 반영)

1. **격리 작업 사본**: 백엔드 개발 서버(`uvicorn --reload --reload-dir app --reload-dir scripts` · 저장소 폴더 기준 · 11/9 실측)와 프론트 dev 서버가 감시하지 않는 저장소 밖 폴더에 git 작업 트리를 만들어 구현 · 시험한다.
   - 경로 `/Users/hyungsookim/projects/krx_hyungsoo_wt_poc6_27` · 브랜치 `poc6-27-today-check`
   - 지금 운영 중인 두 서버 · OCI 기동 읽기 · 외부 시세 갱신은 개발 중 발생하지 않는다.
   - 기동 SSH · 외부 시세 · 원장 동기화는 시험에서 대체 응답으로 확인한다.
2. **제출 화면**: 저장 자료를 띄운 화면은 작업 사본에서 다른 포트로 띄운 백엔드 · 프론트로 만든다. 예: 백엔드 8001(`--reload` 없음 · OCI 기동 읽기 끔), 프론트 3001.
   - 실제 서버 재기동 · OCI 읽기가 필요한 범위(예약 칸을 실제 값으로 보기 등)는 형수님 실화면 확인 때 따로 맞춘다.
3. **프론트 검사**: tsc · eslint · vitest. 프로덕션 빌드는 하지 않는다.
4. **커밋 · push · 실사용 반영**: 결과 판정 뒤(판정 §5).

외부 API · 새 라이브러리 · 파일 삭제 · DB 표 변경은 없다.
