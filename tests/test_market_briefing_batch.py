"""POC3-OPS-02B-2 — 07:20 배치 연결 계약 test.

설계자 §M-2·§M-8 대응. 합성 fixture 와 임시 DB 만 쓴다.
**외부 조회 0건 · 라이브 DB 미접근 · 발송 0건.**
"""

from __future__ import annotations

import ast
import inspect
import json
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.market_briefing import krx_store, krx_sync, meta_gate


def _code_only(module) -> str:
    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body.pop(0)
    return ast.unparse(tree)


def _rows(bas_dd, tickers, close="10000", idx="코스피 200"):
    return [
        {"ISU_CD": t, "BAS_DD": bas_dd, "TDD_CLSPRC": close, "IDX_IND_NM": idx}
        for t in tickers
    ]


def _env(tmp_path, key="DEADBEEF"):
    p = tmp_path / ".env"
    p.write_text(f"KRX_API_KEY={key}\n", encoding="utf-8")
    return p


def _csv(tmp_path, tickers, idx="코스피 200", name="krx_etf_basic_20260909.csv"):
    head = "단축코드,기초지수명,지수산출기관,기초자산분류,추적배수,복제방법\n"
    body = "".join(f"{t},{idx},KRX,주식,일반,실물(패시브)\n" for t in tickers)
    p = tmp_path / name
    p.write_bytes((head + body).encode("cp949"))
    return p


# ── 기준일 bounded 역탐색 ──────────────────────────────────────────────────


def test_basis_date_never_uses_future_and_is_bounded():
    """당일보다 미래를 만들지 않고, 상한 내에서만 역탐색한다."""
    tried = []

    def _fetch(bas_dd, key):
        tried.append(bas_dd)
        return []

    d, rows, attempts = krx_sync.resolve_basis_date(
        start=date(2026, 9, 11), key="K", fetcher=_fetch, lookback_days=7
    )
    assert d is None and rows == []
    assert len(attempts) == 7, "상한을 넘어 역탐색했다"
    assert attempts[0] == "20260911" and attempts[-1] == "20260905"
    assert all(a <= "20260911" for a in attempts), "미래 날짜를 조회했다"


def test_basis_date_picks_most_recent_non_empty():
    def _fetch(bas_dd, key):
        return _rows(bas_dd, ["A"]) if bas_dd == "20260910" else []

    d, rows, _ = krx_sync.resolve_basis_date(
        start=date(2026, 9, 11), key="K", fetcher=_fetch
    )
    assert d == "20260910" and len(rows) == 1


def test_empty_response_is_fetch_failure_not_zero_universe(tmp_path):
    """빈 응답을 universe 0건으로 처리하지 않는다."""
    cpath = tmp_path / "c.json"
    out = krx_sync.sync_krx_daily(
        today=date(2026, 9, 11),
        official_csv_path=_csv(tmp_path, ["A"]),
        consistency_path=cpath,
        db_path=tmp_path / "m.sqlite",
        env_path=_env(tmp_path),
        fetcher=lambda d, k: [],
    )
    assert out["status"] == krx_sync.STATUS_NO_BASIS_DATE
    saved = meta_gate.load_consistency(cpath)
    assert saved.status == meta_gate.STATUS_API_FETCH_FAILED
    assert "no_response_within" in saved.error


def test_missing_api_key_does_not_raise(tmp_path):
    out = krx_sync.sync_krx_daily(
        today=date(2026, 9, 11),
        official_csv_path=_csv(tmp_path, ["A"]),
        consistency_path=tmp_path / "c.json",
        db_path=tmp_path / "m.sqlite",
        env_path=tmp_path / "missing.env",
        fetcher=lambda d, k: _rows(d, ["A"]),
    )
    assert out["status"] == krx_sync.STATUS_NO_API_KEY


# ── 응답 1회 재사용 ────────────────────────────────────────────────────────


def test_single_api_call_feeds_both_price_and_consistency(tmp_path):
    """설계자 §M-2 — **응답 하나**가 가격 적재와 정합성 판정에 함께 쓰인다."""
    calls = []
    db = tmp_path / "m.sqlite"
    cpath = tmp_path / "c.json"

    def _fetch(bas_dd, key):
        calls.append(bas_dd)
        return _rows(bas_dd, ["A", "B"])

    out = krx_sync.sync_krx_daily(
        today=date(2026, 9, 10),
        official_csv_path=_csv(tmp_path, ["A", "B"]),
        consistency_path=cpath,
        db_path=db,
        env_path=_env(tmp_path),
        fetcher=_fetch,
    )
    assert len(calls) == 1, f"API 를 {len(calls)}회 호출했다 (1회여야 한다)"
    assert out["status"] == krx_sync.STATUS_OK
    assert out["rows_written"] == 2
    assert krx_store.stored_trading_days(db_path=db) == ["2026-09-10"]
    assert meta_gate.load_consistency(cpath).status == meta_gate.STATUS_OK


def test_whole_response_is_stored_not_only_candidates(tmp_path):
    """하루 응답의 **전체 ETF** 를 저장한다 (196종만 저장하지 않는다)."""
    db = tmp_path / "m.sqlite"
    tickers = [f"T{i:03d}" for i in range(300)]
    krx_sync.sync_krx_daily(
        today=date(2026, 9, 10),
        official_csv_path=_csv(tmp_path, tickers[:10]),  # CSV 는 10종만
        consistency_path=tmp_path / "c.json",
        db_path=db,
        env_path=_env(tmp_path),
        fetcher=lambda d, k: _rows(d, tickers),
    )
    stored = krx_store.closes_on(["2026-09-10"], db_path=db)["2026-09-10"]
    assert len(stored) == 300, "응답 일부만 저장했다"


