# POC5-25 개발 결과서 — STORED_PRICE_DRAWDOWN_EVIDENCE (현재 저장 종가의 고점 대비 근거 정정)

작성 2026-10-19 · 작성자: 개발자(VSCode Claude) · 수신: 검증자(Codex) · 설계자

```text
STATUS        = IMPLEMENTED_VERIFIED_CLOSED — 구현 완료(2026-10-19) → 독립 검토 1회(P1 0 · P2 3 · P3 5 · 모두 반영 §4 · §8) → 사용자 실화면 확인(2026-10-19 '확인했습니다.') → 검증자 r1 VERIFIED(2026-10-19 · §12) → 설계자 RESULT PASS(2026-10-19 · 추가 코드 수정 없음 · §13) → 종료(2026-10-19 · 구현 + 종료 기록 한 커밋 · 커밋 · push = 사용자 승인)
STEP_ID       = POC5-25 현재 저장 종가의 고점 대비 근거 정정
DESIGN        = docs/ai_design/POC5/POC5-25_STORED_PRICE_DRAWDOWN_EVIDENCE_DESIGN_V1.md
PLAN          = docs/ai_plan/POC5/POC5-25_STORED_PRICE_DRAWDOWN_EVIDENCE_PLAN_V1.md(§6 판정 반영)
DECISION      = docs/ai_design/POC5/POC5-25_STORED_PRICE_DRAWDOWN_EVIDENCE_PLAN_DECISION_2026-10-19.md(PASS · Q1 (a) · Q2 (a))
BACKLOG_DEC   = docs/ai_design/POC5/POC5_BACKLOG_DISPOSITION_DECISION_2026-10-19.md(문서 반영 지시 · 이번 문서 갱신에 함께 반영 · §10)
USER_MOCKUP   = 전체 화면 목업 확인 2026-10-19 '확인함 · 그대로 진행'(로컬 · 게시 안 함)
BASE_COMMIT   = 9df40437 (POC5-16 미사용 파일 삭제)
SCOPE         = 「요즘 잘 오르는 ETF」 카드 펼침 · 표 · 기간 상자 · 「ETF 비교하기」 정렬 · 카드 줄 · 상세의 고점 대비
                새 수집 · 외부 조회 · 모델 실행 · feature 적재 · DB 표 · 의존성 · OCI · PUSH · cron · PARAM · ML · 위험 분류 변경 0
CHECKS        = §8
```

## 0. 요약

- **지금까지**: 두 화면의 '고점 대비'는 폐기된 참고점수 스냅샷(`state/ml/relative_upside_score_latest.json` · 2026-08-27 · 종목별 날짜 없음)의 `drawdown_20d`(비율)를 PC 시장 목록 응답에 붙인 값이었다. 「ETF 비교하기」 고점 정렬은 값 없는 후보를 오름차순에서 맨 앞에 두었다.
- **이제(설계 §2 · §3 · 판정 §2 · §3)**: PC 시장 목록 API(`GET /market/topn/latest`)만 후보 선택 객체 `stored_drawdown_20` 을 붙인다(`app/pc_stored_drawdown.py`).
  - 기준일 D = 후보의 POC5-21 실제 끝 행 날짜(`price_end_date` = 마지막 유효 종가 행 · 시장 최신일 · 스냅샷 날짜 아님).
  - 창 = D 를 포함한 D 이하 원본 저장 행 20개(종목별 `LIMIT 20` · `mode=ro` 연결 하나 · 거르지 않음).
  - 판정: D 없음 · 창 마지막 행 ≠ D `end_date_unknown` · 20행 미만 `insufficient_history` · 창 안 비정상 종가 · 허용 밖 출처 `invalid_price`(PLAN §2 · POC5-06 `BAD_CLOSE` · `SOURCE_NOT_ALLOWED` 와 같은 묶음) · POC5-06 연결 판정(`pc_price_volatility._link_unconfirmed`) 확인 불가 `basis_unconfirmed` · 비정상 행을 빼고 더 오래된 행으로 채우지 않는다(DB 읽기도 거르지 않음).
  - 값 = (D 종가 ÷ 20개 최고 종가 − 1) × 100 · % · 소수 4자리 · 고점일 = 최고 종가의 가장 늦은 날짜 · 고점과 같으면 0.
  - 옛 `drawdown_20d` 필드 · 머지 · 연구 정의는 그대로(화면 · 정렬은 쓰지 않음 · 새 객체가 없으면 옛 값으로 대체하지 않음).
- **화면(사용자 확인 목업 그대로 · 공통 helper `frontend/lib/storedDrawdown.ts`)**:
  - 「요즘 잘 오르는 ETF」 목록 위 기간 상자 셋째 줄 '20저장일 종가 고점 대비' — 공통 기간 '… 저장 종가 20개 · 표시 후보 n개 모두 같음' · 다르면 '종목별 기간 다름 · 끝일 … · 기간은 값 아래'(다수 날짜를 기준으로 삼지 않음 · POC5-21 규칙) · 값 없음 수 · ?(뜻 · 예 · 값 없음 사유 · MDD · 손익률 · 위험 등급과 구분 · 옛 스냅샷 값과 다름).
  - 카드 펼침 · 표 칸 이름 '20저장일 종가 고점 대비' · 값 아래 고점 날짜(공통과 다른 기간이면 그 기간도) · 값 없으면 사유 · 0% 중립 색.
  - 「ETF 비교하기」 정렬 버튼 · 카드 줄 · 상세 칸 같은 이름 · 정렬 = 같은 버튼 · 첫 클릭 오름(값 작은 순 = 고점에서 많이 내려온 순) · **값 없음은 방향과 무관하게 맨 뒤** · 동률 기존 순서 · 상세 '값 (기간 · 고점 날짜 종가)'.
