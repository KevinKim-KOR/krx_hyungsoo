"""POC7-04 V2 RESULT 판정(2026-11-26) §2 — 외부 복사문은 이번 조회 조건과 같다고 확인된 기록만 인용(tmp DB 만).

같은 조건 · 다른 조건 · 조건 미확인(칸 빠짐 · 값 다름 · 기간 다름) · 인용 0건 문구 · 로컬 화면의 조건 차이와 원래 값 ·
「지난 검토와 비교」도 같은 판정 · 인용 범위는 정정 전 대상 안에서만(더 앞 기록으로 대신하지 않음 · 다시 계산 상한)."""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

import pytest

from app.weekly_decision import evidence as E
from app.weekly_decision import history as H
from app.weekly_decision import lines as L
import sqlite3

from app.weekly_decision import conditions as C
from app.weekly_decision import page as PG
from app.weekly_decision import page_saved as PS
from app.weekly_decision import records as RD
from app.weekly_decision import server as SV
from app.weekly_decision import store as ST
from tests._poc7_04_support import (
    FILTERS,
    _cite_line,
    _ctx,
    _item,
    _sessions,
    _true_item,
    _app,
    _bid,
    _decision,
    _free_port,
    _req,
    make_market,
)

NO_INVERSE = {**FILTERS, "exclude_inverse": False}
NONE_LINE = "[당시 저장 기록] 인용할 기록 없음\n"


@pytest.fixture
def market(tmp_path: Path) -> Path:
    return make_market(tmp_path)


