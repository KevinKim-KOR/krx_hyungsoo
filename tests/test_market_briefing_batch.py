"""POC3-OPS-02B-2 — 07:20 배치 연결 계약 test.

설계자 §M-2·§M-8 대응. 합성 fixture 와 임시 DB 만 쓴다.
**외부 조회 0건 · 라이브 DB 미접근 · 발송 0건.**
"""

from __future__ import annotations

import ast
import inspect
import json
from datetime import date
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
