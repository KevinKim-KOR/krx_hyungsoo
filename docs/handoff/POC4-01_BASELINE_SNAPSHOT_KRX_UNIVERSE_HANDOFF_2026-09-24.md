# POC4-01 작업 1~5 인계 — 불변 기준선 스냅샷 · KRX 과거 universe

- **작성**: 개발자(VSCode Claude) · **독자**: 다음 세션 개발자
- **작성일**: 2026-09-24 · 입력: 설계자 POC4-01 판정(2026-09-23)
- 정본 증거는 결과서 `docs/ai_result/POC4/POC4-01_DATA_BACKTEST_FOUNDATION_RESULT.md` 다. 이 문서는 이어받는 데
  필요한 것만 추린다.

```text
POC4-01 작업 1~5   IMPLEMENTED · 검증자 판정 대기
POC4-01 작업 6     미착수 — 설계자 답 대기 (PLAN §5)
NEW_BASELINE       relative_upside_v1_snap_20260921 · REJECT · 두 번 실행 canonical 동일
LEGACY_BASELINE    NON_REPRODUCIBLE 표시 · 원본 무변경
KRX_UNIVERSE       krx_etf_universe_v1 SEALED · 3,318개 기준일 · 기준선 사용은 설계자 승인 사항
UNBIASED_PERFORMANCE_CLAIM = NOT_YET
OCI · PUSH         변경 0 (이번 챕터는 PC 연구 전용 — OCI 에 배포할 것 없음)
```

---

## 1. 이 단계가 만든 것

### 코드 (기준선 commit `be579619`)

```text
391  app/ml_baseline_snapshot.py        스냅샷 생성 · 검증 · 작업 사본 세션 · sqlite 접속 허용 목록
274  app/ml_baseline_provenance.py      코드 게이트 · 모듈 raw/정규화 AST hash · 환경 · run_manifest
532  app/ml_research_krx_universe.py    KRX 연구 DB · downloader(checkpoint·재시도·backoff) · version
119  scripts/ml_baseline_tool.py        build / verify / compare
105  scripts/run_krx_universe_download.py  canary / full / resume / status / verify / seal
588  scripts/run_ml_score_validity_eval_v1.py  스냅샷 필수 러너 (--snapshot-manifest · --cutoff · --out-dir)
589  app/ml_score_validity_eval.py      run_e1_gate(snapshot_path=) · assert_evaluation_window(dates, expected_dates)
```

`app/ml_relative_upside_model.py` 는 docstring 만 설계자 문구로 정정했다(결정 3). raw sha256
`8cb88f9e…` → `b41b2a9a…`, 정규화 AST hash `1ba8f5cb…` 동일.

### 테스트

```text
tests/test_ml_baseline_snapshot.py        20건 — 검증 기준 1~4 · 대조군 · 실행 중 변경 · 코드 게이트
tests/test_ml_research_krx_universe.py    13건 — 가짜 fetcher(10건)로 checkpoint·재시도·429·충돌·봉인
tests/test_ml_score_validity_cli.py       스냅샷으로 실행하도록 수정
tests/test_ml_score_validity_contracts.py 평가일 "목록" 계약으로 수정
```

---

## 2. 새 기준선 — `relative_upside_v1_snap_20260921`

```text
위치      state/ml/baselines/relative_upside_v1_snap_20260921/
git       dataset_manifest.json · runs/run1|run2/run_manifest.json 만 추적
로컬 전용  dataset.sqlite(137,666,560 B · 0444) · e1_score_snapshot.json(0444) · 결과 JSON (gitignore)
cutoff    2026-09-21
dataset   sha256 6fbde434af60e5e702904c36380b5ab7b906274d6697d2affdf6b1889f603781
평가일     E2 146개 (2014-06-30 ~ 2026-07-31) · warmup 2014-04-30 · 2014-05-30
결과      REJECT · canonical e1c02f6657d2d88836dbf254f2beaf2f89aa42f405b077d2e599791f97454000 (run1 = run2)
legacy 대비  결론 같음 · 1M IC 142/145 일치 · 새 평가일 2026-07-31 하나
```

명령 (저장소 루트, `.venv/bin/python`):

