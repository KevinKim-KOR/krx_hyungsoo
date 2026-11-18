"""POC6-32 V2 — 「주간 ETF 점검」 복사 글 · AI 답 해석 · 대조 · [판단 근거 보기] 주간 화면 시험(PLAN V2 §4-3 · §5 AC2 · AC3).

1. 복사 글 = 최신 공개 자료 확인 문단(일일과 같은 원문) → 머리 「주간 ETF 점검」 → 공통 시장 근거 줄 전부 [근거 n]
   (일일 글과 같은 줄 · 같은 순서 · 자료 상태만 번호 없음) → 주간 근거(목록 조건 · 같은 기간 KODEX 200 · 흐름 · 고른 ETF
   R1 · R2 · 보유 겹침). V1 둘째 줄 없음. 기간 다름 = 값 + '기간 다름' + 실제 기간(W5).
2. 답 해석 = 최신 확인(같음 · 새 값 있음 · 확인 불가 · 형식 없음) · 이름 붙은 항목 줄(값 속 ' · ' · 링크 · 시각 콜론 ·
   빈 확인 시각 = '확인 시각 미기재') · ETF 칸(상태 · 인용 근거 · 이유 · 다음 확인) · V1 문법 규칙(머리 · 겹친 칸 ·
   인용 근거 문법) 그대로.
3. 대조 = 상태 같음/다름 · 같은 번호(교집합)와 답마다 다른 번호 · 확인된 답 하나 = '한 의견' · 못 읽음 = '요약 확인 필요'.
4. 경로 · 저장 → 갱신 → 다시 열기(임시 DB · 공통 시장 근거 합성 고정 응답 · 라이브 DB 안 엶).
5. [판단 근거 보기] = 주간 화면 key 를 후보 미리보기만 · 그 화면 고정 조건만 받음(보유 미리보기 화면 목록에는 없음).
"""

from __future__ import annotations

import copy
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import api_weekly_review as W
from app import market_evidence as ME
from app import weekly_review as wr
from app import weekly_review_text as T
from app.decision_preview_common_period import (
    PICK_SCREEN_LABEL,
    SCREEN_LABEL,
    WEEKLY_SCREEN,
    CommonPeriodPick,
    list_label,
)
from app.market_evidence_text import LATEST_CHECK
from app.weekly_review_answers import (
    NO_TIME,
    compare,
    last_record_view,
    parse_cited,
    parse_item,
    parse_latest,
    parse_question,
)
from tests.test_pc_price_basis import api_client  # noqa: F401 — fixture(seeded 가 씀)
from tests.test_poc6_29_decision_preview_common import (  # noqa: F401 — fixture
    CHANGED,
    FAILURE,
    _holding,
    _pick,
    _post,
    _summary,
    _target_line,
    seeded,
)
from tests.test_poc6_32_weekly_review import (  # noqa: F401 — fixture(client)
    FIX,
    NONE_LAST,
    SEL,
    _ans,
    _draft,
    _sum_with,
    body,
    client,
    mev,
    nos,
    review,
    saved_answers,
)


def ev_by(r: dict, key: str) -> dict:
    return next(e for e in r["evidence"] if e["key"] == key)


def copy_lines(r: dict) -> list[str]:
    return r["copy_text"].splitlines()


# ── 1. 복사 글 ────────────────────────────────────────────────────────────────


def test_copy_starts_with_latest_check_same_as_daily_and_drops_v1_line():
    r = review(SEL, body())
    daily_first = mev()["daily_text"].split("\n\n", 1)[0]
    assert r["copy_text"].split("\n\n", 1)[0] == LATEST_CHECK == daily_first
    assert copy_lines(r)[2] == f"[주간 ETF 점검 · {r['condition']['line']}]"
    for v1 in ("수치 · 기준일만", "ETF 주간 검토", "「오늘의 투자 점검」 ·", "관측:"):
        assert v1 not in r["copy_text"], v1


def test_copy_market_numbers_are_the_daily_lines_in_order():
    """AC2 — 주간 시장 [근거 n] = 일일 글의 근거 줄과 같은 글 · 같은 순서(자료 상태만 번호 없음)."""
    m = mev()
    r = review(SEL, body())
    items = [i for i in m["evidence_items"] if i["key"] != "data_status"]
    market = [e for e in r["evidence"] if e["group"] == "market"]
    assert [(e["key"], e["text"]) for e in market] == [
        (i["key"], i["text"]) for i in items
    ]
    assert [e["no"] for e in market] == list(range(1, len(items) + 1))
    daily = m["daily_text"].splitlines()
    for e in market:
        assert e["text"] in daily and f"[근거 {e['no']}] {e['text']}" in copy_lines(r)
    status = next(i["text"] for i in m["evidence_items"] if i["key"] == "data_status")
    assert status.startswith("[자료 상태] ") and status in copy_lines(r)
    assert not any(x["text"] == status for x in r["evidence"])
    groups = [e["group"] for e in r["evidence"]]
    order = ["market", "list", "flow", "rest", "selected", "overlap"]
    assert sorted(groups, key=order.index) == groups  # 공통 시장 근거 → 주간 근거 순


