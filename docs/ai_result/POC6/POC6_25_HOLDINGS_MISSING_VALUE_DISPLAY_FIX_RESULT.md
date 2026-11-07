# POC6-25 개발 결과서 — 보유 시세 · 평가금액의 미확인 표시 정정

작성 2026-11-07 · 작성자: 개발자(VSCode Claude) · 수신: 사용자(실화면 확인) → 검증자(Codex) → 설계자

```text
STATUS   = IMPLEMENTED(2026-11-07) · 사용자 실화면 확인 완료(2026-11-07) → 검증자 r1 VERIFIED(§10)
           → 설계자 최종 RESULT PASS(2026-11-07 · §11) → 종료 커밋 · push 진행(§12 · CLOSED 는 push 성공 뒤 기록)
           설계 V1 → 짧은 PLAN V1 → 설계자 PLAN 판정 PASS(통합설계 V1.1 · Q1 (a) = 세 표시)
           → 사용자 한 묶음 승인(2026-11-07 · ① 구현 · 가상 응답 시험 ② 프런트만 중지 · 격리 사본 build · 재기동 ③ 사용자 실화면 ④ 검증 · RESULT 뒤 커밋 · push)
           → 시험 먼저 작성 · 정정 전 재현(값 없음 2 실패 · 정상 / 0 대조 통과) → 정정 → 렌더 시험 · 프런트 전체 검사 · 격리 사본 build · 프런트 재기동 HTTP 200
VERIFIER = Codex r1 VERIFIED(2026-11-07 · §10)
DESIGN   = docs/ai_design/POC6/POC6_25_HOLDINGS_MISSING_VALUE_DISPLAY_FIX_DESIGN_V1.md
DECISION = docs/ai_design/POC6/POC6_25_HOLDINGS_MISSING_VALUE_DISPLAY_FIX_PLAN_DECISION_2026-11-07.md(A 판정 · B 통합설계 V1.1 = 우선)
PLAN     = docs/ai_plan/POC6/POC6_25_HOLDINGS_MISSING_VALUE_DISPLAY_FIX_PLAN_V1.md(§5 승인 기록)
RESULT   = docs/ai_design/POC6/POC6_25_HOLDINGS_MISSING_VALUE_DISPLAY_FIX_RESULT_DECISION_2026-11-07.md(최종 RESULT PASS)
금액     = 이 문서 · 시험에 실제 금액 · 계좌 정보 없음(모든 예시 = 가상 행) · 백엔드 · 데이터 · 시세 조회 변경 0
```

## 0. 요약

「보유 현황」에서 `current_price` · `eval_amount` 가 값 없음(null · 응답에 칸 없음)일 때 세 자리를 바꿨다. 숫자(0 포함)는 지금과 같다.

| 위치 | 값 없음 — 정정 전 | 값 없음 — 정정 뒤 | 숫자 |
|---|---|---|---|
| 보유 행 '매입 X → 현재 Y' | null = '현재 0원' · 칸 없음 = '현재 확인 불가' | '현재 미확인'(같은 muted 자리 · 매입가 그대로) | 그대로(0 = '현재 0원') |
| 행 상세 '현재가' | null = '0원' · 칸 없음 = 줄 숨김 | '현재가 미확인'(줄 늘 표시) | 그대로 |
| 행 상세 '평가금액' | null = '0원' · 칸 없음 = 줄 숨김 | '평가금액 평가 불가'(줄 늘 표시) | 그대로 |

분기는 형식화 전 `== null` 하나(0 과 미확인을 함께 다루는 조건 없음). 계산 · 데이터 · API · 배치 · 펼침 · 기준시각 · 출처 줄 · 부분 합계 경고 · POC6-24 자금 카드 / 두 비중 · 매입비중 무변경.

## 1. 처리한 요구사항

