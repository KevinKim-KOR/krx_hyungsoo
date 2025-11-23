# DS220J NAS 최적화 설정 가이드

## 🎯 목표

DS220J 저사양 NAS에서 **핵심 기능만** 안정적으로 실행

---

## ✅ 핵심 기능 (유지)

1. **한국 시장 레짐 감지**
   - KOSPI 50/200일 이동평균
   - 상승장/중립장/하락장 판단
   - 신뢰도 계산

2. **보유 종목 매도 신호**
   - 레짐 변경 시 자동 알림
   - 손실/수익 기준 알림

3. **텔레그램 알림**
   - 일일 레짐 리포트
   - 매도 신호 알림

---

## ⚠️ 제외 기능 (Oracle Cloud 이전 시 활성화)

1. **미국 시장 지표**
   - Nasdaq 50일선
   - S&P 500 200일선
   - VIX 변동성 지수

**이유**:
- DS220J 저사양 (CPU: Realtek RTD1296, RAM: 2GB)
- yfinance 설치 어려움 (lxml 빌드 실패)
- FinanceDataReader 설치 어려움
- 미국 지표는 보조 기능 (필수 아님)

---

## 🚀 즉시 실행 가이드

### Step 1: Git Pull

```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
git pull
```

### Step 2: 미국 지표 비활성화

```bash
# 자동 스크립트 실행
bash scripts/nas/disable_us_indicators.sh
```

**또는 수동**:
```bash
nano config/us_market_indicators.yaml
```

```yaml
nasdaq_50ma:
  enabled: false  # true → false

sp500_200ma:
  enabled: false  # true → false

vix:
  enabled: false  # true → false
```

### Step 3: 테스트 실행

```bash
python3 scripts/nas/daily_regime_check.py
```

**예상 출력**:
```
========================================
일일 레짐 감지 시작
========================================

INFO: KOSPI 데이터 조회 중...
INFO: 레짐 감지 완료: 상승장 (신뢰도: 87.5%)
INFO: 보유 종목 매도 신호 확인 중...
INFO: 텔레그램 알림 전송 완료

✅ 일일 레짐 감지 완료
```

### Step 4: Cron 설정 확인

```bash
crontab -l | grep regime_check
```

**예상 출력**:
```
0 9 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python3 scripts/nas/daily_regime_check.py >> /volume2/homes/Hyungsoo/krx/logs/regime_check.log 2>&1
```

---

## 📊 DS220J 성능 최적화

### 현재 설정 (최적화됨)

| 항목 | 상태 | 이유 |
|-----|------|------|
| **yfinance** | ❌ 비활성화 | lxml 빌드 실패 |
| **FinanceDataReader** | ❌ 비활성화 | 설치 실패 |
| **미국 지표** | ❌ 비활성화 | 데이터 소스 없음 |
| **한국 레짐 감지** | ✅ 활성화 | 네이버 금융 사용 |
| **매도 신호** | ✅ 활성화 | 네이버 금융 사용 |
| **텔레그램 알림** | ✅ 활성화 | requests 사용 |

### 메모리 사용량

```
최소 설정: ~100MB
최대 설정: ~200MB (DS220J 2GB RAM의 10%)
```

---

## 🔄 Oracle Cloud 이전 계획

### Phase 1: 현재 (DS220J)
```
✅ 한국 시장 레짐 감지
✅ 보유 종목 매도 신호
✅ 텔레그램 알림
✅ 09:00 자동 실행
```

### Phase 2: Oracle Cloud 이전
```
🚀 WebUI 배포 (React + FastAPI)
🚀 미국 지표 활성화
🚀 실시간 파라미터 조정
🚀 백테스트 히스토리
🚀 PC/모바일 접근
```

### Oracle Cloud 무료 티어
- **VM.Standard.E2.1.Micro**: 1 OCPU, 1GB RAM
- **VM.Standard.A1.Flex**: 4 OCPU, 24GB RAM (ARM)
- **스토리지**: 200GB
- **트래픽**: 10TB/월

**비용**: 무료 (Always Free) ✅

---

## 📝 현재 동작 확인

### 1. 로그 확인

```bash
tail -f /volume2/homes/Hyungsoo/krx/logs/regime_check.log
```

### 2. 텔레그램 알림 확인

**일일 알림 (09:00)**:
```
📊 일일 레짐 리포트

📍 한국 시장:
📈 레짐: 상승장
🎯 신뢰도: 87.5%
💰 KOSPI: 2,650.5 (+1.2%)

📌 보유 종목 매도 신호: 0건
```

### 3. 수동 실행 테스트

```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
python3 scripts/nas/daily_regime_check.py
```

---

## 🔍 문제 해결

### 1. KOSPI 데이터 없음

**증상**:
```
ERROR: KOSPI 데이터 없음 - 과거 데이터 필요
```

**해결**:
```bash
# 캐시 삭제
rm -rf data/cache/ohlcv/*

# 재실행
python3 scripts/nas/daily_regime_check.py
```

### 2. 텔레그램 알림 안 옴

**체크리스트**:
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

### 3. 미국 지표 에러

**증상**:
```
ERROR: 데이터 없음: ^IXIC
ERROR: 데이터 없음: ^GSPC
```

**해결**:
```bash
# 미국 지표 비활성화 확인
grep "enabled:" config/us_market_indicators.yaml

# 모두 false여야 함
```

---

## ✅ 최종 체크리스트

- [ ] Git Pull 완료
- [ ] 미국 지표 비활성화 완료
- [ ] 수동 실행 성공
- [ ] 텔레그램 알림 수신
- [ ] Cron 설정 확인
- [ ] 로그 확인

---

## 🎯 다음 단계

### 즉시 (DS220J)
- ✅ 한국 시장 레짐 감지 사용
- ✅ 매일 09:00 자동 알림
- ✅ 보유 종목 매도 신호

### 향후 (Oracle Cloud)
- 🚀 WebUI 배포
- 🚀 미국 지표 활성화
- 🚀 실시간 모니터링
- 🚀 파라미터 조정 UI

---

## 📚 관련 문서

- `docs/NAS_REGIME_CRON_SETUP.md` - Cron 설정 가이드
- `docs/NAS_YFINANCE_FIX.md` - yfinance 문제 해결
- `config/us_market_indicators.yaml` - 미국 지표 설정

---

## 🎉 완료!

**DS220J에서 핵심 기능만 안정적으로 실행됩니다!**

- ✅ 한국 시장 레짐 감지
- ✅ 보유 종목 매도 신호
- ✅ 텔레그램 알림
- ✅ 저사양 최적화
- ✅ 에러 없는 안정적 동작

**Oracle Cloud 이전은 WebUI가 필요할 때 진행하면 됩니다!**
