"""POC3-02D-OPS-03 — 08:10 배치 단계 격리 · FDR timeout · 09:20 KRX 전용 보강.

설계자 판정 STEP 12 검증 시나리오 6 · 11 · 12(확정 계약 2 · 7 · 13). 배치 `run()` 을
대역 단계로 관통한다. **외부 조회 0건 · 라이브 DB · state · logs 미접근 · 실제 sleep 0.**
"""

from __future__ import annotations

import functools
import json
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.market_briefing import krx_store, krx_target_sync, meta_gate
from app.three_push_runtime import market_data_batch as mdb
from app.three_push_runtime.market_data_batch import RefreshResult

KST = timezone(timedelta(hours=9))
TODAY = date(2026, 9, 30)


@pytest.fixture
def batch(monkeypatch, tmp_path):
    """가격 앞 단계를 대역으로 두고 호출 순서를 기록한다."""
    import scripts.run_oci_market_data_batch as batch

    calls: list[str] = []
    monkeypatch.setattr(mdb, "MARKET_DATA_BATCH_STATE_PATH", tmp_path / "bs.json")
    monkeypatch.setattr(
        mdb, "KRX_REINFORCEMENT_STATE_PATH", tmp_path / "reinforce.json"
    )
    monkeypatch.setattr(batch, "_kst_today", lambda: TODAY)
    monkeypatch.setattr(batch, "collect_approved_tickers", lambda: ["069500", "A"])

    def _refresh(tickers, *, end_date, **kw):
        calls.append("fdr")
        return RefreshResult(
            attempted=2, success=2, fail=0, price_data_as_of="2026-09-29"
        )

    monkeypatch.setattr(batch, "refresh_approved_prices", _refresh)

    def _bench(**kw):
        calls.append("benchmark")
        ok = {"status": "ok", "as_of_date": "2026-09-29", "error": None}
        return {"kospi": ok, "vix": ok, "status": "ok", "failed": []}

    monkeypatch.setattr("app.market_benchmark_batch.refresh_benchmarks", _bench)

    def _artifact(*, price_data_as_of):
        calls.append("artifact")
        art = {"mode": "universe", "summary": {"refresh_status": "ok"}}
        return art, "2026-09-30T08:10:30+09:00", "ok"

    monkeypatch.setattr(batch, "_build_universe_artifact", _artifact)
    monkeypatch.setattr(
        "app.universe_bootstrap.artifact_validator.validate_artifact",
        lambda *a, **k: (True, None, {}),
    )
    monkeypatch.setattr(
        batch, "evaluate_freshness", lambda **kw: SimpleNamespace(ok=True, reason="")
    )
    monkeypatch.setattr(
        "app.momentum.universe_mode.save_latest_artifact",
        lambda result: calls.append("save") or (tmp_path / "art.json"),
    )
    seen_state: dict = {}

    def _krx(**kw):
        calls.append("krx")
        # KRX 대기 전에 가격 · 미국 결과가 먼저 남아 있어야 한다.
        seen_state.update(json.loads((tmp_path / "bs.json").read_text("utf-8")))
        return {
            "status": "ok",
            "mode": "scheduled",
            "target_date": "2026-09-29",
            "basis_date": "20260929",
            "attempts": [{"at_kst": "2026-09-30T08:10:31+09:00", "result": "ok"}],
            "consistency_status": "ok",
        }

    monkeypatch.setattr(krx_target_sync, "sync_krx_target", _krx)
    batch._test_calls = calls
    batch._test_seen_state = seen_state
    return batch


# ── 시나리오 6 — FDR 일부 실패 · timeout 이 뒤 단계를 막지 않는다 ────────────


def test_s6_fdr_partial_failure_still_runs_us_kospi_vix_and_krx(batch, monkeypatch):
    monkeypatch.setattr(
        batch,
        "refresh_approved_prices",
        lambda tickers, *, end_date, **kw: batch._test_calls.append("fdr")
        or RefreshResult(
            attempted=2,
            success=1,
            fail=1,
            failures=[{"ticker": "A", "error": "ReadTimeout: x"}],
        ),
    )
    rec = batch.run(mode="run")

    assert batch._test_calls == ["fdr", "benchmark", "krx"]  # artifact 없음 · KRX 계속
    # 종료 status 는 예전 그대로 — 가격 소비자(Spike)가 fail-closed 한다.
    assert rec["status"] == "failed"
    assert rec["reason"] == "price_refresh_partial:fail=1/2"
    assert rec.get("price_pipeline_status") is None
    assert rec["stage_status"] == {
        "collect": "ok",
        "fdr_price": "failed",
        "benchmark": "ok",
        "artifact": "skipped",
        "krx": "ok",
    }
    assert rec["krx_sync_status"] == "ok" and rec["kospi_as_of"] == "2026-09-29"
    assert rec["price_failures"] == [{"ticker": "A", "error": "ReadTimeout: x"}]
    saved = mdb.read_batch_state()
    assert saved["status"] == "failed" and saved["refresh_date_kst"] == "2026-09-30"
    assert saved["stage_status"]["fdr_price"] == "failed"
    assert saved["krx_attempts"][0]["result"] == "ok"


