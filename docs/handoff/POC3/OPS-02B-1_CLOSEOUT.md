# POC3-OPS-02B-1 종료 · 다음 챕터(`02B-2`) 진입 문서

- **작성일**: 2026-09-10 · **최종 갱신**: 2026-09-11
- **상태**: `OPS-02B-1` **`CLOSED`** — 설계자 최종 Gate 확정 (2026-09-11)
- **검증**: `VERIFIED_WITH_NOTES` · 승인 커밋 **`988b0494`** (이후 코드 변경 0건)
- **다음**: **HANDOFF → `OPS-02B-2` DESIGN**

```text
step_status          = CLOSED
verification         = VERIFIED_WITH_NOTES
OUTLOOK_RELATIONSHIP = ADOPT
OPERATING_RULE       = SP500_SIGN_V1
OLS                  = RESEARCH_REFERENCE
SECTOR               = NOT_EVALUATED
INDEX_LEADERSHIP     = AVAILABLE
KOSPI_VIX_INTEGRITY  = PASS
NEXT                 = HANDOFF → OPS-02B-2 DESIGN
```

---

## 1. 지금 어디까지 왔나

PUSH 3종 중 **2종이 운영 중**이다. 남은 하나가 08:00 시장 브리핑이고, 이번
`02B-1` 은 그 **입력이 쓸 만한지 판정하는 Gate** 였다.

| 종류 | 시각 | autosend | 상태 |
|---|---|---|---|
| `holdings_briefing` | 09:15 · 12:30 · 15:40 | `true` | 운영 중 (OPS-01A) |
| `holdings_risk_alert` | 09:30~15:20 7틱 | `true` | 운영 중 (OPS-02A, 2026-09-08 활성화) |
| `market_briefing` | 08:00 | **`false`** | **`02B-2` 대기** |

---

## 2. Gate 결론 — 그대로 이어받으면 된다

```text
OUTLOOK_RELATIONSHIP = ADOPT
OPERATING_RULE       = SP500_SIGN_V1     (OLS = RESEARCH_REFERENCE)
SECTOR               = NOT_EVALUATED
INDEX_LEADERSHIP     = AVAILABLE
KOSPI_VIX_INTEGRITY  = PASS
```

**해석**

- **미국시장 → 한국 개장 갭의 방향 관계는 유효하다.** 다만 운영 규칙은
  **`sign(S&P500)` 단일 규칙**이다. OLS 는 참고용이고 쓰지 않는다.
- **섹터는 만들 수 없다.** 공식 원천에 구조화된 업종·테마 분류 필드가 없다.
  대신 **`최근 강한 기초지수`** 를 쓴다. **`상승 섹터` 라고 부르면 안 된다.**
- 표현은 **방향 압력까지만**. 개장 예상 등락률 숫자는 금지(calibration 없음).

---

## 3. `02B-2` 가 만들 것

`02B-1` 판정이 `ADOPT` + `INDEX_LEADERSHIP=AVAILABLE` 이므로 본문은 이 형태다.

```text
[시장 흐름 브리핑] 08:00

오늘 한 문장
(미국 지수 방향 → 한국 개장 압력. 숫자 예측 금지)

오늘 볼 기초지수
• ○○지수: 5일 +x.x% · 20일 +x.x% (추종 ETF n개 기준)

근거
S&P500 ±x.x% · Nasdaq ±x.x% · 반도체 ±x.x%

기준
미국 MM-DD 종가 · 국내 MM-DD 종가
```

**후보 0개인 날은 기초지수 문단 자체를 생략한다** (최근 21거래일 중 3일).

구현할 것 — 본문 렌더 · **반복 억제**(fingerprint) · 러너 배선 · 목업 · autosend.

---

## 4. 이미 만들어져 있어 재사용할 것

| 자산 | 위치 |
|---|---|
| 반복 억제 패턴 | `app/runtime_evidence/holdings_risk_state.py` (OPS-02A `worst_state`) |
| 가드 순서 계약 | 조립 → **모든 skip·fail 은 flag guard 뒤** (러너 §6-c) |
| 상태 저장 계약 | **발송 성공 뒤에만** 저장 |
| benchmark 최신성 | `app/market_benchmark_freshness.py` (이번 Step 신설) |
| Gate 재현 | `scripts/ops02b1_gate/reproduce.py` + `state/ops02b1_gate/` snapshot 7종 |

**fingerprint 안**(PLAN §9) — `f"{outlook_state}#{index_leadership_state}"`.
근거 수치는 **넣지 않는다**(매일 바뀌어 억제가 무력화된다 — OPS-02A 확정 원칙).

