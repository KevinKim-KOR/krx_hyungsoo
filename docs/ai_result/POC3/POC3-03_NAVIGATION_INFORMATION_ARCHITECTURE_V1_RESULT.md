# POC3-03 Navigation Information Architecture v1 — 개발 결과서

* 문서 종류: 개발 결과서 (검증자 입력 · 설계자 전달)
* 대응 설계서: `docs/ai_design/POC3/POC3-03_..._DESIGN_V1.md`
* 대응 개발 PLAN: `docs/ai_plan/POC3/POC3-03_NAVIGATION_INFORMATION_ARCHITECTURE_V1_PLAN_V1.md` (Q1~Q6 답변·보완 4항 확정 반영)
* 작성일: 2026-08-01
* 기준 revision: `3345d504` (선행 POC3-REF-02 VERIFIED / CLOSED)
* 상태: **검증자 VERIFIED (2026-08-01)** — 자동 게이트(tsc 0·eslint 0·vitest 96 passed) + 사용자 실화면 확인(AC-15) + 검증자 REJECTED r1(보고 정확성·stale 주석·B-1 fallback)·r2(줄 수·B-1 undefined→throw)·r3(KS-10 대상 오기·중복 검출 범위) 정정 후 최종 VERIFIED. 검증 대상 6종(소스 3 + 문서 3) commit + push. **POC3-03 PASS/CLOSED 는 아직 아님** — 설계서 §12 종료조건 중 통합지도 P-04 완료 반영·STATE_LATEST 갱신·설계자 최종 판정 남음(설계자 영역). 줄 수 절대값은 환경 개행(LF/CRLF) 차이로 보고 생략.
* 성격: 순수 Navigation Step. 신규 API·DB·source·산식·백엔드 0건.

---

## 0. 검증 대상 문서

- 설계서 · 개발 PLAN(Q1~Q6 답변) · 본 결과서 3종 대조.

---

## 1. 처리한 요구사항 (설계서 §2·§3·§4·§6 + AC)

- §3.1 4그룹 재편(오늘 확인/비교·판단/보유·자료 관리/승인·운영): **DONE** (+ 사용자 요청으로 §3.2 재편 → §4 참조)
- §3.2 9개 화면 key 1회 귀속: **DONE** (중복·누락·신규 0)
- §3.3 today_check 기본 진입·ETF 비교하기 첫 번째·기존 대시보드 비중심: **DONE**
- §4.1 최초 4(→5)그룹 모두 펼침: **DONE**
- §4.2 그룹 제목 접힘 토글(화면이동 X·저장 X): **DONE**
- §4.3 접힌 그룹 자동 펼침·다른 그룹 접힘 유지: **DONE**
- §5 기존 직접 이동·Context Bridge 보존: **DONE** (MainPanel 무변경·onNavigate 대상 key 전부 유효)
- §6 그룹/메뉴 정보 계층·활성 표시·접힘 표시·세로줄바꿈 방지: **DONE**
- §7 사실 확인(PLAN §1): **DONE**
- §9 신규 API/화면/key/삭제/Operations 선구현 금지: **준수**

---

## 2. 설계자 확정 답변(Q1~Q6) 반영

| 질문 | 반영 |
|---|---|
| Q1 라벨 | 메뉴명 `승인·알림`(슬래시 제거) · 그룹명 `승인·운영` · `approval` key 불변 |
| Q2 기존 대시보드 | (초기) 보유·자료 관리 마지막 → **이후 사용자 요청으로 "점검대상" 그룹 분리(§4)** |
| Q3 그룹 내 순서 | 비교·판단: ETF 비교하기→요즘 잘 오르는 ETF→ETF 구성종목→AI 투자 세션 / 보유·자료 관리: 내가 가진 ETF→데이터 상태 |
| Q4 그룹 제목 | `<button type="button" aria-expanded>` 접힘 토글 전용 |
| Q5 접힘 표시 | 텍스트 기호 `▸/▾` (외부 아이콘 라이브러리 없음) |
| Q6 승인·운영 | `승인·알림` 1개만 (Operations Panel·자리표시자 없음) |

보완 4항(최초 전체 펼침·그룹 활성 식별·다른 그룹 접힘 유지·today_check=MainPanel 책임) 전부 반영·테스트 고정.

---

