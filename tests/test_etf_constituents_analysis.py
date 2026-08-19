"""ETF 구성종목 집중도 + 중복률 분석 단위 테스트 (POC2 — 2026-05-27).

지시문 §9 의 매칭 규칙 + 중복률 공식 검증.
"""

from __future__ import annotations

from pathlib import Path

from app.etf_constituents_analysis import (
    compute_analysis,
    compute_concentration,
    compute_pair_overlap,
    compute_repeated_core_holdings,
)
from app.etf_constituents_store import ConstituentRow, upsert_constituents


def _row(etf, rank, ticker, name, weight, asof="2026-05-26", source="src"):
    return ConstituentRow(
        etf_ticker=etf,
        asof=asof,
        source=source,
        rank=rank,
        constituent_ticker=ticker,
        constituent_name=name,
        weight_pct=weight,
    )


def test_concentration_calculates_top_n_sums():
    rows = [
        _row("A", 1, "005930", "삼성전자", 25.0),
        _row("A", 2, "000660", "SK하이닉스", 15.0),
        _row("A", 3, "035420", "NAVER", 10.0),
        _row("A", 4, "051910", "LG화학", 8.0),
        _row("A", 5, "005380", "현대차", 6.0),
        _row("A", 6, "207940", "삼성바이오", 4.0),
        _row("A", 7, "068270", "셀트리온", 3.0),
        _row("A", 8, "323410", "카카오뱅크", 2.0),
        _row("A", 9, "012330", "현대모비스", 2.0),
        _row("A", 10, "066570", "LG전자", 1.5),
    ]
    out = compute_concentration(rows)
    assert out["top1_weight_pct"] == 25.0
    assert out["top3_weight_pct"] == 50.0
    assert out["top5_weight_pct"] == 64.0
    assert out["top10_weight_pct"] == 76.5


def test_compute_pair_overlap_min_weight_sum():
    left = [
        _row("A", 1, "005930", "삼성전자", 25.0),
        _row("A", 2, "000660", "SK하이닉스", 20.0),
        _row("A", 3, "035420", "NAVER", 10.0),
    ]
    right = [
        _row("B", 1, "005930", "삼성전자", 30.0),  # common
        _row("B", 2, "000660", "SK하이닉스", 15.0),  # common
        _row("B", 3, "051910", "LG화학", 8.0),
    ]
    out = compute_pair_overlap(left, right, top_k=10)
    assert out["common_count_top10"] == 2
    # min(25, 30) + min(20, 15) = 25 + 15 = 40
    assert out["weighted_overlap_pct"] == 40.0
    tickers = {h["ticker"] for h in out["common_holdings"]}
    assert tickers == {"005930", "000660"}


def test_compute_pair_overlap_falls_back_to_name_when_ticker_missing():
    left = [
        _row("A", 1, None, "삼성전자(우)", 10.0),
    ]
    right = [
        _row("B", 1, None, "삼성전자", 8.0),
    ]
    out = compute_pair_overlap(left, right)
    # 정규화 (괄호 제거) 로 "삼성전자" 매칭 → common 1.
    assert out["common_count_top10"] == 1
    assert out["weighted_overlap_pct"] == 8.0


def test_compute_repeated_core_holdings_aggregates_across_etfs():
    per_ticker = {
        "A": [_row("A", 1, "005930", "삼성전자", 25.0)],
        "B": [_row("B", 1, "005930", "삼성전자", 30.0)],
        "C": [_row("C", 1, "000660", "SK하이닉스", 15.0)],
        "D": [_row("D", 1, "005930", "삼성전자", 22.0)],
    }
    out = compute_repeated_core_holdings(per_ticker, top_k=10, min_appears=2)
    # 삼성전자 가 3개 ETF 에서 등장 — 1위.
    assert out[0]["ticker"] == "005930"
    assert out[0]["appears_in_etf_count"] == 3
    # SK하이닉스 는 1번만 등장 — 제외.
    assert all(r["ticker"] != "000660" for r in out)


