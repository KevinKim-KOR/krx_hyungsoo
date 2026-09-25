# POC4-02B — 위험 구간 조기감지 기준선 RESULT

```text
TRACK_B_VERDICT      = REJECT   (설계자 판정 §7 조건 1~11 · 거짓 1·5·6·7·8·9·10 · 결과를 본 뒤 threshold 변경 없음)
DESIGNER_RESULT      = REJECT_ACCEPTED · RERUN = NO · EVENT_DEFINITION_STATUS = RETIRED_AFTER_THIS_STUDY (설계자 RESULT 판정 2026-09-25)
CRITERIA (PIT)       = 1 F · 2 T · 3 T · 4 T · 5 F · 6 F · 7 F · 8 F · 9 F · 10 F · 11 T
DETERMINISM          = 처음부터 두 번 실행 canonical 동일 4de43c0c… · 결과 파일 sha256 도 동일 67015d25…
LEGACY_REPRODUCTION  = EXACT_MATCH (운영 표 2개 읽기 전용 세션 사본 · 65개 값 · 차이 0 · 감사용)
SEALED_SOURCE        = krx_etf_universe_v1 SEALED · content c1a87776… · 실행 전후 동일 · 라이브 5경로 전후 동일
PRICE_BASIS          = KRX_BASEPRICE_CHAIN (FLUC_RT 기반 분배 중립 계열 · 관계 불일치 0행)
POST_HOC_NOTE        = 사건 창 정의 결함 1건 발견 — 세 가지 창 정의 모두 REJECT (판정 미사용 민감도 §4-8)
OCI · PUSH = 0 · EXTERNAL_CALLS = 0 · DEPENDENCY_ADDED = 0 · COMMIT · PUSH = 0 (설계자 판정 §13)
TRACK_B_PASS != PUSH_ACTIVATION
```

- **작성**: 개발자(VSCode Claude) · **독자**: 설계자(02B 먼저 판정 — 판정 §12) · 검증자(Codex, 설계자 통과 범위)
- **입력**: 설계서 `docs/ai_design/POC4/POC4-02_PARALLEL_RESEARCH_TRACKS_DESIGN_V2.md` 끝 `# 설계자 PLAN 판정`(2026-09-25) ·
  PLAN `docs/ai_plan/POC4/POC4-02B_DOWNSIDE_EARLY_WARNING_PLAN_V1.md`(§3~§11 확정 계약 · 구현 정의)
- **짝 결과서**: `docs/ai_result/POC4/POC4-02A_KRX_PIT_UNIVERSE_BIAS_RESULT.md` — 문서 동기화(§1-1)·공용 reader(§1-2 · §4-1)·공용 파일 목록(§2)은
  이 문서에만 적고 02A 결과서는 참조한다.
- **실행 폴더**(git 추적 밖 `state/ml/research/`): `state/ml/research/poc4_02b/run1` · `run2` · `run2/determinism_compare.json` ·
  사후 민감도 `state/ml/research/poc4_02b/post_hoc_window_sensitivity/`
- **코드 상태**: 실행은 커밋 전 코드로 했다(판정 §13 `COMMIT = 0`). manifest 에 `code_clean=false` · HEAD `94cec4e2` · 미커밋 파일
  11개와 모듈 hash(정규화 AST)를 기록했다. 실행 뒤 코드 변경 0(§4-9 hash).

---

## 1) 처리한 요구사항

### 1-1. 문서 동기화 (판정 §11 · 구현 순서 1)

