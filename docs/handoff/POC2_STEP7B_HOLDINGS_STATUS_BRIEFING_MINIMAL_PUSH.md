# POC2-Step7B 핸드오프

## 보유 종목 상태 브리핑 (PUSH 1) 최소 정리

작성일: 2026-05-12
대상: 사용자 / 설계자 / 다음 세션 진입자
선행 읽기: docs/PROJECT_ORIGIN_INTENT.md / docs/KILL_SWITCHES.md / docs/ASSUMPTIONS.md /
          docs/handoff/POC2_STEP7_SYSTEM_OUTPUT_3_PUSH_REALIGNMENT_DESIGN.md /
          docs/handoff/POC2_STEP7A_NEW_ETF_WATCH_CANDIDATE_MINIMAL_PUSH.md / 본 문서

---

## 1. Step7B 목표

기존 [판단 사유] 의 별도 두 bullet ("보유 비중 영향" + "모멘텀 점검") 을 공식 PUSH 1
**"보유 종목 상태 브리핑"** 1줄로 통합하고, 사용자가 이를 **매수/매도 의견이 아니라
상태 요약**으로 이해하게 만든다.

이번 STEP 은 매수/매도 의견 생성 단계가 **아니다**.

---

## 2. 보유 종목 상태 브리핑 정의

### 변경 전 (Step7A까지) 사용자 노출 구조

```
[판단 사유]
- 보유 비중 영향: ...
- 모멘텀 점검: ...
- 신규 ETF 관찰 후보: ...
```

### 변경 후 (Step7B 이후) 사용자 노출 구조

```
[판단 사유]
- 보유 종목 상태 브리핑: <portfolio 첫 문장> <holdings momentum 첫 문장> 이 내용은 매수/매도 의견이 아닙니다.
- 신규 ETF 관찰 후보: ...
```

### bullet 본문 통합 방식

`_holdings_status_briefing_bullet(payload)` 가 두 데이터 소스를 통합:

1. **factor_signals 의 scope="portfolio" signal 의 reason_text 첫 문장**
   - 예: "평가 계산 가능 보유분 중 KODEX 200의 비중이 가장 큽니다."
2. **momentum_result.summary.top_candidate.reason_text 첫 문장** (placeholder 정정)
   - 원본: "placeholder 기준으로 평가 가능한 보유 종목 중 {label}의 점검값이 가장
     높습니다."
   - 정정 후: "현재 보유 종목 점검 기준으로 평가 가능한 보유 종목 중 {label}의 점검값이
     가장 높습니다."

두 문장 + 중립 안내 "이 내용은 매수/매도 의견이 아닙니다." 를 공백으로 연결.

### 데이터가 일부만 있을 때

- portfolio reason 만 있음 → portfolio 문장 + 중립 안내.
- momentum top 만 있음 → momentum 문장 + 중립 안내.
- 둘 다 없음 → bullet 자체 미생성 (헤더 중복 / 빈 헤더 노출 금지 정책 유지).

---

## 3. 기존 보유 비중 영향 + 모멘텀 점검 병합 방향

### 데이터 계약 (변경 없음)

- factor_signals 5번째 키 그대로 — scope="portfolio" / "holding_row" / "universe" 모두 유지.
- momentum_result 6번째 키 그대로 — candidates / summary / top_candidate 구조 유지.
- draft_payload 키 신설 0건.
- 신규 endpoint 0건.

### 사용자 노출 message_text / UI 만 통합

- `app/draft_message.py:_render_judgment_lines` 가 _factor_bullet + _momentum_bullet 두
  호출을 제거하고 `_holdings_status_briefing_bullet` 1개 호출로 대체.
- `app/message_holdings_briefing.py` 신규 — 통합 bullet 빌더 단독 책임 (draft_message.py
  KS-10 trigger 해소 목적의 분리).
- `frontend/app/components/JudgmentReasonSection.tsx` 의 picker 도 동일하게 통합 —
  `pickHoldingsStatusBriefing(payload)` 1개로 대체.

`_factor_bullet` / `_momentum_bullet` 함수는 **삭제하지 않고** draft_message.py 안에
남는다. 다른 코드가 import 할 수 있는 라벨 상수 (MOMENTUM_BULLET_LABEL 등) 와의
호환성 보호를 위함. 그러나 `_render_judgment_lines` 에서는 더 이상 호출하지 않는다.

---

## 4. placeholder 사용자 노출 제거

### 정정 위치

| 위치 | Before | After |
|---|---|---|
| `app/momentum/holdings_mode.py` PLACEHOLDER_SCORE_BASIS_TEXT | "placeholder: 현재 평가수익률 기준" | "현재 보유 종목 점검 기준 (평가수익률)" |
| `app/momentum/holdings_mode.py` CANDIDATE_REASON_AVAILABLE | "현재 평가수익률 기준 placeholder 점검값이 계산되었습니다. ..." | "현재 평가수익률 기준 보유 종목 점검값이 계산되었습니다. ..." |
| `app/momentum/holdings_mode.py` summary_reason_text | "placeholder 기준으로 ..." | "현재 보유 종목 점검 기준으로 ..." |
| `app/momentum/holdings_mode.py` top_candidate.reason_text | "placeholder 기준으로 ..." | "현재 보유 종목 점검 기준으로 ..." |
| `app/message_holdings_briefing.py` runtime 치환 | (input "placeholder 기준으로") | "현재 보유 종목 점검 기준으로" 치환 |
| `frontend/app/components/JudgmentReasonSection.tsx` runtime 치환 | 동일 | 동일 |

