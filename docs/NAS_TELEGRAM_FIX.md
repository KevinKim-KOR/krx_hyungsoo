# NAS 텔레그램 알림 문제 해결 가이드

## 📋 문제 증상
- 아침 장 시작 알림(09:00)이 오지 않음
- crontab 스케줄은 설정되어 있음
- 수동 실행 시에는 정상 작동

## 🔍 원인 분석

### 1. Crontab 환경 변수 문제
**문제**: crontab은 최소한의 환경만 제공하며, 사용자 환경 변수를 자동으로 로드하지 않음

**영향받는 스크립트**:
- `market_open_alert.py` (09:00)
- `intraday_alert.py` (10:00, 11:00, 13:00, 14:00)
- `daily_report_alert.py` (16:00)
- `weekly_report_alert.py` (토요일 10:00)

### 2. 환경 변수 로드 방식 차이
```python
# ❌ 환경 변수에 의존 (crontab에서 실패)
bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
chat_id = os.getenv('TELEGRAM_CHAT_ID')

# ✅ 설정 파일에서 직접 로드 (crontab에서도 작동)
from extensions.notification.telegram_sender import TelegramSender
sender = TelegramSender()  # secret/config.yaml 자동 로드
```

## 🔧 해결 방법

### Option 1: Crontab에서 환경 변수 로드 (권장)

#### 1단계: 수정된 crontab 적용

```bash
# NAS SSH 접속
ssh admin@your-nas-ip

# 현재 crontab 백업
crontab -l > ~/crontab_backup_$(date +%Y%m%d).txt

# crontab 편집
crontab -e
```

#### 2단계: 다음 내용으로 교체

```cron
# ============================================
# KRX Alertor 자동화 스케줄 (2025-11-24 수정)
# ============================================
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
TZ=Asia/Seoul
PROJECT_ROOT=/volume2/homes/Hyungsoo/krx/krx_alertor_modular

# 평일 알림
# --------------------------------------------

# 09:00 - 장시작 알림
0 9 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && source config/env.nas.sh && python3.8 scripts/nas/market_open_alert.py >> logs/cron_market_open.log 2>&1

# 10:00, 11:00, 13:00, 14:00 - 장중 알림
0 10,11,13,14 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && source config/env.nas.sh && python3.8 scripts/nas/intraday_alert.py >> logs/cron_intraday.log 2>&1

# 15:30 - 손절 모니터링
30 15 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && source config/env.nas.sh && bash scripts/linux/jobs/stop_loss_check.sh >> logs/cron_stop_loss.log 2>&1

# 16:00 - 일일 종합 리포트
0 16 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && source config/env.nas.sh && bash scripts/linux/jobs/daily_scan_notify.sh >> logs/cron_daily_report.log 2>&1

# 주말 알림
# --------------------------------------------

# 토요일 10:00 - 주간 리포트
0 10 * * 6 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && source config/env.nas.sh && python3.8 scripts/nas/weekly_report_alert.py >> logs/cron_weekly_report.log 2>&1
```

**주요 변경 사항**:
- ✅ 모든 작업에 `source config/env.nas.sh` 추가
- ✅ 각 작업별 로그 파일 분리 (`>> logs/cron_*.log 2>&1`)
- ✅ SHELL, PATH, TZ 환경 변수 명시

#### 3단계: 저장 및 확인

```bash
# 저장 (vi 에디터)
:wq

# 적용 확인
crontab -l

# 로그 디렉토리 확인
ls -lh /volume2/homes/Hyungsoo/krx/krx_alertor_modular/logs/
```

### Option 2: 스크립트 수정 (대안)

각 Python 스크립트에서 환경 변수 대신 설정 파일 직접 로드:

```python
# ❌ 기존 방식
from dotenv import load_dotenv
load_dotenv()
bot_token = os.getenv('TELEGRAM_BOT_TOKEN')

# ✅ 수정 방식
from extensions.notification.telegram_sender import TelegramSender
sender = TelegramSender()  # secret/config.yaml 자동 로드
```

## 🧪 테스트

### 1. 텔레그램 연결 테스트

```bash
# NAS SSH 접속
ssh admin@your-nas-ip

# 프로젝트 디렉토리로 이동
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular

# 환경 변수 로드
source config/env.nas.sh

# 텔레그램 연결 테스트
python3.8 scripts/nas/test_telegram.py
```

