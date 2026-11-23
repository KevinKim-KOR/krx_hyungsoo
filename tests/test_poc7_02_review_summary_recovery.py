"""POC7-02 검증자 r1 F1 ~ F4 와 같은 종류 — 첫 결과 보존 · 고르지 않음 · 본 실행 전 고정 · 판정 입력 계약.

흐름 시험의 준비물(가짜 Ollama · 도구 · tmp 연구 폴더 · 묶음)을 `test_poc7_02_review_summary.py` 에서 가져다 쓴다.
"""

from __future__ import annotations

import json
import shutil

import pytest

from app.entry_timing.protocol import CheckRequired
from app.review_summary import bundle as BU
from app.review_summary import judge as JU
from app.review_summary import merge as ME
from app.review_summary import runner_win as RW
from tests import test_poc7_02_review_summary as M

NOW = M.NOW
ollama, tools, root, packed = M.ollama, M.tools, M.root, M.packed
run_win, result, rewrite, unzip, smi = M.run_win, M.result, M.rewrite, M.unzip, M.smi


# ── 검증자 r1 F1 ~ F4 와 같은 종류(첫 결과 보존 · 고르지 않음 · 본 실행 전 고정 · 판정 입력) ──────────


def _chats(ollama) -> int:
    return sum(1 for _m, p, _b in ollama.calls if p == "/api/chat")


def test_f1_main_kept_when_interrupted_after_response(
    root, packed, ollama, tools, monkeypatch
):
    """본 응답을 받은 뒤 진단 중 중단 — 받은 원문 · 구분이 남고, 같은 폴더 다시 실행은 본 호출 없이 멈춤."""
    cid, _bd, win = packed
    real, n = RW.io.log_segment, {"k": 0}

    def seg(*a):
        n["k"] += 1
        if n["k"] == 3:  # 1 = 합성 점검 · 2 = 토큰 세기 · 3 = 본 요약
            raise KeyboardInterrupt
        return real(*a)

    monkeypatch.setattr(RW.io, "log_segment", seg)
    with pytest.raises(KeyboardInterrupt):
        run_win(win, ollama, tools)
    monkeypatch.undo()
    rd = win / "result_1"
    res = result(win)
    raw = json.loads((rd / "main_raw.json").read_text(encoding="utf-8"))
    assert res["status"] == RW.INTERRUPTED and _chats(ollama) == 3
    assert raw["response"]["message"]["content"] == res["main"]["content"] != ""
    assert (
        res["main"]["status"] == JU.TECHNICAL_FAILURE  # 중단 = 기술 실패(PLAN §2-4 ①)
        and (rd / "one_page.html").exists()
    )
    assert (
        run_win(win, ollama, tools) == 2 and result(win, 2)["status"] == RW.ALREADY_RAN
    )
    assert _chats(ollama) == 3  # 본 요약을 다시 부르지 않음
    out = ME.merge(root, cid, rd, now=NOW)
    rec = json.loads((out / "merge.json").read_text(encoding="utf-8"))
    assert (
        rec["main_started"]
        and rec["has_output"]
        and rec["main_status"] == JU.TECHNICAL_FAILURE
    )
    assert (out / "main_raw.json").read_bytes() == (rd / "main_raw.json").read_bytes()


def test_f1_render_failure_keeps_result_and_raw(
    root, packed, ollama, tools, monkeypatch
):
    cid, _bd, win = packed

    def boom(*a, **k):
        raise RuntimeError("한 장 실패")

    monkeypatch.setattr(RW.render, "render_html", boom)
    assert run_win(win, ollama, tools) == 0
    rd = win / "result_1"
    res = result(win)
    assert "한 장 실패" in res["render_error"] and not (rd / "one_page.html").exists()
    assert (rd / "hashes.json").exists() and (rd / "main_raw.json").exists()
    monkeypatch.undo()
    rec = json.loads(
        (ME.merge(root, cid, rd, now=NOW) / "merge.json").read_text(encoding="utf-8")
    )
    assert rec["has_output"] and rec["one_page_sha256"] is None


def test_f1_interrupt_during_main_call(root, packed, ollama, tools, monkeypatch):
    cid, _bd, win = packed
    real, n = RW.io.Ollama.chat, {"k": 0}

    def chat(self, body):
        n["k"] += 1
        if n["k"] == 3:  # 합성 · 세기 · 본
            raise KeyboardInterrupt
        return real(self, body)

    monkeypatch.setattr(RW.io.Ollama, "chat", chat)
    with pytest.raises(KeyboardInterrupt):
        run_win(win, ollama, tools)
    monkeypatch.undo()
    rd = win / "result_1"
    assert (rd / "main_started.json").exists() and not (rd / "main_raw.json").exists()
    assert result(win)["status"] == RW.INTERRUPTED
    assert (
        run_win(win, ollama, tools) == 2 and result(win, 2)["status"] == RW.ALREADY_RAN
    )
    rec = json.loads(
        (ME.merge(root, cid, rd, now=NOW) / "merge.json").read_text(encoding="utf-8")
    )
    assert rec["main_started"] and not rec["has_output"] and rec["main_status"] is None


@pytest.mark.parametrize("keep_raw", [True, False])
def test_f1_power_off_folder_is_kept(root, packed, ollama, tools, keep_raw):
    """결과 기록 전에 꺼진 폴더(시작 표지 · 받은 원문만)도 보관한다."""
    cid, _bd, win = packed
    assert run_win(win, ollama, tools) == 0
    rd = win / "result_1"
    for f in (
        "result.json",
        "hashes.json",
        "one_page.html",
        *(() if keep_raw else ("main_raw.json",)),
    ):
        (rd / f).unlink()
    out = ME.merge(root, cid, rd, now=NOW)
    rec = json.loads((out / "merge.json").read_text(encoding="utf-8"))
    assert (
        rec["status"] == ME.INCOMPLETE
        and rec["main_started"]
        and rec["has_output"] is keep_raw
    )
    assert (out / "main_raw.json").exists() is keep_raw


def test_f1_folder_without_anything_is_refused(root, packed, ollama, tools):
    cid, _bd, win = packed
    ollama.cfg = {"no_model": True}
    assert run_win(win, ollama, tools) == 2
    for f in ("result.json", "hashes.json"):
        (win / "result_1" / f).unlink()
    with pytest.raises(CheckRequired, match="보관할 것 없음"):
        ME.merge(root, cid, win / "result_1", now=NOW)


