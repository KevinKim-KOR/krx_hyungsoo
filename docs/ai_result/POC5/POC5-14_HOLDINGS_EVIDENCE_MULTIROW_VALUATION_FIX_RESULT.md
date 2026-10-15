# POC5-14 개발 결과서 — HOLDINGS_EVIDENCE_MULTIROW_VALUATION_FIX (같은 종목 · 여러 계좌 평가값 정정)

작성 2026-10-15 · 작성자: 개발자(VSCode Claude) · 수신: 검증자(Codex)

```text
STATUS        = IMPLEMENTED_VERIFIED_CLOSED — 검증자 r1 VERIFIED(2026-10-15 · staged 15파일 한정) · 커밋 · push(사용자 승인 2026-10-15 · RESULT 판정 전 · POC5-13 을 따로 stage 하려고) · 설계자 RESULT PASS · 종료(2026-10-15 · §11)
STEP_ID       = POC5-14 같은 종목 · 여러 계좌 평가값 정정
DEFECT        = DEF-HOLDINGS-EVIDENCE-MULTIROW-VALUATION
DECISION      = docs/ai_design/POC5/POC5-14_HOLDINGS_EVIDENCE_MULTIROW_VALUATION_FIX_PLAN_DECISION_2026-10-15.md (PASS · 판정이 좁은 수정 설계를 겸함)
PLAN          = docs/ai_plan/POC5/POC5-14_HOLDINGS_EVIDENCE_MULTIROW_VALUATION_FIX_PLAN_V1.md (V1 · 판정 반영 §5)
BASE_COMMIT   = 12b988bb (POC5-12 종료 커밋)
SCOPE         = 공유 보유 근거 builder 의 행 짝짓기(A) · 요약 composer 의 종목 합산(C) · 사실과 다른 설명 정정
                새 DB · 외부 조회 · 의존성 · API 경로 · 메뉴 · 보유 쓰기 · 알림 원장 · OCI · PUSH 변경 0
REVIEW        = 독립 검토 1회(Workflow · 정확성 · 문서 2관점 · 지적마다 반박 검증 · 2026-10-15) — 확인된 지적 4건 모두 반영(§6-5)
CHECKS        = §8
```

## 0. 요약

- **A. 보유 줄 = 자기 평가 줄**(`app/holdings_market_evidence.py :: build_holdings_market_evidence`)
  - 예전: `enriched_by_ticker = {e.ticker: e ...}` 로 종목마다 마지막 줄만 남겨 보유 줄마다 찾았다. 그래서 같은 종목 여러 줄에 마지막 줄의 평가금액 · 손익률이 복사됐다.
  - 지금: `zip(holdings, enriched_list)` 로 같은 위치끼리 짝짓는다.
  - 짝짓기 전에 길이와 `source_index == 위치` 를 확인한다. 어긋나면 `ValueError` 로 실패하고 대체하지 않는다.
  - `enrich_holdings` 는 입력 한 줄에 출력 한 줄이고 순서 · 길이가 같다(`app/holdings_enrich.py:95` · `:142-187`). 새 ID · DB 는 없다.
- **C. 요약 = 종목 합산**(`app/market_summary_composer.py :: _ticker_valuations` 신규 · `select_top_holdings` · `summarize_holdings`)
  - 계산 규칙
    - 평가 = 같은 종목 줄 평가금액 합(한 줄이라도 없으면 없음)
    - 매입 = Σ 수량 × 평균매입단가(계산할 수 없으면 없음)
    - 손익률 = (평가 − 매입) ÷ 매입 × 100 을 소수 둘째 자리로(매입이 없거나 0 이하면 없음)
    - 비중 = 평가 ÷ 기존 전체 합(확인된 줄 평가 합) 을 소수 첫째 자리로
  - 한 줄 종목은 그 줄 값을 그대로 쓴다(§4-1).
  - 선정(5일 유효) · 5일 낮은 순 · 동률 ticker 순 · 최대 3개 · 전체 합계 결측 처리는 그대로다.
  - `need_check` 판정 규칙도 그대로이고, 판정 입력(평가 · 손익 · 비중)만 종목 합산 값으로 바뀐다.
  - 같은 요약 함수를 두 경로가 쓴다(입력은 다름).
    - 수동 PC 보유 초안: `app/draft.py` 가 공유 builder 결과의 `judgment_summary` 를 그대로 `app/draft_message.py` '[오늘 먼저 볼 보유 ETF]'에 쓴다.
    - PC 화면 응답: 그 결과의 사본에서 가격 흐름 기준일을 고친 뒤 `summarize_holdings` 로 요약을 다시 만든다(`app/pc_price_basis.py:220`). 그래서 최대 3개 선정은 다를 수 있다.
    - 두 경로 모두 시험으로 확인했다(§8).