| 통합설계 V1.1 | 상태 | 비고 |
|---|---|---|
| B-3 행 현재가 값 없음 = '현재 미확인' · 매입가 유지 · 0원처럼 만들지 않음 | DONE | `HoldingRow` |
| B-3 상세 현재가 값 없음 = '현재가' · '미확인'(Q1 (a)) | DONE | `DetailRowFields` |
| B-3 상세 평가금액 값 없음 = '평가 불가' · 계산 · 0 대입 없음 · 항목 숨기지 않음 | DONE | `DetailRowFields` |
| B-3 정상 숫자 · 명시적 0 = 기존 표시 | DONE | 렌더 시험 대조 |
| B-4 접점 한 파일 · 공통 함수 · 다른 화면 · 매입비중 무변경 | DONE | §2 |
| B-5 AC4 실제 컴포넌트 렌더 · 상세 펼침 · null · 정상 · 0 · 누락 네 경우 · 정정 전 재현 | DONE | §4 |
| B-5 AC5 프런트 타입 · lint · 전체 vitest · build | DONE | §4 · build = 승인 ② 방식 |
| B-5 AC6 실제 「보유 현황」 정상 행 · 상세 배치 유지 | DONE | 사용자 실화면(승인 ③) 회신 '네 확인했습니다'(2026-11-07) · 시세 없는 행 경우는 렌더 시험(§4)으로 확인 |
| PLAN §5 승인 기록 · STATE_LATEST · PROGRAM_TRUTH | DONE | |
| 승인 ④ 검증 · RESULT 뒤 코드 · 문서 커밋 · push | 진행 | 최종 RESULT PASS(§11) · 실제 커밋 · push 결과는 §12 |

## 2. 변경된 파일 목록

- `frontend/app/components/EnrichedHoldingsSection.tsx`: 수정(행 `curText` 값 없음 선거름 · 대체 글 '현재 확인 불가' → '현재 미확인' · 상세 현재가 · 평가금액 줄) — 735줄 → 735줄
- `frontend/app/components/EnrichedHoldingsSection.eval.test.tsx`: 수정(POC6-25 묶음 4 · 기존 가상 행 `calcRow` · `unpricedRow` 재사용) — 111줄 → 165줄
- 문서: 설계 V1(우선 연결 한 줄) · PLAN 판정 원문(신규) · PLAN V1(신규 · 판정 반영 · 승인 기록) · 이 결과서(신규) · `docs/STATE_LATEST.md` · `docs/PROGRAM_TRUTH.md`

백엔드 · Python · API · CSS · Dockerfile · 배포 · OCI 변경 없음.

## 3. 신규 추가된 의존성

없음.

## 4. 검증 실측(2026-11-07)

- **정정 전 재현**(새 시험 먼저 · 제품 코드 HEAD 그대로): 7건 중 2 실패 · 5 통과.
  - null: `expected '매입 1,000원→현재 0원' to contain '현재 미확인'`
  - 칸 없음: `expected '매입 1,000원→현재 확인 불가' to contain '현재 미확인'`(대체 분기는 `Number(undefined)` = NaN 일 때만 닿았고, 상세 두 줄은 숨겨졌다)
  - 정상 · 숫자 0 대조는 정정 전에도 통과(판정 A-3 예상대로).
- **정정 뒤**: `EnrichedHoldingsSection.eval.test.tsx` 7 통과(기존 3 + POC6-25 4).
  - 시험 작성 중 내 단언 하나(`not.toContain("0원→")`)가 '매입 1,000원→'에도 걸리는 잘못된 단언이라 지웠다. 현재가 0원 여부는 같은 시험의 `/현재\s*0원/` 단언이 본다.
- `npx tsc --noEmit` 통과 · `npm run lint`(eslint) 통과 · `npx vitest run` **80파일 1,183 통과**.
- **build(승인 ②)**: 저장소 밖 사본에서 build 를 통과한 뒤 원래 프런트 dev 서버를 재기동해 HTTP 200 을 확인했다. 순서 — :3000 의 프런트 `next dev`(이전 단계에 검증자가 다시 켠 프로세스 · 출력은 검증자 임시 폴더)만 정상 종료 → :3000 빔 확인 → 저장소 밖 사본(`.env*` · `node_modules` · `.next` 제외 복사 · `node_modules` 연결 · `NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000`)에서 `npm run build` **종료 코드 0**(컴파일 · lint/type · 정적 페이지 4개) → 저장소 프런트 `npm run dev` 를 창과 무관하게 다시 켬 → `GET /` **HTTP 200**. 백엔드(:8000) 두 프로세스 유지 · build 에 저장소 `.next` 사용 · 삭제 없음 · 훅 변경 · 우회 없음.
- 백엔드 무변경 → 전체 pytest · 라이브 DB 검사 · 변이 시험 제외(설계 B-5 AC5).

