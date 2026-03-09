# 친구 프로젝트(momentum-etf) vs 내 프로젝트(krx_alertor_modular) 비교 분석 v2

> 분석 기준일: 2026-03-09 (v2 업그레이드)
> 이전 분석: 2026-02-25 (v1)
> 친구 프로젝트: `momentum-etf` (GitHub 소스)
> 내 프로젝트: `krx_alertor_modular` (KRX Strategy Cockpit)

---

## 1. 프로젝트 개요 비교

| 항목 | 친구 (momentum-etf) | 나 (krx_alertor_modular) |
|---|---|---|
| **목적** | 5버킷 분산 ETF 모멘텀 자동매매 | KRX ETF 모멘텀 전략 + 운영 자동화 |
| **시장** | 🇰🇷 한국, 🇺🇸 미국, 🇦🇺 호주 (3개국) | 🇰🇷 한국 전용 |
| **계정** | 5개 (kor_kr, kor_isa, kor_pension, aus, us) | 1개 (단일 전략) |
| **유니버스 규모** | ETF 수십~수백 종목 (버킷당 동적) | 4-13종목 (5버킷 확장 완료, P185) |
| **알림** | Slack 자동 알림 (17KB notification.py) | Cockpit UI 수동 확인 |
| **배포** | GitHub Actions CI/CD + Docker | OCI 서버 + SSH Tunnel + 수동 Push |
| **UI** | Streamlit 대시보드 (app.py 33KB + app_pages 5파일) | Streamlit Cockpit (cockpit.py 57KB) |
| **코드 규모** | ~630KB (core + utils + strategies) | ~250KB (app + backend) |

---

## 2. 전략 로직 비교

### 2.1 스코어링

| 항목 | 친구 (MAPS) | 나 (Momentum Score) |
|---|---|---|
| **핵심 공식** | `(Close / MA - 1) × 100` | 모멘텀 수익률 + RSI 필터 |
| **이동평균 종류** | 6종 (SMA, EMA, WMA, DEMA, TEMA, HMA) | 1종 (SMA만) |
| **MA 기간** | 1~12개월 (20~240 거래일) 탐색 | 8~60일 검색공간 |
| **매수 조건** | MAPS > 0 (MA 위에 있으면 매수) | 모멘텀 > entry_threshold + ADX 필터 |
| **매도 조건** | 리밸런싱 때만 교체 (추세 이탈해도 보유) | P184-Fix 이후: `rebalance_only` 모드 지원 |

> [!IMPORTANT]
> **v2 변경사항**: P184-Fix 이후 내 프로젝트도 `sell_mode=rebalance_only` 를 지원하며, 이 경우 친구 프로젝트와 동일하게 리밸런싱 일자에만 종목 교체가 발생합니다.
> 다만 친구 프로젝트의 `StrategyEvaluator.evaluate_sell_decision()`은 **항상** 현 상태를 반환(개별 매도 안 함)하는 반면, 내 프로젝트는 `sell_mode` 설정값에 따라 동적으로 결정합니다.

### 2.2 포트폴리오 구성

| 항목 | 친구 | 나 |
|---|---|---|
| **자산 배분** | 5버킷 균등 (모멘텀/혁신/지수/배당/헷지) | 5버킷 가중 (P182-A, P185) |
| **버킷당 종목 수** | BUCKET_TOPN (1~2개) × 5버킷 = 5~10종목 | N=1/버킷 × 5버킷 = 5종목 (max_positions=4) |
| **리밸런싱** | DAILY / WEEKLY / TWICE_A_MONTH / MONTHLY / QUARTERLY | DAILY / W / M (P184-Fix: 月초 강제) |
| **교체 로직** | 보유 중 최저 점수 종목 → 미보유 최고 점수 종목으로 교체 | 모멘텀 탑1 선정 → `engine.rebalance()` |
| **슬리피지** | 국가별 차등 (한국 0.05%, 미국 0.025%) | 0.1% 고정 |