- **실제 PC 응답 확인**(2026-10-15 · 사용자 서버 · 읽기 전용 GET · 자동 다시 읽기로 고친 코드)
  - 069500 줄별 평가: 284,415 / 1,422,075 / 189,610원(예전 세 줄 모두 189,610). 367760: 160,725 / 214,300원(예전 둘 다 214,300).
  - 요약 합계 14,134,755원 = 정상 보유 평가 합(예전 12,861,060원).
  - 최대 3개 비중 · 손익 = 정상 종목 합산
    - 0193T0: 0.4% · −78.00%
    - 000660: 10.1% · +159.09%
    - 395160: 4.5% · −34.83%
    - 예전 비중은 0.5 · 11.1 · 4.9%
  - coverage = 전체 29 · 자료 확인 필요 0 · 정상 29(그대로)
  - PC 응답 사본 요약으로 같은 메시지 함수를 돌린 줄: '비중 0.4% / 손익 -78.00% …'(초안 실행 기록은 만들지 않음 · 수동 초안 자체는 공유 builder 요약을 쓰고, 그 경로는 시험으로 확인)
- **바뀌지 않는 것**
  - OCI 정기 보유 브리핑 · 보유 위험 · 시장 브리핑: 이 두 함수를 쓰지 않는다(§6-3).
  - 화면 표시: 원래 정상 보유 평가 응답의 종목 합산을 쓴다.
  - 결정 초안 미리보기(자체 종목 합산) · 원장 · 저장된 초안 · 과거 기록 · 보유 저장
- **OCI 과거 발송 여부 확인하지 않음 — 이번 수정 조건에서 제외**(판정 Q2 (b) · §4).

## 1. 처리한 요구사항

| 요구사항(판정) | 상태 | 근거 |
|---|---|---|
| §3-A 위치 짝짓기 · 길이 · source_index 확인 · 어긋나면 실패 · 대체 없음 · 새 ID 없음 | DONE | `holdings_market_evidence.py` · 시험 줄별 2 · 어긋남 2 |
| §3-C 종목 합산(평가 합 · 매입 합 · 손익률 · 비중 · 금액 합친 뒤 계산 · 평균 · 역산 없음) | DONE | `_ticker_valuations` · 시험 순서 2 · PC 사본 · 초안 |
| §3-C 일부 줄 평가 없음 → 평가 · 비중 · 손익 없음 · 매입 불가 · 0 → 손익 없음 | DONE | 시험 일부 결측 · 손익 계산 불가 2 |
| §3-C 전체 합계 결측 · coverage · need_check · 선정 · 정렬 · 최대 3개 · 동률 · 자릿수 유지 | DONE | 기존 시험 그대로 통과 · 시험 선정 순서 · 시세 없는 종목 |
| §3-C PC 사본 요약 · 수동 초안이 같은 요약 | DONE | 시험(PC 사본 · 초안 줄) · 실제 PC 응답 |
| §3-C 사실과 다른 주석 · 시험 설명 · PROGRAM_TRUTH 정정 | DONE | §2 |
| §4 OCI 정기 알림 경로 불변 검증 | DONE | §6-3 가져오기 근거 · 전체 회귀 |
| §4 과거 기록 · 저장 초안 재작성 없음 · PUSH 중단 · 시험 발송 · OCI 쓰기 없음 | DONE | 코드 변경 범위 · 실행 기록 생성 0 |
| §5 범위 밖 관찰 3건 기록만 · total_holdings_count 의미 문서화 | DONE | BACKLOG 결함 절 · PROGRAM_TRUTH API 표 |
| §6 검증 목록 | DONE | §8 |

## 2. 변경된 파일 목록