def test_compute_analysis_integration(tmp_path: Path):
    db = tmp_path / "m.sqlite"
    # 2 ETF 의 구성종목 미리 저장.
    upsert_constituents(
        [
            _row("139260", 1, "005930", "삼성전자", 25.0),
            _row("139260", 2, "000660", "SK하이닉스", 20.0),
        ],
        db_path=db,
    )
    upsert_constituents(
        [
            _row("363580", 1, "005930", "삼성전자", 30.0),
            _row("363580", 2, "035420", "NAVER", 12.0),
        ],
        db_path=db,
    )
    out = compute_analysis(
        tickers=["139260", "363580", "0167A0"],
        asof="2026-05-26",
        db_path=db,
    )
    assert out["status"] == "ok"
    assert out["coverage"]["requested_count"] == 3
    assert out["coverage"]["available_count"] == 2
    assert out["coverage"]["unavailable_count"] == 1
    # 0167A0 는 unavailable.
    statuses = {c["etf_ticker"]: c["status"] for c in out["constituents"]}
    assert statuses["0167A0"] == "unavailable"
    assert statuses["139260"] == "ok"
    # overlap_matrix 는 C(3,2) = 3 pair.
    assert len(out["overlap_matrix"]) == 3
    # 139260 vs 363580 의 common = 005930 1건.
    pair = next(
        p
        for p in out["overlap_matrix"]
        if p["left_ticker"] == "139260" and p["right_ticker"] == "363580"
    )
    assert pair["common_count_top10"] == 1
    # min(25, 30) = 25.
    assert pair["weighted_overlap_pct"] == 25.0


# ── 2026-08-19 설계 확정: 표시 깊이와 중복률 깊이 분리 ────────────────────


def _deep_rows(etf: str, names: list[str], *, asof="2026-08-19"):
    """rank 1..N 을 만든다. 앞쪽일수록 비중이 크다.

    겹침은 **티커**로 판정되므로 티커를 이름에서 파생시킨다 — rank 로 만들면
    서로 다른 종목이 같은 티커를 갖게 돼 테스트가 무의미해진다.
    """
    return [
        _row(etf, i, f"TK-{n}", n, float(30 - i), asof=asof)
        for i, n in enumerate(names, start=1)
    ]


def test_display_depth_does_not_change_overlap_basis(tmp_path: Path):
    """top_k 를 30 으로 올려도 중복률은 상위 10건 기준을 유지한다.

    A·B 는 상위 10건이 전부 다르고 **11~20위에서만 겹친다.** 표시 깊이가
    중복률에 새면 공통 종목이 잡히고, 분리돼 있으면 0 이다.
    """
    db = tmp_path / "m.sqlite"
    a_names = [f"A{i}" for i in range(1, 11)] + [f"공통{i}" for i in range(1, 11)]
    b_names = [f"B{i}" for i in range(1, 11)] + [f"공통{i}" for i in range(1, 11)]
    upsert_constituents(_deep_rows("AAA", a_names), db_path=db)
    upsert_constituents(_deep_rows("BBB", b_names), db_path=db)

    out = compute_analysis(
        tickers=["AAA", "BBB"], asof="2026-08-19", top_k=30, db_path=db
    )

    # 표시는 깊어진다.
    by_tk = {c["etf_ticker"]: c for c in out["constituents"]}
    assert len(by_tk["AAA"]["top_holdings"]) == 20

    # 중복률은 상위 10 기준 그대로 — 겹침 0.
    pair = out["overlap_matrix"][0]
    assert pair["common_count_top10"] == 0, pair
    assert pair["weighted_overlap_pct"] is None
    assert out["repeated_core_holdings"] == []

    # 응답이 두 기준을 구분해 낸다.
    assert out["top_k"] == 30
    assert out["overlap_top_k"] == 10


def test_overlap_still_detected_within_top10(tmp_path: Path):
    """상위 10건 안에서 겹치면 표시 깊이와 무관하게 잡힌다 (역검증)."""
    db = tmp_path / "m.sqlite"
    a_names = ["공통1", "공통2"] + [f"A{i}" for i in range(3, 21)]
    b_names = ["공통1", "공통2"] + [f"B{i}" for i in range(3, 21)]
    upsert_constituents(_deep_rows("AAA", a_names), db_path=db)
    upsert_constituents(_deep_rows("BBB", b_names), db_path=db)

    out = compute_analysis(
        tickers=["AAA", "BBB"], asof="2026-08-19", top_k=30, db_path=db
    )
    pair = out["overlap_matrix"][0]
    assert pair["common_count_top10"] == 2, pair
    assert pair["weighted_overlap_pct"] is not None
    assert len(out["repeated_core_holdings"]) == 2
