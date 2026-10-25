"""POC6-09 — 기존 모델의 검토 우선순위 효용 검증(설계 V1 · PLAN V1 §5 · §7 · 판정 2026-10-25).

작은 가짜 08 산출물(tmp)만 쓴다. 실제 연구 폴더 · 라이브 DB 읽기 0.
"""

from __future__ import annotations

import json
import math
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from app.feature_gain import protocol as FP
from app.ml_evidence import store
from app.review_priority import core as C
from app.review_priority import flow as F
from app.review_priority import report as RP

Fr = __import__("fractions").Fraction
COMMIT = "a" * 40

REPO = Path(__file__).resolve().parents[1]
TICKERS = ["111111", "222222", "333333", "444444", "555555", "666666"]
REVIEW = ["111111", "222222", "333333", "444444"]
PER_FOLD = 8


def _weekdays(n: int, start: str = "2026-01-05") -> list[str]:
    out, d = [], date.fromisoformat(start)
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


DATES = _weekdays(3 * PER_FOLD)


def _fixture(seed: int = 7) -> dict[str, Any]:
    """08 정정 실행과 같은 모양의 작은 산출물(예측 시험 행 + 예제 학습 · 시험 행)."""
    rng = random.Random(seed)
    folds = [[] for _ in range(3)]
    ex_rows, preds = [], []
    i = 100
    for t in TICKERS:  # 학습 행(예측에 없음 · 연결에서 빠져야 함)
        ex_rows.append(
            {"ticker": t, "date": "2025-12-01", "i": 5, "p": [0.0] * 5, "y": -0.01}
        )
    med = {(t, k): round(-rng.uniform(0.0, 0.06), 4) for t in TICKERS for k in range(3)}
    for k in range(3):
        lo, hi = k * PER_FOLD, (k + 1) * PER_FOLD
        for d in DATES[lo:hi]:
            i += 1
            folds[k].append(i)
            for t in TICKERS:
                truth = round(-rng.uniform(0.0, 0.15), 4)
                p = [round(rng.uniform(-0.1, 0.1), 4) for _ in range(5)]
                ex_rows.append(
                    {"ticker": t, "date": d, "i": i, "p": p, "y": truth, "v": None}
                )
                cfg = {
                    "MEDIAN_P": med[(t, k)],
                    "RIDGE_P": round(-rng.uniform(0.0, 0.1), 4),
                    "HGB_P": round(-rng.uniform(0.0, 0.1), 4),
                }
                for extra in ("HGB_PV", "HGB_PR", "HGB_PVR"):
                    cfg[extra] = cfg["HGB_P"]
                preds.append(
                    {
                        "fold": k,
                        "ticker": t,
                        "date": d,
                        "target_end": d,
                        "truth": truth,
                        "raw": dict(cfg),
                        "preds": cfg,
                    }
                )
    return {
        "protocol": {
            "lock_id": "L1",
            "plan": {"eligible": list(TICKERS), "review": list(REVIEW)},
            "recipe": {"features": {"P": list(F.P_ORDER)}},
        },
        "run": {
            "lock_id": "L1",
            "status": "OK",
            "failed_configs": [],
            "restore_ok": True,
        },
        "examples": {"rows": ex_rows, "folds": folds},
        "predictions": preds,
        "report_json": {"x": 1},
        "report_md": "08 보고서",
    }


EXPECTED = {
    "rows": len(TICKERS) * len(DATES),
    "dates": len(DATES),
    "folds": [
        [DATES[k * PER_FOLD], DATES[(k + 1) * PER_FOLD - 1], PER_FOLD] for k in range(3)
    ],
    "n_per_date": {"G_ALL": len(TICKERS), "G_REVIEW": len(REVIEW)},
    "scope_rows": {
        "G_ALL": len(TICKERS) * len(DATES),
        "G_REVIEW": len(REVIEW) * len(DATES),
    },
}


def _write(repo: Path, data: dict[str, Any], raw: dict[str, bytes] = None):
    """가짜 입력을 쓰고 그 바이트의 해시로 spec 을 만든다(raw = 바이트 직접 지정)."""
    spec = {}
    for name, (rel, _) in F.SPEC.items():
        f = repo / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        if raw and name in raw:
            b = raw[name]
        elif name == "report_md":
            b = data[name].encode()
        else:
            b = FP.dumps(data[name])
        f.write_bytes(b)
        spec[name] = (rel, store.sha256_bytes(b))
    return spec


@pytest.fixture
def world(tmp_path):
    repo = tmp_path / "repo"
    data = _fixture()
    spec = _write(repo, data)
    clock = iter(
        datetime(2026, 10, 25, 10, 0, s, tzinfo=timezone.utc) for s in range(59)
    ).__next__
    return {
        "repo": repo,
        "data": data,
        "spec": spec,
        "root": tmp_path / "out",
        "clock": clock,
    }


