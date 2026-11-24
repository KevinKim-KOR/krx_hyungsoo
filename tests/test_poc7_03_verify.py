"""POC7-03 독립 검산 · 검산 기록 · 화면 표시 확인(검증자 r1 F1 · F2 · r2 F5 · F6 · 반박 검토) — tmp 가짜 자료만.

`test_poc7_03_candidate_compare.py` 에서 나눔(KS-10 시험 1,450줄 사전 경고 · 시험 내용 그대로).
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import numpy as np
import pytest

from app.candidate_compare import flow as FW
from app.candidate_compare import recompute as RC
from app.candidate_compare import recompute_weeks as RW
from app.candidate_compare import study as ST
from app.candidate_compare import verify as VF
from app.candidate_compare import verify_records as VR
from app.candidate_compare.protocol import CheckRequired
from app.entry_timing.protocol import dumps
from tests.test_poc7_03_candidate_compare import NOW, _cfg, _sealed

# ── 검증자 r1 F1 · F2 — 검산이 잠금 · 주 기록 · 주 평가 · 보고 · 표시를 모두 묶는가 ─────────


@pytest.fixture
def official(tmp_path: Path):
    """가짜 봉인 DB 로 잠금 → 공식 실행 → 재계산(한 번만) — 시험마다 파일을 고쳐 대조한다."""
    db, content = _sealed(tmp_path)
    cfg = _cfg(tmp_path, db, content)
    FW.prepare(cfg, NOW)
    res = FW.run(cfg, NOW)
    root = FW.real_root(cfg.root)
    lock_dir = FW.locks(root)[-1][0]
    run_dir = Path(res["dir"])
    return cfg, root, lock_dir, run_dir, RC.rebuild(cfg)


def _rewrite(path: Path, obj) -> None:
    path.chmod(0o644)
    path.write_bytes(obj if isinstance(obj, bytes) else dumps(obj))


def _tamper(run_dir: Path, lock_dir: Path, name: str, fn) -> None:
    """파일 하나를 고치고 run.json 해시 · 잠금 주 기록 해시를 맞춘다(해시 대조가 아니라 내용 대조를 시험)."""
    from app.ml_evidence import store

    f = (lock_dir if name == "lock.json" else run_dir) / name
    obj = (
        json.loads(f.read_text(encoding="utf-8"))
        if name.endswith(".json")
        else f.read_bytes()
    )
    obj = fn(obj)
    _rewrite(f, obj)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    for n in run["files"]:
        run["files"][n] = store.sha256_bytes((run_dir / n).read_bytes())
    _rewrite(run_dir / "run.json", run)
    if name == "weeks.json":
        lock = json.loads((lock_dir / "lock.json").read_text(encoding="utf-8"))
        lock["weeks_sha256"] = store.sha256_bytes(dumps(obj["weeks"]))
        _rewrite(lock_dir / "lock.json", lock)


def _first_ok(obj):
    return next(w for w in obj["weeks"] if w["status"] == "OK")


def _set_cost(o):
    o["recipe"]["costs"]["base"] = 0.003
    return o


def _empty_picks(o):
    _first_ok(o)["picks"] = {}
    return o


def _exit_is_entry(o):
    w = _first_ok(o)
    w["exit"] = w["entry"]
    return o


def _label(o):
    o["verdict"]["label"] = "연구 후보"
    return o


def _entry_px(o):
    r = next(r for r in o["rows"] if r["base"]["status"] == "OK")
    r["base"]["slots_a"][0]["entry_px"] *= 1.001
    return o


def _reasons(o):
    o["main"]["dropped_reasons"] = {"NO_ROW_E2": 1}
    return o


def _md(b):
    return b.replace("판정:".encode(), "판정 :".encode())


def _started_id(o):
    o["run_id"] = "20990101T000000Z_00000000"
    return o


@pytest.mark.parametrize(
    "name, fn, want",
    [
        ("lock.json", _set_cost, "잠금 설정"),
        ("weeks.json", _empty_picks, "picks"),
        ("weeks.json", _exit_is_entry, "exit"),
        ("report.json", _label, "verdict.label"),
        ("weeks.json", _entry_px, "entry_px"),
        ("report.json", _reasons, "dropped_reasons"),
        ("report.md", _md, "report.md"),
        ("started.json", _started_id, "started.json"),
    ],
)
def test_check_binds_every_part(official, name, fn, want) -> None:
    cfg, root, lock_dir, run_dir, mine = official
    assert VF.check(cfg, root, lock_dir, run_dir, mine)[0] == []
    _tamper(run_dir, lock_dir, name, fn)
    checks = VF.check(cfg, root, lock_dir, run_dir, mine)[0]
    assert any(want in c for c in checks), checks


def test_rebuild_matches_run_records_exactly(official) -> None:
    cfg, root, lock_dir, run_dir, mine = official
    rec = json.loads((run_dir / "weeks.json").read_text(encoding="utf-8"))
    assert VF.diff(rec["weeks"], json.loads(dumps(mine["weeks"])), "weeks") == []
    assert VF.diff(rec["rows"], json.loads(dumps(mine["rows"])), "rows") == []
    bad = json.loads(json.dumps(rec["weeks"]))
    _first_ok({"weeks": bad})["b"] = list(reversed(_first_ok({"weeks": bad})["b"]))
    assert VF.diff(bad, json.loads(dumps(mine["weeks"])), "weeks")
    assert VF.diff({"x": 1}, {"x": True}) and VF.diff({"x": 1.0}, {"x": 1.0 + 1e-9})


def test_verified_report_follows_current_files(official) -> None:
    cfg, root, lock_dir, run_dir, _mine = official
    v = VF.verify(cfg, NOW)
    assert v["status"] == "VERIFIED_OK" and set(v["files"]) == set(VF.FILES)
    assert v["verify_code_sha256"] == VR.verify_code()[0] and v["seq"] == 1
    assert VR.verified_report(root, lock_dir, run_dir)["run_id"] == run_dir.name
    _tamper(
        run_dir, lock_dir, "report.json", _label
    )  # 검산 뒤 보고가 바뀜(해시는 run.json 과 맞춤)
    assert (
        VR.verified_report(root, lock_dir, run_dir) is None
    )  # 화면에 '검산 일치'로 보이지 않음


def _snapshot(run_dir: Path, lock_dir: Path) -> dict[Path, bytes]:
    return {
        p: p.read_bytes() for p in [lock_dir / "lock.json", *sorted(run_dir.iterdir())]
    }


def _restore(snap: dict[Path, bytes]) -> None:
    for p, b in snap.items():
        _rewrite(p, b)


def test_newer_mismatch_hides_older_ok(official) -> None:
    """반박 M2 — 이 실행의 가장 최근 검산이 MISMATCH 면 파일을 되돌려도 옛 VERIFIED_OK 로 보이지 않음."""
    cfg, root, lock_dir, run_dir, _mine = official
    assert VF.verify(cfg, NOW)["status"] == "VERIFIED_OK"
    snap = _snapshot(run_dir, lock_dir)
    _tamper(run_dir, lock_dir, "report.json", _label)
    later = NOW + timedelta(minutes=1)
    assert VF.verify(cfg, later)["status"] == "MISMATCH"
    _restore(snap)  # 지금 파일 = 옛 성공 검산 해시와 같음
    assert VR.verified_report(root, lock_dir, run_dir) is None
    assert VF.verify(cfg, later + timedelta(minutes=1))["status"] == "VERIFIED_OK"
    assert VR.verified_report(root, lock_dir, run_dir) is not None  # 다시 검산하면 보임


@pytest.mark.parametrize(
    "edit",
    [
        lambda v: {**v, "n_checks": 1},
        lambda v: {**v, "checks": ["x"]},
        lambda v: {**v, "verify_code_sha256": "0" * 64},
        lambda v: {**v, "schema": "other"},
        lambda v: {**v, "n_checks": False},
        lambda v: {**v, "seq": "2"},  # 차례 번호 형식 틀림
    ],
)
def test_verified_report_needs_clean_record_and_current_verify_code(
    official, edit
) -> None:
    cfg, root, lock_dir, run_dir, _mine = official
    v = VF.verify(cfg, NOW)
    assert VR.verified_report(root, lock_dir, run_dir) is not None
    later = VF.new_id(NOW + timedelta(minutes=1))
    (root / "verify" / f"{later}.json").write_bytes(
        dumps(edit({**v, "verify_id": later, "seq": v["seq"] + 1}))
    )
    assert VR.verified_report(root, lock_dir, run_dir) is None


def test_verified_report_hidden_when_verify_code_changes(official, monkeypatch) -> None:
    cfg, root, lock_dir, run_dir, _mine = official
    VF.verify(cfg, NOW)
    monkeypatch.setattr(
        VR, "verify_code", lambda: ("1" * 64, [])
    )  # 검산 규칙이 바뀐 뒤
    assert VR.verified_report(root, lock_dir, run_dir) is None


def test_report_md_uses_run_order_of_dropped_reasons(official) -> None:
    """반박 M1 — run 은 만난 순서(사유 2개 이상 · 이름순 아님)로 글을 만들고 report.json 은 이름순으로 저장된다.

    검산이 report.json 순서로 글을 다시 만들면 정상 실행을 어긋남으로 본다 — 재계산 순서로 만들어야 함.
    """
    from app.candidate_compare import report as RP

    cfg, root, lock_dir, run_dir, mine = official
    order = {"NO_ROW_E2": 1, "NOT_EXEC_E2": 2}  # 만난 순서 = 이름순 아님
    mine = {**mine, "main": {**mine["main"], "dropped_reasons": dict(order)}}
    rep = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    rep["main"]["dropped_reasons"] = dict(order)
    md = RP.render(rep).encode("utf-8")  # run 이 메모리에서 만든 글
    _tamper(run_dir, lock_dir, "report.json", lambda o: json.loads(dumps(rep)))
    _tamper(run_dir, lock_dir, "report.md", lambda b: md)
    stored = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    assert list(stored["main"]["dropped_reasons"]) == sorted(order)  # 저장은 이름순
    assert VF.check(cfg, root, lock_dir, run_dir, mine)[0] == []
    _tamper(run_dir, lock_dir, "report.md", lambda b: RP.render(stored).encode("utf-8"))
    assert any(
        "report.md" in c for c in VF.check(cfg, root, lock_dir, run_dir, mine)[0]
    )


def _drop_code_hash(o):
    o["code_hashes"].pop(next(iter(o["code_hashes"])))
    return o


def _started_at(o):
    o["at"] = "2099-01-01T00:00:00+00:00"
    return o


def _run_extra(o):
    o["error"] = None
    return o


def _prev_lock(o):
    o["previous_lock"] = "20200101T000000Z_00000000"
    return o


def _reason_only(o):
    o["correction_reason"] = "사유만"
    return o


def _int_to_float(o):
    _first_ok(o)["n_pop"] = float(_first_ok(o)["n_pop"])
    return o


def _created_at(o):
    o["created_at"] = "1999-01-01T00:00:00+00:00"
    return o


def _lock_extra(o):
    o["note"] = "x"
    return o


@pytest.mark.parametrize(
    "name, fn, want",
    [
        ("lock.json", _drop_code_hash, "코드 해시 대상"),
        ("started.json", _started_at, "시작 표지와 실행 기록의 시각"),
        ("run.json", _run_extra, "run.json 칸 목록"),
        ("lock.json", _prev_lock, "앞 잠금"),
        ("lock.json", _reason_only, "정정 사유"),
        ("lock.json", _lock_extra, "lock.json 칸 목록"),
        ("weeks.json", _int_to_float, "형 다름"),
        ("lock.json", _created_at, "잠금 만든 시각"),
    ],
)
def test_check_binds_record_shape(official, name, fn, want) -> None:
    """반박 m1 · NIT — 칸 목록 · 시각 · 앞 잠금 · 코드 해시 대상 · 숫자 형."""
    cfg, root, lock_dir, run_dir, mine = official
    _tamper(run_dir, lock_dir, name, fn)
    checks = VF.check(cfg, root, lock_dir, run_dir, mine)[0]
    assert any(want in c for c in checks), checks


def test_check_flags_extra_files_but_allows_leftover_tmp(official) -> None:
    cfg, root, lock_dir, run_dir, mine = official
    (run_dir / f".report.md.{'a' * 32}.tmp").write_bytes(b"")  # 정리 못 한 임시 이름
    assert VF.check(cfg, root, lock_dir, run_dir, mine)[0] == []
    (run_dir / "extra.json").write_bytes(b"{}")
    (lock_dir / "notes.txt").write_bytes(b"")
    checks = VF.check(cfg, root, lock_dir, run_dir, mine)[0]
    assert any("실행 폴더에 다른 파일: extra.json" in c for c in checks)
    assert any("잠금 폴더에 다른 것: notes.txt" in c for c in checks)


def _put_bytes(path: Path, body: bytes) -> None:
    path.chmod(0o644)
    path.write_bytes(body)


def _as_dir(path: Path) -> None:
    path.chmod(0o644)
    path.unlink()
    path.mkdir()


CORRUPT = [  # 검증자 r2 F5 세 경우 + 같은 종류(못 읽음 · JSON 아님 · 객체 아님 · 칸 형 틀림)
    ("lock.json", lambda f: _put_bytes(f, b"{"), "lock.json JSON 아님"),
    ("run.json", lambda f: _put_bytes(f, b"null"), "run.json 객체 아님"),
    ("report.json", lambda f: _put_bytes(f, b"[]"), "report.json 객체 아님"),
    ("started.json", lambda f: _put_bytes(f, b"[1]"), "started.json 객체 아님"),
    ("weeks.json", lambda f: _put_bytes(f, b'{"weeks": "x", "rows": 5}'), "weeks"),
    ("report.json", lambda f: _put_bytes(f, b'{"main": [], "alt": 3}'), "report"),
    ("lock.json", lambda f: _put_bytes(f, b"\xff\xfe"), "lock.json JSON 아님"),
    ("weeks.json", _as_dir, "weeks.json 읽기 실패"),
]


def _mutate_json(f: Path, fn) -> None:
    obj = json.loads(f.read_text(encoding="utf-8"))
    _put_bytes(f, dumps(fn(obj)))


CORRUPT += [
    (
        "lock.json",
        lambda f: _mutate_json(
            f,
            lambda o: {**o, "code_hashes": {k: "x" for k in o["code_hashes"]}},
        ),
        "코드 해시 대상 · 꼴",
    ),
    ("lock.json", lambda f: _mutate_json(f, lambda o: {**o, "env": []}), "환경 칸 꼴"),
    (
        "lock.json",
        lambda f: _mutate_json(f, lambda o: {**o, "env": {"python": "3.12"}}),
        "환경 칸 꼴",
    ),
    (
        "lock.json",
        lambda f: _mutate_json(f, lambda o: {**o, "env": {k: 3 for k in o["env"]}}),
        "환경 칸 꼴",
    ),
    (
        "lock.json",
        lambda f: _mutate_json(f, lambda o: {**o, "correction_reason": 0}),
        "정정 사유",
    ),
    (
        "lock.json",
        lambda f: _mutate_json(f, lambda o: {**o, "code_hashes": ["x"]}),
        "코드 해시 대상",
    ),
    (
        "run.json",
        lambda f: _mutate_json(f, lambda o: {**o, "files": ["weeks.json"]}),
        "run.json 파일 목록",
    ),
    (
        "report.json",
        lambda f: _mutate_json(f, lambda o: {**o, "main": {"dropped_reasons": 5}}),
        "report.main",
    ),
]


@pytest.mark.parametrize("name, spoil, want", CORRUPT)
def test_verify_records_mismatch_for_corrupt_records(
    official, name, spoil, want
) -> None:
    """r2 F5 — 깨진 기록도 예외로 끝내지 않고 어긋남 기록을 남긴다 · 화면 판정은 숨는다."""
    cfg, root, lock_dir, run_dir, _mine = official
    assert VF.verify(cfg, NOW)["status"] == "VERIFIED_OK"
    spoil((lock_dir if name == "lock.json" else run_dir) / name)
    v = VF.verify(cfg, NOW + timedelta(minutes=1))
    assert v["status"] == "MISMATCH" and v["seq"] == 2
    assert any(want in c for c in v["checks"]), v["checks"]
    assert (root / "verify" / f"{v['verify_id']}.json").exists()
    assert VR.display_report(root) is None


def test_random_corruption_never_raises(official) -> None:
    """무작위 손상(잘림 · 다른 형 · 칸 지움 · 칸 형 바꿈 · 보고 글 글자 바꿈) — 대조는 늘 어긋남을 내고 예외가 없다."""
    cfg, root, lock_dir, run_dir, mine = official
    snap = _snapshot(run_dir, lock_dir)
    rng = np.random.default_rng(20261124)
    odd = [None, 0, 1.5, "x", [], [1, 2], {}, True]
    n = 0
    for name in VF.FILES:
        f = (lock_dir if name == "lock.json" else run_dir) / name
        body = f.read_bytes()
        for kind in range(5):
            _restore(snap)
            if name == "report.md":
                b = bytearray(body)
                k = int(rng.integers(0, len(b)))
                b[k] = (b[k] + 1 + int(rng.integers(0, 200))) % 256
                spoiled = bytes(b) if kind else body[: int(rng.integers(0, len(body)))]
            else:
                obj = json.loads(body)
                key = sorted(obj)[int(rng.integers(0, len(obj)))]
                if kind == 0:
                    spoiled = body[: int(rng.integers(1, len(body) - 1))]
                elif kind == 1:
                    spoiled = dumps(odd[int(rng.integers(0, len(odd)))])
                elif kind == 2:
                    spoiled = dumps({k: v for k, v in obj.items() if k != key})
                else:
                    val = odd[int(rng.integers(0, len(odd)))]
                    if val == obj[key] and type(val) is type(obj[key]):
                        val = "바뀐 값"
                    spoiled = dumps({**obj, key: val})
            _put_bytes(f, spoiled)
            checks = VF.check(cfg, root, lock_dir, run_dir, mine)[0]
            assert checks, (name, kind)
            n += 1
    assert n == 30


def test_display_survives_corrupt_verify_records(official) -> None:
    cfg, root, lock_dir, run_dir, _mine = official
    VF.verify(cfg, NOW)
    assert VR.display_report(root) is not None
    bad = root / "verify" / f"{VF.new_id(NOW + timedelta(minutes=1))}.json"
    bad.write_bytes(b"[1, 2]")
    assert VR.display_report(root) is None  # 검산 기록 하나라도 못 읽으면 숨김
    # 차례를 이을 수 없으면 새 검산도 멈춤(반박 2)
    with pytest.raises(CheckRequired):
        VF.verify(cfg, NOW + timedelta(minutes=2))
    bad.write_bytes(b"{")
    assert VR.display_report(root) is None
    bad.unlink()
    assert VF.verify(cfg, NOW + timedelta(minutes=3))["seq"] == 2  # 치우면 이어서 감
    assert VR.display_report(root) is not None


def test_cli_verdict_line_hidden_on_corrupt_lock(official, monkeypatch) -> None:
    import importlib.util

    cfg, root, lock_dir, _run_dir, _mine = official
    VF.verify(cfg, NOW)
    spec = importlib.util.spec_from_file_location(
        "run_candidate_compare_t2",
        Path(__file__).resolve().parents[1] / "scripts" / "run_candidate_compare.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod._verdict_text(cfg) is not None
    _put_bytes(lock_dir / "lock.json", b"{")
    assert mod._verdict_text(cfg) is None  # 예외 없이 판정만 숨김


def test_newest_record_by_sequence_not_clock(official) -> None:
    """r2 F6 ① — 시계를 뒤로 돌린 뒤의 어긋남 검산이 '가장 최근'이다(시각 ID 가 더 작아도)."""
    cfg, root, lock_dir, run_dir, _mine = official
    assert VF.verify(cfg, NOW)["status"] == "VERIFIED_OK"
    snap = _snapshot(run_dir, lock_dir)
    _tamper(run_dir, lock_dir, "report.json", _label)
    back = NOW - timedelta(minutes=1)
    v = VF.verify(cfg, back)
    assert (
        v["status"] == "MISMATCH"
        and v["seq"] == 2
        and v["verify_id"] < "20261124T030000Z"
    )
    _restore(snap)
    assert VR.verified_report(root, lock_dir, run_dir) is None
    ok = VF.verify(cfg, NOW - timedelta(minutes=2))
    assert ok["seq"] == 3 and VR.verified_report(root, lock_dir, run_dir) is not None


def test_last_lock_by_chain_not_clock(official, monkeypatch) -> None:
    """r2 F6 같은 종류 — 정정 잠금을 시계가 뒤로 간 채 만들면(이름은 앞) 이어짐 끝 = 새 잠금 → 옛 판정 숨김."""
    cfg, root, lock_dir, _run_dir, _mine = official
    VF.verify(cfg, NOW)
    assert VR.display_report(root) is not None
    real = FW.code_hashes
    monkeypatch.setattr(FW, "code_hashes", lambda repo: {**real(repo), "x": "changed"})
    lock2 = FW.prepare(cfg, NOW - timedelta(hours=1), "시계가 뒤로 간 정정 잠금")
    assert lock2["lock_id"] < lock_dir.name and lock2["previous_lock"] == lock_dir.name
    tip, probs, _dirs = VR.lock_chain(root)
    assert tip.name == lock2["lock_id"] and probs == []
    assert VR.display_report(root) is None
    # 새 잠금에는 실행이 없음 — 멈추지 않고 어긋남 기록(반박 8)
    v = VF.verify(cfg, NOW)
    assert v["status"] == "MISMATCH" and v["lock_id"] == lock2["lock_id"]
    assert v["run_id"] is None
    with pytest.raises(CheckRequired):
        FW.run(
            cfg, NOW
        )  # 실행 코드는 이름 순서(잠긴 코드) — 옛 잠금을 골라 거부(알려진 한계 · 멈춤 쪽)


def test_lock_chain_problems_are_mismatch(official) -> None:
    cfg, root, lock_dir, run_dir, mine = official
    other = root / "locks" / "20991231T000000Z_0000beef"
    other.mkdir()
    (other / "lock.json").write_bytes(
        dumps({"lock_id": other.name, "previous_lock": None})
    )
    checks = VF.check(cfg, root, lock_dir, run_dir, mine)[0]
    assert any("첫 잠금(앞 잠금 없음)이 2개" in c for c in checks), checks
    v = VF.verify(cfg, NOW)
    assert v["status"] == "MISMATCH" and VR.display_report(root) is None


def test_diff_type_strict() -> None:
    assert VF.diff({"x": 1}, {"x": 1.0}) and VF.diff({"x": 1.0}, {"x": 1})
    assert VF.diff({"x": 1}, {"x": True}) and not VF.diff({"x": 2.5}, {"x": 2.5})
    # 목록 길이 — 실행 기록에서 주 하나가 빠져도(앞부분은 같음) 다름
    assert VF.diff([1, 2], [1]) and VF.diff([1], [1, 2])


def test_rebuild_stops_without_benchmark_or_raw_row(
    tmp_path: Path, monkeypatch
) -> None:
    """반박 NIT — 벤치마크 행 없음 · reader 에 있는 날의 원시 행 없음은 KeyError 가 아니라 확인 필요."""
    db, content = _sealed(tmp_path)
    cfg = _cfg(tmp_path, db, content)
    src = RW.Src(cfg)
    d = src.axis[10]
    src.raw["T00001"].pop(d)
    with pytest.raises(CheckRequired):
        src.open_star("T00001", d)
    real = RW.K.load_panel

    def no_bench(*a, **k):
        p = real(*a, **k)
        p.series.pop("069500")
        return p

    monkeypatch.setattr(RW.K, "load_panel", no_bench)
    with pytest.raises(CheckRequired):
        RW.Src(cfg)


def test_run_id_before_lock_id_is_info_only(tmp_path: Path) -> None:
    """r2 F6 같은 종류 — 시각 ID 순서는 PC 시계에 따르므로 판정에 쓰지 않고 참고로만 남긴다."""
    db, content = _sealed(tmp_path)
    cfg = _cfg(tmp_path, db, content)
    FW.prepare(cfg, NOW)
    res = FW.run(cfg, NOW - timedelta(hours=1))  # 시계가 뒤로 간 실행
    root = FW.real_root(cfg.root)
    checks, _h, info = VF.check(cfg, root, FW.locks(root)[-1][0], Path(res["dir"]))
    assert checks == [] and info["id_time_order_ok"] is False


MUST_COVER = [  # 검산이 실제로 기대는 코드(고정 목록 · 지문 대상 계산과 따로 적음)
    "app/__init__.py",
    "app/candidate_compare/__init__.py",
    "app/candidate_compare/verify.py",
    "app/candidate_compare/verify_records.py",
    "app/candidate_compare/recompute.py",
    "app/candidate_compare/recompute_weeks.py",
    "app/candidate_compare/report.py",
    "app/candidate_compare/study.py",
    "app/candidate_compare/protocol.py",
    "app/candidate_compare/flow.py",
    "app/krx_sealed_reader.py",
    "app/entry_timing/data.py",
    "app/entry_timing/study.py",
    "app/entry_timing/protocol.py",
    "app/ml_evidence/store.py",
]


@pytest.mark.parametrize("rel", MUST_COVER)
def test_verify_code_covers_every_dependency(rel, monkeypatch) -> None:
    """r2 F6 — 검산이 쓰는 코드(보고 글 · 판정 순서 함수 포함) 어느 하나가 바뀌어도 검산 지문이 바뀐다."""
    before, files = VR.verify_code()
    assert rel in files
    real = VR.store.sha256_file
    monkeypatch.setattr(
        VR.store,
        "sha256_file",
        lambda p: "0" * 64 if str(p).endswith(rel) else real(p),
    )
    assert VR.verify_code()[0] != before


def test_verify_code_follows_environment(monkeypatch) -> None:
    before = VR.verify_code()[0]
    monkeypatch.setattr(VR, "env", lambda: {"python": "9.9.9", "numpy": "0"})
    assert VR.verify_code()[0] != before


def test_verify_code_closure_covers_code_run_by_verify(official) -> None:
    """런타임 전수 — 검산 한 번 동안 실행된 저장소 app/ 코드 파일이 모두 지문 대상에 들어 있다."""
    import sys

    cfg, _root, _lock_dir, _run_dir, _mine = official
    repo = VR.REPO
    seen: set[str] = set()

    def prof(frame, event, arg):
        if event == "call":
            f = frame.f_code.co_filename
            if f.startswith(str(repo / "app")):
                seen.add(str(Path(f).relative_to(repo)))

    sys.setprofile(prof)
    try:
        VF.verify(cfg, NOW)
    finally:
        sys.setprofile(None)
    files = set(VR.verify_code()[1])
    assert seen and seen <= files, sorted(seen - files)


def test_check_binds_start_time_to_run_id(official) -> None:
    """시작 표지 · 실행 기록 시각을 함께 바꿔도(서로는 같음) 실행 ID 시각과 다르면 잡는다."""
    cfg, root, lock_dir, run_dir, mine = official
    _tamper(run_dir, lock_dir, "started.json", _started_at)
    _tamper(run_dir, lock_dir, "run.json", _started_at)
    checks = VF.check(cfg, root, lock_dir, run_dir, mine)[0]
    assert not any("시작 표지와 실행 기록의 시각" in c for c in checks)
    assert any("시작 시각이 실행 ID 시각과 다름" in c for c in checks), checks


def test_iso_id_time_converts_to_utc_and_rejects_bad_values() -> None:
    assert VF._iso_id_time("2026-11-24T14:21:43+09:00") == "20261124T052143Z"
    assert VF._iso_id_time("2026-11-24T05:21:43+00:00") == "20261124T052143Z"
    assert VF._iso_id_time("2026-11-24T05:21:43") is None  # 시간대 없음
    assert VF._iso_id_time("어제") is None and VF._iso_id_time(None) is None


def _lock_file(root: Path, name: str, prev) -> None:
    d = root / "locks" / name
    d.mkdir()
    (d / "lock.json").write_bytes(dumps({"lock_id": name, "previous_lock": prev}))


def test_lock_chain_cycle_and_missing_link(official) -> None:
    cfg, root, lock_dir, run_dir, mine = official
    b, c = "20991230T000000Z_0000000b", "20991231T000000Z_0000000c"
    _lock_file(root, b, c)
    _lock_file(root, c, b)  # b ↔ c 가 서로를 앞 잠금으로 — 돎
    tip, probs, _ = VR.lock_chain(root)
    assert tip is None and any("돎" in x for x in probs), probs
    for x in (b, c):
        (root / "locks" / x / "lock.json").unlink()
        (root / "locks" / x).rmdir()
    _lock_file(root, b, "20991229T000000Z_0000000a")  # 없는 앞 잠금
    tip, probs, _ = VR.lock_chain(root)
    assert tip is None and any(
        "앞 잠금 칸이 폴더와 맞지 않음" in x for x in probs
    ), probs


def test_check_flags_lock_that_is_not_the_chain_end(official, monkeypatch) -> None:
    cfg, root, lock_dir, run_dir, mine = official
    real = FW.code_hashes
    monkeypatch.setattr(FW, "code_hashes", lambda repo: {**real(repo), "x": "changed"})
    FW.prepare(cfg, NOW + timedelta(hours=1), "정정 잠금")
    checks = VF.check(cfg, root, lock_dir, run_dir, mine)[0]
    assert any("이어짐의 끝(마지막 잠금)이 아님" in c for c in checks), checks


def _rewrite_record(root: Path, vid: str, fn) -> None:
    f = root / "verify" / f"{vid}.json"
    f.chmod(0o644)
    f.write_bytes(dumps(fn(json.loads(f.read_text(encoding="utf-8")))))


def test_old_records_without_sequence_cannot_show(official) -> None:
    cfg, root, lock_dir, run_dir, _mine = official
    v = VF.verify(cfg, NOW)
    _rewrite_record(
        root, v["verify_id"], lambda o: {k: x for k, x in o.items() if k != "seq"}
    )
    assert (
        VR.verified_report(root, lock_dir, run_dir) is None
    )  # 차례 번호 없는 옛 기록 = 근거 아님


def test_two_records_with_same_top_sequence_cannot_show(official) -> None:
    cfg, root, lock_dir, run_dir, _mine = official
    v = VF.verify(cfg, NOW)
    other = VF.new_id(NOW + timedelta(minutes=1))
    (root / "verify" / f"{other}.json").write_bytes(dumps({**v, "verify_id": other}))
    assert VR.verified_report(root, lock_dir, run_dir) is None  # 같은 번호 둘 = 모호


def test_unexpected_error_during_compare_is_recorded(official, monkeypatch) -> None:
    cfg, root, lock_dir, run_dir, mine = official

    def boom(*a, **k):
        raise RuntimeError("예상 못 한 형식")

    monkeypatch.setattr(VF, "_folder", boom)
    checks = VF.check(cfg, root, lock_dir, run_dir, mine)[0]
    assert any("검산 중 형식 오류: RuntimeError" in c for c in checks), checks


def test_report_md_rebuild_failure_is_recorded(official, monkeypatch) -> None:
    cfg, root, lock_dir, run_dir, mine = official

    def boom(rep):
        raise KeyError("main")

    monkeypatch.setattr(VF.RP, "render", boom)
    checks = VF.check(cfg, root, lock_dir, run_dir, mine)[0]
    assert checks == ["report.md 를 다시 만들 수 없음(KeyError)"], checks


def test_rebuild_failure_stops_without_record(official, monkeypatch) -> None:
    cfg, root, _lock_dir, _run_dir, _mine = official

    def boom(c):
        raise RuntimeError("봉인 DB 를 읽을 수 없음")

    monkeypatch.setattr(VF, "rebuild", boom)
    with pytest.raises(CheckRequired):
        VF.verify(cfg, NOW)
    assert not (root / "verify").exists() or not list((root / "verify").glob("*.json"))


def test_lock_chain_flags_other_lock_problems(official) -> None:
    """검산하는 잠금 밖의 잠금 폴더도 본다 — ID 가 폴더와 다름 · lock.json 없이 실행만 남은 폴더."""
    cfg, root, lock_dir, run_dir, mine = official
    d = root / "locks" / "20991231T000000Z_0000000d"
    d.mkdir()
    (d / "lock.json").write_bytes(
        dumps({"lock_id": "20991231T000000Z_ffffffff", "previous_lock": lock_dir.name})
    )
    _tip, probs, _ = VR.lock_chain(root)
    assert any("ID · 앞 잠금 칸이 폴더와 맞지 않음" in x for x in probs), probs
    (d / "lock.json").unlink()
    (d / "runs").mkdir()  # 잠금 파일 없이 실행만 남은 폴더 = 손상
    _tip, probs, _ = VR.lock_chain(root)
    assert any("0000000d lock.json 읽기 실패" in x for x in probs), probs
    assert any(
        "lock.json 읽기 실패" in c
        for c in VF.check(cfg, root, lock_dir, run_dir, mine)[0]
    )


def test_record_path_that_is_a_directory_hides_display(official) -> None:
    cfg, root, _lock_dir, _run_dir, _mine = official
    VF.verify(cfg, NOW)
    assert VR.display_report(root) is not None
    (root / "verify" / f"{VF.new_id(NOW + timedelta(minutes=1))}.json").mkdir()
    assert VR.display_report(root) is None


def test_code_closure_follows_plain_and_from_imports(tmp_path: Path) -> None:
    for rel, body in {
        "app/__init__.py": "",
        "app/pkg/__init__.py": "",
        "app/pkg/entry.py": (
            "import app.pkg.a\nfrom app.pkg import b\n\ndef f():\n    from app import c\n"
        ),
        "app/pkg/a.py": "",
        "app/pkg/b.py": "from app.pkg.d import x\n",
        "app/pkg/d.py": "x = 1\n",
        "app/c.py": "",
        "app/unused.py": "",
    }.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(body, encoding="utf-8")
    got = VR.code_closure(tmp_path, "app/pkg/entry.py")
    assert got == sorted(
        [
            "app/__init__.py",
            "app/pkg/__init__.py",
            "app/pkg/entry.py",
            "app/pkg/a.py",
            "app/pkg/b.py",
            "app/pkg/d.py",
            "app/c.py",
        ]
    )


def test_correction_lock_needs_real_reason(tmp_path: Path, monkeypatch) -> None:
    """정정 잠금(앞 잠금 있음)은 사유 글이 있어야 한다 — 빈 글 · 다른 형이면 어긋남."""
    db, content = _sealed(tmp_path)
    cfg = _cfg(tmp_path, db, content)
    FW.prepare(cfg, NOW)

    def boom(*a, **k):
        raise RuntimeError("계산 중 중단 흉내")

    monkeypatch.setattr(ST, "evaluate", boom)
    with pytest.raises(RuntimeError):
        FW.run(cfg, NOW)
    monkeypatch.undo()
    later = NOW + timedelta(hours=1)
    FW.prepare(cfg, later, "실패 실행 뒤 정정")
    res = FW.run(cfg, later)
    root = FW.real_root(cfg.root)
    tip, probs, _ = VR.lock_chain(root)
    run_dir = Path(res["dir"])
    mine = RC.rebuild(cfg)
    assert probs == [] and VF.check(cfg, root, tip, run_dir, mine)[0] == []
    assert VF.verify(cfg, later)["status"] == "VERIFIED_OK"
    for bad in ("  ", 0, None):
        _tamper(
            run_dir, tip, "lock.json", lambda o, b=bad: {**o, "correction_reason": b}
        )
        checks = VF.check(cfg, root, tip, run_dir, mine)[0]
        assert any("정정 사유" in c for c in checks), (bad, checks)


# ── r2 정정 전 반박 검토 1 ~ 8 ─────────────────────────────────────────────────


def _put_ascii(path: Path, obj) -> None:
    """깨진 유니코드(짝 없는 서로게이트)를 이스케이프로 담은 JSON — 올바른 UTF-8 · JSON 객체."""
    _put_bytes(path, json.dumps(obj, ensure_ascii=True).encode("ascii"))


def _resync(run_dir: Path, lock_dir: Path) -> None:
    _tamper(run_dir, lock_dir, "run.json", lambda o: o)


@pytest.mark.parametrize(
    "where",
    ["run.status", "lock.previous_lock", "report.label", "lock.code_key"],
)
def test_surrogates_in_records_still_write_a_record(official, where) -> None:
    """반박 1 — 기록에서 온 글에 깨진 유니코드가 있어도 어긋남 기록을 쓴다(예외 없음)."""
    cfg, root, lock_dir, run_dir, _mine = official
    bad = "\ud800"
    if where == "run.status":
        o = json.loads((run_dir / "run.json").read_text("utf-8"))
        _put_ascii(run_dir / "run.json", {**o, "status": bad})
    elif where == "lock.previous_lock":
        o = json.loads((lock_dir / "lock.json").read_text("utf-8"))
        _put_ascii(lock_dir / "lock.json", {**o, "previous_lock": bad})
    elif where == "report.label":
        o = json.loads((run_dir / "report.json").read_text("utf-8"))
        o["verdict"]["label"] = bad
        _put_ascii(run_dir / "report.json", o)
        _resync(run_dir, lock_dir)
    else:
        o = json.loads((lock_dir / "lock.json").read_text("utf-8"))
        o["code_hashes"] = {bad: "0" * 64, **o["code_hashes"]}
        _put_ascii(lock_dir / "lock.json", o)
    v = VF.verify(cfg, NOW)
    assert v["status"] == "MISMATCH"
    rec = json.loads((root / "verify" / f"{v['verify_id']}.json").read_bytes())
    assert rec["n_checks"] == v["n_checks"] > 0
    json.dumps(v, ensure_ascii=False).encode("utf-8")  # CLI 출력도 쓸 수 있는 꼴


def test_unreadable_record_stops_verify_and_hides_display(official) -> None:
    """반박 2 — 기록을 못 읽는 동안 새 검산을 하면 차례를 다시 쓸 수 있으므로 멈춘다(되살려도 옛 OK 가 이기지 않음)."""
    cfg, root, lock_dir, run_dir, _mine = official
    v1 = VF.verify(cfg, NOW)
    f = root / "verify" / f"{v1['verify_id']}.json"
    f.chmod(0)
    try:
        assert VR.display_report(root) is None
        with pytest.raises(CheckRequired):
            VF.verify(cfg, NOW + timedelta(minutes=1))
    finally:
        f.chmod(0o644)
    assert VR.display_report(root) is not None  # 아무 새 기록도 없었음 — 옛 OK 그대로


def test_moved_record_folder_breaks_the_chain(official) -> None:
    """반박 2 — 기록 폴더를 옮겨 두고 새 검산(어긋남)을 쓴 뒤 옛 기록을 다시 합쳐도 옛 OK 로 보이지 않는다."""
    import shutil

    cfg, root, lock_dir, run_dir, _mine = official
    VF.verify(cfg, NOW)
    VF.verify(cfg, NOW + timedelta(minutes=1))
    away = root.parent / "verify_away"
    shutil.move(str(root / "verify"), str(away))
    snap = _snapshot(run_dir, lock_dir)
    _tamper(run_dir, lock_dir, "report.json", _label)
    v = VF.verify(cfg, NOW + timedelta(minutes=2))
    assert v["status"] == "MISMATCH" and v["seq"] == 1
    _restore(snap)
    for f in away.iterdir():
        shutil.copy2(f, root / "verify" / f.name)
    assert VR.display_report(root) is None  # 첫 기록이 둘 = 이어짐 깨짐
    tip, probs, _ = VR.history(root)
    assert tip is None and any("첫 검산 기록이 2개" in x for x in probs), probs


def test_permission_errors_record_or_stop_without_traceback(official) -> None:
    """반박 3 — 실행 · 잠금 폴더를 못 읽으면 어긋남 기록 · 검산 기록 폴더를 못 읽으면 확인 필요(예외 아님)."""
    cfg, root, lock_dir, run_dir, _mine = official
    VF.verify(cfg, NOW)
    for d in (run_dir, lock_dir):
        d.chmod(0)
        try:
            v = VF.verify(cfg, NOW + timedelta(minutes=1 if d == run_dir else 2))
            assert v["status"] == "MISMATCH" and v["n_checks"] > 0
            assert VR.display_report(root) is None
        finally:
            d.chmod(0o755)
    vdir = root / "verify"
    vdir.chmod(0)
    try:
        with pytest.raises(CheckRequired):
            VF.verify(cfg, NOW + timedelta(minutes=3))
        assert VR.display_report(root) is None
    finally:
        vdir.chmod(0o755)


@pytest.mark.parametrize("seq", [int("9" * 4000), -50, 0, 2**53 + 1])
def test_sequence_out_of_range_breaks_history(official, seq) -> None:
    """반박 4 — 차례 번호는 1 ~ 2**53 만 · 그 밖이면 이어짐 깨짐(검산 멈춤 · 화면 숨김)."""
    cfg, root, _lock_dir, _run_dir, _mine = official
    v = VF.verify(cfg, NOW)
    other = VF.new_id(NOW + timedelta(minutes=1))
    (root / "verify" / f"{other}.json").write_bytes(
        json.dumps({**v, "verify_id": other, "run_id": "x", "seq": seq}).encode()
    )
    assert VR.display_report(root) is None
    with pytest.raises(CheckRequired):
        VF.verify(cfg, NOW + timedelta(minutes=2))


def test_duplicate_keys_are_not_the_run_format(official) -> None:
    """반박 7 — 실행이 쓴 꼴(정규 JSON)이 아니면 어긋남 — 중복 칸으로 사람이 보는 글과 읽힌 값이 다를 수 있음."""
    cfg, root, lock_dir, run_dir, mine = official
    f = run_dir / "report.json"
    raw = f.read_bytes()
    _put_bytes(
        f,
        b'{"verdict": {"label": "\xec\x97\xb0\xea\xb5\xac \xed\x9b\x84\xeb\xb3\xb4"}, '
        + raw[1:],
    )
    _resync(run_dir, lock_dir)
    checks = VF.check(cfg, root, lock_dir, run_dir, mine)[0]
    assert checks and all("정규 JSON" in c for c in checks), checks


@pytest.mark.parametrize("case", ["run_json_gone", "two_runs"])
def test_broken_run_folder_is_recorded_not_stopped(official, case) -> None:
    """반박 8 — 검산할 실행이 망가지면 기록 없이 멈추지 않고 어긋남을 남긴다(되돌려도 옛 OK 로 안 보임)."""
    import shutil

    cfg, root, lock_dir, run_dir, _mine = official
    VF.verify(cfg, NOW)
    snap = _snapshot(run_dir, lock_dir)
    if case == "run_json_gone":
        (run_dir / "run.json").unlink()
    else:
        shutil.copytree(run_dir, lock_dir / "runs" / "20991231T000000Z_0000beef")
    v = VF.verify(cfg, NOW + timedelta(minutes=1))
    assert v["status"] == "MISMATCH"
    if case == "two_runs":
        shutil.rmtree(lock_dir / "runs" / "20991231T000000Z_0000beef")
    for path, body in snap.items():  # 지운 파일도 되살림
        if path.exists():
            path.chmod(0o644)
        path.write_bytes(body)
    assert VR.display_report(root) is None  # 더 새 어긋남 기록이 이김


def test_verify_code_follows_sqlite_version(monkeypatch) -> None:
    import types

    before = VR.verify_code()[0]
    monkeypatch.setattr(VR, "sqlite3", types.SimpleNamespace(sqlite_version="0.0.0"))
    assert VR.verify_code()[0] != before


def test_safe_makes_any_record_writable() -> None:
    obj = {"a": "\ud800", "b": [float("nan"), float("inf")], "\udfff": {"c": 1.5}}
    out = VR.safe(obj)
    assert dumps(out) and out["b"] == ["nan", "inf"] and out["a"] == "\\ud800"


# ── 검산 기록 이어짐 — 규칙 하나만 어기는 경우 ─────────────────────────────────────


def _two_records(official):
    cfg, root, lock_dir, run_dir, _mine = official
    v1 = VF.verify(cfg, NOW)
    v2 = VF.verify(cfg, NOW + timedelta(minutes=1))
    assert (v1["seq"], v2["seq"], v2["prev"]) == (1, 2, v1["verify_id"])
    assert VR.history(root)[1] == [] and VR.display_report(root) is not None
    return cfg, root, lock_dir, run_dir, v1, v2


def _put_record(root: Path, rec: dict) -> Path:
    """손으로 만든 기록 — 끝 표시도 그 기록으로(이어짐 규칙만 시험)."""
    f = root / "verify" / f"{rec['verify_id']}.json"
    body = dumps(rec)
    f.write_bytes(body)
    sha = VR.store.sha256_bytes(body)
    mark = VR.mark_of(rec["verify_id"], rec["seq"], sha, rec["prev"], rec["prev_sha"])
    VR.write_last(root, mark)
    return f


def _link_after(root: Path, v: dict) -> dict:
    raw = (root / "verify" / f"{v['verify_id']}.json").read_bytes()
    return {
        "seq": v["seq"] + 1,
        "prev": v["verify_id"],
        "prev_sha": VR.store.sha256_bytes(raw),
    }


def test_history_record_copied_under_other_name(official) -> None:
    _cfg_, root, _l, _r, _v1, v2 = _two_records(official)
    (root / "verify" / f"{VF.new_id(NOW + timedelta(hours=1))}.json").write_bytes(
        (root / "verify" / f"{v2['verify_id']}.json").read_bytes()
    )
    assert VR.history(root)[0] is None and VR.display_report(root) is None


def test_history_prev_of_wrong_type(official) -> None:
    _cfg_, root, _l, _r, _v1, v2 = _two_records(official)
    vid = VF.new_id(NOW + timedelta(hours=1))
    _put_record(root, {**v2, "verify_id": vid, **_link_after(root, v2), "prev": ["x"]})
    tip, probs, _ = VR.history(root)
    assert tip is None and probs


def test_history_root_must_be_first(official) -> None:
    _cfg_, root, _l, _r, v1, _v2 = _two_records(official)
    for f in (root / "verify").glob("*.json"):
        f.unlink()
    _put_record(root, {**v1, "seq": 2})  # 앞 기록 없는데 차례 2
    assert VR.history(root)[0] is None
    _put_record(
        root, {**v1, "seq": 1, "prev_sha": "x" * 64}
    )  # 첫 기록인데 앞 해시가 있음
    assert VR.history(root)[0] is None


def test_history_prev_missing(official) -> None:
    _cfg_, root, _l, _r, _v1, v2 = _two_records(official)
    vid = VF.new_id(NOW + timedelta(hours=1))
    link = _link_after(root, v2)
    _put_record(
        root, {**v2, "verify_id": vid, **link, "prev": "20991231T000000Z_00000000"}
    )
    tip, probs, _ = VR.history(root)
    assert tip is None and any("가 없음" in x for x in probs), probs


def test_display_needs_chain_tip_for_this_run(official) -> None:
    """맨 끝 기록이 다른 실행의 OK 면 이 실행의 판정은 숨는다(무엇에 대한 검산이든 더 새것이 이김)."""
    _cfg_, root, lock_dir, run_dir, _v1, v2 = _two_records(official)
    vid = VF.new_id(NOW + timedelta(hours=1))
    _put_record(
        root, {**v2, "verify_id": vid, **_link_after(root, v2), "run_id": "other"}
    )
    assert VR.history(root)[1] == []
    assert VR.verified_report(root, lock_dir, run_dir) is None


# ── 검증자 r3 F8 · F9 와 같은 종류 ───────────────────────────────────────────────

ODD = [None, 0, 1, -1, 2**60, 1.5, True, "x", "", [], [1], {}, {"a": 1}]


@pytest.mark.parametrize(
    "val", [[], {}, [1], {"a": 1}, 5, True, "", "20991231T000000Z_00000000"]
)
def test_previous_lock_of_any_shape_is_recorded(official, val) -> None:
    """r3 F8 — 앞 잠금 칸이 목록 · 객체 · 수 · 없는 ID 여도 예외 없이 어긋남 기록."""
    cfg, root, lock_dir, _run_dir, _mine = official
    o = json.loads((lock_dir / "lock.json").read_text("utf-8"))
    _rewrite(lock_dir / "lock.json", {**o, "previous_lock": val})
    v = VF.verify(cfg, NOW)
    assert v["status"] == "MISMATCH" and v["n_checks"] > 0
    assert (root / "verify" / f"{v['verify_id']}.json").exists()


def test_missing_previous_lock_key_is_not_a_first_lock(official) -> None:
    cfg, root, lock_dir, run_dir, mine = official
    o = json.loads((lock_dir / "lock.json").read_text("utf-8"))
    _rewrite(
        lock_dir / "lock.json", {k: x for k, x in o.items() if k != "previous_lock"}
    )
    tip, probs, _ = VR.lock_chain(root)
    assert any("앞 잠금 칸" in x for x in probs), probs
    assert VF.check(cfg, root, lock_dir, run_dir, mine)[0]


def test_chain_checks_never_raise(official, monkeypatch) -> None:
    _cfg_, root, _l, _r, _m = official

    def boom(*a, **k):
        raise RuntimeError("예상 못 한 꼴")

    monkeypatch.setattr(VR, "_chain_of_locks", boom)
    assert VR.lock_chain(root)[1] == ["잠금 이어짐 확인 중 형식 오류(RuntimeError)"]
    monkeypatch.setattr(VR, "_history", boom)
    assert VR.history(root)[1] == ["검산 기록 확인 중 형식 오류(RuntimeError)"]


def _ok_then_mismatch(official):
    """OK(차례 1) → 보고를 바꾼 검산 MISMATCH(차례 2) → 보고 되돌림 — 화면은 숨어야 하는 상태."""
    cfg, root, lock_dir, run_dir, _mine = official
    v1 = VF.verify(cfg, NOW)
    snap = _snapshot(run_dir, lock_dir)
    _tamper(run_dir, lock_dir, "report.json", _label)
    v2 = VF.verify(cfg, NOW + timedelta(minutes=1))
    _restore(snap)
    assert (v1["status"], v2["status"], v2["seq"]) == ("VERIFIED_OK", "MISMATCH", 2)
    assert VR.history(root)[1] == [] and VR.display_report(root) is None
    return cfg, root, v1, v2


def _hidden_and_stopped(root: Path, cfg) -> None:
    assert VR.display_report(root) is None
    with pytest.raises(CheckRequired):
        VR.next_link(root)


@pytest.mark.parametrize("which", ["tip", "root"])
def test_every_field_change_of_a_record_breaks_history(official, which) -> None:
    """r3 F9 · 같은 종류 — 검산 기록의 어떤 칸을 지우거나 다른 값으로 바꿔도 옛 OK 가 되살아나지 않고 새 검산도 멈춘다."""
    cfg, root, v1, v2 = _ok_then_mismatch(official)
    v = v2 if which == "tip" else v1
    f = root / "verify" / f"{v['verify_id']}.json"
    body = f.read_bytes()
    obj = json.loads(body)
    n = 0
    for key in sorted(obj):
        for val in ["<지움>", *ODD]:
            if val != "<지움>" and val == obj[key] and type(val) is type(obj[key]):
                continue
            new = {k: x for k, x in obj.items() if k != key}
            if val != "<지움>":
                new[key] = val
            _put_bytes(f, dumps(new))
            _hidden_and_stopped(root, cfg)
            n += 1
    _put_bytes(f, body)
    assert VR.history(root)[1] == [] and n > 200


@pytest.mark.parametrize("target", ["root", "last"])
def test_deleting_root_or_end_mark_breaks_history(official, target) -> None:
    """첫 기록 · 이어짐 끝 표시(LAST.json)를 지우면 손상 — 화면 숨김 · 새 검산 멈춤."""
    cfg, root, v1, _v2 = _ok_then_mismatch(official)
    name = {"root": f"{v1['verify_id']}.json", "last": VR.LAST}
    (root / "verify" / name[target]).unlink()
    _hidden_and_stopped(root, cfg)


def test_deleting_the_newest_record_keeps_verdict_hidden(official) -> None:
    """반박 검토 2 — 더 새 어긋남 기록 파일을 지워도 옛 OK 가 되살아나지 않는다(표시가 '끝 다음 기록'을 가리킴).

    다음 검산은 그 차례로 이어 쓴다(지운 기록 대신 새 검산 결과가 끝이 됨).
    """
    cfg, root, v1, v2 = _ok_then_mismatch(official)
    (root / "verify" / f"{v2['verify_id']}.json").unlink()
    assert VR.history_state(root)[3] == "pending"
    assert VR.display_report(root) is None
    v3 = VF.verify(cfg, NOW + timedelta(minutes=5))
    assert (
        v3["seq"] == 2
        and v3["prev"] == v1["verify_id"]
        and v3["status"] == "VERIFIED_OK"
    )
    assert VR.display_report(root) is not None


def test_old_end_mark_copy_breaks_history(official) -> None:
    """반박 검토 2 — 옛 LAST 사본(끝의 앞 기록)을 되돌려 놓으면 손상(늦은 표시는 인정하지 않음)."""
    cfg, root, v1, v2 = _ok_then_mismatch(official)
    raw1 = (root / "verify" / f"{v1['verify_id']}.json").read_bytes()
    old = VR.mark_of(v1["verify_id"], 1, VR.store.sha256_bytes(raw1), None, None)
    _put_bytes(root / "verify" / VR.LAST, dumps(old))
    _hidden_and_stopped(root, cfg)


@pytest.mark.parametrize("mark", [None, [], {"verify_id": None}, "x", {"seq": 2}])
def test_bad_end_mark_breaks_history(official, mark) -> None:
    cfg, root, _v1, _v2 = _ok_then_mismatch(official)
    _put_bytes(root / "verify" / VR.LAST, dumps(mark))
    _hidden_and_stopped(root, cfg)


@pytest.mark.parametrize(
    "spoil", ["dup_key", "seq_float", "extra_key", "utf16", "spaces"]
)
def test_end_mark_must_be_exact(official, spoil) -> None:
    """반박 검토 하위 — 끝 표시는 실행이 쓰는 꼴 그대로여야(중복 칸 · 실수 차례 · 칸 추가 · 다른 인코딩 · 공백)."""
    cfg, root, _v1, _v2 = _ok_then_mismatch(official)
    f = root / "verify" / VR.LAST
    raw = f.read_bytes()
    mark = json.loads(raw)
    bad = {
        "dup_key": b'{"seq": 99, ' + raw[1:],
        "seq_float": dumps({**mark, "seq": float(mark["seq"])}),
        "extra_key": dumps({**mark, "note": "x"}),
        "utf16": raw.decode("utf-8").encode("utf-16"),
        "spaces": raw + b" ",
    }[spoil]
    _put_bytes(f, bad)
    _hidden_and_stopped(root, cfg)


@pytest.mark.parametrize("stops", [1, 2])
@pytest.mark.parametrize("first", [True, False])
def test_stop_between_end_mark_and_record_does_not_wedge(
    official, monkeypatch, stops, first
) -> None:
    """반박 검토 1 — 끝 표시를 쓰고 기록을 쓰기 전에 멈춰도(첫 기록 · 연속 두 번 포함) 화면만 숨고 다음 검산이 이어 쓴다."""
    cfg, root, _l, _r, _m = official
    if not first:
        VF.verify(cfg, NOW)
    real = VF.write_once

    def stop(*a, **k):
        if str(a[1]).startswith(str(root / "verify")):
            raise KeyboardInterrupt("쓰다 멈춤 흉내")
        return real(*a, **k)

    monkeypatch.setattr(VF, "write_once", stop)
    for k in range(stops):
        with pytest.raises(KeyboardInterrupt):
            VF.verify(cfg, NOW + timedelta(minutes=1 + k))
        assert (
            VR.history_state(root)[3] == "pending" and VR.display_report(root) is None
        )
    monkeypatch.setattr(VF, "write_once", real)
    v = VF.verify(cfg, NOW + timedelta(minutes=9))
    assert v["status"] == "VERIFIED_OK" and v["seq"] == (1 if first else 2)
    assert VR.history_state(root)[3] == "tip" and VR.display_report(root) is not None


def _v1_record(root: Path, vid: str, **kw) -> Path:
    from app.candidate_compare.protocol import SCHEMA

    f = root / "verify" / f"{vid}.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(
        dumps(
            {
                "schema": SCHEMA["verify"],
                "verify_id": vid,
                "status": "VERIFIED_OK",
                **kw,
            }
        )
    )
    return f


def test_old_format_records_are_bound_to_the_first_record(official) -> None:
    cfg, root, _l, _r, _m = official
    old = _v1_record(
        root, "20261101T000000Z_00000001", seq=1, prev=None
    )  # 앞 형식에 seq 가 있어도 옛 기록
    v = VF.verify(cfg, NOW)
    assert v["seq"] == 1 and v["legacy"] == {
        old.stem: VR.store.sha256_bytes(old.read_bytes())
    }
    assert VR.display_report(root) is not None
    _v1_record(
        root, "20261102T000000Z_00000002"
    )  # 이어짐 뒤에 생긴 옛 형식 기록 = 손상
    _hidden_and_stopped(root, cfg)
    (root / "verify" / "20261102T000000Z_00000002.json").unlink()
    _put_bytes(old, old.read_bytes() + b" ")  # 옛 기록이 바뀜 = 손상
    _hidden_and_stopped(root, cfg)
    old.unlink()  # 옛 기록이 없어지는 것은 괜찮음(근거가 아님)
    assert VR.display_report(root) is not None


def test_end_mark_without_chain_is_a_problem(official) -> None:
    cfg, root, _l, _r, _m = official
    (root / "verify").mkdir(exist_ok=True)
    (root / "verify" / VR.LAST).write_bytes(
        dumps({"verify_id": "x", "seq": 1, "sha256": "0"})
    )
    _hidden_and_stopped(root, cfg)


def test_fresh_folder_and_repeated_verifies(official) -> None:
    cfg, root, _l, _r, _m = official
    assert not (root / "verify").exists() and VR.history(root) == (None, [], [])
    seqs = [VF.verify(cfg, NOW + timedelta(minutes=k))["seq"] for k in range(3)]
    assert seqs == [1, 2, 3] and VR.display_report(root) is not None


TOP_FIELDS = ["lock.json", "started.json", "run.json", "weeks.json", "report.json"]


def test_every_top_field_of_run_files_is_recorded(official, monkeypatch) -> None:
    """다섯 JSON 의 모든 윗칸을 지우거나 다른 꼴(목록 · 객체 · 수 · 참)로 바꿔도 대조는 예외 없이 어긋남을 내고 기록할 수 있다."""
    cfg, root, lock_dir, run_dir, mine = official
    snap = _snapshot(run_dir, lock_dir)
    n = 0
    for name in TOP_FIELDS:
        f = (lock_dir if name == "lock.json" else run_dir) / name
        obj = json.loads(f.read_text("utf-8"))
        for key in sorted(obj):
            for val in ["<지움>", *ODD]:
                if val != "<지움>" and val == obj[key] and type(val) is type(obj[key]):
                    continue
                _restore(snap)
                new = {k: x for k, x in obj.items() if k != key}
                if val != "<지움>":
                    new[key] = val
                _put_bytes(f, dumps(new))
                if name in ("weeks.json", "report.json"):
                    _resync(run_dir, lock_dir)
                checks = VF.check(cfg, root, lock_dir, run_dir, mine)[0]
                assert checks, (name, key, val)
                dumps(VR.safe(checks))
                n += 1
    _restore(snap)
    assert n > 400


def test_pending_mark_must_match_tip_hash(official) -> None:
    """'끝 다음 기록 대기' 표시라도 앞 해시가 지금 끝 기록과 다르면 손상(끝 기록을 바꾼 뒤 새 기록을 지운 경우 등)."""
    cfg, root, _v1, v2 = _ok_then_mismatch(official)
    (root / "verify" / f"{v2['verify_id']}.json").unlink()
    f = root / "verify" / VR.LAST
    mark = json.loads(f.read_text("utf-8"))
    _put_bytes(f, dumps({**mark, "prev_sha": "0" * 64}))
    _hidden_and_stopped(root, cfg)
