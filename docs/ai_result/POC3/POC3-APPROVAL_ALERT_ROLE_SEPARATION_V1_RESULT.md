# 승인·알림 화면 역할 분리 및 재배치 — 개발 결과서

* 문서 종류: 개발 결과서 (검증자 입력 · 설계자 전달)
* 대응 설계서: `docs/ai_design/POC3/POC3-APPROVAL_ALERT_ROLE_SEPARATION_V1_DESIGN_V1.md`
* 대응 개발 PLAN: `docs/ai_plan/POC3/POC3-APPROVAL_ALERT_ROLE_SEPARATION_V1_PLAN_V1.md`
* 작성일: 2026-08-01
* 기준 revision: `041a8c2a` → 결과: PLAN `48af5052` · A `13d2cc38` · B `62290a18` · C(본 커밋 예정)
* 상태: **IMPLEMENTED · A·B·C 사용자 실화면 확인 완료** — 검증자 전체 검증 대기(설계서 §7: C 통과 후 전체 검증). 개발자 PASS/DONE 선언 아님.
* 성격: 기존 화면(approval key·ApprovalTelegramView) 재배치. 신규 화면·메뉴·route·API·DB·backend 0건. 독립 Operations Panel 제외·폐기.

---

## 0. 설계 전제 정정 (Q1 — 검증자 필독)

- **설계서 §4는 "판단 초안 승인·거절" 을 한 역할로 두었으나**, 실측 결과 현재 계약(`Run.push_kind`)에는 **"투자 판단 초안" 을 식별할 필드가 없다.** push_kind 3종(`holdings_briefing`/`market_briefing`/`spike_or_falling_alert`)은 **모두 정보 PUSH** 다.
- **설계자 확정(Q1-c)**: 현재 run 중 투자 판단 초안으로 분류할 수 있는 것 없음 → 이번 구현에서 **판단 초안 영역·"승인 대기" 표현·빈 자리표시자를 만들지 않는다.** 화면 명칭 = **`OCI 적용·알림`** (내부 `approval` route key 유지). 판단 초안은 실제 식별 계약 마련 단계에서 연결.
- 이로써 설계서 §5.2 "왼쪽=판단 초안(RunPanel)" 배치는 폐기되고, RunPanel 은 "미리보기·수동 전달 점검"(B)으로 이동했다.

---

## 1. 처리한 요구사항 (A·B·C)

### A구간 — 운영 기능 역할 정리 (commit `13d2cc38` · 사용자 확인 통과)
- 화면 명칭 `Approval / Telegram` → **`OCI 적용·알림`**. 역할 안내(OCI 적용 / 정보 PUSH) 2칸.
- OCI 운영 기준 적용(ThreePushParamCard) 주 작업 배치 — create→approve→sync→verify·실패 보호 계약 불변.
- 정보 PUSH 3카드(시장 흐름·보유 종목·급등락) = 운영 방식 안내만. "자동 발송·메시지별 승인 없음". 실측 상태(정상/운영 중/최근 성공) 미표시(Q4).
- 판단 초안 영역·승인 대기 표현·빈 자리표시자 미생성.

### B구간 — 수동 점검과 현재 run 정리 (commit `62290a18` · 사용자 확인 통과)
- `ThreePushDraftCard`·`RunPanel` → **`미리보기·수동 전달 점검`** 영역(자동 PUSH 와 문맥·시각 구분).
- 현재 run 1건만 `현재 미리보기·수동 처리 상태` 에 push_kind 라벨과 함께 표시(Q5-a).
- `push_kind=null` run → 개발·호환 점검에 `종류 확인 불가 — 기존 기록`(Q2-b, 임의 분류 금지).
- 자동 발송 이력처럼 보이는 표현 없음(조회 API 부재).

### C구간 — 잘못 배치된 기능 이동·전체 정리 (본 커밋 · 사용자 확인 통과)
- `UniverseRefreshPanel`(신규 ETF 관찰 후보) → `OCI 적용·알림`에서 제거 → `요즘 잘 오르는 ETF`(MarketDiscoveryView) "최신 시장 데이터 갱신" 다음에 배치. **정확히 1곳(중복 0)**. 두 갱신 차이 명시(Q6).
- 개발·호환 점검 기본 접힘(DevCompatSection · details).

---

## 2. 사용자 지시 UI 개선 (설계 범위 확인 · 결과서 구분 기록)

> A·B 확인 중 사용자가 실화면에서 직접 지시한 개선 2건. 기능·백엔드·계약 불변, 표시만.
1. **`현재 운영 기준` 컴팩트화**: ThreePushParamCard 의 현재 적용 기준·OCI 반영 상태·마지막 적용 시각을 세로 4줄 → **한 줄**로. (사용자: "굳이 개행까지 할 필요 없다")
2. **OCI 적용 실패 안내**: `적용 실패` 상태일 때 "OCI 연결 없는 환경에서는 실패할 수 있고 기존 기준은 유지되며 화면 오류가 아니다" 안내 추가. (사용자: 로컬 실패 시 안내를 친절히) — apply 계약·실패 보호 불변.

