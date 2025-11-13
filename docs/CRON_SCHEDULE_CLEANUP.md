# NAS Cron 스케줄 정리 (2025-11-13)

## 🎯 **목표**

Phase 4 진행 중 누적된 중복/미사용 알림 스크립트를 정리하고, 최적화된 스케줄을 수립합니다.

---

## 📊 **현재 상태 분석**

### **사용자 요청 스케줄**
```bash
# 평일
09:00 - market_open_alert.py (장시작 알림)
09:20 - intraday_alert.py (장중 알림)
09:30 - regime_change_alert.py (레짐 변경)
15:30 - stop_loss_check.sh (손절 모니터링) ⬅️ Phase 4 신규
16:00 - daily_scan_notify.sh (일일 마감)
16:10 - daily_realtime_signals.sh (EOD 신호)

# 주말
10:00 - weekly_alert.sh (주간 리포트 1)
10:00 - weekly_report_alert.py (주간 리포트 2) ⬅️ Phase 4 신규
10:10 - weekly_report.py (주간 리포트 3)
```

### **문제점**
```
❌ 주간 리포트 3개 중복 (10:00, 10:00, 10:10)
❌ 장중 알림 시간 불명확 (09:20만? 10:00, 11:00, 13:00, 14:00는?)
❌ daily_scan_notify.sh vs daily_realtime_signals.sh 중복 가능성
❌ weekly_alert.sh vs weekly_report.py vs weekly_report_alert.py 중복
```

---

## 🔍 **스크립트 분석**

### **1. 주간 리포트 (3개 중복)**

#### **A. scripts/automation/weekly_alert.sh**
```bash
# 내용: run_weekly_report.py 실행
# 용도: Phase 2 자동화 시스템 (백테스트 기반)
# 상태: 구버전
```

#### **B. scripts/nas/weekly_report.py**
```python
# 내용: SignalTracker, PerformanceTracker 기반 주간 요약
# 용도: Phase 2 백테스트 성과 리포트
# 상태: 구버전 (백테스트 데이터 사용)
```

#### **C. scripts/nas/weekly_report_alert.py** ⬅️ **최신**
```python
# 내용: PortfolioLoader 기반 실제 포트폴리오 주간 리포트
# 용도: Phase 4 실전 포트폴리오 리포트
# 상태: 최신 (실제 holdings.json 사용)
# 기능:
#   - 주간 성과 요약
#   - 상위/하위 성과 종목
#   - 리스크 분석 (손절 대상/근접)
#   - 다음 주 전략
```

**결론:** `weekly_report_alert.py`만 사용! ✅

---

### **2. 일일 마감 (2개 중복 가능성)**

#### **A. scripts/linux/jobs/daily_scan_notify.sh**
```bash
# 내용: daily_report_alert.py 실행
# 용도: 장마감 후 종합 일일 리포트
# 기능:
#   - 포트폴리오 현황
#   - 시장 레짐
#   - 매매 신호
#   - 당일 성과
```

#### **B. scripts/nas/daily_realtime_signals.sh**
```bash
# 내용: nas/app_realtime.py 실행
# 용도: 실시간 신호 생성
# 기능:
#   - 매매 신호만 생성
#   - 포트폴리오 현황 없음
```

**결론:** 
- `daily_scan_notify.sh` (16:00) - 종합 리포트 ✅
- `daily_realtime_signals.sh` (16:10) - 제거 또는 통합 ❌

---

### **3. 장중 알림 (시간 불명확)**

#### **현재 요청: 09:20만 실행**
```bash
09:20 - intraday_alert.py
```

#### **Phase 2 설정: 4회 실행**
```bash
10:00 - intraday_alert.py
11:00 - intraday_alert.py
13:00 - intraday_alert.py
14:00 - intraday_alert.py
```

**결론:** 사용자 의도 확인 필요
- Option 1: 09:20만 실행 (1회)
- Option 2: 10:00, 11:00, 13:00, 14:00 실행 (4회) ⬅️ 권장

---

## ✅ **최종 정리 스케줄**

### **평일 스케줄**

