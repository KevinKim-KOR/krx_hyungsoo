# Phase 3: 실시간 운영 시스템

## 🎯 개요

NAS에서 매일 자동으로 실행되는 실시간 매매 신호 생성 및 알림 시스템입니다.

---

## ⚡ 빠른 시작

### PC에서 테스트

```bash
# Step 1: 신호 생성 테스트
python test_realtime_signals.py

# Step 2: 알림 시스템 테스트
python test_step2_notification.py

# Step 3: 모니터링 시스템 테스트
python test_step3_monitoring.py
```

### NAS 배포

```bash
# 1. 코드 업로드
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
git pull

# 2. 텔레그램 설정
cat > secret/config.yaml << 'EOF'
notifications:
  telegram:
    bot_token: "YOUR_BOT_TOKEN"
    chat_id: YOUR_CHAT_ID
EOF

# 3. 수동 테스트
python3.8 nas/app_realtime.py

# 4. Cron 등록
crontab -e
# 40 15 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && bash scripts/nas/daily_realtime_signals.sh
```

---

## 📁 주요 파일

### 실시간 신호 생성
- `extensions/realtime/signal_generator.py` - 신호 생성 엔진
- `extensions/strategy/signal_generator.py` - MAPS 전략 로직
- `extensions/strategy/risk_manager.py` - 리스크 관리

### 알림 시스템
- `extensions/notification/formatter.py` - 메시지 포맷터
- `extensions/notification/telegram_sender.py` - 텔레그램 전송

### 모니터링
- `extensions/monitoring/tracker.py` - 신호/성과 추적
- `extensions/monitoring/reporter.py` - 리포트 생성
- `extensions/monitoring/regime.py` - 레짐 감지

### NAS 실행
- `nas/app_realtime.py` - NAS 실행 진입점
- `scripts/nas/daily_realtime_signals.sh` - 일일 실행 스크립트

---

## 🔄 실행 흐름

```
15:40 - 장마감 후 신호 생성
  ├─ 데이터 로드
  ├─ MAPS 신호 생성
  ├─ 리스크 필터링
  ├─ 포트폴리오 구성
  ├─ DB 저장
  ├─ 레짐 감지
  ├─ 리포트 생성
  └─ 텔레그램 알림
```

---

## 📊 생성되는 데이터

### DB 파일
- `data/monitoring/signals.db` - 신호 이력
- `data/monitoring/performance.db` - 성과 추적

### 리포트
- `reports/daily/report_YYYYMMDD.md` - 일일 리포트
- `reports/weekly/weekly_YYYYMMDD.md` - 주간 리포트
- `reports/realtime/signals_YYYYMMDD.csv` - 신호 CSV

---

## 🛠️ 유틸리티 스크립트

```bash
# 상태 확인
bash scripts/nas/status.sh

# DB 백업
bash scripts/nas/backup_db.sh

# 로그 정리
bash scripts/nas/cleanup_logs.sh

# 주간 리포트
python3.8 scripts/nas/weekly_report.py
```

---

## 📱 텔레그램 알림 예시

```
*[장마감] 매매 신호 알림*

📅 날짜: 2025-11-02
📊 총 신호: 5개
   • 매수: 5개
   • 매도: 0개

*🟢 매수 신호*

1. `069500` (KODEX 200)
   • 신뢰도: 75.3% | 비중: 15.0%
   • 가격: 30,500원
   • MAPS: 5.23 | RSI: 45
```

---

## 🔧 트러블슈팅

### 알림이 오지 않는 경우
```bash
# 텔레그램 설정 확인
cat secret/config.yaml

# 수동 테스트
python3.8 -c "from infra.notify.telegram import send_to_telegram; send_to_telegram('테스트')"
```

### 신호가 생성되지 않는 경우
```bash
# 데이터 캐시 확인
ls -lh data/cache/*.parquet | wc -l

# 파라미터 확인
cat best_params.json
```

### Cron이 실행되지 않는 경우
```bash
# Cron 확인
crontab -l

# 로그 확인
tail -f logs/realtime_signals_*.log
```

---

## 📚 문서

- **배포 가이드**: [docs/PHASE3_NAS_DEPLOYMENT.md](docs/PHASE3_NAS_DEPLOYMENT.md)
- **완료 보고서**: [docs/PHASE3_COMPLETION_REPORT.md](docs/PHASE3_COMPLETION_REPORT.md)
- **텔레그램 설정**: [docs/TELEGRAM_SETUP.md](docs/TELEGRAM_SETUP.md)

---

## 🎯 다음 단계

1. **NAS 배포** - 실제 운영 시작
2. **1주일 모니터링** - 안정성 확인
3. **Phase 2 재테스트** - 파라미터 최적화
4. **웹 대시보드** (선택) - 실시간 모니터링 UI

---

## 📞 문의

문제 발생 시:
1. 로그 파일 확인
2. 텔레그램 에러 알림 확인
3. 수동 실행으로 재현
4. GitHub Issues 등록

---

**버전**: 1.0  
**업데이트**: 2025-11-03