| 요구 | 상태 | 근거 |
|---|---|---|
| 설계서 기록 | DONE | 설계서 끝에 판정 원문을 그대로 붙임(이 세션 대화 기록의 사용자 붙여넣기와 difflib 대조 차이 0줄) · 머리 안내에 "V2 본문과 충돌하는 곳은 판정이 우선한다" |
| PLAN 02A·02B 동기화 | DONE | 질문 목록 → 확정 표 + 구현 정의(결과 전 고정) · 머리 상태 `PASS_WITH_MANDATORY_AMENDMENTS` |
| Master Plan | DONE | §11 상태 · 판정 순서 · V1 기록 문장 표시 |
| `PROJECT_ORIGIN_INTENT §9.5` | DONE | 기존 문장 유지 + 2026-09-25 예외(판정 원문 그대로) |
| `ASSUMPTIONS Q6` | DONE | `RESEARCH_CONTRACT = FIXED_FOR_POC4_02B` · `OPERATIONAL_CONTRACT = OPEN` |
| 중복 문구 정리 | DONE | 02A "옛 행으로 점수 매겼다"(E2 기준선 사실)는 §2-4·5 한 곳 · `reproduce_scores_at` 동작은 §2-13 표 한 곳(아래 문단은 "위 표의" 로 참조) · 02A `progress/` 규칙은 §8 한 곳 · 02B §8 은 확정 표로 교체 |

### 1-2. 공용 reader (판정 §3 · 구현 순서 2)

| 요구 | 상태 | 근거 |
|---|---|---|
| `app/krx_sealed_reader.py` 하나 · 고정 fixture 테스트 먼저 | DONE | 테스트 12건 · 02A·02B 구현 전에 완성 · 두 트랙은 수정 없이 import(§4-1) |
| 봉인 DB 읽기 전용 · 전후 hash·integrity | DONE | `mode=ro&immutable=1` · 파일 sha256 · seal 재계산 · payload hash · row_count · quick/integrity check |
| `KRX_BASEPRICE_CHAIN` · 관계 검증 · 불일치 행 보정 금지 | DONE | 허용 오차 0.005%p(+1e-9) · 실제 1,612,728행 불일치 0 · 불일치 행은 연결 계열을 끊는다 |

### 1-3. 02B 확정 13건 · 판정 §4~§10

| # | 요구사항 | 상태 | 근거 |
|---|---|---|---|
| B1 | 주 사건 label = 분배 중립 계열 `dd10 ≤ −5%` | DONE | 기존 `_kodex_future_drawdown` 을 그대로 불러 연결 계열에 적용 · label 일 437 |
| B2 | 시점 기준 점수 | DONE | 축 percentile · 경보 기준 모두 t 이전 값만(검토자 end-to-end 확인: t 뒤 행을 바꿔도 EARLY_PIT · REACTIVE 의 t 점수·경보 불변 — 기록용 EARLY_FS 는 최종일 생존 정의상 바뀐다) |
| B3 | 결함 3개 교정(중복 축 · 방향 · 0~1 과거 percentile 정규화) · 새 factor 0 | DONE | EARLY 12축 · legacy 결과는 진단으로 나란히(§4-7) |
| B4 | FLUC_RT 기반 분배 중립 계열 | DONE | 공용 reader |
| B5 | 사건 시작 = 실현 고점일 P | DONE | 정의는 PLAN §5 — **결함 1건 발견**(§5 · §4-8) |
| B6 | 사전 창 W=10 · 간격 ≤ 9 병합 | DONE | 사건 36개(평가 35 · 잘림 1) |
| B7 | severe = 완결 사건 깊이 하위 25% | DONE | 9개 · 기준 깊이 −9.21% |
| B8 | 연도·사건 제외 안정성 | DONE | 사건 하나 빼기 35 · 연도 하나 빼기 11 · 2026 제외 1 |
| B9 | 시점 기준 누적 분위가 주 비교 · exact-k 는 참고 | DONE | 경보 = 과거 점수 66.67 분위 이상 · exact-k 는 `LOOKAHEAD=true` 진단 |
| B10 | universe 축 날짜별 이름으로 인버스·레버리지·합성·선물 제외 | DONE | PIT(주) · FS · 전 종목(legacy 진단만) |
| B11 | 운영 표 재현은 읽기 전용 동결 사본 진단만 | DONE | `EXACT_MATCH` · 라이브 DB 직접 연결 0 · 사본 삭제 |
| B12 | 잘린 사건 주 판정 제외 | DONE | 사건 36(2026-04-29~09-07) — 제외 창을 판정 §8 에 맞춰 관측 구간 전체로(§4 지시문 외 변경 1) |
| B13 | purge·embargo `NOT_APPLICABLE_TO_NO_FIT_RULE` | DONE | 결과 `purge_embargo` 필드 |
| §6 | RANDOM_NULL(연도별 run 구성 보존 원형 이동 · 1,000회 · 고정 seed) | DONE | seed 20260925 · 대체 0회 |
| §7 | PASS/REJECT 11개 조건 | DONE | §4-4 · 판정 REJECT |
| §10 | 운영 DB 재현 조건 6개 | DONE | §4-3 |
| §12-4·5 | 02A 장시간 실행과 동시에 돌리지 않음 · 처음부터 두 번 | DONE | 02B run1·run2 뒤 02A 시작 · compare `criterion_11 = true` |

