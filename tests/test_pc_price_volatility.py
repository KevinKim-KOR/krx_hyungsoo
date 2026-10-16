"""POC5-16 — PC 근거 응답 사본의 저장 종가 가격 흔들림(`price_volatility`).

설계 docs/ai_design/POC5/POC5-16_STORED_PRICE_VOLATILITY_EVIDENCE_DESIGN_V1.md §2~§4 · §8
PLAN docs/ai_plan/POC5/POC5-16_STORED_PRICE_VOLATILITY_EVIDENCE_PLAN_V1.md §2-1 · §4
판정 docs/ai_design/POC5/POC5-16_STORED_PRICE_VOLATILITY_EVIDENCE_PLAN_DECISION_2026-10-16.md
  §3 · §4 · §6
순수 계산 + tmp DB 읽기 + 실제 GET /holdings/market-evidence/latest(격리 보유). 라이브 DB 를 열지 않는다.
"""

from __future__ import annotations

import hashlib
import math
import sqlite3
import statistics
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

import pytest
from fastapi.testclient import TestClient

from app import api_holdings_market_evidence, api_market_topn, pc_price_volatility
from app.market_data_store import EtfDailyPriceRow, upsert_daily_prices
from app.pc_price_volatility import build_price_volatility, compute_price_volatility
from app.reentry_review import prices as reentry_prices
from app.reentry_review.prices import PriceRow
from tests.test_pc_price_basis import api_client  # noqa: F401 — fixture

FDR = "FinanceDataReader"
NAVER = "NAVER_FDR"
D = "2026-10-14"


def _dates(n: int, end: str = D) -> list[str]:
    e = date.fromisoformat(end)
    return [(e - timedelta(days=n - 1 - i)).isoformat() for i in range(n)]


def _closes_from(returns: list[float], start: float = 100.0) -> list[float]:
    out = [start]
    for r in returns:
        out.append(out[-1] * (1.0 + r))
    return out


def _rows(closes: list[Any], end: str = D, source: str = FDR) -> list[PriceRow]:
    """오름차순 행 · change = 실제 종가 변화(첫 행 0) → 경계 없음."""
    dates = _dates(len(closes), end)
    out: list[PriceRow] = []
    for i, (d, c) in enumerate(zip(dates, closes)):
        prev = closes[i - 1] if i else None
        ok = isinstance(c, float) and isinstance(prev, float) and prev > 0 and c > 0
        change = (c / prev - 1.0) if ok else 0.0
        out.append(PriceRow(d, c, source, "2026-10-14T06:27:35Z", change))
    return out


def _replace(rows: list[PriceRow], i: int, **kw) -> list[PriceRow]:
    r = rows[i]
    fields = {"date": r.date, "close": r.close, "source": r.source}
    fields.update({"fetched_at": r.fetched_at, "change": r.change})
    fields.update(kw)
    out = list(rows)
    out[i] = PriceRow(**fields)
    return out


def _calc(rows: list[PriceRow], e: Optional[str] = D, d: Optional[str] = D):
    return compute_price_volatility(rows, last_valid_date=e, reference_date=d)


ALT10 = [0.10, -0.10] * 10  # +10% · −10% 각 10개
FLAT1 = [0.01] * 20  # 모두 같은 변화


# ── 고정 예 · 분모 · 기간 ────────────────────────────────────────────────────
def test_equal_returns_give_zero_and_zero_is_a_value() -> None:
    ev = _calc(_rows(_closes_from(FLAT1 + FLAT1)))
    assert ev.status == "ok"
    assert ev.recent is not None and ev.previous is not None
    assert (ev.recent.value_pct, ev.previous.value_pct) == (0.0, 0.0)
    assert ev.comparison == "same"


def test_plus_minus_ten_is_population_ten_not_sample() -> None:
    ev = _calc(_rows(_closes_from(FLAT1 + ALT10)))
    assert ev.recent is not None and ev.previous is not None
    assert ev.recent.value_pct == 10.0  # 분모 20 · 연율화 없음 · %
    assert round(statistics.stdev(ALT10) * 100, 2) != 10.0  # 표본 분모면 10.26
    assert ev.previous.value_pct == 0.0
    assert ev.comparison == "higher"


