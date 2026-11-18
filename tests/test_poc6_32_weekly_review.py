"""POC6-32 — 「주간 ETF 점검」(서버) 시험.

판정 §3 확인 기준(PLAN V1 §7 · V2 §3-1 · §4-3 · §4-4 · §5):
1. 11/16 고정 자료(공개 시장 자료 · 보유 없음)로 첫 3행(1위 단독 · 2위 단독 · 3 · 4위 Nifty 50 Index 묶음) ·
   비교 기간 10/19 → 11/16 · 시세 11/16 · ① 시장 = 공통 시장 근거 칸 하나(V1 시장 줄 · 두 번째 시장 흐름 읽기 없음 ·
   고정 자료의 `flow` 칸은 이제 조립에 쓰지 않음).
2. 보유 겹침 = 합성 사례(원천 전체 · 상위 행만 · 구성 누락 · 보유 상태 4종 · 계산 실패).
3. AI 대조 · 복사 글 V2(최신 확인 · 항목 줄 · 이유 · 다음 확인 · 공통 시장 근거 번호) = `test_poc6_32_weekly_answers.py`.
4. 저장 → 다시 열기 · 한 장의 마지막 기록이 다른 화면 기록과 섞이지 않음 · 기록 하나의 AI 답 해석 경로(AC3 ·
   저장 원문만 · 404)(임시 DB · 라이브 DB 안 엶).
5. V2 ③ 「선택한 후보 검토」 = 묶음 안 어느 ETF 든 · 보유 0 · 1 · 3개월 ok / 기간 다름 / 없음 · 가격 상태 조합 ·
   국내시장 대비 문구 · 행 자료 부족 · 저장 묶음 · '미기록' 판정(모든 층) · 경로 `/weekly/etf-check` · 겹침 카드 기간.
공통 시장 근거(`mev()`) = 공통 근거 시험 꾸러미의 합성 시장 DB(임시 폴더)로 한 번 만든 응답(라이브 DB 안 엶).
"""

from __future__ import annotations

import copy
import json
import sqlite3
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional, Sequence
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app import api_decision_sessions, api_etf_compare, decision_evidence_store
from app import api_weekly_review as W
from app import constituents_pair_exposure as P
from app import decision_evidence_readonly as DRO
from app import etf_official_info as eoi
from app import market_evidence as ME
from app import weekly_candidate_reads as CR
from app import weekly_candidate_review as wcr
from app import weekly_review as wr
from app.constituents_cross_family import confirmed_rows
from app.weekly_review_answers import compare, last_record_view
from tests import test_poc6_32_market_evidence as MEX
from tests.test_poc6_31_pair_exposure import (
    COND,
    ETFS,
    PRICE_DATE,
    base_hw,
    base_snaps,
    conf,
    hw,
    item,
    unconf,
    us,
)

FIX = json.loads(
    (Path(__file__).parent / "fixtures" / "poc6_32_weekly_1116.json").read_text(
        encoding="utf-8"
    )
)
NOW = "2026-11-17T09:00:00+09:00"
NONE_LAST = {"status": "none", "message": "이 화면에서 저장한 기록 없음"}
SEL = "476070"
REAL_READ = CR.read_candidate


def official_info(tickers, names=None):
    """고정 자료의 공개 KRX ETF 기본정보 행(상위 30 · 글자 그대로)으로 조회."""
    o = FIX["official"]
    return eoi.from_official(o["rows"], o["meta"], tickers, names)


def cons_detail(state="top_rows", asof="2026-11-13", data=None):
    """고른 ETF 구성 요약 — 노출 합성 사례(후보 C)와 같은 구성(R1 과 R4 가 같은 구성을 말하게)."""
    data = base_snaps()["C"]["confirmed"]["data"] if data is None else data
    rows = confirmed_rows({"asof": asof, "data": data})
    return wcr.detail_of(state, asof, rows, ETFS | {SEL})


# 진짜 빌더를 모듈을 읽을 때 잡아 둔다(r1 T1) — client fixture 가 ME.build_market_evidence 를 fake_mev 로 바꾼 뒤
# 처음 mev() 를 부르면(이 시험 하나만 새 프로세스로 돌릴 때) fake_mev → mev → _mev_json → fake_mev 로 되돌아 재귀했다.
_BUILD_MEV = ME.build_market_evidence


@lru_cache(maxsize=1)
def _mev_json() -> str:
    with tempfile.TemporaryDirectory() as d:
        db = MEX.make_db(Path(d) / "market.sqlite")
        with mock.patch.object(
            ME, "build_morning_basis", lambda **kw: MEX.morning()
        ), mock.patch.object(ME, "read_quick_quotes", lambda: MEX.quick()):
            out = _BUILD_MEV(now=MEX.NOW, db_path=db)
    return json.dumps(out, ensure_ascii=False)


def mev() -> dict[str, Any]:
    """공통 시장 근거 고정 응답(합성 시장 DB · 11/17 09:00 KST · 새 사본)."""
    return json.loads(_mev_json())


def review(
    selected=None,
    exposure=None,
    error=False,
    last=NONE_LAST,
    summary=None,
    official="fix",
    cons="fix",
    market="fix",
):
    return W.assemble(
        market_evidence=mev() if market == "fix" else market,
        summary=FIX["summary"] if summary is None else summary,
        selected=selected,
        exposure=exposure,
        exposure_error=error,
        last=last,
        generated_at=NOW,
        official_info=(
            official_info([selected] if selected else [])
            if official == "fix"
            else official
        ),
        constituents=cons_detail() if cons == "fix" else cons,
    )


def body(candidate=SEL, **kw):
    """노출 계산 합성 사례(POC6-31 시험 꾸러미 · 후보 C 의 구성을 고른 ETF 로)."""
    snaps = {**base_snaps(), candidate: base_snaps()["C"]}
    args = dict(
        candidate=candidate,
        holding=None,
        condition=COND,
        hw=base_hw(),
        price_date=PRICE_DATE,
        names={candidate: "고른"},
        etf_tickers=ETFS | {candidate},
        snaps=snaps,
    )
    args.update(kw)
    return P.build(**args)


def screen_texts(r: dict) -> list[str]:
    """화면에 나오는 서버 글 전부(AC-7 · 금액 · 보유 이름 검사용)."""
    out = [
        r["condition"]["line"]
    ]  # ① 시장은 화면이 공통 근거 칸으로 그린다(서버 글 없음)
    for f in r["flows"]:
        out += [f["title"], f["note"]]
    if r["overlap"]:
        out += [*r["overlap"]["warn_lines"], *r["overlap"]["lines"]]
        out.append(r["overlap"]["date_line"] or "")
    return out


# ── 1. 11/16 고정 자료 · 첫 3행 · 기간 · 자료별 기준일 ─────────────────────────────


def test_fixture_first_three_rows_match_design_example():
    r = review()
    assert r["status"] == "ok" and r["end_date"] == "2026-11-16"
    first = r["flows"][: r["first_rows"]]
    assert [(f["kind"], f["rep"], f["rep_rank"]) for f in first] == [
        ("single", "428560", 1),
        ("single", "476070", 2),
        ("group", "453810", 3),
    ]
    assert first[0]["title"] == "KODEX 미국ETF산업Top10 Indxx"
    assert first[1]["title"] == "KODEX 글로벌비만치료제TOP2 Plus"
    assert first[2]["title"] == "Nifty 50 Index"
    assert [m["ticker"] for m in first[2]["members"]] == ["453810", "453870"]
    assert first[2]["note"] == "같은 공식 기초지수를 따르는 2개 상품"
    assert first[2]["index_names_differ"] is False
    # 비만치료제 5 · 6위 = 지수가 달라 각자 원래 순위(판정 §2 ②)
    assert [(f["rep"], f["rep_rank"], f["kind"]) for f in r["flows"][3:5]] == [
        ("476310", 5, "single"),
        ("476690", 6, "single"),
    ]
    # 30개 모두 한 번씩 · 행 순서 = 대표의 원래 순위
    tick = [m["ticker"] for f in r["flows"] for m in f["members"]]
    assert sorted(tick) == sorted(x["ticker"] for x in FIX["summary"]["top"])
    reps = [f["rep_rank"] for f in r["flows"]]
    assert reps == sorted(reps)


