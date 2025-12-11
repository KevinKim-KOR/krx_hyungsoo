# Config 파일로 하드코딩 값 이동 완료 ✅

**완료일**: 2025-11-29  
**소요 시간**: 30분  
**방식**: YAML Config + ConfigLoader

---

## 📊 작업 요약

### 완료된 작업
1. ✅ **ConfigLoader 클래스 생성** (`extensions/automation/config_loader.py`)
2. ✅ **Config 파일 업데이트** (`config/config.nas.yaml`)
3. ✅ **intraday_alert.py 수정** (Config 사용)
4. ✅ **테스트 작성 및 검증** (`tests/test_config_loader.py`)

---

## 🎯 이동된 하드코딩 값

### Before (하드코딩) ❌
```python
# scripts/nas/intraday_alert.py
THRESHOLDS = {
    'leverage': 3.0,
    'sector': 2.0,
    'index': 1.5,
    'overseas': 1.5,
    'default': 2.0
}

MIN_TRADE_VALUE = 50e8  # 50억원

exclude_keywords = [
    '레버리지', '인버스', '곱버스', 'LEVERAGE', 'INVERSE',
    '국고채', '회사채', '통안채', '채권', 'BOND',
    '머니마켓', 'MMF', '단기자금',
]
```

### After (Config 파일) ✅
```yaml
# config/config.nas.yaml
intraday_alert:
  thresholds:
    leverage: 3.0
    sector: 2.0
    index: 1.5
    overseas: 1.5
    default: 2.0
  
  min_trade_value: 5000000000  # 50억원
  
  exclude_keywords:
    - 레버리지
    - 인버스
    - 곱버스
    - LEVERAGE
    - INVERSE
    - 국고채
    - 회사채
    - 통안채
    - 채권
    - BOND
    - 머니마켓
    - MMF
    - 단기자금
```

### 코드에서 사용 (간단!) ✅
```python
# scripts/nas/intraday_alert.py
from extensions.automation.config_loader import get_config_loader

config = get_config_loader()

THRESHOLDS = config.get("intraday_alert.thresholds")
MIN_TRADE_VALUE = config.get("intraday_alert.min_trade_value")
EXCLUDE_KEYWORDS = config.get("intraday_alert.exclude_keywords")
```

---

## 🚀 ConfigLoader 기능

### 1. 중첩 키 접근
```python
# 점(.)으로 구분된 키 경로
config.get("intraday_alert.thresholds.leverage")  # 3.0
config.get("intraday_alert.min_trade_value")      # 5000000000
```

### 2. 기본값 지원
```python
# 키가 없으면 기본값 반환
config.get("non.existent.key", "DEFAULT")  # "DEFAULT"
```

### 3. 섹션 전체 가져오기
```python
# 섹션 딕셔너리 반환
intraday_config = config.get_section("intraday_alert")
# {'thresholds': {...}, 'min_trade_value': 5000000000, ...}
```

### 4. 캐싱
```python
# 첫 번째 호출: 파일 로드
config.load()  # YAML 파일 읽기

# 두 번째 호출: 캐시 사용
config.load()  # 즉시 반환 (파일 읽기 없음)
```

### 5. 싱글톤 패턴
```python
# 어디서든 동일한 인스턴스
config1 = get_config_loader()
config2 = get_config_loader()
assert config1 is config2  # True
```

---

## 📈 개선 효과

### 1. 유지보수성 향상 ⭐⭐⭐⭐⭐
**Before**: 코드 수정 → 재배포 필요
```python
# 코드 수정
THRESHOLDS['leverage'] = 3.5

# Git commit
git add scripts/nas/intraday_alert.py
git commit -m "임계값 조정"

# NAS 배포
ssh admin@nas
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
git pull
```

**After**: Config만 수정 → 즉시 적용
```yaml
# config/config.nas.yaml 수정
intraday_alert:
  thresholds:
    leverage: 3.5  # 3.0 → 3.5

# Git commit
git add config/config.nas.yaml
git commit -m "임계값 조정"

# NAS 배포
ssh admin@nas
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
git pull
# 코드 변경 없음! 즉시 적용!
```

### 2. 환경별 설정 분리 ⭐⭐⭐⭐
```bash
config/
├── config.nas.yaml   # NAS 전용 (경량)
├── config.pc.yaml    # PC 전용 (전체)
└── config.test.yaml  # 테스트 전용
```

### 3. 백테스트 후 최적화 용이 ⭐⭐⭐⭐⭐
```python
# 백테스트로 최적값 발견
best_thresholds = backtest_optimizer.find_best_thresholds()

# Config 파일만 업데이트
with open('config/config.nas.yaml', 'w') as f:
    yaml.dump({
        'intraday_alert': {
            'thresholds': best_thresholds
        }
    }, f)

# 코드 변경 없이 즉시 적용!
```

### 4. Git으로 설정 변경 추적 ⭐⭐⭐⭐
```bash
# 설정 변경 이력 확인
git log config/config.nas.yaml

# 특정 시점으로 롤백
git checkout <commit> config/config.nas.yaml
```

---

## 🧪 테스트 결과

