"""POC5-22 — PC 후보와 KODEX200 의 동일 기간 수익률 비교(`same_period_kodex200`).

설계 V1 §3 · §4 · §6-3 · PLAN 판정(2026-10-17 · Q1 · Q2 · Q3 (a) · §2 시험 보충).
격리 DB(tmp) · 격리 보유(공통 autouse)만 쓴다. 라이브 DB 를 열지 않는다.

종목(ETF · 매일 저장):
- 111111 장기 — 2025-06-01 ~ 2026-10-14
- 222222 늦게 상장 — 2026-08-01 ~ 2026-10-14 (3개월은 첫 저장 행부터)
- 333333 끝이 이름 — 2026-07-01 ~ 2026-10-13
- 444444 행 1개 — 계산 불가(후보 아님)
- 069500 KODEX200 — 2026-05-01 ~ 2026-10-14
"""

from __future__ import annotations

import copy
import math
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app import api_decision_sessions, api_market_topn, decision_evidence_store
from app import market_topn as market_topn_module
from app.market_data_store import (
    EtfDailyPriceRow,
    EtfMasterRow,
    fetch_price_history,
    upsert_daily_prices,
    upsert_etf_master,
)
from app.market_topn import compute_topn
from app.same_period_kodex200 import (
    REASON_CANDIDATE_PERIOD_UNKNOWN,
    REASON_KODEX200_END_MISSING,
    REASON_KODEX200_START_MISSING,
    close_by_date,
    compare,
)
from tests.test_pc_price_basis import api_client  # noqa: F401 — fixture

END = date(2026, 10, 14)
PERIODS = ("one_month", "three_month")


def _days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def _rows(
    ticker: str, start: date, end: date, base: float, step: float, skip=()
) -> list:
    out = []
    for i, d in enumerate(_days(start, end)):
        if d.isoformat() in skip:
            continue
        c = round(base + step * i + (i % 7) * 0.3, 4)
        out.append(EtfDailyPriceRow(ticker, d.isoformat(), c, c, c, c, 1000 + i, 0))
    return out


def _seed(db: Path, kodex_skip=()) -> None:
    upsert_etf_master(
        [
            EtfMasterRow("111111", "장기 ETF", "1", 100.0, 1, 1.0),
            EtfMasterRow("222222", "늦게 상장 ETF", "1", 100.0, 1, 1.0),
            EtfMasterRow("333333", "끝이 이른 ETF", "1", 100.0, 1, 1.0),
            EtfMasterRow("444444", "행 하나 ETF", "1", 100.0, 1, 1.0),
            EtfMasterRow("069500", "KODEX 200", "1", 100.0, 1, 1.0),
        ],
        source="Test",
        db_path=db,
    )
    rows = (
        _rows("111111", date(2025, 6, 1), END, 100.0, 0.05)
        + _rows("222222", date(2026, 8, 1), END, 50.0, 0.4)
        + _rows("333333", date(2026, 7, 1), END - timedelta(days=1), 80.0, -0.1)
        + _rows("444444", END, END, 10.0, 0.0)
        + _rows("069500", date(2026, 5, 1), END, 300.0, -0.3, skip=kodex_skip)
    )
    upsert_daily_prices(rows, source="Test", db_path=db)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    p = tmp_path / "m.sqlite"
    _seed(p)
    return p


def _topn(db: Path, **kw) -> dict:
    kw.setdefault("n", 10)
    return compute_topn(
        db_path=db,
        exclude_inverse=False,
        exclude_leveraged=False,
        exclude_synthetic=False,
        exclude_futures=False,
        **kw,
    )


def _by_ticker(p: dict) -> dict:
    return {c["ticker"]: c for c in p["candidates"]}


def _closes(db: Path, tk: str) -> dict[str, float]:
    return dict(fetch_price_history(tk, db_path=db))


# ── 순수 계산(설계 §3) ────────────────────────────────────────────────────


def test_known_two_prices_example() -> None:
    """후보 +10% · KODEX200 +5% → +5%p(비율로 다시 나누지 않음)."""
    out = compare(
        10.0, "2026-09-14", "2026-10-14", {"2026-09-14": 100.0, "2026-10-14": 105.0}
    )
    assert out == {
        "status": "ok",
        "reason": None,
        "start_date": "2026-09-14",
        "end_date": "2026-10-14",
        "candidate_return_pct": 10.0,
        "kodex200_return_pct": 5.0,
        "diff_pctp": 5.0,
    }


