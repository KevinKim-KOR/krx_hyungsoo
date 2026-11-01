"""POC6-14 — 06 전향 비교 기록 PC 조회(읽기 전용) 시험.

실제 연구 폴더 · 라이브 DB 를 열지 않는다. tmp 폴더에 가짜 cohort · 예측 · 영수증 · 목표 · 회차 · 보고를 만든다
(실제로 없는 성숙 · 방법 실패 · 보고 손상은 가짜 자료 검증).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import api_ml_forward_comparison as API
from app import forward_compare_view as V
from app.forward_compare import protocol as P

TICKERS = list(P.EXPECTED_COHORT)
D1, D2 = "2026-10-27", "2026-10-29"
RUN1, RUN2 = "20261028T015333Z_aaaaaaaa", "20261030T010545Z_bbbbbbbb"


def _w(path: Path, body) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(body, ensure_ascii=False, sort_keys=True, indent=1).encode()
    path.write_bytes(data)
    return data


def _src(obj="o" * 64):
    """06 inputs._source_ref 와 같은 칸(조회가 읽는 것만) — observed_at 은 원래 비어 있을 수 있다."""
    return {
        "object": obj,
        "observed_at": "2026-10-30T00:40:00.000000Z",
        "available_at": "2026-10-30T00:47:00.000000Z",
    }


def _methods(pred=-0.03, **over):
    out = {m: {"status": "OK", "raw": pred - 0.001, "pred": pred} for m in P.METHODS}
    out.update(over)
    return out


def _prediction(
    root,
    run_id,
    D,
    *,
    published,
    confirmed,
    cutoff,
    entries=None,
    record_type="FORWARD_RESEARCH",
    cohort_id="cohort_v1",
    receipt=True,
    sha_override=None,
    not_predicted=(),
    model="mv_test",
):
    entries = (
        entries
        if entries is not None
        else [
            {
                "ticker": t,
                "role": "PRIMARY",
                "input": {
                    "source": {
                        "object": "o" * 64,
                        "observed_at": "2026-10-30T00:40:00.000000Z",
                        "available_at": "2026-10-30T00:47:00.000000Z",
                    }
                },
                "methods": _methods(),
            }
            for t in TICKERS
        ]
    )
    doc = P.doc(
        "prediction",
        id=run_id,
        D=D,
        record_type=record_type,
        cohort_id=cohort_id,
        model={"model_version": model},
        times={
            "published_at": published,
            "close_cutoff_at": cutoff,
            "input_cutoff": published,
        },
        entries=entries,
        not_predicted=list(not_predicted),
    )
    path = root / "predictions" / D / f"{run_id}.json"
    data = _w(path, doc)
    if receipt:
        _w(
            path.with_name(f"{run_id}.receipt.json"),
            P.doc(
                "prediction_receipt",
                id=run_id,
                D=D,
                prediction_sha256=sha_override or hashlib.sha256(data).hexdigest(),
                confirmed_at=confirmed,
            ),
        )
    return path


def _report(root, run_id, generated, per_date, *, rows=0, mae=None, under=None):
    main = {}
    for name, ms in (
        ("HGB_vs_MEDIAN_RIDGE", ("HGB", "MEDIAN", "RIDGE")),
        ("MLP_CPU_vs_MEDIAN_RIDGE", ("MLP_CPU", "MEDIAN", "RIDGE")),
        ("ALL_FOUR", P.METHODS),
    ):
        main[name] = {
            "rows": rows,
            "dates": 1 if rows else 0,
            "tickers": rows,
            "excluded_rows": 0,
            "mae_pp": {m: (mae if rows else None) for m in ms},
            "deep_loss_le_8pct": {
                "rows": 1 if under is not None else 0,
                "mae_pp": {
                    m: under for m in ms
                },  # 06: 큰 하락 행이 있으면 값 · 없으면 null
                "under_estimate_pp": {m: under for m in ms},
            },
        }
    _w(
        root / "reports" / f"{run_id}.json",
        P.doc(
            "report",
            id=run_id,
            generated_at=generated,
            counts={
                "cohort": 24,
                "forward_dates": len(per_date),
                "primary_records": 48,
                "predicted_by_method": {m: 48 for m in P.METHODS},
                "matured": 0,
                "pending_or_missing": 48,
                "diagnostic_entries": 0,
                "supplementary_entries": 0,
                "unconfirmed_forward_records": 0,
            },
            per_date=per_date,
            main=main,
        ),
    )


def _run(root, run_id, finished, open_items=()):
    _w(
        root / "runs" / f"{run_id}.json",
        P.doc(
            "run",
            id=run_id,
            finished_at=finished,
            maturity={"counts": {}, "open": list(open_items)},
        ),
    )


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "poc6_06"
    _w(
        r / "cohort_v1" / "cohort.json",
        P.doc(
            "cohort",
            cohort_id="cohort_v1",
            tickers=TICKERS,
            selected=[{"ticker": t, "name": f"이름{t}"} for t in TICKERS],
            selected_at="2026-10-22T10:37:34.000000Z",
        ),
    )
    # D1 = 10-27(10-28 공개) · D2 = 10-29(10-30 공개) — 10-30 회차가 D1 을 '결과 대기'로 평가(D2 는 평가 전)
    _prediction(
        r,
        RUN1,
        D1,
        published="2026-10-28T01:53:38.000000Z",
        confirmed="2026-10-28T01:53:39.000000Z",
        cutoff="2026-10-28T06:30:00.000000Z",
    )
    _report(
        r,
        RUN1,
        "2026-10-28T01:53:40.000000Z",
        {D1: {"input_ok_primary": 24, "matured": 0}},
    )
    _run(r, RUN1, "2026-10-28T01:53:41.000000Z")
    _prediction(
        r,
        RUN2,
        D2,
        published="2026-10-30T01:05:48.000000Z",
        confirmed="2026-10-30T01:05:49.000000Z",
        cutoff="2026-10-30T06:30:00.000000Z",
    )
    _report(
        r,
        RUN2,
        "2026-10-30T01:05:50.000000Z",
        {
            D1: {"input_ok_primary": 24, "matured": 0},
            D2: {"input_ok_primary": 24, "matured": 0},
        },
    )
    _run(
        r,
        RUN2,
        "2026-10-30T01:05:51.000000Z",
        [
            {"ticker": t, "D": D1, "status": "PENDING_NOT_DUE", "tried": None}
            for t in TICKERS
        ],
    )
    return r


def _hashes(root: Path) -> dict:
    return {
        str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest()
        for f in sorted(root.rglob("*"))
        if f.is_file()
    }


# ---------------------------------------------------------------- 기본 · 단위 · 성숙


def test_normal_latest_D_units_and_states(root):
    r = V.build(root)
    assert r["status"] == "OK" and r["label"] == "연구용 · 운영 미채택"
    assert r["selected_D"] == D2 and [x["D"] for x in r["dates"]] == [D2, D1]
    assert [x["ticker"] for x in r["rows"]] == sorted(TICKERS)
    row = r["rows"][0]
    assert row["methods"]["HGB"]["pred_pct"] == pytest.approx(-3.0)  # 비율 ×100 한 번
    assert "raw" not in row["methods"]["HGB"] and "pred" not in row["methods"]["HGB"]
    assert {x["actual"]["state"] for x in r["rows"]} == {"NOT_EVALUATED"}
    assert r["basis"]["maturity"] is None and r["basis"]["record_runs"] == [RUN2]
    assert r["report"]["state"] == "OK" and r["report"]["selected_D"] == "INCLUDED"
    assert r["report"]["id"] == RUN2
    assert r["report"]["predicted_dates"] == {"count": 2, "first": D1, "last": D2}
    assert r["report"]["matured_dates"]["count"] == 0
    comp = r["report"]["comparisons"]["ALL_FOUR"]
    assert comp["rows"] == 0 and set(comp["mae_pp"].values()) == {
        None
    }  # 정상 미성숙 보고


def test_older_D_pending_from_latest_run(root):
    r = V.build(root, D1)
    assert {x["actual"]["state"] for x in r["rows"]} == {"PENDING_NOT_DUE"}
    assert r["rows"][0]["actual"]["basis_run"] == RUN2
    assert r["basis"]["maturity"]["runs"] == [RUN2]


def test_matured_target_wins_and_value_checked(root):
    t0, t1 = sorted(TICKERS)[:2]
    _w(
        root / "targets" / D1 / f"{t0}.json",
        P.doc("target", ticker=t0, D=D1, target=-0.0712, target_end="2026-11-25"),
    )
    _w(
        root / "targets" / D1 / f"{t1}.json",
        P.doc("target", ticker=t1, D=D1, target=0.03, target_end="2026-11-25"),
    )
    rows = {x["ticker"]: x for x in V.build(root, D1)["rows"]}
    assert rows[t0]["actual"] == {
        "state": "MATURED",
        "actual_pct": pytest.approx(-7.12),
        "target_end": "2026-11-25",
    }
    assert (
        rows[t1]["actual"]["state"] == "CHECK_REQUIRED"
    )  # 양수 D20 을 0 으로 살리지 않음


@pytest.mark.parametrize("bad", [0.2, -1.5, float("nan"), "x", None, True])
def test_bad_prediction_value_is_not_shown(root, bad):
    t = sorted(TICKERS)[0]
    entries = [
        {
            "ticker": t,
            "role": "PRIMARY",
            "input": {"source": _src()},
            "methods": _methods(HGB={"status": "OK", "pred": bad}),
        }
    ]
    _prediction(
        root,
        "20261031T010000Z_cccccccc",
        "2026-10-30",
        published="2026-11-02T01:05:00.000000Z",
        confirmed="2026-11-02T01:05:01.000000Z",
        cutoff="2026-11-02T06:30:00.000000Z",
        entries=entries,
    )
    row = next(x for x in V.build(root, "2026-10-30")["rows"] if x["ticker"] == t)
    assert row["methods"]["HGB"] == {
        "status": "CHECK_REQUIRED",
        "reason": "저장된 예측 값 확인 필요",
    }
    assert row["methods"]["MEDIAN"]["status"] == "OK"


def test_method_failure_reason_path_hidden_and_missing_method(root):
    t = sorted(TICKERS)[0]
    meth = _methods(
        MLP_CPU={
            "status": "FAILED",
            "reason": "FileNotFoundError: /Users/someone/x/mlp_state.pt",
        }
    )
    del meth["RIDGE"]
    entries = [
        {
            "ticker": t,
            "role": "PRIMARY",
            "input": {"source": _src()},
            "methods": meth,
        }
    ]
    _prediction(
        root,
        "20261031T010000Z_cccccccc",
        "2026-10-30",
        published="2026-11-02T01:05:00.000000Z",
        confirmed="2026-11-02T01:05:01.000000Z",
        cutoff="2026-11-02T06:30:00.000000Z",
        entries=entries,
    )
    r = V.build(root, "2026-10-30")
    row = next(x for x in r["rows"] if x["ticker"] == t)
    assert row["methods"]["MLP_CPU"]["status"] == "FAILED"
    assert (
        "/Users" not in row["methods"]["MLP_CPU"]["reason"]
        and "<경로>" in row["methods"]["MLP_CPU"]["reason"]
    )
    assert row["methods"]["RIDGE"]["status"] == "MISSING"
    others = [x for x in r["rows"] if x["ticker"] != t]
    assert len(others) == 23 and not any(
        x["primary"] for x in others
    )  # 결측을 숨기지 않음


def test_not_predicted_reason_kept(root):
    t = sorted(TICKERS)[0]
    entries = [
        e
        for e in json.loads((root / "predictions" / D2 / f"{RUN2}.json").read_text())[
            "entries"
        ]
        if e["ticker"] != t
    ]
    _prediction(
        root,
        "20261031T010000Z_cccccccc",
        "2026-10-30",
        published="2026-11-02T01:05:00.000000Z",
        confirmed="2026-11-02T01:05:01.000000Z",
        cutoff="2026-11-02T06:30:00.000000Z",
        entries=entries,
        not_predicted=[{"ticker": t, "status": "NO_EVIDENCE", "tried": []}],
    )
    row = next(x for x in V.build(root, "2026-10-30")["rows"] if x["ticker"] == t)
    assert row == {
        "ticker": t,
        "name": f"이름{t}",
        "primary": False,
        "why": "NO_EVIDENCE",
    }


# ---------------------------------------------------------------- 주 기록 판정(06 재사용)


@pytest.mark.parametrize(
    "kw",
    [
        {"receipt": False},
        {"sha_override": "0" * 64},
        {"confirmed": "2026-11-02T07:00:00.000000Z"},  # 마감(15:30 KST) 뒤 확인
        {"record_type": "DIAGNOSTIC"},
    ],
)
def test_only_receipted_before_cutoff_forward_is_primary(root, kw):
    base = dict(
        published="2026-11-02T01:05:00.000000Z",
        confirmed="2026-11-02T01:05:01.000000Z",
        cutoff="2026-11-02T06:30:00.000000Z",
    )
    base.update(kw)
    _prediction(root, "20261031T010000Z_cccccccc", "2026-10-30", **base)
    r = V.build(root)
    assert r["selected_D"] == D2 and "2026-10-30" not in [x["D"] for x in r["dates"]]
    with pytest.raises(V.DateNotFound):
        V.build(root, "2026-10-30")


def test_retry_fills_only_failed_method(root):
    t = sorted(TICKERS)[0]
    src = _src()
    prim = [
        {
            "ticker": t,
            "role": "PRIMARY",
            "input": {"source": src},
            "methods": _methods(HGB={"status": "FAILED", "reason": "x"}),
        }
    ]
    retry = [
        {
            "ticker": t,
            "role": "RETRY",
            "retry_of": "20261031T010000Z_cccccccc",
            "input": {"source": src},
            "methods": _methods(pred=-0.05),
        }
    ]
    _prediction(
        root,
        "20261031T010000Z_cccccccc",
        "2026-10-30",
        published="2026-11-02T01:05:00.000000Z",
        confirmed="2026-11-02T01:05:01.000000Z",
        cutoff="2026-11-02T06:30:00.000000Z",
        entries=prim,
    )
    _prediction(
        root,
        "20261031T020000Z_dddddddd",
        "2026-10-30",
        published="2026-11-02T03:05:00.000000Z",
        confirmed="2026-11-02T03:05:01.000000Z",
        cutoff="2026-11-02T06:30:00.000000Z",
        entries=retry,
    )
    m = next(x for x in V.build(root, "2026-10-30")["rows"] if x["ticker"] == t)[
        "methods"
    ]
    assert (
        m["HGB"]["status"] == "OK"
        and m["HGB"]["pred_pct"] == pytest.approx(-5.0)
        and m["HGB"]["retried_at"]
    )
    assert m["MEDIAN"]["pred_pct"] == pytest.approx(-3.0)  # 주 기록 OK 값은 그대로


def test_multiple_runs_for_one_D_show_ranges(root):
    a, b = sorted(TICKERS)[:2], sorted(TICKERS)[2:]

    def mk(ts):
        return [
            {
                "ticker": x,
                "role": "PRIMARY",
                "input": {"source": _src()},
                "methods": _methods(),
            }
            for x in ts
        ]

    _prediction(
        root,
        "20261031T010000Z_cccccccc",
        "2026-10-30",
        published="2026-11-02T01:05:00.000000Z",
        confirmed="2026-11-02T01:05:01.000000Z",
        cutoff="2026-11-02T06:30:00.000000Z",
        entries=mk(b),
    )
    _prediction(
        root,
        "20261031T030000Z_dddddddd",
        "2026-10-30",
        published="2026-11-02T03:05:00.000000Z",
        confirmed="2026-11-02T03:05:01.000000Z",
        cutoff="2026-11-02T06:30:00.000000Z",
        entries=mk(a),
    )
    basis = V.build(root, "2026-10-30")["basis"]
    assert basis["record_runs"] == [
        "20261031T010000Z_cccccccc",
        "20261031T030000Z_dddddddd",
    ]
    assert basis["visible_by"] == {
        "min": "2026-11-02T01:05:01.000000Z",
        "max": "2026-11-02T03:05:01.000000Z",
    }


# ---------------------------------------------------------------- 보고 상태(판정 §5)


def test_run_report_missing_shows_previous_report(root):
    (root / "reports" / f"{RUN2}.json").unlink()
    rep = V.build(root)["report"]
    assert (
        rep["selected_D"] == "RUN_REPORT_MISSING"
        and rep["id"] == RUN1
        and rep["state"] == "OK"
    )


def test_run_report_unreadable_and_newer_flagged(root):
    (root / "reports" / f"{RUN2}.json").write_text("{깨짐")
    rep = V.build(root)["report"]
    assert rep["selected_D"] == "RUN_REPORT_UNREADABLE" and rep["id"] == RUN1
    assert rep["newer_unreadable"] == [RUN2]


def test_no_report_at_all(root):
    for f in (root / "reports").glob("*.json"):
        f.unlink()
    rep = V.build(root)["report"]
    assert rep["state"] == "NONE" and rep["selected_D"] == "RUN_REPORT_MISSING"


def test_per_date_absence_alone_does_not_mean_missing(root):
    _report(
        root,
        RUN2,
        "2026-10-30T01:05:50.000000Z",
        {D1: {"input_ok_primary": 24, "matured": 0}},
    )
    assert V.build(root)["report"]["selected_D"] == "INCLUDED"


def test_negative_mae_is_not_abs(root):
    _report(
        root,
        RUN2,
        "2026-10-30T01:05:50.000000Z",
        {D2: {"input_ok_primary": 24, "matured": 3}},
        rows=3,
        mae=-1.0,
        under=2.5,
    )
    rep = V.build(root)["report"]
    assert rep["state"] == "CHECK_REQUIRED"
    assert set(rep["comparisons"]["ALL_FOUR"]["mae_pp"].values()) == {None}
    assert (
        rep["comparisons"]["ALL_FOUR"]["deep"]["under_estimate_pp"]["HGB"] == 2.5
    )  # %p 그대로(×100 없음)
    assert rep["matured_dates"] == {"count": 1, "first": D2, "last": D2}


# ---------------------------------------------------------------- 실패 · 없음 구분


def test_no_folder_and_no_primary(tmp_path, root):
    assert V.build(tmp_path / "none")["status"] == "NO_RECORDS"
    for f in (root / "predictions").rglob("*.receipt.json"):
        f.unlink()
    r = V.build(root)
    assert (
        r["status"] == "NO_RECORDS" and r["other"]["unconfirmed_forward_records"] == 2
    )


def test_cohort_and_schema_mismatch_check_required(root):
    body = json.loads((root / "cohort_v1" / "cohort.json").read_text())
    body["tickers"] = list(reversed(TICKERS))
    _w(root / "cohort_v1" / "cohort.json", body)
    assert V.build(root)["status"] == "CHECK_REQUIRED"


def test_prediction_cohort_id_mismatch(root):
    _prediction(
        root,
        "20261031T010000Z_cccccccc",
        "2026-10-30",
        published="2026-11-02T01:05:00.000000Z",
        confirmed="2026-11-02T01:05:01.000000Z",
        cutoff="2026-11-02T06:30:00.000000Z",
        cohort_id="cohort_v2",
    )
    assert V.build(root)["status"] == "CHECK_REQUIRED"


def test_prediction_corrupt_or_wrong_schema(root):
    p = root / "predictions" / D2 / f"{RUN2}.json"
    p.write_text("{깨짐")
    assert V.build(root)["status"] == "READ_FAILED"
    _w(p, {"schema": "other", "protocol_id": P.PROTOCOL_ID})
    assert V.build(root)["status"] == "CHECK_REQUIRED"


def test_unreadable_run_not_hidden_as_not_evaluated(root):
    (root / "runs" / f"{RUN2}.json").write_text("{깨짐")
    r = V.build(root, D1)
    assert {x["actual"]["state"] for x in r["rows"]} == {"CHECK_REQUIRED"}
    assert r["basis"]["unreadable_runs"] == [RUN2]


# ---------------------------------------------------------------- 읽기 전용 · 응답 경계 · API


def test_read_only_no_paths_no_lock(root, monkeypatch):
    before = _hashes(root)
    r = V.build(root)
    client = _client(root, monkeypatch)
    assert client.get("/ml/forward-comparison").status_code == 200
    assert _hashes(root) == before
    assert not (root / P.LOCK_NAME).exists()
    text = json.dumps(r, ensure_ascii=False)
    assert str(root) not in text and "/Users" not in text and '"raw"' not in text


def test_view_import_does_not_load_model_or_run_modules():
    code = (
        "import sys, app.api_ml_forward_comparison; "
        "bad=[m for m in ('app.forward_compare.models','app.forward_compare.training',"
        "'app.forward_compare.forward','app.forward_compare.mature',"
        "'sklearn','torch','joblib') if m in sys.modules];"
        "print(','.join(bad))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == ""


def _client(root, monkeypatch):
    monkeypatch.setattr(V, "ROOT", root)  # 라우터는 부를 때마다 V.ROOT 를 읽는다
    app = FastAPI()
    app.include_router(API.router)
    return TestClient(app)


def test_api_dates_and_errors(root, monkeypatch):
    c = _client(root, monkeypatch)
    assert c.get("/ml/forward-comparison", params={"d": D1}).json()["selected_D"] == D1
    assert (
        c.get("/ml/forward-comparison", params={"d": "2026-10-28"}).status_code == 404
    )
    for bad in ("2026-1-5", "20261027", "x"):
        assert c.get("/ml/forward-comparison", params={"d": bad}).status_code == 422
    assert (
        c.get("/ml/forward-comparison", params={"d": D1}).json()
        == c.get("/ml/forward-comparison", params={"d": D1}).json()
    )


# ---------------------------------------------------------------- 검증자 r1 F1 — 손상 구조를 정상으로 받지 않음


def _edit(path: Path, fn) -> None:
    body = json.loads(path.read_text())
    fn(body)
    _w(path, body)


def _set(keys, value):
    def fn(body):
        cur = body
        for k in keys[:-1]:
            cur = cur[k]
        cur[keys[-1]] = value

    return fn


def _drop(keys):
    def fn(body):
        cur = body
        for k in keys[:-1]:
            cur = cur[k]
        del cur[keys[-1]]

    return fn


T0 = sorted(TICKERS)[0]


@pytest.mark.parametrize(
    "fn",
    [
        _set(["maturity", "open"], "damaged"),
        _set(["maturity", "open"], [17]),
        _set(["maturity"], "x"),
        _set(["maturity"], {}),
        _set(["maturity", "open"], [{"ticker": T0, "D": D1}]),
        _set(["maturity", "open"], [{"ticker": T0, "D": D1, "status": "WEIRD"}]),
        _set(
            ["maturity", "open"],
            [{"ticker": T0, "D": "10-27", "status": "PENDING_NOT_DUE"}],
        ),
    ],
)
def test_damaged_maturity_block_is_check_required(root, fn):
    _edit(root / "runs" / f"{RUN2}.json", fn)
    for D in (D1, D2):
        r = V.build(root, D)
        assert r["status"] == "OK" and r["basis"]["unreadable_runs"] == [RUN2]
        assert {x["actual"]["state"] for x in r["rows"]} == {"CHECK_REQUIRED"}


def test_run_without_maturity_is_normal_and_id_mismatch_is_bad(root):
    _run(root, "20261031T010000Z_eeeeeeee", "2026-10-31T01:00:00.000000Z")
    _edit(root / "runs" / "20261031T010000Z_eeeeeeee.json", _drop(["maturity"]))
    r = V.build(root, D1)
    assert r["basis"]["unreadable_runs"] == []
    assert {x["actual"]["state"] for x in r["rows"]} == {"PENDING_NOT_DUE"}
    _edit(root / "runs" / "20261031T010000Z_eeeeeeee.json", _set(["id"], "other"))
    assert V.build(root, D1)["basis"]["unreadable_runs"] == [
        "20261031T010000Z_eeeeeeee"
    ]


def _del_comparison(body):
    del body["main"]["HGB_vs_MEDIAN_RIDGE"]


def _extra_method(body):
    body["main"]["ALL_FOUR"]["mae_pp"]["X"] = None


def _drop_method(body):
    del body["main"]["ALL_FOUR"]["mae_pp"]["HGB"]


@pytest.mark.parametrize(
    "fn",
    [
        _set(["main"], {}),
        _del_comparison,
        _drop(["main", "ALL_FOUR", "mae_pp"]),
        _drop_method,
        _extra_method,
        _set(["main", "ALL_FOUR", "rows"], "0"),
        _set(["main", "ALL_FOUR", "rows"], -1),
        _set(["main", "ALL_FOUR", "mae_pp", "HGB"], 1.0),  # 행 0 인데 MAE 값
        _drop(["main", "ALL_FOUR", "deep_loss_le_8pct"]),
        _set(
            ["main", "ALL_FOUR", "deep_loss_le_8pct", "rows"], 5
        ),  # 큰 하락 행 > 비교 행
        _drop(["counts", "matured"]),
        _set(["counts", "predicted_by_method"], {"MEDIAN": 48}),
        _set(["counts", "unconfirmed_forward_records"], -1),
        _set(["per_date"], {D2: {"matured": 0}}),
        _set(["per_date"], {"10-29": {"input_ok_primary": 24, "matured": 0}}),
        _set(["id"], RUN1),
        _set(["generated_at"], "2026-10-30"),
    ],
)
def test_damaged_report_structure_is_unreadable_not_empty(root, fn):
    _edit(root / "reports" / f"{RUN2}.json", fn)
    rep = V.build(root)["report"]
    assert rep["selected_D"] == "RUN_REPORT_UNREADABLE"
    assert rep["id"] == RUN1 and rep["newer_unreadable"] == [RUN2]


def test_rows_with_values_normal_and_old_report_without_unconfirmed_count(root):
    _report(
        root,
        RUN2,
        "2026-10-30T01:05:50.000000Z",
        {D2: {"input_ok_primary": 24, "matured": 3}},
        rows=3,
        mae=1.5,
    )
    rep = V.build(root)["report"]
    assert (
        rep["state"] == "OK" and rep["comparisons"]["ALL_FOUR"]["mae_pp"]["HGB"] == 1.5
    )
    _edit(
        root / "reports" / f"{RUN2}.json",
        _drop(["counts", "unconfirmed_forward_records"]),
    )
    rep = V.build(root)[
        "report"
    ]  # 06 첫 커밋 전 판의 실제 첫 보고 모양 — 정상 · 칸은 '미확인'
    assert (
        rep["selected_D"] == "INCLUDED"
        and rep["counts"]["unconfirmed_forward_records"] is None
    )


def test_all_reports_damaged(root):
    for rid in (RUN1, RUN2):
        _edit(root / "reports" / f"{rid}.json", _set(["main"], {}))
    rep = V.build(root)["report"]
    assert rep["state"] == "CHECK_REQUIRED" and "generated_at" not in rep
    assert (
        sorted(rep["unreadable"]) == [RUN1, RUN2]
        and rep["selected_D"] == "RUN_REPORT_UNREADABLE"
    )


def _entry0(key, value):
    def fn(body):
        body["entries"][0][key] = value

    return fn


def _source0(key, value):
    def fn(body):
        body["entries"][0]["input"]["source"][key] = value

    return fn


@pytest.mark.parametrize(
    "fn",
    [
        _set(["D"], "2026-10-29x"),
        _drop(["times", "input_cutoff"]),
        _set(["model", "model_version"], None),
        _set(["model", "model_version"], ""),
        _set(["record_type"], "OTHER"),
        _entry0("ticker", "999999"),
        _entry0("role", "X"),
        _entry0("methods", []),
        _source0("available_at", None),
        _source0("observed_at", "bad"),
        _drop(["not_predicted"]),
        _set(["not_predicted"], ["x"]),
        _set(["not_predicted"], [{"ticker": "999999", "status": "NO_EVIDENCE"}]),
    ],
)
def test_damaged_prediction_doc_is_check_required(root, fn):
    _edit(root / "predictions" / D2 / f"{RUN2}.json", fn)
    r = V.build(root)
    assert r["status"] == "CHECK_REQUIRED" and "rows" not in r


def test_observed_at_may_be_null(root):
    _edit(root / "predictions" / D2 / f"{RUN2}.json", _source0("observed_at", None))
    # 영수증 해시가 달라져 주 기록에서 빠지지만 구조는 정상(06 은 observed_at 을 비워 둘 수 있다)
    assert V.build(root)["status"] == "OK"


@pytest.mark.parametrize(
    "cell",
    [
        {"status": "WEIRD", "reason": None},
        {"status": "FAILED", "reason": 17},
        {"status": None},
    ],
)
def test_malformed_method_cell_is_check_required(root, cell):
    entries = [
        {
            "ticker": T0,
            "role": "PRIMARY",
            "input": {"source": _src()},
            "methods": _methods(HGB=cell),
        }
    ]
    _prediction(
        root,
        "20261031T010000Z_cccccccc",
        "2026-10-30",
        published="2026-11-02T01:05:00.000000Z",
        confirmed="2026-11-02T01:05:01.000000Z",
        cutoff="2026-11-02T06:30:00.000000Z",
        entries=entries,
    )
    row = next(x for x in V.build(root, "2026-10-30")["rows"] if x["ticker"] == T0)
    assert row["methods"]["HGB"]["status"] == "CHECK_REQUIRED"


def test_target_end_malformed(root):
    _w(
        root / "targets" / D1 / f"{T0}.json",
        P.doc("target", ticker=T0, D=D1, target=-0.05, target_end="11-25"),
    )
    row = next(x for x in V.build(root, D1)["rows"] if x["ticker"] == T0)
    assert row["actual"]["state"] == "CHECK_REQUIRED"


@pytest.mark.parametrize(
    "selected",
    [
        "x",
        [{"ticker": T0, "name": 7}],
        [{"name": "a"}],
        [{"ticker": t, "name": "a"} for t in TICKERS[:-1]],
    ],
)
def test_cohort_selected_malformed(root, selected):
    _edit(root / "cohort_v1" / "cohort.json", _set(["selected"], selected))
    assert V.build(root)["status"] == "CHECK_REQUIRED"


def test_cohort_name_may_be_null(root):
    _edit(
        root / "cohort_v1" / "cohort.json",
        _set(["selected"], [{"ticker": t, "name": None} for t in TICKERS]),
    )
    r = V.build(root)
    assert r["status"] == "OK" and r["rows"][0]["name"] is None


# -------------------------------------------- 검증자 r2 F3 — 공통 행이 있는데 일부 방법 값만 null


def _normal_with_rows(root):
    _report(
        root,
        RUN2,
        "2026-10-30T01:05:50.000000Z",
        {D2: {"input_ok_primary": 24, "matured": 3}},
        rows=3,
        mae=7.0,
        under=7.0,
    )


@pytest.mark.parametrize(
    "fn",
    [
        _set(["main", "ALL_FOUR", "mae_pp", "HGB"], None),  # F3 재현 1
        _set(
            ["main", "ALL_FOUR", "deep_loss_le_8pct", "under_estimate_pp", "HGB"], None
        ),  # F3 재현 2
        _set(["main", "ALL_FOUR", "deep_loss_le_8pct", "mae_pp", "HGB"], None),
        _set(["main", "HGB_vs_MEDIAN_RIDGE", "mae_pp", "MEDIAN"], None),
        _set(
            [
                "main",
                "MLP_CPU_vs_MEDIAN_RIDGE",
                "deep_loss_le_8pct",
                "under_estimate_pp",
                "MLP_CPU",
            ],
            None,
        ),
        _set(["main", "ALL_FOUR", "dates"], 0),  # 행이 있는데 날짜 0
        _set(["main", "ALL_FOUR", "tickers"], 0),
        _set(
            ["main", "ALL_FOUR", "deep_loss_le_8pct", "rows"], 0
        ),  # 큰 하락 행 0 인데 값
    ],
)
def test_partial_null_with_rows_is_unreadable(root, fn):
    _normal_with_rows(root)
    rep = V.build(root)["report"]
    assert rep["state"] == "OK" and rep["selected_D"] == "INCLUDED"  # 정상 대조
    assert rep["comparisons"]["ALL_FOUR"]["mae_pp"]["HGB"] == 7.0
    _edit(root / "reports" / f"{RUN2}.json", fn)
    rep = V.build(root)["report"]
    assert rep["selected_D"] == "RUN_REPORT_UNREADABLE"
    assert rep["id"] == RUN1 and rep["newer_unreadable"] == [RUN2]


def test_zero_rows_with_dates_is_unreadable(root):
    _edit(root / "reports" / f"{RUN2}.json", _set(["main", "ALL_FOUR", "dates"], 1))
    assert V.build(root)["report"]["selected_D"] == "RUN_REPORT_UNREADABLE"