def test_copy_weekly_list_items_fixture():
    r = review()
    assert ev_by(r, "list_condition")["text"] == (
        f"[목록 조건] {r['condition']['line']} · 3개월 공통 기간 8/18 → 11/16"
    )
    assert ev_by(r, "list_kodex")["text"] == (
        "[같은 기간 KODEX 200] 1개월 -11.03%(10/19 → 11/16) · "
        "3개월 -26.29%(8/18 → 11/16) · 시세 11/16"
    )
    assert not any(e["group"] == "selected" for e in r["evidence"])
    assert "[고른 ETF — 어떤 상품인가" not in r["copy_text"]


def test_copy_selected_r1_r2_lines_fixture():
    r = review(SEL, body())
    assert ev_by(r, "selected_product")["text"] == (
        "[고른 ETF — 어떤 상품인가] KODEX 글로벌비만치료제TOP2 Plus(476070) · 1개월 상위 2위 · "
        "공식 기초지수 iSelect 글로벌 비만치료제TOP2 Plus 지수(PR) · 지수산출기관 NH투자증권 · "
        "투자 대상 해외 · 주식 · 상품 구조 추적배수 일반 · 실물(패시브) · 총보수 0.45%"
        "(KRX 공식 기준정보 2026-09-27 파일)"
    )
    sr = r["selected_review"]
    c = sr["constituents"]
    assert ev_by(r, "selected_constituents")["text"] == (
        "[고른 ETF — 구성] 주요 편입(주식) "
        + " · ".join(f"{s['name']} {s['weight_pct']:.2f}%" for s in c["top_stocks"])
        + " → 상위 3개 합 57.27% · "
        + c["line"]
    )
    assert ev_by(r, "selected_returns")["text"] == (
        "[고른 ETF — 실제로 올랐나] 1개월 +11.77%(10/19 → 11/16) 올랐고 국내시장보다 22.80%p 높음 · "
        "국내시장(KODEX 200) -11.03% / 3개월 -0.62%(8/18 → 11/16) 내렸지만 국내시장보다 25.67%p "
        "덜 내림 · 국내시장(KODEX 200) -26.29% · 가격 = 11/16 마감 뒤 저장(이 ETF · KODEX 200 같음)"
    )
    # 고른 ETF 근거는 그 ETF 답의 관련 근거에만
    t = {x["ticker"]: x["evidence"] for x in r["answer_targets"]}
    sel_nos = [e["no"] for e in r["evidence"] if e["group"] == "selected"]
    assert set(sel_nos) <= set(t[SEL]) and not set(sel_nos) & set(t["428560"])


def test_copy_period_differs_prints_value_and_actual_dates():
    """W5 — 기간 다름 값은 '확인 불가'가 아니라 값 + '기간 다름' + 실제 시작 → 끝(흐름 · 묶음 · 나머지 · 고른 ETF)."""
    s = _sum_with(SEL, three_month={"status": "period_differs", "start": "2026-08-25"})
    g = next(r for r in s["top"] if r["ticker"] == "453870")
    g["criteria"]["three_month"].update(status="period_differs", start="2026-09-01")
    rest = next(r for r in s["top"] if r["ticker"] == "476310")
    rest["criteria"]["one_month"].update(status="period_differs", start="2026-10-20")
    r = review(SEL, body(), summary=s)
    assert "3개월 -0.62% · 기간 다름(8/25 → 11/16)" in ev_by(r, "flow_2")["text"]
    assert (
        "TIGER 인도니프티50(453870) 1개월 +10.80% · 3개월 -0.64% · 기간 다름(9/1 → 11/16)"
        in ev_by(r, "flow_3")["text"]
    )
    assert "476310) +10.69% · 기간 다름(10/20 → 11/16)" in ev_by(r, "rest")["text"]
    assert (
        "3개월 -0.62%(실제 8/25 → 11/16 · 공통 8/18 → 11/16) 내렸음 · 기간 다름 · 국내시장 대비 안 함"
        in ev_by(r, "selected_returns")["text"]
    )
    assert "3개월 확인 불가" not in r["copy_text"]


@pytest.mark.parametrize(
    "market, line",
    [
        (None, "[자료 상태] 공통 시장 근거 확인 불가 — 시장 근거를 읽지 못함"),
        (
            {
                "status": "unavailable",
                "message": "시장 근거를 만들지 못했습니다",
                "evidence_items": [],
                "data_status": ["VIX 읽기 실패", "시장 근거를 만들지 못했습니다"],
            },
            "[자료 상태] 공통 시장 근거 확인 불가 — 시장 근거를 만들지 못했습니다 · VIX 읽기 실패",
        ),
    ],
)
def test_copy_market_unavailable_has_no_market_numbers_and_no_v1_lines(market, line):
    """공통 시장 근거를 못 읽으면 시장 번호 없이 '확인 불가' 한 줄(예전 시장 줄로 대신하지 않음 · I-23)."""
    r = review(SEL, body(), market=market)
    assert not any(e["group"] == "market" for e in r["evidence"])
    assert line in copy_lines(r)
    assert "기존 시장 판정" not in r["copy_text"]
    assert ev_by(r, "list_condition")["no"] == 1
    assert r["market_context_snapshot"]["common"]["status"] == "unavailable"