def test_windows_share_only_the_boundary_close() -> None:
    # P0…P40 · 직전 연결 P0→P1 … P19→P20 · 최근 P20→P21 … P39→P40.
    rows = _rows(_closes_from(ALT10 + FLAT1))
    ev = _calc(rows)
    assert ev.previous is not None and ev.recent is not None
    assert (ev.previous.start_date, ev.previous.end_date) == (
        rows[0].date,
        rows[20].date,
    )
    assert (ev.recent.start_date, ev.recent.end_date) == (rows[20].date, rows[40].date)
    # 수익률 구간이 겹치지 않는다(겹치면 최근이 0 이 아니다).
    assert (ev.previous.value_pct, ev.recent.value_pct) == (10.0, 0.0)
    assert ev.comparison == "lower"
    assert ev.end_date == D


def test_comparison_uses_displayed_two_decimal_values() -> None:
    hi = [0.032049, -0.032049] * 10  # 3.2049 → 3.20
    lo = [0.031951, -0.031951] * 10  # 3.1951 → 3.20
    ev = _calc(_rows(_closes_from(lo + hi)))
    assert ev.recent is not None and ev.previous is not None
    assert (ev.recent.value_pct, ev.previous.value_pct) == (3.2, 3.2)
    assert ev.comparison == "same"


def test_recent_only_and_unavailable_by_history_length() -> None:
    ev = _calc(_rows(_closes_from(ALT10 + [0.0] * 9)))  # 30 행
    assert ev.status == "recent_only"
    assert ev.recent is not None and ev.previous is None
    assert (ev.previous_reason, ev.comparison) == ("insufficient_history", None)
    ev = _calc(_rows(_closes_from([0.01] * 14)))  # 15 행
    assert ev.status == "unavailable"
    assert (ev.recent_reason, ev.previous_reason) == (
        "insufficient_history",
        "insufficient_history",
    )


@pytest.mark.parametrize(
    "n, status, recent_reason, previous_reason",
    [
        (20, "unavailable", "insufficient_history", "insufficient_history"),
        (21, "recent_only", None, "insufficient_history"),  # 최근 21개면 최근 값은 준다
        (
            40,
            "recent_only",
            None,
            "insufficient_history",
        ),  # 41개 전엔 두 기간을 겹쳐 만들지 않음
        (41, "ok", None, None),
    ],
)
def test_row_count_boundaries(n, status, recent_reason, previous_reason) -> None:
    rows = _rows(_closes_from((ALT10 + FLAT1)[-(n - 1) :]))  # noqa: E203
    ev = _calc(rows)
    assert (ev.status, ev.recent_reason, ev.previous_reason) == (
        status,
        recent_reason,
        previous_reason,
    )
    if ev.recent is not None:
        assert (ev.recent.start_date, ev.recent.end_date) == (rows[-21].date, D)
    if n < 41:
        assert ev.previous is None


def test_only_latest_41_rows_are_used() -> None:
    rows = _rows(_closes_from([0.3, -0.3] * 5 + ALT10 + FLAT1))  # 51 행
    ev = _calc(rows)
    assert ev.previous is not None
    assert ev.previous.start_date == rows[10].date
    assert ev.previous.value_pct == 10.0


# ── 비정상 종가 · 출처 · 경계(기간별) ─────────────────────────────────────────
@pytest.mark.parametrize("bad", [None, 0.0, -1.0, math.inf, math.nan, "12.5", True])
def test_invalid_close_in_recent_blocks_only_recent(bad: Any) -> None:
    rows = _replace(_rows(_closes_from(ALT10 + FLAT1)), 30, close=bad)
    ev = _calc(rows)
    assert (ev.status, ev.recent, ev.recent_reason) == (
        "previous_only",
        None,
        "invalid_price",
    )
    assert ev.previous is not None and ev.previous.value_pct == 10.0
    assert ev.comparison is None


def test_invalid_boundary_close_blocks_both() -> None:
    ev = _calc(_replace(_rows(_closes_from(ALT10 + FLAT1)), 20, close=0.0))
    assert ev.status == "unavailable"
    assert (ev.recent_reason, ev.previous_reason) == ("invalid_price", "invalid_price")


