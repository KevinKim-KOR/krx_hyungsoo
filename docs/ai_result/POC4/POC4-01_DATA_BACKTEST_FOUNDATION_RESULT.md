# POC4-01 — 데이터·백테스트 기반 정비 RESULT (작업 1~5)

```text
STATUS             = 작업 1~5 IMPLEMENTED · 작업 6 착수 전 설계자 확인 대기
NEW_BASELINE       = relative_upside_v1_snap_20260921 · REJECT · 두 번 실행 canonical 동일
LEGACY_BASELINE    = NON_REPRODUCIBLE 표시 · 원본 파일 무변경
KRX_UNIVERSE       = 공식 한도 확인 → canary 통과 → 전체 기간 3,318일 적재 · verify ok · 봉인 (§4-5)
OCI · PUSH = 변경 0     DEPENDENCY_ADDED = 0
LOCAL_LIVE_STATE   = 전체 pytest 가 맥북 라이브 시장 DB·state 에 씀 — 사고 보고 §4-8 (기준선 입력 영향 없음)
```

- **작성**: 개발자(VSCode Claude) · **독자**: 검증자(Codex) · 설계자
- **입력**: 설계자 POC4-01 판정(2026-09-23) · PLAN `docs/ai_plan/POC4/POC4-01_DATA_BACKTEST_FOUNDATION_PLAN_V1.md`
- **코드 commit**: `be579619` (로컬 · push 안 함). 문서·manifest 는 staged — commit 은 사용자 승인 후.

---

## 1) 처리한 요구사항

설계자 "개발자 다음 작업" 6개 + 결정 1·2·3 + 132MB 임시 DB 지시를 1:1 로 대조한다.

| # | 요구사항 | 상태 | 근거 |
|---|---|---|---|
| 1 | legacy baseline 을 비재현 가능으로 명시 · 덮어쓰지 않음 | DONE | §4-1 |
| 2 | immutable snapshot · manifest · fail-closed 입력 경로 | DONE | §4-2 |
| 2a | 라이브 DB 를 직접 읽는 baseline 실행 금지 | DONE | 러너에 `--snapshot-manifest`·`--cutoff`·`--out-dir` 필수 · 평가 중 sqlite 접속 허용 목록 |
| 2b | 145 를 146 으로 단순 수정 금지 | DONE | 상수 삭제 · manifest 평가일 목록과 완전 일치 요구(§4-2) |
| 2c | 함께 고정할 12개 항목 | DONE | §4-3 표 |
| 2d | snapshot 누락·hash 불일치 시 fail-closed | DONE | §4-4 기준 4 |
| 3 | 새 기준선 결정성 검증(기준 1~4) | DONE | §4-4 |
| 4 | KRX universe 별도 research DB + resumable canary | DONE | §4-5 |
| 5 | 공식 호출 한도 확인 전 전체 적재 금지 | DONE | 한도 확인(Gate 1) 뒤 canary(Gate 3·4) 통과 후 적재 |
| 6 | embargo · 성과지표 · 비용 분해 | **SKIPPED** | 설계 결정 3건 필요 — PLAN §5 (embargo 는 E2 label 에 누수가 없음을 코드로 확인) |
| 결정 3 | 고정 모듈 주석 정정 · raw/AST hash 기록 · requirements.txt provenance | DONE | §4-3 |
| 132MB | 4가지 확인 → 새 스냅샷 검증 뒤 그 파일 1개만 삭제 | DONE | §4-6 |
| — | OCI · 운영 DB · PUSH 미접촉 | **PARTIAL** | OCI·PUSH 는 미접촉. 맥북 로컬 라이브 시장 DB 는 **제가 돌린 전체 pytest 가 썼다**(기존 테스트 격리 결함 · §4-8). 평가 입력 테이블은 영향 없음 |

---

## 2) 변경된 파일 목록

`git show --stat be579619` (코드 commit):

| 파일 | 구분 |
|---|---|
| `app/ml_baseline_snapshot.py` | 신규 — 스냅샷 생성·검증·작업 사본 세션·sqlite 접속 제한 |
| `app/ml_baseline_provenance.py` | 신규 — 코드·환경 provenance · run_manifest |
| `app/ml_research_krx_universe.py` | 신규 — KRX 연구 DB · downloader · version |
| `scripts/ml_baseline_tool.py` | 신규 — build / verify / compare CLI |
| `scripts/run_krx_universe_download.py` | 신규 — canary / full / resume / status / verify / seal CLI |
| `scripts/run_ml_score_validity_eval_v1.py` | 수정 — 스냅샷 필수 · `_evaluate` 분리 · run_manifest |
| `app/ml_score_validity_eval.py` | 수정 — `run_e1_gate(snapshot_path=)` · `assert_evaluation_window(dates, expected_dates)` · 145 상수 삭제 |
| `app/ml_relative_upside_model.py` | 수정 — docstring 만(결정 3) |
| `state/ml/validity/LEGACY_BASELINE_NON_REPRODUCIBLE.json` | 신규 — legacy 표시 |
| `.gitignore` | 수정 — 스냅샷 데이터·결과 · 연구 DB · legacy 보존 사본 |
| `tests/test_ml_baseline_snapshot.py` | 신규 (20건) |
| `tests/test_ml_research_krx_universe.py` | 신규 (13건) |
| `tests/test_ml_score_validity_cli.py` | 수정 — 스냅샷으로 실행 |
| `tests/test_ml_score_validity_contracts.py` | 수정 — 평가일 목록 계약 |

