"""POC4-02B 운영 표 재현 감사 (PLAN §3 · 확정 B11 · 설계자 판정 §10).

tmp 에 운영 스키마(`ml_feature_store` DDL 그대로)의 작은 "라이브" DB 와 저장 보고서를 만든다 —
진짜 라이브 DB·보고서는 열지 않는다. 저장 보고서는 같은 기존 함수로 만든다.
"""

from __future__ import annotations

import json
import os
import random
import sqlite3
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

import pytest

from app import ml_ew_reproduce as rep
from app.ml_baseline_risk import RISK_COMPOSITE_AXES, evaluate_risk_baseline
from app.ml_baseline_snapshot import _path_key, file_sha256
from app.ml_baseline_targets import build_risk_targets
from app.ml_feature_store import ETF_ML_FEATURE_DAILY_DDL, MARKET_RISK_FEATURE_DAILY_DDL


def make_live_root(root: Path, n: int = 40, seed: int = 1) -> dict:
    """tmp 라이브 루트 — 시장 DB(두 표) · 저장 보고서 · 감시 로그 2개 · state/runs."""
    live_db = root / rep.LIVE_DB_REL
    report = root / rep.REPORT_REL
    live_db.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    cols = [a for a, _ in RISK_COMPOSITE_AXES]
    con = sqlite3.connect(live_db)
    con.execute(ETF_ML_FEATURE_DAILY_DDL)
    con.execute(MARKET_RISK_FEATURE_DAILY_DDL)
    d, close, k = date(2014, 5, 12), 100.0, 0
    while k < n:
        if d.weekday() < 5:
            asof = d.isoformat()
            close *= 1 + rng.gauss(0, 0.012)
            con.execute(
                "INSERT INTO etf_ml_feature_daily (asof, ticker, close_price, created_at) "
                "VALUES (?, '069500', ?, 'x')",
                (asof, round(close, 2)),
            )
            vals = [None if rng.random() < 0.2 else rng.gauss(0, 1) for _ in cols]
            con.execute(
                f"INSERT INTO market_risk_feature_daily (asof, {', '.join(cols)}, created_at) "
                f"VALUES (?, {', '.join('?' for _ in cols)}, 'x')",
                (asof, *vals),
            )
            k += 1
        d += timedelta(days=1)
    con.commit()
    con.close()
    rows, _errors = build_risk_targets(live_db, "069500")
    result = evaluate_risk_baseline(live_db, rows)
    payload = {"status": "ok", "risk_baseline": asdict(result)}
    report.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    for rel in ("logs/oci_market_data_batch.log", "logs/three_push_runtime_cron.log"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("log\n", encoding="utf-8")
    (root / "state" / "runs").mkdir(parents=True, exist_ok=True)
    (root / "state" / "runs" / "r1.json").write_text("{}", encoding="utf-8")
    return {
        "live_db": live_db,
        "report": report,
        "evaluated_days": result.evaluated_days,
    }


def _stat(path: Path) -> tuple:
    st = os.stat(path)
    return file_sha256(path), st.st_mtime_ns, st.st_size


def test_exact_match_live_untouched_copy_deleted(tmp_path):
    live = make_live_root(tmp_path / "live")
    before_db, before_rep = _stat(live["live_db"]), _stat(live["report"])
    copy = tmp_path / "run" / rep.COPY_NAME
    copy.parent.mkdir()
    got = rep.reproduce_legacy(live["live_db"], live["report"], copy)
    assert live["evaluated_days"] == 20
    assert got["status"] == rep.EXACT_MATCH and got["differing_keys"] == []
    assert got["evaluated_days"] == got["stored_evaluated_days"] == 20
    assert got["compared_leaf_values"] > 30
    sha = before_db[0]
    assert got["live_sha256_before_copy"] == got["live_sha256_after_copy"] == sha
    assert (
        got["copy_sha256"]
        == got["copy_sha256_after"]
        == got["live_sha256_after"]
        == sha
    )
    assert got["copy_integrity_check"] == "ok" and got["copy_mode"] == "0o444"
    assert got["copy_deleted"] is True and not copy.exists()
    assert list(copy.parent.iterdir()) == []
    # 라이브 DB·저장 보고서는 바뀌지 않는다 (sha · mtime · 크기)
    assert _stat(live["live_db"]) == before_db
    assert _stat(live["report"]) == before_rep
    assert got["report_sha256"] == got["report_sha256_after"] == before_rep[0]


def test_mismatch_reports_differing_keys(tmp_path):
    live = make_live_root(tmp_path / "live")
    data = json.loads(live["report"].read_text(encoding="utf-8"))
    data["risk_baseline"]["drawdown_capture_rate"]["10d"] += 1e-12
    data["risk_baseline"]["evaluated_days"] = 20.0  # 값은 같아도 타입이 다르면 다르다
    live["report"].write_text(json.dumps(data), encoding="utf-8")
    copy = tmp_path / rep.COPY_NAME
    got = rep.reproduce_legacy(live["live_db"], live["report"], copy)
    assert got["status"] == rep.MISMATCH
    assert got["differing_keys"] == ["drawdown_capture_rate.10d", "evaluated_days"]
    assert not copy.exists()


def test_live_db_is_never_connected(tmp_path, monkeypatch):
    live = make_live_root(tmp_path / "live")
    seen: list[str] = []
    real = sqlite3.connect

    def spy(database, *args, **kwargs):
        seen.append(_path_key(database))
        return real(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", spy)
    copy = tmp_path / rep.COPY_NAME
    got = rep.reproduce_legacy(live["live_db"], live["report"], copy)
    assert got["status"] == rep.EXACT_MATCH
    assert seen and set(seen) == {os.path.realpath(copy)}
    assert os.path.realpath(live["live_db"]) not in seen


def test_live_change_during_copy_fails_and_copy_removed(tmp_path, monkeypatch):
    live = make_live_root(tmp_path / "live")
    real_copy = rep.shutil.copyfile

    def copy_then_touch(src, dst):
        real_copy(src, dst)
        with open(src, "ab") as fh:  # tmp "라이브" 파일 — 복사 중 변경 흉내
            fh.write(b"\0")

    monkeypatch.setattr(rep.shutil, "copyfile", copy_then_touch)
    copy = tmp_path / rep.COPY_NAME
    with pytest.raises(rep.ReproductionError, match="라이브 DB 가 바뀌었다"):
        rep.reproduce_legacy(live["live_db"], live["report"], copy)
    assert not copy.exists()


def test_stale_copy_from_killed_run_is_replaced(tmp_path):
    live = make_live_root(tmp_path / "live")
    copy = tmp_path / rep.COPY_NAME
    copy.write_bytes(b"stale")
    os.chmod(copy, 0o444)
    got = rep.reproduce_legacy(live["live_db"], live["report"], copy)
    assert got["status"] == rep.EXACT_MATCH and not copy.exists()


def test_missing_inputs_fail(tmp_path):
    with pytest.raises(rep.ReproductionError, match="라이브 DB 가 없다"):
        rep.reproduce_legacy(tmp_path / "x.sqlite", tmp_path / "r.json", tmp_path / "c")


def test_diff_keys():
    assert rep.diff_keys({"a": 1, "b": [1, 2]}, {"a": 1, "b": [1, 2]}) == []
    assert rep.diff_keys({"a": 1}, {"a": 1.0}) == ["a"]
    assert rep.diff_keys({"a": {"x": None}}, {"a": {"x": 0}}) == ["a.x"]
    assert rep.diff_keys({"a": [1, 2]}, {"a": [1]}) == ["a"]
    assert rep.diff_keys({"a": [1, 2]}, {"a": [1, 3]}) == ["a[1]"]
    assert rep.diff_keys({"a": 1}, {"b": 1}) == ["a", "b"]
    assert rep.diff_keys(True, 1) == ["<root>"]
