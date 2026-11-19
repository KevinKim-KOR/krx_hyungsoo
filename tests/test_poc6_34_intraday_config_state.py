"""POC6-34 — 「OCI 운영·적용」 ② 장중 급등락 설정 조회(`GET /intraday-config/state`) 계약.

POC6-34 가 `tests/test_intraday_config_integration.py`(POC3-02C-OPS-01 이후 산출 · 배포 ·
재시도 통합 계약)에 붙였던 시험을 이 파일로 옮겼다 — 그 파일이 1,613줄로 KS-10 기준
(시험 파일 1,500줄)을 넘었다(검증자 r2 B-3). 옮긴 시험(R1-F3 · I-22 잠금 · V-2)은 고치지
않았다. 임시 DB fixture `api_client` 와 보조 함수는 그 파일의 것을 그대로 쓴다(복사하지
않는다) — 라이브 DB · 상태 파일을 열지 않는다. 시험 자료는 모두 합성 값이다.

맨 아래 R2-F4 — 활성 정책의 켜짐 여부(`enabled`)도 후보처럼 bool 일 때만 읽는다. 없거나
bool 이 아니면 `policy_enabled` 는 `None`(화면 '확인 불가')이다. 정책 상태
(`policy_status` · `candidate_policy_status`)는 문자열이 아니면 `None` 이다(응답 500 없음).
"""

from __future__ import annotations

import json

import pytest

from app.intraday_config import generator, schema, store
from tests import test_intraday_config_integration as _integ

# 같은 임시 DB fixture · 보조 함수(이름으로 import 하면 fixture 인자가 F811 로 잡힌다).
api_client = _integ.api_client
_activate_with_policy = _integ._activate_with_policy
_policy_with = _integ._policy_with


# ── POC6-34 검증자 r1 R1-F3 — 후보 정책이 빠져도 활성 값으로 메우지 않는다 ──
#
# `shown_policy = cand_policy or active_policy` 였다. 저장된 후보의 정책 블록이
# 없으면 활성 버전의 값(진입 하한 1.5%)이 '승인 시 적용될 기준' 으로, 후보 켜짐 여부는
# `bool(None)` = '꺼짐' 으로 나갔다(검증자 임시 DB 재현). 실제 GET 엔드포인트를
# tmp DB 로 돌려 응답을 본다 — 라이브 DB 를 열지 않는다(`api_client`).

_CAND_ENTRY_MIN = 2.5  # 활성(1.5)과 다른 후보 값 — 섞이면 바로 보인다


def _active_and_candidate(db):
    """활성 = 확정 정책(진입 하한 1.5) · 후보 = 진입 하한 2.5 인 승인 대기 상태."""
    assert generator.CONFIRMED_POLICY["sector_entry_min_pct"] == 1.5
    va = _activate_with_policy(db, dict(generator.CONFIRMED_POLICY))
    s = [
        {"sector_key": "S0", "representative": {"ticker": "T0", "short_name": "n"}},
        {"sector_key": "S1", "representative": {"ticker": "T1", "short_name": "m"}},
    ]
    cand = schema.build_payload(
        rule_version="sector_rep.v1",
        sectors=s,
        token_dictionary={},
        data_asof="2026-09-17",
        excluded=[],
        policy=_policy_with(sector_entry_min_pct=_CAND_ENTRY_MIN),
    )
    vc, created = store.create_candidate(cand, evaluation_input_hash="h2", db_path=db)
    assert created
    return va, vc


def _rewrite_candidate_policy(db, vc, edit):
    """저장된 후보 payload 의 정책 블록만 고친다(`edit(body)` 가 body 를 바꾼다)."""
    import sqlite3

    body = json.loads(store.get_version(vc, db_path=db)["payload_json"])
    edit(body)
    con = sqlite3.connect(db)
    con.execute(
        "UPDATE intraday_alert_config_version SET payload_json=? "
        "WHERE config_version_id=?",
        (json.dumps(body, ensure_ascii=False, sort_keys=True), vc),
    )
    con.commit()
    con.close()


def _drop_block(body):
    del body["intraday_alert_policy"]


def _empty_block(body):
    body["intraday_alert_policy"] = {}


def _null_block(body):
    body["intraday_alert_policy"] = None