문서·manifest (staged · commit 승인 대기):

| 파일 | 구분 |
|---|---|
| `docs/ai_result/POC4/POC4-01_DATA_BACKTEST_FOUNDATION_RESULT.md` | 신규 — 이 문서 |
| `docs/ai_plan/POC4/POC4-01_DATA_BACKTEST_FOUNDATION_PLAN_V1.md` | 수정 — 설계자 판정 반영 · 작업 6 질문 |
| `docs/PROGRAM_TRUTH.md` | 수정 — §7.1 연구 저장소 2종 · §8 KRX Open API |
| `state/ml/baselines/relative_upside_v1_snap_20260921/dataset_manifest.json` | 신규 |
| `state/ml/baselines/relative_upside_v1_snap_20260921/runs/run1/run_manifest.json` | 신규 |
| `state/ml/baselines/relative_upside_v1_snap_20260921/runs/run2/run_manifest.json` | 신규 |

git 밖(PC 로컬 · gitignore): 스냅샷 `dataset.sqlite`(137,666,560 B) · `e1_score_snapshot.json` ·
두 실행의 결과 JSON · 연구 DB `state/ml/research/krx_etf_universe.sqlite`.

---

## 3) 신규 추가된 의존성

없음. KRX 호출은 기존 의존성 `httpx` 를 쓴다(`app/market_briefing/krx_sync.py` 와 같다).

---

## 4) 지시문 외 변경

| 항목 | 이유 |
|---|---|
| `.gitignore` ignore 패턴 9줄 추가(스냅샷 6 · 연구 DB 1 · legacy 보존 사본 1 · 재현 시도 출력 폴더 1) · 기존 주석 1줄을 2줄로 정정 (`git show --numstat` +15/−1 — 새 블록 주석·빈 줄 포함) | 137MB 스냅샷·연구 DB·legacy 보존 사본(`poc4_01_frozen_original/`)·재현 시도 출력 폴더(`poc4_01_repro/`)가 git 에 들어가지 않게. 기존 주석 "재현 가능 산출물" 이 사실과 달라 LEGACY 로 정정 |
| `docs/PROGRAM_TRUTH.md` §7.1·§8 | 새 저장소 2종·외부 source 가 생겨 canonical 문서 갱신 규칙 적용. §8 의 "KRX Open API 잔존 의존은 미발견" 은 시장 브리핑 수집으로 이미 사실과 달라 KRX 행과 모순되므로 함께 교체 |
| `build_frozen_descriptor`·`_node_info` 를 러너에서 `ml_baseline_provenance.py` 로 이동 | 러너를 KS-10 TRIGGER(650) 아래로 유지하려고 새 모듈 쪽으로 옮겼다(run_manifest 작성 함수도 같은 모듈에 새로 둠). 커밋 기준 러너는 554줄(d43db726) → 588줄(be579619). 작업 중 줄 수는 git 에 남지 않아 적지 않는다. 동작은 같고 이름만 `_node_info`→`node_info`, 파일 hash 함수 `file_sha256`→`raw_sha256`(같은 구현) |
| `build_frozen_descriptor(db_path)` 인자 추가 | 가격 투영 hash 를 라이브 DB 가 아니라 작업 사본에서 계산하려면 경로가 필요하다 |

---

## 5) 알려진 한계 / 미완성

- **작업 6 미착수** — embargo 위치 · 비용 수치 · 지표 기준이 설계 결정이다(PLAN §5).
- **E1 은 여전히 `E1_UNAVAILABLE`** — 운영 점수 JSON 이 2026-08-30 에 asof 2026-08-27 로 덮어써졌고
  E1 기준일 상수는 2026-08-20 이다. 원본도 `E1_UNAVAILABLE` 이었으므로 판정은 같다. 스냅샷은 지금
  JSON 을 봉인했을 뿐 E1 을 되살리지 않는다.
