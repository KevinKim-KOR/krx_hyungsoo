# Week 4 자동화 시스템

**상태**: ✅ **최신** (2025-11-08)  
**용도**: 운영 환경 (NAS)  
**Phase**: Week 4 완료

---

## 📋 이 폴더는?

Week 4에서 구현한 **최신 자동화 시스템**입니다.

### 주요 기능
- ✅ 일일 리포트 자동 생성 및 텔레그램 전송
- ✅ 주간 리포트 자동 생성 및 텔레그램 전송
- ✅ 레짐 감지 및 알림
- ✅ 매매 신호 생성 및 알림

---

## 📁 파일 구조

```
scripts/automation/
├── daily_alert.sh           # 일일 리포트 실행 (Cron)
├── weekly_alert.sh          # 주간 리포트 실행 (Cron)
├── run_daily_report.py      # 일일 리포트 Python 스크립트
├── run_weekly_report.py     # 주간 리포트 Python 스크립트
├── test_automation.py       # Day 1 테스트
├── test_reports.py          # Day 2 테스트
└── README.md                # 이 파일
```

---

## 🚀 사용 방법

### 1. 배포 가이드
**메인 가이드**: `docs/NAS_DEPLOYMENT_GUIDE.md`

### 2. Cron 설정

```bash
# 일일 리포트: 평일 오후 4시 (장 마감 후)
0 16 * * 1-5 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/automation/daily_alert.sh

# 주간 리포트: 토요일 오전 10시
0 10 * * 6 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/automation/weekly_alert.sh
```

### 3. 수동 실행 (테스트)

```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular

# 일일 리포트
./scripts/automation/daily_alert.sh

# 주간 리포트
./scripts/automation/weekly_alert.sh
```

---

## 🔄 기존 시스템과의 차이

| 항목 | scripts/nas/ (레거시) | scripts/automation/ (최신) |
|------|---------------------|--------------------------|
| **생성 시기** | Phase 3 이전 | Week 4 (2025-11-08) |
| **구조** | 개별 스크립트 | 모듈화된 클래스 |
| **텔레그램** | 직접 API 호출 | `TelegramNotifier` 클래스 |
| **레짐 감지** | 개별 스크립트 | `RegimeMonitor` 클래스 |
| **리포트** | 간단한 메시지 | 구조화된 리포트 |
| **상태** | ⚠️ 레거시 | ✅ 최신 |

**권장**: `scripts/automation/` 사용

---

## 📊 관련 모듈

### Python 모듈
```
extensions/automation/
├── data_updater.py          # 데이터 수집
├── regime_monitor.py        # 레짐 감지
├── signal_generator.py      # 신호 생성
├── telegram_notifier.py     # 텔레그램 알림
├── daily_report.py          # 일일 리포트
└── weekly_report.py         # 주간 리포트
```

### UI 모듈
```
extensions/ui/
├── backtest_database.py     # 히스토리 DB
└── dashboard.py             # Streamlit 대시보드
```

---

## 🐛 문제 해결

### 로그 확인
```bash
# 최신 로그
tail -f logs/automation/daily_alert_$(date +%Y%m%d).log

# 에러 확인
grep -i error logs/automation/*.log
```

### 텔레그램 알림이 안 오는 경우
1. `.env` 파일 확인
2. `TELEGRAM_BOT_TOKEN` 및 `TELEGRAM_CHAT_ID` 확인
3. `python-telegram-bot` 설치 확인

**상세 가이드**: `docs/NAS_DEPLOYMENT_GUIDE.md` 7장 참조

---

## 📚 관련 문서

- **배포 가이드**: `docs/NAS_DEPLOYMENT_GUIDE.md`
- **완료 보고서**: `docs/WEEK4_AUTOMATION_COMPLETE.md`
- **Phase 2 요약**: `docs/PHASE2_COMPLETE_SUMMARY.md`
- **프로젝트 구조**: `docs/PROJECT_STRUCTURE_AUDIT.md`

---

## 🎯 다음 단계

1. NAS 배포 (`docs/NAS_DEPLOYMENT_GUIDE.md` 참조)
2. Cron 설정
3. 텔레그램 봇 설정
4. 실전 운영 시작

---

**작성일**: 2025-11-08  
**버전**: 1.0.0  
**상태**: ✅ 운영 준비 완료
