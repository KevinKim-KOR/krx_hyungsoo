# POC5-24 개발 PLAN V1 — 선택 근거의 AI 투자세션 연결

작성 2026-10-18 · 작성자: 개발자(VSCode Claude) · 수신: 설계자
근거: `docs/ai_design/POC5/POC5-24_SELECTED_EVIDENCE_AI_SESSION_LINK_DESIGN_V1.md`(V1)

```text
STATUS   = 설계자 PLAN PASS(2026-10-18 · Q1 · Q2 · Q3 = (a) · 보충 §6) · 수정 목업 사용자 확인(2026-10-18) · 구현 완료 · 사용자 실화면 확인(2026-10-19) · 검증자 r1 VERIFIED(2026-10-19 · 결과서 §10) · 설계자 RESULT PASS(2026-10-19 · 결과서 §11) · IMPLEMENTED_VERIFIED_CLOSED(종료 2026-10-19) · 결과서 docs/ai_result/POC5/POC5-24_SELECTED_EVIDENCE_AI_SESSION_LINK_RESULT.md
SCOPE    = 「보유와 비교」 미리보기 버튼 줄 [AI 세션에서 검토] → 기존 「AI 투자 세션」 새 기록 저장 탭 → 기존 저장 · 기록 조회
           새 메뉴 · 표 · DB 열 · 마이그레이션 · API 경로 · 외부 호출 · 계산 · 자동 저장 · LLM · OCI · PUSH 변경 0
MEASURED = 2026-10-18 · 코드 grep / read(HEAD 089310e3)
```

## 1. 지금 AI 세션 동선 (설계 §4-1)

- **초안**: `frontend/lib/aiSessionsDraft.ts` — 브라우저 sessionStorage 한 칸(`krx_alertor.ai_sessions.draft.v3`). 넣는 곳 2곳 — 「요즘 잘 오르는 ETF」 [AI Sessions로 넘기기](`TransferToAISessionsCard` · 후보 전체 · 복사문 · 시장 문맥 · 단기 흐름 · 자료 품질 스냅샷) · 「ETF 구성종목」(구성종목 · 중복률 스냅샷). 둘 다 **기존 초안을 확인 없이 덮어쓴다**(보호 방식 없음 → Q2).
- **작성 화면**: 「AI 투자 세션」(`AISessionsView`) — 들어올 때 초안이 있으면 [새 기록 저장] 탭(`AISessionsCreateTab`): 기준일 · 필터 · 후보 요약 · 질문(초안 질문 · 편집 가능) · GPT / Gemini / Claude 답변 · 메모 · 1차 판정 · 다음 확인 항목 → [기록 저장]. 저장 조건 = 초안 있음 · 후보 1개 이상 · 질문 · 답변 1개 이상(기존 그대로). 화면은 한 번에 하나만 그려 다른 메뉴로 가면 입력 중 답변은 사라진다(기존) — 남는 것은 sessionStorage 초안뿐.
- **저장 API**: `POST /decision/sessions` → `decision_evidence.sqlite :: ai_session_records`(열 = 기준일 · source_screen(자유 문자열) · filters_json(4필터 필수) · candidate_snapshot_json(빈 목록 불가) · question_text · 답변 3 · 메모 · 판정 · next_checks · 스냅샷 JSON 6). 저장 성공 시 초안 삭제.
- **자동 보충**: 저장할 때 초안에 ML 근거가 없으면 `GET /ml/baseline-v0/evidence-snapshot`(최신 ML 기준선 보고서 · 선택 종목과 무관)을 넣는다 → 설계 §3 대로 선택 근거 모드에서만 넣지 않는다.
- **조회**: [기록 조회] — 목록(생성일시 · 기준일 · 판정 · 후보 수 · 답변 채널 · 요약 = 메모 → 답변 → 질문 앞 50자) · 상세(기준일 · 화면 · 판정 · 필터 · 후보 목록 · 질문 · 답변 · 스냅샷 JSON · 메모 · 다음 확인). **제목 칸이 없다** → 목록에서 선택 종목을 알아볼 수 없음(Q1).
- **같은 연결은 없다**: 미리보기(`DecisionDraftPreviewCard`)는 AI 세션 초안을 만들지 않는다(POC5-23 확인 그대로).

## 2. 최소 연결안 (설계 §4-2 · §3)

