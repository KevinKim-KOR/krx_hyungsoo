"""tests for app.three_push_runtime_param.

핵심 검증 (검증자 NOTES r1 반영):
  - 정상 manual_seed PARAM 은 통과한다.
  - top-level 금지 키 거부.
  - **중첩 dict/list 안의 금지 키도 거부** (fail-closed).
  - 대소문자 무관 매칭.
  - schema_version / param_source / enabled_push_kinds 허용값 위반 거부.
  - from_dict 는 검증 실패 시 RuntimeError.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.three_push_runtime_param import (
    ALLOWED_PUSH_KINDS,
    SCHEMA_VERSION,
    build_manual_seed_param,
    from_dict,
    read_param_file,
    validate_param_dict,
    write_param_file,
)


def _valid_dict() -> dict:
    """validator 가 통과하는 최소 PARAM dict."""
    p = build_manual_seed_param(
        param_description="unit",
        source_note="test",
    )
    return p.to_dict()


# ── 정상 경로 ────────────────────────────────────────────────────────────────


def test_manual_seed_param_validates():
    errors = validate_param_dict(_valid_dict())
    assert errors == []


def test_from_dict_roundtrip():
    src = _valid_dict()
    obj = from_dict(src)
    assert obj.schema_version == SCHEMA_VERSION
    # to_dict → from_dict round trip
    again = from_dict(obj.to_dict())
    assert again.param_id == obj.param_id


def test_read_param_file(tmp_path: Path):
    p = build_manual_seed_param()
    path = tmp_path / "latest_runtime_param.json"
    write_param_file(path, p)
    loaded = read_param_file(path)
    assert loaded.param_id == p.param_id
    assert loaded.param_source == "manual_seed"


# ── schema / 필수필드 / 허용값 ────────────────────────────────────────────────


def test_schema_version_mismatch_rejected():
    d = _valid_dict()
    d["schema_version"] = "three_push_runtime_param.v999"
    errs = validate_param_dict(d)
    assert any("schema_version" in e for e in errs)


def test_missing_required_field_rejected():
    d = _valid_dict()
    del d["enabled_push_kinds"]
    errs = validate_param_dict(d)
    assert any("enabled_push_kinds" in e for e in errs)


def test_param_source_not_allowed_rejected():
    d = _valid_dict()
    d["param_source"] = "random_unknown"
    errs = validate_param_dict(d)
    assert any("param_source" in e for e in errs)


def test_enabled_push_kinds_not_allowed_rejected():
    d = _valid_dict()
    d["enabled_push_kinds"] = ["market_briefing", "not_a_real_kind"]
    errs = validate_param_dict(d)
    assert any("enabled_push_kinds" in e for e in errs)


def test_enabled_push_kinds_must_be_list():
    d = _valid_dict()
    d["enabled_push_kinds"] = "market_briefing"
    errs = validate_param_dict(d)
    assert any("list" in e for e in errs)


# ── 금지 키: top-level ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "forbidden_key",
    [
        "message_text",
        "telegram_text",
        "buy_candidates",
        "sell_candidates",
        "cash_allocation",
        "regime_confirmation",
        "risk_threshold_confirmation",
        "etf_ranking",
        "token",
        "chat_id",
        "bot_token",
        "telegram_token",
        "telegram_chat_id",
    ],
)
def test_forbidden_key_top_level_rejected(forbidden_key: str):
    d = _valid_dict()
    d[forbidden_key] = "evil_value"
    errs = validate_param_dict(d)
    assert any(
        forbidden_key in e and "금지 키" in e for e in errs
    ), f"top-level forbidden key '{forbidden_key}' 가 막히지 않음: {errs!r}"


# ── 금지 키: 중첩 (fail-closed 핵심) ─────────────────────────────────────────


def test_forbidden_key_nested_in_dict_rejected():
    """검증자 NOTES r1 핵심 — 중첩 dict 안의 message_text 도 거부해야 함."""
    d = _valid_dict()
    d["extra"] = {"deep": {"message_text": "<완성 텔레그램 본문>"}}
    errs = validate_param_dict(d)
    assert any(
        "message_text" in e for e in errs
    ), f"중첩 message_text 가 통과됨: {errs!r}"


def test_forbidden_key_nested_in_list_rejected():
    d = _valid_dict()
    d["extra"] = [{"buy_candidates": ["TIGER 200"]}]
    errs = validate_param_dict(d)
    assert any("buy_candidates" in e for e in errs)


def test_forbidden_token_nested_rejected():
    """secret 비노출 가드 — 중첩 token 도 거부."""
    d = _valid_dict()
    d["runtime_policy"] = dict(d["runtime_policy"])
    d["runtime_policy"]["nested"] = {"token": "12345:secretsecret"}
    errs = validate_param_dict(d)
    assert any("token" in e for e in errs)


def test_forbidden_key_case_insensitive():
    """'Token' / 'BOT_TOKEN' 같은 변형도 거부."""
    d = _valid_dict()
    d["extra"] = {"TOKEN": "abc"}
    errs = validate_param_dict(d)
    assert any("token" in e.lower() for e in errs)

    d2 = _valid_dict()
    d2["evidence_policy"] = dict(d2["evidence_policy"])
    d2["evidence_policy"]["Bot_Token"] = "..."
    errs2 = validate_param_dict(d2)
    assert any("bot_token" in e.lower() for e in errs2)


def test_from_dict_raises_on_nested_forbidden():
    d = _valid_dict()
    d["extra"] = {"deep": {"chat_id": "1234567"}}
    with pytest.raises(RuntimeError, match="chat_id"):
        from_dict(d)


# ── to_dict: 허용 extra 보존 + forbidden 키 자체 차단 ────────────────────────


def test_to_dict_preserves_allowed_extra():
    p = build_manual_seed_param(
        param_description="hello",
        source_note="world",
    )
    out = p.to_dict()
    assert out.get("param_description") == "hello"
    assert out.get("source_note") == "world"


def test_to_dict_skips_forbidden_top_level_in_extra():
    """build_manual_seed_param 으로 안 들어가지만, 누군가 RuntimeParam.extra 에
    금지 키를 직접 채워도 to_dict 에서 걸러야 한다 (방어적)."""
    p = build_manual_seed_param()
    p.extra["message_text"] = "<완성 본문>"
    p.extra["allowed_meta"] = "ok"
    out = p.to_dict()
    assert "message_text" not in out
    assert out["allowed_meta"] == "ok"


# ── JSON 파일 손상 ───────────────────────────────────────────────────────────


def test_read_param_file_missing_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        read_param_file(tmp_path / "nope.json")


def test_read_param_file_corrupted_raises(tmp_path: Path):
    path = tmp_path / "latest_runtime_param.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(RuntimeError, match="JSON 파싱 실패"):
        read_param_file(path)


def test_read_param_file_schema_invalid_raises(tmp_path: Path):
    path = tmp_path / "latest_runtime_param.json"
    bad = _valid_dict()
    bad["schema_version"] = "v0"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(RuntimeError, match="schema_version"):
        read_param_file(path)


# ── enabled / disabled 헬퍼 ─────────────────────────────────────────────────


def test_is_push_kind_enabled():
    p = build_manual_seed_param(
        enabled_push_kinds=["market_briefing", "holdings_briefing"]
    )
    assert p.is_push_kind_enabled("market_briefing") is True
    assert p.is_push_kind_enabled("spike_or_falling_alert") is False


def test_allowed_push_kinds_constant():
    # 계약 안정성 — 3종 외 추가되면 본 테스트가 깨져서 의도적 변경임을 강제.
    assert set(ALLOWED_PUSH_KINDS) == {
        "market_briefing",
        "holdings_briefing",
        "spike_or_falling_alert",
    }
