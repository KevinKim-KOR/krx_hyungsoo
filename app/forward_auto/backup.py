"""POC6-13 C — 08 ~ 11 연구 산출물 · 봉인 KRX DB · 코드 bundle 의 외장 장치 사본 1회 · 복원 확인(PLAN §4).

```text
목적지   사용자 소유 다른 물리 저장소(외장 장치) — `diskutil info` Internal = 아니오 인 /Volumes 마운트만.
         내부 디스크 · 다른 APFS 볼륨 · 확인 불가(네트워크 공유 포함) = WAITING_TARGET. OCI 전송 없음(판정 §2).
복사     <목적지>/krx_hyungsoo_private_backup/poc6_13/<id>.partial/ 에 쓰고, 목적지에서 다시 읽은 해시가
         manifest 와 맞을 때만 <id>/ 로 이름을 바꾼다(COPY_HASH_OK). 같은 id 는 덮어쓰지 않는다.
복원     최종 폴더를 맥북의 빈 임시 칸으로 되가져와 풀고 파일별 해시 · 봉인 DB 해시 · 커밋 7개 확인(RESTORE_VERIFIED).
```
원본은 읽기만 한다(묶는 동안 크기 · 수정 시각이 바뀌면 완료하지 않음). 모델 파일은 바이트 대조만 —
'바이트 복원 완료'는 '과거 실행 완전 재현'이 아니다. 실행 코드가 커밋으로 남지 않은 옛 실행은 공백 그대로 적는다.
"""

from __future__ import annotations

import errno
import fcntl
import hashlib
import importlib.metadata as md
import io
import json
import os
import platform
import re
import shutil
import stat
import sys
import tarfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Optional

from app.forward_auto import backup_source as SRC
from app.forward_auto import schedule as S
from app.forward_auto import status as ST
from app.ml_evidence import store

DEST = ("krx_hyungsoo_private_backup", "poc6_13")
TAR_NAME, DB_NAME, BUNDLE_NAME = (
    "research_poc6_08_11.tar",
    "krx_etf_universe.sqlite",
    "code.bundle",
)
ARTIFACTS = (DB_NAME, TAR_NAME, BUNDLE_NAME, "env.json", "inputs.json")
CHUNK = 4 * 1024 * 1024
BACKUP_ID = re.compile(r"^backup_\d{8}T\d{6}Z_[0-9a-f]{8}$")

# ── 쓰기 · 대조 ────────────────────────────────────────────────────────────


def _fsync_full(fd: int) -> None:
    """macOS 는 fsync 가 장치 캐시까지 비우지 않는다 — 가능하면 F_FULLFSYNC."""
    try:
        fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
    except (AttributeError, OSError):
        os.fsync(fd)


def _sync_all(folder: Path) -> None:
    """목적지 칸의 모든 파일과 폴더 자체를 장치까지 동기화(이름 바꾸기 전)."""
    for p in sorted(folder.iterdir()):
        fd = os.open(p, os.O_RDONLY)
        try:
            _fsync_full(fd)
        finally:
            os.close(fd)
    _fsync_dir(folder)


def _fsync_dir(folder: Path) -> None:
    fd = os.open(folder, os.O_RDONLY)
    try:
        _fsync_full(fd)
    finally:
        os.close(fd)


def _device(path: Path) -> int:
    return os.stat(path).st_dev


