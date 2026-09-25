"""POC4-02B — 하락 사건 · 포착 · 경보 run · RANDOM_NULL (PLAN §4 · §5 · 확정 B1·B5~B7·B12 · 구현 정의 1·3·4).

- K = 069500 연결 계열. dd10(t) = 기존 `app/ml_baseline_targets._kodex_future_drawdown` 을 **그대로** 불러
  `MarketSeries(kodex_close=K)` 로 계산한다. label 일 = dd10 ≤ −0.05 (t+10 이 있는 날만).
- 사건 = label 일을 날짜 순으로 놓고 앞 label 일과 간격 ≤ 9거래일이면 병합(정확히 10 이면 다른 사건).
  T = [F, Last+10] 최저(같으면 이른 날) · P = [F, T] 최고(같으면 이른 날) · depth = K_T / K_P − 1 ·
  B = [P, T] 에서 처음 K ≤ 0.95·K_P 인 날(없으면 None).
- RIGHT_CENSORED_EVENT: Last + 9 > label 계산 가능 마지막 날 · PRE_WINDOW_UNAVAILABLE: P − 10 < D_0.
  둘 다 주 판정에서 빼고 설명표에만 둔다. 제외 사건 창 = [P−10, T] · 잘린 사건은 관측 구간 전체
  [F−10, 구간 끝] (설계자 판정 §8 "precision … 에서 전부 제외").
- 분류 — PRE: [P−10, P−1] 에 경보 · POST: 그 없이 [P, T] 에 경보 · MISSED: 없음. 선행일 = P − 첫 경보일.
- 경보 run(평가 구간 안 연속 경보일) — TRUE: 평가 사건 창과 겹침 · EXCLUDED: 제외 사건 창과만 겹침 · FALSE: 나머지.
- RANDOM_NULL — 달력 연도별로 경보 0/1 열을 원형 이동(그해 run 길이 구성이 같은 오프셋만 · 최대 1,000번 ·
  없으면 이동 0) · `random.Random(20260925)` · 1,000회 · 같은 창으로 run precision 분포 · 95% 분위.
"""

from __future__ import annotations

import random
from typing import Optional, Sequence

from app.ml_baseline_targets import MarketSeries, _kodex_future_drawdown
from app.ml_ew_signals import (
    EARLY_PIT,
    REACTIVE,
    bracketed_percentile,
    first_defined,
)
from app.ml_score_validity_metrics import mean, median

LABEL_HORIZON = 10
LABEL_THRESHOLD = -0.05
MERGE_GAP = 9
PRE_WINDOW = 10
BREACH_RATIO = 0.95
SEVERE_PERCENTILE = 25.0
NULL_REPEATS = 1000
NULL_SEED = 20260925
NULL_MAX_DRAWS = 1000
NULL_PERCENTILE = 95.0

EVALUABLE = "EVALUABLE"
RIGHT_CENSORED_EVENT = "RIGHT_CENSORED_EVENT"
PRE_WINDOW_UNAVAILABLE = "PRE_WINDOW_UNAVAILABLE"
PRE, POST, MISSED = "PRE", "POST", "MISSED"
RUN_TRUE, RUN_FALSE, RUN_EXCLUDED = "TRUE", "FALSE", "EXCLUDED"


# --- label · 사건 -----------------------------------------------------------------


def future_drawdowns(dates: list[str], chain: list[float]) -> list[Optional[float]]:
    n = len(dates)
    market = MarketSeries(
        dates=list(dates),
        kodex_close=list(chain),
        down_ratio=[None] * n,
        index={d: i for i, d in enumerate(dates)},
    )
    return [_kodex_future_drawdown(market, i, LABEL_HORIZON) for i in range(n)]


def label_days(dd: Sequence[Optional[float]]) -> list[int]:
    return [i for i, v in enumerate(dd) if v is not None and v <= LABEL_THRESHOLD]


def last_computable(dd: Sequence[Optional[float]]) -> Optional[int]:
    got = [i for i, v in enumerate(dd) if v is not None]
    return got[-1] if got else None


def group_label_days(labels: Sequence[int], gap: int = MERGE_GAP) -> list[list[int]]:
    """label 일 index → 사건별 label 일 목록 (앞 label 일과 간격 ≤ gap 이면 같은 사건)."""
    groups: list[list[int]] = []
    for i in labels:
        if groups and i - groups[-1][-1] <= gap:
            groups[-1].append(i)
        else:
            groups.append([i])
    return groups


