# POC6-05 개발 PLAN V1 — 지속 시장 자료 수집 · ML 연구 증거 보관 연결

작성 2026-10-22 · 작성자: 개발자(VSCode Claude) · 수신: 설계자

```text
STATUS   = PLAN 제출(2026-10-22) · 질문 4(§7) → 설계자 PASS_WITH_REQUIRED_CORRECTIONS(2026-10-22 · Q1 ~ Q4 모두 (a) · 필수 보완 반영 = §11 · 재제출 없음) → 격리 구현 · 독립 검토 반영 · 변이 47종 · 전체 회귀 4300 passed(2026-10-22) → 결과서 `docs/ai_result/POC6/POC6-05_CONTINUOUS_MARKET_DATA_AND_ML_EVIDENCE_RETENTION_RESULT.md` → 검증자 r1 REJECTED(2026-10-22 · P2 3건) → 정정(결과서 §4-3) → 검증자 r2 VERIFIED(2026-10-22 · 결과서 §12) → 설계자 RESULT PASS_TO_DEPLOY(2026-10-22 · 결과서 §13) → 실제 연결 확인(배포 8bda752f · 수집 3회 · 업로드 · 복원 · cron · 키움) → IMPLEMENTED_VERIFIED_DEPLOYED_CLOSED(2026-10-22 · 결과서 §14) · 첫 정기 실행 = 정기 운영 확인 대기
DECISION = docs/ai_design/POC6/POC6-05_CONTINUOUS_MARKET_DATA_AND_ML_EVIDENCE_RETENTION_PLAN_DECISION_2026-10-22.md
DESIGN   = docs/ai_design/POC6/POC6-05_CONTINUOUS_MARKET_DATA_AND_ML_EVIDENCE_RETENTION_DESIGN_V1.md
조사     = 저장소 읽기 + OCI 읽기 전용 확인(2026-10-22 11:23 ~ · ssh · crontab -l · DB mode=ro · 로그 읽기) · 외부 조회 0 · 쓰기 0
```

## 0. 한 줄

OCI 에 독립 CLI 하나와 cron 한 줄(09:40)을 둔다. 이 CLI 는 다음을 매일 보관한다.

- ETF 전체 목록과 네이버/FDR 120일 수신 창
- 이미 OCI 가 받은 KRX · 지수 행과 수집 기록
- 원/달러 · WTI · 코스피 수급

모두 증거 폴더(`state/ml/evidence/`)에 쓰기 전용으로 보관한다. OCI DB 에 새로 쓰는 것은 POC6-01 의 두 시장 흐름 표뿐이다.

PC 는 같은 구조의 사본을 SSH 로 가져와 확인 · 공개 · 복구 확인 · 기준 시각 export 를 한다. 02 · 03 · 04 공식 산출물은 바이트 그대로 등록해 OCI 에 한 부 더 둔다.

## 1. 지금 실제 상태 (§8-1 · §8-2 · 실측)

### 1-1. OCI 서버 (2026-10-22 11:23 KST)

| 항목 | 값 |
|---|---|
| 장비 | x86_64 · CPU 2 · 메모리 954MB(가용 약 530MB) · 디스크 45G 중 빈 39G · 시간대 Asia/Seoul |
| 실행 환경 | `venv/` Python 3.12.3 · FinanceDataReader 0.9.202 · pandas 2.3.3 · requests 2.34.2 · pykrx 1.2.8 · numpy 2.4.6 |
| 없는 것 | **torch · scikit-learn 미설치** · sqlite3 CLI 없음 |
| 있는 것 | `flock` · `gzip` · `rsync` |
| 코드 판 | `e525dc37`(POC6-01 종료 · 그 뒤 커밋 미반영) |
| 시장 DB | 139,337,728B · journal `delete` · `state/` 전체 268M |
| 키움 | OCI `.env` 에 `KIWOOM_APP_KEY` · `KIWOOM_APP_SECRET` 없음(줄 수만 셈) |
| 증거 폴더 | `state/ml/evidence` · `state/ml/research` 모두 없음 |

### 1-2. OCI 정기 작업 (crontab 13줄 · 2026-10-22 실제 소요)

| 시각(평일) | 작업 | 2026-10-22 실제 |
|---|---|---|
| 08:10 | 시장 배치 | 08:10:02 → 08:11:02(60초) |
| 08:30 | 시장 브리핑 | 약 2초 |
| 09:15 | 보유 브리핑 | 약 2초 |
| 09:20 | KRX 보강 `--krx-only` + 가격 결과 성숙 | 09:20:02 → 09:20:05(약 3초) |
| 09:30 | 보유 위험 알림 | 약 2초 |
| 10:30 | 보유 위험 알림 | 약 2초 |

그 밖에 11:30 · 12:30 · 13:30 · 14:30 · 15:20 보유 위험 알림, 12:30 · 15:40 보유 브리핑이 있다. 모두 `1-5`(평일)이다.

- **09:40 ~ 10:30 은 비어 있다.**
- OCI 작업에는 프로세스 잠금이 없다. 저장소 안의 프로세스 간 잠금은 `scripts/apply_three_push_param_oci.py :: _writer_lock`(fcntl.flock) 하나뿐이다.

### 1-3. OCI 시장 DB 의 실제 수집 범위 (mode=ro)

| 표 | 실측 | 누가 · 무엇을 |
|---|---|---|
| `etf_daily_price` | 1,149종 · 1,346,022행(2014-04-09 ~ 2026-10-21) | 08:10 배치가 **승인 seed ∪ 보유 41종만** 증분 갱신한다. 2026-09-15 이후 행은 41종뿐이다. 나머지는 과거 적재본에서 멈춰 있다. |
| `krx_etf_daily_price_unadjusted` | 1,191종 · 2026-08-13 ~ · **하루 1,183행(ETF 전체)** | 08:10 KRX `etf_bydd_trd` T-1. 저장 칸 = 종가 · collected_at뿐이다(나머지 18칸은 버림). 원응답은 보관하지 않는다. |
| `market_benchmark_daily_price` | KOSPI 3,072(2014-04-10 ~) · VIX 3,157 · US500 · IXIC · ^SOX 각 37 | 08:10 배치 |
| `etf_master` | 1,146행 · last_seen_at 2026-06-22 ~ 07-04 | **OCI 는 갱신하지 않는다(낡음)** |
| `market_macro_daily` · `market_investor_flow_daily` | **없음** | POC6-01 은 PC 갱신에서만 쓴다 |

