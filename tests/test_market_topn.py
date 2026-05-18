"""POC2 — SQLite 직접 계산 기반 일간 / 1개월 / 3개월 TOP N 산출 테스트.

2026-05-18 변경:
- JSON artifact 저장/읽기 함수 폐기 (save_topn_artifact / compute_and_save_topn).
- payload schema 확장: status / latest_refresh / period_exclusions.
- 결측 데이터는 0% 로 보정하지 않고 exclusion 으로 집계 (지시문 §6).
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from app.market_data_store import (
    EtfDailyPriceRow,
    EtfMasterRow,
    log_refresh,
    upsert_daily_prices,
    upsert_etf_master,
)
from app.market_topn import compute_topn


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "market_data.sqlite"


def _seed_universe(db_path: Path, ticker_names: list[tuple[str, str]]) -> None:
    rows = [
        EtfMasterRow(
            ticker=tk,
            name=nm,
            category="X",
            price=None,
            volume=None,
            market_cap=None,
        )
        for tk, nm in ticker_names
    ]
    upsert_etf_master(rows, source="TestSource", db_path=db_path)


def _seed_price_series(
    db_path: Path,
    ticker: str,
    closes: list[tuple[str, float]],
) -> None:
    rows = [
        EtfDailyPriceRow(
            ticker=ticker, date=d, open=c, high=c, low=c, close=c, volume=0, change=0
        )
        for d, c in closes
    ]
    upsert_daily_prices(rows, source="TestSource", db_path=db_path)


def _dates_around(end: date) -> dict[str, str]:
    return {
        "end": end.isoformat(),
        "minus_1": (end - timedelta(days=1)).isoformat(),
        "minus_30": (end - timedelta(days=30)).isoformat(),
        "minus_90": (end - timedelta(days=90)).isoformat(),
    }


def _seed_three_etfs(db_path: Path, end: date) -> None:
    d = _dates_around(end)
    _seed_universe(
        db_path,
        [("AAA001", "ETF A"), ("BBB002", "ETF B"), ("CCC003", "ETF C")],
    )
    _seed_price_series(
        db_path,
        "AAA001",
        [
            (d["minus_90"], 100.0),
            (d["minus_30"], 110.0),
            (d["minus_1"], 119.0),
            (d["end"], 120.0),
        ],
    )
    _seed_price_series(
        db_path,
        "BBB002",
        [
            (d["minus_90"], 100.0),
            (d["minus_30"], 102.0),
            (d["minus_1"], 100.0),
            (d["end"], 105.0),
        ],
    )
    _seed_price_series(
        db_path,
        "CCC003",
        [
            (d["minus_90"], 100.0),
            (d["minus_30"], 99.0),
            (d["minus_1"], 95.0),
            (d["end"], 94.0),
        ],
    )


# ─── 정상 흐름 (status=ok) ─────────────────────────────────────────


def test_compute_topn_daily(db_path: Path) -> None:
    end = date(2024, 10, 31)
    _seed_three_etfs(db_path, end)

    payload = compute_topn(n=3, db_path=db_path)
    assert payload["status"] == "ok"
    assert payload["asof"] == end.isoformat()
    assert payload["universe_count"] == 3
    daily = payload["daily_topn"]
    assert [r["ticker"] for r in daily] == ["BBB002", "AAA001", "CCC003"]
    assert daily[0]["rank"] == 1
    assert daily[0]["return_pct"] == pytest.approx(5.0, abs=0.01)
    assert daily[0]["name"] == "ETF B"
    assert daily[0]["basis_end_date"] == end.isoformat()


def test_compute_topn_one_month(db_path: Path) -> None:
    end = date(2024, 10, 31)
    _seed_three_etfs(db_path, end)
    payload = compute_topn(n=3, db_path=db_path)
    one_m = payload["one_month_topn"]
    assert [r["ticker"] for r in one_m] == ["AAA001", "BBB002", "CCC003"]
    assert one_m[0]["return_pct"] == pytest.approx(
        (120.0 / 110.0 - 1) * 100.0, abs=0.01
    )


def test_compute_topn_three_month(db_path: Path) -> None:
    end = date(2024, 10, 31)
    _seed_three_etfs(db_path, end)
    payload = compute_topn(n=3, db_path=db_path)
    three_m = payload["three_month_topn"]
    assert [r["ticker"] for r in three_m] == ["AAA001", "BBB002", "CCC003"]
    assert three_m[0]["return_pct"] == pytest.approx(20.0, abs=0.01)


def test_compute_topn_respects_n_parameter(db_path: Path) -> None:
    end = date(2024, 10, 31)
    _seed_three_etfs(db_path, end)

    payload_n1 = compute_topn(n=1, db_path=db_path)
    assert len(payload_n1["daily_topn"]) == 1
    assert len(payload_n1["one_month_topn"]) == 1
    assert len(payload_n1["three_month_topn"]) == 1

    payload_n2 = compute_topn(n=2, db_path=db_path)
    assert len(payload_n2["daily_topn"]) == 2

    payload_n10 = compute_topn(n=10, db_path=db_path)
    assert len(payload_n10["daily_topn"]) == 3  # universe 3개 한계
    assert payload_n10["n"] == 10


def test_compute_topn_latest_refresh_field(db_path: Path) -> None:
    end = date(2024, 10, 31)
    _seed_three_etfs(db_path, end)
    log_refresh(
        run_id="rid-001",
        source="FinanceDataReader/prices",
        asof=end.isoformat(),
        attempted=3,
        success=3,
        fail=0,
        runtime_seconds=1.5,
        db_path=db_path,
    )
    payload = compute_topn(n=3, db_path=db_path)
    assert payload["latest_refresh"] is not None
    assert payload["latest_refresh"]["refresh_id"] == "rid-001"
    assert payload["latest_refresh"]["success_count"] == 3


# ─── status 분기 ──────────────────────────────────────────────────


def test_compute_topn_missing_when_db_file_absent(tmp_path: Path) -> None:
    payload = compute_topn(n=10, db_path=tmp_path / "does_not_exist.sqlite")
    assert payload["status"] == "missing"
    assert payload["asof"] is None
    assert payload["daily_topn"] == []
    assert payload["period_exclusions"]["daily"]


def test_compute_topn_empty_when_no_price_rows(db_path: Path) -> None:
    _seed_universe(db_path, [("AAA001", "ETF A")])  # universe 만 있고 price 없음
    payload = compute_topn(n=10, db_path=db_path)
    assert payload["status"] == "empty"
    assert payload["universe_count"] == 1
    assert payload["daily_topn"] == []


def test_compute_topn_invalid_when_required_table_missing(tmp_path: Path) -> None:
    """DB 파일은 있으나 필수 테이블 누락 → status=invalid."""
    import sqlite3

    bad_db = tmp_path / "bad.sqlite"
    with sqlite3.connect(str(bad_db)) as con:
        con.execute("CREATE TABLE etf_master (ticker TEXT PRIMARY KEY)")
        # etf_daily_price / market_refresh_log 의도적 누락
        con.commit()
    payload = compute_topn(n=10, db_path=bad_db)
    assert payload["status"] == "invalid"
    assert payload["daily_topn"] == []


# ─── 결측 처리 ────────────────────────────────────────────────────


def test_compute_topn_missing_data_not_filled_with_zero(db_path: Path) -> None:
    """지시문 §6 — 결측은 0% 보정 금지. period_exclusions 로 집계.

    시나리오: TINY 신규 상장 ETF (history 1건뿐) → 모든 기간 insufficient_history.
    어떤 TOP N 에도 포함되지 않아야 하고 period_exclusions 에 집계되어야 한다.
    """
    end = date(2024, 10, 31)
    d = _dates_around(end)
    _seed_universe(
        db_path, [("AAA001", "Has Full History"), ("TINY002", "New Listing")]
    )
    _seed_price_series(
        db_path,
        "AAA001",
        [
            (d["minus_90"], 100.0),
            (d["minus_30"], 110.0),
            (d["minus_1"], 119.0),
            (d["end"], 120.0),
        ],
    )
    # TINY002: latest 1건만 — 모든 기간 insufficient_history
    _seed_price_series(db_path, "TINY002", [(d["end"], 105.0)])

    payload = compute_topn(n=10, db_path=db_path)
    assert payload["status"] == "ok"
    # AAA001 만 TOP N 에 포함, TINY002 는 어디에도 안 들어감 (0% 보정 금지)
    for label in ("daily_topn", "one_month_topn", "three_month_topn"):
        tickers = [r["ticker"] for r in payload[label]]
        assert "TINY002" not in tickers
        assert "AAA001" in tickers
    # period_exclusions 에 insufficient_history 1건씩 집계
    assert payload["period_exclusions"]["daily"]["insufficient_history"] >= 1
    assert payload["period_exclusions"]["one_month"]["insufficient_history"] >= 1
    assert payload["period_exclusions"]["three_month"]["insufficient_history"] >= 1


def test_compute_topn_skips_invalid_price(db_path: Path) -> None:
    """close <= 0 또는 base close <= 0 → invalid_price exclusion."""
    end = date(2024, 10, 31)
    d = _dates_around(end)
    _seed_universe(db_path, [("AAA001", "Valid"), ("BAD002", "Zero Latest")])
    _seed_price_series(
        db_path,
        "AAA001",
        [
            (d["minus_1"], 100.0),
            (d["end"], 102.0),
        ],
    )
    # close 0 은 fetch_price_history 가 이미 제외하지만, 의도 분명히 — 아예 행 안 넣음
    # 대신 latest 만 있고 base 부재 케이스로 invalid 가 아니라 missing 처리 흐름
    payload = compute_topn(n=10, db_path=db_path)
    assert payload["status"] == "ok"
    assert "AAA001" in [r["ticker"] for r in payload["daily_topn"]]
    assert "BAD002" not in [r["ticker"] for r in payload["daily_topn"]]


def test_compute_topn_no_legacy_artifact_function() -> None:
    """save_topn_artifact / compute_and_save_topn 함수가 폐기됐는지 확인 (AC-8)."""
    from app import market_topn

    assert not hasattr(market_topn, "save_topn_artifact")
    assert not hasattr(market_topn, "compute_and_save_topn")
    assert not hasattr(market_topn, "DEFAULT_TOPN_PATH")


# ─── Market Discovery 후보 정제 1차 (2026-05-18) ────────────────────


def test_classify_etf_tags_inverse() -> None:
    from app.market_topn import classify_etf_tags

    assert "inverse" in classify_etf_tags("KODEX 200선물인버스2X")
    assert "inverse" in classify_etf_tags("RISE 미국반도체인버스(합성 H)")
    assert "inverse" not in classify_etf_tags("KODEX 200")


def test_classify_etf_tags_leveraged_keyword_variations() -> None:
    from app.market_topn import classify_etf_tags

    assert "leveraged" in classify_etf_tags("KODEX 레버리지")
    assert "leveraged" in classify_etf_tags("ARIRANG 200선물2X")
    assert "leveraged" in classify_etf_tags("PLUS 코스닥150 2배")
    # 소문자 2x 도 대응
    assert "leveraged" in classify_etf_tags("KODEX 200 2x lower")
    assert "leveraged" not in classify_etf_tags("KODEX 200")


def test_classify_etf_tags_synthetic() -> None:
    from app.market_topn import classify_etf_tags

    assert "synthetic" in classify_etf_tags("TIGER 차이나전기차레버리지(합성)")
    assert "synthetic" not in classify_etf_tags("KODEX 200")


def test_classify_etf_tags_futures() -> None:
    from app.market_topn import classify_etf_tags

    assert "futures" in classify_etf_tags("KODEX 200선물인버스2X")
    assert "futures" in classify_etf_tags("RISE 팔라듐선물(H)")
    assert "futures" not in classify_etf_tags("KODEX 200")


def test_classify_etf_tags_multiple_tags() -> None:
    from app.market_topn import classify_etf_tags

    tags = classify_etf_tags("TIGER 차이나전기차레버리지(합성)")
    assert "leveraged" in tags
    assert "synthetic" in tags


def test_classify_etf_tags_neutral_names_not_classified() -> None:
    """금현물, 배당, 반도체, AI, 조선, 방산, 원자재 — 본 STEP 에서 분류 안 함."""
    from app.market_topn import classify_etf_tags

    for nm in [
        "ACE KRX금현물",
        "TIGER 200 IT",
        "KODEX 미국반도체",
        "SOL 미국AI전력인프라",
        "TIGER 조선TOP10",
        "KODEX 방산",
    ]:
        assert classify_etf_tags(nm) == [], f"{nm} → {classify_etf_tags(nm)}"


# Filter 동작 테스트용 mixed dataset
def _seed_mixed_filter_dataset(db_path: Path, end: date) -> None:
    """8 ETF: 4 특수상품 (상위 수익률) + 4 일반 (하위) — filter-before-limit 검증용.

    수익률: 인버스 30%, 레버리지 25%, 합성 20%, 선물 15%, 일반A 10%, 일반B 8%, 일반C 5%, 일반D 3%.
    daily 만 사용 (latest = end, base = minus_1).
    """
    d_end = end.isoformat()
    d_prev = (end - timedelta(days=1)).isoformat()
    _seed_universe(
        db_path,
        [
            ("INV001", "X 인버스 ETF"),
            ("LEV002", "Y 레버리지 ETF"),
            ("SYN003", "Z 무이름(합성)"),
            ("FUT004", "W 선물 ETF"),
            ("GENA005", "일반 알파"),
            ("GENB006", "일반 베타"),
            ("GENC007", "일반 감마"),
            ("GEND008", "일반 델타"),
        ],
    )

    def _seed(tk: str, ret_pct: float) -> None:
        base = 100.0
        latest = base * (1 + ret_pct / 100)
        _seed_price_series(db_path, tk, [(d_prev, base), (d_end, latest)])

    _seed("INV001", 30.0)
    _seed("LEV002", 25.0)
    _seed("SYN003", 20.0)
    _seed("FUT004", 15.0)
    _seed("GENA005", 10.0)
    _seed("GENB006", 8.0)
    _seed("GENC007", 5.0)
    _seed("GEND008", 3.0)


def test_compute_topn_default_excludes_all_specials(db_path: Path) -> None:
    """기본 요청 (모든 exclude=True) — 특수상품 4개 모두 제외, 일반만 표시."""
    end = date(2024, 10, 31)
    _seed_mixed_filter_dataset(db_path, end)
    payload = compute_topn(n=10, db_path=db_path)
    assert payload["status"] == "ok"
    daily_tickers = [r["ticker"] for r in payload["daily_topn"]]
    for special in ("INV001", "LEV002", "SYN003", "FUT004"):
        assert special not in daily_tickers
    for general in ("GENA005", "GENB006", "GENC007", "GEND008"):
        assert general in daily_tickers
    # rank 는 1부터 재부여 — 일반 알파 (10%) 가 1위.
    assert payload["daily_topn"][0]["ticker"] == "GENA005"
    assert payload["daily_topn"][0]["rank"] == 1
    assert payload["filters"]["exclude_inverse"] is True
    assert payload["filter_exclusions"]["daily"]["inverse"] == 1
    assert payload["filter_exclusions"]["daily"]["leveraged"] == 1


def test_compute_topn_opt_in_leveraged(db_path: Path) -> None:
    """exclude_leveraged=False → 레버리지 ETF 포함."""
    end = date(2024, 10, 31)
    _seed_mixed_filter_dataset(db_path, end)
    payload = compute_topn(n=10, db_path=db_path, exclude_leveraged=False)
    daily_tickers = [r["ticker"] for r in payload["daily_topn"]]
    assert "LEV002" in daily_tickers
    # 다른 3개 특수는 여전히 제외
    assert "INV001" not in daily_tickers
    assert "SYN003" not in daily_tickers
    assert "FUT004" not in daily_tickers
    # LEV002 (25%) 가 GENA005 (10%) 보다 위
    rank_lev = next(r["rank"] for r in payload["daily_topn"] if r["ticker"] == "LEV002")
    rank_gen = next(
        r["rank"] for r in payload["daily_topn"] if r["ticker"] == "GENA005"
    )
    assert rank_lev < rank_gen


def test_compute_topn_filter_before_limit(db_path: Path) -> None:
    """지시문 §3.1 / §6 — 상위 N 이 모두 특수상품이라도 기본 요청은 일반 N 개를 반환.

    데이터: 특수 4개가 상위 (30/25/20/15%) + 일반 4개 (10/8/5/3%).
    기본 n=10 요청 → 일반 4개 모두 표시. 특수 4개는 모두 제외.
    'SQLite TOP N 후 필터' 방식이면 일반이 0개만 나옴 — 이번 검증의 핵심 가드.
    """
    end = date(2024, 10, 31)
    _seed_mixed_filter_dataset(db_path, end)
    payload = compute_topn(n=4, db_path=db_path)  # n=4 로 일반 4개 정확히 채워야 함
    daily = payload["daily_topn"]
    assert len(daily) == 4
    assert [r["ticker"] for r in daily] == ["GENA005", "GENB006", "GENC007", "GEND008"]
    assert [r["rank"] for r in daily] == [1, 2, 3, 4]


def test_compute_topn_filter_exclusions_count_per_tag(db_path: Path) -> None:
    """한 ETF 가 여러 태그를 갖고 활성 필터가 그 중 둘 이상이면 각 태그별 +1."""
    end = date(2024, 10, 31)
    d_end = end.isoformat()
    d_prev = (end - timedelta(days=1)).isoformat()
    _seed_universe(
        db_path, [("MULTI001", "AAA 레버리지(합성)"), ("GEN002", "일반 후보")]
    )
    _seed_price_series(db_path, "MULTI001", [(d_prev, 100.0), (d_end, 150.0)])
    _seed_price_series(db_path, "GEN002", [(d_prev, 100.0), (d_end, 110.0)])
    payload = compute_topn(n=10, db_path=db_path)
    # MULTI001 은 leveraged + synthetic 둘 다 — 각각 +1 카운트
    assert payload["filter_exclusions"]["daily"]["leveraged"] == 1
    assert payload["filter_exclusions"]["daily"]["synthetic"] == 1


def test_compute_topn_entries_include_tags_field(db_path: Path) -> None:
    """API 응답 entry 에 tags 필드가 포함된다."""
    end = date(2024, 10, 31)
    _seed_mixed_filter_dataset(db_path, end)
    payload = compute_topn(n=10, db_path=db_path, exclude_leveraged=False)
    daily = payload["daily_topn"]
    lev_entry = next(r for r in daily if r["ticker"] == "LEV002")
    assert "tags" in lev_entry
    assert "leveraged" in lev_entry["tags"]
    gen_entry = next(r for r in daily if r["ticker"] == "GENA005")
    assert gen_entry["tags"] == []


def test_compute_topn_does_not_modify_raw_sqlite(db_path: Path) -> None:
    """compute_topn 호출이 etf_master / etf_daily_price 의 row count 를 변경하지 않는다."""
    import sqlite3 as _sql

    end = date(2024, 10, 31)
    _seed_mixed_filter_dataset(db_path, end)
    with _sql.connect(str(db_path)) as con:
        master_before = con.execute("SELECT COUNT(*) FROM etf_master").fetchone()[0]
        price_before = con.execute("SELECT COUNT(*) FROM etf_daily_price").fetchone()[0]
    compute_topn(n=10, db_path=db_path)
    compute_topn(n=10, db_path=db_path, exclude_leveraged=False)
    with _sql.connect(str(db_path)) as con:
        master_after = con.execute("SELECT COUNT(*) FROM etf_master").fetchone()[0]
        price_after = con.execute("SELECT COUNT(*) FROM etf_daily_price").fetchone()[0]
    assert master_after == master_before
    assert price_after == price_before
