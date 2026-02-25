# 친구 프로젝트(momentum-etf) vs 내 프로젝트(krx_alertor_modular) 비교 분석

> 분석 기준일: 2026-02-25  
> 친구 프로젝트: `momentum-etf` (GitHub 소스)  
> 내 프로젝트: `krx_alertor_modular` (KRX Strategy Cockpit)

---

## 1. 프로젝트 개요 비교

| 항목 | 친구 (momentum-etf) | 나 (krx_alertor_modular) |
|---|---|---|
| **목적** | 5버킷 분산 ETF 모멘텀 자동매매 | KRX ETF 모멘텀 전략 + 운영 자동화 |
| **시장** | 🇰🇷 한국, 🇺🇸 미국, 🇦🇺 호주 (3개국) | 🇰🇷 한국 전용 |
| **계정** | 5개 (kor_kr, kor_isa, kor_pension, aus, us) | 1개 (단일 전략) |
| **유니버스 규모** | ETF 수십~수백 종목 (버킷당 동적) | 4종목 고정 (069500, 229200, 114800, 122630) |
| **알림** | Slack 자동 알림 (17KB notification.py) | Cockpit UI 수동 확인 |
| **배포** | GitHub Actions CI/CD + Docker | OCI 서버 + SSH Tunnel + 수동 Push |
| **UI** | Streamlit 대시보드 (app.py 25KB) | Streamlit Cockpit (cockpit.py 57KB) |
| **코드 규모** | ~260KB (core만) | ~100KB (app + backend) |

---

## 2. 전략 로직 비교

### 2.1 스코어링

| 항목 | 친구 (MAPS) | 나 (Momentum Score) |
|---|---|---|
| **핵심 공식** | `(Close / MA - 1) × 100` | 모멘텀 수익률 + RSI 필터 |
| **이동평균 종류** | 6종 (SMA, EMA, WMA, DEMA, TEMA, HMA) | 1종 (SMA만) |
| **MA 기간** | 1~12개월 (20~240 거래일) 탐색 | 8~60일 검색공간 |
| **매수 조건** | MAPS > 0 (MA 위에 있으면 매수) | 모멘텀 > entry_threshold + ADX 필터 |
| **매도 조건** | 리밸런싱 때만 교체 (추세 이탈해도 보유) | 모멘텀 < exit_threshold 즉시 매도 |

> [!IMPORTANT]
> 친구 프로젝트의 `StrategyEvaluator.evaluate_sell_decision()`은 항상 `(current_state, "")`를 반환합니다.
> 즉, **개별 종목 매도를 하지 않고 리밸런싱 시에만 교체**하는 전략입니다.  
> 반면 내 프로젝트는 `stop_loss` 임계값 돌파 시 즉시 매도합니다.

### 2.2 포트폴리오 구성

| 항목 | 친구 | 나 |
|---|---|---|
| **자산 배분** | 5버킷 균등 (모멘텀/혁신/지수/배당/헷지) | 단일 전략, 균등 비중 |
| **버킷당 종목 수** | BUCKET_TOPN (1~2개) × 5버킷 = 5~10종목 | max_positions (2~6개) |
| **리밸런싱** | DAILY / WEEKLY / TWICE_A_MONTH / MONTHLY / QUARTERLY | DAILY 고정 |
| **교체 로직** | 보유 중 최저 점수 종목 → 미보유 최고 점수 종목으로 교체 | 매도 후 빈자리에 신규 매수 |
| **슬리피지** | 국가별 차등 (한국 0.5%, 미국 0.25%) | 0.1% 고정 |

### 2.3 리스크 관리

| 항목 | 친구 | 나 |
|---|---|---|
| **손절** | 없음 (리밸런싱까지 보유) | stop_loss 임계값 매도 |
| **MDD 제한** | 없음 (백테스트 지표로만 사용) | 튜닝 시 MDD > 20% prune |
| **최대 낙폭** | 보고서에 표시 | 가드레일 시스템 (P160) |
| **방어 모드** | 5번째 버킷(대체헷지)이 방어 역할 | `enable_defense` 옵션 |

