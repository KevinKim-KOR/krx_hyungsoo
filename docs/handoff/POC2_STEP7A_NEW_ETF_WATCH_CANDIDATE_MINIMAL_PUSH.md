# POC2-Step7A 핸드오프

## 신규 ETF 관찰 후보 (PUSH 2) 최소 운영화

작성일: 2026-05-11
대상: 사용자 / 설계자 / 다음 세션 진입자
선행 읽기: docs/PROJECT_ORIGIN_INTENT.md / docs/KILL_SWITCHES.md / docs/ASSUMPTIONS.md /
          docs/handoff/POC2_STEP7_SYSTEM_OUTPUT_3_PUSH_REALIGNMENT_DESIGN.md / 본 문서

---

## 1. Step7A 목표

Step6 의 외부 후보 점검 배관을 공식 PUSH 2 인 **신규 ETF 관찰 후보** 로 정리하고,
seed 파일 부재로 사용자가 막히지 않도록 최소 starter seed 장치를 추가한다.

이전 STEP (Step6) 까지의 상태:
- pykrx 1개월 수익률 계산 + top_candidate + Telegram 도달 검증 완료.
- 그러나 사용자 노출 명칭이 "외부 후보 점검" 으로 남아 있어 Step7 공식 명칭과 불일치.
- seed 파일이 없으면 사용자가 JSON 을 직접 작성해야 했고, 실 운영 테스트 중 이 지점에서
  진입 장벽이 발생.

본 Step7A 는 이 두 문제만 해소한다 — 새 기능은 도입하지 않는다.

---

## 2. "외부 후보 점검" → "신규 ETF 관찰 후보" 명칭 정렬

### 변경 범위 (사용자 노출 문구 한정)

| 영역 | Before | After |
|---|---|---|
| backend `EXTERNAL_UNIVERSE_BULLET_LABEL` 상수 | "외부 후보 점검" | "신규 ETF 관찰 후보" |
| backend `factor_signals` 의 `factor_name` (scope=universe) | "외부 후보 점검" | "신규 ETF 관찰 후보" |
| frontend `JudgmentReasonSection` default factor_name | "외부 후보 점검" | "신규 ETF 관찰 후보" |
| frontend `UniverseRefreshPanel` 헤더 | "외부 후보 점검 (universe momentum)" | "신규 ETF 관찰 후보 (PUSH 2)" |
| frontend refresh 버튼 텍스트 | "외부 후보 점검 갱신" | "신규 ETF 관찰 후보 갱신" |
| frontend 안내 / 상태 노트 | "외부 후보 점검 결과가 ..." | "신규 ETF 관찰 후보 ..." |
| Telegram message_text bullet | "- 외부 후보 점검: ..." | "- 신규 ETF 관찰 후보: ..." |
| 테스트 기대 문자열 | "외부 후보 점검" | "신규 ETF 관찰 후보" |

### 유지 (변경 안 함)

- 내부 함수명: `_external_universe_bullet` / `_build_universe_factor_signal` 등 유지.
- 파일명: `app/message_universe_bullet.py` 유지.
- factor_id: `universe_one_month_return` 유지.
- factor_signals scope 값: `"universe"` 유지.
- 데이터 계약 (universe_momentum_latest.json 구조, draft_payload 키 집합) 유지.

### 메시지 문구 (Step6 그대로 + 라벨 정렬)

성공/부분 성공:
> "- 신규 ETF 관찰 후보: pykrx 1개월 수익률 기준 {name}이 가장 높습니다({score_value}%,
> 기준일 {basis_date}, 계산 가능 {scored}/{total}개). 이 값은 매수 추천이 아닙니다."

실패:
> "- 신규 ETF 관찰 후보: pykrx 가격 데이터 부족으로 1개월 점검값을 계산하지
> 못했습니다(기준일 {basis_date})."

기준일 우선순위 (Step6 동일):
1. top_candidate.price_history_basis.latest_date
2. universe_momentum_latest.json.asof
3. "기준일 확인 불가"

---

## 3. starter seed 정책

### 동작

- `POST /universe/momentum/refresh` 호출 시:
  - seed 파일 (`state/universe/etf_universe_latest.json`) 이 **없으면** starter seed
    를 생성한 후 기존 refresh 흐름을 그대로 진행.
  - seed 파일이 **있으면** starter seed 가 **절대 덮어쓰지 않는다** — 기존 사용자
    파일을 그대로 사용.
- starter seed 의 source 는 `"starter_seed"`. API 응답의 `summary.source` 필드에
  노출되어 UI 가 "기본 후보군 사용" 안내를 표시할 수 있다.

### 기본 후보 3개

```json
{
  "asof": "<생성 시점 KST YYYY-MM-DD>",
  "source": "starter_seed",
  "items": [
    {
      "ticker": "069500",
      "name": "KODEX 200",
      "universe_group": "국내지수",
      "sector_or_theme": "KOSPI200"
    },
    {
      "ticker": "379800",
      "name": "KODEX 미국S&P500",
      "universe_group": "미국지수",
      "sector_or_theme": "S&P500"
    },
    {
      "ticker": "379810",
      "name": "KODEX 미국나스닥100",
      "universe_group": "미국지수",
      "sector_or_theme": "NASDAQ100"
    }
  ]
}
```

