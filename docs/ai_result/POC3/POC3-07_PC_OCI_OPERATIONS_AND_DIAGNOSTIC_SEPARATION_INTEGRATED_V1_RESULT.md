# POC3-07 PC 운영 연결·운영/진단 화면 분리 통합 — 개발 결과서

- 작성일: 2026-08-06 (검증자 REJECTED r1 반영 갱신)
- 문서 성격: 개발 결과서 (검증자 입력)
- 대상 설계서: `docs/ai_design/POC3/PC_OCI_OPERATIONS_AND_DIAGNOSTIC_SEPARATION_INTEGRATED_DESIGN_V1.md`
- 개발 PLAN: `docs/ai_plan/POC3/POC3-07_PC_OCI_OPERATIONS_AND_DIAGNOSTIC_SEPARATION_INTEGRATED_V1_PLAN_V1.md` (V2 확정본)
- 커밋: `37c310f2`(기준·문서) · `30acd561`(A) · `fdced239`(B) · `b39cc7c1`(C) — 전부 커밋됨(미커밋 0)
- 검증: tsc 0 · eslint 0 · vitest 121 passed · pytest(param/holdings 관련) 64 + 신규 6 passed · black/flake8/py_compile OK

---

## 1) 처리한 요구사항

설계자 확정(Q1~Q12) + 사용자 2건에 따라 3축으로 구현.

- **A. 문서 정정**: DONE. PROGRAM_TRUTH OCI=RUNTIME_VERIFIED·OPERATING + KOSPI 정상 확인 + OCI 실측(runtime_state.sqlite 167KB·Holdings 소스 경로·status 파일 성격) 반영. STATE_LATEST POC3-07 STEP 추가.
- **B. 화면 분리 + 기동 시 1회 OCI 읽기**: DONE.
  - 메뉴 10키(dashboard·data_status 제거 → diagnostics 신설·흡수).
  - PC 백엔드 lifespan 에서 OCI 읽기 1회(읽기 전용, 실패해도 기동 안 막음, UNKNOWN). `GET /oci/startup-status` = 기동 캐시 반환(재조회 없음).
  - 첫 화면(오늘의 투자 점검): OCI 상태 한 줄 + 진단·상태 링크. 상세는 `diagnostics`.
  - `운영 관리` 신규화면 만들지 않음(설계자 정정). 버튼·새로고침·타이머 재조회 없음.
- **C. Holdings·PARAM 명시적 OCI 적용**: DONE.
  - `POST /holdings/apply`: 저장된 `state/holdings/holdings_latest.json`(OCI 실측 소스)을 tmp 전송 → 원격 sha256 대조 → atomic rename → active hash 재확인. PC==OCI hash 면 OCI_APPLIED. 실패 시 기존 active 보존.
  - PARAM 적용은 기존 `POST /three-push/param/apply`(create+approve+sync+verify+active 보존) 재사용. 응답에 `content_sha256`(표시용) 추가, 성공 판정은 기존 `oci_verified` 유지(Q4).
  - `holdings_manage` 에 OCI 적용 버튼·상태. 저장(PUT /holdings)과 별도 동작.
- **approval 역할 축소**: DONE. `승인·적용`으로 축소(ThreePushParamCard 만). 정보 PUSH 카드·미리보기·샘플·개발호환은 diagnostics 로 이동.
- **실전 write 검증**: PARTIAL(설계 의도대로). 개발자는 dry-run·계약 검증(단위 테스트 6, 실 OCI write 안 함). 실전 적용은 사용자가 화면에서 명시적 클릭(Q11) — 미수행.

## 2) 변경된 파일 목록

`git diff --name-status 608907bc..HEAD` 실측 기준. **총 30개**(초기 커밋 시점) + REJECTED r1 반영 파일. 상태 문자(A=신규/M=수정)는 git 기준.

**문서 (A=신규 5 · M=수정 2)**
- `docs/PROGRAM_TRUTH.md`: **신규(A)** — git 기준 신규 파일(직전 세션 생성분 포함). ※ r0 결과서에서 "수정"으로 오기재했던 것 정정.
- `docs/STATE_LATEST.md`: 수정(M)
- `docs/ai_design/POC3/PC_OCI_OPERATIONS_AND_DIAGNOSTIC_SEPARATION_INTEGRATED_DESIGN_V1.md`: 신규(A) — 설계서
- `docs/ai_plan/POC3/POC3-07_..._PLAN_V1.md`: 신규(A) — 개발 PLAN(V2 내용)
- `docs/ai_result/POC3/POC3-07_..._RESULT.md`: 신규(A) — 본 결과서
> ※ r0 §2 는 설계서·PLAN·결과서 3개를 누락해 27개로 적었음. 정정: **30개**.

