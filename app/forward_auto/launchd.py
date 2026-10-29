"""POC6-13 — 사용자 LaunchAgent 1개 만들기 · 설치 · 해제(`--apply` 없으면 dry-run · PLAN §3-1).

자기 Label 의 plist 하나만 만든다(절대 파이썬 · 절대 스크립트 · 저장소 작업 경로 · KST 일정 4개 · 로그인 1회 ·
KeepAlive 없음). 다른 작업 · crontab · 전원 설정은 바꾸지 않는다. 해제 = bootout + 자기 plist 삭제만.
"""

from __future__ import annotations

import os
import plistlib
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Optional

from app.forward_auto import schedule as S
from app.forward_auto import status as ST

LABEL = "com.krx-hyungsoo.poc6-13.forward-auto"
NOT_FOUND = 113  # `launchctl print` '서비스 없음'(맥북 실측 · 잘못된 도메인 = 112)


def plist_path(home: Optional[Path] = None) -> Path:
    return Path(home or Path.home()) / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def render(python: str, repo: Path) -> bytes:
    repo = Path(repo).resolve()
    log = str(repo / ST.OPS_REL / "launchd.log")
    body = {
        "Label": LABEL,
        "ProgramArguments": [
            str(python),
            str(repo / "scripts" / "run_forward_auto.py"),
            "tick",
        ],
        "WorkingDirectory": str(repo),
        "StartCalendarInterval": [
            {"Hour": t.hour, "Minute": t.minute} for t in S.SLOTS
        ],
        "RunAtLoad": True,
        "EnvironmentVariables": {
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "PYTHONIOENCODING": "utf-8",
        },
        "StandardOutPath": log,
        "StandardErrorPath": log,
    }
    return plistlib.dumps(body, sort_keys=True)


def _domain() -> str:
    return f"gui/{os.getuid()}"


def check(
    python: str,
    repo: Path,
    *,
    home: Optional[Path] = None,
    runner: Callable = subprocess.run,
) -> dict[str, Any]:
    """읽기만: 자기 plist 가 있는가 · 지금 만들 내용과 같은가 · launchd 에 올라 있는가(확인 불가 = None)."""
    p = plist_path(home)
    want = render(python, repo)
    exists = p.is_file()
    loaded, out = _probe(runner)
    m = re.search(r"last exit code = (-?\d+)", out.decode("utf-8", "replace"))
    last_exit = int(m.group(1)) if m else None
    return {
        "label": LABEL,
        "path": str(p),
        "plist": exists,
        "same": exists and p.read_bytes() == want,
        "loaded": loaded,
        "last_exit": last_exit,  # 0 이 아니면 launchd 가 작업을 띄우지 못했거나 실패한 것(예: 78 = 설정)
        "log_dir": (Path(repo).resolve() / ST.OPS_REL).is_dir(),
    }


def install(
    python: str,
    repo: Path,
    *,
    apply: bool,
    home: Optional[Path] = None,
    runner: Callable = subprocess.run,
) -> dict[str, Any]:
    p = plist_path(home)
    body = render(python, repo)
    st = check(python, repo, home=home, runner=runner)
    plan = {
        "path": str(p),
        "creates_dir": not p.parent.is_dir(),
        "creates_log_dir": not (Path(repo).resolve() / ST.OPS_REL).is_dir(),
        "note": "RunAtLoad — 설치 순간 tick 1회(10:00 ~ 15:20 이면 06 호출 · 업로드가 바로 시작됨)",
        "plist": body.decode("utf-8"),
        "current": st,
    }
    if not Path(python).is_file():
        return {"status": "REFUSED", "reason": f"파이썬 없음: {python}", **plan}
    if st["plist"] and not st["same"]:
        return {
            "status": "REFUSED",
            "reason": "자기 plist 가 다른 내용으로 이미 있음 — uninstall 뒤 다시",
            **plan,
        }
    if not apply:
        return {"status": "DRY_RUN", **plan}
    # launchd 는 로그 폴더를 만들지 않는다 — 없으면 작업을 띄우지 못한다(설치 전에 만든다)
    (Path(repo).resolve() / ST.OPS_REL).mkdir(parents=True, exist_ok=True)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not st["plist"]:
        with open(p, "xb") as fh:
            fh.write(body)
    rc = 0
    if not st["loaded"]:
        r = runner(
            ["launchctl", "bootstrap", _domain(), str(p)],
            capture_output=True,
            timeout=30,
            check=False,
        )
        rc = r.returncode
    after = check(python, repo, home=home, runner=runner)
    return {
        "status": "OK" if rc == 0 and after["loaded"] else "FAILED",
        "rc": rc,
        **plan,
        "after": after,
    }


def uninstall(
    *, apply: bool, home: Optional[Path] = None, runner: Callable = subprocess.run
) -> dict[str, Any]:
    p = plist_path(home)
    plan = {
        "path": str(p),
        "plist": p.is_file(),
        "removes": [str(p)] if p.is_file() else [],
    }
    if not apply:
        return {"status": "DRY_RUN", **plan}
    try:
        r = runner(
            ["launchctl", "bootout", f"{_domain()}/{LABEL}"],
            capture_output=True,
            timeout=30,
            check=False,
        )
        rc: Optional[int] = r.returncode
    except (OSError, subprocess.SubprocessError):
        rc = None
    still = _probe(runner)[0]
    if (
        still is not False
    ):  # 아직 올라 있음 · 확인 불가 = 해제 실패(plist 를 지우지 않음 · 검증자 r1 F4)
        return {
            "status": "FAILED",
            "reason": "bootout 뒤에도 작업이 올라 있거나 확인 불가 — plist 남김",
            "bootout_rc": rc,
            "loaded_after": still,
            **plan,
        }
    if p.is_file():
        p.unlink()
    return {"status": "OK", "bootout_rc": rc, "loaded_after": False, **plan}


def _probe(runner: Callable) -> tuple[Optional[bool], bytes]:
    """`launchctl print` — 0 = 올라 있음 · '서비스 없음'(113) = 없음 · 그 밖 종료 코드 · 실행 예외 = 확인 불가
    (None). 조회 오류를 '없음'으로 대체하지 않는다(검증자 r2 F4). 출력은 올라 있을 때만 돌려준다."""
    try:
        r = runner(
            ["launchctl", "print", f"{_domain()}/{LABEL}"],
            capture_output=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None, b""
    if r.returncode == 0:
        return True, r.stdout or b""
    return (False if r.returncode == NOT_FOUND else None), b""
