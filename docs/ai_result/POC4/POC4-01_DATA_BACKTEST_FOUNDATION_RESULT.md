# POC4-01 — 데이터·백테스트 기반 정비 RESULT

```text
STATUS             = 작업 1~6 · 테스트 격리 · 검증자 P1 · 설계자 3차 판정 교정 IMPLEMENTED
                     · 설계자 확인 완료(§6-3 기존 테스트 수 93 → 233 → 목록 229 · 감시 읽기 예외 2 승인)
                     · 개발자 사전 점검(검증 항목 1~8) → 가드 우회 경로 보강(§4-13 · 테스트 코드만)
                     → READY_FOR_LIMITED_REVERIFICATION
NEW_BASELINE       = relative_upside_v1_snap_20260921 · REJECT
                     run5 = run6 canonical 066ba09a… · E2 핵심 hash = e1c02f66… 그대로 (E2 무변경)
LEGACY_BASELINE    = NON_REPRODUCIBLE 표시 · 원본 파일 무변경
KRX_UNIVERSE       = 전체 기간 3,318일 적재 · verify ok · 봉인 (§4-5) · 설계자 승인: POC4-02 연구 기준선 입력(RESEARCH_ONLY)
TEST_ISOLATION     = 쓰기 가드 + 라이브 DB 는 읽기 전용 세션 사본(기존 테스트 229건 목록만 · 사본 hash·integrity 검사
                     · 사본 보호 · ATTACH/VACUUM INTO 차단 · 삼킨 가드 오류도 실패)
                     저장소 전체 회귀 2,013 passed · 라이브 5곳 전후 동일
AC-8               = NAV 요약 JSON 지정 경로 1개만 · 그 밖 JSON 0 (§4-12) · NAV 요약 오염 파일은 격리 보존 (§4-8 (d))
OCI · PUSH = 변경 0 · push 보류(설계자 PUSH = HOLD)     DEPENDENCY_ADDED = 0
```

- **작성**: 개발자(VSCode Claude) · **독자**: 검증자(Codex) · 설계자
- **입력**: 설계자 POC4-01 판정 1차(2026-09-23) · 2차 · 3차(2026-09-24) · 검증자 1차 판정 REJECTED(P1 산출물 보호) ·
  2차 BLOCKED(설계자 계약 2건) · PLAN `docs/ai_plan/POC4/POC4-01_DATA_BACKTEST_FOUNDATION_PLAN_V1.md`
- **검증 범위(설계자 지시)**: `be579619` 부터 최종 문서 commit 까지 — 모두 로컬 · push 안 함.

```text
be579619  feat  불변 스냅샷 기준선 입력 경로 + KRX universe 연구 DB        (작업 1~5 코드)
02a0f7c5  docs  1차 결과서 · PLAN · PROGRAM_TRUTH(§7.1·§8) · 기준선 manifest(dataset · run1·run2) · 중간 인계  (사용자 직접 지시로 commit — §6-1)
71d50d15  fix   테스트 라이브 격리 · 산출물 보호 · 작업 6                   (코드)
bdffdb4b  docs  결과서 · PLAN · PROGRAM_TRUTH(§7.1 스냅샷 행) · 기준선 manifest(run3·run4) · 인계 문서 표시
2d6547b3  fix   strategy_performance active_return 산식 문구                 (코드 · 설계자 3차 §4)
abf833ee  test  세션 사본 조건 · AC-8 NAV JSON 계약 · 라이브 커버리지 단언 4건 고정 입력  (테스트 · 설계자 3차 §1·§2)
29839c75  test  가드 우회 경로 보강 — 검증 항목 사전 점검                      (테스트 · 설계자 확인 뒤 · 사용자 결정 · §4-13)
(최종)    docs  이 결과서 · PLAN(판정 3차 · 설계자 확인) · 기준선 manifest(run5·run6) · 인계 문서 표시
```

---

## 1) 처리한 요구사항

### 1-1. 설계자 1차 판정 — 작업 1~5 · 결정 1·2·3 · 132MB

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
| 결정 3 | 고정 모듈 주석 정정 · raw/AST hash 기록 · requirements.txt provenance | DONE | §4-3 |
| 132MB | 4가지 확인 → 새 스냅샷 검증 뒤 그 파일 1개만 삭제 | DONE | §4-6 |

### 1-2. 설계자 2차 판정 (2026-09-24) · 검증자 P1

| # | 요구사항 | 상태 | 근거 |
|---|---|---|---|
| 순서 1 | staged 문서·manifest 로컬 checkpoint 커밋 | DONE | `02a0f7c5` — 판정 전에 사용자 직접 지시로 이미 commit(§6-1) |
| 순서 2 | 테스트 사고 증거 기록(경로·크기·hash·mtime·테스트 근거·운영 기록과 안 섞인 근거) | DONE | §4-8 |
| 순서 3 · (b) | 테스트 **단독 생성** 가짜 파일만 삭제 · 공유 로그 전체 삭제 금지 | DONE | 1개 삭제. 나머지는 근거 부족·덮어쓴 산출물·공유 로그라 남김(§4-8) |
| (a) | 시장 DB `market_refresh_state` 1행은 그대로 · 가짜 복원·억지 갱신 금지 | DONE | 손대지 않음 |
| 순서 4 · (c) | 격리 · 라이브 경로 즉시 실패 guard · 5곳 전후 hash · 역검증 · 회귀 후 불변 | DONE | §4-9 — sqlite 는 "즉시 실패" 대신 **읽기 전용 세션 사본**(쓰기는 즉시 실패) — 설계자 3차 판정 `LIVE_DB_TEST_ACCESS = READONLY_SESSION_COPY` 로 확정 |
| 순서 5 · 3-1 | purge·embargo 20거래일 — 모델·설정 선택 분할 · E2 변경 0 · 고정 모듈 변경 0 · 날짜 계약 · 한 줄 침범 실패 · 설정 3개 같은 분할 | DONE | §4-10 |
| 3-2 | 거래비용 — 거래세 0 · 수수료 1.5bp(ASSUMPTION) · 슬리피지 5/10/25/50 · 기본 11.5bp · legacy 25bp 유지 · 50bp 스트레스 · 세금 제외 명시 | DONE | §4-10 |
| 3-3 | 절대·상대 성과지표 · 상대 = equity 비율 · Sharpe_0rf | DONE | §4-10 |
| 순서 6 | 전체 회귀 · KS-10 · 라이브 5곳 불변 | DONE | §4-7 |
| 순서 7 | 결과서 최종 갱신 | DONE | 이 문서 |
| 순서 8~10 | 검증자 → VERIFIED 뒤 push → handoff | 대기 | 설계자 순서 |
| 검증자 P1 | legacy 하위 폴더 허용 · 기존 out-dir 재사용 시 이전 결과 잔존 | DONE | §4-11 — 새 폴더만 허용, 기준선 두 번 재실행(run3·run4) |
| 검증자 A-2 | "문서는 staged" 문구가 commit 뒤 사실과 달랐다 | DONE | 이 문서에서 commit 목록으로 교체 |
| — | OCI · 운영 PUSH · 운영 DB 변경 없음 | DONE | 사고(§4-8)는 격리 수정 전 맥북 로컬 파일 · 이번 단계 전체 회귀는 라이브 5곳 불변 |

### 1-3. 설계자 3차 판정 (2026-09-24) — 검증자 2차 BLOCKED 해소

| # | 요구사항 | 상태 | 근거 |
|---|---|---|---|
| §1 | 라이브 DB 는 사본 생성 때만 읽음 · 테스트 sqlite 연결은 모두 사본 mode=ro · 쓰기 즉시 실패 | DONE · 감시 읽기 예외(설계자 승인) | 테스트 코드에서 라이브 DB 경로로 오는 연결(`sqlite3.connect`·`dbapi2`·`_sqlite3`)은 목록 테스트면 세션 사본(mode=ro), 목록 밖이면 즉시 거부. SQL 안의 `ATTACH '<경로>'`·`VACUUM INTO` 는 대상이 라이브·사본이면 거부(파일을 열지 않는다) · `ATTACH ?`·식은 SQLite 가 파일을 한 번 열지만 그 별칭 접근은 모두 거부되고 테스트가 실패한다(§4-9 · §4-13 · §5). 설계자가 승인한 감시 읽기 예외 2곳 = 세션 전후 hash(파일 바이트 읽기 · sqlite 아님) · 기존 감시 fixture 의 테스트별 benchmark 테이블 mode=ro 조회 — sqlite 로 라이브 DB 를 여는 곳은 이 benchmark 조회 1곳뿐. 파일 바이트로 전후만 비교하는 읽기 전용 감시는 §5 에 모두 적었다 |
| §1 | 사본 생성 전후 라이브 hash 가 다르면 실패 · 사본 SQLite integrity 검사 | DONE | §4-9 사본 검사·사본 보호(0444 · 세션 끝 재측정) · 역검증 테스트 5건(`verified_copy` 3 · 사본 보호 1 · 세션 끝 재측정 1) |
| §1 | 라이브 DB·5곳 hash 전후 동일 | DONE | §4-9 · §4-7 |
| §1 | 운영 코드 기본 경로 계약 무변경 | DONE | 이번 테스트 commit 은 `app/`·`scripts/` 변경 0 |
| §1 | 새 테스트는 자체 임시 DB·고정 fixture · 호환 경로는 기존 테스트에만 | DONE · **수치 정정** | 기존 테스트 목록 + 목록 밖 연결 즉시 거부(앱 코드가 삼켜도 테스트 실패) + 목록 상한·정렬. 판정문의 "93건" 은 개발자 과소 집계 — 실측 233건(§4-9 · §6-3) |
| §1 | 정확한 데이터값 단언 테스트에는 사본 금지 | DONE | 233건 전수 분류 → 4건 고정 종가로 전환·목록 제외 → 229건(§4-9) |
| §1 | 기존 테스트 고정 fixture 전환 = 비차단 기술부채 · POC4-01 인계에 기록 | 대기 | 최종 인계(VERIFIED·push 뒤)에 기록 · §5 |
| §2 | AC-8 — NAV 요약 지정 경로 정확히 1개 · schema·기준일·status·집계 · 그 밖 JSON 0 · 라이브 경로 0 | DONE | §4-12 |
| §2 | 운영 코드의 NAV JSON 쓰기 유지 | DONE | `app/market_refresh_service.py` 는 POC4-01 전 기간 변경 0(`git log be579619~1..` 0건) · abf833ee 는 `app/` 변경 0 |
| §3 | 현재 NAV 요약 증거 기록(경로·hash·크기·mtime·테스트 값 근거) · 활성 경로 밖 격리 보존 · 수동 편집·합성 금지 | DONE | §4-8 (d) |
| §3 | 실행 기록 156개 · 공유 로그 2개 유지 | DONE | 손대지 않음 |
| §4 | `formulas.active_return` 에 월평균 active return · tracking error · information ratio 명시 | DONE | `2d6547b3` · `test_active_return_formula_text_names_every_actual_use` |
| §4 | 기준선 두 번 재실행 — 결과 동일 · E2 핵심 hash 동일 · 산식·설명 외 전략 결과 변화 0 | DONE | §4-4 run5·run6 |
| §5 | `krx_etf_universe_v1` 연구 기준선 입력 승인 · POC4-02 규칙 | 기록 | PLAN 판정 3차 · 최종 인계에 옮김 |
| §6 순서 5 | 전체 회귀 1,997건 이상 · 라이브 5곳 불변 | DONE | §4-7 · §4-9 |
| §6 순서 6 | 결과서 갱신 | DONE | 이 문서 |
| §6 순서 7~9 | 검증자 제한 재검증 → VERIFIED 뒤 로컬 commit 전부 push → push 된 HEAD 확인 → 최종 인계 → 설계자 종료 보고 | 대기 | 설계자 확인 완료(§6-3) — 검증자 차례 |

