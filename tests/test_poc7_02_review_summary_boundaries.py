"""POC7-02 검증자 r2 정정 뒤 잠금 전 반박 검토(네 관점 · 34건)와 같은 종류 — 경계 칸 하나하나.

본 요약 뒤 쓰기 실패 · 본 호출 직전 관문의 빈칸 · USB 폴더 상태(임시 파일 · 복사 손상 · 더 담긴 복사본 · 다른 묶음)
· 맥북 기록 원자성 · 새 묶음 규칙 · 판정 입력. 준비물은 흐름 시험 · 회복 시험에서 가져다 쓴다.
"""

from __future__ import annotations

import json
import shutil
import signal

import pytest

from app.entry_timing.protocol import CheckRequired
from app.review_summary import bundle as BU
from app.review_summary import case as CA
from app.review_summary import judge as JU
from app.review_summary import merge as ME
from app.review_summary import report as RP
from app.review_summary import runner_files as RF
from app.review_summary import runner_win as RW
from tests import test_poc7_02_review_summary as M
from tests import test_poc7_02_review_summary_recovery as R

NOW = M.NOW
ollama, tools, root, packed = M.ollama, M.tools, M.root, M.packed
run_win, result, rewrite, unzip = M.run_win, M.result, M.rewrite, M.unzip
_chats, _merge_rec, _rehash, _full_run = R._chats, R._merge_rec, R._rehash, R._full_run
ANS = {"direction": "맞음", "limits": "맞음", "next": "맞음"}


def _usage(**over):
    L = {
        "user_s": 8,
        "elapsed_s": 20,
        "reopen": 0,
        "fixes": [],
        "reuse": "예",
        "answers": ANS,
    }
    U = {"user_s": 10, "elapsed_s": 10, "reopen": 0, "fixes": [], "answers": ANS}
    L.update(over.pop("L", {}))
    U.update(over.pop("U", {}))
    return {"L": L, "U": U}


# ── 본 요약 뒤 쓰기 실패 · Ctrl+C(첫 결과 보존) ──


def test_rename_briefly_blocked_is_retried(packed, ollama, tools, monkeypatch):
    """Windows 백신 · 동기화가 이름 바꾸기를 잠깐 막아도 다시 시도해 완전한 기록이 남는다."""
    _cid, _bd, win = packed
    real, n = RF.os.rename, {"k": 0}

    def flaky(a, b):
        n["k"] += 1
        if n["k"] in (2, 3):  # 한 장 이름 바꾸기에서 두 번 막힘
            raise PermissionError(32, "다른 프로그램이 사용 중")
        return real(a, b)

    monkeypatch.setattr(RF.os, "rename", flaky)
    monkeypatch.setattr(RF.time, "sleep", lambda s: None)
    assert run_win(win, ollama, tools) == 0
    rd = win / "result_1"
    assert (rd / "one_page.html").exists() and (rd / "hashes.json").exists()
    assert not [p for p in rd.iterdir() if p.name.endswith(".part")]


def test_page_write_failure_keeps_result_and_hashes(
    root, packed, ollama, tools, monkeypatch
):
    cid, _bd, win = packed
    real = RW.write_new

    def no_page(path, data, **k):
        if path.name == "one_page.html":
            raise PermissionError(32, "사용 중")
        return real(path, data, **k)

    monkeypatch.setattr(RW, "write_new", no_page)
    assert run_win(win, ollama, tools) == 0
    res = result(win)
    assert (
        "한 장 쓰기 실패" in res["render_error"]
        and (win / "result_1" / "hashes.json").exists()
    )
    monkeypatch.undo()
    rec = _merge_rec(root, cid, win / "result_1")
    assert rec["main_status"] == JU.COMPLETED and rec["one_page_sha256"] is None
    _t, v = RP.build(root, cid, {"critical_errors": 1}, {}, answers=True)
    assert v["verdict"] == "판정 불가" and "한 장이 없음" in v["reasons"][0]