def build_events(
    chain: Sequence[float],
    dd: Sequence[Optional[float]],
    d0: Optional[int],
) -> list[dict]:
    """사건 목록 (index 기준). 상태: EVALUABLE / RIGHT_CENSORED_EVENT / PRE_WINDOW_UNAVAILABLE."""
    last_label = last_computable(dd)
    events: list[dict] = []
    for eid, days in enumerate(group_label_days(label_days(dd)), start=1):
        f, last = days[0], days[-1]
        end = min(last + LABEL_HORIZON, len(chain) - 1)
        t = min(range(f, end + 1), key=lambda i: (chain[i], i))
        p = min(range(f, t + 1), key=lambda i: (-chain[i], i))
        b = next(
            (i for i in range(p, t + 1) if chain[i] <= BREACH_RATIO * chain[p]), None
        )
        censored = last + MERGE_GAP > last_label
        pre_missing = d0 is None or p - PRE_WINDOW < d0
        if censored:
            status = RIGHT_CENSORED_EVENT
        elif pre_missing:
            status = PRE_WINDOW_UNAVAILABLE
        else:
            status = EVALUABLE
        events.append(
            {
                "event_id": eid,
                "status": status,
                "right_censored": censored,
                "pre_window_unavailable": pre_missing,
                "first": f,
                "last": last,
                "label_days": len(days),
                "peak": p,
                "trough": t,
                "breach": b,
                "depth": chain[t] / chain[p] - 1.0,
            }
        )
    return events


def event_window(event: dict, range_end: Optional[int]) -> tuple[int, int]:
    """[P−10, T]. 잘린 사건은 관측 구간 전체 [min(F, P)−10, max(T, 구간 끝)] — 판정 §8 이 잘린 사건을
    precision 에서 "전부 제외" 하라고 하므로 F 와 P−10 사이 경보도 FALSE 로 세지 않는다."""
    start, end = event["peak"], event["trough"]
    if event["status"] == RIGHT_CENSORED_EVENT:
        start = min(start, event.get("first", start))
        if range_end is not None:
            end = max(end, range_end)
    return start - PRE_WINDOW, end


# --- 사건 분류 ---------------------------------------------------------------------


def classify_event(alerts: Sequence[bool], event: dict) -> dict:
    p, t = event["peak"], event["trough"]
    lo, hi = max(p - PRE_WINDOW, 0), min(t, len(alerts) - 1)
    first = next((i for i in range(lo, hi + 1) if alerts[i]), None)
    if first is None:
        return {"class": MISSED, "first_alert": None, "lead": None, "lead_vs_b": None}
    b = event["breach"]
    return {
        "class": PRE if first < p else POST,
        "first_alert": first,
        "lead": p - first,
        "lead_vs_b": (b - first) if b is not None else None,
    }


def event_summary(alerts: Sequence[bool], evaluable: Sequence[dict]) -> dict:
    """평가 사건의 사전·시작 후·미포착 · 선행일 중앙값 · 사전 비율 · severe 미포착."""
    per = {ev["event_id"]: classify_event(alerts, ev) for ev in evaluable}
    counts = {
        c: sum(1 for x in per.values() if x["class"] == c) for c in (PRE, POST, MISSED)
    }
    captured = counts[PRE] + counts[POST]
    leads = [x["lead"] for x in per.values() if x["lead"] is not None]
    leads_b = [x["lead_vs_b"] for x in per.values() if x["lead_vs_b"] is not None]
    depths = [ev["depth"] for ev in evaluable]
    threshold = bracketed_percentile(depths, SEVERE_PERCENTILE) if depths else None
    severe = (
        [ev["event_id"] for ev in evaluable if ev["depth"] <= threshold]
        if depths
        else []
    )
    return {
        "evaluable_events": len(evaluable),
        "pre_capture": counts[PRE],
        "post_only": counts[POST],
        "missed": counts[MISSED],
        "captured": captured,
        "lead_median": median(leads) if captured else None,
        "pre_share": counts[PRE] / captured if captured else None,
        "lead_vs_b_median": median(leads_b) if leads_b else None,
        "lead_vs_b_events": len(leads_b),
        "severe_threshold_depth": threshold,
        "severe_events": severe,
        "severe_missed": sum(1 for e in severe if per[e]["class"] == MISSED),
        "per_event": {str(k): v for k, v in per.items()},
    }


