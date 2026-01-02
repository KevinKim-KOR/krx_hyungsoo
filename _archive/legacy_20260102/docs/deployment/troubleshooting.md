# 문제 해결 가이드

**최종 업데이트**: 2025-11-27

---

## 📋 목차

1. [Git 관련](#git-관련)
2. [텔레그램 알림](#텔레그램-알림)
3. [Python 환경](#python-환경)
4. [데이터 수집](#데이터-수집)
5. [성능 문제](#성능-문제)

---

## Git 관련

### Git Pull 충돌

**증상**:
```
error: Your local changes to the following files would be overwritten by merge:
  data/cache/ohlcv/*.parquet
Please commit your changes or stash them before you merge.
```

**원인**:
- `.parquet` 캐시 파일이 Git에 추적되고 있음
- `.gitignore`에 있지만 이미 추적된 파일은 계속 추적됨

**해결 방법**:

1. **캐시 파일 Git 추적 중지** (권장)
   ```bash
   # 캐시 파일 Git 추적 중지
   git rm --cached data/cache/ohlcv/*.parquet
   
   # 커밋
   git commit -m "Stop tracking cache files"
   
   # 푸시
   git push
   ```

2. **로컬 변경사항 무시**
   ```bash
   # 캐시 파일 삭제
   rm -rf data/cache/ohlcv/*.parquet
   
   # Git Pull
   git pull
   ```

3. **.gitignore 확인**
   ```bash
   cat .gitignore | grep parquet
   
   # 예상 출력:
   # data/cache/**/*.parquet
   ```

**예방**:
- `.gitignore`에 캐시 파일 패턴 추가
- 이미 추적된 파일은 `git rm --cached`로 제거

---

### Git Push 실패

**증상**:
```
error: failed to push some refs to 'origin'
hint: Updates were rejected because the remote contains work that you do not have locally.
```

**해결 방법**:

1. **Pull 후 Push**
   ```bash
   # Pull (병합)
   git pull
   
   # 충돌 해결 (있으면)
   git add .
   git commit -m "Merge remote changes"
   
   # Push
   git push
   ```

2. **Force Push** (주의!)
   ```bash
   # 로컬 변경사항이 확실히 최신일 때만
   git push --force
   ```

---

## 텔레그램 알림

### 알림 전송 실패

**증상**:
```
ERROR: 텔레그램 알림 전송 실패 (result=False)
```

**원인**:
1. `TELEGRAM_ENABLED=false`
2. `BOT_TOKEN` 또는 `CHAT_ID` 없음
3. 네트워크 오류

**해결 방법**:

1. **환경 변수 확인**
   ```bash
   cat .env | grep TELEGRAM
   
   # 예상 출력:
   # TELEGRAM_ENABLED=true
   # TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   # TELEGRAM_CHAT_ID=123456789
   ```

2. **네트워크 확인**
   ```bash
   curl https://api.telegram.org/bot<TOKEN>/getMe
   
   # 예상 결과: {"ok":true,"result":{...}}
   ```

3. **로그 확인**
   ```bash
   tail -f logs/daily_regime_check.log
   
   # 또는
   tail -f logs/automation.log
   ```

**텔레그램 봇 재설정**:
```bash
# 1. BotFather에서 새 봇 생성
/newbot

# 2. Chat ID 확인
https://api.telegram.org/bot<TOKEN>/getUpdates

# 3. .env 업데이트
nano .env
```

---

### 알림이 너무 많음

**증상**:
- 장중 알림이 너무 자주 옴
- 의미 없는 알림이 많음

**해결 방법**:

**장중 알림 기준 상향**:
```python
# scripts/automation/intraday_alert.py 수정
THRESHOLDS = {
    'leverage': 4.0,      # 3.0 → 4.0
    'sector': 3.0,        # 2.0 → 3.0
    'index': 2.0,         # 1.5 → 2.0
    'overseas': 2.0,      # 1.5 → 2.0
    'default': 3.0        # 2.0 → 3.0
}

# 거래대금 기준 상향
MIN_TRADE_VALUE = 100e8  # 50억 → 100억
```

---

### 알림이 너무 적음

**증상**:
- 알림이 거의 안 옴
- 중요한 신호를 놓침

**해결 방법**:

**장중 알림 기준 하향**:
```python
# scripts/automation/intraday_alert.py 수정
THRESHOLDS = {
    'leverage': 2.0,      # 3.0 → 2.0
    'sector': 1.5,        # 2.0 → 1.5
    'index': 1.0,         # 1.5 → 1.0
    'overseas': 1.0,      # 1.5 → 1.0
    'default': 1.5        # 2.0 → 1.5
}

# 거래대금 기준 하향
MIN_TRADE_VALUE = 30e8  # 50억 → 30억
```

---

## Python 환경

### ModuleNotFoundError

**증상**:
```
ModuleNotFoundError: No module named 'xxx'
```

**해결 방법**:

1. **가상 환경 활성화 확인**
   ```bash
   # 가상 환경 활성화
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   
   # Python 경로 확인
   which python  # Linux/Mac
   where python  # Windows
   
   # 예상: <project>/venv/bin/python
   ```

2. **패키지 재설치**
   ```bash
   pip install -r requirements.txt
   ```

3. **Cron 경로 확인**
   ```bash
   # Cron에서 절대 경로 사용
   /home/ubuntu/krx_alertor_modular/venv/bin/python
   ```

---

### yfinance 설치 오류 (NAS)

**증상**:
```
ERROR: Failed building wheel for lxml
ERROR: Could not build wheels for lxml
```

**해결 방법**:

**yfinance 설치 불필요!**

```bash
# NAS에서는 yfinance 설치하지 마세요
# 대신 네이버 금융 자동 사용

# 필수 패키지만 설치
pip3 install requests beautifulsoup4 pyyaml python-dotenv --upgrade
```

**이유**:
- NAS Python 3.8에서 yfinance 최신 버전 TypeError 발생
- lxml 빌드 실패 (libxml2, libxslt 의존성)
- multitasking 패키지의 type[Thread] 문법 오류

**자동 폴백**:
- `core/data_loader.py`에서 yfinance 없으면 자동으로 네이버 금융 사용
- 한국 주식: 네이버 금융 (빠르고 정확, ~0.5초)

---

### Python 버전 오류

**증상**:
```
SyntaxError: invalid syntax
```

**해결 방법**:

1. **Python 버전 확인**
   ```bash
   python --version
   # 필요: Python 3.8+
   ```

2. **Python 업그레이드**
   ```bash
   # Ubuntu/Debian
   sudo apt install python3.10
   
   # 가상 환경 재생성
   python3.10 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

---

## 데이터 수집

### 데이터 수집 실패

**증상**:
```
ERROR: Failed to fetch data for <ticker>
```

**원인**:
1. 네트워크 오류
2. API Rate Limit
3. 잘못된 티커

**해결 방법**:

1. **네트워크 확인**
   ```bash
   ping 8.8.8.8
   curl https://finance.naver.com
   ```

2. **로그 확인**
   ```bash
   tail -f logs/data_loader.log
   ```

3. **재시도**
   ```bash
   # 데이터 수집 재실행
   python -m core.data_loader --ticker <ticker>
   ```

---

### 캐시 파일 오류

**증상**:
```
ERROR: Failed to read cache file
```

**해결 방법**:

1. **캐시 삭제**
   ```bash
   rm -rf data/cache/ohlcv/*.parquet
   ```

2. **재수집**
   ```bash
   python -m core.data_loader --ticker <ticker> --force
   ```

---

## 성능 문제

### 메모리 부족

**증상**:
```
MemoryError
또는
Killed
```

**해결 방법**:

1. **Swap 파일 생성** (Oracle Cloud Free Tier 1GB RAM)
   ```bash
   # 2GB Swap 생성
   sudo fallocate -l 2G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   
   # 영구 설정
   echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
   
   # 확인
   free -h
   ```

2. **불필요한 프로세스 종료**
   ```bash
   # 메모리 사용량 확인
   top
   
   # 프로세스 종료
   kill <PID>
   ```

3. **배치 크기 줄이기**
   ```python
   # 데이터 수집 시 배치 크기 조정
   BATCH_SIZE = 10  # 기본 50 → 10
   ```

---

### 디스크 공간 부족

**증상**:
```
OSError: [Errno 28] No space left on device
```

**해결 방법**:

1. **디스크 사용량 확인**
   ```bash
   df -h
   ```

2. **캐시 정리**
   ```bash
   # 30일 이상 된 캐시 삭제
   find data/cache/ohlcv -name "*.parquet" -mtime +30 -delete
   ```

3. **로그 정리**
   ```bash
   # 30일 이상 된 로그 삭제
   find logs -name "*.log" -mtime +30 -delete
   ```

4. **불필요한 파일 삭제**
   ```bash
   # __pycache__ 삭제
   find . -type d -name __pycache__ -exec rm -rf {} +
   
   # .pyc 파일 삭제
   find . -name "*.pyc" -delete
   ```

---

### 느린 실행 속도

**증상**:
- 스크립트 실행이 너무 느림
- 타임아웃 발생

**해결 방법**:

1. **캐시 활용**
   ```python
   # 캐시 사용 확인
   USE_CACHE = True
   ```

2. **병렬 처리**
   ```python
   # 멀티프로세싱 사용
   from multiprocessing import Pool
   
   with Pool(4) as p:
       results = p.map(fetch_data, tickers)
   ```

3. **데이터 범위 축소**
   ```python
   # 필요한 기간만 조회
   start_date = "2024-01-01"  # 전체 → 최근 1년
   ```

---

## 참고 문서

- [Oracle Cloud 배포 가이드](./oracle-cloud.md)
- [NAS 배포 가이드](./nas.md)
- [알림 시스템 가이드](../guides/alert-system.md)

---

## 추가 도움

**문제가 해결되지 않으면**:
1. 로그 파일 확인 (`logs/`)
2. GitHub Issues 검색
3. 새 Issue 생성 (로그 첨부)

**로그 위치**:
- `logs/daily_regime_check.log`
- `logs/us_market_monitor.log`
- `logs/automation.log`
- `logs/data_loader.log`
