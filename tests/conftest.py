"""POC2 Step 5D Cleanup — 공통 pytest fixture (autouse + 명시).

설계자 결정 (Step 5D 지시문 §4.1):
- 기존 tests/test_poc1_loop.py 의 단일 파일 누적을 의미별로 분리한다.
- 모든 분리 파일이 공유하는 fixture 는 본 conftest.py 에 둔다.
- pytest 가 같은 디렉터리(또는 상위) 의 conftest.py 를 자동 인식 — import 불필요.

내용:
- _isolated_store (autouse): runs / handoff / holdings / market_cache 경로 격리
- _stub_oci_calls (autouse): deliver / fetch_outbox_result 를 무동작 stub
- client: FastAPI TestClient
- _isolated_universe: Step5C universe seed / artifact 경로 격리

상수 / 헬퍼 함수는 tests/_helpers.py 로 분리 (fixture 가 아니므로 명시 import).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import api, delivery, holdings as holdings_module, market_cache, store


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path, monkeypatch):
    """runs / handoff / holdings / market_cache 경로를 임시 디렉터리로 격리."""
    monkeypatch.setattr(store, "STORE_DIR", Path(tmp_path) / "runs")
    monkeypatch.setattr(store, "HANDOFF_STAGING_DIR", Path(tmp_path) / "handoff")
    monkeypatch.setattr(
        store, "HANDOFF_PROCESSED_DIR", Path(tmp_path) / "handoff_processed"
    )
    # POC2 Step 1: holdings 저장 경로도 격리
    monkeypatch.setattr(holdings_module, "HOLDINGS_DIR", Path(tmp_path) / "holdings")
    monkeypatch.setattr(
        holdings_module,
        "HOLDINGS_FILE",
        Path(tmp_path) / "holdings" / "holdings_latest.json",
    )
    # POC2 Step 2: market cache 도 격리 (개발자 로컬에 캐시가 있어도 테스트는 항상 빈 상태부터)
    monkeypatch.setattr(market_cache, "CACHE_DIR", Path(tmp_path) / "market_cache")
    monkeypatch.setattr(
        market_cache,
        "CACHE_FILE",
        Path(tmp_path) / "market_cache" / "market_latest.json",
    )
    market_cache.reset_for_test()
    yield
    market_cache.reset_for_test()


@pytest.fixture(autouse=True)
def _stub_oci_calls(monkeypatch):
    """기본 stub: deliver 는 무동작 성공, outbox 는 결과 없음(DELIVERING 유지).

    개별 테스트가 필요시 monkeypatch.setattr 로 override.
    실 SCP/SSH 호출이 테스트 환경에서 발생하지 않도록 보장한다.
    """
    monkeypatch.setattr(delivery, "deliver", lambda run: None)
    monkeypatch.setattr(delivery, "fetch_outbox_result", lambda run_id: None)


@pytest.fixture(autouse=True)
def _stub_runtime_probes(monkeypatch):
    """3-PUSH Runtime Package PC 검증 (2026-06-13) — 모든 outbound HTTP 차단.

    개별 테스트가 실 probe 결과를 필요로 하면 override. 기본 stub 은 ok 응답.
    실 Yahoo Finance / Naver 호출이 테스트에서 발생하지 않도록 보장한다.
    """
    from app import runtime_probe_cache as _cache

    def _ok_snapshot(*, kr_tickers, force_refresh=False):
        return {
            "captured_at": "2026-06-13T08:55:00+09:00",
            "kr_realtime_price_snapshot": {
                "captured_at": "2026-06-13T08:55:00+09:00",
                "source": "naver",
                "items": [],
                "status": "unavailable",
                "warnings": [],
                "errors": [],
            },
            "overnight_us_market_snapshot": {
                "captured_at": "2026-06-13T08:55:00+09:00",
                "indices": [],
                "status": "unavailable",
                "warnings": [],
                "errors": [],
            },
            "cache_status": "hit",
        }

    monkeypatch.setattr(_cache, "get_runtime_probe_snapshot", _ok_snapshot)
    # draft 모듈들이 from-import 한 별칭도 차단.
    from app import draft as _draft_mod
    from app import draft_three_push as _draft_three

    monkeypatch.setattr(_draft_mod, "get_runtime_probe_snapshot", _ok_snapshot)
    monkeypatch.setattr(_draft_three, "get_runtime_probe_snapshot", _ok_snapshot)


@pytest.fixture
def client() -> TestClient:
    return TestClient(api.app)


@pytest.fixture
def _isolated_universe(tmp_path, monkeypatch):
    """Step5C 테스트용 universe seed / artifact 경로 격리.

    Step6 추가: pykrx fetcher 도 기본 stub 으로 격리한다 (실 네트워크 호출 차단).
    기본 stub 은 성공 결과를 반환 — Step5C 회귀 테스트가 status="ok" 를 가정하므로
    호환 유지. 개별 Step6 테스트는 monkeypatch.setattr 로 override 가능.
    """
    from app import universe_seed as us
    from app import universe_refresh as ur
    from app.momentum import universe_mode as um
    from app.price_history_pykrx import PriceHistoryBasis

    seed_dir = tmp_path / "universe"
    seed_dir.mkdir()
    seed_file = seed_dir / "etf_universe_latest.json"
    artifact_file = seed_dir / "universe_momentum_latest.json"

    monkeypatch.setattr(us, "UNIVERSE_DIR", seed_dir)
    monkeypatch.setattr(us, "UNIVERSE_SEED_FILE", seed_file)
    monkeypatch.setattr(um, "LATEST_ARTIFACT_DIR", seed_dir)
    monkeypatch.setattr(um, "LATEST_ARTIFACT_FILE", artifact_file)
    # POC2 Step 6: app.draft 는 LATEST_ARTIFACT_FILE 을 모듈 임포트 시점 별칭으로 들고
    # 있으므로 별도 monkeypatch 필요. app.api_universe 는 universe_mode 모듈 attribute 를
    # 호출 시점에 lookup 하므로 위 um monkeypatch 만으로 충분.
    from app import draft as _draft

    monkeypatch.setattr(_draft, "UNIVERSE_LATEST_FILE", artifact_file)

    # POC2 Step 6: pykrx fetcher 기본 stub — 실 네트워크 호출 차단.
    # ticker 별로 안정적 score 를 만들기 위해 ticker hash 로 기준 close 를 결정.
    # **kwargs 수용: score_candidates 의 default fetcher 가 fetch_window_days /
    # lookback_days 를 keyword 로 전달.
    def _stub_fetcher(ticker, asof, **_kwargs):
        ticker_factor = (sum(ord(c) for c in ticker) % 5) + 1  # 1..5
        base_close = 10000.0
        latest_close = base_close * (1 + ticker_factor / 100.0)  # +1%..+5%
        return PriceHistoryBasis(
            base_date="2026-04-10",
            base_close=base_close,
            latest_date=asof,
            latest_close=latest_close,
        )

    monkeypatch.setattr(ur, "fetch_one_month_basis", _stub_fetcher)
    # delay 도 0 으로 (테스트 속도)
    monkeypatch.setattr(ur, "PYKRX_PER_TICKER_DELAY_SECONDS", 0.0)

    return {"seed_file": seed_file, "artifact_file": artifact_file}
