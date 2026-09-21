"""POC3-02C-OPS-01 FIX — 검증자 REJECTED P1 6건의 통합 계약.

기존 `test_intraday_config_contracts.py` 는 **함수 단위**만 봤다. 그래서
`generate()` 가 어디서도 호출되지 않는 것, 승인 후 전달 실패한 버전이 조회에서
사라지는 것, 8단계 재독출 실패 시 OCI active 가 남는 것을 전부 놓쳤다.

여기서는 **운영 경로**를 본다 — 배선 · API 왕복 · 실패 후 재시도 · rollback.

라이브 DB·네트워크·Telegram 을 건드리지 않는다. ssh/scp 는 전부 대역.
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


def _make(tmp_path: Path, db: Path) -> str:
    out = generator.generate(state_db_path=db)
    assert out["status"] == "created", out
    return out["config_version_id"]


# ── P1-1 자동 산출 진입점 ───────────────────────────────────────────────────


def test_backend_startup_actually_calls_generate(tmp_path, monkeypatch):
    """**배선 테스트.** 함수가 있는 것과 불리는 것은 다르다.

    검증자 지적 1번이 정확히 이것이었다 — `generate()` 는 완성돼 있었지만
    호출자가 테스트와 역검증 스크립트뿐이었다.
    """
    from app.intraday_config import startup

    called: list[dict] = []
    monkeypatch.setattr(
        generator, "generate", lambda **kw: called.append(kw) or {"status": "created"}
    )
    startup.catch_up()
    assert called, "기동 catch-up 이 generate 를 부르지 않았다"


def test_lifespan_wires_catch_up():
    """`api.py` lifespan 이 catch-up 을 실제로 호출하는지 소스로 고정한다."""
    src = Path("app/api.py").read_text(encoding="utf-8")
    assert "intraday_startup.catch_up()" in src


def test_market_refresh_success_triggers_regeneration(monkeypatch):
    """시장 데이터 갱신 **성공 후** 재산출 (§10-3(2))."""
    from app import market_refresh_service as svc

    called: list[Path] = []
    monkeypatch.setattr(
        generator, "generate", lambda **kw: called.append(kw.get("db_path")) or {}
    )
    svc._regenerate_intraday_config(Path("x.sqlite"))
    assert called == [Path("x.sqlite")]


def test_catch_up_never_raises(monkeypatch):
    """기동을 막으면 안 된다."""
    from app.intraday_config import startup

    def boom(**_kw):
        raise RuntimeError("의도적 실패")

    monkeypatch.setattr(generator, "generate", boom)
    assert startup.catch_up()["status"] == "failed"


def test_regeneration_failure_does_not_break_refresh(monkeypatch):
    """재산출 실패가 시세 갱신을 실패로 뒤집으면 안 된다."""
    from app import market_refresh_service as svc

    def boom(**_kw):
        raise RuntimeError("의도적 실패")

    monkeypatch.setattr(generator, "generate", boom)
    svc._regenerate_intraday_config(Path("x.sqlite"))  # 예외가 새면 실패


# ── P1-2 배포 실패 후 재시도 대상 보존 ──────────────────────────────────────


def test_approved_but_failed_deploy_survives_refresh(tmp_path):
    """**새로고침 1회에 실패 상태와 재시도 버튼이 사라지면 안 된다.**

    수정 전에는 승인된 행이 `latest_candidate()` 에서 빠지고 active 도 아니라
    화면에서 통째로 없어졌다.
    """
    db = _db(tmp_path)
    vid = _make(tmp_path, db)
    store.approve(vid, approved_by="user", db_path=db)
    store.record_sync(vid, target="oci", status="scp_failed", error="boom", db_path=db)

    row, state = store.actionable_version(db_path=db)
    assert row is not None, "재시도 대상이 사라졌다"
    assert row["config_version_id"] == vid
    assert state == store.STATE_APPROVED_NOT_DEPLOYED


def test_retry_requires_no_reapproval(tmp_path):
    """재시도는 재승인을 요구하지 않는다 (§10-3(3))."""
    db = _db(tmp_path)
    vid = _make(tmp_path, db)
    store.approve(vid, approved_by="user", db_path=db)
    store.record_sync(vid, target="oci", status="scp_failed", db_path=db)
    # 승인 기록이 그대로 살아 있어 activate 가 바로 통과한다.
    store.activate(vid, activated_by="pc_deploy", db_path=db)
    assert store.get_active(db_path=db)["config_version_id"] == vid


def test_successful_deploy_clears_the_action(tmp_path):
    """전달에 성공하면 할 일이 없어야 한다 — 재시도 버튼이 남으면 안 된다."""
    db = _db(tmp_path)
    vid = _make(tmp_path, db)
    store.approve(vid, approved_by="user", db_path=db)
    store.activate(vid, activated_by="pc_deploy", db_path=db)
    assert store.actionable_version(db_path=db) == (None, None)


def test_unapproved_candidate_is_pending_approval(tmp_path):
    db = _db(tmp_path)
    _make(tmp_path, db)
    _, state = store.actionable_version(db_path=db)
    assert state == store.STATE_PENDING_APPROVAL


def test_rejected_version_is_not_actionable(tmp_path):
    db = _db(tmp_path)
    vid = _make(tmp_path, db)
    store.reject(vid, rejected_by="user", reason="싫다", db_path=db)
    assert store.actionable_version(db_path=db) == (None, None)


# ── P1-3 실패 시 OCI active 보존 ────────────────────────────────────────────


def _export(row: dict, path: Path) -> Path:
    """`apply_file` 이 읽는 전송 JSON 형식."""
    path.write_text(
        json.dumps(
            {
                k: row[k]
                for k in (
                    "config_version_id",
                    "schema_version",
                    "created_at",
                    "rule_version",
                    "evaluation_input_hash",
                    "effective_config_hash",
                    "source_hash_sha256",
                    "payload_json",
                    "approved_at",
                    "approved_by",
                )
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def test_apply_file_rolls_back_active_on_readback_mismatch(tmp_path, monkeypatch):
    """**실제 체인을 탄다.** `apply_file()` → activate → 재독출 실패 → rollback.

    이전 판에서는 `_restore()` 만 직접 불러서, activate→readback→rollback 배선이
    끊겨도 통과했다(검증자 r2 P2).
    """
    import scripts.apply_intraday_config_oci as apply_mod
    from app.intraday_config import store as store_mod

    db = _db(tmp_path)
    monkeypatch.setattr(store_mod._db, "DEFAULT_DB_PATH", db)

    v1 = _make(tmp_path, db)
    store.approve(v1, approved_by="user", db_path=db)
    store.activate(v1, activated_by="t", db_path=db)

    payload = json.loads(store.get_version(v1, db_path=db)["payload_json"])
    payload["sector_representative_universe"]["sectors"][0]["representative"][
        "ticker"
    ] = "777777"
    v2, _ = store.create_candidate(payload, evaluation_input_hash="h2", db_path=db)
    store.approve(v2, approved_by="user", db_path=db)
    row2 = store.get_version(v2, db_path=db)

    # 재독출만 어긋나게 한다. activate 는 진짜로 일어난다.
    monkeypatch.setattr(apply_mod, "_readback_matches", lambda row: (False, "hash"))
    rc = apply_mod.apply_file(_export(row2, tmp_path / "v2.json"))

    assert rc != 0, "재독출이 어긋났는데 성공을 반환했다"
    assert store.get_active(db_path=db)["config_version_id"] == v1, "되돌리지 않았다"


def test_apply_file_succeeds_and_activates_when_readback_matches(tmp_path, monkeypatch):
    """반대편 — 정상 경로에서는 실제로 active 가 바뀐다."""
    import scripts.apply_intraday_config_oci as apply_mod
    from app.intraday_config import store as store_mod

    db = _db(tmp_path)
    monkeypatch.setattr(store_mod._db, "DEFAULT_DB_PATH", db)
    vid = _make(tmp_path, db)
    store.approve(vid, approved_by="user", db_path=db)
    row = store.get_version(vid, db_path=db)

    rc = apply_mod.apply_file(_export(row, tmp_path / "v.json"))
    assert rc == 0
    assert store.get_active(db_path=db)["config_version_id"] == vid


def test_rollback_to_empty_when_there_was_no_active(tmp_path, monkeypatch):
    """최초 전달이 실패하면 되돌릴 자리가 없다 — pointer 를 지운다."""
    db = _db(tmp_path)
    vid = _make(tmp_path, db)
    store.approve(vid, approved_by="user", db_path=db)
    store.activate(vid, activated_by="t", db_path=db)
    store.clear_active(db_path=db)
    assert store.get_active(db_path=db) is None


def test_pc_no_longer_does_a_second_readback_ssh():
    """재독출을 PC 가 **따로** 하면 그 왕복 실패가 active 를 남긴다.

    원격 안에서 끝내는 구조를 소스로 고정한다.
    """
    src = Path("scripts/sync_intraday_config.py").read_text(encoding="utf-8")
    assert "_parse_ok(out)" in src
    assert "readback_failed" not in src, "PC 측 별도 재독출 ssh 가 남아 있다"


def test_remote_apply_reads_back_and_can_restore():
    src = Path("scripts/apply_intraday_config_oci.py").read_text(encoding="utf-8")
    assert "_readback_matches" in src
    assert "_restore(before_id" in src


# ── P1-4 승인 후 기각본 활성화 차단 ─────────────────────────────────────────


def test_approved_then_rejected_cannot_activate(tmp_path):
    """**검증자가 직접 재현에 성공한 결함.**

    `reject()` 가 승인 필드를 남겼고 `activate()` 가 기각을 안 봤다.
    """
    db = _db(tmp_path)
    vid = _make(tmp_path, db)
    store.approve(vid, approved_by="user", db_path=db)
    store.reject(vid, rejected_by="user", reason="다시 보니 아니다", db_path=db)

    with pytest.raises(store.ApprovalRequired):
        store.activate(vid, activated_by="t", db_path=db)
    assert store.get_active(db_path=db) is None


def test_reject_clears_approval_fields(tmp_path):
    db = _db(tmp_path)
    vid = _make(tmp_path, db)
    store.approve(vid, approved_by="user", db_path=db)
    store.reject(vid, rejected_by="user", reason="x", db_path=db)
    row = store.get_version(vid, db_path=db)
    assert row["approved_at"] is None and row["approved_by"] is None


def test_activate_checks_rejection_directly(tmp_path):
    """승인 필드가 남아 있어도 기각본이면 막혀야 한다.

    `reject()` 가 승인을 지우는 것에만 기대면 안 된다 — 승인을 남기는 경로가
    하나라도 생기면 뚫린다.
    """
    import sqlite3

    db = _db(tmp_path)
    vid = _make(tmp_path, db)
    store.approve(vid, approved_by="user", db_path=db)
    store.reject(vid, rejected_by="user", reason="x", db_path=db)
    con = sqlite3.connect(db)
    con.execute(
        "UPDATE intraday_alert_config_version SET approved_at=?, approved_by=? "
        "WHERE config_version_id=?",
        ("2026-01-01T00:00:00Z", "user", vid),
    )
    con.commit()
    con.close()

    with pytest.raises(store.ApprovalRequired):
        store.activate(vid, activated_by="t", db_path=db)


# ── P1-5 시총 결측 fallback 제거 ────────────────────────────────────────────


def test_unpriced_candidate_cannot_be_representative(tmp_path):
    """**가격 없는 ETF 가 시총 1위로 조용히 뽑히면 안 된다.**

    수정 전에는 `market_cap or 0.0` 이라 전원 결측이면 ticker 오름차순으로
    고르고도 `metric="market_cap"` 이라 적었다.
    """
    sectors, excluded, _ = selector.build_sectors(csv_path=CSV, db_path=DB)
    for s in sectors:
        basis = s["selection_basis"]
        assert basis["representative_market_cap"], s["sector_key"]
    assert not [e for e in excluded if e["reason"] == "sector_no_market_cap"]


def test_sector_without_any_price_is_excluded_not_guessed(tmp_path, monkeypatch):
    """모든 후보가 시총 미상이면 대표를 만들지 않고 **사유를 남긴다.**"""
    monkeypatch.setattr(selector, "latest_closes", lambda db_path: ("2026-09-11", {}))
    sectors, excluded, _ = selector.build_sectors(csv_path=CSV, db_path=DB)
    assert sectors == [], "가격이 하나도 없는데 대표가 선정됐다"
    assert [e for e in excluded if e["reason"] == "sector_no_market_cap"]


def test_selection_basis_records_the_actual_value(tmp_path):
    """값이 없으면 근거가 없는 것이다 — 값을 남겨야 결측이 보인다."""
    sectors, _, _ = selector.build_sectors(csv_path=CSV, db_path=DB)
    b = sectors[0]["selection_basis"]
    assert set(b) >= {
        "metric",
        "representative_market_cap",
        "unpriced_candidate_count",
    }


def test_representative_is_the_largest_by_market_cap(tmp_path):
    """규칙이 실제로 적용되는지 — 라벨이 아니라 순서로 확인한다."""
    sectors, _, _ = selector.build_sectors(csv_path=CSV, db_path=DB)
    for s in sectors:
        b = s["selection_basis"]
        if b.get("alternate_market_cap"):
            assert b["representative_market_cap"] >= b["alternate_market_cap"]


# ── P1-6 토큰 사전은 번들 데이터 ────────────────────────────────────────────


def test_dictionary_source_is_data_not_code(tmp_path):
    """설계 §10-2 — 사전은 코드 하드코딩이 아니라 번들 데이터다."""
    src = Path("app/intraday_config/selector.py").read_text(encoding="utf-8")
    # 설명문에 사업군 이름이 나오는 것은 상관없다. 금지되는 것은 **매핑 리터럴**
    # (`"반도체": [...]`) 이 소스에 있는 것이다.
    literals = [k for k in selector.load_token_dictionary()[0] if f'"{k}": [' in src]
    assert not literals, f"사업군 토큰이 아직 코드 상수로 남아 있다: {literals}"
    assert selector.TOKEN_DICTIONARY_PATH.exists()


def test_dictionary_loads_from_bundle_file():
    d, sha = selector.load_token_dictionary()
    assert len(d) >= 20 and len(sha) == 64


def test_missing_dictionary_does_not_fall_back_to_code(tmp_path):
    """파일이 없으면 **올린다.** 조용히 옛 사전으로 분류하면 승인 내용과 갈린다."""
    with pytest.raises(selector.TokenDictionaryError):
        selector.load_token_dictionary(tmp_path / "없음.json")


def test_corrupt_dictionary_is_rejected(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text('{"schema_version": "wrong", "sectors": {}}', encoding="utf-8")
    with pytest.raises(selector.TokenDictionaryError):
        selector.load_token_dictionary(p)


def test_dictionary_change_creates_a_new_approval_candidate(tmp_path):
    """사전을 고치면 새 승인 후보가 생긴다 — 승인 없이 분류가 바뀌면 안 된다."""
    db = _db(tmp_path)
    v1 = _make(tmp_path, db)
    payload = json.loads(store.get_version(v1, db_path=db)["payload_json"])
    assert payload["sector_representative_universe"]["token_dictionary"]
    small = {"반도체": ["반도체"]}
    sectors, excluded, asof = selector.build_sectors(
        csv_path=CSV, db_path=DB, dictionary=small
    )
    p2 = schema.build_payload(
        rule_version=selector.RULE_VERSION,
        sectors=sectors,
        token_dictionary=small,
        data_asof=asof,
        excluded=excluded,
    )
    v2, created = store.create_candidate(p2, evaluation_input_hash="h2", db_path=db)
    assert created and v2 != v1


# ── API 왕복 — 승인 → 전달 실패 → 새로고침 → 재시도 ─────────────────────────
#
# 검증자 B-6: "API 승인·실패·새로고침·재시도 흐름의 통합 테스트가 없다."
# 라이브 DB 를 쓰지 않도록 store 의 기본 DB 경로를 tmp 로 돌린다.


@pytest.fixture()
def api_client(tmp_path, monkeypatch):
    """API 를 **tmp DB 로만** 돌린다. 라이브 runtime_state.sqlite 를 쓰지 않는다.

    함수를 하나씩 감싸지 않고 `store` 가 기본 경로를 읽는 **한 곳**을 돌린다.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import app.api_intraday_config as api_mod
    from app.intraday_config import store as store_mod

    db = _db(tmp_path)
    monkeypatch.setattr(store_mod._db, "DEFAULT_DB_PATH", db)

    application = FastAPI()
    application.include_router(api_mod.router)
    return TestClient(application), db


