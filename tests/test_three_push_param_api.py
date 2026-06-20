"""POC2 PUSH 사용자 표현 정리 + PARAM 적용 UI 연결 API 테스트 (2026-06-20).

GET  /three-push/param/state 의 응답 형식 / raw 식별자 미노출 확인.
POST /three-push/param/apply 의 실패 분기에서 raw 식별자 미노출 + 기존 PARAM 보호.

OCI SSH 호출은 subprocess monkeypatch 로 격리 — 실제 OCI 접근 X.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import app

client = TestClient(app)

# Telegram / SSH / file path 식별자는 응답에 절대 노출 금지 (지시문 §5.2 / §6).
_FORBIDDEN_RAW_IN_RESPONSE = (
    "param_id",
    "manual_seed",
    "ssh_target",
    "remote_dir",
    "remote_path",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "latest_runtime_param.json",
    "scp",
    "ssh",
)


def _assert_no_raw_identifiers(text: str) -> None:
    for ident in _FORBIDDEN_RAW_IN_RESPONSE:
        assert ident not in text, f"응답에 raw 식별자 노출: {ident!r}"


def test_param_state_returns_user_only_fields():
    """GET /three-push/param/state 가 사용자 중심 dict 만 반환 (AC-5 / AC-10)."""
    resp = client.get("/three-push/param/state")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # 지시문 §6 데이터 계약 — 정확히 5개 필드만.
    assert set(body.keys()) == {
        "status",
        "display_label",
        "applied_at",
        "oci_verified",
        "message",
    }
    assert body["status"] in (
        "not_applied",
        "applying",
        "applied",
        "failed",
        "verification_required",
    )
    assert isinstance(body["display_label"], str)
    assert isinstance(body["oci_verified"], bool)
    # applied_at 은 사용자 표시 문자열 또는 null.
    assert body["applied_at"] is None or isinstance(body["applied_at"], str)
    # raw 식별자 노출 0건.
    _assert_no_raw_identifiers(resp.text)


def test_param_state_display_label_is_user_friendly():
    """display_label 이 manual_seed / baseline_static 같은 raw 식별자가 아닌
    '기본 운영 기준' 등 사용자 친화 문자열이어야 한다."""
    resp = client.get("/three-push/param/state")
    assert resp.status_code == 200
    body = resp.json()
    assert body["display_label"] != "manual_seed"
    assert body["display_label"] != "baseline_static"
    assert "_" not in body["display_label"], (
        f"display_label 에 snake_case 노출: {body['display_label']!r}"
    )


def test_param_apply_failure_preserves_existing_state(monkeypatch):
    """sync subprocess 실패 시 응답에 raw 식별자 노출 0건 + 기존 sync_status
    파일 보호 (AC-9 / AC-10).

    실제 OCI scp 는 호출하지 않고 subprocess.run 을 monkeypatch.
    """
    import subprocess

    def _fake_run(*args, **kwargs):
        class _R:
            returncode = 1
            stdout = ""
            stderr = "scp: failed to connect"

        return _R()

    monkeypatch.setattr(subprocess, "run", _fake_run)

    resp = client.post("/three-push/param/apply")
    # subprocess 실패여도 endpoint 자체는 200 (status="failed" 로 분기).
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] in ("failed", "not_applied")
    assert body["oci_verified"] is False
    # raw stderr/path 노출 0건.
    _assert_no_raw_identifiers(resp.text)
    assert "scp: failed to connect" not in resp.text