def _open_ext(path: Path, dev: int):
    """외장 사본 파일 — 링크를 따라가지 않고 목적지 장치의 일반 파일일 때만 연다(링크 너머 내부 본문을
    '외장 사본'으로 대조 · 복원 확인하지 않게 · 검증자 r2 F3)."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as e:
        if e.errno == errno.ELOOP:
            raise SRC.BackupError(f"외장 사본 파일이 링크: {path.name}") from e
        raise
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_dev != dev:
            raise SRC.BackupError(
                f"외장 사본이 목적지 장치의 일반 파일이 아님: {path.name}"
            )
        return os.fdopen(fd, "rb")
    except BaseException:
        os.close(fd)
        raise


def _hash_ext(path: Path, dev: int) -> str:
    h = hashlib.sha256()
    with _open_ext(path, dev) as fh:
        while chunk := fh.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def _copy_hash(src: Path, dst: Path, dev: Optional[int] = None) -> str:
    """dev 를 주면 원본(외장 사본)을 `_open_ext` 로 연다."""
    h = hashlib.sha256()
    fi = open(src, "rb") if dev is None else _open_ext(src, dev)
    with fi, open(dst, "xb") as fo:
        while chunk := fi.read(CHUNK):
            h.update(chunk)
            fo.write(chunk)
        fo.flush()
        _fsync_full(fo.fileno())
    return h.hexdigest()


def _record(ops: Path, bid: str, stage: str, now: datetime, **detail: Any) -> None:
    seqs = []
    for f in (
        (ops / "backup").glob(f"{bid}.*.json") if (ops / "backup").is_dir() else []
    ):
        try:
            seqs.append(int(f.name.removeprefix(f"{bid}.").split(".", 1)[0]))
        except ValueError:
            continue
    seq = (
        max(seqs, default=-1) + 1
    )  # 파일 수가 아니라 최대 번호 + 1(빠진 기록이 있어도 겹치지 않음)
    ST.write_once(
        ops / "backup" / f"{bid}.{seq:02d}.{stage}.json",
        {
            "schema": "poc6_13_backup_v1",
            "backup_id": bid,
            "stage": stage,
            "seq": seq,
            "recorded_at": store.iso(now),
            **detail,
        },
    )


def _recorded_manifest(ops: Path, bid: str) -> Optional[str]:
    """그 백업의 COPY_HASH_OK 기록에 남긴 manifest 해시 — 기록 파일이 없으면 None, 있는데 읽지 못하거나
    해시가 아니면 멈춘다(읽기 오류를 '기록 없음'으로 바꿔 대조를 건너뛰지 않게)."""
    found = sorted((ops / "backup").glob(f"{bid}.*.COPY_HASH_OK.json"))
    if not found:
        return None
    try:
        rec = ST.P06.read_json(found[0])
    except (OSError, ValueError) as e:
        raise SRC.BackupError(f"복사 기록을 읽지 못함: {found[0].name}") from e
    sha = rec.get("manifest_sha256") if isinstance(rec, dict) else None
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
        raise SRC.BackupError(f"복사 기록의 manifest 해시 형식 아님: {found[0].name}")
    return sha


def _dest(target: Path, *, create: bool = False) -> Path:
    """목적지 아래 백업 폴더 — 각 단계가 링크가 아니고 실제 경로가 목적지 안 · 같은 장치여야 한다
    (장치 검사를 통과한 외장 목적지 밖으로 쓰기가 새지 않게 · 검증자 r1 F3)."""
    t = Path(target).resolve()
    cur = t
    for part in DEST:
        cur = cur / part
        if cur.is_symlink():
            raise SRC.BackupError(f"목적지 아래 링크: {cur}")
        if create and not cur.exists():
            cur.mkdir()
    if cur.exists() and (
        cur.resolve() != t.joinpath(*DEST) or os.stat(cur).st_dev != os.stat(t).st_dev
    ):
        raise SRC.BackupError("목적지 실제 경로가 외장 목적지 밖")
    return cur


def run(
    repo: Path,
    target: Path,
    *,
    clock: Callable[[], datetime] = store.utc_now,
    disk_info: Callable = SRC.diskutil_info,
    seal: Optional[Callable[[Path], dict]] = None,
    git: Callable = SRC.git_bytes,
    git_ok: Callable = SRC.git_rc,
    awake_fn: Optional[Callable] = None,
) -> dict[str, Any]:
    from app.forward_auto.runner import awake

    paths = ST.Paths.default(repo)
    now = clock()
    if not S.backup_allowed(now):
        return {"status": "REFUSED", "reason": "10:00 ~ 15:45 KST 에는 시작하지 않음"}
    dev = SRC.device_check(target, repo, disk_info)
    if not dev["ok"]:
        return {"status": "WAITING_TARGET", "reason": dev["reason"]}
    inv = SRC.inventory(repo)
    sealed = SRC.sealed_path(repo)
    need = sum(f["size"] for f in inv) + sealed.stat().st_size
    if shutil.disk_usage(target).free < need * 1.2 + 512 * 1024 * 1024:
        return {"status": "WAITING_TARGET", "reason": "목적지 여유 공간 부족"}
    bid = f"backup_{now.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}_{uuid.uuid4().hex[:8]}"
    try:
        droot = _dest(target, create=True)
    except (SRC.BackupError, OSError) as e:
        return {"status": "WAITING_TARGET", "reason": f"{type(e).__name__}: {e}"}
    ext_dev = _device(Path(target).resolve())
    final, part = droot / bid, droot / f"{bid}.partial"
    if final.exists() or part.exists():
        return {"status": "REFUSED", "reason": "같은 id 가 이미 있음(덮어쓰기 없음)"}
    t0 = time.monotonic()
    with store.file_lock(paths.ops / ".backup.lock", wait_s=0.0) as ok:
        if not ok:
            return {"status": "REFUSED", "reason": "다른 백업 실행 중"}
        _record(paths.ops, bid, "COPY_INCOMPLETE", now, detail="복사 중", target=dev)
        try:
            with (
                awake_fn or awake
            )() as aw:  # 쓰기 · 대조 · 이름 바꾸기 전체가 작업 생애
                out = _write(repo, inv, sealed, part, seal, git, git_ok, t0)
                _sync_all(part)
                msha = _check_written(part, out, repo, git_ok, ext_dev)
                os.rename(part, final)
                _fsync_dir(final.parent)
        except (
            Exception
        ) as e:  # noqa: BLE001 — .partial 은 남기고(정상 목록 아님) 사유 기록
            _record(
                paths.ops,
                bid,
                "COPY_INCOMPLETE",
                clock(),
                detail=f"{type(e).__name__}: {str(e)[:300]}",
                target=dev,
            )
            return {
                "status": "COPY_INCOMPLETE",
                "backup_id": bid,
                "error": f"{type(e).__name__}: {e}",
            }
        _record(
            paths.ops,
            bid,
            "COPY_HASH_OK",
            clock(),
            detail=str(final),
            target=dev,
            manifest_sha256=msha,
            awake=aw,
        )
    return {
        "status": "COPY_HASH_OK",
        "backup_id": bid,
        "path": str(final),
        "manifest_sha256": msha,
    }


def _limit(t0: float) -> None:
    if time.monotonic() - t0 > S.BACKUP_LIMIT_S:
        raise SRC.BackupError("60분 상한 초과")


def _write_new(path: Path, data: bytes) -> str:
    """새 파일로만 쓰고(있으면 실패) **쓴 바이트**의 해시를 돌려준다(기대 해시를 목적지에서 다시 읽지 않게)."""
    with open(path, "xb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    return hashlib.sha256(data).hexdigest()


def _source(repo: Path, rel: str) -> Path:
    """목록 뒤 원본 경로의 어느 단계(상위 폴더 포함)가 링크로 바뀌었으면 멈춘다(읽기 직전 재확인)."""
    try:
        return SRC.real_path(repo, rel)
    except SRC.BackupError as e:
        raise SRC.BackupError(f"원본이 링크로 바뀜: {rel}") from e


def _write(repo, inv, sealed, part, seal, git, git_ok, t0) -> dict[str, Any]:
    from app import krx_sealed_reader as K

    part.mkdir()  # 상위(_dest)는 이미 검사 · 생성됨 — 새 칸만 만든다(있으면 실패)
    _source(repo, SRC.SEALED_REL)
    st0 = sealed.stat()
    s = (seal or (lambda p: K.verify_sealed_source(p)))(sealed)
    db_sha = _copy_hash(sealed, part / DB_NAME)
    st1 = sealed.stat()
    if db_sha != s["file_sha256"] or (st0.st_size, st0.st_mtime_ns) != (
        st1.st_size,
        st1.st_mtime_ns,
    ):
        raise SRC.BackupError("봉인 DB 가 봉인 해시와 다르거나 복사 중 바뀜")
    _limit(t0)
    files = []
    with tarfile.open(part / TAR_NAME, "x", format=tarfile.PAX_FORMAT) as tar:
        for f in inv:
            p = _source(repo, f["rel"])
            data = p.read_bytes()
            st = p.stat()
            if (len(data), st.st_size, st.st_mtime_ns) != (
                f["size"],
                f["size"],
                f["mtime_ns"],
            ):
                raise SRC.BackupError(f"원본이 묶는 동안 바뀜: {f['rel']}")
            info = tarfile.TarInfo(f["rel"])
            info.size, info.mtime, info.mode = len(data), st.st_mtime, 0o644
            tar.addfile(info, io.BytesIO(data))
            files.append(
                {
                    "rel": f["rel"],
                    "size": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
    _limit(t0)
    if git_ok(["bundle", "create", str(part / BUNDLE_NAME), *SRC.BRANCHES], repo) != 0:
        raise SRC.BackupError("git bundle 만들기 실패")
    heads = git(["bundle", "list-heads", str(part / BUNDLE_NAME)], repo).decode(
        "utf-8", "replace"
    )
    refs = {x.split()[1] for x in heads.splitlines() if len(x.split()) == 2}
    if not {f"refs/heads/{b}" for b in SRC.BRANCHES} <= refs:
        raise SRC.BackupError("bundle 머리 목록에 정해진 브랜치가 없음")
    env = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": sorted(
            f"{d.metadata['Name']}=={d.version}"
            for d in md.distributions()
            if d.metadata["Name"]
        ),
    }
    inputs = SRC._inputs(Path(repo) / store.EVIDENCE_ROOT)
    # 기대 해시: DB = 원본에서 읽으며 잰 값 · env · inputs = 쓴 바이트 · tar · bundle = 목적지에서 읽은 값
    # (tar 내용은 원본 해시와, bundle 은 git bundle verify 로 `_check_written` 이 따로 대조한다)
    wrote = {
        DB_NAME: db_sha,
        "env.json": _write_new(
            part / "env.json",
            json.dumps(env, ensure_ascii=False, indent=1).encode("utf-8"),
        ),
        "inputs.json": _write_new(
            part / "inputs.json",
            json.dumps(inputs, ensure_ascii=False, indent=1).encode("utf-8"),
        ),
    }
    manifest = {
        "schema": "poc6_13_backup_manifest_v1",
        "created_at": store.iso(store.utc_now()),
        "sealed": {
            "rel": SRC.SEALED_REL,
            "file_sha256": s["file_sha256"],
            "content_sha256": s.get("content_sha256"),
            "bytes": st1.st_size,
        },
        "files": files,
        "artifacts": {
            n: {
                "sha256": wrote.get(n) or store.sha256_file(part / n),
                "bytes": (part / n).stat().st_size,
            }
            for n in ARTIFACTS
        },
        "bundle_heads": heads.splitlines(),
        "commits": SRC.COMMITS,
        "code_refs": SRC.code_refs(repo, git),
        "note": "바이트 복원 확인용 — 과거 실행의 완전 재현 보장 아님 · 코드 보존 공백은 code_refs.gap_files",
    }
    data = json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True).encode(
        "utf-8"
    )
    return {
        "manifest": manifest,
        "manifest_sha256": _write_new(part / "manifest.json", data),
    }


def _check_written(
    part: Path, out: dict, repo: Path, git_ok: Callable, dev: int
) -> str:
    """이름 바꾸기 전 목적지 대조 — 묶음 파일 = 목적지 장치의 일반 파일 · 해시 · 봉인 DB = 봉인 해시 · tar 안
    파일 = **원본에서 읽은** 해시 · 목록 일치 · bundle 검사 · manifest = 쓴 바이트의 해시. 하나라도 어긋나면
    .partial 그대로(COPY_INCOMPLETE). 목적지에서 다시 읽은 manifest 해시를 돌려준다."""
    manifest = out["manifest"]
    for n, a in manifest["artifacts"].items():
        if _hash_ext(part / n, dev) != a["sha256"]:
            raise SRC.BackupError(f"목적지 해시 다름: {n}")
    if manifest["artifacts"][DB_NAME]["sha256"] != manifest["sealed"]["file_sha256"]:
        raise SRC.BackupError("봉인 DB 사본 해시가 봉인 해시와 다름")
    want = {f["rel"]: f["sha256"] for f in manifest["files"]}
    got: dict[str, str] = {}
    with _open_ext(part / TAR_NAME, dev) as fh, tarfile.open(
        fileobj=fh, mode="r"
    ) as tar:
        for m in tar.getmembers():
            if not m.isreg() or not _safe_name(m.name) or m.name in got:
                raise SRC.BackupError(f"허용 밖 묶음 항목: {m.name}")
            got[m.name] = hashlib.sha256(tar.extractfile(m).read()).hexdigest()
    if got != want:
        raise SRC.BackupError("목적지 tar 안 파일이 원본 해시와 다름")
    if git_ok(["bundle", "verify", "-q", str(part / BUNDLE_NAME)], repo) != 0:
        raise SRC.BackupError("목적지 bundle 검사 실패")
    msha = _hash_ext(part / "manifest.json", dev)
    if msha != out["manifest_sha256"]:
        raise SRC.BackupError("목적지 manifest 가 쓴 내용과 다름")
    return msha


def verify(
    repo: Path,
    target: Path,
    backup_id: str,
    *,
    clock: Callable[[], datetime] = store.utc_now,
    disk_info: Callable = SRC.diskutil_info,
    git_ok: Callable = SRC.git_rc,
    awake_fn: Optional[Callable] = None,
    keep: bool = False,
) -> dict[str, Any]:
    """외장 최종 폴더 → 맥북 빈 임시 칸 → 풀기 · 해시 · 커밋 7개(RESTORE_VERIFIED). 라이브 위로 풀지 않는다."""
    from app.forward_auto.runner import awake

    paths = ST.Paths.default(repo)
    if not BACKUP_ID.match(str(backup_id)):
        return {"status": "REFUSED", "reason": "backup_id 형식 아님"}
    if not S.backup_allowed(clock()):
        return {"status": "REFUSED", "reason": "10:00 ~ 15:45 KST 에는 시작하지 않음"}
    dev = SRC.device_check(target, repo, disk_info)
    if not dev["ok"]:
        return {"status": "REFUSED", "reason": f"목적지 장치 아님: {dev['reason']}"}
    try:
        final = _dest(target) / backup_id
    except SRC.BackupError as e:
        return {"status": "REFUSED", "reason": str(e)}
    ext_dev = _device(Path(target).resolve())
    if final.is_symlink() or not (final / "manifest.json").is_file():
        return {
            "status": "REFUSED",
            "reason": "완료된 백업 폴더 없음(.partial 은 대상 아님)",
        }
    restore = paths.ops / "restore" / backup_id
    if restore.exists():
        return {"status": "REFUSED", "reason": "복원 임시 칸이 비어 있지 않음"}
    with store.file_lock(paths.ops / ".backup.lock", wait_s=0.0) as ok:
        if not ok:
            return {"status": "REFUSED", "reason": "다른 백업 실행 중"}
        restore.mkdir(parents=True)
        try:
            with (awake_fn or awake)():
                with _open_ext(final / "manifest.json", ext_dev) as fh:
                    mbytes = fh.read()
                rec = _recorded_manifest(paths.ops, backup_id)
                if rec is not None and store.sha256_bytes(mbytes) != rec:
                    raise SRC.BackupError("외장 manifest 가 복사 때 기록한 해시와 다름")
                res = _restore(final, restore, git_ok, mbytes, ext_dev)
                res["manifest_recorded"] = rec is not None
        except Exception as e:  # noqa: BLE001
            res = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:300]}"}
        finally:
            if not keep:
                shutil.rmtree(restore, ignore_errors=True)
        if (
            not keep and restore.exists()
        ):  # 정리 실패를 숨기지 않는다(복원 판정과 따로 표시)
            res["cleanup"] = f"복원 임시 칸 남음: {restore}"
        stage = "RESTORE_VERIFIED" if res.get("ok") else "RESTORE_FAILED"
        _record(
            paths.ops,
            backup_id,
            stage,
            clock(),
            detail=res.get("error")
            or "바이트 복원 · 커밋 확인 완료(완전 재현 보장 아님)",
            result=res,
        )
    return {"status": stage, "backup_id": backup_id, **res}


def _safe_name(name: str) -> bool:
    pp = PurePosixPath(name)
    return (
        not pp.is_absolute()
        and ".." not in pp.parts
        and name == pp.as_posix()
        and name.startswith(SRC.RESEARCH_REL + "/")
    )


def _restore(
    final: Path, restore: Path, git_ok: Callable, mbytes: bytes, dev: int
) -> dict[str, Any]:
    """외장 최종 폴더의 정해진 묶음 파일(ARTIFACTS)만 `_open_ext` 로 되가져온다."""
    manifest = json.loads(mbytes.decode("utf-8"))
    if sorted(manifest["artifacts"]) != sorted(ARTIFACTS):
        raise SRC.BackupError("manifest 의 묶음 파일 목록이 정해진 5개와 다름")
    if sorted(manifest["commits"]) != sorted(SRC.COMMITS):
        raise SRC.BackupError("manifest 의 커밋 목록이 정해진 커밋과 다름")
    copy = restore / "copy"
    copy.mkdir()
    for n, a in manifest["artifacts"].items():
        if _copy_hash(final / n, copy / n, dev) != a["sha256"]:
            raise SRC.BackupError(f"되가져온 사본 해시 다름: {n}")
    want = {f["rel"]: f for f in manifest["files"]}
    got = {}
    files = restore / "files"
    with tarfile.open(copy / TAR_NAME, "r") as tar:
        for m in tar.getmembers():
            if not m.isreg() or not _safe_name(m.name) or m.name in got:
                raise SRC.BackupError(f"허용 밖 묶음 항목: {m.name}")
            data = tar.extractfile(m).read()
            dst = files / m.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            got[m.name] = hashlib.sha256(data).hexdigest()
    if set(got) != set(want) or any(got[k] != want[k]["sha256"] for k in want):
        raise SRC.BackupError("풀린 파일 목록 · 해시가 manifest 와 다름")
    if store.sha256_file(copy / DB_NAME) != manifest["sealed"]["file_sha256"]:
        raise SRC.BackupError("봉인 DB 사본 해시 다름")
    gdir = restore / "git"
    gdir.mkdir()
    bundle = str(copy / BUNDLE_NAME)
    steps = [
        ["init", "--bare", "-q"],
        ["bundle", "verify", "-q", bundle],
        ["fetch", "-q", bundle, "refs/heads/*:refs/heads/*"],
    ]
    for s in steps:
        if git_ok(s, gdir) != 0:
            raise SRC.BackupError(f"git {s[0]} 실패")
    missing = [
        c
        for c in manifest["commits"]
        if git_ok(["cat-file", "-e", f"{c}^{{commit}}"], gdir) != 0
    ]
    if missing:
        raise SRC.BackupError(f"bundle 에 없는 커밋 {len(missing)}")
    return {
        "ok": True,
        "files": len(got),
        "commits": len(manifest["commits"]),
        "sealed_sha256": manifest["sealed"]["file_sha256"],
    }