- `app/holdings_market_evidence.py`: 수정(위치 짝짓기 · 1:1 확인 · 616 → 620줄)
- `app/market_summary_composer.py`: 수정(`_ticker_valuations` 신규 함수 · 두 요약이 사용 · 279 → 339줄 · 실측)
- `app/decision_draft_preview_service.py`: 수정(설명 문장 1곳)
- `frontend/app/components/today/JudgmentQueueSection.tsx`: 수정(주석 1곳)
- `frontend/app/components/today/TopHoldingsAggregate.test.tsx`: 수정(시험 설명 4곳 · 단정 변경 없음)
- `tests/test_holdings_evidence_multirow_valuation.py`: **신규**(13)
- 문서: 판정 원문(신규) · PLAN V1(§5 반영) · 이 결과서(신규) · `docs/PROGRAM_TRUTH.md` · `docs/backlog/BACKLOG.md` · `docs/STATE_LATEST.md`

## 3. 신규 추가된 의존성

없음.

## 4. 지시문 외 변경 · 구현 판단

1. **한 줄 종목은 그 줄 값을 그대로 쓴다**
   - 기존 손익률은 반올림 전 평가금액으로 계산된다(`holdings_enrich.py:108-113`). 반면 근거 응답의 평가금액은 소수 둘째 자리로 반올림된 값이다.
   - 한 줄 종목까지 합산 공식으로 다시 계산하면, 아주 드물게 손익률 소수 둘째 자리가 갈릴 수 있다. 판정 §6 '단일 계좌 정상값 불변'을 지키려고 여러 줄 종목만 합산 계산한다.
   - 시험: 줄 값과 다른 손익률(11.12)을 그대로 두는지 확인한다.
2. **`need_check` 입력을 종목 합산 값으로 바꿨다**(판정 규칙 자체는 그대로)
   - 예전에는 같은 종목 첫 줄의 평가 · 손익으로 판정했다.
   - 화면 `computeNeedCheck` 는 종목 합산 값으로 판정하므로 같은 입력으로 맞췄다. 지금 enrich 구조에서는 시세가 종목 단위라 결과가 달라지는 실제 경우는 없다.
   - 시험: 매입 계산 불가 경우 need_check 1.
3. **builder 의 `(e.x if e else None)` 조건은 그대로 뒀다**: 이제 `e` 는 늘 있지만, 주변 구조를 바꾸지 않으려고 손대지 않았다(판정 '설명 정정 때문에 주변 기능을 재구성하지 않는다').

## 5. 알려진 한계 / 미완성

0. **PLAN Q3 서술 정정 — 설계자 판단 근거가 틀렸던 부분**(독립 검토 지적 · 코드 확인)
   - PLAN §4 Q3 은 privacy_detector 두 문제를 묶어 '진단용이고 지금 발송 경로에서는 닿지 않는다'고 적었다.
   - `_hints_by_ticker` 가 같은 종목 마지막 줄만 보는 문제: 정기 3종 경로에서 닿지 않는다(근거 payload 를 넘기지 않음). 이 부분은 맞다.
   - **쉼표가 든 숫자를 못 찾는 문제(`has_numeric_word` · `:41`)는 정기 보유 브리핑마다 도는 개인정보 검사 경로에 있다.** 경로: `runner_dispatch.py:69` → `holdings_selection_flow.py:315` `detect_privacy_on_body` → `:344` `detect_private_values_exposed` → 보유 수량 · 평단을 본문에서 찾음.
   - 지금 사용자 영향: 없음. 정기 보유 브리핑 본문은 평가금액 · 현재가 같은 금액 숫자를 넣지 않는다(`holdings_selection_render.py:7`). 그래서 쉼표 형식의 개인 숫자가 본문에 없다.
   - 앞으로 본문에 쉼표 형식 금액이 들어가면 이 검사가 놓친다.
   - BACKLOG · PLAN 서술은 고쳤다. 설계자 RESULT 판정 §3: **기록만 유지**. 보유 수량 · 평단 등 개인 숫자가 들어갈 수 있는 본문 형식을 바꾸거나 실제 미탐지 사례가 나오면 그 변경 범위에서 이 검사를 함께 재검토한다(개인값을 본문에 넣어도 된다는 허용 아님 · §11).
