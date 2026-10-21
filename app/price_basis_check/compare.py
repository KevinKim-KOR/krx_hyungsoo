"""POC6-03 — 사본 · 기존 이력 · KRX 봉인 판 대조(PLAN §7-3 · §7-4 · 판정 §4 · §5 · 결과 전에 고정).

```text
경계    06 `link_break` 를 기존 이력(POC6-02 공식 snapshot 행)과 사본에 그대로 적용 — 관측만(값 · 판정 바꾸지 않음)
KRX     `krx_sealed_reader.load_panel` 의 무조정 종가 C · 관계 검증된 일간 수익률 r = Δ/(C−Δ)
        기준가 B_t = C_t/(1+r_t) · KRX 기준가 대비 배율 = C_t/B_t = 1+r_t
        기준가 조정 후보 = KRX 연속 거래일에서 |B_t − C_prev| ≥ 0.5원 · 후보 배율 = B_t/C_prev(사유 미확인)
짝      연구 축에서 연속인 두 거래일 · KRX 거래일에서도 연속 · 양쪽 값이 다 있을 때만(건너뛰기 없음)
일치    A = 사본 종가 · A_prev − 1 > 0 ·
        (A_t − 1)/(A_prev + 1) ≤ C_t/B_t ≤ (A_t + 1)/(A_prev − 1) (±1원 진단 폭)
단위    겹치는 날 A/C 중앙값 ∈ [0.5, 2.0] → 같은 원 단위 · 아니면 그 종목 대조 불가
누적    A/C 를 보고 · 여러 조정은 배율의 곱(합 · 반올림된 FLUC_RT 누적 복원 없음)
묶음    기존 이력 수집 묶음별 기존/사본 배율 · 기대값 = (묶음 수집일, KRX 끝] 후보의 C_prev/B 곱
```

성과(학습 · 예측 · 오차) 계산 0. 적격 수는 POC6-02 `study.prepare` 그대로 센다.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any, Optional

from app import krx_sealed_reader as krx
from app.d20_pooled import study as S
from app.d20_pooled.snapshot import snapshot_problem
from app.price_basis_check import fetch as F
from app.reentry_review import prices

UNIT_RANGE = (0.5, 2.0)
HALF_WON = 0.5

# 대조 불가 사유(판정 순서 = 아래 순서 · 앞 사유가 먼저)
KRX_OUT_OF_RANGE = "KRX_OUT_OF_RANGE"
KRX_NO_SERIES = "KRX_NO_SERIES"
UNIT_UNCONFIRMED = "UNIT_UNCONFIRMED"
KRX_NOT_CONSECUTIVE = "KRX_NOT_CONSECUTIVE"
KRX_ROW_MISSING = "KRX_ROW_MISSING"
KRX_CLOSE_INVALID = "KRX_CLOSE_INVALID"
KRX_RELATION_FAIL = "KRX_RELATION_FAIL"
COPY_ROW_MISSING = "COPY_ROW_MISSING"
COPY_CLOSE_INVALID = "COPY_CLOSE_INVALID"
INTERVAL_UNDEFINED = "INTERVAL_UNDEFINED"
REASON_TEXT = {
    KRX_OUT_OF_RANGE: "KRX 봉인 판 범위 밖 날짜(KRX 로 검증 안 됨)",
    KRX_NO_SERIES: "KRX 봉인 판에 종목 행 없음",
    UNIT_UNCONFIRMED: "원 단위 확인 불가(A/C 중앙값이 [0.5, 2.0] 밖 · 겹치는 날 없음)",
    KRX_NOT_CONSECUTIVE: "두 축 날짜가 KRX 거래일에서 연속이 아님",
    KRX_ROW_MISSING: "그날 KRX 종목 행 없음",
    KRX_CLOSE_INVALID: "KRX 종가 없음 · 0 이하",
    KRX_RELATION_FAIL: "KRX 전일 대비 · 등락률 관계 불성립 · 값 없음",
    COPY_ROW_MISSING: "그날 사본 행 없음",
    COPY_CLOSE_INVALID: "사본 종가 없음 · 0 이하 · 유한하지 않음",
    INTERVAL_UNDEFINED: "A_prev − 1 ≤ 0 이라 ±1원 구간을 정할 수 없음",
}


class CompareError(Exception):
    """대조 입력 계약 위반(사본 형식 · snapshot · 재계산용 snapshot) — CHECK_REQUIRED."""


# ── 사본 읽기 ──────────────────────────────────────────────────────────────────


def load_copy(copy_dir: Path) -> dict[str, Any]:
    path = Path(copy_dir) / "copy.sqlite"
    if not path.is_file():
        raise CompareError(f"사본 DB 없음: {path}")
    con = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    try:
        meta = {k: json.loads(v) for k, v in con.execute("SELECT key, value FROM meta")}
        log = [json.loads(b) for (b,) in con.execute("SELECT body FROM fetch_log")]
        rows: dict[str, list[prices.PriceRow]] = defaultdict(list)
        for t, d, close, source, at, change in con.execute(
            "SELECT ticker, date, close, source, fetched_at, change FROM prices"
            " ORDER BY ticker, date"
        ):
            rows[t].append(prices.PriceRow(d, close, source, at, change))
    except sqlite3.Error as e:
        raise CompareError(f"사본 DB 읽기 실패: {type(e).__name__}") from e
    finally:
        con.close()
    if meta.get("schema") != F.SCHEMA:
        raise CompareError(f"사본 schema {meta.get('schema')!r} ≠ {F.SCHEMA}")
    return {"meta": meta, "log": log, "rows": dict(rows)}


# ── 경계(06 판정 그대로) ─────────────────────────────────────────────────────────


def breaks(rows: list[prices.PriceRow]) -> list[dict[str, Any]]:
    out = []
    for prev, row in zip(rows, rows[1:]):
        kind = prices.link_break(prev, row)
        if kind:
            out.append(
                {
                    "date": row.date,
                    "kind": kind,
                    "prev_date": prev.date,
                    "prev_fetched": (prev.fetched_at or "")[:10] or None,
                    "fetched": (row.fetched_at or "")[:10] or None,
                }
            )
    return out


def change_vs_close_ratio(rows: list[prices.PriceRow]) -> dict[str, int]:
    """저장 change 가 같은 행들의 종가 비율과 같은지(1e-9) — 사본은 원천 라이브러리가 같은 응답 종가로
    change 를 계산하므로(FinanceDataReader naver `Close.pct_change()`) 06 BASIS_BREAK 가 구조적으로 안 생긴다.
    """
    checked = equal = 0
    for prev, row in zip(rows, rows[1:]):
        if row.change is None or not (
            prices.valid_close(prev.close) and prices.valid_close(row.close)
        ):
            continue
        checked += 1
        equal += (
            abs(float(row.change) - (float(row.close) / float(prev.close) - 1.0))
            <= 1e-9
        )
    return {"checked": checked, "equal": equal}


# ── KRX 일간 단계 · 기준가 조정 후보 ────────────────────────────────────────────


def krx_step(
    s: krx.CodeSeries, pos: dict[str, int], d0: str, d1: str
) -> tuple[Optional[dict[str, float]], Optional[str]]:
    """KRX 연속 거래일 d0 → d1 의 (C_prev, C_t, 배율 C_t/B_t, B_t). 못 구하면 (None, 사유)."""
    if d0 not in pos or d1 not in pos or pos[d1] - pos[d0] != 1:
        return None, KRX_NOT_CONSECUTIVE
    if d0 not in s.index or d1 not in s.index:
        return None, KRX_ROW_MISSING
    i0, i1 = s.index[d0], s.index[d1]
    if s.close_status[i0] != krx.CLOSE_OK or s.close_status[i1] != krx.CLOSE_OK:
        return None, KRX_CLOSE_INVALID
    c0, c1 = s.close[i0], s.close[i1]
    if not (_pos(c0) and _pos(c1)):  # 판정 §4-3 '유한한 양수'(NaN 종가 방어)
        return None, KRX_CLOSE_INVALID
    if not s.relation_ok[i1] or s.daily_return[i1] is None:
        return None, KRX_RELATION_FAIL
    k = 1.0 + s.daily_return[i1]
    if not _pos(k) or not _pos(c1 / k):
        return None, KRX_RELATION_FAIL
    return {"c_prev": c0, "c": c1, "k": k, "base": c1 / k}, None


def _pos(v: Any) -> bool:
    return (
        isinstance(v, (int, float))
        and not isinstance(v, bool)
        and math.isfinite(v)
        and v > 0
    )


def krx_candidates(s: krx.CodeSeries, panel_dates: list[str]) -> dict[str, Any]:
    """KRX 자체 연속 거래일로 본 기준가 조정 후보(날짜 → 배율 B/C_prev) · 평가 못 한 날짜."""
    pos = {d: k for k, d in enumerate(panel_dates)}
    cands: dict[str, float] = {}
    gaps: list[str] = []
    for d0, d1 in zip(s.dates, s.dates[1:]):
        step, why = krx_step(s, pos, d0, d1)
        if step is None:
            gaps.append(d1)
        elif abs(step["base"] - step["c_prev"]) >= HALF_WON:
            cands[d1] = step["base"] / step["c_prev"]
    return {"factors": cands, "unevaluated": gaps}


SIZE_BINS_BP = (
    1,
    5,
    20,
    100,
)  # |사본 배율/KRX 배율 − 1| 구간(bp) — 실제 조회 전에 고정(검토 MED-2)


def mismatch_breakdown(mismatches: list[dict[str, Any]]) -> dict[str, Any]:
    """±1원 불일치를 후보일/일반일 · 크기(bp) · 연도로 나눈다(판정 규칙은 그대로 · 읽는 법만 보탬)."""
    by_size: Counter = Counter()
    for m in mismatches:
        bp = abs(m["copy_k"] / m["krx_k"] - 1.0) * 1e4
        label = next(
            (f"≤{b}bp" for b in SIZE_BINS_BP if bp <= b), f">{SIZE_BINS_BP[-1]}bp"
        )
        by_size[label] += 1
    order = [f"≤{b}bp" for b in SIZE_BINS_BP] + [f">{SIZE_BINS_BP[-1]}bp"]
    return {
        "candidate_days": sum(1 for m in mismatches if m["candidate"]),
        "normal_days": sum(1 for m in mismatches if not m["candidate"]),
        "by_size_bp": {k: by_size[k] for k in order if by_size[k]},
        "by_year": dict(sorted(Counter(m["date"][:4] for m in mismatches).items())),
    }


def _interval(a0: float, a1: float) -> Optional[tuple[float, float]]:
    if a0 - 1.0 <= 0:
        return None
    return (a1 - 1.0) / (a0 + 1.0), (a1 + 1.0) / (a0 - 1.0)


def unit_check(
    copy_by_date: dict[str, prices.PriceRow], s: krx.CodeSeries
) -> tuple[bool, Optional[float]]:
    ratios = [
        float(r.close) / s.close[s.index[d]]
        for d, r in copy_by_date.items()
        if d in s.index
        and s.close_status[s.index[d]] == krx.CLOSE_OK
        and _pos(s.close[s.index[d]])  # NaN 종가가 중앙값을 망가뜨리지 않게
        and prices.valid_close(r.close)
    ]
    if not ratios:
        return False, None
    m = median(ratios)
    return UNIT_RANGE[0] <= m <= UNIT_RANGE[1], m


def krx_compare(
    axis: list[str],
    copy_rows: list[prices.PriceRow],
    s: Optional[krx.CodeSeries],
    panel_dates: list[str],
) -> dict[str, Any]:
    """연구 축 연속 거래일 짝마다 사본 일간 배율 A_t/A_prev 대 KRX C_t/B_t(±1원 구간)."""
    copy_by_date = {r.date: r for r in copy_rows}
    # 그 종목 사본 범위 안의 축만(상장 전 · 요청 구간 밖 날짜를 대조 불가로 부풀리지 않음)
    axis = [d for d in axis if copy_rows and d >= copy_rows[0].date]
    first, last = (panel_dates[0], panel_dates[-1]) if panel_dates else (None, None)
    pos = {d: k for k, d in enumerate(panel_dates)}
    unit_ok, unit_median = (False, None) if s is None else unit_check(copy_by_date, s)
    cand = krx_candidates(s, panel_dates) if s is not None else None
    counts: Counter = Counter()
    mismatches: list[dict[str, Any]] = []
    matched_candidates: list[dict[str, Any]] = []
    ratio_points: list[tuple[str, float]] = []
    for d0, d1 in zip(axis, axis[1:]):
        if first is None or d0 < first or d1 > last:
            counts[KRX_OUT_OF_RANGE] += 1
            continue
        if s is None:
            counts[KRX_NO_SERIES] += 1
            continue
        if not unit_ok:
            counts[UNIT_UNCONFIRMED] += 1
            continue
        step, why = krx_step(s, pos, d0, d1)
        if step is None:
            counts[why] += 1
            continue
        r0, r1 = copy_by_date.get(d0), copy_by_date.get(d1)
        if r0 is None or r1 is None:
            counts[COPY_ROW_MISSING] += 1
            continue
        if not (prices.valid_close(r0.close) and prices.valid_close(r1.close)):
            counts[COPY_CLOSE_INVALID] += 1
            continue
        a0, a1 = float(r0.close), float(r1.close)
        iv = _interval(a0, a1)
        if iv is None:
            counts[INTERVAL_UNDEFINED] += 1
            continue
        ok = iv[0] <= step["k"] <= iv[1]
        counts["MATCH" if ok else "MISMATCH"] += 1
        ratio_points.append((d1, a1 / step["c"]))
        is_cand = abs(step["base"] - step["c_prev"]) >= HALF_WON
        if is_cand:
            matched_candidates.append(
                {
                    "date": d1,
                    "factor": step["base"] / step["c_prev"],
                    "match": ok,
                    "reason": "조정 사유 미확인",
                }
            )
        if not ok:
            mismatches.append(
                {
                    "date": d1,
                    "krx_k": step["k"],
                    "copy_k": a1 / a0,
                    "low": iv[0],
                    "high": iv[1],
                    "candidate": is_cand,
                }
            )
    breakdown = mismatch_breakdown(mismatches)
    ratio = None
    if len(ratio_points) >= 2:
        (fd, fr), (ld, lr) = ratio_points[0], ratio_points[-1]
        product = 1.0
        for d, f in (cand["factors"] if cand else {}).items():
            if fd < d <= ld:
                product *= 1.0 / f
        ratio = {
            "first": {"date": fd, "a_over_c": fr},
            "last": {"date": ld, "a_over_c": lr},
            "observed_change": lr / fr,
            "krx_candidate_product": product,
            "unevaluated_krx_pairs_between": sum(
                1 for d in (cand["unevaluated"] if cand else []) if fd < d <= ld
            ),
            "note": "누적은 배율의 곱 · KRX 평가 못 한 짝이 있으면 숨은 조정이 있을 수 있음(참고)",
        }
    return {
        "krx_series": s is not None,
        "krx_first": s.dates[0] if s is not None and s.dates else None,
        "krx_last": s.dates[-1] if s is not None and s.dates else None,
        "unit_ok": unit_ok,
        "unit_median_a_over_c": unit_median,
        "pairs": len(axis) - 1 if axis else 0,
        "match": counts.pop("MATCH", 0),
        "mismatch": counts.pop("MISMATCH", 0),
        "not_comparable": dict(sorted(counts.items())),
        "candidates_on_pairs": matched_candidates,
        "mismatches": mismatches,
        "mismatch_breakdown": breakdown,
        "krx_candidates": (
            {
                "count": len(cand["factors"]),
                "unevaluated_pairs": len(cand["unevaluated"]),
            }
            if cand
            else None
        ),
        "a_over_c": ratio,
    }


# ── 기존 이력 수집 묶음별 차이 ────────────────────────────────────────────────────


def batch_diff(
    live_rows: list[prices.PriceRow],
    copy_rows: list[prices.PriceRow],
    cand: Optional[dict[str, Any]],
    krx_last: Optional[str],
) -> list[dict[str, Any]]:
    """기존 행의 수집 묶음(수집일)마다 기존/사본 배율 · KRX 범위 안 후보 곱 기대값 대조(±1원)."""
    copy_by_date = {r.date: r for r in copy_rows}
    groups: dict[str, list[tuple[float, float]]] = defaultdict(list)
    missing: Counter = Counter()
    for r in live_rows:
        key = (r.fetched_at or "")[:10] or "unknown"
        c = copy_by_date.get(r.date)
        if c is None or not (
            prices.valid_close(r.close) and prices.valid_close(c.close)
        ):
            missing[key] += 1
            continue
        groups[key].append((float(r.close), float(c.close)))
    out = []
    for key in sorted(set(groups) | set(missing)):
        pairs = groups.get(key, [])
        ratios = [lv / cp for lv, cp in pairs]
        expected, gaps, status = None, None, "대조 불가(겹치는 행 없음)"
        if pairs and key != "unknown" and krx_last and key >= krx_last:
            same = sum(1 for lv, cp in pairs if abs(lv - cp) < HALF_WON)
            status = (
                f"KRX 범위 밖 수집(수집일 ≥ KRX 끝 {krx_last}) · 기존=사본 {same}/{len(pairs)}행"
                " · 그 사이 사건 미확인(KRX 로 검증 안 됨)"
            )
        elif pairs and cand is not None and krx_last and key != "unknown":
            expected = 1.0
            for d, f in cand["factors"].items():
                if key < d <= krx_last:
                    expected *= 1.0 / f
            gaps = sum(1 for d in cand["unevaluated"] if key < d <= krx_last)
            inside = sum(
                1
                for lv, cp in pairs
                if cp - 1.0 > 0
                and (lv - 1.0) / (cp + 1.0) <= expected <= (lv + 1.0) / (cp - 1.0)
            )
            if gaps:
                status = f"조정 사유 미확인(KRX 평가 못 한 짝 {gaps})"
            elif inside == len(pairs):
                status = "KRX 범위 안 후보 곱과 일치(KRX 범위 밖 기간 사건은 미확인)"
            else:
                status = (
                    f"조정 사유 미확인(±1원 밖 {len(pairs) - inside}/{len(pairs)}행)"
                )
        elif pairs:
            status = "조정 사유 미확인(KRX 자료 없음 · 수집일 없음)"
        out.append(
            {
                "batch": key,
                "rows": len(pairs),
                "rows_not_compared": missing.get(key, 0),
                "live_over_copy_min": min(ratios) if ratios else None,
                "live_over_copy_max": max(ratios) if ratios else None,
                "same_within_half_won": sum(
                    1 for lv, cp in pairs if abs(lv - cp) < HALF_WON
                ),
                "expected_from_krx": expected,
                "unevaluated_krx_pairs": gaps,
                "status": status,
            }
        )
    return out


# ── 적격 다시 세기(POC6-02 규칙 그대로 · 성과 0) ─────────────────────────────────


def recount_snapshot(
    snap: dict[str, Any], copy_rows: dict[str, list[prices.PriceRow]]
) -> dict[str, Any]:
    """공식 snapshot 의 기준일 · 축 · 보유 건수에 사본 행(T 이하 · 요청 시작일 이상)을 넣은 snapshot.

    조회 실패 종목은 빼고, 첫 저장일이 늦어지면 06 축 규칙대로 축 앞부분 · 연도 · 건너뛴 평일을 자른다.
    """
    T = snap["T"]
    etfs = {}
    for t, e in sorted(snap["etfs"].items()):
        got = copy_rows.get(t)
        if not got or not e["rows"]:
            continue
        start = e["rows"][0][0]
        kept = [r for r in got if start <= r.date <= T]
        etfs[t] = {
            "name": e["name"],
            "rows": [list(r.as_json().values()) for r in kept],
        }
    firsts = [
        v["rows"][0][0] for v in etfs.values() if v["rows"] and v["rows"][0][0] <= T
    ]
    new_first = min(firsts) if firsts else T
    a = snap["axis"]
    axis = {
        **a,
        "dates": [d for d in a["dates"] if d >= new_first],
        "modes": {y: m for y, m in a["modes"].items() if int(y) >= int(new_first[:4])},
        "skipped_weekdays": [d for d in a["skipped_weekdays"] if d >= new_first],
    }
    axis["problem"] = prices.axis_problem(T, axis)
    h = snap["holdings"]
    out = {
        **snap,
        "axis": axis,
        "etfs": etfs,
        "holdings": {**h, "etf": len(etfs), "tickers": len(etfs) + h["non_etf"]},
    }
    bad = snapshot_problem(out)
    if bad:
        raise CompareError(f"재계산용 snapshot 계약 위반: {bad}")
    return out


def group_of(prep: dict[str, Any], t: str) -> str:
    e = prep["etfs"].get(t)
    if e is None:
        return "NOT_IN_SNAPSHOT"
    if e["eligible"]:
        return "ELIGIBLE"
    if any(pb["train_n"] < S.MIN_TRAIN for pb in e["blocks"]) or not e["blocks"]:
        return "SHORT_HISTORY"
    return "BREAK_EXCLUDED"


def recount(snap: dict[str, Any], copy_rows: dict[str, list]) -> dict[str, Any]:
    official = S.prepare(snap)
    again = S.prepare(recount_snapshot(snap, copy_rows))

    def view(prep):
        return {
            "eligible": list(prep["eligible"]),
            "excluded": {
                t: e["ineligible_reasons"]
                for t, e in prep["etfs"].items()
                if not e["eligible"]
            },
        }

    return {
        "rule": (
            "POC6-02 study.prepare(같은 T · 3구간 · 학습 ≥ 252 · 시험 날짜 ≥ 42 · 최소 4종)"
            " — 학습 · 예측 · 오차 0"
        ),
        "official": view(official),
        "copy": view(again),
        "not_recounted": sorted(set(snap["etfs"]) - set(again["etfs"])),
        "groups": {t: group_of(official, t) for t in sorted(snap["etfs"])},
    }


# ── 묶어서 ───────────────────────────────────────────────────────────────────


def compare(
    snap: dict[str, Any],
    copy: dict[str, Any],
    panel: Optional[krx.SealedPanel],
) -> dict[str, Any]:
    T = snap["T"]
    axis = snap["axis"]["dates"]
    panel_dates = panel.dates if panel is not None else []
    per: dict[str, Any] = {}
    for t, e in sorted(snap["etfs"].items()):
        live = [prices.PriceRow(*r) for r in e["rows"] if r[0] <= T]
        got = [r for r in copy["rows"].get(t, []) if r.date <= T]
        s = panel.series.get(t) if panel is not None else None
        cand = krx_candidates(s, panel_dates) if s is not None else None
        per[t] = {
            "name": e["name"],
            "live_breaks": breaks(live),
            "copy_breaks": breaks(got),
            "live_change_vs_close": change_vs_close_ratio(live),
            "copy_change_vs_close": change_vs_close_ratio(got),
            "copy_rows_to_T": len(got),
            "krx": krx_compare(axis, got, s, panel_dates),
            "batches": batch_diff(
                live,
                got,
                cand,
                (
                    min(
                        s.dates[-1], panel_dates[-1]
                    )  # KRX 끝 = 종목 끝 · 봉인 판 끝 중 이른 날
                    if s is not None and s.dates and panel_dates
                    else None
                ),
            ),
        }
    return per


def summarize(per: dict[str, Any], log: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = Counter(e["status"] for e in log)
    return {
        "fetch": dict(sorted(statuses.items())),
        "live_breaks": sum(len(v["live_breaks"]) for v in per.values()),
        "copy_breaks": sum(len(v["copy_breaks"]) for v in per.values()),
        "krx_match": sum(v["krx"]["match"] for v in per.values()),
        "krx_mismatch": sum(v["krx"]["mismatch"] for v in per.values()),
        "krx_not_comparable": dict(
            sorted(
                sum(
                    (Counter(v["krx"]["not_comparable"]) for v in per.values()),
                    Counter(),
                ).items()
            )
        ),
        "tickers_with_krx": sum(1 for v in per.values() if v["krx"]["krx_series"]),
        "krx_mismatch_breakdown": mismatch_breakdown(
            [m for v in per.values() for m in v["krx"]["mismatches"]]
        ),
        "copy_change_checked": sum(
            v["copy_change_vs_close"]["checked"] for v in per.values()
        ),
        "copy_change_equal": sum(
            v["copy_change_vs_close"]["equal"] for v in per.values()
        ),
    }