---

## 2) 변경된 파일 목록

`be579619` (작업 1~5 코드):

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
| `tests/test_ml_baseline_snapshot.py` | 신규 |
| `tests/test_ml_research_krx_universe.py` | 신규 (13건) |
| `tests/test_ml_score_validity_cli.py` · `tests/test_ml_score_validity_contracts.py` | 수정 — 스냅샷으로 실행 · 평가일 목록 계약 |

`02a0f7c5` (문서): `docs/ai_result/POC4/…_RESULT.md`(신규) · `docs/ai_plan/POC4/…_PLAN_V1.md` · `docs/PROGRAM_TRUTH.md`
(§7.1 연구 저장소 2종 · §8 KRX Open API) · `docs/handoff/POC4-01_BASELINE_SNAPSHOT_KRX_UNIVERSE_HANDOFF_2026-09-24.md`(신규 ·
중간 인계) · `state/ml/baselines/relative_upside_v1_snap_20260921/{dataset_manifest.json, runs/run1, runs/run2 run_manifest.json}`(신규).

`71d50d15` (수정 · 작업 6 코드):

| 파일 | 구분 |
|---|---|
| `tests/_live_guard.py` | 신규 — 라이브 state/logs 쓰기 가드 · 라이브 DB 읽기 전용 세션 사본 |
| `tests/conftest.py` | 수정 — 가드 설치(app import 전) · NAV 요약·러너 로그 tmp 격리 · 세션 전후 5곳 비교 · 감시는 실제 파일 |
| `tests/test_live_state_guard.py` | 신규 (14건) — 역검증 |
| `tests/test_poc1_loop.py` | 수정 — `monkeypatch.undo()` → 구간 `monkeypatch.context()` |
| `tests/test_api_holdings_market_evidence.py` | 수정 — `reset_state_for_testing(db_path=fake_db)` |
| `app/ml_strategy_performance.py` | 신규 — 비용 분해 · 절대·상대 성과지표 |
| `app/ml_research_split.py` | 신규 — purge·embargo 20거래일 선택 분할 |
| `scripts/run_ml_score_validity_eval_v1.py` | 수정 — 새 폴더 강제 · 성과 블록 · E2 핵심 hash |
| `app/ml_baseline_snapshot.py` | 수정 — `new_run_dir`(legacy 하위·별칭·기존 폴더 거부) |
| `app/ml_baseline_provenance.py` | 수정 — run_manifest `e2_core_canonical_sha256` |
| `tests/test_ml_backtest_metrics.py` · `tests/test_ml_backtest_embargo.py` | 신규 (7건 · 11건) |
| `tests/test_ml_baseline_snapshot.py` (현재 24건) · `tests/test_ml_score_validity_cli.py` | 수정 — 산출물 보호 · E2 핵심 hash |

`bdffdb4b` (문서): 결과서 · PLAN(2차 판정 · §5 설계자 결정) · 인계 문서(맨 위 "중간 인계" 표시) ·
`docs/PROGRAM_TRUTH.md`(§7.1 스냅샷 행 — 실행마다 새 `--out-dir` · 결과에 `strategy_performance`) ·
`state/ml/baselines/relative_upside_v1_snap_20260921/runs/{run3,run4}/run_manifest.json`(신규).

`2d6547b3` (산식 문구 · 설계자 3차 §4):

| 파일 | 구분 |
|---|---|
| `app/ml_strategy_performance.py` | 수정 — `formulas.active_return` 문구 · 모듈 docstring 1곳(계산 코드 무변경) |
| `tests/test_ml_backtest_metrics.py` | 수정 — 문구가 실제 쓰임 3가지를 모두 적는지 테스트 1건 추가(현재 8건) |

`abf833ee` (테스트 · 설계자 3차 §1·§2 · §3 gitignore):

| 파일 | 구분 |
|---|---|
| `tests/_live_guard.py` | 수정 — 사본 검사(hash 3개 · integrity) · 기존 테스트 목록 · 기록 모드 · 목록 밖 즉시 실패 |
| `tests/_live_db_legacy_readers.txt` | 신규 — 세션 사본을 쓸 수 있는 기존 테스트 229건(줄이기만 함) |
| `tests/conftest.py` | 수정 — 테스트마다 nodeid 를 가드에 알림 · 종료 때 `[live-db-copy]` 출력 |
| `tests/test_live_state_guard.py` | 수정 — 5건 추가(목록 밖 실패 · 목록 상한 · 사본 hash·integrity · 복사 중 변경 · 손상 DB) · 이 commit 기준 19건 |
| `tests/test_market_topn_api.py` | 수정 — AC-8 테스트 교체(§4-12) |
| `tests/test_intraday_config_integration.py` · `tests/test_intraday_config_contracts.py` | 수정 — 라이브 커버리지 단언 4건 고정 종가(§4-9) |
| `.gitignore` | 수정 — `state/market/*.quarantine-*` (NAV 요약 격리 사본 · §4-8 (d)) |

`29839c75` (테스트 · 사전 점검 뒤 가드 보강 · §4-13):

| 파일 | 구분 |
|---|---|
| `tests/_live_guard.py` | 수정 — ATTACH·VACUUM INTO 차단(authorizer·trace) · 사본 보호·세션 끝 재측정 · 경로 판정 보강 · 다른 진입점 가드 · 막은 연산 기록 |
| `tests/conftest.py` | 수정 — 삼킨 가드 오류도 실패 · three_push 감시는 되돌려 쓰지 않고 실패만 · `[live-db-copy]` 세션 끝 재확인 |
| `tests/test_live_state_guard.py` | 수정 — 10건 추가 · 기록 모드 skip · 목록 정렬·중복 0 · 현재 29건 |
| `tests/_live_db_legacy_readers.txt` | 수정 — 머리말만(목록 229건 그대로) |

최종 문서 commit: 이 결과서 · PLAN(판정 3차 · 설계자 확인) · 인계 문서(맨 위 판정 표시) ·
`state/ml/baselines/relative_upside_v1_snap_20260921/runs/{run5,run6}/run_manifest.json`(신규).

git 밖(PC 로컬 · gitignore): 스냅샷 `dataset.sqlite`(137,666,560 B) · `e1_score_snapshot.json` · 여섯 실행의 결과 JSON ·
연구 DB `state/ml/research/krx_etf_universe.sqlite` · NAV 요약 격리 사본(§4-8 (d)).

---

## 3) 신규 추가된 의존성

없음. KRX 호출은 기존 의존성 `httpx` 를 쓴다(`app/market_briefing/krx_sync.py` 와 같다).

---

## 4) 지시문 외 변경

| 항목 | 이유 |
|---|---|
| `.gitignore` ignore 패턴 9줄 추가(스냅샷 6 · 연구 DB 1 · legacy 보존 사본 1 · 재현 시도 출력 폴더 1) · 기존 주석 1줄을 2줄로 정정 (`git show --numstat` +15/−1 — 새 블록 주석·빈 줄 포함) | 137MB 스냅샷·연구 DB·legacy 보존 사본(`poc4_01_frozen_original/`)·재현 시도 출력 폴더(`poc4_01_repro/`)가 git 에 들어가지 않게. 기존 주석 "재현 가능 산출물" 이 사실과 달라 LEGACY 로 정정 |
| `docs/PROGRAM_TRUTH.md` §7.1·§8 (02a0f7c5) · §7.1 스냅샷 행 재갱신(bdffdb4b — 새 out-dir · `strategy_performance`) | 새 저장소 2종·외부 source·러너 계약 변경이 생겨 canonical 문서 갱신 규칙 적용. §8 의 "KRX Open API 잔존 의존은 미발견" 은 시장 브리핑 수집으로 이미 사실과 달라 KRX 행과 모순되므로 함께 교체 |
| `build_frozen_descriptor`·`_node_info` 를 러너에서 `ml_baseline_provenance.py` 로 이동 · `new_run_dir` 를 스냅샷 모듈에 둠 | 러너를 KS-10 NEAR(600) 아래로 유지하려고 새 모듈 쪽으로 옮겼다. 커밋 기준 러너는 554줄(d43db726) → 588줄(be579619) → 599줄(71d50d15). 동작은 같고 이름만 `_node_info`→`node_info`, 파일 hash 함수 `file_sha256`→`raw_sha256`(같은 구현) |
| `build_frozen_descriptor(db_path)` 인자 추가 | 가격 투영 hash 를 라이브 DB 가 아니라 작업 사본에서 계산하려면 경로가 필요하다 |
| conftest 의 NAV 요약 격리 경로를 `tmp_path/_side_outputs/` 하위로 | 부수 출력을 테스트 자체 파일과 구분하려고. 새 AC-8 테스트(§4-12)는 이 지정 경로의 파일 1개를 직접 본다 |
| 가드가 `os.utime`·`os.link`·`os.symlink` 도 막음 · `new_run_dir` 가 별칭 경로(samefile)도 봄 · `require_same_split` 설정 3개 상한 | 2차 적대 리뷰에서 "계약 위반은 아님" 으로 기각된 지적 4건 중 비용이 작은 보강을 넣었다(§6-5) |
| 중간 인계 문서 맨 위에 "중간 인계 · 정본은 결과서" 표시 · 설계자 확인 뒤 그 줄의 판정값을 `HANDOFF = AFTER_VERIFIED_AND_PUSH` 로 | 새 인계는 VERIFIED·push 뒤. 이미 commit 된 문서가 stale 로 읽히지 않게 표시만 |
| 사전 점검 뒤 가드 보강(ATTACH·VACUUM INTO · 사본 보호 · 경로 별칭 · 다른 진입점 · 삼킨 오류 실패) · conftest 되돌려 쓰기를 실패만으로 | 설계자 조건(쓰기 즉시 실패 · 감시는 읽기 전용)을 코드가 실제로 지키게 — 사용자 결정 "테스트 코드 보강 후 검증자"(§4-13). 운영 코드·기준선 무변경 |
| `.gitignore` 에 `state/market/*.quarantine-*` 1줄(+주석 1줄) | 설계자 3차 §3 "활성 경로 밖 이름으로 격리 보존" — 보존 사본이 git 에 들어가지 않게 |
| 반박 검증이 뒤집은 2건도 고정 종가로 전환(확정 2건 + 2건) | 같은 단언(`>= 20`)·같은 의존(최신일 종가 커버리지)을 한쪽만 사본에 두지 않으려고 — 판단 근거 §4-9 · §6-4 |
| 가드 기록 모드 `KRX_LIVE_DB_READERS_RECORD` | 기존 테스트 목록을 추측이 아니라 전체 회귀 실측으로 만들려고. 평소 실행에는 영향 없음(환경 변수가 있을 때만) |

