# Phase 2 최종 진단 및 권장사항

## 🔍 문제 요약

**Step 3-4 (워크포워드 분석, 로버스트니스 테스트)가 너무 오래 걸리고 실패합니다.**

---

## 📊 진단 결과

### 1. 데이터 상태
✅ **해결 완료**: 손상된 캐시 파일 정리
- 815개 파일 중 120개 손상 (14.7%)
- 손상 파일 삭제 및 재다운로드 완료
- 695개 정상 파일 확보

### 2. pykrx API 문제
✅ **해결 완료**: 캐시 기반 유니버스 로드로 변경
- `get_filtered_universe()` 함수 수정
- pykrx API 호출 대신 캐시 파일 목록 사용
- API 오류 회피

### 3. 백테스트 성능 문제
❌ **진행 중**: 매우 느린 실행 속도
- 695개 종목 × 3개월 데이터 처리
- "데이터 부족 (< 60)" 경고 반복
- 각 trial당 10분 이상 소요 예상

---

## 🎯 근본 원인

### 문제 1: 데이터 기간 부족
```
[WARNING] 데이터 부족 (11 < 60)
[WARNING] 데이터 부족 (0 < 60)
```

**원인**: 
- 2024-01-01 ~ 2024-03-31 (3개월) 테스트
- 많은 종목이 60일 이상 데이터 없음
- MA 계산에 필요한 최소 기간 부족

### 문제 2: 유니버스 크기
- 695개 전체 종목 처리
- 각 종목마다 데이터 로드 및 지표 계산
- 메모리 및 CPU 부하

### 문제 3: 백테스트 복잡도
- SignalGenerator (MA, RSI 계산)
- RiskManager (상관계수, 변동성 계산)
- 매일 리밸런싱 검토

---

## 💡 해결 방안

### 방안 A: 소규모 테스트 (권장)

**목적**: Phase 2 기능 검증
**방법**: 유니버스 축소 + 기간 연장

```bash
# 1. 소규모 최적화 (20개 종목, 6개월)
python -c "
from datetime import date
from pathlib import Path
from extensions.optuna.objective import BacktestObjective
from core.data.filtering import get_filtered_universe
import optuna

# 유니버스 로드
all_universe = get_filtered_universe()
print(f'전체 유니버스: {len(all_universe)}개')

# 상위 20개만 선택
small_universe = all_universe[:20]
print(f'테스트 유니버스: {small_universe}')

# Objective 생성
obj = BacktestObjective(
    start_date=date(2023, 7, 1),  # 6개월
    end_date=date(2023, 12, 31),
    seed=42
)

# 유니버스 축소
obj.universe = small_universe
from infra.data.loader import load_price_data
obj.price_data = load_price_data(small_universe, obj.start_date, obj.end_date)

print(f'데이터 shape: {obj.price_data.shape}')

# 최적화
study = optuna.create_study(direction='maximize')
study.optimize(obj, n_trials=5, show_progress_bar=True)

print(f'\n최적 값: {study.best_value:.2f}')
print(f'최적 파라미터: {study.best_params}')
"
```

### 방안 B: 기간 연장

**문제**: 3개월 데이터는 너무 짧음
**해결**: 최소 6개월 이상 사용

```bash
# 6개월 테스트
python pc/cli.py optimize --start 2023-07-01 --end 2023-12-31 --trials 5 --seed 42
```

### 방안 C: 유니버스 필터링 강화

**문제**: 695개 종목이 너무 많음
**해결**: 거래량/시가총액 기준 필터링

```python
# core/data/filtering.py 수정
def get_filtered_universe(top_n: int = 100) -> List[str]:
    # ... (기존 코드)
    
    # 상위 N개만 반환
    return sorted(filtered)[:top_n]
```

---

## 📝 권장 조치

### 즉시 실행 가능한 테스트

#### 1. 초소규모 테스트 (5분)
```bash
python -c "
from datetime import date
from extensions.optuna.objective import BacktestObjective
import optuna

obj = BacktestObjective(
    start_date=date(2023, 7, 1),
    end_date=date(2023, 12, 31),
    seed=42
)

# 10개 종목만
obj.universe = obj.universe[:10]
from infra.data.loader import load_price_data
obj.price_data = load_price_data(obj.universe, obj.start_date, obj.end_date)

study = optuna.create_study(direction='maximize')
study.optimize(obj, n_trials=3)

print(f'결과: {study.best_value:.2f}')
"
```

#### 2. 중규모 테스트 (30분)
```bash
# 50개 종목, 5 trials
python pc/cli.py optimize --start 2023-07-01 --end 2023-12-31 --trials 5 --seed 42
```

---

## 🚫 Phase 2의 한계

### 현실적 문제
1. **데이터 품질**: 많은 ETF가 짧은 히스토리
2. **계산 복잡도**: 695개 종목 × 복잡한 지표 = 매우 느림
3. **메모리**: 전체 데이터 로드 시 메모리 부족 가능

### Phase 2 목적 재정의

**원래 목적**: 
- Optuna 최적화
- 워크포워드 분석
- 로버스트니스 테스트

**현실적 목적**:
- ✅ **기능 검증**: 코드가 작동하는지 확인
- ✅ **소규모 테스트**: 10-50개 종목으로 검증
- ❌ **전체 최적화**: 현재 환경에서 비현실적

---

## 🎯 최종 권장사항

### Option 1: 소규모 검증 (권장)
```bash
# 10개 종목, 3 trials, 6개월
python -c "
from datetime import date
from extensions.optuna.objective import BacktestObjective
import optuna

obj = BacktestObjective(date(2023, 7, 1), date(2023, 12, 31), seed=42)
obj.universe = obj.universe[:10]

from infra.data.loader import load_price_data
obj.price_data = load_price_data(obj.universe, obj.start_date, obj.end_date)

study = optuna.create_study(direction='maximize')
study.optimize(obj, n_trials=3)
print(f'성공! 최적값: {study.best_value:.2f}')
"
```

### Option 2: Phase 2 건너뛰기
- Phase 1 백테스트 결과로 파라미터 결정
- Phase 3 (실시간 운영) 준비
- 필요 시 나중에 클라우드에서 대규모 최적화

### Option 3: 환경 개선 후 재시도
- 더 강력한 PC 사용
- 클라우드 인스턴스 (AWS, GCP)
- 병렬 처리 구현

---

## 📌 다음 단계 제안

1. **즉시**: Option 1 실행 (소규모 검증)
2. **성공 시**: 결과 확인 및 Phase 3 준비
3. **실패 시**: Phase 2 건너뛰고 Phase 3 진행

---

**작성일**: 2025-11-02
**상태**: 진단 완료, 조치 권장
**결론**: Phase 2 전체 실행은 비현실적, 소규모 검증 또는 건너뛰기 권장
