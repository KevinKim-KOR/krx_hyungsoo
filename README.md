# 📈 KRX Alertor Modular

한국 ETF/주식 자동 매매 시스템 - Crisis Alpha Strategy

[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**System Version**: 9.0 (Phase 11 Complete)
**Last Update**: 2026-01-02

> 📋 **운영 Runbook (Daily Ops & Live Fire)**: [runbook_scheduler_v1.md](docs/ops/runbook_scheduler_v1.md)

---

## 🎯 핵심 개념

시장 하락장을 방어하고 횡보장을 피하는 위기 대응형 알파 전략(Crisis Alpha)입니다.

### 전략 특징
- **Bear Regime Detection**: 하락장 감지 시 현금 100%
- **ADX Chop Filter**: 횡보장(Chop) 진입 보류
- **RSI V2 Logic**: 매수/매도 임계값 기반 신호

### 기술 스택
- **데이터 소스**: PyKRX → FDR → Stooq → YahooFinance (폴백)
- **저장**: SQLite DB + Parquet 캐시
- **UI**: FastAPI Backend + React Dashboard

---

## 🏗️ 아키텍처

```
krx_alertor_modular/
├── core/              # 핵심 엔진 (Phase9Executor, Indicators, DB)
├── backend/           # FastAPI 백엔드 (REST API)
├── dashboard/         # React SPA (관제 UI)
├── app/               # CLI 진입점
├── config/            # 설정 파일
├── tools/             # 운영 스크립트
├── deploy/            # 배포 스크립트
├── reports/           # 시스템 산출물
└── docs/              # 문서
```

---

## 🚀 빠른 시작

### 1. 설치

```powershell
cd "E:\AI Study\krx_alertor_modular"
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. 백엔드 실행

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. 전략 스캔 (CLI)

```bash
python -m app.cli.alerts scan --strategy phase9 --config config/production_config_v2.py
```

### 4. 일일 배치 실행

```powershell
# Windows
./deploy/run_daily.ps1

# Linux/NAS
./deploy/run_daily.sh
```

---

## 📚 Documentation

문서는 `docs/` 폴더에 구성되어 있습니다.

| 폴더 | 내용 |
|------|------|
| `docs/components/` | 모듈별 분석 및 사용 현황 |
| `docs/design/` | 설계 명세 (아키텍처, 전략) |
| `docs/guides/` | 사용자/운영자 가이드 |
| `docs/ops/` | 운영 체크리스트 |
| `docs/contracts/` | API 계약 명세 (Contract 5) |
| `docs/tuning/` | 파라미터 튜닝 가이드 |

### 주요 문서
- **[project_final_report.md](docs/project_final_report.md)**: 최종 프로젝트 리포트
- **[architecture_freeze.md](docs/design/architecture_freeze.md)**: 아키텍처 원칙
- **[strategy_phase9.md](docs/design/strategy_phase9.md)**: Phase 9 전략 명세
- **[usage_summary.md](docs/components/usage_summary.md)**: 사용 현황 요약

---

## 📊 성과 (2022-2025)

| Metric | Value |
|--------|-------|
| CAGR | 27.05% |
| Sharpe | 1.51 ✅ |
| MDD | -19.92% |

---

## 🧪 테스트

```bash
# 전체 테스트
pytest tests/ -v

# 특정 모듈
pytest tests/test_indicators.py -v
```

---

## 📄 라이선스

MIT License

---

## 👤 작성자

Hyungsoo Kim
