# POC3-07 PC 운영 연결·운영/진단 화면 분리 통합 — 개발 PLAN (V2 확정본)

- 작성일: 2026-08-05
- 문서 성격: 개발 PLAN (설계자 Q1~Q12 확정 + 사용자 2건 확정 + OCI 실측 반영)
- 대상 설계서: `PC_OCI_OPERATIONS_AND_DIAGNOSTIC_SEPARATION_INTEGRATED_DESIGN_V1.md`
- 기준 문서: `docs/PROGRAM_TRUTH.md`(정정본) · 2026-08-05 OCI 실측(`ubuntu@krx-alertor-vm`) · `docs/STATE_LATEST.md`(POC3-05 CLOSED)
- 작성자: 개발자(Claude)
- **상태: 확정 · 착수 가능** (설계자 "추가 모호점 없으면 구현하라" + 사용자 2건 확정 완료)

---

## 0. V1 → V2 핵심 변경 (설계자 정정 반영)

설계자가 V1 을 "OCI 모니터링을 과도하게 설계했다"고 정정. V2 는 다음을 **버린다**:
- ❌ `운영 관리` 신규 화면 — **만들지 않는다**
- ❌ 화면 진입·버튼·새로고침·타이머마다 OCI 조회 — **금지**
- ❌ job별 status 파일 신설·OCI runner 수정·로그 재구성 — **범위 아님**

V2 가 **하는 일**(3축):
1. **문서 정정**(A): PROGRAM_TRUTH 잔여 정정 + STATE_LATEST·BACKLOG 갱신.
2. **기동 시 1회 OCI 읽기**(B): PC 백엔드 startup 시 **승인된 SSH 읽기 1회** → 결과 로컬 유지 → 첫 화면에 "확인 시각 + 결과 한 줄", 상세는 `진단·상태`.
3. **Holdings·PARAM 명시적 OCI 적용**(C): 사용자 클릭 시 실제 전송·검증(모니터링과 분리). + **화면 분리**(정상 업무 / 진단·상태).

---

## 1. 기반 문서 확인 완료

- `PROJECT_ORIGIN_INTENT`·`KILL_SWITCHES`·`ASSUMPTIONS`·`DEV_RULES` 확인. 충돌 없음.
- 자동매매·신규 factor·주문 없음(§4.3 제외). KILL_SWITCHES 위반 없음.
- **KS-2**(백엔드 기능 UI 부재) 관점: 미리보기를 정상 화면에서 진단으로 옮기는 것은 설계자·사용자 확정(Q8) → KS-2 아님.

---

## 2. OCI 실측 결과 (2026-08-05, 읽기 전용 SSH · 사용자 승인 방침 옵션 B)

연결: `ssh oci-krx` → `ubuntu@krx-alertor-vm` OK.

| 확인 항목 | 실측 결과 |
|---|---|
| crontab | 활성. Market 08:00 / Holdings 09:15·12:30·15:40(slot OPEN·MIDDAY·CLOSE) / 배치 07:20 / Spike 09:30~15:20 다수. runner = `scripts/run_three_push_runtime_oci.py --push-kind …` |
| **OCI 실제 Holdings 소스** | **`state/holdings/holdings_latest.json`** (`app/holdings.py :: load()`, `HOLDINGS_FILE`). PC·OCI 경로 동일 |
| package holdings | `state/three_push/packages/latest_holdings_briefing.json`(2026-06-18, 오래됨) = **fallback**, 실제 holdings PUSH 소스 아님 |
| holdings_latest.json | OCI: 2026-07-14, 6238 bytes |
| runner ↔ holdings | runner → message builder → `holdings.load()` → `state/holdings/holdings_latest.json`. 현재가는 실행 시 실시간 조회(그래서 package 오래돼도 35종목 처리됨) |

→ **Holdings 적용의 전송 대상 = `state/holdings/holdings_latest.json`** 로 확정.

---

## 3. 설계자 확정 답변 요약 (Q1~Q12)