- **[AI 세션에서 검토]**: 미리보기가 정상 생성돼 있을 때만 버튼 줄([다시 생성] · [복사] 옆 · 중간 버튼)에 보인다. 누르면 **지금 화면에 보이는 응답 그대로** 초안을 만들고 「AI 투자 세션」으로 이동한다(재생성 · 재계산 0 · 숫자 문자열 그대로). 종목 · 종류 · 목록 조건이 바뀌면 미리보기가 비워져 버튼도 사라진다(POC5-23 그대로).
- **초안(선택 근거 모드 · 기존 v3 칸 · 선택 필드만 추가)**:
  - `source_screen` = `holdings_compare_preview`(기존 자유 문자열 열 · 새 값).
  - `question_text` = 미리보기 원문(`preview_text`) 그대로(앞뒤 글 추가 없음 · [AI에게 요청] 묶음 포함).
  - `candidate_snapshot` = 선택 종목 1건 `{rank(후보면 목록 순위 · 보유는 null), ticker, name, tags: []}` + **선택 필드 `selected_preview`** `{target_kind, generated_at, evidence_as_of{target · kodex200 · vix}, preview_text}` — 저장은 기존 `candidate_snapshot_json` 안(POC5-22 `same_period_kodex200` 선택 필드와 같은 방식 · 열 · 표 추가 없음). 처음 넘긴 원문은 여기 그대로 남고, 질문은 사용자가 편집할 수 있다(둘을 구분해 보인다).
  - `asof` = 미리보기 가격 기준일(`evidence_as_of.target_as_of_date` · 없으면 생성 날짜) · `filters` = 「보유와 비교」 화면 목록 필터 그대로(필수 항목 · Q3) · 시장 · 단기 · 자료 품질 · 구성종목 스냅샷 = 없음(null) · ML 근거 = 넣지 않음(자동 보충 생략).
- **작성 화면(선택 근거 모드에서만)**: 기준일 · 필터 · 후보 요약 자리를 '선택 종목 이름(티커) · 보유 / 후보 · 화면 목록 n위' + '미리보기 생성 · 가격 기준일 · KODEX200 · VIX' 한 줄 묶음으로, 질문 라벨 'AI 에게 보낼 질문 — 판단 근거 미리보기 원문 (편집 가능 · 넘겨받은 원문은 따로 보관)'. 카드 설명 한 줄의 출처를 'Market Discovery 에서 넘어온 후보' → '「보유와 비교」 판단 근거 미리보기에서 넘어온 선택 종목'으로(목업에서 찾음 · 그대로 두면 틀린 설명). 나머지(답변 · 메모 · 판정 · 저장)는 기존 그대로 · 이동만으로 저장하지 않는다.
- **조회**: 상세에 '넘겨받은 판단 근거 (원문)' 묶음 — 보유 / 후보 · 미리보기 생성 · 가격 기준일 한 줄. 저장 때 질문을 고쳤으면 '아래 AI 질문은 저장 때 편집됨' + 원문을 따로 보이고, 그대로면 '아래 AI 질문과 같은 글'(같은 글 두 번 안 보임). 상세의 '후보 스냅샷 (저장 시점)'은 선택 근거 기록에서만 '선택 종목 (저장 시점)' · '보유 · 이름(티커)' / '후보 · 목록 n위 · 이름(티커)'로(목업에서 찾음 · 지금은 순위 없는 보유에도 '1.'이 붙는다). 목록은 Q1.
- **Q2 확인 줄의 초안 시각**: 기존 초안의 `draft_created_at` 은 `toISOString()`(UTC) 이라 글자를 잘라 보이면 9시간 어긋난다(목업에서 찾음) → 브라우저 현지 시각 'YYYY-MM-DD HH:MM' 으로 바꿔 보인다(해석 못 하면 원문). 저장 값은 그대로.
- **기존 전체 후보 전달 보존**: 「요즘 잘 오르는 ETF」 · 「ETF 구성종목」 초안 · 저장 · 자동 보충은 그대로(새 필드가 없으면 지금과 같은 경로).

## 3. 변경 파일 · 시험 (설계 §4-3)

- 백엔드: `app/api_decision_sessions.py`(`DecisionCandidateSnapshot.selected_preview` 선택 모델 · Q1 (a) 이면 목록 응답 선택 필드) · (Q1 (a)) `app/decision_evidence_store.py :: list_recent_records`(저장된 후보 1건의 이름 · 티커를 읽어 돌려줌 · 쓰기 변경 없음).
- 프론트: `holdings_compare/DecisionDraftPreviewCard.tsx`(버튼 · 초안 · Q2 확인) · `HoldingsCompareView.tsx` · `MarketDiscoveryView.tsx`(이동 함수 전달) · `lib/aiSessionsDraft.ts`(선택 필드 · 모드 · 초안 출처 · 현지 시각 표시) · `AISessionsCreateTab.tsx`(선택 근거 모드 표시 · 카드 설명 · ML 보충 생략 · source_screen) · `AISessionsListTab.tsx`(상세 선택 종목 · 원문 묶음 · 목록 대상) · `lib/api/decisionSessions.ts`(타입).
- 시험(tmp DB · 라이브 기록 생성 없음): 미리보기 → 초안 = 응답 글 · 날짜 그대로(보유 · 후보) · 기존 초안 있을 때 확인 없이 덮지 않음 · 저장 API → 상세 재조회 = 질문 · 원문 · 답변 · 판정 · 목록 대상 · 선택 모드에서 ML 보충 호출 0 · 기존 전체 후보 전달 · 저장 · 이전 기록 조회 그대로 · 변이 · 전체 회귀.

