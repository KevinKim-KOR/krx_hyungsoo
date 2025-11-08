# NAS 스케줄러 트러블슈팅 가이드

## 🔍 알림 발송 실패 디버깅

### 1단계: 기본 정보 확인

#### 1.1 스케줄러 실행 여부 확인

**Synology DSM → 제어판 → 작업 스케줄러**

확인 사항:
- [ ] 작업이 "활성화" 상태인가?
- [ ] 마지막 실행 시간이 표시되는가?
- [ ] 실행 결과가 "정상" 또는 "비정상"인가?

**스크린샷 필요**:
- 작업 스케줄러 목록 화면
- 해당 작업의 상세 정보

---

#### 1.2 작업 실행 로그 확인

**방법 1: DSM 웹 UI**
```
작업 스케줄러 → 해당 작업 선택 → "실행 결과" 탭
```

**방법 2: SSH 접속**
```bash
# Synology 시스템 로그
sudo cat /var/log/messages | grep -i "cron\|task"

# 최근 100줄
sudo tail -100 /var/log/messages
```

---

### 2단계: 수동 실행 테스트

#### 2.1 SSH로 접속
```bash
ssh admin@nas-ip
# 또는
ssh Hyungsoo@nas-ip
```

#### 2.2 프로젝트 디렉토리 이동
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
pwd  # 경로 확인
ls -la  # 파일 목록 확인
```

#### 2.3 Python 경로 확인
```bash
# Python 3.8 위치 확인
which python3.8
# 출력 예: /usr/local/bin/python3.8 또는 /usr/bin/python3.8

# Python 버전 확인
python3.8 --version
```

#### 2.4 수동 실행 (각 스크립트별)

**장 시작 알림**
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
python3.8 scripts/nas/market_open_alert.py

# 실행 결과 확인
echo $?  # 0이면 성공, 0이 아니면 실패
```

**상승 ETF 알림**
```bash
python3.8 scripts/nas/rising_etf_alert.py
echo $?
```

**레짐 변경 알림**
```bash
python3.8 scripts/nas/regime_change_alert.py
echo $?
```

**EoD 신호**
```bash
bash scripts/nas/daily_realtime_signals.sh
echo $?
```

---

### 3단계: 로그 파일 확인

#### 3.1 로그 디렉토리 확인
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular

# 로그 디렉토리 존재 확인
ls -la logs/

# 최신 로그 파일 확인
ls -lt logs/ | head -10

# 로그 파일이 없다면 생성 권한 확인
ls -ld logs/
```

#### 3.2 로그 파일 읽기
```bash
# 실시간 신호 로그
tail -100 logs/realtime_signals_*.log

