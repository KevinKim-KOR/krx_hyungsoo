# Phase 5: 중복 로직 제거 및 코드 통일화 분석

**분석일**: 2025-11-29  
**목표**: 중복 로직 제거 및 코드 통일화를 통한 유지보수성 향상

---

## 📊 중복 패턴 분석 결과

### 1. 공통 초기화 패턴 (모든 스크립트)

**중복 코드**:
```python
# 프로젝트 루트를 PYTHONPATH에 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 로깅 설정
setup_logging()
logger = logging.getLogger(__name__)
```

**발견 위치**:
- `scripts/nas/intraday_alert.py`
- `scripts/nas/market_open_alert.py`
- `scripts/nas/weekly_report_alert.py`
- `scripts/nas/daily_report_alert.py`
- `scripts/nas/daily_regime_check.py`
- `nas/app_realtime.py`

**중복 횟수**: 6곳

---

### 2. 포트폴리오 로딩 패턴

**중복 코드**:
```python
# 포트폴리오 로드
loader = PortfolioLoader()
summary = loader.get_portfolio_summary()
holdings_count = len(loader.get_holdings_codes())
holdings_detail = loader.get_holdings_detail()
```

**발견 위치**:
- `scripts/nas/market_open_alert.py` (lines 33-35)
- `scripts/nas/weekly_report_alert.py` (lines 50-52)
- `scripts/nas/intraday_alert.py` (lines 225-227)

**중복 횟수**: 3곳

---

### 3. 텔레그램 전송 패턴

**중복 코드**:
```python
# 텔레그램 전송
sender = TelegramSender()
success = sender.send_custom(message, parse_mode='Markdown')

if success:
    logger.info("✅ ... 전송 성공")
else:
    logger.warning("⚠️ ... 전송 실패")
```

**발견 위치**:
- `scripts/nas/market_open_alert.py` (lines 57-63)
- `scripts/nas/intraday_alert.py` (lines 320-329)
- `scripts/nas/weekly_report_alert.py` (lines 223-228)

**중복 횟수**: 3곳

---

### 4. 에러 처리 패턴

**중복 코드**:
```python
try:
    # 메인 로직
    ...
    return 0
except Exception as e:
    logger.error(f"❌ ... 실패: {e}", exc_info=True)
    return 1
```

**발견 위치**:
- `scripts/nas/market_open_alert.py` (lines 31-69)
- `scripts/nas/intraday_alert.py` (lines 222-337)
- `scripts/nas/weekly_report_alert.py` (lines 218-236)
- `scripts/nas/daily_report_alert.py` (lines 39-83)
- `nas/app_realtime.py` (lines 63-136)

**중복 횟수**: 5곳

---

### 5. 로깅 헤더 패턴

**중복 코드**:
```python
logger.info("=" * 60)
logger.info("작업 이름")
logger.info("=" * 60)
```

**발견 위치**:
- `scripts/nas/market_open_alert.py` (lines 27-29)
- `scripts/nas/intraday_alert.py` (lines 214-216)
- `scripts/nas/weekly_report_alert.py` (lines 214-216)
- `scripts/nas/daily_report_alert.py` (lines 32-34)
- `nas/app_realtime.py` (lines 59-61)

**중복 횟수**: 5곳

---

### 6. 포트폴리오 요약 포맷 패턴

**중복 코드**:
```python
# 수익/손실 색상 표시
if summary['return_amount'] >= 0:
    message += f"평가손익: 🔴 `{summary['return_amount']:+,.0f}원` ({summary['return_pct']:+.2f}%)\n"
else:
    message += f"평가손익: 🔵 `{summary['return_amount']:+,.0f}원` ({summary['return_pct']:+.2f}%)\n"
```

**발견 위치**:
- `scripts/nas/market_open_alert.py` (lines 48-51)
- `scripts/nas/weekly_report_alert.py` (lines 88-91)

**중복 횟수**: 2곳

---

## 📋 중복 통계

### 중복 패턴별 통계

| 패턴 | 중복 횟수 | 영향 파일 수 | 우선순위 |
|------|----------|-------------|---------|
| 공통 초기화 | 6곳 | 6개 | 🔴 높음 |
| 에러 처리 | 5곳 | 5개 | 🔴 높음 |
| 로깅 헤더 | 5곳 | 5개 | 🟡 중간 |
| 포트폴리오 로딩 | 3곳 | 3개 | 🟡 중간 |
| 텔레그램 전송 | 3곳 | 3개 | 🟡 중간 |
| 포트폴리오 포맷 | 2곳 | 2개 | 🟢 낮음 |

### 총 중복 라인 수
- **추정 중복 라인**: 약 150-200 라인
- **제거 가능 라인**: 약 100-150 라인 (공통 모듈로 추출 시)

---

## 🎯 개선 계획

### Phase 5.2: 공통 모듈 추출

#### 1. `extensions/automation/script_base.py` (신규)
**목적**: 스크립트 공통 기능 제공

**기능**:
- 프로젝트 루트 설정
- 로깅 초기화
- 에러 처리 데코레이터
- 로깅 헤더 유틸리티

