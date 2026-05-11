"""POC2 Step 7A — 신규 ETF 관찰 후보 최소 운영화 회귀 테스트.

테스트 범위 (Step7A §10):
- 명칭 정렬: 사용자 노출 "신규 ETF 관찰 후보" / 기존 "외부 후보 점검" 잔존 0건.
- starter seed: 파일 부재 시 생성 + 기존 사용자 seed 덮어쓰기 금지.
- POST 응답 source 노출 (UI 가 starter seed 사용 여부 판별).
- 기존 Step6 회귀 (top_candidate / score_result / rank / GenerateDraft pykrx 미호출).
- [판단 사유] 헤더 1회 + bullet 순서 + Telegram payload Run.message_text 단일 소스.
"""

from __future__ import annotations

import json as _json
from datetime import date

from tests._helpers import _put_holdings_for_momentum, _seed_payload, _write_seed

# ─── 1. 명칭 정렬 ──────────────────────────────────────────────────────


def test_message_text_third_bullet_label_is_new_etf_watch(client, _isolated_universe):
    """message_text [판단 사유] 의 3번째 bullet 라벨이 '신규 ETF 관찰 후보'."""
    _write_seed(
        _isolated_universe["seed_file"], _seed_payload(date.today().isoformat())
    )
    client.post("/universe/momentum/refresh")
    _put_holdings_for_momentum(client)
    body = client.post("/runs/generate-from-holdings").json()
    msg: str = body["message_text"]
    assert "- 신규 ETF 관찰 후보:" in msg


def test_message_text_does_not_contain_legacy_external_check_label(
    client, _isolated_universe
):
    """Step7A 명칭 정렬 후 기존 '외부 후보 점검' 사용자 노출 라벨이 0건."""
    _write_seed(
        _isolated_universe["seed_file"], _seed_payload(date.today().isoformat())
    )
    client.post("/universe/momentum/refresh")
    _put_holdings_for_momentum(client)
    msg: str = client.post("/runs/generate-from-holdings").json()["message_text"]
    assert "외부 후보 점검" not in msg


def test_factor_signal_universe_scope_factor_name(client, _isolated_universe):
    """factor_signals 안의 scope='universe' signal 의 factor_name 이 '신규 ETF 관찰 후보'."""
    _write_seed(
        _isolated_universe["seed_file"], _seed_payload(date.today().isoformat())
    )
    client.post("/universe/momentum/refresh")
    _put_holdings_for_momentum(client)
    body = client.post("/runs/generate-from-holdings").json()
    fs = body["draft_payload"]["factor_signals"]
    universe_sigs = [s for s in fs if s.get("scope") == "universe"]
    assert len(universe_sigs) == 1
    assert universe_sigs[0]["factor_name"] == "신규 ETF 관찰 후보"
    # factor_id 는 내부 식별자 그대로 유지 (사용자 노출 아님)
    assert universe_sigs[0]["factor_id"] == "universe_one_month_return"


# ─── 2. starter seed 동작 ────────────────────────────────────────────


def test_starter_seed_created_when_seed_file_missing(client, _isolated_universe):
    """seed 파일 부재 시 POST refresh 가 starter seed 생성 후 정상 동작."""
    seed_file = _isolated_universe["seed_file"]
    assert not seed_file.exists()

    r = client.post("/universe/momentum/refresh")
    assert r.status_code == 200
    # starter seed 가 생성됨
    assert seed_file.exists()
    saved = _json.loads(seed_file.read_text(encoding="utf-8"))
    assert saved["source"] == "starter_seed"
    # 후보 3개
    assert len(saved["items"]) == 3
    # asof YYYY-MM-DD 형식 검증
    asof = saved["asof"]
    assert isinstance(asof, str) and len(asof) == 10
    assert asof[4] == "-" and asof[7] == "-"
    # API 응답에 source 가 noted 됨
    summary = r.json()["momentum_result"]["summary"]
    assert summary.get("source") == "starter_seed"


def test_starter_seed_has_three_default_candidates(client, _isolated_universe):
    """starter seed 의 후보 3개 (KODEX 200 / 미국S&P500 / 미국나스닥100)."""
    client.post("/universe/momentum/refresh")
    saved = _json.loads(_isolated_universe["seed_file"].read_text(encoding="utf-8"))
    tickers = {it["ticker"] for it in saved["items"]}
    assert tickers == {"069500", "379800", "379810"}