def test_copy_product_missing_constituents_not_collected_and_fee_text():
    info = {"csv": {"name": "x.csv", "asof": "2026-09-27", "ok": True, "error": None}}
    cons = review(SEL, body())["selected_review"]["constituents"]
    nc = {**cons, "state": "not_collected", "top_stocks": [], "top3_sum_pct": None}
    nc["line"] = "구성 자료 없음(미수집) — [구성종목 보기]에서 수집"
    r = review(SEL, body(), official={**info, "items": {}}, cons=None)
    assert ev_by(r, "selected_product")["text"].endswith(
        "· 공식 기준정보에 없음 — 공식 기초지수 · 상품 구조 확인 불가"
    )
    assert T.constituents_text(nc) == (
        "[고른 ETF — 구성] 구성 자료 없음(미수집) — [구성종목 보기]에서 수집"
    )
    part = {**cons, "top_stocks": [{"name": "갑", "weight_pct": None}]}
    part["top3_sum_pct"] = None
    assert T.constituents_text(part).startswith(
        "[고른 ETF — 구성] 주요 편입(주식) 갑 비중 확인 불가 → 상위 1개 합 확인 불가 · "
    )
    for raw, want in [
        ("0.450000", "0.45%"),
        ("0", "0%"),
        ("1.000", "1%"),
        (" ", "확인 불가"),
        (None, "확인 불가"),
        ("abc", "abc"),
        ("NaN", "NaN"),
    ]:
        assert T._fee(raw) == want, raw


def test_copy_answer_format_lines():
    r = review(SEL, body())
    lines = copy_lines(r)
    assert "최신 확인: 같음 | 새 값 있음 | 확인 불가" in lines
    assert (
        "- 항목: … · 값: … · 기준일: … · 출처: … · 확인 시각: … · 달라지는 해석: …"
        in lines
    )
    for t in ("428560", SEL, "453810"):
        i = next(
            n for n, x in enumerate(lines) if x.startswith(f"[ETF {t}] (관련 근거 ")
        )
        assert lines[slice(i + 1, i + 5)] == [
            "상태: 근거 확인 | 추가 확인 | 자료 부족 중 하나",
            "인용 근거: 위 [근거 n] 의 번호만(쉼표로 구분)",
            "이유: 한 문장",
            "다음 확인: 한 가지",
        ]
    assert lines.index("최신 확인: 같음 | 새 값 있음 | 확인 불가") < lines.index(
        "대상 ETF: 428560 · 476070 · 453810"
    )
    # 질문 글의 형식 줄 자체는 답 해석기가 형식 없음으로 읽음(옮겨 붙인 답이 '같음'으로 읽히지 않음)
    assert parse_latest(["같음 | 새 값 있음 | 확인 불가"])["state"] == "형식 없음"
    assert parse_item(T.ITEM_TEMPLATE) is None


# ── 2. ETF 칸 해석 · 대조(V1 문법 규칙 그대로 · V2 칸) ─────────────────────────────


@pytest.fixture
def q():
    return review(SEL, body())["copy_text"]


def test_parse_question_reads_numbers_and_targets(q):
    p = parse_question(q)
    assert p["targets"] == ["428560", "476070", "453810"]
    assert p["valid"] == set(range(1, len(review(SEL, body())["evidence"]) + 1))
    assert parse_question("질문 원문을 고쳐 번호가 없음") is None


