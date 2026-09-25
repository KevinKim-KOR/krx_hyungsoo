"""POC4-02B — 신호별 지표 · 판정 1~10 · 변형(2026 제외 · 사건/연도 하나 빼기) · 결과 payload (PLAN §5 · §7 · §8).

판정(설계자 판정 §7 · 구현 정의 5·7·8) — 1~7 은 PIT 로 판정하고 FS 는 나란히 적기만 한다. 8 = 1~7(PIT) ·
9 = 2026 제외 변형의 핵심 {1·2·5} · 10 = 모든 사건 하나 빼기·연도 하나 빼기 변형의 핵심 · 11 = 두 실행 canonical
동일(러너 `compare` 가 따로 기록 — 이 payload 에서는 null). 조건 값은 true / false / null(계산 불가).
1~10 에 false 가 하나라도 있으면 REJECT · 없고 null 이 있으면 INCONCLUSIVE(→ CLOSED) ·
모두 true 면 PASS_CANDIDATE_PENDING_DETERMINISM. `TRACK_B_PASS != PUSH_ACTIVATION`.

진단(EXACT_K · LEGACY_FULL_SAMPLE)은 LOOKAHEAD=true 로 같은 지표만 적고 판정에 쓰지 않는다.
"""

from __future__ import annotations

from collections import Counter
from typing import Optional, Sequence

from app import ml_ew_events as ev
from app import ml_ew_market_axes as mx
from app import ml_ew_signals as sg
from app.krx_sealed_reader import PRICE_BASIS
from app.ml_score_validity_report import NON_DETERMINISTIC_FIELDS, canonical_sha256

SCHEMA = "poc4_02b_early_warning.v1"
TRACK = "POC4-02B"
REJECT = "REJECT"
INCONCLUSIVE = "INCONCLUSIVE"
PENDING = "PASS_CANDIDATE_PENDING_DETERMINISM"
PASS_CANDIDATE = "PASS_CANDIDATE"
CORE = ("1", "2", "5")
EXCLUDED_YEAR = "2026"
TRACK_B_NOTE = "TRACK_B_PASS != PUSH_ACTIVATION"
JUDGED = (sg.EARLY_PIT, sg.REACTIVE)


# --- 평가 맥락 ------------------------------------------------------------------------


def context(
    events: list[dict],
    dates: Sequence[str],
    d0: Optional[int],
    range_end: Optional[int],
    *,
    drop_events: frozenset = frozenset(),
    drop_year: Optional[str] = None,
) -> dict:
    """경보 평가 구간 · 평가 사건 · 창 마스크. 뺀 사건의 창은 EXCLUDED 로 둔다."""
    n = len(dates)
    lo_ok = d0 is not None and range_end is not None and d0 <= range_end
    included = [
        lo_ok and d0 <= i <= range_end and dates[i][:4] != drop_year for i in range(n)
    ]
    evaluable = [
        e
        for e in events
        if e["status"] == ev.EVALUABLE and e["event_id"] not in drop_events
    ]
    kept = {e["event_id"] for e in evaluable}
    excluded = [e for e in events if e["event_id"] not in kept]
    return {
        "included": included,
        "evaluable": evaluable,
        "eval_mask": ev.window_mask(
            n, [ev.event_window(e, range_end) for e in evaluable]
        ),
        "excl_mask": ev.window_mask(
            n, [ev.event_window(e, range_end) for e in excluded]
        ),
    }


def _year_of(event: dict, dates: Sequence[str]) -> str:
    return dates[event["peak"]][:4]


def masked(raw: Sequence[Optional[bool]], included: Sequence[bool]) -> list[bool]:
    """평가 구간 밖 · 판정 불가(None) 는 경보 아님."""
    return [bool(a) and inc for a, inc in zip(raw, included)]


def evaluate(raw: Sequence[Optional[bool]], ctx: dict) -> dict:
    alerts = masked(raw, ctx["included"])
    range_days = sum(ctx["included"])
    alert_days = sum(alerts)
    return {
        "range_days": range_days,
        "alert_days": alert_days,
        "alert_rate": alert_days / range_days if range_days else None,
        "undefined_alert_days": sum(
            1 for a, inc in zip(raw, ctx["included"]) if inc and a is None
        ),
        "runs": ev.run_summary(alerts, ctx["eval_mask"], ctx["excl_mask"]),
        "events": ev.event_summary(alerts, ctx["evaluable"]),
    }