def test_existing_seed_not_overwritten_by_starter(client, _isolated_universe):
    """기존 사용자 seed 가 있으면 starter seed 가 절대 덮어쓰지 않는다."""
    # 사용자 seed 작성 (custom 후보 1개)
    custom_items = [{"ticker": "TIGER", "name": "사용자 커스텀 ETF"}]
    custom_payload = _seed_payload(date.today().isoformat(), items=custom_items)
    _write_seed(_isolated_universe["seed_file"], custom_payload)

    r = client.post("/universe/momentum/refresh")
    assert r.status_code == 200

    # 사용자 seed 가 그대로 보존됨
    saved = _json.loads(_isolated_universe["seed_file"].read_text(encoding="utf-8"))
    assert saved["source"] != "starter_seed"
    assert len(saved["items"]) == 1
    assert saved["items"][0]["ticker"] == "TIGER"
    # API 응답에도 사용자 source 그대로
    summary = r.json()["momentum_result"]["summary"]
    assert summary.get("source") != "starter_seed"


def test_existing_user_seed_candidates_used_in_refresh(client, _isolated_universe):
    """기존 사용자 seed 가 있을 때 그 후보군이 그대로 scoring 대상이 된다."""
    custom_items = [
        {"ticker": "AAA", "name": "AAA ETF"},
        {"ticker": "BBB", "name": "BBB ETF"},
    ]
    custom_payload = _seed_payload(date.today().isoformat(), items=custom_items)
    _write_seed(_isolated_universe["seed_file"], custom_payload)

    r = client.post("/universe/momentum/refresh")
    body = r.json()
    summary = body["momentum_result"]["summary"]
    assert summary["total_candidates"] == 2
    # top_candidate 의 ticker 는 사용자 seed 의 후보 중 하나
    top = summary.get("top_candidate")
    assert top is not None
    assert top["ticker"] in {"AAA", "BBB"}


# ─── 3. 기존 Step6 회귀 ────────────────────────────────────────────


def test_generate_draft_does_not_call_pykrx_step7a(
    client, monkeypatch, _isolated_universe
):
    """GenerateDraft 호출 시 pykrx fetch_one_month_basis 미호출 (Step7A 회귀)."""
    from app import universe_refresh as ur

    # refresh 1회 — stub fetcher 사용
    client.post("/universe/momentum/refresh")

    # GenerateDraft 시점 fetcher 호출되면 RuntimeError
    def _explode(*_args, **_kwargs):
        raise RuntimeError("pykrx must NOT be called from GenerateDraft (Step7A)")

    monkeypatch.setattr(ur, "fetch_one_month_basis", _explode)

    _put_holdings_for_momentum(client)
    r = client.post("/runs/generate-from-holdings")
    assert r.status_code == 200


def test_judgment_header_appears_only_once_step7a(client, _isolated_universe):
    """[판단 사유] 헤더가 1번만 (Step7A 회귀)."""
    client.post("/universe/momentum/refresh")
    _put_holdings_for_momentum(client)
    msg: str = client.post("/runs/generate-from-holdings").json()["message_text"]
    assert msg.count("[판단 사유]") == 1


def test_bullet_order_step7a(client, _isolated_universe):
    """bullet 순서: 보유 비중 영향 → 모멘텀 점검 → 신규 ETF 관찰 후보."""
    client.post("/universe/momentum/refresh")
    _put_holdings_for_momentum(client)
    msg: str = client.post("/runs/generate-from-holdings").json()["message_text"]
    momentum_idx = msg.find("- 모멘텀 점검:")
    new_etf_idx = msg.find("- 신규 ETF 관찰 후보:")
    assert momentum_idx > 0 and new_etf_idx > 0
    assert momentum_idx < new_etf_idx


def test_not_buy_recommendation_text_kept(client, _isolated_universe):
    """'이 값은 매수 추천이 아닙니다' 문구 유지 (성공 시)."""
    client.post("/universe/momentum/refresh")
    _put_holdings_for_momentum(client)
    msg: str = client.post("/runs/generate-from-holdings").json()["message_text"]
    assert "이 값은 매수 추천이 아닙니다" in msg


def test_universe_candidates_not_listed_step7a(client, _isolated_universe):
    """universe 후보 전체가 message_text 에 나열되지 않음 (top 1개만)."""
    # starter seed 사용 → 3개 후보, top 1개만 message_text 에 등장해야 함
    client.post("/universe/momentum/refresh")
    _put_holdings_for_momentum(client)
    msg: str = client.post("/runs/generate-from-holdings").json()["message_text"]
    # 3개 starter seed ticker 중 1개만 message_text 에 등장
    starter_tickers = ("069500", "379800", "379810")
    count = sum(1 for t in starter_tickers if t in msg)
    assert count <= 1