### 2.3 리스크 관리

| 항목 | 친구 | 나 |
|---|---|---|
| **손절** | 없음 (리밸런싱까지 보유) | stop_loss 임계값 매도 (rebalance_only 시 비활성) |
| **MDD 제한** | 없음 (백테스트 지표로만 사용) | 튜닝 시 MDD > 20% prune |
| **최대 낙폭** | 보고서에 표시 | 가드레일 시스템 (P160) |
| **방어 모드** | 5번째 버킷(대체헷지)이 방어 역할 | `enable_defense` 레짐 감지 + ADX Chop Filter |

---

## 3. 튜닝 시스템 비교 (v2 심층 분석)

| 항목 | 친구 | 나 (P167-R) |
|---|---|---|
| **방법** | **전수조사 (Grid Search)** | **Optuna TPE (베이지안 최적화)** |
| **병렬화** | `ProcessPoolExecutor` (CPU 코어 수만큼) | 단일 프로세스 (직접 호출) |
| **검색 공간** | MA_MONTH × MA_TYPE × BUCKET_TOPN = 최대 **144개** 조합 | momentum_period × stop_loss × max_positions 연속 공간 |
| **최적화 지표** | CAGR, SHARPE, SDR 중 선택 | `sharpe - 2.0·(mdd/100) - 0.0002·trades` |
| **결과 적용** | 계정 config.json에 자동 저장 | Cockpit "Apply Best Params" 버튼 |
| **캐시** | 프리페치 + MA 지표 캐시 (`_build_prefetched_metric_cache`) | 프리페치 + 디스크 parquet 캐시 |
| **멀티 기간** | 여러 `backtest_start_date`별 가중 평균 | 단일 기간 (quick 6M / full 3Y) |
| **중간 저장** | ✅ 1%마다 콜백으로 atomic save | ❌ 없음 |
| **디버그 내보내기** | ✅ `_export_debug_month` (상위 N개 조합 저장) | ❌ JSONL 텔레메트리만 |

> [!NOTE]
> **v2 심층 발견**: 친구의 `core/tune/runner.py`(1923줄!)는 단순 Grid Search가 아닙니다.
> - **멀티 기간 가중 합산**: 여러 `backtest_start_date`에 대해 각각 백테스트를 돌리고, 결과를 가중 평균하여 "특정 시점에만 잘 먹히는 파라미터"를 걸러냅니다.
> - **중간 저장 콜백**: 1%마다 `_save_intermediate_results()`로 atomic rename 저장 → 튜닝 중 크래시 시 손실 최소화.
> - **디버그 내보내기**: 상위 N개 조합의 전체 일별 기록을 CSV로 내보내 수동 검증 가능.
> - 이 3가지 기능은 우리 프로젝트에 바로 적용하면 좋을 아이디어입니다.

### 3.1 친구의 튜닝 검색 공간

```python
ACCOUNT_TUNING_CONFIG = {
    "kor_kr": {
        "BUCKET_TOPN": [2],                            # 1개 값
        "MA_MONTH": [1,2,3,4,5,6,7,8,9,10,11,12],     # 12개
        "MA_TYPE": ["SMA","EMA","WMA","DEMA","TEMA","HMA"],  # 6개
    },
}
# 총 조합: 1 × 12 × 6 = 72개 (계정당)
```

### 3.2 내 튜닝 검색 공간

```python
{
    "momentum_period": int [8, 60],   # 53개 값 (연속)
    "stop_loss":       float [-0.10, -0.01],  # 10개 (step=0.01)
    "max_positions":   int [2, 6],    # 5개 값
}
# 이론적 조합: 53 × 10 × 5 = 2,650개 → Optuna가 효율 탐색
```

---

## 4. 데이터 파이프라인 비교

