# 현재 사용 중인 스크립트

**작성일**: 2025-11-28  
**환경**: NAS (Synology DS220j)

---

## 📋 NAS Cron 작업

### 1. Daily Report (Intraday Alert)
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python3.8 scripts/nas/intraday_alert.py
```
- **파일**: `scripts/nas/intraday_alert.py` ✅
- **용도**: 장중 알림 (급등/급락)
- **상태**: 사용 중

---

### 2. Sync to Oracle
```bash
# 데이터 생성
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python scripts/sync/generate_sync_data.py >> logs/sync/generate.log 2>&1

# Oracle로 동기화
/volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/sync/sync_to_oracle.sh
```
- **파일**: 
  - `scripts/sync/generate_sync_data.py` ✅
  - `scripts/sync/sync_to_oracle.sh` ✅
- **용도**: NAS → Oracle Cloud 데이터 동기화
- **상태**: 사용 중

---

### 3. Stop Loss Check
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python3.8 scripts/phase4/hybrid_stop_loss.py
```
- **파일**: `scripts/phase4/hybrid_stop_loss.py` ✅
- **용도**: 손절 체크
- **상태**: 사용 중

---

### 4. Daily Alert
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && bash scripts/linux/jobs/daily_scan_notify.sh
```
- **파일**: `scripts/linux/jobs/daily_scan_notify.sh` ✅
- **용도**: 일일 스캔 알림
- **상태**: 사용 중

---

### 5. Cleanup Logs
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && bash scripts/nas/cleanup_logs.sh
```
- **파일**: `scripts/nas/cleanup_logs.sh` ✅
- **용도**: 로그 정리
- **상태**: 사용 중

---

### 6. Backup DB
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && bash scripts/nas/backup_db.sh
```
- **파일**: `scripts/nas/backup_db.sh` ✅
- **용도**: 데이터베이스 백업
- **상태**: 사용 중

---

### 7. Weekly Alert
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python3.8 scripts/nas/weekly_report_alert.py
```
- **파일**: `scripts/nas/weekly_report_alert.py` ✅
- **용도**: 주간 리포트 알림
- **상태**: 사용 중

---

### 8. Open Daily (Market Open Alert)
```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python3.8 scripts/nas/market_open_alert.py
```
- **파일**: `scripts/nas/market_open_alert.py` ✅
- **용도**: 장시작 알림
- **상태**: 사용 중

---

## 📊 사용 중인 스크립트 요약

### scripts/nas/ (6개)
- ✅ `intraday_alert.py` - 장중 알림
- ✅ `market_open_alert.py` - 장시작 알림
- ✅ `weekly_report_alert.py` - 주간 리포트
- ✅ `cleanup_logs.sh` - 로그 정리
- ✅ `backup_db.sh` - DB 백업
- ❌ `daily_regime_check.py` - **사용 안 함** (대체됨)

### scripts/sync/ (2개)
- ✅ `generate_sync_data.py` - 동기화 데이터 생성
- ✅ `sync_to_oracle.sh` - Oracle 동기화

### scripts/phase4/ (1개)
- ✅ `hybrid_stop_loss.py` - 손절 체크

### scripts/linux/jobs/ (1개)
- ✅ `daily_scan_notify.sh` - 일일 스캔 알림

---

## 🔍 분석 결과

### 사용 안 하는 스크립트 (삭제 가능)

**scripts/nas/**:
- ❌ `daily_regime_check.py` - **대체됨** (intraday_alert.py로 통합)
- ❌ `daily_regime_check.bat` - 래퍼 (이미 삭제)
- ❌ `daily_regime_check.sh` - 래퍼 (이미 삭제)
- ❌ `daily_report_alert.py` - **중복** (intraday_alert.py와 동일?)
- ❌ `README_LEGACY.md` - 레거시 문서

**scripts/nas/ 테스트 파일**:
- ❌ `test_telegram.py` - 테스트 (scripts/tests/로 이동)
- ❌ `debug_scheduler.sh` - 디버그 (scripts/diagnostics/로 이동)
- ❌ `disable_us_indicators.sh` - 일회성 (삭제 또는 archive/)
- ❌ `status.sh` - 디버그 (scripts/diagnostics/로 이동)
- ❌ `crontab_realtime.txt` - 예제 (config/로 이동)

---

## 📋 정리 계획 (수정)

### 안전하게 삭제 가능

1. **래퍼 스크립트** (이미 삭제 완료)
   - ✅ `daily_regime_check.bat`
   - ✅ `daily_regime_check.sh`

2. **레거시 문서**
   - `README_LEGACY.md`

3. **대체된 스크립트**
   - `daily_regime_check.py` (intraday_alert.py로 대체)
   - `daily_report_alert.py` (중복 확인 필요)

### 이동 필요

1. **테스트 스크립트**
   - `test_telegram.py` → `scripts/tests/`

2. **디버그 스크립트**
   - `debug_scheduler.sh` → `scripts/diagnostics/`
   - `status.sh` → `scripts/diagnostics/`

3. **설정 파일**
   - `crontab_realtime.txt` → `config/`

4. **일회성 스크립트**
   - `disable_us_indicators.sh` → `scripts/archive/`

---

## 🎯 Phase 3.2 실행 계획

### Step 1: 레거시 문서 삭제
- `scripts/nas/README_LEGACY.md`

### Step 2: 대체된 스크립트 확인 및 삭제
- `scripts/nas/daily_regime_check.py` (사용 여부 최종 확인)
- `scripts/nas/daily_report_alert.py` (중복 확인)

### Step 3: 테스트/디버그 스크립트 이동
- `test_telegram.py` → `scripts/tests/`
- `debug_scheduler.sh` → `scripts/diagnostics/`
- `status.sh` → `scripts/diagnostics/`

### Step 4: 설정 파일 이동
- `crontab_realtime.txt` → `config/`

### Step 5: 일회성 스크립트 보관
- `disable_us_indicators.sh` → `scripts/archive/`

---

**다음**: Step 1부터 순차 진행
