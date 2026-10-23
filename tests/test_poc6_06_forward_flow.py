"""POC6-06 — 초기 조회 · 학습 · 전향 기록 · 마감 경계 · 월별 학습 · 방법별 실패 · 보관 흐름 시험.

가짜 05 보관소 · 가짜 FDR 응답(결정적 가격) · 가짜 시계만 쓴다(라이브 DB · state · 외부 조회 · SSH 0).
학습은 PC CPU 의 실제 sklearn · torch 로 한다(02 recipe 그대로). 세계는 모듈당 한 번 만들고 시험마다 복사한다.
계약 출처: 설계 V1 §3 ~ §10 · PLAN 판정(2026-10-22) §2 ~ §7.
"""

from __future__ import annotations

import json
import shutil
from collections import Counter
from datetime import timedelta

import pandas as pd
import pytest

from app.d20_pooled import mlp
from app.d20_pooled import study as S
from app.forward_compare import archive, bootstrap, forward, records, report, training
from app.forward_compare import cohort as C
from app.forward_compare import models as M
from app.forward_compare import protocol as P
from app.ml_evidence import store
from app.reentry_review import model as m06
from tests.test_poc6_06_forward_core import D, TICKERS, d20, daily, series, z

FAIL, SHORT = "488720", "494670"


class Clock:
    def __init__(self, t, step=timedelta(milliseconds=1)):
        self.t, self.step = t, step

    def __call__(self):
        v = self.t
        self.t += self.step
        return v


def fake_fetcher(calls: list):
    def get(t, start, end):
        calls.append(t)
        if t == FAIL:
            raise TimeoutError("시험 시간 초과")
        rows = series(t, start, end)
        if t == SHORT:
            rows = rows[-200:]
        return pd.DataFrame(
            [r[1:] for r in rows],
            columns=["Open", "High", "Low", "Close", "Volume", "Change"],
            index=pd.to_datetime([r[0] for r in rows]),
        )

    return get


def write_cohort(root):
    body = P.doc(
        "cohort",
        cohort_id=P.COHORT_ID,
        tickers=list(TICKERS),
        aux_groups=P.aux_groups(list(TICKERS)),
    )
    P.write_once(C.path(root), P.dumps(body))
    return body


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    w = tmp_path_factory.mktemp("poc6_06_world")
    ev, root = w / "ev", w / "r"
    calls: list = []
    status, meta = bootstrap.fetch(
        root,
        write_cohort(root),
        start="2025-01-01",
        clock=Clock(z(2026, 10, 22, 12)),
        fetcher=fake_fetcher(calls),
    )
    daily(ev, D, z(2026, 10, 23, 0, 45), z(2026, 10, 23, 0, 50))
    out = forward.run(root, ev, clock=Clock(z(2026, 10, 23, 1)), code_commit="test")
    return {"dir": w, "fetch": (status, meta, calls), "run": out}


@pytest.fixture
def world(base, tmp_path):
    shutil.copytree(base["dir"], tmp_path / "w")
    return tmp_path / "w" / "ev", tmp_path / "w" / "r"


def latest_model(root):
    folder, meta = training.versions(root)[-1]
    return folder, meta


# ── 초기 조회 ──────────────────────────────────────────────────────────────


def test_bootstrap_one_request_per_ticker_no_retry_and_refuses_second(base, world):
    status, meta, calls = base["fetch"]
    assert status == "PARTIAL" and calls == list(TICKERS)  # 0015K0 그대로 · 재시도 0
    log = {e["ticker"]: e for e in meta["log"]}
    assert log[FAIL]["status"] == "FAILED" and log[FAIL]["timeout"] is True
    assert (
        log["0015K0"]["dropped_in_progress"] == 1
        and log["0015K0"]["returned_last"] == "2026-10-21"
    )
    assert (
        meta["requested_range"] == ["2025-01-01", "2026-10-22"] and meta["retries"] == 0
    )
    ev, root = world
    with pytest.raises(bootstrap.BootstrapRefused):
        bootstrap.fetch(
            root,
            C.load(root),
            start="2025-01-01",
            clock=Clock(z(2026, 10, 24)),
            fetcher=None,
        )


# ── 초기 학습 · 저장 · 복원(설계 §4 · §5 · 판정 §5) ─────────────────────────────


