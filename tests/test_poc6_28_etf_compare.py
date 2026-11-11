"""POC6-28 — 「ETF 비교하기」 요약(`GET /market/etf-compare/summary`).

PLAN §3 · 판정 2026-11-11: 공통 기간 모집단 · 네 기준(기간 다름 · 값 없음 · 0.00%) · 가격 시점(15:30 경계) ·
분류(업종 · 기초지수 · 미분류 · 광의지수 · 전략형) · 공통 구성종목 상태 · 노출 · 보유 연결 · 국면.
임시 DB · 임시 CSV · 임시 사전만 쓴다(라이브 DB · 라이브 보유 파일을 열지 않음).
"""

from __future__ import annotations

import csv
import io
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app import api_etf_compare
from app.market_briefing.official_csv import EXPECTED_HEADER
from app.market_data_store import init_db
from app.etf_constituents_store import init_constituents_db
from app.pc_etf_compare_groups import (
    CONS_NO_OVERLAP,
    CONS_NO_SAMPLE,
    CONS_OK,
    CONS_SINGLE,
    classify_etf,
    common_constituents,
    constituent_key,
)
from app.pc_etf_compare_summary import build_summary, price_state

END = "2026-11-10"
AFTER = "2026-11-11T00:30:00Z"  # 11/11 09:30 KST — 끝일 다음 날 저장
FILTERS = {
    k: True
    for k in (
        "exclude_inverse",
        "exclude_leveraged",
        "exclude_synthetic",
        "exclude_futures",
    )
}
DICTIONARY = {
    "반도체": ["AI반도체", "반도체"],
    "조선": ["조선"],
    "로봇": ["로봇"],
    "바이오": ["바이오"],
}


def _bdays(end: str = END, n: int = 140) -> list[str]:
    out, d = [], date.fromisoformat(end)
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d -= timedelta(days=1)
    return list(reversed(out))


DAYS = _bdays()


def _put(
    db: Path,
    ticker: str,
    closes: list[Optional[float]],
    days: Optional[list[str]] = None,
    fetched: Optional[str] = AFTER,
    last_fetched: Optional[str] = None,
) -> None:
    n = len(closes)
    days = days if days is not None else DAYS[-n:]
    rows, prev = [], None
    for i, (d, c) in enumerate(zip(days, closes)):
        ch = (c / prev - 1.0) if (c and prev) else 0.0
        fa = (
            last_fetched
            if (last_fetched is not None and i == len(closes) - 1)
            else fetched
        )
        rows.append((ticker, d, c, c, c, c, 1000, ch, "FinanceDataReader", fa))
        prev = c if c else prev
    with sqlite3.connect(db) as con:
        con.executemany(
            "INSERT INTO etf_daily_price(ticker, date, open, high, low, close, volume,"
            " change, source, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            rows,
        )


def _master(db: Path, items: dict[str, str]) -> None:
    with sqlite3.connect(db) as con:
        con.executemany(
            "INSERT INTO etf_master(ticker, name, category, price, volume, market_cap,"
            " source, last_seen_at)"
            " VALUES (?,?,NULL,NULL,NULL,NULL,'test','2026-11-10T00:00:00Z')",
            list(items.items()),
        )


def _cons(db: Path, etf: str, asof: str, items: list[tuple[str, str, str]]) -> None:
    init_constituents_db(db)
    with sqlite3.connect(db) as con:
        con.executemany(
            "INSERT INTO etf_constituents(etf_ticker, asof, source, rank,"
            " constituent_ticker, constituent_name, weight_pct, etf_name,"
            " constituent_key, constituent_isin, constituent_reuters_code,"
            " market_type, created_at)"
            " VALUES (?,?,'naver',?,?,?,5.0,NULL,?,NULL,NULL,NULL,'x')",
            [(etf, asof, i + 1, t, n, k) for i, (t, n, k) in enumerate(items)],
        )


def _trend(n: int, start: float, end_v: float) -> list[float]:
    return [round(start + (end_v - start) * i / (n - 1), 4) for i in range(n)]


