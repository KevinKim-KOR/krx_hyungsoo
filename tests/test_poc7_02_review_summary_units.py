"""POC7-02 단위 시험 — 결과 구분 · 합성 점검 문 · 한 장 형식 · 로그 판단 · AC4 · 표준 라이브러리 경계.

흐름 시험(보관 · 묶음 · 실행기 · 회수)은 `test_poc7_02_review_summary.py`.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from app.review_summary import judge as JU
from app.review_summary import ollama_io as IO
from app.review_summary import prompt as PR
from app.review_summary import render as RE
from app.review_summary import report as RP
from app.review_summary import runner_win as RW

MARKS = ("S-1", "E-1")
FULL = (
    "시장: a\n선택한 ETF: b\nAI 의견: c\n최신 자료와 다음 확인: d\n확인 표지: S-1 · E-1"
)


def _run(**over):
    base = {
        "call_error": None,
        "content": "시장: a\n확인 표지: S-1 · E-1",
        "done_reason": "stop",
        "prompt_eval_count": 100,
        "eval_count": 50,
        "count_tokens": 100,
        "ps": {"size": 10, "size_vram": 10, "context_length": 1000},
        "ps_text": None,
        "trunc_log": [],
        "gpu_samples": [{"util": 90, "mem_mb": 7000, "t": 0.0}],
    }
    base.update(over)
    return base


def _cls(run, counted=True):
    return JU.classify(run, model="m", requested_ctx=1000, marks=MARKS, counted=counted)


# ── 결과 구분 ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "over, status, reason",
    [
        ({}, JU.COMPLETED, None),
        ({"call_error": "HTTP 500"}, JU.TECHNICAL_FAILURE, "호출 오류"),
        ({"content": "  "}, JU.TECHNICAL_FAILURE, "빈 출력"),
        ({"done_reason": "length"}, JU.TECHNICAL_FAILURE, "출력 길이 초과"),
        ({"done_reason": None}, JU.TECHNICAL_FAILURE, "종료 이유"),
        ({"count_tokens": 99}, JU.INPUT_UNCONFIRMED, "두 번 센"),
        ({"count_tokens": None}, JU.INPUT_UNCONFIRMED, "두 번 센"),
        ({"prompt_eval_count": 980}, JU.INPUT_UNCONFIRMED, "입력 + 출력"),
        (
            {"ps": {"size": 10, "size_vram": 10, "context_length": 500}},
            JU.INPUT_UNCONFIRMED,
            "할당 문맥 500",
        ),
        ({"ps": {"size": 10, "size_vram": 10}}, JU.INPUT_UNCONFIRMED, "미기록"),
        ({"trunc_log": None}, JU.INPUT_UNCONFIRMED, "이번 호출 기록 없음"),
        ({"trunc_log": ["truncated = 1"]}, JU.INPUT_UNCONFIRMED, "잘림 기록"),
        ({"eval_count": None}, JU.INPUT_UNCONFIRMED, "토큰 수 없음"),
    ],
)
def test_classify(over, status, reason):
    j = _cls(_run(**over))
    assert j["status"] == status
    if reason:
        assert reason in " ".join(j["technical"] + j["input"])


def test_classify_order_marks_and_cache_notes():
    j = _cls(_run(done_reason="length", trunc_log=None))
    assert (
        j["status"] == JU.TECHNICAL_FAILURE and j["input"]
    )  # 둘 다 기록 · 기술 실패가 먼저
    j = _cls(_run(content="시장: a"))
    assert (
        j["status"] == JU.COMPLETED
        and j["marks_echoed"] is False
        and "표지 누락" in j["note"]
    )
    j = _cls(_run(content="시장: a\n확인 표지: S-9 · E-9"))
    assert j["marks_echoed"] is False  # 표지 줄은 있지만 값이 틀림
    assert (
        _cls(_run(count_tokens=1), counted=False)["status"] == JU.COMPLETED
    )  # 합성 점검
    j = _cls(_run(prompt_eval_cached_count=40))
    assert (
        j["status"] == JU.COMPLETED
        and "캐시" in j["note"]
        and j["tokens"]["cached"] == 40
    )


@pytest.mark.parametrize(
    "ps, samples, status",
    [
        ({"size": 10, "size_vram": 10}, [], JU.GPU),
        ({"size": 10, "size_vram": 4}, [], JU.MIXED),
        ({"size": 10, "size_vram": 0}, [], JU.CPU_ONLY),
        (None, [{"util": 1, "mem_mb": 1}], JU.PS_MISSING),
        (None, [], JU.GPU_MEASURE_MISSING),
    ],
)
def test_gpu_status(ps, samples, status):
    assert JU.gpu_status({"ps": ps, "gpu_samples": samples})["status"] == status


def test_ps_context_from_text():
    text = (
        "NAME  ID  SIZE  PROCESSOR  CONTEXT  UNTIL\n"
        "qwen3.5:9b-q4_K_M  a  8 GB  100% GPU  49,152  now\n"
    )
    assert JU.ps_context_from_text(text, "qwen3.5:9b-q4_K_M") == 49152
    assert JU.ps_context_from_text(text, "other") is None
    assert JU.ps_context_from_text("NAME  ID\nx  y\n", "x") is None


# ── 합성 점검 문 ────────────────────────────────────────────────────────────────

KOREAN = "가나다라마바사아자차카타파하" * 3


def _gate(run, driver="566.36", content=None):
    j = _cls(run, counted=False)
    c = content if content is not None else run["content"]
    return JU.trial_gate(j, content=c, marks=MARKS, driver=driver)


def test_trial_gate_passes_good_trial():
    run = _run(content=FULL.replace("a\n", f"{KOREAN}\n", 1))
    assert _gate(run) == {"ok": True, "reasons": [], "categories": []}


@pytest.mark.parametrize(
    "over, driver, content, kind, why",
    [
        (
            {"ps": {"size": 10, "size_vram": 10, "context_length": 500}},
            "566.36",
            None,
            "SETTINGS",
            "할당 문맥 500",
        ),
        ({"done_reason": "length"}, "566.36", None, "SETTINGS", "출력 길이"),
        ({"trunc_log": ["x"]}, "566.36", None, "SETTINGS", "잘림"),
        ({}, "566.36", "Market: ??? �", "MODEL", "한글"),
        (
            {},
            "566.36",
            FULL.replace("확인 표지: S-1 · E-1", "") + KOREAN,
            "MODEL",
            "복창",
        ),
        ({}, "566.36", "머리말\n" + FULL + KOREAN, "MODEL", "형식 다름"),
        ({}, "531.18", None, "ENV", "551.61"),
        ({}, None, None, "ENV", "드라이버 판을 읽지 못함"),
        ({"ps": None}, "566.36", None, "ENV", "GPU 실행을 확인하지 못함"),
        (
            {"ps": {"size": 10, "size_vram": 0, "context_length": 1000}},
            "566.36",
            None,
            "ENV",
            "CPU_ONLY",
        ),
        ({"trunc_log": None}, "566.36", None, "ENV", "이번 호출 기록 없음"),
        ({"ps": {"size": 10, "size_vram": 10}}, "566.36", None, "ENV", "미기록"),
        ({"call_error": "HTTP 500"}, "566.36", None, "ENV", "호출 오류"),
    ],
)
def test_trial_gate_stops_by_kind(over, driver, content, kind, why):
    good = FULL.replace("a\n", f"{KOREAN}\n", 1)
    g = _gate(
        _run(content=good, **over), driver=driver, content=content if content else good
    )
    assert g["ok"] is False and kind in g["categories"]
    assert any(why in r for r in g["reasons"])


def test_driver_ok():
    assert JU.driver_ok("551.61") is True and JU.driver_ok("566.36") is True
    assert JU.driver_ok("551.60") is False and JU.driver_ok("531.18") is False
    assert JU.driver_ok(None) is None and JU.driver_ok("알 수 없음") is None


# ── 한 장 형식 ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text, with_ai, ok, why",
    [
        (FULL, True, True, None),
        (
            "**시장:** a\n- 선택한 ETF: b\n## AI 의견: c\n**최신 자료와 다음 확인**: d",
            True,
            True,
            None,
        ),
        (
            "시장: a\n둘째 줄\n선택한 ETF: b\nAI 의견: c\n최신 자료와 다음 확인: d",
            True,
            True,
            None,
        ),
        ("머리말\n" + FULL, True, False, "첫 칸 앞"),
        (FULL + "\n덧붙임: 매수 추천", True, False, "확인 표지 뒤"),
        (
            "선택한 ETF: b\n시장: a\nAI 의견: c\n최신 자료와 다음 확인: d",
            True,
            False,
            "순서",
        ),
        (
            "시장: a\n시장: b\n선택한 ETF: b\nAI 의견: c\n최신 자료와 다음 확인: d",
            True,
            False,
            "순서",
        ),
        ("시장: a\n선택한 ETF: b\n최신 자료와 다음 확인: d", True, False, "순서"),
        ("시장: a\n선택한 ETF: b", True, False, "빠짐"),
        ("시장: a\n선택한 ETF: b\n최신 자료와 다음 확인: d", False, True, None),
        (FULL, False, False, "순서"),
    ],
)
def test_parse_sections(text, with_ai, ok, why):
    sections, _mark, reason = JU.parse_sections(text, with_ai)
    assert (sections is not None) is ok
    if why:
        assert why in reason


def test_parse_keeps_lines():
    s, mark, _ = JU.parse_sections(
        "시장: a\n  들여쓴 둘째 줄\n" + FULL.split("\n", 1)[1], True
    )
    assert s["시장"] == "a\n  들여쓴 둘째 줄" and mark == "S-1 · E-1"


META = {
    "end_date": "2026-11-20",
    "condition": "c",
    "selected": {"ticker": "T1", "name": "<b>이름</b>", "rank": 1},
    "answer_authors": ["GPT"],
    "model": PR.MODEL,
}
MAIN = {
    "content": FULL,
    "model_digest": "d" * 64,
    "ended_at": "t",
    "status": "COMPLETED",
}


def test_render_escapes_and_is_deterministic():
    main = {**MAIN, "content": FULL.replace("시장: a", "시장: <script>x</script>")}
    page = RE.render_html(META, main)
    assert (
        "<script>x" not in page and "&lt;script&gt;" in page and "&lt;b&gt;이름" in page
    )
    assert RE.render_html(META, main) == page
    assert "확인 표지: S-1 · E-1" in page  # 표지 줄도 그대로 보인다


@pytest.mark.parametrize(
    "content",
    [
        "결론 먼저: 지금 매수 추천합니다.\n" + FULL,
        FULL + "\n덧붙임: AI 들이 모두 동의했습니다. 전량 매수.",
        "최신 자료와 다음 확인: d\n선택한 ETF: b\nAI 의견: c\n시장: a",
        "아무 형식 없음",
    ],
)
def test_render_shows_whole_raw_output_when_format_differs(content):
    page = RE.render_html(META, {**MAIN, "content": content})
    assert "형식이 예상과 다름" in page
    for line in content.splitlines():
        assert (
            RE._esc(line) in page
        )  # 원문 줄이 모두 보인다(숨기거나 순서를 바꾸지 않음)


def test_render_no_answers_has_no_ai_section():
    meta = {**META, "answer_authors": []}
    text = "시장: a\n선택한 ETF: b\n최신 자료와 다음 확인: d"
    page = RE.render_html(meta, {**MAIN, "content": text})
    assert "<h2>AI 의견</h2>" not in page and RE.NO_ANSWER_NOTE in page
    assert "형식이 예상과 다름" in RE.render_html(
        meta, MAIN
    )  # 답이 없는데 AI 의견을 쓰면 원문 그대로


# ── 로그 · 연결 ─────────────────────────────────────────────────────────────────


def test_log_segment_reads_only_live_and_real_truncation(tmp_path):
    log = tmp_path / "server.log"
    log.write_text("옛 줄 truncated = 1\n", encoding="utf-8")
    start = IO.log_size(log)
    assert IO.log_segment(log, start)["trunc"] is None  # 이번 호출 기록 없음 = 못 읽음
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(
            '[GIN] | POST "/api/chat"\nslot release: n_tokens = 9, truncated = 0\n'
        )
    seg = IO.log_segment(log, start)
    assert (
        seg["live"] and seg["trunc"] == [] and seg["release_ok"] == 1
    )  # 정상 줄은 잘림 아님
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(
            'level=WARN msg="truncating input prompt"\nslot release: truncated = 3\n'
        )
    assert len(IO.log_segment(log, start)["trunc"]) == 2
    assert IO.log_segment(tmp_path / "없음.log", 0)["trunc"] is None
    assert IO.log_segment(None, None)["trunc"] is None


def test_local_only_hosts():
    for ok in (
        "http://127.0.0.1:11434",
        "http://localhost:11434",
        "http://[::1]:11434",
    ):
        IO.check_local(ok)
    for bad in (
        "http://192.168.0.2:11434",
        "http://example.com",
        "http://127.0.0.1.evil:1",
    ):
        with pytest.raises(ValueError):
            IO.check_local(bad)


# ── AC4 · 비교표 ────────────────────────────────────────────────────────────────

RUN_OK = {
    "status": "COMPLETED",
    "main_status": "COMPLETED",
    "one_page_sha256": "p",
    "checks": {"main": {"input": [], "gpu": {"status": "GPU"}}},
}


def _side(u, d, g):
    return {
        "user_s": u,
        "dev_s": d,
        "elapsed_s": u + 300,
        "reopen": 1,
        "fixes": [],
        "answers": dict(zip(("direction", "limits", "next"), g)),
        "reuse": "예",
    }


def _usage(**over):
    u = {"L": _side(200, 60, ("맞음",) * 3), "U": _side(400, 0, ("맞음",) * 3)}
    for k, v in over.items():
        s, f = k.split("_", 1)
        if v == "DEL":
            u[s].pop(f)
        else:
            u[s][f] = v
    return u


@pytest.mark.parametrize(
    "score, over, run, verdict, reason",
    [
        ({"critical_errors": 0}, {}, RUN_OK, "사용 이점 관찰", None),
        ({"critical_errors": 1}, {}, RUN_OK, "품질 미달", None),
        ({"critical_errors": None}, {}, RUN_OK, "판정 불가", "채점 없음"),
        ({"critical_errors": 0}, {}, None, "판정 불가", "보관되지 않음"),
        (
            {"critical_errors": 0},
            {},
            {**RUN_OK, "main_status": "INPUT_UNCONFIRMED"},
            "판정 불가",
            "완료가 아님",
        ),
        (
            {"critical_errors": 0},
            {"L_user_s": None},
            RUN_OK,
            "사용 이점 미확인",
            "실측이 빠짐",
        ),
        ({"critical_errors": 0}, {"U_dev_s": "DEL"}, RUN_OK, "사용 이점 관찰", None),
        ({"critical_errors": 0}, {"L_user_s": 312.5}, RUN_OK, "사용 이점 관찰", None),
        (
            {"critical_errors": 0},
            {"L_user_s": 400},
            RUN_OK,
            "사용 이점 미확인",
            "직접 시간",
        ),
        (
            {"critical_errors": 0},
            {"L_dev_s": 300},
            RUN_OK,
            "사용 이점 미확인",
            "총 사람 시간",
        ),
        (
            {"critical_errors": 0},
            {"L_fixes": ["a"]},
            RUN_OK,
            "사용 이점 미확인",
            "사실 수정",
        ),
        (
            {"critical_errors": 0},
            {"L_reuse": "모르겠음"},
            RUN_OK,
            "사용 이점 미확인",
            "다시 쓰겠다",
        ),
        (
            {"critical_errors": 0},
            {"L_answers": {"direction": "부분", "limits": "맞음", "next": "맞음"}},
            RUN_OK,
            "사용 이점 미확인",
            "U 보다 낮음",
        ),
        (
            {"critical_errors": 0},
            {
                "L_answers": {"direction": "틀림", "limits": "맞음", "next": "맞음"},
                "U_answers": {"direction": "틀림", "limits": "맞음", "next": "맞음"},
            },
            RUN_OK,
            "사용 이점 미확인",
            "틀림",
        ),
    ],
)
def test_ac4(score, over, run, verdict, reason):
    v = RP.ac4(score, _usage(**over), run)
    assert v["verdict"] == verdict
    if reason:
        assert any(reason in r for r in v["reasons"])


@pytest.mark.parametrize("bad", [-1, "3분", True])
def test_bad_seconds_are_errors_not_unmeasured(bad):
    with pytest.raises(ValueError):
        RP.ac4({"critical_errors": 0}, _usage(L_user_s=bad), RUN_OK)


def test_table_marks_unmeasured_and_run():
    t = RP.table_md(
        {"critical_errors": 0}, _usage(L_elapsed_s=None), RUN_OK, answers=False
    )
    assert (
        "| 전체 경과(모델 대기 포함) | 미측정 |" in t
        and "긴 AI 답 대조의 효용 미측정" in t
    )
    assert "| 총 사람 시간 | 4분 20.0초 | 6분 40.0초 |" in t
    assert "| 한 장 최초 출력 중요한 오류 | 0건 | — |" in t
    assert "| 본 요약 실행 | COMPLETED | — |" in t and "GPU GPU" in t
    t2 = RP.table_md({"critical_errors": 0}, _usage(), None, answers=True)
    assert "보관 안 됨" in t2 and "판정 불가" in t2


# ── 경계 ───────────────────────────────────────────────────────────────────────


def _in_try(tree, target) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            blocks = [*node.body, *node.handlers]
            if any(target is n for b in blocks for n in ast.walk(b)):
                return True
    return False


def test_shipped_code_is_stdlib_only():
    allowed = set(sys.stdlib_module_names) | {"__future__"}
    for mod in (RW, JU, RE, IO):
        tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)) and not _in_try(
                tree, node
            ):
                names = (
                    [a.name for a in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module]
                )
                assert all(n.split(".")[0] in allowed for n in names), (
                    mod.__name__,
                    names,
                )


def test_options_only_lengths():
    with pytest.raises(ValueError, match="바꿀 수 없는"):
        PR.options({"seed": 1})
    with pytest.raises(ValueError, match="num_predict"):
        PR.options({"num_ctx": 1000, "num_predict": 2000})
    assert PR.options({"num_ctx": 65536})["num_ctx"] == 65536


def test_parse_keeps_blank_lines_inside_sections():
    s, _m, _w = JU.parse_sections(
        "시장: a\n\n둘째 문단\n" + FULL.split("\n", 1)[1], True
    )
    assert s["시장"] == "a\n\n둘째 문단"


def test_broken_chars_are_a_model_problem():
    content = FULL.replace("a\n", f"{KOREAN}\ufffd\n", 1)
    assert "깨진 글자(\ufffd)가 있음" in JU.model_problems(content, MARKS, True)


def test_raw_view_shows_mark_once():
    page = RE.render_html(META, {**MAIN, "content": "머리말\n" + FULL})
    assert page.count("확인 표지: S-1 · E-1") == 1


@pytest.mark.parametrize(
    "bad", [{"num_ctx": -1}, {"num_ctx": True}, {"num_predict": "x"}]
)
def test_length_values_must_be_positive_ints(bad):
    with pytest.raises(ValueError, match="양의 정수"):
        PR.options(bad)


def test_bad_counts_are_errors_and_missing_items_listed():
    with pytest.raises(ValueError):
        RP.ac4({"critical_errors": -1}, _usage(), RUN_OK)
    with pytest.raises(ValueError):
        RP.table_md({"critical_errors": 0}, _usage(L_reopen=-2), RUN_OK, answers=True)
    t = RP.table_md({"critical_errors": 0}, _usage(L_user_s=None), RUN_OK, answers=True)
    assert "판정 불가(항목): L.user_s" in t
