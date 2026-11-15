"""POC6-30 — 섹터요약 보강 대조.

구성 행 종류 · 지수 계열 · 대조 2 · 3 · 근거 · 범위 · 사본 수집 · 대조표.

PLAN docs/ai_plan/POC6/POC6_30_SECTOR_SUMMARY_CONSTITUENTS_PLAN_V1.md §3 ·
판정 …_PLAN_DECISION_2026-11-14.md.
임시 DB · 고정 응답 · 가짜 수집기만 쓴다(라이브 DB · 외부 호출 없음).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

import pytest

from app import sector_constituents_comparison as C
from app.etf_constituents_fetcher import FetchedConstituent, FetchResult
from app.etf_constituents_service import refresh_constituents
from app.etf_constituents_store import init_constituents_db
from app.sector_constituents_report import headline, render_html
from scripts import run_sector_constituents_comparison as R
from tests.test_poc6_28_etf_compare import (  # noqa: F401 — market 은 fixture
    DICTIONARY,
    OFFICIAL,
    _run,
    market,
)

ETFS = {"ETF001"}


def _row(**kw: Any) -> dict[str, Any]:
    base = {"isin": None, "market_type": None, "ticker": None, "name": "x"}
    return {**base, **kw}


@pytest.mark.parametrize(
    "row, kind",
    [
        (_row(isin="KRD010010001", market_type="0", name="원화현금"), C.CASH),
        (
            _row(isin="KR4A06690007", market_type="4", name="코스닥150선물"),
            C.DERIVATIVE,
        ),
        (_row(isin="KR7069500007", market_type="0", ticker="ETF001"), C.DOMESTIC_ETF),
        (_row(isin="KR7005930003", market_type="0", ticker="005930"), C.DOMESTIC_STOCK),
        (_row(isin="KR7058470006", market_type="1", ticker="058470"), C.DOMESTIC_STOCK),
        (_row(isin="US5324571083", market_type="2", name="Eli Lilly"), C.FOREIGN_STOCK),
        (
            _row(
                isin="US81369Y2090",
                market_type="2",
                name="Health Care Select Sector SPDR Fund",
            ),
            C.UNKNOWN,
        ),
        (_row(isin="US6658591044", market_type="2", name="Northern Trust"), C.UNKNOWN),
        (
            _row(
                isin="US8085247976",
                market_type="2",
                name="Schwab US Dividend Equity ETF",
            ),
            C.FOREIGN_ETF,
        ),
        (
            _row(
                isin="KRC035LP5638",
                market_type="3",
                name="국고채원금분리채권01210-5603(26-2)",
            ),
            C.BOND,
        ),
        (_row(isin="KRC000000000", market_type="3", name="무엇"), C.UNKNOWN),
        (
            _row(isin="KR1000000000", market_type="0", ticker=None, name="국고채"),
            C.UNKNOWN,
        ),
        (_row(isin=None, market_type=None, name="?"), C.UNKNOWN),
    ],
)
def test_row_kind_table(row: dict[str, Any], kind: str) -> None:
    assert C.row_kind(row, ETFS) == kind


def test_row_kind_order_cash_and_derivative_win() -> None:
    # 현금 ISIN 이면 시장 구분 · 종목코드와 무관하게 현금 · 시장 구분 4 는 ETF 목록 종목코드여도 파생
    assert (
        C.row_kind(_row(isin="KRD010010001", market_type="4", ticker="ETF001"), ETFS)
        == C.CASH
    )
    assert (
        C.row_kind(_row(isin="KR7069500007", market_type="4", ticker="ETF001"), ETFS)
        == C.DERIVATIVE
    )
    # 국내 ETF 판정이 국내 주식보다 먼저(KR7 · 6자리여도 ETF 목록이면 ETF)
    assert (
        C.row_kind(_row(isin="KR7000001000", market_type="0", ticker="ETF001"), ETFS)
        == C.DOMESTIC_ETF
    )
    assert C.TOP_ROWS == 10


def test_family_of() -> None:
    assert (
        C.family_of("446720", "Dow Jones U.S. Dividend 100 Price Return Index")
        == "Dow Jones U.S. Dividend 100 계열"
    )
    assert C.family_of(
        "483290",
        "Dow Jones U.S. Dividend 100 10% Premium Covered Call Index(Total Return)",
    ) == C.family_of("446720", None)
    assert C.family_of("453810", "Nifty 50 Index") == "Nifty 50 Index"
    assert C.family_of("ZZZ999", None) is None


# ── 대조 3 ────────────────────────────────────────────────────────────────


def _frozen(
    ticker: str, rank: int, index_name: Optional[str], strategy: bool = False
) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "name": f"ETF {ticker}",
        "rank": rank,
        "held": False,
        "basis_return": {"value": 10.0 - rank},
        "classification": {
            "kind": "index" if index_name else "unclassified",
            "sector": None,
            "index_name": index_name,
            "market": "해외",
            "asset": "주식",
            "strategy": strategy,
            "broad": False,
        },
    }


def _cons_rows(*items: tuple[str, str, str, float]) -> dict[str, Any]:
    """(키, 이름, 시장 구분, 비중) → read_latest_rows 모양."""
    top = []
    for i, (k, n, mt, w) in enumerate(items, start=1):
        isin = "KRD010010001" if n == "원화현금" else f"US{i:010d}"
        top.append(
            {
                "rank": i,
                "ticker": None,
                "name": n,
                "weight_pct": w,
                "key": k,
                "isin": isin,
                "reuters": k,
                "market_type": mt,
                "created_at": "2026-11-14T06:00:00.000000Z",
                "match_key": k,
            }
        )
    return {
        "asof": "2026-11-13",
        "source": "naver",
        "stored_count": len(top),
        "created_at": "2026-11-14T06:00:00.000000Z",
        "top": top,
    }


def test_comparison_three_counts_distinct_confirmed_families_only() -> None:
    frozen = [
        _frozen("453810", 1, "Nifty 50 Index"),
        _frozen("453870", 2, "Nifty 50 Index"),
        _frozen("446720", 3, "Dow Jones U.S. Dividend 100 Price Return Index"),
        _frozen(
            "483290",
            4,
            "Dow Jones U.S. Dividend 100 10% Premium Covered Call",
            strategy=True,
        ),
        _frozen(
            "458760",
            5,
            "DowJones U.S. Dividend 100 7% Premium Covered Call",
            strategy=True,
        ),
        _frozen("AAA111", 6, "S&P Dividend Monarchs Index"),
        _frozen("BBB222", 7, None),  # 계열 미확인
    ]
    latest = {
        # 같은 Nifty 50 계열 두 ETF 에만 든 주식 → 계열 1개 · 반복 아님
        "453810": _cons_rows(
            ("RELI.NS", "Reliance", "2", 9.0), ("CASH", "원화현금", "0", 1.0)
        ),
        "453870": _cons_rows(
            ("RELI.NS", "Reliance", "2", 8.5), ("CASH", "원화현금", "0", 2.0)
        ),
        # Dow Jones 계열 3개 + Monarchs 1개 → 계열 2개(ETF 4개)
        "446720": _cons_rows(
            ("PEP.O", "PepsiCo", "2", 4.0), ("CASH", "원화현금", "0", 0.5)
        ),
        "483290": _cons_rows(("PEP.O", "PepsiCo", "2", 3.9)),
        "458760": _cons_rows(("PEP.O", "PepsiCo", "2", 3.8)),
        "AAA111": _cons_rows(
            ("PEP.O", "PepsiCo", "2", 2.0), ("CASH", "원화현금", "0", 0.4)
        ),
        # 계열 미확인 ETF 는 계열 수에 넣지 않음
        "BBB222": _cons_rows(("RELI.NS", "Reliance", "2", 1.0)),
    }
    out = C.comparison_three(frozen, latest, set(), visible_keys={"PEP.O"})
    assert [x["name"] for x in out] == [
        "PepsiCo"
    ]  # 원화현금(주식 외)은 계열 4개여도 빠짐
    pep = out[0]
    assert pep["families"] == [
        "Dow Jones U.S. Dividend 100 계열",
        "S&P Dividend Monarchs Index",
    ]
    assert pep["family_count"] == 2 and pep["etf_count"] == 4
    assert pep["already_visible"] is True
    assert [e["selection_rank"] for e in pep["entries"]] == [3, 4, 5, 6]
    assert pep["max_weight_pct"] == 4.0


def test_comparison_three_order_and_unknown_kind_excluded() -> None:
    frozen = [
        _frozen("A1", 1, "Idx A"),
        _frozen("A2", 2, "Idx B"),
        _frozen("A3", 3, "Idx C"),
    ]
    latest = {
        "A1": _cons_rows(
            ("X", "Xco", "2", 5.0),
            ("Y", "Yco", "2", 9.0),
            ("F", "Big ETF", "2", 9.0),
            ("T", "Big Trust", "2", 8.0),
        ),
        "A2": _cons_rows(
            ("X", "Xco", "2", 4.0),
            ("Y", "Yco", "2", 1.0),
            ("F", "Big ETF", "2", 9.0),
            ("T", "Big Trust", "2", 8.0),
        ),
        "A3": _cons_rows(("X", "Xco", "2", 3.0)),
    }
    out = C.comparison_three(frozen, latest, set(), visible_keys=set())
    assert [x["name"] for x in out] == [
        "Xco",
        "Yco",
    ]  # 계열 3 > 2 · 해외 ETF · 종류 미확인 제외
    assert all(x["already_visible"] is False for x in out)


# ── 대조 2 = 운영 요약과 같은 계산 ───────────────────────────────────────────


def _cons_db(
    db: Path, etf: str, asof: str, items: list[tuple[str, str, str, str, float]]
) -> None:
    """(종목코드, 이름, 키, 시장 구분, 비중) → etf_constituents."""
    init_constituents_db(db)
    with sqlite3.connect(db) as con:
        con.executemany(
            "INSERT INTO etf_constituents(etf_ticker, asof, source, rank, constituent_ticker,"
            " constituent_name, weight_pct, etf_name, constituent_key, constituent_isin,"
            " constituent_reuters_code, market_type, created_at)"
            " VALUES (?,?,'naver',?,?,?,?,NULL,?,?,NULL,?,'2026-11-14T06:00:00.000000Z')",
            [
                (
                    etf,
                    asof,
                    i + 1,
                    t or None,
                    n,
                    w,
                    k,
                    "KRD010010001" if n == "원화현금" else f"KR7{k}",
                    mt,
                )
                for i, (t, n, k, mt, w) in enumerate(items)
            ],
        )


def test_comparison_two_equals_build_summary_top_groups(
    market: Path,  # noqa: F811 — 가져온 fixture
) -> None:
    _cons_db(
        market,
        "AAA003",
        "2026-11-13",
        [
            ("005930", "삼성전자", "005930", "0", 20.0),
            ("", "원화현금", "KRD010010001", "0", 1.0),
        ],
    )
    _cons_db(
        market,
        "AAA010",
        "2026-11-13",
        [
            ("005930", "삼성전자", "005930", "0", 10.0),
            ("", "원화현금", "KRD010010001", "0", 2.0),
        ],
    )
    s = _run(market)
    frozen = s["top"]
    con = sqlite3.connect(f"file:{market}?mode=ro", uri=True)
    try:
        latest = C.read_latest_rows(con, [r["ticker"] for r in frozen])
        kinds = {
            row["match_key"]: C.row_kind(row, set())
            for d in latest.values()
            for row in d["top"]
        }
        c2 = C.comparison_two(con, frozen, kinds, s["both_side_sectors"])
    finally:
        con.close()
    assert s[
        "both_side_sectors"
    ]  # 이 고정 자료에는 상·하위 공통 업종이 있다(표시 재현 확인)
    strip = lambda gs: [{k: v for k, v in g.items()} for g in gs]  # noqa: E731
    want = strip(s["groups"]["top"])
    got = strip(c2["groups"])
    for g in got:
        for c in g["constituents"]["common"]:
            c.pop("kind")
    assert got == want
    assert c2["overview"] == s["overview"]["top"]


def test_comparison_two_flags_cash_common_in_same_group(
    market: Path,  # noqa: F811 — 가져온 fixture
) -> None:
    # 같은 묶음(KRX 조선 지수 · 같은 지수명)의 두 ETF 가 원화현금을 함께 담으면 기존 방식은 공통 구성종목으로 센다
    s = _run(market, official={**OFFICIAL, "AAA010": OFFICIAL["AAA003"]})
    frozen = s["top"]
    _cons_db(
        market, "AAA003", "2026-11-13", [("", "원화현금", "KRD010010001", "0", 1.0)]
    )
    _cons_db(
        market, "AAA010", "2026-11-13", [("", "원화현금", "KRD010010001", "0", 2.0)]
    )
    con = sqlite3.connect(f"file:{market}?mode=ro", uri=True)
    try:
        latest = C.read_latest_rows(con, ["AAA003", "AAA010"])
        kinds = {
            row["match_key"]: C.row_kind(row, set())
            for d in latest.values()
            for row in d["top"]
        }
        c2 = C.comparison_two(con, frozen, kinds)
    finally:
        con.close()
    assert c2["non_stock_common"] == [
        {"group": "조선", "name": "원화현금", "kind": C.CASH}
    ]


# ── 근거 · 범위 ────────────────────────────────────────────────────────────


def test_sector_evidence_only_dictionary_classified_etfs() -> None:
    latest_all = {
        "AAA001": _cons_rows(("X", "Xco", "2", 5.0)),  # FnGuide AI반도체 → 반도체
        "AAA003": _cons_rows(("X", "Xco", "2", 5.0)),  # KRX 조선 → 조선
        "AAA010": _cons_rows(("X", "Xco", "2", 5.0)),  # 코스닥(사업군 없음) → 근거 아님
    }
    ev = C.sector_evidence(
        latest_all, {"X"}, OFFICIAL, DICTIONARY, {"AAA001": "가", "AAA003": "다"}
    )
    assert [(e["etf"], e["sector"]) for e in ev["X"]] == [
        ("AAA001", "반도체"),
        ("AAA003", "조선"),
    ]
    assert C.sector_evidence(latest_all, {"X"}, OFFICIAL, None, {}) == {}


def test_coverage_states_dates_and_weights() -> None:
    frozen = [
        _frozen(t, i, "Idx") for i, t in enumerate(["N1", "C1", "O1", "M1"], start=1)
    ]
    new = _cons_rows(
        ("A", "Aco", "2", 40.0),
        ("CASH", "원화현금", "0", 2.0),
        ("F", "X ETF", "2", 5.0),
    )
    new["asof"] = "2026-11-14"
    old = _cons_rows(("A", "Aco", "2", 30.0))
    old["asof"] = "2026-07-03"
    latest = {"N1": new, "C1": _cons_rows(("A", "Aco", "2", 1.0)), "O1": old}
    collected = {
        "N1": {"status": "ok", "from_cache": False, "saved_asof": "2026-11-14"},
        "C1": {"status": "ok", "from_cache": True},
        "O1": {
            "status": "unavailable",
            "from_cache": False,
            "message": "http_status_500",
        },
        "M1": {"status": "skipped_timeout", "from_cache": False},
    }
    cov = {
        c["ticker"]: c
        for c in C.coverage(frozen, latest, collected, set(), "2026-11-13")
    }
    assert [cov[t]["state"] for t in ("N1", "C1", "O1", "M1")] == [
        "new",
        "cached",
        "old_failed",
        "timeout",  # 검증자 r1 F2 — 시간 초과는 공급자를 부르지 않음(수집 실패가 아님)
    ]
    assert [cov[t]["has_data"] for t in ("N1", "C1", "O1", "M1")] == [
        True,
        True,
        True,
        False,
    ]
    assert (
        cov["N1"]["after_ranking_end"] is True
        and cov["O1"]["after_ranking_end"] is False
    )
    assert cov["N1"]["kinds"] == {C.FOREIGN_STOCK: 1, C.CASH: 1, C.FOREIGN_ETF: 1}
    assert (cov["N1"]["raw_weight_sum"], cov["N1"]["stock_weight_sum"]) == (47.0, 40.0)
    assert cov["M1"]["raw_weight_sum"] is None and cov["M1"]["top_count"] == 0
    assert cov["O1"]["collect_message"] == "http_status_500"


# ── 사본 수집 ──────────────────────────────────────────────────────────────


def _snapshot(tmp_path: Path, tickers: list[str]) -> tuple[Path, str]:
    doc = {"top": [{"ticker": t} for t in tickers]}
    p = tmp_path / "snap.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p, hashlib.sha256(p.read_bytes()).hexdigest()


def _live(tmp_path: Path) -> Path:
    db = tmp_path / "live.sqlite"
    _cons_db(db, "OLD001", "2026-07-03", [("005930", "삼성전자", "005930", "0", 20.0)])
    return db


class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def _refresh_with(fetch_log: list[str], *, slow_after: Optional[int] = None):
    """실제 refresh_constituents + 가짜 수집기 · slow_after 번째 호출 뒤 시간 예산을 넘긴다."""

    def fetcher(tk: str, asof: str, top_k: int) -> FetchResult:
        fetch_log.append(tk)
        return FetchResult(
            status="ok",
            source="naver_stock_etf_component",
            constituents=[
                FetchedConstituent(
                    rank=1,
                    constituent_ticker="005930",
                    constituent_name="삼성전자",
                    weight_pct=10.0,
                    constituent_isin="KR7005930003",
                    market_type="0",
                )
            ],
            effective_asof="2026-11-14",
        )

    def refresh(**kw: Any):
        clock = _Clock()
        calls = {"n": 0}

        def fetch(tk: str, asof: str, top_k: int) -> FetchResult:
            calls["n"] += 1
            if slow_after is not None and calls["n"] >= slow_after:
                clock.t = 31.0
            return fetcher(tk, asof, top_k)

        return refresh_constituents(
            **kw, fetcher=fetch, sleep_fn=lambda s: None, now_fn=clock
        )

    return refresh


def test_collect_uses_copy_batches_in_order_and_keeps_live(tmp_path: Path) -> None:
    tickers = [f"T{i:03d}" for i in range(1, 31)]
    snap, sha = _snapshot(tmp_path, tickers)
    live = _live(tmp_path)
    before = R.table_fingerprint(live)
    log: list[str] = []
    doc = R.collect(
        tmp_path / "run",
        research_root=tmp_path / "research",
        live_db=live,
        snapshot_path=snap,
        snapshot_sha256=sha,
        refresh=_refresh_with(log),
    )
    assert log == tickers  # 선정 순서
    assert [len(b["tickers"]) for b in doc["batches"]] == [10, 10, 10]
    assert doc["external_calls"] == 30
    assert R.table_fingerprint(live) == before  # 운영(여기서는 가짜 운영) DB 그대로
    con = sqlite3.connect(tmp_path / "run" / R.COPY_NAME)
    try:
        n = con.execute(
            "SELECT COUNT(DISTINCT etf_ticker) FROM etf_constituents WHERE asof = '2026-11-14'"
        ).fetchone()[0]
    finally:
        con.close()
    assert n == 30
    assert doc["items"]["T001"]["saved_asof"] == "2026-11-14"
    with pytest.raises(SystemExit):
        R.collect(
            tmp_path / "run",
            research_root=tmp_path / "research",
            live_db=live,
            snapshot_path=snap,
            snapshot_sha256=sha,
            refresh=_refresh_with([]),
        )


def test_collect_retries_timeouts_once_within_call_limit(tmp_path: Path) -> None:
    tickers = [f"T{i:03d}" for i in range(1, 13)]  # 10 + 2
    snap, sha = _snapshot(tmp_path, tickers)
    log: list[str] = []
    # 첫 묶음: 7번째 호출 뒤 예산 초과 → T008 ~ T010 건너뜀 · 둘째 묶음 2개 · 보충 3개
    doc = R.collect(
        tmp_path / "run",
        research_root=tmp_path / "research",
        live_db=_live(tmp_path),
        snapshot_path=snap,
        snapshot_sha256=sha,
        refresh=_refresh_with(log, slow_after=7),
    )
    assert [b["label"] for b in doc["batches"]] == ["묶음 1", "묶음 2", "보충"]
    assert doc["batches"][0]["skipped"] == 3
    assert doc["batches"][2]["tickers"] == ["T008", "T009", "T010"]
    assert doc["external_calls"] == len(log) <= R.CALL_LIMIT


def test_collect_never_exceeds_call_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(R, "CALL_LIMIT", 12)
    tickers = [f"T{i:03d}" for i in range(1, 31)]
    snap, sha = _snapshot(tmp_path, tickers)
    log: list[str] = []
    doc = R.collect(
        tmp_path / "run",
        research_root=tmp_path / "research",
        live_db=_live(tmp_path),
        snapshot_path=snap,
        snapshot_sha256=sha,
        refresh=_refresh_with(log),
    )
    assert len(log) == 12 and doc["external_calls"] == 12
    assert [len(b["tickers"]) for b in doc["batches"]] == [10, 2]


def test_snapshot_hash_mismatch_refused(tmp_path: Path) -> None:
    snap, _ = _snapshot(tmp_path, ["T001"])
    with pytest.raises(SystemExit):
        R.load_snapshot(snap, "0" * 64)


# ── 대조표 첫 줄 ────────────────────────────────────────────────────────────


def _doc(
    c3: list[dict[str, Any]], have: int, families: int = 5, unconfirmed: int = 0
) -> dict[str, Any]:
    states = ["new"] * have + ["missing"] * (30 - have)
    return {
        "comparison_one": {
            "overview": {
                "sector_etf_count": 1,
                "index_group_count": 28,
                "constituents_etf_count": 3,
            },
            "groups": [
                {
                    "kind": "sector",
                    "name": "바이오",
                    "constituents": {"common": [], "status": "single"},
                }
            ],
        },
        "comparison_one_scope": {"groups": 1, "compared": 0, "common": 0},
        "comparison_three": c3,
        "comparison_three_scope": {
            "etf_with_stock_rows": have,
            "family_count": families,
            "unconfirmed_etfs": unconfirmed,
            "comparable": families >= 2,
        },
        "coverage": [{"state": s, "has_data": s == "new"} for s in states],
        "evidence_scope": {"sector_etfs": 23, "sectors": 5},
    }


_SEEN = {
    "name": "Xco",
    "already_visible": True,
    "family_count": 2,
    "etf_count": 2,
    "max_weight_pct": 1.0,
}
_FRESH = {**_SEEN, "key": "Y", "name": "Yco", "already_visible": False}


@pytest.mark.parametrize(
    "c3, have, families, unconfirmed, want",
    [
        # 검증자 r1 F3 — 비교 못 함 / 함께 든 주식 없음 / 모두 대조 2에도 보임 / 새로 보임을 나눈다
        (
            [],
            1,
            1,
            0,
            "구성종목을 보고 새로 알게 된 것: 비교 못 함 — 주식 행이 있는 확인된 지수 계열이"
            " 2개 이상이어야 합니다(구성 자료 1/30 · 주식 행이 있는 확인된 지수 계열 1개).",
        ),
        (
            [],
            30,
            1,
            3,
            "구성종목을 보고 새로 알게 된 것: 비교 못 함 — 주식 행이 있는 확인된 지수 계열이"
            " 2개 이상이어야 합니다(구성 자료 30/30 · 주식 행이 있는 확인된 지수 계열 1개"
            " · 계열 미확인 ETF 3개는 세지 않음).",
        ),
        (
            [],
            30,
            4,
            0,
            "구성종목을 보고 새로 알게 된 것: 없음 — 서로 다른 지수 계열 2개 이상에 함께 든 주식이"
            " 없습니다(구성 자료 30/30 · 주식 행이 있는 확인된 지수 계열 4개).",
        ),
        (
            [_SEEN],
            30,
            4,
            0,
            "구성종목을 보고 새로 알게 된 것: 없음 — 서로 다른 지수 계열 2개 이상에 함께 든 주식"
            " 1종목은 모두 지금 방식(대조 2)에도 보입니다(구성 자료 30/30 · 주식 행이 있는 확인된"
            " 지수 계열 4개).",
        ),
    ],
)
def test_headline_without_new_information_gives_reason(
    c3: list[dict[str, Any]], have: int, families: int, unconfirmed: int, want: str
) -> None:
    now, new = headline(_doc(c3, have, families, unconfirmed))
    assert new == want
    assert "업종(사업군)으로 묶인 ETF 1개(바이오)" in now
    # 대조 1 — 비교한 묶음이 없으면 '0건'이 아니라 비교 못 함
    assert now.endswith(
        "구성 자료 3/30 · 공통 구성종목 비교 못 함 — 구성 자료가 2개 이상인 묶음 없음"
    )
    assert "0건" not in now


def test_headline_new_stock_and_compared_group_counts() -> None:
    doc = _doc([_SEEN, _FRESH], 30, 4)
    doc["comparison_one_scope"] = {"groups": 3, "compared": 2, "common": 0}
    now, new = headline(doc)
    assert now.endswith(
        "공통 구성종목 0건(구성 자료가 2개 이상인 묶음 2개 비교)"
    )  # 비교를 마친 0건
    assert "주식 1종목 — Yco(2개 계열)" in new and "(구성 자료 30/30)." in new
    # 자료 수 = 자료가 남아 있는 모든 상태(예전 자료 포함) · 자료 없는 상태는 빼고 센다
    doc["coverage"][:3] = [
        {"state": "old_timeout", "has_data": True},
        {"state": "cached", "has_data": True},
        {"state": "inconsistent", "has_data": False},
    ]
    assert "(구성 자료 29/30)." in headline(doc)[1]


def test_headline_lists_only_new_repeated_stocks() -> None:
    c3 = [
        {
            "key": "S",
            "name": "Seen",
            "already_visible": True,
            "family_count": 3,
            "etf_count": 3,
            "max_weight_pct": 9.0,
        },
        {
            "key": "L",
            "name": "Eli Lilly",
            "already_visible": False,
            "family_count": 4,
            "etf_count": 5,
            "max_weight_pct": 22.5,
        },
        {
            "key": "P",
            "name": "Pep",
            "already_visible": False,
            "family_count": 2,
            "etf_count": 2,
            "max_weight_pct": 3.0,
        },
    ]
    doc = _doc(c3, 28)
    _, new = headline(doc)
    assert (
        "주식 2종목 — Eli Lilly(4개 계열), Pep(2개 계열)" in new and "Seen" not in new
    )
    assert (
        "최대 비중 22.50%" in new
        and "구성 자료가 있는 사업군 ETF 23개에서 편입 이력이 확인된 주식은 없고" in new
        and "업종 해석은 모두 가설입니다" in new
        and "(구성 자료 28/30)" in new
    )
    # 이미 보인 주식(S)의 근거는 세지 않는다 · 한 주식이 여러 사업군이면 각각 센다
    doc["evidence"] = {
        "S": [{"sector": "조선"}],
        "L": [{"sector": "바이오"}, {"sector": "바이오"}, {"sector": "반도체"}],
        "P": [{"sector": "바이오"}],
    }
    _, new2 = headline(doc)
    assert (
        "그중 2종목은 사업군 ETF('바이오' 2종목 · '반도체' 1종목)에 편입된 이력을 확인했을 뿐이고,"
        " 주식 자체의 업종 자료는 없어 이 종목들을 포함한 업종 해석은 모두 가설입니다"
        in new2
    )
    doc["evidence"] = {"P": [{"sector": "바이오"}]}
    _, new3 = headline(doc)
    assert "그중 1종목은 '바이오' 사업군 ETF에 편입된 이력을 확인했을 뿐이고," in new3


def _full_doc() -> dict[str, Any]:
    doc = _doc(
        [
            {
                "key": "LLY",
                "name": "<b>Eli</b>",
                "already_visible": False,
                "family_count": 2,
                "etf_count": 2,
                "max_weight_pct": 20.0,
                "entries": [
                    {
                        "etf": "A1",
                        "etf_name": "ETF A1",
                        "family": "Idx A",
                        "strategy": False,
                        "weight_pct": 20.0,
                        "rank": 1,
                        "asof": "2026-11-14",
                    },
                    {
                        "etf": "A2",
                        "etf_name": "ETF A2",
                        "family": "Idx B",
                        "strategy": True,
                        "weight_pct": 5.0,
                        "rank": 3,
                        "asof": "2026-11-14",
                    },
                ],
            }
        ],
        30,
    )
    top = [
        {
            "rank": i,
            "ticker": f"A{i}",
            "name": f"ETF A{i}",
            "return_pct": 10.0,
            "classification": {"index_name": "Idx"},
        }
        for i in range(1, 31)
    ]
    cov = [
        {
            "state": "new",
            "has_data": True,
            "collect_message": None,
            "asof": "2026-11-14",
            "after_ranking_end": True,
            "fetched_at": "2026-11-14T06:00:00.000000Z",
            "top_count": 10,
            "stored_count": 30,
            "kinds": {C.FOREIGN_STOCK: 9, C.CASH: 1},
            "raw_weight_sum": 60.0,
            "stock_weight_sum": 58.0,
        }
    ] * 30
    doc.update(
        {
            "snapshot": {
                "sha256": "ab" * 32,
                "period": {"start": "2026-10-14", "end": "2026-11-13"},
                "end_date": "2026-11-13",
                "filters": {
                    "exclude_inverse": True,
                    "exclude_leveraged": True,
                    "exclude_synthetic": True,
                    "exclude_futures": True,
                },
                "counts": {"population": 963},
                "price_state": {
                    "after_close_count": 963,
                    "after_close_fetched_min": "2026-11-13T23:59:52+09:00",
                    "after_close_fetched_max": "2026-11-14T00:02:39+09:00",
                },
                "regime": {"label": "하락장", "asof": "2026-11-13"},
                "top": top,
            },
            "comparison_two": {
                "groups": [],
                "overview": {"constituents_etf_count": 30},
                "non_stock_common": [],
            },
            "comparison_two_scope": {"groups": 1, "compared": 1, "common": 10},
            "evidence": {
                "LLY": [
                    {
                        "etf": "ZZ9999",
                        "etf_name": "숨길이름",
                        "sector": "바이오",
                        "asof": "2026-06-22",
                    }
                ]
            },
            "coverage": cov,
            "kind_labels": C.KIND_LABEL,
            "families": C.SAMPLE_FAMILIES,
            "q5": {
                "one_month": {
                    "status": "ok",
                    "groups_compared": 2,
                    "common_checked": 12,
                    "non_stock_common": [
                        {"group": "Nifty 50 Index", "name": "원화현금", "kind": C.CASH}
                    ],
                },
                "three_month": {
                    "status": "ok",
                    "groups_compared": 1,
                    "common_checked": 10,
                    "non_stock_common": [],
                },
            },
            "collect": {
                "batches": [
                    {
                        "label": "묶음 1",
                        "tickers": ["A1"],
                        "fetched": 1,
                        "failed": 0,
                        "cached": 0,
                        "skipped": 0,
                    }
                ],
                "request_asof": "2026-11-13",
                "external_calls": 30,
                "call_limit": 30,
                "started_at": "2026-11-14T06:00:00.000000Z",
                "finished_at": "2026-11-14T06:01:00.000000Z",
            },
            "official": {"name": "krx_etf_basic_20260927.csv"},
            "copy_top_matches_snapshot": True,
        }
    )
    doc["comparison_one"]["overview"]["index_group_count"] = 28
    return doc


def test_render_html_escapes_and_shows_required_labels() -> None:
    html = render_html(_full_doc())
    assert "<b>Eli</b>" not in html and "&lt;b&gt;Eli&lt;/b&gt;" in html
    # 표본 밖 근거 ETF 의 이름 · 코드는 쓰지 않는다(검토 §2-1)
    assert "숨길이름" not in html and "ZZ9999" not in html
    doc = _full_doc()
    doc["evidence"]["LLY"] += [
        {"etf": "A2", "etf_name": "ETF A2", "sector": "바이오", "asof": "2026-11-13"},
        {
            "etf": "ZZ8888",
            "etf_name": "숨길이름2",
            "sector": "바이오",
            "asof": "2026-06-22",
        },
        {
            "etf": "ZZ7777",
            "etf_name": "숨길이름3",
            "sector": "반도체",
            "asof": "2026-08-20",
        },
    ]
    html2 = render_html(doc)
    assert (
        "바이오 · 반도체 사업군 ETF 4개에 편입 이력"
        "<br><span class=muted>표본 안: ETF A2(바이오 · 구성 11/13)</span>"
        "<br><span class=muted>표본 밖: 바이오 ETF 2개(구성 6/22)</span>"
        "<br><span class=muted>표본 밖: 반도체 ETF 1개(구성 8/20)</span>"
    ) in html2
    assert not any(x in html2 for x in ("숨길이름", "ZZ9999", "ZZ8888", "ZZ7777"))
    for text in (
        "963개 모두 마감 뒤 저장(11/13 23:59 KST ~ 11/14 00:02 KST)",
        "11/14 <b>현재 편입 참고</b>",
        "바이오 사업군 ETF 1개에 편입 이력"
        "<br><span class=muted>표본 밖: 바이오 ETF 1개(구성 6/22)</span>",
        "업종 해석 = 가설",
        "Nifty 50 Index 묶음 '원화현금'(원화현금)",
        "외부 호출 30/30회",
        "보관 목록과 같음",
        "새로 보임",
    ):
        assert text in html, text


def test_josa_by_final_consonant() -> None:
    from app.sector_constituents_report import josa

    assert josa("암젠", "은", "는") == "은" and josa("일라이 릴리", "은", "는") == "는"
    assert (
        josa("Eli Lilly", "은", "는") == "은(는)" and josa("", "은", "는") == "은(는)"
    )


# ── 독립 검토 반영(2026-11-14) — 최신 기준일 · 1 ~ 10행 · 경계 · 상태 · 보충 기록 · report 전체 ─────────


def _put_cons(db: Path, etf: str, asof: str, ranks: int, created: str) -> None:
    init_constituents_db(db)
    with sqlite3.connect(db) as con:
        con.executemany(
            "INSERT INTO etf_constituents(etf_ticker, asof, source, rank, constituent_ticker,"
            " constituent_name, weight_pct, etf_name, constituent_key, constituent_isin,"
            " constituent_reuters_code, market_type, created_at)"
            " VALUES (?,?,'naver',?,NULL,?,1.0,NULL,?,?,NULL,'2',?)",
            [
                (etf, asof, i, f"S{i}", f"US{i:010d}", f"US{i:010d}", created)
                for i in range(1, ranks + 1)
            ],
        )


def test_read_latest_rows_picks_latest_date_and_ranks_1_to_10(tmp_path: Path) -> None:
    db = tmp_path / "c.sqlite"
    _put_cons(db, "E1", "2026-07-03", 10, "2026-07-03T01:00:00.000000Z")
    _put_cons(db, "E1", "2026-11-13", 12, "2026-11-14T06:00:00.000000Z")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        got = C.read_latest_rows(con, ["E1", "NONE"])
    finally:
        con.close()
    assert set(got) == {"E1"}
    e1 = got["E1"]
    assert e1["asof"] == "2026-11-13" and e1["stored_count"] == 12
    assert [r["rank"] for r in e1["top"]] == list(range(1, 11))
    assert e1["created_at"] == "2026-11-14T06:00:00.000000Z"


def test_row_kind_isin_shape_for_foreign_rows() -> None:
    # 선물 약호(5자리)는 주식인지 가를 수 없음 · 끝자리가 영문인 12자리(원천 실제 주식 행)는 해외 주식
    fut = _row(isin="IXCZ6", market_type="2", name="XAV Health Care 2026 12")
    adr = _row(isin="GB000989529A", market_type="2", name="ASTRAZENECA PLC-SP")
    assert C.row_kind(fut, ETFS) == C.UNKNOWN
    assert C.row_kind(adr, ETFS) == C.FOREIGN_STOCK
    bad_kr = _row(isin="KR7005930", market_type="0", ticker="005930")
    assert C.row_kind(bad_kr, ETFS) == C.UNKNOWN


def test_coverage_boundary_missing_and_saved_asof() -> None:
    frozen = [_frozen(t, i, "Idx") for i, t in enumerate(["ON", "AFT", "NO"], start=1)]
    on = _cons_rows(("A", "Aco", "2", 1.0))
    on["asof"] = "2026-11-13"
    aft = _cons_rows(("A", "Aco", "2", 1.0))
    aft["asof"] = "2026-11-14"
    latest = {"ON": on, "AFT": aft}
    collected = {
        "ON": {"status": "ok", "from_cache": False, "saved_asof": "2026-11-12"},
        "AFT": {"status": "ok", "from_cache": False, "saved_asof": "2026-11-14"},
    }
    cov = {
        c["ticker"]: c
        for c in C.coverage(frozen, latest, collected, set(), "2026-11-13")
    }
    assert (cov["ON"]["on_ranking_end"], cov["ON"]["after_ranking_end"]) == (
        True,
        False,
    )
    assert (cov["AFT"]["on_ranking_end"], cov["AFT"]["after_ranking_end"]) == (
        False,
        True,
    )
    assert cov["NO"]["state"] == "missing"  # 부르지 않음
    assert cov["ON"]["state"] == "new" and cov["ON"]["saved_asof"] == "2026-11-12"


def test_collect_saved_asof_ignores_older_logs_and_marker_blocks_rerun(
    tmp_path: Path,
) -> None:
    from app.etf_constituents_store import log_constituent_refresh

    snap, sha = _snapshot(tmp_path, ["T001", "T002"])
    live = _live(tmp_path)
    log_constituent_refresh(
        etf_ticker="T001",
        asof="2026-07-03",
        status="ok",
        source="naver_stock_etf_component",
        message=None,
        db_path=live,
    )
    run = tmp_path / "run"
    doc = R.collect(
        run,
        research_root=tmp_path / "research",
        live_db=live,
        snapshot_path=snap,
        snapshot_sha256=sha,
        refresh=_refresh_with([]),
    )
    assert doc["items"]["T001"]["saved_asof"] == "2026-11-14"  # 예전 7/3 기록이 아님
    # 중간에 멈춘 실행(collect.json 없음 · 시작 표시만 있음)도 다시 돌지 않는다
    (run / "collect.json").unlink()
    with pytest.raises(SystemExit):
        R.collect(
            run,
            research_root=tmp_path / "research",
            live_db=live,
            snapshot_path=snap,
            snapshot_sha256=sha,
            refresh=_refresh_with([]),
        )


def test_reason_ko_and_coverage_display() -> None:
    from app.sector_constituents_report import reason_ko

    assert (
        reason_ko("constituent refresh time budget exceeded")
        == "시간 예산을 넘겨 건너뜀"
    )
    assert reason_ko("http_status_500") == "원천 응답 오류"
    assert reason_ko("무엇") == "기타 사유" and reason_ko(None) == ""
    doc = _full_doc()
    doc["snapshot"]["top"][0] = {
        "rank": 1,
        "ticker": "483290",
        "name": "KODEX 커버드콜",
        "return_pct": 8.0,
        "classification": {
            "index_name": "Dow Jones U.S. Dividend 100 10% Premium Covered Call",
            "strategy": True,
        },
    }
    doc["coverage"] = list(doc["coverage"])
    doc["coverage"][0] = {
        **doc["coverage"][0],
        "state": "failed",
        "collect_message": "no_data",
        "asof": "2026-11-13",
        "after_ranking_end": False,
        "on_ranking_end": True,
    }
    doc["comparison_three"][0]["entries"] = [
        {
            "etf": f"D{i}",
            "etf_name": f"D{i}",
            "family": "Dow Jones U.S. Dividend 100 계열",
            "strategy": i > 0,
            "weight_pct": 5.0 - i,
            "rank": 2,
            "asof": "2026-11-13",
        }
        for i in range(4)
    ] + [
        {
            "etf": "B1",
            "etf_name": "B1",
            "family": "Idx B",
            "strategy": False,
            "weight_pct": 1.0,
            "rank": 9,
            "asof": "2026-11-13",
        }
    ]
    doc["coverage"][1] = {
        **doc["coverage"][1],
        "state": "old_failed",
        "asof": "2026-07-03",
        "after_ranking_end": False,
        "on_ranking_end": False,
    }
    html = render_html(doc)
    assert "<td class=nw>7/3</td>" in html and "7/3 기준 구성" not in html
    for text in (
        "수집 실패 · 자료 없음",
        "원천에 구성 자료 없음",
        "<td class=nw>11/13 기준 구성</td>",
        "10행 / 30행",
        "KODEX 커버드콜 <b>전략형</b>",
        "Dow Jones U.S. Dividend 100 계열 (공식 지수명 "
        "Dow Jones U.S. Dividend 100 10% Premium Covered Call)",
        "D0 외 3 · 전략형 3/4",
    ):
        assert text in html, text


def test_report_end_to_end_on_temporary_market(
    market: Path, tmp_path: Path  # noqa: F811 — 가져온 fixture
) -> None:
    from tests.test_poc6_28_etf_compare import END

    init_constituents_db(market)
    snap_doc = _run(market)
    p = tmp_path / "snap.json"
    p.write_text(json.dumps(snap_doc, ensure_ascii=False), encoding="utf-8")
    sha = hashlib.sha256(p.read_bytes()).hexdigest()

    def item(rank: int, name: str, isin: str, mt: str) -> FetchedConstituent:
        return FetchedConstituent(
            rank=rank,
            constituent_ticker=None,
            constituent_name=name,
            weight_pct=5.0,
            constituent_isin=isin,
            market_type=mt,
        )

    x = item(1, "Xco", "US0000000001", "2")
    y = item(1, "Yco", "US0000000002", "2")
    z = item(2, "Zco", "US0000000003", "2")
    cash = item(3, "원화현금", "KRD010010001", "0")
    plan = {
        "AAA001": ([x, z, cash], END),
        "AAA002": ([x, z, cash], END),
        "AAA003": ([y], "2026-11-12"),
        "AAA010": ([y], END),
    }

    def fetch(tk: str, asof: str, top_k: int) -> FetchResult:
        if tk not in plan:
            return FetchResult(
                status="unavailable",
                source="naver_stock_etf_component",
                constituents=[],
                message="no_data",
            )
        cons, ref = plan[tk]
        return FetchResult(
            status="ok",
            source="naver_stock_etf_component",
            constituents=cons,
            effective_asof=ref,
        )

    def refresh(**kw: Any):
        return refresh_constituents(**kw, fetcher=fetch, sleep_fn=lambda s: None)

    run = tmp_path / "run"
    R.collect(
        run,
        research_root=tmp_path / "research",
        live_db=market,
        snapshot_path=p,
        snapshot_sha256=sha,
        refresh=refresh,
    )
    out = tmp_path / "t.html"
    srcs = (OFFICIAL, {}, DICTIONARY, {})
    doc = R.report(
        run, html_out=out, snapshot_path=p, snapshot_sha256=sha, sources=srcs
    )

    assert doc["copy_top_matches_snapshot"] is True
    # 근거를 찾아본 범위 = 구성 자료가 있는 사업군 ETF(반도체 AAA001 · AAA002 · 조선 AAA003)
    assert doc["evidence_scope"] == {"sector_etfs": 3, "sectors": 2}
    assert doc["comparison_two"]["non_stock_common"] == [
        {"group": "반도체", "name": "원화현금", "kind": C.CASH}
    ]
    c3 = {x["name"]: x for x in doc["comparison_three"]}
    assert set(c3) == {"Xco", "Yco", "Zco"}  # 원화현금은 계열 2개여도 빠짐
    assert (
        c3["Xco"]["already_visible"] is True and c3["Yco"]["already_visible"] is False
    )
    cov = {c["ticker"]: c for c in doc["coverage"]}
    assert (
        cov["AAA003"]["after_ranking_end"] is True
        and cov["AAA001"]["on_ranking_end"] is True
    )
    assert {cov[t]["state"] for t in cov if t not in plan} == {"failed"}
    assert any(
        f["name"] == "원화현금" for f in doc["q5"]["one_month"]["non_stock_common"]
    )
    # 비교한 묶음 = 운영 요약 묶음 중 공통 구성종목 상태가 ok · no_overlap 인 것(검증자 r1 F4)
    for basis in ("one_month", "three_month"):
        groups = [
            g
            for side in ("top", "bottom")
            for g in _run(run / R.COPY_NAME, basis)["groups"][side]
        ]
        q = doc["q5"][basis]
        assert q["status"] == "ok" and q["groups_total"] == len(groups)
        assert q["groups_compared"] == sum(
            g["constituents"]["status"] in ("ok", "no_overlap") for g in groups
        )
    assert (
        doc["q5"]["one_month"]["groups_compared"]
        < doc["q5"]["one_month"]["groups_total"]
    )
    case = doc["lead_case"]
    assert [x["name"] for x in case["stocks"]] == ["Xco", "Zco"]
    ranks = [e["selection_rank"] for e in case["etfs"]]
    assert {e["etf"] for e in case["etfs"]} == {"AAA001", "AAA002"}
    assert ranks == sorted(ranks)
    assert case["sum_min"] == case["sum_max"] == 10.0
    html = out.read_text(encoding="utf-8")
    assert "비중 1·2위 주식은 모두 Xco과(와) Zco입니다" in html
    assert (
        "11/12 <b>현재 편입 참고</b>" in html  # 끝날(11/10)보다 뒤
        and "11/10 기준 구성" in html
        and "원천에 구성 자료 없음" in html
        and "순위 끝날 구성" not in html
    )
    assert json.loads((run / "report.json").read_text(encoding="utf-8"))[
        "comparison_three"
    ]
    with pytest.raises(SystemExit):
        R.report(
            run,
            html_out=out,
            snapshot_path=p,
            snapshot_sha256=sha,
            sources=(OFFICIAL, {"name": "other.csv"}, DICTIONARY, {}),
        )


# ── 설계자 검토 반영(2026-11-14) — 첫 줄 사례(비중 1 · 2위 주식이 같은 ETF 묶음) ──────────────


def _case_inputs() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    frozen = [
        _frozen("O1", 1, "Obesity A"),
        _frozen("O2", 2, "Obesity B"),
        _frozen("O3", 3, "Obesity C"),
        _frozen("K1", 4, "Kor A"),
        _frozen("K2", 5, "Kor B"),
        _frozen("N1", 6, "Nifty 50 Index"),
        _frozen("N2", 7, "Nifty 50 Index"),
        _frozen("N3", 8, "Nifty 50 Index"),
        _frozen("BB", 9, "Blockbuster"),
        _frozen("U1", 10, None),  # 계열 미확인
        _frozen("NW", 11, "Weightless"),
        _frozen("M1", 12, "Misc"),
    ]
    latest = {
        # 1위 행이 현금이어도 주식 행의 앞 두 행을 본다 · 노보가 더 무거움 → 노보가 앞
        "O1": _cons_rows(
            ("CASH", "원화현금", "0", 3.0),
            ("LLY", "일라이 릴리", "2", 20.0),
            ("NVO", "노보 노디스크 ADR", "2", 30.0),
        ),
        "O2": _cons_rows(
            ("NVO", "노보 노디스크 ADR", "2", 26.0), ("LLY", "일라이 릴리", "2", 24.0)
        ),
        "O3": _cons_rows(
            ("NVO", "노보 노디스크 ADR", "2", 27.0), ("LLY", "일라이 릴리", "2", 22.0)
        ),
        # 합산은 더 크지만 ETF 가 2개
        "K1": _cons_rows(
            ("C", "셀트리온", "2", 40.0), ("S", "삼성바이오로직스", "2", 30.0)
        ),
        "K2": _cons_rows(
            ("C", "셀트리온", "2", 35.0), ("S", "삼성바이오로직스", "2", 30.0)
        ),
        # ETF 3개지만 같은 계열 → 사례 아님
        "N1": _cons_rows(("H", "HDFC", "2", 10.0), ("I", "ICICI", "2", 9.0)),
        "N2": _cons_rows(("H", "HDFC", "2", 10.0), ("I", "ICICI", "2", 9.0)),
        "N3": _cons_rows(("H", "HDFC", "2", 10.0), ("I", "ICICI", "2", 9.0)),
        # 두 주식을 1 ~ 10행 안에 함께 담았지만 1 · 2위가 아님 → 함께 담은 ETF
        "BB": _cons_rows(
            ("M", "머크", "2", 11.0),
            ("LLY", "일라이 릴리", "2", 10.0),
            ("NVO", "노보 노디스크 ADR", "2", 8.0),
            ("LLY", "일라이 릴리", "2", 1.0),  # 같은 주식 두 줄 → 앞 행 비중
        ),
        # 계열 미확인 ETF 는 계열 수에 넣지 않는다(K 묶음과 같은 쌍이어도 계열 수는 그대로)
        "U1": _cons_rows(
            ("C", "셀트리온", "2", 1.0), ("S", "삼성바이오로직스", "2", 1.0)
        ),
        # 비중이 비면 합산을 말할 수 없어 묶음에 넣지 않는다
        "NW": _cons_rows(
            ("NVO", "노보 노디스크 ADR", "2", None), ("LLY", "일라이 릴리", "2", 1.0)
        ),
        # 두 주식 중 하나만 담음 → 함께 담은 ETF 아님
        "M1": _cons_rows(("X", "엑스", "2", 5.0), ("LLY", "일라이 릴리", "2", 4.0)),
    }
    return frozen, latest


def test_lead_case_picks_most_etfs_across_families() -> None:
    frozen, latest = _case_inputs()
    case = C.lead_case(frozen, latest, set())
    assert case is not None
    assert [e["etf"] for e in case["etfs"]] == ["O1", "O2", "O3"]
    assert [x["name"] for x in case["stocks"]] == ["노보 노디스크 ADR", "일라이 릴리"]
    assert case["family_count"] == 3
    assert (case["sum_min"], case["sum_max"]) == (49.0, 50.0)
    assert [e["sum_pct"] for e in case["etfs"]] == [50.0, 50.0, 49.0]
    assert case["asofs"] == ["2026-11-13"]
    assert case["also_held"] == [
        {"etf": "BB", "etf_name": "ETF BB", "selection_rank": 9, "sum_pct": 18.0},
        {"etf": "NW", "etf_name": "ETF NW", "selection_rank": 11, "sum_pct": None},
    ]
    # 같은 계열(Nifty 50)만인 묶음은 빠짐 · 계열 미확인 ETF 는 ETF 수에만 든다
    assert case["other_groups"] == [
        {
            "stocks": ["셀트리온", "삼성바이오로직스"],
            "etf_count": 3,
            "sum_min": 2.0,
            "sum_max": 70.0,
        }
    ]


def test_lead_case_tie_breaks_and_none() -> None:
    frozen, latest = _case_inputs()
    # ETF 수가 많은 묶음이 먼저(합산이 더 큰 K 묶음 2개보다 O 묶음 3개)
    no_u = {k: v for k, v in latest.items() if k != "U1"}
    assert [x["name"] for x in C.lead_case(frozen, no_u, set())["stocks"]] == [
        "노보 노디스크 ADR",
        "일라이 릴리",
    ]
    # ETF 수가 같으면 합산의 가장 작은 값이 큰 묶음
    del latest["O3"]
    del latest["U1"]
    case = C.lead_case(frozen, latest, set())
    assert [x["name"] for x in case["stocks"]] == ["셀트리온", "삼성바이오로직스"]
    assert case["other_groups"][0]["stocks"] == ["노보 노디스크 ADR", "일라이 릴리"]
    # 둘 다 같으면 주식 키 순
    latest2 = {  # 키가 뒤인 묶음(C · D)을 먼저 만나도 키 순으로 고른다
        "O1": _cons_rows(("D", "디", "2", 5.0), ("C", "씨", "2", 5.0)),
        "O2": _cons_rows(("D", "디", "2", 5.0), ("C", "씨", "2", 5.0)),
        "K1": _cons_rows(("B", "비", "2", 5.0), ("A", "에이", "2", 5.0)),
        "K2": _cons_rows(("B", "비", "2", 5.0), ("A", "에이", "2", 5.0)),
    }
    case2 = C.lead_case(frozen, latest2, set())
    assert case2["pair"] == ["A", "B"] and case2["stocks"][0]["key"] == "A"
    # 같은 계열뿐 · 같은 주식이 두 행 · 주식 행이 하나뿐 → 사례 없음
    only_same = {k: latest[k] for k in ("N1", "N2", "N3")}
    assert C.lead_case(frozen, only_same, set()) is None
    # 둘째 계열이 '계열 미확인' 뿐이면 계열 1개 → 사례 없음
    with_unknown = {"N1": latest["N1"], "U1": latest["N1"]}
    assert C.lead_case(frozen, with_unknown, set()) is None
    dup = {
        "O1": _cons_rows(("A", "에이", "2", 5.0), ("A", "에이", "2", 4.0)),
        "O2": _cons_rows(("A", "에이", "2", 5.0), ("A", "에이", "2", 4.0)),
        "K1": _cons_rows(("A", "에이", "2", 5.0), ("CASH", "원화현금", "0", 4.0)),
        "K2": _cons_rows(("A", "에이", "2", 5.0), ("CASH", "원화현금", "0", 4.0)),
    }
    assert C.lead_case(frozen, dup, set()) is None
    assert C.lead_case(frozen, {}, set()) is None


def test_lead_case_ignores_non_stock_rows_for_top_two() -> None:
    frozen = [_frozen("E1", 1, "Idx A"), _frozen("E2", 2, "Idx B")]
    latest = {
        "E1": _cons_rows(
            ("A", "에이", "2", 9.0),
            ("069500", "다른 ETF", "0", 8.0),
            ("B", "비", "2", 7.0),
        ),
        "E2": _cons_rows(("A", "에이", "2", 9.0), ("B", "비", "2", 7.0)),
    }
    latest["E1"]["top"][1].update(ticker="069500", isin="KR7069500007")
    # ETF 목록에 있으면 국내 ETF(주식 아님) → 다음 주식 행(B)이 2위 → 두 ETF 가 한 묶음
    case = C.lead_case(frozen, latest, {"069500"})
    assert case["pair"] == ["A", "B"] and case["sum_min"] == case["sum_max"] == 16.0
    # 목록에 없으면 국내 주식 → E1 의 1 · 2위 = A · 069500 → 묶음 없음
    assert C.lead_case(frozen, latest, set()) is None


def test_lead_case_text_and_render_first_line() -> None:
    from app.sector_constituents_report import lead_case_text

    frozen, latest = _case_inputs()
    case = C.lead_case(frozen, latest, set())
    text, notes = lead_case_text(case)
    assert text == (
        "11/13 기준 ETF O1 · ETF O2 · ETF O3 3개 ETF의 비중 1·2위 주식은 모두"
        " 노보 노디스크 ADR과(와) 일라이 릴리입니다. 두 종목의 합산 비중은 ETF별"
        " 49.00%~50.00%이고, 서로 다른 지수 계열 3개에 걸쳐 있습니다."
    )
    assert notes == [
        "두 종목을 원본 1~10행 안에 함께 담은 ETF는 이 3개 말고 2개 더 있습니다:"
        " ETF BB(합산 18.00%) · ETF NW(합산 —).",
        "비중 1·2위 주식이 같은 다른 묶음: 셀트리온과 삼성바이오로직스"
        "(ETF 3개 · 합산 2.00%~70.00%).",
    ]
    assert lead_case_text(None) == ("", [])
    two_dates = {
        **case,
        "asofs": ["2026-11-12", "2026-11-13"],
        "stocks": [{"key": "L", "name": "일라이 릴리"}, {"key": "N", "name": "<노보>"}],
    }
    t2, _ = lead_case_text(two_dates)
    assert (
        t2.startswith("구성 기준일 11/12 ~ 11/13 ETF O1")
        and "일라이 릴리와 <노보>" in t2
    )
    doc = _full_doc()
    doc["lead_case"] = two_dates
    html = render_html(doc)
    lead = html.split('<div class="card lead">', 1)[1]
    # 첫 줄 = 사례 → 그 아래 지금 요약 · 새로 알게 된 것(검토 §1)
    assert lead.startswith("<p class=case><b>구성 기준일 11/12 ~ 11/13")
    assert "&lt;노보&gt;" in lead and "<노보>" not in html
    assert lead.index("지금 요약:") > lead.index("비중 1·2위 주식")
    doc["lead_case"] = None
    assert (
        render_html(doc)
        .split('<div class="card lead">', 1)[1]
        .startswith("<p>지금 요약:")
    )


# ── 검증자 r1 정정(2026-11-15) — 표본 단위 호출 상한 · 부르지 않은 상태 · 비교 못 함 ────────────


def _thirty(tmp_path: Path) -> tuple[Path, str, list[str]]:
    tickers = [f"T{i:03d}" for i in range(1, 31)]
    snap, sha = _snapshot(tmp_path, tickers)
    return snap, sha, tickers


def _collect(run: Path, root: Path, snap: Path, sha: str, live: Path, refresh: Any):
    return R.collect(
        run,
        research_root=root,
        live_db=live,
        snapshot_path=snap,
        snapshot_sha256=sha,
        refresh=refresh,
    )


def test_collect_cap_is_per_sample_across_run_dirs(tmp_path: Path) -> None:
    # F1 — 같은 표본을 다른 실행 폴더(연구 폴더 안 · 밖)에 다시 수집하면 거절 · 가짜 수집기 호출 합계 30
    snap, sha, _ = _thirty(tmp_path)
    live, root, log = _live(tmp_path), tmp_path / "research", []
    first = _collect(root / "run_a", root, snap, sha, live, _refresh_with(log))
    assert first["external_calls"] == 30
    claim = root / R.CLAIMS_NAME / f"{sha}.json"
    assert first["sample_claim"] == str(claim)
    assert json.loads(claim.read_text(encoding="utf-8"))["run_dir"] == str(
        (root / "run_a").resolve()
    )
    for other in (root / "run_b", tmp_path / "elsewhere" / "run_c"):
        with pytest.raises(SystemExit, match="이 표본은 이미 수집했습니다"):
            _collect(other, root, snap, sha, live, _refresh_with(log))
        assert not (other / R.COPY_NAME).exists()
    assert len(log) == 30


def test_collect_claim_alone_blocks_when_records_are_elsewhere(tmp_path: Path) -> None:
    # 첫 실행 폴더가 연구 폴더 밖이라 기록 확인에 안 잡혀도 표본 수집 표시가 막는다
    snap, sha, _ = _thirty(tmp_path)
    live, root, log = _live(tmp_path), tmp_path / "research", []
    _collect(tmp_path / "outside" / "run_a", root, snap, sha, live, _refresh_with(log))
    assert R.prior_collects(root, sha, [f"T{i:03d}" for i in range(1, 31)]) == []
    with pytest.raises(SystemExit, match="표본 수집 표시"):
        _collect(root / "run_b", root, snap, sha, live, _refresh_with(log))
    assert len(log) == 30 and not (root / "run_b" / R.COPY_NAME).exists()


@pytest.mark.parametrize(
    "rel, payload, refused",
    [
        ("run_old/collect.json", {"snapshot_sha256": "SAME"}, True),
        ("a/b/run_old/collect.json", {"snapshot_sha256": "SAME"}, True),  # 깊은 폴더
        # 표본 수집 표시 전 시작 표시(해시 칸 없음 · ETF 목록이 같음)
        ("run_old/collect_started.json", {"started_at": "x", "tickers": "SAME"}, True),
        ("run_old/collect.json", "{broken", True),  # 읽을 수 없는 기록 = 수집한 것으로
        ("run_old/collect.json", [1], True),
        ("run_old/collect.json", {"snapshot_sha256": "0" * 64}, False),  # 다른 표본
        ("run_old/collect_started.json", {"tickers": ["X"]}, False),
    ],
)
def test_collect_refuses_earlier_records_of_same_sample(
    tmp_path: Path, rel: str, payload: Any, refused: bool
) -> None:
    snap, sha, tickers = _thirty(tmp_path)
    root, log = tmp_path / "research", []
    p = root / rel
    p.parent.mkdir(parents=True)
    if isinstance(payload, dict):
        payload = {
            k: (sha if v == "SAME" and k == "snapshot_sha256" else v)
            for k, v in payload.items()
        }
        if payload.get("tickers") == "SAME":
            payload["tickers"] = tickers
    p.write_text(
        payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8"
    )
    run = root / "run_new"
    if refused:
        with pytest.raises(SystemExit, match="이 표본은 이미 수집했습니다"):
            _collect(run, root, snap, sha, _live(tmp_path), _refresh_with(log))
        assert log == [] and not (root / R.CLAIMS_NAME).exists()
    else:
        _collect(run, root, snap, sha, _live(tmp_path), _refresh_with(log))
        assert len(log) == 30


def test_collect_race_between_record_check_and_claim_runs_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 두 실행이 모두 기록 확인을 통과한 뒤에도 표본 수집 표시(O_EXCL)는 하나만 만든다
    snap, sha, _ = _thirty(tmp_path)
    live, root, log = _live(tmp_path), tmp_path / "research", []
    real_scan, entered, done = R.prior_collects, [], []

    def scan_then_other_enters(*a: Any, **kw: Any) -> list[str]:
        found = real_scan(*a, **kw)
        if not entered:  # 끼어드는 실행은 한 번만
            entered.append(True)
            done.append(
                _collect(root / "run_b", root, snap, sha, live, _refresh_with(log))
            )
        return found

    monkeypatch.setattr(R, "prior_collects", scan_then_other_enters)
    with pytest.raises(SystemExit, match="표본 수집 표시"):
        _collect(root / "run_a", root, snap, sha, live, _refresh_with(log))
    assert done[0]["external_calls"] == 30 and len(log) == 30
    assert not (root / "run_a" / R.COPY_NAME).exists()


def test_collect_overlapping_entry_at_backup_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 검증자 재현 지점 — 첫 실행의 백업 중에 다른 폴더 · 같은 폴더 실행이 들어온다
    snap, sha, _ = _thirty(tmp_path)
    live, root, log = _live(tmp_path), tmp_path / "research", []
    real_copy, refused = R.copy_db, []

    def copy_while_others_enter(src: Path, dst: Path) -> None:
        if not refused:
            for other in (root / "run_b", dst.parent):
                try:
                    _collect(other, root, snap, sha, live, _refresh_with(log))
                except SystemExit as e:
                    refused.append(str(e))
        real_copy(src, dst)

    monkeypatch.setattr(R, "copy_db", copy_while_others_enter)
    doc = _collect(root / "run_a", root, snap, sha, live, _refresh_with(log))
    assert len(refused) == 2 and doc["external_calls"] == 30 and len(log) == 30


def test_collect_same_run_dir_two_samples_only_one_uses_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 서로 다른 표본 두 개가 같은 실행 폴더에 겹쳐 들어와도 폴더(사본 · 기록)는 하나만 쓴다
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    snap_a, sha_a, _ = _thirty(tmp_path / "a")
    snap_b, sha_b = _snapshot(tmp_path / "b", [f"U{i:03d}" for i in range(1, 6)])
    live, root, log = _live(tmp_path), tmp_path / "research", []
    run = tmp_path / "outside" / "shared"
    real_scan, entered, done = R.prior_collects, [], []

    def scan_then_other_enters(*a: Any, **kw: Any) -> list[str]:
        found = real_scan(*a, **kw)
        if not entered:
            entered.append(True)
            done.append(_collect(run, root, snap_b, sha_b, live, _refresh_with(log)))
        return found

    monkeypatch.setattr(R, "prior_collects", scan_then_other_enters)
    with pytest.raises(SystemExit, match="실행 폴더"):
        _collect(run, root, snap_a, sha_a, live, _refresh_with(log))
    assert done[0]["snapshot_sha256"] == sha_b and len(log) == 5
    assert (
        json.loads((run / "collect.json").read_text(encoding="utf-8"))[
            "snapshot_sha256"
        ]
        == sha_b
    )


def test_refused_reused_run_dir_does_not_use_up_sample(tmp_path: Path) -> None:
    # 이미 쓴 실행 폴더(예전 시작 표시 · 연구 폴더 밖)로 거절되면 표본 수집 표시를 남기지 않는다
    snap, sha, _ = _thirty(tmp_path)
    live, root, log = _live(tmp_path), tmp_path / "research", []
    used = tmp_path / "outside" / "used"
    used.mkdir(parents=True)
    (used / R.STARTED_NAME).write_text(json.dumps({"tickers": ["X"]}), encoding="utf-8")
    with pytest.raises(SystemExit, match="이 실행 폴더는 이미"):
        _collect(used, root, snap, sha, live, _refresh_with(log))
    assert not (root / R.CLAIMS_NAME).exists() and log == []
    assert (
        _collect(root / "run", root, snap, sha, live, _refresh_with(log))[
            "external_calls"
        ]
        == 30
    )


def test_collect_marks_kept_after_failure_and_root_is_required(tmp_path: Path) -> None:
    snap, sha, _ = _thirty(tmp_path)
    live, root, log = _live(tmp_path), tmp_path / "research", []

    def broken(**kw: Any) -> Any:
        raise RuntimeError("중간 실패")

    with pytest.raises(RuntimeError):
        _collect(root / "run_a", root, snap, sha, live, broken)
    assert (root / R.CLAIMS_NAME / f"{sha}.json").exists()
    assert (root / "run_a" / R.STARTED_NAME).exists()
    with pytest.raises(SystemExit):
        _collect(root / "run_b", root, snap, sha, live, _refresh_with(log))
    assert log == []
    with pytest.raises(TypeError):  # 기본값이 없어 실제 연구 폴더로 새지 않는다
        R.collect(root / "run_c", live_db=live, snapshot_path=snap, snapshot_sha256=sha)


@pytest.mark.parametrize(
    "status, from_cache, data, want",
    [
        ("ok", False, {}, "new"),
        ("ok", True, {}, "cached"),
        ("ok", False, None, "inconsistent"),
        ("unavailable", False, None, "failed"),
        ("unavailable", False, {}, "old_failed"),
        ("skipped_timeout", False, None, "timeout"),
        ("skipped_timeout", False, {}, "old_timeout"),
        (None, False, None, "missing"),
        (None, False, {}, "old_missing"),
        ("무엇", False, None, "unknown"),
        ("무엇", False, {}, "old_unknown"),
    ],
)
def test_collect_state_table(
    status: Optional[str], from_cache: bool, data: Any, want: str
) -> None:
    from app.sector_constituents_report import STATE_LABEL

    assert C.collect_state(status, from_cache, data) == want
    label = STATE_LABEL[want]
    # F2 — 부르지 않은 것에 '실패'를 쓰지 않는다 · 수집 실패는 불렀을 때만
    assert ("실패" in label) == (status == "unavailable")


def test_timeout_without_provider_call_is_not_collect_failure(tmp_path: Path) -> None:
    # F2 재현 — 실제 수집 기능 · 묶음마다 첫 호출 뒤 시간 예산을 넘김 → 공급자를 부르지 않은 24종목
    snap, sha, tickers = _thirty(tmp_path)
    root, log = tmp_path / "research", []
    doc = _collect(
        root / "run", root, snap, sha, _live(tmp_path), _refresh_with(log, slow_after=1)
    )
    uncalled = [t for t in tickers if t not in log]
    assert len(uncalled) == 24 and doc["external_calls"] == len(log) == 6
    con = sqlite3.connect(f"file:{root / 'run' / R.COPY_NAME}?mode=ro", uri=True)
    try:
        latest = C.read_latest_rows(con, tickers)
    finally:
        con.close()
    frozen = [_frozen(t, i, "Idx") for i, t in enumerate(tickers, start=1)]
    cov = C.coverage(frozen, latest, doc["items"], set(), "2026-11-13")
    state = {c["ticker"]: c["state"] for c in cov}
    assert {state[t] for t in uncalled} == {"timeout"}
    assert {state[t] for t in log} == {"new"}
    full = _full_doc()
    full["coverage"] = cov
    html = render_html(full)
    assert html.count("미확보(시간 초과로 부르지 않음)") == 24
    assert "수집 실패" not in html


def test_comparison_three_scope_counts_confirmed_families_with_stock_rows() -> None:
    frozen = [
        _frozen("N1", 1, "Nifty 50 Index"),
        _frozen("N2", 2, "Nifty 50 Index"),
        _frozen("CASHONLY", 3, "Idx C"),
        _frozen("U1", 4, None),
        _frozen("LATE", 5, "Idx D"),
    ]
    latest = {
        "N1": _cons_rows(("A", "Aco", "2", 1.0)),
        "N2": _cons_rows(("A", "Aco", "2", 1.0)),
        "CASHONLY": _cons_rows(("CASH", "원화현금", "0", 5.0)),
        "U1": _cons_rows(("A", "Aco", "2", 1.0)),
    }
    sc = C.comparison_three_scope(frozen, latest, set())
    assert sc == {
        "etf_with_stock_rows": 3,
        "family_count": 1,
        "unconfirmed_etfs": 1,
        "comparable": False,
    }
    assert (
        C.comparison_three(frozen, latest, set(), set()) == []
    )  # 비교 못 하면 늘 빈 목록
    latest["LATE"] = _cons_rows(("A", "Aco", "2", 1.0))
    sc2 = C.comparison_three_scope(frozen, latest, set())
    assert (sc2["family_count"], sc2["comparable"]) == (2, True)
    assert [x["name"] for x in C.comparison_three(frozen, latest, set(), set())] == [
        "Aco"
    ]


def test_group_scope_counts_only_compared_groups() -> None:
    groups = [
        {"constituents": {"status": "ok", "common": [{"key": "a"}, {"key": "b"}]}},
        {"constituents": {"status": "no_overlap", "common": []}},
        {"constituents": {"status": "single", "common": []}},
        {"constituents": {"status": "no_sample", "common": []}},
        {"constituents": {"common": []}},  # 상태 칸 없음 = 비교했다고 보지 않음
    ]
    assert C.group_scope(groups) == {"groups": 5, "compared": 2, "common": 2}
    assert C.group_scope([]) == {"groups": 0, "compared": 0, "common": 0}


def test_render_not_compared_is_not_zero_or_none() -> None:
    # F3 · F4 와 같은 종류 — 비교를 못 한 곳은 '0건 · 없음'으로 쓰지 않는다
    doc = _full_doc()
    doc["comparison_three"] = []
    doc["comparison_three_scope"] = {
        "etf_with_stock_rows": 2,
        "family_count": 1,
        "unconfirmed_etfs": 2,
        "comparable": False,
    }
    doc["comparison_two_scope"] = {"groups": 3, "compared": 0, "common": 0}
    doc["comparison_two"]["groups"] = [
        {
            "kind": "index",
            "name": "Idx S",
            "etf_count": 2,
            "constituents": {
                "status": "single",
                "common": [],
                "etf_with_data": 1,
                "etf_total": 2,
            },
        },
        {
            "kind": "index",
            "name": "Idx N",
            "etf_count": 2,
            "constituents": {
                "status": "no_overlap",
                "common": [],
                "etf_with_data": 2,
                "etf_total": 2,
            },
        },
    ]
    doc["q5"]["one_month"] = {
        "status": "ok",
        "groups_compared": 0,
        "common_checked": 0,
        "non_stock_common": [],
    }
    html = render_html(doc)
    for text in (
        "비교 못 함 — 주식 행이 있는 확인된 지수 계열이 1개입니다(2개 이상 필요).",
        "비교 못 함 — 주식 행이 있는 확인된 지수 계열 1개 · 계열 미확인 ETF 2개는 세지 않음",
        "구성 자료 30/30 · 같은 묶음 안 공통 구성종목 비교 못 함 — 구성 자료가 2개 이상인 묶음 없음</p>",
        "<td>비교 못 함(구성 자료 1/2)</td>",
        "<td>없음</td>",
        "1개월 상·하위: 비교 못 함 — 구성 자료가 2개 이상인 묶음 없음",
        "3개월 상·하위: 주식 외 공통 항목 0건(공통 구성종목 10건 · 묶음 1개 비교)",
        "공통 구성종목 비교 못 함 — 구성 자료가 2개 이상인 묶음 없음</p>",  # 대조 1 카드
    ):
        assert text in html, text
    assert (
        "그중 주식 외 항목" not in html and "서로 다른 계열 2개 이상 0종목" not in html
    )
    doc["comparison_three_scope"]["comparable"] = True
    doc["comparison_three_scope"]["family_count"] = 4
    html2 = render_html(doc)
    assert (
        "서로 다른 지수 계열 2개 이상에 함께 든 주식이 없습니다(주식 행이 있는 확인된 지수 계열 4개를 대조)."
        in html2
    )
    assert "서로 다른 계열 2개 이상 0종목 · 그중 새로 보임 0종목" in html2


@pytest.mark.parametrize(
    "status, why",
    [
        ("empty", "저장된 가격 없음"),
        ("missing", "시장 DB 없음"),
        ("invalid", "시장 DB 읽기 실패"),
        ("no_common_period", "공통 기간을 정할 수 없음"),
        ("무엇", "알 수 없는 상태"),
    ],
)
def test_q5_and_top_match_not_computed_by_status(status: str, why: str) -> None:
    doc = _full_doc()
    for basis in ("one_month", "three_month"):
        doc["q5"][basis] = {
            "status": status,
            "groups_compared": 0,
            "common_checked": 0,
            "non_stock_common": [],
        }
    doc["copy_top_matches_snapshot"] = None
    html = render_html(doc)
    assert html.count(f"비교 못 함 — 사본으로 운영 요약을 만들지 못함({why})") == 2
    assert f"보관 목록과 비교 못 함({why} · 보관 목록을 사용)" in html
    assert "주식 외 공통 항목 0건" not in html and "다름(보관 목록을 사용)" not in html


def test_report_without_prices_shows_q5_not_computed(
    market: Path, tmp_path: Path  # noqa: F811 — 가져온 fixture
) -> None:
    # F4 재현 — 저장 가격이 없는 사본 · 실제 q5_reproduce · 대조표
    init_constituents_db(market)
    snap_doc = _run(market)
    p = tmp_path / "snap.json"
    p.write_text(json.dumps(snap_doc, ensure_ascii=False), encoding="utf-8")
    sha = hashlib.sha256(p.read_bytes()).hexdigest()

    def fetch(tk: str, asof: str, top_k: int) -> FetchResult:
        return FetchResult(
            status="ok",
            source="naver_stock_etf_component",
            constituents=[
                FetchedConstituent(
                    rank=1,
                    constituent_ticker=None,
                    constituent_name="Xco",
                    weight_pct=5.0,
                    constituent_isin="US0000000001",
                    market_type="2",
                )
            ],
        )

    def refresh(**kw: Any):
        return refresh_constituents(**kw, fetcher=fetch, sleep_fn=lambda s: None)

    run, root = tmp_path / "run", tmp_path / "research"
    _collect(run, root, p, sha, market, refresh)
    with sqlite3.connect(run / R.COPY_NAME) as con:
        con.execute("DELETE FROM etf_daily_price")
    out = tmp_path / "t.html"
    doc = R.report(
        run,
        html_out=out,
        snapshot_path=p,
        snapshot_sha256=sha,
        sources=(OFFICIAL, {}, DICTIONARY, {}),
    )
    assert {doc["q5"][b]["status"] for b in ("one_month", "three_month")} == {"empty"}
    assert doc["q5"]["one_month"]["groups_compared"] == 0
    assert doc["copy_top_matches_snapshot"] is None
    html = out.read_text(encoding="utf-8")
    assert (
        html.count("비교 못 함 — 사본으로 운영 요약을 만들지 못함(저장된 가격 없음)")
        == 2
    )
    assert "주식 외 공통 항목 0건" not in html and "다름(보관 목록을 사용)" not in html


# ── r1 정정 독립 검토 반영 — 사업군 ETF 편입 근거의 대조 범위 ──────────────────────────


def test_sector_evidence_scope_uses_same_sector_etfs() -> None:
    latest = {
        "SEC1": _cons_rows(("A", "Aco", "2", 1.0)),
        "SEC2": _cons_rows(("B", "Bco", "2", 1.0)),
        "IDX1": _cons_rows(("A", "Aco", "2", 1.0)),
    }
    # 사업군 = 공식 기초지수명이 사전에 걸리는 ETF(기존 classify_etf)
    official = {
        "SEC1": {"기초지수명": "FnGuide 반도체 지수"},
        "SEC2": {"기초지수명": "KRX 조선 지수"},
        "IDX1": {"기초지수명": "Solactive Global Index"},
    }
    names = {"SEC1": "KODEX 반도체", "SEC2": "TIGER 조선TOP10", "IDX1": "KODEX 글로벌"}
    dictionary = {"반도체": ["반도체"], "조선": ["조선"]}
    ev = C.sector_evidence(latest, {"A", "B"}, official, dictionary, names)
    scope = C.sector_evidence_scope(latest, official, dictionary, names)
    assert {e["etf"] for v in ev.values() for e in v} == {"SEC1", "SEC2"}
    assert scope == {"sector_etfs": 2, "sectors": 2}
    assert C.sector_evidence_scope({}, official, dictionary, names) == {
        "sector_etfs": 0,
        "sectors": 0,
    }


def test_evidence_none_needs_checked_sector_etfs() -> None:
    doc = _full_doc()
    doc["evidence"] = {}
    doc["evidence_scope"] = {"sector_etfs": 0, "sectors": 0}
    html = render_html(doc)
    _, new = headline(doc)
    assert (
        "사업군 ETF 편입 이력은 확인하지 못했고(구성 자료가 있는 사업군 ETF 없음),"
        " 주식 자체의 업종 자료도 없어 업종 해석은 모두 가설입니다(구성 자료 30/30)."
    ) in new
    assert "확인 못 함(구성 자료가 있는 사업군 ETF 없음)" in html
    assert (
        "사업군 ETF 편입 이력 없음" not in html
        and "이력이 있는 주식은 없고" not in html
    )
    assert "사업군 ETF 편입 근거(구성 자료가 있는 사업군 ETF 0개 대조)" in html
    doc["evidence_scope"] = {"sector_etfs": 23, "sectors": 5}
    html2 = render_html(doc)
    assert "사업군 ETF 편입 근거(구성 자료가 있는 사업군 ETF 23개 대조)" in html2
    assert "<td>사업군 ETF 편입 이력 없음<br>" in html2


def test_report_evidence_not_checked_when_sector_etfs_fail(
    market: Path, tmp_path: Path  # noqa: F811 — 가져온 fixture
) -> None:
    # 독립 검토 재현 — 사업군 ETF 는 모두 수집 실패 · 지수형 2개만 같은 주식을 받음
    init_constituents_db(market)
    snap_doc = _run(market)
    p = tmp_path / "snap.json"
    p.write_text(json.dumps(snap_doc, ensure_ascii=False), encoding="utf-8")
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    x = FetchedConstituent(
        rank=1,
        constituent_ticker=None,
        constituent_name="Xco",
        weight_pct=5.0,
        constituent_isin="US0000000001",
        market_type="2",
    )

    def fetch(tk: str, asof: str, top_k: int) -> FetchResult:
        if tk not in {"AAA006", "AAA010"}:
            return FetchResult(
                status="unavailable",
                source="naver_stock_etf_component",
                constituents=[],
                message="http_failed",
            )
        return FetchResult(
            status="ok", source="naver_stock_etf_component", constituents=[x]
        )

    def refresh(**kw: Any):
        return refresh_constituents(**kw, fetcher=fetch, sleep_fn=lambda s: None)

    run, root = tmp_path / "run", tmp_path / "research"
    _collect(run, root, p, sha, market, refresh)
    out = tmp_path / "t.html"
    doc = R.report(
        run,
        html_out=out,
        snapshot_path=p,
        snapshot_sha256=sha,
        sources=(OFFICIAL, {}, DICTIONARY, {}),
    )
    assert [x["name"] for x in doc["comparison_three"]] == ["Xco"]
    assert doc["evidence"] == {} and doc["evidence_scope"]["sector_etfs"] == 0
    html = out.read_text(encoding="utf-8")
    assert (
        "사업군 ETF 편입 이력은 확인하지 못했고(구성 자료가 있는 사업군 ETF 없음)"
        in html
    )
    assert "확인 못 함(구성 자료가 있는 사업군 ETF 없음)" in html
    assert "사업군 ETF 편입 이력 없음" not in html
