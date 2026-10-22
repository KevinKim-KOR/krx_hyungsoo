"""POC6-05 — 증거 보관소(OCI · PC 같은 구조 · git 제외).

    <root>/objects/<sha 앞 2자>/<sha256>  내용 해시가 이름 · 한 번 쓰면 끝(있으면 해시만 확인 · 덮어쓰기 없음)
    <root>/runs/<run_id>/manifest.json    완료 묶음(.partial 폴더에 쓰고 이름 바꿈) — 정본
    <root>/runs/<run_id>/receipt.json     이 장소가 받은 기록(PC 가져오기 · OCI 업로드) · 원래 장소엔 없음
    <root>/catalog.jsonl                  공개 색인(이어 씀) — runs/ 에서 다시 채울 수 있다
    <root>/.incoming/                     내려받기 · 업로드 임시 칸
    <root>/.collect.lock · .index.lock    일일 수집 단일 실행 · 공개 쓰기 잠금(fcntl)

완료 manifest 가 없는 묶음은 어디서도 읽지 않는다. 표준 라이브러리만 쓴다.
"""

from __future__ import annotations

import contextlib
import gzip
import hashlib
import json
import os
import re
import shutil
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

EVIDENCE_ROOT = Path("state/ml/evidence")
SCHEMA = "poc6_05_evidence_manifest_v1"
KINDS = ("DAILY_COLLECTION", "RESEARCH_REGISTRATION")
STATUSES = ("OK", "PARTIAL", "FAILED", "SKIPPED_NO_NEW")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
RUN_ID = re.compile(r"^\d{8}T\d{6}Z_[0-9a-f]{8}$")
ISO_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")
_ISO_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"
INDEX_LOCK_WAIT_S = 30.0
_CHUNK = 1 << 20


class EvidenceError(Exception):
    """보관소 무결성 · 충돌 · 형식 문제(자료 부족과 구분)."""


def iso(dt: datetime) -> str:
    """증거의 모든 시각 = UTC 마이크로초 `…Z` 한 형식."""
    return dt.astimezone(timezone.utc).strftime(_ISO_FMT)


def parse_iso(text: Any) -> datetime:
    """증거 시각을 실제로 해석한다(형식 · 달력 · UTC `Z` 모두 맞아야 함 · 아니면 ValueError).

    문자열인지만 보거나 문자열로 비교하지 않는다(다른 시간대 · 없는 날짜가 섞이면 순서가 틀린다).
    """
    if not isinstance(text, str) or not ISO_Z.match(text):
        raise ValueError(f"시각 형식 아님(UTC …Z 마이크로초): {str(text)[:40]}")
    return datetime.strptime(text, _ISO_FMT).replace(tzinfo=timezone.utc)


def run_id_ok(run_id: Any) -> bool:
    """run_id = `YYYYmmddTHHMMSSZ_8hex` · 날짜 부분이 실제 달력 시각이어야 함."""
    if not isinstance(run_id, str) or not RUN_ID.match(run_id):
        return False
    try:
        datetime.strptime(run_id[:16], "%Y%m%dT%H%M%SZ")
    except ValueError:
        return False
    return True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_run_id(now: datetime) -> str:
    return f"{now.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}_{uuid.uuid4().hex[:8]}"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical(obj: Any) -> bytes:
    return json.dumps(
        obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def manifest_bytes(manifest: dict) -> bytes:
    return (
        json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=1) + "\n"
    ).encode("utf-8")


def object_path(root: Path, sha: str) -> Path:
    if not HEX64.match(sha):
        raise EvidenceError(f"object 이름 형식 아님: {sha[:16]}")
    return root / "objects" / sha[:2] / sha