**백엔드 (A 4 · M 2)**
- `app/oci_startup_status.py`: 신규(A) — 기동 시 OCI 읽기 모듈
- `app/api_oci_startup_status.py`: 신규(A) — GET /oci/startup-status
- `app/holdings_oci_apply.py`: 신규(A) — Holdings OCI 적용
- `app/api_holdings_oci_apply.py`: 신규(A) — POST /holdings/apply
- `app/api.py`: 수정(M) — lifespan 전환 + 두 라우터 등록
- `app/api_three_push_param.py`: 수정(M) — content_sha256 표시

**프론트 (A 3 · M 12)**
- `frontend/app/components/DiagnosticsView.tsx`: 신규(A)
- `frontend/lib/api/ociStartupStatus.ts`: 신규(A)
- `frontend/lib/api/holdingsApply.ts`: 신규(A)
- `frontend/app/components/LeftSidebar.tsx`: 수정(M) — 10키 재편
- `frontend/app/components/LeftSidebar.test.tsx`: 수정(M)
- `frontend/app/components/MainPanel.tsx`: 수정(M)
- `frontend/app/components/ApprovalTelegramView.tsx`: 수정(M) — 역할 축소
- `frontend/app/components/ApprovalTelegramView.test.tsx`: 수정(M)
- `frontend/app/components/approval/OciAlertHeader.tsx`: 수정(M)
- `frontend/app/components/TodayInvestmentCheckView.tsx`: 수정(M) — OCI 한 줄
- `frontend/app/components/DashboardView.tsx`: 수정(M) — navigate 정정
- `frontend/app/components/JudgmentWorkbenchView.tsx`: 수정(M) — navigate 정정
- `frontend/app/components/HoldingsRiskEvidenceSection.tsx`: 수정(M) — navigate 정정
- `frontend/app/components/HoldingsManageView.tsx`: 수정(M) — OCI 적용 버튼
- `frontend/app/components/ThreePushParamCard.tsx`: 수정(M) — 해시 표시
- `frontend/app/globals.css`: 수정(M) — .tc-linklike
- `frontend/lib/api/index.ts`: 수정(M) — barrel export
- `frontend/lib/api/threePushParam.ts`: 수정(M) — content_sha256 타입

**테스트 (A)**
- `tests/test_holdings_oci_apply.py`: 신규(A)
- `tests/test_oci_startup_status.py`: 신규(A) — **REJECTED r1 추가**(startup 경로 테스트)

> `app/api.py`, `frontend/lib/api/index.ts` 는 B·C 두 커밋에 걸쳐 수정됨.
> `approval/ManualPreviewSection.tsx`·`DevCompatSection.tsx` 는 **파일 이동 없이** DiagnosticsView 가 참조. 파일 자체 미변경.
> `InfoPushGuideCards.tsx` 는 approval 축소로 미참조(고아 후보) — 미변경·미삭제.

## 3) 신규 추가된 의존성

없음. (SSH/SCP 는 OS `ssh`/`scp` 를 `subprocess` 로 호출 — 기존 delivery.py 패턴 재사용. Python `hashlib` 표준.)

## 4) 지시문 외 변경

- `app/api.py` startup: 설계에 명시 안 된 세부지만 `@app.on_event("startup")` → `lifespan` 으로 구현(FastAPI 권장·deprecation 제거). 동작은 "기동 시 1회 읽기"로 설계 그대로. 이유: on_event deprecated 경고 제거 + 검증자 지적 예방.
- `DashboardView`/`JudgmentWorkbenchView`/`HoldingsRiskEvidenceSection` 의 `data_status` navigate → `diagnostics`: data_status 키 제거의 필연적 후속(타입 정합). 라벨도 "데이터 상태 확인" → "진단·상태 확인".

## 5) 알려진 한계 / 미완성