- **`market_refresh_log` 는 cutoff 로 자르지 않았다**(최대 asof 2026-09-22). 원본 실행과 같은 복사
  범위다. top-N 응답의 `latest_refresh` 메타데이터에만 쓰이고 슬레이트 종목 선택에는 쓰이지 않는다
  (`app/market_topn.py:389`).
- **KRX 연구 DB 는 아직 평가에 쓰이지 않는다.** 생존편향 제거 백테스트는 POC4-02 이후다
  (`UNBIASED_PERFORMANCE_CLAIM = NOT_YET` 유지).
- 결정성은 **같은 맥북에서** 확인했다. 다른 기계(윈도우 PC)의 torch 결과 일치는 확인하지 않았다.
- **러너의 legacy 폴더 거부는 `state/ml/validity` 경로와 정확히 같을 때만** 작동한다. 하위 폴더(예: 보존
  사본 폴더 `poc4_01_frozen_original/`)를 `--out-dir` 로 주면 그 안의 같은 이름 파일을 덮어쓴다. 코드는
  그대로 두었다(기준선 commit 이후 러너를 바꾸면 기준선 코드 hash 와 달라진다) — 설계자·검증자 판단 요청.
- **KRX 재수집 충돌 기록은 재수집 응답이 TRADED 일 때만** 한다. 같은 날짜가 재수집에서 NON_TRADING·NO_ROWS
  로 오면 raw 는 남지만 비교·충돌 기록은 없다. 현재 데이터 영향 0(충돌 0 · FULL 의 NO_ROWS 0).
- `dataset.sqlite` 의 sha256 은 **파일 바이트** 기준이다. 같은 내용을 다시 복사해 만든 파일은
  hash 가 달라질 수 있어, 내용 hash(테이블별 `content_sha256`)를 따로 남겼다.

---

## 6) 다음 검증자(Codex)에게 알릴 점

1. **코드 commit 을 기준선 실행 전에 로컬로 만들었다.** 결정 3 "새 기준선을 만드는 커밋" 과
   run_manifest 의 코드 commit 을 맞추려면 실행 전에 commit 이 있어야 한다. 러너는 `app/`·`scripts/`·
   `requirements.txt` 에 미커밋 변경이 있으면 공식 실행을 거부한다. push 는 하지 않았다.
2. **라이브 DB 차단은 `sqlite3.connect` 를 프로세스 안에서 바꿔치는 방식**이다
   (`guard_sqlite_paths`). `import sqlite3` 후 `sqlite3.connect(...)` 로 부르는 모든 경로가 걸린다.
   `from sqlite3 import connect` 형태는 `app/`·`scripts/` 에 0건이다(grep).
3. **자체 적대 리뷰에서 결함 5건을 찾아 고친 뒤 commit 했다.**
   - P2 코드 게이트가 손으로 고른 목록만 봐서 `app/market_regime.py`(regime → A3·R4 판정) 수정을
     놓침 → 폴더 단위 게이트 + 실제 import 된 모듈 전부 hash 기록
   - P2 대조군 테스트가 baseline_id·manifest hash 차이만으로 통과(공허) → 기준일별 IC·평가일 비교로 교체
   - P3 실행 중 원본이 바뀌면 결과를 다 쓴 뒤에야 실패 → 쓰기 전 재검증 · E1 도 작업 사본에서 읽음
   - P3 결과 hash 에 manifest 파일 바이트 hash 가 섞여 줄바꿈만 달라도 바뀜 → 내용 hash 로 교체 · LF 고정
   - 새 테스트 2건은 변이(재검증 호출 제거 · E1 을 원본에서 읽기)로 실패하는 것을 확인했다.
4. 평가일 수 계약을 **목록 완전 일치**로 바꿨다. 기존 테스트 3건의 기대값을 목록 기준으로 고쳤고,
   "개수는 같고 날짜만 다른" 경우를 새로 막았다(`test_evaluation_window_rejects_same_count_different_dates`).
5. canary 19개 날짜 중 **토요일(2026-09-19)도 행 1,171개가 왔다** — 기준일자·종목코드·종목명·
   상장주식수·기초지수명만 있고 가격·등락·거래량·거래대금·NAV·시가총액·순자산총액·지수값은 모두 빈 문자열. 기존
   `krx_sync.has_traded_prices` docstring 의 "주말은 행 자체가 없다" 와 다르다. 연구 DB 는 행 유무가
   아니라 가격 유무로 판정해 영향이 없다. 운영 코드는 건드리지 않았다.
6. **사고 보고 §4-8** — 자체 검수로 돌린 전체 pytest 가 맥북 라이브 경로 5곳에 썼다(기존 테스트 격리 결함).
   기준선 입력은 영향이 없음을 날짜별 값 148개 일치로 확인했다. 결함 수정은 이번 범위 밖이라 하지 않았다.