## 5. 지시문 외 변경

없음. (행의 대체 글 '현재 확인 불가' → '현재 미확인'은 설계 B-3 문구.)

## 6. 알려진 한계 / 미완성

- 실화면에서 시세 없는 행이 실제로 있었는지는 사용자 회신에 없다. 그 경우는 렌더 시험(§4)으로 확인했다(실제 데이터 수정 · 새 시세 조회로 사례를 만들지 않음).
- 상세 '매입비중'은 그대로다(판정 B-4). 정상 저장 경로에서는 null 이 생기지 않는다는 PLAN 사실 보고만 있다.
- 다른 화면 · 다른 칸의 `fmtMoney(null)` 호출은 조사 · 정정하지 않았다(설계 범위 밖).

## 7. 다음 검증자(Codex)에게 알릴 점

> 검증 전(r1) 인계 이력이다. 검증 결과는 §10, 최종 판정은 §11.

- 상세 두 줄은 `fmtMoney(값) ?? '미확인' / '평가 불가'` 다 — 값 없음(null · 누락)은 그 앞의 `== null` 로 먼저 거르고, 그 밖에 `fmtMoney` 가 null 을 돌려주는 경우에도 같은 자리에 '미확인' · '평가 불가'를 적는다(예전엔 줄이 숨겨졌다).
- 숫자 0 의 현재가는 서버 계약상 응답에 오지 않지만(`_is_valid_price`), 화면 계약대로 들어오면 '0원'을 그대로 보인다(시험 고정).
- 지금 :3000 프런트는 이번 build 뒤 개발자가 다시 켠 프로세스다(출력 = 개발자 scratchpad 의 `poc6_25_dev_restart.log`).

## 8. 사용자 확인이 필요한 항목

1. **실화면 확인(승인 ③): 완료(2026-11-07).** 정상 종목 행의 '매입 → 현재'와 펼친 상세(현재가 · 평가금액 포함)의 배치 · 금액 글 확인을 요청했고, 사용자가 '네 확인했습니다'라고 회신했다. 실제 금액은 기록하지 않았다. 남은 사용자 확인 없음.

## 9. git 상태(보고 직전 실측 · `git status --short --untracked-files=all`)

```text
M  docs/PROGRAM_TRUTH.md
M  docs/STATE_LATEST.md
A  docs/ai_design/POC6/POC6_25_HOLDINGS_MISSING_VALUE_DISPLAY_FIX_DESIGN_V1.md
A  docs/ai_design/POC6/POC6_25_HOLDINGS_MISSING_VALUE_DISPLAY_FIX_PLAN_DECISION_2026-11-07.md
A  docs/ai_plan/POC6/POC6_25_HOLDINGS_MISSING_VALUE_DISPLAY_FIX_PLAN_V1.md
A  docs/ai_result/POC6/POC6_25_HOLDINGS_MISSING_VALUE_DISPLAY_FIX_RESULT.md
M  frontend/app/components/EnrichedHoldingsSection.eval.test.tsx
M  frontend/app/components/EnrichedHoldingsSection.tsx
?? docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md
```

- 오른쪽 열 공백 = 작업 트리와 staged 같음 · `??` 1건 = 사용자 소유 handoff(stage 하지 않음). 커밋 · push 는 검증자 확인 · 설계자 RESULT 뒤(승인 ④).

## 10. 검증자 r1 — VERIFIED(2026-11-07)

