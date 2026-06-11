"""POC2 Step 5D Cleanup — Step 5C universe mode minimal candidate source 회귀 테스트.

분리 출처: tests/test_poc1_loop.py (Step 5D 이전 단일 파일).
테스트 의미 / 검증 강도 / 동작은 분리 전과 동일.
"""

from __future__ import annotations

import pytest

from tests._helpers import _put_holdings_for_momentum, _seed_payload, _write_seed


def test_step5c_universe_seed_normal_yields_universe_mode_result(_isolated_universe):
    """정상 seed → momentum_result.mode = 'universe' + 후보 변환."""
    from app.momentum import build_universe_momentum_result
    from app.universe_seed import load_universe_seed
    from datetime import date

    today = date.today()
    _write_seed(_isolated_universe["seed_file"], _seed_payload(today.isoformat()))
    seed = load_universe_seed()
    mr = build_universe_momentum_result(seed)
    assert mr["mode"] == "universe"
    assert mr["asof"] == today.isoformat()
    assert mr["summary"]["total_candidates"] == 2
    assert mr["summary"]["scored_candidates"] == 0
    assert mr["summary"]["source_freshness"] == "fresh"
    assert len(mr["candidates"]) == 2
    for c in mr["candidates"]:
        assert c["mode"] == "universe"


def test_step5c_seed_invalid_asof_format_fails(_isolated_universe):
    """asof 가 YYYY-MM-DD 형식이 아니면 UniverseSeedError."""
    from app.universe_seed import UniverseSeedError, load_universe_seed

    _write_seed(_isolated_universe["seed_file"], _seed_payload("2026/05/07"))
    with pytest.raises(UniverseSeedError):
        load_universe_seed()


def test_step5c_seed_future_asof_fails(_isolated_universe):
    """asof 가 미래 날짜면 UniverseSeedError. 오늘로 자동 보정 금지."""
    from app.universe_seed import UniverseSeedError, load_universe_seed
    from datetime import date, timedelta

    future = (date.today() + timedelta(days=5)).isoformat()
    _write_seed(_isolated_universe["seed_file"], _seed_payload(future))
    with pytest.raises(UniverseSeedError):
        load_universe_seed()


def test_step5c_seed_stale_30plus_days_marked_stale(_isolated_universe):
    """asof 가 30일 초과면 source_freshness='stale' + summary 에 stale 문구.
    hard fail 아님."""
    from app.momentum import build_universe_momentum_result
    from app.universe_seed import load_universe_seed
    from datetime import date, timedelta

    asof_old = (date.today() - timedelta(days=45)).isoformat()
    _write_seed(_isolated_universe["seed_file"], _seed_payload(asof_old))
    seed = load_universe_seed()
    mr = build_universe_momentum_result(seed)
    assert mr["summary"]["source_freshness"] == "stale"
    assert mr["summary"]["staleness_days"] == 45
    assert "30일을 초과" in mr["summary"]["summary_reason_text"]


def test_step5c_candidate_reason_text_states_no_formula(_isolated_universe):
    """candidate.reason_text 에 '아직 모멘텀 산식 미적용' 취지가 들어간다."""
    from app.momentum import build_universe_momentum_result
    from app.universe_seed import load_universe_seed
    from datetime import date

    _write_seed(
        _isolated_universe["seed_file"], _seed_payload(date.today().isoformat())
    )
    seed = load_universe_seed()
    mr = build_universe_momentum_result(seed)
    for c in mr["candidates"]:
        assert isinstance(c["reason_text"], str)
        assert "아직 모멘텀 산식" in c["reason_text"]


def test_step5c_score_result_not_scored_no_rank(_isolated_universe):
    """score_result.is_scored = False + rank 키 자체 미생성."""
    from app.momentum import build_universe_momentum_result
    from app.universe_seed import load_universe_seed
    from datetime import date

    _write_seed(
        _isolated_universe["seed_file"], _seed_payload(date.today().isoformat())
    )
    seed = load_universe_seed()
    mr = build_universe_momentum_result(seed)
    for c in mr["candidates"]:
        assert c["score_result"]["is_scored"] is False
        assert "rank" not in c
        assert "score_value" not in c["score_result"]


def test_step5c_endpoint_creates_or_updates_latest_artifact(client, _isolated_universe):
    """POST /universe/momentum/refresh → latest artifact 파일 생성 + 응답에 경로 포함."""
    import json as _json
    from datetime import date

    _write_seed(
        _isolated_universe["seed_file"], _seed_payload(date.today().isoformat())
    )
    r = client.post("/universe/momentum/refresh")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["momentum_result"]["mode"] == "universe"
    assert body["momentum_result"]["summary"]["source_freshness"] == "fresh"
    # 파일 실제 생성 확인
    artifact = _isolated_universe["artifact_file"]
    assert artifact.exists()
    saved = _json.loads(artifact.read_text(encoding="utf-8"))
    assert saved["mode"] == "universe"
    assert saved["asof"] == date.today().isoformat()
    assert "summary" in saved
    assert "candidates" in saved


