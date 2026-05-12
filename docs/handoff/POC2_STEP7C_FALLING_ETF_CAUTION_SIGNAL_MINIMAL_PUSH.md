# POC2-Step7C 핸드오프

## 급락 ETF 주의 신호 (PUSH 3) 최소 구현

작성일: 2026-05-12
대상: 사용자 / 설계자 / 다음 세션 진입자
선행 읽기: docs/PROJECT_ORIGIN_INTENT.md / docs/KILL_SWITCHES.md / docs/ASSUMPTIONS.md /
          docs/handoff/POC2_STEP7_SYSTEM_OUTPUT_3_PUSH_REALIGNMENT_DESIGN.md /
          docs/handoff/POC2_STEP7A_NEW_ETF_WATCH_CANDIDATE_MINIMAL_PUSH.md /
          docs/handoff/POC2_STEP7B_HOLDINGS_STATUS_BRIEFING_MINIMAL_PUSH.md / 본 문서

---

## 1. Step7C 목표

기존 universe momentum 계산 결과 (pykrx 1개월 수익률) 를 **재사용**하여, 1개월 수익률이
초기 급락 기준 이하인 ETF가 있을 때만 공식 PUSH 3 "**급락 ETF 주의 신호**" 를
message_text / Telegram 에 1줄 추가한다.

본 STEP 은 **매도 신호 / 매수 금지 / 손절 기준 / 리밸런싱 제안을 만드는 단계가 아니다.**

---

## 2. 급락 ETF 주의 신호 정의

### 사용자 노출 공식 명칭

**급락 ETF 주의 신호**

### 금지 명칭 (사용자 노출 0건)

- 매도 신호
- 매수 금지
- 손절 신호
- 위험 ETF
- 급락 매매 판단
- 버려야 할 ETF
- BUY / SELL / 리밸런싱

### 신호 있음 시 [판단 사유] 구조

```
[판단 사유]
- 보유 종목 상태 브리핑: ...
- 신규 ETF 관찰 후보: ...
- 급락 ETF 주의 신호: pykrx 1개월 수익률 기준 {name}이 {score_value}%로 초기 급락 기준(-10.0%) 이하입니다(기준일 {basis_date}). 이 값은 매수/매도 지시가 아닙니다.
```

### 신호 없음 시 [판단 사유] 구조

```
[판단 사유]
- 보유 종목 상태 브리핑: ...
- 신규 ETF 관찰 후보: ...
```

**"급락 신호 없음" 같은 문구를 Telegram에 추가하지 않는다** (KS-5 알림 과다 방지).

---

## 3. 초기 급락 기준 -10.0% 는 확정값이 아님

`app/universe_refresh.py:FALLING_THRESHOLD_PCT = -10.0` — **확정 투자 기준이 아니라
초기 운영값**.

코드 주석 (`app/universe_refresh.py` 상수 정의 부근) 에 "확정값 아님 / 운영 검증 필요"
명시. BACKLOG "급락 임계값 검증" 항목에 복귀 조건 명시.

새 가격 데이터 소스 추가 없음 — Step6 의 pykrx 1개월 수익률 그대로 재사용.
pykrx 호출 코드는 `app/price_history_pykrx.py` 단일 모듈 정책 유지.

---

## 4. 급락 후보 tie-breaker (결정론적 선택)

기존 universe candidates 중 `score_result.is_scored=True` + `score_value <= -10.0`
후보만 대상. 동률 시 다음 우선순위:

1. **score_value 오름차순** (= 더 큰 하락 우선)
2. **ticker 오름차순**
3. **candidate_id 오름차순**

예시:

| score_value | ticker | 선택 사유 |
|---|---|---|
| -18.1% | C ETF | 가장 큰 하락 |
| -12.5% | B ETF | |
| -8.2% | A ETF | 기준 미달 (-10.0% 초과) |

→ 선택: **C ETF**

동률 예시:

| score_value | ticker | 선택 사유 |
|---|---|---|
| -12.5% | 069500 | ticker 오름차순 우선 |
| -12.5% | 379800 | |

→ 선택: **069500**

**Telegram / message_text 에는 1개만 노출** (Top N 정책 금지).

---

## 5. 데이터 계약 / 데이터 흐름

### 데이터 계약 변경 (확장만)

| 위치 | 필드 | 의미 |
|---|---|---|
| `universe_momentum_latest.json` summary | `falling_threshold_pct: float = -10.0` | 초기 기준값 (확정값 아님) |
| `universe_momentum_latest.json` summary | `falling_candidate: dict \| None` | tie-breaker 적용 1건 (또는 None) |
| `draft_payload.factor_signals` | scope=`"universe_falling"` signal entry | Step7A universe scope 와 동일 패턴 (draft_payload 키 신설 없음) |
| `POST /universe/momentum/refresh` 응답 | `summary.falling_candidate` / `summary.falling_threshold_pct` | UI 가 상태 패널 표시용 |

신규 draft_payload top-level 키 / 신규 endpoint / 신규 API 모두 **0건**.

### 데이터 흐름

```
POST /universe/momentum/refresh
  → ensure_seed_file_exists (Step7A)
  → load_universe_seed
  → run_universe_refresh  (Step6: pykrx 1개월 수익률 계산)
  → build_universe_momentum_result_scored(..., falling_threshold_pct=-10.0)
    · top_candidate (rank=1)
    · falling_candidate (score_value <= -10.0, tie-breaker 적용)
  → save_latest_artifact

GenerateDraft (POST /runs/generate-from-holdings)
  → _build_holdings_payload
    · _build_universe_factor_signal (Step6 — scope="universe" signal)
    · _build_falling_etf_factor_signal (Step7C — scope="universe_falling" signal, 후보 있을 때만)
  → build_message_text
    · _render_judgment_lines
      · _holdings_status_briefing_bullet (Step7B)
      · _external_universe_bullet
      · _falling_etf_caution_bullet (Step7C, signal 있을 때만)
```