```bash
# 봉인 확인 — 누락·hash 불일치면 종료코드 2
.venv/bin/python scripts/ml_baseline_tool.py verify \
  --manifest state/ml/baselines/relative_upside_v1_snap_20260921/dataset_manifest.json

# 다시 실행 (약 13분) — out-dir 는 새 폴더로. 코드가 commit 과 다르면 거부된다
.venv/bin/python scripts/run_ml_score_validity_eval_v1.py \
  --snapshot-manifest state/ml/baselines/relative_upside_v1_snap_20260921/dataset_manifest.json \
  --cutoff 2026-09-21 --out-dir state/ml/baselines/relative_upside_v1_snap_20260921/runs/run3

# 두 실행 대조 — 다르면 종료코드 1
.venv/bin/python scripts/ml_baseline_tool.py compare <run_manifest A> <run_manifest B>
```

스냅샷·결과 파일은 이 맥북에만 있다. 다른 기계에서는 manifest 만 보인다.

---

## 3. KRX 과거 universe 연구 DB

```text
위치      state/ml/research/krx_etf_universe.sqlite (1,862,836,224 B · gitignore · 맥북 전용)
version   krx_etf_universe_v1  SEALED  content_sha256 c1a877762b9b1f296365801030641c86bc4508f4c2643f1a6793e39119f9bb4c
범위      2014-01-02 ~ 2026-09-21 평일 3,318개 → TRADED 3,122 · NON_TRADING 196
원응답 행  1,716,983 (FULL batch)
달력 교차  2014-04-09 이후 TRADED 3,055일 = 스냅샷 KODEX200 거래일 3,055일 (완전 일치)
생존편향   기간 중 KRX ETF 코드 1,419개 · 2026-09-21 에 상장 안 된 코드 248개 · 스냅샷에 없는 코드 236개
          연도말 누락 비율 2014 31.4% → 2019 22.0% → 2023 12.1% → 2025 1.0%
canary    version canary-20260923 (OPEN · 기준선에 쓰지 않음)
```

```bash
.venv/bin/python scripts/run_krx_universe_download.py status --batch-id FULL-20260923
.venv/bin/python scripts/run_krx_universe_download.py verify --batch-id FULL-20260923
# 기간을 늘리려면 새 batch + 새 version (봉인 version 에는 추가되지 않는다)
```

**호출 한도** — 이용약관 제8조④ 인증키당 하루 10,000회(초과 시 HTTP 429). 코드가 한 KST 일 5,000회로
스스로 막는다(운영 07:20 수집과 같은 키일 수 있음 — 확인 안 함). 2026-09-23 에 3,339회 썼다.
**이용 조건** — 비상업 목적 · 받은 원천 데이터 제3자 제공 금지 · 화면 표출 시 "한국거래소 통계정보" 출처 표시.

---

## 4. 반드시 알아야 할 계약

### 4-1. 기준선은 스냅샷으로만 평가한다

라이브 DB 를 직접 읽는 평가 경로는 없다. 러너는 manifest·파일 누락, sha256 불일치, cutoff 불일치,
실행 중 원본 변경, 평가일 목록 불일치, 코드가 commit 과 다름 중 하나라도 있으면 **아무것도 쓰지 않고**
실패한다(예외: 개발용 `--allow-dirty-code` 는 실행하고 `official=false` 로 기록).

평가 중 sqlite 접속은 hash 를 확인한 **작업 사본**과 U2 임시 DB 로만 허용된다(`sqlite3.connect` 를 프로세스
안에서 제한). 봉인 원본을 직접 열지 않는 이유 — 운영 조회 함수 `market_data_store._connection` 이 처음 여는
DB 에 `CREATE TABLE IF NOT EXISTS` 를 쓴다.

### 4-2. 평가일 수는 상수가 아니다

`E2_EXPECTED_POINT_COUNT = 145` 는 없앴다. 전체 실행은 2014-06-30 시작 + manifest 평가일 목록과 **완전
일치**해야 한다. 145 는 `state/ml/validity/LEGACY_BASELINE_NON_REPRODUCIBLE.json` 에만 남아 있다.

### 4-3. 코드 게이트는 폴더 단위다

