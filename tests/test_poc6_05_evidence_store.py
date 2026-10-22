"""POC6-05 — 보관소 · 연구 등록 · PC ↔ OCI 전송 · export · 복구 경계 시험.

tmp 폴더 두 개(가짜 OCI · 가짜 PC) · 가짜 ssh/scp(같은 기계 복사)만 쓴다. 실제 SSH · 라이브 state 접근 0.
계약 출처: 설계 V1 §4 · §5 · §7 · §9 · PLAN 판정(2026-10-22) §4 · §6-1 · §6-2 · §7.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.ml_evidence import export, research, store, transfer

ROOT = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 10, 22, 0, 40, tzinfo=timezone.utc)


# ── 공용: 가짜 일일 묶음 · 가짜 원격 ─────────────────────────────────────────


def put_lines(root: Path, lines: list[dict]) -> dict:
    w = store.GzJsonlWriter(root)
    for x in lines:
        w.write(x)
    return w.finish()


def daily_run(root, started, published, windows, status="OK", missing=(), prev=None):
    info = put_lines(root, windows)
    objs = {
        info["sha256"]: {
            "sha256": info["sha256"],
            "bytes": info["bytes"],
            "role": "naver_windows",
            "format": "jsonl.gz",
            "lines": info["lines"],
        }
    }
    if prev is not None:
        for o in prev["objects"]:
            objs.setdefault(o["sha256"], dict(o, reused_from=prev["run_id"]))
    m = {
        "schema": store.SCHEMA,
        "run_id": store.new_run_id(started),
        "kind": "DAILY_COLLECTION",
        "site": "TEST",
        "status": status,
        "sources": {
            "naver_etf_windows": {"object": info["sha256"], "missing": list(missing)}
        },
        "objects": [objs[k] for k in sorted(objs)],
    }
    return store.publish_run(root, m, clock=lambda: published)[1]


def win(ticker, close, observed):
    return {
        "ticker": ticker,
        "status": "OK",
        "observed_at": observed,
        "rows": [["2026-10-21", close]],
    }


class FakeRemote(transfer.Remote):
    """원격 경로 → 가짜 OCI 폴더. ssh 명령은 실제 CLI 와 같은 함수를 부른다."""

    def __init__(self, oci_root: Path, fail_once=()):
        super().__init__(target="oci-test")
        self.oci, self.fail_once, self.calls = oci_root, set(fail_once), []

    def _map(self, rp: str) -> Path:
        assert rp.startswith(transfer.REMOTE_EVIDENCE), rp
        return self.oci / rp.removeprefix(transfer.REMOTE_EVIDENCE + "/")

    def ssh(self, cmd, timeout):
        self.calls.append(("ssh", cmd))
        if cmd.endswith(" list-runs"):
            lines = transfer.list_runs_lines(self.oci)
            return 0, "\n".join(json.dumps(x) for x in lines).encode()
        if cmd.startswith("mkdir -p "):
            self._map(cmd.removeprefix("mkdir -p ")).mkdir(parents=True, exist_ok=True)
            return 0, b""
        if " accept-upload " in cmd:
            uid = re.search(r"--upload-id (\S+)", cmd).group(1)
            sha = re.search(r"--expect-manifest-sha (\S+)", cmd).group(1)
            r = transfer.accept_upload(
                root=self.oci, upload_id=uid, expect_sha=sha, now=T0
            )
            return (0 if r["status"] == "OK" else 2), (
                "RESULT " + json.dumps(r)
            ).encode()
        raise AssertionError(cmd)

    def scp_from(self, remote_paths, local_dir, timeout):
        self.calls.append(("scp_from", list(remote_paths)))
        rc = 0
        for rp in remote_paths:
            src = self._map(rp)
            if rp in self.fail_once:
                self.fail_once.discard(rp)
                rc = 1
                continue
            shutil.copyfile(src, Path(local_dir) / src.name)
        return rc

    def scp_to(self, local_paths, remote_dir, timeout):
        self.calls.append(("scp_to", [Path(p).name for p in local_paths]))
        for p in local_paths:
            shutil.copyfile(p, self._map(remote_dir) / Path(p).name)
        return 0


# ── 보관소 ────────────────────────────────────────────────────────────────


def test_objects_are_write_once_and_corruption_is_detected(tmp_path):
    a = store.put_bytes(tmp_path, b"hello")
    b = store.put_bytes(tmp_path, b"hello")
    assert a["created"] and not b["created"] and a["sha256"] == b["sha256"]
    p = store.object_path(tmp_path, a["sha256"])
    os.chmod(p, 0o644)
    p.write_bytes(b"tampered")
    with pytest.raises(store.EvidenceError):
        store.read_object(tmp_path, a["sha256"])
    c = store.put_bytes(
        tmp_path, b"hello"
    )  # 같은 내용을 다시 받으면 손상본 격리 · 되살림
    assert c["repaired"] and store.read_object(tmp_path, a["sha256"]) == b"hello"
    q = list((tmp_path / "objects" / ".corrupt").iterdir())
    assert len(q) == 1 and q[0].read_bytes() == b"tampered"


def test_same_run_id_with_other_content_is_conflict_and_partial_dirs_are_ignored(
    tmp_path,
):
    m = daily_run(tmp_path, T0, T0, [win("A", 1, "x")])
    data = (tmp_path / "runs" / m["run_id"] / "manifest.json").read_bytes()
    assert (
        store.publish_copied(tmp_path, data, lambda: {"site": "X"})[1] is False
    )  # 같은 내용 = 그대로
    other = json.loads(data)
    other["status"] = "PARTIAL"
    with pytest.raises(store.EvidenceError, match="다른 내용"):
        store.publish_copied(
            tmp_path, store.manifest_bytes(other), lambda: {"site": "X"}
        )
    junk = tmp_path / "runs" / ".20261022T004000Z_deadbeef.x.partial"
    junk.mkdir()
    (junk / "manifest.json").write_bytes(data)
    runs, problems = store.list_runs(tmp_path)
    assert [r.run_id for r in runs] == [m["run_id"]] and not problems
    assert store.partial_dirs(tmp_path) == [junk.name]


def test_catalog_is_refilled_when_append_was_interrupted(tmp_path):
    a = daily_run(tmp_path, T0, T0, [win("A", 1, "x")])
    (tmp_path / "catalog.jsonl").write_text(
        "", encoding="utf-8"
    )  # 공개 뒤 append 전에 끊김
    assert [r.run_id for r in store.list_runs(tmp_path)[0]] == [
        a["run_id"]
    ]  # 정본 = runs/
    b = daily_run(
        tmp_path, T0 + timedelta(hours=1), T0 + timedelta(hours=1), [win("A", 2, "y")]
    )
    ids = [
        json.loads(x)["run_id"]
        for x in (tmp_path / "catalog.jsonl").read_text().splitlines()
    ]
    assert sorted(ids) == sorted([a["run_id"], b["run_id"]])


def test_restore_check_with_previous_refs_and_refuses_bad_destination(tmp_path):
    root = tmp_path / "ev"
    r1 = daily_run(root, T0, T0, [win("A", 1, "x")])
    r2 = daily_run(
        root,
        T0 + timedelta(days=1),
        T0 + timedelta(days=1),
        [win("B", 2, "y")],
        prev=r1,
    )
    rep = store.restore_check(root, r2["run_id"], tmp_path / "restore")
    assert rep["status"] == "OK" and rep["objects"] == 2 and rep["same_read_result"]
    with pytest.raises(store.EvidenceError, match="비어 있지 않음"):
        store.restore_check(root, r2["run_id"], tmp_path / "restore")
    with pytest.raises(store.EvidenceError, match="겹침"):
        store.restore_check(root, r2["run_id"], root / "inner")


# ── 연구 등록 ───────────────────────────────────────────────────────────────


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """POC6-02 · 03 · 04 공식 폴더를 흉내 낸 고정 파일(실제 원본을 읽지 않는다)."""
    base = tmp_path / "repo"
    rep02 = {
        "eligibility": {"etfs": {"A": {"eligible": True}, "B": {"eligible": False}}},
        "recipe": {"target": "D20", "feature_names": ["chg5"]},
        "input_digest": "in",
        "recipe_digest": "rc",
        "environment": {"python": "3.12"},
    }
    files = {
        research.P02: {
            "report.json": json.dumps(rep02),
            "gpu_result.json": json.dumps({"env": {"torch": "2.6"}}),
            "gpu_merged/report_with_gpu.json": json.dumps(
                {
                    "candidates": {
                        "POOLED_HGB": "RESEARCH_PROMISING",
                        "POOLED_GPU_MLP": "REJECT",
                    }
                }
            ),
            "gpu_bundle/gpu_input.json": json.dumps({"code_sha256": {"mlp.py": "x"}}),
        },
        research.P03: {
            "copy.sqlite": "SQLite format 3\x00 fake",
            "fetch.json": json.dumps({"targets": 26}),  # 실제 POC6-03 형식(개수 정수)
            f"{research._C03}/report.json": json.dumps(
                {
                    "krx_source": {
                        "file_size": 10,
                        "file_sha256": "f" * 64,
                        "content_sha256": "c" * 64,
                    }
                }
            ),
        },
        research.P04: {
            "manifest.json": json.dumps({"recipe_digest": "rc"}),
            "a_report_frozen.json": json.dumps(rep02),  # 02 report 와 같은 바이트
            "report.json": json.dumps(
                {
                    "four": ["A"],
                    "c_etfs": ["A", "C"],
                    "environment": {},
                    "c12": {"verdict": {"label": "탐색적 기준 미충족"}},
                }
            ),
        },
    }
    table = {}
    for eid, (folder, _) in research.FILES.items():
        entries = []
        for rel, text in files[folder].items():
            p = base / folder / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(text.encode("utf-8"))
            entries.append((rel, p.stat().st_size, store.sha256_file(p)))
        table[eid] = (folder, entries)
    monkeypatch.setattr(research, "FILES", table)
    return base


def test_register_research_keeps_bytes_and_links_without_rerun(repo, tmp_path):
    root = tmp_path / "pc"
    before = {
        p: (store.sha256_file(p), p.stat().st_mtime_ns)
        for p in repo.rglob("*")
        if p.is_file()
    }
    status, m = research.register_research(
        root=root, repo_root=repo, now=T0, git_head="b" * 40
    )
    assert status == "OK" and all(f["status"] == "REGISTERED" for f in m["files"])
    assert before == {
        p: (store.sha256_file(p), p.stat().st_mtime_ns)
        for p in repo.rglob("*")
        if p.is_file()
    }
    for f in m["files"]:
        assert (
            store.read_object(root, f["sha256"]) == (repo / f["rel_path"]).read_bytes()
        )
    assert (
        len(m["objects"]) == len(m["files"]) - 1
    )  # 02 report = 04 a_report_frozen → object 하나
    by = {e["experiment_id"].split(":")[0]: e for e in m["experiments"]}
    assert (
        by["POC6-04"]["predictions"].startswith("not_saved")
        and by["POC6-02"]["trained_artifact"] == "not_saved"
    )
    assert all(
        e["record_type"] == "RETROSPECTIVE_TEST" and e["run_commit"] is None
        for e in by.values()
    )
    assert {c["kind"] for c in by["POC6-02"]["code_evidence"]} == {
        "first_commit_containing_code",
        "result_doc_recompute",
        "gpu_code_sha256",
    }
    assert by["POC6-02"]["links"]["targets"]["eligible"] == ["A"]
    assert by["POC6-02"]["links"]["verdicts"]["POOLED_GPU_MLP"] == "REJECT"
    assert by["POC6-03"]["links"]["targets"]["all"] == 26
    dep = by["POC6-03"]["links"]["dependencies"][0]
    assert dep["uploaded"] is False and dep["file_sha256"] == "f" * 64
    assert m["code_commit_kind"].startswith("registration_program_commit")
    again, m2 = research.register_research(
        root=root, repo_root=repo, now=T0 + timedelta(hours=1), git_head=None
    )
    assert again == "ALREADY_REGISTERED" and m2["run_id"] == m["run_id"]
    assert len(store.list_runs(root)[0]) == 1


def test_register_research_mismatch_is_check_required_and_not_copied(repo, tmp_path):
    (repo / research.P03 / "fetch.json").write_text('{"targets": 27}', encoding="utf-8")
    status, m = research.register_research(
        root=tmp_path / "pc", repo_root=repo, now=T0, git_head=None
    )
    bad = [f for f in m["files"] if f["status"] == "CHECK_REQUIRED"]
    assert status == "PARTIAL" and [f["rel_path"].split("/")[-1] for f in bad] == [
        "fetch.json"
    ]
    assert "sha256" not in bad[0]


# ── PC ↔ OCI ────────────────────────────────────────────────────────────────


def test_upload_research_roundtrip_and_second_upload_is_noop(repo, tmp_path):
    pc, oci = tmp_path / "pc", tmp_path / "oci"
    _, m = research.register_research(root=pc, repo_root=repo, now=T0, git_head=None)
    remote = FakeRemote(oci)
    rep = transfer.upload_research(root=pc, remote=remote, run_id=m["run_id"], now=T0)
    assert rep["status"] == "OK" and rep["objects_sent"] == len(m["objects"])
    runs, _ = store.list_runs(oci)
    assert [r.run_id for r in runs] == [m["run_id"]] and runs[0].receipt[
        "site"
    ] == "OCI"
    assert (oci / "runs" / m["run_id"] / "manifest.json").read_bytes() == (
        pc / "runs" / m["run_id"] / "manifest.json"
    ).read_bytes()
    assert not any((oci / ".incoming").iterdir())
    again = transfer.upload_research(root=pc, remote=remote, run_id=m["run_id"], now=T0)
    assert again["already_on_oci"] and again["same_manifest"]


@pytest.mark.parametrize(
    "case",
    [
        "extra_file",
        "extra_hex",
        "wrong_sha",
        "bad_experiment",
        "tampered",
        "bad_id",
        "no_experiments",
        "unlisted_object",
    ],
)
def test_accept_upload_rejects_without_publishing(repo, tmp_path, case):
    pc, oci = tmp_path / "pc", tmp_path / "oci"
    _, m = research.register_research(root=pc, repo_root=repo, now=T0, git_head=None)
    uid = "up_20261022T004000Z_0123abcd"
    work = oci / ".incoming" / uid
    work.mkdir(parents=True)
    for s in store.manifest_object_shas(m):
        shutil.copyfile(store.object_path(pc, s), work / s)
    data = (pc / "runs" / m["run_id"] / "manifest.json").read_bytes()
    if case == "bad_experiment":
        mm = json.loads(data)
        mm["experiments"][0]["experiment_id"] = "POC9-99:evil"
        data = store.manifest_bytes(mm)
    if case == "no_experiments":
        mm = json.loads(data)
        mm["experiments"] = []
        data = store.manifest_bytes(mm)
    if case == "unlisted_object":  # 허용 목록 밖 파일을 등록 파일로 끼워 넣기
        secret = b"KIWOOM_APP_SECRET=xxx"
        s_sha = store.sha256_bytes(secret)
        (work / s_sha).write_bytes(secret)
        mm = json.loads(data)
        mm["files"][0]["sha256"] = s_sha
        keep = {f["sha256"] for f in mm["files"] if f["status"] == "REGISTERED"}
        mm["objects"] = [o for o in mm["objects"] if o["sha256"] in keep]
        mm["objects"].append({"sha256": s_sha, "bytes": len(secret), "role": "x"})
        data = store.manifest_bytes(
            mm
        )  # object 목록 = 등록 파일 → 허용 목록만이 막는다
    (work / "manifest.json").write_bytes(data)
    sha = store.sha256_bytes(data)
    if case == "extra_file":
        (work / "evil.txt").write_text("x")
    if case == "extra_hex":
        (work / ("e" * 64)).write_text("x")  # 이름 형식은 맞지만 manifest 에 없는 파일
    if case == "wrong_sha":
        sha = "0" * 64
    if case == "tampered":
        victim = work / store.manifest_object_shas(m)[0]
        victim.write_bytes(b"changed")
    r = transfer.accept_upload(
        root=oci, upload_id="../x" if case == "bad_id" else uid, expect_sha=sha, now=T0
    )
    assert r["status"] == "CHECK_REQUIRED"
    assert store.list_runs(oci) == ([], [])


def test_pull_gets_late_published_lower_run_id(tmp_path):
    pc, oci = tmp_path / "pc", tmp_path / "oci"
    b = daily_run(
        oci, T0 + timedelta(minutes=5), T0 + timedelta(minutes=6), [win("A", 1, "x")]
    )
    remote = FakeRemote(oci)
    assert transfer.pull(root=pc, remote=remote, now=T0)["pulled"] == [b["run_id"]]
    # 더 일찍 시작했지만(낮은 run_id) 더 늦게 공개된 묶음
    a = daily_run(oci, T0, T0 + timedelta(minutes=20), [win("B", 2, "y")])
    assert a["run_id"] < b["run_id"]
    rep = transfer.pull(root=pc, remote=remote, now=T0 + timedelta(hours=1))
    assert rep["pulled"] == [a["run_id"]] and rep["already_local"] == 1
    runs, _ = store.list_runs(pc)
    assert {r.run_id for r in runs} == {a["run_id"], b["run_id"]}
    assert all(
        r.receipt["source_site"] == "OCI" and r.receipt["copied_at_pc"] for r in runs
    )
    assert (
        runs[0].manifest["published_at"] == a["published_at"]
    )  # 원래 공개 시각 그대로


def test_pull_resumes_and_downloads_only_missing_objects(tmp_path):
    pc, oci = tmp_path / "pc", tmp_path / "oci"
    r1 = daily_run(oci, T0, T0, [win("A", 1, "x")])
    r2 = daily_run(
        oci, T0 + timedelta(days=1), T0 + timedelta(days=1), [win("B", 2, "y")], prev=r1
    )
    new_obj = r2["sources"]["naver_etf_windows"]["object"]
    path = f"{transfer.REMOTE_EVIDENCE}/objects/{new_obj[:2]}/{new_obj}"
    remote = FakeRemote(oci, fail_once=[path])
    rep1 = transfer.pull(root=pc, remote=remote, now=T0)
    assert rep1["status"] == "CHECK_REQUIRED" and rep1["pulled"] == [r1["run_id"]]
    rep2 = transfer.pull(root=pc, remote=remote, now=T0 + timedelta(hours=1))
    assert (
        rep2["pulled"] == [r2["run_id"]]
        and rep2["objects_downloaded"] == 1
        and rep2["status"] == "OK"
    )
    runs, _ = store.list_runs(pc)
    assert all(store.verify_run(pc, r) == [] for r in runs)


def test_pull_rejects_manifest_that_differs_from_listing(tmp_path, monkeypatch):
    pc, oci = tmp_path / "pc", tmp_path / "oci"
    daily_run(oci, T0, T0, [win("A", 1, "x")])
    real = transfer.list_runs_lines

    def lying(root):
        rows = real(root)
        rows[0]["manifest_sha256"] = "1" * 64
        return rows

    monkeypatch.setattr(transfer, "list_runs_lines", lying)
    rep = transfer.pull(root=pc, remote=FakeRemote(oci), now=T0)
    assert rep["pulled"] == [] and any(
        "해시가 목록과 다름" in x for x in rep["problems"]
    )
    assert store.list_runs(pc) == ([], [])


def test_pull_rejects_tampered_object_and_reports_conflict(tmp_path):
    pc, oci = tmp_path / "pc", tmp_path / "oci"
    r1 = daily_run(oci, T0, T0, [win("A", 1, "x")])
    sha = r1["sources"]["naver_etf_windows"]["object"]
    p = store.object_path(oci, sha)
    os.chmod(p, 0o644)
    p.write_bytes(gzip.compress(b"{}\n"))
    rep = transfer.pull(root=pc, remote=FakeRemote(oci), now=T0)
    assert (
        rep["status"] == "CHECK_REQUIRED"
        and rep["pulled"] == []
        and store.list_runs(pc) == ([], [])
    )
    oci2, pc2 = tmp_path / "oci2", tmp_path / "pc2"
    r = daily_run(oci2, T0, T0, [win("A", 1, "x")])
    data = json.loads((oci2 / "runs" / r["run_id"] / "manifest.json").read_bytes())
    for s in store.manifest_object_shas(data):
        shutil.copytree(oci2 / "objects", pc2 / "objects", dirs_exist_ok=True)
    data["status"] = "PARTIAL"
    store.publish_copied(pc2, store.manifest_bytes(data), lambda: {"site": "PC"})
    rep2 = transfer.pull(root=pc2, remote=FakeRemote(oci2), now=T0)
    assert rep2["conflicts"] == [r["run_id"]] and rep2["status"] == "CHECK_REQUIRED"


# ── export ──────────────────────────────────────────────────────────────────


def test_export_uses_published_at_and_never_mixes_in_later_corrections(tmp_path):
    root, out = tmp_path / "ev", tmp_path / "out"
    daily_run(root, T0, T0, [win("A", 100, "2026-10-22T00:41:00.000000Z")])
    daily_run(
        root,
        T0 + timedelta(days=1),
        T0 + timedelta(days=1),
        [win("A", 101, "2026-10-23T00:41:00.000000Z")],
    )
    daily_run(
        root,
        T0 + timedelta(days=2),
        T0 + timedelta(days=2),
        [win("A", 999, "z")],
        status="FAILED",
    )
    mid = store.iso(T0 + timedelta(hours=12))
    sel = export.select(root, mid)
    assert (
        sel["windows"]["A"]["rows"][0][1] == 100
    )  # 같은 관측일의 뒤 정정(101)은 아직 공개 전
    late = export.select(root, store.iso(T0 + timedelta(days=5)))
    assert late["windows"]["A"]["rows"][0][1] == 101  # FAILED(999) 는 내보내지 않는다
    status, folder = export.export(root=root, as_of=mid, now=T0, out_root=out)
    assert status == "OK"
    rows = [
        json.loads(x)
        for x in (folder / "naver_etf_windows.jsonl").read_text().splitlines()
    ]
    assert rows[0]["rows"][0][1] == 100
    assert json.loads((folder / "export_manifest.json").read_text())["as_of"] == mid


def test_export_partial_run_carries_missing_and_corrupt_object_is_excluded(tmp_path):
    root = tmp_path / "ev"
    r = daily_run(root, T0, T0, [win("A", 1, "x")], status="PARTIAL", missing=["B"])
    sel = export.select(root, store.iso(T0 + timedelta(hours=1)))
    assert sel["used"][0]["naver_missing"] == ["B"] and "A" in sel["windows"]
    p = store.object_path(root, r["sources"]["naver_etf_windows"]["object"])
    os.chmod(p, 0o644)
    p.write_bytes(b"broken")
    sel2 = export.select(root, store.iso(T0 + timedelta(hours=1)))
    assert sel2["windows"] == {} and sel2["problems"]


def test_export_refuses_output_inside_evidence_and_naive_as_of(tmp_path):
    root = tmp_path / "ev"
    daily_run(root, T0, T0, [win("A", 1, "x")])
    with pytest.raises(store.EvidenceError):
        export.export(root=root, as_of=store.iso(T0), now=T0, out_root=root / "x")
    with pytest.raises(ValueError):
        export.parse_as_of("2026-10-22T09:40:00")
    assert (
        export.parse_as_of("2026-10-22T09:40:00+09:00") == "2026-10-22T00:40:00.000000Z"
    )


# ── CLI ─────────────────────────────────────────────────────────────────────


def test_cli_status_and_list_runs_on_tmp_root(tmp_path):
    root = tmp_path / "ev"
    r = daily_run(root, T0, T0, [win("A", 1, "x")])
    cli = [sys.executable, "scripts/run_ml_evidence.py", "--root", str(root)]
    out = subprocess.run(
        cli + ["status"], cwd=ROOT, capture_output=True, text=True, timeout=60
    )
    result = json.loads(out.stdout.strip().splitlines()[-1].removeprefix("RESULT "))
    assert out.returncode == 0 and result["runs"] == 1
    lst = subprocess.run(
        cli + ["list-runs"], cwd=ROOT, capture_output=True, text=True, timeout=60
    )
    assert json.loads(lst.stdout.splitlines()[0])["run_id"] == r["run_id"]
    bad = subprocess.run(
        cli + ["restore-check", "--run-id", r["run_id"], "--to", str(root / "in")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert bad.returncode == 2 and "CHECK_REQUIRED" in bad.stdout


def test_pull_redownloads_corrupt_local_object(tmp_path):
    pc, oci = tmp_path / "pc", tmp_path / "oci"
    r1 = daily_run(oci, T0, T0, [win("A", 1, "x")])
    sha = r1["sources"]["naver_etf_windows"]["object"]
    bad = store.object_path(pc, sha)
    bad.parent.mkdir(parents=True)
    bad.write_bytes(b"corrupt on pc")
    rep = transfer.pull(root=pc, remote=FakeRemote(oci), now=T0)
    assert rep["status"] == "OK" and rep["pulled"] == [r1["run_id"]]
    assert rep["objects_downloaded"] == 1 and store.read_object(pc, sha)


# ── 검증자 r1 F1 · F2 재현 · 같은 종류 ───────────────────────────────────────


def _flip(path: Path) -> None:
    os.chmod(path, 0o644)
    raw = bytearray(path.read_bytes())
    raw[0] ^= 0xFF  # 크기는 같고 내용만 다름
    path.write_bytes(bytes(raw))


def test_pull_rechecks_already_pulled_copies_and_repairs(tmp_path):
    pc, oci = tmp_path / "pc", tmp_path / "oci"
    r1 = daily_run(oci, T0, T0, [win("A", 1, "x")])
    r2 = daily_run(
        oci, T0 + timedelta(days=1), T0 + timedelta(days=1), [win("B", 2, "y")], prev=r1
    )
    remote = FakeRemote(oci)
    assert transfer.pull(root=pc, remote=remote, now=T0)["status"] == "OK"
    a = r1["sources"]["naver_etf_windows"]["object"]
    b = r2["sources"]["naver_etf_windows"]["object"]
    _flip(store.object_path(pc, a))  # 이미 받은 사본 손상
    store.object_path(pc, b).unlink()  # 이미 받은 사본 삭제
    rep = transfer.pull(root=pc, remote=remote, now=T0 + timedelta(hours=1))
    assert rep["status"] == "REPAIRED" and rep["objects_downloaded"] == 2
    assert sorted(rep["local_repaired"]) == sorted([a, b]) and rep["problems"] == []
    runs, _ = store.list_runs(pc)
    assert all(store.verify_run(pc, r) == [] for r in runs)
    assert (
        transfer.pull(root=pc, remote=remote, now=T0 + timedelta(hours=2))["status"]
        == "OK"
    )


def test_pull_reports_when_oci_copy_is_also_damaged(tmp_path):
    pc, oci = tmp_path / "pc", tmp_path / "oci"
    r1 = daily_run(oci, T0, T0, [win("A", 1, "x")])
    remote = FakeRemote(oci)
    transfer.pull(root=pc, remote=remote, now=T0)
    sha = r1["sources"]["naver_etf_windows"]["object"]
    _flip(store.object_path(pc, sha))
    _flip(store.object_path(oci, sha))
    rep = transfer.pull(root=pc, remote=remote, now=T0 + timedelta(hours=1))
    assert rep["status"] == "CHECK_REQUIRED" and rep["local_repaired"] == []
    assert any(x.startswith("OCI ") for x in rep["problems"])
    from app.ml_evidence import status as st_mod

    assert st_mod.summarize(pc)["damaged"] == {r1["run_id"]: [sha]}


def test_upload_repairs_damaged_oci_copy_and_accept_checks_existing(repo, tmp_path):
    pc, oci = tmp_path / "pc", tmp_path / "oci"
    _, m = research.register_research(root=pc, repo_root=repo, now=T0, git_head=None)
    remote = FakeRemote(oci)
    transfer.upload_research(root=pc, remote=remote, run_id=m["run_id"], now=T0)
    victim = store.manifest_object_shas(m)[0]
    _flip(store.object_path(oci, victim))
    rep = transfer.upload_research(root=pc, remote=remote, run_id=m["run_id"], now=T0)
    assert (
        rep["status"] == "OK" and rep["repair_of_oci_copy"] and rep["objects_sent"] == 1
    )
    runs, _ = store.list_runs(oci)
    assert store.verify_run(oci, runs[0]) == []
    # 업로드 받기: 이미 있는 object 가 손상이면(이번 업로드에 없으면) 받지 않는다
    _flip(store.object_path(oci, victim))
    uid = "up_20261022T004000Z_00000000"
    work = oci / ".incoming" / uid
    work.mkdir(parents=True)
    data = (pc / "runs" / m["run_id"] / "manifest.json").read_bytes()
    (work / "manifest.json").write_bytes(data)
    r = transfer.accept_upload(
        root=oci, upload_id=uid, expect_sha=store.sha256_bytes(data), now=T0
    )
    assert r["status"] == "CHECK_REQUIRED" and "손상" in r["reason"]


@pytest.mark.parametrize(
    "field, value",
    [
        ("published_at", "2026-10-21T23:40:00-01:00"),  # 실제 = 10-22 00:40Z
        ("published_at", "0000-00-00T00:00:00.000000Z"),
        ("published_at", "2026-10-21T23:40:00Z"),  # 마이크로초 없음
        ("run_id", "00000000T000000Z_deadbeef"),
    ],
)
def test_time_fields_are_parsed_not_string_checked(tmp_path, field, value):
    root = tmp_path / "ev"
    m = daily_run(root, T0, T0, [win("A", 999, "x")])
    bad = dict(m, **{field: value})
    if field == "run_id":
        bad["run_id"] = value
    assert store.validate_manifest(bad)
    with pytest.raises(store.EvidenceError):
        store.publish_copied(tmp_path / "other", store.manifest_bytes(bad), lambda: {})
    # 이미 놓인 부적합 manifest 는 목록 · export 에서 정상 입력이 아니다
    d = root / "runs" / m["run_id"]
    os.chmod(d / "manifest.json", 0o644)
    (d / "manifest.json").write_bytes(
        store.manifest_bytes(dict(bad, run_id=m["run_id"]))
    )
    runs, problems = store.list_runs(root)
    if field == "published_at":
        assert runs == [] and problems
        sel = export.select(root, export.parse_as_of("2026-10-21T23:50:00Z"))
        assert sel["windows"] == {}  # 미래 공개 판(999)이 과거 export 에 섞이지 않음


def test_upload_refuses_damaged_pc_copy(repo, tmp_path):
    pc, oci = tmp_path / "pc", tmp_path / "oci"
    _, m = research.register_research(root=pc, repo_root=repo, now=T0, git_head=None)
    _flip(store.object_path(pc, store.manifest_object_shas(m)[0]))
    remote = FakeRemote(oci)
    with pytest.raises(store.EvidenceError, match="PC 사본 손상"):
        transfer.upload_research(root=pc, remote=remote, run_id=m["run_id"], now=T0)
    assert remote.calls == [] and store.list_runs(oci) == ([], [])