대상: HEAD `a3ac13ed7783bb2d900534f1921c3e76f6515393` 대비 staged 8개. 통합설계 V1.1 · PLAN · 결과서와 실제 index diff를 대조했다. 시험은 저장소 밖 `/private/tmp/poc625-r1-verify-s3ze9drh/`의 프런트 소스 사본에서 가상 행으로만 실행했다.

### 10-1. A. 기능/산출물 검증

- **A-1 지시 일치: 통과.** Q1 (a)로 확정한 행 현재가 · 상세 현재가 · 상세 평가금액 세 곳만 바꿨다. `== null`로 null/누락을 형식화 전에 구별하며, 정상 숫자와 명시적 숫자 0은 기존 `fmtMoney` 표시를 유지한다. 상세 항목을 숨기지 않고 매입가와 기존 위치를 유지한다.
- **A-2 보고 정확성: 통과.** staged 8개 · unstaged 0개이며 변경 목록과 일치한다. 제품 파일은 `EnrichedHoldingsSection.tsx` 한 개, 시험 한 개, 문서 여섯 개다. 제품 735줄 · 시험 165줄도 실측과 같다. 백엔드 · API · 공통 숫자 함수 · CSS · 배포 파일 변경은 없다. 원 설계/판정 세 곳의 Markdown 강제 줄바꿈용 두 공백은 원문대로 보존하며 코드 결함으로 세지 않았다.
- **A-3 산출물 정합성: 통과.** 기존 HEAD 제품 코드에 새 시험을 붙이면 **2 failed · 5 passed**이며, 실패 문구는 §4와 같다. index 제품 코드로 되돌린 관련 시험은 **3파일 42 passed**(평가 표시 7 · 정렬 8 · 자금 카드/행 비중/금액 안내 27), tsc 및 대상 eslint는 종료 코드 0이다. 시세 없음 · 누락 · 정상 · 명시적 0의 세 표시와 기존 부분 합계 경고를 실제 컴포넌트 렌더로 확인했다.
- **A-4 금지사항 위반: 없음.** 신규 라이브러리/외부 API/파일 삭제/DB 구조 변경이 없고, 실제 금액 · 계좌 · 보유 정본 · 라이브 DB · 실제 `.env` · 사용자 handoff를 읽거나 수정하지 않았다. 검증자의 제품 코드/시험 수정 · 서버 중지/재기동 · 커밋 · push도 없다.

개발자의 프런트 전체 **80파일 1,183 passed** 및 §4의 승인받은 격리 사본 **build 종료 코드 0 · 프런트 복구 HTTP 200** 근거를 재사용했다. 현재 index 범위를 대조한 뒤 해당 검사를 반복하지 않았으며, 검증자가 독립 실행한 42건과 합산하지 않는다. 설계 B-5대로 백엔드 전체 회귀 · 라이브 DB 검사 · 변이 시험은 요구하지 않았다. 검증자의 재현은 사본 제품 파일만 HEAD/index 사이에서 교체했으며 최종 사본이 index와 같음을 확인했다.

AC6은 보고된 사용자의 정상 행·상세 배치 실화면 확인을 수용한다. 실제 화면에 시세 없는 행이 있었다고 추정하지 않으며, 그 경우는 위 렌더 시험 근거로 구분한다. 새 실화면 확인이나 실제 자료 변경은 요구하지 않는다.

로그: `repro-head.log`(2 실패/5 통과), `related-tests.log`(42 통과), `tsc.log`, `eslint.log`. 모두 위 근거 폴더 아래이며 개인 자료는 포함하지 않았다.

### 10-2. B. 구현 규칙/구조 품질 검증