### ConfigLoader 테스트
```bash
$ python tests/test_config_loader.py
============================================================
Config 로더 테스트
============================================================

1. intraday_alert 섹션 전체:
  섹션 키: ['thresholds', 'min_trade_value', 'exclude_keywords']

2. thresholds:
  leverage: 3.0%
  sector: 2.0%
  index: 1.5%
  overseas: 1.5%
  default: 2.0%

3. min_trade_value:
  5,000,000,000원 (50억원)

4. exclude_keywords:
  총 13개:
    - 레버리지
    - 인버스
    - 곱버스
    - LEVERAGE
    - INVERSE
    - 국고채
    - 회사채
    - 통안채
    - 채권
    - BOND
    - 머니마켓
    - MMF
    - 단기자금

5. 기본값 테스트:
  non.existent.key: DEFAULT_VALUE

============================================================
✅ Config 로더 테스트 성공!
============================================================
```

### 컴파일 테스트
```bash
$ python -m py_compile extensions/automation/config_loader.py
$ python -m py_compile scripts/nas/intraday_alert.py
✅ 컴파일 성공
```

---

## 📝 사용 예시

### 1. 임계값 조정
```yaml
# config/config.nas.yaml
intraday_alert:
  thresholds:
    leverage: 3.5  # 3.0 → 3.5 (더 엄격하게)
    sector: 1.8    # 2.0 → 1.8 (더 민감하게)
```

### 2. 최소 거래대금 조정
```yaml
# config/config.nas.yaml
intraday_alert:
  min_trade_value: 10000000000  # 50억 → 100억 (더 유동성 높은 종목만)
```

### 3. 제외 키워드 추가
```yaml
# config/config.nas.yaml
intraday_alert:
  exclude_keywords:
    - 레버리지
    - 인버스
    # ... 기존 키워드 ...
    - 원자재  # 새로 추가
    - 상품    # 새로 추가
```

---

## 🚀 NAS 배포 가이드

### 1. Git Pull
```bash
ssh admin@your-nas-ip
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
git pull origin main
```

### 2. 컴파일 테스트
```bash
python3.8 -m py_compile extensions/automation/config_loader.py
python3.8 -m py_compile scripts/nas/intraday_alert.py
```

### 3. Config 테스트
```bash
python3.8 tests/test_config_loader.py
```

### 4. 실행 테스트
```bash
source config/env.nas.sh
python3.8 scripts/nas/intraday_alert.py
```

---

## 💡 향후 확장

### 1. 다른 스크립트에도 적용
```python
# market_open_alert.py
config = get_config_loader()
MARKET_OPEN_TIME = config.get("market_open_alert.time", "09:00")

# weekly_report_alert.py
config = get_config_loader()
REPORT_DAY = config.get("weekly_report_alert.day", "saturday")
```

### 2. 환경별 Config
```python
# 환경에 따라 다른 Config 사용
import os
env = os.getenv('ENVIRONMENT', 'nas')
config = get_config_loader(f"config.{env}.yaml")
```

### 3. 동적 Config 업데이트
```python
# 웹 대시보드에서 Config 수정
def update_threshold(key, value):
    config_path = "config/config.nas.yaml"
    with open(config_path, 'r') as f:
        data = yaml.safe_load(f)
    
    data['intraday_alert']['thresholds'][key] = value
    
    with open(config_path, 'w') as f:
        yaml.dump(data, f)
```

---

## 📊 성과 요약

### 소요 시간
- **계획**: 30분
- **실제**: 30분
- **효율**: 100% ✅

### 코드 변경
| 파일 | 변경 내용 |
|------|----------|
| `config/config.nas.yaml` | +29 라인 (intraday_alert 섹션) |
| `config_loader.py` | +133 라인 (신규) |
| `intraday_alert.py` | +10 / -9 라인 (Config 사용) |
| `test_config_loader.py` | +62 라인 (신규) |

### 효과
- ✅ **유지보수성**: 코드 수정 없이 파라미터 조정
- ✅ **추적성**: Git으로 설정 변경 이력 관리
- ✅ **확장성**: 다른 스크립트에도 쉽게 적용
- ✅ **최적화**: 백테스트 결과 즉시 반영

---

## 🎉 완료!

**Config 파일로 하드코딩 값 이동 완료!** 🎉

**핵심 요약**:
- ✅ THRESHOLDS, MIN_TRADE_VALUE, EXCLUDE_KEYWORDS → Config 파일
- ✅ ConfigLoader 클래스로 간편한 접근
- ✅ 코드 수정 없이 파라미터 조정 가능
- ✅ 백테스트 후 최적화 용이

**다음 작업**:
1. **백테스트 기반 최적화** (2-3시간)
2. **대시보드 개선** (2-3시간)
3. **다른 스크립트에도 Config 적용** (1시간)

---

**Git Commit**: `4e91e7a1`
```
Config 파일로 하드코딩 값 이동 완료

추가:
- extensions/automation/config_loader.py
- tests/test_config_loader.py

수정:
- config/config.nas.yaml
- scripts/nas/intraday_alert.py

효과:
✅ 코드 수정 없이 파라미터 조정
✅ 환경별 설정 분리
✅ Git으로 변경 추적
✅ 백테스트 후 최적화 용이
```