## 4. 질문 (설계 · 현재 코드가 부딪히는 곳)

**Q1. 목록에서 선택 종목 알아보기.** 세션에는 제목 칸이 없고 목록 요약은 메모 → 답변 앞 50자다(답변 1개 이상이 저장 조건이라 질문 첫 줄은 거의 안 보임).
(a) **권장** — 목록 응답에 선택 필드 `target_label`(저장된 후보가 1건인 선택 근거 기록만 '이름(티커)' · 저장 구조 변경 없음 · 읽을 때 계산)을 더하고 목록 '요약' 칸 앞에 '[이름]' 표시.
(b) 저장 · 목록은 그대로 — 상세에서만 종목 확인.

**Q2. 저장 안 한 기존 초안.** 설계는 '기존 초안 보호 방식'을 전제하지만 지금은 두 전달 경로 모두 확인 없이 덮어쓴다(작성 중 답변은 화면을 떠나면 원래 사라짐 · 남는 것은 초안).
(a) **권장** — 선택 근거 버튼에서만: 저장 안 한 초안이 있으면 버튼 아래 확인 줄 '저장하지 않은 AI 세션 초안이 있습니다(…에서 넘김 · 시각). 바꾸면 그 초안은 사라집니다. [바꾸고 이동] [취소]'. 기존 두 전달 경로는 그대로.
(b) 세 경로 모두 같은 확인을 넣는다(기존 경로 동작 변경).
(c) 확인 없이 덮어쓴다(지금 방식).

**Q3. 필터(필수 항목).** 저장 API 의 4필터는 필수다. 보유 미리보기는 목록 필터와 무관하다.
(a) **권장** — 두 종류 모두 「보유와 비교」 화면 목록 필터 그대로 저장(그 화면의 실제 조건 · API 변경 없음 · 상세에 그대로 보임).
(b) 선택 근거 모드에서 필터를 선택 항목으로 바꾼다(API 계약 변경).

## 5. 목업 (로컬 · 게시 안 함)

- 실제 폭 1440 · 1000px 전체 화면: ① 「보유와 비교」 미리보기 버튼 줄 [AI 세션에서 검토](+ Q2 확인 줄) ② 「AI 투자 세션」 새 기록 저장 — 선택 종목으로 채워진 화면 ③ 저장 뒤 기록 조회 — 목록(Q1) · 상세(넘겨받은 근거 원문). 보유(KODEX AI반도체TOP2플러스 395160 · 질문 그대로 저장) · 후보(SOL 반도체전공정 475300 · 질문 앞에 내 글을 더해 저장) 각 1. 권장안 (a) 기준.
- 사본 자료(시장 저장 최신일 2026-10-14) · 미리보기 글 = 사본 백엔드 실제 출력 · 작성 화면 답변 · 메모 · 판정과 기록 조회의 저장 기록 · '(예시 · 기존 기록)' 줄은 목업용 가짜 응답(사본 DB 에도 쓰지 않음) · 라이브 세션 기록 생성 없음.
- 목업에서 찾아 §2 에 더한 것 3: 작성 카드 설명의 출처 · 상세 선택 종목 표시(보유에 '1.') · 확인 줄 초안 시각(UTC).

## 6. 설계자 판정 반영 (2026-10-18 · 판정 원문 `docs/ai_design/POC5/POC5-24_SELECTED_EVIDENCE_AI_SESSION_LINK_PLAN_DECISION_2026-10-18.md`)

**기술 PLAN PASS · Q1 · Q2 · Q3 모두 (a) · 재제출 없음 · 백엔드 진행 · 화면은 보충 반영 목업 사용자 확인 뒤.**

