# Market Risk Reference v1 — Conclusion (DONE)

작성일: 2026-07-03
측정 방식: `wc -l` (Bash) 통일.

기존 Market Discovery 첫 화면에 KODEX200 + VIX 일별 맥락 evidence 카드를 추가.
지시문 §9 ML 경계 그대로 — 판단 라벨 / 위험 점수 / 시장 국면 라벨 추가 없음.

---

## 1. 실제 VIX 적재 범위

FDR `fdr.DataReader("VIX", start, end)` 실측:

| 항목 | 값 |
|---|---|
| source | FDR_VIX (FinanceDataReader) |
| observed_start | 2014-04-08 |
| observed_end | 2026-07-03 |
| written rows | 3079 |
| price basis | 소스 `Close` 컬럼 |
| storage | `market_benchmark_daily_price` (기존 테이블, benchmark_id='VIX') |

- Close 컬럼 존재 확인 완료.
- 날짜 중복 없음 (`(benchmark_id, date)` PK).
- NaN / 0 이하 값은 filter 로 제외.
- 신규 의존성 0건. 신규 API 키 0건. Cboe 미사용.

기본 SQLite (`state/market/market_data.sqlite`, gitignored) 에 실측 저장 완료.

---

## 2. VIX 최신 기준일

- CLI 실행 시각: 2026-07-03.
- SQLite 저장 최신 VIX 거래일: **2026-07-03** (`market_benchmark_daily_price.date` 최대).
- 최근 6일 실측 (기본 SQLite):
  ```
  2026-07-03  15.81
  2026-07-02  16.15
  2026-07-01  16.59
  2026-06-30  16.45
  2026-06-29  17.65
  2026-06-26  18.41
  ```

---

## 3. KODEX200 · VIX 기준일 차이 사례

이번 실측에서 두 기준일은 실제로 다르게 관측됨:

| 시장 | 기준일 |
|---|---|
| KODEX200 (국내) | 2026-07-02 |
| VIX (미국) | 2026-07-03 |

카드는 두 기준일을 각각 표시하며, 안내 문구 "국내·미국 시장의 마지막 확인
거래일은 다를 수 있습니다..." 를 노출. 자동 테스트
`test_kodex_and_vix_asof_dates_can_differ` 로 기준일 차이 유지 로직 검증.

지시문 §3 정책 그대로: 숨기지 않고, 같은 날짜로 강제 맞추지 않음.

---

## 4. vix CLI 와 ETF 최신화 CLI 분리 결과 (AC-3)

`scripts/refresh_market_timeseries.py` 에 `vix` 서브커맨드 신규 추가.

| 명령 | 책임 |
|---|---|
| `benchmark` | KODEX200 만 최신화 |
| `initial` | ETF 초기 적재만 |
| `incremental` | KODEX200 + ETF 증분 최신화만 (VIX 호출 X) |
| `vix` | VIX 만 적재 (KODEX200 호출 X, universe 순회 X) |

- `test_vix_cli_does_not_call_kodex_or_etf` — `_cmd_benchmark` / `_cmd_initial` / `_cmd_incremental` 이 호출되지 않음을 sentinel 로 검증.
- `test_incremental_does_not_call_vix` — `incremental` 이 `_cmd_vix` 를 호출하지 않음.
- 실행당 1회, 자동 재시도 없음. VIX 실패는 ETF 최신화·ML 실행에 영향 없음.

---

## 5. VIX unavailable 화면 동작 (AC-8 / §8.3)

- `market_risk_reference.vix.availability = "unavailable"` 시 카드 우측 패널은 "VIX 데이터가 아직 확인되지 않았습니다." 렌더.
- KODEX200 unavailable 시 좌측 패널은 "시계열 최신화가 완료되지 않았습니다." 렌더 (기존 표현 재사용).
- VIX 미확인 상태가 기존 ETF 분석이나 ML 실행을 막지 않음 — 카드만 unavailable 표시.
- 자동 테스트 `test_topn_response_market_risk_reference_unavailable_without_data` 로 응답에서도 확인.

---

## 6. Cboe 이번 Step 제외 사실

지시문 §4.1 / §10 준수:
- Cboe 호출 / 스크래핑 / CSV import / API 연동 0건.
- FDR VIX 단일 경로만 사용.
- 신규 API 키 0건.

BACKLOG 신규 항목: "Cboe VIX 자료를 이용한 수동 과거 보정 또는 보조 검증" — FDR VIX 경로 장기 비정상 시 재검토.

