"""POC5-09 — PC 화면용 가격 흐름 기준일 정정 (설계서 §9-4 · PLAN §7).

순수 사본 처리 + 실제 GET /holdings/market-evidence/latest(tmp DB · 격리 fixture).
라이브 DB · 라이브 보유 파일을 열지 않는다.
"""

from __future__ import annotations

import copy
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import (
    api as api_module,
    api_holdings_market_evidence,
    api_market_topn,
    etf_constituents_store,
    etf_nav_store,
    market_data_store,
    market_refresh_service,
)
from app import holdings as holdings_module
from app.holdings_market_evidence import build_holdings_market_evidence
from app.market_data_store import EtfDailyPriceRow, upsert_daily_prices
from app.market_topn import DEFAULT_BASIS, DEFAULT_N, DEFAULT_ORDER, compute_topn
from app.pc_price_basis import apply_pc_price_basis

REF = "2026-10-08"


def _dates_desc(end: str, n: int = 21, skip: tuple[int, ...] = ()) -> list[str]:
    d = date.fromisoformat(end)
    out: list[str] = []
    k = 0
    while len(out) < n:
        if k not in skip:
            out.append((d - timedelta(days=k)).isoformat())
        k += 1
    return out


def _close(r: float) -> float:
    return 100.0 * (1 + r / 100)


def _ret(r: float) -> float:
    # 단기 흐름 산식((끝 - 시작) / 시작 × 100)으로 다시 구한 값 — 부동소수 그대로.
    return (_close(r) - 100.0) / 100.0 * 100.0


def _rows(end: str, skip: tuple[int, ...] = (), r: float = 0.0, n: int = 21) -> list:
    """최신순 n행(기본 21) · 최신 종가만 r% 다르고 나머지 100 → 5 · 10 · 20일 변화 모두 r."""
    dates = _dates_desc(end, n=n, skip=skip)
    return [
        (x, _close(r) if i == 0 else 100.0, 10, "FinanceDataReader")
        for i, x in enumerate(dates)
    ]


def _note(v: float) -> str:
    return f"20거래일 KODEX200 대비 단기 흐름 차이 {v:+.2f}%p."


MD = "현재 Market Discovery 후보에 포함되어 있지 않습니다."


def _item(ticker: str, r, *, status="ok", notes=None, account="일반", ev=1000.0):
    """builder 와 같은 계산 결과(KODEX200 은 평평 → KODEX200 대비 = 자기 변화)."""
    v = _ret(r) if (status == "ok" and r is not None) else None
    return {
        "ticker": ticker,
        "name": ticker + "명",
        "account_group": account,
        "holding": {
            "quantity": 1.0,
            "avg_buy_price": 900.0,
            "evaluation_amount": ev,
            "pnl_rate_pct": 11.1,
            "current_price": 1000.0,
            "price_asof": "2026-10-12",
        },
        "returns": {"status": "unavailable"},
        "short_term_momentum": {
            "status": status,
            "return_5d_pct": v,
            "return_10d_pct": v,
            "return_20d_pct": v,
            "excess_vs_kodex200_5d_pctp": v,
            "excess_vs_kodex200_10d_pctp": v,
            "excess_vs_kodex200_20d_pctp": v,
        },
        "nav_discount": {"status": "ok", "nav": 1000.0},
        "evidence_notes": (
            notes if notes is not None else ([MD, _note(v)] if v is not None else [MD])
        ),
    }


def _evidence(items: list[dict]) -> dict:
    return {
        "status": "ok",
        "summary": {"evidence_unavailable_count": 0},
        "holdings": items,
        "judgment_summary": {
            "market_position": {"available": True},
            "holdings": {"available": True, "top_holdings": [], "coverage": {}},
            "data_status": {},
        },
    }


def _rows_by_ticker(**extra) -> dict:
    base = {"069500": _rows(REF)}
    base.update(extra)
    return base