| 판정 보충 | 반영 |
|---|---|
| Q1 — 선택 근거 모드이며 선택 종목 1건인 기록만 `target_label` · 일반 후보가 우연히 1건인 옛 기록은 아님 | 판정 = 화면 값 `holdings_compare_preview` · 후보 1건 · `selected_preview` 객체 셋 다(백엔드 `app/decision_selected_preview.py :: is_selected_preview_record` · 화면 `lib/aiSessionsDraft.ts :: isSelectedPreviewRecord` 같은 판정) · 목록은 읽을 때 계산 |
| Q2 — 새 버튼에서만 확인 줄 · [취소] = 기존 초안 · 현재 미리보기 보존 · [바꾸고 이동]에서만 교체 · 보호 범위 = sessionStorage 전달 초안 | 그대로 · 기존 두 전달 경로 · 메뉴 이탈 시 답변 소실은 손대지 않음 · 화면 문구에 답변 보호라고 쓰지 않음 |
| Q3 — 두 종류 모두 당시 화면 네 필터 저장 · 선택 근거 기록에서는 '당시 화면의 후보 목록 필터'로 표시 | 작성 화면 선택 종목 묶음 한 줄 · 상세 제목 '필터 조건' → '당시 화면의 후보 목록 필터'(선택 근거 기록만) · API 필수 그대로 |
| 가격 기준일 없음 — `asof` = 생성 시각의 KST 날짜('기록 기준일 — 미리보기 생성일 사용') · 가격 기준일 '미확인' · `target_as_of_date` 를 채우지 않음 | 초안 · 작성 화면 · 상세 그대로 · 백엔드 쓰기 검사가 `asof` = 가격 기준일(없으면 생성 시각 KST 날짜)를 확인 |
| 확인 줄 초안 시각 = Asia/Seoul 고정 · 해석 못 하면 원문 | `kstDateTimeLabel`(Intl · timeZone Asia/Seoul) · 미리보기 생성 시각 표시도 같은 함수 |
| 출처 설명 · '선택 종목' 명칭 · 보유 '1.' 제거 · 후보 순위 = 전달 당시 목록 순위 | 상세 '후보 · 당시 화면 목록 n위'(원문의 'n위'는 생성 시각 서버 목록 · 독립 검토 반영 · 결과서 §4 · §5) |
| 확인 중 종목 · 종류 · 목록 조건이 바뀌면 확인 줄 닫고 전달 취소 · 예전 원문을 새 종목 이름에 붙이지 않음 | 대상이 바뀌면 확인 줄 닫음(기존 미리보기 비우기와 같은 때) · [다시 생성]도 닫음 · 결과에 그 대상 표식(종류 · 종목 · 목록 조건)을 붙여 지금 대상과 같을 때만 버튼 · 초안 생성 |

**백엔드 구현(판정 §3 '진행 가능')**
- `app/decision_selected_preview.py`(신규) — 화면 값 · 판정 · 대상 표시 · KST 날짜 · 쓰기 검사. 쓰기 검사(저장소 `insert_record` 한 곳 · 위반 = 422 · 저장 0): `selected_preview` 는 선택 근거 화면 값에서만 · 그 화면 값이면 후보 1건 + `selected_preview` · 원문 · 생성 시각 필수 · 대상 종류 holding / candidate · `asof` 규칙 · 시장 문맥 · 구성종목 · 중복 · 단기 · 자료 품질 · ML 스냅샷 받지 않음(설계 §3 '다른 자료로 바꿔 넣지 않음'을 화면 · 저장 두 층에서).
- `app/api_decision_sessions.py` — `SelectedPreviewSnapshot`(POC5-23 `PreviewEvidenceAsOf` 재사용) · `DecisionCandidateSnapshot.selected_preview` · `DecisionSessionSummary.target_label`. `app/decision_evidence_store.py` — 쓰기 검사 호출 · 목록 `target_label`. 새 표 · 열 · 마이그레이션 0.
- 시험 `tests/test_poc5_24_selected_preview_session.py`(임시 DB · 실제 API 저장 → 목록 · 상세 왕복 · 원문 글자 그대로 · 질문 편집 뒤 원문 보존 · 가격 날짜 미확인 · KST 날짜 · 일반 1건 기록 · 옛 기록 · 위반 11종 422 · 저장소 직접 호출 위반 4종 · 기존 전체 후보 전달) · 화면 시험 `frontend/app/components/SelectedPreviewAISession.test.tsx` · 변이 백엔드 18/18 · 화면 26/26(결과서 §8).
- 기존 시험 정정 1건: `tests/test_decision_sessions_api.py :: test_decision_db_is_separate_from_market_db` 가 저장소 모듈을 다시 읽어(reload) 그 뒤 시험의 저장 검증 422 가 500 이 되는 오염 → 다시 읽지 않고 `init_db` 기본 인자로 같은 확인(시험 뜻 유지).
