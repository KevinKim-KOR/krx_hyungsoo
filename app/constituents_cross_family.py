"""여러 지수 계열이 함께 담은 주식(POC6-31 STEP 3 · PLAN C17 · 판정 §2 첫째 · Q9 · Q21).

- 후보 ETF마다 원천일이 확인된 마지막 구성(`etf_constituents_status` 기준)의 원본 비중 순위 1 ~ 10행만 본다.
- 식별 가능한 주식 행만 센다(`constituent_row_kind` · 현금 · 채권 · 파생 · ETF · 종류 미확인 가림).
- 계열 = `index_family.family_of`(공식 지수명이 같거나 판정으로 확인된 같은 기초지수) · 공식 지수명이 없으면 계열 미확인.
- **가장 최근 구성일의 ETF끼리** 센다. 그 날짜에 비교할 수 있는 계열(주식 행이 있는 확인 계열)이 2개 미만이면
  '비교 못 함', 비교가 성립하고 공통 주식이 없으면 '0종목'. 이전 구성일 ETF끼리의 대조는 그 날짜의 참고로 따로 둔다.
- 정렬 = 계열 수 → ETF 수 → 가장 큰 비중(새 기준값 없음 · POC6-30 규칙).
- 읽기 전용 · 외부 호출 0.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

from app.constituent_row_kind import STOCK_KINDS, UNKNOWN, row_kind
from app.etf_constituents_status import read_snapshots
from app.index_family import family_of
from app.pc_etf_compare_groups import TOP_CONSTITUENTS, classify_etf, constituent_key

STATUS_OK = "ok"
STATUS_NOT_COMPARABLE = "not_comparable"
STATUS_NO_DATA = "no_data"


def read_confirmed_rows(
    tickers: Iterable[str], *, db_path: Path
) -> dict[str, dict[str, Any]]:
    """ETF마다 원천일이 확인된 마지막 구성 — {asof, stored_count, rows(전체), top(1 ~ 10행)}."""
    tks = [t for t in dict.fromkeys(tickers) if t]
    # 검증자 r2 F5 — 원천일 확인을 판정한 바로 그 행(같은 읽기 트랜잭션 · 내용 지문 일치)만 쓴다. 따로 다시 읽지 않는다
    # (확인과 행 읽기 사이에 다른 경로가 덮어쓴 행이 끼어들지 않게). 칸 순서 = 상태 모듈 `_ROW_SQL`.
    snaps = read_snapshots(tks, db_path=db_path)
    out: dict[str, dict[str, Any]] = {}
    for t in tks:
        conf = snaps.get(t, {}).get("confirmed")
        if not conf:
            continue
        out[t] = with_top(conf["asof"], _row_dicts(conf["data"]))
    return out


def _row_dicts(data: Iterable[Sequence[Any]]) -> list[dict[str, Any]]:
    """확인에 쓴 행(칸 순서 = 상태 모듈 `ROW_SQL`) → 행 사전."""
    return [
        {
            "rank": r[0],
            "ticker": r[1] or None,
            "name": r[2] or None,
            "weight_pct": r[3],
            "key": r[5] or None,
            "isin": r[6] or None,
            "reuters": r[7] or None,
            "market_type": r[8],
        }
        for r in data
    ]


def confirmed_rows(conf: Mapping[str, Any]) -> list[dict[str, Any]]:
    """`read_snapshots` 의 confirmed 한 건 → 저장 행 전체(대조 키 포함 · 짝 비교 POC6-31 STEP 4 가 같은 변환을 씀)."""
    return with_top(conf["asof"], _row_dicts(conf["data"]))["rows"]


def with_top(asof: str, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """저장 행 → {asof, stored_count, rows, top} · 행마다 대조 키(`match_key`)."""
    rows = [{**r, "match_key": constituent_key(r)} for r in rows]
    return {
        "asof": asof,
        "stored_count": len(rows),
        "rows": rows,
        "top": rows[:TOP_CONSTITUENTS],
    }


def _group(
    etfs: Sequence[Mapping[str, Any]],
    latest: Mapping[str, Mapping[str, Any]],
    etf_tickers: set[str],
) -> dict[str, Any]:
    entries: dict[str, list[dict[str, Any]]] = defaultdict(list)
    names: dict[str, str] = {}
    fams: set[str] = set()
    with_stock = unconfirmed = unknown_rows = 0
    for e in etfs:
        data = latest[e["ticker"]]
        fam = family_of(e.get("index_name"))
        stock_rows = 0
        for row in data["top"]:
            kind = row_kind(row, etf_tickers)
            if kind == UNKNOWN:
                unknown_rows += 1
            k = row["match_key"]
            if k is None or kind not in STOCK_KINDS:
                continue
            stock_rows += 1
            names.setdefault(k, row["name"] or k)
            entries[k].append(
                {
                    "etf": e["ticker"],
                    "etf_name": e.get("name"),
                    "selection_rank": e.get("rank"),
                    "family": fam,
                    "index_name": e.get("index_name"),
                    "strategy": bool(e.get("strategy")),
                    "rank": row["rank"],
                    "weight_pct": row["weight_pct"],
                    "asof": data["asof"],
                }
            )
        if stock_rows:
            with_stock += 1
            if fam:
                fams.add(fam)
            else:
                unconfirmed += 1
    stocks = []
    for k, es in entries.items():
        efams = sorted({x["family"] for x in es if x["family"]})
        if len(efams) < 2:
            continue
        top = max(es, key=lambda x: (x["weight_pct"] or 0.0))
        stocks.append(
            {
                "key": k,
                "name": names[k],
                "families": efams,
                "family_count": len(efams),
                "etf_count": len({x["etf"] for x in es}),
                "strategy_count": sum(1 for x in es if x["strategy"]),
                "max_weight_pct": top["weight_pct"] or 0.0,
                "max_entry": {
                    "etf": top["etf"],
                    "etf_name": top["etf_name"],
                    "rank": top["rank"],
                },
                "entries": sorted(
                    es, key=lambda x: (x["selection_rank"] is None, x["selection_rank"])
                ),
            }
        )
    stocks.sort(
        key=lambda s: (
            -s["family_count"],
            -s["etf_count"],
            -s["max_weight_pct"],
            s["name"],
        )
    )
    return {
        "status": STATUS_OK if len(fams) >= 2 else STATUS_NOT_COMPARABLE,
        "etf_count": len(etfs),
        "etf_with_stock_rows": with_stock,
        "family_count": len(fams),
        "unconfirmed_family_etfs": unconfirmed,
        "unknown_rows": unknown_rows,
        "evidence_count": sum(len(s["entries"]) for s in stocks),
        "stocks": stocks,
    }


def cross_family(
    etfs: Sequence[Mapping[str, Any]],
    latest: Mapping[str, Mapping[str, Any]],
    etf_tickers: set[str],
) -> dict[str, Any]:
    """`etfs` = [{ticker, name, rank, index_name, strategy}] (선정 순서).

    `latest` = `read_confirmed_rows` 결과.
    """
    with_data = [e for e in etfs if e["ticker"] in latest]
    dates = sorted({latest[e["ticker"]]["asof"] for e in with_data}, reverse=True)
    scope = {
        "requested": len(etfs),
        "with_data": len(with_data),
        "no_confirmed_data": len(etfs) - len(with_data),
        "latest_date": dates[0] if dates else None,
        "same_date": 0,
    }
    if not dates:
        return {"status": STATUS_NO_DATA, "scope": scope, "stocks": [], "reference": []}
    by_date: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for e in with_data:
        by_date[latest[e["ticker"]]["asof"]].append(e)
    main = _group(by_date[dates[0]], latest, etf_tickers)
    scope["same_date"] = len(by_date[dates[0]])
    reference = [
        {"date": d, **_group(by_date[d], latest, etf_tickers)} for d in dates[1:]
    ]
    return {
        "status": main["status"],
        "scope": {
            **scope,
            **{k: v for k, v in main.items() if k not in ("status", "stocks")},
        },
        "stocks": main["stocks"],
        "reference": reference,
    }


def etf_meta(
    tickers: Sequence[str],
    official: Mapping[str, Mapping[str, str]],
    names: Mapping[str, Optional[str]],
) -> list[dict[str, Any]]:
    """선정 순서 그대로 · 공식 지수명 · 전략형(기존 분류 함수와 같은 규칙)."""
    out = []
    for i, t in enumerate(tickers, start=1):
        c = classify_etf(t, names.get(t), official, None)
        out.append(
            {
                "ticker": t,
                "name": names.get(t),
                "rank": i,
                "index_name": c.get("index_name"),
                "strategy": bool(c.get("strategy")),
            }
        )
    return out
