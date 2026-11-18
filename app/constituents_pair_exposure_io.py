"""보유와 후보의 구성종목 비교 — 저장 자료 읽기(POC6-31 STEP 4 · 계산은 `constituents_pair_exposure.build`).

ETF 목록 · 등록 보유 · 시세 캐시 · 구성 자료(원천일 확인 · 한 읽기 트랜잭션)를 읽어 계산 함수에 넘긴다. 읽기만 ·
외부 호출 0. 계산 모듈이 KS-10(백엔드 핵심 모듈 650줄)을 넘지 않게 읽기 부분만 따로 둔다(검증자 STEP 4~5 r1 B-3).
화면 GET(`/market/constituents/pair-exposure`)과 판단 근거 미리보기가 같은 `load` 를 부른다(지문 대조 · C25).
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Mapping, Optional

from app.constituents_pair_exposure import build, holding_weights
from app.etf_constituents_status import read_snapshots


def read_etf_master(
    db_path: Path,
) -> Optional[tuple[dict[str, Optional[str]], set[str]]]:
    """({ETF 코드: 이름}, ETF 코드 집합) — DB · 표가 없거나 잠겨 못 읽거나 비면 None(빈 목록과 구분 · backend#5)."""
    p = Path(db_path)
    if not p.exists():
        return None
    try:
        with closing(sqlite3.connect(f"file:{p}?mode=ro", uri=True)) as con:
            return master_in(con)
    except sqlite3.Error:
        return None


def master_in(
    con: sqlite3.Connection,
) -> Optional[tuple[dict[str, Optional[str]], set[str]]]:
    """`read_etf_master` 의 읽기 본문 — 부르는 쪽이 연 연결(읽기 트랜잭션) 안에서(POC6-32 r1 F1). 표가 없거나 못 읽거나
    비면 None(빈 목록과 구분)."""
    try:
        rows = con.execute("SELECT ticker, name FROM etf_master").fetchall()
    except sqlite3.Error:
        return None
    if not rows:
        return None
    return {t: n for t, n in rows}, {t for t, _ in rows}


def load(
    candidate: str,
    holding: Optional[str],
    condition: Mapping[str, Any],
    *,
    db_path: Path,
) -> dict[str, Any]:
    """저장 자료를 읽어 `build`(보유 파일 · 시세 캐시 · 시장 DB 읽기만)."""
    from app import holdings_capital, market_cache
    from app.holdings import HoldingsValidationError, load as load_holdings
    from app.holdings_enrich import enrich_holdings

    names, etf_tickers = read_etf_master(db_path) or ({}, set())
    hw = price_date = None
    try:
        rows = load_holdings()
    except (OSError, ValueError, HoldingsValidationError):
        rows = None
    if rows is not None:
        quotes = market_cache.get_all()
        enriched = enrich_holdings(
            rows, {h.ticker: quotes[h.ticker] for h in rows if h.ticker in quotes}
        )
        hw = holding_weights(enriched, etf_tickers)
        price_date = holdings_capital.view(enriched, {})["price_date"]
    tks = [
        candidate,
        *(it["ticker"] for it in (hw or {}).get("items", []) if it["etf"]),
    ]
    if holding and holding in etf_tickers:
        tks.append(holding)
    snaps = read_snapshots(tks, db_path=db_path)
    return build(
        candidate=candidate,
        holding=holding or None,
        condition=condition,
        hw=hw,
        price_date=price_date,
        names=names,
        etf_tickers=etf_tickers,
        snaps=snaps,
    )
