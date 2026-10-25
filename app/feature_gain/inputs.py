"""POC6-08 — 입력 검증 · 연구 축 · 종목별 행 · 구간 · 적격 · 가용(설계 §2 · §3 · §5 · PLAN §2 · §3).

```text
입력   cohort.json · 06 초기 가격 사본 · 03 사본의 069500 · 05 묶음 축 object — 완전한 sha256 대조 ·
       하나라도 다르거나 못 읽으면 CheckRequired(결측으로 숨기지 않음) · 원본은 읽기만
축     06 `research_axis`(05 KOSPI 저장일 + 거래일 파일) · T = 상한 · 24종 끝 · 069500 끝 중 이른 날 이하의
       마지막 축 날짜 · anchor = T 의 축 20거래일 전 · 마지막 189 축 날짜 = 63 × 3 구간
기본 행 06 `AxisSeries.window_ok(i-60, i+20)` 통과(P 5열 · D20 유효) · 학습 = 목표 끝 axis[i+20] < 시험 시작
V      POC5-09 `compute_stored_volume_evidence`(축 날짜 i..i-20 의 사본 거래량 · 반올림 전 배수)
R      종목 · 069500 각각 window_ok(i-20, i) · [C(i)/C(i-20)-1] - [B(i)/B(i-20)-1]
```
"""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from app.feature_gain import protocol as P
from app.ml_evidence import store
from app.reentry_review import model as m06
from app.reentry_review import prices as px
from app.stored_volume_evidence import compute_stored_volume_evidence

LB, H = m06.LB, m06.H  # 60 · 20
ROW_FORMAT = ("date", "open", "high", "low", "close", "volume", "change")
BEFORE_FIRST_ROW = (
    "BEFORE_FIRST_ROW"  # 창 시작이 그 종목 첫 저장 행보다 앞(상장 전 · 사본 시작 전)
)
CAUSE_TEXT = {
    BEFORE_FIRST_ROW: "상장 전(첫 저장 행 이전)",
    **{k: f"중간 · {v}" for k, v in px.REASON_TEXT.items()},
}


@dataclass
class Inputs:
    cohort: list[str]
    review_out: tuple[str, ...]
    prices: dict[
        str, dict
    ]  # ticker → {observed_at, rows[date, open, high, low, close, volume, change]}
    bench_rows: list[tuple]  # (date, close, source, fetched_at, change) 오름차순
    kospi_dates: list[str]
    calendar_dir: Path
    refs: dict[str, Any] = field(default_factory=dict)


def _sha_file(path: Path, expected: str, label: str) -> bytes:
    try:
        data = Path(path).read_bytes()
    except OSError as e:
        raise P.CheckRequired(f"{label} 읽기 실패: {type(e).__name__}") from e
    if store.sha256_bytes(data) != expected:
        raise P.CheckRequired(f"{label} 해시가 고정 값과 다름")
    return data