---

## 7. ML · 예측 · 시장 라벨 미추가 사실 (AC-10 / §9)

- VIX 를 ML feature 로 추가 X.
- ML v0 학습 데이터 변경 X.
- ML 실행 gate 변경 X (기존 `POST /ml/jobs/evidence-refresh` 게이트 그대로).
- 위험 점수 생성 X.
- 후보 제외 규칙 변경 X.
- 매수·매도 판단 변경 X.
- `high_risk` / `low_risk` / `bullish` / `bearish` / `neutral` 등 판단 라벨 코드에 존재하지 않음.

VIX 는 사용자가 참고하는 evidence 로만 사용.

---

## 8. API 응답 계약 확장 (지시문 §7 + 설계자 Q2/Q3 확정)

`MarketTopNResponse` 최상위에 `market_risk_reference` 필드만 추가:

```json
{
  "market_risk_reference": {
    "kodex200": {
      "as_of_date": "2026-07-02",
      "close": 34845.0,
      "change_1d_pct": 1.0,
      "availability": "available",
      "recent_20d_series": [{"date": "...", "close": ...}, ...],
      "series_first_date": "2014-04-09",
      "series_last_date": "2026-07-02"
    },
    "vix": {
      "as_of_date": "2026-07-03",
      "close": 15.81,
      "change_1d_pct": -2.10,
      "change_5d_pct": -14.16,
      "availability": "available",
      "recent_20d_series": [...],
      "series_first_date": "2014-04-08",
      "series_last_date": "2026-07-03"
    }
  }
}
```

**하위 필드 근거 (검증자 A-4 지적 대응)**:
- 지시문 §7 은 "market_risk_reference 객체 하나만 추가" 를 응답 계약 변경 허용 범위로 명시.
- 설계자 **Q2 확정 답변** 에서 `recent_20d_series` 를 각 항목 내부 배열로 두라고 명시 지시: "recent_20d_series는 각 항목 내부의 배열로 둡니다."
- 설계자 **Q3 확정 답변** 에서 "API 배열만 추가하고 화면이 렌더하지 않는 방식은 완료가 아닙니다" — 상세 노출용 20d 배열은 API 응답에 포함되어야 함을 명시.
- 지시문 §8.2 는 상세 노출 요구사항으로 "각 시계열 최초·최종 관측일" 을 명시 → `series_first_date` / `series_last_date` 는 이 요구사항의 최소 구현 (FIX r1 추가).

**따라서 하위 필드 (`recent_20d_series` / `series_first_date` / `series_last_date`) 는 `market_risk_reference` 객체 내부 구성 요소로서 지시문 §7 허용 범위 안**. 기존 필드는 그대로.

- 기존 필드 삭제·이름 변경·의미 변경 0건.
- 신규 endpoint 0건.
- 최상위 객체는 항상 존재. 데이터 부재 시 `availability="unavailable"` + 빈 배열 + null bounds.
- FDR 소스명, SQL 오류, 원본 예외, 외부 URL, 수집 실패 내부 사유는 응답에 노출 X.

---

## 9. 화면 계약 (지시문 §8)

- 첫 화면: `MarketDiscoveryView` 의 `MarketContextCard` 뒤에 `MarketRiskReferenceCard` 신규.
- 카드 좌우 두 영역 — KODEX200 / VIX.
- 상세 펼치기: 카드 안에서만 최소 sparkline (SVG polyline). 별도 화면/새 메뉴/새 라우트 0건.
- KODEX200 / VIX 시계열은 별도 미니 추이 — 동일 축 겹치기 금지.

기준일이 다른 경우 안내 문구 노출 (지시문 §8.1 원문).

---

## 10. 자동 테스트 결과

| 항목 | 결과 |
|---|---|
| backend 전체 테스트 | **691 passed** (675 → 691, 신규 16 — FIX r1 +3) |
| black | PASS |
| flake8 | PASS |
| frontend lint | PASS |
| frontend build | PASS |

신규 테스트 16건:
- `tests/test_market_risk_reference_service.py` (8) — unavailable / KODEX 사용 가능 / VIX change_5d / null 처리 / 20건 cap / 기준일 다름 / **series_first_last 전체 범위 (FIX r1) / series bounds none when unavailable (FIX r1)**.
- `tests/test_vix_cli_and_api.py` (8) — API 응답 확장 (available / unavailable) / vix CLI (adapt / 충돌 미덮어쓰기 / up-to-date) / CLI 독립성 (vix ↔ kodex/etf 분리) / **latest 파싱 실패 시 명확한 실패 (FIX r1)**.