def test_api_state_is_empty_before_any_generation(api_client):
    """지금 화면이 0개로 비어 있는 이유 — 산출이 한 번도 안 돌았을 때의 상태."""
    client, _ = api_client
    body = client.get("/intraday-config/state").json()
    assert body["candidate_version_id"] is None
    assert body["action_state"] is None
    assert body["candidate_sector_count"] == 0


def test_api_shows_candidate_after_generation(api_client, tmp_path):
    client, db = api_client
    _make(tmp_path, db)
    body = client.get("/intraday-config/state").json()
    assert body["action_state"] == store.STATE_PENDING_APPROVAL
    assert body["candidate_sector_count"] >= 20


def test_api_retry_survives_refresh_after_failed_deploy(api_client, tmp_path):
    """**이 라운드의 핵심 회귀.**

    승인 → 전달 실패 → 새로고침. 예전에는 여기서 후보가 통째로 사라져
    실패 상태도 재시도 버튼도 없어졌다.
    """
    client, db = api_client
    vid = _make(tmp_path, db)
    store.approve(vid, approved_by="user", db_path=db)
    store.record_sync(vid, target="oci", status="scp_failed", error="boom", db_path=db)

    body = client.get("/intraday-config/state").json()  # 새로고침
    assert body["candidate_version_id"] == vid
    assert body["action_state"] == store.STATE_APPROVED_NOT_DEPLOYED
    assert body["deploy_status"] == "scp_failed"
    assert body["deploy_error"] == "boom"


