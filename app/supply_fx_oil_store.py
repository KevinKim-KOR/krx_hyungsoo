"""POC6-01 — 시장 흐름(수급 · 환율 · 유가) 일별 저장(시장 DB 같은 파일 · 표 2개).

- `market_macro_daily` — 원/달러 · WTI 의 완료된 일별 값. 계열 ID 마다 공급자 · 단위 · 기준이 고정이다
  (`MACRO_SERIES`). 다른 계열 · 단위가 같은 키로 들어오면 실패(저장 0 · POC6-01 PLAN 판정 §4-4).
  0 이하 값도 그대로 둔다(WTI 음수 가격 · 손상 일괄 처리 없음 · 설계 §3-1).
- `market_investor_flow_daily` — 코스피 투자자별 순매수(정수 원 · 키움 억원 × 1억). 원천 분류 이름
  그대로(`INVESTORS`) · 매수 · 매도 총액은 원천에 없어 NULL(판정 §7-3) · 빠진 날은 행이 없다(0 채우기 없음).

쓰기는 PC 시장 갱신과 POC6-05 OCI 일일 수집(`app/ml_evidence/daily_flow.py` · 받은 값을 먼저 증거로 보관)만
(표 생성 포함). 읽기(GET)는 `mode=ro` 로 열고, 파일 · 표가 없으면 빈 결과다
(조회가 표를 만들거나 외부를 부르지 않는다). 같은 날짜를 다시 받으면 최신 확보 값으로 덮는다(겹쳐 받기 ·
원천 정정 반영 · PIT 데이터셋 아님 · 판정 §4-1).
"""

from __future__ import annotations

import math
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from app.market_data_store import DEFAULT_DB_PATH

MACRO_DDL = """
CREATE TABLE IF NOT EXISTS market_macro_daily (
    series_id     TEXT NOT NULL,
    obs_date      TEXT NOT NULL,
    value         REAL NOT NULL,
    unit          TEXT NOT NULL,
    provider      TEXT NOT NULL,
    basis         TEXT NOT NULL,
    collected_at  TEXT NOT NULL,
    PRIMARY KEY (series_id, obs_date)
);
""".strip()

FLOW_DDL = """
CREATE TABLE IF NOT EXISTS market_investor_flow_daily (
    market        TEXT NOT NULL,
    trade_date    TEXT NOT NULL,
    investor      TEXT NOT NULL,
    buy_value     INTEGER,
    sell_value    INTEGER,
    net_value     INTEGER NOT NULL,
    source        TEXT NOT NULL,
    collected_at  TEXT NOT NULL,
    PRIMARY KEY (market, trade_date, investor)
);
""".strip()

USDKRW = "YAHOO_KRW_X_CLOSE_KRW_PER_USD"
WTI = "YAHOO_CL_F_CLOSE_USD_PER_BBL"
# 계열 ID → (단위, 공급자, 기준) — 고정. 다른 값이 오면 저장하지 않는다.
MACRO_SERIES: dict[str, tuple[str, str, str]] = {
    USDKRW: ("KRW/USD", "Yahoo chart KRW=X", "일봉 종가 · 런던 날짜(Europe/London)"),
    WTI: (
        "USD/bbl",
        "Yahoo chart CL=F",
        "근월물 선물 일봉 종가 · 뉴욕 날짜(America/New_York)",
    ),
}

# 시장 갱신 기록(`market_refresh_log`)의 새 출처 — '마지막 전체 갱신' 조회에서 뺀다(KOSPI 행 그대로).
FX_WTI_LOG_SOURCE = "YAHOO_FX_WTI_DAILY"
FLOW_LOG_SOURCE = "KIWOOM_KA10051_KOSPI_FLOW"
MARKET_FLOW_LOG_SOURCES = (FX_WTI_LOG_SOURCE, FLOW_LOG_SOURCE)