def _tmp_dir(root: Path) -> Path:
    d = root / "objects" / ".tmp"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _fsync_write(path: Path, data: bytes) -> None:
    with open(path, "xb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())


def _quarantine(root: Path, final: Path, sha: str) -> None:
    """이름과 내용이 다른(손상) object 는 지우지 않고 격리 폴더로 옮겨 보존한다."""
    q = root / "objects" / ".corrupt"
    q.mkdir(parents=True, exist_ok=True)
    os.replace(final, q / f"{sha}_{uuid.uuid4().hex[:8]}")


def _link_into_place(root: Path, tmp: Path, sha: str) -> tuple[bool, bool]:
    """임시 파일을 내용 해시 이름으로 공개한다. (새로 만듦, 손상본을 되살림).

    같은 이름이 이미 있고 내용이 맞으면 그대로 둔다(덮어쓰기 없음). 이름과 내용이 다르면(손상) 그 파일을
    격리 폴더로 옮기고 올바른 내용으로 되살린다 — 내용 해시가 같은 값이므로 증거를 바꾸는 것이 아니다.
    """
    final = object_path(root, sha)
    final.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(tmp, final)
        return True, False
    except FileExistsError:
        if sha256_file(final) == sha:
            return False, False
        _quarantine(root, final, sha)
        os.link(tmp, final)
        return True, True
    finally:
        tmp.unlink(missing_ok=True)


def put_bytes(root: Path, data: bytes) -> dict:
    sha = sha256_bytes(data)
    final = object_path(root, sha)
    if final.exists() and sha256_file(final) == sha:
        return {"sha256": sha, "bytes": len(data), "created": False}
    created, repaired = _link_into_place(root, _write_tmp(root, data), sha)
    return {"sha256": sha, "bytes": len(data), "created": created, "repaired": repaired}


def _write_tmp(root: Path, data: bytes) -> Path:
    tmp = _tmp_dir(root) / uuid.uuid4().hex
    _fsync_write(tmp, data)
    return tmp


def put_file(root: Path, src: Path, expect_sha: Optional[str] = None) -> dict:
    """원본 파일을 읽기만 하며 복사한다(원본 바이트 · 위치 그대로)."""
    tmp = _tmp_dir(root) / uuid.uuid4().hex
    h = hashlib.sha256()
    size = 0
    try:
        with open(src, "rb") as fin, open(tmp, "xb") as fout:
            for chunk in iter(lambda: fin.read(_CHUNK), b""):
                h.update(chunk)
                size += len(chunk)
                fout.write(chunk)
            fout.flush()
            os.fsync(fout.fileno())
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    sha = h.hexdigest()
    if expect_sha is not None and sha != expect_sha:
        tmp.unlink(missing_ok=True)
        raise EvidenceError(f"받은 파일 해시가 기대와 다름: {src.name}")
    created, repaired = _link_into_place(root, tmp, sha)
    return {"sha256": sha, "bytes": size, "created": created, "repaired": repaired}


def read_object(root: Path, sha: str) -> bytes:
    data = object_path(root, sha).read_bytes()
    if sha256_bytes(data) != sha:
        raise EvidenceError(f"object 손상: {sha[:16]}")
    return data


def read_jsonl_gz(root: Path, sha: str) -> list[dict]:
    raw = gzip.decompress(read_object(root, sha))
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line]


