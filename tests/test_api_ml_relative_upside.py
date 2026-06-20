"""tests for app.api_ml_relative_upside.

POST /market/relative-upside/run — 동기 처리. 핵심 검증:
  - 성공 (status=ok) — 5 필드 응답 + 사용자 친화 message.
  - main() 예외 raise → status=failed + 기존 snapshot 보존 (파일 변경 0건).
  - main() rc != 0 → status=failed.
  - main() rc=0 이지만 run_meta.status != "ok" → status=unavailable.
  - 응답에 device name / loss / epoch / artifact path / raw traceback 노출 0건.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api import app
from app.ml_relative_upside_score import RUN_META_PATH

client = TestClient(app)

# 일반 UI 응답에 노출되면 안 되는 raw 식별자 (지시문).
_FORBIDDEN_RAW_IN_RESPONSE = (
    "CUDA",
    "cuda",
    "epoch",
    "loss",
    "traceback",
    "Traceback",
    "feature_vector",
    "device_name",
    "NVIDIA",
    "artifact_path",
    "snapshot_path",
    "shell command",
)


def _assert_no_raw_identifiers(text: str) -> None:
    for ident in _FORBIDDEN_RAW_IN_RESPONSE:
        assert ident not in text, f"응답에 raw 식별자 노출: {ident!r}"


def _write_temp_run_meta(payload: dict) -> Path:
    """RUN_META_PATH 에 임시 meta 작성 후 경로 반환."""
    RUN_META_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUN_META_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return RUN_META_PATH


def test_run_success_returns_user_only_fields(monkeypatch):
    """성공 시 5 필드 응답 + 사용자 친화 message + raw 식별자 미노출."""
    fake_meta = {
        "schema_version": "relative_upside_score_run.v0",
        "status": "ok",
        "asof_date": "2026-06-19",
        "generated_at": "2026-06-20T15:00:00+00:00",
        "scored_candidate_count": 1111,
        "model": {
            "model_name": "relative_upside_v0_linear",
            "device_name": "NVIDIA GeForce RTX 4070 SUPER",
            "cuda_available": True,
            "gpu_execution_used": True,
            "train_loss_final": 0.069,
            "epochs": 200,
        },
    }
    _write_temp_run_meta(fake_meta)

    # main() 자체는 실행하지 않고 rc=0 만 시뮬레이션.
    monkeypatch.setattr("scripts.run_ml_relative_upside_score_v0.main", lambda: 0)
    resp = client.post("/market/relative-upside/run")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == {
        "status",
        "asof_date",
        "generated_at",
        "scored_candidate_count",
        "gpu_execution_used",
        "message",
    }
    assert body["status"] == "ok"
    assert body["asof_date"] == "2026-06-19"
    assert body["scored_candidate_count"] == 1111
    assert body["gpu_execution_used"] is True
    # device_name / cuda_available / train_loss_final / epochs 노출 0건.
    _assert_no_raw_identifiers(resp.text)


def test_run_success_without_gpu_returns_specific_message(monkeypatch):
    """GPU 사용 안 했을 때 메시지 변경 (지시문 — 'GPU 실행은 확인되지 않았습니다')."""
    fake_meta = {
        "schema_version": "relative_upside_score_run.v0",
        "status": "ok",
        "asof_date": "2026-06-19",
        "generated_at": "2026-06-20T15:00:00+00:00",
        "scored_candidate_count": 500,
        "model": {
            "device_name": "cpu",
            "cuda_available": False,
            "gpu_execution_used": False,
        },
    }
    _write_temp_run_meta(fake_meta)

    monkeypatch.setattr("scripts.run_ml_relative_upside_score_v0.main", lambda: 0)
    resp = client.post("/market/relative-upside/run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["gpu_execution_used"] is False
    assert "GPU 실행은 확인되지 않았습니다" in body["message"]
    _assert_no_raw_identifiers(resp.text)


def test_run_failure_preserves_existing_snapshot(monkeypatch):
    """main() 예외 raise → 응답 status=failed + 기존 run_meta 파일 변경 0건.

    지시문 — 실패 시 기존 정상 score snapshot 삭제/초기화/빈값 덮어쓰기 X.
    """
    # 기존 정상 meta 작성.
    fake_meta = {
        "schema_version": "relative_upside_score_run.v0",
        "status": "ok",
        "asof_date": "2026-06-18",  # 이전 정상 상태.
        "generated_at": "2026-06-19T00:00:00+00:00",
        "scored_candidate_count": 999,
        "model": {"gpu_execution_used": True},
    }
    meta_path = _write_temp_run_meta(fake_meta)
    before_content = meta_path.read_text(encoding="utf-8")

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated training failure with secret_path=/etc/x")

    monkeypatch.setattr("scripts.run_ml_relative_upside_score_v0.main", _raise)
    resp = client.post("/market/relative-upside/run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert "기존 점수는 유지됩니다" in body["message"]
    # 응답에 raw error / secret_path / traceback 노출 0건.
    _assert_no_raw_identifiers(resp.text)
    assert "secret_path" not in resp.text
    # 기존 meta 파일 변경 0건.
    after_content = meta_path.read_text(encoding="utf-8")
    assert before_content == after_content


def test_run_nonzero_rc_returns_failed(monkeypatch):
    """main() rc != 0 → status=failed (기존 snapshot 보존)."""
    monkeypatch.setattr("scripts.run_ml_relative_upside_score_v0.main", lambda: 2)
    resp = client.post("/market/relative-upside/run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    _assert_no_raw_identifiers(resp.text)


def test_run_meta_unavailable_returns_unavailable(monkeypatch):
    """main() rc=0 이지만 meta.status != 'ok' → status=unavailable."""
    fake_meta = {
        "schema_version": "relative_upside_score_run.v0",
        "status": "unavailable",
        "asof_date": "2026-06-19",
        "generated_at": "2026-06-20T15:00:00+00:00",
        "scored_candidate_count": 0,
        "model": {"gpu_execution_used": True},
    }
    _write_temp_run_meta(fake_meta)
    monkeypatch.setattr("scripts.run_ml_relative_upside_score_v0.main", lambda: 0)
    resp = client.post("/market/relative-upside/run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "unavailable"
    assert "기존 점수는 유지됩니다" in body["message"]
    _assert_no_raw_identifiers(resp.text)
