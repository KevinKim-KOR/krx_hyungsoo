# POC5-11 개발 PLAN V1 — PC 시장 자료 갱신 연결 · 기준일 정정

작성 2026-10-14 · 작성자: 개발자(VSCode Claude) · 수신: 설계자
근거: 설계자 판정 `POC5-UI-03_PLAN_DECISION_AND_PC_MARKET_REFERENCE_FOLLOWUP_2026-10-14.md` §4(원문 = `docs/ai_design/POC5/POC5-UI-03_TODAY_SCREEN_INFORMATION_HIERARCHY_DESIGN_V1.md` §9 · 별도 설계서 없음)

```text
STATUS   = PLAN 제출 — 설계자 판정 대기(구현 미승인 · UI-03 커밋 뒤 착수)
SCOPE    = PC 갱신 서비스에 기존 refresh_vix 연결 · PC 화면 API 의 시장 판정 날짜를 실제 쓴 KODEX200 자료에서 · 같은 단계에서 오늘 화면 판정 줄 이름 정정
           공유 수집 함수 · OCI 배치 · PUSH · DB 스키마 · 의존성 변경 0
QUESTION = 4건(§4)
조사     = 읽기 전용 2갈래(함수 연결 위치 · PC DB 경로 · 기록 부수 효과 · 시장 날짜 호출자 · 격리 시험)
```

## 1. VIX — PC 갱신에 기존 경로 연결

**지금**: PC 갱신(`app/market_refresh_service.py :: _execute_refresh_job`)은 아래 순서로 돈다. VIX 단계는 없다(`grep -i vix` 0건).

1. ETF 목록 · 가격
2. 보유 개별주(POC5-10)
3. KOSPI
4. NAV

그래서 PC VIX 기준일이 2026-09-11 에 멈춰 있고, 「자료 최신화 필요」의 [시장 자료 업데이트로]를 눌러도 풀리지 않는다. `refresh_vix` 를 부르는 곳은 OCI 08:10 배치(`scripts/run_oci_market_data_batch.py:283` `refresh_benchmarks`)와 수동 명령(`scripts/refresh_market_timeseries.py vix`)뿐이다.

**연결**(고칠 파일 = 서비스 하나 · 공유 함수 본문 변경 0)

- **위치**: KOSPI 단계 뒤 · NAV 단계 앞이다. VIX 가 늦거나 실패해도 ETF · 개별주 · KOSPI 결과 기록이 먼저 끝난다.
- **호출**: `refresh_vix(db_path=db_path)` 를 부른다(`app/market_benchmark_batch.py:118`).
  - `db_path` 는 반드시 넘긴다. 넘기지 않으면 import 시점의 라이브 경로로 떨어져 시험 격리가 깨진다.
  - 서비스 모듈 속성으로 import 해 시험에서 바꿔 끼울 수 있게 한다(기존 `refresh_kospi_benchmark` 와 같은 방식).
- **실패 처리**(POC5-10 방식 재사용)
  - `try/except` 로 감싼다. 반환 `status != "ok"` 이거나 예외면 고정 한국어 문구를 쓴다.
  - 최종 `error_summary` 는 `" · ".join(ETF·KOSPI 요약, 보유 개별주 문구, VIX 문구)` 이다.
  - completed / failed 판정 · `last_success_*` · 장중 설정 재산출은 그대로라서, VIX 실패가 다른 단계 성공을 지우지 않는다(판정 §4-2).
  - 기술 사유(status · exit_code · error · as_of_date)는 서버 로그에 남긴다.
- **문구**(안): `시장 불안 지표(VIX)를 갱신하지 못했습니다`
  - 정비 큐의 '시장 불안 지표' 용어와 POC5-10 의 '…을 갱신하지 못했습니다' 꼴에 맞췄다.
  - 「요즘 잘 오르는 ETF」 완료 줄에 `갱신 완료. 확인 필요: …` 로 보인다(POC5-10 화면 그대로 · 프론트 변경 0).
- **기록 부수 효과**
  - `refresh_vix` · `run_vix_ingest` 는 `market_refresh_log` · 상태 파일에 쓰지 않는다.
  - 쓰는 곳은 `market_benchmark_daily_price` 의 VIX 행(`source = FDR_VIX` · 기존 날짜 덮어쓰기 없음 · 추가만)뿐이다.
  - 그래서 '마지막 전체 갱신'(`_latest_refresh_payload`) · KOSPI 상태(출처 지정 조회)는 바뀌지 않는다. 새 기록 행도 만들지 않는다(§4 Q3).
- **자료 날짜**
  - 성공하면 화면의 VIX 기준일(`market_risk_reference.vix.as_of_date` = VIX 저장 최신 행)이 바뀐다.
  - 정비 큐 VIX 지연 판정(`vix.as_of_date < kodex.as_of_date`)은 그대로 쓴다(판정 §4-5 '새 조건 금지').
- **OCI 무변경**: `app/market_benchmark_batch.py` · `scripts/_market_refresh/vix_ingest.py` · `scripts/run_oci_market_data_batch.py` · `app/market_benchmark_store.py` 변경 0. OCI 배치는 `market_refresh_service` 를 import 하지 않는다.