def test_compare_same_state_common_and_per_answer_numbers(q):
    gpt = _ans(
        {
            "428560": ("근거 확인", "2, 5", "1위"),
            "476070": ("추가 확인", "6, 9", "30행 밖 보유 구성 미확인", "구성 더 받기"),
            "453810": ("자료 부족", "7", "인도 수급 자료 없음"),
        }
    )
    gemini = _ans(
        {
            "428560": ("근거 확인", "근거 5 · 근거 2", "-"),
            "476070": ("추가 확인", "6, 9, 10", "미확인 몫 먼저"),
            "453810": ("근거 확인 | 추가 확인 | 자료 부족 중 하나", "7", "x"),
        }
    )
    claude = (
        "**최신 확인:** 새 값 있음\n"
        "**[ETF 428560]**\n- **상태:** 근거 확인\n- **인용 근거:** [근거 2], [근거 5]\n"
        "### [ETF 476070] KODEX\n상태: 추가 확인\n인용 근거: 4, 6\n이유: 3개월 흐름 약함\n"
        "ETF 476070 은 3개월이 낮다.\n다음 확인: 3개월 KODEX 대비\n"
    )
    c = compare(
        q, {"gpt": gpt, "gemini": gemini, "claude": claude}, {"428560": "미국ETF"}
    )
    assert c["status"] == "ok"
    rows = {r["ticker"]: r for r in c["rows"]}
    a = rows["428560"]
    assert a["name"] == "미국ETF" and a["ok_count"] == 3
    assert (a["state_same"], a["cited_same"], a["cited_common"]) == (True, True, [2, 5])
    assert (a["state_text"], a["cited_text"]) == (
        "상태 같음(근거 확인)",
        "인용 근거 번호 일치",
    )
    b = rows["476070"]
    assert (b["state_same"], b["cited_same"], b["cited_common"]) == (True, False, [6])
    assert b["cited_only"] == {"gpt": [9], "gemini": [9, 10], "claude": [4]}
    assert b["cited_text"] == "같은 번호 6 · 다른 번호 GPT 9 / Gemini 9, 10 / Claude 4"
    assert b["cells"]["gpt"] == {
        "status": "ok",
        "state": "추가 확인",
        "cited": [6, 9],
        "why": "30행 밖 보유 구성 미확인",
        "next_check": "구성 더 받기",
    }
    # 본문 속 'ETF 476070 은 …' 은 새 칸 머리가 아니라 앞 칸(이유)의 이어진 글
    cl = b["cells"]["claude"]
    assert cl["why"] == "3개월 흐름 약함 ETF 476070 은 3개월이 낮다."
    assert cl["next_check"] == "3개월 KODEX 대비"
    n = rows["453810"]
    assert n["cells"]["gemini"] == {
        "status": "needs_check",
        "reason": "상태를 셋 중 하나로 읽을 수 없음",
    }
    assert n["cells"]["claude"] == {
        "status": "needs_check",
        "reason": "이 ETF 칸이 없음",
    }
    assert (n["ok_count"], n["state_text"], n["cited_text"]) == (1, "한 의견", None)
    assert c["latest_text"] == "GPT 같음 · Gemini 같음 · Claude 새 값 있음"
    assert (c["answer_count"], c["opinion_text"]) == (3, "AI 답 3개")


def test_compare_state_differs_and_bad_numbers(q):
    gpt = _ans({"428560": ("근거 확인", "2", "-")})
    gemini = _ans({"428560": ("추가 확인", "5", "-")})
    claude = _ans({"428560": ("추가 확인", "999", "-")})
    a = compare(q, {"gpt": gpt, "gemini": gemini, "claude": claude}, {})["rows"][0]
    assert a["cells"]["claude"] == {
        "status": "needs_check",
        "reason": "인용 근거 번호 확인 불가",
    }
    assert a["state_same"] is False
    assert a["state_text"] == "상태 다름(근거 확인 1 · 추가 확인 1)"
    assert a["cited_text"] == "같은 번호 없음 · 다른 번호 GPT 2 / Gemini 5"
    assert a["cited_common"] == []


def test_compare_template_echo_and_empty_answers(q):
    echo = "\n".join(
        [
            "최신 확인: 같음 | 새 값 있음 | 확인 불가",
            "- 항목: … · 값: … · 기준일: … · 출처: … · 확인 시각: … · 달라지는 해석: …",
            "[ETF 428560]",
            "상태: 근거 확인 | 추가 확인 | 자료 부족 중 하나",
            "인용 근거: 위 [근거 n] 의 번호만(쉼표로 구분)",
        ]
    )
    c = compare(q, {"gpt": echo, "gemini": "", "claude": "  "}, {})
    a = c["rows"][0]
    assert a["cells"]["gpt"]["status"] == "needs_check"
    assert a["cells"]["gemini"] == {"status": "no_answer"} == a["cells"]["claude"]
    # 못 읽은 답만 있으면 '요약 확인 필요'(답 없음과 구별) · 모두 비면 '대조할 답 없음'
    assert (a["ok_count"], a["state_text"]) == (0, "요약 확인 필요")
    assert c["answers"]["gpt"] == {
        "status": "ok",
        "latest": {
            "state": "형식 없음",
            "raw": "같음 | 새 값 있음 | 확인 불가",
            "reason": "같음 · 새 값 있음 · 확인 불가 중 하나로 읽을 수 없음",
        },
        "items": [],
    }
    assert c["answers"]["gemini"] == {"status": "no_answer"}
    assert c["opinion_text"] == "한 의견" and c["latest_text"] == "GPT 형식 없음"
    none = compare(q, {"gpt": "", "gemini": "", "claude": ""}, {})
    assert none["rows"][0]["state_text"] == "대조할 답 없음"
    assert (none["opinion_text"], none["latest_text"]) == ("AI 답 없음", None)


def test_compare_question_edited_is_no_format_but_answers_still_read():
    ans = _ans({"428560": ("근거 확인", "2", "-")}, latest="새 값 있음")
    c = compare("고친 질문", {"gpt": ans}, {})
    assert c["status"] == "no_format" and c["rows"] == []
    assert "요약 확인 필요" in c["message"]
    assert c["answers"]["gpt"]["latest"]["state"] == "새 값 있음"