def test_same_date_values_are_kept_and_input_not_mutated() -> None:
    ev = _evidence([_item("111111", -3.0)])
    before = copy.deepcopy(ev)
    out = apply_pc_price_basis(ev, _rows_by_ticker(**{"111111": _rows(REF, r=-3.0)}))
    assert ev == before  # 공유 builder 결과(입력)는 바뀌지 않는다
    it = out["holdings"][0]
    # 두 읽기 사이 자료가 그대로면 같은 읽기로 다시 구한 값 = builder 값.
    assert it["short_term_momentum"] == before["holdings"][0]["short_term_momentum"]
    assert it["evidence_notes"] == before["holdings"][0]["evidence_notes"]
    pd = it["price_dates"]
    assert pd["comparison"] == "ok" and pd["end_date"] == REF
    assert pd["start_date_5d"] == "2026-10-03" and pd["start_date_20d"] == "2026-09-18"
    pb = out["price_basis"]
    assert pb["reference_date"] == REF and pb["reference_ticker"] == "069500"
    assert pb["kodex200_start_date_20d"] == "2026-09-18"
    assert pb["date_mismatch"] == []


def test_values_and_dates_come_from_the_same_read() -> None:
    """설계 §10-2-1 — builder 계산 뒤 새 날이 저장돼도 옛 값에 새 날짜를 붙이지 않는다."""
    # builder 는 10-08 자료로 5일 -10% 를 계산했다.
    ev = _evidence([_item("111111", -10.0)])
    before = copy.deepcopy(ev)
    # 그 뒤 종목 · KODEX200 모두 10-09 가 저장된 읽기(종목 최신 종가 +5%).
    rows = {"069500": _rows("2026-10-09"), "111111": _rows("2026-10-09", r=5.0)}
    out = apply_pc_price_basis(ev, rows)
    assert ev == before
    it = out["holdings"][0]
    stm = it["short_term_momentum"]
    assert it["price_dates"]["end_date"] == "2026-10-09"
    assert it["price_dates"]["comparison"] == "ok"
    assert stm["return_5d_pct"] == _ret(5.0)  # 10-09 날짜와 같은 읽기의 값
    assert stm["excess_vs_kodex200_20d_pctp"] == _ret(5.0)
    # 단기 흐름 메모 한 줄도 이 값으로 바뀐다(옛 값 문구 없음).
    assert it["evidence_notes"] == [MD, _note(_ret(5.0))]
    top = out["judgment_summary"]["holdings"]["top_holdings"]
    assert top[0]["return_5d_pct"] == _ret(5.0)


def test_builder_unavailable_but_same_read_sufficient_uses_the_read() -> None:
    # builder 때는 이력이 짧아 unavailable 이었고, 그 뒤 읽기에는 21행이 있다.
    item = _item(
        "333333",
        None,
        status="unavailable",
        notes=[MD, "단기 흐름은 데이터 부족으로 확인할 수 없습니다."],
    )
    out = apply_pc_price_basis(
        _evidence([item]), _rows_by_ticker(**{"333333": _rows(REF, r=-1.0)})
    )
    it = out["holdings"][0]
    assert it["short_term_momentum"]["status"] == "ok"
    assert it["short_term_momentum"]["return_5d_pct"] == _ret(-1.0)
    assert it["evidence_notes"] == [MD, _note(_ret(-1.0))]


def test_date_mismatch_clears_current_values_and_keeps_holding() -> None:
    ev = _evidence([_item("000660", -9.8)])
    before = copy.deepcopy(ev)
    out = apply_pc_price_basis(
        ev, _rows_by_ticker(**{"000660": _rows("2026-08-12", r=-9.8)})
    )
    assert ev == before  # 정정이 일어나도 입력(공유 builder 결과)은 그대로
    it = out["holdings"][0]
    stm = it["short_term_momentum"]
    assert stm["status"] == "unavailable"
    assert all(stm[k] is None for k in stm if k != "status")
    assert it["price_dates"]["comparison"] == "date_mismatch"
    assert it["price_dates"]["end_date"] == "2026-08-12"
    # 단기 흐름 메모만 빠지고(사유는 price_dates) 다른 메모는 남는다 · '데이터 부족' 문구를 붙이지 않는다.
    assert it["evidence_notes"] == [MD]
    # 보유 · 현재 시세 · NAV 는 그대로.
    assert it["holding"] == ev["holdings"][0]["holding"]
    assert it["nav_discount"] == ev["holdings"][0]["nav_discount"]
    assert out["price_basis"]["date_mismatch"] == [
        {"ticker": "000660", "name": "000660명", "end_date": "2026-08-12"}
    ]