## 2. 시장 판정 날짜 — 실제 쓴 KODEX200 자료에서

**조사 결과**

| 값 | 실제 계산 | 쓰임 |
|---|---|---|
| `compute_topn` 의 `asof_iso` | `etf_daily_price` 전체 `MAX(date)`(`market_topn_helpers._latest_date_in_db` · 종목 · 종가 조건 없음) | **계산 입력**: 후보 기간 수익률의 비교 시작 목표일 · 응답 최상위 `asof` · OCI 근거 문장 날짜 |
| `market_context.asof` | 위 `asof_iso` 를 그대로 넘김(`market_topn.py:313`) | **표시 메타뿐**: `compute_market_context` 안에서 계산에 쓰이지 않는다(`market_regime.py` 반환에만). 국면 · 지속일 · 기준선은 `kodex200_history`(069500 · close > 0) 마지막 행으로 계산된다. |

- 코드 주석 계약 ⑤(`market_regime.py:449`)는 `market_context.asof` 를 'KODEX200 기준일'로 정했다(`asof_source = "KODEX200"`). 실제 값은 전체 최신일이라 둘이 어긋난다 — 이것이 결함이다.

**정정**(가장 좁은 위치 · 공용 함수 뜻 무변경)

- `compute_topn` 에 기본값 False 인 키워드 인자 하나(이름 예: `market_asof_from_kodex200`)를 둔다. `kospi_today_kst` 와 같은 '화면 API 만 넘기는' 선례다.
  - True 면 이미 읽은 `kodex200_history` 의 마지막 행 날짜를 `compute_market_context(asof=…)` 에 넘긴다. 판정 · 지속일 · 기준선과 같은 읽기라 새로 읽지 않는다(POC5-09 '같은 읽기').
  - 069500 행이 없으면 None 이다.
- `GET /market/topn/latest`(`app/api_market_topn.py`)만 True 로 넘긴다.
- 그대로 두는 것
  - 최상위 `asof` · 후보 수익률 · `_latest_date_in_db`
  - 다른 `compute_topn` 호출자: OCI 근거(`runtime_evidence`) · 초안(`draft.py` · `draft_three_push.py`) · 「확인 근거」 API · 결정 초안 미리보기 · universe 제안 · ML 과거 재현
  - 그래서 OCI 근거 문장 · 브리핑 · 초안 저장값(`judgment_summary.market_asof` · 스냅샷의 `market_context.asof`)이 바뀌지 않는다.
- **화면 이름 정정(같은 단계)**: 값이 KODEX200 판정 날짜가 되면 UI-03 의 '저장 가격 최신일(저장된 전체 종목 기준)'이 틀린 설명이 된다. 그래서 이 단계에서 오늘 화면 판정 줄 이름을 함께 바꾼다(§4 Q1).
  - 「개발·실험용」 `DashboardView` 의 '(기준일 …)'는 문구 그대로이고 값만 정정된다.
  - 「요즘 잘 오르는 ETF」 '시장 데이터 기준일'(최상위 `asof` = 전체 최신일)은 그대로다.

## 3. 격리 시험 (가짜 수집기 · tmp DB · 외부 호출 0 · 라이브 DB 0 · `tests/_live_guard.py`)

- **기존 서비스 시험 보호**
  - VIX 단계를 연결하면, stub 이 없는 기존 시험(`test_holdings_equity_refresh` · `test_market_refresh_state_persistence` · `test_market_topn_api` 의 갱신 작업)이 실제 Yahoo 에 나가거나 `error_summary` 정확 비교가 깨진다.
  - 그래서 conftest autouse 로 `market_refresh_service.refresh_vix` 를 중립 stub 으로 바꿔 끼운다.
- **VIX 새 시험**: 실제 `refresh_vix` 에 가짜 `FinanceDataReader.DataReader`(`sys.modules` 교체 · 기존 `test_market_benchmark_freshness` 방식)를 쓴다.
  - ① 성공: VIX 행 추가 · 문구 없음 · `market_refresh_log` 행 수 · 출처 · '마지막 전체 갱신' 불변
  - ② 조회 예외: completed 유지 · VIX 문구 · 다른 단계 저장 유지
  - ③ 기존 날짜 다른 값(rc 2): 덮어쓰기 0 · 문구
  - ④ stub 예외: 문구 · running 에 머물지 않음
  - ⑤ 이미 최신: 문구 없음
  - ⑥ ETF · 개별주 · KOSPI · VIX 실패 조합의 문구 순서(parametrize · 순서 뒤집기 변이)
  - ⑦ `db_path` 전달(spy)
- **날짜 새 시험**: tmp DB 에 069500 유효 행 끝 = D1, 다른 ETF 끝 = D2(> D1)를 넣는다. 069500 의 D2 행은 close NULL 로 둔다.
  - 인자 True: `market_context.asof == D1` · 최상위 `asof == D2` · 후보 `basis_end_date == D2` · 국면 값은 기본 호출과 같다.
  - 인자 기본: `market_context.asof == D2`(OCI · 초안 경로 잠금).
  - API: `market_context.asof == market_risk_reference.kodex200.as_of_date == kodex200_stored_volume.asof_date == D1` · `payload.asof == D2`
  - OCI 근거 문장(`compose_market_discovery`)은 '(D2 기준)' 그대로다.
  - 변이: 분기를 `asof_iso` 로 되돌림 · 인자를 늘 True 로 둠.