def _run(w, **kw):
    return F.run(
        w["root"],
        REPO,
        w["clock"],
        spec=w["spec"],
        expected=EXPECTED,
        inputs_root=w["repo"],
        **kw,
    )


def _verify(w, **kw):
    return F.verify(w["root"], w["repo"], spec=w["spec"], expected=EXPECTED, **kw)


# ── 경계 동점 · 날짜별 지표(설계 §4 · §5) ───────────────────────────────────────


def test_boundary_weights_partial_all_tie_and_exact_equality() -> None:
    bw = C.boundary_weights({"a": -0.3, "b": -0.2, "c": -0.1, "d": -0.1, "e": 0.0})
    assert bw["weights"] == {"a": 1.0, "b": 1.0, "c": 0.5, "d": 0.5, "e": 0.0}
    assert (bw["below"], bw["tie"], bw["q"]) == (2, 2, -0.1)
    allt = C.boundary_weights({t: -0.05 for t in "abcdefg"})
    assert all(v == pytest.approx(3 / 7) for v in allt["weights"].values())
    assert sum(allt["weights"].values()) == pytest.approx(3.0)
    two = C.boundary_weights({"a": 0.0, "b": -0.1})  # n < 3 → k = n
    assert two["k"] == 2 and two["weights"] == {"a": 1.0, "b": 1.0}
    # 저장 숫자 그대로(반올림 · epsilon 없음) — 1 ulp 차이도 다른 값.
    near = math.nextafter(-0.1, 0.0)
    bw = C.boundary_weights({"a": -0.3, "b": -0.2, "c": -0.1, "d": near})
    assert bw["weights"] == {"a": 1.0, "b": 1.0, "c": 1.0, "d": 0.0}
    with pytest.raises(ValueError):
        C.boundary_weights({})


def test_boundary_weights_match_existing_partial_top() -> None:
    """판정 §2 — 기존 `partial_top`(높은 점수 우선 · 비율 k)과 같은 k 가 되는 경우 같은 비중."""
    from app.ml_rf_gate_report import partial_top

    rng = random.Random(3)
    for _ in range(200):
        scores = {
            f"{j:06d}": rng.choice([-0.1, -0.05, -0.02, 0.0, -0.07]) for j in range(15)
        }
        mine = C.boundary_weights(scores)["weights"]
        theirs = partial_top([(t, -s, 0.0) for t, s in scores.items()], 0.2)
        assert theirs["k"] == 3
        assert {t: theirs["weights"].get(t, 0.0) for t in scores} == {
            t: float(v) for t, v in mine.items()
        }


def _r(t, truth, **scores):
    base = {m: 0.0 for m in C.METHODS}
    return {"ticker": t, "truth": truth, "scores": {**base, **scores}}


def test_day_tail_boundary_m_zero_and_over_k() -> None:
    edge = math.nextafter(C.TAIL, 0.0)
    rows = [
        _r("a", -0.08, HGB_P=-0.3),
        _r("b", edge, HGB_P=-0.2),
        _r("c", -0.2, HGB_P=-0.1),
        _r("d", 0.0, HGB_P=0.0),
    ]
    d = C.day(rows)
    assert d["y"] == {"a": 1, "b": 0, "c": 1, "d": 0} and d["M"] == 2  # -8% 포함
    h = d["methods"]["HGB_P"]
    assert (h["TP"], h["P"], h["R"], h["FP"], h["FN"]) == (2, Fr(2, 3), 1, 1, 0)
    u = d["methods"][C.UNIFORM]
    assert u["P"] == 2 / 4 and u["R"] == 3 / 4
    # 큰 하락 0 → P = 0 · R 정의 안 됨(0 · 1 로 채우지 않음)
    z = C.day([_r(t, -0.01) for t in "abcd"])
    assert z["M"] == 0 and all(z["methods"][m]["R"] is None for m in z["methods"])
    assert z["methods"]["RIDGE_P"]["P"] == 0.0
    # 큰 하락 4 > k = 3 → 다 포착 못 함
    many = C.day([_r(t, -0.2, RIDGE_P=-0.1 * i) for i, t in enumerate("abcde")])
    m = many["methods"]["RIDGE_P"]
    assert many["M"] == 5 and m["TP"] == 3 and m["FN"] == 2 and m["R"] == Fr(3, 5)


def _days(spec):
    """spec = [(fold, M, n, P_model)] → summarize 입력(RIDGE_P 만 의미)."""
    out = []
    for fold, rows in spec:
        out.append({"date": f"d{len(out)}", "fold": fold, "day": C.day(rows)})
    return out