def test_first_close_checked_but_link_into_it_is_not() -> None:
    rows = _rows(_closes_from(ALT10 + FLAT1))
    # P0 로 들어오는 창 밖 연결(저장 change)은 보지 않는다 — 42번째 종가를 요구하지 않음.
    ev = _calc(_replace(rows, 0, change=0.5))
    assert ev.status == "ok"
    # P0 자체의 가격 · 출처는 본다.
    ev = _calc(_replace(rows, 0, close=None))
    assert (ev.status, ev.previous_reason) == ("recent_only", "invalid_price")
    ev = _calc(_replace(rows, 0, source="KRX"))
    assert (ev.status, ev.previous_reason) == ("recent_only", "invalid_price")


def test_link_p19_p20_blocks_previous_only_and_p20_p21_recent_only() -> None:
    rows = _rows(_closes_from(ALT10 + FLAT1))
    ev = _calc(_replace(rows, 20, change=0.05))  # P19 → P20
    assert (ev.status, ev.previous_reason, ev.recent_reason) == (
        "recent_only",
        "basis_unconfirmed",
        None,
    )
    ev = _calc(_replace(rows, 21, change=0.05))  # P20 → P21
    assert (ev.status, ev.recent_reason, ev.previous_reason) == (
        "previous_only",
        "basis_unconfirmed",
        None,
    )


def test_change_missing_and_reswitch_are_unconfirmed_not_price_change() -> None:
    rows = _rows(_closes_from(ALT10 + FLAT1))
    ev = _calc(_replace(rows, 30, change=None))
    assert ev.recent_reason == "basis_unconfirmed"
    ev = _calc(_replace(rows, 30, source=NAVER))  # FinanceDataReader → NAVER_FDR 재전환
    assert ev.recent_reason == "basis_unconfirmed"


def test_naver_to_fdr_label_change_alone_is_not_a_boundary() -> None:
    closes = _closes_from(ALT10 + FLAT1)
    naver = _rows(closes, source=NAVER)
    rows = [PriceRow(r.date, r.close, NAVER, r.fetched_at, None) for r in naver[:25]]
    rows += _rows(closes)[25:]  # 이후 FinanceDataReader(change = 실제 변화)
    ev = _calc(rows)
    assert ev.status == "ok"
    assert ev.recent is not None and ev.recent.value_pct == 0.0


def test_infinite_close_on_d_stays_e_equals_d_and_blocks_recent() -> None:
    # 거른 읽기(close > 0)를 통과하는 비정상 값은 E 를 물리지 않는다 → 최근 기간만 계산 불가.
    ev = _calc(_replace(_rows(_closes_from(ALT10 + FLAT1)), 40, close=math.inf))
    assert (ev.status, ev.recent_reason, ev.end_date) == (
        "previous_only",
        "invalid_price",
        D,
    )


@pytest.mark.parametrize("bad_change", ["n/a", "", b"x"])
def test_unreadable_stored_change_is_unconfirmed_not_an_error(bad_change: Any) -> None:
    ev = _calc(_replace(_rows(_closes_from(ALT10 + FLAT1)), 30, change=bad_change))
    assert (ev.status, ev.recent_reason) == ("previous_only", "basis_unconfirmed")


def test_reason_order_invalid_close_before_boundary() -> None:
    rows = _replace(_rows(_closes_from(ALT10 + FLAT1)), 31, change=0.05)
    ev = _calc(_replace(rows, 35, close=None))
    assert ev.recent_reason == "invalid_price"


# ── 판정 순서(PLAN §2-1 · 판정 §3) ─────────────────────────────────────────────
ROWS41 = _rows(_closes_from(ALT10 + FLAT1))


@pytest.mark.parametrize(
    "e, d, rows, status, end_date",
    [
        (None, None, ROWS41, "unavailable", None),  # E 없음이 먼저
        (None, D, ROWS41, "unavailable", None),
        (D, None, ROWS41, "reference_unavailable", D),
        ("2026-10-13", D, ROWS41, "date_mismatch", "2026-10-13"),
        ("2026-10-13", D, ROWS41[:5], "date_mismatch", "2026-10-13"),  # 이력이 짧아도
        (D, D, ROWS41, "ok", D),
    ],
)
def test_judgment_order(e, d, rows, status, end_date) -> None:
    ev = _calc(rows, e=e, d=d)
    assert (ev.status, ev.end_date) == (status, end_date)
    if status in ("date_mismatch", "reference_unavailable"):
        assert (ev.recent, ev.previous, ev.comparison) == (None, None, None)
        assert (ev.recent_reason, ev.previous_reason) == (None, None)
    if status == "unavailable":
        assert (ev.recent_reason, ev.previous_reason) == (
            "insufficient_history",
            "insufficient_history",
        )


