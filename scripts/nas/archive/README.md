# Archive - 미사용 스크립트

**이동 날짜**: 2025-11-23  
**이유**: Daily Regime Check 완성으로 기능 대체

---

## 📁 보관된 파일

### 1. `regime_change_alert.py`
**원래 목적**: 시장 레짐 변경 감지 및 텔레그램 알림

**대체됨**:
- 파일: `scripts/nas/daily_regime_check.py`
- 배포: Oracle Cloud (Cron 09:00)
- 기능: 레짐 감지 + 매도 신호 + 텔레그램 알림
- 상태: 100% 완성 (2025-11-23)

**이동 이유**:
- NAS Cron에서 호출되지 않음
- `daily_regime_check.py`가 모든 기능 포함
- 중복 제거

---

### 2. `rising_etf_alert.py`
**원래 목적**: 상승 중인 ETF 알림

**대체됨**:
- 현재 사용하지 않음
- 필요 시 재구현 예정

**이동 이유**:
- NAS Cron에서 호출되지 않음
- 실제 사용 이력 없음

---

## 🔄 복원 방법

필요 시 다음 명령어로 복원 가능:

```bash
# PC
cd "e:/AI Study/krx_alertor_modular"
cp scripts/nas/archive/regime_change_alert.py scripts/nas/
cp scripts/nas/archive/rising_etf_alert.py scripts/nas/

# NAS
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
cp scripts/nas/archive/regime_change_alert.py scripts/nas/
cp scripts/nas/archive/rising_etf_alert.py scripts/nas/
```

---

## 📊 현재 사용 중인 스크립트

### NAS Cron
- `market_open_alert.py` - 장 시작 알림
- `intraday_alert.py` - 장중 알림 (10:00, 14:00)
- `daily_report_alert.py` - 일일 리포트 (16:00)
- `weekly_report_alert.py` - 주간 리포트 (토 10:00)

### Oracle Cloud Cron
- `daily_regime_check.py` - 레짐 감지 및 매도 신호 (09:00)

---

**참고**: 이 파일들은 삭제되지 않고 보관됩니다.
