# POC5-24 개발 결과서 — SELECTED_EVIDENCE_AI_SESSION_LINK (선택 근거의 AI 투자세션 연결)

작성 2026-10-18 · 작성자: 개발자(VSCode Claude) · 수신: 검증자(Codex) · 설계자

```text
STATUS        = IMPLEMENTED_VERIFIED_CLOSED — 구현 완료(2026-10-18) → 독립 검토 1회(P1 · P2 0 · P3 6 · 모두 반영 §4) → 사용자 실화면 확인(2026-10-19 '모두 확인했습니다. 이상없습니다.') → 검증자 r1 VERIFIED(2026-10-19 · §10) → 설계자 RESULT PASS(2026-10-19 · §11) → 종료(2026-10-19 · 커밋 · push = 이 종료 커밋)
STEP_ID       = POC5-24 선택 근거의 AI 투자세션 연결
DESIGN        = docs/ai_design/POC5/POC5-24_SELECTED_EVIDENCE_AI_SESSION_LINK_DESIGN_V1.md
PLAN          = docs/ai_plan/POC5/POC5-24_SELECTED_EVIDENCE_AI_SESSION_LINK_PLAN_V1.md(§6 판정 반영)
DECISION      = docs/ai_design/POC5/POC5-24_SELECTED_EVIDENCE_AI_SESSION_LINK_PLAN_DECISION_2026-10-18.md(기술 PLAN PASS · Q1 · Q2 · Q3 모두 (a) · 보충 §2)
USER_MOCKUP   = 첫 목업 2026-10-18 → 판정 보충 반영 수정 목업 확인 2026-10-18 '좋습니다.'(로컬 · 게시 안 함)
BASE_COMMIT   = 089310e3 (POC5-23 종료)
SCOPE         = 「보유와 비교」 미리보기 버튼 줄 [AI 세션에서 검토] → 기존 「AI 투자 세션」 새 기록 저장 탭 → 기존 저장 · 기록 조회
                새 메뉴 · 표 · DB 열 · 마이그레이션 · API 경로 · 외부 호출 · 계산 · 자동 저장 · 의존성 · LLM · OCI · PUSH 변경 0
CHECKS        = §8
```

## 0. 요약

- **지금까지**: 「보유와 비교」 판단 근거 미리보기는 [복사]만 있었다. AI 세션 초안(브라우저 sessionStorage 한 칸)을 만드는 곳은 「요즘 잘 오르는 ETF」 [AI Sessions로 넘기기](후보 전체)와 「ETF 구성종목」 둘뿐이고 둘 다 기존 초안을 확인 없이 덮어쓴다. 저장 때 초안에 ML 근거가 없으면 최신 ML 기준선 보고서(선택 종목과 무관)를 자동으로 넣는다. 기록 목록에는 제목 칸이 없다.
- **이제(설계 §2 · §3 · 판정 §1 · §2)**:
  - 미리보기가 정상 생성되고 **지금 대상의 결과일 때만** 버튼 줄 [다시 생성] [복사] 옆에 중간 버튼 **[AI 세션에서 검토]**. 누르면 지금 보이는 응답 그대로 초안을 만들고(재생성 · 재계산 · 재조회 0) 「AI 투자 세션」으로 이동한다. 이동만으로 저장하지 않는다.
  - 초안 = `source_screen` `holdings_compare_preview` · 질문 = 미리보기 원문 그대로 · `candidate_snapshot` 1건(`rank` = 보유 null · 후보는 전달 당시 화면 목록 순위) + 선택 필드 `selected_preview`(`target_kind` · `generated_at` · `evidence_as_of` 날짜 3 · `preview_text`) · `asof` = 가격 기준일(없으면 `generated_at` 의 KST 날짜 · `target_as_of_date` 는 비운 그대로) · `filters` = 「보유와 비교」 화면 목록 필터 · 다른 스냅샷 null.
  - 저장하지 않은 기존 초안이 있으면 버튼 아래 확인 줄 '저장하지 않은 AI 세션 초안이 있습니다(출처 · KST 시각). 바꾸면 그 초안은 사라집니다. [바꾸고 이동] [취소]'. [취소] = 기존 초안 · 지금 미리보기 그대로. 종목 · 종류 · 목록 조건이 바뀌거나 [다시 생성]을 누르면 확인 줄이 닫히고 전달은 취소된다(생성 중에는 [AI 세션에서 검토]가 숨고 · 새 결과가 와도 · 실패해도 닫힌 그대로). 기존 두 전달 경로는 그대로(판정 Q2 (a)).
  - 작성 화면(선택 근거 모드만): 기준일 · 필터 · 후보 요약 자리에 선택 종목 묶음(대상 · 보유/후보 · 화면 목록 순위 · 미리보기 생성 · 가격 기준일(없으면 '미확인') · KODEX200 · VIX · 가격 기준일이 없으면 '기록 기준일 … — 미리보기 생성일 사용' · '당시 화면의 후보 목록 필터 …') · 카드 설명 출처 · 질문 라벨. ML 근거 자동 보충은 하지 않는다(조회 호출 0). 답변 · 메모 · 판정 · [기록 저장] · 저장 조건(답변 1개 이상)은 그대로.
  - 저장(기존 `POST /decision/sessions` · 새 표 · 열 0): `selected_preview` 는 `candidate_snapshot_json` 안(POC5-22 `same_period_kodex200` 와 같은 방식). 저장소 쓰기 검사(`app/decision_selected_preview.py :: selected_preview_error` · 위반 422 · 저장 0) — `selected_preview` 는 그 화면 값에서만 · 그 화면 값이면 후보 1건 + `selected_preview` · 원문 · 생성 시각 필수 · 대상 종류 holding / candidate · `asof` 규칙 · 시장 문맥 · 구성종목 · 중복 · 단기 · 자료 품질 · ML 스냅샷 받지 않음.
  - 기록 조회: 목록 요약 앞 `[이름(티커)]`(선택 근거 기록만 · 응답 선택 필드 `target_label` · 읽을 때 계산). 상세 '기록 기준일'(가격 기준일 없으면 '— 미리보기 생성일 사용 · 가격 기준일 미확인') · '당시 화면의 후보 목록 필터' · '선택 종목 (저장 시점)'(보유 '1.' 없음 · 후보 '당시 화면 목록 n위') · '넘겨받은 판단 근거 (원문)'(질문을 고쳐 저장했으면 원문을 따로 · 같으면 '아래 AI 질문과 같은 글'로 두 번 안 보임).
  - 선택 근거 모드 판정 = 화면 값 · 후보 1건 · `selected_preview` 객체 셋 다(백엔드 `is_selected_preview_record` · 화면 `isSelectedPreviewRecord` 같은 판정). 일반 후보가 우연히 1건인 옛 기록 · 화면 값만 같은 기록은 선택 근거 모드가 아니다.