def test_summary_date_means_r_only_on_tail_dates() -> None:
    d1 = [
        _r("a", -0.1, RIDGE_P=-0.2),
        _r("b", 0.0, RIDGE_P=-0.1),
        _r("c", 0.0),
        _r("d", 0.0),
    ]
    d2 = [_r(t, -0.01) for t in "abcd"]  # M = 0
    days = _days([(0, d1), (1, d2), (2, d1)])
    s = C.summarize(days)["RIDGE_P"]
    assert s["all"]["P"] == pytest.approx((1 / 3 + 0 + 1 / 3) / 3)
    assert s["all"]["R"] == 1.0 and s["all"]["r_dates"] == 2 and s["all"]["dates"] == 3
    assert s["1"]["R"] is None and s["1"]["r_dates"] == 0 and s["1"]["P"] == 0.0
    sel = C.summarize(days)["RIDGE_P"]["selection"]
    assert sum(sel["share"].values()) == pytest.approx(1.0)


def _tail_days(n_dates, tickers, fold_of=lambda j: j % 3):
    """날마다 큰 하락 종목 둘(tickers 를 돌아가며) — 구간마다 여러 종목이 섞이게."""
    out = []
    for j in range(n_dates):
        hit = {tickers[j % len(tickers)], tickers[(j + 1) % len(tickers)]}
        rows = [_r(x, -0.1 if x in hit else 0.0) for x in "abcdef"]
        out.append({"date": f"d{j}", "fold": fold_of(j), "day": C.day(rows)})
    return out


@pytest.mark.parametrize(
    "n, tickers, enough",
    [
        (21, "abc", True),
        (19, "abc", False),  # 큰 하락 날짜 < 20
        (21, "ab", False),  # 종목 < 3
    ],
)
def test_sample_thresholds(n, tickers, enough) -> None:
    assert C.sample(_tail_days(n, tickers))["enough"] is enough


def test_sample_fold_thresholds() -> None:
    # 구간 3 의 큰 하락 날짜 4 < 5 → 부족
    days = _tail_days(24, "abc", fold_of=lambda j: 0 if j < 10 else 1 if j < 20 else 2)
    s = C.sample(days)
    assert s["folds"][2]["tail_dates"] == 4 and not s["enough"]
    # 전체 · 구간 날짜는 충분하지만 구간 1 의 큰 하락 종목이 1 < 2 → 부족(구간 종목 조건 단독)
    days = []
    for j in range(24):
        fold = j % 3
        hit = {"a"} if fold == 0 else {"bcd"[j % 3], "bcd"[(j + 1) % 3]}
        rows = [_r(x, -0.1 if x in hit else 0.0) for x in "abcdef"]
        days.append({"date": f"d{j}", "fold": fold, "day": C.day(rows)})
    s = C.sample(days)
    assert s["tail_dates"] == 24 and s["tail_tickers"] >= 3
    assert all(f["tail_dates"] >= 5 for f in s["folds"])
    assert s["folds"][0]["tail_tickers"] == 1 and not s["enough"]


def _summary(model, bases):
    """judge 입력 — {method: (P 전체, [P 구간], R 전체)}."""
    out = {}
    for m, (p, folds, r) in {model: bases.pop("_model"), **bases}.items():
        out[m] = {
            "all": {"P": p, "R": r},
            **{str(k): {"P": folds[k]} for k in range(3)},
        }
    return out


def _vals(model=(0.40, [0.40, 0.40, 0.40], 0.5), base=(0.30, [0.30, 0.30, 0.30], 0.4)):
    return {"_model": model, **{b: base for b in C.BASELINES}}


ENOUGH = {"enough": True}


