# POC3-08 종목 관리·보유 현황 그리드 UX 개선 (A~F) — 개발 결과서

- 작성일: 2026-08-10 (A~D) · 2026-08-11 (E 정렬 · F 증권사 스타일·구성막대 추가)
- 문서 성격: 개발 결과서 (검증자 Codex 입력)
- 지시 출처: 사용자 직접 지시 — A~D("A→D까지 모두 다 해주세요") + 추가 지시 E(정렬)·F(보유 현황 증권사 스타일·구성 막대)
- PLAN: `docs/ai_plan/POC3/POC3-08_HOLDINGS_GRID_UX_IMPROVEMENT_PLAN_V1.md`
- 인계: `docs/handoff/POC3/POC3-08_SESSION_HANDOFF.md` §2 미해결 4건(A·B·C·D)
- 최신 HEAD 는 `git log --oneline -1` 로 실측 (본문에 SHA 박지 않음)
- 커밋 구성: A~D = `be6d27d9`(push 완료) · **E·F = 본 결과서와 함께 별도 커밋(프론트 전용)**

---

## 사용자 확정 정책 (착수 전 질의로 확정)

| 항목 | 실측 근거 | 사용자 확정 |
|---|---|---|
| (A) 검증 방식 | `etf_master` = ETF 1163개만, 개별주(005930·000660·006400) 미포함. 보유 33건 중 26건 조회됨·4건(개별주 3+`111`) 불가 | **형식검증(영숫자 6자) + 경고** — 형식 위반은 저장 차단, 형식 OK지만 미등록은 경고만(개별주 허용) |
| (B) 저장 흐름 | 오류/저장/OCI가 3곳 분산 | **하단 고정 액션바** |
| (D) 계좌 입력 | datalist 자유입력 | **추천 목록 select 로 제한** |
| 경고 표시(추가 확인) | — | **한 종목 = 한 줄 고정** · 문제 행은 종목코드 칸 아이콘(⚠/✗)+테두리색만 · 상세는 액션바에 모음 |

착수 전 목표 구조 목업을 사용자에게 제시·승인받음("이대로 갑니다").

---

## 1) 처리한 요구사항

- **(A) 종목 형식검증 + 종목명 자동조회**: **DONE**
  - 백엔드: `PUT /holdings` 저장 경로 `strict_ticker=True` — 영숫자 6자 위반(`111`·`dasdasd`)은 422 차단. ETF 실존은 막지 않음(개별주 허용).
  - 신규 GET `/holdings/etf-name?ticker=` — `market_data_store.get_etf_name` 재사용해 `etf_master` 종목명 조회(읽기 전용).
  - 프론트: 종목코드 입력 시 debounce 조회 → 종목명 자동채움 + 상태 아이콘(ok/warn/err).
- **(B) UI 일관성(하단 고정 액션바)**: **DONE** — 경고·오류 요약 → 저장 버튼 → 저장 결과를 그리드 하단 sticky 액션바 한 흐름으로. 형식 오류 있으면 저장 버튼 비활성.
- **(C) OCI 적용 UNKNOWN 제거**: **DONE (근본 해소)** — 껍데기 artifact 삭제 + `.gitignore` 추가 + **재생성 원인(테스트가 live 경로에 write) 근본 차단**(`test_holdings_oci_apply.py` autouse fixture 로 `_LOCAL_APPLY_STATUS` tmp 격리). 삭제만으로는 다음 테스트 실행 시 재생성됨을 실측 확인 후 근본 수정.
- **(D) 계좌 입력 제한**: **DONE** — 계좌 input(datalist 자유입력) → `<select>`(추천 5개: 일반·ISA·연금·오픈뱅킹·기타)로 제한.
- **(E) 정렬(추가 지시 · 두 화면)**: **DONE** — 사용자 추가 지시("계좌순·종목순 정렬"). 정렬 3기준: **계좌순(기본·최우선)** = 계좌 그룹(일반·ISA·연금·오픈뱅킹·기타 순) + 계좌 내 종목명 가나다 · **종목명순**(전체 가나다) · **종목코드순**(전체 ticker 오름차).
  - **보유 현황**(`EnrichedHoldingsSection`, 읽기): 순수 함수 `sortHoldings` — 표시 순서만(평가·계산·요약·expand key 무변경).
  - **종목 관리**(`HoldingsManageView`, 입력·편집): 순수 함수 `sortRowsWithMetas` — rows·metas index 짝 보존하며 함께 정렬. **조회(로드/저장 직후) 시 계좌순 자동 정렬**, 그 후 사용자 정렬 버튼으로 수동 재정렬(편집 중 자동 재정렬 X — 타이핑 중 행 튐 방지 · 빈 입력 행은 맨 뒤). 사용자 확정: "조회 시 자동 정렬 + 수동 버튼".
  - 커밋 분리: A~D 는 `be6d27d9` push 완료 · 정렬(E)은 별도 커밋.
