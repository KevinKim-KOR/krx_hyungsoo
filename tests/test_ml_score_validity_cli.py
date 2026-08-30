"""POC3-ML-02 — CLI 실행 경로 통합 테스트 (검증자 r2 지적 P1 대응).

`preflight_gate()` 반환값만 보는 단위 테스트로는 "실패가 **실제 실행을 막는다**"
를 증명하지 못한다. 본 모듈은 CLI `main()` 을 실제로 돌려 아래를 확인한다.

- 차단 시 `aggregate()` 가 **호출되지 않는다**
- 차단 시 `run_latest` 에 `BLOCKED_*` 와 해당 날짜가 기록된다
- 차단 시 `validity_latest` 가 **발행되지 않는다** (기존 파일도 제거된다)
- 차단 시 종료코드가 **3**
- 통과 시에만 `validity_latest` 가 발행되고 종료코드가 0

무거운 경로(라이브 DB 적재 · U2 재현 · E1 재현)는 monkeypatch 로 대체하고,
**게이트 판정과 발행 분기는 실제 코드**를 그대로 태운다.
"""

from __future__ import annotations

import importlib
import json

import pytest

from app.ml_relative_upside_features import KODEX200_TICKER
from app.ml_score_validity_eval import BLOCKING_MIN_COVERAGE

cli = importlib.import_module("scripts.run_ml_score_validity_eval_v1")


# --- fixture -----------------------------------------------------------------


def _days(months: int = 12) -> list[str]:
    out: list[str] = []
    for m in range(1, months + 1):
        for d in range(1, 21):
            out.append(f"2020-{m:02d}-{d:02d}")
    return out


def _series(days, start, step):
    return [(d, start + step * i) for i, d in enumerate(days)]


def _walk(days, seed: int) -> list[tuple[str, float]]:
    """결정적 의사난수 가격 시계열. 종목마다 다른 궤적을 만든다.

    단조 시계열만 쓰면 횡단면 IC 가 항상 ±1 로 고정돼 N-1 negative control 이
    의미를 잃는다. 실제 실행 경로를 태우려면 IC 가 잡음을 가져야 한다.
    """
    state = (seed * 6364136223846793005 + 1442695040888963407) % (2**31)
    out: list[tuple[str, float]] = []
    price = 100.0 + (seed % 17)
    for d in days:
        state = (state * 1103515245 + 12345) % (2**31)
        price *= 1.0 + ((state % 2001) - 1000) / 40000.0
        out.append((d, round(price, 4)))
    return out


def _prices(*, good_count: int = 30, stale_count: int = 0, stale_cut=None) -> dict:
    """정상 ticker + `stale_count` 개의 '기준일 이후 가격 없음' ticker.

    stale ticker 는 PIT 편입 조건(관측치 21개 이상 · 20거래일 경과)을 만족하고
    점수도 산출되지만, 진입일 가격이 없어 **라벨을 만들 수 없다** → coverage 하락.
    """
    days = _days()
    prices = {KODEX200_TICKER: _walk(days, 1)}
    for i in range(good_count):
        prices[f"GOOD{i:02d}"] = _walk(days, 100 + i)
    for i in range(stale_count):
        full = _walk(days, 500 + i)
        prices[f"STALE{i:02d}"] = (
            full if stale_cut is None else [(d, c) for d, c in full if d <= stale_cut]
        )
    return prices


def _install(monkeypatch, prices, *, spy_aggregate=None):
    """무거운 외부 경로만 대체한다. 게이트·발행 분기는 실제 코드."""
    monkeypatch.setattr(cli, "load_prices", lambda *a, **k: prices)
    monkeypatch.setattr(cli, "build_tag_map", lambda *a, **k: {t: [] for t in prices})
    monkeypatch.setattr(cli, "replay_screen_slates", lambda *a, **k: {})
    monkeypatch.setattr(
        cli, "build_frozen_descriptor", lambda: {"score_version": "test"}
    )
    calls: list[int] = []
    real_aggregate = cli.aggregate

    def _spy(*a, **k):
        calls.append(1)
        return real_aggregate(*a, **k)

    monkeypatch.setattr(cli, "aggregate", spy_aggregate or _spy)
    return calls


def _run(tmp_path, limit=3):
    return cli.main(
        ["--limit-dates", str(limit), "--skip-e1", "--out-dir", str(tmp_path)]
    )


def _paths(tmp_path):
    return (
        tmp_path / cli.RESULT_FILENAME,
        tmp_path / cli.RUN_META_FILENAME,
    )


# --- 통과 경로: 발행된다 ------------------------------------------------------


def test_cli_emits_validity_latest_when_gate_passes(tmp_path, monkeypatch):
    calls = _install(monkeypatch, _prices())
    rc = _run(tmp_path)
    result_path, meta_path = _paths(tmp_path)

    assert rc == 0
    assert calls == [1], "통과 경로에서는 aggregate 가 정확히 1회 호출돼야 한다"
    assert result_path.exists(), "통과 시 validity_latest 가 발행돼야 한다"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["status"] in ("REJECT", "RESEARCH_ONLY")
    assert meta["result_path"] == str(result_path)
    assert meta["canonical_sha256"]
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["preflight_gate"]["status"] == "OK"


