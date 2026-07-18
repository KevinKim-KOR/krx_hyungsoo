"""Universe Seed Bootstrap 후보 제안 조립기.

지시문 §5~§9:
- 보유 ETF 최대 10개 (기존 enrich_holdings 로 계산 가능한 평가금액 내림차순).
- Market Discovery 최대 10개 (기존 compute_topn 순위 유지).
- ticker 중복 제거 (proposal_source = holding / market_discovery / both).
- 전체 최대 20개. 채우기 위한 임의 종목 추가 X.
- 신규 factor · threshold · 재정렬 X.

지시문 §7.4 · §10.1 비노출:
- proposal 결과에 수량 · 평단 · 평가금액 · account_group · 원금 · Holdings JSON 원문 노출 X.

지시문 §10.2 (실패 계약, 검증자 재정정):
- 어느 canonical source 든 읽지 못하면 (broad exception 삼킴 금지)
  운영 후보를 제안하지 않는다. 두 범주 모두 실패 시 partial.
- 일부 종목의 평가금액만 계산 불가한 경우 (예: 시세 없음) 는 정상 부분 실패 —
  나머지 정상 보유 후보 + Market Discovery 로 제안 가능.

지시문 §6 (검증자 재정정): 보유 후보는 **ETF 만**. 개별 주식은 제외.
`app.market_data_store.list_etf_tickers()` 로 canonical ETF set 확인.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

HOLDING_MAX = 10
MARKET_MAX = 10
TOTAL_MAX = 20

HOLDING_REASON_TEXT = "보유 포트폴리오 내 영향도가 큰 종목"
HOLDING_MANUAL_REVIEW_REASON = "평가 기준 부족으로 자동 순위 제외"
MARKET_REASON_TEXT = "Market Discovery 후보"

PROPOSAL_SOURCE_HOLDING = "holding"
PROPOSAL_SOURCE_MARKET = "market_discovery"
PROPOSAL_SOURCE_BOTH = "both"
PROPOSAL_SOURCE_MANUAL_REVIEW = "holding_manual_review"


@dataclass
class ProposedCandidate:
    ticker: str
    name: Optional[str]
    proposal_source: str
    proposal_reason: str
    holding_rank: Optional[int] = None
    market_discovery_rank: Optional[int] = None
    data_asof: Optional[str] = None


@dataclass
class ProposalResult:
    status: str  # "ok" | "partial"
    holdings_asof: Optional[str]
    market_discovery_asof: Optional[str]
    holding_candidates_available: bool
    market_candidates_available: bool
    proposals: list[ProposedCandidate] = field(default_factory=list)
    error_reason: Optional[str] = None
    # 지시문 §10.2 재정정: proposal 결과가 seed materialization 대상인지 명시.
    publishable_proposal: bool = False

    @property
    def proposal_count(self) -> int:
        return len(self.proposals)


def _rank_holdings_by_eval(
    enriched_list: list, etf_ticker_set: set[str]
) -> tuple[list[tuple], list[tuple]]:
    """ETF 만 대상. (ranked_by_eval_desc, manual_review_items) 반환.

    ranked_by_eval_desc: [(ticker, name, price_asof, eval_amount)], eval_amount 내림차순.
    manual_review_items: 평가 불가 (eval_amount None) 항목 중 ETF 만.
    """
    # 검증자 REJECTED r9 재정정: 같은 ticker 여러 계좌 → 평가금액 합산 후 순위.
    # 첫 등장 행만 유지하면 계좌 순서에 의존해 순위가 왜곡됨. §7 "평가금액 내림차순"
    # 계약 유지 위해 ticker 별로 sum(eval_amount) 을 산출한 뒤 정렬.
    #
    # scored: eval_amount 가 하나 이상 존재하는 ticker (합산). name/asof 는 첫
    #   등장 시점 값 유지 (사용자 표시용).
    # manual_review: 모든 계좌 행이 eval_amount None 인 ticker (평가 불가).
    per_ticker: dict[str, dict[str, Any]] = {}
    for e in enriched_list:
        ticker = getattr(e, "ticker", None)
        if not ticker:
            continue
        if ticker not in etf_ticker_set:
            continue
        eval_amt = getattr(e, "eval_amount", None)
        name = getattr(e, "name", None)
        price_asof = getattr(e, "price_asof", None)
        agg = per_ticker.setdefault(
            ticker,
            {
                "name": name,
                "price_asof": price_asof,
                "eval_sum": 0.0,
                "has_eval": False,
            },
        )
        # name / price_asof 는 첫 등장 값 유지 (None 이면 이후 등장 값으로 승격).
        if agg["name"] is None and name is not None:
            agg["name"] = name
        if agg["price_asof"] is None and price_asof is not None:
            agg["price_asof"] = price_asof
        if eval_amt is not None:
            agg["eval_sum"] += float(eval_amt)
            agg["has_eval"] = True

    scored: list[tuple[str, Optional[str], Optional[str], float]] = []
    manual_review: list[tuple[str, Optional[str], Optional[str]]] = []
    for ticker, agg in per_ticker.items():
        if agg["has_eval"]:
            scored.append(
                (ticker, agg["name"], agg["price_asof"], float(agg["eval_sum"]))
            )
        else:
            manual_review.append((ticker, agg["name"], agg["price_asof"]))
    scored.sort(key=lambda x: (-x[3], x[0]))
    return scored, manual_review


def _pick_market_candidates(topn_payload: dict[str, Any]) -> list[tuple]:
    """(rank, ticker, name) 순서로 최대 MARKET_MAX 후보 반환. 기존 순위 유지.

    검증자 REJECTED r7 재정정: 손상된 candidate (dict 아님, ticker 문자열 아님,
    rank 캐스팅 실패 등) 는 sanitized 예외로 승격 (BootstrapSourceError).
    호출자가 partial 로 처리하도록 유도 · AttributeError 전파 X.
    """
    candidates = topn_payload.get("candidates") or []
    if not isinstance(candidates, list):
        raise BootstrapSourceError(_ERROR_REASON_MARKET_SOURCE)
    out: list[tuple[int, str, Optional[str]]] = []
    # 검증자 REJECTED r8 재정정: Market Discovery 내부 ticker 중복 제거 (§9 계약).
    seen_tickers: set[str] = set()
    for i, c in enumerate(candidates):
        if not isinstance(c, dict):
            raise BootstrapSourceError(_ERROR_REASON_MARKET_SOURCE)
        ticker = c.get("ticker")
        if ticker is None:
            continue
        if not isinstance(ticker, str) or not ticker.strip():
            raise BootstrapSourceError(_ERROR_REASON_MARKET_SOURCE)
        rank_raw = c.get("rank")
        try:
            rank = int(rank_raw) if rank_raw is not None else (len(out) + 1)
        except (TypeError, ValueError):
            raise BootstrapSourceError(_ERROR_REASON_MARKET_SOURCE)
        name = c.get("name")
        if name is not None and not isinstance(name, str):
            raise BootstrapSourceError(_ERROR_REASON_MARKET_SOURCE)
        if ticker in seen_tickers:
            # Market Discovery 내부 중복: 첫 등장만 유지.
            continue
        seen_tickers.add(ticker)
        out.append((rank, ticker, name))
        if len(out) >= MARKET_MAX:
            break
    return out


# Sanitized error_reason (§10.1: 내부 reason code / 파일 경로 · 예외 클래스명 노출 금지).
# CLI stdout / proposal 결과에 노출되는 값은 사용자용 축약 사유만.
_ERROR_REASON_HOLDINGS_SOURCE = "holdings_source_unavailable"
_ERROR_REASON_MARKET_SOURCE = "market_discovery_source_unavailable"
_ERROR_REASON_BOTH_EMPTY = "both_sources_empty"
_ERROR_REASON_NO_CANDIDATES = "no_candidates_after_deduplication"


class BootstrapSourceError(RuntimeError):
    """Canonical source 조회 실패 — proposal 생성 불가 (지시문 §10.2).

    예외 message 는 sanitized 상수 사용 (내부 exception 클래스명 · path 노출 X).
    """


def _load_holdings_and_enrich(
    holdings_loader,
    market_quotes_loader,
    etf_ticker_loader,
) -> tuple[list[tuple], list[tuple], Optional[str], set[str]]:
    """Holdings + market_cache + etf_master canonical 조회.

    각 canonical source 실패는 BootstrapSourceError 로 승격 (broad except 삼킴 금지).
    반환: (ranked, manual_review, asof, etf_ticker_set).
    """
    from app.holdings_enrich import enrich_holdings

    # canonical source 각각을 명시적으로 시도. 실패 시 sanitized error_reason 승격
    # (내부 exception class 명 · path 노출 X, §10.1).
    try:
        holdings = holdings_loader()
    except Exception as e:  # noqa: BLE001
        raise BootstrapSourceError(_ERROR_REASON_HOLDINGS_SOURCE) from e
    try:
        market_quotes = market_quotes_loader()
    except Exception as e:  # noqa: BLE001
        raise BootstrapSourceError(_ERROR_REASON_HOLDINGS_SOURCE) from e
    try:
        etf_ticker_set = set(etf_ticker_loader())
    except Exception as e:  # noqa: BLE001
        raise BootstrapSourceError(_ERROR_REASON_HOLDINGS_SOURCE) from e

    enriched = enrich_holdings(holdings, market_quotes)
    ranked, manual = _rank_holdings_by_eval(enriched, etf_ticker_set)
    asof_candidates = [r[2] for r in ranked if r[2] is not None] + [
        m[2] for m in manual if m[2] is not None
    ]
    asof_value = max(asof_candidates) if asof_candidates else None
    return ranked, manual, asof_value, etf_ticker_set


def _load_market_discovery(
    topn_fn, market_db_path
) -> tuple[list[tuple], Optional[str]]:
    """Market Discovery canonical 조회.

    reader 자체 예외는 BootstrapSourceError 로 승격. status != "ok" 는 정상 상태
    (실측된 반환 계약) 로 처리 — 후보 없이 asof None 반환.
    """
    try:
        kwargs = {"db_path": market_db_path} if market_db_path is not None else {}
        payload = topn_fn(**kwargs)
    except Exception as e:  # noqa: BLE001
        raise BootstrapSourceError(_ERROR_REASON_MARKET_SOURCE) from e
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        return [], None
    asof = payload.get("asof")
    return _pick_market_candidates(payload), asof


def build_bootstrap_proposal(
    *,
    holdings_loader: Optional[Callable[[], list]] = None,
    market_quotes_loader: Optional[Callable[[], dict]] = None,
    etf_ticker_loader: Optional[Callable[[], list]] = None,
    topn_fn: Optional[Callable[..., dict]] = None,
    market_db_path=None,
) -> ProposalResult:
    """Bootstrap 후보 제안 조립 (지시문 §6~§9).

    실패 처리 (§10.2 재정정):
    - canonical source 중 하나라도 실행 자체 실패 → status=partial, publishable_proposal=False.
    - 정상 실행 결과가 양쪽 모두 비면 → status=partial, publishable_proposal=False.
    - 최소 하나 이상 후보 존재 → status=ok, publishable_proposal=True.
    """
    if holdings_loader is None:
        from app.holdings import load as _load

        holdings_loader = _load
    if market_quotes_loader is None:
        from app.market_cache import get_all as _get_all

        market_quotes_loader = _get_all
    if etf_ticker_loader is None:
        from app.market_data_store import list_etf_tickers as _list_etf

        etf_ticker_loader = _list_etf
    if topn_fn is None:
        from app.market_topn import compute_topn as _compute

        topn_fn = _compute

    # 각 canonical source 실행. 실패 시 명확한 error_reason 으로 partial 반환.
    try:
        ranked, manual_review, holdings_asof, _etf_set = _load_holdings_and_enrich(
            holdings_loader, market_quotes_loader, etf_ticker_loader
        )
    except BootstrapSourceError as e:
        return ProposalResult(
            status="partial",
            holdings_asof=None,
            market_discovery_asof=None,
            holding_candidates_available=False,
            market_candidates_available=False,
            proposals=[],
            error_reason=str(e),
            publishable_proposal=False,
        )

    try:
        market_ranked, market_asof = _load_market_discovery(topn_fn, market_db_path)
    except BootstrapSourceError as e:
        return ProposalResult(
            status="partial",
            holdings_asof=holdings_asof,
            market_discovery_asof=None,
            holding_candidates_available=False,
            market_candidates_available=False,
            proposals=[],
            error_reason=str(e),
            publishable_proposal=False,
        )

    holdings_available = bool(ranked or manual_review)
    market_available = bool(market_ranked and market_asof)

    # 두 범주 모두 비면 partial (§10.2).
    if not holdings_available and not market_available:
        return ProposalResult(
            status="partial",
            holdings_asof=holdings_asof,
            market_discovery_asof=market_asof,
            holding_candidates_available=False,
            market_candidates_available=False,
            proposals=[],
            error_reason=_ERROR_REASON_BOTH_EMPTY,
            publishable_proposal=False,
        )

    picked_holdings = ranked[:HOLDING_MAX]
    picked_market = market_ranked[:MARKET_MAX]

    holding_tickers = {t for (t, _n, _a, _e) in picked_holdings}
    market_ticker_set = {t for (_r, t, _n) in picked_market}
    both = holding_tickers & market_ticker_set

    proposals: list[ProposedCandidate] = []

    for h_rank, (ticker, name, price_asof, _eval_amt) in enumerate(
        picked_holdings, start=1
    ):
        market_rank = None
        source = PROPOSAL_SOURCE_HOLDING
        if ticker in both:
            for m_rank, m_ticker, _m_name in picked_market:
                if m_ticker == ticker:
                    market_rank = m_rank
                    break
            source = PROPOSAL_SOURCE_BOTH
        proposals.append(
            ProposedCandidate(
                ticker=ticker,
                name=name,
                proposal_source=source,
                proposal_reason=HOLDING_REASON_TEXT,
                holding_rank=h_rank,
                market_discovery_rank=market_rank,
                data_asof=price_asof or holdings_asof,
            )
        )

    market_only_added = 0
    market_slot_target = min(MARKET_MAX, len(market_ranked))
    for m_rank, ticker, name in market_ranked:
        if ticker in holding_tickers:
            continue
        if market_only_added >= market_slot_target:
            break
        if len(proposals) >= TOTAL_MAX:
            break
        proposals.append(
            ProposedCandidate(
                ticker=ticker,
                name=name,
                proposal_source=PROPOSAL_SOURCE_MARKET,
                proposal_reason=MARKET_REASON_TEXT,
                holding_rank=None,
                market_discovery_rank=m_rank,
                data_asof=market_asof,
            )
        )
        market_only_added += 1

    for ticker, name, price_asof in manual_review:
        if len(proposals) >= TOTAL_MAX:
            break
        if any(p.ticker == ticker for p in proposals):
            continue
        proposals.append(
            ProposedCandidate(
                ticker=ticker,
                name=name,
                proposal_source=PROPOSAL_SOURCE_MANUAL_REVIEW,
                proposal_reason=HOLDING_MANUAL_REVIEW_REASON,
                holding_rank=None,
                market_discovery_rank=None,
                data_asof=price_asof or holdings_asof,
            )
        )

    if proposals:
        return ProposalResult(
            status="ok",
            holdings_asof=holdings_asof,
            market_discovery_asof=market_asof,
            holding_candidates_available=holdings_available and bool(picked_holdings),
            market_candidates_available=market_available and bool(picked_market),
            proposals=proposals,
            error_reason=None,
            publishable_proposal=True,
        )
    return ProposalResult(
        status="partial",
        holdings_asof=holdings_asof,
        market_discovery_asof=market_asof,
        holding_candidates_available=holdings_available,
        market_candidates_available=market_available,
        proposals=[],
        error_reason=_ERROR_REASON_NO_CANDIDATES,
        publishable_proposal=False,
    )