### 1-4. 설계자 RESULT 판정 (2026-09-25) — 검증 전 문서 정정

| 요구 | 상태 | 근거 |
|---|---|---|
| 02B 머리말 `거짓 5·6·7 외` → `거짓 1·5·6·7·8·9·10` | DONE | 이 문서 머리말 `TRACK_B_VERDICT` |
| 02A 결과서 §5 번호를 1~7 순서로(내용 불변) | DONE | 02A 결과서 §5 — 7번 항목을 끝으로 옮김 |
| 조건 8 해석 기록(`CRITERION_8_PRIMARY` · `FS_SENSITIVITY` · `FS_RESULT`) | DONE | §4-4 |
| 코드·연구 실행 재실행 없음 | DONE | 실행 폴더·코드 변경 0 (모듈 hash §4-9 그대로) |

---

## 2) 변경된 파일 목록

아래 파일은 전부 스테이징 상태(신규 `A` · 수정 `M`)이며 커밋·push 는 없다(판정 §13 `COMMIT · PUSH = 0`). 보고 직전 작업 파일만
스테이징했다(§4-10) — 아래 사용자 소유 파일은 제외.

**작업과 무관(손대지 않음)**
- `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md`: 이 작업 전부터 있던 사용자 소유 미추적 파일 — 수정·스테이징 0

**공용(이 결과서가 대표로 적는다)**
- `app/krx_sealed_reader.py`: 신규 (362줄)
- `tests/_krx_fixture.py`: 신규 (167줄) · `tests/test_krx_sealed_reader.py`: 신규 (186줄)
- `docs/ai_design/POC4/POC4-02_PARALLEL_RESEARCH_TRACKS_DESIGN_V2.md`: 신규 (V2 기록 + 판정 원문)
- `docs/ai_plan/POC4/POC4-02A_KRX_PIT_UNIVERSE_BIAS_PLAN_V1.md` · `docs/ai_plan/POC4/POC4-02B_DOWNSIDE_EARLY_WARNING_PLAN_V1.md`: 신규
- `docs/ai_plan/POC4/POC4-00_ML_QUANT_ADVANCEMENT_MASTER_PLAN_V1.md` · `docs/PROJECT_ORIGIN_INTENT.md` · `docs/ASSUMPTIONS.md`: 수정

**02B**
- `app/ml_ew_reproduce.py` (166) · `app/ml_ew_market_axes.py` (285) · `app/ml_ew_signals.py` (220) · `app/ml_ew_events.py` (407) ·
  `app/ml_ew_report.py` (443) · `scripts/run_poc4_02b_early_warning.py` (538): 신규
- `tests/test_poc4_02b_axes.py` (186) · `_events.py` (357) · `_reproduce.py` (174) · `_runner.py` (338) · `_runner_guards.py` (263) ·
  `_signals.py` (213): 신규
- `docs/ai_result/POC4/POC4-02B_DOWNSIDE_EARLY_WARNING_RESULT.md`: 신규 (이 문서)

02A 파일은 짝 결과서 §2. 기존 운영 모듈·고정 모듈·기준선 파일 수정 0.

## 3) 신규 추가된 의존성

없음 (stdlib + 기존 torch).

## 4) 지시문 외 변경