1. **OCI 과거 발송 여부 확인하지 않음 — 이번 수정 조건에서 제외**(판정 Q2 (b))
   - 이 PC 의 실행 기록 `state/runs` 는 156건(2026-08-12 ~ 09-21)이고 모두 `FAILED` 다. 메시지 본문이 있는 기록은 0건이다(PLAN §1-3).
   - 이것을 OCI 에서도 과거 발송이 없었다는 뜻으로 넓히지 않는다.
2. **같은 종목 안에서 일부 줄만 평가가 없는 경우는 지금 구조에서 생기지 않는다**: 시세가 종목 단위이고, 수량 · 평단은 0 보다 커야 한다. 그래서 그 경로는 요약 함수 직접 시험으로만 확인했다.
3. **범위 밖 관찰 3건은 기록만 했다**(BACKLOG 결함 절)
   - privacy_detector 가 마지막 줄만 보고 쉼표 숫자를 찾지 못함
   - `total_holdings_count` = 보유 줄 수
   - 결정 초안 미리보기 `data_quality` · `overlap` 이 늘 비어 있음
4. **KS-10 근접**: `app/holdings_market_evidence.py` 620줄(근접 600 이상 · 트리거 650 초과). 이번 증가는 4줄이다.

## 6. 다음 검증자(Codex)에게 알릴 점

1. **고치기 전 코드로 대조**: 고치기 전 두 파일(HEAD 판) + 새 시험 13건 = 10 failed · 3 passed. 통과 3건은 바뀌면 안 되는 것을 지키는 시험이다(한 줄 종목 값 · 선정 순서 · 시세 없는 종목). 고친 코드는 13 passed.
2. **변이**(저장소 밖 사본 · 복원 = 내용 쓰기 + `os.utime` · `PYTHONDONTWRITEBYTECODE=1`): 8/8 검출
   - builder 종목 키 사전으로 되돌림
   - 길이 · source_index 검사 없음
   - 요약이 첫 줄 값
   - 일부 줄 평가 없음도 부분 합
   - 매입 계산 불가도 부분 합
   - 매입 0 검사 없음
   - 한 줄 종목도 다시 계산
   - 자료 확인 판정이 첫 줄 값
3. **OCI 정기 알림 불변 근거**(코드 · grep)
   - `market_summary_composer` 를 가져오는 곳: `holdings_market_evidence.py` · `pc_price_basis.py` 둘뿐이다.
   - builder 를 가져오는 곳: `api_decision_draft_preview.py` · `api_holdings_market_evidence.py` · `draft.py` · `runtime_evidence/composer.py`
     - `runtime_evidence/holdings_composer.py` 는 같은 모듈에서 `get_holdings_file_mtime_iso` 만 가져온다(`:29`).
     - builder 는 `composer.py:122` 가 `evidence_fn` 으로 넘겨준다.
   - 정기 러너(`three_push_runtime/runner_dispatch.py`)가 가져오는 것: `holdings_risk_flow` · `holdings_selection_flow.assemble_holdings_push` · `runner_market_briefing`
   - 보유 브리핑 · 보유 위험 · 시장 브리핑은 `runner_evidence.SKIP_EVIDENCE_KINDS` 로 예전 근거 경로(composer)를 건너뛴다.
   - `select_holdings` 는 자체 종목 합산(수량 가중 평단)을 쓴다.
4. **PC 3-PUSH 패키지 내보내기**(`three_push_package_exporter.py:87`)는 시세 없이(`market_quotes=None`) 부른다. 평가 · 비중 · 손익은 예전처럼 모두 없음이다.
5. **독립 검토 반영**(코드 동작 결함 지적 0건 · 문서 4건)
   - `market_summary_composer.py` 줄 수: 330 → 실측 339 로 정정
   - `holdings_composer.py` 는 builder 를 가져오지 않고 넘겨받는다(§6-3 정정)
   - privacy_detector 쉼표 숫자 탐지 한계가 정기 보유 브리핑 검사 경로에 있음(§5-0 · BACKLOG · PLAN 정정 · 설계자에게 알림)
   - 'PC 응답과 초안이 같은 요약' → 같은 요약 함수 · 입력은 다름(§0 정정 · 초안 경로 자체 요약 시험 추가)
   - PLAN 의 파일 이름 오기와 구현 판단 1건 → 2건(PLAN §5 정정)

