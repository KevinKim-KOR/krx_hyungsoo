# Oracle Cloud 배포 가이드

**최종 업데이트**: 2025-11-27  
**환경**: Oracle Cloud Free Tier + Ubuntu 22.04

---

## 📋 목차

1. [개요](#개요)
2. [사전 준비](#사전-준비)
3. [VM 인스턴스 생성](#vm-인스턴스-생성)
4. [환경 구축](#환경-구축)
5. [애플리케이션 배포](#애플리케이션-배포)
6. [Cron 설정](#cron-설정)
7. [문제 해결](#문제-해결)

---

## 개요

Oracle Cloud Free Tier에 KRX Alertor를 배포하는 가이드입니다.

**배포 구성**:
- **VM**: VM.Standard.E2.1.Micro (1 OCPU, 1 GB RAM)
- **OS**: Ubuntu 22.04
- **Python**: 3.8+
- **서비스**: Daily Regime Check, US Market Monitor

**Free Tier 혜택**:
- ✅ 2개 VM 인스턴스 (Always Free)
- ✅ 100 GB Block Storage
- ✅ 10 TB 아웃바운드 트래픽/월

---

## 사전 준비

### 1. Oracle Cloud 계정

1. **가입**
   ```
   https://cloud.oracle.com/
   ```

2. **Free Tier 활성화**
   - 신용카드 등록 필요 (무료)
   - Always Free 리소스 확인

### 2. 로컬 테스트

```bash
# 로컬에서 테스트
python scripts/nas/daily_regime_check.py --dry-run
python -m core.strategy.us_market_monitor

# 예상 결과: 정상 작동
```

---

## VM 인스턴스 생성

### 1. Compute 인스턴스 생성

1. **Oracle Cloud 콘솔 접속**
   ```
   https://cloud.oracle.com/
   ```

2. **인스턴스 생성**
   ```
   메뉴 > Compute > Instances > "Create Instance"
   ```

3. **설정**
   ```
   Name: krx-alertor
   Image: Ubuntu 22.04 (Canonical)
   Shape: VM.Standard.E2.1.Micro (Free Tier)
     - 1 OCPU
     - 1 GB RAM
     - Always Free!
   
   VCN: 기본 VCN 사용
   Subnet: Public Subnet
   Public IP: Assign a public IPv4 address ✅
   
   SSH Keys:
     - Generate SSH key pair 다운로드
     - 또는 기존 public key 업로드
   ```

4. **인스턴스 생성 완료**
   ```
   Public IP 주소 확인:
   예: 123.456.789.012
   ```

### 2. SSH 접속 테스트

```bash
# SSH 키 권한 설정
chmod 600 <private-key>

# SSH 접속
ssh -i <private-key> ubuntu@<PUBLIC_IP>

# 예상 결과: 접속 성공
```

### 3. 방화벽 설정

**Oracle Cloud 방화벽**:
```
1. VCN Details > Security Lists
2. Default Security List 선택
3. "Add Ingress Rules" 클릭

규칙 추가:
- Source CIDR: 0.0.0.0/0
- Destination Port: 22 (SSH)
- Description: SSH

규칙 추가 (선택사항 - 웹 UI):
- Source CIDR: 0.0.0.0/0
- Destination Port: 8501 (Streamlit)
- Description: Streamlit Dashboard
```

**Ubuntu 방화벽**:
```bash
# SSH 접속 후
sudo ufw allow 22/tcp
sudo ufw allow 8501/tcp  # 웹 UI 사용 시
sudo ufw enable
sudo ufw status
```

---

## 환경 구축

### 1. 시스템 업데이트

```bash
sudo apt update
sudo apt upgrade -y
```

### 2. Python 설치

```bash
# Python 3.8+ 설치
sudo apt install python3 python3-pip python3-venv -y

# 버전 확인
python3 --version
# 예상: Python 3.10.x
```

### 3. Git 설치

```bash
sudo apt install git -y
git --version
```

### 4. 프로젝트 클론

```bash
# 홈 디렉토리로 이동
cd ~

# 프로젝트 클론
git clone https://github.com/<your-username>/krx_alertor_modular.git
cd krx_alertor_modular
```

### 5. 가상 환경 생성

```bash
# 가상 환경 생성
python3 -m venv venv

# 가상 환경 활성화
source venv/bin/activate

# pip 업그레이드
pip install --upgrade pip
```

### 6. 의존성 설치

```bash
# 필수 패키지만 설치 (경량)
pip install requests beautifulsoup4 pyyaml python-dotenv

# 또는 전체 설치
pip install -r requirements.txt
```

### 7. 환경 변수 설정

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
# 가상 환경 활성화
source ~/krx_alertor_modular/venv/bin/activate

# Daily Regime Check 테스트
python scripts/nas/daily_regime_check.py --dry-run

# US Market Monitor 테스트
python -m core.strategy.us_market_monitor

# 예상 결과: 정상 작동
```

### 2. 로그 디렉토리 생성

```bash
mkdir -p ~/krx_alertor_modular/logs
```

### 3. Git Pull 스크립트 생성

```bash
# Git Pull 스크립트 생성
cat > ~/krx_alertor_modular/scripts/cloud/git_pull.sh << 'EOF'
#!/bin/bash

# 프로젝트 디렉토리
PROJECT_DIR="$HOME/krx_alertor_modular"
LOG_FILE="$PROJECT_DIR/logs/git_pull.log"

# 로그 시작
echo "========================================" >> "$LOG_FILE"
echo "Git Pull: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# Git Pull
cd "$PROJECT_DIR" || exit 1
git pull >> "$LOG_FILE" 2>&1

# 결과 확인
if [ $? -eq 0 ]; then
    echo "✅ Git Pull 성공" >> "$LOG_FILE"
else
    echo "❌ Git Pull 실패" >> "$LOG_FILE"
fi

echo "" >> "$LOG_FILE"
EOF

# 실행 권한 부여
chmod +x ~/krx_alertor_modular/scripts/cloud/git_pull.sh
```

---

## Cron 설정

### 1. Cron 편집

```bash
crontab -e
```

### 2. Cron 작업 추가

```bash
# 환경 변수
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
HOME=/home/ubuntu

# Git Pull (매일 06:00)
0 6 * * * /home/ubuntu/krx_alertor_modular/scripts/cloud/git_pull.sh

# Daily Regime Check (평일 16:00 - 장 마감 후)
0 16 * * 1-5 cd /home/ubuntu/krx_alertor_modular && /home/ubuntu/krx_alertor_modular/venv/bin/python scripts/nas/daily_regime_check.py >> logs/daily_regime_check.log 2>&1

# US Market Monitor (평일 23:00 - 미국 장 마감 후)
0 23 * * 1-5 cd /home/ubuntu/krx_alertor_modular && /home/ubuntu/krx_alertor_modular/venv/bin/python -m core.strategy.us_market_monitor >> logs/us_market_monitor.log 2>&1
```

### 3. Cron 작업 확인

```bash
# Cron 목록 확인
crontab -l

# Cron 로그 확인
grep CRON /var/log/syslog | tail -20
```

### 4. 로그 확인

```bash
# Daily Regime Check 로그
tail -f ~/krx_alertor_modular/logs/daily_regime_check.log

# US Market Monitor 로그
tail -f ~/krx_alertor_modular/logs/us_market_monitor.log

# Git Pull 로그
tail -f ~/krx_alertor_modular/logs/git_pull.log
```

---

## 문제 해결

### Git Pull 충돌

**증상**:
```
error: Your local changes to the following files would be overwritten by merge:
  data/cache/ohlcv/*.parquet
Please commit your changes or stash them before you merge.
```

**해결 방법**:

1. **캐시 파일 Git 추적 중지**
   ```bash
   cd ~/krx_alertor_modular
   git rm --cached data/cache/ohlcv/*.parquet
   git commit -m "Stop tracking cache files"
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

**자세한 가이드**: [troubleshooting.md](./troubleshooting.md#git-pull-충돌)

---

### 텔레그램 알림 실패

**증상**:
```
ERROR: 텔레그램 알림 전송 실패 (result=False)
```

**해결 방법**:

1. **환경 변수 확인**
   ```bash
   cat ~/krx_alertor_modular/.env | grep TELEGRAM
   
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
   tail -f ~/krx_alertor_modular/logs/daily_regime_check.log
   ```

**자세한 가이드**: [troubleshooting.md](./troubleshooting.md#텔레그램-알림-실패)

---

### Python 패키지 오류

**증상**:
```
ModuleNotFoundError: No module named 'xxx'
```

**해결 방법**:

1. **가상 환경 활성화 확인**
   ```bash
   which python
   # 예상: /home/ubuntu/krx_alertor_modular/venv/bin/python
   ```

2. **패키지 재설치**
   ```bash
   source ~/krx_alertor_modular/venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Cron 경로 확인**
   ```bash
   # Cron에서 절대 경로 사용
   /home/ubuntu/krx_alertor_modular/venv/bin/python
   ```

---

### 메모리 부족

**증상**:
```
MemoryError
또는
Killed
```

**해결 방법**:

1. **Swap 파일 생성** (Free Tier 1GB RAM)
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

---

## 유지보수

### 1. 정기 업데이트

```bash
# Git Pull (자동 - Cron)
# 매일 06:00 자동 실행

# 수동 업데이트
cd ~/krx_alertor_modular
git pull
```

### 2. 로그 정리

```bash
# 30일 이상 된 로그 삭제
find ~/krx_alertor_modular/logs -name "*.log" -mtime +30 -delete

# 로그 크기 확인
du -sh ~/krx_alertor_modular/logs
```

### 3. 디스크 공간 확인

```bash
# 디스크 사용량 확인
df -h

# 캐시 정리
rm -rf ~/krx_alertor_modular/data/cache/ohlcv/*.parquet
```

### 4. 시스템 업데이트

```bash
# 시스템 업데이트 (월 1회)
sudo apt update
sudo apt upgrade -y
sudo apt autoremove -y
```

---

## 참고 문서

- [Oracle Cloud 공식 문서](https://docs.oracle.com/en-us/iaas/Content/home.htm)
- [Ubuntu 22.04 가이드](https://ubuntu.com/server/docs)
- [문제 해결 가이드](./troubleshooting.md)
- [Cron 설정 가이드](../guides/cron-setup.md)

---

## 관련 파일

**스크립트**:
- `scripts/cloud/git_pull.sh`
- `scripts/nas/daily_regime_check.py`
- `core/strategy/us_market_monitor.py`

**설정**:
- `.env` (환경 변수)
- `config/crontab.cloud.txt` (Cron 예제)

**로그**:
- `logs/daily_regime_check.log`
- `logs/us_market_monitor.log`
- `logs/git_pull.log`

---

**문서 통합 이력**:
- 2025-11-27: ORACLE_CLOUD_DEPLOYMENT.md, ORACLE_CLOUD_DEPLOY_GUIDE.md, ORACLE_CLOUD_GIT_PULL_FIX.md, ORACLE_CLOUD_TELEGRAM_FIX.md 통합
- 이전 문서들은 Git 이력에 보존됨