- **B-1 fallback 위반: 없음.** 미확인/평가 불가는 설계가 명시한 표시 상태이며 숫자 0을 대입하지 않는다.
- **B-2 단일 책임 위반: 없음.** 기존 행/상세 표시 함수 안의 세 호출부만 바꿨다.
- **B-3 파일 책임 과다: 없음.** 제품 파일 735줄로 기존 줄 수와 같고 프런트 KS-10 근접 기준 850줄 미만이다.
- **B-4 실험/운영 경계 위반: 없음.** 새 계산 · 연구 · 수집 · OCI · PUSH 경로는 없다.
- **B-5 배포/실행 경로 영향: 없음.** 제품/시험/문서 경로가 Git 추적 대상이며 파일 이동 · 실행 명령 변경 · 배포 스크립트 영향은 없다.
- **B-6 기술부채/구조적 퇴행: 없음.** 공통 숫자 처리나 다른 화면으로 범위를 넓히지 않았고 과거 결과를 새 계산처럼 재사용하지 않았다.

### 10-3. 기반 문서 준수

신규 Markdown 네 개는 보고된 설계 · 판정 · PLAN · 결과서다. 기존 자금 · 비중 · AI 원문 계약과 정상 0원, 매입비중을 유지했다. 새 UI 프레임워크 · 플랫폼 · 의존성 · 연구 예외는 없다.

### 10-4. 코드 안전성

**위험 수준: NONE(이번 변경 범위에서 미해소 결함 없음).** 변경은 받은 값을 표시하는 분기에 한정되며 새 I/O · 외부 요청 · 인증정보 처리가 없다. 실제 금액이나 개인 화면을 수집하지 않았다.

### 10-5. 범위 폭주

**폭주 수준: NONE.** 상세 현재가의 동반 정정은 설계자 Q1 (a)의 명시 범위다. 다른 `fmtMoney(null)` 호출자나 상세 매입비중을 조사/수정하는 작업은 추가하지 않았다.

### 10-6. 종합 판정

**VERIFIED.** A/B 모든 영역 통과, 추가 결함 없음. 다음은 설계자 최종 RESULT 판정이다. 이 검증은 커밋 · push를 실행한 것이 아니며 기존 종료 승인 절차는 유지한다.

### 10-7. 검증자 수정 내역

검증자가 수정한 저장소 파일은 **이 결과서 하나**다. STATUS · VERIFIER를 r1 VERIFIED로 기록하고 §10 검증 근거/판정을 추가했다. 제품 코드 · 제품 시험 · STATE · PROGRAM_TRUTH · PLAN은 수정하지 않았다. staged 8개 · unstaged 0개를 확인하고 사용자 handoff는 계속 제외했다. 커밋 · push는 하지 않았다.

## 11. 설계자 최종 RESULT 판정(2026-11-07)

원문 = `docs/ai_design/POC6/POC6_25_HOLDINGS_MISSING_VALUE_DISPLAY_FIX_RESULT_DECISION_2026-11-07.md`.

- **RESULT PASS** · 검증자 r1 VERIFIED 수용 · 사용자 실화면(정상 행 · 펼친 상세의 금액 · 배치) 확인 수용 · 시세 없는 행의 동작은 가상 응답 렌더 시험을 근거로 인정.
- 상세 항목의 형식화 함수가 null 을 돌려줄 때도 그 자리에 미확인 문구를 적는 구현 수용.
- 종료 반영: 판정 원문 보관 · 결과서 · PLAN · STATE_LATEST · PROGRAM_TRUTH 에 RESULT PASS · 결과서 §4 build 문구 · §7 인계 이력 구분 · 형식화 설명 한정 · 기존 승인 ④ 로 커밋 · push · push 성공과 원격 일치 뒤 IMPLEMENTED_VERIFIED_CLOSED.

## 12. 종료(커밋 · push · 승인 ④)

- 진행: 이 결과서가 든 종료 커밋(제품 1 · 렌더 시험 1 · 설계 · PLAN 판정 · 최종 RESULT 판정 원문 · PLAN · 결과서 · STATE_LATEST · PROGRAM_TRUTH · 예상 9개)을 `main` 에 커밋하고 `origin/main` 으로 push 한다. 실제 커밋 해시 · 포함 목록 · 원격 일치는 push 성공 뒤 이 절에 기록한다(자기 커밋 해시를 미리 적지 않음).
- 제외: 사용자 소유 handoff(`docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md`) · 개인 자료(보유 · 자금 정본 등).