def test_f2_no_second_main_before_first_is_merged(root, packed, ollama, tools):
    """검증자 재현: 첫 묶음 본 요약을 회수하지 않고 새 묶음 → 거부(뒤 결과를 먼저 보관할 수 없음)."""
    cid, _bd, win = packed
    assert run_win(win, ollama, tools) == 0
    with pytest.raises(CheckRequired, match="먼저 회수"):
        BU.pack(root, cid, reason="아직 회수 전", now=NOW)
    ME.merge(root, cid, win / "result_1", now=NOW)
    with pytest.raises(CheckRequired, match="본 요약 시도가 이미 보관됨"):
        BU.pack(root, cid, reason="더 좋은 답", now=NOW)


def test_f2_merge_order(root, packed, ollama, tools, tmp_path, monkeypatch):
    cid, _bd, win = packed
    ollama.cfg = {"ctx": 8192}
    assert run_win(win, ollama, tools) == 2
    first = ME.merge(root, cid, win / "result_1", now=NOW)
    bd2 = BU.pack(root, cid, reason="다시", now=NOW)
    ollama.cfg = {}
    win2 = unzip(bd2, tmp_path / "w2")
    assert run_win(win2, ollama, tools) == 0
    shutil.rmtree(first)  # 앞 묶음 회수 기록이 없는 상태(뒤섞임 흉내)
    with pytest.raises(CheckRequired, match="앞 묶음 결과를 먼저 회수"):
        ME.merge(root, cid, win2 / "result_1", now=NOW)


@pytest.mark.parametrize(
    "cfg, why",
    [
        ({"no_version": True}, "Ollama 판"),
        ({"no_digest": True}, "digest"),
        ({"bad_digest": True}, "digest"),
    ],
)
def test_f3_env_record_required_before_any_model_call(
    root, packed, ollama, tools, cfg, why
):
    cid, _bd, win = packed
    ollama.cfg = cfg
    assert run_win(win, ollama, tools) == 2
    res = result(win)
    assert (
        res["status"] == RW.NEED_ENV
        and why in res["messages_ko"][0]
        and _chats(ollama) == 0
    )
    ME.merge(root, cid, win / "result_1", now=NOW)


def test_f3_env_changed_or_unreadable_after_main(
    root, packed, ollama, tools, tmp_path, monkeypatch
):
    cid, bd, win = packed
    ollama.cfg = {"digest_change_after": True}
    assert run_win(win, ollama, tools) == 2
    j = result(win)["main"]["judgement"]
    assert j["status"] == JU.TECHNICAL_FAILURE and "digest 가 바뀜" in " ".join(
        j["technical"]
    )
    ME.merge(root, cid, win / "result_1", now=NOW)
    ollama.cfg = {}
    real, n = RW._env_now, {"k": 0}

    def env_now(*a):
        n["k"] += 1
        if n["k"] == 3:  # 1 = 시작 · 2 = 본 요약 직전 · 3 = 본 요약 뒤
            raise OSError("판 다시 읽기 실패")
        return real(*a)

    monkeypatch.setattr(RW, "_env_now", env_now)
    win2 = unzip(bd, tmp_path / "again")  # 같은 묶음 다른 폴더(실행 구분만 확인)
    assert run_win(win2, ollama, tools) == 0  # 다시 읽기 실패는 기록만(상태 그대로)
    j2 = result(win2)["main"]["judgement"]
    assert j2["status"] == JU.COMPLETED and "다시 읽지 못함" in j2["note"]


@pytest.mark.parametrize(
    "change, msg",
    [
        (lambda r: r["env"].update(ollama_version=""), "Ollama 판 기록"),
        (lambda r: r["env"]["model"].update(digest=None), "digest 기록"),
        (lambda r: r["main"].update(ollama_version="0.1"), "환경 기록과 다름"),
    ],
)
def test_f3_merge_requires_env_record(root, packed, ollama, tools, change, msg):
    cid, _bd, win = packed
    assert run_win(win, ollama, tools) == 0
    with pytest.raises(CheckRequired, match=msg):
        ME.merge(root, cid, rewrite(win, 1, change), now=NOW)


def test_f4_usual_dev_time_is_fixed_zero_and_local_has_floor(
    root, packed, ollama, tools
):
    from app.review_summary import report as RP

    cid, _bd, win = packed
    ans = {"direction": "맞음", "limits": "맞음", "next": "맞음"}
    L = {
        "user_s": 8,
        "dev_s": 3,
        "elapsed_s": 20,
        "reopen": 0,
        "fixes": [],
        "reuse": "예",
        "answers": ans,
    }
    U = {"user_s": 10, "elapsed_s": 10, "reopen": 0, "fixes": [], "answers": ans}
    run = {
        "main_status": "COMPLETED",
        "status": "COMPLETED",
        "one_page_sha256": "p",
        "checks": {},
    }
    assert (
        RP.ac4({"critical_errors": 0}, {"L": L, "U": U}, run)["verdict"]
        == "사용 이점 미확인"
    )
    with pytest.raises(
        ValueError, match="0 으로 고정"
    ):  # 검증자 재현(U dev_s=2 → 관찰로 뒤집힘)
        RP.ac4({"critical_errors": 0}, {"L": L, "U": {**U, "dev_s": 2}}, run)
    assert run_win(win, ollama, tools) == 0
    out = ME.merge(root, cid, win / "result_1", now=NOW)
    sha = json.loads((out / "merge.json").read_text(encoding="utf-8"))[
        "one_page_sha256"
    ]
    score = {"critical_errors": 0, "one_page_sha256": sha}
    with pytest.raises(ValueError, match="명령 기록"):
        RP.build(root, cid, score, {"L": {**L, "dev_s": 0}, "U": U}, answers=True)
    table, _v = RP.build(
        root, cid, score, {"L": {**L, "dev_s": 600}, "U": U}, answers=True
    )
    assert "0초(계약 고정)" in table


# ── 정정 뒤 반박 검토 지적과 같은 종류(앞 폴더 · 부분 복사 · 깨진 파일 · 같은 폴더 다시 실행 · 판정 입력) ──


def _merge_rec(root, cid, rd) -> dict:
    out = ME.merge(root, cid, rd, now=NOW)
    return json.loads((out / "merge.json").read_text(encoding="utf-8"))