def test_exact_dates_only_no_neighbor_substitution() -> None:
    k = {"2026-09-13": 99.0, "2026-09-15": 101.0, "2026-10-14": 105.0}
    a = compare(10.0, "2026-09-14", "2026-10-14", k)
    assert (a["status"], a["reason"]) == ("unavailable", REASON_KODEX200_START_MISSING)
    assert a["kodex200_return_pct"] is None and a["diff_pctp"] is None
    assert a["candidate_return_pct"] == 10.0  # 후보 자체 수익률은 숨기지 않는다
    k2 = {"2026-09-14": 100.0, "2026-10-13": 104.0, "2026-10-15": 106.0}
    b = compare(10.0, "2026-09-14", "2026-10-14", k2)
    assert (b["status"], b["reason"]) == ("unavailable", REASON_KODEX200_END_MISSING)


@pytest.mark.parametrize("bad", [0, -1.0, math.nan, math.inf, None, True, "105"])
def test_invalid_kodex_prices_are_missing(bad: Any) -> None:
    hist = [("2026-09-14", 100.0), ("2026-10-14", bad)]
    k = close_by_date(hist)
    assert "2026-10-14" not in k
    out = compare(
        10.0, "2026-09-14", "2026-10-14", {"2026-09-14": 100.0, "2026-10-14": bad}
    )
    assert out["reason"] == REASON_KODEX200_END_MISSING


@pytest.mark.parametrize(
    "cand, start, end",
    [(None, "a", "b"), (math.nan, "a", "b"), (10.0, None, "b"), (10.0, "a", None)],
)
def test_candidate_period_unknown(cand, start, end) -> None:
    out = compare(cand, start, end, {"a": 1.0, "b": 2.0})
    assert (out["status"], out["reason"]) == (
        "unavailable",
        REASON_CANDIDATE_PERIOD_UNKNOWN,
    )
    assert out["diff_pctp"] is None


def test_difference_uses_values_before_rounding() -> None:
    cand = 1 / 3  # 0.33333…
    out = compare(cand, "a", "b", {"a": 300.0, "b": 300.5})
    kodex = (300.5 / 300.0 - 1.0) * 100.0
    assert out["diff_pctp"] == round(cand - kodex, 4)
    assert out["candidate_return_pct"] == round(cand, 4)
    assert out["kodex200_return_pct"] == round(kodex, 4)


# ── compute_topn 연결 ─────────────────────────────────────────────────────


def test_same_period_uses_candidate_actual_rows(db: Path) -> None:
    pc = _topn(db, same_period_kodex200=True, actual_price_dates=True)
    k = _closes(db, "069500")
    seen = 0
    for tk, c in _by_ticker(pc).items():
        closes = _closes(db, tk)
        for label in PERIODS:
            r = c["returns"][label]
            sp = c["same_period_kodex200"][label]
            assert r is not None and sp["status"] == "ok", (tk, label)
            # A · B = 그 수익률의 실제 시작 · 끝 행(POC5-21 날짜와 같음).
            assert (sp["start_date"], sp["end_date"]) == (
                r["price_start_date"],
                r["price_end_date"],
            )
            a, b = sp["start_date"], sp["end_date"]
            raw_cand = (closes[b] / closes[a] - 1.0) * 100.0
            raw_k = (k[b] / k[a] - 1.0) * 100.0
            assert sp["candidate_return_pct"] == r["return_pct"] == round(raw_cand, 4)
            assert sp["kodex200_return_pct"] == round(raw_k, 4)
            assert sp["diff_pctp"] == round(raw_cand - raw_k, 4)
            seen += 1
    assert seen >= 8


def test_short_history_and_earlier_end_use_their_own_period(db: Path) -> None:
    c = _by_ticker(_topn(db, same_period_kodex200=True))
    k = _closes(db, "069500")
    late = c["222222"]["same_period_kodex200"]["three_month"]
    assert (late["start_date"], late["end_date"]) == ("2026-08-01", END.isoformat())
    assert late["kodex200_return_pct"] == round(
        (k[END.isoformat()] / k["2026-08-01"] - 1) * 100, 4
    )
    stale = c["333333"]["same_period_kodex200"]["one_month"]
    assert stale["end_date"] == (END - timedelta(days=1)).isoformat()
    assert stale["status"] == "ok"
    # 다른 후보와 기간이 다르면 비교할 KODEX200 기간도 다르다.
    assert (
        c["111111"]["same_period_kodex200"]["three_month"]["start_date"]
        != late["start_date"]
    )


