# 🧪 NAS 테스트 가이드

**작성일**: 2025-10-24  
**목적**: NAS에서 모듈 분리 후 정상 동작 확인

---

## 📋 사전 준비

### 1. Git 동기화
```bash
cd ~/krx/krx_alertor_modular
bash scripts/linux/batch/update_from_git.sh
```

이 스크립트는 자동으로:
- Git pull 실행
- `nas/requirements.txt` 설치
- 가상환경 설정

---

## ✅ 테스트 단계

### 1단계: 의존성 확인
```bash
source venv/bin/activate
pip list | grep -E "pykrx|pandas|sqlalchemy|pyyaml|requests|pytz|FinanceDataReader"
```

**예상 출력**:
```
FinanceDataReader    0.9.50
pandas               1.5.3
pykrx                1.0.45
pytz                 2024.1
PyYAML               6.0.2
requests             2.32.3
SQLAlchemy           2.0.x
```

### 2단계: CLI 도움말 확인
```bash
python nas/app_nas.py --help
```

**예상 출력**:
```
usage: app_nas.py [-h] {init,ingest-eod,scanner,notify} ...

KRX Alertor NAS CLI

positional arguments:
  {init,ingest-eod,scanner,notify}
    init                DB 초기화
    ingest-eod          EOD 데이터 수집
    scanner             스캐너 실행
    notify              텔레그램 알림
```

### 3단계: DB 초기화 (최초 1회)
```bash
python nas/app_nas.py init
```

**예상 출력**:
```
✅ DB 초기화 완료
```

### 4단계: 스캐너 테스트
```bash
python nas/app_nas.py scanner --date auto
```

**예상 출력** (데이터 없는 경우):
```
유니버스 크기: 0 종목
⚠️ 가격 데이터 없음
```

**예상 출력** (데이터 있는 경우):
```
유니버스 크기: 100 종목

✅ BUY 후보: 5건
  - 069500: 1일 1.50%, 20일 5.20%, ADX 25.3, MFI 65.2, 종가 35000
  ...
```

---

## 🐛 문제 해결

### 문제 1: ModuleNotFoundError: No module named 'sqlalchemy'
**원인**: 의존성 미설치

**해결**:
```bash
source venv/bin/activate
pip install -r nas/requirements.txt
```

### 문제 2: ImportError: cannot import name 'is_trading_day'
**원인**: 순환 import (이미 해결됨)

**확인**:
```bash
git pull  # 최신 코드 받기
```

### 문제 3: 가격 데이터 없음
**원인**: EOD 데이터 미수집

**해결**:
```bash
# 데이터 수집 먼저 실행
python nas/app_nas.py ingest-eod --date auto
```

---

## 📊 성공 기준

- [ ] `python nas/app_nas.py --help` 정상 출력
- [ ] `python nas/app_nas.py init` 성공
- [ ] `python nas/app_nas.py scanner --date auto` 오류 없이 실행
- [ ] 의존성 크기 50MB 이하
- [ ] 메모리 사용량 100MB 이하

---

## 🔄 다음 단계

테스트 성공 후:

1. **Cron 등록**
   ```bash
   crontab -e
   
   # 매일 오전 9시: Git 동기화
   0 9 * * * cd ~/krx/krx_alertor_modular && bash scripts/linux/batch/update_from_git.sh
   
   # 평일 16:10: EOD 데이터 수집
   10 16 * * 1-5 cd ~/krx/krx_alertor_modular && source venv/bin/activate && python nas/app_nas.py ingest-eod --date auto
   
   # 평일 16:20: 스캐너 실행
   20 16 * * 1-5 cd ~/krx/krx_alertor_modular && source venv/bin/activate && python nas/app_nas.py scanner --date auto
   ```

2. **텔레그램 알림 설정**
   - `config/config.nas.yaml`에서 Bot Token, Chat ID 설정

3. **로그 확인**
   ```bash
   tail -f logs/nas_app.log
   ```

---

## 📞 문의

문제 발생 시:
1. 로그 확인: `tail -100 logs/update_*.log`
2. GitHub Issues에 로그 첨부

---

**작성자**: Cascade AI  
**버전**: 1.0.0  
**최종 수정**: 2025-10-24