def test_api_action_clears_after_successful_deploy(api_client, tmp_path):
    client, db = api_client
    vid = _make(tmp_path, db)
    store.approve(vid, approved_by="user", db_path=db)
    store.activate(vid, activated_by="pc_deploy", db_path=db)
    body = client.get("/intraday-config/state").json()
    assert body["action_state"] is None
    assert body["active_version_id"] == vid


def test_api_reject_removes_the_action(api_client, tmp_path):
    client, db = api_client
    vid = _make(tmp_path, db)
    r = client.post(
        "/intraday-config/reject",
        json={"config_version_id": vid, "rejected_by": "user", "reason": "x"},
    )
    assert r.status_code == 200 and r.json()["ok"]
    assert client.get("/intraday-config/state").json()["action_state"] is None


def test_api_never_sends_telegram_or_touches_network(api_client, tmp_path):
    """이 Step 의 API 는 발송 경로가 아니다."""
    src = Path("app/api_intraday_config.py").read_text(encoding="utf-8")
    for banned in ("telegram", "requests.", "urlopen", "naver"):
        assert banned not in src.lower()


# ── r2 REJECTED — 다중 버전 상태 전이 ───────────────────────────────────────
#
# r1 수정은 **승인본이 하나뿐인 경우**만 봤다. 그래서 정상적인 2회 배포에서
# 옛 버전이 재시도 대상으로 되살아나는 것을 놓쳤다.


def _second_version(tmp_path, db, base_vid: str) -> str:
    payload = json.loads(store.get_version(base_vid, db_path=db)["payload_json"])
    payload["sector_representative_universe"]["sectors"][0]["representative"][
        "ticker"
    ] = "777777"
    vid, created = store.create_candidate(
        payload, evaluation_input_hash="h-v2", db_path=db
    )
    assert created
    return vid


