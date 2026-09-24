# POC4-01 종료 인계 — 불변 기준선 · KRX 과거 universe · 테스트 라이브 격리 · 성과지표

> **최종 인계 (2026-09-24 · 검증자 `VERIFIED` 뒤).** 같은 파일의 앞선 판(작업 1~5 중간 인계)과 commit `02a0f7c5` 는
> 사용자 직접 지시로 만들었다 — 설계자 3차 판정이 이 기록을 유지하고 별도 문제로 보지 않기로 했다. 정본 증거는
> 결과서 `docs/ai_result/POC4/POC4-01_DATA_BACKTEST_FOUNDATION_RESULT.md` 다. 이 문서는 이어받는 데 필요한 것만 추린다.
> 결과서·PLAN 머리의 STATUS 는 검증 전 문구(`READY_FOR_LIMITED_REVERIFICATION`) 그대로다 — 검증받은 문서를 고치지 않았다.
> 최종 판정은 이 문서와 `docs/STATE_LATEST.md` 에 적었다.

- **작성**: 개발자(VSCode Claude) · **독자**: 다음 챕터(POC4-02) 개발자
- **입력**: 설계자 POC4-01 판정 1차(2026-09-23) · 2차 · 3차 · 설계자 확인(2026-09-24) · 검증자 제한 재검증 `VERIFIED`

```text
POC4-01            CLOSED — 검증자 VERIFIED (2026-09-24 · 전체 회귀 2,013 passed · 라이브 5경로 전후 동일)
NEW_BASELINE       relative_upside_v1_snap_20260921 · REJECT (ceiling RESEARCH_ONLY) · 두 번 실행 canonical 동일
LEGACY_BASELINE    NON_REPRODUCIBLE 표시 · 원본 무변경
KRX_UNIVERSE       krx_etf_universe_v1 SEALED · 설계자 승인: POC4-02 연구 기준선 입력 (RESEARCH_ONLY)
UNBIASED_PERFORMANCE_CLAIM = NOT_YET (POC4-02 검증 전까지)
TEST_ISOLATION     라이브 쓰기 가드 + 읽기 전용 세션 사본(기존 테스트 229건 목록) — 저장소에서 전체 pytest 가능
OCI · PUSH         변경 0 (PC 연구 전용 — OCI 에 배포할 것 없음)
push               VERIFIED 뒤 사용자 승인으로 일괄 push — 된 여부는 `git log --oneline origin/main..HEAD` 가 비었는지로 확인
```

---

## 1. 이 챕터가 만든 것

### 코드 (줄 수는 2026-09-24 실측)

```text
417  app/ml_baseline_snapshot.py          스냅샷 생성·검증 · 작업 사본 세션 · sqlite 접속 허용 목록 · new_run_dir(새 폴더만)
277  app/ml_baseline_provenance.py        코드 게이트 · 모듈 raw/정규화 AST hash · 환경 · run_manifest(E2 핵심 hash 포함)
532  app/ml_research_krx_universe.py      KRX 연구 DB · downloader(checkpoint·재시도·backoff·429 즉시 중단) · version·봉인
257  app/ml_strategy_performance.py       비용 분해 · 절대·상대 성과지표 (결과의 strategy_performance 블록)
149  app/ml_research_split.py             모델·설정 선택용 purge·embargo 20거래일 분할 · 계약 검사 · 같은 분할 fingerprint
599  scripts/run_ml_score_validity_eval_v1.py   스냅샷 필수 러너 (--snapshot-manifest · --cutoff · --out-dir 새 폴더)
119  scripts/ml_baseline_tool.py         build / verify / compare
105  scripts/run_krx_universe_download.py     canary / full / resume / status / verify / seal
684  tests/_live_guard.py                 테스트 라이브 쓰기 가드 · 세션 사본 (§4)
```