def load(repo: Path, evidence_root: Path, tmp_dir: Path) -> Inputs:
    """고정 입력을 읽고 모두 대조한다(판정 §1 · 완전한 해시)."""
    repo = Path(repo)
    try:
        cohort_doc = json.loads(_sha_file(repo / P.COHORT_PATH, P.COHORT_SHA, "cohort"))
        prices = json.loads(_sha_file(repo / P.PRICES_PATH, P.PRICES_SHA, "가격 사본"))
        _sha_file(repo / P.BENCH_PATH, P.BENCH_SHA, "069500 사본")
        con = sqlite3.connect(
            f"{(repo / P.BENCH_PATH).resolve().as_uri()}?mode=ro", uri=True
        )
        try:
            bench_rows = con.execute(
                "SELECT date, close, source, fetched_at, change FROM prices "
                "WHERE ticker = ? ORDER BY date",
                (P.BENCH,),
            ).fetchall()
        finally:
            con.close()
        runs, _ = store.list_runs(Path(evidence_root))
        run = next((r for r in runs if r.run_id == P.AXIS_RUN), None)
        if run is None:
            raise P.CheckRequired(f"축 묶음 {P.AXIS_RUN} 없음")
        da = run.manifest["sources"]["date_axis"]
        files = tuple((f["name"], f["sha256"]) for f in da.get("calendar_files") or [])
        if da["kospi_stored_dates"]["object"] != P.AXIS_KOSPI_OBJECT:
            raise P.CheckRequired("축 KOSPI 저장일 object 가 고정 값과 다름")
        if files != P.AXIS_CALENDAR_FILES:
            raise P.CheckRequired("축 거래일 파일이 고정 값과 다름")
        kospi = json.loads(store.read_object(Path(evidence_root), P.AXIS_KOSPI_OBJECT))
        cal = Path(tmp_dir)
        cal.mkdir(parents=True, exist_ok=True)
        for name, sha in files:
            (cal / name).write_bytes(store.read_object(Path(evidence_root), sha))
        kospi_dates = list(kospi["dates"])
        selected = sorted(cohort_doc["selected"], key=lambda x: x["rank"])
        cohort = [x["ticker"] for x in selected]
        groups = cohort_doc.get("aux_groups") or {}
        review_out = tuple(groups.get("bond_cash_mixed_5", [])) + tuple(
            groups.get("inverse_2", [])
        )
        if sorted(review_out) != sorted(P.REVIEW_OUT) or len(cohort) != 24:
            raise P.CheckRequired("cohort 명단 · 보조 범위 7종이 설계와 다름")
        if prices.get("row_format") != list(ROW_FORMAT) or set(
            prices.get("tickers", {})
        ) != set(cohort):
            raise P.CheckRequired("가격 사본 형식 · 종목이 기대와 다름")
        if not bench_rows:
            raise P.CheckRequired("069500 행 없음")
    except P.CheckRequired:
        raise
    except store.EvidenceError as e:
        raise P.CheckRequired(f"05 object 손상: {e}") from e
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        IndexError,
        sqlite3.Error,
    ) as e:
        raise P.CheckRequired(f"입력 읽기 실패: {type(e).__name__}: {e}"[:200]) from e
    return Inputs(
        cohort=cohort,
        review_out=P.REVIEW_OUT,
        prices=prices["tickers"],
        bench_rows=[tuple(r) for r in bench_rows],
        kospi_dates=kospi_dates,
        calendar_dir=cal,
        refs={
            "cohort": {"path": P.COHORT_PATH.as_posix(), "sha256": P.COHORT_SHA},
            "prices": {"path": P.PRICES_PATH.as_posix(), "sha256": P.PRICES_SHA},
            "bench": {
                "path": P.BENCH_PATH.as_posix(),
                "sha256": P.BENCH_SHA,
                "ticker": P.BENCH,
            },
            "axis": {
                "run": P.AXIS_RUN,
                "kospi_object": P.AXIS_KOSPI_OBJECT,
                "calendar_files": [list(f) for f in P.AXIS_CALENDAR_FILES],
            },
        },
    )


# ── 축 · 계열 ──────────────────────────────────────────────────────────────────


def build_axis(inp: Inputs) -> dict[str, Any]:
    last24 = max(body["rows"][-1][0] for body in inp.prices.values())
    limit = min(P.CAP, last24, inp.bench_rows[-1][0])
    first = inp.kospi_dates[0]
    ax = px.research_axis(limit, first, inp.kospi_dates, calendar_dir=inp.calendar_dir)
    T = ax["dates"][-1] if ax["dates"] else None
    if T is None:
        raise P.CheckRequired("연구 축이 비었음")
    if T != limit:
        ax = px.research_axis(T, first, inp.kospi_dates, calendar_dir=inp.calendar_dir)
    problem = px.axis_problem(T, ax)
    if problem:
        raise P.CheckRequired(f"연구 축 문제: {problem}")
    return {"limit": limit, "last24": last24, "T": T, **ax}


@dataclass
class Series:
    ticker: str
    s: px.AxisSeries
    volume: list[Any]  # 축 위치별 사본 거래량(행 없으면 None)