@pytest.fixture
def market(tmp_path: Path) -> Path:
    """069500 140일 하락 · ETF 여러 개(공통 기간 · 늦은 상장 · 끝일 없음 · 인버스 · 가격 없음)."""
    db = tmp_path / "market_data.sqlite"
    init_db(db)
    _master(
        db,
        {
            "069500": "KODEX 200",
            "AAA001": "가 반도체",
            "AAA002": "나 반도체",
            "AAA003": "다 조선",
            "AAA004": "라 평탄",
            "AAA005": "마 늦은상장1개월",
            "AAA006": "바 늦은상장3개월",
            "AAA007": "사 끝일없음",
            "AAA008": "아 인버스",
            "AAA009": "자 가격없음",
            "AAA010": "차 지수",
        },
    )
    _put(db, "069500", _trend(140, 120.0, 100.0))
    _put(
        db, "AAA001", [100.0] * 120 + _trend(20, 100.0, 60.0)
    )  # 최근 20일 급락 → 하위 1위
    _put(db, "AAA002", _trend(140, 100.0, 70.0))
    _put(db, "AAA003", _trend(140, 100.0, 130.0))  # 상위
    _put(db, "AAA004", [100.0] * 140)  # 0.00% · 고점 대비 0.00%
    _put(db, "AAA005", _trend(10, 100.0, 90.0))  # 1개월 시작일 다름 → 모집단 밖
    _put(db, "AAA006", _trend(40, 100.0, 80.0))  # 1개월 정상 · 3개월 기간 다름
    _put(db, "AAA007", _trend(139, 100.0, 90.0), days=DAYS[:-1])  # 끝일 없음
    _put(db, "AAA008", _trend(140, 100.0, 150.0))  # 인버스 태그 → 제외 조건
    _put(db, "AAA010", _trend(140, 100.0, 95.0))
    return db


OFFICIAL = {
    "AAA001": {
        "기초지수명": "FnGuide AI반도체 지수",
        "기초시장분류": "국내",
        "기초자산분류": "주식",
    },
    "AAA002": {
        "기초지수명": "KRX 반도체 타겟 위클리 커버드콜 지수",
        "기초시장분류": "국내",
        "기초자산분류": "주식",
    },
    "AAA003": {
        "기초지수명": "KRX 조선 지수",
        "기초시장분류": "국내",
        "기초자산분류": "주식",
    },
    "AAA004": {
        "기초지수명": "KIS 국고채 지수",
        "기초시장분류": "국내",
        "기초자산분류": "채권",
    },
    "AAA006": {
        "기초지수명": "Solactive Robotics Index",
        "기초시장분류": "해외",
        "기초자산분류": "주식",
    },
    "AAA010": {"기초지수명": "코스닥", "기초시장분류": "국내", "기초자산분류": "주식"},
}


def _run(
    db: Path, basis: str = "one_month", held: Optional[list[str]] = None, **kw: Any
) -> dict[str, Any]:
    return build_summary(
        db_path=db,
        basis=basis,
        filters=FILTERS,
        official=kw.get("official", OFFICIAL),
        official_meta={},
        dictionary=kw.get("dictionary", DICTIONARY),
        dictionary_meta={},
        held_tickers=held,
        holdings_status="ok",
    )


# ── 모집단 · 공통 기간 ─────────────────────────────────────────────────────


def test_population_uses_common_period_and_counts_exclusions(market: Path) -> None:
    r = _run(market)
    assert r["status"] == "ok"
    assert r["period"]["end"] == END
    c = r["counts"]
    assert (c["filter_excluded"], c["start_differs"], c["end_differs"]) == (1, 1, 1)
    # 069500 · 001 · 002 · 003 · 004 · 006 · 010 = 7(069500 도 ETF 목록의 한 종목) · 009 는 가격 없음
    assert c["population"] == 7 and c["no_price"] == 1
    tops = [x["ticker"] for x in r["top"]]
    assert (
        tops[0] == "AAA003"
        and "AAA005" not in tops
        and "AAA007" not in tops
        and "AAA008" not in tops
    )
    assert [x["ticker"] for x in r["bottom"]][0] == "AAA001"
    assert sorted(r["in_both"]) == sorted(tops)  # 모집단 < 60 → 양쪽 공통
    assert all(x["basis_return"]["start"] == r["period"]["start"] for x in r["top"])


