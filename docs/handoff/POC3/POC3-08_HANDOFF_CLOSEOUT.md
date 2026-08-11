# POC3-08 Closeout · 설계자 인계 (종목 관리·보유 현황 그리드 UX 개선 A~F)

- 작성일: 2026-08-11
- 상태: **검증자 VERIFIED_WITH_NOTES · 사용자 실화면 확인 완료(Holdings 32종목 정합 OK)** → 위험수준 MEDIUM 근거 해소
- 성격: **설계서 없는 사용자 실화면 직접 확정 UI 개선**(handoff §2 미해결 A~D + 추가 지시 E·F) + 검증자 재작업 1라운드
- 개발 PLAN: `docs/ai_plan/POC3/POC3-08_HOLDINGS_GRID_UX_IMPROVEMENT_PLAN_V1.md`
- 개발 결과서: `docs/ai_result/POC3/POC3-08_HOLDINGS_GRID_UX_IMPROVEMENT_RESULT.md`
- backlog 근거: `project_krx_grid_design_backlog`(POC3-05 때 미룬 그리드 개선)

---

## 1. 무엇을 했나 (A~F)

**A. 종목 형식검증 + 종목명 자동조회** — 종목코드 영숫자 6자 형식검증(`111`·`dasdasd` 같은 오타 **저장 차단**). `PUT /holdings` 저장 경로만 `strict_ticker=True`(읽기 `load()` 는 lenient — 기존 파일 하위호환). 신규 **읽기전용** `GET /holdings/etf-name` 으로 `etf_master` 종목명 자동조회. 개별주(삼성전자 005930 등 — etf_master 에 없음)는 **경고만·저장 허용**(사용자 확정 정책).

**B. 저장 흐름 하단 고정 액션바** — 종목 관리 입력 그리드 하단에 sticky 액션바(경고·오류 요약 → 저장 버튼 → 결과 한 흐름). 형식 오류 있으면 저장 비활성. **행은 항상 1줄 고정**(문제 행은 종목코드 칸 아이콘+테두리색만, 조회 시 2줄로 안 벌어짐 — 사용자 명시 요구).

**C. OCI 적용 UNKNOWN 근본 해소** — 화면의 "UNKNOWN" 은 이전 세션 테스트가 만든 껍데기 status 파일이 원인. artifact 삭제 + `.gitignore` + **재생성 원인**(테스트가 live 경로에 write)까지 tmp 격리로 차단(삭제만으로는 다음 테스트에서 재생성됨을 실측 후 근본 수정).

**D. 계좌 입력 제한** — datalist 자유입력 → 추천 목록 select(일반·ISA·연금·오픈뱅킹·기타).

**E. 정렬(두 화면)** — 계좌순(기본, 계좌 우선순위 + 계좌 내 종목명 가나다) / 종목명순 / 종목코드순. 보유 현황은 표시 정렬, 종목 관리는 조회 시 자동 계좌순 + 수동 버튼(편집 중 재정렬 X · rows·metas 짝 보존).

**F. 보유 현황 증권사 스타일 개편** — 상단 큰 평가 배너(총 평가금액·평가손익) + **계좌별 구성 막대**(평가금액 비율) + 종목 행 2단×2열(좌상 종목명·판단배지 / 우상 손익 / 좌하 티커·수량·비중 / 우하 매입가→현재가), 행 클릭 상세 펼침. 개별 행 비중 막대는 값이 작아(최대 12%·최소 0.76%) 의미가 적어 제거·비중 숫자로만(사용자 지적 반영). **손익 색·평가·계산·요약·정렬 계약은 전부 보존 — 표시 방식만 교체.**

## 2. 신규/변경 계약 (다음 세션이 알아야 할 것)

| 항목 | 내용 |
|---|---|
| `GET /holdings/etf-name?ticker=` | **신규 · 읽기전용.** `etf_master` 종목명 조회. found=false = 개별주/미등록(저장 차단 아님, 프론트 경고용). `market_data_store.get_etf_name` 재사용 |
| `PUT /holdings` (변경) | 저장 경로 `strict_ticker=True` — 영숫자 6자 위반 422. **읽기 load() 는 lenient 유지**(기존 비정형 값 하위호환) |
| `app/holdings.py :: TICKER_PATTERN` | 형식 상수(프론트 `isValidTickerFormat` 와 동일 계약) |
| `HoldingsManageView.tsx` | 종목 관리 — 행 **uid 식별**(비동기 조회 index 경합 방지)·계좌 select 위장 제거·정렬 |
| `EnrichedHoldingsSection.tsx` | 보유 현황 — 증권사 스타일(`HoldingsHero`·`CompositionBar`·`AccountSection`·`HoldingRow`)·평가 3상태 |