1. **잘린 사건의 제외 창** — PLAN §5 처음 문구는 `[P−10, 구간 끝]` 이었다. 구현 검토에서 판정 §8("precision … 에서 전부 제외")보다
   좁다는 지적을 받아 관측 구간 전체 `[F−10, 구간 끝]` 으로 바꾸고 PLAN §5 문구도 고쳤다. **스모크 결과를 본 뒤 발견한 변경**이다 —
   판정 문구(결과 전 고정)에 맞춘 것이며 조건 1~7 의 참·거짓은 바뀌지 않는다 — 공식 run1 기록으로 다시 재면 EARLY run precision
   0.28035 → 0.28198 · REACTIVE 0.44295 → 0.44595 · 무작위 p95 0.3219 → 0.3256 (§4-8). 스모크 결과를 본 뒤 한 해석이며, 설계자 RESULT 판정 §2 가 승인했다(재실행 불필요 · §7-3).
2. **사후 민감도 스크립트**(git 추적 밖 `state/ml/research/poc4_02b/post_hoc_window_sensitivity/`) — 사건 창 결함(§5)이 결론을
   바꾸는지, 잘린 사건 창 변경 전후가 어떻게 다른지 설계자 판단용으로 쟀다. 판정에 쓰지 않는다(§4-8).
3. 구현 정의에 없던 세부 선택(검증자 참고 · 결과 전 코드에 고정): 경계 동점을 보간 오차 없이 넣으려고 분위값을 이웃 두 순서값
   사이로 고정(`bracketed_percentile`) · 판정 불가 경보(None)는 경보 아님 · 뺀 사건 창은 세 변형 모두 EXCLUDED · FS 조건 7 용
   무작위 기준은 같은 seed 로 따로 · legacy 진단 k = `max(1, int(n/3))`(기존 식).
4. **설계자 RESULT 판정 기록**(지정된 정정 2곳 외) — 판정 원문을 설계서 끝 `# 설계자 RESULT 판정` 에 그대로 붙이고, 판정으로
   해소된 "결정 필요 · 판정 대기 · 확인 요청" 문구를 판정 결과로 바꿨다(결과서 두 개의 머리말·§5·§7 · PLAN 02B §4-1·§5 ·
   Master Plan §11). 판정과 문서가 어긋나지 않게 하려는 것이며 수치·결론은 바꾸지 않았다.

## 5) 알려진 한계 / 미완성

1. **사건 정의 결함(설계자 판정: 재실행 없음 · 이 정의는 이번 연구 뒤 폐기 `RETIRED_AFTER_THIS_STUDY`)** — PLAN §5 의 `T = [F, Last+10] 최저 · P = [F, T] 최고` 는 강한 상승장에서 길게 병합된
   사건에 맞지 않는다. 사건 34(2025-10-22~11-17 · label 19일)·35(2026-01-19~03-27 · label 42일)는 T 가 F 바로 다음 날로 잡혀
   깊이가 −1.06% · −0.82% 이고 창이 자기 label 일을 거의 덮지 못한다. 전체 label 일 437 중 58일이 어느 창에도 들지 않는다
   (2026-03-03 −7.88% · 03-04 −12.46% 급락일도 label 일인데 창 밖) → 그 구간 경보 run 은 다른 사건 창과 겹치지 않으면 FALSE 로
   세어진다. **공식 판정은 사전 정의로 냈고**, 창 정의
   두 가지를 바꿔 다시 재도 REJECT 는 그대로다(§4-8).
2. **사건 수가 적다** — 평가 사건 35개 · severe 9개. 2026 은 잘림 사건 1개(사건 36 · 깊이 −40.81%)와 결함 사건 35 뿐이다.
3. **run 단위 지표가 경보 모양에 민감하다** — EARLY 는 경보가 자주 켜졌다 꺼져 run 이 356개(REACTIVE 155개)다. 일 단위 precision 은
   0.379 대 0.362 로 비슷하지만 run precision 은 0.282 대 0.446 이다. 판정 §7 이 run 단위를 정했으므로 그대로 판정했다.
