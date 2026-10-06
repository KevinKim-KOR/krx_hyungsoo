"""POC3-02D-OPS-04 항목 3 · 6 — 「OCI 운영·적용」 ① '장중 대표 ETF' · '운영 기준 활성' 행.

```text
읽기     같은 기동 시 SSH 읽기 1회에 블록 2개(설계자 Q4 a · Q8 a) — 상태 JSON · DB mode=ro
대표 ETF 같은 날이면 09:20 기록 · 아니면 08:10 기록 · 지난 기록도 기준일과 함께(Q3 a/a)
         못 읽으면 숫자를 만들지 않는다(0 · 정상 아님)
활성     러너가 쓰는 유효값 14개 비교(Q7 b) — 버전 ID 가 달라도 값이 같으면 일치 · 요청 때 비교
         `param_id` 는 응답에 없다 · 비교 실패는 그 행만 확인 불가(응답은 200)
```

원격 블록은 로컬 bash 로 실제로 돌린다(따옴표 · heredoc 확인). tmp 홈 · tmp DB · tmp PC
운영 기준만 쓴다 — 라이브 state · OCI · 네트워크 0.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import api_three_push_param as param_api
from app import oci_startup_status as oss
from app import runtime_param_store as store
from app.three_push_runtime_param import build_manual_seed_param

REPS_OK = {
    "source": "active_intraday_config",
    "status": "ok",
    "expected_previous_trading_day": "2026-10-02",
    "count": 27,
    "missing": [],
    "representatives_refresh_due": False,
}


def _raw(batch=None, reinforce=None) -> str:
    return json.dumps({"batch": batch, "reinforce": reinforce})


def _rec(date, at, reps):
    return {"date": date, "at": at, "reps": reps}


# ── 장중 대표 ETF 행 ──────────────────────────────────────────────────────────


def test_reps_row_prefers_same_day_0920_record():
    job = oss.representatives_job(
        _raw(
            _rec(
                "2026-10-06", "2026-10-05T23:10:21+00:00", dict(REPS_OK, missing=["X"])
            ),
            _rec("2026-10-06", "2026-10-06T00:20:01+00:00", REPS_OK),
        )
    )
    assert job.job == "intraday_representatives"
    assert (job.status, job.detail) == (
        "SUCCESS",
        "기준일 10/2 · 27/27 준비됨 (10/6 09:20 확인)",
    )


def test_reps_row_uses_0810_record_when_0920_is_another_day_or_missing():
    batch = _rec("2026-10-06", "2026-10-05T23:10:21+00:00", REPS_OK)
    old = _rec("2026-10-02", "2026-10-02T00:20:01+00:00", REPS_OK)
    for rein in (old, None, _rec("2026-10-06", "x", None)):
        job = oss.representatives_job(_raw(batch, rein))
        assert job.detail == "기준일 10/2 · 27/27 준비됨 (10/6 08:10 확인)"


def test_reps_row_old_record_still_shows_its_basis_date():
    """지난 기록도 기준일과 함께 보인다(Q3 a/a) — PC 를 08:10 전에 켠 날 · 휴장일."""
    job = oss.representatives_job(
        _raw(
            _rec(
                "2026-10-02",
                "2026-10-01T23:10:00+00:00",
                dict(REPS_OK, expected_previous_trading_day="2026-10-01"),
            )
        )
    )
    assert job.detail == "기준일 10/1 · 27/27 준비됨 (10/2 08:10 확인)"


def test_reps_row_missing_representative_is_check_needed():
    job = oss.representatives_job(
        _raw(
            _rec(
                "2026-10-06",
                None,
                dict(REPS_OK, status="representative_missing", missing=["A"]),
            )
        )
    )
    assert (job.status, job.detail) == (
        "STALE",
        "기준일 10/2 · 26/27 준비됨 · 1종 빠짐",
    )


@pytest.mark.parametrize(
    "reps, detail",
    [
        (
            dict(REPS_OK, status="intraday_config_unavailable", count=0),
            "활성 설정을 읽지 못함",
        ),
        # not_evaluated 는 missing=[] · count=27 — 그대로 세면 27/27 이 된다. 셈하지 않는다.
        (dict(REPS_OK, status="not_evaluated"), "기록을 읽지 못함"),
        (None, "기록을 읽지 못함"),  # 08:10 KRX 전 기록(pending)
        (dict(REPS_OK, count="27"), "기록을 읽지 못함"),
        (dict(REPS_OK, missing=["a"] * 28), "기록을 읽지 못함"),
    ],
)
def test_reps_row_unknown_never_shows_numbers(reps, detail):
    job = oss.representatives_job(_raw(_rec("2026-10-06", None, reps)))
    assert (job.status, job.detail) == ("UNKNOWN", detail)
    assert "/" not in job.detail


@pytest.mark.parametrize("raw", ["", "{broken", "[]", json.dumps({"batch": None})])
def test_reps_row_unreadable_block_is_unknown(raw):
    job = oss.representatives_job(raw)
    assert (job.status, job.detail) == ("UNKNOWN", "기록을 읽지 못함")


# ── 운영 기준 활성 행 ─────────────────────────────────────────────────────────


def _param(**kw):
    return build_manual_seed_param(**kw).to_dict()


def _oci_values(d):
    return {
        k: (vt, *store._split_value_columns(vt, v))
        for k, vt, v in store.flatten_param_dict(d)
    }


def _pc_json(tmp_path, d) -> Path:
    p = tmp_path / "latest_runtime_param.json"
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return p


def test_param_row_same_values_different_version_is_match(tmp_path):
    active, sent = _param(), _param()
    assert active["param_id"] != sent["param_id"]
    job = oss.param_active_job(_oci_values(active), _pc_json(tmp_path, sent), True)
    assert (job.status, job.detail) == (
        "SUCCESS",
        "전달한 운영 기준이 OCI 에서 쓰는 값과 같음 (14/14)",
    )
    assert "param-" not in job.detail


def test_param_row_enabled_kinds_order_only_is_match(tmp_path):
    active = _param()
    sent = _param(enabled_push_kinds=list(reversed(active["enabled_push_kinds"])))
    job = oss.param_active_job(_oci_values(active), _pc_json(tmp_path, sent), True)
    assert job.status == "SUCCESS"


@pytest.mark.parametrize(
    "last_sync_ok, tail",
    [(True, " — 전달만 되고 활성화되지 않음"), (False, ""), (None, "")],
)
def test_param_row_different_value(tmp_path, last_sync_ok, tail):
    active = _param()
    sent = _param(enabled_push_kinds=["market_briefing", "holdings_briefing"])
    job = oss.param_active_job(
        _oci_values(active), _pc_json(tmp_path, sent), last_sync_ok
    )
    assert job.status == "STALE"
    assert job.detail == f"OCI 는 다른 값으로 동작 중 (14개 중 2개 다름){tail}"


def test_param_row_unknown_cases(tmp_path):
    d = _param()
    assert oss.param_active_job(None, _pc_json(tmp_path, d), True).detail == (
        "OCI 에서 쓰는 값을 읽지 못함"
    )
    assert oss.param_active_job({}, _pc_json(tmp_path, d), True).status == "UNKNOWN"
    missing = tmp_path / "none.json"
    bad = tmp_path / "bad.json"
    bad.write_text("{broken", "utf-8")
    for path in (missing, bad):
        job = oss.param_active_job(_oci_values(d), path, True)
        assert (job.status, job.detail) == ("UNKNOWN", "전달한 운영 기준을 읽지 못함")


def test_parse_param_values():
    rows = [
        ["safety_policy.x", "boolean", None, None, 1],
        ["a", "numeric", 3, None, None],
    ]
    assert oss.parse_param_values(json.dumps({"rows": rows})) == {
        "safety_policy.x": ("boolean", None, None, 1),
        "a": ("numeric", 3.0, None, None),
    }
    for raw in ("", "{}", json.dumps({"rows": []}), json.dumps({"error": "X"}), "{bad"):
        assert oss.parse_param_values(raw) is None


# ── 원격 블록을 로컬 bash 로 실제 실행 ───────────────────────────────────────────


def _home(tmp_path):
    home = tmp_path / "home"
    (home / "state" / "market").mkdir(parents=True)
    (home / "state" / "runtime").mkdir(parents=True)
    return home


def _bash(cmd: str) -> str:
    out = subprocess.run(
        ["bash", "-c", cmd], capture_output=True, text=True, timeout=30
    )
    assert out.returncode == 0, out.stderr
    return out.stdout


def test_remote_blocks_run_in_bash_read_only(tmp_path):
    home = _home(tmp_path)
    (home / "state/market/oci_market_data_batch_state.json").write_text(
        json.dumps(
            {
                "refresh_date_kst": "2026-10-06",
                "refresh_completed_at": "2026-10-05T23:10:21+00:00",
                "krx_representatives": REPS_OK,
            }
        ),
        "utf-8",
    )
    db = home / "state/runtime/runtime_state.sqlite"
    active = _param()
    vid, _, _ = store.create_param_version(active, db_path=db)
    store.activate_param_version(vid, activated_by="test", db_path=db)
    digest, mtime = hashlib.sha256(db.read_bytes()).hexdigest(), os.stat(db).st_mtime_ns

    reps = _bash(oss.representatives_block(str(home)))
    assert oss.representatives_job(reps).detail == (
        "기준일 10/2 · 27/27 준비됨 (10/6 08:10 확인)"
    )
    raw = _bash(oss.param_values_block(str(home)))
    assert vid not in raw and "param-" not in raw  # 버전 ID 를 꺼내지 않는다
    values = oss.parse_param_values(raw)
    assert values is not None and len(values) == 14
    job = oss.param_active_job(values, _pc_json(tmp_path, _param()), True)
    assert job.detail.endswith("(14/14)")
    # mode=ro — DB 가 바뀌지 않는다.
    assert hashlib.sha256(db.read_bytes()).hexdigest() == digest
    assert os.stat(db).st_mtime_ns == mtime


def test_remote_blocks_missing_files_print_fallback_and_exit_zero(tmp_path):
    home = _home(tmp_path)
    reps = _bash(oss.representatives_block(str(home)))
    assert json.loads(reps) == {"batch": None, "reinforce": None}
    raw = _bash(oss.param_values_block(str(home)))
    assert json.loads(raw) == {"error": "OperationalError"}
    assert not (home / "state/runtime/runtime_state.sqlite").exists()  # 만들지 않는다


def test_full_remote_command_parses_five_blocks(tmp_path, monkeypatch):
    """refresh_snapshot 이 만드는 명령 전체를 tmp 홈으로 돌려 5블록을 파싱한다."""
    home = _home(tmp_path)
    (home / "state/market/oci_krx_reinforcement_state.json").write_text(
        json.dumps(
            {
                "date_kst": "2026-10-06",
                "finished_at": "2026-10-06T00:20:01+00:00",
                "krx_representatives": REPS_OK,
            }
        ),
        "utf-8",
    )
    db = home / "state/runtime/runtime_state.sqlite"
    vid, _, _ = store.create_param_version(_param(), db_path=db)
    store.activate_param_version(vid, activated_by="test", db_path=db)
    monkeypatch.setattr(oss, "_REMOTE_HOME", str(home))
    monkeypatch.setenv("OCI_SSH_TARGET", "test-target")

    def _local(cmd):
        out = subprocess.run(
            ["bash", "-c", cmd], capture_output=True, text=True, timeout=30
        )
        return out.returncode == 0, out.stdout.strip()

    monkeypatch.setattr(oss, "_ssh_read", _local)
    snap = oss.refresh_snapshot()
    assert snap.reachable
    rows = {j.job: j for j in snap.jobs}
    assert rows["intraday_representatives"].status == "SUCCESS"
    assert snap.oci_param_values is not None and len(snap.oci_param_values) == 14


# ── API: 요청 때 비교 ─────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from app.api import app

    return TestClient(app)


def _snap(values):
    return oss.OciStartupSnapshot(
        checked_at="2026-10-06T00:00:00+00:00",
        reachable=True,
        overall="OPERATING",
        summary_line="ok",
        crontab_active=True,
        jobs=[oss.OciJobStatus("crontab", "SUCCESS", "ok")],
        note="n",
        oci_param_values=values,
    )


def test_api_appends_param_row_per_request_without_mutating_cache(client, monkeypatch):
    active = _param()
    snap = _snap(_oci_values(active))
    monkeypatch.setattr(oss, "_snapshot", snap)
    param_api.latest_param_path().parent.mkdir(parents=True, exist_ok=True)
    param_api.latest_param_path().write_text(json.dumps(_param()), "utf-8")
    first = client.get("/oci/startup-status")
    second = client.get("/oci/startup-status")
    assert first.status_code == second.status_code == 200
    jobs = first.json()["jobs"]
    assert [j["job"] for j in jobs] == ["crontab", "param_active"]
    assert jobs[1]["status"] == "SUCCESS"
    assert len(second.json()["jobs"]) == 2 and len(snap.jobs) == 1
    assert "param-" not in first.text and "oci_param_values" not in first.text


def test_api_param_row_follows_current_pc_json_and_sync_status(client, monkeypatch):
    """같은 세션에서 다른 값을 전달하면 다음 조회부터 '다름'(OCI 재조회 없음).

    '— 전달만 되고 활성화되지 않음' 은 지금 PC 기준이 전달된 경우에만 붙는다 — 전달 기록이
    실패이거나 다른 PARAM 의 기록이면 붙이지 않는다(식별자는 내부 비교만 · 응답에 없음).
    """
    monkeypatch.setattr(oss, "_snapshot", _snap(_oci_values(_param())))
    sent = _param(enabled_push_kinds=["market_briefing"])
    path = param_api.latest_param_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sent), "utf-8")

    def _sync(**rec):
        param_api._SYNC_STATUS_PATH.write_text(json.dumps(rec), "utf-8")
        return client.get("/oci/startup-status")

    ok = {"status": "success", "verify_status": "success"}
    r = _sync(**ok, param_id=sent["param_id"])
    row = r.json()["jobs"][-1]
    assert row["status"] == "STALE"
    assert row["detail"].endswith("— 전달만 되고 활성화되지 않음")
    assert sent["param_id"] not in r.text
    for rec in (
        {"status": "failed", "param_id": sent["param_id"]},
        {**ok, "param_id": "param-other"},  # 다른 PARAM 의 전달 기록
        {**ok},  # 식별자 없는 옛 기록
    ):
        row = _sync(**rec).json()["jobs"][-1]
        assert row["status"] == "STALE" and "전달만" not in row["detail"]


def test_api_bad_pc_json_or_compare_error_keeps_200(client, monkeypatch):
    monkeypatch.setattr(oss, "_snapshot", _snap(_oci_values(_param())))
    path = param_api.latest_param_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{broken", "utf-8")
    r = client.get("/oci/startup-status")
    assert r.status_code == 200
    assert r.json()["jobs"][-1] == {
        "job": "param_active",
        "status": "UNKNOWN",
        "detail": "전달한 운영 기준을 읽지 못함",
    }

    def _boom(*a, **k):
        raise RuntimeError("x")

    monkeypatch.setattr(oss, "param_active_job", _boom)
    r = client.get("/oci/startup-status")
    assert r.status_code == 200
    assert r.json()["jobs"][-1]["detail"] == "전달한 운영 기준과 비교하지 못함"


def test_api_unreachable_has_no_param_row(client, monkeypatch):
    monkeypatch.setattr(
        oss, "_snapshot", oss._unknown_snapshot("2026-10-06T00:00:00+00:00", "s", "n")
    )
    assert client.get("/oci/startup-status").json()["jobs"] == []
