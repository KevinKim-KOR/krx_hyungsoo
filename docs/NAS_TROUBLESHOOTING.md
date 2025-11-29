# NAS 문제 해결 가이드

**작성일**: 2025-11-29  
**환경**: Synology DS220j, Python 3.8

---

## 🔧 발생한 문제 및 해결

### 문제 1: `dotenv` 모듈 없음 ❌

**증상**:
```bash
$ python3.8 scripts/nas/daily_report_alert.py
Traceback (most recent call last):
  File "scripts/nas/daily_report_alert.py", line 11, in <module>
    from dotenv import load_dotenv
ModuleNotFoundError: No module named 'dotenv'
```

**원인**:
- `daily_report_alert.py`에서 `dotenv`를 import
- NAS에는 `python-dotenv` 패키지가 설치되지 않음
- NAS에서는 `config/env.nas.sh`를 사용하므로 `dotenv` 불필요

**해결**:
```python
# Before (❌)
from dotenv import load_dotenv
load_dotenv()

# After (✅)
# dotenv 제거 (env.nas.sh 사용)
```

**적용**:
- `scripts/nas/daily_report_alert.py` 수정 완료
- Commit: `f1735fa1`

---

### 문제 2: `intraday_alert.py` 실행 멈춤 ⏸️

**증상**:
```bash
$ python3.8 scripts/nas/intraday_alert.py
============================================================
장중 알림 체크 시작
============================================================
보유 종목: 28개
# 여기서 멈춤... (응답 없음)
```

**원인**:
- `check_intraday_movements()` 함수가 모든 ETF를 하나씩 조회
- ETF 유니버스가 수백 개 → 네이버 API 호출 수백 번
- 진행 상황 표시 없어서 멈춘 것처럼 보임

**실제 상황**:
- 프로그램은 정상 실행 중
- 단지 진행 상황이 표시되지 않아서 멈춘 것처럼 보임
- 전체 실행 시간: 약 5-10분 (ETF 개수에 따라)

**해결**:
```python
# Before (❌)
for etf in etf_universe:
    # 진행 상황 표시 없음
    df = naver.get_market_ohlcv_by_date(fromdate, todate, code)

# After (✅)
total = len(etf_universe)
print(f"\n📊 ETF 데이터 수집 시작 (총 {total}개)...")

for idx, etf in enumerate(etf_universe, 1):
    # 매 10개마다 진행 상황 표시
    if idx % 10 == 0 or idx == total:
        print(f"  진행: {idx}/{total} ({idx/total*100:.1f}%) - 체크: {checked}개")
    
    df = naver.get_market_ohlcv_by_date(fromdate, todate, code)
```

**적용**:
- `scripts/nas/intraday_alert.py` 수정 완료
- Commit: `f1735fa1`

**예상 출력**:
```bash
============================================================
장중 알림 체크 시작
============================================================
보유 종목: 28개
전체 ETF: 500개
필터링 후 ETF: 350개 (제외: 150개)
ETF 유니버스: 350개

📊 ETF 데이터 수집 시작 (총 350개)...
  진행: 10/350 (2.9%) - 체크: 8개
  진행: 20/350 (5.7%) - 체크: 16개
  진행: 30/350 (8.6%) - 체크: 24개
  ...
  진행: 350/350 (100.0%) - 체크: 280개
알림 대상: 5개
```

---

## 📊 성능 개선 방안 (향후)

### 현재 문제
- **실행 시간**: 5-10분 (ETF 350개 기준)
- **병목**: 네이버 API 호출 (1개씩 순차 처리)

### 개선 방안

#### 1. 배치 처리 (추천) ⭐⭐⭐⭐⭐
```python
# pykrx의 배치 API 사용
df_all = stock.get_market_ohlcv_by_date(fromdate, todate, market="ETF")
# 한 번에 모든 ETF 데이터 가져오기
```

**효과**: 5-10분 → 10-30초 (90% 단축)

#### 2. 병렬 처리 ⭐⭐⭐⭐
```python
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=5) as executor:
    results = executor.map(fetch_etf_data, etf_universe)
```

