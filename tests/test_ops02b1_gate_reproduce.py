"""POC3-OPS-02B-1 — Gate 재현 스크립트 계약 test.

검증자 r3 B-6 대응. `reproduce.py` 에 계약 테스트가 없어, **coverage 판정값
미반환**과 **API–CSV 불일치 미제외**가 전체 1,446건 회귀를 그대로 통과했다.

여기서 고정하는 것은 "정상 입력에서 숫자가 맞는가" 가 아니라 **"계약 이하 입력이
성공으로 끝나지 않는가"** 다.
"""

from __future__ import annotations

import pytest

from scripts.ops02b1_gate import reproduce as R


def _row(complete=True, value="1.0"):
    row = {f: value for f in R.PRIMARY_FEATURES}
    row["usdkrw_ret_1d_pct"] = value
    row["primary_complete"] = "True" if complete else "False"
    return row


# ── coverage fail-closed ────────────────────────────────────────────────────


def test_coverage_ok_when_sample_and_ratio_met():
    stats, ok = R.evaluate_coverage([_row() for _ in range(2866)])
    assert ok is True
    assert stats["complete"] == 2866
    assert stats["sample_ok"] and stats["coverage_ok"]


def test_coverage_zero_is_not_ok():
    """강제로 0% 를 만들면 **반드시 실패**여야 한다 (r3 A-1)."""
    _, ok = R.evaluate_coverage([_row(complete=False) for _ in range(2866)])
    assert ok is False


def test_coverage_below_threshold_is_not_ok():
    rows = [_row() for _ in range(940)] + [_row(complete=False) for _ in range(60)]
    stats, ok = R.evaluate_coverage(rows)
    assert stats["ratio"] == pytest.approx(0.94)
    assert ok is False, "94% 인데 통과시켰다"


def test_coverage_sample_shortfall_is_not_ok():
    """비율이 100% 여도 **표본 750일 미만**이면 실패다."""
    stats, ok = R.evaluate_coverage([_row() for _ in range(700)])
    assert stats["coverage_ok"] is True
    assert stats["sample_ok"] is False
    assert ok is False


def test_coverage_threshold_constants():
    assert R.MIN_SAMPLE_DAYS == 750
    assert R.MIN_COVERAGE == 0.95
    assert R.MIN_JOIN_COVERAGE == 0.95


# ── API–CSV 일치 필터 ───────────────────────────────────────────────────────


def test_api_mismatch_is_excluded_not_just_reported():
    """지수명이 다르면 **제외**해야 한다. 출력만 하면 계약이 아니다 (r3 A-1)."""
    meta = [
        {"단축코드": "A", "기초지수명": "코스피 200"},
        {"단축코드": "B", "기초지수명": "코스피 200"},
        {"단축코드": "C", "기초지수명": "코스닥 150"},
    ]
    api = {"A": "코스피 200", "B": "다른 지수명"}
    kept, excluded = R.select_index_universe(meta, api)
    assert [r["단축코드"] for r in kept] == ["A"]
    assert excluded["name_mismatch"] == ["B"]
    assert excluded["not_in_api"] == ["C"]


def test_api_match_does_not_repair_names():
    """이름을 고쳐 맞추지 않는다 — 임의 보완 금지."""
    meta = [{"단축코드": "A", "기초지수명": "코스피200"}]
    api = {"A": "코스피 200"}  # 공백 하나 차이
    kept, excluded = R.select_index_universe(meta, api)
    assert kept == []
    assert excluded["name_mismatch"] == ["A"]


def test_all_matched_keeps_everything():
    meta = [{"단축코드": "A", "기초지수명": "X"}, {"단축코드": "B", "기초지수명": "Y"}]
    kept, excluded = R.select_index_universe(meta, {"A": "X", "B": "Y"})
    assert len(kept) == 2
    assert excluded == {"not_in_api": [], "name_mismatch": []}


# ── 상품 필터 · 그룹 · n>=2 ────────────────────────────────────────────────


def _meta_row(
    code, name, asset="주식", multiple="일반", method="실물(패시브)", agency="KRX"
):
    return {
        "단축코드": code,
        "기초지수명": name,
        "기초자산분류": asset,
        "추적배수": multiple,
        "복제방법": method,
        "지수산출기관": agency,
    }


def test_eligible_excludes_leverage_inverse_synthetic_and_nonequity():
    meta = [
        _meta_row("A", "X"),
        _meta_row("B", "X", multiple="2X 레버리지"),
        _meta_row("C", "X", multiple="1X 인버스"),
        _meta_row("D", "X", method="합성(패시브)"),
        _meta_row("E", "X", asset="채권"),
    ]
    assert [r["단축코드"] for r in R.eligible(meta)] == ["A"]


def test_index_groups_use_exact_agency_and_name():
    """식별키는 `지수산출기관 + 기초지수명` **완전일치**. fuzzy 금지."""
    meta = [
        _meta_row("A", "코스피 200", agency="KRX"),
        _meta_row("B", "코스피 200", agency="KRX"),
        _meta_row("C", "코스피 200", agency="다른기관"),
        _meta_row("D", "코스피200", agency="KRX"),
    ]
    groups = R.index_groups(R.eligible(meta))
    assert groups[("KRX", "코스피 200")] == {"A", "B"}
    assert groups[("다른기관", "코스피 200")] == {"C"}
    assert groups[("KRX", "코스피200")] == {"D"}


# ── CLI 종료코드 ────────────────────────────────────────────────────────────


def test_unknown_section_returns_nonzero():
    assert R.main(["없는섹션"]) == 2


def test_main_returns_nonzero_when_section_fails(monkeypatch):
    monkeypatch.setitem(R.SECTIONS, "coverage", lambda: False)
    assert R.main(["coverage"]) == 1


def test_main_returns_zero_when_section_passes(monkeypatch):
    monkeypatch.setitem(R.SECTIONS, "coverage", lambda: True)
    assert R.main(["coverage"]) == 0


# ── 읽기 전용 ───────────────────────────────────────────────────────────────


def test_write_results_defaults_to_false():
    """기본 실행은 tracked 산출물을 덮지 않는다 (r3 A-2)."""
    assert R.WRITE_RESULTS is False


def test_reproduce_does_not_import_sqlite3():
    """운영 DB 접근 경로가 아예 없어야 한다."""
    import inspect

    source = inspect.getsource(R)
    assert "import sqlite3" not in source
    assert "market_data.sqlite" not in source