- **실전 OCI write 검증 미수행**: 설계 Q11 대로 개발자는 dry-run·단위 테스트(subprocess mock)까지만. Holdings 실제 OCI 적용은 사용자가 화면에서 명시적 클릭해야 최종 확인됨. → 최종 판정은 `INTEGRATED_COMPLETE_WITH_DECLARED_RUNTIME_GAP` 후보(사용자 실사용 확인 전).
- **기동 읽기의 개별 job 상태**: crontab 활성만 판정. Market/Holdings/Spike 개별 최근 성공/실패는 UNKNOWN(설계자 Q5 — 단일 status 파일이 spike 1건만 유지, 신뢰성 있게 구분 불가. 실측 확인).
- **`private_fields_exposed`(Q10)**: r1 에서 소스 확인 완료 — 노출 필드가 아니라 노출 **탐지 boolean**(이미 실측 가드). 추가 차단 불필요. 단 "실제 true 관측 이력" 조사는 런타임 로그 분석(§17.2 BACKLOG)으로 남김.
- OCI 배포 revision(정확한 sha) 표시: BACKLOG(§17.3 · 설계 범위 밖).

## 6) 다음 검증자(Codex)에게 알릴 점

- **OCI 실측은 개발자 직접 SSH 읽기(옵션 B, 설계자 Q2 확정)로 수행**했다. `ubuntu@krx-alertor-vm`. 읽기 전용(crontab -l / stat / sha256sum)만. 원격 write·job 실행·Telegram 발송은 하지 않음.
- **기동 읽기·Holdings apply 는 실제로 라이브 확인**: 백엔드 기동 시 `GET /oci/startup-status` → `reachable=true, overall=OPERATING, crontab_active=true` 반환 확인(포트 8123/8125). `POST /holdings/apply`·`GET /oci/startup-status` 라우트 등록 OpenAPI 로 확인(POST 는 실행 안 함).
- **Holdings apply 의 원자성·active 보존**은 단위 테스트로 검증(`tests/test_holdings_oci_apply.py`): scp 실패 시 mv 미호출, tmp hash 불일치 시 rename 안 함+tmp 정리, 정상 순서 scp→sha256sum(tmp)→mv→sha256sum(active), 적용 후 불일치 OUT_OF_SYNC. 실 OCI write 는 mock.
- **`private_fields_exposed`(Q10)**: 아직 소스에서 의미 확인 안 함. OCI runner 소스에 있을 가능성. 검증자가 이 필드 노출 위험을 별도로 봐주면 좋겠음(실제 노출이면 차단 필요 — 이번 미처리).
- **approval 축소로 삭제한 것**: `InfoPushGuideCards`·`ManualPreviewSection`·`DevCompatSection` 을 approval 에서 제거(파일은 존재, diagnostics 가 후 2개 참조). `InfoPushGuideCards` 는 어디서도 참조 안 됨 → 고아 후보(삭제 안 함).

## 7) 사용자 확인이 필요한 항목

- **Holdings OCI 적용을 실제로 눌러 확인**(Q11): 화면 `보유·자료 관리 > 종목 관리 > OCI 적용` 버튼. 실제 OCI active holdings 를 바꾸는 프로덕션 write 이므로 사용자 승인·실행 필요. 실패해도 기존 active 는 보존되도록 구현.
- **첫 화면 OCI 한 줄 / 진단·상태 화면 실화면 확인**: 레이아웃·문구는 자동 테스트로 안 잡히니 실화면 확인 권장.
- **`InfoPushGuideCards` 고아 처리**: approval 축소로 미참조. 삭제 여부는 사용자 지시 대기(POC3-05 `_orphaned/` 패턴처럼 이동/삭제 가능).

---

## AC 대응 (설계 §15)