@pytest.mark.parametrize("partial", [False, True])
def test_raw_write_failure_keeps_received_reply(
    root, packed, ollama, tools, monkeypatch, partial
):
    """받은 원문을 못 쓰거나 반만 써도 받은 본문 · 구분 · 한 장은 결과 기록에 남고 회수된다."""
    cid, _bd, win = packed
    real = RW.write_x

    def bad_raw(path, data):
        if path.name == RW.MAIN_RAW:
            if partial:
                path.write_bytes(data[: len(data) // 2])
            raise OSError(28, "디스크가 참")
        return real(path, data)

    monkeypatch.setattr(RW, "write_x", bad_raw)
    assert run_win(win, ollama, tools) == 0
    res = result(win)
    assert res["main"]["raw_write_error"] and res["main"]["content"]
    assert (win / "result_1" / "one_page.html").exists()
    monkeypatch.undo()
    rec = _merge_rec(root, cid, win / "result_1")
    assert rec["main_status"] == JU.COMPLETED and rec["has_output"]
    assert rec["checks"]["raw_unparsed"] is partial


def test_ctrl_c_during_wait_still_judges_and_renders(
    root, packed, ollama, tools, monkeypatch
):
    """본 응답을 기다리는 중 누른 Ctrl+C — 받은 값을 다 채운 뒤 멈춰, 구분 · 한 장이 남고 판정까지 간다."""
    cid, _bd, win = packed
    real, n = RW.io.Ollama.chat, {"k": 0}

    def chat(self, body):
        n["k"] += 1
        if n["k"] == 3:
            signal.raise_signal(signal.SIGINT)
        return real(self, body)

    monkeypatch.setattr(RW.io.Ollama, "chat", chat)
    with pytest.raises(KeyboardInterrupt):
        run_win(win, ollama, tools)
    monkeypatch.undo()
    res = result(
        win
    )  # 진단을 건너뛰어 할당 문맥 · 로그를 못 봄 = 입력 미확인(정직한 구분)
    assert res["status"] == RW.INTERRUPTED
    assert (
        res["main"]["judgement"]["status"] == JU.TECHNICAL_FAILURE
    )  # 중단 = 기술 실패(PLAN §2-4 ①)
    assert (win / "result_1" / "one_page.html").exists()
    rec = _merge_rec(root, cid, win / "result_1")
    score = {"critical_errors": 1, "one_page_sha256": rec["one_page_sha256"]}
    assert RP.build(root, cid, score, {}, answers=True)[1]["verdict"] == "품질 미달"


@pytest.mark.parametrize("where", ["marker", "sampler"])
def test_ctrl_c_between_marker_and_call_is_deferred(
    packed, ollama, tools, monkeypatch, where
):
    """시작 표지를 쓴 뒤 본 호출 전에 누른 Ctrl+C 도 미룬다 — 시도만 쓰고 모델을 안 부르는 일이 없다."""
    _cid, _bd, win = packed
    if where == "marker":
        real = RF._sync_dir

        def sync(d):
            if (d / RW.MAIN_STARTED).exists() and not (d / RW.MAIN_RAW).exists():
                signal.raise_signal(signal.SIGINT)
            return real(d)

        monkeypatch.setattr(RF, "_sync_dir", sync)
    else:
        real_start, n = RW.io.Sampler.start, {"k": 0}

        def start(self):
            n["k"] += 1
            if n["k"] == 2:  # 1 = 합성 점검 · 2 = 본 요약
                signal.raise_signal(signal.SIGINT)
            return real_start(self)

        monkeypatch.setattr(RW.io.Sampler, "start", start)
    with pytest.raises(KeyboardInterrupt):
        run_win(win, ollama, tools)
    monkeypatch.undo()
    assert _chats(ollama) == 3 and (win / "result_1" / RW.MAIN_RAW).exists()
    assert result(win)["main"]["judgement"]["status"] == JU.TECHNICAL_FAILURE
    assert (win / "result_1" / "one_page.html").exists()


def test_sampler_start_failure_does_not_consume_attempt(
    packed, ollama, tools, monkeypatch
):
    _cid, _bd, win = packed

    def boom(self):
        raise RuntimeError("스레드를 못 띄움")

    monkeypatch.setattr(RW.io.Sampler, "start", boom)
    run_win(win, ollama, tools)
    res = result(win)
    assert _chats(ollama) == 3 and "gpu_sampler" in res["main"]["diag_errors"]


# ── 본 호출 직전 관문의 빈칸(한 번뿐인 시도를 정해진 실패로 쓰지 않음) ──


def _stop_reasons(win) -> tuple[list, str]:
    res = result(win)
    assert res["status"] == RW.PRE_MAIN_STOPPED and res["main"] is None
    return res["pre_main"]["categories"], " ".join(res["pre_main"]["reasons"])


def test_gate_stops_when_count_log_is_unreadable(packed, ollama, tools, monkeypatch):
    _cid, _bd, win = packed
    ollama.cfg = {"count_silent_log": True}
    monkeypatch.setattr(RW.time, "sleep", lambda s: None)
    assert run_win(win, ollama, tools) == 2
    kinds, why = _stop_reasons(win)
    assert (
        kinds == ["ENV"]
        and "server.log 기록을 읽지 못함" in why
        and _chats(ollama) == 2
    )


def test_count_log_line_arriving_late_is_waited_for(packed, ollama, tools, monkeypatch):
    _cid, _bd, win = packed
    real, n = RW.io.log_segment, {"k": 0}

    def late(path, start):
        n["k"] += 1
        if n["k"] == 2:  # 토큰 세기의 첫 읽기 — 줄이 아직 안 붙음
            return {
                "live": False,
                "trunc": None,
                "chat_lines": 0,
                "release_ok": 0,
                "bytes": 0,
            }
        return real(path, start)

    monkeypatch.setattr(RW.io, "log_segment", late)
    monkeypatch.setattr(RW.time, "sleep", lambda s: None)
    assert run_win(win, ollama, tools) == 0 and result(win)["count"]["trunc_log"] == []


def test_gate_stops_without_output_room(packed, ollama, tools):
    _cid, _bd, win = packed
    ollama.cfg = {"count_delta": 30000}  # 입력 < 문맥 이지만 입력 + num_predict > 문맥
    assert run_win(win, ollama, tools) == 2
    kinds, why = _stop_reasons(win)
    assert kinds == ["SETTINGS"] and "출력 여유 부족" in why


@pytest.mark.parametrize("which, label", [(1, "합성 점검"), (2, "토큰 세기")])
def test_gate_stops_when_model_stays_loaded(
    packed, ollama, tools, monkeypatch, which, label
):
    """모델이 안 내려가면 본 호출이 캐시를 읽는다(PLAN §2-2 '캐시 없이 처음부터') — 부르지 않는다."""
    _cid, _bd, win = packed
    real, n = RW.io.Ollama.wait_unloaded, {"k": 0}

    def stays(self, model, limit=60.0):
        n["k"] += 1
        if n["k"] == which:
            return {"gone": False, "waited_s": 60.0, "error": None}
        return real(self, model, limit)

    monkeypatch.setattr(RW.io.Ollama, "wait_unloaded", stays)
    assert run_win(win, ollama, tools) == 2
    kinds, why = _stop_reasons(win)
    assert kinds == ["ENV"] and f"{label} 뒤 모델이 내려가지 않음" in why


@pytest.mark.parametrize("step", ["trial", "count"])
def test_memory_error_is_a_settings_problem(
    root, packed, ollama, tools, monkeypatch, step
):
    """메모리 부족 호출 오류 = 설정 문제(PLAN §2-2) — 길이만 고친 새 묶음을 만들 수 있다."""
    cid, _bd, win = packed
    real = RW.io.Ollama.chat

    def oom(self, body):
        counting = body["options"].get("num_predict") == 1
        trial = "· 보관 합성]" in body["messages"][-1]["content"]
        if (step == "trial" and trial) or (step == "count" and counting):
            raise RuntimeError(
                "model requires more system memory (13.2 GiB) than is available"
            )
        return real(self, body)

    monkeypatch.setattr(RW.io.Ollama, "chat", oom)
    assert run_win(win, ollama, tools) == 2
    res = result(win)
    kinds = (res["trial"]["gate"] if step == "trial" else res["pre_main"])["categories"]
    assert "SETTINGS" in kinds
    monkeypatch.undo()
    _merge_rec(root, cid, win / "result_1")
    BU.pack(
        root,
        cid,
        lengths={"num_ctx": 32768, "num_predict": 16384},
        reason="메모리",
        now=NOW,
    )


def test_rerun_with_a_different_model_digest_stops(root, packed, ollama, tools):
    """환경 멈춤 뒤 같은 폴더 다시 실행에서 모델 digest 가 앞 실행과 다르면 멈춘다(교체는 설계자 판단)."""
    cid, _bd, win = packed
    ollama.cfg = {"count_404": True}
    assert run_win(win, ollama, tools) == 2  # 직전 관문 환경 멈춤(digest d…)
    ollama.cfg, calls = {"other_digest": True}, _chats(ollama)
    assert run_win(win, ollama, tools) == 2
    again = result(win, 2)
    assert (
        again["status"] == RW.NEED_ENV
        and "앞 실행과 모델 digest" in again["messages_ko"][0]
    )
    assert _chats(ollama) == calls


def test_length_above_model_context_is_refused(root, packed, ollama, tools):
    cid, _bd, win = packed
    ollama.cfg = {"ctx": 8192}
    assert run_win(win, ollama, tools) == 2
    _merge_rec(root, cid, win / "result_1")
    with pytest.raises(ValueError, match="모델 문맥"):
        BU.pack(root, cid, lengths={"num_ctx": 10**30}, reason="오타", now=NOW)


# ── USB 폴더 상태(임시 파일 · 복사 손상 · 원문 누락 · 다른 실행의 한 장 · 더 담긴 복사본 · 다른 묶음) ──


def test_hashes_left_as_part_is_verified_as_complete(root, packed, ollama, tools):
    """해시를 다 쓰고 이름만 못 바꾼 폴더(.hashes.json.part) — 그대로 검증해 완전한 기록으로 받는다."""
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    (rd / "hashes.json").rename(rd / ".hashes.json.part")
    rec = _merge_rec(root, cid, rd)
    assert rec["main_status"] == JU.COMPLETED and rec["checks"]["from_part"] == [
        "hashes.json"
    ]


@pytest.mark.parametrize("name", ["result.json", "one_page.html"])
def test_part_files_of_incomplete_are_kept_by_their_names(
    root, packed, ollama, tools, name
):
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    (rd / "hashes.json").unlink()
    if name == "one_page.html":
        (rd / "result.json").unlink()
    (rd / name).rename(rd / f".{name}.part")
    out = ME.merge(root, cid, rd, now=NOW)
    assert (out / f".{name}.part").exists() and not (out / name).exists()


def test_torn_result_copy_is_refused_but_torn_part_is_kept(root, packed, ollama, tools):
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    (rd / "hashes.json").unlink()
    body = (rd / "result.json").read_bytes()
    (rd / "result.json").write_bytes(body[:100])  # 이름이 붙은 깨진 결과 = 복사 손상
    with pytest.raises(CheckRequired, match="result.json 이 깨짐"):
        ME.merge(root, cid, rd, now=NOW)
    (rd / "result.json").rename(
        rd / ".result.json.part"
    )  # 임시 이름에서만 깨질 수 있다(쓰는 중 꺼짐)
    assert _merge_rec(root, cid, rd)["status"] == ME.INCOMPLETE


def test_raw_omitted_from_copy_is_refused(root, packed, ollama, tools):
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    for f in ("hashes.json", RW.MAIN_RAW):
        (rd / f).unlink()
    with pytest.raises(CheckRequired, match="main_raw.json 이 빠짐"):
        ME.merge(root, cid, rd, now=NOW)


def test_incomplete_page_from_another_run_is_refused(
    root, packed, ollama, tools, tmp_path
):
    cid, bd, win = packed
    rd = _full_run(win, ollama, tools)
    win2 = unzip(bd, tmp_path / "again")
    ollama.cfg = {"main_no_marks": True}  # 다른 실행 = 다른 답
    assert run_win(win2, ollama, tools) == 0
    (rd / "hashes.json").unlink()
    shutil.copyfile(win2 / "result_1" / "one_page.html", rd / "one_page.html")
    with pytest.raises(CheckRequired, match="다시 만든 한 장이 one_page.html 과 다름"):
        ME.merge(root, cid, rd, now=NOW)


def test_fuller_incomplete_copy_replaces_the_thinner_one(
    root, packed, ollama, tools, tmp_path
):
    """꺼진 PC 폴더(표지 + 원문)를 처음엔 표지만 복사해도, 원문까지 담은 복사본을 뒤에 받는다."""
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    for f in ("result.json", "hashes.json", "one_page.html"):
        (rd / f).unlink()
    thin = tmp_path / "thin" / "result_1"
    thin.mkdir(parents=True)
    shutil.copyfile(rd / RW.MAIN_STARTED, thin / RW.MAIN_STARTED)
    first = _merge_rec(root, cid, thin)
    assert not first["has_output"]
    second = _merge_rec(root, cid, rd)
    assert second["replaces"] == first["record_dir"] and second["has_output"]
    assert [r["record_dir"] for r in BU.merged_runs(root, cid)] == [
        second["record_dir"]
    ]
    with pytest.raises(FileExistsError, match="더 담긴 복사본이 아님"):
        ME.merge(root, cid, rd, now=NOW)


@pytest.mark.parametrize(
    "cfg", [{"ctx": 8192}, {"bad_korean": True}]
)  # 새 묶음은 설정 · 모델 멈춤 뒤
def test_other_bundle_extracted_over_the_folder(root, packed, ollama, tools, cfg):
    """앞 묶음을 푼 폴더에 새 묶음 zip 을 덮어 풀어도 앞 묶음의 결과를 이 묶음의 앞 결과로 보지 않는다."""
    cid, _bd, win = packed
    ollama.cfg = cfg
    assert run_win(win, ollama, tools) == 2
    _merge_rec(root, cid, win / "result_1")
    bd2 = BU.pack(root, cid, reason="새 묶음", now=NOW)
    unzip(bd2, win)  # 같은 폴더에 덮어 풂
    ollama.cfg = {}
    assert run_win(win, ollama, tools) == 0
    assert result(win, 2)["prior_results"] == []
    assert _merge_rec(root, cid, win / "result_2")["main_status"] == JU.COMPLETED


# ── 맥북 기록 원자성(회수 · 포장 · 잠금) ──


def _cut_after(monkeypatch, module, n_ok: int):
    real, n = module.write_once, {"k": 0}

    def cut(base, path, data):
        n["k"] += 1
        if n["k"] > n_ok:
            raise KeyboardInterrupt
        return real(base, path, data)

    monkeypatch.setattr(module, "write_once", cut)


def test_interrupted_merge_leaves_no_half_record(
    root, packed, ollama, tools, monkeypatch
):
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    _cut_after(monkeypatch, BU, 2)
    with pytest.raises(KeyboardInterrupt):
        ME.merge(root, cid, rd, now=NOW)
    monkeypatch.undo()
    assert BU.merged_runs(root, cid) == []
    assert _merge_rec(root, cid, rd)["main_status"] == JU.COMPLETED


def test_interrupted_pack_leaves_no_half_bundle(root, monkeypatch):
    cid = M.make_case(root)
    _cut_after(monkeypatch, BU, 2)
    with pytest.raises(KeyboardInterrupt):
        BU.pack(root, cid, now=NOW)
    monkeypatch.undo()
    assert BU.bundles_of(root, cid) == []
    BU.pack(root, cid, now=NOW)
    assert len(BU.bundles_of(root, cid)) == 1


def test_interrupted_lock_key_is_completed_with_the_same_key(root, monkeypatch):
    """메모를 쓴 뒤 잠금 기록 전에 끊겨도, 같은 메모로 다시 하면 잠금을 마친다(다른 메모는 거부)."""
    d = CA.archive(
        root,
        response=M.weekly_response(),
        selected=M.TICKER,
        answers=M.ANSWERS,
        source="시험",
        now=NOW,
    )
    real = CA.write_once

    def cut(base, path, data):
        if path.name == "key_lock.json":
            raise KeyboardInterrupt
        return real(base, path, data)

    monkeypatch.setattr(CA, "write_once", cut)
    with pytest.raises(KeyboardInterrupt):
        CA.lock_key(root, d.name, "메모".encode(), now=NOW)
    monkeypatch.undo()
    with pytest.raises(CheckRequired, match="지금 메모와 다름"):
        CA.lock_key(root, d.name, "다른 메모".encode(), now=NOW)
    assert CA.lock_key(root, d.name, "메모".encode(), now=NOW)["key_sha256"]
    CA.read_lock(root, d.name)


# ── 새 묶음 규칙(실제로 돈 마지막 기록 · 다시 실행 멈춤 기록만은 회수가 아님) ──


@pytest.mark.parametrize("cfg", [{"ctx": 8192}, {"count_delta": 30000}])
def test_length_change_after_settings_stop_and_already_ran(
    root, packed, ollama, tools, cfg
):
    cid, _bd, win = packed
    ollama.cfg = cfg
    assert run_win(win, ollama, tools) == 2
    assert (
        run_win(win, ollama, tools) == 2 and result(win, 2)["status"] == RW.ALREADY_RAN
    )
    _merge_rec(root, cid, win / "result_1")
    _merge_rec(root, cid, win / "result_2")
    bd2 = BU.pack(root, cid, lengths={"num_ctx": 65536}, reason="문맥", now=NOW)
    rec = json.loads((bd2 / "pack.json").read_text(encoding="utf-8"))
    assert rec["after_run"] == result(win)["run_id"]


def test_busy_already_ran_alone_does_not_count_as_merged(
    root, packed, ollama, tools, monkeypatch
):
    cid, _bd, win = packed
    (win / "result_1").mkdir()
    (win / "result_1" / RW.LOCK).write_bytes(b"")
    real = type(win).unlink

    def held(self, *a, **k):
        if self.name == RW.LOCK and self.parent.name == "result_1":
            raise PermissionError("열려 있음")
        return real(self, *a, **k)

    monkeypatch.setattr(type(win), "unlink", held)
    assert run_win(win, ollama, tools) == 2
    monkeypatch.undo()
    _merge_rec(root, cid, win / "result_2")
    with pytest.raises(CheckRequired, match="먼저 회수"):
        BU.pack(root, cid, reason="다른 창 실행 중", now=NOW)


# ── 판정 입력(꼴 · 범위 · 실행기 기록 대조 · 잠금 · CLI) ──


@pytest.mark.parametrize(
    "over, msg",
    [
        ({"U": {"user_s": 1e308, "elapsed_s": 1e308}}, "하루"),
        ({"U": {"user_s": 86401, "elapsed_s": 90000}}, "하루"),
        ({"L": {"user_s": 0}}, "0초보다 커야"),
        ({"L": {"user_s": 30}}, "전체 경과"),
        ({"L": {"answers": ["맞음"]}}, "answers 는 JSON 객체"),
        ({"L": {"answers": {**ANS, "next": ["맞음"]}}}, "맞음 · 부분 · 틀림"),
        ({"U": {"answers": {**ANS, "direction": "right"}}}, "맞음 · 부분 · 틀림"),
        ({"L": {"fixes": "없음"}}, "fixes"),
        ({"L": {"fixes": [1]}}, "fixes"),
        ({"L": {"reuse": "yes"}}, "reuse"),
        ({"L": {"reuse": True}}, "reuse"),
        ({"L": {"reopen": 1.5}}, "reopen"),
    ],
)
def test_usage_values_that_are_not_measurements_are_errors(over, msg):
    run = {
        "main_status": "COMPLETED",
        "status": "COMPLETED",
        "one_page_sha256": "p",
        "checks": {},
    }
    with pytest.raises(ValueError, match=msg):
        RP.ac4({"critical_errors": 0}, _usage(**over), run)


def test_local_elapsed_shorter_than_runner_record_is_an_error(
    root, packed, ollama, tools, monkeypatch
):
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    rec = _merge_rec(root, cid, rd)
    run = {**rec, "run_wall_s": 300.0}  # 실행기 단조 시계 실행 시간(벽시계 아님)
    monkeypatch.setattr(RP, "merged_runs", lambda r, c, every=False: [run])
    score = {"critical_errors": 0, "one_page_sha256": rec["one_page_sha256"]}
    with pytest.raises(ValueError, match="실행기 기록 300.0초"):
        RP.build(root, cid, score, _usage(L={"elapsed_s": 120}), answers=True)
    RP.build(root, cid, score, _usage(L={"elapsed_s": 400}), answers=True)


def test_report_rechecks_the_answer_key_lock(root, packed, ollama, tools):
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    rec = _merge_rec(root, cid, rd)
    (CA.case_dir(root, cid) / "answer_key.md").write_bytes("출력 뒤 고친 메모".encode())
    score = {"critical_errors": 0, "one_page_sha256": rec["one_page_sha256"]}
    with pytest.raises(CheckRequired, match="메모 해시가 다름"):
        RP.build(root, cid, score, _usage(), answers=True)


@pytest.mark.parametrize(
    "text, msg",
    [
        ('{"a": 1, "a": 2}', "같은 키가 두 번"),
        ("[" * 200000 + "]" * 200000, "너무 깊음"),
        ('{"a": NaN}', "쓸 수 없는 값"),
    ],
)
def test_strict_json(text, msg):
    with pytest.raises(ValueError, match=msg):
        CA.strict_loads(text)


@pytest.mark.parametrize(
    "args",
    [
        ["pack", "--case", "x", "--num-ctx", "64k"],
        ["merge", "--case", "x"],
        ["nothing"],
    ],
)
def test_cli_argument_errors_end_with_a_result_line(root, capsys, args):
    from scripts import run_review_summary as CLI

    assert CLI.main(["--root", str(root), *args]) == 2
    last = capsys.readouterr().out.strip().splitlines()[-1]
    assert last.startswith("RESULT ") and "CHECK_REQUIRED" in last


def test_cli_report_shape_errors_end_with_a_result_line(
    root, packed, ollama, tools, tmp_path, capsys
):
    from scripts import run_review_summary as CLI

    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    sha = _merge_rec(root, cid, rd)["one_page_sha256"]
    score = tmp_path / "score.json"
    score.write_text(
        json.dumps({"critical_errors": 0, "one_page_sha256": sha}), encoding="utf-8"
    )
    for usage in (
        {"L": {"answers": [1]}},
        {"L": {"answers": {"next": {"a": 1}}}},
        {"U": 3},
    ):
        u = tmp_path / "usage.json"
        u.write_text(json.dumps(usage), encoding="utf-8")
        args = [
            "--root",
            str(root),
            "report",
            "--case",
            cid,
            "--score",
            str(score),
            "--usage",
            str(u),
        ]
        assert CLI.main(args) == 2
        assert "CHECK_REQUIRED" in capsys.readouterr().out.strip().splitlines()[-1]


def test_ctrl_c_on_the_settings_stop_message_keeps_the_length_rule(
    root, packed, ollama, tools, monkeypatch
):
    """설정 멈춤 안내를 찍는 순간 Ctrl+C(상태 = 중단) — 멈춤 종류는 남아 길이만 고친 새 묶음을 만들 수 있다."""
    cid, _bd, win = packed
    ollama.cfg = {"count_delta": 30000}
    real = RW._say

    def say(res, text):
        real(res, text)
        if text.startswith("멈춤 — 본 요약 직전"):
            raise KeyboardInterrupt

    monkeypatch.setattr(RW, "_say", say)
    with pytest.raises(KeyboardInterrupt):
        run_win(win, ollama, tools)
    monkeypatch.undo()
    res = result(win)
    assert res["status"] == RW.INTERRUPTED and res["pre_main"]["categories"] == [
        "SETTINGS"
    ]
    _merge_rec(root, cid, win / "result_1")
    BU.pack(root, cid, lengths={"num_ctx": 65536}, reason="출력 여유", now=NOW)


# ── 변이에서 살아남은 칸 — 그 대조만 어긋난 경우(겹치는 대조는 자기 문구로 구분) ──


@pytest.mark.parametrize(
    "cfg, kinds, why",
    [
        ({"version_gone": True}, ["ENV"], "Ollama 판을 읽지 못함"),
        ({"count_no_tokens": True}, ["ENV"], "토큰 세기 값 없음"),
    ],
)
def test_gate_stops_on_missing_values(packed, ollama, tools, cfg, kinds, why):
    _cid, _bd, win = packed
    ollama.cfg = cfg
    assert run_win(win, ollama, tools) == 2
    got_kinds, reasons = _stop_reasons(win)
    assert got_kinds == kinds and why in reasons


def _incomplete_folder(win, ollama, tools, drop):
    rd = _full_run(win, ollama, tools)
    for f in drop:
        (rd / f).unlink()
    return rd


@pytest.mark.parametrize(
    "drop, change, msg",
    [
        (
            ("result.json", "hashes.json", "one_page.html", RW.MAIN_STARTED),
            None,
            "받은 원문이 있는데 시작 표지",
        ),
        (
            ("hashes.json", "one_page.html", RW.MAIN_STARTED, RW.MAIN_RAW),
            None,
            r"본 요약 기록이 있는데 시작 표지\(main_started.json\)가 없음",
        ),
        (
            ("result.json", "hashes.json", RW.MAIN_RAW),
            lambda m: m.update(case_id="other"),
            "다른 사례의 결과",
        ),
        (
            ("result.json", "hashes.json", RW.MAIN_RAW),
            lambda m: m.update(run_id="x"),
            "결과 · 시작 표지의 실행 id 꼴이 다름",
        ),
    ],
)
def test_incomplete_identity_checks_alone(
    root, packed, ollama, tools, drop, change, msg
):
    cid, _bd, win = packed
    rd = _incomplete_folder(win, ollama, tools, drop)
    if change is not None:
        p = rd / RW.MAIN_STARTED
        m = json.loads(p.read_text(encoding="utf-8"))
        change(m)
        p.write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(CheckRequired, match=msg):
        ME.merge(root, cid, rd, now=NOW)


def test_incomplete_claim_folder_name_must_match(root, packed, ollama, tools):
    cid, _bd, win = packed
    rd = _incomplete_folder(win, ollama, tools, ("hashes.json",))
    r = json.loads((rd / "result.json").read_text(encoding="utf-8"))
    r["result_dir"] = "result_9"
    (rd / "result.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(
        CheckRequired, match="결과 폴더 이름 · 실행 id 가 결과에 적힌 것과 다름"
    ):
        ME.merge(root, cid, rd, now=NOW)


@pytest.mark.parametrize(
    "change, msg",
    [
        (lambda m: m.update(case_id="other"), "다른 사례의 시작 표지"),
        (lambda m: m.update(run_id="x"), "시작 표지의 실행 id 꼴이 다름"),
        (
            lambda m: m.update(bundle_id="20260101T000000Z_00000000"),
            "시작 표지의 묶음이 결과와 다름",
        ),
    ],
)
def test_complete_marker_checks_alone(root, packed, ollama, tools, change, msg):
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    p = rd / RW.MAIN_STARTED
    m = json.loads(p.read_text(encoding="utf-8"))
    change(m)
    p.write_text(json.dumps(m), encoding="utf-8")
    _rehash(rd, RW.MAIN_STARTED)
    with pytest.raises(CheckRequired, match=msg):
        ME.merge(root, cid, rd, now=NOW)


def test_usb_json_must_be_an_object(root, packed, ollama, tools):
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    (rd / "result.json").write_text("[1]", encoding="utf-8")
    _rehash(rd, "result.json")
    with pytest.raises(CheckRequired, match="JSON 객체가 아님"):
        ME.merge(root, cid, rd, now=NOW)


def _regate(r, win):
    inp = json.loads((win / "bundle_input.json").read_text(encoding="utf-8"))
    env0 = {
        "ollama_version": r["env"]["ollama_version"],
        "model_digest": r["env"]["model"]["digest"],
    }
    unloads = {"trial": r["trial"].get("unload"), "count": r["count"].get("unload")}
    r["pre_main"] = JU.pre_main_gate(
        env0, r["env_before_main"], r["count"], inp["options"], unloads
    )


def test_main_with_a_failed_gate_is_refused(root, packed, ollama, tools):
    """직전 관문을 못 넘은 기록(원값과 맞게 고쳐도)인데 본 요약이 있으면 거부."""
    cid, _bd, win = packed
    _full_run(win, ollama, tools)

    def failed(r):
        r["env_before_main"]["model_digest"] = "e" * 64
        _regate(r, win)

    with pytest.raises(CheckRequired, match="넘지 않았는데 본 요약이 있음"):
        ME.merge(root, cid, rewrite(win, 1, failed), now=NOW)


@pytest.mark.parametrize(
    "change, msg",
    [
        (lambda r, w: r.pop("pre_main"), "직전 확인 기록 없이 그 멈춤으로 적힘"),
        (
            lambda r, w: (
                r["env_before_main"].update(model_digest=r["env"]["model"]["digest"]),
                _regate(r, w),
            ),
            "넘었는데 그 멈춤으로 적힘",
        ),
    ],
)
def test_pre_main_stop_record_must_be_consistent(
    root, packed, ollama, tools, change, msg
):
    cid, _bd, win = packed
    ollama.cfg = {"digest_change": True}
    assert run_win(win, ollama, tools) == 2
    with pytest.raises(CheckRequired, match=msg):
        ME.merge(root, cid, rewrite(win, 1, lambda r: change(r, win)), now=NOW)


@pytest.mark.parametrize("bad", [[1, 2], "usage"])
def test_report_inputs_must_be_objects(root, packed, ollama, tools, bad):
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    sha = _merge_rec(root, cid, rd)["one_page_sha256"]
    with pytest.raises(ValueError, match="사용 기록은 JSON 객체"):
        RP.build(
            root, cid, {"critical_errors": 0, "one_page_sha256": sha}, bad, answers=True
        )
    with pytest.raises(ValueError, match="채점은 JSON 객체"):
        RP.build(root, cid, bad, {}, answers=True)


def test_incomplete_with_claim_waits_for_its_earlier_folder(
    root, packed, ollama, tools
):
    """해시가 빠진 기록 미완이라도 결과 기록이 말하는 같은 폴더 앞 결과를 먼저 받아야 한다."""
    cid, _bd, win = packed
    ollama.cfg = {"count_404": True}  # 환경 멈춤 — 같은 폴더 다시 실행 허용
    assert run_win(win, ollama, tools) == 2
    ollama.cfg = {}
    assert run_win(win, ollama, tools) == 0
    (win / "result_2" / "hashes.json").unlink()
    with pytest.raises(CheckRequired, match=r"앞 결과\(result_1\)"):
        ME.merge(root, cid, win / "result_2", now=NOW)
    _merge_rec(root, cid, win / "result_1")
    assert _merge_rec(root, cid, win / "result_2")["status"] == ME.INCOMPLETE


def test_merge_skips_prior_rows_of_another_bundle(root, packed, ollama, tools):
    cid, _bd, win = packed
    _full_run(win, ollama, tools)
    other = {
        "dir": "result_9",
        "bundle_id": "20260101T000000Z_00000000",
        "run_id": "20260101T000000_00000000",
        "status": "COMPLETED",
        "main_started": True,
    }
    rd = rewrite(win, 1, lambda r: r.update(prior_results=[other]))
    assert _merge_rec(root, cid, rd)["main_status"] == JU.COMPLETED


def test_marker_only_incomplete_keeps_the_marker_digest(root, packed, ollama, tools):
    cid, _bd, win = packed
    rd = _incomplete_folder(
        win, ollama, tools, ("result.json", "hashes.json", "one_page.html", RW.MAIN_RAW)
    )
    m = json.loads((rd / RW.MAIN_STARTED).read_text(encoding="utf-8"))
    assert _merge_rec(root, cid, rd)["model_digest"] == m["model_digest"]


def test_same_complete_run_twice_is_named(root, packed, ollama, tools, tmp_path):
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    _merge_rec(root, cid, rd)
    with pytest.raises(FileExistsError, match="같은 실행이 이미 보관됨"):
        ME.merge(root, cid, rd, now=NOW)
    part = tmp_path / "copy" / "result_1"
    shutil.copytree(rd, part)
    (part / "hashes.json").unlink()
    with pytest.raises(FileExistsError, match="같은 실행이 이미 보관됨"):
        ME.merge(root, cid, part, now=NOW)


def test_earlier_bundle_with_only_a_busy_record_blocks_merge(
    root, packed, ollama, tools, tmp_path, monkeypatch
):
    """앞 묶음에 다시 실행 멈춤(다른 창 실행 중) 기록만 남았으면 뒤 묶음 결과를 받지 않는다."""
    cid, _bd, win = packed
    ollama.cfg = {"ctx": 8192}  # 설정 멈춤 — 새 묶음을 만들 수 있는 멈춤
    assert run_win(win, ollama, tools) == 2
    first = ME.merge(root, cid, win / "result_1", now=NOW)
    (win / "result_9").mkdir()
    (win / "result_9" / RW.LOCK).write_bytes(b"")
    real = type(win).unlink

    def held(self, *a, **k):
        if self.name == RW.LOCK and self.parent.name == "result_9":
            raise PermissionError("열려 있음")
        return real(self, *a, **k)

    monkeypatch.setattr(type(win), "unlink", held)
    assert (
        run_win(win, ollama, tools) == 2 and result(win, 2)["status"] == RW.ALREADY_RAN
    )
    monkeypatch.undo()
    _merge_rec(root, cid, win / "result_2")
    bd2 = BU.pack(root, cid, reason="새 묶음", now=NOW)
    ollama.cfg = {}
    win2 = unzip(bd2, tmp_path / "w2")
    assert run_win(win2, ollama, tools) == 0
    shutil.rmtree(first)  # 앞 묶음의 실제 기록이 없는 상태(다시 실행 멈춤 기록만)
    with pytest.raises(CheckRequired, match="앞 묶음 결과를 먼저 회수"):
        ME.merge(root, cid, win2 / "result_1", now=NOW)


# ── 검증자 r3 F9 ~ F12 와 같은 종류(실행기 ↔ 회수 같은 해석 · 기록 미완 원값 대조 · 실행 상태 · 벽시계 아닌 순서) ──


def _result_rename_fails(monkeypatch):
    real = RF.os.rename

    def no_result(a, b):
        if str(b).endswith("result.json"):
            raise PermissionError(32, "사용 중")
        return real(a, b)

    monkeypatch.setattr(RF.os, "rename", no_result)
    monkeypatch.setattr(RF.time, "sleep", lambda s: None)


@pytest.mark.parametrize(
    "cfg, blocked",
    [
        ({"ctx": 8192}, True),  # 합성 점검 설정 멈춤
        ({"count_delta": 30000}, True),  # 직전 관문 설정 멈춤(출력 여유)
        ({"bad_korean": True}, True),  # 모델 멈춤
        ({"count_404": True}, False),  # 환경 멈춤 — 같은 폴더 다시 실행 허용
    ],
)
def test_stop_left_only_in_part_still_blocks_rerun(
    root, packed, ollama, tools, monkeypatch, cfg, blocked
):
    """검증자 r3 F9: 멈춤 기록이 임시 결과(.result.json.part)에만 남아도 실행기는 회수와 같게 읽는다."""
    cid, _bd, win = packed
    ollama.cfg = cfg
    _result_rename_fails(monkeypatch)
    with pytest.raises(PermissionError):
        run_win(win, ollama, tools)
    monkeypatch.undo()
    assert (win / "result_1" / ".result.json.part").exists()
    ollama.cfg, calls = {}, _chats(ollama)
    run_win(win, ollama, tools)
    second = result(win, 2)
    assert second["prior_results"][0]["result_from_part"]
    if blocked:
        assert second["status"] == RW.ALREADY_RAN and _chats(ollama) == calls
    else:
        assert second["status"] == JU.COMPLETED
    first = _merge_rec(root, cid, win / "result_1")
    assert first["status"] == ME.INCOMPLETE and first["checks"]["claim_checked"]
    _merge_rec(root, cid, win / "result_2")
    if blocked and "SETTINGS" in (first["trial_categories"] or []) + (
        first["pre_main_categories"] or []
    ):
        BU.pack(root, cid, lengths={"num_ctx": 65536}, reason="설정", now=NOW)


def test_digest_in_part_record_is_compared_on_rerun(packed, ollama, tools, monkeypatch):
    _cid, _bd, win = packed
    ollama.cfg = {"count_404": True}
    _result_rename_fails(monkeypatch)
    with pytest.raises(PermissionError):
        run_win(win, ollama, tools)
    monkeypatch.undo()
    ollama.cfg = {"other_digest": True}
    assert run_win(win, ollama, tools) == 2
    assert "앞 실행과 모델 digest" in result(win, 2)["messages_ko"][0]


def _copy_without_hashes(rd, tmp_path):
    part = tmp_path / "copy" / "result_1"
    shutil.copytree(rd, part)
    (part / "hashes.json").unlink()
    return part


def test_corrupted_raw_in_incomplete_copy_is_refused(
    root, packed, ollama, tools, tmp_path
):
    """검증자 r3 F10 재현: 해시가 빠진 복사본의 원문 출력 토큰만 300 → 301 — 결과 기록의 원문 해시로 거부하고,
    원본은 그대로 받는다."""
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    part = _copy_without_hashes(rd, tmp_path)
    raw = json.loads((part / RW.MAIN_RAW).read_text(encoding="utf-8"))
    raw["response"]["eval_count"] = 301
    (part / RW.MAIN_RAW).write_text(
        json.dumps(raw, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(CheckRequired, match="원문 해시와 다름"):
        ME.merge(root, cid, part, now=NOW)
    assert _merge_rec(root, cid, rd)["main_status"] == JU.COMPLETED


def _claim(part, change):
    r = json.loads((part / "result.json").read_text(encoding="utf-8"))
    change(r)
    (part / "result.json").write_text(
        json.dumps(r, ensure_ascii=False), encoding="utf-8"
    )


@pytest.mark.parametrize(
    "change, msg",
    [
        (
            lambda r: r["main"].update(content="다른 본문"),
            "content' 가 받은 원문과 다름",
        ),
        (
            lambda r: r["main"].update(status="TECHNICAL_FAILURE"),
            "본 요약 구분과 본 요약 상태가 다름",
        ),
        (
            lambda r: r["main"]["judgement"].update(status="INPUT_UNCONFIRMED"),
            "다시 하면 실행기 기록과 다름",
        ),
        (lambda r: r["trial"]["gate"].update(ok=False), "합성 점검 통과 판단이 다름"),
        (lambda r: r["pre_main"].update(ok=False), "직전 확인을 원값에서 다시 하면"),
        (lambda r: r["files"].update({"run_summary.bat": "x"}), "manifest 와 다름"),
        (lambda r: r["main"].update(model_digest="e" * 64), "환경 기록과 다름"),
    ],
)
def test_incomplete_claim_gets_the_complete_path_checks(
    root, packed, ollama, tools, tmp_path, change, msg
):
    """해시 없는 결과 기록도 완료 경로와 같은 원값 대조를 받는다(검증자 r3 F10 같은 종류)."""
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    part = _copy_without_hashes(rd, tmp_path)
    _claim(part, change)
    with pytest.raises(CheckRequired, match=msg):
        ME.merge(root, cid, part, now=NOW)


def test_page_left_in_part_after_write_failure_is_kept_as_evidence(
    root, packed, ollama, tools, monkeypatch
):
    """한 장 이름 바꾸기가 끝내 실패하면 render_error 와 임시 한 장이 남는다 — 회수는 완전한 기록으로 받고
    임시 한 장은 증거로만 둔다(판정은 한 장 없음)."""
    cid, _bd, win = packed
    real = RF.os.rename

    def no_page(a, b):
        if str(b).endswith("one_page.html"):
            raise PermissionError(32, "사용 중")
        return real(a, b)

    monkeypatch.setattr(RF.os, "rename", no_page)
    monkeypatch.setattr(RF.time, "sleep", lambda s: None)
    assert run_win(win, ollama, tools) == 0
    monkeypatch.undo()
    rd = win / "result_1"
    assert (rd / ".one_page.html.part").exists() and "한 장 쓰기 실패" in result(win)[
        "render_error"
    ]
    part = _copy_without_hashes(
        rd, rd.parent.parent / "copy_no_hashes"
    )  # 같은 폴더의 해시 빠진 복사본
    inc = json.loads(
        (ME.merge(root, cid, part, now=NOW) / "merge.json").read_text(encoding="utf-8")
    )
    assert inc["status"] == ME.INCOMPLETE and inc["checks"]["claim_checked"]
    out = ME.merge(root, cid, rd, now=NOW)
    rec = json.loads((out / "merge.json").read_text(encoding="utf-8"))
    assert rec["main_status"] == JU.COMPLETED and rec["one_page_sha256"] is None
    assert (out / ".one_page.html.part").exists()


def test_ctrl_c_on_the_final_env_read_is_a_technical_failure(
    root, packed, ollama, tools, monkeypatch
):
    """검증자 r3 F11 재현: 응답 · 진단 뒤 마지막 판 다시 읽기 중 Ctrl+C — 중단 = 기술 실패 · AC4 관찰 아님."""
    cid, _bd, win = packed
    real, n = RW._env_now, {"k": 0}

    def env_now(*a):
        n["k"] += 1
        if n["k"] == 3:  # 1 = 시작 · 2 = 직전 관문 · 3 = 본 요약 뒤
            raise KeyboardInterrupt
        return real(*a)

    monkeypatch.setattr(RW, "_env_now", env_now)
    with pytest.raises(KeyboardInterrupt):
        run_win(win, ollama, tools)
    monkeypatch.undo()
    res = result(win)
    assert (
        res["status"] == RW.INTERRUPTED
        and res["main"]["status"] == JU.TECHNICAL_FAILURE
    )
    assert "실행이 끝나지 않음" in " ".join(res["main"]["judgement"]["technical"])
    rec = _merge_rec(root, cid, win / "result_1")
    score = {"critical_errors": 0, "one_page_sha256": rec["one_page_sha256"]}
    usage = _usage(
        L={"user_s": 5, "elapsed_s": 400}, U={"user_s": 500, "elapsed_s": 900}
    )
    v = RP.build(root, cid, score, usage, answers=True)[1]
    assert v["verdict"] == "판정 불가" and "실행 INTERRUPTED" in v["reasons"][0]


def test_runner_error_after_the_reply_is_a_technical_failure(
    root, packed, ollama, tools, monkeypatch
):
    cid, _bd, win = packed
    real, n = RW.judged, {"k": 0}

    def judged(rec, inp, part, counted):
        if counted:
            n["k"] += 1
            if n["k"] == 1:
                raise RuntimeError("구분 중 오류")
        return real(rec, inp, part, counted)

    monkeypatch.setattr(RW, "judged", judged)
    assert run_win(win, ollama, tools) == 2
    monkeypatch.undo()
    res = result(win)
    assert (
        res["status"] == RW.RUNNER_ERROR
        and res["main"]["status"] == JU.TECHNICAL_FAILURE
    )
    assert (
        _merge_rec(root, cid, win / "result_1")["main_status"] == JU.TECHNICAL_FAILURE
    )


def test_report_needs_both_run_and_reply_completed():
    run = {
        "main_status": "COMPLETED",
        "status": "INTERRUPTED",
        "one_page_sha256": "p",
        "checks": {},
    }
    v = RP.ac4({"critical_errors": 0}, _usage(), run)
    assert v["verdict"] == "판정 불가" and "실행 INTERRUPTED" in v["reasons"][0]


def test_clock_moved_back_does_not_reorder_runs(root, packed, ollama, tools):
    """검증자 r3 F12 재현: ① 환경 멈춤 → 시계를 뒤로 → ② 설정 멈춤 — 실행 순서(앞 결과 사슬)로 마지막을 고른다."""
    cid, _bd, win = packed
    ollama.cfg = {"count_404": True}
    assert run_win(win, ollama, tools) == 2
    ollama.cfg = {"ctx": 8192}
    assert run_win(win, ollama, tools) == 2
    rewrite(win, 2, lambda r: r.update(started_at="2000-01-01T00:00:00+09:00"))
    first = _merge_rec(root, cid, win / "result_1")
    second = _merge_rec(root, cid, win / "result_2")
    assert second["prior_runs"] == [first["run_id"]]
    assert [r["run_id"] for r in BU.merged_runs(root, cid)] == [
        first["run_id"],
        second["run_id"],
    ]
    bd2 = BU.pack(root, cid, lengths={"num_ctx": 65536}, reason="문맥", now=NOW)
    assert (
        json.loads((bd2 / "pack.json").read_text(encoding="utf-8"))["after_run"]
        == second["run_id"]
    )


def test_two_extractions_make_the_last_run_unknown(
    root, packed, ollama, tools, tmp_path
):
    cid, bd, win = packed
    ollama.cfg = {"ctx": 8192}
    assert run_win(win, ollama, tools) == 2
    win2 = unzip(bd, tmp_path / "again")
    assert run_win(win2, ollama, tools) == 2
    _merge_rec(root, cid, win / "result_1")
    _merge_rec(root, cid, win2 / "result_1")
    with pytest.raises(CheckRequired, match="순서를 알 수 없음"):
        BU.pack(root, cid, lengths={"num_ctx": 65536}, reason="문맥", now=NOW)


def test_mac_clock_change_after_lock_does_not_refuse(root, packed, ollama, tools):
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    p = CA.case_dir(root, cid) / "key_lock.json"
    lock = json.loads(p.read_text(encoding="utf-8"))
    lock["locked_at"] = (
        "2099-01-01T00:00:00+09:00"  # 잠근 뒤 맥북 시계를 앞당겼다가 되돌림
    )
    p.write_text(json.dumps(lock), encoding="utf-8")
    assert _merge_rec(root, cid, rd)["main_status"] == JU.COMPLETED