7. 결과서·PLAN·PROGRAM_TRUTH 의 사실 주장을 커밋 전에 두 번 실측 대조했다 — 1차 7개 구역(맞음 315건 ·
   확정 오류 19건), 정정·사고 절 2차 3개 구역(맞음 131건 · 확정 오류 4건). 전부 정정했다. 위 사고도 1차 대조에서 드러났다.

---

## 7) 사용자 확인이 필요한 항목

- **commit·push 승인** — 코드 commit `be579619` 는 로컬에만 있다(push 안 함). 문서·manifest 6개는 staged 상태로
  commit 을 기다린다.
- **KRX Open API 호출** — canary 20회 + 전체 적재 3,319회(3,318개 기준일 + 재시도 1회) = 하루 3,339회.
  설계자 Gate 대로 공식 한도 확인 뒤 진행했다. 받은 데이터는 PC 연구 DB 에만 있고 OCI·운영 DB 로
  가지 않는다(약관 제11조② 제3자 제공 금지).
- **132MB 임시 DB 삭제** — 설계자가 조건부 승인한 파일 1개만 지웠다(§4-6).
- **사고(§4-8) 처리 결정** — 맥북 라이브 경로 5곳(§4-8 표: 시장 DB 1 · state 파일 2 · 로그 2)에 테스트 흔적이 남았다. 복구·정리·결함 수정 모두
  하지 않았다(운영 DB 변경·파일 삭제·범위 밖 코드 수정은 승인 사항). 선택지는 §4-8 끝.
- **연구 DB 용량** — `state/ml/research/krx_etf_universe.sqlite` 가 약 1.86GB 다(원응답 본문을 그대로
  보관하는 계약 때문). 맥북 로컬 디스크에만 있고 git·OCI 로 가지 않는다.

---

## 4. 증거

### 4-1. legacy 표시

`state/ml/validity/LEGACY_BASELINE_NON_REPRODUCIBLE.json` — 원본 두 파일의 sha256·canonical·평가일
145개·재현 실패 원인을 적었다. 원본은 그대로다.

```text
relative_upside_validity_v1_latest.json      a55e7292871106f2436ade0077a6053c4d5243c6ac69d084f51d0f99c9282290
relative_upside_validity_v1_run_latest.json  8d186239d5c7ec405a796e320281b3cdf2fe131f94811af1c036bb8fd0a1d036
```

러너에 `--out-dir state/ml/validity` 를 주면 `RuntimeError`(`test_runner_refuses_legacy_result_dir`).

### 4-2. 불변 스냅샷 `relative_upside_v1_snap_20260921`

```text
cutoff          2026-09-21 (라이브 DB 최신 완료 거래일)
dataset         dataset.sqlite  sha256 6fbde434af60e5e702904c36380b5ab7b906274d6697d2affdf6b1889f603781  (0444)
E1 JSON         e1_score_snapshot.json  sha256 f8c41658…  asof 2026-08-27 · 후보 1,162  (0444)
schema          67041b5a21bc344b1a7b7510e883202c1a9aeaee532272cb1283f26089911d66
manifest 내용   ac890e3e06f9a60d1090223478246c7e2bdce1f6d42e35cdc87e5e4692e2be23

테이블           행 수      종목   최소일 ~ 최대일 (날짜 컬럼)
etf_daily_price  1,405,608  1,186  2014-04-09 ~ 2026-09-21 (date)
etf_master           1,183  1,183  2026-06-22 ~ 2026-09-21 (last_seen_at)
market_refresh_log     645      —  2026-06-17 ~ 2026-09-22 (asof)

평가일           E2 146개 (2014-06-30 ~ 2026-07-31) · warmup 2014-04-30 · 2014-05-30 · 거래일 3,055
```

라이브 `state/market/market_data.sqlite` sha256 앞 16자리: 생성 전 `db0b2e9cf626d1af` · 생성 후
`db0b2e9cf626d1af` · 두 번 실행 후 `db0b2e9cf626d1af`.

### 4-3. 함께 고정한 항목 (결정 1 의 12개)