**시각 칸의 뜻**: `fetched_at` · `collected_at` · `created_at` 은 덮어쓸 때마다 바뀐다. 즉 '처음 받은 시각'이 아니라 '마지막으로 쓴 시각'이다. 예외는 셋이다.

- VIX: 다른 값이 오면 덮어쓰지 않는다.
- KOSPI: 덮어쓰기 전에 `kospi_source_corrections/*.json` 에 이전 값을 남긴다.
- KRX: 값이 다르면 그 날짜를 지우고 다시 쓴다(`replace_date`).

**수집 기록 파일**:

- `state/market/oci_market_data_batch_state.json` · `oci_krx_reinforcement_state.json` — 매 실행 덮어씀
- `logs/oci_market_data_batch.log` — 이어 씀

**OCI 발송 경로의 의존**:

- 시장 브리핑 · 보유 브리핑 · 위험 알림 코드는 두 시장 흐름 표를 읽지 않는다. 그 표들을 읽는 곳은 PC API · 화면뿐이다.
- `etf_master` 를 읽는 곳도 PC API(종목명) · PC 연구뿐이다.

### 1-4. PC 전용 경로 (재사용 대상)

**ETF 가격**:

- 경로: `market_data_fdr._default_price_fetcher`
  - 내부적으로 FDR → 네이버 fchart 를 쓴다. `count=6000` 으로 전체 이력을 받은 뒤 120일로 자른다.
  - `change` 는 같은 응답의 종가로 계산한 값이다.
- 변환: `_dataframe_to_price_rows`
- 시간 초과 판별: `_is_request_timeout`
- 요청 상한: `fdr_request_timeout()`(20초 · 블록 안에서만 바꿔 끼움)
- 멈춤 규칙: 연속 시간 초과 5회 멈춤(`PRICE_TIMEOUT_STOP_STREAK`). 총 시간 상한은 없다.
- PC 실측: 1,192종 80.6 ~ 362.6초(중앙 약 139초 · 종목당 0.07 ~ 0.30초)

**수급 · 환율 · 유가(POC6-01)**:

- 함수: `supply_fx_oil_refresh.refresh_fx_wti` · `refresh_investor_flows`
  - 90일 겹침 · 20거래일 겹침 · 최신 날짜 먼저
  - 호출 400 · 180초 · 연속 3회 실패 · 호출 간격 0.25초
- 두 표 모두 `ON CONFLICT DO UPDATE` 로 덮어쓰므로 이전 값이 남지 않는다.
- 끼어들 자리:
  - FX: `fetch_completed_daily` 결과(L97-99) → upsert(L101) 사이
  - 수급: 날짜별 검증 통과(L166) → 반복 뒤 한 번 upsert(L184)
- 수급 대상 날짜는 '저장된 KOSPI 날짜'에서만 만든다. KOSPI 행이 없는 날은 시도도 실패 집계도 하지 않는다.

**ETF 목록**: `fdr.StockListing("ETF/KR")`(네이버 etfItemList 1회 · 0.7 ~ 1.6초). PC 2026-10-20 = 1,176종이다. 분류는 네이버 탭 코드이며 상장일 칸은 없다.

**거래일 축**:

- 운영 축 = `krx_trading_days_2026.csv`(있으면) · 없으면 평일 기본
- 연구 축 = 파일 ∩ KOSPI 저장일

## 2. 기존 연구 산출물 (§8-3 · 2026-10-22 다시 잼)

| 실험 | 폴더(`state/ml/research/…`) | 파일 · 바이트 | 행 단위 예측 · 정답 | 가중치 |
|---|---|---|---|---|
| 02 | `poc6_02/20261021T104103_129a89b0` | 12 · 6,533,850 | CPU `report.json → rows_by_block`(MEDIAN · RIDGE · HGB · truth) · GPU `gpu_result.json → blocks[].test_ids/pred` · 취합 `report_with_gpu.json`(네 방법) | 없음 |
| 03 | `poc6_03/20261021T161446_3403e974` | 4 · 3,910,772 | 없음(성과 계산 없는 단계) | — |
| 04 | `poc6_04/20261021T200645_c24b88ce` | 6 · 4,242,913 | **없음**(점수 · 판정만 · `a_report_frozen.json` = 02 report.json 같은 바이트) | 없음 |
| 합계 | — | 22 · 14,687,535(서로 다른 내용 21 · 14,422,251) | — | — |

**해시 대조**:

- 02 RESULT §8-7 · §15-2 의 5개, 04 RESULT §12-2 의 6개와 일치한다.
- 03 의 4개는 `app/d20_expand/inputs.py :: MANIFEST` 와 일치한다.
- 나머지(02 report.md · zip · gpu_bundle 5 파일)는 이번에 처음 기록한다(부록 A).

**recipe · 환경 위치**:

- 02: `report.json → recipe`(target · features · methods · blocks · verdict) · `recipe_resolved` · `environment` · `resources` · `input_digest` · `recipe_digest`
- 04: 02 recipe 를 `recipe_digest` 로 참조한다.

**가중치 파일**: `state/` 전체에서 *.pkl · *.joblib · *.pt · *.onnx 등 0건이다. 따라서 `trained_artifact=not_saved`(02 설계 '대형 모델 pickle 만들지 않음')로 기록한다.

**코드 커밋 연결**: 보고서에 commit 칸이 없고, 공식 실행은 모두 커밋 전에 만들어졌다.

- 시각: 02 CPU 10:41 · 03 16:14 · `6a6fa39e` 17:40 · 02 GPU 취합 20:00 · 04 20:06 · `fea10c38` 22:00
- 그래서 '코드가 처음 들어간 커밋' + 02 RESULT §6-11 '정정 코드 재계산 동일'로 연결한다.
- 02 GPU 코드만 `code_sha256` 으로 정확히 묶인다.

**복원 한계**:

- 03 `meta.snapshot_path` · 04 `manifest.json` 에 맥북 절대경로가 들어 있다. 다른 경로에 복원한 사본으로 기존 연구 코드를 다시 돌릴 수는 없다.
- 그래서 복구 확인은 해시 · 목록 · JSON 읽기로 한다. 파일은 고치지 않는다.