## 3. 변경된 파일 (실측 · git staged 6개)

소스(3) — 절대 라인 수는 환경 개행(LF/CRLF) 차이로 재현 불가하여 생략:
- `frontend/app/components/LeftSidebar.tsx` (수정 · 컴포넌트 파일 KS-10 900줄 한계 이내): 평면 `MENU_ITEMS` → 5그룹 `MENU_GROUPS`. 접힘 `useState<Set>`·자동 펼침 `useEffect`·그룹 활성표시. **모듈 로드 시 `assertMenuGroupsCover()` 로 귀속 무결성 검증 — 각 MenuKey 가 그룹 전체(item 단위)에서 정확히 1번 나타나는지 확인. 누락(0번)·중복(2번+, 같은 그룹 내 중복 포함)·미등록 key 유입이면 첫 그룹 위장 없이 즉시 `throw`(dev/운영 동일). `groupIdOf` 는 항상 유효 그룹 id 반환(B-1 반영).** `MenuKey`·key·`onSelect`/`active` props 계약 불변. `MENU_ITEMS` 평탄화 하위호환 export 유지.
- `frontend/app/globals.css` (수정 · CSS 전역 스타일 파일 — KS-10 컴포넌트 라인 기준 대상 아님): 그룹 제목/caret/활성 그룹 스타일 · 메뉴 좌측 들여쓰기(32px) · 그룹명 15px 확대 · 세로줄바꿈 방지 · **`.app-content` 폭 1400→1920px(§4-3)**.
- `frontend/app/components/LeftSidebar.test.tsx` (신규 · 컴포넌트 테스트 KS-10 한계 이내): AC/보완/B-1 총 13 케이스.

문서(3 · 검증자 3종 대조):
- `docs/ai_design/POC3/POC3-03_..._DESIGN_V1.md` (신규 · 설계서 보존본 — 검증 대조용)
- `docs/ai_plan/POC3/POC3-03_..._PLAN_V1.md` (신규 · 개발 PLAN)
- `docs/ai_result/POC3/POC3-03_..._RESULT.md` (신규 · 본 결과서)

**MainPanel.tsx·백엔드·API·DB = 무변경(0건).**

---

## 4. 지시문 외 변경 — 사용자 실화면 지시 (검증자·설계자 필독)

> 실화면 확인 중 사용자가 직접 지시한 변경. 개발자 임의 확장 아님. **UI 최종 판단은 사용자(사용자 명시 2026-08-01).**

1. **"기존 대시보드"를 "점검대상" 그룹으로 분리** — 설계서 §3.2·PLAN Q2는 "기존 대시보드 = 보유·자료 관리 마지막"으로 확정했으나, 사용자 요청으로 **승인·운영 아래 새 그룹 "점검대상"(dashboard 1개)** 으로 이동. → **설계서 §3.2 화면 귀속을 사용자 지시로 재편.** dashboard key·기능 불변. 그룹 수 4→5. 설계자 재확인 필요 항목(§7).
2. **좌측 메뉴 위계 강화** — 그룹명 15px·진하게, 하위 메뉴 좌측 들여쓰기(32px). 친구 프로젝트 캡처의 그룹/메뉴 위계 참고(아이콘은 §9 준수로 미도입).
3. **`.app-content` 콘텐츠 폭 확대** — 1400px → 1920px, 좌우 패딩 32→40px. 사용자 고해상도(원본 2512px)에서 우측 잘림·여백 낭비 해소. **`.app-content`는 전 메뉴 공통**이라 설계서 §9("사이드바 폭·전체 레이아웃 불필요 변경 금지")를 넘는 변경이나, **사용자 직접 지시**로 진행. 사이드바 폭(220px)은 유지.

---

## 5. 검증 실측 (자체 검수 · 검증자 REJECTED r1·r2 반영 후 재실측)

