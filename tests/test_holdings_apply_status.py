"""POC3-08 Holdings OCI 적용 status 지속 기록 테스트(요구 4).

_save_apply_status/read_apply_status 는 마지막 적용 시각·상태를 PC 로컬에 남겨
화면 재진입해도 표시되게 한다. 이 파일은 성공 판정 근거가 아니라 표시용이다.
"""

from __future__ import annotations

import app.holdings_oci_apply as mod


def _redirect_status(tmp_path, monkeypatch):
    p = tmp_path / "holdings_apply_status_latest.json"
    monkeypatch.setattr(mod, "_LOCAL_APPLY_STATUS", p)
    return p


def test_read_status_none_when_no_file(tmp_path, monkeypatch):
    _redirect_status(tmp_path, monkeypatch)
    assert mod.read_apply_status() is None


def test_save_then_read_roundtrip(tmp_path, monkeypatch):
    _redirect_status(tmp_path, monkeypatch)
    result = mod.HoldingsApplyResult(
        status=mod.STATUS_OCI_APPLIED,
        applied_at="2026-08-06T06:40:00+00:00",
        content_sha256="abc123",
        oci_verified=True,
        message="보유 종목을 OCI 에 적용했습니다.",
    )
    mod._save_apply_status(result)
    rec = mod.read_apply_status()
    assert rec is not None
    assert rec["status"] == mod.STATUS_OCI_APPLIED
    assert rec["applied_at"] == "2026-08-06T06:40:00+00:00"
    assert rec["oci_verified"] is True
    assert "message" in rec
    assert "recorded_at" in rec
    # secret/remote path 류는 저장하지 않는다.
    assert "ssh" not in " ".join(rec.keys()).lower()


def test_read_corrupted_returns_none(tmp_path, monkeypatch):
    p = _redirect_status(tmp_path, monkeypatch)
    p.write_text("{ not valid json", encoding="utf-8")
    assert mod.read_apply_status() is None


def test_read_non_dict_returns_none(tmp_path, monkeypatch):
    p = _redirect_status(tmp_path, monkeypatch)
    p.write_text("[1, 2, 3]", encoding="utf-8")
    assert mod.read_apply_status() is None


def test_apply_writes_status_except_pc_saved(tmp_path, monkeypatch):
    # PC_SAVED(로컬 파일 없음 → 적용 시도 안 함)면 status 기록하지 않는다.
    _redirect_status(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "_LOCAL_HOLDINGS", tmp_path / "nope.json")
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_PC_SAVED
    assert mod.read_apply_status() is None  # 기록 안 됨


def test_apply_records_status_on_real_attempt(tmp_path, monkeypatch):
    # 실제 적용 시도(성공 경로 mock)면 status 가 기록된다.
    import hashlib
    import json

    valid = {
        "holdings": [{"ticker": "069500", "quantity": 1.0, "avg_buy_price": 100.0}]
    }
    content = json.dumps(valid, ensure_ascii=False).encode("utf-8")
    sha = hashlib.sha256(content).hexdigest()

    hf = tmp_path / "holdings_latest.json"
    hf.write_bytes(content)
    monkeypatch.setattr(mod, "_LOCAL_HOLDINGS", hf)
    _redirect_status(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "require_env", lambda _k: "oci-krx")

    def _fake_run(cmd, timeout):
        joined = " ".join(cmd)
        if cmd[0] == "scp":
            return 0, "", ""
        if "sha256sum" in joined:
            return 0, sha, ""
        if "json.load" in joined:
            return 0, "", ""
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", _fake_run)
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_OCI_APPLIED
    rec = mod.read_apply_status()
    assert rec is not None
    assert rec["status"] == mod.STATUS_OCI_APPLIED
    assert rec["applied_at"] is not None