**03 의 의존**: 봉인 KRX 판 `state/ml/research/krx_etf_universe.sqlite`(1,862,836,224B · 계약 'OCI 미전송').

- 03 대조 보고서에는 KRX 원가격 행이 없다. KRX 에서 계산한 일간 배율 · 대조 집계만 있다.

**06 · 08(설계 §5 '할 수 있다')**:

- `poc5_06` 2파일 614,543B — **평단 · 수량 · 실현손익 · 계좌 그룹 칸이 있다**.
- `poc5_08` 2파일 1,946,859B — 수량 · 평단은 없다. 보유 표시(`held`)와 사용자 평가 1건이 있다. 가장 최근 폴더를 PC 화면이 읽는다.

## 3. 일일 규모 추정 (§8-4 · 부하 시험 없음)

| 항목 | 추정 | 근거 |
|---|---|---|
| 요청 수(국내 새 완료 거래일이 있는 실행) | 약 1,200 | 목록 1 + 네이버 약 1,176 + Yahoo 2 + 키움 토큰 1 + 수급 약 20일 |
| 첫 OCI 실행 | 위 + 수급 약 253일 | POC6-01 첫 수집 시작일 규칙 |
| 시간 | 네이버 약 8 ~ 11분 + 수급 약 7초(첫 실행 약 85초) + 나머지 30초 미만 → **보통 09:50 전후 종료** | OCI 08:10 의 41종 = 08:10:05 ~ 08:10:11(종목당 약 0.15초) · PC 0.07 ~ 0.30초 · 요청 간격 0.25초(Q4) |
| 메모리 | 모름 → 첫 실행에서 최대 RSS 측정 | FDR · pandas 만 불러옴(torch · sklearn 없음) · OCI 가용 약 530MB |
| 보관량 | 수집일당 약 3MB(gzip) → **연 약 0.75GB**(수집일 약 250) · 연구 등록 1회 14.4MB | PC 2026-10-20 수신 창 1,192종을 실제로 gzip JSONL 로 만든 크기 2.95MB · KRX 종가 행 · 기록 파일 · 수급은 합쳐 0.1MB 미만 |
| 여유 | OCI 빈 39G · PC 빈 347G | 실측 |
| 내려받는 바이트 | 모름 → `network_received_bytes=null` + 미측정 사유(판정 §6-4 · `/proc/self/io` 는 네트워크 계측이 아님) | fchart 응답이 120일이 아니라 전체 이력이다 |

**시각 주의(질문 아님)**: 09:40 에 확보한 자료는 확보 시각 규칙상 같은 날 08:30 판단에 쓸 수 없다. 전날 09:40 판까지만 쓸 수 있다. 후속 비교 설계에서 판단 시각을 정할 때 참고한다.

## 4. 보관 구조 · 명령 (§8-5)

### 4-1. 경로 · 형식 (OCI · PC 같은 구조 · `.gitignore` 에 `state/ml/evidence/` 추가)

```text
state/ml/evidence/
  objects/<sha 앞 2자>/<sha256>   내용 해시 = 이름 · 한 번 쓰면 끝(임시 파일 → fsync → os.link · 있으면 해시 비교만)
  runs/<run_id>/manifest.json      완료 묶음(.partial 폴더에 쓰고 검사 → 한 번에 이름 바꿈 · 덮어쓰기 없음)
  catalog.jsonl                    공개된 묶음 한 줄씩 이어 씀(run_id · kind · manifest sha · published_at · 생산 장소 · PC 는 copied_at_pc)
                                   — 색인일 뿐, 정본은 runs/*/manifest.json(다시 만들 수 있음)
  .incoming/                       업로드(OCI) · 내려받기(PC) 임시 칸
  .collect.lock · .index.lock      일일 수집 단일 실행 · 공개(색인) 쓰기 잠금(일일 · 연구 등록 · 가져오기 공용 · fcntl.flock)
```

- **파일 형식**: JSON · JSONL 과 gzip(mtime 0 · 같은 내용 = 같은 바이트)만 쓴다. 표준 라이브러리만 쓴다.
- **연구 원본**: 압축하지 않고 원래 바이트 그대로 둔다.
- **공개 순서**: 완료 manifest 가 없는 묶음은 조회하지 않는다. 디스크 부족 등으로 쓰기에 실패하면 새 묶음은 FAILED 이고 이전 완료본은 그대로다.
- **정리 · 압축 · 덮어쓰기**: 자동 삭제 · N일 유지 · 덮어쓰기는 없다.
- **manifest 공통 칸**:
  - schema_version · run_id(UTC 시각 + 8자) · kind · code_commit(`git rev-parse HEAD`) · site
  - started/finished_at(UTC `…Z`) · status
  - 대상 목록 참조 · 날짜 축(달력 CSV sha256 · KOSPI 저장일 목록 해시 · 마지막 완료 거래일)
  - 자료원별 항목 · 라이브러리 판 · 자원(경과 · 최대 RSS · 읽은 바이트) · 이전 묶음 참조 · 실패 사유
  - 토큰 · 인증 헤더 · 응답 원문 전체는 넣지 않는다.

### 4-2. OCI 일일 수집 `run_ml_evidence.py collect-daily` (cron `40 9 * * *` 제안)

**언제 무엇을 받는가** — 매일 실행하되 받을 것만 받는다.

