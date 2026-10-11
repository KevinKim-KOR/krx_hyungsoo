# POC5-UI-01 개발 기록 — 버튼 크기 통일 (큰 48px 기본 · 중간 40px)

작성 2026-10-11 · 작성자: 개발자(VSCode Claude) · 지시: 설계서 `docs/ai_design/POC5/POC5-07_HOLDINGS_REFERENCE_DATE_DESIGN_V1.md` §10-3(설계자 PLAN 왕복 없음 · 사용처 → 두 크기 매핑과 변경 파일을 짧게 기록)

```text
STATUS     = DONE_USER_CONFIRMED — 화면 전용 · 측정 완료 · 사용자 실화면 확인 완료(2026-10-11 "다 괜찮습니다" · 선택 묶음 제외 판단 포함) · 별도 커밋(설계 §10-3 · 검증자 · 설계자 재왕복 없음)
SCOPE      = frontend 스타일 · 버튼 사용처만(API · 데이터 · 저장 · ML · OCI 변경 0 · 백엔드 전체 회귀 · OCI pull 불필요 — §10-3)
CHECKS     = vitest 32파일 394 passed · tsc exit 0 · eslint exit 0 · 헤드리스 Chrome 크기 측정(§3)
```

## 1. 두 크기와 매핑

| 크기 | 기준 | 적용(클래스 · 사용처) |
|---|---|---|
| **큰 버튼(기본)** | 높이 48px · 글자 16px · 좌우 16px | 기본 `button` 규칙 자체 — 클래스 없는 실행 버튼 전부(저장 · 실행 · 적용 · 새로고침 · 넘기기 · 승인 · 대화창 아래 동작) · `button.reject`(기각 · 행 추가 · 정정 취소 · 상태 새로고침 · 보유 현황 보기) · `button.hmx-ghost`(대화창 아래 취소 · 「종목 관리」 머리 입력 정정 · 가격 비교 기준일 설정) · `button.ar-ghost`(원장 새로고침) · `.wb-btn`(ETF 비교하기 머리) · `.tc-btn` · `.tc-btn-link`(오늘의 투자 점검) · `.dashboard-flow-btn` · `button-primary` |
| **중간 버튼** | 높이 40px · 글자 14px · 좌우 12px | 공통 규칙 하나: `button.btn-md` · `button.hmx-btn-sm`(보유 줄 매매 · History · 과거 보유 History · 재매수 · History 기간 시장 흐름 보기 · 재진입 검토 · 기록 정정 · 취소 · 기준일 수정/해제 · 이동 링크) · `button.ar-btn-sm`(이전 날 · 다음 날 · 자세히 보기) · `button.link-button`(상세 펼치기) · `.dashboard-exception-btn` · `.wb-attn-btn`(줄 안 보조 동작) |
| 아이콘만 있는 버튼 | 그 단계 높이와 같은 너비 = 40 × 40 | `button.hmx-x`(창 닫기) · `button.hm-del`(입력 정정 표 줄 삭제) · `button.toggle-btn`(▶ 펼치기) |
| **대상 아님(그대로)** | 기존 크기 유지 | 메뉴 `.sidebar-menu-btn` · `.sidebar-group-title` / 탭 `.decision-tab-btn` · `.wb-tab` · `button[role="tab"]`(요즘 잘 오르는 ETF 카드 · 표 · 보유와 비교) / 선택 묶음 `.wb-filter` · `.holdings-sort-seg button`(정렬) · `.ar-seg button`(종류) · `.ar-fb-row button.ar-fb-btn`(평가 선택) · `.hmx-seg button`(최초 매수 / 잔고 등록 · 매매 종류 · 같은 날 앞 / 뒤) · `.hre-quickview button`(전체 / 자료 확인 필요) / 링크형 `.tc-linklike` · `.hmx-rv-back` |

- 선택 묶음(정렬 · 보기 · 종류 · 평가 선택)은 설계 §10-3 '메뉴 · 탭 · 링크의 탐색 구조는 대상 아님'과 같은 탭형 선택 컨트롤로 보고 제외했다(개발자 판단 · 사용자 확인 대상 §4).
- 같은 클래스라도 역할이 다른 곳은 사용처에서 바꿨다(아래 §2).

## 2. 변경 파일