# --- 경보 run -----------------------------------------------------------------------


def window_mask(n: int, windows: Sequence[tuple[int, int]]) -> list[bool]:
    mask = [False] * n
    for lo, hi in windows:
        for i in range(max(lo, 0), min(hi, n - 1) + 1):
            mask[i] = True
    return mask


def alert_runs(alerts: Sequence[bool]) -> list[tuple[int, int]]:
    """연속 경보일 묶음 [a, b] (경보는 이미 평가 구간으로 가려져 있어야 한다)."""
    runs: list[tuple[int, int]] = []
    start = None
    for i, a in enumerate(alerts):
        if a and start is None:
            start = i
        elif not a and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(alerts) - 1))
    return runs


def run_summary(
    alerts: Sequence[bool], eval_mask: Sequence[bool], excl_mask: Sequence[bool]
) -> dict:
    """run TRUE/EXCLUDED/FALSE · run precision · 경보 100건당 false-alarm run · 일 단위 보조."""
    kinds = {RUN_TRUE: 0, RUN_FALSE: 0, RUN_EXCLUDED: 0}
    counted_days = 0
    for a, b in alert_runs(alerts):
        if any(eval_mask[a : b + 1]):  # noqa: E203
            kind = RUN_TRUE
        elif any(excl_mask[a : b + 1]):  # noqa: E203
            kind = RUN_EXCLUDED
        else:
            kind = RUN_FALSE
        kinds[kind] += 1
        if kind != RUN_EXCLUDED:
            counted_days += b - a + 1
    counted_runs = kinds[RUN_TRUE] + kinds[RUN_FALSE]
    day = {RUN_TRUE: 0, RUN_FALSE: 0, RUN_EXCLUDED: 0}
    for i, a in enumerate(alerts):
        if a:
            if eval_mask[i]:
                day[RUN_TRUE] += 1
            elif excl_mask[i]:
                day[RUN_EXCLUDED] += 1
            else:
                day[RUN_FALSE] += 1
    counted_alert_days = day[RUN_TRUE] + day[RUN_FALSE]
    return {
        "runs_total": sum(kinds.values()),
        "runs_true": kinds[RUN_TRUE],
        "runs_false": kinds[RUN_FALSE],
        "runs_excluded": kinds[RUN_EXCLUDED],
        "run_precision": kinds[RUN_TRUE] / counted_runs if counted_runs else None,
        "alert_days_in_counted_runs": counted_days,
        "fa_runs_per_100_alerts": (
            kinds[RUN_FALSE] / counted_days * 100.0 if counted_days else None
        ),
        "alert_days_true": day[RUN_TRUE],
        "false_alarm_days": day[RUN_FALSE],
        "alert_days_excluded": day[RUN_EXCLUDED],
        "day_precision": (
            day[RUN_TRUE] / counted_alert_days if counted_alert_days else None
        ),
    }


# --- RANDOM_NULL ----------------------------------------------------------------------


def year_segments(dates: Sequence[str], lo: int, hi: int) -> list[list[int]]:
    """경보 평가 구간 [lo, hi] 을 달력 연도별 index 목록으로 나눈다."""
    out: list[list[int]] = []
    for i in range(lo, hi + 1):
        if out and dates[out[-1][-1]][:4] == dates[i][:4]:
            out[-1].append(i)
        else:
            out.append([i])
    return out


def run_lengths(bits: Sequence[bool]) -> list[int]:
    return sorted(b - a + 1 for a, b in alert_runs(bits))


def rotate(bits: Sequence[bool], offset: int) -> list[bool]:
    """원형 이동 — 결과[i] = bits[(i − offset) mod n]."""
    n = len(bits)
    offset %= n
    return list(bits[n - offset :]) + list(bits[: n - offset])  # noqa: E203


def acceptable_offsets(bits: Sequence[bool]) -> frozenset:
    """run 길이 구성(개수·길이)이 원래와 같은 오프셋 (연도 경계를 넘는 run 은 잘라 센다)."""
    base = run_lengths(bits)
    return frozenset(
        o for o in range(len(bits)) if run_lengths(rotate(bits, o)) == base
    )