| 항목 | 친구 | 나 |
|---|---|---|
| **데이터 소스** | yfinance + 네이버 금융 API (직접 구현 74KB) | FDR(P180) + yfinance 폴백 |
| **캐시 형식** | Apache Parquet (utils/cache_utils.py) | Parquet (data/cache/ohlcv/) |
| **프리페치** | `prepare_price_data()` → 전 종목 일괄 | `prefetch_ohlcv()` → 전 종목 일괄 |
| **인메모리 캐시** | Worker 글로벌 변수 + 프리페치 메트릭 캐시 | `_OHLCV_MEM_CACHE` 딕셔너리 |
| **거래일 캘린더** | ✅ `get_trading_days()` (정확한 영업일 판별) | ❌ 없음 (데이터에 있는 날짜 기준) |
| **환율 처리** | ✅ 미국 계정용 환율 시리즈 프리페치 | 없음 (한국 전용) |
| **NAV 괴리율** | ✅ 네이버 API로 실시간 NAV/괴리율 조회 | ❌ 없음 |

---

## 5. 체결/실행 엔진 비교 (v2 신규)

| 항목 | 친구 (`execution.py`) | 나 (`backtest.py`) |
|---|---|---|
| **체결 가격** | **익일 시가 + 슬리피지** (현실적) | **당일 종가 + 슬리피지** (다소 낙관적) |
| **매수/매도 분리** | `execute_rebalance_buy`/`sell` 별도 함수 | `engine.rebalance()` 통합 |
| **거래 기록** | `PortfolioState.trades` 리스트 (상세: 수익, 수익률, 잔여주) | `Portfolio.trades` 리스트 (Trade 데이터클래스) |
| **포지션 추적** | `avg_cost` 기반 가중평균 원가법 | `entry_price` 단일 진입가 |
| **거래 라벨** | `BUY`, `BUY_REBALANCE`, `SELL_REBALANCE` 구분 | `buy`/`sell` 2종류 |
| **일별 기록** | ✅ 종목별 `daily_records` (가격, 주수, PV, 점수, 신호) | P183: `trade_histogram_by_date` (날짜별 건수만) |

> [!IMPORTANT]
> **핵심 차이**: 친구 프로젝트는 **익일 시가**로 체결하므로 "오늘 신호 → 내일 매수"라는 현실적 시나리오를 반영합니다. 우리 엔진은 당일 종가 체결이라 약간의 look-ahead bias가 발생할 수 있습니다.

---

## 6. 추천/알림 시스템 (v2 신규)

| 항목 | 친구 (`recommend.py` 959줄) | 나 |
|---|---|---|
| **추천 생성** | 백테스트 마지막 날 결과를 자동 추출 | ❌ 없음 |
| **추천 로직** | 5-Bucket 선정 → 리밸런싱 결과 기반 순위 | — |
| **실시간 보강** | ✅ 네이버 API로 NAV/괴리율/실시간 가격 보강 | — |
| **기간별 수익률** | ✅ 1일/5일/20일/60일 수익률 자동 계산 | — |
| **보유일 계산** | ✅ 연속 보유일 수 산출 | — |
| **Slack 알림** | ✅ `notification.py` (18KB) 자동 발송 | — |
| **추천 저장** | JSON 로그 파일 → 히스토리 관리 | — |

> [!TIP]
> 친구의 `recommend.py`는 "백테스트 엔진을 매일 돌려서 마지막 날의 포지션 상태를 추천으로 변환"하는 패턴입니다. 이 방식은 별도의 실시간 신호 엔진 없이도 매일 추천을 생성할 수 있어 매우 실용적입니다.

---

## 7. 거래 관리 UI (v2 신규)

