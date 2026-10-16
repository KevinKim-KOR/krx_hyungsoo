# POC5-18 개발 PLAN V1 — PC 시장 갱신의 예상 밖 오류 상태 정정

작성 2026-10-16 · 작성자: 개발자(VSCode Claude) · 수신: 설계자
근거: `docs/ai_design/POC5/POC5-18_PC_MARKET_REFRESH_UNEXPECTED_FAILURE_STATUS_DESIGN_V1.md`(V1) · 대상 결함 `DEF-PC-REFRESH-UNEXPECTED-COMPLETED`

```text
STATUS   = 설계자 PLAN PASS(2026-10-16 · 제출안 그대로 · 추가 보충 없음 · 판정 원문 §5) → 구현(2026-10-16) · 결과서 docs/ai_result/POC5/POC5-18_PC_MARKET_REFRESH_UNEXPECTED_FAILURE_STATUS_RESULT.md → 검증자 r1 VERIFIED → 설계자 RESULT PASS · 종료(2026-10-16)
SCOPE    = app/market_refresh_service.py 의 refresh_unexpected 예외 경계 · 최종 성공 판정만
           API · 응답 필드 · 화면 · DB 표 · 의존성 · 공유 함수(market_data_fdr) · OCI · PUSH · 수동 스크립트 · POC5-17 요청 timeout 변경 0
```

## 1. 확인 결과 (설계 §5-1)

### 1-1. 예외 경계는 한 곳
- `app/market_refresh_service.py :: _execute_refresh_job` 의 ETF 목록 · 가격 블록 `try`(`:320`) / `except Exception`(`:346`)에서 `error_summary = "refresh_unexpected: …"` 를 남긴다(`:347`).
- 저장소에서 이 문구를 만드는 곳은 여기뿐이다(`grep refresh_unexpected app/`). 뒤 단계(보유 개별주 `:366` · KOSPI `:400` · VIX `:421` · NAV `:439`)는 각자 다른 예외 처리와 문구를 쓰며, 이번 대상이 아니다.

### 1-2. 이 경계에 닿는 경로와 지금 판정
| 경로 | 예외가 나는 곳 | 지금 최종 상태 |
|---|---|---|
| ETF 목록 단계 안 저장 · 기록 실패 | `market_data_fdr.refresh_etf_universe` 의 `upsert_etf_master` · `log_refresh`(try 밖) | `universe_ok` 가 거짓으로 남아(`:324` 미도달) **이미 failed** |
| **종목 목록 읽기 실패** | `list_etf_tickers`(`:329`) | **completed**(아래) |
| **가격 함수가 결과를 돌려주기 전 예외** | `refresh_price_history` 의 가격 기록 행 `log_refresh` · 종목 루프 안이지만 fetch 예외 처리 블록 밖인 행 변환 등 | **completed**(아래) · 연속 중단이 있었으면 POC5-17 로 이미 failed |

- 완료로 끝나는 이유: 최종 판정 `success_overall = universe_ok and (price_success > 0 or price_attempted == 0)`(`:444`)이다. 예외로 가격 건수를 못 받으면 `price_attempted` 가 초깃값 0이라 참이 된다.
- 최종 상태 · 성공 시각은 `:465`(`completed` / `failed`) · `:474~476`(성공일 때만 `last_success_at` · `last_success_asof_date`) · `:479`(영속화)에서 정해진다. 실패 경로는 이전 성공 기록을 덮지 않는다(`_persist_current_state` `:205~246`).
- 같은 블록의 POC5-17 코드(`:351`)는 중단 문구 뒤에 예외 사유를 붙일지를 **오류 문자열 접두어**(`startswith("refresh_unexpected")`)로 판단한다. 설계 §3 취지에 맞게 이번 표식으로 바꾼다.