# ── 공개 접점(POC5-06 동작 그대로) ─────────────────────────────────────────────
def test_reentry_public_names_are_the_existing_rules() -> None:
    assert reentry_prices.link_break is reentry_prices.AxisSeries._break
    assert reentry_prices.valid_close is reentry_prices._valid_close


# ── tmp DB 읽기 ────────────────────────────────────────────────────────────────
def _seed(db: Path, ticker: str, rows: list[PriceRow]) -> None:
    for r in rows:
        upsert_daily_prices(
            [
                EtfDailyPriceRow(
                    ticker, r.date, r.close, r.close, r.close, r.close, 1000, r.change
                )
            ],
            source=r.source or FDR,
            db_path=db,
        )


def _item(ticker: str, e: Optional[str]) -> dict:
    return {"ticker": ticker, "price_dates": {"end_date": e}}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_db_read_keeps_invalid_rows_inside_and_excludes_rows_after_d(
    tmp_path: Path,
) -> None:
    db = tmp_path / "m.sqlite"
    rows = _rows(_closes_from(ALT10 + FLAT1))
    _seed(db, "111111", _replace(rows, 30, close=None))  # D 이하 창 안 null
    _seed(db, "222222", rows)
    after = date.fromisoformat(D) + timedelta(days=1)
    _seed(
        db, "222222", [PriceRow(after.isoformat(), None, FDR, None, None)]
    )  # D 이후 비정상
    before = _sha(db)
    out = build_price_volatility(
        [_item("111111", D), _item("222222", D)], reference_date=D, db_path=db
    )
    assert _sha(db) == before  # 쓰기 0
    # 창 안 null 은 건너뛰지 않는다(더 오래된 종가로 채우지 않음).
    assert (out["111111"].status, out["111111"].recent_reason) == (
        "previous_only",
        "invalid_price",
    )
    # D 이후 행은 창 밖 — 최근 기간 끝 = D.
    assert out["222222"].status == "ok"
    assert out["222222"].recent is not None and out["222222"].recent.end_date == D


