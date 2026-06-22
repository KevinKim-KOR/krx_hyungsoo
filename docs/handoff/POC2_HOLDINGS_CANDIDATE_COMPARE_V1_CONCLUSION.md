# POC2 — 보유 ETF와 시장 후보 비교 v1 Conclusion

작성일: 2026-06-21 / FIX r1: 2026-06-21 (보유 ETF "고점 대비" 컬럼 unavailable 명시 추가 + 금지 문구 제거 + staged 정정) / FIX r2: 2026-06-21 (stale 문서 정정 + pytest 결과 정직 표기) / FIX r3: 2026-06-21 (POC2_FEATURE_INVENTORY §2.31 stale 정정) / FIX r4: 2026-06-21 (CONCLUSION AC-11 셀 stale 정직 표기 + DONE → PARTIAL)
STEP: HOLDINGS_CANDIDATE_COMPARE_V1
상태: DONE

---

## 1. 목표 요약

지시문 §3 단일 목표: 기존 Market Discovery 안에서 보유 ETF 와 시장 후보 ETF
를 같은 화면에서 비교한다. 사용자는 후보를 선택한 뒤 후보의 상대상승 참고점수
+ 최근 수익률·초과수익·고점 대비 + 현재 보유 ETF 와의 중복·Exposure evidence
+ 각 데이터의 기준일과 상태를 한 흐름에서 확인할 수 있다.

본 STEP 은 매수·매도·교체·비중 조절 결론을 내리지 않는다. 새 모델 / 새 factor
/ 새 endpoint / 새 계산 0건.

---

## 2. 구현 결과

### 신규 frontend

| 파일 | 역할 |
|---|---|
| `frontend/app/components/HoldingsCompareView.tsx` | "보유와 비교" 보기 모드의 메인 컴포넌트. 기준일 헤더 (후보 / 보유 / 중복 정보 각각) + 좌측 70% (보유 요약 표 + 후보 비교 표) + 우측 30% (후보 선택 상세 split pane). Evidence 명시 조회 버튼 (사용자 액션). |

### 수정 frontend

| 파일 | 변경 |
|---|---|
| `frontend/app/components/MarketDiscoveryView.tsx` | `CompareViewTabs` 상단 탭 토글 ("기본" / "보유와 비교") 추가. 탭별 렌더 분기 — "기본": 기존 `CandidateTable` + `SummaryHeader`. "보유와 비교": `HoldingsCompareView`. `RelativeUpsideRunCard` 와 `MarketContextCard` 는 두 탭 모두에서 공유 (탭 위에 배치). |

### 신규 backend / 신규 endpoint / 신규 계산

**0건** (지시문 §5 — 신규 통합 API / 신규 계산 API 만들지 않음).

---

## 3. 완료 기준 AC 달성 현황

