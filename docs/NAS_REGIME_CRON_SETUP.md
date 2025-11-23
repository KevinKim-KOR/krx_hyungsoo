# NAS 레짐 감지 Cron 설정 가이드

**작성일**: 2025-11-23  
**목적**: NAS에서 매일 오전 9시 레짐 감지 및 매도 신호 알림

---

## 📋 개요

매일 오전 9시 (장 시작 전) 시장 레짐을 감지하고, 변화 시 텔레그램 알림을 전송합니다.

### 주요 기능
1. **한국 시장 레짐 감지** (KOSPI 50/200일 이동평균)
2. **미국 시장 지표 모니터링** (나스닥, S&P 500, VIX)
3. **보유 종목 매도 신호 생성**
4. **텔레그램 알림 전송**

---

## 🚀 설정 방법

### 1. NAS SSH 접속

```bash
ssh your_username@your_nas_ip
```

### 2. Cron 편집

```bash
crontab -e
```

### 3. Cron 작업 추가

```bash
# 매일 오전 9시 레짐 감지 (평일만)
0 9 * * 1-5 /volume2/homes/Hyungsoo/krx/krx_alertor_modular/scripts/nas/daily_regime_check.sh >> /volume2/homes/Hyungsoo/krx/logs/regime_check.log 2>&1
```

**설명**:
- `0 9 * * 1-5`: 평일 (월~금) 오전 9시
- `>>`: 로그 파일에 추가
- `2>&1`: 에러도 로그에 기록

### 4. Cron 저장 및 종료

- `ESC` → `:wq` → `Enter` (vi 에디터)
- 또는 `Ctrl+X` → `Y` → `Enter` (nano 에디터)

### 5. Cron 확인

```bash
crontab -l
```

---

## 📁 파일 구조

```
krx_alertor_modular/
├── scripts/nas/
│   ├── daily_regime_check.sh      # Shell 스크립트
│   ├── daily_regime_check.py      # Python 메인 로직
│   └── regime_change_alert.py     # 텔레그램 알림
├── data/state/
│   └── current_regime.json        # 현재 레짐 상태
└── logs/
    └── regime_check.log           # 실행 로그
```

---

## 🔧 텔레그램 봇 설정

### 1. BotFather에서 봇 생성