def test_fixture_returns_and_condition_line():
    r = review()
    m = {x["ticker"]: x for f in r["flows"] for x in f["members"]}
    assert round(m["428560"]["one_month"], 2) == 12.55
    assert round(m["428560"]["three_month"], 2) == 9.86
    assert round(m["476070"]["one_month"], 2) == 11.77
    assert round(m["476070"]["three_month"], 2) == -0.62
    assert (
        round(m["453810"]["one_month"], 2)
        == round(m["453870"]["one_month"], 2)
        == 10.80
    )
    assert r["condition"]["line"] == (
        "1개월 상위 30개(선정 순서) · 10/19 → 11/16 · 인버스 · 레버리지 · 합성 · 선물 제외 · "
        "11/16 가격 = 마감 뒤 저장"
    )
    assert r["condition"]["filters"] == wr.FILTERS and r["condition"]["n"] == 30


def test_market_is_common_evidence_only_no_v1_market_lines():
    """① 시장 = 공통 시장 근거 칸 하나(PLAN V2 S3 · 목업 ①) — V1 목록 요약 판정 줄(`market`)은 응답 · 저장에 없다.
    저장 시장 칸 = 공통 근거 + 목록 쪽 같은 기간 KODEX 200(목록 근거)만(한 기록에 시장 근거 한 벌)."""
    r = review()
    assert "market" not in r
    assert r["market_evidence"] == wr.common_snapshot(mev())
    assert r["market_evidence"]["fields"]["regime"]["today"]["label"] == "하락장"
    snap = r["market_context_snapshot"]
    assert set(snap) == {"source", "common", "kodex200_same_period"}
    assert snap["common"] == r["market_evidence"]
    assert snap["kodex200_same_period"] == {
        "start": "2026-10-19",
        "end": "2026-11-16",
        "return_pct": FIX["summary"]["kodex200"]["basis_return_pct"],
    }
    # 공통 근거를 못 읽으면 '읽지 못함'(V1 줄로 대신하지 않음)
    na = review(market=None)
    assert na["market_evidence"] == {
        "status": "unavailable",
        "message": "공통 시장 근거를 읽지 못함",
    }
    assert "market" not in na


def test_summary_not_ok_passes_status_and_message():
    r = W.assemble(
        summary={"status": "no_common_period", "message": "기간 없음"},
        selected=None,
        exposure=None,
        exposure_error=False,
        last=NONE_LAST,
        generated_at=NOW,
    )
    assert (r["status"], r["message"]) == ("no_common_period", "기간 없음")
    assert r["last_record"] == NONE_LAST and "copy_text" not in r


# ── 묶음 규칙(판정 Q2 (c)) ─────────────────────────────────────────────────


def _row(rank, ticker, index_name):
    ok = {"status": "ok", "value": 1.0, "start": "s", "end": "e"}
    return {
        "rank": rank,
        "ticker": ticker,
        "name": f"E{ticker}",
        "held": False,
        "classification": {"index_name": index_name},
        "criteria": {"one_month": ok, "three_month": ok},
    }


def test_flows_unknown_index_is_single_and_not_bucketed_together():
    rows = wr.flows_of(
        [
            _row(1, "A1", None),
            _row(2, "B1", "지수 X"),
            _row(3, "C1", None),
            _row(4, "D1", "지수 X"),
        ]
    )
    assert [(f["kind"], f["rep"]) for f in rows] == [
        ("single", "A1"),
        ("group", "B1"),
        ("single", "C1"),
    ]
    assert rows[0]["note"] == "공식 기초지수 확인 불가 · 단독 표시"
    assert [m["ticker"] for m in rows[1]["members"]] == ["B1", "D1"]


def test_flows_confirmed_same_index_family_title_is_rep_official_name():
    r = review()
    dj = next(f for f in r["flows"] if f["rep"] == "483290")
    assert dj["kind"] == "group" and [m["rank"] for m in dj["members"]] == [
        24,
        25,
        27,
        29,
    ]
    assert dj["title"] == dj["members"][0]["index_name"]
    # 검토 BE-5 · PLAN I-6 · I-29 — 계열로 묶였고 공식 지수명이 다르면 '같은 공식 기초지수'라 하지 않음
    names = sorted({m["index_name"] for m in dj["members"]})
    assert len(names) > 1 and dj["index_names_differ"] is True
    assert dj["note"] == (
        f"같은 지수 계열 · 공식 기초지수명이 다른 상품 포함(지수명 {len(names)}개) · 4개 상품"
    )
    assert "같은 공식 기초지수" not in dj["note"]
    # 복사 글 = 머리(같은 기초지수 계열) · 묶음 줄에 상품마다 공식 지수명
    text = r["copy_text"]
    assert (
        "[먼저 볼 ETF 흐름 — 같은 기초지수 계열(공식 기초지수명이 같거나 계열 사전으로 확인된 것)만 한 묶음 · "
        "대표 = 묶음에서 가장 높은 순위 · 첫 화면 3행]"
    ) in text
    assert "같은 공식 기초지수만 한 묶음" not in text
    rest = next(e["text"] for e in r["evidence"] if e["key"] == "rest")
    for m in dj["members"]:
        assert f"{m['ticker']} " in rest
        assert f"공식 기초지수 {m['index_name']}" in rest
    nifty = r["flows"][2]  # 이름이 모두 같은 묶음은 상품마다 지수명을 붙이지 않음
    flow3 = next(e["text"] for e in r["evidence"] if e["key"] == "flow_3")
    assert nifty["index_names_differ"] is False and "공식 기초지수 " not in flow3
    # 다른 지수명 · 비만치료제 3종은 자동으로 묶지 않음
    ob = [f for f in r["flows"] if f["rep"] in ("476070", "476310", "476690")]
    assert all(f["kind"] == "single" for f in ob) and len(ob) == 3


# ── 2. 고른 ETF 의 보유 겹침(판정 Q4 · 합성 사례) ───────────────────────────────


def test_overlap_mixed_ranges_reads_range_first_and_exact_sums():
    o = review(SEL, body())["overlap"]
    assert o["state"] == "ok"
    assert o["warn_lines"] == [
        "보유 평가액의 52.00%(보유 ETF 2개)에 해당하는 ETF 는 저장된 상위 행 밖 구성이 미확인 — '겹침 없음'이 아닙니다",
        "보유 평가액의 3.10%(보유 ETF 1개)는 구성일이 달라 합계에서 뺐습니다",
        "보유 평가액의 3.20%(보유 ETF 1개)는 구성 원천 기준일 미확인이라 합계에서 뺐습니다",
        "보유 평가액의 27.00%(보유 ETF 2개)는 구성 자료가 없어 확인 불가",
        "시세가 없어 비중을 모르는 보유 1개(분모 밖)",
    ]
    assert o["lines"] == [
        "확보된 행으로 계산한 주요 주식별 보유 노출 범위 0.00% ~ 7.03%(주식 3개 · 주식마다 저장 범위에서 미확인 몫 40.00% ~ 52.00%)",
        "분모 = 현금 제외 보유 평가액 · 원천 전체 구성이 확인된 ETF 와 직접 보유의 평가 비중 14.70%",
    ]
    assert o["date_line"] == (
        "기준일: 고른 ETF 구성 11/13 · 노출 합계 11/13 · 보유 평가 11/13(부분 평가액) · 금액 없음"
    )
    assert o["numbers"] == {
        "min": "0.00",
        "max": "7.03",
        "stocks": 3,
        "no_value": 0,
        "full_confirmed": "14.70",
    }