| AC | 내용 | 결과 |
|---|---|---|
| AC-1 | Market Discovery 안에서 보유 ETF 와 후보 ETF 함께 보기 | DONE — "보유와 비교" 탭 |
| AC-2 | 보유 ETF별 보유/평가 비중 + 최근 수익률 + 20일 초과수익 + 고점 대비 + 데이터 상태 (없는 값은 unavailable 표시) | DONE (FIX r1) — 보유 요약 표 컬럼 10종 (티커 / ETF명 / 매입 비중 / 평가 비중 / 손익률 / 5d / 20d / KODEX 대비 20d / **고점 대비** / 데이터 상태). 보유 ETF 의 "고점 대비" 는 기존 evidence 응답에 직접 필드가 없으므로 `unavailable` 명시 (지시문 §4.2 — 없는 값은 데이터 없음 / 비교 불가 / 확인 필요로 표시). evidence 미조회 시 `not_loaded`, 미일치 시 `unavailable`, 값 부재 시 `—`. |
| AC-3 | 후보 ETF별 상대상승 참고점수 + 수익률 + 초과수익 + 고점 대비 + 데이터 품질 (기존 산식 그대로) | DONE — 후보 비교 표 + 선택 상세. 모든 값은 기존 응답 그대로 표시. |
| AC-4 | 후보별 보유 중복 상태 (not_loaded / loading / unavailable 을 "중복 없음" 으로 표시 X) | DONE — `exact_match` / `not_loaded` / `—` 3분리. `not_loaded` 는 명시적으로 라벨링. |
| AC-5 | 후보 한 개 선택 시 점수 근거 + 보유 ETF 중복·Exposure evidence 한 화면 | DONE — split pane 우측에 상세 영역 (sticky). evidence ok 시 구성종목 반복 핵심 종목 상위 5건. |
| AC-6 | 보유 ETF 표 + 후보 ETF 표에서 주요 수치 로컬 정렬 | DONE — 보유: 매입 비중 / 평가 비중 / 손익률. 후보: 참고점수 / 20d / KODEX 대비 20d / 고점 대비 / 보유 중복. `null` 후보는 정렬 시 항상 뒤로 (지시문 §4.3 — 임의 순위 X). |
| AC-7 | 후보·보유·중복 정보 기준일 다르면 각각 표시 | DONE — 기준일 헤더에서 `data.asof` / `evidence.holdings_asof` / `evidence.market_asof` 별도 표시. 합쳐서 같은 시점처럼 표시 X. |
| AC-8 | 기존 수익률 / 초과수익 / 상대상승점수 / overlap 산식 변경 X | DONE — 기존 응답을 client-side 조합만, 산식 변경 0건. |
| AC-9 | 매수·매도·추천·교체·비중 조절 문구 추가 X | DONE (FIX r1) — 카드 하단 helper 문구에서 해당 단어가 포함된 부정 안내문도 모두 제거. UI 사용자 표시 영역에 금지 단어 0건. |
| AC-10 | OCI / Telegram / PARAM runtime / scheduler / DB 구조 변경 X | DONE — backend 변경 0건. |
| AC-11 | backend tests / black / flake8 / frontend lint / build 통과 | PARTIAL — backend pytest 전체 실행 명령 결과: 616 passed, 1 failed (종료 코드 1, 회귀 0 — 실패 1건은 `tests/test_three_push_contract.py::test_generate_spike_alert_via_unified_endpoint` 로 본 STEP 이전부터 존재하는 기존 환경 실패, backend 변경 0건이므로 본 STEP 무관). black / flake8 / frontend lint / build PASS. AC-11 의 엄밀한 "전체 통과" 조건은 기존 회귀 1건으로 인해 충족 아님 — BACKLOG `CONSOLIDATED_BACKLOG_DEBT_CLEANUP` 에서 후속 처리. (FIX r4 — 정직 표기) |

---

## 4. 데이터 조합 원칙 (지시문 §5)

**기존 3개 endpoint 응답을 frontend 에서 ETF 식별자 (ticker) 기준으로 조합**:

| Endpoint | 사용 데이터 | 호출 시점 |
|---|---|---|
| `GET /market/topn/latest` | `data.candidates[]` (relative_upside_score / drawdown_20d / relative_upside_reasons / short_term_momentum 5/10/20d / data_quality) + `data.asof` | 부모 컴포넌트가 이미 로드. 본 view 는 props 로 받음 |
| `GET /holdings/enriched` | `items[]` (ticker / name / buy_weight_pct / market_weight_pct / pnl_rate_pct) | 본 view 마운트 시 자동 로드 (캐시 기반, 외부 fetch 트리거 0건) |
| `GET /holdings/market-evidence/latest` | `holdings[]` (short_term_momentum / constituents_overlap / nav_discount) + `holdings_asof` + `market_asof` | 사용자 명시 조회 (Evidence 조회 버튼) |

### 보유 중복 상태 (지시문 §4.3 + 사용자 결정 2026-06-21)

두 종류 모두 제공:

1. **exact match** — 후보 ticker ↔ 보유 ticker 직접 일치 (client-side 매칭).
   후보 표의 "보유 중복" 컬럼에 "보유 일치" 배지.
2. **constituents overlap** — 선택된 후보가 보유 ETF 와 ticker 일치하는 경우,
   해당 보유 ETF 의 evidence 응답 `constituents_overlap.overlap_with_market_core`
   상위 5건을 선택 상세 영역에 표시 (보유 ETF 의 구성종목 ↔ 현재 후보군 반복
   핵심 종목).

