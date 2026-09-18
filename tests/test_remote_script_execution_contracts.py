"""원격 업로드 실행 계약 — 실제 운영에서 터진 2건 (2026-09-18).

두 결함 모두 **함수 단위 테스트로는 잡히지 않았다.**

```text
A  apply_intraday_config_oci.py 가 루트를 자기 위치(parents[1])에서 계산
   → state/three_push/params/ 로 업로드되면 3단계 깊어 app 을 못 찾는다
   기존 테스트는 PC 안에서 apply_file() 을 직접 불러 app 이 이미 import 된
   상태였다 — sys.path 로직을 한 번도 태우지 않았다.

B  verify_three_push_param_oci.py 의 ALLOWED_PUSH_KINDS 가 정본과 어긋남
   → holdings_risk_alert 가 빠져 「현재 운영 기준 OCI 적용」이 매번 거부
   standalone 이라 목록이 복제돼 있는데 복제본을 갱신하지 않았다.
```

여기서는 **스크립트를 실제 위치에서 subprocess 로 실행**하고, 복제된 계약이
정본과 같은지 본다.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APPLY = ROOT / "scripts/apply_intraday_config_oci.py"
VERIFY = ROOT / "scripts/verify_three_push_param_oci.py"


# ── A. 업로드 위치에서 실행 ─────────────────────────────────────────────────


def test_apply_script_runs_from_a_deep_upload_path(tmp_path):
    """**운영 재현.** 원격과 같은 깊이로 옮겨 실행해도 `app` 을 찾아야 한다.

    `--project-root` 없이는 `ModuleNotFoundError: No module named 'app'` 이었다.
    """
    deep = tmp_path / "state" / "three_push" / "params"
    deep.mkdir(parents=True)
    shutil.copy(APPLY, deep / ".apply_intraday_config_oci.py")

    r = subprocess.run(
        [
            sys.executable,
            str(deep / ".apply_intraday_config_oci.py"),
            "--json",
            str(tmp_path / "없는파일.json"),
            "--project-root",
            str(ROOT),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    # 파일이 없으니 실패하는 게 맞다. **import 단계는 통과해야 한다.**
    assert "ModuleNotFoundError" not in r.stderr, r.stderr
    assert "No module named 'app'" not in r.stderr, r.stderr
    assert "missing_file" in r.stdout, (r.stdout, r.stderr)


def test_apply_script_requires_project_root(tmp_path):
    """루트를 추측하지 않는다 — 안 주면 실행을 거부한다."""
    r = subprocess.run(
        [sys.executable, str(APPLY), "--json", str(tmp_path / "x.json")],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode != 0
    assert "--project-root" in r.stderr


def test_sync_passes_project_root_to_remote():
    """호출부가 실제로 넘기는지 소스로 고정한다."""
    src = (ROOT / "scripts/sync_intraday_config.py").read_text(encoding="utf-8")
    assert "--project-root {REMOTE_PROJECT_ROOT}" in src
    # 루트를 하드코딩 문자열로 흩뿌리지 않는다.
    assert src.count('"/home/ubuntu/krx_hyungsoo"') == 1


def test_apply_script_does_not_derive_root_from_its_own_location():
    """`parents[N]` 로 루트를 잡으면 업로드 위치가 바뀔 때마다 깨진다."""
    src = APPLY.read_text(encoding="utf-8")
    # 주석에는 나와도 된다(왜 쓰면 안 되는지 설명). **코드 라인**만 본다.
    code = [
        ln for ln in src.splitlines() if ln.strip() and not ln.strip().startswith("#")
    ]
    offending = [ln for ln in code if "parents[" in ln]
    assert not offending, offending
    assert "_bootstrap(" in src


# ── B. 복제된 계약이 정본과 같은가 ──────────────────────────────────────────


def test_verify_script_allowed_kinds_match_canonical():
    """**복제된 목록이 정본과 어긋나면 OCI 적용이 통째로 막힌다.**

    `verify_three_push_param_oci.py` 는 OCI `/tmp` 에서 standalone 실행이라
    `app` 을 import 하지 않는다. 복제는 불가피하지만 **어긋남은 막는다.**
    """
    from app.three_push_runner_common import VALID_PUSH_KINDS
    from scripts.verify_three_push_param_oci import ALLOWED_PUSH_KINDS

    assert set(ALLOWED_PUSH_KINDS) == set(VALID_PUSH_KINDS), (
        f"verify 복제본={sorted(ALLOWED_PUSH_KINDS)} "
        f"정본={sorted(VALID_PUSH_KINDS)}"
    )


def test_verify_script_accepts_holdings_risk_alert(tmp_path):
    """운영에서 실제로 거부됐던 값을 통과시키는지 실행으로 확인한다."""
    payload = {
        "schema_version": "three_push_runtime_param.v1",
        "param_id": "param-test",
        "created_at": "2026-09-18T00:00:00Z",
        "approved_at": "2026-09-18T00:00:00Z",
        "param_source": "manual_seed",
        "enabled_push_kinds": ["holdings_risk_alert"],
        "safety_policy": {},
    }
    p = tmp_path / "param.json"
    p.write_text(json.dumps(payload), encoding="utf-8")

    r = subprocess.run(
        [sys.executable, str(VERIFY), "--path", str(p)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert "enabled_push_kinds 허용값 위반" not in (r.stdout + r.stderr), r.stdout


@pytest.mark.parametrize("bad", ["not_a_kind", "market_briefingX"])
def test_verify_script_still_rejects_unknown_kinds(tmp_path, bad):
    """느슨해지지 않았는지 — 모르는 종류는 여전히 막는다."""
    from scripts.verify_three_push_param_oci import ALLOWED_PUSH_KINDS

    assert bad not in ALLOWED_PUSH_KINDS