def _text(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


def _compose(ctx: H.Context, tmp_path: Path, name: str, rows: list[dict[str, Any]]):
    (tmp_path / name).mkdir()
    return E.compose(
        ctx, "AAA001", sessions=_sessions(tmp_path / name, rows), reviews=[]
    )


def _shift_start(item: dict[str, Any]) -> dict[str, Any]:
    k1 = item["same_period_kodex200"]["one_month"]
    s = (date.fromisoformat(k1["start_date"]) - timedelta(days=1)).isoformat()
    return _item(
        item["rank"], "AAA001", item["one_month_return_pct"], s, k1["end_date"]
    )


@pytest.mark.parametrize(
    "case,cite,why",
    [
        ("same", "same", None),
        ("differs", "differs", "인버스: 그 기록 포함 · 지금 제외"),
        ("missing_key", "unknown", "확인 못 함 — 선물 제외 여부가 저장되지 않음"),
        (
            "value_differs",
            "unknown",
            "확인 못 함 — 다시 계산한 순위 · 1개월 값이 저장값과 다름",
        ),
        ("period", "unknown", "확인 못 함 — 비교 기간이 달라 값을 맞춰 보지 않음"),
    ],
)
def test_copy_cites_only_records_confirmed_same_condition(
    market: Path, tmp_path: Path, case: str, cite: str, why: Optional[str]
) -> None:
    ctx = _ctx(market)
    d = "2026-11-16"
    filters, item = FILTERS, _true_item(ctx, d)
    if case == "differs":  # 다른 제외 조건 · 그 조건으로는 값이 맞음
        filters, item = NO_INVERSE, _true_item(ctx, d, filters=NO_INVERSE)
    elif case == "missing_key":  # 조건 칸 하나가 빠짐 — 같은지 확인할 수 없음
        filters = {k: v for k, v in FILTERS.items() if k != "exclude_futures"}
    elif case == "value_differs":  # 저장 순위가 그날 다시 계산한 순위와 다름
        item = {**item, "rank": 29}
    elif case == "period":  # 저장 시작일이 하루 앞 — 기간이 달라 값을 맞춰 보지 않음
        item = _shift_start(item)
    rv = _compose(
        ctx, tmp_path, case, [{"asof": d, "filters": filters, "items": [item]}]
    )
    m = [x for r in rv["weeks"]["rows"] for x in r["records"]["mine"]][0]
    assert m["cite"] == cite
    line = _cite_line(item, d)
    weeks = _text(PG.weeks_html(rv))
    assert f"{item['rank']}위" in weeks  # 화면(로컬)은 원래 관측값을 그대로 보임
    if cite == "same":
        assert f"[당시 저장 기록] {line}\n" in rv["copy"]
        assert "AI 질문 인용인용함 — 순위 · 1개월 값 · 기간만" in weeks
        assert "지금과 같은 조건인가같음 — 제외 조건 네 가지가 지금과 같음" in weeks
        assert "AI 질문에 인용 안 함" not in weeks
        return
    assert NONE_LINE in rv["copy"] and line not in rv["copy"]
    assert why in weeks  # 실제 사유(반박 검토 D2 — 다른 사유로 덮지 않음)
    note = "다른 조회 조건" if cite == "differs" else "같은 조건인지 확인 못 함"
    assert f"{note} — AI 질문에 인용 안 함" in weeks
    if case == "differs":
        assert "그 기록의 조회 조건레버리지 · 합성 · 선물 제외" in weeks
    if case == "missing_key":  # 저장되지 않은 칸을 '포함'으로 보이지 않음(반박 검토 P3)
        assert "합성 제외<br>선물 제외 여부 저장 안 됨" in PG.weeks_html(rv)


def test_previous_uses_the_same_condition_judgment(
    market: Path, tmp_path: Path
) -> None:
    """반박 검토 D1 — 「지난 검토와 비교」의 '같은 조건'도 복사문 인용과 같은 판정(제외 조건 + 다시 계산)."""
    ctx = _ctx(market)
    d = "2026-11-16"
    good = _compose(ctx, tmp_path, "good", [{"asof": d, "items": [_true_item(ctx, d)]}])
    assert good["previous"]["kind"] == "session"
    assert good["previous"]["cite_why"]["state"] == "same"
    assert " · 같은 조건" in PG.previous_lines(good)[0][0]
    bad_item = {**_true_item(ctx, d), "rank": 29}
    bad = _compose(ctx, tmp_path, "bad", [{"asof": d, "items": [bad_item]}])
    lines = PG.previous_lines(bad)[0]
    assert bad["previous"]["cite_why"]["state"] == "unknown"
    assert " · 같은 조건" not in lines[0] and "29위" in lines[0]
    assert (
        lines[1]
        == "같은 조건인지 확인 못 함 — 다시 계산한 순위 · 1개월 값이 저장값과 다름"
    )
    assert "조건: " in lines[2]  # 지금 값도 그 조건과 함께(각 관측값)


def test_cite_scope_stays_within_previous_targets(market: Path, tmp_path: Path) -> None:
    """반박 검토 P2 — 정정 전 인용 대상(네 주 안 + 가장 최근 하나) 가운데 같은 조건만 · 더 앞 기록으로 대신하지 않음."""
    ctx = _ctx(market)

    def rec(d: str, filters: dict = FILTERS) -> dict[str, Any]:
        return {"asof": d, "filters": filters, "items": [_true_item(ctx, d, filters)]}

    def asofs(rv: dict[str, Any]) -> list[str]:
        return [c["asof"] for c in rv["cite_records"]]

    # 네 주 밖 기록 하나뿐(가장 최근) · 같은 조건 → 인용
    rv = _compose(ctx, tmp_path, "a", [rec("2026-10-16")])
    assert asofs(rv) == ["2026-10-16"]
    assert _cite_line(rec("2026-10-16")["items"][0], "2026-10-16") in rv["copy"]
    # 가장 최근(10/21)이 다른 조건 → 제외 · 그 앞 같은 조건(10/16)으로 대신하지 않음
    rv = _compose(
        ctx, tmp_path, "b", [rec("2026-10-16"), rec("2026-10-21", NO_INVERSE)]
    )
    assert (
        asofs(rv) == [] and NONE_LINE in rv["copy"] and "10/16 기준" not in rv["copy"]
    )
    # 네 주 안(11/13) + 네 주 밖(10/16) 둘 다 같은 조건 → 네 주 안만(정정 전과 같음)
    rv = _compose(ctx, tmp_path, "c", [rec("2026-10-16"), rec("2026-11-13")])
    assert asofs(rv) == ["2026-11-13"] and "10/16 기준" not in rv["copy"]
    # 네 주 밖 같은 조건 둘 → 가장 최근 하나만
    rv = _compose(ctx, tmp_path, "d", [rec("2026-10-16"), rec("2026-10-21")])
    assert asofs(rv) == ["2026-10-21"]


def test_outside_records_restore_at_most_once_more(
    market: Path, tmp_path: Path
) -> None:
    """반박 검토 P1 — 네 주 밖 기록이 많아도 다시 계산은 많아야 한 번 더(스냅숏 지문도 같은 수만큼)."""
    base = _ctx(market)
    _compose(base, tmp_path, "none", [])
    days = ["2026-09-21", "2026-09-25", "2026-09-29", "2026-10-02", "2026-10-07"]
    days += ["2026-10-14", "2026-10-21"]
    rows = [
        {"asof": d, "items": [_item(29, "AAA001", 1.0, "2026-09-01", d)]} for d in days
    ]
    ctx = _ctx(market)
    rv = _compose(ctx, tmp_path, "many", rows)
    assert rv["cite_records"] == [] and NONE_LINE in rv["copy"]
    assert len(ctx.restores) - len(base.restores) <= 1
    assert len(ctx.fingerprints()) - len(base.fingerprints()) <= 1


def test_cite_judge_rules() -> None:
    e = {"rank": 3, "one_month": 1.0, "start": "2026-10-16", "end": "2026-11-16"}
    rec = {"filters": dict(FILTERS)}
    match = {"state": "match"}
    assert H.cite_state(rec, e, FILTERS, match) == "same"
    for st in ("differs", "period_differs", "no_restore", "after_end"):
        j = H.cite_judge(rec, e, FILTERS, {"state": st})
        assert (j["state"], j["why"]) == ("unknown", st)
    assert H.cite_judge(rec, e, FILTERS, None)["why"] == "not_checked"
    j = H.cite_judge({"filters": NO_INVERSE}, e, FILTERS, match)
    assert j["state"] == "differs"
    assert j["diff"] == [{"key": "exclude_inverse", "stored": False, "now": True}]
    short = {k: v for k, v in FILTERS.items() if k != "exclude_futures"}
    j = H.cite_judge({"filters": short}, e, FILTERS, match)
    assert (j["state"], j["why"], j["missing"], j["invalid"]) == (
        "unknown",
        "filter_unknown",
        ["exclude_futures"],
        [],
    )
    # 불리언이 아닌 저장값(문자열 'false' · 객체 · null · 숫자)은 참 · 거짓으로 바꾸지 않음(검증 F18)
    for bad in ("false", "true", {}, None, 0, 1):
        f = {**FILTERS, "exclude_futures": bad}
        j = H.cite_judge({"filters": f}, e, FILTERS, match)
        assert (j["state"], j["why"], j["invalid"]) == (
            "unknown",
            "filter_unknown",
            ["exclude_futures"],
        ), bad
        assert C.filter_value(f, "exclude_futures") is C.INVALID
    # 저장된 칸이 다르면 빠진 칸이 있어도 '다름'(확인된 사실 먼저)
    j = H.cite_judge(
        {"filters": {**short, "exclude_inverse": False}}, e, FILTERS, match
    )
    assert j["state"] == "differs" and j["missing"] == ["exclude_futures"]
    j = H.cite_judge(rec, {**e, "rank": None}, FILTERS, match)
    assert (j["state"], j["why"]) == ("unknown", "no_value")


@pytest.mark.parametrize("bad", ["false", {}, None, 0])
def test_non_boolean_filter_is_not_cited(
    market: Path, tmp_path: Path, bad: Any
) -> None:
    """검증 F18 — 저장 조건 값이 불리언이 아니면 '같음'으로 바꾸지 않고, 가정해서 다시 계산하지도 않음."""
    base = _ctx(market)
    _compose(base, tmp_path, "none", [])
    ctx = _ctx(market)
    d = "2026-11-16"
    filters = {**FILTERS, "exclude_futures": bad}
    rows = [{"asof": d, "filters": filters, "items": [_true_item(ctx, d)]}]
    rv = _compose(ctx, tmp_path, "bad", rows)
    m = [x for r in rv["weeks"]["rows"] for x in r["records"]["mine"]][0]
    assert m["cite"] == "unknown" and m["check"]["state"] == "filters_unknown"
    assert (
        NONE_LINE in rv["copy"] and _cite_line(rows[0]["items"][0], d) not in rv["copy"]
    )
    weeks = _text(PG.weeks_html(rv))
    assert "확인 못 함 — 선물 제외 여부의 저장 형식이 맞지 않음" in weeks
    assert "합성 제외<br>선물 제외 여부 형식 오류" in PG.weeks_html(rv)
    assert "조회 조건 일부를 알 수 없어 다시 계산하지 않음" in weeks
    assert " · 같은 조건" not in PG.previous_lines(rv)[0][0]
    # 네 주 밖(가장 최근 하나) 경로도 같음 · 가정한 조건으로 복원하지 않음
    out = _ctx(market)
    rows2 = [
        {
            "asof": "2026-10-16",
            "filters": filters,
            "items": [
                _true_item(ctx, "2026-10-16")
            ],  # 값은 다른 문맥에서(복원 수를 세는 문맥은 건드리지 않음)
        }
    ]
    rv2 = _compose(out, tmp_path, "bad_out", rows2)
    assert rv2["cite_records"] == [] and NONE_LINE in rv2["copy"]
    assert len(out.restores) == len(base.restores)


def test_no_saved_filter_is_not_called_no_exclusion(
    market: Path, tmp_path: Path
) -> None:
    """검증 F19 — 네 칸 모두 저장되지 않은 기록에 '제외 없음'을 붙이지 않음."""
    ctx = _ctx(market)
    d = "2026-11-16"
    rv = _compose(
        ctx,
        tmp_path,
        "empty",
        [{"asof": d, "filters": {}, "items": [_true_item(ctx, d)]}],
    )
    weeks = _text(PG.weeks_html(rv))
    assert "그 기록의 조회 조건제외 조건 네 칸 저장 안 됨" in weeks
    assert "제외 없음" not in weeks and NONE_LINE in rv["copy"]


def test_review_filters_with_wrong_type_are_not_same(market: Path) -> None:
    """내 판단 기록(「지난 검토와 비교」)도 같은 칸 판정 — 문자열 'false' 를 같은 조건으로 보지 않음."""
    ctx = _ctx(market)
    one = {"value": 1.0, "start": "2026-10-20", "end": "2026-11-20"}
    rv0 = {
        "ticker": "AAA001",
        "end": "2026-11-20",
        "saved_at": "2026-11-20T23:00:00+09:00",
    }
    rv0 |= {"verdict": "hold", "reason": "", "rank": 3, "one_month": one}
    for f, same in ((FILTERS, True), ({**FILTERS, "exclude_futures": "false"}, False)):
        rv = E.compose(
            ctx,
            "AAA001",
            sessions={"state": "ok", "records": [], "broken": 0},
            reviews=[{**rv0, "filters": f}],
        )
        assert (
            rv["previous"]["kind"] == "review"
            and rv["previous"]["same_filters"] is same
        )
        lines = PG.previous_lines(rv)[0]
        assert (" · 같은 조건" in lines[1]) is same
        if not same:
            assert "선물 제외 여부 형식 오류" in lines[1]
        # 지금 값도 조건과 함께(같은 조건이 아닐 때만)
        assert ("조건: 1개월 수익률" in lines[2]) is (not same)


def test_filter_text_marks_unsaved_fields() -> None:
    assert (
        L.filter_text(FILTERS) == "1개월 수익률 · 인버스 · 레버리지 · 합성 · 선물 제외"
    )
    assert (
        L.filter_text({"exclude_inverse": True})
        == "1개월 수익률 · 인버스 제외 · 레버리지 · 합성 · 선물 제외 여부 저장 안 됨"
    )
    assert L.filter_text({k: False for k in FILTERS}) == "1개월 수익률 · 제외 없음"
    assert L.filter_text({}) == "1개월 수익률 · 제외 조건 네 칸 저장 안 됨"
    assert (
        L.filter_text({"exclude_inverse": False})
        == "1개월 수익률 · 인버스 포함 · 레버리지 · 합성 · 선물 제외 여부 저장 안 됨"
    )
    assert (
        L.filter_text({**FILTERS, "exclude_futures": "false"})
        == "1개월 수익률 · 인버스 · 레버리지 · 합성 제외 · 선물 제외 여부 형식 오류"
    )
    assert L.same_filters(FILTERS, FILTERS)
    for bad in (
        {},
        {**FILTERS, "exclude_futures": "false"},
        {**FILTERS, "exclude_futures": 1},
    ):
        assert not L.same_filters(bad, FILTERS)


# --- 반박 검토(2026-11-27) — 지금 조건에 없는 칸 · NaN · 깊은 JSON ---


def test_extra_saved_filter_is_not_same(market: Path, tmp_path: Path) -> None:
    """지금 조건에 없는 칸이 저장된 기록은 그 기록의 조건을 다 알 수 없음 — 같다고 보지 않음."""
    ctx = _ctx(market)
    d = "2026-11-16"
    f = {**FILTERS, "exclude_etn": True}
    rv = _compose(
        ctx,
        tmp_path,
        "extra",
        [{"asof": d, "filters": f, "items": [_true_item(ctx, d)]}],
    )
    m = [x for r in rv["weeks"]["rows"] for x in r["records"]["mine"]][0]
    assert (m["cite"], m["cite_why"]["extra"]) == ("unknown", ["exclude_etn"])
    assert m["check"]["state"] == "filters_unknown" and NONE_LINE in rv["copy"]
    weeks = _text(PG.weeks_html(rv))
    assert "확인 못 함 — 지금 조건에 없는 칸이 저장됨(exclude_etn)" in weeks
    assert "지금 조건에 없는 칸 저장됨(exclude_etn)" in L.filter_text(f)
    assert not L.same_filters(f, FILTERS)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nan_filter_record_does_not_block_saving(
    market: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad: float
) -> None:
    """반박 검토 D1 · D2 — 저장 조건의 NaN · 무한대가 새 저장 스냅숏에 들어가 저장이 끊기지 않음."""
    ctx = _ctx(market)
    d = "2026-11-16"
    f = {**FILTERS, "exclude_futures": bad}
    app = _app(
        market, tmp_path, [{"asof": d, "filters": f, "items": [_true_item(ctx, d)]}]
    )
    html = app.page("AAA001")
    assert NONE_LINE.strip() in _text(html)
    code, out = app.save(
        {"build_id": _bid(html), "ticker": "AAA001", "verdict": "hold"}
    )
    assert code == 200, out
    # 손으로 고친 내 판단 기록(스냅숏 조건에 NaN)도 다음 저장을 막지 않음
    path = app.root / "reviews" / f"{out['review_id']}.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["snapshot"]["filters"]["exclude_futures"] = bad
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    item = ST.list_reviews(app.root)["items"][0]
    assert item["filters"]["exclude_futures"] is C.INVALID
    html2 = app.page("AAA001")
    code2, out2 = app.save(
        {"build_id": _bid(html2), "ticker": "AAA001", "verdict": "hold"}
    )
    assert code2 == 200, out2

    # 마지막 관문 — 기록할 수 없는 수는 쓰기 전에 거절 · 응답이 옴(연결을 끊지 않음) · 파일 0건 추가
    def boom(*a: Any, **k: Any) -> None:
        raise ST.Unrecordable("기록할 수 없는 수(NaN · inf)")

    monkeypatch.setattr(ST, "save", boom)
    before = sorted((app.root / "reviews").iterdir())
    code3, out3 = app.save(
        {"build_id": _bid(app.page("AAA001")), "ticker": "AAA001", "verdict": "hold"}
    )
    assert code3 == 422 and "저장하지 않았습니다" in out3["error"]
    assert sorted((app.root / "reviews").iterdir()) == before


def test_deeply_nested_json_is_one_unreadable_record(
    market: Path, tmp_path: Path
) -> None:
    """반박 검토 D3 — 너무 깊게 중첩된 JSON 은 그 기록만 못 읽은 기록(화면 전체가 실패하지 않음)."""
    ctx = _ctx(market)
    d = "2026-11-16"
    deep = "[" * 200000 + "]" * 200000
    rows = [
        {"asof": d, "items": [_true_item(ctx, d)]},
        {"asof": d, "items": deep},
    ]
    (tmp_path / "deep").mkdir()
    sess = _sessions(tmp_path / "deep", rows)
    assert sess["state"] == "ok" and len(sess["records"]) == 1 and sess["broken"] == 1
    root = tmp_path / "root"
    (root / "reviews").mkdir(parents=True)
    (root / "reviews" / "20261126T000000Z_deadbeef.json").write_text(deep)
    got = ST.list_reviews(root)
    assert got["items"] == [] and got["broken"] == ["20261126T000000Z_deadbeef.json"]


# --- 검증 §37(2026-11-27) F20 · F21 ---

DUP = (
    '{"exclude_inverse": true, "exclude_leveraged": true, "exclude_synthetic": true, '
    '"exclude_futures": false, "exclude_futures": true}'
)


def _raw_sessions(
    tmp_path: Path, name: str, rows: list[dict[str, Any]], raw: dict
) -> dict:
    """저장 행의 JSON 칸을 글자 그대로 넣음(같은 칸 두 번 등 — json.dumps 로는 만들 수 없는 모양)."""
    (tmp_path / name).mkdir()
    db = _decision(tmp_path / name, rows)
    with sqlite3.connect(db) as con:
        for rid, (col, text) in raw.items():
            con.execute(
                f"UPDATE ai_session_records SET {col}=? WHERE id=?", (text, rid)
            )
    return H.read_sessions(db)


@pytest.mark.parametrize(
    "d", ["2026-11-16", "2026-10-16"]
)  # 지난 네 주 안 · 밖(가장 최근 하나)
def test_conflicting_duplicate_filter_is_not_cited(
    market: Path, tmp_path: Path, d: str
) -> None:
    """검증 F20 — 같은 칸이 false · true 두 번이면 마지막 값으로 덮지 않고 값 충돌 = 확인 못 함 · 인용 안 함."""
    base = _ctx(market)
    _compose(base, tmp_path, "none", [])
    ctx = _ctx(market)
    item = _true_item(
        _ctx(market), d
    )  # 값은 따로 만든 문맥에서(복원 수를 세는 두 문맥은 건드리지 않음)
    sess = _raw_sessions(
        tmp_path, "dup", [{"asof": d, "items": [item]}], {"rec0": ("filters_json", DUP)}
    )
    assert sess["records"][0]["filters"]["exclude_futures"] is C.CONFLICT
    rv = E.compose(ctx, "AAA001", sessions=sess, reviews=[])
    assert rv["cite_records"] == [] and NONE_LINE in rv["copy"]
    assert _cite_line(item, d) not in rv["copy"]
    assert len(ctx.restores) == len(base.restores)  # 가정한 조건으로 다시 계산하지 않음
    if d == "2026-11-16":
        m = [x for r in rv["weeks"]["rows"] for x in r["records"]["mine"]][0]
        assert (m["cite"], m["cite_why"]["conflict"]) == (
            "unknown",
            ["exclude_futures"],
        )
        weeks = _text(PG.weeks_html(rv))
        assert "확인 못 함 — 선물 제외 여부가 서로 다른 값으로 두 번 저장됨" in weeks
        assert "선물 제외 여부 값 충돌(두 번 저장)" in weeks


def test_duplicate_with_same_value_and_conflicting_candidate(
    market: Path, tmp_path: Path
) -> None:
    """같은 값이 두 번이면 그 값(지나치게 막지 않음) · 후보 칸(순위)이 서로 다르면 값 없음 = 인용 안 함."""
    ctx = _ctx(market)
    d = "2026-11-16"
    item = _true_item(ctx, d)
    same = DUP.replace('"exclude_futures": false', '"exclude_futures": true')
    sess = _raw_sessions(
        tmp_path,
        "same",
        [{"asof": d, "items": [item]}],
        {"rec0": ("filters_json", same)},
    )
    rv = E.compose(ctx, "AAA001", sessions=sess, reviews=[])
    assert [c["asof"] for c in rv["cite_records"]] == [d]
    k1 = item["same_period_kodex200"]["one_month"]
    cand = (
        f'[{{"rank": 29, "rank": {item["rank"]}, "ticker": "AAA001", '
        f'"one_month_return_pct": {item["one_month_return_pct"]}, '
        f'"same_period_kodex200": {{"one_month": {{"start_date": "{k1["start_date"]}", '
        f'"end_date": "{k1["end_date"]}"}}}}}}]'
    )
    sess2 = _raw_sessions(
        tmp_path,
        "cand",
        [{"asof": d, "items": [item]}],
        {"rec0": ("candidate_snapshot_json", cand)},
    )
    # 후보 칸이 서로 다르면 원래 값을 알 수 없음 — 그 기록 전체를 못 읽은 기록으로('값 없음' · '이 ETF 없음'으로 단정하지 않음)
    assert sess2["records"] == [] and sess2["broken"] == 1
    rv2 = E.compose(ctx, "AAA001", sessions=sess2, reviews=[])
    assert rv2["cite_records"] == [] and NONE_LINE in rv2["copy"]
    # 같은 ETF 가 한 기록에 두 번 — 값이 모두 같으면 하나로 읽음 · 다르면 그 행만 못 읽음(반박 검토 L2)
    two = f"[{json.dumps(item)}, {json.dumps(item)}]"
    sess3 = _raw_sessions(
        tmp_path,
        "twice",
        [{"asof": d, "items": [item]}],
        {"rec0": ("candidate_snapshot_json", two)},
    )
    assert sess3["broken"] == 0 and len(sess3["records"][0]["items"]) == 1
    other = {**item, "rank": item["rank"] + 1}
    diff = f"[{json.dumps(item)}, {json.dumps(other)}]"
    sess4 = _raw_sessions(
        tmp_path,
        "twice2",
        [{"asof": d, "items": [item]}],
        {"rec0": ("candidate_snapshot_json", diff)},
    )
    assert sess4["records"] == [] and sess4["broken"] == 1


def test_review_file_with_duplicate_key_is_unreadable(
    market: Path, tmp_path: Path
) -> None:
    """내 판단 기록 파일에 같은 칸이 두 번이면 그 파일은 못 읽은 파일(이 도구가 쓴 파일에는 없음)."""
    app = _app(market, tmp_path)
    code, out = app.save(
        {"build_id": _bid(app.page("AAA001")), "ticker": "AAA001", "verdict": "hold"}
    )
    assert code == 200
    rid = out["review_id"]
    path = app.root / "reviews" / f"{rid}.json"
    assert ST.list_reviews(app.root)["broken"] == [] and ST.load(app.root, rid)
    text = path.read_text(encoding="utf-8")
    assert text.count('"decision": {') == 1
    path.write_text(
        text.replace('"decision": {', '"decision": {"verdict": "continue",'),
        encoding="utf-8",
    )
    assert ST.list_reviews(app.root) == {"items": [], "broken": [f"{rid}.json"]}
    with pytest.raises(ValueError):
        ST.load(app.root, rid)
    assert "AAA001" in app.page("AAA001")  # 다른 화면은 그대로 열림
    # 읽기 표시: 같은 칸 서로 다른 값 = 충돌(중첩 칸도) · 같은 값 = 그 값
    assert C.stored_filters(C.loads('{"a": true, "a": false}'))["a"] is C.CONFLICT
    assert C.filter_value(C.loads('{"x": {"b": 1, "b": 2}}')["x"], "b") is C.CONFLICT
    assert C.loads('{"a": true, "a": true}') == {"a": True}


def test_save_folder_problem_is_not_called_nan(market: Path, tmp_path: Path) -> None:
    """검증 F21 — 저장 폴더 자리에 보통 파일이 있으면 폴더 문제로 안내(값 오류 아님) · 판단 기록 0건."""
    app = _app(market, tmp_path)
    html = app.page("AAA001")
    (app.root / "reviews").write_text("보통 파일")
    code, out = app.save(
        {"build_id": _bid(html), "ticker": "AAA001", "verdict": "hold"}
    )
    assert code == 500 and out["error"].startswith("저장 폴더에 쓰지 못했습니다 — ")
    assert "NaN" not in out["error"] and "실제 폴더가 아님" in out["error"]
    assert (app.root / "reviews").read_text() == "보통 파일"
    # 값 오류는 저장할 글을 만들 때 따로(Unrecordable) · 파일 0건
    (app.root / "reviews").unlink()
    snap = app.builds[_bid(html)]
    with pytest.raises(ST.Unrecordable):
        ST.save(app.root, app.now(), {**snap, "bad": float("nan")}, {"verdict": "hold"})
    assert not (app.root / "reviews").exists() or not any(
        (app.root / "reviews").iterdir()
    )


# --- 반박 검토(2026-11-27 · F20 · F21 정정 뒤) — 손상 값 하나가 화면 · 저장을 막지 않음 · 원인별 안내 ---

BIG = "1" + "0" * 400  # 401자리 정수


def test_unencodable_text_is_rejected_before_write(
    market: Path, tmp_path: Path
) -> None:
    """D1 — 짝 없는 대리 문자는 입력 단계에서 422 · 원인 그대로 · 파일 0건."""
    app = _app(market, tmp_path)
    b = _bid(app.page("AAA001"))
    for body, key in (
        ({"reason": "a\ud83d b"}, "「이유」 칸"),
        ({"ais": [{"name": "GPT", "answer": "답\udc00"}]}, "「GPT 답」 칸"),
    ):
        code, out = app.save(
            {"build_id": b, "ticker": "AAA001", "verdict": "hold", **body}
        )
        assert code == 422 and f"{key}에 저장할 수 없는 문자" in out["error"], out
    assert not (app.root / "reviews").exists()
    snap = app.builds[b]
    for bad, why in (
        ({"x": "a\ud83d"}, "저장할 수 없는 문자"),
        ({"x": float("nan")}, "기록할 수 없는 수"),
    ):
        with pytest.raises(ST.Unrecordable, match=why):
            ST.save(app.root, app.now(), {**snap, **bad}, {"verdict": "hold"})
    assert not (app.root / "reviews").exists()


def test_damaged_past_review_does_not_block_next_save(
    market: Path, tmp_path: Path
) -> None:
    """D2 — 지난 판단 파일의 one_month 에 덧붙은 칸(깊은 중첩 · NaN)이 새 스냅숏에 들어가지 않음."""
    app = _app(market, tmp_path)
    code, out = app.save(
        {"build_id": _bid(app.page("AAA001")), "ticker": "AAA001", "verdict": "hold"}
    )
    path = app.root / "reviews" / f"{out['review_id']}.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["snapshot"]["review"]["one_month"]
    for extra in ("[" * 2000 + "]" * 2000, "NaN"):
        doc["snapshot"]["review"]["one_month"]["x"] = "@X@"
        path.write_text(json.dumps(doc).replace('"@X@"', extra), encoding="utf-8")
        item = ST.list_reviews(app.root)["items"][0]
        assert set(item["one_month"]) == {"value", "start", "end"}
        code, got = app.save(
            {
                "build_id": _bid(app.page("AAA001")),
                "ticker": "AAA001",
                "verdict": "hold",
            }
        )
        assert code == 200, got


def test_huge_integer_is_one_unreadable_value(market: Path, tmp_path: Path) -> None:
    """D3 — 아주 큰 정수 하나로 화면 전체가 실패하지 않음(그 값 · 그 파일만)."""
    ctx = _ctx(market)
    d = "2026-11-16"
    item = _true_item(ctx, d)
    cand = json.dumps([item]).replace(json.dumps(item["one_month_return_pct"]), BIG, 1)
    sess = _raw_sessions(
        tmp_path,
        "big",
        [{"asof": d, "items": [item]}],
        {"rec0": ("candidate_snapshot_json", cand)},
    )
    assert (
        len(sess["records"]) == 1
        and sess["records"][0]["items"][0]["one_month"] is None
    )
    rv = E.compose(ctx, "AAA001", sessions=sess, reviews=[])
    weeks = _text(PG.weeks_html(rv))
    assert NONE_LINE in rv["copy"]
    assert (
        "순위 · 1개월 값 없음(또는 읽을 수 없음)" in weeks
    )  # '저장되지 않음'으로 단정하지 않음
    assert "확인 안 함 — 순위 · 1개월 값이 없거나 읽을 수 없음" in weeks
    (tmp_path / "app").mkdir()
    app = _app(market, tmp_path / "app")
    code, out = app.save(
        {"build_id": _bid(app.page("AAA001")), "ticker": "AAA001", "verdict": "hold"}
    )
    path = app.root / "reviews" / f"{out['review_id']}.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["snapshot"]["review"]["one_month"]["value"] = "@X@"
    path.write_text(json.dumps(doc).replace('"@X@"', BIG), encoding="utf-8")
    assert ST.list_reviews(app.root)["broken"] == [path.name]
    assert "AAA001" in app.page("AAA001")  # 다른 화면은 그대로 열림
    assert f"읽지 못한 기록 1건: {path.name}" in app.list_page()


def test_save_failures_answer_with_their_cause(
    market: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D4 · D6 · 마지막 관문 — 요청 읽기 실패 = 400 · 파일 쓰기 실패 = 원인 · 예상 못 한 오류 = 결과 모름(끊지 않음)."""
    app = _app(market, tmp_path)
    port = _free_port()
    httpd = SV.serve(app, port)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        hdr = {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{port}"}
        for raw in ("[" * 100000 + "]" * 100000, '{"x": ' + "9" * 5000 + "}"):
            code, out = _req(port, "POST", "/api/reviews", raw.encode(), hdr)
            assert code == 400 and "JSON 을 읽지 못했습니다" in json.loads(out)["error"]
        b = _bid(app.page("AAA001"))
        body = json.dumps(
            {"build_id": b, "ticker": "AAA001", "verdict": "hold"}
        ).encode()

        def exists(*a: Any, **k: Any) -> None:
            raise FileExistsError(
                17, "File exists", str(app.root / "reviews" / "x.json")
            )

        monkeypatch.setattr(ST, "save", exists)
        code, out = _req(port, "POST", "/api/reviews", body, hdr)
        assert code == 500
        assert (
            json.loads(out)["error"]
            == "저장 폴더에 쓰지 못했습니다 — 같은 이름의 파일이 이미 있음(x.json)"
        )

        def boom(*a: Any, **k: Any) -> None:
            raise RuntimeError("뜻밖")

        monkeypatch.setattr(ST, "save", boom)
        code, out = _req(port, "POST", "/api/reviews", body, hdr)
        assert code == 500 and "저장됐는지 모릅니다" in json.loads(out)["error"]
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_any_damage_is_one_unreadable_row_or_file(
    market: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """어떤 손상이든(예상 못 한 오류 포함) 그 행 · 그 파일만 못 읽은 기록 — 화면 전체를 막지 않음."""
    ctx = _ctx(market)
    d = "2026-11-16"
    (tmp_path / "s").mkdir()
    db = _decision(tmp_path / "s", [{"asof": d, "items": [_true_item(ctx, d)]}])
    real = RD._session

    def flaky(r: tuple) -> dict:
        raise RuntimeError("뜻밖의 손상")

    monkeypatch.setattr(RD, "_session", flaky)
    assert H.read_sessions(db) == {"state": "ok", "records": [], "broken": 1}
    monkeypatch.setattr(RD, "_session", real)
    app = _app(market, tmp_path)
    code, out = app.save(
        {"build_id": _bid(app.page("AAA001")), "ticker": "AAA001", "verdict": "hold"}
    )
    monkeypatch.setattr(
        ST, "summary", lambda doc: (_ for _ in ()).throw(RuntimeError("뜻밖"))
    )
    assert ST.list_reviews(app.root)["broken"] == [f"{out['review_id']}.json"]


# --- 검증 §39(2026-11-27) F22 — 손상된 글자 한 건은 그 기록 · 그 파일만 ---


def test_broken_text_in_review_file_is_that_file_only(
    market: Path, tmp_path: Path
) -> None:
    """내 판단 파일 한 건의 짝 없는 대리 문자(JSON 이스케이프)는 그 파일만 못 읽음 — 목록 · 같은 ETF 화면 · 다른 기록은 그대로."""
    app = _app(market, tmp_path)
    ids = []
    for reason in ("이유1", "이유2"):
        code, out = app.save(
            {
                "build_id": _bid(app.page("AAA001")),
                "ticker": "AAA001",
                "verdict": "hold",
                "reason": reason,
            }
        )
        assert code == 200
        ids.append(out["review_id"])
    bad = app.root / "reviews" / f"{ids[1]}.json"
    text = bad.read_text(encoding="utf-8")
    assert text.count('"이유2"') == 1
    bad.write_text(text.replace('"이유2"', '"이유2\\ud83d"'), encoding="utf-8")
    got = ST.list_reviews(app.root)
    assert [x["review_id"] for x in got["items"]] == [ids[0]] and got["broken"] == [
        bad.name
    ]
    with pytest.raises(ValueError):
        ST.load(app.root, ids[1])
    assert ST.load(app.root, ids[0])
    port = _free_port()
    httpd = SV.serve(app, port)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        assert _req(port, "GET", "/reviews")[0] == 200
        assert _req(port, "GET", "/?ticker=AAA001")[0] == 200
        assert _req(port, "GET", f"/reviews/{ids[0]}")[0] == 200
        code, html = _req(port, "GET", f"/reviews/{ids[1]}")
        assert code == 404 and "읽지 못했습니다" in html
    finally:
        httpd.shutdown()
        httpd.server_close()


@pytest.mark.parametrize(
    "col,text",
    [
        ("user_memo", None),  # 읽을 수 없는 UTF-8 바이트(아래에서 X'C3' 로 넣음)
        (
            "candidate_snapshot_json",
            "NAME_SURROGATE",
        ),  # 후보 이름에 짝 없는 대리 문자(JSON 이스케이프)
    ],
)
def test_broken_text_in_one_session_row_is_that_row_only(
    market: Path, tmp_path: Path, col: str, text: Any
) -> None:
    """「AI 투자 세션」 한 행의 깨진 글자는 그 행만 못 읽음 — 정상 행과 그 인용은 그대로."""
    ctx = _ctx(market)
    d = "2026-11-16"
    good = {"asof": d, "items": [_true_item(ctx, d)]}
    other = {
        "asof": "2026-11-17",
        "items": [{**_true_item(ctx, d), "ticker": "DOM001"}],
    }
    db = _decision(tmp_path, [good, other])
    with sqlite3.connect(db) as con:
        if text is None:
            con.execute(
                f"UPDATE ai_session_records SET {col}=CAST(X'C3' AS TEXT) WHERE id='rec1'"
            )
        else:
            raw = json.dumps(other["items"]).replace(
                '"name": ', '"name": "x\\ud83d", "_n": ', 1
            )
            con.execute(
                f"UPDATE ai_session_records SET {col}=? WHERE id='rec1'", (raw,)
            )
    sess = H.read_sessions(db)
    assert sess["state"] == "ok" and sess["broken"] == 1
    assert [r["id"] for r in sess["records"]] == ["rec0"]
    rv = E.compose(ctx, "AAA001", sessions=sess, reviews=[])
    assert _cite_line(good["items"][0], d) in rv["copy"]
    PG.weeks_html(rv).encode("utf-8")


def test_text_ok_checks_keys_and_nested_values() -> None:
    assert C.text_ok({"a": ["가", {"b": "c"}], "n": 1, "x": None})
    assert not C.text_ok({"a\ud83d": 1})  # 칸 이름
    assert not C.text_ok({"a": [{"b": "x\udc00"}]})  # 중첩 목록 안 글


# --- 반박 검토(F22 정정 뒤) — 손상된 한 건 × 정상 한 건 표: 손상된 것만 못 읽음 · 나머지 화면 · 저장 · 인용 그대로 ---

UPD = "UPDATE ai_session_records SET "
WHERE1 = " WHERE id='rec1'"
SESSION_DAMAGE = {
    "id_blob": UPD + "id=CAST('rec0' AS BLOB)" + WHERE1,
    "id_null": UPD + "id=NULL" + WHERE1,
    "verdict_garbage": UPD + "user_verdict='garbage'" + WHERE1,
    "created_far": UPD + "created_at='9999-12-31T23:00:00+00:00'" + WHERE1,
    "created_naive": UPD + "created_at='2026-11-17T10:00:00'" + WHERE1,
    "asof_integer": UPD + "asof=20261117" + WHERE1,
    "asof_basic": UPD + "asof='20261117'" + WHERE1,
    "filters_blob": UPD + "filters_json=CAST(filters_json AS BLOB)" + WHERE1,
    "raw_surrogate": UPD
    + "candidate_snapshot_json=replace(candidate_snapshot_json, "
    + '\'"rank"\', \'"zz": "\\ud800", "rank"\')'
    + WHERE1,
}


def _healthy_and_damaged(ctx: H.Context) -> list[dict[str, Any]]:
    d = "2026-11-16"
    return [
        {"asof": d, "items": [_true_item(ctx, d)]},
        {
            "asof": "2026-11-17",
            "filters": NO_INVERSE,
            "items": [_true_item(ctx, d, NO_INVERSE)],
        },
    ]


def _screens_and_save_work(app: Any) -> None:
    for html in (app.page(None), app.page("AAA001"), app.list_page()):
        html.encode("utf-8")
    code, out = app.save(
        {"build_id": _bid(app.page("AAA001")), "ticker": "AAA001", "verdict": "hold"}
    )
    assert code == 200, out


@pytest.mark.parametrize("case", sorted(SESSION_DAMAGE))
def test_damaged_session_row_is_that_row_only(
    market: Path, tmp_path: Path, case: str
) -> None:
    ctx = _ctx(market)
    rows = _healthy_and_damaged(ctx)
    app = _app(market, tmp_path, rows)
    with sqlite3.connect(app.decision_db) as con:
        con.execute(SESSION_DAMAGE[case])
    sess = H.read_sessions(app.decision_db)
    assert sess["broken"] == 1 and [r["id"] for r in sess["records"]] == ["rec0"], case
    rv = E.compose(ctx, "AAA001", sessions=sess, reviews=[])
    assert _cite_line(rows[0]["items"][0], "2026-11-16") in rv["copy"]
    _screens_and_save_work(app)


def test_out_of_range_end_date_is_not_compared(market: Path, tmp_path: Path) -> None:
    """반박 검토 D1 — 1개월 끝일이 범위 밖(0001-01-01)이면 그 값은 '읽을 수 없음' · 다시 계산하지 않음 · 화면 · 저장 그대로."""
    ctx = _ctx(market)
    rows = _healthy_and_damaged(ctx)
    app = _app(market, tmp_path, rows)
    with sqlite3.connect(app.decision_db) as con:
        con.execute(
            UPD
            + "candidate_snapshot_json=replace(candidate_snapshot_json, "
            + '\'"end_date": "2026-11-16"\', \'"end_date": "0001-01-01"\')'
            + WHERE1
        )
    sess = H.read_sessions(app.decision_db)
    assert [r["items"][0]["end"] for r in sess["records"]] == ["2026-11-16", None]
    _screens_and_save_work(app)


REVIEW_DAMAGE = {
    "saved_far_past": ("saved_at", "0001-01-01T00:00:00+10:00"),
    "saved_far_future": ("saved_at", "9999-12-31T23:59:59-10:00"),
    "saved_naive": ("saved_at", "2026-11-26T10:00:00"),
    "saved_year_2500": ("saved_at", "2500-01-01T00:00:00+00:00"),
    "pasted_far": ("pasted_at", "9999-12-31T23:00:00+00:00"),
    "end_far": ("end", "0001-01-01"),
}


@pytest.mark.parametrize("case", sorted(REVIEW_DAMAGE))
def test_damaged_review_file_is_that_file_only(
    market: Path, tmp_path: Path, case: str
) -> None:
    app = _app(market, tmp_path)
    ids = []
    for _ in range(2):
        body = {
            "build_id": _bid(app.page("AAA001")),
            "ticker": "AAA001",
            "verdict": "hold",
        }
        code, out = app.save(
            {
                **body,
                "ais": [
                    {
                        "name": "GPT",
                        "answer": "답",
                        "pasted_at": "2026-11-26T01:00:00.000Z",
                    }
                ],
            }
        )
        assert code == 200
        ids.append(out["review_id"])
    path = app.root / "reviews" / f"{ids[1]}.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    key, value = REVIEW_DAMAGE[case]
    if key == "saved_at":
        doc["saved_at"] = value
    elif key == "pasted_at":
        doc["decision"]["ais"][0]["pasted_at"] = value
    else:
        doc["snapshot"]["end"] = value
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    got = ST.list_reviews(app.root)
    assert [x["review_id"] for x in got["items"]] == [ids[0]] and got["broken"] == [
        path.name
    ]
    _screens_and_save_work(app)
    port = _free_port()
    httpd = SV.serve(app, port)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        assert _req(port, "GET", f"/reviews/{ids[1]}")[0] == 404
        assert _req(port, "GET", f"/reviews/{ids[0]}")[0] == 200
        if (
            case == "pasted_far"
        ):  # 화면 만들기 실패도 그 기록만(500 아님 · 반박 검토 D7)
            real = PS.render_saved
            PS.render_saved = lambda doc: (_ for _ in ()).throw(RuntimeError("뜻밖"))
            try:
                assert _req(port, "GET", f"/reviews/{ids[0]}")[0] == 404
            finally:
                PS.render_saved = real
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_special_or_oddly_named_files_are_skipped(market: Path, tmp_path: Path) -> None:
    """반박 검토 D6 · 잠재 — FIFO · 이름 끝 줄바꿈은 그 파일만 못 읽음(읽다 멈추지 않음) · 큰 정상 파일은 읽음(검증 F23)."""
    app = _app(market, tmp_path)
    code, out = app.save(
        {"build_id": _bid(app.page("AAA001")), "ticker": "AAA001", "verdict": "hold"}
    )
    good = app.root / "reviews" / f"{out['review_id']}.json"
    os.mkfifo(app.root / "reviews" / "20261123T030000Z_cccccccc.json")
    big = app.root / "reviews" / "20261123T040000Z_dddddddd.json"
    doc = json.loads(good.read_text(encoding="utf-8"))
    doc["review_id"] = big.stem
    pad = " " * (11 * 1024 * 1024)  # 10MiB 를 넘는 정상 파일 — 상한 없이 읽힘
    big.write_text(json.dumps(doc, ensure_ascii=False) + pad, encoding="utf-8")
    nl = "20261123T050000Z_eeeeeeee\n"  # 이름 끝 줄바꿈 — 기록 번호도 같게(이름 검사만으로 걸러지는지 봄)
    text = json.dumps({**doc, "review_id": nl}, ensure_ascii=False)
    (app.root / "reviews" / f"{nl}.json").write_text(text, encoding="utf-8")
    got = ST.list_reviews(app.root)
    assert sorted(x["review_id"] for x in got["items"]) == sorted(
        [out["review_id"], big.stem]
    )
    assert sorted(got["broken"]) == sorted(
        ["20261123T030000Z_cccccccc.json", "20261123T050000Z_eeeeeeee\n.json"]
    )
    _screens_and_save_work(app)
    assert ST.shown_name("a\udcffb.json") == "a\\udcffb.json"


def test_reviews_are_ordered_by_time_not_text(market: Path, tmp_path: Path) -> None:
    """반박 검토 D5 — 저장 시각 표기가 달라도(기본 표기 · 다른 시간대) 시각 순으로 '지난 판단' · 비교 대상을 고름."""
    ctx = _ctx(market)
    one = {"value": 1.0, "start": "2026-10-20", "end": "2026-11-20"}
    base = {
        "ticker": "AAA001",
        "end": "2026-11-20",
        "verdict": "hold",
        "reason": "",
        "rank": 3,
        "one_month": one,
        "filters": FILTERS,
    }
    older = {
        **base,
        "review_id": "20261120T010000Z_aaaaaaaa",
        "saved_at": "20261120T100000+0900",
    }
    newer = {
        **base,
        "review_id": "20261123T010000Z_bbbbbbbb",
        "saved_at": "2026-11-23T01:00:00+00:00",
        "reason": "새것",
    }
    rv = E.compose(
        ctx,
        "AAA001",
        sessions={"state": "ok", "records": [], "broken": 0},
        reviews=[newer, older],
    )
    assert rv["previous"]["review"]["review_id"] == newer["review_id"]
    assert [r["review_id"] for r in rv["past"]] == [
        newer["review_id"],
        older["review_id"],
    ]
    assert (
        H.parse_time("9999-12-31T23:59:59-10:00") is None
    )  # 넘침 = 못 읽음(예외 아님)


def test_saved_list_is_ordered_by_time(market: Path, tmp_path: Path) -> None:
    """저장 목록도 시각 순 — 기본 표기(20261101T…)로 쓰인 더 이른 기록이 맨 위로 오지 않음."""
    app = _app(market, tmp_path)
    ids = []
    for _ in range(2):
        b = _bid(app.page("AAA001"))
        code, out = app.save({"build_id": b, "ticker": "AAA001", "verdict": "hold"})
        ids.append(out["review_id"])
    old = app.root / "reviews" / f"{ids[0]}.json"
    doc = json.loads(old.read_text(encoding="utf-8"))
    # 더 이르지만 글자 순으로는 뒤(20261 > 2026-) — 글자 순이면 맨 위로 옴
    doc["saved_at"] = "20261101T000000+0900"
    old.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    assert [x["review_id"] for x in ST.list_reviews(app.root)["items"]] == [
        ids[1],
        ids[0],
    ]


# --- 검증 §41(2026-11-27) F23 — 저장 성공 = 목록에 보이고 다시 열림(쓰기와 읽기가 같은 약속) ---


def test_large_normal_save_is_listed_and_reopens(market: Path, tmp_path: Path) -> None:
    """메모가 큰 정상 「AI 투자 세션」 기록 때문에 판단 파일이 10MiB 를 넘어도 저장 → 목록 → 다시 열기."""
    ctx = _ctx(market)
    memo = "a" * 3_000_000
    rows = [
        {"asof": d, "memo": memo, "items": [_true_item(ctx, d)]}
        for d in ("2026-11-13", "2026-11-16")
    ]
    app = _app(market, tmp_path, rows)
    code, out = app.save(
        {"build_id": _bid(app.page("AAA001")), "ticker": "AAA001", "verdict": "hold"}
    )
    assert code == 200, out
    path = app.root / "reviews" / f"{out['review_id']}.json"
    assert path.stat().st_size > 10 * 1024 * 1024
    assert [x["review_id"] for x in ST.list_reviews(app.root)["items"]] == [
        out["review_id"]
    ]
    assert ST.list_reviews(app.root)["broken"] == []
    PS.render_saved(ST.load(app.root, out["review_id"])).encode("utf-8")


def test_save_refuses_what_could_not_be_reopened(
    market: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """쓰기 전에 목록 · 다시 열기 검사를 돌려 보고, 통과 못 하면 422 · 파일 0건(저장 성공인데 못 여는 일이 없게)."""
    app = _app(market, tmp_path)
    b = _bid(app.page("AAA001"))
    snap = app.builds[b]
    with pytest.raises(ST.Unrecordable, match="다시 열 수 없는 기록"):
        ST.save(app.root, app.now(), {**snap, "end": "2026-13-40"}, {"verdict": "hold"})
    with pytest.raises(ST.Unrecordable, match="다시 열 수 없는 기록"):
        ST.save(
            app.root,
            app.now(),
            snap,
            ST.clean_decision({"verdict": "hold"}),
            reopen=lambda doc: (_ for _ in ()).throw(RuntimeError("화면")),
        )
    assert not (app.root / "reviews").exists() or not any(
        (app.root / "reviews").iterdir()
    )
    monkeypatch.setattr(
        PS, "render_saved", lambda doc: (_ for _ in ()).throw(RuntimeError("화면"))
    )
    code, out = app.save({"build_id": b, "ticker": "AAA001", "verdict": "hold"})
    assert code == 422 and "다시 열 수 없는 기록" in out["error"]
    assert not (app.root / "reviews").exists() or not any(
        (app.root / "reviews").iterdir()
    )


def test_request_within_input_limits_is_accepted(market: Path, tmp_path: Path) -> None:
    """입력 칸 상한을 모두 채운 최악의 요청(제어 문자 = JSON 6바이트)도 받아 저장 · 다시 열기(요청 상한 = 입력 상한에서 계산)."""
    app = _app(market, tmp_path)
    port = _free_port()
    httpd = SV.serve(app, port)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        _, html = _req(port, "GET", "/?ticker=AAA001")
        lim = ST.LIMITS
        body = {
            "build_id": _bid(html),
            "ticker": "AAA001",
            "verdict": "hold",
            "reason": "\x01" * lim["reason"],
            "next_check": "\x01" * lim["next_check"],
            "ai_excerpt": "\x01" * lim["ai_excerpt"],
            "ais": [
                {"name": n, "answer": "\x01" * lim["ai_answer"]} for n in ST.AI_BOXES
            ],
        }
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        assert len(raw) > 1024 * 1024  # 예전 상한(1MiB)으로는 거절되던 크기
        hdr = {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{port}"}
        code, out = _req(port, "POST", "/api/reviews", raw, hdr)
        assert code == 200, out
        rid = json.loads(out)["review_id"]
        assert _req(port, "GET", f"/reviews/{rid}")[0] == 200
    finally:
        httpd.shutdown()
        httpd.server_close()


# --- 반박 검토(F23 정정 뒤) — 쓰는 쪽과 읽는 쪽 · 화면과 서버가 같은 규칙 ---


def test_same_second_reviews_pick_the_same_latest(market: Path) -> None:
    """D1 — 같은 시각에 저장한 판단이 둘이면 「지난 검토와 비교」와 「이 ETF 의 지난 판단」이 같은 것을 최근으로."""
    ctx = _ctx(market)
    one = {"value": 1.0, "start": "2026-10-20", "end": "2026-11-20"}
    base = {"ticker": "AAA001", "end": "2026-11-20", "verdict": "hold", "reason": ""}
    base |= {
        "rank": 3,
        "one_month": one,
        "filters": FILTERS,
        "saved_at": "2026-11-23T10:00:00+09:00",
    }
    a = {**base, "review_id": "20261123T010000Z_aaaaaaaa"}
    b = {**base, "review_id": "20261123T010000Z_bbbbbbbb"}
    for order in ([a, b], [b, a]):
        rv = E.compose(
            ctx,
            "AAA001",
            sessions={"state": "ok", "records": [], "broken": 0},
            reviews=order,
        )
        assert (
            rv["previous"]["review"]["review_id"]
            == rv["past"][0]["review_id"]
            == b["review_id"]
        )


def test_saved_excerpt_keeps_line_breaks_and_v1_blank_answer(
    market: Path, tmp_path: Path
) -> None:
    """D2 · L5 — 판단에 쓴 대목의 줄바꿈을 다시 열기에서 지킴 · 예전 기록의 공백뿐인 답은 목록 · 다시 열기 모두 '답 없음'."""
    app = _app(market, tmp_path)
    b = _bid(app.page("AAA001"))
    body = {
        "build_id": b,
        "ticker": "AAA001",
        "verdict": "hold",
        "ai_excerpt": "첫 줄\n\n둘째 줄",
    }
    code, out = app.save(body)
    html = PS.render_saved(ST.load(app.root, out["review_id"]))
    assert '쓴 대목: <span class="keep">첫 줄\n\n둘째 줄</span>' in html
    doc = ST.load(app.root, out["review_id"])
    v1 = {
        "schema": ST.SCHEMA_V1,
        "review_id": "20261126T000318Z_5ef54a10",
        "saved_at": "2026-11-26T09:03:18+09:00",
        "snapshot": doc["snapshot"],
        "decision": {
            "verdict": "hold",
            "reason": "",
            "next_check": "",
            "used": [],
            "ai": {
                "name": "Claude",
                "answer": " \ufeff\n\t ",  # BOM 섞인 공백 — 브라우저 trim 은 지우고 파이썬 strip 은 못 지움
                "excerpt": "",
                "pasted_at": None,
                "copied_at": None,
                "asked": {"state": "no_copy"},
            },
        },
    }
    (app.root / "reviews" / f"{v1['review_id']}.json").write_text(
        json.dumps(v1, ensure_ascii=False), encoding="utf-8"
    )
    item = [
        x
        for x in ST.list_reviews(app.root)["items"]
        if x["review_id"] == v1["review_id"]
    ][0]
    assert item["ai_count"] == 0
    assert "붙여 넣은 답 없음" in PS.render_saved(ST.load(app.root, v1["review_id"]))


def test_blank_rule_matches_browser_trim(market: Path, tmp_path: Path) -> None:
    """D3 — '답 있음' · 앞뒤 공백 규칙 = 브라우저 String.prototype.trim(node 로 BMP 전 글자 대조) · \\x1c 만 있는 답도 답."""
    import shutil
    import subprocess

    if shutil.which("node") is None:
        pytest.skip("node 없음")
    js = (
        "let o=[];for(let c=0;c<0x10000;c++){if(c>=0xd800&&c<=0xdfff)continue;"
        "if(String.fromCharCode(c).trim()==='')o.push(c)}console.log(JSON.stringify(o))"
    )
    got = set(
        json.loads(
            subprocess.run(
                ["node", "-e", js], capture_output=True, text=True, check=True
            ).stdout
        )
    )
    assert got == {ord(c) for c in ST.JS_WS}
    app = _app(market, tmp_path)
    body = {"build_id": _bid(app.page("AAA001")), "ticker": "AAA001", "verdict": "hold"}
    code, out = app.save(
        {**body, "ais": [{"name": "GPT", "answer": "\x1c\x85", "helpful": True}]}
    )
    assert code == 200, out
    ais = ST.load(app.root, out["review_id"])["decision"]["ais"]
    assert [(a["name"], a["answer"], a["helpful"]) for a in ais] == [
        ("GPT", "\x1c\x85", True)
    ]
    code, out = app.save({**body, "reason": "가" * 501})
    assert code == 422 and out["error"] == "「이유」 칸이 너무 깁니다(최대 500자)"


def test_unrecordable_tells_page_to_reload(
    market: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D5 — 화면 자료 쪽 거절(422 · fix=reload)은 '다시 저장' 말고 '새로 고쳐 다시 열기'로 안내."""
    from tests.test_poc7_04_weekly_decision_browser import SAVE, _browser

    app = _app(market, tmp_path)
    monkeypatch.setattr(
        PS, "render_saved", lambda doc: (_ for _ in ()).throw(RuntimeError("화면"))
    )
    code, out = app.save(
        {"build_id": _bid(app.page("AAA001")), "ticker": "AAA001", "verdict": "hold"}
    )
    assert code == 422 and out["fix"] == "reload"
    page = app.page("AAA001")
    got = _browser(
        tmp_path, page, [SAVE, {"do": "respond", "status": 422, "json": out}]
    )
    msg = got["tabs"][0]["savemsg"]
    assert (
        msg.startswith("저장 안 됨 — 이 화면 자료로는 저장할 수 없습니다")
        and "새로 고쳐 다시 연 뒤" in msg
    )
    assert "다시 저장\n" not in msg


def test_browser_time_check_is_within_server_rule() -> None:
    """L1 — 화면이 받아들이는 시각(초안 되살리기)은 서버도 받음 · 브라우저가 쓰는 표기(toISOString)는 둘 다 받음."""
    import shutil
    import subprocess

    from app.weekly_decision import page_script as PSC

    if shutil.which("node") is None:
        pytest.skip("node 없음")
    s = PSC.SCRIPT
    i, j = s.index("var ISO_RE"), s.index(");", s.index("var ISO_RE")) + 2
    head = s[slice(i, j)]
    i, j = (
        s.index("function okIso(v){"),
        s.index("\n  }\n", s.index("function okIso(v){")) + 4,
    )
    fn = s[slice(i, j)]
    cases = [
        "2026-11-26T09:54:56.821Z",
        "2026-11-26T09:54:56Z",
        "2026-11-26T09:54Z",
        "2026-11-26T18:54:56+09:00",
        "2026-11-27T10:00:00",
        "2026-11-27T10:00",
        "2026-11-27T24:00Z",
        "2026-02-30T00:00:00Z",
        "1989-12-31T23:59:59Z",
        "2101-01-01T00:00:00Z",
        "2026-11-27T10:00:00+0900",
        "2026-11-27T10:60:00Z",
        "2026-11-27T10:00:00.1234567Z",
        "2100-12-31T23:59:59.999999Z",
    ]
    js = head + fn + f"console.log(JSON.stringify({json.dumps(cases)}.map(okIso)))"
    ok = json.loads(
        subprocess.run(
            ["node", "-e", js], capture_output=True, text=True, check=True
        ).stdout
    )
    for v, b in zip(cases, ok):
        assert not b or ST._is_time(v), v  # 화면이 받으면 서버도 받음
    assert ok[:4] == [True] * 4  # 브라우저가 쓰는 표기 · 시간대 표기


def test_long_reason_is_clipped_with_ellipsis() -> None:
    """L4 — 이유를 줄여 보일 때 '…'(잘린 줄이 전체처럼 보이지 않게)."""
    assert L.clip("가" * 80) == "가" * 80
    assert L.clip("가" * 81) == "가" * 80 + "…"


POOL = (
    list(ST.JS_WS)
    + ["\x1c", "\x1f", "\x85", "\x01", "\x7f", "​", "\U0001f600", "\U00010348"]
    + list("가힣aZ09\"'\\<>&{}[]:,")
    + ["́", "‮", "�"]
)


def _rand_text(rng: Any, n: int) -> str:
    return "".join(rng.choice(POOL) for _ in range(rng.randint(0, n)))


def test_any_valid_input_saves_lists_and_reopens_as_written(
    market: Path, tmp_path: Path
) -> None:
    """쓰기 ↔ 읽기 약속을 무작위 입력으로(고정 씨앗) — 칸 상한 안의 입력은 저장 200 · 목록에 보임 · 다시 열림 ·
    값은 규칙대로(이유 · 다음 확인 · 대목 = 브라우저 trim · AI 답 = 원문 그대로 · 공백뿐이면 빠짐) · 화면 자료 거절 0."""
    import random

    rng = random.Random(20261127)
    app = _app(market, tmp_path)
    for k in range(40):
        b = _bid(app.page("AAA001"))
        reason, nxt, exc = _rand_text(rng, 40), _rand_text(rng, 40), _rand_text(rng, 80)
        ais = []
        for name in ST.AI_BOXES:
            if rng.random() < 0.7:
                ans = _rand_text(rng, 120)
                has = bool(ST.js_trim(ans))
                ais.append(
                    {
                        "name": name,
                        "answer": ans,
                        "helpful": has and rng.random() < 0.5,
                        "pasted_at": "2026-11-26T09:54:56.821Z" if has else None,
                    }
                )
        body = {
            "build_id": b,
            "ticker": "AAA001",
            "verdict": rng.choice(["continue", "hold", "unrecorded"]),
            "reason": reason,
            "next_check": nxt,
            "ai_excerpt": exc,
            "ais": ais,
        }
        code, out = app.save(body)
        assert code == 200 and "fix" not in out, (k, out)
        doc = ST.load(app.root, out["review_id"])
        dec = doc["decision"]
        assert (dec["reason"], dec["next_check"], dec["excerpt"]) == tuple(
            ST.js_trim(x) for x in (reason, nxt, exc)
        )
        want = [
            (a["name"], a["answer"], a["helpful"])
            for a in ais
            if ST.js_trim(a["answer"])
        ]
        assert [(a["name"], a["answer"], a["helpful"]) for a in dec["ais"]] == want, k
        PS.render_saved(doc).encode("utf-8")
    got = ST.list_reviews(app.root)
    assert len(got["items"]) == 40 and got["broken"] == []
    app.page("AAA001").encode("utf-8")