def test_initial_training_boundary_restore_and_equals_existing_functions(base, world):
    ev, root = world
    assert base["run"]["training"]["decision"] == "INITIAL"
    folder, meta = latest_model(root)
    assert {m: v["status"] for m, v in meta["methods"].items()} == dict.fromkeys(
        P.METHODS, "OK"
    )
    assert all(v["ok"] for v in meta["restore_check"].values())
    assert FAIL not in meta["trainable"] and SHORT not in meta["trainable"]
    assert set(meta["data_short"]) == {FAIL, SHORT} and len(meta["trainable"]) == 22
    rows = training.load_examples(root, meta["examples"])
    started = store.parse_iso(meta["training_started_at"])
    assert all(r["target_end"] < D for r in rows) and meta["boundary_D"] == D
    assert all(store.parse_iso(r["available_at"]) <= started for r in rows)
    assert len({(r["ticker"], r["date"]) for r in rows}) == len(rows)
    assert {r["ticker"] for r in rows} == set(meta["trainable"])
    assert M.hashes(rows) == meta["hashes"]
    loaded = M.Loaded(folder, meta)
    t = "122090"
    mine = [r for r in rows if r["ticker"] == t]
    x = mine[-1]["x"]
    ridge = m06.fit_predict([r["x"] for r in mine], [r["y"] for r in mine], [x])[0]
    assert M.clip(loaded.raw("RIDGE", t, x)) == pytest.approx(ridge, abs=1e-12)
    assert loaded.raw("MEDIAN", t, x) == m06.median([r["y"] for r in mine])
    n_d = Counter(r["date"] for r in rows)  # 02 `block_sets` 와 같은 1/n_d(독립 계산)
    X, y, w = (
        [r["x"] for r in rows],
        [r["y"] for r in rows],
        [1 / n_d[r["date"]] for r in rows],
    )
    assert M.date_weights(rows) == w
    assert loaded.raw("HGB", t, x) == float(S.fit_hgb(X, y, w).predict([x])[0])
    mean, std = mlp.standardize_params(X, w)
    want = mlp.train_predict(X, y, w, [x], mean, std, device="cpu")[0]
    assert abs(loaded.raw("MLP_CPU", t, x) - want) <= mlp.REPRO_TOL


def test_restore_check_detects_any_difference(world):
    ev, root = world
    folder, meta = latest_model(root)
    loaded = M.Loaded(folder, meta)
    rows = training.load_examples(root, meta["examples"])[: M.CHECK_ROWS]
    exact = {m: [loaded.raw(m, r["ticker"], r["x"]) for r in rows] for m in P.METHODS}
    assert all(v["ok"] for v in M.restore_check(loaded, rows, exact).values())
    near = {m: [v + 1e-13 for v in exact[m]] for m in ("RIDGE",)}
    assert (
        M.restore_check(loaded, rows, near)["RIDGE"]["ok"] is True
    )  # 식 계산 허용 1e-12
    off = {m: [v + 1e-9 for v in exact[m]] for m in P.METHODS}
    assert not any(v["ok"] for v in M.restore_check(loaded, rows, off).values())


def test_env_mismatch_and_tampered_file_fail_only_that_method(world, monkeypatch):
    ev, root = world
    folder, meta = latest_model(root)
    real = M.env()
    monkeypatch.setattr(M, "env", lambda: dict(real, **{"scikit-learn": "0.0"}))
    loaded = M.Loaded(folder, meta)
    got = {m: v["status"] for m, v in loaded.status.items()}
    assert got == {
        "MEDIAN": "OK",
        "RIDGE": "OK",
        "HGB": "ENV_MISMATCH",
        "MLP_CPU": "OK",
    }
    monkeypatch.setattr(M, "env", lambda: real)
    p = folder / "mlp_state.pt"
    data = bytearray(p.read_bytes())
    data[-1] ^= 0xFF  # 한 바이트 뒤집기
    p.write_bytes(bytes(data))
    assert M.Loaded(folder, meta).status["MLP_CPU"]["status"] == "FAILED"
    pred = M.Loaded(folder, meta).predict("122090", [0.0] * 5)
    assert pred["MLP_CPU"]["status"] == "FAILED" and pred["HGB"]["status"] == "OK"
    assert (
        M.Loaded(folder, meta).predict(SHORT, [0.0] * 5)["RIDGE"]["status"]
        == "DATA_SHORT"
    )


# ── 전향 기록 · 재실행 · 늦은 진단(설계 §6 · §7) ─────────────────────────────


