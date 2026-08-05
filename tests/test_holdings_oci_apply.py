"""POC3-07 Holdings OCI 적용 로직 단위 테스트.

실제 OCI 로 write 하지 않는다 — subprocess(_run)·환경변수·로컬 파일 존재를 monkeypatch
로 통제해 분기별 계약만 검증한다(설계자 Q11: 개발자는 dry-run·계약 검증만).

검증 계약:
  - 로컬 Holdings 파일 없음 → PC_SAVED (전송 시도 안 함).
  - OCI_SSH_TARGET 미설정 → UNKNOWN.
  - scp 실패 → APPLY_FAILED, 기존 active 보존(mv 호출 안 함).
  - 전송 tmp hash 불일치 → APPLY_FAILED, active rename 안 함, tmp 정리.
  - 정상: scp OK → tmp hash == local → mv OK → active hash == local → OCI_APPLIED.
  - 정상 흐름은 tmp 로만 전송 후 atomic rename(중간 파일을 바로 active 로 안 씀).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import app.holdings_oci_apply as mod


_CONTENT = b'{"holdings": [{"ticker": "069500"}]}'
_SHA = hashlib.sha256(_CONTENT).hexdigest()


def _write_local(tmp_path: Path, monkeypatch) -> Path:
    f = tmp_path / "holdings_latest.json"
    f.write_bytes(_CONTENT)
    monkeypatch.setattr(mod, "_LOCAL_HOLDINGS", f)
    return f


def test_missing_local_file_returns_pc_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_LOCAL_HOLDINGS", tmp_path / "nope.json")
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_PC_SAVED
    assert result.oci_verified is False
    assert result.applied_at is None


def test_missing_ssh_target_returns_unknown(tmp_path, monkeypatch):
    _write_local(tmp_path, monkeypatch)

    def _raise(_key):
        raise RuntimeError("OCI_SSH_TARGET 미설정")

    monkeypatch.setattr(mod, "require_env", _raise)
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_UNKNOWN
    assert result.oci_verified is False


def test_scp_failure_preserves_active(tmp_path, monkeypatch):
    _write_local(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "require_env", lambda _k: "oci-krx")

    calls: list[list[str]] = []

    def _fake_run(cmd, timeout):
        calls.append(cmd)
        # scp 실패.
        if cmd[0] == "scp":
            return 1, "", "scp error"
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", _fake_run)
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_APPLY_FAILED
    assert result.oci_verified is False
    # active 를 바꾸는 mv 가 호출되지 않았다.
    assert not any("mv " in " ".join(c) for c in calls)


def test_tmp_hash_mismatch_no_rename(tmp_path, monkeypatch):
    _write_local(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "require_env", lambda _k: "oci-krx")

    calls: list[list[str]] = []

    def _fake_run(cmd, timeout):
        calls.append(cmd)
        joined = " ".join(cmd)
        if cmd[0] == "scp":
            return 0, "", ""
        if "sha256sum" in joined:
            # tmp hash 가 로컬과 다르게 나온다(전송 손상).
            return 0, "deadbeef", ""
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", _fake_run)
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_APPLY_FAILED
    # active rename(mv) 호출 안 함. tmp 정리(rm) 는 호출됨.
    assert not any("mv " in " ".join(c) for c in calls)
    assert any("rm -f" in " ".join(c) for c in calls)


def test_success_applies_and_verifies(tmp_path, monkeypatch):
    _write_local(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "require_env", lambda _k: "oci-krx")

    seq: list[str] = []

    def _fake_run(cmd, timeout):
        joined = " ".join(cmd)
        if cmd[0] == "scp":
            seq.append("scp")
            return 0, "", ""
        if "sha256sum" in joined:
            seq.append("sha256sum")
            # tmp 와 active 모두 로컬 hash 와 동일.
            return 0, _SHA, ""
        if "mv " in joined:
            seq.append("mv")
            return 0, "", ""
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", _fake_run)
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_OCI_APPLIED
    assert result.oci_verified is True
    assert result.content_sha256 == _SHA
    assert result.applied_at is not None
    # 순서: scp → (tmp)sha256sum → mv → (active)sha256sum.
    assert seq == ["scp", "sha256sum", "mv", "sha256sum"]


def test_active_hash_mismatch_after_apply_out_of_sync(tmp_path, monkeypatch):
    _write_local(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "require_env", lambda _k: "oci-krx")

    state = {"sha_calls": 0}

    def _fake_run(cmd, timeout):
        joined = " ".join(cmd)
        if cmd[0] == "scp":
            return 0, "", ""
        if "sha256sum" in joined:
            state["sha_calls"] += 1
            # 첫 호출(tmp) 은 일치, 둘째(active) 는 불일치.
            if state["sha_calls"] == 1:
                return 0, _SHA, ""
            return 0, "different", ""
        if "mv " in joined:
            return 0, "", ""
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", _fake_run)
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_OUT_OF_SYNC
    assert result.oci_verified is False
