# 투자모델 구현 현황 (2025-12-10 기준)

## 1. 시스템 전반

| 영역           | 내용                                   | 구현 여부 | 파일/경로                                    | 메모 |
|----------------|----------------------------------------|-----------|----------------------------------------------|------|
| 데이터 수집    | pykrx 기반 ETF 가격 데이터 일별 수집   | ✅        | `infra/data/loader.py`                       | pykrx API 사용 |
| 데이터 캐싱    | Parquet 캐시 + PC/Cloud 동기화         | ✅        | `data/etf_cache.parquet`, `core/cache_store.py` | 90일 룩백 버퍼 |
| 유니버스       | ETF 유니버스 필터링 (거래량/거래대금)  | ✅        | `core/data/filtering.py`, `config/universe.yaml` | ~690개 ETF |
| 캘린더 가드    | 한국 휴장일 반영                       | ✅        | `core/calendar_kr.py`                        | exchange_calendars 사용 |
| 로그/가드      | 로깅 시스템                            | ✅        | `infra/logging/`, `app/cli/log_utils.py`     | Python logging |

## 2. 전략별 현황

### 2-1. 하이브리드 레짐 전략

| 항목                 | 내용                                   | 구현 여부 | 파일/경로                                    | 메모 |
|----------------------|----------------------------------------|-----------|----------------------------------------------|------|
| 레짐 정의            | MA50/200 기반 레짐 분류 (bull/bear/neutral) | ✅    | `core/strategy/market_regime_detector.py`    | 임계값 ±2% |
| 포지션 결정 로직     | 레짐별 포지션 비율 조절                | ✅        | `core/strategy/market_regime_detector.py`    | bull:1.0, neutral:0.8, bear:0.5 |
| 모멘텀 스코어        | MAPS (이동평균 대비 수익률)            | ✅        | `extensions/backtest/runner.py`              | ma_period 파라미터화 |
| RSI 비중 스케일링    | RSI 기반 종목별 비중 조절              | ✅        | `core/strategy/weight_scaler.py`             | YAML 프로파일 기반, Soft Normalize |
| 백테스트 엔진        | 매수/매도/NAV 계산                     | ✅        | `core/engine/backtest.py`                    | 거래비용 반영 |
| 백테스트 러너        | 모멘텀 기반 동적 종목 선정             | ✅        | `extensions/backtest/runner.py`              | Top N 리밸런싱 |
| 성과 지표 계산       | CAGR, Sharpe, MDD, 변동성, 승률 등     | ✅        | `core/engine/backtest.py`, `core/metrics/performance.py` | |
| 리포트/시각화        | HTML 리포트 생성                       | ✅        | `extensions/backtest/report.py`              | |

### 2-2. 리스크/이벤트 방어 로직

| 항목                 | 내용                                   | 구현 여부 | 파일/경로                                    | 메모 |
|----------------------|----------------------------------------|-----------|----------------------------------------------|------|
| 스탑로스             | 종목별 손절 (파라미터: -5%~-20%)       | ✅        | `extensions/backtest/runner.py`              | stop_loss 파라미터화 |
| 테이크 프로핏        | 종목별 익절                            | ❌        | -                                            | 미구현 |
| 시장 급락 감지       | 지수 급락 시 방어 모드 전환            | ✅        | `core/strategy/market_crash_detector.py`     | |
| 방어 시스템          | 변동성/추세 기반 방어                  | ✅        | `core/strategy/defense_system.py`            | |
| 변동성 관리          | 변동성 기반 포지션 조절                | ✅        | `core/strategy/volatility_manager.py`        | |
| 이벤트 캘린더        | FOMC, CPI 등 경제 일정 반영            | ❌        | -                                            | 미구현 |
| 미국 시장 모니터     | S&P500, VIX 등 미국 지표 모니터링      | ✅        | `core/strategy/us_market_monitor.py`         | |

## 3. 튜닝/최적화

| 항목                 | 내용                                   | 구현 여부 | 파일/경로                                    | 메모 |
|----------------------|----------------------------------------|-----------|----------------------------------------------|------|
| Optuna 튜닝          | 파라미터 자동 최적화                   | ✅        | `app/services/tuning_service.py`             | Sharpe 최대화 |
| 튜닝 변수 관리       | YAML 기반 변수 정의                    | ✅        | `config/backtest.yaml`                       | MA, RSI, 손절 등 |
| 최적 파라미터 저장   | JSON 파일 저장                         | ✅        | `app/services/optimal_params_service.py`     | `data/optimal_params.json` |
| Train/Val/Test 분할  | 70/15/15 비율 분할 검증                | ✅        | `app/services/backtest_service.py`           | run_with_split() |
| 과적합 경고          | Train→Test Sharpe 30%+ 저하 시 경고    | ✅        | `app/services/backtest_service.py`           | |
| 엔진 헬스체크        | 변동성0, 매도0, 비용0 등 검증          | ✅        | `core/engine/backtest.py`                    | engine_health |

