# 하이브리드 실행 가이드

## 📋 개요

실시간 모니터링과 백테스트 개선을 병행하는 하이브리드 방식 가이드

**기간**: 2주 (2025-11-09 ~ 2025-11-22)
**목표**: 안정적 실전 투입 준비

---

## 🚀 Week 1: 관찰 모드 + 백테스트 개선

### Day 1-2 (토/일): 도구 설정

#### 1. 실시간 신호 기록 시스템
```bash
# PC에서 테스트
cd "E:\AI Study\krx_alertor_modular"
python scripts/monitoring/signal_logger.py
```

**기능**:
- 텔레그램 신호 자동 기록
- JSON 형식으로 저장
- 일일 요약 생성

#### 2. 파라미터 최적화
```bash
# PC에서 Grid Search 실행
python scripts/optimization/grid_search.py
```

**최적화 대상**:
- MAPS 임계값: 3, 5, 7, 10
- 레짐 MA: (20,50), (50,200), (100,300)
- 포지션 비율: 상승 100~130%, 중립 60~90%, 하락 30~60%

**예상 시간**: 2~3시간 (조합 50개 기준)

#### 3. 주간 비교 리포트
```bash
# 주말마다 실행
python scripts/monitoring/weekly_comparison.py
```

**출력**:
- 일별 신호 요약
- 주간 통계
- 레짐 분포

---

### Day 3-7 (월~금): 실시간 관찰

#### 매일 루틴 (10분)

**09:00 - 장 시작 알림 확인**
```
텔레그램 메시지:
- 포트폴리오 현황
- 오늘의 레짐
```

**16:00 - 일일 리포트 확인**
```
텔레그램 메시지:
- 매수 신호 (종목명, MAPS 점수)
- 매도 신호 (사유)
- 레짐 분석
```

**기록 방법**:
1. 텔레그램 메시지 캡처
2. 엑셀/노트에 기록
   - 날짜
   - 매수 종목 코드
   - MAPS 점수
   - 레짐 상태

**예시 기록**:
```
날짜: 2025-11-11
레짐: 상승장 (신뢰도 95%)
매수 신호:
  - 069500 (KODEX 200): MAPS 85.23
  - 143850 (TIGER 미국S&P500): MAPS 82.15
매도 신호: 없음
```

---

## 🔬 Week 2: 분석 + 소액 실전

### Day 8-9 (토/일): 분석 및 조정

#### 1. 주간 비교 분석
```bash
python scripts/monitoring/weekly_comparison.py
```

**확인 사항**:
- 실시간 신호 vs 백테스트 예상 비교
- 신호 정확도
- 레짐 감지 정확도

#### 2. 파라미터 미세 조정
```bash
# 최적 파라미터 확인
cat data/optimization/best_params.json

# 백테스트 재실행
python scripts/phase2/run_backtest_hybrid.py --config data/optimization/best_params.json
```

#### 3. 리스크 관리 점검
- 손절 로직 확인
- 포지션 사이징 검토
- 변동성 대응 전략

---

### Day 10-14 (월~금): 소액 실전 테스트

#### 실전 투입 기준
- ✅ 1주일 이상 신호 관찰 완료
- ✅ 백테스트 성능 검증 (Sharpe > 1.5)
- ✅ 신호 정확도 확인
- ✅ 리스크 관리 준비

#### 소액 실전 규칙
1. **초기 자금**: 전체 자금의 10~20%
2. **신호 선택**: 신뢰도 높은 것만
   - MAPS 점수 > 10
   - 레짐 신뢰도 > 90%
3. **손절 엄수**: -5% 도달 시 무조건 매도
4. **일일 기록**: 매매 내역, 수익률, 소감

#### 매일 체크리스트
- [ ] 09:00 장 시작 알림 확인
- [ ] 16:00 일일 리포트 확인
- [ ] 신호 선택 (신뢰도 높은 것만)
- [ ] 매매 실행 (있는 경우)
- [ ] 결과 기록 (엑셀/노트)