**계약 무변경**: 신규 API 는 위 읽기전용 GET 1개뿐. DB·외부 source·factor·threshold·산식·OCI runner·crontab·Telegram·매매로직 무변경. 손익 색(수익=--ok 초록/손실=--danger 빨강)도 기존 그대로.

## 3. 검증자 재작업 반영 (VERIFIED_WITH_NOTES · 1라운드)

검증자가 UI 자체(1280×720 오버플로/콘솔 오류 없음·정렬·구성 막대)는 통과시키고 기능·정합 3건만 재작업 요청 → 반영(`90c2b005`):
- **#1 비동기 종목명 조회 index 경합**: 배열 index → 행 `uid` 식별. 응답 적용 직전 현재 ticker 재확인 → 정렬·삭제·코드변경 후 늦은 응답 폐기. deferred 실비동기 테스트로 고정.
- **#2 기존 커스텀 계좌 표시=저장 정합**: select 위장("일반") 제거 → 실제 저장값 표시 + `(기존)` 옵션. 미변경 저장 시 payload=표시값.
- **#3 부분 평가값 3상태**: 전부/일부/전부불가 구분 + 부분이면 `N/M종목 기준` 명시(전체·계좌 소계).

## 4. ⚠️ 남은 사항 / 설계자 인지 필요

- **손익 색 방향**: 현재 앱은 서양식(수익=초록/손실=빨강). 국내 증권사 관례(수익=빨강)와 반대. 이번엔 기존 색 보존(범위 밖). **국내 관례 전환 여부는 설계자·사용자 결정** 대기.
- **개별주 종목명**: `etf_master` 는 ETF 전용(1163개)이라 개별주(005930·000660·006400 등) 종목명 자동조회 불가 → 사용자 직접 입력. 개별주 마스터가 필요하면 별도 데이터 source STEP 필요(현재는 경고+수동입력으로 충분하다는 사용자 확정).
- **보유 현황 편의 버튼**: `종목 관리 →`·`확인 근거 보기 →` 는 좌측 메뉴와 중복 바로가기 — 사용자 확인 후 **유지 결정**.
- **라이브 Holdings 사고**: 개발 중 `PUT /holdings` 를 live 파일 대상 실행한 실수로 33건→1건 덮어씀 → OCI 정본에서 32건 복구(오타 `111` 소거). **사용자 32종목 정합 확인 완료.** 재발방지 메모리 등록.

## 5. 이번에 얻은 교훈 (메모리 반영)

- **[[feedback_no_write_api_test_on_live_state]]**(신규): 쓰기 API(PUT/POST)를 **라이브 state 파일 대상** 테스트하면 실데이터 덮어씀. 반드시 경로 격리(tmp_path/monkeypatch). 복구는 OCI 읽기전용.
- **행 식별은 index 가 아니라 안정 uid**: 비동기 응답 + 배열 재정렬/삭제가 겹치면 index 경합. 응답 적용 직전 "대상이 여전히 유효한지" 재확인.
- **부분 합계를 전체처럼 표시 금지**: 일부만 계산 가능하면 N/M 기준 명시(결측 정직성 — 기존 프로젝트 원칙과 정합).

## 6. 커밋 (전부 push 완료)

`ca9a0415`(파트1 카드행·콤마·계좌색) · `0a8fe3cd`(파트2 OCI 이력·계좌색) · `be6d27d9`(A~D) · `3b2a3175`(E·F) · `90c2b005`(검증자 재작업) · `591a05a0`(결과서 NOTE 정정) · `34322970`(STATE) · +본 Closeout.
`git diff --name-status ca9a0415^..HEAD` = 21경로, 결과서 §2와 1:1 일치. 최신 HEAD 는 `git log --oneline -1` 로 실측.

## 7. 다음 게이트

**설계자 Closeout**: 통합지도상 다음 실제 Step 확정. 그리드 디자인 개선 backlog(`project_krx_grid_design_backlog`)는 본 STEP(종목 관리·보유 현황 증권사 스타일)으로 **대부분 소진**. 후보:
- 손익 색 국내 관례 전환(사용자 결정 시)
- 개별주 종목 마스터 데이터 source(필요 시)
- 나머지 화면(확인 근거·오늘의 투자 점검 등) 동일 스타일 확산 여부
