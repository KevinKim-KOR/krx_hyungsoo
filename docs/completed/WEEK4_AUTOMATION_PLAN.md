# Week 4: 자동화 시스템 구현 계획

**예상 기간**: 2~3일  
**예상 소요 시간**: 8시간  
**상태**: 📋 계획 중

---

## 🎯 목표

### 핵심 목표
- 평일 5분, 주말 30분 투자로 운영 가능한 자동화 시스템
- 파라미터 조정 UI 구현 (사용자 요청사항)
- 백테스트 히스토리 뷰어 (사용자 요청사항)

### 세부 목표
1. 실시간 데이터 수집 및 모니터링
2. 자동 매매 신호 생성
3. 텔레그램 알림 시스템
4. 웹 기반 파라미터 조정 UI
5. 백테스트 히스토리 관리

---

## 📅 일정

### Day 1: 실시간 모니터링 시스템 (3시간)

#### 1.1 데이터 수집 자동화
**파일**: `extensions/automation/data_updater.py`

**기능**:
- PyKRX를 통한 일별 가격 데이터 수집
- KOSPI 지수 데이터 수집
- 데이터베이스 자동 업데이트
- 스케줄링 (매일 장 마감 후 실행)

**구현**:
```python
class DataUpdater:
    def __init__(self):
        self.loader = PriceLoader()
        
    def update_daily_prices(self, date: date):
        """일별 가격 데이터 업데이트"""
        # PyKRX로 데이터 수집
        # DB에 저장
        # 로그 기록
        
    def update_kospi_index(self, date: date):
        """KOSPI 지수 업데이트"""
        # KODEX 200 데이터 수집
        # DB에 저장
```

#### 1.2 레짐 감지 자동화
**파일**: `extensions/automation/regime_monitor.py`

**기능**:
- 매일 레짐 분석
- 레짐 변경 감지
- 방어 모드 판단
- 변경 이력 저장

**구현**:
```python
class RegimeMonitor:
    def __init__(self):
        self.detector = MarketRegimeDetector()
        
    def analyze_daily_regime(self, date: date):
        """일별 레짐 분석"""
        # KOSPI 데이터 로드
        # 레짐 감지
        # 변경 여부 확인
        # 이력 저장
        
    def get_regime_history(self, days: int = 30):
        """레짐 변경 이력 조회"""
        # DB에서 이력 조회
        # DataFrame 반환
```

#### 1.3 매매 신호 생성
**파일**: `extensions/automation/signal_generator.py`

**기능**:
- MAPS 점수 계산
- Top N 종목 선정
- 포지션 크기 계산
- 매수/매도 신호 생성

**구현**:
```python
class SignalGenerator:
    def __init__(self):
        self.strategy = SignalGenerator()
        self.regime_monitor = RegimeMonitor()
        
    def generate_daily_signals(self, date: date):
        """일별 매매 신호 생성"""
        # 현재 레짐 확인
        # MAPS 점수 계산
        # 포지션 비율 적용
        # 매수/매도 신호 생성
        
    def get_buy_signals(self):
        """매수 신호 조회"""
        
    def get_sell_signals(self):
        """매도 신호 조회"""
```

---

### Day 2: 알림 시스템 (2시간)

#### 2.1 텔레그램 봇 연동
**파일**: `extensions/automation/telegram_notifier.py`

**기능**:
- 매매 신호 알림
- 레짐 변경 알림
- 방어 모드 진입/해제 알림
- 시장 급락 알림

**구현**:
```python
class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot = telegram.Bot(token=bot_token)
        self.chat_id = chat_id
        
    def send_buy_signal(self, signals: List[Dict]):
        """매수 신호 알림"""
        message = self._format_buy_signals(signals)
        self.bot.send_message(chat_id=self.chat_id, text=message)
        
    def send_regime_change(self, old_regime: str, new_regime: str):
        """레짐 변경 알림"""
        
    def send_defense_mode_alert(self, reason: str):
        """방어 모드 알림"""
```

#### 2.2 일일 리포트
**파일**: `extensions/automation/daily_report.py`

**기능**:
- 포트폴리오 현황
- 당일 수익률
- 레짐 상태
- 매매 신호

**구현**:
```python
class DailyReport:
    def generate_report(self, date: date):
        """일일 리포트 생성"""
        # 포트폴리오 현황
        # 수익률 계산
        # 레짐 상태
        # 매매 신호
        # 텔레그램 전송
```