def test_missing_kodex_end_gives_no_common_period(tmp_path: Path) -> None:
    db = tmp_path / "m.sqlite"
    init_db(db)
    _master(db, {"069500": "KODEX 200", "AAA001": "가"})
    _put(db, "069500", _trend(60, 100.0, 90.0), days=DAYS[-61:-1])
    _put(db, "AAA001", _trend(60, 100.0, 90.0))
    r = _run(db)
    assert r["status"] == "no_common_period" and r["holdings"]["items"] == []


def test_missing_and_empty_db(tmp_path: Path) -> None:
    assert _run(tmp_path / "none.sqlite")["status"] == "missing"
    db = tmp_path / "e.sqlite"
    init_db(db)
    assert _run(db)["status"] == "empty"


def test_stock_price_rows_stay_out_of_population_and_end_date(market: Path) -> None:
    """같은 가격 표의 보유 개별 주식(ETF 목록 밖)은 모집단 · 끝일에 들어가지 않는다(독립 검토 HIGH)."""
    _put(market, "005930", _trend(140, 100.0, 40.0))  # 급락 — 들어가면 하위 1위가 된다
    with sqlite3.connect(
        market
    ) as con:  # ETF 보다 하루 늦은 주식 행(보유 현재가 업데이트)
        con.execute(
            "INSERT INTO etf_daily_price(ticker, date, open, high, low, close, volume, change,"
            " source, fetched_at) VALUES ('005930', '2026-11-11', 40, 40, 40, 40, 1, 0,"
            " 'FinanceDataReader', '2026-11-11T00:30:00Z')"
        )
    r = _run(market, held=["005930"])
    assert r["status"] == "ok" and r["period"]["end"] == END
    assert r["counts"]["universe"] == 11 and r["counts"]["population"] == 7
    assert "005930" not in [x["ticker"] for x in r["top"] + r["bottom"]]
    h = r["holdings"]["items"][0]
    assert h["is_stock"] and h["out_reason"] == "stock" and h["in_population"] is False
    # 보유 가격 흐름은 보유 근거와 같은 행 조건(최신 저장 행)이라 11/11 행을 보고, 기준일이 달라 비교하지 않는다.
    assert h["end_price"]["date"] == "2026-11-11"
    assert h["price_flow"]["comparison"] == "date_mismatch"


def test_missing_kodex_window_is_missing_not_period_differs(market: Path) -> None:
    """069500 의 고점 창을 못 정하면(20저장일 안 가격 기준 끊김) ETF 값은 '값 없음'이다."""
    with sqlite3.connect(market) as con:
        con.execute(
            "UPDATE etf_daily_price SET change = 0.5 WHERE ticker = '069500' AND date = ?",
            (DAYS[-3],),
        )
    r = _run(market)
    assert r["criteria_periods"]["drawdown"] is None
    dd = r["top"][0]["criteria"]["drawdown"]
    assert dd["status"] == "missing" and dd["reason"] == "kodex_window_unknown"


# ── 네 기준(판정 §5) ──────────────────────────────────────────────────────


def test_criteria_period_differs_missing_and_zero_is_valid(market: Path) -> None:
    rows = {x["ticker"]: x for x in _run(market)["top"]}
    late = rows["AAA006"]["criteria"]
    assert late["one_month"]["status"] == "ok"
    assert (
        late["three_month"]["status"] == "period_differs"
        and late["three_month"]["value"] is not None
    )
    flat = rows["AAA004"]["criteria"]
    assert flat["one_month"]["value"] == 0.0 and flat["one_month"]["status"] == "ok"
    assert flat["drawdown"]["status"] == "ok" and flat["drawdown"]["value"] == 0.0