| 항목 | 위치 | 값 |
|---|---|---|
| dataset snapshot 파일 | bundle | `dataset.sqlite` |
| dataset sha256 | dataset_manifest · run_manifest · 결과 payload | `6fbde434…` |
| data cutoff | 세 곳 모두 | `2026-09-21` |
| 테이블별 행 수·종목 수·최소일·최대일 | dataset_manifest `tables` | §4-2 표 |
| schema hash | dataset_manifest · run_manifest | `67041b5a…` |
| 코드 commit | run_manifest `code.git` | `be579619…` · `code_clean=true` · 게이트 `app`·`scripts`·`requirements.txt` |
| 고정 모듈 raw sha256 | run_manifest `code.frozen_modules` | features `11910654…` · model `b41b2a9a…` · score `8d53aa56…` |
| 정규화 AST hash | 같은 곳 | model `1ba8f5cb…` = 정정 전 `1ba8f5cb…` (docstring 만 바뀜) |
| Python·주요 의존성 | run_manifest `environment` | Python 3.12.13 · torch 2.13.0 · numpy 2.4.6 · pandas 2.3.3 · scipy 1.18.0 · scikit-learn 1.9.0 · SQLite 3.53.1 · requirements.txt `3e427a75…` |
| 실행 인자 | run_manifest `run_arguments` | limit 없음 · E1 포함 · dirty 허용 안 함 |
| 결과 artifact sha256 | run_manifest `result` | 파일 hash + canonical hash |
| 평가일 목록과 개수 | run_manifest `evaluation` | 146개 전체 목록 |

고정 모듈 raw hash 변화: 정정 전 `8cb88f9e…`(legacy frozen_descriptor 와 같음) → `b41b2a9a…`.
정규화 AST 정의: 모듈·클래스·함수 첫 docstring 제거 후 `ast.dump(include_attributes=False)` 의 sha256.

### 4-4. 결정성 검증 (기준 1~4)

**기준 1 — 실제 데이터로 두 번 실행**

```text
             canonical sha256                                                  평가일  시간
run1         e1c02f6657d2d88836dbf254f2beaf2f89aa42f405b077d2e599791f97454000  146    794.8s
run2         e1c02f6657d2d88836dbf254f2beaf2f89aa42f405b077d2e599791f97454000  146    810.1s
compare      identical = true (상태·dataset·manifest 내용·cutoff·commit·모듈 hash·평가일·canonical 전부)
```

결과 파일 sha256 은 `generated_at` 와 `e1.elapsed_seconds`(13.01 vs 14.03) 때문에 다르다(run1 `52e08ddc…` ·
run2 `046448f5…`) — canonical 은 이 두 필드를 뺀다(기존 계약 `NON_DETERMINISTIC_FIELDS`).

**기준 2·3 — 합성 DB 로 실제 러너 실행** (`test_same_snapshot_same_result_even_after_live_db_changes`)

```text
같은 스냅샷 2회              canonical 동일
라이브에 새 날짜 + 과거 행 변경 뒤 같은 스냅샷   canonical · 평가일 · 기준일별 IC 전부 동일
대조군 A (과거 행 변경을 담은 새 스냅샷)          같은 평가일에서 기준일별 (IC·n·상위 10% 평균) 묶음이 달라짐
                                                  (테스트는 묶음 전체 비교 · 합성 실측에서는 IC 가 3개 평가일 모두 달라짐)
대조군 B (새 날짜까지 담은 새 스냅샷)            평가일 목록 자체가 달라짐 (2020-11-20 추가)
```

실제 라이브 DB 는 바꾸지 않았다(쓰기 금지). 대신 평가 중 라이브 DB 접속 자체가 막힌다
(`test_session_serves_working_copy_and_blocks_live_reads`).

**기준 4 — 누락·불일치** (각각 테스트)

```text
manifest 없음 · dataset 없음 · E1 없음                    → SnapshotIntegrityError
dataset·E1 1바이트 변조                                   → "hash 불일치"
러너에 변조된 스냅샷                                       → 실패 · 결과·run_manifest 미기록
실행 중 봉인 원본 변경                                     → 쓰기 전 재검증에서 실패 · 결과·meta·run_manifest 미기록
cutoff 가 manifest 와 다름                                → 실패
--snapshot-manifest 없음                                  → argparse 종료코드 2
코드가 commit 과 다름 (--allow-dirty-code 없이)            → 실패
```

**새 기준선 vs legacy** — 결론이 같다.

| 항목 | legacy (145일) | 새 기준선 (146일) |
|---|---:|---:|
| 최종 | REJECT | REJECT (ceiling RESEARCH_ONLY) |
| A1 평균 IC | −0.04349 | −0.04266 |
| A2 상위 10% net 25bp | −1.214 %/월 | −1.225 %/월 |
| A3 양(+)의 연도 | 4 / 13 | 4 / 13 |
| A4 화면 슬레이트 평균 차이 | −0.00176 | −0.00237 |
| A5 무결성 | 통과 | 통과 |
| R1~R4 | R3 만 true | R3 만 true |
| E1 | UNAVAILABLE | UNAVAILABLE |
| 누수 L1~L3 | 0 | 0 |