4. KRX 축은 운영 보고서와 숫자가 다르다(가격 기준 · universe · NAV 괴리 정의) — 운영 숫자 재현은 감사 단계에서만 했다.
5. 결과·실행 폴더는 git 추적 밖이다. 결과서의 hash 로 대조한다.

## 6) 다음 검증자(Codex)에게 알릴 점

- 판정 기준값(label · 병합 간격 · W · 경보 분위 · severe · seed — 설정 hash `a9775c4e…` 가 스모크와 공식 실행에서 같음)은 사전 정의
  그대로다. 사건 창 계산 중 잘린 사건 제외 창(§4 지시문 외 변경 1)만 스모크 결과를 본 뒤 바뀌었고, 판정 문구에 맞춘 것이며 조건
  값은 불변이다.
- 조건 8 은 "주 평가가 PIT 이므로 1~7(PIT) 그대로"로 구현했다(구현 정의 7) — 설계자 RESULT 판정 §3 이 이 해석을 승인했다
  (`CRITERION_8_PRIMARY` · `FS_SENSITIVITY` · `FS_RESULT` 기록은 §4-4). FS 에서도 5·6·7 거짓.
- 러너 재개는 엄격하다: 첫 시작 뒤 라이브 5경로가 바뀌면 그 폴더는 재개·compare 모두 거부(`guard_failed.json`). 결과는 라이브 대조
  통과 뒤에만 쓴다. 모든 출력은 임시 파일 → fsync → `os.link` 로 덮어쓰기 없이 게시.
- 구현 뒤 두 관점 검토(계약 대조 · 정확성/안전)의 지적 7건: 5건은 코드로 고쳤다(재개로 라이브 가드 우회 — 두 검토자가 같은 결함을 따로 지적 · 네트워크 0·다른 DB
  연결 거부 테스트 없음 · 비공식 실행에 판정 기록 · 쓰다 끊긴 반쪽 기록) · 1건(잘린 사건 창)은 판정 §8 에 맞췄다(§4 지시문 외
  변경 1) · 1건(사건 정의)은 설계자 결정 사항으로 남겼다(§5-1). 검토자 두 명이 스모크 결과를 독립 재계산해 3,122일 점수·경보 ·
  사건 36개 · 신호별 지표 · 변형 47개의 핵심 값이 차이 0 이었다(잘린 사건 창 변경 전 코드·스모크 기준 — 변경 뒤 공식 실행 지표는
  독립 재계산하지 않았다 · 변경 전후 차이는 §4-8 에 공식 run1 로 다시 쟀다).
- 운영 표 재현은 `evaluate_risk_baseline` 이 set 을 순회해 합산한다 — 비트 일치는 Python 3.12(저장소 .venv 3.12.13)에서 확인했고,
  3.9 에서는 9개 키가 시드마다 마지막 비트에서 달라진다(PLAN §2-6).

## 7) 사용자 확인이 필요한 항목

없음 — 아래 네 항목은 설계자 RESULT 판정(2026-09-25 · 설계서 끝 `# 설계자 RESULT 판정`)으로 결정됐다.

1. **사건 창 정의(§5-1)** — 재실행 없음(`POC4_02B_RERUN = NO`). 공식 결과는 사전 등록 정의에 따른 REJECT 이고, 이 사건 정의는
   향후 연구에 재사용하지 않는다(`EVENT_DEFINITION_STATUS = RETIRED_AFTER_THIS_STUDY`). Track B 재시도는 새 PLAN·새 사전 등록이
   있는 별도 연구로만 가능하다. 사후 민감도(§4-8)는 공식 판정을 대체하지 않는 진단으로만 남긴다.
2. **커밋 범위** — 검증자 `VERIFIED` 전에는 커밋·push 0. 통과 뒤 staged 29개를 함께 커밋·push 한다(사용자 소유 handoff · git 밖
   사후 진단 파일 제외).
3. **잘린 사건 제외 창(§4 지시문 외 변경 1)** — `[F−10, 관측 종료일]` 승인 · 공식 실행 재실행 불필요.
4. **조건 8 해석** — 승인 · 해석 기록은 §4-4.

---

## 4. 증거

