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

import sqlite3
import sys
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
def _isolated_holdings_selection_state(tmp_path, monkeypatch):
    """POC3-OPS-01A r3 — 보유 선정 상태 파일 격리 + 라이브 파일 **변경** 감지.

    러너 테스트가 `HOLDINGS_SELECTION_STATE_PATH` 를 개별로 monkeypatch 하고
    있었지만, **격리하지 않은 테스트는 flag guard 가 먼저 막아준 덕에** 라이브
    경로에 쓰지 않았을 뿐이다. 역검증에서 flag guard 를 무력화하자 실제로
    라이브 파일이 생겼다.

    r1 은 러너를 `importlib` 로 직접 import 해 격리했으나 러너는 import 시
    `load_dotenv_file()` 을 실행해 **모든 테스트 프로세스에 운영 `.env` 를 올리는
    부작용**이 있었다(r2 B-6). r2 는 그걸 빼는 대신 감지를 "파일이 새로 생겼나"
    로만 두어 **이미 있던 파일의 덮어쓰기를 놓쳤고**, 상대경로라 실행 위치가
    저장소 루트가 아니면 엉뚱한 곳을 봤다(r3 B-6).

    지금은 세 가지를 모두 만족시킨다.

    1. 경로는 러너와 **같은 절대경로**를 쓴다. `app.three_push_runner_common` 은
       import 해도 `.env` 를 읽지 않으므로 `STATE_DIR` 를 그대로 가져온다.
    2. 러너가 이미 import 돼 있으면 저장 경로를 `tmp_path` 로 덮어쓴다.
    3. import 여부와 무관하게 **생성뿐 아니라 내용 변경까지** 감지해 실패시킨다.
       원본 바이트를 들고 있다가 달라졌으면 되돌려 놓고 실패시킨다.

    POC3-OPS-02A — 위험 알림 상태 파일(`holdings_risk_state_latest.json`)도 같은
    보호를 받는다. 같은 러너 §8 이 쓰므로 하나만 막으면 "한 통로 막기" 다.
    """
    from app.three_push_runner_common import STATE_DIR as _STATE_DIR

    names = (
        "holdings_selection_state_latest.json",
        "holdings_risk_state_latest.json",
    )
    consts = (
        "HOLDINGS_SELECTION_STATE_PATH",
        "HOLDINGS_RISK_STATE_PATH",
    )
    lives = [(_STATE_DIR / n).resolve() for n in names]

    mod = sys.modules.get("scripts.run_three_push_runtime_oci")
    if mod is not None:
        for const, name in zip(consts, names):
            monkeypatch.setattr(mod, const, Path(tmp_path) / "three_push" / name)

    befores = [p.read_bytes() if p.exists() else None for p in lives]
    yield
    for live, before in zip(lives, befores):
        after = live.read_bytes() if live.exists() else None
        if after == before:
            continue
        _restore_and_fail(live, before)


def _restore_and_fail(live, before):
    """운영 파일을 원래대로 되돌린 뒤 실패시킨다.

    테스트가 남긴 상태로 다음 테스트가 돌면 원인 추적이 불가능해진다.
    """
    if before is None:
        live.unlink()
        what = "새로 만들었다"
    else:
        live.write_bytes(before)
        what = "덮어썼다"
    pytest.fail(
        f"테스트가 라이브 보유 상태 파일을 {what}: {live}\n"
        "경로 격리 없이 러너 저장 경로를 탄다 (원본은 되돌려 놓았다)."
    )