- **(F) 보유 현황 증권사 스타일 개편(추가 지시)**: **DONE** — 사용자 추가 지시("관리처럼 카드형 말고 더 예쁜 것 · 직관적인 증권사 스타일 · 전체 현황이 보이게"). `EnrichedHoldingsSection` 표시를 증권사 MTS 스타일로 교체:
  - **HoldingsHero**: 상단 큰 평가 배너(총 평가금액·평가손익 금액·수익률·총매입·종목수·시세확인수 + 미확인 경고). 기존 `summary`(computeSummaryFor) 재사용, 신규 계산 없음.
  - **AccountSection**: 계좌순이면 계좌 소계 헤더(계좌 태그·종목수·계좌 평가손익)로 묶고, 종목명/코드순이면 헤더 없는 단일 섹션(정렬 정책 그대로).
  - **HoldingRow**(2단×2열): 좌상 종목명+판단배지(보유 HOLD + 시세미확인/계산부족 경고) · 우상 손익 금액·수익률 · 좌하 티커/수량/비중(숫자) · 우하 매입가→현재가. 행 클릭 시 `DetailRowFields` 상세 펼침(평단·기준시각·출처).
  - **CompositionBar**(계좌별 구성 막대): 상단 배너 안에 계좌별 평가금액 비율 가로 누적 막대(계좌순·계좌색). 사용자 지적("비중이 낮아 개별 행 막대는 의미 적음") 반영 → **개별 행 비중 막대 제거, 비중은 숫자로만**. 막대는 계좌별(일반/ISA/오픈뱅킹) 3세그먼트로 통합. 비율=평가금액 기준(개별 행 시장비중과 동일 기준·`AccountSummary.priced_eval` 재사용, 신규 계산 없음). 라이브 실측: 일반 37.1%·ISA 40.0%·오픈뱅킹 22.9%(합 100%).
  - 손익 색은 앱 실제 `pnlClass`(수익=--ok 초록 / 손실=--danger 빨강) 재사용 — **색 자체는 변경 안 함**(기존 계약 보존). 표시 방식만 교체(평가·계산·요약·정렬 로직 무변경).
  - 죽은 컴포넌트 제거: `OverallSummaryCard`·`AccountSummaryCards`·`AccountSummaryRow`·`CompactHoldingsTable`·`CompactRow`·`SummaryItem`·`KV`(교체됨). `DetailRowFields` 는 재사용 유지. `.summary-card`/`.compact-table`/`.account-summary` CSS 는 `EvidenceDetails.tsx` 가 여전히 사용하므로 삭제 안 함.
  - 라이브 API(`/holdings/enriched`) 실측으로 컴포넌트 소비 필드 12종 전부 존재 확인.

## 2) 변경된 파일 목록

