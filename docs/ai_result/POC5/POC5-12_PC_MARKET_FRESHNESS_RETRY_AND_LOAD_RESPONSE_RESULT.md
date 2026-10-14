# POC5-12 개발 결과서 — PC_MARKET_FRESHNESS_RETRY_AND_LOAD_RESPONSE (PC 시장 화면 응답 · VIX 경고 · 실패 재시도 보완)

작성 2026-10-14 · 작성자: 개발자(VSCode Claude) · 수신: 검증자(Codex)

```text
STATUS        = IMPLEMENTED_VERIFIED_CLOSED(2026-10-14) — 검증자 r1 REJECTED(2026-10-14 · P2 1건: 이전 재시도의 늦은 상태 응답이 새 재시도 진행을 끝냄) → 고침 · 같은 종류 3곳 함께(§4-14 · §4-15) → **검증자 r2 VERIFIED(2026-10-14 · 위험 NONE · 범위 폭주 NONE · 프론트 517 · r1 독립 재현 2 · 백엔드는 r1 검증본과 해시 같아 회귀 재실행 없음)** → 사용자 일반 화면 확인(2026-10-14 · §7-1) → 사용자 커밋 · push 승인 → 종료(§10)
STEP_ID       = POC5-12 PC 시장 화면 응답 · VIX 경고 · 실패 재시도 보완
DESIGN        = docs/ai_design/POC5/POC5-12_PC_MARKET_FRESHNESS_RETRY_AND_LOAD_RESPONSE_DESIGN_V1.md (V1)
DECISION      = docs/ai_design/POC5/POC5-12_PC_MARKET_FRESHNESS_RETRY_AND_LOAD_RESPONSE_PLAN_DECISION_2026-10-14.md (PLAN PASS · Q1~Q4 (a) · NAV 결과 포함 · 재시도 완료 결과 표시 보충)
PLAN          = docs/ai_plan/POC5/POC5-12_PC_MARKET_FRESHNESS_RETRY_AND_LOAD_RESPONSE_PLAN_V1.md (V1 · PASS · 판정 반영 §7)
BASE_COMMIT   = f950ebfa (POC5-11 종료 커밋)
SCOPE         = PC 화면 응답 선택 필드 2개(VIX freshness · 상태 vix_retry) · POST /market/refresh 선택 인자 scope=vix · 세 화면 VIX 안내 ·
                「요즘 잘 오르는 ETF」 같은 버튼 'VIX 다시 받기' · 시장 GET 진행 중 공유 · 늦은 응답 무시 · 받은 화면 유지 · 실행 스크립트 파일 감시 범위
                새 API 경로 · DB 표 · 스키마 · 의존성 · 외부 조회 · OCI · PUSH 변경 0
REVIEW        = 독립 검토 1회(읽기 전용 · 2관점 · 2026-10-14) — MEDIUM 1 · LOW 4 → 모두 반영(§6-2) · r1 고침 검토 1회(Workflow · 3관점 · 반박 검증 · 지적 5 → 모두 반영 · §4-15)
CHECKS        = §8
```

## 0. 요약

- **VIX 최신성 안내**(설계 §2 · 판정 Q1)
  - 판정은 Python 한 곳 `app/pc_vix_refresh.py :: vix_freshness(as_of_date, now_utc)` 이다. POC5-11 마감 함수 `last_settled_us_date` 를 그대로 쓴다.
    - E = 조회 시각의 미국 동부 마감 기준일(16:30 ET 이후면 그날)이다. 토 · 일이면 직전 금요일로 돌린다.
    - L = 저장 기준일 D 다음 날부터 E 까지의 평일 수다(달력 없음).
    - `fresh`(D = E) · `one_weekday_behind`(L = 1) · `update_check`(L ≥ 2) · `date_check`(날짜 없음 · 해석 불가 · D > E)
  - PC `GET /market/topn/latest` 응답 조립(`api_market_topn_service.build_market_risk_reference_payload`)만 `market_risk_reference.vix.freshness = {state, compare_date, weekdays_behind}` 를 붙인다.
    - 공유 builder(`market_risk_reference_service.build_market_risk_reference` · 결정 초안 미리보기)는 그대로다.
    - 기준일 · 종가 · 위험 참고 산식은 그대로다(시험으로 고정).
  - 화면 세 곳이 같은 문구 함수 `frontend/lib/vixFreshness.ts :: vixFreshnessNotice` 를 쓴다(KODEX200 날짜 비교 없음 · 미국 마감 · 서머타임 재계산 없음).
    - 「오늘의 투자 점검」 정비 큐(같은 자리 · `heavy` · '시장 자료 업데이트로')
    - 「ETF 비교하기」 「확인 필요」 탭
    - 「개발·실험용」 예외 목록과 시장 카드 VIX 줄
  - 문구
    - `update_check`: `VIX 자료 업데이트 확인 필요(기준일 D)`
    - `date_check` · 판정 필드 없음: `VIX 기준일 확인 필요(기준일 D)`(날짜 없으면 `기준일 확인 불가`)
    - `fresh` · `one_weekday_behind`: 없음
    - VIX 자료 없음: 기존 항목 그대로
  - 지운 것: '시장 불안 지표가 오래되었습니다' · 'VIX stale — 기준일 D (시장 …보다 이전)' · 국내 날짜 비교 설명 · '⚠ stale — 현재 시장값 아님'
  - 실행 중 서버 실측(2026-10-14 · 읽기 전용 GET): VIX 10-13 · KODEX200 10-14 → `fresh`(E = 10-13) → 첨부 사례의 경고가 사라진다.
