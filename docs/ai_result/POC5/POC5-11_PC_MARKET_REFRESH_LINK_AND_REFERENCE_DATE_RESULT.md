# POC5-11 개발 결과서 — PC_MARKET_REFRESH_LINK_AND_REFERENCE_DATE (PC 시장 자료 갱신 연결 · 기준일 정정)

작성 2026-10-14 · 작성자: 개발자(VSCode Claude) · 수신: 검증자(Codex)

```text
STATUS        = IMPLEMENTED_VERIFIED_CLOSED(2026-10-14) — **검증자 VERIFIED(2026-10-14 · 위험 NONE · 범위 폭주 NONE · 격리 사본 관련 backend 172 · frontend 463 · 정적 검사 · OCI · PUSH 기존 호출 · 출력 유지 · PLAN 끝 빈 줄은 검증자가 직접 정리)** → 사용자 갱신 1회 · 읽기 전용 확인 완료(2026-10-14 · §7-1 · VIX 10-13 · 판정 날짜 10-14 · VIX 경고 잔류) → 사용자 커밋 · push 승인 → 종료(§10)
STEP_ID       = POC5-11 PC 시장 자료 갱신 연결 · 기준일 정정
DESIGN        = 별도 설계서 없음 — 근거 = docs/ai_design/POC5/POC5-UI-03_TODAY_SCREEN_INFORMATION_HIERARCHY_DESIGN_V1.md §9 §4 · 판정 docs/ai_design/POC5/POC5-11_PC_MARKET_REFRESH_LINK_AND_REFERENCE_DATE_PLAN_DECISION_2026-10-14.md
PLAN          = docs/ai_plan/POC5/POC5-11_PC_MARKET_REFRESH_LINK_AND_REFERENCE_DATE_PLAN_V1.md (V1 · PASS · 판정 반영 · 구현 중 보충 §6)
BASE_COMMIT   = ff4279e8 (POC5-UI-03 종료 커밋)
SCOPE         = PC 갱신에 VIX 단계(새 모듈 1) · 공유 VIX 함수에 선택 인자(max_date · 기본 동작 불변) · PC 화면 API 판정 날짜 · 오늘 화면 판정 줄 이름 · 시험 · 문서
                OCI 배치 · PUSH · DB 스키마 · 의존성 · 새 메뉴 · 버튼 · 정기 갱신 변경 0
REVIEW        = 독립 검토 1회(읽기 전용 · 2관점 · 2026-10-14) — MEDIUM 2(같은 주말 오판) · LOW 9 → 모두 반영(§6-2)
CHECKS        = §8
```

## 0. 요약

- **VIX — PC 갱신에 연결**(판정 Q2 · Q3 · §3)
  - **위치**: PC '최신 시장 데이터 갱신'이 KOSPI 단계 뒤 · NAV 앞에서 VIX 를 받는다.
    - 새 모듈 `app/pc_vix_refresh.py :: refresh_pc_vix` 가 OCI 08:10 배치와 같은 `market_benchmark_batch.refresh_vix` 를 부른다.
  - **요청 timeout 20초**: 기존 `fdr_request_timeout()` 으로 VIX 블록을 감싼다.
    - 그 블록 안 `requests` 호출(FDR Yahoo `^VIX` 조회 1회 · timeout 인자 없음)에 `timeout=20` 이 들어간다.
    - 그래서 연결 대기 20초 · 응답 바이트 사이 무응답 20초를 각각 끊는다.
    - 조회 1회 전체 시간 · DNS 조회 · 전체 갱신 시간의 상한은 아니다.
    - 블록을 빠져나오면(정상 · 예외 · timeout) `requests.Session.request` 가 원래 함수로 돌아간다.
  - **미확정 자료 제외**(판정 §3 · §4-1): PC 호출만 `max_date` 를 넘긴다. 미국 동부 시각으로 16:30(마감 16:15 + 15분)이 지난 마지막 날짜다.
    - 그 뒤 날짜 행은 저장하지 않는다.
    - 남은 범위가 주말뿐이면 조회하지 않고 '이미 최신'으로 끝낸다(요일만 · 거래일 달력 없음).
    - 갱신 시간대 · 재시도 제한은 없다.
  - **실패**: 완료 사유 끝에 `시장 불안 지표(VIX)를 갱신하지 못했습니다` 를 붙인다.
    - 서버 로그에는 `status · exit_code · error · as_of_date · settled_through` 가 남는다.
    - error 가 없어도(rc 2) 실패로 친다.
    - 새 기록 행 · 상태 파일은 없다. 다른 단계 결과 · 최종 판정은 그대로다.
    - 작업은 running 에 남지 않는다(기존 6시간 쿨다운은 그대로 · §5-2).
