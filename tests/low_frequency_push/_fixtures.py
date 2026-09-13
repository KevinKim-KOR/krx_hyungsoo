"""`tests/low_frequency_push/` 공용 fixture·helper.

`tests/test_low_frequency_push_operation.py` 가 KS-10 테스트 임계(>1500)를 넘어
책임별로 분해할 때 **helper 만 모았다**. 각 함수 본문은 원본에서 한 줄도
고치지 않았다 — 바뀐 것은 파일 배치와 import 경로뿐이다.

선례: `tests/runtime_evidence/_fixtures.py` 와 같은 역할이다.
"""

from __future__ import annotations

import sys

import types

from typing import Any

from app.holdings import Holding

from app.market_cache import MarketQuote


def _quote(ticker: str, price: float, asof: str) -> MarketQuote:
    return MarketQuote(
        ticker=ticker,
        name=None,
        current_price=price,
        price_asof=asof,
        price_source="naver",
    )


def _topn_ok(asof: str = "2026-07-24") -> dict[str, Any]:
    return {
        "status": "ok",
        "asof": asof,
        "basis": "one_month",
        "n": 10,
        "candidates": [],
        "market_context": None,
    }


def _holdings(n: int = 1) -> list[Holding]:
    return [
        Holding(
            ticker=f"0000{i:02d}",
            quantity=10,
            avg_buy_price=1000,
            name=f"종목{i:02d}",
            account_group="일반",
        )
        for i in range(n)
    ]


# ── Reevaluator: Published Evidence 강제 · fingerprint 축약 ──────────────


def _artifact_full(cands: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "engine_id": "universe_momentum",
        "mode": "universe",
        "asof": "2026-07-24",
        "summary": {
            "refresh_status": "ok",
            "falling_threshold_pct": -10.0,
            "spike_trigger_type": "falling",
            "spike_direction": "down",
            "evidence_as_of": "2026-07-24",
        },
        "candidates": cands,
    }


def _scored(ticker: str, name: str, base_close: float) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "name": name,
        "score_result": {"is_scored": True, "score_value": -5.0, "score_unit": "%"},
        "price_history_basis": {
            "base_date": "2026-06-24",
            "base_close": base_close,
            "latest_date": "2026-07-24",
            "latest_close": base_close * 0.95,
        },
    }


# ── Runner-level Fail-Closed ─────────────────────────────────────────────


def _seed_and_get_param(_tmp_path):
    from app.runtime_param_store import activate_param_version, create_param_version
    from app.three_push_runtime_param import build_manual_seed_param

    p = build_manual_seed_param()
    vid, _, _ = create_param_version(p.to_dict())
    activate_param_version(vid, activated_by="test")
    return p


def _install_common_mocks(monkeypatch, tmp_path):
    import scripts.run_three_push_runtime_oci as runner

    monkeypatch.setattr(runner, "telegram_send", lambda *a, **kw: (True, "", False))
    monkeypatch.setattr(runner, "_HISTORY_PATH", tmp_path / "history.jsonl")
    monkeypatch.setenv("PUSH_AUTOSEND_ENABLED", "true")
    # 2026-08-25 — push_kind 별 flag 이름이 코드와 어긋나 있었다.
    #   코드는 app/three_push_runner_common.PUSH_KIND_FLAG_ENVS 의
    #   `PUSH_AUTOSEND_<KIND>_ENABLED` 를 읽는데, 여기서는 `PUSH_<KIND>_ENABLED`
    #   를 설정해 실제로는 개발자 `.env` 값에 의존했다(맥은 전부 false → 상시 실패).
    #   검증을 약화시키지 않고 이름만 코드 계약에 맞춘다.
    monkeypatch.setenv("PUSH_AUTOSEND_HOLDINGS_BRIEFING_ENABLED", "true")
    monkeypatch.setenv("PUSH_AUTOSEND_SPIKE_OR_FALLING_ALERT_ENABLED", "true")
    # OCI Operational Market Data Refresh v1: Spike freshness guard 가 실 artifact
    # 를 읽지 않도록 fresh fixture 로 mock (compose 를 별도 mock 하는 test 기본값).
    _install_fresh_universe_artifact(monkeypatch, tmp_path=tmp_path)
    return runner


def _install_fresh_universe_artifact(monkeypatch, candidates=None, tmp_path=None):
    """freshness guard 통과용 fresh universe artifact + 당일 배치 성공 상태 mock."""
    from app import draft_three_push as _dtp
    from app.three_push_runtime_message_builder import kst_today_date
    from app.three_push_runtime import market_data_batch as _mdb
    from datetime import datetime, timezone
    import tempfile
    from pathlib import Path

    today = kst_today_date()
    gen = datetime.now(timezone.utc).isoformat()
    art = {
        "mode": "universe",
        "asof": today,
        "summary": {
            "refresh_status": "ok",
            "falling_threshold_pct": -10.0,
            "spike_trigger_type": "falling",
            "spike_direction": "down",
            "evidence_as_of": today,
            "artifact_generated_at": gen,
        },
        "candidates": candidates or [],
    }
    monkeypatch.setattr(_dtp, "_load_universe_artifact_for_spike", lambda: art)
    # C 확정: Spike guard 가 읽는 당일 배치 성공 상태를 tmp 로 격리 mock.
    base = Path(tmp_path) if tmp_path else Path(tempfile.mkdtemp())
    state_path = base / "batch_state.json"
    monkeypatch.setattr(_mdb, "MARKET_DATA_BATCH_STATE_PATH", state_path)
    _mdb.write_batch_state(
        status="success",
        price_data_as_of=today,
        artifact_generated_at=gen,
        refresh_date_kst=today,
        refresh_completed_at=gen,
        state_path=state_path,
    )


