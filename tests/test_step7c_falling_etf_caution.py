"""POC2 Step 7C — 급락 ETF 주의 신호 (PUSH 3) 최소 구현 회귀 테스트.

테스트 범위 (Step7C §11):
- score_value <= -10.0 후보가 있으면 falling candidate 선택.
- 여러 후보 동률 시 tie-breaker: score_value ASC → ticker ASC → candidate_id ASC.
- 기준 만족 후보 없으면 message_text 에 급락 ETF 주의 신호 bullet 미생성.
- 후보 있으면 message_text 에 3번째 bullet 추가 (이름 / 수익률 / 기준 / 기준일 포함).
- 매수/매도 지시 중립 안내 포함.
- BUY / SELL / 손절 / 리밸런싱 문구 0건.
- GenerateDraft pykrx 미호출.
- 기존 PUSH 1 / PUSH 2 / [판단 사유] 헤더 1회 유지.
- Telegram payload = Run.message_text 단일 소스.
"""

from __future__ import annotations

from datetime import date

import pytest

from tests._helpers import _put_holdings_for_momentum, _seed_payload, _write_seed


def _stub_with_returns(pcts: dict[str, float]):
    """ticker → 1개월 수익률 % 매핑으로 stub fetcher 생성.

    base_close=10000 기준으로 latest_close 를 결정해 정확한 score_value 가 나오게 한다.
    """
    from app.price_history_pykrx import PriceHistoryBasis

    def _fetcher(ticker: str, asof: str, **_kw):
        pct = pcts.get(ticker, 0.0)
        base_close = 10000.0
        latest_close = base_close * (1 + pct / 100.0)
        return PriceHistoryBasis(
            base_date="2026-04-10",
            base_close=base_close,
            latest_date=asof,
            latest_close=latest_close,
        )

    return _fetcher


# ─── 1. 급락 후보 선택 + tie-breaker ─────────────────────────────────


def test_falling_candidate_selected_when_below_threshold(
    client, monkeypatch, _isolated_universe
):
    """score_value <= -10.0 후보가 있으면 summary.falling_candidate 선택."""
    from app import universe_refresh as ur

    items = [
        {"ticker": "AAA", "name": "AAA ETF"},
        {"ticker": "BBB", "name": "BBB ETF"},
    ]
    _write_seed(
        _isolated_universe["seed_file"],
        _seed_payload(date.today().isoformat(), items=items),
    )
    monkeypatch.setattr(
        ur, "fetch_one_month_basis", _stub_with_returns({"AAA": -15.0, "BBB": 3.0})
    )
    r = client.post("/universe/momentum/refresh")
    summary = r.json()["momentum_result"]["summary"]
    assert summary["falling_candidate"] is not None
    assert summary["falling_candidate"]["ticker"] == "AAA"
    assert summary["falling_threshold_pct"] == -10.0


def test_falling_candidate_picks_lowest_score(client, monkeypatch, _isolated_universe):
    """여러 후보 중 score_value 가장 낮은 (= 가장 큰 하락) 1건만 선택."""
    from app import universe_refresh as ur

    items = [
        {"ticker": "AAA", "name": "AAA"},
        {"ticker": "BBB", "name": "BBB"},
        {"ticker": "CCC", "name": "CCC"},
    ]
    _write_seed(
        _isolated_universe["seed_file"],
        _seed_payload(date.today().isoformat(), items=items),
    )
    monkeypatch.setattr(
        ur,
        "fetch_one_month_basis",
        _stub_with_returns({"AAA": -12.5, "BBB": 5.0, "CCC": -18.1}),
    )
    r = client.post("/universe/momentum/refresh")
    summary = r.json()["momentum_result"]["summary"]
    assert summary["falling_candidate"]["ticker"] == "CCC"  # 가장 큰 하락 = -18.1%