def test_forward_record_times_and_same_day_rerun_returns_existing(base, world):
    ev, root = world
    out = base["run"]
    assert out["status"] == "OK" and out["record_type"] == "FORWARD_RESEARCH"
    doc = records.prediction_docs(root)[0]
    t = {
        k: store.parse_iso(v)
        for k, v in doc["times"].items()
        if k.endswith(("_at", "cutoff"))
    }
    assert (
        t["input_cutoff"] <= t["computation_started_at"] <= t["training_completed_at"]
    )
    assert t["training_completed_at"] <= t["prediction_started_at"] <= t["published_at"]
    assert t["published_at"] < t["close_cutoff_at"] == z(2026, 10, 23, 6, 30)
    assert {e["role"] for e in doc["entries"]} == {"PRIMARY"} and len(
        doc["entries"]
    ) == 24
    for e in doc["entries"]:
        src = e["input"]["source"]
        assert store.parse_iso(src["available_at"]) <= t["input_cutoff"]
        assert store.parse_iso(src["copied_at_pc"]) <= t["input_cutoff"]
    for e in doc["entries"]:
        for v in e["methods"].values():
            if v["status"] == "OK":
                assert -1.0 <= v["pred"] <= 0.0 and v["pred"] == M.clip(v["raw"])
    short = next(e for e in doc["entries"] if e["ticker"] == SHORT)
    assert {v["status"] for v in short["methods"].values()} == {"DATA_SHORT"}
    again = forward.run(root, ev, clock=Clock(z(2026, 10, 23, 2)))
    assert (
        again["status"] == "ALREADY_RECORDED"
        and len(records.prediction_docs(root)) == 1
    )
    assert {x["role"] for x in again["existing"]} == {"PRIMARY_EXISTS"}


def test_late_run_is_diagnostic_once_and_excluded(world):
    ev, root = world
    daily(ev, "2026-10-23", z(2026, 10, 24, 0, 45), z(2026, 10, 24, 0, 50))
    late = forward.run(
        root, ev, clock=Clock(z(2026, 10, 26, 8))
    )  # 월 17:00 KST > 15:30
    assert late["status"] == "SKIPPED_TOO_LATE" and late["record_type"] == "DIAGNOSTIC"
    again = forward.run(root, ev, clock=Clock(z(2026, 10, 26, 9)))
    assert again["status"] == "ALREADY_RECORDED"
    assert not any(k[1] == "2026-10-23" for k in records.primaries(root))


@pytest.mark.parametrize(
    "offset_us,kind", [(-1, "FORWARD_RESEARCH"), (0, "DIAGNOSTIC")]
)
def test_cutoff_boundary_is_strict(world, offset_us, kind):
    ev, root = world
    daily(ev, "2026-10-23", z(2026, 10, 24, 0, 45), z(2026, 10, 24, 0, 50))
    t = z(2026, 10, 26, 6, 30) + timedelta(microseconds=offset_us)
    out = forward.run(root, ev, clock=lambda: t)  # 멈춘 시계 = 공개 시각이 정확히 그 값
    assert (
        out["record_type"] == kind
        and out["close_cutoff_at"] == "2026-10-26T06:30:00.000000Z"
    )


def test_started_before_cutoff_but_published_after_is_diagnostic(world, monkeypatch):
    ev, root = world
    daily(ev, "2026-10-23", z(2026, 10, 24, 0, 45), z(2026, 10, 24, 0, 50))
    cutoff = z(2026, 10, 26, 6, 30)
    clock = Clock(cutoff - timedelta(seconds=30))
    real = M.Loaded.predict

    def slow(self, *a, **k):  # 예측 계산 중 마감이 지난다
        clock.t = max(clock.t, cutoff)
        return real(self, *a, **k)

    monkeypatch.setattr(M.Loaded, "predict", slow)
    out = forward.run(root, ev, clock=clock)
    doc = next(d for d in records.prediction_docs(root) if d["D"] == "2026-10-23")
    t = doc["times"]
    assert (
        store.parse_iso(t["computation_started_at"])
        < cutoff
        <= store.parse_iso(t["published_at"])
    )
    assert out["record_type"] == "DIAGNOSTIC" and {
        e["role"] for e in doc["entries"]
    } == {"DIAGNOSTIC"}
    assert not any(k[1] == "2026-10-23" for k in records.primaries(root))


def _cutoff_world(world):
    ev, root = world
    daily(ev, "2026-10-23", z(2026, 10, 24, 0, 45), z(2026, 10, 24, 0, 50))
    return ev, root, z(2026, 10, 26, 6, 30)


def test_slow_write_past_cutoff_is_not_published_as_forward(world, monkeypatch):
    ev, root, cutoff = _cutoff_world(world)
    clock = Clock(cutoff - timedelta(seconds=30))
    real = P.write_once

    def slow(
        path, data, before_link=None
    ):  # 임시 파일 쓰기 · fsync 가 마감을 넘김(검증자 r1 F1)
        if before_link is not None and "predictions" in path.parts:

            def late():
                clock.t = max(clock.t, cutoff + timedelta(seconds=1))
                return before_link()

            return real(path, data, late)
        return real(path, data, before_link)

    monkeypatch.setattr(P, "write_once", slow)
    out = forward.run(root, ev, clock=clock)
    assert out["record_type"] == "DIAGNOSTIC" and out["status"] == "SKIPPED_TOO_LATE"
    doc = next(d for d in records.prediction_docs(root) if d["D"] == "2026-10-23")
    assert (
        doc["record_type"] == "DIAGNOSTIC"
        and not records.receipt_path(doc["_path"]).exists()
    )
    assert not any(k[1] == "2026-10-23" for k in records.primaries(root))