def test_overlap_top30_only_uses_design_wording():
    b = body(
        hw=hw([item("A", "60.0000"), item("B", "40.0000")]),
    )
    o = review(SEL, b)["overlap"]
    assert o["warn_lines"] == [
        "보유 평가액의 60.00%(보유 ETF 1개)에 해당하는 ETF 는 상위 30행 밖 구성이 미확인 — '겹침 없음'이 아닙니다"
    ]
    assert o["lines"][1].endswith("평가 비중 40.00%")


def test_overlap_full_only_has_no_unknown_range_line():
    b = body(
        hw=hw(
            [
                item("B", "70.0000"),
                item("005930", "30.0000", etf=False, name="삼성전자"),
            ]
        )
    )
    o = review(SEL, b)["overlap"]
    assert o["warn_lines"] == []
    assert o["lines"][0].startswith("확보된 행으로 계산한 주요 주식별 보유 노출 범위 ")
    assert "미확인 몫" not in o["lines"][0]
    assert o["lines"][1].endswith("평가 비중 100.00%")


@pytest.mark.parametrize(
    "snap, want",
    [
        (unconf("2026-06-22", 10), "구성 원천 기준일 미확인(2026-06-22 보존 자료)"),
        (None, "구성 자료 없음"),
    ],
)
def test_overlap_selected_without_constituents_is_no_data(snap, want):
    snaps = base_snaps()
    if snap is not None:
        snaps[SEL] = snap
    b = body(snaps=snaps)
    assert b["status"] == P.STATUS_NO_CANDIDATE_DATA
    o = review(SEL, b)["overlap"]
    assert o["state"] == "no_data" and o["lines"] == []
    assert o["warn_lines"] == [
        f"자료 없음 — 이 ETF 의 {want} · [구성종목 보기]에서 수집(겹침 없음이라는 뜻 아님)"
    ]


@pytest.mark.parametrize(
    "kw, status, head",
    [
        ({"hw": None}, P.STATUS_HOLDINGS_UNREADABLE, "보유 목록을 읽지 못했습니다"),
        ({"hw": hw([])}, P.STATUS_NO_HOLDINGS, "등록 보유 없음"),
        ({"hw": hw([item("A", None)])}, P.STATUS_NO_WEIGHT_BASIS, "비중 확인 불가"),
        ({"etf_tickers": set()}, P.STATUS_NO_ETF_LIST, "확인 불가 — ETF 목록"),
    ],
)
def test_overlap_holdings_status_texts(kw, status, head):
    b = body(**kw)
    assert b["status"] == status
    o = review(SEL, b)["overlap"]
    assert o["state"] == status and o["warn_lines"][0].startswith(head)
    assert o["lines"] == [] and o["numbers"] is None


def test_overlap_calc_error_is_not_zero():
    o = review(SEL, None, error=True)["overlap"]
    assert o["state"] == "error"
    assert o["warn_lines"] == [
        "보유 겹침을 계산하지 못했습니다 — [다시 읽기]로 다시 시도(겹침 없음이라는 뜻 아님)"
    ]


def test_overlap_uncovered_stock_counts_as_unknown_not_zero():
    # 30행 ETF 하나뿐 · 후보 주식이 그 30행에 없음 → 확인 불가(0.00% 로 바꾸지 않음)
    b = body(
        hw=hw([item("A", "100.0000")]),
        snaps={
            **base_snaps(),
            SEL: conf("2026-11-13", base_snaps()["C"]["confirmed"]["data"][1:3]),
        },
    )
    o = review(SEL, b)["overlap"]
    assert o["lines"][0].startswith(
        "확보된 행으로 계산한 주요 주식별 보유 노출 범위 확인 불가(주식 2개"
    )
    assert o["numbers"]["min"] is None and o["numbers"]["no_value"] == 2


# ── 화면 · 복사 · 넘기기 = 같은 응답(판정 §3-1) · AC-7 · 금액 없음 ─────────────────


def test_response_has_no_candidate_word_amounts_or_holding_names():
    r = review(SEL, body())
    # 고른 ETF 의 주요 편입 이름(그 ETF 자기 구성 행 · R1)은 그 근거 줄에만 — 직접 보유 이름과 같아도 보유 목록이 아님
    own = next(e for e in r["evidence"] if e["key"] == "selected_constituents")
    assert "삼성전자" in own["text"]
    copy_rest = r["copy_text"].replace(own["text"], "")
    for t in [*screen_texts(r), copy_rest]:
        assert "후보" not in t, t
        assert "보유A" not in t and "보유L" not in t and "삼성전자" not in t, t
    raw = json.dumps(r, ensure_ascii=False)
    for k in ("eval_amount", "invested", "quantity", "avg_buy"):
        assert k not in raw


def test_copy_evidence_numbers_and_targets():
    r = review(SEL, body())
    ev = r["evidence"]
    assert [e["no"] for e in ev] == list(range(1, len(ev) + 1))
    for e in ev:
        assert r["copy_text"].count(f"[근거 {e['no']}] ") == 1
    n_market = len(mev()["evidence_items"]) - 1  # 자료 상태 줄만 번호 없음
    assert [e["group"] for e in ev[: n_market + 2]] == ["market"] * n_market + [
        "list",
        "list",
    ]
    t = {x["ticker"]: x["evidence"] for x in r["answer_targets"]}
    assert list(t) == [
        "428560",
        "476070",
        "453810",
    ]  # 고른 ETF 가 첫 3행 대표라 더하지 않음
    ov = [e["no"] for e in ev if e["group"] == "overlap"]
    assert set(ov) <= set(t[SEL]) and not set(ov) & set(t["428560"])
    assert "대상 ETF: 428560 · 476070 · 453810" in r["copy_text"]
    assert r["copy_text"].splitlines()[2] == (
        "[주간 ETF 점검 · " + r["condition"]["line"] + "]"
    )


def test_copy_selected_in_rest_is_added_as_target():
    r = review("476310", body("476310"))
    t = {x["ticker"]: x["evidence"] for x in r["answer_targets"]}
    assert list(t) == ["428560", "476070", "453810", "476310"]
    rest_no = next(e["no"] for e in r["evidence"] if e["group"] == "rest")
    assert rest_no in t["476310"]


def test_copy_without_selection_says_not_compared():
    r = review()
    assert r["selected"] is None and r["overlap"] is None
    ov = [e for e in r["evidence"] if e["group"] == "overlap"]
    assert [e["text"] for e in ov] == ["고른 ETF 없음 — 내 보유와 겹침은 대조 전"]


def test_selected_outside_list_is_reported_not_substituted():
    r = review("999999")
    assert (
        r["selected"] is None and r["selected_missing"] is True and r["overlap"] is None
    )


def test_candidate_snapshot_keeps_actual_periods_in_existing_fields():
    snap = review()["candidate_snapshot"]
    assert len(snap) == 30 and [c["rank"] for c in snap] == list(range(1, 31))
    allowed = {
        "rank",
        "ticker",
        "name",
        "daily_return_pct",
        "one_month_return_pct",
        "three_month_return_pct",
        "tags",
        "same_period_kodex200",
    }
    for c in snap:
        assert set(c) == allowed
        one = c["same_period_kodex200"]["one_month"]
        assert (one["status"], one["start_date"], one["end_date"]) == (
            "ok",
            "2026-10-19",
            "2026-11-16",
        )
        assert round(one["kodex200_return_pct"], 2) == -11.03
    three = snap[1]["same_period_kodex200"]["three_month"]
    w3 = FIX["summary"]["criteria_periods"]["three_month"]
    assert (three["start_date"], three["end_date"]) == (w3["start"], w3["end"])
    assert three["diff_pctp"] == round(
        three["candidate_return_pct"]
        - FIX["summary"]["kodex200"]["three_month_return_pct"],
        4,
    )


# ── 3. AI 답(V2 형식 · 대조 시험은 test_poc6_32_weekly_answers.py) ──────────────────────


