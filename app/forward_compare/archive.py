"""POC6-06 — 산출물을 05 보관소에 등록 · OCI 업로드(명시 실행만 · 설계 §10 · 판정 §7).

등록 = `state/ml/research/poc6_06/` 아래 아직 등록하지 않은 파일을 object 로 넣고 FORWARD_RESEARCH_ARTIFACTS 묶음
하나를 공개한다(같은 경로가 다른 해시로 이미 등록됐으면 CHECK_REQUIRED · 덮어쓰기 없음). 허용 규칙은 OCI 받기와
같은 `forward_artifacts` 를 쓴다. 모델 폴더는 training.json 이 있는(완료된) 폴더만 등록한다.
업로드 = 05 `transfer.upload_research`(같은 SSH · `accept-upload` 검사). 올리기 전 = PC_ONLY.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.forward_compare import protocol as P
from app.ml_evidence import forward_artifacts as FA
from app.ml_evidence import store


def registered(ev_root: Path) -> tuple[dict[str, str], list[str]]:
    """이미 등록된 상대 경로 → 해시 · 그 묶음 run_id 목록."""
    runs, _ = store.list_runs(ev_root)
    paths: dict[str, str] = {}
    ids = []
    for r in runs:
        if r.manifest["kind"] != FA.KIND:
            continue
        ids.append(r.run_id)
        for f in r.manifest["files"]:
            paths.setdefault(f["rel_path"], f["sha256"])
    return paths, ids


def scan(root: Path) -> tuple[list[dict], list[str]]:
    """연구 폴더의 파일 → (등록 후보, 허용 밖 · 미완료 경로)."""
    files, odd = [], []
    if not root.is_dir():
        return files, odd
    for p in sorted(root.rglob("*")):
        if not p.is_file() or any(
            part.startswith(".") for part in p.relative_to(root).parts
        ):
            continue
        rel = f"{FA.ROOT_REL}/{p.relative_to(root).as_posix()}"
        kind, parts = FA.classify(rel)
        if kind is None:
            odd.append(rel)
            continue
        if kind.startswith("model_") and not (p.parent / "training.json").is_file():
            odd.append(rel + " (모델 판 미완료)")
            continue
        files.append({"rel_path": rel, "type": kind, "path": p})
    return files, odd


def local_state(root: Path, ev_root: Path) -> dict[str, Any]:
    """SSH 없이 아는 것만 — 미등록 수 · 등록 묶음. OCI 업로드 여부는 여기서 모른다(확인 전 = 모두 PC_ONLY)."""
    files, odd = scan(root)
    reg, ids = registered(ev_root)
    return {
        "files": len(files),
        "unregistered": sum(1 for f in files if f["rel_path"] not in reg),
        "registered_runs": ids,
        "oci_confirmed": None,
        "not_allowed": odd,
        "note": (
            "OCI 업로드 확인 전 산출물은 모두 PC_ONLY — `archive --upload` 결과 OK 또는"
            " 05 `status --remote` 로 확인"
        ),
    }


@P.exclusive
def register(
    root: Path, ev_root: Path, *, now: datetime, code_commit: Optional[str]
) -> tuple[str, dict]:
    files, odd = scan(root)
    reg, _ = registered(ev_root)
    new, clash = [], []
    for f in files:
        sha = store.sha256_file(f["path"])
        if f["rel_path"] in reg:
            if reg[f["rel_path"]] != sha:
                clash.append(f["rel_path"])
            continue
        new.append(dict(f, sha256=sha))
    if clash:
        return "CHECK_REQUIRED", {
            "reason": "등록된 경로의 내용이 바뀜(한 번 쓰면 끝 위반)",
            "paths": clash[:20],
        }
    if not new:
        return "SKIPPED_NO_NEW", {"not_allowed": odd}
    objects, rows = {}, []
    for f in new:
        put = store.put_file(ev_root, f["path"], expect_sha=f["sha256"])
        rows.append(
            {
                "rel_path": f["rel_path"],
                "type": f["type"],
                "sha256": f["sha256"],
                "bytes": put["bytes"],
            }
        )
        fmt = "json" if f["rel_path"].endswith(".json") else "raw"
        objects.setdefault(
            f["sha256"],
            {
                "sha256": f["sha256"],
                "bytes": put["bytes"],
                "role": f"poc6_06_{f['type']}",
                "format": fmt,
            },
        )
    manifest = {
        "schema": store.SCHEMA,
        "run_id": store.new_run_id(now),
        "kind": FA.KIND,
        "protocol_id": FA.PROTOCOL_ID,
        "site": "PC",
        "status": "OK",
        "code_commit": code_commit,
        "registered_at": store.iso(now),
        "record_type": "FORWARD_RESEARCH_ARTIFACTS",
        "files": rows,
        "not_allowed_paths": odd,
        "objects": [objects[k] for k in sorted(objects)],
        "limits": [
            "OCI 는 bytes 보관만(모델 load · import · 학습 · 예측 0)",
            "수량 · 평단 · 계좌 · 메모 · 키 없음(연구 산출물만)",
        ],
    }
    bad = FA.problems(
        manifest,
        lambda s: (
            store.read_object(ev_root, s) if store.object_ok(ev_root, s) else None
        ),
    )
    if bad:
        return "CHECK_REQUIRED", {"reason": " · ".join(bad[:5])}
    _, published = store.publish_run(ev_root, manifest, clock=lambda: now)
    return "OK", published