### 4-1. 공용 reader · 봉인 source

```text
verify_sealed_source (run1 전후 · run2 전후 모두 동일)
  file_sha256   fe3022e98d861beb70ead529c7efc678f5197eb20a754af48541f221656dacf2 · 1,862,836,224 B
  content       c1a877762b9b1f296365801030641c86bc4508f4c2643f1a6793e39119f9bb4c · SEALED · member 3,122일
  payload_hash_mismatch 0 · row_count_mismatch 0 · refetch_conflicts 0 · quick_check ok · integrity_check ok
load_panel      1,419종목 · 3,122일 · 1,612,728행 · 관계 불일치 0 · 무효 종가 0 · 끊긴 구간 0 · 최종일 1,171종목
                069500 연결 계열 2014-01-02 25,910 → 2026-09-21 141,696.8 (무조정 종가 111,700)
관계 검증       |CMPPREVDD/(TDD_CLSPRC−CMPPREVDD)×100 − FLUC_RT| 최대 0.005000000000000782 (허용 0.005 + 1e-9)
```

### 4-2. 달력 · 사건

```text
거래일 3,122 (2014-01-02 ~ 2026-09-21) · label 계산 가능 3,112일(끝 2026-09-07) · label 일 437
경보 판정 시작 D_0 = 2014-07-25 (EARLY 2014-07-01 · REACTIVE 2014-07-25) · 경보 평가 구간 2,973일 (~2026-09-07)
사건 36 = 평가 35 + RIGHT_CENSORED 1 (사전 창 없음 0) · severe 9 (깊이 ≤ −9.21%: 사건 5·7·11·19·21·22·26·28·33)
평가 사건의 P 연도: 2014 1 · 2015 3 · 2018 3 · 2019 2 · 2020 5 · 2021 4 · 2022 4 · 2023 3 · 2024 6 · 2025 3 · 2026 1
```

| 사건 | F ~ Last | P | T | 깊이 | 비고 |
|---|---|---|---|---|---|
| 11 | 2020-02-10 ~ 03-20 | 02-14 | 03-19 | −33.96% | severe · 평가 사건 중 가장 깊음 |
| 28 | 2024-07-11 ~ 08-02 | 07-11 | 08-05 | −16.48% | severe |
| 34 | 2025-10-22 ~ 11-17 | 10-22 | 10-23 | −1.06% | 정의 결함(§5-1) |
| 35 | 2026-01-19 ~ 03-27 | 01-19 | 01-20 | −0.82% | 정의 결함 · 두 신호 모두 미포착 |
| 36 | 2026-04-29 ~ 09-07 | 06-22 | 07-30 | −40.81% | RIGHT_CENSORED · 주 판정 제외 |

(전체 36개 표는 결과 파일 `events.table`)

### 4-3. 운영 표 재현 (감사 · B11 · 판정 §10)

```text
방법   라이브 state/market/market_data.sqlite 파일 복사(읽기만) → 전후 sha256 db0b2e9c… = 사본 db0b2e9c… · 사본 integrity ok · 0o444
       → guard_sqlite_paths([사본]) 안에서 build_risk_targets + evaluate_risk_baseline 무수정 호출
결과   EXACT_MATCH · 비교 값 65개 · 다른 키 0 · evaluated_days 2,998 = 저장 2,998
보호   사본 hash 불변 뒤 삭제 · 라이브 DB 연결 0 · ml_baseline_v0_report_latest.json sha256 a5435f4f… 전후 동일 · feature 표 쓰기 0
       라이브 5경로(conftest 감시 목록) 시작·전·후 동일 (run1 · run2)
```

### 4-4. 판정 (PIT · 설계자 판정 §7)

