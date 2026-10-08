"""POC5-05 개정 2 — '시장 흐름 보기' 읽기 전용 조회(설계 §8 · §11-1 Q-B · PLAN §2-7).

임시 시세 DB(tmp sqlite · 기존 DDL) · 임시 캘린더 CSV 만 쓴다. 라이브 state · DB · 외부 조회 0.
"""

from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app import holdings_market_flow as mf
from app.market_benchmark_store import MARKET_BENCHMARK_DAILY_PRICE_DDL
from app.market_data_store import ETF_DAILY_PRICE_DDL, ETF_MASTER_DDL
from app.three_push_runtime import ledger_outcome_prices as lop

HOLIDAYS = {"2026-01-01", "2026-10-09"}  # 신정 · 한글날(금)
ETF = "069500"
STOCK = "005930"
FDR = "FinanceDataReader"
NAVER = "NAVER_FDR"
KRX_KOSPI = "KRX_OPEN_API/idx_kospi_dd_trd"


# ── fixture ──────────────────────────────────────────────────────────────────


def _calendar(root: Path) -> Path:
    """2026 연도 파일만 — 2025 는 평일 기본으로 판정된다."""
    cal = root / "cal"
    cal.mkdir(parents=True, exist_ok=True)
    d, days = date(2026, 1, 1), []
    while d.year == 2026:
        if d.weekday() < 5 and d.isoformat() not in HOLIDAYS:
            days.append(d.isoformat())
        d += timedelta(days=1)
    (cal / "krx_trading_days_2026.csv").write_text(
        "date\n" + "\n".join(days) + "\n", "utf-8"
    )
    return cal


def _db(root: Path, *, master: bool = True, etf: bool = True, market: bool = True):
    p = root / "market.sqlite"
    con = sqlite3.connect(p)
    if master:
        con.execute(ETF_MASTER_DDL)
        con.execute(
            "INSERT INTO etf_master (ticker, name, source, last_seen_at)"
            " VALUES (?, 'KODEX 200', 'FDR', '2026-10-01')",
            (ETF,),
        )
    if etf:
        con.execute(ETF_DAILY_PRICE_DDL)
    if market:
        con.execute(MARKET_BENCHMARK_DAILY_PRICE_DDL)
    # KRX 무조정 표 — 시장 흐름은 이 표를 읽으면 안 된다(값을 크게 달리 둔다).
    con.execute(
        "CREATE TABLE krx_etf_daily_price_unadjusted (date TEXT, ticker TEXT,"
        " close REAL, source TEXT, price_basis TEXT, collected_at TEXT)"
    )
    con.commit()
    con.close()
    return p


def _etf(db: Path, ticker: str, rows: dict[str, tuple[float, str]]) -> None:
    con = sqlite3.connect(db)
    con.executemany(
        "INSERT OR REPLACE INTO etf_daily_price (ticker, date, close, source,"
        " fetched_at) VALUES (?, ?, ?, ?, '2026-10-08T00:00:00Z')",
        [(ticker, d, c, s) for d, (c, s) in rows.items()],
    )
    con.executemany(
        "INSERT INTO krx_etf_daily_price_unadjusted VALUES (?, ?, ?, 'KRX', 'U', 'x')",
        [(d, ticker, c * 7) for d, (c, _) in rows.items()],
    )
    con.commit()
    con.close()


def _kospi(db: Path, rows: dict[str, tuple[float, str]]) -> None:
    con = sqlite3.connect(db)
    con.executemany(
        "INSERT OR REPLACE INTO market_benchmark_daily_price VALUES"
        " ('KOSPI', 'KOSPI', ?, ?, ?, '2026-10-08T00:00:00Z')",
        [(d, c, s) for d, (c, s) in rows.items()],
    )
    con.commit()
    con.close()


def _cycle(opened_by: str, status: str, *events: tuple[str, str, str]) -> dict:
    return {
        "cycle_id": "cyc-1",
        "opened_by": opened_by,
        "status": status,
        "events": [{"record_id": r, "kind": k, "trade_date": d} for r, k, d in events],
    }


@pytest.fixture
def env(tmp_path):
    return {"db": _db(tmp_path), "cal": _calendar(tmp_path)}


