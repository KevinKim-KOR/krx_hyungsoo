"""POC5-25 — 현재 PC 저장 종가 '20저장일 종가 고점 대비'(`stored_drawdown_20`).

순수 계산(D 포함 20행 · 고점 중복 · 결측 · 비정상 · 가격 기준 연결) + 임시 DB 의 실제
`GET /market/topn/latest` 응답. 라이브 DB · 라이브 점수 스냅샷을 열지 않는다(tmp_path · monkeypatch).
"""

from __future__ import annotations

import json
import math
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import ml_relative_upside_score
from app.market_data_store import (
    EtfDailyPriceRow,
    EtfMasterRow,
    upsert_daily_prices,
    upsert_etf_master,
)
from app.market_topn import compute_topn
from app.pc_stored_drawdown import candidate_end_date, compute_stored_drawdown
from app.reentry_review.prices import FDR, NAVER, PriceRow
from tests.test_pc_price_basis import api_client  # noqa: F401 — fixture

START = date(2026, 9, 1)


def _dates(n: int, start: date = START) -> list[str]:
    return [(start + timedelta(days=i)).isoformat() for i in range(n)]


def _rows(closes: list, source: str = FDR, start: date = START) -> list[PriceRow]:
    """FDR 행은 change = 종가 비율 변화(연결 검사 통과) · 첫 행 change 0."""
    out: list[PriceRow] = []
    prev = None
    for d, c in zip(_dates(len(closes), start), closes):
        ch = (
            c / prev - 1.0
            if isinstance(c, float) and isinstance(prev, float) and prev > 0
            else 0.0
        )
        out.append(PriceRow(d, c, source, None, ch if source == FDR else None))
        prev = c if isinstance(c, float) else prev
    return out


def _flat(n: int, v: float = 100.0) -> list:
    return [float(v)] * n


# ── 순수 계산(설계 §2) ────────────────────────────────────────────────────


def test_window_is_d_inclusive_20_rows_and_older_rows_are_ignored() -> None:
    """25행 중 최근 20행만 · 창 밖의 더 높은 종가(1000)는 고점이 아니다 · 120 → 90 = −25%."""
    closes = _flat(5, 1000.0) + _flat(10, 100.0) + [120.0] + _flat(8, 100.0) + [90.0]
    rows = _rows(closes)
    out = compute_stored_drawdown(rows, end_date=rows[-1].date)
    assert out.status == "ok" and out.reason is None
    assert out.value_pct == -25.0
    assert (out.peak_close, out.peak_date) == (120.0, rows[15].date)
    assert (out.start_date, out.end_date, out.rows) == (rows[5].date, rows[-1].date, 20)
    assert out.close == 90.0


def test_peak_ties_take_the_latest_date() -> None:
    closes = _flat(3) + [120.0] + _flat(5) + [120.0] + _flat(9) + [96.0]
    rows = _rows(closes)
    out = compute_stored_drawdown(rows, end_date=rows[-1].date)
    assert out.peak_date == rows[9].date and out.value_pct == -20.0


def test_at_peak_is_zero_and_peak_date_is_d() -> None:
    rows = _rows(_flat(19) + [130.0])
    out = compute_stored_drawdown(rows, end_date=rows[-1].date)
    assert out.value_pct == 0.0 and out.peak_date == rows[-1].date


def test_value_is_percent_rounded_to_4_places() -> None:
    rows = _rows(_flat(19, 300.0) + [200.0])
    out = compute_stored_drawdown(rows, end_date=rows[-1].date)
    assert out.value_pct == round((200.0 / 300.0 - 1) * 100, 4) == -33.3333


def test_19_rows_is_insufficient_and_has_no_value() -> None:
    rows = _rows(_flat(19))
    out = compute_stored_drawdown(rows, end_date=rows[-1].date)
    assert (out.status, out.reason, out.rows) == (
        "unavailable",
        "insufficient_history",
        19,
    )
    assert out.value_pct is None and out.peak_close is None


def test_no_end_date_is_unknown() -> None:
    out = compute_stored_drawdown(_rows(_flat(20)), end_date=None)
    assert (out.status, out.reason, out.rows) == ("unavailable", "end_date_unknown", 0)


@pytest.mark.parametrize("bad", [None, 0.0, -1.0, "abc", math.nan, math.inf])
def test_invalid_close_inside_window_is_not_refilled_from_older_rows(bad) -> None:
    closes = _flat(30)
    closes[-5] = bad
    rows = _rows(closes)
    out = compute_stored_drawdown(rows, end_date=rows[-1].date)
    assert (out.status, out.reason) == ("unavailable", "invalid_price")
    assert out.value_pct is None and out.rows == 20


def test_invalid_close_older_than_window_does_not_matter() -> None:
    closes = _flat(25)
    closes[2] = None
    rows = _rows(closes)
    out = compute_stored_drawdown(rows, end_date=rows[-1].date)
    assert out.status == "ok" and out.value_pct == 0.0


