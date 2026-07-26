# POC2 Step 2B 종결 — Telegram Message Compaction

작성일: 2026-04-28
작성자: 개발자(VSCode Claude)
상태: 구현 + 자동 검증 게이트 통과 (black/flake8/pytest 63 passed). 사용자 디바이스 18+ 종목 실 Telegram 발송은 다음 사용자 실행 시점 자연 검증.
대상 독자: 다음 챕터(POC2-Step2C 또는 운영 안정화) 진입자

---

## 1. 단계 목적 (한 줄)

보유 종목 18+ 에서 Telegram message_text 가 길어져 발송이 실패하던 문제를 해결한다. 메시지를 "전체 보유 상세 보고서" 가 아니라 "승인 결과 + 전체 요약 + 주목 종목 일부" 로 전환한다. 18+ 보유 종목에서도 message_text 가 안전 한도(3500자) 이하로 생성되어 발송 실패가 발생하지 않게 한다.

---

## 2. 사용자(설계자) 결정 사항 반영

| Q | 결정 | 적용 위치 |
|---|---|---|
| 메시지 형식 | "전체 상세 보고서" 아님 → "승인 결과 + 요약 + 주목 종목 일부" | `app/draft_message.py::build_message_text` |
| 길이 한도 | 3500 자 (`MAX_LENGTH_CHARS`) | `app/draft_message.py` 모듈 상수 |
| 메시지 분할 | 도입 안 함. compaction 만 사용 | `_enforce_length_limit` |
| Top N 정책 | 코드 상수 (price_missing/calc_missing/bottom_pnl_rate/top_market_weight/top_pnl_rate 각 3건) | `TOP_N_*` 상수 |
| 기본 HOLD 처리 | 요약 카운트에는 포함, 상세 목록 전부 나열 금지 | `_is_default_hold` + `select_focus_items` |
| 정렬 안전성 | 누락/None/NaN/비숫자 정렬 대상 제외 | `_to_finite_float` 단일 진입점 |
| 시세 확인 vs 평가 계산 가능 분리 | `_is_priced` ≠ `_is_calc_available`. 평가 집계는 `_is_calc_available` 만 사용 | `compute_summary` |
| snapshot/history/전일 대비 | 도입 안 함 | 코드 작성 안 함 |
| UI 압축 / 계좌 구분 | 이번 단계 외 — POC2-Step2C 로 deferred | BACKLOG |

---

## 3. 책임 분리 (Step 2B 핵심)

```
[로컬 FastAPI]
  └─ delivery.deliver()
     └─ draft_message.build_message_text(run_id, payload)
         ├─ compute_summary(recs)   ← 시세 확인 / 평가 계산 가능 / 미확인 분리
         ├─ select_focus_items(recs) ← 5개 카테고리 + 중복 제거
         ├─ _build_with_focus_limit() ← 헤더+요약+주목+안내 조립
         └─ 길이 단계 축소 (전체 → 절반 → 0) → _enforce_length_limit
            └─ Telegram 안전 한도 내 message_text 보장

[OCI consumer]
  └─ message_text 그대로 발송 (POC2 Step 1A 책임 분리 유지)
```

핵심 규칙:
- 메시지 텍스트 생성 책임 = 여전히 로컬 백엔드. OCI 는 발송만
- draft_payload 구조 / handoff artifact 5필드 / 5 state 모델 그대로 유지
- 외부 fetch / Naver 호출 / 캐시 정책은 변경 없음 (Step 2 그대로)

---

## 4. 메시지 구성 정책 (Step 2B)

```
1. 헤더
   - ✅ POC2 holdings 승인 처리
   - run_id
   - title

2. 전체 요약
   - 보유 종목 수
   - 시세 확인 / 미확인 카운트
   - 평가 계산 가능 / 계산 정보 부족 카운트 (계산 정보 부족이 1+ 일 때만)
   - 총 매입금액 (모든 종목 합계)
   - 평가금액/평가손익/평가수익률 (평가 계산 가능 종목 기준)
   - ⚠ 시세 미확인/계산 정보 부족 경고 (1+ 종목 있을 때)

3. 주목 종목 (카테고리별)
   - 🔍 시세 미확인 종목
   - ⚙ 계산 정보 부족 종목  (Step 2B FIX 라운드 추가)
   - 📉 평가수익률 하위
   - 📊 시장비중 상위
   - 📈 평가수익률 상위

4. 안내 문구
   - 전체 보유 상세는 웹 화면에서 확인하세요.
```

---

## 5. "시세 확인" vs "평가 계산 가능" 분리 (Step 2B FIX 라운드)

| 분류 | 조건 | 카운트/집계 영향 |
|---|---|---|
| **시세 미확인** | `current_price` 키 없음 / None / NaN / ≤0 | unpriced_count 에 포함, 평가 집계 제외, 🔍 그룹에 표시 |
| **시세 확인** (priced) | `current_price` 키 + 유효 양수 | priced_count 에 포함 |
| **평가 계산 가능** (priced + calc_available) | priced AND `eval_amount` + `invested_amount` 모두 유효 양수 | calc_available_count 에 포함, 평가금액/손익/수익률 집계에 사용 |
| **계산 정보 부족** (priced 이지만 calc 불가) | priced AND (eval_amount 누락 또는 invested_amount 누락) | calc_missing_count 에 포함, 평가 집계 제외, ⚙ 그룹에 표시 |

핵심: 평가 집계는 **계산 가능 종목만** 사용. 계산 정보 부족 종목을 0 원으로 취급하지 않는다.

---

## 6. 종목별 표시 필드 (Step 2B)

기본 표시 (주목 종목 카드):
- 종목명 또는 종목코드
- 평가수익률
- 평가손익 (옵션)
- 시장비중 (옵션)
- [시세 미확인] / [계산 정보 부족] 마커 (해당 시)
- 판단 (action)
- 사유 (reason)

