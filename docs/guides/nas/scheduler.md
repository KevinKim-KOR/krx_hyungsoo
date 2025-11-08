# NAS 스케줄러 명령어 (최종 버전)

## ⚙️ 스케줄러 설정 방법

**DSM → 제어판 → 작업 스케줄러 → 생성 → 예약된 작업 → 사용자 정의 스크립트**

---

## 📋 필수 설정 (모든 작업 공통)

### 일반 설정
- **사용자**: `Hyungsoo`
- **활성화**: ✅ 체크 필수!

### 스케줄 설정
- 각 작업별로 아래 시간 설정

### 작업 설정
- **사용자 정의 스크립트**에 아래 명령어 입력
- **이메일 알림**: 선택 (실패 시 알림 받으려면 체크)

---

## 🕐 평일 스케줄 (월~금)

### 1. 장 시작 알림 (09:00)

**스케줄**: 월~금, 09:00

**명령어**:
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && /usr/bin/python3.8 scripts/nas/market_open_alert.py >> logs/market_open_$(date +\%Y\%m\%d).log 2>&1
```

---

### 2. 상승 ETF 알림 #1 (10:00)

**스케줄**: 월~금, 10:00

**명령어**:
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && /usr/bin/python3.8 scripts/nas/rising_etf_alert.py >> logs/rising_etf_$(date +\%Y\%m\%d).log 2>&1
```

---

### 3. 상승 ETF 알림 #2 (11:00)

**스케줄**: 월~금, 11:00

**명령어**:
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && /usr/bin/python3.8 scripts/nas/rising_etf_alert.py >> logs/rising_etf_$(date +\%Y\%m\%d).log 2>&1
```

---

### 4. 상승 ETF 알림 #3 (12:00)

**스케줄**: 월~금, 12:00

**명령어**:
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && /usr/bin/python3.8 scripts/nas/rising_etf_alert.py >> logs/rising_etf_$(date +\%Y\%m\%d).log 2>&1
```

---

### 5. 상승 ETF 알림 #4 (13:00)

**스케줄**: 월~금, 13:00

**명령어**:
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && /usr/bin/python3.8 scripts/nas/rising_etf_alert.py >> logs/rising_etf_$(date +\%Y\%m\%d).log 2>&1
```

---

### 6. 상승 ETF 알림 #5 (14:00)

**스케줄**: 월~금, 14:00

**명령어**:
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && /usr/bin/python3.8 scripts/nas/rising_etf_alert.py >> logs/rising_etf_$(date +\%Y\%m\%d).log 2>&1
```

---

### 7. 상승 ETF 알림 #6 (15:00)

**스케줄**: 월~금, 15:00

**명령어**:
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && /usr/bin/python3.8 scripts/nas/rising_etf_alert.py >> logs/rising_etf_$(date +\%Y\%m\%d).log 2>&1
```

---

### 8. EoD 신호 (16:00) ⭐ 중요

**스케줄**: 월~금, 16:00

**명령어**:
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && bash scripts/nas/daily_realtime_signals.sh >> logs/eod_signals_$(date +\%Y\%m\%d).log 2>&1
```

---

### 9. 레짐 변경 알림 (16:30) ⭐ 중요

**스케줄**: 월~금, 16:30

**명령어**:
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && /usr/bin/python3.8 scripts/nas/regime_change_alert.py >> logs/regime_change_$(date +\%Y\%m\%d).log 2>&1
```

---

## 🗓️ 매일 스케줄

### 10. 로그 정리 (02:00)

**스케줄**: 매일, 02:00

**명령어**:
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && bash scripts/nas/cleanup_logs.sh >> logs/cleanup_$(date +\%Y\%m\%d).log 2>&1
```

---

### 11. DB 백업 (03:00)

**스케줄**: 매일, 03:00

**명령어**:
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && bash scripts/nas/backup_db.sh >> logs/backup_$(date +\%Y\%m\%d).log 2>&1
```

---

## 📅 주간 스케줄

### 12. 주간 리포트 (일요일 09:00)

**스케줄**: 일요일, 09:00

**명령어**:
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && /usr/bin/python3.8 scripts/nas/weekly_report.py >> logs/weekly_report_$(date +\%Y\%m\%d).log 2>&1
```

---

## 🔧 명령어 구조 설명