def test_link_confirmed_after_cutoff_is_not_forward(world, monkeypatch):
    ev, root, cutoff = _cutoff_world(world)
    clock = Clock(cutoff - timedelta(seconds=30))
    real_link = P.os.link

    def link_then_stall(src, dst):  # 놓는 것까지는 마감 전 · 그 뒤 확인이 마감 뒤
        real_link(src, dst)
        if "predictions" in str(dst):
            clock.t = max(clock.t, cutoff)

    monkeypatch.setattr(P.os, "link", link_then_stall)
    out = forward.run(root, ev, clock=clock)
    assert out["status"] == "SKIPPED_TOO_LATE" and out["publication_confirmed"] is False
    doc = next(d for d in records.prediction_docs(root) if d["D"] == "2026-10-23")
    assert (
        doc["record_type"] == "FORWARD_RESEARCH"
        and doc["status"] == "FORWARD_CANDIDATE"
    )
    rec = P.read_json(records.receipt_path(doc["_path"]))  # 마감 뒤 확인도 남는다(무효)
    assert store.parse_iso(rec["confirmed_at"]) >= cutoff
    assert not any(k[1] == "2026-10-23" for k in records.primaries(root))
    monkeypatch.setattr(P.os, "link", real_link)
    before = sorted(p for p in root.rglob("*") if p.is_file())
    with pytest.raises(P.ClockBehind):  # 시계가 뒤로 감 — 아무것도 쓰지 않는다
        forward.run(root, ev, clock=Clock(cutoff - timedelta(minutes=5)))
    assert sorted(p for p in root.rglob("*") if p.is_file()) == before
    again = forward.run(root, ev, clock=Clock(cutoff + timedelta(minutes=5)))
    assert again["confirmed_earlier"] == []  # 영수증이 이미 있어 다시 확인하지 않는다
    assert not any(k[1] == "2026-10-23" for k in records.primaries(root))
    rep = report.build(root, C.load(root))
    assert rep["counts"]["unconfirmed_forward_records"] == 1


def test_publication_across_midnight_counts_the_confirmed_day(
    base, tmp_path, monkeypatch
):
    shutil.copytree(base["dir"], tmp_path / "w")
    ev, root = tmp_path / "w" / "ev", tmp_path / "w" / "r"
    for sub in (
        "predictions",
        "runs",
        "reports",
    ):  # 첫 전향 기록이 없는 폴더(모델은 둠)
        shutil.rmtree(root / sub)
    daily(ev, "2026-10-23", z(2026, 10, 24, 0, 45), z(2026, 10, 24, 0, 50))
    clock = Clock(z(2026, 10, 24, 14, 59, 59))  # 토 23:59:59 KST
    real_link = P.os.link

    def slow_link(src, dst):  # 놓는 데 2초 → 일 00:00:01 KST 에 공개 · 확인
        if "predictions" in str(dst):
            clock.t += timedelta(seconds=2)
        real_link(src, dst)

    monkeypatch.setattr(P.os, "link", slow_link)
    out = forward.run(root, ev, clock=clock)
    assert out["status"] == "OK" and out["publication_confirmed"] is True
    doc = records.prediction_docs(root)[0]
    assert P.kst_day(store.parse_iso(doc["times"]["published_at"])) == "2026-10-24"
    assert P.kst_day(store.parse_iso(doc["_receipt"]["confirmed_at"])) == "2026-10-25"
    rep = P.read_json(root / out["report"])
    assert rep["first_forward_published_kst"] == "2026-10-25"
    assert rep["first_interpretation_date"] == "2027-01-25"


def test_receipt_missing_is_confirmed_by_later_run_only_before_cutoff(world):
    ev, root = world
    doc = records.prediction_docs(root)[0]
    rp = records.receipt_path(doc["_path"])
    rp.unlink()  # 놓은 뒤 영수증 전에 멈춘 상황
    assert records.primaries(root) == {}
    out = forward.run(root, ev, clock=Clock(z(2026, 10, 23, 5)))  # 마감(06:30) 전
    (done,) = out["confirmed_earlier"]
    assert done["id"] == doc["id"] and done["D"] == D
    assert (
        z(2026, 10, 23, 5)
        <= store.parse_iso(done["confirmed_at"])
        < z(2026, 10, 23, 6, 30)
    )
    assert len(records.primaries(root)) == 24 and out["status"] == "ALREADY_RECORDED"
    assert P.read_json(rp)["how"] == "LATER_RUN_BEFORE_CUTOFF"