| 자료 | 받는 조건 · 방식 | 보관 | OCI DB |
|---|---|---|---|
| ETF 목록 | 국내 **새 완료 거래일**이 있을 때(운영 축 기준 오늘 KST 미만의 마지막 거래일이 직전 보관본보다 새로울 때 · 토요일 실행이 금요일 봉을 받는다). FDR 목록 1회 | 목록 · 목록 해시 · 기준일 · 분류 출처 · 추가 · 사라짐 · KRX T-1 종목과의 차이 수. 실패 · 빈 응답 · 직전의 95% 미만이면 직전 목록 + 그 날짜 + `stale` 표시 | 쓰지 않음(`etf_master` 그대로) |
| 네이버/FDR 수신 창 | 목록의 각 ETF 를 순서대로 120일 요청. **오늘 KST 날짜 이상 행은 진행 중 봉으로 빼고 개수를 남긴다.** 종목마다 한 줄씩 gzip JSONL 하나로 흘려 쓴다(전 종목을 메모리에 쌓지 않음) | 요청 · 반환 범위 · 받은 시각(UTC) · 행(날짜 · OHLC · 거래량 · change) · 61행 미만 '부족' · 실패 사유. 가격 의미 = 'NAVER_FDR 수신 창 · 수정주가 · 총수익 · PIT 보증 아님 · change = 같은 응답 종가 계산' | **쓰지 않음**(Q2) |
| KRX ETF · 보유 개별주 종가 | 재조회 0. 최근 21거래일 중 직전 보관 이후 내용이 바뀐 날짜만 표에서 읽는다 | 행 + 표의 `collected_at` = 'DB 마지막 쓰기 시각(첫 확보 보증 아님)' | 읽기만 |
| KOSPI · VIX · US500 · IXIC · ^SOX | 같음(재조회 0 · 바뀐 날짜만) | 행 + `created_at` 같은 뜻 · KOSPI 정정 증거 파일 새것 | 읽기만 |
| 배치 수집 기록 | 08:10 · 09:20 상태 JSON 두 개를 읽어 해시가 바뀌었으면 보관 | 파일 바이트 그대로 | — |
| 원/달러 · WTI | 매 실행 · POC6-01 함수 그대로(90일 겹침 · 완료 봉 규칙) | **표에 쓰기 전에** 받은 행 · 받은 시각 · since 를 보관 칸에 먼저 쓴다. 실패하면 그 계열은 upsert 하지 않는다(KOSPI 정정 선례) | 두 표 생성 · upsert(POC6-01 과 같은 스키마) |
| 코스피 수급 | 매 실행 · POC6-01 함수 그대로(최신 날짜 먼저 · 20거래일 겹침 · 400 · 180초 · 3회) | 날짜별 받은 순매수 13분류 · 지수값 · 받은 시각 · 실패 날짜 사유 · **미시도 날짜 사유**(KOSPI 저장일 없음 · 상한 · 연속 실패 · 인증) | 같음 |

**네이버 단계 상한**:

- 요청 20초(`fdr_request_timeout` 재사용) · 연속 시간 초과 5회 멈춤(PC 규칙)
- 요청 간격 0.25초 · 30분 = 새 요청을 시작하지 않는 시간 예산(강제 종료 보장 아님) · 연속 실패(종류 무관) 20회 멈춤 · 명확한 HTTP 403/429 즉시 멈춤(Q4 · 판정 §5)
- 남은 종목은 '미시도 · 사유'로 둔다.

**프로세스 경계**:

- 독립 프로세스이고 `.collect.lock` 을 잡는다. 이미 실행 중이면 즉시 끝내고 'busy' 를 기록한다.
- DB 쓰기는 두 시장 흐름 표의 짧은 upsert 둘뿐이다. 보관 파일 생성 · 압축 · 외부 대기는 DB 잠금 밖에서 한다.
- `app/ml_evidence` 는 torch · sklearn · `app.d20_*` · `app.reentry_review` 를 불러오지 않는다(시험으로 고정).

**상태**:

- 자료원별로 `OK / PARTIAL / FAILED` 와 성공 · 실패 · 미시도 수 · 사유를 남긴다.
- '새 자료 없음(휴장 · 새 완료 거래일 없음)'은 실패가 아니라 `SKIPPED_NO_NEW` 로 따로 둔다.
- 묶음 전체는 이렇게 정한다:
  - 하나라도 실패 · 미시도가 있으면 PARTIAL
  - 공개에 실패하면 FAILED
  - 파일 손상은 FAILED(자료 부족과 구분)
- 보관과 표 반영이 엇갈리면 불일치로 기록한다(성공으로 감추지 않음).

### 4-3. 연구 증거 등록 · 업로드 (PC → OCI 1회 · 이후 추가분만)

**`register-research`(PC)**:

- 02 · 03 · 04 공식 파일을 원래 바이트로 objects 에 넣는다(원본 위치 파일은 읽기만 하고, 등록 전후 해시가 같은지 확인한다).
- `RESEARCH_REGISTRATION` manifest 하나에 실험마다 다음을 연결한다.
  - experiment_id(`POC6-02:20261021T104103_129a89b0` 등)
  - 원래 상대 경로 · 코드 커밋(위 §2 방식)
  - input · recipe digest · 대상 목록(4 · 12 · 26 · 제외 22)
  - 목표 · feature 정의 · 실행 환경
  - 예측 · 정답 위치(JSON 키 경로) 또는 `predictions=not_saved`(04)
  - 원래 판정(HGB RESEARCH_PROMISING · MLP REJECT · 04 탐색적 기준 미충족)
  - 결과서 · 판정 문서 경로 + 커밋 · `trained_artifact=not_saved` · `record_type=RETROSPECTIVE_TEST` · `imported_at`
- 봉인 KRX 판은 올리지 않는다. 경로 · 파일 해시 `fe3022e9…` · 내용 해시 `c1a87776…` · 바이트만 참조한다.
- 받은 파일 해시가 기대와 다르면 그 파일만 `CHECK_REQUIRED` 로 두고 등록하지 않는다.

**`upload-research`(PC)**:

- objects + manifest 를 OCI `.incoming/<upload_id>/` 에 scp 한다.
- 그다음 OCI 의 `accept-upload <upload_id>` 를 ssh 로 실행한다. 이 명령은:
  - kind = RESEARCH_REGISTRATION · 허용 experiment_id · 모든 해시 · 이름 = 해시만(경로 문자 거절)을 검사한다.
  - 검사를 통과하면 `.index.lock` 아래에서 공개하고 incoming 을 지운다.
- 다른 경로에는 쓰지 못한다(임의 원격 쓰기 도구 아님).

**미래 예측 기록 형식만 정한다(생산 작업 없음)**: `FORWARD_RESEARCH` 칸은 다음과 같다.

- record_type · model_id · model_version · recipe_digest · 입력 묶음 참조 · decision_time
- generated_at · 학습 자료 종료일 · 학습 자료 확보 기준 시각 · 목표 정의 · 대상 목록 참조 · 예측값

### 4-4. PC 가져오기 · 읽기 · export · 복구 확인

**`pull`**:

