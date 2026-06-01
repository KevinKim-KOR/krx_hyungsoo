"""Naver source 통합 — service + store + analysis 흐름 검증 (POC2 — 2026-05-31).

지시문 §6.1 (referenceDate → asof) / §6.3 (해외 reuters/isin key) / §7
(constituent_key 등 4 컬럼 저장) / §11.2 (analysis 매칭 보정) 종합 검증.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.etf_constituents_analysis import compute_pair_overlap
from app.etf_constituents_fetcher import (
    FetchedConstituent,
    FetchResult,
    NAVER_STOCK_SOURCE,
)
from app.etf_constituents_service import refresh_constituents
from app.etf_constituents_store import (
    ConstituentRow,
    fetch_constituents,
    init_constituents_db,
    upsert_constituents,
)


def _domestic_fetch(ticker, asof, top_k):  # noqa: ARG001
    return FetchResult(
        status="ok",
        source=NAVER_STOCK_SOURCE,
        constituents=[
            FetchedConstituent(
                rank=1,
                constituent_ticker="005930",
                constituent_name="삼성전자",
                weight_pct=32.33,
                constituent_isin="KR7005930003",
                market_type="0",
            ),
            FetchedConstituent(
                rank=2,
                constituent_ticker="000660",
                constituent_name="SK하이닉스",
                weight_pct=25.61,
                constituent_isin="KR7000660001",
                market_type="0",
            ),
        ],
        effective_asof="2026-05-29",
    )


def _overseas_fetch(ticker, asof, top_k):  # noqa: ARG001
    return FetchResult(
        status="ok",
        source=NAVER_STOCK_SOURCE,
        constituents=[
            FetchedConstituent(
                rank=1,
                constituent_ticker=None,
                constituent_name="브로드컴",
                weight_pct=9.14,
                constituent_isin="US11135F1012",
                constituent_reuters_code="AVGO.O",
                market_type="2",
            ),
        ],
        effective_asof="2026-05-29",
    )


def test_service_uses_effective_asof_from_fetcher(tmp_path: Path):
    """입력 asof 와 응답 effective_asof 가 다를 때, 저장 + cache key 는
    effective_asof 기준으로 사용된다 (지시문 §6.1)."""
    db = tmp_path / "m.sqlite"
    result = refresh_constituents(
        asof="2026-05-31",  # 호출 입력.
        tickers=["069500"],
        fetcher=_domestic_fetch,
        sleep_fn=lambda _s: None,
        db_path=db,
    )
    assert result.status == "ok"
    assert result.success_count == 1
    # store 에 저장된 asof 는 응답의 effective_asof.
    stored = fetch_constituents(etf_ticker="069500", asof="2026-05-29", db_path=db)
    assert len(stored) == 2
    assert stored[0].source == NAVER_STOCK_SOURCE
    assert stored[0].constituent_isin == "KR7005930003"
    assert stored[0].market_type == "0"
    # 입력 asof 로는 저장 안 됨.
    not_stored = fetch_constituents(etf_ticker="069500", asof="2026-05-31", db_path=db)
    assert not_stored == []


def test_service_stores_overseas_reuters_and_isin(tmp_path: Path):
    """해외형 ETF — constituent_ticker=None 인 경우에도 reuters_code / ISIN /
    constituent_key 가 정확히 저장된다 (지시문 §6.3 / §7)."""
    db = tmp_path / "m.sqlite"
    refresh_constituents(
        asof="2026-05-29",
        tickers=["411420"],
        fetcher=_overseas_fetch,
        sleep_fn=lambda _s: None,
        db_path=db,
    )
    stored = fetch_constituents(etf_ticker="411420", asof="2026-05-29", db_path=db)
    assert len(stored) == 1
    c = stored[0]
    assert c.constituent_ticker is None
    assert c.constituent_reuters_code == "AVGO.O"
    assert c.constituent_isin == "US11135F1012"
    assert c.constituent_key == "AVGO.O"  # service 가 reuters 우선 매칭.
    assert c.market_type == "2"


def test_analysis_matches_overseas_via_reuters_code(tmp_path: Path):
    """compute_pair_overlap 가 해외 종목 (ticker=None) 을 reuters_code 로 매칭."""
    db = tmp_path / "m.sqlite"
    upsert_constituents(
        [
            ConstituentRow(
                etf_ticker="411420",
                asof="2026-05-29",
                source=NAVER_STOCK_SOURCE,
                rank=1,
                constituent_ticker=None,
                constituent_name="브로드컴",
                weight_pct=9.14,
                constituent_reuters_code="AVGO.O",
                constituent_isin="US11135F1012",
                constituent_key="AVGO.O",
                market_type="2",
            ),
            ConstituentRow(
                etf_ticker="411420",
                asof="2026-05-29",
                source=NAVER_STOCK_SOURCE,
                rank=2,
                constituent_ticker=None,
                constituent_name="엔비디아",
                weight_pct=8.0,
                constituent_reuters_code="NVDA.O",
                constituent_isin="US67066G1040",
                constituent_key="NVDA.O",
                market_type="2",
            ),
        ],
        db_path=db,
    )
    upsert_constituents(
        [
            ConstituentRow(
                etf_ticker="OTHER_OVERSEAS",
                asof="2026-05-29",
                source=NAVER_STOCK_SOURCE,
                rank=1,
                constituent_ticker=None,
                constituent_name="Broadcom Inc",  # 표기 다름.
                weight_pct=12.0,
                constituent_reuters_code="AVGO.O",  # 같은 reuters → 매칭.
                constituent_key="AVGO.O",
                market_type="2",
            ),
        ],
        db_path=db,
    )
    left = fetch_constituents(etf_ticker="411420", asof="2026-05-29", db_path=db)
    right = fetch_constituents(
        etf_ticker="OTHER_OVERSEAS", asof="2026-05-29", db_path=db
    )
    out = compute_pair_overlap(left, right, top_k=10)
    # AVGO.O 매칭 → 공통 1건.
    assert out["common_count_top10"] == 1
    # min(9.14, 12.0) = 9.14.
    assert out["weighted_overlap_pct"] == 9.14


def test_end_to_end_refresh_then_analysis_without_asof(tmp_path: Path):
    """2026-06-01 FIX (검증자 A-1 NOTE 반영) — refresh 가 effective_asof 로
    저장한 뒤, analysis 가 asof omit 으로 호출되면 latest_constituent_asof
    MAX 를 자동 사용해 available_count >= 1 이 나와야 한다.

    재현: Naver fetcher 가 referenceDate=2026-06-01 을 반환할 때, 사용자 입력
    asof=2026-05-28 로 refresh → 저장은 2026-06-01 → 입력 asof 로 analysis 면
    available_count=0 (직전 검증자 NOTE) → asof omit 으로 분석 시 MAX 사용해
    available_count=1.
    """
    from app.etf_constituents_analysis import compute_analysis
    from app.etf_constituents_store import latest_constituent_asof

    db = tmp_path / "m.sqlite"
    # service 에 입력 asof 는 사용자 화면 시점 (예: 2026-05-28).
    refresh_constituents(
        asof="2026-05-28",
        tickers=["069500"],
        fetcher=_domestic_fetch,  # effective_asof=2026-05-29 (위 _domestic_fetch)
        sleep_fn=lambda _s: None,
        db_path=db,
    )
    # 입력 asof 로 직접 조회하면 0건 (이전 버그 재현).
    out_with_input_asof = compute_analysis(
        tickers=["069500"], asof="2026-05-28", db_path=db
    )
    assert out_with_input_asof["coverage"]["available_count"] == 0

    # 본 FIX: asof omit 시 latest 사용 → available_count == 1.
    effective = latest_constituent_asof("069500", db_path=db)
    assert effective == "2026-05-29"
    out_with_latest = compute_analysis(tickers=["069500"], asof=effective, db_path=db)
    assert out_with_latest["coverage"]["available_count"] == 1
    assert out_with_latest["constituents"][0]["status"] == "ok"


def test_migration_adds_naver_columns_on_existing_db(tmp_path: Path):
    """직전 STEP 의 DB (constituent_key 등 4 컬럼 없음) → init_constituents_db
    호출 시 자동 ADD COLUMN 한다 (회귀 보호)."""
    db = tmp_path / "m.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    # 직전 STEP DDL — 신규 4 컬럼 없음.
    prev_ddl = (
        "CREATE TABLE etf_constituents ("
        "etf_ticker TEXT NOT NULL, asof TEXT NOT NULL, source TEXT NOT NULL, "
        "rank INTEGER NOT NULL, constituent_ticker TEXT, constituent_name TEXT, "
        "weight_pct REAL, etf_name TEXT, created_at TEXT NOT NULL, "
        "PRIMARY KEY (etf_ticker, asof, source, rank))"
    )
    with sqlite3.connect(str(db)) as con:
        con.execute(prev_ddl)
        con.commit()

    init_constituents_db(db)

    with sqlite3.connect(str(db)) as con:
        cur = con.execute("PRAGMA table_info(etf_constituents)")
        cols = {row[1] for row in cur.fetchall()}
    assert {
        "constituent_key",
        "constituent_isin",
        "constituent_reuters_code",
        "market_type",
    } <= cols

    # 새 컬럼 사용 가능.
    upsert_constituents(
        [
            ConstituentRow(
                etf_ticker="139260",
                asof="2026-05-29",
                source=NAVER_STOCK_SOURCE,
                rank=1,
                constituent_ticker="005930",
                constituent_name="삼성전자",
                weight_pct=32.33,
                constituent_isin="KR7005930003",
                constituent_key="005930",
                market_type="0",
            )
        ],
        db_path=db,
    )
    stored = fetch_constituents(etf_ticker="139260", asof="2026-05-29", db_path=db)
    assert stored[0].constituent_key == "005930"
    assert stored[0].constituent_isin == "KR7005930003"


def test_migration_concurrent_init_does_not_raise(tmp_path: Path):
    """2026-06-01 FIX (운영 사고 1건 후속) — FastAPI threadpool 에서 analysis
    엔드포인트가 ticker 마다 latest_constituent_asof 를 동시 호출 → 매번
    _connection() → init_constituents_db() → _migrate_add_naver_columns()
    실행. PRAGMA 확인 시점과 ALTER 실행 시점 사이 race 로 두 번째 스레드가
    duplicate column 오류로 500. 본 회귀 — 동시 init 여러 번 실행해도 예외
    없이 통과.
    """
    import threading

    db = tmp_path / "m.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    # 직전 STEP DDL — 신규 4 컬럼 없음. 마이그레이션 trigger 상태.
    prev_ddl = (
        "CREATE TABLE etf_constituents ("
        "etf_ticker TEXT NOT NULL, asof TEXT NOT NULL, source TEXT NOT NULL, "
        "rank INTEGER NOT NULL, constituent_ticker TEXT, constituent_name TEXT, "
        "weight_pct REAL, etf_name TEXT, created_at TEXT NOT NULL, "
        "PRIMARY KEY (etf_ticker, asof, source, rank))"
    )
    with sqlite3.connect(str(db)) as con:
        con.execute(prev_ddl)
        con.commit()

    errors: list[BaseException] = []

    def _worker():
        try:
            init_constituents_db(db)
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=_worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    # 결과적으로 4 컬럼 모두 정상 추가.
    with sqlite3.connect(str(db)) as con:
        cur = con.execute("PRAGMA table_info(etf_constituents)")
        cols = {row[1] for row in cur.fetchall()}
    assert {
        "constituent_key",
        "constituent_isin",
        "constituent_reuters_code",
        "market_type",
    } <= cols