- **복사문 · AI 전달**: 고점 대비를 싣는 곳이 없어 변경 0(판정 §3).
- **실제 대조(사본 · 시장 저장 최신일 2026-10-14)**: SOL 반도체전공정 옛 0.00% → 새 −13.84%(2026-09-11 ~ 2026-10-14 · 고점 10-06 28,550) · 「ETF 비교하기」 후보 30개 중 계산 29 · 저장 종가 20개 미만 1.

## 1. 처리한 요구사항

| 요구 | 상태 | 근거 |
|---|---|---|
| 설계 §2 — 기준일 D · D 포함 20행 · 최고 종가 · % 값 · 계산 불가 사유 · 대체 금지 · 가장 늦은 고점일 | DONE | `compute_stored_drawdown` · 시험 §8 |
| 설계 §2 — 기존 연결 판정 재사용 · MDD 등과 구분 · 옛 `drawdown_20d` 와 섞지 않음 | DONE | `_link_unconfirmed` 재사용 · ? 문구 · 새 객체 하나 |
| 설계 §3 — PC 응답 조립 경로에서만 · 제한된 저장 창 읽기 · 새 수집 · DB 표 0 | DONE | `get_market_topn_latest` 한 곳 · `compute_topn` 무변경 |
| 설계 §3 — 두 화면 같은 객체 · helper · 실제 기간 · 스냅샷 대체 없음 | DONE | `lib/storedDrawdown.ts` |
| 설계 §3 — 칸 교체 · 이름 · 기준일 확인 · 새 카드 · 펼치기 버튼 없음 | DONE | 카드 · 표 · 비교하기 |
| 설계 §3 — 사용자 정렬 새 값 · 방향 뜻 보존 · 값 없음 맨 뒤 · 동률 기존 순서 · 기본 정렬 무변경 · 서버 정렬 경로 없음 | DONE | `drawdownMissingLast` · 시험 |
| 설계 §3 — 복사문 · AI 전달 소비처 같은 값(소비처 없음 확인) · 과거 기록 무변경 | DONE | PLAN §1 조사 |
| 판정 Q1 (a) — 종목 자신의 D · 다르면 '수익률 끝일' 안내 + 실제 기간 | DONE | D = `price_end_date` · 시험(하루 늦은 종목) |
| 판정 Q2 (a) — 기간 상자 셋째 줄 + ? · 공통 기간 한 번 · 비교하기 상세 칸 | DONE | `ReturnPeriodLine` · 상세 |
| 판정 §3 — 정렬 helper 분리 · 줄바꿈 CSS · 리팩터 · 새 숫자 체계 없음 | DONE | `workbench/helpers.ts` · `.cand-dcell .k` |
| 판정 §4 — 사용자 목업 확인 기록 · 계산 · 결측 · 정렬 · 기존 호출 보존 시험 | DONE | PLAN §6 · §8 |
| 백로그 처리 판정 §6 — BACKLOG · 통합지도 · STATE 문서 반영 · 다른 사실 알림 | DONE | §10 |
| RESULT 판정 §2 — 판정 원문 첨부 · RESULT · PLAN · STATE · PROGRAM_TRUTH 종료 상태 · 커밋 범위 일치 · 후속 설계서 미포함 | DONE | §13 |
| RESULT 판정 §3 · §4 — 백로그 최신 합계 · 개발 대상 3 · 사용자 보류 5 · 관찰 후보군 정의 정정 | DONE | §11 · §13 · BACKLOG 머리 |

## 2. 변경된 파일 목록

신규 10 · 수정 17 · 합 27(실측 §9).

- 백엔드: `app/pc_stored_drawdown.py`(신규) · `app/api_market_topn_models.py`(선택 필드) · `app/api_market_topn.py`(연결).
- 화면: `frontend/lib/storedDrawdown.ts`(신규) · `frontend/lib/api/market.ts`(타입) · `ReturnPeriodLine.tsx`(셋째 줄) · `CandidateCards.tsx` · `CandidateTable.tsx` · `JudgmentWorkbenchView.tsx` · `workbench/helpers.ts` · `globals.css`(2줄).
- 시험: `tests/test_poc5_25_stored_drawdown.py`(신규) · `frontend/lib/storedDrawdown.test.ts`(신규) · `frontend/app/components/StoredDrawdownTable.test.tsx`(신규) · `JudgmentWorkbenchView.test.tsx` · `CandidateCards.test.tsx` · `RejectedScoreCloseout.test.tsx`(새 이름 · 새 객체 계약) · `ReturnPeriodLine.test.tsx`(기간 상자 셋째 줄).
- 문서: 설계 V1 · PLAN 판정 · 백로그 처리 판정 · PLAN V1 · 이 결과서 · PROGRAM_TRUTH · STATE · BACKLOG · 통합지도 V2.

## 3. 신규 추가된 의존성

없음.

## 4. 지시문 외 변경 · 구현 판단

