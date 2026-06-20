"""tests for app.api_ml_relative_upside.

POST /market/relative-upside/run — 동기 처리. 핵심 검증:
  - 성공 (status=ok) — 6 필드 응답 (status / asof_date / generated_at /
    scored_candidate_count / gpu_execution_used / message) + 사용자 친화 message.
  - main() 예외 raise → status=failed.
  - main() rc != 0 → status=failed.
  - main() rc=0 이지만 run_meta.status != "ok" → status=unavailable.
  - main() 의 실제 unavailable / failed 경로 (model None / inference_rows 빈)
    에서 기존 score snapshot 파일을 덮어쓰지 않는다 (실패 시 기존 점수 보존).
  - run meta 파일 손상 시 status=unavailable (B-1).
  - 응답에 device name / loss / epoch / artifact path / raw traceback 노출 0건.

본 테스트는 실제 운영 artifact 파일 (state/ml/relative_upside_score_run_latest.
json) 을 건드리지 않는다 — monkeypatch 로 RUN_META_PATH 와
SCORE_SNAPSHOT_PATH 를 tmp_path 로 격리 (B-6).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import app

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


@pytest.fixture
def isolated_meta(tmp_path: Path, monkeypatch) -> Path:
    """RUN_META_PATH 와 SCORE_SNAPSHOT_PATH 를 tmp_path 로 격리.

    api_ml_relative_upside 의 모듈 전역 RUN_META_PATH 도 함께 patch — 실제
    state/ml/ 의 운영 artifact 를 오염시키지 않는다.
    """
    fake_meta_path = tmp_path / "relative_upside_score_run_latest.json"
    fake_snapshot_path = tmp_path / "relative_upside_score_latest.json"

    monkeypatch.setattr("app.ml_relative_upside_score.RUN_META_PATH", fake_meta_path)
    monkeypatch.setattr(
        "app.ml_relative_upside_score.SCORE_SNAPSHOT_PATH", fake_snapshot_path
    )
    monkeypatch.setattr("app.api_ml_relative_upside.RUN_META_PATH", fake_meta_path)
    return fake_meta_path


def _write_meta(meta_path: Path, payload: dict) -> None:
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def test_run_success_returns_6_user_fields(monkeypatch, isolated_meta):
    """성공 시 6 필드 응답 (지시문 — status 포함) + 사용자 친화 message + raw 식별자 미노출."""
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
    _write_meta(isolated_meta, fake_meta)

    monkeypatch.setattr(
        "scripts.run_ml_relative_upside_score_v0.main", lambda argv=None: 0
    )
    resp = client.post("/market/relative-upside/run")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # 응답은 정확히 6 필드 (지시문 — status 포함).
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
    _assert_no_raw_identifiers(resp.text)


def test_run_success_without_gpu_returns_specific_message(monkeypatch, isolated_meta):
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
    _write_meta(isolated_meta, fake_meta)

    monkeypatch.setattr(
        "scripts.run_ml_relative_upside_score_v0.main", lambda argv=None: 0
    )
    resp = client.post("/market/relative-upside/run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["gpu_execution_used"] is False
    assert "GPU 실행은 확인되지 않았습니다" in body["message"]
    _assert_no_raw_identifiers(resp.text)


def test_run_failure_preserves_existing_meta_file(monkeypatch, isolated_meta):
    """main() 예외 raise → 응답 status=failed + 기존 run_meta 파일 변경 0건."""
    fake_meta = {
        "schema_version": "relative_upside_score_run.v0",
        "status": "ok",
        "asof_date": "2026-06-18",
        "generated_at": "2026-06-19T00:00:00+00:00",
        "scored_candidate_count": 999,
        "model": {"gpu_execution_used": True},
    }
    _write_meta(isolated_meta, fake_meta)
    before_content = isolated_meta.read_text(encoding="utf-8")

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated training failure with secret_path=/etc/x")

    monkeypatch.setattr("scripts.run_ml_relative_upside_score_v0.main", _raise)
    resp = client.post("/market/relative-upside/run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert "기존 점수는 유지됩니다" in body["message"]
    _assert_no_raw_identifiers(resp.text)
    assert "secret_path" not in resp.text
    # 기존 meta 파일 변경 0건.
    after_content = isolated_meta.read_text(encoding="utf-8")
    assert before_content == after_content


def test_run_nonzero_rc_returns_failed(monkeypatch, isolated_meta):
    monkeypatch.setattr(
        "scripts.run_ml_relative_upside_score_v0.main", lambda argv=None: 2
    )
    resp = client.post("/market/relative-upside/run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    _assert_no_raw_identifiers(resp.text)


def test_run_meta_unavailable_returns_unavailable(monkeypatch, isolated_meta):
    fake_meta = {
        "schema_version": "relative_upside_score_run.v0",
        "status": "unavailable",
        "asof_date": "2026-06-19",
        "generated_at": "2026-06-20T15:00:00+00:00",
        "scored_candidate_count": 0,
        "model": {"gpu_execution_used": True},
    }
    _write_meta(isolated_meta, fake_meta)
    monkeypatch.setattr(
        "scripts.run_ml_relative_upside_score_v0.main", lambda argv=None: 0
    )
    resp = client.post("/market/relative-upside/run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "unavailable"
    assert "기존 점수는 유지됩니다" in body["message"]
    _assert_no_raw_identifiers(resp.text)


def test_run_meta_corrupted_returns_unavailable(monkeypatch, isolated_meta):
    """run meta 파일이 손상 (JSON parse 실패) 시 status=unavailable + 사용자 친화 message (B-1)."""
    isolated_meta.parent.mkdir(parents=True, exist_ok=True)
    isolated_meta.write_text("not a valid json {{{", encoding="utf-8")
    monkeypatch.setattr(
        "scripts.run_ml_relative_upside_score_v0.main", lambda argv=None: 0
    )
    resp = client.post("/market/relative-upside/run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "unavailable"
    assert "기존 점수는 유지됩니다" in body["message"]
    assert "운영 상태 파일을 읽지 못했습니다" in body["message"]
    _assert_no_raw_identifiers(resp.text)


def test_main_unavailable_branch_does_not_overwrite_existing_snapshot(
    monkeypatch, tmp_path
):
    """main() 의 unavailable/failed 경로 (model None / inference_rows 빈) 에서
    기존 score snapshot 파일을 덮어쓰지 않는다 (A-1 핵심 수정 검증).

    1. 정상 snapshot 을 SCORE_SNAPSHOT_PATH 에 기록.
    2. main() 의 학습 단계가 train_walk_forward 에서 model=None 반환하도록 patch.
    3. main() 호출 후 SCORE_SNAPSHOT_PATH 파일 변경 0건 확인.
    """
    fake_snapshot_path = tmp_path / "relative_upside_score_latest.json"
    fake_meta_path = tmp_path / "relative_upside_score_run_latest.json"
    # 기존 정상 snapshot 시뮬레이션.
    existing_snapshot = {
        "schema_version": "relative_upside_score.v0",
        "status": "ok",
        "asof_date": "2026-06-15",
        "candidates": [{"ticker": "069500", "relative_upside_score": 50.0}],
    }
    fake_snapshot_path.write_text(
        json.dumps(existing_snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    before = fake_snapshot_path.read_text(encoding="utf-8")

    # 모듈 전역 path patch.
    monkeypatch.setattr(
        "app.ml_relative_upside_score.SCORE_SNAPSHOT_PATH", fake_snapshot_path
    )
    monkeypatch.setattr("app.ml_relative_upside_score.RUN_META_PATH", fake_meta_path)

    # main() 의 의존성 stub.
    monkeypatch.setattr(
        "app.market_data_store.list_etf_tickers",
        lambda: ["069500", "TEST1"],
    )
    monkeypatch.setattr(
        "app.market_data_store.fetch_price_history",
        lambda ticker: [("2026-06-19", 100.0)],
    )

    # train_walk_forward 가 model=None 반환 (학습 데이터 부족 시뮬레이션).
    from app.ml_relative_upside_model import TrainResult
    from app.ml_relative_upside_features import FEATURE_COLUMNS

    def _fake_train(rows, **kwargs):
        return None, TrainResult(
            train_row_count=0,
            test_row_count=0,
            train_date_range=("", ""),
            test_date_range=("", ""),
            train_loss_final=float("nan"),
            test_loss_final=float("nan"),
            epochs=0,
            learning_rate=0.001,
            device_name="cpu",
            cuda_available=False,
            gpu_execution_used=False,
            train_seconds=0.0,
            feature_columns=FEATURE_COLUMNS,
        )

    monkeypatch.setattr(
        "scripts.run_ml_relative_upside_score_v0.train_walk_forward",
        _fake_train,
    )

    from scripts.run_ml_relative_upside_score_v0 import main as run_ml_main

    # argv=[] 로 명시 호출 — sys.argv 오염과 무관하게 default 만 사용.
    # API 경로 (uvicorn) / pytest 경로 양쪽 모두 안전 (FIX r3 — uvicorn sys.argv
    # 가 argparse 에 흘러들어가 SystemExit 발생하는 회귀 차단).
    rc = run_ml_main(argv=[])
    assert rc == 0
    # 기존 score snapshot 파일 변경 0건 — A-1 핵심 검증.
    after = fake_snapshot_path.read_text(encoding="utf-8")
    assert before == after
    # run meta 는 갱신됨 (이력 추적용).
    assert fake_meta_path.exists()
    meta = json.loads(fake_meta_path.read_text(encoding="utf-8"))
    assert meta["status"] in ("failed", "unavailable")
    # snapshot_path 는 빈 문자열 ("저장 안 함" 명시).
    assert meta["snapshot_path"] == ""


def test_api_call_isolated_from_uvicorn_sys_argv(monkeypatch, isolated_meta):
    """API 경로에서 sys.argv 가 uvicorn 인자로 오염돼 있어도 정상 동작.

    FIX r3 — 실제 운영에서 uvicorn 의 sys.argv 가
    `["app.api:app", "--host", "127.0.0.1", "--port", "8000", "--reload"]`
    형태로 오염돼 있어 main() 안의 argparse 가 SystemExit(2) 를 발생시키던
    회귀를 차단. 해결: API endpoint 에서 `run_ml_main(argv=[])` 로 명시 호출.
    """
    import sys as _sys

    # uvicorn 운영 환경과 동일한 sys.argv 오염 시뮬레이션.
    monkeypatch.setattr(
        _sys,
        "argv",
        ["uvicorn", "app.api:app", "--host", "127.0.0.1", "--port", "8000"],
    )

    fake_meta = {
        "schema_version": "relative_upside_score_run.v0",
        "status": "ok",
        "asof_date": "2026-06-19",
        "generated_at": "2026-06-20T15:00:00+00:00",
        "scored_candidate_count": 1111,
        "model": {"gpu_execution_used": True},
    }
    _write_meta(isolated_meta, fake_meta)

    # main 시그니처가 argv 키워드를 받아야 한다 (FIX r3 — API 가 argv=[] 호출).
    captured = {}

    def _fake_main(argv=None):
        captured["argv"] = argv
        return 0

    monkeypatch.setattr("scripts.run_ml_relative_upside_score_v0.main", _fake_main)
    resp = client.post("/market/relative-upside/run")
    # SystemExit 회귀 시 응답이 500 또는 status=failed 가 되지 않고 정상 200/ok.
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ok"
    # API 가 argv=[] 로 명시 호출했는지 확인 (uvicorn sys.argv 격리).
    assert captured["argv"] == []
    _assert_no_raw_identifiers(resp.text)
