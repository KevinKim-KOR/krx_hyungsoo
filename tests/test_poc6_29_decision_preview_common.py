"""POC6-29 — 판단 근거 미리보기의 후보를 공통 기간 목록에서 찾기(PLAN §3-4 · 판정 Q4-2 · 완료 확인 2).

같은 조건의 요약(`GET /market/etf-compare/summary`) 상 · 하위 30 에서 종목을 찾고 화면이 본 쪽 · 선정 순위 ·
실제 시작일 · 끝일 · 끝일 가격 시점을 대조한다. 재현 사례(가격이 멈춘 ETF 가 옛 목록 n=10 을 차지해 B 3개월
10위를 옛 경로가 못 찾음) · 11 ~ 30위 · 하위 · 어긋남 안내(정확한 문구) · 새 필드 없으면 기존 동작.
임시 DB · 임시 보유만 쓴다(`api_client` · conftest 격리 · 라이브 DB 를 열지 않음).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import (
    api_decision_draft_preview,
    api_etf_compare,
    api_market_topn,
    decision_preview_common_period,
)
from app.decision_preview_lines import fmt_pct
from app.market_data_store import init_db
from tests.test_pc_price_basis import api_client  # noqa: F401 — fixture
from tests.test_poc6_28_etf_compare import AFTER, DAYS, END, _master, _put, _trend

PREVIEW = "/decision-draft/preview"
SUMMARY = "/market/etf-compare/summary"
CHANGED = "목록이 바뀌었습니다 — 목록을 다시 읽고 다시 고르세요."
NOT_IN_LIST = (
    "현재 목록 조건에서 이 후보를 찾지 못했습니다. 목록을 다시 불러온 뒤 시도하세요."
)
FAILURE = "판단 근거 미리보기를 생성하지 못했습니다. 다시 시도하세요."
STOPPED = "S00001"  # 가격이 DAYS[-30] 에 멈춘 ETF — 옛 목록(자기 마지막 행 계산)에는 3개월 1위
HELD = "E00005"


def _etf(k: int) -> str:
    return f"E{k:05d}"


@pytest.fixture
def seeded(
    api_client: TestClient,  # noqa: F811 — tests.test_pc_price_basis 의 fixture
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> TestClient:
    db: Path = api_market_topn.DEFAULT_DB_PATH
    init_db(db)
    _master(
        db,
        {
            "069500": "KODEX 200",
            STOPPED: "멈춘 ETF",
            **{_etf(k): f"시험 ETF {k:02d}" for k in range(40)},
        },
    )
    _put(db, "069500", _trend(140, 120.0, 100.0))
    for k in range(40):
        _put(db, _etf(k), _trend(140, 100.0, 70.0 + 3.0 * k))
    _put(db, STOPPED, [100.0] * 80 + _trend(31, 100.0, 400.0), days=DAYS[:-29])
    monkeypatch.setattr(api_decision_draft_preview, "DEFAULT_DB_PATH", db)
    monkeypatch.setattr(api_etf_compare, "MARKET_DB_PATH", db)
    monkeypatch.setattr(api_etf_compare, "META_DIR", tmp_path / "no_meta")
    monkeypatch.setattr(api_etf_compare, "DICTIONARY_PATH", tmp_path / "no_dict.json")
    holdings = [
        {"ticker": HELD, "name": "시험 ETF 05", "quantity": 2, "avg_buy_price": 90}
    ]
    assert api_client.put("/holdings", json={"holdings": holdings}).status_code == 200
    return api_client


def _summary(c: TestClient, basis: str) -> dict[str, Any]:
    s = c.get(SUMMARY, params={"basis": basis}).json()
    assert s["status"] == "ok" and s["end_date"] == END
    return s


def _md(d: str) -> str:
    _, m, day = d.split("-")
    return f"{int(m)}/{int(day)}"


def _pick(
    row: dict[str, Any], side: str, basis: str, screen: str = "candidate_list"
) -> dict[str, Any]:
    return {
        "target_kind": "candidate",
        "ticker": row["ticker"],
        "list_source": "common_period",
        "screen": screen,
        "basis": basis,
        "side": side,
        "rank": row["rank"],
        "start_date": row["basis_return"]["start"],
        "end_date": row["basis_return"]["end"],
        "end_price_state": row["end_price"]["state"],
    }


def _post(c: TestClient, body: dict[str, Any]) -> dict[str, Any]:
    res = c.post(PREVIEW, json=body)
    assert res.status_code == 200
    return res.json()


def _target_line(text: str) -> str:
    return text.split("\n")[1]  # [대상] 다음 첫 줄


# ── 찾기 성공(상위 · 11 ~ 30위 · 하위) ─────────────────────────────────────


def test_top_row_preview_uses_common_period_values(seeded: TestClient) -> None:
    s = _summary(seeded, "one_month")
    row = s["top"][2]
    body = _post(seeded, _pick(row, "top", "one_month"))
    assert body["status"] == "ok", body
    text = body["preview_text"]
    br = row["basis_return"]
    assert _target_line(text) == (
        f"- {row['name']} ({row['ticker']}) · 후보 ETF · 「후보리스트」 1개월 상위 3위 · "
        f"공통 기간 {_md(br['start'])} → {_md(br['end'])}"
    )
    # 1 · 3개월 = 행 상세(공통 기간 날짜) = 요약 criteria 값 그대로.
    detail = seeded.get("/market/etf-detail", params={"tickers": row["ticker"]}).json()
    it = detail["items"][0]
    m1, m3 = it["m1"], it["m3"]
    assert m1["value"] == row["criteria"]["one_month"]["value"]
    assert (
        f"1개월 {fmt_pct(m1['value'], plus_zero=True)} ({m1['start']} → {m1['end']}) · "
        f"3개월 {fmt_pct(m3['value'], plus_zero=True)} ({m3['start']} → {m3['end']})"
    ) in text
    same = it["same_kodex"]["one_month"]
    assert (
        f"1개월 {fmt_pct(same['value'], '%p')} (후보 {fmt_pct(same['etf_return_pct'])} · "
        f"KODEX200 {fmt_pct(same['kodex200_return_pct'])} · "
        f"사용 종가 {same['start']} → {same['end']})"
    ) in text
    assert "[시장]" in text and "[가격 흔들림]" in text and "[검토 질문]" in text
    assert body["evidence_as_of"]["target_as_of_date"] == END


def test_reproduced_case_three_month_rank10_old_path_fails_new_path_ok(
    seeded: TestClient,
) -> None:
    """PLAN §1-3 — 옛 목록(n=10)은 멈춘 ETF 가 한 칸을 차지해 B 3개월 10위를 못 찾는다."""
    s = _summary(seeded, "three_month")
    assert STOPPED not in [r["ticker"] for r in s["top"]]
    row = s["top"][9]
    old = _post(
        seeded,
        {
            "target_kind": "candidate",
            "ticker": row["ticker"],
            "n": 10,
            "basis": "three_month",
        },
    )
    assert old == {**old, "status": "error", "message": NOT_IN_LIST}
    new = _post(seeded, _pick(row, "top", "three_month"))
    assert new["status"] == "ok"
    assert "「후보리스트」 3개월 상위 10위 · 공통 기간" in _target_line(
        new["preview_text"]
    )


def test_rank_between_11_and_30(seeded: TestClient) -> None:
    s = _summary(seeded, "one_month")
    row = s["top"][14]
    body = _post(seeded, _pick(row, "top", "one_month", screen="sector_summary"))
    assert body["status"] == "ok"
    assert "「섹터요약」 1개월 상위 15위 · 공통 기간" in _target_line(
        body["preview_text"]
    )


def test_bottom_row(seeded: TestClient) -> None:
    s = _summary(seeded, "one_month")
    row = s["bottom"][1]
    body = _post(
        seeded, _pick(row, "bottom", "one_month", screen="holding_candidate_compare")
    )
    assert body["status"] == "ok"
    line = _target_line(body["preview_text"])
    assert "「보유와 후보 비교」 1개월 하위 2위 · 공통 기간" in line
    assert "현재 목록" not in line and "낮은 순" not in line


def test_holdings_screen_label_and_direct_holding(seeded: TestClient) -> None:
    s = _summary(seeded, "one_month")
    row = next(r for r in s["bottom"] if r["ticker"] == HELD)
    text = _post(seeded, _pick(row, "bottom", "one_month", screen="holdings"))[
        "preview_text"
    ]
    assert f"「보유」 1개월 하위 {row['rank']}위" in _target_line(text)
    assert "직접 보유: 있음(이미 보유 중)" in text


# ── 어긋남 → 정확한 다시 읽기 안내 ─────────────────────────────────────────


@pytest.mark.parametrize(
    "change",
    [
        {"rank": "+1"},
        {"start_date": "2026-01-02"},
        {"end_date": "2026-11-09"},
        {"end_price_state": "intraday"},
        {"side": "bottom"},  # 상위 1위는 하위 30 에 없다
        {"basis": "three_month"},  # 다른 조건의 목록
        {"exclude_inverse": False, "ticker": "Z99999"},  # 목록에 없는 종목
    ],
)
def test_mismatch_returns_list_changed(
    seeded: TestClient, change: dict[str, Any]
) -> None:
    s = _summary(seeded, "one_month")
    body = _pick(s["top"][0], "top", "one_month")
    for k, v in change.items():
        body[k] = body[k] + 1 if v == "+1" else v
    out = _post(seeded, body)
    assert out["status"] == "error" and out["message"] == CHANGED
    assert out.get("preview_text") is None


def test_refresh_between_list_and_pick_is_list_changed(seeded: TestClient) -> None:
    s = _summary(seeded, "one_month")
    body = _pick(s["top"][0], "top", "one_month")
    db = api_market_topn.DEFAULT_DB_PATH
    with sqlite3.connect(db) as con:  # 그사이 갱신 — 다음 영업일 행
        for tk in ["069500", *[_etf(k) for k in range(40)]]:
            con.execute(
                "INSERT INTO etf_daily_price(ticker, date, open, high, low, close, volume,"
                " change, source, fetched_at) VALUES (?, '2026-11-11', 1, 1, 1, 150, 1, 0,"
                " 'FinanceDataReader', '2026-11-11T07:00:00Z')",
                (tk,),
            )
    out = _post(seeded, body)
    assert out["status"] == "error" and out["message"] == CHANGED


@pytest.mark.parametrize(
    "change",
    [
        {"list_source": "topn"},
        {"screen": "market_discovery"},
        {"side": None},
        {"rank": 0},
        {"rank": 31},
        {"end_price_state": "closed"},
        {"start_date": None},
        {"basis": "weekly"},
    ],
)
def test_invalid_fields_are_general_failure(
    seeded: TestClient, change: dict[str, Any]
) -> None:
    s = _summary(seeded, "one_month")
    body = {**_pick(s["top"][0], "top", "one_month"), **change}
    out = _post(seeded, body)
    assert out["status"] == "error" and out["message"] == FAILURE


# ── 새 필드가 없으면 기존 동작 ─────────────────────────────────────────────


def test_absent_fields_keep_topn_path(seeded: TestClient) -> None:
    market = seeded.get(
        "/market/topn/latest", params={"n": 10, "basis": "one_month"}
    ).json()
    first = market["candidates"][0]
    body = _post(
        seeded, {"target_kind": "candidate", "ticker": first["ticker"], "n": 10}
    )
    assert body["status"] == "ok"
    line = _target_line(body["preview_text"])
    assert "현재 목록 1위(1개월 기준)" in line and "공통 기간" not in line


def _holding(screen: str, basis: str, **extra: Any) -> dict[str, Any]:
    return {
        "target_kind": "holding",
        "ticker": HELD,
        "list_source": "common_period",
        "screen": screen,
        "basis": basis,
        **extra,
    }


OLD_TOP10 = "현재 1개월 상위 10 후보"


def test_holding_preview_without_list_source_keeps_old_text(seeded: TestClient) -> None:
    """화면 조건을 보내지 않는 기존 호출은 그대로(예전 고정 목록 문구 포함)."""
    plain = _post(seeded, {"target_kind": "holding", "ticker": HELD})
    assert plain["status"] == "ok" and OLD_TOP10 in plain["preview_text"]


@pytest.mark.parametrize(
    "screen,label",
    [("holdings", "「보유」"), ("holding_candidate_compare", "「보유와 후보 비교」")],
)
@pytest.mark.parametrize("basis", ["one_month", "three_month"])
def test_holding_preview_relation_uses_screen_condition_list(
    seeded: TestClient, screen: str, label: str, basis: str
) -> None:
    """판정 Q4-2 둘째 항목 · 검토 지적 — B 화면 보유 미리보기의 후보 목록 관계 = 그 화면 조건의 공통 기간 목록만.

    예전 '현재 1개월 상위 10 후보' 겹침 · 동일 기간 줄은 나오지 않고, 같은 기간 KODEX 200 은 종목 상세 값.
    """
    s = _summary(seeded, basis)
    link = next(h for h in s["holdings"]["items"] if h["ticker"] == HELD)
    out = _post(seeded, _holding(screen, basis))
    assert out["status"] == "ok"
    text = out["preview_text"]
    assert OLD_TOP10 not in text
    word = {"one_month": "1개월", "three_month": "3개월"}[basis]
    p = s["period"]
    head = (
        f"후보 목록 위치({label} 조건 {word} 상·하위 30 · 공통 기간 "
        f"{_md(p['start'])} → {_md(p['end'])}): "
    )
    assert head in text
    br = link["basis_return"]
    where = (
        f"하위 {link['side_rank']}위"
        if link["side"] == "bottom"
        else (
            f"상위 {link['side_rank']}위" if link["side"] == "top" else "상·하위 30 밖"
        )
    )
    assert (
        f"{br['value']:+.2f}% · {_md(br['start'])} → {_md(br['end'])} · {where}" in text
    )
    assert (
        "하위 목록과의 구성종목 노출: 확인 불가" in text
    )  # 시험 자료엔 구성종목이 없다
    detail = seeded.get("/market/etf-detail", params={"tickers": HELD}).json()
    m1 = detail["items"][0]["same_kodex"]["one_month"]
    assert m1["status"] == "ok"
    assert f"(이 종목 {m1['etf_return_pct']:+.2f}% · " in text


def test_holding_preview_invalid_scope_is_general_failure(seeded: TestClient) -> None:
    for bad in (
        _holding("market_discovery", "one_month"),
        _holding("holdings", "weekly"),
        {**_holding("holdings", "one_month"), "list_source": "topn"},
    ):
        out = _post(seeded, bad)
        assert out["status"] == "error" and out["message"] == FAILURE


def test_same_day_price_change_with_same_rank_is_list_changed(
    seeded: TestClient,
) -> None:
    """검토 지적 — 순위 · 날짜 · 가격 상태가 같아도 화면이 본 수익률과 지금 값이 다르면 다시 읽기 안내."""
    s = _summary(seeded, "one_month")
    row = s["top"][0]
    body = {
        **_pick(row, "top", "one_month"),
        "basis_value": row["basis_return"]["value"],
    }
    assert _post(seeded, body)["status"] == "ok"
    stale = {**body, "basis_value": row["basis_return"]["value"] + 0.01}
    out = _post(seeded, stale)
    assert out["status"] == "error" and out["message"] == CHANGED


# ── 검증자 r1 F1 — 조립하는 사이 같은 날 재저장(한 저장 판으로만 승인) ─────────────

LATER = "2026-11-11T00:45:00Z"  # AFTER 보다 15분 뒤 — 같은 '마감 뒤 저장' 상태
assert LATER != AFTER
RESAVES = {
    # 이 종목 끝일 가격 1.2배(날짜 · 가격 상태 그대로 — 검증자 재현과 같음)
    "pick_close": ("pick", "UPDATE etf_daily_price SET close = close * 1.2"),
    # 이 종목 끝일 저장 시각만(같은 가격 · 같은 상태 — 실제 재저장은 저장 시각이 바뀜)
    "pick_stamp": ("pick", f"UPDATE etf_daily_price SET fetched_at = '{LATER}'"),
    # KODEX 200 끝일 가격 0.1%(같은 기간 KODEX 200 값만 · 1.2배면 069500 자체가 상위 1위가 되어 순위로 걸림)
    "kodex_close": ("069500", "UPDATE etf_daily_price SET close = close * 1.001"),
}


def _resave(kind: str, pick: str) -> None:
    who, sql = RESAVES[kind]
    with sqlite3.connect(api_market_topn.DEFAULT_DB_PATH) as con:
        cur = con.execute(
            sql + " WHERE ticker = ? AND date = ?",
            (pick if who == "pick" else who, END),
        )
        assert cur.rowcount == 1


def _hook(monkeypatch: pytest.MonkeyPatch, where: str, fire: Any) -> None:
    """`where` 바로 뒤(또는 앞) 한 번만 재저장 — 실제 SQL 갱신 · 실제 계산(가짜 값 없음)."""
    mod = decision_preview_common_period
    done: list[bool] = []

    def once() -> None:
        if not done:
            done.append(True)
            fire()

    if where == "after_first_detail":
        real_detail = mod.build_etf_detail

        def detail(*a: Any, **k: Any) -> Any:
            out = real_detail(*a, **k)
            once()
            return out

        monkeypatch.setattr(mod, "build_etf_detail", detail)
    elif where == "after_list_check":
        real_summary = api_etf_compare.get_etf_compare_summary

        def summary(*a: Any, **k: Any) -> Any:
            out = real_summary(*a, **k)
            once()
            return out

        monkeypatch.setattr(api_etf_compare, "get_etf_compare_summary", summary)
    else:
        assert where == "before_extras"
        real_extras = mod.selected_extras

        def extras(*a: Any, **k: Any) -> Any:
            once()
            return real_extras(*a, **k)

        monkeypatch.setattr(mod, "selected_extras", extras)


@pytest.mark.parametrize("kind", sorted(RESAVES))
@pytest.mark.parametrize(
    "where", ["after_first_detail", "after_list_check", "before_extras"]
)
def test_resave_while_assembling_candidate_is_list_changed(
    seeded: TestClient, monkeypatch: pytest.MonkeyPatch, kind: str, where: str
) -> None:
    """검증자 r1 F1 — 목록 대조 · 상세 · 추가 근거를 읽는 사이 같은 날 재저장이 있으면 정상 승인하지 않는다."""
    s = _summary(seeded, "one_month")
    row = s["top"][0]
    body = {
        **_pick(row, "top", "one_month"),
        "basis_value": row["basis_return"]["value"],
    }
    _hook(monkeypatch, where, lambda: _resave(kind, row["ticker"]))
    out = _post(seeded, body)
    assert out["status"] == "error" and out["message"] == CHANGED


def test_same_hooks_without_resave_still_ok(
    seeded: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """대조군 — 같은 끼워 넣기에 재저장이 없으면 정상(두 번 읽기 자체는 거절 사유가 아님)."""
    s = _summary(seeded, "one_month")
    row = s["top"][0]
    body = {
        **_pick(row, "top", "one_month"),
        "basis_value": row["basis_return"]["value"],
    }
    for where in ("after_first_detail", "after_list_check", "before_extras"):
        _hook(monkeypatch, where, lambda: None)
    out = _post(seeded, body)
    assert out["status"] == "ok"
    br = row["basis_return"]
    assert (
        f"1개월 {fmt_pct(br['value'], plus_zero=True)} ({br['start']} → {br['end']})"
        in out["preview_text"]
    )


@pytest.mark.parametrize("kind", ["pick_close", "pick_stamp", "kodex_close"])
def test_resave_while_reading_holding_relation_is_not_confirmed(
    seeded: TestClient, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """같은 뿌리 — 보유 미리보기의 목록 위치(요약) · 같은 기간 값(상세)이 다른 저장 판이면 관계를 적지 않는다."""
    _summary(seeded, "one_month")
    _hook(monkeypatch, "after_list_check", lambda: _resave(kind, HELD))
    out = _post(seeded, _holding("holdings", "one_month"))
    assert out["status"] == "ok"
    text = out["preview_text"]
    assert (
        "후보 목록과의 관계: 확인 불가 — 「보유」 조건 1개월 상·하위 30 목록을 읽는 동안 "
        "저장 자료가 바뀌었습니다. [다시 생성]으로 다시 확인하세요." in text
    )
    assert "후보 목록 위치(" not in text
    assert "- 1개월 · 3개월: 값 없음" in text  # 같은 기간 KODEX 200 값도 적지 않음
    assert OLD_TOP10 not in text