---

## 5) 알려진 한계 / 미완성

- **E1 은 여전히 `E1_UNAVAILABLE`** — 운영 점수 JSON 이 2026-08-30 에 asof 2026-08-27 로 덮어써졌고 E1 기준일 상수는
  2026-08-20 이다. 원본도 `E1_UNAVAILABLE` 이었으므로 판정은 같다.
- **`market_refresh_log` 는 cutoff 로 자르지 않았다**(최대 asof 2026-09-22). 원본 실행과 같은 복사 범위다. top-N 응답의
  `latest_refresh` 메타데이터에만 쓰이고 슬레이트 종목 선택에는 쓰이지 않는다(`app/market_topn.py:389`).
- **KRX 연구 DB 는 아직 평가에 쓰이지 않는다** — 생존편향 제거 백테스트는 POC4-02 이후(`UNBIASED_PERFORMANCE = NOT_YET`).
- 결정성은 **같은 맥북에서** 확인했다. 다른 기계의 torch 결과 일치는 확인하지 않았다.
- **KRX 재수집 충돌 기록은 재수집 응답이 TRADED 일 때만** 한다(현재 데이터 영향 0 · 충돌 0 · FULL 의 NO_ROWS 0).
- `dataset.sqlite` 의 sha256 은 **파일 바이트** 기준이다. 내용 hash(테이블별 `content_sha256`)를 따로 남겼다.
- **성과지표 한계** — MDD 는 월별 기간 말 equity 기준(월중 낙폭 미반영) · 첫 달 비용 0(A2 와 같은 규칙) · 가격수익률
  기준(분배금 미반영 — 기존 `PRICE_BASIS_LABEL`) · 무위험수익률 0(`Sharpe_0rf`) · 생존편향이 남은 universe.
- **purge·embargo 분할은 아직 소비자가 없다** — RF 설정 선택(POC4-03)이 이 분할을 받아 쓴다. 이번에는 분할과 계약 검사만.
- **남긴 테스트 흔적** — `state/runs/` 의 과거 실행 기록 156개(모양은 테스트 산출물과 같지만 파일마다 출처 증명 불가) ·
  공유 로그 2개(§4-8). NAV 요약은 격리 사본으로 보존했고 활성 경로는 비어 있다(§4-8 (d)). 이 파일을 읽는 코드는 수동 진단 스크립트
  (`scripts/run_push_content_gap_diagnosis.py` → `artifact_status`, 존재·크기·mtime 만)뿐이라, 다음 정상 NAV 갱신 전까지 그 진단이
  "없음" 으로 보고한다. 화면·API·발송은 이 파일을 읽지 않는다(`app`·`scripts` grep).
- **기존 테스트 229건이 아직 라이브 DB 세션 사본을 읽는다** — 고정 fixture 전환은 설계자가 정한 비차단 기술부채다.
  최종 인계에 목록 파일(`tests/_live_db_legacy_readers.txt`)과 함께 기록한다. 사본은 세션 시작 시점의 라이브 데이터라,
  라이브 데이터가 바뀌면 이 테스트들의 결과가 바뀔 수 있다(정확한 값 단언은 §4-9 에서 뺐다). "목록은 줄이기만" 의 자동 검사는
  개수 상한뿐이라, 항목을 바꿔치기하면 테스트가 잡지 못한다(목록 파일 diff 로만 보인다) — 설계자 확인에서 비차단 기술부채로
  기록 · 목록은 정렬·중복 0 을 유지하고 변경 diff 는 검증자가 확인한다.
- 가드는 **이 pytest 프로세스 안**의 쓰기만 막는다. 하위 프로세스 쓰기는 막지 못하고 사후 감지만 된다 — 세션 종료 전후
  비교(state/·logs/ 전체)와, 일부 대상(시장 DB benchmark 테이블 · state/three_push 상태 파일 6개)의 테스트별 전후 비교.
- 가드가 보지 못하는 쓰기 통로(저장소 코드·테스트에 사용처 0): `io.FileIO(...)` 직접 생성 · `sqlite3.Connection(...)` 직접 생성 ·
  파일 디스크립터로 부르는 연산(`os.fchmod`·`os.ftruncate`·`os.chmod(fd)` 등) · 세션 전부터 있던 하드링크. 파일 생성·삭제·
  이름 변경·크기·mtime 변경은 세션 전후 비교(state/·logs/ 파일의 크기·mtime)로 사후에 잡히지만, 권한·소유자·플래그만 바꾸는
  것과 빈 폴더 생성·삭제는 그 비교에도 안 잡힌다. (`posix.*` 직접 호출 · `os.chown`·`mkfifo` 등은 29839c75 에서 막았다.)
- `ATTACH ?`(매개변수)·식으로 라이브 경로를 붙이면 그 별칭 접근은 모두 거부되고 테스트가 실패하지만(앞에 SQL 주석이 붙어도
  같다), SQLite 가 그 파일을 한 번 연다 — 읽기 전용 URI 가 아니고 없는 경로면 빈 파일이 생길 수 있고 세션 전후 비교가 잡는다.
- **라이브 파일을 직접 읽는 곳**(모두 읽기 전용 · 라이브 값 단언 없음): 설계자 승인 감시 2곳(세션 전후 hash · 테스트별
  benchmark 조회 mode=ro) 밖에 전후 바이트 비교 — conftest 의 three_push 상태 파일 6개, 기존 테스트 3개
  (`runtime_evidence/test_failure_paths.py::test_composer_does_not_touch_real_market_db` 시장 DB 바이트 hash ·
  `test_runtime_state_isolation.py` `state/runtime/runtime_state.sqlite` 바이트·stat · `test_market_briefing_flow_through.py::
  test_repo_state_file_is_not_touched` `state/three_push/` 시장 브리핑 상태 바이트), 새 AC-8 테스트(라이브 NAV 요약 경로 —
  지금은 파일이 없어 읽지 않는다) — 와 가드 자체 테스트 1개(`test_reads_and_tmp_writes_are_allowed` 가 라이브 state/ JSON
  하나를 1바이트 읽는다)가 있다. sqlite 로 라이브 DB 를 여는 곳은 conftest 의 benchmark 감시(`real_connect` · mode=ro) 1곳뿐이다
  — 세션 전후 hash 는 파일 바이트 sha256 이다.
  감시 조회는 라이브 DB 가 rollback journal 모드(지금 `delete`)일 때만 파일을 만들지 않는다 — WAL 로 바뀌면 mode=ro 연결도
  -wal·-shm 을 만든다(지금 WAL 설정 코드 0).
- **AC-8 테스트가 못 보는 곳** — tmp_path · 라이브 state/·logs/ 밖(예: 저장소 data/ · 시스템 tmp)에 쓰는 JSON. 라이브 경로 JSON 은
  가드가 막고 삼켜도 테스트가 실패한다.
- **운영 코드의 옛 설명 주석이 AC-8 계약과 반대다**(이번 Step 운영 코드 무변경 조건이라 두었다) — `app/market_refresh_service.py:8`
  "JSON artifact 생성하지 않는다" · `app/api_market_topn.py:14` · `app/market_topn.py:4`. 다음 운영 코드 Step 에서 고친다.
- 호환 목록 id 는 저장소 루트에서 pytest 를 돌린 nodeid 기준이다(pytest ini 없음) — 다른 폴더에서 돌리면 229건이 모두
  목록 밖으로 판정돼 실패한다(닫힌 쪽으로 실패).

---

## 6) 다음 검증자(Codex)에게 알릴 점

1. **`02a0f7c5` 는 사용자 직접 지시로 만든 commit 이다.** 2026-09-24 사용자가 "인계 문서 작성(3) · commit 과 push(1)" 를
   지시했다. commit 은 했고, push 는 도구 권한 검사가 막아 **실행되지 않았다**. 그 뒤 설계자가 `CODE_PUSH = HOLD` 로
   정했다. 사용자는 이 지시 사실을 설계자·검증자에게 아직 전하지 않았다고 알려 왔다 — 이 보고로 함께 전한다.
   설계자 3차 판정: 중간 인계와 `02a0f7c5` 는 사용자 직접 지시로 생성됐다는 기록을 유지하고 별도 문제로 취급하지 않는다.
2. **코드 commit 이 기준선 실행보다 먼저다.** run_manifest 의 코드 commit 과 맞추려면 실행 전에 commit 이 있어야 하고,
   러너는 `app/`·`scripts/`·`requirements.txt` 에 미커밋 변경이 있으면 공식 실행을 거부한다. `71d50d15` 뒤 기준선을
   **새 폴더 run3·run4 로 두 번 다시** 돌렸고(run1·run2 는 `be579619` 기록으로 남김), 산식 문구 정정 `2d6547b3` 뒤
   run5·run6 으로 다시 두 번 돌렸다.
3. **기존 테스트 수 정정 — 설계자 판정문의 "93건" 은 개발자 과소 집계였다(설계자 확인 완료).** 3차 판정의 세션 사본
   조건 "기존 93건에만 호환 경로로 허용" 은 개발자가 2차 보고에서 전한 93 을 받은 것이다. 그 93 은 가드 첫 버전에서 rw 연결이
   막혀 **실패한** 수다 — `mode=ro` 로 라이브 DB 를 읽는 테스트와, rw 로 열었지만 오류를 코드가 삼켜 통과한 테스트는 세지
   않았다. 전수 실측은 **233건**(29839c75 전 측정: 목록을 비우면 199건 실패 · 34건 통과 — 29839c75 부터는 삼킨 가드 오류도
   실패시키므로 목록 229건 전부 실패, §4-13)이다
   (§4-9). 판정의 뜻("기존 테스트에만 · 새 테스트는 금지")대로 기존 233건을 목록으로 고정하고 목록 밖은 즉시 실패시켰으며,
   라이브 커버리지 단언 4건을 빼 **229건**으로 줄였다. 그 93건은 모두 229건 목록 안에 있다(첫 가드 실행 실패 목록과
   대조). 글자 그대로 93건만 허용하면 나머지 136건(229 − 93)을 모두 이번 Step 에서 고정 fixture 로 바꿔야 한다 — 29839c75
   부터는 앱 코드가 삼킨 가드 오류도 테스트를 실패시키므로 136건 모두 사본 없이는 실패한다(29839c75 전 측정으로는 102건
   실패(intraday_config 90 · 가드 역검증 2 · 그 밖 10) · 34건 통과, §4-9 · §4-13). 설계자가 "비차단 기술부채" 로 정한 범위라
   하지 않았다.
   설계자 확인(2026-09-24): `DESIGNER_CONFIRMATION = ACCEPTED` · `LEGACY_READONLY_ALLOWLIST = 229` ·
   `MONITORING_READ_EXCEPTIONS = 2 (READ-ONLY ONLY)` — 계측 범위를 바로잡은 결과로 수용. 목록은 정렬·중복 0 이다(실측).
