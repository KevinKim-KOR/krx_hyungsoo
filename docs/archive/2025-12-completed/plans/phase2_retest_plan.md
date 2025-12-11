# Phase 2 재테스트 계획 (업데이트)

**작성일**: 2025-11-07  
**업데이트**: 2025-11-07 (하이브리드 전략 추가)  
**목표**: 하이브리드 전략 구현 + 전체 백테스트 파이프라인 검증  
**기간**: 약 4~5주

---

## 📋 개요

Phase 2 재테스트는 다음을 목표로 합니다:
1. **하이브리드 전략 구현**: Jason 공격 로직 + 방어 시스템 (Week 1~4)
2. **더 적합한 종목 선택**: 81개 ETF (기존 44 + 최신 테마 37)
3. **전체 테스트**: Optuna 최적화, 워크포워드, 로버스트니스
4. **실전 준비**: 실제 거래 가능한 전략 검증

## 🔄 계획 변경사항

### 기존 계획
```
1단계: 환경 준비 ✅
2단계: 데이터 준비 ✅
3단계: 기본 백테스트
4단계: Optuna 최적화
5단계: 워크포워드
6단계: 로버스트니스
7단계: 결과 정리
```

### 새로운 계획 (Option A)
```
1단계: 환경 준비 ✅
2단계: 데이터 준비 ✅
2-1단계: 최신 테마 ETF 추가 (81개) ✅
3단계: 기본 백테스트 (임시) ✅

🆕 하이브리드 전략 구현 (3~4주)
├─ Week 1: Jason 백테스트 엔진 통합 🔄
├─ Week 2: 방어 시스템 구현
├─ Week 3: 하이브리드 전략 구현
└─ Week 4: 자동화 시스템 구현

3-1단계: 하이브리드 백테스트 (실제)
4단계: Optuna 최적화 (하이브리드)
5단계: 워크포워드 분석
6단계: 로버스트니스 테스트
7단계: 결과 정리
```

**상세 계획**: `docs/HYBRID_STRATEGY_PLAN.md` 참고

---

## 📋 Phase 2 재테스트가 필요한 이유

### 이전 Phase 2의 한계
- ✅ 기능 구현 완료
- ✅ 코드 검증 완료
- ⚠️ **데이터 부족** (6개월, 10개 종목)
- ⚠️ **최적화 부족** (3 trials만 실행)
- ⚠️ **검증 부족** (워크포워드 분석 미실행)

### 재테스트 목표
- 📊 **충분한 데이터** (1~3년)
- 📈 **다양한 종목** (50~100개 ETF)
- 🔬 **완전한 최적화** (50~100 trials)
- ✅ **워크포워드 분석** (과적합 방지)
- 🛡️ **로버스트니스 테스트** (안정성 검증)

---

## 🔍 친구 코드 분석 (momentum-etf)

### 참고할 부분

#### 1. 데이터 수집
```python
# jasonisdoing/momentum-etf 참고
# - 긴 히스토리 ETF 선별
# - 최소 3년 이상 데이터
# - 거래량 필터링
```

#### 2. 백테스트 엔진
```python
# - 슬리피지 고려
# - 거래 비용 반영
# - 리밸런싱 로직
```

#### 3. 성과 지표
```python
# - CAGR (연평균 수익률)
# - MDD (최대 낙폭)
# - Sharpe Ratio
# - Calmar Ratio
# - Win Rate
```

#### 4. 시각화
```python
# - 누적 수익률 차트
# - 드로다운 차트
# - 월별 수익률 히트맵
```

---

## 📝 재테스트 체크리스트

### 1단계: 환경 준비 ✅
- [x] PC 환경 확인 (Python 3.13)
- [x] 의존성 설치 확인
- [x] 데이터 캐시 확인

### 2단계: 데이터 준비 (예정)
- [ ] **긴 히스토리 ETF 선별**
  - 2022년 이전 상장 ETF
  - 일평균 거래량 > 10억원
  - 레버리지/인버스 제외
- [ ] **데이터 수집**
  - 기간: 2022-01-01 ~ 2025-11-07 (약 3년)
  - 종목: 50~100개 ETF
  - 데이터 품질 확인
- [ ] **데이터 검증**
  - 결측치 확인
  - 이상치 제거
  - 분할 조정 확인

