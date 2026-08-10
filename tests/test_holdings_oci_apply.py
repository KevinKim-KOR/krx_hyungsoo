"""POC3-07 Holdings OCI 적용 로직 단위 테스트.

manifest 계약 확정(2026-08-06): OCI active 정본은 payload 파일 1개. 별도 manifest
정본 파일을 만들지 않는다. applied_hash 는 적용 후 active payload 재독출로 재계산.
→ 2파일 정합 문제 자체가 없다.

실제 OCI 로 write 하지 않는다 — subprocess(_run)·환경변수·로컬 파일을 monkeypatch
로 통제해 분기별 계약만 검증한다(설계자 Q11: 개발자는 dry-run·계약 검증만).

검증 계약(active 교체는 payload 단일 atomic mv 하나뿐):
  - 로컬 파일 없음 → PC_SAVED (전송 시도 안 함).
  - 로컬 schema 손상 → APPLY_FAILED, SSH 미호출.
  - OCI_SSH_TARGET 미설정 → UNKNOWN.
  - payload scp 실패 → APPLY_FAILED, mv 미호출(보존).
  - payload-tmp hash 불일치 → APPLY_FAILED, mv 미호출.
  - payload-tmp schema 불일치 → APPLY_FAILED, mv 미호출.
  - mv(단일 원자 교체) 실패 → APPLY_FAILED, active 미변경(보존).
  - 정상: scp → sha256sum(tmp) → schema → mv → sha256sum(active) → OCI_APPLIED.
  - 적용 후 active hash 불일치 → OUT_OF_SYNC. 재확인 실패 → UNKNOWN.
  - manifest 관련 명령(별도 정본 파일 write)이 전혀 발생하지 않는다.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import app.holdings_oci_apply as mod


@pytest.fixture(autouse=True)
def _isolate_apply_status(tmp_path, monkeypatch):
    """apply_holdings_to_oci() 는 적용 후 _LOCAL_APPLY_STATUS 파일을 write 한다.

    POC3-08 (C): 기본값은 live 경로(state/holdings/holdings_apply_status_latest.json)라
    이 테스트가 실행되면 사용자 화면에 UNKNOWN 껍데기 파일이 생겼다(handoff §2 C 지적).
    모든 테스트에서 tmp 로 격리해 live state 오염을 원천 차단한다.
    """
    monkeypatch.setattr(
        mod,
        "_LOCAL_APPLY_STATUS",
        tmp_path / "holdings_apply_status_latest.json",
    )


_VALID = {"holdings": [{"ticker": "069500", "quantity": 1.0, "avg_buy_price": 100.0}]}
_CONTENT = json.dumps(_VALID, ensure_ascii=False).encode("utf-8")
_SHA = hashlib.sha256(_CONTENT).hexdigest()


def _write_local(tmp_path: Path, monkeypatch, content: bytes = _CONTENT) -> Path:
    f = tmp_path / "holdings_latest.json"
    f.write_bytes(content)
    monkeypatch.setattr(mod, "_LOCAL_HOLDINGS", f)
    return f


def _is_active_mv(cmd: list[str]) -> bool:
    """payload-tmp → active 교체(mv). active 를 바꾸는 유일한 원자 연산."""
    return f"mv {mod._REMOTE_TMP} {mod._REMOTE_FINAL}" in " ".join(cmd)


def test_missing_local_file_returns_pc_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_LOCAL_HOLDINGS", tmp_path / "nope.json")
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_PC_SAVED
    assert result.oci_verified is False
    assert result.applied_at is None


def test_local_schema_invalid_no_transfer(tmp_path, monkeypatch):
    _write_local(tmp_path, monkeypatch, content=b'{"holdings": []}')
    monkeypatch.setattr(mod, "require_env", lambda _k: "oci-krx")

    calls: list[list[str]] = []
    monkeypatch.setattr(
        mod, "_run", lambda cmd, timeout: (calls.append(cmd), (0, "", ""))[1]
    )
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_APPLY_FAILED
    assert calls == []  # SSH/scp 미호출


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
        if cmd[0] == "scp":
            return 1, "", "scp error"
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", _fake_run)
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_APPLY_FAILED
    assert not any(_is_active_mv(c) for c in calls)


def test_tmp_hash_mismatch_preserves_active(tmp_path, monkeypatch):
    _write_local(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "require_env", lambda _k: "oci-krx")

    calls: list[list[str]] = []

    def _fake_run(cmd, timeout):
        calls.append(cmd)
        if cmd[0] == "scp":
            return 0, "", ""
        if "sha256sum" in " ".join(cmd):
            return 0, "deadbeef", ""  # hash 불일치
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", _fake_run)
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_APPLY_FAILED
    assert not any(_is_active_mv(c) for c in calls)
    assert any("rm -f" in " ".join(c) for c in calls)


def test_tmp_schema_check_fail_preserves_active(tmp_path, monkeypatch):
    _write_local(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "require_env", lambda _k: "oci-krx")

    calls: list[list[str]] = []

    def _fake_run(cmd, timeout):
        calls.append(cmd)
        joined = " ".join(cmd)
        if cmd[0] == "scp":
            return 0, "", ""
        if "sha256sum" in joined:
            return 0, _SHA, ""
        if "json.load" in joined:  # 원격 schema 검증 실패
            return 1, "", ""
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", _fake_run)
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_APPLY_FAILED
    assert not any(_is_active_mv(c) for c in calls)


def test_active_mv_failure_preserves_active(tmp_path, monkeypatch):
    # 검증 통과했으나 단일 원자 교체(mv) 실패 → active 미변경(보존).
    _write_local(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "require_env", lambda _k: "oci-krx")

    def _fake_run(cmd, timeout):
        joined = " ".join(cmd)
        if cmd[0] == "scp":
            return 0, "", ""
        if "sha256sum" in joined:
            return 0, _SHA, ""
        if "json.load" in joined:
            return 0, "", ""
        if _is_active_mv(cmd):
            return 1, "", "mv error"  # 교체 실패
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", _fake_run)
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_APPLY_FAILED
    assert result.oci_verified is False


def test_success_order_single_payload(tmp_path, monkeypatch):
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
            return 0, _SHA, ""
        if "json.load" in joined:
            seq.append("schema")
            return 0, "", ""
        if _is_active_mv(cmd):
            seq.append("mv")
            return 0, "", ""
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", _fake_run)
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_OCI_APPLIED
    assert result.oci_verified is True
    assert result.content_sha256 == _SHA
    assert result.kind == mod._APPLY_KIND
    # 검증은 mv 앞, active 재확인(두 번째 sha256sum)은 mv 뒤. manifest 단계 없음.
    assert seq == ["scp", "sha256sum", "schema", "mv", "sha256sum"]


def test_no_separate_manifest_file_written(tmp_path, monkeypatch):
    # 별도 manifest 정본 파일을 만드는 원격 write 가 전혀 없어야 한다(계약).
    _write_local(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "require_env", lambda _k: "oci-krx")

    calls: list[list[str]] = []

    def _fake_run(cmd, timeout):
        calls.append(cmd)
        joined = " ".join(cmd)
        if cmd[0] == "scp":
            return 0, "", ""
        if "sha256sum" in joined:
            return 0, _SHA, ""
        if "json.load" in joined:
            return 0, "", ""
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", _fake_run)
    mod.apply_holdings_to_oci()
    # 원격 파일 조작 명령(ssh) 중 manifest 정본 파일을 만드는 것이 없다.
    #   (scp 로컬 경로에 tmp 디렉토리명이 우연히 'manifest' 를 포함할 수 있으므로
    #    ssh 원격 명령만 검사한다.)
    ssh_cmds = [" ".join(c) for c in calls if c and c[0] == "ssh"]
    assert not any("manifest" in j for j in ssh_cmds)
    # active(payload) 로 향하는 redirect write(`>`) 도 없다 — 교체는 오직 mv.
    assert not any(f"> {mod._REMOTE_FINAL}" in j for j in ssh_cmds)


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
            if state["sha_calls"] == 1:
                return 0, _SHA, ""  # tmp 검증 일치
            return 0, "different", ""  # 사후 active 불일치
        if "json.load" in joined:
            return 0, "", ""
        if _is_active_mv(cmd):
            return 0, "", ""
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", _fake_run)
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_OUT_OF_SYNC
    assert result.oci_verified is False


def test_active_hash_recheck_fail_unknown(tmp_path, monkeypatch):
    _write_local(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "require_env", lambda _k: "oci-krx")

    state = {"sha_calls": 0}

    def _fake_run(cmd, timeout):
        joined = " ".join(cmd)
        if cmd[0] == "scp":
            return 0, "", ""
        if "sha256sum" in joined:
            state["sha_calls"] += 1
            if state["sha_calls"] == 1:
                return 0, _SHA, ""
            return 1, "", "no such file"  # 사후 재확인 실패
        if "json.load" in joined:
            return 0, "", ""
        if _is_active_mv(cmd):
            return 0, "", ""
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", _fake_run)
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_UNKNOWN
    assert result.oci_verified is False
