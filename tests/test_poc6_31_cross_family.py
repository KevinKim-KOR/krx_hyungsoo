"""POC6-31 STEP 3 — 여러 지수 계열이 함께 담은 주식(판정 §2 첫째 · Q9 · Q21).

11/13 고정 자료(POC6-30 대조용 사본에서 뽑은 공개 시장 자료)로 반복 40종목 · 근거 138건을 대조하고,
같은 입력에서 POC6-30 연구 계산(`comparison_three`)과 결과가 같은지 본다. 라이브 DB · 외부 호출 0.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import constituents_cross_family as X
from app import sector_constituents_comparison as C
from app.etf_constituents_fetcher import NAVER_STOCK_SOURCE
from app.etf_constituents_store import (
    ConstituentRow,
    log_constituent_refresh,
    upsert_constituents,
)
from app.etf_constituents_status import confirmation_message

FIX = json.loads(
    (Path(__file__).parent / "fixtures" / "poc6_31_cross_family_1113.json").read_text(
        encoding="utf-8"
    )
)


def _latest(dates=None):
    dates = dates or {}
    return {
        t: X.with_top(dates.get(t, v["asof"]), v["rows"])
        for t, v in FIX["constituents"].items()
    }


def test_reproduces_poc6_30_forty_stocks_138_evidence():
    out = X.cross_family(
        FIX["etfs"], _latest(), set(FIX["etf_tickers_among_constituents"])
    )
    assert out["status"] == X.STATUS_OK
    assert len(out["stocks"]) == 40 and out["scope"]["evidence_count"] == 138
    assert (
        out["scope"]["latest_date"] == "2026-11-13" and out["scope"]["same_date"] == 30
    )
    top = out["stocks"][0]
    assert (
        top["name"],
        top["family_count"],
        top["etf_count"],
        top["max_weight_pct"],
    ) == ("암젠", 9, 12, 11.98)
    names = [s["name"] for s in out["stocks"][:5]]
    assert names == ["암젠", "일라이 릴리", "머크 앤 코", "애브비", "노보 노디스크 ADR"]
    coke = next(s for s in out["stocks"] if s["name"] == "코카콜라")
    assert (coke["family_count"], coke["etf_count"], coke["strategy_count"]) == (
        3,
        6,
        3,
    )
    assert out["reference"] == []


def test_same_as_research_comparison_three_on_same_input():
    latest = _latest()
    frozen = [
        {
            "ticker": e["ticker"],
            "name": e["name"],
            "rank": e["rank"],
            "classification": {
                "index_name": e["index_name"],
                "strategy": e["strategy"],
            },
        }
        for e in FIX["etfs"]
    ]
    research = C.comparison_three(
        frozen, latest, set(FIX["etf_tickers_among_constituents"]), set()
    )
    ours = X.cross_family(
        FIX["etfs"], latest, set(FIX["etf_tickers_among_constituents"])
    )["stocks"]

    def sig(xs):
        return [
            (x["key"], x["family_count"], x["etf_count"], len(x["entries"])) for x in xs
        ]

    assert sig(ours) == sig(research)


def test_only_latest_date_counts_other_dates_are_reference():
    # 판정 §2 — 같은 날짜끼리만 · 이전 구성일 대조는 그 날짜의 참고
    first = FIX["etfs"][0]["ticker"]
    out = X.cross_family(FIX["etfs"], _latest({first: "2026-11-12"}), set())
    assert out["scope"]["same_date"] == 29
    assert [r["date"] for r in out["reference"]] == ["2026-11-12"]
    assert (
        out["reference"][0]["etf_count"] == 1
        and out["reference"][0]["status"] == X.STATUS_NOT_COMPARABLE
    )
    assert all(e["etf"] != first for s in out["stocks"] for e in s["entries"])


def test_not_comparable_vs_zero_stocks_vs_no_data():
    # 같은 계열 둘만 → 비교 못 함 · 서로 다른 계열인데 겹치는 주식 없음 → 0종목 · 자료 없음
    nifty = [e for e in FIX["etfs"] if e["index_name"] == "Nifty 50 Index"]
    assert len(nifty) == 2
    out = X.cross_family(nifty, _latest(), set())
    assert out["status"] == X.STATUS_NOT_COMPARABLE and out["stocks"] == []
    pair = [
        e for e in FIX["etfs"] if e["ticker"] in ("494840", "451530")
    ]  # 방산 TOP10 · 국고채(주식 행 없음)
    out2 = X.cross_family(pair, _latest(), set())
    assert out2["status"] == X.STATUS_NOT_COMPARABLE  # 주식 행 있는 계열 1개
    two = [
        e for e in FIX["etfs"] if e["ticker"] in ("494840", "453810")
    ]  # 방산 · 인도 — 계열 2 · 겹침 없음
    out3 = X.cross_family(two, _latest(), set())
    assert out3["status"] == X.STATUS_OK and out3["stocks"] == []
    assert X.cross_family(FIX["etfs"][:2], {}, set())["status"] == X.STATUS_NO_DATA


def test_unknown_family_not_counted():
    etfs = [{**e, "index_name": None} for e in FIX["etfs"]]
    out = X.cross_family(etfs, _latest(), set())
    assert (
        out["status"] == X.STATUS_NOT_COMPARABLE
        and out["scope"]["unconfirmed_family_etfs"] == 29  # 국고채(주식 행 없음) 제외
    )


def test_read_confirmed_rows_uses_only_confirmed_snapshots(tmp_path):
    db = tmp_path / "m.sqlite"

    def put(t, asof, confirmed):
        rows = [
            ConstituentRow(
                etf_ticker=t,
                asof=asof,
                source=NAVER_STOCK_SOURCE,
                rank=1,
                constituent_ticker="005930",
                constituent_name="삼성전자",
                weight_pct=10.0,
                etf_name=None,
                constituent_key="005930",
            )
        ]
        upsert_constituents(rows, db_path=db)
        log_constituent_refresh(
            etf_ticker=t,
            asof=asof,
            status="ok",
            source=NAVER_STOCK_SOURCE,
            message=confirmation_message(rows) if confirmed else None,
            db_path=db,
        )

    put("A", "2026-11-13", True)
    put("B", "2026-11-14", False)  # 예전 저장분(원천 기준일 미확인) — 쓰지 않음
    put("B", "2026-11-12", True)
    got = X.read_confirmed_rows(["A", "B", "Z"], db_path=db)
    assert (
        got["A"]["asof"] == "2026-11-13"
        and got["B"]["asof"] == "2026-11-12"
        and "Z" not in got
    )
    assert got["A"]["top"][0]["match_key"] == "005930"


@pytest.mark.parametrize("ticker", ["453640"])
def test_non_stock_rows_hidden_and_counted_as_unknown(ticker):
    # 453640 원본 1 ~ 10행: 원화현금 1 · 종류 미확인 1(선물 약호) — 주식 노출 집계에서 가림
    e = [x for x in FIX["etfs"] if x["ticker"] == ticker]
    out = X.cross_family(e, _latest(), set())
    assert (
        out["scope"]["unknown_rows"] >= 1 and out["scope"]["etf_with_stock_rows"] == 1
    )


def test_api_cross_family_reads_confirmed_rows_and_official_names(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from app import api as api_module
    from app import api_etf_constituents, etf_constituents_store
    from app.market_data_store import EtfMasterRow, upsert_etf_master

    db = tmp_path / "m.sqlite"
    monkeypatch.setattr(etf_constituents_store, "DEFAULT_DB_PATH", db)
    upsert_etf_master(
        [
            EtfMasterRow(
                ticker=e["ticker"],
                name=e["name"],
                category=None,
                price=None,
                volume=None,
                market_cap=None,
            )
            for e in FIX["etfs"]
        ],
        source="test",
        db_path=db,
    )
    for t, v in FIX["constituents"].items():
        rows = [
            ConstituentRow(
                etf_ticker=t,
                asof=v["asof"],
                source=NAVER_STOCK_SOURCE,
                rank=r["rank"],
                constituent_ticker=r["ticker"],
                constituent_name=r["name"],
                weight_pct=r["weight_pct"],
                etf_name=None,
                constituent_key=r["key"],
                constituent_isin=r["isin"],
                constituent_reuters_code=r["reuters"],
                market_type=r["market_type"],
            )
            for r in v["rows"]
        ]
        upsert_constituents(rows, db_path=db)
        log_constituent_refresh(
            etf_ticker=t,
            asof=v["asof"],
            status="ok",
            source=NAVER_STOCK_SOURCE,
            message=confirmation_message(rows),
            db_path=db,
        )
    official = {
        e["ticker"]: {"단축코드": e["ticker"], "기초지수명": e["index_name"] or ""}
        for e in FIX["etfs"]
    }
    monkeypatch.setattr(
        api_etf_constituents,
        "resolve_official_csv",
        lambda _d: SimpleNamespace(
            ok=True, records=list(official.values()), name="krx_etf_basic_test.csv"
        ),
    )
    client = TestClient(api_module.app)
    tickers = ",".join(e["ticker"] for e in FIX["etfs"])
    body = client.get(f"/market/constituents/cross-family?tickers={tickers}").json()
    assert (
        body["status"] == "ok"
        and len(body["stocks"]) == 40
        and body["scope"]["evidence_count"] == 138
    )
    assert (
        body["stocks"][0]["name"] == "암젠"
        and body["official_csv"] == "krx_etf_basic_test.csv"
    )
    too_many = ",".join(f"X{i}" for i in range(31))
    assert (
        client.get(f"/market/constituents/cross-family?tickers={too_many}").status_code
        == 422
    )