def _run(env, cycle, ticker=ETF):
    return mf.build_market_flow(
        ticker=ticker, cycle=cycle, db_path=env["db"], calendar_dir=env["cal"]
    )


# ── ETF 정상 · 기준일 ─────────────────────────────────────────────────────────


def test_trading_day_buy_to_latest_stored_with_kospi(env):
    _etf(
        env["db"],
        ETF,
        {
            "2026-10-05": (10000.0, FDR),
            "2026-10-06": (10500.0, FDR),
            "2026-10-08": (11000.0, FDR),
            "2026-10-12": (0.0, FDR),  # close 0 은 마지막 저장일이 아니다
        },
    )
    _kospi(
        env["db"],
        {"2026-10-05": (2000.0, KRX_KOSPI), "2026-10-08": (2100.0, KRX_KOSPI)},
    )
    out = _run(env, _cycle("BUY", "OPEN", ("r1", "BUY", "2026-10-05")))

    assert out["asset_kind"] == "ETF" and out["db_present"] is True
    assert out["latest_stored_date"] == "2026-10-08"
    assert out["latest_stored_close"] == 11000.0
    assert out["latest_stored_source"] == FDR
    ev = out["events"][0]
    assert (
        ev["record_id"] == "r1" and ev["window_label"] == "매수 기준일 → 마지막 저장일"
    )
    assert ev["basis"]["basis_date"] == "2026-10-05"
    assert ev["basis"]["moved_to_next_trading_day"] is False
    assert ev["basis"]["trade_date_decided_by"] == "snapshot"
    t = ev["ticker"]
    assert t["status"] == mf.STATUS_OK and t["reason"] is None
    assert t["table"] == "etf_daily_price" and t["series_name"] == "ETF 저장 종가"
    assert t["start"] == {"date": "2026-10-05", "close": 10000.0, "source": FDR}
    assert t["end"] == {"date": "2026-10-08", "close": 11000.0, "source": FDR}
    assert Decimal(t["change_pct"]) == Decimal("10")  # 무조정 표(×7)를 읽지 않았다
    assert t["source_differs"] is False
    m = ev["market"]
    assert m["status"] == mf.STATUS_OK and m["table"] == "market_benchmark_daily_price"
    assert (m["start_date"], m["end_date"]) == ("2026-10-05", "2026-10-08")
    assert Decimal(m["change_pct"]) == Decimal("5")
    # 열린 실제 매수 기간 — 보유 기간 항목은 아직 계산하지 않는다.
    assert out["holding_period"]["computed"] is False
    assert out["holding_period"]["reason_code"] == "CYCLE_OPEN"
    assert out["purchase_date_unknown"] is False
    assert out["series"]["ticker"]["table"] == "etf_daily_price"
    assert out["series"]["market"]["benchmark_id"] == "KOSPI"
    assert out["free_commentary"] is None
    json.dumps(out, ensure_ascii=False)  # 직렬화 가능


def test_holiday_trade_uses_next_trading_day_with_rule(env):
    _etf(
        env["db"],
        ETF,
        {
            "2026-10-08": (9000.0, FDR),  # 휴장 전날 — 기준일로 쓰면 안 된다
            "2026-10-12": (10000.0, FDR),
            "2026-10-14": (12000.0, FDR),
        },
    )
    _kospi(
        env["db"],
        {"2026-10-12": (2000.0, KRX_KOSPI), "2026-10-14": (2200.0, KRX_KOSPI)},
    )
    out = _run(
        env,
        _cycle(
            "BUY",
            "OPEN",
            ("r1", "BUY", "2026-10-09"),  # 한글날(연도 파일 휴장)
            ("r2", "BUY", "2026-10-10"),  # 토요일
        ),
    )
    for ev in out["events"]:
        b = ev["basis"]
        assert b["basis_date"] == "2026-10-12"
        assert b["moved_to_next_trading_day"] is True
        assert b["trade_date_is_trading_day"] is False
        assert b["trade_date_decided_by"] == "snapshot"
        assert b["basis_date_decided_by"] == "snapshot"
        assert b["basis_note"] == "비거래일(연도 파일) → 다음 거래일(연도 파일)"
        assert ev["ticker"]["start"]["date"] == "2026-10-12"
        assert Decimal(ev["ticker"]["change_pct"]) == Decimal("20")
        assert Decimal(ev["market"]["change_pct"]) == Decimal("10")


