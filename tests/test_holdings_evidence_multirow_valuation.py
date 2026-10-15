"""POC5-14 — 같은 종목 · 여러 계좌 평가값 정정(DEF-HOLDINGS-EVIDENCE-MULTIROW-VALUATION).

판정: docs/ai_design/POC5/
  POC5-14_HOLDINGS_EVIDENCE_MULTIROW_VALUATION_FIX_PLAN_DECISION_2026-10-15.md §6
A = 공유 builder 가 보유 줄과 평가 줄을 같은 위치끼리 짝짓는다(어긋나면 실패).
C = 요약(top_holdings · coverage)이 같은 종목 여러 줄을 종목 합산으로 쓴다.
임시 DB · 고정 시세만 쓴다(외부 호출 0 · 라이브 DB 0).
"""

from __future__ import annotations

import dataclasses
from datetime import date, timedelta
from pathlib import Path

import pytest

from app import holdings_market_evidence as hme
from app.draft_message import _render_today_holdings_lines
from app.holdings import Holding
from app.holdings_enrich import enrich_holdings
from app.market_cache import MarketQuote
from app.market_data_store import EtfDailyPriceRow, init_db, upsert_daily_prices
from app.market_summary_composer import select_top_holdings, summarize_holdings
from app.pc_price_basis import apply_pc_price_basis, load_recent_price_rows

DUP, OTHER = "069500", "367760"
PRICE = {DUP: 35000.0, OTHER: 10000.0}
TOPN = {
    "status": "ok",
    "basis": "return_20d",
    "asof": "2026-10-13",
    "n": 10,
    "candidates": [],
    "market_context": None,
}


def _rows_a() -> list[Holding]:
    return [
        Holding(
            ticker=DUP,
            name="KODEX 200",
            quantity=10,
            avg_buy_price=30000,
            account_group="일반",
        ),
        Holding(
            ticker=DUP,
            name="KODEX 200",
            quantity=30,
            avg_buy_price=32000,
            account_group="ISA",
        ),
        Holding(
            ticker=OTHER,
            name="RISE",
            quantity=20,
            avg_buy_price=9000,
            account_group="일반",
        ),
    ]


def _quotes(prices: dict[str, float] | None = None) -> dict[str, MarketQuote]:
    return {
        t: MarketQuote(
            ticker=t,
            name=None,
            current_price=p,
            price_asof="2026-10-13T15:30:00+09:00",
            price_source="fixture",
        )
        for t, p in (prices or PRICE).items()
    }


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "market_data.sqlite"
    init_db(path)
    days: list[str] = []
    d = date(2026, 10, 13)
    while len(days) < 25:
        if d.weekday() < 5:
            days.append(d.isoformat())
        d -= timedelta(days=1)
    days.reverse()
    rows = []
    for i, day in enumerate(days):
        back = len(days) - 1 - i
        rows.append(
            EtfDailyPriceRow(
                DUP, day, None, None, None, 35000.0 - back * 100.0, 1000, None
            )
        )
        rows.append(
            EtfDailyPriceRow(
                OTHER, day, None, None, None, 10000.0 + back * 80.0, 1000, None
            )
        )
    upsert_daily_prices(rows, source="fixture", db_path=path)
    return path


def _build(
    holdings: list[Holding], db: Path, prices: dict[str, float] | None = None
) -> dict:
    return hme.build_holdings_market_evidence(
        holdings=holdings,
        topn_payload=TOPN,
        market_quotes=_quotes(prices),
        db_path=db,
        holdings_asof="2026-10-13T00:00:00+00:00",
    )


def _top(ev: dict) -> dict[str, dict]:
    return {r["ticker"]: r for r in ev["judgment_summary"]["holdings"]["top_holdings"]}


# ── A. 보유 줄 = 자기 평가 줄 ─────────────────────────────────────────────────
@pytest.mark.parametrize("order", ["a", "b"])
def test_each_row_carries_its_own_enrich_values(db: Path, order: str) -> None:
    rows = _rows_a() if order == "a" else [_rows_a()[1], _rows_a()[0], _rows_a()[2]]
    enriched = enrich_holdings(rows, _quotes())
    ev = _build(rows, db)
    assert len(ev["holdings"]) == len(rows)
    for h, e, item in zip(rows, enriched, ev["holdings"]):
        assert item["holding"]["quantity"] == float(h.quantity)  # 출력 순서 = 입력 순서
        assert item["holding"]["evaluation_amount"] == e.eval_amount
        assert item["holding"]["pnl_rate_pct"] == e.pnl_rate_pct
    evals = sorted(i["holding"]["evaluation_amount"] for i in ev["holdings"])
    assert evals == [200000.0, 350000.0, 1050000.0]
    assert sum(evals) == 1600000.0


@pytest.mark.parametrize("break_how", ["shorter", "source_index"])
def test_misaligned_enrich_result_fails_without_substitution(
    db: Path, monkeypatch: pytest.MonkeyPatch, break_how: str
) -> None:
    real = hme.enrich_holdings

    def broken(holdings, quotes):
        out = real(holdings, quotes)
        if break_how == "shorter":
            return out[:-1]
        return [dataclasses.replace(out[0], source_index=1), *out[1:]]

    monkeypatch.setattr(hme, "enrich_holdings", broken)
    with pytest.raises(ValueError):
        _build(_rows_a(), db)