## 7. 사용자 확인

- 판정 §7-3: 사용자 실화면 신규 확인 · 영업일 대기 없음.
- **설계자 RESULT 판정(2026-10-15)**: PLAN Q3 의 privacy_detector 서술 정정(§5-0)을 수용했다. 쉼표 숫자 탐지 한계는 정기 보유 브리핑의 실제 개인정보 검사 경로 문제로 기록하고, 현재 노출 영향이 없는 범위에서 기록만 유지한다(§11).
- PC 반영(자동 다시 읽기)과 실제 응답 · 초안 줄 확인은 §0 에 적었다.

## 8. 검증 실측 (2026-10-15 · 최종 코드)

- backend: `black --check` · `flake8` · `py_compile` 통과(변경 · 신규 파이썬 4개)
  - `tests/test_holdings_evidence_multirow_valuation.py` 13 passed
  - 관련 묶음(요약 · builder · PC 사본 · 근거 API · 결정 미리보기 · PUSH 대시보드 일치) 84 passed(변경 전과 같은 시험)
  - 검토 반영 뒤 새 시험 파일 다시 실행: 13 passed(초안 경로 자체 요약 확인 추가 · 시험 수 그대로)
  - 전체 회귀(마지막 1회): **3549 passed**(2026-10-15 · 403.17초 · 경고 1 = 기존 httpx 사용 중단 안내 · POC5-12 종료 3536 + 새 시험 13)
- frontend(설명만 바뀜): `npx tsc --noEmit` 종료 0 · eslint 종료 0 · `TopHoldingsAggregate.test.tsx` 2 passed
- 시험의 라이브 DB 접근 0(임시 DB) · 외부 호출 0

## 9. git 상태 (2026-10-15 · 검증 요청 직전 실측)

- **검증 대상 = staged 15파일**(`git diff --cached --name-status`). 이 중 POC5-13 문서 3개(설계 V1 · PLAN 판정 · PLAN V1)는 PLAN 단계 문서다(코드 없음 · 이 결함은 POC5-13 PLAN §6 조사 · 판정 Q4 에서 나옴).
- **같은 작업 트리에 POC5-13 구현이 함께 있다**(별도 검증 요청 예정 · POC5-14 커밋 뒤 stage). stage 안 된 변경 · 새 파일은 모두 POC5-13 이다(사용자 소유 `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md` 제외).
  - staged · 작업 트리 둘 다 바뀐 파일: `docs/PROGRAM_TRUTH.md` · `docs/STATE_LATEST.md` · `docs/backlog/BACKLOG.md` · `frontend/app/components/today/JudgmentQueueSection.tsx` · POC5-13 PLAN V1 — POC5-14 판정은 staged 판(`git show :<경로>` · `git diff --cached`)으로 한다.
  - staged 판에 POC5-13 구현 흔적 0: `JudgmentQueueSection.tsx` 의 `tc-risk-strip` 0 · `PROGRAM_TRUTH.md` 의 `decline_band` 0 · `app/pc_price_basis.py` 의 `_decline_band` 0 · `tests/test_pc_decline_band.py` 없음.
- **staged 만 꺼낸 사본 실측**(`git checkout-index -a --prefix=<저장소 밖 폴더>/` · `.venv` 링크 · `PYTHONDONTWRITEBYTECODE=1`)
  - 관련 묶음(새 시험 · 요약 · PC 사본 · builder · 근거 API) 69 passed
  - 전체: 3379 passed · 164 failed · 6 skipped
  - 대조군 HEAD 사본(`git archive HEAD` · 같은 방법): 3366 passed · 164 failed · 6 skipped
  - 실패 164건 목록이 두 사본에서 같다(차이 0). 실제 DB 부재와 Git 메타데이터 부재 등 사본의 환경 차이다(검증자 2026-10-15 정정).
    - `tests/_live_guard.py` 가 기존 목록 시험에 읽기 전용 사본으로 열어 주는 실제 DB가 사본에는 없어 `unable to open database file` 및 그 결과에 따른 후속 단언 실패가 난다.
    - `tests/test_market_context_kodex200_asof.py::test_other_callers_keep_whole_table_date` 1건은 DB와 무관하다. `.git`이 없는 사본에서 `git grep` 결과가 비어 실패했다. 검증자가 Git 메타데이터를 유지한 staged 사본에서 이 시험 1건 통과를 확인했다. 따라서 실패 164건 전부를 DB 부재로 설명한 기존 문구는 정정한다.
  - 통과 수 차이 13 = 새 시험 13건이다.
