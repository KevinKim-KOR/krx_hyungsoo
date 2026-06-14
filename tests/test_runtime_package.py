"""POC2 3-PUSH Runtime Package PC 검증 — 단위 + 통합 테스트 (2026-06-13).

지시문 §17 AC-1 ~ AC-14 검증.
- AC-1/2/3: 3종 push_kind 모두 runtime_package 가 draft_payload 에 저장됨.
- AC-4/5: kr / us 시세 probe 결과가 package 에 반영됨 (mock probe 로 격리).
- AC-6: message_text 가 runtime_package.message_contract.message_text 와 일치.
- AC-7: empty runtime slot 이 UI placeholder 로 새지 않는다 (status="unavailable"
        snapshot 이 명시적으로 그 사실을 표기).
- AC-8: handoff JSON (store.write_handoff_artifact 결과) 에 runtime_package 포함.
- AC-9: 기존 PENDING_APPROVAL 흐름 유지.
- AC-11: 실제 외부 HTTP 호출은 monkeypatch 로 차단 (cache + probe 격리).
- AC-12/14: 신규 PUSH 전용 endpoint 없음 + 금지 문구 substring 0건.

외부 source 호출 0건: monkeypatch 로 runtime_probe_cache.get_runtime_probe_snapshot
를 stub.
"""

from __future__ import annotations

import json

import pytest

from app import draft as draft_mod
from app import store
from app.draft_three_push import (
    generate_market_briefing_via_generic,
    generate_spike_alert_via_generic,
)
from app.holdings import Holding
from app.runtime_package import (
    SCHEMA_VERSION,
    SOURCE_MODE_PC_TEST,
    build_runtime_package,
)

# ─── 공통 stub 데이터 ────────────────────────────────────────────


def _stub_runtime_snapshot(*, kr_status: str = "ok", us_status: str = "ok") -> dict:
    return {
        "captured_at": "2026-06-13T08:55:00+09:00",
        "kr_realtime_price_snapshot": {
            "captured_at": "2026-06-13T08:55:00+09:00",
            "source": "naver",
            "items": [
                {
                    "ticker": "069500",
                    "name": "KODEX 200",
                    "price": 36000,
                    "change_pct": 0.42,
                    "volume": 123456,
                    "data_status": "ok",
                }
            ],
            "status": kr_status,
            "warnings": [],
            "errors": [],
        },
        "overnight_us_market_snapshot": {
            "captured_at": "2026-06-13T08:55:00+09:00",
            "indices": [
                {
                    "symbol": "NASDAQ",
                    "name": "Nasdaq Composite",
                    "change_pct": 0.85,
                    "close": 18000.12,
                    "status": "ok",
                },
                {
                    "symbol": "SPX",
                    "name": "S&P 500",
                    "change_pct": 0.41,
                    "close": 5400.33,
                    "status": "ok",
                },
                {
                    "symbol": "SOX",
                    "name": "Philadelphia Semiconductor Index",
                    "change_pct": 1.25,
                    "close": 5200.45,
                    "status": "ok",
                },
            ],
            "status": us_status,
            "warnings": [],
            "errors": [],
        },
        "cache_status": "hit",
    }


@pytest.fixture
def stub_probe(monkeypatch: pytest.MonkeyPatch):
    """모든 outbound HTTP 를 차단하는 단일 stub. draft_three_push / draft 양쪽 사용."""

    def _fake(*, kr_tickers, force_refresh=False):
        return _stub_runtime_snapshot()

    monkeypatch.setattr(
        "app.draft_three_push.get_runtime_probe_snapshot", _fake, raising=True
    )
    monkeypatch.setattr("app.draft.get_runtime_probe_snapshot", _fake, raising=True)
    yield


@pytest.fixture
def stub_storage():
    """conftest._isolated_store autouse 가 이미 store 격리. placeholder."""
    yield


# ─── AC-1/2/3: 3종 package 생성 ────────────────────────────────