| # | 조건 | EARLY | REACTIVE | 값 |
|---|---|---|---|---|
| 1 | 포착 사건 전체 선행일 중앙값 EARLY > REACTIVE | 8.0 | 8.0 | 거짓 |
| 2 | 사전 capture EARLY ≥ REACTIVE | 28 | 22 | 참 |
| 3 | severe 완전 미포착 EARLY ≤ REACTIVE | 0 | 0 | 참 |
| 4 | 사전 포착 비율 EARLY > REACTIVE | 0.824 | 0.667 | 참 |
| 5 | 경보 run precision EARLY > REACTIVE | 0.2820 | 0.4459 | **거짓** |
| 6 | 경보 100건당 false-alarm run EARLY < REACTIVE | 23.59 | 8.06 | **거짓** |
| 7 | EARLY run precision > RANDOM_NULL 95% 분위 | 0.2820 | p95 0.3256 (평균 0.2962) | **거짓** |
| 8 | PIT 에서 1~7 성립 | | | 거짓 |
| 9 | 2026 제외 핵심 {1·2·5} | 1 거짓 · 2 참 · 5 거짓 | | 거짓 |
| 10 | 사건·연도 하나 빼기 핵심 | 변형 46개 모두 5 거짓(1 거짓 24개) | | 거짓 |
| 11 | 두 실행 canonical 동일 | 4de43c0c… = 4de43c0c… | | 참 |

→ `REJECT` (`determinism_compare.json` `final_verdict = REJECT` · `official_both = true`).

조건 8 해석 (설계자 RESULT 판정 §3):

```text
CRITERION_8_PRIMARY = PIT가 주 평가이므로 독립 조건이 아님
FS_SENSITIVITY      = 기록용 보조검사
FS_RESULT           = 조건 5·6·7 실패, REJECT 방향 동일
```

### 4-5. 신호별 지표 (경보 평가 구간 2,973일)

```text
                     경보일(비율)      사전/시작후/미포착  선행 중앙  run 참/거짓/제외  run prec  오경보run/100  일 prec
EARLY_PIT (주)       1,097 (36.9%)     28 / 6 / 1          8.0        97 / 247 / 12     0.2820    23.59          0.379
EARLY_FS (기록만)    1,095 (36.8%)     28 / 6 / 1          8.5        98 / 253 / 12     0.2792    24.21          0.383
REACTIVE             1,071 (36.0%)     22 / 11 / 2         8.0        66 /  82 /  7     0.4459     8.06          0.362
RANDOM_NULL(EARLY)   run precision p95 0.3256 · 평균 0.2962 · 1,000회 · 대체 0 (FS p95 0.3229)
```

EARLY 는 사전 포착이 더 많지만(28 대 22) 경보가 자주 끊겨 run 이 2.3배 많고, 그중 대부분이 사건 창 밖이다. run precision 은
무작위 기준 평균(0.296)보다도 낮다.

### 4-6. 변형 (조건 9·10)

```text
2026 제외        EARLY 선행 8.0 · 사전 28 · run prec 0.2878 / REACTIVE 8.0 · 22 · 0.4552 → 핵심 1 거짓 · 5 거짓
사건 하나 빼기   35개 모두 핵심 불성립 (5 거짓 35 · 1 거짓 18)
연도 하나 빼기   11개 모두 핵심 불성립 (5 거짓 11 · 1 거짓 6)
```

### 4-7. 진단 (판정 미사용 · LOOKAHEAD=true)

```text
EXACT_K (k=991 · 판정 §6 LOOKAHEAD_DIAGNOSTIC_ONLY)  EARLY 사전 26 · 선행 8.0 · run prec 0.3098 / REACTIVE 사전 21 · 선행 5.0 · run prec 0.4069
LEGACY_FULL_SAMPLE     기존 합성(결함 그대로 · 전 종목 · 전체 기간 순위 → 구간 안 상위 1/3 · k=991) 사전 26 · 선행 8.0 · run prec 0.2881 · 오경보run/100 27.20
universe 축 PIT − FS   평균 |차이| 하락 비율 0.0137 · breadth 0.0267 · 5일 중앙 수익률 0.0647%p · NAV 괴리 0.0100%p (3,117~3,121일)
```