# ── snapshot fail-closed ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "bad_rows",
    [
        # 2026-09-13 정정: 전 행 빈 종가는 **휴장일 응답**이므로 여기서 빠졌다
        # (별도 테스트 test_all_empty_close_is_holiday_not_invalid 로 고정).
        # 원래 의도인 "종가 결측 행이 섞이면 전체 거부" 는 혼합 응답으로 유지한다.
        [
            {"ISU_CD": "A", "BAS_DD": "20260910", "TDD_CLSPRC": "1"},
            {"ISU_CD": "B", "BAS_DD": "20260910", "TDD_CLSPRC": ""},
        ],
        [{"ISU_CD": "A", "BAS_DD": "20260910", "TDD_CLSPRC": "0"}],
        [{"ISU_CD": "A", "BAS_DD": "20260910", "TDD_CLSPRC": "-5"}],
        [
            {"ISU_CD": "A", "BAS_DD": "20260910", "TDD_CLSPRC": "1"},
            {"ISU_CD": "A", "BAS_DD": "20260910", "TDD_CLSPRC": "2"},
        ],
        [{"ISU_CD": "A", "BAS_DD": "20260909", "TDD_CLSPRC": "1"}],
    ],
)
def test_invalid_snapshot_writes_nothing(tmp_path, bad_rows):
    """하나라도 어긋나면 **전체를 거부**한다. 부분 저장 금지."""
    db = tmp_path / "m.sqlite"
    out = krx_sync.sync_krx_daily(
        today=date(2026, 9, 10),
        official_csv_path=_csv(tmp_path, ["A"]),
        consistency_path=tmp_path / "c.json",
        db_path=db,
        env_path=_env(tmp_path),
        fetcher=lambda d, k: bad_rows,
    )
    assert out["status"] == krx_sync.STATUS_INVALID_SNAPSHOT
    assert out["rows_written"] == 0
    assert krx_store.stored_trading_days(db_path=db) == []


def test_sync_is_idempotent(tmp_path):
    db = tmp_path / "m.sqlite"
    kw = dict(
        today=date(2026, 9, 10),
        official_csv_path=_csv(tmp_path, ["A"]),
        consistency_path=tmp_path / "c.json",
        db_path=db,
        env_path=_env(tmp_path),
        fetcher=lambda d, k: _rows(d, ["A"]),
    )
    krx_sync.sync_krx_daily(**kw)
    krx_sync.sync_krx_daily(**kw)
    assert krx_store.stored_trading_days(db_path=db) == ["2026-09-10"]


# ── 초기 적재 bounded ──────────────────────────────────────────────────────


def test_initial_backfill_stops_at_required_days(tmp_path):
    """21개 확보하면 멈춘다. 전체 backfill 하지 않는다."""
    db = tmp_path / "m.sqlite"
    calls = []

    def _fetch(bas_dd, key):
        calls.append(bas_dd)
        return _rows(bas_dd, ["A"])

    out = krx_sync.initial_backfill(
        today=date(2026, 9, 30),
        db_path=db,
        env_path=_env(tmp_path),
        fetcher=_fetch,
    )
    assert out["status"] == krx_sync.STATUS_OK
    assert out["total_days"] == krx_store.REQUIRED_TRADING_DAYS
    assert len(calls) == krx_store.REQUIRED_TRADING_DAYS


def test_initial_backfill_is_bounded_by_lookback(tmp_path):
    """상한 안에 충분한 거래일이 없으면 `insufficient` 로 끝난다."""
    calls = []

    def _fetch(bas_dd, key):
        calls.append(bas_dd)
        return _rows(bas_dd, ["A"]) if bas_dd.endswith("1") else []

    out = krx_sync.initial_backfill(
        today=date(2026, 9, 30),
        db_path=tmp_path / "m.sqlite",
        env_path=_env(tmp_path),
        fetcher=_fetch,
        lookback_days=10,
    )
    assert out["status"] == "insufficient"
    assert len(calls) <= 10, "상한을 넘어 조회했다"


# ── 미국 지수 3종 ──────────────────────────────────────────────────────────


class _DF:
    """`iterrows()` 만 쓰는 최소 스텁."""

    def __init__(self, rows):
        self._rows = rows

    def iterrows(self):
        for d, close in self._rows:
            yield SimpleNamespace(strftime=lambda f, _d=d: _d), {"Close": close}


def _us_fetcher(rows):
    return lambda sym, start, end: _DF(rows)


def test_us_index_requires_two_sessions(tmp_path):
    from app.market_benchmark_batch import refresh_us_index

    one = refresh_us_index(
        "US500",
        "S&P500",
        "FDR_US500",
        end_date=date(2026, 9, 10),
        db_path=tmp_path / "m.sqlite",
        price_fetcher=_us_fetcher([("2026-09-10", 7000.0)]),
    )
    assert one["status"] == "failed"
    assert "insufficient_sessions" in one["error"]


def test_us_index_ok_with_two_sessions(tmp_path):
    from app.market_benchmark_batch import refresh_us_index

    r = refresh_us_index(
        "US500",
        "S&P500",
        "FDR_US500",
        end_date=date(2026, 9, 10),
        db_path=tmp_path / "m.sqlite",
        price_fetcher=_us_fetcher([("2026-09-09", 6900.0), ("2026-09-10", 7000.0)]),
    )
    assert r["status"] == "ok" and r["as_of_date"] == "2026-09-10"


@pytest.mark.parametrize(
    "rows,frag",
    [
        ([("2026-09-11", 1.0), ("2026-09-12", 2.0)], "future_date"),
        ([("2026-09-10", 1.0), ("2026-09-10", 2.0)], "duplicate_date"),
    ],
)
def test_us_index_fail_closed(tmp_path, rows, frag):
    from app.market_benchmark_batch import refresh_us_index

    r = refresh_us_index(
        "US500",
        "S&P500",
        "FDR_US500",
        end_date=date(2026, 9, 10),
        db_path=tmp_path / "m.sqlite",
        price_fetcher=_us_fetcher(rows),
    )
    assert r["status"] == "failed" and frag in r["error"]