- **VIX 만 실패한 뒤 바로 다시 받기**(설계 §3 · 판정 Q2 · Q3 · §3)
  - 표식 · 결과는 기존 `market_refresh_state` 표의 `refresh_scope = 'vix_retry'` 행이다(스키마 변경 0). 상태값은 needed · running · completed · failed · cleared 다.
  - 전체 갱신 끝에 표식을 맞춘다(서비스 잠금 안 · 기록 직후).
    - VIX 만 실패 → needed
    - '다른 단계 실패 없음' = ETF 목록 성공 · 가격(성공 > 0 · 사유 없음) · KOSPI `status == "ok"`(예외 포함) · 보유 개별주 문구 없음 · **NAV 예외 없음이고 반환 `status == "ok"`**
    - 그 밖(VIX 성공 · 다른 단계도 실패)이면, 예전 표식이 있을 때 `cleared` 로 바꾼다(예전 표식으로 재시도를 열지 않음). 표식이 없으면 새 행을 만들지 않는다.
  - `POST /market/refresh?scope=vix` 는 같은 잠금 안에서 표식(needed · failed)과 실행 중을 확인한 뒤 VIX 단계(`refresh_pc_vix` · POC5-11 그대로)만 돈다.
    - 대상 없음 → `not_needed`(실행 0) · 알 수 없는 scope → 422(실행 0) · 생략 → 원래 전체 갱신
    - 6시간 대기와 무관하다. 대기 · 횟수 제한 · 자동 반복은 없다.
    - 전체 갱신과 다시 받기는 서로 실행 중이면 거절한다. 전체 갱신이 돌면 `running`, 다시 받기가 돌면 `vix_retry_running`(재시도 id)이다. 화면은 `vix_retry_running` 을 받으면 그 다시 받기를 이어서 보인다('갱신 완료'로 읽지 않음).
    - 결과는 그 행에만 쓴다: completed(VIX 저장 기준일 · 끝난 시각 · 재시도 id) 또는 failed(한국어 사유 · needed 유지)
    - 전체 갱신 상태 · 마지막 성공 시각 · 건수 · 기록 행은 그대로다(시험으로 고정).
    - 끝나기 전 서버가 다시 켜지면 running → failed(사유 = VIX 실패 문구 · 다시 누를 수 있음)
  - `GET /market/refresh/status` 에 선택 필드 `vix_retry = {needed, status, refresh_id, started_at, finished_at, error_summary, vix_as_of_date}`(행 없으면 null)를 더했다.
  - 화면(「요즘 잘 오르는 ETF」 같은 갱신 버튼)
    - 화면을 열 때 상태를 한 번 읽는다. 전체 갱신이 끝난 상태 응답도 받아 맞춘다.
    - 6시간 대기 중이고 `vix_retry.needed` 면 버튼 글자가 'VIX 다시 받기'로 바뀌고 `scope=vix` 를 보낸다. 대기 중 여부는 받은 남은 초로 타이머를 걸어, 화면을 연 채 대기가 끝나면 원래 버튼으로 돌아온다.
    - POST 가 준 재시도 id 와 상태 응답의 `vix_retry.refresh_id` 가 같고 끝난 상태인지로 결과를 읽는다(첫 상태 조회 전에 끝나도 보임).
    - 'VIX 다시 받기' 상태 확인을 멈추면(결과 확인 · 상한 · 새 재시도 · 화면 떠남) 그 전에 보낸 상태 요청의 응답(성공 · 오류)은 버린다(세대). 받은 상태는 요청 순번으로 반영해 늦게 온 오래된 응답이 더 새 상태(버튼 글자 · 대기 시간)를 덮지 않는다(검증자 r1 · §4-14).
    - 전체 갱신 상태 확인은 세대만 쓴다: 멈춘 뒤(결과 확인 · 새 갱신 · 화면 떠남) 온 보통 확인의 응답 · 오류는 버린다. 상한(120회) 뒤 마지막 조회는 세대를 보지 않는다(기존 동작 · §4-14). 버튼을 누르고 POST 응답 전에 화면을 떠나면, 늦게 온 응답은 상태 확인을 새로 열지 않는다(§4-15).
    - 진행 · 결과 줄: 'VIX 다시 받는 중…' / 'VIX 다시 받기 완료(기준일 D)' / '확인 필요: 시장 불안 지표(VIX)를 갱신하지 못했습니다'
    - 성공하면 시장 읽기를 무효화하고 TOP N 을 다시 읽는다. '갱신 완료'(전체)로 부르지 않는다.
    - 대기가 끝났거나 표식이 없으면 원래 버튼 · 전체 갱신 그대로다.
- **조회 지연**(설계 §4 · PLAN §3 · 판정 §4)
  - `fetchMarketTopnLatest` 는 같은 주소면 끝날 때까지 같은 요청을 돌려준다. 성공 · 실패 · 시간 초과 뒤 바로 지운다(보관 캐시 · 자동 재조회 없음).
  - 조회는 hook `useMarketTopnLoad` 가 맡는다. 순번을 둬서 늦게 온 이전 요청 응답을 무시한다.
  - 갱신 · 'VIX 다시 받기'가 끝난 뒤 다시 읽기는 그 전에 보낸 같은 주소 요청에 붙지 않고 새로 보낸다(`forgetMarketTopnInflight` · §4-15).
  - 갱신 · 'VIX 다시 받기'가 끝난 뒤 다시 읽기는 늘 지금 입력(필터 · 정렬)으로 읽는다(`reloadLatest`). 예전에는 상태 확인 반복이 클릭 때 함수를 쥐고 있어서, 갱신 중 필터를 바꾸면 끝난 뒤 옛 조건 자료가 새 체크 상태 아래 보일 수 있었다(기존 결함 · 독립 검토 지적 · §4-11).
  - 같은 입력 재조회가 실패하면 받은 자료를 두고 위에 한 줄을 보인다: `시장 자료를 다시 불러오지 못해 이전에 받은 자료(기준일 D)를 표시합니다: <오류>`
  - 입력을 바꾼 뒤 실패하면 결과 영역을 숨기고 오류 카드다(이전 조건 자료를 새 결과처럼 보이지 않음).
  - `start.sh` · `start.bat` 의 uvicorn 에 `--reload-dir app --reload-dir scripts` 를 더했다(코드 수정 자동 다시 읽기 유지). 사용자가 `./start.sh` 로 한 번 다시 켜야 적용된다.
  - 개발자 측정(§3-1): 화면을 한 번 열 때 시장 TOP N GET 2 → 1 · 응답 2.6 ~ 2.7초 → 1.25초 · 파일 감시 CPU 79% → 5%(빈 앱 · 같은 조건). 사용자 실제 화면 수치는 다시 켠 뒤 확인한다(§7).

