"""POC6-13 C — 백업 대상 · 목적지 검사(원본 쪽 · 읽기만 · PLAN §4-1 ~ §4-4).

대상 = 08 ~ 11 연구 폴더 · 봉인 KRX DB · 코드 bundle(main + 로컬 연구 브랜치) · 02 ~ 06 입력 연결 목록.
목적지 = 사용자 소유 외장 장치(내부 디스크 · 디스크 이미지 · 확인 불가 = WAITING_TARGET · 판정 §2) 또는
`--pc-share` 로 지정한 별도 PC 의 윈도우 공유 폴더(SMB · 보완 판정 2026-10-29 · 두 검사는 따로).
쓰기 · 복사 · 복원은 `backup.py`.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import plistlib
import re
import shutil
import socket
import subprocess
import urllib.parse
from pathlib import Path
from typing import Any, Callable, Optional

from app.ml_evidence import store

TARGETS = ("poc6_08", "poc6_09", "poc6_10", "poc6_11")
RESEARCH_REL = "state/ml/research"
SEALED_REL = f"{RESEARCH_REL}/krx_etf_universe.sqlite"
BRANCHES = ("main", "research/poc6-10-local")
# PLAN §4-2 — bundle 에서 복구돼야 하는 커밋(실행 기록 · 코드 해시가 가리키는 판)
COMMITS = {
    "e499e5a53c6a247ef3a1f556595da7fc63dc3308": "08 기록 기준",
    "3df435396db5fa763fbe119228e4b30ef1b9f9ad": "08 정정 실행 코드",
    "ed18f3cef1d18ecfe8fc13b56a9e5c4e23e9faa2": "09 기록 기준",
    "49f5ab8830279370ca54cbfd723fe7fd68c85f9f": "09 실행 코드",
    "50a728dffff287bc9cb0edc007d6db854634b4c5": "10 기록 기준",
    "6779a31c3f1095a64574f7371723caa70da7c3ed": "10 실행 코드(로컬 연구 브랜치)",
    "549af63c337c7c6f7374411abfb0516db27df229": "11 최종 실행 코드",
}
# PLAN §4-3 — 08 ~ 11 이 참조하는 02 ~ 06 입력(재업로드 0 · 연결 목록)
INPUT_LINKS = [
    {
        "used_by": "08",
        "input": "05 일일 묶음(달력 · KOSPI)",
        "run_id": "20261023T004002Z_9211e9fb",
    },
    {
        "used_by": "08",
        "input": "poc6_03 copy.sqlite",
        "run_id": "20261022T103800Z_cf957e09",
    },
    {
        "used_by": "08 · 10",
        "input": "poc6_06 cohort · bootstrap",
        "run_id": "20261023T045432Z_e3570691",
    },
    {"used_by": "09", "input": "08 정정 실행 산출물", "run_id": None},
    {"used_by": "10 · 11", "input": "봉인 DB", "run_id": None},
]


class BackupError(RuntimeError):
    pass


# ── 목적지 · 대상 ───────────────────────────────────────────────────────────


def diskutil_info(mount: Path) -> Optional[dict]:
    try:
        r = subprocess.run(
            ["/usr/sbin/diskutil", "info", "-plist", str(mount)],
            capture_output=True,
            timeout=30,
            check=False,
        )
        return plistlib.loads(r.stdout) if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, plistlib.InvalidFileException):
        return None


def mount_point(p: Path) -> Path:
    p = Path(p).resolve()
    while not os.path.ismount(p):
        p = p.parent
    return p


def _dev(p: Path) -> int:
    return os.stat(p).st_dev


def device_check(
    target: Path,
    repo: Path,
    disk_info: Callable = diskutil_info,
    *,
    mount_fn: Callable = mount_point,
    dev_fn: Callable = _dev,
) -> dict:
    """외장 장치인가 — 아니면 WAITING_TARGET(내부 디스크에 대신 쓰지 않음)."""
    t = Path(target)
    if not t.is_dir():
        return {"ok": False, "reason": "목적지 폴더 없음 · 장치 마운트 안 됨"}
    mp = mount_fn(t)
    if not str(mp).startswith("/Volumes/"):
        return {"ok": False, "reason": f"내부 디스크 경로({mp})"}
    if dev_fn(mp) == dev_fn(Path(repo).resolve()):
        return {"ok": False, "reason": "저장소와 같은 볼륨"}
    info = disk_info(mp)
    if not isinstance(info, dict):
        return {
            "ok": False,
            "reason": "장치 정보 확인 불가(네트워크 공유 포함 · 별도 확인 대상)",
        }
    if info.get("Internal") is not False:
        return {"ok": False, "reason": "내부 장치(Internal 아님이 확인되지 않음)"}
    # 디스크 이미지(.dmg · .sparsebundle)는 External 로 보고될 수 있다 — 볼륨과 그 물리 저장소 모두 확인
    stores = [
        s.get("APFSPhysicalStore")
        for s in info.get("APFSPhysicalStores") or []
        if isinstance(s, dict) and s.get("APFSPhysicalStore")
    ]
    for c in [info] + [disk_info(s) for s in stores]:
        if (
            not isinstance(c, dict)
            or c.get("Internal") is not False
            or c.get("BusProtocol") == "Disk Image"
        ):
            return {
                "ok": False,
                "reason": "디스크 이미지 · 내부 물리 저장소 위의 볼륨(두 번째 물리 사본 아님)",
            }
    return {
        "ok": True,
        "mount": str(mp),
        "device": info.get("DeviceIdentifier"),
        "volume_uuid": info.get("VolumeUUID"),
        "bus": info.get("BusProtocol"),
        "fs": info.get("FilesystemType") or info.get("FilesystemName"),
        "internal": False,
    }


# ── PC 공유 폴더(SMB · 보완 판정 2026-10-29 §2) ─────────────────────────────

MOUNT_LINE = re.compile(r"^(?P<src>.+?) on (?P<mp>/.*) \((?P<fs>[^,)]+)(?:,.*)?\)$")


def parse_share(spec: str) -> tuple[str, str]:
    """`//서버/공유`(또는 `서버/공유`) → (서버, 공유) 소문자. 인증 정보(`사용자@`)는 받지 않는다."""
    s = str(spec).strip()
    s = s[2:] if s.startswith("//") else s
    server, sep, share = s.partition("/")
    share = share.strip("/")
    if "@" in server or ":" in server:
        raise BackupError(
            "--pc-share 에 사용자 · 비밀번호 · 포트 · IPv6 주소를 넣지 않는다(//서버/공유)"
        )
    if not server or not sep or not share or "/" in share:
        raise BackupError("--pc-share 형식 = //서버/공유")
    return server.lower(), share.lower()


def smb_source(source: str) -> Optional[tuple[str, str]]:
    """마운트 원본 `//[사용자@]서버/공유` → (서버, 공유) 소문자 — 사용자 · 인증 부분은 버린다(기록 안 함)."""
    if not source.startswith("//"):
        return None
    host, sep, share = source[2:].partition("/")
    share = urllib.parse.unquote(share.strip("/"))
    server = urllib.parse.unquote(host.rpartition("@")[2])
    if not server or not sep or not share or "/" in share:
        return None
    return server.lower(), share.lower()


def mount_table(runner: Callable = subprocess.run) -> Optional[list[dict]]:
    """`/sbin/mount` 표 — [{source, mount, fs}] · 읽지 못하면 None(확인 불가)."""
    try:
        r = runner(["/sbin/mount"], capture_output=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    rows = []
    for line in r.stdout.decode("utf-8", "replace").splitlines():
        m = MOUNT_LINE.match(line.strip())
        if m:
            rows.append({"source": m["src"], "mount": m["mp"], "fs": m["fs"]})
    return rows


def resolve_host(name: str) -> Optional[set[str]]:
    try:
        infos = socket.getaddrinfo(name, None)
    except (OSError, UnicodeError):
        return None
    return {i[4][0].split("%")[0] for i in infos} or None


def own_addresses(runner: Callable = subprocess.run) -> Optional[set[str]]:
    """맥북 자신의 주소(`ifconfig` 의 inet · inet6) — 읽지 못하면 None."""
    try:
        r = runner(["/sbin/ifconfig"], capture_output=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    out = set()
    for line in r.stdout.decode("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("inet", "inet6"):
            out.add(parts[1].split("%")[0])
    return out or None


def share_check(
    target: Path,
    repo: Path,
    approved: str,
    *,
    table_fn: Optional[Callable] = None,
    resolve_fn: Optional[Callable] = None,
    own_fn: Optional[Callable] = None,
    dev_fn: Optional[Callable] = None,
) -> dict:
    """사용자가 승인한 PC 의 공유 폴더(SMB) 안인가 — 확인하는 것은 그 PC 의 SMB 연결이다(PC 디스크 자체의
    원격 인증 아님). 외장 장치 검사와 섞지 않는다. 공유가 해제돼 같은 이름의 로컬 폴더만 남으면 거부한다."""
    want_server, want_share = parse_share(approved)
    table_fn, resolve_fn = table_fn or mount_table, resolve_fn or resolve_host
    own_fn, dev_fn = own_fn or own_addresses, dev_fn or _dev
    t = Path(target)
    if not t.is_dir():
        return {"ok": False, "reason": "목적지 폴더 없음 · 공유 연결 안 됨"}
    rows = table_fn()
    if rows is None:
        return {"ok": False, "reason": "마운트 표 확인 불가"}
    tr = t.resolve()
    hits = [r for r in rows if Path(r["mount"]) == tr or Path(r["mount"]) in tr.parents]
    if not hits:
        return {"ok": False, "reason": "목적지가 속한 마운트 확인 불가"}
    row = max(hits, key=lambda r: len(r["mount"]))
    if row["fs"] != "smbfs":
        return {
            "ok": False,
            "reason": f"SMB 공유 아님({row['fs']}) — 공유가 해제됐으면 로컬 폴더에 대신 쓰지 않음",
        }
    got = smb_source(row["source"])
    if got is None:
        return {"ok": False, "reason": "SMB 마운트 원본 해석 불가"}
    server, share = got
    if share != want_share:
        return {"ok": False, "reason": "승인한 공유 이름과 다름"}
    addrs = resolve_fn(server)
    if not addrs:
        return {"ok": False, "reason": "공유 서버 주소 확인 불가"}
    if server != want_server:  # 별칭은 확인된 주소 대응으로만
        want_addrs = resolve_fn(want_server)
        if not want_addrs or not addrs & want_addrs:
            return {"ok": False, "reason": "승인한 PC 와 다른 서버(주소 대응 없음)"}
    own = own_fn()
    if own is None:
        return {"ok": False, "reason": "맥북 자기 주소 확인 불가"}
    for a in addrs:
        ip = ipaddress.ip_address(a)
        if ip.is_loopback or ip.is_unspecified or a in own:
            return {"ok": False, "reason": "localhost · 맥북 자신의 주소"}
        if not ip.is_private:
            return {"ok": False, "reason": "같은 로컬 네트워크 주소 아님"}
    mount = Path(row["mount"])
    if dev_fn(tr) != dev_fn(mount):
        return {"ok": False, "reason": "목적지가 공유 마운트 위에 있지 않음"}
    if dev_fn(mount) == dev_fn(Path(repo).resolve()):
        return {"ok": False, "reason": "저장소와 같은 볼륨"}
    return {
        "ok": True,
        "kind": "PC_SHARE",
        "server": want_server,
        "share": want_share,
        "addresses": sorted(addrs),
        "mount": str(mount),
        "fs": "smbfs",
        "mount_dev": dev_fn(mount),
    }


def target_check(
    target: Path,
    repo: Path,
    pc_share: Optional[str],
    disk_info: Callable = diskutil_info,
) -> dict:
    """`--pc-share` 가 있을 때만 PC 공유 검사 · 없으면 기존 외장 장치 검사(서로 대신하지 않음)."""
    if pc_share:
        return share_check(target, repo, pc_share)
    return device_check(target, repo, disk_info)


def real_path(repo: Path, rel: str) -> Path:
    """저장소 안 그 자리의 실제 경로 — 어느 단계라도 링크면(시작 폴더 · 상위 폴더 포함) 멈춘다."""
    p = Path(repo) / rel
    if p.is_symlink() or p.resolve() != Path(repo).resolve() / rel:
        raise BackupError(f"링크 경로(범위 밖 가능): {rel}")
    return p


def sealed_path(repo: Path) -> Path:
    p = real_path(repo, SEALED_REL)
    if not p.is_file():
        raise BackupError(f"봉인 DB 없음: {SEALED_REL}")
    return p


def inventory(repo: Path) -> list[dict[str, Any]]:
    """대상 폴더의 일반 파일(점 파일 제외). 대상 폴더 자체 · 하위의 링크가 있으면 멈춘다."""
    out = []
    for name in TARGETS:
        root = real_path(repo, f"{RESEARCH_REL}/{name}")
        if not root.is_dir():
            raise BackupError(f"대상 폴더 없음: {name}")
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
            for d in dirnames:
                if (Path(dirpath) / d).is_symlink():
                    raise BackupError(f"심볼릭 폴더: {Path(dirpath) / d}")
            for fn in sorted(filenames):
                p = Path(dirpath) / fn
                rel = p.relative_to(Path(repo)).as_posix()
                if fn.startswith(".") or any(x.startswith(".") for x in rel.split("/")):
                    continue
                if p.is_symlink() or not p.is_file():
                    raise BackupError(f"일반 파일 아님: {rel}")
                st = p.stat()
                out.append({"rel": rel, "size": st.st_size, "mtime_ns": st.st_mtime_ns})
    return out


def code_refs(repo: Path, git: Callable) -> list[dict[str, Any]]:
    """각 실행 protocol 의 코드 파일 해시 ↔ 커밋 7개의 같은 파일 — 가장 많이 맞는 커밋 · 공백 수.
    커밋에 없는 경로 = 공백(`ls-tree` 목록으로 판정) · git 조회 실패는 공백으로 적지 않고 멈춘다."""
    have = {
        c: {
            x.decode("utf-8", "surrogateescape")
            for x in git(["ls-tree", "-r", "-z", "--name-only", c], repo).split(b"\0")
            if x
        }
        for c in COMMITS
    }
    rows = []
    for name in TARGETS:
        for proto in sorted((Path(repo) / RESEARCH_REL / name).glob("*/protocol.json")):
            code = json.loads(proto.read_text(encoding="utf-8")).get("code") or {}
            shas = code.get("sha256") or {}
            best = (None, -1)
            for c in COMMITS:
                hit = sum(
                    1
                    for f, s in shas.items()
                    if f in have[c]
                    and hashlib.sha256(git(["show", f"{c}:{f}"], repo)).hexdigest() == s
                )
                if hit > best[1]:
                    best = (c, hit)
            rows.append(
                {
                    "run": proto.parent.relative_to(Path(repo)).as_posix(),
                    "recorded_base": code.get("base_commit"),
                    "best_commit": best[0] if best[1] > 0 else None,
                    "matched": max(best[1], 0),
                    "files": len(shas),
                    "gap_files": len(shas) - max(best[1], 0),
                }
            )
    return rows


def git_bytes(args: list[str], cwd: Path) -> bytes:
    """git 출력 — 0 이 아닌 종료는 빈 출력이 아니라 멈춤(조회 실패를 '없음' · '공백'으로 기록하지 않게)."""
    r = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, timeout=600, check=False
    )
    if r.returncode != 0:
        raise BackupError(f"git {args[0]} 실패(종료 코드 {r.returncode})")
    return r.stdout


def git_rc(args: list[str], cwd: Path) -> int:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, timeout=600, check=False
    ).returncode


def _inputs(ev_root: Path) -> list[dict]:
    have = (
        {r.run_id for r in store.list_runs(ev_root)[0]} if ev_root.is_dir() else set()
    )
    return [
        dict(x, present_local=(x["run_id"] in have) if x["run_id"] else None)
        for x in INPUT_LINKS
    ]


def plan(
    repo: Path,
    target: Optional[Path],
    disk_info: Callable = diskutil_info,
    pc_share: Optional[str] = None,
) -> dict[str, Any]:
    inv = inventory(repo)
    by = {n: {"files": 0, "bytes": 0} for n in TARGETS}
    for f in inv:
        b = by[f["rel"].split("/")[3]]
        b["files"] += 1
        b["bytes"] += f["size"]
    sealed = sealed_path(repo)
    total = sum(f["size"] for f in inv) + sealed.stat().st_size
    out = {
        "targets": by,
        "files": len(inv),
        "bytes": sum(f["size"] for f in inv),
        "sealed_bytes": sealed.stat().st_size,
        "needed_bytes_without_bundle": total,
        "commits": COMMITS,
        "inputs": _inputs(Path(repo) / store.EVIDENCE_ROOT),
    }
    if target is not None:
        dev = target_check(target, repo, pc_share, disk_info)
        if dev["ok"]:
            dev["free_bytes"] = shutil.disk_usage(target).free
        out["target"] = dev
    return out