겹치는 145개 평가일 중 **1M IC(`ic_filter`·`ic_all`·`ic_simple_momentum`)는 142개가 완전히 같다.** 다른
3개(2026-04-30 · 05-29 · 06-30)는 재적재된 가격 구간이다. 3M IC(`ic_3m`)는 141개가 같고 4개가 다르다 — 3M
청산 구간이 재적재 구간에 걸리는 2026-02-27 · 03-31 · 04-30 이 달라졌고, 2026-05-29 는 원본에서 3M 청산일이
없어 비어 있던 것이 이번에는 계산됐다. 기록 전체가 같은 평가일은 140개(다른 날 2026-02-27 · 03-31 · 04-30 ·
05-29 · 06-30). 새로 생긴 평가일은 2026-07-31(IC +0.0793) 하나다. 1M IC 기준으로 PLAN §1-4 진단과 일치한다.

### 4-5. KRX universe 연구 DB

**Gate 1 — 공식 한도**: PLAN §2-3 (약관 제8조④ 키당 10,000회/일 · 인용 12건 원문 재확인).

**Gate 3·4 — canary** (`CANARY-20260923` 19개 기준일 + `CANARY-20260923-RECHECK` 1회 = 호출 20회)

```text
결과        TRADED 16 · NON_TRADING 3 (2014-12-25 · 2026-01-01 · 2026-09-19 토요일)
verify      미완료 날짜 0 · payload hash 불일치 0 · 응답 내 종목 중복 0 · ISU_CD 없는 행 0 ·
            거래일 누락 0 · 재수집 충돌 0
재수집      2018-06-29 두 번 받은 payload sha256 동일 (3afdb70d…)
재시도      연구 DB 테스트 13건(그중 가짜 fetcher 10건) — 5xx·네트워크 지수 backoff(2s→4s) · 429 즉시 중단 후 이어받기 ·
            401 즉시 중단 · 연속 실패 3회 중단 · 하루 상한 · 끝난 날짜 재호출 0 ·
            재수집 내용이 다르면 충돌 기록 + 기존 version 유지 · 봉인 version 추가 거부
```

**생존편향 대조** (canary 거래일 · 운영 DB 는 읽기 전용 · 섞지 않음)

| 기준일 | KRX 상장 | 운영 DB 그날 | 운영 DB 에 없음 | 누락 비율 |
|---|---:|---:|---:|---:|
| 2014-04-09 | 149 | 103 | 46 | 30.9% |
| 2016-06-30 | 215 | 171 | 44 | 20.5% |
| 2018-06-29 | 372 | 291 | 81 | 21.8% |
| 2020-03-31 | 451 | 351 | 100 | 22.2% |
| 2022-06-30 | 590 | 517 | 73 | 12.4% |
| 2024-06-28 | 863 | 783 | 80 | 9.3% |
| 2025-06-30 | 990 | 951 | 39 | 3.9% |
| 2026-09-21 | 1,171 | 1,171 | 0 | 0.0% |

운영 DB 에 있는데 KRX 에 없는 종목은 2026-07-31 의 3개뿐이고 나머지 날짜는 0 이다.

**Gate 5 — 전체 기간 적재** (`FULL-20260923` · version `krx_etf_universe_v1`)

```text
계획        2014-01-02 ~ 2026-09-21 평일 3,318개 기준일
호출        3,319회 (재시도 1회 — 2019-07-03 ConnectError → 2번째 시도 성공)
            UTC 13:38:36 ~ 14:57:41 · 중단 없음(stopped=null)
결과        TRADED 3,122 · NON_TRADING 196 · 미완료 0
verify      미완료 날짜 0 · payload hash 불일치 0 · 응답 내 종목 중복 0 · ISU_CD 없는 행 0 ·
            거래일 누락 0 · 재수집 충돌 0
행          원응답 행 1,716,983 · 원응답 본문 합계 786,326,655 B (UTF-8 · FULL 3,318건) · 연구 DB 파일 1,862,836,224 B
호출 합계   2026-09-23 KST 하루 3,339회 (canary 20 + 전체 3,319) — 자체 상한 5,000 · 공식 10,000 이하
봉인        krx_etf_universe_v1  SEALED  content_sha256 c1a877762b9b1f296365801030641c86bc4508f4c2643f1a6793e39119f9bb4c
            (canary-20260923 version 은 OPEN 으로 남김 — 기준선에 쓰지 않는다)
```

봉인은 "이후 바뀌지 않는다" 는 기술적 고정이다. **기준선에 이 version 을 쓸지는 설계자 승인 사항**이다.

**거래일 달력 교차 확인** — KRX 가 가격을 준 날(TRADED) 중 2014-04-09 이후 **3,055일이 스냅샷의
KODEX200 거래일 3,055일과 완전히 같다**(양쪽에만 있는 날 0). 나머지 67일은 운영 DB 가 시작하기 전
2014-01-02 ~ 2014-04-08 이다.

**전 기간 생존편향** (각 연도 마지막 거래일 · 스냅샷은 읽기 전용 · 섞지 않음)

