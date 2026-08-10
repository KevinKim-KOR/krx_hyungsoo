# POC3-08 종목 관리·보유 현황 그리드 UX 개선 (A~D) — 개발 결과서

- 작성일: 2026-08-10
- 문서 성격: 개발 결과서 (검증자 Codex 입력)
- 지시 출처: 사용자 직접 지시 ("A→D까지 모두 다 해주세요")
- PLAN: `docs/ai_plan/POC3/POC3-08_HOLDINGS_GRID_UX_IMPROVEMENT_PLAN_V1.md`
- 인계: `docs/handoff/POC3/POC3-08_SESSION_HANDOFF.md` §2 미해결 4건(A·B·C·D)
- 최신 HEAD 는 `git log --oneline -1` 로 실측 (본문에 SHA 박지 않음)

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
- `docs/PROGRAM_TRUTH.md`: 수정 — 헤더·§5.1·§5.2·§6.1·부록 A 에 POC3-08 반영.

## 3) 신규 추가된 의존성

없음. (신규 GET 은 기존 `market_data_store.get_etf_name` 재사용. 신규 DB·source·수집 없음.)

## 4) 지시문 외 변경

- **`tests/test_holdings_oci_apply.py` autouse fixture 추가**: 지시(C)는 "artifact 삭제 + .gitignore" 였으나, 삭제만으로는 기존 테스트가 live 경로에 재생성함을 실측 → 재발 방지 위해 테스트 격리를 함께 수정. (C의 근본 원인 해소 — 지시 취지 범위 내.)

## 5) 알려진 한계 / 미완성

- (A) `etf_master`에 없는 개별주(005930 등)는 종목명 자동조회 불가 → 사용자가 직접 입력(경고만, 저장 허용). 정책 확정대로.
- 실화면(입력 편의·자동조회 표시·액션바 레이아웃·select)은 자동 테스트 미탐지 → **사용자 실화면 확인 필요**.
- OCI 실제 적용(POST /holdings/apply write)은 기존과 동일 — 이번 범위 아님.

## 6) 다음 검증자(Codex)에게 알릴 점

- **⚠️ 라이브 holdings 파일 복구 이력**: 개발 중 `PUT /holdings` 를 TestClient 로 **live 파일 대상** 실행하는 실수로 `state/holdings/holdings_latest.json`(사용자 보유 33종목)을 1종목으로 덮어씀 → **OCI authoritative 복사본**(`ssh oci-krx`, 읽기전용)에서 복구. 복구본 = **32종목**(OCI 최종 적용본, 오타 `111` 행은 없음 — 목표 A와 정합). PC 원본의 `111` 1건은 소거됨. 이후 모든 쓰기 테스트는 경로 격리(tmp)로만 수행. (재발방지 메모리 등록.)
- **⚠️ 사전 존재 실패(내 변경 무관)**: `tests/test_factor_signals.py::test_step3_message_text_does_not_list_all_holdings_factor_reasons` 가 `KeyError: 'message_text'` 로 FAIL. 내 코드를 stash 한 clean HEAD 에서도 동일 FAIL → **POC3-08 이전부터 존재하는 실패**. 이번 작업과 무관(`/runs/generate-from-holdings` 응답 shape 이슈).
- **strict_ticker 계약 핵심**: 저장(PUT)만 strict, 읽기(`load()`)는 lenient. 이 분리로 기존 저장 파일의 비정형 값(`111` 등)이 있어도 전체 화면이 죽지 않음 — `test_load_backward_compat_with_legacy_ticker` 로 고정.
- **(C) 근본 검증법**: artifact 삭제 후 `pytest tests/test_holdings_oci_apply.py` 재실행 → `state/holdings/holdings_apply_status_latest.json` 재생성 안 되면 OK.

## 7) 사용자 확인이 필요한 항목

- **holdings 파일이 32종목으로 복구됨**(위 §6). PC 원본에 있던 오타 `111` 행이 사라짐. 실제 보유와 32종목이 일치하는지 실화면 확인 권장(불일치 시 화면에서 재입력·저장).
- 실화면 UX(A~D) 최종 확인(레이아웃·자동조회·저장 흐름은 사용자 판단).

---

## 검증 산출물 (실측)

- 백엔드: `black --check` OK · `flake8` 0 · `py_compile` OK · `pytest tests/test_holdings_ticker_validation.py tests/test_holdings_oci_apply.py tests/test_holdings_apply_status.py tests/test_holdings_account_group.py` = **41 passed**.
- 프론트: `npx tsc --noEmit` 0 · `npm run lint` 0 · `npx vitest run` = **135 passed**(+4 신규).
- 런타임 실측: `GET /holdings/etf-name` — 069500→"KODEX 200"(found) · 005930→found=false · 0005g0→0005G0 정규화·"IBK K-AI반도체코어테크". `PUT /holdings` — 111→422 · 005930→200 (격리 파일).
- (C) artifact: 삭제 후 테스트 재실행에도 재생성 안 됨 확인. gitignore 적용 확인(`git check-ignore`).