`app/ml_relative_upside_model.py`(고정 모듈)는 docstring 만 정정했다 — raw sha256 `8cb88f9e…` → `b41b2a9a…`,
정규화 AST hash `1ba8f5cb…` 그대로. E2 평가 로직은 바꾸지 않았다.

### 테스트 (수집 수 실측)

```text
tests/test_ml_baseline_snapshot.py        24   검증 기준 1~4 · 대조군 · 실행 중 변경 · 코드 게이트 · 산출물 보호
tests/test_ml_research_krx_universe.py    13   가짜 fetcher 로 checkpoint·재시도·429·충돌·봉인
tests/test_ml_backtest_metrics.py          8   비용·성과지표 손계산 대조 · 산식 문구
tests/test_ml_backtest_embargo.py         11   purge·embargo 계약 · 한 줄 침범 실패
tests/test_live_state_guard.py            29   가드 역검증 (가드를 빼면 22건 실패)
tests/test_ml_score_validity_cli.py        7 · tests/test_ml_score_validity_contracts.py  40   스냅샷 실행 · 평가일 목록 계약
```

---

## 2. 새 기준선 — `relative_upside_v1_snap_20260921`

```text
위치      state/ml/baselines/relative_upside_v1_snap_20260921/
git       dataset_manifest.json · runs/run1 ~ run6/run_manifest.json
로컬 전용  dataset.sqlite(137,666,560 B · 0444) · e1_score_snapshot.json(0444) · 각 run 의 결과 JSON (gitignore · 맥북에만)
cutoff    2026-09-21 · dataset sha256 6fbde434af60e5e702904c36380b5ab7b906274d6697d2affdf6b1889f603781
평가일     E2 146개 (2014-06-30 ~ 2026-07-31)
판정      REJECT (ceiling RESEARCH_ONLY) · legacy 와 결론 같음

run       코드       canonical            E2 핵심 hash
run1·2    be579619   e1c02f66…            (기록 없음 — 성과 블록 전이라 canonical 자체가 E2 결과)
run3·4    71d50d15   2a6ca8c6…            e1c02f66…   ← strategy_performance 블록 추가
run5·6    2d6547b3   066ba09a…            e1c02f66…   ← active_return 산식 문구 정정만
```

성과(run5 · 146기간 · 기본 비용 편도 11.5bp): CAGR 2.97% · MDD −33.89% · Sharpe_0rf 0.253 · 상대 wealth 0.2746 ·
IR −0.631. 같은 기간 KODEX200 CAGR 14.50%. **생존편향이 남은 universe 기준이다** — 우월성 주장 금지.

명령 (저장소 루트):

```bash
# 봉인 확인
.venv/bin/python scripts/ml_baseline_tool.py verify \
  --manifest state/ml/baselines/relative_upside_v1_snap_20260921/dataset_manifest.json

# 다시 실행 (약 16분) — out-dir 는 없는 새 폴더(run7 …). app/·scripts/·requirements.txt 가 commit 과 다르면 거부
.venv/bin/python scripts/run_ml_score_validity_eval_v1.py \
  --snapshot-manifest state/ml/baselines/relative_upside_v1_snap_20260921/dataset_manifest.json \
  --cutoff 2026-09-21 --out-dir state/ml/baselines/relative_upside_v1_snap_20260921/runs/run7

# 두 실행 대조 — 다르면 종료코드 1 (compare 는 E2 핵심 hash 를 비교하지 않는다 — run_manifest 의
# result.e2_core_canonical_sha256 을 따로 본다)
.venv/bin/python scripts/ml_baseline_tool.py compare <run_manifest A> <run_manifest B>
```

---

## 3. KRX 과거 universe 연구 DB