def test_why_and_next_check_are_shortened_but_kept(q):
    long = "가" * 300
    c = compare(q, {"gpt": _ans({"428560": ("근거 확인", "2", long, long)})}, {})
    cell = c["rows"][0]["cells"]["gpt"]
    for k in ("why", "next_check"):
        assert len(cell[k]) == 140 and cell[k].endswith("…")


def test_last_record_view_none_and_blank_fields():
    assert last_record_view(None) == NONE_LAST
    v = last_record_view(
        {
            "id": "x",
            "created_at": "2026-11-17T21:05:00.000000+0900",
            "asof": "2026-11-16",
            "user_verdict": "unrecorded",
            "user_memo": "  ",
            "next_checks": ["", " ", "구성 확인"],
            "candidate_snapshot": [{"ticker": "428560", "name": "미국ETF"}],
            "question_text": "",
        }
    )
    assert (v["memo"], v["next_checks"], v["verdict"]) == (
        None,
        ["구성 확인"],
        "unrecorded",
    )
    assert v["compare"]["status"] == "no_format"
    # 고른 후보 칸이 없는 기록 = '모름'(고르지 않음으로 바꾸지 않음) · 답 0개
    assert (v["selected"], v["answer_count"]) == ({"status": "unknown"}, 0)


@pytest.mark.parametrize(
    "dq, want",
    [
        (
            {"selected": {"ticker": "476070", "name": "KODEX 비만", "rank": 2}},
            {"status": "ok", "ticker": "476070", "name": "KODEX 비만"},
        ),
        ({"selected": None}, {"status": "none"}),
        ({}, {"status": "unknown"}),
        ({"selected": {"name": "코드 없음"}}, {"status": "unknown"}),
        (["모양이 다름"], {"status": "unknown"}),
    ],
)
def test_last_record_view_selected_and_answer_count(dq, want):
    """검토 F4(⑤ 목업) — 고른 후보 = 저장한 data_quality_snapshot.selected(코드 · 이름) · AI 답 수 = 빈 답 제외."""
    rec = {
        "id": "x",
        "created_at": "2026-11-17T21:05:00.000000+0900",
        "asof": "2026-11-16",
        "user_verdict": "hold",
        "user_memo": "",
        "next_checks": [],
        "candidate_snapshot": [],
        "question_text": "",
        "gpt_answer_text": "답",
        "gemini_answer_text": "  ",
        "claude_answer_text": "답",
        "data_quality_snapshot": dq,
    }
    v = last_record_view(rec)
    assert v["selected"] == want and v["answer_count"] == 2
    assert NONE_LAST["message"] == "이 화면에서 저장한 기록 없음"


@pytest.mark.parametrize(
    "head",
    [
        "[ETF 476070] KODEX 글로벌비만치료제TOP2 Plus",
        "[ETF 476070 KODEX 글로벌비만치료제TOP2 Plus]",
        "### ETF 476070 — KODEX 글로벌비만치료제TOP2 Plus",
        "ETF 476070:",
        "【ETF 476070】",
        "1. [ETF 476070]",
        "**[ETF 476070]**",
    ],
)
def test_compare_reads_named_and_markdown_heads_without_mixing(q, head):
    ans = "\n".join(
        [
            "[ETF 428560]",
            "상태: 근거 확인",
            "인용 근거: 2, 5",
            head,
            "상태: 자료 부족",
            "인용 근거: 6, 9",
        ]
    )
    rows = {r["ticker"]: r for r in compare(q, {"gpt": ans}, {})["rows"]}
    assert rows["428560"]["cells"]["gpt"]["cited"] == [2, 5]
    assert rows["428560"]["cells"]["gpt"]["state"] == "근거 확인"
    assert rows["476070"]["cells"]["gpt"]["cited"] == [6, 9]
    assert rows["476070"]["cells"]["gpt"]["state"] == "자료 부족"


def test_compare_unreadable_head_or_duplicate_block_is_needs_check(q):
    mixed = "[ETF 428560]\n상태: 근거 확인\n인용 근거: 2\n**476070 KODEX**\n상태: 자료 부족\n인용 근거: 6"
    rows = {r["ticker"]: r for r in compare(q, {"gpt": mixed}, {})["rows"]}
    assert rows["428560"]["cells"]["gpt"] == {
        "status": "needs_check",
        "reason": "'상태' 칸이 두 번 나옴(다른 ETF 칸 머리를 읽지 못했을 수 있음)",
    }
    assert rows["476070"]["cells"]["gpt"]["reason"] == "이 ETF 칸이 없음"
    dup = "\n".join(
        [
            "[ETF 428560]",
            "상태: 근거 확인",
            "인용 근거: 2",
            "[ETF 476070]",
            "상태: 추가 확인",
            "인용 근거: 6",
            "[ETF 428560]",
            "상태: 자료 부족",
            "인용 근거: 5",
        ]
    )
    rows = {r["ticker"]: r for r in compare(q, {"gpt": dup}, {})["rows"]}
    assert rows["428560"]["cells"]["gpt"]["reason"] == "같은 ETF 칸이 두 번 나옴"
    assert rows["476070"]["cells"]["gpt"]["cited"] == [6]