@pytest.mark.parametrize(
    "vals, status",
    [
        (_vals(), C.SIGNAL),
        (
            _vals(
                # 정확히 0.05 · 정확히 -0.05(분수 · 경계 포함)
                model=(Fr(1, 20), [Fr(1, 10), Fr(1, 10), Fr(0)], Fr(1, 2)),
                base=(Fr(0), [Fr(0), Fr(0), Fr(1, 20)], Fr(2, 5)),
            ),
            C.SIGNAL,
        ),
        # ③ 구간 차가 -0.05 보다 10⁻¹⁹ 더 나쁨(분수로만 갈림 · float 0.05 는 이 경계를 못 가름)
        (
            _vals(
                model=(Fr(1, 2), [Fr(1, 2), Fr(1, 2), Fr(0)], Fr(1, 2)),
                base=(Fr(1, 4), [Fr(0), Fr(0), Fr(1, 20) + Fr(1, 10**19)], Fr(2, 5)),
            ),
            C.NOT_SHOWN,
        ),
        # ① 전체 차가 0.05 보다 10⁻¹⁹ 작음
        (
            _vals(
                model=(Fr(1, 20) - Fr(1, 10**19), [Fr(1, 2)] * 3, Fr(1, 2)),
                base=(Fr(0), [Fr(0)] * 3, Fr(2, 5)),
            ),
            C.NOT_SHOWN,
        ),
        # ① 전체 차 0.0499 < 0.05
        (_vals(model=(0.3499, [0.4, 0.4, 0.4], 0.5)), C.NOT_SHOWN),
        # ② 양수 구간 1개
        (_vals(model=(0.40, [0.5, 0.30, 0.30], 0.5)), C.NOT_SHOWN),
        # ③ 한 구간 -0.0501 악화
        (_vals(model=(0.40, [0.6, 0.6, 0.2499], 0.5)), C.NOT_SHOWN),
        # ④ R 낮음 / 같음
        (_vals(model=(0.40, [0.4, 0.4, 0.4], 0.39)), C.NOT_SHOWN),
        (_vals(model=(0.40, [0.4, 0.4, 0.4], 0.4)), C.SIGNAL),
    ],
)
def test_judge_conditions_and_boundaries(vals, status) -> None:
    j = C.judge(_summary("RIDGE_P", vals), ENOUGH, "RIDGE_P")
    assert j["status"] == status


def test_judge_each_baseline_and_data_short() -> None:
    vals = _vals()
    vals["MEDIAN_P"] = (0.36, [0.3, 0.3, 0.3], 0.4)  # 한 기준만 5%p 미만
    j = C.judge(_summary("RIDGE_P", vals), ENOUGH, "RIDGE_P")
    assert j["status"] == C.NOT_SHOWN and j["best_baseline"] == "MEDIAN_P"
    assert not j["against"]["MEDIAN_P"]["pass"] and j["against"]["PRICE20_RULE"]["pass"]
    assert j["p_diff_vs_best"] == pytest.approx(0.04)
    short = C.judge(_summary("RIDGE_P", _vals()), {"enough": False}, "RIDGE_P")
    assert short["status"] == C.DATA_SHORT and short["against"]["MEDIAN_P"]["pass"]


# ── 고정 입력 · 연결(판정 §3-1) ─────────────────────────────────────────────────


def test_read_inputs_same_bytes_once_and_hash(world, monkeypatch) -> None:
    seen: dict[str, int] = {}
    real = Path.read_bytes

    def spy(self):
        seen[self.name] = seen.get(self.name, 0) + 1
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", spy)
    inp = F.read_inputs(world["repo"], world["spec"])
    assert all(v == 1 for v in seen.values()) and len(seen) == 6
    assert inp["_sha256"] == {n: s for n, (_, s) in world["spec"].items()}
    monkeypatch.setattr(Path, "read_bytes", real)
    bad = {**world["spec"], "predictions": (world["spec"]["predictions"][0], "0" * 64)}
    with pytest.raises(F.CheckRequired, match="해시"):
        F.read_inputs(world["repo"], bad)


def test_nonfinite_input_is_check_required(world) -> None:
    text = FP.dumps(world["data"]["predictions"]).decode()
    text = text.replace('"truth": ', '"truth": 1e999, "x": ', 1)
    spec = _write(world["repo"], world["data"], raw={"predictions": text.encode()})
    with pytest.raises(F.CheckRequired, match="비유한"):
        F.read_inputs(world["repo"], spec)


def _mutate(path, value):
    def go(d):
        node = d
        keys = path.split(".")
        for k in keys[:-1]:
            node = node[int(k)] if isinstance(node, list) else node[k]
        last = keys[-1]
        if isinstance(node, list):
            node[int(last)] = value
        else:
            node[last] = value

    return go


def _drop_example(d):
    key = (d["predictions"][3]["ticker"], d["predictions"][3]["date"])
    d["examples"]["rows"] = [
        r for r in d["examples"]["rows"] if (r["ticker"], r["date"]) != key
    ]


def _both(d, field, value):
    """예측 행과 그 예제 행을 함께 바꿔(연결은 유지) 형식 · 종목 검사만 걸리게."""
    p = d["predictions"][5]
    e = next(
        r
        for r in d["examples"]["rows"]
        if (r["ticker"], r["date"]) == (p["ticker"], p["date"])
    )
    p[field] = e[field] = value


def _dup_pred(d):
    d["predictions"].append(dict(d["predictions"][0]))


def _shift_fold(d):
    d["predictions"][0]["fold"] = 2