- **시장 판정 날짜**(판정 Q1)
  - PC 화면 API(`GET /market/topn/latest`)만 `compute_topn(market_asof_from_kodex200=True)` 를 부른다.
  - 그래서 `market_context.asof` = 국면 · 지속일 · 기준선과 같은 읽기의 069500 유효 이력 마지막 날짜다. 이력이 없으면 None 이다.
  - 그대로인 것: 최상위 `asof` · 후보 기간 계산 · `_latest_date_in_db` · 다른 호출자(OCI 근거 · 초안 · 「확인 근거」 · ML)는 전체 최신일이다.
  - 「오늘의 투자 점검」 펼친 판정 줄 이름: `KODEX200 기준일 D`(UI-03 '저장 가격 최신일 …'을 대신함)
- **공유 함수 변경**: `scripts/_market_refresh/vix_ingest.py :: run_vix_ingest` 와 `app/market_benchmark_batch.py :: refresh_vix` 에 선택 인자 `max_date` 를 더했다.
  - 넘기지 않으면 예전 코드 경로 그대로다. `refresh_vix` 는 그때 `run_vix_ingest(db_path)` 를 인자 하나로 부른다(시험으로 고정).
  - OCI 배치 · CLI 는 넘기지 않는다.

## 1. 처리한 요구사항

| 요구사항(PLAN · 판정) | 상태 | 근거 |
|---|---|---|
| PLAN §1 VIX 연결(KOSPI 뒤 · NAV 앞 · db_path 명시 · 실패 격리 · 문구 순서) | DONE | `market_refresh_service.py` · `pc_vix_refresh.py` · 시험 단계 순서 |
| 판정 Q2 (b) VIX 만 기존 20초 timeout · 복원 · 실패 뒤 NAV · 작업 종료 · running 해제 | DONE | 시험 timeout · 복원 · 단계 순서(NAV 호출) · 실패 뒤 재실행(쿨다운 0) |
| 판정 Q2 '실패 뒤 다음 수동 갱신' | DONE(running 해제) · 한계 | VIX 만 실패하면 갱신은 completed 라 기존 6시간 쿨다운이 걸린다(§5-2 · 시험으로 고정) |
| 판정 Q3 (a) 문구 + 서버 로그 · 기록 행 없음 · error 없어도 실패 | DONE | `refresh_pc_vix` 로그 · 시험 충돌(rc 2) · 기록 행 3줄 그대로 |
| 판정 Q4 (a) 기존 지연 판정 유지 · 실제 날짜 · 경고 잔류 기록 | DONE(기록은 실제 수집 뒤) | 화면 판정 무변경 · §7 |
| 판정 §3 미확정 자료 저장 가능성 확인 · PC 호출 범위 최소 보완 | DONE | §4-1 · 시험 '기본 경로 영구 저장' · 'PC 경로 제외' · '기준일 넘는 행' |
| PLAN §2 · 판정 Q1 판정 날짜 = 같은 KODEX200 이력 끝 · PC API 만 · 이력 없으면 None | DONE | `market_topn.py` · `api_market_topn.py` · 시험 D1/D2 |
| 판정 Q1 화면 이름 `KODEX200 기준일 D` · OPS-03 시험 수정 | DONE | `KospiHeadline.tsx` · `KospiStatusSurfaces.test.tsx` STEP 4-3 |
| 판정 §3 관찰 항목(basis_end_date · OCI 근거 날짜) 별도 기록 · 중복 등록 없음 | DONE | BACKLOG `DEF-MARKET-CONTEXT-ASOF-MEANING` 안 관찰 줄 · 시험 OCI 근거 문장 = D2 |
| 판정 §4 시험 목록 | DONE | §8 |
| 판정 §4 실제 확인(사용자 갱신 1회 · 읽기 전용) · 결함 2건 닫기 | 대기 | 검증 뒤 |

## 2. 변경된 파일 목록