def test_past_deployed_version_is_not_offered_for_retry(tmp_path):
    """**검증자 r2 재현.** v1 배포 → v2 배포 후, v1 이 재시도 대상이면 안 된다.

    옛 조회는 "active 가 아닌 승인본" 을 물어 v1 을 그대로 집어냈다. 그러면
    화면이 **옛 설정을 OCI 에 재배포하라고** 권한다.
    """
    db = _db(tmp_path)
    v1 = _make(tmp_path, db)
    store.approve(v1, approved_by="user", db_path=db)
    store.activate(v1, activated_by="pc_deploy", db_path=db)

    v2 = _second_version(tmp_path, db, v1)
    store.approve(v2, approved_by="user", db_path=db)
    store.activate(v2, activated_by="pc_deploy", db_path=db)

    row, state = store.actionable_version(db_path=db)
    assert (row, state) == (None, None), f"옛 버전이 되살아났다: {row}, {state}"


def test_only_the_latest_version_is_actionable(tmp_path):
    """최신본만 조치 대상이다. 과거는 이력이다."""
    db = _db(tmp_path)
    v1 = _make(tmp_path, db)
    store.approve(v1, approved_by="user", db_path=db)
    store.activate(v1, activated_by="pc_deploy", db_path=db)

    v2 = _second_version(tmp_path, db, v1)
    row, state = store.actionable_version(db_path=db)
    assert row["config_version_id"] == v2
    assert state == store.STATE_PENDING_APPROVAL


def test_newest_version_failed_deploy_still_offers_retry(tmp_path):
    """다중 버전이어도 **최신본의** 전달 실패는 재시도로 남아야 한다."""
    db = _db(tmp_path)
    v1 = _make(tmp_path, db)
    store.approve(v1, approved_by="user", db_path=db)
    store.activate(v1, activated_by="pc_deploy", db_path=db)

    v2 = _second_version(tmp_path, db, v1)
    store.approve(v2, approved_by="user", db_path=db)
    store.record_sync(v2, target="oci", status="scp_failed", db_path=db)

    row, state = store.actionable_version(db_path=db)
    assert row["config_version_id"] == v2
    assert state == store.STATE_APPROVED_NOT_DEPLOYED


def test_rejecting_newest_falls_back_to_no_action(tmp_path):
    """최신본을 기각하면 운영 중인 v1 만 남는다 — 할 일 없음."""
    db = _db(tmp_path)
    v1 = _make(tmp_path, db)
    store.approve(v1, approved_by="user", db_path=db)
    store.activate(v1, activated_by="pc_deploy", db_path=db)

    v2 = _second_version(tmp_path, db, v1)
    store.reject(v2, rejected_by="user", reason="x", db_path=db)
    assert store.actionable_version(db_path=db) == (None, None)


# ── r2 REJECTED — 재시도가 승인 기록을 다시 쓰지 않는다 ─────────────────────


def test_retry_does_not_rewrite_approved_at(api_client, tmp_path, monkeypatch):
    """**승인은 멱등이다.** 재시도할 때마다 승인 시각이 바뀌면 안 된다."""
    import app.api_intraday_config as api_mod

    client, db = api_client
    vid = _make(tmp_path, db)
    monkeypatch.setattr(
        "scripts.sync_intraday_config.deploy", lambda _v: (False, "scp_failed")
    )

    r1 = client.post(
        "/intraday-config/approve-and-apply",
        json={"config_version_id": vid, "approved_by": "user"},
    )
    assert r1.status_code == 200 and not r1.json()["ok"]
    first = store.get_version(vid, db_path=db)["approved_at"]

    r2 = client.post(  # 재시도
        "/intraday-config/approve-and-apply",
        json={"config_version_id": vid, "approved_by": "user"},
    )
    assert r2.status_code == 200
    assert store.get_version(vid, db_path=db)["approved_at"] == first
    assert api_mod.DEPLOY_APPROVED_NOT_DEPLOYED == r2.json()["deploy_status"]


def test_rejected_version_cannot_be_applied(api_client, tmp_path):
    client, db = api_client
    vid = _make(tmp_path, db)
    store.reject(vid, rejected_by="user", reason="x", db_path=db)
    r = client.post(
        "/intraday-config/approve-and-apply",
        json={"config_version_id": vid, "approved_by": "user"},
    )
    assert r.status_code == 409


# ── r2 REJECTED — 운영 중 버전 기각 금지 ────────────────────────────────────


def test_cannot_reject_the_active_version(tmp_path):
    """**활성 설정이 동시에 기각 상태**가 되는 모순을 막는다."""
    db = _db(tmp_path)
    vid = _make(tmp_path, db)
    store.approve(vid, approved_by="user", db_path=db)
    store.activate(vid, activated_by="pc_deploy", db_path=db)

    with pytest.raises(store.CannotRejectActive):
        store.reject(vid, rejected_by="user", reason="x", db_path=db)

    row = store.get_version(vid, db_path=db)
    assert row["rejected_at"] is None and row["approved_at"]
    assert store.get_active(db_path=db)["config_version_id"] == vid


def test_reject_active_returns_409(api_client, tmp_path):
    client, db = api_client
    vid = _make(tmp_path, db)
    store.approve(vid, approved_by="user", db_path=db)
    store.activate(vid, activated_by="pc_deploy", db_path=db)
    r = client.post(
        "/intraday-config/reject",
        json={"config_version_id": vid, "rejected_by": "user", "reason": "x"},
    )
    assert r.status_code == 409


# ── r2 REJECTED — 원격 적용 성공 후 SSH 실패 ────────────────────────────────


def test_cleanup_rm_is_not_chained_to_apply():
    """`; rm` 을 붙이면 rc 가 정리 명령에서 나와 성공이 실패로 보고된다."""
    src = Path("scripts/sync_intraday_config.py").read_text(encoding="utf-8")
    assert "; rm -f {remote_apply}" not in src
    # 정리는 `cleanup()` 한 곳에서 한다 — 적용 명령에 붙이지 않는다.
    assert "rm -f {remote_tmp} {remote_apply}" in src
    assert "cleanup()" in src


