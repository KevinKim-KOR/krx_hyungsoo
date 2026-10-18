"""POC5-23 — 판단 근거 미리보기의 자료 모으기(읽기 전용).

설계 `docs/ai_design/POC5/POC5-23_SELECTED_ETF_DECISION_EVIDENCE_PREVIEW_DESIGN_V1.md` §3 · §4 ·
판정 `..._PLAN_DECISION_2026-10-18.md` §1 · §2.

- 보유 = 화면(「보유와 비교」 · 「확인 근거」)이 쓰는 `get_holdings_market_evidence_latest()` 응답에서
  그 종목의 첫 항목(같은 종목 여러 계좌는 시장 값이 같다) · 국면 · PC 비교 기준일.
- 후보 = 화면(「요즘 잘 오르는 ETF」)이 쓰는 `get_market_topn_latest(화면과 같은 목록 조건)` 응답에서 그 종목.
  화면에 없는 거래량 · 가격 흔들림은 선택 1종목의 저장 창만 읽어 POC5-09 · 16 함수 그대로 만든다(판정 Q2 (a)).
- 후보 ↔ 보유 ETF 구성종목 중복 = 「ETF 구성종목」 분석의 쌍 계산(`compute_pair_overlap`) · 종목마다 마지막
  저장 구성종목(판정 Q3 (b) · §2). 자료 없는 쌍은 계산하지 않는다(0% 아님).

외부 조회 · 저장 · 수집 없음. 공유 builder · 두 화면 API 의 출력은 바꾸지 않는다(부르기만 한다).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from app.api_holdings_market_evidence import get_holdings_market_evidence_latest
from app.api_market_topn import get_market_topn_latest
from app.etf_constituents_analysis import (
    DEFAULT_TOP_K_FOR_OVERLAP,
    compute_pair_overlap,
)
from app.etf_constituents_store import fetch_constituents, latest_constituent_asof
from app.holdings import HoldingsValidationError, load as load_holdings
from app.market_data_store import DEFAULT_DB_PATH, list_etf_tickers
from app.market_topn import DEFAULT_BASIS, DEFAULT_N, DEFAULT_ORDER
from app.pc_price_basis import load_recent_price_rows
from app.pc_price_volatility import build_price_volatility
from app.short_term_momentum import KODEX200_TICKER
from app.stored_volume_evidence import compute_stored_volume_evidence

ALLOWED_BASES = ("daily", "one_month", "three_month")
ALLOWED_ORDERS = ("desc", "asc")
MAX_N = 200  # 화면 API 와 같은 상한(`GET /market/topn/latest` n ≤ 200)


class CandidateListUnavailable(Exception):
    """화면 시장 목록 계산 자체가 실패(status ≠ ok) — '목록에 없음'과 구분한다."""


@dataclass(frozen=True)
class CandidateListQuery:
    """화면 후보 목록 조건(판정 Q1 (a)). 요청에 없으면 기존 기본 조건."""

    n: int = DEFAULT_N
    basis: str = DEFAULT_BASIS
    order: str = DEFAULT_ORDER
    exclude_inverse: bool = True
    exclude_leveraged: bool = True
    exclude_synthetic: bool = True
    exclude_futures: bool = True

    def is_valid(self) -> bool:
        return (
            self.basis in ALLOWED_BASES
            and self.order in ALLOWED_ORDERS
            and 1 <= self.n <= MAX_N
        )


def _etf_tickers(db_path: Path) -> set[str]:
    # 개별 종목 판별 = `etf_master` 에 없음(POC5-10 보유 개별주 수집과 같은 기준).
    return set(list_etf_tickers(db_path=db_path))


def load_holding_bundle(
    ticker: str, *, db_path: Path = DEFAULT_DB_PATH
) -> Optional[dict[str, Any]]:
    """보유 종목 하나의 화면 근거(PC 근거 사본) — 응답에 그 종목이 없으면 None."""
    evidence = get_holdings_market_evidence_latest()
    item = next((h for h in evidence.holdings if h.ticker == ticker), None)
    if item is None:
        return None
    is_etf = ticker in _etf_tickers(db_path)
    overlap = item.constituents_overlap
    return {
        "item": item.model_dump(),
        "is_etf": is_etf,
        "market_position": (evidence.judgment_summary or {}).get("market_position"),
        "reference_date": (
            evidence.price_basis.reference_date if evidence.price_basis else None
        ),
        # 겹침을 계산한 구성종목 저장일(builder 와 같은 `latest_constituent_asof` · 응답에는 없는 값).
        "constituents_asof": (
            latest_constituent_asof(ticker, db_path=db_path)
            if is_etf and overlap.status == "ok"
            else None
        ),
    }


def _candidate_overlap(
    candidate: str,
    held_etfs: list[tuple[str, Optional[str]]],
    *,
    db_path: Path,
) -> dict[str, Any]:
    """후보 ↔ 보유 ETF 쌍마다 「ETF 구성종목」 분석과 같은 중복 계산(상위 10건 · 저장 자료만)."""
    c_asof = latest_constituent_asof(candidate, db_path=db_path)
    c_rows = (
        fetch_constituents(etf_ticker=candidate, asof=c_asof, db_path=db_path)
        if c_asof
        else []
    )
    out: dict[str, Any] = {
        "candidate_asof": c_asof if c_rows else None,
        "candidate_available": bool(c_rows),
        "held_etf_count": len(held_etfs),
        "pairs": [],
        "missing": [],
    }
    if not c_rows:
        return out  # 후보 자료가 없으면 어떤 쌍도 계산하지 않는다(보유 쪽도 읽지 않음).
    for tk, name in held_etfs:
        h_asof = latest_constituent_asof(tk, db_path=db_path)
        h_rows = (
            fetch_constituents(etf_ticker=tk, asof=h_asof, db_path=db_path)
            if h_asof
            else []
        )
        if not h_rows:
            out["missing"].append({"ticker": tk, "name": name})
            continue
        pair = compute_pair_overlap(c_rows, h_rows, top_k=DEFAULT_TOP_K_FOR_OVERLAP)
        out["pairs"].append({"ticker": tk, "name": name, "asof": h_asof, **pair})
    return out


def load_candidate_bundle(
    ticker: str,
    query: CandidateListQuery,
    *,
    db_path: Path = DEFAULT_DB_PATH,
) -> Optional[dict[str, Any]]:
    """후보 하나의 화면 근거 + 선택 1종목 추가 읽기 — 그 조건의 목록에 없으면 None."""
    resp = get_market_topn_latest(
        n=query.n,
        basis=query.basis,  # type: ignore[arg-type]
        order=query.order,  # type: ignore[arg-type]
        exclude_inverse=query.exclude_inverse,
        exclude_leveraged=query.exclude_leveraged,
        exclude_synthetic=query.exclude_synthetic,
        exclude_futures=query.exclude_futures,
    )
    if resp.status != "ok":
        raise CandidateListUnavailable(resp.status)
    cand = next((c for c in resp.candidates if c.ticker == ticker), None)
    if cand is None:
        return None

    # 「확인 근거」와 같은 읽기 · 같은 날짜 정의(pc_price_basis: 같은 읽기의 첫 행 = 끝 날짜).
    rows = load_recent_price_rows([ticker], db_path=db_path)
    mine = rows[ticker]
    reference_date = rows[KODEX200_TICKER][0][0] if rows[KODEX200_TICKER] else None
    end_date = mine[0][0] if mine else None
    volatility = build_price_volatility(
        [{"ticker": ticker, "price_dates": {"end_date": end_date}}],
        reference_date=reference_date,
        db_path=db_path,
    )[ticker]

    direct: Optional[dict[str, Any]] = None
    overlap: Optional[dict[str, Any]] = None
    try:
        holdings = load_holdings()
    except (OSError, ValueError, HoldingsValidationError):
        # 보유 파일 손상 — 직접 보유 · 중복만 '확인 불가'로 두고 나머지 묶음은 제공한다(빈 보유로 보지 않음).
        holdings = None
    if holdings is not None:
        etfs = _etf_tickers(db_path)
        names: dict[str, Optional[str]] = {}
        for h in holdings:
            names.setdefault(h.ticker, h.name)
        direct = {"held": ticker in names, "name": names.get(ticker)}
        held_etfs = [
            (tk, nm) for tk, nm in names.items() if tk in etfs and tk != ticker
        ]
        overlap = _candidate_overlap(ticker, held_etfs, db_path=db_path)

    return {
        "candidate": cand.model_dump(),
        "market_context": (
            resp.market_context.model_dump() if resp.market_context else None
        ),
        "basis": query.basis,
        "order": query.order,
        "reference_date": reference_date,
        "end_date": end_date,
        "stored_volume": compute_stored_volume_evidence(ticker, mine).model_dump(),
        "price_volatility": volatility.model_dump(),
        "direct_holding": direct,
        "overlap": overlap,
    }