BROKEN = [
    (_drop_example, "예제 없음"),
    (_dup_pred, "예측 키 중복"),
    (
        lambda d: d["examples"]["rows"].append(dict(d["examples"]["rows"][-1])),
        "예제 키 중복",
    ),
    (_shift_fold, "구간"),
    (_mutate("predictions.5.truth", -0.5), "y 와 다르"),
    (_mutate("predictions.5.preds.RIDGE_P", 0.1), "제한 예측"),
    (lambda d: d["predictions"][5]["preds"].pop("HGB_P"), "형식 손상"),
    (lambda d: _both(d, "date", "2026-02-30"), "날짜"),
    (lambda d: _both(d, "ticker", "999999"), "종목"),
    (lambda d: d["examples"]["rows"][7].update(p=[0.0, "x", 0, 0, 0]), "P 열"),
    (
        _mutate(
            "protocol.recipe.features.P",
            ["chg20", "chg5", "chg60", "vol20", "from_high60"],
        ),
        "P 열 순서",
    ),
    (_mutate("run.status", "FAILED"), "실행 기록"),
    (_mutate("run.failed_configs", ["HGB_P"]), "실패 구성"),
    (_mutate("run.restore_ok", False), "복원"),
    (lambda d: d["predictions"].pop(), "개수"),
]


@pytest.mark.parametrize("change, match", BROKEN)
def test_broken_link_is_check_required(world, change, match) -> None:
    data = json.loads(json.dumps(world["data"]))
    change(data)
    spec = _write(world["repo"], data)
    with pytest.raises(F.CheckRequired, match=match):
        F.build_table(F.read_inputs(world["repo"], spec), EXPECTED)


def test_table_uses_test_rows_and_p_chg20(world) -> None:
    t = F.build_table(F.read_inputs(world["repo"], world["spec"]), EXPECTED)
    assert len(t["rows"]) == EXPECTED["rows"]  # 학습 행(2025-12-01) 제외
    ex = {(r["ticker"], r["date"]): r for r in world["data"]["examples"]["rows"]}
    for r in t["rows"][:20]:
        assert r["scores"]["PRICE20_RULE"] == ex[(r["ticker"], r["date"])]["p"][1]


# ── 범위 독립 · MEDIAN 성질 ─────────────────────────────────────────────────────


def test_scopes_rank_independently_and_median_constant_in_fold(world) -> None:
    table = F.build_table(F.read_inputs(world["repo"], world["spec"]), EXPECTED)
    res = F.compute(table)
    rev = res["rows"]["G_REVIEW"]
    assert {r["ticker"] for r in rev} == set(REVIEW)
    for d in DATES:
        ws = [r["w"]["HGB_P"] for r in rev if r["date"] == d]
        assert sum(ws) == pytest.approx(3.0)  # 보조 범위 안에서 다시 3개
    # G_ALL 에서 고른 종목을 거른 것이 아님 — 비보조 종목이 G_ALL 선택에 들어간 날이 있다.
    all_rows = res["rows"]["G_ALL"]
    assert any(r["w"]["HGB_P"] > 0 and r["ticker"] not in REVIEW for r in all_rows)
    for k in range(3):
        sel = {
            r["date"]: tuple(
                sorted(
                    t["ticker"]
                    for t in all_rows
                    if t["date"] == r["date"] and t["w"]["MEDIAN_P"] > 0
                )
            )
            for r in all_rows
            if r["fold"] == k
        }
        assert len(set(sel.values())) == 1  # 구간 안에서 MEDIAN 선택이 같다


# ── run · verify(판정 §3-2 · §3-3) ─────────────────────────────────────────────


def test_run_once_protocol_first_and_verify(world) -> None:
    res = _run(world, base_commit=COMMIT)
    rdir = res["run_dir"]
    for name in ("protocol.json", "rows.json", "report.json", "report.md", "run.json"):
        assert (rdir / name).exists()
    proto = FP.read_json(rdir / "protocol.json")
    assert (
        proto["conditions"] == C.conditions() and proto["code"]["base_commit"] == COMMIT
    )
    assert set(proto["code"]["sha256"]) == set(F.CODE_FILES)
    assert proto["inputs"]["predictions"]["sha256"] == world["spec"]["predictions"][1]
    assert res["meta"]["status"] == "OK" and res["meta"]["changed_code"] is None
    v = _verify(world)
    assert v["status"] == "OK" and v["run_status"] == "OK" and v["problems"] == []
    with pytest.raises(F.Refused):
        _run(world)


def test_precheck_failure_writes_no_run_folder(world) -> None:
    bad = {**world["spec"], "run": (world["spec"]["run"][0], "1" * 64)}
    with pytest.raises(F.CheckRequired):
        F.run(
            world["root"],
            REPO,
            world["clock"],
            spec=bad,
            expected=EXPECTED,
            inputs_root=world["repo"],
        )
    assert [p.name for p in world["root"].iterdir()] == [F.LOCK_NAME]  # 잠금 파일만