def test_us_index_failure_recorded_separately(monkeypatch, tmp_path):
    """미국 지수 실패를 KOSPI·VIX 성공으로 숨기지 않는다."""
    import app.market_benchmark_batch as mod

    monkeypatch.setattr(
        mod,
        "refresh_kospi",
        lambda **kw: {"status": "ok", "as_of_date": "2026-09-10", "error": None},
    )
    monkeypatch.setattr(
        mod,
        "refresh_vix",
        lambda **kw: {"status": "ok", "as_of_date": "2026-09-10", "error": None},
    )
    monkeypatch.setattr(
        mod,
        "refresh_us_index",
        lambda *a, **kw: {"status": "failed", "as_of_date": None, "error": "boom"},
    )
    out = mod.refresh_benchmarks(end_date=date(2026, 9, 10))
    assert out["status"] == "partial", "미국 지수 실패가 ok 로 묻혔다"
    assert set(out["failed"]) == {"us:US500", "us:IXIC", "us:^SOX"}
    assert out["kospi"]["status"] == "ok"
    assert set(out["us_indices"]) == {"US500", "IXIC", "^SOX"}


def test_us_benchmarks_are_exactly_three():
    """Russell 2000·USD/KRW 는 이번 Step 에 추가하지 않는다 (설계자 §M-2)."""
    from app.market_benchmark_batch import US_BENCHMARKS

    assert [s for s, _, _ in US_BENCHMARKS] == ["US500", "IXIC", "^SOX"]
    assert "RUT" not in str(US_BENCHMARKS)
    assert "USD/KRW" not in str(US_BENCHMARKS)


# ── 격리 ───────────────────────────────────────────────────────────────────


def test_krx_sync_does_not_touch_adjusted_series():
    import re

    src = _code_only(krx_sync)
    assert not re.search(r"(?<![\w_])etf_daily_price(?![\w_])", src)


def test_batch_state_records_krx_fields(tmp_path):
    from app.three_push_runtime.market_data_batch import (
        read_batch_state,
        write_batch_state,
    )

    p = tmp_path / "s.json"
    write_batch_state(
        status="success",
        price_data_as_of="2026-09-10",
        artifact_generated_at="x",
        refresh_date_kst="2026-09-11",
        refresh_completed_at="y",
        state_path=p,
        krx_sync_status="ok",
        krx_basis_date="20260910",
        meta_consistency_status="CSV_REFRESH_REQUIRED",
    )
    st = read_batch_state(p)
    assert st["krx_sync_status"] == "ok"
    assert st["krx_basis_date"] == "20260910"
    assert st["meta_consistency_status"] == "CSV_REFRESH_REQUIRED"
    assert json.loads(p.read_text(encoding="utf-8"))["price_data_as_of"] == "2026-09-10"


# ── 휴장일 응답은 기준일이 될 수 없다 (2026-09-13 실측 결함) ──────────────────
# KRX Open API 는 평일 휴장일에도 **행을 돌려준다**. 가격 필드만 빈 문자열이다
# (실측: 20260101 rows=1058 TDD_CLSPRC=""). `rows` 유무만 보면 휴장일을 기준일로
# 집어 그 다음날 07:20 배치가 invalid_snapshot 으로 통째로 실패한다(2026년 11회).


def _holiday_rows(bas_dd: str = "20260817", n: int = 3) -> list[dict[str, object]]:
    """휴장일 응답 — 행은 있고 가격 필드가 전부 빈 문자열."""
    return [
        {
            "ISU_CD": f"00000{i}",
            "ISU_NM": f"ETF{i}",
            "BAS_DD": bas_dd,
            "TDD_CLSPRC": "",
            "ACC_TRDVOL": "",
            "IDX_IND_NM": "KOSPI 200",
        }
        for i in range(n)
    ]


def _traded_rows(
    bas_dd: str = "20260814", close: str = "10000", n: int = 3
) -> list[dict[str, object]]:
    return [
        {
            "ISU_CD": f"00000{i}",
            "ISU_NM": f"ETF{i}",
            "BAS_DD": bas_dd,
            "TDD_CLSPRC": close,
            "ACC_TRDVOL": "100",
            "IDX_IND_NM": "KOSPI 200",
        }
        for i in range(n)
    ]


def test_has_traded_prices_rejects_holiday_response():
    assert krx_sync.has_traded_prices(_traded_rows()) is True
    assert krx_sync.has_traded_prices(_holiday_rows()) is False
    assert krx_sync.has_traded_prices([]) is False


def test_resolve_basis_date_skips_holiday_and_keeps_searching():
    """휴장일을 건너뛰고 **직전 거래일**까지 계속 과거로 탐색한다."""
    calls: list[str] = []

    def fetch(bas_dd: str, key: str):
        calls.append(bas_dd)
        if bas_dd == "20260818":
            return []  # 07:20 — 당일 미공시
        if bas_dd == "20260817":
            return _holiday_rows(bas_dd)  # 광복절 대체공휴일
        return _traded_rows(bas_dd)

    bas, rows, tried = krx_sync.resolve_basis_date(
        start=date(2026, 8, 18), key="K", fetcher=fetch, lookback_days=7
    )
    assert bas == "20260816", (bas, tried)
    assert krx_sync.has_traded_prices(rows)
    # 휴장일을 기준일로 집지 않았다.
    assert bas != "20260817"


def test_resolve_basis_date_returns_none_when_only_holidays():
    """상한 내 전부 휴장이면 **기준일 없음**. 휴장일로 위장하지 않는다."""

    def fetch(bas_dd: str, key: str):
        return _holiday_rows(bas_dd)

    bas, rows, tried = krx_sync.resolve_basis_date(
        start=date(2026, 8, 18), key="K", fetcher=fetch, lookback_days=3
    )
    assert bas is None
    assert rows == []
    assert len(tried) == 3