4. **라이브 커버리지 단언 4건 — 반박된 2건도 전환했다.** 에이전트 분류에서 EXACT 4건 중 반박 검증이 2건을 뒤집었다
   (`test_api_shows_candidate_after_generation` · `test_unmatched_index_is_recorded_not_dropped`). 두 반박 모두 통과 여부가
   라이브 최신일 종가 커버리지에 달려 있다는 점은 인정했고, 앞의 것은 확정된 `test_healthy_payload_has_no_error` 와 단언이
   같다(`candidate_sector_count >= 20`). 기준을 한쪽으로만 적용하지 않으려고 4건 모두 고정 종가로 바꿨다(§4-9 표). 나머지
   229건의 분류(LIVE_STRUCTURAL · INDEPENDENT)는 에이전트 판정이며 반박 검증은 EXACT 후보에만 돌렸다.
5. **자체 적대 리뷰를 두 번 돌렸다.** 1차(작업 1~5 · commit 전): 확정 5건 수정(1차 결과서 §6 에 기록). 2차(71d50d15 전):
   확정 3건 — ① 가드를 끈 역검증에서 sqlite 탐침이 라이브 DB 에 테이블을 남김 → 쓰기 전에 연결 경로부터 확인 ② 세션 사본이
   쓰기를 조용히 흡수(사고 패턴이 통과 · 테스트끼리 데이터 샘) → 사본을 읽기 전용으로 ③ ①과 같은 지적(P3). 기각 4건 중
   값싼 보강 4개를 넣었다(§4).
6. 평가일 수 계약은 **목록 완전 일치**다. "개수는 같고 날짜만 다른" 경우도 막는다
   (`test_evaluation_window_rejects_same_count_different_dates`).
7. KRX 토요일(2026-09-19) 응답도 행 1,171개가 왔다 — 기준일자·종목코드·종목명·상장주식수·기초지수명만 있고 나머지
   필드는 빈 문자열. `krx_sync.has_traded_prices` docstring 의 "주말은 행 자체가 없다" 와 다르다(운영 코드 무변경).
8. **사전 점검에서 바꾼 테스트 인프라 동작 2가지 — 새 실패가 생길 수 있는 변경이다.** ① 가드가 막은 연산을 앱 코드가
   삼켜도 그 테스트를 실패시킨다(전에는 통과) ② conftest 의 three_push 상태 파일 감시는 바뀐 파일을 되돌려 쓰지 않고 실패만
   시킨다(전에는 되돌린 뒤 실패 · POC3-OPS-01A r3 부터의 동작). ②는 이 프로세스의 쓰기를 가드가 먼저 막으므로 하위 프로세스·
   다른 운영 프로세스의 쓰기에서만 오고, 되돌려 쓰면 진짜 운영 쓰기를 지울 수 있어서다. 전체 회귀에서 이 두 변경으로 새로
   실패한 기존 테스트는 0건이다(§4-7).
9. **AC-8 테스트가 잡는 것** — 사본에서 운영 코드를 일부러 바꿔 돌렸다: NAV 요약을 두 번 씀 → `2 == 1` 실패 · 다른 JSON 1개를
   더 씀 → "NAV 요약 1개 외 JSON" 실패 · NAV 요약 쓰기를 뺌 → `0 == 1` 실패 · 원래 코드 → 통과(사본 코드는 원래대로 되돌림).
   사전 점검 뒤 추가 실측(복제본 · 29839c75 코드): NAV 요약을 쓰는 try 안에서 라이브 경로 `state/market/market_topn_latest.json` 을 씀(옛 JSON 모양 ·
   예외는 앱이 삼킴) → teardown ERROR("가드가 라이브 경로·사본 연산을 막았다 … io.open mode=w") · 파일 생김 0. tmp_path ·
   라이브 state/·logs/ 밖 다른 폴더(예: 저장소 data/ · 시스템 tmp)에 쓰는 JSON 은 이 테스트가 보지 못한다(§5).
10. **관찰 (범위 밖 · 수정 안 함 · 실행 확인 안 함)** — 격리한 NAV 요약은 1,175종목 · `cache_hit true` 다. 캐시는 프로세스 메모리
   (`app/naver_etf_universe_fetcher.py::_UNIVERSE_CACHE`)라, 사고 pytest 실행 안에서 먼저 누군가 실제 규모의 스냅샷을 채웠다는
   뜻이다 — 스텁 없는 Naver 실제 조회가 테스트 중에 있었을 가능성이 있다. 사전 점검에서 코드를 읽어 보니
   `tests/test_market_topn_api.py::test_post_refresh_accepted_and_runs_inline_for_test` 와
   `tests/test_market_refresh_state_persistence.py` 의 갱신 테스트가 `fetch_universe_snapshot` 을 대체하지 않아 기본 경로
   (`urllib.request.urlopen(NAVER_UNIVERSE_URL)`)로 갈 수 있다. 네트워크 금지라 실행으로는 확인하지 않았다. 새 AC-8 테스트는
   스냅샷을 고정 fixture 로 넣어 외부 호출이 없다.
11. 문서 사실 주장은 commit 전에 에이전트로 실측 대조한다. 1차 문서(02a0f7c5)는 두 번 대조했다(1회차 7개 구역: 맞음
   315건·오류 19건 · 2회차 정정·사고 절 3개 구역: 맞음 131건·오류 4건). bdffdb4b 문서는 6개 구역을 대조했다(맞음 371건 ·
   확정 오류 17건 · 하위 폴더 테스트 추적 누락 1건 포함). 이번 문서(3차 판정 반영)는 3개 구역을 대조했다(맞음 254건 · 확정
   오류 8건 · 오류 지적 1건은 수정 전 줄 번호라 기각). 확정 오류는 전부 정정했고, 의심 항목은 근거를 확인해 문구를 좁혔다
   (§6-10 관찰 · §4-9 199건 성격 · 개수만 같은 다른 집합 · 감시 읽기 예외 등).

---

## 7) 사용자 확인이 필요한 항목

- **push** — 설계자 지시대로 검증자 `VERIFIED` 뒤 로컬 commit 전부(`be579619` · `02a0f7c5` · `71d50d15` · `bdffdb4b` ·
  `2d6547b3` · `abf833ee` · `29839c75` · 최종 문서 commit — 8개)를 한꺼번에 push 한다. 지금은 모두 로컬에만 있다.
- **§6-3 설계자 확인 완료** — 기존 테스트 목록 229건 · 감시 읽기 예외 2건 승인. 다음은 검증자 제한 재검증이다.
- **사전 점검 뒤 가드 보강은 사용자 결정으로 진행했다**(2026-09-24 "테스트 코드 보강 후 검증자") — 설계자 확인 뒤에 생긴
  commit(`29839c75`)이라 검증 범위가 7개에서 8개로 늘었다. 설계자에게는 검증 전달문과 함께 알린다(§4-13 · §6-8).
- **남은 테스트 흔적** — 과거 실행 기록 156개 · 공유 로그 2개는 그대로다(§4-8). NAV 요약은 격리 사본으로 보존했고
  다음 정상 NAV 갱신이 새로 만든다. `market_refresh_state` 는 다음 정상 시장 데이터 갱신이 다시 쓴다.
- **KRX Open API 호출** — 2026-09-23 KST 탐침 7회(PLAN §2-2 · 연구 DB 미기록) + canary 20회 + 전체 적재 3,319회 =
  하루 3,346회(연구 DB 기록 3,339 · 공식 한도 10,000 · 자체 상한 5,000). 받은 데이터는 PC 연구 DB 에만 있다.
- **연구 DB 용량** — `state/ml/research/krx_etf_universe.sqlite` 약 1.86GB(원응답 본문 보관 계약) · 맥북 로컬만.

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

**기준 1 — 실제 데이터로 두 번 실행** (코드 commit 마다 두 번씩 · 여섯 실행 모두 `official = true`)

```text
코드       실행   canonical sha256                                                  E2 핵심 hash   평가일  시간
be579619  run1   e1c02f6657d2d88836dbf254f2beaf2f89aa42f405b077d2e599791f97454000  (기록 없음)     146    794.8s
be579619  run2   e1c02f6657d2d88836dbf254f2beaf2f89aa42f405b077d2e599791f97454000  (기록 없음)     146    810.1s
71d50d15  run3   2a6ca8c6ef554942c7b80c45d6c888bce6a0d060da4f5a47fc8c6619bb3728bb  e1c02f66…      146   1030.8s
71d50d15  run4   2a6ca8c6ef554942c7b80c45d6c888bce6a0d060da4f5a47fc8c6619bb3728bb  e1c02f66…      146    966.5s
2d6547b3  run5   066ba09af85ed334acaef3a35df80a924bd2bb926bc7e9480172b8b33fb05aec  e1c02f66…      146    940.7s
2d6547b3  run6   066ba09af85ed334acaef3a35df80a924bd2bb926bc7e9480172b8b33fb05aec  e1c02f66…      146   1005.0s
compare   run1↔run2 · run3↔run4 · run5↔run6  identical = true (상태·dataset·manifest 내용·cutoff·commit·모듈 hash·평가일·canonical)
```

시간 = run_manifest `elapsed_seconds`(`time.perf_counter` — macOS 절전 중에는 멈춘다). run3 는 실행 중 시스템 절전이 끼어
`started_at`→`finished_at` 벽시계로는 1,976.7초다. run1·run2·run4·run5·run6 은 두 값이 거의 같다(795.1 · 810.4 · 966.8 ·
940.9 · 1,005.3초).

**E2 무변경 증명** — run3·run4 의 `e2_core_canonical_sha256`(결과에서 새 `strategy_performance` 블록만 뺀 canonical)이
`e1c02f6657d2d88836dbf254f2beaf2f89aa42f405b077d2e599791f97454000` 으로 **run1·run2 의 canonical 과 같다**. 작업 6·격리
수정·산출물 보호가 E2 평가·판정·기록을 한 글자도 바꾸지 않았다. canonical 이 바뀐 것은 성과 블록이 더해졌기 때문이다.

**산식 문구 정정 뒤 재실행 (설계자 3차 §4 · `2d6547b3`)** — run5·run6 결과 JSON 을 run3 과 필드 단위로 전부 비교했다.

```text
run5 ↔ run6   다른 필드 = generated_at · e1.elapsed_seconds 뿐 (기존 계약 NON_DETERMINISTIC_FIELDS)
run3 ↔ run5   다른 필드 = strategy_performance.formulas.active_return (정정한 문구)
                        · determinism.canonical_sha256 (그 문구가 canonical 에 들어가서)
                        · generated_at · e1.elapsed_seconds
E2 핵심 hash  run5 = run6 = e1c02f6657d2d88836dbf254f2beaf2f89aa42f405b077d2e599791f97454000 (run3·run4 기록값 · run1·run2 canonical 과 같음)
전략 결과     strategy_performance 에서 formulas 를 뺀 나머지 run3 = run5 = run6 — 산식·설명 외 변화 0
```

