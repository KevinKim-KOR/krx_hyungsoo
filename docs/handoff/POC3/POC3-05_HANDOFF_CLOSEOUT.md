# POC3-05 종료 인계 — Holdings Risk Evidence (보유·자료 관리 4하위 화면 분리)

작성: 2026-08-03 · POC3-05 **PASS / CLOSED · 검증자 VERIFIED** 시점 인계.
canonical 상태 앵커는 `docs/STATE_LATEST.md` 최상단. 본 문서는 다음 Step 진입자용 요약.

## 한 줄 상태
POC3-05 = **완료.** 보유·자료 관리 그룹을 4개 하위 화면으로 분리(보유 현황·종목 관리·확인 근거·데이터 상태). 완료 revision `b431f9a6`. 사용자 최종 실화면 확인·검증자 VERIFIED 완료. 다음 Step 미확정.

## 최종 구현 요약
- **좌측 메뉴**: `보유·자료 관리` = 보유 현황`holdings` · 종목 관리`holdings_manage`(신규) · 확인 근거`holdings_evidence`(신규) · 데이터 상태`data_status`. MenuKey 9→11, `assertMenuGroupsCover()` 11개 무결성.
- **보유 현황**(`HoldingsView`): 평가 현황(EnrichedSection) + 시세 갱신. 입력폼 없음.
- **종목 관리**(`HoldingsManageView` 신규): 입력·수정·삭제·저장. 저장 후 "보유 현황 보기" 버튼(자동 전환 없음).
- **확인 근거**(`HoldingsEvidenceView`+`HoldingsRiskEvidenceSection`): 평가액·비중·손익·5일·20일·KODEX200 대비·자료 상태 표 + 선택 상세(가격 차트·NAV·괴리율·구성종목·중복률). 급락·topn 제외.
- **초안 생성**: Holdings 계열에서 제거 → `OCI 적용·알림 > 미리보기·수동 전달 점검`의 PUSH-2 버튼(`HoldingsDraftButton`)으로 이동. 기존 계약 그대로.
- **화면 이동**: 오늘의 투자 점검·Dashboard·Workbench 모두 평가→`보유 현황`, 근거→`확인 근거` 분기. `자료 확인 필요` 건수는 오늘 화면·확인 근거 화면이 동일 함수(`buildRiskEvidenceRows`) 공유.

## 문서
- 설계서 정본: `docs/ai_design/POC3/POC3-05_..._DESIGN_V2.md`
- PLAN 정본: `docs/ai_plan/POC3/POC3-05_..._PLAN_V2.md`
- 결과서: `docs/ai_result/POC3/POC3-05_..._RESULT.md` (AC 1~21 전수 PASS · FIX r1~r3 기록)
- 전환 인계(휘발성): `docs/handoff/POC3/POC3-05_HANDOFF_DESIGN_V2_TRANSITION.md` — **본 종료 인계로 대체됨. 삭제 대상**(사용자 승인 시).

## 다음 진입자 주의
- 구 컴포넌트 `_orphaned/HoldingsClient.tsx`·`HoldingsMarketEvidenceCard.tsx` 는 참조 끊긴 보관물. 새 화면이 다시 import 금지. 오류 없으면 추후 삭제(사용자 방침).
- 급락(`falling_candidate`) latest GET 계약 · 종합 위험 구간 분류 = BACKLOG(자동 조회 계약/근거 부재).
- **[설계자 전달 대기]** krx 그리드 디자인 개선 — 사용자 지목 다음 개선 후보. BACKLOG §10 기록.

## 다음 게이트
설계자가 통합지도(`POC3-00_..._MAP_V2.md`) §4 남은 Lane 중 다음 실제 Step 확정. 그리드 개선 검토 포함.

문서 끝.