## 1. 처리한 요구사항

| 요구 | 상태 | 근거 |
|---|---|---|
| 설계 §2-1 · 2 — 같은 버튼 줄 [AI 세션에서 검토] → 기존 작성 화면 · 선택 종목 · 근거 · 질문 미리 채움 | DONE | `DecisionDraftPreviewCard.tsx :: buildSelectedPreviewDraft` · `goReview` · `AISessionsCreateTab.tsx :: SelectedTarget` |
| 설계 §2-3 · 4 — 외부 AI 호출 0 · 기존 저장 · 목록 · 상세 · 새 필수 항목 0 | DONE | 저장 조건 그대로 · 실제 API 왕복 시험 |
| 설계 §2 — 정상 생성일 때만 · 조건 변경으로 비워지면 새로 생성 뒤 · 기존 초안 조용히 덮지 않음 | DONE | 버튼 조건 · 확인 줄 · 시험 |
| 설계 §3 — 그 시점 응답 값 전달 · 재생성 · 재계산 0 · 원문을 질문에 · 새 표 · 열 · 파일 저장소 0 | DONE | 버튼 클릭 때 fetch 0(시험) · JSON 안 선택 필드 |
| 설계 §3 — 제목으로 종목 알아보기 · 종목별 새 이력 0 | DONE | 목록 `target_label`(판정 Q1 (a)) |
| 설계 §3 — 최신 시세로 자동 교체 0 · 처음 원문과 편집 질문 구분 | DONE | 상세 원문 묶음 |
| 설계 §3 — ML 자동 보충은 이 모드에서만 생략 · 한 종목을 상위 후보 전체 근거로 저장 0 · 기존 전체 후보 전달 보존 | DONE | 화면 생략 + 저장 검사(다른 스냅샷 거절) · 기존 경로 시험 |
| 설계 §3 — 이동만으로 저장 0 · 감사 로그 · 해시 · 원장 0 · 보유 정책 · PC 저장 정책 유지 | DONE | 이동 = 초안만 |
| 판정 Q1 (a) — `target_label` 선택 근거 모드 · 1건만 · 옛 1건 기록 제외 | DONE | `selected_target_label` · 시험(일반 1건 · 화면 값만 같은 옛 기록) |
| 판정 Q2 (a) — 새 버튼만 확인 줄 · [취소] 보존 · [바꾸고 이동]만 교체 · 보호 범위 = sessionStorage 초안 | DONE | 확인 줄 문구에 답변 보호 표현 없음 |
| 판정 Q3 (a) — 두 종류 화면 네 필터 · '당시 화면의 후보 목록 필터' · API 필수 유지 | DONE | 작성 화면 한 줄 · 상세 제목 |
| 판정 §2 — 가격 기준일 없으면 기록 기준일 = 생성 시각 KST 날짜 · '미확인' · 날짜 칸 채우지 않음 | DONE | 초안 · 저장 검사 · 작성 · 상세 표시 |
| 판정 §2 — 초안 시각 Asia/Seoul 고정 · 해석 못 하면 원문 | DONE | `kstDateTimeLabel` · 시험(브라우저 시간대 3종) |
| 판정 §2 — 출처 설명 · '선택 종목' · 보유 '1.' 제거 · 후보 = 전달 당시 순위 | DONE | 작성 카드 설명 · 상세 |
| 판정 §2 — 확인 중 대상 변경 → 닫고 취소 · 예전 원문을 새 종목에 붙이지 않음 | DONE | 결과 대상 표식 · 비우기 효과 · 시험(같은 그림 확인 포함) |
| 판정 §3 — 연결 시험(왕복 · 편집 뒤 원문 · 일반 1건 구분 · 가격 날짜 미확인 · KST · 교체 확인 중 선택 변경) | DONE | §8 |
| 실화면 · 검증자 · RESULT 판정 | DONE | 사용자 실화면 확인(§7) · 검증자 r1 VERIFIED(§10) · 설계자 RESULT PASS · IMPLEMENTED_VERIFIED_CLOSED(§11) |

