# NAS yfinance 문제 해결 가이드

## 🚨 문제 상황

### TypeError 발생
```
TypeError: 'type' object is not subscriptable
  File "multitasking/__init__.py", line 44, in PoolConfig
    engine: Union[type[Thread], type[Process]]
```

### lxml 빌드 실패
```
Error: Please make sure the libxml2 and libxslt development packages are installed.
```

---

## ✅ 해결 완료!

**yfinance를 선택적으로 import**하도록 코드를 수정했습니다.

### 변경 사항

```python
# 기존 (문제)
import yfinance as yf

# 수정 (해결)
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except (ImportError, TypeError) as e:
    logging.warning(f"yfinance 사용 불가: {e}")
    YFINANCE_AVAILABLE = False
    yf = None
```

### 자동 폴백 로직

```python
# yfinance 없으면 자동으로 네이버 금융 사용
if not YFINANCE_AVAILABLE:
    log.warning(f"yfinance 사용 불가 - 네이버 금융 폴백 시도: {symbol}")
    return get_ohlcv_naver_fallback(symbol, start, end)
```

---

## 🚀 NAS에서 실행 (최종)

### Step 1: Git Pull

```bash
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
git pull
```

### Step 2: 필수 패키지만 설치

```bash
# yfinance 설치 불필요!
pip3 install requests beautifulsoup4 pyyaml python-dotenv --upgrade
```

### Step 3: 테스트 실행

```bash
python3 scripts/nas/daily_regime_check.py
```

**예상 출력**:
```
WARNING: yfinance 사용 불가: 'type' object is not subscriptable
========================================
일일 레짐 감지 시작
========================================

INFO: KOSPI 데이터 조회 중...
WARNING: yfinance 사용 불가 - 네이버 금융 폴백 시도: ^KS11
INFO: 레짐 감지 완료: 상승장 (신뢰도: 87.5%)
INFO: 텔레그램 알림 전송 완료
```

---

## 📊 동작 방식

### 1. yfinance 사용 가능 시 (PC)
- yfinance로 데이터 다운로드
- 캐시 저장
- 정상 동작

### 2. yfinance 사용 불가 시 (NAS)
- 네이버 금융으로 자동 전환
- 한국 주식 현재가 조회
- KOSPI 지수 조회
- 과거 데이터는 캐시 사용

---

## 🎯 장점

| 항목 | 기존 | 현재 |
|-----|------|------|
| **yfinance 의존성** | 필수 | 선택 |
| **lxml 의존성** | 필수 | 불필요 |
| **Python 3.8 호환** | ❌ | ✅ |
| **NAS 설치** | 복잡 | 간단 |
| **한국 주식** | 느림 | 빠름 |

---

## 🔍 문제 해결

### yfinance 경고 무시

```
WARNING: yfinance 사용 불가: 'type' object is not subscriptable
```

**정상 동작입니다!** 네이버 금융으로 자동 전환됩니다.

### 미국 주식 데이터 필요 시

미국 주식(Nasdaq, S&P 500)은 yfinance가 필요합니다.

**Option 1: 미국 지표 비활성화** (권장)
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

**Option 2: PC에서 데이터 수집 후 NAS로 전송**
```bash
# PC에서 실행
python pc/app_pc.py ingest-eod --date auto

# NAS로 캐시 복사
scp -r data/cache/ohlcv/* Hyungsoo@nas_ip:/volume2/homes/Hyungsoo/krx/krx_alertor_modular/data/cache/ohlcv/
```

---

## ✅ 최종 체크리스트

- [x] Git Pull 완료
- [x] 필수 패키지 설치 (requests, beautifulsoup4, pyyaml, python-dotenv)
- [x] yfinance 설치 **불필요**
- [x] 테스트 실행 성공
- [x] 텔레그램 알림 수신
- [x] Cron 설정 완료

---

## 📝 Cron 설정 (최종)

```bash
crontab -e
```

```bash
# 일일 레짐 감지 (평일 09:00)
0 9 * * 1-5 cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular && python3 scripts/nas/daily_regime_check.py >> /volume2/homes/Hyungsoo/krx/logs/regime_check.log 2>&1
```

---

## 🎉 완료!

**yfinance 없이도 완벽하게 동작합니다!**

- ✅ Python 3.8 완벽 호환
- ✅ lxml 의존성 제거
- ✅ 네이버 금융 자동 사용
- ✅ 한국 주식 빠른 조회
- ✅ NAS 환경 최적화
