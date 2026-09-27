"""market_benchmark_store + KOSPI refresh fetcher 단위 테스트 (POC2 — 2026-05-22)."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path


from app.market_benchmark_store import (
    fetch_benchmark_history,
    fetch_existing_benchmark_close_map,
    init_benchmark_db,
    latest_benchmark_date,
    refresh_kospi_benchmark,
    upsert_benchmark_prices,
)


def test_init_benchmark_db_creates_table(tmp_path: Path):
    db = tmp_path / "market_data.sqlite"
    init_benchmark_db(db)
    with sqlite3.connect(str(db)) as con:
        cur = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='market_benchmark_daily_price'"
        )
        assert cur.fetchone() is not None


def test_upsert_and_fetch_benchmark_history(tmp_path: Path):
    db = tmp_path / "market_data.sqlite"
    rows = [
        ("2026-05-20", 2700.0),
        ("2026-05-21", 2710.0),
        ("2026-05-22", 2725.0),
    ]
    written = upsert_benchmark_prices(
        benchmark_id="KOSPI",
        benchmark_name="KOSPI",
        rows=rows,
        source="test_source",
        db_path=db,
    )
    assert written == 3
    history = fetch_benchmark_history("KOSPI", db_path=db)
    assert history == [(d, c) for d, c in rows]
    assert latest_benchmark_date("KOSPI", db_path=db) == "2026-05-22"


def test_upsert_benchmark_prices_skips_null_and_nonpositive(tmp_path: Path):
    db = tmp_path / "market_data.sqlite"
    upsert_benchmark_prices(
        benchmark_id="KOSPI",
        benchmark_name="KOSPI",
        rows=[
            ("2026-05-20", None),
            ("2026-05-21", 0.0),
            ("2026-05-22", 2725.0),
        ],
        source="test",
        db_path=db,
    )
    history = fetch_benchmark_history("KOSPI", db_path=db)
    # null + 0 은 fetch 단계에서 제외 (close > 0 가드).
    assert history == [("2026-05-22", 2725.0)]


def test_refresh_kospi_benchmark_with_stub_fetcher_ok(tmp_path: Path):
    """fetcher stub 으로 외부 FDR 의존 없이 흐름 검증."""
    db = tmp_path / "market_data.sqlite"

    class FakeDF:
        columns = ["Open", "High", "Low", "Close", "Volume"]

        def __init__(self):
            self._rows = [
                ("2026-05-20", 2700.0),
                ("2026-05-21", 2710.0),
                ("2026-05-22", 2725.0),
            ]

        def __len__(self):
            return len(self._rows)

        def iterrows(self):
            class _Idx:
                def __init__(self, s):
                    self._s = s

                def strftime(self, fmt):  # noqa: ARG002
                    return self._s

            for dt, close in self._rows:
                yield _Idx(dt), {"Close": close}

    def fake_fetcher(ticker, start, end):
        assert ticker == "KS11"
        return FakeDF()

    # 축은 tmp 캘린더 — 저장소 `state/market_meta` 를 읽지 않는다.
    cal = _calendar_dir(tmp_path, ["2026-05-19", "2026-05-20", "2026-05-21"])
    result = refresh_kospi_benchmark(
        end_date=date(2026, 5, 22),
        price_fetcher=fake_fetcher,
        db_path=db,
        calendar_dir=cal,
    )
    assert result["status"] == "ok"
    assert result["rows_written"] == 3
    assert latest_benchmark_date("KOSPI", db_path=db) == "2026-05-22"


def test_refresh_kospi_benchmark_returns_failed_on_exception(tmp_path: Path):
    db = tmp_path / "market_data.sqlite"

    def boom_fetcher(ticker, start, end):  # noqa: ARG001
        raise RuntimeError("network timeout")

    result = refresh_kospi_benchmark(
        end_date=date(2026, 5, 22),
        price_fetcher=boom_fetcher,
        db_path=db,
    )
    assert result["status"] == "failed"
    assert "RuntimeError" in result["error"]
    assert result["rows_written"] == 0
    # DB 는 생성됐지만 KOSPI rows 는 0.
    assert fetch_benchmark_history("KOSPI", db_path=db) == []


def test_refresh_kospi_benchmark_returns_failed_on_empty_df(tmp_path: Path):
    db = tmp_path / "market_data.sqlite"

    class EmptyDF:
        columns = ["Close"]

        def __len__(self):
            return 0

        def iterrows(self):
            return iter(())

    def empty_fetcher(ticker, start, end):  # noqa: ARG001
        return EmptyDF()

    result = refresh_kospi_benchmark(
        end_date=date(2026, 5, 22),
        price_fetcher=empty_fetcher,
        db_path=db,
    )
    assert result["status"] == "failed"
    assert result["error"] == "no_data"


# ── POC3-02D-OPS-01 C7 — 감지 정정 A: 멈춘 source 를 ok 로 숨기지 않는다 ─────
#
# 09-18 부터 upstream 이 행을 내주지 않았는데 배치는 매일 `kospi=ok(as_of=09-17)`
# 였다. 비어 있지 않은 반환이면 마지막 날짜와 상관없이 ok 였기 때문이다.
# 축은 08:00 기초지수 최신성 관문과 같다 — `end_date` **미만** 거래일(snapshot ·
# 없으면 평일 fallback). 임계는 기존 `MAX_STALE_TRADING_DAYS` 그대로.

# 합성 snapshot — 2026-09 평일에서 추석 연휴(09-24 · 25 · 28)를 뺀다. 평일
# fallback 과 판정이 갈리는 날을 넣어 snapshot 축을 실제로 쓰는지 본다.
_SEP_2026_TRADING_DAYS = [
    f"2026-09-{d:02d}"
    for d in (1, 2, 3, 4, 7, 8, 9, 10, 11, 14, 15, 16, 17, 18, 21, 22, 23, 29, 30)
]


def _calendar_dir(tmp_path: Path, days) -> Path:
    d = tmp_path / "market_meta"
    d.mkdir(exist_ok=True)
    (d / "krx_trading_days_2026.csv").write_text(
        "date\n" + "\n".join(days) + "\n", encoding="utf-8"
    )
    return d


class _Idx:
    def __init__(self, s):
        self._s = s

    def strftime(self, fmt):  # noqa: ARG002
        return self._s


class _RowsDF:
    """FDR DataFrame 모양만 흉내 낸다 — 외부 조회 0건."""

    columns = ["Close"]

    def __init__(self, dates):
        self._rows = [(d, 2700.0 + i) for i, d in enumerate(dates)]

    def __len__(self):
        return len(self._rows)

    def iterrows(self):
        for dt, close in self._rows:
            yield _Idx(dt), {"Close": close}


def _refresh_with(tmp_path: Path, dates, *, end_date, calendar_dir=None):
    db = tmp_path / "market_data.sqlite"
    kwargs = {} if calendar_dir is None else {"calendar_dir": calendar_dir}
    result = refresh_kospi_benchmark(
        end_date=end_date,
        price_fetcher=lambda ticker, start, end: _RowsDF(dates),
        db_path=db,
        **kwargs,
    )
    return result, db


def test_refresh_kospi_benchmark_stale_source_fails_but_keeps_rows(tmp_path: Path):
    """lag 4 — `failed` + `source_stale:` · 적재한 행은 되돌리지 않는다."""
    cal = _calendar_dir(tmp_path, _SEP_2026_TRADING_DAYS)
    dates = ["2026-09-15", "2026-09-16", "2026-09-17"]
    result, db = _refresh_with(
        tmp_path, dates, end_date=date(2026, 9, 29), calendar_dir=cal
    )
    assert result["status"] == "failed", "멈춘 source 를 ok 로 숨겼다"
    assert result["error"] == "source_stale:as_of=2026-09-17,ref=2026-09-23,lag=4"
    # 계약 ③ — 행은 유지한다(다음 적재가 180일 lookback 으로 채운다).
    assert result["rows_written"] == 3
    assert [d for d, _ in fetch_benchmark_history("KOSPI", db_path=db)] == dates
    assert latest_benchmark_date("KOSPI", db_path=db) == "2026-09-17"


def test_refresh_kospi_benchmark_lag_two_is_stale(tmp_path: Path):
    """경계 — `MAX_STALE_TRADING_DAYS=1` 을 넘는 첫 값."""
    cal = _calendar_dir(tmp_path, _SEP_2026_TRADING_DAYS)
    result, _ = _refresh_with(
        tmp_path,
        ["2026-09-18", "2026-09-21"],
        end_date=date(2026, 9, 29),
        calendar_dir=cal,
    )
    assert result["status"] == "failed"
    assert result["error"] == "source_stale:as_of=2026-09-21,ref=2026-09-23,lag=2"
    assert result["rows_written"] == 2


def test_refresh_kospi_benchmark_lag_zero_and_one_stay_ok(tmp_path: Path):
    """회귀 — 직전 거래일(lag 0) · 하루 지연(lag 1)은 지금처럼 ok.

    `end_date=09-29` 직전 거래일은 snapshot 에서 09-23 이다. 평일 fallback 이면
    09-24 · 25 · 28 이 끼어 lag 3 으로 오판된다 — snapshot 축을 쓰는지도 본다.
    """
    cal = _calendar_dir(tmp_path, _SEP_2026_TRADING_DAYS)
    for last in ("2026-09-23", "2026-09-22"):
        sub = tmp_path / last
        sub.mkdir()
        result, _ = _refresh_with(
            sub, ["2026-09-21", last], end_date=date(2026, 9, 29), calendar_dir=cal
        )
        assert result == {"status": "ok", "error": None, "rows_written": 2}, last


def test_refresh_kospi_benchmark_end_date_row_is_lag_zero(tmp_path: Path):
    """PC 수동 갱신은 `end_date=date.today()` 라 당일 행이 올 수 있다.

    축이 기준일 당일을 빼므로 그대로 재면 '축 밖' 으로 stale 이 된다. 축의
    마지막 날 이상이면 lag 0 으로 먼저 처리한다.
    """
    cal = _calendar_dir(tmp_path, _SEP_2026_TRADING_DAYS)
    result, _ = _refresh_with(
        tmp_path,
        ["2026-09-23", "2026-09-29"],
        end_date=date(2026, 9, 29),
        calendar_dir=cal,
    )
    assert result["status"] == "ok"
    assert result["error"] is None


def test_refresh_kospi_benchmark_lag_unknown_is_stale(tmp_path: Path):
    """lag 를 모르면 stale — 축 안에 없는 과거 날짜 · 파싱 불가 날짜."""
    cal = _calendar_dir(tmp_path, _SEP_2026_TRADING_DAYS)
    cases = {
        # 토요일 — 축에 없는 과거 날짜.
        "2026-09-19": "source_stale:as_of=2026-09-19,ref=2026-09-23,lag=unknown",
        # `YYYYMMDD` 는 문자열 비교로 축 끝보다 커 보인다 — 먼저 걸러야 한다.
        "20260923": "source_stale:as_of=20260923,ref=2026-09-23,lag=unknown",
    }
    for last, expected in cases.items():
        sub = tmp_path / last
        sub.mkdir()
        result, db = _refresh_with(
            sub, [last], end_date=date(2026, 9, 29), calendar_dir=cal
        )
        assert result["status"] == "failed", last
        assert result["error"] == expected
        assert result["rows_written"] == 1


def test_refresh_kospi_benchmark_weekday_fallback_year(tmp_path: Path, monkeypatch):
    """캘린더가 그 연도를 덮지 않으면 평일 fallback 축.

    `calendar_dir` 를 주지 않는다 — 기본 경로(`calendar.CALENDAR_DIR`)를 호출
    시점에 읽는 운영 경로 그대로다. 테스트는 그 상수만 tmp 로 돌린다.
    """
    from app.market_briefing import calendar as _cal

    monkeypatch.setattr(
        _cal, "CALENDAR_DIR", _calendar_dir(tmp_path, _SEP_2026_TRADING_DAYS)
    )
    end = date(2027, 3, 10)  # 수요일 · 2027 파일 없음
    ok, _ = _refresh_with(tmp_path / "a", ["2027-03-09"], end_date=end)
    assert ok["status"] == "ok"
    lag2, _ = _refresh_with(tmp_path / "b", ["2027-03-05"], end_date=end)
    assert lag2["status"] == "failed"
    assert lag2["error"] == "source_stale:as_of=2027-03-05,ref=2027-03-09,lag=2"
    # 평일 fallback 축(90 달력일)보다 오래된 최신일 — lag 를 모른다.
    old, _ = _refresh_with(tmp_path / "c", ["2026-10-01"], end_date=end)
    assert old["status"] == "failed"
    assert old["error"] == "source_stale:as_of=2026-10-01,ref=2027-03-09,lag=unknown"


# ── POC3-02D-OPS-01 C7 · 설계자 Q26(b) — `as_of` = 유효 종가가 있는 마지막 날짜 ──
#
# 반환의 마지막 날짜를 그대로 `as_of` 로 쓰면, upstream 이 새 날짜에 종가 없는
# 행(NaN · 0 이하)을 줄 때 lag 0 · `ok` 로 통과한다. 화면 계층
# (`fetch_benchmark_history`)은 유효 종가 행만 보므로 여전히 멈춘 날짜를 본다.
# 유효 종가 = 유한한 수 · 0 초과. 행은 지금처럼 전부 적재하고 되돌리지 않는다.


class _PairsDF(_RowsDF):
    """(날짜, 종가) 를 그대로 준다 — 종가 결측 · 0 이하 행을 만든다."""

    def __init__(self, pairs):
        self._rows = list(pairs)


def _refresh_pairs(tmp_path: Path, pairs, *, end_date, calendar_dir):
    db = tmp_path / "market_data.sqlite"
    result = refresh_kospi_benchmark(
        end_date=end_date,
        price_fetcher=lambda ticker, start, end: _PairsDF(pairs),
        db_path=db,
        calendar_dir=calendar_dir,
    )
    return result, db


def test_refresh_kospi_benchmark_invalid_last_close_is_not_fresh(tmp_path: Path):
    """마지막 행 종가가 무효면 그 날짜를 신선한 자료로 치지 않는다.

    09-23 행이 lag 0 이지만 종가가 무효라 `as_of` 는 09-17 이다 → lag 4 ·
    `failed`. 무효 행도 지금처럼 적재된다(되돌리지 않는다).
    """
    cal = _calendar_dir(tmp_path, _SEP_2026_TRADING_DAYS)
    # 무효 종가 → DB 에 남는 값. NaN 은 `_df_to_close_rows` 가 None 으로 바꾼다.
    cases = {
        "nan": (float("nan"), None),
        "none": (None, None),
        "zero": (0.0, 0.0),
        "negative": (-1.0, -1.0),
        "inf": (float("inf"), float("inf")),
    }
    for label, (bad, stored) in cases.items():
        sub = tmp_path / label
        sub.mkdir()
        pairs = [("2026-09-16", 2700.0), ("2026-09-17", 2710.0), ("2026-09-23", bad)]
        result, db = _refresh_pairs(
            sub, pairs, end_date=date(2026, 9, 29), calendar_dir=cal
        )
        assert result["status"] == "failed", f"{label}: 무효 종가를 신선하다고 봤다"
        assert (
            result["error"] == "source_stale:as_of=2026-09-17,ref=2026-09-23,lag=4"
        ), label
        assert result["rows_written"] == 3, label
        stored_map = fetch_existing_benchmark_close_map("KOSPI", db_path=db)
        assert stored_map == {
            "2026-09-16": 2700.0,
            "2026-09-17": 2710.0,
            "2026-09-23": stored,
        }, label


def test_refresh_kospi_benchmark_duplicate_date_uses_last_row_like_upsert(
    tmp_path: Path,
):
    """같은 날짜 행이 둘이면 적재처럼 **마지막 행**으로 `as_of` 를 정한다.

    09-23 이 유효 종가 뒤에 NaN 으로 다시 오면 DB 에는 NULL 이 남는다. 앞 행의
    유효 종가로 09-23 을 신선하다고 보면 저장값과 판정이 갈린다.
    """
    cal = _calendar_dir(tmp_path, _SEP_2026_TRADING_DAYS)
    pairs = [
        ("2026-09-16", 2700.0),
        ("2026-09-17", 2710.0),
        ("2026-09-23", 2720.0),
        ("2026-09-23", float("nan")),
    ]
    result, db = _refresh_pairs(
        tmp_path, pairs, end_date=date(2026, 9, 29), calendar_dir=cal
    )
    assert result == {
        "status": "failed",
        "error": "source_stale:as_of=2026-09-17,ref=2026-09-23,lag=4",
        "rows_written": 4,
    }
    assert fetch_existing_benchmark_close_map("KOSPI", db_path=db) == {
        "2026-09-16": 2700.0,
        "2026-09-17": 2710.0,
        "2026-09-23": None,
    }


def test_refresh_kospi_benchmark_no_valid_close_is_stale_unknown(tmp_path: Path):
    """유효 종가 행이 하나도 없으면 `as_of=unknown` · `failed` · 행은 유지."""
    cal = _calendar_dir(tmp_path, _SEP_2026_TRADING_DAYS)
    pairs = [("2026-09-21", float("nan")), ("2026-09-22", 0.0), ("2026-09-23", -1.0)]
    result, db = _refresh_pairs(
        tmp_path, pairs, end_date=date(2026, 9, 29), calendar_dir=cal
    )
    assert result == {
        "status": "failed",
        "error": "source_stale:as_of=unknown,ref=2026-09-23,lag=unknown",
        "rows_written": 3,
    }
    assert sorted(fetch_existing_benchmark_close_map("KOSPI", db_path=db)) == [
        "2026-09-21",
        "2026-09-22",
        "2026-09-23",
    ]
    # 축이 비면(기준일 앞 거래일 없음) `ref` 도 unknown 이다.
    sub = tmp_path / "axis"
    sub.mkdir()
    empty_axis = _calendar_dir(sub, ["2026-09-29", "2026-09-30"])
    result, _ = _refresh_pairs(
        sub,
        [("2026-09-23", float("nan"))],
        end_date=date(2026, 9, 29),
        calendar_dir=empty_axis,
    )
    assert result["status"] == "failed"
    assert result["error"] == "source_stale:as_of=unknown,ref=unknown,lag=unknown"
    assert result["rows_written"] == 1


def test_refresh_kospi_benchmark_valid_close_as_of_keeps_stale_rule(tmp_path: Path):
    """회귀 — 유효 종가 마지막 날짜에 기존 임계를 그대로 적용한다.

    - 중간 무효 행은 상관없다: 마지막 유효 종가 09-23 → lag 0 · ok.
    - 마지막 무효 · 직전 유효 09-22 → lag 1 · ok(임계 `MAX_STALE_TRADING_DAYS=1`).
    """
    cal = _calendar_dir(tmp_path, _SEP_2026_TRADING_DAYS)
    cases = {
        "mid_nan": [
            ("2026-09-21", 2700.0),
            ("2026-09-22", float("nan")),
            ("2026-09-23", 2710.0),
        ],
        "last_zero_lag1": [("2026-09-22", 2700.0), ("2026-09-23", 0.0)],
    }
    for label, pairs in cases.items():
        sub = tmp_path / label
        sub.mkdir()
        result, _ = _refresh_pairs(
            sub, pairs, end_date=date(2026, 9, 29), calendar_dir=cal
        )
        assert result == {
            "status": "ok",
            "error": None,
            "rows_written": len(pairs),
        }, label