## 4. API/UI

| 항목                 | 내용                                   | 구현 여부 | 파일/경로                                    | 메모 |
|----------------------|----------------------------------------|-----------|----------------------------------------------|------|
| 백테스트 API         | FastAPI 기반 백테스트/튜닝 API         | ✅        | `api_backtest.py`                            | Port 8001 |
| 분할 백테스트 API    | Train/Val/Test 분할 백테스트           | ✅        | `api_backtest.py` `/run-split`               | ExtendedBacktestResponse |
| 보유종목 API         | FastAPI 기반 포트폴리오 관리 API       | ✅        | `api_holdings.py`                            | Port 8000 |
| React 대시보드       | 웹 UI                                  | ✅        | `web/dashboard/`                             | Vite + React |
| 튜닝 UI              | Optuna 튜닝 인터페이스                 | ✅        | `web/dashboard/src/pages/Strategy.tsx`       | Train/Val/Test 비교 |
| 과적합 경고 UI       | Trial별 과적합/무효 상태 표시          | ✅        | `web/dashboard/src/pages/Strategy.tsx`       | 색상 구분 |

## 5. 자동화/운영

| 항목                 | 내용                                   | 구현 여부 | 파일/경로                                    | 메모 |
|----------------------|----------------------------------------|-----------|----------------------------------------------|------|
| Cloud 크론           | 매일 장후 알림/리포트 수행             | ✅        | `config/crontab.cloud.txt`                   | Oracle Cloud |
| 장시작 알림          | 09:00 텔레그램 알림                    | ✅        | `scripts/nas/market_open_alert.py`           | |
| 장중 알림            | 실시간 모니터링                        | ✅        | `scripts/nas/intraday_alert.py`              | |
| 일일 리포트          | 16:00 일일 리포트                      | ✅        | `scripts/nas/daily_report_alert.py`          | |
| 주간 리포트          | 토요일 주간 리포트                     | ✅        | `scripts/nas/weekly_report_alert.py`         | |
| 텔레그램 알림        | 텔레그램 봇 알림                       | ✅        | `infra/notify/telegram.py`                   | |
| Slack 알림           | Slack 웹훅 알림                        | ✅        | `infra/notify/slack.py`                      | |
| Oracle Cloud 동기화  | PC → Cloud 배포 스크립트               | ✅        | `scripts/sync/sync_to_oracle.sh`             | |
| DB 백업              | SQLite DB 백업                         | ✅        | `scripts/nas/backup_db.sh`                   | |

## 6. 데이터베이스

| 항목                 | 내용                                   | 구현 여부 | 파일/경로                                    | 메모 |
|----------------------|----------------------------------------|-----------|----------------------------------------------|------|
| SQLite DB            | 보유종목, 백테스트 히스토리 저장       | ✅        | `core/db.py`, `data/krx_alertor.db`          | |
| 백테스트 히스토리    | 백테스트 결과 저장                     | ✅        | `app/services/history_service.py`            | |

---

## 파라미터 연결 현황

| 파라미터       | 연결 상태 | 사용 위치                                    |
|----------------|-----------|----------------------------------------------|
| `ma_period`    | ✅        | `runner.py` → `_calculate_momentum_scores()` |
| `rsi_period`   | ✅        | `runner.py` → `_calculate_rsi()` → 비중 스케일링 |
| `stop_loss`    | ✅        | `runner.py` → 손절 매도 트리거               |
| `max_positions`| ✅        | `BacktestEngine` 생성자                      |

---

## 개발 로드맵 (2025-12-10 수립)

### Phase 0: 엔진 정합성 검증 (즉시)
| 항목 | 설명 | 상태 |
|------|------|------|
| 튜닝 결과 engine_health 검증 | 변동성0, 매도0, 비용0 등 이상 탐지 | ✅ 완료 |
| Train/Val/Test 분할 검증 | 과적합 경고 시스템 | ✅ 완료 |
| DB 히스토리 저장 | Train/Val/Test + engine_health 저장 | ✅ 완료 |

### Phase 1: 장기 백테스트 검증
| 항목 | 설명 | 상태 |
|------|------|------|
| 12개월+ 장기 백테스트 | 다양한 시장 국면 검증 | ⏳ 예정 |
| 2022~2024 하락장 검증 | Bear 시장 방어력 확인 | ⏳ 예정 |
| 거래비용 민감도 분석 | 슬리피지/수수료 영향 측정 | ⏳ 예정 |