def draw_offset(
    rng: random.Random, n: int, acceptable: frozenset, max_draws: int = NULL_MAX_DRAWS
) -> tuple[int, bool]:
    """(오프셋, 대체 여부) — 받을 수 있는 오프셋이 나올 때까지 최대 max_draws 번 뽑는다."""
    for _ in range(max_draws):
        off = rng.randrange(n)
        if off in acceptable:
            return off, False
    return 0, True


def shift_once(
    rng: random.Random,
    alerts: Sequence[bool],
    segments: Sequence[Sequence[int]],
    accept: Optional[Sequence[frozenset]] = None,
) -> tuple[list[bool], int]:
    """한 번의 무작위 이동 — 연도 구간마다 원형 이동한 경보열(구간 밖은 경보 없음)과 대체 횟수."""
    shifted = [False] * len(alerts)
    fallbacks = 0
    for n, seg in enumerate(segments):
        bits = [bool(alerts[i]) for i in seg]
        ok = accept[n] if accept is not None else acceptable_offsets(bits)
        off, fell_back = draw_offset(rng, len(bits), ok)
        fallbacks += fell_back
        for i, v in zip(seg, rotate(bits, off)):
            shifted[i] = v
    return shifted, fallbacks


def random_null(
    alerts: Sequence[bool],
    dates: Sequence[str],
    lo: Optional[int],
    hi: Optional[int],
    eval_mask: Sequence[bool],
    excl_mask: Sequence[bool],
    *,
    repeats: int = NULL_REPEATS,
    seed: int = NULL_SEED,
) -> dict:
    """연도별 run 구성 보존 원형 이동 · 반복마다 같은 창으로 run precision."""
    base = {
        "repeats": repeats,
        "seed": seed,
        "max_draws": NULL_MAX_DRAWS,
        "percentile": NULL_PERCENTILE,
    }
    if lo is None or hi is None or hi < lo:
        return {
            **base,
            "p95": None,
            "mean": None,
            "fallbacks": 0,
            "none_count": repeats,
        }
    segments = year_segments(dates, lo, hi)
    accept = [acceptable_offsets([bool(alerts[i]) for i in seg]) for seg in segments]
    rng = random.Random(seed)
    precisions: list[float] = []
    fallbacks = none_count = 0
    for _ in range(repeats):
        shifted, fell = shift_once(rng, alerts, segments, accept)
        fallbacks += fell
        got = run_summary(shifted, eval_mask, excl_mask)["run_precision"]
        if got is None:
            none_count += 1
        else:
            precisions.append(got)
    return {
        **base,
        "year_segments": [
            {"year": dates[seg[0]][:4], "days": len(seg), "acceptable_offsets": len(ok)}
            for seg, ok in zip(segments, accept)
        ],
        "p95": (
            bracketed_percentile(precisions, NULL_PERCENTILE) if precisions else None
        ),
        "mean": mean(precisions),
        "fallbacks": fallbacks,
        "none_count": none_count,
    }


def config() -> dict:
    return {
        "label": (
            "future_market_drawdown_10d <= -0.05 "
            "(_kodex_future_drawdown · KRX_BASEPRICE_CHAIN)"
        ),
        "label_horizon": LABEL_HORIZON,
        "label_threshold": LABEL_THRESHOLD,
        "merge_gap": MERGE_GAP,
        "pre_window": PRE_WINDOW,
        "breach_ratio": BREACH_RATIO,
        "severe_percentile": SEVERE_PERCENTILE,
        "null_repeats": NULL_REPEATS,
        "null_seed": NULL_SEED,
        "null_max_draws": NULL_MAX_DRAWS,
        "null_percentile": NULL_PERCENTILE,
    }


def build_event_stage(axes: dict, signals: dict) -> dict:
    """사건 단계 출력 — dd10 · D_0 · label 계산 가능 마지막 날 · 사건 목록 (JSON 그대로 저장 가능)."""
    dates, chain = axes["dates"], axes["chain"]
    dd = future_drawdowns(dates, chain)
    alerts = signals["alerts"]
    d0 = first_defined(alerts[EARLY_PIT], alerts[REACTIVE])
    return {
        "dd10": dd,
        "d0": d0,
        "range_end": last_computable(dd),
        "label_days": label_days(dd),
        "events": build_events(chain, dd, d0),
    }
