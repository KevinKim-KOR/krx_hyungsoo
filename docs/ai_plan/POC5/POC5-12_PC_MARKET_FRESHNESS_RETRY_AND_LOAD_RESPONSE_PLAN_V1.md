# POC5-12 개발 PLAN V1 — PC 시장 화면 응답 · VIX 경고 · 실패 재시도 보완

작성 2026-10-14 · 작성자: 개발자(VSCode Claude) · 수신: 설계자
근거: `docs/ai_design/POC5/POC5-12_PC_MARKET_FRESHNESS_RETRY_AND_LOAD_RESPONSE_DESIGN_V1.md`(V1)

```text
STATUS   = PLAN 확정 — 설계자 PASS(2026-10-14 · Q1~Q4 모두 (a) · NAV 결과 포함 · 재시도 완료 결과 표시 보충 · 판정 원문 docs/ai_design/POC5/POC5-12_PC_MARKET_FRESHNESS_RETRY_AND_LOAD_RESPONSE_PLAN_DECISION_2026-10-14.md) → 판정 반영 §7 → 구현
SCOPE    = PC 응답 선택 필드 2개 · 정비 큐 VIX 안내 · VIX 단독 재시도(같은 버튼 · 같은 갱신 경로) · 시장 GET 진행 중 공유 · 늦은 응답 무시 ·
           백엔드 파일 감시 범위 · 화면 오류 덮어쓰기 방지
           새 API 경로 · DB 표 · 스키마 · 의존성 · 외부 조회 · OCI · PUSH 변경 0
MOCKUP   = 불필요(같은 자리 문구 · 버튼 글자만 바뀜 · 새 배치 · 동선 없음)
QUESTION = 4건(§5)
```

## 1. VIX 최신성 안내 (설계 §2)

- **지금**: 정비 큐(`frontend/app/components/today/maintenanceQueue.ts:55-75`)는 `vix.as_of_date < kodex.as_of_date` 면 '시장 불안 지표가 오래되었습니다 (기준일 D)'를 띄운다.
  - 같은 규칙이 「ETF 비교하기」(`JudgmentWorkbenchView.tsx:625-640` · 'VIX stale — 기준일 D (시장 …보다 이전)')와 「개발·실험용」(`DashboardView.tsx:119-134`)에도 있다(§5 Q1).
- **판정 위치(Python 한 곳)**: 기존 마감 함수 `app/pc_vix_refresh.py :: last_settled_us_date` 옆에 `vix_freshness(as_of_date, now_utc)` 를 둔다.
  - E = 마감 기준일. 토 · 일이면 직전 금요일이다.
  - L = D 다음 날부터 E 까지의 평일 수다.
  - 판정
    - `fresh`(D = E)
    - `one_weekday_behind`(L = 1)
    - `update_check`(L ≥ 2)
    - `date_check`(날짜 없음 · 해석 불가 · D > E)
  - 달력은 쓰지 않는다. 기준일 · 종가 · 위험 참고 산식은 바꾸지 않는다.
- **전달(작은 선택 필드)**: PC `GET /market/topn/latest` 의 `market_risk_reference.vix.freshness = {state, compare_date, weekdays_behind}` 다.
  - 붙이는 곳은 응답 조립 `app/api_market_topn_service.py :: build_market_risk_reference_payload` 다(조회 시각 = 요청 시각).
  - 공유 builder `market_risk_reference_service.build_market_risk_reference`(결정 초안 미리보기도 사용)는 그대로다.
  - 모델 `MarketRiskVix` 에 선택 필드 하나를 더한다.
- **화면**(정비 큐 · 같은 자리 · 같은 이동 버튼 '시장 자료 업데이트로')
  - `update_check`: `VIX 자료 업데이트 확인 필요(기준일 D)`
  - `date_check` 또는 판정 필드 없음: `VIX 기준일 확인 필요(기준일 D)`. 날짜가 없으면 `(기준일 확인 불가)`. 예전 `vix < kodex` 로 추측하지 않는다.
  - `fresh` · `one_weekday_behind`: 항목 없음
  - VIX 자료 자체 없음(`availability = unavailable`): 기존 '시장 불안 지표 자료가 없습니다' 그대로