def _ans(
    blocks: dict[str, tuple[str, ...]],
    latest: Optional[str] = "같음",
    items: Sequence[str] = (),
) -> str:
    """V2 답 형식 — 최신 확인 줄 · 항목 줄 · ETF 칸(상태 · 인용 근거 · 이유 · 다음 확인)."""
    out = [] if latest is None else [f"최신 확인: {latest}"]
    out += [f"- {it}" for it in items]
    for t, (state, cited, why, *nxt) in blocks.items():
        out += [
            f"[ETF {t}]",
            f"상태: {state}",
            f"인용 근거: {cited}",
            f"이유: {why}",
            f"다음 확인: {nxt[0] if nxt else '-'}",
        ]
    return "\n".join(out)


def nos(r: dict, *keys: str) -> str:
    """근거 key → 그 응답의 [근거 n] 번호(쉼표) — 번호를 하드코딩하지 않음."""
    by = {e["key"]: e["no"] for e in r["evidence"]}
    return ", ".join(str(by[k]) for k in keys)


def saved_answers(r: dict) -> dict[str, str]:
    """화면 고정 자료 saved 기록의 합성 답 3개(같은 상태 · 다른 번호 · 한 의견 · 최신 확인 셋 · 확인 시각 미기재)."""
    t1, t2, t3 = "428560", SEL, "453810"
    return {
        "gpt": _ans(
            {
                t1: ("근거 확인", nos(r, "regime", "flow_1"), "1개월 상위 1위"),
                t2: (
                    "추가 확인",
                    nos(r, "flow_2", "overlap_1"),
                    "상위 행 밖 보유 구성 미확인",
                    "보유 ETF 구성 더 받기",
                ),
                t3: ("자료 부족", nos(r, "flow_3"), "인도 수급 자료 없음"),
            }
        ),
        "gemini": _ans(
            {
                t1: ("근거 확인", nos(r, "flow_1", "regime"), "-"),
                t2: (
                    "추가 확인",
                    nos(r, "flow_2", "overlap_1", "overlap_2"),
                    "미확인 몫 먼저",
                ),
                t3: (
                    "근거 확인 | 추가 확인 | 자료 부족 중 하나",
                    nos(r, "flow_3"),
                    "x",
                ),
            },
            latest="최신 자료 확인 불가",
        ),
        "claude": _ans(
            {
                t1: ("근거 확인", nos(r, "regime", "flow_1"), "-"),
                t2: (
                    "추가 확인",
                    nos(r, "kospi_close", "flow_2"),
                    "3개월 흐름 약함",
                    "3개월 KODEX 대비 확인",
                ),
            },
            latest="새 값 있음",
            items=[
                "항목: 코스피 종가 · 값: 5,190.00 · 기준일: 2026-11-16 · "
                "출처: https://data.krx.co.kr · 확인 시각:  · 달라지는 해석: 코스피 방향"
            ],
        ),
    }


# ── 4. API · 저장 → 다시 열기 · 다른 화면 기록과 섞이지 않음(임시 DB) ───────────────────


@pytest.fixture
def client(monkeypatch, tmp_path):
    db = tmp_path / "decision_evidence.sqlite"
    monkeypatch.setattr(decision_evidence_store, "DEFAULT_DB_PATH", db)
    monkeypatch.setattr(api_decision_sessions, "DEFAULT_DB_PATH", db)
    monkeypatch.setattr(api_etf_compare, "_official", lambda: ({}, {"status": "ok"}))
    monkeypatch.setattr(
        api_etf_compare, "_dictionary", lambda: (None, {"status": "unavailable"})
    )
    monkeypatch.setattr(api_etf_compare, "_held_tickers", lambda: ([], "none"))
    calls: dict = {"summary": [], "load": []}

    def fake_summary(**kw):
        calls["summary"].append(kw)
        return FIX["summary"]

    def fake_read(candidate, *, db_path, condition=None):
        """고른 후보 한 읽기(구성 · ETF 목록 · 노출) — 라이브 DB 를 열지 않음(실제 읽기는 test_poc6_32_r1_reads)."""
        calls["load"].append((candidate, dict(condition or {})))
        return {
            "names": {SEL: "고른"},
            "constituents": cons_detail(),
            "exposure": body(candidate),
            "exposure_error": False,
        }

    def fake_mev(**kw):
        calls.setdefault("mev", []).append(kw)
        return mev()

    monkeypatch.setattr(W, "build_summary", fake_summary)
    # V2 공통 시장 근거 — 합성 고정 응답(라이브 시장 DB · 오늘 시세 파일을 읽지 않음)
    monkeypatch.setattr(ME, "build_market_evidence", fake_mev)
    # 고른 후보의 ETF 목록 · 구성 · 노출 = 한 읽기(r1 F1) 를 바꿔 끼움(라이브 DB 를 열지 않음)
    monkeypatch.setattr(CR, "read_candidate", fake_read)
    c = TestClient(api_module.app)
    c.calls = calls  # type: ignore[attr-defined]
    return c


def test_api_condition_is_fixed_and_selection_uses_existing_exposure(client):
    r = client.get("/weekly/etf-check", params={"selected": f" {SEL} "}).json()
    kw = client.calls["summary"][0]
    assert (kw["basis"], kw["filters"]) == ("one_month", wr.FILTERS)
    cand, cond = client.calls["load"][0]
    assert cand == SEL
    assert (cond["screen"], cond["basis"], cond["side"], cond["rank"]) == (
        "today_weekly_review",
        "one_month",
        "top",
        2,
    )
    assert (cond["start_date"], cond["end_date"]) == ("2026-10-19", "2026-11-16")
    assert r["selected"]["ticker"] == SEL and r["overlap"]["state"] == "ok"
    assert r["last_record"] == NONE_LAST


def test_api_selected_outside_list_skips_exposure(client):
    r = client.get("/weekly/etf-check", params={"selected": "999999"}).json()
    assert r["selected_missing"] is True and client.calls["load"] == []


def test_api_read_failures_stay_in_their_own_box(client, monkeypatch):
    def failed(candidate, *, db_path, condition=None):  # 노출 계산만 실패(구성은 읽음)
        out = {"names": {SEL: "고른"}, "constituents": cons_detail(), "exposure": None}
        return {**out, "exposure_error": True}

    monkeypatch.setattr(CR, "read_candidate", failed)
    na = {"status": "unavailable", "message": "시장 근거를 만들지 못했습니다"}
    monkeypatch.setattr(ME, "build_market_evidence", lambda **kw: na)
    r = client.get("/weekly/etf-check", params={"selected": SEL}).json()
    assert r["status"] == "ok" and r["overlap"]["state"] == "error"
    assert r["market_evidence"]["status"] == "unavailable"
    assert r["flows"] and r["selected_review"]  # 다른 칸은 그대로


def test_api_reads_market_once_through_common_evidence(client):
    """주간 라우트는 시장 흐름을 따로 읽지 않는다 — 공통 시장 근거 한 번(그 안에서 시장 흐름 한 번)."""
    assert not hasattr(W, "build_market_flow_context")
    client.get("/weekly/etf-check", params={"selected": SEL})
    assert len(client.calls["mev"]) == 1


def test_api_last_record_read_failure_is_not_none(client, monkeypatch):
    def boom(**k):
        raise sqlite3.OperationalError("locked")

    monkeypatch.setattr(DRO, "latest_record", boom)
    r = client.get("/weekly/etf-check").json()
    assert r["last_record"]["status"] == "error"


def _draft(r: dict, **over) -> dict:
    """화면 [AI 투자 세션으로 넘기기] 와 같은 초안 → 저장 요청(같은 응답 하나에서)."""
    d = {
        "asof": r["end_date"],
        "source_screen": r["source_screen"],
        "filters": r["condition"]["filters"],
        "candidate_snapshot": r["candidate_snapshot"],
        "question_text": r["copy_text"],
        "gpt_answer_text": _ans({"476070": ("추가 확인", "6, 9", "30행 밖 구성")}),
        "market_context_snapshot": r["market_context_snapshot"],
        "data_quality_snapshot": r["data_quality_snapshot"],
        "constituent_snapshot": r["constituent_snapshot"],
        "overlap_snapshot": r["overlap"] or {},
    }
    d.update(over)
    return d