def _sync_env(monkeypatch, tmp_path, db, reads):
    """`deploy()` 를 원격 없이 돌린다. 조회 결과만 `reads` 로 주입한다."""
    import scripts.sync_intraday_config as sync
    from app.intraday_config import store as store_mod

    monkeypatch.setattr(store_mod._db, "DEFAULT_DB_PATH", db)
    monkeypatch.setattr(sync, "_ssh_target", lambda: "fake")
    monkeypatch.setattr(sync, "export_json", lambda v: tmp_path / "x.json")

    seq = list(reads)
    applied: list = []
    writes: list = []  # **원격을 바꾸는 모든 명령** — scp · mv · rm 포함
    slept: list[float] = []

    def fake_active(_t):
        return seq.pop(0) if seq else (False, None, None)

    def fake_run(cmd, timeout=120.0):
        joined = " ".join(map(str, cmd))
        # `--json` 만 보면 그 앞의 scp·mv 를 놓친다(검증자 지적).
        if cmd[0] == "scp" or (
            cmd[0] == "ssh" and any(w in joined for w in ("mv ", "rm ", "> "))
        ):
            writes.append(cmd)
        if cmd[0] == "ssh" and "--json" in joined:
            applied.append(cmd)
            return 255, "ssh: connection closed"  # 모호한 실패
        return 0, "OK"

    monkeypatch.setattr(sync, "_remote_active", fake_active)
    monkeypatch.setattr(sync, "_run", fake_run)
    monkeypatch.setattr(sync.time, "sleep", lambda d: slept.append(d))
    return sync, applied, slept, writes


# ── 설계자 확정 read-back 재시도 (2026-09-18) ───────────────────────────────


def test_reconcile_confirms_deployed_after_two_failed_reads(monkeypatch, tmp_path):
    """**1·2회 조회 실패 후 3회차에 확인 성공** → `deployed`."""
    db = _db(tmp_path)
    vid = _make(tmp_path, db)
    store.approve(vid, approved_by="user", db_path=db)
    want = store.get_version(vid, db_path=db)["source_hash_sha256"]

    sync, applied, slept, writes = _sync_env(
        monkeypatch,
        tmp_path,
        db,
        [
            (True, None, None),  # 적용 전 조회 (직전 active 없음)
            (False, None, None),  # 1차 실패
            (False, None, None),  # 2차 실패
            (True, vid, want),  # 3차 확인
        ],
    )
    ok, err = sync.deploy(vid, ssh_target="fake")
    assert ok is True and err is None
    assert len(applied) == 1, "apply 를 자동 재실행했다"
    assert slept == [2.0, 5.0], slept
    assert store.get_active(db_path=db)["config_version_id"] == vid


def test_reconcile_confirms_prior_active_kept(monkeypatch, tmp_path):
    """**직전 version/hash 확인** → `remote_apply_failed` (적용 안 됨)."""
    db = _db(tmp_path)
    v1 = _make(tmp_path, db)
    store.approve(v1, approved_by="user", db_path=db)
    store.activate(v1, activated_by="t", db_path=db)
    h1 = store.get_version(v1, db_path=db)["source_hash_sha256"]
    v2 = _second_version(tmp_path, db, v1)
    store.approve(v2, approved_by="user", db_path=db)

    sync, applied, _, writes = _sync_env(
        monkeypatch, tmp_path, db, [(True, v1, h1), (True, v1, h1)]
    )
    ok, err = sync.deploy(v2, ssh_target="fake")
    assert ok is False and err == "remote_apply_failed", err
    assert len(applied) == 1
    assert store.get_active(db_path=db)["config_version_id"] == v1


def test_three_failed_reads_are_unconfirmed(monkeypatch, tmp_path):
    """**3회 전부 조회 실패** → `deploy_unconfirmed`. 완료·실패로 단정 안 함."""
    db = _db(tmp_path)
    vid = _make(tmp_path, db)
    store.approve(vid, approved_by="user", db_path=db)

    sync, applied, slept, writes = _sync_env(
        monkeypatch,
        tmp_path,
        db,
        [
            (True, None, None),
            (False, None, None),
            (False, None, None),
            (False, None, None),
        ],
    )
    ok, err = sync.deploy(vid, ssh_target="fake")
    assert ok is False and err == "deploy_unconfirmed", err
    assert len(applied) == 1, "자동 재적용이 일어났다"
    assert slept == [2.0, 5.0]
    # PC 를 완료로 표시하지 않는다.
    assert store.get_active(db_path=db) is None


def test_unexpected_version_is_unconfirmed(monkeypatch, tmp_path):
    """**예상 밖 version/hash** → `deploy_unconfirmed`. 추정하지 않는다."""
    db = _db(tmp_path)
    vid = _make(tmp_path, db)
    store.approve(vid, approved_by="user", db_path=db)

    sync, applied, _, writes = _sync_env(
        monkeypatch,
        tmp_path,
        db,
        [(True, None, None)] + [(True, "intraday-누구세요", "f" * 64)] * 3,
    )
    ok, err = sync.deploy(vid, ssh_target="fake")
    assert ok is False and err == "deploy_unconfirmed", err
    assert len(applied) == 1
    assert store.get_active(db_path=db) is None


def test_no_automatic_reapply_in_any_reconcile_path(monkeypatch, tmp_path):
    """`AUTOMATIC_REAPPLY = FORBIDDEN` — 어느 경로에서도 apply 는 1회뿐이다."""
    db = _db(tmp_path)
    vid = _make(tmp_path, db)
    store.approve(vid, approved_by="user", db_path=db)
    want = store.get_version(vid, db_path=db)["source_hash_sha256"]

    for reads in (
        [(True, None, None), (True, vid, want)],
        [
            (True, None, None),
            (False, None, None),
            (False, None, None),
            (False, None, None),
        ],
        [(True, None, None)] + [(True, "other", "f" * 64)] * 3,
    ):
        store.clear_active(db_path=db)
        sync, applied, _, writes = _sync_env(monkeypatch, tmp_path, db, reads)
        sync.deploy(vid, ssh_target="fake")
        assert len(applied) == 1, f"{reads} 에서 apply {len(applied)}회"


def test_reconcile_is_read_only():
    """재시도 경로에 원격 쓰기 명령이 없어야 한다."""
    src = Path("scripts/sync_intraday_config.py").read_text(encoding="utf-8")
    start = src.index("def reconcile_after_apply")
    end = src.index("def _parse_ok")
    body = src[start:end]
    for banned in ("activate(", "clear_active", "s.approve", "rm -f"):
        assert banned not in body, banned


# ── r3 REJECTED — stale 화면 · 사전조회 실패 · 손상 payload ─────────────────


def test_stale_screen_cannot_apply_an_older_candidate(api_client, tmp_path):
    """**화면을 오래 열어둔 사이 새 후보가 나면 옛 버전은 못 보낸다.**

    조회는 최신본만 보여주는데 승인 API 가 옛 버전을 받으면, 화면과 실제로
    나가는 설정이 갈린다(검증자 r3).
    """
    client, db = api_client
    v1 = _make(tmp_path, db)
    v2 = _second_version(tmp_path, db, v1)

    assert store.actionable_version(db_path=db)[0]["config_version_id"] == v2
    r = client.post(
        "/intraday-config/approve-and-apply",
        json={"config_version_id": v1, "approved_by": "user"},
    )
    assert r.status_code == 409, r.text
    assert "새로고침" in r.json()["detail"]
    # 옛 버전이 승인되지 않았다.
    assert store.get_version(v1, db_path=db)["approved_at"] is None