def test_tie_breaker_ticker_ascending_when_score_equal(
    client, monkeypatch, _isolated_universe
):
    """score_value 동률 시 ticker 오름차순으로 결정론적 선택 (지시문 §3.3)."""
    from app import universe_refresh as ur

    items = [
        {"ticker": "069500", "name": "AAA"},
        {"ticker": "379800", "name": "BBB"},
    ]
    _write_seed(
        _isolated_universe["seed_file"],
        _seed_payload(date.today().isoformat(), items=items),
    )
    # 둘 다 동일 score
    monkeypatch.setattr(
        ur,
        "fetch_one_month_basis",
        _stub_with_returns({"069500": -12.5, "379800": -12.5}),
    )
    r = client.post("/universe/momentum/refresh")
    summary = r.json()["momentum_result"]["summary"]
    assert summary["falling_candidate"]["ticker"] == "069500"  # 알파벳 오름차순


def test_tie_breaker_candidate_id_when_score_and_ticker_equal():
    """score_value + ticker 동일 시 candidate_id 오름차순 — 단위 테스트."""
    from app.momentum.universe_mode import _select_falling_candidate

    cands = [
        {
            "candidate_id": "universe|XXX|국내지수|KOSPI200",
            "ticker": "XXX",
            "score_result": {"is_scored": True, "score_value": -12.0},
        },
        {
            "candidate_id": "universe|XXX|국내지수|KODEX200",
            "ticker": "XXX",
            "score_result": {"is_scored": True, "score_value": -12.0},
        },
    ]
    selected = _select_falling_candidate(cands, -10.0)
    assert selected is not None
    # candidate_id 오름차순 — "KODEX200" 이 "KOSPI200" 보다 알파벳 앞
    assert selected["candidate_id"].endswith("KODEX200")


# ─── 2. 신호 없음 처리 ──────────────────────────────────────────────


def test_no_falling_signal_when_all_above_threshold(
    client, monkeypatch, _isolated_universe
):
    """모든 후보가 기준 초과 → falling_candidate=None, message_text 에 bullet 미생성."""
    from app import universe_refresh as ur

    items = [
        {"ticker": "AAA", "name": "AAA"},
        {"ticker": "BBB", "name": "BBB"},
    ]
    _write_seed(
        _isolated_universe["seed_file"],
        _seed_payload(date.today().isoformat(), items=items),
    )
    monkeypatch.setattr(
        ur,
        "fetch_one_month_basis",
        _stub_with_returns({"AAA": -5.0, "BBB": 3.0}),
    )
    r = client.post("/universe/momentum/refresh")
    summary = r.json()["momentum_result"]["summary"]
    assert summary["falling_candidate"] is None
    # message_text 에도 급락 bullet 없음
    _put_holdings_for_momentum(client)
    msg = client.post("/runs/generate-from-holdings").json()["message_text"]
    assert "- 급락 ETF 주의 신호:" not in msg
    # "신호 없음" 같은 문구도 Telegram 에 추가되지 않음 (KS-5 가드)
    assert "급락 주의 신호 없음" not in msg
    assert "급락 신호 없음" not in msg


# ─── 3. 신호 있음 message_text ───────────────────────────────────────


def test_message_text_includes_falling_signal_when_present(
    client, monkeypatch, _isolated_universe
):
    """급락 후보 있을 때 message_text 에 3번째 bullet 추가 (이름/수익률/기준/기준일 포함)."""
    from app import universe_refresh as ur

    today = date.today().isoformat()
    items = [
        {"ticker": "FALL", "name": "급락ETF"},
        {"ticker": "BBB", "name": "BBB"},
    ]
    _write_seed(_isolated_universe["seed_file"], _seed_payload(today, items=items))
    monkeypatch.setattr(
        ur,
        "fetch_one_month_basis",
        _stub_with_returns({"FALL": -15.5, "BBB": 7.0}),
    )
    client.post("/universe/momentum/refresh")
    _put_holdings_for_momentum(client)
    msg = client.post("/runs/generate-from-holdings").json()["message_text"]
    assert "- 급락 ETF 주의 신호:" in msg
    # 이름 포함 (note: score는 base/latest 비율 계산이라 약간의 floating 오차 허용)
    assert "급락ETF" in msg
    # 수익률 음수 (= 하락) 포함 — "-15" 부분 포함
    assert "-15" in msg
    # 초기 급락 기준 포함
    assert "-10.0%" in msg
    # 기준일 포함
    assert f"기준일 {today}" in msg


