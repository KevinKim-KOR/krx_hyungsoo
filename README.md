# 📈 KRX Alertor Modular

한국 ETF/주식 자동 매매 시스템 - 데이터 수집, 스캐너, 백테스트, 알림 통합 플랫폼

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🎯 주요 기능

- **📥 데이터 수집**: PyKRX → FDR → Stooq → YahooFinance 다중 소스 폴백
- **🔍 스캐너**: 급등+추세+강도+섹터 다중 조건 필터링
- **📊 백테스트**: 리밸런싱 전략 시뮬레이션 (수수료/슬리피지 반영)
- **📢 알림**: Telegram/Slack 실시간 알림
- **💾 캐시**: Parquet 기반 증분 업데이트
- **🔄 배치**: NAS/PC 환경 분리, 락 파일 기반 중복 실행 방지

---

## 🚀 빠른 시작

### 1. 설치 (Windows)

```powershell
cd "E:\AI Study\krx_alertor_modular"
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. 초기 설정

```bash
# 1) 설정 파일 생성
cp config.yaml.example config.yaml
# config.yaml 편집 (Telegram/Slack 토큰 등)

# 2) DB 초기화
python app.py init

# 3) 종목 데이터 수집
python app.py ingest-eod --date auto

# 4) 섹터 자동 분류
python app.py autotag
```

### 3. 스캐너 실행

```bash
# 오늘 날짜 기준 BUY/SELL 추천
python app.py scanner

# 특정 날짜 지정
python app.py scanner --date 2025-10-20

# 진단 스크립트 (0건 출력 시)
python scripts/diagnostics/diagnose_scanner_zero.py
```

---

## 📖 명령어 가이드

### 데이터 수집

```bash
# EOD 데이터 수집 (자동 날짜)
python app.py ingest-eod --date auto

# 특정 날짜 수집
python app.py ingest-eod --date 2025-10-20

# 실시간 가격 (단일 종목)
python app.py ingest-realtime --code 005930
```

### 스캐너

```bash
# 기본 실행
python app.py scanner

# Slack 알림 포함
python app.py scanner-slack --date 2025-10-20
```

### 백테스트

```bash
# 기간 지정 백테스트
python app.py backtest --start 2024-01-01 --end 2025-10-20 --config config.yaml

# 결과는 backtests/ 폴더에 CSV로 저장
```

### 리포트

```bash
# 성과 리포트 생성
python app.py report --start 2024-01-01 --end 2025-10-20 --benchmark 069500

# EOD 요약 리포트 (Telegram 전송)
python app.py report-eod --date auto
```

---

## 🏗️ 아키텍처

```
krx_alertor_modular/
├── app.py                 # CLI 진입점
├── config.yaml            # 설정 파일 (gitignore)
├── config.yaml.example    # 설정 템플릿
│
├── db.py                  # SQLAlchemy ORM
├── fetchers.py            # 데이터 수집 (PyKRX/YF)
├── scanner.py             # 스캐너 로직
├── backtest.py            # 백테스트 엔진
├── indicators.py          # 기술 지표 (SMA, ADX, MFI 등)
├── notifications.py       # Telegram/Slack 알림
├── calendar_kr.py         # 한국 거래일 캘린더
│
├── providers/             # 멀티 소스 라우팅
│   ├── ohlcv.py          # PyKRX → FDR → Stooq → YF
│   └── ohlcv_bridge.py   # 캐시 우선 브리지
│
├── data/
│   ├── cache/            # Parquet 캐시
│   └── kr/               # 한국 시장 데이터
│
├── scripts/
│   ├── linux/batch/      # NAS 배치 스크립트
│   ├── diagnostics/      # 진단 도구
│   └── ops/              # 운영 스크립트
│
├── tests/                 # 단위 테스트
│   ├── test_indicators.py
│   └── test_scanner_filters.py
│
└── web/                   # UI (개발 중)
```

---

## 🔧 설정 파일 (config.yaml)

주요 설정 항목:

```yaml
# 유니버스
universe:
  type: ETF
  exclude_keywords: [레버리지, 채권, 인버스]
  min_avg_turnover: 1000000000  # 10억원

# 스캐너 임계값
scanner:
  thresholds:
    daily_jump_pct: 1.0    # 급등 기준 (완화)
    adx_min: 15.0          # ADX 최소값 (완화)
    mfi_min: 40.0          # MFI 범위 (완화)

# 알림
notifications:
  channel: telegram
  telegram:
    bot_token: "YOUR_BOT_TOKEN"
    chat_id: "YOUR_CHAT_ID"
```

자세한 설정은 `config.yaml.example` 참고

---

## 🐛 트러블슈팅

### 스캐너가 0건 출력

```bash
# 진단 스크립트 실행
python scripts/diagnostics/diagnose_scanner_zero.py

# 레짐 가드 비활성화 (테스트용)
bash scripts/linux/diagnostics/disable_regime_guard.sh

# 필터 조건 완화
# config.yaml > scanner.thresholds 값 조정
```

### YahooFinance RateLimit

→ 이미 해결됨 (PyKRX/FDR 우선 사용)

### 캐시 손상

```bash
# 캐시 재생성
rm -rf data/cache/kr/*.pkl
python app.py ingest-eod --date auto
```

---

## 🧪 테스트

```bash
# 전체 테스트
pytest tests/ -v

# 특정 모듈
pytest tests/test_indicators.py -v
pytest tests/test_scanner_filters.py -v
```

---

## 📅 로드맵

- [x] Multi-provider 라우팅 (PyKRX/FDR/Stooq/YF)
- [x] Parquet 캐시 시스템
- [x] 스캐너 브리지 통합
- [ ] 신호 튜닝 (RSI, MACD 추가)
- [ ] 백테스트 피드백 루프
- [ ] Web UI 완성
- [ ] 배치 스케줄러 등록

---

## 📄 라이선스

MIT License

---

## 👤 작성자

Hyungsoo Kim

---

## 🙏 기여

Issue 및 PR 환영합니다!