def test_current_actionable_version_still_applies(api_client, tmp_path, monkeypatch):
    """게이트가 정상 경로를 막으면 안 된다."""
    client, db = api_client
    vid = _make(tmp_path, db)
    monkeypatch.setattr(
        "scripts.sync_intraday_config.deploy", lambda _v: (False, "scp_failed")
    )
    r = client.post(
        "/intraday-config/approve-and-apply",
        json={"config_version_id": vid, "approved_by": "user"},
    )
    assert r.status_code == 200
    assert store.get_version(vid, db_path=db)["approved_at"]


def test_retry_of_the_current_version_passes_the_gate(
    api_client, tmp_path, monkeypatch
):
    """재시도 대상(`approved_not_deployed`)도 게이트를 통과해야 한다."""
    client, db = api_client
    vid = _make(tmp_path, db)
    store.approve(vid, approved_by="user", db_path=db)
    store.record_sync(vid, target="oci", status="scp_failed", db_path=db)
    monkeypatch.setattr(
        "scripts.sync_intraday_config.deploy", lambda _v: (False, "scp_failed")
    )
    r = client.post(
        "/intraday-config/approve-and-apply",
        json={"config_version_id": vid, "approved_by": "user"},
    )
    assert r.status_code == 200, r.text


def test_deploy_writes_nothing_remote_when_precheck_fails(monkeypatch, tmp_path):
    """**되돌릴 기준이 없으면 원격에 아무것도 쓰지 않는다.**

    예전에는 precheck 이 scp·mv·스크립트 업로드 **뒤**에 있어서,
    `precheck_failed` 를 반환하면서도 원격 정본 JSON 이 이미 교체돼 있었고
    임시 적용 스크립트도 남았다(검증자 지적 · OCI 실측으로 파일 2개 확인).

    `--json` 명령만 세면 그 앞의 scp·mv 를 놓친다. **모든 쓰기 명령**을 센다.
    """
    db = _db(tmp_path)
    vid = _make(tmp_path, db)
    store.approve(vid, approved_by="user", db_path=db)

    sync, applied, _slept, writes = _sync_env(
        monkeypatch, tmp_path, db, [(False, None, None)]
    )
    ok, reason = sync.deploy(vid, ssh_target="fake")
    assert ok is False and reason == "precheck_failed", reason
    assert not applied, "적용을 시작했다"
    assert not writes, f"원격에 썼다: {writes}"


def test_precheck_runs_before_any_remote_write():
    """소스 순서로 고정한다 — precheck 이 scp 보다 앞이어야 한다."""
    src = Path("scripts/sync_intraday_config.py").read_text(encoding="utf-8")
    body = src[src.index("def deploy(") :]  # noqa: E203
    assert body.index("prior_read_ok") < body.index(
        '"scp"'
    ), "precheck 이 scp 뒤에 있다"


def test_temp_apply_script_is_cleaned_on_failure(monkeypatch, tmp_path):
    """업로드 뒤 실패해도 **임시 적용 스크립트를 남기지 않는다.**"""
    db = _db(tmp_path)
    vid = _make(tmp_path, db)
    store.approve(vid, approved_by="user", db_path=db)

    sync, _applied, _slept, writes = _sync_env(
        monkeypatch, tmp_path, db, [(True, None, None)] * 4
    )
    sync.deploy(vid, ssh_target="fake")
    rm = [c for c in writes if "rm -f" in " ".join(map(str, c))]
    assert rm, "정리 명령이 실행되지 않았다"
    assert any(".apply_intraday_config_oci.py" in " ".join(map(str, c)) for c in rm)


@pytest.mark.parametrize(
    "break_at,expect",
    [
        ("scp_json", "scp_failed"),
        ("mv", "rename_failed"),
        ("scp_apply", "apply_upload_failed"),
    ],
)
def test_every_post_upload_failure_cleans_up(monkeypatch, tmp_path, break_at, expect):
    """**업로드 뒤 모든 실패 분기**가 임시 파일을 지운다.

    이전에는 apply 실행 실패 경로만 직접 태워서, 앞쪽 분기가 정리를 건너뛰어도
    테스트가 통과했다(검증자 r7).
    """
    import scripts.sync_intraday_config as sync
    from app.intraday_config import store as store_mod

    db = _db(tmp_path)
    monkeypatch.setattr(store_mod._db, "DEFAULT_DB_PATH", db)
    vid = _make(tmp_path, db)
    store.approve(vid, approved_by="user", db_path=db)

    monkeypatch.setattr(sync, "_ssh_target", lambda: "fake")
    monkeypatch.setattr(sync, "export_json", lambda v: tmp_path / "x.json")
    monkeypatch.setattr(sync, "_remote_active", lambda t: (True, None, None))

    cleaned: list = []

    def fake_run(cmd, timeout=120.0):
        joined = " ".join(map(str, cmd))
        if "rm -f" in joined:
            cleaned.append(joined)
            return 0, "OK"
        if break_at == "scp_json" and cmd[0] == "scp" and "x.json" in joined:
            return 1, "scp 실패"
        if break_at == "mv" and "mv " in joined:
            return 1, "mv 실패"
        if break_at == "scp_apply" and cmd[0] == "scp" and "apply_" in joined:
            return 1, "scp 실패"
        return 0, "OK"

    monkeypatch.setattr(sync, "_run", fake_run)
    ok, reason = sync.deploy(vid, ssh_target="fake")
    assert ok is False and reason == expect, reason
    assert cleaned, f"{break_at} 실패 시 정리하지 않았다"
    assert any(".apply_intraday_config_oci.py" in c for c in cleaned)


def test_rollback_impossible_path_is_gone():
    src = Path("scripts/sync_intraday_config.py").read_text(encoding="utf-8")
    body = "\n".join(ln for ln in src.splitlines() if not ln.strip().startswith("#"))
    assert "rollback_impossible" not in body