@pytest.mark.parametrize(
    "value, want",
    [
        ("2, 5", [2, 5]),
        ("[근거 2] · [근거 5]", [2, 5]),
        ("근거 5, 근거 2", [2, 5]),
        ("2번, 5번", [2, 5]),
        ("1 ~ 4, 9", [1, 2, 3, 4, 9]),
        ("9~12", [9, 10, 11, 12]),
        ("2 5", [2, 5]),
        ("6(3개월), 9", None),
        ("근거 4(6개월 해석), 9", None),
        ("위 [근거 n] 의 번호만(쉼표로 구분)", None),
        ("", None),
        ("5 ~ 2", None),
    ],
)
def test_parse_cited_grammar(value, want):
    assert parse_cited(value) == want


def test_compare_range_notation_is_same_set(q):
    a = _ans({"428560": ("근거 확인", "1 ~ 4, 5", "-")})
    b = _ans({"428560": ("근거 확인", "1, 2, 3, 4, 5", "-")})
    c = _ans({"428560": ("근거 확인", "1, 5", "-")})
    r = compare(q, {"gpt": a, "gemini": b}, {})["rows"][0]
    assert r["cited_text"] == "인용 근거 번호 일치"
    r = compare(q, {"gpt": a, "gemini": c}, {})["rows"][0]
    assert r["cited_text"] == "같은 번호 1, 5 · 다른 번호 GPT 2, 3, 4"
    bad = _ans({"428560": ("근거 확인", "6(3개월), 9", "-")})
    cell = compare(q, {"gpt": bad}, {})["rows"][0]["cells"]["gpt"]
    assert cell["status"] == "needs_check"


# ── 3. 최신 확인 · 확인 항목 줄(I-15 · Q5) ────────────────────────────────────────


@pytest.mark.parametrize(
    "values, state, reason",
    [
        (["같음"], "같음", None),
        (["같음(저장값과 같음)"], "같음", None),
        (["새 값 있음(같은 날짜 정정)"], "새 값 있음", None),
        (["새값 있음"], "새 값 있음", None),
        (["최신 자료 확인 불가"], "확인 불가", None),
        (["확인불가"], "확인 불가", None),
        (["같음 | 새 값 있음 | 확인 불가"], "형식 없음", "중 하나로 읽을 수 없음"),
        (["모름"], "형식 없음", "중 하나로 읽을 수 없음"),
        ([], "형식 없음", "최신 확인 줄 없음"),
        (["같음", "같음"], "형식 없음", "최신 확인 줄이 두 번 이상 나옴"),
    ],
)
def test_parse_latest_table(values, state, reason):
    got = parse_latest(values)
    assert got["state"] == state
    assert (got["reason"] is None) if reason is None else (reason in got["reason"])


def test_latest_line_anywhere_with_markdown_never_joins_a_field(q):
    ans = "\n".join(
        [
            "[ETF 428560]",
            "상태: 근거 확인",
            "인용 근거: 2",
            "이유: 1위",
            "**최신 확인:** 확인 불가",
            "- 항목: 코스피 종가 · 값: 5,190.00 · 기준일: 2026-11-16 · 출처: KRX · 확인 시각: 10:05",
            "이 줄은 어느 칸에도 붙지 않음",
        ]
    )
    c = compare(q, {"claude": ans}, {})
    assert c["answers"]["claude"]["latest"]["state"] == "확인 불가"
    assert [i["item"] for i in c["answers"]["claude"]["items"]] == ["코스피 종가"]
    assert c["rows"][0]["cells"]["claude"]["why"] == "1위"
    # 항목 줄 하나만 끼어도 그 뒤 글은 앞 칸(이유)에 붙지 않음
    only_item = "\n".join(
        ["[ETF 428560]", "상태: 근거 확인", "인용 근거: 2", "이유: 1위"]
        + ["- 항목: VIX · 값: 19.30", "이 줄도 붙지 않음"]
    )
    cell = compare(q, {"gpt": only_item}, {})["rows"][0]["cells"]["gpt"]
    assert cell["why"] == "1위"