### 1-3. VIX 전용 재시도와의 관계
- `vix_only_failure`(`:449`)는 `success_overall` 이 참이고 `error_summary` 가 없을 때만 참이다. 예상 밖 오류가 있으면 이미 `error_summary` 가 있으므로 지금도 거짓이다.
- 최종 failed 가 되면 `success_overall` 도 거짓이라 VIX 단독 실패로 판정할 길이 없다.
- `sync_vix_retry_after_full_refresh`(`market_refresh_vix_retry.py:46`)는 VIX 단독 실패가 아니면 예전 표식을 `cleared` 로 둔다(기존 그대로). 전체 갱신과 VIX 다시 받기의 같은 잠금도 그대로다.

## 2. 최소 변경 (설계 §5-2)

- `market_refresh_service.py` 한 파일, 약 +1줄(지금 597줄 → 598줄 · 600줄 근접선 아래).
  1. 실행마다 새 표식 `stage_unexpected = False` 를 `stop_box` 옆에서 만든다. 함수 지역 변수라 다음 실행이 물려받지 않는다.
  2. `except`(`:346`)에서 `stage_unexpected = True` 를 세운다. 문구는 지금 그대로 남긴다.
  3. 중단 문구 결합(`:351`)은 문자열 접두어 대신 이 표식으로 판단한다. 결과 문구는 POC5-17 과 같다('중단 문구 · refresh_unexpected: …').
  4. 최종 판정: `success_overall = success_overall and not (price_stopped or stage_unexpected)`(`:446` 한 줄 교체).
- 이 결과
  - 예상 밖 오류가 난 회차는 뒤 단계가 성공해도 `failed` 다. 성공 시각 · 6시간 대기는 생기지 않고, 이전 성공 기록은 그대로다.
  - 작업이 끝난 뒤 기존 마지막 기록(`:465~479`)에서 메모리와 영속 상태가 `failed` 로 정리된다. 잠금(`running`)도 그때 풀린다.
  - 받은 가격은 종목마다 즉시 저장되므로 그대로 남는다. 건수 필드는 기존 뜻이다(예외로 받지 못하면 0 · 추정하지 않음). 사유는 `refresh_unexpected: …` 로 드러난다.
- 바꾸지 않는 것: 종목별 일부 실패의 완료 · 대기 · 마지막 5종목 시간 초과 · 미조회 0 판정 · ETF 목록 실패 · 보유 개별주 · KOSPI · VIX · NAV 정책 · 공유 함수 · 화면.

## 3. 시험 (설계 §5-3 · §6)

- 새 파일 `tests/test_pc_refresh_unexpected_failure.py` 를 만든다. 기존 도구를 그대로 가져다 쓴다.
  - `tests/test_market_vix_retry.py :: svc`(tmp DB · 다른 단계 성공 stub · 고정 시각).
  - `tests/test_pc_refresh_stall_protection.py :: _run · _scripted · _ok · _block_price_log`(SQLite 시험용 트리거로 가격 기록 INSERT 만 막음 · POC5-17 재현 방식).
- 시험 목록
  - **종목 목록 읽기 오류**: `list_etf_tickers` 를 실패시킨다.
    - 메모리와 영속 상태(`read_state`)가 모두 `failed` 인지 본다.
    - 이전 성공 기록(`last_success_at`)이 그대로이고 대기가 0이며, 다음 실행이 accepted 인지 본다.
  - **중단 없는 가격 기록 오류**: 모든 종목 정상 저장 뒤 가격 기록만 막는다.
    - 저장 자료가 남는지, `failed` · 사유 `refresh_unexpected:` · 다음 실행 accepted 인지 본다.
  - **중단 + 기록 오류**: POC5-17 시험(`test_stop_survives_price_log_failure`)이 그대로 통과하는지 본다(failed · 두 사유).
  - **대조**: 정상 완료 + 대기 · 일부 종목 실패 완료 + 대기 · 마지막 5종목 미조회 0 은 POC5-17 시험 그대로 통과해야 한다.
  - **실행 간 분리**: 오류 회차 → 다시 실행 정상 완료 → 그다음은 기존 대기(skipped_cooldown)인지 본다.
  - **VIX**: 예상 밖 오류 + VIX 실패면 VIX 다시 받기 표식이 생기지 않는다. VIX 단독 실패의 표식은 기존 시험(`test_market_vix_retry.py`) 그대로다.