def test_same_period_kodex_is_one_month_minus_kodex_return(market: Path) -> None:
    r = _run(market)
    k = r["kodex200"]["one_month_return_pct"]
    # 보유 비교는 price_flow(같은 응답)로 한다 — KODEX 200 가격 목록은 보내지 않는다(검증자 r2 F4).
    assert "closes" not in r["kodex200"]
    for x in r["top"]:
        s = x["criteria"]["same_kodex_1m"]
        assert s["status"] == "ok" and s["kodex200_return_pct"] == pytest.approx(
            k, abs=1e-4
        )
        assert s["value"] == pytest.approx(
            x["criteria"]["one_month"]["value"] - k, abs=2e-4
        )


def test_drawdown_window_must_match_kodex_window(market: Path) -> None:
    r = _run(market)
    w = r["criteria_periods"]["drawdown"]
    dd = {x["ticker"]: x["criteria"]["drawdown"] for x in r["top"]}
    assert all(
        (d["start"], d["end"]) == (w["start"], w["end"])
        for d in dd.values()
        if d["status"] == "ok"
    )


def test_daily_basis_uses_previous_row(market: Path) -> None:
    r = _run(market, basis="daily")
    assert r["status"] == "ok" and r["period"] == {"start": DAYS[-2], "end": DAYS[-1]}


# ── 가격 시점(판정 §4 · PLAN §3-7) ────────────────────────────────────────


@pytest.mark.parametrize(
    ("fetched", "state"),
    [
        ("2026-11-10T04:18:02Z", "intraday"),  # 13:18 KST
        ("2026-11-10T06:29:59Z", "intraday"),  # 15:29:59 KST
        ("2026-11-10T06:30:00Z", "after_close"),  # 15:30:00 KST
        ("2026-11-11T00:30:00+00:00", "after_close"),  # 다음 날
        ("2026-11-09T14:59:59Z", "unknown"),  # 11/9 23:59:59 KST — 가격 날짜보다 앞섬
        ("2026-11-10T13:18:02", "unknown"),  # 시간대 없음
        ("", "unknown"),
        (None, "unknown"),
        ("어제", "unknown"),
    ],
)
def test_price_state_boundaries(fetched: Optional[str], state: str) -> None:
    assert price_state(END, fetched)["state"] == state


def test_intraday_end_rows_make_summary_and_regime_provisional(
    tmp_path: Path, market: Path
) -> None:
    with sqlite3.connect(market) as con:
        con.execute(
            "UPDATE etf_daily_price SET fetched_at = '2026-11-10T04:18:02Z' WHERE date = ?",
            (END,),
        )
    r = _run(market)
    ps = r["price_state"]
    assert (
        ps["provisional"] is True and ps["intraday_count"] == r["counts"]["population"]
    )
    assert ps["intraday_fetched_min"] == "2026-11-10T13:18:02+09:00"
    assert (
        r["regime"]["price"]["state"] == "intraday"
        and r["regime"]["same_end_date"] is True
    )
    assert all(x["end_price"]["state"] == "intraday" for x in r["top"])


# ── 분류 · 묶음 · 공통 구성종목 ───────────────────────────────────────────


