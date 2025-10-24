# 📈 KRX Alertor Modular

한국 ETF/주식 자동 매매 시스템 - 모멘텀 추세 추종 전략

[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🎯 핵심 개념

이동평균선 기반 모멘텀 추세 추종 전략으로 ETF 포트폴리오를 자동 관리합니다.
- **데이터 소스**: PyKRX → FDR → Stooq → YahooFinance (폴백)
- **저장**: SQLite DB + Parquet 캐시
- **환경**: Synology NAS (운영) + Windows PC (개발)

## 🏗️ 아키텍처

```
krx_alertor_modular/
├── core/              # 공통 모듈 (NAS + PC)
│   ├── db.py
│   ├── fetchers.py
│   ├── providers/     # 멀티 소스 라우팅
│   └── utils/
├── nas/               # NAS 전용 (경량, Python 3.8)
│   ├── app_nas.py
│   └── scanner_nas.py
├── pc/                # PC 전용 (전체 기능)
│   ├── app_pc.py
│   ├── backtest.py
│   └── ml/
├── config/            # 설정 파일
│   ├── common.yaml
│   ├── scanner_config.yaml
│   └── universe.yaml
└── scripts/           # 배치 스크립트
    └── linux/batch/
```

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
# 1) DB 초기화
python pc/app_pc.py init

# 2) 종목 데이터 수집
python pc/app_pc.py ingest-eod --date auto

# 3) 섹터 자동 분류
python pc/app_pc.py autotag
```

### 3. 스캐너 실행

**PC에서 테스트:**
```bash
python nas/app_nas.py scanner --date 2024-10-23
```

**NAS에서 운영:**
```bash
cd ~/krx/krx_alertor_modular
bash scripts/linux/batch/update_from_git.sh
source venv/bin/activate
python nas/app_nas.py scanner --date auto
```

---

## 📖 명령어 가이드

### 데이터 수집 (PC)

```bash
# EOD 데이터 수집
python pc/app_pc.py ingest-eod --date auto

# 특정 날짜 수집
python pc/app_pc.py ingest-eod --date 2024-10-23
```

### 스캐너 (NAS)

```bash
# 기본 실행
python nas/app_nas.py scanner --date auto

# 특정 날짜
python nas/app_nas.py scanner --date 2024-10-23
```

### 백테스트 (PC)

```bash
# 기간 지정 백테스트
python pc/app_pc.py backtest --start 2024-01-01 --end 2024-10-23

# 결과는 backtests/ 폴더에 CSV로 저장
```

### 리포트 (PC)

```bash
# 성과 리포트 생성
python pc/app_pc.py report --start 2024-01-01
```

---

## 📊 개발 워크플로우

```
PC (개발/테스트)           NAS (운영)
─────────────────         ─────────────
1. 코드 수정               4. Git pull
2. 로컬 테스트             5. 스캐너 실행
3. Git push                6. 알림 전송
```

**권장 프로세스:**
1. PC에서 `nas/app_nas.py` 테스트
2. 성공 시 Git commit & push
3. NAS에서 `update_from_git.sh` 실행
4. NAS에서 최종 확인

---

## 🔧 설정 파일

### config/common.yaml
```yaml
database:
  path: "krx_alertor.sqlite3"
timezone: "Asia/Seoul"
cache:
  ohlcv_dir: "data/cache/ohlcv"
```

### config/scanner_config.yaml
```yaml
strategy:
  name: "MAPS"
  ma_period: 60
  portfolio_topn: 5
  
market_regime:
  indices:
    - symbol: "^KS11"
      ma_period: 60
```

### config/universe.yaml
```yaml
etfs:
  - symbol: "069500"
    name: "KODEX 200"
    category: "대형주"
```

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

### ✅ 완료
- [x] 모듈 분리 (core/, nas/, pc/)
- [x] Multi-provider 라우팅 (PyKRX/FDR/Stooq/YF)
- [x] Parquet 캐시 시스템
- [x] NAS 배포 자동화

### 🚧 진행 중
- [ ] DataFrame ambiguous error 수정
- [ ] 캘린더 로딩 안정화
- [ ] 스캐너 신호 튜닝

### 📋 계획
- [ ] 백테스트 피드백 루프
- [ ] Telegram 알림 통합
- [ ] Web UI 완성

---

## 📄 라이선스

MIT License

---

## 👤 작성자

Hyungsoo Kim

---

## 🙏 기여

Issue 및 PR 환영합니다!