결과 파일 sha256 은 `generated_at` 와 `e1.elapsed_seconds` 때문에 실행마다 다르다(run1 `52e08ddc…` · run2 `046448f5…` ·
run3 `43905694…` · run4 `2e828f07…` · run5 `6f07095c…` · run6 `37b0d8f3…`) — canonical 은 이 두 필드를 뺀다(기존 계약 `NON_DETERMINISTIC_FIELDS`).

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
호출 합계   2026-09-23 KST 하루 3,346회 (탐침 7 · 연구 DB 미기록 + canary 20 + 전체 3,319) — 자체 상한 5,000 · 공식 10,000 이하
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
black --check · flake8 · py_compile   2d6547b3·abf833ee·29839c75 의 변경 py 8개 통과 (71d50d15 의 변경 py 14개도 그때 통과)
pytest (전체 · 저장소)   2013 passed (3분 19초 · 29839c75) · 세션 종료 검사 변경 0 · 세션 끝 사본 재확인 같음 ·
                         라이브 5곳 전후 동일(§4-9) = 1,997 + 산식 문구 1 + 가드 5(abf833ee) + 가드 10(29839c75) ·
                         AC-8 은 1건 교체 · 고정 입력 4건은 기존 테스트 수정 · 사전 점검 뒤 바꾼 테스트 인프라로 새로 실패한 기존 테스트 0
                         (abf833ee 에서는 2003 passed · 3분 04초)
pytest (전체 · 사본)     기록 모드 2009 passed · 4 skipped · 목록 비운 실측 229건 전부 실패(29839c75 코드 · §4-13)
pytest (재현 명령 8개 파일)  153 passed (29839c75) · 라이브 5곳 전후 동일
KS-10                    abf833ee·29839c75 는 테스트뿐 — 테스트 파일 최대 test_intraday_config_integration 1,423줄(임계 1,500 ·
                         근접 1,450 미만) · 가드 도우미 tests/_live_guard.py 684줄(tests/ 안 테스트 도우미라 테스트 기준 1,500
                         미만 — 백엔드 핵심 모듈 기준 650 이었다면 초과다 · 검증자 판단에 맡긴다) · app/ 변경은 2d6547b3 의 문구뿐(ml_strategy_performance.py 257줄 · docstring 1곳 ·
                         formulas 문자열 1곳 · +4/−2). 71d50d15 때 전수 TRIGGER 0 · NEAR 7
```

(이전 1961 passed 전체 회귀가 §4-8 사고를 냈다. 이번 회귀는 가드가 걸린 상태다.)

재현 명령:

```text
python scripts/ml_baseline_tool.py verify --manifest state/ml/baselines/relative_upside_v1_snap_20260921/dataset_manifest.json
python scripts/ml_baseline_tool.py compare state/ml/baselines/relative_upside_v1_snap_20260921/runs/run5/run_manifest.json state/ml/baselines/relative_upside_v1_snap_20260921/runs/run6/run_manifest.json
python -m pytest tests/test_ml_baseline_snapshot.py tests/test_ml_research_krx_universe.py tests/test_ml_score_validity_cli.py tests/test_ml_score_validity_contracts.py tests/test_ml_backtest_metrics.py tests/test_ml_backtest_embargo.py tests/test_live_state_guard.py tests/test_market_topn_api.py -q
```

(스냅샷·결과 파일은 PC 로컬이라 다른 기계에서는 `verify`·`compare` 를 재현할 수 없다. dataset_manifest 와 run1·run2
run_manifest 는 02a0f7c5 로, run3·run4 는 bdffdb4b 로, run5·run6 run_manifest 는 이 결과서와 같은 최종 문서 commit 으로 git 에 들어간다.)

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
- (수정 전) `tests/test_api_holdings_market_evidence.py:40` 이 인자 없이 불렀다(호출은 2026-06-03 `e1e5b886` 부터 · 이 함수가 기본값 라이브 경로로 DB 행을
  지우게 된 것은 2026-06-30 `ccbdadd0` 부터) →
  라이브 DB 의 `market_refresh_state` 행을 지운다. 사본에 행 1개를 넣고 이 파일만 돌리면 0행이 되고 DB hash 가
  바뀐다(`515098f5…` → `51879f53…`).
- 테스트 파일 125개(최상위 106 · 하위 폴더 19)를 사본에서 하나씩 돌려 쓰기 주체를 찾았다. 최상위는 격리 수정 전 사본,
  하위 폴더는 `be579619` 코드로 새로 만든 사본에서 돌렸다(처음에는 최상위만 돌렸다 — 최종 문서 대조에서 누락을 찾아 보충):

| 라이브 경로 | 쓰기 | 테스트 파일 |
|---|---|---|
| `state/market/market_data.sqlite` | `market_refresh_state` 행 삭제 | `test_api_holdings_market_evidence.py` |
| `state/market/nav_discount_refresh_latest.json` | 테스트 값으로 덮어씀 | `test_market_refresh_state_persistence.py` · `test_market_topn_api.py` |
| `state/runs/run_*.json` | 새 파일 1개 | `test_poc1_loop.py` |
| `logs/oci_market_data_batch.log` | 줄 추가 | `test_market_benchmark_freshness.py` · `test_oci_market_data_refresh.py` |
| `logs/three_push_runtime_cron.log` | 줄 추가 | `test_holdings_risk_alert_runner.py` · `test_intraday_alert_flow_through.py` · `test_market_briefing_flow_through.py` · `test_oci_market_data_refresh.py` · `test_runtime_runner_dry_run.py` · `test_runtime_runner_partial_delivery.py` · `test_runtime_runner_spike_no_signal.py` · 하위 폴더 `low_frequency_push/test_kind_flag_guard.py` · `low_frequency_push/test_runner_fail_closed.py` · `low_frequency_push/test_selection_state_isolation.py` · `runtime_evidence/test_runtime_runner_forwarding.py` · `universe_bootstrap/test_runtime_universe.py` |

`state/runs/` 에 2026-09-21 자 같은 흔적 파일이 이미 있어, **이전 작업들의 전체 pytest 때도 반복돼 온 기존
결함**으로 보인다. `tests/conftest.py` 의 `_detect_live_market_db_write` 는 `market_benchmark_daily_price`
테이블만 감시해서 이 경로들을 잡지 못한다.

**기준선에 영향 없음**

- 스냅샷이 복사한 3개 테이블(`etf_master` · `etf_daily_price` · `market_refresh_log`)은 삭제된 테이블이 아니다.
  행 수는 pytest 전 측정(1,183 · 1,405,608 · 645)과 스냅샷이 같다.
- pytest **전**(21:43)에 라이브 DB 로 돌린 재현 시도와 pytest **뒤** 스냅샷으로 돌린 run1 의 기준일 148개
  (warmup 2 포함) 로그 값(IC · 표본 수 · 커버리지)이 **전부 같다**. 종목 1,183 · 거래일 3,055 · E1 재현 1,157 도 같다.

**흔적 증거 (2026-09-24 삭제 전 기록)**

```text
경로                                              크기 B       mtime (KST)          sha256
state/runs/run_20260923T135127_2dd2891c.json          184  2026-09-23 22:51:27  ab93efad7b3b31a7831257059ed5b2618e513bfc4d254f65719489b3e8d768c5
state/market/nav_discount_refresh_latest.json         536  2026-09-23 22:50:29  9b38489a47949007233688f9f87748a32bfab6954f275cee78cd1dc439f52518
logs/oci_market_data_batch.log                    272,145  2026-09-23 22:51:27  df0b29f5da9c3fb7e44dd067a9b4233120dc2d75fa7b094e4a37acbb900c04a1
logs/three_push_runtime_cron.log               13,330,611  2026-09-23 22:52:38  add4a1e738644435f52d027dc06c0de339ffdce83b1107d77983780d763d167e
state/market/market_data.sqlite               419,737,600  2026-09-23 22:49:53  db0b2e9cf626d1af610e23a1bd15d07c49fa272807712ce3cfe24bc64c8592d4
```

- **실행 기록 1개가 테스트 단독 생성인 근거** — 생성 시각 13:51:27Z 가 전체 pytest 실행 구간(13:49:47Z ~
  13:52:38Z · 마지막 테스트 로그 줄) 안이다. 앱 서버는 21:31 KST 에 종료됐고(`/tmp/krx_backend.log` 끝이 shutdown), 그 뒤 서버 프로세스가
  없었으며, 그 로그에 `/runs/generate` 요청이 0건이다. 사본에서 테스트를 하나씩 돌리면
  `test_poc1_loop.py::test_ac8_terminal_states_block_reuse` 가 같은 모양의 파일(`FAILED` · payload·message·push_kind
  모두 null · 184 B)을 만든다. 파일 하나에 기록 하나라 다른 실행 기록과 섞이지 않는다.
- **나머지 실행 기록 156개**(2026-08-12 ~ 09-21)도 모양이 전부 같지만, 앱 화면도 `/runs/generate` 를 부를 수
  있어 파일마다 테스트 출처를 증명하지 못했다 → **지우지 않는다.**
- **NAV 요약 파일**은 테스트가 **덮어쓴** 라이브 산출물이다(단독 생성 아님) → 지우지 않고, 설계자 3차 판정대로
  **활성 경로 밖 이름으로 격리 보존**했다(아래 (d)).
- **로그 2개**는 공유 로그다(사고 실행이 붙인 줄 — three_push 479줄: 22:49:50~53 70줄 + 22:50~22:52:38 409줄 · oci 배치
  20줄). 파일 전체를 지우지 않는다.

**처리 (설계자 판정 2차 (a)+(b)+(c) · 3차 (d))**

```text
(a) market_refresh_state 1행   그대로 둔다 — 가짜 값 복원·억지 갱신 없음. 다음 정상 갱신이 다시 쓴다
(b) 테스트 단독 생성 파일       state/runs/run_20260923T135127_2dd2891c.json 1개만 삭제
(c) 테스트 격리                 §4-9 (필수 · 차단 결함)
(d) NAV 요약                    활성 경로 밖 이름으로 옮겨 보존 — 삭제·수동 편집·값 합성 없음. 다음 정상 NAV 갱신이 새로 만든다
유지                            과거 실행 기록 156개 · 공유 로그 2개
```

OCI 와 PUSH 는 영향이 없다(맥북 로컬 파일만). `market_refresh_state` 행은 복원하지 않았다.

**(d) NAV 요약 격리 기록** (2026-09-24 실측)

```text
원래 경로     state/market/nav_discount_refresh_latest.json            → 지금 없음(활성 경로 비움)
격리 경로     state/market/nav_discount_refresh_latest.json.quarantine-test-20260923T135028Z
              같은 폴더 안 이름 변경 · 2026-09-24 10:35:27 KST(파일 ctime) · gitignore `state/market/*.quarantine-*`
크기 · mtime  536 B · 2026-09-23 22:50:29 KST — 이름 변경 전후 같음
sha256        9b38489a47949007233688f9f87748a32bfab6954f275cee78cd1dc439f52518 — 위 흔적 증거 표와 같음
내용          source naver_etf_item_list · asof 2024-10-31 · status ok · fetched_at 2026-09-23T13:50:28Z ·
              total 1,175 · success 1,175 · upserted 1,175 · cache_hit true · elapsed 0.004s