- ssh 로 OCI 의 `list-runs`(읽기 전용 · stdout JSONL · **완료 manifest 전체 목록**)를 실행한다. 시각 커서는 쓰지 않는다(판정 §6-1).
- 새 완료 묶음마다 manifest 와 PC 에 없는 해시의 objects 만 scp 로 `.incoming/` 에 받는다.
- 형식 · 해시 · 참조를 검사한 뒤 object → manifest 순서로 공개한다(copied_at_pc 기록).
- 이어받기: 중단되면 다음 실행이 빠진 해시만 다시 받는다.
- 충돌: 같은 run_id 인데 manifest 해시가 다르면 거절하고 보고한다.
- SSH 실패는 기존 사본을 지우지 않는다.
- ssh 옵션은 원장 사본과 같다(`BatchMode=yes` · `ConnectTimeout=8` · `OCI_SSH_TARGET`).

**`status`**: 다음을 보여 준다.

- 묶음 목록 · 자료원별 최신 관측일 · 확보 시각 · 실패 · 누락
- 연구 실험의 입력 · 예측 · 정답 연결
- PC 두 번째 사본 유무(PC 에 아직 없는 OCI 묶음 = '두 번째 사본 없음')

**`export --as-of <UTC> [--tickers]`**:

- 종목마다 `available_at ≤ as-of` 인 가장 새 수신 창을 **그대로** 골라 `state/ml/research/poc6_05_exports/<시각>/` 에 새 파일로 쓴다.
- 여러 판을 이어 붙이지 않는다. 회고 자료(`imported_at`)는 표시한다.
- 02 형식 호환 출력은 만들지 않는다(장기 이력은 수신 창에 없음 · 사유를 export manifest 에 적음).
- 외부 조회 · 학습 · DB 쓰기 0.

**`restore-check --run <id> --to <빈 임시 폴더>`**:

- 완료 묶음 하나를 별도 경로에 복원해 같은 해시 · 목록 · 읽기 결과(gunzip · JSON 해석 · 행 수)를 비교한다.
- 실행 중인 SQLite 복사 · 원본 위 복구는 하지 않는다.

## 5. 코드 변경 범위 (§8-6)

| 구분 | 파일 | 내용 |
|---|---|---|
| 새 파일 | `app/ml_evidence/__init__.py` · `store.py` · `daily.py` · `research.py` · `transfer.py` · `export.py` | 각 400줄 미만 목표 |
| 새 파일 | `scripts/run_ml_evidence.py` | 하위 명령: `collect-daily` · `list-runs` · `accept-upload`(OCI) · `register-research` · `upload-research` · `pull` · `status` · `export` · `restore-check`(PC) |
| 새 파일 | `tests/test_poc6_05_evidence_store.py` · `tests/test_poc6_05_evidence_daily.py` | 각 1,450줄 미만 |
| 수정 | `app/supply_fx_oil_refresh.py`(261줄) | `refresh_fx_wti` · `refresh_investor_flows` 에 선택 인자 `capture`(기본 None)를 추가한다. None 이면 PC 동작은 그대로다. 약 +35줄 |
| 수정 | `app/supply_fx_oil_store.py` L9 · `app/kiwoom_investor_flow.py` L4-5 | 'PC 에서만' 주석 → 'PC 갱신 + OCI 05 수집' |
| 수정 | `.gitignore` | `state/ml/evidence/` 한 줄 |
| 문서 | `PROGRAM_TRUTH` · `STATE_LATEST` · (Q1 (a)면) 기반 문서 3곳 날짜 주석 | — |

**바꾸지 않는 것**:

- `scripts/run_oci_market_data_batch.py`(596줄) · `app/market_refresh_service.py`(616줄 · 근접) · `market_data_store.py` · `market_data_fdr.py`
  - `market_data_fdr.py` 의 함수는 POC6-03 처럼 읽기 재사용만 한다.
- OCI `etf_daily_price` · `etf_master` · KRX 표 · PUSH · 원장
- 새 의존성 · 새 DB · 공개 API · 화면

## 6. 시험 · 실제 실행 · 종료 구분 (§8-7)

### 6-1. 격리 시험(tmp 폴더 · tmp DB · 가짜 수집기 · 가짜 원격 · 라이브 DB 열지 않음)

| 수용 기준(설계 §9) | 시험 |
|---|---|
| 1 연구 원본 불변 · 같은 해시 | 고정 fixture 로 등록 → 원본 해시 전후 동일 · objects 바이트 = 원본 · 04 `predictions=not_saved` · `trained_artifact=not_saved` · RETROSPECTIVE_TEST |
| 2 보유와 독립 | 보유 파일 · 개인 값 · 사용자 평가를 바꿔도 대상 목록 · 수신 창 파일 바이트가 같다 · 목록 변경(추가 · 사라짐) · stale · 실패 분모 |
| 3 정정 판 보존 · 기준 시각 | 같은 날짜 값이 바뀐 두 묶음 → 둘 다 남음 · export as-of 가 나중 정정을 고르지 않음 · imported_at ≠ observed_at |
| 4 가격 · 시각 의미 분리 | 진행 중 봉 제외 · NAVER/KRX/D20 라벨 · 새 모델 결과 0 |
| 5 실패 · 손상 · 중복 · 중단 | 부분 실패 → PARTIAL · 미시도 사유 · 디스크 쓰기 실패 → FAILED + 이전 완료본 그대로 · 손상 object 거절 · `.collect.lock` busy · 중단된 pull 이어받기 · manifest 없는 묶음 무시 · 같은 id 다른 내용 거절 |
| 6 PC 쪽 쓰기 경계 | pull · export 는 시장 · 원장 · 보유 DB 를 열지 않는다 · 새 자료 없어도 기존 사본 읽기 |
| 7 비밀 · 개인 값 · 경로 | 환경 변수 값(가짜 토큰)이 어떤 산출물 · 오류에도 없음 · upload 의 경로 문자 · 허용 밖 experiment_id 거절 |
| 8 운영 불변 | `capture=None` 이면 POC6-01 기존 시험 그대로 통과 · 표 반영 전 보관 순서(보관 실패 → upsert 0) · 수집 모듈이 torch · sklearn · `app.d20_*` 를 불러오지 않음(하위 프로세스 확인) |

그 뒤 다음을 한다.

- 독립 검토 1회
- 의미 있는 변이(순서 뒤집기 · 미시도 집계 누락 · 진행 중 봉 포함 · 덮어쓰기 허용 등)
- 관련 시험 → 전체 회귀 1회