def test_window_mismatch_clears_only_that_excess() -> None:
    # 기준일은 같지만 12일 전 하루가 비어 20일 비교 기간 시작만 KODEX200 과 다르다.
    ev = _evidence([_item("222222", -2.0)])
    before = copy.deepcopy(ev)
    out = apply_pc_price_basis(
        ev, _rows_by_ticker(**{"222222": _rows(REF, skip=(12,), r=-2.0)})
    )
    assert ev == before  # 정정이 일어나도 입력(공유 builder 결과)은 그대로
    it = out["holdings"][0]
    stm = it["short_term_momentum"]
    assert it["price_dates"]["comparison"] == "window_mismatch"
    # 기준일이 같아 자기 5 · 10 · 20일 값은 유효 — status 는 ok 그대로(최대 3개 후보 유지).
    assert stm["status"] == "ok"
    assert stm["excess_vs_kodex200_20d_pctp"] is None
    assert stm["excess_vs_kodex200_5d_pctp"] == _ret(-2.0)  # 5일 · 10일 기간은 같다
    assert stm["excess_vs_kodex200_10d_pctp"] == _ret(-2.0)
    assert stm["return_20d_pct"] == _ret(-2.0)  # 종목 자신의 20일 변화는 그대로
    assert (
        it["price_dates"]["start_date_20d"]
        != out["price_basis"]["kodex200_start_date_20d"]
    )
    assert it["evidence_notes"] == [MD]  # 비운 KODEX200 대비 20일 메모는 빠진다


def test_unavailable_items_are_left_as_is() -> None:
    item = _item(
        "333333",
        None,
        status="unavailable",
        notes=["단기 흐름은 데이터 부족으로 확인할 수 없습니다."],
    )
    out = apply_pc_price_basis(_evidence([item]), _rows_by_ticker(**{"333333": []}))
    it = out["holdings"][0]
    assert it["short_term_momentum"] == item["short_term_momentum"]
    assert it["evidence_notes"] == item["evidence_notes"]
    assert it["price_dates"] == {
        "end_date": None,
        "start_date_5d": None,
        "start_date_20d": None,
        "comparison": "unavailable",
    }


def test_top3_refills_from_same_date_candidates() -> None:
    items = [
        _item("000660", -20.0),  # 08-12 자료 — 기존 규칙이면 1위
        _item("222222", -5.0),  # 기간 불일치 — 기준일은 같아 자기 5일 값으로 후보 유지
        _item("111111", -3.0),
        _item("444444", -2.0),
        _item("555555", -2.0),  # 동점 → 종목코드 순
        _item("666666", 1.0),
    ]
    rows = _rows_by_ticker(
        **{
            "000660": _rows("2026-08-12", r=-20.0),
            "222222": _rows(REF, skip=(12,), r=-5.0),
            "111111": _rows(REF, r=-3.0),
            "444444": _rows(REF, r=-2.0),
            "555555": _rows(REF, r=-2.0),
            "666666": _rows(REF, r=1.0),
        }
    )
    out = apply_pc_price_basis(_evidence(items), rows)
    top = out["judgment_summary"]["holdings"]["top_holdings"]
    assert [t["ticker"] for t in top] == ["222222", "111111", "444444"]
    assert top[0]["excess_vs_kodex200_20d_pctp"] is None  # 비운 비교값은 비운 채
    cov = out["judgment_summary"]["holdings"]["coverage"]
    assert cov["total"] == 6
    # 000660(값 비움) · 222222(KODEX200 대비 비움)는 자료 확인 필요로 센다.
    assert cov["need_check"] == 2
    assert out["judgment_summary"]["market_position"] == {"available": True}