- **첨부 사례 확인**: 10-14 15:41 KST 조회 = 미국 동부 10-14 02:41 → E = 10-13 · D = 10-13 → `fresh` → 경고 없음.

## 2. VIX 만 실패한 뒤 바로 다시 받기 (설계 §3)

- **표식 저장(기존 상태 저장 경계 · 스키마 변경 0)**
  - `market_refresh_state` 표는 이미 `refresh_scope`(PK)로 줄을 나눈다. 지금은 `market_data` 한 줄뿐이다.
  - 같은 표에 `refresh_scope = 'vix_retry'` 한 줄을 쓴다(`app/market_refresh_state_store.py` 함수들에 scope 인자를 더하고, 기본은 지금 값).
  - 뜻: `last_attempt_status` = `needed`(전체 갱신에서 VIX 만 실패) · `running` · `failed`(다시 받기 실패 · 한국어 사유) / 해제 = 줄 삭제
  - PC 를 다시 켜도 남는다. 다시 켤 때 `running` 은 기존과 같이 `failed` 로 바꾼다.
- **표식 세우기 · 해제**(`app/market_refresh_service.py`)
  - 세우기: 전체 갱신이 성공하고 다른 단계 사유가 하나도 없는데 VIX 단계만 실패하면 세운다.
    - 다른 단계 사유 = ETF 목록 · 가격 · KOSPI 사유(`error_summary`) · 보유 개별주 문구
    - VIX 단계 실패 = `refresh_pc_vix` 문구나 예외
  - 해제: 다음 전체 갱신의 VIX 단계가 성공하면 해제한다.
  - 최신성 안내(§1)만 남는 경우에는 세우지 않는다.
- **같은 버튼 · 같은 경로**
  - `GET /market/refresh/status` 응답에 선택 필드 `vix_retry = {needed, status, error_summary, finished_at}` 를 더한다.
  - `POST /market/refresh` 에 선택 인자 `scope=vix` 를 더한다(새 경로 없음 · §5 Q2).
    - 표식이 `needed`/`failed` 이고 전체 갱신 · VIX 다시 받기가 모두 실행 중이 아닐 때만, VIX 단계만 돈다.
    - VIX 단계는 POC5-11 `refresh_pc_vix` 그대로다(20초 · 미확정 날짜 제외 · 실패 격리).
    - 전체 갱신 상태 · `last_success_*` · 건수 · 기록 행은 건드리지 않는다.
  - 중복 방지: 전체 갱신과 VIX 다시 받기는 같은 잠금을 쓴다. 실행 중이면 둘 다 거절한다. 끝나면 대기 · 횟수 제한 없이 다시 누를 수 있다. 자동 반복은 없다.
- **화면**(「요즘 잘 오르는 ETF」 갱신 카드 · `MarketDiscoveryView.tsx` · 같은 자리)
  - 전체 갱신 6시간 대기 중이고 `vix_retry.needed` 면, 버튼 글자를 'VIX 다시 받기'로 바꾸고 `scope=vix` 를 보낸다.
  - 진행 · 결과 줄
    - 실행 중: 'VIX 다시 받는 중…'
    - 성공: 'VIX 다시 받기 완료(기준일 D)'
    - 실패: '확인 필요: 시장 불안 지표(VIX)를 갱신하지 못했습니다'
  - 성공해도 '갱신 완료'(전체)로 부르지 않는다.
  - 대기가 끝났으면 원래 버튼 · 전체 갱신 그대로다.

## 3. 첫 화면 조회 지연 (설계 §4)

**확인한 현재 연결**(측정은 POC5-11 결과서 §5-8 을 출발점으로 쓰고 다시 재현하지 않음)