결함을 고친 EARLY(PIT 경보 1,097일 · 0.282)와 결함 그대로의 legacy 합성(상위 1/3 · k=991 · 0.288)은 run precision 이 비슷하다.
같은 경보 수(k=991 · 둘 다 LOOKAHEAD)로 맞추면 EARLY 0.310 · legacy 0.288 로 EARLY 가 조금 높지만 사전 포착 26 · 선행 중앙 8.0 은
같고, 같은 k 의 REACTIVE(0.407)에는 둘 다 못 미친다 — 교정이 판정을 바꿀 만한 조기감지력을 만들지 않았다.

### 4-8. 사후 민감도 — 사건 창 정의 (판정 미사용 · 설계자 판단용)

스크립트 `state/ml/research/poc4_02b/post_hoc_window_sensitivity/ew_window_sensitivity.py`(sha256 `8ac11599…`) · 출력
`output_run1.json`(sha256 `8dbde8c8…`). run1 의 axes·signals·events 기록만 읽는다.

```text
정의                                   label 일 덮음   1  2  3  4  5  6  7   EARLY run prec  REACTIVE run prec  null p95
OFFICIAL (사전 정의)                    379/437        F  T  T  T  F  F  F   0.2820          0.4459             0.3256
ALT_A 창 끝 = max(T, Last)              437/437        T  T  T  T  F  F  F   0.3052          0.4797             0.3458
ALT_B label 기반 실현 고점·저점          410/437        F  T  T  T  F  F  F   0.2878          0.4257             0.3121
```

시험한 세 정의 모두에서 조건 5·6·7 이 거짓이다 → 사건 창 결함은 REJECT 결론을 바꾸지 않는다.

**잘린 사건 제외 창 변경 전후**(§4 지시문 외 변경 1) — 스크립트 `censored_window_before_after.py`(sha256 `22da97d8…`) · 출력
`censored_window_before_after_run1.json`(sha256 `3a9399a5…`) · 공식 run1 기록만 읽는다.

```text
잘린 사건 제외 창                 조건 1~7          EARLY run prec (참/거짓/제외)   REACTIVE run prec (참/거짓/제외)   null p95
변경 전 [P−10, 구간 끝]           F T T T F F F     0.28035 (97/249/10)             0.44295 (66/83/6)                  0.3219
변경 후 [F−10, 구간 끝] (공식)    F T T T F F F     0.28198 (97/247/12)             0.44595 (66/82/7)                  0.3256
```

### 4-9. 실행 · 결정성 · 코드

```text
run1  37.8초 · 최대 RSS 0.97 GB · resumed=false · canonical 4de43c0c27eaa932e4ecec447ce3cc53bb7021b9283a14174245c3055d7d645a
run2  38.2초 · 최대 RSS 0.96 GB · resumed=false · canonical 같음 · 결과 파일 sha256 67015d254e6e…2f81e0d 두 폴더 같음
compare  criterion_11 = true · official_both = true · final_verdict = REJECT

실행 당시 = 지금 모듈 sha256
  app/krx_sealed_reader.py              e43275ff…
  app/ml_ew_reproduce.py                712b632a…    app/ml_ew_market_axes.py   ae4f198d…
  app/ml_ew_signals.py                  78c5f5a8…    app/ml_ew_events.py        bf0a2c30…
  app/ml_ew_report.py                   54a94e31…    scripts/run_poc4_02b_early_warning.py  1606b334…
```

### 4-10. 자체 검수

```text
black --check (새 파일 21개)  21 files would be left unchanged
flake8                        출력 없음
py_compile                    통과
02B + 공용 테스트              86건 (reader 12 · 02B 74) — tmp 고정 DB 또는 DB 없는 순수 함수(events 23 · signals 15) · 봉인·라이브 DB
                              미접속 · 허용 목록 미추가
전체 회귀                      2,134 passed (0:04:13) · 라이브 DB 세션 사본 hash 전후 동일
KS-10                         새 파일 최대 586줄(02A 러너) — 전부 600 미만
git (보고 직전 실측)          `git status --short --untracked-files=all` — 작업 파일 29개 스테이징(A 26 · M 3) · 우측 열 수정 0 ·
                              `??` 는 사용자 소유 handoff 파일 1개뿐 · 커밋·push 0
```