def test_s6_fdr_exception_and_collect_failure_do_not_stop_later_stages(
    batch, monkeypatch
):
    def _boom(tickers, *, end_date, **kw):
        raise RuntimeError("hung")

    monkeypatch.setattr(batch, "refresh_approved_prices", _boom)
    rec = batch.run(mode="run")
    assert rec["reason"] == "refresh_error:RuntimeError"
    assert batch._test_calls == ["benchmark", "krx"]

    batch._test_calls.clear()

    def _no_holdings():
        raise RuntimeError("holdings source missing")

    monkeypatch.setattr(batch, "collect_approved_tickers", _no_holdings)
    rec = batch.run(mode="run")
    assert rec["reason"] == "collect_tickers_error:RuntimeError"
    assert rec["stage_status"]["fdr_price"] == "skipped"
    assert batch._test_calls == ["benchmark", "krx"]


def test_s6_benchmark_exception_is_isolated(batch, monkeypatch):
    def _boom(**kw):
        raise ValueError("bad")

    monkeypatch.setattr("app.market_benchmark_batch.refresh_benchmarks", _boom)
    rec = batch.run(mode="run")
    assert rec["status"] == "success_with_benchmark_failure"
    assert rec["price_pipeline_status"] == "success"
    assert "krx" in batch._test_calls and rec["krx_sync_status"] == "ok"


def test_success_path_order_and_state_written_before_krx_wait(batch):
    rec = batch.run(mode="run")
    assert rec["status"] == "success" and rec["reason"] is None
    assert batch._test_calls == ["fdr", "benchmark", "artifact", "save", "krx"]
    early = batch._test_seen_state
    assert early["status"] == "success" and early["stage_status"]["krx"] == "pending"
    final = mdb.read_batch_state()
    assert final["stage_status"]["krx"] == "ok"
    assert final["krx_target_date"] == "2026-09-29"
    assert final["krx_basis_date"] == "20260929"
    assert final["krx_stage_mode"] == "scheduled"
    # Spike 가 읽는 기존 키는 그대로다.
    assert {"status", "refresh_date_kst", "price_data_as_of"} <= set(final)


def test_krx_stage_exception_does_not_change_terminal_status(batch, monkeypatch):
    def _boom(**kw):
        raise RuntimeError("x")

    monkeypatch.setattr(krx_target_sync, "sync_krx_target", _boom)
    rec = batch.run(mode="run")
    assert rec["status"] == "success"
    assert rec["krx_sync_status"] == "unexpected:RuntimeError"


# ── FDR timeout (DEF-FDR-TIMEOUT) ──────────────────────────────────────────


@pytest.fixture
def spy_session(monkeypatch):
    """네트워크 없이 `requests` 호출의 timeout 인자만 기록한다."""
    import requests

    seen: list = []

    def _spy(self, method, url, *args, **kwargs):
        seen.append(kwargs.get("timeout"))
        if kwargs.get("timeout") is not None:
            raise requests.exceptions.ReadTimeout("simulated hang")
        return SimpleNamespace(status_code=200, text="")

    monkeypatch.setattr(requests.Session, "request", _spy)
    return seen


def test_fdr_timeout_is_injected_only_inside_the_block(spy_session):
    import requests

    before = requests.Session.request
    with pytest.raises(requests.exceptions.ReadTimeout):
        with mdb.fdr_request_timeout(3.0):
            requests.get("http://fdr.invalid/A")  # FDR 처럼 timeout 없이 부른다
    assert spy_session == [3.0]
    assert requests.Session.request is before  # 예외가 나도 원래대로
    requests.get("http://fdr.invalid/B")
    assert spy_session == [3.0, None]  # 블록 밖으로 새지 않는다
    with mdb.fdr_request_timeout(3.0):
        with pytest.raises(requests.exceptions.ReadTimeout):
            requests.get("http://fdr.invalid/C", timeout=9)
    assert spy_session[-1] == 9  # 호출자가 준 timeout 은 그대로