- `app/pc_vix_refresh.py`: 신규(PC VIX 단계 · 미국 마감 기준일 · 20초 timeout · 문구 · 로그)
- `app/market_refresh_service.py`: 수정(VIX 단계 호출 · 예외 격리 · 문구 합치기)
- `app/market_benchmark_batch.py`: 수정(`refresh_vix(max_date=None)` 선택 인자 · 없으면 예전 호출)
- `scripts/_market_refresh/vix_ingest.py`: 수정(`run_vix_ingest(db_path, max_date=None)` · 있을 때만 주말뿐 범위 조회 생략 · 그 뒤 날짜 제외)
- `app/market_topn.py`: 수정(`compute_topn(market_asof_from_kodex200=False)` 선택 인자)
- `app/api_market_topn.py`: 수정(PC 화면 API 만 True)
- `frontend/app/components/today/KospiHeadline.tsx`: 수정(판정 줄 이름 `KODEX200 기준일 D` · testid `tc-regime-date`)
- `tests/conftest.py`: 수정(autouse — 서비스의 VIX 단계를 기본 '성공 · 문구 없음' stub 으로 · 새 경계 시험은 진짜로 되돌림)
- `tests/test_pc_vix_refresh.py`: 신규(35 시험)
- `tests/test_market_context_kodex200_asof.py`: 신규(5 시험)
- `frontend/app/components/today/TodayFolds.test.tsx` · `KospiStatusSurfaces.test.tsx` · `TodayInvestmentCheckView.test.tsx`: 수정(새 이름 · 앵커)
- 문서
  - 판정 원문(신규 `docs/ai_design/POC5/POC5-11_PC_MARKET_REFRESH_LINK_AND_REFERENCE_DATE_PLAN_DECISION_2026-10-14.md`)
  - PLAN §6 · 이 결과서
  - `docs/PROGRAM_TRUTH.md` · `docs/backlog/BACKLOG.md` · `docs/STATE_LATEST.md`

## 3. 신규 추가된 의존성

없음(`zoneinfo` 는 표준 라이브러리).

## 4. 지시문 외 변경 · 구현 판단

1. **미확정 자료 — 실제 가능함을 확인하고 보완했다**(판정 §3)
   - Yahoo 조회 끝(`period2`)은 PC 로컬(KST) 자정이다(`FinanceDataReader/yahoo/data.py`). 그래서 진행 중인 미국 세션 봉이 들어오는 시간대가 두 가지다.
     - 한국 시각 00:00 ~ 05:00(겨울 06:00)
     - 조회 시작 = 끝일 때 FDR 이 끝을 하루 늘려서, 한국 22:30 ~ 24:00(겨울 23:30 ~ 24:00)
   - 저장은 '마지막 저장일 다음 날부터'만 받는다. 그래서 그 값은 다시 고쳐지지 않는다.
   - 시험 `test_default_path_stores_in_progress_session_and_never_fixes_it` 으로 기본 경로의 가능성을 재현했다.
     - 10-14 새벽 실행으로 10-13 장중 값 30.0 이 저장된다.
     - 다음 날 원천이 31.5 를 줘도 30.0 그대로다.
   - PC 호출은 `max_date`(날짜 기준)로 두 경우를 모두 막는다.
   - 공유 기본 동작 변경 · 달력은 필요 없었다 — 충돌 보고 대상 없음.
2. **주말 오판 방지**(독립 검토 MEDIUM 반영 · `max_date` 경로만)
   - 금요일 값이 이미 저장된 뒤 한국 일요일 아침 ~ 월요일 미국 마감 전에 갱신하면, 조회 범위가 토 · 일뿐이라 빈 응답이 실패(rc 2)로 잡혔다.
   - 그래서 남은 범위가 주말뿐이면 조회하지 않고 '이미 최신'으로 끝낸다.
   - 요일만 보고 미국 거래일 달력은 쓰지 않는다(판정 '새 해외 거래일 달력 금지').
3. **VIX 단계를 서비스 안이 아닌 새 모듈로 뒀다**(PLAN '고칠 파일 = 서비스 하나'와 다름 · PLAN §6 보충). 이유는 두 가지다.
   - 서비스 시험의 기본 stub(conftest)이 경계 시험을 가리지 않게 하려는 것이다(판정 §4).
   - POC5-10 과 같은 방식이다.