### Phase 2: Walk-Forward 프레임워크
| 항목 | 설명 | 상태 |
|------|------|------|
| 롤링 윈도우 백테스트 | 6개월 Train → 1개월 Test 롤링 | ⏳ 예정 |
| Out-of-Sample 성능 추적 | 실제 예측력 측정 | ⏳ 예정 |
| 파라미터 안정성 점수 (PSS) | 인접 파라미터 성능 유사도 | ⏳ 예정 |

### Phase 3: TP/SL 시스템 고도화
| 항목 | 설명 | 상태 |
|------|------|------|
| Take Profit 구현 | ATR 기반 목표 수익률 익절 | ⏳ 예정 |
| Trailing Stop 구현 | 고점 대비 동적 손절 | ⏳ 예정 |
| 시간 기반 손절 | N일 후 수익 없으면 청산 | ⏳ 예정 |

### Phase 4: 고급 기능
| 항목 | 설명 | 상태 |
|------|------|------|
| Market Breadth 지표 | 상승/하락 종목 비율 분석 | ⏳ 예정 |
| Volatility Scaling | ATR 기반 변동성 역가중 | ⏳ 예정 |
| 이벤트 캘린더 | FOMC, CPI 등 경제 일정 반영 | ⏳ 예정 |
| 비중 히트맵 UI | UI에 비중 조절 시각화 | ⏳ 예정 |

---

## 최신 튜닝 결과 (2025-12-10)

| 항목 | 값 |
|------|-----|
| 기간 | 2025-09-11 ~ 2025-12-10 (3개월) |
| 최적 파라미터 | MA=20, RSI=17, stop_loss=-5% |
| CAGR | 48.68% |
| Sharpe | 4.02 |
| MDD | 3.23% |
| 총 거래 | 174회 |
| Train/Val/Test | 정상 (과적합 없음) |
| Engine Health | PASS |

> ⚠️ 3개월 백테스트는 짧음. Phase 1에서 12개월+ 장기 검증 필요.

---

## 미구현 항목 (Legacy)

## 비중 스케일링 파이프라인 (2025-12-10 구현)

```
① 모멘텀 기반 base weight (equal weight of top N)
    ↓
② RSI 스케일링 (종목 레벨) - YAML 프로파일 기반
    - RSI >= 80 → scale 0.0
    - RSI >= 70 → scale 0.5
    - RSI >= 60 → scale 0.8
    - RSI 40~60 → scale 1.0
    - RSI <= 30 → scale 1.2 (bull 레짐에서만)
    ↓
③ Soft Normalize
    - 합계 > 1.0 → 압축
    - 합계 <= 1.0 → 그대로 (부족분 cash)
    ↓
④ 레짐 스케일링 (포트폴리오 레벨)
    - bull: 1.0~1.2
    - neutral: 0.6~0.8
    - bear: 0.2~0.4
    ↓
⑤ 최종 비중 + Cash
```

**충돌 방지**: neutral/bear 레짐에서는 RSI boost (scale > 1.0) 비활성화

**관련 파일**:
- `config/rsi_profile.yaml` - RSI 프로파일 정의
- `core/strategy/weight_scaler.py` - 비중 스케일링 모듈
- `extensions/backtest/runner.py` - 백테스트 통합

---

## 디렉토리 구조 요약

```
krx_alertor_modular/
├── api_backtest.py          # 백테스트/튜닝 API (Port 8001)
├── api_holdings.py          # 보유종목 API (Port 8000)
├── app/services/            # 서비스 레이어
│   ├── backtest_service.py
│   ├── tuning_service.py
│   └── optimal_params_service.py
├── core/
│   ├── engine/backtest.py   # 백테스트 엔진
│   ├── strategy/            # 전략 모듈
│   │   ├── market_regime_detector.py
│   │   ├── market_crash_detector.py
│   │   └── defense_system.py
│   └── data/filtering.py    # 유니버스 필터링
├── extensions/backtest/
│   └── runner.py            # 백테스트 러너 (모멘텀/RSI/손절)
├── infra/
│   ├── data/loader.py       # 데이터 로더
│   └── notify/              # 알림 (텔레그램/Slack)
├── config/
│   ├── backtest.yaml        # 튜닝 변수 정의
│   └── regime_params.yaml   # 레짐 파라미터
├── scripts/
│   ├── nas/                 # 알림 스크립트
│   └── sync/                # Cloud 동기화
└── web/dashboard/           # React UI
```