- **사유 이름**: PLAN 의 `no_price` 를 `end_date_unknown`('기준일 확인 불가')으로 고쳤다(D 를 정할 수 없다는 뜻이 정확). 창 마지막 행이 D 가 아닐 때도 같은 사유(독립 검토 P3 · 지금 자료에서는 늘 같음). 허용 밖 출처는 PLAN §2 그대로 `invalid_price` 다(처음 구현은 연결 사유로 묶었고 그 근거로 적은 'POC5-06 이 출처를 연결 사유로 다룬다'는 사실과 달랐다 — POC5-06 은 `SOURCE_NOT_ALLOWED` 를 `BAD_CLOSE` 와 같은 창 제외 사유로 둔다 · 독립 검토 지적으로 되돌림).
- **0% 표시**: 고점과 같은 0% 를 상승 색(빨강)이 아닌 중립 색으로 · 카드 · 「ETF 비교하기」의 기존 % 함수가 0 에 '+'를 붙여 '+0.00%' 가 되던 것을 `ddPct` 로 '0.00%'(표와 같게 · 정의상 양수가 없음 · 독립 검토 P3).
- **기존 시험 4개 계약 갱신**: '고점 대비' · '고점대비' 이름과 옛 `drawdown_20d` 정렬을 확인하던 시험(`JudgmentWorkbenchView` · `CandidateCards` · `RejectedScoreCloseout`)과 기간 상자를 두 줄로 확인하던 POC5-21 시험(`ReturnPeriodLine.test.tsx` · 판정 Q2 (a) 셋째 줄)을 새 계약으로 바꿨다. 옛 `drawdown_20d` 는 반대 순서 · 다른 값의 함정으로 남겨 새 객체만 읽는지 확인한다.
- **설명 문구 1건**: 새 모듈 docstring 에 `compute_topn(actual_price_dates=True)` 글자가 있어 POC5-21 의 '플래그 켜는 곳은 PC 화면 API 하나' 글자 검사에 걸렸다 → 설명 문구를 바꿨다(동작 무관).

## 5. 알려진 한계 / 미완성

- 후보가 n 개면 원본 창 읽기가 n 번(`LIMIT 20` · (ticker, date) 기본 키 · 화면 기본 10 · 「ETF 비교하기」 30 · API 최대 200). 같은 API 를 부르는 「오늘의 투자 점검」 · LEGACY Dashboard · POC5-23 미리보기 후보 조회도 이 읽기를 한다 — 미리보기 글은 이 객체를 읽지 않아 원문 무변경(POC5-23 시험 통과). 읽기 SQLite 오류는 다른 응답 보강과 같이 목록 응답 오류가 된다(별도 보호 없음).
- 창 밖 → 창 첫 행 연결은 보지 않는다(POC5-16 창 규칙과 같음). 창 안 19개 연결만 검사.
- 옛 `drawdown_20d` 는 응답에 그대로 남는다(설계 §2 '과거 필드 의미 그대로'). 이 화면들은 쓰지 않는다.
- 다른 고점 지표(코스피 최근 1년 고점 대비 · OCI 보유 브리핑 `drawdown_20d_pct` · ML 실험 카드)는 다른 원천이며 이번에 바꾸지 않았다.
- `frontend/app/components/JudgmentWorkbenchView.tsx` 845 → 849줄(KS-10 근접 850 미만).

## 6. 다음 검증자(Codex)에게 알릴 점

- D 는 응답 후보의 `returns.*.price_end_date` 중 있는 첫 값이다(기간마다 같은 마지막 유효 종가 행). 목록에 오른 후보는 기준 기간 수익률이 있어 D 가 늘 있다 — `end_date_unknown` 은 방어 분기.
- 정렬 값 없음 처리는 `drawdownMissingLast` 가 먼저 결정하고, 둘 다 값이 있을 때만 기존 비교로 간다.

## 7. 사용자 확인이 필요한 항목

- 실화면 확인 완료(2026-10-19 · '확인했습니다.') — 확인 순서: 「요즘 잘 오르는 ETF」 카드 탭 기간 상자 셋째 줄 · ? → 카드 펼침 '20저장일 종가 고점 대비'(값 · 고점 날짜) → 표 탭 마지막 칸 → 「ETF 비교하기」 정렬 오름 · 내림(값 없음 맨 아래) → 후보 상세 칸(값 · 기간 · 고점 날짜 종가).

## 8. 검증 실측 (2026-10-19 · 독립 검토 반영 뒤)

| 검사 | 결과 |
|---|---|
| 백엔드 전체 `uv run pytest -q` | **3903 passed**(약 7분 · 독립 검토 반영 뒤 · 라이브 쓰기 가드 그대로) |
| 새 백엔드 시험 `tests/test_poc5_25_stored_drawdown.py` | 27 passed(순수 계산 · 임시 DB 실제 `GET /market/topn/latest` · DB 읽기 대체 금지 · 조립 경로 한정 · 라이브 DB · 라이브 점수 스냅샷 미사용) · POC5-21 시험과 함께 50 passed |
| 프론트 전체 `npx vitest run` | **66 files · 762 passed** |
| 새 · 고친 화면 시험 | `lib/storedDrawdown.test.ts` · `StoredDrawdownTable.test.tsx` · `JudgmentWorkbenchView.test.tsx`(정렬 값 없음 맨 뒤 · 상세) · `CandidateCards` · `RejectedScoreCloseout` · `ReturnPeriodLine` |
| `npx tsc --noEmit` · `npx eslint`(변경 파일) | 0 · 0 |
| `black --check` · `flake8` · `py_compile`(백엔드 변경 4파일) | 통과 |
| 라이브 자료 재확인(2026-10-19 16:38 · 사용자 [최신 시장 데이터 갱신] 16:03 뒤 · 라이브 DB 를 `mode=ro` 백업으로 복사해 계산) | 시장 저장 최신일 2026-10-19(마감 뒤 수집) · 「요즘 잘 오르는 ETF」 후보 10 · 「ETF 비교하기」 30 모두 `ok` · 기간 2026-09-16 ~ 2026-10-19 모두 같음 · 다시 받은 10-14 종가(95,015 → 94,805)와 10-15 change 가 맞아 연결 판정 통과 |
| 변이(사본 폴더만 · 복원 뒤 저장소와 일치 확인) | 백엔드 **15/15** · 화면 **17/17** |