4. **마감 기준 16:30 ET**: VIX 지수 장 마감 16:15 에 여유 15분을 더했다. 서머타임 · 표준시는 `zoneinfo("America/New_York")` 가 처리한다(시험 6경계).
5. **`fdr_request_timeout()` 은 전역 함수를 잠시 바꾼다**: VIX 블록 동안 같은 프로세스의 다른 스레드 `requests` 호출에도 'timeout 이 없으면 20초'가 들어간다. 기존 OCI 사용과 같은 성질이고 timeout 을 넣기만 한다.

## 5. 알려진 한계 / 미완성

1. **정비 큐 '시장 불안 지표가 오래되었습니다'는 정상 수집 뒤에도 남을 수 있다**(판정 Q4 · 기존 판정 `vix.as_of_date < kodex.as_of_date` 유지)
   - VIX 는 최대 미국 마감일이다.
   - PC KODEX200 은 한국 장중 · 장 뒤 갱신이면 한국 당일 날짜가 될 수 있다(추정 · ETF 가격 수집이 당일 행을 거르지 않음).
   - 수집 연결 해소와 경고 해소는 실제 수집 뒤 나눠 기록한다(§7).
2. **VIX 만 실패하면 기존 6시간 쿨다운 때문에 바로 다시 갱신할 수 없다**
   - 작업은 running 에 남지 않는다. 그러나 ETF 가 성공하면 갱신은 completed 이고, `last_success_at` 이 기록돼 기존 쿨다운(6시간 · `DEFAULT_COOLDOWN_HOURS`)이 걸린다.
   - 쿨다운은 이번에 바꾸지 않았다(기존 규칙 · 시험으로 고정).
   - 바로 다시 갱신할 수 있어야 하는지는 설계자 판단 대상이다.
3. **미국 평일 휴장 다음 날에는 실패 문구가 날 수 있다**: 요일만 보기 때문이다(달력 없음). 남은 범위가 휴장일 하나뿐이면 빈 응답이 실패로 잡힌다(연 10일 안팎).
4. **PC 수동 명령 `scripts/refresh_market_timeseries.py vix` 는 기본 경로 그대로다**: 한국 새벽 · 저녁에 실행하면 진행 중 세션 값이 저장될 수 있다. OCI 08:10 은 미국 마감 뒤라 해당 없다. 판정 범위(PC 갱신 작업) 밖이다.
5. **관찰(해소 아님 · BACKLOG 한 곳에만)**
   - OCI 근거 문장 'KODEX200 최근 수익률 ({asof} 기준)'은 최상위 `asof`(전체 최신일)를 쓴다(시험으로 D2 확인).
   - 후보 `basis_end_date` 라벨은 전체 최신일인데, 끝 값은 종목마다 자기 마지막 행이다.
6. **같은 카드의 두 KODEX200 날짜**는 행 조건이 같지만 읽기는 따로다(평소 같은 날짜).
   - 기준선 옆(UI-03): `market_risk_reference.kodex200.as_of_date`
   - 판정 줄: `market_context.asof`
7. **PC 의 다른 갱신 단계(ETF 가격 · 보유 개별주 · NAV)는 timeout 이 여전히 없다**(`DEF-FDR-TIMEOUT` PC 잔여 · 판정 '다른 단계 바꾸지 않음').
8. **발견(이번 범위 밖 · 별도 등록 `DEF-PC-MARKET-SCREEN-SLOW-LOAD` · 사용자 요청 2026-10-14)**: 실제 확인 직전 「요즘 잘 오르는 ETF」를 열자 `요청 시간 초과 … /market/topn/latest … (10000ms)` 가 두 번 떴다.
   - 서버 로그상 요청은 모두 200 으로 끝났다.
   - 같은 동시 요청 8개를 3회 재현했다. 시장 TOP N 2개와 확인 근거 1개가 서버에서 차례로 계산돼 각각 4.8 ~ 5.1초 걸렸다.
   - 요인
     - 개발 모드(React StrictMode)에서 화면이 같은 시장 요청을 두 번 보낸다.
     - 백엔드 파일 감시(StatReload)가 CPU 를 늘 40 ~ 80% 쓴다.
     - 화면 요청 시간 제한은 10초다.
   - POC5-11 은 이 계산에 일을 더하지 않았다.

## 6. 다음 검증자(Codex)에게 알릴 점