### 유지 (변경 안 함)

- 내부 식별자 `ENGINE_ID = "momentum_engine_placeholder_v1"` 유지 (데이터 계약).
- 상수 키명 `PLACEHOLDER_SCORE_BASIS_TEXT` 유지 (코드 식별자).
- 테스트명 / 파일명 / 함수명 안의 "placeholder" 유지 (사용자 노출 아님).

### "최종 투자 판단 산식이 아닙니다" 문구는 유지

본 문구는 placeholder 의 의미 (= 최종 산식 아님) 를 사용자 친화적으로 전달하므로 유지.

---

## 5. 매수/매도 의견 아님 원칙

### 본 STEP 의 핵심 원칙

- 시스템은 매수/매도 결정을 내리지 않는다.
- PUSH 1 은 보유 종목 **상태 정보** 만 제공.
- 최종 매매 결정은 사용자가 한다.
- AI 투자세션은 해석 보조 채널이지 결정자가 아니다.

### message_text 에서 차단할 표현 (테스트로 검증)

다음 표현은 message_text 어디에도 등장하지 않는다:
- "매수 추천" / "매도 추천"
- "매수 권유" / "매도 권유"
- "BUY" / "SELL"
- "리밸런싱"
- "비중 조정 권유"

### message_text 에 항상 포함되는 중립 안내

브리핑 bullet 끝에 항상 다음 1문장 부착:

> "이 내용은 매수/매도 의견이 아닙니다."

(브리핑 데이터가 일부만 있어도 중립 안내는 항상 부착.)

---

## 6. 완료 기준 AC

| AC | 내용 |
|---|---|
| AC-1 | Telegram/message_text 에 "보유 종목 상태 브리핑" 명칭이 반영된다. |
| AC-2 | 기존 보유 비중 영향과 holdings momentum 점검이 PUSH 1 의 하위 재료로 통합된다. |
| AC-3 | 사용자 노출 문구에서 "placeholder" 표현이 제거된다. |
| AC-4 | message_text 에 매수/매도 의견으로 읽히는 표현이 없다. |
| AC-5 | "매수/매도 의견이 아닙니다" 중립 문구가 포함된다. |
| AC-6 | PUSH 2 "신규 ETF 관찰 후보" 문구와 기존 Step7A 흐름이 유지된다. |
| AC-7 | 기존 holdings 승인 / OCI / Telegram 경로가 깨지지 않는다. |

### 본 라운드 검증 결과 (보고 직전 실측)

- pytest 147 → **159 passed** (Step7B 회귀 12개 추가) ✓
- black --check / flake8 / TypeScript build / Next.js lint 모두 PASS ✓
- KS-10 임계: 백엔드 max draft_message.py **586** / 프론트 max EnrichedHoldingsSection.tsx
  **515** / 테스트 max test_holdings_message_text.py **924** — 트리거 0 + 근접 0 ✓
- 750라인 이상 파일: 1건 (test_holdings_message_text.py 924 — 본 STEP 변경 없음).

### 본 라운드 부수 작업

draft_message.py 가 Step7B 통합 빌더 추가로 673라인 → KS-10 trigger 4 (백엔드 핵심 모듈
>650) 발동. 즉시 `app/message_holdings_briefing.py` 로 빌더 분리하여 draft_message.py
586라인 (trigger 미달 + 근접 미달) 으로 복귀.

---

## 7. BACKLOG 후보

### BACKLOG: 무릎/머리/어깨 정량 기준
- 보류 사유: 상태 브리핑을 더 정교하게 만들려면 필요하지만 아직 검증되지 않았다.
- 보류된 위험: 임의 기준을 쓰면 매매 의견처럼 보이는 신호가 생성될 수 있다.
- 복귀 조건: 보유 상태 브리핑을 2회 이상 운영한 뒤, 사용자가 "그래서 현재 위치가 좋은지
  나쁜지 모르겠다" 고 느끼는 경우.

### BACKLOG: 보유 종목 상태 브리핑 상세 UI
- 보류 사유: Step7B 는 Telegram/message_text 최소 정리 단계다.
- 보류된 위험: Telegram 요약만으로는 상세 이유를 보기 어려울 수 있다.
- 복귀 조건: 사용자가 특정 보유 종목의 상태 근거를 더 보고 싶다고 명시할 때.

### BACKLOG: 보유 점검 산식 개선
- 보류 사유: 현재 holdings momentum 은 placeholder 성격의 점검값이다.
- 보류된 위험: 점검값이 실제 투자 판단 품질을 충분히 설명하지 못할 수 있다.
- 복귀 조건: 보유 상태 브리핑 운영 후 점검값이 사용자 판단에 도움이 되지 않는다고
  확인될 때.

---

## 8. 다음 단계

본 Step7B 완료 후 다음 후보 (Step7 §13 한 번에 하나의 PUSH 원칙):

- **PUSH 3 급락 ETF 주의 신호 최소 구현 Step** — 자리만 잡은 상태에서 최소 구현 진입.
- **운영 빈도 문서 정합성 보정** (PROJECT_ORIGIN_INTENT §7 "1일 3회" vs Step7 §7
  "K6/EOD 저빈도" 통합).
- BACKLOG 잔존 후속 항목 (seed 편집 UI / 자동 universe 수집 / 무릎머리어깨 등).

사용자가 협의 후 명시 지시 — 본 핸드오프에서는 후속 STEP 을 선결정하지 않는다.

---

문서 끝.