| Q | 확정 |
|---|---|
| Q1 | 실연동은 Holdings·PARAM 적용에만. OCI 모니터링 시스템 안 만듦. 기동 시 읽기 1회만. 완료·검증은 통합 단위, 커밋은 분할 가능, 축별 PASS 없음 |
| Q2 | OCI 상태 조회 = **PC 백엔드 기동 시 승인된 SSH 읽기 1회만**. 요청·진입·새로고침·타이머·수동버튼 실행 전부 금지 |
| Q3 | `OCI 적용` 버튼 = 실제 전송·적용(업무 실행). 저장/승인과 적용은 별도 동작. 자동 전송 금지. 적용 결과만 그 요청 응답에 표시. 적용 후 일반 상태 재조회 안 함 |
| Q4 | 복잡한 canonical revision 안 만듦. **전송 payload 바이트 SHA-256**. manifest 에 kind·content_sha256·created_at. OCI 원자 적용 후 같은 hash 를 active manifest 에 기록. PC==OCI hash 면 성공. 기존 승인 ID 는 보조 식별자로 재사용 |
| Q5 | **OCI runner 수정 안 함**. 기존 status·log·cron 근거에서 기동 시 읽을 수 있는 사실만. 구분 불가 시 `UNKNOWN` |
| Q6 | `운영 관리` 없음. 최종 MenuKey 10개(아래 §4.2). `dashboard`·`data_status` 정상 메뉴에서 제거 → `diagnostics` 흡수 |
| Q7 | `approval` = `승인·적용` 역할만. PARAM·seed 등 실제 승인 대상만. 정보 PUSH 카드·빈 승인 카드 금지. PUSH 실행 결과는 기동 상태 요약/진단에서만 |
| Q8 | 샘플·미리보기·개발호환·MOCK·placeholder·미연결 전부 `진단·상태`로. 정보 PUSH 는 발송 전 승인 업무 아니므로 정상 화면에 미리보기 둘 이유 없음 |
| Q9 | AC-24 충족 처리. KOSPI source·DB·산식 변경 없음. 기준일/장중·종가 구분은 **사실과 다른 부분만 최소 정정** |
| Q10 | `private_fields_exposed` 는 개발자가 소스에서 사실 확인. 단순 boolean 이면 민감값 없이 표시. **실제 노출이면 표시 이동 아니라 노출 차단 + 보안 결함 보고** |
| Q11 | 개발자는 dry-run·안전 계약 검증만. **실전 write 는 사용자가 화면에서 명시적 `OCI 적용` 실행**. 기존 active 보존·tmp 전송·검증 후 원자 교체·실패 시 기존 유지. 별도 PASS 아닌 통합 검증의 마지막 실사용 확인 |
| Q12 | BACKLOG 확정: 실시간 갱신·polling·수동 새로고침·장기 로그·배포 자동화·모니터링 시스템·runner status 개편 전부 제외 |

**사용자 확정 2건:**
- PARAM hash: **기존 verify 재사용**(sync 스크립트가 이미 OCI verify → `oci_verified`). hash 필드는 표시용으로만 추가. 스크립트 대규모 수정 없음.
- Holdings 적용: **OCI 실측 후 결정** → 완료(위 §2). 소스 = `state/holdings/holdings_latest.json`.

---

## 4. 개발 범위 (확정)

### 4.1 A축 — 문서 정정 (신규 md 금지, 기존 갱신)

- `docs/PROGRAM_TRUTH.md`: 잔여 정정(§14 목록의 "정정 항목" 반영). OCI = RUNTIME_VERIFIED·OPERATING 유지(이미 반영). PC 판단용 조회 vs OCI 운영용 평가 목적 구분 문구. PC 공유 발송함수 존재≠PC 정식 발송경로 표현 정정.
- `docs/STATE_LATEST.md`: POC3-07 착수·완료 상태.
- `docs/backlog/BACKLOG.md`(있으면): §17 3개 항목만 기록. (파일 없으면 생성 여부는 사용자 확인 — 신규 파일이므로.)

### 4.2 B축 — 화면 분리 + 기동 시 1회 OCI 읽기