| 항목 | 친구 (`transactions_page.py` 501줄) | 나 |
|---|---|---|
| **거래 입력** | ✅ 4개 탭 (관리/일괄/현금/스냅샷) | ❌ 없음 |
| **일괄 입력** | ✅ CSV 복붙 → DataFrame 변환 → 저장 | — |
| **현금 관리** | ✅ 계정별 현금 잔고 수동 관리 | — |
| **포트폴리오 스냅샷** | ✅ 현재 포트폴리오 상태 저장/조회 | — |
| **종목 추가/수정** | ✅ 모달 다이얼로그 (add/edit) | — |

---

## 8. 아키텍처 비교

### 8.1 친구 프로젝트 구조

```
momentum-etf/                      # 총 ~630KB
├── tune.py            ← CLI: 튜닝 실행
├── backtest.py        ← CLI: 백테스트 실행
├── recommend.py       ← CLI: 매매 추천 + Slack (35KB)
├── app.py             ← Streamlit 대시보드 (33KB)
├── config.py          ← 전역 설정
├── core/
│   ├── backtest/
│   │   ├── engine.py     ← 백테스트 엔진 (59KB, 1325줄)
│   │   ├── runner.py     ← 계정별 백테스트 (44KB)
│   │   ├── execution.py  ← 체결 로직 (7KB)
│   │   ├── domain.py     ← 데이터 클래스 (4KB)
│   │   └── signals.py    ← 신호 생성 (1.5KB)
│   └── tune/
│       ├── runner.py     ← 전수조사 튜너 (72KB!, 1923줄)
│       └── worker.py     ← 멀티프로세스 워커 (5KB)
├── strategies/maps/      ← MAPS 전략 (11 파일)
│   ├── scoring.py        ← (Close/MA-1)×100 (1KB)
│   ├── rules.py          ← StrategyRules 데이터클래스 (4KB)
│   └── evaluator.py      ← 매도 평가 (항상 보유) (1.3KB)
├── app_pages/            ← Streamlit 멀티페이지
│   ├── account_page.py   ← 계정별 대시보드 (38KB)
│   ├── transactions_page.py ← 거래 관리 (22KB)
│   └── stocks.py         ← 종목 정보 (6KB)
├── utils/                ← 유틸리티 (23 파일, 370KB)
│   ├── data_loader.py    ← 데이터 수집 (74KB!)
│   ├── notification.py   ← Slack 알림 (18KB)
│   └── portfolio_io.py   ← 포트폴리오 I/O (18KB)
└── zaccounts/            ← 5개 계정 설정
```

### 8.2 내 프로젝트 구조

```
krx_alertor_modular/                # 총 ~250KB
├── app/
│   ├── run_backtest.py    ← CLI: 백테스트 (21KB)
│   ├── run_tune.py        ← CLI: Optuna 튜닝 (P167)
│   ├── backtest/
│   │   ├── runners/backtest_runner.py  ← 엔진 (34KB)
│   │   ├── engine/backtest.py         ← 체결 로직 (28KB)
│   │   └── infra/data_loader.py       ← 데이터+캐시
│   └── tuning/            ← Optuna 튜닝 (7 파일, P167-R)
├── backend/               ← FastAPI 백엔드 (OCI 연동)
├── pc_cockpit/cockpit.py  ← Streamlit Cockpit (57KB)
├── deploy/                ← OCI 배포 스크립트
├── tools/                 ← P181-R 신뢰성 검증 스크립트
└── state/                 ← SSOT 상태 파일
```

---

## 9. 친구 프로젝트에서 배울 점 (v2 업그레이드)

### 9.1 ⭐ 즉시 적용 가능 (우선순위 높음)

| 아이디어 | 설명 | 난이도 | 비고 |
|---|---|---|---|
| **익일 시가 체결** | 현재 당일 종가 체결 → 익일 Open으로 변경 | ⭐⭐ | bias 제거, 현실성 ↑ |
| **추천 시스템** | 백테스트 마지막 날 결과를 매매 추천으로 변환 | ⭐⭐⭐ | `recommend.py` 패턴 참조 |
| **거래 라벨 세분화** | BUY/SELL → BUY/BUY_REBALANCE/SELL_REBALANCE | ⭐ | P183 histogram 보강 |