## 1. 처리한 요구사항

| 요구사항(PLAN · 판정) | 상태 | 근거 |
|---|---|---|
| PLAN §1 · 판정 Q1 (a) VIX 판정 Python 한 곳 · 미국 마감 기준 · 주말 직전 금요일 · 평일 수 · 4상태 | DONE | `pc_vix_refresh.vix_freshness` · 시험 16경우 |
| PLAN §1 PC 응답 선택 필드(응답 조립만 · 공유 builder 무변경 · 원래 값 보존) | DONE | `api_market_topn_service` · 시험 2 |
| 판정 Q1 세 화면 같은 판정 · 문구 · 옛 '(시장 …보다 이전)' 제거 · 자료 없음 항목 유지 · 판정 없으면 추측 안 함 | DONE | `lib/vixFreshness.ts` · 정비 큐 · 「ETF 비교하기」 · 「개발·실험용」(예외 목록 + 시장 카드 VIX 줄 · §4-4) · 시험 |
| PLAN §2 표식 저장(기존 표 · scope 인자 · 스키마 0 · 다시 켜면 running → failed) | DONE | `market_refresh_state_store` scope 인자 · `_hydrate_from_sqlite` · 시험 |
| 판정 Q3 (a) + NAV 결과 포함 · 최근 전체 갱신에 맞춤(needed / cleared) | DONE | `vix_only_failure` · `sync_vix_retry_after_full_refresh` · 다른 단계 실패 8경우 × (표식 없음 · 이전 표식 해제) |
| 판정 Q2 (a) 같은 POST `scope=vix` · 생략 = 전체 · 대상 없음 not_needed · 알 수 없는 scope 422 · 같은 잠금 | DONE | `api_market_topn.post_market_refresh` · `market_refresh_vix_retry.start_vix_retry_job` · 시험 |
| PLAN §2 VIX 만 호출 · 전체 갱신 상태 · 시각 · 건수 · 기록 행 보존 · 중복 · 겹침 거절 · 대기 · 횟수 제한 없음 | DONE | 시험(호출 = ['vix'] · 상태 · 행 · 기록 같음 · 중복 · 겹침(`vix_retry_running`) · 재실패 뒤 재시도) |
| 판정 §3 재시도 결과 표시(id 일치 · 빠른 완료) · 전체 갱신 행과 섞지 않음 · 현재 재시도 결과만(이전 재시도의 늦은 응답 무시 · 검증자 r1) | DONE | 상태 필드 · `useMarketVixRetry` · 시험(다른 id 무시 · 빠른 완료 · 늦은 이전 응답 7 — 검증자 재현 2 · 같은 종류 5) |
| PLAN §2 화면 버튼 글자 · scope 전송 · 진행 · 결과 줄 · 성공해도 '갱신 완료' 아님 · 대기 끝나면 원래 버튼 | DONE | `MarketDiscoveryView` · `useMarketVixRetry` · 시험 10 + 검토 반영 3(거절 인계 2 · 화면을 연 채 대기 만료 1) |
| PLAN §3 보완 1 · 판정 §4 시장 GET 진행 중 공유 · 성공 · 실패 · timeout 뒤 지움 | DONE | `lib/api/market.ts` · 시험 6 · 화면 StrictMode 시험(서버 GET 1) |
| PLAN §3 보완 1 · 판정 §4 늦은 응답 무시 | DONE | 순번 · 시험(StrictMode 이중 실행 순서 뒤집기) · 갱신 중 필터 변경 뒤 다시 읽기 = 새 조건(시험 · §4-11) |
| PLAN §3 보완 3 · 판정 §4 받은 화면 유지 · 입력 변경 뒤 실패는 오류 카드 | DONE | `useMarketTopnLoad` · 시험 2 |
| PLAN §3 보완 2 · 판정 Q4 (a) 파일 감시 범위 | DONE | `start.sh` · `start.bat` · 사용자 서버 2026-10-14 18:00 새 감시 범위로 다시 켜짐(ps 실측) · §3-1 측정 |
| PLAN §3 보완 4(그래도 남으면 시간 나눠 재기 · 20초) | SKIPPED(조건 미도래) | 개발자 측정에서 시장 GET 1.25초 · 사용자 실제 화면 확인 뒤 판단(§7) |
| PLAN §3 전후 측정 · 개발자 / 사용자 구분 | PARTIAL | 개발자 측정 · 다시 켠 사용자 서버의 파일 감시 CPU 실측 완료(§3-1) · 사용자 일반 화면 확인(시간 초과 · VIX 경고)은 남음(§7) |
| 판정 '검사 보충'(NAV 실패 · 이전 표식 뒤 다른 단계 실패 · 빠른 완료 · GET 실패/timeout 뒤 재요청 · 조건 변경 뒤 오인 방지) | DONE | §8 시험 목록 |

## 2. 변경된 파일 목록

