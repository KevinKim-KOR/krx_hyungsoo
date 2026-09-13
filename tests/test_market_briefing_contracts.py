"""POC3-OPS-02B-2 — 계약 test.

설계자 §8(24종) + PLAN §K(25~37) + §M-8(38~57) 대응. 합성 fixture 와 임시 DB 만
쓴다. **외부 조회 0건 · 라이브 DB·state 미접근 · 발송 0건.**

고정하는 것은 "정상 입력에서 숫자가 맞는가" 보다 **"계약 이하 입력이 성공으로
끝나지 않는가"** 다.
"""

from __future__ import annotations

import ast
import inspect
import json
import re

import pytest

from app.market_briefing import calendar as cal
from app.market_briefing import evidence as ev
from app.market_briefing import flow, krx_store, meta_gate, render

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
    """API-only 1건이면 **coverage 와 무관하게** 차단."""
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


def test_missing_calendar_fails_closed(tmp_path):
    v = cal.check_trading_day("2026-09-10", directory=tmp_path / "none")
    assert not v.ok and v.reason == cal.REASON_CALENDAR_REFRESH_REQUIRED


def test_year_not_covered_fails_closed(tmp_path):
    """연도가 빠졌는데 '목록에 없으니 휴장일' 로 판정하면 한 해가 조용히 죽는다."""
    d = _write_calendar(tmp_path, TRADING_DAYS_2026)
    v = cal.check_trading_day("2027-03-02", directory=d)
    assert not v.ok and v.reason == cal.REASON_CALENDAR_REFRESH_REQUIRED


def test_corrupt_calendar_fails_closed(tmp_path):
    (tmp_path / "krx_trading_days_2026.csv").write_text("nope\n1\n", encoding="utf-8")
    v = cal.check_trading_day("2026-09-10", directory=tmp_path)
    assert not v.ok and v.reason == cal.REASON_CALENDAR_REFRESH_REQUIRED


def test_calendar_module_has_no_holiday_library_or_weekday_rule():
    src = _code_only(cal)
    for banned in ("holidays", "weekday()", "isoweekday", "requests", "httpx"):
        assert banned not in src


# ═══ 계약 16~19 · 27~28 — fingerprint 와 억제 ═════════════════════════════


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


def test_same_state_different_numbers_is_no_change(tmp_path):
    out, state = _assemble(tmp_path, sp500=1.0)
    flow.save_state(
        state, fingerprint=out.fingerprint, sent_date_kst="2026-09-09", runtime_kst=None
    )
    again, _ = _assemble(tmp_path, sp500=9.9)  # 숫자만 다름
    assert again.fingerprint == out.fingerprint
    assert again.skip_reason == flow.REASON_NO_CHANGE


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
    bad = meta_gate.ConsistencyResult(
        status=meta_gate.STATUS_CSV_REFRESH_REQUIRED, api_only=["ZZZ"]
    )
    out, _ = _assemble(tmp_path, sp500=1.0, consistency=bad)
    assert out.diagnostics["index_status"] == meta_gate.STATUS_CSV_REFRESH_REQUIRED
    assert "공식 기준정보 갱신이 필요해" in out.message_text