변이 목록(요약): 백엔드 — 21행 창 · 비정상 행 빼고 채움 · 가장 이른 고점일 · 100배 없음 · 20행 미만 허용 · 연결 검사 빠짐 · 출처 검사 빠짐 · DB 읽기에서 비정상 행 거름(오래된 행으로 채움 · 독립 검토 P2-3 이 찾은 빈틈) · 창 끝 = D 확인 빠짐 · 출처를 연결 사유로 · D 이하 경계 빠짐 · API 연결 빠짐 · 비정상 종가 검사 빠짐 · 소수 2자리 · D 없음 처리. 화면 — 객체 없으면 옛 값 · 100배 · 다수 기간을 공통으로 · 값 아래 늘 기간 · 고점 날짜 빠짐 · 값 없음 맨 뒤 빠짐 · 비교하기 정렬 · 카드 · 상세 옛 값 · 표 옛 이름 · 기간 줄 값 · 0% 하락 색 · 사유 문구 · 상세 고점 종가 · 표 값 아래 표시 · ? 도움말 · 0 에 '+'.

**독립 검토 1회(2026-10-19 · P1 0 · P2 3 · P3 5) 반영**:
1. P2 — 검토 시점에 일부 파일이 stage 전이었다 → 보고 직전 전부 stage(§9).
2. P2 — 허용 밖 출처를 PLAN §2 와 달리 연결 사유로 묶었고 그 근거 설명이 사실과 달랐다 → `invalid_price` 로 되돌리고 시험 · PLAN · PROGRAM_TRUTH · 이 결과서 설명을 정정(§4).
3. P2 — DB 읽기 단계의 '오래된 행으로 채우지 않음' 시험이 없었다(읽기에 `close > 0` 조건을 더해도 시험 통과) → 임시 DB 에 기간 안 빈 종가 · 다른 출처 행 종목 2개를 넣어 실제 API 로 `invalid_price` · 20행 · 원래 시작일 확인 + 그 변이 추가.
4. P3 — 조립 경로 시험이 약했다 → app · scripts 에서 `build_stored_drawdown(` 을 부르는 곳이 이 API 하나뿐인지 확인으로 교체. P3 — 0 이 '+0.00%' → `ddPct`. P3 — 창 끝 ≠ D 확인 추가. P3 — 같은 API 를 쓰는 다른 화면 · 미리보기의 추가 읽기 · 오류 동작은 §5 한계로 기록. P3 — 기간이 다를 때 값마다 기간을 보이는 것은 Q2 (a) · POC5-21 규칙 해석으로 유지.

## 9. git 상태 (보고 직전 실측 · 2026-10-19)

`git status --short --untracked-files=all` — 27개 모두 stage(A 10 · M 17 · 오른쪽 칸 공백) · `??` 1건 = 사용자 소유 handoff 문서(넣지 않음):

```text
M  app/api_market_topn.py
M  app/api_market_topn_models.py
A  app/pc_stored_drawdown.py
M  docs/PROGRAM_TRUTH.md
M  docs/STATE_LATEST.md
M  docs/ai_design/POC3/POC3-00_PC_JUDGMENT_UI_INTEGRATED_IMPLEMENTATION_MAP_V2.md
A  docs/ai_design/POC5/POC5-25_STORED_PRICE_DRAWDOWN_EVIDENCE_DESIGN_V1.md
A  docs/ai_design/POC5/POC5-25_STORED_PRICE_DRAWDOWN_EVIDENCE_PLAN_DECISION_2026-10-19.md
A  docs/ai_design/POC5/POC5_BACKLOG_DISPOSITION_DECISION_2026-10-19.md
A  docs/ai_plan/POC5/POC5-25_STORED_PRICE_DRAWDOWN_EVIDENCE_PLAN_V1.md
A  docs/ai_result/POC5/POC5-25_STORED_PRICE_DRAWDOWN_EVIDENCE_RESULT.md
M  docs/backlog/BACKLOG.md
M  frontend/app/components/CandidateCards.test.tsx
M  frontend/app/components/CandidateCards.tsx
M  frontend/app/components/CandidateTable.tsx
M  frontend/app/components/JudgmentWorkbenchView.test.tsx
M  frontend/app/components/JudgmentWorkbenchView.tsx
M  frontend/app/components/RejectedScoreCloseout.test.tsx
M  frontend/app/components/ReturnPeriodLine.test.tsx
M  frontend/app/components/ReturnPeriodLine.tsx
A  frontend/app/components/StoredDrawdownTable.test.tsx
M  frontend/app/components/workbench/helpers.ts
M  frontend/app/globals.css
M  frontend/lib/api/market.ts
A  frontend/lib/storedDrawdown.test.ts
A  frontend/lib/storedDrawdown.ts
A  tests/test_poc5_25_stored_drawdown.py
?? docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md
```

## 10. 백로그 처리 판정 반영 (2026-10-19 · 문서만 · 기능 구현 없음)