- **중복 GET**
  - `MarketDiscoveryView.tsx:279-288` · 갱신 뒤 `:337` 이 `useEffect → loadTopn → fetchMarketTopnLatest` 로 시장 TOP N 을 직접 부른다.
  - `reactStrictMode: true`(`frontend/next.config.ts`)라 개발 모드에서 같은 요청이 2개 나간다.
  - 「오늘의 투자 점검」은 `useSharedQuery` 가 이미 진행 중 요청을 공유해 중복이 없다(`lib/api/queryCache.ts:64`).
  - `loadTopn` 은 늦게 온 이전 입력의 응답도 화면 상태에 그대로 쓴다.
- **파일 감시**
  - `start.sh:29` · `start.bat:18` 이 `uvicorn --reload` 를 감시 범위 없이 띄운다. 그래서 저장소 루트 전체를 감시한다.
  - uvicorn 0.52.1 은 `watchfiles` 가 없으면 StatReload 를 쓰고, 0.25초마다 감시 폴더에서 `rglob("*.py")` 를 돈다(`uvicorn/supervisors/statreload.py:49-51`).
  - 그래서 `.venv` · `frontend/node_modules`(452MB) · `state`(2.4GB) · `.git` 를 매번 훑는다. 실제 파이썬 코드는 `app` 267 · `scripts` 50 · `tests` 190 파일이다.
  - 앱이 저장소 안에서 읽는 패키지는 `app` · `scripts` 뿐이다(import 실측).
- **화면 오류 덮어쓰기**: `MarketDiscoveryView` 는 시장 요청이 실패하면 받은 화면 전체를 오류 카드로 바꾼다. 갱신 카드만 남는다.
- **실행 경계**: 두 무거운 GET(`get_market_topn_latest` · `get_holdings_market_evidence_latest`)은 동기 `def` 라 이미 스레드에서 돈다(이벤트 루프를 막지 않음). 같이 오면 CPU 를 차례로 쓴다(측정과 맞음).
- **측정으로 설명되지 않는 점**: 재현 묶음은 4.8 ~ 5.1초였는데 사용자 화면은 10초를 넘었다.
  - 후보 요인
    - 파일 감시 CPU(측정 때 40 ~ 80%)
    - 브라우저의 같은 주소 동시 연결 한도(6개 · 첫 묶음 요청 7개) 대기
    - 화면 이동이 겹쳐 두 화면이 각자 시장 요청
  - 하나로 단정하지 않는다. 아래 보완 뒤 실제 화면 수치로 다시 본다.

**보완**(설계 순서 그대로)

1. **같은 입력의 시장 GET 은 진행 중 요청을 공유한다**(`frontend/lib/api/market.ts :: fetchMarketTopnLatest`).
   - URL 이 같으면 끝날 때까지 같은 약속(Promise)을 돌려준다. 끝나면 지운다(보관 캐시 · 자동 재조회 없음).
   - `loadTopn` 에 순번을 둬서, 입력이 바뀌었거나 화면을 떠난 뒤 늦게 온 응답은 무시한다.
2. **파일 감시 범위**: `start.sh` · `start.bat` 의 uvicorn 에 `--reload-dir app --reload-dir scripts` 를 더한다(코드 수정 자동 다시 읽기 유지 · 그 밖은 감시 안 함).
   - 사용자가 `./start.sh` 로 한 번 다시 켜야 적용된다(§5 Q4).
3. **먼저 받은 화면을 지킨다**: `MarketDiscoveryView` 에서 이미 받은 시장 자료가 있으면, 다시 부르다 실패해도 그 화면을 두고 위에 오류 한 줄만 보인다. 처음부터 못 받았으면 지금처럼 오류 카드다.
4. **그래도 남으면**: 시장 GET 의 대기 · 계산 · DB 읽기 시간을 한 번 나눠 잰다(서버 로그 한 줄 · 개발 때만).
   - 실제 정상 응답이 10초를 넘는 것이 남으면, 시장 TOP N GET 의 화면 제한만 20초로 바꾼다(공통 10초 · VIX 20초와 별개).
   - 이것을 '빨라짐'으로 보고하지 않는다.