# --- 차단 경로: coverage --------------------------------------------------


def test_cli_blocks_and_does_not_emit_when_coverage_below_threshold(
    tmp_path, monkeypatch
):
    """실제 게이트가 coverage 로 막고, 발행이 실제로 일어나지 않는가."""
    calls = _install(
        monkeypatch, _prices(good_count=4, stale_count=26, stale_cut="2020-07-20")
    )
    rc = _run(tmp_path)
    result_path, meta_path = _paths(tmp_path)

    assert rc == 3, "차단 시 종료코드는 3 이어야 한다"
    assert calls == [], "차단 시 aggregate 가 호출되면 안 된다"
    assert not result_path.exists(), "차단 시 validity_latest 를 발행하면 안 된다"

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["status"] == "BLOCKED_COVERAGE"
    assert "BLOCKED_COVERAGE" in meta["blocked"]
    assert meta["result_path"] is None
    blocked_dates = meta["blocked_details"]["BLOCKED_COVERAGE"]["dates"]
    assert blocked_dates, "차단된 기준일이 기록돼야 한다"
    for entry in blocked_dates:
        assert entry["coverage"] is None or entry["coverage"] < BLOCKING_MIN_COVERAGE


def test_cli_removes_stale_validity_latest_when_blocked(tmp_path, monkeypatch):
    """직전 정상 결과가 남아 있어도 차단되면 지워야 한다 (stale 발행 금지)."""
    result_path, meta_path = _paths(tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    result_path.write_text('{"stale": true}', encoding="utf-8")

    _install(monkeypatch, _prices(good_count=4, stale_count=26, stale_cut="2020-07-20"))
    rc = _run(tmp_path)

    assert rc == 3
    assert not result_path.exists(), "차단 시 기존 validity_latest 도 제거돼야 한다"
    assert json.loads(meta_path.read_text(encoding="utf-8"))["status"] == (
        "BLOCKED_COVERAGE"
    )


# --- 차단 경로: 누수 / N-1 -------------------------------------------------


def test_cli_blocks_on_leakage_violation(tmp_path, monkeypatch):
    calls = _install(monkeypatch, _prices())
    real_gate = cli.preflight_gate

    def _leaky(records, n1):
        for r in records:
            r["max_input_date"] = "2099-01-01"
        return real_gate(records, n1)

    monkeypatch.setattr(cli, "preflight_gate", _leaky)
    rc = _run(tmp_path)
    result_path, meta_path = _paths(tmp_path)

    assert rc == 3
    assert calls == []
    assert not result_path.exists()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["status"] == "BLOCKED_LEAKAGE"
    assert meta["blocked_details"]["BLOCKED_LEAKAGE"]["L1"]


def test_cli_blocks_on_n1_metric_control_failure(tmp_path, monkeypatch):
    calls = _install(monkeypatch, _prices())
    monkeypatch.setattr(
        cli,
        "shuffle_control_verdict",
        lambda *a, **k: {"passed": False, "verdict": "metric 구현 이상 의심"},
    )
    rc = _run(tmp_path)
    result_path, meta_path = _paths(tmp_path)

    assert rc == 3
    assert calls == []
    assert not result_path.exists()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert "BLOCKED_METRIC_CONTROL" in meta["blocked"]


# --- warmup 이 실제 실행에서 분리되는가 --------------------------------------


def test_cli_reports_warmup_dates_separately_in_payload(tmp_path, monkeypatch):
    """사전 고정 warmup 날짜가 달력에 있으면 평가에서 빠지고 별도 기록된다."""
    prices = _prices()
    _install(monkeypatch, prices)
    monkeypatch.setattr(
        cli, "PRE_EVALUATION_WARMUP_DATES", ("2020-10-20",), raising=False
    )
    monkeypatch.setattr(
        cli,
        "classify_phase",
        lambda d: cli.PHASE_WARMUP if d == "2020-10-20" else cli.PHASE_EVALUATION,
    )
    rc = _run(tmp_path, limit=3)
    result_path, _ = _paths(tmp_path)
    assert rc == 0
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    warmup_dates = [x["signal_date"] for x in payload["pre_evaluation_warmup"]["dates"]]
    assert "2020-10-20" in warmup_dates
    evaluated = [r["signal_date"] for r in payload["per_date"]]
    assert "2020-10-20" not in evaluated, "warmup 은 평가 레코드에 남으면 안 된다"


# --- 평가 구간 계약이 실제 실행을 막는가 -------------------------------------


def test_cli_enforces_evaluation_window_contract_on_full_run(tmp_path, monkeypatch):
    """`--limit-dates` 없이 돌리면 145개·2014-06-30 계약이 강제된다."""
    _install(monkeypatch, _prices())
    with pytest.raises(RuntimeError, match="시작일|평가일 수"):
        cli.main(["--skip-e1", "--out-dir", str(tmp_path)])
