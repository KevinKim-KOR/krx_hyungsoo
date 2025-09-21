import os

DB_URL = os.environ.get("KRX_ALERTOR_DB", "sqlite:///krx_alertor.sqlite3")

# 벤치마크 (보고서 기본) — KODEX200, 비교용 S&P500 ETF는 아래에서 별도 지정
DEFAULT_BENCHMARK = "069500"

# ▶ 전략 기본 파라미터
EXCLUDE_KEYWORDS = ["레버리지", "채권", "커버드콜", "인버스", "선물", "ETN"]
REBAL_FREQ = "M"          # M=월 / W=주
TOP_N = 5                 # 상위 몇 종목
MOM_LOOKBACK_D = 126      # 모멘텀 룩백(약 6개월)
TREND_SMA_D = 200         # 종목 추세 필터(200일)
REGIME_TICKER_YF = "069500.KS"   # 시장 레짐(미국 S&P500 지수)
REGIME_SMA_D = 200           # S&P500 200일 이평 이하이면 '현금'

# 타임존/폴링
TIMEZONE = "Asia/Seoul"
REALTIME_INTERVAL_SEC = 300
REALTIME_DURATION_SEC = 1800

# 비교 대상: 한국거래소 379800 (KODEX 미국S&P500)
KOREA_SP500_ETF = "379800"