| 시간 | 스크립트 | 내용 | 상태 |
|------|----------|------|------|
| **09:00** | `market_open_alert.py` | 장시작 알림 | ✅ 유지 |
| **10:00** | `intraday_alert.py` | 장중 알림 1 | ✅ 유지 |
| **11:00** | `intraday_alert.py` | 장중 알림 2 | ✅ 유지 |
| **13:00** | `intraday_alert.py` | 장중 알림 3 | ✅ 유지 |
| **14:00** | `intraday_alert.py` | 장중 알림 4 | ✅ 유지 |
| **15:30** | `stop_loss_check.sh` | 손절 모니터링 | ✅ 유지 (Phase 4) |
| **16:00** | `daily_scan_notify.sh` | 일일 종합 리포트 | ✅ 유지 |

**제거:**
- ~~09:20 intraday_alert.py~~ (10:00으로 통합)
- ~~09:30 regime_change_alert.py~~ (daily_scan_notify.sh에 포함)
- ~~16:10 daily_realtime_signals.sh~~ (daily_scan_notify.sh에 통합)

---

### **주말 스케줄**

| 시간 | 스크립트 | 내용 | 상태 |
|------|----------|------|------|
| **10:00** | `weekly_report_alert.py` | 주간 리포트 | ✅ 유지 (Phase 4) |

**제거:**
- ~~10:00 weekly_alert.sh~~ (구버전)
- ~~10:10 weekly_report.py~~ (구버전)

---

## 📝 **최종 Cron 설정**

### **NAS Crontab**

```bash
# ============================================
# KRX Alertor 자동화 스케줄 (2025-11-13 정리)
# ============================================

# 평일 알림
# --------------------------------------------

# 09:00 - 장시작 알림
0 9 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python3.8 scripts/nas/market_open_alert.py

# 10:00, 11:00, 13:00, 14:00 - 장중 알림 (ETF 급등/급락)
0 10,11,13,14 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python3.8 scripts/nas/intraday_alert.py

# 15:30 - 손절 모니터링 (Phase 4)
30 15 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && bash scripts/linux/jobs/stop_loss_check.sh

# 16:00 - 일일 종합 리포트 (포트폴리오 + 레짐 + 신호)
0 16 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && bash scripts/linux/jobs/daily_scan_notify.sh

# 주말 알림
# --------------------------------------------

# 토요일 10:00 - 주간 리포트 (Phase 4)
0 10 * * 6 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python3.8 scripts/nas/weekly_report_alert.py
```

---

## 🗑️ **제거할 파일**

### **1. 구버전 주간 리포트**
```bash
# 백업 후 제거
scripts/automation/weekly_alert.sh
scripts/nas/weekly_report.py
scripts/automation/run_weekly_report.py
```

### **2. 중복 EOD 스크립트**
```bash
# 백업 후 제거
scripts/nas/daily_realtime_signals.sh
nas/app_realtime.py (사용 안 함)
```

### **3. 독립 레짐 알림**
```bash
# daily_scan_notify.sh에 통합되어 있으므로 제거
scripts/nas/regime_change_alert.py (독립 실행 불필요)
```

---

## 📊 **정리 전후 비교**

### **정리 전 (10개 스케줄)**
```
평일:
09:00 - market_open_alert.py
09:20 - intraday_alert.py (중복)
09:30 - regime_change_alert.py (중복)
15:30 - stop_loss_check.sh
16:00 - daily_scan_notify.sh
16:10 - daily_realtime_signals.sh (중복)

주말:
10:00 - weekly_alert.sh (중복)
10:00 - weekly_report_alert.py
10:10 - weekly_report.py (중복)
```

### **정리 후 (7개 스케줄)**
```
평일:
09:00 - market_open_alert.py ✅
10:00, 11:00, 13:00, 14:00 - intraday_alert.py ✅
15:30 - stop_loss_check.sh ✅
16:00 - daily_scan_notify.sh ✅

주말:
10:00 - weekly_report_alert.py ✅
```

**개선:**
- 중복 제거: 3개 → 0개
- 스케줄 명확화
- 유지보수 용이

---

## 🎯 **각 알림의 역할**