- `frontend/app/globals.css`: 기본 `button` = 큰 버튼(min-height 48 · padding 0 16 · 16px · line-height 1.25) · 파일 끝 POC5-UI-01 블록(중간 공통 규칙 1개 · 아이콘 40 × 40 · 제외 규칙 — min-height 0 · 줄 높이 원래대로 · 메뉴 / 탭 글자 14px) · 720px 이하 `.hmx-row-actions` 줄바꿈 · 기존 개별 크기 선언 삭제(`hmx-btn-sm` · `ar-btn-sm` · `wb-btn` · `wb-attn-btn` · `tc-btn` · `dashboard-flow-btn` · `dashboard-exception-btn` · `toggle-btn` · `hm-del` · `hmx-x` 의 padding / font-size / 크기 — 색 · 테두리는 그대로).
- `holdings_manage/HoldingsBookSection.tsx`: 머리 [새 보유 추가] · [입력 정정] · [가격 비교 기준일 설정] → 큰 버튼(작은 클래스 제거).
- `holdings_manage/ReentryMlPanel.tsx`: [ML 검토 실행] → 큰 버튼(분석).
- `holdings_manage/ReentryReviewDialog.tsx`: 창 아래 [매매(매매 창)] / [재매수(매매 창)] → 큰 버튼.
- `alert_records/FeedbackForm.tsx`: 평가 [저장] → 큰 버튼.
- `JudgmentWorkbenchView.tsx`: 선택 상세 안 [ETF Exposure 상세 →] · [Market Discovery →] → 중간(`btn-md`).
- `RelativeUpsideRunCard.tsx` · `ThreePushParamCard.tsx` · `HoldingsCompareView.tsx`: 인라인 padding 제거 → 큰 버튼(점수 계산 · OCI 전달 · 보유 비교 조회).
- `holdings_compare/SelectedDetail.tsx`: [세부 근거 펼치기] 인라인 padding · 글자 제거 + `btn-md` → 중간.

## 3. 측정(헤드리스 Chrome · 실제 `globals.css` 를 읽은 시험 페이지 · 변경 전 = HEAD 의 globals.css)

| 대상 | 변경 전(높이 × 너비 · 글자) | 변경 후 |
|---|---|---|
| 기본 · reject · hmx-ghost · ar-ghost | 37 ~ 39 · 14px | **48 · 16px** |
| wb-btn · tc-btn · dashboard-flow-btn | 23 · 37 · 28 / 12 · 15 · 13px | **48 · 16px** |
| hmx-btn-sm · ar-btn-sm · dashboard-exception · wb-attn · wb-btn btn-md · link-button | 23 ~ 37 / 12 ~ 14px | **40 · 14px** |
| hmx-x · hm-del · toggle-btn | 24×24 · 28×38 · 19×18 | **40 × 40**(글자 크기 그대로) |
| 제외 11종(메뉴 · 탭 · 선택 묶음 · 링크형) | — | **전부 변경 전과 같음**(높이 · 너비 · 글자) |

- 처음 측정에서 정렬 버튼(32 → 29)과 왼쪽 메뉴 글자(14 → 16px)가 달라져, 제외 규칙을 '줄 높이 원래대로(revert · 정렬 버튼은 자체 `font: inherit` 유지)' · '메뉴 14px' 로 고친 뒤 다시 재어 같음을 확인했다.

## 4. 사용자 확인(2026-10-11 · 완료 — 아래 항목 모두 "다 괜찮습니다")

1. **실화면(대표)**: 「종목 관리」 보유 줄(매매 · History 중간) · 머리 버튼(큰) · 매매 / 새 보유 / 기준일 창 아래 버튼(큰) · History 안 버튼(중간) · 「받은 알림 기록」 원장 새로고침(큰) · 날짜 이동(중간) · 좁은 폭(720px 이하에서 버튼 줄 줄바꿈 · 가로 넘침 없음).
2. **판단 확인**: 정렬 · 보기 전환 · 종류 선택 같은 '선택 묶음' 버튼은 탭처럼 보고 크기를 바꾸지 않았다 — 이것도 맞추길 원하면 알려 주시면 된다.
3. 버튼이 커져 일부 표 줄(입력 정정 표 줄 삭제 × · 확인 근거 ▶ 펼치기)이 조금 높아진다.
