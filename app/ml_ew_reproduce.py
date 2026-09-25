"""POC4-02B — 운영 risk_baseline 표 재현 감사 (PLAN §3 · 확정 B11 · 설계자 판정 §10).

라이브 시장 DB 에 **직접 연결하지 않는다**. POC4-01 `READONLY_SESSION_COPY` 방식으로 사본을 만든다.

1. 라이브 sha256 → `shutil.copyfile` → 라이브 sha256 다시(같아야 함) → 사본 sha256 == 라이브 →
   사본을 `file:<사본>?mode=ro` 로 열어 `PRAGMA integrity_check` == ok → 사본 0444.
2. `guard_sqlite_paths([사본])` 안에서 기존 `build_risk_targets(사본, "069500")` ·
   `evaluate_risk_baseline(사본, rows)` 를 **수정 없이** 부른다(평범한 `sqlite3.connect` —
   0444 파일이라 SQLite 가 읽기 전용으로 연다).
3. `json.loads(json.dumps(asdict(result), default=str))` 를 저장 보고서의 `risk_baseline` 과 모든 키 비교
   (타입까지) → `EXACT_MATCH` / `MISMATCH` + 다른 키 목록(점 표기).
4. 사본 hash 를 다시 재고(바뀌면 실패) 쓰기 가능으로 되돌려 지운다.

감사 전용 — 여기 숫자는 KRX 평가 입력이 아니다. 보고서·feature 표 쓰기 0 · 보고서를 쓰는 두 입구
(`scripts/run_ml_baseline_v0.py` · `app/ml_job_runner.py`)를 부르지 않는다.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import stat
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.ml_baseline_risk import evaluate_risk_baseline
from app.ml_baseline_snapshot import file_sha256, guard_sqlite_paths
from app.ml_baseline_targets import build_risk_targets

KODEX_TICKER = "069500"
EXACT_MATCH = "EXACT_MATCH"
MISMATCH = "MISMATCH"
SKIPPED = "SKIPPED"
LIVE_DB_REL = Path("state") / "market" / "market_data.sqlite"
REPORT_REL = Path("state") / "ml" / "ml_baseline_v0_report_latest.json"
COPY_NAME = "legacy_session_copy.sqlite"
_READ_ONLY = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
_SIDE_FILES = ("-journal", "-wal", "-shm")


class ReproductionError(RuntimeError):
    """세션 사본 조건 위반 — 복사 중 라이브 변경 · 사본 hash 불일치 · integrity 실패 · 사본 변경."""


def diff_keys(a: Any, b: Any, prefix: str = "") -> list[str]:
    """두 JSON 값의 다른 키(점 표기). 타입이 다르면(예: 1 대 1.0) 다른 값으로 본다."""
    if isinstance(a, dict) and isinstance(b, dict):
        out: list[str] = []
        for key in sorted(set(a) | set(b), key=str):
            path = f"{prefix}.{key}" if prefix else str(key)
            if key not in a or key not in b:
                out.append(path)
            else:
                out.extend(diff_keys(a[key], b[key], path))
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [prefix or "<root>"]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out.extend(diff_keys(x, y, f"{prefix}[{i}]"))
        return out
    if type(a) is not type(b) or a != b:
        return [prefix or "<root>"]
    return []


def _leaf_count(value: Any) -> int:
    if isinstance(value, dict):
        return sum(_leaf_count(v) for v in value.values())
    if isinstance(value, list):
        return sum(_leaf_count(v) for v in value)
    return 1


def _remove_copy(copy: Path) -> None:
    for suffix in ("", *_SIDE_FILES):
        path = Path(f"{copy}{suffix}")
        if path.exists():
            os.chmod(path, stat.S_IWUSR | stat.S_IRUSR)
            path.unlink()


def _session_copy(live_db: Path, copy: Path) -> dict:
    before = file_sha256(live_db)
    shutil.copyfile(live_db, copy)
    after = file_sha256(live_db)
    copied = file_sha256(copy)
    if before != after:
        raise ReproductionError(f"사본을 만드는 동안 라이브 DB 가 바뀌었다: {live_db}")
    if copied != before:
        raise ReproductionError(f"사본 sha256 이 라이브와 다르다: {copy}")
    con = sqlite3.connect(f"file:{copy.resolve()}?mode=ro", uri=True)
    try:
        integrity = [r[0] for r in con.execute("PRAGMA integrity_check")]
    finally:
        con.close()
    if integrity != ["ok"]:
        raise ReproductionError(f"사본 integrity 검사 실패: {integrity[:5]}")
    os.chmod(copy, _READ_ONLY)
    return {
        "live_sha256_before_copy": before,
        "live_sha256_after_copy": after,
        "copy_sha256": copied,
        "copy_integrity_check": integrity[0],
        "copy_mode": oct(stat.S_IMODE(os.stat(copy).st_mode)),
    }


def reproduce_legacy(live_db: Path, report_path: Path, copy: Path) -> dict:
    """세션 사본으로 기존 risk_baseline 을 다시 계산해 저장 보고서와 모든 키를 비교한다."""
    live_db, report_path, copy = Path(live_db), Path(report_path), Path(copy)
    if not live_db.is_file():
        raise ReproductionError(f"라이브 DB 가 없다: {live_db}")
    if not report_path.is_file():
        raise ReproductionError(f"저장 보고서가 없다: {report_path}")
    report_sha = file_sha256(report_path)
    stored = json.loads(report_path.read_text(encoding="utf-8"))["risk_baseline"]
    _remove_copy(copy)  # 이전에 강제 종료된 실행이 남긴 사본(이 단계 전용 임시 파일)
    try:
        with guard_sqlite_paths([copy]):
            record = _session_copy(live_db, copy)
            rows, target_errors = build_risk_targets(copy, KODEX_TICKER)
            result = evaluate_risk_baseline(copy, rows)
        got = json.loads(json.dumps(asdict(result), default=str))
        copy_after = file_sha256(copy)
        if copy_after != record["copy_sha256"]:
            raise ReproductionError("재현 중 사본이 바뀌었다")
    finally:
        _remove_copy(copy)
    live_after = file_sha256(live_db)
    if live_after != record["live_sha256_before_copy"]:
        raise ReproductionError("재현 중 라이브 DB 가 바뀌었다")
    report_after = file_sha256(report_path)
    if report_after != report_sha:
        raise ReproductionError("재현 중 저장 보고서가 바뀌었다")
    differing = diff_keys(got, stored)
    return {
        "status": EXACT_MATCH if not differing else MISMATCH,
        "differing_keys": differing,
        "compared_leaf_values": _leaf_count(stored),
        "live_db": str(live_db),
        **record,
        "copy_sha256_after": copy_after,
        "copy_deleted": not copy.exists(),
        "live_sha256_after": live_after,
        "report_path": str(report_path),
        "report_sha256": report_sha,
        "report_sha256_after": report_after,
        "evaluated_days": result.evaluated_days,
        "stored_evaluated_days": stored.get("evaluated_days"),
        "risk_target_errors": target_errors,
        "method": "READONLY_SESSION_COPY · build_risk_targets + evaluate_risk_baseline 무수정",
        "audit_only": True,
    }


def skipped_record() -> dict:
    return {
        "status": SKIPPED,
        "reason": "--skip-legacy-reproduction (스모크 전용 · official=false)",
        "audit_only": True,
    }