@pytest.mark.parametrize(
    "edit", [_drop_block, _empty_block, _null_block], ids=["removed", "empty", "null"]
)
def test_candidate_without_policy_shows_unknown_not_active_values(api_client, edit):
    """후보 정책이 없으면 12개 값 · 후보 켜짐 · 상태 모두 `None` — 후보 ID 는 그대로."""
    client, db = api_client
    va, vc = _active_and_candidate(db)

    # 대조: 정책이 온전할 때는 후보 값(2.5)이 나간다 — 아래 None 이 고정 자료 탓이 아니다.
    before = client.get("/intraday-config/state").json()
    assert before["candidate_version_id"] == vc
    vals = {p["key"]: p["value"] for p in before["policy_values"]}
    assert vals["sector_entry_min_pct"] == _CAND_ENTRY_MIN
    assert before["candidate_policy_enabled"] is True

    _rewrite_candidate_policy(db, vc, edit)
    body = client.get("/intraday-config/state").json()

    assert body["payload_error"] is None
    assert body["active_version_id"] == va
    assert body["candidate_version_id"] == vc
    assert body["action_state"] == "pending_approval"
    keys = [p["key"] for p in body["policy_values"]]
    assert keys == list(schema.REQUIRED_POLICY_KEYS)
    vals = {p["key"]: p["value"] for p in body["policy_values"]}
    leaked = {k: v for k, v in vals.items() if v is not None}
    assert leaked == {}, f"활성 값이 승인 기준으로 나갔다: {leaked}"
    # 없는 켜짐 여부를 '꺼짐'(False)으로 바꾸지 않는다.
    assert body["candidate_policy_enabled"] is None
    assert body["candidate_policy_status"] is None
    # 지금(활성) 상태는 활성 정책 그대로다.
    assert body["policy_enabled"] is True
    assert body["policy_status"] == schema.POLICY_CONFIGURED


@pytest.mark.parametrize(
    "enabled_edit",
    [lambda p: p.pop("enabled"), lambda p: p.update(enabled="true")],
    ids=["missing", "not-bool"],
)
def test_candidate_enabled_missing_or_not_bool_is_unknown(api_client, enabled_edit):
    """켜짐 여부만 없거나 bool 이 아니면 `None` — 다른 값은 후보 정책에서 그대로 읽는다."""
    client, db = api_client
    _va, vc = _active_and_candidate(db)
    _rewrite_candidate_policy(
        db, vc, lambda body: enabled_edit(body["intraday_alert_policy"])
    )
    body = client.get("/intraday-config/state").json()

    assert body["candidate_version_id"] == vc
    assert body["candidate_policy_enabled"] is None
    assert body["candidate_policy_status"] == schema.POLICY_CONFIGURED
    vals = {p["key"]: p["value"] for p in body["policy_values"]}
    assert vals["sector_entry_min_pct"] == _CAND_ENTRY_MIN


# ── POC6-34 I-22 — 화면 문장 전제 잠금 ──────────────────────────────────────


def test_holdings_surge_drop_values_equal_fixed_band_edges():
    """설계 고정값의 보유 급등 · 급락 값 = 프로그램 고정 경계임을 잠근다.

    보유 급등 · 급락 판정은 설정값이 아니라 고정 구간(`_SURGE_BANDS` 가장 낮은 하한 ·
    `_RISK_BANDS` 가장 얕은 상한)으로 한다. 화면의 '이 값의 뜻'은 POC6-34 검증자 r1
    R1-F1 정정 뒤 설정값이 아니라 이 고정 경계로 만들고, 저장값이 경계와 다르면
    '이 설정값(…)은 실제 판정 경계(…)와 다릅니다' 한 문장을 덧붙인다. 이 시험은
    설계 고정값(`CONFIRMED_POLICY`)에서는 그 문장이 나오지 않는다는 전제를 지킨다.
    화면 상수 ↔ 서버 상수 대조는 공용 고정 자료
    `tests/fixtures/poc6_34_holdings_bands.json` 을 거쳐
    `tests/test_holdings_risk_alert.py` 와 `intradayCriteria.test.ts` 가 맡는다.
    """
    from app.runtime_evidence import holdings_risk

    lowest_surge = min(low for _state, low, _high in holdings_risk._SURGE_BANDS)
    shallowest_drop = max(high for _state, _low, high in holdings_risk._RISK_BANDS)
    assert generator.CONFIRMED_POLICY["surge_threshold_pct"] == lowest_surge
    assert generator.CONFIRMED_POLICY["drop_threshold_pct"] == shallowest_drop


