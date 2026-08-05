"""POC3-07 Holdings OCI 적용 로직 단위 테스트 (검증자 REJECTED r1 반영).

실제 OCI 로 write 하지 않는다 — subprocess(_run)·환경변수·로컬 파일을 monkeypatch
로 통제해 분기별 계약만 검증한다(설계자 Q11: 개발자는 dry-run·계약 검증만).

검증 계약(수정된 순서 — rename 전에 모든 검증 완료):
  - 로컬 파일 없음 → PC_SAVED (전송 시도 안 함).
  - 로컬 schema 손상 → APPLY_FAILED, SSH 를 아예 호출하지 않음(전송 안 함).
  - OCI_SSH_TARGET 미설정 → UNKNOWN.
  - scp 실패 → APPLY_FAILED, active 보존(mv 미호출).
  - 전송 tmp hash 불일치 → APPLY_FAILED, rename 안 함, tmp 정리.
  - 전송 tmp schema 검증 실패 → APPLY_FAILED, rename 안 함(rename 전 검증).
  - 정상: scp → sha256sum(tmp) → schema-check → mv → manifest → sha256sum(active) → OCI_APPLIED.
  - 사후 active hash 불일치 → OUT_OF_SYNC.
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
    monkeypatch.setattr(mod, "_LOCAL_MANIFEST", tmp_path / "manifest.json")
    return f


def test_missing_local_file_returns_pc_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_LOCAL_HOLDINGS", tmp_path / "nope.json")
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_PC_SAVED
    assert result.oci_verified is False
    assert result.applied_at is None


def test_local_schema_invalid_no_transfer(tmp_path, monkeypatch):
    # 손상된 로컬 파일(빈 holdings) → 전송조차 하지 않아야 한다.
    _write_local(tmp_path, monkeypatch, content=b'{"holdings": []}')
    monkeypatch.setattr(mod, "require_env", lambda _k: "oci-krx")

    calls: list[list[str]] = []
    monkeypatch.setattr(
        mod, "_run", lambda cmd, timeout: (calls.append(cmd), (0, "", ""))[1]
    )
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_APPLY_FAILED
    # SSH/scp 를 한 번도 호출하지 않았다(로컬 검증에서 차단).
    assert calls == []


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
            return 0, "deadbeef", ""  # tmp hash 불일치
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", _fake_run)
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_APPLY_FAILED
    assert not any("mv " in " ".join(c) for c in calls)
    assert any("rm -f" in " ".join(c) for c in calls)


def test_tmp_schema_check_fail_no_rename(tmp_path, monkeypatch):
    # 전송 무결성(hash)은 통과하지만 원격 schema 검증이 실패 → rename 금지.
    _write_local(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "require_env", lambda _k: "oci-krx")

    calls: list[list[str]] = []

    def _fake_run(cmd, timeout):
        calls.append(cmd)
        joined = " ".join(cmd)
        if cmd[0] == "scp":
            return 0, "", ""
        if "sha256sum" in joined:
            return 0, _SHA, ""  # hash 일치
        if "json.load" in joined:  # 원격 schema 검증
            return 1, "", ""  # 실패
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", _fake_run)
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_APPLY_FAILED
    # rename(mv) 안 함, tmp 정리함.
    assert not any("mv " in " ".join(c) for c in calls)
    assert any("rm -f" in " ".join(c) for c in calls)


def test_success_order_and_verified(tmp_path, monkeypatch):
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
        if "mv " in joined:
            seq.append("mv")
            return 0, "", ""
        if "> " in joined:  # manifest write
            seq.append("manifest")
            return 0, "", ""
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", _fake_run)
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_OCI_APPLIED
    assert result.oci_verified is True
    assert result.content_sha256 == _SHA
    assert result.applied_at is not None
    # 핵심 순서: schema 검증이 mv 앞에 온다.
    assert seq.index("schema") < seq.index("mv")
    assert seq.index("sha256sum") < seq.index("mv")
    # 순서 전체.
    assert seq == ["scp", "sha256sum", "schema", "mv", "manifest", "sha256sum"]


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
                return 0, _SHA, ""  # tmp 일치
            return 0, "different", ""  # 사후 active 불일치
        if "json.load" in joined:
            return 0, "", ""
        if "mv " in joined:
            return 0, "", ""
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", _fake_run)
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_OUT_OF_SYNC
    assert result.oci_verified is False