def test_corrupt_payload_is_surfaced_not_hidden(api_client, tmp_path):
    """**깨진 설정을 '0개 사업군' 으로 보이게 하지 않는다.**"""
    import sqlite3

    import app.api_intraday_config as api_mod

    client, db = api_client
    vid = _make(tmp_path, db)
    con = sqlite3.connect(db)
    con.execute(
        "UPDATE intraday_alert_config_version SET payload_json=? "
        "WHERE config_version_id=?",
        ("{깨진 JSON", vid),
    )
    con.commit()
    con.close()

    with pytest.raises(api_mod.PayloadCorrupt):
        api_mod._payload(store.get_version(vid, db_path=db))

    body = client.get("/intraday-config/state").json()
    assert body["payload_error"], "손상이 드러나지 않았다"
    assert vid in body["payload_error"]
    # 정상적으로 비어 있는 것처럼 보이면 안 된다.
    assert body["candidate_version_id"] == vid


def test_healthy_payload_has_no_error(api_client, tmp_path):
    client, db = api_client
    _make(tmp_path, db)
    body = client.get("/intraday-config/state").json()
    assert body["payload_error"] is None
    assert body["candidate_sector_count"] >= 20


# ── OPS-03 §2·§3 — 생성 번들이 정책을 담는다 ───────────────────────────────
#
# 전에는 `generate()` 가 `build_payload()` 에 `policy=` 를 넘기지 않아 스키마
# 기본값(`enabled=False`)이 들어갔다. 그래서 장중 알림을 **켤 방법이 없었다**.
# 사용자가 임계값을 하나씩 넣는 화면은 만들지 않는다 — PC 가 산출한 버전을
# 통째로 승인하는 것이 계약이다.


def test_generated_bundle_carries_enabled_policy(tmp_path):
    """산출 번들에 `enabled=true` 정책이 들어간다."""
    db = _db(tmp_path)
    vid = _make(tmp_path, db)
    payload = json.loads(store.get_version(vid, db_path=db)["payload_json"])
    policy = payload["intraday_alert_policy"]
    assert policy["enabled"] is True
    assert policy["policy_status"] == schema.POLICY_CONFIGURED


def test_generated_policy_has_all_twelve_keys_in_range(tmp_path):
    """12개 키가 전부 있고 범위 안이다. 하나라도 빠지면 `validate` 가 막는다."""
    db = _db(tmp_path)
    vid = _make(tmp_path, db)
    policy = json.loads(store.get_version(vid, db_path=db)["payload_json"])[
        "intraday_alert_policy"
    ]
    missing = [k for k in schema.REQUIRED_POLICY_KEYS if policy.get(k) is None]
    assert missing == [], f"누락: {missing}"
    for key, lo, hi in schema.POLICY_RANGES:
        assert lo <= policy[key] <= hi, f"{key}={policy[key]} 범위 [{lo}, {hi}] 밖"


def test_generated_policy_matches_designer_confirmed_values(tmp_path):
    """설계자 §3 이 값까지 못박은 것과 일치한다.

    임의 생성 금지 — 이 표가 바뀌면 설계자 확정이 바뀐 것이어야 한다.
    """
    db = _db(tmp_path)
    vid = _make(tmp_path, db)
    policy = json.loads(store.get_version(vid, db_path=db)["payload_json"])[
        "intraday_alert_policy"
    ]
    for key, want in {
        "cooldown_minutes": 120,
        "max_sends_per_day": 4,
        "max_items_per_section": 3,
        "sector_entry_min_pct": 1.5,
        "sector_chase_pct": 4.0,
        "sector_avoid_drop_pct": -1.5,
        "sector_rank_top_pct": 20.0,
        "sector_min_coverage_pct": 80.0,
        # §3 목록 밖 — 설계서 확정값(§13-1 구간 · §6 회차 상한 · §5 창)
        "surge_threshold_pct": 5.0,
        "drop_threshold_pct": -5.0,
        "max_sends_per_run": 1,
        "dedup_window_minutes": 120,
    }.items():
        assert policy[key] == want, f"{key}: {policy[key]} != {want}"


def test_policy_is_not_silently_taken_from_schema_defaults(tmp_path):
    """**스키마 기본값 주입이 아니라** 생성부가 명시한 값이다(설계자 지시).

    `CONFIRMED_POLICY` 를 바꾸면 산출 번들도 바뀌어야 한다. 기본값에서 조용히
    오는 구조면 이 테스트가 잡는다.
    """
    db = _db(tmp_path)
    from unittest.mock import patch

    tweaked = dict(generator.CONFIRMED_POLICY)
    # `dedup_window_minutes` 는 별칭이라 **함께** 옮겨야 한다(OPS-03 보완).
    tweaked["cooldown_minutes"] = 90
    tweaked["dedup_window_minutes"] = 90
    with patch.object(generator, "CONFIRMED_POLICY", tweaked):
        vid = _make(tmp_path, db)
    policy = json.loads(store.get_version(vid, db_path=db)["payload_json"])[
        "intraday_alert_policy"
    ]
    assert policy["cooldown_minutes"] == 90
    assert schema.INITIAL_POLICY_VALUES["cooldown_minutes"] == 120, "기본값은 그대로"


def test_state_api_exposes_policy_values_read_only(tmp_path, monkeypatch):
    """`GET /state` 가 12개 키를 **읽기 전용**으로 내린다(OPS-03 §2).

    값을 바꾸는 엔드포인트는 만들지 않는다 — 쓰기는 승인·기각 2개뿐이다.
    """
    from app import api_intraday_config as api_mod

    db = _db(tmp_path)
    _make(tmp_path, db)
    monkeypatch.setattr(store, "DEFAULT_DB_PATH", db, raising=False)

    keys = [p.key for p in api_mod.ConfigStateResponse().policy_values]
    assert keys == []  # 기본 응답은 비어 있다(상태 없음)

    routes = {
        (m, r.path) for r in api_mod.router.routes for m in getattr(r, "methods", set())
    }
    writes = {(m, p) for m, p in routes if m in ("POST", "PUT", "PATCH", "DELETE")}
    assert writes == {
        ("POST", "/intraday-config/approve-and-apply"),
        ("POST", "/intraday-config/reject"),
    }, f"정책 편집 엔드포인트가 생겼다: {writes}"


# ── OPS-03 필수 보완 — 선언만 된 설정값을 남기지 않는다 ────────────────────
#
# `dedup_window_minutes` 와 `max_sends_per_run` 은 실행 코드가 읽지 않는다.
# 범위 검사만 두면 화면에 "조절 가능" 처럼 보이면서 실제 효과가 0인 장식용
# 값이 된다. 설계자가 각각 **호환 별칭**·**고정값**으로 확정했다.


def _policy_with(**over):
    from app.intraday_config.generator import CONFIRMED_POLICY

    p = dict(CONFIRMED_POLICY)
    p.update(over)
    return p


def _build(policy):
    return schema.build_payload(
        rule_version="r",
        sectors=[
            {"sector_key": "S", "representative": {"ticker": "T", "short_name": "n"}}
        ],
        token_dictionary={},
        data_asof="2026-09-17",
        excluded=[],
        policy=policy,
    )