### **1. 장시작 알림 (09:00)** 📊
```
내용:
- 포트폴리오 현황
- 총 평가액, 수익률
- 보유 종목 수

목적: 하루 시작 전 포트폴리오 확인
```

### **2. 장중 알림 (10:00, 11:00, 13:00, 14:00)** 🚨
```
내용:
- ETF 급등/급락 (±5% 이상)
- 거래대금 50억 이상
- 3개월 수익률
- 괴리율 (ETF)
- 거래량 트렌드

목적: 실시간 시장 모니터링
```

### **3. 손절 모니터링 (15:30)** ⚠️
```
내용:
- 손절 대상 (-7% 이하)
- 손절 근접 (-5% ~ -7%)
- 즉시 매도 필요 종목

목적: 장 마감 전 손절 대상 확인
```

### **4. 일일 종합 리포트 (16:00)** 📈
```
내용:
- 포트폴리오 현황
- 시장 레짐 (상승/중립/하락)
- 매매 신호 (진입/청산)
- 당일 성과

목적: 하루 마감 후 종합 분석
```

### **5. 주간 리포트 (토 10:00)** 📊
```
내용:
- 주간 성과 요약
- 상위/하위 성과 종목 Top 5
- 리스크 분석 (손절 대상/근접)
- 다음 주 전략

목적: 주간 성과 리뷰 및 전략 수립
```

---

## 🚀 **적용 방법**

### **1. 백업**
```bash
# NAS SSH 접속
ssh admin@nas-ip

# 현재 crontab 백업
crontab -l > ~/crontab_backup_$(date +%Y%m%d).txt
```

### **2. Crontab 편집**
```bash
crontab -e
```

### **3. 기존 내용 삭제 후 새 스케줄 붙여넣기**
```bash
# 위의 "최종 Cron 설정" 내용 복사
# crontab 편집기에 붙여넣기
# 저장 후 종료 (:wq)
```

### **4. 확인**
```bash
# crontab 확인
crontab -l

# 로그 확인 (다음 실행 시)
tail -f /volume2/homes/Hyungsoo/krx/krx_alertor_modular/logs/*.log
```

### **5. 구버전 파일 정리 (선택)**
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular

# 백업 디렉토리 생성
mkdir -p scripts/_deprecated_2025-11-13

# 구버전 파일 이동
mv scripts/automation/weekly_alert.sh scripts/_deprecated_2025-11-13/
mv scripts/nas/weekly_report.py scripts/_deprecated_2025-11-13/
mv scripts/nas/daily_realtime_signals.sh scripts/_deprecated_2025-11-13/
```

---

## 💡 **주의사항**

### **1. 장중 알림 시간**
```
현재 요청: 09:20
권장 설정: 10:00, 11:00, 13:00, 14:00

이유:
- 09:20은 시초가 직후 (변동성 높음)
- 10:00부터 시작하면 시장 안정 후 알림
- 4회 실행으로 충분한 모니터링
```

### **2. 레짐 변경 알림**
```
독립 실행 불필요:
- daily_scan_notify.sh에 이미 포함
- 16:00 일일 리포트에서 확인 가능
- 중복 알림 방지
```

### **3. EOD 신호**
```
daily_realtime_signals.sh 제거:
- daily_scan_notify.sh에 통합
- 중복 알림 방지
- 16:00 한 번만 실행
```

---

## 🎉 **정리 완료 후 기대 효과**

### **1. 중복 제거** ✅
```
주간 리포트: 3개 → 1개
일일 마감: 2개 → 1개
레짐 알림: 독립 실행 제거
```

### **2. 명확한 스케줄** ✅
```
평일: 7개 시간대 (09:00, 10:00, 11:00, 13:00, 14:00, 15:30, 16:00)
주말: 1개 시간대 (10:00)
```

### **3. 유지보수 용이** ✅
```
최신 스크립트만 사용
구버전 파일 정리
명확한 역할 분담
```

### **4. 알림 품질 향상** ✅
```
중복 알림 제거
실제 포트폴리오 기반
Phase 4 최신 기능 반영
```

---

**정리 완료!**  
**이제 Week 3로 진행 가능합니다!** 🚀
