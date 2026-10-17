"""POC5-19 — PC 근거 응답 사본의 최근 저장일 거래량 흐름(`volume_trend`).

설계 docs/ai_design/POC5/POC5-19_STORED_VOLUME_TREND_VIEW_DESIGN_V1.md §3 · §4 · §6
개정 판정 docs/ai_design/POC5/POC5-19_EVIDENCE_PRESENTATION_REVISION_DECISION_2026-10-16.md §4
PLAN docs/ai_plan/POC5/POC5-19_STORED_VOLUME_TREND_VIEW_PLAN_V1.md §2 · §4 · §5
순수 계산 + 실제 GET /holdings/market-evidence/latest(tmp DB · 격리 보유). 라이브 DB 를 열지 않는다.
"""

from __future__ import annotations

import math
import sys
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import api_holdings_market_evidence, api_market_topn, market_data_store
from app.market_data_store import EtfDailyPriceRow, upsert_daily_prices
from app.stored_volume_evidence import (
    TREND_POINTS,
    compute_stored_volume_evidence,
    compute_volume_trend,
)
from tests.test_pc_price_basis import api_client  # noqa: F401 — fixture

D = "2026-10-14"


def _rows_desc(n: int, volumes: list[Any] | None = None) -> list[tuple]:
    """최신순 (date, close, volume, source) n행 · 기본 거래량 = 1000 + 날짜 순번."""
    end = date.fromisoformat(D)
    out = []
    for i in range(n):
        v = volumes[i] if volumes is not None else 1000 + i
        out.append(
            ((end - timedelta(days=i)).isoformat(), 100.0, v, "FinanceDataReader")
        )
    return out


# ── 순수 계산 ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("n, expected", [(21, 20), (25, 20), (20, 20), (7, 7), (1, 1)])
def test_latest_up_to_20_points_oldest_first_including_d(n: int, expected: int) -> None:
    rows = _rows_desc(n)
    ev = compute_volume_trend(rows)
    assert len(ev.points) == expected == min(n, TREND_POINTS)
    assert ev.asof_date == D
    assert ev.points[-1].date == D  # 기준일 포함 · 마지막
    assert [p.date for p in ev.points] == [r[0] for r in reversed(rows[:expected])]
    assert ev.missing_count == 0


def test_no_rows_is_empty() -> None:
    ev = compute_volume_trend([])
    assert (ev.asof_date, ev.points, ev.missing_count) == (None, [], 0)


@pytest.mark.parametrize("bad", [None, -1, math.nan, math.inf, "12", True])
def test_invalid_volume_is_null_and_keeps_its_date(bad: Any) -> None:
    vols: list[Any] = [1000 + i for i in range(21)]
    vols[3] = bad
    rows = _rows_desc(21, vols)
    ev = compute_volume_trend(rows)
    # 결측 행을 지워 더 오래된 행으로 채우지 않는다 — 날짜 집합이 결측 없는 경우와 같다.
    assert [p.date for p in ev.points] == [r[0] for r in reversed(rows[:20])]
    by_date = {p.date: p.volume for p in ev.points}
    assert by_date[rows[3][0]] is None
    assert ev.missing_count == 1


def test_stored_zero_is_a_value_not_missing() -> None:
    vols: list[Any] = [1000 + i for i in range(21)]
    vols[5] = 0
    ev = compute_volume_trend(_rows_desc(21, vols))
    assert {p.date: p.volume for p in ev.points}[_rows_desc(21)[5][0]] == 0
    assert ev.missing_count == 0


def test_same_rows_as_the_volume_cells_and_cells_unchanged() -> None:
    rows = _rows_desc(21)
    cells = compute_stored_volume_evidence("111111", rows)
    ev = compute_volume_trend(rows)
    assert ev.asof_date == cells.asof_date == D
    # 기존 평균 창(D 앞 20행)은 그대로 · 차트는 D 포함 20행.
    assert cells.window_date_count == 20
    assert ev.points[0].date == rows[19][0]


# ── 실제 GET 응답(tmp DB) ─────────────────────────────────────────────────────
def _seed(db, ticker: str, n: int, volumes: list[Any] | None = None) -> None:
    rows = []
    for i, (d, c, v, _s) in enumerate(_rows_desc(n, volumes)):
        rows.append(EtfDailyPriceRow(ticker, d, c, c, c, c, v, 0.0))
    upsert_daily_prices(rows, source="FinanceDataReader", db_path=db)


def _put(client: TestClient, rows: list[dict]) -> None:
    assert client.put("/holdings", json={"holdings": rows}).status_code == 200


def _h(ticker: str, account: str = "일반") -> dict:
    return {
        "ticker": ticker,
        "name": ticker + "명",
        "quantity": 1,
        "avg_buy_price": 100,
        "account_group": account,
    }


def test_endpoint_field_shared_by_accounts_and_no_extra_read(
    api_client: TestClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = api_market_topn.DEFAULT_DB_PATH
    _seed(db, "069500", 25)
    vols: list[Any] = [1000 + i for i in range(25)]
    vols[2] = None
    _seed(db, "111111", 25, vols)
    _seed(db, "222222", 7)
    _put(api_client, [_h("111111"), _h("111111", "ISA"), _h("222222")])

    reads: list[str] = []
    real = market_data_store.fetch_recent_price_rows

    def spy(ticker, **kw):
        reads.append(ticker)
        return real(ticker, **kw)

    # 저장 가격 행 읽기 함수를 이름으로 가져간 모든 app 모듈을 함께 감시한다
    # (pc_price_basis · stored_volume_evidence 등 — 한 경로만 보지 않는다).
    bound = [
        m
        for name, m in list(sys.modules.items())
        if (name == "app" or name.startswith("app."))
        and getattr(m, "fetch_recent_price_rows", None) is real
    ]
    assert {m.__name__ for m in bound} >= {
        "app.market_data_store",
        "app.pc_price_basis",
        "app.stored_volume_evidence",
    }
    for m in bound:
        monkeypatch.setattr(m, "fetch_recent_price_rows", spy)
    body = api_client.get("/holdings/market-evidence/latest").json()
    # 종목별 한 번(기존 읽기 그대로) — 흐름 때문에 늘지 않는다.
    assert sorted(reads) == ["069500", "111111", "222222"]
    by = [(h["ticker"], h["volume_trend"]) for h in body["holdings"]]
    a, b = [v for t, v in by if t == "111111"]
    assert a == b
    assert len(a["points"]) == 20 and a["asof_date"] == D
    assert a["missing_count"] == 1 and a["points"][-3]["volume"] is None
    short = dict(by)["222222"]
    assert len(short["points"]) == 7


def test_endpoint_other_fields_unchanged_by_new_field(
    api_client: TestClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = api_market_topn.DEFAULT_DB_PATH
    _seed(db, "069500", 25)
    _seed(db, "111111", 25)
    _put(api_client, [_h("111111"), _h("111111", "ISA")])
    with_field = api_client.get("/holdings/market-evidence/latest").json()
    monkeypatch.setattr(
        api_holdings_market_evidence, "compute_volume_trend", lambda rows: None
    )
    without = api_client.get("/holdings/market-evidence/latest").json()
    for h in with_field["holdings"]:
        assert h.pop("volume_trend") is not None
    for h in without["holdings"]:
        assert h.pop("volume_trend") is None
    with_field.pop("asof")
    without.pop("asof")
    assert with_field == without
