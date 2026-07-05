# 시장 우선 운영 원칙 (Market First Operating Direction)

작성일: 2026-07-03
성격: **현재 구현·운영 우선순위 handoff.** MASTER_PLAN 대체 문서가 아니다. `docs/MASTER_PLAN.md` 의 1~5단계 (+6단계 확장) 구조·순서·승인 게이트·완료 조건은 그대로 유지되며, 본 문서는 각 단계 안에서 **무엇을 먼저 구현할지** 정하는 기준이다.

---

## 1. 현재 운영 우선 흐름

```text
시장 시계열·시장 evidence
→ 시장 전체 흐름 ML 학습 데이터셋·Baseline
→ 시장 흐름과 보유 ETF 정합성
→ 필요한 소수 ETF만 상세 evidence·Decision Draft Preview
→ 외부 AI 해석 참고
→ 기존 AI Sessions에 사용자 판단 기록
→ 기존 승인·OCI·Telegram 전달 흐름
→ 이후 ML·백테스트 고도화
```

이 흐름은 기존 MASTER_PLAN 의 상위 단계 안에서 **현재 무엇을 먼저 구현할지** 정하는 기준이다. 단계 번호·순서·승인 게이트 자체를 재정의하지 않는다.

---

## 2. 운영 원칙

```text
- 시스템의 첫 질문은 "시장 전체가 지금 어떤 흐름인가"다.
- 두 번째 질문은 "내 보유 ETF가 그 흐름에 편승하고 있는가"다.
- 보유 ETF 개별 상세는 기본 운영 흐름이 아니라,
  예외·기회 종목을 깊게 볼 때만 사용하는 drill-down이다.
- 사용자가 모든 보유 ETF를 매번 개별 심사하도록 만들지 않는다.
- 직장인 개인 운영 기준으로,
  시장 요약 → 보유 정합성 → 소수 상세 확인 순서를 유지한다.
- 24시간 수집, 무중단 운영, 엔터프라이즈 수준의 고가용성은 목표가 아니다.
```

---

## 3. 완료 기능의 역할 고정

### 3.1 시계열 SQLite

- **역할**: 시장·ETF evidence 의 기반.
- **사용자 일상 조작 기능이 아님**. 사용자가 필요할 때 PC CLI 로 최신화.

### 3.2 KODEX200·VIX 시장 위험 참고 (Market Risk Reference v1)

- **역할**: 시장 맥락을 빠르게 보는 원시 evidence.
- **시장 예측·자동 행동 신호가 아님**. 판단 라벨·위험 등급 부여 X.

### 3.3 보유·후보 비교 (HoldingsCompareView)

- **역할**: 시장 흐름과 연결할 대상·예외 종목을 고르는 화면.
- 개별 종목의 자동 매수·매도 신호를 생성하지 않는다.

### 3.4 Decision Draft Preview v1

- **역할**: 선택 ETF 하나를 외부 AI 에 물어보기 좋게 정리하는 **선택적 상세 도구**.
- **주력 운영 흐름이 아니라 drill-down 도구**.
- 새 승인 시스템·새 이력 시스템으로 확장하지 않음.
- 저장 없음. PENDING 저장 오염 없음. 승인·OCI·Telegram 미연결.

---

## 4. AI Sessions 및 승인 원칙

```text
- 사용자 판단 기록은 기존 AI Sessions를 중심으로 사용한다.
- 기존 AI Sessions와 역할이 겹치는 별도 승인·결정 시스템을 새로 만들지 않는다.
- OCI·Telegram 전달은 향후 기존 AI Sessions의 승인 기록과
  연결하는 방향으로 검토한다.
```

Decision Draft Preview 는 사용자가 외부 AI 웹사이트에 붙여넣기 위한 evidence 정리 도구일 뿐, 별도의 승인 대상 산출물이 아니다. 사용자 확정 문구는 기존 AI Sessions 로 이관된다.

---

## 5. 데이터 소스 운영 원칙