### 6-2. 실제 실행 순서 (설계 §10)

**RESULT 판정 → 사용자 승인 범위 진행**:

1. 커밋 · push
2. OCI pull(거래일 08:05 ~ 15:45 피함)
3. 사용자: OCI `.env` 에 키움 두 이름 추가 · 키움에 OCI 공인 IP 등록
4. OCI 수동 `collect-daily` 1회(장 마감 뒤 또는 주말)
5. PC `pull`
6. PC `register-research` → `upload-research`
7. `restore-check` 두 방향
   - PC 임시 폴더에 OCI 일일 묶음 복원
   - OCI 임시 폴더에 연구 묶음 복원
8. 사용자: crontab 한 줄 추가 → `crontab -l` 읽기 확인
9. 종료 기록

**운영 불변 확인(읽기만)**:

- 수동 실행 전후 OCI `etf_daily_price` · `etf_master` · KRX · 지수 표의 행 수 · 최대 시각이 같다.
- 새로 생긴 것은 두 시장 흐름 표뿐이다.
- 다음 거래일 08:10 배치 · 08:30 브리핑 기록이 정상이다.

**종료 판정**: 수동 실제 1회 · PC 가져오기 · 연구 보관 · 복구 · 설정 확인으로 한다. 첫 09:40 cron 결과는 '정기 운영 확인'으로 따로 표시한다. 20거래일 대기 · 모델 성능 · GPU 가동은 종료 조건이 아니다.

**일정**: 2026-10-23(금) 배치 완료 뒤 POC5-04 공식 R0 1회(개발자 · OCI 읽기 전용 · POC5 종료 인계 §4-1)가 예정돼 있다. 05 의 실제 OCI 작업은 그와 겹치지 않게 그 뒤로 잡는다.

## 7. 질문 (실제 충돌만)

**Q1. OCI 수집 경계 — 기반 문서와 충돌.**

`PROJECT_ORIGIN_INTENT.md` §7(L142-152 · 2026-07-26 정정) · `KILL_SWITCHES.md` KS-11 2026-07-26 기록(L135-153) · `ASSUMPTIONS.md` 「PC · OCI 역할 경계」(L328-330)는 다음을 정해 두었다.

- OCI 자율 시세 갱신 = '승인 seed ∪ 현재 보유 한정'
- '전체 시장 수집 · ML' 은 금지 유지

설계 §2-1(보유와 무관한 ETF 전체를 OCI 에서 네이버로 매일)과 OCI 연구 증거 보관은 이 범위 밖이다. 설계 §1 의 '05 한정 별도 범위'는 기반 문서에 아직 기록이 없다. 선례: OCI 는 이미 KRX ETF 전체 종가를 매일 받는다(POC3-02D-OPS-03).

- **(a) 권장**: 판정문에 '05 한정 해석' 문장을 주시면 POC5-27 선례처럼 세 기반 문서에 날짜 · 출처와 함께 그대로 넣는다.
  - 범위 = 연구 증거의 수집 · 보관만
  - 후보 탐색 · 운영 사용 · OCI 학습/추론 · 운영 가격 표 교체 없음
- (b) 경계를 유지한다.
  - 네이버 수신 창은 seed ∪ 보유만 받는다.
  - ETF 전체는 이미 있는 KRX 종가 보관으로만 덮는다(거래량 · change · 네이버 기준 없음).

**Q2. 네이버 수신 창을 OCI DB 에도 쓰는가 — 설계 §4 '기존 표 우선 재사용' 과 §3-1 '가격 저장 교체 없음'의 두 해석.**

- **(a) 권장**: 보관 파일에만 둔다.
  - OCI DB 쓰기는 두 시장 흐름 표뿐이다.
  - 1,176종 120일 창을 `etf_daily_price` 에 upsert 하면 41종 운영 행과 `fetched_at` 을 덮는다. 그러면 08:10 증분 · 유니버스 산출물의 입력이 바뀐다.
- (b) 운영 41종을 뺀 나머지만 `etf_daily_price` 에 쓴다.
  - 표 안에서 서로 다른 갱신 주기가 섞인다.

**Q3. 연구 증거 등록 범위.**

- **(a) 권장**: 02 · 03 · 04 공식 22파일(내용 21)만 등록 · 업로드한다.
  - 03 대조 보고서는 KRX 원가격이 아니라 계산 배율뿐이다. 사용자 소유 서버이고 같은 KRX 키 보유자이므로 올린다.
  - 봉인 KRX 판(OCI 미전송 계약)은 해시 참조만 둔다.
  - 06 · 08 은 이번에 등록하지 않는다.
    - 06 은 평단 · 수량 · 실현손익이 있어 설계 §2-6 · §5 와 충돌한다.
    - 개인 칸을 지우면 '같은 해시'(§9-1)가 깨진다.
- (b) (a) + 08 을 등록한다(수량 · 평단 없음 · 보유 표시 · 평가 1건 포함).
- (c) (b) + 06 을 PC 에만 등록한다(OCI 미업로드).

**Q4. OCI 네이버 단계 상한 — 설계 §6-4 'PC 규칙 재사용'에 더하는 것.**

PC 규칙에는 총 시간 상한이 없다(실측 최대 363초). 같은 OCI IP 로 08:10 운영 가격(41종) · 보유 현재가도 네이버를 쓴다.

- **(a) 권장**: PC 규칙(20초 · 연속 시간 초과 5회)에 아래를 더한다. 남은 종목은 미시도로 둔다.
  - 요청 간격 0.25초(POC6-01 `CALL_GAP_S` 재사용)
  - 30분 = 새 요청을 시작하지 않는 시간 예산(강제 종료 보장 아님 · 판정 §5 정정)
  - 연속 실패 종류 무관 20회 멈춤(차단 응답에 계속 요청하지 않음)
- (b) PC 규칙만 쓴다.

## 8. 사용자 승인이 필요한 일 (CLAUDE.md §7 · PLAN 판정 뒤 한 번에)

1. 외부 조회 추가: OCI 에서 네이버 ETF 목록 · 수신 창(약 1,176종/일) · Yahoo 원/달러 · WTI · 키움 ka10051.
2. DB 스키마 변경: OCI `market_data.sqlite` 에 `market_macro_daily` · `market_investor_flow_daily` 생성(POC6-01 과 같은 스키마).
3. OCI 쓰기:
   - pull
   - `state/ml/evidence/` 생성 · 쓰기
   - 연구 묶음 업로드
   - crontab 한 줄(`40 9 * * * cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_ml_evidence.py collect-daily >> logs/ml_evidence_daily.log 2>&1`)
