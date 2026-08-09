# POC3-07 Closeout · 인계 (PC 운영 연결·운영/진단 화면 분리 통합)

- 작성일: 2026-08-06
- 상태: **검증자 VERIFIED · PASS** (위험수준 NONE)
- 성격: 통합 개발(A·B·C 3축) + 검증자 REJECTED r1~r7 반영 완료
- 설계서: `docs/ai_design/POC3/PC_OCI_OPERATIONS_AND_DIAGNOSTIC_SEPARATION_INTEGRATED_DESIGN_V1.md`
- 개발 PLAN: `docs/ai_plan/POC3/POC3-07_..._PLAN_V1.md`
- 개발 결과서: `docs/ai_result/POC3/POC3-07_..._RESULT.md`

---

## 1. 무엇을 했나 (3축)

**A. 문서 정정** — PROGRAM_TRUTH 를 OCI RUNTIME_VERIFIED·OPERATING 으로 정정(사용자·개발자 OCI 실측 반영), KOSPI 데이터 정상 확인, STATE_LATEST 갱신.

**B. 화면 분리 + 기동 시 1회 OCI 읽기**
- 메뉴 10키: `dashboard`·`data_status` 제거 → **`diagnostics`(진단·상태)** 신설·흡수. `approval` → `승인·적용` 역할 축소.
- PC 백엔드 **lifespan 에서 OCI 상태 SSH 읽기 1회**(읽기 전용, 실패해도 기동 안 막음). `GET /oci/startup-status` = 기동 캐시 반환(재조회 없음).
- 첫 화면(오늘의 투자 점검)에 OCI 상태 한 줄 + 진단·상태 링크.
- crontab 판정: 필수 push-kind 3종 등록 여부로 `OPERATING`/`DEGRADED`/`UNKNOWN` 구분.

**C. Holdings·PARAM 명시적 OCI 적용**
- `POST /holdings/apply`: **단일 payload 정본** 구조 — 임시전송 → hash·schema 검증 → **단일 atomic replace(mv)** → active 재독출 hash 확인. 별도 manifest 파일 없음(설계자 확정). 실패 시 기존 active 보존.
- PARAM 적용은 기존 `/three-push/param/apply` 재사용 + `content_sha256` 표시.

## 2. 신규 진입점 (다음 세션이 알아야 할 계약)

| 신규 | 내용 |
|---|---|
| `GET /oci/startup-status` | 기동 시 1회 읽은 OCI 상태 캐시 반환. 요청·새로고침으로 재조회 안 함(설계자 Q2) |
| `POST /holdings/apply` | Holdings 명시적 OCI 적용(단일 payload atomic replace). 사용자 명시 클릭만 |
| `app/oci_startup_status.py` | 기동 읽기 모듈(읽기 전용 SSH) |
| `app/holdings_oci_apply.py` | Holdings 적용 모듈. **manifest 파일 안 만듦 — 정본은 payload 1개** |
| `frontend .../DiagnosticsView.tsx` | 진단·상태 화면(기동 OCI 상태·DataStatus·미리보기/샘플·LEGACY 대시보드 흡수) |

## 3. ⚠️ 남은 GAP (사용자 몫 · 설계자 인지 필요)

- **실전 OCI write 미검증(Q11)**: `종목 관리 > OCI 적용` 버튼은 프로덕션 OCI 에 실제 write 하므로 개발자는 dry-run·단위테스트까지만 했다. **사용자가 화면에서 명시적으로 눌러 최종 확인 필요.** 실패해도 기존 active 보존되도록 구현됨.
- **첫 화면 OCI 한 줄 / 진단·상태 실화면 확인**: 레이아웃·문구는 자동 테스트 미탐지 → 실화면 확인 권장.
- **`InfoPushGuideCards.tsx` 고아**: approval 축소로 미참조. 삭제 여부 사용자 지시 대기(POC3-05 `_orphaned/` 패턴처럼 처리 가능).
- **AC-10 배포 revision 표시**: BACKLOG(§17.3).
- **`private_fields_exposed`**: 노출 탐지 boolean 임을 소스 확인(이미 가드). 실제 true 관측 이력 조사는 로그분석 BACKLOG(§17.2).

## 4. 이번에 얻은 교훈 (메모리 반영)

- **[[feedback_enumerate_layers_before_guard]]**: r1~r5 핑퐁 근본 = "payload·manifest 2파일 정합"을 반쪽씩 고침. 파일시스템은 2파일 동시 원자 교체 불가 → **두 번째 객체를 없애** 근본 해결(manifest 파일 제거).
- **[[feedback_no_change_confirmed_plan]]**: r2 에서 확정 PLAN 을 임의 변경 → REJECTED. AC/안전성 지적은 PLAN 을 지우지 말고 구현으로 성립시킨다.
- **[[feedback_no_head_sha_in_result_doc]]**: r6·r7 = 결과서에 "현재 HEAD=SHA" 자기참조 → 항상 stale. 과거 라운드 SHA 만 적고 HEAD 는 `git log` 실측.

## 5. 커밋 (라운드별)

`37c310f2`(기준) · `30acd561`(A) · `fdced239`(B) · `b39cc7c1`(C) · `5dc8e852`(결과서) · `06c856eb`(r1) · `6536b29d`(r2) · `8f31fdeb`(r3) · `c52251ae`(r4) · `997bdf9f`(r5) · `686fa47c`(r6) · `96a4a414`(r7) · +Closeout.
최신 HEAD 는 `git log --oneline -1` 로 실측.

## 6. 다음 게이트

설계자 Closeout: 통합지도상 다음 실제 Step 확정. (그리드 디자인 개선 backlog 포함 — `project_krx_grid_design_backlog` 참조.)