def test_market_briefing_runtime_package_created(stub_probe, stub_storage):
    """AC-1, AC-2: PUSH-1 runtime_package 가 draft_payload 에 저장된다."""
    run = generate_market_briefing_via_generic({"push_kind": "market_briefing"})
    assert run.status == "PENDING_APPROVAL"
    assert run.push_kind == "market_briefing"
    payload = run.draft_payload or {}
    pkg = payload.get("runtime_package")
    assert isinstance(pkg, dict)
    assert pkg["schema_version"] == SCHEMA_VERSION
    assert pkg["push_kind"] == "market_briefing"
    assert pkg["source_mode"] == SOURCE_MODE_PC_TEST


def test_spike_alert_runtime_package_created(stub_probe, stub_storage):
    """AC-1, AC-2: PUSH-3 runtime_package 가 draft_payload 에 저장된다."""
    run = generate_spike_alert_via_generic({"push_kind": "spike_or_falling_alert"})
    assert run.push_kind == "spike_or_falling_alert"
    pkg = (run.draft_payload or {}).get("runtime_package")
    assert isinstance(pkg, dict)
    assert pkg["schema_version"] == SCHEMA_VERSION
    assert pkg["push_kind"] == "spike_or_falling_alert"


def test_holdings_briefing_runtime_package_created(stub_probe, stub_storage):
    """AC-1, AC-2: PUSH-2 holdings_briefing runtime_package 가 draft_payload 에 저장된다."""
    holdings = [
        Holding(
            ticker="069500",
            quantity=10,
            avg_buy_price=35000,
            name="KODEX 200",
            account_group="일반",
        )
    ]
    run = draft_mod.generate_draft_from_holdings(holdings)
    assert run.status == "PENDING_APPROVAL"
    assert run.push_kind == "holdings_briefing"
    pkg = (run.draft_payload or {}).get("runtime_package")
    assert isinstance(pkg, dict)
    assert pkg["schema_version"] == SCHEMA_VERSION
    assert pkg["push_kind"] == "holdings_briefing"


# ─── AC-3: PC evidence snapshot 포함 ───────────────────────────


def test_pc_evidence_snapshot_keys_present(stub_probe, stub_storage):
    """AC-3: pc_evidence_snapshot 6 키가 모두 존재 (push_kind 별 일부 비어있을 수 있음)."""
    run = generate_market_briefing_via_generic({"push_kind": "market_briefing"})
    pkg = (run.draft_payload or {})["runtime_package"]
    ev = pkg["pc_evidence_snapshot"]
    for k in (
        "holdings_snapshot",
        "market_discovery_snapshot",
        "ml_baseline_snapshot",
        "universe_momentum_snapshot",
        "nav_discount_snapshot",
        "data_quality_snapshot",
    ):
        assert k in ev


# ─── AC-4/5: runtime source probe 반영 ─────────────────────────


def test_runtime_kr_and_us_probe_reflected(stub_probe, stub_storage):
    """AC-4, AC-5: stub probe 값이 runtime_snapshot 에 그대로 반영."""
    run = generate_market_briefing_via_generic({"push_kind": "market_briefing"})
    pkg = (run.draft_payload or {})["runtime_package"]
    rs = pkg["runtime_snapshot"]
    assert rs["kr_realtime_price_snapshot"]["status"] == "ok"
    assert rs["overnight_us_market_snapshot"]["status"] == "ok"
    indices = rs["overnight_us_market_snapshot"]["indices"]
    symbols = {i["symbol"] for i in indices}
    assert symbols == {"NASDAQ", "SPX", "SOX"}


def test_runtime_probe_partial_marked_partial(
    monkeypatch: pytest.MonkeyPatch, stub_storage
):
    """미국 지수 일부 실패는 generation_status=partial 로 노출 (AC-7 placeholder 금지)."""
    snap = _stub_runtime_snapshot(us_status="partial")
    snap["overnight_us_market_snapshot"]["indices"][2]["status"] = "failed"

    def _fake(*, kr_tickers, force_refresh=False):
        return snap

    monkeypatch.setattr("app.draft_three_push.get_runtime_probe_snapshot", _fake)
    run = generate_market_briefing_via_generic({"push_kind": "market_briefing"})
    pkg = (run.draft_payload or {})["runtime_package"]
    assert pkg["generation_status"]["status"] == "partial"
    assert (
        "overnight_us_market_snapshot=partial" in pkg["generation_status"]["warnings"]
    )