def test_receipt_missing_after_cutoff_stays_unconfirmed(world):
    ev, root = world
    doc = records.prediction_docs(root)[0]
    rp = records.receipt_path(doc["_path"])
    rp.unlink()  # 놓은 뒤 영수증 전에 멈췄고 · 다음 run 은 마감(06:30) 뒤
    out = forward.run(root, ev, clock=Clock(z(2026, 10, 23, 7)))
    (done,) = out["confirmed_earlier"]
    assert done["id"] == doc["id"] and done["unconfirmed"].startswith("마감 뒤")
    assert not rp.exists() and not any(k[1] == D for k in records.primaries(root))


def test_other_process_holding_the_lock_blocks_every_writer(world, tmp_path):
    import subprocess
    import sys

    ev, root = world
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import sys, time\n"
            "from app.forward_compare import protocol as P\n"
            "with P.run_lock(sys.argv[1]) as ok:\n"
            "    print(ok, flush=True)\n"
            "    time.sleep(30)\n",
            str(root),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout.readline().strip() == "True"
        before = sorted(p for p in root.rglob("*") if p.is_file())
        with pytest.raises(P.Busy):
            forward.run(root, ev, clock=Clock(z(2026, 10, 23, 2)))
        with pytest.raises(P.Busy):
            archive.register(root, ev, now=z(2026, 10, 23, 2), code_commit=None)
        with pytest.raises(P.Busy):
            C.select(root, ev, tmp_path / "none.sqlite", z(2026, 10, 23, 2))
        with pytest.raises(P.Busy):
            bootstrap.fetch(
                root, C.load(root), start="2025-01-01", clock=Clock(z(2026, 10, 24))
            )
        assert (
            sorted(p for p in root.rglob("*") if p.is_file()) == before
        )  # 아무것도 쓰지 않음
    finally:
        holder.kill()
        holder.wait()
    assert (
        forward.run(root, ev, clock=Clock(z(2026, 10, 23, 2)))["status"]
        == "ALREADY_RECORDED"
    )


def test_failed_restore_check_blocks_the_method(base, tmp_path, monkeypatch):
    shutil.copytree(base["dir"], tmp_path / "w")
    ev, root = tmp_path / "w" / "ev", tmp_path / "w" / "r"
    for sub in ("models", "examples", "predictions", "runs", "reports"):
        shutil.rmtree(root / sub)
    real = M.restore_check

    def broken(loaded, rows, before):
        out = real(loaded, rows, before)
        out["HGB"] = dict(out["HGB"], ok=False, max_abs_diff=0.05)
        return out

    monkeypatch.setattr(M, "restore_check", broken)
    forward.run(root, ev, clock=Clock(z(2026, 10, 23, 1)))
    folder, meta = latest_model(root)
    assert meta["methods"]["HGB"]["status"] == "RESTORE_MISMATCH"
    assert M.Loaded(folder, meta).status["HGB"]["status"] == "RESTORE_MISMATCH"
    e = next(
        x
        for x in records.prediction_docs(root)[0]["entries"]
        if x["ticker"] == "122090"
    )
    assert (
        e["methods"]["HGB"]["status"] == "RESTORE_MISMATCH"
        and e["methods"]["RIDGE"]["status"] == "OK"
    )


def test_repair_keeps_library_version_of_copied_files(base, tmp_path, monkeypatch):
    shutil.copytree(base["dir"], tmp_path / "w")
    ev, root = tmp_path / "w" / "ev", tmp_path / "w" / "r"
    for sub in ("models", "examples", "predictions", "runs", "reports"):
        shutil.rmtree(root / sub)
    real_fit, real_env = M.FITTERS["MLP_CPU"], M.env()

    def no_torch(rows):
        raise ImportError("torch 없음(시험)")

    monkeypatch.setitem(M.FITTERS, "MLP_CPU", no_torch)
    forward.run(root, ev, clock=Clock(z(2026, 10, 23, 1)))
    assert latest_model(root)[1]["methods"]["MLP_CPU"]["status"] == "NOT_RUN_ENV"
    monkeypatch.setitem(M.FITTERS, "MLP_CPU", real_fit)
    monkeypatch.setattr(M, "env", lambda: dict(real_env, **{"scikit-learn": "99.0"}))
    out = forward.run(root, ev, clock=Clock(z(2026, 10, 23, 2)))
    assert out["training"]["repair"]["fixed"] == ["MLP_CPU"]
    folder, meta = latest_model(root)
    assert meta["methods"]["HGB"]["env"]["scikit-learn"] == real_env["scikit-learn"]
    status = M.Loaded(folder, meta).status
    assert (
        status["HGB"]["status"] == "ENV_MISMATCH"
        and status["MLP_CPU"]["status"] == "OK"
    )