### 9.2 ⭐⭐ 중기 적용 가능

| 아이디어 | 설명 | 난이도 | 비고 |
|---|---|---|---|
| **MA 타입 다양화** | SMA만 → EMA/HMA 등 추가 | ⭐⭐ | 튜닝 검색 공간 확장 |
| **멀티 기간 튜닝** | 여러 시작일에 대해 가중 백테스트 | ⭐⭐⭐ | 과적합 방지 핵심 |
| **Slack/Telegram 알림** | 매일 추천 결과 자동 발송 | ⭐⭐ | notification.py 참조 |
| **튜닝 중간 저장** | 1%마다 atomic save → 크래시 복구 | ⭐ | 즉시 적용 가능 |

### 9.3 ⭐⭐⭐ 설계 철학 차이점

| 관점 | 친구 | 나 | 비고 |
|---|---|---|---|
| **분산투자** | 5버킷 강제 분산 | 5버킷 가중 분산 (P185) | 이제 동등 |
| **매도 전략** | 리밸런싱까지 보유 | sell_mode 선택 가능 | 내 프로젝트가 유연 |
| **체결 모델** | 익일 시가 (현실적) | 당일 종가 (낙관적) | **친구가 우위** |
| **튜닝 방식** | 전수조사 (확실) | Optuna (효율) | 내 프로젝트가 확장성 ↑ |
| **운영 인프라** | GitHub Actions (클라우드) | OCI + Cockpit (하이브리드) | 나의 운영 가시성 ↑ |
| **텔레메트리** | 없음 | P183 거래 증거 + P181 신뢰성 검증 | **내 프로젝트가 우위** |
| **코드 크기** | ~630KB | ~250KB | 내 프로젝트가 가벼움 |
| **SSOT 체계** | 계정별 JSON 분산 | 단일 SSOT + SHA256 지문 | **내 프로젝트가 우위** |

---

## 10. 내 프로젝트 강점

| 강점 | 설명 |
|---|---|
| **SSOT 체계** | strategy_params → SHA256 지문 → 결과 JSON 역추적 (P185) |
| **가드레일** | LIVE/DRY_RUN/REPLAY 모드별 안전장치 (P160) |
| **거래 증거** | trade_histogram + reason_counts + cluster_check (P183) |
| **엔진 신뢰성** | 결정론성/캐시/교차검증 자동 스크립트 (P181-R) |
| **트리거 제어** | 레거시 룰 무시 + 월초 강제 (P184-Fix) |
| **OCI 연동** | 실시간 서버 동기화 + 원격 실행 |
| **Replay Mode** | 과거 날짜 기반 시스템 전체 재현 |
| **Optuna 튜닝** | 연속 파라미터 효율 탐색 + 프루닝 |
| **LLM 연동 UX** | 모든 탭에 LLM 복붙 블록 |

---

## 11. 핵심 수치 비교

| 지표 | 친구 (공개) | 나 (P185 2버킷 기준) |
|---|---|---|
| **CAGR** | 72.37% | 10.64% |
| **MDD** | -11.24% | -16.32% |
| **Sharpe** | 2.82 | 0.83 |
| **기간** | 12개월 | 3년 (full mode) |
| **종목 수** | ~50 ETF | 4 ETF |
| **총 체결** | 미공개 | 87건 (월초 집중 90.8%) |

> [!CAUTION]
> 직접 비교는 불가합니다. 기간이 다르고 (12개월 vs 3년), 유니버스 규모가 다르고 (50 vs 4), 시장 조건이 다릅니다.
> 친구의 수치는 최적 파라미터 기반 특정 계좌이고, 내 수치는 고정 SSOT 기반 전체 기간 결과입니다.
> 특히 3년 기간에는 2024-2025 하락장이 포함되어 있어 MDD가 더 크게 나옵니다.
