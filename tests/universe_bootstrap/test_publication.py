"""Universe Momentum publication CLI tests (지시문 §33.2)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from scripts.run_universe_momentum_publication import main as pub_main


def _artifact(asof: str = "2026-07-16", candidates=None, status: str = "ok") -> dict:
    # 검증자 REJECTED r5: shape 자동 보완 시 `is_scored=True + score_value=1.23` 로
    # 채워 넣어 refresh_status ok ↔ scored 계약 (universe_refresh.determine_refresh_status)
    # 을 통과시킴. is_scored=False fixture 가 필요한 test 는 명시적으로 넘긴다.
    cs = candidates or []
    normalized = []
    for c in cs:
        if isinstance(c, dict) and "score_result" not in c and "ticker" in c:
            c = {
                **c,
                "score_result": {
                    "is_scored": True,
                    "score_value": 1.23,
                    "score_unit": "%",
                },
            }
        normalized.append(c)
    return {
        "engine_id": "momentum_engine",
        "engine_version": "v1",
        "mode": "universe",
        "asof": asof,
        "summary": {
            "refresh_status": status,
            "total_candidates": len(normalized),
        },
        "candidates": normalized,
    }


def _write_artifact(path: Path, artifact: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _sha_of(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ── 33.2.1 정상 artifact prepare 성공 ──


def test_prepare_success_zero_candidates(tmp_path, capsys) -> None:
    src = tmp_path / "art.json"
    _write_artifact(src, _artifact(asof="2026-07-16", candidates=[]))
    rc = pub_main(["prepare", "--source", str(src)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["status"] == "ok"
    assert out["publishable"] is True
    assert out["source_candidate_count"] == 0


def test_prepare_success_with_candidates(tmp_path, capsys) -> None:
    src = tmp_path / "art.json"
    _write_artifact(
        src,
        _artifact(candidates=[{"ticker": "A", "name": "A_name", "rank": 1}]),
    )
    rc = pub_main(["prepare", "--source", str(src)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["source_candidate_count"] == 1


# ── 33.2.2 source 부재 실패 ──


def test_prepare_source_missing(tmp_path, capsys) -> None:
    rc = pub_main(["prepare", "--source", str(tmp_path / "missing.json")])
    out = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert out["source_exists"] is False
    assert out["publishable"] is False


# ── 33.2.3 JSON parse 실패 ──


def test_prepare_json_parse_error(tmp_path, capsys) -> None:
    src = tmp_path / "bad.json"
    src.write_text("{not json", encoding="utf-8")
    rc = pub_main(["prepare", "--source", str(src)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert "json_parse_error" in out["error_reason"]


# ── 33.2.4 validation 실패 (mode mismatch) ──


def test_prepare_validation_failed(tmp_path, capsys) -> None:
    src = tmp_path / "art.json"
    payload = _artifact()
    payload["mode"] = "holdings"
    _write_artifact(src, payload)
    rc = pub_main(["prepare", "--source", str(src)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert out["error_reason"] == "artifact_mode_mismatch"


# ── 33.2.5 as-of 부재 ──


def test_prepare_asof_missing(tmp_path, capsys) -> None:
    src = tmp_path / "art.json"
    payload = _artifact()
    payload["asof"] = ""
    _write_artifact(src, payload)
    rc = pub_main(["prepare", "--source", str(src)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert out["error_reason"] == "artifact_asof_missing"


# ── 33.2.6 failed status 활성화 차단 ──


def test_prepare_refresh_status_failed_blocked(tmp_path, capsys) -> None:
    src = tmp_path / "art.json"
    _write_artifact(src, _artifact(status="failed"))
    rc = pub_main(["prepare", "--source", str(src)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert out["error_reason"] == "artifact_refresh_status_failed"


def test_prepare_refresh_status_unknown_blocked(tmp_path, capsys) -> None:
    """검증자 REJECTED r2: refresh_status allowlist = {ok, partial}. 미지 값 차단."""
    src = tmp_path / "art.json"
    _write_artifact(src, _artifact(status="mystery"))
    rc = pub_main(["prepare", "--source", str(src)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert out["error_reason"] == "artifact_refresh_status_unknown"


def test_prepare_broken_candidate_shape_blocked(tmp_path, capsys) -> None:
    """검증자 REJECTED r2: candidate 구조 손상은 Publication 도 차단."""
    src = tmp_path / "art.json"
    _write_artifact(src, _artifact(candidates=[{"name": "no_ticker"}]))
    rc = pub_main(["prepare", "--source", str(src)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert "candidate_ticker_missing" in out["error_reason"]


def test_prepare_is_scored_not_bool_blocked(tmp_path, capsys) -> None:
    """검증자 REJECTED r3: is_scored 가 bool 타입 아니면 차단."""
    src = tmp_path / "art.json"
    # _artifact helper 는 score_result 없으면 자동 보완하므로 명시적으로 넣음.
    _write_artifact(
        src,
        _artifact(
            candidates=[
                {
                    "ticker": "A",
                    "name": "A_name",
                    "score_result": {"is_scored": "yes"},  # 문자열 - bool 아님.
                }
            ]
        ),
    )
    rc = pub_main(["prepare", "--source", str(src)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert "candidate_is_scored_not_bool" in out["error_reason"]


def test_prepare_asof_invalid_format_blocked(tmp_path, capsys) -> None:
    """검증자 REJECTED r6: asof 는 YYYY-MM-DD 형식 · 실제 존재 날짜 필수."""
    src = tmp_path / "art.json"
    _write_artifact(src, _artifact(asof="not-a-date"))
    rc = pub_main(["prepare", "--source", str(src)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert out["error_reason"] == "artifact_asof_format_invalid"


def test_prepare_asof_not_real_date_blocked(tmp_path, capsys) -> None:
    """검증자 REJECTED r6: 형식은 맞지만 존재하지 않는 날짜 (2월 30일 등) 차단."""
    src = tmp_path / "art.json"
    _write_artifact(src, _artifact(asof="2026-02-30"))
    rc = pub_main(["prepare", "--source", str(src)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert out["error_reason"] == "artifact_asof_not_a_real_date"


def test_prepare_status_ok_partial_scored_blocked(tmp_path, capsys) -> None:
    """검증자 REJECTED r6: status=ok 인데 일부만 scored → 차단.

    producer 계약: scored == total 이어야만 ok.
    """
    src = tmp_path / "art.json"
    _write_artifact(
        src,
        _artifact(
            status="ok",
            candidates=[
                {
                    "ticker": "A",
                    "name": "A_name",
                    "score_result": {"is_scored": True, "score_value": 1.0},
                },
                {
                    "ticker": "B",
                    "name": "B_name",
                    "score_result": {"is_scored": False},
                },
            ],
        ),
    )
    rc = pub_main(["prepare", "--source", str(src)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert out["error_reason"] == "artifact_status_ok_but_partial_scored"


def test_prepare_status_partial_all_scored_blocked(tmp_path, capsys) -> None:
    """검증자 REJECTED r6: status=partial 인데 전부 scored → 차단.

    producer 계약: 0 < scored < total 이어야만 partial.
    """
    src = tmp_path / "art.json"
    _write_artifact(
        src,
        _artifact(
            status="partial",
            candidates=[
                {
                    "ticker": "A",
                    "name": "A_name",
                    "score_result": {"is_scored": True, "score_value": 1.0},
                },
                {
                    "ticker": "B",
                    "name": "B_name",
                    "score_result": {"is_scored": True, "score_value": 2.0},
                },
            ],
        ),
    )
    rc = pub_main(["prepare", "--source", str(src)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert out["error_reason"] == "artifact_status_partial_but_all_scored"


def test_verify_activation_ready_false_when_temp_mode_wrong(tmp_path, capsys) -> None:
    """검증자 REJECTED r6: temp mode != 600 이면 activation_ready=false.

    이전 구현은 mode 를 stdout 만 하고 판정에 반영 안 함 → verify 통과했으나
    실제 activate 는 실패하는 계약 불일치.
    """
    import os as _os
    import sys as _sys

    if _sys.platform.startswith("win"):
        pytest.skip("POSIX mode check only")

    temp = tmp_path / "u.json"
    _write_artifact(temp, _artifact(candidates=[{"ticker": "A", "name": "A"}]))
    _os.chmod(temp, 0o666)  # 잘못된 mode.
    h, sz, asof, cnt = _prepare_meta(temp)
    rc = pub_main(_verify_args(temp, h, sz, asof, cnt))
    out = json.loads(capsys.readouterr().out)
    assert rc == 3
    assert out["activation_ready"] is False
    assert out["mode_match"] is False
    assert "temp_mode_mismatch" in out["error_reason"]


def test_prepare_status_ok_but_all_unscored_blocked(tmp_path, capsys) -> None:
    """검증자 REJECTED r5: refresh_status=ok 인데 scored 0건 → Publication 차단.

    producer 계약 (universe_refresh.determine_refresh_status): scored 0 → failed.
    ok/partial 상태에서 scored 0건이면 producer 계약 위반 · Runtime unavailable.
    Publication 에서 미리 차단 → Publication↔Runtime 판정 일치.
    """
    src = tmp_path / "art.json"
    _write_artifact(
        src,
        _artifact(
            status="ok",
            candidates=[
                {
                    "ticker": "A",
                    "name": "A_name",
                    "score_result": {"is_scored": False},
                }
            ],
        ),
    )
    rc = pub_main(["prepare", "--source", str(src)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert out["error_reason"] == "artifact_status_scored_inconsistency"


def test_prepare_score_value_nan_blocked(tmp_path, capsys) -> None:
    """검증자 REJECTED r4: score_value NaN 은 정상 momentum 수치 아님 → 차단."""
    src = tmp_path / "art.json"
    _write_artifact(
        src,
        _artifact(
            candidates=[
                {
                    "ticker": "A",
                    "name": "A_name",
                    "score_result": {
                        "is_scored": True,
                        "score_value": float("nan"),
                    },
                }
            ]
        ),
    )
    rc = pub_main(["prepare", "--source", str(src)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert "candidate_score_value_not_finite" in out["error_reason"]


def test_prepare_score_value_inf_blocked(tmp_path, capsys) -> None:
    """검증자 REJECTED r4: score_value +Inf / -Inf 도 차단."""
    for inf_value in (float("inf"), float("-inf")):
        src = tmp_path / f"art_{'p' if inf_value > 0 else 'n'}inf.json"
        _write_artifact(
            src,
            _artifact(
                candidates=[
                    {
                        "ticker": "A",
                        "name": "A_name",
                        "score_result": {
                            "is_scored": True,
                            "score_value": inf_value,
                        },
                    }
                ]
            ),
        )
        rc = pub_main(["prepare", "--source", str(src)])
        out = json.loads(capsys.readouterr().out)
        assert rc == 2
        assert "candidate_score_value_not_finite" in out["error_reason"]


def test_prepare_scored_true_but_missing_score_value_blocked(tmp_path, capsys) -> None:
    """검증자 REJECTED r3: is_scored=True 인데 score_value 부재 → 차단.

    이 경우 Runtime 이 표시할 수 없어 Publication ↔ Runtime 판정 차이 발생.
    Publication 에서 미리 차단해서 계약 불일치 방지.
    """
    src = tmp_path / "art.json"
    _write_artifact(
        src,
        _artifact(
            candidates=[
                {
                    "ticker": "A",
                    "name": "A_name",
                    "score_result": {"is_scored": True},  # score_value 없음.
                }
            ]
        ),
    )
    rc = pub_main(["prepare", "--source", str(src)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert "candidate_score_value_missing_or_invalid" in out["error_reason"]


# ── 33.2.9~12 expected 불일치 차단 (verify) ──


def _prepare_meta(src: Path) -> tuple[str, int, str, int]:
    data = json.loads(src.read_text(encoding="utf-8"))
    return _sha_of(src), src.stat().st_size, data["asof"], len(data["candidates"])


def _verify_args(temp: Path, h: str, sz: int, asof: str, cnt: int) -> list[str]:
    return [
        "verify",
        "--temp",
        str(temp),
        "--expected-hash",
        h,
        "--expected-size",
        str(sz),
        "--expected-asof",
        asof,
        "--expected-count",
        str(cnt),
    ]


def test_verify_hash_mismatch_blocks(tmp_path, capsys) -> None:
    temp = tmp_path / "t.json"
    _write_artifact(temp, _artifact(candidates=[{"ticker": "A", "name": "A"}]))
    h, sz, asof, cnt = _prepare_meta(temp)
    rc = pub_main(_verify_args(temp, "wronghash" * 8, sz, asof, cnt))
    out = json.loads(capsys.readouterr().out)
    assert rc == 3
    assert out["hash_match"] is False
    assert out["activation_ready"] is False


def test_verify_size_mismatch_blocks(tmp_path, capsys) -> None:
    temp = tmp_path / "t.json"
    _write_artifact(temp, _artifact())
    h, sz, asof, cnt = _prepare_meta(temp)
    rc = pub_main(_verify_args(temp, h, sz + 1, asof, cnt))
    out = json.loads(capsys.readouterr().out)
    assert rc == 3
    assert out["size_match"] is False


def test_verify_asof_mismatch_blocks(tmp_path, capsys) -> None:
    temp = tmp_path / "t.json"
    _write_artifact(temp, _artifact(asof="2026-07-16"))
    h, sz, _asof, cnt = _prepare_meta(temp)
    rc = pub_main(_verify_args(temp, h, sz, "2020-01-01", cnt))
    out = json.loads(capsys.readouterr().out)
    assert rc == 3
    assert out["asof_match"] is False


def test_verify_count_mismatch_blocks(tmp_path, capsys) -> None:
    temp = tmp_path / "t.json"
    _write_artifact(temp, _artifact(candidates=[{"ticker": "A", "name": "A"}]))
    h, sz, asof, _cnt = _prepare_meta(temp)
    rc = pub_main(_verify_args(temp, h, sz, asof, 999))
    out = json.loads(capsys.readouterr().out)
    assert rc == 3
    assert out["candidate_count_match"] is False


# ── 33.2.14 verify 이후 임시 파일 변경 차단 (activate 재검증) ──
# ── 33.2.15 정상 atomic activation ──
# ── 33.2.16 active artifact 재검증 ──
# ── 33.2.17 artifact byte 동일 (activation 은 replace 이므로 byte 동일 보장) ──


@pytest.mark.skipif(
    sys.platform.startswith("win"), reason="chmod/owner check requires POSIX"
)
def test_activate_success_atomic_and_reverify(tmp_path, capsys, monkeypatch) -> None:
    """POSIX 정상 activate 재검증.

    검증자 REJECTED r4 재정정: owner override 는 CLI · env 모두 제거.
    Test 는 monkeypatch 로 `_EXPECTED_OWNER_CONST` 상수를 직접 대체.
    """
    import getpass

    import scripts.run_universe_momentum_publication as pub_mod

    exec_user = getpass.getuser()
    monkeypatch.setattr(pub_mod, "_EXPECTED_OWNER_CONST", exec_user)

    temp = tmp_path / "u.json"
    _write_artifact(temp, _artifact(candidates=[{"ticker": "A", "name": "A"}]))
    h, sz, asof, cnt = _prepare_meta(temp)
    active = tmp_path / "u.json.active"
    rc = pub_main(
        [
            "activate",
            "--temp",
            str(temp),
            "--active",
            str(active),
            "--expected-hash",
            h,
            "--expected-size",
            str(sz),
            "--expected-asof",
            asof,
            "--expected-count",
            str(cnt),
        ]
    )
    out = json.loads(capsys.readouterr().out)
    assert rc == 0, f"activate 실패: {out.get('error_reason')}"
    assert out["atomic_activation_completed"] is True
    assert out["active_file_exists"] is True
    assert out["active_asof"] == asof
    assert out["active_candidate_count"] == cnt
    assert out["active_file_mode"] == "600"
    assert out["active_file_owner"] == exec_user
    assert out["active_file_permission_checked"] is True


@pytest.mark.skipif(
    sys.platform.startswith("win"), reason="chmod/owner check requires POSIX"
)
def test_activate_rejects_when_exec_user_not_expected_owner(
    tmp_path, capsys, monkeypatch
) -> None:
    """monkeypatch 로 상수를 exec_user 와 다른 값 → activation 차단."""
    import scripts.run_universe_momentum_publication as pub_mod

    monkeypatch.setattr(
        pub_mod,
        "_EXPECTED_OWNER_CONST",
        "no_such_user_zzz_that_does_not_match_exec",
    )

    temp = tmp_path / "u.json"
    _write_artifact(temp, _artifact(candidates=[{"ticker": "A", "name": "A"}]))
    h, sz, asof, cnt = _prepare_meta(temp)
    active = tmp_path / "u.json.active"
    rc = pub_main(
        [
            "activate",
            "--temp",
            str(temp),
            "--active",
            str(active),
            "--expected-hash",
            h,
            "--expected-size",
            str(sz),
            "--expected-asof",
            asof,
            "--expected-count",
            str(cnt),
        ]
    )
    out = json.loads(capsys.readouterr().out)
    assert rc == 4
    assert "exec_user_not_expected_owner" in out["error_reason"]
    assert out["atomic_activation_completed"] is False


def test_activate_defaults_to_ubuntu_owner_when_no_override(
    tmp_path, capsys, monkeypatch
) -> None:
    """monkeypatch 없이 실행 → expected owner = 소스 상수 `ubuntu`. test 환경 차단.

    검증자 REJECTED r4: env 우회 경로 완전 제거 확인.
    """
    import getpass
    import os as _os

    # 혹시라도 남아있는 (이전 정정본의) env 는 명시적으로 삭제.
    monkeypatch.delenv("_UNIVERSE_PUBLICATION_TEST_OWNER", raising=False)
    _ = _os  # unused-suppress.

    temp = tmp_path / "u.json"
    _write_artifact(temp, _artifact(candidates=[{"ticker": "A", "name": "A"}]))
    h, sz, asof, cnt = _prepare_meta(temp)
    active = tmp_path / "u.json.active"
    rc = pub_main(
        [
            "activate",
            "--temp",
            str(temp),
            "--active",
            str(active),
            "--expected-hash",
            h,
            "--expected-size",
            str(sz),
            "--expected-asof",
            asof,
            "--expected-count",
            str(cnt),
        ]
    )
    out = json.loads(capsys.readouterr().out)
    exec_user = getpass.getuser()
    if exec_user == "ubuntu":
        # 실제 OCI 환경 시뮬레이션.
        return
    assert rc == 4
    assert "exec_user_not_expected_owner" in out["error_reason"]
    assert "expected=ubuntu" in out["error_reason"]


@pytest.mark.skipif(
    sys.platform.startswith("win"), reason="chmod/owner check requires POSIX"
)
def test_env_variable_cannot_override_expected_owner(
    tmp_path, capsys, monkeypatch
) -> None:
    """검증자 REJECTED r4: 환경변수도 owner override 불가.

    이전 정정본에는 `_UNIVERSE_PUBLICATION_TEST_OWNER=root` 로 우회 가능한
    경로가 있었음. 재정정 후에는 exec_user 인 값을 env 로 설정해도 activation
    은 여전히 소스 상수 `ubuntu` 기준으로 판정 → 차단.
    """
    import getpass

    exec_user = getpass.getuser()
    if exec_user == "ubuntu":
        # OCI 환경이면 소스 상수와 동일 → override 판정 불가 (test 무의미).
        return
    # exec_user 로 env 를 설정해도 소스 상수 기준 판정 → 차단돼야 함.
    monkeypatch.setenv("_UNIVERSE_PUBLICATION_TEST_OWNER", exec_user)

    temp = tmp_path / "u.json"
    _write_artifact(temp, _artifact(candidates=[{"ticker": "A", "name": "A"}]))
    h, sz, asof, cnt = _prepare_meta(temp)
    active = tmp_path / "u.json.active"
    rc = pub_main(
        [
            "activate",
            "--temp",
            str(temp),
            "--active",
            str(active),
            "--expected-hash",
            h,
            "--expected-size",
            str(sz),
            "--expected-asof",
            asof,
            "--expected-count",
            str(cnt),
        ]
    )
    out = json.loads(capsys.readouterr().out)
    # env 로 override 되지 않고 소스 상수 `ubuntu` 로 판정 → 차단.
    assert rc == 4
    assert "exec_user_not_expected_owner" in out["error_reason"]
    assert "expected=ubuntu" in out["error_reason"]


def test_cli_does_not_accept_owner_flag(tmp_path, capsys) -> None:
    """검증자 REJECTED r3: CLI 는 owner override 인자를 아예 받지 않음.

    argparse 는 unknown flag 를 SystemExit 로 거부한다.
    """
    temp = tmp_path / "u.json"
    _write_artifact(temp, _artifact(candidates=[{"ticker": "A", "name": "A"}]))
    h, sz, asof, cnt = _prepare_meta(temp)
    active = tmp_path / "u.json.active"
    with pytest.raises(SystemExit):
        pub_main(
            [
                "activate",
                "--temp",
                str(temp),
                "--active",
                str(active),
                "--expected-hash",
                h,
                "--expected-size",
                str(sz),
                "--expected-asof",
                asof,
                "--expected-count",
                str(cnt),
                # 어떤 owner override 인자도 argparse 에 등록되지 않아야 함.
                "--expected-owner",
                "root",
            ]
        )


def test_activate_rejects_after_verify_temp_tampering(tmp_path, capsys) -> None:
    """§33.2.14: verify 이후 임시 파일이 변경되면 activate 재검증 차단."""
    temp = tmp_path / "u.json"
    _write_artifact(temp, _artifact(candidates=[{"ticker": "A", "name": "A"}]))
    h, sz, asof, cnt = _prepare_meta(temp)
    # verify 이후 파일 변경 시뮬레이션 (candidate 수 변경).
    _write_artifact(
        temp,
        _artifact(
            candidates=[{"ticker": "A", "name": "A"}, {"ticker": "B", "name": "B"}]
        ),
    )
    active = tmp_path / "u.json.active"
    rc = pub_main(
        [
            "activate",
            "--temp",
            str(temp),
            "--active",
            str(active),
            "--expected-hash",
            h,  # 이전 hash.
            "--expected-size",
            str(sz),
            "--expected-asof",
            asof,
            "--expected-count",
            str(cnt),  # 이전 count.
        ]
    )
    out = json.loads(capsys.readouterr().out)
    assert rc == 4
    assert out["atomic_activation_completed"] is False
    # 재검증에서 hash / size / count 중 하나로 차단.
    assert any(
        kw in out["error_reason"]
        for kw in (
            "expected_hash_mismatch",
            "expected_size_mismatch",
            "expected_count_mismatch",
        )
    )


def test_activate_rejects_temp_and_active_different_dirs(tmp_path, capsys) -> None:
    """§19.2: temp 와 active 가 다른 디렉터리면 activate 차단."""
    d1 = tmp_path / "a"
    d2 = tmp_path / "b"
    d1.mkdir()
    d2.mkdir()
    temp = d1 / "u.json"
    _write_artifact(temp, _artifact())
    h, sz, asof, cnt = _prepare_meta(temp)
    active = d2 / "u.json"
    rc = pub_main(
        [
            "activate",
            "--temp",
            str(temp),
            "--active",
            str(active),
            "--expected-hash",
            h,
            "--expected-size",
            str(sz),
            "--expected-asof",
            asof,
            "--expected-count",
            str(cnt),
        ]
    )
    out = json.loads(capsys.readouterr().out)
    assert rc == 4
    assert "temp_and_active_in_different_directories" in out["error_reason"]


def test_verify_stdout_no_artifact_original_or_traceback(tmp_path, capsys) -> None:
    """§17 최소 stdout: sanitized. verify 결과에 artifact 원문 · stack trace 미노출."""
    temp = tmp_path / "u.json"
    art = _artifact(candidates=[{"ticker": "A", "name": "SECRET_CANDIDATE_MARKER"}])
    _write_artifact(temp, art)
    h, sz, asof, cnt = _prepare_meta(temp)
    pub_main(_verify_args(temp, h, sz, asof, cnt))
    out_text = capsys.readouterr().out
    # verify 는 후보 개수만 반환 · 후보 이름 등 원문 미노출.
    assert "SECRET_CANDIDATE_MARKER" not in out_text
    assert "Traceback" not in out_text