`app/` · `scripts/` · `requirements.txt` 에 미커밋 변경이 있으면 공식 실행이 거부된다. 목록을 손으로
고르면 결과를 바꾸는 모듈(예: regime 판정 `app/market_regime.py`)을 빠뜨린다 — 자체 리뷰에서 실제로 놓쳤다.

### 4-4. KRX 원응답은 덮어쓰지 않는다

원응답은 append-only 다. 같은 날짜를 다시 받아 TRADED 로 왔는데 내용이 다르면 기존 version 은 그대로 두고
`krx_refetch_conflict` 에 남긴다. 새 내용은 `derive_version` 으로 **별도 version** 을 만들어야 쓴다.
연구 DB 는 운영 DB 경로로 열면 거부되고, 운영 `etf_daily_price`(조정 계열)와 섞지 않는다(KRX 는 무조정).

---

## 5. 열린 항목

### 5-1. 검증자 판정 (차단)

결과서를 검증자에게 넘긴 상태다. 검증자가 코드 수정을 요구하면 수정 → 새 commit → **기준선 두 번 실행을 다시**
해야 run_manifest 의 코드 commit 이 맞는다(스냅샷은 그대로 재사용).

### 5-2. 작업 6 — 설계자 질문 3개 (차단)

PLAN `docs/ai_plan/POC4/POC4-01_DATA_BACKTEST_FOUNDATION_PLAN_V1.md` §5.

- **embargo 위치** — E2 평가 label 에는 누수가 없다(학습 행 label 종료일 ≤ t · 진입 t+1 · 스냅샷으로 독립
  재계산). embargo 가 필요한 곳은 train/validation 으로 설정을 고르는 경로다. 개발자 제안 (a): 평가기 쪽 분할
  함수에 넣고 고정 모듈은 그대로.
- **비용 분해 수치** — 수수료 · 슬리피지 · ETF 증권거래세 적용 여부.
- **성과지표 기준** — 초과수익(정보비율·추적오차) / 절대수익(Sharpe) / 둘 다.

`app/ml_score_validity_report.py` 가 626줄이다. 지표를 붙이기 **전에** 판정 부분을 분리한다(650 초과 금지).

### 5-3. 전체 pytest 가 맥북 라이브 경로 5곳에 쓴다 (미처리 · 사용자 결정 대기)

결과서 §4-8. 기존 테스트 격리 결함이고, 2026-09-23 22:49 자체 검수 때 드러났다.

```text
state/market/market_data.sqlite          market_refresh_state 행 삭제   ← test_api_holdings_market_evidence.py:40
state/market/nav_discount_refresh_latest.json  테스트 값으로 덮어씀   ← test_market_refresh_state_persistence.py · test_market_topn_api.py
state/runs/run_*.json                    새 파일                        ← test_poc1_loop.py
logs/oci_market_data_batch.log · logs/three_push_runtime_cron.log  줄 추가  ← 러너·배치 테스트 8개
```

기준선 입력에는 영향이 없다(pytest 전후 기준일 148개 값 동일). 선택지: (a) 그대로 — 다음 시장 데이터 갱신 때
행이 다시 써진다 · (b) 흔적 파일 정리(삭제 승인) · (c) 격리 수정(별도 작업).

**그때까지 저장소 안에서 전체 pytest 를 돌리면 또 쓴다.** 라이브를 건드리면 안 되는 작업이면 사본에서 돌린다:

```bash
SB=/private/tmp/claude-501/pytest_sandbox; rm -rf "$SB"; mkdir -p "$SB"
git archive HEAD | tar -x -C "$SB"
rsync -a --exclude 'ml/research/' --exclude 'ml/baselines/' state/ "$SB/state/"
cp .env "$SB/.env"; ln -s "$PWD/.venv" "$SB/.venv"
cd "$SB" && PUSH_AUTOSEND_ENABLED=true PUSH_AUTOSEND_MARKET_BRIEFING_ENABLED=true \
  PUSH_AUTOSEND_SPIKE_OR_FALLING_ALERT_ENABLED=true PUSH_AUTOSEND_HOLDINGS_BRIEFING_ENABLED=true \
  ./.venv/bin/python -m pytest tests -q -p no:cacheprovider
```