4. 사용자 직접:
   - OCI `.env` 키움 두 값
   - 키움 OCI IP 등록(키는 채팅 · 문서 · 로그로 받지 않는다)
5. 커밋 · push.

## 9. 하지 않는 것

- 새 학습 · 추론 · 성과 비교 · D20 정답 · 오차 · 모델 선택 · 예측 생산 작업
- 화면 · 메뉴 · 공개 API
- 08:10 · 09:20 배치 수정
- 기존 연구 재실행 · 2014년 이후 장기 백필 · 상장폐지 모집단 복원
- pickle 저장 · 출처 불명 pickle 읽기
- 저장소 · `.env` · 보유 · AI 세션 DB 보내기
- NAS · 유료 저장소 · 상시 동기화
- PC 수집 · 수동 갱신 버튼 변경
- #3 · #55 · #57 · #62 를 완료로 바꾸기
- 별도 handoff 문서

## 10. 진행

설계자 PLAN 판정 → (승인 받은 범위로) 구현 · 격리 시험 → 독립 검토 · 변이 · 전체 회귀 → RESULT → 검증자 → 설계자 RESULT 판정 → 사용자 승인 범위의 커밋 · push · OCI 배포 · 수동 실제 1회 · PC 가져오기 · 복구 확인 · cron → 종료 기록 → 다음 날 정기 운영 확인.

## 부록 A. 02 · 03 · 04 공식 파일 (2026-10-22 실측 · `.DS_Store` 제외)

| 실험 | 파일 | 바이트 | sha256 |
|---|---|---:|---|
| 02 | report.json | 265,284 | 700c55a832834536941055a2e117cab4fb115d53f175f89baa9e79946c71312a |
| 02 | report.md | 9,171 | d8b298288f443fcd936167ebb34848621cfbbb3c5b34c10eaf3923cf6add492a |
| 02 | input_snapshot.json | 2,779,173 | eccfce451d20e4f082c2f28b79a29a796a72f7b80979789665bc4b1d6eb1d57b |
| 02 | gpu_bundle.zip | 733,466 | 5843829d9c53f97008495caeedad8913dd5fedce5b4164301ba6a008921cdd07 |
| 02 | gpu_bundle/gpu_input.json | 2,369,207 | 21a8c52734718e156edf87ba454181a1ef6f9e33622c6034a12966075587ddda |
| 02 | gpu_bundle/gpu_runner.py | 13,243 | 139099338e43b4de8854285eb2b3d05a00acd119891aa62689a05ca957538102 |
| 02 | gpu_bundle/mlp.py | 6,803 | 930095c04533aae01add24d3219095d1c3fe6e9c0cd9384e5800859a207593a2 |
| 02 | gpu_bundle/run_gpu.bat | 131 | 4ee204e61cb70a77101778d65dbb6d6f21d5fd3f1d02809094c5ed81ddedbf48 |
| 02 | gpu_bundle/README_KO.txt | 1,135 | b5ee9589baf99ae27ad301b2c26ada54f38a396567b5cb94601db02c318a9c37 |
| 02 | gpu_result.json | 42,880 | d5dac74d483dc754094defe2b2ce0eef6db7137d983703f8e6821fa1b17a2b6a |
| 02 | gpu_merged/report_with_gpu.json | 302,890 | 85b67c587828ca39297addff273482be09174c25043ddc60f8c7a1435f7f4bfe |
| 02 | gpu_merged/report_with_gpu.md | 10,467 | 84dd6bc8cde17d5c74c01b4b816ecd563618380377417d4c7b1167bb7ba07e3e |
| 03 | copy.sqlite | 3,051,520 | 276c29e74b0d100e97d9eaf33b59214ab896329d8e87004384a74503143bb088 |
| 03 | fetch.json | 10,576 | 709a2837aaa1cdbcb2cf25337b904da206787eb529c7496a06d0f55c537e6213 |
| 03 | compare_20261021T161507_3927699a/report.json | 778,392 | a5ecf0137c3f2541ed31f5e9be90f2623514f17bd0328c849b827754e5dab772 |
| 03 | compare_20261021T161507_3927699a/report.md | 70,284 | 4496059ccce94a2aa4cb426f62da8b9095722b54523c61bd31ddabb7ad7aef41 |
| 04 | manifest.json | 2,110 | a2953b3bcc176142f59c10fa035ae8c37193d74abfd665164459d416f20afae7 |
| 04 | a_report_frozen.json | 265,284 | 700c55a832834536941055a2e117cab4fb115d53f175f89baa9e79946c71312a |
| 04 | b_snapshot.json | 671,175 | 0cdb21c490d94818fd1de9afe080c02cc4bffc8cb8de78cee2cf490325ef8d64 |
| 04 | c_snapshot.json | 3,272,043 | 40074f11956fc105d7fac9e04a1296fb5a655be45f3dcf5cccdab6d35d7aa457 |
| 04 | report.json | 24,458 | 70c575a2f4315d37fdac076764512442762d27515a4d02beb46e377e6d92bd1c |
| 04 | report.md | 7,843 | 54392f3242b00d1901387cca469e326635af19f28089950bdf21015d0fb62b0b |

## 11. 설계자 판정 반영 (2026-10-22 · 판정 원문 `docs/ai_design/POC6/POC6-05_CONTINUOUS_MARKET_DATA_AND_ML_EVIDENCE_RETENTION_PLAN_DECISION_2026-10-22.md`)

판정 = **PASS_WITH_REQUIRED_CORRECTIONS**. Q1 ~ Q4 모두 (a) 수용. 아래가 위 본문보다 우선한다.

### 11-1. 질문 판정