def test_s6_hung_ticker_times_out_and_batch_continues(batch, monkeypatch, spy_session):
    import requests

    def _refresh(tickers, *, end_date, **kw):
        batch._test_calls.append("fdr")
        fail = 0
        for tk in tickers:
            try:
                requests.get(f"http://fchart.invalid/{tk}")  # FDR 내부와 같은 호출
            except requests.exceptions.ReadTimeout:
                fail += 1
        return RefreshResult(attempted=len(tickers), success=0, fail=fail)

    monkeypatch.setattr(batch, "refresh_approved_prices", _refresh)
    rec = batch.run(mode="run")
    assert spy_session == [mdb.FDR_REQUEST_TIMEOUT_SECONDS] * 2
    assert rec["reason"] == "price_refresh_partial:fail=2/2"
    assert batch._test_calls == ["fdr", "benchmark", "krx"]


def test_s6_hung_benchmark_call_times_out_and_krx_still_runs(
    batch, monkeypatch, spy_session
):
    """미국 · VIX 조회(Yahoo)도 timeout 안에서 돈다 — 멈춘 호출이 KRX 단계를 막지 않는다."""
    import requests

    def _bench(**kw):
        batch._test_calls.append("benchmark")
        try:
            requests.get("http://yahoo.invalid/US500")  # FDR 내부와 같은 호출
        except requests.exceptions.ReadTimeout:
            return {"status": "failed", "failed": ["US500"], "kospi": {}, "vix": {}}
        return {"status": "ok", "failed": [], "kospi": {}, "vix": {}}

    monkeypatch.setattr("app.market_benchmark_batch.refresh_benchmarks", _bench)
    rec = batch.run(mode="run")
    assert spy_session == [mdb.FDR_REQUEST_TIMEOUT_SECONDS]
    assert rec["benchmark_status"] == "failed"
    assert batch._test_calls == ["fdr", "benchmark", "artifact", "save", "krx"]


def test_fdr_stage_passes_time_budget(batch, monkeypatch):
    seen: dict = {}

    def _refresh(tickers, *, end_date, **kw):
        seen.update(kw)
        return RefreshResult(attempted=2, success=2, fail=0, price_data_as_of="x")

    monkeypatch.setattr(batch, "refresh_approved_prices", _refresh)
    batch.run(mode="run")
    assert seen == {"time_budget_seconds": mdb.FDR_STAGE_TIME_BUDGET_SECONDS}


def test_fdr_time_budget_stops_starting_new_tickers(tmp_path):
    """원천 전체 불통 — 상한을 넘기면 남은 종목은 시작하지 않고 실패로 센다."""
    now = {"t": 0.0}
    called: list[str] = []

    def _hung(tks, **kw):
        called.append(tks[0])
        now["t"] += 20.0  # 종목마다 timeout 20초
        return SimpleNamespace(success=0, failure_examples=[{"ticker": tks[0]}])

    from app.market_data_store import EtfDailyPriceRow, upsert_daily_prices

    db = tmp_path / "m.sqlite"
    tickers = [f"{i:06d}" for i in range(41)]
    # 평소처럼 전날까지 종가가 있다(첫 적재가 아니다).
    upsert_daily_prices(
        [
            EtfDailyPriceRow(t, "2026-09-28", 1.0, 1.0, 1.0, 1.0, 1, 0.0)
            for t in tickers
        ],
        source="test",
        db_path=db,
    )
    r = mdb.refresh_approved_prices(
        tickers + ["999999"],  # 끝 종목은 저장 종가가 없는 새 종목
        end_date=TODAY,
        db_path=db,
        refresh_fn=_hung,
        time_budget_seconds=180.0,
        clock=lambda: now["t"],
    )
    assert called == tickers[:9]  # 9 × 20초 = 180초에서 멈춘다
    assert r.budget_skipped == tickers[9:] + ["999999"]
    # 시작하지 않은 새 종목을 '유효 종가 없음' 으로 한 번 더 세지 않는다.
    assert (r.attempted, r.success, r.fail) == (42, 0, 42)
    assert {"ticker": tickers[9], "error": "stage_time_budget:33"} in r.failures