@pytest.mark.parametrize("exc", [RuntimeError, KeyboardInterrupt])
def test_failure_after_run_id_keeps_protocol_and_records(
    world, monkeypatch, exc
) -> None:
    def boom(table):
        raise exc("계산 중 실패")

    monkeypatch.setattr(F, "compute", boom)
    with pytest.raises(exc):
        _run(world)
    rdir = next(p for p in world["root"].iterdir() if p.is_dir())
    assert (rdir / "protocol.json").exists() and not (rdir / "rows.json").exists()
    meta = FP.read_json(rdir / "run.json")
    assert meta["status"] == "FAILED" and exc.__name__ in meta["reason"]
    assert _verify(world)["status"] == "RUN_FAILED"
    monkeypatch.undo()
    with pytest.raises(F.Refused):
        _run(world)
    again = _run(world, correction_reason="중단 뒤 같은 코드 재실행")
    assert again["meta"]["corrects"] == [rdir.name]
    assert again["meta"]["changed_code"]["files"] == []
    assert _verify(world)["status"] == "OK"


def test_correction_records_changed_code(world, monkeypatch) -> None:
    first = _run(world)["run_dir"]
    real = F.code_hashes
    monkeypatch.setattr(
        F,
        "code_hashes",
        lambda repo: {**real(repo), "app/review_priority/core.py": "0" * 64},
    )
    res = _run(world, correction_reason="core.py 결함 정정")
    assert res["meta"]["corrects"] == [first.name]
    assert res["meta"]["changed_code"]["files"] == ["app/review_priority/core.py"]
    assert _verify(world, run_id=first.name)["status"] == "OK"  # 이전 실행 보존


def test_busy(world) -> None:
    with F.run_lock(world["root"]):
        with pytest.raises(F.Busy):
            _run(world)


def _tamper(name, fn):
    def go(rdir):
        f = rdir / name
        d = FP.read_json(f)
        fn(d)
        f.write_bytes(FP.dumps(d))

    return go


def _first_selected(rows):
    r = next(r for r in rows["G_ALL"] if r["w"]["RIDGE_P"] > 0)
    r["w"]["RIDGE_P"] = 0.0


def _report_and_md_tampered(rdir):
    """보고서 판정을 바꾸고 글도 그에 맞춰 다시 써서 — 글 대조가 아닌 보고서 재계산이 잡아야 함."""
    f = rdir / "report.json"
    d = FP.read_json(f)
    d["scopes"]["G_ALL"]["judge"]["HGB_P"]["status"] = "X"
    f.write_bytes(FP.dumps(d))
    (rdir / "report.md").write_text(RP.markdown(FP.read_json(f)))


TAMPER = [
    (_tamper("rows.json", _first_selected), "rows.json"),
    (_report_and_md_tampered, "report.json ≠"),
    (lambda r: (r / "report.md").write_text("x"), "report.md"),
    (_tamper("protocol.json", lambda d: d["conditions"].update(k=5)), "조건"),
    (
        _tamper(
            "protocol.json",
            lambda d: d["inputs"]["predictions"].update(sha256="0" * 64),
        ),
        "입력 해시",
    ),
    (_tamper("run.json", lambda d: d.update(run_id="other")), "실행 ID"),
    (_tamper("run.json", lambda d: d.update(corrects=["x"])), "정정 관계"),
    (lambda r: (r / "protocol.json").write_bytes(FP.dumps([1, 2])), "형식 손상"),
]


def test_verify_detects_tampering(world, tmp_path) -> None:
    import shutil

    _run(world)
    for n, (fn, msg) in enumerate(TAMPER):
        copy = tmp_path / f"t{n}"
        shutil.copytree(world["root"], copy)
        rdir = next(p for p in copy.iterdir() if p.is_dir())
        fn(rdir)
        v = F.verify(copy, world["repo"], spec=world["spec"], expected=EXPECTED)
        assert v["status"] == "MISMATCH" and any(msg in p for p in v["problems"]), (
            n,
            v,
        )
    # 비유한 수 · 빠진 파일 = 확인 필요
    copy = tmp_path / "nf"
    shutil.copytree(world["root"], copy)
    rdir = next(p for p in copy.iterdir() if p.is_dir())
    text = (rdir / "rows.json").read_text().replace('"truth":', '"truth":1e999,"z":', 1)
    (rdir / "rows.json").write_text(text)
    v = F.verify(copy, world["repo"], spec=world["spec"], expected=EXPECTED)
    assert v["status"] == "CHECK_REQUIRED" and "rows.json" in v["problems"][0]
    # 입력이 바뀌면(해시 다름) 다시 계산할 수 없음 = 확인 필요
    f = world["repo"] / world["spec"]["predictions"][0]
    f.write_bytes(f.read_bytes() + b" ")
    assert _verify(world)["status"] == "CHECK_REQUIRED"