def test_save_reopen_restores_list_period_condition_and_basis(client):
    r = client.get("/weekly/etf-check", params={"selected": SEL}).json()
    n0 = len(client.get("/decision/sessions", params={"limit": 50}).json()["records"])
    assert n0 == 0  # GET 은 쓰지 않음
    saved = client.post("/decision/sessions", json=_draft(r)).json()
    rec = client.get(f"/decision/sessions/{saved['id']}").json()["record"]
    assert rec["asof"] == "2026-11-16" and rec["source_screen"] == "today_weekly_review"
    assert rec["filters"] == wr.FILTERS
    # 보낸 칸이 모두 그대로(정의 밖 칸이 없어 버려진 칸 없음) · 저장 모델이 덧붙이는 칸은 빈 값(selected_preview)
    assert [
        {k: v for k, v in c.items() if k != "selected_preview"}
        for c in rec["candidate_snapshot"]
    ] == r["candidate_snapshot"]
    assert all(c.get("selected_preview") is None for c in rec["candidate_snapshot"])
    head = rec["question_text"].splitlines()[
        2
    ]  # 첫 문단 = 최신 공개 자료 확인 · 빈 줄 · 머리
    assert head.startswith("[주간 ETF 점검 · ") and (
        "1개월 상위 30개(선정 순서) · 10/19 → 11/16 · 인버스 · 레버리지 · 합성 · 선물 제외"
        in head
    )
    assert set(rec["market_context_snapshot"]) == {
        "source",
        "common",
        "kodex200_same_period",
    }
    # 공통 시장 근거 칸(번호 붙인 시장 줄 · 오늘 시세 칸 포함) = 보낸 그대로 · 일일 글은 저장하지 않음
    common = rec["market_context_snapshot"]["common"]
    assert common == wr.common_snapshot(mev()) and "daily_text" not in common
    assert common["fields"]["quick"]["review_date"] == "2026-11-17"
    # V2 저장 묶음(기존 자유 칸) = 보낸 그대로 — 고른 ETF · 상품 · 구성 요약 · 조건 · 공통 기간 · 겹침
    assert rec["data_quality_snapshot"] == r["data_quality_snapshot"]
    assert rec["constituent_snapshot"] == r["constituent_snapshot"]
    assert rec["constituent_snapshot"]["selected"]["ticker"] == SEL
    assert rec["overlap_snapshot"] == r["overlap"]
    # 판정 칸을 보내지 않은 주간 기록 = '미기록'(Q4 (c) 보완 · 직접 고른 보류와 구별)
    assert (
        rec["user_verdict"] == "unrecorded"
        and rec["user_memo"] == ""
        and rec["next_checks"] == []
    )

    last = client.get("/weekly/etf-check").json()["last_record"]
    assert (last["status"], last["id"], last["asof"]) == (
        "ok",
        saved["id"],
        "2026-11-16",
    )
    assert (last["memo"], last["next_checks"], last["verdict"]) == (
        None,
        [],
        "unrecorded",
    )
    row = next(x for x in last["compare"]["rows"] if x["ticker"] == SEL)
    assert row["cells"]["gpt"]["cited"] == [6, 9]
    assert row["cells"]["gpt"]["why"] == "30행 밖 구성"
    assert row["cells"]["gemini"] == {"status": "no_answer"}
    assert (
        row["state_text"] == "한 의견" and last["compare"]["opinion_text"] == "한 의견"
    )
    assert last["compare"]["answers"]["gpt"]["latest"]["state"] == "같음"


def test_last_record_never_mixes_other_screens(client):
    r = client.get("/weekly/etf-check").json()
    mine = client.post("/decision/sessions", json=_draft(r)).json()
    other = client.post(
        "/decision/sessions", json=_draft(r, source_screen="market_discovery")
    ).json()
    assert other["created_at"] >= mine["created_at"]
    last = client.get("/weekly/etf-check").json()["last_record"]
    assert last["id"] == mine["id"]
    only = client.get(
        "/decision/sessions", params={"source_screen": "today_weekly_review"}
    ).json()["records"]
    assert [x["id"] for x in only] == [mine["id"]]
    both = client.get("/decision/sessions").json()["records"]
    assert {x["id"] for x in both} == {mine["id"], other["id"]}


def test_record_review_route_parses_stored_originals_only(client, monkeypatch):
    """AC3 · I-14 — `GET /weekly/etf-check/records/{id}/review` = 저장한 질문 · 답 원문을 ④ 와 같은 해석기로 나눈다
    (최신 확인 · 항목 줄 · ETF 칸 · 대조) · 시장 · 목록 · 노출 다시 읽기 없음 · 쓰기 없음 · 남의 화면 기록 · 없는 id = 404.
    """
    r = client.get("/weekly/etf-check", params={"selected": SEL}).json()
    gpt = _ans(
        {SEL: ("추가 확인", "6, 9", "30행 밖 구성", "구성 더 받기")},
        latest="새 값 있음",
        items=[
            "항목: 코스피 종가 · 값: 5,190.00 · 기준일: 2026-11-16 · 출처: KRX · 확인 시각:"
        ],
    )
    claude = _ans({SEL: ("추가 확인", "6", "3개월 약함")})
    saved = client.post(
        "/decision/sessions",
        json=_draft(r, gpt_answer_text=gpt, claude_answer_text=claude),
    ).json()
    other = client.post(
        "/decision/sessions", json=_draft(r, source_screen="market_discovery")
    ).json()
    n_summary, n_load = len(client.calls["summary"]), len(client.calls["load"])
    fake_mev = ME.build_market_evidence

    def no_read(**kw):  # 해석 경로는 시장 근거를 다시 만들지 않음
        raise AssertionError("market evidence must not be rebuilt")

    monkeypatch.setattr(ME, "build_market_evidence", no_read)
    got = client.get(f"/weekly/etf-check/records/{saved['id']}/review")
    assert got.status_code == 200
    # 목록 요약 · 노출 계산도 다시 읽지 않음
    assert (len(client.calls["summary"]), len(client.calls["load"])) == (
        n_summary,
        n_load,
    )
    v = got.json()
    rec = decision_evidence_store.get_record(
        saved["id"], db_path=decision_evidence_store.DEFAULT_DB_PATH
    )
    assert v == json.loads(json.dumps(last_record_view(rec), ensure_ascii=False))
    assert (v["status"], v["id"], v["verdict"]) == ("ok", saved["id"], "unrecorded")
    a = v["compare"]["answers"]
    assert a["gpt"]["latest"]["state"] == "새 값 있음"
    assert a["gpt"]["items"][0]["checked_at_text"] == "확인 시각 미기재"
    assert a["gemini"] == {"status": "no_answer"}
    row = next(x for x in v["compare"]["rows"] if x["ticker"] == SEL)
    assert (row["cells"]["gpt"]["why"], row["cells"]["gpt"]["next_check"]) == (
        "30행 밖 구성",
        "구성 더 받기",
    )
    assert row["state_same"] is True and row["cited_common"] == [6]
    # 남의 화면 기록이 더 늦게 저장됐어도 주간 ④ 마지막 기록 = 이 기록 → 같은 해석
    monkeypatch.setattr(ME, "build_market_evidence", fake_mev)
    assert client.get("/weekly/etf-check").json()["last_record"] == v
    for rid, detail in (
        (other["id"], "「주간 ETF 점검」에서 저장한 기록이 아닙니다."),
        ("decision_none", "기록을 찾을 수 없습니다."),
    ):
        miss = client.get(f"/weekly/etf-check/records/{rid}/review")
        assert (miss.status_code, miss.json()["detail"]) == (404, detail)