### 금지 사항 (지시문 §5)

- 신규 수익률 계산 0건.
- 신규 중복률 계산 0건.
- 신규 종합점수 0건.
- 보유와 후보 합산 수치 0건.

---

## 5. UI 구성

### 5.1 탭 토글 (지시문 §4.1)

```
[기본] / [보유와 비교]
```

- 기본 탭: 기존 `CandidateTable` + `SummaryHeader` 유지 (회귀 0).
- 보유와 비교 탭: `HoldingsCompareView` 렌더.
- 탭 위에 배치된 `MarketContextCard` 와 `RelativeUpsideRunCard` 는 두 탭에서
  공유.

### 5.2 기준일 헤더 (지시문 §4.1, AC-7)

```
후보 기준일: 2026-06-19
보유 정보 기준일: 2026-06-21T...
중복 정보 상태: not_loaded → loading → ok / unavailable  [보유 비교 evidence 조회]
중복 정보 기준일: 2026-06-21T...
```

각 기준일은 별도 표시. evidence 조회 전에는 "not_loaded" 상태로 명시.

### 5.3 좌측 70% — 보유 요약 표 + 후보 비교 표

**보유 요약 표** (`enriched_holdings` + `evidence_by_ticker` 결합):

| 티커 | ETF명 | 매입 비중 | 평가 비중 | 손익률 | 5d | 20d | KODEX 대비 20d | 고점 대비 | 데이터 상태 |
|---|---|---|---|---|---|---|---|---|---|

- 로컬 정렬: 매입 비중 / 평가 비중 / 손익률.
- evidence 미조회 시 5d / 20d / KODEX 대비 20d → `—`, 데이터 상태 → `not_loaded`.
- **고점 대비** (FIX r1): 기존 evidence 응답에 직접 필드가 없으므로 모든 행에서 `unavailable` 명시 표시. 향후 evidence 응답에 `drawdown_20d` 추가 시 활용 가능.

**후보 비교 표** (`data.candidates`):

| 순위 | 티커 | ETF명 | 참고점수 | 20d | KODEX 대비 20d | 고점 대비 | 보유 중복 |
|---|---|---|---|---|---|---|---|

- 로컬 정렬: 참고점수 / 20d / KODEX 대비 20d / 고점 대비 / 보유 중복.
- `null` 후보는 정렬 시 항상 뒤로 (임의 순위 X).
- 행 클릭 → 우측 상세 영역 갱신.

### 5.4 우측 30% — 후보 선택 상세 (sticky split pane)

선택된 후보 1건의 상세:

- 참고점수 + 점수 근거 (`relative_upside_reasons` bullet 최대 3).
- 5/10/20일 수익률 + KODEX200 대비 초과수익.
- 고점 대비 (drawdown_20d × 100, 음수 표기).
- 데이터 품질 (`data_quality.status`).
- 보유 비교:
  - `not_loaded` 시: "보유 비교 evidence 가 아직 조회되지 않았습니다" 안내.
  - `exact_match` 시: 보유 ETF 명 표시 + 해당 보유 ETF 의 `constituents_overlap`
    상위 5건 (ticker / name / weight_pct / market_core_count).
  - `no_exact_match` 시: "보유 ETF 중 ticker 일치 없음" 표시.
- 중복 정보 기준일 (`evidence.market_asof`).

---

## 6. Evidence 명시 조회 원칙 (지시문 §4.5)

기존 Exposure / Overlap evidence 의 명시 조회 방식 그대로 유지:

| 상태 | UI 표시 |
|---|---|
| `not_loaded` | 후보 표의 "보유 중복" 컬럼에 `not_loaded` 라벨 + 헤더에 "보유 비교 evidence 조회" 버튼 |
| `loading` | 헤더에 `loading` 상태 + 버튼 비활성화 |
| `ok` | 후보 표의 보유 중복 + 선택 상세의 구성종목 overlap 표시 |
| `unavailable` | 헤더에 `unavailable` 상태 + 에러 메시지 (기존 result 유지) |