- 저장소 안(실제 `state/` 있음)에서의 전체 회귀는 §8 의 3549 passed(POC5-14 만 있던 작업 트리)다.

## 10. 검증자 r1 확인 · 문서 정정 (2026-10-15)

- 판정: **VERIFIED — staged 15파일만 대상**. 기준 HEAD `dfe4edb5`; 최초 인덱스 15파일과 사본의 내용 일치를 확인했다. POC5-13의 unstaged 구현은 판정하지 않았다.
- 독립 실행: staged 관련 백엔드 69 passed · 추가 확인 7 passed(계좌 순서 6가지 · 추가 길이/위치 불일치 · 전체 시세 결측 · 수량 결측 · 원본 불변 · 빈 보유) · 위 Git 환경 시험 1 passed. 프론트 `TopHoldingsAggregate.test.tsx` 2 passed · tsc · 대상 eslint · Python black/flake8/문법 검사 통과.
- 고치기 전 두 운영 파일과 동일 신규 시험으로 `10 failed · 3 passed`를 재현했다. 전체 회귀와 변이 8종은 반복 실행하지 않았으며, 개발자 사본 전체 회귀 로그의 요약과 실패 목록 동일성을 대조했다.
- 문서만 정정: PLAN §1-3에서 미리보기의 실제 builder 호출과 별도 평가 합산을 구분했고, 본문 §9의 실패 원인 설명을 바로잡았다. 운영 코드·테스트 변경은 없다.
- 결과서 §5-0의 privacy_detector 관찰은 기존 설계자 전달 항목으로 유지한다. 신규 커밋·push·OCI 작업은 하지 않았다.

## 11. 설계자 RESULT 판정 · 종료 (2026-10-15)

- **판정: PASS — 종료 기록 진행 승인**(대상 커밋 `01e54a50`). 판정 원문은 아래에 그대로 둔다(별도 파일로 두지 않음 · 판정 §4).
- **개인정보 검사**(판정 §3): 비활성 힌트 경로(`_hints_by_ticker` · 같은 종목 마지막 줄)와 활성 검사 경로(`has_numeric_word` 쉼표 숫자)를 BACKLOG 에서 나눠 적었다. 활성 경로 한계는 기록만 유지하고, 재검토 조건은 본문 형식 변경 · 실제 미탐지 사례다(개인값 추가 허용 아님).
- **진행 순서 기록**(판정 §4): RESULT 판정 전 사용자 승인으로 커밋 · push(`01e54a50`)했고, 그 뒤 POC5-13 을 따로 stage 했다. 순서를 다시 만들거나 재검증하지 않는다.
- **PC 확인 근거**: §0(실제 PC 응답 줄별 평가 · 요약 합계 14,134,755원 · 최대 3개 비중 0.4 · 10.1 · 4.5%).
- **상태**: `IMPLEMENTED_VERIFIED_CLOSED`. STATE · PROGRAM_TRUTH · BACKLOG 의 결함을 해소로 맞췄다. 과거 초안 · 기록은 다시 쓰지 않는다. OCI 과거 발송 여부 미확인은 종료 조건에서 제외.
- 코드 추가 변경 · OCI pull · 다음 영업일 확인은 종료 조건이 아니다. 종료 기록 커밋 · push 는 사용자 승인 뒤.

### 판정 원문 (설계자 · 2026-10-15)

````text
# POC5-14 같은 종목·여러 계좌 평가값 정정 — RESULT 판정
작성일: 2026-10-15 · 독자: 개발자 · 사용자
판정: **PASS — 종료 기록 진행 승인**
대상 커밋: `01e54a50`(사용자 보고상 push 완료)

