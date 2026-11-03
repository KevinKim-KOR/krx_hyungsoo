"""POC6-19 — 고정 표본(PLAN §1-3)과 입력 사본(외부 조회 전 · 운영 DB mode=ro · 봉인 판 immutable).

- 수급 표본 8일 = 2026-09-21 · 2025-09-30 + 2024 · 2022 · 2020 · 2018 · 2016 · 2014 년 첫 저장 코스피 거래일
  (코스피 저장 계열이 2014-04-10 부터라 2014 년 표본 = 그날). 실행 때 저장 달력과 다시 대조한다(`check_plan`).
- 원/달러 · WTI 표본 창 = 2026-09-01 ~ 21 · 2020-04 · 2014-01(끝일 포함).
- 입력 사본: 코스피 종가(날짜 · 종가 · 출처) · 기존 저장 수급 · 환율 · WTI(대조용) · 봉인 판 날짜와 파일 sha256.
  검산은 이 사본으로 한다(운영 DB 가 바뀌어도 같은 결과).
"""

from __future__ import annotations

import sqlite3
import subprocess
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.krx_sealed_reader import SEALED_VERSION, open_readonly
from app.market_history import normalize as N
from app.ml_baseline_snapshot import file_sha256
from app.supply_fx_oil_store import USDKRW, WTI, read_investor_flows, read_macro_series

FLOW_SAMPLES = (
    "2026-09-21",
    "2025-09-30",
    "2024-01-02",
    "2022-01-03",
    "2020-01-02",
    "2018-01-02",
    "2016-01-04",
    "2014-04-10",
)
MACRO_WINDOWS = (
    ("2026-09", "2026-09-01", "2026-09-21"),
    ("2020-04", "2020-04-01", "2020-04-30"),
    ("2014-01", "2014-01-01", "2014-01-31"),
)


@dataclass(frozen=True)
class Plan:
    flow_samples: tuple = FLOW_SAMPLES
    macro_windows: tuple = MACRO_WINDOWS
    target_end: str = "2026-09-21"
    macro_target_start: str = "2014-01-02"


# --- 입력 사본 ---------------------------------------------------------------


def _kospi_rows(market_db: Path) -> list[list]:
    uri = f"file:{Path(market_db).resolve()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as con:
        rows = con.execute(
            "SELECT date, close, source FROM market_benchmark_daily_price "
            "WHERE benchmark_id = 'KOSPI' AND close IS NOT NULL AND close > 0 ORDER BY date"
        ).fetchall()
    return [[d, float(c), s] for d, c, s in rows]


def _sealed_calendar(sealed_db: Path) -> dict:
    with closing(open_readonly(sealed_db)) as con:
        st = con.execute(
            "SELECT status FROM krx_dataset_version WHERE version_id = ?",
            (SEALED_VERSION,),
        ).fetchone()
        rows = con.execute(
            "SELECT DISTINCT bas_dd FROM krx_dataset_member WHERE version_id = ? ORDER BY bas_dd",
            (SEALED_VERSION,),
        ).fetchall()
    return {
        "version": SEALED_VERSION,
        "status": st[0] if st else None,
        "dates": [N.iso(r[0]) for r in rows],
    }