def test_sync_krx_daily_uses_prior_trading_day_after_holiday(tmp_path):
    """휴장일 다음날 배치가 실패하지 않고 직전 거래일을 적재한다."""

    def fetch(bas_dd: str, key: str):
        if bas_dd == "20260818":
            return []
        if bas_dd == "20260817":
            return _holiday_rows(bas_dd)
        return _traded_rows(bas_dd)

    env = tmp_path / ".env"
    env.write_text("KRX_API_KEY=dummy\n", encoding="utf-8")
    out = krx_sync.sync_krx_daily(
        today=date(2026, 8, 18),
        official_csv_path=tmp_path / "missing.csv",
        consistency_path=tmp_path / "consistency.json",
        db_path=tmp_path / "krx.sqlite",
        env_path=env,
        fetcher=fetch,
        lookback_days=7,
    )
    assert out["status"] == krx_sync.STATUS_OK, out
    assert out["basis_date"] == "20260816"
    assert out["rows_written"] == 3


def test_initial_backfill_skips_holiday_dates(tmp_path):
    """초기 적재도 휴장일을 거래일로 세지 않는다."""
    holidays = {"20260817", "20260815", "20260816"}

    def fetch(bas_dd: str, key: str):
        return _holiday_rows(bas_dd) if bas_dd in holidays else _traded_rows(bas_dd)

    env = tmp_path / ".env"
    env.write_text("KRX_API_KEY=dummy\n", encoding="utf-8")
    out = krx_sync.initial_backfill(
        today=date(2026, 8, 18),
        db_path=tmp_path / "krx.sqlite",
        env_path=env,
        fetcher=fetch,
        required_days=2,
        lookback_days=6,
    )
    assert out["status"] == krx_sync.STATUS_OK, out
    for d in ("2026-08-17", "2026-08-16", "2026-08-15"):
        assert d not in out["written_days"], out["written_days"]


def test_all_empty_close_is_holiday_not_invalid(tmp_path):
    """전 행 빈 종가는 **휴장일**이다 — `invalid_snapshot` 으로 분류하지 않는다.

    2026-09-13 실측으로 바뀐 전제다. 예전에는 이 응답을 "종가 결측 snapshot" 으로
    거부했는데, 실제로는 KRX 가 평일 휴장일에 돌려주는 정상 응답이다. 따라서
    기준일 후보에서 제외되고, 상한 내 거래일이 없으면 기준일 없음이 된다.

    어느 쪽이든 **아무것도 저장하지 않는다** — fail-closed 는 그대로다.
    """
    db = tmp_path / "m.sqlite"
    out = krx_sync.sync_krx_daily(
        today=date(2026, 9, 10),
        official_csv_path=_csv(tmp_path, ["A"]),
        consistency_path=tmp_path / "c.json",
        db_path=db,
        env_path=_env(tmp_path),
        fetcher=lambda d, k: _holiday_rows(d),
        lookback_days=3,
    )
    assert out["status"] == krx_sync.STATUS_NO_BASIS_DATE, out
    assert out["status"] != krx_sync.STATUS_INVALID_SNAPSHOT
    assert out["rows_written"] == 0
    assert krx_store.stored_trading_days(db_path=db) == []


# ── POC3-02D-OPS-01 C1 — pending gate 는 07:20 이 판정한다 ────────────────────
# 적재 직후 · **같은 응답**으로 d20 종가 유무와 첫 적재일을 본다(설계자 Q1 (c)).
# d20 은 08:00 과 같은 창(`krx_store.resolve_window`)의 d20 이다.

BASE20 = [f"B{i:02d}" for i in range(20)]


def _weekdays(start: date, end: date) -> list[str]:
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append(d.strftime("%Y%m%d"))
        d += timedelta(days=1)
    return out


# 20260916 까지 21 거래일 — 20260917 을 적재하면 d20 은 20260820 이다.
DAYS21 = _weekdays(date(2026, 8, 19), date(2026, 9, 16))


def _sync_on(
    tmp_path,
    *,
    seed,
    csv_tickers,
    api_tickers,
    today=date(2026, 9, 17),
    basis="20260917",
):
    db = tmp_path / "m.sqlite"
    for bas, tickers in seed:
        krx_store.upsert_snapshot(
            krx_store.validate_snapshot(_rows(bas, tickers), expected_date=bas),
            db_path=db,
        )
    cpath = tmp_path / "c.json"
    out = krx_sync.sync_krx_daily(
        today=today,
        official_csv_path=_csv(tmp_path, csv_tickers),
        consistency_path=cpath,
        db_path=db,
        env_path=_env(tmp_path),
        fetcher=lambda d, k: _rows(d, api_tickers) if d == basis else [],
    )
    return out, json.loads(cpath.read_text(encoding="utf-8"))


def _base_seed(extra=()):
    return [(d, BASE20 + list(extra)) for d in DAYS21]


def test_sync_new_listing_without_d20_is_pending_not_blocking(tmp_path):
    assert len(DAYS21) == krx_store.REQUIRED_TRADING_DAYS
    seed = _base_seed() + [("20260915", ["NEW1"]), ("20260916", ["NEW1"])]
    out, saved = _sync_on(
        tmp_path, seed=seed, csv_tickers=BASE20, api_tickers=BASE20 + ["NEW1"]
    )
    assert out["status"] == krx_sync.STATUS_OK
    assert out["consistency_status"] == meta_gate.STATUS_OK, saved
    assert saved["status"] == meta_gate.STATUS_OK
    assert saved["api_only"] == ["NEW1"]
    assert saved["api_only_pending_count"] == 1
    # 09-15 · 16 · 17(오늘 적재) 3거래일 → d20 까지 18 (R2 Q23).
    assert saved["api_only_pending"] == [
        {
            "ticker": "NEW1",
            "first_loaded": "2026-09-15",
            "stored_trading_day_count": 3,
            "remaining_trading_days": 18,
        }
    ]


def test_sync_api_only_with_d20_close_still_blocks(tmp_path):
    out, saved = _sync_on(
        tmp_path,
        seed=_base_seed(extra=["OLD1"]),
        csv_tickers=BASE20,
        api_tickers=BASE20 + ["OLD1"],
    )
    assert out["consistency_status"] == meta_gate.STATUS_CSV_REFRESH_REQUIRED
    assert saved["api_only"] == ["OLD1"]
    assert saved["api_only_pending_count"] == 0