### 구현 위치

- `app/universe_seed.py` 에 `STARTER_SEED_ITEMS` 상수 + `ensure_seed_file_exists()`
  함수 추가.
- `app/api_universe.py` 의 POST 핸들러가 `load_universe_seed()` 호출 직전에
  `ensure_seed_file_exists()` 를 호출.
- 새 endpoint 미도입. 새 데이터 계약 미도입.

---

## 4. starter seed 는 투자전략 확정값이 아니다

본 라운드에서 명시하는 정책:

- starter seed 는 **신규 ETF 관찰 후보 기능 작동 확인용 기본 후보군** 이다.
- starter seed 는 **투자전략 확정값이 아니다**.
- 사용자는 운영 사이클을 거치면서 후보군을 자유롭게 수정한다 (수정 UX 는 BACKLOG).
- 시스템은 starter seed 의 종목 선택을 매수 추천으로 해석하지 않는다.
- UI 의 starter seed 안내 문구는 위 사실을 명시:

> "ⓘ 사용자 seed 파일이 없어 기본 후보군 (starter seed) 으로 동작 중입니다. 이 기본
> 후보군은 투자전략 확정값이 아니며, 신규 ETF 관찰 후보 기능 작동 확인용입니다."

---

## 5. 자동 ETF universe 수집은 BACKLOG 유지

본 Step7A 는 starter seed 라는 **최소 fallback 만** 추가했다. 다음은 BACKLOG 로 유지:

- **자동 ETF universe 수집** — 전체 ETF 목록 수집 / 제외 기준 / 레버리지·인버스 처리 /
  거래대금 기준 등 결정할 것이 많음. starter seed 가 장기 운영 후보군으로 굳지 않도록
  복귀 조건 명시 (신규 ETF 관찰 후보 2회 이상 운영 후 후보군 관리 병목 재확인 시).
- **seed 편집 UI** — Step7A 는 UI 대개편이 아닌 최소 운영화. 후보군 변경은 여전히 파일
  수정 또는 별도 절차. 복귀 조건: 사용자가 후보군 직접 수정 필요 상황 1회 이상 발생 시.

---

## 6. seed 편집 UI 는 BACKLOG 유지

본 Step7A 에서는 seed 편집 UI 를 만들지 않는다. starter seed 도입으로 첫 진입 장벽은
해소되지만, 사용자가 후보군을 바꾸고 싶을 때는 여전히:
- 파일 직접 수정 (수동), 또는
- starter seed 를 삭제 후 새 사용자 seed 작성 (수동).

복귀 조건: 사용자가 운영 중 후보군 변경 필요를 명시 보고할 때 또는 PUSH 2 두 번째
구현 라운드 진입 시.

---

## 7. 완료 기준 AC

| AC | 내용 |
|---|---|
| AC-1 | 사용자 노출 표현 "외부 후보 점검" 이 공식 PUSH 2 명칭 "신규 ETF 관찰 후보" 로 정리된다. |
| AC-2 | Step6 의 pykrx 1개월 수익률 / top_candidate / 기준일 / 계산 가능 후보 수 구조가 유지된다. |
| AC-3 | seed 파일이 없을 때 사용자가 JSON 을 직접 만들지 않아도 refresh 를 실행할 수 있는 starter seed 장치가 있다. |
| AC-4 | starter seed 는 기존 사용자 seed 를 덮어쓰지 않는다. |
| AC-5 | Telegram message_text 에는 신규 ETF 관찰 후보 1개만 노출된다. |
| AC-6 | "매수 추천이 아닙니다" 문구가 유지된다. |
| AC-7 | 기존 holdings 승인 / OCI / Telegram 경로가 깨지지 않는다. |

### 본 라운드 검증 결과 (보고 직전 실측)

- pytest 119 → **147 passed** (Step5 119 + Step6 16 + Step7A 11 = 147 정확) ✓
- black --check / flake8 / TypeScript build / Next.js lint 모두 PASS ✓
- KS-10 임계: 백엔드 max draft_message.py 572 / 프론트 max EnrichedHoldingsSection.tsx
  515 / 테스트 max test_holdings_message_text.py 924 — **트리거 0 + 근접 0** ✓
- 750라인 이상 파일: `tests/test_holdings_message_text.py` (924, 변경 없음 — 보고만).

---

## 8. 다음 단계

본 Step7A 완료 후 다음 후보:

- **PUSH 1 보유 종목 상태 브리핑 구현 Step** (별도 STEP 진입 — 한 번에 하나의 PUSH 원칙).
- **PUSH 3 급락 ETF 주의 신호 최소 구현 Step** (별도 STEP 진입).
- **운영 빈도 문서 정합성 보정** (PROJECT_ORIGIN_INTENT §7 의 "1일 3회" vs Step7 §7 의
  "K6/EOD 저빈도" 통합).
- BACKLOG 잔존 후속 항목 (seed 편집 UI / 자동 universe 수집 / starter seed 확장 등).

사용자가 협의 후 명시 지시 — 본 핸드오프에서는 후속 STEP 을 선결정하지 않는다.

---

문서 끝.
