"""POC7-04 화면 스크립트(브라우저 동작) — 실제 서버가 만든 화면 HTML 을 jsdom 에서 돌린다.

node · frontend/node_modules/jsdom 필요.

AI 답의 질문 출처 · 복사 기록 · 초안(이 창 · 예전 형식) · 저장 상태 · 저장 결과 문구(tmp DB · tmp 저장 폴더만 · 라이브 DB 안 엶).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

import pytest

from app.weekly_decision import page_saved as PS
from app.weekly_decision import server as SV
from app.weekly_decision import store as ST
from tests._poc7_04_support import (
    END,
    REPO,
    _app,
    _bid,
    _bump,
    make_market,
)


@pytest.fixture
def market(tmp_path: Path) -> Path:
    return make_market(tmp_path)


NODE = shutil.which("node")
JSDOM = REPO / "frontend" / "node_modules" / "jsdom"
HARNESS = Path(__file__).with_name("_poc7_04_page_events.cjs")
KEY = "poc7_04_draft_AAA001"  # 이 창(sessionStorage) 초안 키 · 예전 방식(localStorage)도 같은 이름 + '__창'
CLIP = "poc7_04_clip"


def _browser(
    tmp_path: Path,
    pages: Any,
    steps: list,
    *,
    seed: Optional[dict] = None,
    session_seed: Optional[dict] = None,
    clipboard: str = "ok",
    storage_fail: bool = False,
    session_fail: bool = False,
    session_quota: int = 0,
    session_fail_keys: Optional[list] = None,
) -> dict[str, Any]:
    """실제 화면 HTML 의 스크립트를 jsdom 에서 돌린다(node · frontend/node_modules/jsdom 필요)."""
    if NODE is None or not (JSDOM / "package.json").is_file():
        pytest.skip(
            "node · jsdom(frontend/node_modules) 없음 — 화면 스크립트 시험 건너뜀"
        )
    if isinstance(pages, str):
        pages = [(pages, "AAA001")]
    run = tmp_path / f"run_{len(list(tmp_path.glob('run_*')))}"
    run.mkdir()
    files = []
    for i, (html, ticker) in enumerate(pages):
        f = run / f"page_{i}.html"
        f.write_text(html, encoding="utf-8")
        files.append({"html": str(f), "ticker": ticker})
    scenario = run / "scenario.json"
    scenario.write_text(
        json.dumps(
            {
                "pages": files,
                "seed": seed or {},
                "session_seed": session_seed or {},
                "clipboard": clipboard,
                "storage_fail": storage_fail,
                "session_fail": session_fail,
                "session_quota": session_quota,
                "session_fail_keys": session_fail_keys or [],
                "steps": steps,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    r = subprocess.run(
        [NODE, str(HARNESS), str(JSDOM), str(scenario)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _draft_of(out: dict[str, Any], tab: int = 0) -> Optional[dict[str, Any]]:
    """그 창 저장소의 이 ETF 초안(없으면 None)."""
    raw = out["tabs"][tab]["session"].get(KEY)
    return json.loads(raw) if raw else None


def _legacy(out: dict[str, Any]) -> list[str]:
    return [k for k in out["storage"] if k == KEY or k.startswith(KEY + "__")]


def _draft(
    answer_from: Optional[str],
    answer: str = "답A",
    sig: Optional[str] = None,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "draft_v": 4,
        "at": 1,
        "verdict": "hold",
        "reason": "",
        "next_check": "",
        "used": [],
        "ai_name": "GPT",
        "ai_answer": answer,
        "ai_excerpt": "",
        "ai_pasted_at": "2026-11-24T01:00:00.000Z",
        "answer_from": answer_from,
        "answer_sig": sig,
        "end": END,
        **extra,
    }


def _gpt(body: dict[str, Any]) -> dict[str, Any]:
    """보낸 본문의 GPT 칸(답 하나 시절 시험을 칸 세 개 계약에서 그대로 쓰려고 평평하게)."""
    a = next(x for x in body["ais"] if x["name"] == "GPT")
    return {
        "answer_from": a["answer_from"],
        "answer_sig": a["answer_sig"],
        "answer_copied_at": a["answer_copied_at"],
        "ai_pasted_at": a["pasted_at"],
        "ai_answer": a["answer"],
        "helpful": a["helpful"],
    }


def _asked(doc: dict[str, Any], name: str = "GPT") -> dict[str, Any]:
    """저장 기록에서 그 칸의 질문 출처 — 답을 넣지 않은 칸은 기록에 없음('no_answer')."""
    a = next((x for x in doc["decision"]["ais"] if x["name"] == name), None)
    return a["asked"] if a else {"state": "no_answer"}


COPY = {"do": "copy"}
SAVE = {"do": "save"}
UNKNOWN_ID = "20261124T000000Z_99999999"


def _ans(value: str, how: str) -> dict[str, Any]:
    return {"do": "field", "id": "answer_gpt", "value": value, "how": how}


def _undo(value: str) -> dict[str, Any]:
    return {"do": "undo", "value": value}


# (이름, 초안: None · "A"(근거가 다른 화면) · "A1"(같은 글 화면) · "R"(서버가 모르는 화면 · 같은 질문 지문) · "old"(예전 초안),
#  클립보드, 단계, 보낸 출처, 서버 판정)
PROVENANCE = [
    (
        "새 화면 복사 뒤 붙임",
        None,
        "ok",
        [COPY, _ans("답B", "paste")],
        "B",
        "this_screen",
    ),
    (
        "빈 칸에 타자로 새 답",
        None,
        "ok",
        [COPY, _ans("답B", "type")],
        "B",
        "this_screen",
    ),
    (
        "빈 칸에 끌어 놓기",
        None,
        "ok",
        [COPY, {"do": "drop", "value": "답B"}],
        "B",
        "this_screen",
    ),
    (
        "아무것도 안 들어간 끌어 놓기 뒤 타자",
        None,
        "ok",
        [
            COPY,
            _ans("답B", "paste"),
            {"do": "drop", "value": ""},
            _ans("답B 고침", "type"),
        ],
        "B",
        "this_screen",
    ),
    ("되살린 답 · 새 질문 복사만", "A", "ok", [COPY], "A", "other_screen"),
    ("되살린 답 · 복사 실패(선택만)", "A", "fail", [COPY], "A", "other_screen"),
    (
        "복사 실패 · 직접 복사 뒤 바꿔 붙임",
        "A",
        "fail",
        [COPY, {"do": "manual_copy"}, _ans("답B", "paste_all")],
        "B",
        "this_screen",
    ),
    (
        "복사 실패 · 직접 복사 없이 바꿔 붙임",
        "A",
        "fail",
        [COPY, _ans("답B", "paste_all")],
        None,
        "no_copy_record",
    ),
    (
        "질문 일부만 복사",
        None,
        "fail",
        [{"do": "select_part"}, {"do": "manual_copy"}, _ans("답B", "paste")],
        "mixed",
        "mixed",
    ),
    (
        "되살린 답에 새 답 덧붙임",
        "A",
        "ok",
        [COPY, _ans(" 추가답", "paste")],
        "mixed",
        "mixed",
    ),
    (
        "되살린 답에 다른 글 끌어 놓기",
        "A",
        "ok",
        [COPY, {"do": "drop", "value": " 끌어온 글"}],
        "mixed",
        "mixed",
    ),
    (
        "되살린 답 · 새 질문 복사 뒤 타자 고침",
        "A",
        "ok",
        [COPY, _ans("답A 고침", "type")],
        "A",
        "other_screen",
    ),
    ("되살린 답을 지움", "A", "ok", [COPY, _ans("", "type")], None, "no_answer"),
    ("예전 초안(마지막 복사 칸)", "old", "ok", [], None, "no_copy_record"),
    # r4 F13 — 되살린 예전 형식 초안의 답에 다른 질문의 답을 덧붙이면 '하나로 정할 수 없음'
    (
        "예전 형식 초안 답에 새 답 덧붙임",
        "LA",
        "ok",
        [COPY, _ans(" 추가답", "paste")],
        "mixed",
        "mixed",
    ),
    ("다시 연 같은 화면 초안", "A1", "ok", [], "A1", "same_copy"),
    ("서버를 다시 켠 뒤 같은 질문", "R", "ok", [], "R", "same_copy"),
    (
        "전체 바꿔 붙인 뒤 되돌리기",
        "A",
        "ok",
        [COPY, _ans("엉뚱한 글", "paste_all"), _undo("답A")],
        "mixed",
        "mixed",
    ),
    (
        "지운 뒤 되돌리기",
        "A",
        "ok",
        [COPY, _ans("", "type"), _undo("답A")],
        "mixed",
        "mixed",
    ),
    # r3 F9 — 같은 글이 서로 다른 질문의 답으로 있었으면 되돌려도 '하나로 정할 수 없음'
    (
        "같은 글이 두 출처로 있은 뒤 되돌리기",
        "A",
        "ok",
        [
            _ans("답A 이유", "type"),
            COPY,
            _ans("답A", "paste_all"),
            _undo("답A 이유"),
            _undo("답A"),
        ],
        "mixed",
        "mixed",
    ),
    (
        "처음 보는 값으로 되돌리기",
        None,
        "ok",
        [COPY, _ans("답B", "paste"), _undo("처음 보는 글")],
        "mixed",
        "mixed",
    ),
    # 검증자 r2 F6① — 새 질문을 복사한 뒤 붙인 답은 예전 답과 같은 글이어도 새 질문의 답
    (
        "새 질문 복사 뒤 같은 글로 바꿔 붙임",
        "A",
        "ok",
        [COPY, _ans("답A", "paste_all")],
        "B",
        "this_screen",
    ),
    (
        "새 질문 복사 뒤 지우고 같은 글 붙임",
        "A",
        "ok",
        [COPY, _ans("", "type"), _ans("답A", "paste")],
        "B",
        "this_screen",
    ),
    # 잘라낸 답 칸 글은 이 페이지의 다른 글 복사 — 다시 붙이면 '하나로 정할 수 없음'(보수 쪽)
    (
        "잘라낸 뒤 다시 붙이기",
        "A",
        "ok",
        [COPY, {"do": "cut_answer"}, _ans("답A", "paste")],
        "mixed",
        "mixed",
    ),
    (
        "답 칸 글을 복사한 뒤 새 글 붙임",
        None,
        "ok",
        [
            COPY,
            _ans("답B", "paste"),
            {"do": "copy_answer"},
            _ans("", "type"),
            _ans("답C", "paste"),
        ],
        "mixed",
        "mixed",
    ),
    (
        "질문이 선택된 채 답 칸 글 복사 뒤 새 글",
        None,
        "fail",
        [
            COPY,
            {"do": "manual_copy"},
            _ans("답B", "paste"),
            {"do": "copy_answer"},
            _ans("", "type"),
            _ans("답C", "paste"),
        ],
        "mixed",
        "mixed",
    ),
]


@pytest.mark.parametrize(
    "name,draft_from,clip,steps,sent,state",
    PROVENANCE,
    ids=[c[0] for c in PROVENANCE],
)
def test_browser_answer_provenance(
    market: Path, tmp_path: Path, name, draft_from, clip, steps, sent, state
) -> None:
    """F2 · H1 · r2 F6① — 보내는 출처 = 답을 붙일 때의 복사 · 되돌리기 · 다시 실행만 예전 값의 출처."""
    app = _app(market, tmp_path)
    a = _bid(app.page("AAA001"))
    if draft_from not in ("A1", "R"):
        _bump(market)  # A 화면과 근거 · 복사문이 달라짐
    html = app.page("AAA001")
    b = _bid(html)
    sig_a = SV.copy_sig(app.builds[a]["copy"])
    sig_b = SV.copy_sig(app.builds[b]["copy"])
    ids = {
        "A": a,
        "A1": a,
        "LA": a,
        "R": UNKNOWN_ID,
        "B": b,
        None: None,
        "mixed": "mixed",
    }
    seed: dict[str, Any] = {}
    session: dict[str, Any] = {}
    if draft_from in (
        "old",
        "LA",
    ):  # 이 창 번호(old)의 예전 형식 초안 — 화면을 열 때 되살림
        session["poc7_04_tab"] = "old"
        if draft_from == "old":
            old = {
                k: v
                for k, v in _draft(None).items()
                if k not in ("draft_v", "answer_from", "answer_sig")
            }
            seed[KEY + "__old"] = {**old, "copied_build": b}
        else:
            seed[KEY + "__old"] = _draft(a, sig=sig_a, draft_v=3)
    elif draft_from is not None:
        sig = sig_b if draft_from == "R" else sig_a
        session[KEY] = _draft(ids[draft_from], sig=sig)
    out = _browser(
        tmp_path, html, steps + [SAVE], seed=seed, session_seed=session, clipboard=clip
    )
    post = out["posts"][0]["body"]
    assert _gpt(post)["answer_from"] == ids[sent], name
    if sent == "B":
        assert _gpt(post)["answer_sig"] == sig_b  # 화면 스크립트 지문 = 서버 copy_sig
    code, saved = app.save(post)
    assert code == 200
    doc = ST.load(app.root, saved["review_id"])
    asked = _asked(doc)
    assert asked["state"] == state, name
    if state == "other_screen":
        assert asked["copy"] == app.builds[a]["copy"]
    if draft_from is not None:
        restored = _browser(tmp_path, html, [], seed=seed, session_seed=session)
        text = restored["tabs"][0]["savemsg"]
        if draft_from in ("A1", "R"):
            assert "이 화면과 같은 질문의 답입니다" in text
        else:
            assert "이 화면 질문의 답으로 기록되지 않습니다" in text


def test_browser_copy_record_newest_wins(market: Path, tmp_path: Path) -> None:
    """r2 F6② · 반박 LOW7 — 이 창의 새 복사가 예전 공유 기록보다 앞선다 · 공유 기록을 못 쓴 복사는 '하나로 정할 수 없음'."""
    app = _app(market, tmp_path)
    a = _bid(app.page("AAA001"))
    _bump(market)
    html = app.page("AAA001")
    b = _bid(html)
    old_clip = {"from": a, "sig": SV.copy_sig(app.builds[a]["copy"]), "at": 1}
    # 공유 기록이 쓰이면 새 복사(이 창 · 공유 모두 새것)
    out = _browser(
        tmp_path, html, [COPY, _ans("답B", "paste"), SAVE], seed={CLIP: old_clip}
    )
    post = out["posts"][0]["body"]
    assert _gpt(post)["answer_from"] == b and _gpt(post)["answer_copied_at"]
    # 공유 기록을 못 쓰면 그 기록을 지우고(다른 창 = '복사 기록 없음') 이 창에 붙인 답은 'mixed'
    for steps in (
        [COPY, _ans("답B", "paste"), SAVE],
        [COPY, {"do": "reload"}, _ans("답B", "paste"), SAVE],  # 새로 고친 뒤에도
    ):
        out = _browser(tmp_path, html, steps, seed={CLIP: old_clip}, storage_fail=True)
        assert _gpt(out["posts"][0]["body"])["answer_from"] == "mixed"
        assert CLIP not in out["storage"]
    out = _browser(tmp_path, html, [COPY], storage_fail=True)
    msg = out["tabs"][0]["copymsg"]
    assert "이 창에 붙인 답의 질문은 '하나로 정할 수 없음'으로 남습니다" in msg
    assert "다른 창에 붙인 답의 질문도" not in msg


def test_browser_unwritable_copy_does_not_mislead_other_windows(
    market: Path, tmp_path: Path
) -> None:
    """반박 R3-2 · R3-5 · R3-6 — 공유 기록에 못 쓴 복사 · 다시 열기 화면 복사가 다른 창 답의 출처를 틀리게 하지 않는다."""
    app = _app(market, tmp_path)
    x = app.page("AAA001")
    y = app.page("AAA002")
    pages = [(x, "AAA001"), (y, "AAA002")]
    tab1_copied = [{"do": "open", "tab": 1, "page": 1}, {"do": "copy", "tab": 1}]
    paste1 = [_ans("답", "paste") | {"tab": 1}, {"do": "save", "tab": 1}]
    # 이 창(0)이 공유 기록에 못 쓰고 복사 → 창 1에 붙인 답은 '복사 기록 없음'(창 1 질문이라고 하지 않음)
    out = _browser(
        tmp_path,
        pages,
        tab1_copied + [{"do": "storage", "local": "fail"}, COPY] + paste1,
    )
    assert _gpt(out["posts"][0]["body"])["answer_from"] is None
    # 공유 기록을 지우지도 못하면 그 사실을 복사 안내에 적음
    out = _browser(
        tmp_path,
        pages,
        tab1_copied
        + [{"do": "storage", "local": "fail", "local_delete": "fail"}, COPY],
    )
    assert (
        "다른 창에 붙인 답의 질문도 잘못 기록될 수 있으니" in out["tabs"][0]["copymsg"]
    )
    # 다시 열기 화면 복사가 공유 기록에 못 쓰면 그 기록을 지움 → 붙인 답은 '복사 기록 없음'
    _, saved_id = app.save({"build_id": _bid(x), "ticker": "AAA001", "verdict": "hold"})
    saved = PS.render_saved(ST.load(app.root, saved_id["review_id"]))
    out = _browser(
        tmp_path,
        [(x, "AAA001"), (saved, "AAA001")],
        [
            COPY,
            {"do": "storage", "local": "fail"},
            {"do": "open", "tab": 1, "page": 1},
            {"do": "manual_copy", "tab": 1},
            _ans("답", "paste"),
            SAVE,
        ],
    )
    assert _gpt(out["posts"][0]["body"])["answer_from"] is None
    # 두 저장소 모두 못 쓰는 창이 복사한 뒤 새로 고쳐도 다른 창의 옛 복사를 이 창 답의 출처로 쓰지 않음
    out = _browser(
        tmp_path,
        pages,
        tab1_copied
        + [
            {"do": "storage", "local": "fail", "session": "fail"},
            COPY,
            {"do": "reload"},
            _ans("답", "paste"),
            SAVE,
        ],
    )
    assert _gpt(out["posts"][0]["body"])["answer_from"] is None


def test_browser_corrupted_copy_record(market: Path, tmp_path: Path) -> None:
    """반박 R3-7 — 망가진 공유 복사 기록(형식이 틀린 화면 번호 · 지문 · 시각)은 쓰지 않고 화면 동작도 멈추지 않는다."""
    app = _app(market, tmp_path)
    html = app.page("AAA001")
    b = _bid(html)
    paste = [_ans("답", "paste"), SAVE]
    for bad in (
        {"from": "x y", "sig": "zz", "seq": 3},
        {"from": b, "sig": "zz", "seq": 3},
        ["x"],
    ):
        out = _browser(tmp_path, html, paste, seed={CLIP: bad})
        assert _gpt(out["posts"][0]["body"])["answer_from"] is None
    sig = SV.copy_sig(app.builds[b]["copy"])
    out = _browser(
        tmp_path,
        html,
        paste,
        seed={CLIP: {"from": b, "sig": sig, "at": 1e20, "seq": 1}},
    )
    post = out["posts"][0]["body"]
    assert _gpt(post)["answer_from"] == b and _gpt(post)["answer_copied_at"] is None
    assert (
        _gpt(json.loads(out["tabs"][0]["session"][KEY]))["ai_answer"] == "답"
    )  # 초안도 남음
    code, _ = app.save(post)
    assert code == 200
    # 초안의 형식이 틀린 화면 번호 · 지문 · 시각은 버림(저장 거절로 이어지지 않음)
    bad_draft = _draft(
        "bad id", "답", sig="zz", ai_pasted_at="어제", answer_copied_at="그제"
    )
    out = _browser(tmp_path, html, [SAVE], session_seed={KEY: bad_draft})
    post = out["posts"][0]["body"]
    assert _gpt(post)["answer_from"] is None and _gpt(post)["answer_sig"] is None
    assert _gpt(post)["ai_pasted_at"] is None and _gpt(post)["answer_copied_at"] is None
    assert app.save(post)[0] == 200


def test_browser_copy_on_saved_page_is_marked(market: Path, tmp_path: Path) -> None:
    """반박 LOW9 — 다시 열기 화면에서 옛 질문을 복사하면 그 뒤 붙인 답은 '하나로 정할 수 없음'."""
    app = _app(market, tmp_path)
    html = app.page("AAA001")
    _, out = app.save({"build_id": _bid(html), "ticker": "AAA001", "verdict": "hold"})
    saved = PS.render_saved(ST.load(app.root, out["review_id"]))
    listing = PS.render_list(ST.list_reviews(app.root))
    for other in (saved, listing):
        res = _browser(
            tmp_path,
            [(html, "AAA001"), (other, "AAA001")],
            [
                COPY,
                {"do": "open", "tab": 1, "page": 1},
                {"do": "manual_copy", "tab": 1},
                _ans("답", "paste"),
                SAVE,
            ],
        )
        assert _gpt(res["posts"][0]["body"])["answer_from"] == "mixed"
    # 다시 열기 화면의 복사 표시도 차례 번호를 올린다 — 그 뒤 다른 창 복사가 '못 씀' 창 표시보다 뒤가 됨
    y = app.page("AAA001")
    res = _browser(
        tmp_path,
        [(html, "AAA001"), (saved, "AAA001"), (y, "AAA001")],
        [
            {"do": "open", "tab": 2, "page": 2},
            {"do": "copy", "tab": 2},
            {"do": "storage", "local": "fail"},
            COPY,
            {"do": "storage", "local": "ok"},
            {"do": "open", "tab": 1, "page": 1},
            {"do": "manual_copy", "tab": 1},
            {"do": "copy", "tab": 2},
            _ans("답", "paste"),
            SAVE,
        ],
    )
    assert _gpt(res["posts"][0]["body"])["answer_from"] == _bid(y)


def test_browser_copy_in_other_window(market: Path, tmp_path: Path) -> None:
    """반박 M1 — 마지막 복사는 창끼리 같이 본다(다른 ETF 창에서 복사한 질문의 답이면 그 화면)."""
    app = _app(market, tmp_path)
    x = app.page("AAA001")
    y = app.page("AAA002")
    out = _browser(
        tmp_path,
        [(x, "AAA001"), (y, "AAA002")],
        [
            COPY,
            {"do": "open", "tab": 1, "page": 1},
            {"do": "copy", "tab": 1},
            _ans("답", "paste"),
            SAVE,
        ],
    )
    post = out["posts"][0]["body"]
    assert _gpt(post)["answer_from"] == _bid(y)
    _, saved = app.save(post)
    asked = _asked(ST.load(app.root, saved["review_id"]))
    assert asked["state"] == "other_screen" and asked["ticker"] == "AAA002"


def _reason(value: str, tab: int = 0) -> dict[str, Any]:
    return {"do": "field", "id": "reason", "value": value, "how": "type", "tab": tab}


OK = {
    "do": "respond",
    "status": 200,
    "json": {"review_id": "20261125T000000Z_aaaaaaaa"},
}


def test_browser_windows_keep_their_own_drafts(market: Path, tmp_path: Path) -> None:
    """반박 M2 · r2 F7 — 초안은 그 창 저장소에만: 다른 창 초안을 가져오거나 지우지 않는다."""
    app = _app(market, tmp_path)
    html = app.page("AAA001")
    out = _browser(
        tmp_path,
        html,
        [
            _reason("창0 이유"),
            {"do": "open", "tab": 1},
            _reason("창1 이유", tab=1),
            SAVE,
            OK,
        ],
    )
    assert out["posts"][0]["body"]["reason"] == "창0 이유"
    assert _draft_of(out, 0) is None  # 창0 저장 성공 = 창0 초안만 지움
    assert _draft_of(out, 1)["reason"] == "창1 이유"
    assert out["tabs"][1]["savemsg"] == ""  # 새 창은 다른 창 입력을 되살리지 않음
    # r2 F7 — 원래 창에서 같은 주소로 연 새 창(저장소 복사)이 원래 창 초안을 가져가지 않는다
    out = _browser(
        tmp_path,
        html,
        [
            _reason("원래 창 이유"),
            {"do": "open", "tab": 1, "page": 0, "from": 0},
            _reason("새 창 이유", tab=1),
            {"do": "reload"},
        ],
    )
    assert out["tabs"][0]["reason"] == "원래 창 이유"
    assert _draft_of(out, 0)["reason"] == "원래 창 이유"
    assert _draft_of(out, 1)["reason"] == "새 창 이유"


def test_browser_reload_and_legacy_draft(market: Path, tmp_path: Path) -> None:
    """같은 창 새로 고침 = 그 창 초안 · 예전 형식 초안도 같은 규칙(그 창의 것) — 이 창 번호 것만 되살림(r3 F8 · r4 F11 ~ F13).

    다른 창 번호 · 창 번호 없는 예전 초안은 되살리지도 안내하지도 지우지도 않는다. 예전 초안은 어떤 경우에도 지우지 않는다."""
    app = _app(market, tmp_path)
    html = app.page("AAA001")
    out = _browser(tmp_path, html, [_reason("새로 고침 전"), {"do": "reload"}])
    assert out["tabs"][0]["reason"] == "새로 고침 전"
    assert out["tabs"][0]["olddrafts"] is None  # 예전 입력이 없으면 목록도 없음
    assert out["tabs"][0]["savemsg"].startswith(
        "저장하지 않은 입력을 되살렸습니다(기준일"
    )
    k = KEY + "__r1tab"
    old = {k: _draft(None, "", reason="예전 초안", draft_v=3, at=1764000000000)}
    mine = {"poc7_04_tab": "r1tab"}
    # 이 창 번호 것(새로 고친 원래 창) = 되살림 · 예전 자리는 그대로
    out = _browser(tmp_path, html, [], seed=old, session_seed=mine)
    assert out["tabs"][0]["reason"] == "예전 초안"
    msg = out["tabs"][0]["savemsg"]
    assert msg.startswith("이 브라우저에 남아 있던 이 ETF 입력을 되살렸습니다")
    assert "한 창에서만 저장하세요" in msg
    assert json.loads(out["storage"][k]) == old[k]
    # r3 F8 — 관계없는 새 창은 가져가지도 지우지도 않음 → 원래 창(그 창 번호)을 새 판으로 열면 돌아옴
    out = _browser(
        tmp_path, html, [{"do": "open", "tab": 1, "session": mine}], seed=old
    )
    assert out["tabs"][0]["reason"] == "" and out["tabs"][1]["reason"] == "예전 초안"
    assert out["tabs"][0]["savemsg"] == ""  # 다른 창 것은 안내도 없음
    assert json.loads(out["storage"][k]) == old[k]
    # 이 창 번호가 있어도 다른 창 번호의 초안 · 창 번호 없는 초안은 되살리지 않음 — 읽기 전용 목록에만(반박 r4-1)
    for seed in ({KEY + "__other": old[k]}, {KEY: {"reason": "창 번호 없음"}}):
        out = _browser(tmp_path, html, [], seed=seed, session_seed=mine)
        assert out["tabs"][0]["reason"] == "" and out["tabs"][0]["savemsg"] == ""
        assert set(seed) <= set(out["storage"])
        listed = out["tabs"][0]["olddrafts"]
        assert (
            "예전 화면에 남은 이 ETF 입력 1건(읽기만 · 이 화면에 넣지 않음)" in listed
        )
        assert next(iter(seed.values()))["reason"] in listed
    # 이 창 번호 것은 되살리고 목록에는 넣지 않음 · 다른 창 것은 목록에
    out = _browser(
        tmp_path,
        html,
        [],
        seed={**old, KEY + "__other": {**old[k], "reason": "다른 창 이유"}},
        session_seed=mine,
    )
    assert out["tabs"][0]["reason"] == "예전 초안"
    listed = out["tabs"][0]["olddrafts"]
    assert "다른 창 이유" in listed and "예전 초안" not in listed
    # 저장해도 예전 초안은 지우지 않음 · 이 창은 이미 가져왔으니 새로 고쳐도 다시 되살리지 않음(r4 F12①)
    out = _browser(
        tmp_path, html, [SAVE, OK, {"do": "reload"}], seed=old, session_seed=mine
    )
    assert json.loads(out["storage"][k]) == old[k]
    assert out["tabs"][0]["reason"] == "" and out["tabs"][0]["savemsg"] == ""
    # 창 번호가 없는 창 — 창 번호 없는(첫 판) 초안도 되살리지 않음
    out = _browser(tmp_path, html, [], seed={KEY: {"reason": "창 번호 없음"}})
    assert out["tabs"][0]["reason"] == "" and out["tabs"][0]["savemsg"] == ""
    # 이 창에 임시 저장을 못 했으면 '가져옴'도 적지 않음 → 새로 고치면 다시 되살림(r4 F12②)
    # 작은 값('가져옴')은 써지고 큰 초안만 거절되는 경우도 같음
    big = {
        k: _draft(
            None, "긴 답 " * 400, reason="큰 예전 초안", draft_v=3, at=1764000000000
        )
    }
    out = _browser(
        tmp_path,
        html,
        [{"do": "reload"}],
        seed=big,
        session_seed=mine,
        session_quota=500,
    )
    assert out["tabs"][0]["reason"] == "큰 예전 초안"
    out = _browser(
        tmp_path,
        html,
        [{"do": "reload"}],
        seed=old,
        session_seed=mine,
        session_fail=True,
    )
    assert out["tabs"][0]["reason"] == "예전 초안"
    assert "이 창에 임시로 남기지 못했습니다" in out["tabs"][0]["savemsg"]
    assert out["tabs"][0]["keepmsg"]
    # '가져옴' 표시만 못 써도, 저장 뒤 새로 고치면 예전 초안이 아니라 '이미 저장한 입력'(반박 r4-2)
    for steps, reason in (
        ([SAVE, OK, {"do": "reload"}], "예전 초안"),
        (
            [{"do": "reload"}, SAVE, OK, {"do": "reload"}],
            "예전 초안",
        ),  # 가져온 사실이 새로 고쳐도 이어짐
        ([_reason("새로 쓴 이유"), SAVE, OK, {"do": "reload"}], "새로 쓴 이유"),
    ):
        out = _browser(
            tmp_path,
            html,
            steps,
            seed=old,
            session_seed=mine,
            session_fail_keys=["poc7_04_legacy_taken2"],
        )
        assert out["tabs"][0]["reason"] == reason
        assert out["tabs"][0]["savemsg"].startswith("이미 저장한 판단의 입력입니다")
    # 처음엔 못 쓴 '가져옴' 표시를 저장 때 다시 적으면, 초안을 비우고 새로 고쳐도 예전 초안을 다시 안 가져옴
    out = _browser(
        tmp_path,
        html,
        [{"do": "storage", "session_fail_keys": []}, SAVE, OK, {"do": "reload"}],
        seed=old,
        session_seed=mine,
        session_fail_keys=["poc7_04_legacy_taken2"],
    )
    assert out["tabs"][0]["reason"] == "" and out["tabs"][0]["savemsg"] == ""
    # r3 판이 남긴 옛 '가져옴' 표시는 보지 않음 — 그 창 초안을 되살림(반박 r4-3)
    out = _browser(
        tmp_path,
        html,
        [],
        seed=old,
        session_seed={**mine, "poc7_04_legacy_taken": [{"key": k, "at": old[k]["at"]}]},
    )
    assert out["tabs"][0]["reason"] == "예전 초안"
    # 그 사이 원래 창이 고쳐 시각이 바뀌면 다른 초안 — 이미 가져온 창도 다시 되살림
    changed = {**old[k], "reason": "원래 창이 고침", "at": 1764000000999}
    out = _browser(
        tmp_path,
        html,
        [SAVE, OK, {"do": "local_set", "key": k, "value": changed}, {"do": "reload"}],
        seed=old,
        session_seed=mine,
    )
    assert out["tabs"][0]["reason"] == "원래 창이 고침"
    # 빈 · 형식이 틀린 이 창 번호 초안 = 되살리지 않음(화면 동작은 그대로)
    empty = _draft(None, "", verdict="unrecorded", ai_name="", draft_v=3)
    for bad in (empty, {"used": "rank_flow"}):
        out = _browser(tmp_path, html, [], seed={k: bad}, session_seed=mine)
        assert out["tabs"][0]["savemsg"] == "" and out["tabs"][0]["reason"] == ""
        out = _browser(
            tmp_path, html, [_reason("새 이유"), SAVE], seed={k: bad}, session_seed=mine
        )
        assert out["tabs"][0]["savemsg"] == "저장 중…"
        assert out["posts"][0]["body"]["reason"] == "새 이유"
    # 기준일이 바뀐 안내는 AI 답이 있을 때만 · 썼다가 다 지운 이 창 초안은 알리지 않음
    no_answer = _draft(None, "", reason="이유만", end="2026-11-13")
    out = _browser(tmp_path, html, [], session_seed={KEY: no_answer})
    assert "기준일이" not in out["tabs"][0]["savemsg"]
    out = _browser(
        tmp_path, html, [], session_seed={KEY: {**no_answer, "ai_answer": "답"}}
    )
    assert "기준일이 2026-11-23 로 바뀌었으니" in out["tabs"][0]["savemsg"]
    out = _browser(tmp_path, html, [_reason("잠깐"), _reason(""), {"do": "reload"}])
    assert out["tabs"][0]["savemsg"] == ""


def test_browser_copy_order_ignores_clock(market: Path, tmp_path: Path) -> None:
    """r3 F10 — 기기 시계가 뒤로 가도 나중에 복사한 질문이 앞선다(공유 기록의 차례 번호)."""
    app = _app(market, tmp_path)
    x = app.page("AAA001")
    _bump(market)
    y = app.page("AAA001")
    pages = [(x, "AAA001"), (y, "AAA001")]
    later = [
        {"do": "open", "tab": 1, "page": 1},
        {"do": "copy", "tab": 1},
        _ans("답", "paste"),
        SAVE,
    ]
    out = _browser(tmp_path, pages, [COPY, {"do": "wait", "ms": -120000}] + later)
    assert _gpt(out["posts"][0]["body"])["answer_from"] == _bid(y)
    # 공유 기록에 못 쓴 복사 뒤 다른 창이 정상 복사하면 그 복사가 앞선다
    out = _browser(
        tmp_path,
        pages,
        [{"do": "storage", "local": "fail"}, COPY, {"do": "storage", "local": "ok"}]
        + later,
    )
    assert _gpt(out["posts"][0]["body"])["answer_from"] == _bid(y)
    # 다른 창 복사 → 이 창 복사(공유 기록 못 씀) → 다른 창 다시 복사: 마지막 복사가 앞선다
    out = _browser(
        tmp_path,
        pages,
        [
            {"do": "open", "tab": 1, "page": 1},
            {"do": "copy", "tab": 1},
            {"do": "storage", "local": "fail"},
            COPY,
            {"do": "storage", "local": "ok"},
            {"do": "copy", "tab": 1},
            _ans("답", "paste"),
            SAVE,
        ],
    )
    assert _gpt(out["posts"][0]["body"])["answer_from"] == _bid(y)


@pytest.mark.parametrize(
    "bad",
    [{"used": "rank_flow"}, {"verdict": 5}, {"reason": 3}, ["x"], "문자"],
    ids=["used-글", "verdict-숫자", "reason-숫자", "목록", "글"],
)
def test_browser_malformed_draft_does_not_break_page(
    market: Path, tmp_path: Path, bad
) -> None:
    """반박 LOW4 — 형식이 틀린 초안은 되살리지 않고 알리며, 복사 · 저장은 그대로 된다."""
    app = _app(market, tmp_path)
    html = app.page("AAA001")
    out = _browser(
        tmp_path,
        html,
        [COPY, _ans("답", "paste"), SAVE],
        session_seed={KEY: bad},
    )
    assert _gpt(out["posts"][0]["body"])["answer_from"] == _bid(html)
    out = _browser(tmp_path, html, [], session_seed={KEY: bad})
    assert out["tabs"][0]["savemsg"].startswith(
        "이 창에 남아 있던 입력의 형식이 맞지 않아"
    )


def test_browser_other_drafts_in_this_window(market: Path, tmp_path: Path) -> None:
    """반박 MEDIUM3 — 이 창에 저장하지 않은 다른 ETF 입력이 있으면 고르는 길을 알린다."""
    app = _app(market, tmp_path)
    x = app.page("AAA001")
    y = app.page("AAA002")
    out = _browser(
        tmp_path,
        [(x, "AAA001"), (y, "AAA002")],
        [_reason("AAA001 이유"), {"do": "open", "tab": 0, "page": 1}],
    )
    note = out["tabs"][0]["otherdrafts"]
    assert (
        note.startswith("이 창에 저장하지 않은 다른 ETF 입력:") and "(AAA001)" in note
    )
    assert "가가 미국" in note or "AAA001" in note
    back = _browser(
        tmp_path,
        [(x, "AAA001"), (y, "AAA002")],
        [
            _reason("AAA001 이유"),
            {"do": "open", "tab": 0, "page": 1},
            {"do": "open", "tab": 0, "page": 0},
        ],
    )
    assert (
        back["tabs"][0]["reason"] == "AAA001 이유"
        and back["tabs"][0]["otherdrafts"] is None
    )


@pytest.mark.parametrize(
    "steps,text",
    [
        (
            [SAVE, {"do": "respond", "network": True}],
            "저장됐는지 모르는 입력을 되살렸습니다",
        ),
        ([SAVE], "저장됐는지 모르는 입력을 되살렸습니다"),  # 보내는 중에 창을 새로 고침
        ([SAVE, _reason("둘"), OK], "앞서 저장한 판단 뒤에 고친 입력을 되살렸습니다"),
        (
            [SAVE, {"do": "respond", "status": 422, "json": {"error": "x"}}],
            "저장하지 않은 입력을 되살렸습니다",
        ),
        # 반박 LOW6 — 거절은 앞선 '모름' · 저장 기록을 지우지 않는다
        (
            [
                SAVE,
                {"do": "respond", "network": True},
                SAVE,
                {"do": "respond", "status": 409, "json": {"error": "x"}},
            ],
            "저장됐는지 모르는 입력을 되살렸습니다",
        ),
        (
            [
                SAVE,
                _reason("둘"),
                OK,
                SAVE,
                {"do": "respond", "status": 422, "json": {"error": "x"}},
            ],
            "앞서 저장한 판단 뒤에 고친 입력을 되살렸습니다",
        ),
        # 반박 HIGH1 — 저장한 뒤 고치면 '이미 저장한 입력'이라고 하지 않는다 · 그대로면 '이미 저장한 입력'
        (
            [SAVE, OK, _reason("하나 고침")],
            "앞서 저장한 판단 뒤에 고친 입력을 되살렸습니다",
        ),
    ],
)
def test_browser_restore_tells_save_state(
    market: Path, tmp_path: Path, steps, text
) -> None:
    """반박 M3 — 되살릴 때 저장 결과(모름 · 일부 저장 · 거절)를 그대로 말한다('저장하지 않음' 단정 금지)."""
    app = _app(market, tmp_path)
    html = app.page("AAA001")
    out = _browser(tmp_path, html, [_reason("하나")] + steps + [{"do": "reload"}])
    assert out["tabs"][0]["savemsg"].startswith(text)


def test_browser_edit_during_save_is_kept(market: Path, tmp_path: Path) -> None:
    """F4 · r2 F5② — 저장 중 고친 내용은 성공 뒤에도 남기고, 남기지 못했으면 그렇게 말한다."""
    app = _app(market, tmp_path)
    html = app.page("AAA001")
    out = _browser(
        tmp_path, html, [_reason("첫 이유"), SAVE, _reason("두 번째 이유"), OK]
    )
    assert out["posts"][0]["body"]["reason"] == "첫 이유"
    assert out["tabs"][0]["reason"] == "두 번째 이유"
    d = _draft_of(out)
    assert d["reason"] == "두 번째 이유" and d["save"]["pending"] is None
    assert d["save"]["last"]["id"] == "20261125T000000Z_aaaaaaaa"
    assert (
        "저장 중에 고친 내용은 아직 저장 안 됨(이 창에 임시로 남김"
        in out["tabs"][0]["savemsg"]
    )
    same = _browser(tmp_path, html, [_reason("첫 이유"), SAVE, OK])
    assert _draft_of(same) is None and same["tabs"][0]["savemsg"].startswith("저장됨")
    # 반박 HIGH1 — 저장 뒤 고치면 화면 문구도 바로 바뀌고, 저장한 그 입력으로 되돌리면 다시 '저장됨'
    after = _browser(
        tmp_path, html, [_reason("첫 이유"), SAVE, OK, _reason("고친 이유")]
    )
    assert after["tabs"][0]["savemsg"].startswith(
        "저장한 뒤 고친 내용은 아직 저장 안 됨"
    )
    back = _browser(
        tmp_path,
        html,
        [_reason("첫 이유"), SAVE, OK, _reason("고친 이유"), _reason("첫 이유")],
    )
    assert back["tabs"][0]["savemsg"].startswith("저장됨")
    # 저장 성공 뒤 초안 지우기만 실패 — 다시 열면 '이미 저장한 판단의 입력'(저장 여부를 모른다고 하지 않음)
    stuck = _browser(
        tmp_path,
        html,
        [
            _reason("첫 이유"),
            SAVE,
            {"do": "storage", "session_delete": "fail"},
            OK,
            {"do": "reload"},
        ],
    )
    assert stuck["tabs"][0]["savemsg"].startswith("이미 저장한 판단의 입력입니다")
    assert stuck["tabs"][0]["keepmsg"] is None
    # 실제 새로 고침은 새 화면 번호 — 그래도 '이미 저장한 입력'(입력 지문은 화면 번호를 빼고 비교)
    fresh = app.page("AAA001")
    assert _bid(fresh) != _bid(html)
    stuck2 = _browser(
        tmp_path,
        [(html, "AAA001"), (fresh, "AAA001")],
        [
            _reason("첫 이유"),
            SAVE,
            {"do": "storage", "session_delete": "fail"},
            OK,
            {"do": "open", "tab": 0, "page": 1},
        ],
    )
    assert stuck2["tabs"][0]["savemsg"].startswith("이미 저장한 판단의 입력입니다")
    failed = _browser(
        tmp_path,
        html,
        [
            _reason("첫 이유"),
            SAVE,
            {"do": "storage", "session": "fail"},
            _reason("두 번째 이유"),
            OK,
        ],
    )
    msg = failed["tabs"][0]["savemsg"]
    assert "이 창에 임시로 남기지 못함" in msg and "임시로 남김" not in msg
    assert failed["tabs"][0]["keepmsg"]


def test_browser_keep_failure_is_shown_while_typing(
    market: Path, tmp_path: Path
) -> None:
    """임시 보관을 못 하면 쓰는 동안 바로 알리고, 다시 되면 알림을 거둔다."""
    app = _app(market, tmp_path)
    html = app.page("AAA001")
    out = _browser(tmp_path, html, [_reason("이유")], session_fail=True)
    assert "이 창에 임시로 남기지 못하고 있습니다" in out["tabs"][0]["keepmsg"]
    out = _browser(
        tmp_path,
        html,
        [
            {"do": "storage", "session": "fail"},
            _reason("이유"),
            {"do": "storage", "session": "ok"},
            _reason("이유2"),
        ],
    )
    assert out["tabs"][0]["keepmsg"] is None and _draft_of(out)["reason"] == "이유2"


@pytest.mark.parametrize(
    "respond,text",
    [
        (
            {
                "status": 409,
                "json": {"error": "이 화면의 자료를 서버가 갖고 있지 않습니다"},
            },
            "저장 안 됨\n",
        ),
        (
            {"status": 422, "json": {"error": "판단 값이 올바르지 않습니다"}},
            "저장 안 됨 — 다시 저장\n",
        ),
        (
            {"status": 500, "json": {"error": "파일에 쓰지 못했습니다(OSError)"}},
            "저장됐는지 모릅니다",
        ),
        ({"status": 200, "json": {}}, "저장됐는지 모릅니다"),
        ({"network": True}, "저장됐는지 모릅니다"),
    ],
)
def test_browser_save_failure_keeps_draft(
    market: Path, tmp_path: Path, respond, text
) -> None:
    """거절(4xx)만 '저장 안 됨'(409 는 '다시 저장' 없이) — 서버 오류 · 응답 없음은 저장 여부를 모른다고 쓴다."""
    app = _app(market, tmp_path)
    html = app.page("AAA001")
    out = _browser(
        tmp_path, html, [_reason("이유"), SAVE, {"do": "respond", **respond}]
    )
    msg = out["tabs"][0]["savemsg"]
    assert msg.startswith(text)
    if respond.get("status") == 409:
        assert (
            "이 창을 새로 고치면 쓴 내용이 돌아옵니다" in msg
            and "다시 저장\n" not in msg
        )
    else:
        assert "쓴 내용은 이 창에 임시로 남아 있습니다" in msg
    if text == "저장됐는지 모릅니다":
        assert (
            "새로 열리는 창에는 이 입력이 없으니 이 창을 닫지 마세요" in msg
        )  # 반박 MEDIUM3
    assert _draft_of(out)["reason"] == "이유"


def test_browser_storage_unavailable_is_said(market: Path, tmp_path: Path) -> None:
    """반박 L7 — 이 창 저장소를 못 쓰면 '남아 있다'고 하지 않는다."""
    app = _app(market, tmp_path)
    html = app.page("AAA001")
    out = _browser(
        tmp_path,
        html,
        [
            _reason("이유"),
            SAVE,
            {"do": "respond", "status": 409, "json": {"error": "x"}},
        ],
        session_fail=True,
    )
    msg = out["tabs"][0]["savemsg"]
    # 반박 MEDIUM2 — 남기지 못했으면 '새로 고치면 돌아옴'이라고 하지 않는다
    assert "이 창에 임시로 남기지 못했으니 새로 고치기 전에" in msg
    assert "돌아옵니다" not in msg and "남아 있습니다" not in msg
    # 그 창에서 저장에 성공하면 '남기지 못하고 있습니다' 알림을 거둔다(남길 입력이 없음)
    ok = _browser(tmp_path, html, [_reason("이유"), SAVE, OK], session_fail=True)
    assert (
        ok["tabs"][0]["savemsg"].startswith("저장됨")
        and ok["tabs"][0]["keepmsg"] is None
    )


# --- AI 답 세 칸(PLAN V2 판정 2026-11-26 §3 · §4) ---


def _box(value: str, how: str, box: str) -> dict[str, Any]:
    return {"do": "field", "id": f"answer_{box}", "value": value, "how": how}


def _by(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {a["name"]: a for a in body["ais"]}


def test_browser_three_boxes_keep_each_own_provenance(
    market: Path, tmp_path: Path
) -> None:
    """칸마다 붙일 때의 복사 기록 — 뒤의 복사 · 다른 칸 붙이기로 앞 칸 출처가 바뀌지 않음."""
    app = _app(market, tmp_path)
    html = app.page("AAA001")
    b = _bid(html)
    out = _browser(
        tmp_path,
        html,
        [
            COPY,
            _box("답G", "paste", "gpt"),
            {"do": "select_part"},
            {
                "do": "manual_copy"
            },  # 질문 일부 복사 → 그 뒤 붙인 칸은 '하나로 정할 수 없음'
            _box("답C", "paste", "claude"),
            SAVE,
        ],
        clipboard="fail",
    )
    body = out["posts"][0]["body"]
    by = _by(body)
    assert [a["name"] for a in body["ais"]] == ["GPT", "Gemini", "Claude"]
    assert (
        by["GPT"]["answer_from"] is None
    )  # 클립보드 실패 · 직접 복사 없음 — 복사 기록 없음
    assert by["Claude"]["answer_from"] == "mixed" and by["Gemini"]["answer"] == ""
    note = out["tabs"][0]["notes"]["gpt"]
    assert note.endswith("질문 복사 기록 없음 — 먼저 [AI 질문 복사]를 누르세요")
    out2 = _browser(
        tmp_path,
        html,
        [
            COPY,
            _box("답G", "paste", "gpt"),
            {"do": "select_part"},
            {"do": "manual_copy"},
            _box("답C", "paste", "claude"),
            SAVE,
        ],
    )
    by2 = _by(out2["posts"][0]["body"])
    assert by2["GPT"]["answer_from"] == b and by2["Claude"]["answer_from"] == "mixed"
    notes = out2["tabs"][0]["notes"]
    assert "질문: 이 화면의 복사문" in notes["gpt"] and notes["gpt"].startswith(
        "붙인 시각 "
    )
    assert (
        "질문: 하나로 정할 수 없음" in notes["claude"]
        and notes["gemini"] == "답 미입력"
    )
    code, saved = app.save(out2["posts"][0]["body"])
    doc = ST.load(app.root, saved["review_id"])
    assert _asked(doc, "GPT")["state"] == "this_screen"
    assert _asked(doc, "Claude")["state"] == "mixed"
    assert _asked(doc, "Gemini") == {"state": "no_answer"}


def test_browser_helpful_only_for_filled_boxes_and_cleared_with_answer(
    market: Path, tmp_path: Path
) -> None:
    """'판단에 도움이 된 답' — 처음 모두 미선택 · 빈 칸은 못 고름 · 답을 지우면 선택 · 시각 · 출처도 지움."""
    app = _app(market, tmp_path)
    html = app.page("AAA001")
    out = _browser(tmp_path, html, [{"do": "check", "id": "help_gemini"}])
    helps = out["tabs"][0]["helps"]
    assert helps == {
        "gpt": [False, True],
        "gemini": [False, True],
        "claude": [False, True],
    }
    out = _browser(
        tmp_path,
        html,
        [
            COPY,
            _box("답G", "paste", "gpt"),
            {"do": "check", "id": "help_gpt"},
            _box("답C", "paste", "claude"),
            {"do": "check", "id": "help_claude"},
            _box("", "type", "claude"),  # 답을 지움
            SAVE,
        ],
    )
    t = out["tabs"][0]
    assert t["helps"]["gpt"] == [True, False] and t["helps"]["claude"] == [False, True]
    by = _by(out["posts"][0]["body"])
    assert by["GPT"]["helpful"] is True
    assert by["Claude"] == {
        "name": "Claude",
        "answer": "",
        "helpful": False,
        "pasted_at": None,
        "answer_from": None,
        "answer_sig": None,
        "answer_copied_at": None,
    }
    code, _ = app.save(out["posts"][0]["body"])
    assert code == 200


def test_browser_new_draft_restores_three_boxes(market: Path, tmp_path: Path) -> None:
    """새 형식 초안(세 칸 · 칸마다 출처 · 도움 선택) — 새로 고쳐도 그대로 · 답 없는 칸의 선택은 버림."""
    app = _app(market, tmp_path)
    html = app.page("AAA001")
    b = _bid(html)
    out = _browser(
        tmp_path,
        html,
        [
            COPY,
            _box("답G", "paste", "gpt"),
            _box("답C", "paste", "claude"),
            {"do": "check", "id": "help_claude"},
            {"do": "reload"},
        ],
    )
    t = out["tabs"][0]
    assert t["answers"] == {"gpt": "답G", "gemini": "", "claude": "답C"}
    assert t["helps"]["claude"] == [True, False] and t["helps"]["gpt"] == [False, False]
    assert "되살린 AI 답(GPT · Claude)은 이 화면과 같은 질문의 답입니다" in t["savemsg"]
    assert "질문: 이 화면의 복사문" in t["notes"]["claude"]
    out = _browser(
        tmp_path,
        html,
        [
            COPY,
            _box("답G", "paste", "gpt"),
            _box("답C", "paste", "claude"),
            {"do": "check", "id": "help_claude"},
            {"do": "reload"},
            SAVE,
        ],
    )
    by = _by(out["posts"][0]["body"])
    assert by["GPT"]["answer_from"] == b and by["Claude"]["answer_from"] == b
    assert by["Claude"]["helpful"] is True
    seeded = {
        "draft_v": 6,
        "at": 1,
        "verdict": "hold",
        "reason": "이유",
        "used": [],
        "ais": [
            {"name": "Gemini", "answer": "", "helpful": True, "answer_from": b},
            {"name": "Claude", "answer": "답C", "helpful": True, "answer_from": "nope"},
        ],
        "end": END,
    }
    out = _browser(tmp_path, html, [SAVE], session_seed={KEY: seeded})
    t = out["tabs"][0]
    assert t["helps"]["gemini"] == [False, True] and t["helps"]["claude"] == [
        True,
        False,
    ]
    by = _by(out["posts"][0]["body"])
    assert by["Gemini"]["helpful"] is False and by["Claude"]["answer_from"] is None
    assert app.save(out["posts"][0]["body"])[0] == 200


@pytest.mark.parametrize("name", ["", "기타"])
def test_browser_old_draft_without_box_name_is_shown_not_placed(
    market: Path, tmp_path: Path, name: str
) -> None:
    """답 하나짜리 예전 초안 — AI 이름이 없거나 '기타'면 칸에 넣지 않고 읽기 전용(초안에 남김)."""
    app = _app(market, tmp_path)
    html = app.page("AAA001")
    seed = {KEY: _draft(None, "옛답글", ai_name=name, reason="옛이유")}
    out = _browser(tmp_path, html, [_ans("새답", "paste"), SAVE], session_seed=seed)
    t = out["tabs"][0]
    assert (
        t["orphan"] == "옛답글"
        and t["answers"]["gemini"] == ""
        and t["answers"]["claude"] == ""
    )
    assert _draft_of(out)["ai_orphan"] == "옛답글"
    body = out["posts"][0]["body"]
    assert (
        "옛답글" not in json.dumps(body, ensure_ascii=False)
        and body["reason"] == "옛이유"
    )
    shown = _browser(tmp_path, html, [], session_seed=seed)["tabs"][0]
    assert "칸에 넣지 않았습니다" in shown["savemsg"] and shown["orphan"] == "옛답글"


def test_browser_old_draft_with_box_name_goes_to_that_box(
    market: Path, tmp_path: Path
) -> None:
    app = _app(market, tmp_path)
    a = _bid(app.page("AAA001"))
    _bump(market)
    html = app.page("AAA001")
    sig_a = SV.copy_sig(app.builds[a]["copy"])
    seed = {KEY: _draft(a, "옛답C", sig=sig_a, ai_name="Claude")}
    t = _browser(tmp_path, html, [], session_seed=seed)["tabs"][0]
    assert t["answers"] == {"gpt": "", "gemini": "", "claude": "옛답C"}
    assert t["orphan"] is None
    assert (
        "되살린 AI 답(Claude)은 이 화면 질문의 답으로 기록되지 않습니다" in t["savemsg"]
    )
    out = _browser(tmp_path, html, [SAVE], session_seed=seed)
    by = _by(out["posts"][0]["body"])
    assert by["Claude"]["answer_from"] == a and by["Claude"]["answer_sig"] == sig_a
    code, saved = app.save(out["posts"][0]["body"])
    assert (
        _asked(ST.load(app.root, saved["review_id"]), "Claude")["state"]
        == "other_screen"
    )


def test_browser_dragging_page_text_into_box_is_mixed(
    market: Path, tmp_path: Path
) -> None:
    """반박 검토 F4 — 이 페이지의 글(예전 입력의 AI 답)을 칸에 끌어 놓으면 출처 = '하나로 정할 수 없음'."""
    app = _app(market, tmp_path)
    html = app.page("AAA001")
    seed = {KEY: _draft(None, "옛답글", ai_name="")}
    out = _browser(
        tmp_path,
        html,
        [
            COPY,
            {"do": "dragstart", "id": "orphantext"},
            {"do": "drop", "value": "옛답글", "box": "gpt"},
            SAVE,
        ],
        session_seed=seed,
    )
    assert _gpt(out["posts"][0]["body"])["answer_from"] == "mixed"
    assert "질문: 하나로 정할 수 없음" in out["tabs"][0]["notes"]["gpt"]
    code, saved = app.save(out["posts"][0]["body"])
    assert _asked(ST.load(app.root, saved["review_id"]))["state"] == "mixed"


def test_browser_orphan_answer_is_kept_after_save(market: Path, tmp_path: Path) -> None:
    """반박 검토 F5 — 칸에 넣지 않은 예전 입력의 AI 답은 저장한 뒤에도 이 창에 남는다(그 글만)."""
    app = _app(market, tmp_path)
    html = app.page("AAA001")
    seed = {KEY: _draft(None, "옛답글", ai_name="기타", reason="옛이유")}
    steps = [SAVE, {"do": "respond", "status": 200, "json": {"review_id": UNKNOWN_ID}}]
    out = _browser(tmp_path, html, steps, session_seed=seed)
    left = _draft_of(out)
    assert left is not None and left["ai_orphan"] == "옛답글"
    assert "reason" not in left and "save" not in left and "ais" not in left
    again = _browser(tmp_path, html, [], session_seed={KEY: left})["tabs"][0]
    assert again["orphan"] == "옛답글" and again["reason"] == ""
    assert again["savemsg"].startswith(
        "예전 입력의 AI 답은 어느 AI 의 답인지 적혀 있지 않아"
    )
    assert "저장하지 않은 입력을 되살렸습니다" not in again["savemsg"]


def test_browser_v5_saved_mark_is_not_compared_with_new_shape(
    market: Path, tmp_path: Path
) -> None:
    """반박 검토 F6 — 칸 세 개 이전(v5) 초안의 '저장 확인' 지문은 지금 입력과 비교하지 않음(그 뒤 고쳤는지 모름)."""
    app = _app(market, tmp_path)
    html = app.page("AAA001")
    v5 = {
        **_draft(None, "답A"),
        "draft_v": 5,
        "save": {"pending": None, "last": {"id": UNKNOWN_ID, "sig": "abcd1234"}},
    }
    t = _browser(tmp_path, html, [], session_seed={KEY: v5})["tabs"][0]
    assert (
        "앞서 저장한 판단이 있는 입력을 되살렸습니다(그 뒤 고쳤는지는 모름)"
        in t["savemsg"]
    )
