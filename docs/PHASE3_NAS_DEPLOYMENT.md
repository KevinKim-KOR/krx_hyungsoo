# Phase 3: NAS 배포 가이드

## 개요

이 문서는 실시간 신호 생성 및 알림 시스템을 NAS에 배포하는 전체 과정을 설명합니다.

---

## 사전 준비

### 1. 환경 확인

- **NAS 모델**: Synology DS220j
- **Python 버전**: 3.8
- **프로젝트 경로**: `/volume2/homes/Hyungsoo/krx/krx_alertor_modular`

### 2. 필수 패키지 (경량 버전)

```bash
# NAS에서 설치된 패키지 확인
pip3.8 list

# 필수 패키지 (nas/requirements.txt)
pandas
numpy
pykrx
requests
PyYAML
pyarrow
```

---

## 배포 절차

### Step 1: 코드 업로드

#### 방법 A: Git Pull (권장)

```bash
# NAS SSH 접속
ssh Hyungsoo@your-nas-ip

# 프로젝트 디렉토리로 이동
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular

# 최신 코드 가져오기
git pull origin main
```

#### 방법 B: rsync (Git 미사용 시)

```powershell
# PC에서 실행
rsync -avz --exclude='.git' --exclude='__pycache__' `
  E:\AI Study\krx_alertor_modular/ `
  Hyungsoo@your-nas-ip:/volume2/homes/Hyungsoo/krx/krx_alertor_modular/
```

---

### Step 2: 환경 설정

#### 2.1 텔레그램 설정

```bash
# secret/config.yaml 생성
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
mkdir -p secret

cat > secret/config.yaml << 'EOF'
notifications:
  telegram:
    bot_token: "YOUR_BOT_TOKEN_HERE"
    chat_id: YOUR_CHAT_ID_HERE
EOF
```

#### 2.2 환경 변수 설정 (선택)

```bash
# config/env.nas.sh 생성
cat > config/env.nas.sh << 'EOF'
#!/bin/bash
export PYTHONPATH="/volume2/homes/Hyungsoo/krx/krx_alertor_modular:$PYTHONPATH"
export KRX_TELEGRAM_TOKEN="YOUR_BOT_TOKEN"
export KRX_TELEGRAM_CHAT_ID="YOUR_CHAT_ID"
EOF

chmod +x config/env.nas.sh
```

#### 2.3 디렉토리 생성

```bash
# 필요한 디렉토리 생성
mkdir -p logs
mkdir -p data/monitoring
mkdir -p data/cache
mkdir -p reports/daily
mkdir -p reports/realtime
```

---

### Step 3: 수동 테스트

#### 3.1 신호 생성 테스트

```bash
# 프로젝트 루트에서 실행
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular

# 실시간 신호 생성 및 알림
python3.8 nas/app_realtime.py
```

**예상 출력**:
```
============================================================
실시간 신호 생성 및 알림 시작
============================================================
대상 날짜: 2025-11-02
파라미터 로드: best_params.json
신호 생성 시작...
생성된 신호: 5개
신호 이력 저장...
시장 레짐 감지...
레짐: bull, 변동성=15.23%
일일 리포트 생성...
텔레그램 알림 전송...
✅ 알림 전송 성공
============================================================
작업 완료
============================================================
```

#### 3.2 로그 확인

```bash
# 최신 로그 확인
tail -f logs/realtime_signals_*.log

# 에러 확인
grep "ERROR\|❌" logs/realtime_signals_*.log
```

#### 3.3 생성된 파일 확인

```bash
# DB 파일
ls -lh data/monitoring/*.db

# 리포트 파일
ls -lh reports/daily/report_*.md

# 신호 CSV
ls -lh reports/realtime/signals_*.csv
```

---

### Step 4: Cron 자동화

#### 4.1 스크립트 실행 권한 부여

```bash
chmod +x scripts/nas/daily_realtime_signals.sh
```

#### 4.2 Cron 등록

```bash
# Cron 편집
crontab -e

# 아래 내용 추가 (평일 15:40 실행)
40 15 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && bash scripts/nas/daily_realtime_signals.sh
```

#### 4.3 Cron 확인

```bash
# 등록된 Cron 작업 확인
crontab -l

# Cron 서비스 상태 확인 (Synology)
synoservice --status crond
```

---

### Step 5: 모니터링 설정

#### 5.1 로그 정리 Cron (선택)

```bash
# 30일 이상 된 로그 자동 삭제
crontab -e

# 추가
0 2 * * * find /volume2/homes/Hyungsoo/krx/krx_alertor_modular/logs -name "*.log" -mtime +30 -delete
```

#### 5.2 주간 리포트 (선택)

```bash
# 매주 일요일 09:00 주간 요약 전송
0 9 * * 0 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python3.8 scripts/nas/weekly_report.py
```

---

## 트러블슈팅

### 1. 텔레그램 알림이 오지 않는 경우

**원인**:
- Bot Token 또는 Chat ID 오류
- 봇과 대화 시작 안 함
- 네트워크 연결 문제

**해결**:
```bash
# 설정 파일 확인
cat secret/config.yaml

# 텔레그램 API 테스트
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getMe"

# 수동 메시지 전송 테스트
python3.8 -c "
from infra.notify.telegram import send_to_telegram
send_to_telegram('테스트 메시지')
"
```

