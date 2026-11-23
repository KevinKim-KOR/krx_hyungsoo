"""POC7-02 검증자 r3 정정 뒤 잠금 전 반박 검토(네 관점 · 24건)와 같은 종류 — 상태 · 정체 · 순서 칸.

A 멈춤 종류(안내 중 중단 · 기록 미완) · B 정체 없는 기록 · C 고정 모델 digest · D 새 묶음은 설정 · 모델 멈춤 뒤에만
· E 기록 미완 ↔ 완료 경로 같은 대조 · F 대신 받기 · G 판정 불가 전 입력 검사 · H 단조 시계 실행 시간 · I 못 읽음 ≠ 없음.
준비물은 흐름 · 회복 · 경계 시험에서 가져다 쓴다.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta

import pytest

from app.entry_timing.protocol import CheckRequired
from app.review_summary import bundle as BU
from app.review_summary import judge as JU
from app.review_summary import merge as ME
from app.review_summary import report as RP
from app.review_summary import runner_files as RF
from app.review_summary import runner_win as RW
from tests import test_poc7_02_review_summary as M
from tests import test_poc7_02_review_summary_boundaries as B
from tests import test_poc7_02_review_summary_recovery as R

NOW = M.NOW
ollama, tools, root, packed = M.ollama, M.tools, M.root, M.packed
run_win, result, rewrite, unzip = M.run_win, M.result, M.rewrite, M.unzip
_chats, _merge_rec, _rehash, _full_run = R._chats, R._merge_rec, R._rehash, R._full_run
_usage, _result_rename_fails = B._usage, B._result_rename_fails


def _ctrl_c_on(monkeypatch, prefix):
    real = RW._say

    def say(res, text):
        real(res, text)
        if text.startswith(prefix):
            raise KeyboardInterrupt

    monkeypatch.setattr(RW, "_say", say)


def _hold_lock(monkeypatch, win, name):
    (win / name).mkdir()
    (win / name / RW.LOCK).write_bytes(b"")
    real = type(win).unlink

    def held(self, *a, **k):
        if self.name == RW.LOCK and self.parent.name == name:
            raise PermissionError("열려 있음")
        return real(self, *a, **k)

    monkeypatch.setattr(type(win), "unlink", held)


# ── A 멈춤 종류 — 안내 중 중단 · 기록 미완이어도 무슨 멈춤이었는지 ──


def test_ctrl_c_on_bundle_changed_message_is_still_mergeable(
    root, packed, ollama, tools, monkeypatch
):
    cid, bd, win = packed
    (win / "README_KO.txt").write_text("바뀜", encoding="utf-8")
    _ctrl_c_on(monkeypatch, "멈춤 — 묶음 파일")
    with pytest.raises(KeyboardInterrupt):
        run_win(win, ollama, tools)
    monkeypatch.undo()
    first = result(win)
    assert first["status"] == RW.INTERRUPTED and first["stop"] == RW.BUNDLE_CHANGED
    rec = _merge_rec(root, cid, win / "result_1")
    assert rec["stop_kind"] == RW.BUNDLE_CHANGED
    unzip(bd, win)  # 같은 zip 을 다시 풀어 같은 폴더에서
    assert run_win(win, ollama, tools) == 0
    assert _merge_rec(root, cid, win / "result_2")["main_status"] == JU.COMPLETED


def test_ctrl_c_on_already_ran_message_keeps_the_length_rule(
    root, packed, ollama, tools, monkeypatch
):
    cid, _bd, win = packed
    ollama.cfg = {"ctx": 8192}
    assert run_win(win, ollama, tools) == 2
    _ctrl_c_on(monkeypatch, "멈춤 — 이 묶음은 다시")
    with pytest.raises(KeyboardInterrupt):
        run_win(win, ollama, tools)
    monkeypatch.undo()
    assert result(win, 2)["stop"] == RW.ALREADY_RAN
    _merge_rec(root, cid, win / "result_1")
    assert _merge_rec(root, cid, win / "result_2")["stop_kind"] == RW.ALREADY_RAN
    BU.pack(root, cid, lengths={"num_ctx": 65536}, reason="문맥", now=NOW)


@pytest.mark.parametrize("how", ["ctrl_c", "part"])
def test_busy_record_is_never_a_merged_bundle(
    root, packed, ollama, tools, monkeypatch, how
):
    """다른 창 실행 중 멈춤은 안내 중 중단 · 임시 결과(기록 미완)여도 앞 묶음 회수로 치지 않는다."""
    cid, _bd, win = packed
    _hold_lock(monkeypatch, win, "result_1")
    if how == "ctrl_c":
        _ctrl_c_on(monkeypatch, "멈춤 — 다른 창에서")
        with pytest.raises(KeyboardInterrupt):
            run_win(win, ollama, tools)
    else:
        _result_rename_fails(monkeypatch)
        with pytest.raises(PermissionError):
            run_win(win, ollama, tools)
    monkeypatch.undo()
    rec = _merge_rec(root, cid, win / "result_2")
    assert rec["stop_kind"] == RW.ALREADY_RAN
    with pytest.raises(CheckRequired, match="먼저 회수"):
        BU.pack(root, cid, reason="다른 창", now=NOW)


def test_incomplete_already_ran_does_not_hide_the_settings_stop(
    root, packed, ollama, tools, monkeypatch
):
    cid, _bd, win = packed
    ollama.cfg = {"ctx": 8192}
    assert run_win(win, ollama, tools) == 2
    _result_rename_fails(monkeypatch)
    with pytest.raises(PermissionError):
        run_win(win, ollama, tools)
    monkeypatch.undo()
    _merge_rec(root, cid, win / "result_1")
    second = _merge_rec(root, cid, win / "result_2")
    assert second["status"] == ME.INCOMPLETE and second["stop_kind"] == RW.ALREADY_RAN
    BU.pack(root, cid, lengths={"num_ctx": 65536}, reason="문맥", now=NOW)


def test_stop_and_status_must_agree(root, packed, ollama, tools):
    cid, _bd, win = packed
    _full_run(win, ollama, tools)
    rd = rewrite(win, 1, lambda r: r.update(stop="TRIAL_STOPPED"))
    with pytest.raises(CheckRequired, match="멈춤 종류와 결과 상태가 다름"):
        ME.merge(root, cid, rd, now=NOW)


# ── B 정체 없는 기록 — 맥북이 받을 수 있게 · 받을 수 없으면 뒤 기록을 막지 않게 ──


def test_unreadable_bundle_input_still_records_identity(root, packed, ollama, tools):
    cid, bd, win = packed
    (win / "bundle_input.json").unlink()
    assert run_win(win, ollama, tools) == 2
    first = result(win)
    assert first["status"] == RW.BUNDLE_CHANGED and first["case_id"] == cid
    assert _merge_rec(root, cid, win / "result_1")["stop_kind"] == RW.BUNDLE_CHANGED
    unzip(bd, win)
    assert run_win(win, ollama, tools) == 0
    assert _merge_rec(root, cid, win / "result_2")["main_status"] == JU.COMPLETED


def test_ctrl_c_in_bundle_check_is_mergeable(root, packed, ollama, tools, monkeypatch):
    cid, _bd, win = packed

    def check(bdir):
        raise KeyboardInterrupt

    monkeypatch.setattr(RW, "check_bundle", check)
    with pytest.raises(KeyboardInterrupt):
        run_win(win, ollama, tools)
    monkeypatch.undo()
    first = result(win)
    assert first["case_id"] == cid and first.get("files") is None
    assert _merge_rec(root, cid, win / "result_1")["status"] == RW.INTERRUPTED
    assert run_win(win, ollama, tools) == 0
    assert _merge_rec(root, cid, win / "result_2")["main_status"] == JU.COMPLETED


def test_record_without_any_identity_does_not_block_the_later_folder(
    root, packed, ollama, tools, tmp_path
):
    cid, bd, win = packed
    for f in ("manifest.json", "bundle_input.json"):
        (win / f).unlink()
    assert run_win(win, ollama, tools) == 2
    assert result(win).get("case_id") is None
    with pytest.raises(CheckRequired):
        ME.merge(root, cid, win / "result_1", now=NOW)  # 정체가 없으니 받을 수 없다
    unzip(bd, win)
    assert run_win(win, ollama, tools) == 0
    assert _merge_rec(root, cid, win / "result_2")["main_status"] == JU.COMPLETED


# ── C 고정 모델 digest — 합성 점검까지 간 실행의 것만 · 다르면 모델 멈춤 ──


def test_refused_digest_is_not_pinned(packed, ollama, tools):
    _cid, _bd, win = packed
    ollama.cfg = {"count_404": True}  # 환경 멈춤(digest d… 고정)
    assert run_win(win, ollama, tools) == 2
    ollama.cfg = {"other_digest": True}
    assert run_win(win, ollama, tools) == 2
    second = result(win, 2)
    assert second["env_gate"]["categories"] == ["MODEL"]
    calls = _chats(ollama)
    assert run_win(win, ollama, tools) == 2  # 세 번째에도 다른 모델로 돌지 않는다
    assert result(win, 3)["status"] == RW.ALREADY_RAN and _chats(ollama) == calls


def test_malformed_digest_stop_does_not_block_after_the_fix(packed, ollama, tools):
    _cid, _bd, win = packed
    ollama.cfg = {"bad_digest": True}
    assert run_win(win, ollama, tools) == 2 and result(win)["status"] == RW.NEED_ENV
    ollama.cfg = {}
    assert run_win(win, ollama, tools) == 0


def test_report_refuses_an_attempt_on_another_model(
    root, packed, ollama, tools, tmp_path
):
    cid, bd, win = packed
    ollama.cfg = {"ctx": 8192}  # 합성 점검까지 간 앞 실행(digest d…)
    assert run_win(win, ollama, tools) == 2
    _merge_rec(root, cid, win / "result_1")
    ollama.cfg = {"other_digest": True}
    win2 = unzip(bd, tmp_path / "again")  # 다른 곳에 풀어 다른 모델로
    assert run_win(win2, ollama, tools) == 0
    rec = _merge_rec(root, cid, win2 / "result_1")
    score = {"critical_errors": 0, "one_page_sha256": rec["one_page_sha256"]}
    v = RP.build(root, cid, score, {}, answers=True)[1]
    assert v["verdict"] == "판정 불가" and "모델 digest 가 다름" in v["reasons"][0]


# ── D 새 묶음은 설정 · 모델 멈춤 뒤에만(그 밖은 같은 폴더 다시 실행) ──


@pytest.mark.parametrize(
    "cfg",
    [
        {"no_model": True},
        {"no_version": True},
        {"count_404": True},
        {"vram": 0, "_env": 1},
    ],
)
def test_no_new_bundle_after_rerunnable_stops(root, packed, ollama, tools, cfg):
    cid, _bd, win = packed
    ollama.cfg = {k: v for k, v in cfg.items() if not k.startswith("_")}
    assert run_win(win, ollama, tools) == 2
    _merge_rec(root, cid, win / "result_1")
    rec_kinds = BU.stop_categories(BU.merged_runs(root, cid)[0])
    if rec_kinds & {"SETTINGS", "MODEL"}:
        BU.pack(root, cid, reason="설정", now=NOW)  # CPU 단독 = 설정이기도 함
    else:
        with pytest.raises(CheckRequired, match="같은 폴더에서 다시 돌리는 멈춤"):
            BU.pack(root, cid, reason="다시", now=NOW)


def test_no_new_bundle_after_interrupt_before_main(
    root, packed, ollama, tools, monkeypatch
):
    cid, _bd, win = packed
    real, n = RW.io.Ollama.chat, {"k": 0}

    def chat(self, body):
        n["k"] += 1
        if n["k"] == 1:
            raise KeyboardInterrupt
        return real(self, body)

    monkeypatch.setattr(RW.io.Ollama, "chat", chat)
    with pytest.raises(KeyboardInterrupt):
        run_win(win, ollama, tools)
    monkeypatch.undo()
    _merge_rec(root, cid, win / "result_1")
    with pytest.raises(CheckRequired, match="같은 폴더에서 다시 돌리는 멈춤"):
        BU.pack(root, cid, reason="다시", now=NOW)


# ── E 기록 미완 ↔ 완료 경로 같은 대조(같은 함수) ──


def _claim_copy(win, ollama, tools, tmp_path, cfg=None):
    if cfg:
        ollama.cfg = cfg
    run_win(win, ollama, tools)
    ollama.cfg = {}
    part = tmp_path / "copy" / "result_1"
    shutil.copytree(win / "result_1", part)
    (part / "hashes.json").unlink()
    return part


def _edit(part, change):
    r = json.loads((part / "result.json").read_text(encoding="utf-8"))
    change(r)
    (part / "result.json").write_text(
        json.dumps(r, ensure_ascii=False), encoding="utf-8"
    )


@pytest.mark.parametrize(
    "cfg, change, extra, msg",
    [
        (
            {"ctx": 8192},
            lambda r: r.update(status="NEED_X", stop="NEED_X"),
            None,
            "멈춤이 아님",
        ),
        ({"ctx": 8192}, None, "page", "본 요약이 없는데 한 장"),
        (
            {"ctx": 8192},
            lambda r: r.update(status="BUNDLE_CHANGED", stop="BUNDLE_CHANGED"),
            None,
            "묶음이 바뀐 실행인데",
        ),
        ({"ctx": 8192}, None, "marker", "본 요약을 시작했는데 멈춤 상태가 아님"),
        (
            {"ctx": 8192},
            lambda r: (
                r["trial"].pop("judgement"),
                r.update(status="INTERRUPTED", stop=None),
            ),
            None,
            "구분 없는 합성 점검에 통과 판단",
        ),
    ],
)
def test_incomplete_claim_gets_the_same_body_checks(
    root, packed, ollama, tools, tmp_path, cfg, change, extra, msg
):
    cid, _bd, win = packed
    part = _claim_copy(win, ollama, tools, tmp_path, cfg)
    if change is not None:
        _edit(part, change)
    if extra == "page":
        (part / "one_page.html").write_text("<p>섞인 한 장</p>", encoding="utf-8")
    if extra == "marker":
        r = json.loads((part / "result.json").read_text(encoding="utf-8"))
        inp = json.loads((win / "bundle_input.json").read_text(encoding="utf-8"))
        m = {
            "run_id": r["run_id"],
            "bundle_id": r["bundle_id"],
            "case_id": cid,
            "result_dir": "result_1",
            "at": r["started_at"],
            "ollama_version": r["env"]["ollama_version"],
            "model_digest": r["env"]["model"]["digest"],
            "options": inp["options"],
        }
        (part / RW.MAIN_STARTED).write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(CheckRequired, match=msg):
        ME.merge(root, cid, part, now=NOW)


def test_mac_bundle_input_is_checked_on_both_paths(
    root, packed, ollama, tools, tmp_path
):
    cid, bd, win = packed
    part = _claim_copy(win, ollama, tools, tmp_path)
    p = bd / "bundle_input.json"
    p.write_bytes(p.read_bytes() + b" ")
    for rd in (part, win / "result_1"):
        with pytest.raises(
            CheckRequired, match="bundle_input.json 이 manifest 와 다름"
        ):
            ME.merge(root, cid, rd, now=NOW)


def test_named_page_with_render_error_is_refused_on_both_paths(
    root, packed, ollama, tools, tmp_path, monkeypatch
):
    cid, bd, win = packed
    real = RW.write_new

    def no_page(path, data, **k):
        if path.name == "one_page.html":
            raise PermissionError(32, "사용 중")
        return real(path, data, **k)

    monkeypatch.setattr(RW, "write_new", no_page)
    assert run_win(win, ollama, tools) == 0
    monkeypatch.undo()
    win2 = unzip(bd, tmp_path / "again")
    assert run_win(win2, ollama, tools) == 0
    rd = win / "result_1"
    shutil.copyfile(win2 / "result_1" / "one_page.html", rd / "one_page.html")
    part = tmp_path / "copy" / "result_1"
    shutil.copytree(rd, part)
    (part / "hashes.json").unlink()
    for target in (part, rd):
        with pytest.raises(CheckRequired, match="한 장 만들기 오류인데 한 장이 있음"):
            ME.merge(root, cid, target, now=NOW)


def test_trial_judgement_without_gate_is_a_genuine_stop(root, packed, ollama, tools):
    cid, _bd, win = packed
    ollama.cfg = {"ctx": 8192}
    assert run_win(win, ollama, tools) == 2

    def stopped(r):
        r["trial"].pop("gate")
        r.update(status="INTERRUPTED", stop=None, count=None, pre_main=None)

    rec = _merge_rec(root, cid, rewrite(win, 1, stopped))
    assert rec["status"] == RW.INTERRUPTED


def test_incomplete_has_output_matches_the_complete_path(
    root, packed, ollama, tools, tmp_path, monkeypatch
):
    cid, _bd, win = packed
    real = RW.write_x

    def bad_raw(path, data):
        if path.name == RW.MAIN_RAW:
            raise OSError(28, "디스크가 참")
        return real(path, data)

    monkeypatch.setattr(RW, "write_x", bad_raw)
    assert run_win(win, ollama, tools) == 0
    monkeypatch.undo()
    part = tmp_path / "copy" / "result_1"
    shutil.copytree(win / "result_1", part)
    (part / "hashes.json").unlink()
    assert _merge_rec(root, cid, part)["has_output"] is True


def test_code_hashes_are_taken_at_bundle_check(packed, ollama, tools):
    _cid, _bd, win = packed
    _full_run(win, ollama, tools)
    man = json.loads((win / "manifest.json").read_text(encoding="utf-8"))
    assert result(win)["code"] == {c: man["files"][c] for c in RW.CODE_FILES}


# ── F 대신 받기(정체 칸 · 표지 임시 파일 · 실행 id 가 다르면 다른 시도 · 얇은 복사본 · 끊긴 원문) ──


@pytest.mark.parametrize("damaged", [True, False])
def test_marker_part_evidence_is_not_identity(
    root, packed, ollama, tools, tmp_path, monkeypatch, damaged
):
    """표지 임시 파일은 정체가 아니라 증거 — 같은 이름끼리 비교해 바이트가 다를 때만 '달랐던 파일'로 남긴다."""
    cid, _bd, win = packed
    real = RF.os.rename

    def no_marker(a, b):
        if str(b).endswith(RW.MAIN_STARTED):
            raise PermissionError(32, "사용 중")
        return real(a, b)

    monkeypatch.setattr(RF.os, "rename", no_marker)
    monkeypatch.setattr(RF.time, "sleep", lambda s: None)
    assert run_win(win, ollama, tools) == 2
    monkeypatch.undo()
    rd = win / "result_1"
    part = tmp_path / "copy" / "result_1"
    shutil.copytree(rd, part)
    (part / "hashes.json").unlink()
    if damaged:  # 증거 바이트만 다름
        (part / f".{RW.MAIN_STARTED}.part").write_text("{}", encoding="utf-8")
    _merge_rec(root, cid, part)
    rec = _merge_rec(root, cid, rd)
    assert rec["replaces"]
    assert (f".{RW.MAIN_STARTED}.part" in rec["kept_differs"]) is damaged


@pytest.mark.parametrize(
    "field, value", [("at", "2026-01-01T00:00:00+09:00"), ("ollama_version", "0.0.1")]
)
def test_damaged_marker_field_does_not_block_the_original(
    root, packed, ollama, tools, tmp_path, field, value
):
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    part = tmp_path / "copy" / "result_1"
    shutil.copytree(rd, part)
    for f in ("result.json", "hashes.json", "one_page.html", RW.MAIN_RAW):
        (part / f).unlink()
    m = json.loads((part / RW.MAIN_STARTED).read_text(encoding="utf-8"))
    m[field] = value
    (part / RW.MAIN_STARTED).write_text(json.dumps(m), encoding="utf-8")
    _merge_rec(root, cid, part)
    rec = _merge_rec(root, cid, rd)
    assert rec["main_status"] == JU.COMPLETED and RW.MAIN_STARTED in rec["kept_differs"]


def _marker_left(rd):
    """응답 뒤 원문을 쓰기 전 전원이 끊긴 폴더 — 시작 표지만 남는다."""
    for f in ("result.json", "hashes.json", "one_page.html", RW.MAIN_RAW):
        (rd / f).unlink()
    return rd


@pytest.mark.parametrize("first", ["incomplete", "complete"])
@pytest.mark.parametrize("how", ["second_run", "damaged_copy"])
def test_marker_alike_attempts_are_never_merged_into_one(
    root, packed, ollama, tools, tmp_path, monkeypatch, first, how
):
    """검증자 r4 F13: 실행 id 만 다른 두 표지는 같은 초에 시작한 다른 시도(같은 zip 을 두 곳에 풂)와 실행 id 손상
    복사본을 구별할 근거가 없다 — 회수 순서와 상관없이 둘 다 시도로 세고 판정을 막는다(설계자 판단 · §6-3)."""
    cid, bd, win = packed
    monkeypatch.setattr(RW, "now", lambda: "2026-11-23T18:26:02+09:00")  # 같은 초
    if how == "second_run":
        assert run_win(win, ollama, tools) == 0
        cut = _marker_left(win / "result_1")
        win2 = unzip(bd, tmp_path / "second")
        assert run_win(win2, ollama, tools) == 0
        full = win2 / "result_1"
        assert _chats(ollama) == 6  # 본 호출이 실제로 두 번
    else:
        full = _full_run(win, ollama, tools)
        cut = tmp_path / "copy" / "result_1"
        shutil.copytree(full, cut)
        _marker_left(cut)
        m = json.loads((cut / RW.MAIN_STARTED).read_text(encoding="utf-8"))
        m["run_id"] = m["run_id"][:-1] + ("0" if m["run_id"][-1] != "0" else "1")
        (cut / RW.MAIN_STARTED).write_text(json.dumps(m), encoding="utf-8")
    a = json.loads((cut / RW.MAIN_STARTED).read_text(encoding="utf-8"))
    b = json.loads((full / RW.MAIN_STARTED).read_text(encoding="utf-8"))
    assert a["run_id"] != b["run_id"]
    assert {k: v for k, v in a.items() if k != "run_id"} == {
        k: v for k, v in b.items() if k != "run_id"
    }
    for rd in (cut, full) if first == "incomplete" else (full, cut):
        _merge_rec(root, cid, rd)
    runs = BU.merged_runs(root, cid)
    assert sorted(r["run_id"] for r in runs if r["main_started"]) == sorted(
        [a["run_id"], b["run_id"]]
    )
    assert not [r for r in runs if r.get("replaces")]
    sha = next(r for r in runs if r["status"] == JU.COMPLETED)["one_page_sha256"]
    score = {"critical_errors": 0, "one_page_sha256": sha}
    _t, v = RP.build(root, cid, score, _usage(), answers=True)
    assert v["verdict"] == "판정 불가" and "본 요약 시도 2건" in v["reasons"][0]


def test_thinner_incomplete_after_fuller_is_a_duplicate(
    root, packed, ollama, tools, tmp_path
):
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    for f in ("result.json", "hashes.json", "one_page.html"):
        (rd / f).unlink()
    _merge_rec(root, cid, rd)  # 표지 + 원문
    thin = tmp_path / "thin" / "result_1"
    thin.mkdir(parents=True)
    shutil.copyfile(rd / RW.MAIN_STARTED, thin / RW.MAIN_STARTED)
    with pytest.raises(FileExistsError, match="더 담긴 복사본이 아님"):
        ME.merge(root, cid, thin, now=NOW)


# ── G · H 판정 입력 — 일찍 끝나는 판정 불가에도 입력 검사 · 경과는 단조 시계 실행 시간 ──


@pytest.mark.parametrize("state", ["incomplete", "no_page", "two_attempts"])
def test_bad_inputs_are_errors_in_every_report_state(
    root, packed, ollama, tools, tmp_path, monkeypatch, state
):
    cid, bd, win = packed
    rd = _full_run(win, ollama, tools)
    if state == "incomplete":
        (rd / "hashes.json").unlink()
        _merge_rec(root, cid, rd)
    elif state == "no_page":
        rec = _merge_rec(root, cid, rd)
        monkeypatch.setattr(
            RP,
            "merged_runs",
            lambda r, c, every=False: [{**rec, "one_page_sha256": None}],
        )
    else:
        _merge_rec(root, cid, rd)
        win2 = unzip(bd, tmp_path / "again")
        assert run_win(win2, ollama, tools) == 0
        _merge_rec(root, cid, win2 / "result_1")
    for score, usage in (
        ({"critical_errors": 0}, _usage(L={"user_s": -5})),
        ({"critical_errors": "0"}, {}),
    ):
        with pytest.raises(ValueError):
            RP.build(root, cid, score, usage, answers=True)


def test_wall_clock_jump_does_not_refuse_an_honest_elapsed_time(
    root, packed, ollama, tools
):
    cid, _bd, win = packed
    _full_run(win, ollama, tools)
    rd = rewrite(
        win, 1, lambda r: r.update(ended_at="2026-11-25T10:00:00+09:00")
    )  # 시간 맞춤이 앞으로
    rec = _merge_rec(root, cid, rd)
    score = {"critical_errors": 0, "one_page_sha256": rec["one_page_sha256"]}
    usage = _usage(
        L={"user_s": 5, "elapsed_s": 600}, U={"user_s": 500, "elapsed_s": 900}
    )
    assert (
        RP.build(root, cid, score, usage, answers=True)[1]["verdict"]
        == "사용 이점 관찰"
    )


# ── I 못 읽음 ≠ 없음 ──


@pytest.mark.parametrize("how", ["locked", "damaged"])
def test_unreadable_prior_result_blocks_rerun(packed, ollama, tools, monkeypatch, how):
    _cid, _bd, win = packed
    ollama.cfg = {"ctx": 8192}
    assert run_win(win, ollama, tools) == 2
    ollama.cfg = {}
    p = win / "result_1" / "result.json"
    if how == "damaged":
        p.write_bytes(p.read_bytes()[:50])
    else:
        real = type(p).read_text

        def locked(self, *a, **k):
            if self == p:
                raise PermissionError(13, "백신이 잡음")
            return real(self, *a, **k)

        monkeypatch.setattr(type(p), "read_text", locked)
        monkeypatch.setattr(RF.time, "sleep", lambda s: None)
    calls = _chats(ollama)
    assert run_win(win, ollama, tools) == 2
    monkeypatch.undo()
    second = result(win, 2)
    assert (
        second["status"] == RW.ALREADY_RAN
        and "읽지 못했습니다" in second["messages_ko"][0]
    )
    assert _chats(ollama) == calls


def test_new_bundle_allowed_after_a_model_digest_stop(root, packed, ollama, tools):
    """앞 실행과 다른 digest(모델 멈춤)로 끝난 묶음 뒤에는 새 묶음을 만들 수 있다(설계자 보고 · 길이 그대로)."""
    cid, _bd, win = packed
    ollama.cfg = {"count_404": True}
    assert run_win(win, ollama, tools) == 2
    ollama.cfg = {"other_digest": True}
    assert run_win(win, ollama, tools) == 2
    _merge_rec(root, cid, win / "result_1")
    rec = _merge_rec(root, cid, win / "result_2")
    assert rec["env_gate_categories"] == ["MODEL"]
    with pytest.raises(CheckRequired, match="'설정' 문제"):
        BU.pack(root, cid, lengths={"num_ctx": 65536}, reason="r", now=NOW)
    BU.pack(root, cid, reason="모델 다시 받음 — 설계자 판단", now=NOW)


def test_local_elapsed_below_the_real_run_time_is_an_error(root, packed, ollama, tools):
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    rec = _merge_rec(root, cid, rd)
    assert rec["run_wall_s"] > 0.001
    score = {"critical_errors": 0, "one_page_sha256": rec["one_page_sha256"]}
    with pytest.raises(ValueError, match="실행기 기록"):
        RP.build(
            root,
            cid,
            score,
            _usage(L={"user_s": 0.0005, "elapsed_s": 0.001}),
            answers=True,
        )


# ── 순서 = 폴더 번호(글자 순이면 result_10 이 result_2 앞 · 검증자 r3 F12) ──


def test_prior_results_follow_folder_numbers(tmp_path):
    for n in (10, 2, 1):
        d = tmp_path / f"result_{n}"
        d.mkdir()
        rec = {"bundle_id": "b", "run_id": f"r{n}", "status": "NEED_OLLAMA"}
        (d / "result.json").write_text(json.dumps(rec), encoding="utf-8")
    rows = RF.prior_results(tmp_path, tmp_path / "result_11", "b")
    assert [r["dir"] for r in rows] == ["result_1", "result_2", "result_10"]


def test_merged_runs_follow_bundle_then_folder_numbers(tmp_path, monkeypatch):
    recs = {
        "x1": {"bundle_id": "b2", "result_dir": "result_1", "run_id": "z"},
        "x2": {"bundle_id": "b1", "result_dir": "result_10", "run_id": "a"},
        "x3": {"bundle_id": "b1", "result_dir": "result_2", "run_id": "b"},
        "x4": {"bundle_id": "b1", "result_dir": "result_2", "run_id": "a"},
    }
    monkeypatch.setattr(BU, "real_root", lambda r: r)
    monkeypatch.setattr(BU, "case_dir", lambda b, c: b)
    monkeypatch.setattr(BU, "_listed", lambda b, p: sorted(recs))
    monkeypatch.setattr(BU, "read_json_inside", lambda b, p: dict(recs[p.parent.name]))
    monkeypatch.setattr(BU, "bundles_of", lambda b, c: ["b1", "b2"])
    got = [
        (r["bundle_id"], r["result_dir"], r["run_id"])
        for r in BU.merged_runs(tmp_path, "c")
    ]
    assert got == [
        ("b1", "result_2", "a"),
        ("b1", "result_2", "b"),
        ("b1", "result_10", "a"),
        ("b2", "result_1", "z"),
    ]


# ── 변이로 찾은 단독 칸(r3 변이 v8 · 다른 대조가 대신 막지 않는 칸) ──


def _marker_only(rd, where):
    d = where / "result_1"
    d.mkdir(parents=True)
    shutil.copyfile(rd / RW.MAIN_STARTED, d / RW.MAIN_STARTED)
    return d


def test_fuller_incomplete_with_a_different_marker_is_escalated(
    root, packed, ollama, tools, tmp_path
):
    """기록 미완 → 기록 미완은 앞서 받은 표지와 같은 바이트여야 대신 받는다(검증 못 한 두 복사본 · 설계자 판단)."""
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    _merge_rec(root, cid, _marker_only(rd, tmp_path / "a"))
    fuller = tmp_path / "b" / "result_1"
    fuller.mkdir(parents=True)
    m = json.loads((rd / RW.MAIN_STARTED).read_text(encoding="utf-8"))
    at = datetime.fromisoformat(m["at"]) + timedelta(seconds=1)  # 한 칸만 다른 손상
    m["at"] = at.isoformat(timespec="seconds")
    (fuller / RW.MAIN_STARTED).write_text(
        json.dumps(m, ensure_ascii=False), encoding="utf-8"
    )
    shutil.copyfile(rd / RW.MAIN_RAW, fuller / RW.MAIN_RAW)
    with pytest.raises(CheckRequired, match="main_started.json 이 이 폴더와 다름"):
        ME.merge(root, cid, fuller, now=NOW)


def test_fuller_incomplete_with_a_different_raw_is_escalated(
    root, packed, ollama, tools, tmp_path
):
    """앞서 받은 원문(다 쓴 것)과 다른 원문을 담은 더 담긴 복사본은 대신 받지 않는다(잘린 앞부분만 이어 받음)."""
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    first = _marker_only(rd, tmp_path / "a")
    shutil.copyfile(rd / RW.MAIN_RAW, first / RW.MAIN_RAW)
    _merge_rec(root, cid, first)
    fuller = _marker_only(rd, tmp_path / "b")
    raw = json.loads((rd / RW.MAIN_RAW).read_text(encoding="utf-8"))
    raw["response"]["eval_count"] = raw["response"]["eval_count"] + 1
    (fuller / RW.MAIN_RAW).write_text(
        json.dumps(raw, ensure_ascii=False), encoding="utf-8"
    )
    (fuller / ".result.json.part").write_bytes(
        b'{"run'
    )  # 쓰다 꺼진 임시 결과(더 담긴 것처럼)
    with pytest.raises(CheckRequired, match="main_raw.json 이 이 폴더와 다름"):
        ME.merge(root, cid, fuller, now=NOW)


@pytest.mark.parametrize("path", ["complete", "incomplete"])
def test_record_without_bundle_check_must_not_have_called_the_model(
    root, packed, ollama, tools, tmp_path, path
):
    """묶음 확인 기록(files)이 없으면 그 전에 멈춘 기록만 — 모델을 부른 기록이면 코드 해시 대조를 건너뛰게 된다."""
    cid, _bd, win = packed
    _full_run(win, ollama, tools)
    rd = rewrite(win, 1, lambda r: r.update(files=None))
    if path == "incomplete":
        rd = tmp_path / "copy" / "result_1"
        shutil.copytree(win / "result_1", rd)
        (rd / "hashes.json").unlink()
    with pytest.raises(
        CheckRequired, match="묶음 확인 기록이 없는데 멈춤 전 기록이 아님"
    ):
        ME.merge(root, cid, rd, now=NOW)


def test_trial_without_gate_is_only_for_a_run_stopped_in_between(
    root, packed, ollama, tools
):
    """합성 점검 구분만 있고 통과 판단이 없으면 그 사이 멈춘 실행만 — 끝까지 돈 실행이면 거부."""
    cid, _bd, win = packed
    _full_run(win, ollama, tools)
    rd = rewrite(win, 1, lambda r: r["trial"].pop("gate"))
    with pytest.raises(
        CheckRequired, match="통과 판단 없는 합성 점검은 그 사이 멈춘 실행만"
    ):
        ME.merge(root, cid, rd, now=NOW)


@pytest.mark.parametrize(
    "change, kind",
    [
        (lambda r: r.update(main=[]), "AttributeError"),
        (lambda r: r.update(prior_results=[1]), "AttributeError"),
        (lambda r: r.update(run_id=1), "TypeError"),
    ],
)
def test_cli_merge_shape_errors_end_with_a_result_line(
    root, packed, ollama, tools, capsys, change, kind
):
    """USB 결과 기록의 모양 오류(해시까지 맞춘 손 고침)도 CLI 는 RESULT 줄 · rc 2 로 끝낸다(판정 입력 꼴은 ValueError)."""
    from scripts import run_review_summary as CLI

    cid, _bd, win = packed
    _full_run(win, ollama, tools)
    rd = rewrite(win, 1, change)
    args = ["--root", str(root), "merge", "--case", cid, "--result", str(rd)]
    assert CLI.main(args) == 2
    last = capsys.readouterr().out.strip().splitlines()[-1]
    assert last.startswith("RESULT ") and "CHECK_REQUIRED" in last and kind in last


@pytest.mark.parametrize(
    "status, kind, refused",
    [
        ("INTERRUPTED", "ALREADY_RAN", True),  # 다른 창 실행 중 멈춤을 안내하다 중단
        ("INCOMPLETE_RECORD", "ALREADY_RAN", True),  # 임시 결과로만 남은 다시 실행 멈춤
        ("INTERRUPTED", "TRIAL_STOPPED", False),  # 대조 칸: 실제로 돈 멈춤은 회수
    ],
)
def test_merge_order_reads_the_stop_kind_of_earlier_bundles(
    tmp_path, monkeypatch, status, kind, refused
):
    monkeypatch.setattr(ME, "bundles_of", lambda b, c: ["b1", "b2"])
    runs = [{"bundle_id": "b1", "status": status, "stop_kind": kind, "run_id": "r1"}]
    v = {"result": {"run_id": "r2"}, "prior_results": []}
    if refused:
        with pytest.raises(CheckRequired, match="앞 묶음 결과를 먼저 회수해야 함: b1"):
            ME._order(tmp_path, "c", "b2", v, runs)
    else:
        assert ME._order(tmp_path, "c", "b2", v, runs) is None


def _as_trial_stop_interrupted(r):
    r.update(status="INTERRUPTED", stop="TRIAL_STOPPED")


def test_trial_stop_kind_is_checked_even_when_interrupted(root, packed, ollama, tools):
    """안내 중 중단된 기록도 '합성 점검 멈춤' 종류로 대조한다 — 합성 점검을 통과한 기록에 그 종류를 붙이면 거부."""
    cid, _bd, win = packed
    ollama.cfg = {"version_change": True}  # 합성 점검 통과 · 본 호출 직전 관문에서 멈춤
    assert run_win(win, ollama, tools) == 2
    assert result(win, 1)["trial"]["gate"]["ok"]
    rd = rewrite(win, 1, _as_trial_stop_interrupted)
    with pytest.raises(CheckRequired, match="합성 점검을 통과했는데 멈춤으로 적힘"):
        ME.merge(root, cid, rd, now=NOW)


def test_trial_stop_kind_without_a_trial_is_refused_even_when_interrupted(
    root, packed, ollama, tools
):
    cid, _bd, win = packed
    ollama.cfg = {"no_model": True}  # 합성 점검 전 멈춤
    assert run_win(win, ollama, tools) == 2
    assert result(win, 1).get("trial") is None
    rd = rewrite(win, 1, _as_trial_stop_interrupted)
    with pytest.raises(
        CheckRequired, match="합성 점검 기록 없이 합성 점검 멈춤으로 적힘"
    ):
        ME.merge(root, cid, rd, now=NOW)


# ── 검증자 r4 정정 뒤 잠금 전 검토 — 끊긴 원문 양방향 · 겹쳐 복사한 결과 폴더 ──


@pytest.mark.parametrize("first", ["short", "long"])
def test_torn_raw_copies_keep_the_longer_whichever_order(
    root, packed, ollama, tools, tmp_path, first
):
    """같은 실행의 끊긴 원문 복사본 둘 — 어느 순서로 받아도 긴 원문이 남고 짧은 쪽은 중복(설계자 판단으로 올리지 않음)."""
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    raw = (rd / RW.MAIN_RAW).read_bytes()
    cuts = {}
    for name, n in (("short", 40), ("long", 80)):
        d = _marker_only(rd, tmp_path / name)
        (d / RW.MAIN_RAW).write_bytes(raw[:n])
        cuts[name] = d
    second = "long" if first == "short" else "short"
    _merge_rec(root, cid, cuts[first])
    if first == "short":
        rec = _merge_rec(root, cid, cuts[second])  # 더 길게 이어진 복사본 = 대신 받음
        assert rec["replaces"]
    else:
        with pytest.raises(FileExistsError, match="더 담긴 복사본이 아님"):
            ME.merge(root, cid, cuts[second], now=NOW)
    (kept,) = [r for r in BU.merged_runs(root, cid)]
    stored = root / "cases" / cid / "runs" / kept["record_dir"] / RW.MAIN_RAW
    assert stored.read_bytes() == raw[:80]


@pytest.mark.parametrize("first", ["torn", "whole"])
def test_torn_copy_and_the_whole_raw_agree_whichever_order(
    root, packed, ollama, tools, tmp_path, first
):
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    raw = (rd / RW.MAIN_RAW).read_bytes()
    torn = _marker_only(rd, tmp_path / "torn")
    (torn / RW.MAIN_RAW).write_bytes(raw[:40])
    whole = _marker_only(rd, tmp_path / "whole")
    (whole / RW.MAIN_RAW).write_bytes(raw)
    order = (torn, whole) if first == "torn" else (whole, torn)
    _merge_rec(root, cid, order[0])
    if first == "torn":
        assert _merge_rec(root, cid, order[1])["replaces"]
    else:
        with pytest.raises(FileExistsError, match="더 담긴 복사본이 아님"):
            ME.merge(root, cid, order[1], now=NOW)
    assert len(BU.merged_runs(root, cid)) == 1


@pytest.mark.parametrize(
    "trace",
    [
        "result (2).json",
        "main_started (2).json",
        "one_page (2).html",
        "result - 복사본.json",
        "hashes 2.json",
        ".result.json (2).part",
    ],
)
@pytest.mark.parametrize("path", ["complete", "incomplete"])
def test_copy_name_traces_in_a_result_folder_are_refused(
    root, packed, ollama, tools, tmp_path, trace, path
):
    """결과 폴더 둘을 같은 이름으로 겹쳐 복사하면(Windows '둘 다 유지' 등) 사본 이름이 남는다 — 시도를 하나로 세지 않게 거부."""
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    if path == "incomplete":
        (rd / "hashes.json").unlink()
    (rd / trace).write_bytes(b"{}")
    with pytest.raises(CheckRequired, match="결과 파일의 사본 이름이 있음"):
        ME.merge(root, cid, rd, now=NOW)


def test_os_metadata_files_are_not_copy_traces(root, packed, ollama, tools):
    cid, _bd, win = packed
    rd = _full_run(win, ollama, tools)
    for n in (
        ".DS_Store",
        "._result.json",
        "._main_raw.json",
        "Thumbs.db",
        "desktop.ini",
    ):
        (rd / n).write_bytes(b"x")
    assert _merge_rec(root, cid, rd)["main_status"] == JU.COMPLETED


def test_two_unzips_kept_both_in_one_usb_folder_are_refused(
    root, packed, ollama, tools, tmp_path, monkeypatch
):
    """검토 재현: 같은 zip 을 두 곳에 풀어 둘 다 돌린 뒤 USB 의 같은 result_1 에 '둘 다 유지'로 겹쳐 복사."""
    cid, bd, win = packed
    monkeypatch.setattr(RW, "now", lambda: "2026-11-23T18:26:02+09:00")
    assert run_win(win, ollama, tools) == 0
    win2 = unzip(bd, tmp_path / "second")
    assert run_win(win2, ollama, tools) == 0
    usb = tmp_path / "usb" / "result_1"
    shutil.copytree(win / "result_1", usb)
    for f in (win2 / "result_1").iterdir():
        stem, dot, ext = f.name.rpartition(".")
        (usb / f"{stem} (2).{ext}").write_bytes(f.read_bytes())
    with pytest.raises(CheckRequired, match="결과 파일의 사본 이름이 있음"):
        ME.merge(root, cid, usb, now=NOW)


def test_readme_tells_to_copy_each_unzip_folder_separately(packed):
    _cid, _bd, win = packed
    text = (win / "README_KO.txt").read_text(encoding="utf-8")
    assert "푼 폴더마다 따로 복사" in text and "취소한 뒤 알려 주세요" in text


def test_reply_from_another_model_is_refused(root, packed, ollama, tools):
    """응답의 모델 이름이 묶음의 지정 모델과 다르면 거부(원문 · 결과가 서로 맞아도 · 판정 Q3 모델 고정)."""
    cid, _bd, win = packed
    _full_run(win, ollama, tools)
    rd = win / "result_1"
    R._raw(rd, lambda r: r["response"].update(model="other:7b"))
    rewrite(win, 1, lambda r: r["main"].update(model_reported="other:7b"))
    with pytest.raises(
        CheckRequired, match="응답한 모델이 지정 모델과 다름: 'other:7b'"
    ):
        ME.merge(root, cid, rd, now=NOW)
