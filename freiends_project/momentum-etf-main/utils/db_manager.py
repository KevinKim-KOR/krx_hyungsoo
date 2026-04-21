import os
import time
from urllib.parse import quote_plus

from dotenv import load_dotenv
from pymongo import MongoClient

try:
    import data.settings as global_settings  # type: ignore
except ImportError:  # pragma: no cover - 하위 호환
    global_settings = object()
from utils.logger import get_app_logger

# .env 파일이 있다면 로드합니다.
load_dotenv()

# --- 전역 변수로 DB 연결 관리 ---
_db_connection = None
_mongo_client: MongoClient | None = None
logger = get_app_logger()


def _reset_connection() -> None:
    """캐시된 Mongo 연결을 닫고 초기화한다."""
    global _db_connection, _mongo_client
    _db_connection = None
    if _mongo_client is not None:
        try:
            _mongo_client.close()
        except Exception:
            pass
    _mongo_client = None


def _resolve_connection_string() -> str | None:
    """환경 변수로부터 MongoDB 연결 문자열을 결정한다.

    우선순위:
    1) MONGO_DB_CONNECTION_STRING 가 설정되어 있으면 그대로 사용 (하위호환)
    2) MONGO_DB_USER / MONGO_DB_PASSWORD / MONGO_DB_HOST 가 모두 있으면 조립
       - host 가 *.mongodb.net 이면 mongodb+srv:// 자동 선택
       - 그 외에는 mongodb:// (authSource=admin, retryWrites, w=majority 기본 옵션)
    """
    existing = (os.environ.get("MONGO_DB_CONNECTION_STRING") or "").strip()
    if existing:
        return existing

    user = (os.environ.get("MONGO_DB_USER") or "").strip()
    password = os.environ.get("MONGO_DB_PASSWORD") or ""
    host = (os.environ.get("MONGO_DB_HOST") or "").strip()
    if not (user and password and host):
        return None

    db_name = (os.environ.get("MONGO_DB_NAME") or "momentum_etf_db").strip() or "momentum_etf_db"
    is_srv = host.endswith(".mongodb.net")
    scheme = "mongodb+srv" if is_srv else "mongodb"

    default_opts = (
        "retryWrites=true&w=majority"
        if is_srv
        else "authSource=admin&retryWrites=true&w=majority"
    )
    options = (os.environ.get("MONGO_DB_OPTIONS") or default_opts).strip()

    user_q = quote_plus(user)
    pass_q = quote_plus(password)
    uri = f"{scheme}://{user_q}:{pass_q}@{host}/{db_name}"
    if options:
        uri = f"{uri}?{options}"
    return uri


def _build_client(connection_string: str) -> MongoClient:
    """환경 변수 기반으로 MongoClient를 생성한다."""
    max_pool = int(os.environ.get("MONGO_DB_MAX_POOL_SIZE", "10"))
    min_pool = int(os.environ.get("MONGO_DB_MIN_POOL_SIZE", "0"))
    max_idle = int(os.environ.get("MONGO_DB_MAX_IDLE_TIME_MS", "60000"))
    wait_q_timeout = int(os.environ.get("MONGO_DB_WAIT_QUEUE_TIMEOUT_MS", "15000"))
    server_selection_timeout = int(os.environ.get("MONGO_DB_SERVER_SELECTION_TIMEOUT_MS", "10000"))
    connect_timeout = int(os.environ.get("MONGO_DB_CONNECT_TIMEOUT_MS", "10000"))
    socket_timeout = int(os.environ.get("MONGO_DB_SOCKET_TIMEOUT_MS", "10000"))
    heartbeat_frequency = int(os.environ.get("MONGO_DB_HEARTBEAT_FREQUENCY_MS", "10000"))

    client_kwargs = dict(
        maxPoolSize=max_pool,
        minPoolSize=min_pool,
        retryWrites=True,
        retryReads=True,
        serverSelectionTimeoutMS=server_selection_timeout,
        connectTimeoutMS=connect_timeout,
        socketTimeoutMS=socket_timeout,
        heartbeatFrequencyMS=heartbeat_frequency,
        appname="momentum-etf",
    )
    if max_idle > 0:
        client_kwargs["maxIdleTimeMS"] = max_idle
    if wait_q_timeout > 0:
        client_kwargs["waitQueueTimeoutMS"] = wait_q_timeout

    return MongoClient(connection_string, **client_kwargs)


def get_db_connection():
    """
    MongoDB 클라이언트 연결을 생성하고, 전역 변수에 저장하여 재사용합니다.
    """
    global _db_connection, _mongo_client

    # 이미 연결이 설정되어 있으면, 기존 연결을 반환합니다.
    if _db_connection is not None:
        return _db_connection

    connection_string = _resolve_connection_string() or getattr(
        global_settings, "MONGO_DB_CONNECTION_STRING", None
    )
    db_name = (os.environ.get("MONGO_DB_NAME") or "momentum_etf_db").strip() or "momentum_etf_db"
    if not connection_string:
        logger.error(
            "오류: MongoDB 연결 정보가 설정되지 않았습니다. "
            "MONGO_DB_CONNECTION_STRING 또는 MONGO_DB_USER/PASSWORD/HOST 환경변수를 확인하세요."
        )
        return None

    last_error: Exception | None = None
    for attempt, wait_seconds in enumerate((0, 1.5, 4.0), start=1):
        try:
            if wait_seconds > 0:
                time.sleep(wait_seconds)

            if _mongo_client is None:
                _mongo_client = _build_client(connection_string)

            client = _mongo_client
            client.admin.command("ping")
            _db_connection = client[db_name]
            logger.debug("MongoDB에 성공적으로 연결되었습니다. (attempt=%s)", attempt)
            return _db_connection
        except Exception as exc:
            last_error = exc
            logger.warning("MongoDB 연결 재시도 %s/3 실패: %s", attempt, exc)
            _reset_connection()

    logger.error("오류: MongoDB 연결에 실패했습니다: %s", last_error)
    return None
