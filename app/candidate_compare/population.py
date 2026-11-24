"""봉인 KRX → 주별 전체 후보 · 공통 후보군 · 두 기준 선정(PLAN §2 · 선정 뒤 가격은 보지 않는다).

```text
읽기     POC7-01 `data.load`(봉인 확인 전후 · 연결 종가 · 합성 시가 · 체결 가능 · 그날 이름) + 원시 거래량
신호일 D ISO 주 마지막 거래일(069500 축) · 1개월 시작 s = D − 30일 뒤 첫 거래일
전체 P   D · s 에 행 · 같은 가격 구간 · 연결값 유효 · 그날 이름이 제외 낱말 아님 → 원래 순위(1개월 · 종목코드)
공통 C   P 중 주 마감 5번(W-4 ~ W0 = D) 모두 같은 구간 유효 값 → 공통 순위 · 빠진 수 · 원래 상위 3 · 30 여부
선정     rules.pick_a · rules.pick_b(공통 후보 3개 미만 = '후보 부족')
편입     e1 = D 다음 거래일 · 평가 e2 = e1 + 20 거래일(축 밖이면 '결과 미성숙')
```
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from app import krx_sealed_reader as K
from app.candidate_compare import rules as RU
from app.candidate_compare.protocol import (
    BENCH,
    HOLD_DAYS,
    LOOKBACK_1M,
    N_INTERVALS,
    N_PICK,
    CheckRequired,
    Config,
)
from app.entry_timing import data as DA
from app.entry_timing import weekly as WK

ORDER_KEEP = 10  # 주 기록에 남기는 두 기준 순서의 앞부분(AC2 손 계산용)


@dataclass
class Data:
    """봉인 판 행렬 + 원시 거래량(행 없음 = NaN)."""

    panel: DA.Panel
    vol: np.ndarray

    @property
    def axis(self) -> list[str]:
        return self.panel.axis


def load(cfg: Config) -> Data:
    """봉인 확인(전후 같음) → POC7-01 행렬 + 원시 거래량. 봉인 판이 바뀌면 CheckRequired."""
    etc = cfg.entry_timing()
    before = DA._verify(etc)
    panel = DA.load(etc)
    raw = DA.read_raw(cfg.db, cfg.version)
    try:
        K.assert_same_source(before, DA._verify(etc))
    except K.SealedSourceError as e:
        raise CheckRequired(f"실행 중 봉인 판 바뀜: {e}"[:300]) from e
    pos = {d: i for i, d in enumerate(panel.axis)}
    vol = np.full((len(panel.codes), len(panel.axis)), np.nan)
    for j, code in enumerate(panel.codes):
        for d, vals in raw.get(code, {}).items():
            v = vals[4]
            if v is not None:
                vol[j, pos[d]] = v
    return Data(panel=panel, vol=vol)


def _close(panel: DA.Panel, j: int, i: int, seg: int) -> Optional[float]:
    if not panel.has_row[j, i] or panel.seg[j, i] != seg:
        return None
    v = float(panel.I[j, i])
    return v if math.isfinite(v) and v > 0 else None


def population(panel: DA.Panel, i: int, s: int, wk: list[int]) -> list[dict[str, Any]]:
    """전체 후보 P — (−1개월, 종목코드) 순 · 원래 순위 · 주 마감 5번 · 오른 주."""
    ok = (
        panel.has_row[:, i]
        & panel.has_row[:, s]
        & (panel.seg[:, i] == panel.seg[:, s])
        & np.isfinite(panel.I[:, i])
        & np.isfinite(panel.I[:, s])
    )
    pop = []
    for j in np.nonzero(ok)[0].tolist():
        if WK.name_excluded(panel.name[j, i]):
            continue
        seg = int(panel.seg[j, i])
        closes = [_close(panel, j, w, seg) for w in wk]
        pop.append(
            {
                "code": panel.codes[j],
                "j": j,
                "ret": float(panel.I[j, i] / panel.I[j, s] - 1.0),
                "closes": closes,
                "up": RU.up_weeks(closes),
            }
        )
    pop.sort(key=lambda p: (-p["ret"], p["code"]))
    for r, p in enumerate(pop, 1):
        p["orig_rank"] = r
    common = [p for p in pop if p["up"] is not None]
    for r, p in enumerate(common, 1):
        p["common_rank"] = r
    return pop


def _brief(p: dict[str, Any]) -> dict[str, Any]:
    return {
        "orig_rank": p["orig_rank"],
        "common_rank": p.get("common_rank"),
        "ret": p["ret"],
        "up": p["up"],
        "closes": p["closes"],
    }


def week_record(panel: DA.Panel, k: int, sig: list[int], cfg: Config) -> Optional[dict]:
    """신호 k 의 주 기록(기간 밖 · 1개월 창 없음 = None)."""
    axis = panel.axis
    i = sig[k]
    d = axis[i]
    span = WK.span_of(d, cfg.spans)
    if span is None or k < N_INTERVALS:
        return None
    s = DA.window_start(axis, i, LOOKBACK_1M)
    if s is None:
        return None
    wk = [sig[k - N_INTERVALS + m] for m in range(N_INTERVALS + 1)]
    e1, e2 = i + 1, i + 1 + HOLD_DAYS
    rec: dict[str, Any] = {
        "signal": d,
        "span": span,
        "sub": WK.sub_of(d, cfg.subs) if span == "main" else None,
        "window": [axis[s], d],
        "weekly_dates": [axis[w] for w in wk],
        "weekly_before_window": axis[wk[0]] < axis[s],
        "entry": axis[e1] if e1 < len(axis) else None,
        "exit": axis[e2] if e2 < len(axis) else None,
    }
    pop = population(panel, i, s, wk)
    common = [p for p in pop if p["up"] is not None]
    dropped = [p for p in pop if p["up"] is None]
    rec.update(
        n_pop=len(pop),
        n_common=len(common),
        dropped=[[p["code"], p["orig_rank"]] for p in dropped],
        dropped_top3=any(p["orig_rank"] <= N_PICK for p in dropped),
        dropped_top30=any(p["orig_rank"] <= 30 for p in dropped),
    )
    if e2 >= len(axis):
        rec.update(status="IMMATURE", a=[], b=[], same=None, picks={})
        return rec
    if len(common) < N_PICK:
        rec.update(status="FEW", a=[], b=[], same=None, picks={})
        return rec
    cands = [RU.Cand(p["code"], p["ret"], p["up"]) for p in common]
    a, b = RU.pick_a(cands), RU.pick_b(cands)
    by = {p["code"]: p for p in common}
    b_order = sorted(
        (c for c in cands if c.ret > 0), key=lambda c: (-c.up, -c.ret, c.code)
    )
    rec.update(
        status="OK",
        a=a,
        b=b,
        same=RU.same_selection(a, b),
        picks={c: _brief(by[c]) for c in sorted(set(a) | set(b))},
        a_order=[c.code for c in sorted(cands, key=RU.order_key)[:ORDER_KEEP]],
        b_order=[c.code for c in b_order[:ORDER_KEEP]],
    )
    return rec


def build_weeks(data: Data, cfg: Config) -> list[dict[str, Any]]:
    """본 · 보조 구간의 모든 신호 주 기록(달력 순)."""
    panel = data.panel
    if BENCH not in panel.ci:
        raise CheckRequired(f"벤치마크 {BENCH} 행이 없음")
    sig = DA.weekly_signals(panel.axis)
    out = []
    for k in range(len(sig)):
        rec = week_record(panel, k, sig, cfg)
        if rec is not None:
            out.append(rec)
    return out


def counts(weeks: list[dict[str, Any]], spans: dict) -> dict[str, dict[str, Any]]:
    """PLAN §1-4 분모 — 선정 뒤 가격을 보지 않는 수."""
    out: dict[str, dict[str, Any]] = {}
    for span in spans:
        ws = [w for w in weeks if w["span"] == span]
        pops = sorted(w["n_pop"] for w in ws)
        out[span] = {
            "weeks": len(ws),
            "ok_weeks": sum(1 for w in ws if w["status"] == "OK"),
            "few_weeks": sum(1 for w in ws if w["status"] == "FEW"),
            "immature_weeks": sum(1 for w in ws if w["status"] == "IMMATURE"),
            "common_missing": sum(len(w["dropped"]) for w in ws),
            "dropped_top3_weeks": sum(1 for w in ws if w["dropped_top3"]),
            "dropped_top30_weeks": sum(1 for w in ws if w["dropped_top30"]),
            "weekly_before_window": sum(1 for w in ws if w["weekly_before_window"]),
            "pop_median": float(np.median(pops)) if pops else None,
            "pop_min": pops[0] if pops else None,
            "pop_max": pops[-1] if pops else None,
            "same_weeks": sum(1 for w in ws if w["same"] is True),
            "first": ws[0]["signal"] if ws else None,
            "last": ws[-1]["signal"] if ws else None,
        }
    return out


def check_expected(cnt: dict, expected: Optional[dict]) -> None:
    if not expected:
        return
    for span, want in expected.items():
        for key, v in want.items():
            got = cnt.get(span, {}).get(key)
            if got != v:
                raise CheckRequired(
                    f"분모가 PLAN §1-4 와 다름: {span}.{key} = {got}(기대 {v})"
                )