#### 2.3 주간 리포트
**파일**: `extensions/automation/weekly_report.py`

**기능**:
- 주간 성과 요약
- 레짐 변경 히스토리
- 다음 주 전망

---

### Day 3: 파라미터 조정 UI (3시간) ⭐ 사용자 요청

#### 3.1 웹 대시보드
**파일**: `extensions/ui/dashboard.py`

**기술 스택**: Streamlit (빠른 개발) 또는 Gradio

**화면 구성**:
```
┌─────────────────────────────────────────┐
│  하이브리드 전략 대시보드               │
├─────────────────────────────────────────┤
│  [현재 상태]                            │
│  ├─ 현재 레짐: 상승장                   │
│  ├─ 포트폴리오 가치: 19,679,545원       │
│  ├─ 수익률: +96.80%                     │
│  └─ MDD: -19.92%                        │
├─────────────────────────────────────────┤
│  [파라미터 조정]                        │
│  ├─ 레짐 감지                           │
│  │  ├─ 단기 MA: [50] 일                │
│  │  ├─ 장기 MA: [200] 일               │
│  │  ├─ 상승장 임계값: [2.0] %          │
│  │  └─ 하락장 임계값: [-2.0] %         │
│  ├─ 포지션 비율                         │
│  │  ├─ 상승장 최소: [100] %            │
│  │  ├─ 상승장 최대: [120] %            │
│  │  ├─ 중립장: [80] %                  │
│  │  ├─ 하락장 최소: [40] %             │
│  │  └─ 하락장 최대: [60] %             │
│  ├─ 방어 시스템                         │
│  │  ├─ 방어 모드 임계값: [85] %        │
│  │  ├─ 시장 급락 (단일): [-5.0] %      │
│  │  └─ 시장 급락 (단기): [-7.0] %      │
│  └─ [백테스트 실행] 버튼                │
├─────────────────────────────────────────┤
│  [백테스트 히스토리] ⭐                 │
│  ┌───────────────────────────────────┐  │
│  │ 날짜      파라미터  CAGR  Sharpe │  │
│  │ 11-08 MA50/200  27.05% 1.51    │  │
│  │ 11-07 MA50/200  21.28% 1.46    │  │
│  │ 11-06 MA20/60   18.68% 1.17    │  │
│  │ 11-05 MA30/100  17.79% 1.14    │  │
│  └───────────────────────────────────┘  │
│  [비교 차트 보기]                       │
├─────────────────────────────────────────┤
│  [성과 차트]                            │
│  📈 CAGR 추이                           │
│  📊 MDD 비교                            │
│  📉 Sharpe 비교                         │
│  🎯 레짐 타임라인                       │
└─────────────────────────────────────────┘
```

**구현**:
```python
import streamlit as st

def main():
    st.title("하이브리드 전략 대시보드")
    
    # 현재 상태
    show_current_status()
    
    # 파라미터 조정
    params = show_parameter_panel()
    
    # 백테스트 실행
    if st.button("백테스트 실행"):
        results = run_backtest(params)
        save_to_history(results)
        
    # 백테스트 히스토리
    show_backtest_history()
    
    # 성과 차트
    show_performance_charts()
```

#### 3.2 파라미터 관리
**파일**: `extensions/ui/parameter_manager.py`

**기능**:
- 파라미터 저장/로드
- 프리셋 관리 (보수적/균형/공격적)
- 파라미터 검증

**구현**:
```python
class ParameterManager:
    def save_parameters(self, name: str, params: Dict):
        """파라미터 저장"""
        
    def load_parameters(self, name: str) -> Dict:
        """파라미터 로드"""
        
    def get_presets(self) -> Dict:
        """프리셋 조회"""
        return {
            'conservative': {...},  # 보수적
            'balanced': {...},      # 균형
            'aggressive': {...}     # 공격적
        }
```

#### 3.3 백테스트 히스토리 뷰어 ⭐ 사용자 요청
**파일**: `extensions/ui/backtest_history.py`

**기능**:
- 파라미터별 결과 비교
- 성과 지표 시각화
- 레짐 변경 타임라인
- 최적 파라미터 추천

