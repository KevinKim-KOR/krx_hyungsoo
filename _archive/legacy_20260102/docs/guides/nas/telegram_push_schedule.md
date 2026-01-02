# 텔레그램 PUSH 알림 스케줄

**작성일**: 2025-11-08  
**상태**: ✅ 실제 API 호출 수정 완료

---

## 📱 PUSH 알림 시스템 개요

### 텔레그램 알림 구조

| 구분 | 파일 | API 호출 | 상태 |
|------|------|----------|------|
| **실제 전송** | `infra/notify/telegram.py` | ✅ requests 사용 | 정상 |
| **자동화 시스템** | `extensions/automation/telegram_notifier.py` | ✅ requests 사용 (수정 완료) | 정상 |

---

## 🕐 PUSH 알림 스케줄 및 역할

### 1️⃣ 장 시작 알림 (Market Open Alert)

**파일**: `scripts/nas/market_open_alert.py`

**역할**:
- 장 시작 전 포트폴리오 현황 확인
- 총 자산, 현금, 포지션 수, 누적 수익률 요약
- 하루 시작 준비 상태 점검

**실행 시간**: **평일 09:00** (장 시작 전)

**Cron 설정**:
```bash
0 9 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python3.8 scripts/nas/market_open_alert.py
```

**메시지 예시**:
```
[장 시작] 포트폴리오 현황

📅 2025-11-08

💰 총 자산: 11,500,000원
💵 현금: 2,500,000원
📊 포지션: 3개
📈 누적 수익률: 15.00%

오늘도 좋은 하루 되세요!
```

**API 호출**: ✅ `infra/notify/telegram.py` (정상 작동)

---

### 2️⃣ 레짐 변경 알림 (Regime Change Alert)

**파일**: `scripts/nas/regime_change_alert.py`

**역할**:
- 시장 레짐 변경 감지 (상승장 ↔ 중립장 ↔ 하락장)
- 레짐 변경 시에만 알림 전송
- 포트폴리오 리스크 관리 경고

**실행 시간**: **평일 09:30** (장 시작 직후)

**Cron 설정**:
```bash
30 9 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python3.8 scripts/nas/regime_change_alert.py
```

**메시지 예시**:
```
[시장 레짐 변경]

📅 2025-11-08

📈 상승장 → ➡️ 중립장

현재 상태
레짐: 중립장
신뢰도: 85%
권장 포지션: 80%

포트폴리오 리스크 관리에 유의하세요.
```

**API 호출**: ✅ `infra/notify/telegram.py` (정상 작동)

---

### 3️⃣ 장중 급등/급락 알림 (Intraday Alert)

**파일**: `scripts/nas/intraday_alert.py`

**역할**:
- 장중 급등/급락 종목 감지 (±3% 이상)
- 주요 종목 실시간 모니터링
- 빠른 대응 기회 제공

**실행 시간**: **평일 11:00, 14:00** (장중 2회)

**Cron 설정**:
```bash
0 11 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python3.8 scripts/nas/intraday_alert.py
0 14 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python3.8 scripts/nas/intraday_alert.py
```

**메시지 예시**:
```
[장중 알림] 급등/급락

📅 2025-11-08

🟢 005930 삼성전자
   변동: +3.50%
   가격: 72,500원

🔴 000660 SK하이닉스
   변동: -3.20%
   가격: 135,000원
```

**API 호출**: ✅ `infra/notify/telegram.py` (정상 작동)

---

### 4️⃣ 일일 리포트 (Daily Report)

**파일**: `scripts/automation/daily_alert.sh` → `run_daily_report.py`

**역할**:
- 장 마감 후 당일 성과 요약
- 포트폴리오 현황 (평가액, 수익률, 보유 종목)
- 시장 레짐 상태
- 매매 신호 (매수/매도 추천)

**실행 시간**: **평일 16:00** (장 마감 후)

**Cron 설정**:
```bash
0 16 * * 1-5 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/automation/daily_alert.sh
```

