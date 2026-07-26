"""OCI Operational Market Data Refresh v1 — focused test (§7 핵심 8계약).

1. 승인 seed 와 Holdings ticker만 수집
2. 증분 저장과 반복 실행 멱등성
3. DB schema·기존 데이터 보존
4. SQLite fetcher를 이용한 Builder 실행
5. 기존 pykrx 경로 보존
6. price_data_as_of와 생성 시각 분리
7. freshness 미달 시 Spike 미발송·registry 미기록
8. Market·Holdings 기존 운영 영향 없음
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone

import pytest

from app.market_data_store import (
    EtfDailyPriceRow,
    fetch_price_history,
    get_last_price_date,
    init_db,
    upsert_daily_prices,
)
from app.three_push_runtime.market_data_batch import (
    evaluate_freshness,
    refresh_approved_prices,
)


def list_tables(db_path):
    con = sqlite3.connect(str(db_path))
    try:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        con.close()


def _seed_prices(db_path, ticker, start_close, dates):
    rows = [
        EtfDailyPriceRow(
            ticker=ticker,
            date=d,
            open=None,
            high=None,
            low=None,
            close=start_close + i,
            volume=None,
            change=None,
        )
        for i, d in enumerate(dates)
    ]
    upsert_daily_prices(rows, source="test", db_path=db_path)


# ── 계약 1: 승인 seed ∪ Holdings ticker만 수집 ──────────────────────────────


def test_collect_approved_tickers_seed_union_holdings(tmp_path, monkeypatch):
    from app.three_push_runtime import market_data_batch as mdb
    from app import universe_seed as _us
    from app import holdings as _h
    from app.universe_seed import UniverseSeed, UniverseSeedItem

    fake_seed = UniverseSeed(
        asof="2026-07-24",
        source="manual_seed",
        source_freshness="fresh",
        staleness_days=0,
        items=[
            UniverseSeedItem(
                ticker="069500", name="A", universe_group=None, sector_or_theme=None
            ),
            UniverseSeedItem(
                ticker="139260", name="B", universe_group=None, sector_or_theme=None
            ),
        ],
    )
    monkeypatch.setattr(_us, "load_universe_seed", lambda *a, **k: fake_seed)
    # market_data_batch 가 import 하는 심볼도 대체.
    monkeypatch.setattr(
        "app.universe_seed.load_universe_seed", lambda *a, **k: fake_seed
    )

    hfile = tmp_path / "holdings.json"
    hfile.write_text(
        '{"holdings":[{"ticker":"069500","name":"A","quantity":10,'
        '"avg_buy_price":1000,"account_group":"일반"},'
        '{"ticker":"305720","name":"C","quantity":5,'
        '"avg_buy_price":2000,"account_group":"일반"}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(_h, "HOLDINGS_FILE", hfile)

    out = mdb.collect_approved_tickers()
    # seed(069500,139260) ∪ holdings(069500,305720) → 중복 069500 제거.
    assert out == ["069500", "139260", "305720"]


# ── 계약 2·3: 증분 저장 멱등 + DB schema/기존 데이터 보존 ──────────────────


def test_incremental_refresh_idempotent_and_preserves(tmp_path):
    db = tmp_path / "market_data.sqlite"
    init_db(db)
    tables_before = set(list_tables(db))

    # 기존 데이터 적재.
    _seed_prices(db, "069500", 1000.0, ["2026-07-01", "2026-07-02", "2026-07-03"])
    before = fetch_price_history("069500", db_path=db)
    assert len(before) == 3

    # fake refresh_fn: 2026-07-04 를 추가 upsert. 두 번 호출해도 동일 결과.
    def _fake_refresh(tickers, *, end_date, db_path, lookback_days=None):
        _seed_prices(db_path, tickers[0], 1003.0, ["2026-07-04"])

        class _R:
            success = 1
            fail = 0
            failure_examples = []

        return _R()

    r1 = refresh_approved_prices(
        ["069500"], end_date=date(2026, 7, 4), db_path=db, refresh_fn=_fake_refresh
    )
    after1 = fetch_price_history("069500", db_path=db)
    refresh_approved_prices(
        ["069500"], end_date=date(2026, 7, 4), db_path=db, refresh_fn=_fake_refresh
    )
    after2 = fetch_price_history("069500", db_path=db)

    assert r1.success == 1 and r1.fail == 0
    assert len(after1) == 4  # 2026-07-04 추가
    assert after1 == after2  # 멱등: 재실행해도 동일
    # DB schema 보존.
    assert set(list_tables(db)) == tables_before
    # 기존 데이터 보존.
    assert after2[0] == ("2026-07-01", 1000.0)


def test_get_last_price_date(tmp_path):
    db = tmp_path / "m.sqlite"
    init_db(db)
    assert get_last_price_date("069500", db_path=db) is None
    _seed_prices(db, "069500", 1000.0, ["2026-07-01", "2026-07-03"])
    assert get_last_price_date("069500", db_path=db) == "2026-07-03"


# ── 계약 4·5: SQLite fetcher Builder 실행 + pykrx 경로 보존 ─────────────────


def test_sqlite_fetcher_matches_contract(tmp_path):
    """SQLite fetcher 가 pykrx fetch_one_month_basis 와 동일 계약(PriceHistoryBasis)."""
    from app.price_history_sqlite import fetch_one_month_basis_sqlite
    from app.price_history_pykrx import PriceHistoryBasis

    db = tmp_path / "m.sqlite"
    init_db(db)
    # 40일치 시세 (base_target = asof-30 이후 첫 거래일 존재하도록).
    base = date(2026, 6, 1)
    dates = [(base + timedelta(days=i)).isoformat() for i in range(40)]
    _seed_prices(db, "069500", 1000.0, dates)

    res = fetch_one_month_basis_sqlite("069500", asof="2026-07-10", db_path=db)
    assert isinstance(res, PriceHistoryBasis)
    assert res.base_close > 0
    assert res.latest_close > 0
    assert res.base_date <= res.latest_date


def test_pykrx_path_preserved():
    """기존 pykrx 경로 (fetch_one_month_basis) 가 그대로 존재·독립."""
    from app.price_history_pykrx import fetch_one_month_basis
    import inspect

    # SQLite fetcher 는 별도 모듈 · pykrx 함수 시그니처 무변경.
    sig = inspect.signature(fetch_one_month_basis)
    assert "ticker" in sig.parameters
    assert "asof" in sig.parameters
    # score_candidates 기본 fetcher 는 여전히 pykrx (fetcher=None 시).
    from app.universe_refresh import score_candidates

    src = inspect.getsource(score_candidates)
    assert "fetch_one_month_basis" in src


# ── 계약 6: price_data_as_of ↔ artifact_generated_at 분리 ──────────────────


def test_as_of_fields_are_separate():
    """세 as-of 가 서로 다른 필드로 구분됨."""
    now = datetime(2026, 7, 24, 8, 0, tzinfo=timezone.utc)
    v = evaluate_freshness(
        price_data_as_of="2026-07-24",
        artifact_generated_at="2026-07-24T07:20:00+00:00",
        current_date="2026-07-24",
        now=now,
    )
    assert v.ok is True
    assert v.price_data_as_of == "2026-07-24"
    assert v.artifact_generated_at == "2026-07-24T07:20:00+00:00"
    assert v.price_data_as_of != v.artifact_generated_at


# ── 계약 7: freshness 미달 판정 ────────────────────────────────────────────


def test_freshness_price_stale_fails():
    now = datetime(2026, 7, 24, 8, 0, tzinfo=timezone.utc)
    v = evaluate_freshness(
        price_data_as_of="2026-07-03",  # 21일 지연
        artifact_generated_at="2026-07-24T07:20:00+00:00",
        current_date="2026-07-24",
        now=now,
    )
    assert v.ok is False
    assert v.reason.startswith("price_data_stale")


def test_freshness_artifact_stale_fails():
    now = datetime(2026, 7, 24, 8, 0, tzinfo=timezone.utc)
    v = evaluate_freshness(
        price_data_as_of="2026-07-24",
        artifact_generated_at="2026-07-20T00:00:00+00:00",  # 4일 전 > 36h
        current_date="2026-07-24",
        now=now,
    )
    assert v.ok is False
    assert v.reason.startswith("artifact_stale")


def test_freshness_missing_fields_fail():
    assert (
        evaluate_freshness(
            price_data_as_of=None,
            artifact_generated_at="2026-07-24T07:20:00+00:00",
            current_date="2026-07-24",
        ).ok
        is False
    )
    assert (
        evaluate_freshness(
            price_data_as_of="2026-07-24",
            artifact_generated_at=None,
            current_date="2026-07-24",
        ).ok
        is False
    )


# ── 계약 7 (Runner): freshness 미달 시 Spike 미발송·registry 미기록 ─────────


def test_runner_spike_freshness_stale_fail_closed(tmp_path, monkeypatch):
    from app.runtime_param_store import activate_param_version, create_param_version
    from app.runtime_sent_registry_store import count as registry_count
    from app.three_push_runtime_param import build_manual_seed_param
    import scripts.run_three_push_runtime_oci as runner
    from app import draft_three_push as _dtp

    param = build_manual_seed_param()
    vid, _, _ = create_param_version(param.to_dict())
    activate_param_version(vid, activated_by="test")

    monkeypatch.setenv("PUSH_AUTOSEND_ENABLED", "true")
    monkeypatch.setenv("PUSH_SPIKE_OR_FALLING_ALERT_ENABLED", "true")
    monkeypatch.setattr(runner, "telegram_send", lambda *a, **kw: (True, "", False))
    monkeypatch.setattr(runner, "_HISTORY_PATH", tmp_path / "history.jsonl")
    # price refresh guard 우회 (대상 없음).
    monkeypatch.setattr(runner, "_collect_target_tickers", lambda pk: [])

    # artifact: price(evidence_as_of) 오래됨 → freshness 미달.
    stale_art = {
        "mode": "universe",
        "asof": "2026-07-03",
        "summary": {
            "refresh_status": "ok",
            "falling_threshold_pct": -10.0,
            "spike_trigger_type": "falling",
            "spike_direction": "down",
            "evidence_as_of": "2026-07-03",
            "artifact_generated_at": "2026-07-03T07:20:00+00:00",
        },
        "candidates": [],
    }
    monkeypatch.setattr(_dtp, "_load_universe_artifact_for_spike", lambda: stale_art)

    calls = []
    monkeypatch.setattr(
        runner,
        "telegram_send",
        lambda *a, **kw: (calls.append("SEND"), (True, "", False))[1],
    )

    before = registry_count()
    rec = runner.run("spike_or_falling_alert", "send")
    assert rec["status"] == "failed"
    assert rec["reason"] == "freshness_stale"
    assert calls == []
    assert registry_count() == before


# ── 계약 8: Market·Holdings 는 freshness guard 무관 ─────────────────────────


def test_market_holdings_unaffected_by_freshness(tmp_path, monkeypatch):
    """Market 은 Spike freshness guard 를 타지 않는다 (별도 경로)."""
    import scripts.run_three_push_runtime_oci as runner
    import inspect

    src = inspect.getsource(runner.run)
    # freshness guard 는 spike_or_falling_alert 조건 안에만 있어야 함.
    assert "freshness_stale" in src
    # guard 블록 이전에 spike push_kind 가드가 존재 (guard 가 spike 전용).
    idx = src.index("freshness_stale")
    preceding = src[:idx]
    assert preceding.count("spike_or_falling_alert") >= 1


# ── REJECTED 정정: 거래일 freshness · Holdings 부재 · validate · asof 연결 ──


def test_freshness_friday_data_monday_run_passes():
    """C 확정: 금요일 데이터 + 월요일 실행. 3달력일 ≤ 7 상한 → 통과 (주말 흡수)."""
    now = datetime(2026, 7, 27, 8, 0, tzinfo=timezone.utc)  # 월요일
    v = evaluate_freshness(
        price_data_as_of="2026-07-24",  # 금요일 데이터
        artifact_generated_at="2026-07-27T07:20:00+00:00",
        current_date="2026-07-27",  # 월요일 (달력 3일)
        now=now,
    )
    assert v.ok is True
    assert v.price_lag_days == 3


def test_freshness_stale_db_blocked_not_false_fresh():
    """C 핵심: DB 가 오래된 상태(21달력일)면 stale 로 차단 (순환 결함 재발 방지)."""
    now = datetime(2026, 7, 24, 8, 0, tzinfo=timezone.utc)
    v = evaluate_freshness(
        price_data_as_of="2026-07-03",  # 3주 전 stale
        artifact_generated_at="2026-07-24T07:20:00+00:00",
        current_date="2026-07-24",
        now=now,
    )
    assert v.ok is False
    assert v.reason.startswith("price_data_stale")
    assert v.price_lag_days == 21


def test_freshness_over_7_calendar_days_stale():
    """C: 7달력일 초과는 stale (8일)."""
    now = datetime(2026, 7, 24, 8, 0, tzinfo=timezone.utc)
    v = evaluate_freshness(
        price_data_as_of="2026-07-16",  # 8달력일 전
        artifact_generated_at="2026-07-24T07:20:00+00:00",
        current_date="2026-07-24",
        now=now,
    )
    assert v.ok is False
    assert v.price_lag_days == 8


def test_collect_approved_tickers_holdings_missing_raises(tmp_path, monkeypatch):
    """B-1: Holdings 파일 부재 시 seed 만으로 축소하지 않고 raise (Fail-Closed)."""
    from app.three_push_runtime import market_data_batch as mdb
    from app import universe_seed as _us
    from app import holdings as _h
    from app.universe_seed import UniverseSeed, UniverseSeedItem

    fake_seed = UniverseSeed(
        asof="2026-07-24",
        source="manual_seed",
        source_freshness="fresh",
        staleness_days=0,
        items=[
            UniverseSeedItem(
                ticker="069500", name="A", universe_group=None, sector_or_theme=None
            )
        ],
    )
    monkeypatch.setattr(_us, "load_universe_seed", lambda *a, **k: fake_seed)
    monkeypatch.setattr(_h, "HOLDINGS_FILE", tmp_path / "no_holdings.json")
    with pytest.raises(RuntimeError, match="holdings source missing"):
        mdb.collect_approved_tickers()


def test_spike_freshness_invalid_artifact_fails():
    """A-1(6): 공용 validate_artifact 실패 시 freshness ok=False."""
    from app.three_push_runtime.spike_freshness import check_spike_freshness

    # mode 누락 → validate_artifact 실패.
    bad = {"summary": {"evidence_as_of": "2026-07-24"}, "candidates": []}
    r = check_spike_freshness(bad, runtime_date_kst="2026-07-24")
    assert r.ok is False
    assert r.reason.startswith("artifact_invalid")


def test_spike_freshness_fresh_artifact_passes(tmp_path, monkeypatch):
    """정상 artifact (validate 통과 + 당일 배치 success + 일치 + fresh) → ok."""
    from app.three_push_runtime import market_data_batch as mdb
    from app.three_push_runtime.spike_freshness import check_spike_freshness
    from datetime import datetime as _dt, timezone as _tz

    today = "2026-07-24"
    gen = _dt.now(_tz.utc).isoformat()
    state_path = tmp_path / "batch_state.json"
    monkeypatch.setattr(mdb, "MARKET_DATA_BATCH_STATE_PATH", state_path)
    mdb.write_batch_state(
        status="success",
        price_data_as_of=today,
        artifact_generated_at=gen,
        refresh_date_kst=today,
        refresh_completed_at="t",
        state_path=state_path,
    )
    art = {
        "mode": "universe",
        "asof": today,
        "summary": {
            "refresh_status": "ok",
            "evidence_as_of": today,
            "artifact_generated_at": gen,
        },
        "candidates": [],
    }
    r = check_spike_freshness(art, runtime_date_kst=today)
    # candidates=[] 는 validator 통과 (no-signal 정상). 당일 배치 성공 + fresh.
    assert r.ok is True


def test_batch_asof_uses_price_data_as_of(tmp_path, monkeypatch):
    """A-1(1,2): 배치 artifact 생성 시 asof 를 실제 price_data_as_of 로 override.

    seed.asof (옛 날짜) 가 아니라 갱신된 최신일이 evidence_as_of 로 들어감을 확인.
    """
    import scripts.run_oci_market_data_batch as batch
    from app.universe_seed import UniverseSeed, UniverseSeedItem

    captured = {}

    old_seed = UniverseSeed(
        asof="2026-06-01",  # 옛 seed 날짜
        source="manual_seed",
        source_freshness="fresh",
        staleness_days=0,
        items=[
            UniverseSeedItem(
                ticker="069500", name="A", universe_group=None, sector_or_theme=None
            )
        ],
    )
    monkeypatch.setattr(
        "app.universe_seed.load_universe_seed", lambda *a, **k: old_seed
    )
    monkeypatch.setattr(
        "app.universe_refresh.validate_seed_for_refresh", lambda s: None
    )

    def _fake_run_refresh(seed, *, fetcher=None):
        # 배치가 override 한 asof 를 캡처.
        captured["asof"] = seed.asof
        return [], "ok"

    monkeypatch.setattr("app.universe_refresh.run_universe_refresh", _fake_run_refresh)
    monkeypatch.setattr(
        "app.momentum.universe_mode.build_universe_momentum_result_scored",
        lambda **kw: {
            "mode": "universe",
            "asof": kw["seed"].asof,
            "summary": {},
            "candidates": [],
        },
    )

    # A-1(4): _build_universe_artifact 는 저장하지 않고 dict 를 반환.
    result, gen_at, status = batch._build_universe_artifact(
        price_data_as_of="2026-07-24"
    )
    # 실제 최신일이 Builder asof 로 전달됨 (seed.asof 2026-06-01 아님).
    assert captured["asof"] == "2026-07-24"
    assert result["summary"]["data_source"] == "sqlite_etf_daily_price"
    assert result["summary"]["artifact_generated_at"] == gen_at
    assert result["asof"] == "2026-07-24"
    assert status == "ok"


# ── REJECTED r2 정정: NULL 종가 · 공휴일 · 기존행 보존 · 실패 artifact 미저장 ──


def test_get_last_price_date_requires_valid_close(tmp_path):
    """A-1(2): NULL/0 종가만 있는 최신 행은 price_data_as_of 로 쓰이지 않는다."""
    import sqlite3

    db = tmp_path / "m.sqlite"
    init_db(db)
    _seed_prices(db, "069500", 1000.0, ["2026-07-23", "2026-07-24"])
    # 2026-07-27 행을 close=NULL 로 직접 삽입.
    con = sqlite3.connect(str(db))
    con.execute(
        "INSERT INTO etf_daily_price (ticker, date, close, source, fetched_at) "
        "VALUES ('069500','2026-07-27',NULL,'test','t')"
    )
    con.commit()
    con.close()
    # require_valid_close=True (기본): 유효 종가 최신일 = 2026-07-24.
    assert get_last_price_date("069500", db_path=db) == "2026-07-24"
    # require_valid_close=False: MAX(date) = 2026-07-27 (증분 시작점용).
    assert (
        get_last_price_date("069500", db_path=db, require_valid_close=False)
        == "2026-07-27"
    )


def test_spike_freshness_requires_today_batch_success(tmp_path, monkeypatch):
    """C 핵심: Spike 는 당일 배치 success + artifact price_as_of 일치를 요구."""
    from app.three_push_runtime import market_data_batch as mdb
    from app.three_push_runtime.spike_freshness import check_spike_freshness
    from datetime import datetime as _dt, timezone as _tz

    today = "2026-07-24"
    state_path = tmp_path / "batch_state.json"
    monkeypatch.setattr(mdb, "MARKET_DATA_BATCH_STATE_PATH", state_path)

    art = {
        "mode": "universe",
        "asof": today,
        "summary": {
            "refresh_status": "ok",
            "evidence_as_of": today,
            "artifact_generated_at": _dt.now(_tz.utc).isoformat(),
        },
        "candidates": [],
    }

    # 배치 상태 없음 → fail.
    r = check_spike_freshness(art, runtime_date_kst=today)
    assert r.ok is False
    assert r.reason == "batch_state_missing"

    # 배치 status=failed → fail.
    mdb.write_batch_state(
        status="failed",
        price_data_as_of=today,
        artifact_generated_at=art["summary"]["artifact_generated_at"],
        refresh_date_kst=today,
        refresh_completed_at="t",
        state_path=state_path,
    )
    r = check_spike_freshness(art, runtime_date_kst=today)
    assert r.ok is False
    assert r.reason.startswith("batch_not_success")

    # 배치 success + 일치 → ok.
    mdb.write_batch_state(
        status="success",
        price_data_as_of=today,
        artifact_generated_at=art["summary"]["artifact_generated_at"],
        refresh_date_kst=today,
        refresh_completed_at="t",
        state_path=state_path,
    )
    r = check_spike_freshness(art, runtime_date_kst=today)
    assert r.ok is True


def test_spike_freshness_price_as_of_mismatch_fails(tmp_path, monkeypatch):
    """C: artifact.evidence_as_of 와 배치 price_data_as_of 불일치 → fail."""
    from app.three_push_runtime import market_data_batch as mdb
    from app.three_push_runtime.spike_freshness import check_spike_freshness
    from datetime import datetime as _dt, timezone as _tz

    today = "2026-07-24"
    state_path = tmp_path / "batch_state.json"
    monkeypatch.setattr(mdb, "MARKET_DATA_BATCH_STATE_PATH", state_path)
    mdb.write_batch_state(
        status="success",
        price_data_as_of="2026-07-24",  # 배치는 7/24
        artifact_generated_at=_dt.now(_tz.utc).isoformat(),
        refresh_date_kst=today,
        refresh_completed_at="t",
        state_path=state_path,
    )
    art = {
        "mode": "universe",
        "asof": today,
        "summary": {
            "refresh_status": "ok",
            "evidence_as_of": "2026-07-23",  # artifact 는 7/23 (불일치)
            "artifact_generated_at": _dt.now(_tz.utc).isoformat(),
        },
        "candidates": [],
    }
    r = check_spike_freshness(art, runtime_date_kst=today)
    assert r.ok is False
    assert r.reason.startswith("price_as_of_mismatch")


def test_incremental_refresh_only_after_last_saved(tmp_path):
    """A-1 증분: lookback == gap. 마지막 저장일 **이전** 을 재조회하지 않는다.

    refresh_price_history 는 start_date = end_date - lookback_days 이므로
    lookback == gap 이면 start_date == 마지막 저장일 (그 이전 재조회 없음).
    """
    db = tmp_path / "m.sqlite"
    init_db(db)
    _seed_prices(db, "069500", 1000.0, ["2026-06-01", "2026-06-02", "2026-07-24"])

    captured = {}

    def _fake_refresh(tickers, *, end_date, db_path, lookback_days=None):
        captured["lookback"] = lookback_days

        class _R:
            success = 1
            fail = 0
            failure_examples = []

        return _R()

    refresh_approved_prices(
        ["069500"], end_date=date(2026, 7, 27), db_path=db, refresh_fn=_fake_refresh
    )
    # 마지막 저장일 2026-07-24, end 2026-07-27 → gap = 3. lookback == gap 이어야
    # start_date(= end - lookback) == 마지막 저장일. +경계 여유 없음.
    assert captured["lookback"] == 3


def test_refresh_missing_valid_price_ticker_fails(tmp_path):
    """A-1 전체 최솟값: 유효 종가 없는 대상은 제외 X → fail 집계, price_data_as_of=None."""
    import sqlite3

    db = tmp_path / "m.sqlite"
    init_db(db)
    _seed_prices(db, "A", 1000.0, ["2026-07-24"])
    # B: NULL 종가만.
    con = sqlite3.connect(str(db))
    con.execute(
        "INSERT INTO etf_daily_price (ticker, date, close, source, fetched_at) "
        "VALUES ('B','2026-07-24',NULL,'t','t')"
    )
    con.commit()
    con.close()

    def _fake(tickers, *, end_date, db_path, lookback_days=None):
        class _R:
            success = 1
            fail = 0
            failure_examples = []

        return _R()

    r = refresh_approved_prices(
        ["A", "B"], end_date=date(2026, 7, 24), db_path=db, refresh_fn=_fake
    )
    # B 유효 종가 없음 → fail>0, price_data_as_of=None (성공 확정 안 됨).
    assert r.fail >= 1
    assert r.price_data_as_of is None
    assert any(f.get("error") == "no_valid_close_price" for f in r.failures)


def test_refresh_result_without_success_field_fails(tmp_path):
    """B-1: refresh 결과에 success 필드 없으면 성공 처리 X → fail."""
    db = tmp_path / "m.sqlite"
    init_db(db)
    _seed_prices(db, "A", 1000.0, ["2026-07-23"])

    def _fake_no_field(tickers, *, end_date, db_path, lookback_days=None):
        class _R:  # success 필드 없음
            pass

        return _R()

    r = refresh_approved_prices(
        ["A"], end_date=date(2026, 7, 24), db_path=db, refresh_fn=_fake_no_field
    )
    assert r.fail >= 1
    assert any(f.get("error") == "refresh_result_no_success_field" for f in r.failures)


def test_refresh_bad_last_date_fails_closed(tmp_path, monkeypatch):
    """B-1: DB 최신일 형식 손상 시 전체 lookback fallback 하지 않고 실패 집계."""
    db = tmp_path / "m.sqlite"
    init_db(db)
    import app.three_push_runtime.market_data_batch as mdb

    # get_last_price_date 가 손상된 문자열 반환하도록.
    monkeypatch.setattr(mdb, "get_last_price_date", lambda *a, **k: "NOT-A-DATE")

    called = {"n": 0}

    def _fake_refresh(*a, **k):
        called["n"] += 1

        class _R:
            success = 1
            fail = 0

        return _R()

    r = refresh_approved_prices(
        ["069500"], end_date=date(2026, 7, 27), db_path=db, refresh_fn=_fake_refresh
    )
    # 손상 → fetch 호출 안 하고 fail 로 집계.
    assert r.fail == 1
    assert called["n"] == 0


def test_batch_failed_refresh_status_does_not_save(tmp_path, monkeypatch):
    """A-1(4): refresh_status != ok 면 latest artifact 저장 안 함."""
    import scripts.run_oci_market_data_batch as batch
    from app.three_push_runtime import market_data_batch as mdb

    # 배치 상태 파일을 tmp 로 격리 (실 state 오염 방지).
    monkeypatch.setattr(
        mdb, "MARKET_DATA_BATCH_STATE_PATH", tmp_path / "batch_state.json"
    )
    saved = {"called": False}
    monkeypatch.setattr(
        "app.momentum.universe_mode.save_latest_artifact",
        lambda result: saved.update(called=True) or (tmp_path / "art.json"),
    )
    # collect/refresh 를 통과시키고 _build_universe_artifact 가 failed 반환하도록.
    monkeypatch.setattr(batch, "collect_approved_tickers", lambda: ["069500"])
    from app.three_push_runtime.market_data_batch import RefreshResult

    monkeypatch.setattr(
        batch,
        "refresh_approved_prices",
        lambda *a, **k: RefreshResult(
            attempted=1, success=1, fail=0, price_data_as_of="2026-07-24"
        ),
    )
    monkeypatch.setattr(
        batch,
        "_build_universe_artifact",
        lambda *, price_data_as_of: (
            {
                "mode": "universe",
                "asof": price_data_as_of,
                "summary": {},
                "candidates": [],
            },
            "2026-07-24T07:20:00+00:00",
            "failed",  # refresh_status
        ),
    )
    monkeypatch.setattr(batch, "_HISTORY_PATH_UNUSED", None, raising=False)
    rec = batch.run(mode="run")
    assert rec["status"] == "failed"
    assert rec["reason"].startswith("refresh_status")
    # 실패 → save_latest_artifact 미호출.
    assert saved["called"] is False
