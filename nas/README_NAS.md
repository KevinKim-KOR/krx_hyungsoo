# 📘 NAS 실행 가이드

## 🎯 개요

NAS 전용 경량 CLI - 데이터 수집, 스캐너, 알림 기능만 포함

**특징**:
- 의존성 5개 (50MB, 설치 1분)
- PyTorch, ML 모듈 제외
- 메모리 사용량 100MB 이하

---

## 📦 설치 (NAS)

### 1. 프로젝트 클론
```bash
cd /volume2/homes/Hyungsoo/krx
git clone https://github.com/KevinKim-KOR/krx_hyungsoo.git krx_alertor_modular
cd krx_alertor_modular
```

### 2. 가상환경 생성
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. 의존성 설치 (최소)
```bash
pip install -r nas/requirements.txt
```

**설치 시간**: ~1분  
**용량**: ~50MB

---

## 🚀 실행

### DB 초기화 (최초 1회)
```bash
python nas/app_nas.py init
```

### EOD 데이터 수집
```bash
# 자동 날짜 (오늘 또는 최근 거래일)
python nas/app_nas.py ingest-eod --date auto

# 특정 날짜
python nas/app_nas.py ingest-eod --date 2025-10-20
```

### 스캐너 실행
```bash
# 자동 날짜
python nas/app_nas.py scanner

# 특정 날짜
python nas/app_nas.py scanner --date 2025-10-20
```

### 알림 전송
```bash
python nas/app_nas.py notify "테스트 메시지"
```

---

## ⏰ Cron 등록

### crontab 편집
```bash
crontab -e
```

### 스케줄 등록
```bash
# 매일 오전 9시: Git 동기화
0 9 * * * cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && git pull

# 평일 16:10: EOD 데이터 수집
10 16 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && source venv/bin/activate && python nas/app_nas.py ingest-eod --date auto

# 평일 16:20: 스캐너 실행
20 16 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && source venv/bin/activate && python nas/app_nas.py scanner
```

---

## 🔧 설정

### 설정 파일 위치
- `config/config.yaml` (또는 `config.yaml`)

### 주요 설정
```yaml
universe:
  type: ETF
  exclude_keywords:
    - 레버리지
    - 인버스
    - 채권

scanner:
  thresholds:
    daily_jump_pct: 1.0    # 급등 기준 (%)
    adx_min: 15.0          # ADX 최소값
    mfi_min: 40.0          # MFI 최소값

notifications:
  channel: telegram
  telegram:
    bot_token: "YOUR_BOT_TOKEN"
    chat_id: "YOUR_CHAT_ID"
```

---

## 📊 로그 확인

### 실행 로그
```bash
tail -f logs/nas_app.log
```

### 에러 로그
```bash
tail -f logs/error.log
```

---

## 🐛 트러블슈팅

### Import 오류
```bash
# Python 경로 확인
python -c "import sys; print(sys.path)"

# 프로젝트 루트에서 실행
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
python nas/app_nas.py --help
```

### 의존성 오류
```bash
# 재설치
pip install -r nas/requirements.txt --force-reinstall
```

### DB 오류
```bash
# DB 재초기화
rm krx_alertor.sqlite3
python nas/app_nas.py init
```

---

## 📈 성능

| 항목 | 수치 |
|------|------|
| **의존성 크기** | ~50MB |
| **설치 시간** | ~1분 |
| **메모리 사용** | ~100MB |
| **EOD 수집 시간** | ~30초 (100종목) |
| **스캐너 실행 시간** | ~10초 (100종목) |

---

## 🔗 관련 문서

- **PC 개발 가이드**: `../pc/README_PC.md`
- **전체 프로젝트**: `../README.md`
- **작업 계획**: `../docs/ACTION_PLAN_MODULE_SEPARATION.md`

---

**작성일**: 2025-10-24  
**버전**: 1.0.0