def test_dedup_window_must_equal_cooldown():
    """`dedup_window_minutes` 는 `cooldown_minutes` 의 호환 별칭이다."""
    _build(_policy_with())  # 기본값은 통과
    with pytest.raises(schema.ConfigSchemaError, match="호환 별칭"):
        _build(_policy_with(dedup_window_minutes=90))
    # 둘을 **같이** 옮기는 것은 허용된다 — 별칭이지 상수가 아니다.
    _build(_policy_with(cooldown_minutes=90, dedup_window_minutes=90))


def test_max_sends_per_run_is_fixed_at_one():
    """회차당 본문 1개라는 **구조에서 나온 고정값**이다."""
    # 범위(1~10) **안**이지만 1 이 아닌 값 — 고정값 규칙이 잡아야 한다.
    for bad in (2, 5, 10):
        with pytest.raises(schema.ConfigSchemaError, match="고정값"):
            _build(_policy_with(max_sends_per_run=bad))
    # 범위 밖은 기존 범위 검사가 먼저 잡는다(메시지가 다르다).
    with pytest.raises(schema.ConfigSchemaError, match="범위 밖"):
        _build(_policy_with(max_sends_per_run=0))
    assert schema.FIXED_MAX_SENDS_PER_RUN == 1


def test_derived_keys_are_named_so_ui_can_separate_them():
    """화면이 두 키를 가려내려면 **코드가 목록을 갖고 있어야** 한다.

    화면에서만 문자열로 골라내면, 키가 늘어날 때 조용히 섞인다.
    """
    assert set(schema.DERIVED_POLICY_KEYS) == {
        "dedup_window_minutes",
        "max_sends_per_run",
    }
    for k in schema.DERIVED_POLICY_KEYS:
        assert k in schema.REQUIRED_POLICY_KEYS, f"{k} 는 여전히 번들에 실린다"


def test_generated_bundle_satisfies_derived_key_rules():
    """산출 번들이 두 규칙을 실제로 만족한다."""
    from app.intraday_config.generator import CONFIRMED_POLICY

    assert (
        CONFIRMED_POLICY["dedup_window_minutes"] == CONFIRMED_POLICY["cooldown_minutes"]
    )
    assert CONFIRMED_POLICY["max_sends_per_run"] == schema.FIXED_MAX_SENDS_PER_RUN


# ── OPS-03 P1 — 현재 active 상태와 적용 예정 후보를 구분한다 ───────────────
#
# `policy = (cp or ap)` 였다. 후보가 있으면 후보 값이 `policy_enabled` 로
# 나가서, active 가 비활성인데도 화면이 「장중 알림 발송 중」 으로 보이고
# 활성화 경고는 `!policy_enabled` 조건에 가려 숨었다(검증자 실측).
#
# 앞선 API 테스트는 **엔드포인트 목록만** 봤다. 응답 내용을 안 봐서 못 잡았다.


def _pending_activation(db):
    """active=비활성 · 후보=enabled 인 실제 승인 대기 상태를 만든다."""
    s = [{"sector_key": "S0", "representative": {"ticker": "T0", "short_name": "n"}}]
    act = schema.build_payload(
        rule_version="sector_rep.v1",
        sectors=s,
        token_dictionary={},
        data_asof="2026-09-10",
        excluded=[],
        policy={"enabled": False, "policy_status": schema.POLICY_NOT_CONFIGURED},
    )
    va, _ = store.create_candidate(act, evaluation_input_hash="h1", db_path=db)
    store.approve(va, approved_by="u", db_path=db)
    store.activate(va, activated_by="u", db_path=db)
    cand = schema.build_payload(
        rule_version="sector_rep.v1",
        sectors=s
        + [{"sector_key": "S1", "representative": {"ticker": "T1", "short_name": "m"}}],
        token_dictionary={},
        data_asof="2026-09-17",
        excluded=[],
        policy=dict(generator.CONFIRMED_POLICY),
    )
    vc, _ = store.create_candidate(cand, evaluation_input_hash="h2", db_path=db)
    return va, vc


def _state_in(db, va, vc, monkeypatch):
    from app import api_intraday_config as api_mod

    monkeypatch.setattr(
        store, "get_active", lambda **k: store.get_version(va, db_path=db)
    )
    monkeypatch.setattr(
        store,
        "actionable_version",
        lambda **k: (store.get_version(vc, db_path=db), "pending_approval"),
    )
    monkeypatch.setattr(store, "latest_sync", lambda v, **k: None)
    return api_mod.get_state()


def test_state_reports_active_policy_not_candidate(tmp_path, monkeypatch):
    """`policy_enabled` 는 **지금 운영 중인** 값이다."""
    db = _db(tmp_path)
    r = _state_in(db, *_pending_activation(db), monkeypatch)
    assert r.policy_enabled is False, "승인 전인데 발송 중으로 보고했다"
    assert r.policy_status == schema.POLICY_NOT_CONFIGURED


def test_state_reports_candidate_policy_separately(tmp_path, monkeypatch):
    """적용하면 켜진다는 사실을 **별도 필드**로 내린다 — 경고의 근거다."""
    db = _db(tmp_path)
    r = _state_in(db, *_pending_activation(db), monkeypatch)
    assert r.candidate_policy_enabled is True
    assert r.candidate_policy_status == schema.POLICY_CONFIGURED


def test_state_policy_values_come_from_the_version_being_approved(
    tmp_path, monkeypatch
):
    """「적용될 판정 기준」 은 **승인 대상**(후보) 기준이다."""
    db = _db(tmp_path)
    r = _state_in(db, *_pending_activation(db), monkeypatch)
    vals = {p.key: p.value for p in r.policy_values}
    assert len(vals) == len(schema.REQUIRED_POLICY_KEYS)
    assert vals["cooldown_minutes"] == generator.CONFIRMED_POLICY["cooldown_minutes"]
    assert r.policy_rule_version == "sector_rep.v1"


def test_state_without_candidate_has_no_candidate_policy(tmp_path, monkeypatch):
    """후보가 없으면 적용 예정 상태도 없다 — `False` 로 위장하지 않는다."""
    from app import api_intraday_config as api_mod

    db = _db(tmp_path)
    va, _vc = _pending_activation(db)
    monkeypatch.setattr(
        store, "get_active", lambda **k: store.get_version(va, db_path=db)
    )
    monkeypatch.setattr(store, "actionable_version", lambda **k: (None, None))
    monkeypatch.setattr(store, "latest_sync", lambda v, **k: None)
    r = api_mod.get_state()
    assert r.candidate_policy_enabled is None
    assert r.candidate_policy_status is None
