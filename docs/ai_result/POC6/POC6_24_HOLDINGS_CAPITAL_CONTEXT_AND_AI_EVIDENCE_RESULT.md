# POC6-24 개발 결과서 — 보유 판단의 현금 · 추가 투입 한도와 AI 근거 연결

작성 2026-11-06 · 작성자: 개발자(VSCode Claude) · 수신: 사용자(실화면 확인) → 검증자(Codex) → 설계자

```text
STATUS   = IMPLEMENTED(2026-11-06) · 사용자 실화면 확인 완료 → 검증자 r1 REJECTED(F1 · P2 · §10) → 정정 뒤 r2 VERIFIED(§11)
           → 설계자 최종 RESULT PASS(2026-11-07 · §12) → 종료 커밋 · push 진행(§13 · CLOSED 는 push 성공 뒤 기록)
           설계 V1 → PLAN V1 · 목업 → 설계자 PLAN 판정 PASS(통합설계 V1.1 · Q1 ~ Q3 (a)) · 사용자 목업 배치 확인
           → 사용자 한 묶음 승인(2026-11-06 · ① 구현 · 가상 자료 시험(Q1 금액 계약 포함) ② 사용자 실화면 ③ 검증 · RESULT 뒤 커밋 · push)
           → 구현 · 관련 / 전체 시험 · 독립 검토 1회(지적 7 · 모두 정정 · §4-2) · 변이 6/6
           → 개발자 r1 정정(2026-11-06 · F1 · §4-3) · 시험 8 추가 · 검증자 재현 시험 사본 실행 · 변이 3/3 · 관련 / 전체 시험 → 검증자 r2 VERIFIED · 승인받은 사본 build 통과 · 프런트 재기동 확인
VERIFIER = Codex r2 VERIFIED(2026-11-06 · §11) · r1 기록은 §10 보존
DESIGN   = docs/ai_design/POC6/POC6_24_HOLDINGS_CAPITAL_CONTEXT_AND_AI_EVIDENCE_DESIGN_V1.md
DECISION = docs/ai_design/POC6/POC6_24_HOLDINGS_CAPITAL_CONTEXT_AND_AI_EVIDENCE_PLAN_DECISION_2026-11-06.md(A 판정 · B 통합설계 V1.1 = 우선)
RESULT   = docs/ai_design/POC6/POC6_24_HOLDINGS_CAPITAL_CONTEXT_AND_AI_EVIDENCE_RESULT_DECISION_2026-11-07.md(최종 RESULT PASS)
PLAN     = docs/ai_plan/POC6/POC6_24_HOLDINGS_CAPITAL_CONTEXT_AND_AI_EVIDENCE_PLAN_V1.md(§8 승인 기록) · 목업 …_MOCKUP.html(가상 금액)
금액     = 이 문서 · 시험 · 로그에 실제 금액 · 계좌 정보 없음(모든 예시 = 설계 AC2 가상 값) · 개발자는 실제 금액을 입력하지 않았다
           (다음은 개발자의 실화면 확인 전 조회 기록: 당시 capital_context.json 없음 · /holdings/enriched 상태 값 NOT_ENTERED)
```

## 0. 요약

- 「보유 현황」 보유 배너 바로 아래에 「자금 기준」 카드를 두었다(보유가 없어도 보인다). 기본 화면 = 제목(직접 입력 · 확인일) → 결론(보유 + 입력 현금 합계 · 보유/현금 구성) → [입력·수정] → 현금 · 추가 투입 한도 · 확인일 · 보유 평가액 · 가격 기준일 → 기준일 차이 · 자동 반영 안 됨 · 집계 단위 안내 → 자세히.
- 편집 = 세 칸 · [저장] [취소] [비우기](세 칸 null 저장). 편집 중 값은 저장에 성공하기 전까지 화면 계산 · 미리보기에 쓰이지 않는다(숫자는 모두 서버 `/holdings/enriched` 의 `capital` 칸). 저장 실패 = 입력값 유지 + 서버 사유.
- 자금 값은 `state/holdings/capital_context.json`(holdings_latest.json · 「보유 OCI 반영」 밖 · 별도 잠금 · 원자 저장 · git 제외)에만 저장된다. 손상 파일은 '확인 불가'로 보이며 덮어쓰지 않는다.
- 종목 행 비중 = 첫 줄 '보유 내 비중'(기존 `market_weight_pct` 그대로) + 계산될 때만 둘째 줄 '입력 현금 포함'(이 계좌 행 ÷ 합계). 구성 막대 제목 = '계좌별 구성 (보유 평가액 기준 · 현금 제외)'.
- 판단 근거 미리보기 = [대상] 다음 [보유 · 자금 기준] 묶음(묶음 11개). 원 단위 금액은 V · C · A · T 네 가지만. 보유 [대상]의 평가비중은 이 묶음으로 옮김(Q2). 후보는 '현재 보유 중 + 종목 합산 두 비중' / '현재 보유 아님 — 보유 비중 없음'(Q3). [AI에게 요청] 한 줄 추가. [복사] · [AI 세션에서 검토] 바로 아래 금액 포함 기본 안내(Q1).
- 기존 시장 비중 분모 · 매입 비중 · 손익 · 세션 저장 경로 · OCI · Telegram/PUSH · PARAM 변경 0.

## 1. 처리한 요구사항