# --- 판정 -------------------------------------------------------------------------------


def _cmp(a, b, op: str) -> Optional[bool]:
    if a is None or b is None:
        return None
    return {">": a > b, ">=": a >= b, "<": a < b, "<=": a <= b}[op]


def all_of(values: Sequence[Optional[bool]]) -> Optional[bool]:
    """false 가 하나라도 → false · 아니면 null 이 있으면 null · 비어 있으면 null."""
    if any(v is False for v in values):
        return False
    if not values or any(v is None for v in values):
        return None
    return True


def core(early: dict, reactive: dict) -> dict:
    e, r = early["events"], reactive["events"]
    has = e["evaluable_events"] > 0
    return {
        "1": _cmp(e["lead_median"], r["lead_median"], ">"),
        "2": _cmp(e["pre_capture"], r["pre_capture"], ">=") if has else None,
        "5": _cmp(
            early["runs"]["run_precision"], reactive["runs"]["run_precision"], ">"
        ),
    }


def criteria_1_7(early: dict, reactive: dict, null: dict) -> dict:
    e, r = early["events"], reactive["events"]
    er, rr = early["runs"], reactive["runs"]
    has = e["evaluable_events"] > 0
    rows = {
        "1": ("lead_median", e["lead_median"], r["lead_median"], ">"),
        "2": ("pre_capture", e["pre_capture"], r["pre_capture"], ">="),
        "3": ("severe_missed", e["severe_missed"], r["severe_missed"], "<="),
        "4": ("pre_share", e["pre_share"], r["pre_share"], ">"),
        "5": ("run_precision", er["run_precision"], rr["run_precision"], ">"),
        "6": (
            "fa_runs_per_100_alerts",
            er["fa_runs_per_100_alerts"],
            rr["fa_runs_per_100_alerts"],
            "<",
        ),
    }
    out = {}
    for key, (metric, a, b, op) in rows.items():
        value = _cmp(a, b, op)
        if key in ("2", "3") and not has:
            value = None
        out[key] = {
            "metric": metric,
            "op": op,
            "early": a,
            "reactive": b,
            "value": value,
        }
    out["7"] = {
        "metric": "run_precision_vs_random_null_p95",
        "op": ">",
        "early": er["run_precision"],
        "random_null_p95": null.get("p95"),
        "value": _cmp(er["run_precision"], null.get("p95"), ">"),
    }
    return out


def verdict(values: Sequence[Optional[bool]]) -> str:
    if any(v is False for v in values):
        return REJECT
    if any(v is None for v in values):
        return INCONCLUSIVE
    return PENDING


# --- 변형 -------------------------------------------------------------------------------


def _compact(m: dict) -> dict:
    e, r = m["events"], m["runs"]
    keys = ("evaluable_events", "pre_capture", "post_only", "missed", "lead_median")
    return {
        **{k: e[k] for k in keys},
        "run_precision": r["run_precision"],
        "runs_true": r["runs_true"],
        "runs_false": r["runs_false"],
        "alert_days": m["alert_days"],
        "range_days": m["range_days"],
    }


def _variant(name: str, alerts: dict, events, dates, d0, range_end, **drop) -> dict:
    ctx = context(events, dates, d0, range_end, **drop)
    got = {s: evaluate(alerts[s], ctx) for s in JUDGED}
    c = core(got[sg.EARLY_PIT], got[sg.REACTIVE])
    return {
        "name": name,
        "dropped_events": sorted(drop.get("drop_events", ())),
        "dropped_year": drop.get("drop_year"),
        **{s: _compact(got[s]) for s in JUDGED},
        "core": c,
        "core_holds": all_of(list(c.values())),
    }


def variants(alerts: dict, events: list[dict], dates, d0, range_end) -> dict:
    """2026 제외 · 평가 사건 하나 빼기 · 평가 사건이 있는 연도 하나 빼기 (사건 연도 = P 의 연도)."""
    evaluable = [e for e in events if e["status"] == ev.EVALUABLE]

    def by_year(year: str) -> frozenset:
        return frozenset(e["event_id"] for e in evaluable if _year_of(e, dates) == year)

    def one(name: str, **drop) -> dict:
        return _variant(name, alerts, events, dates, d0, range_end, **drop)

    years = sorted({_year_of(e, dates) for e in evaluable})
    return {
        "exclude_2026": one(
            "EXCLUDE_2026", drop_events=by_year(EXCLUDED_YEAR), drop_year=EXCLUDED_YEAR
        ),
        "leave_one_event_out": [
            one(f"LEAVE_EVENT_{e['event_id']}", drop_events=frozenset({e["event_id"]}))
            for e in evaluable
        ],
        "leave_one_year_out": [
            one(f"LEAVE_YEAR_{y}", drop_events=by_year(y), drop_year=y) for y in years
        ],
    }