def test_real_refresh_price_history_counts_timeout_as_ticker_failure(tmp_path):
    """`refresh_price_history` 는 종목 단위로 잡는다 — timeout 한 종목이 다음 종목을 막지 않는다."""
    import requests

    from app.market_data_fdr import refresh_price_history

    def _fetch(ticker, start, end):
        if ticker == "000001":
            raise requests.exceptions.ReadTimeout("hung")
        import pandas as pd

        return pd.DataFrame(
            {"Open": [1.0], "High": [1.0], "Low": [1.0], "Close": [1.0], "Volume": [1]},
            index=pd.to_datetime(["2026-09-29"]),
        )

    r = refresh_price_history(
        ["000001", "000002"],
        end_date=TODAY,
        lookback_days=3,
        price_fetcher=_fetch,
        db_path=tmp_path / "m.sqlite",
    )
    assert (r.success, r.fail) == (1, 1)
    assert "ReadTimeout" in r.failure_examples[0]["error"]


# ── 시나리오 11 — 09:20 KRX 전용 보강 ────────────────────────────────────────


def _calendar(tmp_path):
    d = tmp_path / "cal"
    d.mkdir(exist_ok=True)
    day, lines = date(2026, 7, 1), ["date"]
    holidays = {"2026-08-17", "2026-09-24", "2026-09-25", "2026-10-05", "2026-10-09"}
    while day <= date(2026, 12, 30):
        if day.weekday() < 5 and day.isoformat() not in holidays:
            lines.append(day.isoformat())
        day += timedelta(days=1)
    (d / "krx_trading_days_2026.csv").write_text("\n".join(lines) + "\n", "utf-8")
    return d


def _rows(bas_dd, n=30):
    return [
        {
            "ISU_CD": f"T{i:03d}",
            "BAS_DD": bas_dd,
            "TDD_CLSPRC": "100",
            "TDD_OPNPRC": "100",
            "TDD_HGPRC": "100",
            "TDD_LWPRC": "100",
            "IDX_IND_NM": "코스피 200",
        }
        for i in range(n)
    ]


@pytest.fixture
def krx_only(monkeypatch, tmp_path):
    """실제 `sync_krx_target` 에 임시 DB · 가짜 fetcher · 09:20 시계만 끼운다."""
    import scripts.run_oci_market_data_batch as batch
    from app import trading_day_lag

    cal = _calendar(tmp_path)
    db = tmp_path / "m.sqlite"
    days = trading_day_lag.trading_days_ending("2026-09-28", 20, calendar_dir=cal)
    for d in days:
        krx_store.upsert_snapshot(
            [
                krx_store.SnapshotRow(date=d, ticker=f"T{i:03d}", close=100.0)
                for i in range(30)
            ],
            db_path=db,
        )
    env = tmp_path / ".env"
    env.write_text("KRX_API_KEY=DEADBEEF\n", encoding="utf-8")
    monkeypatch.setattr(batch, "_kst_today", lambda: TODAY)
    monkeypatch.setattr(mdb, "MARKET_DATA_BATCH_STATE_PATH", tmp_path / "bs.json")
    monkeypatch.setattr(
        mdb, "KRX_REINFORCEMENT_STATE_PATH", tmp_path / "reinforce.json"
    )
    # 08:10 배치 상태 — 09:20 보강이 덮으면 안 된다.
    (tmp_path / "bs.json").write_text('{"status": "success"}', encoding="utf-8")

    # 부른 것을 **기록**한다 — 예외만 올리면 배치의 단계 격리(`_fdr_stage` ·
    # `_benchmark_stage` 의 except)가 삼켜 테스트가 못 잡는다(리뷰 지적).
    forbidden: list[str] = []

    def _forbid(name):
        def _called(*a, **k):
            forbidden.append(name)
            raise AssertionError(f"09:20 보강이 {name} 을 불렀다")

        return _called

    monkeypatch.setattr(batch, "collect_approved_tickers", _forbid("collect"))
    monkeypatch.setattr(batch, "refresh_approved_prices", _forbid("fdr"))
    monkeypatch.setattr(
        "app.market_benchmark_batch.refresh_benchmarks", _forbid("benchmark")
    )

    state = {"responses": [], "calls": [], "forbidden": forbidden}

    def _fetch(bas_dd, key):
        state["calls"].append(bas_dd)
        return state["responses"].pop(0) if state["responses"] else []

    t = datetime(2026, 9, 30, 9, 20, tzinfo=KST)
    real = krx_target_sync.sync_krx_target
    monkeypatch.setattr(
        krx_target_sync,
        "sync_krx_target",
        functools.partial(
            real,
            db_path=db,
            env_path=env,
            calendar_dir=cal,
            fetcher=_fetch,
            required_tickers=["T000"],
            clock=lambda: t,
            sleep=lambda s: pytest.fail("09:20 보강은 기다리지 않는다"),
        ),
    )
    state.update(batch=batch, db=db, bs=tmp_path / "bs.json")
    return state