| 통합설계 V1.1 항목 | 상태 | 비고 |
|---|---|---|
| B-2 입력 C · A · 확인일 · 미입력 / 0원 구분 · A 는 C 필요 · 0 ≤ A ≤ C · C 있으면 확인일 · 미래 불가 · 한 묶음 저장 · 수정 · 비우기 | DONE | `app/holdings_capital.py :: validate · save` · `PUT /holdings/capital-context` |
| B-2 '직접 입력한 확인일 기준 값 · 거래/입출금 후 자동 반영되지 않음' 표시 | DONE | 화면 카드 · 미리보기 둘째 줄 |
| B-3 보유 내 비중 불변 · 입력 현금 포함 = 행 ÷ T(완전 · C 입력 · T > 0) · 구성 V/T · C/T · T = 0 = 0원 표시 + 비중 계산 불가 · 보유 없음 + C > 0 = 현금 100% | DONE | `view` · `with_cash_pct` |
| B-3 부분 자료 = T · 현금 포함 비중 · 구성 계산 안 함 · 부분 평가액 기준 명시 | DONE | 화면 결론 글 · 미리보기 '부분 합계 N/M종목' · 종목 비중 '(현금 제외 · 부분 평가액 기준)' |
| B-3 화면 = 계좌 행 · AI = 종목 합산 · 한 행이라도 미평가 = 미확인 · 두 집계 단위 명시 | DONE | 화면 카드 안내 줄(§4-2 검토 4) · 미리보기 '같은 종목 모든 계좌 합산' |
| B-3 가격 기준일 최소 ~ 최대 · 모든 평가 행 = 확인일일 때만 같은 기준일 · 다르면 '기준일이 다른 참고 합계/비중' · 날짜 못 읽음 = 확인 불가 · 보유 없음 = 대상 없음 | DONE | 합계 줄 · 종목 '입력 현금 포함' 비중 · 화면 경고(§4-2 검토 5) |
| B-3 한도는 합계에 더하지 않음 · 매입금액 ≠ 원금 | DONE | '합계에 더하지 않음' · 자세히 |
| B-4 「보유 현황」 배너 아래 기본 노출 · 입력 · 수정 · 미저장 값 미사용 · 저장 실패 입력 유지 · 불러오기 실패 = 확인 불가(0원 아님) · 보유 조회 유지 · AC7 저장 결과 모름(응답 유실 · 예상 밖 서버 오류)을 '바뀌지 않음'으로 단정하지 않고 다시 읽기 | DONE | `CapitalContextPanel.tsx` · `HoldingsView.tsx` · r1 F1 정정(§4-3) |
| B-4 미리보기 [보유 · 자금 기준] · [대상] 평가비중 이동(Q2) · 후보 보유 중 / 아님(Q3) · 미입력 · 읽기 실패 · 부분 평가 설명 · [AI에게 요청] 맥락 · 버튼 근처 기본 안내(Q1) | DONE | §0 |
| B-4 미리보기 · [복사] · AI 세션 = 같은 원문 · 생성 때 고정 · 수정 뒤 옛 원문 · 세션 불변 · 기존 저장 경로 재사용 | DONE | 서버 원문 하나 · 세션 저장 시험(§8-1) |
| B-4 · AC7 자금 미입력 · 읽기 실패여도 미리보기 · AI 세션 사용 가능 | DONE | 보유 파일 읽기 오류 · 자금 줄 예상 밖 실패도 이 묶음만 실패(§4-2 검토 1) |
| B-5 별도 파일 · 별도 잠금 · 원자 저장 · .gitignore(파일 · 저장 중 임시 파일) · holdings_latest.json 무변경 | DONE | §8-4 |
| B-7 AC8 프런트 lint · build | DONE | lint 통과 · 사용자 승인 뒤 프런트 서버만 중지 · 격리 사본 build 통과 · 기존 프런트 재기동/HTTP 200(§11) |
| B-7 AC4 실화면(사용자 직접 입력) | DONE | 사용자 '입력·수정·비우기와 미리보기를 모두 확인했습니다'(2026-11-06) · 실제 금액 기록 없음 |
| PLAN §8 승인 기록 · STATE_LATEST · PROGRAM_TRUTH 반영 | DONE | |
| 승인 ③ 검증 · RESULT 뒤 코드 · 문서 커밋 · push | 진행 | 최종 RESULT PASS(§12) · 실제 커밋 · push 결과는 §13 |

## 2. 변경된 파일 목록

**백엔드**
- `app/holdings_capital.py`: 신규(저장 · 읽기 · 검증 · 계산 `view` · `with_cash_pct` · 미리보기 줄 `preview_lines`)
- `app/api_holdings.py`: 수정(`PUT /holdings/capital-context` · 요청 · 응답 모델 `CapitalPayload` · `CapitalStateResponse` · `CapitalViewResponse`)
- `app/api.py`: 수정(`/holdings/enriched` 응답 `capital` · 행 `cash_inclusive_weight_pct` · 줄 수 588 → 595)
- `app/api_decision_draft_preview.py`: 수정(`_load_capital_lines` · 엔드포인트에서 자금 줄 전달)
- `app/decision_draft_preview_service.py`: 수정(`build_preview_text(capital_lines)` · 묶음 삽입 · 보유 [대상] 둘째 줄)
- `app/decision_preview_lines.py`: 수정(`AI_REQUEST` 세 번째 줄)
- `.gitignore`: 수정(`state/holdings/capital_context.json` · `state/holdings/.capital-*.tmp`)

**프런트**
- `frontend/app/components/holdings/CapitalContextPanel.tsx`: 신규(자금 기준 카드 · r1 정정 = 저장 실패 종류 구분 `refusedBeforeWrite` · 결과 모름 때 다시 읽기)
- `frontend/app/components/HoldingsView.tsx`: 수정(capital 상태 · 카드 배치 · 보유 없음일 때도 카드)
- `frontend/app/components/EnrichedHoldingsSection.tsx`: 수정(`capitalSlot` · 행 비중 두 줄 · 구성 막대 제목 · null 비중 표시)
- `frontend/app/components/holdings_compare/DecisionDraftPreviewCard.tsx`: 수정(`AMOUNT_NOTE` 기본 안내 · 도움말 한 문단)
- `frontend/lib/api/holdings.ts`: 수정(`CapitalView` 등 형 · `saveCapitalContext`)
- `frontend/app/globals.css`: 수정(`cap-*` · 행 둘째 줄 스타일)

**시험**
- `tests/test_poc6_24_capital_context.py`: 신규(65)
- `frontend/app/components/holdings/CapitalContextPanel.test.tsx`: 신규(27 · r1 정정 8 포함)
- `tests/test_decision_draft_preview.py` · `tests/test_poc5_23_decision_preview_bundles.py` · `tests/test_poc6_07_selected_moving_average.py`: 수정(묶음 목록 · 개수 10 → 11 · 시장 흐름 위치 2 → 3 · [대상] 평가비중 → 새 묶음 '보유 내 X%' — 단언 약화 없음)

**문서**
- 신규: 이 결과서
- 수정: `docs/ai_plan/POC6/POC6_24_HOLDINGS_CAPITAL_CONTEXT_AND_AI_EVIDENCE_PLAN_V1.md`(STATUS · §8 승인 기록) · `docs/PROGRAM_TRUTH.md`(최종 반영 줄 · §5.1 holdings 행 · §5.2 holdings · §6.1 enriched · 새 PUT 행 · decision-draft/preview · §7.2 capital_context.json 행 · 프로세스 A · 부록 A) · `docs/STATE_LATEST.md`
- 앞 단계(PLAN 제출 · 판정 보관)에서 staged 된 문서(설계 V1 · PLAN 판정 원문 · POST23 사실 회신 · 목업)는 이번 구현에서 바꾸지 않았다.

Dockerfile · 배포 스크립트 · OCI 경로 · 연구 코드(H1 · POC6-19 ~ 23) 변경 없음.

## 3. 신규 추가된 의존성

없음.

## 4. 지시문 외 변경 · 구현 판단

### 4-1. 판단(같은 계약 안의 구현 결정)

