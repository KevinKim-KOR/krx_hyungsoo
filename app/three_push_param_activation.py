"""POC5-27 — 「OCI 운영·적용」 [현재 기준 OCI 적용] 의 OCI 발행 순서(PC 쪽).

PC 에서 확정 · 사용자가 승인한 PARAM 값을 OCI 로컬 도구(`scripts/apply_three_push_param_oci.py`)가
그대로 발행한다. PC 는 OCI DB 를 직접 열지 않는다 — 읽기는 기존 `mode=ro` 블록, 쓰기는 OCI 쪽
도구만 한다(PLAN 판정 §1). 러너의 정본은 OCI DB 활성값 하나다 · JSON 은 전달 자료다.

```text
1 적용 전 읽기       OCI 활성값. 못 읽으면 OCI 에 쓰지 않고 failed(기존 값 그대로).
2 같으면 끝          OCI 쓰기 0 · 새 버전 0 · active_same.
3 전달              기존 sync(JSON 확인 뒤 교체). 실패 = 전환 전 failed.
4 도구 업로드 · 실행  OCI 프로세스 안에서 내용 대조(PC 가 보낸 파일 SHA-256) · 검증 · 기록 · 전환 ·
                    다시 읽기 · 불일치면 되돌림 확인. 앞 실행이 아직 돌면 도구는 손대지 않는다(busy).
5 정리 · 애매하면     임시 도구를 지우고, 결과를 모르면 읽기만 0 · 2 · 5초(남은 예산 안).
                    요청값이 실제로 읽힐 때만 activated — 아니면 unconfirmed(기존 값 유지로
                    단정하지 않는다 · 자동으로 다시 쓰거나 되돌리지 않는다 · 판정 §5).
```

전체 예산 105초(화면 120초 안 · 판정 §5). 응답 · 화면에 버전 ID · 원격 경로 · SSH 대상을 싣지
않는다(이 모듈은 결과 종류와 실제로 읽은 값만 돌려준다).
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from app.oci_status_rows import _compare_values, param_values_block, parse_param_values

logger = logging.getLogger(__name__)

REMOTE_ROOT = "/home/ubuntu/krx_hyungsoo"  # OCI 배포 규약(저장소 스크립트에 이미 공개)
DEFAULT_REMOTE_PARAM_DIR = f"{REMOTE_ROOT}/state/three_push/params"
TOOL_LOCAL = (
    Path(__file__).resolve().parent.parent / "scripts" / "apply_three_push_param_oci.py"
)
TOOL_REMOTE_NAME = ".apply_three_push_param_oci.py"

TOTAL_BUDGET_S = 105.0
READ_TIMEOUT_S = 12.0
DELIVER_TIMEOUT_S = 40.0
UPLOAD_TIMEOUT_S = 10.0
APPLY_TIMEOUT_S = 20.0
CLEANUP_TIMEOUT_S = 6.0
RECONCILE_DELAYS: tuple[float, ...] = (0.0, 2.0, 5.0)

ACTIVE_SAME = "active_same"
ACTIVATED = "activated"
FAILED = "failed"
UNCONFIRMED = "unconfirmed"


@dataclass
class Outcome:
    """적용 결과. `values` = 실제로 읽은 OCI 활성값(읽지 않았으면 None) · `read_at` = 그 시각."""

    result: str
    stage: str
    values: Optional[dict[str, tuple]] = None
    read_at: Optional[str] = None
    n: Optional[int] = None
    diff: Optional[int] = None
    note: str = ""  # 내부 로그용(응답에 싣지 않는다)


@dataclass
class Remote:
    """원격 호출 묶음 — 시험에서 바꿔 끼운다."""

    ssh: Callable[[str, float], tuple[int, str]]
    scp: Callable[[Path, str, float], int]
    deliver: Callable[[float], bool]
    remote_dir: str = DEFAULT_REMOTE_PARAM_DIR
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def pc_values(pc_dict: dict[str, Any]) -> dict[str, tuple]:
    """PC 운영 기준 dict → ① 비교와 같은 꼴(`{키: (형, 수, 글, 참거짓)}`)."""
    from app.runtime_param_store import _split_value_columns, flatten_param_dict

    return {
        key: (vtype, *_split_value_columns(vtype, value))
        for key, vtype, value in flatten_param_dict(pc_dict)
    }


def _read_active(remote: Remote, timeout: float) -> Optional[dict[str, tuple]]:
    rc, out = remote.ssh(param_values_block(REMOTE_ROOT), max(1.0, timeout))
    if rc != 0:
        return None
    return parse_param_values(out)


def _parse_result(out: str) -> Optional[dict[str, Any]]:
    """도구 출력의 마지막 `RESULT {json}` 줄. 없거나 못 읽으면 None."""
    for line in reversed((out or "").splitlines()):
        if line.startswith("RESULT "):
            try:
                data = json.loads(line[len("RESULT ") :])  # noqa: E203
            except ValueError:
                return None
            return data if isinstance(data, dict) else None
    return None


def _rows_to_values(rows: Any) -> Optional[dict[str, tuple]]:
    if not rows:
        return None
    return parse_param_values(json.dumps({"rows": rows}))


def _tool_command(
    remote: Remote, tool_remote: str, expect_sha256: Optional[str]
) -> str:
    """OCI 도구 실행 명령. 경로는 모두 따옴표로 감싼다(환경 변수 경로의 공백 · 특수 문자)."""
    q = shlex.quote
    cmd = (
        f"cd {q(REMOTE_ROOT)} && venv/bin/python {q(tool_remote)} "
        f"--json {q(remote.remote_dir + '/latest_runtime_param.json')} "
        f"--project-root {q(REMOTE_ROOT)}"
    )
    if expect_sha256:
        cmd += f" --expect-sha256 {q(expect_sha256)}"
    return cmd


def _cleanup(remote: Remote, tool_remote: str) -> None:
    rc, _ = remote.ssh(f"rm -f {shlex.quote(tool_remote)}", CLEANUP_TIMEOUT_S)
    if rc != 0:
        logger.warning("PARAM 적용 도구 정리 실패(결과에는 영향 없음): rc=%s", rc)


def _reconcile(
    wanted: dict[str, tuple], remote: Remote, left: Callable[[], float]
) -> Outcome:
    """결과를 모를 때 읽기만 다시(0 · 2 · 5초 · 남은 예산 안). 요청값이 읽힐 때만 activated."""
    for delay in RECONCILE_DELAYS:
        if left() < delay + 2.0:
            break
        if delay:
            remote.sleep(delay)
        values = _read_active(remote, min(8.0, left()))
        if values is None:
            continue
        n, d = _compare_values(wanted, values)
        if d == 0:
            return Outcome(ACTIVATED, "reconcile", values, _now_iso(), n, 0)
    return Outcome(UNCONFIRMED, "reconcile", note="not_confirmed")


def activate(
    pc_dict: dict[str, Any], remote: Remote, *, expect_sha256: Optional[str] = None
) -> Outcome:
    """PC 운영 기준을 OCI DB 에 발행한다(설명은 모듈 머리 · 실패해도 예외를 올리지 않는다).

    `expect_sha256` = PC 가 보낸 JSON 바이트의 SHA-256(API 는 늘 준다). OCI 도구가 전달된 파일과
    대조해 다르면 쓰기 전에 실패한다 — 그 사이 다른 쓰기 · 다른 경로의 값을 대신 발행하지 않는다.
    """
    t0 = remote.clock()

    def left() -> float:
        return TOTAL_BUDGET_S - (remote.clock() - t0)

    tool_started = False  # DB 를 바꿀 수 있는 것은 OCI 도구 실행뿐 — 그 뒤의 뜻밖 오류는 '확인 불가'
    try:
        wanted = pc_values(pc_dict)
        before = _read_active(remote, min(READ_TIMEOUT_S, left()))
        if before is None:
            return Outcome(FAILED, "precheck", note="read_failed")
        read_at = _now_iso()
        n, d = _compare_values(wanted, before)
        if d == 0:
            return Outcome(ACTIVE_SAME, "precheck", before, read_at, n, 0)
        if left() < DELIVER_TIMEOUT_S + UPLOAD_TIMEOUT_S + APPLY_TIMEOUT_S:
            return Outcome(FAILED, "budget", before, read_at, n, d)
        if not remote.deliver(DELIVER_TIMEOUT_S):
            return Outcome(FAILED, "deliver", before, read_at, n, d)
        tool_remote = f"{remote.remote_dir}/{TOOL_REMOTE_NAME}"
        if left() < UPLOAD_TIMEOUT_S + APPLY_TIMEOUT_S:
            return Outcome(FAILED, "budget", before, read_at, n, d)
        if remote.scp(TOOL_LOCAL, tool_remote, UPLOAD_TIMEOUT_S) != 0:
            _cleanup(remote, tool_remote)
            return Outcome(FAILED, "upload", before, read_at, n, d)
        tool_started = True
        rc, out = remote.ssh(
            _tool_command(remote, tool_remote, expect_sha256),
            min(APPLY_TIMEOUT_S, left()),
        )
        _cleanup(remote, tool_remote)
        parsed = _parse_result(out)
        result = parsed.get("result") if parsed else None
        values = _rows_to_values(parsed.get("rows")) if parsed else None
        if result in ("SAME", "ACTIVATED") and values is not None:
            n2, d2 = _compare_values(wanted, values)
            if d2 == 0:
                kind = ACTIVE_SAME if result == "SAME" else ACTIVATED
                return Outcome(kind, "apply", values, _now_iso(), n2, 0)
        if result == "FAILED" and parsed and parsed.get("previous_kept"):
            stage = f"apply:{parsed.get('stage')}"
            if values is not None:
                n2, d2 = _compare_values(wanted, values)
                return Outcome(FAILED, stage, values, _now_iso(), n2, d2)
            return Outcome(FAILED, stage, before, read_at, n, d)
        logger.warning(
            "PARAM 적용 결과를 바로 확인하지 못함(rc=%s · result=%s) — 읽기만 다시",
            rc,
            result,
        )
        return _reconcile(wanted, remote, left)
    except Exception as e:  # noqa: BLE001 - 예외를 화면 오류로 올리지 않는다
        logger.error("PARAM 적용 중 뜻밖 오류: %s", type(e).__name__)
        if tool_started:
            return Outcome(UNCONFIRMED, "error", note=type(e).__name__)
        return Outcome(FAILED, "error", note=type(e).__name__)


def _ssh_opts() -> list[str]:
    from app.oci_startup_status import _ssh_key_opts

    return ["-o", "BatchMode=yes", "-o", "ConnectTimeout=8", *_ssh_key_opts()]


def default_remote(deliver: Callable[[float], bool]) -> Remote:
    """실제 OCI 연결(`OCI_SSH_TARGET`). 없으면 예외 — 호출자가 OCI 에 쓰기 전 실패로 처리한다."""
    from app.config import require_env

    target = require_env("OCI_SSH_TARGET")

    def ssh(cmd: str, timeout: float) -> tuple[int, str]:
        try:
            r = subprocess.run(
                ["ssh", *_ssh_opts(), target, cmd],
                capture_output=True,
                text=True,
                timeout=max(1.0, timeout),
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError):
            return 255, ""
        return r.returncode, r.stdout

    def scp(local: Path, remote_path: str, timeout: float) -> int:
        try:
            r = subprocess.run(
                ["scp", *_ssh_opts(), str(local), f"{target}:{remote_path}"],
                capture_output=True,
                text=True,
                timeout=max(1.0, timeout),
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError):
            return 255
        return r.returncode

    return Remote(
        ssh=ssh,
        scp=scp,
        deliver=deliver,
        remote_dir=os.environ.get(
            "THREE_PUSH_REMOTE_PARAM_DIR", DEFAULT_REMOTE_PARAM_DIR
        ),
    )
