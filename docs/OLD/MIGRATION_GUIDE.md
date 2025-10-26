# 🔄 모듈 분리 마이그레이션 가이드

**작성일**: 2025-10-24  
**버전**: 1.0.0

---

## 📋 변경 사항 요약

### 디렉토리 구조 변경
```
기존:
krx_alertor_modular/
├── db.py
├── fetchers.py
├── scanner.py
├── backtest.py
├── ml/
└── providers/

변경 후:
krx_alertor_modular/
├── core/              # 공통 모듈
│   ├── db.py
│   ├── fetchers.py
│   └── providers/
├── nas/               # NAS 전용
│   ├── app_nas.py
│   └── scanner_nas.py
└── pc/                # PC 전용
    ├── app_pc.py
    ├── backtest.py
    └── ml/
```

---

## 🚀 NAS 사용자

### 기존 명령어
```bash
python app.py scanner --date auto
python app.py ingest-eod --date auto
```

### 새 명령어
```bash
python nas/app_nas.py scanner --date auto
python nas/app_nas.py ingest-eod --date auto
```

### Shell 스크립트 수정
```bash
# scripts/linux/batch/run_scanner.sh
# 기존: python app.py scanner
# 변경: python nas/app_nas.py scanner
```

### 의존성 재설치
```bash
pip install -r nas/requirements.txt
```

---

## 💻 PC 사용자

### 기존 명령어
```bash
python app.py backtest --start 2024-01-01
```

### 새 명령어
```bash
python pc/app_pc.py backtest --start 2024-01-01
```

### 의존성 재설치
```bash
pip install -r pc/requirements.txt
```

---

## 🔧 Import 경로 변경

### Python 코드
```python
# 기존
from db import SessionLocal
from fetchers import ingest_eod
from scanner import recommend_buy_sell

# 변경 후
from core.db import SessionLocal
from core.fetchers import ingest_eod
from pc.scanner import recommend_buy_sell  # PC
# 또는
from nas.scanner_nas import run_scanner_nas  # NAS
```

---

## ⚠️ 주의사항

1. **기존 파일 유지**: 원본 파일은 삭제하지 않음 (백업 목적)
2. **설정 파일**: `config.yaml` → `config/config.nas.yaml` 또는 `config/config.pc.yaml`
3. **DB 경로**: 변경 없음 (`krx_alertor.sqlite3`)
4. **캐시 경로**: 변경 없음 (`data/cache/`)

---

## 🎯 마이그레이션 체크리스트

### NAS
- [ ] `nas/requirements.txt` 설치
- [ ] Shell 스크립트 경로 수정
- [ ] Cron 작업 업데이트
- [ ] 테스트 실행

### PC
- [ ] `pc/requirements.txt` 설치
- [ ] Import 경로 수정
- [ ] 백테스트 실행 확인
- [ ] ML 모듈 동작 확인

---

**문의**: GitHub Issues
