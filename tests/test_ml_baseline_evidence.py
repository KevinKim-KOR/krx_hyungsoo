"""ML Baseline Evidence Draft Integration — builder + bullet + draft 통합 테스트.

POC2 2026-06-11. 지시문 §8 AC-1 ~ AC-10 / §9 검증 지시.

원칙 (지시문 §4.1 / §7):
- 재계산 / feature 재생성 / 외부 source 호출 / ML 학습 0건.
- 매수 / 매도 / 추천 / 현금비중 / 조정장 / 위험 알림 / 위험 threshold 문구 0건.
- report 부재 / 손상 / stale 도 draft 실패시키지 않는다.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.ml_baseline_evidence import (
    BASELINE_REPORT_PATH,
    EXTERNAL_CONTEXT_CHECKLIST,
    JUDGMENT_LABEL,
    STALE_DAYS_THRESHOLD,
    build_ml_baseline_evidence_bullet,
    build_ml_baseline_evidence_factor_signal,
    build_ml_baseline_evidence_snapshot,
    render_ml_baseline_evidence_bullet,
)

PROHIBITED_WORDS = [
    "매수",
    "매도",
    "추천",
    "현금비중",
    "조정장",
    "위험 알림",
    "교체",
    "BUY",
    "SELL",
]


def _make_ok_report() -> dict:
    return {
        "status": "ok",
        "generated_at": "2026-06-11T00:00:00Z",
        "feature_asof_range": {
            "start": "2026-03-11",
            "end": "2026-06-08",
            "trading_days": 60,
        },
        "evaluated_asof_range": {
            "start": "2026-03-11",
            "end": "2026-05-10",
            "evaluated_days": 40,
        },
        "candidate_baseline": {
            "status": "ok",
            "evaluated_days": 40,
            "evaluated_ticker_count": 1099,
            "target_horizons": [5, 10, 20],
            "top_group_quantile": 0.2,
            "top_group_avg_future_return": {"5d": 0.0343, "10d": 0.0554, "20d": 0.1351},
            "universe_median_future_return": {
                "5d": 0.0111,
                "10d": 0.0210,
                "20d": 0.0467,
            },
            "hit_rate": {"5d": 0.55, "10d": 0.58, "20d": 0.61},
            "rank_correlation": {"5d": 0.220, "10d": 0.133, "20d": 0.188},
        },
        "risk_baseline": {
            "status": "ok",
            "evaluated_days": 40,
            "high_risk_group_future_drawdown": {"5d": -0.0583, "10d": -0.0809},
            "low_risk_group_future_drawdown": {"5d": -0.0108, "10d": -0.0340},
            "drawdown_capture_rate": {"5d": 1.72, "10d": 1.44},
        },
        "leakage_checks": {
            "feature_future_data_leakage_detected": False,
            "target_horizon_short_tail_excluded": True,
            "time_order_preserved": True,
        },
        "warnings": [],
        "errors": [],
    }


# ─── snapshot builder ────────────────────────────────────────────────


def test_snapshot_unavailable_when_report_missing(tmp_path: Path):
    fake = tmp_path / "missing.json"
    snap = build_ml_baseline_evidence_snapshot(report_path=fake)
    assert snap["status"] == "unavailable"
    assert snap["report_status"] == "unavailable"
    assert snap["candidate_summary"] is None
    assert snap["risk_summary"] is None
    assert snap["external_context_checklist"] == EXTERNAL_CONTEXT_CHECKLIST


def test_snapshot_error_when_report_corrupted(tmp_path: Path):
    snap_path = tmp_path / "broken.json"
    snap_path.write_text("{invalid json", encoding="utf-8")
    snap = build_ml_baseline_evidence_snapshot(report_path=snap_path)
    assert snap["status"] == "error"
    assert snap["report_status"] == "error"


def test_snapshot_ok_when_report_fresh(tmp_path: Path):
    p = tmp_path / "report.json"
    p.write_text(json.dumps(_make_ok_report()), encoding="utf-8")
    # feature_end=2026-06-08, today=2026-06-11 → 3일 차이 → fresh.
    snap = build_ml_baseline_evidence_snapshot(report_path=p, today=date(2026, 6, 11))
    assert snap["status"] == "ok"
    assert snap["report_status"] == "ok"
    assert snap["candidate_summary"]["evaluated_days"] == 40
    assert snap["risk_summary"]["high_risk_group_future_drawdown"][
        "10d"
    ] == pytest.approx(-0.0809)
    assert snap["leakage_summary"]["future_data_leakage_detected"] is False
    assert snap["leakage_summary"]["tail_excluded"] is True
    assert isinstance(snap["limitations"], list) and len(snap["limitations"]) >= 1


def test_snapshot_stale_when_feature_end_old(tmp_path: Path):
    report = _make_ok_report()
    p = tmp_path / "report.json"
    p.write_text(json.dumps(report), encoding="utf-8")
    far_future = date(2026, 6, 8) + __import__("datetime").timedelta(
        days=STALE_DAYS_THRESHOLD + 5
    )
    snap = build_ml_baseline_evidence_snapshot(report_path=p, today=far_future)
    assert snap["status"] == "stale"
    # stale 한계 문구가 limitations 에 포함.
    assert any("오래" in s for s in snap["limitations"])


def test_snapshot_warn_when_report_status_warn(tmp_path: Path):
    report = _make_ok_report()
    report["status"] = "warn"
    p = tmp_path / "report.json"
    p.write_text(json.dumps(report), encoding="utf-8")
    snap = build_ml_baseline_evidence_snapshot(report_path=p, today=date(2026, 6, 11))
    assert snap["status"] == "warn"


def test_snapshot_error_when_errors_list_nonempty(tmp_path: Path):
    report = _make_ok_report()
    report["errors"] = ["coverage_failed"]
    p = tmp_path / "report.json"
    p.write_text(json.dumps(report), encoding="utf-8")
    snap = build_ml_baseline_evidence_snapshot(report_path=p, today=date(2026, 6, 11))
    assert snap["status"] == "error"


# ─── bullet builder — 금지 문구 ──────────────────────────────────────


def test_bullet_contains_evidence_phrases_for_ok_snapshot(tmp_path: Path):
    p = tmp_path / "report.json"
    p.write_text(json.dumps(_make_ok_report()), encoding="utf-8")
    snap = build_ml_baseline_evidence_snapshot(report_path=p, today=date(2026, 6, 11))
    bullet = build_ml_baseline_evidence_bullet(snap)
    assert bullet is not None
    assert JUDGMENT_LABEL in bullet
    # 평가 거래일 / candidate / risk / leakage 4가지 모두 본문에 노출.
    assert "평가 40거래일" in bullet
    assert "후보 발굴 baseline" in bullet
    assert "위험 baseline" in bullet
    assert "leakage" in bullet


def test_bullet_no_prohibited_wording_for_ok_snapshot(tmp_path: Path):
    p = tmp_path / "report.json"
    p.write_text(json.dumps(_make_ok_report()), encoding="utf-8")
    snap = build_ml_baseline_evidence_snapshot(report_path=p, today=date(2026, 6, 11))
    bullet = build_ml_baseline_evidence_bullet(snap)
    assert bullet is not None
    for w in PROHIBITED_WORDS:
        assert w not in bullet, f"금지 문구 '{w}' 가 bullet 에 포함됨: {bullet}"


def test_bullet_unavailable_when_report_missing(tmp_path: Path):
    snap = build_ml_baseline_evidence_snapshot(report_path=tmp_path / "missing.json")
    bullet = build_ml_baseline_evidence_bullet(snap)
    assert bullet is not None
    assert "사용할 수 없습니다" in bullet
    for w in PROHIBITED_WORDS:
        assert w not in bullet


# ─── factor_signal + render via payload ──────────────────────────────


def test_factor_signal_added_for_ok_snapshot(tmp_path: Path):
    p = tmp_path / "report.json"
    p.write_text(json.dumps(_make_ok_report()), encoding="utf-8")
    snap = build_ml_baseline_evidence_snapshot(report_path=p, today=date(2026, 6, 11))
    sig = build_ml_baseline_evidence_factor_signal(
        snap, asof_iso="2026-06-11T00:00:00Z"
    )
    assert sig is not None
    assert sig["scope"] == "ml_baseline_evidence"
    assert sig["is_available"] is True
    assert sig["reason_text"] is not None
    assert sig["fallback_text"] is None
    payload = {"factor_signals": [sig]}
    line = render_ml_baseline_evidence_bullet(payload)
    assert line is not None
    assert JUDGMENT_LABEL in line


def test_factor_signal_unavailable_for_missing_report(tmp_path: Path):
    snap = build_ml_baseline_evidence_snapshot(report_path=tmp_path / "missing.json")
    sig = build_ml_baseline_evidence_factor_signal(
        snap, asof_iso="2026-06-11T00:00:00Z"
    )
    assert sig is not None
    assert sig["is_available"] is False
    assert sig["fallback_text"] is not None


# ─── draft 통합 — generate_draft_from_holdings 흐름 ──────────────────


def test_draft_payload_includes_ml_baseline_evidence_snapshot(
    tmp_path: Path, monkeypatch
):
    """generate_draft_from_holdings 이 ml_baseline_evidence_snapshot 키를
    draft_payload 에 채워야 한다 (AC-2).
    """
    from app import draft as draft_mod
    from app.holdings import Holding

    # report 가 존재하는 경로로 우회 — BASELINE_REPORT_PATH monkeypatch.
    report_file = tmp_path / "ml_baseline_v0_report_latest.json"
    report_file.write_text(json.dumps(_make_ok_report()), encoding="utf-8")
    monkeypatch.setattr(
        "app.ml_baseline_evidence.BASELINE_REPORT_PATH", report_file, raising=False
    )

    # store.save / 외부 side effect 차단 — Run 만 검사.
    monkeypatch.setattr(draft_mod.store, "save", lambda run: None)

    holdings = [
        Holding(ticker="069500", name="KODEX 200", quantity=10, avg_buy_price=30000.0)
    ]
    run = draft_mod.generate_draft_from_holdings(holdings, market_quotes={})
    payload = run.draft_payload
    assert payload is not None
    snap = payload.get("ml_baseline_evidence_snapshot")
    assert isinstance(snap, dict)
    # AC-2 필수 키.
    assert snap["status"] in ("ok", "warn", "stale", "unavailable", "error")
    assert "candidate_summary" in snap
    assert "risk_summary" in snap
    assert "leakage_summary" in snap
    assert "limitations" in snap
    assert "external_context_checklist" in snap

    # AC-3/4/5/6 — factor_signals 에 ml_baseline_evidence scope entry 1건.
    fs = payload.get("factor_signals") or []
    scopes = [s.get("scope") for s in fs if isinstance(s, dict)]
    assert "ml_baseline_evidence" in scopes

    # AC-8 — 기존 evidence 유지.
    assert "holdings_market_evidence_snapshot" in payload


def test_draft_does_not_fail_when_report_missing(tmp_path: Path, monkeypatch):
    """report 부재 시에도 draft 생성은 실패하지 않는다 (AC-7)."""
    from app import draft as draft_mod
    from app.holdings import Holding

    monkeypatch.setattr(
        "app.ml_baseline_evidence.BASELINE_REPORT_PATH",
        tmp_path / "missing.json",
        raising=False,
    )
    monkeypatch.setattr(draft_mod.store, "save", lambda run: None)

    holdings = [
        Holding(ticker="069500", name="KODEX 200", quantity=10, avg_buy_price=30000.0)
    ]
    run = draft_mod.generate_draft_from_holdings(holdings, market_quotes={})
    assert run.status == "PENDING_APPROVAL"
    assert run.draft_payload is not None
    snap = run.draft_payload.get("ml_baseline_evidence_snapshot")
    assert snap["status"] == "unavailable"


def test_draft_message_includes_ml_baseline_bullet(tmp_path: Path, monkeypatch):
    """draft_message build 시 [판단 사유] 섹션에 ML baseline evidence 1줄 포함."""
    from app import draft as draft_mod
    from app.holdings import Holding

    report_file = tmp_path / "ml_baseline_v0_report_latest.json"
    report_file.write_text(json.dumps(_make_ok_report()), encoding="utf-8")
    monkeypatch.setattr(
        "app.ml_baseline_evidence.BASELINE_REPORT_PATH", report_file, raising=False
    )
    monkeypatch.setattr(draft_mod.store, "save", lambda run: None)

    holdings = [
        Holding(ticker="069500", name="KODEX 200", quantity=10, avg_buy_price=30000.0)
    ]
    run = draft_mod.generate_draft_from_holdings(holdings, market_quotes={})
    text = run.message_text or ""
    assert JUDGMENT_LABEL in text
    # ML baseline evidence bullet 줄 자체에 금지 문구가 들어가면 안 된다 (AC-3/4).
    # 기존 holdings 안내 note ("매수/매도 의견이 아닙니다") 는 본 STEP 의 범위 밖.
    ml_lines = [ln for ln in text.split("\n") if JUDGMENT_LABEL in ln]
    assert ml_lines, "ML baseline bullet 줄이 메시지에 없음"
    for ml_line in ml_lines:
        for w in PROHIBITED_WORDS:
            assert (
                w not in ml_line
            ), f"ML baseline bullet 줄에 금지 문구 '{w}' 포함: {ml_line}"


def test_default_baseline_report_path_constant():
    """app.api_ml_baseline.BASELINE_REPORT_PATH 와 동일 경로."""
    from app import api_ml_baseline

    assert BASELINE_REPORT_PATH == api_ml_baseline.BASELINE_REPORT_PATH


# ─── AI Sessions / Decision Evidence 통합 (FIX r2) ─────────────────


def test_ai_sessions_record_stores_ml_baseline_evidence_snapshot(tmp_path: Path):
    """AC-2 — AI Sessions / Decision Evidence 저장 경로에 ml_baseline_evidence_
    snapshot 이 받아들여지고 그대로 조회된다.
    """
    from app.decision_evidence_store import get_record, insert_record

    db = tmp_path / "decision.sqlite"
    snap = {
        "status": "ok",
        "report_status": "ok",
        "candidate_summary": {"evaluated_days": 40},
        "risk_summary": {
            "high_risk_group_future_drawdown": {"10d": -0.0809},
        },
        "leakage_summary": {
            "future_data_leakage_detected": False,
            "tail_excluded": True,
            "time_order_preserved": True,
        },
        "limitations": ["평가 기간이 짧아 장기 안정성 검증은 아닙니다."],
        "external_context_checklist": [
            "CNN Fear & Greed 현재 수준",
            "원유 가격 급등 여부",
        ],
    }
    saved = insert_record(
        asof="2026-06-11",
        source_screen="market_discovery",
        filters={
            "exclude_inverse": False,
            "exclude_leveraged": False,
            "exclude_synthetic": False,
            "exclude_futures": False,
        },
        candidate_snapshot=[{"ticker": "069500", "name": "KODEX 200"}],
        question_text="ML evidence 통합 점검",
        gpt_answer_text="ok",
        gemini_answer_text="",
        claude_answer_text="",
        user_memo="",
        user_verdict="hold",
        next_checks=[],
        linked_market_refresh_id=None,
        ml_baseline_evidence_snapshot=snap,
        db_path=db,
    )
    fetched = get_record(saved["id"], db_path=db)
    assert fetched is not None
    got = fetched["ml_baseline_evidence_snapshot"]
    assert got["status"] == "ok"
    assert got["candidate_summary"]["evaluated_days"] == 40
    assert got["leakage_summary"]["future_data_leakage_detected"] is False


def test_evidence_snapshot_api_returns_normalized_shape(tmp_path: Path, monkeypatch):
    """FIX r3 — GET /ml/baseline-v0/evidence-snapshot 가 GenerateDraft 와 동일
    shape 의 정규화 snapshot 을 반환. AI Sessions fallback 이 본 API 를 사용.
    """
    from fastapi.testclient import TestClient

    from app.api import app

    p = tmp_path / "report.json"
    p.write_text(json.dumps(_make_ok_report()), encoding="utf-8")
    monkeypatch.setattr(
        "app.ml_baseline_evidence.BASELINE_REPORT_PATH", p, raising=False
    )

    client = TestClient(app)
    resp = client.get("/ml/baseline-v0/evidence-snapshot")
    assert resp.status_code == 200
    body = resp.json()
    # GenerateDraft snapshot 과 동일한 top-level 키.
    expected_keys = {
        "status",
        "report_status",
        "report_path",
        "report_generated_at",
        "feature_asof_range",
        "evaluated_asof_range",
        "candidate_summary",
        "risk_summary",
        "leakage_summary",
        "limitations",
        "external_context_checklist",
        "message",
    }
    assert expected_keys <= set(body.keys())
    # 정규화 의미: candidate / risk / leakage 필드가 dict 로 채워짐 (raw report 아님).
    assert body["candidate_summary"]["evaluated_days"] == 40
    assert body["risk_summary"]["high_risk_group_future_drawdown"][
        "10d"
    ] == pytest.approx(-0.0809)
    assert body["leakage_summary"]["future_data_leakage_detected"] is False
    assert isinstance(body["external_context_checklist"], list)
    assert len(body["external_context_checklist"]) == 7


def test_evidence_snapshot_api_unavailable_when_report_missing(
    tmp_path: Path, monkeypatch
):
    """FIX r3 — report 부재 시에도 200 + status='unavailable' (조용히 빠지지 않음)."""
    from fastapi.testclient import TestClient

    from app.api import app

    monkeypatch.setattr(
        "app.ml_baseline_evidence.BASELINE_REPORT_PATH",
        tmp_path / "missing.json",
        raising=False,
    )
    client = TestClient(app)
    resp = client.get("/ml/baseline-v0/evidence-snapshot")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "unavailable"
    assert body["report_status"] == "unavailable"
    # 정규화 shape 유지.
    assert isinstance(body["limitations"], list) and len(body["limitations"]) >= 1
    assert isinstance(body["external_context_checklist"], list)


def test_decision_sessions_api_accepts_ml_baseline_evidence_snapshot(
    tmp_path: Path, monkeypatch
):
    """POST /decision/sessions 가 ml_baseline_evidence_snapshot 을 수용 + GET 응답에 그대로 반환."""
    from fastapi.testclient import TestClient

    from app import api_decision_sessions
    from app.api import app

    db = tmp_path / "decision_api.sqlite"
    monkeypatch.setattr(api_decision_sessions, "DEFAULT_DB_PATH", db, raising=False)

    snap = {
        "status": "ok",
        "candidate_summary": {"evaluated_days": 40},
        "external_context_checklist": ["CNN Fear & Greed 현재 수준"],
    }
    body = {
        "asof": "2026-06-11",
        "source_screen": "market_discovery",
        "filters": {
            "exclude_inverse": False,
            "exclude_leveraged": False,
            "exclude_synthetic": False,
            "exclude_futures": False,
        },
        "candidate_snapshot": [{"ticker": "069500", "name": "KODEX 200"}],
        "question_text": "evidence 통합",
        "gpt_answer_text": "ok",
        "user_verdict": "hold",
        "next_checks": [],
        "ml_baseline_evidence_snapshot": snap,
    }
    client = TestClient(app)
    post_resp = client.post("/decision/sessions", json=body)
    assert post_resp.status_code == 200, post_resp.text
    rec_id = post_resp.json()["id"]

    get_resp = client.get(f"/decision/sessions/{rec_id}")
    assert get_resp.status_code == 200
    record = get_resp.json()["record"]
    assert record["ml_baseline_evidence_snapshot"]["status"] == "ok"
    assert (
        record["ml_baseline_evidence_snapshot"]["candidate_summary"]["evaluated_days"]
        == 40
    )
