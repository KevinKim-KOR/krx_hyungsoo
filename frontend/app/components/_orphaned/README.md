# _orphaned — 참조 끊긴 구 컴포넌트 보관

이 폴더는 **더 이상 어디서도 import 되지 않는** 구 컴포넌트를 삭제 전 임시 보관하는 곳이다.
빌드·타입·테스트에 영향이 없는지 확인 후, 추후 사용자 판단으로 삭제한다(사용자 방침 2026-08-02).

## 보관 사유

| 파일 | 사유 (출처 = 사유 앞에 적은 단계 · 적지 않은 행은 POC3-05 DESIGN_V2) |
|---|---|
| `HoldingsClient.tsx` | "보유·자료 관리" 4하위 화면 분리로 HoldingsView 가 재작성되어 참조가 끊김. 입력·저장·평가·초안 생성을 한 컴포넌트에 담던 구 화면. 입력·저장은 `HoldingsManageView`, 평가·시세는 `HoldingsView`, 초안 생성은 §4.6에 따라 C구간에서 OCI 로 이동 예정. |
| `HoldingsMarketEvidenceCard.tsx` | 위 `HoldingsClient` 에서만 참조되던 "보유 vs 시장 Evidence" 카드. §4.4·Q2 로 그 고유 정보(NAV·괴리율·구성종목·중복률)는 `확인 근거` 선택 상세로 통합됨. |
| `ReferenceDateDialog.tsx` | **POC6-33(설계자 PLAN 판정 2026-11-18 · Q17 · Q46 · PLAN V1 M1 · M2 · I-1).** 「종목 관리」 상단 [가격 비교 기준일 설정] 일괄 버튼을 내려 이 창(POC5-07 일괄 설정)과 창 전용 대상 고르기 함수 `referenceTargets` 를 함께 보관. 내린 이유 = 보유 기간이 모두 기준일을 가져 일괄 대상이 0건이고(버튼이 안내만 보임) 같은 저장을 History 기간마다 1건(`holdings_manage/ReferenceDateEditor.tsx` · 화면 '비교 시작일' · [수정/해제] · 기준일 없는 새 잔고 등록 기간 포함)으로 할 수 있음. 백엔드 다건 경로(PUT `/holdings/trade-history` action `reference_date` · 대상 1 ~ 200 · 한 번 저장)와 저장된 날짜는 그대로이고 `tests/test_poc5_07_reference_date.py` 가 계속 확인. 옮길 때 바꾼 것 = 상대 import 경로(`../holdings_manage/Dialog` · `../holdings_manage/format`)뿐. 이 창 · 함수의 화면 시험은 보관 폴더 정의(import 없음)에 맞춰 `holdings_manage/ReferenceDate.test.tsx` 에서 뺐다 — 다시 쓰면 그 시험을 POC5-07 커밋 `89f90f0f` 판에서 되살린다. 결정 기록 = `docs/KILL_SWITCHES.md` KS-2 판정 기록(2026-11-18). |

## 주의

- 이 폴더의 파일은 **운영 경로에서 사용되지 않는다.** 새 화면이 이들을 다시 import 하면 안 된다.
- 삭제 시 함께 정리: 이 파일들만 참조하는 자산이 남아 있는지 재확인.
