# 텔레그램 알림 설정 가이드

## 1. 사전 준비

### 1.1 텔레그램 봇 생성 (이미 완료된 경우 스킵)
1. 텔레그램에서 `@BotFather` 검색
2. `/newbot` 명령 실행
3. 봇 이름 및 username 설정
4. **Bot Token** 저장

### 1.2 Chat ID 확인
1. 생성한 봇과 대화 시작
2. 아무 메시지 전송
3. 브라우저에서 확인:
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
4. `chat.id` 값 확인 및 저장

---

## 2. 설정 파일 구성

### 2.1 secret/config.yaml 생성
```yaml
# secret/config.yaml
notifications:
  telegram:
    bot_token: "YOUR_BOT_TOKEN_HERE"
    chat_id: YOUR_CHAT_ID_HERE
```

### 2.2 환경 변수 설정 (선택)
```bash
# config/env.nas.sh
export KRX_TELEGRAM_TOKEN="YOUR_BOT_TOKEN"
export KRX_TELEGRAM_CHAT_ID="YOUR_CHAT_ID"
```

---

## 3. 사용 방법

### 3.1 PC에서 테스트
```bash
# 매매 신호 스캔 + 텔레그램 알림
python pc/cli.py scan --date auto --notify

# 백테스트 후 수동 알림
python -c "
from infra.notify.telegram import send_to_telegram
send_to_telegram('*테스트 메시지*\n백테스트 완료!')
"
```

### 3.2 NAS에서 자동화

#### 수동 실행 테스트
```bash
# NAS SSH 접속 후
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular

# 장마감 신호 스캔 + 알림
bash scripts/linux/jobs/daily_scan_notify.sh

# 주간 백테스트 리포트
bash scripts/linux/jobs/weekly_backtest_report.sh
```

#### Cron 자동화 설정
```bash
# Cron 작업 설치
bash scripts/linux/setup_cron.sh

# 설치 확인
crontab -l

# 로그 확인
tail -f logs/daily_scan_*.log
```

---

## 4. Cron 스케줄

### 4.1 장마감 신호 알림
- **시간**: 평일 18:00 (장마감 후)
- **작업**: 매매 신호 스캔 및 텔레그램 알림
- **스크립트**: `scripts/linux/jobs/daily_scan_notify.sh`

```cron
0 18 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && bash scripts/linux/jobs/daily_scan_notify.sh
```

### 4.2 주간 백테스트 리포트
- **시간**: 매주 일요일 09:00
- **작업**: 주간 백테스트 실행 및 리포트 전송
- **스크립트**: `scripts/linux/jobs/weekly_backtest_report.sh`

```cron
0 9 * * 0 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && bash scripts/linux/jobs/weekly_backtest_report.sh
```

---

## 5. 알림 메시지 포맷

### 5.1 장마감 신호 알림
```
*[장마감] 매매 신호 알림*

📅 날짜: 2024-12-31
📊 신호 수: 5개

1. `069500`: *BUY*
   신뢰도: 75.3% | 가격: 30,500원
2. `091160`: *BUY*
   신뢰도: 68.2% | 가격: 15,200원
...
```

### 5.2 주간 백테스트 리포트
```
*[주간 백테스트 리포트]*

기간: 2024-12-24 ~ 2024-12-31

```
============================================================
백테스트 성과 요약
============================================================

## 수익률
총 수익률:              5.20%
연율화 수익률:          12.30%
...
```
```

---

## 6. 트러블슈팅

### 6.1 알림이 오지 않는 경우
1. Bot Token 및 Chat ID 확인
2. 봇과 대화 시작 여부 확인
3. 네트워크 연결 확인
4. 로그 파일 확인:
   ```bash
   tail -f logs/daily_scan_*.log
   ```

### 6.2 Cron 작업이 실행되지 않는 경우
1. Cron 등록 확인:
   ```bash
   crontab -l
   ```
2. 스크립트 실행 권한 확인:
   ```bash
   chmod +x scripts/linux/jobs/*.sh
   ```
3. 경로 확인 (절대 경로 사용)
4. Cron 로그 확인:
   ```bash
   grep CRON /var/log/syslog  # Ubuntu/Debian
   ```

### 6.3 Python 모듈 import 오류
1. 프로젝트 루트에서 실행 확인
2. PYTHONPATH 설정:
   ```bash
   export PYTHONPATH=/volume2/homes/Hyungsoo/krx/krx_alertor_modular:$PYTHONPATH
   ```

---

## 7. 고급 설정

### 7.1 알림 메시지 커스터마이징
`infra/notify/telegram.py`의 `send_alerts` 함수 수정

### 7.2 알림 조건 변경
`pc/cli.py`의 `cmd_scan` 함수에서 `--min-confidence` 조정

### 7.3 추가 알림 추가
```python
from infra.notify.telegram import send_to_telegram

# 커스텀 메시지
message = "*[긴급] 시장 급등*\n\nKOSPI: +3.5%"
send_to_telegram(message)
```

---

## 8. 참고 자료

- 텔레그램 Bot API: https://core.telegram.org/bots/api
- Cron 표현식: https://crontab.guru/
- 프로젝트 문서: `docs/NEW/README.md`
