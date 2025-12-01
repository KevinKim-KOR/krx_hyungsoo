# NAS Crontab 최종 설정 가이드

**작성일**: 2025-11-29  
**환경**: Synology DS220j, Python 3.8  
**프로젝트**: `/volume2/homes/Hyungsoo/krx/krx_alertor_modular`

---

## 📋 현재 Crontab 설정 (Phase 5 리팩토링 후)

### 스크립트 상태

| 스크립트 | 리팩토링 | 상태 | Cron 설정 필요 |
|---------|---------|------|--------------|
| `market_open_alert.py` | ✅ 완료 | 사용 중 | ✅ 필요 |
| `intraday_alert.py` | ⏳ 대기 | 사용 중 | ✅ 필요 |
| `weekly_report_alert.py` | ⏳ 대기 | 사용 중 | ✅ 필요 |
| `daily_report_alert.py` | ⏳ 대기 | 사용 중 | ✅ 필요 |
| `daily_regime_check.py` | ⏳ 대기 | 사용 중 | ⚠️ 선택 |

---

## 🎯 최종 Crontab 설정

### 1. 기본 환경 변수

```bash
# 환경 변수 설정 (모든 작업에 적용)
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
TZ=Asia/Seoul
PROJECT_ROOT=/volume2/homes/Hyungsoo/krx/krx_alertor_modular
```

### 2. 평일 알림 (월~금)

#### 09:00 - 장시작 알림 ✅ (리팩토링 완료)
```bash
# 포트폴리오 현황 (총 평가액, 수익률, 보유 종목)
0 9 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && source config/env.nas.sh && python3.8 scripts/nas/market_open_alert.py >> logs/cron_market_open.log 2>&1
```

**기능**:
- 포트폴리오 현황 요약
- 총 평가액, 매입액, 수익률
- 보유 종목 수

**리팩토링 효과**:
- ✅ ScriptBase 사용
- ✅ PortfolioHelper 사용
- ✅ TelegramHelper 사용
- ✅ 에러 처리 자동화

---

#### 10:00, 11:00, 13:00, 14:00 - 장중 알림 ⏳ (리팩토링 대기)
```bash
# ETF 급등/급락 알림 (거래대금 50억 이상)
0 10,11,13,14 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && source config/env.nas.sh && python3.8 scripts/nas/intraday_alert.py >> logs/cron_intraday.log 2>&1
```

**기능**:
- ETF 급등/급락 감지
- 특성별 차별화 (지수 1.5%, 섹터 2.0%, 레버리지 3.0%)
- 거래대금 50억원 이상 필터
- 보유 종목 제외 (새로운 투자처 발굴)

**리팩토링 필요**:
- ⏳ ScriptBase 적용
- ⏳ PortfolioHelper 적용
- ⏳ TelegramHelper 적용

---

#### 15:30 - 손절 모니터링 ⚠️ (Shell 스크립트)
```bash
# 손절 대상 (-7% 이하), 손절 근접 (-5%~-7%)
30 15 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && source config/env.nas.sh && bash scripts/linux/jobs/stop_loss_check.sh >> logs/cron_stop_loss.log 2>&1
```

**기능**:
- 손절 대상 종목 확인
- 손절 근접 종목 경고
- 텔레그램 알림

**상태**: Shell 스크립트 (Python 리팩토링 고려)

---

#### 16:00 - 일일 종합 리포트 ⏳ (리팩토링 대기)
```bash
# 포트폴리오 + 레짐 + 신호 + 당일 성과
0 16 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && source config/env.nas.sh && bash scripts/linux/jobs/daily_scan_notify.sh >> logs/cron_daily_report.log 2>&1
```

**기능**:
- 일일 포트폴리오 리포트
- 시장 레짐 분석
- 매매 신호
- 당일 성과 요약

**리팩토링 필요**:
- ⏳ Python 스크립트로 전환 고려
- ⏳ 공통 모듈 적용

---

### 3. 주말 알림 (토요일)

#### 10:00 - 주간 리포트 ⏳ (리팩토링 대기)
```bash
# 주간 성과 + 리스크 분석 + 다음 주 전략
0 10 * * 6 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && source config/env.nas.sh && python3.8 scripts/nas/weekly_report_alert.py >> logs/cron_weekly_report.log 2>&1
```

**기능**:
- 주간 포트폴리오 성과
- 상위/하위 성과 종목
- 손절 대상 및 근접 종목
- 다음 주 전략

**리팩토링 필요**:
- ⏳ ScriptBase 적용
- ⏳ PortfolioHelper 적용
- ⏳ TelegramHelper 적용

