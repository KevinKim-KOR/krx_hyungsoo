"""Universe Seed Bootstrap propose 테스트 (지시문 §33.1).

검증자 재정정:
- ETF 만 대상 (개별 주식은 제외).
- source 실패는 삼키지 않고 partial 로 명시.
- publishable_proposal boolean 계약.
- materialize 는 canonical seed validation 을 통과해야 저장.
- 예제 seed 참조 없음.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.holdings import Holding
from app.market_cache import MarketQuote
from app.universe_bootstrap.materialize import (
    ApprovedItem,
    UniverseApprovalError,
    materialize_seed,
)
from app.universe_bootstrap.proposal import (
    HOLDING_MANUAL_REVIEW_REASON,
    HOLDING_REASON_TEXT,
    MARKET_REASON_TEXT,
    PROPOSAL_SOURCE_BOTH,
    PROPOSAL_SOURCE_HOLDING,
    PROPOSAL_SOURCE_MANUAL_REVIEW,
    PROPOSAL_SOURCE_MARKET,
    TOTAL_MAX,
    build_bootstrap_proposal,
)

# 테스트 fixture: ETF ticker 로 취급할 세트 (실제 etf_master 값 무관, 격리).
_ALL_TEST_TICKERS_AS_ETF = lambda: [  # noqa: E731
    "A",
    "B",
    "C",
    "SHARED",
    "MA",
    "MB",
    "MC",
    "H1",
    "H2",
    *[f"H{i}" for i in range(20)],
    *[f"M{i}" for i in range(20)],
    *[f"T{i}" for i in range(30)],
]


def _q(ticker: str, price: float) -> MarketQuote:
    return MarketQuote(
        ticker=ticker,
        name=f"{ticker}_name",
        current_price=price,
        price_asof="2026-07-15",
        price_source="test",
    )


def _h(ticker: str, qty: float = 10.0, avg: float = 10000.0, name=None) -> Holding:
    return Holding(ticker=ticker, quantity=qty, avg_buy_price=avg, name=name)


def _topn(candidates: list[dict[str, Any]], asof: str = "2026-07-15") -> dict:
    return {"status": "ok", "asof": asof, "candidates": candidates}


def _mk_market_candidate(rank: int, ticker: str, name: str) -> dict[str, Any]:
    return {"rank": rank, "ticker": ticker, "name": name}


def _build(
    *,
    holdings=None,
    quotes=None,
    topn=None,
    etf_tickers=None,
):
    return build_bootstrap_proposal(
        holdings_loader=lambda: holdings or [],
        market_quotes_loader=lambda: quotes or {},
        etf_ticker_loader=(etf_tickers or _ALL_TEST_TICKERS_AS_ETF),
        topn_fn=lambda **_: topn or _topn([]),
    )


# ── 33.1.1 Holdings 평가 가능한 정상 후보 정렬 ──


def test_holdings_ranked_by_eval_desc() -> None:
    r = _build(
        holdings=[_h("A", qty=1, avg=1000), _h("B", qty=100, avg=1000)],
        quotes={"A": _q("A", 100.0), "B": _q("B", 100.0)},
    )
    tickers = [p.ticker for p in r.proposals if p.holding_rank]
    assert tickers == ["B", "A"]
    assert r.publishable_proposal is True


# ── 33.1.2 Holdings 평가 불가 → 자동 순위 제외 ──


def test_holdings_no_price_excluded_from_auto_rank() -> None:
    r = _build(
        holdings=[_h("A", qty=10, avg=1000), _h("B", qty=10, avg=1000)],
        quotes={"A": _q("A", 100.0)},  # B 시세 없음.
    )
    ranked = [p for p in r.proposals if p.holding_rank is not None]
    manual = [
        p for p in r.proposals if p.proposal_source == PROPOSAL_SOURCE_MANUAL_REVIEW
    ]
    assert [p.ticker for p in ranked] == ["A"]
    assert [p.ticker for p in manual] == ["B"]
    assert manual[0].proposal_reason == HOLDING_MANUAL_REVIEW_REASON


# ── 33.1.3 Market Discovery 기존 순서 유지 ──


def test_market_discovery_order_preserved() -> None:
    cands = [
        _mk_market_candidate(1, "MA", "MA_name"),
        _mk_market_candidate(2, "MB", "MB_name"),
        _mk_market_candidate(3, "MC", "MC_name"),
    ]
    r = _build(topn=_topn(cands))
    ordered = [
        p.ticker for p in r.proposals if p.proposal_source == PROPOSAL_SOURCE_MARKET
    ]
    assert ordered == ["MA", "MB", "MC"]


# ── 33.1.4 보유 후보 최대 10개 ──


def test_holding_max_ten() -> None:
    holdings = [_h(f"H{i}", qty=i + 1, avg=1000) for i in range(15)]
    quotes = {f"H{i}": _q(f"H{i}", 100.0) for i in range(15)}
    r = _build(holdings=holdings, quotes=quotes)
    ranked = [p for p in r.proposals if p.holding_rank]
    assert len(ranked) == 10


# ── 33.1.5 외부 후보 최대 10개 ──


def test_market_max_ten() -> None:
    cands = [_mk_market_candidate(i + 1, f"M{i}", f"M{i}_name") for i in range(15)]
    r = _build(topn=_topn(cands))
    market_only = [
        p for p in r.proposals if p.proposal_source == PROPOSAL_SOURCE_MARKET
    ]
    assert len(market_only) == 10


# ── 33.1.6 전체 최대 20개 ──


def test_total_max_twenty() -> None:
    holdings = [_h(f"H{i}", qty=i + 1, avg=1000) for i in range(15)]
    quotes = {f"H{i}": _q(f"H{i}", 100.0) for i in range(15)}
    cands = [_mk_market_candidate(i + 1, f"M{i}", f"M{i}_name") for i in range(15)]
    r = _build(holdings=holdings, quotes=quotes, topn=_topn(cands))
    assert r.proposal_count <= TOTAL_MAX
    assert r.proposal_count == 20


# ── 33.1.7 ticker 중복 제거 ──


def test_ticker_deduplication_both() -> None:
    r = _build(
        holdings=[_h("SHARED", qty=10, avg=1000)],
        quotes={"SHARED": _q("SHARED", 100.0)},
        topn=_topn(
            [
                _mk_market_candidate(1, "SHARED", "SHARED_name"),
                _mk_market_candidate(2, "MB", "MB_name"),
            ]
        ),
    )
    shared = [p for p in r.proposals if p.ticker == "SHARED"]
    assert len(shared) == 1
    assert shared[0].proposal_source == PROPOSAL_SOURCE_BOTH
    assert shared[0].holding_rank == 1
    assert shared[0].market_discovery_rank == 1


# ── 33.1.8 중복 후 Market Discovery 다음 순위 보충 ──


def test_market_fills_after_dedup() -> None:
    r = _build(
        holdings=[_h("SHARED", qty=10, avg=1000)],
        quotes={"SHARED": _q("SHARED", 100.0)},
        topn=_topn(
            [
                _mk_market_candidate(1, "SHARED", "SHARED_name"),
                _mk_market_candidate(2, "MA", "MA_name"),
                _mk_market_candidate(3, "MB", "MB_name"),
            ]
        ),
    )
    market_only = [
        p.ticker for p in r.proposals if p.proposal_source == PROPOSAL_SOURCE_MARKET
    ]
    assert "MA" in market_only and "MB" in market_only


# ── 33.1.9 20개 강제 채움 없음 ──


def test_no_forced_fill_to_twenty() -> None:
    r = _build(
        holdings=[_h("H1", qty=10, avg=1000)],
        quotes={"H1": _q("H1", 100.0)},
        topn=_topn([_mk_market_candidate(1, "MA", "MA_name")]),
    )
    assert r.proposal_count == 2


# ── 33.1.10~12 proposal_source ──


def test_proposal_source_holding_only() -> None:
    r = _build(holdings=[_h("H1", qty=10, avg=1000)], quotes={"H1": _q("H1", 100.0)})
    assert r.proposals[0].proposal_source == PROPOSAL_SOURCE_HOLDING
    assert r.proposals[0].proposal_reason == HOLDING_REASON_TEXT


def test_proposal_source_market_only() -> None:
    r = _build(topn=_topn([_mk_market_candidate(1, "MA", "MA_name")]))
    assert r.proposals[0].proposal_source == PROPOSAL_SOURCE_MARKET
    assert r.proposals[0].proposal_reason == MARKET_REASON_TEXT


def test_proposal_source_both() -> None:
    r = _build(
        holdings=[_h("SHARED", qty=10, avg=1000)],
        quotes={"SHARED": _q("SHARED", 100.0)},
        topn=_topn([_mk_market_candidate(1, "SHARED", "S_name")]),
    )
    both = [p for p in r.proposals if p.proposal_source == PROPOSAL_SOURCE_BOTH]
    assert len(both) == 1


# ── 33.1.13~16 개인정보 비노출 ──


def test_no_quantity_in_output() -> None:
    r = _build(
        holdings=[_h("A", qty=99999, avg=88888)],
        quotes={"A": _q("A", 100.0)},
    )
    for p in r.proposals:
        assert "99999" not in (p.proposal_reason or "")
        for attr in ("quantity", "qty", "eval_amount", "invested_amount"):
            assert not hasattr(p, attr), f"forbidden attr: {attr}"


def test_no_avg_buy_price_in_output() -> None:
    r = _build(
        holdings=[_h("A", qty=10, avg=77777)],
        quotes={"A": _q("A", 100.0)},
    )
    for p in r.proposals:
        assert "77777" not in (p.proposal_reason or "")
        assert not hasattr(p, "avg_buy_price")


def test_no_eval_amount_in_output() -> None:
    r = _build(
        holdings=[_h("A", qty=10, avg=1000)],
        quotes={"A": _q("A", 100.0)},
    )
    for p in r.proposals:
        assert not hasattr(p, "eval_amount")


def test_no_account_group_in_output() -> None:
    h = _h("A", qty=10, avg=1000)
    h.account_group = "SecretAcct"
    r = _build(holdings=[h], quotes={"A": _q("A", 100.0)})
    for p in r.proposals:
        assert "SecretAcct" not in (p.name or "")
        assert "SecretAcct" not in (p.proposal_reason or "")
        assert not hasattr(p, "account_group")


# ── 33.1.17~19 source 실패 (검증자 재정정: 삼키지 않고 partial) ──


def test_holdings_source_failure_returns_partial() -> None:
    """검증자 재정정: canonical holdings source 실패는 부분 성공 X → partial."""

    def _fail_loader() -> list:
        raise RuntimeError("holdings unavailable")

    r = build_bootstrap_proposal(
        holdings_loader=_fail_loader,
        market_quotes_loader=lambda: {},
        etf_ticker_loader=_ALL_TEST_TICKERS_AS_ETF,
        topn_fn=lambda **_: _topn([_mk_market_candidate(1, "MA", "MA_name")]),
    )
    assert r.status == "partial"
    assert r.publishable_proposal is False
    assert r.proposal_count == 0
    # 검증자 REJECTED r2: sanitized error_reason (내부 exception 클래스명 노출 X).
    assert r.error_reason == "holdings_source_unavailable"
    assert "RuntimeError" not in (r.error_reason or "")


def test_market_discovery_source_failure_returns_partial() -> None:
    """검증자 재정정: canonical market discovery source 실패도 partial."""

    def _fail_topn(**_):
        raise RuntimeError("topn unavailable")

    r = build_bootstrap_proposal(
        holdings_loader=lambda: [_h("H1", qty=10, avg=1000)],
        market_quotes_loader=lambda: {"H1": _q("H1", 100.0)},
        etf_ticker_loader=_ALL_TEST_TICKERS_AS_ETF,
        topn_fn=_fail_topn,
    )
    assert r.status == "partial"
    assert r.publishable_proposal is False
    assert r.proposal_count == 0
    # 검증자 REJECTED r2: sanitized error_reason.
    assert r.error_reason == "market_discovery_source_unavailable"
    assert "RuntimeError" not in (r.error_reason or "")


def test_both_sources_empty_returns_partial() -> None:
    """정상 실행이지만 두 범주 모두 비면 partial."""
    r = _build()  # holdings=[], topn=empty.
    assert r.status == "partial"
    assert r.publishable_proposal is False


# ── 33.1.20 propose 는 seed 파일을 생성하지 않는다 ──


def test_propose_does_not_write_any_seed_file(tmp_path, monkeypatch) -> None:
    """검증자 재정정: propose 이후 실제 seed 파일이 생성되지 않았음을 명시 확인."""
    from app.universe_bootstrap import materialize as _mat

    fake_default = tmp_path / "would_be_default.json"
    monkeypatch.setattr(_mat, "DEFAULT_SEED_PATH", fake_default)
    _ = _build(holdings=[_h("H1", qty=10, avg=1000)], quotes={"H1": _q("H1", 100.0)})
    assert not fake_default.exists()


# ── 33.1.21~23 materialize 계약 ──


def test_materialize_only_approved_items(tmp_path) -> None:
    approved = [
        ApprovedItem(ticker="069500", name="KODEX 200"),
        ApprovedItem(ticker="139260", name="TIGER 200 IT"),
    ]
    seed_path = tmp_path / "seed.json"
    materialize_seed(approved, asof="2026-07-16", seed_path=seed_path)
    import json

    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    assert payload["source"] == "manual"
    assert payload["asof"] == "2026-07-16"
    assert [it["ticker"] for it in payload["items"]] == ["069500", "139260"]


def test_materialize_rejects_duplicate_ticker(tmp_path) -> None:
    approved = [
        ApprovedItem(ticker="069500", name="KODEX 200"),
        ApprovedItem(ticker="069500", name="KODEX 200 dup"),
    ]
    with pytest.raises(UniverseApprovalError, match="ticker 중복"):
        materialize_seed(approved, asof="2026-07-16", seed_path=tmp_path / "seed.json")


def test_materialize_rejects_over_twenty(tmp_path) -> None:
    approved = [ApprovedItem(ticker=f"T{i:03d}", name=f"T{i}") for i in range(21)]
    with pytest.raises(UniverseApprovalError, match="20개를 초과"):
        materialize_seed(approved, asof="2026-07-16", seed_path=tmp_path / "seed.json")


def test_materialize_rejects_empty(tmp_path) -> None:
    with pytest.raises(UniverseApprovalError, match="비어있습니다"):
        materialize_seed([], asof="2026-07-16", seed_path=tmp_path / "seed.json")


# ── 33.1.24 source=manual ──


def test_seed_source_is_manual(tmp_path) -> None:
    approved = [ApprovedItem(ticker="069500", name="KODEX 200")]
    seed_path = tmp_path / "seed.json"
    materialize_seed(approved, asof="2026-07-16", seed_path=seed_path)
    import json

    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    assert payload["source"] == "manual"


# ── 33.1.25 예제 seed 운영 사용 없음 ──


def test_no_example_seed_reference_in_source() -> None:
    from pathlib import Path

    src1 = Path("app/universe_bootstrap/proposal.py").read_text(encoding="utf-8")
    src2 = Path("app/universe_bootstrap/materialize.py").read_text(encoding="utf-8")
    for src in (src1, src2):
        assert "docs/examples" not in src
        assert "etf_universe_latest.example" not in src


# ── 검증자 재정정: 신규 계약 tests ──


def test_holdings_only_etf_included() -> None:
    """검증자 재정정: 개별 주식 (etf_master 부재) 은 후보에서 제외."""
    r = build_bootstrap_proposal(
        holdings_loader=lambda: [
            _h("000660", qty=10, avg=100000),  # 개별 주식 (SK하이닉스 시뮬).
            _h("069500", qty=10, avg=30000),  # ETF (KODEX 200).
        ],
        market_quotes_loader=lambda: {
            "000660": _q("000660", 200000.0),
            "069500": _q("069500", 40000.0),
        },
        etf_ticker_loader=lambda: ["069500"],  # etf_master 에는 069500 만.
        topn_fn=lambda **_: _topn([]),
    )
    tickers = [p.ticker for p in r.proposals]
    assert "069500" in tickers
    assert "000660" not in tickers, "개별 주식은 후보에서 제외돼야 함"


def test_publishable_proposal_boolean_contract() -> None:
    """publishable_proposal 은 boolean · 후보 존재 시 True, 실패 시 False."""
    r_ok = _build(holdings=[_h("H1", qty=10, avg=1000)], quotes={"H1": _q("H1", 100.0)})
    assert isinstance(r_ok.publishable_proposal, bool)
    assert r_ok.publishable_proposal is True

    r_partial = _build()
    assert isinstance(r_partial.publishable_proposal, bool)
    assert r_partial.publishable_proposal is False


def test_materialize_rejects_invalid_asof_via_canonical_parser(tmp_path) -> None:
    """검증자 REJECTED r1: materialize 는 canonical parse_universe_seed 로 재검증."""
    approved = [ApprovedItem(ticker="069500", name="KODEX 200")]
    with pytest.raises(UniverseApprovalError, match="canonical seed validation 실패"):
        materialize_seed(approved, asof="not-a-date", seed_path=tmp_path / "seed.json")
    # 파일이 생성되지 않아야 함 (in-memory 검증 실패 후 write 시도 X).
    assert not (tmp_path / "seed.json").exists()


def test_holdings_internal_duplicate_ticker_deduplicated() -> None:
    """검증자 REJECTED r8+r9: 같은 ticker Holdings 여러 행 → 1건 + 평가금액 합산.

    검증자 REJECTED r9 재정정: SHARED 총 평가금액 = 100 + 10000 = 10100 > B 5000.
    첫 등장 행만 유지 (100) 하면 B 가 위로 오는 순위 왜곡 발생.
    """
    h1 = _h("SHARED", qty=1, avg=100)
    h1.account_group = "일반"
    h2 = _h("SHARED", qty=100, avg=100)  # eval = 100 * 100 = 10000.
    h2.account_group = "isa"
    hB = _h("B", qty=50, avg=100)  # eval = 50 * 100 = 5000.
    r = _build(
        holdings=[h1, h2, hB],
        quotes={
            "SHARED": _q("SHARED", 100.0),
            "B": _q("B", 100.0),
        },
    )
    shared = [p for p in r.proposals if p.ticker == "SHARED"]
    assert len(shared) == 1
    # SHARED (합산 10100) > B (5000) → SHARED 가 rank 1.
    ranked = [(p.ticker, p.holding_rank) for p in r.proposals if p.holding_rank]
    assert ranked == [("SHARED", 1), ("B", 2)]


def test_holdings_duplicate_eval_amount_not_exposed() -> None:
    """검증자 REJECTED r9 재정정: 합산 평가금액이 proposal 결과에 노출되지 않음."""
    h1 = _h("SHARED", qty=100, avg=99)  # eval=9900.
    h1.account_group = "일반"
    h2 = _h("SHARED", qty=100, avg=77)  # eval=7700.
    h2.account_group = "isa"
    r = _build(holdings=[h1, h2], quotes={"SHARED": _q("SHARED", 100.0)})
    for p in r.proposals:
        # 개인정보 (§7.4): 합산 평가금액 값 (17600), 개별 값 (9900/7700) 노출 금지.
        for kw in ("17600", "9900", "7700"):
            assert kw not in (p.name or "")
            assert kw not in (p.proposal_reason or "")
        assert not hasattr(p, "eval_amount")
        assert not hasattr(p, "eval_sum")


def test_market_discovery_internal_duplicate_ticker_deduplicated() -> None:
    """검증자 REJECTED r8: Market Discovery 내부 동일 ticker 2행 → 1건만."""
    r = _build(
        topn=_topn(
            [
                _mk_market_candidate(1, "MA", "MA_name"),
                _mk_market_candidate(2, "MA", "MA_name_dup"),  # 중복.
                _mk_market_candidate(3, "MB", "MB_name"),
            ]
        )
    )
    ma = [p for p in r.proposals if p.ticker == "MA"]
    assert len(ma) == 1
    # 첫 등장 유지 (rank=1).
    assert ma[0].market_discovery_rank == 1


def test_market_discovery_malformed_candidate_returns_partial() -> None:
    """검증자 REJECTED r7: Market Discovery candidate 손상 시 partial.

    이전 구현은 c.get("ticker") 에서 AttributeError 전파.
    정정: BootstrapSourceError 로 승격 → 상위가 partial 처리.
    """

    def _bad_topn(**_):
        # candidates 중 하나가 dict 아님.
        return {"status": "ok", "asof": "2026-07-15", "candidates": ["not_a_dict"]}

    r = build_bootstrap_proposal(
        holdings_loader=lambda: [_h("H1", qty=10, avg=1000)],
        market_quotes_loader=lambda: {"H1": _q("H1", 100.0)},
        etf_ticker_loader=_ALL_TEST_TICKERS_AS_ETF,
        topn_fn=_bad_topn,
    )
    assert r.status == "partial"
    assert r.publishable_proposal is False
    assert r.error_reason == "market_discovery_source_unavailable"


def test_cli_materialize_rejects_malformed_item(tmp_path, capsys) -> None:
    """검증자 REJECTED r7: 승인 목록에 dict 아닌 항목 있으면 CLI 전체 실패.

    이전 구현은 continue 로 조용히 skip → "승인된 종목 제거 금지" 계약 위반.
    """
    import json as _json

    from scripts.run_universe_seed_bootstrap import main as boot_main

    approved_file = tmp_path / "approved.json"
    approved_file.write_text(
        _json.dumps(
            {
                "asof": "2026-07-16",
                "items": [
                    {"ticker": "069500", "name": "KODEX 200"},
                    "not_a_dict_item",  # ← malformed.
                ],
            }
        ),
        encoding="utf-8",
    )
    rc = boot_main(["materialize", "--approved", str(approved_file)])
    out = _json.loads(capsys.readouterr().out)
    assert rc == 2
    assert "approved_item_not_dict" in out["error_reason"]


def test_materialize_preserves_existing_seed_when_new_invalid(tmp_path) -> None:
    """검증자 REJECTED r2 (B-1): validation 실패 시 기존 정상 seed 는 보존.

    이전 구현은 파일을 먼저 덮어쓴 후 검증 → 실패 시 기존 seed 삭제.
    정정: in-memory validation 우선 → 실패 시 target 파일 손대지 않음.
    """
    import json as _json

    seed_path = tmp_path / "seed.json"
    existing = {
        "asof": "2026-01-01",
        "source": "manual",
        "items": [{"ticker": "069500", "name": "KODEX 200"}],
    }
    seed_path.write_text(_json.dumps(existing), encoding="utf-8")
    existing_bytes = seed_path.read_bytes()

    approved = [ApprovedItem(ticker="139260", name="TIGER 200 IT")]
    with pytest.raises(UniverseApprovalError, match="canonical seed validation 실패"):
        materialize_seed(approved, asof="not-a-date", seed_path=seed_path)

    # 기존 seed 는 byte 단위로 보존됐어야 함.
    assert seed_path.exists()
    assert seed_path.read_bytes() == existing_bytes