- **[저장] 때 두 금액이 모두 빈칸이면 보내지 않음**: '현금과 한도가 모두 비어 있습니다 — 모두 지우려면 [비우기]를 누르세요.' 확인일 기본값(오늘)이 남아 서버가 '현금이 비어 있으면 확인일도 비워 두세요'로 거절하는 대신 [비우기]로 안내한다. 숫자 아닌 글 · 소수도 화면에서 먼저 막는다(서버 검증은 그대로).
- **확인일 칸 = 날짜 입력(`type="date"` · max = 오늘 KST)**: 첫 입력 기본값 = 오늘(B-2). 지난 날짜 가능.
- **시세가 하나도 없을 때 미리보기 첫 줄 = '보유 평가액 확인 불가'**: 합 0 을 '0원'으로 적지 않는다(화면도 '계산 불가').
- **자금 줄 예상 밖 실패 = 이 묶음만 '만들지 못했습니다' 한 줄**: 기존 시장 흐름 묶음(`_market_flow_section`)과 같은 방식(traceback 은 서버 로그). 보유 파일 읽기 오류는 기존 후보 경로와 같은 예외 묶음(`OSError` · `ValueError` · `HoldingsValidationError`)으로 '확인 불가' 한 줄.
- **`build_preview_text` 를 자금 줄 없이 부르면 '확인 불가' 한 줄**: 묶음은 늘 있다(직접 부르는 시험 · 다른 호출자용).
- **[대상] 이 보유인데 등록 보유에 그 종목이 없을 때** '이 종목: 현재 등록 보유에 없음 — 보유 비중 없음'(보유 근거 응답에만 있는 경우 대비).

### 4-2. 독립 검토(1회 · 코드 + 계약 문서 · 읽기 전용) — 지적 7 · 모두 정정

| # | 지적 | 정정 | 확인 |
|---|---|---|---|
| 1 | 후보 미리보기: 보유 파일이 깨진 UTF-8 · 같은 이름 폴더면 자금 줄이 예외를 올려 미리보기 전체 실패(기존 후보 경로는 잡음 · B-4 · AC7) | 보유 읽기 예외 = 후보 경로와 같은 묶음 · 그 뒤 단계 실패 = 이 묶음만 실패 줄 | 시험(UTF-8 · 폴더 · 시세 캐시 예외 · 후보 미리보기 200) · 변이 M1 · M5 |
| 2 | 자금 파일 깊은 중첩(`"[" * 200000`) = `RecursionError` → `/holdings/enriched` 500 | 읽기 실패로 처리 | 손상 표 + 1 · 변이 M2 |
| 3 | `schema_version` 이 `true` · `1.0` 이어도 통과 | 형식 버전은 정수 1만 | 손상 표 + 2 · 변이 M3 |
| 4 | 화면에 '계좌 행 기준 / 미리보기 = 종목 합산' 집계 단위 글 없음(B-3 '두 표현의 집계 단위를 명시') | 카드에 안내 줄(보유가 있을 때) | vitest |
| 5 | 기준일이 다를 때 '참고'가 합계에만 붙고 비중에는 없음(B-3 '참고 합계/비중') | 미리보기 종목 '입력 현금 포함' 비중에 '(기준일이 다른 참고 비중)' · 확인 불가 표시 · 화면 경고 '참고 합계 · 비중(종목 행 포함)' | 시험 3조합 · vitest · 변이 M4 |
| 6 | 저장 중 임시 파일 `.capital-*.tmp` 가 git 제외 안 됨(A-3 · B-5 임시 산출물) | `.gitignore` 한 줄 | `git check-ignore` · 시험 · 변이 M6 |
| 7 | 보유 응답 자체가 실패해도 '자금 기준을 불러오지 못했습니다 … 보유 조회는 그대로'로 안내(AC7 오인) | 보유 응답 실패 = '보유 현황을 불러오지 못해 자금 기준도 확인할 수 없습니다' · 자금 파일만 실패 = 기존 글 | vitest |

변이 확인은 저장소 밖 사본에서만(켜 둔 백엔드 `--reload` 가 저장소 `app/` 변경에 반응하므로) · 바이트 그대로 복원 · `PYTHONDONTWRITEBYTECODE=1` → **잡힘 6/6**.

### 4-3. 검증자 r1 정정(2026-11-06 · F1 · P2)

**지적**: [저장] · [비우기]의 PUT 이 서버에서 원자 교체를 마친 뒤 응답만 잃어도(연결 끊김 · 예상 밖 500) 카드가 '저장된 값은 바뀌지 않았습니다'로 단정하고 다시 읽지 않았다(최초 입력 · 수정 · 비우기 모두).

**정정**(`frontend/app/components/holdings/CapitalContextPanel.tsx`):

| 실패 종류 | 판정 근거 | 화면 |
|---|---|---|
| 422 입력 오류 | 서버가 검증에서 쓰기 전에 거절(`holdings_capital.validate` · 요청 모델) | '저장하지 못했습니다 — 사유 · 저장된 값은 바뀌지 않았습니다' · 다시 읽지 않음(지금과 같음) |
| 500 + detail 머리 '자금 기준 파일 손상' | 서버가 손상 파일을 읽는 단계(쓰기 전)에서 거절(`save` 의 `_read_doc`) | 위와 같음 |
| 그 밖(연결 끊김 · 시간 초과 · 다른 500 · 502 등) | 요청을 보낸 뒤 결과를 모름 — 이미 저장됐을 수 있음 | '저장 결과를 확인하지 못했습니다(서버 응답을 받지 못함 / 서버 오류 HTTP n) — 서버에 이미 저장됐을 수도 있어 저장된 값을 다시 읽습니다(아래 「지금 저장된 값」) · 입력값 유지 · 같은 값으로 다시 [저장]해도 됨' · **서버 값 다시 읽기(`onSaved` = `/holdings/enriched` 재조회)** |
| 저장 성공 | — | 보기 화면 · 다시 읽기(지금과 같음) · 다시 읽기 실패는 부모가 알림(저장 실패로 바꾸지 않음) |

- 판정 함수 `refusedBeforeWrite`(내보냄) · 손상 문구 머리는 `app/api_holdings.py :: put_capital_context` 의 500 detail 과 같은 글(양쪽 주석 · 백엔드 시험을 `startswith` 로 강화).
- 결과 모름 뒤 편집 칸의 「지금 저장된 값」은 다시 읽은 서버 값으로 바뀐다(입력값과 비교 가능). 다시 읽기까지 실패하면 카드는 '보유 현황을 불러오지 못해 … 확인할 수 없습니다'(어느 쪽도 '바뀌지 않음'이라 말하지 않음). PUT 은 세 칸 한 묶음 교체라 같은 값 재저장이 안전하다.
- 백엔드 동작 변경 없음(주석 1줄 · 시험 단언 강화).

**시험**(`CapitalContextPanel.test.tsx` · 19 → 27): 최초 입력 · 수정 · 비우기 × 응답 유실, 수정 × 500(본문 'Internal Server Error') · 502 → 결과 모름 안내 · '바뀌지 않았습니다' 없음 · 다시 읽기 1회 · 서버에 보낸 값 · 입력 유지 / 손상 500 = 쓰기 전 거절 · 다시 읽지 않음 / 저장 성공 뒤 다시 읽기 실패 = 알림 없음 · 보기 화면 / `refusedBeforeWrite` 표(422 · 손상 500 · 일반 500 · 다른 detail · 0 · 502 · 연결 오류).