**전후 측정 · 보고 구분**: 개발자 측정과 사용자 실제 확인을 나눠 적는다.

| 측정 | 보완 전 | 보완 뒤 |
|---|---|---|
| 화면을 한 번 열 때 서버가 받은 시장 GET 수(서버 접속 기록) | (측정) | (측정) |
| 파일 감시 프로세스 CPU(1분 누적) | (측정) | (측정) |
| 시장 GET 응답 시간 · 시간 초과 여부(사용자 일반 화면 열기) | (측정) | (측정) |

## 4. 바뀌는 파일 · 시험 · 실제 확인

- **backend**
  - `app/pc_vix_refresh.py`(`vix_freshness`)
  - `app/api_market_topn_service.py`(선택 필드)
  - `app/api_market_topn_models.py`
  - `app/market_refresh_state_store.py`(scope 인자)
  - `app/market_refresh_service.py`(표식 · VIX 단독 작업 · 잠금)
  - `app/api_market_topn.py`(`scope=vix` · 상태 필드)
- **frontend**
  - `today/maintenanceQueue.ts`
  - `MarketDiscoveryView.tsx`(버튼 · 진행 줄 · 순번 · 오류 덮어쓰기 방지)
  - `lib/api/market.ts`(진행 중 공유 · `scope`)
  - `lib/api` 형식
  - §5 Q1 이면 `JudgmentWorkbenchView.tsx` · `DashboardView.tsx`
- **실행 스크립트**: `start.sh` · `start.bat`
- **시험(격리 DB · 가짜 수집기 · 고정 시각)**
  - **최신성**: 아래 경우를 모두 본다.
    - 마감 전 · 후
    - 서머타임 · 표준시
    - 토 · 일 · 월요일 아침
    - L = 0 · 1 · 2 이상
    - 날짜 없음 · D > E
    - 첨부 사례(10-14 / 10-13)
    - 판정 필드 없는 응답(추측 안 함)
    - 원래 값 보존
  - **재시도**: 아래 흐름을 모두 본다.
    - VIX 만 실패 → 표식
    - 다른 단계도 실패 → 표식 없음
    - 대기 중 `scope=vix` → VIX 만 호출(ETF · 보유 · KOSPI · NAV 호출 0)
    - 성공 → 해제
    - 재실패 → 유지 · 사유
    - 다시 켜기 → 유지 · `running` → `failed`
    - 중복 클릭 · 전체 갱신과 겹침 → 거절
    - 전체 갱신 시각 · 건수 · 기록 행 보존
    - 최신성 안내만으로 표식 없음
  - **화면**: 아래 동작을 모두 본다.
    - 버튼 글자 · `scope` 전송
    - 같은 입력 GET 1회
    - 입력 변경 · 화면 이동 뒤 늦은 응답 무시
    - 받은 화면 유지
    - 정비 큐 문구 3종
- **필수 검사**: black · flake8 · py_compile · pytest 관련 + 전체 1회 · tsc · eslint · vitest. 변이는 복원 = 내용 쓰기 + utime 으로 한다.
- **실제 확인(사용자)**
  1. `./start.sh` 다시 켜기 1회
  2. 「요즘 잘 오르는 ETF」 · 「오늘의 투자 점검」 일반 열기
     - 시간 초과 반복 여부
     - 정비 큐 VIX 경고 사라짐
  3. VIX 실패는 실제로 만들지 않는다(격리 시험으로만).

## 5. 판정 요청