- `app/holdings.py`: 수정 — `TICKER_PATTERN` 신설, `validate_holdings`/`_coerce_holding` 에 `strict_ticker` 파라미터(기본 False=하위호환).
- `app/api.py`: 수정 — `put_holdings` 에 `strict_ticker=True`, 신규 `GET /holdings/etf-name`(`get_etf_name_lookup`), `market_data_store` import.
- `frontend/lib/api/holdings.ts`: 수정 — `fetchEtfName` + `EtfNameLookupResult` 추가.
- `frontend/app/components/HoldingsManageView.tsx`: 수정 — 종목코드 검증/자동조회·행별 메타·하단 액션바·계좌 select·`isValidTickerFormat` export.
- `frontend/app/globals.css`: 수정 — `.hm-code-cell`·`.hm-flag*`·`.hm-row-err/warn`·`.hm-inp-err/warn`·`.hm-actionbar*`·`.hm-msg-*`.
- `frontend/app/components/HoldingsManageView.commas.test.tsx`: 수정 — `isValidTickerFormat` 테스트 4케이스 추가.
- `tests/test_holdings_ticker_validation.py`: **신규** — 형식 게이트·etf-name·하위호환 13케이스(untracked).
- `tests/test_holdings_oci_apply.py`: 수정 — `_LOCAL_APPLY_STATUS` tmp 격리 autouse fixture(C 근본).
- `.gitignore`: 수정 — `state/holdings/holdings_apply_status_latest.json` 추가.
- `docs/PROGRAM_TRUTH.md`: 수정 — 헤더·§5.1·§5.2·§6.1·부록 A 에 POC3-08 반영(정렬 포함).
- `frontend/app/components/EnrichedHoldingsSection.tsx`: 수정 — (E) 정렬 `sortHoldings`·`HoldingsSortKey`·정렬 컨트롤 + (F) 증권사 스타일 `HoldingsHero`·`CompositionBar`(계좌별 구성 막대)·`AccountSection`·`HoldingRow`(죽은 표 컴포넌트 제거·개별 행 비중 막대 제거).
- `frontend/app/components/EnrichedHoldingsSection.sort.test.tsx`: **신규** — 보유 현황 정렬 8케이스(untracked).
- `frontend/app/components/HoldingsManageView.tsx`: 수정 — (E) 종목 관리 정렬 `sortRowsWithMetas`·`ManageSortKey`·조회 시 자동 계좌순·수동 정렬 버튼(rows·metas 짝 보존).
- `frontend/app/components/HoldingsManageView.sort.test.tsx`: **신규** — 종목 관리 정렬 8케이스(untracked, 빈 행·metas 짝 보존 포함).
- `frontend/app/globals.css`: 수정 — (E) `.holdings-sortbar*`·`.holdings-sort-seg` + (F) `.hld-hero*`·`.hld-comp*`(계좌별 구성 막대)·`.hld-acct*`·`.hld-row*`·`.hld-badges`·`.hld-wv` 추가(위 (A~D) 수정에 이어).

## 3) 신규 추가된 의존성

없음. (신규 GET 은 기존 `market_data_store.get_etf_name` 재사용. 신규 DB·source·수집 없음.)

## 4) 지시문 외 변경

- **`tests/test_holdings_oci_apply.py` autouse fixture 추가**: 지시(C)는 "artifact 삭제 + .gitignore" 였으나, 삭제만으로는 기존 테스트가 live 경로에 재생성함을 실측 → 재발 방지 위해 테스트 격리를 함께 수정. (C의 근본 원인 해소 — 지시 취지 범위 내.)

## 5) 알려진 한계 / 미완성

- (A) `etf_master`에 없는 개별주(005930 등)는 종목명 자동조회 불가 → 사용자가 직접 입력(경고만, 저장 허용). 정책 확정대로.
- (F) 구성 막대·평가금액·손익은 **시세 확인(평가 계산 가능) 종목 기준** — 시세 미확인 종목은 막대·총평가에서 제외(개별 행엔 "시세 미확인" 표시). 배너 경고로 명시.
- 실화면(입력 편의·자동조회·액션바·select·증권사 스타일 레이아웃·구성 막대·정렬 표시)은 자동 테스트 미탐지 → **사용자 실화면 확인 필요**(레이아웃/폭/색 최종 판단은 사용자).
- OCI 실제 적용(POST /holdings/apply write)은 기존과 동일 — 이번 범위 아님.
- (버튼) `보유 현황`의 `종목 관리 →`·`확인 근거 보기 →`는 좌측 메뉴와 중복되는 편의 바로가기 — 사용자 확인 후 **그대로 유지 결정**. `시세 갱신`은 실기능이라 유지.

## 6) 다음 검증자(Codex)에게 알릴 점