---

## 5. 반드시 지킬 제약

| # | 제약 |
|---|---|
| 1 | **08:00 autosend 는 `false`**. 활성화는 목업 + 사용자 확인 후 별도 |
| 2 | `etf_daily_price` 의 `open`·`close` **수정 금지** |
| 3 | 기초지수명 **문자열 해석으로 섹터를 만들지 않는다** |
| 4 | `minimum_distinct_tickers_per_index = 2` · `n=1` fallback 부활 금지 |
| 5 | join coverage **95% 미만이면 블록 전체 미산출** |
| 6 | 개장 **예상 등락률 숫자 표시 금지** |
| 7 | KS-10 — 러너는 **637줄**이다. 조립은 helper 모듈에 두고 러너는 호출만 |

---

## 6. 이월 — **필수와 BACKLOG 를 분리했다** (설계자 2026-09-11)

그대로 넘기면 `02B-2` 범위가 다시 불어난다.

### 6.1 `02B-2` **필수** 2건

| # | 항목 |
|---|---|
| 1 | **API 에만 있는 신규 ticker 감지** — CSV 순회 방식이라 API 쪽 신규 종목을 못 본다 |
| 2 | **API·CSV 불일치 감지 + `CSV_REFRESH_REQUIRED` 상태** — 매일 API 대조 → 불일치 제외 → 공식 CSV 교체 필요 기록 |

> **정적 CSV 자동 다운로드는 범위 밖이다.** API 가 주지 않는 필드를 억지로
> 자동화하지 않는다. 위 2건까지만 하면 운영 안전성은 확보된다.

### 6.2 BACKLOG · **비차단** 2건

| # | 항목 |
|---|---|
| 1 | `DEF-ETF-DAILY-PRICE-BASIS-CONSISTENCY` DB 가격계열 **본조사** |
| 2 | **분배락 민감도** 평가 (공식 분배락 날짜 확보 시) |

**`02B-2` 를 막지 않는다.**

---

## 7. 열린 결함

| 결함 | 상태 |
|---|---|
| `DEF-ETF-DAILY-PRICE-BASIS-CONSISTENCY` | `INVESTIGATION_REQUIRED` · **운영 실영향 없음**(계열 혼합 0건) |
| `DEF-KOSPI-BENCHMARK-VALUE-ASOF-INTEGRITY` | **해소** (`KOSPI_VIX_INTEGRITY = PASS`) |
| `DEF-FDR-TIMEOUT` · `DEF-COMPUTE-TOPN-ASOF-HISTORICAL` | 기존 유지 |

---

## 8. 이번 Step 에서 배운 것 (반복하지 말 것)

| # | 교훈 |
|---|---|
| 1 | **계약을 문서에만 쓰고 코드에 연결하지 않았다.** coverage 판정값을 반환하지 않아 0% 에도 통과했다. 계약을 쓰면 **그 계약이 깨지는 입력으로 테스트**를 만들 것 |
| 2 | **해시·수치를 손으로 옮겨 적었다.** 결과서 sha256 이 틀렸다. **출력에서 생성**할 것 |
| 3 | **bootstrap 에 공유 RNG 를 순서대로 소비**해 스크립트 구성이 바뀌자 CI 가 달라졌다. 통계 항목마다 **독립 seed** |
| 4 | **운영 배치에 단계를 추가하면서 기존 테스트를 격리하지 않았다.** 라이브 DB 에 실제로 썼다. 외부 조회·DB 쓰기를 붙일 때는 **conftest 에서 일괄 차단** |
| 5 | **재현 스크립트가 live DB 를 읽었다.** "읽기 전용" 이라 적어놓고 tracked JSON 도 덮었다 |

---

## 9. 다음 사람이 바로 할 일

최종 Gate 는 **확정 완료**다. 남은 순서는 이것뿐이다.

1. 설계자 `02B-2` 설계서 수신
2. **개발 PLAN 먼저** 회신 (모호점 질문 포함) — 바로 코딩 금지
3. 확정 후 구현 → 결과서 → 검증자 → 목업·사용자 확인 → 활성화

---

## 10. `02B-2` 착수 조건

| 조건 | 상태 |
|---|---|
| `OPS-02B-1` 검증 | **`VERIFIED_WITH_NOTES`** (`988b0494`) |
| 설계자 최종 Gate 확정 | **완료** (2026-09-11) |
| 이월 분리 | **완료** (§6) |
| `02B-2` 설계서 | **대기** |

08:00 autosend 는 계속 **`false`**, OCI 배포·실발송 **없음**.