def test_missing_kodex_rows_are_reasons_not_neighbors(tmp_path: Path) -> None:
    base = tmp_path / "base.sqlite"
    _seed(base)
    a = _by_ticker(_topn(base, same_period_kodex200=True))["111111"]
    start_1m = a["same_period_kodex200"]["one_month"]["start_date"]
    end_1m = a["same_period_kodex200"]["one_month"]["end_date"]
    db1 = tmp_path / "no_start.sqlite"
    _seed(db1, kodex_skip={start_1m})
    sp1 = _by_ticker(_topn(db1, same_period_kodex200=True))["111111"][
        "same_period_kodex200"
    ]
    assert sp1["one_month"]["reason"] == REASON_KODEX200_START_MISSING
    assert sp1["one_month"]["candidate_return_pct"] is not None
    assert sp1["three_month"]["status"] == "ok"  # 다른 기간은 그대로
    db2 = tmp_path / "no_end.sqlite"
    _seed(db2, kodex_skip={end_1m})
    sp2 = _by_ticker(_topn(db2, same_period_kodex200=True))["111111"][
        "same_period_kodex200"
    ]
    assert sp2["one_month"]["reason"] == REASON_KODEX200_END_MISSING
    assert sp2["three_month"]["reason"] == REASON_KODEX200_END_MISSING


def _strip_same(p: dict) -> dict:
    out = copy.deepcopy(p)
    out.pop("runtime_seconds", None)
    for c in out["candidates"]:
        c.pop("same_period_kodex200", None)
    return out


@pytest.mark.parametrize("basis", ["daily", "one_month", "three_month"])
@pytest.mark.parametrize("order", ["desc", "asc"])
def test_flag_off_unchanged_and_flag_only_adds_object(
    db: Path, basis: str, order: str
) -> None:
    default = _topn(db, basis=basis, order=order)
    pc = _topn(db, basis=basis, order=order, same_period_kodex200=True)
    assert all("same_period_kodex200" not in c for c in default["candidates"])
    assert all("same_period_kodex200" in c for c in pc["candidates"])
    d = copy.deepcopy(default)
    d.pop("runtime_seconds", None)
    # 수익률 · 기존 excess_return · basis_* · 순위 · 필터 · 시장 판정 전부 같음.
    assert _strip_same(pc) == d