---

## 🔧 적용 방법

### 1. NAS SSH 접속
```bash
ssh admin@your-nas-ip
# 또는
ssh Hyungsoo@your-nas-ip
```

### 2. 현재 Crontab 백업
```bash
crontab -l > ~/crontab_backup_$(date +%Y%m%d_%H%M%S).txt
```

### 3. Crontab 편집
```bash
crontab -e
```

### 4. 설정 복사 및 붙여넣기
```bash
# ============================================
# KRX Alertor 자동화 스케줄 (2025-11-29 최종)
# ============================================
# NAS: Synology DS220j
# Python: 3.8
# 프로젝트: /volume2/homes/Hyungsoo/krx/krx_alertor_modular
# ============================================

# 환경 변수 설정 (모든 작업에 적용)
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
TZ=Asia/Seoul
PROJECT_ROOT=/volume2/homes/Hyungsoo/krx/krx_alertor_modular

# 평일 알림
# --------------------------------------------

# 09:00 - 장시작 알림 (포트폴리오 현황) ✅ 리팩토링 완료
0 9 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && source config/env.nas.sh && python3.8 scripts/nas/market_open_alert.py >> logs/cron_market_open.log 2>&1

# 10:00, 11:00, 13:00, 14:00 - 장중 알림 (ETF 급등/급락)
0 10,11,13,14 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && source config/env.nas.sh && python3.8 scripts/nas/intraday_alert.py >> logs/cron_intraday.log 2>&1

# 15:30 - 손절 모니터링
30 15 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && source config/env.nas.sh && bash scripts/linux/jobs/stop_loss_check.sh >> logs/cron_stop_loss.log 2>&1

# 16:00 - 일일 종합 리포트
0 16 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && source config/env.nas.sh && bash scripts/linux/jobs/daily_scan_notify.sh >> logs/cron_daily_report.log 2>&1

# 주말 알림
# --------------------------------------------

# 토요일 10:00 - 주간 리포트
0 10 * * 6 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && source config/env.nas.sh && python3.8 scripts/nas/weekly_report_alert.py >> logs/cron_weekly_report.log 2>&1

# ============================================
# 변경 사항 (2025-11-29):
# - market_open_alert.py 리팩토링 완료
# - 공통 모듈 적용 (ScriptBase, PortfolioHelper, TelegramHelper)
# - 나머지 스크립트 리팩토링 대기
# ============================================
```

### 5. 저장 및 종료
```bash
# vi 에디터
:wq

# nano 에디터
Ctrl+X, Y, Enter
```

### 6. 설정 확인
```bash
crontab -l
```

---

## 📊 실행 시간표

| 시간 | 요일 | 스크립트 | 기능 | 리팩토링 |
|------|------|---------|------|---------|
| 09:00 | 월~금 | `market_open_alert.py` | 장시작 알림 | ✅ 완료 |
| 10:00 | 월~금 | `intraday_alert.py` | 장중 알림 | ⏳ 대기 |
| 11:00 | 월~금 | `intraday_alert.py` | 장중 알림 | ⏳ 대기 |
| 13:00 | 월~금 | `intraday_alert.py` | 장중 알림 | ⏳ 대기 |
| 14:00 | 월~금 | `intraday_alert.py` | 장중 알림 | ⏳ 대기 |
| 15:30 | 월~금 | `stop_loss_check.sh` | 손절 모니터링 | ⚠️ Shell |
| 16:00 | 월~금 | `daily_scan_notify.sh` | 일일 리포트 | ⚠️ Shell |
| 10:00 | 토 | `weekly_report_alert.py` | 주간 리포트 | ⏳ 대기 |

---

## 🔍 로그 확인

### 로그 파일 위치
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular/logs
```

### 로그 파일 목록
```bash
ls -lh logs/cron_*.log
```

### 실시간 로그 확인
```bash
# 장시작 알림
tail -f logs/cron_market_open.log

# 장중 알림
tail -f logs/cron_intraday.log

# 손절 모니터링
tail -f logs/cron_stop_loss.log

# 일일 리포트
tail -f logs/cron_daily_report.log

# 주간 리포트
tail -f logs/cron_weekly_report.log
```

### 최근 에러 확인
```bash
# 최근 100줄
tail -n 100 logs/cron_market_open.log

# 에러만 필터링
grep -i "error\|fail\|❌" logs/cron_market_open.log
```

---

## ⚠️ 주의사항

### 1. 환경 변수 파일
**필수**: `config/env.nas.sh` 파일이 존재해야 함

**확인**:
```bash
cat /volume2/homes/Hyungsoo/krx/krx_alertor_modular/config/env.nas.sh
```

**내용**:
```bash
#!/bin/bash
# NAS 환경 변수