**메시지 예시**:
```
📊 일일 투자 리포트
📅 날짜: 2025년 11월 08일

💼 포트폴리오 현황
  평가액: 11,500,000원
  수익: +1,500,000원 (+15.00%)
  보유 종목: 3개

🎯 시장 레짐
  📈 현재 레짐: 상승장
  📊 신뢰도: 100.0%
  💪 포지션 비율: 120%

📈 매매 신호
  🟢 매수: 7개
    - KODEX 200 (MAPS: 85.2)
    - TIGER 미국S&P500 (MAPS: 82.1)
  🔴 매도: 없음

⚠️ 주의사항
  - 현재 상승장 유지 중
  - 포지션 비율 120% 권장
```

**API 호출**: ✅ `extensions/automation/telegram_notifier.py` (수정 완료)

---

### 5️⃣ 주간 리포트 (Weekly Report - scripts/automation)

**파일**: `scripts/automation/weekly_alert.sh` → `run_weekly_report.py`

**역할**:
- 주간 성과 종합 분석
- 레짐 변화 히스토리
- 다음 주 전망 및 전략 제안

**실행 시간**: **토요일 10:00**

**Cron 설정**:
```bash
0 10 * * 6 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/automation/weekly_alert.sh
```

**메시지 예시**:
```
📊 주간 투자 리포트
📅 기간: 2025-11-01 ~ 2025-11-08

🎯 시장 레짐 분석
  📈 상승장: 1일 (100.0%)
  🔄 레짐 변경: 0회

  현재 레짐: 📈 상승장
  신뢰도: 100.0%

🔮 다음 주 전망
  ✅ 상승 추세 지속 예상
  💡 공격적 포지션 유지
```

**API 호출**: ✅ `extensions/automation/telegram_notifier.py` (수정 완료)

---

### 6️⃣ 주간 리포트 (Weekly Report - scripts/nas)

**파일**: `scripts/nas/weekly_report.py`

**역할**:
- 주간 신호 추적 및 성과 분석
- 상세 리포트 파일 생성 (`reports/weekly/`)
- 텔레그램으로 요약 전송

**실행 시간**: **토요일 11:00** (automation 이후)

**Cron 설정**:
```bash
0 11 * * 6 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python3.8 scripts/nas/weekly_report.py
```

**메시지 예시**:
```
[주간 리포트] 2025-11-01 ~ 2025-11-08

주간 신호 요약
  매수 신호: 35개
  매도 신호: 12개
  평균 MAPS: 78.5

성과 분석
  승률: 65%
  평균 수익률: +2.3%

전체 리포트: weekly_20251108.md
```

**API 호출**: ✅ `infra/notify/telegram.py` (정상 작동)

---

## 📅 전체 스케줄 타임라인

### 평일 (월~금)

```
09:00 ─── 장 시작 알림 (market_open_alert.py)
          └─ 포트폴리오 현황

09:30 ─── 레짐 변경 알림 (regime_change_alert.py)
          └─ 레짐 변경 감지 (변경 시에만)

11:00 ─── 장중 알림 (intraday_alert.py)
          └─ 급등/급락 종목

14:00 ─── 장중 알림 (intraday_alert.py)
          └─ 급등/급락 종목

16:00 ─── 일일 리포트 (daily_alert.sh)
          └─ 당일 성과 + 매매 신호
```

### 주말 (토요일)

```
10:00 ─── 주간 리포트 (weekly_alert.sh)
          └─ 주간 성과 + 다음 주 전망

11:00 ─── 주간 리포트 (weekly_report.py)
          └─ 상세 분석 + 파일 저장
```

---

## 🔧 Cron 전체 설정

NAS에서 다음 명령어로 Cron 등록:

```bash
crontab -e
```

전체 설정 추가:

```bash
# ========================================
# 텔레그램 PUSH 알림 스케줄
# ========================================

# 1. 장 시작 알림 (평일 09:00)
0 9 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python3.8 scripts/nas/market_open_alert.py

# 2. 레짐 변경 알림 (평일 09:30)
30 9 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python3.8 scripts/nas/regime_change_alert.py

# 3. 장중 알림 (평일 11:00, 14:00)
0 11 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python3.8 scripts/nas/intraday_alert.py
0 14 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python3.8 scripts/nas/intraday_alert.py

# 4. 일일 리포트 (평일 16:00)
0 16 * * 1-5 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/automation/daily_alert.sh

# 5. 주간 리포트 (토요일 10:00, 11:00)
0 10 * * 6 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/automation/weekly_alert.sh
0 11 * * 6 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python3.8 scripts/nas/weekly_report.py
```

---

## ✅ 수정 완료 사항

### 문제
- `extensions/automation/telegram_notifier.py`가 실제 API를 호출하지 않음
- `daily_alert.sh`, `weekly_alert.sh` 실행 시 메시지 미수신

### 해결
- `telegram_notifier.py`의 `send_message()` 수정
- 주석 처리된 코드 → `requests` 직접 호출로 변경
- 실제 텔레그램 API 호출 활성화

### 변경 코드
```python
# 수정 전 (주석 처리)
# import telegram
# bot = telegram.Bot(token=self.bot_token)
# bot.send_message(...)
logger.info(f"텔레그램 메시지 전송: {len(message)}자")

# 수정 후 (실제 API 호출)
import requests
url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
data = {
    'chat_id': self.chat_id,
    'text': message,
    'parse_mode': parse_mode
}
response = requests.post(url, json=data)
response.raise_for_status()
logger.info(f"텔레그램 메시지 전송 성공: {len(message)}자")
```

---

## 🧪 테스트 방법

### 1. 개별 스크립트 테스트

```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular

# 장 시작 알림
python3.8 scripts/nas/market_open_alert.py

# 레짐 변경 알림
python3.8 scripts/nas/regime_change_alert.py

# 장중 알림
python3.8 scripts/nas/intraday_alert.py

# 일일 리포트
bash scripts/automation/daily_alert.sh

# 주간 리포트
bash scripts/automation/weekly_alert.sh
python3.8 scripts/nas/weekly_report.py
```

### 2. 로그 확인

```bash
# 일일 리포트 로그
tail -f logs/automation/daily_alert_$(date +%Y%m%d).log

# 주간 리포트 로그
tail -f logs/automation/weekly_alert_$(date +%Y%m%d).log

# 개별 스크립트 로그
tail -f logs/app.log
```

### 3. Cron 확인

```bash
# Cron 목록 확인
crontab -l

# Cron 로그 확인 (Synology)
cat /var/log/cron.log | grep krx
```

---

## 📊 알림 빈도 요약

| 알림 | 평일 | 주말 | 총 (주간) |
|------|------|------|-----------|
| **장 시작** | 5회 | 0회 | 5회 |
| **레짐 변경** | 0~5회 | 0회 | 0~5회 (변경 시만) |
| **장중** | 10회 | 0회 | 10회 |
| **일일 리포트** | 5회 | 0회 | 5회 |
| **주간 리포트** | 0회 | 2회 | 2회 |
| **합계** | 20~25회 | 2회 | **22~27회** |

---

## 💡 운영 팁

### 1. 알림 과다 시
- 장중 알림 빈도 조정 (11:00, 14:00 → 13:00만)
- 급등/급락 기준 상향 (3% → 5%)

### 2. 알림 부족 시
- 장중 알림 추가 (10:00, 13:00, 15:00)
- 레짐 신뢰도 임계값 하향 (85% → 70%)

### 3. 문제 해결
- 로그 확인: `logs/automation/`, `logs/app.log`
- 환경 변수 확인: `source .env && echo $TELEGRAM_BOT_TOKEN`
- API 테스트: `curl https://api.telegram.org/bot<TOKEN>/getMe`

---

**작성자**: Cascade AI  
**최종 업데이트**: 2025-11-08  
**다음 작업**: NAS Cron 등록 및 실전 모니터링