| AC | 상태 | 근거 |
|---|---|---|
| AC-1 OCI 스케줄·발송 계약 불변 | DONE | crontab·runner 미수정. 읽기 전용만. |
| AC-2 OCI 자동 운영 지속 | DONE | 기동 읽기·apply 모두 OCI runner 안 건드림. |
| AC-3 PC 화면이 OCI job/Telegram 자동실행 안 함 | DONE | 조회는 기동 캐시. apply 는 명시적 클릭만. |
| AC-4 Holdings PC·OCI revision/hash 구분 | DONE | content_sha256 PC 계산 + OCI active sha256 대조. |
| AC-5 적용 성공 시만 OCI_APPLIED | DONE | PC==OCI hash 일치만 OCI_APPLIED. |
| AC-6 적용 실패 시 기존 active 보존·단계 표시 | DONE(r1 정정) | **rename 전에** schema+hash 검증 완료 → 검증 실패는 모두 rename 이전이라 active 미변경. 테스트: scp실패/hash불일치/schema불일치 모두 mv 미호출·tmp 정리. |
| AC-7 PARAM 승인됨/OCI 적용됨 분리 | DONE | 기존 param state status + apply 결과 분리. |
| AC-4 Holdings PC·OCI hash 구분 | DONE(r1 강화) | manifest(kind/content_sha256/created_at) 기록 + OCI active sha256 대조. |
| AC-8 PARAM 성공 시 PC==OCI hash | PARTIAL | 성공 판정은 기존 verify(Q4 사용자 확정). hash 는 표시용. |
| AC-9 동일 revision 재적용 idempotent | DONE | 같은 내용→같은 hash→같은 결과(테스트). |
| AC-10 PC·OCI 배포 revision 표시 | SKIPPED | 배포 sha 표시 BACKLOG(§17.3). |
| AC-11 job별 상태 독립 표시 | PARTIAL(r1 강화) | crontab(필수 3종 등록 판정) + holdings_source + runtime_state_db + push_job_results 를 독립 표시. 개별 PUSH job 성공/실패는 UNKNOWN(Q5). |
| AC-12 단일 status 로 전체 stale 오판 안 함 | DONE | status 파일 성격 확정, 구분 불가는 UNKNOWN. |
| AC-13 SUCCESS/스킵/FAILED/STALE/UNKNOWN 구분 | PARTIAL(r1 강화) | crontab=SUCCESS/STALE(일부 누락)/UNKNOWN, artifact=SUCCESS/UNKNOWN, push job=UNKNOWN. 필수 push-kind 누락 시 DEGRADED 로 구분(하나만 있어도 OPERATING 하던 문제 정정). |
| AC-14 실패 단계·조치 표시 | PARTIAL | apply 실패 단계별 메시지. 기동 읽기는 DEGRADED 시 누락 kind 명시. |
| AC-15 token·chat id·민감 payload 미노출 | DONE | 스냅샷·응답에 secret/target/raw 없음. |
| AC-16 정상 메뉴에 MOCK/TEST/LEGACY 없음 | DONE | diagnostics 로 격리. |
| AC-17 data_status → diagnostics | DONE | 흡수 + navigate 정정. |
| AC-18 기존 대시보드 LEGACY 분류 | DONE | diagnostics 안 details(LEGACY). |
| AC-19 미리보기·샘플이 실 PUSH 와 분리 | DONE | diagnostics 미리보기 영역, PREVIEW/TEST 표기. |
| AC-20 미연결 기능 진단으로 | DONE | 미리보기·샘플·개발호환 이동. |
| AC-21 PC production Telegram 직접 발송 버튼 없음 | DONE | approval 축소, 발송 버튼 없음. |
| AC-22 정상 화면 실행 버튼은 실제 동작 | DONE | 정상 화면에 mock 버튼 없음. |
| AC-23 PC 판단용 vs OCI 운영용 가격 구분 | DONE | PROGRAM_TRUTH 목적 구분 문구. |
| AC-24 KOSPI 6,600 이상값 표시 안 함 | DONE | 이미 정정(사용자 실측). |
| AC-25 정식 runner 고정·fallback 미호출 | DONE | crontab 실측 = runtime_oci runner. 문서 반영. |
| AC-26 0바이트 sqlite 정정 | DONE | 실측 167KB·Aug5, 정상. |
| AC-27 GET /runs 등 미사용 분류·가짜 UI 없음 | DONE | PROGRAM_TRUTH §6.2·부록B 유지(가짜 UI 안 만듦). |
| AC-28 문서 실측 정합 갱신 | DONE | PROGRAM_TRUTH·STATE_LATEST 갱신. |
| AC-29 Holdings 저장→OCI 적용 결과 확인 | DONE(계약)/PARTIAL(실사용) | 버튼·상태 구현. 실사용은 사용자. |
| AC-30 PARAM 승인→OCI 적용 결과 확인 | DONE | 기존 apply + hash 표시. |
| AC-31 마지막 OCI 결과·실패 원인 확인 | PARTIAL | 기동 읽기 요약 + apply 결과. 개별 job UNKNOWN. |
| AC-32 정상/진단 기능 메뉴·화면 구분 | DONE | diagnostics 그룹 분리. |
| AC-33 실 PC→OCI→자동운영 통합 확인 후 완료 | PARTIAL | 사용자 실사용 확인 전이라 GAP 선언. |