```text
위치      state/ml/research/krx_etf_universe.sqlite (1,862,836,224 B · gitignore · 맥북 전용)
version   krx_etf_universe_v1  SEALED  content_sha256 c1a877762b9b1f296365801030641c86bc4508f4c2643f1a6793e39119f9bb4c
범위      2014-01-02 ~ 2026-09-21 평일 3,318개 → TRADED 3,122 · NON_TRADING 196 · 원응답 행 1,716,983
달력 교차  2014-04-09 이후 TRADED 3,055일 = 스냅샷 KODEX200 거래일 3,055일 (완전 일치)
생존편향   기간 중 KRX ETF 코드 1,419개 · 2026-09-21 에 상장 안 된 코드 248개 · 스냅샷에 없는 코드 236개
canary    version canary-20260923 (OPEN · 기준선에 쓰지 않음)
```

**설계자 승인 (3차 판정)** — `PURPOSE=RESEARCH_BASELINE` · `OPERATION_PROMOTION=NO` · `OCI_DEPLOY=0` · `PUSH_USE=0`.
**POC4-02 에서 반드시 지킬 규칙**:

- 각 날짜의 KRX universe 를 쓴다 · 현재 `etf_master` 로 다시 거르지 않는다
- 폐지 ETF 가격은 같은 KRX 봉인 version 에서, KODEX200(069500)도 같은 계열에서 가져온다
- 결측을 생존 DB(운영 `etf_daily_price`)로 채우지 않는다 — 가격 출처·기준이 다르다(설계자 결정 2 "가격 혼합 금지")
- 결측·0·휴장 응답은 사유와 함께 제외한다 · dataset version · payload hash · 날짜 범위를 고정한다
- `UNBIASED_PERFORMANCE_CLAIM=YES` 아님 — POC4-02 검증 전까지 결과는 `RESEARCH_ONLY`

**호출 한도** — 이용약관 인증키당 하루 10,000회(초과 시 HTTP 429). 코드가 한 KST 일 5,000회로 막는다.
**이용 조건** — 비상업 목적 · 원천 데이터 제3자 제공 금지 · 화면 표출 시 출처 표시(이용약관 · PLAN §2-3).

```bash
.venv/bin/python scripts/run_krx_universe_download.py status --batch-id FULL-20260923
.venv/bin/python scripts/run_krx_universe_download.py verify --batch-id FULL-20260923
# 기간을 늘리려면 새 batch + 새 version (봉인 version 에는 추가되지 않는다)
```

---

## 4. 테스트 라이브 격리 — 새 테스트를 쓸 때 반드시 알 것

이 챕터 전까지 **전체 pytest 가 맥북 라이브 경로 5곳에 썼다**(결과서 §4-8). 지금은 `tests/_live_guard.py` 가
막는다 — **저장소에서 전체 pytest 를 돌려도 된다**(2,013 passed · 라이브 5곳 sha256 전후 동일 · 3분대).

```bash
.venv/bin/python -m pytest tests -q -p no:cacheprovider      # 저장소 루트에서 (목록 id 가 루트 기준 nodeid)
# 예전에는 PUSH_AUTOSEND_* 4개를 명령줄에 붙여야 3건이 통과했다. 2026-09-24 사본 실측: 플래그 없이 2,013 passed(3분 06초)
# — 붙이지 않아도 된다. 붙이더라도 명령줄에만, .env 에는 절대 넣지 말 것(실제 발송 스위치).
```

- **라이브 state/·logs/ 파일 쓰기(open·os 연산)는 쓰는 순간 `LiveStateWriteError`**, SQL `ATTACH`·`VACUUM INTO` 로
  라이브 DB·사본을 붙이는 것은 SQLite 가 `not authorized` 로 거부한다 — 이 둘은 앱 코드가 `except Exception` 으로
  삼켜도 그 테스트가 실패한다(teardown ERROR). 목록 테스트의 sqlite 쓰기는 읽기 전용 사본에서 `attempt to write a
  readonly database` 로 실패한다(라이브 무변경 · 기록 대상이 아니라 앱이 삼키면 테스트는 통과할 수 있다).