# ── POC6-34 r1 검증 V-2 — 정책 블록이 객체가 아니면 500 이 아니라 손상(payload_error) ──
def _list_block(body):
    body["intraday_alert_policy"] = ["x"]


def _str_block(body):
    body["intraday_alert_policy"] = "str"


def _num_block(body):
    body["intraday_alert_policy"] = 5


@pytest.mark.parametrize(
    "edit", [_list_block, _str_block, _num_block], ids=["list", "str", "number"]
)
def test_candidate_policy_block_not_object_is_payload_error(api_client, edit):
    """후보 정책 블록이 객체가 아니면 손상으로 드러난다(값을 지어내지 않음 · 500 아님)."""
    client, db = api_client
    va, vc = _active_and_candidate(db)
    _rewrite_candidate_policy(db, vc, edit)
    res = client.get("/intraday-config/state")
    assert res.status_code == 200
    body = res.json()
    assert body["payload_error"] and vc in body["payload_error"]
    assert body["candidate_version_id"] == vc
    assert body["active_version_id"] == va
    assert body["policy_values"] == []


def test_active_policy_block_not_object_is_payload_error(api_client):
    """활성 정책 블록이 객체가 아니어도 같다(후보가 없을 때 · 500 아님)."""
    import sqlite3

    client, db = api_client
    va = _activate_with_policy(db, dict(generator.CONFIRMED_POLICY))
    body = json.loads(store.get_version(va, db_path=db)["payload_json"])
    body["intraday_alert_policy"] = ["x"]
    con = sqlite3.connect(db)
    con.execute(
        "UPDATE intraday_alert_config_version SET payload_json=? "
        "WHERE config_version_id=?",
        (json.dumps(body, ensure_ascii=False, sort_keys=True), va),
    )
    con.commit()
    con.close()
    res = client.get("/intraday-config/state")
    assert res.status_code == 200
    out = res.json()
    assert out["payload_error"] and va in out["payload_error"]


# ── POC6-34 검증자 r2 R2-F4 — 활성 정책의 켜짐 여부 · 상태를 확인하지 못하면 `None` ──
#
# 후보 켜짐 여부는 r1 에서 형식을 검사했지만 활성은 `bool(active_policy.get("enabled"))`
# 였다. 활성 정책의 `enabled` 가 문자열 "false" 면 '켜짐', 없으면 '꺼짐' 으로 나갔다
# (검증자 임시 DB 재현 · 두 값 모두 스키마는 거부). 정책 상태는 문자열이 아니면 응답 모델
# 검사에서 500 이었다. 스키마 검사를 거치지 않는 손상을 저장 행에 직접 써서 실제 GET
# 엔드포인트로 본다.


def _rewrite_version(db, vid, edit):
    """버전 `vid`(활성 · 후보 어느 쪽이든)의 저장 payload 를 `edit(body)` 로 고친다.

    위 `_rewrite_candidate_policy` 는 버전 ID 로만 행을 찾는다 — 활성 버전에도 같다.
    """
    _rewrite_candidate_policy(db, vid, edit)


def _edit_policy(db, vid, edit):
    """버전 `vid` 의 정책 블록만 `edit(policy)` 로 고친다."""
    _rewrite_version(db, vid, lambda body: edit(body["intraday_alert_policy"]))


def _set(key, value):
    return lambda policy: policy.update({key: value})


def _pop(key):
    return lambda policy: policy.pop(key)


# 켜짐 여부를 확인할 수 없는 값 — 스키마는 모두 거부한다(`enabled` 는 bool 이어야 한다).
# 문자열 "false" 는 `bool()` 로 '켜짐', 없음 · null · 0 은 '꺼짐' 이 되던 값이다.
_UNKNOWN_ENABLED = [
    pytest.param(_set("enabled", "false"), id="str-false"),
    pytest.param(_set("enabled", "true"), id="str-true"),
    pytest.param(_pop("enabled"), id="missing"),
    pytest.param(_set("enabled", None), id="null"),
    pytest.param(_set("enabled", 1), id="int-1"),
    pytest.param(_set("enabled", 0), id="int-0"),
]

# 문자열이 아닌 정책 상태 — 그대로 내리면 응답 모델(`Optional[str]`) 검사에서 500 이다.
_NOT_STR_STATUS = [
    pytest.param(5, id="number"),
    pytest.param(True, id="bool"),
    pytest.param([schema.POLICY_CONFIGURED], id="list"),
    pytest.param({"v": schema.POLICY_CONFIGURED}, id="object"),
]