def test_classification_kinds() -> None:
    c = classify_etf("AAA001", "가", OFFICIAL, DICTIONARY)
    assert (c["kind"], c["sector"], c["strategy"]) == ("sector", "반도체", False)
    cc = classify_etf("AAA002", "나", OFFICIAL, DICTIONARY)
    assert (cc["kind"], cc["sector"], cc["strategy"]) == ("sector", "반도체", True)
    broad = classify_etf("AAA010", "차", OFFICIAL, DICTIONARY)
    assert (
        broad["kind"] == "index" and broad["broad"] is True and broad["sector"] is None
    )
    assert classify_etf("ZZZ", "없음", OFFICIAL, DICTIONARY)["kind"] == "unclassified"
    assert (
        classify_etf("AAA001", "가", OFFICIAL, None)["kind"] == "index"
    )  # 사전 없음 → 지수별만
    conflict = {
        "기초지수명": "조선 로봇 지수",
        "기초시장분류": "국내",
        "기초자산분류": "주식",
    }
    assert (
        classify_etf("X", "x", {"X": conflict}, DICTIONARY)["kind"] == "index"
    )  # 같은 길이 충돌
    longer = {
        "기초지수명": "반도체 조선 지수",
        "기초시장분류": "국내",
        "기초자산분류": "주식",
    }
    assert (
        classify_etf("Y", "y", {"Y": longer}, DICTIONARY)["sector"] == "반도체"
    )  # 긴 낱말 우선


def test_groups_overview_and_both_sides(market: Path) -> None:
    r = _run(market)
    bottom = r["groups"]["bottom"]
    semi = next(g for g in bottom if g["name"] == "반도체")
    assert (
        semi["etf_count"] == 2
        and semi["distinct_index_count"] == 2
        and semi["strategy_count"] == 1
    )
    assert "반도체" in r["both_side_sectors"] and semi["both_sides"] is True
    ov = r["overview"]["bottom"]
    assert ov["total"] == len(r["bottom"]) and ov["sector_etf_count"] >= 2
    assert ov["unclassified_count"] == 1  # 069500 은 이 시험 CSV 에 없음


def _ci(*keys: tuple[Optional[str], Optional[str], Optional[str]]) -> dict[str, Any]:
    items = []
    for t, n, k in keys:
        it = {"ticker": t, "name": n, "key": k}
        it["match_key"] = constituent_key(it)
        items.append(it)
    return {"asof": "2026-10-02", "items": items}


def test_common_constituents_states_and_overseas_key() -> None:
    cons = {
        "E1": _ci((None, "마이크론", "MU.O"), ("000660", "SK하이닉스", "000660")),
        "E2": _ci(("", "마이크론 테크놀로지", "MU.O"), (None, "샌디스크", "SNDK.O")),
        "E3": _ci((None, "다른", "ZZ.O")),
    }
    assert common_constituents(["X", "Y"], cons)["status"] == CONS_NO_SAMPLE
    assert common_constituents(["E1", "Y"], cons)["status"] == CONS_SINGLE
    assert common_constituents(["E1", "E3"], cons)["status"] == CONS_NO_OVERLAP
    ok = common_constituents(["E1", "E2", "E3"], cons)
    assert ok["status"] == CONS_OK and [c["key"] for c in ok["common"]] == ["MU.O"]
    assert ok["etf_with_data"] == 3 and ok["etf_total"] == 3
    assert constituent_key({"key": None, "ticker": "", "name": "이름"}) == "N:이름"
    assert constituent_key({"key": "", "ticker": "", "name": ""}) is None


# ── 보유 연결(판정 §4) ────────────────────────────────────────────────────