---

## 3. 튜닝 시스템 비교

| 항목 | 친구 | 나 (P167-R) |
|---|---|---|
| **방법** | **전수조사 (Grid Search)** | **Optuna TPE (베이지안 최적화)** |
| **병렬화** | `ProcessPoolExecutor` (CPU 코어 수만큼) | 단일 프로세스 (직접 호출) |
| **검색 공간** | MA_MONTH × MA_TYPE × BUCKET_TOPN = 최대 **144개** 조합 | momentum_period × stop_loss × max_positions 연속 공간 |
| **최적화 지표** | CAGR, SHARPE, SDR 중 선택 | `sharpe - 2.0·(mdd/100) - 0.0002·trades` |
| **결과 적용** | 계정 config.json에 자동 저장 | Cockpit "Apply Best Params" 버튼 |
| **캐시** | 프리페치 + MA 지표 캐시 (`_build_prefetched_metric_cache`) | 프리페치 + 디스크 parquet 캐시 |
| **멀티 기간** | 여러 `backtest_start_date`별 가중 평균 | 단일 기간 (quick 6M / full 3Y) |

> [!NOTE]
> 친구의 전수조사 방식은 검색 공간이 제한적(~144 조합)이므로 완전히 탐색 가능합니다.  
> 내 프로젝트의 Optuna TPE는 연속 파라미터(stop_loss 등)를 효율적으로 탐색하는 데 적합합니다.

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
| **데이터 소스** | yfinance + 네이버 금융 API (직접 구현 74KB) | yfinance + PyKRX + 네이버 금융 폴백 |
| **캐시 형식** | Apache Parquet (utils/cache_utils.py) | Parquet (data/cache/ohlcv/) |
| **프리페치** | `prepare_price_data()` → 전 종목 일괄 | `prefetch_ohlcv()` → 전 종목 일괄 |
| **인메모리 캐시** | Worker 글로벌 변수 + 프리페치 메트릭 캐시 | `_OHLCV_MEM_CACHE` 딕셔너리 |
| **거래일 캘린더** | 별도 `get_trading_days()` 함수 | 없음 (데이터 기준) |
| **환율 처리** | 미국 계정용 환율 시리즈 프리페치 | 없음 (한국 전용) |

---

## 5. 아키텍처 비교

### 5.1 친구 프로젝트 구조

```
momentum-etf/
├── tune.py            ← CLI: 튜닝 실행
├── backtest.py        ← CLI: 백테스트 실행
├── recommend.py       ← CLI: 매매 추천 + Slack
├── app.py             ← Streamlit 대시보드
├── config.py          ← 전역 설정
├── core/
│   ├── backtest/
│   │   ├── engine.py     ← 백테스트 엔진 (51KB)
│   │   ├── runner.py     ← 계정별 백테스트 (43KB)
│   │   └── ...           ← 분석/필터/포트폴리오
│   └── tune/
│       ├── runner.py     ← 전수조사 튜너 (69KB!)
│       └── worker.py     ← 멀티프로세스 워커
├── strategies/maps/      ← MAPS 전략 (11 파일)
├── utils/                ← 유틸리티 (23 파일, 370KB)
└── zaccounts/            ← 5개 계정 설정
```

### 5.2 내 프로젝트 구조

```
krx_alertor_modular/
├── app/
│   ├── run_backtest.py    ← CLI: 백테스트
│   ├── run_tune.py        ← CLI: Optuna 튜닝 (P167)
│   ├── backtest/
│   │   ├── runners/backtest_runner.py  ← 엔진
│   │   └── infra/data_loader.py       ← 데이터+캐시
│   └── tuning/            ← Optuna 튜닝 (7 파일, P167-R)
├── backend/               ← FastAPI 백엔드 (OCI 연동)
├── pc_cockpit/cockpit.py  ← Streamlit Cockpit (57KB)
├── deploy/                ← OCI 배포 스크립트
└── state/                 ← SSOT 상태 파일
```