### 3단계: 백테스트 실행 (예정)
- [ ] **기본 백테스트**
  - 전체 기간 (2022~2025)
  - 기본 파라미터 사용
  - 성과 지표 확인
- [ ] **파라미터 민감도 분석**
  - MA 기간 변화
  - RSI 임계값 변화
  - 포지션 수 변화

### 4단계: Optuna 최적화 (예정)
- [ ] **최적화 설정**
  - Trials: 50~100
  - 목적함수: Sharpe Ratio 또는 Calmar Ratio
  - 탐색 공간 정의
- [ ] **최적화 실행**
  - 병렬 실행 (선택)
  - 진행 상황 모니터링
  - 중간 결과 저장
- [ ] **결과 분석**
  - 최적 파라미터 확인
  - 파라미터 중요도 분석
  - 수렴 여부 확인

### 5단계: 워크포워드 분석 (예정)
- [ ] **In-Sample / Out-of-Sample 분할**
  - In-Sample: 2022-01 ~ 2024-06 (2.5년)
  - Out-of-Sample: 2024-07 ~ 2025-11 (1.5년)
- [ ] **롤링 윈도우 분석**
  - 윈도우 크기: 12개월
  - 스텝 크기: 3개월
  - 각 윈도우별 최적화 및 검증
- [ ] **과적합 검증**
  - In-Sample vs Out-of-Sample 성과 비교
  - 성과 차이 < 20% 목표

### 6단계: 로버스트니스 테스트 (예정)
- [ ] **몬테카를로 시뮬레이션**
  - 1000회 시뮬레이션
  - 신뢰구간 계산
- [ ] **스트레스 테스트**
  - 2020년 코로나 위기
  - 2022년 금리 인상
  - 극단적 시장 상황
- [ ] **민감도 분석**
  - 거래 비용 변화
  - 슬리피지 변화
  - 리밸런싱 빈도 변화

### 7단계: 결과 정리 및 문서화 (예정)
- [ ] **성과 리포트 작성**
  - 주요 지표 요약
  - 차트 및 그래프
  - 분석 및 인사이트
- [ ] **최적 파라미터 저장**
  - `best_params.json` 업데이트
  - 버전 관리
- [ ] **문서 업데이트**
  - README 업데이트
  - Phase 2 완료 보고서

---

## 🛠️ 필요한 스크립트 및 도구

### 기존 파일 (활용)
- ✅ `pc/backtest.py` - 백테스트 엔진
- ✅ `extensions/optuna/objective.py` - Optuna 목적함수
- ✅ `extensions/optuna/walk_forward.py` - 워크포워드 분석
- ✅ `extensions/optuna/robustness.py` - 로버스트니스 테스트
- ✅ `quick_phase2_test.py` - 빠른 검증 스크립트

### 신규 파일 (생성 필요)
- [ ] `scripts/phase2/prepare_data.py` - 데이터 준비
- [ ] `scripts/phase2/run_backtest.py` - 백테스트 실행
- [ ] `scripts/phase2/run_optimization.py` - 최적화 실행
- [ ] `scripts/phase2/run_walkforward.py` - 워크포워드 분석
- [ ] `scripts/phase2/run_robustness.py` - 로버스트니스 테스트
- [ ] `scripts/phase2/generate_report.py` - 리포트 생성

### 친구 코드 참고 (선택)
- [ ] 데이터 수집 로직
- [ ] 백테스트 엔진 개선
- [ ] 시각화 개선
- [ ] 성과 지표 추가

---

## 📊 예상 결과물

### 1. 데이터
- `data/cache/ohlcv/*.parquet` - 가격 데이터 (50~100개 종목, 3년)
- `data/universe/etf_universe.csv` - 선별된 ETF 목록

### 2. 백테스트 결과
- `backtests/phase2_retest/backtest_YYYYMMDD.csv` - 거래 내역
- `backtests/phase2_retest/performance_YYYYMMDD.csv` - 성과 지표

### 3. 최적화 결과
- `backtests/phase2_retest/optuna_study.db` - Optuna 스터디 DB
- `backtests/phase2_retest/best_params.json` - 최적 파라미터
- `backtests/phase2_retest/optimization_history.png` - 최적화 히스토리

### 4. 워크포워드 결과
- `backtests/phase2_retest/walkforward_results.csv` - 각 윈도우별 성과
- `backtests/phase2_retest/walkforward_chart.png` - 워크포워드 차트