---

### 2. 신호가 생성되지 않는 경우

**원인**:
- 데이터 캐시 부족
- 파라미터 파일 없음
- 조건 미충족

**해결**:
```bash
# 데이터 캐시 확인
ls -lh data/cache/*.parquet | wc -l

# 파라미터 파일 확인
cat best_params.json

# 수동 데이터 수집
python3.8 -c "
from extensions.realtime import RealtimeDataCollector
from datetime import date, timedelta
collector = RealtimeDataCollector()
collector.update_latest(date.today() - timedelta(days=1))
"
```

---

### 3. Cron이 실행되지 않는 경우

**원인**:
- 경로 오류
- 실행 권한 없음
- Python 경로 오류

**해결**:
```bash
# 스크립트 실행 권한 확인
ls -l scripts/nas/daily_realtime_signals.sh

# 권한 부여
chmod +x scripts/nas/daily_realtime_signals.sh

# 절대 경로 사용 확인
which python3.8

# Cron 로그 확인 (Synology)
cat /var/log/cron.log | grep realtime
```

---

### 4. Import 오류

**원인**:
- PYTHONPATH 미설정
- 모듈 누락

**해결**:
```bash
# PYTHONPATH 설정
export PYTHONPATH="/volume2/homes/Hyungsoo/krx/krx_alertor_modular:$PYTHONPATH"

# 모듈 import 테스트
python3.8 -c "
import sys
sys.path.insert(0, '/volume2/homes/Hyungsoo/krx/krx_alertor_modular')
from extensions.realtime import RealtimeSignalGenerator
print('✅ Import 성공')
"
```

---

## 성능 최적화

### 1. 캐시 관리

```bash
# 오래된 캐시 정리 (90일 이상)
find data/cache -name "*.parquet" -mtime +90 -delete

# 캐시 크기 확인
du -sh data/cache
```

### 2. DB 최적화

```bash
# SQLite DB 최적화
python3.8 -c "
import sqlite3
conn = sqlite3.connect('data/monitoring/signals.db')
conn.execute('VACUUM')
conn.close()
print('✅ DB 최적화 완료')
"
```

---

## 백업 전략

### 1. DB 백업

```bash
# 일일 백업 스크립트
cat > scripts/nas/backup_db.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/volume2/homes/Hyungsoo/krx/backups"
DATE=$(date +%Y%m%d)

mkdir -p $BACKUP_DIR

cp data/monitoring/signals.db $BACKUP_DIR/signals_$DATE.db
cp data/monitoring/performance.db $BACKUP_DIR/performance_$DATE.db

# 30일 이상 된 백업 삭제
find $BACKUP_DIR -name "*.db" -mtime +30 -delete
EOF

chmod +x scripts/nas/backup_db.sh

# Cron 등록 (매일 새벽 3시)
# 0 3 * * * /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/nas/backup_db.sh
```

---

## 모니터링 대시보드 (선택)

### 간단한 상태 확인 스크립트

```bash
cat > scripts/nas/status.sh << 'EOF'
#!/bin/bash
echo "=========================================="
echo "실시간 신호 시스템 상태"
echo "=========================================="

# 최근 실행 로그
echo -e "\n최근 실행:"
ls -lt logs/realtime_signals_*.log | head -1

# DB 크기
echo -e "\nDB 크기:"
du -h data/monitoring/*.db

# 최근 신호 수
echo -e "\n최근 신호 (최근 7일):"
python3.8 -c "
from extensions.monitoring import SignalTracker
from datetime import date, timedelta
tracker = SignalTracker()
stats = tracker.get_signal_stats(days=7)
print(f'총 신호: {stats[\"total_signals\"]}개')
print(f'매수: {stats[\"buy_count\"]}개')
print(f'매도: {stats[\"sell_count\"]}개')
"

echo "=========================================="
EOF

chmod +x scripts/nas/status.sh
```

**실행**:
```bash
bash scripts/nas/status.sh
```

---

## 체크리스트

### 배포 전
- [ ] Git pull 또는 rsync로 코드 업로드
- [ ] `secret/config.yaml` 텔레그램 설정
- [ ] 필요한 디렉토리 생성
- [ ] 스크립트 실행 권한 부여

### 배포 후
- [ ] 수동 테스트 성공
- [ ] 텔레그램 알림 수신 확인
- [ ] Cron 등록 완료
- [ ] 로그 파일 생성 확인
- [ ] DB 파일 생성 확인

### 운영 중
- [ ] 매일 텔레그램 알림 수신
- [ ] 주간 로그 확인
- [ ] 월간 DB 백업
- [ ] 분기별 성과 리뷰

---

## 참고 자료

- **프로젝트 문서**: `docs/NEW/README.md`
- **텔레그램 설정**: `docs/TELEGRAM_SETUP.md`
- **Cron 설정**: `scripts/nas/crontab_realtime.txt`
- **개발 규칙**: `docs/DEVELOPMENT_RULES.md`

---

## 문의

문제 발생 시:
1. 로그 파일 확인 (`logs/realtime_signals_*.log`)
2. 텔레그램 에러 알림 확인
3. 수동 실행으로 재현
4. GitHub Issues 등록