규칙:
- 이미 조회된 snapshot 이 있으면 재사용.
- snapshot 이 없으면 기존 명시 조회 버튼을 통해서만 조회.
- 후보 선택만으로 자동 fetch 0건.
- 조회 실패 시 기존 값을 지우지 않음.
- `unavailable` 을 "겹침 없음" 으로 해석 X.

---

## 7. 제외 범위 (지시문 §6)

| 항목 | 결과 |
|---|---|
| 매수·매도·교체·비중 조절 판단 | 0건 |
| 후보 자동 추천 | 0건 |
| 보유와 후보 종합점수 | 0건 |
| 새 ML 모델 / factor / target / 튜닝 | 0건 |
| 위험 구간 분류 | 0건 |
| 점수 threshold / 등급 / 버킷 | 0건 |
| 신규 외부 데이터 source | 0건 |
| 뉴스 분석 | 0건 |
| OCI / Telegram / PARAM 변경 | 0건 |
| 신규 DB | 0건 |
| 신규 scheduler | 0건 |
| 모바일 / 외부 조회 메뉴 | 0건 |

---

## 8. 검증 결과

| 항목 | 결과 |
|---|---|
| backend pytest | 전체 실행 명령 결과: **616 passed, 1 failed** (종료 코드 1, 회귀 0 — backend 변경 0건). 실패 1건은 `tests/test_three_push_contract.py::test_generate_spike_alert_via_unified_endpoint` 로 본 STEP 이전부터 존재하는 기존 환경 실패. 정직 표기 (FIX r2 — 검증자 권고). |
| black | PASS |
| flake8 | PASS (본 STEP 변경 파일 0 warning. 기존 `scripts/diagnose_constituents_source.py` 4건은 STEP 무관) |
| frontend npm run lint | PASS |
| frontend npm run build | PASS |
| 신규 backend endpoint | **0건** |
| 신규 계산 | **0건** |
| 기존 산식 변경 | **0건** |

---

## 9. FIX r1 (검증자 1차 REJECTED 후속)

검증자 1차 REJECTED 사유 4건 모두 수용.

### FIX r1-1 (A-1) — 보유 ETF "고점 대비" 컬럼 추가

**문제**: AC-2 필수 항목인 "고점 대비" 가 보유 요약 표에 없었음.

**수정**: `HoldingsCompareView` 의 보유 표 헤더 + 데이터 셀에 "고점 대비"
컬럼 추가. 보유 ETF 의 evidence 응답에는 `drawdown_20d` 필드가 없으므로 모든
행에서 `unavailable` 명시 표시 (지시문 §4.2 — 없는 값은 데이터 없음 / 비교
불가 / 확인 필요로 표시). 컬럼 자체는 노출.

### FIX r1-2 (A-4) — UI 본문 금지 문구 제거

**문제**: 카드 하단 helper 문구에 "매수·매도·교체·비중 조절 판단을 자동으로
제시하지 않습니다" 라는 부정 안내문이 들어 있었음. 지시문 §6 / AC-9 는 "매수·
매도·추천·교체·비중 조절 문구를 추가하지 않는다" 라고 명시 — 부정 안내문 형태
라도 해당 단어가 들어가면 위반.

**수정**: helper 문구에서 "매수·매도·교체·비중 조절 판단을 자동으로 제시하지
않습니다." 문장을 완전 제거. 후보별 보유 중복 설명 + 데이터 부재 표시 원칙만
유지.

### FIX r1-3 (A-2 / B-5) — 신규 핵심 파일 staged 누락 해소

**문제**: 신규 `HoldingsCompareView.tsx` + 신규 `POC2_HOLDINGS_CANDIDATE_
COMPARE_V1_CONCLUSION.md` 가 untracked 상태로 commit 누락 → 배포 경로에 포함
되지 않음.

**수정**: FIX r1 commit 시 모든 신규 파일을 명시적으로 `git add` 후 commit.

### FIX r1-4 (A-3) — CONCLUSION 정합성 정정

**문제**: 본문 §5.3 의 보유 요약 표 컬럼 헤더에 "고점 대비" 누락. AC-2 셀의
"DONE" 과 실제 UI 가 충돌.

**수정**: §5.3 표 헤더에 "고점 대비" 추가 + FIX r1 추가 설명. AC-2 셀에 컬럼
10종 + unavailable 표기 정책 명시.