```

테스트 값인 근거 — ① asof `2024-10-31` 은 테스트가 넣는 고정 날짜다(`test_market_refresh_state_persistence.py:74·321`
`end_date_for_prices=date(2024, 10, 31)` · `test_market_topn_api.py` 도 같은 날짜) ② fetched_at 13:50:28Z 가 사고 pytest 실행
구간(13:49:47Z ~ 13:52:38Z) 안이다 ③ 테스트 파일을 하나씩 돌린 실측에서 이 경로에 쓴 파일이 그 두 개다(위 표).

### 4-9. 테스트 격리 — 차단 결함 수정 (설계자 (c))

**설계** — 경로를 하나씩 막으면 새 경로가 생길 때 또 뚫린다. 그래서 쓰기 연산 자체에 건다(`tests/_live_guard.py`).
conftest 가 **app 모듈 import 전에** 설치하고 pytest 종료 때 푼다.

```text
파일 쓰기      open/io.open/_io.open(w·a·x·+) · os.open(과 원본 posix.open · 쓰기 플래그) · os.replace/rename ·
              os.remove/unlink/rmdir · os.mkdir(없는 경로) · os.truncate · os.chmod · os.utime · os.symlink(만드는 쪽) ·
              os.link(원본·만드는 쪽 — 라이브 파일의 하드링크도 라이브 파일이다)
              → 대상이 라이브 state/·logs/ 아래면 즉시 LiveStateWriteError (dir_fd 상대 경로도 실제 폴더로 풀어 판정)
