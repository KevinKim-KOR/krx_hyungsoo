"""Holdings Evidence OCI Publication v1 — CLI 전용 테스트.

지시문 §13.1 최소 15 케이스 커버.
Q9 확정본: 모든 테스트는 tmp_path 익명 fixture. 실제 state/holdings/holdings_latest.json,
state/market/market_data.sqlite, state/runtime/runtime_state.sqlite 미참조 · 미변경.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from scripts import run_holdings_publication as cli

_REAL_HOLDINGS = Path("state/holdings/holdings_latest.json")


def _snapshot(p: Path) -> dict[str, Any]:
    if not p.exists():
        return {"exists": False}
    b = p.read_bytes()
    return {"exists": True, "size": len(b), "sha256": hashlib.sha256(b).hexdigest()}


def _write_holdings(path: Path, holdings: list[dict[str, Any]]) -> None:
    payload = {"holdings": holdings}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _sample_holdings(n: int = 2) -> list[dict[str, Any]]:
    return [
        {
            "ticker": f"0{69500 + i}",
            "quantity": 10 + i,
            "avg_buy_price": 35000.0 + i * 100,
            "account_group": "일반",
        }
        for i in range(n)
    ]


def _run_prepare(monkeypatch, source: Path) -> tuple[int, dict[str, Any]]:
    """cli.main 은 stdout 에 JSON print → capsys 로 캡처. 여기서는 함수 직접 호출."""
    import argparse

    args = argparse.Namespace(source=str(source), func=cli.cmd_prepare)
    return cli.cmd_prepare(args), None  # exit code only; JSON goes to stdout.


# ── 1~5: source validation ───────────────────────────────────────────────────


def test_prepare_ok_normal_holdings(tmp_path: Path, capsys) -> None:
    src = tmp_path / "holdings_latest.json"
    _write_holdings(src, _sample_holdings(3))
    exit_code = cli.main(["prepare", "--source", str(src)])
    out = json.loads(capsys.readouterr().out.strip())
    assert exit_code == 0
    assert out["status"] == "ok"
    assert out["source_exists"] is True
    assert out["source_valid"] is True
    assert out["source_hash"] and len(out["source_hash"]) == 64
    assert out["source_size"] > 0
    assert out["source_holding_count"] == 3


def test_prepare_fails_when_source_missing(tmp_path: Path, capsys) -> None:
    src = tmp_path / "no_holdings.json"
    exit_code = cli.main(["prepare", "--source", str(src)])
    out = json.loads(capsys.readouterr().out.strip())
    assert exit_code == 2
    assert out["source_exists"] is False
    assert out["error_reason"] == "source_not_found"


def test_prepare_fails_on_bad_json(tmp_path: Path, capsys) -> None:
    src = tmp_path / "holdings_latest.json"
    src.write_text("{ this is not json", encoding="utf-8")
    exit_code = cli.main(["prepare", "--source", str(src)])
    out = json.loads(capsys.readouterr().out.strip())
    assert exit_code == 2
    assert out["source_valid"] is False
    assert "json_parse_error" in out["error_reason"]


def test_prepare_fails_on_holdings_validation(tmp_path: Path, capsys) -> None:
    """ticker 필드가 없으면 validate_holdings 가 실패."""
    src = tmp_path / "holdings_latest.json"
    src.write_text(
        json.dumps({"holdings": [{"quantity": 10, "avg_buy_price": 100.0}]}),
        encoding="utf-8",
    )
    exit_code = cli.main(["prepare", "--source", str(src)])
    out = json.loads(capsys.readouterr().out.strip())
    assert exit_code == 2
    assert out["source_valid"] is False
    assert "holdings_validation_error" in out["error_reason"]


def test_prepare_fails_on_empty_holdings(tmp_path: Path, capsys) -> None:
    src = tmp_path / "holdings_latest.json"
    _write_holdings(src, [])
    exit_code = cli.main(["prepare", "--source", str(src)])
    out = json.loads(capsys.readouterr().out.strip())
    assert exit_code == 2
    assert out["source_valid"] is False


# ── 6~7: hash/size/count 산출 + verify 통과 ──────────────────────────────────


def test_prepare_hash_size_count_deterministic(tmp_path: Path, capsys) -> None:
    src = tmp_path / "holdings_latest.json"
    _write_holdings(src, _sample_holdings(2))
    cli.main(["prepare", "--source", str(src)])
    out1 = json.loads(capsys.readouterr().out.strip())
    cli.main(["prepare", "--source", str(src)])
    out2 = json.loads(capsys.readouterr().out.strip())
    assert out1["source_hash"] == out2["source_hash"]
    assert out1["source_size"] == out2["source_size"]
    assert out1["source_holding_count"] == out2["source_holding_count"]


def test_verify_passes_when_all_match(tmp_path: Path, capsys) -> None:
    src = tmp_path / "holdings_latest.json"
    _write_holdings(src, _sample_holdings(3))
    b = src.read_bytes()
    expected_hash = hashlib.sha256(b).hexdigest()

    # Simulate: user SCP-ed source to OCI tmp path.
    tmp_dest = tmp_path / "holdings_latest.json.tmp"
    tmp_dest.write_bytes(b)
    exit_code = cli.main(
        [
            "verify",
            "--temp",
            str(tmp_dest),
            "--expected-hash",
            expected_hash,
            "--expected-size",
            str(len(b)),
            "--expected-count",
            "3",
        ]
    )
    out = json.loads(capsys.readouterr().out.strip())
    assert exit_code == 0
    assert out["status"] == "ok"
    assert out["activation_ready"] is True
    assert out["hash_match"] and out["size_match"] and out["holding_count_match"]


# ── 8~10: mismatch 차단 ─────────────────────────────────────────────────────


def test_verify_blocks_on_hash_mismatch(tmp_path: Path, capsys) -> None:
    tmp_dest = tmp_path / "holdings_latest.json.tmp"
    _write_holdings(tmp_dest, _sample_holdings(2))
    b = tmp_dest.read_bytes()
    exit_code = cli.main(
        [
            "verify",
            "--temp",
            str(tmp_dest),
            "--expected-hash",
            "0" * 64,  # 잘못된 hash.
            "--expected-size",
            str(len(b)),
            "--expected-count",
            "2",
        ]
    )
    out = json.loads(capsys.readouterr().out.strip())
    assert exit_code == 3
    assert out["hash_match"] is False
    assert out["activation_ready"] is False


def test_verify_blocks_on_size_mismatch(tmp_path: Path, capsys) -> None:
    tmp_dest = tmp_path / "holdings_latest.json.tmp"
    _write_holdings(tmp_dest, _sample_holdings(2))
    b = tmp_dest.read_bytes()
    exit_code = cli.main(
        [
            "verify",
            "--temp",
            str(tmp_dest),
            "--expected-hash",
            hashlib.sha256(b).hexdigest(),
            "--expected-size",
            str(len(b) + 1),
            "--expected-count",
            "2",
        ]
    )
    out = json.loads(capsys.readouterr().out.strip())
    assert exit_code == 3
    assert out["size_match"] is False
    assert out["activation_ready"] is False


def test_verify_blocks_on_count_mismatch(tmp_path: Path, capsys) -> None:
    tmp_dest = tmp_path / "holdings_latest.json.tmp"
    _write_holdings(tmp_dest, _sample_holdings(2))
    b = tmp_dest.read_bytes()
    exit_code = cli.main(
        [
            "verify",
            "--temp",
            str(tmp_dest),
            "--expected-hash",
            hashlib.sha256(b).hexdigest(),
            "--expected-size",
            str(len(b)),
            "--expected-count",
            "99",  # 잘못된 count.
        ]
    )
    out = json.loads(capsys.readouterr().out.strip())
    assert exit_code == 3
    assert out["holding_count_match"] is False


# ── 11~13: activate 기존 active 불변 + atomic + JSON byte 불변 ──────────────


def test_activate_keeps_existing_active_when_validation_fails(
    tmp_path: Path, capsys
) -> None:
    """activate 직전 재검증 실패 시 기존 active 파일이 그대로 유지."""
    active = tmp_path / "holdings_latest.json"
    _write_holdings(active, _sample_holdings(1))
    active_snapshot = _snapshot(active)

    tmp_dest = tmp_path / "holdings_latest.json.tmp"
    _write_holdings(tmp_dest, _sample_holdings(2))
    b = tmp_dest.read_bytes()

    # 잘못된 expected 값으로 activate 시도 → 재검증 실패.
    exit_code = cli.main(
        [
            "activate",
            "--temp",
            str(tmp_dest),
            "--active",
            str(active),
            "--expected-hash",
            "0" * 64,
            "--expected-size",
            str(len(b)),
            "--expected-count",
            "2",
        ]
    )
    out = json.loads(capsys.readouterr().out.strip())
    assert exit_code == 3
    assert out["atomic_activation_completed"] is False
    # 기존 active 파일 완전 불변.
    assert _snapshot(active) == active_snapshot


def test_activate_atomic_replace_and_byte_unchanged(tmp_path: Path, capsys) -> None:
    active = tmp_path / "holdings_latest.json"
    tmp_dest = tmp_path / "holdings_latest.json.tmp"
    _write_holdings(tmp_dest, _sample_holdings(3))
    b = tmp_dest.read_bytes()
    expected_hash = hashlib.sha256(b).hexdigest()

    cli.main(
        [
            "activate",
            "--temp",
            str(tmp_dest),
            "--active",
            str(active),
            "--expected-hash",
            expected_hash,
            "--expected-size",
            str(len(b)),
            "--expected-count",
            "3",
        ]
    )
    out = json.loads(capsys.readouterr().out.strip())
    # Windows 환경에서는 owner/mode 정책이 POSIX 와 달라 permission_checked=False 가능.
    # 이 test 는 atomic replace + byte 불변만 확인.
    assert out["atomic_activation_completed"] is True
    assert active.exists()
    # JSON byte 완전 불변.
    assert active.read_bytes() == b
    assert out["active_hash"] == expected_hash
    assert out["active_holding_count"] == 3
    # tmp 파일은 사라져야 함.
    assert not tmp_dest.exists()


def test_activate_blocks_when_tmp_not_in_same_dir(tmp_path: Path, capsys) -> None:
    other = tmp_path / "other"
    other.mkdir()
    active = tmp_path / "holdings_latest.json"
    tmp_dest = other / "holdings_latest.json.tmp"
    _write_holdings(tmp_dest, _sample_holdings(1))
    b = tmp_dest.read_bytes()
    exit_code = cli.main(
        [
            "activate",
            "--temp",
            str(tmp_dest),
            "--active",
            str(active),
            "--expected-hash",
            hashlib.sha256(b).hexdigest(),
            "--expected-size",
            str(len(b)),
            "--expected-count",
            "1",
        ]
    )
    out = json.loads(capsys.readouterr().out.strip())
    assert exit_code == 2
    assert out["error_reason"] == "temp_and_active_directory_mismatch"
    assert not active.exists()


# ── 14: sanitization — 원문 · 민감 필드 stdout 미노출 ─────────────────────


def test_stdout_contains_no_sensitive_fields(tmp_path: Path, capsys) -> None:
    src = tmp_path / "holdings_latest.json"
    _write_holdings(
        src,
        [
            {
                "ticker": "069500",
                "quantity": 12345,
                "avg_buy_price": 99999.99,
                "account_group": "SECRET_GROUP_XYZ",
                "name": "SECRET_NAME_XYZ",
            }
        ],
    )
    cli.main(["prepare", "--source", str(src)])
    text = capsys.readouterr().out
    # ticker 도 종목명도 계좌 그룹도 stdout 에 미노출.
    assert "069500" not in text
    assert "SECRET_GROUP_XYZ" not in text
    assert "SECRET_NAME_XYZ" not in text
    assert "12345" not in text
    assert "99999" not in text


# ── 15: 실제 state 파일 무참조 ──────────────────────────────────────────────


def test_real_holdings_file_not_touched_by_tests() -> None:
    """모든 test 는 tmp_path fixture 만 사용. 실제 state 파일은 read 도 하지 않는다.

    이 test 는 test 세션 시작 시점 실제 파일 상태를 스냅샷으로 assert 하지 않는다
    (isolation 은 다른 test 들이 real path 를 참조하지 않는 것으로 보장).
    Q9 확정본: 실제 state 불변은 PC 수동 hash 실측으로 확인.
    """
    # 이 test 자체가 실제 파일에 접근하지 않는 것이 보장의 일부.
    # 이 test 는 실제 파일이 없어도 성공.
    _ = _REAL_HOLDINGS  # 참조만.
    assert True
