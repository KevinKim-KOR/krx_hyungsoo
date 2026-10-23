"""POC6-05 — PC ↔ OCI 전송(기존 SSH 설정 재사용 · 별도 서버 · 포트 · 웹 API 없음).

- `pull`(PC): OCI `list-runs`(읽기 전용 · 완료 manifest 전체 목록)를 받아 PC 에 없는 run 만 가져온다.
  시각 커서를 쓰지 않는다(늦게 공개된 낮은 run_id 도 다음 pull 에 들어온다 · 판정 §6-1).
  object 는 PC 에 없는 해시만 받는다 → 중단 뒤 다시 실행하면 빠진 것만 받는다. SSH 실패는 기존 사본을 지우지 않는다.
- `upload-research`(PC → OCI): 연구 등록 묶음의 object(OCI 에 없는 해시만) + manifest 를
  `.incoming/<upload_id>/` 로
  보내고, OCI 의 `accept-upload` 가 검사 · 공개한다. 임의 원격 경로 쓰기 도구가 아니다.
- `accept-upload`(OCI): 이름 = 해시 · manifest 해시 · kind · 허용 실험 · 모든 object 해시를 검사한 뒤에만 공개.
- POC6-06 산출물 묶음(`FORWARD_RESEARCH_ARTIFACTS`)도 같은 길로 올린다 — `forward_artifacts.problems`(정규화 상대 경로 ·
  schema · training.json 참조 · 해시)를 통과해야만 공개 · 모델 파일은 bytes 로만 보관(load 0).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from app.ml_evidence import forward_artifacts, research, store

REMOTE_ROOT = "/home/ubuntu/krx_hyungsoo"
REMOTE_EVIDENCE = f"{REMOTE_ROOT}/state/ml/evidence"
CLI = "scripts/run_ml_evidence.py"
CONNECT_TIMEOUT_SEC = 8
LIST_TIMEOUT_SEC = 60
SCP_TIMEOUT_SEC = 300
ACCEPT_TIMEOUT_SEC = 180
CHUNK = 40
UPLOAD_ID = re.compile(r"^up_\d{8}T\d{6}Z_[0-9a-f]{8}$")
UPLOAD_KINDS = ("RESEARCH_REGISTRATION", forward_artifacts.KIND)


@dataclass
class Remote:
    """ssh · scp 실행기(시험은 가짜로 바꿔 끼운다)."""

    target: str
    key_opts: list[str] = field(default_factory=list)
    runner: Callable = subprocess.run

    def _opts(self) -> list[str]:
        return [
            "-o",
            "BatchMode=yes",
            "-o",
            f"ConnectTimeout={CONNECT_TIMEOUT_SEC}",
            *self.key_opts,
        ]

    def ssh(self, remote_cmd: str, timeout: int) -> tuple[int, bytes]:
        r = self.runner(
            ["ssh", *self._opts(), self.target, remote_cmd],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return r.returncode, r.stdout

    def scp_from(self, remote_paths: list[str], local_dir: Path, timeout: int) -> int:
        srcs = [f"{self.target}:{p}" for p in remote_paths]
        r = self.runner(
            ["scp", "-q", *self._opts(), *srcs, str(local_dir) + "/"],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return r.returncode

    def scp_to(self, local_paths: list[Path], remote_dir: str, timeout: int) -> int:
        r = self.runner(
            [
                "scp",
                "-q",
                *self._opts(),
                *[str(p) for p in local_paths],
                f"{self.target}:{remote_dir}/",
            ],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return r.returncode


def default_remote() -> Remote:
    from app.config import require_env
    from app.oci_startup_status import _ssh_key_opts

    return Remote(target=require_env("OCI_SSH_TARGET"), key_opts=_ssh_key_opts())


def list_runs_lines(root: Path) -> list[dict]:
    """OCI 쪽 읽기 전용 목록(완료 manifest 전체). 형식이 깨진 묶음은 problem 줄로."""
    runs, problems = store.list_runs(root)
    out = [
        {
            "run_id": r.run_id,
            "manifest_sha256": r.manifest_sha256,
            "kind": r.manifest["kind"],
            "status": r.manifest["status"],
            "published_at": r.manifest["published_at"],
            "objects": store.manifest_object_shas(r.manifest),
            "damaged": store.damaged_objects(root, r.manifest),
        }
        for r in runs
    ]
    return out + [{"problem": p} for p in problems]


def _parse_remote_list(raw: bytes) -> tuple[list[dict], list[str]]:
    rows, problems = [], []
    for line in raw.decode("utf-8", "replace").splitlines():
        if not line.startswith("{"):
            continue
        try:
            d = json.loads(line)
        except ValueError:
            problems.append("목록 줄 해석 불가")
            continue
        if "problem" in d:
            problems.append(f"OCI: {d['problem']}")
            continue
        d.setdefault("damaged", [])
        ok = (
            store.run_id_ok(d.get("run_id"))
            and isinstance(d.get("manifest_sha256"), str)
            and store.HEX64.match(d["manifest_sha256"])
            and isinstance(d.get("objects"), list)
            and all(isinstance(s, str) and store.HEX64.match(s) for s in d["objects"])
            and isinstance(d["damaged"], list)
            and set(d["damaged"]) <= set(d["objects"])
        )
        if ok:
            rows.append(d)
        else:
            problems.append("목록 줄 형식 아님")
    return rows, problems


def _remote_list(remote: Remote) -> tuple[list[dict], list[str]]:
    rc, out = remote.ssh(
        f"cd {REMOTE_ROOT} && venv/bin/python {CLI} list-runs", LIST_TIMEOUT_SEC
    )
    if rc != 0:
        raise store.EvidenceError(f"OCI 목록 조회 실패(rc {rc})")
    return _parse_remote_list(out)


def pull(
    *,
    root: Path,
    remote: Remote,
    now: datetime,
    clock: Callable[[], datetime] = store.utc_now,
) -> dict:
    """완료 manifest 전체를 대조해 PC 에 없는 묶음을 가져오고, **이미 받은 묶음도 매번 다시 검사**한다.

    - 없는 · 손상된 PC object 는 OCI 정상본을 다시 받아 되살린다(손상본은 격리 보존 · `REPAIRED`).
    - OCI 쪽이 손상 · 없음이면 받지 않고 확인 필요로 남긴다. 같은 run_id 다른 manifest = 충돌.
    """
    remote_rows, problems = _remote_list(remote)
    local, local_problems = store.list_runs(root)
    problems += [f"PC: {p}" for p in local_problems]
    have = {r.run_id: r for r in local}
    conflicts = [
        r["run_id"]
        for r in remote_rows
        if r["run_id"] in have
        and have[r["run_id"]].manifest_sha256 != r["manifest_sha256"]
    ]
    need = [r for r in remote_rows if r["run_id"] not in have]
    present = [
        r for r in remote_rows if r["run_id"] in have and r["run_id"] not in conflicts
    ]
    remote_bad = {s for r in remote_rows for s in r.get("damaged", [])}
    for r in remote_rows:
        if r.get("damaged"):
            problems.append(
                f"OCI {r['run_id']}: object 없음 · 손상 {len(r['damaged'])}"
            )
    local_bad = sorted(
        {
            s
            for r in present
            for s in store.damaged_objects(root, have[r["run_id"]].manifest)
        }
    )
    incoming = root / ".incoming"
    for old in incoming.glob("pull_*") if incoming.exists() else []:
        shutil.rmtree(old, ignore_errors=True)  # 검사 안 된 임시 칸만 지운다
    pull_id = f"pull_{now:%Y%m%dT%H%M%SZ}_{uuid.uuid4().hex[:8]}"
    work = incoming / pull_id
    (work / "objects").mkdir(parents=True)
    new_objs = {s for r in need for s in r["objects"] if not store.object_ok(root, s)}
    wanted = sorted((new_objs | set(local_bad)) - remote_bad)
    downloaded = 0
    for i in range(0, len(wanted), CHUNK):
        part = wanted[i:][:CHUNK]
        rc = remote.scp_from(
            [f"{REMOTE_EVIDENCE}/objects/{s[:2]}/{s}" for s in part],
            work / "objects",
            SCP_TIMEOUT_SEC,
        )
        for s in part:
            p = work / "objects" / s
            if not p.exists():
                continue
            try:
                store.put_file(root, p, expect_sha=s)
                downloaded += 1
            except store.EvidenceError as e:
                problems.append(f"object {s[:16]}: {e}")
            p.unlink(missing_ok=True)
        if rc != 0:
            problems.append(f"object 내려받기 일부 실패(rc {rc})")
    repaired = [s for s in local_bad if store.object_ok(root, s)]
    still = [s for s in local_bad if not store.object_ok(root, s)]
    if still:
        problems.append(f"PC 사본 손상 · 없음 되살리지 못함 {len(still)}")
    pulled = []
    for r in sorted(need, key=lambda x: x["run_id"]):
        mdir = work / "manifests" / r["run_id"]
        mdir.mkdir(parents=True)
        rc = remote.scp_from(
            [f"{REMOTE_EVIDENCE}/runs/{r['run_id']}/manifest.json"],
            mdir,
            SCP_TIMEOUT_SEC,
        )
        mp = mdir / "manifest.json"
        if rc != 0 or not mp.exists():
            problems.append(f"{r['run_id']}: manifest 내려받기 실패")
            continue
        data = mp.read_bytes()
        if store.sha256_bytes(data) != r["manifest_sha256"]:
            problems.append(f"{r['run_id']}: manifest 해시가 목록과 다름")
            continue

        def receipt() -> dict:
            # PC 가 실제로 공개한 순간(원래 published_at 은 manifest 그대로)
            return {
                "site": "PC",
                "source_site": "OCI",
                "copied_at_pc": store.iso(clock()),
                "pull_id": pull_id,
            }

        try:
            store.publish_copied(root, data, receipt)
            pulled.append(r["run_id"])
        except store.EvidenceError as e:
            problems.append(f"{r['run_id']}: {e}")
    shutil.rmtree(work, ignore_errors=True)
    if problems or conflicts:
        status = "CHECK_REQUIRED"
    else:
        status = "REPAIRED" if repaired else "OK"
    return {
        "status": status,
        "remote_runs": len(remote_rows),
        "already_local": len(present),
        "pulled": pulled,
        "conflicts": conflicts,
        "objects_downloaded": downloaded,
        "local_damaged_found": local_bad,
        "local_repaired": repaired,
        "problems": problems,
        "pull_id": pull_id,
    }


def upload_research(*, root: Path, remote: Remote, run_id: str, now: datetime) -> dict:
    runs, _ = store.list_runs(root)
    run = next((r for r in runs if r.run_id == run_id), None)
    if run is None or run.manifest["kind"] not in UPLOAD_KINDS:
        raise store.EvidenceError(f"연구 등록 · POC6-06 산출물 묶음 아님: {run_id}")
    bad_here = store.damaged_objects(root, run.manifest)
    if bad_here:
        raise store.EvidenceError(f"PC 사본 손상 · 없음 {len(bad_here)} — 올리지 않음")
    remote_rows, problems = _remote_list(remote)
    there = next((r for r in remote_rows if r["run_id"] == run_id), None)
    if there is not None and there["manifest_sha256"] != run.manifest_sha256:
        return {
            "status": "CHECK_REQUIRED",
            "already_on_oci": True,
            "same_manifest": False,
        }
    if there is not None and not there["damaged"]:
        return {"status": "OK", "already_on_oci": True, "same_manifest": True}
    on_oci = {s for r in remote_rows for s in r["objects"]} - {
        s for r in remote_rows for s in r["damaged"]
    }
    send = [s for s in store.manifest_object_shas(run.manifest) if s not in on_oci]
    upload_id = f"up_{now:%Y%m%dT%H%M%SZ}_{uuid.uuid4().hex[:8]}"
    rdir = f"{REMOTE_EVIDENCE}/.incoming/{upload_id}"
    rc, _ = remote.ssh(f"mkdir -p {rdir}", LIST_TIMEOUT_SEC)
    if rc != 0:
        raise store.EvidenceError(f"OCI 임시 칸 만들기 실패(rc {rc})")
    for i in range(0, len(send), CHUNK):
        rc = remote.scp_to(
            [store.object_path(root, s) for s in send[i:][:CHUNK]],
            rdir,
            SCP_TIMEOUT_SEC,
        )
        if rc != 0:
            raise store.EvidenceError(f"object 올리기 실패(rc {rc})")
    rc = remote.scp_to(
        [root / "runs" / run_id / "manifest.json"], rdir, SCP_TIMEOUT_SEC
    )
    if rc != 0:
        raise store.EvidenceError(f"manifest 올리기 실패(rc {rc})")
    cmd = (
        f"cd {REMOTE_ROOT} && venv/bin/python {CLI} accept-upload "
        f"--upload-id {upload_id} --expect-manifest-sha {run.manifest_sha256}"
    )
    rc, out = remote.ssh(cmd, ACCEPT_TIMEOUT_SEC)
    result = _last_result(out)
    return {
        "status": (result or {}).get("status", "UNKNOWN") if rc in (0, 2) else "FAILED",
        "upload_id": upload_id,
        "repair_of_oci_copy": there is not None,
        "objects_sent": len(send),
        "accept": result,
        "problems": problems,
    }


def _last_result(out: bytes) -> Optional[dict]:
    for line in reversed(out.decode("utf-8", "replace").splitlines()):
        if line.startswith("RESULT "):
            try:
                return json.loads(line[7:])
            except ValueError:
                return None
    return None


def _research_problems(m: dict) -> list[str]:
    """연구 등록 묶음이 허용 실험 · 허용 파일(경로 · 해시)만 담았는가 — 임의 파일 업로드 통로가 아니게."""
    if m.get("kind") != "RESEARCH_REGISTRATION":
        return ["연구 등록 묶음 아님"]
    exps, files = m.get("experiments"), m.get("files")
    if (
        not isinstance(exps, list)
        or not exps
        or not all(isinstance(e, dict) for e in exps)
    ):
        return ["experiments 형식 아님 · 비어 있음"]
    if not {e.get("experiment_id") for e in exps} <= research.ALLOWED_EXPERIMENTS:
        return ["허용 밖 실험"]
    if not isinstance(files, list) or not all(isinstance(f, dict) for f in files):
        return ["files 형식 아님"]
    allowed = research.allowed_files()
    got = {
        (f.get("experiment_id"), f.get("rel_path"), f.get("sha256"))
        for f in files
        if f.get("status") == "REGISTERED"
    }
    if not got or not got <= allowed:
        return ["허용 밖 파일(실험 · 경로 · 해시가 목록과 다름)"]
    if set(store.manifest_object_shas(m)) != {sha for _, _, sha in got}:
        return ["object 목록이 등록 파일과 다름"]
    return []


def accept_upload(
    *,
    root: Path,
    upload_id: str,
    expect_sha: str,
    now: datetime,
    clock: Callable[[], datetime] = store.utc_now,
) -> dict:
    """OCI 쪽 업로드 받기 — 검사를 모두 통과해야만 공개한다(실패면 아무것도 공개하지 않고 임시 칸을 남긴다)."""
    if not UPLOAD_ID.match(upload_id) or not store.HEX64.match(expect_sha):
        return {"status": "CHECK_REQUIRED", "reason": "upload_id · 해시 형식 아님"}
    base = (root / ".incoming").resolve()
    work = root / ".incoming" / upload_id
    if not work.is_dir() or work.is_symlink() or work.resolve().parent != base:
        return {"status": "CHECK_REQUIRED", "reason": "임시 칸 없음 · 경로 이상"}
    names = {p.name: p for p in work.iterdir()}
    bad = [
        n
        for n, p in names.items()
        if p.is_symlink()
        or not p.is_file()
        or not (n == "manifest.json" or store.HEX64.match(n))
    ]
    if bad or "manifest.json" not in names:
        return {
            "status": "CHECK_REQUIRED",
            "reason": "허용 밖 파일 · manifest 없음",
            "bad": bad[:10],
        }
    data = names["manifest.json"].read_bytes()
    if store.sha256_bytes(data) != expect_sha:
        return {"status": "CHECK_REQUIRED", "reason": "manifest 해시가 기대와 다름"}
    try:
        m = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {"status": "CHECK_REQUIRED", "reason": "manifest 해석 불가"}
    problems = store.validate_manifest(m)
    if not problems and m.get("kind") == forward_artifacts.KIND:

        def read(sha: str) -> Optional[bytes]:
            p = names.get(sha)
            if p is not None:
                data = p.read_bytes()
                return data if store.sha256_bytes(data) == sha else None
            return store.read_object(root, sha) if store.object_ok(root, sha) else None

        problems = forward_artifacts.problems(m, read)
    elif not problems:
        problems = _research_problems(m)
    shas = store.manifest_object_shas(m) if not problems else []
    extra = set(names) - {"manifest.json"} - set(shas)
    if extra:
        problems.append("manifest 에 없는 파일")
    for s in shas:
        p = names.get(s)
        if p is not None and store.sha256_file(p) != s:
            problems.append(f"object 해시 다름 {s[:16]}")
        elif p is None and not store.object_ok(root, s):
            problems.append(f"object 없음 · 손상 {s[:16]}")
    if problems:
        return {"status": "CHECK_REQUIRED", "reason": " · ".join(problems)}
    for s in shas:
        if s in names:
            store.put_file(root, names[s], expect_sha=s)

    def receipt() -> dict:
        return {
            "site": "OCI",
            "source_site": m.get("site"),
            "received_at": store.iso(clock()),
            "upload_id": upload_id,
        }

    sha, created = store.publish_copied(root, data, receipt)
    shutil.rmtree(work, ignore_errors=True)
    return {
        "status": "OK",
        "run_id": m["run_id"],
        "manifest_sha256": sha,
        "created": created,
        "objects": len(shas),
    }