## 2. 변경된 파일 목록

신규 7 · 수정 13 · 합 20(실측 §9).

- 백엔드: `app/decision_selected_preview.py`(신규) · `app/decision_evidence_store.py`(쓰기 검사 호출 · 목록 `target_label`) · `app/api_decision_sessions.py`(`SelectedPreviewSnapshot` · 선택 필드 2).
- 화면: `frontend/app/components/holdings_compare/DecisionDraftPreviewCard.tsx`(버튼 · 초안 · 확인 줄 · 결과 대상 표식) · `HoldingsCompareView.tsx`(화면 필터 · 순위 · 이동 함수 전달) · `MarketDiscoveryView.tsx`(이동 함수 전달 1줄) · `AISessionsCreateTab.tsx`(선택 근거 모드 · ML 보충 생략 · `source_screen`) · `AISessionsListTab.tsx`(목록 대상 · 상세) · `frontend/lib/aiSessionsDraft.ts`(선택 필드 · 판정 · 출처 · KST) · `frontend/lib/api/decisionSessions.ts`(타입) · `frontend/app/globals.css`(확인 줄 · 선택 종목 묶음).
- 시험: `tests/test_poc5_24_selected_preview_session.py`(신규) · `frontend/app/components/SelectedPreviewAISession.test.tsx`(신규) · `tests/test_decision_sessions_api.py`(오염 정정 · §4).
- 문서: 설계 V1 · PLAN 판정 · PLAN V1 · 이 결과서(신규) · `docs/PROGRAM_TRUTH.md` · `docs/STATE_LATEST.md`.

## 3. 신규 추가된 의존성

없음.

## 4. 지시문 외 변경 · 구현 판단