**검증자 재현 시험**(`/private/tmp/poc624-r1-verify-sj3b0is7/src/frontend/app/components/holdings/CapitalContextVerifier.test.tsx`)을 정정 코드의 저장소 밖 사본에서 그대로 실행: 3건 모두 `expect(saved).not.toHaveBeenCalled()` 한 줄에서 실패(정정 뒤에는 다시 읽기를 1회 하므로 — 이 줄은 정정 전 결함 상태 '다시 읽기 안 함'을 적은 줄). 그 한 줄만 `toHaveBeenCalledTimes(1)` 로 바꾼 변형 = **3 passed**(서버 쪽 저장 완료 · 단정 문구 없음 단언 통과). 저장소에는 넣지 않았다.

**변이**(저장소 밖 사본 · 원복 뒤 `cmp` 동일): R1 모든 실패를 쓰기 전 거절로 · R2 결과 모름 때 다시 읽기 안 함 · R3 모든 5xx 를 쓰기 전 거절로 → **잡힘 3/3**.

**실화면 확인과의 관계**: 이번 정정은 '결과를 모를 때'의 안내 글 · 다시 읽기만 바꾼다. 정상 입력 · 수정 · 비우기 · 미리보기 화면은 바뀌지 않았다(사용자 실화면 확인 범위 그대로). 바뀐 경로(응답 유실 · 예상 밖 서버 오류)는 실화면에서 일부러 만들기 어려워 시험으로 확인했다.

### 4-4. 지시문 외 변경

- **보유 행 비중 칸의 값 없음(null) 표시 정정**: 기존 `fmtPct(null)` 이 '0%'를 돌려(`toFiniteNumber(null)` = `Number(null)` = 0) 시세 없는 행이 '비중 0%'로 보였다. 이번에 둘째 줄을 넣은 같은 칸이라 null 이면 기존 분기 '비중 계산 불가'가 나오게 먼저 거른다(설계 B-3 '부분 자료를 완전한 비중으로 표시하지 않는다'와 같은 방향). 같은 원인의 다른 칸은 고치지 않았다(§7).

## 5. 알려진 한계 / 미완성

- **프런트 build(AC8) 확인 완료**: 개발 단계에는 dev 서버(3000)와 전역 훅 때문에 미실행이었다. 검증자 r2에서 사용자의 '지금 중지·build·재기동 승인'을 받고 프런트 서버만 중지한 뒤 격리 사본 build를 통과했다. 기존 프런트를 다시 켜 HTTP 200을 확인했다(§11). 백엔드와 저장소의 `.next`는 build에 사용하지 않았고 훅은 우회하지 않았다.
- **사용자 실화면(AC4) 완료**: 2026-11-06 사용자가 '입력·수정·비우기와 미리보기를 모두 확인했습니다'라고 회신했다. 검증자는 실제 금액을 조회하거나 기록하지 않았다. 응답 유실 경로의 F1은 격리 시험으로 별도 확인했다(§10).
- 자금 기준만 읽는 GET 은 없다(계약 요구 아님). 보유 파일이 손상돼 `/holdings/enriched` 가 실패하면 정상인 자금 값도 화면에서 보거나 고칠 수 없다(카드는 '보유 현황을 불러오지 못해 … 확인할 수 없습니다').
- 보유 종목을 고른 미리보기는 기존처럼 보유 파일을 읽지 못하면 실패한다(`_load_holdings_evidence` 기존 예외 범위 · 이번 무변경 · 보유 근거 자체가 없으므로).
- 기존 보유 저장 임시 파일 `.holdings-*.tmp` 도 git 제외 규칙이 없다(이번 범위 밖 · 무변경).
- 현금 · 한도는 수동 값이라 매매 · 입출금 뒤 자동으로 맞춰지지 않는다(설계 B-8 그대로).

## 6. 다음 검증자(Codex)에게 알릴 점

> 검증 전(r1 · r2) 인계 이력이다. 검증 결과는 §10 · §11, 최종 판정은 §12.

- **r1 F1 정정**: 검증자 재현 시험의 `expect(saved).not.toHaveBeenCalled()` 는 정정 뒤 성립하지 않는다(결과 모름 때 다시 읽기 = 정정 내용) · 그 한 줄을 뺀 단언은 통과(§4-3).
- **[대상] 평가비중 이동(Q2)**: 새로 생성하는 원문만 바뀐다. 이미 저장된 AI 세션 원문(옛 '평가비중 X% · 손익률 Y%')은 그대로 열린다(기존 세션 시험 고정 원문 유지 · 프런트 시험 고정 원문도 옛 글 그대로).
- 후보 미리보기가 이제 보유 파일 · 시세 캐시를 읽는다(자금 줄용 · 쓰기 0). 보유 파일 손상 · 예상 밖 실패는 이 묶음만 '확인 불가 / 만들지 못했습니다'(§4-2 검토 1).
- 화면 숫자 표시 함수 `fmtMoney` · `fmtPct` 는 null 을 0 으로 바꾼다. 새 코드는 모두 null 을 먼저 거른다(카드 `won` · 행 두 비중). 그 밖의 기존 호출은 바꾸지 않았다(§7).
- 미리보기의 '입력 현금 포함' 종목 비중 = 종목 합산 평가금액 ÷ T(반올림 소수 둘째) · '보유 내' = 기존 `_aggregate_enriched_by_ticker` 값 그대로(분모 = 시세 있는 행 평가액 합).
- `PUT` 요청 모델은 세 칸 모두 필수(빠진 칸 = 422 · 비움으로 보지 않음) · 형 검사는 모듈(JSON 정수만 · 불 · 소수 · 문자열 · NaN 거부).
- `api.py` 595줄(KS-10 근접 600 미만) · `EnrichedHoldingsSection.tsx` 735줄(근접 850 미만) — 새 책임(자금 입력)은 별도 컴포넌트.

## 7. 사용자 확인이 필요한 항목

> 아래 세 항목은 모두 처리됐다(2026-11-07 · 최종 RESULT 판정 §2 · §3 · §4). 남은 사용자 확인 없음.

1. **실화면 확인(승인 ②): 완료(2026-11-06).** 사용자가 입력 · 수정 · 비우기와 미리보기를 모두 확인했다고 회신했다. 실제 금액은 기록하지 않았다. r1 정정은 응답 유실 · 예상 밖 서버 오류 때의 안내 글 · 다시 읽기만 바꿔 확인한 정상 화면은 그대로다(§4-3) — 최종 RESULT 판정 §2 · §3-1 이 같은 실화면 확인을 다시 요구하지 않음으로 정리했다.
2. **프런트 build: 승인 및 확인 완료.** 검증자 r2가 사용자 승인 뒤 프런트만 중지 → 격리 사본 build 통과 → 기존 프런트 재기동/HTTP 200을 확인했다(§11). 실제 저장소의 `.next`를 삭제하거나 build하지 않았다.
3. **같은 원인의 기존 표시 결함 2건(이번 범위 밖 · 이번 미변경)**: 시세 없는 보유 행의 '매입 X → 현재 0원' · 행 상세 평가금액 '0원'(`fmtMoney(null)` = '0원'). 최종 RESULT 판정 §4 = **둘 다 결함으로 확정 · POC6-24 코드 · 커밋과 분리 · 종료 직후 다음 단일 작업(별도 설계)** · 범위 = 해당 표시 경로에서 미확인 · 평가 불가와 0 구별(공통 숫자 함수 전역 교체 · 화면 재설계 · 새 조회 · 계산 · DB · ML 아님).

