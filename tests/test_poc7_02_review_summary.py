"""POC7-02 로컬 AI 주간 검토 요약 — 맥북 모의 시험(흐름: 보관 · 묶음 · Windows 실행기 · 회수).

가짜 Ollama 서버 · 가짜 nvidia-smi · ollama ps · tmp 연구 폴더만 쓴다. 라이브 DB · 운영 서버 · 실제 연구 폴더는
열지 않는다. Windows 실행기는 같은 코드를 이 프로세스 안에서 돌린다. 단위 시험은 `_units.py`.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import sys
import threading
import zipfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from app.entry_timing.protocol import CheckRequired
from app.review_summary import bundle as BU
from app.review_summary import case as CA
from app.review_summary import judge as JU
from app.review_summary import merge as ME
from app.review_summary import prompt as PR
from app.review_summary import render as RE
from app.review_summary import runner_win as RW
from app.review_summary import trial as TR

NOW = datetime(2026, 11, 23, 10, 0, 0, tzinfo=CA.KST)
TICKER = "T09999"
GOOD_LINES = [
    "시장: 시장 판정은 11/20 기준이다. 〔근거 1〕",
    "선택한 ETF: 1개월 올랐다. 〔근거 2〕",
    "AI 의견: GPT 는 방향, Claude 는 속도를 설명했다. 〔GPT 이유 · Claude 이유〕",
    "최신 자료와 다음 확인: 최신 공개 자료 확인 불가 · 저장 자료 11/19. 다음 확인: 외국인 수급.",
]


# ── 가짜 맥북 서버 응답 · 가짜 Ollama ────────────────────────────────────────────


def weekly_response(**over) -> bytes:
    syn = TR.build(0)
    body = {
        "status": "ok",
        "source_screen": "today_weekly_review",
        "generated_at": "2026-11-23T09:59:00+09:00",
        "end_date": "2026-11-20",
        "condition": {"line": "1개월 상위 30개(선정 순서) · 10/21 → 11/20"},
        "selected": {"ticker": TICKER, "name": "시험 ETF", "rank": 2},
        "selected_missing": False,
        "copy_text": syn["copy_text"],
        "evidence": [
            {"no": 1, "group": "market", "key": "regime_morning", "text": "x"}
        ],
        "market_evidence": {
            "status": "partial",
            "data_status": ["코스피 11/19까지(기대 11/20 · 늦음)"],
        },
    }
    body.update(over)
    return json.dumps(body, ensure_ascii=False).encode("utf-8")


class Fake:
    """가짜 Ollama — 설정(cfg)으로 갈래를 만든다 · 받은 요청을 calls 에 남긴다 · 실제처럼 log 를 쓴다."""

    def __init__(self, log: Path) -> None:
        self.cfg: dict = {}
        self.calls: list[tuple[str, str, dict]] = []
        self.log = log
        self.loaded = False

    def _log(self, *lines: str, counting: bool = False) -> None:
        if self.cfg.get("silent_log") or (
            counting and self.cfg.get("count_silent_log")
        ):
            return
        with open(self.log, "a", encoding="utf-8") as fh:
            fh.write("".join(f"{ln}\n" for ln in lines))

    def reply(self, body: dict) -> dict:
        cfg, msgs = self.cfg, body["messages"]
        n = sum(len(m["content"]) for m in msgs) // 2
        self.loaded = body.get("keep_alive") != 0
        user = msgs[-1]["content"]
        trial = "· 보관 합성]" in user
        counting = body["options"].get("num_predict") == 1
        bad = not trial and (
            cfg.get("trunc") or (cfg.get("main_trunc") and not counting)
        )
        self._log(
            '[GIN] 2026/11/23 - 10:00:00 | 200 | 1s | 127.0.0.1 | POST "/api/chat"',
            "slot release: id 0 | task 1 | stop processing: "
            f"n_tokens = {n}, truncated = {1 if bad else 0}",
            counting=counting,
        )
        if counting:
            if cfg.get("count_404"):
                raise KeyError("count")
            if cfg.get("count_no_tokens"):
                return {"done_reason": "length", "model": body["model"], "message": {}}
            return {
                "prompt_eval_count": n + cfg.get("count_delta", 0),
                "eval_count": 1,
                "done_reason": "length",
                "model": body["model"],
                "message": {"content": ""},
            }
        start = re.search(r"입력 맨 앞 표지: (S-[0-9a-f]{8})", user).group(1)
        end = re.search(r"입력 맨 뒤 표지: (E-[0-9a-f]{8})", user).group(1)
        lines = list(GOOD_LINES)
        if "[AI 답 없음" in user:
            lines.pop(2)
        no_marks = cfg.get("no_marks") if trial else cfg.get("main_no_marks")
        if not no_marks:
            lines.append(f"확인 표지: {start} · {end}")
        content = "\n".join(lines)
        if trial and cfg.get("bad_korean"):
            content = "Market: ??? �\nSelected: ok"
        return {
            "model": body["model"],
            "message": {"role": "assistant", "content": content, "thinking": "생각"},
            "done_reason": cfg.get("trial_done" if trial else "main_done", "stop"),
            "prompt_eval_count": n,
            "eval_count": 300,
            "total_duration": 10,
        }

    def handle(self, method: str, path: str, body: dict):
        self.calls.append((method, path, body))
        if path == "/api/version":
            self.version_calls = getattr(self, "version_calls", 0) + 1
            if self.cfg.get("no_version") or (
                self.cfg.get("version_gone") and self.version_calls > 1
            ):
                return {}
            late = self.cfg.get("version_change") and self.version_calls > 1
            return {"version": "0.41.0" if late else "0.40.17"}
        if path == "/api/tags":
            models = [
                {"name": PR.MODEL, "digest": "d" * 64, "size": 6600, "modified_at": "m"}
            ]
            if self.cfg.get("no_model"):
                models = []
            self.tags_calls = getattr(self, "tags_calls", 0) + 1
            if self.cfg.get("no_digest"):
                models[0].pop("digest")
            if self.cfg.get("bad_digest"):
                models[0]["digest"] = "abc"
            if self.cfg.get("digest_change") and self.tags_calls > 1:
                models[0]["digest"] = "e" * 64  # 토큰 세기 뒤(본 요약 직전) 바뀜
            if self.cfg.get("digest_change_after") and self.tags_calls > 2:
                models[0]["digest"] = "e" * 64  # 본 요약 뒤 바뀜
            if self.cfg.get("digest_gone") and self.tags_calls > 1:
                models[0].pop("digest")
            if self.cfg.get("other_digest"):
                models[0]["digest"] = "f" * 64  # 처음부터 다른 모델(다시 받음)
            if self.cfg.get("other_model"):
                models = [{"name": "qwen3.5:9b", "digest": "e" * 64, "size": 7000}]
            return {"models": models}
        if path == "/api/ps":
            if not self.loaded:
                return {"models": []}
            m = {"name": PR.MODEL, "model": PR.MODEL, "size": 8000}
            m["size_vram"] = self.cfg.get("vram", 8000)
            if not self.cfg.get("no_ctx"):
                m["context_length"] = self.cfg.get("ctx", PR.OPTIONS["num_ctx"])
            return {"models": [m]}
        if path == "/api/chat":
            return self.reply(body)
        if path == "/api/generate":
            self.loaded = False
            return {"done": True}
        raise KeyError(path)


@pytest.fixture
def ollama(tmp_path):
    log = tmp_path / "server.log"
    log.write_text("", encoding="utf-8")
    fake = Fake(log)

    class H(BaseHTTPRequestHandler):
        def _go(self, method):
            size = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(size)) if size else {}
            try:
                out = json.dumps(fake.handle(method, self.path, body)).encode()
                code = 200
            except KeyError:
                out, code = b"{}", 404
            broken = (
                fake.cfg.get("broken_main")
                and self.path == "/api/chat"
                and body.get("options", {}).get("num_predict") != 1
                and "· 보관 합성]" not in body["messages"][-1]["content"]
            )
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out) + (500 if broken else 0)))
            self.end_headers()
            self.wfile.write(out[:20] if broken else out)

        def do_GET(self):
            self._go("GET")

        def do_POST(self):
            self._go("POST")

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, args=(0.02,), daemon=True).start()
    fake.url = f"http://127.0.0.1:{srv.server_address[1]}"
    yield fake
    srv.shutdown()


def tool(tmp_path: Path, name: str, body: str) -> str:
    p = tmp_path / name
    p.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return str(p)


def smi(tmp_path: Path, driver: str = "566.36", name: str = "nvidia-smi") -> str:
    return tool(
        tmp_path,
        name,
        f'case "$1" in *name*) echo "NVIDIA GeForce RTX 4070 SUPER, {driver}, 12282";;\n'
        '  *) echo "57, 7400";;\nesac\n',
    )


@pytest.fixture
def tools(tmp_path):
    cli = tool(
        tmp_path,
        "ollama",
        'echo "NAME  ID  SIZE  PROCESSOR  CONTEXT  UNTIL"\n'
        'echo "qwen3.5:9b-q4_K_M  abc  8.0 GB  100% GPU  49152  4 minutes"\n',
    )
    return {"smi": smi(tmp_path), "cli": cli}


@pytest.fixture
def root(tmp_path):
    r = (tmp_path / "research").resolve()
    r.mkdir()
    return r


ANSWERS = (("GPT", "GPT 답 본문".encode()), ("Claude", "Claude 답 본문".encode()))


def make_case(root, answers=ANSWERS):
    d = CA.archive(
        root,
        response=weekly_response(),
        selected=TICKER,
        answers=answers,
        source="시험",
        now=NOW,
    )
    CA.lock_key(root, d.name, "채점용 메모 — 필수 ① 기준일".encode(), now=NOW)
    return d.name


def unzip(bdir: Path, dest: Path) -> Path:
    with zipfile.ZipFile(bdir / "bundle.zip") as z:
        z.extractall(dest)
    return dest


def run_win(bdir: Path, ollama, tools, *extra) -> int:
    return RW.main(
        [
            "--bundle-dir",
            str(bdir),
            "--ollama",
            ollama.url,
            "--nvidia-smi",
            tools["smi"],
            "--ollama-cli",
            tools["cli"],
            "--server-log",
            str(ollama.log),
            *extra,
        ]
    )


@pytest.fixture
def packed(root, tmp_path):
    cid = make_case(root)
    bd = BU.pack(root, cid, now=NOW)
    return cid, bd, unzip(bd, tmp_path / "win")


def result(win: Path, n: int = 1) -> dict:
    return json.loads((win / f"result_{n}" / "result.json").read_text(encoding="utf-8"))


def rewrite(win: Path, n: int, change) -> Path:
    """result.json 을 고치고 hashes.json 을 다시 맞춘다(사람이 일부러 고친 경우 흉내)."""
    rd = win / f"result_{n}"
    r = result(win, n)
    change(r)
    (rd / "result.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    h = json.loads((rd / "hashes.json").read_text(encoding="utf-8"))
    for f in ("result.json", "one_page.html"):
        if (rd / f).exists():
            h[f] = RW.sha_bytes((rd / f).read_bytes())
    (rd / "hashes.json").write_text(json.dumps(h), encoding="utf-8")
    return rd


# ── 보관 · 잠금 ─────────────────────────────────────────────────────────────────


def test_archive_keeps_response_and_answers(root):
    raw = weekly_response()
    d = CA.archive(
        root,
        response=raw,
        selected=TICKER,
        answers=[("GPT", b"g")],
        source="s",
        now=NOW,
    )
    assert (d / "response.json").read_bytes() == raw
    c = CA.load_case(root, d.name)
    assert c["selected"] == {"ticker": TICKER, "name": "시험 ETF", "rank": 2}
    assert c["data_status"] == ["코스피 11/19까지(기대 11/20 · 늦음)"]
    assert c["answer_texts"] == [{"author": "GPT", "text": "g"}]
    assert c["archived_at"] == "2026-11-23T10:00:00+09:00"


@pytest.mark.parametrize(
    "over, sel, answers, msg",
    [
        ({"status": "error"}, TICKER, (), "ok 가 아님"),
        ({}, "T00000", (), "고른 ETF"),
        ({"selected_missing": True}, TICKER, (), "고른 ETF"),
        ({"copy_text": "근거 없음"}, TICKER, (), "근거 번호"),
        ({"evidence": []}, TICKER, (), "evidence"),
        ({}, TICKER, (("Bard", b"x"),), "작성자"),
        ({}, TICKER, (("GPT", b"x"), ("GPT", b"y")), "두 번"),
        ({}, TICKER, (("GPT", b"  "),), "비었거나"),
        ({}, TICKER, (("GPT", b"\xff"),), "UTF-8"),
    ],
)
def test_archive_refuses_bad_input(root, over, sel, answers, msg):
    with pytest.raises(CheckRequired, match=msg):
        CA.archive(
            root,
            response=weekly_response(**over),
            selected=sel,
            answers=answers,
            source="s",
            now=NOW,
        )
    assert not (root / "cases").exists() or not any((root / "cases").iterdir())


def test_archive_refuses_symlinked_root(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    with pytest.raises(CheckRequired, match="심볼릭"):
        CA.archive(
            link, response=weekly_response(), selected=TICKER, source="s", now=NOW
        )
    assert list(real.iterdir()) == []


def test_fetch_weekly_only_local_server():
    with pytest.raises(CheckRequired, match="맥북 서버"):
        CA.fetch_weekly("http://192.168.0.9:8000", TICKER)


@pytest.mark.parametrize(
    "edit, msg",
    [
        (lambda c: c["selected"].update(name="조작 ETF"), "'selected'"),
        (lambda c: c.update(end_date="2026-12-31"), "'end_date'"),
        (lambda c: c.update(condition="조작"), "'condition'"),
        (lambda c: c.update(data_status=[]), "'data_status'"),
        (lambda c: c.update(answers=c["answers"][:1]), "답 파일"),
    ],
)
def test_load_case_checks_every_field_against_response(root, edit, msg):
    d = CA.archive(
        root,
        response=weekly_response(),
        selected=TICKER,
        answers=[("GPT", b"g"), ("Claude", b"c")],
        source="s",
        now=NOW,
    )
    c = json.loads((d / "case.json").read_text(encoding="utf-8"))
    edit(c)
    (d / "case.json").write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(CheckRequired, match=msg):
        CA.load_case(root, d.name)


def test_load_case_detects_tampered_answer(root):
    d = CA.archive(
        root,
        response=weekly_response(),
        selected=TICKER,
        answers=[("GPT", b"g")],
        source="s",
        now=NOW,
    )
    (d / "answers" / "GPT.txt").write_bytes(b"changed")
    with pytest.raises(CheckRequired, match="GPT 답 해시"):
        CA.load_case(root, d.name)


def test_key_lock_once_before_pack_and_not_after(root):
    d = CA.archive(
        root, response=weekly_response(), selected=TICKER, source="s", now=NOW
    )
    with pytest.raises(CheckRequired, match="lock-key"):
        BU.pack(root, d.name, now=NOW)
    CA.lock_key(root, d.name, "메모".encode(), now=NOW)
    with pytest.raises(FileExistsError):
        CA.lock_key(root, d.name, "다른 메모".encode(), now=NOW)
    BU.pack(root, d.name, now=NOW)
    for f in ("answer_key.md", "key_lock.json"):
        (d / f).unlink()
    with pytest.raises(CheckRequired, match="묶음을 만든 뒤"):
        CA.lock_key(root, d.name, "출력을 본 뒤 메모".encode(), now=NOW)


def test_pack_refuses_tampered_key(root):
    cid = make_case(root)
    (root / "cases" / cid / "answer_key.md").write_bytes("고친 메모".encode())
    with pytest.raises(CheckRequired, match="메모 해시"):
        BU.pack(root, cid, now=NOW)


# ── 묶음 ────────────────────────────────────────────────────────────────────────


def test_pack_contents_and_marks(root, packed):
    cid, bd, win = packed
    with zipfile.ZipFile(bd / "bundle.zip") as z:
        names = sorted(z.namelist())
    extra = ["run_summary.bat", "README_KO.txt", "bundle_input.json", "manifest.json"]
    assert names == sorted([*BU.SHIPPED, *extra])
    man = json.loads((win / "manifest.json").read_text(encoding="utf-8"))
    for n, sha in man["files"].items():
        assert RW.sha_bytes((win / n).read_bytes()) == sha
    assert (win / "review_ollama.py").read_bytes() == BU.SHIPPED[
        "review_ollama.py"
    ].read_bytes()
    inp = json.loads((win / "bundle_input.json").read_text(encoding="utf-8"))
    start, end = inp["main"]["marks"]
    sysm, user = inp["main"]["messages"]
    assert sysm["content"].startswith(f"[실행 표지 {start}]")
    assert user["content"].startswith(f"[입력 맨 앞 표지: {start}]")
    assert user["content"].endswith(f"[입력 맨 뒤 표지: {end}]")
    assert "[원문 2 · GPT 답]\nGPT 답 본문" in user["content"]
    assert inp["trial"]["input_chars"] >= max(TR.MIN_CHARS, inp["main"]["input_chars"])
    assert inp["trial"]["marks"] != inp["main"]["marks"]
    assert inp["options"] == PR.OPTIONS and inp["think"] is True
    assert inp["model"] == "qwen3.5:9b-q4_K_M"
    bat = (win / "run_summary.bat").read_bytes().decode("utf-8")
    assert (
        'py -3 -c "import sys"' in bat
        and 'python -c "import sys"' in bat
        and "\r\n" in bat
    )
    rec = json.loads((bd / "pack.json").read_text(encoding="utf-8"))
    assert isinstance(rec["dev_ms"], int) and rec["prior_bundles"] == []


def test_trial_is_at_least_as_long_as_a_long_case(root):
    long_copy = TR.build(0)["copy_text"] + "\n" + ("[근거 99] 긴 줄 " * 3000)
    d = CA.archive(
        root,
        response=weekly_response(copy_text=long_copy),
        selected=TICKER,
        source="s",
        now=NOW,
    )
    CA.lock_key(root, d.name, b"key", now=NOW)
    bd = BU.pack(root, d.name, now=NOW)
    inp = json.loads((bd / "bundle_input.json").read_text(encoding="utf-8"))
    assert inp["main"]["input_chars"] > TR.MIN_CHARS + 10000
    assert inp["trial"]["input_chars"] >= inp["main"]["input_chars"]


def test_first_bundle_keeps_start_settings(root):
    cid = make_case(root)
    with pytest.raises(CheckRequired, match="첫 묶음은 시작 설정"):
        BU.pack(root, cid, lengths={"num_ctx": 65536}, reason="r", now=NOW)


def test_new_bundle_rules_after_trial_stop(root, packed, ollama, tools, tmp_path):
    cid, _bd, win = packed
    ollama.cfg = {"ctx": 8192}  # 합성 점검 설정 문제
    assert run_win(win, ollama, tools) == 2
    for kw in (
        {},
        {"reason": "아직 회수 전"},
        {"lengths": {"num_ctx": 65536}, "reason": "r"},
    ):
        with pytest.raises(
            CheckRequired, match="먼저 회수"
        ):  # 회수 전 새 묶음 없음(F2 · 예외 없음)
            BU.pack(root, cid, now=NOW, **kw)
    ME.merge(root, cid, win / "result_1", now=NOW)
    with pytest.raises(CheckRequired, match="사유"):
        BU.pack(root, cid, now=NOW)
    with pytest.raises(ValueError, match="바꿀 수 없는"):
        BU.pack(root, cid, lengths={"temperature": 0}, reason="r", now=NOW)
    bd2 = BU.pack(
        root, cid, lengths={"num_ctx": 65536}, reason="합성 점검: 문맥 부족", now=NOW
    )
    rec = json.loads((bd2 / "pack.json").read_text(encoding="utf-8"))
    assert rec["options"]["num_ctx"] == 65536 and rec["after_run"]
    with pytest.raises(CheckRequired, match="먼저 회수"):
        BU.pack(root, cid, reason="USB 결과 분실", now=NOW)
    ollama.cfg = {"ctx": 8192}
    win2 = unzip(bd2, tmp_path / "w2")
    assert run_win(win2, ollama, tools) == 2
    ME.merge(root, cid, win2 / "result_1", now=NOW)
    bd3 = BU.pack(root, cid, reason="다시 점검", now=NOW)  # 앞 묶음 길이를 이어받는다
    assert (
        json.loads((bd3 / "pack.json").read_text(encoding="utf-8"))["options"][
            "num_ctx"
        ]
        == 65536
    )


def test_no_new_bundle_after_a_rerunnable_stop(root, packed, ollama, tools, tmp_path):
    """환경 멈춤은 같은 폴더에서 다시 돌린다 — 그 폴더에 첫 본 요약이 생길 수 있어 새 묶음 · 길이 변경 없음(검토 D)."""
    cid, _bd, win = packed
    assert (
        run_win(win, ollama, {**tools, "smi": smi(tmp_path, "531.18", "old-smi")}) == 2
    )
    assert result(win)["trial"]["gate"]["categories"] == ["ENV"]
    ME.merge(root, cid, win / "result_1", now=NOW)
    for kw in ({"lengths": {"num_ctx": 65536}}, {}):
        with pytest.raises(CheckRequired, match="같은 폴더에서 다시 돌리는 멈춤"):
            BU.pack(root, cid, reason="드라이버 갱신 뒤", now=NOW, **kw)


def test_no_new_bundle_after_main_and_prompt_fixed(
    root, packed, ollama, tools, monkeypatch
):
    cid, _bd, win = packed
    ollama.cfg = {"ctx": 8192}
    assert run_win(win, ollama, tools) == 2
    ME.merge(root, cid, win / "result_1", now=NOW)
    monkeypatch.setattr(PR, "SYSTEM", PR.SYSTEM + "\n추가 규칙")
    with pytest.raises(CheckRequired, match="지시문"):
        BU.pack(root, cid, reason="r", now=NOW)
    monkeypatch.undo()
    bd2 = BU.pack(root, cid, lengths={"num_ctx": 65536}, reason="문맥", now=NOW)
    win2 = unzip(bd2, win.parent / "w2")
    ollama.cfg = {"ctx": 65536}
    assert run_win(win2, ollama, tools) == 0
    ME.merge(root, cid, win2 / "result_1", now=NOW)
    with pytest.raises(CheckRequired, match="본 요약 시도가 이미 보관됨"):
        BU.pack(root, cid, reason="더 좋은 답", now=NOW)


def test_no_rerun_even_after_failed_main(root, packed, ollama, tools):
    """한 사례에 본 요약 시도는 한 번 — 실행 실패여도 새 묶음 없음(다시 실행은 설계자 판단 · PLAN §2-2)."""
    cid, _bd, win = packed
    ollama.cfg = {"main_done": "length"}
    assert run_win(win, ollama, tools) == 2
    ME.merge(root, cid, win / "result_1", now=NOW)
    for kw in (
        {"reason": "같은 설정으로 다시"},
        {"lengths": {"num_predict": 30000}, "reason": "길이"},
    ):
        with pytest.raises(CheckRequired, match="본 요약 시도가 이미 보관됨"):
            BU.pack(root, cid, now=NOW, **kw)


def test_no_answer_case_omits_ai_section(root, tmp_path, ollama, tools):
    cid = make_case(root, answers=())
    win = unzip(BU.pack(root, cid, now=NOW), tmp_path / "w")
    inp = json.loads((win / "bundle_input.json").read_text(encoding="utf-8"))
    assert PR.NO_ANSWER_LINE in inp["main"]["messages"][1]["content"]
    assert run_win(win, ollama, tools) == 0
    page = (win / "result_1" / "one_page.html").read_text(encoding="utf-8")
    assert (
        "<h2>AI 의견</h2>" not in page
        and "긴 AI 답 대조의 효용은 이번에 재지 않음" in page
    )
    ME.merge(root, cid, win / "result_1", now=NOW)


# ── Windows 실행기 ──────────────────────────────────────────────────────────────


def test_runner_completes_and_refuses_rerun(root, packed, ollama, tools):
    cid, _bd, win = packed
    assert run_win(win, ollama, tools) == 0
    res = result(win)
    assert res["status"] == JU.COMPLETED and res["result_dir"] == "result_1"
    j = res["main"]["judgement"]
    assert (
        j["marks_echoed"] is True and j["gpu"]["status"] == JU.GPU and j["input"] == []
    )
    assert (
        res["main"]["trunc_log"] == []
        and res["main"]["log_evidence"]["release_ok"] >= 1
    )
    assert (
        res["env"]["model"]["digest"] == "d" * 64
        and res["env"]["gpu"]["driver"] == "566.36"
    )
    assert res["trial"]["gate"] == {"ok": True, "reasons": [], "categories": []}
    assert res["trial"]["chars_per_token"] > 1.9
    chats = [b for m, p, b in ollama.calls if p == "/api/chat"]
    assert [c["options"]["num_predict"] for c in chats] == [
        24576,
        1,
        24576,
    ]  # 합성 · 세기 · 본
    assert [c["keep_alive"] for c in chats] == ["5m", 0, "5m"]
    assert all(c["think"] is True and c["stream"] is False for c in chats)
    assert (
        res["main"]["unload"]["gone"] is True and res["count"]["unload"]["gone"] is True
    )
    page = (win / "result_1" / "one_page.html").read_text(encoding="utf-8")
    assert "선택한 ETF: 시험 ETF(T09999) · 2위" in page and "GPT 는 방향" in page
    assert run_win(win, ollama, tools) == 2  # 같은 묶음 다시 = 모델 호출 없이 멈춤
    again = result(win, 2)
    assert (
        again["status"] == RW.ALREADY_RAN
        and again["prior_results"][0]["main_started"] is True
    )
    assert sum(1 for _m, p, _b in ollama.calls if p == "/api/chat") == 3
    out = ME.merge(root, cid, win / "result_1", now=NOW)
    rec = json.loads((out / "merge.json").read_text(encoding="utf-8"))
    assert rec["status"] == JU.COMPLETED and rec["has_main"]
    assert rec["checks"]["repo_code_same_as_bundle"] is True
    assert out.name == f"{res['bundle_id']}__{res['run_id']}"
    assert (out / "one_page.html").read_bytes() == (
        win / "result_1" / "one_page.html"
    ).read_bytes()
    with pytest.raises(FileExistsError):
        ME.merge(root, cid, win / "result_1", now=NOW)
    ME.merge(root, cid, win / "result_2", now=NOW)  # 멈춘 기록도 보관


@pytest.mark.parametrize(
    "cfg, status, has_main, why, kinds",
    [
        ({"no_model": True}, RW.NEED_MODEL, False, None, None),
        ({"other_model": True}, RW.NEED_MODEL, False, None, None),
        ({"vram": 0}, RW.TRIAL_STOPPED, False, "CPU_ONLY", ["ENV", "SETTINGS"]),
        (
            {"trial_done": "length"},
            RW.TRIAL_STOPPED,
            False,
            "출력 길이 초과",
            ["SETTINGS"],
        ),
        ({"ctx": 8192}, RW.TRIAL_STOPPED, False, "할당 문맥 8192", ["SETTINGS"]),
        ({"bad_korean": True}, RW.TRIAL_STOPPED, False, "한글 출력", ["MODEL"]),
        ({"no_marks": True}, RW.TRIAL_STOPPED, False, "복창", ["MODEL"]),
        ({"silent_log": True}, RW.TRIAL_STOPPED, False, "이번 호출 기록 없음", ["ENV"]),
        (
            {"no_ctx": True, "_bare_cli": True},
            RW.TRIAL_STOPPED,
            False,
            "미기록",
            ["ENV"],
        ),
        ({"main_done": "length"}, JU.TECHNICAL_FAILURE, True, "출력 길이 초과", None),
        (
            {"trunc": True},
            RW.PRE_MAIN_STOPPED,
            False,
            "토큰 세기의 server.log 잘림",
            None,
        ),
        ({"main_trunc": True}, JU.INPUT_UNCONFIRMED, True, "server.log 잘림", None),
        ({"count_delta": 5}, JU.INPUT_UNCONFIRMED, True, "두 번 센", None),
        ({"broken_main": True}, JU.TECHNICAL_FAILURE, True, "호출 오류", None),
        ({"vram": 4000}, JU.COMPLETED, True, None, None),
        ({"main_no_marks": True}, JU.COMPLETED, True, None, None),
        ({"no_ctx": True}, JU.COMPLETED, True, None, None),
    ],
)
def test_runner_branches_are_kept_and_mergeable(
    root, packed, ollama, tools, tmp_path, cfg, status, has_main, why, kinds
):
    cid, _bd, win = packed
    ollama.cfg = {k: v for k, v in cfg.items() if not k.startswith("_")}
    if cfg.get("_bare_cli"):
        tools = {
            **tools,
            "cli": tool(tmp_path, "ollama-bare", 'echo "NAME  ID  SIZE  UNTIL"\n'),
        }
    rc = run_win(win, ollama, tools)
    res = result(win)
    assert res["status"] == status and rc == (0 if status == JU.COMPLETED else 2)
    assert (res["main"] is not None) is has_main
    assert (win / "result_1" / "one_page.html").exists() is has_main
    if why:
        part = res["main"] or res["trial"]
        text = " ".join(
            [
                *part["judgement"]["technical"],
                *part["judgement"]["input"],
                *(part.get("gate") or {}).get("reasons", []),
                *(res.get("pre_main") or {}).get("reasons", []),
            ]
        )
        assert why in text
    if kinds:
        assert res["trial"]["gate"]["categories"] == kinds
    if cfg == {"vram": 4000}:
        assert res["main"]["judgement"]["gpu"]["status"] == JU.MIXED
    if cfg == {"main_no_marks": True}:
        assert "표지 누락" in res["main"]["judgement"]["note"]
    if cfg == {"no_ctx": True}:
        assert (
            res["main"]["judgement"]["tokens"]["allocated_ctx"] == 49152
        )  # ollama ps 글
    if cfg == {"broken_main": True}:
        assert res["main"]["gpu_samples"] and res["main"]["ps"] is not None  # 진단 보존
    ME.merge(
        root, cid, win / "result_1", now=NOW
    )  # 어떤 갈래든 첫 결과를 보관할 수 있다


def test_driver_checks(packed, ollama, tools, tmp_path):
    _cid, _bd, win = packed
    assert run_win(win, ollama, {**tools, "smi": str(tmp_path / "no-smi")}) == 2
    g = result(win)["trial"]["gate"]
    assert (
        g["categories"] == ["ENV"] and "NVIDIA 드라이버 판을 읽지 못함" in g["reasons"]
    )
    assert "GPU 실행을 확인하지 못함" not in " ".join(g["reasons"])  # ps 는 읽음
    assert (
        run_win(win, ollama, {**tools, "smi": smi(tmp_path, "531.18", "old-smi")}) == 2
    )
    assert "531.18 < 551.61" in " ".join(result(win, 2)["trial"]["gate"]["reasons"])


def test_runner_stops_without_ollama_and_refuses_remote(packed, tools, tmp_path):
    _cid, _bd, win = packed

    class Down:
        url = "http://127.0.0.1:9"
        log = tmp_path / "none.log"

    assert run_win(win, Down, tools) == 2
    assert result(win)["status"] == RW.NEED_OLLAMA
    Down.url = "http://192.168.0.5:11434"
    assert run_win(win, Down, tools) == 2
    assert (
        result(win, 2)["status"] == RW.RUNNER_ERROR
        and "이 PC 안" in result(win, 2)["error"]
    )


def test_runner_ignores_proxy_settings(packed, ollama, tools, monkeypatch):
    seen: list[str] = []

    class P(BaseHTTPRequestHandler):
        def _go(self):
            seen.append(self.path)
            self.send_response(502)
            self.end_headers()

        do_GET = do_POST = _go

        def log_message(self, *a):
            pass

    proxy = ThreadingHTTPServer(("127.0.0.1", 0), P)
    threading.Thread(target=proxy.serve_forever, args=(0.02,), daemon=True).start()
    url = f"http://127.0.0.1:{proxy.server_address[1]}"
    for k in ("http_proxy", "HTTP_PROXY", "all_proxy"):
        monkeypatch.setenv(k, url)
    monkeypatch.delenv("no_proxy", raising=False)
    monkeypatch.delenv("NO_PROXY", raising=False)
    _cid, _bd, win = packed
    assert run_win(win, ollama, tools) == 0
    proxy.shutdown()
    assert seen == [] and result(win)["status"] == JU.COMPLETED


def test_runner_refuses_changed_bundle_and_merge_keeps_it(root, packed, ollama, tools):
    cid, _bd, win = packed
    p = win / "README_KO.txt"
    p.write_text(p.read_text(encoding="utf-8") + "x", encoding="utf-8")
    assert run_win(win, ollama, tools) == 2
    res = result(win)
    assert res["status"] == RW.BUNDLE_CHANGED and res["case_id"] == cid
    assert not any(p == "/api/chat" for _m, p, _b in ollama.calls)
    out = ME.merge(root, cid, win / "result_1", now=NOW)
    rec = json.loads((out / "merge.json").read_text(encoding="utf-8"))
    assert rec["checks"]["changed_files"] == ["README_KO.txt"]


def test_interrupt_and_print_failure_still_write_first_result(
    root, packed, ollama, tools, monkeypatch
):
    cid, _bd, win = packed

    def stop(*a, **k):
        raise KeyboardInterrupt

    monkeypatch.setattr(RW, "count_tokens", stop)
    with pytest.raises(KeyboardInterrupt):
        run_win(win, ollama, tools)
    assert (
        result(win)["status"] == RW.INTERRUPTED and result(win)["trial"]["gate"]["ok"]
    )
    ME.merge(root, cid, win / "result_1", now=NOW)
    monkeypatch.undo()

    def bad_print(*a, **k):
        raise UnicodeEncodeError("cp949", "—", 0, 1, "x")

    monkeypatch.setattr("builtins.print", bad_print)
    assert (
        run_win(win, ollama, tools) == 0
    )  # 앞 결과는 본 요약 없음(중단) → 이번이 본 요약
    assert result(win, 2)["status"] == JU.COMPLETED


# ── 회수 ────────────────────────────────────────────────────────────────────────


def _trial_fails_consistently(r):
    """합성 점검 원값 · 구분 · 문을 함께 '실패'로 바꿈 — 본 요약이 있으면 안 되는 조합."""
    r["trial"]["done_reason"] = "length"
    r["trial"]["judgement"] = JU.classify(
        r["trial"],
        model=PR.MODEL,
        requested_ctx=PR.OPTIONS["num_ctx"],
        marks=json.loads(Path(r["_inp"]).read_text(encoding="utf-8"))["trial"]["marks"],
        counted=False,
    )
    r["trial"]["gate"] = JU.trial_gate(
        r["trial"]["judgement"],
        content=r["trial"]["content"],
        marks=json.loads(Path(r["_inp"]).read_text(encoding="utf-8"))["trial"]["marks"],
        driver=r["env"]["gpu"]["driver"],
    )
    r.pop("_inp")


def _content_down(r):
    r["main"]["content"] = r["main"]["content"].replace("올랐다", "내렸다")


@pytest.mark.parametrize(
    "change, msg",
    [
        (_content_down, "받은 원문"),
        (
            lambda r: r["main"].update(trunc_log=["truncating input prompt"]),
            "다시 하면",
        ),
        (lambda r: r.update(case_id="20990101T000000Z_00000000"), "다른 사례"),
        (lambda r: r["meta"]["selected"].update(name="다른 ETF"), "머리 정보"),
        (lambda r: r["count"].update(prompt_eval_count=1), "세기 토큰"),
        (lambda r: r["env"]["model"].update(digest="f" * 64), "digest"),
        (lambda r: r["main"].update(model_reported="other"), "받은 원문"),
        (lambda r: r.update(result_dir="result_7"), "폴더 이름"),
        (lambda r: r.update(run_id="x"), "실행 id"),
        (lambda r: r["files"].update({"README_KO.txt": "0" * 64}), "묶음 파일 해시"),
        (lambda r: r.update(trial=None), "합성 점검 없이"),
        (lambda r: r.update(status="INPUT_UNCONFIRMED"), "결과 상태가 다름"),
        (lambda r: r["code"].update({"run_summary.py": "0" * 64}), "실행 코드 해시"),
        (lambda r: r["trial"]["judgement"].update(note="x"), "합성 점검 구분"),
        (lambda r: r["trial"]["gate"]["reasons"].append("x"), "통과 판단이 다름"),
        (_trial_fails_consistently, "통과하지 않았는데 본 요약"),
    ],
)
def test_merge_refuses_tampered_result(root, packed, ollama, tools, change, msg):
    cid, _bd, win = packed
    assert run_win(win, ollama, tools) == 0

    def go(r):
        r["_inp"] = str(win / "bundle_input.json")
        change(r)
        r.pop("_inp", None)

    rd = rewrite(win, 1, go)
    with pytest.raises(CheckRequired, match=msg):
        ME.merge(root, cid, rd, now=NOW)
    assert not (root / "cases" / cid / "runs").exists()


def test_merge_refuses_unhashed_edit_and_consistent_meta_tamper(
    root, packed, ollama, tools
):
    cid, _bd, win = packed
    assert run_win(win, ollama, tools) == 0
    rd = win / "result_1"
    orig = (rd / "result.json").read_bytes()
    r = result(win)
    r["env"]["python"] = "9.9"  # 다른 대조에 쓰이지 않는 칸 — 해시만 잡는다
    (rd / "result.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(CheckRequired, match="result.json 해시"):
        ME.merge(root, cid, rd, now=NOW)
    (rd / "result.json").write_bytes(orig)
    p = rd / "one_page.html"
    p.write_text(
        p.read_text(encoding="utf-8").replace("시험 ETF", "다른 ETF"), encoding="utf-8"
    )
    with pytest.raises(CheckRequired, match="one_page.html 해시"):
        ME.merge(root, cid, rd, now=NOW)

    def meta(res):
        res["meta"]["selected"]["name"] = "다른 ETF"
        p.write_text(RE.render_html(res["meta"], res["main"]), encoding="utf-8")

    rewrite(win, 1, meta)
    with pytest.raises(CheckRequired, match="머리 정보"):
        ME.merge(root, cid, rd, now=NOW)


def test_two_extractions_are_both_kept_and_block_the_verdict(
    root, packed, ollama, tools, tmp_path
):
    """같은 묶음을 두 폴더에 풀어 두 번 돌리면, 회수 순서로 고르지 않고 둘 다 보관한 뒤 판정을 막는다."""
    from app.review_summary import report as RP

    cid, bd, win = packed
    win2 = unzip(bd, tmp_path / "win_again")
    assert run_win(win, ollama, tools) == 0
    assert run_win(win2, ollama, tools) == 0
    first = ME.merge(root, cid, win2 / "result_1", now=NOW)
    second = ME.merge(root, cid, win / "result_1", now=NOW)
    r1 = json.loads((first / "merge.json").read_text(encoding="utf-8"))
    r2 = json.loads((second / "merge.json").read_text(encoding="utf-8"))
    assert r1["attempt_conflict"] is False and r2["attempt_conflict"] is True
    assert r2["other_main_attempts"][0]["run_id"] == r1["run_id"]
    _t, v = RP.build(root, cid, {"critical_errors": 0}, {}, answers=True)
    assert v["verdict"] == "판정 불가" and "본 요약 시도 2건" in v["reasons"][0]
    shutil.copytree(win / "result_1", tmp_path / "result_5")
    with pytest.raises(CheckRequired, match="폴더 이름"):
        ME.merge(root, cid, tmp_path / "result_5", now=NOW)


def test_merge_refuses_relocked_key(root, packed, ollama, tools):
    cid, _bd, win = packed
    assert run_win(win, ollama, tools) == 0
    d = root / "cases" / cid
    key = "출력을 본 뒤 메모".encode()
    (d / "answer_key.md").write_bytes(key)
    lock = json.loads((d / "key_lock.json").read_text(encoding="utf-8"))
    lock["key_sha256"] = RW.sha_bytes(key)
    (d / "key_lock.json").write_text(json.dumps(lock), encoding="utf-8")
    with pytest.raises(CheckRequired, match="다시 잠금"):
        ME.merge(root, cid, win / "result_1", now=NOW)


def test_merge_refuses_links_and_wrong_folder(root, packed, ollama, tools, tmp_path):
    cid, _bd, win = packed
    assert run_win(win, ollama, tools) == 0
    rd = win / "result_1"
    link = tmp_path / "result_9"
    link.symlink_to(rd)
    with pytest.raises(CheckRequired, match="결과 폴더가 아님"):
        ME.merge(root, cid, link, now=NOW)
    with pytest.raises(CheckRequired, match="결과 폴더가 아님"):
        ME.merge(root, cid, win, now=NOW)
    real = rd / "result.json"
    moved = tmp_path / "elsewhere.json"
    os.replace(real, moved)
    real.symlink_to(moved)
    with pytest.raises(CheckRequired, match="보통 파일"):
        ME.merge(root, cid, rd, now=NOW)


def test_merge_uses_bundle_code_after_repo_change(
    root, packed, ollama, tools, monkeypatch, tmp_path
):
    """뒤에 저장소 render 가 바뀌어도 앞 묶음의 첫 결과는 그 묶음에 들어간 코드로 대조된다."""
    cid, _bd, win = packed
    assert run_win(win, ollama, tools) == 0
    changed = tmp_path / "render_changed.py"
    src = Path(RE.__file__).read_text(encoding="utf-8")
    changed.write_text(
        src.replace("주간 ETF 검토 한 장 ·", "바뀐 머리 ·"), encoding="utf-8"
    )
    monkeypatch.setattr(ME, "SHIPPED", {**BU.SHIPPED, "review_render.py": changed})
    out = ME.merge(root, cid, win / "result_1", now=NOW)
    checks = json.loads((out / "merge.json").read_text(encoding="utf-8"))["checks"]
    assert (
        checks["status"] == JU.COMPLETED and checks["repo_code_same_as_bundle"] is False
    )
    assert "review_judge" not in sys.modules  # 묶음 코드를 잠깐 이은 뒤 지운다


def test_cli_flow(root, monkeypatch, capsys, tmp_path, ollama, tools):
    from scripts import run_review_summary as CLI

    monkeypatch.setattr(CA, "fetch_weekly", lambda server, sel: weekly_response())
    key = tmp_path / "key.md"
    key.write_text("메모", encoding="utf-8")

    def last() -> dict:
        return json.loads(capsys.readouterr().out.strip().splitlines()[-1][7:])

    assert CLI.main(["--root", str(root), "archive", "--selected", TICKER]) == 0
    cid = last()["case"]
    assert CLI.main(["--root", str(root), "pack", "--case", cid]) == 2  # 잠금 전
    last()
    assert (
        CLI.main(["--root", str(root), "lock-key", "--case", cid, "--key", str(key)])
        == 0
    )
    last()
    assert CLI.main(["--root", str(root), "pack", "--case", cid]) == 0
    z = Path(last()["zip"])
    win = tmp_path / "cliwin"
    with zipfile.ZipFile(z) as f:
        f.extractall(win)
    assert run_win(win, ollama, tools) == 0
    capsys.readouterr()
    rd = str(win / "result_1")
    assert CLI.main(["--root", str(root), "merge", "--case", cid, "--result", rd]) == 0
    assert last()["result_status"] == JU.COMPLETED


def test_report_ties_score_to_merged_page_and_dev_time(root, packed, ollama, tools):
    from app.review_summary import report as RP

    cid, _bd, win = packed
    usage = {
        "L": {
            "user_s": 200,
            "elapsed_s": 500,
            "reopen": 1,
            "fixes": [],
            "reuse": "예",
            "answers": {"direction": "맞음", "limits": "맞음", "next": "맞음"},
        },
        "U": {
            "user_s": 400,
            "elapsed_s": 400,
            "reopen": 2,
            "fixes": [],
            "answers": {"direction": "맞음", "limits": "맞음", "next": "맞음"},
        },
    }
    _t, v = RP.build(root, cid, {"critical_errors": 0}, usage, answers=True)
    assert v["verdict"] == "판정 불가"  # 본 요약 보관 전
    assert run_win(win, ollama, tools) == 0
    out = ME.merge(root, cid, win / "result_1", now=NOW)
    sha = json.loads((out / "merge.json").read_text(encoding="utf-8"))[
        "one_page_sha256"
    ]
    with pytest.raises(CheckRequired, match="one_page_sha256"):
        RP.build(
            root,
            cid,
            {"critical_errors": 0, "one_page_sha256": "x"},
            usage,
            answers=True,
        )
    table, v = RP.build(
        root, cid, {"critical_errors": 0, "one_page_sha256": sha}, usage, answers=True
    )
    assert (
        v["verdict"] == "사용 이점 관찰" and "명령 기록 pack 1회 · merge 1회" in table
    )


def test_merge_refuses_changed_mac_zip(root, packed, ollama, tools):
    """잠금 시각은 비교하지 않는다(맥북 시계 맞춤으로 진짜 잠금을 거부하지 않게 · 순서는 구조로 지킴)."""
    cid, bd, win = packed
    assert run_win(win, ollama, tools) == 0
    with zipfile.ZipFile(bd / "bundle.zip") as z:
        files = {n: z.read(n) for n in z.namelist()}
    files["review_judge.py"] += b"\n# changed\n"
    (bd / "bundle.zip").write_bytes(BU._zip(files))
    with pytest.raises(CheckRequired, match="맥북 묶음"):
        ME.merge(root, cid, win / "result_1", now=NOW)


@pytest.mark.parametrize(
    "cfg, change, msg",
    [
        (
            {"no_model": True},
            lambda r: r.update(status="COMPLETED", stop=None),
            "본 요약이 없는데 상태",
        ),
        (
            {"no_model": True},
            lambda r: r.update(status="TRIAL_STOPPED", stop="TRIAL_STOPPED"),
            "합성 점검 기록 없이",
        ),
        (
            {"ctx": 8192},
            lambda r: r.update(status="BUNDLE_CHANGED", stop="BUNDLE_CHANGED"),
            "묶음이 바뀐 실행인데",
        ),
    ],
)
def test_merge_refuses_wrong_stop_states(root, packed, ollama, tools, cfg, change, msg):
    cid, _bd, win = packed
    ollama.cfg = cfg
    assert run_win(win, ollama, tools) == 2
    rd = rewrite(win, 1, change)
    with pytest.raises(CheckRequired, match=msg):
        ME.merge(root, cid, rd, now=NOW)


def test_merge_refuses_trial_stopped_label_on_passing_trial(
    root, packed, ollama, tools
):
    cid, _bd, win = packed
    assert run_win(win, ollama, tools) == 0
    rd = win / "result_1"
    for f in ("one_page.html", "main_started.json", "main_raw.json"):
        (rd / f).unlink()

    def stopped(r):
        r.update(status="TRIAL_STOPPED", main=None, count=None)

    rewrite(win, 1, stopped)
    h = json.loads((rd / "hashes.json").read_text(encoding="utf-8"))
    h["one_page.html"] = None
    h["main_raw.json"] = None
    h["main_started.json"] = None
    (rd / "hashes.json").write_text(json.dumps(h), encoding="utf-8")
    with pytest.raises(CheckRequired, match="통과했는데 멈춤"):
        ME.merge(root, cid, rd, now=NOW)
    h["one_page.html"] = "x"
    (rd / "hashes.json").write_text(json.dumps(h), encoding="utf-8")
    r = result(win)
    r["status"] = "NEED_MODEL"
    r["trial"] = None
    (rd / "result.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    h["result.json"] = RW.sha_bytes((rd / "result.json").read_bytes())
    (rd / "hashes.json").write_text(json.dumps(h), encoding="utf-8")
    with pytest.raises(CheckRequired, match="본 요약이 없는데 한 장"):
        ME.merge(root, cid, rd, now=NOW)


def test_merge_refuses_changed_mac_bundle_input_and_zip_list(
    root, packed, ollama, tools
):
    cid, bd, win = packed
    assert run_win(win, ollama, tools) == 0
    p = bd / "bundle_input.json"
    orig = p.read_bytes()
    p.write_bytes(orig.replace(b'"created_at": "', b'"created_at": "9'))
    with pytest.raises(CheckRequired, match="bundle_input.json 이 manifest"):
        ME.merge(root, cid, win / "result_1", now=NOW)
    p.write_bytes(orig)
    with zipfile.ZipFile(bd / "bundle.zip") as z:
        files = {n: z.read(n) for n in z.namelist()}
    files["extra.txt"] = b"x"
    (bd / "bundle.zip").write_bytes(BU._zip(files))
    with pytest.raises(CheckRequired, match="파일 목록"):
        ME.merge(root, cid, win / "result_1", now=NOW)


def test_bad_ids_and_empty_key_and_response_hash(root):
    d = CA.archive(
        root, response=weekly_response(), selected=TICKER, source="s", now=NOW
    )
    with pytest.raises(CheckRequired, match="꼴이 아님"):
        CA.case_dir(root, "bad")
    with pytest.raises(CheckRequired, match="꼴이 아님"):
        BU.read_bundle(root, d.name, "bad")
    with pytest.raises(CheckRequired, match="비었음"):
        CA.lock_key(root, d.name, b"   ", now=NOW)
    raw = (d / "response.json").read_bytes()
    (d / "response.json").write_bytes(
        raw.replace(b"today_weekly_review", b"today_weekly_reviex")
    )
    with pytest.raises(CheckRequired, match="응답 원본 해시"):
        CA.load_case(root, d.name)


def test_fetch_weekly_reads_local_server_and_refuses_odd_status():
    state = {"code": 200}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            out = weekly_response()
            self.send_response(state["code"])
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, args=(0.02,), daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        assert CA.fetch_weekly(url, TICKER) == weekly_response()
        state["code"] = 203
        with pytest.raises(CheckRequired, match="조회 응답 203"):
            CA.fetch_weekly(url, TICKER)
    finally:
        srv.shutdown()


def test_lengths_carry_over_across_settings_stops(
    root, packed, ollama, tools, tmp_path
):
    cid, _bd, win = packed
    ollama.cfg = {"ctx": 8192}
    assert run_win(win, ollama, tools) == 2
    ME.merge(root, cid, win / "result_1", now=NOW)
    bd2 = BU.pack(
        root, cid, lengths={"num_predict": 30000}, reason="출력 여유", now=NOW
    )
    win2 = unzip(bd2, tmp_path / "w2")
    assert run_win(win2, ollama, tools) == 2
    ME.merge(root, cid, win2 / "result_1", now=NOW)
    bd3 = BU.pack(root, cid, lengths={"num_ctx": 65536}, reason="문맥", now=NOW)
    opts = json.loads((bd3 / "pack.json").read_text(encoding="utf-8"))["options"]
    assert opts["num_predict"] == 30000 and opts["num_ctx"] == 65536


def test_report_refuses_two_mains(root, packed, monkeypatch):
    from app.review_summary import report as RP

    cid, _bd, _win = packed
    two = [{"main_started": True, "main_status": "COMPLETED", "run_id": "a"}] * 2
    monkeypatch.setattr(RP, "merged_runs", lambda r, c: two)
    _t, v = RP.build(root, cid, {"critical_errors": 0}, {}, answers=True)
    assert v["verdict"] == "판정 불가" and "시도 2건" in v["reasons"][0]