- **기존 시험 정정(지시문 외)**: `tests/test_decision_sessions_api.py :: test_decision_db_is_separate_from_market_db` 가 `importlib.reload(app.decision_evidence_store)` 로 모듈을 다시 읽었다. 그 뒤에는 API 모듈이 가진 예외 클래스와 저장소가 던지는 예외 클래스가 달라져, 같은 실행의 뒤 시험에서 저장 검증 422 가 500 으로 바뀐다(이번 새 시험을 그 파일 뒤에 돌리면 11건 실패로 확인 · 기존 '답변 0개' 규칙도 같은 증상). 다시 읽지 않고 `init_db` 기본 인자(정의 때 고정된 기본 경로)로 같은 확인(결정 DB 경로 · 시장 DB 와 다름)을 하도록 바꿨다. 시험의 뜻은 유지.
- **저장소 쓰기 검사(구현 판단 · PLAN §6 기록)**: 판정 §2 의 선택 근거 모드 계약(화면 값 · 후보 1건 · `asof` 규칙 · 관련 없는 스냅샷 null)을 화면만이 아니라 저장소 한 곳에서도 검사한다. 선택 근거와 무관한 기록은 그대로 통과(기존 전체 후보 전달 · ETF 구성종목 전달 시험 통과).
- **결과 대상 표식(구현 판단)**: 미리보기 결과에 그 요청 때의 대상(종류 · 종목 · 목록 조건)을 붙여, 지금 대상과 같을 때만 상자 · [복사] · [AI 세션에서 검토]를 보인다. 대상이 바뀐 직후 비우기 효과가 돌기 전 한 번의 그림에서도 예전 원문 버튼이 없도록(판정 §2 '예전 종목 원문을 새 종목 이름에 붙이지 않는다').
- **미리보기 생성 시각 표시**: 작성 화면 · 상세의 미리보기 생성 시각도 확인 줄과 같은 KST 함수로 보인다. 미리보기 카드 자체의 날짜 줄(POC5-23)은 바꾸지 않았다(서버 값이 이미 +09:00).
- **독립 검토 1회 반영(2026-10-18 · P1 · P2 0건 · P3 6건 · 모두 고침)**:
  1. 시간대 없는 생성 시각 — 브라우저는 그 기기 시간 · 백엔드는 KST 로 읽어 날짜가 갈릴 수 있었다(지금 응답은 늘 +09:00 이라 실제로는 안 생김) → 화면 `kstParts` 도 시간대 없는 값 · 날짜만 · 'YYYY-MM-DD HH:MM' 공백 형식을 KST 로 읽고 앞뒤 공백을 무시(백엔드 `kst_date_of` 와 같은 규칙 · 양쪽 같은 사례 시험).
  2. [다시 생성] 중에도 [AI 세션에서 검토]가 보여 확인 줄이 생성 뒤까지 남을 수 있었다 → 생성 중에는 버튼을 숨기고 누름도 무시 · 새 결과가 오면 확인 줄 닫음.
  3. 저장 순위는 화면 목록 순위 · 원문 'n위'는 생성 시각 서버 목록이라 그 사이 시장 자료가 바뀌면 다를 수 있다 → 표시를 '화면 목록 n위'(작성) · '당시 화면 목록 n위'(상세)로 바로잡고 §5 에 적음(목업 문구 '목록 9위' · '당시 목록 9위'에서 '화면'만 더함).
  4. 가격 기준일이 빈 글자면 '미확인' 대신 공백 → 빈 글자도 없음으로(`|| null` · 기록 기준일 규칙과 같음).
  5. 확인 줄의 초안 출처 — 분석 전 「ETF 구성종목」 초안이 「요즘 잘 오르는 ETF」로 보일 수 있었다 → 구성종목 · 중복 칸 키가 있으면 「ETF 구성종목」(그 화면 초안만 그 칸을 늘 넣음) · 넘긴 시각이 없으면 시각 생략('undefined' 방지).
  6. 시험 — 대상 종류 · 원문 검사 422 가 API 모델 단계에서만 났다 → 저장소 `insert_record` 직접 호출 시험(정상 저장 대조 + 위반 4종) 추가.
- 저장 JSON: 기존 경로의 후보 항목에도 `"selected_preview": null` 키가 들어간다(POC5-22 `same_period_kodex200: null` 과 같은 pydantic 직렬화 · 읽기 · 표시 영향 없음).

## 5. 알려진 한계 / 미완성

- 확인 줄이 보호하는 것은 sessionStorage 에 남은 전달 초안뿐이다. 작성 화면에서 입력 중이던 답변은 메뉴를 떠나면 지금처럼 사라진다(판정 Q2 · 범위 밖).
- 기존 두 전달 경로(「요즘 잘 오르는 ETF」 · 「ETF 구성종목」)는 여전히 확인 없이 덮어쓴다(판정 Q2 (a) · 이번 범위 밖).
- 상세 '화면:' 줄은 저장 값(`holdings_compare_preview`)을 그대로 보인다(기존 `market_discovery` 표시와 같은 방식).
- 후보 순위는 전달 당시 **화면 목록** 순위다. 미리보기 원문의 '현재 목록 n위'는 생성 시각에 서버가 다시 계산한 목록이라, 화면을 연 뒤 시장 자료가 갱신됐다면 둘이 다를 수 있다(POC5-23 '생성 시각에 다시 계산한 값' 안내와 같은 성격 · 새 조회로 맞추지 않음).
- 백엔드는 압축 ISO 형식(예: `20261018T224405+09:00`)도 읽지만 브라우저는 못 읽는다. 그 경우 화면은 버튼을 숨겨 넘기지 않는다(안전한 쪽 · 지금 응답 형식에서는 안 생김).
- `frontend/app/components/MarketDiscoveryView.tsx` 는 이번 전에도 864줄(KS-10 근접 · 850 이상)이었다. 이번 변경은 같은 줄 수(1줄 교체)로 새 책임 추가 없음.

## 6. 다음 검증자(Codex)에게 알릴 점

- 선택 근거 모드 판정이 백엔드(`app/decision_selected_preview.py :: is_selected_preview_record`)와 화면(`frontend/lib/aiSessionsDraft.ts :: isSelectedPreviewRecord`) 두 곳에 같은 규칙으로 있다.
- 저장 검사는 `insert_record` 안에서 기존 검사 뒤에 돈다. 일반 기록(화면 값 ≠ `holdings_compare_preview` · `selected_preview` 없음)은 `None` 을 돌려 그대로 통과한다.
- §4 의 기존 시험 정정은 다른 시험 파일에 영향을 주던 오염 제거다. 실행 순서를 바꿔 돌린 결과는 §8.