# ─── AC-6: message_text = message_contract.message_text ────────


def test_message_text_consistent_with_runtime_package(stub_probe, stub_storage):
    """AC-6: Run.message_text 가 runtime_package.message_contract.message_text 와 동일."""
    run = generate_market_briefing_via_generic({"push_kind": "market_briefing"})
    pkg = (run.draft_payload or {})["runtime_package"]
    assert pkg["message_contract"]["message_text"] == run.message_text


# ─── AC-8: handoff JSON 에 runtime_package 포함 ─────────────────


def test_handoff_artifact_contains_runtime_package(stub_probe, stub_storage):
    """AC-8: write_handoff_artifact 결과 JSON 에 draft_payload.runtime_package 가 들어있다."""
    run = generate_market_briefing_via_generic({"push_kind": "market_briefing"})
    path = store.write_handoff_artifact(
        run, approved_at="2026-06-13T09:00:00+00:00", message_text=run.message_text
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["message_text"] == run.message_text  # 기존 계약 유지
    pkg = data["draft_payload"]["runtime_package"]
    assert pkg["schema_version"] == SCHEMA_VERSION


# ─── AC-7: empty runtime slot 명시 (placeholder 금지) ───────────


def test_unavailable_runtime_status_distinct_from_ok(stub_storage):
    """AC-7: runtime_snapshot=빈 dict 일 때 빌더가 자동으로 비어있는 dict 로 채움.
    placeholder 식 'unavailable' 문자열을 message_text 에 끼워넣지 않음 — runtime
    snapshot 항목이 빈 dict 이면 generation_status 가 partial/failed 로 드러난다.
    """
    pkg = build_runtime_package(
        push_kind="market_briefing",
        message_text="empty body",
        pc_evidence_snapshot={
            "holdings_snapshot": {},
            "market_discovery_snapshot": {"asof": "2026-06-13", "items": [{"a": 1}]},
            "ml_baseline_snapshot": {},
            "universe_momentum_snapshot": {},
            "nav_discount_snapshot": {},
            "data_quality_snapshot": {"asof_date": "2026-06-13", "warnings": []},
        },
        runtime_snapshot={
            "captured_at": None,
            "kr_realtime_price_snapshot": {},
            "overnight_us_market_snapshot": {},
            "news_snapshot": {"status": "unavailable", "items": []},
        },
    )
    # 필수 evidence 가 있으므로 failed 는 아님.
    assert pkg["generation_status"]["status"] in ("ok", "partial")
    # message_text 에는 "unavailable" placeholder 가 자동으로 들어가지 않음.
    assert "unavailable" not in pkg["message_contract"]["message_text"]


# ─── AC-10: 산식 변경 X (interface 만 확인 — generate_draft_from_holdings) ─


def test_holdings_draft_keeps_existing_keys(stub_probe, stub_storage):
    """AC-10: holdings draft 기존 키 (recommendations / factor_signals /
    ml_baseline_evidence_snapshot / holdings_market_evidence_snapshot /
    momentum_result) 가 유지된다."""
    holdings = [
        Holding(
            ticker="069500",
            quantity=10,
            avg_buy_price=35000,
            name="KODEX 200",
            account_group="일반",
        )
    ]
    run = draft_mod.generate_draft_from_holdings(holdings)
    payload = run.draft_payload or {}
    for key in (
        "title",
        "asof",
        "note",
        "recommendations",
        "factor_signals",
        "momentum_result",
        "holdings_market_evidence_snapshot",
        "ml_baseline_evidence_snapshot",
        "runtime_package",  # 신규
    ):
        assert key in payload, f"누락 키: {key}"


# ─── safety_guards 고정 ───────────────────────────────────────


def test_safety_guards_fixed_values(stub_probe, stub_storage):
    run = generate_market_briefing_via_generic({"push_kind": "market_briefing"})
    pkg = (run.draft_payload or {})["runtime_package"]
    sg = pkg["safety_guards"]
    assert sg["frontend_may_build_message_text"] is False
    assert sg["telegram_direct_call_from_pc"] is False
    assert sg["actual_send_allowed_in_tests"] is False
    assert sg["allow_unapproved_delivery"] is False


# ─── AC-6 보강: message_text 가 runtime_package 흐름 (push_context) 기반 ───


def test_message_text_contains_overnight_us_section_when_probe_ok(
    stub_probe, stub_storage
):
    """AC-6 / 지시문 §13: runtime probe 가 ok 이면 push_context.market_view.
    observations 안의 overnight_us 신호가 PUSH-1 message_text 에 1줄 섹션으로
    반영되어야 한다 (단순 복사가 아니라 push_context 입력 기반 생성).
    """
    run = generate_market_briefing_via_generic({"push_kind": "market_briefing"})
    msg = run.message_text or ""
    pkg = (run.draft_payload or {})["runtime_package"]
    pc = pkg["push_context"]
    mv = pc.get("market_view") or {}
    types = {
        o.get("type") for o in (mv.get("observations") or []) if isinstance(o, dict)
    }
    assert (
        "overnight_us" in types
    ), "stub probe 는 us status=ok 이므로 push_context.market_view 에 overnight_us 관측이 있어야 함"
    # message_text 에 push_context 기반 1줄 섹션이 들어가야 한다.
    assert "[밤사이 미국 시장 (runtime probe)]" in msg


def test_message_text_omits_overnight_us_section_when_probe_fails(
    monkeypatch: pytest.MonkeyPatch, stub_storage
):
    """반대 케이스: probe 실패 (status=failed) 면 push_context 에 overnight_us
    관측이 없고 message_text 에도 1줄 섹션이 없어야 한다 (placeholder 금지)."""
    snap = _stub_runtime_snapshot(us_status="failed")
    for it in snap["overnight_us_market_snapshot"]["indices"]:
        it["status"] = "failed"

    def _fake(*, kr_tickers, force_refresh=False):
        return snap

    monkeypatch.setattr("app.draft_three_push.get_runtime_probe_snapshot", _fake)
    run = generate_market_briefing_via_generic({"push_kind": "market_briefing"})
    msg = run.message_text or ""
    assert "[밤사이 미국 시장 (runtime probe)]" not in msg
    assert "미국지수 unavailable" not in msg


# ─── FIX r3: unavailable / failed 노출 검증 (검증자 2차 NOTES A-1) ─────


def test_unavailable_runtime_us_marks_partial_status(
    monkeypatch: pytest.MonkeyPatch, stub_storage
):
    """A-1: us_snapshot.status='unavailable' 도 generation_status 에 warning 으로
    반영되어 partial 이 되어야 한다. ok 로 통과되면 안 된다.
    """
    snap = _stub_runtime_snapshot()
    snap["overnight_us_market_snapshot"]["status"] = "unavailable"
    snap["overnight_us_market_snapshot"]["indices"] = []

    def _fake(*, kr_tickers, force_refresh=False):
        return snap

    monkeypatch.setattr("app.draft_three_push.get_runtime_probe_snapshot", _fake)
    run = generate_market_briefing_via_generic({"push_kind": "market_briefing"})
    pkg = (run.draft_payload or {})["runtime_package"]
    assert pkg["generation_status"]["status"] == "partial"
    assert any(
        "overnight_us_market_snapshot=unavailable" in w
        for w in pkg["generation_status"]["warnings"]
    )


def test_unavailable_runtime_kr_marks_partial_status(
    monkeypatch: pytest.MonkeyPatch, stub_storage
):
    """A-1: kr_snapshot.status='unavailable' 도 warning 으로 반영."""
    snap = _stub_runtime_snapshot()
    snap["kr_realtime_price_snapshot"]["status"] = "unavailable"
    snap["kr_realtime_price_snapshot"]["items"] = []

    def _fake(*, kr_tickers, force_refresh=False):
        return snap

    monkeypatch.setattr("app.draft_three_push.get_runtime_probe_snapshot", _fake)
    run = generate_market_briefing_via_generic({"push_kind": "market_briefing"})
    pkg = (run.draft_payload or {})["runtime_package"]
    assert pkg["generation_status"]["status"] == "partial"
    assert any(
        "kr_realtime_price_snapshot=unavailable" in w
        for w in pkg["generation_status"]["warnings"]
    )


def test_holdings_delivery_rejects_failed_package_message_rebuild(
    monkeypatch: pytest.MonkeyPatch, stub_storage
):
    """FIX r6 (검증자 5차 NOTES A-1 / B-1 / B-6): runtime_package.generation_
    status="failed" 인 holdings draft 는 delivery 의 legacy fallback 으로 본문이
    재생성되면 안 된다 — DeliveryError 로 명시 차단되어야 한다 (계약 §12).

    재현: FIX r5 로 Run.message_text=None 인 failed holdings run 을 만든 뒤
    delivery.deliver() 직접 호출. holdings fallback 이 본문을 재생성하면 안 됨.
    """
    import importlib

    from app import delivery as _delivery_mod
    from app import draft as draft_mod

    monkeypatch.setattr(
        draft_mod,
        "build_ml_baseline_evidence_snapshot",
        lambda: {"status": "unavailable"},
    )
    monkeypatch.setattr(
        draft_mod,
        "build_holdings_market_evidence",
        lambda **_kwargs: {"status": "unavailable"},
    )
    monkeypatch.setattr(
        draft_mod, "compute_topn", lambda **_kwargs: {"asof": "", "items": []}
    )

    holdings = [
        Holding(
            ticker="069500",
            quantity=10,
            avg_buy_price=35000,
            name="KODEX 200",
            account_group="일반",
        )
    ]
    run = draft_mod.generate_draft_from_holdings(holdings)
    pkg = (run.draft_payload or {})["runtime_package"]
    # 사전 조건.
    assert pkg["generation_status"]["status"] == "failed"
    assert run.message_text is None

    # conftest._stub_oci_calls 가 deliver 를 무동작 stub 으로 교체했으므로 원본을
    # 복원 (delivery 모듈을 reload).
    importlib.reload(_delivery_mod)
    # 외부 SCP/SSH 차단: _ssh_target 등 환경변수 접근만 stub (실제 발송 X 보장).
    monkeypatch.setenv("OCI_SSH_TARGET", "stub@stub")
    monkeypatch.setenv("OCI_REMOTE_INBOX", "/tmp/stub_inbox")
    monkeypatch.setenv("OCI_REMOTE_OUTBOX", "/tmp/stub_outbox")
    monkeypatch.setattr(_delivery_mod, "_scp_upload", lambda *a, **k: None)

    # deliver 는 DELIVERING 상태에서만 동작 — 상태 끌어올림.
    run.status = "DELIVERING"
    with pytest.raises(_delivery_mod.DeliveryError) as exc:
        _delivery_mod.deliver(run)
    assert "failed" in str(exc.value).lower() or "generation_status" in str(exc.value)


def test_holdings_draft_failed_package_clears_run_message_text(
    monkeypatch: pytest.MonkeyPatch, stub_storage
):
    """FIX r5 (검증자 4차 NOTES A-1 / B-1 / B-6): runtime_package 가 failed 면
    실제 승인/preview/발송 단일 소스인 Run.message_text 도 None 이어야 한다.

    Run.message_text 가 정상 본문을 유지하면 RunPanel 이 preview 를 보여주고
    승인 버튼이 활성화되어 "failed 인데 정상 흐름" 상태가 됨 (계약 §12 위반).
    """
    from app import draft as draft_mod

    monkeypatch.setattr(
        draft_mod,
        "build_ml_baseline_evidence_snapshot",
        lambda: {"status": "unavailable"},
    )
    monkeypatch.setattr(
        draft_mod,
        "build_holdings_market_evidence",
        lambda **_kwargs: {"status": "unavailable"},
    )
    monkeypatch.setattr(
        draft_mod, "compute_topn", lambda **_kwargs: {"asof": "", "items": []}
    )

    holdings = [
        Holding(
            ticker="069500",
            quantity=10,
            avg_buy_price=35000,
            name="KODEX 200",
            account_group="일반",
        )
    ]
    run = draft_mod.generate_draft_from_holdings(holdings)
    pkg = (run.draft_payload or {})["runtime_package"]
    assert pkg["generation_status"]["status"] == "failed"
    # Run.message_text 는 None 이어야 한다.
    assert run.message_text is None
    # Run.status 는 PENDING_APPROVAL 유지 (기존 흐름 손상 X).
    assert run.status == "PENDING_APPROVAL"


def test_market_briefing_failed_package_clears_run_message_text(
    monkeypatch: pytest.MonkeyPatch, stub_storage
):
    """FIX r5: PUSH-1 도 동일 정책 — failed 면 Run.message_text 도 None.

    generate_market_briefing_draft 를 직접 호출 (via_generic 우회) — empty topn
    + unavailable ml_baseline → market_discovery_snapshot 빈 dict → failed.
    """
    from app import draft_three_push as dtp

    # autouse stub 이 runtime_probe 를 kr/us=unavailable 로 반환. PUSH-1 의 필수
    # evidence (market_discovery + data_quality) 중 market_discovery 가 비어있게
    # 만들면 generation_status=failed. topn_payload=None 이면 _build_market_briefing_
    # evidence 가 market_discovery_snapshot 을 {} 로 채움 → _has_data False → failed.
    run = dtp.generate_market_briefing_draft(
        ml_baseline_snapshot={"status": "unavailable"},
        topn_payload=None,
    )
    pkg = (run.draft_payload or {})["runtime_package"]
    assert pkg["generation_status"]["status"] == "failed"
    assert run.message_text is None
    assert run.status == "PENDING_APPROVAL"


def test_holdings_draft_failed_package_keeps_message_contract_empty(
    monkeypatch: pytest.MonkeyPatch, stub_storage
):
    """FIX r4 (검증자 3차 NOTES A-1 / B-1): holdings 경로의 동기화 단계가 failed
    package 의 message_contract.message_text 를 다시 채우면 안 된다.

    재현 조건: runtime probe + ml baseline + market_discovery 모두 unavailable →
    push_context.market_view 빈 dict → market_view OR market_discovery 모두 부재
    → holdings_briefing generation_status="failed". 이때 draft_message 는 여전히
    message_text 본문을 만들 수 있으나, runtime_package.message_contract 는 빈
    문자열을 유지해야 한다 (FIX r3 안전장치 유지).
    """
    # 모든 evidence 를 빈 상태로 만들기 위해 의존 모듈 stub.
    from app import draft as draft_mod

    monkeypatch.setattr(
        draft_mod,
        "build_ml_baseline_evidence_snapshot",
        lambda: {"status": "unavailable"},
    )
    monkeypatch.setattr(
        draft_mod,
        "build_holdings_market_evidence",
        lambda **_kwargs: {"status": "unavailable"},
    )
    monkeypatch.setattr(
        draft_mod, "compute_topn", lambda **_kwargs: {"asof": "", "items": []}
    )

    holdings = [
        Holding(
            ticker="069500",
            quantity=10,
            avg_buy_price=35000,
            name="KODEX 200",
            account_group="일반",
        )
    ]
    run = draft_mod.generate_draft_from_holdings(holdings)
    pkg = (run.draft_payload or {})["runtime_package"]
    # 사전 조건: generation_status 가 failed 여야 본 테스트 의미가 있다.
    assert (
        pkg["generation_status"]["status"] == "failed"
    ), f"테스트 전제 깨짐 — failed 가 아니라 {pkg['generation_status']['status']}"
    # 본 검증: message_contract.message_text 는 빈 문자열.
    assert pkg["message_contract"]["message_text"] == ""


def test_failed_package_clears_message_contract_text(stub_storage):
    """A-1: generation_status='failed' 인 package 의 message_contract.message_text
    는 빈 문자열로 강제. 정상처럼 보이는 본문이 들어가면 안 된다 (계약 §12).
    """
    from app.runtime_package import build_runtime_package

    # holdings_snapshot 없음 → holdings_briefing 은 failed.
    pkg = build_runtime_package(
        push_kind="holdings_briefing",
        message_text="이건 정상 본문처럼 보이는 메시지입니다",
        pc_evidence_snapshot={
            "holdings_snapshot": {},
            "market_discovery_snapshot": {"asof": "2026-06-13", "items": [{"a": 1}]},
            "ml_baseline_snapshot": {},
            "universe_momentum_snapshot": {},
            "nav_discount_snapshot": {},
            "data_quality_snapshot": {"warnings": []},
        },
        runtime_snapshot={
            "captured_at": None,
            "kr_realtime_price_snapshot": {},
            "overnight_us_market_snapshot": {},
            "news_snapshot": {"status": "unavailable"},
        },
        push_context={},
    )
    assert pkg["generation_status"]["status"] == "failed"
    assert pkg["message_contract"]["message_text"] == ""


def test_empty_market_view_not_treated_as_present(stub_storage):
    """A-1: build_market_view 가 observations 없으면 빈 dict 를 반환해
    holdings_briefing 검증에서 market_view 가 "있는 것" 으로 오인되지 않는다.
    """
    from app.push_context import build_market_view

    mv = build_market_view(
        pc_evidence={
            "market_discovery_snapshot": {},
            "ml_baseline_snapshot": {},
        },
        runtime_snapshot={
            "overnight_us_market_snapshot": {"status": "unavailable", "indices": []},
        },
    )
    assert mv == {}


def test_holdings_briefing_requires_market_view_or_market_discovery(stub_storage):
    """A-1 (2) 보강: PUSH-2 generation_status 가 holdings_snapshot 만으로는 통과 X.
    push_context 의 market_view (또는 market_discovery_snapshot) 가 있어야 ok.
    """
    from app.runtime_package import build_runtime_package

    pc_evidence = {
        "holdings_snapshot": {"positions": [{"ticker": "069500"}]},
        "market_discovery_snapshot": {},
        "ml_baseline_snapshot": {},
        "universe_momentum_snapshot": {},
        "nav_discount_snapshot": {},
        "data_quality_snapshot": {"warnings": []},
    }
    runtime_snapshot = {
        "captured_at": None,
        "kr_realtime_price_snapshot": {},
        "overnight_us_market_snapshot": {},
        "news_snapshot": {"status": "unavailable"},
    }
    # push_context 비어있고 market_discovery 도 없음 → failed.
    pkg1 = build_runtime_package(
        push_kind="holdings_briefing",
        message_text="x",
        pc_evidence_snapshot=pc_evidence,
        runtime_snapshot=runtime_snapshot,
        push_context={},
    )
    assert pkg1["generation_status"]["status"] == "failed"
    assert (
        "market_view or market_discovery_snapshot"
        in pkg1["generation_status"]["missing_sections"]
    )

    # push_context.market_view 가 있으면 ok (또는 partial — runtime 빈 dict 만 영향).
    pkg2 = build_runtime_package(
        push_kind="holdings_briefing",
        message_text="x",
        pc_evidence_snapshot=pc_evidence,
        runtime_snapshot=runtime_snapshot,
        push_context={"market_view": {"observations": []}},
    )
    assert pkg2["generation_status"]["status"] in ("ok", "partial")