def test_already_ran_record_waits_for_the_earlier_folder(root, packed, ollama, tools):
    """다시 실행(ALREADY_RAN) 기록만 먼저 회수해 '본 요약 없음'으로 보이게 할 수 없다."""
    cid, _bd, win = packed
    assert run_win(win, ollama, tools) == 0
    assert run_win(win, ollama, tools) == 2
    again = result(win, 2)
    assert again["status"] == RW.ALREADY_RAN and "result_1" in again["messages_ko"][0]
    with pytest.raises(CheckRequired, match=r"같은 폴더의 앞 결과\(result_1\)"):
        ME.merge(root, cid, win / "result_2", now=NOW)
    assert _merge_rec(root, cid, win / "result_1")["main_started"]
    assert not _merge_rec(root, cid, win / "result_2")["main_started"]
    with pytest.raises(CheckRequired, match="본 요약 시도가 이미 보관됨"):
        BU.pack(root, cid, reason="다시", now=NOW)


def test_partial_copy_is_refused_but_power_off_is_kept(root, packed, ollama, tools):
    cid, _bd, win = packed
    assert run_win(win, ollama, tools) == 0
    rd = win / "result_1"
    body = (rd / "result.json").read_bytes()
    (rd / "result.json").unlink()  # hashes.json 은 마지막에 쓴다 → 있으면 복사 누락
    with pytest.raises(CheckRequired, match="복사 누락"):
        ME.merge(root, cid, rd, now=NOW)
    (rd / "result.json").write_bytes(body)
    (rd / "hashes.json").unlink()  # result.json 뒤 꺼짐
    rec = _merge_rec(root, cid, rd)
    assert rec["status"] == ME.INCOMPLETE and rec["main_started"] and rec["has_output"]
    assert rec["checks"]["result_unverified"] and rec["ollama_version"] == "0.40.17"
    assert rec["model_digest"] == json.loads(body)["env"]["model"]["digest"]
    with pytest.raises(CheckRequired, match="본 요약 시도가 이미 보관됨"):
        BU.pack(root, cid, reason="결과가 덜 쓰임", now=NOW)


def test_torn_raw_is_kept_as_bytes(root, packed, ollama, tools):
    cid, _bd, win = packed
    assert run_win(win, ollama, tools) == 0
    rd = win / "result_1"
    for f in ("result.json", "hashes.json", "one_page.html"):
        (rd / f).unlink()
    torn = (rd / "main_raw.json").read_bytes()[:40]
    (rd / "main_raw.json").write_bytes(torn)
    out = ME.merge(root, cid, rd, now=NOW)
    rec = json.loads((out / "merge.json").read_text(encoding="utf-8"))
    assert rec["checks"]["raw_unparsed"] and rec["has_output"] is None
    assert (out / "main_raw.json").read_bytes() == torn


@pytest.mark.parametrize(
    "change, msg",
    [
        (lambda m: m.update(case_id="other"), "다른 사례"),
        (lambda m: m.update(run_id="x"), "실행 id 꼴"),
        (lambda m: m.update(at="2026-11-23T10:00:00"), "시각이 없거나"),
        (lambda m: m.update(at=None), "시각이 없거나"),
    ],
)
def test_incomplete_marker_is_checked(root, packed, ollama, tools, change, msg):
    cid, _bd, win = packed
    assert run_win(win, ollama, tools) == 0
    rd = win / "result_1"
    for f in ("result.json", "hashes.json", "main_raw.json"):
        (rd / f).unlink()
    m = json.loads((rd / RW.MAIN_STARTED).read_text(encoding="utf-8"))
    change(m)
    (rd / RW.MAIN_STARTED).write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(CheckRequired, match=msg):
        ME.merge(root, cid, rd, now=NOW)


def test_marker_env_must_match_the_result(root, packed, ollama, tools):
    cid, _bd, win = packed
    assert run_win(win, ollama, tools) == 0
    p = win / "result_1" / RW.MAIN_STARTED
    m = json.loads(p.read_text(encoding="utf-8"))
    p.write_text(json.dumps({**m, "model_digest": "f" * 64}), encoding="utf-8")
    with pytest.raises(CheckRequired, match="main_started.json 해시가"):
        ME.merge(root, cid, win / "result_1", now=NOW)
    _rehash(
        win / "result_1", RW.MAIN_STARTED
    )  # 해시까지 맞춰도 판이 결과와 다르면 거부
    with pytest.raises(CheckRequired, match="시작 표지의 Ollama 판"):
        ME.merge(root, cid, win / "result_1", now=NOW)


@pytest.mark.parametrize(
    "cfg, kinds, rerun",
    [
        ({"ctx": 8192}, ["SETTINGS"], False),
        ({"bad_korean": True}, ["MODEL"], False),
        ({"vram": 0}, ["ENV", "SETTINGS"], False),  # CPU 단독 = 메모리(설정)일 수 있음
    ],
)
def test_same_folder_rerun_after_trial_stop(
    root, packed, ollama, tools, cfg, kinds, rerun
):
    """설정 · 모델 문제 멈춤은 같은 폴더로 다시 돌지 않는다(맥북에서 새 묶음 · 설계자 보고) · 환경 문제만 다시."""
    cid, _bd, win = packed
    ollama.cfg = cfg
    assert run_win(win, ollama, tools) == 2
    assert result(win)["trial"]["gate"]["categories"] == kinds
    ollama.cfg, calls = {}, _chats(ollama)
    rc = run_win(win, ollama, tools)
    second = result(win, 2)
    if rerun:
        assert rc == 0 and second["status"] == JU.COMPLETED
    else:
        assert second["status"] == RW.ALREADY_RAN and _chats(ollama) == calls
    ME.merge(root, cid, win / "result_1", now=NOW)
    ME.merge(root, cid, win / "result_2", now=NOW)


