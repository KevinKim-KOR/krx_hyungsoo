"""POC5-02 — 가격 결과 성숙(설계서 §8 AC 1 ~ 9 · 설계자 Q-C 정정).

임시 원장(conftest `_isolated_decision_ledger`) · 임시 시장 DB · 임시 캘린더 · 대역 보유/구분만 쓴다.
라이브 state · logs · 운영 DB · 외부 조회 0.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.three_push_runtime import ledger_outcome as lo
from app.three_push_runtime import ledger_store as ls

HOLIDAY = "2026-10-09"  # 한글날(금)


# ── fixture ──────────────────────────────────────────────────────────────────


def _calendar(root: Path) -> Path:
    cal = root / "cal"
    cal.mkdir(parents=True, exist_ok=True)
    d, days = date(2026, 1, 1), []
    while d.year == 2026:
        if d.weekday() < 5 and d.isoformat() != HOLIDAY:
            days.append(d.isoformat())
        d += timedelta(days=1)
    (cal / "krx_trading_days_2026.csv").write_text(
        "date\n" + "\n".join(days) + "\n", "utf-8"
    )
    return cal


def _days_from(start: str, n: int) -> list[str]:
    d, out = date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5 and d.isoformat() != HOLIDAY:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _market_db(root: Path) -> Path:
    p = root / "market.sqlite"
    con = sqlite3.connect(p)
    for t in ("krx_etf_daily_price_unadjusted", "krx_stock_daily_price_unadjusted"):
        con.execute(
            f"CREATE TABLE {t} (date TEXT, ticker TEXT, close REAL, source TEXT,"
            " price_basis TEXT, collected_at TEXT, PRIMARY KEY (date, ticker))"
        )
    con.execute(
        "CREATE TABLE market_benchmark_daily_price (benchmark_id TEXT, benchmark_name"
        " TEXT, date TEXT, close REAL, source TEXT, created_at TEXT,"
        " PRIMARY KEY (benchmark_id, date))"
    )
    # FDR 표 — 성숙은 이 표를 읽으면 안 된다(값을 크게 달리 둔다).
    con.execute("CREATE TABLE etf_daily_price (ticker TEXT, date TEXT, close REAL)")
    con.commit()
    con.close()
    return p


def _prices(db: Path, table: str, ticker: str, rows: dict[str, float]) -> None:
    con = sqlite3.connect(db)
    if table == "kospi":
        con.executemany(
            "INSERT OR REPLACE INTO market_benchmark_daily_price VALUES"
            " ('KOSPI', 'KOSPI', ?, ?, 'KRX', ?)",
            [(d, c, f"{d}T00:00:00Z") for d, c in rows.items()],
        )
    else:
        con.executemany(
            f"INSERT OR REPLACE INTO {table} VALUES (?, ?, ?, 'KRX', 'U', ?)",
            [(d, ticker, c, f"{d}T23:10:00+00:00") for d, c in rows.items()],
        )
        con.executemany(
            "INSERT INTO etf_daily_price VALUES (?, ?, ?)",
            [(ticker, d, c * 10) for d, c in rows.items()],
        )
    con.commit()
    con.close()


_ETF = "krx_etf_daily_price_unadjusted"
_STOCK = "krx_stock_daily_price_unadjusted"


def _item(kind, sid, *, t0=100.0, t0_asof="2026-10-08T10:30:00+09:00", **over):
    row = {
        "subject_kind": kind,
        "subject_id": sid,
        "held": 1 if kind == "ticker" else None,
        "state": None,
        "prev_state": None,
        "disposition": "sent",
        "event_type": None,
        "exposure": None,
        "values_json": "{}",
        "t0_price": t0,
        "t0_price_asof": t0_asof,
        "evaluable": 1,
    }
    row.update(over)
    return row


def _run(eid, items, *, day="2026-10-08", hhmm="10:30", cohort="PRIMARY_LIVE", off=0):
    con = ls.connect()
    try:
        ls.insert_started(
            con,
            {
                "event_id": eid,
                "push_kind": "holdings_risk_alert",
                "runtime_date_kst": day,
                "started_at": f"{day}T{hhmm}:01+09:00",
                "off_schedule": off,
                "schedule_expected": None if off else hhmm,
            },
        )
        ls.finalize(
            con,
            eid,
            {"status": "sent", "cohort": cohort},
            lambda c: list(items),
            {"delivery_status": "sent"},
        )
    finally:
        con.close()


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv(lo.FLAG_ENV, "true")
    cal = _calendar(tmp_path)
    db = _market_db(tmp_path)
    state = {"holdings": ["A", "S"], "kinds": {}, "classify_calls": 0, "hook": None}

    def _holdings():
        if state["holdings"] is None:
            raise LookupError("holdings_missing")
        return [{"ticker": t} for t in state["holdings"]]

    def _classify(tickers, db_path=None):
        state["classify_calls"] += 1
        if state["hook"]:
            state["hook"]()
        return {t: state["kinds"].get(t, ("ETF", "etf_master_csv")) for t in tickers}

    def go(today):
        return lo.run_maturity(
            today_kst=today,
            calendar_dir=cal,
            market_db=db,
            holdings_loader=_holdings,
            classify=_classify,
        )

    return {"db": db, "cal": cal, "go": go, "state": state}


def _outcomes(where="1=1"):
    con = sqlite3.connect(ls.DEFAULT_DB_PATH)
    try:
        return con.execute(
            "SELECT event_id, item_seq, series_id, horizon, status, eval_date,"
            " eval_price, return_raw, max_up_raw, max_down_raw, path_points, t0_price,"
            f" price_basis FROM price_outcome WHERE {where}"
            " ORDER BY event_id, item_seq, series_id, horizon"
        ).fetchall()
    finally:
        con.close()


# ── AC 1 · 2 · 8 날짜 · 계열 ─────────────────────────────────────────────────────


def test_horizon_dates_differ_for_pre_open_intraday_and_close(env):
    """AC 1 — 08:30 · 장중 = 사건일 종가가 +1 · 15:40 CLOSE = 다음 거래일(10-09 휴장 → 10-12)."""
    days = _days_from("2026-10-07", 25)
    _prices(env["db"], _ETF, "A", {d: 100.0 + i for i, d in enumerate(days)})
    _prices(env["db"], "kospi", "KOSPI", {d: 3000.0 + i for i, d in enumerate(days)})
    _run("ev_open", [_item("ticker", "A")], hhmm="10:30")
    _run("ev_close", [_item("ticker", "A")], hhmm="15:40")
    sp = _item("market", "SP500", t0=None, t0_asof=None)
    _run("ev_mkt", [sp], hhmm="08:30")
    env["go"]("2026-11-20")
    got = {(r[0], r[3]): r[5] for r in _outcomes()}
    assert got[("ev_open", 1)] == "2026-10-08"
    assert got[("ev_mkt", 1)] == "2026-10-08"
    assert got[("ev_close", 1)] == "2026-10-12"  # 10-09 휴장(캘린더)
    assert got[("ev_open", 5)] == _days_from("2026-10-08", 5)[-1]
    assert got[("ev_close", 20)] == _days_from("2026-10-12", 20)[-1]


def test_matured_values_are_raw_and_series_are_krx_only(env):
    """AC 2 · 8 — KRX 표 값만(FDR 표 ×10 값이 섞이지 않음) · 원시 소수 · KOSPI t0 = 직전 저장 종가."""
    days = _days_from("2026-10-07", 25)
    _prices(
        env["db"], _ETF, "A", {d: 100.0 for d in days} | {days[1]: 110.0, days[2]: 90.0}
    )
    env["state"]["kinds"]["S"] = ("STOCK", "etf_master_csv+krx_table")
    _prices(env["db"], _STOCK, "S", {d: 50.0 for d in days})
    _prices(env["db"], "kospi", "KOSPI", {d: 3000.0 for d in days} | {days[1]: 3030.0})
    _run("ev_1", [_item("ticker", "A"), _item("ticker", "S", t0=50.0)])
    _run("ev_2", [_item("market", "SP500", t0=None, t0_asof=None)], hhmm="08:30")
    env["go"]("2026-11-20")
    rows = {(r[0], r[2], r[3]): r for r in _outcomes()}
    a5 = rows[("ev_1", "krx_etf:A", 5)]
    assert a5[4] == lo.MATURED and a5[11] == 100.0
    assert a5[8] == pytest.approx(0.10) and a5[9] == pytest.approx(-0.10)
    assert a5[7] == pytest.approx(0.0) and a5[10] == 5
    assert a5[12] == "KRX_ETF_UNADJUSTED|etf_master_csv"
    assert rows[("ev_1", "krx_stock:S", 1)][12].startswith("KRX_STOCK_UNADJUSTED")
    k1 = rows[("ev_2", "benchmark:KOSPI", 1)]
    assert k1[11] == 3000.0  # 10-07 종가(08:30 전에 확정된 직전 값)
    assert k1[7] == pytest.approx(3030.0 / 3000.0 - 1)
    con = sqlite3.connect(ls.DEFAULT_DB_PATH)
    cols = {r[1] for r in con.execute("PRAGMA table_info(price_outcome)")}
    con.close()
    assert not cols & {"hit", "success", "direction", "favorable"}  # 판정 컬럼 0


def test_unknown_class_retries_and_unlisted_stock_is_unsupported(env):
    """Q-A — UNKNOWN 은 행 없음(재시도) · 개별주 표가 지원하지 않는 종목(코스닥 등) = UNSUPPORTED."""
    days = _days_from("2026-10-07", 25)
    _prices(env["db"], _STOCK, "OTHER", {d: 10.0 for d in days})  # 표는 전진했다
    env["state"]["kinds"].update(
        {"U": ("UNKNOWN", None), "Q": ("STOCK", "etf_master_csv+krx_table")}
    )
    _run("ev_1", [_item("ticker", "U"), _item("ticker", "Q")])
    out = env["go"]("2026-11-20")
    rows = _outcomes()
    assert [(r[2], r[4]) for r in rows] == [("unsupported:Q", lo.UNSUPPORTED)] * 3
    assert out["pending"] == 3  # U 의 세 horizon


# ── AC 3 · 4 · 5 · 6 결측 · 반복 ──────────────────────────────────────────────────


def test_repeat_run_does_not_add_or_change_rows(env):
    """AC 3 — 같은 입력을 두 번 돌려도 행 · 값이 같다(INSERT-once)."""
    days = _days_from("2026-10-07", 25)
    _prices(env["db"], _ETF, "A", {d: 100.0 + i for i, d in enumerate(days)})
    _run("ev_1", [_item("ticker", "A")])
    env["go"]("2026-11-20")
    first = _outcomes()
    _prices(env["db"], _ETF, "A", {d: 999.0 for d in days})  # 나중 값이 바뀌어도
    env["go"]("2026-11-21")
    assert _outcomes() == first and len(first) == 3


def test_missing_path_day_is_pending_then_price_missing_after_fill_window(env):
    """AC 4 · Q-C — 중간 날이 빠지면 MATURED 아님 · 채우기 창 안 = 행 없음 · 지나면 PRICE_MISSING."""
    days = _days_from("2026-10-08", 25)
    gap = days[2]
    _prices(env["db"], _ETF, "A", {d: 100.0 for d in days if d != gap})
    _run("ev_1", [_item("ticker", "A")])
    out = env["go"](days[6])  # 창(21거래일) 안
    assert [r[3] for r in _outcomes()] == [1]  # +1 만 성숙 · +5 · +20 은 대기
    assert out["pending"] == 2
    env["go"]("2026-12-15")  # gap 이 21거래일 창을 지난 뒤
    got = {r[3]: (r[4], r[10]) for r in _outcomes()}
    assert got[5] == (lo.PRICE_MISSING, 4) and got[20] == (lo.PRICE_MISSING, 19)
    assert got[1][0] == lo.MATURED


def test_latest_day_delay_stays_pending(env):
    """AC 4 — 최신 평가일 행이 아직 없으면(적재 지연) 행을 쓰지 않는다."""
    days = _days_from("2026-10-08", 3)
    _prices(env["db"], _ETF, "A", {days[0]: 100.0})
    _run("ev_1", [_item("ticker", "A")])
    env["go"](days[2])
    assert [r[3] for r in _outcomes()] == [1]


def test_untracked_after_exit_differs_from_missing(env):
    """AC 5 — 매도 뒤 끊긴 개별주 = UNTRACKED_AFTER_EXIT · 보유 중 결측은 창 안이면 대기."""
    days = _days_from("2026-10-08", 25)
    env["state"]["kinds"].update(
        {
            "S": ("STOCK", "etf_master_csv+krx_table"),
            "K": ("STOCK", "etf_master_csv+krx_table"),
        }
    )
    _prices(env["db"], _ETF, "AXIS", {d: 1.0 for d in days})  # 공통 축 전진
    _prices(env["db"], _STOCK, "S", {d: 50.0 for d in days[:2]})  # 2일 뒤 매도
    _prices(env["db"], _STOCK, "K", {d: 50.0 for d in days[:2]})  # 보유 중 결측
    env["state"]["holdings"] = ["K"]
    _run("ev_1", [_item("ticker", "S", t0=50.0), _item("ticker", "K", t0=50.0)])
    env["go"](days[8])
    got = {(r[2], r[3]): r[4] for r in _outcomes()}
    assert got[("krx_stock:S", 1)] == lo.MATURED
    assert got[("krx_stock:S", 5)] == lo.UNTRACKED_AFTER_EXIT
    assert ("krx_stock:K", 5) not in got  # 보유 중 · 31거래일 창 안 = 대기


def test_t0_missing_is_not_replaced(env):
    """AC 6 — t0 없음 = T0_MISSING(종가로 대체 0) · KOSPI 직전 종가가 없어도 같다."""
    days = _days_from("2026-10-08", 25)
    _prices(env["db"], _ETF, "A", {d: 100.0 for d in days})
    _prices(env["db"], "kospi", "KOSPI", {d: 3000.0 for d in days})  # 10-07 행 없음
    _run("ev_1", [_item("ticker", "A", t0=None, t0_asof=None)])
    _run("ev_2", [_item("market", "SP500", t0=None, t0_asof=None)], hhmm="08:30")
    env["go"]("2026-11-20")
    rows = _outcomes()
    assert {r[4] for r in rows} == {lo.T0_MISSING} and len(rows) == 6
    assert all(r[11] is None and r[6] is None for r in rows)


# ── AC 7 대상 ────────────────────────────────────────────────────────────────


def test_targets_include_all_dispositions_and_exclude_unevaluable_and_legacy(env):
    """AC 7 — sent · suppressed · cut · not_selected 포함 · evaluable 0 · LEGACY · 예정 밖 · 구역 행 제외."""
    days = _days_from("2026-10-07", 25)
    for t in ("A", "B", "C", "D", "E", "X1", "X2", "R"):
        _prices(env["db"], _ETF, t, {d: 100.0 for d in days})
    items = [
        _item("ticker", "A", disposition="sent"),
        _item("ticker", "B", disposition="suppressed"),
        _item("ticker", "C", disposition="cut_by_section_cap"),
        _item("ticker", "D", disposition="not_selected"),
        _item("ticker", "E", disposition="data_unavailable", evaluable=0),
        _item("sector", "반도체", values_json=json.dumps({"ticker": "R"})),
        _item(
            "index_group",
            "A|IDX",
            t0=None,
            t0_asof=None,
            values_json=json.dumps({"tickers": ["X1", "X2"], "price_asof": days[0]}),
        ),
        _item("index_block", "KR_INDEX", t0=None, t0_asof=None),
    ]
    _run("ev_1", items)
    _run("ev_legacy", [_item("ticker", "A")], cohort="LEGACY_DIAGNOSTIC")
    _run("ev_manual", [_item("ticker", "A")], hhmm="10:47", off=1)
    env["go"]("2026-11-20")
    series = sorted({(r[0], r[2]) for r in _outcomes()})
    assert series == [
        ("ev_1", s)
        for s in sorted(
            [
                "krx_etf:A",
                "krx_etf:B",
                "krx_etf:C",
                "krx_etf:D",
                "krx_etf:R",
                "krx_etf:X1",
                "krx_etf:X2",
            ]
        )
    ]
    x1 = [r for r in _outcomes() if r[2] == "krx_etf:X1"][0]
    assert x1[11] == 100.0  # 기초지수 ticker t0 = price_asof 종가


# ── AC 9 · 게이트 · 배치 격리 ─────────────────────────────────────────────────


def test_gates_never_create_ledger_files(tmp_path, monkeypatch):
    """플래그 없음 · 원장 파일 없음 → 원장 파일 · 폴더 생성 0."""
    assert lo.run_maturity()["status"] == "disabled"
    monkeypatch.setenv(lo.FLAG_ENV, "true")
    assert lo.run_maturity()["status"] == "no_ledger"
    assert not ls.DEFAULT_DB_PATH.exists() and not ls.DEFAULT_DB_PATH.parent.exists()


def test_flag_is_read_from_env_file_when_environment_lacks_it(tmp_path):
    """배치는 .env 를 환경변수로 올리지 않는다 — 이 한 키만 파일에서 읽는다."""
    env_file = tmp_path / ".env"
    env_file.write_text("KRX_API_KEY=secret\n\nDECISION_LEDGER_ENABLED=true\n", "utf-8")
    assert lo.flag_enabled(env_file) is True
    env_file.write_text("DECISION_LEDGER_ENABLED=false\n", "utf-8")
    assert lo.flag_enabled(env_file) is False
    assert lo.flag_enabled(tmp_path / "none.env") is False


@pytest.mark.parametrize(
    "argv, called",
    [(["--krx-only"], 1), ([], 1), (["--dry-run"], 0)],
)
@pytest.mark.parametrize("fail", [False, True])
def test_batch_main_output_and_exit_code_unchanged_by_maturity(
    monkeypatch, capsys, argv, called, fail
):
    """AC 9 — 성숙 실패를 넣어도 stdout · exit code 같음 · dry-run 은 성숙 0."""
    from scripts import run_oci_market_data_batch as batch

    calls = []

    def _maturity(**_kw):
        calls.append(1)
        if fail:
            raise RuntimeError("maturity bug")
        return {"status": "ok"}

    monkeypatch.setattr(lo, "run_maturity", _maturity)
    monkeypatch.setattr(batch, "run_krx_only", lambda: {"status": "ok", "x": 1})
    monkeypatch.setattr(batch, "run", lambda mode: {"status": "success", "mode": mode})
    monkeypatch.setattr(sys, "argv", ["run_oci_market_data_batch.py", *argv])
    with pytest.raises(SystemExit) as ei:
        batch.main()
    out = capsys.readouterr().out
    assert ei.value.code == 0
    assert json.loads(out)["status"] in ("ok", "success")
    assert len(calls) == called


def test_reconcile_cli_legacy_is_optional(tmp_path, capsys):
    """Q-D — `--legacy` 를 줄 때만 cohort · 연결 · 원장 이전 runtime 건수를 더 출력한다."""
    from scripts import run_decision_ledger_reconcile as cli

    _run("ev_1", [], cohort="PRIMARY_LIVE")
    _run("ev_2", [], cohort="LEGACY_DIAGNOSTIC", off=1, hhmm="10:47")
    con = ls.connect()
    ls.meta_put_once(con, "first_active_at", "2026-10-08T10:30:01+09:00")
    con.close()
    rt = tmp_path / "rt.sqlite"
    c = sqlite3.connect(rt)
    c.execute(
        "CREATE TABLE runtime_execution_status (run_id INTEGER, push_kind TEXT,"
        " started_at TEXT, mode TEXT)"
    )
    c.execute(
        "INSERT INTO runtime_execution_status VALUES"
        " (1, 'holdings_risk_alert', '2026-10-07T10:30:01+09:00', 'send')"
    )
    c.commit()
    c.close()
    args = ["--ledger", str(ls.DEFAULT_DB_PATH), "--runtime", str(rt)]
    assert cli.main(args) == 0
    plain = capsys.readouterr().out
    assert "legacy" not in plain
    assert cli.main([*args, "--legacy"]) == 0
    out = capsys.readouterr().out
    assert out.startswith(plain)
    assert "legacy cohort=LEGACY_DIAGNOSTIC kind=holdings_risk_alert runs=1" in out
    assert "legacy runtime_send_before_ledger kind=holdings_risk_alert runs=1" in out


# ── 검토 반영(2026-10-07) — 채우기 창 · KOSPI · 값 · 매도 · 보유 · 격리 · 성능 ─────────────


def _status(eid, series, h):
    got = [r[4] for r in _outcomes() if (r[0], r[2], r[3]) == (eid, series, h)]
    return got[0] if got else None


@pytest.mark.parametrize("table, window", [(_ETF, 21), (_STOCK, 31)])
def test_fill_window_boundary_decides_price_missing(env, table, window):
    """Q-C — 빠진 날이 창 첫날이면 대기 · 하루 지나면 PRICE_MISSING(ETF 21 · 개별주 31)."""
    days = _days_from("2026-10-08", window + 5)  # days[0] 이 빠진 날
    ticker = "A" if table == _ETF else "S"
    if table == _STOCK:
        env["state"]["kinds"]["S"] = ("STOCK", "etf_master_csv+krx_table")
    _prices(env["db"], table, ticker, {d: 100.0 for d in days[1:]})
    _run("ev_1", [_item("ticker", ticker)])
    series = f"{'krx_etf' if table == _ETF else 'krx_stock'}:{ticker}"
    env["go"](days[window])  # 창 첫날 = gap
    assert _status("ev_1", series, 1) is None
    env["go"](days[window + 1])
    assert _status("ev_1", series, 1) == lo.PRICE_MISSING


def test_kospi_gap_needs_a_later_stored_day(env):
    """KOSPI 는 채우기가 없다 — 빠진 날 뒤 날짜가 저장돼야 확정 · 미래 평가일이 남으면 대기."""
    days = _days_from("2026-10-07", 8)  # 10-07 = t0 날
    _prices(
        env["db"], "kospi", "KOSPI", {d: 3000.0 for d in days[:3]}
    )  # 10-07 · 08 · 12
    _run("ev_1", [_item("market", "SP500", t0=None, t0_asof=None)], hhmm="08:30")
    env["go"]("2026-12-01")
    assert _status("ev_1", "benchmark:KOSPI", 5) is None  # 뒤 날짜 없음
    _prices(
        env["db"], "kospi", "KOSPI", {days[4]: 3000.0}
    )  # days[3] 결측 · days[5] 미저장
    env["go"]("2026-12-01")
    assert _status("ev_1", "benchmark:KOSPI", 5) is None  # 평가일(days[5])이 아직 없음
    _prices(env["db"], "kospi", "KOSPI", {days[5]: 3000.0})
    env["go"]("2026-12-01")
    assert _status("ev_1", "benchmark:KOSPI", 5) == lo.PRICE_MISSING


def test_close_event_value_columns(env):
    """15:40 사건 — 사건일 · 직전일 종가 · 평가일 수집 시각 · 평가일이 최저면 max_down = 평가일."""
    days = _days_from("2026-10-07", 8)  # 10-07 · 08 · 12 ...
    closes = {days[0]: 95.0, days[1]: 101.0, days[2]: 103.0, days[3]: 104.0}
    closes.update({days[4]: 102.0, days[5]: 98.0, days[6]: 90.0})
    _prices(env["db"], _ETF, "A", closes)
    _prices(env["db"], "kospi", "KOSPI", {days[0]: 2990.0, days[1]: 3000.0})
    _run("ev_1", [_item("ticker", "A", t0=100.0)], hhmm="15:40")  # 10-08 15:40
    _run("ev_2", [_item("market", "SP500", t0=None, t0_asof=None)], hhmm="08:30")
    env["go"]("2026-12-01")
    con = sqlite3.connect(ls.DEFAULT_DB_PATH)
    row = con.execute(
        "SELECT signal_date_close, previous_close, eval_date, source_collected_at,"
        " max_down_raw, t0_price_asof FROM price_outcome"
        " WHERE event_id = 'ev_1' AND horizon = 5"
    ).fetchone()
    k = con.execute(
        "SELECT t0_price, t0_price_asof FROM price_outcome"
        " WHERE event_id = 'ev_2' AND horizon = 1"
    ).fetchone()
    con.close()
    assert row[0] == 101.0 and row[1] == 95.0  # 10-08 종가 · 10-07 종가
    assert row[2] == days[6] and row[3] == f"{days[6]}T23:10:00+00:00"
    assert row[4] == pytest.approx(-0.10)  # 평가일 90 이 최저
    assert row[5] == "2026-10-08T10:30:00+09:00"
    assert k == (2990.0, "2026-10-07")


def test_untracked_needs_axis_past_eval_date_and_break_after_last_row(env):
    """매도 판정 대조군 — ETF 축이 평가일 전이면 대기 · 매도 전 결측(뒤에 행 있음)은 매도가 아님."""
    days = _days_from("2026-10-08", 30)
    env["state"]["kinds"].update(
        {k: ("STOCK", "etf_master_csv+krx_table") for k in ("S", "T")}
    )
    env["state"]["holdings"] = []
    _prices(env["db"], _ETF, "AXIS", {d: 1.0 for d in days[:3]})  # 축은 days[2] 까지
    _prices(env["db"], _STOCK, "S", {d: 50.0 for d in days[:2]})
    _prices(
        env["db"], _STOCK, "T", {days[0]: 50.0, days[2]: 50.0}
    )  # days[1] 결측 뒤 행
    _run("ev_1", [_item("ticker", "S", t0=50.0), _item("ticker", "T", t0=50.0)])
    env["go"](days[3])
    assert _status("ev_1", "krx_stock:S", 5) is None  # 축이 평가일(days[4]) 전
    assert _status("ev_1", "krx_stock:T", 5) is None  # 마지막 행이 결측 뒤 = 매도 아님
    _prices(env["db"], _ETF, "AXIS", {d: 1.0 for d in days})
    env["go"](days[6])
    assert _status("ev_1", "krx_stock:S", 5) == lo.UNTRACKED_AFTER_EXIT


def test_unknown_holdings_never_mark_untracked(env, tmp_path, monkeypatch):
    """보유 파일 없음 · 손상 = 모름 → 미추적 판정 0(빈 보유와 구분 · 개별주 곁 작업과 같은 구분)."""
    from app import holdings
    from app.market_briefing import krx_stock_sync as kss
    from app.three_push_runtime import ledger_outcome_prices as px

    monkeypatch.setattr(holdings, "HOLDINGS_FILE", tmp_path / "missing.json")
    assert px.current_holdings() is None  # 파일 없음 = 모름(빈 보유 아님)
    monkeypatch.setattr(
        kss, "holdings_tickers", lambda: (None, "holdings_unreadable:X")
    )
    assert px.current_holdings() is None
    monkeypatch.setattr(kss, "holdings_tickers", lambda: (None, kss.STATUS_NO_HOLDINGS))
    assert px.current_holdings() == set()  # 보유 0 은 빈 집합
    monkeypatch.setattr(kss, "holdings_tickers", lambda: (["S"], None))
    assert px.current_holdings() == {"S"}
    days = _days_from("2026-10-08", 30)
    env["state"]["kinds"]["S"] = ("STOCK", "etf_master_csv+krx_table")
    env["state"]["holdings"] = None  # 로더가 모름을 알림
    _prices(env["db"], _ETF, "AXIS", {d: 1.0 for d in days})
    _prices(env["db"], _STOCK, "S", {d: 50.0 for d in days[:2]})
    _run("ev_1", [_item("ticker", "S", t0=50.0)])
    env["go"](days[8])
    assert _status("ev_1", "krx_stock:S", 5) is None


def test_unlisted_stock_is_unsupported_after_window_even_if_table_stalls(env):
    """코스피 개별주를 하나도 안 갖고 있어 표가 멈춰도, 채우기 창이 지나면 UNSUPPORTED."""
    days = _days_from("2026-10-08", 40)
    env["state"]["kinds"]["Q"] = ("STOCK", "etf_master_csv+krx_table")
    _run("ev_1", [_item("ticker", "Q")])
    env["go"](days[31])  # 개별주 창 첫날 = 10-08 → 아직 대기
    assert _outcomes() == []
    env["go"](days[32])
    assert [r[4] for r in _outcomes()] == [lo.UNSUPPORTED] * 3


def test_market_db_is_read_only(env, tmp_path):
    """시장 DB 는 mode=ro — 실행 전후 파일 · 스키마가 같고, 없는 경로면 만들지 않는다."""
    import hashlib

    days = _days_from("2026-10-07", 25)
    _prices(env["db"], _ETF, "A", {d: 100.0 for d in days})
    _run("ev_1", [_item("ticker", "A")])
    before = hashlib.sha256(env["db"].read_bytes()).hexdigest()
    env["go"]("2026-11-20")
    assert hashlib.sha256(env["db"].read_bytes()).hexdigest() == before
    missing = tmp_path / "nope.sqlite"
    _run(
        "ev_2", [_item("ticker", "A")]
    )  # 아직 계산 안 된 대상이 있어야 시장 DB 를 연다
    with pytest.raises(FileNotFoundError):
        lo.run_maturity(
            today_kst="2026-11-21",
            calendar_dir=env["cal"],
            market_db=missing,
            classify=lambda t, db_path=None: {},
        )
    assert not missing.exists()


def test_no_ledger_write_lock_during_compute_and_insert_ignores(env):
    """계산 중에는 원장 쓰기 잠금이 없고, 이미 있는 키는 덮어쓰지 않는다(INSERT OR IGNORE)."""
    days = _days_from("2026-10-07", 25)
    _prices(env["db"], _ETF, "A", {d: 100.0 for d in days})
    _run("ev_1", [_item("ticker", "A")])

    def _probe():
        c = sqlite3.connect(ls.DEFAULT_DB_PATH, timeout=0)
        c.execute("BEGIN IMMEDIATE")  # 잠금을 쥔 연결이 있으면 여기서 실패한다
        c.execute(
            "INSERT INTO price_outcome (event_id, item_seq, series_id, horizon,"
            " status, computed_at) VALUES ('ev_1', 1, 'krx_etf:A', 1, 'SENTINEL', 'x')"
        )
        c.execute("COMMIT")
        c.close()

    env["state"]["hook"] = _probe
    env["go"]("2026-11-20")
    assert _status("ev_1", "krx_etf:A", 1) == "SENTINEL"
    assert _status("ev_1", "krx_etf:A", 5) == lo.MATURED


def test_calendar_is_read_once_and_done_items_are_skipped(env, monkeypatch):
    """성능 — 실행 한 번에 캘린더 1회 · 끝난 item 은 다음 실행에서 계산하지 않는다."""
    from app import trading_day_lag

    days = _days_from("2026-10-07", 25)
    for t in ("A", "B", "C"):
        _prices(env["db"], _ETF, t, {d: 100.0 for d in days})
    _run("ev_1", [_item("ticker", t) for t in ("A", "B", "C")])
    real, calls = trading_day_lag.load_calendar, []
    monkeypatch.setattr(
        trading_day_lag,
        "load_calendar",
        lambda *a, **k: calls.append(1) or real(*a, **k),
    )
    env["go"]("2026-11-20")
    assert len(calls) == 1
    out = env["go"]("2026-11-21")
    assert out["targets"] == 0 and env["state"]["classify_calls"] == 1


def test_flag_reading_does_not_leak_other_env_keys(tmp_path, monkeypatch):
    """.env 에서 플래그 한 키만 본다 — 다른 키는 환경변수로 올리지 않는다."""
    monkeypatch.delenv("KRX_API_KEY", raising=False)
    import os

    keys = set(os.environ)
    f = tmp_path / ".env"
    f.write_text("KRX_API_KEY=secret\nDECISION_LEDGER_ENABLED=true\n", "utf-8")
    assert lo.flag_enabled(f) is True
    assert set(os.environ) == keys


def test_batch_maturity_import_failure_and_skipped_day(monkeypatch, capsys):
    """import 실패도 격리 · 09:20 skipped 날에도 성숙 · 성숙은 결과 출력 뒤."""
    from scripts import run_oci_market_data_batch as batch

    monkeypatch.setattr(
        batch, "run_krx_only", lambda: {"status": "skipped_already_ran_today"}
    )
    monkeypatch.setattr(sys, "argv", ["run_oci_market_data_batch.py", "--krx-only"])
    seen = []

    def _maturity(**_kw):
        seen.append(capsys.readouterr().out)  # 이 시점에 JSON 이 이미 출력됐다
        return {"status": "ok"}

    monkeypatch.setattr(lo, "run_maturity", _maturity)
    with pytest.raises(SystemExit) as ei:
        batch.main()
    assert (
        ei.value.code == 1
        and json.loads(seen[0])["status"] == "skipped_already_ran_today"
    )
    monkeypatch.setitem(sys.modules, "app.three_push_runtime.ledger_outcome", None)
    with pytest.raises(SystemExit) as ei:
        batch.main()
    assert ei.value.code == 1
    assert json.loads(capsys.readouterr().out)["status"] == "skipped_already_ran_today"


def test_legacy_summary_is_read_only(tmp_path):
    """Q-D — `--legacy` 실행 전후 원장 · runtime 파일이 같다."""
    import hashlib

    from scripts import run_decision_ledger_reconcile as cli

    _run("ev_1", [])
    rt = tmp_path / "rt.sqlite"
    c = sqlite3.connect(rt)
    c.execute(
        "CREATE TABLE runtime_execution_status (run_id INTEGER, push_kind TEXT,"
        " started_at TEXT, mode TEXT)"
    )
    c.commit()
    c.close()
    files = [ls.DEFAULT_DB_PATH, rt]
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in files]
    assert cli.main(["--ledger", str(files[0]), "--runtime", str(rt), "--legacy"]) == 0
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in files] == before