- backend
  - `app/pc_vix_refresh.py`: 수정(`vix_freshness`)
  - `app/api_market_topn_service.py`: 수정(`_now_utc` · PC 응답 조립에 `freshness`)
  - `app/api_market_topn_models.py`: 수정(`MarketRiskVixFreshness` · `MarketRiskVix.freshness` · `MarketRefreshVixRetry` · 상태 응답 `vix_retry` · 시작 응답 상태 주석 `not_needed`)
  - `app/market_refresh_state_store.py`: 수정(`VIX_RETRY_SCOPE` · 함수 4개에 `scope` 인자 · 기본은 지금 값)
  - `app/market_refresh_service.py`: 수정(NAV · KOSPI 실제 결과 · `vix_only_failure` · 표식 맞추기 호출 · 다시 켤 때 정규화 · 시험 초기화 · 전체 갱신 시작 가드)
  - `app/market_refresh_vix_retry.py`: **신규**(표식 맞추기 · 상태 조회 · 다시 받기 시작 · 실행 — §4-3)
  - `app/api_market_topn.py`: 수정(`scope` 선택 인자 · 상태 응답 `vix_retry`)
- frontend
  - `frontend/lib/api/market.ts`: 수정(형식 · 진행 중 공유 · 끝난 뒤 다시 읽기용 `forgetMarketTopnInflight` · `postMarketRefresh(scope?)` · `not_needed` · `vix_retry_running`)
  - `frontend/lib/vixFreshness.ts`: **신규**(세 화면 공통 문구 — §4-3)
  - `frontend/app/components/useMarketVixRetry.ts`: **신규**('VIX 다시 받기' 흐름 hook — §4-3)
  - `frontend/app/components/useMarketTopnLoad.ts`: **신규**(시장 TOP N 조회 · 순번 · 받은 화면 유지 · 최신 입력으로 다시 읽기 hook — §4-3)
  - `frontend/app/components/MarketDiscoveryView.tsx`: 수정(두 hook 연결 · 버튼 글자 · 진행 줄 · 오류 한 줄 · 거절 인계 · 전체 갱신 상태 확인 세대)
  - `frontend/app/components/today/maintenanceQueue.ts` · `JudgmentWorkbenchView.tsx` · `DashboardView.tsx`: 수정(공통 문구)
  - `frontend/vitest.setup.ts`: 수정(진행 중 공유 초기화 — 테스트 사이 누수 방지)
- 실행 스크립트: `start.sh` · `start.bat`(CRLF 유지): 수정 · `docs/README.md` 수동 실행 명령: 수정(사용자 결정 · §7-1)
- 시험
  - `tests/test_market_vix_retry.py`: **신규**(49)
  - `frontend/lib/vixFreshness.test.ts`(7) · `frontend/lib/api/marketTopnInflight.test.ts`(6) · `frontend/app/components/today/maintenanceQueueVix.test.ts`(5) · `frontend/app/components/MarketDiscoveryVixRetry.test.tsx`(30): **신규**
  - `frontend/app/components/JudgmentWorkbenchView.test.tsx`(+3) · `DashboardView.test.tsx`(+3 · 기존 1 수정): 수정
  - `frontend/app/components/KospiStatusSurfaces.test.tsx` · `TodayInvestmentCheckView.test.tsx`: 수정(옛 문구 · 판정 없는 자료 → 서버 판정 자료)
- 문서
  - 판정 원문(신규 `docs/ai_design/POC5/POC5-12_..._PLAN_DECISION_2026-10-14.md`) · 설계서(신규 · 수신본)
  - PLAN V1(**신규** · 판정 반영 §7 · 구현 중 보충 §8) · 이 결과서(신규)
  - `docs/PROGRAM_TRUTH.md` · `docs/backlog/BACKLOG.md` · `docs/STATE_LATEST.md`

## 3. 신규 추가된 의존성

없음.

### 3-1. 전후 측정(개발자 · 2026-10-14)

| 측정 | 보완 전 | 보완 뒤 | 방법 |
|---|---|---|---|
| 「요즘 잘 오르는 ETF」를 한 번 열 때 서버가 받은 시장 TOP N GET | 2건(2회 측정 모두) | 1건(5회 측정 모두 · 검토 반영 뒤 1회 · 다시 켠 서버 + 최종 코드 2회 포함) | 실행 중 사용자 서버(3000 · 8000)를 headless Chrome 으로 열고 메뉴 클릭 · CDP 네트워크 기록 · GET 만 · 쓰기 요청 0 |
| 같은 열기의 시장 TOP N 응답 시간 | 2,659 · 2,606 / 2,701 · 2,655ms(동시 2건) | 1,252 / 1,247 / 1,267ms · 다시 켠 서버 + 최종 코드 1,192 / 1,178ms(2026-10-14 20:25) | 같은 방법 · 첫 화면(오늘의 투자 점검) 요청이 끝난 뒤 클릭 |
| 같은 열기의 갱신 상태 GET | 0건 | 2건(개발 모드 이중 실행 · 3 ~ 5ms) | 같은 방법 — 화면을 열 때 상태 1회 읽기(§4-5) |
| 파일 감시 프로세스 CPU(60초 누적) | 47.66초(약 79%) | 3.17초(약 5%) | 같은 시각 · 같은 저장소 · 빈 앱(`uvicorn --reload` 감시만 비교) · 감시 범위 없음 vs `--reload-dir app --reload-dir scripts` |
| 실행 중 사용자 서버의 파일 감시 프로세스 CPU(60초) | 44.96초(약 75% · 누적 1,160분 · 예전 명령) | 5.26초(약 9% · 2026-10-14 20:22 ~ 20:23 · 18:00 새 감시 범위로 다시 켠 서버 pid 10969) | `ps` 누적 CPU 시간 2회 |

- 응답 시간은 개발자 측정이다. 사용자 일반 화면의 시간 초과 여부는 다시 켠 뒤 확인한다(§7). '빨라짐'의 근거로 쓰지 않는다.
- 측정 스크립트 · 원본 출력은 개발자 scratchpad(저장소 밖)에만 있다.

## 4. 지시문 외 변경 · 구현 판단

