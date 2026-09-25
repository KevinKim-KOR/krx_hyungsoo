"""POC4-02B 러너 보호 — 재개로 라이브 5경로 검사를 우회하지 못함 · 원자 기록 · 네트워크 0 · 다른 DB 연결 거부 ·
공식 실행 쌍에만 판정 (PLAN §3-5 · §9 · 설계 §15 · 판정 §10).

tmp_path 의 KRX 스키마 고정 DB 와 tmp 라이브 루트만 쓴다. 봉인 DB·라이브 DB 는 열지 않는다.
"""

from __future__ import annotations

import copy
import json
import os
import socket
import sqlite3
from pathlib import Path

import pytest

from app import ml_ew_events as ew_events
from app import ml_ew_market_axes as ew_axes
from app import ml_ew_report as ew_report
from app import ml_ew_reproduce as ew_repro
from app.ml_baseline_snapshot import SnapshotGuardError, file_sha256
from app.ml_score_validity_report import canonical_sha256
from scripts import run_poc4_02b_early_warning as runner
from tests.test_poc4_02b_reproduce import make_live_root
from tests.test_poc4_02b_runner import _args, _files, build_krx_fixture

LOG_REL = "logs/oci_market_data_batch.log"


@pytest.fixture(scope="module")
def env(tmp_path_factory) -> dict:
    """봉인 fixture · 바뀌지 않는 라이브 루트 · 끊지 않은 기준 실행 1회."""
    base = tmp_path_factory.mktemp("guards")
    sealed = base / "krx.sqlite"
    build_krx_fixture(sealed)
    root = base / "live"
    make_live_root(root)
    baseline = runner.run(_args(base / "baseline", sealed, root))
    return {"sealed": sealed, "live": root, "baseline": baseline}


@pytest.fixture
def live(tmp_path) -> Path:
    root = tmp_path / "live"
    make_live_root(root)
    return root


def _append_log(root: Path) -> None:
    with open(root / LOG_REL, "a", encoding="utf-8") as fh:
        fh.write("changed\n")  # tmp 라이브 루트 — 실행 중 변경 흉내


def _marker(out: Path) -> dict:
    return json.loads((out / runner.GUARD_FAILED_FILENAME).read_text(encoding="utf-8"))


# --- 재개로 라이브 검사 우회 불가 ------------------------------------------------------------


def test_live_change_in_interrupted_segment_blocks_resume(
    tmp_path, env, live, monkeypatch
):
    """끊긴 구간에서 바뀐 라이브 경로 — 재개 시작에서 첫 시작 지문과 대조해 잡는다(결과 0)."""
    out = tmp_path / "run"

    def change_then_die(axes, signals):
        _append_log(live)
        raise KeyboardInterrupt("변경 뒤 중단 흉내")

    monkeypatch.setattr(ew_events, "build_event_stage", change_then_die)
    with pytest.raises(KeyboardInterrupt):
        runner.run(_args(out, env["sealed"], live))
    assert not (out / runner.GUARD_FAILED_FILENAME).exists()  # 끊긴 프로세스는 못 잰다
    monkeypatch.undo()
    with pytest.raises(runner.RunError, match="라이브 경로가 바뀌었다"):
        runner.run(_args(out, env["sealed"], live, "--resume"))
    mark = _marker(out)
    assert mark["reason"] == "LIVE_PATHS_CHANGED"
    assert mark["detail"]["when"] == "resume_start"
    assert mark["detail"]["changed"] == [LOG_REL]
    with pytest.raises(runner.RunError, match="보호 검사에 실패"):
        runner.run(_args(out, env["sealed"], live, "--resume"))
    assert sorted(_files(out)) == ["axes.json", "reproduce.json", "signals.json"]
    assert not (out / runner.RESULT_FILENAME).exists()
    assert not (out / runner.META_FILENAME).exists()


def test_live_change_in_resumed_segment_is_caught_at_end(
    tmp_path, env, live, monkeypatch
):
    """재개한 구간에서 바뀐 라이브 경로 — 끝에서 manifest 의 첫 시작 지문과 대조해 잡는다."""
    out = tmp_path / "run"
    real_null = ew_report.build_null_stage

    def die(*_a, **_k):
        raise KeyboardInterrupt("중단 흉내")

    monkeypatch.setattr(ew_report, "build_null_stage", die)
    with pytest.raises(KeyboardInterrupt):
        runner.run(_args(out, env["sealed"], live))

    def change_then_compute(*a, **k):
        _append_log(live)
        return real_null(*a, **k)

    monkeypatch.setattr(ew_report, "build_null_stage", change_then_compute)
    with pytest.raises(runner.RunError, match="라이브 경로가 바뀌었다"):
        runner.run(_args(out, env["sealed"], live, "--resume"))
    assert _marker(out)["detail"]["when"] == "run_end"
    assert "report.json" not in _files(out)  # 결과 payload 는 progress 에도 없다
    assert not (out / runner.RESULT_FILENAME).exists()
    monkeypatch.setattr(ew_report, "build_null_stage", real_null)
    with pytest.raises(runner.RunError, match="보호 검사에 실패"):
        runner.run(_args(out, env["sealed"], live, "--resume"))
    assert not (out / runner.RESULT_FILENAME).exists()


# --- 원자 기록 ------------------------------------------------------------------------------


def _fail_link_for(name: str):
    real_link = os.link

    def link(src, dst, *a, **k):
        if Path(dst).name == name:
            raise KeyboardInterrupt(f"{name} 게시 직전 중단 흉내")
        return real_link(src, dst, *a, **k)

    return link