## 1. 근거와 판정 범위
- 첨부 RESULT의 §0·§4·§5·§7·§8·§9·§10 및 앞선 PLAN 판정을 대조했다.
- 설계자가 코드·PC·OCI·git을 직접 재검증한 것은 아니다. 실측과 실행 결과는 결과서의 개발자·검증자 근거를 구분해 수용한다.
- 개발자 전체 회귀 3,549 passed, 새 시험 13건, 변이 8/8과 검증자의 staged 대상 VERIFIED를 수용한다.
- 검증자의 직접 관련 시험·추가 확인과 개발자의 전체 회귀는 다른 근거이다. 전체 회귀를 검증자가 다시 실행했다고 기록하지 않는다.
- 저장소 밖 사본의 환경 실패 164건은 대조군과 목록이 같다는 확인 및 Git 메타데이터 관련 설명 정정을 수용한다.
- 행별 평가값과 요약 종목 합산을 함께 고친 A + C가 요구를 충족한다.

## 2. 구현 판단 수용
| 결과서 항목 | 판정 |
|---|---|
| §4-1 한 줄 종목은 기존 손익률을 그대로 사용 | 수용. 반올림 전후 재계산으로 기존 정상 표시가 변하는 것을 피함 |
| §4-2 need_check의 입력을 종목 합산 값으로 변경 | 수용. 판정 규칙은 유지하고 평가 단위를 종목으로 맞춤 |
| §4-3 이제 불필요한 e 존재 조건을 그대로 유지 | 수용. 이번 정정에 필요하지 않은 정리는 추가하지 않음 |

- 위치·길이·source_index 확인, 일부 결측 시 없음 처리, 금액 합산 뒤 손익 계산, PC 사본·수동 초안 반영을 수용한다.
- 실제 응답의 합계·비중 확인은 PC 반영 근거로 충분하다. 새로운 초안 저장·시험 발송·사용자 화면 확인을 추가하지 않는다.

## 3. 개인정보 검사 조사 정정
- 앞선 PLAN과 설계자 판정의 “진단용·정기 발송 경로에서 닿지 않음” 설명은 두 문제를 잘못 묶었다. 이 근거를 정정한다.
- 같은 종목 마지막 줄만 보는 `_hints_by_ticker` 문제는 보고된 정기 3종 경로에서 닿지 않는다는 구분을 유지한다.
- 쉼표 숫자 탐지 한계는 정기 보유 브리핑의 실제 개인정보 검사 경로에 있는 문제로 기록한다. 휴면 진단 경로로 적지 않는다.
- 결과서가 보고한 현재 본문에는 해당 쉼표 형식 개인값이 없어 현재 노출 영향이 없다는 범위에서 **기록만 유지**한다.
- 현재 두 단계의 종료를 막거나 개인정보 검사 수정 단계를 즉시 추가하지 않는다.
- 향후 보유 수량·평단 등 개인 숫자가 들어갈 수 있는 본문 형식을 변경하거나 실제 미탐지 사례가 나오면, 그 변경 범위에서 이 검사를 함께 재검토한다.
- 이 재검토 조건은 개인값을 본문에 추가하는 허용이 아니다. 기존 본문·개인값 정책은 그대로 적용한다.
- BACKLOG에서 활성 검사 경로의 쉼표 탐지 한계와 비활성 힌트 경로의 다중 행 한계를 구분하면 된다. 광범위한 발송 이력 조사로 확대하지 않는다.
- OCI 과거 발송 여부 미확인은 앞선 판정대로 종료 조건에서 제외한다.

## 4. 진행 순서와 종료
- RESULT 판정 전 사용자 승인으로 커밋·push한 사실과 두 단계를 분리 stage한 경위를 수용한다.
- 되돌려 커밋 순서를 다시 만들거나 같은 코드를 재검증할 필요는 없다. 실제 순서를 기록한다.
- 기존 RESULT에 본 판정과 PC 확인 근거를 붙이고, 상태를 `IMPLEMENTED_VERIFIED_CLOSED`로 바꾼다.
- STATE·PROGRAM_TRUTH·BACKLOG의 해당 결함을 종료 상태로 맞춘다. 과거 초안·기록은 다시 쓰지 않는다.
- 이 판정 전달 파일을 저장소에 별도 문서로 추가할 의무는 없다. 작업당 기존 RESULT 한 파일에 판정·종료를 이어 기록해도 된다.
- 코드 추가 변경·OCI pull·다음 영업일 확인은 종료 조건이 아니다. 종료 기록 커밋·push는 기존 사용자 승인 절차를 따른다.
````