## 8. 검증 실측(2026-11-06)

### 8-1. 시험 · 검사

- 백엔드: `black --check`(변경 · 신규 Python 10개 · 변경 없음) · `flake8` 통과 · `py_compile` 통과.
- 새 시험 `tests/test_poc6_24_capital_context.py` 65 + 기존 미리보기 시험 4개 파일(새 계약 갱신 3 + 세션 1) 229 = 294 통과(검토 정정 뒤 실행).
- **전체 pytest(r1 정정 뒤 · `pytest tests/ -q`)**: 5,493 통과 · 2 건너뜀 · 실패 0(1,663초) · 라이브 DB 사본 해시 세션 전후 같음(`[live-db-copy]` 두 줄). r1 정정 전 실행도 같은 수(5,493 · 2 · 0) — r1 은 백엔드 동작을 바꾸지 않았다(주석 1줄 · 단언 강화)
- 프런트(r1 정정 뒤): `npx tsc --noEmit` 통과 · `npm run lint`(eslint) 통과 · `npx vitest run` 80파일 1,179 통과(`CapitalContextPanel.test.tsx` 27 포함).
- 검증자 r2의 관련 시험 · 정적 검사 · 격리 사본 build 결과는 §11에 별도 기록했다. 개발자의 전체 회귀를 반복 실행한 수치가 아니다.
- 변이: 검토 정정 6/6(§4-2) · r1 정정 3/3(§4-3).

### 8-2. 줄 수(KS-10 · 백엔드 핵심 650 · 프런트 900 · 시험 1,500)

| 파일 | HEAD | 지금 |
|---|---|---|
| `app/holdings_capital.py` | 신규 | 425 |
| `app/api.py` | 588 | 595 |
| `app/api_holdings.py` | 73 | 126 |
| `app/api_decision_draft_preview.py` | 359 | 419 |
| `app/decision_draft_preview_service.py` | 281 | 299 |
| `app/decision_preview_lines.py` | 493 | 496 |
| `frontend/app/components/holdings/CapitalContextPanel.tsx` | 신규 | 408 |
| `frontend/app/components/EnrichedHoldingsSection.tsx` | 725 | 735 |
| `frontend/app/components/HoldingsView.tsx` | 153 | 166 |
| `frontend/app/components/holdings_compare/DecisionDraftPreviewCard.tsx` | 298 | 306 |
| `frontend/lib/api/holdings.ts` | 384 | 428 |
| `tests/test_poc6_24_capital_context.py` | 신규 | 928 |
| `frontend/app/components/holdings/CapitalContextPanel.test.tsx` | 신규 | 449 |
| `tests/test_decision_draft_preview.py` | 775 | 784 |
| `tests/test_poc5_23_decision_preview_bundles.py` | 918 | 919 |
| `tests/test_poc6_07_selected_moving_average.py` | 1004 | 1011 |

위 표에서 측정한 이번 변경 파일 기준으로 근접(백엔드 ≥ 600 · 프런트 ≥ 850 · 시험 ≥ 1,450) · 트리거 파일 없음(`wc -l` 실측 · 저장소 전체 측정 아님).

### 8-3. 개발자의 실화면 확인 전 라이브 확인 기록(읽기 전용 · 금액 출력 없음)

- 백엔드(:8000 `--reload`)가 바뀐 코드로 다시 올라온 뒤 `GET /holdings/enriched` 의 상태 값만 확인: `capital.status = NOT_ENTERED` · `total_reason = NO_CASH` · `price_date.state = KNOWN` · 모든 행에 `cash_inclusive_weight_pct` 칸 있음.
- 라이브 `state/holdings/` 에 `capital_context.json` 없음(파일 이름만 확인 · 개발자 쓰기 0).

### 8-4. 저장 분리 · git 제외(AC8 · 실제 OCI 적용 실행 없음)

- 시험: 가상 자료로 자금 저장 · 비우기 뒤 `holdings_latest.json` 바이트 동일 · `cash_krw` · `limit_krw` 문자열 없음.
- `git check-ignore -v`: `state/holdings/capital_context.json` → `.gitignore:170` · `state/holdings/.capital-abc123.tmp` → `.gitignore:171`.

## 9. git 상태(r1 정정 뒤 보고 직전 실측 · `git status --short --untracked-files=all`)

```text
M  .gitignore
M  app/api.py
M  app/api_decision_draft_preview.py
M  app/api_holdings.py
M  app/decision_draft_preview_service.py
M  app/decision_preview_lines.py
A  app/holdings_capital.py
M  docs/PROGRAM_TRUTH.md
M  docs/STATE_LATEST.md
A  docs/ai_design/POC6/POC6_24_HOLDINGS_CAPITAL_CONTEXT_AND_AI_EVIDENCE_DESIGN_V1.md
A  docs/ai_design/POC6/POC6_24_HOLDINGS_CAPITAL_CONTEXT_AND_AI_EVIDENCE_PLAN_DECISION_2026-11-06.md
A  docs/ai_design/POC6/POC6_POST23_CLOSEOUT_AND_CAPITAL_CONTRACT_CHECK_2026-11-06.md
A  docs/ai_plan/POC6/POC6_24_HOLDINGS_CAPITAL_CONTEXT_AND_AI_EVIDENCE_PLAN_V1.md
A  docs/ai_plan/POC6/POC6_24_HOLDINGS_CAPITAL_CONTEXT_MOCKUP.html
A  docs/ai_result/POC6/POC6_24_HOLDINGS_CAPITAL_CONTEXT_AND_AI_EVIDENCE_RESULT.md
M  frontend/app/components/EnrichedHoldingsSection.tsx
M  frontend/app/components/HoldingsView.tsx
A  frontend/app/components/holdings/CapitalContextPanel.test.tsx
A  frontend/app/components/holdings/CapitalContextPanel.tsx
M  frontend/app/components/holdings_compare/DecisionDraftPreviewCard.tsx
M  frontend/app/globals.css
M  frontend/lib/api/holdings.ts
M  tests/test_decision_draft_preview.py
M  tests/test_poc5_23_decision_preview_bundles.py
M  tests/test_poc6_07_selected_moving_average.py
A  tests/test_poc6_24_capital_context.py
?? docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md
```

