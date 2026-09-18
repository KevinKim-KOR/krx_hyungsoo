"""POC3-02C-OPS-01 — `INTRADAY_ALERT_CONFIG` PC→OCI 전달 (8단계 사슬).

설계자 §5 순서 그대로다. 기존 `sync_three_push_runtime_param.py` 의 4단계를
재사용하고 **5~7 을 신규로 채운다** — 조사에서 확인된 공백이다.

```text
1 PC 승인 DB              approved 확인
2 전송 JSON export        state/three_push/params/latest_intraday_alert_config.json
3 SCP → atomic rename     tmp 업로드 후 mv
4 OCI verify              schema + source_hash 대조
5 OCI DB version 적재     ← 신규
6 승인 확인                ← 신규
7 active pointer 갱신     ← 신규
8 version/hash 재독출 대조
```

5~7 은 `apply_intraday_config_oci.py` 를 **일시 업로드해 원격 실행**한다. 기존
verify 스크립트가 쓰는 방식 그대로이며 **상시 배포 스크립트를 늘리지 않는다.**

## 하지 않는 것

- **DB 파일 복사·덮어쓰기 금지** (§10-3(4)) — JSON 만 옮기고 원격에서 적재한다.
- 실패 시 OCI active 를 건드리지 않는다. 직전 버전이 그대로 남는다.
- Telegram · Naver 호출 0건.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Optional

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.intraday_config import store  # noqa: E402

EXPORT_PATH = Path("state/three_push/params/latest_intraday_alert_config.json")
DEFAULT_REMOTE_DIR = "/home/ubuntu/krx_hyungsoo/state/three_push/params"
REMOTE_NAME = "latest_intraday_alert_config.json"
APPLY_SCRIPT = Path(__file__).resolve().parent / "apply_intraday_config_oci.py"
TARGET = "oci"


def _ssh_target() -> Optional[str]:
    return os.environ.get("OCI_SSH_TARGET") or None


def _run(cmd: list[str], timeout: float = 120.0) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except Exception as e:  # noqa: BLE001
        return 1, f"{type(e).__name__}: {e}"


_REMOTE_PY = "cd /home/ubuntu/krx_hyungsoo && venv/bin/python -c"


def _remote_active(target: str) -> tuple[bool, Optional[str], Optional[str]]:
    """OCI 의 현재 active `(읽기성공, version_id, source_hash)`.

    `version_id is None` 은 "active 가 없다" 이고, `읽기성공=False` 는 "모른다" 다.
    둘을 섞으면 안 된다 — 모르는 것을 없다고 적으면 거짓 보고가 된다.
    """
    rc, out = _run(
        [
            "ssh",
            target,
            f'{_REMOTE_PY} \'import sys;sys.path.insert(0,".");'
            "from app.intraday_config import store as s;a=s.get_active();"
            'print(a["config_version_id"], a["source_hash_sha256"]) '
            'if a else print("NONE")\'',
        ],
        timeout=60,
    )
    if rc != 0 or not out.strip():
        return False, None, None
    parts = out.strip().splitlines()[-1].split()
    if parts == ["NONE"]:
        return True, None, None
    if len(parts) != 2:
        return False, None, None
    return True, parts[0], parts[1]


# 설계자 확정(2026-09-18) — 적용 후 read-back 을 **조회만** 3회 재시도한다.
READBACK_DELAYS: tuple[float, ...] = (0.0, 2.0, 5.0)


def reconcile_after_apply(
    target: str,
    *,
    want_id: str,
    want_hash: str,
    prior_id: Optional[str],
    prior_hash: Optional[str],
    sleep: Optional[Callable[[float], None]] = None,
) -> tuple[str, list[tuple[bool, Optional[str], Optional[str]]]]:
    """적용 명령이 모호하게 끝났을 때 OCI 실제 상태를 확정한다.

    반환 `(상태, 조회이력)`. 설계자 확정 3종이다.

    ```text
    deployed              목표 version/hash 가 active 임을 확인
    remote_apply_failed   직전 version/hash 가 유지됨을 확인
    deploy_unconfirmed    3회 모두 조회 실패 또는 예상 밖 상태
    ```

    **조회만 한다.** 자동 재적용은 금지다(`AUTOMATIC_REAPPLY = FORBIDDEN`).
    """
    # **호출 시점에** 해석한다. 기본 인자로 박으면 import 때 고정돼 테스트가
    # 실제로 7초를 잔다.
    nap = sleep or time.sleep
    seen: list[tuple[bool, Optional[str], Optional[str]]] = []
    for delay in READBACK_DELAYS:
        if delay:
            nap(delay)
        ok, vid, vhash = _remote_active(target)
        seen.append((ok, vid, vhash))
        if not ok:
            continue
        if vid == want_id and vhash == want_hash:
            return "deployed", seen
        if vid == prior_id and vhash == prior_hash:
            return "remote_apply_failed", seen
        # 예상 밖 상태다. 일시적일 수 있으니 남은 회차를 마저 조회한다.
    return "deploy_unconfirmed", seen


def _parse_ok(out: str) -> Optional[tuple[str, str]]:
    """원격 apply 의 `OK <version> <hash>` 줄을 읽는다."""
    for line in reversed((out or "").strip().splitlines()):
        parts = line.strip().split()
        if len(parts) == 3 and parts[0] == "OK":
            return parts[1], parts[2]
    return None


def export_json(config_version_id: str, *, out_path: Optional[Path] = None) -> Path:
    """2단계 — 전송용 JSON. **DB 가 SSOT 이고 이것은 전송 형식**이다."""
    row = store.get_version(config_version_id)
    p = out_path or EXPORT_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "config_version_id": row["config_version_id"],
        "schema_version": row["schema_version"],
        "created_at": row["created_at"],
        "rule_version": row["rule_version"],
        "evaluation_input_hash": row["evaluation_input_hash"],
        "effective_config_hash": row["effective_config_hash"],
        "source_hash_sha256": row["source_hash_sha256"],
        "payload_json": row["payload_json"],
        "approved_at": row["approved_at"],
        "approved_by": row["approved_by"],
    }
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)
    return p


def deploy(
    config_version_id: str,
    *,
    ssh_target: Optional[str] = None,
    remote_dir: str = DEFAULT_REMOTE_DIR,
) -> tuple[bool, Optional[str]]:
    """8단계 사슬. 반환 `(성공, 실패사유)`. **예외를 올리지 않는다.**"""

    def fail(reason: str, err: Optional[str] = None) -> tuple[bool, str]:
        store.record_sync(
            config_version_id, target=TARGET, status=reason, error=(err or "")[:400]
        )
        return False, reason

    # 1. 승인 확인 — 미승인이면 전달 자체를 하지 않는다.
    try:
        row = store.get_version(config_version_id)
    except store.ConfigNotFound:
        return fail("version_not_found")
    if not row.get("approved_at") or not row.get("approved_by"):
        return fail("not_approved")

    target = ssh_target or _ssh_target()
    if not target:
        return fail("missing_ssh_target", "OCI_SSH_TARGET 미설정")

    rc, out = _run(["ssh", "-o", "BatchMode=yes", target, "echo OK"], timeout=30)
    if rc != 0:
        return fail("ssh_unreachable", out)

    # 2. **precheck — 원격에 아무것도 쓰기 전에** 직전 active 를 붙든다.
    #
    # 예전에는 이 조회가 scp·mv·스크립트 업로드 **뒤**에 있었다. 그래서
    # `precheck_failed` 를 반환하면서도 원격 정본 JSON 은 이미 교체돼 있었고
    # 임시 적용 스크립트도 남았다 — "OCI 를 건드리지 않았다" 가 거짓이었다
    # (검증자 지적, 실측으로 원격 파일 2개 확인).
    #
    # 읽지 못하면 되돌릴 기준이 없으므로 **아무것도 하지 않고** 중단한다.
    prior_read_ok, prior_active, prior_hash = _remote_active(target)
    if not prior_read_ok:
        return fail(
            "precheck_failed",
            "OCI 상태를 읽지 못해 중단했다. 원격에 아무것도 쓰지 않았다. "
            "OCI 에 이 기능 코드가 아직 배포되지 않았거나 접속이 안 되는 경우다",
        )

    # 3. export (로컬)
    try:
        local = export_json(config_version_id)
    except Exception as e:  # noqa: BLE001
        return fail("export_failed", f"{type(e).__name__}: {e}")

    # 4. scp → atomic rename — **여기부터 원격에 쓴다.**
    remote_tmp = f"{remote_dir}/.{REMOTE_NAME}.tmp"
    remote_final = f"{remote_dir}/{REMOTE_NAME}"
    remote_apply = f"{remote_dir}/.apply_intraday_config_oci.py"

    def cleanup() -> None:
        """임시 파일을 지운다. **rc 를 보지 않는다** — 정리일 뿐이다."""
        _run(["ssh", target, f"rm -f {remote_tmp} {remote_apply}"], timeout=30)

    def fail_after_upload(reason: str, err: Optional[str] = None):
        """업로드 뒤 실패 — 임시 파일을 남기지 않는다."""
        cleanup()
        return fail(reason, err)

    rc, out = _run(["scp", str(local), f"{target}:{remote_tmp}"], timeout=120)
    if rc != 0:
        return fail_after_upload("scp_failed", out)
    rc, out = _run(["ssh", target, f"mv {remote_tmp} {remote_final}"], timeout=30)
    if rc != 0:
        return fail_after_upload("rename_failed", out)

    # 5~8. verify + DB 적재 + 승인 확인 + pointer 갱신 (원격 1회 실행)
    if not APPLY_SCRIPT.exists():
        return fail_after_upload("apply_script_missing", str(APPLY_SCRIPT))
    rc, out = _run(["scp", str(APPLY_SCRIPT), f"{target}:{remote_apply}"], timeout=60)
    if rc != 0:
        return fail_after_upload("apply_upload_failed", out)

    # `rm` 을 **같은 명령에 붙이지 않는다.** 붙이면 rc 가 정리 명령에서 나와,
    # 적용이 성공했는데도 `remote_apply_failed` 로 보고된다(검증자 r2 P1).
    rc, out = _run(
        [
            "ssh",
            target,
            f"cd /home/ubuntu/krx_hyungsoo && venv/bin/python {remote_apply} "
            f"--json {remote_final}",
        ],
        timeout=180,
    )
    cleanup()  # 적용 성공·실패와 무관하게 임시 파일을 남기지 않는다

    if rc != 0 and _parse_ok(out) is None:
        # 적용이 됐는지 모른다. **모르는 채로 단정하지 않는다** — OCI 를 조회해
        # 확정한다(설계자 확정 2026-09-18). 조회만 하고 재적용하지 않는다.
        verdict, seen = reconcile_after_apply(
            target,
            want_id=config_version_id,
            want_hash=row["source_hash_sha256"],
            prior_id=prior_active,
            prior_hash=prior_hash,
        )
        if verdict == "deployed":
            # 통신만 끊겼고 적용은 됐다. **되돌리지 않는다** — 되돌리면 멀쩡히
            # 적용된 설정을 우리 쪽 통신 사고로 날리는 셈이다.
            return _record_deployed(config_version_id, row["source_hash_sha256"])
        return fail(verdict, f"조회 {len(seen)}회={seen} rc={rc} {out}"[:400])

    # 8. 재독출 대조는 **원격 안에서** 끝났다. 예전에는 여기서 별도 ssh 로
    # 다시 읽었고, 그 왕복만 실패해도 `deploy` 는 실패를 반환하면서 OCI active
    # 는 이미 새 버전인 상태로 남았다. 지금은 원격이 불일치를 발견하면 직전
    # active 로 되돌린 뒤 실패를 반환한다.
    got = _parse_ok(out)
    if got is None:
        return fail("remote_apply_unparsed", out.strip()[:300])
    if got[0] != config_version_id or got[1] != row["source_hash_sha256"]:
        return fail("readback_mismatch", out.strip()[:300])

    return _record_deployed(config_version_id, got[1])


def _record_deployed(
    config_version_id: str, remote_hash: str
) -> tuple[bool, Optional[str]]:
    """전달 성공 확정. 정상 경로와 **재조회 확정 경로**가 같은 일을 한다."""
    store.record_sync(
        config_version_id,
        target=TARGET,
        status="deployed",
        verify_status="ok",
        remote_hash=remote_hash,
    )
    # PC active 도 여기서 갱신한다. 안 하면 전달에 성공한 버전이 계속
    # `approved_not_deployed` 로 잡혀 재시도 버튼이 사라지지 않는다.
    # OCI 가 먼저 성공한 뒤이므로 PC 가 앞서가는 일은 없다.
    try:
        store.activate(config_version_id, activated_by="pc_deploy")
    except Exception as e:  # noqa: BLE001
        # OCI 는 이미 성공했다. 여기서 실패를 반환하면 사용자가 재시도해 OCI 를
        # 한 번 더 건드린다 — 그게 더 나쁘다. 사실만 기록한다.
        store.record_sync(
            config_version_id,
            target="pc",
            status="pc_activate_failed",
            error=f"{type(e).__name__}: {e}"[:400],
        )
    return True, None


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config-version-id", required=True)
    ap.add_argument("--ssh-target", default=None)
    ap.add_argument("--remote-dir", default=DEFAULT_REMOTE_DIR)
    a = ap.parse_args(argv)
    ok, err = deploy(
        a.config_version_id, ssh_target=a.ssh_target, remote_dir=a.remote_dir
    )
    print("deployed" if ok else f"failed: {err}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