def test_window_closed_before_main_allows_same_folder_rerun(
    root, packed, ollama, tools, monkeypatch
):
    """본 요약 전에 창을 닫아 비어 남은 폴더는 같은 폴더 다시 실행을 막지 않는다 · 다른 창이 실행 중이면 막는다."""
    cid, _bd, win = packed
    (win / "result_1").mkdir()
    (win / "result_1" / RW.LOCK).write_bytes(
        b""
    )  # 꺼진 실행이 남긴 잠금(열린 손잡이 없음)
    real = type(win).unlink

    def held(self, *a, **k):
        if self.name == RW.LOCK and self.parent.name == "result_1":
            raise PermissionError("열려 있음")
        return real(self, *a, **k)

    monkeypatch.setattr(type(win), "unlink", held)
    assert run_win(win, ollama, tools) == 2
    busy = result(win, 2)
    assert busy["status"] == RW.ALREADY_RAN and "아직 실행 중" in busy["messages_ko"][0]
    assert _chats(ollama) == 0
    monkeypatch.undo()
    assert (
        run_win(win, ollama, tools) == 0
    )  # 잠금이 풀린 빈 폴더 · 멈춤 기록은 막지 않음
    assert result(win, 3)["status"] == JU.COMPLETED
    assert not (win / "result_1" / RW.LOCK).exists()
    assert not (win / "result_3" / RW.LOCK).exists()
    with pytest.raises(CheckRequired, match="보관할 것 없음"):
        ME.merge(root, cid, win / "result_1", now=NOW)
    with pytest.raises(CheckRequired, match=r"앞 결과\(result_2\)"):
        ME.merge(root, cid, win / "result_3", now=NOW)
    ME.merge(root, cid, win / "result_2", now=NOW)
    assert _merge_rec(root, cid, win / "result_3")["main_status"] == JU.COMPLETED


@pytest.mark.parametrize("lock", [True, False])
def test_empty_earlier_folder_does_not_block(root, packed, ollama, tools, lock):
    """폴더만 만들고 꺼진 실행(잠금 파일이 남았든 없든) — 같은 폴더 다시 실행으로 본 요약까지 간다."""
    _cid, _bd, win = packed
    (win / "result_1").mkdir()
    if lock:
        (win / "result_1" / RW.LOCK).write_bytes(b"")
    assert run_win(win, ollama, tools) == 0
    assert result(win, 2)["prior_results"][0]["running"] is False


def test_ctrl_c_during_main_wait_writes_raw_first(
    root, packed, ollama, tools, monkeypatch
):
    """Windows 는 응답을 기다리는 중 Ctrl+C 가 깨우지 못함 — 미룬 뒤 받은 원문을 먼저 쓰고 멈춘다."""
    import signal

    cid, _bd, win = packed
    real, n = RW.io.Ollama.chat, {"k": 0}

    def chat(self, body):
        n["k"] += 1
        if n["k"] == 3:  # 본 요약 호출 중 Ctrl+C
            signal.raise_signal(signal.SIGINT)
        return real(self, body)

    before = signal.getsignal(signal.SIGINT)
    monkeypatch.setattr(RW.io.Ollama, "chat", chat)
    with pytest.raises(KeyboardInterrupt):
        run_win(win, ollama, tools)
    monkeypatch.undo()
    assert signal.getsignal(signal.SIGINT) is before
    rd = win / "result_1"
    raw = json.loads((rd / RW.MAIN_RAW).read_text(encoding="utf-8"))
    res = result(win)
    assert res["status"] == RW.INTERRUPTED and raw["response"]["message"]["content"]
    rec = _merge_rec(root, cid, rd)
    assert rec["has_output"] and rec["main_started"]


def test_score_needs_the_page(root, packed, ollama, tools, monkeypatch):
    from app.review_summary import report as RP

    cid, _bd, win = packed
    monkeypatch.setattr(RW.render, "render_html", lambda *a, **k: 1 / 0)
    assert run_win(win, ollama, tools) == 0
    monkeypatch.undo()
    ME.merge(root, cid, win / "result_1", now=NOW)
    for score in (
        {"critical_errors": 0},
        {"critical_errors": 0, "one_page_sha256": ""},
    ):
        _t, v = RP.build(root, cid, score, {}, answers=True)
        assert v["verdict"] == "판정 불가" and "한 장이 없음" in v["reasons"][0]


def test_dev_floor_counts_every_pack_and_merge(root, packed, ollama, tools, tmp_path):
    from app.review_summary import report as RP

    cid, bd, win = packed
    ollama.cfg = {"ctx": 8192}
    assert run_win(win, ollama, tools) == 2
    m1 = _merge_rec(root, cid, win / "result_1")
    bd2 = BU.pack(root, cid, lengths={"num_ctx": 65536}, reason="문맥", now=NOW)
    ollama.cfg = {"ctx": 65536}
    win2 = unzip(bd2, tmp_path / "w2")
    assert run_win(win2, ollama, tools) == 0
    m2 = _merge_rec(root, cid, win2 / "result_1")
    packs = [
        json.loads((b / "pack.json").read_text(encoding="utf-8")) for b in (bd, bd2)
    ]
    floor = (sum(p["dev_ms"] for p in packs) + m1["dev_ms"] + m2["dev_ms"]) / 1000
    ans = {"direction": "맞음", "limits": "맞음", "next": "맞음"}
    L = {
        "user_s": 8,
        "elapsed_s": 20,
        "reopen": 0,
        "fixes": [],
        "reuse": "예",
        "answers": ans,
    }
    U = {"user_s": 10, "elapsed_s": 10, "reopen": 0, "fixes": [], "answers": ans}
    score = {"critical_errors": 0, "one_page_sha256": m2["one_page_sha256"]}
    table, _v = RP.build(root, cid, score, {"L": L, "U": U}, answers=True)
    assert "명령 기록 pack 2회 · merge 2회" in table
    for given, ok in ((floor, True), (floor - 0.001, False)):
        usage = {"L": {**L, "dev_s": given}, "U": U}
        if ok:
            RP.build(root, cid, score, usage, answers=True)
        else:
            with pytest.raises(ValueError, match="명령 기록"):
                RP.build(root, cid, score, usage, answers=True)


# ── 회수 대조 하나하나 — 그것만 어긋난 경우(대조가 겹쳐도 각자 자기 문구로 거부) ──


def _rehash(rd, *names) -> None:
    h = json.loads((rd / "hashes.json").read_text(encoding="utf-8"))
    for n in names:
        h[n] = RW.sha_bytes((rd / n).read_bytes()) if (rd / n).exists() else None
    (rd / "hashes.json").write_text(json.dumps(h), encoding="utf-8")


def _raw(rd, change, rehash=True) -> None:
    p = rd / RW.MAIN_RAW
    r = json.loads(p.read_text(encoding="utf-8"))
    change(r)
    p.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    if rehash:
        _rehash(rd, RW.MAIN_RAW)