**메시지에서 제외** (UI 에서 확인):
- 수량
- 평균 매입단가
- 매입금액
- 매입비중
- 현재가
- 평가금액 (종목별)

---

## 7. 길이 제한 방어 흐름

```
1. 전체 주목 종목 + 요약으로 1차 조립
   ├─ 한도 이하 → 그대로 반환
   └─ 한도 초과
2. 주목 종목 절반으로 축소
   ├─ 한도 이하 → 반환
   └─ 한도 초과
3. 주목 종목 0건 (요약만)
   ├─ 한도 이하 → 반환
   └─ 한도 초과
4. 강제 잘라냄 + 잘림 안내 문구 (TRUNCATION_NOTICE)
   └─ 잘림 후 한도 이하 보장
```

`message split` 사용 안 함 (이번 단계 정책).

---

## 8. 변경 / 신규 파일

수정:
- `app/draft_message.py` — 요약형 + 주목 선별 + 길이 방어 + `_is_priced`/`_is_calc_available` 분리
- `tests/test_poc1_loop.py` — 기존 Step 1A 테스트 3건 재조정 + Step 2B 신규 14건 추가 (총 63 passed)
- `docs/backlog/BACKLOG.md` — Step 2B deferred 12건 + Step2C 별도 STEP 등록

신규 (사용자 작성 — 본 챕터에 포함):
- `docs/agent/INSTRUCTION_RULES.md` — 설계자 역할 / 필수 선행 읽기 / 지시문 작성 규칙
- `docs/handoff/STATE_LATEST.md` — 프로젝트 현재 상태 스냅샷

---

## 9. 검증 게이트 통과 기록

```
.venv/Scripts/black.exe --check app/ tests/   → exit 0 (16 files)
.venv/Scripts/flake8.exe  app/ tests/         → exit 0
.venv/Scripts/python.exe -m pytest tests/ -q  → 63 passed
```

테스트 추가 항목:
- `test_draft_message_step2b_summary_form_no_per_item_buy_fields`
- `test_draft_message_step2b_default_hold_not_in_focus`
- `test_draft_message_step2b_large_holdings_under_length_limit`
- `test_draft_message_step2b_omits_quantity_avg_price_lines`
- `test_draft_message_step2b_pnl_rate_and_action_reason_included`
- `test_draft_message_step2b_sorting_excludes_missing_pnl_rate`
- `test_draft_message_step2b_sorting_handles_nan_and_string_values`
- `test_draft_message_step2b_price_missing_not_treated_as_zero`
- `test_draft_message_step2b_summary_priced_basis_label`
- `test_draft_message_step2b_truncation_notice_when_over_limit`
- `test_draft_message_step2b_compute_summary_unit`
- `test_draft_message_step2b_calc_missing_not_treated_as_zero` (Codex FIX)
- `test_draft_message_step2b_compute_summary_separates_calc_missing` (Codex FIX)
- `test_draft_message_step2b_returns_empty_for_non_holdings`

---

## 10. 알려진 한계 / 미완성

- **운영 E2E 미검증** — 18+ 종목 실 Telegram 수신은 다음 사용자 실행 시점 자연 검증
- **UI 카드 길이는 그대로** — POC2-Step2C 로 이연
- **계좌 구분 없음** — POC2-Step2C 로 이연
- **Top N 값 코드 상수** — 환경변수/UI 노출 안 함 (BACKLOG)
- **메시지 split 미도입** — compaction + 잘림 안내만 (BACKLOG)
- **snapshot/history 미도입** — 전일 대비 변화 감지 없음 (BACKLOG)
- **ML/factor 추천 미도입** (Phase 1 격리 유지)

---

## 11. 다음 챕터 진입자에게

### 건드리지 말아야 할 것 (Step 2B 까지 확정 계약)

- 5 state 모델 / 4필드 draft_payload / handoff 5필드
- holdings 식별 규약 (recommendations 첫 항목에 quantity 또는 avg_buy_price)
- 외부 fetch 는 `POST /market/refresh` 단 1곳에서만
- draft_payload 메타 flag(`price_missing/calc_missing`) 절대 추가 금지 (Step 2 정책 유지)
- `_is_priced` ≠ `_is_calc_available` 분리 — 평가 집계는 `_is_calc_available` 만 사용
- action 은 'HOLD' 고정, score 도입 금지
- Telegram 메시지에 종목별 매입 상세 (수량/평균매입단가/매입금액/매입비중/현재가/평가금액) 추가 금지 — UI 에서 확인
- 메시지 split / snapshot / history / 전일 대비 변화 감지 도입 금지
- "실시간" 단어 사용 금지

### 즉시 진행 가능한 후보

- **(A) 운영 E2E 자연 검증** — 사용자 디바이스에서 18+ 종목 실 Telegram 수신 형식 확인
- **(B) POC2-Step2C — Holdings UI 압축** (BACKLOG 트리거 충족 시)
- **(C) POC2-Step2C — 계좌 구분 추가** (BACKLOG 트리거 충족 시)
- **(D) ML 연결 / factor 추천 고도화** (Phase 1 격리 모듈 활용 — BACKLOG)

---

## 12. 한 줄 당부

POC2 Step 2B 의 핵심 — **Telegram 은 요약 채널이고 UI 가 상세 채널이다** — 를 깨지 말고 위에 쌓아라. 길이 방어는 발송 전 단계에서 보장하는 것이며 Telegram 응답으로 FAILED 처리하는 후행 회복이 아니다. 평가 집계는 항상 "평가 계산 가능 종목 기준" 만 사용하라 — 누락 데이터를 0 원으로 취급하지 않는 것이 사용자 신뢰의 출발점이다.