- 오른쪽 열 공백 = 작업 트리와 staged 같음 · `??` 1건 = 사용자 소유 handoff(`docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md` · stage 하지 않음).
- `A` 문서 6건 = 설계 V1 · PLAN 판정 원문 · POST23 사실 회신 · PLAN · 목업(앞 단계 PLAN 제출 · 판정 보관에서 staged · PLAN 은 이번에 STATUS · §8 승인 기록만 갱신) + 이 결과서. 커밋 · push 는 검증자 확인 · 설계자 RESULT 뒤(승인 ③).

## 10. 검증자 r1 — REJECTED(2026-11-06)

대상: HEAD `1a4a4698043c95a7ac8039a1a8d1fbfdbe13ec8d` 대비 staged 26개, 통합설계 V1.1 · PLAN · 결과서 · 실제 index 소스. 사용자의 실화면 확인 완료 회신을 AC4 근거로 수용했다. 검증 근거는 저장소 밖 `/private/tmp/poc624-r1-verify-sj3b0is7/`에 두었으며, 제품 코드/시험은 수정하지 않았다.

### 10-1. A. 기능/산출물 검증

- **A-1 지시 일치: 위반(F1 · P2).** `frontend/app/components/holdings/CapitalContextPanel.tsx:125~127`은 PUT의 연결 오류/응답 유실까지 모두 '저장된 값은 바뀌지 않았습니다'로 단정한다. 서버는 `holdings_capital.save`에서 원자 교체를 마친 뒤 응답하므로, 저장된 값이 이미 바뀐 상태에서 응답만 잃을 수 있다. 이때 화면의 이전 값/미반영 안내와 서버 저장값이 엇갈린다. 통합설계 B-4의 실패 상태 구분과 AC7의 실제 반영 상태를 오인하지 않는 계약을 충족하지 못한다. 최초 입력 · 수정 · 비우기 모두 같은 경로다.
- **A-2 보고 정확성: 통과(진행 메타 갱신).** 실제 staged 26개와 변경 목록이 맞으며 신규 의존성 · 기존 연구/OCI 코드 변경은 없다. 사용자가 확인을 마쳤으므로 머리말 · AC4 · §5 · §7의 실화면 대기를 완료로 갱신하고, 개발자의 미입력 조회 기록은 실화면 확인 전 기록으로 구분했다. 실제 금액은 기록하지 않았다. build 미실행은 통과로 바꾸지 않았다. 설계자 원문 세 곳의 줄 끝 두 공백(Markdown 강제 줄바꿈)은 보존했고 공백 검사 결과와 분리했다.
- **A-3 산출물 정합성: F1 위반 · AC8 build 미확인.** 관련 백엔드 선택 시험 **277 passed · 1 deselected**, 기존 프런트 시험 **19 passed**, tsc · 대상 eslint · black/flake8/구문 검사 10개 파일은 통과했다. 그러나 아래 검증자 재현은 F1을 확인한다. 개발자의 전체 회귀 5,493 · 프런트 전체 1,171 · 변이 6종은 반복하지 않았다.
- **A-4 금지사항 위반: 없음.** 새 PUT · 저장 파일 · Q1의 V/C/A/T 원문은 승인 범위다. 실제 자금/보유 파일 · 라이브 DB · OCI · 외부 API에 접근하거나 쓰지 않았고, 서버 중지 · 커밋 · push도 하지 않았다.

**F1 재현 근거(가상 값 · 격리 사본만):**

1. 백엔드의 실제 자금 PUT 라우터를 별도 FastAPI 앱에 붙이고, 라우터가 처리된 뒤 응답 단계만 실패하도록 했다. 최초 입력 · 수정 · 비우기 세 경우 모두 HTTP 500이지만 임시 자금 파일에는 새 값/비움이 이미 저장되어 있었다(**3 passed**, 저장 완료 후 응답 실패 가능성을 확인하는 시험).
2. 실제 `saveCapitalContext`/`request`를 쓰는 카드에서 fetch가 저장을 마친 뒤 연결 오류를 반환하는 장면을 만들었다. 최초 입력 · 수정 · 비우기 모두 화면이 '저장된 값은 바뀌지 않았습니다'를 표시하고 다시 읽기 콜백은 호출하지 않았다. 이 단정을 금지하는 기대를 넣은 재현 시험은 현재 코드에서 **3 failed**다.
3. 정상 422 입력 거절과 일반적인 성공/취소는 기존 19개 프런트 시험에서 통과한다. F1은 이 경우들과 구분되는, 요청 전송 뒤 결과를 받지 못한 경로의 결함이다. 파일의 원자 저장 자체가 실패했다는 지적은 아니다.

재현 파일:

- `src/tests/test_poc624_verifier_commit_response.py` — 실제 라우터의 저장 후 응답 실패, 최초/수정/비우기 3경우.
- `src/frontend/app/components/holdings/CapitalContextVerifier.test.tsx` — 대응 화면 계약 3경우(현재 코드에서 실패).
- 로그: `repro-backend.log` · `repro-frontend.log`(모두 위 근거 폴더 아래).

기존 시험의 사본 환경 한계도 구분했다. 실제 시장 DB를 복사하지 않은 첫 실행은 기존 일반 상태 시험 두 개가 DB 부재로 실패했다(276 passed). 사본에 **가상 빈 시장 DB**를 초기화하면 보유 쪽 시험은 통과하고 후보 쪽 한 개는 목록이 비어 있어 실패한다(277 passed). 이 후보 로더와 공통 공급 함수의 AST는 HEAD와 동일하다. 실제 시장 자료를 요구하는 기존 한 건만 선택에서 제외한 최종 관련 실행은 **277 passed · 1 deselected**다. 그 제외를 제품 결함 정정이나 전체 통과로 기록하지 않았다.

### 10-2. B. 구현 규칙/구조 품질 검증

- **B-1 암묵 fallback 위반: 추가 발견 없음.** 미입력/0/부분 평가/읽기 실패, 필수 입력 검증은 구분한다. F1의 결과 단정은 A-1에 별도 기록했다.
- **B-2 단일 책임 위반: 없음.** 자금 저장/계산/표시 함수와 별도 프런트 패널로 책임을 분리했다.
- **B-3 파일 책임 과다: 없음.** 주요 파일의 줄 수는 결과서 실측과 일치하고 KS-10 상한 안이다. 자금 편집 책임을 기존 큰 보유 컴포넌트에 넣지 않았다.
- **B-4 실험/운영 경계 위반: 없음.** 기존 연구 · 수집 · cron · PUSH · PARAM을 변경하지 않았다. 새 코드가 AI/외부 서비스로 자동 전송하지 않는다.
- **B-5 배포/실행 경로 영향: 없음.** 추가 코드/시험/문서가 실제 Git 추적 파일이며, 자금 정본/임시 파일의 git 제외 규칙이 있다. 파일 이동 · 배포 스크립트 변경은 없다. build는 아직 확인하지 못했다.
- **B-6 구조적 퇴행: 추가 발견 없음.** 기존 세션 원문과 기존 비중/손익 계산을 재사용하며 새 이력/동기화 플랫폼을 만들지 않았다.