**효과**: 5-10분 → 1-2분 (80% 단축)

#### 3. 캐싱 ⭐⭐⭐
```python
# 당일 데이터 캐싱 (1시간 유효)
cache_file = f"data/cache/etf_intraday_{today}.parquet"
if os.path.exists(cache_file):
    df = pd.read_parquet(cache_file)
```

**효과**: 두 번째 실행부터 즉시 완료

---

## 🚀 즉시 적용 가능한 최적화

### 1. ETF 필터링 강화
```python
# 거래대금 기준 상향 (50억 → 100억)
MIN_TRADE_VALUE = 100e8

# 더 적은 ETF만 체크 → 실행 시간 단축
```

### 2. 체크 주기 조정
```python
# Crontab에서 실행 횟수 줄이기
# Before: 10:00, 11:00, 13:00, 14:00 (4회)
# After: 10:30, 13:30 (2회)
```

---

## 📝 NAS 배포 체크리스트

### Git Pull 후 확인 사항
```bash
# 1. Git Pull
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
git pull origin main

# 2. 컴파일 테스트
python3.8 -m py_compile scripts/nas/daily_report_alert.py
python3.8 -m py_compile scripts/nas/intraday_alert.py

# 3. 수동 실행 테스트
source config/env.nas.sh

# daily_report_alert (빠름, 1-2초)
python3.8 scripts/nas/daily_report_alert.py

# intraday_alert (느림, 5-10분 예상)
# 진행 상황 확인하면서 실행
python3.8 scripts/nas/intraday_alert.py
```

### 예상 실행 시간

| 스크립트 | 실행 시간 | 비고 |
|---------|----------|------|
| `market_open_alert.py` | 1-2초 | 포트폴리오만 로드 |
| `daily_report_alert.py` | 1-2초 | 포트폴리오만 로드 |
| `weekly_report_alert.py` | 2-3초 | 포트폴리오 + 분석 |
| `intraday_alert.py` | **5-10분** | ETF 전체 조회 |

---

## ⚠️ 주의사항

### 1. `intraday_alert.py` 실행 시
- ✅ **정상**: 진행 상황이 표시되면 정상 실행 중
- ❌ **비정상**: 5분 이상 진행 상황 표시 없으면 문제

**확인 방법**:
```bash
# 다른 터미널에서 프로세스 확인
ps aux | grep intraday_alert

# 로그 확인
tail -f logs/cron_intraday.log
```

### 2. Cron 실행 시
- Cron에서는 출력이 로그 파일로 저장됨
- 진행 상황은 로그 파일에서 확인

```bash
# 실시간 로그 확인
tail -f logs/cron_intraday.log
```

### 3. 네트워크 문제
- 네이버 API 호출 실패 시 자동으로 건너뜀
- 일부 ETF 데이터 없어도 정상 동작

---

## 🎯 권장 사항

### 즉시 적용
1. ✅ **dotenv 제거** (완료)
2. ✅ **진행 상황 표시** (완료)

### 향후 개선
1. ⏳ **배치 처리** (실행 시간 90% 단축)
2. ⏳ **캐싱** (두 번째 실행부터 즉시)
3. ⏳ **ETF 필터링 강화** (체크 대상 감소)

---

## 📞 문제 발생 시

### 1. 로그 확인
```bash
# 최근 로그
tail -n 100 logs/cron_intraday.log

# 에러만 필터링
grep -i "error\|fail\|❌" logs/cron_intraday.log
```

### 2. 수동 실행
```bash
source config/env.nas.sh
python3.8 scripts/nas/intraday_alert.py
```

### 3. 환경 변수 확인
```bash
echo $TELEGRAM_BOT_TOKEN
echo $TELEGRAM_CHAT_ID
```

---

**NAS 문제 해결 가이드 완료!** 🎉

**핵심 요약**:
- ✅ `dotenv` 제거 → ModuleNotFoundError 해결
- ✅ 진행 상황 표시 → 실행 중임을 확인 가능
- ⏳ 향후 배치 처리로 실행 시간 90% 단축 가능