def build_series(inp: Inputs, dates: list[str]) -> tuple[dict[str, Series], Any]:
    """종목마다 따로 만든다(한 종목 자료가 다른 종목에 섞이지 않게 · 판정 §4)."""
    pos = {d: i for i, d in enumerate(dates)}
    out: dict[str, Series] = {}
    for t in inp.cohort:
        body = inp.prices[t]
        rows = body["rows"]
        s = px.AxisSeries(
            dates,
            [
                px.PriceRow(r[0], r[4], P.SOURCE, body["observed_at"], r[6])
                for r in rows
            ],
        )
        vol: list[Any] = [None] * len(dates)
        for r in rows:
            j = pos.get(r[0])
            if j is not None:
                vol[j] = r[5]
        out[t] = Series(t, s, vol)
    bench = px.AxisSeries(dates, [px.PriceRow(*r) for r in inp.bench_rows])
    return out, bench


def volume_ratio(
    ser: Series, dates: list[str], i: int
) -> tuple[Optional[float], Optional[str]]:
    """V(t) = 축 날짜 i 거래량 ÷ 축 날짜 i-20..i-1 평균(POC5-09 함수 · 반올림 전)."""
    if i - 20 < 0:
        return None, "date_short"
    desc = [(dates[j], None, ser.volume[j], P.SOURCE) for j in range(i, i - 21, -1)]
    ev = compute_stored_volume_evidence(ser.ticker, desc)
    if ev.ratio_status != "ok" or ev.ratio is None:
        return None, ev.ratio_status
    if not math.isfinite(ev.ratio):
        return None, "not_finite"
    return float(ev.ratio), None


def relative_return(
    ser: Series, bench: Any, i: int
) -> tuple[Optional[float], Optional[str]]:
    """R(t) = 종목 20축 변화 - 069500 20축 변화(같은 시작 · 끝 축 날짜 · 소수)."""
    if i - 20 < 0 or not ser.s.window_ok(i - 20, i):
        return None, "ticker_window"
    if not bench.window_ok(i - 20, i):
        return None, "bench_window"
    c, b = ser.s.closes, bench.closes
    value = (c[i] / c[i - 20] - 1.0) - (b[i] / b[i - 20] - 1.0)
    if not math.isfinite(value):
        return None, "not_finite"
    return value, None


# ── 구간 · 적격 · 가용 ─────────────────────────────────────────────────────────


def fold_positions(dates: list[str]) -> dict[str, Any]:
    iT = len(dates) - 1
    anchor = iT - P.TARGET_GAP
    start = anchor - P.FOLDS * P.FOLD_LEN + 1
    if start - H < LB:
        raise P.CheckRequired("연구 축이 짧아 구간을 만들 수 없음")
    folds = [
        list(range(start + k * P.FOLD_LEN, start + (k + 1) * P.FOLD_LEN))
        for k in range(P.FOLDS)
    ]
    return {"T_index": iT, "anchor_index": anchor, "folds": folds}


def base_ok(ser: Series, i: int, n: int) -> bool:
    return LB <= i < n - H and ser.s.window_ok(i - LB, i + H)


