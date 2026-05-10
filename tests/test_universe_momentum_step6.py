"""POC2 Step 6 — Universe Momentum Formula Minimal Scoring 회귀 테스트.

설계자 결정 (Step 6 §20 — 16개 최소 테스트):
1. pykrx price history 성공 시 one_month_return_pct 계산
2. pykrx 실패 candidate 는 is_scored=false
3. 일부 성공 시 refresh_status="partial"
4. 전체 실패 시 refresh_status="failed"
5. 성공 시 refresh_status="ok"
6. seed items 20개 초과 hard fail
7. rank 는 scored 후보에만 부여
8. top_candidate 저장
9. GenerateDraft 가 pykrx 를 호출하지 않고 latest artifact 만 읽는지
10. message_text 에 외부 후보 점검 bullet 이 세 번째로 들어가는지
11. message_text 의 외부 후보 점검 bullet 에 기준일 포함
12. [판단 사유] 헤더가 1번만
13. universe 후보 전체가 Telegram/message_text 에 나열되지 않는지
14. refresh button API 호출 (= POST /universe/momentum/refresh) 동작
15. UI status panel 데이터 (= GET /universe/momentum/latest) 가 마지막 갱신 asof + 기준일 노출
16. Step5B / Step5C regression — 기존 holdings momentum_result + universe seed 검증 그대로
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from tests._helpers import _put_holdings_for_momentum, _seed_payload, _write_seed

# ─── 1. pykrx 성공 → one_month_return_pct 계산 ─────────────────────────


def test_one_month_return_pct_computed_from_pykrx_basis():
    """PriceHistoryBasis → compute_one_month_return_pct = (latest/base - 1)*100."""
    from app.price_history_pykrx import (
        PriceHistoryBasis,
        compute_one_month_return_pct,
    )

    basis = PriceHistoryBasis(
        base_date="2026-04-07",
        base_close=10000,
        latest_date="2026-05-07",
        latest_close=10425,
    )
    pct = compute_one_month_return_pct(basis)
    assert pct == pytest.approx(4.25, abs=1e-9)


# ─── 2. pykrx 실패 candidate → is_scored=false + exclusion_reason ─────


def test_failure_candidate_is_unscored_with_exclusion_reason(_isolated_universe):
    """fetcher 가 PriceHistoryFailure 반환 → is_scored=False + exclusion_reason 기록."""
    from app import universe_refresh as ur
    from app.momentum import build_universe_momentum_result_scored
    from app.price_history_pykrx import PriceHistoryFailure
    from app.universe_seed import load_universe_seed

    _write_seed(
        _isolated_universe["seed_file"], _seed_payload(date.today().isoformat())
    )
    seed = load_universe_seed()

    def _fail(ticker, asof, **_kw):
        return PriceHistoryFailure(reason="no_data")

    scores, status = ur.run_universe_refresh(
        seed, fetcher=_fail, sleeper=lambda _x: None
    )
    assert status == "failed"
    mr = build_universe_momentum_result_scored(seed, scores, status)
    for c in mr["candidates"]:
        assert c["score_result"]["is_scored"] is False
        assert "exclusion_reason" in c["score_result"]
        assert "rank" not in c
        assert "price_history_basis" not in c


# ─── 3. partial / 4. failed / 5. ok ────────────────────────────────────


def test_refresh_status_partial(_isolated_universe):
    from app import universe_refresh as ur
    from app.price_history_pykrx import PriceHistoryBasis, PriceHistoryFailure
    from app.universe_seed import load_universe_seed

    _write_seed(
        _isolated_universe["seed_file"], _seed_payload(date.today().isoformat())
    )
    seed = load_universe_seed()

    def _half(ticker, asof, **_kw):
        if ticker == "069500":
            return PriceHistoryFailure(reason="no_data")
        return PriceHistoryBasis(
            base_date="2026-04-10",
            base_close=10000,
            latest_date=asof,
            latest_close=10300,
        )

    scores, status = ur.run_universe_refresh(
        seed, fetcher=_half, sleeper=lambda _x: None
    )
    assert status == "partial"


def test_refresh_status_failed(_isolated_universe):
    from app import universe_refresh as ur
    from app.price_history_pykrx import PriceHistoryFailure
    from app.universe_seed import load_universe_seed

    _write_seed(
        _isolated_universe["seed_file"], _seed_payload(date.today().isoformat())
    )
    seed = load_universe_seed()

    def _all_fail(ticker, asof, **_kw):
        return PriceHistoryFailure(reason="fetch_error")

    scores, status = ur.run_universe_refresh(
        seed, fetcher=_all_fail, sleeper=lambda _x: None
    )
    assert status == "failed"


def test_refresh_status_ok(_isolated_universe):
    from app import universe_refresh as ur
    from app.price_history_pykrx import PriceHistoryBasis
    from app.universe_seed import load_universe_seed

    _write_seed(
        _isolated_universe["seed_file"], _seed_payload(date.today().isoformat())
    )
    seed = load_universe_seed()

    def _all_ok(ticker, asof, **_kw):
        return PriceHistoryBasis(
            base_date="2026-04-10",
            base_close=10000,
            latest_date=asof,
            latest_close=10500,
        )

    scores, status = ur.run_universe_refresh(
        seed, fetcher=_all_ok, sleeper=lambda _x: None
    )
    assert status == "ok"


# ─── 6. seed items 20 초과 hard fail ──────────────────────────────────


def test_seed_items_over_20_hard_fail(client, _isolated_universe):
    """20개 초과 seed → POST /universe/momentum/refresh 422 (조용히 자르지 않음)."""
    items = [{"ticker": f"{i:06d}", "name": f"ETF{i}"} for i in range(21)]
    payload = _seed_payload(date.today().isoformat(), items=items)
    _write_seed(_isolated_universe["seed_file"], payload)
    r = client.post("/universe/momentum/refresh")
    assert r.status_code == 422
    body = r.json()
    assert "20" in body["detail"]


# ─── 7. rank 는 scored 후보에만 + 8. top_candidate 저장 ────────────────


def test_rank_only_for_scored_candidates(_isolated_universe):
    """일부 성공 seed → scored 만 rank 부여, unscored 는 rank 키 없음."""
    from app import universe_refresh as ur
    from app.momentum import build_universe_momentum_result_scored
    from app.price_history_pykrx import PriceHistoryBasis, PriceHistoryFailure
    from app.universe_seed import load_universe_seed

    items = [
        {"ticker": "AAA", "name": "AAA"},
        {"ticker": "BBB", "name": "BBB"},
        {"ticker": "CCC", "name": "CCC"},
    ]
    _write_seed(
        _isolated_universe["seed_file"],
        _seed_payload(date.today().isoformat(), items=items),
    )
    seed = load_universe_seed()
    pcts = {"AAA": 5.0, "BBB": None, "CCC": 3.0}

    def _ftc(ticker, asof, **_kw):
        v = pcts.get(ticker)
        if v is None:
            return PriceHistoryFailure(reason="no_data")
        return PriceHistoryBasis(
            base_date="2026-04-10",
            base_close=10000,
            latest_date=asof,
            latest_close=10000 * (1 + v / 100),
        )

    scores, status = ur.run_universe_refresh(
        seed, fetcher=_ftc, sleeper=lambda _x: None
    )
    mr = build_universe_momentum_result_scored(seed, scores, status)
    by_ticker = {c["ticker"]: c for c in mr["candidates"]}
    assert by_ticker["AAA"]["rank"] == 1  # 5%
    assert by_ticker["CCC"]["rank"] == 2  # 3%
    assert "rank" not in by_ticker["BBB"]
    # top_candidate 저장
    top = mr["summary"]["top_candidate"]
    assert top["ticker"] == "AAA"
    assert top["score_result"]["score_value"] == 5.0


# ─── 9. GenerateDraft 가 pykrx 를 직접 호출하지 않음 ───────────────────


def test_generate_draft_does_not_call_pykrx(client, monkeypatch, _isolated_universe):
    """GenerateDraft 호출 시 fetch_one_month_basis 를 호출해서는 안 된다 (AC-20).

    refresh artifact 가 이미 있어도 GenerateDraft 는 새 fetch 를 트리거 안 함.
    """
    from app import universe_refresh as ur

    # 먼저 refresh 1회 — 이때만 stub fetcher 호출됨.
    _write_seed(
        _isolated_universe["seed_file"], _seed_payload(date.today().isoformat())
    )
    client.post("/universe/momentum/refresh")

    # GenerateDraft 호출 시점에 fetcher 가 호출되면 RuntimeError 가 발생하도록 교체.
    def _explode(*_args, **_kwargs):  # noqa: ANN001
        raise RuntimeError("pykrx must NOT be called from GenerateDraft")

    monkeypatch.setattr(ur, "fetch_one_month_basis", _explode)

    _put_holdings_for_momentum(client)
    r = client.post("/runs/generate-from-holdings")
    assert r.status_code == 200
    body = r.json()
    assert "external_universe_check" in body["draft_payload"]


# ─── 10. message_text 에 외부 후보 점검 bullet 이 3번째 + 11. 기준일 포함 ───


def test_message_text_external_universe_bullet_third(client, _isolated_universe):
    """message_text [판단 사유] 의 bullet 순서: 보유 비중 → 모멘텀 → 외부 후보.

    bullet text 에 기준일이 포함되어야 한다 (AC-23).
    """
    _write_seed(
        _isolated_universe["seed_file"], _seed_payload(date.today().isoformat())
    )
    client.post("/universe/momentum/refresh")
    _put_holdings_for_momentum(client)
    body = client.post("/runs/generate-from-holdings").json()
    msg: str = body["message_text"]
    # 3개 bullet 모두 존재
    assert msg.count("[판단 사유]") == 1
    factor_idx = msg.find("- 보유 비중 영향:")
    momentum_idx = msg.find("- 모멘텀 점검:")
    external_idx = msg.find("- 외부 후보 점검:")
    # 순서 확인 (모멘텀 / external 은 반드시 있음)
    assert momentum_idx > 0
    assert external_idx > 0
    if factor_idx > 0:
        assert factor_idx < momentum_idx < external_idx
    else:
        assert momentum_idx < external_idx
    # 기준일 (top_candidate.latest_date 또는 universe asof) 포함
    after_external = msg[external_idx:]
    assert "기준일 " in after_external[:300]


# ─── 12. [판단 사유] 헤더는 1번만 ────────────────────────────────────


def test_judgment_header_appears_only_once(client, _isolated_universe):
    _write_seed(
        _isolated_universe["seed_file"], _seed_payload(date.today().isoformat())
    )
    client.post("/universe/momentum/refresh")
    _put_holdings_for_momentum(client)
    body = client.post("/runs/generate-from-holdings").json()
    assert body["message_text"].count("[판단 사유]") == 1


# ─── 13. universe 후보 전체가 message_text 에 나열되지 않음 ──────────


def test_universe_candidates_not_listed_in_message_text(client, _isolated_universe):
    items = [
        {"ticker": "DDD", "name": "DDD-ETF"},
        {"ticker": "EEE", "name": "EEE-ETF"},
        {"ticker": "FFF", "name": "FFF-ETF"},
    ]
    _write_seed(
        _isolated_universe["seed_file"],
        _seed_payload(date.today().isoformat(), items=items),
    )
    client.post("/universe/momentum/refresh")
    _put_holdings_for_momentum(client)
    msg: str = client.post("/runs/generate-from-holdings").json()["message_text"]
    # top 후보 1개만 등장. 나머지 2개 ticker 는 message_text 어디에도 없어야 함.
    counts = sum(1 for t in ("DDD", "EEE", "FFF") if t in msg)
    assert counts == 1


# ─── 14. POST /universe/momentum/refresh + 15. GET /universe/momentum/latest ───


def test_refresh_endpoint_returns_summary(client, _isolated_universe):
    """refresh button API 동작: 200 + refresh_status / scored / total."""
    _write_seed(
        _isolated_universe["seed_file"], _seed_payload(date.today().isoformat())
    )
    r = client.post("/universe/momentum/refresh")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "partial", "failed")
    summary = body["momentum_result"]["summary"]
    assert summary["refresh_status"] == body["status"]
    assert "scored_candidates" in summary
    assert "total_candidates" in summary


def test_latest_endpoint_exposes_asof_and_basis_date(client, _isolated_universe):
    """GET /universe/momentum/latest 는 마지막 asof / top_candidate.latest_date 노출."""
    today = date.today().isoformat()
    _write_seed(_isolated_universe["seed_file"], _seed_payload(today))
    client.post("/universe/momentum/refresh")
    r = client.get("/universe/momentum/latest")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "present"
    mr = body["momentum_result"]
    assert mr["asof"] == today
    top = mr["summary"].get("top_candidate")
    assert top is not None
    assert "price_history_basis" in top
    assert top["price_history_basis"]["latest_date"] == today


def test_latest_endpoint_absent_when_no_artifact(client, _isolated_universe):
    """artifact 부재 시 status='absent' (404 가 아님)."""
    r = client.get("/universe/momentum/latest")
    assert r.status_code == 200
    assert r.json()["status"] == "absent"


# ─── 16. Step5B / Step5C regression ─────────────────────────────────


def test_step5b_holdings_momentum_preserved_after_step6(client, _isolated_universe):
    """Step5B holdings momentum_result 가 깨지지 않는다."""
    _put_holdings_for_momentum(client)
    body = client.post("/runs/generate-from-holdings").json()
    payload = body["draft_payload"]
    assert "momentum_result" in payload
    assert payload["momentum_result"]["mode"] == "holdings"


def test_step5c_seed_validation_preserved_after_step6(client, _isolated_universe):
    """Step5C seed 검증 — 미래 asof 는 422 hard fail (Step6 변경 후에도 유지)."""
    future = (date.today() + timedelta(days=5)).isoformat()
    _write_seed(_isolated_universe["seed_file"], _seed_payload(future))
    r = client.post("/universe/momentum/refresh")
    assert r.status_code == 422


# ─── 추가: 실패 시 message_text bullet 형식 확인 ─────────────────────


def test_message_text_failure_bullet_contains_basis_date(
    client, monkeypatch, _isolated_universe
):
    """전체 실패 → [판단 사유] 의 외부 후보 점검 bullet 은 실패 형식 + 기준일 포함."""
    from app import universe_refresh as ur
    from app.price_history_pykrx import PriceHistoryFailure

    def _all_fail(ticker, asof, **_kw):
        return PriceHistoryFailure(reason="no_data")

    monkeypatch.setattr(ur, "fetch_one_month_basis", _all_fail)
    today = date.today().isoformat()
    _write_seed(_isolated_universe["seed_file"], _seed_payload(today))
    client.post("/universe/momentum/refresh")
    _put_holdings_for_momentum(client)
    msg: str = client.post("/runs/generate-from-holdings").json()["message_text"]
    assert "- 외부 후보 점검:" in msg
    assert "pykrx 가격 데이터 부족" in msg
    assert f"기준일 {today}" in msg