- **⚠️ 라이브 holdings 파일 복구 이력**: 개발 중 `PUT /holdings` 를 TestClient 로 **live 파일 대상** 실행하는 실수로 `state/holdings/holdings_latest.json`(사용자 보유 33종목)을 1종목으로 덮어씀 → **OCI authoritative 복사본**(`ssh oci-krx`, 읽기전용)에서 복구. 복구본 = **32종목**(OCI 최종 적용본, 오타 `111` 행은 없음 — 목표 A와 정합). PC 원본의 `111` 1건은 소거됨. 이후 모든 쓰기 테스트는 경로 격리(tmp)로만 수행. (재발방지 메모리 등록.)
- **⚠️ 사전 존재 실패(내 변경 무관)**: `tests/test_factor_signals.py::test_step3_message_text_does_not_list_all_holdings_factor_reasons` 가 `KeyError: 'message_text'` 로 FAIL. 내 코드를 stash 한 clean HEAD 에서도 동일 FAIL → **POC3-08 이전부터 존재하는 실패**. 이번 작업과 무관(`/runs/generate-from-holdings` 응답 shape 이슈).
- **strict_ticker 계약 핵심**: 저장(PUT)만 strict, 읽기(`load()`)는 lenient. 이 분리로 기존 저장 파일의 비정형 값(`111` 등)이 있어도 전체 화면이 죽지 않음 — `test_load_backward_compat_with_legacy_ticker` 로 고정.
- **(C) 근본 검증법**: artifact 삭제 후 `pytest tests/test_holdings_oci_apply.py` 재실행 → `state/holdings/holdings_apply_status_latest.json` 재생성 안 되면 OK.

## 7) 사용자 확인이 필요한 항목

- **holdings 파일이 32종목으로 복구됨**(위 §6). PC 원본에 있던 오타 `111` 행이 사라짐. 실제 보유와 32종목이 일치하는지 실화면 확인 권장(불일치 시 화면에서 재입력·저장).
- 실화면 UX(A~F) 최종 확인 — 종목 관리(입력·자동조회·액션바·계좌 select·정렬) + 보유 현황(증권사 스타일 배너·계좌별 구성 막대·2단 종목 행·정렬). 레이아웃·색은 사용자 판단.
- 손익 색은 앱 기존 색(수익=초록/손실=빨강, 서양식) 그대로 유지 — 국내 관례(수익 빨강)로 바꾸려면 별도 지시 필요(이번 범위 아님).

---

## 검증 산출물 (실측)

- 백엔드(A·C 커밋 `be6d27d9`): `black --check` OK · `flake8` 0 · `py_compile` OK · `pytest tests/test_holdings_ticker_validation.py tests/test_holdings_oci_apply.py tests/test_holdings_apply_status.py tests/test_holdings_account_group.py` = **41 passed**. E·F 는 프론트 전용 — 백엔드 무변경.
- 프론트(최종 A~F): `npx tsc --noEmit` 0 · `npm run lint` 0 · `npx vitest run` = **151 passed** (12 파일). POC3-08 신규/확장 테스트: `HoldingsManageView.commas.test.tsx`(14, +콤마·형식검증) · `EnrichedHoldingsSection.sort.test.tsx`(8, 신규) · `HoldingsManageView.sort.test.tsx`(8, 신규).
- 런타임 실측:
  - (A) `GET /holdings/etf-name` — 069500→"KODEX 200"(found) · 005930→found=false · 0005g0→0005G0 정규화·"IBK K-AI반도체코어테크". `PUT /holdings` — 111→422 · 005930→200 (격리 파일).
  - (E) 계좌순 정렬 실데이터 32종목 — 일반→ISA→오픈뱅킹 그룹핑 + 계좌 내 종목명 가나다 · 종목 관리 metas 짝 보존 OK.
  - (F) `GET /holdings/enriched` 실측 — 컴포넌트 소비 필드 12종 전부 존재(32종목·27 priced) · 계좌별 구성 막대 비율 일반 37.1%·ISA 40.0%·오픈뱅킹 22.9%(합 100%).
- (C) artifact: 삭제 후 `pytest tests/test_holdings_oci_apply.py` 재실행에도 `state/holdings/holdings_apply_status_latest.json` 재생성 안 됨 확인. gitignore 적용 확인(`git check-ignore`).
- **사전 존재 실패(무관)**: `tests/test_factor_signals.py::test_step3_message_text_does_not_list_all_holdings_factor_reasons` FAIL — POC3-08 이전부터 존재(§6, 내 코드 stash 후에도 동일 FAIL).