export TZ="Asia/Seoul"
export PROJECT_ROOT="/volume2/homes/Hyungsoo/krx/krx_alertor_modular"
export ENV="nas"
export PYTHONBIN="python3.8"
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH}"
export ALLOW_NET_FETCH="true"

# 텔레그램 설정 (민감 정보)
export TG_TOKEN="your_telegram_bot_token"
export TG_CHAT_ID="your_telegram_chat_id"
export TELEGRAM_TOKEN="your_telegram_bot_token"
export TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
```

### 2. 권한 확인
```bash
# 스크립트 실행 권한
chmod +x /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/nas/*.py
chmod +x /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/linux/jobs/*.sh

# 로그 디렉토리 권한
chmod 755 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/logs
```

### 3. Python 버전 확인
```bash
python3.8 --version
# Python 3.8.x 확인
```

---

## 🚀 나머지 스크립트 리팩토링 후 작업

### 리팩토링 대상
1. **intraday_alert.py** (장중 알림)
2. **weekly_report_alert.py** (주간 리포트)
3. **daily_report_alert.py** (일일 리포트)

### 리팩토링 후 작업
1. **컴파일 테스트**
   ```bash
   python3.8 -m py_compile scripts/nas/intraday_alert.py
   python3.8 -m py_compile scripts/nas/weekly_report_alert.py
   python3.8 -m py_compile scripts/nas/daily_report_alert.py
   ```

2. **수동 실행 테스트**
   ```bash
   cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
   source config/env.nas.sh
   
   python3.8 scripts/nas/intraday_alert.py
   python3.8 scripts/nas/weekly_report_alert.py
   python3.8 scripts/nas/daily_report_alert.py
   ```

3. **Git 동기화**
   ```bash
   cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
   git pull origin main
   ```

4. **Crontab 재시작 (필요시)**
   ```bash
   # Synology는 자동으로 crontab 재시작
   # 수동 재시작이 필요한 경우:
   sudo synoservice --restart crond
   ```

---

## 📋 체크리스트

### 리팩토링 전
- [x] 현재 Crontab 백업
- [x] 환경 변수 파일 확인 (`config/env.nas.sh`)
- [x] 텔레그램 설정 확인
- [x] 로그 디렉토리 확인

### 리팩토링 중
- [x] `market_open_alert.py` 리팩토링 완료
- [ ] `intraday_alert.py` 리팩토링
- [ ] `weekly_report_alert.py` 리팩토링
- [ ] `daily_report_alert.py` 리팩토링

### 리팩토링 후
- [ ] 모든 스크립트 컴파일 테스트
- [ ] 수동 실행 테스트
- [ ] Git 동기화 (PC → NAS)
- [ ] Crontab 설정 확인
- [ ] 로그 모니터링 (1일)

---

## 💡 추가 개선 사항 (선택)

### 1. 로그 로테이션
```bash
# logrotate 설정 (선택)
# /etc/logrotate.d/krx_alertor
/volume2/homes/Hyungsoo/krx/krx_alertor_modular/logs/*.log {
    daily
    rotate 30
    compress
    missingok
    notifempty
}
```

### 2. 에러 알림
```bash
# Cron 에러 시 텔레그램 알림 (선택)
# 각 작업 끝에 추가:
|| python3.8 scripts/nas/send_error_alert.py "Cron 작업 실패"
```

### 3. 헬스체크
```bash
# 매일 자정 헬스체크 (선택)
0 0 * * * cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python3.8 scripts/nas/health_check.py >> logs/cron_health.log 2>&1
```

---

## 📞 문제 해결

### Cron이 실행되지 않는 경우
1. **Cron 서비스 확인**
   ```bash
   sudo synoservice --status crond
   ```

2. **로그 확인**
   ```bash
   tail -f /var/log/cron.log
   ```

3. **권한 확인**
   ```bash
   ls -la /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/nas/
   ```

### 텔레그램 전송 실패
1. **환경 변수 확인**
   ```bash
   source config/env.nas.sh
   echo $TELEGRAM_BOT_TOKEN
   echo $TELEGRAM_CHAT_ID
   ```

2. **수동 테스트**
   ```bash
   python3.8 scripts/nas/market_open_alert.py
   ```

---

**NAS Crontab 최종 설정 가이드 완료!** 🎉

**다음 단계**:
1. 나머지 스크립트 리팩토링 (1시간)
2. NAS Git Pull 및 테스트
3. Crontab 모니터링 (1일)