def test_sync_mixed_api_only_blocks_and_records_pending(tmp_path):
    seed = _base_seed(extra=["OLD1"]) + [("20260916", ["NEW1"])]
    out, saved = _sync_on(
        tmp_path,
        seed=seed,
        csv_tickers=BASE20,
        api_tickers=BASE20 + ["OLD1", "NEW1"],
    )
    assert out["consistency_status"] == meta_gate.STATUS_CSV_REFRESH_REQUIRED
    assert saved["api_only"] == ["NEW1", "OLD1"]
    assert saved["api_only_pending"] == [
        {
            "ticker": "NEW1",
            "first_loaded": "2026-09-16",
            "stored_trading_day_count": 2,
            "remaining_trading_days": 19,
        }
    ]


def _seed_new_from(first_day):
    """BASE20 은 전 기간 · NEW1 은 `first_day` 부터 적재."""
    return [(d, BASE20 + (["NEW1"] if d >= first_day else [])) for d in DAYS21]


def test_sync_first_loaded_on_d20_day_blocks(tmp_path):
    """경계 — d20 **당일** 첫 적재면 d20 종가가 있다 → 후보 n 에 들어가므로 차단."""
    out, saved = _sync_on(
        tmp_path,
        seed=_seed_new_from("20260820"),
        csv_tickers=BASE20,
        api_tickers=BASE20 + ["NEW1"],
    )
    assert krx_store.resolve_window(db_path=tmp_path / "m.sqlite").d20 == "2026-08-20"
    assert out["consistency_status"] == meta_gate.STATUS_CSV_REFRESH_REQUIRED, saved
    assert saved["api_only"] == ["NEW1"]
    assert saved["api_only_pending_count"] == 0


def test_sync_first_loaded_day_after_d20_is_pending(tmp_path):
    """경계 — d20 **다음** 저장일 첫 적재면 d20 종가가 없다 → pending."""
    out, saved = _sync_on(
        tmp_path,
        seed=_seed_new_from("20260821"),
        csv_tickers=BASE20,
        api_tickers=BASE20 + ["NEW1"],
    )
    assert krx_store.resolve_window(db_path=tmp_path / "m.sqlite").d20 == "2026-08-20"
    assert out["consistency_status"] == meta_gate.STATUS_OK, saved
    # 08-21 ~ 09-16 19일 + 오늘 1일 = 20 → 다음 저장 거래일에 d20 이 생긴다.
    assert saved["api_only_pending"] == [
        {
            "ticker": "NEW1",
            "first_loaded": "2026-08-21",
            "stored_trading_day_count": 20,
            "remaining_trading_days": 1,
        }
    ]


def test_sync_without_window_treats_api_only_as_pending(tmp_path):
    """21 거래일이 없으면 창이 없다 — d20 종가가 있는 ticker 도 없다."""
    out, saved = _sync_on(
        tmp_path, seed=[], csv_tickers=BASE20, api_tickers=BASE20 + ["NEW1"]
    )
    assert krx_store.resolve_window(db_path=tmp_path / "m.sqlite") is None
    assert out["consistency_status"] == meta_gate.STATUS_OK, saved
    assert saved["api_only_pending"] == [
        {
            "ticker": "NEW1",
            "first_loaded": "2026-09-17",
            "stored_trading_day_count": 1,
            "remaining_trading_days": 20,
        }
    ]


def test_sync_oci_0925_shape_turns_ok_with_pending(tmp_path):
    """09-25 07:20 실측 모양 — API-only 8 · 불일치 0 · coverage 1,167/1,175."""
    base = [f"{100000 + i}" for i in range(1167)]
    new_0915 = ["0227L0", "0238F0", "0239Y0", "0239Z0"]
    new_0922 = ["0238C0", "0240J0", "0241R0", "0242S0"]
    seed = []
    for bas in _weekdays(date(2026, 8, 17), date(2026, 9, 21)):
        tickers = list(base)
        if bas <= "20260914":
            tickers.append("465780")  # CSV 에만 남은 종목 · 09-14 마지막 적재
        if bas >= "20260915":
            tickers += new_0915
        seed.append((bas, tickers))
    out, saved = _sync_on(
        tmp_path,
        seed=seed,
        csv_tickers=base + ["465780"],
        api_tickers=base + new_0915 + new_0922,
        today=date(2026, 9, 25),
        basis="20260922",
    )
    assert out["basis_date"] == "20260922"
    assert saved["status"] == meta_gate.STATUS_OK, saved["status"]
    assert saved["api_only_count"] == 8
    assert saved["name_mismatch_count"] == 0
    assert saved["csv_only"] == ["465780"]
    assert saved["exact_match_count"] == 1167
    assert saved["join_coverage"] == pytest.approx(0.993191, abs=1e-6)
    assert {p["ticker"]: p["first_loaded"] for p in saved["api_only_pending"]} == {
        **{t: "2026-09-15" for t in new_0915},
        **{t: "2026-09-22" for t in new_0922},
    }


def test_sync_pending_lookup_failure_falls_back_to_strict_block(tmp_path, monkeypatch):
    """첫 적재일 조회가 실패하면 옛 계약(API-only 전부 차단)으로 fail-closed 한다.

    `sync_krx_daily` 는 예외를 올리지 않는 계약이다 — 정합성 JSON 을 남긴다.
    """
    import sqlite3

    def _boom(*a, **k):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(krx_store, "first_loaded_dates", _boom)
    seed = _base_seed() + [("20260916", ["NEW1"])]
    out, saved = _sync_on(
        tmp_path, seed=seed, csv_tickers=BASE20, api_tickers=BASE20 + ["NEW1"]
    )
    assert out["status"] == krx_sync.STATUS_OK  # 가격 적재는 끝났다
    assert saved["status"] == meta_gate.STATUS_CSV_REFRESH_REQUIRED
    assert saved["api_only_pending_count"] == 0
    assert saved["error"] == "pending_lookup:OperationalError"


# ── POC3-02D-OPS-01 C1 — 07:20 공용 resolver · refresh_due · 판정 창 ─────────
# 설계자 C1 필수 보완 · R2 Q23 · Q25 · Q27. `meta_dir` 는 전부 tmp 다 — 저장소
# `state/market_meta` 를 읽지 않는다.


