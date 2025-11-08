# NAS 배포 가이드

**작성일**: 2025-11-08  
**대상**: Synology NAS DS220j  
**목적**: 자동화 시스템 배포 및 텔레그램 알림 설정

---

## 📋 목차

1. [사전 준비](#사전-준비)
2. [파일 전송](#파일-전송)
3. [환경 설정](#환경-설정)
4. [텔레그램 봇 설정](#텔레그램-봇-설정)
5. [스케줄러 설정](#스케줄러-설정)
6. [테스트](#테스트)
7. [문제 해결](#문제-해결)

---

## 1. 사전 준비

### 1.1 필요한 패키지 (NAS)

```bash
# NAS SSH 접속
ssh Hyungsoo@[NAS_IP]

# Python 3.8 확인
python3 --version

# 필요한 패키지 설치
pip3 install --user pandas numpy pykrx
```

### 1.2 디렉토리 구조

```
/volume2/homes/Hyungsoo/krx/krx_alertor_modular/
├── core/                      # 공통 모듈
├── extensions/automation/     # 자동화 모듈
├── data/
│   ├── universe/             # 유니버스 파일
│   └── output/               # 결과 파일
├── logs/                     # 로그 파일
└── scripts/automation/       # 실행 스크립트
```

---

## 2. 파일 전송

### 2.1 PC → NAS 파일 동기화

**Windows PC에서 실행**:

```powershell
# rsync 사용 (Git Bash 또는 WSL)
rsync -avz --exclude='*.pyc' --exclude='__pycache__' \
  "e:/AI Study/krx_alertor_modular/core/" \
  Hyungsoo@[NAS_IP]:/volume2/homes/Hyungsoo/krx/krx_alertor_modular/core/

rsync -avz --exclude='*.pyc' --exclude='__pycache__' \
  "e:/AI Study/krx_alertor_modular/extensions/" \
  Hyungsoo@[NAS_IP]:/volume2/homes/Hyungsoo/krx/krx_alertor_modular/extensions/

rsync -avz \
  "e:/AI Study/krx_alertor_modular/data/universe/" \
  Hyungsoo@[NAS_IP]:/volume2/homes/Hyungsoo/krx/krx_alertor_modular/data/universe/

rsync -avz \
  "e:/AI Study/krx_alertor_modular/scripts/automation/" \
  Hyungsoo@[NAS_IP]:/volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/automation/
```

**또는 WinSCP 사용**:
1. WinSCP 실행
2. NAS 접속
3. 해당 폴더 드래그 앤 드롭

---

## 3. 환경 설정

### 3.1 환경 변수 설정

NAS에서 `.env` 파일 생성:

```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
nano .env
```

내용:
```bash
# 텔레그램 설정
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# 데이터 경로
DATA_DIR=/volume2/homes/Hyungsoo/krx/krx_alertor_modular/data
LOG_DIR=/volume2/homes/Hyungsoo/krx/krx_alertor_modular/logs
```

저장: `Ctrl+O`, `Enter`, `Ctrl+X`

---

## 4. 텔레그램 봇 설정

### 4.1 봇 생성

1. **BotFather와 대화**
   - 텔레그램에서 `@BotFather` 검색
   - `/newbot` 명령 실행
   - 봇 이름 입력: `KRX Alertor Bot`
   - 봇 사용자명 입력: `krx_alertor_bot` (고유해야 함)
   - 봇 토큰 받기: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`

2. **Chat ID 확인**
   - 봇과 대화 시작 (`/start` 전송)
   - 브라우저에서 접속:
     ```
     https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
     ```
   - `chat.id` 값 확인

3. **.env 파일 업데이트**
   ```bash
   TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   TELEGRAM_CHAT_ID=123456789
   ```

### 4.2 텔레그램 봇 패키지 설치 (선택)

실제 텔레그램 알림을 사용하려면:

```bash
pip3 install --user python-telegram-bot
```

---

## 5. 스케줄러 설정

### 5.1 일일 리포트 스크립트

`scripts/automation/daily_alert.sh` 생성:

```bash
#!/bin/bash

# 프로젝트 경로
PROJECT_DIR="/volume2/homes/Hyungsoo/krx/krx_alertor_modular"
cd $PROJECT_DIR

# 환경 변수 로드
source .env

# Python 경로
PYTHON="/usr/bin/python3"

# 로그 디렉토리
LOG_DIR="$PROJECT_DIR/logs/automation"
mkdir -p $LOG_DIR

# 로그 파일
LOG_FILE="$LOG_DIR/daily_alert_$(date +%Y%m%d).log"

# 일일 리포트 실행
echo "=== 일일 리포트 시작: $(date) ===" >> $LOG_FILE
$PYTHON $PROJECT_DIR/scripts/automation/run_daily_report.py >> $LOG_FILE 2>&1
echo "=== 일일 리포트 완료: $(date) ===" >> $LOG_FILE
```

실행 권한 부여:
```bash
chmod +x scripts/automation/daily_alert.sh
```

### 5.2 일일 리포트 Python 스크립트

`scripts/automation/run_daily_report.py` 생성:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
일일 리포트 실행 스크립트
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import os
from datetime import date
from extensions.automation.daily_report import DailyReport

# 환경 변수 로드
bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
chat_id = os.getenv('TELEGRAM_CHAT_ID')

# 리포트 생성
reporter = DailyReport(
    telegram_enabled=True,  # 텔레그램 활성화
    bot_token=bot_token,
    chat_id=chat_id
)

# 실행
report = reporter.generate_report(
    target_date=date.today(),
    current_holdings=[],  # 실제 보유 종목 입력
    portfolio_value=None,  # 실제 포트폴리오 가치 입력
    initial_capital=10000000
)

print(report)
```

### 5.3 주간 리포트 스크립트

`scripts/automation/weekly_alert.sh` 생성:

```bash
#!/bin/bash

PROJECT_DIR="/volume2/homes/Hyungsoo/krx/krx_alertor_modular"
cd $PROJECT_DIR
source .env

PYTHON="/usr/bin/python3"
LOG_DIR="$PROJECT_DIR/logs/automation"
mkdir -p $LOG_DIR
LOG_FILE="$LOG_DIR/weekly_alert_$(date +%Y%m%d).log"

echo "=== 주간 리포트 시작: $(date) ===" >> $LOG_FILE
$PYTHON $PROJECT_DIR/scripts/automation/run_weekly_report.py >> $LOG_FILE 2>&1
echo "=== 주간 리포트 완료: $(date) ===" >> $LOG_FILE
```

실행 권한:
```bash
chmod +x scripts/automation/weekly_alert.sh
```

### 5.4 Cron 설정

NAS에서 crontab 편집:

```bash
crontab -e
```

추가할 내용:

```bash
# 일일 리포트: 평일 오후 4시 (장 마감 후)
0 16 * * 1-5 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/automation/daily_alert.sh

# 주간 리포트: 토요일 오전 10시
0 10 * * 6 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/automation/weekly_alert.sh
```

저장 후 cron 재시작:
```bash
# Synology DSM 7.x
sudo synoservicectl --restart crond
```

---

## 6. 테스트

### 6.1 수동 실행 테스트

```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular

# 일일 리포트 테스트
./scripts/automation/daily_alert.sh

# 주간 리포트 테스트
./scripts/automation/weekly_alert.sh
```

### 6.2 로그 확인

```bash
# 최신 로그 확인
tail -f logs/automation/daily_alert_$(date +%Y%m%d).log

# 에러 확인
grep -i error logs/automation/*.log
```

### 6.3 텔레그램 수신 확인

- 텔레그램 앱에서 봇으로부터 메시지 수신 확인
- 메시지 형식 및 내용 확인

---

## 7. 문제 해결

### 7.1 텔레그램 메시지가 안 오는 경우

**원인 1**: 봇 토큰 또는 Chat ID 오류
```bash
# .env 파일 확인
cat .env

# 환경 변수 로드 확인
source .env
echo $TELEGRAM_BOT_TOKEN
echo $TELEGRAM_CHAT_ID
```

**원인 2**: python-telegram-bot 미설치
```bash
pip3 install --user python-telegram-bot
```

**원인 3**: 네트워크 문제
```bash
# 텔레그램 API 접속 테스트
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe
```

### 7.2 Cron이 실행되지 않는 경우

**확인 1**: Cron 서비스 상태
```bash
sudo synoservicectl --status crond
```

**확인 2**: Cron 로그
```bash
cat /var/log/cron.log | grep daily_alert
```

**확인 3**: 스크립트 권한
```bash
ls -l scripts/automation/*.sh
# -rwxr-xr-x 여야 함
```

### 7.3 Python 모듈 import 에러

**해결 1**: PYTHONPATH 설정
```bash
# .env 파일에 추가
export PYTHONPATH=/volume2/homes/Hyungsoo/krx/krx_alertor_modular:$PYTHONPATH
```

**해결 2**: 패키지 재설치
```bash
pip3 install --user --upgrade pandas numpy pykrx
```

---

## 8. 실행 시간표

### 평일 (월~금)

| 시간 | 작업 | 설명 |
|------|------|------|
| 16:00 | 일일 리포트 | 장 마감 후 레짐 분석 및 매매 신호 생성 |

### 주말 (토요일)

| 시간 | 작업 | 설명 |
|------|------|------|
| 10:00 | 주간 리포트 | 주간 성과 요약 및 다음 주 전망 |

---

## 9. 알림 예시

### 일일 리포트 알림

```
📊 일일 투자 리포트
📅 날짜: 2025년 11월 08일

💼 포트폴리오 현황
  평가액: 11,500,000원
  수익: +1,500,000원 (+15.00%)
  보유 종목: 3개

🎯 시장 레짐
  📈 현재 레짐: 상승장
  📊 신뢰도: 100.0%
  💪 포지션 비율: 120%

📈 매매 신호
  🟢 매수: 7개
     1. 396500 (MAPS: 34.55)
     2. 091230 (MAPS: 33.61)
     ...
  🔴 매도: 없음
```

### 레짐 변경 알림

```
🔄 레짐 변경 감지!

📅 날짜: 2025-11-08
➡️ 이전: 중립장
📈 현재: 상승장
📊 신뢰도: 85.0%

전략을 조정하세요!
```

---

## 10. 유지보수

### 10.1 정기 점검 (주 1회)

```bash
# 로그 파일 크기 확인
du -sh logs/automation/

# 오래된 로그 삭제 (30일 이상)
find logs/automation/ -name "*.log" -mtime +30 -delete

# 데이터베이스 백업
cp data/output/backtest_history.db data/output/backtest_history_$(date +%Y%m%d).db
```

### 10.2 업데이트

PC에서 코드 수정 후:

```powershell
# PC → NAS 동기화
rsync -avz --exclude='*.pyc' --exclude='__pycache__' \
  "e:/AI Study/krx_alertor_modular/extensions/" \
  Hyungsoo@[NAS_IP]:/volume2/homes/Hyungsoo/krx/krx_alertor_modular/extensions/
```

---

## 11. 참고 자료

- [Synology DSM 사용자 가이드](https://www.synology.com/ko-kr/support/documentation)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [python-telegram-bot 문서](https://python-telegram-bot.org/)

---

**배포 완료 체크리스트**:

- [ ] 파일 전송 완료
- [ ] .env 파일 설정
- [ ] 텔레그램 봇 생성 및 토큰 확인
- [ ] 스크립트 실행 권한 부여
- [ ] Cron 설정
- [ ] 수동 테스트 성공
- [ ] 텔레그램 알림 수신 확인
- [ ] 로그 파일 정상 생성 확인

---

**문의**: 문제 발생 시 로그 파일 확인 후 디버깅