def test_step5c_endpoint_idempotent_overwrite(client, _isolated_universe):
    """endpoint 두 번 호출하면 latest 1건 덮어쓰기 — history 누적 없음."""
    from datetime import date

    _write_seed(
        _isolated_universe["seed_file"], _seed_payload(date.today().isoformat())
    )
    client.post("/universe/momentum/refresh")
    first_mtime = _isolated_universe["artifact_file"].stat().st_mtime

    # 두 번째 호출 — 동일 파일 덮어쓰기, 별도 history 파일 안 생김
    client.post("/universe/momentum/refresh")
    second_mtime = _isolated_universe["artifact_file"].stat().st_mtime
    assert second_mtime >= first_mtime
    # history 파일이 디렉터리에 누적되지 않음
    files_in_dir = list(_isolated_universe["artifact_file"].parent.iterdir())
    artifact_files = [
        f for f in files_in_dir if f.name.endswith(".json") and "momentum" in f.name
    ]
    assert len(artifact_files) == 1


def test_step5c_endpoint_stale_seed_returns_stale_marker(client, _isolated_universe):
    """stale seed 도 endpoint 는 200 으로 응답하고 source_freshness='stale' 표시."""
    from datetime import date, timedelta

    asof_old = (date.today() - timedelta(days=45)).isoformat()
    _write_seed(_isolated_universe["seed_file"], _seed_payload(asof_old))
    r = client.post("/universe/momentum/refresh")
    assert r.status_code == 200
    body = r.json()
    assert body["momentum_result"]["summary"]["source_freshness"] == "stale"
    # 저장된 artifact 에도 stale 상태 보존
    import json as _json

    saved = _json.loads(_isolated_universe["artifact_file"].read_text(encoding="utf-8"))
    assert saved["summary"]["source_freshness"] == "stale"


def test_step5c_endpoint_invalid_seed_fails_422(client, _isolated_universe):
    """asof 누락 / 형식 오류 / 미래 날짜 / items 비정상은 422."""
    from datetime import date, timedelta

    # 미래 날짜
    future = (date.today() + timedelta(days=5)).isoformat()
    _write_seed(_isolated_universe["seed_file"], _seed_payload(future))
    r = client.post("/universe/momentum/refresh")
    assert r.status_code == 422

    # asof 누락
    _write_seed(
        _isolated_universe["seed_file"],
        {"source": "manual_seed", "items": [{"ticker": "X", "name": "X"}]},
    )
    r = client.post("/universe/momentum/refresh")
    assert r.status_code == 422

    # items 빈 배열
    _write_seed(
        _isolated_universe["seed_file"],
        _seed_payload(date.today().isoformat(), items=[]),
    )
    r = client.post("/universe/momentum/refresh")
    assert r.status_code == 422