**메뉴 재편** — 최종 MenuKey 10개(설계자 Q6):
`today_check` · `workbench` · `market_discovery` · `etf_exposure` · `ai_sessions` · `holdings` · `holdings_manage` · `holdings_evidence` · `approval` · `diagnostics`
- 제거: `dashboard`, `data_status` (→ `diagnostics` 흡수)
- 신규: `diagnostics` 1개
- `assertMenuGroupsCover` 가드·`ALL_MENU_KEYS`·`MainPanel` switch 동기 수정.

**`diagnostics`(진단·상태) 신규 화면** — 흡수 대상:
- 기존 `DataStatusView` 진단 정보
- 기동 시 OCI 상태 상세
- 샘플/미리보기(Sample draft·Market/Holdings/Spike preview·개발호환) — `approval`의 `ManualPreviewSection`·`DevCompatSection`에서 이동
- MOCK·PREVIEW·TEST·LEGACY(기존 `dashboard`)·미연결 기능

**기동 시 1회 OCI 읽기** (백엔드):
- FastAPI startup(lifespan/on_event) 에서 **승인된 SSH 읽기 1회** 실행 → 결과를 프로세스 로컬(메모리 or PC state 파일)에 유지.
- 읽는 사실(구분 가능한 것만): crontab 활성 여부, holdings PUSH 최근 status(기존 단일 status·로그), 배치 최근 실행. 구분 불가는 `UNKNOWN`.
- 실패 시 **기동 막지 않음** → `UNKNOWN` 표시.
- 첫 화면(`today_check` 상단): "OCI 확인 시각 + 결과 한 줄"만. 상세는 `diagnostics`.
- **조회 API 는 이 기동 결과를 반환**(요청마다 SSH 재실행 금지). 화면 새로고침 = 기동 시 캐시 반환.

### 4.3 C축 — Holdings·PARAM 명시적 OCI 적용

**PARAM 적용**(대부분 완성됨):
- `POST /three-push/param/apply` 이미 create+approve+sync+verify+기존 active 보존 구현.
- 추가: 응답에 `content_sha256`(표시용) — 기존 verify(`oci_verified`)를 성공 판정으로 유지. 스크립트 verify 로직 재사용.

**Holdings 적용**(신규):
- 신규 `POST /holdings/apply`(경로명 확정 전, §6 주의) — 동작: `state/holdings/holdings_latest.json` payload SHA-256 계산 → manifest(kind·content_sha256·created_at) → SCP tmp 전송 → OCI schema/존재 검증 → **atomic rename**(기존 active 보존) → OCI active hash 재확인 → PC==OCI hash 성공 판정.
- PARAM 의 `sync_three_push_runtime_param.py` 패턴과 동형(atomic·verify·실패 시 기존 유지). Holdings 전송이므로 대상 파일만 다름.
- 저장(`PUT /holdings`)과 적용(`POST /holdings/apply`)은 **별도 동작**. 자동 전송 금지. 사용자 명시 클릭만.
- `holdings_manage` 화면에 `OCI 적용` 버튼 + 적용 결과 상태(`PC_SAVED`/`TRANSFER_PENDING`/`OCI_APPLIED`/`OUT_OF_SYNC`/`APPLY_FAILED`/`UNKNOWN`).

**상태 표시 원칙**(§5.5·§6.4): PC 저장 성공을 OCI 적용 성공으로 위장 금지. 적용 실패 시 기존 OCI active 유지 + 실패 단계 표시.

---

## 5. 개발 순서 (커밋 분할 — 완료 판정은 통합 1회)

1. **A**(문서 정정) — 코드 무관, 먼저.
2. **B**(화면 분리 + 기동 읽기) — 프론트 메뉴 재편 + `diagnostics` + 백엔드 startup 읽기 + 첫 화면 한 줄.
3. **C**(Holdings 적용 신규 + PARAM hash 표시) — 백엔드 apply API + 프론트 버튼·상태.
4. 결과서 작성 → 검증자.
5. **최종 실전 검증**: 사용자가 화면에서 명시적 `OCI 적용` 실행(개발자는 dry-run·계약 검증까지만).