def _drop(rd, name, rehash=False) -> None:
    (rd / name).unlink()
    if rehash:
        _rehash(rd, name)


def _page(rd) -> None:
    p = rd / "one_page.html"
    p.write_bytes(p.read_bytes() + b" ")
    _rehash(rd, "one_page.html")


SINGLE = [
    (
        lambda w, rd: _drop(rd, RW.MAIN_RAW, rehash=True),
        "받은 원문\\(main_raw.json\\)이 없음",
    ),
    (lambda w, rd: _drop(rd, RW.MAIN_RAW), "hashes.json 에 받은 원문이 있는데"),
    (
        lambda w, rd: _raw(rd, lambda r: r.update(received_at="x"), rehash=False),
        "main_raw.json 해시가",
    ),
    (
        lambda w, rd: _raw(rd, lambda r: r.update(run_id="20260101T000000_00000000")),
        "받은 원문의 실행 id 가 결과와",
    ),
    (
        lambda w, rd: _raw(rd, lambda r: r.update(call_error="끊김")),
        "호출 오류가 받은 원문과",
    ),
    (
        lambda w, rd: _drop(rd, RW.MAIN_STARTED),
        "hashes.json 에 시작 표지가 있는데",
    ),
    (
        lambda w, rd: _drop(rd, RW.MAIN_STARTED, rehash=True),
        "시작 표지\\(main_started.json\\)가 없음",
    ),
    (
        lambda w, rd: rewrite(w, 1, lambda r: r["main"].pop("judgement")),
        "구분이 없는 본 요약",
    ),
    (
        lambda w, rd: rewrite(
            w,
            1,
            lambda r: (
                r["main"].update(status=JU.TECHNICAL_FAILURE),
                r.update(status=JU.TECHNICAL_FAILURE),
            ),
        ),
        "본 요약 구분과 본 요약 상태가 다름",
    ),
    (
        lambda w, rd: rewrite(w, 1, lambda r: r.update(render_error="x")),
        "한 장 만들기 오류인데",
    ),
    (lambda w, rd: _drop(rd, "one_page.html"), "one_page.html 이 없음"),
    (lambda w, rd: _page(rd), "다시 만든 한 장이"),
    (
        lambda w, rd: rewrite(w, 1, lambda r: r["trial"].pop("judgement")),
        "구분이 없는 합성 점검",
    ),
]


@pytest.mark.parametrize("tamper, msg", SINGLE)
def test_each_merge_check_refuses_alone(root, packed, ollama, tools, tamper, msg):
    cid, _bd, win = packed
    assert run_win(win, ollama, tools) == 0
    rd = win / "result_1"
    tamper(win, rd)
    with pytest.raises(CheckRequired, match=msg):
        ME.merge(root, cid, rd, now=NOW)


def test_marker_on_a_run_without_main_is_refused(root, packed, ollama, tools):
    cid, _bd, win = packed
    ollama.cfg = {"ctx": 8192}
    assert run_win(win, ollama, tools) == 2
    rd, r = win / "result_1", result(win)
    inp = json.loads((win / "bundle_input.json").read_text(encoding="utf-8"))
    marker = (
        {  # 이 실행에 맞춘 시작 표지(해시까지) — 본 요약 없이 표지만 있는 멈춤 기록
            "run_id": r["run_id"],
            "bundle_id": r["bundle_id"],
            "case_id": cid,
            "result_dir": "result_1",
            "at": r["started_at"],
            "ollama_version": r["env"]["ollama_version"],
            "model_digest": r["env"]["model"]["digest"],
            "options": inp["options"],
        }
    )
    (rd / RW.MAIN_STARTED).write_text(json.dumps(marker), encoding="utf-8")
    _rehash(rd, RW.MAIN_STARTED)
    with pytest.raises(CheckRequired, match="본 요약을 시작했는데 멈춤 상태가 아님"):
        ME.merge(root, cid, win / "result_1", now=NOW)


def test_incomplete_raw_must_match_marker(root, packed, ollama, tools):
    cid, _bd, win = packed
    assert run_win(win, ollama, tools) == 0
    rd = win / "result_1"
    for f in ("result.json", "hashes.json"):
        (rd / f).unlink()
    _raw(rd, lambda r: r.update(run_id="20260101T000000_00000000"), rehash=False)
    with pytest.raises(CheckRequired, match="시작 표지와 다름"):
        ME.merge(root, cid, rd, now=NOW)


# ── 검증자 r2 F5 ~ F8 과 같은 종류(쓰다 끊긴 파일 · 본 호출 직전 확정 실패 · 섞인 표지 · 사람 입력 숫자) ──


def _full_run(win, ollama, tools):
    assert run_win(win, ollama, tools) == 0
    return win / "result_1"


def test_atomic_names_and_marker_hash(packed, ollama, tools):
    """시작 표지 · 한 장 · 결과 · 해시는 다 쓴 뒤 이름을 바꾼다(임시 이름 · 잠금이 남지 않음) · 표지도 해시에."""
    _cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    names = sorted(p.name for p in rd.iterdir())
    assert not [n for n in names if n.endswith(".part")] and RW.LOCK not in names
    h = json.loads((rd / "hashes.json").read_text(encoding="utf-8"))
    assert h[RW.MAIN_STARTED] == RW.sha_bytes((rd / RW.MAIN_STARTED).read_bytes())


def test_write_new_never_overwrites(tmp_path):
    p = tmp_path / "a.json"
    RW.write_new(p, b"1")
    with pytest.raises(FileExistsError):
        RW.write_new(p, b"2")
    assert p.read_bytes() == b"1"
    (tmp_path / ".b.json.part").write_bytes(
        b"x"
    )  # 앞서 끊긴 임시 파일 — 덮지 않고 멈춤
    with pytest.raises(FileExistsError):
        RW.write_new(tmp_path / "b.json", b"y")
    assert not (tmp_path / "b.json").exists()