def test_rerun_same_day_is_not_a_valid_training_run(world, monkeypatch):
    ev, root = world
    seen = []
    real = training.ensure

    def spy(*a, **k):
        seen.append(k["valid_run"])
        return real(*a, **k)

    monkeypatch.setattr(training, "ensure", spy)
    forward.run(root, ev, clock=Clock(z(2026, 10, 23, 2)))  # D 의 주 기록이 이미 있음
    daily(ev, "2026-10-23", z(2026, 10, 26, 0, 45), z(2026, 10, 26, 0, 50))
    forward.run(root, ev, clock=Clock(z(2026, 10, 26, 1)))  # 새 기준일 = 유효
    assert seen == [False, True]


def test_weekend_run_uses_friday_and_monday_cutoff(world):
    ev, root = world
    out = forward.run(
        root, ev, clock=Clock(z(2026, 10, 24, 1))
    )  # 토 10:00 KST · 금 창 없음
    assert out["D"] == "2026-10-23" and out["status"] == "NO_INPUT"
    daily(ev, "2026-10-23", z(2026, 10, 24, 0, 45), z(2026, 10, 24, 1, 30))
    out = forward.run(root, ev, clock=Clock(z(2026, 10, 24, 2)))
    assert out["record_type"] == "FORWARD_RESEARCH" and out[
        "close_cutoff_at"
    ].startswith("2026-10-26T06:30")


def test_next_trading_day_unknown_is_pending_calendar(world):
    ev, root = world
    skip = tuple(
        f"2026-{d}" for d in ("10-23", "10-26", "10-27", "10-28", "10-29", "10-30")
    )
    skip += tuple(f"2026-11-{n:02d}" for n in range(2, 7))
    daily(ev, D, z(2026, 10, 23, 0, 46), z(2026, 10, 23, 0, 51), cal_skip=skip)
    out = forward.run(root, ev, clock=Clock(z(2026, 10, 23, 3)))
    assert (
        out["status"] == "PENDING_CALENDAR" and len(records.prediction_docs(root)) == 1
    )


# ── 성숙 · 월별 학습(설계 §5 · §8 · 판정 §4 · §5) ───────────────────────────


def test_maturity_then_monthly_training_once_with_logged_examples(world):
    ev, root = world
    _, first = latest_model(root)
    daily(ev, "2026-10-23", z(2026, 10, 24, 0, 45), z(2026, 10, 24, 0, 50))
    forward.run(
        root, ev, clock=Clock(z(2026, 10, 26, 8))
    )  # 10-23 = 늦은 진단(학습 제외 대상)
    daily(ev, "2026-11-19", z(2026, 11, 20, 0, 40), z(2026, 11, 20, 0, 41))
    a = forward.run(root, ev, clock=Clock(z(2026, 11, 20, 1)))
    assert a["maturity"]["counts"]["MATURED"] == 24
    assert (
        a["training"]["reason"] == "NO_NEW_TRAINING_EXAMPLES"
    )  # 목표 끝 11-19 = D → 아직 아님
    tg = records.targets(root)[("0015K0", D)]
    assert (
        tg["target"] == pytest.approx(d20("0015K0", D), abs=1e-12)
        and not tg["base_close_differs"]
    )

    def corrected(tk, rows):
        return [r[:4] + [r[4] * 1.1] + r[5:] for r in rows]

    daily(
        ev, "2026-11-20", z(2026, 11, 23, 0, 40), z(2026, 11, 23, 0, 41), edit=corrected
    )
    late = forward.run(
        root, ev, clock=Clock(z(2026, 11, 23, 8))
    )  # 마감 뒤 = 유효 실행 아님
    assert late["training"]["reason"].startswith("NOT_VALID_RUN")
    assert len(training.versions(root)) == 1  # 그 달 기회를 쓰지 않음
    daily(ev, "2026-11-23", z(2026, 11, 24, 0, 40), z(2026, 11, 24, 0, 41))
    b = forward.run(root, ev, clock=Clock(z(2026, 11, 24, 1)))
    assert b["training"]["decision"] == "MONTHLY" and b["training"]["new_logged"] == 22
    assert (
        records.targets(root)[("0015K0", D)] == tg
    )  # 첫 평가 목표 판 고정(정정 판 무시)
    folder, meta = latest_model(root)
    assert meta["parent"] == first["model_version"]
    assert (
        meta["origin_counts"]["LOGGED_FORWARD"] == 22
        and meta["boundary_D"] == "2026-11-23"
    )
    rows = training.load_examples(root, meta["examples"])
    logged = [r for r in rows if r["origin"] == "LOGGED_FORWARD"]
    assert {r["date"] for r in logged} == {D}  # 10-23 진단 · 11-19 · 11-20 미성숙 제외
    started = store.parse_iso(meta["training_started_at"])
    assert all(store.parse_iso(r["available_at"]) <= started for r in logged)
    assert all(r["target_end"] < meta["boundary_D"] for r in rows)
    ex = P.read_json(root / meta["examples"]["path"])
    assert (
        ex["initial_examples"] == first["examples"] and len(ex["rows"]) == 22
    )  # 초기 예제 = 참조
    daily(ev, "2026-11-24", z(2026, 11, 25, 0, 40), z(2026, 11, 25, 0, 41))
    c = forward.run(root, ev, clock=Clock(z(2026, 11, 25, 1)))
    assert (
        c["training"]["reason"] == "SAME_MONTH_TRAINED"
        and len(training.versions(root)) == 2
    )