(autosend 플래그 4개는 테스트 3건 통과용이다. `.env` 에 넣지 말 것 — 실제 발송 스위치다.)

### 5-4. 비차단

- 러너의 legacy 폴더 거부는 `state/ml/validity` 와 **정확히 같은 경로**만 막는다. 하위 폴더(보존 사본
  `poc4_01_frozen_original/`)를 `--out-dir` 로 주면 덮어쓴다 — 주지 말 것.
- KRX 재수집 충돌 기록은 재수집 응답이 TRADED 일 때만 한다.
- E1 은 `E1_UNAVAILABLE` 그대로다(운영 점수 JSON 이 asof 2026-08-27 로 바뀌었고 E1 기준일 상수는 2026-08-20).
- `market_refresh_log` 는 cutoff 로 자르지 않았다(메타데이터 전용 · 슬레이트 선택 무관).
- 운영 `etf_daily_price` 에 개별 주식 3종목(000660 · 005930 · 006400)이 93행씩 있다. `etf_master` 에 없어
  평가 대상이 아니다. 운영 DB 는 건드리지 않았다.
- 휴장 평일·토요일에도 KRX 는 행을 준다(가격 빈 문자열). `krx_sync.has_traded_prices` docstring 의
  "주말은 행 자체가 없다" 와 다르다 — 운영 코드는 그대로 뒀다.

---

## 6. 이 단계에서 배운 것 (반복하지 말 것)

1. **라이브 DB 를 읽는 백테스트는 재현되지 않는다.** 일일 배치가 최근 몇 달 가격을 다시 받아 덮어쓴다.
   비교 실험은 반드시 스냅샷으로.
2. **"운영 DB 변경 0" 은 전체 pytest 이후 시각까지 재야 말할 수 있다.** 스냅샷 직전부터만 hash 를 재서 결과서에
   "작업 전후 동일" 이라고 썼다가, 커밋 전 대조에서 틀린 것이 드러났다.
3. **고정 모듈은 주석도 hash 를 바꾼다.** 정정은 새 기준선 commit 에서 하고, 정규화 AST hash 가 같다는 것으로
   로직 무변경을 보인다.
4. **결과서는 커밋 전에 구역별로 실측 대조한다.** 1차 19건 · 2차 4건의 오류를 잡았다(숫자 단위, 테스트가 실제로
   검사하는 범위보다 넓게 쓴 문구, 시점 혼동).
5. **대조군 테스트는 데이터에서 나온 값을 비교한다.** 식별자(baseline_id·manifest hash) 차이만으로 통과하는
   대조군은 아무것도 증명하지 않는다.

---

## 7. 다음 사람이 바로 할 일

1. 검증자 판정을 받는다 → 코드 수정 요구면 §5-1 순서로.
2. 설계자 답(§5-2)을 받는다 → PLAN §5 에 반영(같은 V1 갱신) → 작업 6 착수. 먼저 `ml_score_validity_report.py` 분리.
3. §5-3 사용자 결정이 오면 그대로 처리한다. 그 전에는 저장소 안에서 전체 pytest 를 돌리지 않는다.
4. POC4-02(정정된 규율로 기준선 재측정)는 작업 6 이 끝난 뒤다. KRX universe 를 기준선에 쓰는 것은 설계자 승인 뒤다.

---

## 8. 문서

```text
설계자 판정·계획   docs/ai_plan/POC4/POC4-01_DATA_BACKTEST_FOUNDATION_PLAN_V1.md
결과서            docs/ai_result/POC4/POC4-01_DATA_BACKTEST_FOUNDATION_RESULT.md
Master Plan      docs/ai_plan/POC4/POC4-00_ML_QUANT_ADVANCEMENT_MASTER_PLAN_V1.md
legacy 표시       state/ml/validity/LEGACY_BASELINE_NON_REPRODUCIBLE.json
현행 동작         docs/PROGRAM_TRUTH.md §7.1 (연구 저장소 2종) · §8 (KRX Open API)
```

## 9. 사용자 확인

- 화면 확인 없음 · OCI 적용 없음(PC 연구 전용).
- 결정 대기: §5-3 테스트 흔적 처리.