@pytest.mark.parametrize(
    "line, want",
    [
        (
            "- 항목: 코스피 종가 · 값: 5,290.53 · 기준일: 2026-11-16 · "
            "출처: https://data.krx.co.kr/a_b?x=1 · 확인 시각: 2026-11-17 10:05 KST · "
            "달라지는 해석: 코스피 방향",
            {
                "item": "코스피 종가",
                "value": "5,290.53",
                "basis_date": "2026-11-16",
                "source": "https://data.krx.co.kr/a_b?x=1",
                "checked_at": "2026-11-17 10:05 KST",
                "changes": "코스피 방향",
                "checked_at_text": "2026-11-17 10:05 KST",
            },
        ),
        (
            # 값 속 ' · ' — 칸 위치로 나누면 확인 시각을 잘못 읽음(I-15 · 이름 붙은 칸으로 읽음)
            "1. **항목:** 외국인 20거래일 · 값: 순매도 6,060억원 · 일평균 303억원 · "
            "기준일: 10/19 ~ 11/13 · 출처: KRX · 확인 시각: 11/17 09:30 · 달라지는 해석: 없음",
            {
                "item": "외국인 20거래일",
                "value": "순매도 6,060억원 · 일평균 303억원",
                "basis_date": "10/19 ~ 11/13",
                "source": "KRX",
                "checked_at": "11/17 09:30",
                "changes": "없음",
                "checked_at_text": "11/17 09:30",
            },
        ),
        (
            "- 항목: VIX · 값: 19.30 · 기준일: 11/13 · 출처: CBOE · 확인 시각:  · 달라지는 해석: 없음",
            {"checked_at": None, "checked_at_text": NO_TIME, "source": "CBOE"},
        ),
        (
            "- 항목: VIX · 값: 19.30 · 확인 시각: — · 달라지는 해석: 저장 값: 19.30 과 같음",
            {
                "checked_at": None,
                "checked_at_text": NO_TIME,
                "changes": "저장 값: 19.30 과 같음",
                "basis_date": None,
            },
        ),
        (
            "- 항목: WTI · 값: 88.56",
            {"value": "88.56", "checked_at": None, "checked_at_text": NO_TIME},
        ),
        (
            # 낱말 속 '값:'(저장값:)은 칸 이름이 아님 — 칸 이름은 줄 처음이나 구분 글자 뒤에서만
            "- 항목: 코스피 종가(저장값: 5,184.00) · 값: 5,190.00 · 출처: KRX",
            {"item": "코스피 종가(저장값: 5,184.00)", "value": "5,190.00"},
        ),
        (
            "- 항목: … · 값: … · 기준일: … · 출처: … · 확인 시각: … · 달라지는 해석: …",
            None,
        ),
        ("- 항목:  · 값: 1", None),
    ],
)
def test_parse_item_named_fields_table(line, want):
    got = parse_item(line)
    if want is None:
        assert got is None
        return
    assert got["line"] == line.strip()  # 원문 그대로
    for k, v in want.items():
        assert got[k] == v, k


def test_one_opinion_and_answers_view_in_saved_record(q):
    c = compare(q, {"gpt": _ans({"428560": ("근거 확인", "2", "-")})}, {})
    assert (c["answer_count"], c["opinion_text"], c["latest_text"]) == (
        1,
        "한 의견",
        "GPT 같음",
    )
    assert c["rows"][0]["state_text"] == "한 의견"
    assert c["answers"]["gemini"] == c["answers"]["claude"] == {"status": "no_answer"}


# ── 4. 경로 · 응답 칸 · 저장 → 갱신 → 다시 열기(AC3) ──────────────────────────────


def test_route_reads_common_evidence_with_same_now_only_when_list_ok(
    client,  # noqa: F811 — fixture
    monkeypatch,
):
    r = client.get("/weekly/etf-check", params={"selected": SEL}).json()
    (kw,) = client.calls["mev"]
    assert kw["now"].isoformat(timespec="seconds") == r["generated_at"]
    assert r["market_evidence"] == wr.common_snapshot(mev())
    assert r["market_context_snapshot"]["common"] == r["market_evidence"]
    assert "daily_text" not in r["market_evidence"]
    assert r["data_quality_snapshot"]["evidence_list"] == r["evidence"]
    monkeypatch.setattr(
        W, "build_summary", lambda **kw: {"status": "empty", "message": "목록 없음"}
    )
    bad = client.get("/weekly/etf-check").json()
    assert bad["status"] == "empty" and len(client.calls["mev"]) == 1


def test_save_then_refresh_then_reopen_keeps_what_was_sent(
    client,  # noqa: F811 — fixture
    monkeypatch,
):
    """AC3 — 저장한 검토는 갱신 뒤에도 당시 근거 · 인용 · AI 확인을 그대로(이후 관측값으로 덮어쓰지 않음)."""
    r = client.get("/weekly/etf-check", params={"selected": SEL}).json()
    ans = saved_answers(r)
    over = {f"{k}_answer_text": v for k, v in ans.items()}
    saved = client.post(
        "/decision/sessions", json=_draft(r, user_verdict="hold", **over)
    ).json()
    later = mev()
    later["evidence_items"][0]["text"] = "[시장 판정] 갱신 뒤 다른 값"
    monkeypatch.setattr(ME, "build_market_evidence", lambda **kw: copy.deepcopy(later))
    r2 = client.get("/weekly/etf-check", params={"selected": SEL}).json()
    assert r2["evidence"][0]["text"] == "[시장 판정] 갱신 뒤 다른 값"
    rec = client.get(f"/decision/sessions/{saved['id']}").json()["record"]
    assert rec["question_text"] == r["copy_text"]
    assert rec["market_context_snapshot"]["common"] == r["market_evidence"]
    assert rec["data_quality_snapshot"]["evidence_list"] == r["evidence"]
    assert rec["user_verdict"] == "hold"  # 직접 고른 보류(미기록과 구별)
    last = r2["last_record"]
    names = {c["ticker"]: c["name"] for c in r["candidate_snapshot"]}
    assert last["id"] == saved["id"]
    assert last["compare"] == compare(r["copy_text"], ans, names)
    claude = last["compare"]["answers"]["claude"]
    assert claude["latest"]["state"] == "새 값 있음"
    assert claude["items"][0]["checked_at_text"] == "확인 시각 미기재"
    row = next(x for x in last["compare"]["rows"] if x["ticker"] == SEL)
    assert row["cited_common"] == [ev_by(r, "flow_2")["no"]]
    assert nos(r, "overlap_1") in row["cited_text"]


