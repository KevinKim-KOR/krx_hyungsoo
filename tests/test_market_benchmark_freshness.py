"""POC3-OPS-02B-1 — `DEF-KOSPI-BENCHMARK-VALUE-ASOF-INTEGRITY` 계약 test.

설계자 확정 최소 계약 7개를 고정한다. 합성 fixture 만 사용하며 외부 조회·DB
접근 0건이다.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.market_benchmark_freshness import (
    evaluate_freshness,
    return_by_trading_days,
)
from app.market_regime import compute_kospi_metrics, compute_market_context
from app.market_summary_composer import summarize_market_position

# 합성 거래일 축 (2026-08-03 ~ 평일 70일)
from datetime import date, timedelta


def _axis(n: int = 70, end: str = "2026-09-07") -> list[str]:
    d = date.fromisoformat(end)
    out: list[str] = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d -= timedelta(days=1)
    return sorted(out)


AXIS = _axis()


def _series(axis, *, start=100.0, step=1.0):
    return [(d, start + i * step) for i, d in enumerate(axis)]


# ── 계약 ② 자기 as_of_date ──────────────────────────────────────────────────


def test_kospi_metrics_carry_their_own_as_of_date():
    m = compute_kospi_metrics(_series(AXIS), trading_days=AXIS)
    assert m["status"] == "ok"
    assert m["as_of_date"] == AXIS[-1]
    assert m["freshness"]["reference_date"] == AXIS[-1]
    assert m["freshness"]["lag_trading_days"] == 0


def test_stale_kospi_keeps_as_of_date_but_drops_returns():
    """계약 ②⑤ — 값은 빼되 **언제 것인지는 숨기지 않는다**."""
    short = _series(AXIS[:-5])  # 5거래일 뒤처짐
    m = compute_kospi_metrics(short, trading_days=AXIS)
    assert m["status"] == "stale"
    assert m["as_of_date"] == AXIS[-6]
    assert m["freshness"]["lag_trading_days"] == 5
    for k in ("return_20d_pct", "return_60d_pct", "return_1m_pct", "return_3m_pct"):
        assert k not in m, f"stale 인데 {k} 를 산출했다"


# ── 계약 ③ 날짜 기준 수익률 ────────────────────────────────────────────────


def test_returns_use_trading_day_dates_not_positional_index():
    """중간 결측이 있어도 **20거래일 전 그 날짜**를 본다.

    위치 인덱스면 결측만큼 더 과거를 보게 되어 값이 달라진다.
    """
    full = _series(AXIS)
    holes = [(d, c) for d, c in full if d not in (AXIS[-5], AXIS[-9])]
    a = return_by_trading_days(full, trading_days=AXIS, lookback=20)
    b = return_by_trading_days(holes, trading_days=AXIS, lookback=20)
    assert a == b, "결측이 기준일을 밀었다 — 위치 인덱스로 계산되고 있다"


def test_return_is_none_when_base_date_missing():
    """기준일 값이 없으면 더 오래된 값으로 대체하지 않는다."""
    full = _series(AXIS)
    base_date = AXIS[-21]
    holes = [(d, c) for d, c in full if d != base_date]
    assert return_by_trading_days(holes, trading_days=AXIS, lookback=20) is None


def test_return_none_without_axis():
    assert return_by_trading_days(_series(AXIS), trading_days=[], lookback=20) is None


# ── 계약 ④ 최신성 1거래일 ──────────────────────────────────────────────────


def test_one_trading_day_lag_is_still_fresh():
    m = compute_kospi_metrics(_series(AXIS[:-1]), trading_days=AXIS)
    assert m["status"] == "ok"
    assert m["freshness"]["lag_trading_days"] == 1


def test_two_trading_day_lag_is_stale():
    m = compute_kospi_metrics(_series(AXIS[:-2]), trading_days=AXIS)
    assert m["status"] == "stale"
    assert m["freshness"]["lag_trading_days"] == 2


def test_freshness_without_axis_is_not_fresh():
    f = evaluate_freshness(_series(AXIS), trading_days=[])
    assert f.is_fresh is False
    assert f.reason == "no_trading_day_axis"


def test_freshness_no_data():
    f = evaluate_freshness([], trading_days=AXIS)
    assert f.is_fresh is False and f.reason == "no_data"


# ── 계약 ⑤ 상위 asof 로 표시 금지 ──────────────────────────────────────────


def test_market_context_asof_is_labelled_as_kodex200():
    ctx = compute_market_context(
        asof=AXIS[-1],
        kodex200_history=_series(AXIS),
        kospi_history=_series(AXIS[:-5]),
    )
    assert ctx["asof_source"] == "KODEX200"
    assert ctx["kospi"]["as_of_date"] == AXIS[-6]
    assert ctx["kospi"]["as_of_date"] != ctx["asof"]


def test_composer_does_not_emit_stale_kospi_values():
    ctx = compute_market_context(
        asof=AXIS[-1],
        kodex200_history=_series(AXIS),
        kospi_history=_series(AXIS[:-5]),
    )
    pos = {
        "daily_return_pct": 1.23,
        "return_1y_pct": 4.56,
        "high_52w_gap_pct": -7.89,
        "as_of_date": AXIS[-6],
    }
    out = summarize_market_position(
        market_context=ctx, kospi_position=pos, regime_streak=None
    )
    k = out["kospi"]
    assert k["status"] == "stale"
    assert k["daily_return_pct"] is None
    assert k["return_1y_pct"] is None
    assert k["high_52w_gap_pct"] is None
    assert k["as_of_date"] == AXIS[-6], "기준일까지 지우면 언제 것인지 알 수 없다"
    assert out["market_asof_source"] == "KODEX200"


def test_composer_emits_values_when_fresh():
    ctx = compute_market_context(
        asof=AXIS[-1],
        kodex200_history=_series(AXIS),
        kospi_history=_series(AXIS),
    )
    pos = {"daily_return_pct": 1.23, "as_of_date": AXIS[-1]}
    out = summarize_market_position(
        market_context=ctx, kospi_position=pos, regime_streak=None
    )
    assert out["kospi"]["status"] == "ok"
    assert out["kospi"]["daily_return_pct"] == 1.23


# ── 계약 ⑥ 일부 실패 시 실패 블록만 제외 ──────────────────────────────────


def test_kodex_block_survives_stale_kospi():
    ctx = compute_market_context(
        asof=AXIS[-1],
        kodex200_history=_series(AXIS),
        kospi_history=_series(AXIS[:-5]),
    )
    assert ctx["status"] == "partial"
    assert ctx["kodex200"]["status"] == "ok"
    assert ctx["regime_label"] not in (None, "판정불가")
    assert any("stale" in w for w in ctx["warnings"])


def test_kospi_absent_keeps_kodex_block():
    ctx = compute_market_context(
        asof=AXIS[-1], kodex200_history=_series(AXIS), kospi_history=None
    )
    assert ctx["status"] == "partial"
    assert ctx["kodex200"]["status"] == "ok"
    assert ctx["kospi"]["status"] == "unavailable"


# ── 계약 ① 배치가 benchmark 를 갱신하되 롤백하지 않는다 ────────────────────


def test_refresh_benchmarks_reports_each_source_separately(monkeypatch):
    import app.market_benchmark_batch as mod

    monkeypatch.setattr(
        mod,
        "refresh_kospi",
        lambda **kw: {"status": "ok", "as_of_date": "2026-09-07", "error": None},
    )
    monkeypatch.setattr(
        mod,
        "refresh_vix",
        lambda **kw: {"status": "failed", "as_of_date": None, "error": "boom"},
    )
    monkeypatch.setattr(
        mod,
        "refresh_us_index",
        lambda *a, **kw: {"status": "ok", "as_of_date": "2026-09-07", "error": None},
    )
    out = mod.refresh_benchmarks(end_date=date.fromisoformat("2026-09-07"))
    assert out["status"] == "partial", "일부 실패를 ok 로 숨겼다"
    assert out["failed"] == ["vix"]
    assert out["kospi"]["status"] == "ok"
    assert all(r["status"] == "ok" for r in out["us_indices"].values())


def test_refresh_benchmarks_never_raises(monkeypatch):
    """계약 ③ — 예외가 올라가면 배치가 ETF 가격까지 롤백한다."""
    import app.market_benchmark_batch as mod

    def _boom(**kw):
        raise RuntimeError("network down")

    monkeypatch.setattr(mod, "refresh_kospi", _boom)
    monkeypatch.setattr(mod, "refresh_vix", _boom)
    try:
        mod.refresh_benchmarks(end_date=date.fromisoformat("2026-09-07"))
    except Exception as e:  # noqa: BLE001
        raise AssertionError(f"예외가 올라왔다: {type(e).__name__}") from e


def test_refresh_kospi_wraps_store_failure(monkeypatch, tmp_path):
    """store 가 dict 로 돌려준 실패를 그대로 전달한다.

    conftest `_block_live_benchmark_refresh` 를 덮어써야 하므로 **`db_path` 를
    tmp 로 주입**한다 — 라이브 시장 DB 를 건드리지 않기 위해서다.
    """
    import app.market_benchmark_batch as mod
    import app.market_benchmark_store as store

    monkeypatch.setattr(
        store,
        "refresh_kospi_benchmark",
        lambda **kw: {"status": "failed", "error": "fdr down", "rows_written": 0},
    )
    monkeypatch.setattr(store, "latest_benchmark_date", lambda *a, **k: None)

    out = mod.refresh_kospi(
        end_date=date.fromisoformat("2026-09-07"), db_path=tmp_path / "x.sqlite"
    )
    assert out["status"] == "failed"
    assert out["error"] == "fdr down"


def test_conftest_blocks_live_benchmark_write():
    """가드를 고정한다 — **저장 계층**에서 라이브 쓰기를 막아야 한다.

    함수별 가드는 새 갱신 함수가 추가되면 뚫린다. 실제로 `refresh_us_index` 가
    추가됐을 때 라이브 DB 에 썼다.
    """
    import app.market_benchmark_store as store

    try:
        store.upsert_benchmark_prices(
            benchmark_id="TEST",
            benchmark_name="t",
            rows=[("2026-09-07", 1.0)],
            source="x",
        )
    except AssertionError as e:
        assert "라이브 시장 DB" in str(e)
    else:
        raise AssertionError("가드가 라이브 쓰기를 막지 못했다")


def test_conftest_allows_isolated_db_path(tmp_path):
    """`db_path` 를 준 호출은 통과해야 한다 — 그래야 실제 저장 경로를 검사할 수 있다."""
    import app.market_benchmark_store as store

    n = store.upsert_benchmark_prices(
        benchmark_id="TEST",
        benchmark_name="t",
        rows=[("2026-09-07", 1.0)],
        source="x",
        db_path=tmp_path / "x.sqlite",
    )
    assert n == 1


# ── 검증자 r1 A-1 — 배치가 benchmark 실패를 숨기지 않는다 ──────────────────


def test_batch_state_records_benchmark_status_separately(tmp_path):
    from app.three_push_runtime.market_data_batch import (
        read_batch_state,
        write_batch_state,
    )

    p = tmp_path / "batch_state.json"
    write_batch_state(
        status="success_with_benchmark_failure",
        price_data_as_of="2026-09-07",
        artifact_generated_at="2026-09-08T07:20:00Z",
        refresh_date_kst="2026-09-08",
        refresh_completed_at="2026-09-08T07:21:00Z",
        state_path=p,
        price_pipeline_status="success",
        benchmark_status="partial",
        benchmark_failed=["vix"],
        kospi_as_of="2026-09-07",
        vix_as_of=None,
    )
    st = read_batch_state(p)
    assert st["status"] == "success_with_benchmark_failure"
    assert st["price_pipeline_status"] == "success", "ETF 가격 성공이 지워졌다"
    assert (
        st["benchmark_status"] == "partial"
    ), "benchmark 실패가 영구 상태에서 사라졌다"
    assert st["benchmark_failed"] == ["vix"]
    assert st["kospi_as_of"] == "2026-09-07"


def test_guard_does_not_swallow_base_exception(monkeypatch):
    """계약 — 종료 신호(`BaseException`)를 benchmark 실패로 바꾸지 않는다."""
    import app.market_benchmark_batch as mod

    def _kb(**kw):
        raise KeyboardInterrupt()

    monkeypatch.setattr(mod, "refresh_kospi", _kb)
    monkeypatch.setattr(
        mod,
        "refresh_vix",
        lambda **kw: {"status": "ok", "as_of_date": None, "error": None},
    )
    try:
        mod.refresh_benchmarks(end_date=date.fromisoformat("2026-09-07"))
    except KeyboardInterrupt:
        return
    raise AssertionError("KeyboardInterrupt 를 삼켰다")


# ── 검증자 r2 B-6 — 실제 `batch.run()` 종료 분기를 통과시킨다 ──────────────


def _install_batch_success_path(monkeypatch, batch, tmp_path):
    """benchmark 앞 단계를 전부 통과시켜 **종료 분기까지** 도달하게 한다."""
    from app.three_push_runtime import market_data_batch as mdb
    from app.three_push_runtime.market_data_batch import RefreshResult

    monkeypatch.setattr(
        mdb, "MARKET_DATA_BATCH_STATE_PATH", tmp_path / "batch_state.json"
    )
    monkeypatch.setattr(batch, "collect_approved_tickers", lambda: ["069500"])
    monkeypatch.setattr(
        batch,
        "refresh_approved_prices",
        lambda *a, **k: RefreshResult(
            attempted=1, success=1, fail=0, price_data_as_of="2026-09-07"
        ),
    )
    monkeypatch.setattr(
        batch,
        "_build_universe_artifact",
        lambda *, price_data_as_of: (
            {
                "mode": "universe",
                "asof": price_data_as_of,
                "summary": {"refresh_status": "ok"},
                "candidates": [],
            },
            "2026-09-08T07:20:00+00:00",
            "ok",
        ),
    )
    monkeypatch.setattr(
        "app.universe_bootstrap.artifact_validator.validate_artifact",
        lambda *a, **k: (True, None, {}),
    )
    monkeypatch.setattr(
        batch, "evaluate_freshness", lambda **kw: SimpleNamespace(ok=True, reason=None)
    )
    monkeypatch.setattr(
        "app.momentum.universe_mode.save_latest_artifact",
        lambda result: tmp_path / "art.json",
    )
    # POC3-02D-OPS-03 — KRX 단계는 실제 시각으로 시도 시각표를 정하므로(08:10~08:24
    # 대기) 여기서는 대역으로 둔다. KRX 단계 계약은 test_poc3_02d_ops03_krx_* 가 본다.
    monkeypatch.setattr(
        "app.market_briefing.krx_target_sync.sync_krx_target",
        lambda **kw: {"status": "skipped_before_open", "attempts": []},
    )
    return tmp_path / "batch_state.json"


def _run_batch_with_benchmark(monkeypatch, tmp_path, bench_result):
    import scripts.run_oci_market_data_batch as batch

    state_path = _install_batch_success_path(monkeypatch, batch, tmp_path)
    monkeypatch.setattr(
        "app.market_benchmark_batch.refresh_benchmarks", lambda **kw: bench_result
    )
    rec = batch.run(mode="run")
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    return rec, saved


def test_batch_run_marks_benchmark_partial_in_terminal_status(monkeypatch, tmp_path):
    """benchmark 실패가 **배치 종료 status 로 드러나야** 한다 (검증자 r2 A-1)."""
    rec, saved = _run_batch_with_benchmark(
        monkeypatch,
        tmp_path,
        {
            "kospi": {"status": "ok", "as_of_date": "2026-09-07", "error": None},
            "vix": {"status": "failed", "as_of_date": None, "error": "boom"},
            "status": "partial",
            "failed": ["vix"],
        },
    )
    assert rec["status"] == "success_with_benchmark_failure", rec["status"]
    assert "vix" in (rec["reason"] or "")
    # ETF 가격 적재는 롤백되지 않는다.
    assert rec["price_pipeline_status"] == "success"
    assert rec["price_data_as_of"] == "2026-09-07"
    # 영구 상태에도 분리되어 남는다.
    assert saved["status"] == "success_with_benchmark_failure"
    assert saved["price_pipeline_status"] == "success"
    assert saved["benchmark_status"] == "partial"
    assert saved["benchmark_failed"] == ["vix"]
    assert saved["kospi_as_of"] == "2026-09-07"
    assert saved["vix_as_of"] is None


def test_batch_run_stays_success_when_benchmark_ok(monkeypatch, tmp_path):
    rec, saved = _run_batch_with_benchmark(
        monkeypatch,
        tmp_path,
        {
            "kospi": {"status": "ok", "as_of_date": "2026-09-07", "error": None},
            "vix": {"status": "ok", "as_of_date": "2026-09-07", "error": None},
            "status": "ok",
            "failed": [],
        },
    )
    assert rec["status"] == "success"
    assert saved["status"] == "success"
    assert saved["benchmark_status"] == "ok"
    assert saved["benchmark_failed"] == []


def test_batch_run_benchmark_total_failure_is_not_plain_success(monkeypatch, tmp_path):
    rec, saved = _run_batch_with_benchmark(
        monkeypatch,
        tmp_path,
        {
            "kospi": {"status": "failed", "as_of_date": None, "error": "x"},
            "vix": {"status": "failed", "as_of_date": None, "error": "y"},
            "status": "failed",
            "failed": ["kospi", "vix"],
        },
    )
    assert rec["status"] != "success", "benchmark 전면 실패가 success 로 묻혔다"
    assert saved["benchmark_status"] == "failed"
    assert saved["price_pipeline_status"] == "success"


# ── POC3-02D-OPS-01 C7 — 공용 거래일-lag helper 추출 (설계자 Q17) ────────────
#
# `flow._weekday_axis_before` · `_window_lag_trading_days` 본체를
# `app/trading_day_lag.py` 로 옮겼다. 08:00 시장 브리핑 판정이 **옮기기 전과
# 같아야** 한다. 아래 `_legacy_*` 는 옮기기 전 `flow.py:118-165` 본체 사본이다
# (비교 기준 — 운영 코드가 부르지 않는다).


def _legacy_weekday_axis_before(today_kst: str, *, span_days: int) -> list[str]:
    try:
        base = date.fromisoformat(today_kst[:10])
    except ValueError:
        return []
    out = [base - timedelta(days=i) for i in range(span_days, 0, -1)]
    return [d.isoformat() for d in out if d.weekday() < 5]


def _legacy_window_lag_trading_days(latest, *, today_kst, calendar_dir):
    from app.market_briefing.calendar import load_calendar

    try:
        cal = load_calendar(calendar_dir)
    except Exception:  # noqa: BLE001
        cal = None

    if cal is not None and cal.covers(int(today_kst[:4])):
        days = sorted(d for d in cal.days if d < today_kst)
    else:
        days = _legacy_weekday_axis_before(today_kst, span_days=90)

    if not days or latest not in days:
        return None
    return len(days) - 1 - days.index(latest)


def _outcome(fn, *args, **kw):
    """값 또는 예외 종류 — 예외 경로까지 같아야 '동작 동일' 이다."""
    try:
        return ("value", fn(*args, **kw))
    except Exception as e:  # noqa: BLE001
        return ("raise", type(e).__name__)


def test_flow_lag_helper_names_are_bound_to_shared_module():
    """`flow` 의 옛 이름이 공용 helper 를 가리킨다 — 역검증 스크립트
    (`scripts/ops02b2/reverse_verify_guards.py` ②)의 monkeypatch 와 기존 호출이
    그대로 동작한다."""
    from app import trading_day_lag
    from app.market_briefing import flow

    assert flow._window_lag_trading_days is trading_day_lag.window_lag_trading_days
    assert flow._weekday_axis_before is trading_day_lag.weekday_axis_before


def test_shared_lag_helper_matches_legacy_flow_body(tmp_path):
    """옮기기 전 본체와 같은 입력 → 같은 lag (snapshot 축 · 평일 fallback 축)."""
    from app.market_briefing import flow

    cal = tmp_path / "cal"
    cal.mkdir()
    # 추석 연휴(09-24 · 25 · 28)를 뺀 2026-09 거래일 — 평일 fallback 과 갈리는 날.
    (cal / "krx_trading_days_2026.csv").write_text(
        "date\n"
        + "\n".join(
            f"2026-09-{d:02d}"
            for d in (1, 2, 3, 4, 7, 8, 9, 10, 11, 14, 15, 16, 17, 18, 21, 22, 23, 29)
        )
        + "\n",
        encoding="utf-8",
    )
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "krx_trading_days_2026.csv").write_text("nodate\nx\n", encoding="utf-8")
    none_dir = tmp_path / "none"

    cases = [
        # (latest, today_kst, calendar_dir, 기대 lag)
        ("2026-09-23", "2026-09-29", cal, 0),  # snapshot — 연휴 건너뜀
        ("2026-09-22", "2026-09-29", cal, 1),
        ("2026-09-17", "2026-09-29", cal, 4),
        ("2026-09-01", "2026-09-29", cal, 16),
        ("2026-09-24", "2026-09-29", cal, None),  # 휴장일 — 축에 없음
        ("2026-09-29", "2026-09-29", cal, None),  # 기준일 당일은 축에서 뺀다
        ("2026-08-31", "2026-09-29", cal, None),  # snapshot 범위 밖
        ("2026-09-23", "2026-09-29", none_dir, 3),  # 평일 fallback — 연휴 포함
        ("2026-09-23", "2026-09-29", broken, 3),  # 손상 snapshot → 평일 fallback
        ("2027-03-09", "2027-03-10", cal, 0),  # 연도 미지원 → 평일 fallback
        ("2027-03-05", "2027-03-10", cal, 2),
        ("2026-12-01", "2027-03-10", cal, None),  # 90 달력일 축보다 오래됨
        ("2027-03-06", "2027-03-10", cal, None),  # 토요일
        ("2027-03-09", "2027-03-10T08:00:00", none_dir, 0),
        ("2026-09-23", "not-a-date", none_dir, None),  # 평일 축 없음
    ]
    for latest, today, cdir, expected in cases:
        new = _outcome(
            flow._window_lag_trading_days, latest, today_kst=today, calendar_dir=cdir
        )
        old = _outcome(
            _legacy_window_lag_trading_days, latest, today_kst=today, calendar_dir=cdir
        )
        assert new == old, (latest, today, cdir, new, old)
        assert new == ("value", expected), (latest, today, cdir, new)

    # 예외 경로도 같다 — snapshot 이 있을 때 연도를 못 읽는 기준일.
    raise_case = ("2026-09-23", "not-a-date", cal)
    new = _outcome(
        flow._window_lag_trading_days,
        raise_case[0],
        today_kst=raise_case[1],
        calendar_dir=raise_case[2],
    )
    old = _outcome(
        _legacy_window_lag_trading_days,
        raise_case[0],
        today_kst=raise_case[1],
        calendar_dir=raise_case[2],
    )
    assert new == old == ("raise", "ValueError")

    for today, span in (("2026-09-29", 90), ("2027-03-10", 7), ("", 5), ("x", 3)):
        assert flow._weekday_axis_before(
            today, span_days=span
        ) == _legacy_weekday_axis_before(today, span_days=span)


# ── POC3-02D-OPS-01 C7 — 배치 관통: stale KOSPI 가 배치 종료 status 로 드러난다 ──


def test_batch_run_marks_stale_kospi_as_benchmark_failure(monkeypatch, tmp_path):
    """07:20 배치 `run()` 을 **benchmark 조회만 stub** 하고 끝까지 통과시킨다.

    09-18~09-25 실제 사고 재현 — upstream 이 09-17 에서 멈췄는데 배치는
    `kospi=ok(as_of=2026-09-17)` · status success 였다. 감지 정정 A 뒤에는
    `success_with_benchmark_failure` 로 드러나고, ETF 가격 · artifact 는 그대로다.

    - 조회: `FinanceDataReader` 모듈 자리에 가짜를 둔다(VIX · 미국 3종 공용). KOSPI 는
      POC3-02D-OPS-03 자료원 전환(확정 계약 9) — KRX `idx/kospi_dd_trd` 대역.
    - 저장: 실제 `refresh_benchmarks` 를 tmp DB 로 부른다.
    - 축: `calendar.CALENDAR_DIR` 를 합성 snapshot 으로 돌린다.
    """
    import sys

    import pandas as pd

    import app.market_benchmark_batch as bench_mod
    import scripts.run_oci_market_data_batch as batch
    from app.market_benchmark_store import fetch_benchmark_history
    from app.market_briefing import calendar as _cal

    state_path = _install_batch_success_path(monkeypatch, batch, tmp_path)
    saved_artifact = {"n": 0}

    def _save(result):
        saved_artifact["n"] += 1
        return tmp_path / "art.json"

    monkeypatch.setattr("app.momentum.universe_mode.save_latest_artifact", _save)
    monkeypatch.setattr(batch, "_kst_today", lambda: date(2026, 9, 25))

    cal = tmp_path / "market_meta"
    cal.mkdir()
    (cal / "krx_trading_days_2026.csv").write_text(
        "date\n"
        + "\n".join(
            f"2026-09-{d:02d}" for d in (15, 16, 17, 18, 21, 22, 23, 24, 25, 29)
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(_cal, "CALENDAR_DIR", cal)

    def _df(dates):
        return pd.DataFrame(
            {"Close": [100.0 + i for i in range(len(dates))]},
            index=pd.to_datetime(dates),
        )

    calls: list[str] = []

    def _data_reader(symbol, start, end):
        calls.append(symbol)
        return _df(["2026-09-23", "2026-09-24"])

    from app.market_briefing import krx_sync

    def _krx_kospi(bas_dd, key):
        calls.append(f"KRX:{bas_dd}")
        if bas_dd > "20260917":
            return []  # 자료원이 09-17 에서 멈춘 모양
        return [{"BAS_DD": bas_dd, "IDX_NM": "코스피", "CLSPRC_IDX": "2700.00"}]

    monkeypatch.setattr(krx_sync, "_default_kospi_fetcher", _krx_kospi)
    monkeypatch.setattr(krx_sync, "read_api_key", lambda env_path=None: "TEST-KEY")

    monkeypatch.setitem(
        sys.modules,
        "FinanceDataReader",
        SimpleNamespace(DataReader=_data_reader),
    )
    db = tmp_path / "market_data.sqlite"
    real_refresh = bench_mod.refresh_benchmarks
    monkeypatch.setattr(
        bench_mod,
        "refresh_benchmarks",
        lambda **kw: real_refresh(db_path=db, **kw),
    )

    rec = batch.run(mode="run")
    saved = json.loads(state_path.read_text(encoding="utf-8"))

    assert "KS11" not in calls and "VIX" in calls
    assert "KRX:20260917" in calls and "KRX:20260918" in calls
    kospi = rec["benchmark_refresh"]["kospi"]
    assert kospi["status"] == "failed", "멈춘 KOSPI 를 ok 로 숨겼다"
    assert kospi["error"] == (
        "source_stale:as_of=2026-09-17,expected=2026-09-24,lag=5,"
        "reason=no_rows@2026-09-18"
    )
    assert kospi["as_of_date"] == "2026-09-17"
    assert kospi["source"] == "KRX_OPEN_API/idx_kospi_dd_trd"
    assert rec["benchmark_refresh"]["failed"] == ["kospi"]
    assert rec["status"] == "success_with_benchmark_failure", rec["status"]
    assert rec["reason"] == "benchmark_partial:kospi"
    # ETF 가격 · artifact 는 롤백하지 않는다.
    assert rec["price_pipeline_status"] == "success"
    assert saved_artifact["n"] == 1
    assert rec["artifact_path"] == str(tmp_path / "art.json")
    # 적재한 KOSPI 행은 유지된다.
    assert [d for d, _ in fetch_benchmark_history("KOSPI", db_path=db)] == [
        "2026-09-15",
        "2026-09-16",
        "2026-09-17",
    ]
    assert saved["status"] == "success_with_benchmark_failure"
    assert saved["benchmark_failed"] == ["kospi"]
    assert saved["kospi_as_of"] == "2026-09-17"