def test_falling_signal_includes_neutral_text(client, monkeypatch, _isolated_universe):
    """급락 ETF 주의 신호에 매수/매도 지시 중립 안내 포함."""
    from app import universe_refresh as ur

    items = [{"ticker": "AAA", "name": "AAA"}]
    _write_seed(
        _isolated_universe["seed_file"],
        _seed_payload(date.today().isoformat(), items=items),
    )
    monkeypatch.setattr(ur, "fetch_one_month_basis", _stub_with_returns({"AAA": -15.0}))
    client.post("/universe/momentum/refresh")
    _put_holdings_for_momentum(client)
    msg = client.post("/runs/generate-from-holdings").json()["message_text"]
    falling_line = next(
        ln for ln in msg.split("\n") if ln.startswith("- 급락 ETF 주의 신호:")
    )
    assert "매수/매도 지시가 아닙니다" in falling_line


# ─── 4. 금지 표현 0건 ──────────────────────────────────────────────


def test_message_text_no_sell_or_stoploss_phrases(
    client, monkeypatch, _isolated_universe
):
    """급락 신호 있을 때도 BUY / SELL / 손절 / 리밸런싱 문구 0건."""
    from app import universe_refresh as ur

    items = [{"ticker": "FALL", "name": "급락ETF"}]
    _write_seed(
        _isolated_universe["seed_file"],
        _seed_payload(date.today().isoformat(), items=items),
    )
    monkeypatch.setattr(
        ur, "fetch_one_month_basis", _stub_with_returns({"FALL": -20.0})
    )
    client.post("/universe/momentum/refresh")
    _put_holdings_for_momentum(client)
    msg = client.post("/runs/generate-from-holdings").json()["message_text"]
    forbidden = ["BUY", "SELL", "매도 신호", "매수 금지", "손절", "리밸런싱"]
    for phrase in forbidden:
        assert phrase not in msg, f"Forbidden phrase: {phrase}"


# ─── 5. GenerateDraft pykrx 미호출 (Step6/Step7A 회귀) ──────────────


def test_generate_draft_does_not_call_pykrx_step7c(
    client, monkeypatch, _isolated_universe
):
    """급락 신호 있는 상태에서도 GenerateDraft 가 pykrx 직접 호출 안 함."""
    from app import universe_refresh as ur

    items = [{"ticker": "FALL", "name": "급락ETF"}]
    _write_seed(
        _isolated_universe["seed_file"],
        _seed_payload(date.today().isoformat(), items=items),
    )
    monkeypatch.setattr(
        ur, "fetch_one_month_basis", _stub_with_returns({"FALL": -15.0})
    )
    client.post("/universe/momentum/refresh")

    # 이제 fetcher 가 호출되면 RuntimeError
    def _explode(*_a, **_kw):
        raise RuntimeError("pykrx must NOT be called from GenerateDraft (Step7C)")

    monkeypatch.setattr(ur, "fetch_one_month_basis", _explode)

    _put_holdings_for_momentum(client)
    r = client.post("/runs/generate-from-holdings")
    assert r.status_code == 200


# ─── 6. 기존 PUSH 1 / 2 유지 + [판단 사유] 헤더 1회 ─────────────────