@pytest.mark.parametrize("torn", [b"", b'{"one_page.html": "ab'])
def test_torn_hashes_is_kept_as_incomplete(root, packed, ollama, tools, torn):
    """검증자 r2 F5①: 마지막 해시 쓰기가 끊긴 폴더 — 거부하지 않고 기록 미완으로 받되 판정에는 쓰지 않는다."""
    from app.review_summary import report as RP

    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    (rd / "hashes.json").write_bytes(torn)
    rec = _merge_rec(root, cid, rd)
    assert rec["status"] == ME.INCOMPLETE and rec["checks"]["hashes_broken"]
    assert rec["has_output"] and rec["record_dir"].endswith("__incomplete")
    score = {"critical_errors": 0, "one_page_sha256": rec["one_page_sha256"]}
    _t, v = RP.build(root, cid, score, {}, answers=True)
    assert v["verdict"] == "판정 불가" and "다 쓰이지 않음" in v["reasons"][0]


@pytest.mark.parametrize("keep_raw", [True, False])
def test_rerun_after_power_off_merges_in_order(root, packed, ollama, tools, keep_raw):
    """검증자 r2 F5②: 결과 기록 전 꺼짐 → 같은 폴더 다시 실행(ALREADY_RAN) → 앞 폴더를 기록 미완으로 받은 뒤 뒤 기록도."""
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    rid = result(win)["run_id"]
    for f in ("result.json", "hashes.json", "one_page.html"):
        (rd / f).unlink()
    if not keep_raw:
        (rd / RW.MAIN_RAW).unlink()
    assert run_win(win, ollama, tools) == 2
    again = result(win, 2)
    assert again["status"] == RW.ALREADY_RAN
    assert again["prior_results"][0]["run_id"] == rid  # 시작 표지에서 읽음
    with pytest.raises(CheckRequired, match=r"앞 결과\(result_1\)"):
        ME.merge(root, cid, win / "result_2", now=NOW)
    assert _merge_rec(root, cid, rd)["status"] == ME.INCOMPLETE
    assert _merge_rec(root, cid, win / "result_2")["status"] == RW.ALREADY_RAN


def test_incomplete_then_full_copy_is_upgraded(root, packed, ollama, tools, tmp_path):
    """먼저 일부만 복사해 기록 미완으로 받은 실행의 완전한 폴더가 뒤에 오면 같은 바이트를 확인하고 받는다."""
    from app.review_summary import report as RP

    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    part = tmp_path / "copy" / "result_1"
    shutil.copytree(rd, part)
    for f in ("result.json", "hashes.json", "one_page.html"):
        (part / f).unlink()
    first = _merge_rec(root, cid, part)
    with pytest.raises(FileExistsError):
        ME.merge(root, cid, part, now=NOW)
    full = _merge_rec(root, cid, rd)
    assert (
        full["replaces"] == first["record_dir"] and full["main_status"] == JU.COMPLETED
    )
    assert [r["record_dir"] for r in BU.merged_runs(root, cid)] == [full["record_dir"]]
    with pytest.raises(FileExistsError):
        ME.merge(root, cid, rd, now=NOW)
    score = {"critical_errors": 0, "one_page_sha256": full["one_page_sha256"]}
    _t, v = RP.build(root, cid, score, {}, answers=True)
    assert v["verdict"] == "사용 이점 미확인"  # 시도 1건 · 실측만 빠짐(판정 불가 아님)


def test_verified_folder_supersedes_differing_unverified_bytes(
    root, packed, ollama, tools, tmp_path
):
    """검증 못 한 기록 미완(원문 손상 · 결과 없음)을 먼저 받아도, 해시로 검증된 원본은 받고 다른 파일을 기록한다."""
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    part = tmp_path / "copy" / "result_1"
    shutil.copytree(rd, part)
    for f in ("result.json", "hashes.json", "one_page.html"):
        (part / f).unlink()
    raw = (rd / RW.MAIN_RAW).read_bytes()
    (part / RW.MAIN_RAW).write_bytes(
        b"X" + raw[1:30]
    )  # 앞부분도 아닌 다른 바이트(손상)
    assert _merge_rec(root, cid, part)["checks"]["raw_unparsed"]
    full = _merge_rec(root, cid, rd)
    assert full["main_status"] == JU.COMPLETED and full["kept_differs"] == [RW.MAIN_RAW]


def test_upgrade_accepts_torn_raw_prefix(root, packed, ollama, tools, tmp_path):
    """복사 중 잘린 원문(완전한 원문의 앞부분)으로 먼저 받았어도 완전한 폴더로 대신 받는다."""
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    part = tmp_path / "copy" / "result_1"
    shutil.copytree(rd, part)
    for f in ("result.json", "hashes.json", "one_page.html"):
        (part / f).unlink()
    (part / RW.MAIN_RAW).write_bytes((rd / RW.MAIN_RAW).read_bytes()[:30])
    first = _merge_rec(root, cid, part)
    assert _merge_rec(root, cid, rd)["replaces"] == first["record_dir"]


def test_clock_difference_is_noted_not_refused(root, packed, ollama, tools):
    """PC 시계가 맥북보다 늦거나 실행 중 시간 맞춤이 되돌려도 진짜 실행은 받는다(순서는 메모만)."""
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    m = json.loads((rd / RW.MAIN_STARTED).read_text(encoding="utf-8"))
    m["at"] = "2000-01-01T00:00:00+09:00"
    (rd / RW.MAIN_STARTED).write_text(
        json.dumps(m, ensure_ascii=False), encoding="utf-8"
    )
    _rehash(rd, RW.MAIN_STARTED)
    rec = _merge_rec(root, cid, rd)
    assert rec["main_status"] == JU.COMPLETED
    assert "after_bundle_s" in rec["checks"]["clock"]["out_of_order"]


def test_stop_record_without_hashes_is_kept_and_ordered(root, packed, ollama, tools):
    """본 요약 없이 멈춘 실행이 해시 쓰기 전 꺼져도 받고, 결과 기록을 원값으로 대조한 멈춤은 길이 변경 근거가 된다."""
    cid, _bd, win = packed
    ollama.cfg = {"ctx": 8192}
    assert run_win(win, ollama, tools) == 2
    (win / "result_1" / "hashes.json").unlink()
    ollama.cfg = {}
    assert run_win(win, ollama, tools) == 2
    assert (
        result(win, 2)["status"] == RW.ALREADY_RAN
    )  # 설정 멈춤 기록이 읽혀 다시 돌지 않음
    rec = _merge_rec(root, cid, win / "result_1")
    assert rec["status"] == ME.INCOMPLETE and not rec["main_started"]
    assert rec["checks"]["claimed_status"] == RW.TRIAL_STOPPED
    assert rec["checks"]["claim_checked"] and rec["trial_categories"] == ["SETTINGS"]
    _merge_rec(root, cid, win / "result_2")
    BU.pack(root, cid, lengths={"num_ctx": 65536}, reason="문맥", now=NOW)


