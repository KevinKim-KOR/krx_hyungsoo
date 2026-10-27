"""POC6-11 verify 적대 사례 — 결론을 남긴 채 근거를 지우거나 바꾼 묶음은 모두 불일치(검증 r3 · 적대 검토).

공격(a_*)과 거절(r_*) 사례는 독립 적대 검토가 만든 재현이며, 모두 MISMATCH 여야 한다. 마지막 시험은 흐름이 실제로
만들 수 있는 정지(시험 첫 학습에서 미확정)가 verify 에서 일관(OK)인지 본다(오탐 방지). tmp 봉인 DB · 가짜 모델만 쓴다.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil

import pytest

from app.ml_evidence import store
from app.weekly_selection import flow as FL
from app.weekly_selection import model as M
from app.weekly_selection import policy as PO
from app.weekly_selection import protocol as PR
from app.weekly_selection import report as R
from app.weekly_selection import verify as VR
from tests.test_poc6_11_flow import (  # noqa: F401 — 픽스처 재사용
    REPO,
    _Booster,
    _break,
    _cut_after_validation,
    _rdir,
    _refresh_manifest,
    _run,
    _text,
    sealed,
    study,
)


def _load(p):
    return json.loads(p.read_text())


def _save(p, d):
    p.write_text(json.dumps(d, ensure_ascii=False))


def _rep(rdir, fn):
    rep = _load(rdir / "report.json")
    fn(rep)
    _save(rdir / "report.json", rep)
    (rdir / "report.md").write_text(R.markdown(rep))
    _refresh_manifest(rdir)


def _meta(rdir, fn):
    meta = _load(rdir / "run.json")
    fn(meta)
    _save(rdir / "run.json", meta)
    _refresh_manifest(rdir)


def _rm(rdir, *rels):
    for rel in rels:
        (rdir / rel).unlink()
    _refresh_manifest(rdir)


def _verify(study):  # noqa: F811 — pytest 픽스처 주입
    return VR.verify(study["root"], study["db"], repo=REPO)


FORGED = {
    "h1": "PRICE_GAIN_OBSERVED",
    "candidate": "FURTHER_REVIEW_CANDIDATE",
    "uncertainty": "CI_EXCLUDES_ZERO",
    "reasons": [],
}


# ── attacks ──────────────────────────────────────────────────────────────────────


def a_boot_null_forge_ok(rdir):
    """OK run · bootstrap -> null · judgment forged to H1 observed + candidate."""

    def f(rep):
        rep["bootstrap"] = None
        rep["judgment"].update(FORGED)

    _rep(rdir, f)


def a_boot_empty_forge_ok(rdir):
    def f(rep):
        rep["bootstrap"] = {}
        rep["bootstrap_tail_excluded"] = 99
        rep["judgment"].update(FORGED)
        v = rep["judgment"].get("values")
        if v:
            v["cagr_gap_L_B"] = 0.5

    _rep(rdir, f)


def a_failed_keep_judgment_drop_k40(rdir):
    """OK -> FAILED · test/K_40 deleted · report test drops K_40 · judgment (validity OK) kept."""
    _rm(rdir, "test/K_40.json")
    _rep(rdir, lambda rep: rep["test"].pop("K_40"))
    _meta(rdir, lambda m: m.update(status="FAILED", reason="RuntimeError: x"))


def a_failed_boot_null_minimal(rdir):
    """FAILED · only test/L_20 kept · bootstrap null · explain dropped · forged judgment."""
    _rm(rdir, *(f"test/{b}.json" for b in ("B_20", "K_20", "L_40", "B_40", "K_40")))

    def f(rep):
        rep["test"] = {"L_20": rep["test"]["L_20"]}
        rep["bootstrap"] = None
        rep.pop("explain")
        rep.pop("bootstrap_tail_excluded")
        rep["judgment"].update(FORGED)

    _rep(rdir, f)
    _meta(rdir, lambda m: m.update(status="FAILED", reason="RuntimeError: x"))


def _test_partial(rdir, status, stop, keep=("L_20", "B_20", "K_20"), boot_forge=False):
    drop = [
        b for b in ("L_20", "B_20", "K_20", "L_40", "B_40", "K_40") if b not in keep
    ]
    _rm(rdir, *(f"test/{b}.json" for b in drop))

    def f(rep):
        rep["test"] = {k: v for k, v in rep["test"].items() if k in keep}
        rep.pop("explain")
        rep.pop("bootstrap_tail_excluded")
        rep["stop"] = stop
        if boot_forge:
            rep["bootstrap"] = None
            rep["judgment"] = {**rep["judgment"], **FORGED, "validity": status}
        else:
            rep.pop("bootstrap")
            rep["judgment"] = R.judge(status, None, None)

    _rep(rdir, f)

    def m(meta):
        meta["status"] = status
        if status == "BUDGET_STOP":
            meta["stages"][-1]["wall_s"] = 10**6

    _meta(rdir, m)


def a_budget_stop_test_partial(rdir):
    _test_partial(rdir, "BUDGET_STOP", "BudgetStop: test books: 경과 99999초")


def a_budget_stop_test_only_l20(rdir):
    _test_partial(rdir, "BUDGET_STOP", "BudgetStop: test books", keep=("L_20",))


def a_check_required_dates_partial(rdir):
    _test_partial(
        rdir, "CHECK_REQUIRED", "CheckRequired: L · B 주간 날짜가 다름", keep=("L_20",)
    )


def a_budget_stop_boot_null_forge(rdir):
    _test_partial(rdir, "BUDGET_STOP", "BudgetStop: x", keep=("L_20",), boot_forge=True)


def a_budget_stop_validation_keep_selection(rdir):
    """BUDGET_STOP at 'validation books' (impossible with a selection in the real flow) ·
    test phase deleted · selection.json + report selection kept."""
    sel = _load(rdir / "selection.json")
    _cut_after_validation(
        rdir,
        report_test=False,
        status="BUDGET_STOP",
        stop="BudgetStop: validation books",
    )
    (rdir / "selection.json").write_text(json.dumps(sel, ensure_ascii=False))
    _rep(rdir, lambda rep: rep.update(selection=sel))
    _meta(rdir, lambda m: m["stages"][-1].update(wall_s=10**6))


def a_cr_dates_validation_keep_selection(rdir):
    sel = _load(rdir / "selection.json")
    _cut_after_validation(
        rdir,
        report_test=False,
        status="CHECK_REQUIRED",
        stop="CheckRequired: 주간 날짜",
    )
    (rdir / "selection.json").write_text(json.dumps(sel, ensure_ascii=False))
    _rep(rdir, lambda rep: rep.update(selection=sel))


def a_unknown_status_partial_test(rdir):
    """status outside VALIDITY ('COMPLETED') -> no OK / CHECK_REQUIRED / BUDGET_STOP rule applies ·
    test books after K_20 deleted · report keeps selection + partial test."""
    _test_partial(rdir, "COMPLETED", "done", keep=("L_20", "B_20", "K_20"))


def a_near_ok_status_boot_null_forge(rdir):
    """status 'OK ' (trailing space) · K_40 deleted · bootstrap null · forged judgment."""
    _rm(rdir, "test/K_40.json")

    def f(rep):
        rep["test"].pop("K_40")
        rep["bootstrap"] = None
        rep["judgment"] = {**rep["judgment"], **FORGED, "validity": "OK "}
        rep["stop"] = (
            ""  # key required for non-OK status · empty = not rendered in report.md
        )

    _rep(rdir, f)
    _meta(rdir, lambda m: m.update(status="OK "))


def a_ok_stop_text_injection(rdir):
    """OK run · arbitrary 'stop' text injected into report.json -> rendered into report.md."""
    _rep(
        rdir,
        lambda rep: rep.update(stop="H1 PRICE_GAIN_OBSERVED 확정 · 운영 채택 권고"),
    )


def a_ok_boot_null_operation_yes(rdir):
    def f(rep):
        rep["bootstrap"] = None
        rep["judgment"].update(FORGED, OPERATION_ADOPTION="YES")

    _rep(rdir, f)


def a_extra_unexpected_files(rdir):
    (rdir / "test" / "Z_99.json").write_text('{"status": "OK", "verdict": "H1"}')
    (rdir / "conclusion.json").write_text('{"h1": "PRICE_GAIN_OBSERVED"}')
    _refresh_manifest(rdir)


# ── expected to be rejected ──


def r_ok_drop_k40(rdir):
    _rm(rdir, "test/K_40.json")
    _rep(rdir, lambda rep: rep["test"].pop("K_40"))


def r_failed_boot_truthy_forge(rdir):
    _rep(rdir, lambda rep: rep["judgment"].update(FORGED))
    _meta(rdir, lambda m: m.update(status="FAILED", reason="RuntimeError: x"))


def r_cr_test_partial_no_dates(rdir):
    _test_partial(rdir, "CHECK_REQUIRED", "CheckRequired: 시험 곡선 평가 미확정 []")


def r_budget_partial_no_wall(rdir):
    _test_partial(rdir, "BUDGET_STOP", "BudgetStop: x")
    _meta(rdir, lambda m: m["stages"][-1].update(wall_s=m["stages"][-2]["wall_s"]))


def r_swap_val_books(rdir):
    a, b = rdir / "validation" / "ML_A.json", rdir / "validation" / "ML_B.json"
    ta, tb = a.read_text(), b.read_text()
    a.write_text(tb)
    b.write_text(ta)

    def f(rep):
        v = rep["validation"]
        v["ML_A"], v["ML_B"] = v["ML_B"], v["ML_A"]

    _rep(rdir, f)


def r_extra_model_record(rdir):
    src = sorted((rdir / "models").glob("*.json"))[0]
    d = _load(src)
    d["id"] = "2099Q1_ML_A"
    _save(rdir / "models" / "2099Q1_ML_A.json", d)
    (rdir / "models" / "2099Q1_ML_A.txt").write_text(
        src.with_suffix(".txt").read_text()
    )
    _refresh_manifest(rdir)


def r_dup_test_model_other_struct(rdir):
    t = [
        f
        for f in sorted((rdir / "models").glob("*.json"))
        if _load(f)["phase"] == "test"
    ][0]
    d = _load(t)
    other = "ML_B" if d["struct"] == "ML_A" else "ML_A"
    d.update(struct=other, id=f"{d['quarter']}_{other}")
    _save(rdir / "models" / f"{d['id']}.json", d)
    (rdir / "models" / f"{d['id']}.txt").write_text(t.with_suffix(".txt").read_text())
    _refresh_manifest(rdir)


def r_cr_validation_sel_no_dates(rdir):
    sel = _load(rdir / "selection.json")
    _cut_after_validation(
        rdir, report_test=False, status="CHECK_REQUIRED", stop="CheckRequired: x"
    )
    (rdir / "selection.json").write_text(json.dumps(sel, ensure_ascii=False))
    _rep(rdir, lambda rep: rep.update(selection=sel))


def r_failed_drop_val_book_keep_sel(rdir):
    _rm(rdir, "validation/K.json")
    _rep(rdir, lambda rep: rep["validation"].pop("K"))
    _meta(rdir, lambda m: m.update(status="FAILED", reason="x"))


def r_data_short_forge(rdir):
    _test_partial(rdir, "DATA_SHORT", "평가 주 부족")


def r_failed_no_boot_forge(rdir):
    _rm(rdir, "test/K_40.json")

    def f(rep):
        rep["test"].pop("K_40")
        rep.pop("bootstrap")
        rep["judgment"].update(FORGED)

    _rep(rdir, f)
    _meta(rdir, lambda m: m.update(status="FAILED", reason="x"))


def r_cr_validation_sel_forged_rows_reason(rdir):
    """정지 이유를 '시험 첫 분기 학습 표본 불일치'로 꾸밈 — verify 가 표본을 다시 세어 같으므로 거짓."""
    sel = _load(rdir / "selection.json")
    q0 = sorted(
        _load(f)["quarter"]
        for f in (rdir / "models").glob("*.json")
        if _load(f)["phase"] == "test"
    )[0]
    _cut_after_validation(
        rdir,
        report_test=False,
        status="CHECK_REQUIRED",
        stop=f"CheckRequired: {q0} 학습 표본이 잠금과 다름: 0주 · 0행",
    )
    (rdir / "selection.json").write_text(json.dumps(sel, ensure_ascii=False))
    _rep(rdir, lambda rep: rep.update(selection=sel))


CASES = {k: v for k, v in globals().items() if k.startswith(("a_", "r_"))}


@pytest.mark.parametrize("case", sorted(CASES))
def test_forged_bundle_is_mismatch(study, case):  # noqa: F811 — pytest 픽스처 주입
    res = _run(study)
    assert res["meta"]["status"] == "OK"
    rdir = _rdir(study, res)
    assert _verify(study)["status"] == "OK"
    CASES[case](rdir)
    out = _verify(study)
    assert out["status"] == "MISMATCH" and out["problems"], case


def test_real_stop_in_first_test_fit_verifies_consistently(
    study, monkeypatch  # noqa: F811 — pytest 픽스처 주입
):
    """선택을 쓴 뒤 시험 첫 학습에서 미확정(학습 표본 불일치)으로 멈춘 실제 흐름 — 오탐이 아니어야 한다.

    결함은 같은 코드 · 같은 자료에서 결정적으로 다시 나야 하므로 verify 때도 그대로 둔다.
    """
    from app.weekly_selection import features as F

    q0 = study["fx"]["quarter_detail"]["test"][0]
    orig = F.training_rows

    def rows(tbl, axis, ci):
        out = orig(tbl, axis, ci)
        return (
            out[:-1] if axis[ci] == q0["cutoff"] else out
        )  # 시험 첫 분기만 한 행 모자람

    monkeypatch.setattr(F, "training_rows", rows)
    res = _run(study)
    rdir = _rdir(study, res)
    assert (
        res["meta"]["status"] == "CHECK_REQUIRED" and (rdir / "selection.json").exists()
    )
    assert res["meta"]["stages"][-1]["stage"] == "validation books"
    assert res["report"]["stop"].startswith(
        f"CheckRequired: {q0['id']} 학습 표본이 잠금과 다름"
    )
    out = _verify(study)
    assert out["status"] == "OK", out["problems"][:5]


# ── 2차 적대 검토(정지 이유 · 시각 · 보고 밖 결론 · 1회 규칙) ─────────────────────────────


def _downgrade_report(rep, status, stop, keep_test=True):
    for k in ("bootstrap", "bootstrap_tail_excluded", "explain"):
        rep.pop(k, None)
    if not keep_test:
        rep.pop("test", None)
        rep.pop("test_signal_after_end", None)
    rep["judgment"] = R.judge(status, None, None)
    rep["stop"] = stop


def _forge_budget(meta, n_stages=None):
    """last recorded stage = over budget, with at/wall_s/finished_at consistent."""
    if n_stages is not None:
        meta["stages"] = meta["stages"][:n_stages]
    st0 = store.parse_iso(meta["started_at"])
    at = st0 + dt.timedelta(seconds=PR.BUDGET_S + 1)
    meta["stages"][-1].update(at=store.iso(at), wall_s=float(PR.BUDGET_S + 1))
    meta["finished_at"] = store.iso(at + dt.timedelta(seconds=1))
    meta["status"] = "BUDGET_STOP"


def _test_models(rdir):
    return sorted(
        f for f in (rdir / "models").glob("*.json") if _load(f)["phase"] == "test"
    )


def a2_ok_to_cr_weekly_dates(rdir):
    """OK -> CHECK_REQUIRED '주간 날짜' (verify never recomputes L/B weekly dates)."""
    _rep(
        rdir,
        lambda r: _downgrade_report(
            r, "CHECK_REQUIRED", "CheckRequired: L · B 주간 날짜가 다름"
        ),
    )
    _meta(rdir, lambda m: m.update(status="CHECK_REQUIRED"))


def a2_ok_to_cr_weekly_dates_text_injection(rdir):
    stop = (
        "CheckRequired: L · B 주간 날짜가 다름 — 참고: H1 = PRICE_GAIN_OBSERVED · "
        "CANDIDATE = FURTHER_REVIEW_CANDIDATE 확정"
    )
    _rep(rdir, lambda r: _downgrade_report(r, "CHECK_REQUIRED", stop))
    _meta(rdir, lambda m: m.update(status="CHECK_REQUIRED"))


def a2_ok_to_budget_at_test_books(rdir):
    _rep(
        rdir,
        lambda r: _downgrade_report(
            r, "BUDGET_STOP", "BudgetStop: test books: 경과 5401초"
        ),
    )
    _meta(rdir, _forge_budget)


def a2_ok_to_cr_first_test_fit_forged_restore_diff(rdir):
    """OK -> CHECK_REQUIRED at 'validation books' (first test fit restore diff) keeping selection.
    The orphan .txt is the genuine model (diff would be 0) — verify only checks it exists.
    """
    sel = _load(rdir / "selection.json")
    mid0 = _test_models(rdir)[0].stem
    rels = ["predictions_test.json", "schedule_test.json"]
    rels += [str(f.relative_to(rdir)) for f in (rdir / "test").glob("*.json")]
    for f in _test_models(rdir):
        rels.append(f"models/{f.name}")
        if f.stem != mid0:
            rels.append(f"models/{f.stem}.txt")
    _rm(rdir, *rels)
    (rdir / "test").rmdir()

    def f(rep):
        _downgrade_report(
            rep,
            "CHECK_REQUIRED",
            f"CheckRequired: {mid0} 저장 전후 예측 차이 1.0",
            keep_test=False,
        )
        rep["fits"] = [r for r in rep["fits"] if r["phase"] == "val"]

    _rep(rdir, f)

    def m(meta):
        k = [x["stage"] for x in meta["stages"]].index("validation books")
        meta["stages"] = meta["stages"][: k + 1]
        meta["status"] = "CHECK_REQUIRED"

    _meta(rdir, m)
    assert sel["L"] in mid0


def a2_same_with_garbage_txt(rdir):
    a2_ok_to_cr_first_test_fit_forged_restore_diff(rdir)
    mid0 = next((rdir / "models").glob("2016Q3_*.txt"))
    mid0.write_text("garbage — not a model")
    _refresh_manifest(rdir)


def a2_ok_to_budget_at_first_test_fit(rdir):
    """OK -> BUDGET_STOP at 'fit <q0>_<L>' keeping selection + first test model."""
    tms = _test_models(rdir)
    mid0 = tms[0].stem
    rels = ["predictions_test.json", "schedule_test.json"]
    rels += [str(f.relative_to(rdir)) for f in (rdir / "test").glob("*.json")]
    for f in tms[1:]:
        rels += [f"models/{f.name}", f"models/{f.stem}.txt"]
    _rm(rdir, *rels)
    (rdir / "test").rmdir()

    def f(rep):
        _downgrade_report(
            rep, "BUDGET_STOP", f"BudgetStop: fit {mid0}: 경과 5401초", keep_test=False
        )
        rep["fits"] = [r for r in rep["fits"] if r["phase"] == "val" or r["id"] == mid0]

    _rep(rdir, f)

    def m(meta):
        k = [x["stage"] for x in meta["stages"]].index(f"fit {mid0}")
        _forge_budget(meta, k + 1)

    _meta(rdir, m)


def a2_ok_to_cr_scores_missing_last_test_fit(rdir):
    """OK -> CHECK_REQUIRED after the last test fit ('점수 결측' in test plans) — keeps all test
    models / predictions / schedule + selection; verify never re-checks the scores."""
    _rm(rdir, *[str(f.relative_to(rdir)) for f in (rdir / "test").glob("*.json")])
    (rdir / "test").rmdir()
    _rep(
        rdir,
        lambda r: _downgrade_report(
            r,
            "CHECK_REQUIRED",
            "CheckRequired: RET_20 점수 결측(연속 126 자격이 창을 보장하지 못함)",
            keep_test=False,
        ),
    )

    def m(meta):
        meta["stages"] = meta["stages"][:-1]
        meta["status"] = "CHECK_REQUIRED"

    _meta(rdir, m)


def a2_ok_extra_report_keys(rdir):
    def f(rep):
        rep["conclusion"] = {
            "h1": "PRICE_GAIN_OBSERVED",
            "candidate": "FURTHER_REVIEW_CANDIDATE",
        }
        rep["selection"]["note"] = "L 우위 확정"
        rep["explain"]["verdict"] = "H1 확인"

    _rep(rdir, f)


def a2_ok_plant_verify_record(rdir):
    (rdir / "verify_20990101T000000Z_deadbeef.json").write_text(
        json.dumps({"status": "OK", "problems": [], "h1": "PRICE_GAIN_OBSERVED"})
    )


def a2_failed_keep_report_md_only(rdir):
    """OK -> FAILED: report.json deleted, report.md (renders judgment) kept and forged."""
    md = (rdir / "report.md").read_text()
    md = md.replace("PRICE_GAIN_NOT_SHOWN", "PRICE_GAIN_OBSERVED").replace(
        "NOT_CANDIDATE", "FURTHER_REVIEW_CANDIDATE"
    )
    (rdir / "report.json").unlink()
    (rdir / "report.md").write_text(md)
    _meta(rdir, lambda m: m.update(status="FAILED", reason="RuntimeError: x"))


def a2_failed_md_partial_books(rdir):
    """FAILED during test books (stage 'test books' not recorded) — only L_20 kept, forged md."""
    md = (
        (rdir / "report.md")
        .read_text()
        .replace("PRICE_GAIN_NOT_SHOWN", "PRICE_GAIN_OBSERVED")
    )
    (rdir / "report.json").unlink()
    (rdir / "report.md").write_text(md)
    _rm(rdir, *(f"test/{b}.json" for b in ("B_20", "K_20", "L_40", "B_40", "K_40")))

    def m(meta):
        meta["stages"] = meta["stages"][:-1]
        meta.update(status="FAILED", reason="RuntimeError: x")

    _meta(rdir, m)


def r2_cr_test_books_fake_unresolved_text(rdir):
    _rep(
        rdir,
        lambda r: _downgrade_report(
            r, "CHECK_REQUIRED", "시험 곡선 평가 미확정 [] — x"
        ),
    )
    _meta(rdir, lambda m: m.update(status="CHECK_REQUIRED"))


def r2_budget_wall_only(rdir):
    _rep(rdir, lambda r: _downgrade_report(r, "BUDGET_STOP", "BudgetStop: test books"))

    def m(meta):
        meta["status"] = "BUDGET_STOP"
        meta["stages"][-1]["wall_s"] = float(PR.BUDGET_S + 1)

    _meta(rdir, m)


def r2_budget_at_after_finished(rdir):
    _rep(rdir, lambda r: _downgrade_report(r, "BUDGET_STOP", "BudgetStop: test books"))

    def m(meta):
        fin = meta["finished_at"]
        _forge_budget(meta)
        meta["finished_at"] = fin

    _meta(rdir, m)


def r2_cr_first_test_fit_no_txt(rdir):
    a2_ok_to_cr_first_test_fit_forged_restore_diff(rdir)
    _rm(
        rdir,
        *[str(f.relative_to(rdir)) for f in (rdir / "models").glob("2016Q3_*.txt")],
    )


def r2_cr_dates_drop_k40(rdir):
    _rm(rdir, "test/K_40.json")

    def f(r):
        _downgrade_report(r, "CHECK_REQUIRED", "CheckRequired: L · B 주간 날짜가 다름")
        r["test"].pop("K_40")

    _rep(rdir, f)
    _meta(rdir, lambda m: m.update(status="CHECK_REQUIRED"))


def r2_failed_keep_report_json(rdir):
    _meta(rdir, lambda m: m.update(status="FAILED", reason="x"))


def r2_nonok_keep_bootstrap(rdir):
    def f(r):
        _downgrade_report(r, "CHECK_REQUIRED", "CheckRequired: L · B 주간 날짜가 다름")
        r["bootstrap"] = None

    _rep(rdir, f)
    _meta(rdir, lambda m: m.update(status="CHECK_REQUIRED"))


def r2_ok_with_stop(rdir):
    _rep(rdir, lambda r: r.update(stop="BudgetStop: x"))


def r2_other_struct_txt(rdir):
    sel = _load(rdir / "selection.json")
    other = "ML_B" if sel["L"] == "ML_A" else "ML_A"
    (rdir / "models" / f"2016Q3_{other}.txt").write_text("x")
    _refresh_manifest(rdir)


def r2_cr_weekly_dates_at_val_books(rdir):
    a2_ok_to_cr_first_test_fit_forged_restore_diff(rdir)
    _rep(rdir, lambda r: r.update(stop="CheckRequired: L · B 주간 날짜가 다름"))


CASES2 = {k: v for k, v in globals().items() if k.startswith(("a2_", "r2_"))}


@pytest.mark.parametrize("case", sorted(CASES2))
def test_forged_bundle_round2_is_mismatch(
    study, case  # noqa: F811 — pytest 픽스처 주입
):
    res = _run(study)
    rdir = _rdir(study, res)
    assert _verify(study)["status"] == "OK"
    CASES2[case](rdir)
    out = _verify(study)
    assert out["status"] == "MISMATCH" and out["problems"], case


def test_second_run_under_one_lock_is_mismatch(study, monkeypatch):  # noqa: F811
    def boom(*a, **k):
        raise RuntimeError("x")

    with monkeypatch.context() as m:
        m.setattr(R, "select", boom)
        with pytest.raises(RuntimeError):
            _run(study)
    ldir = next(study["root"].glob("*/protocol.json")).parent
    aside = ldir.parent / "aside"
    shutil.move(str(ldir / "runs"), str(aside))
    FL.run(study["root"], study["db"], REPO, study["clock"])
    for d in aside.iterdir():
        shutil.move(str(d), str(ldir / "runs" / d.name))
    aside.rmdir()
    out = _verify(study)
    assert out["status"] == "MISMATCH" and any(
        "실행이 하나가 아님" in x for x in out["problems"]
    )


def test_consistent_downgrade_never_certifies_a_conclusion(study):  # noqa: F811
    """한계 확인: 시각 · 정지 문구까지 일관되게 '시험 장부에서 예산 정지'로 낮춘 위조는 외부 기준 없이 구별하지
    못할 수 있다. 그래도 verify 가 통과시키는 묶음의 판정은 NOT_JUDGED(결론을 인증하지 않음)여야 한다."""
    res = _run(study)
    rdir = _rdir(study, res)

    def m(meta):
        _forge_budget(meta)
        x = meta["stages"][-1]
        meta["_stop"] = (
            f"BudgetStop: {x['stage']}: 경과 {x['wall_s']:.0f}초 · 최대 RSS {x['max_rss_bytes']} bytes"
        )

    meta = _load(rdir / "run.json")
    m(meta)
    stop = meta.pop("_stop")
    _save(rdir / "run.json", meta)
    _rep(rdir, lambda r: _downgrade_report(r, "BUDGET_STOP", stop))
    _refresh_manifest(rdir)
    out = _verify(study)
    rep = _load(rdir / "report.json")
    assert (
        rep["judgment"]["h1"] == "NOT_JUDGED"
        and rep["judgment"]["candidate"] == "NOT_JUDGED"
    )
    assert out["status"] in (
        "OK",
        "MISMATCH",
    )  # 통과하더라도 결론 없음 — 결과서 §5 한계


# ── 결정적으로 재현되는 실제 흐름 결과는 일관(OK) — 오탐 방지 ──────────────────────────


class _Off(_Booster):
    def predict(self, X, num_threads=None):
        return super().predict(X) + 1.0


def _restore_off_for(monkeypatch, rows):
    """학습 행 수가 `rows` 인 분기의 원문만 복원이 어긋난다(같은 원문 → 같은 결함 · verify 때도 다시 남)."""

    def train(struct, X, y, w):
        b = _Booster(struct)
        b.n = len(y)
        return b

    def restore(text):
        tok = text.split()
        return (_Off if int(tok[-1]) == rows else _Booster)(tok[1])

    monkeypatch.setattr(M, "train", train)
    monkeypatch.setattr(M, "to_text", lambda b: _text(b) + f"rows {b.n}\n")
    monkeypatch.setattr(M, "restore", restore)


def _quarter(s, where):
    """복원 차이를 낼 분기 — 학습 행 수가 그 분기에만 있어야 한다(결정적 결함의 열쇠)."""
    qd = s["fx"]["quarter_detail"]
    allq = qd["val"] + qd["test"]
    ph, k = {"val_first": ("val", 0), "test_first": ("test", 0)}.get(
        where, ("test", -1)
    )
    q = qd[ph][k]
    assert [x["rows"] for x in allq].count(q["rows"]) == 1
    return q


@pytest.mark.parametrize("where", ["val_first", "test_first", "test_last"])
def test_real_restore_diff_stop_verifies_consistently(
    study, monkeypatch, where  # noqa: F811
):
    """검증 r4 F4: 복원 차이로 멈춘 실제 흐름은 진단 파일(<id>.mismatch.json)이 남아도 일관(OK)이어야 한다."""
    q = _quarter(study, where)
    _restore_off_for(monkeypatch, q["rows"])
    res = _run(study)
    rdir = _rdir(study, res)
    stop = res["report"]["stop"]
    assert res["meta"]["status"] == "CHECK_REQUIRED" and " 저장 전후 예측 차이 " in stop
    mid = stop.split()[1]
    assert mid.startswith(q["id"] + "_")
    assert (rdir / "models" / f"{mid}{PR.MISMATCH_SUFFIX}").exists()
    assert not (rdir / "models" / f"{mid}.json").exists()
    if where == "test_first":
        assert res["meta"]["stages"][-1]["stage"] == "validation books"
    out = _verify(study)
    assert out["status"] == "OK", out["problems"][:5]


@pytest.mark.parametrize("kind", ["restore", "budget"])
def test_real_failure_while_reporting_a_stop_is_recorded(
    study, monkeypatch, kind  # noqa: F811
):
    """정지(복원 차이 · 예산) 보고를 쓰다 예외가 나도 run.json FAILED(원래 정지 이유 포함)가 남고 verify 는 일관."""
    if kind == "restore":
        _restore_off_for(monkeypatch, _quarter(study, "test_last")["rows"])
        want = "CheckRequired: "
    else:
        monkeypatch.setattr(PR, "BUDGET_S", 9)  # 가짜 시계 = 호출마다 1초
        want = "BudgetStop: "
    with monkeypatch.context() as mp:
        mp.setattr(R, "markdown", _raise_on(R.markdown, lambda *a, **k: True))
        with pytest.raises(RuntimeError):
            _run(study)
    rdir = next(study["root"].glob("*/runs/*"))
    meta = _load(rdir / "run.json")
    assert meta["status"] == "FAILED" and not (rdir / "report.json").exists()
    assert meta["reason"].startswith(f"정지 보고 중 실패(원래 정지 = {want}")
    if kind == "restore":
        assert list((rdir / "models").glob(f"*{PR.MISMATCH_SUFFIX}"))
    else:
        assert meta["stages"][-1]["wall_s"] > PR.BUDGET_S
    out = _verify(study)
    assert out["run_status"] == "FAILED" and out["status"] == "OK", out["problems"][:4]


def _plant_ok(rdir):
    src = sorted((rdir / "models").glob("*.json"))[0]
    shutil.copy(src, rdir / "models" / f"{src.stem}{PR.MISMATCH_SUFFIX}")


def _plant_other_mid(rdir):
    ev = next((rdir / "models").glob(f"*{PR.MISMATCH_SUFFIX}"))
    mid = ev.name[: -len(PR.MISMATCH_SUFFIX)]
    other = sorted(f.stem for f in PR.model_files(rdir) if f.stem != mid)[
        0
    ]  # 기록된 다른 학습 이름으로 근거를 하나 더 둠
    shutil.copy(ev, rdir / "models" / f"{other}{PR.MISMATCH_SUFFIX}")


def _plant_future_txt(rdir, s):
    last = s["fx"]["quarter_detail"]["test"][-1]["id"]
    shutil.copy(
        next((rdir / "models").glob("*.txt")),
        rdir / "models" / f"{last}_ML_A.txt",
    )  # 아직 오지 않은 학습의 원문


@pytest.mark.parametrize("case", ["ok_planted", "other_mid", "future_txt"])
def test_planted_model_side_files_are_outside_contract(
    study, monkeypatch, case  # noqa: F811
):
    """진단 · 원문 파일은 흐름이 그 단계까지 쓰는 것만 — 심은 파일은 계약 밖(검증 r4 F4 이웃 칸)."""
    if case != "ok_planted":
        _restore_off_for(monkeypatch, _quarter(study, "test_first")["rows"])
    res = _run(study)
    rdir = _rdir(study, res)
    if case == "ok_planted":
        assert res["meta"]["status"] == "OK"
        _plant_ok(rdir)
    elif case == "other_mid":
        _plant_other_mid(rdir)
    else:
        _plant_future_txt(rdir, study)
    _refresh_manifest(rdir)
    out = _verify(study)
    assert out["status"] == "MISMATCH" and any(
        "계약 밖 파일" in x for x in out["problems"]
    ), out["problems"][:4]


def _raise_on(fn, pred, exc=RuntimeError):
    def g(*a, **k):
        if pred(*a, **k):
            raise exc("injected")
        return fn(*a, **k)

    return g


def _real(study, monkeypatch, patches, expect_raise=False):  # noqa: F811
    for (
        mod,
        attr,
        val,
    ) in patches:  # 결함을 verify 때도 그대로 둔다(같은 코드 · 같은 자료면 다시 남)
        monkeypatch.setattr(mod, attr, val)
    if expect_raise:
        with pytest.raises(Exception):
            _run(study)
    else:
        _run(study)
    return _verify(study)


def test_real_k20_bad(study, monkeypatch):  # noqa: F811
    orig = PO.simulate_bench
    tstart = study["fx"]["test"]["start"]

    def sb(p, ci, k_idx, s, e, cost):
        bk = orig(p, ci, k_idx, s, e, cost)
        if p.axis[s] == tstart and cost == PR.BASE_COST:
            bk.status = "CHECK_REQUIRED"
            bk.unresolved = {
                "first_unresolved": "2016-07-05",
                "items": [{"cause": "TEST"}],
            }
            bk.end = {"stopped_at": bk.ledger[-1]["date"]}
        return bk

    out = _real(study, monkeypatch, [(PO, "simulate_bench", sb)])
    assert out["status"] == "OK", out["problems"][:4]


def test_real_l20_bad(study, monkeypatch):  # noqa: F811
    out = _real(study, monkeypatch, [(PO, "simulate", _break("L_20"))])
    assert out["status"] == "OK", out["problems"][:4]


def _walls_for(study, monkeypatch, patches):  # noqa: F811 — 픽스처 값 전달
    root = study["root"]
    study["root"] = root.parent / "dry"
    try:
        with monkeypatch.context() as m:
            for mod, attr, val in patches:
                m.setattr(mod, attr, val)
            res = _run(study)
        return {s["stage"]: s["wall_s"] for s in res["meta"]["stages"]}
    finally:
        study["root"] = root


@pytest.mark.parametrize("where", ["test books", "validation books", "first test fit"])
def test_real_budget_stops(study, monkeypatch, where):  # noqa: F811
    w = _walls_for(study, monkeypatch, [])
    name = (
        where
        if where != "first test fit"
        else [k for k in w if k.startswith("fit 2016Q3_")][0]
    )
    monkeypatch.setattr(PR, "BUDGET_S", w[name] - 0.5)
    out = _real(study, monkeypatch, [])
    assert out["run_status"] == "BUDGET_STOP" and out["status"] == "OK", out[
        "problems"
    ][:4]


@pytest.mark.parametrize(
    "where",
    [
        "simulate_MOM20",
        "simulate_L_40",
        "curve_val",
        "train_first_test",
        "restore_first_test",
        "bootstrap",
        "after_end",
        "markdown_in_finish",
        "rank_ic",
    ],
)
def test_real_failed_at(study, monkeypatch, where):  # noqa: F811
    patches = []
    if where.startswith("simulate_"):
        tgt = where.split("_", 1)[1]
        orig = PO.simulate
        patches = [(PO, "simulate", _raise_on(orig, lambda *a, **k: a[5] == tgt))]
    elif where == "curve_val":
        patches = [(R, "curve", _raise_on(R.curve, lambda *a, **k: True))]
    elif where == "train_first_test":
        orig = M.train
        state = {"n": 0}

        def tr(struct, X, y, w):
            state["n"] += 1
            if state["n"] == 5:
                raise RuntimeError("train boom")
            return orig(struct, X, y, w)

        patches = [(M, "train", tr)]
    elif where == "restore_first_test":
        orig = M.restore
        state = {"n": 0}

        def rs(text):
            state["n"] += 1
            if state["n"] == 5:
                raise RuntimeError("restore boom")
            return orig(text)

        patches = [(M, "restore", rs)]
    elif where == "bootstrap":
        patches = [(R, "bootstrap", _raise_on(R.bootstrap, lambda *a, **k: True))]
    elif where == "after_end":
        state = {"n": 0}
        orig = FL._after_end

        def ae(*a):
            state["n"] += 1
            if state["n"] == 2:
                raise RuntimeError("after_end boom")
            return orig(*a)

        patches = [(FL, "_after_end", ae)]
    elif where == "markdown_in_finish":
        patches = [(R, "markdown", _raise_on(R.markdown, lambda *a, **k: True))]
    elif where == "rank_ic":
        patches = [(R, "rank_ic", _raise_on(R.rank_ic, lambda *a, **k: True))]
    with monkeypatch.context() as mp:
        for mod, attr, val in patches:
            mp.setattr(mod, attr, val)
        with pytest.raises(Exception):
            _run(study)
    out = _verify(study)
    assert out["run_status"] == "FAILED" and out["status"] == "OK", (
        where,
        out["problems"][:4],
    )
