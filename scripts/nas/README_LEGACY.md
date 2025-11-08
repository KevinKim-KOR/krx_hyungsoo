# NAS 알림 시스템 (레거시)

**상태**: ⚠️ **레거시**  
**최신 시스템**: `scripts/automation/`  
**생성 시기**: Phase 3 이전

---

## ⚠️ 중요 공지

이 폴더는 **Phase 3 이전에 사용하던 시스템**입니다.

**새로운 배포는 `scripts/automation/`을 사용하세요.**

---

## 📋 이 폴더의 파일들

```
scripts/nas/
├── daily_realtime_signals.sh   # 일일 신호 (레거시)
├── rising_etf_alert.py          # 상승 ETF 알림
├── market_open_alert.py         # 장 시작 알림
├── regime_change_alert.py       # 레짐 변경 알림
├── intraday_alert.py            # 장중 알림
├── weekly_report.py             # 주간 리포트 (레거시)
├── test_telegram.py             # 텔레그램 테스트
└── crontab_realtime.txt         # Cron 설정 (구버전)
```

---

## 🔄 마이그레이션 가이드

### 기존 시스템 → 새 시스템

| 기존 (scripts/nas/) | 새 시스템 (scripts/automation/) |
|-------------------|-------------------------------|
| `daily_realtime_signals.sh` | `daily_alert.sh` |
| `weekly_report.py` | `weekly_alert.sh` |
| 개별 스크립트 | 모듈화된 클래스 |
| 직접 API 호출 | `TelegramNotifier` 클래스 |

### 마이그레이션 절차

1. **새 시스템 배포**
   ```bash
   # docs/NAS_DEPLOYMENT_GUIDE.md 참조
   ```

2. **Cron 업데이트**
   ```bash
   # 기존 Cron 비활성화
   crontab -e
   # scripts/nas/ 관련 항목 주석 처리
   
   # 새 Cron 추가
   0 16 * * 1-5 /path/to/scripts/automation/daily_alert.sh
   0 10 * * 6 /path/to/scripts/automation/weekly_alert.sh
   ```

3. **테스트**
   ```bash
   # 새 시스템 수동 실행
   ./scripts/automation/daily_alert.sh
   ```

4. **기존 시스템 제거 (선택)**
   ```bash
   # 백업 후 제거
   mv scripts/nas scripts/nas_backup
   ```

---

## 📚 새 시스템 문서

- **배포 가이드**: `docs/NAS_DEPLOYMENT_GUIDE.md`
- **자동화 README**: `scripts/automation/README.md`
- **완료 보고서**: `docs/WEEK4_AUTOMATION_COMPLETE.md`

---

## 🤔 왜 새 시스템으로 전환해야 하나요?

### 기존 시스템의 한계
- ❌ 개별 스크립트로 관리 어려움
- ❌ 코드 중복
- ❌ 에러 처리 부족
- ❌ 로깅 시스템 미흡

### 새 시스템의 장점
- ✅ 모듈화된 구조
- ✅ 클래스 기반 설계
- ✅ 완벽한 에러 처리
- ✅ 체계적인 로깅
- ✅ 백테스트 히스토리 관리
- ✅ Streamlit 대시보드

---

## 📊 비교표

| 기능 | 레거시 | 최신 |
|------|--------|------|
| **일일 리포트** | 간단한 메시지 | 구조화된 리포트 |
| **주간 리포트** | 기본 요약 | 상세 분석 |
| **레짐 감지** | 개별 스크립트 | `RegimeMonitor` 클래스 |
| **텔레그램** | 직접 API | `TelegramNotifier` 클래스 |
| **에러 처리** | 최소한 | 완벽 |
| **로깅** | 기본 | 체계적 |
| **히스토리** | 없음 | SQLite DB |
| **UI** | 없음 | Streamlit 대시보드 |

---

## ⏰ 지원 종료 계획

- **현재**: 레거시 유지 (참고용)
- **1개월 후**: 레거시 폴더 이동 (`scripts/legacy/nas/`)
- **3개월 후**: 완전 제거 고려

---

## 🆘 도움이 필요하신가요?

- **새 시스템 배포**: `docs/NAS_DEPLOYMENT_GUIDE.md`
- **문제 해결**: `docs/NAS_DEPLOYMENT_GUIDE.md` 7장
- **프로젝트 구조**: `docs/PROJECT_STRUCTURE_AUDIT.md`

---

**작성일**: 2025-11-08  
**권장 조치**: `scripts/automation/` 사용