**예상 코드**:
```python
class ScriptBase:
    """스크립트 베이스 클래스"""
    
    def __init__(self, script_name: str):
        self.script_name = script_name
        self.setup_environment()
        self.setup_logging()
    
    def setup_environment(self):
        """환경 설정"""
        PROJECT_ROOT = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(PROJECT_ROOT))
    
    def setup_logging(self):
        """로깅 설정"""
        setup_logging()
        self.logger = logging.getLogger(self.script_name)
    
    def log_header(self, message: str):
        """로깅 헤더"""
        self.logger.info("=" * 60)
        self.logger.info(message)
        self.logger.info("=" * 60)
    
    @staticmethod
    def handle_errors(func):
        """에러 처리 데코레이터"""
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"❌ 오류 발생: {e}", exc_info=True)
                return 1
        return wrapper
```

#### 2. `extensions/automation/portfolio_helper.py` (신규)
**목적**: 포트폴리오 관련 공통 기능

**기능**:
- 포트폴리오 로딩 헬퍼
- 포트폴리오 요약 포맷터
- 수익/손실 색상 포맷터

**예상 코드**:
```python
class PortfolioHelper:
    """포트폴리오 헬퍼"""
    
    def __init__(self):
        self.loader = PortfolioLoader()
    
    def load_full_data(self) -> dict:
        """전체 데이터 로드"""
        return {
            'summary': self.loader.get_portfolio_summary(),
            'holdings_count': len(self.loader.get_holdings_codes()),
            'holdings_codes': self.loader.get_holdings_codes(),
            'holdings_detail': self.loader.get_holdings_detail()
        }
    
    @staticmethod
    def format_return(return_amount: float, return_pct: float) -> str:
        """수익/손실 포맷"""
        emoji = "🔴" if return_amount >= 0 else "🔵"
        return f"{emoji} `{return_amount:+,.0f}원` ({return_pct:+.2f}%)"
```

#### 3. `extensions/notification/telegram_helper.py` (신규)
**목적**: 텔레그램 전송 공통 기능

**기능**:
- 전송 헬퍼
- 성공/실패 로깅

**예상 코드**:
```python
class TelegramHelper:
    """텔레그램 헬퍼"""
    
    def __init__(self):
        self.sender = TelegramSender()
        self.logger = logging.getLogger(__name__)
    
    def send_with_logging(
        self,
        message: str,
        success_msg: str,
        fail_msg: str,
        parse_mode: str = 'Markdown'
    ) -> bool:
        """로깅과 함께 전송"""
        success = self.sender.send_custom(message, parse_mode)
        
        if success:
            self.logger.info(f"✅ {success_msg}")
        else:
            self.logger.warning(f"⚠️ {fail_msg}")
        
        return success
```

---

### Phase 5.3: 리팩토링 적용

#### 리팩토링 순서
1. **공통 모듈 생성** (30분)
   - `script_base.py`
   - `portfolio_helper.py`
   - `telegram_helper.py`

2. **스크립트 리팩토링** (1시간)
   - `market_open_alert.py` → 공통 모듈 사용
   - `intraday_alert.py` → 공통 모듈 사용
   - `weekly_report_alert.py` → 공통 모듈 사용
   - `daily_report_alert.py` → 공통 모듈 사용

3. **테스트 및 검증** (30분)
   - 각 스크립트 컴파일 테스트
   - 실행 테스트 (dry-run)
   - 기능 동작 확인

---

### Phase 5.4: 예상 효과

#### 코드 라인 감소
- **Before**: 약 1,000 라인 (5개 스크립트)
- **After**: 약 850 라인 (공통 모듈 + 리팩토링된 스크립트)
- **감소율**: 15%

#### 유지보수성 향상
- ✅ **중복 제거**: 6개 패턴 제거
- ✅ **일관성**: 모든 스크립트가 동일한 패턴 사용
- ✅ **확장성**: 새로운 스크립트 추가 시 공통 모듈 재사용
- ✅ **버그 수정**: 한 곳만 수정하면 모든 스크립트에 적용

#### 개발 속도 향상
- ✅ **새 스크립트 작성 시간**: 50% 단축
- ✅ **버그 수정 시간**: 70% 단축
- ✅ **코드 리뷰 시간**: 40% 단축

---

## 💡 주의사항

### 1. 하위 호환성
- 기존 스크립트가 정상 동작해야 함
- 점진적 마이그레이션 (한 번에 하나씩)

### 2. 테스트
- 각 단계마다 컴파일 테스트
- 실행 테스트 (dry-run)
- 기능 동작 확인

### 3. 문서화
- 공통 모듈 사용법 문서화
- 마이그레이션 가이드 작성

---

## 📝 다음 단계

1. **Phase 5.2**: 공통 모듈 생성
2. **Phase 5.3**: 리팩토링 적용
3. **Phase 5.4**: 테스트 및 검증
4. **Phase 5.5**: 문서화 및 완료

**예상 총 소요 시간**: 2시간

---

**Phase 5.1 분석 완료!** 🎉