def test_basis_rule_reports_weekday_fallback_year(env):
    """연도 파일이 없는 해(2025)는 평일 기본 — 12-31 휴장 → 다음 거래일은 2026 연도 파일."""
    _etf(
        env["db"], ETF, {"2026-01-02": (10000.0, NAVER), "2026-01-05": (10100.0, NAVER)}
    )
    out = _run(env, _cycle("BUY", "OPEN", ("r1", "BUY", "2025-12-31")))
    b = out["events"][0]["basis"]
    assert b["basis_date"] == "2026-01-02"  # 2026-01-01 은 연도 파일에 없다
    assert b["trade_date_decided_by"] == "weekday_fallback"
    assert b["basis_date_decided_by"] == "snapshot"
    assert b["basis_note"] == "비거래일(평일 기본) → 다음 거래일(연도 파일)"
    assert Decimal(out["events"][0]["ticker"]["change_pct"]) == Decimal("1")


def test_basis_row_missing_is_no_data_without_adjacent_fill(env):
    _etf(
        env["db"],
        ETF,
        {
            "2026-10-05": (10000.0, FDR),
            "2026-10-07": (10200.0, FDR),
            "2026-10-08": (11000.0, FDR),
        },
    )
    out = _run(env, _cycle("BUY", "OPEN", ("r1", "BUY", "2026-10-06")))
    t = out["events"][0]["ticker"]
    assert t["status"] == mf.STATUS_NO_DATA
    assert t["reason_code"] == "BASIS_ROW_MISSING"
    assert t["reason"] == "자료 없음(기준일 종가 없음 · 인접일 대체 안 함)"
    assert t["start"] is None and t["change_pct"] is None
    assert t["start_date"] == "2026-10-06"
    assert "10000.0" not in json.dumps(out) and "10200.0" not in json.dumps(out)


def test_latest_stored_before_basis_has_no_change(env):
    _etf(env["db"], ETF, {"2026-10-01": (10000.0, FDR), "2026-10-02": (10100.0, FDR)})
    _kospi(
        env["db"],
        {"2026-10-02": (2000.0, KRX_KOSPI), "2026-10-08": (2100.0, KRX_KOSPI)},
    )
    out = _run(env, _cycle("BUY", "OPEN", ("r1", "SELL", "2026-10-08")))
    ev = out["events"][0]
    assert ev["window_label"] == "매도 기준일 → 마지막 저장일"
    assert ev["latest_stored_date"] == "2026-10-02"
    t = ev["ticker"]
    assert t["status"] == mf.STATUS_NO_DATA
    assert t["reason_code"] == "LATEST_BEFORE_BASIS"
    assert t["change_pct"] is None
    assert t["end"]["date"] == "2026-10-02"
    # KOSPI 는 종목과 같은 두 날짜만 — 종목 구간이 없으면 계산하지 않는다.
    assert ev["market"]["status"] == mf.STATUS_NO_DATA
    assert ev["market"]["reason_code"] == "NO_WINDOW"
    assert ev["market"]["change_pct"] is None


def test_kospi_needs_both_ends(env):
    _etf(env["db"], ETF, {"2026-10-05": (10000.0, FDR), "2026-10-08": (11000.0, FDR)})
    _kospi(
        env["db"],
        {"2026-10-05": (2000.0, KRX_KOSPI), "2026-10-07": (2050.0, KRX_KOSPI)},
    )
    out = _run(env, _cycle("BUY", "OPEN", ("r1", "BUY", "2026-10-05")))
    m = out["events"][0]["market"]
    assert out["events"][0]["ticker"]["status"] == mf.STATUS_OK
    assert m["status"] == mf.STATUS_NO_DATA and m["reason_code"] == "END_ROW_MISSING"
    assert m["end"] is None and m["change_pct"] is None


# ── 출처 ─────────────────────────────────────────────────────────────────────