**Q1. 같은 VIX 지연 규칙이 있는 다른 두 화면**
- 「ETF 비교하기」 'VIX stale — 기준일 D (시장 …보다 이전)' · 「개발·실험용」 같은 문구가 같은 `vix < kodex` 규칙이다.
- 선택지
  - (a) 같은 판정 필드로 함께 고친다(문구는 각 화면 그대로 · 조건만 `update_check` · `date_check`).
  - (b) 정비 큐만 고친다.
- 개발자 권장 = (a)(같은 자료에 화면마다 다른 경고가 나지 않게).

**Q2. VIX 다시 받기 호출 방식**
- 선택지
  - (a) 같은 `POST /market/refresh` 에 명시 인자 `scope=vix` — 화면 버튼 글자와 실제 동작이 늘 일치한다.
  - (b) 인자 없이 서버가 '대기 중 + 표식'이면 자동으로 VIX 만 돈다.
- 개발자 권장 = (a).

**Q3. 'VIX 만 실패'의 범위**
- 표식은 ETF 목록 · 가격(부분 실패 없음) · 보유 개별주 · KOSPI 가 모두 사유 없이 끝나고, VIX 만 실패했을 때만 세운다.
- 선택지
  - (a) 그대로(다른 단계도 실패하면 이번 범위 밖 · 설계 §3)
  - (b) ETF 부분 실패와 겹쳐도 세운다
- 개발자 권장 = (a).

**Q4. 파일 감시 변경 적용**: 실행 스크립트를 고친 뒤 사용자가 `./start.sh` 로 한 번 다시 켜야 적용된다(실행 중 서버는 그대로).
- 선택지
  - (a) 실제 확인 때 사용자가 다시 켠다.
  - (b) 개발자가 확인을 받고 다시 켠다.
- 개발자 권장 = (a).

## 6. 범위 밖

- 새 API 경로 · DB 표 · 스키마 · 의존성(`watchfiles` 설치 포함) · 외부 조회 · 정기 갱신
- OCI · PUSH · 보유 · 원장 · 시세 산식
- 전체 갱신 쿨다운 일반 규칙
- 모든 계산 성능 재설계 · 새 SLA
- 종합 위험 분류 · KOSPI 지수 거래량

## 7. 설계자 판정 반영 (2026-10-14 · PASS · 재제출 없음)

- **Q1 (a)**: 정비 큐 · 「ETF 비교하기」 · 「개발·실험용」 세 화면이 같은 `freshness` 판정을 쓴다.
  - `fresh` · `one_weekday_behind` 는 경고 없음이다.
  - `update_check` 는 `VIX 자료 업데이트 확인 필요(기준일 D)`, `date_check` 와 판정 필드 없음은 `VIX 기준일 확인 필요(기준일 D)` 다.
  - 옛 '(시장 …보다 이전)' · 국내 날짜 비교 설명은 지운다.
  - 실제 VIX 기준일 · 값 · '자료 없음' 항목은 그대로다. 저장된 초안 · 원장 · 과거 재현은 건드리지 않는다.
- **Q2 (a)**: `POST /market/refresh` 의 `scope` 는 다음과 같이 나뉜다.
  - 생략: 원래 전체 갱신
  - `scope=vix`: 표식(`needed` · `failed`)과 실행 중 상태를 같은 잠금(`_service.lock`) 안에서 확인한 뒤 VIX 만 돈다.
  - 대상이 없으면 `not_needed`(실행 0)다.
  - 알 수 없는 scope 는 422(실행 0)다.
- **Q3 (a) + NAV**: '다른 단계 실패 없음'에 NAV 실제 결과를 포함한다.
  - `refresh_nav_universe` 예외가 없고 반환 `status == "ok"` 일 때만 성공이다. 평소 2026-10-14 실측은 `ok` · 1,176/1,176 이다. `partial` · `unavailable` · 예외는 다른 단계 실패로 본다.
  - 표식은 가장 최근 전체 갱신 결과에 맞춘다.
    - VIX 만 실패하면 `needed` 다.
    - 그 밖(VIX 성공이거나, 다른 단계도 실패)이면 행을 `cleared`(필요 없음)로 바꿔 예전 표식으로 재시도를 열지 않는다.
  - NAV 수집 방식 · completed/failed 판정은 바꾸지 않는다.
