"""POC4-01 — 불변 스냅샷 · fail-closed 입력 · 결정성 검증 (설계자 결정 1 — 2026-09-23).

설계자 검증 기준 4개를 실제 실행 경로로 확인한다.

1. 같은 snapshot 으로 두 번 실행한 결과 hash 가 같다
2. 라이브 DB 에 새 날짜가 추가돼도 결과가 같다
3. 라이브 DB 의 과거 행이 바뀌어도 결과가 같다
4. snapshot 누락·hash 불일치면 실행이 실패한다

2·3 이 "아무 영향 없는 변경" 이라서 통과하는 것이 아님을 보이려고, 같은 변경을
반영한 **새 snapshot** 으로 돌리면 **데이터에서 나온 값**(기준일별 IC·평가일 목록)이
달라지는 것도 함께 확인한다. 식별자(baseline_id·manifest hash) 차이는 대조 근거로
쓰지 않는다.
모든 DB 는 tmp_path 안에 만든다 — 라이브 DB 는 열지 않는다.
"""

from __future__ import annotations

import importlib
import json
import os
import sqlite3
import stat
import subprocess
from pathlib import Path

import pytest

from app.market_data_store import (
    EtfDailyPriceRow,
    EtfMasterRow,
    init_db,
    upsert_daily_prices,
    upsert_etf_master,
)
from app.ml_baseline_provenance import git_state, normalized_ast_sha256_from_source
from app.ml_baseline_snapshot import (
    MANIFEST_FILENAME,
    WORKING_E1_NAME,
    SnapshotGuardError,
    SnapshotIntegrityError,
    build_snapshot,
    file_sha256,
    guard_sqlite_paths,
    snapshot_session,
    verify_snapshot,
)
from app.ml_relative_upside_features import KODEX200_TICKER
from app.ml_score_validity_eval import load_prices

cli = importlib.import_module("scripts.run_ml_score_validity_eval_v1")
tool = importlib.import_module("scripts.ml_baseline_tool")

CUTOFF = "2020-12-20"


# --- 합성 라이브 DB ------------------------------------------------------------


def synthetic_days(months: int = 12) -> list[str]:
    return [f"2020-{m:02d}-{d:02d}" for m in range(1, months + 1) for d in range(1, 21)]


def _walk(days, seed: int) -> list[tuple[str, float]]:
    state = (seed * 6364136223846793005 + 1442695040888963407) % (2**31)
    out, price = [], 100.0 + (seed % 17)
    for d in days:
        state = (state * 1103515245 + 12345) % (2**31)
        price *= 1.0 + ((state % 2001) - 1000) / 40000.0
        out.append((d, round(price, 4)))
    return out


def synthetic_prices(good_count: int = 30) -> dict:
    days = synthetic_days()
    prices = {KODEX200_TICKER: _walk(days, 1)}
    for i in range(good_count):
        prices[f"GOOD{i:02d}"] = _walk(days, 100 + i)
    return prices


def write_live_db(path: Path, prices: dict) -> Path:
    init_db(path)
    upsert_etf_master(
        [EtfMasterRow(t, f"테스트 {t}", None, None, None, None) for t in prices],
        source="test",
        db_path=path,
    )
    upsert_daily_prices(
        [
            EtfDailyPriceRow(t, d, c, c, c, c, 1000, None)
            for t, hist in prices.items()
            for d, c in hist
        ],
        source="test",
        db_path=path,
    )
    return path


def make_snapshot(
    tmp_path: Path,
    prices: dict,
    *,
    baseline_id: str = "snap",
    live: Path | None = None,
    cutoff: str = CUTOFF,
) -> Path:
    live = live or write_live_db(tmp_path / "live.sqlite", prices)
    e1 = tmp_path / "e1_source.json"
    if not e1.exists():
        e1.write_text(json.dumps({"asof_date": cutoff, "candidates": []}), "utf-8")
    build_snapshot(
        live_db_path=live,
        e1_source_path=e1,
        bundle_dir=tmp_path / "baselines" / baseline_id,
        cutoff=cutoff,
        baseline_id=baseline_id,
    )
    return tmp_path / "baselines" / baseline_id / MANIFEST_FILENAME