---

## 6. 착수 전 남은 확인 (경미 — 진행하며 확정)

이 항목들은 설계자 재량 위임(§16 "함수명·helper 위치·컴포넌트 분리·내부 호출 순서는 개발자 결정")에 해당하거나 구현 중 확정 가능. **작업 중단 사유 아님.**

1. **신규 API 경로명**: `POST /holdings/apply`·`GET /operations/startup-status`(가칭) — 기존 명명 관례(`/three-push/param/apply`) 따라 개발자 확정.
2. **기동 읽기 저장 위치**: 프로세스 메모리 vs PC state 파일. 재시작 잦지 않으니 메모리 + 선택적 캐시 파일. 개발자 확정.
3. **`diagnostics` MenuKey 문자열**: `diagnostics` 확정(설계자 Q6 명시).
4. **BACKLOG.md 신규 생성 여부**: 파일 없으면 신규 md → 신규 파일 생성은 승인 필요(§7). **없으면 STATE_LATEST 의 BACKLOG 절에 기록**하는 것으로 대체 제안(신규 md 회피). → 착수 시 파일 존재 확인 후 결정.

**중단 조건(§16) 해당 시**(예: OCI crontab 이 다른 runner 사용, atomic 적용 불가, hash 대조가 Telegram 중복 유발)에는 자체 판단 없이 설계자에게 보고.

---

## 7. 신규 파일·의존성·승인 필요 항목 (사전 고지)

- **신규 파일(코드)**: `diagnostics` 뷰 컴포넌트, Holdings 적용 백엔드 모듈/라우터, 기동 읽기 모듈. — 설계서가 명시적으로 요구한 화면·기능이므로 지시 범위 내.
- **신규 md 파일**: 원칙적으로 안 만듦(기존 갱신). BACKLOG.md 만 예외 가능 → §6.4 처리.
- **신규 의존성**: 없음 예정(SSH 는 OS `ssh`/`scp` 호출, 기존 `subprocess` 패턴 재사용).
- **프로덕션 OCI write**: Holdings 적용 실전 실행은 **사용자 명시 클릭**만(Q11). 개발자는 dry-run.
- **SSH 상시 read**: 기동 시 1회만. 앱이 상시 SSH read 하는 구조 아님(Q2).

---

## 8. 검증 계획

- 프론트: `npx tsc --noEmit` · `npm run lint` · `npx vitest run`. dev 서버 켜둔 채 build 금지.
- 백엔드: `black --check` · `flake8` · `py_compile` · `pytest -k`(관련). 전체 pytest 는 background.
- 자체 검수 6단계 + 보고 직전 `git status` staged 정합(우측 컬럼 공백·`??` 0건).
- 기동 읽기·Holdings 적용은 **dry-run/모의**로 계약 검증(실전 write 는 사용자).

---

## 9. AC 대응 (요약)

- AC-1~3(OCI 보존·자동운영 불변·PC가 job/Telegram 자동실행 안 함): B축이 읽기 전용·기동 1회라 충족.
- AC-4~9(Holdings·PARAM 적용 상태·hash·실패 시 active 보존·idempotent): C축.
- AC-10~15(운영 상태·job 구분·stale·민감정보 미노출): 기동 읽기 + `diagnostics`. job 구분 불가는 `UNKNOWN`(Q5).
- AC-16~22(화면 분리·미리보기 이동·미연결 진단 이동·PC production 발송 버튼 없음): B축.
- AC-23~28(데이터 의미·KOSPI·runner 고정·0바이트 sqlite 설명·문서 갱신): A축 + §2 실측 + Q9.
- AC-29~33(사용자 과업·통합 완료 판정): 최종 실사용 확인(Q11).

> 본 PLAN(V2)은 확정본입니다. 설계자가 요청한 "추가 모호점 없으면 구현" 조건을 충족하므로, 사용자 승인 시 A→B→C 순으로 착수합니다.
