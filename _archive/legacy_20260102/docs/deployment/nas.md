# NAS 배포 가이드

**최종 업데이트**: 2025-11-27  
**환경**: Synology NAS DS220j + Python 3.8

---

## 📋 목차

1. [개요](#개요)
2. [사전 준비](#사전-준비)
3. [환경 구축](#환경-구축)
4. [애플리케이션 배포](#애플리케이션-배포)
5. [Cron 설정](#cron-설정)
6. [문제 해결](#문제-해결)

---

## 개요

Synology NAS에 KRX Alertor를 배포하는 가이드입니다.

**배포 구성**:
- **NAS**: Synology DS220j
- **OS**: DSM 7.x
- **Python**: 3.8
- **서비스**: Daily Regime Check

**특징**:
- ✅ 경량 설치 (yfinance 없이)
- ✅ Python 3.8 완벽 호환
- ✅ 네이버 금융 자동 사용
- ✅ 빠른 조회 (~0.5초)

---

## 사전 준비

### 1. NAS 환경 확인

```bash
# SSH 접속
ssh <username>@<nas-ip>

# Python 버전 확인
python3 --version
# 예상: Python 3.8.x

# pip 확인
pip3 --version
```

### 2. Git 설치 확인

```bash
# Git 버전 확인
git --version

# Git 없으면 설치
# DSM 패키지 센터에서 Git Server 설치
```

---

## 환경 구축

### 1. 프로젝트 클론

```bash
# 프로젝트 디렉토리로 이동
cd /volume2/homes/<username>

# 프로젝트 클론
git clone https://github.com/<your-username>/krx_alertor_modular.git
cd krx_alertor_modular
```

### 2. 의존성 설치

**중요**: NAS Python 3.8에서는 yfinance 설치 불필요!

```bash
# 필수 패키지만 설치 (경량)
pip3 install requests beautifulsoup4 pyyaml python-dotenv --upgrade

# yfinance 설치 불필요!
# - lxml 빌드 실패 (libxml2, libxslt 의존성)
# - multitasking 패키지 type[Thread] 문법 오류
# - 네이버 금융 자동 사용으로 대체
```

**설치 완료 확인**:
```bash
pip3 list | grep -E "requests|beautifulsoup4|pyyaml|python-dotenv"

# 예상 출력:
# beautifulsoup4    4.12.x
# python-dotenv     1.0.x
# PyYAML            6.0.x
# requests          2.31.x
```

### 3. 환경 변수 설정

```bash
# .env 파일 생성
cp .env.example .env

# .env 파일 편집
nano .env
```

**.env 파일 내용**:
```bash
# 텔레그램 설정
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=<your-bot-token>
TELEGRAM_CHAT_ID=<your-chat-id>

# 한국투자증권 API (선택사항)
KIS_APP_KEY=<your-app-key>
KIS_APP_SECRET=<your-app-secret>
KIS_ACCOUNT_NUMBER=<your-account-number>
```

---

## 애플리케이션 배포

### 1. 테스트 실행

```bash
# Daily Regime Check 테스트
python3 scripts/nas/daily_regime_check.py --dry-run

# 예상 결과:
# ✅ 레짐 감지 성공
# ✅ 네이버 금융 자동 사용
# ✅ 빠른 조회 (~0.5초)
```

### 2. 로그 디렉토리 생성

```bash
mkdir -p /volume2/homes/<username>/krx_alertor_modular/logs
```

---

## Cron 설정

### 1. Cron 편집

```bash
# Cron 편집
crontab -e
```

### 2. Cron 작업 추가

```bash
# 환경 변수
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
HOME=/volume2/homes/<username>

# Daily Regime Check (평일 16:00 - 장 마감 후)
0 16 * * 1-5 cd /volume2/homes/<username>/krx_alertor_modular && /usr/bin/python3 scripts/nas/daily_regime_check.py >> logs/daily_regime_check.log 2>&1
```

### 3. Cron 작업 확인

```bash
# Cron 목록 확인
crontab -l

# 로그 확인
tail -f /volume2/homes/<username>/krx_alertor_modular/logs/daily_regime_check.log
```

---

## 문제 해결

### yfinance 설치 오류

**증상**:
```
ERROR: Failed building wheel for lxml
ERROR: Could not build wheels for lxml
```

**해결 방법**:

**yfinance 설치 불필요!**

```bash
# yfinance 설치하지 마세요
# 대신 네이버 금융 자동 사용

# 필수 패키지만 설치
pip3 install requests beautifulsoup4 pyyaml python-dotenv --upgrade
```

**이유**:
- NAS Python 3.8에서 yfinance 최신 버전 TypeError 발생
- lxml 빌드 실패 (libxml2, libxslt 의존성)
- multitasking 패키지의 type[Thread] 문법 오류

**자동 폴백 로직**:
```python
# core/data_loader.py
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except (ImportError, TypeError) as e:
    logging.warning(f"yfinance 사용 불가: {e}")
    YFINANCE_AVAILABLE = False
    yf = None

# yfinance 없으면 자동으로 네이버 금융 사용
# 한국 주식: 네이버 금융 (빠르고 정확)
# 미국 주식: config에서 비활성화 가능
```

---

### 텔레그램 알림 실패

**증상**:
```
ERROR: 텔레그램 알림 전송 실패 (result=False)
```

**해결 방법**:

1. **환경 변수 확인**
   ```bash
   cat /volume2/homes/<username>/krx_alertor_modular/.env | grep TELEGRAM
   
   # 예상 출력:
   # TELEGRAM_ENABLED=true
   # TELEGRAM_BOT_TOKEN=123456789:...
   # TELEGRAM_CHAT_ID=123456789
   ```

2. **네트워크 확인**
   ```bash
   curl https://api.telegram.org/bot<TOKEN>/getMe
   
   # 예상 결과: {"ok":true,"result":{...}}
   ```

3. **로그 확인**
   ```bash
   tail -f /volume2/homes/<username>/krx_alertor_modular/logs/daily_regime_check.log
   ```

---

### Python 경로 오류

**증상**:
```
python3: command not found
```

**해결 방법**:

1. **Python 경로 확인**
   ```bash
   which python3
   # 예상: /usr/bin/python3
   ```

2. **Cron에서 절대 경로 사용**
   ```bash
   # Cron 편집
   crontab -e
   
   # 절대 경로 사용
   0 16 * * 1-5 cd /volume2/homes/<username>/krx_alertor_modular && /usr/bin/python3 scripts/nas/daily_regime_check.py >> logs/daily_regime_check.log 2>&1
   ```

---

### 권한 오류

**증상**:
```
Permission denied
```

**해결 방법**:

1. **파일 권한 확인**
   ```bash
   ls -la /volume2/homes/<username>/krx_alertor_modular/scripts/nas/
   ```

2. **실행 권한 부여**
   ```bash
   chmod +x /volume2/homes/<username>/krx_alertor_modular/scripts/nas/daily_regime_check.py
   ```

---

## 유지보수

### 1. 정기 업데이트

```bash
# Git Pull
cd /volume2/homes/<username>/krx_alertor_modular
git pull

# 패키지 업데이트
pip3 install --upgrade requests beautifulsoup4 pyyaml python-dotenv
```

### 2. 로그 정리

```bash
# 30일 이상 된 로그 삭제
find /volume2/homes/<username>/krx_alertor_modular/logs -name "*.log" -mtime +30 -delete

# 로그 크기 확인
du -sh /volume2/homes/<username>/krx_alertor_modular/logs
```

### 3. 디스크 공간 확인

```bash
# 디스크 사용량 확인
df -h

# 캐시 정리
rm -rf /volume2/homes/<username>/krx_alertor_modular/data/cache/ohlcv/*.parquet
```

---

## 참고 문서

- [Synology DSM 공식 문서](https://www.synology.com/en-global/support/documentation)
- [Python 3.8 문서](https://docs.python.org/3.8/)
- [문제 해결 가이드](./troubleshooting.md)
- [Cron 설정 가이드](../guides/cron-setup.md)

---

## 관련 파일

**스크립트**:
- `scripts/nas/daily_regime_check.py`
- `core/data_loader.py` (yfinance 폴백 로직)

**설정**:
- `.env` (환경 변수)
- `config/crontab.nas.txt` (Cron 예제)

**로그**:
- `logs/daily_regime_check.log`

---

**문서 통합 이력**:
- 2025-11-27: NAS_DS220J_SETUP.md, NAS_REGIME_CRON_SETUP.md, NAS_TELEGRAM_FIX.md, NAS_YFINANCE_FIX.md 통합
- 이전 문서들은 Git 이력에 보존됨