| 질문 | 판정 | 반영 |
|---|---|---|
| Q1 OCI 수집 경계 | (a) | 판정 §2 문장을 `PROJECT_ORIGIN_INTENT.md` §7 · `KILL_SWITCHES.md` KS-11 · `ASSUMPTIONS.md` 「PC · OCI 역할 경계」에 날짜 · 출처와 함께 원문 그대로 추가(2026-10-22 · 기존 원문 보존) |
| Q2 네이버 창 저장 | (a) | 증거 파일에만. `etf_daily_price` · `etf_master` · KRX · 지수 표 쓰기 0. 새 목록은 evidence 안에서 관리. OCI DB 새 쓰기 = 두 시장 흐름 표만. `capture=None` PC 동작 그대로 · capture 실패 값은 upsert 0 |
| Q3 연구 등록 | (a) | 02 · 03 · 04 공식 22파일(내용 중복 1 = 같은 object). 봉인 KRX 판 = 참조만. POC5-06 · 08 = 이번 OCI 등록 제외 · PC 원본 보존(폐기 · 보관 완료로 기록하지 않음) |
| Q4 네이버 제한 | (a) + 정정 | 간격 ≥ 0.25초 · 요청 20초 · 연속 시간 초과 5회 · 연속 실패(종류 무관) 20회(성공하면 초기화) · 명확한 HTTP 403/429 즉시 멈춤 · 30분 = 새 요청 시작 금지 예산(대기 전후 확인 · 강제 종료 보장 아님) · 자동 재시도 · 새 접속 방식 없음 |

### 11-2. 필수 보완 (판정 §6)

1. **동기화 누락 방지**: `list-runs` 는 완료 manifest 전체(run_id · manifest sha)를 돌려주고 PC 는 없는 것만 받는다. 시각 커서 없음. 정본 = `runs/*/manifest.json` · `catalog.jsonl` 은 다시 만들 수 있는 색인(공개 뒤 append 전에 끊겨도 누락 없음).
2. **부분 실패 뒤 다음 실행**: 같은 기준 거래일의 국내 단계가 PARTIAL/FAILED 이거나 미확보 종목이 있으면 다음 일일 실행이 그 종목만 다시 시도한다. 이미 받은 종목은 이전 판(run_id · object)을 명시해 재사용한다. 별도 당일 재시도 일정 없음.
3. **공급자 미제공 ≠ 실패**: 받은 창에 기준 거래일 행이 없으면 `NO_NEW_ROW`(실패 아님 · 따로 셈). 토요일에 받은 금요일 봉의 확보 시각은 토요일이다.
4. **시각 칸**: `observed_at` = 실제 수신 · `published_at`(= `available_at`) = 검증된 묶음의 최초 공개(manifest 안 · 이후 바뀌지 않음) · `imported_at` = 과거 자료 등록 · `copied_at_pc` = PC 수신(PC 쪽 receipt 파일 · manifest 바이트는 OCI 와 같음).
5. **export**: 공개된 정상 묶음 + `published_at ≤ as-of` 를 함께 검사한다. PARTIAL 의 유효 자료는 실패 범위와 함께 내보내고, FAILED · 미완료 · 손상은 내보내지 않는다.
6. **상태**: 유효 자료가 있는 부분 실패 = PARTIAL · 필요한 확보가 모두 실패했거나 무결성 · 공개 실패 = FAILED · 정상적인 새 자료 없음 = SKIPPED_NO_NEW. 상태와 자료원별 성공 · 실패 · 미시도 분모가 맞아야 한다.
7. **날짜 축 · 이전 판 실제 보관**: 달력 CSV · 연구 축 KOSPI 저장일 목록을 hash 만이 아니라 object 로 보관(없으면 없음 기록 · 새 달력 제작 없음). KRX · 지수는 최근 21거래일 delta — 첫 실행 = 21일 전체 · 이후 바뀐 날짜만 새 object · 안 바뀐 날짜는 이전 object 참조. manifest 의 object 목록에 참조한 이전 object 까지 넣어 export · 복구 · 가져오기가 함께 가져간다. 21일 밖 과거 정정 보존은 주장하지 않는다.
8. **DB 읽기**: 관련 행 · 날짜 축은 짧은 읽기 전용 트랜잭션 하나에서 읽고 외부 대기 · 압축 전에 닫는다. DB 마지막 쓰기 시각을 최초 확보 시각으로 쓰지 않는다.
9. **자원 수치**: `network_received_bytes=null`(미측정 사유) · 보관 바이트 · 경과 · 최대 RSS(Linux = KiB · macOS = bytes 단위 칸을 함께 저장). 연 0.75GB 는 추정 표시 · 실제 증가량 한 번 기록.
10. **목록 95% 규칙**: 공급자 응답 급감에 대한 임시 보류 — 새 응답 · 차이 수 · 사유 보존 + 이전 목록 stale 사용. 대규모 상장폐지 확정 · 새 목록 영구 폐기로 해석하지 않음.
11. **코드 연결**: 수집 · 보관 프로그램 = 실행 commit 기록. 과거 연구 = 실행 당시 commit 미상 · '코드가 처음 들어간 commit' · '결과서 재현 근거' · GPU `code_sha256` 을 근거 종류별로 따로 기록(HEAD · 최초 포함 commit 을 실행 commit 으로 대입 금지).

### 11-3. 시험 보강 (판정 §7)

늦게 공개된 낮은 run_id 도 다음 pull 에 포함 · manifest 공개와 색인 append 사이 중단 · 같은 기준일 부분 실패 뒤 다음 일일 시도 · 과거 as-of 에서 미래 정정 배제 · 날짜 축 · 이전 판 참조를 포함한 복구 · 시간 예산 · 연속 실패 · 403/429 멈춤.

### 11-4. 실제 실행 · 승인 (판정 §5 · §8)

- 첫 실연결은 소수 종목 순차 처리로 RSS 를 확인한 뒤 전체로 넓힌다(같은 승인 범위 · 별도 부하 시험 아님). 운영에 쓸 메모리 여유가 없으면 전체를 강행하지 않고 부분 결과 · 제한을 보고한다.
- 실제 OCI 외부 조회 · 표 2개 생성 · 보관 경로 · 연구 업로드 · pull · cron · 커밋 · push 는 §8 묶음으로 사용자 승인을 한 번 확인한다(이 판정 자체는 승인 아님).
- 2026-10-23 POC5-04 공식 R0 는 별도 점검이다. 05 구현 · 격리 시험은 계속하고, 실제 OCI 배포 · 실수집만 겹치지 않게 한다.
- 종료 = 수동 실수집 · PC 가져오기 · 연구 사본 · 임시 경로 복구 · 설정 확인. 첫 정기 cron = 별도 운영 확인. handoff 문서 없음.