def _state(client):
    res = client.get("/intraday-config/state")
    assert res.status_code == 200, res.text
    return res.json()


@pytest.mark.parametrize(
    "policy, enabled, status",
    [
        pytest.param(
            dict(generator.CONFIRMED_POLICY), True, schema.POLICY_CONFIGURED, id="true"
        ),
        pytest.param(
            {"enabled": False, "policy_status": schema.POLICY_NOT_CONFIGURED},
            False,
            schema.POLICY_NOT_CONFIGURED,
            id="false",
        ),
    ],
)
def test_active_enabled_bool_is_kept(api_client, policy, enabled, status):
    """활성 켜짐 여부가 bool 이면 그대로다 — 아래 `None` 이 고정 자료 탓이 아니다."""
    client, db = api_client
    va = _activate_with_policy(db, policy)
    body = _state(client)
    assert body["payload_error"] is None
    assert body["active_version_id"] == va
    assert body["policy_enabled"] is enabled
    assert body["policy_status"] == status


@pytest.mark.parametrize("edit", _UNKNOWN_ENABLED)
def test_active_enabled_missing_or_not_bool_is_unknown(api_client, edit):
    """활성 켜짐 여부가 없거나 bool 이 아니면 `None` — '켜짐' · '꺼짐' 으로 읽지 않는다.

    손상 표시는 없고(정책 블록은 객체다) 상태 · 12개 값은 활성 정책에서 그대로 읽는다.
    """
    client, db = api_client
    va = _activate_with_policy(db, dict(generator.CONFIRMED_POLICY))
    _edit_policy(db, va, edit)
    body = _state(client)
    assert body["payload_error"] is None
    assert body["active_version_id"] == va
    assert body["candidate_version_id"] is None
    assert body["policy_enabled"] is None
    assert body["policy_status"] == schema.POLICY_CONFIGURED
    assert body["candidate_policy_enabled"] is None
    vals = {p["key"]: p["value"] for p in body["policy_values"]}
    assert vals["cooldown_minutes"] == generator.CONFIRMED_POLICY["cooldown_minutes"]


@pytest.mark.parametrize(
    "edit", [_drop_block, _empty_block, _null_block], ids=["removed", "empty", "null"]
)
def test_active_without_policy_is_unknown(api_client, edit):
    """활성 버전은 있는데 정책 블록이 없으면 켜짐 여부 · 상태 · 12개 값 모두 `None`."""
    client, db = api_client
    va = _activate_with_policy(db, dict(generator.CONFIRMED_POLICY))
    _rewrite_version(db, va, edit)
    body = _state(client)
    assert body["payload_error"] is None
    assert body["active_version_id"] == va
    assert body["policy_enabled"] is None
    assert body["policy_status"] is None
    assert [p["value"] for p in body["policy_values"]] == [None] * len(
        schema.REQUIRED_POLICY_KEYS
    )


def test_no_active_version_stays_off(api_client):
    """활성 버전이 아예 없으면 '꺼짐'(`False`) 그대로다 — 손상이 아니라 적용한 설정이 없다
    (운영 `intraday_alert_flow.active_policy()` 도 활성 없음 = 발송 안 함)."""
    client, _db = api_client
    body = _state(client)
    assert body["active_version_id"] is None
    assert body["payload_error"] is None
    assert body["policy_enabled"] is False
    assert body["policy_status"] is None


def test_corrupt_payload_leaves_enabled_unknown(api_client):
    """저장 내용을 못 읽으면(`payload_error`) 켜짐 여부도 `None` — '꺼짐' 으로 메우지 않는다."""
    import sqlite3

    client, db = api_client
    va = _activate_with_policy(db, dict(generator.CONFIRMED_POLICY))
    con = sqlite3.connect(db)
    con.execute(
        "UPDATE intraday_alert_config_version SET payload_json=? "
        "WHERE config_version_id=?",
        ("{깨진 JSON", va),
    )
    con.commit()
    con.close()
    body = _state(client)
    assert body["payload_error"] and va in body["payload_error"]
    assert body["policy_enabled"] is None
    assert body["policy_status"] is None
    assert body["candidate_policy_enabled"] is None