## 7. 사용자 확인이 필요한 항목

- 실화면 확인 완료(2026-10-19 · '모두 확인했습니다. 이상없습니다.') — 확인 순서: 「요즘 잘 오르는 ETF」 › 보유와 비교 › 보유 한 줄 › [판단 근거 미리보기 생성] › [AI 세션에서 검토] → 「AI 투자 세션」 새 기록 저장(선택 종목 묶음 · 원문 질문) → 저장하지 않고 후보 한 줄로 다시 [AI 세션에서 검토] → 확인 줄(출처 · KST 시각 · [취소] · [바꾸고 이동] · '화면 목록 n위') → (선택) 저장 뒤 기록 조회 목록 · 상세.

## 8. 검증 실측 (2026-10-18 · 독립 검토 반영 뒤)

| 검사 | 결과 |
|---|---|
| 백엔드 전체 `uv run pytest -q` | **3876 passed**(약 7분 · 라이브 쓰기 가드 그대로) |
| 새 백엔드 시험 `tests/test_poc5_24_selected_preview_session.py` | 33 passed(임시 DB · 실제 API 왕복 · 저장소 직접 호출) · 관련 3파일(+ `test_decision_sessions_api.py` · `test_decision_evidence_store.py`) 72 passed · 파일 순서를 바꿔도 통과 |
| 프론트 전체 `npx vitest run` | **65 files · 749 passed** |
| 새 화면 시험 `frontend/app/components/SelectedPreviewAISession.test.tsx` | 30 passed(진짜 request · 가짜 fetch · 브라우저 시간대 America/New_York · UTC · Asia/Seoul) |
| `npx tsc --noEmit` · `npx eslint`(변경 파일) | 0 · 0 |
| `black --check` · `flake8` · `py_compile`(백엔드 변경 5파일) | 통과 |
| 변이(사본 폴더만 · 복원 = 내용 쓰기 + 시각 되돌림 · 복원 뒤 저장소와 일치 확인) | 백엔드 **18/18** · 화면 **26/26** |
| 사용자 PC 서버(8000 · 3000) | 새 코드로 다시 읽힘(`/openapi.json` 에 `target_label` · `selected_preview` 확인 · DB 를 열지 않는 확인) |

변이 목록(요약): 백엔드 — 읽기 판정(화면 값 · 후보 수) · 다른 화면 값 허용 · 후보 2건 · 기록 기준일(언제나 생성일 · 검사 없음 · KST 아님 · 시간대 없는 값 UTC) · 다른 스냅샷 · 공백 원문 · 목록 대상 빠짐 · 저장 때 원문 버림 · 저장소 검사 무시 · 이름만 · 응답 모델 필드 빠짐 2 · 저장소 대상 종류 · 생성 시각 검사. 화면 — 원문 다듬기 · 기록 기준일 글자 자르기 · 가격 기준일 무시 · 확인 없이 덮음 · [취소]가 교체 · 대상 변경 · [다시 생성] 때 확인 줄 유지 · 결과 대상 표식 무시 · 브라우저 시간대 · 해석 못 한 시각 · ML 보충 · 화면 값 고정 · 판정 후보 수 · 상세 필터 제목 · 원문 두 번 · 목록 대상 · 가격 기준일 안내 · 기록 기준일 줄 · 보유 '1.' · 후보 순위 · 당시 필터 줄 · 생성 중 버튼 · 시간대 없는 값 · 빈 가격 기준일 · 초안 출처 · 시각 없음.

KS-10 줄 수(실측): `app/decision_selected_preview.py` 111 · `app/decision_evidence_store.py` 565 · `app/api_decision_sessions.py` 252 · `DecisionDraftPreviewCard.tsx` 294 · `AISessionsCreateTab.tsx` 412 · `AISessionsListTab.tsx` 371 · `HoldingsCompareView.tsx` 505 · `MarketDiscoveryView.tsx` 864(이전과 같음 · 근접 · §5) · 시험 파일 각각 1,450 미만.

## 9. git 상태 (개발자 실측 2026-10-18 · 검증자 재확인 2026-10-19)

`git status --short --untracked-files=all` — 20개 모두 stage(A 7 · M 13 · 오른쪽 칸 공백) · `??` 1건 = 사용자 소유 handoff 문서(넣지 않음):