```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && \
/usr/bin/python3.8 scripts/nas/script_name.py >> \
logs/log_name_$(date +\%Y\%m\%d).log 2>&1
```

**구성 요소**:
1. `cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular` - 프로젝트 디렉토리로 이동
2. `&&` - 이전 명령 성공 시 다음 실행
3. `/usr/bin/python3.8` - Python 절대 경로
4. `scripts/nas/script_name.py` - 실행할 스크립트
5. `>> logs/log_name_$(date +\%Y\%m\%d).log` - 로그 파일에 추가 (날짜별)
6. `2>&1` - 에러도 로그에 기록

---

## ✅ 설정 후 확인 사항

### 1. 즉시 실행 테스트

작업 스케줄러에서:
1. 작업 선택
2. "실행" 버튼 클릭
3. 텔레그램 메시지 확인
4. "실행 결과" 탭에서 성공/실패 확인

---

### 2. 로그 확인

SSH 접속 후:
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular

# 오늘 생성된 로그 확인
ls -lt logs/*$(date +%Y%m%d)*.log

# 최신 로그 내용 확인
tail -50 logs/market_open_$(date +%Y%m%d).log
```

---

### 3. 다음 실행 시간 확인

작업 스케줄러에서:
- "다음 실행 시간" 컬럼 확인
- 예상 시간이 맞는지 확인

---

## 🚨 주의사항

### 1. 날짜 형식
- Synology Cron에서는 `\%` 사용 (백슬래시 필수!)
- SSH에서는 `%` 사용

### 2. 경로
- **절대 경로** 사용 필수
- 상대 경로는 Cron에서 작동 안 함

### 3. 권한
- 사용자: `Hyungsoo` (root 아님!)
- 로그 디렉토리 쓰기 권한 확인

### 4. 시간대
- DSM 시간대가 `Asia/Seoul`인지 확인
- 제어판 → 지역 옵션 → 시간대

---

## 📊 예상 동작 (평일 기준)

```
09:00 - 🏦 장 시작 알림 (포트폴리오 현황)
10:00 - 📈 상승 ETF #1
11:00 - 📈 상승 ETF #2
12:00 - 📈 상승 ETF #3
13:00 - 📈 상승 ETF #4
14:00 - 📈 상승 ETF #5
15:00 - 📈 상승 ETF #6
16:00 - 📊 EoD 신호 (매수/매도 추천)
16:30 - 🌡️ 레짐 변경 알림 (변경 시에만)
```

---

## 🔍 트러블슈팅

### 문제: 실행은 되는데 알림이 안 옴

**원인**: 스크립트는 실행되지만 텔레그램 전송 실패

**확인**:
```bash
# 로그 확인
tail -50 logs/market_open_$(date +%Y%m%d).log

# 에러 검색
grep -i "error\|fail\|exception" logs/*.log
```

---

### 문제: 실행 자체가 안 됨

**원인**: 경로 또는 권한 문제

**확인**:
```bash
# 수동 실행 테스트
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
/usr/bin/python3.8 scripts/nas/market_open_alert.py
```

---

### 문제: 특정 시간에만 실행 안 됨

**원인**: 스케줄 설정 오류

**확인**:
- 작업 스케줄러에서 스케줄 설정 재확인
- "다음 실행 시간"이 올바른지 확인

---

## 📝 빠른 설정 가이드

1. **DSM → 제어판 → 작업 스케줄러**
2. **생성 → 예약된 작업 → 사용자 정의 스크립트**
3. **일반**: 작업 이름 입력, 사용자 `Hyungsoo`, **활성화 체크**
4. **스케줄**: 시간 설정
5. **작업 설정**: 위 명령어 복사/붙여넣기
6. **확인** 클릭
7. **즉시 실행 테스트**
8. **텔레그램 메시지 확인**

---

## ✅ 최종 체크리스트

- [ ] 모든 작업 "활성화" 체크
- [ ] 명령어에 절대 경로 사용
- [ ] 로그 리다이렉션 설정 (`>> logs/...`)
- [ ] 즉시 실행 테스트 성공
- [ ] 텔레그램 메시지 수신 확인
- [ ] "다음 실행 시간" 확인

---

## 🎯 성공 확인

**내일 (금요일) 09:00**에 장 시작 알림이 자동으로 오면 성공입니다! 🎉