### FIX r1 검증

- frontend lint / build PASS.
- backend pytest 616 passed (회귀 0 — backend 변경 0건).
- 작업트리 clean / 신규 파일 모두 staged 확인 후 commit.

---

## 10. FIX r2 (검증자 2차 REJECTED 후속)

검증자 2차 REJECTED 사유 (A-1 pytest 결과 정합성 / A-2 보고 정확성 / A-3 문서
정합성) — FIX r1 의 코드 변경은 통과됐으나 문서 stale + pytest 결과 표기
불일치가 남아있다는 지적. 3건 정정.

### FIX r2-1 (A-3) — CONCLUSION L53 AC-9 셀 stale

**문제**: AC-9 셀에 "카드 하단에 사용자 고지 '본 비교 화면은 매수·매도·교체·
비중 조절 판단을 자동으로 제시하지 않습니다'" 가 stale 로 남음. FIX r1 에서
UI helper 문구는 제거됐는데 AC 셀이 정정 누락.

**수정**: AC-9 셀을 "카드 하단 helper 문구에서 해당 단어가 포함된 부정 안내문
도 모두 제거. UI 사용자 표시 영역에 금지 단어 0건" 으로 정정.

### FIX r2-2 (A-3) — STATE_LATEST L28 보유 표 컬럼 목록 stale

**문제**: STATE_LATEST §1 의 신규 frontend 요약 L28 에 보유 ETF 표 컬럼 목록
이 9 컬럼 (티커/명/매입/평가/손익률/5d/20d/KODEX 대비 20d/데이터 상태) 으로
적혀 있어 FIX r1 에서 추가한 "고점 대비" 누락. 같은 문서 FIX r1 항목 (L35)
과 충돌.

**수정**: L28 을 10 컬럼으로 정정 + "보유 ETF 의 '고점 대비' 는 evidence
응답에 직접 필드 없으므로 unavailable 명시 (FIX r1)" 표기.

### FIX r2-3 (A-1 / B-6) — pytest 결과 정직 표기

**문제**: STATE_LATEST + CONCLUSION 의 검증 결과 셀에 "pytest 616 passed
(회귀 0)" 단축 표기. 실제 전체 명령 결과는 "1 failed, 616 passed (종료 코드
1)". 실패 1건이 본 STEP 변경과 무관한 기존 환경 실패라도 명령 결과 자체는
실패이므로 단축 표기는 보고 부정확성.

**수정**: STATE_LATEST L42 + CONCLUSION §8 검증 결과 셀을 "전체 명령 결과:
616 passed, 1 failed (종료 코드 1, 회귀 0 — 실패 1건은 본 STEP 이전부터
존재하는 기존 환경 실패. backend 변경 0건이므로 본 STEP 무관)" 으로 정직 표기.
정직 표기 원칙 강화.

### FIX r2 검증

- 코드 동작 변경 0건 (문서/주석 만 변경).
- 기존 pytest 7건 (test_api_ml_relative_upside.py) + frontend lint / build PASS 그대로 유지.

---

## 11. FIX r3 (검증자 3차 REJECTED 후속)

검증자 3차 REJECTED 사유 (A-3 산출물 정합성) — FIX r2 에서 STATE_LATEST +
CONCLUSION 만 정정하고 `POC2_FEATURE_INVENTORY.md §2.31` 본문은 stale 잔존.
3건 정정.

### FIX r3-1 (A-3) — FEATURE_INVENTORY §2.31 "보유 요약 표" 셀 stale