def _install_naver(monkeypatch, fetch_many):
    from app import market_naver as _mn

    monkeypatch.setattr(_mn, "fetch_many", fetch_many)
    fake = types.ModuleType("app.market_naver")
    fake.fetch_many = fetch_many
    monkeypatch.setitem(sys.modules, "app.market_naver", fake)


# ── target_tickers unit test 확장 (라운드 5 검증자 지적) ──────────────────


def _mock_universe_artifact(monkeypatch, artifact):
    from app import draft_three_push as _dtp

    monkeypatch.setattr(_dtp, "_load_universe_artifact_for_spike", lambda: artifact)


def _artifact_with_candidates(
    candidates: list, refresh_status: str = "ok"
) -> dict[str, Any]:
    """공용 validate_artifact 계약을 만족하는 최소 완전 artifact 를 만든다.

    (mode/asof/summary/refresh_status 필수). candidates 만 test 별로 교체.
    """
    return {
        "mode": "universe",
        "asof": "2026-07-24",
        "summary": {
            "refresh_status": refresh_status,
            "falling_threshold_pct": -10.0,
            "spike_trigger_type": "falling",
            "spike_direction": "down",
            "evidence_as_of": "2026-07-24",
        },
        "candidates": candidates,
    }


_MISSING = object()


def _cand(ticker="000660", is_scored=True, score_value=-5.0):
    sr: dict[str, Any] = {}
    if is_scored is not _MISSING:
        sr["is_scored"] = is_scored
    if score_value is not _MISSING:
        sr["score_value"] = score_value
    c: dict[str, Any] = {"score_result": sr}
    if ticker is not _MISSING:
        c["ticker"] = ticker
    return c


# ── PUSH 종류별 flag = false → 차단 분기 (2026-08-29) ──────────────────────
#
# 계약: `PUSH_AUTOSEND_<KIND>_ENABLED=false` 면 발송 경로에 도달하기 전에 멈춘다.
#   scripts/run_three_push_runtime_oci.run() §6 enable flag guard 가
#   `_finish("skipped", "push_kind_disabled")` 로 즉시 반환하므로,
#   telegram_send(§542)·mark_sent(§558,§565) 는 호출되지 않는다.
#
# 왜 필요한가: 지금까지 true(발송 허용) 분기만 검증돼 있었고 차단 분기를 지키는
#   테스트가 0건이었다. 가드 순서가 바뀌어 registry 기록이 먼저 일어나도
#   아무 테스트도 깨지지 않는 상태였다.
#
# status/history 종료 기록은 차단 시에도 남는 것이 정상이다(_finish 계약).


def _install_mocks_with_kind_disabled(monkeypatch, tmp_path, kind_flag_env: str):
    """공용 mock 을 깐 뒤 해당 push_kind flag 만 false 로 되돌린다.

    전역 `PUSH_AUTOSEND_ENABLED` 는 true 로 두어, 차단 사유가
    `autosend_disabled` 가 아니라 **`push_kind_disabled`** 임을 분리 검증한다.
    """
    runner = _install_common_mocks(monkeypatch, tmp_path)
    monkeypatch.setenv(kind_flag_env, "false")

    calls: list[str] = []
    marked: list[tuple] = []

    def _tracking_send(text: str, *a, **kw):
        calls.append(text)
        return True, "", False

    monkeypatch.setattr(runner, "telegram_send", _tracking_send)
    monkeypatch.setattr(
        runner,
        "mark_sent",
        lambda *a, **kw: marked.append((a, kw)),
        raising=False,
    )
    return runner, calls, marked


# ── POC3-OPS-01A — 선정 상태가 라이브 경로에 새지 않는가 ─────────────────────
#
# 순서 정정 전 실행에서 `no_selection` skip 이 **라이브**
# `state/three_push/holdings_selection_state_latest.json` 을 실제로 만들었다.
# 테스트가 운영 상태를 건드리는 것은 금지다. 경로 주입이 실제로 먹는지 고정한다.


def _stub_holdings_selection_inputs(monkeypatch, runner, *, quotes_asof):
    """보유 원장·가격·시세를 통제. 외부 조회 0건."""
    from dataclasses import dataclass

    @dataclass
    class _H:
        ticker: str
        name: str
        account_group: str = "일반"

    @dataclass
    class _Q:
        current_price: float
        price_asof: str

    import app.holdings as holdings_mod
    import app.market_data_store as store_mod

    monkeypatch.setattr(holdings_mod, "load", lambda *a, **k: [_H("AAA", "가나다")])
    # 20거래일 전 종가 대비 변화 없음 → 선정 0건.
    monkeypatch.setattr(
        store_mod,
        "fetch_price_history",
        lambda ticker, **kw: [(f"2026-08-{i + 1:02d}", 100.0) for i in range(30)],
    )
    monkeypatch.setattr(
        runner,
        "_collect_target_tickers",
        lambda pk: ["AAA"],
    )

    import types as _t

    fake = _t.ModuleType("app.market_naver")

    class _R:
        def __init__(self, t):
            self.ticker = t
            self.quote = _Q(current_price=100.0, price_asof=quotes_asof)

    fake.fetch_many = lambda tickers, timeout=15.0: [_R(t) for t in tickers]
    monkeypatch.setitem(sys.modules, "app.market_naver", fake)
    from app import market_naver as _mn

    monkeypatch.setattr(_mn, "fetch_many", fake.fetch_many)