def test_top3_has_fewer_when_few_same_date_candidates() -> None:
    items = [_item("000660", -20.0), _item("111111", -3.0)]
    rows = _rows_by_ticker(
        **{"000660": _rows("2026-08-12", r=-20.0), "111111": _rows(REF, r=-3.0)}
    )
    out = apply_pc_price_basis(_evidence(items), rows)
    assert [
        t["ticker"] for t in out["judgment_summary"]["holdings"]["top_holdings"]
    ] == ["111111"]


def test_same_ticker_in_two_accounts_listed_once() -> None:
    items = [_item("000660", -9.8, account="A"), _item("000660", -9.8, account="B")]
    out = apply_pc_price_basis(
        _evidence(items), _rows_by_ticker(**{"000660": _rows("2026-08-12", r=-9.8)})
    )
    assert len(out["price_basis"]["date_mismatch"]) == 1
    assert all(
        h["price_dates"]["comparison"] == "date_mismatch" for h in out["holdings"]
    )


def test_evidence_unavailable_count_recounted_on_copy() -> None:
    items = [_item("000660", -9.8), _item("111111", -3.0)]
    rows = _rows_by_ticker(
        **{"000660": _rows("2026-08-12", r=-9.8), "111111": _rows(REF, r=-3.0)}
    )
    ev = _evidence(items)
    out = apply_pc_price_basis(ev, rows)
    assert out["summary"]["evidence_unavailable_count"] == 1
    assert ev["summary"]["evidence_unavailable_count"] == 0


SHORT = "단기 흐름은 데이터 부족으로 확인할 수 없습니다."
OLD = "2026-08-12"


@pytest.mark.parametrize(
    "mine_n, mine_end, bench_n, skip, expected, note",
    [
        # 종목 저장 가격 없음 → 날짜가 없어 비교 불가(이력 부족 문구)
        (0, REF, 21, (), "unavailable", SHORT),
        # KODEX200 저장 가격 없음 → 비교 기준일 없음
        (21, REF, 0, (), "unavailable", SHORT),
        # 기준일이 다르면 이력 길이와 상관없이 기준일 불일치(검증자 r1 재현 = 08-12 · 20행)
        (20, OLD, 21, (), "date_mismatch", None),
        (21, OLD, 21, (), "date_mismatch", None),
        (5, OLD, 20, (), "date_mismatch", None),
        (21, OLD, 5, (), "date_mismatch", None),
        # 기준일은 같고 이력이 짧으면 이력 부족
        (20, REF, 21, (), "unavailable", SHORT),
        (21, REF, 20, (), "unavailable", SHORT),
        # 둘 다 21행 · 기준일 같음 → 비교 기간이 같으면 ok, 다르면 그 대비값만 비움
        (21, REF, 21, (), "ok", "value"),
        (21, REF, 21, (12,), "window_mismatch", None),
    ],
)
def test_state_matrix_date_before_history(
    mine_n, mine_end, bench_n, skip, expected, note
) -> None:
    """판정 순서 = 기준일 비교 → 이력 길이 → 비교 기간(설계 §9-4-2 · 검증자 r1)."""
    rows = {
        "069500": _rows(REF, n=bench_n),
        "777777": _rows(mine_end, skip=skip, r=-1.0, n=mine_n),
    }
    ev = _evidence([_item("777777", -1.0)])
    before = copy.deepcopy(ev)
    out = apply_pc_price_basis(ev, rows)
    assert ev == before
    it = out["holdings"][0]
    stm = it["short_term_momentum"]
    assert it["price_dates"]["comparison"] == expected
    listed = [m["ticker"] for m in out["price_basis"]["date_mismatch"]]
    assert listed == (["777777"] if expected == "date_mismatch" else [])
    if expected in ("date_mismatch", "unavailable"):
        assert stm["status"] == "unavailable"
        assert all(stm[k] is None for k in stm if k != "status")
    else:
        assert stm["status"] == "ok"
        assert stm["return_5d_pct"] == _ret(-1.0)
    if expected == "date_mismatch":
        assert it["price_dates"]["end_date"] == OLD
    expected_notes = [MD] + (
        [_note(_ret(-1.0))] if note == "value" else [note] if note else []
    )
    assert it["evidence_notes"] == expected_notes
    # 기준일이 다른 종목은 최대 3개에 들어가지 않는다.
    top = [t["ticker"] for t in out["judgment_summary"]["holdings"]["top_holdings"]]
    assert top == (["777777"] if expected in ("ok", "window_mismatch") else [])


