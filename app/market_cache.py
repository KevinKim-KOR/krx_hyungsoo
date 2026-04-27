"""POC2 Step 2 — 시장 데이터 캐시 (메모리 + JSON 파일).

설계자 결정:
- 캐시 파일: state/market_cache/market_latest.json (단일)
- holdings 파일과 분리 (데이터 경계)
- 원자적 쓰기: 임시파일 → os.replace
- 동시 쓰기는 같은 프로세스 내 threading.Lock 으로 직렬화
- 쓰기 실패 시 기존 캐시 보존
- TTL/만료 정책 도입 안 함 — "최근 조회값 재사용" 수준

캐시 항목 1건 스키마:
{
  "ticker": "069500",
  "name": "KODEX 200",
  "current_price": 100240.0,
  "price_asof": "2026-04-27T16:10:16+09:00",
  "price_source": "naver"
}

캐시 파일 전체 스키마:
{
  "updated_at": "ISO-8601",
  "items": { "<ticker>": <항목 스키마> }
}
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

CACHE_DIR = Path("state/market_cache")
CACHE_FILE = CACHE_DIR / "market_latest.json"

_LOCK = threading.Lock()
_MEM_CACHE: dict[str, "MarketQuote"] = {}
_MEM_LOADED = False


@dataclass
class MarketQuote:
    ticker: str
    name: Optional[str]
    current_price: Optional[float]
    price_asof: Optional[str]
    price_source: str = "naver"

    def has_price(self) -> bool:
        return isinstance(self.current_price, (int, float)) and self.current_price > 0


def _atomic_write(path: Path, text: str) -> None:
    """임시 파일에 쓴 후 os.replace 로 교체. 실패 시 원본 파일 보존."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=".market_latest.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        # 실패 시 임시파일 정리 — 원본 파일은 그대로 유지
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _load_from_disk_unlocked() -> dict[str, MarketQuote]:
    if not CACHE_FILE.exists():
        return {}
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # 손상된 파일은 무시 (기존 캐시 보존 정책상 빈 dict 로 시작 — 다음 쓰기에서 정상 파일로 교체됨)
        return {}
    items = data.get("items") or {}
    result: dict[str, MarketQuote] = {}
    for ticker, raw in items.items():
        if not isinstance(raw, dict):
            continue
        result[ticker] = MarketQuote(
            ticker=str(raw.get("ticker") or ticker),
            name=(raw.get("name") if isinstance(raw.get("name"), str) else None),
            current_price=_coerce_price(raw.get("current_price")),
            price_asof=(
                raw.get("price_asof")
                if isinstance(raw.get("price_asof"), str)
                else None
            ),
            price_source=str(raw.get("price_source") or "naver"),
        )
    return result


def _coerce_price(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    return n


def _ensure_loaded() -> None:
    """첫 접근 시 디스크 → 메모리 1회 로드."""
    global _MEM_LOADED
    if _MEM_LOADED:
        return
    with _LOCK:
        if _MEM_LOADED:
            return
        _MEM_CACHE.clear()
        _MEM_CACHE.update(_load_from_disk_unlocked())
        _MEM_LOADED = True


def reset_for_test() -> None:
    """테스트 격리용. 메모리 캐시 + loaded 플래그 초기화."""
    global _MEM_LOADED
    with _LOCK:
        _MEM_CACHE.clear()
        _MEM_LOADED = False


def get(ticker: str) -> Optional[MarketQuote]:
    _ensure_loaded()
    return _MEM_CACHE.get(ticker)


def get_all() -> dict[str, MarketQuote]:
    _ensure_loaded()
    return dict(_MEM_CACHE)


def upsert_many(quotes: list[MarketQuote]) -> None:
    """여러 종목을 한 번에 갱신 + 디스크 원자적 저장.

    같은 프로세스 내 동시 쓰기는 _LOCK 으로 직렬화.

    "기존 캐시 보존" 정책 (강화):
    1. 쓰기 전에 반드시 디스크 캐시를 메모리에 병합한다 (_ensure_loaded). 서버
       재시작 직후 첫 호출이 upsert_many 라도, 부분 성공으로 인해 디스크에 있던
       타 종목의 기존 캐시가 사라지지 않는다.
    2. 디스크 쓰기가 실패하면 메모리 캐시도 직전 스냅샷으로 원복한다.
       원자적 교체라 실패 시 기존 파일은 손상되지 않으며, 메모리도 일관 유지.
    """
    if not quotes:
        return
    # 디스크 기존 캐시를 먼저 메모리에 로드 — 부분 fetch 결과가 기존 값을
    # 덮어쓰지 않고 병합되도록 보장. _LOCK 외부에서 호출해도 _ensure_loaded
    # 자체가 lock 으로 직렬화한다.
    _ensure_loaded()
    with _LOCK:
        # 직전 스냅샷 보존 — 쓰기 실패 시 롤백용.
        snapshot = dict(_MEM_CACHE)
        for q in quotes:
            _MEM_CACHE[q.ticker] = q
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "items": {t: asdict(q) for t, q in _MEM_CACHE.items()},
        }
        text = json.dumps(payload, indent=2, ensure_ascii=False)
        try:
            _atomic_write(CACHE_FILE, text)
        except Exception:
            # 디스크 쓰기 실패 → 메모리 캐시도 직전 스냅샷으로 원복.
            _MEM_CACHE.clear()
            _MEM_CACHE.update(snapshot)
            raise
