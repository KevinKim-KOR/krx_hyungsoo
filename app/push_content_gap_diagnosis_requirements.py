"""PUSH Content Gap Diagnosis v1 — requirements + readiness (2026-07-05, FIX r2 분리).

책임:
- 3 PUSH (market_briefing / holdings_briefing / spike_or_falling_alert) 의
  SQLite · state artifact · 최소 lookback 의존성 매핑 상수 export.
- 읽기 전용 readiness helper (SQLite integrity / 테이블 존재 / artifact 존재).

분리 이유 (B-2 / B-3, FIX r2): 진단 core 를 requirements · reproducers ·
classifier · main runner 로 분해.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.three_push_runtime_message_builder import PUSH_KIND_DATA_SOURCES

# PUSH 별 관측 이력·evidence 의존성 매핑. 값은 실제 코드에서 참조하는 논리
# 이름·상대 경로. 절대 경로·secret 미포함.
PUSH_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "market_briefing": {
        "purpose": (
            "시장 흐름 브리핑 (KR 실시간 시세 + 미국 야간 흐름 + 시장 discovery"
            " + ML baseline + 뉴스 요약)"
        ),
        "sqlite_dependencies": [
            {
                "table": "etf_daily_price",
                "role": "KODEX200 / ETF 종가",
                "minimum_lookback_days": 20,
            },
            {
                "table": "market_benchmark_daily_price",
                "role": "KOSPI / VIX",
                "minimum_lookback_days": 20,
            },
        ],
        "artifact_dependencies": [
            {
                "logical": "runtime_probe_cache",
                "path": "state/runtime/three_push_runtime_probe_latest.json",
            },
            {"logical": "market_discovery_snapshot", "path": "state/market_cache"},
            {
                "logical": "ml_baseline_v0_report",
                "path": "state/ml/ml_baseline_v0_report_latest.json",
            },
        ],
        "expected_sources": PUSH_KIND_DATA_SOURCES.get("market_briefing", []),
    },
    "holdings_briefing": {
        "purpose": (
            "보유 종목 관찰 브리핑 (holdings snapshot + KR 실시간 시세 + NAV"
            " 괴리 + ML baseline)"
        ),
        "sqlite_dependencies": [
            {
                "table": "etf_daily_price",
                "role": "보유 ETF 종가",
                "minimum_lookback_days": 5,
            },
        ],
        "artifact_dependencies": [
            {
                "logical": "holdings_snapshot",
                "path": "state/holdings/holdings_latest.json",
            },
            {
                "logical": "runtime_probe_cache",
                "path": "state/runtime/three_push_runtime_probe_latest.json",
            },
            {
                "logical": "nav_discount_refresh",
                "path": "state/market/nav_discount_refresh_latest.json",
            },
            {
                "logical": "ml_baseline_v0_report",
                "path": "state/ml/ml_baseline_v0_report_latest.json",
            },
        ],
        "expected_sources": PUSH_KIND_DATA_SOURCES.get("holdings_briefing", []),
    },
    "spike_or_falling_alert": {
        "purpose": "급등락·상승 관찰 신호 (universe momentum + KR 실시간 시세)",
        "sqlite_dependencies": [
            {
                "table": "etf_daily_price",
                "role": "ETF 종가",
                "minimum_lookback_days": 20,
            },
        ],
        "artifact_dependencies": [
            {"logical": "universe_momentum_snapshot", "path": "state/universe"},
            {
                "logical": "runtime_probe_cache",
                "path": "state/runtime/three_push_runtime_probe_latest.json",
            },
        ],
        "expected_sources": PUSH_KIND_DATA_SOURCES.get("spike_or_falling_alert", []),
    },
}


# ---------- SQLite readiness (read only) ----------


def check_sqlite_integrity(db_path: Path) -> str:
    """SQLite integrity check. 파일이 없으면 unavailable, 손상 시 failed."""
    if not db_path.exists():
        return "unavailable"
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            r = con.execute("PRAGMA integrity_check").fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        return "failed"
    return "ok" if r and r[0] == "ok" else "failed"


def sqlite_table_ready(db_path: Path, table: str) -> dict[str, Any]:
    """table 존재 여부 + 행 수 + max(date). read only."""
    result: dict[str, Any] = {
        "table": table,
        "exists": False,
        "row_count": 0,
        "max_date": None,
    }
    if not db_path.exists():
        return result
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            row = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
                (table,),
            ).fetchone()
            if not row:
                return result
            result["exists"] = True
            count_row = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            if count_row:
                result["row_count"] = int(count_row[0])
            date_col_row = con.execute(f"PRAGMA table_info({table})").fetchall()
            date_cols = [c[1] for c in date_col_row if c[1] in ("date",)]
            if date_cols and result["row_count"] > 0:
                mx = con.execute(f"SELECT MAX(date) FROM {table}").fetchone()
                if mx:
                    result["max_date"] = mx[0]
        finally:
            con.close()
    except sqlite3.Error:
        return result
    return result


# ---------- artifact readiness (read only) ----------


def artifact_status(path_str: str) -> dict[str, Any]:
    """artifact 존재 여부 + mtime + size. content 는 read 하지 않음.

    보안: absolute path 를 artifact 에 저장하지 않는다 — 상대 경로 그대로 유지.
    """
    p = Path(path_str)
    if not p.exists():
        return {"path": path_str, "exists": False, "size": 0, "mtime": None}
    try:
        stat = p.stat()
        if p.is_dir():
            entries = list(p.iterdir())
            return {
                "path": path_str,
                "exists": True,
                "is_dir": True,
                "entry_count": len(entries),
                "mtime": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        return {
            "path": path_str,
            "exists": True,
            "is_dir": False,
            "size": int(stat.st_size),
            "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
        }
    except OSError:
        return {"path": path_str, "exists": False, "size": 0, "mtime": None}
