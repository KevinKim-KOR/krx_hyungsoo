# NAS Crontab 체크리스트 (간편 버전)

**작성일**: 2025-11-29  
**목적**: 리팩토링 후 Crontab 설정 빠른 확인

---

## ✅ 현재 상태 (2025-11-29)

### 리팩토링 완료
- ✅ **market_open_alert.py** (09:00 장시작 알림)

### 리팩토링 대기
- ⏳ **intraday_alert.py** (10:00, 11:00, 13:00, 14:00 장중 알림)
- ⏳ **weekly_report_alert.py** (토 10:00 주간 리포트)
- ⏳ **daily_report_alert.py** (16:00 일일 리포트)

---

## 📋 즉시 해야 할 작업

### 1. NAS에 Git Pull (필수)
```bash
ssh admin@your-nas-ip
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
git pull origin main
```

### 2. 리팩토링된 스크립트 테스트
```bash
source config/env.nas.sh
python3.8 scripts/nas/market_open_alert.py
```

### 3. Crontab 확인
```bash
crontab -l | grep market_open_alert
```

**예상 출력**:
```
0 9 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && source config/env.nas.sh && python3.8 scripts/nas/market_open_alert.py >> logs/cron_market_open.log 2>&1
```

---

## 🔄 나머지 스크립트 리팩토링 후 작업

### 1. PC에서 리팩토링 완료 후
```bash
# PC
git add scripts/nas/*.py
git commit -m "Phase 5.3: 나머지 스크립트 리팩토링 완료"
git push origin main
```

### 2. NAS에서 Git Pull
```bash
# NAS
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
git pull origin main
```

### 3. 컴파일 테스트
```bash
python3.8 -m py_compile scripts/nas/intraday_alert.py
python3.8 -m py_compile scripts/nas/weekly_report_alert.py
python3.8 -m py_compile scripts/nas/daily_report_alert.py
```

### 4. 수동 실행 테스트
```bash
source config/env.nas.sh

# 장중 알림 테스트
python3.8 scripts/nas/intraday_alert.py

# 주간 리포트 테스트
python3.8 scripts/nas/weekly_report_alert.py

# 일일 리포트 테스트
python3.8 scripts/nas/daily_report_alert.py
```

### 5. Crontab 확인 (변경 불필요)
```bash
crontab -l
```

**현재 설정이 그대로 동작합니다!** ✅

---

## 📊 Crontab 실행 시간표

| 시간 | 요일 | 스크립트 | 상태 |
|------|------|---------|------|
| 09:00 | 월~금 | `market_open_alert.py` | ✅ 리팩토링 완료 |
| 10:00 | 월~금 | `intraday_alert.py` | ⏳ 리팩토링 대기 |
| 11:00 | 월~금 | `intraday_alert.py` | ⏳ 리팩토링 대기 |
| 13:00 | 월~금 | `intraday_alert.py` | ⏳ 리팩토링 대기 |
| 14:00 | 월~금 | `intraday_alert.py` | ⏳ 리팩토링 대기 |
| 15:30 | 월~금 | `stop_loss_check.sh` | ⚠️ Shell (변경 없음) |
| 16:00 | 월~금 | `daily_scan_notify.sh` | ⚠️ Shell (변경 없음) |
| 10:00 | 토 | `weekly_report_alert.py` | ⏳ 리팩토링 대기 |

---

## 🔍 로그 확인 (문제 발생 시)

### 빠른 확인
```bash
# 최근 로그 확인
tail -n 50 logs/cron_market_open.log

# 에러만 확인
grep -i "error\|fail\|❌" logs/cron_market_open.log
```

### 실시간 모니터링
```bash
# 장시작 알림 (09:00)
tail -f logs/cron_market_open.log

# 장중 알림 (10:00, 11:00, 13:00, 14:00)
tail -f logs/cron_intraday.log

# 주간 리포트 (토 10:00)
tail -f logs/cron_weekly_report.log
```

---

## ⚠️ 중요 사항

### Crontab 변경 불필요!
- ✅ **스크립트 경로 동일**: `scripts/nas/*.py`
- ✅ **실행 방법 동일**: `python3.8 scripts/nas/...`
- ✅ **환경 변수 동일**: `source config/env.nas.sh`

**리팩토링은 내부 코드만 변경, 외부 인터페이스는 동일합니다!**

### Git Pull만 하면 끝!
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
git pull origin main
```

---

## 📞 문제 발생 시

### 1. 스크립트 실행 실패
```bash
# 권한 확인
ls -la scripts/nas/market_open_alert.py

# 권한 부여
chmod +x scripts/nas/market_open_alert.py
```

### 2. 텔레그램 전송 실패
```bash
# 환경 변수 확인
source config/env.nas.sh
echo $TELEGRAM_BOT_TOKEN
echo $TELEGRAM_CHAT_ID
```

### 3. Import 에러
```bash
# Python 경로 확인
echo $PYTHONPATH

# 수동 설정
export PYTHONPATH="/volume2/homes/Hyungsoo/krx/krx_alertor_modular:$PYTHONPATH"
```

---

## 🎯 요약

### 지금 해야 할 것
1. ✅ **NAS Git Pull** (리팩토링된 코드 가져오기)
2. ✅ **테스트 실행** (market_open_alert.py)
3. ✅ **로그 확인** (정상 동작 확인)

### 나중에 할 것
1. ⏳ **나머지 스크립트 리팩토링** (PC에서)
2. ⏳ **NAS Git Pull** (리팩토링 완료 후)
3. ⏳ **전체 테스트** (모든 스크립트)

### 변경 불필요
- ✅ **Crontab 설정**: 그대로 유지
- ✅ **환경 변수**: 그대로 유지
- ✅ **로그 파일**: 그대로 유지

---

**간단 요약**: Git Pull만 하면 끝! Crontab 변경 불필요! 🎉