| 기준일 | KRX 상장 | 스냅샷 그날 | 스냅샷에 없음 | 누락 비율 |
|---|---:|---:|---:|---:|
| 2014-12-30 | 172 | 118 | 54 | 31.4% |
| 2015-12-30 | 198 | 154 | 44 | 22.2% |
| 2016-12-29 | 256 | 208 | 48 | 18.8% |
| 2017-12-28 | 325 | 265 | 60 | 18.5% |
| 2018-12-28 | 413 | 319 | 94 | 22.8% |
| 2019-12-30 | 450 | 351 | 99 | 22.0% |
| 2020-12-30 | 468 | 392 | 76 | 16.2% |
| 2021-12-30 | 533 | 468 | 65 | 12.2% |
| 2022-12-29 | 666 | 580 | 86 | 12.9% |
| 2023-12-28 | 812 | 714 | 98 | 12.1% |
| 2024-12-30 | 935 | 875 | 60 | 6.4% |
| 2025-12-30 | 1,058 | 1,047 | 11 | 1.0% |
| 2026-09-21 | 1,171 | 1,171 | 0 | 0.0% |

```text
기간 중 KRX ETF 코드   1,419개 — 그중 2026-09-21 에 상장돼 있지 않은 코드 248개
스냅샷에 한 번도 없는 KRX 코드   236개
KRX 에 없는 스냅샷 종목          3개 — 000660 · 005930 · 006400 (개별 주식, 아래)
```

스냅샷에 있는데 KRX 에 없는 종목은 위 연도말 13개 시점 모두 0개다.

**관찰 1건 (수정하지 않음)** — 운영 시장 DB `etf_daily_price` 에 개별 주식 3종목(`000660` ·
`005930` · `006400`)이 각 93행(2026-03-30 ~ 08-12 · source FinanceDataReader) 들어 있다. `etf_master`
에는 없어서 평가기의 종목 목록(`list_etf_tickers`)에 들어가지 않고, 새 기준선 결과의 어떤 상위 목록에도
나오지 않는다(0건). 운영 DB 는 변경 금지라 그대로 두었다.

### 4-6. 132MB 임시 DB

설계자 4가지 확인(2026-09-23 실측): SQLite integrity `ok` · `etf_daily_price` 1,364,822행
2014-04-09~2026-07-31 · 실패한 146일 실행의 **U2 재현용** 입력(E2 는 라이브 DB 를 직접 읽음) ·
평가 입력 전체가 아니므로 기준선 스냅샷으로 승격 불가.

→ 새 스냅샷 생성·`verify` OK·두 번 실행 일치 뒤 **그 파일 1개만** 삭제했다.

```text
삭제 파일   state/ml/validity/poc4_01_repro/_pit_replay.sqlite
크기        132,603,904 B
sha256      5caa649d6f4f90823407501992cba71c881c7cedb32f28f7cb1f0dbe864de397
방법        rm <그 경로> (재귀·폴더 삭제 없음 — 빈 폴더 poc4_01_repro/ 는 남김)
```

### 4-7. 자체 검수

```text
black --check      변경 12개 py 파일 통과
flake8             통과
py_compile         통과
pytest (ML 관련)   261 passed
pytest (전체)      1961 passed (2분 49초) — 이 실행이 §4-8 사고를 냈다
                   저장소 사본에서 다시 실행해도 1961 passed (2분 52초)
KS-10              전수 491 · TRIGGER 0 · NEAR 7 (기존 목록 그대로)
                   러너 588 · eval 589 · snapshot 391 · provenance 274 · krx 532
```

재현 명령:

```text
python scripts/ml_baseline_tool.py verify --manifest state/ml/baselines/relative_upside_v1_snap_20260921/dataset_manifest.json
python scripts/ml_baseline_tool.py compare state/ml/baselines/relative_upside_v1_snap_20260921/runs/run1/run_manifest.json state/ml/baselines/relative_upside_v1_snap_20260921/runs/run2/run_manifest.json
python -m pytest tests/test_ml_baseline_snapshot.py tests/test_ml_research_krx_universe.py tests/test_ml_score_validity_cli.py tests/test_ml_score_validity_contracts.py -q
```

(스냅샷·결과 파일은 PC 로컬이라 다른 기계에서는 `verify`·`compare` 를 재현할 수 없다. manifest 는 git 에 있다.)

### 4-8. 사고 — 자체 검수용 전체 pytest 가 맥북 라이브 state 에 썼다

**무엇이 일어났나** — 2026-09-23 22:49:47 KST 에 자체 검수로 전체 pytest 를 돌렸다. 그 6초 뒤(22:49:53)
맥북 라이브 `state/market/market_data.sqlite` 에 쓰기가 일어났다.