def test_s11_reinforcement_success_single_call(krx_only):
    krx_only["responses"] = [_rows("20260929")]
    rec = krx_only["batch"].run_krx_only()
    assert rec["status"] == "ok" and rec["attempted"] is True
    assert krx_only["calls"] == ["20260929"]
    assert rec["krx_stage_mode"] == krx_target_sync.MODE_SINGLE
    assert krx_store.row_count_on("2026-09-29", db_path=krx_only["db"]) == 30
    assert krx_only["bs"].read_text("utf-8") == '{"status": "success"}'
    saved = mdb.read_krx_reinforcement_state()
    assert saved["date_kst"] == "2026-09-30" and saved["status"] == "ok"
    assert krx_only["forbidden"] == []  # FDR · 미국 · 대상 수집 0회(확정 계약 7)


def test_s11_reinforcement_failure_is_one_attempt_then_once_per_day(krx_only):
    rec = krx_only["batch"].run_krx_only()
    assert rec["status"] == krx_target_sync.STATUS_TARGET_NOT_OBTAINED
    assert krx_only["calls"] == ["20260929"]  # 1회 · 재시도 없음
    assert krx_only["bs"].read_text("utf-8") == '{"status": "success"}'

    krx_only["responses"] = [_rows("20260929")]
    again = krx_only["batch"].run_krx_only()
    assert again["status"] == "skipped_already_ran_today"
    assert krx_only["calls"] == ["20260929"]  # 하루 1회
    assert mdb.read_krx_reinforcement_state()["status"] == "target_not_obtained"
    assert krx_only["forbidden"] == []


def test_s11_reinforcement_makes_no_call_when_t1_already_loaded(krx_only):
    import app.three_push_runner_common as common

    krx_only["responses"] = [_rows("20260929")]
    krx_only["batch"].run_krx_only()  # T-1 적재 · 판정
    cpath = common.STATE_DIR / meta_gate.CONSISTENCY_STATE_NAME  # conftest 격리 경로
    judged = cpath.read_bytes()
    assert meta_gate.load_consistency(cpath).evaluated_api_basis_date == "20260929"
    krx_only["calls"].clear()
    mdb.KRX_REINFORCEMENT_STATE_PATH.unlink()  # 하루 1회 기록을 지워도
    rec = krx_only["batch"].run_krx_only()
    assert rec["status"] == "ok" and rec["attempted"] is False
    assert rec["krx_stage_mode"] == krx_target_sync.MODE_ALREADY_LOADED
    assert krx_only["calls"] == []
    assert cpath.read_bytes() == judged  # 성공한 T-1 판정을 다시 쓰지 않는다
    assert krx_only["forbidden"] == []


def test_s11_manual_krx_only_inside_0810_0827_is_still_one_attempt(
    krx_only, monkeypatch
):
    """08:10 ~ 08:27 에 수동으로 `--krx-only` 를 돌려도 1회다(`max_attempts=1`).

    보강은 기다리지 않는다 — 시각표(08:15 · 08:20 · 08:24)를 따르면 fixture 의
    `sleep` 이 실패시킨다.
    """
    t = datetime(2026, 9, 30, 8, 12, tzinfo=KST)
    monkeypatch.setattr(
        krx_target_sync,
        "sync_krx_target",
        functools.partial(krx_target_sync.sync_krx_target, clock=lambda: t),
    )
    rec = krx_only["batch"].run_krx_only()
    assert rec["status"] == krx_target_sync.STATUS_TARGET_NOT_OBTAINED
    assert krx_only["calls"] == ["20260929"]
    assert rec["krx_stage_mode"] == krx_target_sync.MODE_SINGLE
    assert krx_only["forbidden"] == []


def test_krx_only_flag_is_parsed_and_exclusive(monkeypatch):
    import scripts.run_oci_market_data_batch as batch

    monkeypatch.setattr("sys.argv", ["x", "--krx-only"])
    assert batch._parse_args().krx_only is True
    monkeypatch.setattr("sys.argv", ["x", "--krx-only", "--dry-run"])
    with pytest.raises(SystemExit):
        batch._parse_args()
