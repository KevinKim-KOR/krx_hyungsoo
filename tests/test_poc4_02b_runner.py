"""POC4-02B 러너 — 새 폴더 · 봉인 전후 검증 · 라이브 5경로 · progress 재개 · 두 실행 비교 (PLAN §9 · §11).
보호 쪽(재개 우회 차단 · 원자 기록 · 네트워크 0 · 다른 DB 연결 거부)은 `test_poc4_02b_runner_guards.py`.

tmp_path 의 KRX 스키마 고정 DB(300거래일)와 tmp 라이브 루트만 쓴다. 봉인 DB·라이브 DB 는 열지 않는다.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from app import krx_sealed_reader as reader
from app import ml_ew_events as ew_events
from app import ml_ew_report as ew_report
from app import ml_ew_reproduce as ew_repro
from app.ml_baseline_snapshot import SnapshotIntegrityError, file_sha256
from scripts import run_poc4_02b_early_warning as runner
from tests._krx_fixture import build_sealed_db, krx_row, trading_dates
from tests.test_poc4_02b_reproduce import make_live_root

N_DAYS = 300
# 069500 일간 충격 (index → %) — 사전 창 없음(60) · 평가 사건(180 · 230) · 잘림(283~)
CRASHES = {
    **{i: -2.2 for i in range(60, 64)},
    **{i: -1.9 for i in range(180, 185)},
    **{i: -2.4 for i in range(230, 234)},
    **{i: -2.1 for i in range(283, 288)},
}
OTHERS = (
    ("111111", "TEST 일반", 0, N_DAYS),
    ("222222", "TEST 인버스", 0, N_DAYS),
    ("333333", "TEST 레버리지", 0, N_DAYS),
    ("444444", "TEST 폐지", 0, 200),
    ("555555", "TEST 신규", 100, N_DAYS),
)


def _walk(rng: random.Random, n: int, start: float, crashes=None) -> list[float]:
    out, c = [], start
    for i in range(n):
        shock = (crashes or {}).get(i)
        c *= 1 + (shock / 100 if shock is not None else rng.gauss(0.0004, 0.007))
        out.append(round(c, 2))
    return out


def build_krx_fixture(path: Path) -> str:
    days = trading_dates(N_DAYS)
    rng = random.Random(20260925)
    by_date: dict[str, list[dict]] = {d: [] for d in days}
    series = [("069500", "KODEX 200", 0, N_DAYS, _walk(rng, N_DAYS, 150.0, CRASHES))]
    for code, name, lo, hi in OTHERS:
        series.append((code, name, lo, hi, _walk(rng, hi - lo, 80.0)))
    for code, name, lo, hi, closes in series:
        prev = None
        for d, c in zip(days[lo:hi], closes):
            nav = round(c * (1 + rng.gauss(0, 0.002)), 2)
            vol = rng.randint(1000, 9000)
            by_date[d].append(krx_row(code, d, c, prev, volume=vol, nav=nav, name=name))
            prev = c
    return build_sealed_db(path, by_date)


@pytest.fixture(scope="module")
def sealed(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("krx") / "krx.sqlite"
    build_krx_fixture(path)
    return path


@pytest.fixture
def live(tmp_path) -> Path:
    root = tmp_path / "live"
    make_live_root(root)
    return root


def _args(out: Path, sealed: Path, live: Path, *extra: str):
    argv = [
        "run",
        "--out-dir",
        str(out),
        "--sealed-db",
        str(sealed),
        "--live-root",
        str(live),
    ]
    return runner.build_parser().parse_args(argv + list(extra))


def _files(run_dir: Path) -> dict:
    return {p.name: file_sha256(p) for p in sorted((run_dir / "progress").iterdir())}


@pytest.fixture(scope="module")
def fresh_pair(tmp_path_factory, sealed):
    """재개 없이 처음부터 두 번 실행 (같은 tmp 라이브 루트)."""
    base = tmp_path_factory.mktemp("pair")
    root = base / "live"
    make_live_root(root)
    out = [base / "run1", base / "run2"]
    results = [runner.run(_args(o, sealed, root)) for o in out]
    return {"dirs": out, "results": results, "live": root}


def test_full_run_payload_contract(fresh_pair, sealed):
    result = fresh_pair["results"][0]
    run_dir = fresh_pair["dirs"][0]
    assert result["schema"] == "poc4_02b_early_warning.v1"
    assert result["official"] is False  # tmp 봉인·tmp 라이브 → 공식 아님
    assert result["price_basis"] == "KRX_BASEPRICE_CHAIN"
    assert result["legacy_reproduction"]["status"] == ew_repro.EXACT_MATCH
    assert result["source"]["before"] == result["source"]["after"]
    assert result["purge_embargo"] == "NOT_APPLICABLE_TO_NO_FIT_RULE"
    assert result["note"] == "TRACK_B_PASS != PUSH_ACTIVATION"
    assert result["criteria"]["11"]["value"] is None
    assert set(result["criteria"]) == {str(i) for i in range(1, 12)}
    assert result["verdict"] in (
        ew_report.REJECT,
        ew_report.INCONCLUSIVE,
        ew_report.PENDING,
    )
    diag = result["diagnostics"]
    assert diag["EXACT_K_DIAGNOSTIC"]["LOOKAHEAD"] is True
    assert diag["LEGACY_FULL_SAMPLE_DIAGNOSTIC"]["LOOKAHEAD"] is True
    statuses = result["events"]["by_status"]
    assert statuses.get(ew_events.EVALUABLE, 0) >= 2
    assert statuses.get(ew_events.PRE_WINDOW_UNAVAILABLE, 0) >= 1
    assert statuses.get(ew_events.RIGHT_CENSORED_EVENT, 0) >= 1
    assert set(result["metrics"]) == {"EARLY_PIT", "EARLY_FS", "REACTIVE"}
    assert result["random_null"]["EARLY_PIT"]["repeats"] == 1000
    assert result["calendar"]["trading_days"] == N_DAYS
    assert set(result["universe_axis_pit_minus_fs"]) == {
        "etf_universe_down_ratio",
        "breadth_deterioration_proxy",
        "etf_universe_median_return_5d",
        "nav_discount_abs_avg",
    }
    # 결과·진행 기록·manifest·meta · 재현 사본은 지워졌다
    names = sorted(p.name for p in run_dir.iterdir())
    assert names == [
        "poc4_02b_early_warning_result.json",
        "progress",
        "run_manifest.json",
        "run_meta.json",
    ]
    assert sorted(_files(run_dir)) == sorted(f"{s}.json" for s in runner.STAGES)
    meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert (
        meta["resumed"] is False
        and meta["live_paths_before"] == meta["live_paths_after"]
    )
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert (
        manifest["fingerprint"]["components"]["options"]["skip_legacy_reproduction"]
        is False
    )
    assert "code" in manifest and "environment" in manifest
    blob = json.dumps(result)
    assert str(run_dir) not in blob  # 실행 폴더 경로는 canonical 에 없다


def test_two_fresh_runs_identical_and_compare(fresh_pair):
    r1, r2 = fresh_pair["results"]
    assert (
        r1["determinism"]["canonical_sha256"] == r2["determinism"]["canonical_sha256"]
    )
    rec = runner.compare(*fresh_pair["dirs"])
    assert rec["criterion_11"]["value"] is True
    # tmp 실행은 공식이 아니다 → 판정 값을 붙이지 않는다 (공식 쌍은 guards 테스트)
    assert rec["official_both"] is False
    assert rec["final_verdict"] == runner.NOT_OFFICIAL_FINAL
    assert (fresh_pair["dirs"][1] / runner.COMPARE_FILENAME).is_file()
    with pytest.raises(FileExistsError):
        runner.compare(*fresh_pair["dirs"])  # 비교 기록도 덮어쓰지 않는다
    with pytest.raises(runner.RunError, match="같은 실행 폴더"):
        runner.compare(fresh_pair["dirs"][0], fresh_pair["dirs"][0])


def _interrupt(*_a, **_k):
    raise KeyboardInterrupt("중단 흉내")


def test_resume_after_interrupt_equals_uninterrupted(
    tmp_path, sealed, fresh_pair, monkeypatch
):
    live = fresh_pair["live"]  # 같은 라이브 루트 — 결과에 경로가 들어가므로
    out = tmp_path / "run"
    original = ew_report.build_null_stage
    monkeypatch.setattr(ew_report, "build_null_stage", _interrupt)
    with pytest.raises(KeyboardInterrupt):
        runner.run(_args(out, sealed, live))
    done = _files(out)
    assert sorted(done) == [
        "axes.json",
        "events.json",
        "reproduce.json",
        "signals.json",
    ]
    assert not (out / runner.RESULT_FILENAME).exists()
    monkeypatch.setattr(ew_report, "build_null_stage", original)
    result = runner.run(_args(out, sealed, live, "--resume"))
    after = _files(out)
    assert {k: after[k] for k in done} == done  # 완료된 단계는 다시 쓰지 않는다
    assert sorted(after) == sorted(f"{s}.json" for s in runner.STAGES)
    fresh = fresh_pair["results"][0]
    assert (
        result["determinism"]["canonical_sha256"]
        == fresh["determinism"]["canonical_sha256"]
    )
    assert result == fresh
    meta = json.loads((out / runner.META_FILENAME).read_text())
    manifest = json.loads((out / runner.MANIFEST_FILENAME).read_text())
    assert meta["resumed"] is True
    assert meta["live_paths_at_start"] == manifest["live_paths_at_start"]
    with pytest.raises(runner.RunError, match="처음부터"):
        runner.compare(fresh_pair["dirs"][0], out)
    with pytest.raises(runner.RunError, match="이미 완료"):
        runner.run(_args(out, sealed, live, "--resume"))


def test_resume_refuses_different_fingerprint_and_tampered_record(
    tmp_path, sealed, live, monkeypatch
):
    out = tmp_path / "run"
    original = ew_events.build_event_stage
    monkeypatch.setattr(ew_events, "build_event_stage", _interrupt)
    with pytest.raises(KeyboardInterrupt):
        runner.run(_args(out, sealed, live))
    monkeypatch.setattr(ew_events, "build_event_stage", original)
    with pytest.raises(runner.RunError, match="입력 지문이 다르다"):
        runner.run(_args(out, sealed, live, "--resume", "--skip-legacy-reproduction"))
    real_threshold = ew_events.LABEL_THRESHOLD
    monkeypatch.setattr(ew_events, "LABEL_THRESHOLD", -0.07)  # 설정 상수가 바뀌면 중단
    with pytest.raises(runner.RunError, match="config_sha256"):
        runner.run(_args(out, sealed, live, "--resume"))
    monkeypatch.setattr(ew_events, "LABEL_THRESHOLD", real_threshold)
    rec_path = out / "progress" / "signals.json"
    rec = json.loads(rec_path.read_text(encoding="utf-8"))
    rec["fingerprint_sha256"] = "f" * 64
    rec_path.write_text(json.dumps(rec), encoding="utf-8")
    with pytest.raises(runner.RunError, match="진행 기록"):
        runner.run(_args(out, sealed, live, "--resume"))
    rec_path.write_text(json.dumps(rec)[:500], encoding="utf-8")  # 반쪽 기록(손상)
    with pytest.raises(runner.RunError, match="읽을 수 없다.*signals.json"):
        runner.run(_args(out, sealed, live, "--resume"))
    assert not (out / runner.RESULT_FILENAME).exists()


def test_resume_and_new_run_folder_rules(tmp_path, sealed, live):
    with pytest.raises(runner.RunError, match="run_manifest.json"):
        runner.run(_args(tmp_path / "missing", sealed, live, "--resume"))
    existing = tmp_path / "exists"
    existing.mkdir()
    with pytest.raises(SnapshotIntegrityError, match="이미 있다"):
        runner.run(_args(existing, sealed, live))
    with pytest.raises(SnapshotIntegrityError, match="legacy"):
        runner.run(_args(runner.FORBIDDEN_ROOT / "x", sealed, live))


def test_live_path_change_fails_without_result(tmp_path, sealed, live, monkeypatch):
    out = tmp_path / "run"
    real = ew_events.build_event_stage

    def touch_live_log(axes, signals):
        with open(
            live / "logs" / "oci_market_data_batch.log", "a", encoding="utf-8"
        ) as fh:
            fh.write("changed\n")  # tmp 라이브 루트 — 실행 중 변경 흉내
        return real(axes, signals)

    monkeypatch.setattr(ew_events, "build_event_stage", touch_live_log)
    with pytest.raises(runner.RunError, match="oci_market_data_batch.log"):
        runner.run(_args(out, sealed, live))
    assert not (out / runner.RESULT_FILENAME).exists()
    assert not (out / runner.META_FILENAME).exists()
    # 결과 payload 는 progress 에도 남지 않는다 · 실패 표시 → 재개 거부 (재개로 결과를 만들 수 없다)
    assert not (out / "progress" / "report.json").exists()
    mark = json.loads((out / runner.GUARD_FAILED_FILENAME).read_text(encoding="utf-8"))
    assert mark["reason"] == "LIVE_PATHS_CHANGED"
    assert mark["detail"]["changed"] == ["logs/oci_market_data_batch.log"]
    monkeypatch.setattr(ew_events, "build_event_stage", real)
    with pytest.raises(runner.RunError, match="보호 검사에 실패"):
        runner.run(_args(out, sealed, live, "--resume"))
    assert not (out / runner.RESULT_FILENAME).exists()


def test_sealed_source_change_fails_before_result(tmp_path, sealed, live, monkeypatch):
    out = tmp_path / "run"
    real = reader.verify_sealed_source
    calls = []

    def verify(path, *a, **k):
        got = real(path, *a, **k)
        calls.append(1)
        if len(calls) > 1:
            got = {**got, "file_sha256": "changed"}
        return got

    monkeypatch.setattr(reader, "verify_sealed_source", verify)
    with pytest.raises(reader.SealedSourceError, match="file_sha256"):
        runner.run(_args(out, sealed, live, "--skip-legacy-reproduction"))
    assert not (out / runner.RESULT_FILENAME).exists()
    assert not (out / "progress" / "report.json").exists()
    mark = json.loads((out / runner.GUARD_FAILED_FILENAME).read_text(encoding="utf-8"))
    assert mark["reason"] == "SEALED_SOURCE_CHANGED"
    monkeypatch.setattr(reader, "verify_sealed_source", real)
    with pytest.raises(runner.RunError, match="보호 검사에 실패"):
        runner.run(_args(out, sealed, live, "--skip-legacy-reproduction", "--resume"))


def test_skip_legacy_reproduction_and_report_never_written(tmp_path, sealed, live):
    report = live / ew_repro.REPORT_REL
    live_db = live / ew_repro.LIVE_DB_REL
    before = (file_sha256(report), report.stat().st_mtime_ns, file_sha256(live_db))
    result = runner.run(
        _args(tmp_path / "run", sealed, live, "--skip-legacy-reproduction")
    )
    assert result["legacy_reproduction"]["status"] == ew_repro.SKIPPED
    assert result["official"] is False
    assert (
        file_sha256(report),
        report.stat().st_mtime_ns,
        file_sha256(live_db),
    ) == before


def test_main_cli_prints_summary(tmp_path, sealed, live, capsys):
    argv = ["run", "--out-dir", str(tmp_path / "run"), "--sealed-db", str(sealed)]
    assert (
        runner.main(argv + ["--live-root", str(live), "--skip-legacy-reproduction"])
        == 0
    )
    summary = json.loads(capsys.readouterr().out)
    assert summary["legacy_reproduction"] == "SKIPPED" and "verdict" in summary