1. 텔레그램에서 `@BotFather` 검색
2. `/newbot` 명령어 입력
3. 봇 이름 설정
4. **토큰 복사** (예: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Chat ID 확인

1. 봇과 대화 시작 (메시지 1개 전송)
2. 브라우저에서 접속:
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```
3. `"chat":{"id":123456789}` 부분에서 **Chat ID 복사**

### 3. .env 파일 설정

```bash
# NAS에서 실행
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
nano .env
```

```bash
# 텔레그램 설정
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

---

## ⚙️ Python 3.8 호환성 설정 (중요!)

### yfinance 문제 해결

NAS는 Python 3.8을 사용하므로 yfinance 최신 버전과 호환되지 않습니다.

**Option 1: yfinance 다운그레이드** (빠른 해결)
```bash
# NAS SSH 접속 후
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
pip3 install yfinance==0.2.28 --upgrade
```

**Option 2: 네이버 금융 사용** (이미 적용됨 ✅)
- 한국 주식: 네이버 금융 자동 사용
- 미국 주식: yfinance 필요 (다운그레이드 권장)
- 코드에 이미 폴백 로직 구현됨

### 필수 패키지 설치

```bash
pip3 install requests beautifulsoup4 pyyaml --upgrade
```

---

## 📊 알림 예시

### 레짐 변화 알림

```
🚨 시장 레짐 변화 감지

📍 한국 시장:
➡️ 이전: 상승장
📉 현재: 중립장
📊 신뢰도: 87.5%

🇺🇸 미국 시장:
📉 레짐: bearish

📌 나스닥 50일선 - AI/반도체 섹터 모멘텀
   현재가: 15,000
   이동평균: 15,800
   괴리율: -5.06%
   신호: bearish

💰 권장 조치:
- 현금 보유율: 40~50% 🔥
- 포지션 크기: 50~60%
- 전략: 중립적 투자

⚠️ 보유 종목 매도 신호 (3건)

📌 삼성전자 (005930)
   수량: 50주
   평균가: 70,000원
   사유: 중립장 전환 (일부 매도 권장)
```

---

## 🧪 테스트

### 1. 패키지 설치 확인

```bash
# NAS SSH 접속
ssh Hyungsoo@your_nas_ip

# 필수 패키지 설치
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
pip3 install yfinance==0.2.28 requests beautifulsoup4 pyyaml --upgrade
```

### 2. 수동 실행 (테스트)

```bash
# Python 직접 실행 (권장)
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
python3 scripts/nas/daily_regime_check.py

# 또는 Shell 스크립트
bash scripts/nas/daily_regime_check.sh
```

**예상 출력**:
```
========================================
일일 레짐 감지 시작
========================================

INFO: KOSPI 데이터 조회 중...
INFO: 레짐 감지 완료: 상승장 (신뢰도: 87.5%)
INFO: 미국 시장 지표 조회 중...
INFO: 텔레그램 알림 전송 완료
```

### 3. 로그 확인

```bash
# 실시간 로그 확인
tail -f /volume2/homes/Hyungsoo/krx/logs/regime_check.log

# 전체 로그 확인
cat /volume2/homes/Hyungsoo/krx/logs/regime_check.log
```

### 4. 텔레그램 알림 확인

- 봇에서 메시지 수신 확인
- 레짐 정보 표시 확인
- 매도 신호 표시 확인

---

## 🔍 문제 해결

### 1. TypeError: 'type' object is not subscriptable

**증상**:
```
TypeError: 'type' object is not subscriptable
  File "multitasking/__init__.py", line 44, in PoolConfig
    engine: Union[type[Thread], type[Process]]
```

**원인**: Python 3.8에서 yfinance 최신 버전 호환 문제

**해결**:
```bash
pip3 install yfinance==0.2.28 --upgrade
```

### 2. Python 모듈 없음

```bash
pip3 install pyyaml requests beautifulsoup4 yfinance==0.2.28 --upgrade
```

### 3. 권한 오류

```bash
chmod +x scripts/nas/daily_regime_check.sh
```

### 4. 텔레그램 알림 안 옴

**체크리스트**:
- [ ] `.env` 파일 존재 확인
- [ ] `TELEGRAM_BOT_TOKEN` 정확한지 확인
- [ ] `TELEGRAM_CHAT_ID` 정확한지 확인
- [ ] 봇과 대화 시작했는지 확인 (메시지 1개 전송)
- [ ] 방화벽 확인 (NAS → 텔레그램 API)

**테스트**:
```bash
# .env 파일 확인
cat .env | grep TELEGRAM

# 수동 알림 테스트
python3 -c "
import os
from dotenv import load_dotenv
import requests

load_dotenv()
token = os.getenv('TELEGRAM_BOT_TOKEN')
chat_id = os.getenv('TELEGRAM_CHAT_ID')

url = f'https://api.telegram.org/bot{token}/sendMessage'
data = {'chat_id': chat_id, 'text': '테스트 메시지'}
response = requests.post(url, data=data)
print(response.json())
"
```

### 5. KOSPI 데이터 없음

**yfinance 실패 시**:
```bash
# 캐시 삭제 후 재시도
rm -rf data/cache/ohlcv/^KS11.parquet
python3 scripts/nas/daily_regime_check.py
```

**네이버 금융 사용** (코드에 이미 구현됨):
- 한국 주식은 자동으로 네이버 금융 사용
- 과거 데이터는 yfinance 필요

### 6. 미국 시장 지표 조회 실패

**원인**: yfinance 버전 문제 또는 네트워크

**해결**:
```bash
# yfinance 다운그레이드
pip3 install yfinance==0.2.28 --upgrade

# 또는 미국 지표 비활성화 (임시)
nano config/us_market_indicators.yaml
# enabled: false로 변경
```

---

## 📅 실행 시간표

| 시간 | 작업 | 설명 |
|-----|------|------|
| 09:00 | 레짐 감지 | 장 시작 전 레짐 확인 |
| 16:00 | 일일 리포트 | 장 마감 후 성과 확인 |
| 토 10:00 | 주간 리포트 | 주간 성과 요약 |

---

## 🎯 다음 단계

1. ✅ NAS Cron 설정
2. ⏳ WebUI에서 레짐 파라미터 수정
3. ⏳ Oracle Cloud 외부 접속 설정
4. ⏳ 백테스트 UI 개선

---

## 📚 참고 문서

- `docs/REGIME_MONITORING_GUIDE.md` - 상세 가이드
- `config/us_market_indicators.yaml` - 미국 시장 지표 설정
- `scripts/nas/daily_regime_check.py` - 메인 스크립트