- **화면**: 판정 줄 새 이름 · KospiStatusSurfaces STEP 4-3 · TodayFolds 날짜 시험을 고친다.
- **필수**: black · flake8 · py_compile · pytest 관련 + 전체 1회 · tsc · eslint · vitest. 실제 수집은 사용자 기존 [최신 시장 데이터 갱신] 1회로 확인한다(VIX 기준일 · 화면 · 갱신 완료 줄).

## 4. 판정 요청

**Q1. 오늘 화면 판정 줄의 새 이름**(실제 충돌 · UI-03 문구)
- 정정 뒤 `market_context.asof` = 판정에 실제 쓴 KODEX200 마지막 유효 행 날짜다. 계약 ⑤와 맞는다.
- UI-03 의 '저장 가격 최신일(저장된 전체 종목 기준)'은 틀린 설명이 되므로 바꿔야 한다.
- 선택지
  - (a) `· KODEX200 기준일 D` 로 바꾼다. 기본 화면 기준선 옆 `기준일 D`(UI-03 Q1 · 같은 행 조건)와 평소 같은 날짜다.
  - (b) 설계자 확정 문구로 바꾼다.
- 개발자 권장 = (a).

**Q2. VIX 조회 시간 상한**
- PC 갱신 경로에는 FDR 요청 시간 상한이 없다(`DEF-FDR-TIMEOUT` PC 잔여 · 조건부).
- 새 VIX 조회(Yahoo · `requests` timeout 없음)가 멈추면 작업이 running 에 머문다. 한 번에 하나만 도는 구조라 서버를 다시 켤 때까지 다음 갱신이 막힌다.
- 선택지
  - (a) 시간 상한을 넣지 않는다(지금 PC 경로처럼).
  - (b) VIX 호출만 기존 `fdr_request_timeout()` 으로 감싼다(`app/three_push_runtime/market_data_batch.py:176` · OCI 와 같은 20초 · 새 함수 없음).
- 개발자 권장 = (b).

**Q3. VIX 실패 기록**
- 선택지
  - (a) 서버 로그에만 남기고 `market_refresh_log` 행은 만들지 않는다(공유 조회 함수 · '마지막 전체 갱신' 변경 0).
  - (b) POC5-10 처럼 요약 행을 두고 '마지막 전체 갱신' 제외를 두 출처로 넓힌다.
- 개발자 권장 = (a). `refresh_vix` 실패 반환에는 기술 사유가 거의 없다(rc 2 · `error = None`).

**Q4. 받은 뒤에도 '오래됨'이 남을 수 있음**(기존 판정 재사용의 실제 효과)
- 정비 큐는 `vix.as_of_date < kodex.as_of_date` 면 '시장 불안 지표가 오래되었습니다'를 띄운다.
- 한국 날짜 D 에 갱신하면 VIX 는 최대 미국 D-1 이다. PC KODEX200 은 당일 행을 거르지 않아 장중 · 장 뒤 갱신이면 D 가 될 수 있다(추정).
- 그러면 VIX 를 정상으로 받아도 항목이 남을 수 있다.
- 선택지
  - (a) 기존 규칙 그대로 두고, 실제 수집 뒤 날짜를 실측해 결과서에 한계로 기록한다(판정 §4-5).
  - (b) 규칙을 조정한다(이번 범위 밖 · 별도 판단).
- 개발자 권장 = (a).

## 5. 결함 기록 · 한계

- **BACKLOG 에 결함 2건을 등재한다**(실제 확인 뒤 닫음 · 판정 §4).
  - `DEF-PC-VIX-REFRESH-MISSING`: PC 갱신에 VIX 단계 없음.
  - `DEF-MARKET-CONTEXT-ASOF-MEANING`: `market_context.asof` 의 이름(KODEX200 기준일)과 값(전체 최신일)이 다름.
- **범위 밖 · 기록만**
  - OCI 근거 문장 'KODEX200 최근 수익률 ({asof} 기준)'은 최상위 `asof`(전체 최신일)를 KODEX200 날짜처럼 쓴다(`app/runtime_evidence/market_discovery.py:61`). 판정상 OCI · PUSH 불변이라 바꾸지 않는다.
  - 후보 수익률 `basis_end_date` 는 `asof_iso` 이지만, 끝값은 종목마다 자기 마지막 행이다(추정 · 라벨 차이).
  - 한국 시각 00:00~05:00(겨울 06:00)에 갱신하면 진행 중인 미국 세션 VIX 값이 저장될 수 있다(추정 · Yahoo 조회 끝이 로컬 자정). 다음 실행은 저장 최신일 다음 날부터라 다시 고쳐지지 않는다.
- 첫 실행은 2026-09-12 이후 약 한 달 치 VIX 를 한 번에 받는다(추정 · 라이브 DB 미조회).
