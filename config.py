# 기본 설정 (하위 호환성)
import os

# 데이터베이스
DB_URL = "sqlite:///krx_alertor.sqlite3"

# 타임존
TIMEZONE = "Asia/Seoul"

# 캐시 디렉토리
CACHE_DIR = "data/cache"
OHLCV_CACHE_DIR = os.path.join(CACHE_DIR, "ohlcv")
CALENDAR_CACHE_DIR = os.path.join(CACHE_DIR, "kr")