def test_holdings_links_reasons_side_and_exposure(market: Path) -> None:
    _cons(
        market,
        "AAA001",
        "2026-10-02",
        [("005930", "삼성전자", "005930"), ("", "마이크론", "MU.O")],
    )
    _cons(market, "AAA002", "2026-10-02", [("005930", "삼성전자", "005930")])
    _cons(
        market,
        "AAA010",
        "2026-06-22",
        [("", "마이크론", "MU.O"), ("035420", "NAVER", "035420")],
    )
    r = _run(
        market,
        held=[
            "AAA001",
            "AAA010",
            "AAA004",
            "AAA005",
            "AAA008",
            "AAA009",
            "005930",
            "AAA003",
        ],
    )
    h = {x["ticker"]: x for x in r["holdings"]["items"]}
    assert h["005930"]["is_stock"] and h["005930"]["out_reason"] == "stock"
    assert h["005930"]["exposure"]["status"] == "ok"  # 하위 ETF 구성에 그 종목코드
    assert h["AAA008"]["out_reason"] == "filter_excluded"
    assert h["AAA009"]["out_reason"] == "no_price"
    assert h["AAA005"]["out_reason"] == "period_differs"
    assert h["AAA001"]["side"] == "bottom" and h["AAA001"]["side_rank"] == 1
    # 모집단 7 < 60 — 상위에도 들어 있으면 그 순위도 함께(검증자 r1 F3)
    assert h["AAA001"]["top_rank"] == 7 and "AAA001" in r["in_both"]
    assert h["AAA001"]["end_price"]["date"] == END
    assert h["AAA001"]["basis_return"]["value"] < 0
    # 자기 자신과는 비교하지 않는다 — AAA001 의 MU.O 는 AAA010, 005930 은 AAA002 와 겹친다(AAA001 자신 제외)
    expo = h["AAA001"]["exposure"]
    assert expo["status"] == "ok"
    assert {o["key"]: o["etfs"] for o in expo["overlaps"]} == {
        "MU.O": ["AAA010"],
        "005930": ["AAA002"],
    }
    assert expo["holding_asof"] == "2026-10-02" and expo["compared_etf_count"] == 2
    assert (
        h["AAA004"]["exposure"]["status"] == "no_constituents"
        and not h["AAA004"]["has_constituents"]
    )
    assert all(x["held"] == (x["ticker"] in h) for x in r["top"])


# ── API · 자료 위치 ──────────────────────────────────────────────────────


def _write_csv(meta: Path) -> None:
    meta.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(EXPECTED_HEADER)
    for tk, row in OFFICIAL.items():
        vals = {h: "x" for h in EXPECTED_HEADER}
        vals.update({"단축코드": tk, **row})
        w.writerow([vals[h] for h in EXPECTED_HEADER])
    (meta / "krx_etf_basic_20260927.csv").write_bytes(buf.getvalue().encode("cp949"))