# ── 5. [판단 근거 보기] — 주간 화면 key(후보만 · 고정 조건만) ───────────────────────


def _weekly_pick(**over: Any) -> CommonPeriodPick:
    base = dict(
        screen=WEEKLY_SCREEN,
        basis="one_month",
        filters=dict(wr.FILTERS),
        side="top",
        rank=2,
        start_date="2026-10-19",
        end_date="2026-11-16",
        end_price_state="after_close",
    )
    base.update(over)
    return CommonPeriodPick(**base)


def test_weekly_pick_valid_only_with_its_fixed_condition():
    assert WEEKLY_SCREEN == "today_weekly_review" == wr.SOURCE_SCREEN
    assert _weekly_pick().is_valid()
    assert list_label(_weekly_pick()) == (
        "「주간 ETF 점검」 1개월 상위 2위 · 공통 기간 10/19 → 11/16"
    )
    assert not _weekly_pick(basis="three_month").is_valid()
    assert not _weekly_pick(side="bottom").is_valid()
    for k in wr.FILTERS:
        assert not _weekly_pick(filters={**wr.FILTERS, k: False}).is_valid(), k
    # 다른 화면은 지금처럼(조건 고정 없음) · 보유 미리보기 화면 목록에는 주간 key 없음
    assert _weekly_pick(screen="candidate_list", side="bottom").is_valid()
    assert WEEKLY_SCREEN in PICK_SCREEN_LABEL and WEEKLY_SCREEN not in SCREEN_LABEL


def test_weekly_screen_preview_uses_common_period_list(
    seeded: TestClient,  # noqa: F811 — fixture
) -> None:
    s = _summary(seeded, "one_month")
    row = s["top"][1]
    body_ = {
        **_pick(row, "top", "one_month", screen=WEEKLY_SCREEN),
        "basis_value": row["basis_return"]["value"],
    }
    out = _post(seeded, body_)
    assert out["status"] == "ok", out
    br = row["basis_return"]
    md = lambda d: f"{int(d[5:7])}/{int(d[8:10])}"  # noqa: E731
    assert _target_line(out["preview_text"]).endswith(
        f"「주간 ETF 점검」 1개월 상위 2위 · 공통 기간 {md(br['start'])} → {md(br['end'])}"
    )
    # 같은 목록 대조 가드 그대로 — 순위가 다르면 '목록이 바뀌었습니다'
    moved = _post(seeded, {**body_, "rank": 3})
    assert moved["status"] == "error" and moved["message"] == CHANGED


@pytest.mark.parametrize(
    "change",
    [{"side": "bottom"}, {"exclude_inverse": False}, {"exclude_futures": False}],
)
def test_weekly_screen_other_condition_is_general_failure(
    seeded: TestClient,  # noqa: F811 — fixture
    change: dict[str, Any],
) -> None:
    s = _summary(seeded, "one_month")
    out = _post(
        seeded, {**_pick(s["top"][0], "top", "one_month", WEEKLY_SCREEN), **change}
    )
    assert out["status"] == "error" and out["message"] == FAILURE


def test_weekly_screen_three_month_basis_is_general_failure(
    seeded: TestClient,  # noqa: F811 — fixture
) -> None:
    s = _summary(seeded, "three_month")
    out = _post(seeded, _pick(s["top"][0], "top", "three_month", WEEKLY_SCREEN))
    assert out["status"] == "error" and out["message"] == FAILURE


def test_weekly_screen_is_not_a_holding_preview_screen(
    seeded: TestClient,  # noqa: F811 — fixture
) -> None:
    out = _post(seeded, _holding(WEEKLY_SCREEN, "one_month"))
    assert out["status"] == "error" and out["message"] == FAILURE


def test_fixture_rows_carry_what_the_preview_compares():
    """화면이 [판단 근거 보기] 요청을 만들 칸 = 흐름 구성원 1개월 값 · 기간 · 끝일 가격 상태 = 목록 행 대조 칸."""
    r = review(SEL, body())
    m = next(x for f in r["flows"] for x in f["members"] if x["ticker"] == SEL)
    row = next(x for x in FIX["summary"]["top"] if x["ticker"] == SEL)
    br = row["basis_return"]
    assert m["one_month"] == br["value"]
    assert (m["periods"]["one_month"]["start"], m["periods"]["one_month"]["end"]) == (
        br["start"],
        br["end"],
    )
    assert m["end_price"]["state"] == row["end_price"]["state"]