1. **변이**: backend 14/14 · frontend 1/1 검출. 복원은 원본 내용 쓰기 + `os.utime` · `PYTHONDONTWRITEBYTECODE=1` 로 했다.
   - 서비스: VIX 문구 안 합침 · VIX 예외 격리 없앰 · 서비스가 DB 경로 안 넘김 · VIX 단계를 NAV 뒤로
   - VIX 단계: 20초 timeout 없앰 · 미확정 날짜 제외 안 함 · 마감 16:00 · error 없으면 성공으로
   - 공유 함수: 날짜 거르기 빠짐 · 기본 호출 바뀜 · 주말만 남으면 조회 안 함 빠짐
   - 판정 날짜: 늘 KODEX200 날짜 · 이력 없으면 전체 최신일로 대신 · 화면 API 인자 안 넘김
   - 화면: 판정 줄 이름 되돌림
   - '날짜 거르기 빠짐'은 처음에 놓쳤다. '기준일 넘는 행을 같이 받는' 시험을 더해 잡았다.
2. **독립 검토 반영**(2026-10-14 · 읽기 전용 · 2관점 · 지적 11건 · 모두 반영)
   - MEDIUM(두 관점 같은 지적) 주말 오판: §4-2 로 고치고 주말 시험 3 · 월요일 마감 뒤 시험 1 을 더했다.
   - LOW 쿨다운 서술: §5-2 · 시험으로 고정했다.
   - LOW NAV · 순서 시험: 단계 순서 시험 3을 더했다.
   - LOW ETF · KOSPI 실패와 문구 순서: 시험 3을 더했다.
   - LOW OCI 근거 문장: 시험 1을 더했다.
   - LOW CLI 한계: §5-4 에 적었다.
   - LOW 20초 뜻: §0 · PROGRAM_TRUTH · PLAN · 모듈 설명을 고쳤다.
   - LOW 시작 = 끝 시간대: §4-1 · 모듈 · 가짜 수집기 설명을 고쳤다.
   - LOW PROGRAM_TRUTH: 'PC 수동 갱신 timeout 0' 문장 범위와 POC5-11 문장 위치를 고쳤다.
   - LOW PLAN: '공유 함수 변경 0' 정정을 PLAN §6 보충에 적었다.
3. **OCI 무변경 근거**
   - `scripts/run_oci_market_data_batch.py` · `app/three_push_runtime/*` 변경 0이다.
   - `refresh_vix` 기본 호출이 `run_vix_ingest(db_path)` 인자 하나인 것을 시험으로 고정했다.
   - `market_asof_from_kodex200=True` 를 넘기는 곳은 `app/api_market_topn.py` 하나다(시험 `git grep`).
   - OCI 근거 문장 날짜가 그대로인 것을 시험으로 확인했다.
4. **conftest 기본 stub 범위**: `market_refresh_service.refresh_pc_vix` 모듈 속성만 바꾼다. 새 경계 시험은 진짜 `refresh_pc_vix` 와 가짜 `FinanceDataReader.DataReader` 를 쓴다.

## 7. 사용자 확인 — 실제 수집(검증 뒤)

- **확인 방법**: 사용자가 「요즘 잘 오르는 ETF」 '최신 시장 데이터 갱신'을 1회 누른다. 개발자는 그 뒤 읽기 전용(PC DB `mode=ro` · 화면 API GET)으로 아래를 확인한다.
  - VIX 행 · 실제 기준일(지금 2026-09-11)
  - 완료 사유
  - KODEX200 날짜 · 판정 날짜(`market_context.asof`)
  - 정비 큐 VIX 경고 잔류 여부
- **결함 처리**: `DEF-PC-VIX-REFRESH-MISSING`(수집 연결) · `DEF-MARKET-CONTEXT-ASOF-MEANING`(PC 화면)은 이 확인 뒤 닫는다. 남은 최신성 한계는 따로 적는다.

### 7-1. 실제 수집 결과 (2026-10-14 · 사용자 갱신 1회 · 개발자 읽기 전용 확인 15:41 KST)

- **갱신**: `market_refresh_20261014_062637_d0fa54`(15:26:37 ~ 15:31:38 KST · 300.8초)
  - 상태 completed · 완료 사유 없음(VIX 실패 문구 없음)
  - ETF 1,192/1,192 · 보유 개별주 3/3 · KOSPI 성공
