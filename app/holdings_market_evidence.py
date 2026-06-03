"""POC2 — Holdings × Market Discovery Evidence 1차 (2026-06-03).

지시문 §5 — 사용자 실제 holdings 를 Market Discovery evidence 와 연결한
read-only evidence builder.

핵심 원칙 (지시문 §6 / §11):
- 외부 source 호출 0건. SQLite read + store read 만.
- 매수 / 매도 / 교체 판단 0건. "현재 후보 안에 있는가" 등 raw evidence 만.
- 보유 ETF 구성종목 외부 source 신규 호출 X (Strict Cache-only, 지시문 §5.8).
- NAV source 신규 채택 X (기존 unavailable 흐름 유지).
- 데이터 부족 시 0 대체 X — unavailable status.

본 모듈은 `GET /holdings/market-evidence/latest` 와 GenerateDraft 흐름이 같이
재사용한다 (지시문 §5.10 — backend evidence builder 단일화).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.etf_constituents_analysis import compute_repeated_core_holdings
from app.etf_constituents_store import (
    ConstituentRow,
    fetch_constituents,
    latest_constituent_asof,
)
from app.etf_nav_fetcher import classify_discount_flag
from app.etf_nav_store import DEFAULT_DB_PATH as NAV_DEFAULT_DB_PATH, fetch_latest_nav
from app.holdings import Holding
from app.holdings_enrich import enrich_holdings
from app.market_cache import MarketQuote
from app.short_term_momentum import compute_short_term_momentum_batch

# 본 모듈은 외부 fetch 를 절대 트리거하지 않는다 — 호출자가 market_quotes 를
# 미리 캐시에서 채워 넘긴다 (api 라우트가 책임).

TOPN_MATCH_MATCHED = "matched_topn_candidate"
TOPN_MATCH_NOT_IN_TOPN = "not_in_current_topn"
TOPN_MATCH_UNAVAILABLE = "unavailable"

STATUS_OK = "ok"
STATUS_UNAVAILABLE = "unavailable"
STATUS_PARTIAL = "partial"
STATUS_WARNING = "warning"

CONSTITUENTS_OK = "ok"
CONSTITUENTS_UNAVAILABLE = "constituents_unavailable"
MARKET_CORE_UNAVAILABLE = "market_core_unavailable"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_topn_match(
    holding_ticker: str,
    topn_status: str,
    topn_basis: Optional[str],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """보유 ETF 가 현재 Market Discovery 후보 목록에 있는지 표시.

    지시문 §5.3 / §5.5:
    - matched_topn_candidate / not_in_current_topn / unavailable.
    - 매수/매도/교체 의미가 아니다.
    """
    if topn_status != "ok":
        return {
            "status": TOPN_MATCH_UNAVAILABLE,
            "rank": None,
            "basis": topn_basis,
            "candidate_name": None,
        }
    for c in candidates:
        if c.get("ticker") == holding_ticker:
            return {
                "status": TOPN_MATCH_MATCHED,
                "rank": c.get("rank"),
                "basis": topn_basis,
                "candidate_name": c.get("name"),
            }
    return {
        "status": TOPN_MATCH_NOT_IN_TOPN,
        "rank": None,
        "basis": topn_basis,
        "candidate_name": None,
    }


def _build_returns_and_excess(
    matched_candidate: Optional[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """matched candidate 의 returns + excess_return 을 evidence payload 로 옮긴다.

    candidate match 가 없거나 candidate 의 1m/3m 값이 모두 누락이면 unavailable.
    지시문 §5.6 — 데이터 부족 시 0 대체 X.
    """
    if matched_candidate is None:
        return (
            {
                "status": STATUS_UNAVAILABLE,
                "one_month_return_pct": None,
                "three_month_return_pct": None,
            },
            {
                "status": STATUS_UNAVAILABLE,
                "vs_kodex200_1m_pctp": None,
                "vs_kodex200_3m_pctp": None,
            },
        )

    returns_block = matched_candidate.get("returns") or {}
    one_m = (returns_block.get("one_month") or {}).get("return_pct")
    three_m = (returns_block.get("three_month") or {}).get("return_pct")
    if one_m is None and three_m is None:
        returns_payload = {
            "status": STATUS_UNAVAILABLE,
            "one_month_return_pct": None,
            "three_month_return_pct": None,
        }
    elif one_m is not None and three_m is not None:
        returns_payload = {
            "status": STATUS_OK,
            "one_month_return_pct": one_m,
            "three_month_return_pct": three_m,
        }
    else:
        returns_payload = {
            "status": STATUS_PARTIAL,
            "one_month_return_pct": one_m,
            "three_month_return_pct": three_m,
        }

    excess_block = matched_candidate.get("excess_return") or {}
    e1m = excess_block.get("vs_kodex200_1m_pctp")
    e3m = excess_block.get("vs_kodex200_3m_pctp")
    if e1m is None and e3m is None:
        excess_payload = {
            "status": STATUS_UNAVAILABLE,
            "vs_kodex200_1m_pctp": None,
            "vs_kodex200_3m_pctp": None,
        }
    elif e1m is not None and e3m is not None:
        excess_payload = {
            "status": STATUS_OK,
            "vs_kodex200_1m_pctp": e1m,
            "vs_kodex200_3m_pctp": e3m,
        }
    else:
        excess_payload = {
            "status": STATUS_PARTIAL,
            "vs_kodex200_1m_pctp": e1m,
            "vs_kodex200_3m_pctp": e3m,
        }

    return returns_payload, excess_payload


def _build_short_term_payload(stm_result: Any) -> dict[str, Any]:
    """ShortTermMomentum dataclass → evidence payload dict.

    None / 없음 → status=unavailable.
    """
    if stm_result is None:
        return {
            "status": STATUS_UNAVAILABLE,
            "return_5d_pct": None,
            "return_10d_pct": None,
            "return_20d_pct": None,
            "excess_vs_kodex200_5d_pctp": None,
            "excess_vs_kodex200_10d_pctp": None,
            "excess_vs_kodex200_20d_pctp": None,
        }
    return {
        "status": stm_result.status,
        "return_5d_pct": stm_result.return_5d_pct,
        "return_10d_pct": stm_result.return_10d_pct,
        "return_20d_pct": stm_result.return_20d_pct,
        "excess_vs_kodex200_5d_pctp": stm_result.excess_vs_kodex200_5d_pctp,
        "excess_vs_kodex200_10d_pctp": stm_result.excess_vs_kodex200_10d_pctp,
        "excess_vs_kodex200_20d_pctp": stm_result.excess_vs_kodex200_20d_pctp,
    }


def _build_market_core_repeated_lookup(
    candidates: list[dict[str, Any]],
    topn_status: str,
    *,
    db_path: Path,
) -> Optional[dict[str, dict[str, Any]]]:
    """현재 Market Discovery 후보들의 반복 핵심 종목 lookup 생성 (Strict Cache-only).

    각 후보의 latest_constituent_asof 로 cache 조회. cache 가 없거나 후보가
    하나도 없으면 None (market_core_unavailable). 본 함수는 외부 fetch 0건.

    반환: { match_key → {ticker, name, market_core_count} }. compute_repeated_core_holdings
    의 결과를 match key (ticker 또는 정규화 name) 기준 dict 로 변환.
    """
    if topn_status != "ok" or not candidates:
        return None

    per_ticker_rows: dict[str, list[ConstituentRow]] = {}
    for c in candidates:
        tk = c.get("ticker")
        if not tk:
            continue
        cache_asof = latest_constituent_asof(tk, db_path=db_path)
        if cache_asof is None:
            continue
        rows = fetch_constituents(etf_ticker=tk, asof=cache_asof, db_path=db_path)
        if rows:
            per_ticker_rows[tk] = rows

    if not per_ticker_rows:
        return None

    repeated = compute_repeated_core_holdings(per_ticker_rows)
    if not repeated:
        # cache 는 있는데 반복 핵심 종목이 없는 경우. 비교 자체는 가능 → empty lookup.
        return {}

    # repeated 의 각 entry → match key 로 lookup table 구성. analysis 의 _match_key 와
    # 같은 정규화를 사용해야 하지만, 외부에 노출하지 않은 internal helper 라 여기서는
    # ticker 기준으로 1차 매칭. ticker 가 없으면 name 으로 2차 매칭.
    lookup: dict[str, dict[str, Any]] = {}
    for item in repeated:
        market_core_count = int(item.get("appears_in_etf_count") or 0)
        ticker = item.get("ticker") or None
        name = item.get("name") or None
        entry = {
            "ticker": ticker,
            "name": name,
            "market_core_count": market_core_count,
        }
        if ticker:
            lookup[f"T:{ticker}"] = entry
        if name:
            # name 기반 정규화는 _normalize_name 과 동일 결과를 얻기 어렵지만,
            # 본 STEP 에서는 ticker 매칭만으로 충분 (보유 ETF 구성종목 ticker 우선).
            lookup[f"N:{name.strip().lower()}"] = entry
    return lookup


def _build_constituents_overlap(
    holding_ticker: str,
    market_core_lookup: Optional[dict[str, dict[str, Any]]],
    *,
    db_path: Path,
) -> dict[str, Any]:
    """보유 ETF 구성종목 ∩ Market Discovery 반복 핵심 종목 (Strict Cache-only).

    지시문 §5.7 / §5.8 — Cache 에 없으면 constituents_unavailable. 외부 fetch X.
    """
    if market_core_lookup is None:
        return {
            "status": MARKET_CORE_UNAVAILABLE,
            "overlap_with_market_core": [],
        }
    cache_asof = latest_constituent_asof(holding_ticker, db_path=db_path)
    if cache_asof is None:
        return {
            "status": CONSTITUENTS_UNAVAILABLE,
            "overlap_with_market_core": [],
        }
    rows = fetch_constituents(
        etf_ticker=holding_ticker, asof=cache_asof, db_path=db_path
    )
    if not rows:
        return {
            "status": CONSTITUENTS_UNAVAILABLE,
            "overlap_with_market_core": [],
        }
    overlap: list[dict[str, Any]] = []
    for r in rows[:10]:  # top 10 만 비교 (DEFAULT_TOP_K_FOR_OVERLAP 정합).
        match: Optional[dict[str, Any]] = None
        if r.constituent_ticker:
            match = market_core_lookup.get(f"T:{r.constituent_ticker}")
        if match is None and r.constituent_name:
            match = market_core_lookup.get(f"N:{r.constituent_name.strip().lower()}")
        if match is None:
            continue
        overlap.append(
            {
                "ticker": r.constituent_ticker,
                "name": r.constituent_name,
                "weight_pct": r.weight_pct,
                "market_core_count": match.get("market_core_count"),
            }
        )
    return {
        "status": CONSTITUENTS_OK,
        "overlap_with_market_core": overlap,
    }


def _build_nav_payload(holding_ticker: str, *, db_path: Path) -> dict[str, Any]:
    """기존 etf_nav_daily store 에서 최신 row 1건 조회 (외부 fetch X).

    지시문 §5.9 — source 미연동이면 unavailable. NAV source 신규 채택 X.
    """
    row = fetch_latest_nav(etf_ticker=holding_ticker, db_path=db_path)
    if row is None:
        return {
            "status": STATUS_UNAVAILABLE,
            "source": "not_integrated",
            "asof": None,
            "nav": None,
            "market_price": None,
            "discount_rate_pct": None,
            "flag": None,
            "message": "NAV / discount source not integrated",
        }
    return {
        "status": row.status,
        "asof": row.asof,
        "nav": row.nav,
        "market_price": row.market_price,
        "discount_rate_pct": row.discount_rate_pct,
        "flag": classify_discount_flag(row.discount_rate_pct),
        "source": row.source,
        "message": row.message,
    }


def _build_evidence_notes(
    topn_match: dict[str, Any],
    short_term: dict[str, Any],
    constituents: dict[str, Any],
    nav_discount: dict[str, Any],
    *,
    holding_name: str,
    topn_n: Optional[int],
) -> list[str]:
    """status 조합 기반 자연어 evidence 메모 (지시문 §5.10 금지 표현 회피).

    매수/매도/교체/탈락 등 판단 어휘 사용 X. 데이터 상태만 기술.
    """
    notes: list[str] = []
    if topn_match["status"] == TOPN_MATCH_MATCHED:
        notes.append("현재 Market Discovery 후보와 일치합니다.")
    elif topn_match["status"] == TOPN_MATCH_NOT_IN_TOPN:
        if topn_n:
            notes.append(
                f"현재 Market Discovery TOP {topn_n} 후보에 포함되어 있지 않습니다."
            )
        else:
            notes.append("현재 Market Discovery 후보에 포함되어 있지 않습니다.")
    else:
        notes.append("현재 Market Discovery 후보 목록을 확인할 수 없습니다.")

    if short_term["status"] == STATUS_OK:
        excess_20d = short_term.get("excess_vs_kodex200_20d_pctp")
        if isinstance(excess_20d, (int, float)):
            if excess_20d >= 0:
                notes.append(
                    f"20거래일 KODEX200 대비 단기 흐름 차이 {excess_20d:+.2f}%p."
                )
            else:
                notes.append(
                    f"20거래일 KODEX200 대비 단기 흐름 차이 {excess_20d:+.2f}%p."
                )
    elif short_term["status"] == STATUS_UNAVAILABLE:
        notes.append("단기 흐름은 데이터 부족으로 확인할 수 없습니다.")

    if constituents["status"] == CONSTITUENTS_OK:
        overlap = constituents.get("overlap_with_market_core") or []
        if overlap:
            notes.append("구성종목 기준 현재 후보군의 반복 핵심 종목과 일부 겹칩니다.")
        else:
            notes.append(
                "구성종목 기준 현재 후보군의 반복 핵심 종목과 겹치는 항목이 없습니다."
            )
    elif constituents["status"] == CONSTITUENTS_UNAVAILABLE:
        notes.append("구성종목 데이터가 캐시에 없어 비교할 수 없습니다.")
    elif constituents["status"] == MARKET_CORE_UNAVAILABLE:
        notes.append("현재 후보군의 구성종목 데이터를 확인할 수 없습니다.")

    if nav_discount["status"] == STATUS_UNAVAILABLE:
        notes.append("NAV / 괴리율은 source 미연동으로 확인할 수 없습니다.")
    elif nav_discount.get("flag"):
        notes.append("NAV / 괴리율 확인이 필요합니다.")

    # holding_name 은 1줄 bullet 빌더가 활용. notes 본문에는 종목명 미반복.
    _ = holding_name
    return notes


def build_holdings_market_evidence(
    *,
    holdings: list[Holding],
    topn_payload: dict[str, Any],
    market_quotes: Optional[dict[str, MarketQuote]] = None,
    db_path: Path = NAV_DEFAULT_DB_PATH,
    holdings_asof: Optional[str] = None,
) -> dict[str, Any]:
    """보유 ETF × Market Discovery evidence (지시문 §5.2~§5.10).

    외부 fetch 0건. 모든 데이터는 호출자가 미리 채워 넘기거나 SQLite/store 에서 read.

    Parameters
    ----------
    holdings : list[Holding]
        검증된 holdings (validate_holdings 통과 후). 빈 list 도 허용 — 빈 응답 200.
    topn_payload : dict
        `compute_topn()` 의 raw 응답 dict. status 가 'ok' 가 아니면 모든 holdings 에
        대해 topn_match=unavailable + returns/excess_return=unavailable.
    market_quotes : dict[str, MarketQuote] | None
        보유 ETF 현재 시세 (캐시에서 미리 추출). evaluation_amount / pnl_rate
        표시용. None / 빈 dict 이면 holding.evaluation_amount = None.
    db_path : Path
        market_data.sqlite. NAV / constituents store 가 같은 파일을 사용.
    holdings_asof : str | None
        holdings_latest.json 의 갱신 시각 (ISO). 호출자가 측정.
    """
    market_quotes = market_quotes or {}
    enriched_list = enrich_holdings(holdings, market_quotes)
    enriched_by_ticker = {e.ticker: e for e in enriched_list}

    topn_status = topn_payload.get("status") or "missing"
    topn_basis = topn_payload.get("basis")
    market_asof = topn_payload.get("asof")
    topn_n = topn_payload.get("n")
    candidates = topn_payload.get("candidates") or []
    candidates_by_ticker = {c.get("ticker"): c for c in candidates if c.get("ticker")}

    # 단기 흐름 batch 1회 호출 — 보유 ETF tickers 만. KODEX200 시계열은 helper 가 1회만 fetch.
    holding_tickers = [h.ticker for h in holdings]
    stm_map = (
        compute_short_term_momentum_batch(holding_tickers, db_path=db_path)
        if holding_tickers
        else {}
    )

    # 반복 핵심 종목 lookup 은 후보 전체에 대해 1회 계산.
    market_core_lookup = _build_market_core_repeated_lookup(
        candidates, topn_status, db_path=db_path
    )

    summary = {
        "total_holdings_count": len(holdings),
        "matched_topn_count": 0,
        "not_in_current_topn_count": 0,
        "evidence_unavailable_count": 0,
        "constituents_available_count": 0,
        "constituents_unavailable_count": 0,
        "nav_discount_unavailable_count": 0,
    }

    holdings_out: list[dict[str, Any]] = []
    for h in holdings:
        e = enriched_by_ticker.get(h.ticker)
        matched_candidate = candidates_by_ticker.get(h.ticker)
        topn_match = _build_topn_match(h.ticker, topn_status, topn_basis, candidates)
        returns_payload, excess_payload = _build_returns_and_excess(matched_candidate)
        short_term = _build_short_term_payload(stm_map.get(h.ticker))
        constituents = _build_constituents_overlap(
            h.ticker, market_core_lookup, db_path=db_path
        )
        nav_discount = _build_nav_payload(h.ticker, db_path=db_path)
        notes = _build_evidence_notes(
            topn_match,
            short_term,
            constituents,
            nav_discount,
            holding_name=(h.display_name() if h else h.ticker),
            topn_n=topn_n,
        )

        # summary 집계.
        if topn_match["status"] == TOPN_MATCH_MATCHED:
            summary["matched_topn_count"] += 1
        elif topn_match["status"] == TOPN_MATCH_NOT_IN_TOPN:
            summary["not_in_current_topn_count"] += 1
        if (
            returns_payload["status"] == STATUS_UNAVAILABLE
            and short_term["status"] == STATUS_UNAVAILABLE
        ):
            summary["evidence_unavailable_count"] += 1
        if constituents["status"] == CONSTITUENTS_OK:
            summary["constituents_available_count"] += 1
        else:
            summary["constituents_unavailable_count"] += 1
        if nav_discount["status"] == STATUS_UNAVAILABLE:
            summary["nav_discount_unavailable_count"] += 1

        holdings_out.append(
            {
                "ticker": h.ticker,
                "name": h.display_name(),
                "account_group": getattr(h, "account_group", "일반"),
                "holding": {
                    "quantity": float(h.quantity),
                    "avg_buy_price": float(h.avg_buy_price),
                    "evaluation_amount": (e.eval_amount if e else None),
                    "pnl_rate_pct": (e.pnl_rate_pct if e else None),
                },
                "topn_match": topn_match,
                "returns": returns_payload,
                "excess_return": excess_payload,
                "short_term_momentum": short_term,
                "constituents_overlap": constituents,
                "nav_discount": nav_discount,
                "evidence_notes": notes,
            }
        )

    market_context = topn_payload.get("market_context")
    warnings: list[str] = []
    if topn_status != "ok":
        warnings.append(f"market_topn status={topn_status}")
    if market_core_lookup is None and topn_status == "ok" and candidates:
        warnings.append("market_core_constituents_unavailable")

    return {
        "status": "ok",
        "asof": market_asof or holdings_asof or _utcnow_iso(),
        "holdings_asof": holdings_asof,
        "market_asof": market_asof,
        "market_context": market_context,
        "summary": summary,
        "holdings": holdings_out,
        "warnings": warnings,
    }


def get_holdings_file_mtime_iso(path: Path) -> Optional[str]:
    """holdings_latest.json 파일 갱신 시각 (ISO). 파일 없으면 None.

    holdings 자체에는 asof 가 저장되지 않으므로 파일 mtime 으로 대용.
    응답 evidence 의 holdings_asof 표기용. 매매 결정에는 사용하지 않는다.
    """
    try:
        ts = path.stat().st_mtime
    except FileNotFoundError:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
