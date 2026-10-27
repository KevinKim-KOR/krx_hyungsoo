"""POC6-11 자료 — 봉인 KRX 한 판 → 시장 축 행렬 · 합성 OHLC · 체결 가능 · 주간 신호 · 시점별 자격.

설계 §2 · §3-1 · PLAN §1 · §6(판정 §5 · §6).

```text
연결   공용 reader(`krx_sealed_reader`)의 연결 종가 I 를 그대로 쓴다(수정 없음 · 봉인 확인 전후 같음)
원시   시가 · 고가 · 저가 · 종가 · 거래량은 같은 member 조인에서 새로 읽는다(POC6-10 로컬 코드 미사용)
합성   O* = O × I/C · H* = H × I/C · L* = L × I/C(같은 날 배율) · 비유한 원시 값 = CheckRequired
체결   exec_ok = 원시 거래량 > 0 · 원시 시가 > 0 · 고저 관계(H ≥ max(O, C) · 0 < L ≤ min(O, C)) · 종가 유효 · 관계 성립
자격   신호일 이름 필터(POC4) · 연속 126 유효 종가(같은 구간 · 축 날짜 빠짐 없음 · 거래량 행)
       · 최근 20거래일(t−19 ~ t) 평균(원시 종가 × 원시 거래량) ≥ 1억원(대용치) · 신호일 원시 거래량 > 0
```
"""

from __future__ import annotations

import datetime as dt
import json
import math
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np

from app import krx_sealed_reader as K
from app.ml_pit_universe import name_at, passes_name_filter

BENCH = K.BENCHMARK_CODE
RUN_ROWS = 126
LIQ_DAYS = 20
LIQ_MIN = 1e8
MIN_ELIGIBLE = 20
RAW_KEYS = ("TDD_OPNPRC", "TDD_HGPRC", "TDD_LWPRC", "TDD_CLSPRC", "ACC_TRDVOL")
_RAW_SQL = (
    "SELECT m.bas_dd, d.isu_cd, d.row_json FROM krx_dataset_member m "
    "JOIN krx_etf_daily_raw d ON d.response_id = m.response_id WHERE m.version_id = ?"
)


class CheckRequired(Exception):
    """입력 · 가격 관계 · 날짜가 고정 · 의미와 다름 — 성과를 계산하지 않는다."""