def test_naver_rows_without_change_are_fine() -> None:
    rows = _rows(_flat(19) + [95.0], source=NAVER)
    out = compute_stored_drawdown(rows, end_date=rows[-1].date)
    assert out.status == "ok" and out.value_pct == -5.0


def test_source_not_allowed_inside_window_is_invalid_price() -> None:
    """허용 밖 출처 = 비정상 종가와 같은 묶음(PLAN §2 · POC5-06 SOURCE_NOT_ALLOWED · POC5-16)."""
    rows = _rows(_flat(20))
    r = rows[12]
    rows[12] = PriceRow(r.date, r.close, "Test", None, r.change)
    out = compute_stored_drawdown(rows, end_date=rows[-1].date)
    assert (out.status, out.reason) == ("unavailable", "invalid_price")


@pytest.mark.parametrize(
    "breaker", ["change_mismatch", "change_missing", "change_text", "reswitch"]
)
def test_basis_link_problems_inside_window_have_no_value(breaker: str) -> None:
    rows = _rows(_flat(10) + [110.0] + _flat(9))
    i = 15
    r = rows[i]
    if breaker == "change_mismatch":
        rows[i] = PriceRow(r.date, r.close, FDR, None, 0.05)
    elif breaker == "change_missing":
        rows[i] = PriceRow(r.date, r.close, FDR, None, None)
    elif breaker == "change_text":
        rows[i] = PriceRow(r.date, r.close, FDR, None, "x")
    else:  # FDR → NAVER 재전환
        rows[i] = PriceRow(r.date, r.close, NAVER, None, None)
    out = compute_stored_drawdown(rows, end_date=rows[-1].date)
    assert (out.status, out.reason) == ("unavailable", "basis_unconfirmed")
    assert out.value_pct is None


def test_window_must_end_at_d() -> None:
    rows = _rows(_flat(20))
    out = compute_stored_drawdown(rows, end_date="2099-01-01")
    assert (out.status, out.reason) == ("unavailable", "end_date_unknown")


def test_link_into_the_first_window_row_is_not_checked() -> None:
    """창 밖 → 창 첫 행 연결은 보지 않는다(POC5-16 창 규칙과 같음) · 창 안 연결만."""
    rows = _rows(_flat(21))
    r = rows[1]
    rows[1] = PriceRow(
        r.date, r.close, FDR, None, 0.5
    )  # 창 첫 행(21행 중 [1])의 change 불일치
    out = compute_stored_drawdown(rows, end_date=rows[-1].date)
    assert out.status == "ok"


def test_candidate_end_date_reads_poc5_21_actual_end() -> None:
    cand = {
        "returns": {
            "daily": None,
            "one_month": {"return_pct": 1.0, "price_end_date": "2026-10-13"},
        }
    }
    assert candidate_end_date(cand) == "2026-10-13"
    assert candidate_end_date({"returns": {}}) is None


# ── 임시 DB · 실제 API ────────────────────────────────────────────────────


def _seed(db: Path, ticker: str, closes: list, *, start: date = START) -> None:
    rows = []
    prev = None
    for d, c in zip(_dates(len(closes), start), closes):
        ch = (
            c / prev - 1.0 if (c is not None and prev is not None and prev > 0) else 0.0
        )
        rows.append(EtfDailyPriceRow(ticker, d, c, c, c, c, 1000, ch))
        prev = c if c is not None and c > 0 else prev
    upsert_daily_prices(rows, source=FDR, db_path=db)


def _master(db: Path, tickers: dict[str, str]) -> None:
    upsert_etf_master(
        [EtfMasterRow(tk, nm, "1", 100.0, 1, 1.0) for tk, nm in tickers.items()],
        source="Test",
        db_path=db,
    )


