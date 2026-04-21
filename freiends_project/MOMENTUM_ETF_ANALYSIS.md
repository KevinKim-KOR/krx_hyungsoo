# 친구 프로젝트 분석: `momentum-etf-main`

> 분석 대상: `freiends_project/momentum-etf-main.zip` (압축 해제 후 `freiends_project/momentum-etf-main/`)
> 분석 시각: 2026-04-15 (정량 수치 정정: 2026-04-16 FIX1)
> 분석 목적: 친구가 개발한 모멘텀 ETF 시스템의 전반적 구조, 핵심 로직, UI 특징, 인프라 파악 — 이후 P211-STEP11A 진행 시 규칙 추출 근거 문서로 사용
>
> **정량 기준 (실측값)**:
> - 총 파일 수: **228 files**
> - Python 파일: **84 files / 18,070 LOC**
> - Web TypeScript/TSX 파일: **87 files / 13,819 LOC** (ts 44 files / 2,779 LOC + tsx 43 files / 11,040 LOC)
> - 코드 단순 합산: **31,889 LOC** (Python 18,070 + Web TS/TSX 13,819) + docker / 문서 / 설정 자원
>
> **Python LOC 상위 디렉토리**:
> - `utils/` : 35 files / **11,885 LOC** (최대 볼륨)
> - `scripts/` : 15 files / 2,928 LOC
> - `services/` : 8 files / 1,323 LOC
> - `fastapi_app/` : 16 files / 1,159 LOC
> - `core/` : 4 files / 389 LOC

---

## 목차