def _krx_csv(path, tickers, idx="코스피 200"):
    """승인 파일과 같은 17컬럼 · cp949."""
    from app.market_briefing import official_csv as oc

    lines = [",".join(oc.EXPECTED_HEADER)]
    for t in tickers:
        r = dict.fromkeys(oc.EXPECTED_HEADER, "-")
        r.update({"단축코드": t, "기초지수명": idx, "한글종목약명": f"ETF{t}"})
        lines.append(",".join(r[h] for h in oc.EXPECTED_HEADER))
    path.write_bytes(("\n".join(lines) + "\n").encode("cp949"))
    return path


def _sha(path):
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


class _Log:
    def __init__(self):
        self.warnings: list[str] = []

    def warning(self, msg, *args):
        self.warnings.append(msg % args)

    def info(self, msg, *args):
        pass


def _meta_dir(tmp_path, files):
    meta = tmp_path / "market_meta"
    meta.mkdir(exist_ok=True)
    for name, tickers in files.items():
        _krx_csv(meta / name, tickers)
    return meta


def _sync_meta(
    tmp_path,
    meta,
    *,
    seed,
    api_tickers,
    today=date(2026, 9, 17),
    basis="20260917",
    logger=None,
):
    """`_sync_on` 과 같되 CSV 를 **resolver** 로 고른다(운영 07:20 과 같은 길)."""
    db = tmp_path / "m.sqlite"
    for bas, tickers in seed:
        krx_store.upsert_snapshot(
            krx_store.validate_snapshot(_rows(bas, tickers), expected_date=bas),
            db_path=db,
        )
    cpath = tmp_path / "c.json"
    out = krx_sync.sync_krx_daily(
        today=today,
        meta_dir=meta,
        consistency_path=cpath,
        db_path=db,
        env_path=_env(tmp_path),
        fetcher=lambda d, k: _rows(d, api_tickers) if d == basis else [],
        logger=logger,
    )
    return out, json.loads(cpath.read_text(encoding="utf-8"))


def test_sync_resolver_records_selection_and_rejections(tmp_path):
    meta = _meta_dir(
        tmp_path,
        {
            "krx_etf_basic_20260909.csv": BASE20,
            "krx_etf_basic_20260927.csv": BASE20 + ["B00"],  # 단축코드 중복
        },
    )
    log = _Log()
    out, saved = _sync_meta(
        tmp_path, meta, seed=_base_seed(), api_tickers=BASE20, logger=log
    )
    good, bad = meta / "krx_etf_basic_20260909.csv", meta / "krx_etf_basic_20260927.csv"
    assert out["status"] == krx_sync.STATUS_OK
    assert saved["status"] == meta_gate.STATUS_OK, saved
    assert saved["csv_name"] == good.name and saved["csv_sha256"] == _sha(good)
    assert saved["csv_asof_date"] == "2026-09-09" and saved["csv_rows"] == 20
    assert [(r["name"], r["sha256"], r["reason"]) for r in saved["csv_rejected"]] == [
        (bad.name, _sha(bad), "duplicate_ticker")
    ]
    assert any(bad.name in w for w in log.warnings), log.warnings
    assert out["csv_name"] == good.name


def test_sync_without_valid_csv_fails_closed_but_keeps_prices(tmp_path):
    from app.market_briefing import official_csv as oc

    meta = tmp_path / "market_meta"
    meta.mkdir()
    bad = meta / "krx_etf_basic_20260927.csv"
    bad.write_bytes(",".join(oc.EXPECTED_HEADER).encode("utf-8") + b"\n")
    out, saved = _sync_meta(tmp_path, meta, seed=_base_seed(), api_tickers=BASE20)
    assert out["status"] == krx_sync.STATUS_OK and out["rows_written"] == 20
    assert saved["status"] == meta_gate.STATUS_CSV_REFRESH_REQUIRED
    assert saved["error"] == oc.ERROR_NO_VALID_FILE
    assert saved["csv_name"] is None
    assert [r["reason"] for r in saved["csv_rejected"]] == [oc.REASON_DECODE]
    assert saved["refresh_due"] is True
    assert saved["refresh_due_reason"] == meta_gate.REFRESH_REASON_CSV
    assert saved["evaluated_api_basis_date"] == "20260917"


@pytest.mark.parametrize("stored,remaining,due", [(15, 6, False), (16, 5, True)])
def test_sync_refresh_due_from_stored_counts(tmp_path, stored, remaining, due):
    """R2 Q23 — 저장 거래일 수는 **오늘 적재 뒤** 센다(같은 응답)."""
    first = DAYS21[-(stored - 1)]  # 오늘(20260917) 포함 `stored` 거래일
    seed = [(d, BASE20 + (["NEW1"] if d >= first else [])) for d in DAYS21]
    meta = _meta_dir(tmp_path, {"krx_etf_basic_20260909.csv": BASE20})
    out, saved = _sync_meta(tmp_path, meta, seed=seed, api_tickers=BASE20 + ["NEW1"])
    assert saved["status"] == meta_gate.STATUS_OK, saved
    assert saved["api_only_pending"] == [
        {
            "ticker": "NEW1",
            "first_loaded": f"{first[:4]}-{first[4:6]}-{first[6:]}",
            "stored_trading_day_count": stored,
            "remaining_trading_days": remaining,
        }
    ]
    assert saved["refresh_due"] is due and out["refresh_due"] is due
    assert saved["refresh_due_cycle_id"] == ("20260917" if due else None)
    # R2 Q27 — 판정에 쓴 창을 남긴다(적재 뒤 `resolve_window`).
    window = krx_store.resolve_window(db_path=tmp_path / "m.sqlite")
    assert saved["evaluated_api_basis_date"] == "20260917"
    assert saved["evaluated_window_d20_date"] == window.d20 == "2026-08-20"
    assert saved["evaluated_at_kst"].endswith("+09:00")