def plan(inp: Inputs, ax: dict[str, Any]) -> dict[str, Any]:
    """lock 이 고정하는 것 — 행 식별자 · 유효성 · 기간 · 분모 · 가용(목표 크기 · 오차는 보지 않음)."""
    dates = ax["dates"]
    n = len(dates)
    fp = fold_positions(dates)
    series, bench = build_series(inp, dates)
    per: dict[str, Any] = {}
    train_ids: list[list[list[str]]] = [[] for _ in range(P.FOLDS)]
    test_ids: list[list[list[str]]] = [[] for _ in range(P.FOLDS)]
    eligible: list[str] = []
    for t in inp.cohort:
        ser = series[t]
        tr = [
            [i for i in range(LB, f[0]) if i + H < f[0] and base_ok(ser, i, n)]
            for f in fp["folds"]
        ]
        te = [[i for i in f if base_ok(ser, i, n)] for f in fp["folds"]]
        first = inp.prices[t]["rows"][0][0]
        reasons: dict[str, int] = {}
        causes: dict[str, int] = (
            {}
        )  # 상장 전 / 중간 공백 · 가격 기준 · 비정상 종가 구분(설계 §2-2)
        for i in range(LB, fp["anchor_index"] + 1):
            r = ser.s.window_reason(i - LB, i + H)
            if r:
                reasons[r] = reasons.get(r, 0) + 1
                c = BEFORE_FIRST_ROW if dates[i - LB] < first else r
                causes[c] = causes.get(c, 0) + 1
        ok = all(len(x) >= P.MIN_TRAIN for x in tr) and all(
            len(x) >= P.MIN_TEST for x in te
        )
        per[t] = {
            "first_row": first,
            "train": [len(x) for x in tr],
            "test": [len(x) for x in te],
            "eligible": ok,
            "reason": None if ok else _ineligible_text(tr, te, causes),
            "excluded_by_reason": reasons,
            "excluded_by_cause": causes,
        }
        if ok:
            eligible.append(t)
            for k in range(P.FOLDS):
                train_ids[k] += [[t, dates[i]] for i in tr[k]]
                test_ids[k] += [[t, dates[i]] for i in te[k]]
            per[t]["_positions"] = (tr, te)
    review = [t for t in eligible if t not in inp.review_out]
    cov = coverage(series, bench, dates, per, eligible, review)
    for t in per:
        per[t].pop("_positions", None)
    folds_out = [
        {
            "test": [dates[f[0]], dates[f[-1]]],
            "target_end": [dates[f[0] + H], dates[f[-1] + H]],
            "train_target_end_before": dates[f[0]],
        }
        for f in fp["folds"]
    ]
    return {
        "T": ax["T"],
        "limit_inputs": {
            "cap": P.CAP,
            "last24": ax["last24"],
            "bench_end": inp.bench_rows[-1][0],
        },
        "axis": {
            "first": dates[0],
            "last": dates[-1],
            "length": n,
            "modes": ax.get("modes"),
        },
        "anchor": dates[fp["anchor_index"]],
        "folds": folds_out,
        "per_ticker": per,
        "eligible": eligible,
        "review": review,
        "train_rows": [len(x) for x in train_ids],
        "test_rows": {
            "G_ALL": [len(x) for x in test_ids],
            "G_REVIEW": [
                sum(1 for tk, _ in test_ids[k] if tk in set(review))
                for k in range(P.FOLDS)
            ],
        },
        "ids_sha256": {
            "train": [store.sha256_bytes(store.canonical(x)) for x in train_ids],
            "test": [store.sha256_bytes(store.canonical(x)) for x in test_ids],
        },
        "coverage": cov,
    }


def _ineligible_text(tr, te, causes: dict[str, int]) -> str:
    short = [
        f"{k + 1}구간 학습 {len(x)}<{P.MIN_TRAIN}"
        for k, x in enumerate(tr)
        if len(x) < P.MIN_TRAIN
    ] + [
        f"{k + 1}구간 시험 {len(x)}<{P.MIN_TEST}"
        for k, x in enumerate(te)
        if len(x) < P.MIN_TEST
    ]
    why = " · ".join(f"{CAUSE_TEXT.get(c, c)} {n}" for c, n in sorted(causes.items()))
    return f"{' · '.join(short)} — 제외 창 원인: {why or '없음'}"


def coverage(series, bench, dates, per, eligible, review) -> dict[str, Any]:
    """후보 · 범위 · 구간별 추가 열 유효 비율(학습 = G_ALL 공동 · 시험 = 그 범위) · 5종 · 80%."""
    v_ok: dict[tuple[str, int], bool] = {}
    r_ok: dict[tuple[str, int], bool] = {}

    def ok(t: str, i: int, need: tuple[str, ...]) -> bool:
        key = (t, i)
        if key not in v_ok:
            v_ok[key] = volume_ratio(series[t], dates, i)[0] is not None
            r_ok[key] = relative_return(series[t], bench, i)[0] is not None
        return all(v_ok[key] if x == "V" else r_ok[key] for x in need)

    out: dict[str, Any] = {}
    for cand in P.CANDIDATES:
        need = P.EXTRA[cand]
        out[cand] = {}
        for scope, members in (("G_ALL", eligible), ("G_REVIEW", review)):
            folds = []
            for k in range(P.FOLDS):
                tr = [(t, i) for t in eligible for i in per[t]["_positions"][0][k]]
                te = [(t, i) for t in members for i in per[t]["_positions"][1][k]]
                tr_ok = sum(1 for t, i in tr if ok(t, i, need))
                te_ok = sum(1 for t, i in te if ok(t, i, need))
                folds.append(
                    {
                        "train": [tr_ok, len(tr)],
                        "test": [te_ok, len(te)],
                        "pass": bool(tr)
                        and bool(te)
                        and tr_ok / len(tr) >= P.COVERAGE
                        and te_ok / len(te) >= P.COVERAGE,
                    }
                )
            enough = len(members) >= P.MIN_ELIGIBLE
            out[cand][scope] = {
                "folds": folds,
                "eligible": len(members),
                "status": (
                    "OK" if enough and all(f["pass"] for f in folds) else "DATA_SHORT"
                ),
            }
    return out