def test_flag_adds_no_reads(db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    real = market_topn_module.fetch_price_history

    def counting(ticker, *a, **kw):
        calls.append(ticker)
        return real(ticker, *a, **kw)

    monkeypatch.setattr(market_topn_module, "fetch_price_history", counting)
    _topn(db)
    off = list(calls)
    calls.clear()
    _topn(db, same_period_kodex200=True)
    assert calls == off  # KODEX200 을 후보마다 다시 읽지 않는다
    assert off.count("069500") == calls.count("069500")


def test_only_pc_apis_turn_the_flag_on() -> None:
    root = Path(__file__).resolve().parents[1]
    pattern = re.compile(r"same_period_kodex200\s*=\s*True")
    hits = sorted(
        str(f.relative_to(root))
        for d in ("app", "scripts")
        for f in (root / d).rglob("*.py")
        if pattern.search(f.read_text(encoding="utf-8"))
    )
    assert hits == ["app/api_holdings_market_evidence.py", "app/api_market_topn.py"]


def test_no_research_module_on_the_default_path() -> None:
    """판정 Q1 (a) — 연결 검사 · 연구 모듈 import 를 운영 기본 경로에 더하지 않는다."""
    root = Path(__file__).resolve().parents[1]
    research = "('app.reentry_review.prices', 'app.pc_price_volatility')"
    code = (
        "import sys; import app.market_topn, app.same_period_kodex200; "
        f"print(','.join(m for m in {research} if m in sys.modules))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert out == ""
    src = (root / "app" / "same_period_kodex200.py").read_text(encoding="utf-8")
    assert "import" in src and "reentry_review" not in src and "link_break" not in src


# ── PC API ────────────────────────────────────────────────────────────────


def test_pc_market_api_and_holdings_api_copy(
    api_client: TestClient,  # noqa: F811 — tests.test_pc_price_basis 의 fixture
) -> None:
    db = api_market_topn.DEFAULT_DB_PATH
    _seed(db)
    params = {
        "exclude_inverse": False,
        "exclude_leveraged": False,
        "exclude_synthetic": False,
        "exclude_futures": False,
    }
    market = api_client.get("/market/topn/latest", params=params).json()
    sp = {c["ticker"]: c["same_period_kodex200"] for c in market["candidates"]}
    assert sp["111111"]["one_month"]["status"] == "ok"
    assert sp["111111"]["one_month"]["diff_pctp"] is not None
    # Q2 (a) — 보유 근거 PC 사본: 상위 후보와 연결된 보유 종목만 같은 객체 · 아니면 None.
    # 보유 근거 API 의 후보 계산(기본 필터)에서 빠지는 보유 ETF — 가격은 있어도 새 계산 경로를 만들지 않는다.
    upsert_etf_master(
        [EtfMasterRow("777777", "테스트 레버리지 ETF", "1", 100.0, 1, 1.0)],
        source="Test",
        db_path=db,
    )
    upsert_daily_prices(
        _rows("777777", date(2026, 5, 1), END, 70.0, 0.2), source="Test", db_path=db
    )
    payload = [
        {"ticker": t, "name": t + "명", "quantity": 1, "avg_buy_price": 100}
        for t in ("111111", "005930", "777777")
    ]
    assert api_client.put("/holdings", json={"holdings": payload}).status_code == 200
    ev = api_client.get("/holdings/market-evidence/latest").json()
    by = {h["ticker"]: h for h in ev["holdings"]}
    assert by["111111"]["same_period_kodex200"] == sp["111111"]
    assert by["005930"]["same_period_kodex200"] is None
    # 상위 후보 밖 보유 ETF(기본 필터 제외) — 값 없음(기존 제공 범위 · 판정 Q2).
    assert by["777777"]["same_period_kodex200"] is None
    # 기존 excess_return 은 그대로(새 값으로 바꾸거나 채우지 않음).
    default = compute_topn(n=10, db_path=db)
    old = {c["ticker"]: c["excess_return"] for c in default["candidates"]}["111111"]
    assert (
        by["111111"]["excess_return"]["vs_kodex200_1m_pctp"]
        == old["vs_kodex200_1m_pctp"]
    )


# ── AI 세션 저장(candidate_snapshot 선택 필드) ─────────────────────────────


@pytest.fixture
def decision_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    fake = tmp_path / "decision_evidence.sqlite"
    monkeypatch.setattr(decision_evidence_store, "DEFAULT_DB_PATH", fake)
    monkeypatch.setattr(api_decision_sessions, "DEFAULT_DB_PATH", fake)
    return TestClient(api_module.app)


def _session(snapshot: list[dict]) -> dict:
    return dict(
        asof="2026-10-14",
        source_screen="market_discovery",
        filters={
            "exclude_inverse": True,
            "exclude_leveraged": True,
            "exclude_synthetic": True,
            "exclude_futures": True,
        },
        candidate_snapshot=snapshot,
        question_text="질문",
        gpt_answer_text="답",
        gemini_answer_text="",
        claude_answer_text="",
        user_memo="",
        user_verdict="needs_constituents",
        next_checks=[],
        linked_market_refresh_id=None,
    )


def test_decision_session_keeps_same_period_object(decision_client: TestClient) -> None:
    obj = {
        "one_month": {
            "status": "ok",
            "reason": None,
            "start_date": "2026-09-14",
            "end_date": "2026-10-14",
            "candidate_return_pct": 22.2689,
            "kodex200_return_pct": -9.8615,
            "diff_pctp": 32.1304,
        },
        "three_month": None,
    }
    base = {"rank": 1, "ticker": "0005D0", "name": "SOL", "tags": []}
    rid = decision_client.post(
        "/decision/sessions",
        json=_session([{**base, "same_period_kodex200": obj}, {**base, "ticker": "X"}]),
    ).json()["id"]
    rec = decision_client.get(f"/decision/sessions/{rid}").json()["record"]
    assert rec["candidate_snapshot"][0]["same_period_kodex200"] == obj
    assert rec["candidate_snapshot"][1]["same_period_kodex200"] is None  # 없으면 없음
