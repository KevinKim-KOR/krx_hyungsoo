"""POC2 PUSH 사용자 표현 정리 + PARAM 적용 UI 연결 API 테스트 (2026-06-20).

GET  /three-push/param/state 의 응답 형식 / raw 식별자 미노출 확인.
POST /three-push/param/apply 의 실패 분기에서 raw 식별자 미노출 + 기존 PARAM 보호.

OCI SSH 호출은 subprocess monkeypatch 로 격리 — 실제 OCI 접근 X.

POC5-27(2026-10-20): 상태 값이 실제 적용 결과로 바뀌었다(active_same · activated · failed ·
unconfirmed · 예전 기록 delivered_only). 적용 순서는 `three_push_param_activation.Remote` 를
바꿔 끼워 시험한다(conftest 가 실제 OCI 연결을 막는다).
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
        "delivered_only",
        "active_same",
        "activated",
        "failed",
        "unconfirmed",
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
    assert (
        "_" not in body["display_label"]
    ), f"display_label 에 snake_case 노출: {body['display_label']!r}"


def test_param_apply_failure_preserves_existing_state(monkeypatch, caplog):
    """sync subprocess 실패 시 응답에 raw 식별자 노출 0건 + 기존 OCI 값 보호 (AC-9 / AC-10).

    POC5-27: OCI 활성값을 먼저 읽고(가짜 · PC 와 다른 값) 다르므로 전달 단계(실제
    `_run_sync_to_oci` → sync subprocess)까지 간다. subprocess.run 을 실패로 바꿔 끼운다.
    실제 OCI scp 는 호출하지 않는다. stderr(SSH 대상 · 경로가 있을 수 있음)는 응답 · 로그 모두 0건.
    """
    import json
    import subprocess

    from app import three_push_param_activation as act
    from app.runtime_param_store import _split_value_columns, flatten_param_dict
    from app.three_push_runtime_param import build_manual_seed_param

    other = build_manual_seed_param(enabled_push_kinds=["market_briefing"]).to_dict()
    rows = [
        [k, vt, *_split_value_columns(vt, v)] for k, vt, v in flatten_param_dict(other)
    ]
    tool_calls: list[str] = []

    def _ssh(cmd: str, timeout: float):
        if "sqlite3.connect" in cmd:
            return 0, json.dumps({"rows": rows})
        tool_calls.append(cmd)
        return 0, ""

    monkeypatch.setattr(
        act,
        "default_remote",
        lambda deliver: act.Remote(ssh=_ssh, scp=lambda *a: 0, deliver=deliver),
    )

    def _fake_run(*args, **kwargs):
        class _R:
            returncode = 1
            stdout = ""
            stderr = "scp: failed to connect ubuntu@oci-host:/home/ubuntu/x"

        return _R()

    monkeypatch.setattr(subprocess, "run", _fake_run)

    resp = client.post("/three-push/param/apply")
    # subprocess 실패여도 endpoint 자체는 200 (status="failed" 로 분기).
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "failed"
    assert "OCI 전달 실패" in body["message"]
    assert body["oci_verified"] is False
    assert tool_calls == []  # 전달 실패 → 도구 업로드 · 실행 없음(OCI DB 그대로)
    # raw 식별자 노출 0건(응답) · stderr 는 로그에도 없다.
    _assert_no_raw_identifiers(resp.text)
    assert "scp: failed to connect" not in resp.text
    assert "oci-host" not in caplog.text
