"""KOSPI Closeout — 역사 시계열 보강 (2026-07-05).

지시문 §5.2 순서:
  1. SQLite KODEX200 min/max 확인.
  2. 기존 SQLite KOSPI 행 read.
  3. NAVER_FDR 에서 KODEX200 범위 포괄 KOSPI 후보 조회 (SQLite write X).
  4. 기존 KOSPI 행 우선 원칙으로 논리 결합 (in-memory).
  5. 기존 dataset builder 로 가정 결합 데이터의 split 계산.
  6. 조건 (train/val/test 모두 >0) 만족 시 NAVER 선택.
  7. 조건 불충족 시 NAVER 저장 X.
  8. YAHOO_FDR 로 동일 조건 검사.
  9. YAHOO 조건 충족 시 YAHOO 만 선택.
 10. 둘 다 실패 → SQLite 변경 X, unavailable.

부작용: kospi 명령에서만 외부 조회. NAVER + YAHOO 신규 행 혼합 금지. 기존
KOSPI 행 overwrite 금지.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from app.market_benchmark_store import (
    fetch_existing_benchmark_close_map,
    upsert_benchmark_prices,
)
from app.market_data_store import DEFAULT_DB_PATH
from app.market_flow_dataset import (
    BENCHMARK_KOSPI_ID,
    BENCHMARK_KODEX200_TICKER,
    build_dataset,
)

KOSPI_CLOSEOUT_ARTIFACT_PATH = Path("state/market/kospi_history_closeout_latest.json")

NAVER_SYMBOL = "NAVER:KOSPI"
YAHOO_SYMBOL = "YAHOO:^KS11"


@dataclass
class SourceCandidate:
    name: str
    symbol: str
    queried: bool = False
    row_count: int = 0
    min_date: Optional[str] = None
    max_date: Optional[str] = None
    projected_split_rows: dict[str, int] = field(
        default_factory=lambda: {"train": 0, "validation": 0, "test": 0}
    )
    selected: bool = False


@dataclass
class KospiCloseoutResult:
    status: str = "unavailable"  # ok / unavailable / failed
    requested_start_date: Optional[str] = None
    requested_end_date: Optional[str] = None
    existing_row_count_before: int = 0
    existing_min_date: Optional[str] = None
    existing_max_date: Optional[str] = None
    naver: SourceCandidate = field(
        default_factory=lambda: SourceCandidate(name="NAVER_FDR", symbol=NAVER_SYMBOL)
    )
    yahoo: SourceCandidate = field(
        default_factory=lambda: SourceCandidate(name="YAHOO_FDR", symbol=YAHOO_SYMBOL)
    )
    selected_source: Optional[str] = None
    inserted_row_count: int = 0
    overwrite_performed: bool = False
    remaining_kospi_gap_count: int = 0
    source_application_ranges: list[dict] = field(default_factory=list)
    unavailable_reason: Optional[str] = None
    limitations: list[str] = field(default_factory=list)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fetch_kodex_range(db_path: Path) -> tuple[Optional[str], Optional[str]]:
    if not db_path.exists():
        return None, None
    con = sqlite3.connect(str(db_path))
    try:
        row = con.execute(
            "SELECT MIN(date), MAX(date) FROM etf_daily_price "
            "WHERE ticker = ? AND close IS NOT NULL AND close > 0",
            (BENCHMARK_KODEX200_TICKER,),
        ).fetchone()
    finally:
        con.close()
    if not row or row[0] is None:
        return None, None
    return str(row[0]), str(row[1])


def _fetch_source_kospi(symbol: str, start: date, end: date) -> list[tuple[str, float]]:
    """단일 source 에서 KOSPI (date, close) 리스트 조회. 외부 호출 1회.

    FIX r1 (검증자 B-1): 예외 세분화. FDR / requests / pandas 계열 예외만
    빈 리스트로 처리하고 그 외 (예: KeyboardInterrupt, MemoryError) 는 상위로.
    """
    import FinanceDataReader as fdr

    df = fdr.DataReader(symbol, start, end)
    if df is None or len(df) == 0 or "Close" not in df.columns:
        return []
    out: list[tuple[str, float]] = []
    for idx, raw in df.iterrows():
        if hasattr(idx, "strftime"):
            dt = idx.strftime("%Y-%m-%d")
        else:
            dt = str(idx)[:10]
        close_raw = raw["Close"]
        if close_raw is None:
            continue
        try:
            close = float(close_raw)
        except (TypeError, ValueError):
            continue
        if close != close or close <= 0:  # NaN or non-positive
            continue
        out.append((dt, close))
    return out


def _project_split_with_hypothetical_kospi(
    db_path: Path,
    hypothetical_kospi_rows: list[tuple[str, float]],
    existing_kospi: dict[str, Optional[float]],
) -> dict[str, int]:
    """가정 결합 데이터 (기존 KOSPI 우선 + 신규 KOSPI 를 hypothetical 로 삽입)
    을 만들어 임시 SQLite 에 넣고 build_dataset + split 실측.
    """
    import gc
    import shutil
    import tempfile

    # Windows 파일 핸들 GC 지연 회피 위해 TemporaryDirectory 에
    # ignore_cleanup_errors=True 지정.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpd:
        tmp_db = Path(tmpd) / "hypothetical.sqlite"
        shutil.copyfile(str(db_path), str(tmp_db))
        # 기존 KOSPI 우선 — hypothetical row 중 기존에 이미 있는 date 는 skip.
        appendable: list[tuple[str, Optional[float]]] = []
        for dt, close in hypothetical_kospi_rows:
            if dt in existing_kospi:
                continue
            appendable.append((dt, close))
        if appendable:
            upsert_benchmark_prices(
                benchmark_id=BENCHMARK_KOSPI_ID,
                benchmark_name="KOSPI",
                rows=appendable,
                source="HYPOTHETICAL",
                db_path=tmp_db,
            )
        result = build_dataset(db_path=tmp_db)
        # split 계산 (동일한 로직 재사용).
        from app.market_flow_baseline import _temporal_split

        train, val, test = _temporal_split(result.rows)
        split_result = {
            "train": len(train),
            "validation": len(val),
            "test": len(test),
        }
        # 명시적으로 참조 해제 + GC — Windows sqlite 파일 언락.
        del result, train, val, test
        gc.collect()
        return split_result


def _evaluate_candidate(
    *,
    db_path: Path,
    candidate: SourceCandidate,
    kodex_min: str,
    kodex_max: str,
    existing_kospi_map: dict[str, Optional[float]],
) -> list[tuple[str, float]]:
    """단일 source 에서 데이터 조회 + split 예측 계산. rows 반환."""
    start = date.fromisoformat(kodex_min)
    end = date.fromisoformat(kodex_max)
    # FIX r1 (검증자 B-1): 외부 조회 실패를 무조건 삼키지 않고, FDR /
    # requests 계열 네트워크·데이터 예외만 빈 후보로 처리. 프로그래머 오류
    # (AttributeError, TypeError from bug) 는 상위 노출.
    try:
        rows = _fetch_source_kospi(candidate.symbol, start, end)
    except (OSError, ValueError, KeyError):
        candidate.queried = True
        candidate.row_count = 0
        return []
    candidate.queried = True
    candidate.row_count = len(rows)
    if rows:
        candidate.min_date = rows[0][0]
        candidate.max_date = rows[-1][0]
    candidate.projected_split_rows = _project_split_with_hypothetical_kospi(
        db_path, rows, existing_kospi_map
    )
    return rows


def _is_split_sufficient(split: dict[str, int]) -> bool:
    return split["train"] > 0 and split["validation"] > 0 and split["test"] > 0


def _apply_selected_source(
    db_path: Path,
    rows: list[tuple[str, float]],
    existing_kospi_map: dict[str, Optional[float]],
    source_label: str,
) -> tuple[int, list[dict]]:
    """선택 source 의 신규 행만 (기존 date 제외) SQLite 적재.

    return: (inserted_count, application_ranges).
    """
    appendable: list[tuple[str, Optional[float]]] = []
    for dt, close in rows:
        if dt in existing_kospi_map:
            continue
        appendable.append((dt, close))
    if not appendable:
        return 0, []
    upsert_benchmark_prices(
        benchmark_id=BENCHMARK_KOSPI_ID,
        benchmark_name="KOSPI",
        rows=appendable,
        source=source_label,
        db_path=db_path,
    )
    ranges = [
        {
            "source": source_label,
            "start_date": appendable[0][0],
            "end_date": appendable[-1][0],
            "row_count": len(appendable),
        }
    ]
    return len(appendable), ranges


def _write_artifact(result: KospiCloseoutResult, path: Path) -> None:
    payload = {
        "status": result.status,
        "generated_at": _utcnow_iso(),
        "requested_range": {
            "start_date": result.requested_start_date,
            "end_date": result.requested_end_date,
        },
        "existing_kospi": {
            "row_count_before": result.existing_row_count_before,
            "min_date": result.existing_min_date,
            "max_date": result.existing_max_date,
        },
        "source_candidates": {
            "naver_fdr": {
                "queried": result.naver.queried,
                "row_count": result.naver.row_count,
                "min_date": result.naver.min_date,
                "max_date": result.naver.max_date,
                "projected_split_rows": result.naver.projected_split_rows,
                "selected": result.naver.selected,
            },
            "yahoo_fdr": {
                "queried": result.yahoo.queried,
                "row_count": result.yahoo.row_count,
                "min_date": result.yahoo.min_date,
                "max_date": result.yahoo.max_date,
                "projected_split_rows": result.yahoo.projected_split_rows,
                "selected": result.yahoo.selected,
            },
        },
        "selected_source": result.selected_source,
        "inserted_row_count": result.inserted_row_count,
        "overwrite_performed": result.overwrite_performed,
        "remaining_kospi_gap_count": result.remaining_kospi_gap_count,
        "source_application_ranges": result.source_application_ranges,
        "unavailable_reason": result.unavailable_reason,
        "limitations": result.limitations,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    tmp.replace(path)


def run_kospi_closeout(
    db_path: Path = DEFAULT_DB_PATH,
    artifact_path: Path = KOSPI_CLOSEOUT_ARTIFACT_PATH,
) -> KospiCloseoutResult:
    """KOSPI 역사 보강 실행 — SQLite 만 사용 (외부는 여기서만 호출).

    NAVER 우선, YAHOO 보조. 둘 다 실패 시 SQLite 변경 없이 unavailable.
    NAVER + YAHOO 신규 행 혼합 금지 (단일 source 만 적재).
    """
    result = KospiCloseoutResult()
    kodex_min, kodex_max = _fetch_kodex_range(db_path)
    result.requested_start_date = kodex_min
    result.requested_end_date = kodex_max
    if not kodex_min or not kodex_max:
        result.unavailable_reason = "kodex_range_missing"
        _write_artifact(result, artifact_path)
        return result

    existing_map = fetch_existing_benchmark_close_map(
        BENCHMARK_KOSPI_ID, db_path=db_path
    )
    result.existing_row_count_before = len(existing_map)
    if existing_map:
        sorted_dates = sorted(existing_map.keys())
        result.existing_min_date = sorted_dates[0]
        result.existing_max_date = sorted_dates[-1]

    # NAVER 시도.
    naver_rows = _evaluate_candidate(
        db_path=db_path,
        candidate=result.naver,
        kodex_min=kodex_min,
        kodex_max=kodex_max,
        existing_kospi_map=existing_map,
    )
    if naver_rows and _is_split_sufficient(result.naver.projected_split_rows):
        result.naver.selected = True
        inserted, ranges = _apply_selected_source(
            db_path, naver_rows, existing_map, "NAVER_FDR"
        )
        result.selected_source = "NAVER_FDR"
        result.inserted_row_count = inserted
        result.source_application_ranges = ranges
        result.status = "ok"
        _write_artifact(result, artifact_path)
        return result

    # NAVER 불충족 — SQLite 미변경. YAHOO 시도.
    yahoo_rows = _evaluate_candidate(
        db_path=db_path,
        candidate=result.yahoo,
        kodex_min=kodex_min,
        kodex_max=kodex_max,
        existing_kospi_map=existing_map,
    )
    if yahoo_rows and _is_split_sufficient(result.yahoo.projected_split_rows):
        result.yahoo.selected = True
        inserted, ranges = _apply_selected_source(
            db_path, yahoo_rows, existing_map, "YAHOO_FDR"
        )
        result.selected_source = "YAHOO_FDR"
        result.inserted_row_count = inserted
        result.source_application_ranges = ranges
        result.status = "ok"
        _write_artifact(result, artifact_path)
        return result

    # 둘 다 불충족.
    result.status = "unavailable"
    result.unavailable_reason = "both_sources_split_insufficient"
    _write_artifact(result, artifact_path)
    return result