def _run(
    manifest: Path, out_dir: Path, *extra: str, cutoff: str = CUTOFF, e1: bool = False
) -> int:
    return cli.main(
        [
            "--snapshot-manifest",
            str(manifest),
            "--cutoff",
            cutoff,
            "--out-dir",
            str(out_dir),
            "--limit-dates",
            "3",
            "--allow-dirty-code",
            *([] if e1 else ["--skip-e1"]),
            *extra,
        ]
    )


def _writable(path: Path) -> None:
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


# --- 스냅샷 생성 --------------------------------------------------------------


def test_build_snapshot_copies_only_rows_up_to_cutoff_and_seals(tmp_path):
    manifest_path = make_snapshot(tmp_path, synthetic_prices(), cutoff="2020-06-20")
    m = json.loads(manifest_path.read_text("utf-8"))
    bundle = manifest_path.parent

    prices = m["tables"]["etf_daily_price"]
    assert prices["max_date"] == "2020-06-20"
    assert prices["rows"] == 31 * 6 * 20
    assert prices["tickers"] == 31
    assert m["source"]["live_db_stats_at_snapshot"]["etf_daily_price"]["max_date"] == (
        "2020-12-20"
    ), "라이브에는 cutoff 이후 행이 있었어야 한다"
    assert m["files"]["dataset"]["sha256"] == file_sha256(bundle / "dataset.sqlite")
    assert m["schema_sha256"] and m["tables"]["etf_master"]["content_sha256"]
    assert m["evaluation_calendar"]["e2_dates"], "평가일 목록이 manifest 에 고정돼야"
    for name in ("dataset.sqlite", "e1_score_snapshot.json", MANIFEST_FILENAME):
        assert not os.access(bundle / name, os.W_OK), f"{name} 은 읽기 전용이어야"
    assert not (bundle.parent / "snap.building").exists()


def test_build_snapshot_refuses_to_overwrite_existing_bundle(tmp_path):
    make_snapshot(tmp_path, synthetic_prices())
    with pytest.raises(SnapshotIntegrityError, match="덮어쓰지"):
        make_snapshot(tmp_path, synthetic_prices(), live=tmp_path / "live.sqlite")


# --- 검증 기준 4: 누락·불일치면 실패 --------------------------------------------


def test_verify_fails_when_manifest_missing(tmp_path):
    with pytest.raises(SnapshotIntegrityError, match="manifest"):
        verify_snapshot(tmp_path / "nope" / MANIFEST_FILENAME)


@pytest.mark.parametrize("name", ["dataset.sqlite", "e1_score_snapshot.json"])
def test_verify_fails_when_file_missing(tmp_path, name):
    manifest = make_snapshot(tmp_path, synthetic_prices())
    target = manifest.parent / name
    _writable(target)
    target.unlink()
    with pytest.raises(SnapshotIntegrityError, match="파일이 없다"):
        verify_snapshot(manifest)


@pytest.mark.parametrize("name", ["dataset.sqlite", "e1_score_snapshot.json"])
def test_verify_fails_when_file_hash_differs(tmp_path, name):
    manifest = make_snapshot(tmp_path, synthetic_prices())
    target = manifest.parent / name
    _writable(target)
    with target.open("ab") as fh:
        fh.write(b" ")
    with pytest.raises(SnapshotIntegrityError, match="hash 불일치"):
        verify_snapshot(manifest)


def test_runner_fails_closed_on_tampered_snapshot_and_writes_nothing(tmp_path):
    manifest = make_snapshot(tmp_path, synthetic_prices())
    target = manifest.parent / "dataset.sqlite"
    _writable(target)
    con = sqlite3.connect(target)
    con.execute(
        "UPDATE etf_daily_price SET close = close * 2 WHERE date = ?", (CUTOFF,)
    )
    con.commit()
    con.close()
    out = tmp_path / "run"
    with pytest.raises(SnapshotIntegrityError):
        _run(manifest, out)
    assert not (out / cli.RESULT_FILENAME).exists()
    assert not (out / cli.RUN_MANIFEST_FILENAME).exists()