FLOW_MARKET = "KOSPI"
FLOW_SOURCE = "KIWOOM_KA10051_KRX"
# 원천(키움 ka10051) 분류 그대로. 기관계 = 기관 세부 합(함께 더하지 않는다).
INVESTORS: tuple[str, ...] = (
    "individual",
    "foreign",
    "institution",
    "other_corp",
    "native_foreign",
    "nation",
    "inst_securities",
    "inst_insurance",
    "inst_trust",
    "inst_bank",
    "inst_other_finance",
    "inst_pension",
    "inst_private_fund",
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def init_market_flow_tables(db_path: Path = DEFAULT_DB_PATH) -> None:
    """표 2개 보장(쓰기 경로 전용 — 시장 갱신)."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(str(db_path))) as con:
        con.execute(MACRO_DDL)
        con.execute(FLOW_DDL)
        con.commit()


def upsert_macro_daily(
    *,
    series_id: str,
    rows: Iterable[tuple[str, float]],
    unit: str,
    provider: str,
    basis: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    """완료된 일별 값을 (계열, 날짜) 기준으로 넣거나 최신 확보 값으로 바꾼다. 검사 실패 = 저장 0."""
    if MACRO_SERIES.get(series_id) != (unit, provider, basis):
        raise ValueError(f"계열 · 단위 · 공급자 · 기준이 고정값과 다름: {series_id}")
    now = _utcnow_iso()
    payload = []
    for d, v in rows:
        datetime.strptime(d, "%Y-%m-%d")
        if (
            not isinstance(v, (int, float))
            or isinstance(v, bool)
            or not math.isfinite(v)
        ):
            raise ValueError(f"값이 수가 아님: {series_id} {d}")
        payload.append((series_id, d, float(v), unit, provider, basis, now))
    if not payload:
        return 0
    init_market_flow_tables(db_path)
    with closing(sqlite3.connect(str(db_path))) as con:
        con.executemany(
            "INSERT INTO market_macro_daily "
            "(series_id, obs_date, value, unit, provider, basis, collected_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(series_id, obs_date) DO UPDATE SET value = excluded.value, "
            "unit = excluded.unit, provider = excluded.provider, basis = excluded.basis, "
            "collected_at = excluded.collected_at",
            payload,
        )
        con.commit()
    return len(payload)


def upsert_investor_flows(
    *,
    rows: Iterable[tuple[str, str, int]],
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    """(거래일, 투자자, 순매수 원) 을 넣거나 최신 확보 값으로 바꾼다. 매수 · 매도 총액은 NULL."""
    now = _utcnow_iso()
    payload = []
    for d, inv, net in rows:
        datetime.strptime(d, "%Y-%m-%d")
        if inv not in INVESTORS:
            raise ValueError(f"모르는 투자자 분류: {inv}")
        if not isinstance(net, int) or isinstance(net, bool):
            raise ValueError(f"순매수가 정수 원이 아님: {d} {inv}")
        payload.append((FLOW_MARKET, d, inv, net, FLOW_SOURCE, now))
    if not payload:
        return 0
    init_market_flow_tables(db_path)
    with closing(sqlite3.connect(str(db_path))) as con:
        con.executemany(
            "INSERT INTO market_investor_flow_daily (market, trade_date, investor, "
            "buy_value, sell_value, net_value, source, collected_at) "
            "VALUES (?, ?, ?, NULL, NULL, ?, ?, ?) "
            "ON CONFLICT(market, trade_date, investor) DO UPDATE SET "
            "net_value = excluded.net_value, source = excluded.source, "
            "collected_at = excluded.collected_at",
            payload,
        )
        con.commit()
    return len(payload)


def _ro(db_path: Path) -> Optional[sqlite3.Connection]:
    if not Path(db_path).exists():
        return None
    return sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)


def _has_table(con: sqlite3.Connection, name: str) -> bool:
    return (
        con.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
        ).fetchone()
        is not None
    )


def read_macro_series(
    series_id: str, *, db_path: Path = DEFAULT_DB_PATH
) -> tuple[list[tuple[str, float]], Optional[str]]:
    """(날짜순 [(날짜, 값)], 마지막 수집 시각). 표 · 파일 없음 = ([], None)."""
    con = _ro(db_path)
    if con is None:
        return [], None
    with closing(con):
        if not _has_table(con, "market_macro_daily"):
            return [], None
        rows = con.execute(
            "SELECT obs_date, value, collected_at FROM market_macro_daily "
            "WHERE series_id = ? ORDER BY obs_date",
            (series_id,),
        ).fetchall()
    return [(d, float(v)) for d, v, _ in rows], max(
        (c for _, _, c in rows), default=None
    )


def read_investor_flows(
    *, db_path: Path = DEFAULT_DB_PATH
) -> tuple[dict[str, list[tuple[str, int]]], Optional[str]]:
    """({투자자: 날짜순 [(거래일, 순매수 원)]}, 마지막 수집 시각). 표 · 파일 없음 = ({}, None)."""
    con = _ro(db_path)
    if con is None:
        return {}, None
    with closing(con):
        if not _has_table(con, "market_investor_flow_daily"):
            return {}, None
        rows = con.execute(
            "SELECT trade_date, investor, net_value, collected_at FROM market_investor_flow_daily "
            "WHERE market = ? ORDER BY trade_date",
            (FLOW_MARKET,),
        ).fetchall()
    out: dict[str, list[tuple[str, int]]] = {}
    for d, inv, net, _ in rows:
        out.setdefault(inv, []).append((d, int(net)))
    return out, max((c for *_, c in rows), default=None)


def read_benchmark_collected_at(
    benchmark_id: str, *, db_path: Path = DEFAULT_DB_PATH
) -> Optional[str]:
    """그 지수 최신 저장 행의 저장 시각(`created_at` · UTC ISO). 표 · 행 없음 = None."""
    con = _ro(db_path)
    if con is None:
        return None
    with closing(con):
        if not _has_table(con, "market_benchmark_daily_price"):
            return None
        row = con.execute(
            "SELECT created_at FROM market_benchmark_daily_price WHERE benchmark_id = ? "
            "AND close IS NOT NULL AND close > 0 ORDER BY date DESC LIMIT 1",
            (benchmark_id,),
        ).fetchone()
    return row[0] if row else None


def read_benchmark_series(
    benchmark_id: str, *, db_path: Path = DEFAULT_DB_PATH
) -> list[tuple[str, float]]:
    """코스피 · VIX 저장 시계열(읽기 전용 · 표가 없으면 []) — 조회가 표를 만들지 않게."""
    con = _ro(db_path)
    if con is None:
        return []
    with closing(con):
        if not _has_table(con, "market_benchmark_daily_price"):
            return []
        rows = con.execute(
            "SELECT date, close FROM market_benchmark_daily_price "
            "WHERE benchmark_id = ? AND close IS NOT NULL AND close > 0 ORDER BY date",
            (benchmark_id,),
        ).fetchall()
    return [(d, float(c)) for d, c in rows]