# ── C. 요약 = 종목 합산 ───────────────────────────────────────────────────────
@pytest.mark.parametrize("order", ["a", "b"])
def test_summary_uses_ticker_totals_regardless_of_row_order(
    db: Path, order: str
) -> None:
    rows = _rows_a() if order == "a" else [_rows_a()[1], _rows_a()[0], _rows_a()[2]]
    top = _top(_build(rows, db))
    assert top[DUP]["eval_amount"] == 1400000.0
    assert top[DUP]["market_weight_pct"] == 87.5
    assert top[DUP]["pnl_rate_pct"] == 11.11
    assert top[OTHER]["eval_amount"] == 200000.0
    assert top[OTHER]["market_weight_pct"] == 12.5  # 한 줄 종목도 바른 합계로
    assert top[OTHER]["pnl_rate_pct"] == 11.11


def test_pc_copy_summary_and_manual_draft_lines_use_ticker_totals(db: Path) -> None:
    ev = _build(_rows_a(), db)
    # 수동 PC 보유 초안(app/draft.py)은 공유 builder 의 요약을 그대로 쓴다 — 그 요약으로 만든 줄.
    own = "\n".join(
        _render_today_holdings_lines({"judgment_summary": ev["judgment_summary"]})
    )
    assert "비중 87.5%" in own and "+11.11%" in own and "비중 12.5%" in own
    # PC 화면 응답은 그 결과의 사본에서 요약을 다시 만든다(app/pc_price_basis.py).
    pc = apply_pc_price_basis(ev, load_recent_price_rows([DUP, OTHER], db_path=db))
    top = _top(pc)
    assert (top[DUP]["market_weight_pct"], top[DUP]["pnl_rate_pct"]) == (87.5, 11.11)
    assert top[OTHER]["market_weight_pct"] == 12.5
    text = "\n".join(
        _render_today_holdings_lines({"judgment_summary": pc["judgment_summary"]})
    )
    assert "비중 87.5%" in text and "+11.11%" in text
    assert "비중 12.5%" in text
    assert "45.7%" not in text and "+9.38%" not in text  # 예전 잘못된 값(PLAN §1-4)


def test_whole_ticker_without_quote_has_no_substitute_numbers(db: Path) -> None:
    ev = _build(_rows_a(), db, prices={OTHER: 10000.0})
    dup_rows = [i for i in ev["holdings"] if i["ticker"] == DUP]
    assert all(i["holding"]["evaluation_amount"] is None for i in dup_rows)
    top = _top(ev)
    assert top[DUP]["eval_amount"] is None
    assert top[DUP]["market_weight_pct"] is None
    assert top[DUP]["pnl_rate_pct"] is None
    assert top[OTHER]["market_weight_pct"] == 100.0  # 기존 규칙: 확인된 평가금액만 합계
    cov = ev["judgment_summary"]["holdings"]["coverage"]
    assert cov["total"] == 2 and cov["need_check"] >= 1


def _item(ticker: str, ev, pnl, qty, avg, r5=-1.0) -> dict:
    return {
        "ticker": ticker,
        "name": ticker,
        "holding": {
            "quantity": qty,
            "avg_buy_price": avg,
            "evaluation_amount": ev,
            "pnl_rate_pct": pnl,
        },
        "short_term_momentum": {
            "status": "ok",
            "return_5d_pct": r5,
            "return_20d_pct": -2.0,
            "excess_vs_kodex200_20d_pctp": 0.5,
        },
    }


def test_partial_rows_in_one_ticker_give_none_not_partial_sum() -> None:
    items = [
        _item(DUP, 350000.0, 16.67, 10, 30000),
        _item(DUP, None, None, 30, 32000),
        _item(OTHER, 200000.0, 11.11, 20, 9000),
    ]
    top = {r["ticker"]: r for r in select_top_holdings(items)}
    assert top[DUP]["eval_amount"] is None
    assert top[DUP]["market_weight_pct"] is None
    assert top[DUP]["pnl_rate_pct"] is None
    # 전체 합계는 기존 규칙(확인된 줄만) — 350,000 + 200,000
    assert top[OTHER]["market_weight_pct"] == round(200000 / 550000 * 100, 1)
    cov = summarize_holdings(items)["coverage"]
    assert cov == {"total": 2, "need_check": 1, "ok": 1}


@pytest.mark.parametrize(
    "avgs", [(30000, None), (0, 0)], ids=["one_row_avg_missing", "invested_zero"]
)
def test_pnl_none_when_invested_not_computable(avgs) -> None:
    items = [
        _item(DUP, 350000.0, 16.67, 10, avgs[0]),
        _item(DUP, 1050000.0, 9.38, 30, avgs[1]),
    ]
    top = select_top_holdings(items)[0]
    assert top["eval_amount"] == 1400000.0
    assert top["pnl_rate_pct"] is None
    # 자료 확인 판정도 종목 합산 손익(없음)을 본다 — 첫 줄 손익으로 '정상' 처리하지 않음.
    assert summarize_holdings(items)["coverage"]["need_check"] == 1


def test_single_row_ticker_keeps_its_row_values_exactly() -> None:
    # 한 줄 종목은 그 줄 값을 그대로(다시 계산하지 않음 · 기존 값 불변).
    items = [_item(OTHER, 200000.0, 11.12, 20, 9000)]
    top = select_top_holdings(items)[0]
    assert top["eval_amount"] == 200000.0
    assert top["pnl_rate_pct"] == 11.12
    assert top["market_weight_pct"] == 100.0


def test_selection_and_order_rules_unchanged() -> None:
    items = [
        _item("BBB", 100.0, 1.0, 1, 90, r5=-3.0),
        _item(DUP, 350000.0, 16.67, 10, 30000, r5=-1.0),
        _item("AAA", 100.0, 1.0, 1, 90, r5=-3.0),
        _item(DUP, 1050000.0, 9.38, 30, 32000, r5=-1.0),
        _item("CCC", 100.0, 1.0, 1, 90, r5=-0.5),
    ]
    assert [r["ticker"] for r in select_top_holdings(items)] == ["AAA", "BBB", DUP]