1. **표식 해제 = 행 삭제 대신 `cleared` 상태**: PLAN §2 본문은 '해제 = 줄 삭제'였으나 판정 §3 · PLAN §7(판정 반영)이 `cleared`(필요 없음)로 바꾸는 것을 정했다. §7 을 따랐다.
2. **KOSPI 예외 경로를 '다른 단계 실패'에 넣었다**: KOSPI 단계가 예외로 끝나면 기존 코드는 기록 행만 남기고 `error_summary` 를 비워 둔다. 그대로면 'VIX 만 실패'로 잘못 볼 수 있어 `kospi_ok`(반환 `status == "ok"` 일 때만 참)를 판정에 더했다. 완료 사유 · 기록 행 · 최종 판정은 그대로다.
3. **새 파일 4개(KS-10 · 공통화)**
   - `app/market_refresh_vix_retry.py`: 서비스 파일이 727줄로 백엔드 핵심 모듈 650줄 기준을 넘어 나눴다(지금 서비스 576 · 새 모듈 200 · 기준 커밋 서비스 533). 잠금 · 상태 · `refresh_pc_vix` 는 서비스 모듈 속성으로 부른다(지연 import · 순환 없음 · 시험 교체가 같은 통로).
   - `frontend/app/components/useMarketVixRetry.ts`(258줄) · `useMarketTopnLoad.ts`(81줄): 시장 화면의 새 책임('VIX 다시 받기' 흐름 · 조회 순번 · 받은 화면 유지)을 hook 으로 뺐다. 화면은 연결 · 버튼 글자 · 줄 표시만 한다(§5-7).
   - `frontend/lib/vixFreshness.ts`: 세 화면이 같은 판정 · 문구를 쓰게 한 곳에 두었다(React 없음 · lib → components 의존 0).
4. **「개발·실험용」 시장 카드 VIX 줄도 바꿨다**: 같은 화면 예외 목록 외에 시장 카드 `VixLine` 이 같은 옛 규칙(`vix < kodex`)으로 '⚠ stale — 현재 시장값 아님'을 띄웠다. 판정 Q1(세 화면 같은 판정 · 추측 금지)에 따라 같은 함수로 바꾸고 표시는 '⚠ 업데이트 확인 필요' / '⚠ 기준일 확인 필요'로 했다. 「요즘 잘 오르는 ETF」 시장 위험 참고 카드의 '국내·미국 시장의 마지막 확인 거래일은 다를 수 있습니다' 는 경고가 아닌 중립 안내라 그대로 뒀다.
5. **화면을 열 때 갱신 상태를 한 번 읽는다**: 6시간 대기 · 표식을 알아야 버튼 글자를 정할 수 있어서다(가벼운 GET · 개발 모드에서 2건). 못 읽으면 원래 버튼 그대로다. 전체 갱신 화면 상태(idle 등)는 바꾸지 않았다.
6. **정비 큐 ⓘ 사유 문장을 새로 썼다**(실제 값만 · 국내 날짜 비교 없음)
   - `update_check`: `시장 불안 지표(VIX) 저장 기준일 D · 미국 장 마감 기준 비교일 E · 그 사이 평일 L일. 미국 평일 휴장은 따로 거르지 않으므로 장애로 단정하지 않고 업데이트를 확인할 대상으로 봅니다.`
   - `date_check`: `시장 불안 지표(VIX) 저장 기준일(D)을 미국 장 마감 기준 비교일(E)과 맞춰 볼 수 없습니다.`