- `docs/backlog/BACKLOG.md` 머리 '현재 처리 요약' — 처리 판정 당시 합계(완료 4 · 대체 · 병합 종료 5 · ML 설계 통합 4 · 조건부 47 · 사용자 보류 2 = 62 · 지금은 '이력' 표 · 최신 합계는 §13) · 처리별 표(완료 · 대체 종료는 '활성 할 일 아님'으로 분리) · 판정 §5 잔여 표 · P-12 / P-13. 본문 62개 `- **항목**` 줄 끝에 '[처리 2026-10-19: … · 현재 처리 요약 #n]'(원문 · B-ID · 섹션 보존 · 등록 수 62 그대로).
- 통합지도 V2 §6 머리 · 후속 개발 16행 끝 '현재 처리' 메모 · P-19 행에 POC5-23 ~ 24 완료 연결(원래 판정 · 합계 보존).
- STATE 맨 위 줄에 25 진행 · 남은 큰 방향(ML 목표 · 기준선 · 시간 분리 · 자료 성숙 · 검증 · 중단 기준 설계).
- **판정 자료와 다른 사실 1건(판정 §6-4 에 따라 알림)**: 판정 §5 'POC5-16 미사용 파일 삭제 — 사용자 승인 대기로 유지'는 2026-10-19 사용자 승인으로 이미 삭제됐다(커밋 `9df40437` · `PriceVolatilityBlock.tsx` · 시험 · `.pvb*` CSS). BACKLOG 잔여 표에 '삭제 완료'로 적었다.
- **사용자 결정 기록(2026-10-19 · 문서만)**: 조건부 중 '사용자 요청이 재개 조건'인 18건을 사용자가 검토 — 19 · 48 · 50 개발 대상(RESULT 판정 §3 확정 · 순서 19 → 50 → 48) · 33 · 20 보류 · 12건 지금 불편 없음 · 59 보류(ML 설계에서 후보 선별과 함께 결정). BACKLOG 머리 '사용자 결정' 표 · 해당 항목 줄 표시 · 설계자 전달용 요약 §11. 기능 구현 없음.
- PROGRAM_TRUTH 는 POC5-25 기능 변경 반영만 했다(백로그 판정으로 모순되는 현재 상태 문구는 찾지 못함 · 전수 재감사 안 함).

## 11. 설계자에게 함께 전달 — 백로그 사용자 결정과 대화 요약 (2026-10-19 · 사용자 요청)

POC5-25 RESULT 판정 때 함께 봐 주시도록 사용자가 요청한 내용입니다(코드 변경 없음 · BACKLOG 머리 '사용자 결정'과 같은 내용).

**1. 백로그 사용자 결정** — 설계자 백로그 처리 판정의 조건부 47건 중 '사용자 요청이 재개 조건'인 18건을 사용자가 직접 검토했다.