# ── 실제 GET 응답(tmp DB) ─────────────────────────────────────────────────────


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    fake_db = tmp_path / "market_data.sqlite"
    monkeypatch.setattr(api_market_topn, "DEFAULT_DB_PATH", fake_db)
    monkeypatch.setattr(market_data_store, "DEFAULT_DB_PATH", fake_db)
    monkeypatch.setattr(etf_constituents_store, "DEFAULT_DB_PATH", fake_db)
    monkeypatch.setattr(etf_nav_store, "DEFAULT_DB_PATH", fake_db)
    monkeypatch.setattr(api_holdings_market_evidence, "MARKET_DB_PATH", fake_db)
    market_refresh_service.reset_state_for_testing(db_path=fake_db)
    return TestClient(api_module.app)


def _seed(db: Path, ticker: str, end: str, closes: list[float], skip=()) -> None:
    dates = list(reversed(_dates_desc(end, n=len(closes), skip=skip)))
    rows = [
        EtfDailyPriceRow(ticker, d, c, c, c, c, 1000 + i, 0)
        for i, (d, c) in enumerate(zip(dates, closes))
    ]
    upsert_daily_prices(rows, source="FinanceDataReader", db_path=db)


def _closes(r5_pct: float) -> list[float]:
    # 30개 · 마지막 6개 구간 5일 변화 = r5_pct.
    base = [100.0] * 24
    return base + [100.0] * 5 + [100.0 * (1 + r5_pct / 100)]


def test_endpoint_applies_price_basis_and_keeps_shared_builder(
    api_client: TestClient,
) -> None:
    db = api_market_topn.DEFAULT_DB_PATH
    _seed(db, "069500", REF, _closes(0.0))
    _seed(db, "000660", "2026-08-12", _closes(-20.0))
    _seed(db, "111111", REF, _closes(-3.0))
    _seed(db, "444444", REF, _closes(-2.0))
    _seed(db, "555555", REF, _closes(1.0))
    payload = [
        {"ticker": t, "name": t + "명", "quantity": 1, "avg_buy_price": 100}
        for t in ("000660", "111111", "444444", "555555")
    ]
    assert api_client.put("/holdings", json={"holdings": payload}).status_code == 200

    body = api_client.get("/holdings/market-evidence/latest").json()
    by = {h["ticker"]: h for h in body["holdings"]}
    assert body["price_basis"]["reference_date"] == REF
    assert [m["ticker"] for m in body["price_basis"]["date_mismatch"]] == ["000660"]
    sk = by["000660"]
    assert sk["short_term_momentum"]["status"] == "unavailable"
    assert sk["short_term_momentum"]["return_5d_pct"] is None
    assert sk["price_dates"] == {
        "end_date": "2026-08-12",
        "start_date_5d": "2026-08-07",
        "start_date_20d": "2026-07-23",
        "comparison": "date_mismatch",
    }
    assert by["111111"]["short_term_momentum"]["return_5d_pct"] == pytest.approx(-3.0)
    top = [t["ticker"] for t in body["judgment_summary"]["holdings"]["top_holdings"]]
    assert top == ["111111", "444444", "555555"]
    # 거래량 = 같은 최근 행 읽기 · 자기 기준일(개별주는 08-12 그대로).
    assert sk["stored_volume"]["asof_date"] == "2026-08-12"
    assert sk["stored_volume"]["volume"] == 1029
    assert sk["stored_volume"]["source"] == "FinanceDataReader"

    # 공유 builder(PUSH · 초안 경로)는 그대로 — 같은 입력이면 08-12 값과 기존 선정을 유지한다.
    shared = build_holdings_market_evidence(
        holdings=holdings_module.load(),
        topn_payload=compute_topn(
            n=DEFAULT_N, db_path=db, basis=DEFAULT_BASIS, order=DEFAULT_ORDER
        ),
        market_quotes={},
        db_path=db,
        holdings_asof=None,
    )
    shared_sk = next(h for h in shared["holdings"] if h["ticker"] == "000660")
    assert shared_sk["short_term_momentum"]["status"] == "ok"
    assert shared_sk["short_term_momentum"]["return_5d_pct"] == pytest.approx(-20.0)
    assert "price_dates" not in shared_sk and "price_basis" not in shared
    shared_top = [
        t["ticker"] for t in shared["judgment_summary"]["holdings"]["top_holdings"]
    ]
    assert shared_top[0] == "000660"
    # 두 읽기 사이 자료가 그대로면, 같은 읽기로 다시 구한 응답 값 = builder 값(기준일이 같은 종목).
    for t in ("111111", "444444", "555555"):
        sh = next(h for h in shared["holdings"] if h["ticker"] == t)
        assert by[t]["short_term_momentum"] == sh["short_term_momentum"]
        assert by[t]["evidence_notes"] == sh["evidence_notes"]