7. **'VIX 다시 받기' 상태 확인**: 4초마다 상태를 읽는다(전체 갱신과 같은 간격 · 같은 8분 상한). 상태 GET 이 한 번 실패해도 멈추지 않고 다음 차례에 다시 읽는다(전체 갱신 polling 은 첫 실패에서 멈춤 · 이번에 바꾸지 않음).
8. **결과 줄 정리**: 'VIX 다시 받기' 결과 줄은 다음 전체 갱신을 시작하면 비운다(전체 갱신 진행 줄을 가리지 않게).
9. **같은 입력 재조회 중 화면**: 기존처럼 '불러오는 중...' 화면을 거친다. 실패하면 받은 자료로 돌아가고 오류 한 줄을 보인다.
10. **변이로 찾은 쓸모없는 줄을 지웠다**: '화면을 떠날 때 순번 올리기'는 변이로 바꿔도 시험이 그대로였다. 떠난 화면의 갱신은 React 가 버리고, 개발 모드 이중 실행은 다음 조회가 순번을 올리므로 결과를 바꾸지 못한다. 그래서 지웠다(§6-1).
11. **기존 결함을 같이 고쳤다 — 갱신 뒤 다시 읽기가 옛 입력**(독립 검토 MEDIUM): 전체 갱신 상태 확인 반복(`setInterval`)은 클릭 때 만든 함수를 쥔다. 그래서 갱신 중 필터를 바꾸면, 갱신이 끝난 뒤 다시 읽기가 클릭 때 조건으로 서버를 불러 옛 조건 자료가 새 체크 상태 아래 보였다(POC5-12 전부터 있던 동작). 판정 §4('이전 조건 자료를 새 결과처럼 보이지 않음')에 걸려, 다시 읽기를 늘 지금 입력으로 하게 고쳤다(`reloadLatest` · ref).
12. **거절 상태값 `vix_retry_running` 을 더했다**(독립 검토 LOW): 처음에는 'VIX 다시 받기' 실행 중 거절도 `running` 이었다. 그러면 화면은 전체 갱신이 도는 줄 알고 상태를 읽다가, 예전 전체 갱신의 completed 를 받아 '갱신 완료'를 띄우고 다시 읽었다(다른 창 · 8분 상한 뒤 같은 창에서 가능 · 설계 §3 'VIX 만 받은 일을 전체 갱신 완료로 보고하지 않는다' 위반). 그래서 거절 상태를 따로 두고, 화면은 그 재시도 id 로 결과까지 이어서 보인다. 전체 갱신이 돌 때의 `running` 은 그대로다.
13. **대기 만료 타이머**(독립 검토 LOW): 처음에는 받은 순간의 남은 초만 봐서, 화면을 6시간 넘게 열어 두면 대기가 끝나도 'VIX 다시 받기'가 남았다. 남은 초로 타이머를 걸어 끝나는 순간 원래 버튼으로 돌린다. 서버의 `scope=vix` 는 대기와 무관하다는 판정(Q2)은 그대로다.
14. **늦은 상태 응답 — 검증자 r1 결함과 같은 종류 3곳**(검증자 r1 REJECTED · P2)
    - 원인: 'VIX 다시 받기' 상태 확인은 끝난 뒤에도 그 전에 보낸 요청의 응답을 버리지 않았고, 공용 타이머를 멈추는 함수를 같이 썼다. 그래서 이전 재시도의 늦은 응답이 새 재시도를 실패로 표시하고 새 상태 확인 타이머까지 멈췄다(검증자 재현).
    - 고침: 상태 확인 세대 — 멈출 때(결과 확인 · 상한 · 새 재시도 · 화면 떠남) 세대를 올리고, 응답(성공 · 오류)은 보낸 때의 세대가 지금과 같을 때만 쓴다. 상태 요청 순번 — 받은 상태(버튼 글자 · 대기 시간)는 순번이 더 새 것만 반영한다(전체 갱신 화면이 넘긴 상태는 받은 순간 순번).
    - 같은 종류로 함께 고친 곳(계약 문장 기준 · 모두 고치기 전 코드에서 시험 실패 확인)
      - 같은 확인의 오류 응답: 이전 확인이 상한(120회)에 닿은 뒤 늦게 온 오류가 새 재시도를 끝냈다.
      - 화면을 열 때 읽은 상태: 늦게 오면 더 새 상태(전체 갱신 끝 · 'VIX 다시 받기' 버튼)를 덮었고, '진행 중'이면 그 사이 이어받은 다른 재시도 대신 옛 id 를 따라갔다.
      - 전체 갱신 상태 확인 반복(POC5-12 전부터 있던 구조): 실패 뒤 다시 누른 새 갱신을, 이전 요청의 늦은 응답(실패 · 오류)이 끝내고 '갱신 실패'로 표시했다. 같은 세대 방식으로 고쳤다(실패 표시 · 8분 상한 동작은 그대로).
    - '다시 받기 시작 때 멈춤'은 결과를 바꾸지 못해(버튼이 진행 중 잠김) 넣지 않았다(§4-10 과 같은 기준).
    - 전체 갱신 상한(120회) 뒤 마지막 조회는 일부러 세대를 보지 않는다(기존 동작 그대로). 그 조회 중 화면을 떠나도 갱신이 끝났으면 시장 읽기 무효화와 다시 읽기 GET 1회가 일어난다(떠난 화면에는 보이는 변화 없음). 처음 보고에 이 줄을 '결과를 바꾸지 못하는 줄'로 적은 것은 틀려 고쳤다(r1 검토).
15. **r1 고침 검토(Workflow · 3관점 · 지적마다 반박 검증)에서 나온 2건을 고쳤다**
    - 끝난 뒤 다시 읽기가 진행 중 요청에 붙음: 갱신 · 'VIX 다시 받기'가 끝난 뒤 다시 읽기가, 그 전에 보낸 같은 주소 요청(예: 갱신 중 필터를 바꿔 보낸 요청)이 아직 진행 중이면 새 요청 없이 그 결과를 썼다(시험 재현). 반박 검증에서 실제 서버의 쓰기 순서상 옛 기준일 · 옛 VIX 가 보일 가능성은 낮고, NAV 를 읽은 직후 저장되는 좁은 경우만 남는다고 판정됐다. 고치는 값이 작아 고쳤다: 다시 읽기 직전 진행 중 공유를 비우고 새로 보낸다(`forgetMarketTopnInflight` · 이미 기다리는 쪽은 자기 요청 그대로 · 늦게 온 옛 응답은 순번으로 무시).
    - 화면 떠난 뒤 POST 응답: 버튼을 누르고 POST 응답 전에 화면을 떠나면, 늦게 온 응답(`accepted` · `vix_retry_running`)이 아무도 멈추지 않는 상태 확인을 열었다(전체 갱신 쪽은 기존 동작). POST 전 세대를 기억해 화면을 떠났으면 응답을 버린다.
    - 문서 3건(전체 갱신 상태 확인의 순번 서술 · 마지막 조회 서술 · 서버 다시 켜기 사실)을 실제 코드 · 실측에 맞게 고쳤다.

## 5. 알려진 한계 / 미완성

1. **파일 감시 범위는 다시 켜야 적용된다 — 적용됨**: 이 맥북의 백엔드는 2026-10-14 18:00:06 에 `./start.sh` 로 `--reload-dir app --reload-dir scripts` 를 달고 다시 켜졌다(ps 실측 · 부모 프로세스 `bash ./start.sh`). 다시 켠 뒤 파일 감시 CPU 는 60초에 5.26초다(§3-1).
   - `docs/README.md` 의 Windows 수동 실행 명령에도 같은 감시 범위를 넣었다(사용자 결정 2026-10-14 · §7-1).