def test_damaged_marker_is_refused_and_blocks_by_name(root, packed, ollama, tools):
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    for f in ("result.json", "hashes.json", "one_page.html", RW.MAIN_RAW):
        (rd / f).unlink()
    (rd / RW.MAIN_STARTED).write_bytes(b'{"run_id": "2026')
    with pytest.raises(CheckRequired, match=r"시작 표지\(main_started.json\)가 깨짐"):
        ME.merge(root, cid, rd, now=NOW)
    assert run_win(win, ollama, tools) == 2  # 표지가 있으면 본 요약을 시작했을 수 있다
    assert result(win, 2)["status"] == RW.ALREADY_RAN and _chats(ollama) == 3
    with pytest.raises(CheckRequired, match="실행 id 를 알 수 없음"):
        ME.merge(root, cid, win / "result_2", now=NOW)


def _other_marker(win, tmp_path, bd, ollama, tools) -> bytes:
    win2 = unzip(bd, tmp_path / "again")
    assert run_win(win2, ollama, tools) == 0
    return (win2 / "result_1" / RW.MAIN_STARTED).read_bytes()


@pytest.mark.parametrize(
    "drop, msg",
    [
        ((), "main_started.json 해시가"),
        (("result.json", "hashes.json"), "받은 원문의 실행 id 가 시작 표지와 다름"),
        (("hashes.json", RW.MAIN_RAW), "result.json 이 시작 표지와 다른 실행"),
    ],
)
def test_marker_from_another_run_is_refused(
    root, packed, ollama, tools, tmp_path, drop, msg
):
    """검증자 r2 F7 재현: 같은 zip 을 따로 풀어 두 번 돌린 뒤 두 번째 실행의 시작 표지만 첫 폴더에 복사."""
    cid, bd, win = packed
    rd = _full_run(win, ollama, tools)
    (rd / RW.MAIN_STARTED).write_bytes(_other_marker(win, tmp_path, bd, ollama, tools))
    for f in drop:
        (rd / f).unlink()
    with pytest.raises(CheckRequired, match=msg):
        ME.merge(root, cid, rd, now=NOW)
    if not drop:
        _rehash(rd, RW.MAIN_STARTED)
        with pytest.raises(CheckRequired, match="시작 표지의 실행 id 가 결과와 다름"):
            ME.merge(root, cid, rd, now=NOW)


@pytest.mark.parametrize(
    "change, msg",
    [
        (lambda m, i: m.update(result_dir="result_2"), "결과 폴더 이름이 다름"),
        (
            lambda m, i: m.update(options={**m["options"], "seed": 1}),
            "설정이 묶음과 다름",
        ),
        (lambda m, i: m.update(model_digest=None), "digest 기록이 없거나"),
        (lambda m, i: m.update(ollama_version=""), "Ollama 판 기록이 없음"),
    ],
)
def test_marker_fields_must_match_this_run(root, packed, ollama, tools, change, msg):
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    inp = json.loads((win / "bundle_input.json").read_text(encoding="utf-8"))
    m = json.loads((rd / RW.MAIN_STARTED).read_text(encoding="utf-8"))
    change(m, inp)
    (rd / RW.MAIN_STARTED).write_text(
        json.dumps(m, ensure_ascii=False), encoding="utf-8"
    )
    _rehash(rd, RW.MAIN_STARTED)
    with pytest.raises(CheckRequired, match=msg):
        ME.merge(root, cid, rd, now=NOW)


@pytest.mark.parametrize(
    "cfg, kinds, why, rerun",
    [
        ({"digest_change": True}, ["MODEL"], "digest 가 처음 읽은 값과 다름", False),
        ({"version_change": True}, ["ENV"], "Ollama 판이 처음 읽은 값과 다름", True),
        ({"digest_gone": True}, ["MODEL"], "digest 가 없거나", False),
        ({"count_404": True}, ["ENV"], "토큰 세기 호출 오류", True),
        ({"trunc": True}, ["SETTINGS"], "토큰 세기의 server.log 잘림", False),
        ({"count_delta": 10**6}, ["SETTINGS"], "≥ 문맥", False),
    ],
)
def test_pre_main_gate_stops_before_the_single_attempt(
    root, packed, ollama, tools, cfg, kinds, why, rerun
):
    """검증자 r2 F6: 토큰 세기 뒤 판 · digest 가 바뀌거나 빠지거나, 세기가 실패 · 잘림 · 문맥 초과면 본 요약을 부르지 않는다."""
    cid, _bd, win = packed
    ollama.cfg = cfg
    assert run_win(win, ollama, tools) == 2
    res = result(win)
    assert res["status"] == RW.PRE_MAIN_STOPPED and res["main"] is None
    assert res["pre_main"]["categories"] == kinds and why in " ".join(
        res["pre_main"]["reasons"]
    )
    assert _chats(ollama) == 2 and not (win / "result_1" / RW.MAIN_STARTED).exists()
    ollama.cfg = {}
    run_win(win, ollama, tools)
    second = result(win, 2)
    assert (second["status"] == JU.COMPLETED) is rerun
    assert (second["status"] == RW.ALREADY_RAN) is not rerun
    rec = _merge_rec(root, cid, win / "result_1")
    assert rec["pre_main_categories"] == kinds and not rec["main_started"]
    _merge_rec(root, cid, win / "result_2")


def test_pre_main_env_unreadable_stops(root, packed, ollama, tools, monkeypatch):
    cid, _bd, win = packed
    real, n = RW._env_now, {"k": 0}

    def env_now(*a):
        n["k"] += 1
        if n["k"] == 2:
            raise OSError("다시 읽기 실패")
        return real(*a)

    monkeypatch.setattr(RW, "_env_now", env_now)
    assert run_win(win, ollama, tools) == 2
    res = result(win)
    assert res["status"] == RW.PRE_MAIN_STOPPED and res["env_before_main"] is None
    assert "다시 읽지 못함" in res["pre_main"]["reasons"][0] and _chats(ollama) == 2
    monkeypatch.undo()
    _merge_rec(root, cid, win / "result_1")