def test_sync_refresh_due_cycle_carries_through_failure_and_resets(tmp_path):
    """due 주기는 이어지는 동안 같은 id · 판정 못 한 날은 이어받음 · 갱신 뒤 해제."""
    first = DAYS21[-15]  # 오늘 포함 16거래일 → 남은 5
    seed = [(d, BASE20 + (["NEW1"] if d >= first else [])) for d in DAYS21]
    meta = _meta_dir(tmp_path, {"krx_etf_basic_20260909.csv": BASE20})
    api = BASE20 + ["NEW1"]
    _, day1 = _sync_meta(tmp_path, meta, seed=seed, api_tickers=api)
    assert (day1["refresh_due"], day1["refresh_due_cycle_id"]) == (True, "20260917")

    # 다음 날 조회 실패 — 판정하지 못했으므로 주기를 끊지 않는다.
    _, day2 = _sync_meta(
        tmp_path, meta, seed=[], api_tickers=api, today=date(2026, 9, 18), basis="x"
    )
    assert day2["status"] == meta_gate.STATUS_API_FETCH_FAILED
    assert (day2["refresh_due"], day2["refresh_due_cycle_id"]) == (True, "20260917")
    assert day2["refresh_due_reason"] == meta_gate.REFRESH_REASON_NOT_EVALUATED
    assert day2["evaluated_api_basis_date"] is None
    assert day2["evaluated_at_kst"].endswith("+09:00")

    _, day3 = _sync_meta(
        tmp_path,
        meta,
        seed=[],
        api_tickers=api,
        today=date(2026, 9, 18),
        basis="20260918",
    )
    assert (day3["refresh_due"], day3["refresh_due_cycle_id"]) == (True, "20260917")
    assert day3["api_only_pending"][0]["remaining_trading_days"] == 4

    # 새 CSV 가 들어오면 pending 이 비고 due 가 풀린다.
    _krx_csv(meta / "krx_etf_basic_20260918.csv", api)
    _, day4 = _sync_meta(
        tmp_path,
        meta,
        seed=[],
        api_tickers=api,
        today=date(2026, 9, 18),
        basis="20260918",
    )
    assert day4["csv_name"] == "krx_etf_basic_20260918.csv"
    assert day4["api_only_pending_count"] == 0
    assert (day4["refresh_due"], day4["refresh_due_cycle_id"]) == (False, None)


def test_0720_and_0800_share_one_resolver(tmp_path, monkeypatch):
    """Q2 — 07:20 · 08:00 이 **같은 함수**로 CSV 를 고른다(한 층만 바꾸는 회귀 방지)."""
    import inspect
    from pathlib import Path

    import scripts.run_oci_market_data_batch as batch
    from app.market_briefing import calendar as _cal
    from app.market_briefing import official_csv as oc
    from app.three_push_runtime import runner_market_briefing as mb

    calls: list[Path] = []
    real = oc.resolve_official_csv

    def _spy(meta_dir, **kw):
        calls.append(Path(meta_dir))
        return real(meta_dir, **kw)

    monkeypatch.setattr(oc, "resolve_official_csv", _spy)
    meta = _meta_dir(tmp_path, {"krx_etf_basic_20260909.csv": BASE20})
    _sync_meta(tmp_path, meta, seed=_base_seed(), api_tickers=BASE20)
    (meta / "krx_trading_days_2026.csv").write_text(
        "date\n2026-09-17\n2026-09-18\n", encoding="utf-8"
    )
    monkeypatch.setattr(_cal, "CALENDAR_DIR", meta)
    monkeypatch.setattr(mb, "_sp500_input", lambda _t, **_kw: (1.0, "2026-09-17", True))
    record: dict = {}
    mb.assemble(
        record,
        push_kind=mb.PUSH_KIND,
        today_kst="2026-09-18",
        runtime_kst=None,
        state_dir=tmp_path / "three_push",
        meta_dir=meta,
        db_path=tmp_path / "m.sqlite",
    )
    assert calls == [meta, meta]
    assert record["official_csv"]["name"] == "krx_etf_basic_20260909.csv"
    # 운영 두 진입점에 고정 파일명 상수가 남아 있지 않다.
    batch_src = Path(inspect.getsourcefile(batch)).read_text(encoding="utf-8")
    for src in (inspect.getsource(mb), batch_src):
        assert "krx_etf_basic_2026" not in src
        assert "OFFICIAL_ETF_CSV" not in src


def test_batch_run_passes_meta_dir_and_records_refresh_due(
    tmp_path, monkeypatch, caplog
):
    """07:20 배치는 폴더를 넘기고 · refresh_due 를 매회 record · 로그에 남긴다."""
    import logging

    import scripts.run_oci_market_data_batch as batch
    from app.three_push_runtime import market_data_batch as mdb
    from app.three_push_runtime.market_data_batch import RefreshResult

    monkeypatch.setattr(mdb, "MARKET_DATA_BATCH_STATE_PATH", tmp_path / "bs.json")
    monkeypatch.setattr(batch, "collect_approved_tickers", lambda: ["069500"])
    monkeypatch.setattr(
        batch,
        "refresh_approved_prices",
        lambda *a, **k: RefreshResult(
            attempted=1, success=1, fail=0, price_data_as_of="2026-09-17"
        ),
    )
    ok = {"status": "ok", "as_of_date": "2026-09-17", "error": None}
    monkeypatch.setattr(
        "app.market_benchmark_batch.refresh_benchmarks",
        lambda **kw: {"kospi": ok, "vix": ok, "status": "ok", "failed": []},
    )
    seen: dict = {}

    def _sync(**kw):
        seen.update(kw)
        return {
            "status": krx_sync.STATUS_OK,
            "basis_date": "20260917",
            "consistency_status": meta_gate.STATUS_OK,
            "refresh_due": True,
            "refresh_due_reason": meta_gate.REFRESH_REASON_PENDING,
            "refresh_due_cycle_id": "20260917",
            "csv_name": "krx_etf_basic_20260909.csv",
        }

    # POC3-02D-OPS-03 — 배치의 KRX 단계는 목표일 수집(`krx_target_sync`)이다.
    from app.market_briefing import krx_target_sync

    monkeypatch.setattr(krx_target_sync, "sync_krx_target", _sync)
    monkeypatch.setattr(
        batch,
        "_build_universe_artifact",
        lambda *, price_data_as_of: ({"summary": {}}, "t", "failed"),
    )
    with caplog.at_level(logging.INFO):
        rec = batch.run(mode="run")
    assert seen["meta_dir"] == batch.MARKET_META_DIR
    assert "official_csv_path" not in seen
    assert rec["meta_refresh_due"] is True
    assert rec["meta_refresh_due_reason"] == meta_gate.REFRESH_REASON_PENDING
    assert rec["meta_refresh_due_cycle_id"] == "20260917"
    assert rec["official_csv_name"] == "krx_etf_basic_20260909.csv"
    assert any(
        "refresh_due=True" in m and "20260917" in m for m in caplog.messages
    ), caplog.messages


