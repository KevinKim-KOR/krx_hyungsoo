"""POC2 3-PUSH Runtime Package PC 검증 — probe cache 단위 테스트 (2026-06-13).

지시문 Q5 — TTL 30분 cache. cache hit → 외부 호출 없음. cache miss/TTL 만료
→ probe 1회. 신규 scheduler / refresh endpoint 0건. 외부 HTTP 는 monkeypatch.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import runtime_probe_cache as cache_mod


@pytest.fixture(autouse=True)
def _restore_real_cache_function(monkeypatch: pytest.MonkeyPatch):
    """conftest._stub_runtime_probes (autouse) 가 get_runtime_probe_snapshot 을
    교체했지만 본 파일은 cache 모듈 자체를 테스트하므로 원본 함수를 복원한다.
    실제 probe (probe_kr_quotes / probe_us_indices) 는 각 테스트가 monkeypatch.
    """
    # cache_mod 모듈은 직접 import 되었으므로 원본 함수가 그대로 살아있다 — 별도 복원 불필요.
    # 단, autouse stub 이 cache_mod.get_runtime_probe_snapshot 을 교체했으니 그것만 복원.
    import importlib

    importlib.reload(cache_mod)
    yield


_KR_OK = {
    "captured_at": "2026-06-13T08:55:00+09:00",
    "source": "naver",
    "items": [
        {
            "ticker": "069500",
            "name": "KODEX 200",
            "price": 36000,
            "change_pct": 0.42,
            "volume": 1,
            "data_status": "ok",
        }
    ],
    "status": "ok",
    "warnings": [],
    "errors": [],
}

_US_OK = {
    "captured_at": "2026-06-13T08:55:00+09:00",
    "indices": [
        {
            "symbol": "NASDAQ",
            "name": "Nasdaq Composite",
            "change_pct": 0.85,
            "close": 18000.12,
            "status": "ok",
        }
    ],
    "status": "ok",
    "warnings": [],
    "errors": [],
}


@pytest.fixture
def tmp_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cache_file = tmp_path / "runtime" / "three_push_runtime_probe_latest.json"
    monkeypatch.setattr(cache_mod, "CACHE_DIR", cache_file.parent, raising=True)
    monkeypatch.setattr(cache_mod, "CACHE_FILE", cache_file, raising=True)
    yield cache_file


def test_cache_miss_invokes_probes(tmp_cache: Path, monkeypatch: pytest.MonkeyPatch):
    """cache 미존재 시 두 probe 모두 호출 + 결과 저장."""
    kr_calls: list = []
    us_calls: list = []

    def _kr(tickers):
        kr_calls.append(list(tickers))
        return _KR_OK

    def _us():
        us_calls.append(1)
        return _US_OK

    monkeypatch.setattr(cache_mod, "probe_kr_quotes", _kr)
    monkeypatch.setattr(cache_mod, "probe_us_indices", _us)
    snap = cache_mod.get_runtime_probe_snapshot(kr_tickers=["069500"])
    assert kr_calls == [["069500"]]
    assert us_calls == [1]
    assert snap["cache_status"] == "miss"
    assert tmp_cache.exists()


def test_cache_hit_skips_probes(tmp_cache: Path, monkeypatch: pytest.MonkeyPatch):
    """fresh cache 가 있으면 probe 호출 0건."""
    fresh_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "captured_at": fresh_iso,
        "kr_realtime_price_snapshot": {**_KR_OK, "captured_at": fresh_iso},
        "overnight_us_market_snapshot": {**_US_OK, "captured_at": fresh_iso},
        "cache_status": "miss",
    }
    tmp_cache.parent.mkdir(parents=True, exist_ok=True)
    tmp_cache.write_text(json.dumps(payload), encoding="utf-8")

    def _kr(_):
        raise AssertionError("kr probe 호출되면 안 됨")

    def _us():
        raise AssertionError("us probe 호출되면 안 됨")

    monkeypatch.setattr(cache_mod, "probe_kr_quotes", _kr)
    monkeypatch.setattr(cache_mod, "probe_us_indices", _us)
    snap = cache_mod.get_runtime_probe_snapshot(kr_tickers=["069500"])
    assert snap["cache_status"] == "hit"


def test_cache_expired_triggers_reprobe(
    tmp_cache: Path, monkeypatch: pytest.MonkeyPatch
):
    """TTL 만료 시 새 probe 수행."""
    expired = (
        datetime.now(timezone.utc) - timedelta(minutes=cache_mod.TTL_MINUTES + 1)
    ).isoformat()
    payload = {
        "captured_at": expired,
        "kr_realtime_price_snapshot": {**_KR_OK, "captured_at": expired},
        "overnight_us_market_snapshot": {**_US_OK, "captured_at": expired},
        "cache_status": "miss",
    }
    tmp_cache.parent.mkdir(parents=True, exist_ok=True)
    tmp_cache.write_text(json.dumps(payload), encoding="utf-8")
    called = []
    monkeypatch.setattr(
        cache_mod, "probe_kr_quotes", lambda t: (called.append("kr"), _KR_OK)[1]
    )
    monkeypatch.setattr(
        cache_mod, "probe_us_indices", lambda: (called.append("us"), _US_OK)[1]
    )
    snap = cache_mod.get_runtime_probe_snapshot(kr_tickers=["069500"])
    assert "kr" in called and "us" in called
    assert snap["cache_status"] == "miss"


def test_force_refresh_bypasses_cache(tmp_cache: Path, monkeypatch: pytest.MonkeyPatch):
    fresh_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "captured_at": fresh_iso,
        "kr_realtime_price_snapshot": {**_KR_OK, "captured_at": fresh_iso},
        "overnight_us_market_snapshot": {**_US_OK, "captured_at": fresh_iso},
        "cache_status": "miss",
    }
    tmp_cache.parent.mkdir(parents=True, exist_ok=True)
    tmp_cache.write_text(json.dumps(payload), encoding="utf-8")
    called = []
    monkeypatch.setattr(
        cache_mod, "probe_kr_quotes", lambda t: (called.append("kr"), _KR_OK)[1]
    )
    monkeypatch.setattr(
        cache_mod, "probe_us_indices", lambda: (called.append("us"), _US_OK)[1]
    )
    snap = cache_mod.get_runtime_probe_snapshot(
        kr_tickers=["069500"], force_refresh=True
    )
    assert called == ["kr", "us"]
    assert snap["cache_status"] == "bypassed"


def test_corrupted_cache_triggers_reprobe(
    tmp_cache: Path, monkeypatch: pytest.MonkeyPatch
):
    """JSON 손상 시 silent fall-through 후 새 probe."""
    tmp_cache.parent.mkdir(parents=True, exist_ok=True)
    tmp_cache.write_text("not-a-json{", encoding="utf-8")
    called = []
    monkeypatch.setattr(
        cache_mod, "probe_kr_quotes", lambda t: (called.append("kr"), _KR_OK)[1]
    )
    monkeypatch.setattr(
        cache_mod, "probe_us_indices", lambda: (called.append("us"), _US_OK)[1]
    )
    snap = cache_mod.get_runtime_probe_snapshot(kr_tickers=["069500"])
    assert called == ["kr", "us"]
    assert snap["cache_status"] == "miss"


def test_both_failed_snapshots_are_not_cached(
    tmp_cache: Path, monkeypatch: pytest.MonkeyPatch
):
    """B-6 정책: 두 snapshot 모두 failed 면 cache 저장 안 함 (다음 호출이 즉시 재시도).
    한쪽이라도 ok/partial 이면 저장 (기존 정책).
    """
    kr_failed = {**_KR_OK, "status": "failed", "items": [], "errors": ["net"]}
    us_failed = {**_US_OK, "status": "failed", "indices": [], "errors": ["net"]}
    monkeypatch.setattr(cache_mod, "probe_kr_quotes", lambda t: kr_failed)
    monkeypatch.setattr(cache_mod, "probe_us_indices", lambda: us_failed)
    snap = cache_mod.get_runtime_probe_snapshot(kr_tickers=["069500"])
    assert snap["cache_status"] == "miss"
    assert not tmp_cache.exists(), "두 snapshot 모두 failed 면 cache 저장하지 않는다"


def test_partial_snapshot_is_cached(tmp_cache: Path, monkeypatch: pytest.MonkeyPatch):
    """한쪽 ok / 한쪽 failed → cache 저장."""
    us_failed = {**_US_OK, "status": "failed", "indices": [], "errors": ["net"]}
    monkeypatch.setattr(cache_mod, "probe_kr_quotes", lambda t: _KR_OK)
    monkeypatch.setattr(cache_mod, "probe_us_indices", lambda: us_failed)
    snap = cache_mod.get_runtime_probe_snapshot(kr_tickers=["069500"])
    assert snap["cache_status"] == "miss"
    assert tmp_cache.exists(), "한쪽이라도 ok 면 cache 저장"