def test_different_input_version_is_supplementary_not_primary(world):
    ev, root = world
    first = store.list_runs(ev)[0][0]
    win = next(
        o["sha256"] for o in first.manifest["objects"] if o["role"] == "naver_windows"
    )
    daily(ev, D, z(2026, 10, 23, 0, 55), z(2026, 10, 23, 0, 56))  # 같은 D 의 다른 판
    p = store.object_path(ev, win)
    p.write_bytes(p.read_bytes()[:-2] + b"zz")  # 처음 판 손상 → 다음 판이 입력
    out = forward.run(root, ev, clock=Clock(z(2026, 10, 23, 2)))
    assert out["roles"] == {"SUPPLEMENTARY": 24}
    prims = records.primaries(root)
    assert {p["input"]["source"]["object"] for p in prims.values()} == {
        win
    }  # 주 기록 그대로
    rep = report.build(root, C.load(root))
    assert (
        rep["counts"]["supplementary_entries"] == 24
        and rep["counts"]["primary_records"] == 24
    )
    again = forward.run(
        root, ev, clock=Clock(z(2026, 10, 23, 3))
    )  # 같은 입력 · 같은 판 재실행
    assert (
        again["status"] == "ALREADY_RECORDED"
        and len(records.prediction_docs(root)) == 2
    )
    assert {x["role"] for x in again["existing"]} == {"SUPPLEMENTARY_EXISTS"}


# ── 방법별 실패 · 복구 · 재시도(설계 §5 · §7) ────────────────────────────────


def test_method_failure_is_isolated_then_repaired_without_retraining_others(
    base, tmp_path, monkeypatch
):
    shutil.copytree(base["dir"], tmp_path / "w")
    ev, root = tmp_path / "w" / "ev", tmp_path / "w" / "r"
    for sub in ("models", "examples", "predictions", "runs", "reports"):
        shutil.rmtree(root / sub)
    real = M.FITTERS["HGB"]

    def boom(rows):
        raise RuntimeError("시험 실패")

    monkeypatch.setitem(M.FITTERS, "HGB", boom)
    out = forward.run(root, ev, clock=Clock(z(2026, 10, 23, 1)))
    _, meta = latest_model(root)
    assert (
        meta["methods"]["HGB"]["status"] == "FAILED"
        and meta["methods"]["RIDGE"]["status"] == "OK"
    )
    doc = records.prediction_docs(root)[0]
    e = next(x for x in doc["entries"] if x["ticker"] == "122090")
    assert (
        e["methods"]["HGB"]["status"] == "FAILED"
        and e["methods"]["MEDIAN"]["status"] == "OK"
    )
    assert out["status"] == "OK"
    still = forward.run(
        root, ev, clock=Clock(z(2026, 10, 23, 1, 30))
    )  # 학습 실패 그대로
    assert still["training"]["repair"]["status"] == "NOT_FIXED"
    assert (
        still["status"] == "ALREADY_RECORDED"
        and len(records.prediction_docs(root)) == 1
    )
    monkeypatch.setitem(M.FITTERS, "HGB", real)
    called = []
    for name, fn in list(M.FITTERS.items()):
        monkeypatch.setitem(
            M.FITTERS, name, lambda rows, _n=name, _f=fn: called.append(_n) or _f(rows)
        )
    again = forward.run(root, ev, clock=Clock(z(2026, 10, 23, 2)))
    assert called == ["HGB"]  # 정상 방법은 다시 학습하지 않음
    assert again["training"]["repair"]["fixed"] == ["HGB"]
    folder, fixed = latest_model(root)
    assert fixed["kind"] == "REPAIR" and fixed["parent"] == meta["model_version"]
    for name in ("median.json", "ridge.json", "mlp_state.pt", "mlp_norm.json"):
        assert fixed["file_sha256"][name] == meta["file_sha256"][name]
    # 다른 모델 판이라 주 기록의 실패 방법에 연결하지 않는다(소급 없음)
    assert {x["role"] for x in again["existing"]} == {"PRIMARY_EXISTS"}