---

## 6. UI/대시보드 비교

| 항목 | 친구 (app.py) | 나 (cockpit.py) |
|---|---|---|
| **프레임워크** | Streamlit | Streamlit |
| **탭 수** | 단일 페이지 + 멀티 뷰 | 9개 탭 |
| **전략 파라미터 편집** | JSON 파일 직접 수정 | UI 폼 + 즉시 저장 |
| **백테스트 실행** | CLI (`python backtest.py kor_kr`) | 버튼 클릭 → subprocess |
| **튜닝 실행** | CLI (`python tune.py kor_kr`) | 버튼 클릭 → subprocess |
| **결과 유지** | JSON + CSV 파일 | JSON (latest + snapshot) |
| **LLM 연동** | 없음 | LLM 복붙용 블록 (P138/P165/P167) |
| **운영 기능** | 없음 (CI/CD에 위임) | Operations 탭 (P144) + OCI Sync |

---

## 7. 친구 프로젝트에서 배울 점

### 7.1 즉시 적용 가능

| 아이디어 | 설명 | 적용 난이도 |
|---|---|---|
| **MA 타입 다양화** | SMA만 쓰는 대신 EMA/HMA 등 추가 | ⭐⭐ |
| **리밸런싱 주기 옵션** | DAILY 외에 WEEKLY/MONTHLY 선택지 | ⭐⭐ |
| **튜닝 자동 적용** | 최적 파라미터를 config에 자동 저장 | ⭐ (P168에서 UI 구현 완료) |
| **프리페치 메트릭 캐시** | MA/Score를 모든 기간×타입 조합으로 미리 계산 | ⭐⭐⭐ |

### 7.2 설계 철학 차이점 (장단점)

| 관점 | 친구 | 나 | 비고 |
|---|---|---|---|
| **분산투자** | 5버킷 강제 분산 | 단일 전략 | 친구가 우위 — 하락장 방어력↑ |
| **매도 전략** | 리밸런싱까지 보유 | 즉시 손절 | 상황에 따라. 친구: 과매도 방지 / 나: 하방 리스크 제한 |
| **튜닝 방식** | 전수조사 (확실) | Optuna (효율) | 내 프로젝트가 확장성↑ (파라미터 추가 시) |
| **운영 인프라** | GitHub Actions (클라우드) | OCI + Cockpit (하이브리드) | 나의 운영 가시성↑ |
| **코드 크기** | ~630KB 전체 | ~250KB 전체 | 친구가 기능 많음, 나는 가벼움 |

---

## 8. 내 프로젝트 강점

| 강점 | 설명 |
|---|---|
| **SSOT 체계** | strategy_bundle → params → portfolio 단일 진실 소스 |
| **가드레일** | LIVE/DRY_RUN/REPLAY 모드별 안전장치 (P160) |
| **OCI 연동** | 실시간 서버 동기화 + 원격 실행 |
| **Replay Mode** | 과거 날짜 기반 시스템 전체 재현 |
| **Optuna 튜닝** | 연속 파라미터 효율 탐색 + 프루닝 |
| **텔레메트리** | 튜닝 과정 JSONL 로깅 |
| **LLM 연동 UX** | 모든 탭에 LLM 복붙 블록 |

---

## 9. 핵심 수치 비교

| 지표 | 친구 (공개) | 나 (P167-R 테스트) |
|---|---|---|
| **CAGR** | 72.37% | 109.44% (best trial) |
| **MDD** | -11.24% | -6.37% |
| **Sharpe** | 2.82 | 3.41 |
| **기간** | 12개월 | 6개월 (quick mode) |
| **종목 수** | ~50 ETF | 4 ETF |

> [!CAUTION]
> 직접 비교 불가: 기간, 유니버스, 자본금, 시장 조건이 모두 다릅니다.  
> 친구의 수치는 10개 계좌 평균이고, 내 수치는 단일 trial의 best입니다.