- **새 테스트는 라이브 DB 를 열 수 없다** — 자체 tmp DB 나 고정 fixture 를 쓴다(설계자 규칙). 기존 테스트
  229건(`tests/_live_db_legacy_readers.txt`)만 라이브 DB 의 **읽기 전용 세션 사본**을 쓴다. 이 목록은 줄이기만 한다
  (상한 `LEGACY_READERS_CEILING = 229` · 정렬·중복 0 — 항목 바꿔치기는 테스트가 못 잡으니 diff 로 본다).
- **정확한 라이브 값을 단언하는 테스트는 세션 사본도 쓰지 않는다** — 고정 입력으로(예: intraday_config 4건은
  `selector.latest_closes` 를 고정 종가로 바꿨다).
- 목록을 다시 재야 하면 기록 모드: `KRX_LIVE_DB_READERS_RECORD=<파일>` 로 전체 회귀 → 사본을 연 테스트 id 가 모인다
  (연결마다 한 줄이라 중복 제거 후 센다 — 지금 기록하면 목록 229건과 정확히 같다).
- 세션 끝에 `[live-db-copy]` 줄(사본 hash·integrity·세션 끝 재확인)과, 라이브가 바뀌었으면 `[live-state]` 가 나온다.
- 감시 예외(설계자 승인 · 읽기 전용): 세션 전후 hash, 테스트별 benchmark 테이블 mode=ro 조회. conftest 의
  three_push 상태 파일 감시는 바뀌면 실패만 시킨다(되돌려 쓰지 않는다).

---

## 5. 남은 기술부채 · 열린 항목 (모두 비차단)

1. **기존 테스트 229건의 고정 fixture 전환** — 설계자가 정한 비차단 기술부채. 목록 파일이 대상 목록이다. 92건이
   intraday_config 테스트(integration 46 · contracts 46), 33건이 `test_intraday_alert_flow_through.py` 다. 전환할 때마다 목록에서 빼고 상한을 낮춘다.
2. **가드가 못 보는 통로**(저장소 사용처 0) — `io.FileIO(...)` · `sqlite3.Connection(...)` 직접 생성 · 파일 디스크립터
   연산(`os.fchmod` 등) · 세션 전부터 있던 하드링크. 권한·플래그만 바꾸는 것과 빈 폴더는 세션 전후 비교에도 안 잡힌다.
   `ATTACH ?`(매개변수) 는 막히지만 SQLite 가 파일을 한 번 연다(결과서 §5).
3. **`tests/_live_guard.py` 684줄** — 테스트 기준(1,500) 안이다(검증자 VERIFIED 판정 B-3 에서 문제 없음). 더 붙일 때는 분리를 먼저 본다.
4. **KS-10 근접** — `app/ml_score_validity_report.py` 626줄(근접) · `scripts/run_ml_score_validity_eval_v1.py` 599줄(근접 600 에 1줄 모자람).
   지표·판정을 더 붙이기 **전에** 분리한다(650 초과 금지).
5. **운영 코드 옛 주석 3곳이 NAV JSON 계약과 반대** — `app/market_refresh_service.py:8` "JSON artifact 생성하지 않는다" ·
   `app/api_market_topn.py:14` · `app/market_topn.py:4`. 운영 코드를 만지는 다음 Step 에서 고친다.
6. **NAV 요약 활성 경로가 비어 있다** — 테스트 값으로 덮인 `state/market/nav_discount_refresh_latest.json` 을
   `…json.quarantine-test-20260923T135028Z` 로 옮겨 보존했다(gitignore). 다음 정상 NAV 갱신이 새로 만든다. 그때까지 수동
   진단 스크립트만 "없음" 으로 본다(화면·API·발송 무관).
7. **맥북 라이브 시장 DB 의 `market_refresh_state` 행** — 사고 때 지워졌고 복원하지 않았다(설계자 (a)). 다음 정상 시장
   데이터 갱신이 다시 쓴다. 과거 실행 기록 156개 · 공유 로그 2개도 그대로 뒀다.
