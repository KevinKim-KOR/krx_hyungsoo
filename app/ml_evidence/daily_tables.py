"""POC6-05 — 기존 OCI 표 · 수집 기록 보관(재조회 0 · 읽기만).

- 관련 행은 한 읽기 전용 트랜잭션에서 읽고 바로 닫는다(외부 대기 · 압축 전 · 판정 §6-3).
- 최근 21거래일 delta: 처음 = 21일 전체 · 이후 바뀐 날짜만 새 object · 안 바뀐 날짜는 이전 object 참조.
- 시각 칸(collected_at · created_at) = DB 마지막 쓰기 시각. 최초 확보 시각으로 쓰지 않는다.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Callable, Optional

from app.ml_evidence import store

KOSPI_CORRECTIONS_DIR = Path("state/market/kospi_source_corrections")
DELTA_TRADING_DAYS = 21
BENCHMARK_IDS = ("KOSPI", "VIX", "US500", "IXIC", "^SOX")
TABLE_SEMANTICS = (
    "기존 OCI 표 읽기 · 재조회 0 · 시각 칸 = DB 마지막 쓰기 시각(최초 확보 시각 아님) · "
    "최근 21거래일 밖의 과거 정정은 보존하지 않음"
)
KRX_TABLES = (
    ("krx_etf_close", "krx_etf_daily_price_unadjusted"),
    ("krx_stock_close", "krx_stock_daily_price_unadjusted"),
)
BENCH_TABLE = "market_benchmark_daily_price"


def batch_state_files() -> tuple[Path, ...]:
    from app.three_push_runtime import market_data_batch as mdb

    return (mdb.MARKET_DATA_BATCH_STATE_PATH, mdb.KRX_REINFORCEMENT_STATE_PATH)


def _bench_groups(con: sqlite3.Connection) -> dict[str, list]:
    groups: dict[str, list] = {}
    sql = (
        f"SELECT date, close, source, created_at FROM {BENCH_TABLE} WHERE benchmark_id=? "
        f"AND date IN (SELECT DISTINCT date FROM {BENCH_TABLE} WHERE benchmark_id=? "
        "ORDER BY date DESC LIMIT ?) ORDER BY date"
    )
    for bid in BENCHMARK_IDS:
        for d, close, source, created in con.execute(
            sql, (bid, bid, DELTA_TRADING_DAYS)
        ):
            groups[f"{bid}|{d}"] = [[close, source, created]]
    return groups


def _krx_groups(con: sqlite3.Connection, table: str) -> dict[str, list]:
    groups: dict[str, list] = {}
    sql = (
        f"SELECT date, ticker, close, source, price_basis, collected_at FROM {table} "
        f"WHERE date IN (SELECT DISTINCT date FROM {table} ORDER BY date DESC LIMIT ?) "
        "ORDER BY date, ticker"
    )
    for d, t, close, source, basis, collected in con.execute(
        sql, (DELTA_TRADING_DAYS,)
    ):
        groups.setdefault(d, []).append([t, close, source, basis, collected])
    return groups


def read_db_snapshot(db_path: Path) -> dict[str, Any]:
    snap: dict[str, Any] = {"problems": [], "kospi": [], "groups": {}}
    if not db_path.exists():
        snap["problems"].append("시장 DB 없음")
        return snap
    con = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    try:
        con.execute("BEGIN")  # 한 읽기 트랜잭션 = 같은 시점의 행
        tables = {
            r[0]
            for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if BENCH_TABLE in tables:
            snap["kospi"] = [
                r[0]
                for r in con.execute(
                    f"SELECT date FROM {BENCH_TABLE} WHERE benchmark_id='KOSPI' ORDER BY date"
                )
            ]
            snap["groups"]["benchmarks"] = _bench_groups(con)
        else:
            snap["problems"].append(f"{BENCH_TABLE} 표 없음")
        for name, table in KRX_TABLES:
            if table in tables:
                snap["groups"][name] = _krx_groups(con, table)
            else:
                snap["problems"].append(f"{table} 표 없음")
        con.rollback()
    finally:
        con.close()
    return snap


def delta(
    name: str,
    snap: dict,
    prev_map: dict,
    root: Path,
    add: Callable[..., Any],
    reuse: Callable[[str, str], None],
    usable: Callable[[str], bool],
) -> dict:
    """바뀐 날짜(키)만 새 object 로 · 나머지는 이전 object 참조.

    이전 object 가 없거나 손상이면(`usable` 거짓) 그 키는 지금 표 값으로 다시 보관한다(손상 object 를 참조로
    잇지 않는다 · 매일 공개가 멈추지 않게 · 판정 §6-3).
    """
    groups = snap["groups"].get(name)
    if groups is None:
        return {"status": "FAILED", "reason": "표 없음 · 시장 DB 읽기 불가", "map": {}}
    writer = store.GzJsonlWriter(root)
    new_map: dict[str, dict] = {}
    changed: list[str] = []
    repaired: list[str] = []
    bad_refs = sorted({v["obj"] for v in prev_map.values() if not usable(v["obj"])})
    try:
        for key in sorted(groups):
            h = store.sha256_bytes(store.canonical(groups[key]))
            old = prev_map.get(key)
            if old and old["h"] == h:
                if old["obj"] not in bad_refs:
                    new_map[key] = old
                    continue
                repaired.append(key)
            writer.write({"key": key, "rows": groups[key]})
            changed.append(key)
            new_map[key] = {"h": h, "obj": None}
    except BaseException:
        writer.abort()
        raise
    sha = add(writer.finish(), f"{name}_delta", "jsonl.gz")
    for key in changed:
        new_map[key]["obj"] = sha
    for ref in sorted({v["obj"] for v in new_map.values()} - {sha}):
        reuse(ref, f"{name}_previous")
    return {
        "status": "OK" if changed else "SKIPPED_NO_NEW",
        "reason": None if groups else "표에 행 없음",
        "first_archive": not prev_map,
        "window_keys": len(groups),
        "changed_keys": changed,
        "repaired_keys": repaired,
        "previous_bad_objects": bad_refs,
        "object": sha,
        "map": new_map,
        "semantics": TABLE_SEMANTICS,
    }


def note_behind(section: dict, target: Optional[str]) -> None:
    """기준 거래일 행이 아직 없으면 최신일 · 사유를 남긴다(상태는 바꾸지 않음 — 수집 실패가 아니라 원천 미제공)."""
    keys = section.get("map") or {}
    if not target or not keys:
        return
    kospi = [k.split("|")[1] for k in keys if k.startswith("KOSPI|")]
    dates = kospi if any("|" in k for k in keys) else list(keys)
    latest = max(dates) if dates else None
    if latest is not None and latest < target:
        section["behind_target"] = {
            "target_day": target,
            "latest": latest,
            "reason": "기준 거래일 행이 아직 표에 없음(08:10 · 09:20 배치 미확보 · 주말에는 다음 거래일 08:10 배치가 채움)",
        }


def batch_records(root: Path, add: Callable[..., Any]) -> dict:
    """08:10 · 09:20 상태 파일(매 실행 덮어씀)의 그날 판 · KOSPI 정정 증거 파일."""
    files = []
    for p in batch_state_files():
        if not p.exists():
            files.append({"path": str(p), "missing": True})
            continue
        info = store.put_file(root, p)
        add(info, "batch_state", "json")
        files.append({"path": str(p), "sha256": info["sha256"], "bytes": info["bytes"]})
    corrections = {}
    if KOSPI_CORRECTIONS_DIR.exists():
        for p in sorted(KOSPI_CORRECTIONS_DIR.glob("*.json")):
            corrections[p.name] = add(
                store.put_file(root, p), "kospi_correction", "json"
            )
    got = [f for f in files if not f.get("missing")]
    return {
        "status": "OK" if len(got) == len(files) else ("PARTIAL" if got else "FAILED"),
        "files": files,
        "kospi_corrections": corrections,
        "semantics": "실행 시점 파일 내용 그대로(매 실행 덮어쓰는 상태 파일의 그날 판)",
    }