```text
라이브 시장 DB sha256   aa73e85f…  (21:43 KST · 재현 시도 직전 · /private/tmp/claude-501/mkt_before_repro.sha)
                       db0b2e9c…  (22:52 스냅샷 생성 직전 ~ 지금까지 동일)
파일 mtime             2026-09-23 22:49:53 KST
같은 실행이 쓴 것       state/market/nav_discount_refresh_latest.json (22:50:29 · 테스트 값 asof 2024-10-31)
                       state/runs/run_20260923T135127_2dd2891c.json (22:51 · 새 파일)
                       logs/oci_market_data_batch.log · logs/three_push_runtime_cron.log (줄 추가)
```

**원인 — 실측으로 확정** (저장소 사본 `/private/tmp/claude-501/pytest_sandbox` 에서만 실행 · 실제 저장소는
이 실험으로 바뀐 파일 0개)

- `app/market_refresh_service.py:235` `reset_state_for_testing(db_path: Path = DEFAULT_DB_PATH)` — 기본값이
  **함수 정의 시점에** 라이브 경로로 묶인다. 테스트가 모듈 변수 `DEFAULT_DB_PATH` 를 monkeypatch 해도
  이 기본값은 바뀌지 않는다.
- `tests/test_api_holdings_market_evidence.py:40` 이 인자 없이 부른다(호출은 2026-06-03 `e1e5b886` 부터 · 이 함수가 기본값 라이브 경로로 DB 행을
  지우게 된 것은 2026-06-30 `ccbdadd0` 부터) →
  라이브 DB 의 `market_refresh_state` 행을 지운다. 사본에 행 1개를 넣고 이 파일만 돌리면 0행이 되고 DB hash 가
  바뀐다(`515098f5…` → `51879f53…`).
- 106개 테스트 파일을 사본에서 하나씩 돌려 쓰기 주체를 전부 찾았다:

| 라이브 경로 | 쓰기 | 테스트 파일 |
|---|---|---|
| `state/market/market_data.sqlite` | `market_refresh_state` 행 삭제 | `test_api_holdings_market_evidence.py` |
| `state/market/nav_discount_refresh_latest.json` | 테스트 값으로 덮어씀 | `test_market_refresh_state_persistence.py` · `test_market_topn_api.py` |
| `state/runs/run_*.json` | 새 파일 1개 | `test_poc1_loop.py` |
| `logs/oci_market_data_batch.log` | 줄 추가 | `test_market_benchmark_freshness.py` · `test_oci_market_data_refresh.py` |
| `logs/three_push_runtime_cron.log` | 줄 추가 | `test_holdings_risk_alert_runner.py` · `test_intraday_alert_flow_through.py` · `test_market_briefing_flow_through.py` · `test_oci_market_data_refresh.py` · `test_runtime_runner_dry_run.py` · `test_runtime_runner_partial_delivery.py` · `test_runtime_runner_spike_no_signal.py` |

`state/runs/` 에 2026-09-21 자 같은 흔적 파일이 이미 있어, **이전 작업들의 전체 pytest 때도 반복돼 온 기존
결함**으로 보인다. `tests/conftest.py` 의 `_detect_live_market_db_write` 는 `market_benchmark_daily_price`
테이블만 감시해서 이 경로들을 잡지 못한다.

**기준선에 영향 없음**

- 스냅샷이 복사한 3개 테이블(`etf_master` · `etf_daily_price` · `market_refresh_log`)은 삭제된 테이블이 아니다.
  행 수는 pytest 전 측정(1,183 · 1,405,608 · 645)과 스냅샷이 같다.
- pytest **전**(21:43)에 라이브 DB 로 돌린 재현 시도와 pytest **뒤** 스냅샷으로 돌린 run1 의 기준일 148개
  (warmup 2 포함) 로그 값(IC · 표본 수 · 커버리지)이 **전부 같다**. 종목 1,183 · 거래일 3,055 · E1 재현 1,157 도 같다.

**하지 않은 것** — 지워진 `market_refresh_state` 행 복구, 흔적 파일 삭제, 테스트 격리 수정. 운영 DB 변경·
파일 삭제·범위 밖 코드 수정은 승인 사항이다. OCI 와 PUSH 는 영향이 없다(맥북 로컬 파일만).

**선택지 (사용자·설계자 결정)**

```text
(a) market_refresh_state 는 다음 시장 데이터 갱신(POST /market/refresh) 때 다시 써진다 — 그대로 둔다
(b) 흔적 파일(state/runs/run_20260923T135127_2dd2891c.json 등) 정리 — 삭제 승인 필요
(c) 테스트 격리 수정 — 위 표의 경로를 conftest 에서 tmp 로 돌리고, 라이브 경로 쓰기 감시를 이 5곳으로 넓힌다
    (별도 작업 · 코드 변경)
```