### 5. 로버스트니스 결과
- `backtests/phase2_retest/monte_carlo_results.csv` - 몬테카를로 결과
- `backtests/phase2_retest/stress_test_results.csv` - 스트레스 테스트

### 6. 리포트
- `docs/PHASE2_RETEST_REPORT.md` - 최종 리포트
- `docs/PHASE2_RETEST_CHARTS.md` - 차트 모음

---

## ⏱️ 예상 소요 시간

| 단계 | 작업 | 예상 시간 |
|------|------|-----------|
| 1 | 환경 준비 | 30분 |
| 2 | 데이터 준비 | 2시간 |
| 3 | 기본 백테스트 | 1시간 |
| 4 | Optuna 최적화 | 3~6시간 |
| 5 | 워크포워드 분석 | 2~4시간 |
| 6 | 로버스트니스 테스트 | 2~4시간 |
| 7 | 결과 정리 및 문서화 | 2시간 |
| **합계** | | **12~19시간** |

**권장**: 2~3일에 걸쳐 진행

---

## 🚀 실행 순서

### Day 1: 데이터 준비 및 기본 백테스트
```bash
# 1. 데이터 준비
python scripts/phase2/prepare_data.py

# 2. 기본 백테스트
python scripts/phase2/run_backtest.py --start 2022-01-01 --end 2025-11-07

# 3. 결과 확인
cat backtests/phase2_retest/performance_*.csv
```

### Day 2: 최적화 및 워크포워드
```bash
# 1. Optuna 최적화 (시간 소요)
python scripts/phase2/run_optimization.py --trials 100

# 2. 워크포워드 분석
python scripts/phase2/run_walkforward.py --window 12 --step 3

# 3. 중간 결과 확인
```

### Day 3: 로버스트니스 및 리포트
```bash
# 1. 로버스트니스 테스트
python scripts/phase2/run_robustness.py --simulations 1000

# 2. 리포트 생성
python scripts/phase2/generate_report.py

# 3. 문서 업데이트
```

---

## 📚 참고 자료

### 내부 문서
- `README_PHASE2.md` - Phase 2 원본 문서
- `docs/PHASE2_COMPLETION_REPORT.md` - Phase 2 완료 보고서

### 친구 코드
- [jasonisdoing/momentum-etf](https://github.com/jasonisdoing/momentum-etf)
  - `backtest/engine.py` - 백테스트 엔진
  - `strategy/momentum.py` - 모멘텀 전략
  - `utils/metrics.py` - 성과 지표

### 외부 자료
- [Optuna Documentation](https://optuna.readthedocs.io/)
- [Backtrader Documentation](https://www.backtrader.com/docu/)
- [QuantStats Documentation](https://github.com/ranaroussi/quantstats)

---

## 🎯 성공 기준

### 필수 조건
- [ ] 50개 이상 ETF로 백테스트 완료
- [ ] 50 trials 이상 최적화 완료
- [ ] 워크포워드 분석 완료 (과적합 < 20%)
- [ ] 주요 지표 계산 완료 (CAGR, MDD, Sharpe)

### 목표 성과
- **CAGR**: > 10%
- **MDD**: < -20%
- **Sharpe Ratio**: > 1.0
- **Calmar Ratio**: > 0.5
- **Win Rate**: > 55%

### 추가 목표
- [ ] 몬테카를로 시뮬레이션 완료
- [ ] 스트레스 테스트 통과
- [ ] 완전한 문서화

---

## 🔄 다음 단계 (Phase 2 완료 후)

1. **Phase 4-2**: 전략 고도화
   - 다중 전략 조합
   - 레짐별 파라미터 조정
   - 동적 포지션 사이징

2. **Phase 4-3**: 리스크 관리 강화
   - 손절매 로직
   - 포트폴리오 리밸런싱
   - 상관계수 기반 분산

3. **Phase 5**: Oracle Cloud 배포

4. **Phase 6**: 고급 웹 대시보드

---

## 📞 문의 및 지원

문제 발생 시:
1. 로그 파일 확인
2. 데이터 품질 확인
3. 파라미터 설정 재확인
4. GitHub Issues 등록

---

**작성일**: 2025-11-07  
**버전**: 1.0  
**상태**: 준비 중