class GzJsonlWriter:
    """한 줄씩 흘려 쓰는 gzip JSONL object(전 종목을 메모리에 쌓지 않는다 · mtime 0 = 같은 내용 같은 바이트)."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.tmp = _tmp_dir(root) / f"{uuid.uuid4().hex}.gz"
        self._raw = open(self.tmp, "xb")
        self._gz = gzip.GzipFile(filename="", mode="wb", fileobj=self._raw, mtime=0)
        self.lines = 0

    def write(self, obj: dict) -> None:
        self._gz.write(canonical(obj) + b"\n")
        self.lines += 1

    def finish(self) -> Optional[dict]:
        """줄이 하나도 없으면 object 를 만들지 않고 None."""
        self._gz.close()
        self._raw.flush()
        os.fsync(self._raw.fileno())
        self._raw.close()
        if self.lines == 0:
            self.tmp.unlink(missing_ok=True)
            return None
        sha = sha256_file(self.tmp)
        size = self.tmp.stat().st_size
        created, repaired = _link_into_place(self.root, self.tmp, sha)
        return {
            "sha256": sha,
            "bytes": size,
            "lines": self.lines,
            "created": created,
            "repaired": repaired,
        }

    def abort(self) -> None:
        with contextlib.suppress(Exception):
            self._gz.close()
            self._raw.close()
        self.tmp.unlink(missing_ok=True)


@contextlib.contextmanager
def file_lock(path: Path, *, wait_s: float = 0.0) -> Iterator[bool]:
    """프로세스 사이 잠금(`scripts/apply_three_push_param_oci.py :: _writer_lock` 과 같은 방식).

    잡으면 True. `wait_s` 동안 못 잡으면 False(기다리지 않으면 바로 False). 파일을 닫거나 프로세스가 끝나면 풀린다.
    """
    import fcntl

    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + wait_s
    with open(path, "a", encoding="utf-8") as fh:
        while True:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    yield False
                    return
                time.sleep(0.1)
        yield True


@dataclass(frozen=True)
class RunRef:
    run_id: str
    manifest_sha256: str
    manifest: dict
    receipt: Optional[dict]


def validate_manifest(m: Any) -> list[str]:
    if not isinstance(m, dict):
        return ["manifest 가 객체가 아님"]
    problems = []
    if m.get("schema") != SCHEMA:
        problems.append("schema 다름")
    if not run_id_ok(m.get("run_id")):
        problems.append("run_id 형식 아님")
    if m.get("kind") not in KINDS:
        problems.append("kind 허용 밖")
    if m.get("status") not in STATUSES:
        problems.append("status 허용 밖")
    try:
        parse_iso(m.get("published_at"))
    except ValueError:
        problems.append("published_at 형식 아님(UTC …Z 실제 시각)")
    objs = m.get("objects")
    if not isinstance(objs, list):
        problems.append("objects 목록 없음")
    else:
        for o in objs:
            if not (
                isinstance(o, dict)
                and isinstance(o.get("sha256"), str)
                and HEX64.match(o["sha256"])
                and isinstance(o.get("bytes"), int)
            ):
                problems.append("objects 항목 형식 아님")
                break
    return problems


def manifest_object_shas(m: dict) -> list[str]:
    return sorted({o["sha256"] for o in m.get("objects", [])})


def object_ok(root: Path, sha: str) -> bool:
    """이 장소에 있고 내용 해시가 이름과 같은가."""
    p = object_path(root, sha)
    return p.is_file() and sha256_file(p) == sha


def damaged_objects(root: Path, m: dict) -> list[str]:
    """완료 묶음이 참조하는 object 중 없거나 손상된 것(이미 받은 사본도 매번 다시 본다)."""
    return [s for s in manifest_object_shas(m) if not object_ok(root, s)]


def _check_objects(root: Path, m: dict) -> None:
    for o in m["objects"]:
        p = object_path(root, o["sha256"])
        if not p.exists():
            raise EvidenceError(f"참조 object 없음: {o['sha256'][:16]}")
        if p.stat().st_size != o["bytes"] or sha256_file(p) != o["sha256"]:
            raise EvidenceError(f"참조 object 손상: {o['sha256'][:16]}")


def _catalog_line(ref_id: str, m: dict, sha: str, receipt: Optional[dict]) -> dict:
    line = {
        "run_id": ref_id,
        "kind": m.get("kind"),
        "status": m.get("status"),
        "manifest_sha256": sha,
        "published_at": m.get("published_at"),
        "site": m.get("site"),
    }
    if receipt:
        line["receipt"] = receipt
    return line


def _append_catalog(root: Path) -> None:
    """runs/ 에 있는데 색인에 없는 묶음을 모두 덧붙인다(공개 뒤 append 전에 끊겨도 다음 공개 때 채워진다)."""
    cat = root / "catalog.jsonl"
    seen = set()
    if cat.exists():
        for line in cat.read_text(encoding="utf-8").splitlines():
            with contextlib.suppress(ValueError, KeyError, TypeError):
                seen.add(json.loads(line)["run_id"])
    runs, _ = list_runs(root)
    missing = [r for r in runs if r.run_id not in seen]
    if not missing:
        return
    with open(cat, "a", encoding="utf-8") as fh:
        for r in missing:
            fh.write(
                json.dumps(
                    _catalog_line(r.run_id, r.manifest, r.manifest_sha256, r.receipt),
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )
        fh.flush()
        os.fsync(fh.fileno())


def _publish(
    root: Path,
    m: dict,
    *,
    data: Optional[bytes] = None,
    stamp: Optional[Callable[[], datetime]] = None,
    receipt: Optional[Callable[[], dict]] = None,
) -> tuple[str, bool, dict]:
    """잠금 → 참조 object 검사 → (stamp 가 있으면) 그 순간을 published_at 으로 → .partial 에 쓰고 이름 바꿈."""
    runs = root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    with file_lock(root / ".index.lock", wait_s=INDEX_LOCK_WAIT_S) as ok:
        if not ok:
            raise EvidenceError("보관 색인 잠금을 잡지 못함(busy)")
        if stamp is not None:
            m = dict(
                m, published_at=iso(stamp())
            )  # 형식 검사용 임시 값 · 검사 뒤 다시 정함
        problems = validate_manifest(m)
        if problems:
            raise EvidenceError("manifest 형식: " + " · ".join(problems))
        _check_objects(root, m)
        if stamp is not None:
            m["published_at"] = iso(stamp())  # 읽을 수 있게 되는 순간(잠금 · 검사 뒤)
            data = manifest_bytes(m)
        sha = sha256_bytes(data)
        final = runs / m["run_id"]
        if final.exists():
            existing = (final / "manifest.json").read_bytes()
            if existing != data:
                raise EvidenceError(f"같은 run_id 에 다른 내용: {m['run_id']}")
            _append_catalog(root)
            return sha, False, m
        staging = runs / f".{m['run_id']}.{uuid.uuid4().hex[:8]}.partial"
        staging.mkdir()
        try:
            _fsync_write(staging / "manifest.json", data)
            if receipt is not None:
                _fsync_write(staging / "receipt.json", manifest_bytes(receipt()))
            os.rename(staging, final)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        _append_catalog(root)
    return sha, True, m


def publish_run(
    root: Path,
    manifest: dict,
    *,
    clock: Callable[[], datetime],
    receipt: Optional[Callable[[], dict]] = None,
) -> tuple[str, dict]:
    """이 장소에서 만든 묶음을 공개한다. `published_at`(= available_at) = 잠금 · 검사 뒤 공개 순간(한 번 정함)."""
    sha, _, m = _publish(root, dict(manifest), stamp=clock, receipt=receipt)
    return sha, m


def publish_copied(
    root: Path, data: bytes, receipt: Callable[[], dict]
) -> tuple[str, bool]:
    """다른 장소에서 공개된 manifest 를 바이트 그대로 공개한다(원래 published_at 그대로 · receipt = 받은 순간)."""
    try:
        m = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise EvidenceError(f"manifest 해석 불가: {type(e).__name__}") from e
    sha, created, _ = _publish(root, m, data=data, receipt=receipt)
    return sha, created


def list_runs(root: Path) -> tuple[list[RunRef], list[str]]:
    """완료 묶음 전체(run_id 순). 점 폴더(.partial)는 미완료라 읽지 않는다."""
    out: list[RunRef] = []
    problems: list[str] = []
    runs = root / "runs"
    if not runs.exists():
        return out, problems
    for d in sorted(runs.iterdir()):
        if d.name.startswith(".") or not d.is_dir():
            continue
        try:
            data = (d / "manifest.json").read_bytes()
            m = json.loads(data.decode("utf-8"))
        except (OSError, UnicodeDecodeError, ValueError) as e:
            problems.append(f"{d.name}: manifest 읽기 불가({type(e).__name__})")
            continue
        bad = validate_manifest(m)
        if bad or m.get("run_id") != d.name:
            problems.append(
                f"{d.name}: " + (" · ".join(bad) or "폴더 이름과 run_id 다름")
            )
            continue
        receipt = None
        rp = d / "receipt.json"
        if rp.exists():
            with contextlib.suppress(OSError, ValueError, UnicodeDecodeError):
                receipt = json.loads(rp.read_text(encoding="utf-8"))
        out.append(RunRef(d.name, sha256_bytes(data), m, receipt))
    return out, problems


def partial_dirs(root: Path) -> list[str]:
    runs = root / "runs"
    return sorted(p.name for p in runs.glob(".*.partial")) if runs.exists() else []


def verify_run(root: Path, run: RunRef) -> list[str]:
    """object 해시 · 크기 · gzip JSONL 읽기(줄 수)를 다시 확인한다."""
    problems = []
    for o in run.manifest["objects"]:
        sha = o["sha256"]
        try:
            data = read_object(root, sha)
        except (OSError, EvidenceError) as e:
            problems.append(f"{sha[:16]}: {type(e).__name__}")
            continue
        if len(data) != o["bytes"]:
            problems.append(f"{sha[:16]}: 크기 다름")
        if o.get("format") == "jsonl.gz":
            try:
                n = len(read_jsonl_gz(root, sha))
            except (OSError, ValueError, EOFError) as e:
                problems.append(f"{sha[:16]}: gzip JSONL 읽기 불가({type(e).__name__})")
                continue
            if "lines" in o and n != o["lines"]:
                problems.append(f"{sha[:16]}: 줄 수 다름")
    return problems


def _read_summary(root: Path, run: RunRef) -> dict:
    out = {}
    for o in run.manifest["objects"]:
        sha = o["sha256"]
        lines = len(read_jsonl_gz(root, sha)) if o.get("format") == "jsonl.gz" else None
        out[sha] = {"bytes": len(read_object(root, sha)), "lines": lines}
    return out


def restore_check(root: Path, run_id: str, dest: Path) -> dict:
    """완료 묶음 하나를 빈 별도 경로에 복원해 같은 해시 · 목록 · 읽기 결과인지 본다(원본 위 복구 없음)."""
    root_r, dest_r = root.resolve(), dest.resolve()
    if dest_r == root_r or root_r in dest_r.parents or dest_r in root_r.parents:
        raise EvidenceError("복원 경로가 보관소와 겹침")
    if dest_r == EVIDENCE_ROOT.resolve():
        raise EvidenceError("복원 경로가 운영 보관소")
    if dest.exists() and any(dest.iterdir()):
        raise EvidenceError("복원 경로가 비어 있지 않음")
    runs, _ = list_runs(root)
    src = next((r for r in runs if r.run_id == run_id), None)
    if src is None:
        raise EvidenceError(f"완료 묶음 없음: {run_id}")
    for sha in manifest_object_shas(src.manifest):
        target = object_path(dest, sha)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(object_path(root, sha), target)
    rdir = dest / "runs" / run_id
    rdir.mkdir(parents=True)
    shutil.copyfile(root / "runs" / run_id / "manifest.json", rdir / "manifest.json")
    got, problems = list_runs(dest)
    same_list = [(r.run_id, r.manifest_sha256) for r in got] == [
        (src.run_id, src.manifest_sha256)
    ]
    problems += verify_run(dest, got[0]) if got else ["복원본에 완료 묶음 없음"]
    same_read = bool(got) and _read_summary(dest, got[0]) == _read_summary(root, src)
    ok = same_list and same_read and not problems
    return {
        "status": "OK" if ok else "FAILED",
        "run_id": run_id,
        "manifest_sha256": src.manifest_sha256,
        "objects": len(manifest_object_shas(src.manifest)),
        "same_hash_and_list": same_list,
        "same_read_result": same_read,
        "problems": problems,
        "dest": str(dest),
    }


def max_rss() -> dict:
    """최대 RSS 와 단위(Linux = KiB · macOS = bytes · 같은 원시 단위로 가정하지 않는다)."""
    import resource

    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {"raw": raw, "unit": "bytes" if sys.platform == "darwin" else "KiB"}
