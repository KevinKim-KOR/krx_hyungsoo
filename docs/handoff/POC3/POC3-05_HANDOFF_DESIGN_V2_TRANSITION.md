# POC3-05 인계 — DESIGN_V2(화면 분리) 전환 시점

작성: 2026-08-02 · 이전 세션이 응답 출력 오류로 중단되어 인계.

## 한 줄 상태
POC3-05 = **DESIGN_V2 수신·저장 완료 · PLAN_V2 작성 대기.** V1 방식(한 화면)으로 만든 B구간 구현물은 삭제하지 말고 재사용 대상. 아직 아무것도 커밋 안 함(HEAD=`bd7802ba`).

## 지금까지 확정된 사실 (다시 조사 불필요 — DESIGN_V2 §5)
- 이 Step은 `보유·자료 관리` 그룹 아래를 **4개 하위 메뉴로 분리**하는 것: `보유 현황`(기존 `holdings`) / `종목 관리`(신규 `holdings_manage`) / `확인 근거`(신규 `holdings_evidence`) / `데이터 상태`(기존 `data_status`).
- **V1의 "신규 route 금지"는 폐기됨** — V2가 신규 key 2개(`holdings_manage`·`holdings_evidence`) 명시 허용. MenuKey 9→11개. `내가 가진 ETF` 부모 메뉴는 두지 않음(2단계 구조).
- 급락(falling) 신호 = 자동 조회 GET 계약 부재 → 이번 Step 제외(BACKLOG). `topn_match` 미사용.
- evidence 조회는 `GET /holdings/enriched` + `GET /holdings/market-evidence/latest` 2개(N+1 없음). 평가액·비중(`market_weight_pct`)·손익은 enriched, 5일·20일·KODEX200 대비는 evidence `short_term_momentum`.
- 자동 초안 생성(`저장된 보유 종목으로 초안 만들기`, HoldingsClient) = Holdings 3화면에서 **제거** → OCI 적용·알림 미리보기 영역으로 귀속(§4.6).

## 문서 위치 (정합 완료)
- 설계서 정본: `docs/ai_design/POC3/POC3-05_..._DESIGN_V2.md` (533줄, 인코딩 정상 — 방금 사용자 정본으로 교체 완료)
- V1 설계서: `docs/ai_design/POC3/POC3-05_..._DESIGN_V1.md` (사실확인 근거로 보존, 구현 기준 아님 — §8.2)
- PLAN_V1: `docs/ai_plan/POC3/POC3-05_..._PLAN_V1.md` (커밋됨 `bd7802ba`. 사실확인 근거로 보존)
- **PLAN_V2: 아직 없음 — 다음 세션이 작성해야 함.**

## 미커밋 변경 (B구간 V1 구현물 — 보존·재사용 대상, §8.1)
```
 M frontend/app/components/HoldingsView.tsx        (확인근거 영역 부착 — V2에선 별도 화면으로 이동)
 M frontend/app/globals.css                        (hre-* 스타일 — 재사용)
?? frontend/app/components/HoldingsRiskEvidenceSection.tsx      (읽기전용 표 — holdings_evidence 화면으로 이동)
?? frontend/app/components/HoldingsRiskEvidenceSection.test.tsx (5 케이스)
?? frontend/app/components/holdings_risk_evidence/helpers.ts    (evidence ticker 통합·5일 정렬 — 재사용)
?? frontend/app/components/holdings_risk_evidence/helpers.test.ts (10 케이스)
?? docs/ai_design/POC3/POC3-05_..._DESIGN_V2.md   (설계서 정본)
```
- 전체 vitest 123 passed(마지막 실행). tsc 0·eslint 0.
- **HoldingsView.tsx**: V1에서 `<HoldingsRiskEvidenceSection/>`를 붙였는데, V2에선 이걸 `holdings_evidence` 별도 화면으로 옮기고 HoldingsView(=`보유 현황`)에선 떼야 함.

## 다음 세션 할 일 (순서)
1. **레드팀 상태 확인**: DESIGN_V2 상태 = "레드팀 검토 대기". 사용자가 앞서 "레드팀 통과로 간주"라 했었으나, V2는 새 문서라 재확인 필요. 사용자에게 물을 것.
2. **PLAN_V2 작성** (설계서 §8.2·§9-A): 현재 변경 파일·구현 완료부·재사용 컴포넌트·이동/삭제할 mount 지점 기록 + 모호점 질문. 전수 재조사 금지(§5).
   - 사실확인 대상(§9-A): `LeftSidebar.tsx`(MENU_GROUPS manage 그룹·MenuKey union·ALL_MENU_KEYS — 여기에 2 key 추가), `MainPanel.tsx`(switch 분기·2 case 추가), `HoldingsClient.tsx`(초안 생성 L207·L376 제거 대상), `assertMenuGroupsCover`(11개 무결성 자동 검증).
3. PLAN_V2 확정 → **PLAN_V2 먼저 커밋**(개발과 분리, 설계자 방침).
4. A(보존 목록·메뉴 계약 확정) → B(4하위 화면 분리) → 사용자 확인 → C(Dashboard·Workbench·초안이동 연결) → 사용자 확인 → 전체 검증.

## 실측 근거 (PLAN_V2에 쓸 것)
- LeftSidebar `manage` 그룹: 현재 `holdings`("내가 가진 ETF") + `data_status` 2개 → V2는 `holdings`(보유 현황)·`holdings_manage`·`holdings_evidence`·`data_status` 4개.
- `assertMenuGroupsCover`(POC3-03에서 만든 fail-closed 무결성): `ALL_MENU_KEYS` 배열에 2 key 추가하면 11개 자동 검증. 누락/중복 시 throw.
- MainPanel switch: `case "holdings"`(HoldingsView)·`case "data_status"`(DataStatusView) 존재 → `holdings_manage`·`holdings_evidence` 2 case 추가 필요.
- HoldingsClient 초안 생성: `generateDraftFromHoldings`(L207) + 버튼 "저장된 보유 종목으로 초안 만들기"(L376).

## 주의 (반복 실패 방지)
- V2 AC 21개 중 하나라도 미충족이면 PASS 아님. 특히 AC-3(11 MenuKey 1회 귀속)·AC-16(초안 생성 Holdings 제거+중복 0)·AC-18(신규 key 2개만).
- 결과서에 코드 동작 쓸 때 실제 코드 재확인 후 서술(줄 수 절대값은 LF/CRLF로 재현 불가 → 보고 생략).
- 설계서 §11 복귀 조건 8개 중 하나라도 걸리면 자체 판단 말고 설계자 복귀.