---

## 📊 성과 측정

### 주간 지표
- **신호 정확도**: 실제 수익 종목 / 전체 신호
- **레짐 정확도**: 레짐 예측 vs 실제 시장
- **수익률**: 주간 누적 수익률
- **MDD**: 최대 낙폭

### 월간 목표
- **CAGR**: 20% 이상
- **Sharpe**: 1.3 이상
- **MDD**: -15% 이내
- **신호 정확도**: 60% 이상

---

## 🛠 도구 사용법

### 1. 신호 기록
```python
from scripts.monitoring.signal_logger import SignalLogger

logger = SignalLogger()

# 매수 신호 기록
buy_signals = [
    {'code': '069500', 'name': 'KODEX 200', 'maps_score': 85.23}
]
regime_info = {'state': 'bull', 'confidence': 95.0}

logger.log_signal('buy', buy_signals, regime_info)

# 일일 요약
summary = logger.get_daily_summary()
print(summary)
```

### 2. 파라미터 최적화
```python
from scripts.optimization.grid_search import ParameterOptimizer

optimizer = ParameterOptimizer()

# 최적화 실행 (50개 조합)
results_df = optimizer.optimize(max_combinations=50)

# 최적 파라미터 저장
optimizer.save_best_params(results_df)
```

### 3. 주간 리포트
```python
from scripts.monitoring.weekly_comparison import WeeklyComparison

comparison = WeeklyComparison()

# 리포트 생성
report_file = comparison.generate_report()

# 요약 출력
comparison.print_summary()
```

---

## 📝 기록 템플릿

### 일일 기록
```
날짜: YYYY-MM-DD
레짐: [상승/중립/하락] (신뢰도: XX%)

매수 신호:
  1. 종목명(코드): MAPS XX.XX
  2. ...

매도 신호:
  1. 종목명(코드): 사유

실제 매매:
  - 매수: [종목, 수량, 가격]
  - 매도: [종목, 수량, 가격, 수익률]

소감:
  - ...
```

### 주간 리포트
```
기간: YYYY-MM-DD ~ YYYY-MM-DD

신호 통계:
  - 총 매수 신호: XX개
  - 총 매도 신호: XX개
  - 일평균 신호: XX개

레짐 분포:
  - 상승장: X일
  - 중립장: X일
  - 하락장: X일

실전 성과:
  - 매매 횟수: XX회
  - 수익률: XX%
  - MDD: -XX%

개선 사항:
  - ...
```

---

## ⚠️ 주의사항

### 실시간 모니터링
- 텔레그램 알림 놓치지 않기
- 매일 기록 습관화
- 신호 선택 기준 명확히

### 백테스트 개선
- 과최적화 주의 (Overfitting)
- 실시간 데이터와 비교
- 슬리피지/수수료 반영

### 실전 투입
- 소액으로 시작
- 손절 엄수
- 감정 배제
- 지속적 개선

---

## 📞 문제 해결

### 신호가 안 오는 경우
```bash
# NAS Cron 확인
ssh Hyungsoo@192.168.x.x
crontab -l

# 로그 확인
tail -f logs/automation/daily_alert_YYYYMMDD.log
```

### 백테스트 오류
```bash
# 데이터 업데이트
python scripts/data/update_ohlcv.py

# 백테스트 재실행
python scripts/phase2/run_backtest_hybrid.py
```

### 성능 저하
- 파라미터 재최적화
- 레짐 감지 민감도 조정
- 리스크 관리 강화

---

## 📚 참고 문서

- `docs/WEEK3_HYBRID_STRATEGY.md`: 백테스트 전략 상세
- `docs/guides/nas/telegram_push_schedule.md`: 알림 스케줄
- `docs/PHASE2_COMPLETE_SUMMARY.md`: Phase 2 요약

---

**작성일**: 2025-11-09
**버전**: 1.0
**작성자**: Cascade AI