def test_write_json_x_is_atomic_and_exclusive(tmp_path, monkeypatch):
    work = tmp_path / "w"  # tmp_path 에는 공용 fixture 가 만든 폴더가 있을 수 있다
    work.mkdir()
    target = work / "rec.json"
    runner.write_json_x(target, {"a": 1})
    with pytest.raises(FileExistsError):
        runner.write_json_x(target, {"a": 2})
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}
    monkeypatch.setattr(os, "link", _fail_link_for("other.json"))
    with pytest.raises(KeyboardInterrupt):
        runner.write_json_x(work / "other.json", {"b": 1})
    assert sorted(p.name for p in work.iterdir()) == ["rec.json"]  # 반쪽·임시 0


def test_interrupt_while_writing_record_then_resume_equals_fresh(
    tmp_path, env, monkeypatch
):
    out = tmp_path / "run"
    monkeypatch.setattr(os, "link", _fail_link_for("signals.json"))
    with pytest.raises(KeyboardInterrupt):
        runner.run(_args(out, env["sealed"], env["live"]))
    assert sorted(p.name for p in (out / "progress").iterdir()) == [
        "axes.json",
        "reproduce.json",
    ]
    monkeypatch.undo()
    result = runner.run(_args(out, env["sealed"], env["live"], "--resume"))
    assert result == env["baseline"]


# --- 네트워크 0 · 다른 DB 연결 거부 ------------------------------------------------------------


def test_run_makes_no_network_calls(tmp_path, env, live, monkeypatch):
    calls: list[str] = []

    def refuse(name):
        def _blocked(*_a, **_k):
            calls.append(name)
            raise OSError(f"테스트 네트워크 차단: {name}")

        return _blocked

    for name in (
        "socket",
        "create_connection",
        "getaddrinfo",
        "gethostbyname",
        "gethostbyname_ex",
        "gethostbyaddr",
    ):
        monkeypatch.setattr(socket, name, refuse(name))
    result = runner.run(_args(tmp_path / "run", env["sealed"], live))
    assert calls == []
    assert result["legacy_reproduction"]["status"] == ew_repro.EXACT_MATCH


@pytest.mark.parametrize("uri", [False, True], ids=["path", "readonly_uri"])
def test_live_db_connection_is_refused_during_run(
    tmp_path, env, live, monkeypatch, uri
):
    """운영 DB(etf_daily_price 등)에 붙으려 하면 실패 — 연결 허용은 봉인 DB 와 재현 사본뿐."""
    live_db = live / ew_repro.LIVE_DB_REL
    before = file_sha256(live_db)
    target = f"file:{live_db}?mode=ro" if uri else str(live_db)

    def peek_live(panel):
        con = sqlite3.connect(target, uri=uri)
        return con.execute("SELECT * FROM etf_daily_price").fetchall()

    monkeypatch.setattr(ew_axes, "build_market_axes", peek_live)
    out = tmp_path / "run"
    with pytest.raises(SnapshotGuardError, match="허용되지 않은 DB"):
        runner.run(_args(out, env["sealed"], live))
    assert not (out / runner.RESULT_FILENAME).exists()
    assert not (out / runner.META_FILENAME).exists()
    assert file_sha256(live_db) == before


# --- 비교: 공식 실행 쌍에만 판정 --------------------------------------------------------------


def _fake_run(d: Path, base: dict, **changes) -> Path:
    """완료된 실행 폴더 흉내 — result(canonical 재계산) · meta(재개 없음)."""
    d.mkdir()
    result = copy.deepcopy(base)
    result.update(changes)
    result["determinism"]["canonical_sha256"] = canonical_sha256(result)
    (d / runner.RESULT_FILENAME).write_text(json.dumps(result), encoding="utf-8")
    (d / runner.META_FILENAME).write_text(json.dumps({"resumed": False}), "utf-8")
    return d


@pytest.mark.parametrize(
    "first, second, final",
    [
        ((True, "PENDING"), (True, "PENDING"), "PASS_CANDIDATE"),
        ((True, "REJECT"), (True, "REJECT"), "REJECT"),
        ((True, "PENDING"), (True, "REJECT"), "REJECT"),  # canonical 다름
        ((False, "PENDING"), (False, "PENDING"), "NOT_OFFICIAL"),
        ((True, "PENDING"), (False, "PENDING"), "NOT_OFFICIAL"),
    ],
)
def test_compare_gives_verdict_only_for_official_pairs(
    tmp_path, env, first, second, final
):
    verdicts = {"PENDING": ew_report.PENDING, "REJECT": ew_report.REJECT}
    dirs = [
        _fake_run(tmp_path / f"r{i}", env["baseline"], official=o, verdict=verdicts[v])
        for i, (o, v) in enumerate((first, second))
    ]
    rec = runner.compare(*dirs)
    expected = {
        "PASS_CANDIDATE": ew_report.PASS_CANDIDATE,
        "REJECT": ew_report.REJECT,
        "NOT_OFFICIAL": runner.NOT_OFFICIAL_FINAL,
    }[final]
    assert rec["final_verdict"] == expected
    assert rec["official_both"] is (first[0] and second[0])
    assert rec["criterion_11"]["value"] is (first == second)


def test_compare_refuses_guard_failed_folder(tmp_path, env):
    dirs = [
        _fake_run(tmp_path / f"r{i}", env["baseline"], official=True) for i in (1, 2)
    ]
    (dirs[0] / runner.GUARD_FAILED_FILENAME).write_text("{}", encoding="utf-8")
    with pytest.raises(runner.RunError, match="보호 검사에 실패"):
        runner.compare(*dirs)
    assert not (dirs[1] / runner.COMPARE_FILENAME).exists()
