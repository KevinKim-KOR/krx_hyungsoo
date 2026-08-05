"""POC3-07 Holdings OCI 적용 로직 단위 테스트 (검증자 REJECTED r3 반영).

실제 OCI 로 write 하지 않는다 — subprocess(_run)·환경변수·로컬 파일을 monkeypatch
로 통제해 분기별 계약만 검증한다(설계자 Q11: 개발자는 dry-run·계약 검증만).

검증 계약(확정 PLAN §4.3 — payload 승격이 마지막, 그 앞 실패는 active 보존):
  - 로컬 파일 없음 → PC_SAVED (전송 시도 안 함).
  - 로컬 schema 손상 → APPLY_FAILED, SSH 미호출.
  - OCI_SSH_TARGET 미설정 → UNKNOWN.
  - payload scp 실패 → APPLY_FAILED, payload mv 미호출(active 보존).
  - manifest-tmp 전송 실패 → APPLY_FAILED, payload mv 미호출(active 보존).
  - payload-tmp hash 불일치 → APPLY_FAILED, payload mv 미호출.
  - payload-tmp schema 불일치 → APPLY_FAILED, payload mv 미호출.
  - manifest 승격(mv) 실패 → APPLY_FAILED, **payload mv 미호출(active 보존)**.
  - 정상: scp → manifest 전송 → sha256sum(tmp) → schema → manifest mv → payload mv
    → sha256sum(active) → OCI_APPLIED. payload mv 는 항상 manifest mv 뒤(마지막).
  - 승격 후 active hash 불일치 → OUT_OF_SYNC (PLAN §4.3 재확인).
  - 승격 후 hash 재확인 자체 실패 → UNKNOWN.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import app.holdings_oci_apply as mod

_VALID = {"holdings": [{"ticker": "069500", "quantity": 1.0, "avg_buy_price": 100.0}]}
_CONTENT = json.dumps(_VALID, ensure_ascii=False).encode("utf-8")
_SHA = hashlib.sha256(_CONTENT).hexdigest()


def _write_local(tmp_path: Path, monkeypatch, content: bytes = _CONTENT) -> Path:
    f = tmp_path / "holdings_latest.json"
    f.write_bytes(content)
    monkeypatch.setattr(mod, "_LOCAL_HOLDINGS", f)
    return f


def _is_payload_mv(cmd: list[str]) -> bool:
    """payload-tmp → active 승격(mv)인가(마지막 원자 교체)."""
    j = " ".join(cmd)
    return f"mv {mod._REMOTE_TMP} {mod._REMOTE_FINAL}" in j


def _is_manifest_mv(cmd: list[str]) -> bool:
    j = " ".join(cmd)
    return f"mv {mod._REMOTE_MANIFEST_TMP} {mod._REMOTE_MANIFEST}" in j


def _is_manifest_transfer(cmd: list[str]) -> bool:
    """manifest 를 manifest-tmp 로 쓰는 원격 명령."""
    return f"> {mod._REMOTE_MANIFEST_TMP}" in " ".join(cmd)


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
    assert not any(_is_payload_mv(c) for c in calls)  # active 보존


def test_manifest_transfer_failure_preserves_active(tmp_path, monkeypatch):
    # manifest-tmp 전송 실패 → payload 승격 안 함(active 보존).
    _write_local(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "require_env", lambda _k: "oci-krx")

    calls: list[list[str]] = []

    def _fake_run(cmd, timeout):
        calls.append(cmd)
        if cmd[0] == "scp":
            return 0, "", ""
        if _is_manifest_transfer(cmd):
            return 1, "", "disk full"  # manifest 전송 실패
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", _fake_run)
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_APPLY_FAILED
    assert not any(_is_payload_mv(c) for c in calls)


def test_tmp_hash_mismatch_preserves_active(tmp_path, monkeypatch):
    _write_local(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "require_env", lambda _k: "oci-krx")

    calls: list[list[str]] = []

    def _fake_run(cmd, timeout):
        calls.append(cmd)
        joined = " ".join(cmd)
        if cmd[0] == "scp":
            return 0, "", ""
        if "sha256sum" in joined:
            return 0, "deadbeef", ""  # hash 불일치
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", _fake_run)
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_APPLY_FAILED
    assert not any(_is_payload_mv(c) for c in calls)
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
    assert not any(_is_payload_mv(c) for c in calls)


def test_manifest_promote_failure_preserves_active(tmp_path, monkeypatch):
    # 검증 모두 통과했으나 manifest 승격(mv) 실패 → payload 승격 안 함(active 보존).
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
        if _is_manifest_mv(cmd):
            return 1, "", "mv error"  # manifest 승격 실패
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", _fake_run)
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_APPLY_FAILED
    # 핵심: manifest 승격 실패 시 payload 는 active 로 올라가지 않는다(보존).
    assert not any(_is_payload_mv(c) for c in calls)


def test_success_order_and_verified(tmp_path, monkeypatch):
    _write_local(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "require_env", lambda _k: "oci-krx")

    seq: list[str] = []

    def _fake_run(cmd, timeout):
        joined = " ".join(cmd)
        if cmd[0] == "scp":
            seq.append("scp")
            return 0, "", ""
        if _is_manifest_transfer(cmd):
            seq.append("manifest_xfer")
            return 0, "", ""
        if "sha256sum" in joined:
            seq.append("sha256sum")
            return 0, _SHA, ""
        if "json.load" in joined:
            seq.append("schema")
            return 0, "", ""
        if _is_manifest_mv(cmd):
            seq.append("manifest_mv")
            return 0, "", ""
        if _is_payload_mv(cmd):
            seq.append("payload_mv")
            return 0, "", ""
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", _fake_run)
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_OCI_APPLIED
    assert result.oci_verified is True
    assert result.content_sha256 == _SHA
    # 모든 검증·manifest 승격이 payload 승격 앞에 온다(실패 시 보존 보장).
    assert seq.index("sha256sum") < seq.index("payload_mv")
    assert seq.index("schema") < seq.index("payload_mv")
    assert seq.index("manifest_mv") < seq.index("payload_mv")
    # 전체 순서(PLAN §4.3: 승격 후 active hash 재확인 포함).
    assert seq == [
        "scp",
        "manifest_xfer",
        "sha256sum",
        "schema",
        "manifest_mv",
        "payload_mv",
        "sha256sum",
    ]


def test_active_hash_mismatch_after_apply_out_of_sync(tmp_path, monkeypatch):
    # 승격 후 active hash 재확인 불일치 → OUT_OF_SYNC(PLAN §4.3).
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
        if _is_manifest_mv(cmd) or _is_payload_mv(cmd):
            return 0, "", ""
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", _fake_run)
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_OUT_OF_SYNC
    assert result.oci_verified is False


def test_active_hash_recheck_fail_unknown(tmp_path, monkeypatch):
    # 승격 후 hash 재확인 자체 실패(rc!=0) → UNKNOWN.
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
                return 0, _SHA, ""  # tmp 검증
            return 1, "", "no such file"  # 사후 재확인 실패
        if "json.load" in joined:
            return 0, "", ""
        if _is_manifest_mv(cmd) or _is_payload_mv(cmd):
            return 0, "", ""
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", _fake_run)
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_UNKNOWN
    assert result.oci_verified is False