```text
주 시계열 소스:
NAVER_FDR (fdr.DataReader("NAVER:<ticker>", ...))

보조 소스:
YAHOO_FDR (fdr.DataReader("YAHOO:<ticker>.KS", ...))
  네이버 실패 또는 빈 응답 시 1회. 자동 재시도 없음.

KRX CSV/Excel:
특정 과거 구간·누락·충돌 보정용 fallback.
정기 운영 경로 아님.

KRX Open API:
주 운영 소스로 사용하지 않음.

운영 방식:
사용자가 필요할 때 PC CLI로 최신화 후 분석·ML 실행.
24/365 자동 수집이 아니다.
```

이 원칙은 이미 구현된 상태 (`scripts/refresh_market_timeseries.py` 의 `benchmark` / `initial` / `incremental` / `vix` 서브커맨드) 로 반영되어 있으며, 후속 STEP 에서도 유지한다.

---

## 6. 다음 활성 Step

```text
직전 활성 Step:
Market Flow ML Walk-forward Lookback v1 → DONE (2026-07-05).

Walk-forward 요약:
  Ridge baseline v1 의 과거 반복 성능 evidence 산출.
  build_dataset() 1회 계산 + 각 기준일 t 마다 target_end_date < t 인 학습 subset.
  StandardScaler · Ridge(alpha=1.0) 는 기준일별 새로 fit.
  Anchor = 756 학습 행 확보 첫 KODEX200 거래일, 이후 grid 는 KODEX200 거래일 index 기준 20 간격 고정 (skip 이 grid 를 밀지 않음).
  Simple baseline = 동일 학습 범위의 target 평균 비교.
  실측: predictions=110, 2017-07-06 ~ 2026-06-01, 연도별 10 구간.
  Ridge directional_accuracy 0.5273, simple baseline 0.5727.
  상세: docs/handoff/POC2_MARKET_FLOW_WALK_FORWARD_LOOKBACK_V1_CONCLUSION.md.

이전 활성 Step:
Market Flow ML Dataset + Baseline v1 → Closeout DONE (2026-07-05).
  상세: docs/handoff/POC2_MARKET_FLOW_ML_DATASET_BASELINE_V1_CONCLUSION.md.

다음 활성 Step: 미결정 (설계자 지정 대기).
```

**목표**: 기존 SQLite 의 KODEX200 / KOSPI / VIX / 정상 ETF universe 시계열을 사용해 **누수 없는 날짜별 시장 학습 행** 과 **baseline 결과** 를 만든다.

**이번 다음 Step 에서 하지 않는 것**:

```text
- 보유 ETF 상세 UI 확장
- Decision Draft Preview 확장
- AI Sessions 확장
- 승인 UI 신설
- OCI·Telegram 변경
- 자동 매수·매도
- 시장 예측 문구·임계치 선확정
```

---

## 7. 동결 항목 (본 원칙 하에서 확장 금지)

```text
- Decision Draft Preview 추가 확장
- 별도 승인 테이블·승인 UI·결정 이력 화면 (기존 AI Sessions 와 역할 중복)
- 보유 ETF 전체 개별 심사형 화면 확장
- 24시간 자동 수집·무중단 운영 인프라
```

동결 항목이라도 시장 우선 원칙과 명백히 연결되고 사용자 결정이 있을 때는 재검토 가능. 단, 본 문서는 그 재검토의 기본 상태를 "동결" 로 유지한다.

---

## 8. 완료 기능 참조

| 기능 | 참조 문서 |
|---|---|
| 시장 시계열 SQLite Closeout | `docs/handoff/POC2_MARKET_TIMESERIES_SQLITE_CLOSEOUT_CONCLUSION.md` |
| Market Risk Reference v1 (KODEX200 + VIX) | `docs/handoff/POC2_MARKET_RISK_REFERENCE_V1_CONCLUSION.md` |
| Decision Draft Preview v1 | `docs/handoff/POC2_DECISION_DRAFT_PREVIEW_V1_CONCLUSION.md` |

---

## 9. 본 문서의 위치

본 문서는 `docs/MASTER_PLAN.md` 를 **대체하지 않고 보완**한다.

- 단계 번호 / 순서 / 승인 게이트 / 완료 조건 → MASTER_PLAN 그대로.
- 현재 무엇을 먼저 구현할지 / 완료 기능의 역할 / 다음 활성 Step → 본 문서.
- 향후 시장 우선 원칙과 어긋나는 STEP 후보가 나오면 본 문서로 복귀하여 정합성 확인.