def test_record_review_route_read_failure_is_korean_503(client, monkeypatch):
    def boom(*a, **k):
        raise sqlite3.OperationalError("locked")

    monkeypatch.setattr(DRO, "get_record", boom)
    got = client.get("/weekly/etf-check/records/decision_x/review")
    assert got.status_code == 503
    assert got.json()["detail"] == "기록을 읽지 못했습니다 — 잠시 뒤 다시 열어 주세요."


def test_list_filter_store_level(tmp_path):
    db = tmp_path / "d.sqlite"
    r = review()
    for screen in ("today_weekly_review", "market_discovery", "today_weekly_review"):
        decision_evidence_store.insert_record(
            asof="2026-11-16",
            source_screen=screen,
            filters=wr.FILTERS,
            candidate_snapshot=r["candidate_snapshot"][:1],
            question_text="q",
            gpt_answer_text="a",
            gemini_answer_text="",
            claude_answer_text="",
            user_memo="",
            user_verdict="hold",
            next_checks=[],
            linked_market_refresh_id=None,
            db_path=db,
        )
    got = decision_evidence_store.list_recent_records(
        limit=10, db_path=db, source_screen="today_weekly_review"
    )
    assert [x["source_screen"] for x in got] == ["today_weekly_review"] * 2
    assert len(decision_evidence_store.list_recent_records(limit=10, db_path=db)) == 3


# ── 독립 검토 정정(2026-11-17) ─────────────────────────────────────────────────


def test_copy_answer_heads_list_numbers_not_ranges():
    t = review(SEL, body())["copy_text"]
    head = next(
        ln for ln in t.splitlines() if ln.startswith("[ETF 476070] (관련 근거 ")
    )
    assert "~" not in head and head.endswith(")")


@pytest.mark.parametrize(
    "kw, why",
    [
        ({"hw": None}, "보유 목록을 읽지 못함"),
        ({"hw": hw([])}, "계산하지 않음"),
        ({"hw": hw([item("A", None)])}, "계산하지 않음"),
        ({"etf_tickers": set()}, "계산하지 않음"),
    ],
)
def test_overlap_status_date_line_never_says_direct_only(kw, why):
    o = review(SEL, body(**kw))["overlap"]
    assert "직접 보유만" not in (o["date_line"] or "")
    assert o["date_line"].endswith(f"노출 합계 확인 불가({why}) · 금액 없음")


def test_overlap_holdings_status_also_reports_selected_without_constituents():
    snaps = base_snaps()
    snaps[SEL] = unconf("2026-06-22", 10)
    o = review(SEL, body(hw=None, snaps=snaps))["overlap"]
    assert o["warn_lines"][0].startswith("보유 목록을 읽지 못했습니다")
    assert o["warn_lines"][1] == (
        "자료 없음 — 이 ETF 의 구성 원천 기준일 미확인(2026-06-22 보존 자료) · [구성종목 보기]에서 수집(겹침 없음이라는 뜻 아님)"
    )


def test_overlap_splits_out_of_range_and_weight_unknown():
    # 원천 전체 구성 ETF B(70%)에 고른 ETF 의 첫 주식이 있지만 비중을 읽을 수 없음 + 직접 보유 30%
    snaps = base_snaps()
    snaps["B"] = conf(
        "2026-11-13", [us(1, "LLY.N", "일라이 릴리", None)], complete=True
    )
    snaps[SEL] = base_snaps()["C"]
    b = body(
        hw=hw(
            [
                item("B", "70.0000"),
                item("005930", "30.0000", etf=False, name="삼성전자"),
            ]
        ),
        snaps=snaps,
    )
    o = review(SEL, b)["overlap"]
    assert o["warn_lines"] == []
    assert "편입 비중 확인 불가 몫 0.00% ~ 70.00%" in o["lines"][0]
    assert "저장 범위에서 미확인 몫" not in o["lines"][0]
    assert o["lines"][1].endswith("평가 비중 100.00%")


def test_copy_overlap_evidence_keeps_range_first_order():
    r = review(SEL, body())
    o = r["overlap"]
    head = f"고른 ETF {o['name']}({o['ticker']}) · {o['rank']}위"
    got = [e["text"] for e in r["evidence"] if e["group"] == "overlap"]
    assert got == [
        f"{head} — {o['warn_lines'][0]}",
        *o["warn_lines"][1:],
        *o["lines"],
        o["date_line"],
    ]


def test_front_fixture_matches_server_assembly():
    """화면 시험 고정 응답(frontend/lib/weeklyReviewTestFixtures.json)이 지금 서버 조립 출력과 같다."""
    front = json.loads(
        (
            Path(__file__).parent.parent
            / "frontend"
            / "lib"
            / "weeklyReviewTestFixtures.json"
        ).read_text(encoding="utf-8")
    )
    assert front["none"] == json.loads(json.dumps(review(), ensure_ascii=False))
    assert front["selected"] == json.loads(
        json.dumps(review(SEL, body()), ensure_ascii=False)
    )
    saved = front["saved"]
    drop = lambda d: {k: v for k, v in d.items() if k != "last_record"}  # noqa: E731
    assert drop(saved) == drop(front["selected"])
    assert saved["last_record"]["compare"] == compare(
        front["selected"]["copy_text"],
        saved_answers(front["selected"]),
        {c["ticker"]: c["name"] for c in front["selected"]["candidate_snapshot"]},
    )


def test_candidate_snapshot_three_month_needs_same_window():
    """3개월 같은 기간 KODEX 200 비교 = 그 ETF 의 3개월 기간이 공통 3개월 기간과 같을 때만(다르면 비교 안 함)."""
    s = json.loads(json.dumps(FIX["summary"]))
    w3 = s["criteria_periods"]["three_month"]
    r0 = s["top"][0]["criteria"]["three_month"]
    r0.update(status="ok", start="2026-08-01", end=w3["end"])  # 기간이 다른데 상태만 ok
    r1 = s["top"][1]["criteria"]["three_month"]
    r1.update(status="period_differs", start=w3["start"], end=w3["end"])
    snap = wr.candidate_snapshot(s)
    assert snap[0]["same_period_kodex200"]["three_month"]["status"] == "unavailable"
    assert snap[0]["same_period_kodex200"]["three_month"]["diff_pctp"] is None
    assert snap[1]["same_period_kodex200"]["three_month"]["status"] == "unavailable"
    assert snap[2]["same_period_kodex200"]["three_month"]["status"] == "ok"


# ── 5. V2 ③ 「선택한 후보 검토」(PLAN V2 §3-1 · §9) ──────────────────────────────


def _sum_with(ticker, **crit):
    """고정 자료 사본 — 한 ETF 의 기준 칸 · 끝일 가격 상태만 바꿈(합성 사례)."""
    s = copy.deepcopy(FIX["summary"])
    row = next(r for r in s["top"] if r["ticker"] == ticker)
    for k, v in crit.items():
        if k == "end_price":
            row["end_price"] = v
        elif k == "kodex_price":
            s["regime"]["price"] = v
        else:
            row["criteria"][k].update(v)
    return s


def _ret(r, code):
    return next(x for x in r["selected_review"]["returns"] if x["period"] == code)