@pytest.fixture(autouse=True)
def _isolated_runtime_state_db(tmp_path, monkeypatch):
    """Refactor v1 Q4 (a) + FIX r1: runtime_state.sqlite + latest_runtime_param.json
    을 test 마다 tmp_path 로 격리.

    실제 운영 DB (`state/runtime/runtime_state.sqlite`) 및 실제 운영 PARAM 파일
    (`state/three_push/params/latest_runtime_param.json` / history/) 은 test 로
    write 되지 않는다. market_data.sqlite / decision_evidence.sqlite 등 다른 DB
    path 는 건드리지 않는다.
    """
    from app import api_three_push_param as _api
    from app import runtime_state_db as _rt_db
    from scripts import create_three_push_runtime_param as _create

    test_db_path = Path(tmp_path) / "runtime_state.sqlite"
    monkeypatch.setattr(_rt_db, "DEFAULT_DB_PATH", test_db_path)

    # FIX r1: legacy JSON write path 도 격리 (latest + history).
    # api_three_push_param 과 create_three_push_runtime_param 이 apply/approve
    # 흐름에서 실제 파일에 쓰지 못하도록 tmp_path 로 지정.
    test_param_dir = Path(tmp_path) / "three_push" / "params"
    test_history_dir = test_param_dir / "history"
    test_history_dir.mkdir(parents=True, exist_ok=True)
    test_latest_path = test_param_dir / "latest_runtime_param.json"
    monkeypatch.setattr(_api, "_LATEST_PATH", test_latest_path)
    monkeypatch.setattr(_create, "_LATEST_PATH", test_latest_path)
    monkeypatch.setattr(_create, "_HISTORY_DIR", test_history_dir)
    monkeypatch.setattr(_create, "_PARAM_DIR", test_param_dir)

    _rt_db.reset_init_cache_for_testing()
    yield
    _rt_db.reset_init_cache_for_testing()


@pytest.fixture(autouse=True)
def _block_live_benchmark_refresh(monkeypatch):
    """POC3-OPS-02B-1 — 테스트가 **라이브 시장 DB 로** benchmark 를 갱신하지 못하게.

    OCI 07:20 배치에 benchmark 갱신을 붙이자, 배치를 돌리는 기존 테스트가 그대로
    외부 조회 + 기본 DB 경로를 타서 **로컬 `market_data.sqlite` 에 KOSPI 120행·
    VIX 48행이 실제로 기록됐다**(검증자 r1 A-2·A-4). 개별 테스트를 하나씩 고치는
    것은 "한 통로 막기" 라 여기서 일괄로 막는다.

    **`db_path` 를 준 호출은 통과시킨다** — 그건 이미 격리된 호출이다. 기본값
    (=라이브 DB)으로 들어오는 호출만 막는다.
    """
    import app.market_benchmark_batch as _bench

    real_kospi, real_vix = _bench.refresh_kospi, _bench.refresh_vix

    def _fail(name):
        raise AssertionError(
            f"테스트가 라이브 benchmark 갱신을 시도했다 ({name}): "
            "FDR 외부 조회 + 기본 시장 DB 쓰기 경로다. "
            "배치를 돌리는 테스트는 refresh_benchmarks 를 stub 하거나 "
            "db_path 를 tmp 로 주입해야 한다."
        )

    def _guarded_kospi(*, end_date, db_path=None):
        if db_path is None:
            _fail("refresh_kospi")
        return real_kospi(end_date=end_date, db_path=db_path)

    def _guarded_vix(*, db_path=None):
        if db_path is None:
            _fail("refresh_vix")
        return real_vix(db_path=db_path)

    monkeypatch.setattr(_bench, "refresh_kospi", _guarded_kospi)
    monkeypatch.setattr(_bench, "refresh_vix", _guarded_vix)
    yield


@pytest.fixture(autouse=True)
def _detect_live_market_db_write():
    """라이브 시장 DB 의 benchmark 테이블이 테스트로 바뀌면 **실패시킨다**.

    위 stub 을 우회하는 경로가 새로 생겨도 여기서 잡힌다. 되돌리지는 않는다 —
    시세 데이터는 임의 복원이 더 위험하므로 사실만 알린다.
    """
    from app.market_data_store import DEFAULT_DB_PATH

    live = Path(DEFAULT_DB_PATH).resolve()

    def _fingerprint():
        if not live.exists():
            return None
        try:
            con = sqlite3.connect(f"file:{live}?mode=ro", uri=True)
            row = con.execute(
                "select count(*), max(created_at) from market_benchmark_daily_price"
            ).fetchone()
            con.close()
            return row
        except Exception:  # noqa: BLE001
            return None

    before = _fingerprint()
    yield
    after = _fingerprint()
    if before != after:
        pytest.fail(
            "테스트가 라이브 시장 DB 의 benchmark 테이블을 변경했다: "
            f"{live}\n  before={before}\n  after={after}"
        )


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