경로 판정      file: URI 를 SQLite 처럼 푼다(//localhost · %XX · ?query) · 심볼릭 링크를 먼저 따라간 뒤 비교 · 문자열로
              안 맞으면 가장 가까운 실제 조상의 (장치, inode) 를 라이브 루트와 비교 — 대소문자만 다른 경로 · macOS
              firmlink(/System/Volumes/Data/…) 도 라이브로 본다. unlink·rename 처럼 링크 자체만 바꾸는 연산은 마지막
              링크를 따라가지 않는다(tmp 의 링크를 지우는 것은 라이브를 건드리지 않는다)
sqlite        라이브 DB 경로로 오는 연결(sqlite3.connect · sqlite3.dbapi2.connect · _sqlite3.connect) → 세션 임시
              사본을 mode=ro 로 연다. 읽기는 그대로 · 쓰기는 즉시 "attempt to write a readonly database" · 가드는
              라이브 파일을 세션 첫 연결 때 사본을 만들 때만 읽고(복사 전·후 sha256 + shutil.copyfile) sqlite 로는 열지 않음
SQL 안 파일    가드를 거친 모든 연결(sqlite3.Connection(...) 직접 생성은 제외 · §5)에 authorizer + trace callback —
              ATTACH '<경로>' · VACUUM INTO 는 라이브·사본이면 준비·실행 때 거부(파일을 열지 않는다). ATTACH ?(매개변수)·
              식은 준비 때 경로를 모르므로 실행 직전 값이 채워진 SQL(앞 SQL 주석은 걷어낸다)을 trace 가 본다 — 대상이
              문자열 하나면(매개변수는 이렇게 채워진다) 라이브·사본일 때만 막고, 그 밖의 식('a' || 'b' 포함)은 판정
              불가로 보아 tmp 대상이어도 막는다. 막으면 그 별칭의 모든 접근을 거부하고 막은 기록을 남긴다
사본 검사      복사 전 라이브 sha256 → 복사 → 복사 후 라이브 sha256 → 사본 sha256. 복사 중 라이브가 바뀌거나 사본이
              다르면 즉시 실패 · 사본에 PRAGMA integrity_check (ok 가 아니면 실패)
사본 보호      검증을 통과한 사본은 0444 · 사본 경로로 직접 열기(목록 밖) · 쓰기 · 권한 변경 · 삭제도 라이브와 똑같이
              막는다 · 세션 끝에 사본 sha256 을 다시 재 비교 — 다르거나 사본 검사가 실패했으면 세션 실패.
              pytest 끝 [live-db-copy] 줄: 복사 전·후 · 사본 · integrity · 세션 끝 사본(같음/다름)
허용 목록      tests/_live_db_legacy_readers.txt 의 기존 테스트만 사본을 연다. 목록 밖 테스트가 라이브 DB 를 열면 즉시
              LiveStateWriteError("새 테스트는 자체 임시 DB·고정 fixture 를 쓴다 …") · 목록은 줄이기만 한다 —
              자동 검사는 개수 상한(tests/test_live_state_guard.py::LEGACY_READERS_CEILING = 229) · id 형식 ·
              정렬·중복 0 뿐이라 항목을 바꿔치기하면 테스트가 잡지 못한다(목록 파일 diff 로만 보인다)
삼킨 오류      가드가 막은 연산은 모두 기록한다. 앱 코드가 except Exception 으로 가드 오류를 삼켜도 conftest 가 그
              테스트를 실패시킨다(teardown ERROR) — 가드 자체 테스트(test_live_state_guard.py)만 뺀다
부수 출력      NAV 요약 · 러너 로그 폴더를 tmp_path/_side_outputs 로 (호출 시점에 읽는 모듈 상수)
세션 전후      감시 파일 4곳 sha256 + state/runs 파일 목록 + state/·logs/ 전체 (크기·mtime) — 바뀌면 [live-state] ·
              종료코드 실패
감시 fixture   _detect_live_market_db_write 는 real_connect 로 **실제 파일**을 mode=ro 로 본다 · three_push 상태 파일
              6개는 테스트마다 전후 바이트를 비교해 바뀌면 실패만 시킨다(되돌려 쓰지 않는다 — 아래 §4-13)
```

**원인 수정** — `tests/test_poc1_loop.py::test_ac8_terminal_states_block_reuse` 의 `monkeypatch.undo()` 가 conftest 의
격리 패치(store 경로 · OCI stub 등)까지 전부 풀었다 → 구간 `monkeypatch.context()` 로. `tests/test_api_holdings_market_evidence.py:40`(수정 전 줄)
의 `reset_state_for_testing()` → `reset_state_for_testing(db_path=fake_db)`.

**가드를 켜자 드러난 것** (사본 전체 실행 · `test_api_holdings_market_evidence` 인자 수정은 이미 적용 · test_ac8 수정과 세션
사본 도입 전) — 실패 96건 / 22개 파일. 93건이 운영 조회 함수가 라이브 시장 DB 를 **읽으려고** rw 로 연 것(`sqlite3.connect (rw)`),
나머지 3건은 `state/runs` 쓰기(test_ac8) · AC-8 NAV JSON 격리 경로 · 진단 helper 호출 집합 불일치(가드 언급 없음 — 이후 실행에서
통과)였다. 사고를 낸 `market_refresh_state` 삭제는 이 실행 전에 이미 고쳐 96건에 없다. 읽기 전용 세션 사본 도입 뒤 전체 1,997 passed.

**기존 테스트 수 정정 — 93건이 아니라 233건** (설계자 3차 판정 "기존 93건에만 호환 경로" 의 전제)

위 93건은 가드 첫 버전에서 **rw 연결이 막혀 실패한** 수다. 그 버전은 `mode=ro` URI 열기를 라이브 파일에 그대로
허용했다 — 예: `app/intraday_config/selector.py::latest_closes` 는 `file:…?mode=ro` 로 연다(첫 버전 코드는 남아 있지 않고,
실패 표시가 `sqlite3.connect (rw)` 뿐이며 intraday_config 테스트 실패가 0건인 기록과 맞는다). 그래서 라이브 DB 를 읽기
전용으로 여는 테스트와, rw 로 열었지만 오류를 코드가 삼켜 통과한 테스트가 세지지 않았다. 개발자가 2차 보고에서 이 93 을
라이브 DB 를 읽는 테스트 수처럼 전했고, 설계자 판정의 93 은 그 수치다. 기록 모드(`KRX_LIVE_DB_READERS_RECORD=<파일>`)로 전체 회귀를 돌려 전수 측정했다.

```text
세션 사본을 연 기존 테스트        233건 (전체 회귀 1,997 passed · 사본 2개: 시장 DB · decision_evidence DB)
목록을 비우고 전체 회귀(233건 기준)  199건 실패 · 34건 통과
고정 종가로 바꿔 목록에서 뺀 것      4건(모두 199건 쪽) → 목록 229건
```

199건 실패는 "라이브 DB 연결이 막혀서" 다 — 라이브 데이터가 있어야 하는 것만은 아니다. 아래 분류로 보면 199건 =
LIVE_STRUCTURAL 93 · INDEPENDENT 102 · EXACT 4 이고, INDEPENDENT 102건 중 101건은 분류 근거에 "스키마만 있는 빈 DB
(0행)로도 통과" 가 적혀 있다(에이전트 근거 · 전부 재실측하지는 않았다) — 연결 성공만 필요한 테스트다. 목록에는 POC4-01
(71d50d15)에서 만든 가드 역검증 테스트 2건(`test_live_sqlite_opens_a_read_only_session_copy[False·True]`)도 들어 있다 — 세션
사본 자체를 확인하는 테스트라 사본이 필요하다. 3차 판정 시점에 있던 테스트라 "기존" 에 넣었다.

34건도 목록에 둔다 — 이 테스트들은 라이브 DB 를 연다. 위 측정 당시에는 목록에서 빼도 앱 코드가 가드 오류를 삼켜
통과했지만(원래 확인하던 경로가 바뀐 채), 지금은 삼킨 가드 오류도 테스트를 실패시키므로(위 설계 "삼킨 오류") 빼면
실패한다. 목록 밖의 기존·새 테스트가 라이브 DB 를 열면 연결은 즉시 거부되고 테스트는 실패한다
(`test_test_outside_legacy_list_cannot_open_live_db` · 삼킨 경우는 §4-13 사본 실측).

**정확한 값 단언 전수 분류** (설계자 "정확한 데이터값을 계약으로 단언하는 테스트에는 session copy 사용 금지")

233건을 에이전트로 테스트마다 분류했다(근거 = 파일:줄 · 사본 측정). 1차 분류: 흐름에 라이브 데이터가 필요하지만 단언은
구조·상태(LIVE_STRUCTURAL) 93 · 라이브 값과 무관(INDEPENDENT) 136 · 라이브 값에 기대는 단언(EXACT_LIVE_VALUE) 4.
(이 93·136 은 위 "rw 실패 93건" · §6-3 "229 − 93 = 136건" 과 **개수만 같은 다른 집합**이다 — rw 실패 93건과 LIVE_STRUCTURAL
93건이 겹치는 것은 1건.)
EXACT 4건은 테스트마다 반박 검증 에이전트 1개를 따로 돌려 2건 확정 · 2건 반박됐다. 넷 다 같은 모양이라 **4건 모두** 고정 입력으로 바꿨다:

| 테스트 | 라이브에 기대던 단언 | 반박 검증 |
|---|---|---|
| `test_intraday_config_integration.py::test_healthy_payload_has_no_error` | 사업군 수 `>= 20` — 최신일 종가가 있는 사업군만 셈 | 확정 |
| `test_intraday_config_integration.py::test_unpriced_candidate_cannot_be_representative` | `sector_no_market_cap` 0건 — 27개 사업군 중 5개는 종가 있는 후보가 1개뿐 | 확정 |
| `test_intraday_config_integration.py::test_api_shows_candidate_after_generation` | 위 첫째와 **같은 단언**(`>= 20`) | 반박 — 상한 27 은 고정 CSV·토큰 사전이 정하고, 종가·날짜를 바꿔도 수가 같다(부등식 단언) |
| `test_intraday_config_contracts.py::test_unmatched_index_is_recorded_not_dropped` | 제외 사유가 `unclassified` 뿐 — 반도체 후보 전원 종가가 있어야 성립 | 반박 — 비교값(`unclassified`)이 코드 상수 |

반박된 2건도 통과 여부가 **라이브 최신일 종가 커버리지**에 달려 있다는 점은 확정 2건과 같다(반박 근거도 이 의존을
인정한다). 같은 단언을 한 곳은 사본, 한 곳은 고정 입력으로 두지 않으려고 넷 다 바꿨다. 방법: `selector.latest_closes` 를
고정 종가(git 고정 CSV 전 종목 10,000원 · 기준일 2026-09-11)로 대체 — 후보는 git 고정 CSV 에서, 사업군은 토큰 사전에서
나온다(integration 3건은 git 의 사전 · contracts 1건은 테스트 안 사전 `{"반도체": ["반도체"]}`). `test_unpriced_candidate_cannot_be_representative` 는 대체가 있는 사업군의 1위 종목에서 종가를 빼, 뺀 종목이 대표로
남지 않는지도 본다. 목록을 비운 사본 실행에서 4건 passed · 대조군(`test_selection_basis_records_the_actual_value`, 목록에
남은 테스트)은 "새 테스트는 자체 임시 DB" 로 실패 — 4건이 라이브 DB 를 열지 않음을 확인했다.

**역검증 — 71d50d15 시점 기록** (저장소 사본 · 대상 3파일: `test_poc1_loop` · `test_api_holdings_market_evidence` ·
`test_live_state_guard` 14건). 지금 가드 테스트는 29건(abf833ee 19건 → 29839c75 29건)이고, `test_api_holdings_market_evidence` 가 목록 밖이라 원인
수정을 되돌리면 `readonly database` 가 아니라 목록 검사("새 테스트는 자체 임시 DB")에서 먼저 실패한다 — 이 표는 다시 돌리지
않았다. 지금 가드 테스트의 가드 유무 검사는 아래 문단.

| 조건 | 라이브 DB | 실행 기록 | 결과 |
|---|---|---|---|
| 가드 끔 + 원인 수정 되돌림 | 바뀜(`market_refresh_state` 1→0) | +1 | `[live-state]` 4항목 · 가드 테스트 12건 실패 · 종료코드 1 · **탐침 테이블 증가 0** |
| 가드 켬 + 원인 수정 되돌림 | 그대로 | 그대로 | 사고 패턴이 `readonly database` 로 즉시 실패(5건) · test_ac8 은 `LiveStateWriteError` · 종료코드 1 |
| 가드 켬 + 원인 수정 | 그대로 | 그대로 | 37 passed · 종료코드 0 |

**저장소 전체 회귀 — 라이브 5곳 sha256** (29839c75 · 2026-09-24 19:17:55 → 19:21:17 KST · 2,013 passed)

```text
state/market/market_data.sqlite                db0b2e9cf626d1af610e23a1bd15d07c49fa272807712ce3cfe24bc64c8592d4  전후 동일
state/market/nav_discount_refresh_latest.json  (없음 — §4-8 (d) 격리 뒤)                                          전후 없음
logs/oci_market_data_batch.log                 df0b29f5da9c3fb7e44dd067a9b4233120dc2d75fa7b094e4a37acbb900c04a1  전후 동일
logs/three_push_runtime_cron.log               add4a1e738644435f52d027dc06c0de339ffdce83b1107d77983780d763d167e  전후 동일
state/runs (파일 목록 156개)                    efe6f3609317dad99441a822f42bf53dc666a375c4b23a5b782114763ae230b5  전후 동일
NAV 요약 격리 사본                               9b38489a47949007233688f9f87748a32bfab6954f275cee78cd1dc439f52518  전후 동일
[live-db-copy]  market_data.sqlite       복사 전 db0b2e9c… = 복사 후 = 사본 · integrity ok · 2.17s · 세션 끝 사본 같음
                decision_evidence.sqlite 복사 전 1f446da6… = 복사 후 = 사본 · integrity ok · 0.0s · 세션 끝 사본 같음
```

(abf833ee 회귀 — 11:31:05 → 11:34:12 KST · 2,003 passed — 와 71d50d15 회귀 — 02:38:53 → 02:41:56 KST · 1,997 passed — 도 같은
hash 로 전후 동일이었다. 71d50d15 때는 NAV 요약이 활성 경로에 `9b38489a…` 로 있었다.)

역검증 테스트(`tests/test_live_state_guard.py` 29건) 중 22건은 가드가 빠지면 실패한다(사본 복제본에서 conftest 의 가드 설치를
빼고 실측 — 22 failed · 7 passed · 복제본 라이브 루트에 남은 탐침 0 · 복제본 시장 DB sha256 그대로). 통과한 7건은 가드 유무와 무관한 것들이다: 확인용 2건(읽기·tmp 쓰기 허용 · 감시 5곳 목록) ·
목록 상한·정렬 1건 · 사본 검사 4건(검사 함수 `verified_copy`·`recheck_copies` 를 tmp DB 로 직접 불러 hash 일치 · 복사 중 원본
변경 · 손상 DB · 세션 끝 재확인을 본다). 탐침 경로는 라이브 루트 아래 **없는 이름**만
쓰고, sqlite 탐침(`test_live_sqlite_opens_a_read_only_session_copy`)은 **쓰기 전에** 연결 경로부터 확인한다. 목록 밖 테스트는 라이브 경로에 연결만 하고 닫는다(쓰기 없음) —
가드가 망가져도 라이브 데이터를 바꾸지 않는다.

### 4-10. 작업 6 — purge·embargo · 거래비용 · 성과지표 (설계자 2차 판정 §3)

**purge·embargo** — `app/ml_research_split.py` · 테스트 `tests/test_ml_backtest_embargo.py` 11건

```text
make_selection_folds   표본 끝의 연속 n 개 validation 구간 · walk-forward(학습은 validation 앞만) 또는
                       blocked(validation 뒤도 학습 · embargo 적용) · label 미완성 표본은 제외
assert_fold_contract   학습 표본마다 날짜로 검사 — label 종료일(asof 뒤 20거래일) ≥ validation 시작이면 purge 위반 ·
                       validation 안이면 위반 · validation 종료 뒤 20거래일 이내면 embargo 위반
split_fingerprint      분할 전체 sha256 · require_same_split: 설정 최대 3개 · 모두 같은 분할이 아니면 실패
검사 결과              마지막 학습일 label 이 validation 전날 끝남(필요한 만큼만 뺌) · purge 20일 · embargo 20일 ·
                       purge/embargo/validation 날짜를 한 줄 넣으면 실패 · 19일로 만든 분할은 20일 계약에서 실패
```

E2 평가 · 고정 모듈(`app/ml_relative_upside_model.py`)은 바꾸지 않았다 — §4-4 E2 핵심 hash 로 확인.

**거래비용 · 성과지표** — `app/ml_strategy_performance.py` · 테스트 `tests/test_ml_backtest_metrics.py` 7건(손계산 대조)

```text
전략     모델 점수 상위 10% 동일가중 (A2 와 같은 바스켓) · 월말 신호 · 다음 거래일 진입 · 다음 월말 다음 거래일 청산
수익률   전략 = 상위 10% 초과수익 평균 + 같은 기간 KODEX200 수익률 (= ETF 원수익률 평균 · forward_excess 정의)
비용     그 달 실측 교체비율 × 편도 × 2 · 첫 달 0 (A2 규칙) · 편도 = 수수료 1.5(ASSUMPTION) + 슬리피지 + 거래세 0
산식     절대 equity Π(1+순수익) · benchmark Π(1+KODEX200) · relative = 두 equity 의 비율 ·
         active(순수익 − KODEX200)는 relative 에 복리 누적하지 않고 추적오차·정보비율·월평균 active 에만 · Sharpe_0rf · 연율화 = 기간 수 / (달력일/365.25)
```

**새 기준선 실측** (run3 · 146기간 · 2014-07-01 ~ 2026-09-01 · 4,445일 · 연 11.997기간 · 제외 기간 0 · run5·run6 도 formulas 밖 값이 같다 — §4-4)

| 시나리오 | 편도 | 전략 end | CAGR | MDD | 변동성 | Sharpe_0rf | 상대 wealth | 상대 MDD | active/월 | 추적오차 | IR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| legacy all-in (비교) | 25.0 | 1.0329 | 0.27% | −37.96% | 18.02% | 0.105 | 0.1987 | −83.65% | −1.225% | 19.09% | −0.770 |
| 분해 · 슬리피지 5 | 6.5 | 1.6085 | 3.98% | −33.07% | 18.03% | 0.307 | 0.3095 | −75.42% | −0.922% | 19.08% | −0.580 |
| **분해 · 슬리피지 10 (기본)** | **11.5** | **1.4272** | **2.97%** | **−33.89%** | **18.02%** | **0.253** | **0.2746** | **−77.98%** | **−1.004%** | **19.08%** | **−0.631** |
| 분해 · 슬리피지 25 | 26.5 | 0.9964 | −0.03% | −38.45% | 18.02% | 0.089 | 0.1917 | −84.18% | −1.250% | 19.10% | −0.785 |
| 분해 · 슬리피지 50 (스트레스) | 51.5 | 0.5463 | −4.85% | −58.77% | 18.03% | −0.184 | 0.1051 | −90.90% | −1.660% | 19.12% | −1.042 |

같은 기간 KODEX200 benchmark: end 5.1978 · CAGR 14.50% · MDD −32.20%. legacy 25bp 시나리오의 월평균 active −1.225% 는 기존 A2
순수익 평균(−0.012253)과 같다 — 같은 바스켓·같은 비용 규칙이라는 교차 확인이다. 판정은 그대로 `REJECT` 다. 이 수치는 생존편향이
남은 universe 기준이다(`UNBIASED_PERFORMANCE = NOT_YET`).

### 4-11. 산출물 보호 — 검증자 P1

`app/ml_baseline_snapshot.py::new_run_dir` 를 러너가 가장 먼저 부른다.

```text
거부   state/ml/validity 자체 · 그 하위 모든 폴더(보존 사본 poc4_01_frozen_original 포함) ·
       대소문자·firmlink 같은 별칭 경로(있는 조상을 samefile 로 비교) · 이미 있는 폴더
허용   존재하지 않는 새 폴더만 — 러너가 만든다
정리   아무것도 쓰지 못하고 끝난 실행은 그 빈 폴더를 지운다(러너가 방금 만든 폴더만)
```

검증자가 재현한 두 경우를 테스트로 막았다.

```text
test_runner_refuses_any_folder_under_legacy_result_dir   하위 폴더 2종 거부 · 거부 전에 폴더를 만들지 않음
test_cli_refuses_existing_out_dir_and_leaves_its_files_untouched
                                                         SENTINEL 결과·meta 가 있는 폴더 → 거부 · 두 파일 그대로 ·
                                                         다른 파일 생기지 않음
test_failed_run_leaves_no_empty_out_dir                   cutoff 불일치로 실패 → out-dir 가 남지 않음
test_new_run_dir_refuses_alias_paths_into_forbidden_root  대소문자 별칭 거부(대소문자 구분 없는 파일시스템)
```

예전 "차단 시 이전 결과 제거" 테스트(`test_cli_removes_stale_validity_latest_when_blocked`)는 전제(같은 폴더 재사용)가 계약에서
사라져 위 기존 폴더 거부 테스트로 바꿨다. 러너의 차단 경로에 있던 "이전 결과 파일 삭제" 코드도 새 폴더에서는 실행될 수 없어
뺐다. 이 수정으로 러너 코드 hash 가 바뀌어 기준선을 run3·run4 로 다시 돌렸다(§4-4).

### 4-12. AC-8 — 시장 갱신의 JSON 산출물 (설계자 3차 판정 `MARKET_REFRESH_NAV_JSON = REQUIRED`)

`tests/test_market_topn_api.py::test_post_refresh_json_artifact_is_exactly_the_nav_summary` 가 예전
`test_post_refresh_does_not_create_json_artifact`("JSON 을 하나도 만들지 않는다")를 대체한다. 예전 단언은 2026-06-08 NAV 요약이
생긴 뒤로 운영 동작과 반대였고, 통과한 것은 관찰 폴더 밖에 써졌기 때문이다 — 71d50d15 전에는 라이브 폴더,
71d50d15 뒤로는 conftest 격리 하위 폴더(`tmp_path/_side_outputs` · 예전 테스트는 시장 DB 폴더만 `iterdir` 로 봤다).

```text
계약        LEGACY_MARKET_JSON_ARTIFACTS = 0 · NAV_SUMMARY_JSON = 지정 경로 1개 · OTHER_MARKET_JSON_ARTIFACTS = 0
지정 경로    market_refresh_service.NAV_REFRESH_SUMMARY_PATH — conftest 가 tmp_path/_side_outputs 로 격리 · 라이브 경로와 다름을 단언
NAV 입력     고정 fixture — fetch_universe_snapshot 을 3종목 스냅샷(069500 ok · 379800 ok · 999999 unavailable)으로 대체 · 외부 호출 0
단언        NAV 요약 쓰기 호출 정확히 1회 · 갱신 뒤 tmp_path 전체(시장 DB 폴더 포함)에 새로 생긴 JSON = {지정 경로} 뿐 ·
            키 = NavUniverseRefreshSummary 필드 전체 · source naver_etf_item_list · asof 2024-10-31 · status ok · fetched_at ·
            집계 total 3 · success 2 · unavailable 1 · failed 0 · ignored 0 · upserted 3 · sample_tickers [069500, 379800] ·
            cache_hit·stale_cache_used false · 라이브 NAV 경로 바이트 전후 같음(지금은 파일 없음 → 없음 그대로)
운영 코드    무변경 — NAV JSON 쓰기(app/market_refresh_service.py::_write_nav_refresh_summary) 유지
```

### 4-13. 사전 점검 — 검증자 제한 재검증 항목 1~8 선검증과 보강 (사용자 결정 2026-09-24)

설계자가 검증자에게 준 체크리스트 1~9 중 1~8 을 개발자가 먼저 돌렸다. 에이전트 5개가 항목별로 저장소 사본의 **자기 복제본**
에서만 테스트를 돌렸고(저장소·라이브 파일은 읽기만), 지적 27건 중 info 가 아닌 19건(high 1 · medium 9 · low 9)은 건마다 반박
검증 에이전트 1개가 따로 재현했다(19건 모두 사실 · info 8건은 반박 검증 없음). 9번(저장소 전체 회귀)은 개발자가 직접
돌렸다(§4-7). 보강 뒤 결과서 대조(에이전트 3개 · 지적 21건 모두 반박 검증에서 사실)에서 가드 구멍 2건이 더 나와 같이
막았다(아래 표 마지막 두 줄).

**통과** — 1 233 − 기록 모드 재현 = 고정 입력 4건(다만 목록 밖 거부 확인 테스트가 기록 모드에서도 라이브를 열어 230건 ·
1 실패로 나왔다 → 아래 처리) · 2 정렬·중복 0 · 모든 id 가 현재 수집에 있음 · 3 사본 hash·integrity · 6 AC-8 기본 계약 ·
7 격리 NAV 파일을 읽는 코드·동기화 경로 0 · 8 run5 = run6 · E2 핵심 hash · 필드 diff.

**보강 뒤 기록 모드 재현** (저장소 사본 · 29839c75 코드 · `KRX_LIVE_DB_READERS_RECORD`) — 기록된 사본 사용 테스트 229건 =
목록 229건(양쪽 차이 0) · 2,009 passed · 4 skipped(기록 모드에서 건너뛰는 가드 테스트 4건).

**반박 검증을 거쳐 확정된 문제 → 처리** (사용자가 "테스트 코드 보강 후 검증자" 를 골랐다 · 운영 코드·기준선 무변경)

| 문제 | 처리 |
|---|---|
| `ATTACH`·`VACUUM INTO` 로 라이브 DB 에 쓰기 가능 — 읽기 전용 사본 연결에서도(붙인 DB 는 mode=ro 를 물려받지 않는다) | 가드를 거친 모든 연결(`sqlite3.connect`·`dbapi2`·`_sqlite3`)에 authorizer + trace callback (§4-9 "SQL 안 파일" · `sqlite3.Connection(...)` 직접 생성은 제외 §5) |
| 세션 사본을 경로로 직접 열면 쓰기 가능 · 세션 끝 재확인 없이 만들 때 hash 만 다시 찍음 | 사본 0444 · 사본 경로도 라이브처럼 보호 · 세션 끝 sha256 재측정 |
| 경로 별칭으로 우회 — 대소문자 · firmlink · `file://localhost` · `%XX` · 링크 뒤 `..` · 하드링크 | 경로 판정 보강 (§4-9 "경로 판정") · 하드링크는 만드는 순간 막음(`os.link` 원본도 검사 — 세션 전부터 있던 하드링크는 경로 판정이 알아보지 못한다 §5) |
| `sqlite3.dbapi2.connect`·`_sqlite3.connect`·`_io.open`·`posix.open` 미가드 | 함께 가드 |
| 목록 밖 테스트의 라이브 DB 연결 · 라이브 경로 JSON 쓰기를 앱 코드가 `except Exception` 으로 삼키면 테스트 통과 | 막은 연산을 기록 → 삼켜도 그 테스트 실패 (§4-9 "삼킨 오류") |
| conftest `_restore_and_fail` 이 가드를 끄고 라이브 three_push 상태 파일을 되돌려 씀 — 승인된 "읽기 전용 감시" 밖의 쓰기 | 실패만 시키고 되돌리지 않음 · 전후 크기·sha256 을 실패 메시지에 남김 |
| 가드 자체 테스트의 `_cleanup` 이 `suspended()` 로 가드를 끈 채 라이브 루트 아래 탐침을 지운다 | 그대로 둠 — `__live_guard_probe_<uuid>` 이름 탐침이 실제로 있을 때(가드가 뚫렸을 때)만 그 탐침 하나를 지운다 · 이제 `suspended()` 를 쓰는 곳은 여기 하나뿐 |
| 기록 모드로 재현하면 230건 · 1 실패(목록 밖 거부를 확인하는 테스트가 일부러 라이브를 연다) | 기록 모드에서 그 테스트들은 skip → 229 |
| 결과서가 코드보다 넓게 말함 — 목록 밖 테스트 "실패" · 라이브 직접 읽기 "2곳" · 가드 테스트의 `real_connect` rw 사용 | 코드 보강으로 "실패" 성립 · 읽기 목록 공개(§5) · `_small_db` 는 `sqlite3.connect` |
| 설계자 전달문의 검증 범위 끝 커밋 `57784ab3` 은 amend 로 없어졌다 | 사용자 전달문에서 범위 정정 |
| (결과서 대조) `'a' \|\| 'b'` 처럼 따옴표로 시작·끝나는 식 ATTACH 를 문자열 하나로 잘못 읽어 라이브 대상도 통과 | 대상 전체가 문자열 하나일 때만 문자열로 본다 — 그 밖은 판정 불가로 막는다 |
| (결과서 대조) 앞에 SQL 주석이 붙은 `ATTACH ?` 는 판정을 건너뜀 · `posix.*` 직접 호출 · `os.chown`·`mkfifo` 등 목록 밖 os 함수 | 앞 주석을 걷어내고 판정 · os 쓰기 함수는 원본 모듈(posix·nt)도 같이 가드 · 있는 메타데이터·특수 파일 함수 추가 (`test_os_module_originals_are_guarded`) |

가드 보강 중 개발자가 만든 버그 1건도 역검증에서 잡혔다 — 링크를 먼저 따라가는 판정이 pytest 가 tmp 의 링크(라이브를
가리키는)를 지우는 것까지 막았다. 링크 자체만 바꾸는 연산은 마지막 링크를 따라가지 않게 고치고 테스트를 더했다
(`test_removing_a_tmp_symlink_to_live_is_allowed`).

**삼킨 오류 실측** (복제본 · 29839c75 코드 · 임시 테스트 파일 · 확인 뒤 삭제) — 목록 밖 테스트가 ① 라이브 DB 연결 ② 앱 함수
(`generator._stored_trading_days`, 안에서 `except Exception`) ③ 라이브 경로 파일 쓰기 ④ `ATTACH ?` 로 라이브 DB 를 각각
`try/except` 로 삼키게 했다 → 4건 모두 teardown ERROR("가드가 라이브 경로·사본 연산을 막았다") · 대조 테스트 1건 통과 ·
라이브 경로에 생긴 파일 0 · 복제본 시장 DB sha256 그대로.

**목록을 비운 전체 회귀** (복제본 · 29839c75 코드) — 목록의 229건이 **전부** 실패(FAILED 또는 teardown ERROR) · 그 밖에는
목록 상한 테스트 1건만 실패(목록이 비어서) · 나머지 1,783건 통과. pytest 요약은 '196 failed, 1817 passed, 1 warning,
227 errors' 다 — 1,817 에는 본문은 통과하고 teardown ERROR 로 실패한 목록 34건이 함께 세어진다. 그 34건은 예전 측정
(233건 기준 199 실패 · 34 통과)에서 통과했던 34건과 같은 테스트다 — 삼킨 가드 오류가 이제 테스트를 실패시킨다. 실행 뒤
복제본 라이브 루트에 남은 탐침 0.