# --- 표 ---------------------------------------------------------------------------------


def _date(dates: Sequence[str], i: Optional[int]) -> Optional[str]:
    return dates[i] if i is not None and 0 <= i < len(dates) else None


def events_table(events: list[dict], dates, range_end, severe_ids) -> list[dict]:
    out = []
    for e in events:
        lo, hi = ev.event_window(e, range_end)
        out.append(
            {
                "event_id": e["event_id"],
                "status": e["status"],
                "reason": None if e["status"] == ev.EVALUABLE else e["status"],
                "right_censored": e["right_censored"],
                "pre_window_unavailable": e["pre_window_unavailable"],
                **{
                    k: _date(dates, e[k])
                    for k in ("first", "last", "peak", "trough", "breach")
                },
                "label_days": e["label_days"],
                "depth": e["depth"],
                "severe": e["event_id"] in severe_ids,
                "window_start": _date(dates, max(lo, 0)),
                "window_end": _date(dates, min(hi, len(dates) - 1)),
            }
        )
    return out


def classification(metrics: dict, dates) -> dict:
    out = {}
    for sig, m in metrics.items():
        per = m["events"].pop("per_event")
        out[sig] = {
            eid: {**c, "first_alert": _date(dates, c["first_alert"])}
            for eid, c in per.items()
        }
    return out


def yearly(alerts: dict, ctx: dict, dates, classes: dict) -> list[dict]:
    rows = []
    years = sorted({dates[i][:4] for i, inc in enumerate(ctx["included"]) if inc})
    for y in years:
        idx = [i for i, inc in enumerate(ctx["included"]) if inc and dates[i][:4] == y]
        ev_ids = [
            str(e["event_id"]) for e in ctx["evaluable"] if _year_of(e, dates) == y
        ]
        row: dict = {"year": y, "range_days": len(idx), "evaluable_events": len(ev_ids)}
        for sig, raw in alerts.items():
            days = sum(1 for i in idx if raw[i])
            cls = [classes[sig][k]["class"] for k in ev_ids]
            row[sig] = {
                "alert_days": days,
                "alert_rate": days / len(idx) if idx else None,
                **{c: cls.count(c) for c in (ev.PRE, ev.POST, ev.MISSED)},
            }
        rows.append(row)
    return rows


# --- 단계 · payload -----------------------------------------------------------------------


def build_null_stage(axes: dict, signals: dict, ev_stage: dict) -> dict:
    dates = axes["dates"]
    d0, end = ev_stage["d0"], ev_stage["range_end"]
    ctx = context(ev_stage["events"], dates, d0, end)
    lo, hi = (d0, end) if any(ctx["included"]) else (None, None)
    return {
        sig: ev.random_null(
            masked(signals["alerts"][sig], ctx["included"]),
            dates,
            lo,
            hi,
            ctx["eval_mask"],
            ctx["excl_mask"],
        )
        for sig in (sg.EARLY_PIT, sg.EARLY_FS)
    }


def _calendar(dates, ev_stage: dict, signals: dict, ctx: dict) -> dict:
    d0, end = ev_stage["d0"], ev_stage["range_end"]
    first = {
        s: next((i for i, a in enumerate(signals["alerts"][s]) if a is not None), None)
        for s in sg.SIGNALS
    }
    return {
        "first_date": dates[0],
        "last_date": dates[-1],
        "trading_days": len(dates),
        "d0": _date(dates, d0),
        "d0_index": d0,
        "range_end": _date(dates, end),
        "range_end_index": end,
        "range_days": sum(ctx["included"]),
        "label_computable_days": sum(1 for v in ev_stage["dd10"] if v is not None),
        "label_days": len(ev_stage["label_days"]),
        "first_alert_defined": {s: _date(dates, i) for s, i in first.items()},
    }