2. **사용자 실제 화면 수치는 아직 없다**: 개발자 측정만 있다. PLAN §3 보완 4(대기 · 계산 · DB 읽기 나눠 재기 · 시장 GET 화면 제한 20초)는 다시 켠 뒤에도 10초를 넘는 정상 응답이 남을 때만 한다.
3. **늦은 응답 시험 범위**: 조회 중에는 '불러오는 중...' 화면이라 그 사이 필터 · 정렬을 바꿀 수 없다. 순번 시험은 개발 모드 이중 실행 응답 순서를 뒤집어 확인하고, 갱신 중 필터 변경은 §4-11 시험으로 확인한다.
4. **실제 VIX 실패로 확인하지 않았다**(PLAN '격리 시험으로만'): 'VIX 다시 받기'는 격리 시험(서비스 · API · 화면)으로만 확인했다. 지금 실제 행은 없다(`vix_retry` = null).
5. **미국 평일 휴장**: 요일만 센다(달력 없음 · 설계 §2). 휴장 다음 날은 L = 1 로 안내가 없고, 휴장에 공개 지연이 겹치면 `update_check` 가 날 수 있다(설계가 '장애로 단정하지 않는 확인 대상'으로 정함).
6. **`fdr_request_timeout()` 전역 교체**(POC5-11 과 같은 성질): 다시 받기의 VIX 블록 동안 같은 프로세스 다른 스레드의 `requests` 호출에도 'timeout 없으면 20초'가 들어간다.
7. **KS-10 근접**: `MarketDiscoveryView.tsx` 는 기준 커밋 835줄 → 지금 861줄로 근접 구간(850줄 이상 · 트리거 900 초과)에 들어갔다. 새 책임은 hook 2개로 뺐고 화면에 남은 것은 연결 · 버튼 글자 · 줄 표시 · 전체 갱신 상태 확인 세대(기존 반복의 결함 정정 · §4-14)다. 다음에 이 화면에 기능을 더하면 분리를 먼저 해야 한다. `market_refresh_service.py` 576줄(근접 600줄 미만).

## 6. 다음 검증자(Codex)에게 알릴 점

1. **변이**(복원 = 원본 내용 쓰기 + `os.utime` · 저장소 밖 사본에서 실행 — 실행 중 서버가 변이 코드를 다시 읽지 않게)
   - backend 14/14 검출: NAV 결과 제외 · KOSPI 예외 제외 · 이전 표식 해제 안 함 · 다시 받기 중복 허용 · 전체 갱신이 다시 받기 실행 중 무시 · 재시작 정규화 없음 · 주말 되돌림 없음 · D > E 판정 없음 · scope 아무 값 허용 · 결과를 전체 갱신 행에 씀 · 다시 받기가 다른 단계 호출 · 대상 없어도 실행 · L = 1 경고 · PC 응답 판정 시각 고정 안 씀
   - frontend 12/13 검출: 진행 중 공유 없음 · 끝나도 안 지움 · 늦은 응답 무시 없음 · 같은 입력 실패도 오류 카드 · 다른 입력 실패도 자료 유지 · 재시도 id 확인 안 함 · 대기 시간 무시 · 판정 필드 없으면 안내 없음 · 전체 갱신 시작 때 결과 줄 유지 · scope 안 보냄 · 「개발·실험용」 옛 규칙 · 표식 없어도 VIX 버튼
   - 살아남은 1(화면을 떠날 때 순번 올리기)은 결과를 바꾸지 못하는 줄이라 지웠다(§4-10).
   - 검토 반영 뒤 7종 더 검출: 다시 읽기가 옛 입력 · 거절 인계 안 함 · 대기 만료 타이머 없음 · 다시 받기 실행 중 응답 안 따라감 · 같은 입력 실패도 오류 카드(hook) · 늦은 응답 무시 없음(hook) · (backend) 전체 갱신 거절을 `running` 으로
   - 검증자 r1 반영 뒤 9종 더 검출: 다시 받기 응답 세대 확인 없음 · 다시 받기 오류 세대 확인 없음 · 멈출 때 세대를 안 올림 · 상태 순번 확인 없음 · 화면 열 때 응답의 세대 확인 없음 · 전체 갱신 응답 세대 확인 없음 · 전체 갱신 오류 세대 확인 없음 · 전체 갱신 멈출 때 세대를 안 올림 · 순번을 받은 순간에 매김
   - r1 고침 검토 반영 뒤 2종 더 검출: 끝난 뒤 다시 읽기가 진행 중 요청에 붙음 · 화면 떠난 뒤 POST 응답 확인 없음(각각 시험 2건 실패)
   - 합계: backend 15/15 · frontend 29/30(살아남은 1 = 지운 줄)
2. **독립 검토**(2026-10-14 · 읽기 전용 · 정합 · 문서 2관점 · 지적 5건 · 모두 반영)
   - MEDIUM 갱신 중 필터 변경 뒤 옛 조건으로 다시 읽기(기존 결함): §4-11 · 시험 1 · 변이 1
   - LOW 'VIX 다시 받기' 실행 중 전체 갱신 거절이 '갱신 완료'로 보일 수 있음: §4-12 · 시험 2 · 변이 3
   - LOW 화면을 연 채 대기가 끝나도 'VIX 다시 받기': §4-13 · 시험 1 · 변이 1
   - LOW 결과서 숫자 · KS-10 표현 · PLAN 신규 표기: §1 · §2 · §4-3 · §5-7 실측으로 고침
   - LOW STATE staged 정합: 보고 직전 git 상태로 맞춤(§9)
   - 검토가 확인한 것: 최신성 4상태 · 'VIX 만 실패' 조건(KOSPI 예외 · NAV status) · 잠금 안 표식 · scope · 422 · 상호 거절 · 재시작 정규화 · 진행 중 공유 · 세 화면 문구 · 옛 규칙 제거
3. **OCI · 공유 경로 무변경 근거**
   - `scripts/run_oci_market_data_batch.py` · `app/three_push_runtime/*` · `market_risk_reference_service.py` 변경 0이다.
   - `freshness` 는 PC 응답 조립 함수에서만 붙는다(공유 builder 결과에 없음 — 시험).
   - `refresh_pc_vix` · `run_vix_ingest` · `refresh_vix` 는 POC5-11 그대로다.
