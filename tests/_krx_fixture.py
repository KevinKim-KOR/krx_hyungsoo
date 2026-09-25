"""POC4-02 테스트용 KRX 봉인 스키마 고정 DB (tmp_path 전용).

봉인 DB·라이브 DB 는 열지 않는다(테스트 가드가 거부한다). 스키마·hash·봉인은 운영 연구 모듈
(`app/ml_research_krx_universe`)의 함수를 그대로 써서 만든다 — 스키마가 실제와 어긋나지 않게.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional

from app import ml_research_krx_universe as research

VERSION = "krx_etf_universe_v1"

KEYS = (
    "ACC_TRDVAL",
    "ACC_TRDVOL",
    "BAS_DD",
    "CMPPREVDD_IDX",
    "CMPPREVDD_PRC",
    "FLUC_RT",
    "FLUC_RT_IDX",
    "IDX_IND_NM",
    "INVSTASST_NETASST_TOTAMT",
    "ISU_CD",
    "ISU_NM",
    "LIST_SHRS",
    "MKTCAP",
    "NAV",
    "OBJ_STKPRC_IDX",
    "TDD_CLSPRC",
    "TDD_HGPRC",
    "TDD_LWPRC",
    "TDD_OPNPRC",
)


def krx_row(
    code: str,
    bas_dd: str,
    close: float,
    prev_close: Optional[float],
    *,
    volume: float = 1000,
    nav: Optional[float] = None,
    name: Optional[str] = None,
    cmpprev: Optional[float] = None,
    fluc: Optional[float] = None,
) -> dict:
    """KRX 응답 행 하나(모든 값 문자열). 대비·등락률은 직전 기준가(prev_close)로 만든다."""
    if cmpprev is None:
        cmpprev = 0.0 if prev_close is None else close - prev_close
    if fluc is None:
        base = close - cmpprev
        fluc = round(cmpprev / base * 100.0, 2) if base > 0 else 0.0
    row = {k: "" for k in KEYS}
    row.update(
        {
            "BAS_DD": bas_dd,
            "ISU_CD": code,
            "ISU_NM": name or f"TEST {code}",
            "TDD_CLSPRC": f"{close:g}",
            "CMPPREVDD_PRC": f"{cmpprev:g}",
            "FLUC_RT": f"{fluc:.2f}",
            "ACC_TRDVOL": f"{volume:g}",
            "ACC_TRDVAL": f"{volume * close:g}",
            "NAV": f"{(nav if nav is not None else close):g}",
            "IDX_IND_NM": "TEST INDEX",
            "TDD_OPNPRC": f"{close:g}",
            "TDD_HGPRC": f"{close:g}",
            "TDD_LWPRC": f"{close:g}",
            "LIST_SHRS": "1000000",
            "MKTCAP": f"{close * 1000000:g}",
            "INVSTASST_NETASST_TOTAMT": f"{close * 1000000:g}",
            "OBJ_STKPRC_IDX": "100",
            "CMPPREVDD_IDX": "0",
            "FLUC_RT_IDX": "0",
        }
    )
    return row


def series_rows(
    code: str,
    dates: Iterable[str],
    closes: Iterable[float],
    *,
    volumes: Optional[Iterable[float]] = None,
    names: Optional[Iterable[str]] = None,
    name: Optional[str] = None,
) -> dict[str, dict]:
    """한 종목의 날짜별 행. 첫 행은 대비 0 (상장일 기준가 = 종가)."""
    dates, closes = list(dates), list(closes)
    vols = list(volumes) if volumes is not None else [1000] * len(dates)
    nms = list(names) if names is not None else [name] * len(dates)
    out: dict[str, dict] = {}
    prev = None
    for d, c, v, n in zip(dates, closes, vols, nms):
        out[d] = krx_row(code, d, c, prev, volume=v, name=n)
        prev = c
    return out


def build_sealed_db(
    path: Path,
    rows_by_date: dict[str, list[dict]],
    *,
    version: str = VERSION,
    seal: bool = True,
    extra_unattached: Optional[dict[str, list[dict]]] = None,
) -> str:
    """고정 DB 를 만들고 봉인한다. 반환: content_sha256 (seal=False 면 '').

    `extra_unattached` — 같은 날짜의 member 가 아닌 추가 응답(canary 흉내). reader 는 읽지 않아야 한다.
    """
    con = research.connect(path)
    try:
        dates = sorted(rows_by_date)
        research.create_batch(
            con,
            batch_id="FULL-TEST",
            purpose="FULL",
            dates=dates,
            dataset_version=version,
        )
        for d in dates:
            rows = rows_by_date[d]
            text = json.dumps({"OutBlock_1": rows}, ensure_ascii=False)
            rid = research._store_response(
                con, "FULL-TEST", d, research.FetchResult(200, text), rows
            )
            research._attach_member(con, version, d, rid)
        for d, rows in (extra_unattached or {}).items():
            text = json.dumps({"OutBlock_1": rows, "canary": True}, ensure_ascii=False)
            research._store_response(
                con, "FULL-TEST", d, research.FetchResult(200, text), rows
            )
        con.commit()
        if not seal:
            return ""
        return research.seal_version(con, version)["content_sha256"]
    finally:
        con.close()


def rows_by_date(*code_maps: dict[str, dict]) -> dict[str, list[dict]]:
    """`series_rows` 결과 여러 개를 날짜별 행 목록으로 합친다."""
    out: dict[str, list[dict]] = {}
    for mapping in code_maps:
        for d, row in mapping.items():
            out.setdefault(d, []).append(row)
    return out


def trading_dates(n: int, start: int = 20140102) -> list[str]:
    """테스트용 연속 평일 날짜(YYYYMMDD) n 개."""
    from datetime import date, timedelta

    d = date(start // 10000, start // 100 % 100, start % 100)
    out: list[str] = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.strftime("%Y%m%d"))
        d += timedelta(days=1)
    return out