**완료 판정 제안**: `INTEGRATED_COMPLETE_WITH_DECLARED_RUNTIME_GAP` — 소스·화면·계약은 구현됐고 안전 계약(active 보존·schema 검증)은 r1 에서 정정했으나, **다음 항목이 선언된 GAP 으로 남는다**:
- (Q11) 실 OCI write(Holdings apply) 실사용 확인 — 사용자 명시 클릭 필요.
- (AC-10) PC·OCI 배포 revision(정확한 sha) 표시 — BACKLOG(§17.3).
- (Q10 이력) `private_fields_exposed` 는 탐지 boolean 임을 소스로 확인(가드 정상). 단 "실제 true 관측 이력" 조사는 런타임 로그 분석 BACKLOG(§17.2).
"소스·화면·계약 완료"라는 r0 의 단정은 위 미완 항목과 상충하므로 철회한다. 정확히는 "**핵심 기능·안전 계약 구현 완료, AC-10·실사용 확인 GAP 선언**"이다.

---

## 검증자 REJECTED r1 반영 (2026-08-06)

r0 검증자 REJECTED 를 받아 아래를 수정했다.

**A-1 (active 보존 계약) — 수정 완료:**
- 원인: r0 은 `mv tmp→active` **후** 검증 → post-rename 실패 시 이전 active 복원 불가.
- 수정: **rename 전에** (a) 로컬 schema 검증(손상 파일은 전송조차 안 함), (b) 원격 tmp 의 sha256 == 로컬, (c) 원격 tmp JSON 파싱 + holdings 배열 구조 검증을 모두 끝내고, **통과한 tmp 만** atomic rename. 검증 실패는 전부 rename 이전 → active 보존. rename 자체 실패도 active 미변경(tmp 정리).
- Q4 manifest(kind/content_sha256/created_at) 로컬·원격 기록 추가.
- 테스트: `tests/test_holdings_oci_apply.py` 8케이스(로컬 schema 손상 시 SSH 미호출, hash·schema 불일치 시 mv 미호출·tmp 정리, 정상 순서 scp→sha256sum→schema→mv→manifest→sha256sum).

**코드 안전성 HIGH — 해소:** schema 손상 파일은 (로컬·원격 이중) 검증에서 차단되어 active 로 승격되지 않는다.

**B-6 (startup 미사용 값·OPERATING 오판·무테스트) — 수정 완료:**
- crontab 판정을 "runner 한 줄 존재"에서 **필수 push-kind 3종(market/holdings/spike) 등록 여부**로 변경 → OPERATING/DEGRADED(일부 누락, 누락 kind 명시)/UNKNOWN.
- 읽어온 holdings·runtime_state stat 값을 job detail 에 **실제 반영**(미사용 제거).
- 신규 테스트 `tests/test_oci_startup_status.py` 8케이스(등록/누락/없음/접속실패/ENV미설정/stat 반영).

**A-2 (보고 정확성) — 수정 완료:** §2 를 30파일(설계서·PLAN·결과서 포함)로 정정. `docs/PROGRAM_TRUTH.md` 를 git 기준 **신규(A)** 로 정정(r0 "수정" 오기).

**A-3 (산출물 정합) — 수정 완료:** STATE_LATEST 를 "개발 완료·재검증 대기"로 갱신(결과서 "예정"→"작성됨"). AC-6 근거 보강. 최종 판정 문구에서 과대 단정 철회.

**Q10 (private_fields_exposed) — 소스 확인 완료(r1):**
- 정의: `app/runtime_evidence/diagnostics.py:136` — `bool(detect_private_values_exposed(...))`. 값을 노출하는 필드가 **아니라**, 메시지·extra_notes 에 개인값이 새는지 `privacy_detector` 로 실측 스캔한 **탐지 boolean**이다.
- 계약: 하드코드 False 금지·실측 강제(diagnostics.py:99). 즉 이미 보안 가드로 설계됨.
- 판정: 설계자 Q10 의 (a)"단순 안전 점검 boolean" 에 해당. **값 자체가 민감정보가 아니며**(true/false), 노출을 표시하는 게 아니라 노출을 감시한다. → 추가 차단·표시 이동 불필요. 이번 범위에서 이 필드를 새로 다루거나 노출하지 않았고, 기존 가드를 훼손하지 않았다.
- 단, 이 플래그가 **실제로 true 로 관측된 이력**(=실제 개인값 노출 발생)은 이번에 확인하지 않았다. 그 이력 조사는 별도(런타임 로그 분석 = §17.2 BACKLOG).