def test_runner_requires_snapshot_manifest_argument(tmp_path):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--cutoff", CUTOFF, "--out-dir", str(tmp_path)])
    assert exc.value.code == 2


def test_runner_rejects_cutoff_other_than_manifest(tmp_path):
    manifest = make_snapshot(tmp_path, synthetic_prices())
    with pytest.raises(SnapshotIntegrityError, match="cutoff"):
        cli.main(
            [
                "--snapshot-manifest",
                str(manifest),
                "--cutoff",
                "2020-12-19",
                "--out-dir",
                str(tmp_path / "run"),
                "--allow-dirty-code",
            ]
        )


def test_runner_refuses_legacy_result_dir(tmp_path):
    manifest = make_snapshot(tmp_path, synthetic_prices())
    with pytest.raises(RuntimeError, match="legacy"):
        _run(manifest, cli.OUT_DIR)


def test_runner_refuses_dirty_code_without_explicit_flag(tmp_path, monkeypatch):
    manifest = make_snapshot(tmp_path, synthetic_prices())
    monkeypatch.setattr(cli, "code_provenance", lambda: {"git": {"code_clean": False}})
    with pytest.raises(RuntimeError, match="commit"):
        cli.main(
            [
                "--snapshot-manifest",
                str(manifest),
                "--cutoff",
                CUTOFF,
                "--out-dir",
                str(tmp_path / "run"),
            ]
        )


# --- 라이브 DB 차단 -------------------------------------------------------------


def test_guard_blocks_unlisted_sqlite_paths_and_restores(tmp_path):
    allowed = tmp_path / "ok.sqlite"
    other = tmp_path / "live.sqlite"
    real = sqlite3.connect
    with guard_sqlite_paths([allowed]):
        sqlite3.connect(allowed).close()
        with pytest.raises(SnapshotGuardError):
            sqlite3.connect(str(other))
        with pytest.raises(SnapshotGuardError):
            sqlite3.connect(f"file:{other}?mode=ro", uri=True)
    assert sqlite3.connect is real


def test_session_serves_working_copy_and_blocks_live_reads(tmp_path):
    live = write_live_db(tmp_path / "live.sqlite", synthetic_prices())
    manifest = make_snapshot(tmp_path, {}, live=live)
    work = tmp_path / "work"
    work.mkdir()
    with snapshot_session(manifest, cutoff=CUTOFF, work_dir=work) as snap:
        assert load_prices(snap.work_db)[KODEX200_TICKER]
        with pytest.raises(SnapshotGuardError):
            load_prices(live)
    assert not snap.work_db.exists(), "작업 사본은 세션 종료 시 지워져야 한다"


# --- 검증 기준 1·2·3: 결정성 · 라이브 변경 무관 --------------------------------


def _manifest_of(out: Path) -> dict:
    return json.loads((out / cli.RUN_MANIFEST_FILENAME).read_text("utf-8"))


def _data_view(out: Path) -> dict:
    """결과 중 **데이터에서 나온** 부분 — 기준일별 IC·표본 수와 평가일."""
    payload = json.loads((out / cli.RESULT_FILENAME).read_text("utf-8"))
    return {
        r["signal_date"]: (r["ic_filter"], r["n_filter"], r["top_decile_mean"])
        for r in payload["per_date"]
    }