@pytest.mark.parametrize("status", _NOT_STR_STATUS)
def test_active_status_not_string_is_unknown_not_500(api_client, status):
    """활성 정책 상태가 문자열이 아니면 `None` — 500 이 아니고 켜짐 여부는 그대로 bool."""
    client, db = api_client
    va = _activate_with_policy(db, dict(generator.CONFIRMED_POLICY))
    _edit_policy(db, va, _set("policy_status", status))
    body = _state(client)
    assert body["payload_error"] is None
    assert body["policy_status"] is None
    assert body["policy_enabled"] is True


@pytest.mark.parametrize("edit", _UNKNOWN_ENABLED)
def test_candidate_enabled_unknown_table(api_client, edit):
    """후보도 같은 규칙 — 켜짐 여부만 `None` · 활성 상태와 후보 값(2.5)은 그대로."""
    client, db = api_client
    _va, vc = _active_and_candidate(db)
    _edit_policy(db, vc, edit)
    body = _state(client)
    assert body["payload_error"] is None
    assert body["candidate_version_id"] == vc
    assert body["candidate_policy_enabled"] is None
    assert body["candidate_policy_status"] == schema.POLICY_CONFIGURED
    assert body["policy_enabled"] is True
    vals = {p["key"]: p["value"] for p in body["policy_values"]}
    assert vals["sector_entry_min_pct"] == _CAND_ENTRY_MIN


@pytest.mark.parametrize("status", _NOT_STR_STATUS)
def test_candidate_status_not_string_is_unknown_not_500(api_client, status):
    """후보 정책 상태가 문자열이 아니면 `None` — 500 이 아니고 다른 칸은 그대로."""
    client, db = api_client
    _va, vc = _active_and_candidate(db)
    _edit_policy(db, vc, _set("policy_status", status))
    body = _state(client)
    assert body["payload_error"] is None
    assert body["candidate_version_id"] == vc
    assert body["candidate_policy_status"] is None
    assert body["candidate_policy_enabled"] is True
    assert body["policy_status"] == schema.POLICY_CONFIGURED


@pytest.mark.parametrize("edit", _UNKNOWN_ENABLED)
def test_active_unknown_with_enabled_candidate(api_client, edit):
    """검증자 재현의 비교 조합 — 활성 켜짐 여부 확인 불가 + 켜진 후보.

    지금 값은 `None`, 후보는 `True` · CONFIGURED 그대로라 화면이 '지금과 같음' · '지금 꺼짐
    → 켜짐' 같은 비교를 지어낼 근거(지금 값)가 응답에 없다.
    """
    client, db = api_client
    va, vc = _active_and_candidate(db)
    _edit_policy(db, va, edit)
    body = _state(client)
    assert body["payload_error"] is None
    assert body["active_version_id"] == va
    assert body["candidate_version_id"] == vc
    assert body["action_state"] == "pending_approval"
    assert body["policy_enabled"] is None
    assert body["policy_status"] == schema.POLICY_CONFIGURED
    assert body["candidate_policy_enabled"] is True
    assert body["candidate_policy_status"] == schema.POLICY_CONFIGURED
    vals = {p["key"]: p["value"] for p in body["policy_values"]}
    assert vals["sector_entry_min_pct"] == _CAND_ENTRY_MIN


def test_active_status_not_string_with_enabled_candidate(api_client):
    """활성 상태만 문자열이 아니면 그 칸만 `None` — 후보 칸은 그대로다."""
    client, db = api_client
    va, vc = _active_and_candidate(db)
    _edit_policy(db, va, _set("policy_status", 5))
    body = _state(client)
    assert body["payload_error"] is None
    assert body["policy_status"] is None
    assert body["policy_enabled"] is True
    assert body["candidate_policy_enabled"] is True
    assert body["candidate_policy_status"] == schema.POLICY_CONFIGURED


def test_both_unknown_stay_unknown(api_client):
    """활성 · 후보 모두 켜짐 여부가 문자열 "false" 면 둘 다 `None` — 한쪽이 다른 쪽을 메우지 않는다."""
    client, db = api_client
    va, vc = _active_and_candidate(db)
    _edit_policy(db, va, _set("enabled", "false"))
    _edit_policy(db, vc, _set("enabled", "false"))
    body = _state(client)
    assert body["payload_error"] is None
    assert body["policy_enabled"] is None
    assert body["candidate_policy_enabled"] is None