> 참고: OCI 적용 실패 자체는 로컬에 `ssh oci-krx` 대상이 없어 나는 **기존 환경 문제**이며 이번 작업과 무관(백엔드 `/apply` 는 200 으로 정제된 실패 메시지 반환, raw traceback 은 서버 콘솔 로그일 뿐 화면 미노출).

---

## 3. 변경된 파일 (실측)

신규:
- `frontend/app/components/approval/OciAlertHeader.tsx` (A · 화면 역할 안내)
- `frontend/app/components/approval/InfoPushGuideCards.tsx` (A · 정보 PUSH 안내 3카드)
- `frontend/app/components/approval/ManualPreviewSection.tsx` (B · 미리보기·수동 전달 점검)
- `frontend/app/components/approval/DevCompatSection.tsx` (B · 개발·호환 점검)
- `frontend/app/components/approval/pushKindLabel.ts` (B · push_kind 라벨/판별 헬퍼)
- `frontend/app/components/ApprovalTelegramView.test.tsx` (A·B·C 계약 테스트)

수정:
- `frontend/app/components/ApprovalTelegramView.tsx` (전면 재구성 · UniverseRefreshPanel 제거)
- `frontend/app/components/ThreePushParamCard.tsx` (컴팩트 한 줄 + 실패 안내 · 계약 불변)
- `frontend/app/components/MarketDiscoveryView.tsx` (UniverseRefreshPanel 수용 · 1회)
- `frontend/app/globals.css` (OCI 적용·알림 영역 스타일)

**MainPanel·백엔드·API·DB·화면 전환 key·데이터 계약 = 무변경(0건).**

---

## 4. 검증 실측

- **tsc 0 · eslint 0 · vitest 108 passed** (ApprovalTelegramView A 6 + B 5 + C 1 = 12 신규 · 기존 96 무손상 · act 경고 0).
- `<UniverseRefreshPanel />` 렌더 = MarketDiscoveryView **1곳뿐**(grep 실측) → AC-8·AC-10 중복·누락 0.
- KS-10: 신규/수정 컴포넌트 파일 모두 프론트 900줄 한계 이내. globals.css 는 CSS 전역 파일(KS-10 컴포넌트 기준 대상 아님). 절대 라인 수는 환경 개행(LF/CRLF) 차이로 보고 생략.
- build 미실행(dev 서버 가동 중 · `.next` 캐시 보호). dev HMR 로 실화면 확인.

---

## 5. AC 1:1 대조 (설계서 §8)

| AC | 결과 |
|---|---|
| 1 approval key·전환 경로 유지 | 충족 (route key·MainPanel 분기·draft→approval 자동이동 불변) |
| 2 신규 화면·메뉴·route 0 | 충족 |
| 3 신규 API·DB·source·factor·threshold·scheduler 0 | 충족 (backend 0건) |
| 4 판단 초안 승인·거절은 판단 초안 영역에만 | 충족 (판단 초안 영역 자체를 만들지 않음 — Q1-c. 승인/거절은 RunPanel=수동 처리 기능에만) |
| 5 ThreePushParamCard 적용 계약·실패 보호 유지 | 충족 (create→approve→sync→verify·실패 시 기존 state 유지 불변) |
| 6 정보 PUSH 영역에 메시지별 승인 문구 없음 | 충족 ("자동 발송·메시지별 승인 없음" 안내) |
| 7 자동운영 상태 ↔ 수동 미리보기 결과 구분 | 충족 (정보 PUSH 안내 vs 미리보기·수동 전달 점검 분리) |
| 8 UniverseRefreshPanel 정확히 1회 | 충족 (MarketDiscoveryView 1곳 · 실측) |
| 9 샘플·raw·호환 기능 기본 접힘 | 충족 (DevCompatSection details 기본 접힘) |
| 10 기존 실행 기능 누락·중복 0 | 충족 (ThreePushDraft·RunPanel·UniverseRefresh·Sample 모두 유지, 위치만 이동) |
| 11 frontend 테스트·lint·build 통과 | tsc/eslint/vitest 통과. build 는 dev 캐시 보호로 미실행(검증 3종 `.next` 미변경) |
| 12 A·B·C 사용자 확인 통과 | 충족 (A·B·C 각 실화면 확인 통과 2026-08-01) |

---

## 6. 통합지도·STATE 정정 (미반영 — 최종 Closeout 예정)

설계서 §10·§1에 따라 통합지도(P-04 완료·P-05 제외·폐기·POC3-04 Lane 삭제 등)·STATE 정정은 **본 작업의 착수 선행조건이 아니며 최종 Closeout 에서 반영**한다. 검증자 전체 검증 PASS 후 별도 처리.

---

## 7. 다음 게이트

- 검증자 전체 검증(A·B·C 전체) → PASS 시 설계자 최종 판정 → 통합지도·STATE Closeout 정정.
- 사용자 지시 UI 개선 2건(§2)은 설계 범위를 약간 넘으나 사용자 실화면 직접 지시 · 계약 불변 — 설계자 인지 대상.