- **POC5-17 시험 두 건의 기대값을 바꾼다**. 지금 동작(completed)을 그대로 고정해 둔 시험이고, BACKLOG 결함 항목에 '정정 때 기대값을 바꾼다'고 적어 둔 대상이다.
  - `test_price_log_failure_without_stop_keeps_existing_judgement`: 새 파일의 '중단 없는 가격 기록 오류' 시험으로 옮기고 원래 시험은 지운다.
  - `test_function_restored_when_exception_leaves_the_block[price]`: 복원 확인은 그대로 두고 상태 `failed` 를 더 확인한다.
- 변이: 표식을 세우지 않음 · 판정에 표식을 빼먹음 · 표식을 함수 밖(다음 실행이 물려받음)으로 · 문자열 판단으로 되돌림.
- 검사: black · flake8 · py_compile · 관련 시험(갱신 · POC5-17 · VIX 다시 받기 · OPS-03) · 전체 pytest 1회. 화면 변경이 없어 프론트 시험 · 목업은 없다.

## 4. 질문
- 없음. 확인한 경계 · 경로가 설계 §1 · §3 과 같다. 공유 함수나 다른 실행 경로를 바꿀 필요는 없다.

## 5. 설계자 PLAN 판정 원문 (2026-10-16 · PASS)

````text
# POC5-18 PLAN 판정 — 예상 밖 갱신 오류의 완료 상태 정정

작성일: 2026-10-16 · 독자: 개발자

**판정: PASS. 제출한 PLAN 그대로 구현한다. 추가 보충·PLAN 재제출은 없다.**

- 첨부 DESIGN V1과 PLAN V1을 대조했다. 예외 경계·줄 번호·호출 경로는 개발자 코드 조사 근거를 수용한다. 설계자가 저장소를 직접 검사한 것은 아니다.
- 운영 소스 변경은 `app/market_refresh_service.py` 한 파일의 확인된 예외 경계와 최종 성공 판정에 한정한다.

## 수용한 구현

1. 실행마다 새 지역 표식을 만들고, 해당 예외 경계에서 예상 밖 오류 사실을 남긴다. 최종 성공 판정에 중단과 예상 밖 오류를 모두 반영한다.
2. POC5-17의 중단·오류 사유 결합도 문자열 접두어 대신 이 표식을 사용한다. 기존 두 사유는 보존한다.
3. 정상 실행·기존 일부 실패·마지막 5종목 timeout의 기존 판정, VIX 전용 재시도, 이전 성공 기록과 저장 가격 보존은 PLAN대로 유지한다.
4. 이전 결함을 고정한 POC5-17 시험 두 건의 정정을 수용한다. 가격 기록 오류 시험의 이동·중복 제거와 요청 함수 복원 검사의 유지를 포함한다.

## 진행과 범위

- PLAN §3의 재현·대조 시험, 관련 검사와 전체 회귀 1회로 확인한 뒤 검증자와 RESULT 판정으로 진행한다. 같은 근거를 위한 별도 검토 라운드는 추가하지 않는다.
- 목업·프론트 시험·OCI 반영·외부 장애 재현·거래일 대기는 필요 없다.
- 이 단계는 확인된 두 오류 경로의 작은 마무리 수정이다. 갱신 전반 조사나 구조 개편을 붙이지 않는다. 완료 후 다음 우선순위는 남은 사용자 기능·미구현 요구에서 정한다.
- 본 판정은 구현 진행에 대한 설계 판정이다. 커밋·push는 해당 작업에 대한 사용자 승인 범위를 따른다.
- 원문은 기존 PLAN 끝에 기록해도 된다. 별도 인계 문서는 필요 없다.
````
