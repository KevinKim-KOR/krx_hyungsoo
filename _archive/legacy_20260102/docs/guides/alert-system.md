# 알림 시스템 가이드

**최종 업데이트**: 2025-11-27  
**버전**: 2.0 (Phase 4 완료)

---

## 📋 목차

1. [개요](#개요)
2. [알림 유형](#알림-유형)
3. [설정 방법](#설정-방법)
4. [문제 해결](#문제-해결)
5. [개선 이력](#개선-이력)

---

## 개요

KRX Alertor의 알림 시스템은 3가지 유형의 텔레그램 알림을 제공합니다:

1. **장중 알림** - 새로운 투자 기회 발굴
2. **장시작 알림** - 일일 시장 상황 및 보유 종목 현황
3. **EOD 알림** - 장 마감 후 매매 신호

---

## 알림 유형

### 1. 장중 알림 (Intraday Alert) 🔍

**목적**: 보유하지 않은 종목 중 급등/급락 발견

**특징**:
- 보유 종목 제외 (이미 보유한 종목은 알림 불필요)
- 급등 상위 10개 표시
- 급락 상위 5개 표시 (저가 매수 기회)
- ETF 특성별 기준 적용
- 거래대금 50억원 이상만

**알림 기준**:
```python
THRESHOLDS = {
    'leverage': 3.0,      # 레버리지 ETF: 3% 이상
    'sector': 2.0,        # 섹터 ETF: 2% 이상
    'index': 1.5,         # 지수 ETF: 1.5% 이상
    'overseas': 1.5,      # 해외 ETF: 1.5% 이상
    'default': 2.0        # 기본: 2% 이상
}

MIN_TRADE_VALUE = 50e8  # 50억원 이상
```

**Cron 설정**:
```bash
# 장중 알림 (평일 10:00, 14:00)
0 10,14 * * 1-5 /path/to/scripts/automation/intraday_alert.sh
```

**알림 예시**:
```
[장중 알림] 새로운 투자 기회

📅 2025-11-11
🔍 신규 투자 기회: 15개
💼 현재 보유: 28개 (제외됨)

🟢 급등 ETF (신규 투자 기회)
1. UNICORN SK하이닉스밸류체인액티브 (494220)
   금일: +6.17% | 가격: 12,345원
   거래대금: 138.8억원

2. KODEX 200IT TR (363580)
   금일: +5.36% | 가격: 23,456원
   거래대금: 305.7억원

... (상위 10개)

🔴 급락 ETF (저가 매수 기회)
1. KODEX 은행 (091170)
   금일: -2.15% | 가격: 12,585원
   거래대금: 187.8억원

... (상위 5개)
```

---

### 2. 장시작 알림 (Market Open Alert) 🌅

**목적**: 일일 시장 상황 및 보유 종목 현황 확인

**특징**:
- 실제 보유 종목 현황 (API 연동)
- 총 자산, 현금, 포지션 비율
- 오늘의 주요 이슈
- 레짐 상태 (상승/중립/하락)

**Cron 설정**:
```bash
# 장시작 알림 (평일 09:00)
0 9 * * 1-5 /path/to/scripts/automation/market_open_alert.sh
```

**알림 예시**:
```
[장시작 알림] 오늘의 시장

📅 2025-11-11 (월)
📊 레짐: 상승장 (신뢰도 92%)

💰 포트폴리오 현황
- 총 자산: 10,500,000원
- 현금: 2,100,000원 (20%)
- 포지션: 8,400,000원 (80%)
- 보유 종목: 15개

📈 오늘의 주요 이슈
- 미국 증시: S&P 500 +0.5%
- 환율: 1,320원 (전일 대비 -5원)
- 주요 뉴스: 반도체 수출 증가
```

---

### 3. EOD 알림 (End-of-Day Alert) 📊

**목적**: 장 마감 후 매매 신호 제공

**특징**:
- 매수 신호 (Top 5)
- 매도 신호 (보유 종목 중)
- 신호 없으면 알림 없음
- 실제 포트폴리오 반영

**Cron 설정**:
```bash
# EOD 알림 (평일 15:30)
30 15 * * 1-5 /path/to/scripts/automation/eod_alert.sh
```

**알림 예시**:
```
[EOD 알림] 매매 신호

📅 2025-11-11

🟢 매수 신호 (5개)
1. TIGER 미국나스닥100 (133690)
   신호: 강한 매수 | 점수: 8.5
   현재가: 45,600원 | 전일 대비: +2.3%

2. KODEX 200 (069500)
   신호: 매수 | 점수: 7.2
   현재가: 38,900원 | 전일 대비: +1.1%

... (5개)

🔴 매도 신호 (2개)
1. KODEX 은행 (091170)
   신호: 손절 | 수익률: -8.5%
   현재가: 12,585원 | 보유 수량: 10주

2. TIGER 차이나전기차SOLACTIVE (371460)
   신호: 약세 | 수익률: -3.2%
   현재가: 8,920원 | 보유 수량: 20주
```

---

## 설정 방법

### 1. 텔레그램 봇 생성

1. **BotFather에서 봇 생성**
   ```
   /newbot
   봇 이름 입력
   봇 사용자명 입력
   ```

2. **토큰 저장**
   ```
   BotFather가 제공하는 토큰 복사
   예: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   ```

3. **Chat ID 확인**
   ```
   봇에게 메시지 전송
   브라우저에서 확인:
   https://api.telegram.org/bot<TOKEN>/getUpdates
   
   "chat":{"id":123456789} 부분 확인
   ```

### 2. 환경 변수 설정

`.env` 파일에 추가:
```bash
# 텔레그램 설정
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

### 3. Cron 설정 (NAS/Oracle Cloud)

```bash
# crontab 편집
crontab -e

# 알림 추가
0 9 * * 1-5 /path/to/scripts/automation/market_open_alert.sh
0 10,14 * * 1-5 /path/to/scripts/automation/intraday_alert.sh
30 15 * * 1-5 /path/to/scripts/automation/eod_alert.sh
```

### 4. 테스트

```bash
# 장중 알림 테스트
python scripts/automation/intraday_alert.py

# 장시작 알림 테스트
python scripts/automation/market_open_alert.py

# EOD 알림 테스트
python scripts/automation/eod_alert.py
```

---

## 문제 해결

### 알림이 오지 않을 때

**1. 텔레그램 설정 확인**
```bash
# .env 파일 확인
cat .env | grep TELEGRAM

# 예상 출력:
# TELEGRAM_ENABLED=true
# TELEGRAM_BOT_TOKEN=123456789:...
# TELEGRAM_CHAT_ID=123456789
```

**2. 네트워크 확인**
```bash
# 텔레그램 API 접근 확인
curl https://api.telegram.org/bot<TOKEN>/getMe
```

**3. 로그 확인**
```bash
# 알림 로그 확인
tail -f logs/automation.log

# 예상 출력:
# INFO: 텔레그램 알림 전송 성공
# 또는
# ERROR: 텔레그램 알림 전송 실패 - <원인>
```

### 알림이 너무 많을 때

**장중 알림 기준 조정**:

`scripts/automation/intraday_alert.py` 수정:
```python
# 기준 상향 조정
THRESHOLDS = {
    'leverage': 4.0,      # 3.0 → 4.0
    'sector': 3.0,        # 2.0 → 3.0
    'index': 2.0,         # 1.5 → 2.0
    'overseas': 2.0,      # 1.5 → 2.0
    'default': 3.0        # 2.0 → 3.0
}

# 거래대금 기준 상향
MIN_TRADE_VALUE = 100e8  # 50억 → 100억
```

### 알림이 너무 적을 때

**장중 알림 기준 하향**:

`scripts/automation/intraday_alert.py` 수정:
```python
# 기준 하향 조정
THRESHOLDS = {
    'leverage': 2.0,      # 3.0 → 2.0
    'sector': 1.5,        # 2.0 → 1.5
    'index': 1.0,         # 1.5 → 1.0
    'overseas': 1.0,      # 1.5 → 1.0
    'default': 1.5        # 2.0 → 1.5
}

# 거래대금 기준 하향
MIN_TRADE_VALUE = 30e8  # 50억 → 30억
```

---

## 개선 이력

### v2.0 (2025-11-13) - Phase 4 완료

**주요 개선**:
1. ✅ 장중 알림 - ETF 누락 문제 해결
   - 수동 14개 → 전체 ETF 자동 조회
   - PyKRX 연동으로 실시간 ETF 목록 확보

2. ✅ 장시작 알림 - 더미 데이터 제거
   - 백테스트 데이터 → 실제 API 연동
   - 실시간 보유 종목 현황 반영

3. ✅ EOD 알림 - 빈 메시지 제거
   - 신호 없으면 알림 없음
   - 실제 포트폴리오 반영

**수정 파일**:
- `scripts/automation/intraday_alert.py`
- `scripts/automation/market_open_alert.py`
- `scripts/automation/eod_alert.py`

---

### v1.1 (2025-11-11) - 알림 기준 개선

**주요 개선**:
1. ✅ 장중 알림 - 특성별 차별화된 기준
   - 레버리지 ETF: 3% 이상
   - 섹터 ETF: 2% 이상
   - 지수 ETF: 1.5% 이상

2. ✅ 보유 종목 우선 알림
   - 1순위: 보유 종목 급등/급락
   - 2순위: 기타 주요 ETF

3. ✅ 거래대금 필터 추가
   - 최소 50억원 이상만 알림

**수정 파일**:
- `scripts/automation/intraday_alert.py`

---

### v1.0 (2025-11-08) - 초기 버전

**기능**:
- 장중 알림 (10:00, 14:00)
- 장시작 알림 (09:00)
- EOD 알림 (15:30)

---

## 참고 문서

- [텔레그램 봇 API 문서](https://core.telegram.org/bots/api)
- [Cron 설정 가이드](./cron-setup.md)
- [문제 해결 가이드](../deployment/troubleshooting.md)

---

## 관련 파일

**스크립트**:
- `scripts/automation/intraday_alert.py`
- `scripts/automation/market_open_alert.py`
- `scripts/automation/eod_alert.py`
- `scripts/automation/intraday_alert.sh`
- `scripts/automation/market_open_alert.sh`
- `scripts/automation/eod_alert.sh`

**설정**:
- `.env` (텔레그램 설정)
- `config/alert_config.yaml` (알림 기준)

**로그**:
- `logs/automation.log`

---

**문서 통합 이력**:
- 2025-11-27: ALERT_SYSTEM_FINAL.md, ALERT_SYSTEM_FIX.md, ALERT_SYSTEM_IMPROVEMENT.md 통합
- 이전 문서들은 Git 이력에 보존됨