def test_briefing_and_etf_watch_preserved_with_falling(
    client, monkeypatch, _isolated_universe
):
    """급락 신호 있을 때도 PUSH 1 / PUSH 2 bullet 유지 + 헤더 1회."""
    from app import universe_refresh as ur

    items = [
        {"ticker": "FALL", "name": "급락ETF"},
        {"ticker": "TOP", "name": "TOP ETF"},
    ]
    _write_seed(
        _isolated_universe["seed_file"],
        _seed_payload(date.today().isoformat(), items=items),
    )
    monkeypatch.setattr(
        ur, "fetch_one_month_basis", _stub_with_returns({"FALL": -15.0, "TOP": 10.0})
    )
    client.post("/universe/momentum/refresh")
    _put_holdings_for_momentum(client)
    msg = client.post("/runs/generate-from-holdings").json()["message_text"]
    assert msg.count("[판단 사유]") == 1
    assert "- 보유 종목 상태 브리핑:" in msg
    assert "- 신규 ETF 관찰 후보:" in msg
    assert "- 급락 ETF 주의 신호:" in msg
    # bullet 순서: 보유 종목 상태 브리핑 → 신규 ETF 관찰 후보 → 급락 ETF 주의 신호
    b_idx = msg.find("- 보유 종목 상태 브리핑:")
    n_idx = msg.find("- 신규 ETF 관찰 후보:")
    f_idx = msg.find("- 급락 ETF 주의 신호:")
    assert b_idx < n_idx < f_idx


# ─── 7. Telegram payload = Run.message_text 단일 소스 ────────────────


def test_telegram_message_text_single_source_step7c(
    client, monkeypatch, _isolated_universe
):
    """GET /runs/{id} 응답의 message_text 가 POST 응답과 동일."""
    from app import universe_refresh as ur

    items = [{"ticker": "FALL", "name": "급락ETF"}]
    _write_seed(
        _isolated_universe["seed_file"],
        _seed_payload(date.today().isoformat(), items=items),
    )
    monkeypatch.setattr(
        ur, "fetch_one_month_basis", _stub_with_returns({"FALL": -12.0})
    )
    client.post("/universe/momentum/refresh")
    _put_holdings_for_momentum(client)
    body = client.post("/runs/generate-from-holdings").json()
    run_id = body["run_id"]
    fetched = client.get(f"/runs/{run_id}").json()
    assert fetched["message_text"] == body["message_text"]
    assert "- 급락 ETF 주의 신호:" in fetched["message_text"]


# ─── 8. 미스코어 후보는 falling 후보 대상 아님 ───────────────────────


def test_unscored_candidates_not_eligible_for_falling():
    """score_result.is_scored=False 후보는 score_value 음수여도 falling 후보 대상이 아니다."""
    from app.momentum.universe_mode import _select_falling_candidate

    cands = [
        {
            "candidate_id": "universe|UNSCORED",
            "ticker": "UNSCORED",
            "score_result": {
                "is_scored": False,
                "exclusion_reason": "pykrx 데이터 없음",
            },
        },
        {
            "candidate_id": "universe|SCORED",
            "ticker": "SCORED",
            "score_result": {"is_scored": True, "score_value": -11.0},
        },
    ]
    selected = _select_falling_candidate(cands, -10.0)
    assert selected is not None
    assert selected["ticker"] == "SCORED"


# ─── 9. threshold 정확히 -10.0 일 때 포함 (boundary) ─────────────────


def test_threshold_inclusive_boundary():
    """score_value == threshold (-10.0) 일 때 후보로 포함 (<=)."""
    from app.momentum.universe_mode import _select_falling_candidate

    cands = [
        {
            "candidate_id": "universe|EXACT",
            "ticker": "EXACT",
            "score_result": {"is_scored": True, "score_value": -10.0},
        }
    ]
    selected = _select_falling_candidate(cands, -10.0)
    assert selected is not None
    assert selected["ticker"] == "EXACT"


# ─── 10. compute_one_month_return_pct + threshold 일관성 sanity ─────


def test_score_value_computed_consistent_with_falling_filter():
    """stub fetcher 기반으로 계산된 score_value 가 threshold 검사에 일관되게 사용."""
    from app.price_history_pykrx import (
        PriceHistoryBasis,
        compute_one_month_return_pct,
    )

    basis = PriceHistoryBasis(
        base_date="2026-04-10",
        base_close=10000.0,
        latest_date="2026-05-10",
        latest_close=8500.0,
    )
    pct = compute_one_month_return_pct(basis)
    # -15% 근사
    assert pct == pytest.approx(-15.0, abs=1e-9)
    # threshold -10.0 보다 작으므로 falling 후보 자격 있음
    assert pct <= -10.0