def test_fdr_naver_source_differs_is_ok_with_flag(env):
    _etf(env["db"], ETF, {"2026-03-03": (10000.0, NAVER), "2026-10-08": (12500.0, FDR)})
    _kospi(
        env["db"], {"2026-03-03": (2000.0, NAVER), "2026-10-08": (3000.0, KRX_KOSPI)}
    )
    out = _run(env, _cycle("BUY", "OPEN", ("r1", "BUY", "2026-03-03")))
    t, m = out["events"][0]["ticker"], out["events"][0]["market"]
    assert t["status"] == mf.STATUS_OK and t["source_differs"] is True
    assert (t["start"]["source"], t["end"]["source"]) == (NAVER, FDR)
    assert Decimal(t["change_pct"]) == Decimal("25")
    assert m["status"] == mf.STATUS_OK and m["source_differs"] is True
    assert Decimal(m["change_pct"]) == Decimal("50")


def test_other_source_is_not_comparable(env):
    _etf(
        env["db"],
        ETF,
        {"2026-10-05": (10000.0, FDR), "2026-10-08": (11000.0, "KRX_DATA_MARKET")},
    )
    _kospi(
        env["db"], {"2026-10-05": (2000.0, "KRX"), "2026-10-08": (2100.0, KRX_KOSPI)}
    )
    out = _run(env, _cycle("BUY", "OPEN", ("r1", "BUY", "2026-10-05")))
    for item in (out["events"][0]["ticker"], out["events"][0]["market"]):
        assert item["status"] == mf.STATUS_NOT_COMPARABLE
        assert item["reason"] == "비교 불가(가격 기준 확인 안 됨)"
        assert item["change_pct"] is None
        assert item["start"] is not None and item["end"] is not None


# ── 자료 없음 · 조회 실패 ──────────────────────────────────────────────────────


def test_individual_stock_is_no_data_even_with_rows(env):
    _etf(env["db"], STOCK, {"2026-10-05": (60000.0, FDR), "2026-10-08": (66000.0, FDR)})
    _kospi(
        env["db"],
        {"2026-10-05": (2000.0, KRX_KOSPI), "2026-10-07": (2100.0, KRX_KOSPI)},
    )
    out = _run(
        env,
        _cycle(
            "BUY", "CLOSED", ("b1", "BUY", "2026-10-05"), ("s1", "SELL", "2026-10-07")
        ),
        ticker=STOCK,
    )
    assert out["asset_kind"] == "STOCK"
    assert out["latest_stored_date"] is None
    for ev in out["events"]:
        assert ev["ticker"]["status"] == mf.STATUS_NO_DATA
        assert ev["ticker"]["reason"] == "자료 없음(PC 개별주 일별 종가 미수집)"
        assert ev["market"]["reason_code"] == "NO_WINDOW"
    hp = out["holding_period"]
    assert hp["computed"] is True
    assert hp["ticker"]["reason_code"] == "STOCK_NOT_COLLECTED"
    assert hp["ticker"]["start"] is None and hp["ticker"]["change_pct"] is None
    # 같은 보유 기간의 KOSPI 는 달력으로 정한 두 날짜라 계산된다.
    assert Decimal(hp["market"]["change_pct"]) == Decimal("5")


def test_missing_db_file_is_no_data_and_not_created(tmp_path):
    db = tmp_path / "market" / "absent.sqlite"
    out = mf.build_market_flow(
        ticker=ETF,
        cycle=_cycle(
            "BUY", "CLOSED", ("b1", "BUY", "2026-10-05"), ("s1", "SELL", "2026-10-07")
        ),
        db_path=db,
        calendar_dir=_calendar(tmp_path),
    )
    assert not db.exists() and not db.parent.exists()
    assert out["db_present"] is False and out["asset_kind"] == "UNKNOWN"
    ev = out["events"][0]
    assert ev["ticker"]["reason_code"] == "NO_DB"
    assert ev["market"]["reason_code"] == "NO_DB"
    assert out["holding_period"]["ticker"]["reason_code"] == "NO_DB"
    assert out["holding_period"]["market"]["reason_code"] == "NO_DB"