**구현**:
```python
class BacktestHistory:
    def __init__(self):
        self.db = BacktestDatabase()
        
    def save_result(self, params: Dict, results: Dict):
        """백테스트 결과 저장"""
        
    def get_history(self, days: int = 30) -> pd.DataFrame:
        """히스토리 조회"""
        
    def compare_results(self, ids: List[int]) -> pd.DataFrame:
        """결과 비교"""
        
    def recommend_best_params(self, metric: str = 'sharpe') -> Dict:
        """최적 파라미터 추천"""
```

#### 3.4 차트 시각화
**파일**: `extensions/ui/charts.py`

**기능**:
- CAGR 추이 차트
- MDD 비교 차트
- Sharpe 비교 차트
- 레짐 타임라인

**구현**:
```python
import plotly.graph_objects as go

class ChartGenerator:
    def plot_cagr_trend(self, history: pd.DataFrame):
        """CAGR 추이 차트"""
        
    def plot_mdd_comparison(self, history: pd.DataFrame):
        """MDD 비교 차트"""
        
    def plot_regime_timeline(self, regime_history: pd.DataFrame):
        """레짐 타임라인"""
```

---

## 🗂️ 파일 구조

```
extensions/
├── automation/
│   ├── __init__.py
│   ├── data_updater.py          # 데이터 수집 자동화
│   ├── regime_monitor.py        # 레짐 감지 자동화
│   ├── signal_generator.py      # 매매 신호 생성
│   ├── telegram_notifier.py     # 텔레그램 알림
│   ├── daily_report.py          # 일일 리포트
│   └── weekly_report.py         # 주간 리포트
├── ui/
│   ├── __init__.py
│   ├── dashboard.py             # 메인 대시보드
│   ├── parameter_manager.py     # 파라미터 관리
│   ├── backtest_history.py      # 백테스트 히스토리
│   └── charts.py                # 차트 시각화
└── scheduler/
    ├── __init__.py
    └── task_scheduler.py        # 작업 스케줄러
```

---

## 🔧 기술 스택

### 백엔드
- **Python 3.13**
- **SQLite**: 백테스트 히스토리 저장
- **APScheduler**: 작업 스케줄링

### 프론트엔드
- **Streamlit**: 웹 대시보드 (빠른 개발)
- **Plotly**: 인터랙티브 차트
- **Pandas**: 데이터 처리

### 알림
- **python-telegram-bot**: 텔레그램 연동

---

## 📊 데이터베이스 스키마

### backtest_history 테이블
```sql
CREATE TABLE backtest_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    params_json TEXT,  -- 파라미터 (JSON)
    cagr REAL,
    sharpe_ratio REAL,
    max_drawdown REAL,
    total_return_pct REAL,
    num_trades INTEGER,
    regime_stats_json TEXT,  -- 레짐 통계 (JSON)
    notes TEXT
);
```

### regime_history 테이블
```sql
CREATE TABLE regime_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE UNIQUE,
    regime TEXT,  -- bull, bear, neutral
    confidence REAL,
    ma_short REAL,
    ma_long REAL,
    ma_diff_pct REAL
);
```

---

## 🎯 성공 기준

### 자동화
- ✅ 매일 자동으로 데이터 수집 및 신호 생성
- ✅ 텔레그램으로 알림 수신
- ✅ 평일 5분 투자로 운영 가능

### UI
- ✅ 파라미터 실시간 조정 가능
- ✅ 백테스트 즉시 실행 (30초 이내)
- ✅ 히스토리 비교 및 시각화

### 성능
- ✅ 대시보드 로딩 시간 < 3초
- ✅ 백테스트 실행 시간 < 30초
- ✅ 히스토리 조회 시간 < 1초

---

## 📝 참고 자료

### Streamlit 예제
- https://streamlit.io/gallery
- https://docs.streamlit.io/

### Telegram Bot
- https://python-telegram-bot.org/
- https://core.telegram.org/bots/api

### APScheduler
- https://apscheduler.readthedocs.io/

---

## ⚠️ 주의사항

### 보안
- 텔레그램 봇 토큰은 환경 변수로 관리
- API 키는 `.env` 파일에 저장 (Git 제외)

### 성능
- 백테스트는 비동기로 실행
- 대용량 데이터는 캐싱 활용

### 에러 처리
- 모든 자동화 작업에 에러 핸들링
- 실패 시 텔레그램 알림

---

**Week 4 시작 준비 완료!** 🚀