# ── 검증 스크립트 (PC 전용 · 외부 호출 0) ─────────────────────────────────────


def test_check_script_exit_codes(tmp_path, capsys):
    import importlib

    chk = importlib.import_module("scripts.check_krx_etf_basic_csv")
    meta = _meta_dir(tmp_path, {"krx_etf_basic_20260909.csv": BASE20})
    assert chk.main(["--meta-dir", str(meta)]) == 0
    assert "krx_etf_basic_20260909.csv" in capsys.readouterr().out

    # 새 원본(파일명 무관) — 내용 검사 통과 · 옛 파일 대비 추가 ticker 표시.
    new = _krx_csv(tmp_path / "KRX_ETF_20260927.csv", BASE20[1:] + ["NEW1"])
    old = meta / "krx_etf_basic_20260909.csv"
    assert chk.main([str(new), "--meta-dir", str(meta), "--compare", str(old)]) == 0
    out = capsys.readouterr().out
    assert "NEW1" in out and BASE20[0] in out

    bad = _krx_csv(tmp_path / "bad.csv", BASE20 + ["B00"])
    assert chk.main([str(bad), "--meta-dir", str(meta)]) == 1
    assert "duplicate_ticker" in capsys.readouterr().out

    # 폴더에 고를 파일이 없으면 실패.
    empty = tmp_path / "empty"
    empty.mkdir()
    _krx_csv(empty / "krx_etf_basic_20260927.csv", ["A", "A"])
    assert chk.main(["--meta-dir", str(empty)]) == 1
    assert "duplicate_ticker" in capsys.readouterr().out

    # 새 파일이 조용히 안 쓰이면 실패 — 선택 날짜 이상 · 날짜 불명 거부 후보.
    def _utf8(path):
        path.write_bytes(path.read_bytes().decode("cp949").encode("utf-8"))

    for i, (name, broken) in enumerate(
        [
            # Excel 등으로 UTF-8 재저장한 새 파일 — resolver 는 20260909 로 내려간다.
            ("krx_etf_basic_20260927.csv", True),
            # 이름이 엄격 패턴이 아닌 새 파일(날짜는 읽힌다 · name_pattern).
            ("krx_etf_basic_20260927 (1).csv", False),
            # 날짜를 못 읽는 이름(date_parse) — 새 파일인지 알 수 없다.
            ("krx_etf_basic_2026-09-27.csv", False),
        ]
    ):
        base = tmp_path / f"newer{i}"
        base.mkdir()
        m = _meta_dir(base, {"krx_etf_basic_20260909.csv": BASE20})
        new = _krx_csv(m / name, BASE20 + ["NEW1"])
        if broken:
            _utf8(new)
        assert chk.main(["--meta-dir", str(m)]) == 1, name
        out = capsys.readouterr().out
        assert "resolver 선택: krx_etf_basic_20260909.csv" in out, name
        assert f"새 파일이 쓰이지 않는다: {name}" in out and "결과: 실패" in out

    # 선택보다 오래된 거부 후보만 있으면 통과.
    older = tmp_path / "older"
    older.mkdir()
    m = _meta_dir(older, {"krx_etf_basic_20260927.csv": BASE20})
    _utf8(_krx_csv(m / "krx_etf_basic_20260909.csv", BASE20))
    assert chk.main(["--meta-dir", str(m)]) == 0
    out = capsys.readouterr().out
    assert "resolver 선택: krx_etf_basic_20260927.csv" in out
    assert "거부: krx_etf_basic_20260909.csv" in out and "결과: 통과" in out
    assert "새 파일이 쓰이지 않는다" not in out

    # resolver 후보(`FILE_GLOB`)에도 안 걸리는 비슷한 이름 — 거부 목록에도 없어
    # 조용히 무시된다. 폴더 검사가 실패로 드러낸다.
    for i, name in enumerate(
        [
            "krx_etf_basic_20260927.CSV",
            "KRX_ETF_BASIC_20260927.csv",
            "krx_etf_basic20260927.csv",
            "krx_etf_basic_20260927.csv.txt",
        ]
    ):
        (tmp_path / f"off{i}").mkdir()
        m = _meta_dir(tmp_path / f"off{i}", {"krx_etf_basic_20260909.csv": BASE20})
        _krx_csv(m / name, BASE20 + ["NEW1"])
        assert chk.main(["--meta-dir", str(m)]) == 1, name
        out = capsys.readouterr().out
        assert "resolver 선택: krx_etf_basic_20260909.csv" in out, name
        assert f"파일명이 resolver 후보가 아니다: {name}" in out, name
        assert "결과: 실패" in out, name

    # 다른 이름의 파일(거래일 달력 등)은 대상이 아니다.
    (tmp_path / "cal").mkdir()
    m = _meta_dir(tmp_path / "cal", {"krx_etf_basic_20260909.csv": BASE20})
    (m / "krx_trading_days_2026.csv").write_text("date\n", encoding="utf-8")
    assert chk.main(["--meta-dir", str(m)]) == 0
    assert "resolver 후보가 아니다" not in capsys.readouterr().out