- **tsc 0 · eslint 0 error/0 warning · vitest 96 passed** (LeftSidebar 13 신규 + 기존 83 무손상).
- LeftSidebar 13 케이스: 5그룹 순서·9key 1회귀속·**B-1 모든 key 정확히 1그룹(fallback 미발생 고정)**·최초 전체펼침·선택↔그룹 활성일치·접힘토글 화면전환 X·메뉴클릭 onSelect·자동펼침+다른그룹 접힘유지·AC-8 금지어(Workbench/Market Discovery/Holdings/ETF Exposure/Data Status/Operations Panel) 비노출·승인운영 1개·점검대상 위치·기존대시보드 활성그룹·라벨 슬래시 제거.
- 보존 이동 흐름(설계서 §5): onNavigate 정적 대상(workbench·market_discovery·etf_exposure·holdings·approval·ai_sessions) 전부 9 key 내 유효. MainPanel `setActive`·draft→approval 자동전환 불변.
- KS-10(프론트 **컴포넌트 파일** 900줄 한계): 대상은 `LeftSidebar.tsx`·`LeftSidebar.test.tsx` — 둘 다 한계 이내. `globals.css` 는 CSS 파일이라 KS-10 컴포넌트 라인 기준 대상 아님(전역 스타일 누적 파일). 절대 라인 수는 환경 개행(LF/CRLF) 차이로 보고 생략.
- build 미실행(dev 서버 가동 중 · `.next` 캐시 보호). 검증 3종은 `.next` 미변경.
- **B-1 fallback 제거(REJECTED r2·r3 반영)**: `groupIdOf` 가 귀속 누락 시 첫 그룹으로 위장하지 않는다. 모듈 로드 시 `assertMenuGroupsCover()` 가 **각 MenuKey 의 그룹 전체 출현 횟수(item 단위)** 를 세어 정확히 1번이 아니면(누락 0 / 중복 2+, **같은 그룹 내 중복 포함**) 즉시 `throw` + 항목 수 ≠ 알려진 key 수면 미등록 key 유입으로 `throw`. **dev·운영 동일.** 정적 구성 무결성은 이 invariant + 별도 테스트(B-1 케이스)로 이중 고정. 정상 경로에선 발생하지 않는다.

---

## 6. AC 1:1 대조 (설계서 §10)

| AC | 결과 |
|---|---|
| 1 4그룹 표시 | 충족 (사용자 재편으로 5그룹 — 점검대상 추가) |
| 2 9key 1회 귀속·중복/누락/신규 0 | 충족 (테스트) |
| 3 첫 진입 today_check | 충족 (MainPanel) |
| 4 선택↔활성 일치 | 충족 (aria-current + 자동펼침) |
| 5 접힌 그룹 자동 펼침 | 충족 (테스트) |
| 6 그룹 토글 화면전환/API/갱신 X | 충족 (테스트) |
| 7 기존 이동·Context Bridge 유지 | 충족 (MainPanel 무변경) |
| 8 내부 명칭 비노출 | 충족 (테스트 label/hint/aria 스캔) |
| 9 접힘 영구저장 X | 충족 (useState만) |
| 10 1440×900 가로 잘림 없음 | 충족 (사용자 실화면 확인 · 폭 확대로 개선) |
| 11 세로 줄바꿈 없음 | 충족 (nowrap · 사용자 실화면 확인) |
| 12 데이터 조회/저장/캐시 의미 불변 | 충족 (화면·MainPanel 무변경) |
| 13 신규 API/DB/화면/백엔드 0 | 충족 (실측 0건) |
| 14 오늘→비교→내ETF→승인 각 1클릭 | 충족 |
| 15 사용자 실화면 확인 | **충족 (2026-08-01)** |

---

## 7. 사용자 확인이 필요한 항목 / 설계자 재판정 대상

1. **"점검대상" 그룹 분리(§4-1)** — 설계서 §3.2·Q2를 사용자 지시로 재편. 설계자가 이 재편을 canonical 설계로 승인/정정할지 판정 필요. (개발자는 사용자 UI 최종 판단 원칙에 따라 반영만.)
2. **`.app-content` 폭 1920px 확대(§4-3)** — 전 메뉴 공통 레이아웃 변경. 사용자 지시이나 설계서 §9 경계를 넘으므로 설계자 인지 필요. (다른 화면들 레이아웃도 함께 넓어짐 — 사용자 실화면에서 수용.)

---

## 8. 다음 게이트

- 검증자 코드 검증 → PASS 시 설계자 최종 판정(§7 재편 2건 포함) → POC3-03 PASS/CLOSED → 통합지도 P-04 완료 반영 · STATE_LATEST 갱신 (설계서 §12).
- 검증 대상 산출물은 검증자 인계 전 staged 처리.
