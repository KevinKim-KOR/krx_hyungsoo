"""POC3-OPS-02B-2 — 계약 test.

설계자 §8(24종) + PLAN §K(25~37) + §M-8(38~57) 대응. 합성 fixture 와 임시 DB 만
쓴다. **외부 조회 0건 · 라이브 DB·state 미접근 · 발송 0건.**

고정하는 것은 "정상 입력에서 숫자가 맞는가" 보다 **"계약 이하 입력이 성공으로
끝나지 않는가"** 다.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import inspect
import io
import json
import re
from pathlib import Path

import pytest

from app.market_briefing import calendar as cal
from app.market_briefing import evidence as ev
from app.market_briefing import flow, krx_store, meta_gate, render
from app.market_briefing import official_csv as oc

# ── fixture 헬퍼 ────────────────────────────────────────────────────────────


def _meta(code, name, agency="KRX", asset="주식", mult="일반", method="실물(패시브)"):
    return {
        "단축코드": code,
        "기초지수명": name,
        "지수산출기관": agency,
        "기초자산분류": asset,
        "추적배수": mult,
        "복제방법": method,
    }


def _api_row(code, date="20260904", close="10000"):
    return {"ISU_CD": code, "BAS_DD": date, "TDD_CLSPRC": close}


def _write_calendar(tmp_path, days):
    p = tmp_path / "krx_trading_days_2026.csv"
    p.write_text("date\n" + "\n".join(days) + "\n", encoding="utf-8")
    return tmp_path


TRADING_DAYS_2026 = [f"2026-09-{d:02d}" for d in (1, 2, 3, 4, 7, 8, 9, 10, 11)]


def _code_only(module) -> str:
    """docstring·주석을 뺀 **실행 코드**만.

    문서에 설명으로 적힌 단어까지 금지어로 잡으면 계약이 아니라 문장을 검사하게
    된다. 실제로 두 테스트가 docstring 을 잡았다.
    """
    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body.pop(0)
    return ast.unparse(tree)


# ═══ 계약 1~4 · 31~32 — 전망 `SP500_SIGN_V1` ═══════════════════════════════


def test_outlook_up_and_down_sentence():
    up = ev.decide_outlook(
        sp500_return_pct=1.2, sp500_asof="2026-09-10", sp500_fresh=True
    )
    dn = ev.decide_outlook(
        sp500_return_pct=-1.2, sp500_asof="2026-09-10", sp500_fresh=True
    )
    assert up.state == ev.OUTLOOK_UP and dn.state == ev.OUTLOOK_DOWN
    assert render.outlook_sentence(up) == render.SENTENCE_UP
    assert render.outlook_sentence(dn) == render.SENTENCE_DOWN
    assert "직전 미국 거래일" in render.SENTENCE_UP


def test_mixed_state_does_not_exist():
    """`MIXED` 상태값이 코드에 없다 (설계 §3.2)."""
    for mod in (ev, render, flow):
        assert "MIXED" not in _code_only(mod)


def test_flat_sp500_uses_flat_sentence():
    """정확히 0 이면 임의 중립 구간을 만들지 않고 `FLAT` 이다."""
    o = ev.decide_outlook(
        sp500_return_pct=0.0, sp500_asof="2026-09-10", sp500_fresh=True
    )
    assert o.state == ev.OUTLOOK_FLAT
    assert render.outlook_sentence(o) == render.SENTENCE_FLAT


def test_stale_sp500_is_none():
    o = ev.decide_outlook(
        sp500_return_pct=1.0, sp500_asof="2026-07-03", sp500_fresh=False
    )
    assert o.state == ev.OUTLOOK_NONE
    assert render.outlook_sentence(o) is None


def test_decide_outlook_takes_only_sp500():
    """Nasdaq·반도체가 방향에 개입할 수 없는 구조여야 한다."""
    sig = inspect.signature(ev.decide_outlook)
    assert set(sig.parameters) == {"sp500_return_pct", "sp500_asof", "sp500_fresh"}


def test_body_has_no_predicted_pct():
    """예상 개장 등락률 숫자를 만들지 않는다."""
    o = ev.decide_outlook(
        sp500_return_pct=1.2, sp500_asof="2026-09-10", sp500_fresh=True
    )
    text = render.render_market_briefing(
        outlook=o, index_status=render.STATUS_NO_CANDIDATE_NORMAL, us_asof="2026-09-10"
    )
    for banned in ("예상", "전망치", "개장 예상"):
        assert banned not in text
    for banned in ("매수", "매도", "교체", "상승 섹터", "유망 테마", "적중률"):
        assert banned not in text


# ═══ 계약 5~7 · 49~50 — 기초지수 산출 ══════════════════════════════════════


def _closes(tickers, latest=10000.0, d5=9000.0, d20=8000.0):
    return {
        "L": {t: latest for t in tickers},
        "5": {t: d5 for t in tickers},
        "20": {t: d20 for t in tickers},
    }


def _leader(meta, closes):
    return ev.compute_index_leadership(
        meta_rows=meta, closes=closes, latest="L", d5="5", d20="20"
    )


def test_single_ticker_index_excluded():
    """`n=1` 은 후보가 아니다. fallback 으로 부활시키지 않는다."""
    r = _leader([_meta("A", "X")], _closes(["A"]))
    assert r.candidates == []
    assert r.diagnostics["dropped_insufficient_valid_tickers"] == 1


def test_two_tickers_qualify():
    r = _leader([_meta("A", "X"), _meta("B", "X")], _closes(["A", "B"]))
    assert [c.name for c in r.candidates] == ["X"]
    assert r.candidates[0].ticker_count == 2


def test_nonpositive_return_excluded():
    """5일 또는 20일이 0 이하면 후보가 아니다."""
    meta = [_meta("A", "X"), _meta("B", "X")]
    flat5 = {
        "L": {"A": 9000.0, "B": 9000.0},
        "5": {"A": 9000.0, "B": 9000.0},
        "20": {"A": 8000.0, "B": 8000.0},
    }
    assert _leader(meta, flat5).candidates == []


def test_missing_any_of_three_prices_excludes_ticker():
    """세 기준 가격이 모두 있어야 `n` 에 포함한다 (§M-4)."""
    meta = [_meta("A", "X"), _meta("B", "X")]
    c = _closes(["A", "B"])
    del c["20"]["B"]  # B 는 20일 전 가격 없음
    r = _leader(meta, c)
    assert r.candidates == [], "결측 ticker 를 n 에 포함했다"


def test_stale_tickers_dropped_then_n_below_two():
    meta = [_meta("A", "X"), _meta("B", "X"), _meta("C", "Y"), _meta("D", "Y")]
    c = _closes(["A", "C", "D"])  # B 누락
    r = _leader(meta, c)
    assert [x.name for x in r.candidates] == ["Y"]


def test_leverage_inverse_synthetic_nonequity_excluded():
    meta = [
        _meta("A", "X"),
        _meta("B", "X", mult="2X 레버리지"),
        _meta("C", "X", mult="1X 인버스"),
        _meta("D", "X", method="합성(패시브)"),
        _meta("E", "X", asset="채권"),
    ]
    assert [r["단축코드"] for r in ev.eligible_products(meta)] == ["A"]


def test_top2_limit_and_deterministic_tie_break():
    meta = []
    closes = {"L": {}, "5": {}, "20": {}}
    # 세 그룹, 20일 수익률 동률 → 5일 → 식별자 순
    for i, (name, agency, d5) in enumerate(
        [("B지수", "KRX", 9000.0), ("A지수", "KRX", 9000.0), ("C지수", "KRX", 8500.0)]
    ):
        for k in range(2):
            t = f"{i}{k}"
            meta.append(_meta(t, name, agency=agency))
            closes["L"][t], closes["5"][t], closes["20"][t] = 10000.0, d5, 8000.0
    r = _leader(meta, closes)
    assert len(r.candidates) == 2, "상위 2개 제한이 없다"
    assert [c.name for c in r.candidates] == ["C지수", "A지수"]


def test_group_key_is_exact_agency_and_name():
    meta = [
        _meta("A", "코스피 200", agency="KRX"),
        _meta("B", "코스피 200", agency="다른기관"),
        _meta("C", "코스피200", agency="KRX"),
    ]
    g = ev.group_by_index(ev.eligible_products(meta))
    assert len(g) == 3, "fuzzy matching 으로 합쳐졌다"


def test_kospi200_is_not_specially_excluded():
    """`코스피 200` 이라는 이유만으로 빼지 않는다 (§M-4)."""
    r = _leader(
        [_meta("A", "코스피 200"), _meta("B", "코스피 200")], _closes(["A", "B"])
    )
    assert [c.name for c in r.candidates] == ["코스피 200"]


# ═══ 계약 8 · 37 — 부분 산출과 안내 문구 ═══════════════════════════════════


def _up():
    return ev.decide_outlook(
        sp500_return_pct=1.0, sp500_asof="2026-09-10", sp500_fresh=True
    )


def test_zero_candidate_omits_block_without_notice():
    text = render.render_market_briefing(
        outlook=_up(), index_status=render.STATUS_NO_CANDIDATE_NORMAL
    )
    assert "오늘 볼 기초지수" not in text
    assert "제외했습니다" not in text, "정상 0개인데 안내 문구를 넣었다"


@pytest.mark.parametrize(
    "status,fragment",
    [
        (meta_gate.STATUS_CSV_REFRESH_REQUIRED, "공식 기준정보 갱신이 필요해"),
        (meta_gate.STATUS_COVERAGE_BELOW_THRESHOLD, "정합성 조건을 충족하지 않아"),
        (meta_gate.STATUS_API_FETCH_FAILED, "최신 기준을 확인하지 못해"),
        ("stale", "최신성 조건을 충족하지 않아"),
    ],
)
def test_notice_sentence_matches_internal_state(status, fragment):
    text = render.render_market_briefing(outlook=_up(), index_status=status)
    assert fragment in text
    assert status not in text, "기술 상태명을 본문에 노출했다"


def test_no_outlook_with_candidates_renders_index_only():
    none = ev.decide_outlook(sp500_return_pct=None, sp500_asof=None, sp500_fresh=False)
    c = ev.IndexCandidate("KRX", "X", 1.0, 2.0, 2)
    text = render.render_market_briefing(
        outlook=none, index_status="ok", candidates=[c]
    )
    assert render.SENTENCE_NO_OUTLOOK in text
    assert "오늘 볼 기초지수" in text
    assert "압력으로 해석" not in text


def test_no_outlook_no_candidate_renders_empty():
    none = ev.decide_outlook(sp500_return_pct=None, sp500_asof=None, sp500_fresh=False)
    assert render.render_market_briefing(outlook=none, index_status="stale") == ""


def test_distinct_asof_dates_shown_separately():
    text = render.render_market_briefing(
        outlook=_up(),
        index_status="ok",
        candidates=[ev.IndexCandidate("KRX", "X", 1.0, 2.0, 2)],
        us_asof="2026-09-10",
        kr_asof="2026-09-11",
    )
    assert "미국 2026-09-10 종가" in text
    assert "국내 2026-09-11 종가" in text


# ═══ 계약 9~13 · 44~48 — API↔CSV 정합성 ═══════════════════════════════════


def test_api_only_ticker_forces_csv_refresh_required():
    """API-only 1건이면 **coverage 와 무관하게** 차단.

    d20 정보를 넘기지 않은 호출(옛 계약)이다 — 모든 API-only 가 차단 사유다.
    """
    api = {f"T{i}": "X" for i in range(100)}
    csv_rows = [_meta(f"T{i}", "X") for i in range(99)]
    r = meta_gate.evaluate_consistency(api_index_names=api, csv_rows=csv_rows)
    assert r.status == meta_gate.STATUS_CSV_REFRESH_REQUIRED
    assert r.api_only == ["T99"]
    assert r.join_coverage >= 0.95, "coverage 는 충분한데도 차단되어야 한다"


def test_name_mismatch_forces_csv_refresh_required():
    api = {f"T{i}": "X" for i in range(100)}
    csv_rows = [_meta(f"T{i}", "X" if i else "다른이름") for i in range(100)]
    r = meta_gate.evaluate_consistency(api_index_names=api, csv_rows=csv_rows)
    assert r.status == meta_gate.STATUS_CSV_REFRESH_REQUIRED
    assert r.name_mismatch == ["T0"]


def test_coverage_denominator_is_max_of_both():
    """API 부분 응답(행 수 급감)을 잡아야 한다."""
    api = {f"T{i}": "X" for i in range(50)}
    csv_rows = [_meta(f"T{i}", "X") for i in range(100)]
    r = meta_gate.evaluate_consistency(api_index_names=api, csv_rows=csv_rows)
    assert r.csv_only and not r.api_only
    assert r.join_coverage == pytest.approx(0.5)
    assert r.status == meta_gate.STATUS_COVERAGE_BELOW_THRESHOLD


def test_coverage_boundary_95():
    api = {f"T{i}": "X" for i in range(100)}
    csv95 = [_meta(f"T{i}", "X") for i in range(100)]
    assert (
        meta_gate.evaluate_consistency(api_index_names=api, csv_rows=csv95).status
        == meta_gate.STATUS_OK
    )


def test_empty_api_is_fetch_failure_not_mismatch():
    r = meta_gate.evaluate_consistency(api_index_names={}, csv_rows=[_meta("A", "X")])
    assert r.status == meta_gate.STATUS_API_FETCH_FAILED
    assert r.error == "empty_api_response"


def test_matched_rows_do_not_repair_names():
    rows = [_meta("A", "코스피200")]
    assert meta_gate.matched_meta_rows(rows, {"A": "코스피 200"}) == []


# ═══ POC3-02D-OPS-01 C1 — pending gate (설계자 Q1 (c)) ═══════════════════════
# d20 종가가 없는 API-only 는 차단하지 않고 pending(ticker · 첫 적재일)으로
# 남긴다. d20 종가가 있는 API-only · 지수명 불일치 · coverage 규칙은 그대로다.


def _gate(api, csv_rows, no_d20):
    return meta_gate.evaluate_consistency(
        api_index_names=api, csv_rows=csv_rows, no_d20_first_loaded=no_d20
    )


def _pending(ticker, first_loaded):
    return {"ticker": ticker, "first_loaded": first_loaded}


def test_api_only_without_d20_is_pending_not_blocking():
    api = {f"T{i}": "X" for i in range(100)}
    csv_rows = [_meta(f"T{i}", "X") for i in range(99)]
    # T5 도 d20 종가가 없지만 CSV 에 있다 — pending 이 아니다.
    r = _gate(api, csv_rows, {"T99": "2026-09-15", "T5": "2026-09-15"})
    assert r.status == meta_gate.STATUS_OK, "d20 없는 신규 ETF 가 블록을 막았다"
    assert r.usable
    assert r.api_only == ["T99"], "증거용 API-only 전체 목록이 바뀌었다"
    assert r.api_only_pending == [_pending("T99", "2026-09-15")]


def test_api_only_with_d20_still_forces_csv_refresh_required():
    api = {f"T{i}": "X" for i in range(100)}
    csv_rows = [_meta(f"T{i}", "X") for i in range(99)]
    r = _gate(api, csv_rows, {})  # T99 는 d20 종가가 있다
    assert r.status == meta_gate.STATUS_CSV_REFRESH_REQUIRED
    assert r.api_only == ["T99"]
    assert r.api_only_pending == []


def test_mixed_api_only_blocks_and_still_records_pending():
    api = {f"T{i}": "X" for i in range(100)}
    csv_rows = [_meta(f"T{i}", "X") for i in range(98)]
    r = _gate(api, csv_rows, {"T98": "2026-09-22"})  # T99 는 d20 종가가 있다
    assert r.status == meta_gate.STATUS_CSV_REFRESH_REQUIRED
    assert r.api_only == ["T98", "T99"]
    assert r.api_only_pending == [_pending("T98", "2026-09-22")]


def test_name_mismatch_still_blocks_with_pending_present():
    api = {f"T{i}": "X" for i in range(101)}
    csv_rows = [_meta(f"T{i}", "X" if i else "다른이름") for i in range(100)]
    r = _gate(api, csv_rows, {"T100": "2026-09-15"})
    assert r.status == meta_gate.STATUS_CSV_REFRESH_REQUIRED
    assert r.name_mismatch == ["T0"]
    assert r.api_only_pending == [_pending("T100", "2026-09-15")]


@pytest.mark.parametrize(
    "matched,new,expected",
    [
        (95, 5, meta_gate.STATUS_OK),  # 95/100 = 0.95 — 경계는 통과
        (94, 6, meta_gate.STATUS_COVERAGE_BELOW_THRESHOLD),  # 0.94
    ],
)
def test_pending_does_not_change_coverage_rule(matched, new, expected):
    """분자·분모가 그대로다 — pending 도 분모(큰 쪽)에 들어간다."""
    api = {f"T{i}": "X" for i in range(matched + new)}
    csv_rows = [_meta(f"T{i}", "X") for i in range(matched)]
    no_d20 = {f"T{i}": "2026-09-22" for i in range(matched, matched + new)}
    r = _gate(api, csv_rows, no_d20)
    assert r.exact_match_count == matched
    assert r.join_coverage == pytest.approx(matched / (matched + new))
    assert r.status == expected
    assert len(r.api_only_pending) == new


def test_oci_0925_shape_is_ok_with_pending():
    """09-25 07:20 실측 모양 — API-only 8(모두 d20 없음) · 불일치 0 · 0.993."""
    base = [f"{100000 + i}" for i in range(1167)]
    new = {
        **{t: "2026-09-15" for t in ("0227L0", "0238F0", "0239Y0", "0239Z0")},
        **{t: "2026-09-22" for t in ("0238C0", "0240J0", "0241R0", "0242S0")},
    }
    api = {t: "X" for t in base + list(new)}
    csv_rows = [_meta(t, "X") for t in base + ["465780"]]
    r = _gate(api, csv_rows, new)
    assert r.status == meta_gate.STATUS_OK
    assert r.api_only == sorted(new)
    assert r.csv_only == ["465780"] and r.name_mismatch == []
    assert r.exact_match_count == 1167
    assert r.join_coverage == pytest.approx(1167 / 1175)
    # 첫 적재일 순(09-15 4종 → 09-22 4종) · 같은 날은 ticker 순.
    order = sorted(new, key=lambda t: (new[t], t))
    assert r.api_only_pending == [_pending(t, new[t]) for t in order]


def test_pending_roundtrip_and_old_json_without_field(tmp_path):
    api = {f"T{i}": "X" for i in range(100)}
    csv_rows = [_meta(f"T{i}", "X") for i in range(99)]
    r = _gate(api, csv_rows, {"T99": "2026-09-15"})
    d = r.to_dict()
    assert d["api_only_pending_count"] == 1
    assert d["api_only_pending"] == [_pending("T99", "2026-09-15")]
    assert d["api_only"] == ["T99"] and d["api_only_count"] == 1

    p = tmp_path / "c.json"
    meta_gate.save_consistency(r, p)
    back = meta_gate.load_consistency(p)
    assert back.api_only_pending == r.api_only_pending
    assert back.status == meta_gate.STATUS_OK and back.usable

    # 필드가 없던 옛 07:20 JSON 도 그대로 읽힌다(pending 0).
    old = {k: v for k, v in d.items() if not k.startswith("api_only_pending")}
    legacy = meta_gate.ConsistencyResult.from_dict(old)
    assert legacy.api_only_pending == []
    assert legacy.to_dict()["api_only_pending_count"] == 0


def test_pending_list_is_not_truncated_and_earliest_first():
    """pending 은 자르지 않고 첫 적재일 순이다 — 08:00 이 읽어도 수·순서가 같다.

    20건에서 자르면 가장 먼저 적재된 ticker(곧 d20 을 얻어 차단으로 넘어갈
    종목)가 08:00 진단에서 빠지고 개수도 20 으로 줄었다(검토 지적).
    """
    api = {f"T{i:03d}": "X" for i in range(600)}
    csv_rows = [_meta(f"T{i:03d}", "X") for i in range(575)]
    # ticker 번호가 클수록 먼저 적재 — ticker 순과 첫 적재일 순을 일부러 어긋나게.
    # T575 → 08-25 … T598 → 08-02, T599 는 첫 적재일 모름(맨 뒤).
    no_d20 = {f"T{i:03d}": f"2026-08-{(600 - i):02d}" for i in range(575, 599)}
    no_d20["T599"] = None
    d = _gate(api, csv_rows, no_d20).to_dict()
    assert d["api_only_pending_count"] == 25
    assert len(d["api_only_pending"]) == 25
    tickers = [p["ticker"] for p in d["api_only_pending"]]
    assert tickers[0] == "T598" and tickers[-2] == "T575" and tickers[-1] == "T599"
    firsts = [p["first_loaded"] for p in d["api_only_pending"]]
    assert firsts[:-1] == sorted(firsts[:-1]) and firsts[-1] is None
    back = meta_gate.ConsistencyResult.from_dict(d).to_dict()
    assert back["api_only_pending_count"] == 25
    assert back["api_only_pending"] == d["api_only_pending"]


# ═══ 계약 43 · 51~52 — snapshot 검증과 저장 ═══════════════════════════════


def test_snapshot_rejects_bad_rows():
    for rows, frag in [
        ([], "empty_response"),
        ([_api_row("A", close="")], "missing_close"),
        ([_api_row("A", close="0")], "non_positive_close"),
        ([_api_row("A"), _api_row("A")], "duplicate_ticker"),
        ([_api_row("A", date="20260903")], "date_mismatch"),
    ]:
        with pytest.raises(krx_store.KrxSnapshotError) as e:
            krx_store.validate_snapshot(rows, expected_date="20260904")
        assert frag in str(e.value)


def test_snapshot_upsert_is_idempotent(tmp_path):
    db = tmp_path / "m.sqlite"
    rows = krx_store.validate_snapshot(
        [_api_row("A"), _api_row("B")], expected_date="20260904"
    )
    krx_store.upsert_snapshot(rows, db_path=db)
    krx_store.upsert_snapshot(rows, db_path=db)
    assert krx_store.stored_trading_days(db_path=db) == ["2026-09-04"]
    assert krx_store.closes_on(["2026-09-04"], db_path=db)["2026-09-04"] == {
        "A": 10000.0,
        "B": 10000.0,
    }


def test_window_requires_21_trading_days(tmp_path):
    db = tmp_path / "m.sqlite"
    for i in range(1, 21):  # 20일만
        rows = krx_store.validate_snapshot(
            [_api_row("A", date=f"202609{i:02d}")], expected_date=f"202609{i:02d}"
        )
        krx_store.upsert_snapshot(rows, db_path=db)
    assert krx_store.resolve_window(db_path=db) is None, "21일 미만인데 창을 만들었다"
    rows = krx_store.validate_snapshot(
        [_api_row("A", date="20260921")], expected_date="20260921"
    )
    krx_store.upsert_snapshot(rows, db_path=db)
    w = krx_store.resolve_window(db_path=db)
    assert w is not None and w.latest == "2026-09-21"


def test_first_loaded_dates_is_min_stored_date(tmp_path):
    """POC3-02D-OPS-01 C1 — pending 의 첫 적재일은 이 계열의 `MIN(date)` 다."""
    db = tmp_path / "m.sqlite"
    for bas, codes in (
        ("20260910", ["A"]),
        ("20260911", ["A", "B"]),
        ("20260914", ["A", "B"]),
    ):
        krx_store.upsert_snapshot(
            krx_store.validate_snapshot(
                [_api_row(c, date=bas) for c in codes], expected_date=bas
            ),
            db_path=db,
        )
    assert krx_store.first_loaded_dates(["A", "B", "ZZZ"], db_path=db) == {
        "A": "2026-09-10",
        "B": "2026-09-11",
    }
    assert krx_store.first_loaded_dates([], db_path=db) == {}

    # 창이 없을 때는 응답 전 종목(약 1,200)을 묻는다 — SQLite 변수 상한과 무관해야 한다.
    many = [f"{100000 + i}" for i in range(1200)]
    krx_store.upsert_snapshot(
        krx_store.validate_snapshot(
            [_api_row(c, date="20260915") for c in many], expected_date="20260915"
        ),
        db_path=db,
    )
    got = krx_store.first_loaded_dates(many + ["A"], db_path=db)
    assert len(got) == 1201 and got["A"] == "2026-09-10"
    assert set(got[c] for c in many) == {"2026-09-15"}


def _references_adjusted_table(src: str) -> bool:
    """기존 조정 계열 테이블을 **단어 경계로** 참조하는가.

    신규 테이블명이 `krx_etf_daily_price_unadjusted` 라 단순 부분 문자열로 보면
    자기 자신이 걸린다.
    """
    return bool(re.search(r"(?<![\w_])etf_daily_price(?![\w_])", src))


def test_krx_store_does_not_touch_etf_daily_price():
    """신규 계열이 기존 조정 계열을 읽지도 쓰지도 않는다 (§M-1)."""
    src = _code_only(krx_store)
    assert not _references_adjusted_table(src)
    assert " JOIN " not in src.upper()
    assert krx_store.TABLE == "krx_etf_daily_price_unadjusted"


def test_evidence_does_not_read_etf_daily_price():
    for mod in (ev, flow, render):
        assert not _references_adjusted_table(_code_only(mod))


# ═══ 계약 25~26 · 55~56 — 거래일 Gate ═════════════════════════════════════


def test_trading_day_passes(tmp_path):
    d = _write_calendar(tmp_path, TRADING_DAYS_2026)
    v = cal.check_trading_day("2026-09-10", directory=d)
    assert v.ok and v.reason is None


def test_non_trading_day_blocked(tmp_path):
    d = _write_calendar(tmp_path, TRADING_DAYS_2026)
    v = cal.check_trading_day("2026-09-05", directory=d)
    assert not v.ok and v.reason == cal.REASON_NON_TRADING_DAY


# ── 캘린더 부재 = 평일 fallback (2026-09-13 사용자 운영정책) ─────────────────
# 이전 계약("캘린더 없으면 fail-closed")은 **폐기**됐다. 장이 닫힌 날 연 2~3회
# 푸시가 오는 것은 1인 운영에서 사용자가 수용한 오차다. 대신 주말 발송·snapshot
# 반대 판정·예외 중단은 여전히 결함이므로 아래에서 고정한다.


def test_missing_calendar_falls_back_to_weekday(tmp_path):
    v = cal.check_trading_day("2026-09-10", directory=tmp_path / "none")  # 목
    assert v.ok and v.reason is None
    assert v.decided_by == cal.SOURCE_WEEKDAY_FALLBACK


def test_missing_calendar_still_blocks_weekend(tmp_path):
    """주말 발송은 계속 결함이다."""
    for d, label in (("2026-09-12", "토"), ("2026-09-13", "일")):
        v = cal.check_trading_day(d, directory=tmp_path / "none")
        assert not v.ok, label
        assert v.reason == cal.REASON_NON_TRADING_DAY
        assert v.decided_by == cal.SOURCE_WEEKDAY_FALLBACK


def test_year_not_covered_falls_back_to_weekday(tmp_path):
    """2027 CSV 가 없어도 평일이면 막지 않는다."""
    d = _write_calendar(tmp_path, TRADING_DAYS_2026)
    ok = cal.check_trading_day("2027-03-02", directory=d)  # 화
    assert ok.ok and ok.decided_by == cal.SOURCE_WEEKDAY_FALLBACK
    weekend = cal.check_trading_day("2027-03-06", directory=d)  # 토
    assert not weekend.ok and weekend.reason == cal.REASON_NON_TRADING_DAY


def test_corrupt_calendar_falls_back_without_raising(tmp_path):
    """캘린더 판단 중 예외로 러너가 멈추면 안 된다."""
    (tmp_path / "krx_trading_days_2026.csv").write_text("nope\n1\n", encoding="utf-8")
    v = cal.check_trading_day("2026-09-10", directory=tmp_path)
    assert v.ok and v.decided_by == cal.SOURCE_WEEKDAY_FALLBACK


def test_snapshot_wins_over_weekday_fallback(tmp_path):
    """snapshot 이 있으면 그것을 쓴다 — 평일이라고 덮어쓰지 않는다."""
    d = _write_calendar(tmp_path, TRADING_DAYS_2026)
    v = cal.check_trading_day("2026-09-14", directory=d)  # 평일이지만 목록에 없음
    assert not v.ok
    assert v.reason == cal.REASON_NON_TRADING_DAY
    assert v.decided_by == cal.SOURCE_SNAPSHOT


def test_calendar_module_has_no_holiday_library_or_external_call():
    """공휴일 라이브러리·외부 호출은 계속 금지다.

    평일 판정(`weekday()`)은 2026-09-13 정책으로 **허용**된다 — 주말 휴장은
    규칙이 아니라 정의이고, 캘린더 부재 시 평일 fallback 이 확정 계약이다.
    """
    src = _code_only(cal)
    for banned in ("holidays", "requests", "httpx", "urllib"):
        assert banned not in src


# ═══ 계약 16~19 · 27~28 — fingerprint 와 content_unchanged (억제 폐지) ═════


def _assemble(tmp_path, *, sp500=1.0, fresh=True, consistency=None, days=None, **kw):
    state = tmp_path / "state.json"
    cpath = tmp_path / "consistency.json"
    if consistency is not None:
        meta_gate.save_consistency(consistency, cpath)
    csvp = tmp_path / "official.csv"
    csvp.write_bytes(
        ("단축코드,기초지수명,지수산출기관,기초자산분류,추적배수,복제방법\n").encode(
            "cp949"
        )
    )
    caldir = _write_calendar(tmp_path, days or TRADING_DAYS_2026)
    return (
        flow.assemble_market_briefing(
            today_kst=kw.pop("today", "2026-09-10"),
            runtime_kst="2026-09-10T08:00:00+09:00",
            state_path=state,
            consistency_path=cpath,
            official_csv_path=csvp,
            sp500_return_pct=sp500,
            sp500_asof="2026-09-09",
            sp500_fresh=fresh,
            calendar_dir=caldir,
            db_path=tmp_path / "m.sqlite",
            **kw,
        ),
        state,
    )


def test_fingerprint_excludes_numbers(tmp_path):
    out, _ = _assemble(tmp_path, sp500=1.0)
    assert out.fingerprint == "UP#NONE"
    for n in ("1.0", "+1.0", "2026-09-09"):
        assert n not in out.fingerprint


def test_same_state_still_sends_and_records_unchanged(tmp_path):
    out, state = _assemble(tmp_path, sp500=1.0)
    flow.save_state(
        state, fingerprint=out.fingerprint, sent_date_kst="2026-09-09", runtime_kst=None
    )
    again, _ = _assemble(tmp_path, sp500=9.9)  # 숫자만 다름
    assert again.fingerprint == out.fingerprint
    # POC3-02B-OPS-03 (2026-09-16): 정기 PUSH 는 내용이 같아도 **막지 않는다.**
    # fingerprint 는 그대로 계산해 진단에 남긴다.
    assert again.skip_reason is None, "내용이 같다고 정기 브리핑을 막았다"
    assert again.diagnostics["content_unchanged"] is True
    assert again.message_text


def test_changed_state_sends(tmp_path):
    out, state = _assemble(tmp_path, sp500=1.0)
    flow.save_state(
        state, fingerprint=out.fingerprint, sent_date_kst="2026-09-09", runtime_kst=None
    )
    down, _ = _assemble(tmp_path, sp500=-1.0)
    assert down.fingerprint == "DOWN#NONE"
    assert down.skip_reason is None and down.should_send


def test_empty_content_is_not_no_change(tmp_path):
    """`NONE#NONE` 이 같다는 이유로 `no_publishable_content` 를 덮으면 안 된다."""
    out, state = _assemble(tmp_path, sp500=None, fresh=False)
    assert out.skip_reason in (flow.REASON_NO_PUBLISHABLE, flow.REASON_ALL_STALE)
    assert out.skip_reason != flow.REASON_NO_CHANGE
    assert out.fingerprint == "", "본문이 없는데 fingerprint 를 만들었다"


def test_non_trading_day_skips_before_fingerprint(tmp_path):
    out, _ = _assemble(tmp_path, today="2026-09-05")
    assert out.skip_reason == cal.REASON_NON_TRADING_DAY
    assert out.fingerprint == ""
    assert out.message_text == ""


def test_state_roundtrip(tmp_path):
    p = tmp_path / "s.json"
    flow.save_state(
        p, fingerprint="UP#A|B", sent_date_kst="2026-09-10", runtime_kst=None
    )
    d = flow.load_state(p)
    assert d["state_fingerprint"] == "UP#A|B"
    assert d["schema_version"] == flow.SCHEMA_VERSION


def test_state_schema_mismatch_is_ignored(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(
        json.dumps({"schema_version": "old", "state_fingerprint": "X"}),
        encoding="utf-8",
    )
    assert flow.load_state(p) is None


# ═══ 계약 41~42 — 08:00 외부 조회 0건 ═════════════════════════════════════


def test_flow_makes_no_external_call():
    src = _code_only(flow) + _code_only(meta_gate)
    for banned in ("httpx.get", "requests.get", "fdr.DataReader", "urlopen"):
        assert banned not in src


def test_flow_consumes_0720_result_only(tmp_path):
    """07:20 결과가 없으면 기초지수 블록은 fail-closed 다."""
    out, _ = _assemble(tmp_path, sp500=1.0, consistency=None)
    assert out.diagnostics["index_status"] == meta_gate.STATUS_API_FETCH_FAILED
    assert out.should_send, "전망이 유효하면 전망만이라도 발송한다"


def test_consistency_failure_blocks_index_even_with_prices(tmp_path):
    # 오늘 창의 판정이어야 저장된 status 를 쓴다(설계자 R2 Q27) — 07:20 이 적재한
    # 기준일 1일과 그 판정을 함께 둔다.
    krx_store.upsert_snapshot(
        krx_store.validate_snapshot(
            [_api_row("069500", "20260909")], expected_date="20260909"
        ),
        db_path=tmp_path / "m.sqlite",
    )
    bad = meta_gate.ConsistencyResult(
        status=meta_gate.STATUS_CSV_REFRESH_REQUIRED,
        api_only=["ZZZ"],
        **_evaluated(["2026-09-09"]),
    )
    out, _ = _assemble(tmp_path, sp500=1.0, consistency=bad)
    assert out.diagnostics["index_status"] == meta_gate.STATUS_CSV_REFRESH_REQUIRED
    assert "공식 기준정보 갱신이 필요해" in out.message_text


# ═══ 2026-09-13 사용자 지적 2건 — 기준일 최신성 · 추종 ETF 표시 ═══════════════


def _meta_named(code, index_name, short, **kw):
    r = _meta(code, index_name, **kw)
    r["한글종목약명"] = short
    return r


def test_index_line_shows_tracking_etf_short_names():
    """`추종 ETF 2개` 만으로는 무엇인지 알 수 없다 — 공식 약명을 보여준다."""
    rows = [
        _meta_named("069500", "코스피200", "KODEX 200"),
        _meta_named("102110", "코스피200", "TIGER 200"),
    ]
    r = _leader(rows, _closes(["069500", "102110"], latest=11000.0))
    assert r.candidates, r.diagnostics
    c = r.candidates[0]
    assert c.products == ("KODEX 200", "TIGER 200"), c.products
    line = "\n".join(render.render_index_block(r.candidates))
    assert "KODEX 200" in line and "TIGER 200" in line
    # 추천으로 읽히는 말을 붙이지 않는다.
    for banned in ("추천", "유망", "매수", "매도", "교체"):
        assert banned not in line


def test_index_line_caps_products_and_counts_rest():
    """수십 개인 지수는 상위 N개 + `외 N개`. 개수를 숨기지 않는다."""
    codes = [f"00000{i}" for i in range(7)]
    rows = [_meta_named(c, "코스피200", f"ETF{c}") for c in codes]
    r = _leader(rows, _closes(codes, latest=11000.0))
    c = r.candidates[0]
    assert c.ticker_count == 7
    text = render.render_products(c)
    assert text.count(",") == render.MAX_SHOWN_PRODUCTS - 1, text
    assert f"외 {7 - render.MAX_SHOWN_PRODUCTS}개" in text


def test_products_only_count_tickers_used_in_returns():
    """가격이 빠져 수익률에서 제외된 ticker 를 이름으로 되살리지 않는다."""
    rows = [
        _meta_named("A", "X", "ETF-A"),
        _meta_named("B", "X", "ETF-B"),
        _meta_named("C", "X", "ETF-C"),
    ]
    closes = _closes(["A", "B", "C"], latest=11000.0)
    del closes["L"]["C"]  # C 는 최신 가격 결측
    r = _leader(rows, closes)
    c = r.candidates[0]
    assert c.ticker_count == 2
    assert "ETF-C" not in c.products, c.products


def test_short_name_missing_falls_back_to_count_only():
    """약명을 못 찾으면 개수만 남긴다 — 없는 이름을 만들지 않는다."""
    rows = [_meta("A", "X"), _meta("B", "X")]  # 한글종목약명 없음
    r = _leader(rows, _closes(["A", "B"], latest=11000.0))
    c = r.candidates[0]
    assert c.products == ()
    assert render.render_products(c) == "추종 ETF 2개"


def _evaluated(stored_days):
    """07:20 이 `stored_days` 를 적재한 직후 남기는 판정 창(설계자 R2 Q27)."""
    days = sorted(stored_days)
    return {
        "evaluated_api_basis_date": days[-1].replace("-", "") if days else None,
        "evaluated_window_d20_date": (
            days[-1 - krx_store.LOOKBACK_20D]
            if len(days) >= krx_store.REQUIRED_TRADING_DAYS
            else None
        ),
        "evaluated_at_kst": "2026-09-18T07:20:00+09:00",
    }


def _fresh_assemble(tmp_path, *, stored_days, today="2026-09-18", axis=None):
    """`stored_days` 만 적재한 상태로 조립한다."""
    db = tmp_path / "m.sqlite"
    for d in stored_days:
        bas = d.replace("-", "")
        rows = [
            {"ISU_CD": t, "BAS_DD": bas, "TDD_CLSPRC": "11000"}
            for t in ("069500", "102110")
        ]
        krx_store.upsert_snapshot(
            krx_store.validate_snapshot(rows, expected_date=bas), db_path=db
        )
    cpath = tmp_path / "consistency.json"
    meta_gate.save_consistency(
        meta_gate.ConsistencyResult(
            status=meta_gate.STATUS_OK,
            api_ticker_count=2,
            csv_ticker_count=2,
            exact_match_count=2,
            join_coverage=1.0,
            **_evaluated(stored_days),
        ),
        cpath,
    )
    csvp = tmp_path / "official.csv"
    csvp.write_bytes(
        (
            "단축코드,기초지수명,지수산출기관,기초자산분류,추적배수,복제방법,"
            "한글종목약명\n"
            "069500,코스피200,KRX,주식,일반,실물(패시브),KODEX 200\n"
            "102110,코스피200,KRX,주식,일반,실물(패시브),TIGER 200\n"
        ).encode("cp949")
    )
    axis = axis or (
        [f"2026-08-{d:02d}" for d in range(3, 32)]
        + [
            f"2026-09-{d:02d}"
            for d in (1, 2, 3, 4, 7, 8, 9, 10, 11, 14, 15, 16, 17, 18)
        ]
    )
    (tmp_path / "krx_trading_days_2026.csv").write_text(
        "date\n" + "\n".join(axis) + "\n", encoding="utf-8"
    )
    return flow.assemble_market_briefing(
        today_kst=today,
        runtime_kst=None,
        state_path=tmp_path / "s.json",
        consistency_path=cpath,
        official_csv_path=csvp,
        sp500_return_pct=1.2,
        sp500_asof="2026-09-17",
        sp500_fresh=True,
        calendar_dir=tmp_path,
        db_path=db,
    )


def test_stale_window_is_not_used_even_with_21_days(tmp_path):
    """21일이 모인 것과 **그 21일이 최근인 것**은 다르다 (사용자 지적)."""
    old = [f"2026-08-{d:02d}" for d in range(3, 31)][:21]
    out = _fresh_assemble(tmp_path, stored_days=old)
    assert out.diagnostics["index_status"] == "stale"
    d = out.diagnostics["index_diagnostics"]
    assert d["reason"] == "window_not_fresh"
    assert d["lag_trading_days"] > d["max_stale_trading_days"]


def test_stale_window_does_not_print_kr_basis_date(tmp_path):
    """쓰지 않은 국내 기준일을 `기준` 줄에 적지 않는다 (설계 §3.4)."""
    old = [f"2026-08-{d:02d}" for d in range(3, 31)][:21]
    out = _fresh_assemble(tmp_path, stored_days=old)
    body = out.message_text or ""
    assert "국내" not in body, body
    assert "2026-08" not in body, body


def test_fresh_window_passes_and_prints_prior_trading_day(tmp_path):
    """직전 거래일까지 적재돼 있으면 통과하고 그 날짜를 적는다."""
    axis = [f"2026-08-{d:02d}" for d in range(3, 32)] + [
        f"2026-09-{d:02d}" for d in (1, 2, 3, 4, 7, 8, 9, 10, 11, 14, 15, 16, 17)
    ]
    out = _fresh_assemble(tmp_path, stored_days=axis)
    assert out.diagnostics["index_status"] != "stale", out.diagnostics
    assert "국내 2026-09-17 종가" in (out.message_text or "")


def test_window_freshness_unknown_is_fail_closed(tmp_path):
    """지연을 **못 재면** 쓰지 않는다 — 모르면 `stale` (fail-closed).

    적재된 최신일이 거래일 축에 없으면 지연을 계산할 수 없다. 그때 "아마 최근일
    것" 으로 넘기면 최신성 Gate 가 무력화된다.
    """
    axis = [f"2026-08-{d:02d}" for d in range(3, 32)] + [
        f"2026-09-{d:02d}" for d in (1, 2, 3, 4, 7, 8, 9, 10, 11, 14, 15, 16, 17, 18)
    ]
    stored = [d for d in axis if d <= "2026-09-11"][-20:] + ["2026-09-12"]
    out = _fresh_assemble(tmp_path, stored_days=stored, axis=axis)
    assert out.diagnostics["index_status"] == "stale", out.diagnostics
    assert out.diagnostics["index_diagnostics"]["reason"] == "lag_unknown"
    assert "국내" not in (out.message_text or "")


# ── 손상 캘린더·잘못된 실행일 (검증자 r1 REJECTED · 2026-09-13) ───────────────
# 기존 계약 테스트는 **헤더 손상만** 검사해 아래 두 경로를 놓쳤다. focused 60건과
# 전체 회귀가 통과하는데도 운영 계약이 깨져 있었다.


@pytest.mark.parametrize(
    "body,decided_by",
    [
        # 정상 행이 섞여 있으면 그것만 쓴다 — snapshot 판정.
        ("date\nnot-a-date\n2026-09-18\n", cal.SOURCE_SNAPSHOT),
        ("date\n\n2026-09-18\n", cal.SOURCE_SNAPSHOT),
        # 유효한 행이 하나도 없으면 snapshot 이 없는 것과 같다 — 평일 fallback.
        ("date\nxx\nyy\n", cal.SOURCE_WEEKDAY_FALLBACK),
        ("date\n20260918\n", cal.SOURCE_WEEKDAY_FALLBACK),
        ("nope\n1\n", cal.SOURCE_WEEKDAY_FALLBACK),
        ("date\n", cal.SOURCE_WEEKDAY_FALLBACK),
    ],
)
def test_corrupt_calendar_never_raises(tmp_path, body, decided_by):
    """어떤 손상이든 예외로 러너를 멈추지 않고, **정상 평일을 막지도 않는다.**

    검증자 r2 지적 — "예외 없음" 만 보면 손상 snapshot 이 그 해 평일을 전부
    `non_trading_day` 로 막는 **비충돌 오판**을 놓친다. 판정값까지 본다.
    """
    (tmp_path / "krx_trading_days_2026.csv").write_text(body, encoding="utf-8")
    v = cal.check_trading_day("2026-09-18", directory=tmp_path)  # 금요일
    assert isinstance(v, cal.CalendarVerdict)
    # 어떤 손상이든 **정상 평일을 막지 않는다.**
    assert v.ok is True, (body, v)
    assert v.reason is None
    assert v.decided_by == decided_by, (body, v)


def test_corrupt_date_rows_do_not_break_year_coverage(tmp_path):
    """형식이 깨진 행은 연도 집계에서 **빼고 센다** — 터뜨리지 않는다."""
    (tmp_path / "krx_trading_days_2026.csv").write_text(
        "date\nnot-a-date\n2026-09-18\n", encoding="utf-8"
    )
    loaded = cal.load_calendar(tmp_path)
    assert loaded is not None
    assert loaded.covered_years == (2026,)


@pytest.mark.parametrize(
    "bad", ["not-a-date", "", "2026-13-45", "20260918", "2026-9-18", "오늘"]
)
def test_unreadable_run_date_is_not_a_trading_day(tmp_path, bad):
    """읽을 수 없는 실행일을 "평일" 로 통과시키지 않는다.

    평일인지 주말인지 모르는데 넘기면 **주말 발송을 막는 계약이 무력화**된다.
    모르면 보내지 않는다 — 예외는 올리지 않는다.
    """
    v = cal.check_trading_day(bad, directory=tmp_path / "none")
    assert not v.ok, (bad, v)
    assert v.reason == cal.REASON_INVALID_DATE


def test_unreadable_run_date_blocked_even_with_snapshot(tmp_path):
    """snapshot 이 있어도 마찬가지다."""
    d = _write_calendar(tmp_path, TRADING_DAYS_2026)
    v = cal.check_trading_day("not-a-date", directory=d)
    assert not v.ok and v.reason == cal.REASON_INVALID_DATE


def test_date_format_is_consistent_between_snapshot_and_fallback(tmp_path):
    """같은 날짜가 형식에 따라 다르게 판정되면 안 된다.

    `fromisoformat` 은 3.11+ 에서 `YYYYMMDD` 도 받지만 snapshot 경로는 문자열
    비교를 한다. 형식을 고정해 두 경로를 일치시킨다.
    """
    d = _write_calendar(tmp_path, TRADING_DAYS_2026)
    iso = cal.check_trading_day("2026-09-10", directory=d)
    basic = cal.check_trading_day("20260910", directory=d)
    assert iso.ok is True
    assert basic.ok is False and basic.reason == cal.REASON_INVALID_DATE


def test_runner_does_not_send_on_unreadable_date(tmp_path):
    """조립까지 태워도 미발송이어야 한다."""
    out = _fresh_assemble(tmp_path, stored_days=[], today="not-a-date")
    assert out.skip_reason == cal.REASON_INVALID_DATE
    assert not out.message_text


@pytest.mark.parametrize("row", ["20260918", "2026-13-45", "2026-9-18", "not-a-date"])
def test_corrupt_row_does_not_claim_year_coverage(tmp_path, row):
    """손상 행이 그 연도를 덮는 것으로 오인되면 안 된다 (검증자 r2).

    앞 4자리만 검사하던 때는 `20260918` 한 줄이 2026년을 덮는 것으로 쳐서
    **정상 평일이 전부 휴장**이 됐다.
    """
    (tmp_path / "krx_trading_days_2026.csv").write_text(
        f"date\n{row}\n", encoding="utf-8"
    )
    assert cal.load_calendar(tmp_path) is None, row
    v = cal.check_trading_day("2026-09-18", directory=tmp_path)
    assert v.ok and v.decided_by == cal.SOURCE_WEEKDAY_FALLBACK


def test_corrupt_rows_dropped_but_valid_rows_kept(tmp_path):
    """정상 행이 섞여 있으면 그것만 쓰고, 버린 수를 진단에 남긴다."""
    (tmp_path / "krx_trading_days_2026.csv").write_text(
        "date\n20260918\nnot-a-date\n2026-09-21\n", encoding="utf-8"
    )
    loaded = cal.load_calendar(tmp_path)
    assert loaded is not None
    assert loaded.days == frozenset({"2026-09-21"})
    assert loaded.dropped_rows == 2
    assert loaded.covered_years == (2026,)
    # 목록에 없는 평일은 snapshot 기준으로 휴장이다.
    v = cal.check_trading_day("2026-09-18", directory=tmp_path)
    assert not v.ok and v.decided_by == cal.SOURCE_SNAPSHOT


@pytest.mark.parametrize(
    "bad", ["2026-09-18junk", "2026-09-18T09:00:00", "2026-09-18  ", " 2026-09-18"]
)
def test_date_is_not_truncated_to_ten_chars(tmp_path, bad):
    """`[:10]` 자르기로 형식 검사를 우회하면 안 된다 (검증자 r2).

    자르면 snapshot 경로(문자열 비교)와 fallback 경로의 판정이 갈린다.
    """
    fallback = cal.check_trading_day(bad, directory=tmp_path / "none")
    snapshot = cal.check_trading_day(
        bad, directory=_write_calendar(tmp_path, TRADING_DAYS_2026)
    )
    assert not fallback.ok and fallback.reason == cal.REASON_INVALID_DATE
    assert fallback.ok == snapshot.ok, (bad, fallback, snapshot)


# ── POC3-02B-OPS-03 — 정기 PUSH 억제 해제 ───────────────────────────────────


def test_consecutive_same_state_days_all_send(tmp_path):
    """5거래일 연속 같은 전망이어도 매일 보낸다.

    실측 근거(2026-09-07~09-11): 미국 방향이 5거래일 연속 DOWN 이었다. 이전
    계약이었다면 그 주에 브리핑이 **월요일 한 번만** 갔다.
    """
    for i, day in enumerate(("2026-09-07", "2026-09-08", "2026-09-09")):
        out, state = _assemble(tmp_path, sp500=-1.0, today=day)
        assert out.skip_reason is None, (day, out.skip_reason)
        assert out.message_text
        assert out.fingerprint == "DOWN#NONE"
        if i:
            assert out.diagnostics["content_unchanged"] is True
        flow.save_state(
            state, fingerprint=out.fingerprint, sent_date_kst=day, runtime_kst=None
        )


def test_no_change_reason_is_no_longer_produced(tmp_path):
    """`no_change` 로 미발송되는 경로가 남아 있으면 안 된다."""
    out, state = _assemble(tmp_path, sp500=1.0)
    flow.save_state(
        state, fingerprint=out.fingerprint, sent_date_kst="2026-09-09", runtime_kst=None
    )
    again, _ = _assemble(tmp_path, sp500=1.0)
    assert again.skip_reason != flow.REASON_NO_CHANGE


# ═══ POC3-02D-OPS-01 C1 — 공용 CSV resolver (설계자 C1 필수 보완 · R2 Q25) ═════
# 07:20 · 08:00 이 같은 함수로 `krx_etf_basic_YYYYMMDD.csv` 중 파일명 날짜가 가장
# 늦고 검사를 통과한 파일을 고른다. 합성 파일만 쓴다 — 저장소 `state/market_meta`
# 를 읽지 않는다.


def _krx_rows(*codes, index_name="코스피200"):
    rows = []
    for c in codes:
        r = dict.fromkeys(oc.EXPECTED_HEADER, "-")
        r.update({"단축코드": c, "기초지수명": index_name, "한글종목약명": f"ETF {c}"})
        rows.append(r)
    return rows


def _krx_csv(path, rows, *, header=oc.EXPECTED_HEADER, encoding="cp949"):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    for r in rows:
        w.writerow([r.get(h, "") for h in header])
    path.write_bytes(buf.getvalue().encode(encoding))
    return path


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class _Log:
    def __init__(self):
        self.warnings = []

    def warning(self, msg, *args):
        self.warnings.append(msg % args)


def test_resolver_header_is_the_approved_17_columns():
    assert len(oc.EXPECTED_HEADER) == 17 == len(set(oc.EXPECTED_HEADER))
    used = {"단축코드", "기초지수명", "지수산출기관", "기초자산분류", "추적배수"}
    assert used | {"복제방법", "한글종목약명"} <= set(oc.EXPECTED_HEADER)


def test_resolver_picks_latest_valid_file_deterministically(tmp_path):
    _krx_csv(tmp_path / "krx_etf_basic_20260909.csv", _krx_rows("A", "B"))
    new = _krx_csv(tmp_path / "krx_etf_basic_20260927.csv", _krx_rows("A", "B", "C"))
    (tmp_path / "krx_trading_days_2026.csv").write_text("date\n", encoding="utf-8")
    sel = oc.resolve_official_csv(tmp_path)
    assert sel.ok and sel.name == new.name and sel.path == new
    assert sel.sha256 == _sha(new)
    assert sel.csv_asof == "2026-09-27" and sel.rows == 3
    assert [r["단축코드"] for r in sel.records] == ["A", "B", "C"]
    assert sel.rejected == [] and sel.error is None
    assert oc.resolve_official_csv(tmp_path).to_dict() == sel.to_dict()


@pytest.mark.parametrize(
    "make,reason",
    [
        # Excel 등으로 UTF-8 재저장 → cp949 로 읽히지 않는다.
        (lambda p: _krx_csv(p, _krx_rows("A"), encoding="utf-8"), oc.REASON_DECODE),
        (
            lambda p: _krx_csv(p, _krx_rows("A"), header=oc.EXPECTED_HEADER[:-1]),
            oc.REASON_COLUMNS,
        ),
        (lambda p: _krx_csv(p, _krx_rows("A", "A")), oc.REASON_DUPLICATE_TICKER),
        (
            lambda p: _krx_csv(p, _krx_rows("A") + _krx_rows("B", index_name=" ")),
            oc.REASON_EMPTY_INDEX_NAME,
        ),
    ],
)
def test_resolver_falls_back_to_previous_valid_when_latest_fails(
    tmp_path, make, reason
):
    """R2 Q25 (a) — 최신 파일이 검사에 걸리면 직전의 최신 유효 파일을 쓴다."""
    good = _krx_csv(tmp_path / "krx_etf_basic_20260909.csv", _krx_rows("A"))
    bad = tmp_path / "krx_etf_basic_20260927.csv"
    make(bad)
    log = _Log()
    sel = oc.resolve_official_csv(tmp_path, logger=log)
    assert sel.ok and sel.name == good.name, "직전 유효 파일로 내려가지 않았다"
    assert [(r.name, r.sha256, r.reason) for r in sel.rejected] == [
        (bad.name, _sha(bad), reason)
    ]
    assert len(log.warnings) == 1
    assert bad.name in log.warnings[0] and reason in log.warnings[0]
    assert sel.to_dict()["rejected"][0]["sha256"] == _sha(bad)


def test_resolver_rejects_data_row_with_wrong_field_count(tmp_path):
    """헤더는 17컬럼 그대로인데 데이터 한 행만 16필드 → `columns` 로 거부."""
    good = _krx_csv(tmp_path / "krx_etf_basic_20260909.csv", _krx_rows("A"))
    bad = _krx_csv(tmp_path / "krx_etf_basic_20260927.csv", _krx_rows("A", "B"))
    lines = bad.read_bytes().decode("cp949").split("\n")
    lines[2] = lines[2].rsplit(",", 1)[0]  # 3번째 줄(B) 마지막 필드 제거
    bad.write_bytes("\n".join(lines).encode("cp949"))
    assert lines[0].split(",") == list(oc.EXPECTED_HEADER)
    assert [len(x.split(",")) for x in lines[1:3]] == [17, 16]

    chk = oc.check_file(bad)
    assert not chk.ok and chk.reason == oc.REASON_COLUMNS
    assert chk.detail == "line 3: 16"
    sel = oc.resolve_official_csv(tmp_path)
    assert sel.name == good.name
    assert [(r.name, r.reason) for r in sel.rejected] == [(bad.name, oc.REASON_COLUMNS)]


def test_resolver_rejects_duplicate_date_group_and_bad_names(tmp_path):
    """같은 날짜 묶음은 통째로 무효 · 날짜를 못 읽는 이름도 거부한다."""
    good = _krx_csv(tmp_path / "krx_etf_basic_20260909.csv", _krx_rows("A"))
    dup_a = _krx_csv(tmp_path / "krx_etf_basic_20260927.csv", _krx_rows("A", "B"))
    dup_b = _krx_csv(tmp_path / "krx_etf_basic_20260927 (1).csv", _krx_rows("A"))
    no_day = _krx_csv(tmp_path / "krx_etf_basic_20260231.csv", _krx_rows("A"))
    no_date = _krx_csv(tmp_path / "krx_etf_basic_latest.csv", _krx_rows("A"))
    loose = _krx_csv(tmp_path / "krx_etf_basic_20260910_v2.csv", _krx_rows("A"))
    log = _Log()
    sel = oc.resolve_official_csv(tmp_path, logger=log)
    assert sel.name == good.name
    expected = {
        dup_a.name: oc.REASON_DUPLICATE_DATE,
        dup_b.name: oc.REASON_DUPLICATE_DATE,
        no_day.name: oc.REASON_DATE_PARSE,
        no_date.name: oc.REASON_DATE_PARSE,
        loose.name: oc.REASON_NAME_PATTERN,
    }
    assert {r.name: r.reason for r in sel.rejected} == expected
    assert [r.name for r in sel.rejected] == sorted(expected)
    assert all(r.sha256 == _sha(tmp_path / r.name) for r in sel.rejected)
    assert len(log.warnings) == len(expected)


def test_resolver_without_valid_file_fails_closed(tmp_path):
    none = oc.resolve_official_csv(tmp_path / "missing_dir")
    assert not none.ok and none.error == oc.ERROR_NO_VALID_FILE
    assert none.records == [] and none.rejected == []
    bad = _krx_csv(tmp_path / "krx_etf_basic_20260927.csv", _krx_rows("A", "A"))
    sel = oc.resolve_official_csv(tmp_path)
    assert not sel.ok and sel.name is None and sel.sha256 is None
    assert sel.error == oc.ERROR_NO_VALID_FILE
    assert [(r.name, r.reason) for r in sel.rejected] == [
        (bad.name, oc.REASON_DUPLICATE_TICKER)
    ]


def test_fixed_20260909_consumers_do_not_use_resolver():
    """R2 · Q3 — 장중 설정 · 02B-1 재현 · 장중 역검증은 `20260909` 고정이다."""
    from app.intraday_config import generator

    root = Path(__file__).resolve().parents[1]
    assert generator.DEFAULT_CSV == Path("state/market_meta/krx_etf_basic_20260909.csv")
    for rel in (
        "app/intraday_config/generator.py",
        "scripts/ops02b1_gate/reproduce.py",
        "scripts/ops02c/reverse_verify_guards.py",
    ):
        src = (root / rel).read_text(encoding="utf-8")
        assert "krx_etf_basic_20260909.csv" in src, rel
        assert not re.search(r"\bofficial_csv\b", src), rel


# ── R2 Q23 — refresh_due · 주기 ──────────────────────────────────────────────


@pytest.mark.parametrize("count,remaining,due", [(15, 6, False), (16, 5, True)])
def test_refresh_due_boundary_on_earliest_pending(count, remaining, due):
    api = {f"T{i}": "X" for i in range(100)}
    csv_rows = [_meta(f"T{i}", "X") for i in range(98)]
    r = meta_gate.evaluate_consistency(
        api_index_names=api,
        csv_rows=csv_rows,
        api_basis_date="20260917",
        no_d20_first_loaded={"T98": "2026-08-25", "T99": "2026-09-15"},
        stored_day_counts={"T98": count, "T99": 3},
    )
    assert r.status == meta_gate.STATUS_OK
    assert r.api_only_pending == [
        {
            "ticker": "T98",
            "first_loaded": "2026-08-25",
            "stored_trading_day_count": count,
            "remaining_trading_days": remaining,
        },
        {
            "ticker": "T99",
            "first_loaded": "2026-09-15",
            "stored_trading_day_count": 3,
            "remaining_trading_days": 18,
        },
    ]
    meta_gate.apply_refresh_due(r, previous=None)
    assert r.refresh_due is due
    assert r.refresh_due_reason == (meta_gate.REFRESH_REASON_PENDING if due else None)
    assert r.refresh_due_cycle_id == ("20260917" if due else None)


def test_refresh_due_remaining_never_negative_and_csv_required_alone():
    api = {f"T{i}": "X" for i in range(100)}
    r = meta_gate.evaluate_consistency(
        api_index_names=api,
        csv_rows=[_meta(f"T{i}", "X") for i in range(99)],
        no_d20_first_loaded={"T99": "2026-08-01"},
        stored_day_counts={"T99": 30},
    )
    assert r.api_only_pending[0]["remaining_trading_days"] == 0
    blocked = _gate(api, [_meta(f"T{i}", "X") for i in range(99)], {})
    assert blocked.status == meta_gate.STATUS_CSV_REFRESH_REQUIRED
    assert blocked.api_only_pending == []
    meta_gate.apply_refresh_due(blocked, previous=None)
    assert blocked.refresh_due is True
    assert blocked.refresh_due_reason == meta_gate.REFRESH_REASON_CSV
    quiet = _gate(api, [_meta(f"T{i}", "X") for i in range(100)], {})
    meta_gate.apply_refresh_due(quiet, previous=None)
    assert (quiet.refresh_due, quiet.refresh_due_reason) == (False, None)
    assert quiet.refresh_due_cycle_id is None


def test_refresh_due_cycle_id_carries_resets_and_renews():
    """R2 Q24 — `false → true` 가 된 주기마다 새 id · due 가 이어지면 같은 id."""

    def _verdict(basis, due, prev):
        r = meta_gate.ConsistencyResult(
            status=(
                meta_gate.STATUS_CSV_REFRESH_REQUIRED if due else meta_gate.STATUS_OK
            ),
            api_basis_date=basis,
            evaluated_api_basis_date=basis,
        )
        meta_gate.apply_refresh_due(r, previous=prev)
        return r

    first = _verdict("20260917", True, None)
    second = _verdict("20260918", True, first)
    off = _verdict("20260921", False, second)
    again = _verdict("20260922", True, off)
    assert first.refresh_due_cycle_id == second.refresh_due_cycle_id == "20260917"
    assert (off.refresh_due, off.refresh_due_cycle_id) == (False, None)
    assert again.refresh_due_cycle_id == "20260922"
    back = meta_gate.ConsistencyResult.from_dict(second.to_dict())
    assert (back.refresh_due, back.refresh_due_cycle_id) == (True, "20260917")
    old = meta_gate.ConsistencyResult.from_dict({"status": meta_gate.STATUS_OK})
    assert (old.refresh_due, old.refresh_due_cycle_id) == (False, None)


# ── R2 Q27 — 저장된 판정이 오늘 창의 것인가 ───────────────────────────────────


def test_verdict_window_check_normalizes_dates_and_fails_closed():
    r = meta_gate.ConsistencyResult(
        status=meta_gate.STATUS_OK,
        evaluated_api_basis_date="20260917",
        evaluated_window_d20_date="2026-08-20",
        evaluated_at_kst="2026-09-18T07:20:05+09:00",
    )
    check = meta_gate.verdict_stale_reason
    assert check(r, latest="2026-09-17", d20="2026-08-20") is None
    assert check(r, latest="20260917", d20="20260820") is None
    assert check(r, latest="2026-09-18", d20="2026-08-20") == "api_basis_date_mismatch"
    assert check(r, latest="2026-09-17", d20="2026-08-21") == "window_d20_mismatch"
    assert check(r, latest="2026-09-17", d20=None) == "window_d20_mismatch"
    old = meta_gate.ConsistencyResult.from_dict(
        {k: v for k, v in r.to_dict().items() if not k.startswith("evaluated_")}
    )
    assert check(old, latest="2026-09-17", d20="2026-08-20") == (
        "evaluated_window_missing"
    )
    short = meta_gate.ConsistencyResult(
        status=meta_gate.STATUS_OK,
        evaluated_api_basis_date="20260917",
        evaluated_at_kst="2026-09-18T07:20:05+09:00",
    )
    assert check(short, latest="2026-09-17", d20=None) is None  # 21일 미만끼리