@pytest.fixture
def market(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, api_client  # noqa: F811
) -> dict:
    from app import api_market_topn

    db = api_market_topn.DEFAULT_DB_PATH  # api_client 가 tmp 로 바꾼 경로
    _master(
        db,
        {
            "111111": "고점 뒤 하락 ETF",
            "222222": "새 상장 ETF",
            "333333": "하루 늦은 ETF",
            "444444": "중간 결측 ETF",
            "555555": "출처 다른 ETF",
            "069500": "KODEX 200",
        },
    )
    n = 60
    a = (
        _flat(n - 20) + _flat(5) + [150.0] + _flat(13) + [120.0]
    )  # 마지막 20: 고점 150 → 120
    _seed(db, "111111", a)
    _seed(
        db,
        "222222",
        [100.0 + i for i in range(18)],
        start=START + timedelta(days=n - 18),
    )
    b = _flat(n - 2) + [110.0]  # 끝일이 하루 이르다(D = 58번째 날)
    _seed(db, "333333", b)
    # 하루 늦은 ETF 의 마지막 날짜 다음 날에 종가 0 행(거른 읽기에서 빠짐 · 원본에는 있음)
    upsert_daily_prices(
        [EtfDailyPriceRow("333333", _dates(n)[-1], 0.0, 0.0, 0.0, 0.0, 0, 0.0)],
        source=FDR,
        db_path=db,
    )
    # 마지막 20행 안 빈 종가 · 다른 출처 행(그 앞은 정상 행 40개 — 거른 읽기면 채워져 값이 생긴다)
    c4 = _flat(n)
    c4[n - 8] = None
    _seed(db, "444444", c4)
    _seed(db, "555555", _flat(n))
    d5 = _dates(n)[n - 6]
    upsert_daily_prices(
        [EtfDailyPriceRow("555555", d5, 100.0, 100.0, 100.0, 100.0, 1000, 0.0)],
        source="Test",
        db_path=db,
    )
    _seed(db, "069500", [300.0 - 0.5 * i for i in range(n)])
    snap = tmp_path / "score.json"
    snap.write_text(
        json.dumps(
            {
                "status": "ok",
                "asof_date": "2026-08-27",
                "generated_at": "2026-08-30T00:00:00+00:00",
                "candidates": [
                    {
                        "ticker": "111111",
                        "drawdown_20d": -0.5,
                        "relative_upside_score": 1,
                    },
                    {
                        "ticker": "222222",
                        "drawdown_20d": -0.03,
                        "relative_upside_score": 2,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ml_relative_upside_score, "SCORE_SNAPSHOT_PATH", snap)
    return {"client": api_client, "db": db, "dates": _dates(n)}


def _get(client: TestClient) -> dict:
    res = client.get(
        "/market/topn/latest?n=10&exclude_inverse=false&exclude_leveraged=false"
        "&exclude_synthetic=false&exclude_futures=false"
    )
    assert res.status_code == 200, res.text
    return {c["ticker"]: c for c in res.json()["candidates"]}


def test_api_returns_current_stored_drawdown_per_candidate(market: dict) -> None:
    by = _get(market["client"])
    dates = market["dates"]
    a = by["111111"]["stored_drawdown_20"]
    assert a["status"] == "ok" and a["value_pct"] == -20.0
    assert (a["start_date"], a["end_date"], a["rows"]) == (dates[-20], dates[-1], 20)
    assert (a["peak_close"], a["peak_date"], a["close"]) == (150.0, dates[-15], 120.0)
    # 옛 스냅샷 필드는 그대로(의미 · 값 변경 없음) · 새 객체와 섞지 않는다.
    assert by["111111"]["drawdown_20d"] == -0.5


def test_api_new_listing_has_no_value_even_if_old_snapshot_has_one(
    market: dict,
) -> None:
    by = _get(market["client"])
    n = by["222222"]
    assert n["drawdown_20d"] == -0.03  # 옛 값은 응답에 남지만
    s = n["stored_drawdown_20"]
    assert (s["status"], s["reason"], s["rows"]) == (
        "unavailable",
        "insufficient_history",
        18,
    )
    assert s["value_pct"] is None  # 옛 값으로 채우지 않는다


def test_api_uses_each_candidate_actual_end_not_market_latest(market: dict) -> None:
    by = _get(market["client"])
    dates = market["dates"]
    c = by["333333"]
    assert c["returns"]["one_month"]["price_end_date"] == dates[-2]
    s = c["stored_drawdown_20"]
    # D = 그 종목 마지막 유효 종가 행(시장 최신일 · 원본의 종가 0 행이 아님)
    assert (s["status"], s["end_date"], s["start_date"]) == (
        "ok",
        dates[-2],
        dates[-21],
    )
    assert s["value_pct"] == 0.0 and s["close"] == 110.0


def test_api_invalid_rows_in_window_are_not_refilled_from_older_rows(
    market: dict,
) -> None:
    """DB 읽기 단계에서도 비정상 · 다른 출처 행을 빼고 더 오래된 행으로 채우지 않는다."""
    by = _get(market["client"])
    dates = market["dates"]
    for tk in ("444444", "555555"):
        s = by[tk]["stored_drawdown_20"]
        assert (s["status"], s["reason"]) == ("unavailable", "invalid_price"), tk
        assert (s["rows"], s["start_date"], s["end_date"]) == (
            20,
            dates[-20],
            dates[-1],
        )
        assert s["value_pct"] is None


def test_only_the_pc_market_list_api_builds_the_object(market: dict) -> None:
    """PC 응답 조립 경로에서만(설계 §3) — app · scripts 에서 build 를 부르는 곳은 이 API 하나 · compute_topn 은 그대로."""
    root = Path(__file__).resolve().parents[1]
    hits = sorted(
        str(f.relative_to(root))
        for d in ("app", "scripts")
        for f in (root / d).rglob("*.py")
        if "build_stored_drawdown(" in f.read_text(encoding="utf-8")
        and f.name != "pc_stored_drawdown.py"
    )
    assert hits == ["app/api_market_topn.py"]
    p = compute_topn(
        n=10,
        db_path=market["db"],
        exclude_inverse=False,
        exclude_leveraged=False,
        exclude_synthetic=False,
        exclude_futures=False,
    )
    assert p["candidates"] and all(
        "stored_drawdown_20" not in c for c in p["candidates"]
    )
