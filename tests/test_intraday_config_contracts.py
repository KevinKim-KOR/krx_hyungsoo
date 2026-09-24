"""POC3-02C-OPS-01 — `INTRADAY_ALERT_CONFIG` 계약 테스트.

설계자 §10-3 필수 보완 6건을 **판정값까지** 고정한다. 라이브 DB·네트워크·
Telegram 을 건드리지 않는다 — 전부 `tmp_path`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.intraday_config import generator, schema, selector, store

CSV = Path("state/market_meta/krx_etf_basic_20260909.csv")
DB = Path("state/market/market_data.sqlite")


def _db(tmp_path: Path) -> Path:
    return tmp_path / "runtime_state.sqlite"


def _payload(tmp_path: Path) -> dict:
    sectors, excluded, asof = selector.build_sectors(csv_path=CSV, db_path=DB)
    return schema.build_payload(
        rule_version=selector.RULE_VERSION,
        sectors=sectors,
        token_dictionary=selector.default_token_dictionary(),
        data_asof=asof,
        excluded=excluded,
    )


# ── §10-2 분류 ───────────────────────────────────────────────────────────────


def test_longer_token_wins():
    """긴 토큰 우선. `AI반도체` 가 `반도체` 보다 먼저다."""
    d = {"반도체": ["반도체"], "AI반도체": ["AI반도체"]}
    assert selector.classify("FnGuide AI반도체 TOP2+ 지수", d) == "AI반도체"


def test_conflicting_same_length_tokens_are_not_classified():
    """같은 길이 토큰이 서로 다른 사업군을 가리키면 **임의 분류하지 않는다.**"""
    d = {"A": ["금융"], "B": ["금융"]}
    assert selector.classify("코스피 200 금융", d) is None


def test_unmatched_index_is_recorded_not_dropped(monkeypatch):
    """분류 안 된 지수를 조용히 버리지 않는다.

    고정 종가로 돌린다(설계자 2026-09-24) — 아래 `unclassified` 뿐이라는 단언은 라이브
    최신일 종가 커버리지(반도체 후보 전원 종가 있음)에 기대면 안 된다.
    """
    closes = {
        t: 10000.0
        for r in selector.load_official_rows(CSV)
        if (t := (r.get("단축코드") or "").strip())
    }
    monkeypatch.setattr(
        selector, "latest_closes", lambda db_path: ("2026-09-11", closes)
    )
    _, excluded, _ = selector.build_sectors(
        csv_path=CSV, db_path=DB, dictionary={"반도체": ["반도체"]}
    )
    assert excluded, "미분류가 기록되지 않았다"
    assert all(e["reason"] == "unclassified" for e in excluded)


def test_one_index_belongs_to_at_most_one_sector(tmp_path):
    """한 ticker 가 두 사업군의 대표가 되면 같은 종목을 두 번 조회한다."""
    p = _payload(tmp_path)
    reps = [
        s["representative"]["ticker"]
        for s in p["sector_representative_universe"]["sectors"]
    ]
    assert len(reps) == len(set(reps))


def test_representative_excludes_leveraged_inverse_synthetic(tmp_path):
    rows = {r["단축코드"].strip(): r for r in selector.load_official_rows(CSV)}
    p = _payload(tmp_path)
    for s in p["sector_representative_universe"]["sectors"]:
        for who in ("representative", "alternate"):
            item = s.get(who)
            if not item:
                continue
            row = rows[item["ticker"]]
            assert row["추적배수"].strip() == "일반"
            assert "합성" not in row["복제방법"]
            assert row["기초시장분류"].strip() == "국내"


def test_alternate_differs_from_representative(tmp_path):
    p = _payload(tmp_path)
    for s in p["sector_representative_universe"]["sectors"]:
        alt = s.get("alternate")
        if alt:
            assert alt["ticker"] != s["representative"]["ticker"]


# ── §10-3(1) 해시 분리 ───────────────────────────────────────────────────────


def test_price_asof_change_does_not_create_new_version(tmp_path):
    """가격 기준일만 바뀌면 **새 승인 버전을 만들지 않는다.**

    이게 없으면 거래일마다 승인 요청이 쌓인다.
    """
    db = _db(tmp_path)
    p1 = _payload(tmp_path)
    vid1, created1 = store.create_candidate(
        p1, evaluation_input_hash="hash-day1", db_path=db
    )
    assert created1

    p2 = json.loads(json.dumps(p1))
    p2["sector_representative_universe"]["data_asof"] = "2099-12-31"
    vid2, created2 = store.create_candidate(
        p2, evaluation_input_hash="hash-day2", db_path=db
    )
    assert not created2, "기준일만 달라졌는데 새 버전이 생겼다"
    assert vid2 == vid1


def test_representative_change_creates_new_version(tmp_path):
    db = _db(tmp_path)
    p1 = _payload(tmp_path)
    vid1, _ = store.create_candidate(p1, evaluation_input_hash="h1", db_path=db)

    p2 = json.loads(json.dumps(p1))
    p2["sector_representative_universe"]["sectors"][0]["representative"][
        "ticker"
    ] = "999999"
    vid2, created = store.create_candidate(p2, evaluation_input_hash="h1", db_path=db)
    assert created and vid2 != vid1


def test_holdings_are_not_a_selection_input():
    """보유 여부는 장중 메시지에서 판정할 정보이지 선정 입력이 아니다."""
    src = Path("app/intraday_config/selector.py").read_text(encoding="utf-8")
    assert "holdings" not in src.lower().replace("보유 여부는 선정 입력이 아니다", "")


# ── §10-3(5) checksum 범위 ──────────────────────────────────────────────────


def test_source_hash_ignores_approval_and_timestamps(tmp_path):
    """승인 시각이 바뀌었다고 설정 내용의 checksum 이 바뀌면 안 된다."""
    p = _payload(tmp_path)
    before = schema.source_hash(p)
    noisy = json.loads(json.dumps(p))
    noisy["created_at"] = "2026-01-01T00:00:00Z"
    noisy["approved_at"] = "2026-02-02T00:00:00Z"
    noisy["approved_by"] = "user"
    noisy["sync"] = {"status": "deployed"}
    assert schema.source_hash(noisy) == before


# ── §10-3(6) 최초 번들 비활성 ───────────────────────────────────────────────


def test_initial_bundle_is_disabled(tmp_path):
    p = _payload(tmp_path)
    pol = p["intraday_alert_policy"]
    assert pol["enabled"] is False
    assert pol["policy_status"] == schema.POLICY_NOT_CONFIGURED


@pytest.mark.parametrize("missing", list(schema.REQUIRED_POLICY_KEYS))
def test_enabled_requires_every_policy_value(tmp_path, missing):
    """켜려면 임계·cooldown·억제·상한이 **모두** 있어야 한다."""
    p = _payload(tmp_path)
    full = {k: 1 for k in schema.REQUIRED_POLICY_KEYS}
    full.update({"enabled": True, "policy_status": schema.POLICY_CONFIGURED})
    del full[missing]
    p["intraday_alert_policy"] = full
    with pytest.raises(schema.ConfigSchemaError) as e:
        schema.validate(p)
    assert missing in str(e.value)


def test_enabled_false_must_declare_not_configured(tmp_path):
    p = _payload(tmp_path)
    p["intraday_alert_policy"] = {
        "enabled": False,
        "policy_status": schema.POLICY_CONFIGURED,
    }
    with pytest.raises(schema.ConfigSchemaError):
        schema.validate(p)


# ── §10-3(4) 승인 게이트 ────────────────────────────────────────────────────


def test_activate_rejects_unapproved_version(tmp_path):
    """**미승인 자동 승격 차단.** 기존 `activate_param_version` 에는 없던 게이트다."""
    db = _db(tmp_path)
    p = _payload(tmp_path)
    vid, _ = store.create_candidate(p, evaluation_input_hash="h", db_path=db)
    with pytest.raises(store.ApprovalRequired):
        store.activate(vid, activated_by="test", db_path=db)
    assert store.get_active(db_path=db) is None


def test_activate_succeeds_after_approval(tmp_path):
    db = _db(tmp_path)
    p = _payload(tmp_path)
    vid, _ = store.create_candidate(p, evaluation_input_hash="h", db_path=db)
    store.approve(vid, approved_by="user", db_path=db)
    store.activate(vid, activated_by="test", db_path=db)
    active = store.get_active(db_path=db)
    assert active["config_version_id"] == vid
    assert active["approved_by"] == "user"


def test_rejected_version_cannot_activate(tmp_path):
    db = _db(tmp_path)
    p = _payload(tmp_path)
    vid, _ = store.create_candidate(p, evaluation_input_hash="h", db_path=db)
    store.reject(vid, rejected_by="user", reason="테스트", db_path=db)
    with pytest.raises(store.ApprovalRequired):
        store.activate(vid, activated_by="test", db_path=db)


def test_failed_deploy_keeps_previous_active(tmp_path):
    """전달 실패가 직전 active 를 바꾸면 안 된다."""
    db = _db(tmp_path)
    p1 = _payload(tmp_path)
    v1, _ = store.create_candidate(p1, evaluation_input_hash="h1", db_path=db)
    store.approve(v1, approved_by="user", db_path=db)
    store.activate(v1, activated_by="t", db_path=db)

    p2 = json.loads(json.dumps(p1))
    p2["sector_representative_universe"]["sectors"][0]["representative"][
        "ticker"
    ] = "888888"
    v2, _ = store.create_candidate(p2, evaluation_input_hash="h2", db_path=db)
    store.record_sync(v2, target="oci", status="scp_failed", error="boom", db_path=db)

    assert store.get_active(db_path=db)["config_version_id"] == v1


# ── 생성 트리거 §10-3(2) ────────────────────────────────────────────────────


def test_generate_is_idempotent(tmp_path):
    db = _db(tmp_path)
    r1 = generator.generate(state_db_path=db)
    r2 = generator.generate(state_db_path=db, force=True)
    assert r1["status"] == "created"
    assert r2["status"] == "unchanged"
    assert r1["config_version_id"] == r2["config_version_id"]


def test_generate_never_raises(tmp_path):
    """백엔드 기동을 막으면 안 된다 — 실패해도 dict 로 돌려준다."""
    out = generator.generate(
        csv_path=tmp_path / "missing.csv",
        db_path=tmp_path / "missing.sqlite",
        state_db_path=_db(tmp_path),
        force=True,
    )
    assert out["status"] == "failed"
    assert "reason" in out


def test_should_regenerate_when_no_active(tmp_path):
    need, why = generator.should_regenerate(state_db_path=_db(tmp_path))
    assert need and why == "no_active_version"


def test_no_new_db_file_created(tmp_path):
    """신규 DB 파일 금지 — 기존 runtime_state.sqlite 를 재사용한다."""
    db = _db(tmp_path)
    generator.generate(state_db_path=db)
    files = sorted(p.name for p in tmp_path.iterdir() if p.suffix == ".sqlite")
    assert files == ["runtime_state.sqlite"], files


# ── POC3-02C-OPS-02 §15-3 정책 값 범위 계약 ─────────────────────────────────
#
# 키가 **있는 것만으로는 부족하다.** 범위 밖 값이 통과하면 커버리지 Gate 가
# 무력화된다(`sector_min_coverage_pct = -1` 이면 언제나 통과).


def _enabled_policy(**over):
    p = dict(schema.INITIAL_POLICY_VALUES)
    p.update({"enabled": True, "policy_status": schema.POLICY_CONFIGURED})
    p.update(over)
    return p


def test_coverage_key_is_required(tmp_path):
    """`sector_min_coverage_pct` 가 필수 키다(설계자 §15-3)."""
    assert "sector_min_coverage_pct" in schema.REQUIRED_POLICY_KEYS
    p = _payload(tmp_path)
    policy = _enabled_policy()
    del policy["sector_min_coverage_pct"]
    p["intraday_alert_policy"] = policy
    with pytest.raises(schema.ConfigSchemaError) as e:
        schema.validate(p)
    assert "sector_min_coverage_pct" in str(e.value)


@pytest.mark.parametrize("bad", ["80", None, True, False, [], {}])
def test_non_numeric_coverage_is_rejected(tmp_path, bad):
    p = _payload(tmp_path)
    p["intraday_alert_policy"] = _enabled_policy(sector_min_coverage_pct=bad)
    with pytest.raises(schema.ConfigSchemaError):
        schema.validate(p)


@pytest.mark.parametrize("bad", [-0.1, 100.1, 1e9, float("nan")])
def test_out_of_range_coverage_is_rejected(tmp_path, bad):
    p = _payload(tmp_path)
    p["intraday_alert_policy"] = _enabled_policy(sector_min_coverage_pct=bad)
    with pytest.raises(schema.ConfigSchemaError):
        schema.validate(p)


@pytest.mark.parametrize("ok", [0.0, 80.0, 100.0])
def test_in_range_coverage_passes(tmp_path, ok):
    """하한·상한 **포함**이다."""
    p = _payload(tmp_path)
    p["intraday_alert_policy"] = _enabled_policy(sector_min_coverage_pct=ok)
    schema.validate(p)


@pytest.mark.parametrize(
    "key,bad",
    [
        ("max_sends_per_day", 0),
        ("max_items_per_section", 0),
        ("cooldown_minutes", -1),
        ("sector_rank_top_pct", 101.0),
        ("drop_threshold_pct", 1.0),
    ],
)
def test_other_policy_ranges_are_enforced(tmp_path, key, bad):
    p = _payload(tmp_path)
    p["intraday_alert_policy"] = _enabled_policy(**{key: bad})
    with pytest.raises(schema.ConfigSchemaError) as e:
        schema.validate(p)
    assert key in str(e.value)


def test_disabled_policy_skips_range_check(tmp_path):
    """`enabled=false` 면 수치가 비어 있어도 된다(§10-3(6) 최초 번들 비활성)."""
    p = _payload(tmp_path)
    schema.validate(p)  # 기본 payload 는 enabled=false