def check_expected(pl: dict[str, Any], expected: Optional[dict[str, Any]]) -> list[str]:
    """PLAN §2 표와 08 구현의 재계산 대조(판정 §4) — 다른 칸 목록(비면 같음)."""
    if expected is None:
        return []
    diffs = []
    per = pl["per_ticker"]
    cov = [
        (scope, k, f)
        for c in P.CANDIDATES
        for scope, v in pl["coverage"][c].items()
        for k, f in enumerate(v["folds"])
    ]
    got = {
        "T": pl["T"],
        "anchor": pl["anchor"],
        "folds": [f["test"] for f in pl["folds"]],
        "eligible": sorted(pl["eligible"]),
        "train_rows": pl["train_rows"],
        "test_rows": pl["test_rows"],
        "excluded_fold1_train": {
            t: v["train"][0] for t, v in per.items() if not v["eligible"]
        },
        # 적격 종목 모두 같은 값이면 그 값 · 다르면 종목별(어긋남이 드러나게)
        "eligible_test_dates": _same_or_all(
            {t: per[t]["test"] for t in pl["eligible"]}
        ),
        "exclusion_causes": sorted(
            {c for v in per.values() for c in v["excluded_by_cause"]}
        ),
        "coverage_missing": sum(
            (f["train"][1] - f["train"][0]) + (f["test"][1] - f["test"][0])
            for _, _, f in cov
        ),
        "coverage_denominators_match": all(
            f["train"][1] == pl["train_rows"][k]
            and f["test"][1] == pl["test_rows"][scope][k]
            for scope, k, f in cov
        ),
    }
    for k, v in expected.items():
        want = sorted(v) if k in ("eligible", "exclusion_causes") else v
        if k not in got:
            diffs.append(f"{k}: 재계산 항목 없음")
        elif got[k] != want:
            diffs.append(f"{k}: PLAN {want} ≠ 재계산 {got[k]}")
    return diffs


def _same_or_all(by: dict[str, list[int]]) -> Any:
    vals = {tuple(v) for v in by.values()}
    return list(vals.pop()) if len(vals) == 1 else by


def examples(inp: Inputs, ax: dict[str, Any], pl: dict[str, Any]) -> dict[str, Any]:
    """run 의 실제 X · y — 적격 종목의 기본 행 전부(구간마다 쓰는 행은 날짜 경계로 고른다)."""
    dates = ax["dates"]
    n = len(dates)
    fp = fold_positions(dates)
    series, bench = build_series(inp, dates)
    last_test = fp["folds"][-1][-1]
    rows: list[dict[str, Any]] = []
    for t in pl["eligible"]:
        ser = series[t]
        # 마지막 시험 날짜 이하의 기본 행 전부 — 구간마다 학습(목표 끝 < 시험 시작) · 시험 위치를 고른다.
        for i in range(LB, last_test + 1):
            if not base_ok(ser, i, n):
                continue
            v, vr = volume_ratio(ser, dates, i)
            r, rr = relative_return(ser, bench, i)
            rows.append(
                {
                    "ticker": t,
                    "date": dates[i],
                    "i": i,
                    "target_end": dates[i + H],
                    "p": m06.features_at(ser.s.closes, i),
                    "v": v,
                    "v_reason": vr,
                    "r": r,
                    "r_reason": rr,
                    "y": m06.target_at(ser.s.closes, i),
                }
            )
    return {"rows": rows, "folds": fp["folds"], "dates_index": {"n": n}}