- **Q4 (a)**: 검증 뒤 실제 확인 때 사용자가 `./start.sh` 로 한 번 다시 켠다. 진행 중 갱신이 없을 때 하고, 그 뒤 코드 수정 자동 다시 읽기를 확인한다.
- **재시도 결과 표시(판정 §3)**: `vix_retry` 행은 아래 상태를 오간다.
  - `needed` → `running` → `completed`(needed=false · VIX 기준일 · 끝난 시각 · 재시도 id) 또는 `failed`(needed=true · 한국어 사유)
  - 다시 켤 때 `running` 은 `failed` 로 바꾼다.
  - 화면은 POST 가 준 재시도 id 와 상태 응답의 `vix_retry.refresh_id` 가 같고 끝난 상태인지로 결과를 읽는다. 그래서 첫 상태 조회 전에 끝나도 'VIX 다시 받기 완료(기준일 D)'를 볼 수 있다.
  - 전체 갱신 행 · 마지막 성공 시각 · 건수 · 기록 행에는 섞지 않는다.
- **조회 지연(판정 §4)**: 시장 GET 은 진행 중에만 공유하고, 성공 · 실패 · timeout 뒤 지운다.
  - 같은 입력 재조회가 실패하면 받은 자료와 실제 기준일을 두고 오류 한 줄을 보인다.
  - 입력을 바꾼 뒤 실패하면 결과 영역을 숨기고 오류 카드를 보인다(이전 조건 자료를 새 결과처럼 보이지 않음).
  - 늦은 응답 · 화면을 떠난 뒤 응답은 무시한다.
- **검사 보충**: NAV 실패 · 이전 표식 뒤 다른 단계 실패 · 빠른 재시도 완료 · GET 실패/timeout 뒤 재요청 · 조건 변경 뒤 이전 자료 오인 방지를 시험에 넣는다.


## 8. 구현 중 보충 (2026-10-14 · 결과서 §4)

- **해제 방식**: §2 본문의 '해제 = 줄 삭제' 대신 §7(판정 반영)대로 행 상태를 `cleared` 로 바꾼다.
- **KOSPI 예외**: KOSPI 단계가 예외로 끝나면 기존 코드는 `error_summary` 를 비워 둔다. 그래서 '다른 단계 실패 없음'에 KOSPI 반환 `status == "ok"`(예외면 실패)를 따로 더했다.
- **새 파일 4**(§4 목록 밖 · KS-10 · 공통화)
  - `app/market_refresh_vix_retry.py`: 서비스가 650줄을 넘지 않게 'VIX 다시 받기'를 나눴다.
  - `frontend/app/components/useMarketVixRetry.ts` · `useMarketTopnLoad.ts`: 시장 화면의 새 책임(버튼 흐름 · 조회 순번 · 받은 화면 유지)을 hook 으로 나눴다.
  - `frontend/lib/vixFreshness.ts`: 세 화면 공통 문구.
- **거절 상태값**: 'VIX 다시 받기' 실행 중 거절은 `vix_retry_running`(전체 갱신 중 거절 `running` 과 구분 · 화면이 '갱신 완료'로 읽지 않게).
- **다시 읽기 입력**: 갱신 · 다시 받기 뒤 다시 읽기는 늘 지금 입력으로 한다(갱신 중 필터를 바꾸면 클릭 때 조건으로 읽던 기존 동작 정정 · 판정 §4).
- **「개발·실험용」 시장 카드 VIX 줄**: 같은 화면의 옛 규칙(`vix < kodex` · '⚠ stale')도 같은 판정으로 바꿨다(판정 Q1 · 세 화면 같은 판정).