def prepare_inputs(rec, market_db: Path, sealed_db: Path) -> dict:
    """외부 조회 전에 읽는 입력 사본(운영 DB mode=ro · 봉인 판 immutable)과 해시."""
    kospi = {
        "source_table": "market_benchmark_daily_price(KOSPI)",
        "rows": _kospi_rows(market_db),
    }
    flows, _ = read_investor_flows(db_path=market_db)
    stored = {
        "flows": {
            inv: [[d, n] for d, n in pairs] for inv, pairs in sorted(flows.items())
        },
        "macro": {
            sid: [[d, v] for d, v in read_macro_series(sid, db_path=market_db)[0]]
            for sid in (USDKRW, WTI)
        },
    }
    sealed = {
        **_sealed_calendar(sealed_db),
        "file_sha256_before": file_sha256(sealed_db),
    }
    for rel, doc in (
        (N.INPUT_KOSPI, kospi),
        (N.INPUT_STORED, stored),
        (N.INPUT_SEALED, sealed),
    ):
        rec.new_json(rel, doc)
    sources: dict[str, int] = {}
    for _, _, s in kospi["rows"]:
        sources[s] = sources.get(s, 0) + 1
    return {
        "kospi": kospi,
        "sealed": sealed,
        "summary": {
            N.INPUT_KOSPI: {
                "sha256": file_sha256(rec.run_dir / N.INPUT_KOSPI),
                "rows": len(kospi["rows"]),
                "first": kospi["rows"][0][0] if kospi["rows"] else None,
                "last": kospi["rows"][-1][0] if kospi["rows"] else None,
                "sources": sources,
            },
            N.INPUT_STORED: {
                "sha256": file_sha256(rec.run_dir / N.INPUT_STORED),
                "flow_dates": len({d for p in stored["flows"].values() for d, _ in p}),
                "macro_rows": {sid: len(v) for sid, v in stored["macro"].items()},
            },
            N.INPUT_SEALED: {
                "sha256": file_sha256(rec.run_dir / N.INPUT_SEALED),
                "version": sealed["version"],
                "status": sealed["status"],
                "dates": len(sealed["dates"]),
                "file_sha256": sealed["file_sha256_before"],
            },
        },
    }


def sealed_refusal(sealed: dict) -> Optional[str]:
    """봉인 판 전제: 판 기록 있음 · 상태 SEALED · 날짜 목록 있음(PLAN §1-1 · 검증자 r1 F1)."""
    if sealed.get("status") is None:
        return f"봉인 판 기록이 없다: {SEALED_VERSION}"
    if sealed["status"] != "SEALED":
        return f"봉인되지 않은 판: {SEALED_VERSION}({sealed['status']})"
    if not sealed.get("dates"):
        return f"봉인 판의 날짜 목록이 비어 있다: {SEALED_VERSION}"
    return None


def precheck(market_db: Path, sealed_db: Path) -> Optional[str]:
    """외부 조회 · 실행 폴더 생성 전 필수 입력 전제. 하나라도 아니면 시작하지 않는다(사유 = 문장)."""
    if not Path(sealed_db).is_file():
        return "봉인 판 파일이 없다"
    if not Path(market_db).is_file():
        return "운영 시장 DB 파일이 없다"
    try:
        refusal = sealed_refusal(_sealed_calendar(sealed_db))
    except sqlite3.Error as e:
        return f"봉인 판을 읽을 수 없다({type(e).__name__})"
    if refusal:
        return refusal
    try:
        rows = _kospi_rows(market_db)
    except sqlite3.Error as e:
        return f"운영 시장 DB 의 코스피 종가를 읽을 수 없다({type(e).__name__})"
    return None if rows else "운영 시장 DB 에 코스피 종가가 없다"


def check_plan(plan: Plan, kospi_dates: list[str]) -> Optional[str]:
    """표본 날짜가 PLAN 규칙(앞 두 날짜 = 저장 달력에 있음 · 나머지 = 그해 첫 저장 거래일)과 같은지."""
    have = set(kospi_dates)
    for d in plan.flow_samples[:2]:
        if d not in have:
            return f"대조일 {d} 가 저장 코스피 달력에 없다"
    for d in plan.flow_samples[2:]:
        first = next((x for x in kospi_dates if x.startswith(d[:4])), None)
        if first != d:
            return (
                f"{d[:4]}년 첫 저장 코스피 거래일은 {first} 다(PLAN 표본 {d} 와 다름)"
            )
    if list(plan.flow_samples) != sorted(plan.flow_samples, reverse=True):
        return "수급 표본은 최근 → 과거 순서여야 한다"
    return None


def code_info(repo_root: Path) -> dict:
    files = sorted((repo_root / "app/market_history").glob("*.py")) + [
        repo_root / "scripts/run_market_history.py"
    ]
    rels = [str(p.relative_to(repo_root)) for p in files if p.is_file()]

    def git(*args: str) -> str:
        try:
            return subprocess.run(
                ["git", *args],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return "UNKNOWN"

    return {
        "git_head": git("rev-parse", "HEAD"),
        "git_status": git("status", "--porcelain", "--", *rels).splitlines(),
        "files": {rel: file_sha256(repo_root / rel) for rel in rels},
    }