**예상 출력**:
```
✅ TelegramSender 초기화 성공
✅ 메시지 전송 성공!
```

### 2. 장 시작 알림 수동 테스트

```bash
# 환경 변수 로드
source config/env.nas.sh

# 장 시작 알림 실행
python3.8 scripts/nas/market_open_alert.py
```

### 3. Crontab 로그 확인

```bash
# 최신 로그 확인
tail -f /volume2/homes/Hyungsoo/krx/krx_alertor_modular/logs/cron_market_open.log

# 모든 cron 로그 확인
ls -lht /volume2/homes/Hyungsoo/krx/krx_alertor_modular/logs/cron_*.log | head -10
```

### 4. 다음 실행 대기

```bash
# 다음 실행 시간 확인
date
# 예: 2025-11-25 08:55:00 (평일 아침)

# 09:00 이후 로그 확인
tail -20 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/logs/cron_market_open.log
```

## 📊 로그 분석

### 정상 로그 예시

```
========================================
[2025-11-25 09:00:01] 장 시작 알림
========================================
✅ 장 시작 알림 전송 성공
```

### 오류 로그 예시

```
❌ 텔레그램 설정 없음 (.env 파일 확인)
⚠️ 텔레그램 설정 없음 - 콘솔 출력만
```

**원인**: 환경 변수가 로드되지 않음
**해결**: crontab에 `source config/env.nas.sh` 추가

## 🔍 추가 진단

### 환경 변수 확인

```bash
# NAS SSH 접속 후
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
source config/env.nas.sh

# 환경 변수 출력
echo "TG_TOKEN: ${TG_TOKEN:0:10}..."
echo "TG_CHAT_ID: $TG_CHAT_ID"
echo "TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN:0:10}..."
echo "TELEGRAM_CHAT_ID: $TELEGRAM_CHAT_ID"
```

**예상 출력**:
```
TG_TOKEN: 8216278192...
TG_CHAT_ID: 7457035904
TELEGRAM_BOT_TOKEN: 8216278192...
TELEGRAM_CHAT_ID: 7457035904
```

### 설정 파일 확인

```bash
# secret/config.yaml 확인
cat secret/config.yaml | grep -A 5 telegram
```

**예상 출력**:
```yaml
telegram:
  bot_token: "8216278192:AAFLuiVI8hrWr86uV2zs9gMLrTcZdO9tGyk"
  chat_id: 7457035904
```

## 📝 체크리스트

- [ ] NAS SSH 접속 가능
- [ ] crontab 백업 완료
- [ ] 수정된 crontab 적용
- [ ] `config/env.nas.sh` 파일 존재 확인
- [ ] `secret/config.yaml` 파일 존재 확인
- [ ] 텔레그램 연결 테스트 성공
- [ ] 장 시작 알림 수동 테스트 성공
- [ ] 로그 파일 생성 확인
- [ ] 다음 평일 09:00 알림 수신 확인

## 🚨 긴급 복구

만약 수정 후에도 문제가 계속되면:

```bash
# 1. 백업에서 복구
crontab ~/crontab_backup_YYYYMMDD.txt

# 2. 수동 실행으로 임시 대응
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
source config/env.nas.sh
python3.8 scripts/nas/market_open_alert.py
```

## 📞 문제 지속 시 확인 사항

1. **네트워크 연결**: NAS가 인터넷에 연결되어 있는가?
2. **텔레그램 API**: api.telegram.org 접근 가능한가?
3. **Bot Token**: 봇이 차단되지 않았는가?
4. **Chat ID**: 사용자가 봇과 대화를 시작했는가?
5. **시스템 시간**: NAS 시간이 정확한가? (`date` 명령으로 확인)

## 📚 참고 문서

- `config/crontab.nas.txt` - 원본 crontab 설정
- `config/crontab.nas.fixed.txt` - 수정된 crontab 설정
- `config/env.nas.sh` - NAS 환경 변수 설정
- `scripts/nas/test_telegram.py` - 텔레그램 연결 테스트
- `docs/NAS_REGIME_CRON_SETUP.md` - Cron 설정 가이드

## 🎯 요약

**핵심 문제**: Crontab에서 환경 변수가 로드되지 않음

**해결책**: 모든 cron 작업에 `source config/env.nas.sh` 추가

**테스트**: `python3.8 scripts/nas/test_telegram.py`

**확인**: 다음 평일 09:00에 텔레그램 알림 수신
