"""운영 파일을 읽지 않고 검증 소스 범위와 최종 판정을 기록한다."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from datetime import datetime, timezone

USER_DOCUMENT = "docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md"
DENIED_DIRS = {
    "state",
    "logs",
    "znotes",
    "secret",
    "backup",
    "data",
    "reports",
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".next",
    ".aws",
}
DENIED_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".pem", ".key", ".p12"}
VERDICTS = (
    "VERIFIED",
    "VERIFIED_WITH_NOTES",
    "PARTIALLY_VERIFIED",
    "REJECTED",
    "BLOCKED",
)
PASS_VERDICTS = set(VERDICTS[:3])


class ScopeError(Exception):
    """누락되거나 변한 검증 근거."""


def git(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, timeout=8, check=False
    )
    if result.returncode:
        raise ScopeError("Git 조회 실패: " + " ".join(args[:2]))
    return result.stdout.decode("utf-8", errors="surrogateescape")


def repo_root(path):
    return Path(git(Path(path), "rev-parse", "--show-toplevel").strip()).resolve()


def safe_relative(name):
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ScopeError("저장소 내부 상대 경로가 필요합니다: " + str(name))
    return path.as_posix()


def excluded(name):
    path = Path(name)
    return (
        name == USER_DOCUMENT
        or bool(set(path.parts) & DENIED_DIRS)
        or (path.name.startswith(".env") and path.name != ".env.example")
        or path.suffix.lower() in DENIED_SUFFIXES
        or any(path.name.endswith(suffix) for suffix in ("-wal", "-shm", "-journal"))
    )


def status_entries(repo):
    chunks = iter(
        git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all").split("\0")
    )
    entries = {}
    for chunk in chunks:
        if not chunk:
            continue
        code, name = chunk[:2], safe_relative(chunk[3:])
        entries[name] = {"status": code}
        if "R" in code or "C" in code:
            entries[name]["from"] = safe_relative(next(chunks))
    return entries


def file_facts(repo, name):
    path = repo
    for part in Path(name).parts:
        path = path / part
        if path.is_symlink():
            return {"problem": "심볼릭 링크는 따라 읽지 않음"}
    if not path.exists():
        return {"deleted": True}
    if not path.is_file():
        return {"problem": "일반 파일이 아님"}
    try:
        content = path.read_bytes()
    except OSError:
        return {"problem": "파일 해시 조회 실패"}
    facts = {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
    if path.suffix in {".py", ".ts", ".tsx", ".md"}:
        facts["lines"] = content.count(b"\n")  # wc -l과 같은 기준
    return facts


def capture(repo, inputs):
    entries = status_entries(repo)
    index = {}
    for item in git(repo, "ls-files", "--stage", "-z").split("\0"):
        if item:
            meta, name = item.split("\t", 1)
            index.setdefault(name, []).append(meta)
    files, problems, omitted = {}, [], []
    for name in sorted(set(entries) | set(inputs)):
        name = safe_relative(name)
        if excluded(name):
            omitted.append(name)
            if entries.get(name, {}).get("status") != "??":
                problems.append(name + ": 읽기 제외된 변경 또는 입력")
            continue
        facts = file_facts(repo, name)
        files[name] = {
            "status": entries.get(name, {}).get("status", "  "),
            "index": index.get(name, []),
            "file": facts,
        }
        if "from" in entries.get(name, {}):
            files[name]["from"] = entries[name]["from"]
        if files[name]["status"] == "??":
            problems.append(name + ": Git 비추적 산출물(배포 경로에 없음)")
        if "U" in files[name]["status"] or any(
            not stage.endswith(" 0") for stage in files[name]["index"]
        ):
            problems.append(name + ": 병합 충돌 미해결")
        if facts.get("problem"):
            problems.append(name + ": " + facts["problem"])
        if name in inputs and facts.get("deleted"):
            problems.append(name + ": 입력 문서가 없음")
    totals = {
        "staged": sum(
            value["status"][0] not in {" ", "?"} for value in entries.values()
        ),
        "unstaged": sum(
            value["status"][1] not in {" ", "?"} for value in entries.values()
        ),
        "untracked": sum(value["status"] == "??" for value in entries.values()),
    }
    return {
        "head": git(repo, "rev-parse", "HEAD").strip(),
        "files": files,
        "totals": totals,
        "omitted": omitted,
        "problems": problems,
        "head_changes": [
            name
            for name in git(repo, "diff", "--name-only", "-z", "HEAD").split("\0")
            if name and not excluded(name)
        ],
    }


def differences(before, after, accepted_docs=()):
    changes = []
    if before["head"] != after["head"]:
        changes.append("HEAD 변경")
    for name in sorted(set(before["files"]) | set(after["files"])):
        if name not in accepted_docs and before["files"].get(name) != after[
            "files"
        ].get(name):
            changes.append(name)
    return changes


def record_path(repo, session_id, storage=None):
    if not session_id or not session_id.strip():
        raise ScopeError("CODEX_THREAD_ID가 없으면 --session-id를 명시하세요")
    root = (
        Path(storage)
        if storage
        else Path(tempfile.gettempdir()).resolve() / "krx-codex-verify"
    )
    if root.is_symlink() or repo == root.resolve() or repo in root.resolve().parents:
        raise ScopeError("검증 근거 경로는 저장소 밖 일반 디렉터리여야 합니다")
    repo_key = hashlib.sha256(str(repo).encode()).hexdigest()[:16]
    session_key = hashlib.sha256(session_id.encode()).hexdigest()[:24]
    return root / repo_key / session_key / "session.json"


def read_record(path):
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ScopeError("검증 근거의 심볼릭 링크는 허용하지 않습니다")
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        snapshot = value["snapshot"]
        if (
            value["phase"] not in {"verifying", "finished"}
            or not isinstance(value["inputs"], list)
            or not all(isinstance(name, str) for name in value["inputs"])
            or not isinstance(snapshot["head"], str)
            or not isinstance(snapshot["files"], dict)
            or not isinstance(snapshot["problems"], list)
            or (value["phase"] == "finished" and value["verdict"] not in VERDICTS)
        ):
            raise ValueError
        return value
    except (OSError, ValueError, KeyError, TypeError):
        raise ScopeError("검증 근거 파일 손상") from None


def write_record(path, value):
    for directory in reversed(list(path.parents)[:3]):
        if directory.is_symlink():
            raise ScopeError("검증 근거 경로에 심볼릭 링크가 있습니다")
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if hasattr(os, "getuid") and directory.stat().st_uid != os.getuid():
            raise ScopeError("검증 근거 경로의 소유자가 다릅니다")
        directory.chmod(0o700)
    descriptor, temporary = tempfile.mkstemp(
        dir=path.parent, prefix=".record-", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=True, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def start(repo, path, inputs):
    previous = read_record(path)
    if previous and previous["phase"] == "verifying":
        raise ScopeError(
            "이미 진행 중인 검증이 있습니다. 먼저 finish로 판정을 기록하세요"
        )
    if not inputs:
        raise ScopeError("설계·PLAN·결과서 등 실제 입력 경로를 --input으로 명시하세요")
    names = [safe_relative(name) for name in inputs]
    if any(excluded(name) for name in names):
        raise ScopeError("읽기 금지 경로를 검증 입력으로 사용할 수 없습니다")
    snapshot = capture(repo, names)
    if any(snapshot["files"][name]["file"].get("deleted") for name in names):
        raise ScopeError("입력 파일이 없습니다")
    record = {"phase": "verifying", "inputs": names, "snapshot": snapshot}
    record["started_at"] = datetime.now(timezone.utc).isoformat()
    write_record(path, record)
    return record


def check(repo, path):
    record = read_record(path)
    if record is None:
        raise ScopeError("검증 시작 기록이 없습니다")
    current = capture(repo, record["inputs"])
    changes = differences(record["snapshot"], current)
    return record, current, changes


def finish(repo, path, verdict, accepted_docs=(), reason=""):
    record, current, changes = check(repo, path)
    if verdict not in VERDICTS:
        raise ScopeError("허용되지 않은 판정")
    accepted = [safe_relative(name) for name in accepted_docs]
    for name in accepted:
        if (
            excluded(name)
            or Path(name).suffix != ".md"
            or not reason.strip()
            or name not in record["snapshot"]["files"]
            or name not in current["files"]
            or current["files"][name]["file"].get("deleted")
            or current["files"][name].get("from")
        ):
            raise ScopeError(
                "문서 정정은 기존 검증 범위의 .md 파일과 정정 사유만 허용합니다"
            )
    pending = differences(record["snapshot"], current, accepted)
    if verdict in PASS_VERDICTS and (pending or current["problems"]):
        raise ScopeError("통과 기록 불가: " + "; ".join(pending + current["problems"]))
    record.update(
        phase="finished",
        verdict=verdict,
        snapshot=current,
        scope_changes=changes,
        doc_corrections={name: reason for name in accepted},
        finished_at=datetime.now(timezone.utc).isoformat(),
    )
    write_record(path, record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("begin", "check", "finish"))
    parser.add_argument("--repo", default=".")
    parser.add_argument("--session-id", default=os.environ.get("CODEX_THREAD_ID"))
    parser.add_argument("--input", action="append", default=[])
    parser.add_argument("--verdict", choices=VERDICTS)
    parser.add_argument("--accept-doc", action="append", default=[])
    parser.add_argument("--doc-reason", default="")
    args = parser.parse_args()
    try:
        repo = repo_root(args.repo)
        path = record_path(repo, args.session_id)
        if args.action == "begin":
            record = start(repo, path, args.input)
        elif args.action == "finish":
            record = finish(repo, path, args.verdict, args.accept_doc, args.doc_reason)
        else:
            record, current, changes = check(repo, path)
            print(
                json.dumps(
                    {"changes": changes, "problems": current["problems"]},
                    ensure_ascii=False,
                )
            )
            return int(bool(changes or current["problems"]))
        print(json.dumps({"record": str(path), **record}, ensure_ascii=False, indent=2))
        return 0
    except (ScopeError, OSError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