def test_missing_tables_are_no_data(tmp_path):
    cal = _calendar(tmp_path)
    cyc = _cycle("BUY", "OPEN", ("r1", "BUY", "2026-10-05"))
    # 표가 하나도 없음 — 종목 구분 확인 불가.
    bare = tmp_path / "bare.sqlite"
    sqlite3.connect(bare).close()
    out = mf.build_market_flow(ticker=ETF, cycle=cyc, db_path=bare, calendar_dir=cal)
    assert out["asset_kind"] == "UNKNOWN"
    assert out["events"][0]["ticker"]["reason_code"] == "ASSET_UNKNOWN"
    assert out["events"][0]["market"]["reason_code"] == "NO_TABLE"
    # etf_master 는 있고 가격 표가 없음.
    sub = tmp_path / "sub"
    sub.mkdir()
    db = _db(sub, etf=False, market=False)
    out = mf.build_market_flow(ticker=ETF, cycle=cyc, db_path=db, calendar_dir=cal)
    assert out["asset_kind"] == "ETF"
    assert out["events"][0]["ticker"]["reason_code"] == "NO_TABLE"
    assert out["events"][0]["ticker"]["reason"] == "자료 없음(가격 표 없음)"
    assert out["events"][0]["market"]["reason_code"] == "NO_TABLE"


def test_corrupt_db_raises_read_error(tmp_path):
    db = tmp_path / "market.sqlite"
    junk = b"not a sqlite database \x00\x01\x02" * 64
    db.write_bytes(junk)
    with pytest.raises(mf.MarketFlowReadError):
        mf.build_market_flow(
            ticker=ETF,
            cycle=_cycle("BUY", "OPEN", ("r1", "BUY", "2026-10-05")),
            db_path=db,
            calendar_dir=_calendar(tmp_path),
        )
    assert db.read_bytes() == junk


# ── 보유 기간 ─────────────────────────────────────────────────────────────────


def test_closed_buy_cycle_has_holding_period(env):
    _etf(
        env["db"],
        ETF,
        {
            "2026-10-05": (10000.0, FDR),
            "2026-10-06": (10100.0, FDR),
            "2026-10-07": (10300.0, FDR),
            "2026-10-12": (12000.0, FDR),
            "2026-10-14": (13000.0, FDR),
        },
    )
    _kospi(
        env["db"],
        {"2026-10-05": (2000.0, KRX_KOSPI), "2026-10-12": (2300.0, KRX_KOSPI)},
    )
    out = _run(
        env,
        _cycle(
            "BUY",
            "CLOSED",
            ("b1", "BUY", "2026-10-05"),
            ("b2", "BUY", "2026-10-06"),
            ("s1", "SELL", "2026-10-07"),
            ("s2", "SELL", "2026-10-09"),  # 휴장 → 10-12
        ),
    )
    hp = out["holding_period"]
    assert hp["computed"] is True and hp["reason_code"] is None
    assert hp["window_label"] == "첫 매수 기준일 → 마지막 매도 기준일"
    assert (hp["start_record_id"], hp["end_record_id"]) == ("b1", "s2")
    assert hp["start_basis"]["basis_date"] == "2026-10-05"
    assert hp["end_basis"]["basis_date"] == "2026-10-12"
    assert hp["end_basis"]["moved_to_next_trading_day"] is True
    assert hp["ticker"]["status"] == mf.STATUS_OK
    assert Decimal(hp["ticker"]["change_pct"]) == Decimal("20")
    assert hp["market"]["status"] == mf.STATUS_OK
    assert Decimal(hp["market"]["change_pct"]) == Decimal("15")
    # 이벤트 4건은 각자 기준일 → 마지막 저장일(10-14).
    assert [e["record_id"] for e in out["events"]] == ["b1", "b2", "s1", "s2"]
    assert all(e["ticker"]["end_date"] == "2026-10-14" for e in out["events"])
    s2 = Decimal(out["events"][3]["ticker"]["change_pct"])  # 12,000 → 13,000
    assert abs(s2 - Decimal(1000) / Decimal(12000) * 100) < Decimal("1e-25")