def test_v2_selected_review_fixture_r1_r2_r3():
    sr = review(SEL, body())["selected_review"]
    assert (sr["ticker"], sr["rank"], sr["side"]) == (SEL, 2, "top")
    p = sr["product"]
    assert (p["found"], p["kind"], p["index_name"], p["index_provider"]) == (
        True,
        "etf",
        "iSelect 글로벌 비만치료제TOP2 Plus 지수(PR)",
        "NH투자증권",
    )
    assert (p["market"], p["asset"], p["multiple"], p["replication"], p["fee_pct"]) == (
        "해외",
        "주식",
        "일반",
        "실물(패시브)",
        "0.450000",
    )
    assert p["csv"] == {
        "name": "krx_etf_basic_20260927.csv",
        "asof": "2026-09-27",
        "ok": True,
        "error": None,
    }
    c = sr["constituents"]
    assert (c["state"], c["state_label"], c["stored_rows"], c["stock_rows"]) == (
        "top_rows",
        "상위 4행만 확인",
        4,
        3,
    )
    assert [s["name"] for s in c["top_stocks"]] == [
        "일라이 릴리",
        "노보 노디스크 ADR",
        "삼성전자",
    ]
    assert c["top3_sum_pct"] == 57.27
    one, three = _ret({"selected_review": sr}, "1m"), _ret(
        {"selected_review": sr}, "3m"
    )
    assert (one["status"], one["direction"], one["start"], one["end"]) == (
        "ok",
        "up",
        "2026-10-19",
        "2026-11-16",
    )
    assert one["market"] == {
        "value_pct": -11.0265,
        "diff_pp": 22.8,
        "comparable": True,
        "provisional": False,
        "reason": None,
    }
    assert one["phrase"] == "올랐고 국내시장보다 22.80%p 높음"
    assert three["phrase"] == "내렸지만 국내시장보다 25.67%p 덜 내림"
    assert sr["price_note"] == "가격 = 11/16 마감 뒤 저장(이 ETF · KODEX 200 같음)"
    assert sr["checks"] == [
        "구성 상위 4행만 확인 — 그 밖 구성은 미확인",
        "구성 기준일 11/13 · 가격 끝일 11/16 — 기준일이 다름",
        "공식 기준정보 파일 2026-09-27(51일 전 · 그 뒤 바뀐 상품 정보는 확인 불가)",
        *sr["overlap"]["warn_lines"],
        "이동평균 · 거래량 · 흔들림 등 상세 근거는 [판단 근거 보기]",
    ]
    assert sr["overlap"] == review(SEL, body())["overlap"]  # R4 = V1 겹침 그대로
    assert sr["overlap_note"].endswith("후보끼리 중복률과 다른 값")


def test_v2_selected_review_holds_no_amounts_or_holding_only_names():
    r = review(SEL, body())
    raw = json.dumps(r["selected_review"], ensure_ascii=False)
    for k in ("eval_amount", "invested", "quantity", "avg_buy", "보유A", "보유L"):
        assert k not in raw
    # 주요 편입 이름 = 고른 ETF 자기 구성 행에서만(보유 목록에서 오지 않음)
    own = {row[2] for row in base_snaps()["C"]["confirmed"]["data"]}
    assert {
        s["name"] for s in r["selected_review"]["constituents"]["top_stocks"]
    } <= own


@pytest.mark.parametrize("ticker, rank", [("453810", 3), ("453870", 4)])
def test_v2_any_group_member_is_selectable(ticker, rank):
    r = review(ticker, body(ticker))
    assert r["selected"] == {
        "ticker": ticker,
        "name": r["selected_review"]["name"],
        "rank": rank,
    }
    assert r["selected_review"]["product"]["index_name"] == "Nifty 50 Index"
    assert r["data_quality_snapshot"]["selected"]["ticker"] == ticker


def test_v2_zero_holdings_still_shows_candidate_evidence():
    r = review(SEL, body(hw=hw([])))
    sr = r["selected_review"]
    assert r["overlap"]["state"] == P.STATUS_NO_HOLDINGS
    assert sr["constituents"]["state"] == "top_rows" and sr["product"]["found"]
    assert [x["direction"] for x in sr["returns"]] == ["up", "down"]
    assert any(c.startswith("등록 보유 없음") for c in sr["checks"])


@pytest.mark.parametrize(
    "cons, line",
    [
        (None, "구성 자료를 읽지 못함 — [다시 읽기]로 다시 시도"),
        (wcr.detail_of("not_collected", None, [], ETFS), "구성 자료 없음(미수집) — "),
        (
            cons_detail(state="source_unconfirmed", asof="2026-06-22"),
            "구성 원천 기준일 미확인(6/22 저장 자료)",
        ),
        (cons_detail(state="full", asof="2026-11-16"), None),
    ],
)
def test_v2_constituent_states_in_checks(cons, line):
    sr = review(SEL, body(), cons=cons)["selected_review"]
    first = [c for c in sr["checks"] if c.startswith("구성")]
    if line is None:
        assert first == [] and sr["constituents"]["state_label"] == "전체 확인"
    else:
        assert first[0].startswith(line)


@pytest.mark.parametrize(
    "period, crit, status, phrase, check",
    [
        (
            "3m",
            {"three_month": {"status": "period_differs", "start": "2026-08-25"}},
            "period_differs",
            "내렸음 · 기간 다름 · 국내시장 대비 안 함",
            "3개월 기간 다름(실제 8/25 → 11/16 · 공통 8/18 → 11/16) — 국내시장 대비 안 함",
        ),
        (
            "3m",
            {"three_month": {"status": "missing", "value": None, "start": None}},
            "missing",
            "수익률 확인 불가",
            "3개월 수익률 자료 없음 — 확인 불가",
        ),
        (
            "1m",
            {"same_kodex_1m": {"status": "missing", "kodex200_return_pct": None}},
            "ok",
            "올랐음 · 국내시장 대비 안 함(국내시장(KODEX 200) 같은 날짜 가격 없음)",
            "1개월 국내시장 대비 안 함 — 국내시장(KODEX 200) 같은 날짜 가격 없음",
        ),
        (
            "3m",
            {
                "three_month": {"status": "ok", "start": "2026-08-25"}
            },  # 상태만 ok · 기간 다름
            "ok",
            "내렸음 · 국내시장 대비 안 함(기간 다름)",
            "3개월 국내시장 대비 안 함 — 기간 다름",
        ),
    ],
)
def test_v2_returns_period_table(period, crit, status, phrase, check):
    r = review(SEL, body(), summary=_sum_with(SEL, **crit))
    x = _ret(r, period)
    assert (x["status"], x["phrase"]) == (status, phrase)
    assert x["market"]["comparable"] is False
    assert check in r["selected_review"]["checks"]
    if status == "period_differs":
        # 기간 다름 = 값 유지(확인 불가 아님) · ② 행도 값 + 실제 기간 + 자료 부족
        assert x["value_pct"] == -0.6184 and x["common"]["start"] == "2026-08-18"
        m = next(m for f in r["flows"] for m in f["members"] if m["ticker"] == SEL)
        assert m["three_month"] == -0.6184
        assert m["periods"]["three_month"] == {
            "status": "period_differs",
            "start": "2026-08-25",
            "end": "2026-11-16",
        }
        assert m["lack"] == ["3개월 기간 다름"]
        assert r["data_quality_snapshot"]["period_differs_values"] == [
            {
                "ticker": SEL,
                "rank": 2,
                "period": "3m",
                "value_pct": -0.6184,
                "start": "2026-08-25",
                "end": "2026-11-16",
            }
        ]


AFTER = {"date": "2026-11-16", "state": "after_close", "fetched_at_kst": None}
INTRA = {"date": "2026-11-16", "state": "intraday", "fetched_at_kst": None}
UNK = {"date": "2026-11-16", "state": "unknown", "fetched_at_kst": None}


@pytest.mark.parametrize(
    "etf, kodex, comparable, provisional, reason",
    [
        (AFTER, AFTER, True, False, None),
        (INTRA, INTRA, True, True, None),
        (
            INTRA,
            AFTER,
            False,
            False,
            "가격 상태 다름(이 ETF 장중 저장값 · 잠정 · KODEX 200 마감 뒤 저장)",
        ),
        (UNK, AFTER, False, False, "가격 끝일 저장 상태 확인 필요"),
        (AFTER, UNK, False, False, "가격 끝일 저장 상태 확인 필요"),
        (
            {**AFTER, "date": "2026-11-13"},
            AFTER,
            False,
            False,
            "가격 끝일이 기간 끝과 다름",
        ),
        ({}, AFTER, False, False, "가격 끝일 확인 불가"),
    ],
)
def test_v2_price_state_table(etf, kodex, comparable, provisional, reason):
    s = _sum_with(SEL, end_price=etf, kodex_price=kodex)
    r = review(SEL, body(), summary=s)
    for code in ("1m", "3m"):
        m = _ret(r, code)["market"]
        assert (m["comparable"], m["provisional"], m["reason"]) == (
            comparable,
            provisional,
            reason,
        )
    if provisional:
        assert _ret(r, "1m")["phrase"].endswith(" · 잠정 비교")
        assert (
            "1개월 국내시장 대비는 잠정 — 두 가격 모두 장중 저장값"
            in r["selected_review"]["checks"]
        )