def test_same_snapshot_same_result_even_after_live_db_changes(tmp_path):
    prices = synthetic_prices()
    live = write_live_db(tmp_path / "live.sqlite", prices)
    manifest = make_snapshot(tmp_path, prices, baseline_id="s1", live=live)

    assert _run(manifest, tmp_path / "run1") == 0
    assert _run(manifest, tmp_path / "run2") == 0
    r1, r2 = _manifest_of(tmp_path / "run1"), _manifest_of(tmp_path / "run2")
    assert r1["result"]["canonical_sha256"] == r2["result"]["canonical_sha256"]
    assert tool.compare_run_manifests(r1, r2)["identical"] is True

    # 라이브 DB: 새 날짜 추가 + 평가 구간의 과거 행 변경
    con = sqlite3.connect(live)
    con.execute(
        "INSERT INTO etf_daily_price (ticker, date, close, source, fetched_at) "
        "SELECT ticker, '2021-01-04', close, 'test', 'x' FROM etf_daily_price "
        "WHERE date = ?",
        (CUTOFF,),
    )
    con.execute(
        "UPDATE etf_daily_price SET close = close * 1.7 "
        "WHERE ticker LIKE 'GOOD0%' AND date >= '2020-08-01'"
    )
    con.commit()
    con.close()

    assert _run(manifest, tmp_path / "run3") == 0
    r3 = _manifest_of(tmp_path / "run3")
    assert r3["result"]["canonical_sha256"] == r1["result"]["canonical_sha256"]
    assert r3["evaluation"]["dates"] == r1["evaluation"]["dates"]
    assert r3["dataset"]["dataset_sha256"] == r1["dataset"]["dataset_sha256"]
    assert _data_view(tmp_path / "run3") == _data_view(tmp_path / "run1")

    # 대조군 A (기준 3): 과거 행 변경을 담은 새 snapshot — 같은 평가일인데 IC 가 달라진다.
    s2 = make_snapshot(tmp_path, prices, baseline_id="s2", live=live)
    assert _run(s2, tmp_path / "run4") == 0
    r4 = _manifest_of(tmp_path / "run4")
    assert r4["dataset"]["dataset_sha256"] != r1["dataset"]["dataset_sha256"]
    assert r4["evaluation"]["dates"] == r1["evaluation"]["dates"]
    v1, v4 = _data_view(tmp_path / "run1"), _data_view(tmp_path / "run4")
    assert v4 != v1, "바뀐 과거 행이 평가 지표에 실제로 쓰여야 대조가 성립한다"

    # 대조군 B (기준 2): 새 날짜까지 담은 snapshot — 평가일 자체가 달라진다.
    s3 = make_snapshot(
        tmp_path, prices, baseline_id="s3", live=live, cutoff="2021-01-04"
    )
    assert _run(s3, tmp_path / "run5", cutoff="2021-01-04") == 0
    r5 = _manifest_of(tmp_path / "run5")
    assert r5["evaluation"]["dates"] != r1["evaluation"]["dates"]
    assert "2020-11-20" in r5["evaluation"]["dates"]
    assert "2020-11-20" not in r1["evaluation"]["dates"]


def test_run_manifest_records_full_provenance(tmp_path):
    manifest = make_snapshot(tmp_path, synthetic_prices())
    assert _run(manifest, tmp_path / "run") == 0
    rm = _manifest_of(tmp_path / "run")
    assert rm["official"] is False, "limit·skip-e1·dirty 허용 실행은 공식이 아니다"
    assert rm["dataset"]["data_cutoff"] == CUTOFF
    assert rm["dataset"]["manifest_sha256"] == file_sha256(manifest)
    assert rm["code"]["git"].get("head") or rm["code"]["git"].get("error")
    frozen = rm["code"]["frozen_modules"]["app/ml_relative_upside_model.py"]
    assert frozen["raw_sha256"] and frozen["normalized_ast_sha256"]
    assert rm["environment"]["python"] and "torch" in rm["environment"]["packages"]
    assert rm["environment"]["requirements_txt_sha256"]
    assert rm["run_arguments"]["cutoff"] == CUTOFF
    assert rm["evaluation"]["count"] == len(rm["evaluation"]["dates"]) == 3
    result = tmp_path / "run" / cli.RESULT_FILENAME
    assert rm["result"]["file_sha256"] == file_sha256(result)
    payload = json.loads(result.read_text("utf-8"))
    assert payload["dataset"]["dataset_sha256"] == rm["dataset"]["dataset_sha256"]
    assert (
        payload["dataset"]["manifest_canonical_sha256"]
        == rm["dataset"]["manifest_canonical_sha256"]
    )
    # 결과에 영향을 주는데 손 목록에 없던 모듈도 hash 가 남는다 (리뷰 P2).
    assert "app/market_regime.py" in rm["code"]["evaluator_modules"]
    assert rm["code"]["gate_paths"] == ["app", "scripts", "requirements.txt"]
    m = json.loads(manifest.read_text("utf-8"))
    assert m["tables"]["market_refresh_log"].get("date_column") == "asof"
    assert m["tables"]["etf_master"]["date_column"] == "last_seen_at"
    assert m["tables"]["etf_master"]["min_date"]
    for leftover in ("_work_dataset.sqlite", WORKING_E1_NAME, cli.REPLAY_DB_NAME):
        assert not (tmp_path / "run" / leftover).exists()