@pytest.mark.parametrize("opened_by", ["BASELINE", "REGISTER"])
def test_unknown_purchase_date_skips_buy_change_but_computes_sell(env, opened_by):
    _etf(env["db"], ETF, {"2026-10-07": (10000.0, FDR), "2026-10-14": (9000.0, FDR)})
    _kospi(
        env["db"],
        {"2026-10-07": (2000.0, KRX_KOSPI), "2026-10-14": (1900.0, KRX_KOSPI)},
    )
    out = _run(env, _cycle(opened_by, "CLOSED", ("s1", "SELL", "2026-10-07")))
    assert out["purchase_date_unknown"] is True
    assert out["purchase_date_note"] == "매수일 미상 — 매수 전후 변화 계산 안 함"
    hp = out["holding_period"]
    assert hp["computed"] is False
    assert hp["reason_code"] == "PURCHASE_DATE_UNKNOWN"
    assert hp["ticker"] is None and hp["market"] is None
    ev = out["events"][0]
    assert ev["window_label"] == "매도 기준일 → 마지막 저장일"
    assert Decimal(ev["ticker"]["change_pct"]) == Decimal("-10")
    assert Decimal(ev["market"]["change_pct"]) == Decimal("-5")


def test_closed_cycle_without_sell_has_no_period(env):
    """입력 정정으로 종료한 기간 등 — 매도가 없으면 보유 기간 변화를 만들지 않는다."""
    _etf(env["db"], ETF, {"2026-10-05": (10000.0, FDR)})
    out = _run(env, _cycle("BUY", "CLOSED", ("b1", "BUY", "2026-10-05")))
    assert out["holding_period"]["computed"] is False
    assert out["holding_period"]["reason_code"] == "NO_SELL"


def test_change_pct_is_unrounded_decimal_string(env):
    _etf(env["db"], ETF, {"2026-10-05": (30000.0, FDR), "2026-10-08": (40000.0, FDR)})
    out = _run(env, _cycle("BUY", "OPEN", ("r1", "BUY", "2026-10-05")))
    pct = out["events"][0]["ticker"]["change_pct"]
    assert isinstance(pct, str) and "E" not in pct
    assert pct.startswith("33.3333333333333333333")
    assert abs(Decimal(pct) - Decimal(100) / Decimal(3)) < Decimal("1e-25")
    assert len(pct.replace(".", "")) > 28  # 정밀도 40 · 화면 반올림 없음


def test_invalid_cycle_is_value_error(env):
    with pytest.raises(ValueError):
        _run(env, _cycle("SPLIT", "OPEN"))
    with pytest.raises(ValueError):
        _run(env, _cycle("BUY", "OPEN", ("r1", "BUY", "20261005")))
    with pytest.raises(ValueError):
        _run(env, _cycle("BUY", "OPEN", ("r1", "ADJUSTMENT", "2026-10-05")))


# ── 쓰기 0 · 모듈 경계 ────────────────────────────────────────────────────────


def test_db_bytes_and_mtime_unchanged_and_read_only_uri(env, monkeypatch):
    _etf(env["db"], ETF, {"2026-10-05": (10000.0, FDR), "2026-10-08": (11000.0, FDR)})
    _kospi(
        env["db"],
        {"2026-10-05": (2000.0, KRX_KOSPI), "2026-10-08": (2100.0, KRX_KOSPI)},
    )
    db: Path = env["db"]
    before = (hashlib.sha256(db.read_bytes()).hexdigest(), db.stat().st_mtime_ns)
    listing = sorted(p.name for p in db.parent.iterdir())
    real, calls = lop.sqlite3.connect, []

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(lop.sqlite3, "connect", spy)
    out = _run(
        env,
        _cycle(
            "BUY", "CLOSED", ("b1", "BUY", "2026-10-05"), ("s1", "SELL", "2026-10-08")
        ),
    )
    assert out["holding_period"]["ticker"]["status"] == mf.STATUS_OK
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert str(args[0]).startswith("file:") and str(args[0]).endswith("?mode=ro")
    assert kwargs.get("uri") is True
    after = (hashlib.sha256(db.read_bytes()).hexdigest(), db.stat().st_mtime_ns)
    assert after == before
    assert sorted(p.name for p in db.parent.iterdir()) == listing  # -journal · -wal 0


def test_module_has_no_network_subprocess_or_telegram_imports():
    src = Path(mf.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    mods = [
        *(a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names),
        *(n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)),
    ]
    banned = (
        "requests",
        "httpx",
        "subprocess",
        "telegram",
        "urllib",
        "aiohttp",
        "socket",
    )
    assert not [m for m in mods if any(b in m for b in banned)], mods