def test_v2_period_check_comes_before_price_state():
    # 판정 순서 변이 — 기간이 다르면 가격 상태와 상관없이 '기간 다름'
    s = _sum_with(SEL, three_month={"status": "period_differs"}, end_price=UNK)
    assert _ret(review(SEL, body(), summary=s), "3m")["market"]["reason"] == "기간 다름"


def test_v2_flow_lack_fixture_is_empty_and_group_unions_members():
    r = review()
    assert all(
        f["lack"] == [] for f in r["flows"]
    )  # 11/16 상위 30 = 가격 · 상품 자료 모두 있음
    assert r["data_quality_snapshot"]["lack"] == []
    s = _sum_with("453870", three_month={"status": "period_differs"})
    g = next(f for f in review(summary=s)["flows"] if f["rep"] == "453810")
    assert g["lack"] == ["3개월 기간 다름"] and g["members"][0]["lack"] == []


def test_v2_official_missing_and_csv_unread_lines():
    info = {"csv": eoi.csv_meta(True, "krx_etf_basic_20260927.csv", "2026-09-27")}
    sr = review(SEL, body(), official={**info, "items": {}})["selected_review"]
    assert sr["product"]["found"] is False
    assert sr["product"]["missing_reason"] == "공식 기준정보에 없음"
    assert "공식 기준정보에 없음 — 공식 기초지수 · 상품 구조 확인 불가" in sr["checks"]
    sr = review(SEL, body(), official=None)["selected_review"]
    assert sr["product"]["missing_reason"] == "공식 기준정보 파일을 읽지 못함"
    assert not any(c.startswith("공식 기준정보 파일 2026") for c in sr["checks"])


def test_v2_snapshots_for_transfer():
    r = review(SEL, body())
    dq = r["data_quality_snapshot"]
    # 근거 목록 = 복사 글의 [근거 n] 그대로(번호 · 묶음 · key · 글 · ETF)
    assert dq["condition"] == r["condition"] and dq["evidence_list"] == r["evidence"]
    # 검토 F2 · F5 · PLAN I-32 — 고른 후보 R2 결과(국내시장 대비 · 잠정 · 사유 · 문구) 그대로
    saved = [
        {
            **{k: x[k] for k in wcr.RETURN_KEYS},
            "market": {k: x["market"][k] for k in wcr.MARKET_KEYS},
        }
        for x in r["selected_review"]["returns"]
    ]
    assert dq["selected"] == {
        "ticker": SEL,
        "name": r["selected"]["name"],
        "rank": 2,
        "side": "top",
        "returns": saved,
    }
    assert [x["period"] for x in saved] == ["1m", "3m"] and set(saved[0]) == {
        *wcr.RETURN_KEYS,
        "market",
    }
    # 30행 · KODEX 200 끝 가격 상태(날짜 · 상태) — '당시 검토'가 저장된 상태로 I-8 적용
    ps, top = dq["price_states"], FIX["summary"]["top"]
    assert (
        ps["rows"]
        == {
            t["ticker"]: {
                "date": t["end_price"]["date"],
                "state": t["end_price"]["state"],
            }
            for t in top
        }
        and len(ps["rows"]) == 30
    )
    assert ps["kodex200"] == {"date": "2026-11-16", "state": "after_close"}
    assert dq["common_periods"] == {
        "one_month": {"start": "2026-10-19", "end": "2026-11-16"},
        "three_month": {"start": "2026-08-18", "end": "2026-11-16"},
    }
    cs = r["constituent_snapshot"]
    assert cs["selected"]["ticker"] == SEL
    assert cs["product"] == r["selected_review"]["product"]
    assert cs["constituents"] == r["selected_review"]["constituents"]
    none = review()
    assert none["selected_review"] is None and none["constituent_snapshot"] == {}
    assert none["data_quality_snapshot"]["selected"] is None
    assert none["data_quality_snapshot"]["price_states"] == ps
    # 끝 가격 상태가 비면 '모름'(unknown)으로 저장(빈 칸을 마감 뒤로 채우지 않음)
    s2 = copy.deepcopy(FIX["summary"])
    s2["top"][0]["end_price"] = {"date": None, "state": None}
    s2["regime"]["price"] = None
    ps2 = review(summary=s2)["data_quality_snapshot"]["price_states"]
    assert ps2["rows"][s2["top"][0]["ticker"]] == {"date": None, "state": "unknown"}
    assert ps2["kodex200"] == {"date": None, "state": "unknown"}


# ── 6. V2 API · 경로 · '미기록' 판정(모든 층) ────────────────────────────────────


def test_v2_route_moved_and_reads_candidate_without_holdings(client):
    assert client.get("/today/weekly-review").status_code == 404
    r = client.get("/weekly/etf-check", params={"selected": SEL}).json()
    sr = r["selected_review"]
    assert [c for c, _ in client.calls["load"]] == [SEL]  # 고른 후보 한 읽기 한 번
    # _official 이 빈 표를 주는 시험 환경 — ETF 목록에는 있으니 '공식 기준정보에 없음'(개별 주식 아님)
    assert (sr["product"]["kind"], sr["product"]["missing_reason"]) == (
        "etf",
        "공식 기준정보에 없음",
    )
    assert sr["constituents"]["state"] == "top_rows"


def test_v2_api_constituents_read_failure_is_error_not_missing(
    client, monkeypatch, tmp_path
):
    def boom(*a, **k):
        raise sqlite3.OperationalError("locked")

    db = tmp_path / "market.sqlite"
    sqlite3.connect(str(db)).close()  # 있는 파일(읽기 실패를 만들 곳)
    monkeypatch.setattr(W.etf_constituents_store, "DEFAULT_DB_PATH", db)
    monkeypatch.setattr(CR, "read_candidate", REAL_READ)
    monkeypatch.setattr(CR, "_holdings_side", lambda: (None, None, False))
    monkeypatch.setattr(CR, "master_in", boom)
    r = client.get("/weekly/etf-check", params={"selected": SEL}).json()
    assert (
        r["status"] == "ok" and r["selected_review"]["constituents"]["state"] == "error"
    )
    # 같은 한 읽기 — 겹침도 '읽지 못함'(없음 아님) · ETF 목록을 못 읽어 종류 '알 수 없음'
    assert r["overlap"]["state"] == "error"
    assert r["selected_review"]["product"]["kind"] == "unknown"


@pytest.mark.parametrize(
    "screen, over, code, stored",
    [
        ("today_weekly_review", {}, 200, "unrecorded"),
        ("today_weekly_review", {"user_verdict": "hold"}, 200, "hold"),
        ("today_weekly_review", {"user_verdict": "unrecorded"}, 200, "unrecorded"),
        ("market_discovery", {}, 200, "hold"),
        ("market_discovery", {"user_verdict": "unrecorded"}, 422, None),
        ("today_weekly_review", {"user_verdict": None}, 422, None),
    ],
)
def test_v2_verdict_api_layer(client, screen, over, code, stored):
    r = client.get("/weekly/etf-check").json()
    res = client.post(
        "/decision/sessions", json=_draft(r, source_screen=screen, **over)
    )
    assert res.status_code == code
    if stored:
        rec = client.get(f"/decision/sessions/{res.json()['id']}").json()["record"]
        assert rec["user_verdict"] == stored


def test_v2_unrecorded_source_is_this_screen():
    # 저장소 · 처리 함수 층 시험 = tests/test_decision_evidence_store.py · tests/test_decision_sessions_api.py
    assert decision_evidence_store.UNRECORDED_SOURCE_SCREENS == (wr.SOURCE_SCREEN,)