### 10-3. 기반 문서 준수

통합설계 Q1의 금액 네 종류 한정 예외와 버튼 근처 기본 안내를 확인했다. 실제 금액/계좌 정보/사용자 handoff는 검증 자료에 넣지 않았다. 신규 Markdown은 보고된 설계 · 판정 · PLAN · 결과서 범위다. 기존 시장 비중 분모 · cash_allocation 금지 · 운영 ML 미승격 경계는 유지된다. 시세 없는 행의 비중 null 표시 동반 정정은 같은 표시 칸과 B-3에 직접 연결되는 작은 변경이다.

### 10-4. 코드 안전성

**위험 수준: MEDIUM(F1).** 잘못된 미반영 안내 때문에 사용자가 실제 저장된 자금 맥락과 다른 상태를 믿을 수 있다. 개인정보 외부 전송 · 라이브 데이터 변경은 발견하지 못했다. 검증자는 가상 값과 tmp 파일만 사용했다.

### 10-5. 범위 폭주 및 build 상태

**폭주 수준: NONE.** 기존 '현재 0원'/상세 '0원' 두 표시 문제는 개발자가 밝힌 범위 밖 항목으로 분리하며 이번 F1의 원인이나 새 수정 승인으로 취급하지 않는다.

AC8의 build는 계속 미실행이다. 개발자의 차단 보고는 전역 `/Users/hyungsookim/.claude/hooks/krx_guard_bash.py:100~105`의 조건과 일치한다. 이 훅은 사본 경로와 무관하게 포트 3000이 열려 있으면 build 명령을 막으며, 안내는 'build 가 꼭 필요하면 dev 서버를 내린 뒤 실행하세요'다. 검증자는 훅을 변경/우회하거나 서버를 내리지 않았다. 통합설계 A-3/PLAN §6은 격리 사본 build를 허용하지만, 현재 차단 조건과 AC8 미확인은 완료로 처리하지 않는다. F1 판정은 build 결과와 독립적이며 build 미실행 자체를 F1로 세지 않았다.

### 10-6. 종합 판정

**REJECTED.** 가장 큰 문제는 **F1(P2): 요청 전송 뒤 응답을 받지 못했는데도 자금 저장값이 바뀌지 않았다고 단정하는 것**이다. 기존 정상 시험 통과와 사용자 실화면 확인은 이 실패 경로를 보증하지 않는다. 정정 후 재검증 대상이며, AC8 build도 미확인 상태로 남는다. 새 설계 선택이 필요한 결함으로 분류하지 않는다.

### 10-7. 사용자에게 한마디 및 검증자 수정 내역

이번 단계는 커밋/종료 판정으로 넘길 수 없다. 제품 코드 · 시험 · 실제 자금/보유 자료는 수정하지 않았다.

검증자가 수정한 파일은 **이 결과서 하나**다. STATUS · VERIFIER를 r1 REJECTED로 기록하고, 사용자 회신에 맞춰 실화면 확인 메타를 완료로 갱신했으며, 개발자의 미입력 조회 시점을 구분하고 §10 검증 기록을 추가했다. STATE · PROGRAM_TRUTH · PLAN은 수정하지 않았다. 커밋 · push는 하지 않았다.

## 11. 검증자 r2 — VERIFIED(2026-11-06)

대상: 같은 HEAD `1a4a4698043c95a7ac8039a1a8d1fbfdbe13ec8d` 대비 staged 26개. r1의 최종 소스와 비교하면 정정 코드/시험 4개와 문서 3개만 달라 개발 보고와 일치한다. 그 밖의 범위는 r1의 코드·계약 검토 근거를 재사용했다. 근거 폴더는 `/private/tmp/poc624-r2-verify-va8zy0po/`이며, index 사본에서 가상 값만 사용했다.

### 11-1. A. 기능/산출물 검증

- **A-1 지시 일치: 통과 · F1 해소.** 422 입력 거절과 손상 파일 거절 500만 쓰기 전 거절로 다룬다. 응답 유실/시간 초과/그 밖의 5xx는 결과 미확인 안내를 남기고 서버 값을 다시 읽는다. 부모 `HoldingsView`까지 연결해 최초 입력 · 수정 · 비우기와 재조회 성공/실패를 확인했다. 편집 입력과 '지금 저장된 값'은 구분되며, 재조회 실패는 확인 불가로 표시한다.
- **A-2 보고 정확성: 통과.** r1 대비 변경 파일 7개와 전체 staged 26개가 보고와 맞는다. `app/api_holdings.py`의 AST는 r1과 같아 백엔드 동작 무변경 주장과 일치한다. 기존 시험의 단언은 손상 문구 포함에서 머리 일치로 강화됐다. 줄 수 126 · 928 · 408 · 449도 §8-2와 일치한다.
- **A-3 산출물 정합성: 통과.** 관련 백엔드 **68 passed**(제품 시험 65 + 저장 뒤 응답 실패 재현 3), 프런트 **49 passed**(제품 시험 27 + r1 재현의 재조회 기대 갱신 3 + 부모 통합 시험 19). tsc · 대상 eslint · 변경 Python 2파일 black/flake8도 통과했다. 승인받은 격리 사본 build가 종료 코드 0으로 완료돼 AC8 미확인을 해소했다.
- **A-4 금지사항 위반: 없음.** 새 라이브러리 · 외부 API · DB 구조 · 제품 코드/시험 수정 · 개인 금액 열람은 없다. 승인받은 프런트 중지/재기동만 수행했으며 백엔드는 중지하지 않았다. 커밋 · push는 하지 않았다.

**재현 및 정상 대조 근거:**

- r1 재현 원문을 그대로 돌리면 제품 시험 27개는 통과하고 재현 3개는 `expect(saved).not.toHaveBeenCalled()`에서만 실패한다. 이 줄은 정정 전의 '재조회 없음' 관찰이다. 사본에서 이 한 줄만 `toHaveBeenCalledTimes(1)`로 바꾼 3개는 저장 완료·잘못된 단정 없음까지 통과했다. 원문과 변경본을 근거 폴더에 구분 보존했다.
- 부모 통합 시험 19개: 최초/수정/비우기 × 연결 오류/AbortError/500/502/본문 유실 **15개**, 쓰기 전 거절 422/손상 500 **2개**, PUT 성공 또는 응답 유실 뒤 GET도 실패 **2개**다. 결과 미확인 때 GET은 정확히 1회 추가되고, 다시 읽은 새 값/비움이 표시된다. 쓰기 전 거절에는 추가 GET이 없다. 재조회까지 실패하면 0원/불변 단정 대신 확인 불가로 남는다.
- 로그: `backend.log`, `frontend-original-repro.log`, `frontend-final.log`, `tsc.log`, `eslint.log`, `black.log`, `flake8.log`, `build.log`. 검증자가 만든 시험은 사본 안에만 있으며 저장소에 추가하지 않았다.
- 개발자의 백엔드 전체 5,493 · 프런트 전체 1,179 · 정정 변이 3종은 반복하지 않았다. r1의 기존 사본 관련 시험 277건과 1건 제외 내역은 §10의 당시 근거로 보존하며 r2에서 다시 실행한 수치로 합산하지 않았다.