```text
M  app/api_decision_sessions.py
M  app/decision_evidence_store.py
A  app/decision_selected_preview.py
M  docs/PROGRAM_TRUTH.md
M  docs/STATE_LATEST.md
A  docs/ai_design/POC5/POC5-24_SELECTED_EVIDENCE_AI_SESSION_LINK_DESIGN_V1.md
A  docs/ai_design/POC5/POC5-24_SELECTED_EVIDENCE_AI_SESSION_LINK_PLAN_DECISION_2026-10-18.md
A  docs/ai_plan/POC5/POC5-24_SELECTED_EVIDENCE_AI_SESSION_LINK_PLAN_V1.md
A  docs/ai_result/POC5/POC5-24_SELECTED_EVIDENCE_AI_SESSION_LINK_RESULT.md
M  frontend/app/components/AISessionsCreateTab.tsx
M  frontend/app/components/AISessionsListTab.tsx
M  frontend/app/components/HoldingsCompareView.tsx
M  frontend/app/components/MarketDiscoveryView.tsx
A  frontend/app/components/SelectedPreviewAISession.test.tsx
M  frontend/app/components/holdings_compare/DecisionDraftPreviewCard.tsx
M  frontend/app/globals.css
M  frontend/lib/aiSessionsDraft.ts
M  frontend/lib/api/decisionSessions.ts
M  tests/test_decision_sessions_api.py
A  tests/test_poc5_24_selected_preview_session.py
?? docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md
```


## 10. 검증자 r1 판정 (2026-10-19 · Codex)

```text
VERIFIER_DECISION = VERIFIED
OPEN_FINDINGS     = NONE
BASE_COMMIT       = 089310e332c3f24c8ccd77999ce76cfa91833a68
SCOPE             = staged 20개(A 7 · M 13) · unstaged 0
NEXT              = 설계자 RESULT 판정 → 사용자 커밋·push 별도 승인
COMMIT / PUSH     = 미수행
```

### 1) A. 기능/산출물 검증

- **A-1 지시 일치: 통과.** 정상 생성된 현재 대상의 미리보기만 전달하며, 원문·종목·종류·생성 시각·근거 날짜가 기존 초안에 들어간다. 전달 시 재조회·재계산·자동 DB 저장이 없다. 기존 초안 확인·취소·선택/조건 변경과 재생성 중 전달 취소가 동작한다. 선택 모드에서만 최신 ML 보충을 생략하고 기존 전체 후보 전달을 보존한다.
- **A-2 보고 정확성: 통과.** 실제 staged 20개(A 7 · M 13)·unstaged 0, 신규 모듈 추적 상태·변경 목록·주요 줄 수는 보고와 일치한다. 사용자 handoff 1개는 제외돼 있다. §9에는 이번 재확인 날짜만 추가했다. 개발자 전체 회귀/변이 근거와 검증자 직접 실행 수치는 아래에서 구분했다.
- **A-3 산출물 정합성: 통과.** 원문은 기존 `candidate_snapshot_json` 안에서 저장·재조회된다. 질문 편집 후에도 원문이 남고, 같으면 중복 표시하지 않는다. 일반 후보 1건/옛 기록과 선택 모드를 구분한다. 가격 기준일이 없으면 생성 시각 KST 날짜를 기록 기준일로 사용하고 실제 가격 날짜는 비워 둔다. 필터는 당시 화면 목록 조건으로 표시한다.
- **A-4 금지사항 위반: 없음.** 새 라이브러리·API 경로·DB 표/열·마이그레이션·외부 호출·LLM·운영 원장·OCI/PUSH 변경은 없다. 세션 저장은 기존 사용자의 명시적 저장 동작이다.

### 2) B. 구현 규칙/구조 품질 검증

- **B-1 암묵 fallback 위반: 없음.** 생성일을 쓰는 기록 기준일·KST 표시·해석 실패 시 원문 보존은 승인된 명시 규칙이다. 선택 모드 위반은 저장소에서 422로 거절한다.
- **B-2 단일 책임 위반: 없음.** 선택 근거 규칙·저장소·API·초안·작성/조회 화면의 경계가 유지된다.
- **B-3 파일 책임 과다: 없음.** 규칙 111줄·저장소 565줄·API 252줄·미리보기 카드 294줄·작성 412줄·조회 371줄·비교 화면 505줄이다. 시장 화면은 기존 864줄 그대로이며 기존 이동 함수 전달 1줄 교체라 새 대형 책임 추가가 아니다. 변경 시험은 Python 441/339줄·프론트 638줄로 기준 미만이다.
- **B-4 실험/운영 경계 위반: 없음.** 연구·학습·분석을 운영 경로에 넣지 않았다.
- **B-5 배포/실행 경로 문제: 없음.** 신규 모듈은 index에 등록돼 있고 import 경로가 일치한다. 추적 중인 Dockerfile은 없으며 배포/기동 스크립트·진입점 변경은 없다.
- **B-6 기술부채/구조적 퇴행: 없음.** 임시/stale 근거 재사용이나 새 저장 경로가 없고 필드가 API·저장·화면에 연결된다.