def test_e1_reads_verified_working_copy_not_bundle_or_live_file(tmp_path, monkeypatch):
    manifest = make_snapshot(tmp_path, synthetic_prices())
    seen: list[Path] = []
    real_gate = cli.run_e1_gate

    def _spy(prices, *, log=None, snapshot_path):
        seen.append(snapshot_path)
        assert snapshot_path.name == WORKING_E1_NAME
        assert file_sha256(snapshot_path) == file_sha256(
            manifest.parent / "e1_score_snapshot.json"
        )
        return real_gate(prices, log=log, snapshot_path=snapshot_path)

    monkeypatch.setattr(cli, "run_e1_gate", _spy)
    assert _run(manifest, tmp_path / "run", e1=True) == 0
    assert len(seen) == 1
    payload = json.loads((tmp_path / "run" / cli.RESULT_FILENAME).read_text("utf-8"))
    assert payload["e1"]["snapshot_asof"] == CUTOFF, "bundle 의 E1 JSON 을 읽어야 한다"


def test_input_changed_during_run_writes_nothing(tmp_path, monkeypatch):
    """실행 중 봉인 원본이 바뀌면 결과·meta·run_manifest 를 하나도 쓰지 않는다."""
    manifest = make_snapshot(tmp_path, synthetic_prices())
    real_gate = cli.preflight_gate

    def _tamper(records, n1):
        target = manifest.parent / "e1_score_snapshot.json"
        _writable(target)
        with target.open("ab") as fh:
            fh.write(b" ")
        return real_gate(records, n1)

    monkeypatch.setattr(cli, "preflight_gate", _tamper)
    out = tmp_path / "run"
    with pytest.raises(SnapshotIntegrityError):
        _run(manifest, out)
    for name in (cli.RESULT_FILENAME, cli.RUN_META_FILENAME, cli.RUN_MANIFEST_FILENAME):
        assert not (out / name).exists(), name


def test_code_gate_sees_uncommitted_change_in_any_app_module(tmp_path):
    """손 목록에 없는 모듈(예: regime 판정)의 미커밋 수정도 게이트가 잡는다."""
    repo = tmp_path / "repo"
    (repo / "app").mkdir(parents=True)
    (repo / "app" / "market_regime.py").write_text("X = 1\n", "utf-8")
    (repo / "requirements.txt").write_text("", "utf-8")
    for cmd in (
        ["init", "-q"],
        ["add", "."],
        ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
    ):
        subprocess.run(["git", *cmd], cwd=repo, check=True)
    assert git_state(("app", "scripts", "requirements.txt"), repo)["code_clean"] is True
    (repo / "app" / "market_regime.py").write_text("X = 2\n", "utf-8")
    state = git_state(("app", "scripts", "requirements.txt"), repo)
    assert state["code_clean"] is False
    assert state["dirty_paths"] == ["app/market_regime.py"]


# --- 정규화 AST hash -----------------------------------------------------------


def test_normalized_ast_ignores_docstring_and_comment_but_not_logic():
    base = '"""원래 설명."""\n\n\ndef f(x):\n    """함수 설명."""\n    return x + 1\n'
    doc = '"""정정한 설명."""\n\n\ndef f(x):\n    # 주석\n    return x + 1\n'
    logic = '"""원래 설명."""\n\n\ndef f(x):\n    return x + 2\n'
    h = normalized_ast_sha256_from_source
    assert h(base) == h(doc)
    assert h(base) != h(logic)
