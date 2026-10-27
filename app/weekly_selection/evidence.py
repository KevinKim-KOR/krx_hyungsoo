"""POC6-11 필수 근거 계약 — 실행 기록이 주장하는 범위만큼 근거가 모두 있어야 한다(검증 r2 · r3 F3).

```text
계약 단계  start → 자격 → 30열 → 검증 학습 24 → 검증 장부 → 시험 학습 23 → 시험 장부(항상 시험까지)
주장       정상 완료 상태 · 최종 판정 · 보고 칸(검증 · 선택 · 시험 · fits) · 남은 파일 → 기록돼 있어야 할 단계 앞부분
           (가장 강한 주장이 범위를 정한다 · 근거가 사라졌다고 요구가 줄지 않음 · 실패 실행만 그 단계가 덜 기록될 수 있음)
근거       기록된 단계마다 그때 만든 파일 · 보고 칸 · run.json 필수 칸 · 해시 목록
정지 이유  장부 단계 미확정 정지 = 실제 미확정 곡선 · 자료 부족 = 잠금 사실의 부족 기록
```
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.ml_evidence import store
from app.weekly_selection import flow as FL
from app.weekly_selection import protocol as PR
from app.weekly_selection import report as R
from app.weekly_selection.protocol import load_json

VAL_BOOKS = ("ML_A", "ML_B", "MOM20", "MOM120", "K")
TEST_BOOKS = ("L_20", "B_20", "K_20", "L_40", "B_40", "K_40")


UNKNOWN_STRUCT = "?"


def expected_stages(lk: dict, struct: Optional[str]) -> list[str]:
    """flow 가 남기는 단계 기록의 계약 순서 — 항상 시험 장부까지(검증 r3: 선택이 없다고 계약을 줄이지 않음).

    시험 학습 이름은 선택 구조로 정해지며, 구조를 정할 근거가 없으면 자리표시 '?' 로 둔다(기록과 맞지 않게).
    """
    qd = lk["facts"]["quarter_detail"]
    st = struct or UNKNOWN_STRUCT
    out = ["start", "panel · eligibility", "features · labels"]
    out += [f"fit {q['id']}_{s}" for q in qd["val"] for s in ("ML_A", "ML_B")]
    out.append("validation books")
    out += [f"fit {q['id']}_{st}" for q in qd["test"]]
    out.append("test books")
    return out


def book_prefix(rdir: Path, sub: str, order: tuple) -> tuple[list[str], list[str]]:
    """장부는 순서대로 쓰고 미확정 곡선에서 멈춘다 — 있어야 할 앞부분과 그 뒤에 있으면 안 되는 장부."""
    present: list[str] = []
    for b in order:
        f = rdir / sub / f"{b}.json"
        if not f.exists():
            break
        present.append(b)
        if load_json(f).get("status") != "OK":
            break
    rest = order[len(present) :]  # noqa: E203
    extra = [b for b in rest if (rdir / sub / f"{b}.json").exists()]
    return present, extra


def _struct(
    rdir: Path, sel: Optional[dict], rep: Optional[dict], out: list[str]
) -> Optional[str]:
    """시험 구조 = 선택 파일 · 보고 선택 · 시험 모델 기록이 가리키는 하나(어긋나면 문제 · 없으면 None)."""
    tests = set()
    for f in PR.model_files(rdir):
        rec = load_json(f)
        if rec.get("phase") == "test":
            tests.add(rec.get("struct"))
    rsel = rep.get("selection") if isinstance(rep, dict) else None
    cand = {x for x in ((sel or {}).get("L"), (rsel or {}).get("L"), *tests) if x}
    if len(cand) > 1:
        out.append(f"시험 구조 기록 불일치(선택 · 보고 · 시험 모델: {sorted(cand)})")
    return next(iter(cand)) if len(cand) == 1 else None


def _claims(lk, meta, rep, rdir, full, failed) -> list[tuple[int, str]]:
    """근거 · 주장 → 기록돼 있어야 할 단계 앞부분 길이(검증 r3 — 가장 강한 주장이 필요 범위를 정함).

    파일은 쓴 뒤 그 단계를 기록하므로 파일 = 그 단계까지. 실패 실행만 그 단계가 덜 기록됐을 수 있다(−1).
    """
    pos = {n: k for k, n in enumerate(full)}
    vb, tb = pos["validation books"] + 1, len(full)
    last_val, last_test = pos["validation books"], len(full) - 1  # 마지막 학습 단계까지
    shift = 1 if failed else 0
    out: list[tuple[int, str]] = []
    if meta.get("status") == "OK":
        out.append((len(full), "정상 완료 상태"))
    if isinstance(rep, dict):
        if (
            (rep.get("judgment") or {}).get("validity") == "OK"
            or "bootstrap" in rep
            or "explain" in rep
        ):
            out.append((len(full), "보고 최종 판정"))
        if "test" in rep or "test_signal_after_end" in rep:
            out.append((tb, "보고 시험 결과"))
        if (
            "selection" in rep
            or "validation" in rep
            or "validation_signal_after_end" in rep
        ):
            out.append((vb, "보고 검증 · 선택"))
        for r in rep.get("fits") or []:
            if isinstance(r, dict) and f"fit {r.get('id')}" in pos:
                out.append((pos[f"fit {r.get('id')}"] + 1, "보고 fits"))
    files = [
        ("eligibility.json.gz", pos["panel · eligibility"] + 1),
        ("features.json.gz", pos["features · labels"] + 1),
        ("predictions_validation.json", last_val),
        ("schedule_validation.json", last_val),
        ("selection.json", vb),
        ("predictions_test.json", last_test),
        ("schedule_test.json", last_test),
    ]
    files += [(f"validation/{b}.json", vb) for b in VAL_BOOKS] + [
        (f"test/{b}.json", tb) for b in TEST_BOOKS
    ]
    for rel, n in files:
        if (rdir / rel).exists():
            out.append((n - shift, rel))
    for f in PR.model_files(rdir):
        name = f"fit {f.stem}"
        out.append(
            (
                (pos[name] + 1 - shift) if name in pos else len(full) + 1,
                f"models/{f.name}",
            )
        )
    return out


STATUSES = ("OK", "CHECK_REQUIRED", "DATA_SHORT", "BUDGET_STOP", "FAILED")
FIXED_FILES = (
    "run.json",
    "report.json",
    "report.md",
    "eligibility.json.gz",
    "features.json.gz",
    "predictions_validation.json",
    "predictions_test.json",
    "schedule_validation.json",
    "schedule_test.json",
    "selection.json",
)


def _books(rdir: Path, sub: str, order: tuple) -> dict:
    """장부 앞부분 · 빠짐없음(정상 끝 또는 미확정 곡선에서 멈춤) · 모두 정상 · 미확정 곡선 있음."""
    present, extra = book_prefix(rdir, sub, order)
    bad = (
        bool(present)
        and load_json(rdir / sub / f"{present[-1]}.json").get("status") != "OK"
    )
    return {
        "present": present,
        "extra": extra,
        "bad": bad,
        "complete": bool(present) and not extra and (present == list(order) or bad),
        "all_ok": present == list(order) and not bad,
    }


def _unexpected_files(
    rdir: Path, full: list[str], names: list[str], status: Optional[str], stop: str
) -> list[str]:
    """계약 밖 파일 — 정해진 이름 · 장부 · 흐름이 그 단계까지 쓰는 모델 파일만(검증 r3 적대 검토 · r4 F4).

    모델 = 기록된 학습 단계 + 진행 중이던 학습(원문은 복원 대조 전에 씀 · 기록은 _claims 가 단계와 대조).
    복원 차이 근거는 그 학습의 복원 차이 정지(정지 이유는 verify 가 다시 대조) 또는 실패 실행에서만 생긴다.
    """
    mids = {n[4:] for n in names if n.startswith("fit ")}
    nxt = full[len(names)] if len(names) < len(full) else ""
    cur = nxt[4:] if nxt.startswith("fit ") else None
    ok = (
        set(FIXED_FILES)
        | {f"validation/{b}.json" for b in VAL_BOOKS}
        | {f"test/{b}.json" for b in TEST_BOOKS}
    )
    if cur:
        mids.add(cur)
        if status == "FAILED" or stop.startswith(
            f"CheckRequired: {cur} 저장 전후 예측 차이 "
        ):
            ok.add(f"models/{cur}{PR.MISMATCH_SUFFIX}")
    ok |= {f"models/{m}.json" for m in mids} | {f"models/{m}.txt" for m in mids}
    bad = []
    for f in sorted(rdir.rglob("*")):
        if not f.is_file():
            continue
        rel = str(f.relative_to(rdir))
        if (
            rel in ok
        ):  # verify 기록은 실행 폴더 밖(잠금 폴더 verify/)에 둔다 — 안에 있으면 계약 밖
            continue
        bad.append(rel)
    return [f"계약 밖 파일: {', '.join(bad)[:300]}"] if bad else []


def completeness_problems(
    lk: dict, meta: dict, rep: Optional[dict], rdir: Path
) -> list[str]:
    """필수 근거 계약(검증 r2 F3): 기록된 단계마다 그때 만든 파일 · 보고 칸이 반드시 있어야 한다.

    정상 완료(OK)는 계약 단계 전체 · 모든 근거. 중간 정지는 실제로 지나간 단계까지만(아직 만들지 않은
    근거와 잃어버린 근거를 단계 기록으로 구분). 단계 기록 자체가 없으면 그것이 문제다.
    """
    out: list[str] = []
    status = meta.get("status")
    keys = [
        "schema",
        "protocol_id",
        "lock_id",
        "run_id",
        "started_at",
        "status",
        "stages",
        "files",
    ]
    keys += ["reason"] if status == "FAILED" else ["finished_at"]
    miss = [k for k in keys if k not in meta]
    if miss:
        out.append(f"run.json 필수 칸 없음: {', '.join(miss)}")
    stages = meta.get("stages")
    if (
        not isinstance(stages, list)
        or not stages
        or not all(isinstance(x, dict) for x in stages)
    ):
        out.append("run.json 단계 기록 없음 · 형식 이상")
        return out
    names = [x.get("stage") for x in stages]
    sel_f = rdir / "selection.json"
    sel = load_json(sel_f) if sel_f.exists() else None
    struct = _struct(rdir, sel, rep, out)
    full = expected_stages(lk, struct)
    if names != full[: len(names)]:
        out.append("단계 기록 순서 ≠ 계약 순서(시험 구조 근거 없음 포함)")
    if status == "OK" and names != full:
        out.append("정상 완료인데 계약 단계가 다 기록되지 않음")
    claims = _claims(lk, meta, rep, rdir, full, status == "FAILED")
    short = [why for n, why in claims if n > len(names)]
    if short:
        out.append(
            f"근거 · 주장 대비 단계 기록이 짧음(또는 계약 밖 모델): {', '.join(sorted(set(short)))[:300]}"
        )
    vb = full.index("validation books") + 1
    last = names[-1]
    stop = str(rep.get("stop")) if isinstance(rep, dict) else ""
    if status not in STATUSES:
        out.append(f"run.json 상태 {status!r} ≠ 허용 상태 {STATUSES}")
    if status == "FAILED" and (
        (rdir / "report.json").exists() or (rdir / "report.md").exists()
    ):
        out.append(
            "실패 실행에 보고 파일이 있음(흐름은 보고 내용을 다 만든 뒤에만 씀 · 쓰기 도중 실패면 확인 필요)"
        )
    has_file, has_rep = sel is not None, isinstance(rep, dict) and "selection" in rep
    v = _books(rdir, "validation", VAL_BOOKS)
    t = _books(rdir, "test", TEST_BOOKS)
    if (has_file or has_rep) and not v["all_ok"]:
        out.append("선택이 있는데 검증 장부 5개가 모두 정상이 아님")
    if (len(names) > vb or status == "OK") and not (
        has_file and (has_rep or status == "FAILED")
    ):
        out.append(
            "시험 단계 · 정상 완료인데 선택 기록(selection.json · 보고 selection) 없음"
        )
    # 장부 단계에서 멈춘 조합 = 흐름이 실제로 만들 수 있는 것만(검증 r3 · 적대 검토)
    if last == "validation books" and status == "BUDGET_STOP" and (has_file or has_rep):
        out.append(
            "검증 장부에서 예산 정지인데 선택이 있음(선택은 그 확인을 지난 뒤에만 씀)"
        )
    if last == "validation books" and status == "CHECK_REQUIRED":
        q0 = lk["facts"]["quarter_detail"]["test"][0]["id"]
        mid0 = f"{q0}_{(sel or {}).get('L')}"
        reason_ok = stop.startswith(f"CheckRequired: {q0} 학습 표본이 잠금과 다름") or (
            stop.startswith(f"CheckRequired: {mid0} 저장 전후 예측 차이")
            and (rdir / "models" / f"{mid0}.txt").exists()
        )  # 흐름이 시험 첫 학습에서 남기는 정지 이유 두 가지(표본 불일치는 verify 가 다시 셈)
        first_test_fit = v["all_ok"] and has_file and has_rep and reason_ok
        if not (v["bad"] and not (has_file or has_rep)) and not first_test_fit:
            out.append(
                "검증 장부에서 CHECK_REQUIRED 인데 미확정 곡선도 시험 첫 학습 정지도 아님"
            )
    dates_ok = last == "test books" and status == "CHECK_REQUIRED" and t["all_ok"]
    if "주간 날짜" in stop and not dates_ok:
        out.append(
            "'주간 날짜' 정지는 시험 장부 6개가 모두 정상인 시험 장부 단계에서만 가능"
        )
    if (
        last == "test books"
        and status == "CHECK_REQUIRED"
        and not t["bad"]
        and "주간 날짜" not in stop
    ):
        out.append("시험 장부에서 CHECK_REQUIRED 인데 미확정 곡선이 없음")
    if status == "DATA_SHORT" and (
        names != ["start"] or not lk["facts"].get("data_short")
    ):
        out.append(
            "DATA_SHORT 인데 잠금 사실에 부족 기록이 없거나 단계가 start 뒤로 감"
        )
    out += _unexpected_files(rdir, full, names, status, stop)
    done = set(names)
    need: list[str] = []
    if "panel · eligibility" in done:
        need.append("eligibility.json.gz")
    if "features · labels" in done:
        need.append("features.json.gz")
    fits = [n[4:] for n in names if isinstance(n, str) and n.startswith("fit ")]
    for mid in fits:
        need += [f"models/{mid}.json", f"models/{mid}.txt"]
    for stage, key, bk, files in (
        (
            "validation books",
            "검증",
            v,
            ["predictions_validation.json", "schedule_validation.json"],
        ),
        ("test books", "시험", t, ["predictions_test.json", "schedule_test.json"]),
    ):
        if (
            stage in done
        ):  # 장부는 그 단계 확인 전에 모두 쓴다 — 미확정 곡선까지 빠짐없이
            need += files
            if not bk["complete"] or (status == "OK" and not bk["all_ok"]):
                out.append(
                    f"{key} 장부 앞부분 · 순서 이상(있음 {bk['present']} · 뒤에 남은 {bk['extra']})"
                )
    if (
        "validation books" not in done
        and (sel is not None or v["present"])
        and status != "FAILED"
    ):
        out.append("검증 장부 단계 기록 없이 선택 · 검증 장부가 있음")
    if status != "FAILED":
        need += ["report.json", "report.md"]
    lost = [n for n in need if not (rdir / n).exists()]
    if lost:
        out.append(f"지나간 단계의 필수 근거 없음: {', '.join(lost)}")
    if status == "FAILED" or rep is None:
        return out
    rkeys = ["schema", "lock_id", "run_id", "price_note", "judgment"]
    rkeys += [] if status == "OK" else ["stop"]
    rkeys += ["fits"] if fits else []
    rkeys += (
        ["validation", "validation_signal_after_end"]
        if "validation books" in done
        else []
    )
    rkeys += ["selection"] if sel is not None else []
    rkeys += ["test", "test_signal_after_end"] if "test books" in done else []
    rkeys += (
        ["bootstrap", "bootstrap_tail_excluded", "explain"] if status == "OK" else []
    )
    lost_k = [k for k in rkeys if k not in rep]
    if (
        status == "OK"
        and "explain" in rep
        and set((rep["explain"] or {}).get("rank_ic") or {}) != {"L", "B"}
    ):
        lost_k.append("explain.rank_ic(L · B)")
    if lost_k:
        out.append(f"report.json 필수 칸 없음: {', '.join(lost_k)}")
    return out


# ── run · 보고 기록 정합성(verify 가 씀) ──────────────────────────────────────────


REPORT_KEYS = {
    "schema",
    "lock_id",
    "run_id",
    "price_note",
    "judgment",
    "stop",
    "fits",
    "validation",
    "validation_signal_after_end",
    "selection",
    "test",
    "test_signal_after_end",
    "bootstrap",
    "bootstrap_tail_excluded",
    "explain",
}
SELECTION_KEYS = {"L", "B", "cagr", "rule", "selected_at"}
STOP_PREFIX = {  # flow 가 남기는 정지 문구의 시작(상태별)
    "BUDGET_STOP": ("BudgetStop: ",),
    "CHECK_REQUIRED": (
        "CheckRequired: ",
        "검증 곡선 평가 미확정 ",
        "시험 곡선 평가 미확정 ",
    ),
    "DATA_SHORT": ("",),
}


def _stage_time_problems(stages: list, st0, rdir: Path) -> list[str]:
    """단계 시각 ↔ 모델 학습/예측 시각 · 선택 시각(flow 순서 그대로 · 숫자 몇 개만 바꾼 위조 검출)."""
    recs = {f.stem: load_json(f) for f in PR.model_files(rdir)}
    sel_f = rdir / "selection.json"
    sel_at = (
        store.parse_iso(load_json(sel_f)["selected_at"]) if sel_f.exists() else None
    )
    prev = st0
    for x in stages:
        at = store.parse_iso(x["at"])
        name = x["stage"]
        rec = recs.get(name[4:]) if name.startswith("fit ") else None
        if rec is not None and not (
            prev <= store.parse_iso(rec["train_started_at"])
            and store.parse_iso(rec["predicted_at"]) <= at
        ):
            return [f"단계 '{name}' 시각 ≠ 모델 학습 · 예측 시각 순서"]
        if name == "validation books" and sel_at is not None and not at <= sel_at:
            return ["검증 장부 단계 시각 > 선택 시각"]
        prev = at
    return []


def lock_run_problems(lk: dict, ldir: Path, meta: dict, rdir: Path) -> list[str]:
    """잠금 문서 ↔ 지금 코드 · 환경, run.json 식별자 · 시각 · 예산 기록(검증 r1 F1 · 같은 층 전수)."""
    out = PR.lock_problems(lk)
    if lk.get("lock_id") != ldir.name:
        out.append("잠금 id ≠ 잠금 폴더")
    runs = sorted(d.name for d in (ldir / "runs").iterdir() if d.is_dir())
    if runs != [rdir.name]:  # 1회 규칙 — 정정은 새 잠금 아래에만
        out.append(f"한 잠금 아래 실행이 하나가 아님: {runs}")
    if FL.runtime_env() != lk.get("env"):
        out.append("지금 환경 ≠ 잠금 환경")
    if (
        meta.get("schema") != "poc6_11_run_v1"
        or meta.get("protocol_id") != PR.PROTOCOL_ID
        or meta.get("lock_id") != lk.get("lock_id")
        or meta.get("run_id") != rdir.name
    ):
        out.append("run.json 식별자(schema · protocol · 잠금 · 실행 id) 다름")
    try:
        st = store.parse_iso(meta["started_at"])
        if (
            meta.get("finished_at") is not None
            and store.parse_iso(meta["finished_at"]) < st
        ):
            out.append("run.json 끝 시각 < 시작 시각")
    except (KeyError, TypeError, ValueError):
        out.append("run.json 시각 형식 이상")
    stages = meta.get("stages")
    if not isinstance(
        stages, list
    ):  # 없음 · 형식 이상은 완결성 계약이 문제로 남긴다(빈 목록으로 통과시키지 않음)
        return out
    walls = [s.get("wall_s") for s in stages]
    if any(not isinstance(w, (int, float)) for w in walls) or walls != sorted(walls):
        out.append("run.json 단계 경과 기록 이상")
        return out
    try:  # 경과 = 그 단계 기록 시각 − 시작 시각(Budget 이 남긴 그대로 · 숫자 하나만 바꾼 위조 검출)
        st0 = store.parse_iso(meta["started_at"])
        end = store.parse_iso(meta["finished_at"]) if meta.get("finished_at") else None
        for x in stages:
            at = store.parse_iso(x["at"])
            if (
                abs(x["wall_s"] - (at - st0).total_seconds()) > 1e-6
                or at < st0
                or (end and at > end)
            ):
                out.append(
                    f"run.json 단계 '{x.get('stage')}' 경과 ≠ 기록 시각 − 시작 시각"
                )
                return out
    except (KeyError, TypeError, ValueError):
        out.append("run.json 단계 시각 형식 이상")
        return out
    out += _stage_time_problems(stages, st0, rdir)
    over = [
        s["stage"]
        for s in stages
        if s["wall_s"] > PR.BUDGET_S or s["max_rss_bytes"] > PR.RSS_MAX
    ]
    if meta.get("status") == "BUDGET_STOP":
        if not over or over != [stages[-1]["stage"]]:
            out.append("BUDGET_STOP 인데 마지막 단계만 상한을 넘은 기록이 아님")
    elif over and not (
        meta.get("status") == "FAILED" and over == [stages[-1]["stage"]]
    ):  # Budget 은 넘은 단계를 기록하고 바로 멈춘다 — FAILED 는 그 정지 보고를 쓰다 실패한 경우만
        out.append(f"예산 상한 넘은 단계가 있는데 상태 {meta.get('status')}")
    return out


def report_meta_problems(p, sig, fx, lk, meta, rdir, rep) -> list[str]:
    """보고서의 나머지 칸 — 식별자 · 모델 기록 사본 · 구간 밖 신호 · 멈춘 실행의 판정 · report.md."""
    out: list[str] = []
    extra = sorted(set(rep) - REPORT_KEYS)
    if extra:  # 보고서 밖 결론 · 추가 칸 금지(검증 r3 적대 검토)
        out.append(f"report.json 계약 밖 칸: {extra}")
    sel_f = rdir / "selection.json"
    sel = load_json(sel_f) if sel_f.exists() else None
    if sel is not None and (not isinstance(sel, dict) or set(sel) != SELECTION_KEYS):
        out.append("selection.json 칸 ≠ 계약")
    if "selection" in rep and (
        not isinstance(rep["selection"], dict)
        or set(rep["selection"]) != SELECTION_KEYS
        or (sel is not None and _norm(sel) != _norm(rep["selection"]))
    ):
        out.append("report 선택 칸 ≠ 계약 · selection.json(칸 전체)")
    if "explain" in rep and (
        not isinstance(rep["explain"], dict) or set(rep["explain"]) != {"rank_ic"}
    ):
        out.append("report 설명 칸 ≠ 계약(rank_ic 만)")
    if (
        rep.get("schema") != "poc6_11_report_v1"
        or rep.get("lock_id") != lk.get("lock_id")
        or rep.get("run_id") != rdir.name
        or rep.get("price_note") != R.PRICE_NOTE
    ):
        out.append("report.json 식별자 · 가격 의미 문구 다름")
    recs = {r["id"]: r for r in map(PR.load_json, PR.model_files(rdir))}
    if "fits" in rep and _norm({r["id"]: r for r in rep["fits"]}) != _norm(recs):
        out.append("report.json fits ≠ 모델 기록")
    pos = {d: k for k, d in enumerate(p.axis)}
    for tag, key in (
        ("val", "validation_signal_after_end"),
        ("test", "test_signal_after_end"),
    ):
        if key in rep:
            w = {"start_idx": pos[fx[tag]["start"]], "end_idx": pos[fx[tag]["end"]]}
            if rep[key] != FL._after_end(p, sig, w):
                out.append(f"report.json {key} ≠ 재계산")
    status = meta.get("status")
    if (
        status != "OK"
    ):  # 정상 완료가 아니면 판정 = NOT_JUDGED 규칙 · 최종 판정 칸 없음(검증 r3 적대 검토)
        if _norm(rep.get("judgment")) != _norm(R.judge(status, None, None)):
            out.append("멈춘 실행의 판정 ≠ NOT_JUDGED 규칙")
        if any(k in rep for k in ("bootstrap", "bootstrap_tail_excluded", "explain")):
            out.append("정상 완료가 아닌데 bootstrap · 설명 칸이 있음")
        stop = rep.get("stop")
        if not isinstance(stop, str) or not stop.startswith(
            STOP_PREFIX.get(status, ("\x00",))
        ):
            out.append(f"정지 문구 형식 ≠ 상태 {status}")
        if status == "DATA_SHORT" and stop != " · ".join(
            lk["facts"].get("data_short") or []
        ):
            out.append("DATA_SHORT 정지 문구 ≠ 잠금 사실의 부족 기록")
    elif "stop" in rep:
        out.append("정상 완료 보고에 정지 문구가 있음")
    md = rdir / "report.md"
    if not md.exists() or md.read_text(encoding="utf-8") != R.markdown(rep):
        out.append("report.md ≠ report.json 에서 다시 만든 보고")
    return out


def _norm(obj):
    return PR.P8.loads(PR.P8.dumps(obj, compact=True).decode())