# 에러만 필터링
grep -i "error\|fail\|exception" logs/*.log

# 오늘 날짜 로그
grep "$(date +%Y-%m-%d)" logs/*.log
```

#### 3.3 로그가 없는 경우
```bash
# 로그 디렉토리 생성
mkdir -p logs

# 권한 설정
chmod 755 logs

# 테스트 로그 작성
echo "test" > logs/test.log
cat logs/test.log
rm logs/test.log
```

---

### 4단계: 텔레그램 설정 확인

#### 4.1 설정 파일 확인
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular

# secret/config.yaml 존재 확인
ls -la secret/config.yaml

# 파일 내용 확인 (민감 정보 주의)
cat secret/config.yaml
```

**필요한 설정**:
```yaml
telegram:
  bot_token: "YOUR_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"
```

#### 4.2 텔레그램 연결 테스트
```bash
# Python으로 직접 테스트
python3.8 << 'EOF'
import sys
from pathlib import Path
sys.path.insert(0, '/volume2/homes/Hyungsoo/krx/krx_alertor_modular')

from extensions.notification.telegram_sender import TelegramSender

sender = TelegramSender()
result = sender.send_custom("🧪 테스트 메시지", parse_mode='Markdown')
print(f"전송 결과: {result}")
EOF
```

---

### 5단계: 환경 변수 확인

#### 5.1 Cron 환경 vs SSH 환경

**문제**: Cron 실행 시 환경 변수가 다름

**확인 방법**:
```bash
# SSH 환경
echo $PATH
echo $PYTHONPATH

# Cron 환경 (테스트 작업 생성)
# 작업 스케줄러에서 다음 명령 실행:
# env > /volume2/homes/Hyungsoo/krx/cron_env.txt

# 결과 확인
cat /volume2/homes/Hyungsoo/krx/cron_env.txt
```

---

### 6단계: 권한 확인

#### 6.1 파일 실행 권한
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular

# Python 스크립트 권한
ls -la scripts/nas/*.py

# 실행 권한 추가 (필요시)
chmod +x scripts/nas/*.py

# Bash 스크립트 권한
ls -la scripts/nas/*.sh
chmod +x scripts/nas/*.sh
```

#### 6.2 디렉토리 권한
```bash
# 프로젝트 루트 권한
ls -ld /volume2/homes/Hyungsoo/krx/krx_alertor_modular

# 하위 디렉토리 권한
ls -la /volume2/homes/Hyungsoo/krx/krx_alertor_modular/
```

---

## 📋 정보 수집 체크리스트

디버깅을 위해 다음 정보를 수집해주세요:

### 필수 정보
- [ ] **작업 스케줄러 스크린샷** (실행 결과 포함)
- [ ] **수동 실행 결과** (각 스크립트별)
  ```bash
  python3.8 scripts/nas/market_open_alert.py 2>&1 | tee manual_test.log
  ```
- [ ] **로그 파일 내용** (있다면)
  ```bash
  tail -100 logs/*.log
  ```
- [ ] **Python 경로**
  ```bash
  which python3.8
  python3.8 --version
  ```

### 추가 정보
- [ ] **환경 변수**
  ```bash
  echo $PATH
  echo $PYTHONPATH
  ```
- [ ] **텔레그램 설정**
  ```bash
  cat secret/config.yaml
  ```
- [ ] **파일 권한**
  ```bash
  ls -la scripts/nas/
  ```
- [ ] **디스크 공간**
  ```bash
  df -h
  ```

---

## 🔧 일반적인 문제 및 해결

### 문제 1: 로그 파일이 생성되지 않음

**원인**: 로그 디렉토리 권한 또는 경로 문제

**해결**:
```bash
# 로그 디렉토리 생성
mkdir -p /volume2/homes/Hyungsoo/krx/krx_alertor_modular/logs

# 권한 설정
chmod 755 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/logs

# 소유자 확인
ls -ld /volume2/homes/Hyungsoo/krx/krx_alertor_modular/logs
```

---

### 문제 2: Python 모듈 import 실패

**원인**: PYTHONPATH 미설정

**해결**: 스크립트 수정
```python
# 각 Python 스크립트 상단에 추가
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
```

---

### 문제 3: 텔레그램 전송 실패

**원인**: 
- Bot Token 또는 Chat ID 오류
- 네트워크 연결 문제

**해결**:
```bash
# 텔레그램 API 테스트
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/sendMessage" \
  -d "chat_id=<YOUR_CHAT_ID>" \
  -d "text=테스트 메시지"
```

---

### 문제 4: 데이터 파일 없음

**원인**: DB 파일 또는 데이터 파일 부재

**해결**:
```bash
# DB 파일 확인
ls -la data/monitoring/*.db

# DB 파일이 없다면 생성
python3.8 << 'EOF'
from extensions.monitoring import SignalTracker, PerformanceTracker
SignalTracker()
PerformanceTracker()
print("DB 초기화 완료")
EOF
```

---

### 문제 5: 시간대 문제

**원인**: NAS 시간대 설정

**확인**:
```bash
# 현재 시간 확인
date

# 시간대 확인
timedatectl
# 또는
cat /etc/timezone
```

**해결**: DSM → 제어판 → 지역 옵션 → 시간대 확인

---

## 🚨 긴급 디버깅 스크립트

로그가 없을 때 사용할 디버깅 스크립트를 생성하겠습니다.