def test_step5c_endpoint_does_not_affect_holdings_draft_flow(
    client, _isolated_universe
):
    """Step6 + Fix 라운드 + Step 7A 명칭 정렬: universe refresh 결과는 draft_payload 의
    신규 키가 아니라 factor_signals 안의 scope='universe' signal 1건으로 표현된다.
    [판단 사유] 에 '신규 ETF 관찰 후보' bullet 1줄이 더해진다. 단:
    - refresh 이전 (artifact 부재) 에는 universe scope signal 미추가.
    - holdings momentum_result / factor_signals / recommendations 등 기존 키 모두 보존.
    - **draft_payload 키 신설 0건** (external_universe_check 등 새 키 금지).
    - [판단 사유] 헤더 1번 유지 (헤더 중복 금지).
    - draft_payload / message_text 에 universe 후보 전체 목록 노출 금지.
    """
    from datetime import date

    # holdings 흐름 1회 — universe refresh 전 (artifact 부재)
    _put_holdings_for_momentum(client)
    body_before = client.post("/runs/generate-from-holdings").json()
    payload_before = body_before["draft_payload"]
    msg_before = body_before["message_text"]
    # refresh 전: universe scope signal 미추가 + 키 신설 0건.
    assert "external_universe_check" not in payload_before
    fs_before = payload_before.get("factor_signals", [])
    universe_sigs_before = [s for s in fs_before if s.get("scope") == "universe"]
    assert len(universe_sigs_before) == 0
    # universe 후보 전체 목록 표시 금지 (Step6 §13 / AC-28).
    # POC2 ML Baseline Evidence Draft Integration (2026-06-11) — ML baseline
    # evidence bullet 본문에 "universe median" 비교 문구가 들어가므로 단순 substring
    # "universe" 검사는 더 이상 유효하지 않다. universe momentum 후보 관련 노출이
    # 없음을 확인하는 기존 의도는 "신규 ETF 관찰 후보" 라벨 부재로 보존.
    assert "- 신규 ETF 관찰 후보:" not in msg_before
    assert "외부 ETF 후보군" not in msg_before
    # 기준선 [판단 사유] 헤더 1번.
    assert msg_before.count("[판단 사유]") == 1
    # Step7B 통합 후: 보유 종목 상태 브리핑 1줄에 보유 비중 영향 + 모멘텀 점검 통합.
    assert "- 보유 종목 상태 브리핑:" in msg_before

    # universe refresh 수행
    _write_seed(
        _isolated_universe["seed_file"], _seed_payload(date.today().isoformat())
    )
    client.post("/universe/momentum/refresh")

    # holdings 흐름 1회 — universe refresh 후
    body_after = client.post("/runs/generate-from-holdings").json()
    payload_after = body_after["draft_payload"]
    msg_after = body_after["message_text"]

    # draft_payload 키 신설 — Step6 universe 흐름은 신규 키 0건이며 universe
    # 결과는 factor_signals 안의 scope="universe" signal 1건으로 표현된다 (본 검증의
    # 원래 의도). 본 STEP 외 신규 키 추가는 금지.
    # POC2 Holdings × Market Discovery Evidence 1차 (2026-06-03) — 별도 STEP 으로
    # holdings_market_evidence_snapshot 1건 신규 키 추가 (지시문 §5.11 권장).
    # POC2 ML Baseline Evidence Draft Integration (2026-06-11) — 추가로
    # ml_baseline_evidence_snapshot 1건 신규 키 추가 (지시문 §4.2).
    expected_keys = {
        "title",
        "asof",
        "note",
        "recommendations",
        "factor_signals",
        "momentum_result",
        "holdings_market_evidence_snapshot",
        "ml_baseline_evidence_snapshot",
    }
    assert set(payload_after.keys()) == expected_keys
    # universe 결과는 factor_signals 안의 scope="universe" signal 1건으로 표현
    fs_after = payload_after.get("factor_signals", [])
    universe_sigs_after = [s for s in fs_after if s.get("scope") == "universe"]
    assert len(universe_sigs_after) == 1
    assert universe_sigs_after[0]["factor_id"] == "universe_one_month_return"
    # universe 후보 전체 목록은 message 어디에도 풀려나오지 않음.
    assert "외부 ETF 후보군" not in msg_after
    # [판단 사유] 헤더는 여전히 1번 (헤더 중복 금지 — AC-26)
    assert msg_after.count("[판단 사유]") == 1
    # Step7B 통합 후 bullet 구조:
    # - 별도 "- 보유 비중 영향:" / "- 모멘텀 점검:" 줄 0건.
    # - "- 보유 종목 상태 브리핑:" 1줄 + "- 신규 ETF 관찰 후보:" 1줄.
    assert "- 보유 비중 영향:" not in msg_after
    assert "- 모멘텀 점검:" not in msg_after
    assert "- 보유 종목 상태 브리핑:" in msg_after
    assert "- 신규 ETF 관찰 후보:" in msg_after
    # bullet 순서: 보유 종목 상태 브리핑 → 신규 ETF 관찰 후보
    assert msg_after.index("- 보유 종목 상태 브리핑:") < msg_after.index(
        "- 신규 ETF 관찰 후보:"
    )


def test_step5c_existing_step5b_holdings_momentum_preserved(client, _isolated_universe):
    """기존 Step5B holdings mode 가 깨지지 않는다 — momentum_result 그대로 유지."""
    from datetime import date

    # universe refresh 1회 수행
    _write_seed(
        _isolated_universe["seed_file"], _seed_payload(date.today().isoformat())
    )
    client.post("/universe/momentum/refresh")

    # holdings momentum_result 확인
    _put_holdings_for_momentum(client)
    body = client.post("/runs/generate-from-holdings").json()
    payload = body["draft_payload"]
    assert "momentum_result" in payload
    mr = payload["momentum_result"]
    assert mr["mode"] == "holdings"
    assert mr["engine_id"] == "momentum_engine_placeholder_v1"
    # holdings candidate row 매핑 4 키 유지
    cand = mr["candidates"][0]
    for key in ("source_index", "ticker", "account_group", "avg_buy_price"):
        assert key in cand


# ─── POC2 Step 3: First Factor Signal Integration ───────────────