def _num(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def iso(bas_dd: str) -> str:
    return f"{bas_dd[:4]}-{bas_dd[4:6]}-{bas_dd[6:]}"


def week(date: str) -> tuple[int, int]:
    y, w, _ = dt.date.fromisoformat(date).isocalendar()
    return (y, w)


def weekly_signals(axis: list[str]) -> list[int]:
    """축의 다음 날짜가 다른 주(월 ~ 일)인 날의 위치 — 끝의 불완전 주는 없음."""
    return [i for i in range(len(axis) - 1) if week(axis[i]) != week(axis[i + 1])]


@dataclass
class Panel:
    """시장 축 × 종목 행렬(행 없음 = NaN · False · −1)."""

    axis: list[str]
    codes: list[str]
    I: np.ndarray  # noqa: E741 — 연결 종가 지수(설계 기호)
    O: np.ndarray  # 합성 시가 O*
    H: np.ndarray
    L: np.ndarray
    C: np.ndarray  # 원시 종가
    V: np.ndarray  # 원시 거래량
    raw_open: np.ndarray
    raw_high: (
        np.ndarray
    )  # 원시 고가 · 저가 — 같은 날 관계 검사는 원시값으로(합성 배율 1ulp 오차 없음)
    raw_low: np.ndarray
    seg: np.ndarray
    has_row: np.ndarray
    exec_ok: np.ndarray
    series: dict = field(
        repr=False, default_factory=dict
    )  # reader CodeSeries(이름 · 날짜)
    seal: dict = field(default_factory=dict)

    @property
    def ci(self) -> dict[str, int]:
        return {c: j for j, c in enumerate(self.codes)}


def read_raw(db_path: Path, version: str) -> dict[str, dict[str, tuple]]:
    out: dict[str, dict[str, tuple]] = {}
    con = sqlite3.connect(K.readonly_uri(Path(db_path)), uri=True)
    try:
        for bas_dd, code, row_json in con.execute(_RAW_SQL, (version,)):
            row = json.loads(row_json)
            vals = tuple(_num(row.get(k)) for k in RAW_KEYS)
            if any(v is not None and not math.isfinite(v) for v in vals):
                raise CheckRequired(f"{code} {bas_dd} 원시 값 비유한(NaN · inf)")
            d = iso(bas_dd)
            per = out.setdefault(code, {})
            if d in per:
                raise CheckRequired(f"{code} {d} 원시 행이 둘 이상")
            per[d] = vals
    finally:
        con.close()
    return out


def build_panel(
    db_path: Path, version: str, expected_content: Optional[str] = None
) -> Panel:
    """봉인 확인(전후 같음) → reader 계열 + 원시 OHLCV → 행렬. 종가 · 거래량은 reader 와 행마다 대조한다."""
    try:
        before = K.verify_sealed_source(
            db_path, version_id=version, expected_content_sha256=expected_content
        )
    except K.SealedSourceError as e:
        raise CheckRequired(f"봉인 판 확인 실패: {e}"[:300]) from e
    panel = K.load_panel(db_path, version_id=version)
    raw = read_raw(db_path, version)
    try:
        K.assert_same_source(
            before,
            K.verify_sealed_source(
                db_path, version_id=version, expected_content_sha256=expected_content
            ),
        )
    except K.SealedSourceError as e:
        raise CheckRequired(f"실행 중 봉인 판 바뀜: {e}"[:300]) from e
    axis = panel.dates
    if panel.benchmark().dates != axis:
        raise CheckRequired("시장 축 ≠ 069500 날짜")
    pos = {d: i for i, d in enumerate(axis)}
    codes = sorted(panel.series)
    n, m = len(codes), len(axis)
    shape = (n, m)
    arr = {
        k: np.full(shape, np.nan)
        for k in ("I", "O", "H", "L", "C", "V", "raw_open", "raw_high", "raw_low")
    }
    seg = np.full(shape, -1, dtype=np.int32)
    has_row = np.zeros(shape, dtype=bool)
    exec_ok = np.zeros(shape, dtype=bool)
    for j, code in enumerate(codes):
        s = panel.series[code]
        rw = raw.get(code, {})
        if sorted(rw) != list(s.dates):
            raise CheckRequired(f"{code} 원시 행 날짜가 reader 와 다름")
        for r, d in enumerate(s.dates):
            i = pos[d]
            o, h, lo, c, v = rw[d]
            if c != s.close[r] or v != s.volume[r]:
                raise CheckRequired(f"{code} {d} 종가 · 거래량이 reader 와 다름")
            has_row[j, i] = True
            seg[j, i] = s.segment[r]
            arr["C"][j, i] = np.nan if c is None else c
            arr["V"][j, i] = np.nan if v is None else v
            arr["raw_open"][j, i] = np.nan if o is None else o
            arr["raw_high"][j, i] = np.nan if h is None else h
            arr["raw_low"][j, i] = np.nan if lo is None else lo
            chain = s.chain[r]
            if chain is None or s.close_status[r] != K.CLOSE_OK:
                continue
            if not (math.isfinite(chain) and chain > 0):
                raise CheckRequired(f"{code} {d} 연결값 비유한 · 0 이하")
            arr["I"][j, i] = chain
            f = chain / c
            for key, x in (("O", o), ("H", h), ("L", lo)):
                if x is not None:
                    arr[key][j, i] = x * f
            ok = (
                v is not None
                and v > 0
                and o is not None
                and o > 0
                and h is not None
                and lo is not None
                and h >= max(o, c)
                and 0 < lo <= min(o, c)
                and s.relation_ok[r]
            )
            exec_ok[j, i] = bool(ok)
    return Panel(
        axis=axis,
        codes=codes,
        seg=seg,
        has_row=has_row,
        exec_ok=exec_ok,
        series=panel.series,
        seal={
            k: before[k]
            for k in (
                "file_sha256",
                "content_sha256",
                "member_dates",
                "first_date",
                "last_date",
            )
        },
        **arr,
    )


def run_lengths(p: Panel) -> np.ndarray:
    """연속 유효(행 · 연결값 · 거래량 · 같은 구간 · 축 날짜 빠짐 없음) 길이."""
    valid = p.has_row & np.isfinite(p.I) & np.isfinite(p.V)
    n, m = valid.shape
    idx = np.arange(m)[None, :].repeat(n, axis=0)
    prev_valid = np.zeros_like(valid)
    prev_valid[:, 1:] = valid[:, :-1]
    same_seg = np.zeros_like(valid)
    same_seg[:, 1:] = p.seg[:, 1:] == p.seg[:, :-1]
    start = valid & ~(prev_valid & same_seg)
    last_start = np.maximum.accumulate(np.where(start, idx, -1), axis=1)
    return np.where(valid, idx - last_start + 1, 0)


def liquidity_mean(p: Panel) -> np.ndarray:
    """최근 20거래일 t−19 ~ t(신호일 포함) 평균(원시 종가 × 원시 거래량). 빠진 값이 있으면 NaN(판정 §5)."""
    tv = p.C * p.V
    csum = np.nancumsum(np.nan_to_num(tv, nan=0.0), axis=1)
    cnt = np.cumsum(np.isfinite(tv), axis=1)
    out = np.full(tv.shape, np.nan)
    w = LIQ_DAYS
    s = csum[:, w - 1 :].copy()  # noqa: E203
    s[:, 1:] -= csum[:, :-w]
    c = cnt[:, w - 1 :].copy()  # noqa: E203
    c[:, 1:] -= cnt[:, :-w]
    full = c == w
    out[:, w - 1 :] = np.where(full, s / w, np.nan)  # noqa: E203
    return out


@dataclass
class Eligibility:
    sig: list[int]
    members: dict[int, list[int]]  # 신호 위치 → 자격 종목 위치(종목 코드 오름차순)
    reasons: dict[str, int]
    excluded: dict[int, dict[str, list[int]]]


def eligibility(p: Panel, sig: list[int]) -> Eligibility:
    run = run_lengths(p)
    liq = liquidity_mean(p)
    members: dict[int, list[int]] = {}
    excluded: dict[int, dict[str, list[int]]] = {}
    reasons = {"name": 0, "run126": 0, "liquidity": 0, "vol0": 0}
    for i in sig:
        d = p.axis[i]
        keep: list[int] = []
        ex: dict[str, list[int]] = {k: [] for k in reasons}
        for j in np.flatnonzero(p.has_row[:, i]):
            s = p.series[p.codes[j]]
            if not passes_name_filter(name_at(s, d)):
                why = "name"
            elif run[j, i] < RUN_ROWS:
                why = "run126"
            elif not (np.isfinite(liq[j, i]) and liq[j, i] >= LIQ_MIN):
                why = "liquidity"
            elif not p.V[j, i] > 0:
                why = "vol0"
            else:
                keep.append(int(j))
                continue
            ex[why].append(int(j))
            reasons[why] += 1
        members[i] = keep
        excluded[i] = ex
    return Eligibility(sig=sig, members=members, reasons=reasons, excluded=excluded)


def first_trading(axis: list[str], date: str) -> int:
    return next(i for i, d in enumerate(axis) if d >= date)


def last_trading(axis: list[str], date: str) -> int:
    return max(i for i, d in enumerate(axis) if d <= date)