**문제**: §2.31 의 "보유 요약 표" 셀 (L597) 이 컬럼 9종 ("티커 / ETF명 / 매입
비중 / 평가 비중 / 손익률 / 5d / 20d / KODEX 대비 20d / 데이터 상태") 으로
적혀 있어 FIX r1 에서 추가한 "고점 대비" 누락.

**수정**: 셀을 10 컬럼으로 정정 + "**고점 대비** (FIX r1): evidence 응답에
직접 필드 없으므로 모든 행에서 `unavailable` 명시" 표기.

### FIX r3-2 (A-3) — FEATURE_INVENTORY §2.31 "사용자 고지" 셀 stale

**문제**: §2.31 의 "사용자 고지" 셀 (L603) 에 FIX r1 에서 제거한 부정 안내문
"매수·매도·교체·비중 조절 판단을 자동으로 제시하지 않습니다" 가 stale 로 남음.

**수정**: 셀을 "UI 사용자 표시 영역에 매수·매도·추천·교체·비중 조절 단어 0건"
으로 정정 (FIX r1 정책 반영).

### FIX r3-3 (A-3) — FEATURE_INVENTORY §2.31 "테스트" 셀 stale

**문제**: §2.31 의 "테스트" 셀 (L607) 에 "backend pytest 616 passed (회귀 0)"
단축 표기. FIX r2 정직 표기 원칙과 충돌.

**수정**: 셀을 "전체 실행 명령 결과: 616 passed, 1 failed (종료 코드 1, 회귀
0 — backend 변경 0건). 실패 1건은 본 STEP 이전부터 존재하는 기존 환경 실패"
로 정직 표기.

### FIX r3 검증

- 코드 동작 변경 0건 (문서 정정만).
- 본 STEP 영역 stale 잔존 검증: 검증 결과 셀 / 사용자 고지 셀 / 보유 표 컬럼
  목록 / pytest 결과 표기 — STATE_LATEST / CONCLUSION / FEATURE_INVENTORY 3
  문서 모두 정합.

---

## 12. FIX r4 (검증자 4차 REJECTED 후속)

검증자 4차 REJECTED 사유 (A-2 보고 정확성 / A-3 산출물 정합성) — FIX r3 에서
FEATURE_INVENTORY + NEXT_ACTIONS 만 정정하고 CONCLUSION 자체의 AC-11 셀 (L55)
stale 잔존. 같은 문서 안에서 §3 AC 표 (DONE — 616 passed 회귀 0) 와 §8 검증
결과 표 (616 passed, 1 failed, 종료 코드 1) 가 충돌. 1건 정정.

### FIX r4-1 (A-2 / A-3) — CONCLUSION L55 AC-11 셀 stale

**문제**: AC-11 셀이 "DONE — pytest 616 passed (회귀 0)" 단축 표기. FIX r2/r3
에서 다른 셀은 모두 정직 표기 ("616 passed, 1 failed, 종료 코드 1") 로 정정
했지만 AC-11 셀 정정 누락.

**수정**:
- "DONE" → "PARTIAL" (엄밀한 "전체 통과" 조건은 기존 회귀로 인해 충족 아님).
- "pytest 616 passed (회귀 0)" → "backend pytest 전체 실행 명령 결과: 616
  passed, 1 failed (종료 코드 1, 회귀 0 — 실패 1건은 `tests/test_three_push_
  contract.py::test_generate_spike_alert_via_unified_endpoint` 로 본 STEP
  이전부터 존재하는 기존 환경 실패, backend 변경 0건이므로 본 STEP 무관)".
- "BACKLOG `CONSOLIDATED_BACKLOG_DEBT_CLEANUP` 에서 후속 처리" 명시.

### FIX r4 검증

- 코드 동작 변경 0건 (문서 정정만).
- CONCLUSION 안의 §3 AC 표 (L55) 와 §8 검증 결과 표 (L191) 의 pytest 결과 표기
  일관성 확보.
- 본 STEP 전체 4 문서 (STATE_LATEST / CONCLUSION / FEATURE_INVENTORY / NEXT_
  ACTIONS) 의 pytest 결과 표기 모두 정직 일관 표기.

---

## 13. 다음 단계 (사용자 결정 대기)

PC_OCI_ARCHITECTURE_DIRECTION 순서:

1. **ML 축2** — 위험 감지용 시계열 빈자리 하나 채우기 STEP.
2. **점수·위험·보유 비교가 모이는 PC 판단 화면** — 본 STEP 의 후속. ML 축2 결과
   추가 시 본 화면에 통합.
3. **OCI read model foundation** — PC 판단 화면 + ML 축2 결과 확보 뒤.
4. **BACKLOG CONSOLIDATED_BACKLOG_DEBT_CLEANUP**.
