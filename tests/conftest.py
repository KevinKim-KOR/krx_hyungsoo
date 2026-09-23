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

import hashlib
import os
import sys
from pathlib import Path

import pytest

# 라이브 state/logs 쓰기 가드 — app 모듈 import **전에** 건다(import 시점 쓰기까지 막는다).
from tests import _live_guard  # noqa: E402

_live_guard.install()

from fastapi.testclient import TestClient  # noqa: E402

from app import (  # noqa: E402
    api,
    delivery,
    holdings as holdings_module,
    market_cache,
    store,
)

# 세션 전후 비교 대상 — POC4-01 사고에서 전체 회귀가 실제로 쓴 라이브 경로 5곳.
# 하위 프로세스처럼 가드 밖에서 쓰는 경우를 여기서 잡는다.
_LIVE_WATCH_FILES = (
    "state/market/market_data.sqlite",
    "state/market/nav_discount_refresh_latest.json",
    "logs/oci_market_data_batch.log",
    "logs/three_push_runtime_cron.log",
)
_LIVE_WATCH_DIRS = ("state/runs",)


def _live_fingerprint() -> dict:
    """감시 5곳의 sha256 + state/·logs/ 전체 파일의 (크기, mtime)."""
    root = _live_guard.PROJECT_ROOT
    out: dict = {}
    for rel in _LIVE_WATCH_FILES:
        path = root / rel
        if path.exists():
            digest = hashlib.sha256()
            with path.open("rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    digest.update(chunk)
            out[rel] = digest.hexdigest()
        else:
            out[rel] = None
    for rel in _LIVE_WATCH_DIRS:
        path = root / rel
        out[rel] = sorted(os.listdir(path)) if path.exists() else None
    for live_root in _live_guard.LIVE_ROOTS:
        for dirpath, _dirs, files in os.walk(live_root):
            for name in files:
                full = os.path.join(dirpath, name)
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                out[f"stat:{os.path.relpath(full, root)}"] = (
                    st.st_size,
                    st.st_mtime_ns,
                )
    return out


def pytest_unconfigure(config):
    _live_guard.uninstall()


def pytest_sessionstart(session):
    session.config._live_before = _live_fingerprint()


def pytest_sessionfinish(session, exitstatus):
    before = getattr(session.config, "_live_before", None)
    if before is None:
        return
    after = _live_fingerprint()
    changed = sorted(
        k for k in set(before) | set(after) if before.get(k) != after.get(k)
    )
    if not changed:
        return
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    lines = ["[live-state] 테스트 세션 동안 라이브 경로가 바뀌었다:"] + [
        f"  - {k}" for k in changed[:50]
    ]
    for line in lines:
        if reporter is not None:
            reporter.write_line(line, red=True)
        else:
            print(line)
    session.exitstatus = pytest.ExitCode.TESTS_FAILED


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

    POC3-OPS-02B-2 — 시장 브리핑 상태도 같은 §8 이 쓴다. 다만 경로가 러너
    상수가 아니라 `runner_market_briefing` 안에서 `STATE_DIR` 로 풀리므로,
    **그 모듈의 `STATE_DIR` 자체**를 격리해야 막힌다. 실제로 막기 전에
    라이브 `market_briefing_state_latest.json` 이 테스트로 덮어써졌다.
    """
    from app.three_push_runner_common import STATE_DIR as _STATE_DIR

    names = (
        "holdings_selection_state_latest.json",
        "holdings_risk_state_latest.json",
        "market_briefing_state_latest.json",
        "market_briefing_meta_consistency_latest.json",
        # POC3-02C-OPS-02 — 장중 사업군 억제 상태 · 회차 집계.
        #
        # 전체 회귀 1회에서 라이브 경로에 집계 파일이 실제로 생겼다(파일 내용
        # 확인). 가드를 넣은 뒤로는 3회 연속 깨끗하다. 다만 가드를 다시 빼도
        # **재현되지 않아** 어느 줄이 막는지는 단정하지 못한다 — 그래서 감지
        # (`names`)와 격리(`setattr`)를 **둘 다** 둔다.
        "sector_signal_state_latest.json",
        "intraday_checkup_tally_latest.json",
    )
    consts = (
        "HOLDINGS_SELECTION_STATE_PATH",
        "HOLDINGS_RISK_STATE_PATH",
    )
    lives = [(_STATE_DIR / n).resolve() for n in names]

    mod = sys.modules.get("scripts.run_three_push_runtime_oci")
    if mod is not None:
        for const, name in zip(consts, names[: len(consts)]):
            monkeypatch.setattr(mod, const, Path(tmp_path) / "three_push" / name)

    # 시장 브리핑은 상수가 아니라 모듈의 `STATE_DIR` 로 경로를 푼다.
    # 이 모듈은 import 해도 `.env` 를 읽지 않으므로 직접 가져와 격리한다.
    from app.three_push_runtime import runner_market_briefing as _mb

    iso = Path(tmp_path) / "three_push"
    iso.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(_mb, "STATE_DIR", iso)

    # 07:20 배치는 `STATE_DIR` 를 **호출 시점에** 읽어 정합성 결과를 쓴다
    # (`run_oci_market_data_batch` 가 유일). 원본 상수도 같이 격리한다.
    import app.three_push_runner_common as _common

    monkeypatch.setattr(_common, "STATE_DIR", iso)

    # 장중 경로는 `holdings_risk_flow` 의 모듈 상수로 경로를 푼다. 호출 시점에
    # 읽으므로 그 모듈 자체를 격리해야 막힌다.
    from app.runtime_evidence import holdings_risk_flow as _hrf

    monkeypatch.setattr(
        _hrf, "DEFAULT_SECTOR_STATE_PATH", iso / "sector_signal_state_latest.json"
    )
    monkeypatch.setattr(
        _hrf, "DEFAULT_TALLY_PATH", iso / "intraday_checkup_tally_latest.json"
    )

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
    with _live_guard.suspended():  # 되돌리기만 — 가드가 먼저 막으므로 보통은 오지 않는다
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
    """POC3-OPS-02B-1/2 — 테스트가 **라이브 시장 DB 로** benchmark 를 쓰지 못하게.

    처음에는 `refresh_kospi`/`refresh_vix` 두 함수만 감쌌다. 그런데 `02B-2` 에서
    `refresh_us_index` 가 추가되자 **가드 밖이라 라이브 DB 에 실제로 썼다**
    (US500·IXIC·^SOX 각 10행). 함수를 하나씩 막는 것은 "한 통로 막기" 다.

    그래서 **저장 계층**에 건다. `upsert_benchmark_prices` 를 **기본 db_path**
    (=라이브 DB)로 호출하면 차단한다. `db_path` 를 준 호출은 이미 격리된
    호출이므로 통과시킨다 — 그래야 실제 저장 경로를 검사할 수 있다.

    이 한 곳이 모든 현재·미래 benchmark 갱신 경로를 덮는다.
    """
    import app.market_benchmark_store as _store
    from app.market_data_store import DEFAULT_DB_PATH as _LIVE

    real_upsert = _store.upsert_benchmark_prices
    live = Path(_LIVE).resolve()

    def _guarded_upsert(*, db_path=None, **kw):
        # `db_path is None` 만 보면 뚫린다 — 호출부가 **기본값을 이미 해석해서**
        # 실제 라이브 경로를 넘기기 때문이다(`refresh_kospi_benchmark` 가 그렇다).
        # 그래서 **경로 자체**를 비교한다.
        target = Path(db_path).resolve() if db_path is not None else live
        if target == live:
            raise AssertionError(
                "테스트가 라이브 시장 DB 에 benchmark 를 쓰려 했다 "
                f"(benchmark_id={kw.get('benchmark_id')!r}, path={target}). "
                "db_path 를 tmp 로 주입하거나 갱신 함수를 stub 해야 한다."
            )
        return real_upsert(db_path=db_path, **kw)

    monkeypatch.setattr(_store, "upsert_benchmark_prices", _guarded_upsert)
    yield


@pytest.fixture(autouse=True)
def _isolated_side_outputs(tmp_path, monkeypatch):
    """POC4-01 사고 — 테스트가 라이브 NAV 요약·러너 로그에 쓰던 경로를 tmp 로 돌린다.

    `NAV_REFRESH_SUMMARY_PATH` 와 로그 폴더는 **호출 시점에** 읽히는 모듈 상수다.
    `scripts.three_push_oci_helpers` 는 import 하면 `.env` 를 읽으므로, 이미 import
    된 경우에만 바꾼다(그 밖의 경로는 `_live_guard` 가 쓰는 순간 막는다).
    """
    from app import market_refresh_service as _mrs
    import app.three_push_runner_common as _common

    # tmp_path 바로 아래가 아니라 전용 하위 폴더 — tmp_path 를 훑는 테스트(AC-8)와 섞이지 않게.
    side = Path(tmp_path) / "_side_outputs"
    logs = side / "logs"
    monkeypatch.setattr(
        _mrs, "NAV_REFRESH_SUMMARY_PATH", side / "nav_discount_refresh_latest.json"
    )
    monkeypatch.setattr(_common, "LOG_DIR", logs)
    helpers = sys.modules.get("scripts.three_push_oci_helpers")
    if helpers is not None:
        monkeypatch.setattr(helpers, "_LOG_DIR", logs)
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
            # 사본이 아니라 라이브 파일을 본다 (가드는 라이브 경로를 세션 사본으로 돌린다).
            con = _live_guard.real_connect(f"file:{live}?mode=ro", uri=True)
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


@pytest.fixture(autouse=True)
def _block_live_krx_api(monkeypatch):
    """POC3-OPS-02B-2 — 테스트가 **라이브 KRX Open API** 를 호출하지 못하게.

    07:20 배치 테스트는 `refresh_benchmarks` 만 stub 했고 `sync_krx_daily` 는
    그대로 뒀다. 맥 `.env` 에 `KRX_API_KEY` 가 있어 **실제로 외부 호출이 나갔고**
    그 결과가 라이브 정합성 상태 파일에 쓰였다.

    네트워크 경계(`_default_fetcher`)에 건다. `fetcher` 를 명시로 넘긴 호출은
    이미 격리된 것이므로 건드리지 않는다. `sync_krx_daily` 는 예외를 올리지
    않는 계약이라 차단 시 `api_fetch_failed` 로 떨어진다 — 테스트 환경에서
    맞는 결과다.
    """
    from app.market_briefing import krx_sync

    def _blocked(bas_dd, key):
        raise AssertionError(
            "테스트가 라이브 KRX Open API 를 호출했다. " "`fetcher=` 로 stub 을 넘겨라."
        )

    monkeypatch.setattr(krx_sync, "_default_fetcher", _blocked)