def test_cli_run_refuse_verify(world, monkeypatch, capsys) -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "run_review_priority_cli", REPO / "scripts" / "run_review_priority.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "REPO", world["repo"])
    monkeypatch.setattr(mod.F, "ROOT", world["root"])
    monkeypatch.setattr(mod.F, "SPEC", world["spec"])
    monkeypatch.setattr(mod.F, "EXPECTED", EXPECTED)
    monkeypatch.setattr(
        mod.F, "code_hashes", lambda repo: {f: "0" * 64 for f in F.CODE_FILES}
    )
    assert mod.main(["run"]) == 0
    out = capsys.readouterr().out.strip().splitlines()[-1]
    assert out.startswith("RESULT ") and json.loads(out[7:])["status"] == "OK"
    assert mod.main(["run"]) == 3
    assert mod.main(["verify"]) == 0


# ── 독립 검토 1회 반영(M1 · L2 ~ L9) ────────────────────────────────────────────


def _rd(rdir, name):
    return FP.read_json(rdir / name)


RECORD_TAMPER = [
    ("protocol.json", lambda d: d["scopes"].update(G_REVIEW=["111111"])),
    ("protocol.json", lambda d: d["expected"].update(rows=1)),
    ("protocol.json", lambda d: d["code"]["sha256"].update({F.CODE_FILES[0]: "x"})),
    ("protocol.json", lambda d: d["code"].update(base_commit="abc")),
    ("protocol.json", lambda d: d.update(protocol_id="other")),
    ("protocol.json", lambda d: d.pop("note")),
    ("run.json", lambda d: d.update(correction_reason="다른 사유")),
    ("run.json", lambda d: d.update(changed_code={"files": ["x"]})),
    ("run.json", lambda d: d.update(protocol_id="other")),
    ("run.json", lambda d: d.update(reason="성공인데 사유")),
]


def test_verify_checks_whole_protocol_and_run_record(world, tmp_path) -> None:
    """검토 M1 — protocol · run.json 을 고정 계약 · 같은 실행 기록으로 다시 만들어 통째로 대조."""
    import shutil

    _run(world, base_commit=COMMIT)
    for n, (name, fn) in enumerate(RECORD_TAMPER):
        copy = tmp_path / f"r{n}"
        shutil.copytree(world["root"], copy)
        rdir = next(p for p in copy.iterdir() if p.is_dir())
        _tamper(name, fn)(rdir)
        v = F.verify(copy, world["repo"], spec=world["spec"], expected=EXPECTED)
        assert v["status"] == "MISMATCH", (n, v)


def test_verify_checks_correction_chain_against_folders(world, tmp_path) -> None:
    """검토 L2 — 앞선 실행이 있는데 정정 관계가 비어 있는 '나중 폴더'는 같은 실행 기록이 아님."""
    import shutil

    first = _run(world)["run_dir"]
    later = world["root"] / "29991231T000000000000Z_deadbeef"
    shutil.copytree(first, later)
    for name in ("protocol.json", "run.json", "report.json"):
        _tamper(name, lambda d: d.update(run_id=later.name))(later)
    (later / "report.md").write_text(RP.markdown(FP.read_json(later / "report.json")))
    v = _verify(world)  # 기본 = 마지막 폴더 = later · 다른 것은 같고 정정 관계만 빔
    assert v["run_id"] == later.name and v["status"] == "MISMATCH"
    assert _verify(world, run_id=first.name)["status"] == "OK"


def test_clock_behind_previous_run_is_check_required(world) -> None:
    """검토 L4 — 이전 실행보다 이르거나 같은 시각이면 실행 순서를 보장할 수 없어 멈춤(폴더 없음)."""
    _run(world)
    before = sorted(p.name for p in world["root"].iterdir())
    back = iter([datetime(2026, 10, 25, 9, 0, 0, tzinfo=timezone.utc)]).__next__
    with pytest.raises(F.CheckRequired, match="시계"):
        F.run(
            world["root"],
            REPO,
            back,
            correction_reason="정정",
            spec=world["spec"],
            expected=EXPECTED,
            inputs_root=world["repo"],
        )
    assert sorted(p.name for p in world["root"].iterdir()) == before