@pytest.fixture
def client(market: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    _write_csv(tmp_path / "meta")
    dic = tmp_path / "dict.json"
    dic.write_text(
        json.dumps(
            {"schema_version": "intraday_token_dictionary.v1", "sectors": DICTIONARY},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(api_etf_compare, "MARKET_DB_PATH", market)
    monkeypatch.setattr(api_etf_compare, "META_DIR", tmp_path / "meta")
    monkeypatch.setattr(api_etf_compare, "DICTIONARY_PATH", dic)
    monkeypatch.setattr(api_etf_compare, "_held_tickers", lambda: (["AAA001"], "ok"))
    return TestClient(api_module.app)


def test_endpoint_returns_summary_with_sources(client: TestClient) -> None:
    res = client.get("/market/etf-compare/summary", params={"basis": "three_month"})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok" and body["basis"] == "three_month"
    assert body["sources"]["official_csv"]["name"] == "krx_etf_basic_20260927.csv"
    assert (
        body["sources"]["dictionary"]["status"] == "ok"
        and body["sources"]["dictionary"]["sector_count"] == 4
    )
    assert (
        body["holdings"]["status"] == "ok"
        and body["holdings"]["items"][0]["ticker"] == "AAA001"
    )
    assert "eval_amount" not in json.dumps(body) and "quantity" not in json.dumps(body)
    assert (
        client.get(
            "/market/etf-compare/summary", params={"basis": "weekly"}
        ).status_code
        == 422
    )


def test_endpoint_without_dictionary_or_csv_still_answers(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(api_etf_compare, "META_DIR", tmp_path / "empty_meta")
    monkeypatch.setattr(api_etf_compare, "DICTIONARY_PATH", tmp_path / "missing.json")
    body = client.get("/market/etf-compare/summary").json()
    assert body["status"] == "ok"
    assert body["sources"]["official_csv"]["status"] == "unavailable"
    assert body["sources"]["dictionary"]["status"] == "unavailable"
    assert all(x["classification"]["kind"] == "unclassified" for x in body["top"])


def test_held_tickers_reads_holdings_safely(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app import holdings as holdings_module
    from app.holdings import HoldingsValidationError

    monkeypatch.setattr(holdings_module, "HOLDINGS_FILE", tmp_path / "none.json")
    monkeypatch.setattr(holdings_module, "load", lambda: [])
    assert api_etf_compare._held_tickers() == ([], "none")

    def boom() -> list:
        raise HoldingsValidationError("broken")

    monkeypatch.setattr(holdings_module, "load", boom)
    assert api_etf_compare._held_tickers() == (None, "error")


# ── 보유 가격 흐름 = 같은 응답 · 같은 읽기(검증자 r2 F4) ─────────────────────


def _pc_basis(db: Path, tickers: list[str]) -> dict[str, Any]:
    from app.pc_price_basis import apply_pc_price_basis, load_recent_price_rows

    ev = {
        "holdings": [
            {"ticker": t, "short_term_momentum": {}, "evidence_notes": []}
            for t in tickers
        ]
    }
    rows = load_recent_price_rows(tickers, db_path=db)
    return {h["ticker"]: h for h in apply_pc_price_basis(ev, rows)["holdings"]}


def test_holding_price_flow_equals_pc_evidence_computation(market: Path) -> None:
    """요약의 보유 가격 흐름 = 보유 근거 PC 사본(`apply_pc_price_basis`)과 같은 값 · 날짜 · 하락 판정."""
    with sqlite3.connect(
        market
    ) as con:  # 장중 저장 끝일 행 + 늦은 주식 행(기준일 다름)
        con.execute(
            "UPDATE etf_daily_price SET fetched_at = '2026-11-10T04:18:02Z' WHERE date = ?",
            (END,),
        )
        # KODEX 200 끝일 행만 마감 뒤 다시 저장 — 저장 상태는 이 종목 끝일 행에서만 읽어야 한다.
        con.execute(
            "UPDATE etf_daily_price SET fetched_at = '2026-11-10T06:40:00Z'"
            " WHERE date = ? AND ticker = '069500'",
            (END,),
        )
    _put(market, "005930", _trend(30, 100.0, 70.0), days=DAYS[-29:] + ["2026-11-11"])
    held = ["AAA001", "AAA004", "005930", "AAA009"]
    r = _run(market, held=held)
    pc = _pc_basis(market, held[:3])
    h = {x["ticker"]: x for x in r["holdings"]["items"]}
    for t in held[:3]:
        flow, ev = h[t]["price_flow"], pc[t]
        stm = ev["short_term_momentum"]
        assert flow["comparison"] == ev["price_dates"]["comparison"]
        assert (flow["end_date"], flow["start_date_5d"], flow["start_date_20d"]) == (
            ev["price_dates"]["end_date"],
            ev["price_dates"]["start_date_5d"],
            ev["price_dates"]["start_date_20d"],
        )
        for k in ("return_5d_pct", "return_20d_pct", "excess_vs_kodex200_20d_pctp"):
            assert flow[k] == stm.get(k)
        assert flow["decline_band"] == ev["decline_band"]
    a = h["AAA001"]["price_flow"]
    assert a["comparison"] == "ok" and a["decline_band"]["state"] == "D10_PLUS"
    assert (
        a["end_price"]["state"] == "intraday"
        and h["AAA001"]["end_price"] == a["end_price"]
    )
    # KODEX 200 수익률 = 같은 069500 행 · 같은 산식(차이에서 되돌려 만들지 않음)
    assert a["return_20d_pct"] - a["kodex200_return_20d_pct"] == pytest.approx(
        a["excess_vs_kodex200_20d_pctp"], abs=1e-9
    )
    stock = h["005930"]["price_flow"]
    assert stock["comparison"] == "date_mismatch" and stock["end_date"] == "2026-11-11"
    assert (
        stock["kodex200_return_20d_pct"] is None
        and stock["decline_band"]["judgeable"] is False
    )
    assert h["AAA009"]["price_flow"] is None and h["AAA009"]["end_price"] is None