**GenerateDraft 가 pykrx 직접 호출 0건** — universe_momentum_latest.json 만 읽음 (AC-20).

---

## 6. 매수/매도 지시 아님 원칙

본 PUSH 도 시스템 출력의 핵심 원칙을 따른다 (Step7 §3):

- 시스템은 매수/매도 결정을 내리지 않는다.
- 시스템은 판단 재료와 관찰 후보를 제공한다.
- 최종 매매 결정은 사용자가 한다.
- PUSH 3 은 매도 지시나 매수 금지 명령이 아니다.

bullet 본문 끝에 항상 **"이 값은 매수/매도 지시가 아닙니다"** 부착.

---

## 7. UI 최소 반영

UniverseRefreshPanel 안에 급락 신호 상태 표시:

- **신호 있음**: ⚠ 경고 안내 1줄 (종목 / 수익률 / 기준 / "매수/매도 지시 아님" 표기)
- **신호 없음**: "급락 주의 신호 없음 (초기 급락 기준 -10.0%)" 짧은 안내

별도 페이지 / 차트 / Top N 표 / 위험 등급 색상 체계 / 매도 버튼 모두 미도입.

---

## 8. 완료 기준 AC

| AC | 내용 |
|---|---|
| AC-1 | "급락 ETF 주의 신호" 공식 명칭이 message_text / UI 에 반영된다. |
| AC-2 | 기존 pykrx 1개월 수익률을 재사용하고 tie-breaker (score ASC → ticker ASC → candidate_id ASC) 결정론적 1개 선택. |
| AC-3 | 초기 급락 기준 -10.0% 는 "확정값 아님 / 운영 검증 필요" 로 코드 주석 + 문서에 표시. |
| AC-4 | 급락 기준을 만족하는 후보가 있을 때만 message_text 에 1줄 추가. |
| AC-5 | 후보 없으면 Telegram/message_text 에 "신호 없음" 문구 미추가. |
| AC-6 | "매수/매도 지시가 아닙니다" 중립 문구 포함. |
| AC-7 | 기존 PUSH 1 / PUSH 2 / holdings 승인 / OCI / Telegram 경로 보존. |

### 본 라운드 검증 결과 (보고 직전 실측)

- pytest 159 → **173 passed** (Step7C 회귀 14개 추가). ✓
- black --check / flake8 / TypeScript build / Next.js lint 모두 PASS. ✓
- KS-10 임계: 백엔드 max `draft_message.py` **564** / 프론트 max `EnrichedHoldingsSection.tsx`
  **515** / 테스트 max `test_holdings_message_text.py` **924** — **트리거 0 + 근접 0** ✓.

### 본 라운드 부수 작업 (KS-10 가드 대응)

draft_message.py 가 _falling_etf_caution_bullet 추가로 623라인 (near ≥600 위반) →
- 본 라운드 안에서 `app/message_falling_etf_bullet.py` 로 picker 함수 이전.
- 미사용 `_factor_bullet` / `_momentum_bullet` 함수 제거 (Step7B 통합 이후 외부 호출 0).
- 결과: draft_message.py **564라인** (near 미달 + trigger 미달) 으로 복귀.

---

## 9. BACKLOG 후보

### BACKLOG: 급락 임계값 검증
- 보류 사유: -10.0% 는 초기 운영값이며 백테스트로 검증되지 않았다.
- 보류된 위험: 너무 민감하면 알림 과다 (KS-5), 너무 둔하면 급락 신호가 늦게 나온다.
- 복귀 조건: 급락 ETF 주의 신호가 2회 이상 발생하거나, 급락 후보가 전혀 나오지 않아
  기준 조정 필요성이 생길 때.

### BACKLOG: 급락 기준 기간 비교
- 보류 사유: Step7C 는 1개월 수익률을 재사용한다.
- 보류된 위험: 급락은 1개월보다 짧은 기간에서 더 잘 포착될 수 있다.
- 복귀 조건: 사용자가 "이미 많이 빠진 뒤에야 신호가 나온다" 고 느끼는 경우.

### BACKLOG: 급락 신호 UI 고도화
- 보류 사유: Step7C 는 message_text 최소 신호 단계다.
- 보류된 위험: Telegram 만으로는 급락 근거를 충분히 보기 어려울 수 있다.
- 복귀 조건: 사용자가 급락 후보의 가격 흐름을 UI 에서 더 보고 싶다고 명시할 때.

---

## 10. 다음 단계

Step7C 완료 후 **3-PUSH 모두 최소 구현 단계**. 다음 후보:

- **운영 빈도 문서 정합성 보정** (PROJECT_ORIGIN_INTENT §7 "1일 3회" vs Step7 §7
  "K6/EOD 저빈도" 통합 — Step7 BACKLOG §9.7).
- **운영 사이클 1회 시작 → Q5 첫 실전 데이터 수집** (ASSUMPTIONS Q5 BACKLOG 복귀 트리거).
- BACKLOG 잔존 후속 항목 (무릎/머리/어깨 / 급락 임계값 검증 / 보유 점검 산식 개선 등).

사용자 협의 후 명시 지시 — 본 핸드오프에서는 후속 STEP 을 선결정하지 않는다.

---

문서 끝.
