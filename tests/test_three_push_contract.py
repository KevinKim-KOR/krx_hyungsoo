"""POC2 3-PUSH Message Contract 정렬 — 3층 테스트 (2026-06-11).

지시문 §14 AC-1 ~ AC-12 검증. 3층 구조 (사용자 결정 (a)):
  Layer 1: builder 단위 — 금지 문구 0건 / 허용 문구 포함 / 길이 안전.
  Layer 2: draft 통합 — Run.push_kind / message_text 박힘 / draft_payload 메타.
  Layer 3: API 응답 — POST /runs/generate-{market-briefing,spike-alert} 가
                       PENDING_APPROVAL Run 반환 + push_kind 전파.

원칙 (지시문 §5 / §12):
- 외부 source 호출 / Telegram 직접 호출 / 자동 발송 0건.
- AC-11: 테스트 중 실제 Telegram 발송 0건 — delivery 는 호출하지 않는다.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import draft as draft_mod
from app.api import app
from app.message_market_briefing import (
    PUSH_KIND as MARKET_BRIEFING_KIND,
)
from app.message_market_briefing import (
    build_market_briefing_message,
)
from app.message_spike_alert import (
    PUSH_KIND as SPIKE_ALERT_KIND,
)
from app.message_spike_alert import (
    build_spike_alert_message,
)
from app.models import Run

# 지시문 §4.2 / §4.3 / §4.4 + §10.10 금지 문구.
# **중요**: 기존 frontend 정책 / 기존 falling ETF bullet 처럼 부정문 ("매수/매도
# 지시가 아닙니다") 은 허용 — 사용자 주의를 위한 중립 안내. 본 substring 검사는
# 그 부정문이 끝나는 NEUTRAL_NOTE 라인 **앞** (실제 콘텐츠 본문) 에 매수/매도 등의
# 강한 동사 표현이 들어가면 실패. 동사 결합 형태로 정의해 부정 안내문은 통과
# 시키되, 실제 매매 지시는 잡는다.
PROHIBITED_WORDS = [
    "매수 후보",
    "매도 후보",
    "지금 매수",
    "지금 매도",
    "매수해야",
    "매도해야",
    "교체 권유",
    "교체 필요",
    "현금비중 확대",
    "현금비중 조절",
    "조정장 확정",
    "상승장 확정",
    "단기 대응 필요",
    "위험 알림 확정",
    "지금 행동",
    "추천 종목",
]

# 안전 (raw secret 노출 0건).
SECRET_TOKENS = ["chat_id", "bot_token", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]


def _make_ok_baseline_snapshot() -> dict:
    return {
        "status": "ok",
        "report_status": "ok",
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
        "candidate_summary": {
            "status": "ok",
            "evaluated_days": 40,
            "top_group_avg_future_return": {"20d": 0.1351},
        },
        "risk_summary": {
            "status": "ok",
            "evaluated_days": 40,
            "high_risk_group_future_drawdown": {"5d": -0.0583, "10d": -0.0809},
            "low_risk_group_future_drawdown": {"5d": -0.0108, "10d": -0.0340},
        },
        "leakage_summary": {
            "future_data_leakage_detected": False,
            "tail_excluded": True,
            "time_order_preserved": True,
        },
        "limitations": ["평가 기간이 짧을 수 있어 장기 안정성 검증은 아닙니다."],
        "external_context_checklist": [
            "CNN Fear & Greed 현재 수준",
            "VIX 또는 VKOSPI 유사 변동성 지표",
            "원유 가격 급등 여부",
            "USD/KRW 환율 급등 여부",
            "미국장 / 미국 선물 흐름",
            "지정학 이벤트",
            "한국장 영향 업종",
        ],
    }


def _make_topn_payload(spike: bool = True) -> dict:
    items = [
        {"ticker": "266390", "name": "KODEX 경기소비재", "return_pct": 18.42},
        {"ticker": "360750", "name": "TIGER 미국S&P500", "return_pct": 12.10},
        {"ticker": "069500", "name": "KODEX 200", "return_pct": 3.50},
        {"ticker": "229200", "name": "KODEX 코스닥150", "return_pct": -6.40},
        {"ticker": "133690", "name": "TIGER 미국나스닥100", "return_pct": -11.20},
    ]
    if not spike:
        # 임계 미만으로 모두 줄여 spike 섹션이 비도록 만든다.
        items = [{**it, "return_pct": it["return_pct"] / 10.0} for it in items]
    return {"basis": "1m", "asof": "2026-06-11", "items": items}


def _make_universe_artifact_with_falling() -> dict:
    return {
        "asof": "2026-06-11",
        "summary": {
            "refresh_status": "ok",
            "falling_threshold_pct": -10.0,
            "falling_candidate": {
                "ticker": "133690",
                "name": "TIGER 미국나스닥100",
                "candidate_id": "133690-1m",
                "score_result": {"score_value": -12.5},
                "price_history_basis": {"latest_date": "2026-06-10"},
            },
        },
    }


# ─── Layer 1: builder 단위 ─────────────────────────────────────────


def test_push1_builder_includes_required_sections_when_evidence_available():
    """PUSH-1 builder 가 시장 내부 신호 + 위험 패턴 참고 + 외부 변수 checklist
    3섹션을 포함한다 (AC-4)."""
    text = build_market_briefing_message(
        asof_iso="2026-06-11T13:00:00+09:00",
        ml_baseline_snapshot=_make_ok_baseline_snapshot(),
        topn_payload=_make_topn_payload(),
    )
    assert "시장 흐름 브리핑" in text
    # PUSH 사용자 표현 정리 STEP (2026-06-20): 섹션 헤더가 사용자 표시명으로 정렬.
    assert "[ETF 후보 흐름]" in text
    assert "[위험 참고 데이터]" in text
    assert "[별도 확인 필요 외부 변수]" in text


def test_push1_builder_omits_news_section_when_unavailable():
    """뉴스 source 가 없을 때 뉴스 섹션 자체 생략 — "unavailable" 보여주기 X
    (AC-4 / §4.2)."""
    text = build_market_briefing_message(
        asof_iso="2026-06-11T13:00:00+09:00",
        ml_baseline_snapshot=None,
        topn_payload=_make_topn_payload(),
    )
    assert "뉴스 수집 실패" not in text
    assert "뉴스 unavailable" not in text
    # 위험 참고 데이터 섹션은 evidence None 이므로 생략되어야 한다.
    assert "[위험 참고 데이터]" not in text


def test_push1_builder_no_prohibited_wording():
    """AC-10 / §4.2 — 매수/매도/현금비중/조정장 확정 등 금지 문구 0건."""
    text = build_market_briefing_message(
        asof_iso="2026-06-11T13:00:00+09:00",
        ml_baseline_snapshot=_make_ok_baseline_snapshot(),
        topn_payload=_make_topn_payload(),
    )
    for w in PROHIBITED_WORDS:
        assert w not in text, f"PUSH-1 에 금지 문구 '{w}' 포함: {text!r}"
    for s in SECRET_TOKENS:
        assert s not in text, f"PUSH-1 에 민감 토큰 '{s}' 노출"


def test_push1_builder_length_safe():
    """길이 정책 — MAX_LENGTH_CHARS 이내 (§9 / §10 message_text 안전)."""
    text = build_market_briefing_message(
        asof_iso="2026-06-11T13:00:00+09:00",
        ml_baseline_snapshot=_make_ok_baseline_snapshot(),
        topn_payload=_make_topn_payload(),
    )
    assert len(text) <= 3500


def test_push1_builder_no_raw_json():
    """AC-10 — message_text 에 raw JSON 본문 노출 X."""
    text = build_market_briefing_message(
        asof_iso="2026-06-11T13:00:00+09:00",
        ml_baseline_snapshot=_make_ok_baseline_snapshot(),
        topn_payload=_make_topn_payload(),
    )
    # JSON 마커 { ... } 가 dict 형태로 박혀 있으면 안 된다.
    assert '"status": "ok"' not in text
    assert "candidate_summary" not in text


def test_push3_builder_includes_topn_spike_when_threshold_met():
    """PUSH-3 builder 가 ETF universe 변동성 확대 섹션 포함 (AC-6)."""
    text = build_spike_alert_message(
        asof_iso="2026-06-11T13:00:00+09:00",
        topn_payload=_make_topn_payload(spike=True),
        universe_artifact=_make_universe_artifact_with_falling(),
    )
    # PUSH 사용자 표현 정리 STEP (2026-06-20): title 이 '[급등락·상승 관찰 신호]' 로 변경.
    assert "급등락" in text
    assert "[ETF 변동성 확대 관찰]" in text
    # 18.42% 상승 / -11.20% 하락이 모두 임계 5% 이상이므로 포함.
    assert "+18.42%" in text or "+18.42" in text
    assert "-11.20%" in text or "-11.20" in text


def test_push3_builder_reuses_existing_falling_signal():
    """기존 universe_momentum_latest.json 의 falling_candidate 를 재사용 — 새
    source 추가 0건 (§4.4)."""
    text = build_spike_alert_message(
        asof_iso="2026-06-11T13:00:00+09:00",
        topn_payload=_make_topn_payload(),
        universe_artifact=_make_universe_artifact_with_falling(),
    )
    assert "급락 ETF 주의 신호" in text
    assert "TIGER 미국나스닥100" in text


def test_push3_builder_no_prohibited_wording():
    """AC-10 / §4.4 — 매수/매도/단기 대응/위험 알림 확정 0건."""
    text = build_spike_alert_message(
        asof_iso="2026-06-11T13:00:00+09:00",
        topn_payload=_make_topn_payload(),
        universe_artifact=_make_universe_artifact_with_falling(),
    )
    for w in PROHIBITED_WORDS:
        assert w not in text, f"PUSH-3 에 금지 문구 '{w}' 포함: {text!r}"
    for s in SECRET_TOKENS:
        assert s not in text


def test_push3_builder_empty_universe_keeps_safe_default():
    """topn / artifact 모두 비어도 builder 가 raise 하지 않고 안전한 기본 메시지
    생성 (생성 실패가 운영을 막지 않는다)."""
    text = build_spike_alert_message(
        asof_iso="2026-06-11T13:00:00+09:00",
        topn_payload=None,
        universe_artifact=None,
    )
    assert "급등락" in text
    # 빈 universe 도 본문 비어있지 않게 (사용자 중심 unavailable 메시지로 fallback).
    assert "관찰" in text or "임계" in text or "데이터" in text


# ─── Layer 2: draft 통합 ───────────────────────────────────────────


def test_market_briefing_draft_creates_pending_run_with_push_kind(monkeypatch):
    """generate_market_briefing_draft 가 Run.push_kind="market_briefing" +
    PENDING_APPROVAL 로 저장된 Run 을 반환 (AC-1 / AC-7 / AC-8)."""
    # store.save 차단 — 디스크 사이드이펙트 0건.
    monkeypatch.setattr(draft_mod.store, "save", lambda run: None)
    run = draft_mod.generate_market_briefing_draft(
        ml_baseline_snapshot=_make_ok_baseline_snapshot(),
        topn_payload=_make_topn_payload(),
    )
    assert isinstance(run, Run)
    assert run.status == "PENDING_APPROVAL"
    assert run.push_kind == MARKET_BRIEFING_KIND
    assert isinstance(run.message_text, str) and "시장 흐름 브리핑" in run.message_text
    # draft_payload 에 push_kind 메타가 박혀있어야 한다.
    assert run.draft_payload is not None
    assert run.draft_payload.get("push_kind") == MARKET_BRIEFING_KIND
    # recommendations 키 (frontend 호환) 유지.
    assert "recommendations" in run.draft_payload


def test_spike_alert_draft_creates_pending_run_with_push_kind(monkeypatch):
    """generate_spike_alert_draft 가 Run.push_kind="spike_or_falling_alert" 로
    PENDING_APPROVAL Run 반환 (AC-6)."""
    monkeypatch.setattr(draft_mod.store, "save", lambda run: None)
    run = draft_mod.generate_spike_alert_draft(
        topn_payload=_make_topn_payload(),
        universe_artifact=_make_universe_artifact_with_falling(),
    )
    assert run.status == "PENDING_APPROVAL"
    assert run.push_kind == SPIKE_ALERT_KIND
    assert isinstance(run.message_text, str) and "급등락" in run.message_text
    assert run.draft_payload is not None
    assert run.draft_payload.get("push_kind") == SPIKE_ALERT_KIND


def test_holdings_draft_gets_push_kind_holdings_briefing(monkeypatch):
    """기존 generate_draft_from_holdings 가 PUSH-2 로 재정의 — push_kind 자동
    부여 (AC-1)."""
    from app.holdings import Holding

    monkeypatch.setattr(draft_mod.store, "save", lambda run: None)
    holdings = [
        Holding(ticker="069500", name="KODEX 200", quantity=10, avg_buy_price=30000.0)
    ]
    run = draft_mod.generate_draft_from_holdings(holdings, market_quotes={})
    assert run.push_kind == "holdings_briefing"
    # 기존 message_text / draft_payload 흐름은 그대로 유지.
    assert run.status == "PENDING_APPROVAL"


# ─── Layer 3: API 응답 ─────────────────────────────────────────────


def _isolate_state_dir(tmp_path: Path, monkeypatch) -> None:
    """store.save 가 디스크에 쓰는 경로를 tmp 로 격리 (테스트 간 누수 방지)."""
    from app import store

    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(store, "RUNS_DIR", runs_dir, raising=False)


def test_generate_market_briefing_via_unified_endpoint(tmp_path: Path, monkeypatch):
    """FIX r2 (설계자 수용) — POST /runs/generate 의 input_data.push_kind 분기로
    PUSH-1 생성. 별도 PUSH endpoint 신설 0건 (§3 / §11 준수)."""
    _isolate_state_dir(tmp_path, monkeypatch)
    client = TestClient(app)
    resp = client.post(
        "/runs/generate",
        json={"input_data": {"push_kind": "market_briefing"}},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "PENDING_APPROVAL"
    assert body["push_kind"] == MARKET_BRIEFING_KIND
    assert isinstance(body["message_text"], str) and len(body["message_text"]) > 0
    # frontend 가 본문을 조립하지 않음을 확인 — message_text 가 backend 단일 소스.
    assert "시장 흐름 브리핑" in body["message_text"]
    # 금지 문구 / 민감 토큰 0건.
    for w in PROHIBITED_WORDS:
        assert w not in body["message_text"]
    for s in SECRET_TOKENS:
        assert s not in body["message_text"]


def test_generate_spike_alert_via_unified_endpoint(tmp_path: Path, monkeypatch):
    """FIX r2 (설계자 수용) — POST /runs/generate 의 input_data.push_kind 분기로
    PUSH-3 생성. 별도 PUSH endpoint 신설 0건."""
    _isolate_state_dir(tmp_path, monkeypatch)
    client = TestClient(app)
    resp = client.post(
        "/runs/generate",
        json={"input_data": {"push_kind": "spike_or_falling_alert"}},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "PENDING_APPROVAL"
    assert body["push_kind"] == SPIKE_ALERT_KIND
    assert isinstance(body["message_text"], str) and len(body["message_text"]) > 0
    assert "급등락" in body["message_text"]
    for w in PROHIBITED_WORDS:
        assert w not in body["message_text"]


def test_no_dedicated_push_endpoints_exist(tmp_path: Path, monkeypatch):
    """FIX r2 (A-1 / A-4 검증자 수용) — 기존 신규 PUSH endpoint 가 제거되어
    POST 가 등록되어 있지 않음. 별도 PUSH API 신설 금지선 (§3 / §11) 준수 직접
    검증. FastAPI 는 등록되지 않은 path 에 대해 404 또는 405 반환 (등록된
    path 가 다른 method 만 가질 때는 405). 본 검증은 OK status 가 아닌 것만
    확인."""
    _isolate_state_dir(tmp_path, monkeypatch)
    client = TestClient(app)
    for path in (
        "/runs/generate-market-briefing",
        "/runs/generate-spike-alert",
    ):
        resp = client.post(path)
        assert resp.status_code in (
            404,
            405,
        ), f"{path} 가 여전히 활성 — FIX r2 미적용 (status={resp.status_code})"


def test_unified_generate_does_not_trigger_telegram_send(tmp_path: Path, monkeypatch):
    """AC-3 / AC-7 / AC-11 — input_data.push_kind 분기 경로도 delivery 를 호출
    하지 않는다. 인간 승인 전 발송 차단 직접 검증."""
    _isolate_state_dir(tmp_path, monkeypatch)

    def _boom(*args, **kwargs):
        raise AssertionError("승인 전에 delivery.deliver 가 호출되었습니다")

    monkeypatch.setattr("app.delivery.deliver", _boom, raising=False)
    client = TestClient(app)
    r1 = client.post(
        "/runs/generate",
        json={"input_data": {"push_kind": "market_briefing"}},
    )
    r2 = client.post(
        "/runs/generate",
        json={"input_data": {"push_kind": "spike_or_falling_alert"}},
    )
    assert r1.status_code == 200 and r1.json()["status"] == "PENDING_APPROVAL"
    assert r2.status_code == 200 and r2.json()["status"] == "PENDING_APPROVAL"


def test_generate_without_push_kind_falls_back_to_sample(tmp_path: Path, monkeypatch):
    """기존 sample_draft 흐름 (POC1 호환) 이 깨지지 않는다 — push_kind 가 없거나
    알 수 없는 값이면 sample_draft 로 위임."""
    _isolate_state_dir(tmp_path, monkeypatch)
    client = TestClient(app)
    # sample_draft 가 받는 valid input 은 모듈 contract 에 정의된 키를 가져야
    # 한다 — 본 테스트는 분기 분류만 확인하므로 빈 dict 로 호출해 FAILED 가
    # 정상 나오는지 본다 (POC1 "GenerateDraft 실패 → FAILED 단일 규칙").
    resp = client.post("/runs/generate", json={"input_data": {}})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "FAILED"
    # push_kind 가 없으므로 None.
    assert body.get("push_kind") is None


# ─── Run 모델 / handoff 계약 보존 ────────────────────────────────


def test_run_from_dict_back_compatible_with_legacy_runs():
    """과거 push_kind 가 없던 run 파일도 역직렬화 — push_kind=None (AC-12)."""
    legacy = {
        "run_id": "run_legacy",
        "asof": "2026-05-01T00:00:00Z",
        "status": "COMPLETED",
        "draft_payload": {"title": "legacy"},
    }
    r = Run.from_dict(legacy)
    assert r.push_kind is None
    assert r.message_text is None
    assert r.status == "COMPLETED"


def test_run_to_dict_includes_push_kind_when_set():
    """신규 run 의 to_dict 에 push_kind 가 포함되어 store / handoff 가 의미를
    잃지 않는다."""
    r = Run(
        run_id="run_test",
        asof="2026-06-11T00:00:00Z",
        status="PENDING_APPROVAL",
        draft_payload={"title": "test", "recommendations": []},
        message_text="hello",
        push_kind="market_briefing",
    )
    d = r.to_dict()
    assert d["push_kind"] == "market_briefing"
    assert d["message_text"] == "hello"
    # roundtrip 안정성.
    r2 = Run.from_dict(d)
    assert r2.push_kind == "market_briefing"


# ─── delivery fallback 안전 ────────────────────────────────────────


def test_delivery_refuses_holdings_fallback_for_push1_without_message_text(
    monkeypatch,
):
    """AC-2 / AC-10 / §10.10 — PUSH-1 / PUSH-3 run 에 message_text 가 누락된
    이상 상태에서 delivery 가 holdings builder 로 fallback 하지 않고 명시 에러로
    떨어진다 (raw recommendations 노출 금지).

    conftest 의 autouse _stub_oci_calls 가 delivery.deliver 를 lambda 로 교체
    하므로, 본 테스트에서는 진짜 함수 참조를 미리 보관 후 직접 호출한다.
    """
    from app import delivery

    real_deliver = (
        delivery.deliver.__wrapped__
        if hasattr(delivery.deliver, "__wrapped__")
        else None
    )
    # autouse stub 이 lambda 로 덮은 상태에서 진짜 함수에 접근하려면 module 의
    # 원본을 직접 reload 해야 한다. 가장 안전한 방법은 dotted path 로 가져오기.
    import importlib

    delivery_mod = importlib.reload(importlib.import_module("app.delivery"))
    # autouse fixture 를 다시 적용해 SCP / SSH 차단은 유지.
    monkeypatch.setattr("app.delivery._ssh_target", lambda: "user@host", raising=False)
    monkeypatch.setattr(
        "app.delivery._remote_inbox", lambda: "/tmp/inbox", raising=False
    )
    monkeypatch.setattr("app.delivery._scp_upload", lambda *a, **k: None, raising=False)
    _ = real_deliver  # noqa: F841 (참고용; reload 한 모듈을 사용)

    bad_run = Run(
        run_id="run_bad",
        asof="2026-06-11T00:00:00Z",
        status="DELIVERING",
        draft_payload={"title": "PUSH-1 broken", "recommendations": []},
        message_text=None,
        push_kind="market_briefing",
    )
    with pytest.raises(delivery_mod.DeliveryError) as ei:
        delivery_mod.deliver(bad_run)
    # raise 메시지에 push_kind 가 명시되어야 한다 — holdings fallback 으로 raw
    # recommendations 가 나가지 않음을 보장하는 핵심 검증.
    assert "market_briefing" in str(ei.value)