1. [한 줄 요약 & 프로젝트 포지셔닝](#1-한-줄-요약--프로젝트-포지셔닝)
2. [전체 시스템 아키텍처](#2-전체-시스템-아키텍처)
3. [핵심 전략 로직](#3-핵심-전략-로직)
4. [백엔드 상세 (FastAPI + services + utils)](#4-백엔드-상세-fastapi--services--utils)
5. [캐싱 & 데이터 파이프라인](#5-캐싱--데이터-파이프라인)
6. [백테스트 엔진](#6-백테스트-엔진)
7. [FastAPI REST API 엔드포인트](#7-fastapi-rest-api-엔드포인트)
8. [프론트엔드 (Next.js)](#8-프론트엔드-nextjs)
9. [UI/UX 상세 특징](#9-uiux-상세-특징)
10. [문서 (`docs/`) 분석](#10-문서-docs-분석)
11. [인프라 & 배포](#11-인프라--배포)
12. [데이터 모델 & MongoDB 스키마](#12-데이터-모델--mongodb-스키마)
13. [CI/CD & 자동화](#13-cicd--자동화)
14. [보안 & 운영](#14-보안--운영)
15. [현재 프로젝트(`krx_alertor_modular`)와의 비교](#15-현재-프로젝트krx_alertor_modular와의-비교)
16. [이식 가능 후보 (Phase 2 rule extraction 입력)](#16-이식-가능-후보-phase-2-rule-extraction-입력)

---

## 1. 한 줄 요약 & 프로젝트 포지셔닝

### 1.1 프로젝트 정체성

> **"추세에 순응하되, 위험은 철저히 관리한다"** — 이동평균(MA) 기반 다중 규칙 모멘텀 점수 + RSI 보조지표로 **다국가 ETF/주식 순위를 실시간 갱신**하고, 계좌별로 실제 보유 포트폴리오를 관리하며, 월/주간 리밸런싱 백테스트를 지원하는 **엔터프라이즈급 개인용 투자 의사결정 플랫폼**.

### 1.2 한국 / 미국 / 호주 3개국 대응

| 국가 | 거래소 | 데이터 소스 | 거래시간 (현지) |
|---|---|---|---|
| 한국 (KOR) | KOSPI/KOSDAQ | pykrx + Naver 금융 | 09:00-15:30 |
| 미국 (US) | NASDAQ/NYSE | yfinance | 09:30-16:00 |
| 호주 (AU) | ASX | yfinance + MarketIndex QuoteAPI | 10:00-16:00 |

### 1.3 운영 계좌 5종 (`zaccounts/*/config.json`)

- `1_kor_account` — 국내 일반 (KRW)
- `2_isa_account` — ISA 계좌
- `3_pension_account` — 연금 계좌
- `4_core_account` — 코어 포트폴리오
- `5_aus_account` — 호주 (AUD)

각 계좌는 여러 종목풀(`ticker_codes`)을 조합해 순위 산출 범위를 구성.

### 1.4 종목풀 4종 (`ztickers/*/config.json`)

| ID | 범위 | MA 규칙 예시 |
|---|---|---|
| `1_kor_kr` | 국내상장 국내 ETF | SMA 12개월 + ALMA 6개월 |
| `2_kor_us` | 국내상장 미국 ETF | 유사 |
| `3_aus` | 호주 ASX | 유사 |
| `4_us` | 미국 NYSE/NASDAQ | 유사 |

---

## 2. 전체 시스템 아키텍처

### 2.1 스택 요약

```
┌────────────────────────────────────────────────────┐
│ 사용자 브라우저 (https://etf.dojason.com)           │
└──────────────┬─────────────────────────────────────┘
               │ HTTPS (Let's Encrypt / acme)
               ▼
┌────────────────────────────────────────────────────┐
│ Oracle VM — Docker Compose                         │
│                                                     │
│  nginx-proxy (80/443)                              │
│       │                                             │
│       ├─► node_app  (Next.js 16 + React 19, :3000) │
│       │        │                                    │
│       │        ├─ Next.js API Routes (/api/*)      │
│       │        │    │ internal fetch                │
│       │        │    ▼                               │
│       │        │   fastapi_app (FastAPI, :8000)    │
│       │        │          │                         │
│       │        └── mongodb ◄─── services / utils   │
│       │              (127.0.0.1:27017)             │
│       │                                             │
│       └─► (fastapi_app 직접 노출은 없음)           │
└────────────────────────────────────────────────────┘

로컬 개발: SSH 터널 (autossh) 로 VM mongodb:27017 → localhost:27017 포워딩
```

### 2.2 디렉토리 레이아웃 (전체)

```
momentum-etf-main/
├── README.md                 # 프로젝트 소개
├── AGENTS.md                 # AI 협업 규칙 (한국어 우선, fallback 금지 등)
├── LICENSE
├── Dockerfile.fastapi
├── docker-compose.yml        # 4 service (mongodb + fastapi_app + node_app + hybrid_proxy)
├── docker-compose.hybrid.yml # 하이브리드 모드
├── pyproject.toml
├── requirements.txt          # 70개 deps
├── requirements-dev.txt
├── run_local_dev.py          # 로컬 dev 런처
│
├── config.py                 # 프로젝트 전역 상수 (버킷, 거래시간, MA 기본값)
│
├── core/
│   └── strategy/             # 전략 로직 핵심
│       ├── scoring.py        # 모멘텀 점수 공식 ((Close/MA) - 1) × 100
│       ├── metrics.py        # 종목별 메트릭 계산 + 7종 MA 지원
│       └── weight_allocator.py # 비중 할당 (min/max 가드레일 반복 정규화)
│
├── strategies/               # (현재 비어있음 — `__init__.py` 92 bytes 의 placeholder 모듈.
│                             #  주석: "거래 전략 컬렉션", 향후 전략 추가 예정 네임스페이스)
│
├── fastapi_app/
│   ├── main.py               # FastAPI 앱 팩토리 + 예외 핸들러 + 헬스체크
│   ├── dependencies.py       # X-Internal-Token 인증
│   └── routes/               # 12개 REST 라우터
│       ├── backtest.py       # 백테스트 CRUD + 실행
│       ├── rank.py           # 순위 조회 (MA 규칙 오버라이드 지원)
│       ├── holdings.py       # 실보유 종목 관리
│       ├── stocks.py         # 종목 마스터 CRUD
│       ├── assets.py         # 현금자산 관리
│       ├── dashboard.py      # 대시보드 요약
│       ├── snapshots.py      # 일일 스냅샷
│       ├── market.py         # FX / VKOSPI / 공포탐욕지수
│       ├── note.py           # 계좌 메모
│       ├── ticker_detail.py  # 종목 상세 (479 LOC — 가장 큼)
│       ├── weekly.py         # 주간 집계
│       └── system.py         # 시스템 정보 / 액션
│
├── services/                 # 외부 연동 일원화 레이어 (1,323 LOC)
│   ├── price_service.py      # 실시간 스냅샷 메모리 캐싱 (TTL)
│   ├── etf_holdings_service.py # ETF 구성종목 (Naver + Yahoo)
│   ├── etf_meta_service.py   # ETF 메타 (배당률/보수/순자산)
│   ├── fear_greed_service.py # CNN Fear & Greed
│   ├── vkospi_service.py     # 한국 변동성 지수
│   └── stock_cache_service.py # 종목 캐시 추상화
│
├── shared/
│   └── bucket_theme.json     # 버킷 색상 테마 (5 종)
│
├── utils/
│   ├── rankings.py           # 순위 생성 엔진 (500+ LOC)
│   ├── data_loader.py        # 다국가 가격 데이터 + 캐싱 (500+ LOC)
│   ├── cache_utils.py        # 3-tier 캐싱 (memory / MongoDB / API fallback)
│   ├── moving_averages.py    # 7종 MA (SMA/EMA/WMA/DEMA/TEMA/HMA/ALMA)
│   ├── indicators.py         # MA 신호 / RSI
│   ├── normalization.py      # 숫자 / 문자열 정규화
│   ├── backtest_service.py   # 백테스트 설정 + 실행 엔진
│   ├── db_manager.py         # MongoDB 연결 풀
│   ├── portfolio_io.py       # 포트폴리오 마스터 I/O
│   ├── notification.py       # Slack 전송
│   └── settings_loader.py    # 계좌/종목풀 설정 로더
│
├── scripts/                  # 15개 CLI/배치 (cron & GitHub Actions 에서 실행)
│   ├── stock_price_cache_updater.py  # 종가 캐시 갱신 (매시간)
│   ├── stock_meta_cache_updater.py   # 메타 캐시 갱신 (매일)
│   ├── portfolio_notifier.py         # Slack 포트폴리오 알림
│   ├── slack_asset_summary.py        # 자산 요약 Slack
│   ├── collect_investor_trend.py
│   ├── analyze_removed_ytd.py
│   ├── analyze_market_hours.py
│   ├── clear_cache.py
│   ├── debug_cache.py
│   ├── check_similar_tickers.py
│   └── migrate_*.py (4개)             # 데이터 마이그레이션
│
├── web/                      # Next.js 프론트엔드
│   ├── app/                  # Next.js 16 App Router
│   │   ├── AppShell.tsx      # 사이드바 + 메인 레이아웃
│   │   ├── page.tsx          # "/" 대시보드
│   │   ├── holdings/page.tsx
│   │   ├── assets/page.tsx
│   │   ├── stocks/
│   │   │   ├── page.tsx
│   │   │   └── StocksManager.tsx (51K - 순위 화면 전체 로직)
│   │   ├── ticker/
│   │   │   ├── page.tsx
│   │   │   └── TickerDetailManager.tsx (41K - 개별 종목 상세)
│   │   ├── note/page.tsx
│   │   ├── market/page.tsx
│   │   ├── snapshots/page.tsx
│   │   ├── weekly/page.tsx
│   │   ├── backtest/page.tsx
│   │   ├── system/page.tsx
│   │   ├── login/page.tsx    # Google OAuth
│   │   ├── api/              # Next.js API Routes (Python FastAPI 프록시)
│   │   └── components/       # AppAgGrid, ToastProvider, GlobalTickerSearch 등
│   ├── lib/                  # 19개 유틸 (mongo.ts, auth.ts, ...)
│   ├── globals.css           # 커스텀 변수 + Pretendard
│   └── package.json          # React 19.2 + Next.js 16 + AG Grid + lightweight-charts
│
├── static/                   # og-image.png, rank.txt
│
├── docs/
│   ├── project_overview.md   # 시스템 고수준 설계
│   ├── developer_guide.md    # 아키텍처 + 데이터 파이프라인 + UI 표준
│   ├── user_guide.md         # 사용자 가이드 (가장 긴 문서 8.3K)
│   ├── strategy_logic.md     # 순위 알고리즘 수학적 정의
│   ├── server_infrastructure.md # VM / 도메인 / nginx 가이드
│   └── mongodb.md            # Atlas → VM 마이그레이션 (9.7K, 가장 상세)
│
├── infra/
│   └── cron/
│       ├── crontab           # VM 내 cron 스케줄
│       └── run_batch.py      # 배치 래퍼 (Slack 알림 포함)
│
├── .github/workflows/        # 5개 CI/CD
│   ├── deploy.yml            # push upgrade → SSH → docker compose up
│   ├── cache_refresh.yml     # 매시간 종가 캐시
│   ├── metadata_updater.yml  # 매일 자정 메타 캐시
│   ├── asset_summary.yml     # 09:30 / 16:30 자산 요약 Slack
│   └── market_hours_analysis.yml # 07:00 장 시간 분석
│
├── zaccounts/                # 계좌 설정 5종
├── zcountry/                 # 국가별 거래일 캘린더 (kor/au/us) + README.md
│                             # - market_calendars.json 파일만 사용 (pandas_market_calendars 런타임 미사용)
│                             # - 범위: CACHE_START_DATE ~ 2026-12-31
│                             # - 2027년 이후 수동 갱신 필요
└── ztickers/                 # 종목풀 설정 4종 (MA_RULES 포함)
```

---

## 3. 핵심 전략 로직

### 3.1 모멘텀 점수 공식 (`core/strategy/scoring.py`)

**RANK (Moving Average Position Score)**:

```python
점수 = ((종가 / MA) - 1) × 100
```

- 종가 > MA → 양수 (상승 모멘텀)
- 종가 < MA → 음수 (하락)
- 종가 = MA → 0 (중립)

**예시**:
- 종가 121, MA 100 → **+21.0** (강한 상승)
- 종가 95, MA 100 → **−5.0** (약한 하락)

### 3.2 7종 이동평균 지원 (`utils/moving_averages.py`)

| 타입 | 공식 / 특성 | 데이터 요구 배수 |
|---|---|---:|
| **SMA** | 단순 이동평균 | 1.0× |
| **EMA** | 지수 가중 (`span=period, adjust=False`) | 2.0× |
| **WMA** | 선형 가중 (1, 2, ..., N) | 1.0× |
| **DEMA** | `2×EMA − EMA(EMA)` | 2.0× |
| **TEMA** | `3×EMA − 3×EMA² + EMA³` | 2.0× |
| **HMA** | Hull MA (고주파 반응) | 1.5× |
| **ALMA** | Arnaud Legoux (`offset=0.85, sigma=6.0`) | 1.0× |

### 3.3 데이터 충분성 검증 (`core/strategy/metrics.py`)

**완화 정책** — 신규 상장 종목 조기 포착을 위해 이상적 배수 부족 시 단계적 완화:

| MA 타입 | 이상적 | 불충분 시 완화 | 절대 최소 |
|---|---:|---:|---:|
| EMA/DEMA/TEMA | 2.0× | 1.0× | 5일 |
| HMA | 1.5× | 0.75× | 5일 |
| SMA/WMA | 1.0× | 0.5× | 5일 |

`MIN_TRADING_DAYS = 5` 이하면 **점수 계산 불가** (silent fallback 아님, 명시적 반환 None).

### 3.4 순위 생성 파이프라인 (`utils/rankings.py`)

```
종목풀 로드 (ztickers/*/config.json)
   ↓
캐시에서 종가 시계열 일괄 조회 (cache_utils)
   ↓
실시간 스냅샷 오버레이 (price_service — Naver/Yahoo/MarketIndex)
   ↓
종목별로:
 ├─ MA_RULES 순회 (예: order=1 SMA 12개월, order=2 ALMA 6개월)
 ├─ 각 규칙 점수 계산 (scoring.py)
 ├─ percentile 정규화 → "추세1", "추세2" 컬럼
 ├─ 최근 13개월 월간 수익률
 └─ RSI (14일)
   ↓
복합 점수 합산 (_build_composite_score)
   ↓
백분위 순위 산출
   ↓
메타 보강 (배당률/보수율/순자산/상장일)
   ↓
최종 DataFrame (정렬 내림차순)
```

**0 중심 부호 보존 백분위** — 상승/하락 구간을 별도 백분위로 계산해 부호를 유지 (`docs/strategy_logic.md`):
1. 종목풀 전체에 MA_RULES 적용
2. 0 중심 상승/하락 구간 구분
3. 각 구간 내 상대 순위(백분위) 계산, 부호 유지
4. 규칙별 부호 보존 점수 합산 → 최종 점수
5. MIN_TRADING_DAYS 미만은 계산 불가
6. 점수 내림차순 정렬

### 3.5 비중 할당 알고리즘 (`core/strategy/weight_allocator.py`)

**반복 정규화 with 가드레일**:

```python
def calculate_score_weights(
    scores: dict[str, float],
    *, min_weight=0.10, max_weight=0.30
) -> dict[str, float]:
```

**절차**:
1. 음수 점수 → 0 치환 (손실 종목 제거)
2. 양수 점수 비례 배분
3. 모든 종목에 `min_weight` 기본 할당
4. 남은 비중(`remaining`)을 점수 비례로 추가 배분
5. 상한 도달 종목 제외 후 재반복
6. 합계 100% 맞추기 미세 조정

**사전 검증**:
- 음수 min/max 거부
- `max < min` 거부
- `min_weight × N > 100%` (수학적 불가능) 거부
- `max_weight × N < 100%` (수학적 불가능) 거부

**재조정 판정** (`should_rebalance`):
- 현재 vs 목표 비중 차이 > 2% → 리밸런스 필요 표시

### 3.6 보유종목 강조 가점 (UI 전용)

`/stocks` 화면에서 실제 보유 종목(녹색 행)에 **0~50 범위 가점**을 5점 단위로 추가 가능. `localStorage.holdings_bonus_score` 에 저장 — 다음 방문에도 유지. **알고리즘 순위에는 영향 없음**, 화면 정렬 시각 편의.

---

## 4. 백엔드 상세 (FastAPI + services + utils)

### 4.1 FastAPI 앱 구조 (`fastapi_app/main.py` — 121 LOC)

```python
app = FastAPI(title="Momentum ETF Internal API")

# 11개 라우터 등록 (require_internal_token 의존성)
# 예외 핸들러:
#   ValueError → 400
#   RuntimeError → 500
#   FileNotFoundError → 500
#   Exception → 500

# MongoDB 타임아웃 미들웨어 → 503 Service Unavailable
# 헬스체크: GET /internal/health, POST /internal/health/report_error
```

### 4.2 인증 (`fastapi_app/dependencies.py` — 26 LOC)

```python
def require_internal_token(x_internal_token: str | None = Header(...)) -> None:
    # 환경변수 FASTAPI_INTERNAL_TOKEN 와 비교
    # 모든 /internal/* 엔드포인트에 Depends 로 적용
```

**외부 노출 없음** — Node.js Next.js 에서만 `X-Internal-Token` 헤더로 호출.

### 4.3 서비스 레이어 (`services/` — 1,323 LOC)

| 파일 | LOC | 역할 |
|---|---:|---|
| `price_service.py` | 319 | 실시간 가격 스냅샷 메모리 TTL 캐싱 (KOR 30s, AU 60s, idle 3600s, FX 3600s). fallback: stale cache 재사용 |
| `etf_holdings_service.py` | 535 | ETF 구성종목 (Naver + Yahoo), 300초 TTL |
| `etf_meta_service.py` | 116 | 배당률/보수율/순자산 |
| `fear_greed_service.py` | 96 | CNN Fear & Greed Index |
| `vkospi_service.py` | 99 | 한국 변동성 지수 |
| `stock_cache_service.py` | 90 | `meta_cache` / `holdings_cache` 추상화 |

**중요 설계**: 외부 API 호출은 **반드시** `services/` 를 거친다. 라우터/유틸에서 직접 호출 금지 (developer_guide.md 원칙).

### 4.4 주요 유틸리티 (`utils/` 총 **35 files / 11,885 LOC** — 프로젝트 최대 볼륨)

**실측 LOC 순 상위 파일**:

| 파일 | LOC | 역할 |
|---|---:|---|
| `data_loader.py` | **2,003** | 다국가 가격 데이터 + 거래일 + Naver/Yahoo/MarketIndex/환율 (단일 최대 파일) |
| `cache_utils.py` | 1,019 | 3-tier 캐싱 (memory / MongoDB Parquet / API fallback) |
| `portfolio_io.py` | 818 | 실보유 포트폴리오 I/O, `MissingPriceCacheError` 명시적 에러 |
| `rankings.py` | 817 | 순위 생성 엔진 (MA 규칙 정규화, 복합 점수, 메타 보강) |
| `backtest_service.py` | 650 | 백테스트 설정 CRUD + 실행 엔진 |
| `stock_list_io.py` | 638 | 종목 마스터 I/O (active/deleted, bucket 이동, 정렬) |
| `stock_meta_updater.py` | 629 | 배당률/보수율/순자산/상장일 등 메타 배치 갱신 |
| `holdings_detail_service.py` | 582 | 보유 상세 (평균매수가, 손익, 평가금액) |
| `stocks_service.py` | 525 | 종목 관리 비즈니스 로직 |
| `weekly_service.py` | 507 | 주간 집계 (수정 가능, 저장) |
| `kis_market.py` | 500 | KIS 증권 종목정보 마스터 파일 처리 |
| `moving_averages.py` | ~150 | 7종 MA (SMA/EMA/WMA/DEMA/TEMA/HMA/ALMA) |
| `indicators.py` | 67 | MA 신호 / RSI |
| `normalization.py` | 53 | 숫자/문자열 정규화 |
| `db_manager.py` | — | MongoDB 연결 풀 (`minPool=0, maxPool=10, idleTime=60s, selectionTimeout=10s`) |
| `notification.py` | — | Slack 전송 (`send_slack_message_v2`, 채널 `C0A0X2LTS3X`) |
| `settings_loader.py` | — | 계좌/종목풀 설정 로더 |

**주목할 점**:
- 단일 파일 `data_loader.py` 가 **전체 Python LOC 의 11%** 차지 (2,003 LOC). 다국가 데이터 소스 통합 책임이 한 파일에 응집됨
- `cache_utils` + `portfolio_io` + `rankings` + `backtest_service` 상위 4개 합산 **3,657 LOC** → `utils/` 의 31%
- `utils/` 전체가 사실상 **"비즈니스 로직 레이어"** 역할 (FastAPI 라우트는 얇은 어댑터)

---

## 5. 캐싱 & 데이터 파이프라인

### 5.1 3-tier 캐싱 전략

```
┌─────────────────────────────────────────────────┐
│ Tier 1: 메모리 캐시 (process-level)              │
│ _CLOSE_SERIES_MEMORY_CACHE                      │
│ 구조: (collection, ticker) → (updated_at, Series)│
│ 속도: ~5ms                                       │
└──────────────┬──────────────────────────────────┘
               │ miss
               ▼
┌─────────────────────────────────────────────────┐
│ Tier 2: MongoDB 캐시 (persistent)                │
│ cache_kor_stocks / cache_us_stocks 컬렉션        │
│ close_data: Binary (Parquet + snappy)           │
│ stale detection: updated_at 비교                 │
│ 속도: ~50-200ms                                  │
└──────────────┬──────────────────────────────────┘
               │ miss / stale
               ▼
┌─────────────────────────────────────────────────┐
│ Tier 3: 원천 API fallback                        │
│ - pykrx (한국)                                   │
│ - yfinance (미국/호주)                           │
│ - Naver 금융 (실시간)                            │
│ - MarketIndex QuoteAPI (호주)                    │
│ 속도: 수 초 ~ 수십 초                            │
└─────────────────────────────────────────────────┘
```

### 5.2 Parquet 채택 이유

**Pickle 버전 충돌 제거**:
- pandas / numpy / pyarrow 버전이 달라도 Parquet 은 상호 호환
- Python 런타임 3.9 ↔ 3.12 사이 이식 가능
- `pyarrow==21.0.0` 고정
- snappy 압축으로 저장 공간 최적화

### 5.3 실시간 데이터 오버레이

EOD(종가) 캐시 위에 **실시간 스냅샷을 덮어쓰기**:
- 현재가
- NAV (ETF 내재가치)
- 괴리율 (premium/discount)
- 일간 변동률

### 5.4 캐시 갱신 전략

| 갱신 주기 | 대상 | 트리거 |
|---|---|---|
| 매시간 정각 | 종가 캐시 | `cache_refresh.yml` (GitHub Actions) + VM cron |
| 매일 자정 | 메타 캐시 | `metadata_updater.yml` |
| 실시간 (요청 시) | 가격 스냅샷 | `price_service.py` TTL |

---

## 6. 백테스트 엔진

### 6.1 설정 관리 (`utils/backtest_service.py`)

**입력 스키마**:
```python
{
  "name": "코스피 모멘텀 12개월",
  "period_months": 12,            # 1-24
  "slippage_pct": 0.5,            # 0-100
  "benchmark": {
    "ticker": "069500",
    "name": "KODEX 200",
    "listing_date": "..."
  },
  "groups": [
    {
      "group_id": "group-1",
      "name": "모멘텀 그룹",
      "weight": 50,               # % (그룹 가중치)
      "tickers": [
        {"ticker": "069500", "name": "..."}
      ]
    }
  ],
  "rebalance_freq": "monthly"     # or "weekly"
}
```

**중복 감지**: 동일 `(name, period, slippage, groups, rebalance_freq)` 조합은 기존 `config_id` 반환 + `duplicated=True` 플래그.

### 6.2 실행 흐름

```python
def run_backtest(period_months, slippage_pct, benchmark, groups, country_code, rebalance_freq):
    1. ticker_type 결정 (AU → "aus", 나머지 → "kor_kr")
    2. 평가 기간 거래일 조회
    3. 재조정 날짜 계산:
       - monthly: 각 월 마지막 거래일
       - weekly: 각 주 마지막 거래일
    4. 재조정 날짜마다:
       a) 그룹별 종목 순위 계산 (rankings.py)
       b) 가중치 적용 (weight_allocator.py)
       c) slippage 반영 거래
       d) 현금/배당 처리
    5. 수익률 / 드로다운 / 샤프지수 계산
```

### 6.3 성능 특성

- **12개월 백테스트, 재조정 12회, 그룹 3개, 종목 30개**: 약 10~30초
- **순위 생성 단독** (종목 500개): 캐시 HIT 2~5초 / 캐시 MISS 20~60초

---

## 7. FastAPI REST API 엔드포인트

### 7.1 전체 라우트 목록 (12개 파일 / **40개 FastAPI 엔드포인트** — `@router.*` 데코레이터 기준)

| 라우터 | LOC | 엔드포인트 수 | 주요 기능 |
|---|---:|---:|---|
| `backtest.py` | 109 | 5 | 백테스트 설정 CRUD + 실행 + 검증 |
| `rank.py` | 34 | 1 | 순위 조회 (MA 규칙 오버라이드 쿼리스트링) |
| `holdings.py` | 86 | 6 | 실보유 종목 CRUD + 정렬 + 검증 |
| `assets.py` | 26 | 2 | 현금자산 조회/저장 |
| `dashboard.py` | 13 | 1 | 대시보드 요약 |
| `snapshots.py` | 13 | 1 | 일일 스냅샷 목록 |
| `stocks.py` | 112 | 8 | 종목 마스터 CRUD + 삭제 복구 |
| `market.py` | 40 | 4 | FX / VKOSPI / 공포탐욕 |
| `note.py` | 29 | 2 | 계좌 메모 |
| `ticker_detail.py` | **479** | 1 | 종목 상세 (가격 + 구성종목 + 메타) |
| `weekly.py` | 41 | 2 | 주간 집계 |
| `system.py` | 31 | 2 | 시스템 정보 + 액션 |

### 7.2 대표 엔드포인트

#### 백테스트
```
GET    /internal/backtest?config_id=<id>
POST   /internal/backtest
POST   /internal/backtest/run
POST   /internal/backtest/validate
DELETE /internal/backtest
```

#### 순위 (MA 규칙 동적 오버라이드)
```
GET /internal/rank?ticker_type=kor_kr&rule1_ma_type=EMA&rule1_ma_months=9
                                      &rule2_ma_type=SMA&rule2_ma_months=20
```
→ 쿼리스트링만으로 `MA_RULES` 오버라이드 가능 → UI 에서 즉시 재정렬.

#### 보유종목
```
GET    /internal/holdings?account=1_kor_account
POST   /internal/holdings
PATCH  /internal/holdings
DELETE /internal/holdings?account=...&ticker=...
PATCH  /internal/holdings/order
POST   /internal/holdings/validate
```

#### 시장 데이터
```
GET /internal/market
GET /internal/market/fx            # USD/KRW, AUD/KRW
GET /internal/market/vkospi
GET /internal/market/fear-greed    # CNN index
```

---

## 8. 프론트엔드 (Next.js)

### 8.1 스택 요약

| 항목 | 버전 | 비고 |
|---|---|---|
| React | 19.2.0 | 최신 |
| Next.js | 16.0.0 | App Router |
| TypeScript | 5.9 | |
| AG Grid Community | 35.2.0 | 순위/자산/ETF 마켓/주별 테이블 |
| Lightweight Charts | 5.1.0 | 캔들스틱 (일/주/월) |
| Recharts | 3.8.1 | 대시보드 비중 차트 |
| Tabler (CSS) | @tabler/core 1.4.0 | Bootstrap 기반 디자인 시스템 |
| @tabler/icons-react | 3.41.0 | 20+ 메뉴 아이콘 |
| MongoDB (Node.js) | 6.20.0 | API Routes 에서 직접 접근 |

**상태 관리**: Redux/Zustand 미사용. `useState` + `localStorage` 조합만. (Redux 복잡도 회피)

### 8.2 페이지 인벤토리 (13개)

| 경로 | 파일 | 목적 |
|---|---|---|
| `/` | `app/page.tsx` → `dashboard/` | 홈 — 핵심 지표 / 비중 / 계좌별 요약 / FX / VKOSPI / Fear & Greed |
| `/holdings` | `app/holdings/page.tsx` | 보유종목 — 전 계좌 통합 |
| `/assets` | `app/assets/page.tsx` | 자산 관리 — 수량 / 단가 / 목표비중 수정 |
| `/stocks` | `app/stocks/page.tsx` + `StocksManager.tsx` (51K) | **순위** — 시스템의 핵심 화면 |
| `/ticker` | `app/ticker/page.tsx` + `TickerDetailManager.tsx` (41K) | 개별 종목 상세 |
| `/note` | `app/note/page.tsx` | 계좌 메모 |
| `/market` | `app/market/page.tsx` | ETF 마켓 전체 조회 & 필터 |
| `/snapshots` | `app/snapshots/page.tsx` | 일일 스냅샷 |
| `/weekly` | `app/weekly/page.tsx` | 주간 집계 (수정 가능) |
| `/backtest` | `app/backtest/page.tsx` | 백테스트 설정 저장/조회 |
| `/system` | `app/system/page.tsx` | 앱 버전, 캐시 갱신 시각 |
| `/login` | `app/login/page.tsx` | Google OAuth |

### 8.3 Next.js API Routes (`web/app/api/`) — 총 **22개 route.ts**

Next.js 서버가 **중계 레이어** 로 동작 — 브라우저는 FastAPI 를 직접 호출하지 않음:

```typescript
// web/app/api/rank/route.ts (예시)
export async function POST(req: Request) {
  const { account, tickers, rules } = await req.json();
  const response = await fetch('http://fastapi_app:8000/internal/rank', {
    method: 'POST',
    headers: { 'X-Internal-Token': process.env.FASTAPI_INTERNAL_TOKEN },
    body: JSON.stringify({ account, tickers, rules }),
  });
  return Response.json(await response.json());
}
```

**전체 22개 route.ts 목록**:

| 경로 | 용도 |
|---|---|
| `api/assets/route.ts` | 자산/현금 조회·저장 |
| `api/auth/callback/google/route.ts` | Google OAuth 콜백 |
| `api/auth/google/start/route.ts` | Google OAuth 시작 |
| `api/auth/logout/route.ts` | 로그아웃 |
| `api/backtest/route.ts` | 백테스트 설정 CRUD |
| `api/dashboard/route.ts` | 대시보드 요약 |
| `api/deleted/route.ts` | 삭제 종목 조회/복구 |
| `api/fear-greed/route.ts` | CNN Fear & Greed |
| `api/fx/route.ts` | 환율 (USD/KRW, AUD/KRW) |
| `api/health/route.ts` | 헬스체크 |
| `api/market/route.ts` | ETF 마켓 전체 |
| `api/note/route.ts` | 계좌 메모 |
| `api/rank/route.ts` | 순위 산출 (MA 오버라이드) |
| `api/snapshots/route.ts` | 일일 스냅샷 |
| `api/stocks/route.ts` | 종목 마스터 CRUD |
| `api/stocks/refresh/route.ts` | 종목 캐시 새로고침 |
| `api/system/route.ts` | 시스템 정보·액션 |
| `api/ticker-detail/route.ts` | 종목 상세 |
| `api/ticker-search-data/route.ts` | 전역 검색용 데이터 |
| `api/ticker-tickers/route.ts` | 종목 리스트 |
| `api/vkospi/route.ts` | VKOSPI |
| `api/weekly/route.ts` | 주간 집계 |

### 8.4 `web/lib/` — 19개 Store/Util 모듈

| 파일 | 역할 |
|---|---|
| `accounts.ts` | 계좌 목록/선택 상태 |
| `auth.ts` | 인증 토큰 관리 |
| `backtest-store.ts` | 백테스트 설정 상태 |
| `bucket-theme.ts` | 버킷 색상/이름 |
| `dashboard-store.ts` | 대시보드 상태 |
| `deleted-stocks-store.ts` | 삭제 종목 상태 |
| `fear-greed.ts` | CNN 지수 유틸 |
| `internal-api.ts` | FastAPI 프록시 헬퍼 |
| `market-store.ts` | ETF 마켓 상태 |
| `mongo.ts` | Node MongoDB 드라이버 (부품 조립 URL) |
| `note-store.ts` | 메모 상태 |
| `python-runtime.ts` | Python 실행 경로 (dev 전환용) |
| `rank-store.ts` | 순위 상태 |
| `recent-ticker-searches.ts` | localStorage 검색 이력 |
| `snapshot-store.ts` | 스냅샷 상태 |
| `stocks-store.ts` | 종목 CRUD 상태 |
| `system-store.ts` | 시스템 정보 상태 |
| `ticker-detail-store.ts` | 종목 상세 상태 |
| `weekly-store.ts` | 주간 집계 상태 |

---

## 9. UI/UX 상세 특징

### 9.1 레이아웃

```
┌─[사이드바 11rem]───┐┌──[메인 콘텐츠]─────────────────────┐
│  dark #1f2937     ││  ┌──[헤더]────────────────────────┐│
│                   ││  │ 메뉴명 / 계좌 / 검색 / 액션     ││
│  홈               ││  └────────────────────────────────┘│
│  자산              ││                                    │
│  종목 ★           ││  ┌──[본문 (AG Grid / 차트 등)]────┐│
│  메모              ││  │                                ││
│  백테스트          ││  │                                ││
│  ETF 마켓          ││  │                                ││
│  시스템            ││  └────────────────────────────────┘│
│  ───              ││                                    │
│  FX               ││  ┌──[푸터]────────────────────────┐│
│  VKOSPI           ││  └────────────────────────────────┘│
│  Fear & Greed     ││                                    │
└───────────────────┘└────────────────────────────────────┘
```

**사이드바**:
- 다크 모드 (`#1f2937`)
- 너비 `11rem` 고정, collapse 가능
- 하단에 FX / VKOSPI / Fear & Greed 미니 위젯

**전역 헤더**:
- 계좌 선택 드롭다운
- 전역 종목 검색 (자동완성, 최근 검색, 급상승 목록 3종)
- 페이지별 보조 액션 (추가/저장/삭제)

### 9.2 순위 화면 (`/stocks`) — 시스템의 핵심

**기능 조합**:

| 기능 | 동작 |
|---|---|
| **추세1/추세2 변경** | MA_TYPE, MA_MONTHS 독립 변경 → **즉시** 점수/정렬 갱신 |
| **모드 토글** | 순위 모드 / 관리 모드 (종목 추가·삭제) |
| **실보유 강조** | 녹색 행 |
| **현재가 / 일간 %** | 캐시 스냅샷 + 실시간 업데이트 |
| **RSI / 추세 차트** | Lightweight Charts 미리보기 |
| **컬럼 전환** | 누적수익률 / 월별수익률 / 정보(배당률/보수/순자산/상장일) |
| **정렬** | 기본 점수 내림차순, 다른 컬럼으로 사용자 정렬 가능 (알고리즘 순위 유지) |
| **보유 가점** | 녹색 행에 0~50 가점 5단위 (localStorage 저장) |

### 9.3 개별 종목 상세 (`/ticker`)

| 기능 | 설명 |
|---|---|
| **캔들스틱** | Lightweight Charts — 일/주/월 선택 + 거래량 + MA(5/20/60/120) |
| **고점/저점 등락률** | 현재 보이는 범위 내 고점/저점 대비 |
| **구성종목 패널** | 한국 ETF — 종목코드/명/현재가/일간%/비중 |
| **해외 구성종목** | Yahoo Finance 실시간 (메모리 TTL) |
| **미국 종목풀 추가** | ➕ 아이콘 → 즉시 추가 + 토스트 |
| **일별/월별 시세** | CACHE_START_DATE부터 최신까지 |
| **캐시 완료 시각** | "2026-04-09(목) 오전 9:10 기준" 표시 |

### 9.4 CSS 변수 & 타이포그래피

```css
--bg: #f6f8fb
--panel: #ffffff
--ink: #182433
--muted: #667382
--line: #dce1e7
--accent: #206bc4          /* 파랑 */
--accent-soft: rgba(32,107,196,0.08)
```

헤더 높이: `2.585rem` (≈41px)

**폰트**:
```
"Pretendard", "Noto Sans KR", "Apple SD Gothic Neo",
"Malgun Gothic", "Segoe UI", sans-serif
```

### 9.5 공통 페이지 구조 (`docs/developer_guide.md §6`)

```
┌─[1. 메뉴 헤더]─────────────────────────────────────────┐
│  좌: 메뉴명                   우: 총 개수 / 선택 개수    │
├─[2. 메인 헤더]─────────────────────────────────────────┤
│  좌: 계좌 선택 / 보기 토글 / 검색필터                   │
│  우: 특별 버튼 (금액 가리기 등)                          │
├─[3. 보조 액션 헤더]────────────────────────────────────┤
│                           우 정렬: 추가 / 저장 / 삭제    │
├─[4. 테이블 / 그리드]───────────────────────────────────┤
│  카드 내부 스크롤 / 헤더 클릭 정렬                      │
└──────────────────────────────────────────────────────────┘
```

---

## 10. 문서 (`docs/`) 분석

### 10.1 문서 6종 요약

| 파일 | 크기 | 핵심 인사이트 |
|---|---:|---|
| `README.md` | 3.5K | "추세에 순응하되, 위험은 철저히 관리" — 프로젝트 한줄 철학 |
| `AGENTS.md` | 4.2K | AI 협업 규칙 8가지 — 한국어 우선 / 100% 이해 후 코드 / fallback 금지 / `znotes/` 보호 / Dockerfile 영향 확인 |
| `project_overview.md` | 2K | Parquet 캐싱으로 버전 충돌 해결 / 서비스 계층 일원화 |
| `developer_guide.md` | 5.7K | 종목 캐시 = 가격 캐시 + 메타 캐시 / 외부 연동은 `services/` 로 / UI 3단 표준 |
| `user_guide.md` | 8.3K | 설치 / 계좌 설정 / 추세1·추세2 즉시 갱신 / 캐시 갱신 |
| `strategy_logic.md` | 1.1K | MA_RULES 필수 / 0 중심 백분위 부호 보존 / fallback 금지 |
| `server_infrastructure.md` | 1.5K | 도메인 `etf.dojason.com` / nginx-proxy / acme |
| `mongodb.md` | 9.7K | Atlas → VM 마이그레이션 (2026-04-10) / SSH 터널 / 환경변수 부품 조립 |

### 10.2 AGENTS.md — AI 협업 규칙 (매우 중요)

```
1. 모든 응답은 한국어
2. 100% 이해할 때까지 질문
3. 코드 주석 한국어
4. 질문 시 먼저 답변, 그 후 수정 제시
5. 명시적 수정 요청 시 코드 먼저 (계획 문서 후순)
6. 작업 전 docs/ 읽기
7. znotes/ 는 사용자 메모 (명시 지시만)
8. 리팩토링 시 Dockerfile/배포 스크립트 영향 확인
```

**암묵적 fallback 금지, 명시적 에러만 사용** — 현재 `krx_alertor_modular` 의 rule 6/7 과 동일한 철학.

### 10.3 `mongodb.md` — 마이그레이션의 실전 기록

- **배경**: Atlas 무료 티어 → Oracle VM 자체 호스팅 (2026-04-10)
- **환경변수 변경**:
  - 기존: `MONGO_DB_CONNECTION_STRING` 단일값
  - 신규: `MONGO_DB_USER / PASSWORD / HOST / NAME` 부품 조립
  - 코드는 두 방식 모두 지원 (롤백 가능)
- **로컬 접근**: `autossh -M 0 -N -i ~/.ssh/... -L 27017:localhost:27017 ubuntu@134.185.109.82`
- **VM 접근**: `docker network` 내 hostname `mongodb:27017` (외부 노출 X)
- **백업**: `mongodump` / `mongorestore` 예시 포함. 자동 백업은 TODO

---

## 11. 인프라 & 배포

### 11.1 Docker Compose 서비스 (4종)

| 서비스 | 이미지 | 포트 | 역할 |
|---|---|---|---|
| `mongodb` | `mongo:7.0` | `127.0.0.1:27017` | DB (외부 미노출) |
| `fastapi_app` | 자체 빌드 (`Dockerfile.fastapi`) | `8000` (expose) | Python FastAPI |
| `node_app` | 자체 빌드 (`web/Dockerfile`) | `3000` (expose) | Next.js 프론트 |
| `hybrid_proxy` | `nginx:1.27-alpine` | `80/443` | 리버스 프록시 + SSL |

**통신**:
- 외부 → nginx-proxy → `node_app`
- `node_app` → `FASTAPI_INTERNAL_URL=http://fastapi_app:8000` (Docker 네트워크 DNS)
- `fastapi_app` → `mongodb:27017` (내부)

### 11.2 환경변수 (MongoDB 부품 조립)

```bash
# 앱 접근
MONGO_DB_USER=jasonisdoing
MONGO_DB_PASSWORD=<비밀번호>
MONGO_DB_HOST=localhost:27017           # 로컬: SSH 터널
MONGO_DB_NAME=momentum_etf_db

# VM .env 에만
MONGO_DB_ROOT_USER=root
MONGO_DB_ROOT_PASSWORD=<32자 랜덤>

# FastAPI 내부 토큰
FASTAPI_INTERNAL_TOKEN=<랜덤>
FASTAPI_INTERNAL_URL=http://fastapi_app:8000

# Slack
SLACK_BOT_TOKEN=<xoxb-...>
SLACK_CHANNEL=C0A0X2LTS3X
```

**코드 로직** (`utils/db_manager.py`, `web/lib/mongo.ts`):
1. `MONGO_DB_CONNECTION_STRING` 있으면 그대로 사용 (롤백 지원)
2. 없으면 부품 조립
3. `*.mongodb.net` 끝 → `mongodb+srv://`, 아니면 `mongodb://`
4. `authSource=admin` 자동 추가

### 11.3 MongoDB 연결 풀

```
minPoolSize: 0
maxPoolSize: 10
maxIdleTimeMS: 60000
waitQueueTimeoutMS: 15000
serverSelectionTimeoutMS: 10000
connectTimeoutMS: 10000
```

**타임아웃 감지 & 상태 리포팅**:
- 미들웨어에서 `PyMongoError` 캐치
- `/internal/health/report_error` 엔드포인트로 수동 보고
- 1분 내 타임아웃 기록 있으면 `/internal/health` 503 반환

---

## 12. 데이터 모델 & MongoDB 스키마

### 12.1 주요 컬렉션

#### `cache_kor_stocks` / `cache_us_stocks` — 가격 캐시

```python
{
  "ticker": str,
  "close_data": Binary,           # Parquet + snappy
  "close_column": str,            # "Close" 또는 "unadjusted_close"
  "close_row_count": int,
  "updated_at": datetime,
  "meta_cache": {                 # 선택
    "dividend_yield_ttm": float,
    "expense_ratio": float,
    "total_net_assets": str,
    "listed_date": str,
  },
  "holdings_cache": {...}         # ETF 구성종목 (선택)
}
```

#### `cache_refresh_status` — 갱신 추적
```python
{
  "collection": str,
  "last_updated_at": datetime,
}
```

#### `backtest_configs` — 백테스트 설정
```python
{
  "config_id": "bt_<uuid>",
  "name": str,
  "period_months": int,
  "slippage_pct": float,
  "benchmark": {...},
  "rebalance_freq": "monthly" | "weekly",
  "groups": [...]
}
```

#### `portfolio_master` — 실포트폴리오
```python
{
  "account_id": str,               # 1_kor_account 등
  "date": str,
  "cash": float,                   # 통화는 계좌에 따름
  "holdings": [
    {
      "ticker": str,
      "quantity": float,
      "average_buy_price": float,
      "memo": str,                 # 선택
    }
  ]
}
```

#### `stock_meta` — 종목 마스터
```python
{
  "ticker": str,
  "name": str,
  "country_code": str,
  "bucket_id": int,                # 1~5 (모멘텀/시장/배당/헷지/현금)
  "status": "active" | "deleted",
  "created_at": datetime,
}
```

### 12.2 버킷 체계 (`shared/bucket_theme.json`)

| ID | 이름 | 색상 |
|---:|---|---|
| 1 | 모멘텀 | `#e74c3c` (빨강) |
| 2 | 시장지수 | `#3498db` (파랑) |
| 3 | 배당방어 | `#2ecc71` (초록) |
| 4 | 대체헷지 | `#f39c12` (주황) |
| 5 | 현금 | `#95a5a6` (회색) |

---

## 13. CI/CD & 자동화

### 13.1 GitHub Actions (5개 워크플로우)

| 워크플로우 | 트리거 | 작업 | 실패 알림 |
|---|---|---|---|
| `deploy.yml` | push `upgrade` 브랜치 | SSH → VM → `git reset --hard` → `docker compose up -d --build` | Slack |
| `cache_refresh.yml` | `0 * * * *` (매시간) | `stock_price_cache_updater.py` | Slack |
| `metadata_updater.yml` | `0 0 * * *` (매일 자정) | `stock_meta_cache_updater.py` | Slack |
| `asset_summary.yml` | `30 0,7 * * *` (KST 09:30, 16:30) | `slack_asset_summary.py` | Slack |
| `market_hours_analysis.yml` | `0 22 * * *` (KST 07:00) | `analyze_market_hours.py --slack` | Slack |

### 13.2 VM 내부 Cron (`infra/cron/crontab`)

| 시간 | 작업 | 래퍼 | 로그 |
|---|---|---|---|
| 매시간 | 주가 캐시 | `run_batch.py cache_refresh ...` | `logs/cron/cache_refresh.log` |
| 매일 09:00 KST | 메타 업데이트 | `run_batch.py metadata_updater ...` | `logs/cron/metadata_updater.log` |
| 매일 09:30/16:30 KST | 자산 요약 Slack | `run_batch.py asset_summary ...` | `logs/cron/asset_summary.log` |
| 매일 07:00 KST | 장시간 분석 | `run_batch.py market_hours_analysis ...` | `logs/cron/market_hours_analysis.log` |

**래퍼 역할** (`infra/cron/run_batch.py`): 스크립트 실행 + 결과 Slack 통지 + 디스크 여유 리포트.

---

## 14. 보안 & 운영

### 14.1 인증

| 항목 | 방식 |
|---|---|
| 사용자 인증 | Google OAuth (web/app/api/auth/) |
| 토큰 저장 | `localStorage.auth_token` |
| 내부 API | `X-Internal-Token` 헤더 (Node → FastAPI) |
| MongoDB | root + app 유저 분리 |
| SSH | 키 기반만 (`~/.ssh/ssh-key-2025-10-09.key`) |

### 14.2 데이터 보호

- MongoDB 포트 `127.0.0.1:27017` 바인딩 → 외부 미노출
- SSH 터널 필수 (로컬 개발)
- `.env` 는 `.gitignore`
- Docker 내부 네트워크 — 외부 API 호출은 `fastapi_app` 만 수행
- Atlas 최종 스냅샷 gzip 백업 + VM 수동 백업

### 14.3 운영 TODO

- ❌ 주기적 백업 자동화 (cron 권장)
- ❌ VM 디스크 모니터링 (size tracking)

---

## 15. 현재 프로젝트(`krx_alertor_modular`)와의 비교

### 15.1 공통점

| 축 | 공통 |
|---|---|
| 철학 | 추세/모멘텀 기반, 위험 관리 |
| 언어 | Python 백엔드 + MongoDB (친구) / Python + JSON 파일 SSOT (우리) |
| 금지 규칙 | silent fallback 금지, 명시적 에러 (rule 6/7 ≡ `docs/strategy_logic.md` "fallback 금지") |
| 한국 시장 | pykrx / Naver 활용 |
| 문서 관습 | 한국어 우선 / AGENTS.md / docs/ 구조화 |
| ETF 중심 | 둘 다 ETF 우선 대상 |

### 15.2 차이점

| 축 | 친구 프로젝트 | 현재 프로젝트 |
|---|---|---|
| **목적** | 실제 투자 의사결정 + 자동 포트폴리오 관리 | 백테스트/튜닝/증빙 연구 플랫폼 |
| **대상** | 3개국 (KOR/US/AU) | 한국 KRX ETF 중심 |
| **프론트엔드** | Next.js 16 + React 19 + AG Grid + Lightweight Charts | Streamlit (pc_cockpit) + FastAPI 정적 mount (dashboard) |
| **저장소** | MongoDB (가격 Parquet + 메타/포트폴리오 JSON) | JSON 파일 SSOT + reports/ 디렉토리 |
| **전략 축** | MA 7종 × 다중 규칙 (추세1/추세2) × percentile 부호 보존 | 모멘텀 44일 + 변동성 19일 + ADX 20 + regime + guard + ML classifier (Track B) |
| **백테스트** | 월간/주간 재조정, 설정 저장소 + 실행 | 전략 sweep + Tune + Evidence + Drawdown attribution + Track A/B 실험 프레임 |
| **실시간** | Naver/Yahoo/MarketIndex 스냅샷 TTL | 없음 (research only) |
| **알림** | Slack 자산 요약 / 실패 통지 / 포트폴리오 알림 | 백엔드 경고 / evidence writer |
| **자동화** | GitHub Actions + VM cron 통합 | 수동 실행 (Streamlit 워크플로우) + 일부 스케줄 |
| **개별 종목 분석** | 캔들 / 구성종목 / 일별·월별 시세 / RSI | 종목 필터링 (scanner) + drawdown attribution |
| **유저 목적** | 본인 투자 운영 | 전략 검증 / 승격 의사결정 |

### 15.3 아키텍처 철학 대비

**친구 프로젝트 = "투자자용 대시보드"**
- 프론트엔드 중심 (Next.js 16 + AG Grid + Lightweight Charts)
- 실시간 데이터 오버레이
- 사용자 조작 (추세1/추세2 즉시 갱신) 이 핵심 경험
- 의사결정 지원 + 포트폴리오 추적

**현재 프로젝트 = "전략 연구 워크벤치"**
- 백엔드 / 데이터 파이프라인 중심
- 정적 evidence + canonical state 중심
- 백테스트 / 튜닝 / ML 실험이 핵심 경험
- 승격 여부 판정 + 문서화

---

## 16. 이식 가능 후보 (Phase 2 rule extraction 입력)

> 이하는 **P211-STEP11A-FRIEND-SOURCE-RULE-EXTRACTION-V1 진입 시 참고용 후보 목록**입니다.
> **직접 이식 금지** — 반드시 추출·분석·타당성 평가 단계를 거쳐야 함.

### 16.1 전략 로직 관점 — 이식 가능성 "상"

| 후보 | 출처 | 우리 측 이식 위치 후보 | 예상 효과 |
|---|---|---|---|
| **7종 MA (특히 ALMA / HMA)** | `utils/moving_averages.py` | `app/backtest/strategy/` 의 momentum 계산 | 기존 SMA 기반 모멘텀에 HMA/ALMA 반응성 옵션 |
| **0 중심 부호 보존 백분위 점수** | `docs/strategy_logic.md` + `utils/rankings.py` | scanner scoring / selection rank | 현재 raw score 기반 + 순위 비교 대비 통계적 안정성 |
| **MA 규칙 다중 조합 (추세1 + 추세2)** | `ztickers/*/config.json` `MA_RULES` | strategy_params 확장 | 단일 momentum_period → 다중 규칙 ensemble |
| **데이터 충분성 단계적 완화** | `core/strategy/metrics.py` | `app/backtest/data/` | 신규 상장 조기 포착 |
| **가드레일 비중 할당 (min/max 반복 정규화)** | `core/strategy/weight_allocator.py` | `app/backtest/allocation/` (P207 risk_aware_equal_weight 대안) | 현재 floor/cap 단순 클립보다 안정적 수렴 |
| **월간 수익률 13개월 시계열 특징** | `utils/rankings.py` `get_recent_monthly_return_labels` | Track B predictive risk feature set | 현재 14-feature set 에 월간 수익률 curve 추가 후보 |

### 16.2 UI/UX 관점 — 이식 가능성 "중~하"

> 지시문상 "UI 대격변 금지". 참고만.

| 후보 | 의미 |
|---|---|
| AG Grid 기반 정렬/필터 UX | Streamlit dataframe 한계 보완 시 참고 |
| Lightweight Charts 캔들 | 현재 pc_cockpit 에 종목 상세 화면 없음 — 추후 필요 시 |
| 계좌/종목풀 분리 개념 | 향후 실운영 계좌 관리가 들어오면 계층 설계 참고 |
| 3단 페이지 헤더 표준 | UI 재설계 (P211-STEP11B) 시 참고 |

### 16.3 인프라 / 운영 관점 — 이식 가능성 "중"

| 후보 | 의미 |
|---|---|
| Parquet 기반 가격 캐시 | 현재 프로젝트의 JSON/CSV 캐시를 Parquet 으로 통일 고려 |
| 3-tier 캐싱 (memory → DB → API) | 현재 reports/ 파일 기반과 비교 검토 |
| Slack 자산 요약 배치 | 운영 전환 시 알림 채널 참고 |
| 환경변수 부품 조립 방식 | 배포 다양성 확보 참고 |

### 16.4 절대 이식하면 안 되는 것

| 항목 | 이유 |
|---|---|
| **MongoDB 자체 호스팅** | 현재 프로젝트 SSOT 는 JSON 파일. 상태 저장소 전환은 거대한 변경 |
| **Google OAuth 인증** | 현재 프로젝트는 단일 사용자 연구 환경 |
| **Next.js 프론트엔드** | Streamlit + FastAPI 정적 mount 를 뒤집는 건 Phase 3 이후 결정 |
| **실시간 Naver/Yahoo API** | 연구 목적에 불필요한 외부 의존 추가 |
| **Google Analytics / Slack 자동 알림** | 연구 단계에 불필요 |

### 16.5 추천 Phase 2 진입 순서 (제안)

1. **Step11A (rule extraction)** 에서 본 문서 16.1 후보를 평가
   - 각 후보별 "타당성 / 기대 효과 / 이식 비용 / 전략 로직 영향" 4축 평가표 작성
2. 평가 결과에 따라 `Step11A-FIX1` 또는 `Step11A-N (N>=2)` 로 실제 이식 계획
3. 이식 실행은 **Phase 2 별도 step** — 전략 로직 변경이므로 Full Backtest / Tune 재실행 의무화

---

## 부록 A. 파일 인벤토리 (주요 파일 ~50)

### 최상위
- `README.md` (3.5K), `AGENTS.md` (4.2K), `LICENSE`, `config.py` (100 LOC)
- `Dockerfile.fastapi`, `docker-compose.yml`, `docker-compose.hybrid.yml`
- `pyproject.toml`, `requirements.txt` (70 deps), `requirements-dev.txt`
- `run_local_dev.py`

### 백엔드 핵심
- `core/strategy/scoring.py` (43 LOC) — 모멘텀 공식
- `core/strategy/metrics.py` (172 LOC) — 종목 처리 + 7종 MA
- `core/strategy/weight_allocator.py` (165 LOC) — 비중 할당
- `utils/rankings.py` (500+ LOC) — 순위 생성 엔진
- `utils/data_loader.py` (500+ LOC) — 가격 데이터
- `utils/cache_utils.py` (400+ LOC) — 3-tier 캐싱
- `utils/backtest_service.py` (400+ LOC) — 백테스트
- `utils/moving_averages.py` (~150 LOC) — 7종 MA
- `utils/indicators.py` (67 LOC)
- `utils/normalization.py` (53 LOC)

### 서비스
- `services/price_service.py` (319), `etf_holdings_service.py` (535),
- `etf_meta_service.py` (116), `fear_greed_service.py` (96),
- `vkospi_service.py` (99), `stock_cache_service.py` (90)

### FastAPI
- `fastapi_app/main.py` (121), `dependencies.py` (26)
- `routes/backtest.py` (109), `rank.py` (34), `holdings.py` (86)
- `routes/stocks.py` (112), `assets.py` (26), `dashboard.py` (13)
- `routes/snapshots.py` (13), `market.py` (40), `note.py` (29)
- `routes/ticker_detail.py` (479), `weekly.py` (41), `system.py` (31)

### 프론트
- `web/app/stocks/StocksManager.tsx` (51K - 순위 화면)
- `web/app/ticker/TickerDetailManager.tsx` (41K - 종목 상세)
- `web/app/AppShell.tsx`, `web/app/components/*`
- `web/globals.css` (58K)
- `web/package.json` (React 19 + Next 16 + AG Grid + Lightweight Charts)

### 문서
- `docs/README.md` (none), `project_overview.md` (2K)
- `developer_guide.md` (5.7K), `user_guide.md` (8.3K)
- `strategy_logic.md` (1.1K), `server_infrastructure.md` (1.5K)
- `mongodb.md` (9.7K)

### 인프라
- `.github/workflows/` — 5개 (deploy, cache_refresh, metadata_updater, asset_summary, market_hours_analysis)
- `infra/cron/crontab`, `infra/cron/run_batch.py`
- `scripts/` — 15개 CLI

---

## 부록 B. 용어집

| 용어 | 정의 |
|---|---|
| **MAPS** | Moving Average Position Score — `((Close/MA) − 1) × 100` |
| **MA_RULES** | `ztickers/*/config.json` 내 다중 이동평균 규칙 배열 |
| **추세1 / 추세2** | MA_RULES 의 order 별 점수 컬럼 |
| **Bucket** | 5개 자산군 분류 (모멘텀/시장/배당/헷지/현금) |
| **Ticker Type** | 종목풀 식별자 (`kor_kr`, `kor_us`, `aus`, `us`) |
| **Account** | 투자 계좌 (`1_kor_account` 등 5종) |
| **iNAV** | 내재가치 (ETF 실시간 자산가치) |
| **괴리율** | 시장가 vs NAV 차이 (premium/discount) |

---

## 부록 C. 의존성 전체 (친구 프로젝트)

### Python (`requirements.txt` 주요 70개)

| 카테고리 | 패키지 | 버전 |
|---|---|---|
| 웹 | fastapi, uvicorn | - |
| 데이터 | pandas 2.3.2, numpy 1.26.4, pyarrow 21.0.0 | |
| 금융 | pykrx 1.2.4, yfinance 0.2.65, beautifulsoup4 4.13.5 | |
| 차트 | matplotlib 3.10.6 | |
| DB | pymongo 4.15.1 | |
| 캘린더 | pandas-market-calendars 5.1.1, exchange-calendars 4.11.1 | |
| 스케줄 | apscheduler 3.11.0 | |
| 알림 | slack-sdk 3.36.0 | |
| 환경 | python-dotenv 1.1.1 | |

### Node.js (`web/package.json`)

| 패키지 | 버전 |
|---|---|
| react, react-dom | ^19.2.0 |
| next | ^16.0.0 |
| ag-grid-react | ^35.2.0 |
| lightweight-charts | ^5.1.0 |
| recharts | ^3.8.1 |
| mongodb | ^6.20.0 |
| @tabler/core | ^1.4.0 |
| @tabler/icons-react | ^3.41.0 |

---

## 부록 D. 정량 측정 결과 (실측)

### D-1. 파일 수 / LOC 전체

| 분류 | 파일 수 | LOC |
|---|---:|---:|
| 전체 파일 | 228 | — |
| Python (`*.py`) | **84** | **18,070** |
| Web TypeScript (`*.ts`) | 44 | 2,779 |
| Web TSX (`*.tsx`) | 43 | 11,040 |
| Web TS + TSX 합계 | **87** | **13,819** |
| **Python + Web 단순 합산** | **171** | **31,889** |

### D-2. Python 디렉토리별 breakdown

| 디렉토리 | 파일 수 | LOC | 비중 |
|---|---:|---:|---:|
| `utils/` | 35 | **11,885** | 65.8% |
| `scripts/` | 15 | 2,928 | 16.2% |
| `services/` | 8 | 1,323 | 7.3% |
| `fastapi_app/` | 16 | 1,159 | 6.4% |
| `core/` | 4 | 389 | 2.2% |
| 기타 (`config.py`, `run_local_dev.py` 등) | 6 | ~386 | 2.1% |
| **합계** | **84** | **18,070** | 100% |

### D-3. Python 상위 LOC 파일 (Top 15)

| 순위 | 파일 | LOC |
|---:|---|---:|
| 1 | `utils/data_loader.py` | 2,003 |
| 2 | `utils/cache_utils.py` | 1,019 |
| 3 | `utils/portfolio_io.py` | 818 |
| 4 | `utils/rankings.py` | 817 |
| 5 | `utils/backtest_service.py` | 650 |
| 6 | `utils/stock_list_io.py` | 638 |
| 7 | `utils/stock_meta_updater.py` | 629 |
| 8 | `utils/holdings_detail_service.py` | 582 |
| 9 | `services/etf_holdings_service.py` | 535 |
| 10 | `utils/stocks_service.py` | 525 |
| 11 | `scripts/collect_investor_trend.py` | 520 |
| 12 | `utils/weekly_service.py` | 507 |
| 13 | `utils/kis_market.py` | 500 |
| 14 | `fastapi_app/routes/ticker_detail.py` | 479 |
| 15 | `scripts/stock_price_cache_updater.py` | 386 |

### D-4. `scripts/` 15개 LOC

| 파일 | LOC | 용도 |
|---|---:|---|
| `collect_investor_trend.py` | 520 | 투자자 동향 수집 |
| `stock_price_cache_updater.py` | 386 | 종가 캐시 갱신 (매시간 cron) |
| `slack_asset_summary.py` | 317 | 자산 요약 Slack |
| `check_similar_tickers.py` | 307 | 유사 종목 검사 |
| `find_kor.py` | 305 | 한국 종목 탐색 |
| `portfolio_notifier.py` | 272 | 포트폴리오 Slack 알림 |
| `analyze_market_hours.py` | 201 | 장 시간 분석 |
| `migrate_bucket_scheme.py` | 160 | 버킷 마이그레이션 |
| `migrate_daily_snapshots_round_money.py` | 108 | 일일 스냅샷 반올림 |
| `migrate_weekly_round_floats.py` | 106 | 주간 데이터 반올림 |
| `analyze_removed_ytd.py` | 95 | 제거 종목 YTD 분석 |
| `audit_aus_snapshot_cash.py` | 65 | 호주 현금 감사 |
| `stock_meta_cache_updater.py` | 44 | 메타 캐시 갱신 (매일 cron) |
| `debug_cache.py` | 31 | 캐시 디버깅 |
| `clear_cache.py` | 11 | 캐시 초기화 |
| + `mongo-tunnel.sh`, `update_app_datetime.sh` (쉘) | — | 운영 헬퍼 |

### D-5. FastAPI 엔드포인트 합계 (실측)

- **FastAPI 엔드포인트** (`fastapi_app/routes/*.py` 의 `@router.*` 데코레이터): **40개**
- **Next.js API Routes** (`web/app/api/**/route.ts`): **22개**
- 둘의 합은 아키텍처상 중복 카운팅이므로 **"총 엔드포인트 수"** 로 합산하지 않음

---

## 분석 결론

친구 프로젝트 `momentum-etf-main` 은 **실투자 의사결정 + 포트폴리오 관리** 를 지원하는 **엔터프라이즈급 풀스택 애플리케이션** 입니다. 현재 우리 프로젝트 `krx_alertor_modular` 와는 **목적이 다른 자매 시스템** 이며, 일부 전략 로직 아이디어 (7종 MA / 0 중심 부호 보존 백분위 / 다중 규칙 조합 / 가드레일 비중 할당) 는 Phase 2 rule extraction 의 유의미한 입력이 될 수 있습니다.

다만 MongoDB 저장소 / Next.js 프론트 / Google OAuth 같은 **인프라 축** 은 현재 프로젝트의 연구 용도와 맞지 않아 직접 이식 후보에서 제외하는 것이 합리적입니다.

다음 단계(`P211-STEP11A-FRIEND-SOURCE-RULE-EXTRACTION-V1`) 진입 시, 본 문서 §16.1 의 6개 전략 로직 후보를 **4축 평가표 (타당성 / 기대 효과 / 이식 비용 / 영향 범위)** 로 스코어링하는 것이 자연스러운 시작점입니다.
