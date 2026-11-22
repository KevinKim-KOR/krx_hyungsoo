"""봉인 KRX 한 판 → 시장 축 행렬(연결 종가 · 합성 시가 · 체결 가능 · 그날 이름 · 그날 지수명).

```text
봉인   verify_sealed_source 전후 두 번 · 같아야 쓴다 · 파일 해시 = 고정값(protocol.FILE_SHA)
연결   공용 reader 의 KRX_BASEPRICE_CHAIN(수정 없음) · 구간(segment) 그대로
원시   시가 · 고가 · 저가 · 종가 · 거래량 · 지수명은 같은 member 조인에서 읽는다 · 종가 · 거래량은 reader 와 행마다 대조
합성   O* = 원 시가 × (연결 종가 ÷ 원 종가) — POC6 `weekly_selection.data.build_panel` 과 같은 식(verify 가 칸 대조)
체결   거래량 > 0 · 시가 > 0 · 고가 ≥ max(시가, 종가) · 0 < 저가 ≤ min(시가, 종가) · 기준가 관계 성립 · 종가 유효
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
from app.entry_timing.protocol import CheckRequired, Config

RAW_KEYS = ("TDD_OPNPRC", "TDD_HGPRC", "TDD_LWPRC", "TDD_CLSPRC", "ACC_TRDVOL")
_RAW_SQL = (
    "SELECT m.bas_dd, d.isu_cd, d.row_json FROM krx_dataset_member m "
    "JOIN krx_etf_daily_raw d ON d.response_id = m.response_id WHERE m.version_id = ?"
)


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
    """축의 다음 날짜가 다른 ISO 주(월 ~ 일)인 날의 위치 — 끝의 불완전 주는 없음."""
    return [i for i in range(len(axis) - 1) if week(axis[i]) != week(axis[i + 1])]


def window_start(axis: list[str], i: int, lookback_days: int) -> Optional[int]:
    """운영 1개월 규칙: 끝 − lookback 일 이후 첫 축 날짜(축 = 069500 날짜). 축 처음보다 앞이면 None."""
    target = (
        dt.date.fromisoformat(axis[i]) - dt.timedelta(days=lookback_days)
    ).isoformat()
    if target < axis[0]:
        return None
    for j in range(i + 1):
        if axis[j] >= target:
            return j
    return None


@dataclass
class Panel:
    """시장 축 × 종목 행렬(행 없음 = NaN · False · −1 · '')."""

    axis: list[str]
    codes: list[str]
    I: np.ndarray  # noqa: E741 — 연결 종가(설계 기호)
    O: np.ndarray  # 합성 시가 O*
    C: np.ndarray  # 원 종가
    seg: np.ndarray
    has_row: np.ndarray
    exec_ok: np.ndarray
    name: np.ndarray  # 그날 ISU_NM
    index_name: np.ndarray  # 그날 IDX_IND_NM(앞뒤 공백 정리)
    seal: dict = field(default_factory=dict)

    @property
    def ci(self) -> dict[str, int]:
        return {c: j for j, c in enumerate(self.codes)}


def read_raw(db_path: Path, version: str) -> dict[str, dict[str, tuple]]:
    """{code: {date: (open, high, low, close, volume, index_name)}} — 읽기 전용 · 불변 URI."""
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
            per[d] = vals + ((row.get("IDX_IND_NM") or "").strip(),)
    finally:
        con.close()
    return out


def _verify(cfg: Config) -> dict:
    try:
        seal = K.verify_sealed_source(
            cfg.db, version_id=cfg.version, expected_content_sha256=cfg.content_sha
        )
    except K.SealedSourceError as e:
        raise CheckRequired(f"봉인 판 확인 실패: {e}"[:300]) from e
    if cfg.file_sha is not None and seal.get("file_sha256") != cfg.file_sha:
        raise CheckRequired("봉인 파일 해시가 고정값과 다름")
    return seal


def load(cfg: Config) -> Panel:
    """봉인 확인(전후 같음) → reader 계열 + 원시 OHLCV · 지수명 → 행렬."""
    before = _verify(cfg)
    panel = K.load_panel(cfg.db, version_id=cfg.version)
    raw = read_raw(cfg.db, cfg.version)
    try:
        K.assert_same_source(before, _verify(cfg))
    except K.SealedSourceError as e:
        raise CheckRequired(f"실행 중 봉인 판 바뀜: {e}"[:300]) from e
    axis = panel.dates
    if panel.benchmark().dates != axis:
        raise CheckRequired("시장 축 ≠ 069500 날짜")
    pos = {d: i for i, d in enumerate(axis)}
    codes = sorted(panel.series)
    shape = (len(codes), len(axis))
    arr = {k: np.full(shape, np.nan) for k in ("I", "O", "C")}
    seg = np.full(shape, -1, dtype=np.int32)
    has_row = np.zeros(shape, dtype=bool)
    exec_ok = np.zeros(shape, dtype=bool)
    name = np.full(shape, "", dtype=object)
    index_name = np.full(shape, "", dtype=object)
    for j, code in enumerate(codes):
        s = panel.series[code]
        rw = raw.get(code, {})
        if sorted(rw) != list(s.dates):
            raise CheckRequired(f"{code} 원시 행 날짜가 reader 와 다름")
        for r, d in enumerate(s.dates):
            i = pos[d]
            o, h, lo, c, v, idx = rw[d]
            if c != s.close[r] or v != s.volume[r]:
                raise CheckRequired(f"{code} {d} 종가 · 거래량이 reader 와 다름")
            has_row[j, i] = True
            seg[j, i] = s.segment[r]
            name[j, i] = s.name[r]
            index_name[j, i] = idx
            arr["C"][j, i] = np.nan if c is None else c
            chain = s.chain[r]
            if chain is None or s.close_status[r] != K.CLOSE_OK:
                continue
            if not (math.isfinite(chain) and chain > 0):
                raise CheckRequired(f"{code} {d} 연결값 비유한 · 0 이하")
            arr["I"][j, i] = chain
            f = chain / c
            if o is not None:
                arr["O"][j, i] = o * f
            exec_ok[j, i] = bool(
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
    return Panel(
        axis=axis,
        codes=codes,
        seg=seg,
        has_row=has_row,
        exec_ok=exec_ok,
        name=name,
        index_name=index_name,
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