---

## 11. 변경 파일 목록

- `app/api_market_topn_models.py`: 수정 (`MarketRiskReference` / `MarketRiskKodex200` / `MarketRiskVix` / `MarketRiskRecentPoint` 신규 + `MarketTopNResponse.market_risk_reference` 추가).
- `app/api_market_topn_service.py`: 수정 (`build_market_risk_reference_payload` 추가).
- `app/api_market_topn.py`: 수정 (`/market/topn/latest` 응답 조립에 필드 추가).
- `app/market_risk_reference_service.py`: 신규 (SQLite read + change 계산).
- `scripts/refresh_market_timeseries.py`: 수정 (`vix` 서브커맨드 추가).
- `tests/test_market_risk_reference_service.py`: 신규 (8 케이스 — 초기 6 + FIX r1 +2).
- `tests/test_vix_cli_and_api.py`: 신규 (8 케이스 — 초기 7 + FIX r1 +1).
- `frontend/lib/api/market.ts`: 수정 (타입 추가).
- `frontend/app/components/MarketRiskReferenceCard.tsx`: 신규 (카드 컴포넌트).
- `frontend/app/components/MarketDiscoveryView.tsx`: 수정 (카드 삽입).
- `frontend/app/globals.css`: 수정 (카드 스타일 최소).
- `docs/STATE_LATEST.md`: 수정.
- `docs/ASSUMPTIONS.md`: 수정 (VIX 확보 사실 추가).
- `docs/handoff/POC2_B_NEXT_ACTIONS.md`: 수정.
- `docs/handoff/POC2_FEATURE_INVENTORY.md`: 수정 (§2.37 추가).
- `docs/handoff/POC2_MARKET_RISK_REFERENCE_V1_CONCLUSION.md`: 신규 (본 파일).
- `docs/backlog/BACKLOG.md`: 수정 (Cboe VIX 보조 검증 항목 신규).

---

## 12. AC 충족 (지시문 §11)

| AC | 결과 |
|---|---|
| AC-1 FDR VIX 조회 실측 + Close 확인 | ✅ |
| AC-2 VIX Close SQLite 저장 (기존 테이블) | ✅ |
| AC-3 vix 독립 CLI (benchmark/initial/incremental 미호출) | ✅ |
| AC-4 VIX 실패가 ETF 최신화·ML 실행에 영향 없음 | ✅ |
| AC-5 응답에 market_risk_reference 추가 | ✅ |
| AC-6 첫 화면 KODEX200·VIX 기본값 표시 | ✅ |
| AC-7 상세 최근 20거래일 추이 + 각 시계열 최초·최종 관측일 | ✅ (FIX r1 — series_first_date / series_last_date 추가 + UI 노출) |
| AC-8 기준일 차이·unavailable 상태 미숨김 | ✅ |
| AC-9 기존 API 필드 삭제·이름 변경·의미 변경 0건 | ✅ |
| AC-10 VIX ML feature/라벨/판단 미사용 | ✅ |
| AC-11 Cboe/신규 API 키/의존성/가격 테이블/DB 엔진 0건 | ✅ |
| AC-12 backend / black / flake8 / frontend lint / build | ✅ |

---

## 13. 알려진 한계 (Known Limits)

### 13.1 FDR VIX 단일 경로

- 상태: 지시문 §4.1 명시 정책 그대로.
- 내용: FDR 이 장기간 비정상일 때 즉시 사용할 대체 경로 없음.
- 완화 상태: BACKLOG 항목 "Cboe VIX 자료를 이용한 수동 과거 보정 또는 보조 검증" 로 이관.

### 13.2 FDR 호출 timeout 부재

- 이전 Closeout STEP note 그대로 유지. `vix` 명령도 동일.
- BACKLOG §7 참조.

---

## 14. 다음 작업 후보 (사용자 결정 대기)

1. **위험 evidence / 시장 국면 / 추세 전환 거리** — 본 STEP 확보 evidence 위에서 진입.
2. **ML 축2** (위험 감지) — 동일.
3. **Cboe VIX 보조 검증 경로** — BACKLOG 신규 항목.
4. **FDR 호출 timeout 명시** — 이전 STEP note 유지.