def _diagnostics(signals: dict, ctx: dict, d0, end, dates) -> dict:
    scores = signals["scores"]
    out = {}
    ek = {}
    for sig in JUDGED:
        alerts, k = sg.exact_k_alerts(scores[sig], d0, end)
        m = evaluate(alerts, ctx)
        m["events"].pop("per_event")
        ek[sig] = {"k": k, **m}
    out["EXACT_K_DIAGNOSTIC"] = {"LOOKAHEAD": True, "judged": False, **ek}
    alerts, k = sg.legacy_top_third_alerts(signals["legacy_composite"], d0, end)
    m = evaluate(alerts, ctx)
    m["events"].pop("per_event")
    out["LEGACY_FULL_SAMPLE_DIAGNOSTIC"] = {
        "LOOKAHEAD": True,
        "judged": False,
        "universe": mx.VARIANT_ALL,
        "k": k,
        **m,
    }
    return out


def build_result(
    *,
    axes: dict,
    signals: dict,
    ev_stage: dict,
    null: dict,
    legacy: dict,
    source: dict,
    official: bool,
) -> dict:
    dates = axes["dates"]
    d0, end, events = ev_stage["d0"], ev_stage["range_end"], ev_stage["events"]
    ctx = context(events, dates, d0, end)
    alerts = signals["alerts"]
    metrics = {s: evaluate(alerts[s], ctx) for s in sg.SIGNALS}
    severe = set(metrics[sg.EARLY_PIT]["events"]["severe_events"])
    classes = classification(metrics, dates)
    pit = criteria_1_7(metrics[sg.EARLY_PIT], metrics[sg.REACTIVE], null[sg.EARLY_PIT])
    fs = criteria_1_7(metrics[sg.EARLY_FS], metrics[sg.REACTIVE], null[sg.EARLY_FS])
    var = variants(alerts, events, dates, d0, end)
    loo = var["leave_one_event_out"] + var["leave_one_year_out"]
    crit = dict(pit)
    crit["8"] = {"basis": "1~7 on PIT", "value": all_of([pit[k]["value"] for k in pit])}
    crit["9"] = {
        "basis": "core {1,2,5} excl-2026",
        "value": var["exclude_2026"]["core_holds"],
    }
    crit["10"] = {
        "basis": "core {1,2,5} in every leave-one-event/year-out",
        "variants": len(loo),
        "value": all_of([v["core_holds"] for v in loo]) if loo else None,
    }
    crit["11"] = {
        "basis": "two from-scratch runs canonical identical",
        "value": None,
        "note": "compare 단계가 determinism_compare.json 에 기록",
    }
    judged = [crit[str(k)]["value"] for k in range(1, 11)]
    status = dict(sorted(Counter(e["status"] for e in events).items()))
    payload = {
        "schema": SCHEMA,
        "track": TRACK,
        "official": official,
        "price_basis": PRICE_BASIS,
        "source": source,
        "legacy_reproduction": legacy,
        "calendar": _calendar(dates, ev_stage, signals, ctx),
        "event_contract": ev.config(),
        "signal_contract": sg.config(),
        "universe_axis_pit_minus_fs": mx.pit_minus_fs(axes),
        "universe": {
            "sizes_by_date": axes["universe_size"],
            "axes_config": mx.config(),
        },
        "events": {
            "count": len(events),
            "by_status": status,
            "table": events_table(events, dates, end, severe),
        },
        "metrics": metrics,
        "classification": classes,
        "random_null": null,
        "variants": var,
        "criteria": crit,
        "criteria_fs_record_only": fs,
        "verdict": verdict(judged),
        "verdict_rule": "false → REJECT · null → INCONCLUSIVE(→ CLOSED) · all true → pending 11",
        "diagnostics": _diagnostics(signals, ctx, d0, end, dates),
        "yearly": yearly(alerts, ctx, dates, classes),
        "purge_embargo": sg.PURGE_EMBARGO,
        "note": TRACK_B_NOTE,
        "determinism": {
            "excluded_fields": list(NON_DETERMINISTIC_FIELDS),
            "self_referential_field": "determinism.canonical_sha256",
            "canonical_sha256": None,
        },
    }
    payload["determinism"]["canonical_sha256"] = canonical_sha256(payload)
    return payload


def final_verdict(run_verdict: str, identical: bool) -> str:
    """조건 11 반영 — false 면 REJECT · pending + true 면 PASS_CANDIDATE · 그 밖은 실행 판정 그대로."""
    if not identical:
        return REJECT
    return PASS_CANDIDATE if run_verdict == PENDING else run_verdict
