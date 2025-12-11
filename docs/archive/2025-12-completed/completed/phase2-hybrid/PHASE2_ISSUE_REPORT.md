# Phase 2 문제 진단 및 해결 방안

## 🔍 문제 요약

**Step 3-4 (워크포워드 분석, 로버스트니스 테스트)가 실패하고 있습니다.**

## 📊 진단 결과

### 1. 데이터 로딩 상태
✅ **정상**: `load_price_data` 함수는 정상 작동
- MultiIndex (code, date) 반환 확인
- 10개 종목 테스트: 132행 × 8열 로드 성공
- 'date' 레벨 존재 확인

### 2. Parquet 캐시 상태
⚠️ **일부 손상**: 815개 파일 중 일부 손상
- 손상 파일 예: `0000H0.parquet` (Repetition level histogram size mismatch)
- 정상 파일 예: `0000J0.parquet`, `0000Y0.parquet`
- **대부분 파일은 정상**

### 3. Optuna 최적화 실패 원인
❌ **모든 trial 실패** (목적함수 값: -999.0)

**근본 원인**:
```python
KeyError: 'Requested level (date) does not match index name (None)'
```

**발생 위치**: `extensions/backtest/runner.py` Line 67
```python
all_dates = sorted(price_data.index.get_level_values('date').unique())
```

**문제**: 
- `load_price_data`는 MultiIndex를 반환하지만
- `BacktestRunner.run()`에 전달될 때 인덱스가 손실되거나 변경됨

---

## 🛠️ 해결 방안

### 방안 1: 손상된 캐시 파일 재생성 (권장)

**문제**: 일부 Parquet 파일 손상
**해결**: 손상된 파일만 삭제하고 재다운로드

```bash
# 1. 손상된 파일 확인 및 삭제
python -c "
import pandas as pd
from pathlib import Path

cache_dir = Path('data/cache')
corrupted = []

for pf in cache_dir.glob('*.parquet'):
    try:
        pd.read_parquet(pf)
    except:
        corrupted.append(pf)
        pf.unlink()
        print(f'삭제: {pf.name}')

print(f'\n총 {len(corrupted)}개 파일 삭제')
"

# 2. 재다운로드
python pc/cli.py update --date 2024-12-30
```

### 방안 2: BacktestRunner 데이터 전달 검증

**문제**: `price_data` 인덱스가 `BacktestRunner.run()`에서 손실
**해결**: `objective.py`에서 데이터 전달 전 검증 추가

```python
# extensions/optuna/objective.py 수정
def __call__(self, trial: optuna.Trial) -> float:
    # ... (기존 코드)
    
    # 데이터 검증 추가
    if not isinstance(self.price_data.index, pd.MultiIndex):
        logger.error(f"price_data 인덱스가 MultiIndex가 아님: {type(self.price_data.index)}")
        return -999.0
    
    if 'date' not in self.price_data.index.names:
        logger.error(f"price_data에 'date' 레벨 없음: {self.price_data.index.names}")
        return -999.0
    
    # 백테스트 실행
    result = runner.run(...)
```

### 방안 3: 간소화된 테스트 (임시)

**목적**: Phase 2 기능 검증
**방법**: 소규모 데이터로 빠른 테스트

```bash
# 1. 소규모 최적화 (5 trials, 10개 종목, 1개월)
python -c "
from datetime import date
from extensions.optuna.objective import BacktestObjective
import optuna

# 소규모 설정
obj = BacktestObjective(
    start_date=date(2024, 1, 1),
    end_date=date(2024, 1, 31),
    seed=42
)

# 유니버스 축소
obj.universe = obj.universe[:10]
obj.price_data = obj.price_data[obj.price_data.index.get_level_values('code').isin(obj.universe)]

# 최적화
study = optuna.create_study(direction='maximize')
study.optimize(obj, n_trials=5)

print(f'최적 값: {study.best_value}')
print(f'최적 파라미터: {study.best_params}')
"
```

---

## 📝 권장 조치 순서

### Step 1: 손상 파일 확인 및 정리 (5분)
```bash
python -c "
import pandas as pd
from pathlib import Path

cache_dir = Path('data/cache')
total = 0
corrupted = 0

for pf in cache_dir.glob('*.parquet'):
    total += 1
    try:
        pd.read_parquet(pf)
    except:
        corrupted += 1
        print(f'손상: {pf.name}')

print(f'\n총 {total}개 중 {corrupted}개 손상 ({corrupted/total*100:.1f}%)')
"
```

### Step 2: 손상률에 따른 조치

#### 손상률 < 10%: 선택적 재생성
```bash
# 손상 파일만 삭제 후 재다운로드
python pc/cli.py update --date 2024-12-30
```

#### 손상률 >= 10%: 전체 재생성
```bash
# 전체 캐시 삭제 후 재다운로드
Remove-Item data/cache/*.parquet
python pc/cli.py update --date 2024-12-30
```

### Step 3: 데이터 검증
```bash
python test_data_loading.py
```

### Step 4: Phase 2 재시도
```bash
# 초고속 테스트
python pc/cli.py optimize --start 2024-01-01 --end 2024-03-31 --trials 5 --seed 42
```

---

## 🎯 예상 결과

### 성공 시
```
[I] Trial 0 finished with value: 15.23
[I] Trial 1 finished with value: 12.45
...
최적 목적함수 값: 15.2300
```

### 여전히 실패 시
```
Trial 0 failed: 'Requested level (date) does not match index name (None)'
```
→ **방안 2 적용 필요** (BacktestRunner 데이터 전달 검증)

---

## 💡 추가 제안

### 장기 해결책: 데이터 파이프라인 개선

1. **Parquet 검증 추가**
   ```python
   def validate_parquet(file_path):
       try:
           df = pd.read_parquet(file_path)
           assert not df.empty
           assert df.index.name in ['날짜', 'date']
           return True
       except:
           return False
   ```

2. **자동 복구 메커니즘**
   ```python
   if not validate_parquet(cache_file):
       logger.warning(f"손상된 캐시 발견: {cache_file}")
       cache_file.unlink()
       # 재다운로드
   ```

3. **데이터 품질 모니터링**
   - 주기적 캐시 검증
   - 손상률 추적
   - 자동 알림

---

## 📞 다음 단계

1. **즉시 조치**: Step 1-2 실행 (손상 파일 확인 및 정리)
2. **검증**: Step 3-4 실행 (데이터 검증 및 Phase 2 재시도)
3. **실패 시**: 방안 2 적용 (BacktestRunner 수정)
4. **성공 시**: Phase 2 전체 테스트 진행

---

**작성일**: 2025-11-02
**상태**: 진단 완료, 조치 대기