### 11-2. B. 구현 규칙/구조 품질 검증

- **B-1 fallback 위반: 없음.** 미확인 결과를 성공/실패로 단정하지 않고, 저장 거절·결과 모름·재조회 실패를 구분한다.
- **B-2 단일 책임 위반: 없음.** 기존 패널 안의 저장/재조회 흐름과 작은 오류 분류 함수로 정정했다.
- **B-3 파일 책임 과다: 없음.** 패널 408줄, 백엔드 접점 126줄로 KS-10 기준 안이다.
- **B-4 실험/운영 경계 위반: 없음.** 연구/OCI/PUSH/수집 경로는 r1과 같다.
- **B-5 배포/실행 경로 영향: 없음.** 코드·시험 경로가 Git 추적 대상이며 이동/배포 스크립트 변경은 없다. production build도 통과했다.
- **B-6 구조적 퇴행: 없음.** 기존 PUT과 GET을 사용하며 새 동기화/이력 구조를 만들지 않았다. 성공한 저장의 재조회 오류를 저장 실패로 바꾸지 않는다.

### 11-3. 기반 문서 준수

Q1 금액 네 종류 한정과 기본 안내, 기존 시장 비중 및 과거 세션 보존 범위는 r1과 같다. 신규 Markdown/의존성/엔드포인트는 정정 라운드에서 추가되지 않았다. 사용자 실화면 확인은 정상 경로 변경이 없어 그대로 수용하고, 인위적인 응답 유실은 위 격리 시험으로 확인했다.

### 11-4. 코드 안전성

**위험 수준: NONE(이번 정정 범위에서 미해소 결함 없음).** F1의 저장 결과 오인 경로는 해소됐다. 실제 자금/보유 파일 · 라이브 DB · 외부 API를 읽거나 쓰지 않았다. 프런트 재기동 때 앱이 기존 환경 설정을 사용하게 했으며 검증자가 실제 `.env` 내용을 열람하지는 않았다.

### 11-5. 범위 폭주 및 build/복구

**폭주 수준: NONE.** 기존 시세 없음의 '현재 0원'/상세 '평가금액 0원' 두 항목은 범위 밖으로 남긴다. 이번에 수정하거나 새 결함으로 세지 않았다.

사용자가 '지금 중지·build·재기동 승인'을 회신한 뒤, 확인된 프런트 `next dev`만 정상 종료했다. 포트 3000이 비었는지 확인하고 격리 사본에서 `NEXT_TELEMETRY_DISABLED=1 npm run build`를 실행했다. Next.js 15.5.15의 컴파일 · lint/type · 정적 페이지 4개 생성이 모두 통과했다. 실제 `.env`/개인 자료는 사본에 복사하지 않았다. build 뒤 기존 저장소의 프런트를 `npm run dev`로 재기동해 포트 3000과 `GET /` **HTTP 200**을 확인했다. 백엔드는 유지했고 실제 저장소의 `.next` 삭제/production build는 하지 않았다. 훅 우회도 없다.

### 11-6. 종합 판정

**VERIFIED.** F1 정정 · 관련 실패/정상 대조 · AC8 build를 확인했고 A/B 모든 영역에서 추가 위반은 없다. 다음은 설계자 최종 RESULT 판정이다. 이번 판정이나 build 승인이 별도의 커밋 · push 절차를 대신하지 않는다.

### 11-7. 검증자 수정 내역

검증자가 수정한 저장소 파일은 **이 결과서 하나**다. STATUS/VERIFIER를 r2 VERIFIED로 갱신하고 §1 AC8 · §5 · §7 · §8-1의 build 진행 메타를 실측으로 정정했으며 §11을 추가했다. §8-3의 과거 조회 기록 시점도 명시했다. r1의 §10은 보존했다. STATE · PROGRAM_TRUTH · PLAN · 제품 코드 · 제품 시험은 수정하지 않았다. 최종 staged 26개 · unstaged 0개를 확인하며 사용자 handoff는 계속 제외한다.

## 12. 설계자 최종 RESULT 판정(2026-11-07)

원문 = `docs/ai_design/POC6/POC6_24_HOLDINGS_CAPITAL_CONTEXT_AND_AI_EVIDENCE_RESULT_DECISION_2026-11-07.md`.

- **RESULT PASS** · 검증자 r2 VERIFIED 수용 · r1 F1 정정 수용(r1 REJECTED 기록 보존) · 사용자 실화면 확인과 승인받은 프런트 build 를 완료 근거로 인정.
- 구현 선택 수용: [비우기] 안내 · 날짜 입력 · 자금 묶음 실패의 제한된 표시 · 같은 원문 저장 재사용 · 이번 비중 셀의 null 선거름(공통 숫자 함수 정비로 해석하지 않음). 자금 단독 GET · 손상 보유 파일 복구는 요구 아님(한계 수용 · 새 API 추가 없음).
- 남은 두 표시 결함('현재 0원' · 상세 '평가금액 0원') = 결함 확정 · POC6-24 와 분리 · **종료 직후 다음 단일 작업**(별도 설계 · 포괄 구현 승인 아님).
- 유지 한계: 현금 · 한도는 확인일 기준 수동 값 · 보유 조회 실패 때 자금 정보 확인 불가 · 기존 `.holdings-*.tmp` git 제외 부재는 별도 사실 · 새 모델 · 매매 신호 · 자동 주문 · 수익 개선 검증 아님.
- 승인 ③ 유효 → 종료 커밋 · push 진행(같은 범위 재승인 없음 · OCI 배포 · 운영 변경 미포함) · push 성공 뒤 IMPLEMENTED_VERIFIED_CLOSED. 판정 이후 코드 · 시험 변경 없음 → 전체 회귀 · build · 재검증 반복 없음.

## 13. 종료(커밋 · push · 승인 ③)

- 진행: 이 결과서가 든 종료 커밋(구현 · 시험 · 설계 · 판정 · PLAN · 목업 · 결과서 · 상태 문서 · `.gitignore`)을 `main` 에 커밋하고 `origin/main` 으로 push 한다. 실제 커밋 해시 · 포함 / 제외 · 원격 일치는 push 성공 뒤 이 절에 기록한다(자기 커밋 해시를 미리 적지 않음).
- 제외: 실제 자금 정본(`state/holdings/capital_context.json` · 라이브에 없음) · 보유 정본 · 임시 개인 자료 · 연구 산출물 · 사용자 소유 handoff(`docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md`).