def test_lengths_after_pre_main_stop(root, packed, ollama, tools):
    cid, _bd, win = packed
    ollama.cfg = {
        "count_404": True
    }  # 환경 멈춤 — 같은 폴더에서 다시(새 묶음 · 길이 변경 근거 아님)
    assert run_win(win, ollama, tools) == 2
    ollama.cfg = {"count_delta": 10**6}  # 다시 돌려 설정 멈춤 — 길이만 고친 새 묶음
    assert run_win(win, ollama, tools) == 2
    _merge_rec(root, cid, win / "result_1")
    _merge_rec(root, cid, win / "result_2")
    BU.pack(root, cid, lengths={"num_ctx": 65536}, reason="문맥 부족", now=NOW)


@pytest.mark.parametrize(
    "change, msg",
    [
        (lambda r: r.pop("pre_main"), "직전 확인 없이 본 요약"),
        (
            lambda r: r["env_before_main"].update(model_digest="e" * 64),
            "원값에서 다시 하면",
        ),
        (
            lambda r: r["count"].update(trunc_log=["truncating input prompt"]),
            "원값에서 다시 하면",
        ),
        (lambda r: r.update(env_before_main=[1]), "다시 읽은 판 기록이 없음"),
    ],
)
def test_merge_rechecks_pre_main(root, packed, ollama, tools, change, msg):
    cid, _bd, win = packed
    _full_run(win, ollama, tools)
    with pytest.raises(CheckRequired, match=msg):
        ME.merge(root, cid, rewrite(win, 1, change), now=NOW)


@pytest.mark.parametrize(
    "change, msg",
    [
        (
            lambda r: r["pre_main"].update(ok=True, reasons=[], categories=[]),
            "원값에서 다시 하면",
        ),
        (
            lambda r: r.update(status="NEED_MODEL", stop="NEED_MODEL"),
            "못 넘었는데 그 멈춤이 아님",
        ),
    ],
)
def test_merge_rechecks_pre_main_stop(root, packed, ollama, tools, change, msg):
    cid, _bd, win = packed
    ollama.cfg = {"digest_change": True}
    assert run_win(win, ollama, tools) == 2
    with pytest.raises(CheckRequired, match=msg):
        ME.merge(root, cid, rewrite(win, 1, change), now=NOW)


def test_usb_json_with_non_finite_numbers_is_refused(root, packed, ollama, tools):
    cid, _bd, win = packed
    _full_run(win, ollama, tools)
    rd = rewrite(win, 1, lambda r: r["main"].update(wall_s=float("nan")))
    with pytest.raises(CheckRequired, match="result.json 이 JSON 이 아님"):
        ME.merge(root, cid, rd, now=NOW)


@pytest.mark.parametrize(
    "bad", [float("inf"), float("nan"), -1, True, 10**400, "10", [1]]
)
def test_seconds_must_be_finite_numbers(bad):
    from app.review_summary import report as RP

    with pytest.raises(ValueError):
        RP.secs({"user_s": bad}, "user_s")


def test_r2_f8_infinite_time_does_not_flip_the_verdict():
    """검증자 r2 F8 재현: U 직접 시간 1e309(무한대) · NaN 은 실측이 아니다 — 판정을 바꾸지 않고 오류."""
    from app.review_summary import report as RP

    ans = {"direction": "맞음", "limits": "맞음", "next": "맞음"}
    L = {
        "user_s": 8,
        "dev_s": 3,
        "elapsed_s": 20,
        "reopen": 0,
        "fixes": [],
        "reuse": "예",
        "answers": ans,
    }
    U = {"user_s": 10, "elapsed_s": 10, "reopen": 0, "fixes": [], "answers": ans}
    run = {
        "main_status": "COMPLETED",
        "status": "COMPLETED",
        "one_page_sha256": "p",
        "checks": {},
    }
    score = {"critical_errors": 0}
    assert RP.ac4(score, {"L": L, "U": U}, run)["verdict"] == "사용 이점 미확인"
    for bad in (float("inf"), float("nan")):
        with pytest.raises(ValueError):
            RP.ac4(score, {"L": L, "U": {**U, "user_s": bad}}, run)
        with pytest.raises(ValueError):
            RP.ac4(score, {"L": L, "U": {**U, "dev_s": bad}}, run)
    assert (
        RP.ac4(score, {"L": L, "U": {**U, "dev_s": 0.0}}, run)["verdict"]
        == "사용 이점 미확인"
    )
    for usage in ({"L": [1], "U": U}, {"L": L, "U": "10"}):
        with pytest.raises(ValueError, match="JSON 객체"):
            RP.ac4(score, usage, run)


@pytest.mark.parametrize(
    "text",
    [
        '{"critical_errors": 0, "x": NaN}',
        '{"critical_errors": 0, "x": Infinity}',
        '{"critical_errors": 0, "x": -Infinity}',
        '{"critical_errors": 0, "x": 1e309}',
        "[1, 2]",
    ],
)
def test_cli_refuses_non_finite_or_non_object_json(
    root, packed, ollama, tools, tmp_path, capsys, text
):
    from scripts import run_review_summary as CLI

    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    sha = _merge_rec(root, cid, rd)["one_page_sha256"]
    good_u = tmp_path / "usage.json"
    good_u.write_text("{}", encoding="utf-8")
    good_s = (
        tmp_path / "good_score.json"
    )  # 정상 채점(해시 있음) — 사용 기록만 잘못일 때 그것 때문에 거부되는지
    good_s.write_text(
        json.dumps({"critical_errors": 0, "one_page_sha256": sha}), encoding="utf-8"
    )
    args0 = ["--root", str(root), "report", "--case", cid]
    assert CLI.main([*args0, "--score", str(good_s), "--usage", str(good_u)]) == 0
    capsys.readouterr()
    bad = tmp_path / "bad.json"
    bad.write_text(
        text.replace("0,", f'0, "one_page_sha256": "{sha}",', 1), encoding="utf-8"
    )
    for s, u in ((bad, good_u), (good_s, bad)):
        args = [
            "--root",
            str(root),
            "report",
            "--case",
            cid,
            "--score",
            str(s),
            "--usage",
            str(u),
        ]
        assert CLI.main(args) == 2
        assert "CHECK_REQUIRED" in capsys.readouterr().out