### 3) 기반 문서 준수

- 설계 V1·PLAN 판정·PLAN·결과서·실제 index diff를 대조했다. 사용자 목업/실화면 승인 기록이 있다. 신규 .md 4개는 승인된 설계·판정·PLAN·결과 기록이다. 신규 MongoDB·의존성/UI 프레임워크·KS-10 발동 변경은 없다.
- 기존 DB 분리 시험의 reload 제거는 예외 클래스가 분리되는 오염을 없애는 변경이며 경로/DB 분리 단언은 유지한다. 해당 API 시험 파일을 선택 근거 시험보다 먼저 실행한 관련 묶음도 통과했다.
- 원본 `.env`·state/logs/DB·znotes·사용자 handoff는 읽거나 수정하지 않았다. 실제 AI 답변·매매·라이브 시험 기록은 만들지 않았다.

### 4) 코드 안전성

- **위험 수준: NONE.** 추가 결함은 확인되지 않았다. 관련 없는 스냅샷과 불완전한 선택 근거는 쓰기 경계에서 거절하며 외부 발송·호출·비밀정보 하드코딩은 없다.

### 5) 범위 폭주

- **폭주 수준: NONE.** 저장소 검사·결과 대상 표식·KST·시험 오염 정정은 연결 계약과 직접 관련된다. 기존 두 전달 경로의 초안 보호와 메뉴 이탈 시 답변 소실 정책을 확대 수정하지 않았다.

### 6) 종합 판정 및 실행 근거

**VERIFIED — A/B 전체 통과, 추가 결함 없음.**

- 고정 staged 사본: `/private/tmp/poc524-verifier-sbdc_tvg/staged`. 시작 시 HEAD·index/작업 트리·사본 20개 파일의 SHA-256을 고정·대조했다.
- 백엔드 관련 시험 **72 passed**(선택 근거·기존 세션 API·저장소 3파일). 로그 `backend-related.log`.
- 프론트 관련 시험 **5 files · 43 passed**(선택 근거·기존 미리보기/연결·기존 전체 후보 전달). 4파일 41건과 기존 전달 1파일 2건의 합이다. 로그 `frontend-related.log`·`frontend-legacy-transfer.log`.
- 독립 실제 API 연결 **4 passed**. tmp 시장/보유 자료에서 POC5-23 미리보기를 생성하고, 보유/후보 각각 질문 그대로/질문 편집의 네 경우를 기존 세션 API로 저장→목록/상세 재조회했다. 원문·대상·생성 시각·근거 날짜·답변·판정·목록 대상이 보존되고 ML 스냅샷은 비어 있었다. 명시적 저장 전에는 세션 DB가 없었다. 로그 `roundtrip.log`, 사본에만 있는 `tests/_verifier_poc524_roundtrip.py`.
- `black --check`(5파일)·`flake8`·Python 문법 컴파일(5파일, pyc 생성 없음)·`tsc --noEmit --incremental false`·변경 TS/TSX eslint: 모두 exit 0.
- 개발자 전체 회귀 **3,876건**·전체 프론트 **749건**·변이 백엔드 **18/18**/화면 **26/26**은 §8의 개발자 실행 근거이며 이번에 반복하지 않았다.
- 실행 근거는 `/private/tmp/poc524-verifier-sbdc_tvg/`의 `checks.json` 및 로그에 있다. 검증자 운영 코드·시험 수정 0. 커밋·push·배포 없음.

### 7) 사용자에게 한마디

검증은 통과했다. 다음은 설계자 RESULT 판정이며, 실제 커밋·push는 기존 사용자 별도 승인 절차를 유지한다.

## 11. 설계자 RESULT 판정 · 종료 (2026-10-19)

- 판정: **PASS — 추가 코드 수정 없이 종료**(문서 기반 판정 · 설계자가 맥북 소스 · DB · 서버를 직접 실행한 확인 아님).
- 종료 상태: **IMPLEMENTED_VERIFIED_CLOSED(2026-10-19)**. RESULT · PLAN · STATE · PROGRAM_TRUTH 의 이번 관련 상태를 같게 맞췄다. 별도 인계 문서 없음.
- 해소로 기록하는 것: 「보유와 비교」 판단 근거 미리보기 → [AI 세션에서 검토] → 「AI 투자 세션」 작성 · 저장 · 기록 조회 연결(원문 · 대상 · 생성 시각 · 근거 날짜 그대로 · 저장하지 않은 전달 초안 확인 줄 · 선택 근거 모드 ML 자동 보충 생략 · 목록 대상 표시 · 편집 질문과 처음 원문 구분 · 가격 기준일 없을 때 기록 기준일 = 생성 시각 KST 날짜). POC5-23 ~ 24 의 선택 근거 생성 → AI 세션 전달 · 저장 · 재조회 연결은 여기서 마무리.
- 해소로 기록하지 않는 것(한계 · §5 · 판정 §2): 기존 두 전달 경로의 초안 덮어쓰기 · 메뉴 이탈 시 입력 중 답변 소실 · 생성 시점 서버 순위와 당시 화면 순위의 차이 · 압축 ISO 형식 전달 불가 · `MarketDiscoveryView.tsx` 크기 근접 · 종합 위험 분류 · 운영 ML · 전체 프로젝트 완료 · 미사용 POC5-16 파일 삭제 승인 아님.
- 재검증 · 재판정 · 추가 실화면 · OCI pull · PC 재기동 · 거래일 대기 없음. 커밋 · push 는 사용자 승인 뒤(사용자 소유 handoff 문서 제외).