| 결정 | 항목(BACKLOG 출현 순서 #) |
|---|---|
| 당장 할 것(개발 대상으로 올림) | 19 「요즘 잘 오르는 ETF」 기본 조회 기준 설정 화면 · 48 추가 runtime 자료원 · 50 PC 에서 OCI PARAM 자동 활성화 |
| 할지 말지 보류 | 33 손익 산식 설명 · 20 ETF Category 라벨 |
| 지금 불편하지 않음(조건부 유지) | 30 · 36 · 37 · 38 · 39 · 28 · 29 · 18 · 51 · 5 · 44 · 26 |
| 보류 · ML 설계 때 함께 결정 | 59 seed(관찰 후보군) 편집 화면 |
| 아직 안 해도 됨(조건부 그대로) | 장애 · 실패가 재개 신호인 24건 · 개발 · 연구 중 처리할 5건 |

- **48**: 원래 범위가 넓다(공포 · 탐욕 지수 · 원/달러 · 원유 · 뉴스 · 보유 평가 · VIX 는 구현됨). 설계 때 어떤 자료를 어느 화면 · 알림에 쓸지 먼저 정하고, 새 외부 자료원 · 외부 호출은 그때 사용자 승인을 받는다.
- **50**: PC 가 OCI 의 실제 운영 값(DB 활성 PARAM)을 바꾸는 새 원격 쓰기 경로다(지금은 화면 '전달'이 OCI JSON 만 바꾸고 활성화는 OCI 수동 스크립트). 실패 · 되돌리기 · 확인 절차를 설계에서 함께 정한다.

**2. 관찰 후보군(seed) 대화 요약** — 59 를 결정하며 확인한 사실.
- 뜻: 사용자가 승인해 정해 둔 ETF 관찰 목록이며 보유 · 비보유를 포함할 수 있다(RESULT 판정 §4 정정 · 아래 '시작'의 첫 제안에 보유 ETF 도 들어 있었다). OCI 가 전체 시장을 훑지 않도록 시세를 받을 범위(이 목록 ∪ 보유)를 정하는 데도 쓰인다.
- 시작: 2026-07-16(PC) · 07-18(OCI) 첫 버전이다. 보유 ETF 비중 상위 최대 10 과 「요즘 잘 오르는 ETF」 상위 최대 10 을 제안받아 사용자가 20종목을 승인했다. 자동 갱신은 없고, ML 결과도 사용자가 승인해야 바뀌는 구조다(사용자 확인).
- 이름만 남은 이유: ① 유지 · 교체 · 갱신 주기 · 재승인 조건과 ML · 백테스트 기반 품질 개선을 '텔레그램 운영 한 바퀴 뒤'로 미뤘고, ML 상대상승 참고점수가 2026-08-29 검증에서 탈락해 쓸 결과가 없었다. ② 이 목록을 쓰던 장중 급등 · 급락 관찰 신호가 폐지(같은 시간대 = 보유 종목 위험 알림)됐고, 신규 ETF 관찰 후보 알림 자리는 08:30 시장 브리핑이 됐다.
- 지금: PC 는 기능 확인용 기본 3종목(2026-08-18) · OCI 는 승인 20종목(설계자 기록)이며 차이는 사용자 결정 대기(B-098)다. PC 「요즘 잘 오르는 ETF」 위 '신규 ETF 관찰 후보' 카드만 쓰고, OCI 아침 배치는 이 목록 ∪ 보유 시세를 받는다(그 계산 결과를 쓰는 알림은 없다).

**3. 정리된 순서(사용자)**: 당장 할 것 = 19 · 48 · 50 / 향후 할 것 = 나머지 조건부(재개 신호가 실제로 생기면) · 보류 33 · 20 / ML 이후 할 것 = ML 설계 통합 4건(3 · 55 · 57 · 62) + 59 · 관찰 후보군을 다시 쓸지.

**4. 설계자께 드리는 요청**
- POC5-25 종료 뒤 다음 설계 후보로 19 · 48 · 50 을 검토해 주세요(선형 진행 · 우선순위 · 범위는 설계자 판단).
- 다음 ML 설계에서 '후보 선별'을 목표에 넣을지 정할 때, 관찰 후보군을 '검증된 결과 → 사용자 승인'으로 담는 자리로 다시 쓸지와 59 편집 화면을 함께 판단해 주세요. PC 3종목 · OCI 20종목 차이(B-098)도 그때 함께 정리할 수 있습니다.


## 12. 검증자 r1 — 2026-10-19

```text
VERIFIER         = Codex
VERDICT          = VERIFIED
BASE_COMMIT      = 9df40437648bb7e16655315fcd47e46f6499b462
SOURCE_SCOPE     = staged 27파일(A 10 · M 17) · 운영/시험 원본 수정 0
EVIDENCE         = /private/tmp/poc525-verifier-irvvi3u3
COMMIT_PUSH      = 미실행 · 사용자 별도 승인 유지
NEXT             = 설계자 RESULT 판정
```

### 1) A. 기능/산출물 검증

- **A-1 지시 일치: 통과.** 설계 V1·PLAN·PLAN 판정과 staged 구현을 대조했다. D는 후보의 실제 `price_end_date`, 창은 D 이하 원본 최근 20행, 고점은 그 창의 최고 종가, 동률 고점일은 가장 최근 날짜다. 창 안 비정상 종가·허용 밖 출처·연결 문제는 사유와 값 없음으로 나가며 과거 정상 행으로 메우지 않는다. 새 객체가 없을 때 옛 스냅샷으로 채우지 않는다. 두 화면의 표시와 정렬이 같은 객체를 사용하고, 결측은 양방향 맨 뒤·동률은 기존 순서다.
- **A-2 보고 정확성: 통과(목록 메타 직접 보완).** Git 실측은 staged 27(A 10 · M 17), unstaged 0, 사용자 소유 handoff 1건 untracked다. §9 전체 목록은 맞고 §2 시험 목록에만 빠진 `ReturnPeriodLine.test.tsx`를 검증자가 직접 보완했다. 코드 결함과 구분하며 이 누락으로 반려하지 않는다.
- **A-3 산출물 정합성: 통과.** 새 값의 단위·창·기간·고점 날짜·사유가 API와 화면 helper에서 일치한다. 관련 백엔드 50건, 프론트 6파일 84건, 검증자 독립 점검 4건이 모두 통과했다. 사용자 실화면 확인은 §7의 완료 기록을 반영했다.
- **A-4 금지사항 위반: 없음.** 새 라이브러리·외부 API·DB 표·스키마·수집·OCI/PUSH/cron/PARAM·ML 변경이 없다. `9df40437`의 미사용 파일 삭제는 이번 staged 변경 전의 HEAD에 이미 들어 있다. 사용자 고지·해당 커밋·§10 및 BACKLOG의 삭제 완료 기록을 대조했다.

### 2) B. 구현 규칙/구조 품질 검증

- **B-1 fallback 위반: 없음.** 결측/경계는 명시 사유이며 옛 고점 필드·시장 전체 날짜로 대체하지 않는다. DB 열기 실패도 정상값으로 숨기지 않는다.
- **B-2 단일 책임 위반: 없음.** 저장 창 계산/읽기는 `pc_stored_drawdown.py`, 화면 표시/기간 묶음은 `storedDrawdown.ts`, 응답 연결은 PC API에 한정된다.
- **B-3 파일 책임 과다: 없음.** 백엔드 신규 모듈 135줄, 화면 helper 123줄, `JudgmentWorkbenchView.tsx` 849줄로 계약을 충족한다. 이번 변경 파일의 KS-10 트리거는 없다.
- **B-4 실험/운영 경계 위반: 없음.** `compute_topn`·연구용 `drawdown_20d`·OCI 보유 브리핑은 바뀌지 않는다. 새 객체를 조립하는 호출은 PC 시장 목록 API 한 곳이다. 같은 API의 다른 소비처에 추가 읽기가 생기는 한계는 §5에 기록돼 있다.
- **B-5 배포 경로 영향: 없음.** 새 모듈·화면 helper·시험은 모두 index에 추적된다. 기존 파일 이동·배포 스크립트 변경은 없으며 import/API 시험이 통과했다. 사용자 handoff는 포함하지 않았다.
- **B-6 기술부채/구조적 퇴행: 없음.** 과거 스냅샷을 현재값으로 재사용하지 않는다. 한 읽기 전용 연결·종목별 `LIMIT 20`·같은 종목 중복 조회 방지를 독립 임시 DB로 확인했다.

### 3) 기반 문서 준수

- 위반 없음. 신규 문서는 설계·판정·PLAN·RESULT·백로그 처리 판정의 승인된 기록이다. 새 프레임워크·MongoDB·운영 ML 승격은 없다.
- 백로그 등록 62개는 원문·순서·기존 본문을 보존한 채 처리 주석과 요약을 추가했다. 설계자 처리 합계(4·5·4·47·2)와 16개 후속 항목의 귀속 문구가 판정 원문과 일치한다. 검증 중 추가된 사용자 후속 결정도 원문/기존 분류를 지우지 않은 별도 기록으로 보존했다.
- 검증 중 `STATE`·`RESULT`·`BACKLOG`에 추가된 §11 후속 설계 전달 기록은 POC5-25의 기능 구현으로 세지 않았다. 후속 자료원·원격 PARAM 쓰기 등의 구현은 이번 변경에 없다. §8의 16:38 실자료 재확인 수치는 개발자 기록이며 검증자가 라이브 DB로 재측정한 수치가 아니다.

### 4) 코드 안전성

- **위험 수준: NONE.** 바인딩 SQL과 `mode=ro`를 사용한다. 독립 점검에서 임시 DB 해시 불변, 없는 DB의 명시 오류·파일 미생성도 확인했다. 실제 운영 데이터·사용자 보유 파일·`.env`·외부 API를 검증에 사용하지 않았다.

### 5) 범위 폭주

- **폭주 수준: NONE.** §4의 사유 이름/0% 표시/시험 계약 정정은 승인된 계산·표시 경계에 부합한다. 백로그 작업은 문서 분류와 후속 결정 기록이며 관련 기능을 추가하지 않았다.

### 6) 종합 판정

**VERIFIED**

| 검증자가 직접 실행한 검사 | 결과 |
|---|---|
| staged 사본의 POC5-25 + POC5-21 백엔드 | 50 passed |
| staged 사본의 관련 프론트 | 6 files · 84 passed |
| 독립 임시 DB 점검 | 4 passed — 창 밖/미래 가격 제외·최근 동률 고점·DB 해시·한 연결/중복 조회 제한·비정상 행 대체 금지·없는 DB 오류 |
| black `--check`·flake8·Python 구문 검사 | 변경 Python 4파일 통과(검사 시 pyc 미생성) |
| tsc `--noEmit --incremental false`·변경 TS/TSX eslint | exit 0 · exit 0 |
| Git 소스 대조 | 운영 코드·시험·HEAD는 최초 고정본과 동일. 문서 추가분은 따로 읽어 대조하고 최종 메타 기록을 반영 |

개발자의 전체 회귀 3,903건·프론트 전체 762건·변이 15/15 및 17/17은 §8의 개발자 근거로 구분한다. 전체 회귀·전체 변이는 반복하지 않았다. 이번 검증의 시험은 저장소 밖 사본·임시 자료에서 실행했고 원본 운영 코드와 시험은 수정하지 않았다.

### 7) 사용자에게 한마디

POC5-25 구현 검증을 통과했다. 다음은 설계자 RESULT 판정이며, 커밋·push는 별도 승인을 유지한다. 설계자에게 전달할 백로그 후속 요약(§11)과 선행 파일 삭제 사실(§10)을 함께 보존했다.

## 13. 설계자 RESULT 판정 · 종료 (2026-10-19)

- **판정: PASS** — 추가 코드 수정 없이 종료(원문 아래). 추가 재검증 · 실화면 · OCI pull · PC 재기동 · 거래일 대기 · 별도 인계 문서 없음(판정 §2-3).
- **종료 기록(판정 §2-1 · 문서만 · 코드 변경 0)**: 이 결과서(STATUS · §1 · §10 · §11 '뜻' 교체 · 이 절) · PLAN STATUS · STATE 맨 위 줄 · '다음' 줄 · PROGRAM_TRUTH '최종 반영' · market_discovery 줄 · 기능 목록 줄 · BACKLOG(25 항목 '정정 완료' · 잔여 표 '종료' · 최신 합계 · 개발 대상 표 · 사용자 보류 5 · 관찰 후보군 정의).
- **백로그 최신 합계(판정 §3)**: 완료 4 · 대체 · 병합 종료 5 · **개발 대상 3(#19 → #50 → #48)** · ML 설계 통합 4 · 조건부 41('불편 없음' 12 + 장애 조건 24 + 개발 · 연구 조건 5) · 사용자 보류 5(#20 · #33 · #40 · #59 · #60) = 62. 처리 판정 당시 4 · 5 · 4 · 47 · 2 는 BACKLOG 머리 '이력' 표로 남겼다.
- **관찰 후보군 정의 정정(판정 §4)**: §11 '뜻'을 '사용자가 승인해 정해 둔 ETF 관찰 목록이며 보유 · 비보유를 포함할 수 있다'로 교체했다(BACKLOG 머리도 같은 문장). PC 3개 · OCI 20개 차이와 편집 화면 #59 는 ML 후보 선별 설계 때 함께 검토하며 지금 자동 동기화 · 자동 갱신하지 않는다.
- **최종 커밋 범위(판정 §2-1)**: §9 의 27개 그대로(신규 10 · 수정 17) · 종료 기록은 그 27개 안의 문서 내용만 바꿨다. `POC5-26` 설계서(`docs/ai_design/POC5/POC5-26_PC_MARKET_DEFAULT_BASIS_PREFERENCE_DESIGN_V1.md`)는 별도 작업의 원문이라 이 종료 커밋에 넣지 않았다(판정 §2-4) · 사용자 소유 handoff 문서도 넣지 않았다.
- **상태**: `IMPLEMENTED_VERIFIED_CLOSED`(종료 2026-10-19). 다음 = `POC5-26` 「요즘 잘 오르는 ETF」 기본 조회 기준 설정(#19) 짧은 PLAN · 전체 화면 목업.

### 설계자 RESULT 판정 원문 (`POC5-25_STORED_PRICE_DRAWDOWN_EVIDENCE_RESULT_DECISION_2026-10-19.md`)

# POC5-25 RESULT 판정 및 백로그 후속 결정

작성: 2026-10-19 · 설계자 → 개발자 / 사용자
근거: 제출 RESULT §0~§12, 사용자 실화면 확인 §7, 검증자 r1 VERIFIED §12.

**판정: PASS. 추가 코드 수정 없이 종료 정리를 진행한다.**

## 1. RESULT 수용

- 실제 종목 기준일 D 이하 원본 20행, 가장 최근 동률 고점일, % 단위, 창 안 비정상 값·자료원·연결 문제의 명시 사유, 과거 스냅샷 대체 금지는 설계에 부합한다. 두 화면의 표시·정렬·기간이 새 객체를 사용한다.
- §4의 구현 판단을 수용한다: end_date_unknown 사유와 창 끝=D 확인, 0% 중립색·부호 정리, 기존 시험의 새 계약 반영, 동작과 무관한 docstring 정정. 허용 밖 출처를 invalid_price로 되돌린 것은 PLAN 준수 정정이다.
- §5의 제한된 추가 읽기·같은 API 소비처의 추가 읽기·DB 오류 전파·창 안 19개 연결 검사·옛 연구 필드 잔존·다른 고점 지표 불변을 수용한다. 새 성능 프로젝트·오류 격리 프레임워크·전체 이력 조사로 확대하지 않는다.
- 개발자의 전체 회귀 3,903·프론트 762·변이 15/15 및 17/17과 검증자의 직접 실행(백엔드 50·프론트 84·독립 점검 4)을 구분해 수용한다. 설계자가 저장소·라이브 DB·원격을 직접 검증한 것은 아니다.

## 2. 종료 지시

1. 이 판정 원문을 결과서에 붙이고 RESULT·PLAN·STATE·PROGRAM_TRUTH 등 현재 상태를 종료로 맞춘다. 최종 파일 목록·건수는 실제 커밋 범위와 일치시킨다.
2. 사용자 커밋·push 승인을 받아 구현과 종료 기록을 함께 반영한다. 이미 승인된 동일 범위가 있다면 그 승인을 존중한다.
3. 반영 후 IMPLEMENTED_VERIFIED_CLOSED로 종료한다. 추가 재검증·추가 실화면·OCI pull·PC 재기동·거래일 대기·별도 인계 문서는 필요 없다.
4. 후속 설계서는 별도 작업의 원문이다. 25 종료 커밋에 반드시 섞거나 후속 PLAN 완료까지 25를 열어 두지 않는다.

## 3. 백로그 사용자 결정 반영

- 오늘 사용자 결정이 앞선 조건부 분류보다 우선한다. **#19·#48·#50은 개발 대상으로 선정**됐으며, 모두 아직 조건부인 것처럼 기록하지 않는다. 이는 후속 설계 대상 확정이고 자료원 추가·원격 쓰기의 구현 승인과는 구분한다.
- #33·#20은 사용자 보류, #59는 ML의 후보 선별·관찰 후보군 재사용 판단 때까지 보류한다. 기존 보류 #40·#60도 유지한다.
- 최신 요약은 완료 4 · 대체/병합 종료 5 · 개발 대상 3 · ML 설계 통합 4 · 조건부 41 · 사용자 보류 5 = 62다. 사용자 보류 5개는 #20·#33·#40·#59·#60이다. 앞선 4/5/4/47/2 합계는 당시 판정 이력으로 남기고 최신 수행 목록에 오늘 결정을 반영한다. 현재 '불편 없음' 12 + 장애 조건 24 + 개발/연구 조건 5 = 조건부 41이다.
- §10의 삭제 사실을 수용한다. POC5-16 미사용 파일은 사용자 승인과 커밋 9df40437로 삭제 완료다. 설계자의 앞선 '승인 대기'는 그 사실을 반영하지 못한 옛 상태이므로 현재 목록에서 정정하고 다시 승인을 묻지 않는다.

## 4. 관찰 후보군과 다음 순서

- 관찰 후보군은 **사용자가 승인해 정해 둔 ETF 관찰 목록이며 보유·비보유를 포함할 수 있다.** §11의 '아직 보유하지 않은 ETF'라는 설명은 최초 제안에 보유 종목도 포함했다는 같은 절의 기록에 맞춰 이 문장으로 정정한다.
- 현재 PC 표시·OCI 시세 수집의 소비는 남아 있지만 목록의 관찰 신호를 쓰는 알림은 없다는 보고를 수용한다. 목록 전체가 운영에서 삭제됐다는 뜻으로 쓰지 않는다. PC 3개·OCI 20개 차이와 편집 UI #59는 사용자 결정대로 ML 후보 선별 설계 때 함께 검토하며 지금 자동 동기화·자동 갱신하지 않는다.
- **진행 순서: #19 → #50 → #48.** #19는 매일 쓰는 화면의 기본 조회 기준을 적은 변경으로 선택할 수 있어 먼저 한다. 다음 POC5-26 설계서를 함께 전달한다.
- #50은 기존 수동 활성화를 PC에서 실행하는 범위로 설계한다. 실제 활성값 확인·실패·기존 값 복구 의미를 함께 정하되 별도 운영 플랫폼을 만들지 않는다.
- #48은 어떤 자료를 어느 화면·알림에 사용할지 먼저 정한다. 공포/탐욕·환율·원유·뉴스·보유 평가를 전부 한 번에 추가하는 승인이 아니다. 새 외부 자료원·호출은 해당 설계에서 사용자 승인 범위를 확인한다.
- ML 고도화의 목표·기준선·검증·중단 기준 설계는 병행할 수 있다. ML 통합 4건을 별도 선행 기능 4개로 개발하지 않는다. 기존 연구 반려 기록과 운영 ML 미승인 상태는 그대로다.