def test_prediction_failure_retried_on_same_input_and_model(world, monkeypatch):
    ev, root = world
    daily(ev, "2026-10-23", z(2026, 10, 26, 0, 45), z(2026, 10, 26, 0, 50))
    real = M.Loaded.raw

    def flaky(self, method, ticker, x):
        if method == "HGB" and ticker == "122090":
            raise RuntimeError("일시 실패")
        return real(self, method, ticker, x)

    monkeypatch.setattr(M.Loaded, "raw", flaky)
    forward.run(root, ev, clock=Clock(z(2026, 10, 26, 1)))
    monkeypatch.setattr(M.Loaded, "raw", real)
    out = forward.run(root, ev, clock=Clock(z(2026, 10, 26, 2)))
    assert out["roles"] == {"RETRY": 1} and out["valid_run"] is False  # 새 주 기록 없음
    third = forward.run(root, ev, clock=Clock(z(2026, 10, 26, 3)))
    assert (
        third["status"] == "ALREADY_RECORDED"
        and len(records.prediction_docs(root)) == 3
    )
    prim = records.primaries(root)[("122090", "2026-10-23")]
    assert (
        prim["methods"]["HGB"]["status"] == "OK"
        and prim["retries"][0]["method"] == "HGB"
    )


def test_failed_retry_is_not_repeated_on_rerun(world, monkeypatch):
    ev, root = world
    daily(ev, "2026-10-23", z(2026, 10, 26, 0, 45), z(2026, 10, 26, 0, 50))
    real = M.Loaded.raw

    def broken(self, method, ticker, x):  # 같은 판에서 계속 실패
        if method == "HGB" and ticker == "122090":
            raise RuntimeError("계속 실패")
        return real(self, method, ticker, x)

    monkeypatch.setattr(M.Loaded, "raw", broken)
    forward.run(root, ev, clock=Clock(z(2026, 10, 26, 1)))
    second = forward.run(root, ev, clock=Clock(z(2026, 10, 26, 2)))
    assert second["roles"] == {"RETRY": 1}  # 한 번은 다시 해 본다
    third = forward.run(root, ev, clock=Clock(z(2026, 10, 26, 3)))
    assert (
        third["status"] == "ALREADY_RECORDED"
        and len(records.prediction_docs(root)) == 3
    )


# ── 보관(설계 §10 · 판정 §6 · §7) ───────────────────────────────────────────


def test_archive_register_upload_and_restore(world, tmp_path):
    from tests.test_poc6_05_evidence_store import FakeRemote
    from app.ml_evidence import transfer

    ev, root = world
    before = archive.local_state(root, ev)
    assert before["unregistered"] > 0 and before["not_allowed"] == []
    status, m = archive.register(root, ev, now=z(2026, 10, 23, 3), code_commit="test")
    assert status == "OK" and len(m["files"]) == before["unregistered"]
    assert archive.local_state(root, ev)["unregistered"] == 0
    assert (
        archive.register(root, ev, now=z(2026, 10, 23, 4), code_commit=None)[0]
        == "SKIPPED_NO_NEW"
    )
    oci = tmp_path / "oci"
    rep = transfer.upload_research(
        root=ev, remote=FakeRemote(oci), run_id=m["run_id"], now=z(2026, 10, 23, 5)
    )
    assert rep["status"] == "OK"
    back = store.restore_check(oci, m["run_id"], tmp_path / "restore")
    assert back["status"] == "OK" and back["objects"] == len(
        {f["sha256"] for f in m["files"]}
    )
    p = root / "cohort_v1" / "cohort.json"
    p.write_bytes(p.read_bytes() + b" ")
    assert (
        archive.register(root, ev, now=z(2026, 10, 23, 6), code_commit=None)[0]
        == "CHECK_REQUIRED"
    )


def test_report_counts_and_no_matured_rows_are_null(world):
    ev, root = world
    rep = P.read_json(root / forward_report_path(root))
    assert rep["counts"]["cohort"] == 24 and rep["counts"]["primary_records"] == 24
    assert (
        rep["counts"]["matured"] == 0
        and rep["main"]["ALL_FOUR"]["mae_pp"]["HGB"] is None
    )
    assert rep["counts"]["predicted_by_method"]["HGB"] == 22
    assert (
        rep["first_forward_published_kst"] == "2026-10-23"
    )  # D = 10-22 · 공개 = 10-23 10:00 KST
    assert rep["first_interpretation_date"] == "2027-01-23"


def forward_report_path(root):
    runs = sorted((root / "runs").glob("*.json"))
    return json.loads(runs[0].read_text())["report"]