def test_db_read_returns_at_most_41_rows_ending_at_d(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "m.sqlite"
    rows = _rows(_closes_from([0.02] * 15 + ALT10 + FLAT1))  # D 이하 56행
    _seed(db, "111111", _replace(rows, 0, close=None))  # 41행 밖(가장 오래된 행) 비정상
    got: list[list[PriceRow]] = []
    real_read = pc_price_volatility._read_raw_rows

    def read(con, ticker, ref):
        out = real_read(con, ticker, ref)
        got.append(out)
        return out

    monkeypatch.setattr(pc_price_volatility, "_read_raw_rows", read)
    out = build_price_volatility([_item("111111", D)], reference_date=D, db_path=db)
    assert len(got) == 1 and len(got[0]) == 41
    assert (got[0][0].date, got[0][-1].date) == (rows[15].date, D)
    assert out["111111"].status == "ok"  # 41행 밖 비정상 행은 영향 없음
    assert out["111111"].previous is not None
    assert out["111111"].previous.value_pct == 10.0


def test_db_text_change_does_not_break_the_read(tmp_path: Path) -> None:
    db = tmp_path / "m.sqlite"
    rows = _rows(_closes_from(ALT10 + FLAT1))
    _seed(db, "111111", rows)
    with sqlite3.connect(db) as con:  # 손상된 저장값(REAL 열의 텍스트)
        con.execute(
            "UPDATE etf_daily_price SET change = 'n/a' WHERE ticker = ? AND date = ?",
            ("111111", rows[30].date),
        )
    out = build_price_volatility([_item("111111", D)], reference_date=D, db_path=db)
    assert (out["111111"].status, out["111111"].recent_reason) == (
        "previous_only",
        "basis_unconfirmed",
    )


def test_db_read_is_read_only_and_once_per_ticker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "m.sqlite"
    _seed(db, "111111", _rows(_closes_from(ALT10 + FLAT1)))
    uris: list[str] = []
    reads: list[str] = []
    real_connect = sqlite3.connect
    real_read = pc_price_volatility._read_raw_rows

    def connect(database, *a, **kw):
        uris.append(database)
        return real_connect(database, *a, **kw)

    def read(con, ticker, ref):
        reads.append(ticker)
        return real_read(con, ticker, ref)

    monkeypatch.setattr(pc_price_volatility.sqlite3, "connect", connect)
    monkeypatch.setattr(pc_price_volatility, "_read_raw_rows", read)
    items = [_item("111111", D), _item("111111", D), _item("333333", "2026-10-13")]
    out = build_price_volatility(items, reference_date=D, db_path=db)
    assert reads == [
        "111111"
    ]  # 같은 종목 여러 계좌 1번 · 날짜 검사 불통과 종목은 읽지 않음
    assert len(uris) == 1 and uris[0].endswith("?mode=ro")
    assert out["333333"].status == "date_mismatch"
    with pytest.raises(sqlite3.OperationalError):
        real_connect(uris[0], uri=True).execute("CREATE TABLE x (a)")


def test_no_reference_date_reads_nothing(tmp_path: Path) -> None:
    out = build_price_volatility(
        [_item("111111", D)], reference_date=None, db_path=tmp_path / "없음.sqlite"
    )
    assert out["111111"].status == "reference_unavailable"


# ── 실제 GET 응답(tmp DB · 격리 보유) ──────────────────────────────────────────
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


def test_endpoint_states_and_shared_value_for_two_accounts(
    api_client: TestClient,  # noqa: F811
) -> None:
    db = api_market_topn.DEFAULT_DB_PATH
    rows = _rows(_closes_from(ALT10 + FLAT1))
    _seed(db, "069500", rows[-5:])  # KODEX200 5행 — 41행을 요구하지 않는다
    _seed(db, "111111", rows)
    _seed(db, "222222", _replace(rows, 40, close=None))  # D 당일 비정상 → E 후퇴
    _seed(db, "333333", _replace(rows, 30, close=None))  # 창 안 비정상
    _put(api_client, [_h("111111"), _h("111111", "ISA"), _h("222222"), _h("333333")])

    body = api_client.get("/holdings/market-evidence/latest").json()
    assert body["price_basis"]["reference_date"] == D
    pv = [(h["ticker"], h["price_volatility"]) for h in body["holdings"]]
    a, b = [v for t, v in pv if t == "111111"]
    assert a == b
    assert a["status"] == "ok"
    assert (a["previous"]["value_pct"], a["recent"]["value_pct"]) == (10.0, 0.0)
    # 평가금액이 없어도(시세 캐시 없음) 계산한다.
    assert all(h["holding"]["evaluation_amount"] is None for h in body["holdings"])
    by = dict(pv)
    assert by["222222"]["status"] == "date_mismatch"
    assert by["222222"]["end_date"] == rows[39].date  # 마지막 유효 가격일
    assert (by["333333"]["status"], by["333333"]["recent_reason"]) == (
        "previous_only",
        "invalid_price",
    )


def test_endpoint_reference_unavailable_differs_from_date_mismatch(
    api_client: TestClient,  # noqa: F811
) -> None:
    db = api_market_topn.DEFAULT_DB_PATH
    _seed(db, "111111", _rows(_closes_from(ALT10 + FLAT1)))  # KODEX200 저장 가격 0행
    _put(api_client, [_h("111111")])
    body = api_client.get("/holdings/market-evidence/latest").json()
    assert body["price_basis"]["reference_date"] is None
    ev = body["holdings"][0]["price_volatility"]
    assert (ev["status"], ev["end_date"], ev["recent"]) == (
        "reference_unavailable",
        D,
        None,
    )


def test_endpoint_other_fields_unchanged_by_new_field(
    api_client: TestClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = api_market_topn.DEFAULT_DB_PATH
    rows = _rows(_closes_from(ALT10 + FLAT1))
    _seed(db, "069500", rows)
    _seed(db, "111111", _rows(_closes_from(FLAT1 + ALT10)))
    _seed(db, "222222", rows[:30])
    _put(api_client, [_h("111111"), _h("111111", "ISA"), _h("222222")])
    with_field = api_client.get("/holdings/market-evidence/latest").json()

    monkeypatch.setattr(
        api_holdings_market_evidence,
        "build_price_volatility",
        lambda items, **kw: {it["ticker"]: None for it in items},
    )
    without = api_client.get("/holdings/market-evidence/latest").json()
    for h in with_field["holdings"]:
        assert h.pop("price_volatility") is not None
    for h in without["holdings"]:
        assert h.pop("price_volatility") is None
    with_field.pop("asof")
    without.pop("asof")
    assert with_field == without