- **VIX**(수집 연결 해소): 2026-09-11 → **2026-10-13**
  - 22행이 들어왔다(09-14 ~ 10-13 · source `FDR_VIX`). 10-13 종가는 15.27 이다.
  - 갱신 시각 15:26 KST = 미국 동부 02:26 이라 `max_date` = 10-13 이다. 미국 10-14 행은 없다(미확정 제외 동작).
- **기록**: 새 VIX 기록 행이 없다. 기록 4줄(ETF 목록 · 가격 · 보유 개별주 · KOSPI)은 예전과 같고, 가장 최근 행은 KOSPI 단계 행이다.
- **시장 판정 날짜**(화면 API GET): `market_context.asof` = **2026-10-14**
  - KODEX200 유효 최신 행(10-14 · 95,015) · `market_risk_reference.kodex200.as_of_date`(10-14) · 거래량 기준일(10-14)과 같다.
  - 최상위 `asof` 도 10-14 다(오늘은 D1 = D2).
  - 국면 하락장 · 4거래일째다.
- **KOSPI**: 2026-10-13 · 화면 판정 정상(지연 0) · 일간 -5.46%
- **경고 잔류**(판정 Q4 · 경고 판정 해소 아님): VIX 10-13 < KODEX200 10-14 라, 정비 큐 '시장 불안 지표가 오래되었습니다 (기준일 2026-10-13)'가 **남는다**.
  - 수집 연결은 해소됐다. 경고는 기존 판정 규칙(`vix < kodex`)의 한계다(§5-1).
- **참고(기존 동작 · 이번 무변경)**: 갱신이 국내 장 마감(15:30) 전에 시작돼, KODEX200 10-14 값(95,015)이 최종 종가가 아닐 수 있다.
  - PC ETF 가격 수집은 매번 돌아보는 기간(`end_date - lookback_days`)부터 다시 받아 덮어쓴다(`app/market_data_fdr.py`).
  - 그래서 다음 갱신 때 최종 값으로 바뀐다.

## 8. 검증 실측 (2026-10-14 · 최종 코드)

- backend: `black --check` · `flake8` · `py_compile` 통과(변경 · 신규 파이썬 9개)
  - `tests/test_pc_vix_refresh.py` 35 passed · `tests/test_market_context_kodex200_asof.py` 5 passed
  - 전체 회귀(마지막 1회): **3487 passed**(2026-10-14 · 405.60초 · 경고 1 = 기존 httpx 사용 중단 안내 · 직전 3447 + 새 시험 40)
  - 그 전 기록: 검토 반영 전 = 3475 passed(430.10초).
- frontend: `npx tsc --noEmit` 종료 0 · `npm run lint` 종료 0 · `npx vitest run` 39파일 463 passed(개수 불변 · 기존 시험 안 이름 · 앵커만 바뀜)
- 변이: backend 14/14 · frontend 1/1(§6-1)
- 시험의 라이브 DB · 보유 파일 접근 0 · 외부 호출 0(가짜 수집기 · 가짜 전송 · 실제 20초 대기 없음)

## 9. git 상태

(보고 직전 실측 · 보고 메시지에 인용)

## 10. 종료 (2026-10-14)

- 사용자가 커밋 · push 를 승인했다(2026-10-14 "네 푸시해주세요"). 코드 · 시험 · 문서 · 종료 기록을 한 커밋으로 push 했다(커밋 번호 = `git log`).
- PC 백엔드 · 화면은 자동 다시 읽기로 이미 반영됐다. OCI pull 은 없다(PC 전용 · OCI 배치 · PUSH 는 기존 호출 그대로).
- 결함: `DEF-PC-VIX-REFRESH-MISSING` 해소(수집 연결) · `DEF-MARKET-CONTEXT-ASOF-MEANING` 해소(PC 화면).
- 남은 것: 정비 큐 VIX 지연 경고(기존 판정 한계) · OCI 근거 날짜 · 후보 끝 날짜 라벨(관찰) · 새 등록 `DEF-PC-MARKET-SCREEN-SLOW-LOAD`(화면 첫 조회 10초 초과 · 사용자 요청 별도 처리).
- 다음 차례 = 설계자(`DEF-PC-MARKET-SCREEN-SLOW-LOAD` 처리 방식 · VIX 지연 경고 규칙 · VIX 만 실패할 때 6시간 쿨다운 여부).

