"""POC6-32 r1 F1 — 고른 후보 하나의 저장 자료를 **한 번** 읽는다(읽기 전용 · 한 읽기 트랜잭션).

한 주간 응답의 ③ R1 구성 요약 · R4 보유 겹침(노출 계산) · 복사 글 · 넘기기 묶음(구성 · 겹침 · 자료 상태)이 같은 구성 ·
같은 원천일 확인 기록 · 같은 ETF 목록을 쓰게 한다(검증자 r1 F1 — 구성 요약과 노출 계산이 따로 읽어, 그 사이 같은
구성일 저장본이 바뀌면 요약은 주식 A · 노출은 주식 B 로 계산돼 응답 · 복사 글 · 저장 기록에 섞였다).
- 보유 파일 · 시세 캐시(파일)를 먼저 읽는다(기존 `constituents_pair_exposure_io.load` 와 같은 읽기 · 같은 실패 처리).
- 시장 DB 는 `mode=ro` 연결 하나에서 BEGIN 뒤 ETF 목록 → 후보 + 보유 쪽 ETF 의 구성 · 원천일 확인 기록 → (후보에
  원천일 확인 구성이 없을 때만) 후보의 저장 최신 구성 순으로 읽는다. 구성 요약 · 노출은 이 메모리 사본으로만 계산한다.
- 시장 DB 파일이 없으면 열지 않는다(만들지 않음) — 구성 = 미수집 · ETF 목록 없음(기존 읽기와 같은 결과).
- 노출 = 기존 `constituents_pair_exposure.build`(계산 · 지문 변경 없음) · 구성 요약 = `weekly_candidate_review`.
- 시장 DB 읽기 실패 = 구성 · 노출 모두 '읽지 못함'(같은 읽기라 한쪽만 성공하지 않음 · '없음'으로 바꾸지 않음).
「ETF 구성종목」 한 ETF 모드(`GET /market/constituents/summary`)도 같은 함수로 구성 요약만 읽는다(보유 쪽 읽지 않음).
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Mapping, Optional

from app import holdings, holdings_capital, market_cache
from app import weekly_candidate_review as wcr
from app.constituents_pair_exposure import build, holding_weights
from app.constituents_pair_exposure_io import master_in
from app.etf_constituents_status import analysis_rows_in, read_snapshots, snapshots_in
from app.holdings_enrich import enrich_holdings

READ_ERRORS = (sqlite3.Error, OSError, ValueError, KeyError)


def _holdings_side() -> tuple[Optional[list[Any]], Any, bool]:
    """(보유 행 + 시세 · 보유 파일을 못 읽으면 None, 보유 평가 기준일, 시세 · 평가 읽기 실패)."""
    try:
        rows = holdings.load()
    except (OSError, ValueError, holdings.HoldingsValidationError):
        # 보유 파일을 못 읽음 = 노출 계산이 '보유 목록을 읽지 못함'으로 보임(기존 `load` 와 같음)
        return None, None, False
    try:
        quotes = market_cache.get_all()
        enriched = enrich_holdings(
            rows, {h.ticker: quotes[h.ticker] for h in rows if h.ticker in quotes}
        )
        return enriched, holdings_capital.view(enriched, {})["price_date"], False
    except READ_ERRORS:
        return None, None, True


def _read_db(
    db_path: Path, candidate: str, enriched: Optional[list[Any]]
) -> tuple[Any, dict[str, Any], Any, Any]:
    """(ETF 목록, 구성 · 확인 기록 묶음, 후보 저장 최신 구성, 보유 비중) — 한 읽기 트랜잭션."""
    p = Path(db_path)

    def weights(master: Any) -> Any:
        return (
            None
            if enriched is None
            else holding_weights(enriched, master[1] if master else set())
        )

    def tickers(hw: Any) -> list[str]:
        return [
            candidate,
            *(it["ticker"] for it in (hw or {}).get("items", []) if it["etf"]),
        ]

    if not p.exists():
        # 파일이 없으면 열지 않음(만들지 않음 · 기존 읽기와 같은 빈 결과)
        hw = weights(None)
        return None, read_snapshots(tickers(hw), db_path=p), None, hw
    with closing(sqlite3.connect(f"file:{p}?mode=ro", uri=True)) as con:
        # 아래 읽기 모두 같은 시점(공유 잠금 유지 · 사이에 끼어든 저장은 보이지 않음)
        con.execute("BEGIN")
        master = master_in(con)
        hw = weights(master)
        snaps = snapshots_in(con, tickers(hw))
        latest = None
        if not (snaps.get(candidate) or {}).get("confirmed"):
            dates, data = analysis_rows_in(con, [candidate], asof=None)
            if candidate in data:
                latest = (dates[candidate], *data[candidate])
    return master, snaps, latest, hw


def read_candidate(
    candidate: str,
    *,
    db_path: Path,
    condition: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """고른 후보 → {names, constituents, exposure, exposure_error}.

    `names` = ETF 목록의 이름(못 읽으면 None · 공식 기준정보의 개별 주식 판별에 씀) · `constituents` = 구성 요약
    전체(`weekly_candidate_review.detail_of` 모양 · 저장 행 · 집중 포함) · `exposure` = 노출 계산 응답(`condition` 이
    없으면 계산 안 함 · 보유 쪽도 읽지 않음) · `exposure_error` = 노출을 계산하지 못함(읽기 · 계산 실패)."""
    side = _holdings_side() if condition is not None else (None, None, False)
    enriched, price_date, side_failed = side
    try:
        master, snaps, latest, hw = _read_db(db_path, candidate, enriched)
    except READ_ERRORS:
        return {
            "names": None,
            "constituents": wcr.error_detail(),
            "exposure": None,
            "exposure_error": condition is not None,
        }
    names, etf_tickers = master or (None, None)
    out: dict[str, Any] = {
        "names": names,
        "constituents": wcr.constituents_of(snaps.get(candidate), latest, etf_tickers),
        "exposure": None,
        "exposure_error": side_failed,
    }
    if condition is None or side_failed:
        return out
    try:
        out["exposure"] = build(
            candidate=candidate,
            holding=None,
            condition=condition,
            hw=hw,
            price_date=price_date,
            names=names or {},
            etf_tickers=etf_tickers or set(),
            snaps=snaps,
        )
    except (ValueError, KeyError):
        out["exposure_error"] = True
    return out