def test_price_dates_equal_short_term_momentum_dates(tmp_path: Path) -> None:
    """날짜 키 = 실제 단기 흐름 계산이 쓴 날짜(가격 없는 행 · 종가 0 행은 둘 다 건너뜀)."""
    from app.market_data_store import EtfDailyPriceRow as Row
    from app.pc_price_basis import load_recent_price_rows
    from app.short_term_momentum import compute_short_term_momentum_batch

    db = tmp_path / "m.sqlite"
    _seed(db, "069500", REF, [100.0 + i for i in range(30)])
    _seed(db, "111111", REF, [50.0 + i for i in range(30)])
    # 창 가운데에 가격 없는 행 · 종가 0 행을 넣는다(가격 날짜가 아니다).
    upsert_daily_prices(
        [
            Row("111111", "2026-10-09", None, None, None, None, 5, None),
            Row("111111", "2026-09-30", 1, 1, 1, 0.0, 5, 0),
        ],
        source="FinanceDataReader",
        db_path=db,
    )
    stm = compute_short_term_momentum_batch(["111111"], db_path=db)["111111"]
    rows = load_recent_price_rows(["111111"], db_path=db)
    ev = _evidence([_item("111111", stm.return_5d_pct)])
    pd = apply_pc_price_basis(ev, rows)["holdings"][0]["price_dates"]
    assert pd["end_date"] == stm.end_date == REF
    assert pd["start_date_5d"] == stm.start_date_5d
    assert pd["start_date_20d"] == stm.start_date_20d
    # 종가 0 행(09-30)이 빠져 종목 10 · 20일 비교 기간 시작이 KODEX200 과 달라진다 → 그 비교값만 비움.
    assert pd["comparison"] == "window_mismatch"


def test_endpoint_short_and_old_history_is_date_mismatch(
    api_client: TestClient,
) -> None:
    """검증자 r1 재현 — 종목 08-12 · 20행 / KODEX200 10-08 · 30행 → 기준일 불일치로 보인다."""
    db = api_market_topn.DEFAULT_DB_PATH
    _seed(db, "069500", REF, _closes(0.0))
    _seed(db, "000660", "2026-08-12", [100.0] * 19 + [90.0])
    payload = [
        {"ticker": "000660", "name": "SK하이닉스", "quantity": 1, "avg_buy_price": 100}
    ]
    assert api_client.put("/holdings", json={"holdings": payload}).status_code == 200
    body = api_client.get("/holdings/market-evidence/latest").json()
    sk = body["holdings"][0]
    assert sk["price_dates"]["comparison"] == "date_mismatch"
    assert sk["price_dates"]["end_date"] == "2026-08-12"
    assert sk["short_term_momentum"]["status"] == "unavailable"
    assert [m["ticker"] for m in body["price_basis"]["date_mismatch"]] == ["000660"]