### 설계자 RESULT 판정 원문 (`POC5-24_SELECTED_EVIDENCE_AI_SESSION_LINK_RESULT_DECISION_2026-10-19.md`)

# POC5-24 선택 근거의 AI 투자세션 연결 — RESULT 판정

작성일: 2026-10-19 · 작성자: 설계자 · 수신: 개발자 / 사용자

**판정: PASS. 추가 코드 수정 없이 종료 기록과 사용자 승인 후 커밋·push로 진행한다.**

제출 결과서를 설계 V1·PLAN 판정과 대조했다. 결과서 §7의 사용자 실화면 확인과 §10의 검증자 r1 VERIFIED를 수용한다. 설계자가 맥북 소스·DB·서버를 직접 실행한 검증은 아니다.

## 1. 구현·검증 수용

- 현재 선택의 미리보기 원문·대상·생성 시각·근거 날짜를 기존 세션 초안으로 전달하고, 재조회·재계산·자동 저장 없이 작성 화면으로 이동하는 구현을 수용한다.
- 기존 JSON 안의 `selected_preview`, 명시적 저장 후 목록·상세 재조회, 편집 질문과 처음 원문 구분, 선택 모드의 `target_label`과 ML 자동 보충 생략을 수용한다. 일반 한 종목 기록과 기존 전체 후보 전달도 보존된 것으로 확인됐다.
- 초안 교체 확인·취소, 대상/조건 변경 및 재생성 중 전달 취소, 가격 기준일 미확인 시 KST 생성일을 별도 기록 기준일로 표시하는 처리는 PLAN 판정과 일치한다.
- 결과서 §4의 저장소 검사·결과 대상 표식·KST 표시 보완·출처/순위 문구 정정·시험의 reload 오염 제거를 수용한다. 기존 경로 JSON의 선택 필드 null 추가도 호환 범위로 수용한다. 전역 초안 관리·새 저장 구조로 확대하지 않은 점을 확인한다.
- 검증자 직접 실행(백엔드 관련 72건·프런트 관련 43건·임시 자료의 실제 API 왕복 4건)과 개발자 보고(전체 회귀 3,876건·프런트 749건·변이 18/18 및 26/26)를 구분해 근거로 삼는다. 실제 라이브 시험 기록을 추가로 만들 필요는 없다.

## 2. 알려진 한계 수용

결과서 §5를 이번 범위의 한계로 수용한다. 기존 두 전달 경로의 초안 덮어쓰기와 메뉴 이탈 시 입력 중 답변 소실, 생성 시점 서버 순위와 당시 화면 순위의 차이, 현재 응답에 없는 압축 ISO 형식의 전달 불가, 기존 파일 크기 근접 상태는 이번 종료의 선행 보완이나 자동 후속 단계로 만들지 않는다. 수용을 해당 한계의 해소로 기록하지 않는다.

## 3. 종료 지시

1. 본 판정 원문을 기존 결과서 끝에 붙이고 RESULT·PLAN·STATE·PROGRAM_TRUTH의 이번 관련 상태를 정리한다. 별도 전수 문서 정리나 인계 문서는 요구하지 않는다.
2. 사용자 승인 범위에 따라 커밋·push한다. 동일 범위의 기존 승인이 있으면 재요청하지 않는다. 사용자 소유 handoff 문서는 포함하지 않는다.
3. 종료 기록과 커밋·push 완료 뒤 `IMPLEMENTED_VERIFIED_CLOSED`로 확정한다. POC5-23~24의 선택 근거 생성 → AI 세션 전달·저장·재조회 연결은 여기서 마무리한다. 이를 종합 위험 분류·운영 ML·전체 프로젝트 완료로 확대하지 않는다.

추가 실화면 확인·재검증·재판정·OCI pull·PC 재기동·거래일 대기는 종료 조건이 아니다. 실제 AI 답변·판단의 정답·실제 매매를 추가 완료 조건으로 요구하지 않는다.