4. **상태 저장 함수의 scope 인자**: 기본값이 지금 값(`market_data`)이라 기존 호출은 그대로다. 새 행은 `vix_retry` 하나다.
5. **화면 시험 방식**: 진행 중 공유는 진짜 `fetchMarketTopnLatest` · `request` 에 가짜 `fetch` 로 서버 호출 수를 센다(`marketTopnInflight.test.ts` · 화면 StrictMode 시험). 진행 중 공유는 모듈 상태라 `vitest.setup.ts` 가 매 시험 전에 비운다.
6. **판정 Q1 확인 범위**: VIX 날짜를 국내 날짜와 비교하던 곳을 `frontend` 전체에서 찾았다(`vix` × 날짜 비교 · stale · 오래). 남은 곳은 없다. 결정 초안 미리보기 카드는 VIX 기준일만 보인다(판정 없음 · 그대로).
7. **검증자 r1 결함 재현 · 확인**: 검증자 재현 순서(이전 상태 요청 2개 겹침 → 두 번째 응답으로 실패 → 새 재시도 → 첫 번째의 늦은 응답)를 같은 모양 시험으로 넣었다(늦은 응답 있음 · 없음 2경우 · 새 진행 줄 · 버튼 잠금 · 다음 상태 요청 1건 · 그 뒤 새 재시도 결과 표시까지).
   - 고치기 전 코드(staged 판) + 새 시험(그때 이 파일 26건): 6 failed · 20 passed(실패 6 = 늦은 응답이 있는 경우 전부 · 대조 경우 통과).
   - 고친 코드: 26 passed → r1 고침 검토 반영 4건을 더해 지금 30 passed.
   - 이번 라운드 backend 변경 0(전체 회귀 3536 passed 는 그대로 유효).

## 7. 사용자 확인 — 실제 화면(검증 뒤)

- 사용자 후속 확인(2026-10-14): `stop.bat` / `start.bat` 실행을 완료했고, 재기동에 오래 걸리지 않았다고 확인했다. Windows 시작 스크립트 실행 확인이며, 시장 화면의 시간 초과 반복 여부·VIX 경고 표시 확인은 별도로 남는다.

1. 다시 켜기: 완료(위 사용자 확인 · 이 맥북 백엔드는 18:00 `./start.sh` 로 새 감시 범위 · §5-1).
2. 「요즘 잘 오르는 ETF」 · 「오늘의 투자 점검」을 평소처럼 연다.
   - 시간 초과 반복 여부
   - 정비 큐 VIX 경고가 사라졌는지(지금 VIX 10-13 · `fresh`)
3. 개발자 재측정(다시 켠 서버 · 최종 코드): 파일 감시 CPU 60초 5.26초 · 시장 메뉴 열기 시장 TOP N GET 1건 · 1,192 / 1,178ms(§3-1).
4. 사용자 결정: `docs/README.md` 수동 실행 명령에도 같은 감시 범위를 넣는다(2026-10-14 · 반영 완료).

### 7-1. 사용자 화면 확인 결과 (2026-10-14)

- 「요즘 잘 오르는 ETF」: "금방 뜹니다. 예전보다 더 빨라졌네요" — 시간 초과 반복 없음.
- 「오늘의 투자 점검」 「자료 최신화 필요」: VIX 경고 줄 없음. 사용자는 VIX 칸이 화면에 있어야 하는 줄 알았다(개발자 안내 문구가 헷갈리게 쓰였음). 이 화면에는 VIX 값 칸이 원래 없고, VIX 는 문제가 있을 때만 경고 한 줄로 나온다. 같은 시각 화면 API 응답은 VIX 2026-10-13 · `fresh`(21:38 KST 읽기 확인).
- `docs/README.md` 수동 실행 명령에 감시 범위를 넣는 것과 커밋 · push 를 승인했다.

## 8. 검증 실측 (2026-10-14 · 최종 코드)

- backend: `black --check` · `flake8` · `py_compile` 통과(변경 · 신규 파이썬 8개)
  - `tests/test_market_vix_retry.py` 49 passed
  - 전체 회귀(검토 반영 뒤 · 마지막 1회): **3536 passed**(2026-10-14 · 415.73초 · 경고 1 = 기존 httpx 사용 중단 안내 · POC5-11 종료 3487 + 새 시험 49)
- frontend: `npx tsc --noEmit` 종료 0 · `npm run lint` 종료 0 · `npx vitest run` 43파일 517 passed(직전 39파일 463 + 새 시험 54)
- 변이: backend 15/15 · frontend 29/30(살아남은 1 = 지운 줄 · §6-1)
- 시험의 라이브 DB 접근 0(격리 DB) · 외부 호출 0(가짜 수집기 · 가짜 fetch)

## 9. git 상태

(보고 직전 실측 · 보고 메시지에 인용)

## 10. 종료 (2026-10-14)

- 사용자가 커밋 · push 를 승인했다(2026-10-14 "푸시해주세요"). 코드 · 시험 · 문서 · README · 종료 기록을 한 커밋으로 push 했다(커밋 번호 = `git log`).
- PC 백엔드는 18:00 새 감시 범위로 다시 켜져 있고, 화면은 자동 다시 읽기로 반영됐다. OCI pull 은 없다(PC 전용 · OCI 배치 · PUSH 변경 0).
- 결함: `DEF-PC-MARKET-SCREEN-SLOW-LOAD` 해소(사용자 화면 확인) · 정비 큐 VIX 지연 경고(`DEF-PC-VIX-REFRESH-MISSING` 의 남은 한계) 해소.
- 남은 것: 「요즘 잘 오르는 ETF」 화면 파일 KS-10 근접(861줄 · 다음 기능 전에 분리) · 실제 VIX 실패로는 'VIX 다시 받기'를 확인하지 않음(격리 시험만) · 미국 평일 휴장은 요일로만 셈.
- 다음 차례 = 설계자(다음 단계).