def test_failure_at_protocol_write_and_changed_code_fallback(
    world, monkeypatch
) -> None:
    """검토 L3 · L5 — protocol 쓰기 실패 = RUN_FAILED · 정정의 비교 기준 = protocol 이 있는 최근 시도."""
    first = _run(world)["run_dir"]
    real = FP.write_once

    def broken(path, data):
        if path.name == "protocol.json":
            raise OSError("disk full")
        return real(path, data)

    monkeypatch.setattr(FP, "write_once", broken)
    with pytest.raises(OSError):
        _run(world, correction_reason="정정 1")
    failed = sorted(p for p in world["root"].iterdir() if p.is_dir())[-1]
    assert not (failed / "protocol.json").exists()
    assert _rd(failed, "run.json")["status"] == "FAILED"
    assert _verify(world, run_id=failed.name)["status"] == "RUN_FAILED"
    monkeypatch.setattr(FP, "write_once", real)
    third = _run(world, correction_reason="정정 2")
    assert third["meta"]["corrects"] == [first.name, failed.name]
    assert (
        third["meta"]["changed_code"]["previous_run"] == first.name
    )  # protocol 있는 시도
    assert _verify(world)["status"] == "OK"
    # 앞선 protocol 의 코드 기록이 dict 가 아니어도 실패하지 않고 '없음 · 손상'
    _tamper("protocol.json", lambda d: d["code"].update(sha256=[1]))(first)
    got = F._changed_code(world["root"], [first.name], {"a": "0" * 64})
    assert got == {"previous_protocol": "없음 · 손상", "files": ["a"]}


def test_verify_survives_deep_nesting_and_missing_files(world) -> None:
    """검토 L6 · L8 — 깊은 중첩 · 빠진 파일 · 실행 없음 · 모르는 실행 ID 가 예외 없이 상태로."""
    assert _verify(world)["problems"] == ["실행 없음"]
    rdir = _run(world)["run_dir"]
    assert _verify(world, run_id="없는_실행")["status"] == "CHECK_REQUIRED"
    (rdir / "rows.json").write_text("[" * 100000 + "]" * 100000)
    v = _verify(world)
    assert v["status"] == "CHECK_REQUIRED" and "rows.json" in v["problems"][0]


def test_missing_report_md_is_mismatch(world) -> None:
    rdir = _run(world)["run_dir"]
    (rdir / "report.md").unlink()
    v = _verify(world)
    assert v["status"] == "MISMATCH" and any("report.md" in p for p in v["problems"])


def test_report_has_not_hit_best_baseline_per_ticker_and_limits(world) -> None:
    """검토 L7 — 1−P · 기준 중 최고 · 종목별 내역(행 · 큰 하락 · 선택 · 적중) · 한계 문구."""
    res = _run(world)
    rep = res["report"]
    md = (res["run_dir"] / "report.md").read_text()
    assert "1−P(미해당)" in md and "기준 중 최고 P" in md and "선택 · 적중" in md
    assert any("G_REVIEW 는 사전 고정 15종" in x for x in rep["limits"])
    pt = rep["scopes"]["G_REVIEW"]["per_ticker"]
    assert set(pt) == set(REVIEW) and all(e["rows"] == len(DATES) for e in pt.values())
    for scope in F.SCOPES:
        sm = rep["scopes"][scope]["summary"]
        for m in C.METHODS:
            sel = sum(
                e["methods"][m]["selected"]
                for e in rep["scopes"][scope]["per_ticker"].values()
            )
            hit = sum(
                e["methods"][m]["hit"]
                for e in rep["scopes"][scope]["per_ticker"].values()
            )
            assert sel == pytest.approx(3 * len(DATES)) and hit == pytest.approx(
                sm[m]["all"]["TP"]
            )


@pytest.mark.parametrize(
    "fold_of, enough",
    [
        (lambda j: 0 if j < 5 else 1 if j < 10 else 2, True),  # 구간 1 · 2 정확히 5
        (lambda j: 0 if j < 4 else 1 if j < 10 else 2, False),  # 구간 1 = 4
    ],
)
def test_sample_exact_minimums(fold_of, enough) -> None:
    """검토 L8 — 정확히 20 날짜 · 정확히 5 날짜(≥ 경계)."""
    s = C.sample(_tail_days(20, "abc", fold_of=fold_of))
    assert s["tail_dates"] == 20 and s["enough"] is enough


def test_scope_lists_must_match_fixed_ranges(world) -> None:
    """검토 L9 — G_REVIEW ⊂ 적격 · 중복 없음 · 고정 크기."""
    for change in (
        lambda d: d["protocol"]["plan"].update(review=REVIEW[:3] + ["999999"]),
        lambda d: d["protocol"]["plan"].update(eligible=TICKERS[:5] + [TICKERS[0]]),
    ):
        data = json.loads(json.dumps(world["data"]))
        change(data)
        spec = _write(world["repo"], data)
        with pytest.raises(F.CheckRequired, match="범위"):
            F.build_table(F.read_inputs(world["repo"], spec), EXPECTED)