8. **관찰(확인 안 함)** — 일부 기존 갱신 테스트가 Naver `fetch_universe_snapshot` 을 대체하지 않아 실제 조회 경로를
   탈 수 있다(`test_market_topn_api.py::test_post_refresh_accepted_and_runs_inline_for_test` ·
   `test_market_refresh_state_persistence.py`). 테스트 외부 호출 정리 때 본다.
9. E1 은 `E1_UNAVAILABLE` 그대로 · `market_refresh_log` 는 cutoff 로 자르지 않았다(메타데이터 전용) · 운영
   `etf_daily_price` 에 개별 주식 3종목(000660 · 005930 · 006400)이 있다(평가 대상 아님) · 주말에도 KRX 는 가격 빈 행을
   준다(2026-09-19 토요일 1,171행 — `krx_sync.has_traded_prices` docstring 의 "주말은 행 자체가 없다" 와 다름).

---

## 6. 이 챕터에서 배운 것 (반복하지 말 것)

1. **라이브 DB 를 읽는 백테스트는 재현되지 않는다** — 일일 배치가 최근 과거 가격을 다시 덮어쓴다. 비교는 스냅샷으로.
2. **"운영 변경 0" 은 전체 pytest 이후까지 재야 말할 수 있다** — 자체 검수 pytest 가 라이브에 썼다(§4 가드의 이유).
3. **센 수는 측정 방법이 정한다** — "라이브 DB 를 읽는 테스트 93건" 은 rw 실패만 센 과소 집계였고, 기록 모드 전수
   측정은 233건이었다. 설계자 조건이 그 수치를 받아 적었다가 정정해야 했다.
4. **가드는 통로를 전부 열거한 뒤 역검증한다** — 첫 가드는 SQL 쪽을 `sqlite3.connect` 만 봐서 ATTACH·사본 직접 쓰기·경로 별칭·
   삼킨 오류가 뚫려 있었다. 검증자에게 넘기기 **전에** 검증 항목을 직접 돌린 사전 점검이 이것을 잡았다.
5. **전달문 안의 commit 번호도 stale 이 된다** — 설계자 전달문을 받은 뒤 amend 하면 그 번호가 브랜치에서 사라진다.
   넘길 때 `git log --oneline origin/main..HEAD` 로 다시 잰다.
6. **결과서는 커밋 전에 구역별로 실측 대조한다** — 매 라운드 숫자·범위·시점 오류가 나왔다.

---

## 7. 다음 사람이 바로 할 일

1. push 여부 확인 — `git fetch && git log --oneline origin/main..HEAD` 가 비어 있지 않으면 사용자 승인으로 `git push origin main`.
2. 설계자에게 POC4-01 종료 보고(사용자 경유) → POC4-02 설계서 수신.
3. POC4-02 는 **설계서 → 개발 PLAN(모호점 질문) → 설계자 확정 → 구현** 순서. 착수 전 §3 규칙과 §5-4 분리를 PLAN 에 넣는다.

---

## 8. 문서

```text
설계자 판정·계획   docs/ai_plan/POC4/POC4-01_DATA_BACKTEST_FOUNDATION_PLAN_V1.md (판정 1~3차 · 설계자 확인)
결과서            docs/ai_result/POC4/POC4-01_DATA_BACKTEST_FOUNDATION_RESULT.md (§4-13 사전 점검 · §5 한계)
Master Plan      docs/ai_plan/POC4/POC4-00_ML_QUANT_ADVANCEMENT_MASTER_PLAN_V1.md
legacy 표시       state/ml/validity/LEGACY_BASELINE_NON_REPRODUCIBLE.json
현행 동작         docs/PROGRAM_TRUTH.md §7.1 (연구 저장소 2종 · 스냅샷 러너) · §8 (KRX Open API)
현재 상태         docs/STATE_LATEST.md
```

## 9. 사용자 확인

- 화면 확인 없음 · OCI 적용 없음(PC 연구 전용).
