"""ETF 구성종목 집중도 + 중복률 분석 (POC2 — 2026-05-27).

본 모듈은 pure function — DB read 만, write 없음. 지시문 §9 의 매칭 + 중복률
공식을 그대로 구현한다.

매칭 기준 (지시문 §9.1):
1. constituent_ticker 가 있으면 ticker 기준.
2. ticker 가 없으면 정규화된 constituent_name 기준 (공백 제거 / 대소문자 통일 /
   괄호 최소 정리).
3. 복잡한 fuzzy matching 은 본 STEP 에서 X.

중복률 (지시문 §9.2):
- common_count_top10: ETF A/B 의 상위 10개 중 공통 종목 수.
- weighted_overlap_pct: 공통 종목에 대해 min(A 비중, B 비중) 합산.
"""

from __future__ import annotations

import re
from itertools import combinations
from pathlib import Path
from typing import Optional

from app.etf_constituents_store import (
    ConstituentRow,
    DEFAULT_DB_PATH,
    fetch_constituents,
)

DEFAULT_TOP_K_FOR_OVERLAP = 10


def _normalize_name(name: Optional[str]) -> str:
    """매칭용 정규화 — 공백 제거 + 대소문자 통일 + 괄호 최소 정리."""
    if not name:
        return ""
    s = name.strip().lower()
    # 괄호 안 내용 제거 (예: "삼성전자(우)" → "삼성전자").
    s = re.sub(r"\([^)]*\)", "", s)
    # 공백 / 특수문자 제거.
    s = re.sub(r"[\s\-_/.,]+", "", s)
    return s


def _match_key(c: ConstituentRow) -> str:
    """매칭 키 우선순위 (2026-05-31 Naver 통합으로 확장, 지시문 §11.2):
    1. constituent_key (Naver fetcher 가 미리 결정한 1차 키 — ticker / reuters /
       isin / name 우선순위 반영).
    2. constituent_ticker (국내 종목 ticker).
    3. constituent_reuters_code (해외 종목 reuters code).
    4. constituent_isin (해외 종목 ISIN).
    5. 정규화된 constituent_name.
    """
    if c.constituent_key and c.constituent_key.strip():
        return f"K:{c.constituent_key.strip()}"
    if c.constituent_ticker and c.constituent_ticker.strip():
        return f"T:{c.constituent_ticker.strip()}"
    if c.constituent_reuters_code and c.constituent_reuters_code.strip():
        return f"R:{c.constituent_reuters_code.strip()}"
    if c.constituent_isin and c.constituent_isin.strip():
        return f"I:{c.constituent_isin.strip()}"
    return f"N:{_normalize_name(c.constituent_name)}"


def compute_concentration(top_rows: list[ConstituentRow]) -> dict:
    """상위 1/3/5/10 비중 합산 — None 비중은 0 으로 취급해 합산만 (보고 의미상).

    실제로는 weight 가 None 인 source 는 ok 처리되지 않으므로 정상 데이터에서는
    None 이 없다. 방어 처리.
    """

    def _sum_top(n: int) -> Optional[float]:
        if not top_rows:
            return None
        weights = [r.weight_pct for r in top_rows[:n] if r.weight_pct is not None]
        if not weights:
            return None
        return round(sum(weights), 2)

    return {
        "top1_weight_pct": _sum_top(1),
        "top3_weight_pct": _sum_top(3),
        "top5_weight_pct": _sum_top(5),
        "top10_weight_pct": _sum_top(10),
    }


def compute_pair_overlap(
    left: list[ConstituentRow],
    right: list[ConstituentRow],
    top_k: int = DEFAULT_TOP_K_FOR_OVERLAP,
) -> dict:
    """ETF 두 개의 top_k 기준 중복률 (지시문 §9.2).

    common_count_top10 = 공통 종목 수.
    weighted_overlap_pct = sum(min(left weight, right weight)) for common.
    """
    left_top = left[:top_k]
    right_top = right[:top_k]
    left_map = {_match_key(c): c for c in left_top}
    right_map = {_match_key(c): c for c in right_top}
    common_keys = set(left_map.keys()) & set(right_map.keys())
    # 빈 prefix-only 키는 무효 (Naver 통합 prefix 까지 모두 제거).
    for empty in ("K:", "T:", "R:", "I:", "N:"):
        common_keys.discard(empty)
    common_holdings: list[dict] = []
    weighted_sum = 0.0
    has_any_weight = False
    for k in common_keys:
        lc = left_map[k]
        rc = right_map[k]
        lw = lc.weight_pct if lc.weight_pct is not None else None
        rw = rc.weight_pct if rc.weight_pct is not None else None
        # 표시용 ticker / name 은 left 기준.
        ticker = lc.constituent_ticker or rc.constituent_ticker
        name = lc.constituent_name or rc.constituent_name
        common_holdings.append(
            {
                "ticker": ticker,
                "name": name,
                "left_weight_pct": lw,
                "right_weight_pct": rw,
            }
        )
        if lw is not None and rw is not None:
            weighted_sum += min(lw, rw)
            has_any_weight = True
    return {
        "common_count_top10": len(common_keys),
        "weighted_overlap_pct": (round(weighted_sum, 2) if has_any_weight else None),
        "common_holdings": common_holdings,
    }


def compute_repeated_core_holdings(
    per_ticker_rows: dict[str, list[ConstituentRow]],
    top_k: int = DEFAULT_TOP_K_FOR_OVERLAP,
    min_appears: int = 2,
) -> list[dict]:
    """반복 등장 핵심 종목 (지시문 §6.2). 본 STEP 의 refresh 가 다룬 ETF 안의
    등장 횟수 (universe 전체 X).
    """
    # key → {"ticker", "name", "items": [{etf_ticker, weight_pct}]}
    agg: dict[str, dict] = {}
    for etf_ticker, rows in per_ticker_rows.items():
        for c in rows[:top_k]:
            k = _match_key(c)
            if k in ("K:", "T:", "R:", "I:", "N:"):
                continue
            if k not in agg:
                agg[k] = {
                    "ticker": c.constituent_ticker,
                    "name": c.constituent_name,
                    "items": [],
                }
            agg[k]["items"].append(
                {"etf_ticker": etf_ticker, "weight_pct": c.weight_pct}
            )
    out: list[dict] = []
    for k, v in agg.items():
        cnt = len(v["items"])
        if cnt < min_appears:
            continue
        out.append(
            {
                "ticker": v["ticker"],
                "name": v["name"],
                "appears_in_etf_count": cnt,
                "items": v["items"],
            }
        )
    # 등장 횟수 DESC, 같으면 ticker ASC.
    out.sort(key=lambda x: (-x["appears_in_etf_count"], (x["ticker"] or "")))
    return out


def compute_analysis(
    *,
    tickers: list[str],
    asof: str,
    top_k: int = DEFAULT_TOP_K_FOR_OVERLAP,
    db_path: Path = DEFAULT_DB_PATH,
) -> dict:
    """GET /market/constituents/analysis 의 핵심 계산.

    각 ticker 에 대해 fetch_constituents → 집중도. 이후 ETF 쌍 조합으로 중복률
    계산 + repeated_core_holdings 집계.
    """
    per_ticker_rows: dict[str, list[ConstituentRow]] = {}
    constituents_out: list[dict] = []
    available_count = 0
    unavailable_count = 0
    for tk in tickers:
        rows = fetch_constituents(etf_ticker=tk, asof=asof, db_path=db_path)
        per_ticker_rows[tk] = rows
        if not rows:
            unavailable_count += 1
            constituents_out.append(
                {
                    "etf_ticker": tk,
                    "etf_name": None,
                    "status": "unavailable",
                    "source": None,
                    "asof": asof,
                    "top_holdings": [],
                    "concentration": {
                        "top1_weight_pct": None,
                        "top3_weight_pct": None,
                        "top5_weight_pct": None,
                        "top10_weight_pct": None,
                    },
                }
            )
            continue
        available_count += 1
        # 동일 source 의 1 행에서 etf_name 추출 (있으면).
        etf_name = next((r.etf_name for r in rows if r.etf_name), None)
        source = rows[0].source
        top_holdings = [
            {
                "rank": r.rank,
                "ticker": r.constituent_ticker,
                "name": r.constituent_name,
                "weight_pct": r.weight_pct,
                # 2026-05-31 — Naver 통합. 해외형 종목 식별자 노출.
                "constituent_isin": r.constituent_isin,
                "constituent_reuters_code": r.constituent_reuters_code,
                "market_type": r.market_type,
            }
            for r in rows[:top_k]
        ]
        constituents_out.append(
            {
                "etf_ticker": tk,
                "etf_name": etf_name,
                "status": "ok",
                "source": source,
                "asof": asof,
                "top_holdings": top_holdings,
                "concentration": compute_concentration(rows),
            }
        )

    overlap_matrix: list[dict] = []
    for left_tk, right_tk in combinations(tickers, 2):
        left_rows = per_ticker_rows.get(left_tk, [])
        right_rows = per_ticker_rows.get(right_tk, [])
        if not left_rows or not right_rows:
            # 한쪽이 unavailable 이면 의미 없는 0 0 0 결과 — 표시는 하되 null.
            overlap_matrix.append(
                {
                    "left_ticker": left_tk,
                    "right_ticker": right_tk,
                    "common_count_top10": 0,
                    "weighted_overlap_pct": None,
                    "common_holdings": [],
                }
            )
            continue
        pair = compute_pair_overlap(left_rows, right_rows, top_k=top_k)
        overlap_matrix.append(
            {
                "left_ticker": left_tk,
                "right_ticker": right_tk,
                **pair,
            }
        )

    repeated = compute_repeated_core_holdings(per_ticker_rows, top_k=top_k)

    return {
        "status": "ok",
        "asof": asof,
        "top_k": top_k,
        "coverage": {
            "requested_count": len(tickers),
            "available_count": available_count,
            "unavailable_count": unavailable_count,
        },
        "constituents": constituents_out,
        "overlap_matrix": overlap_matrix,
        "repeated_core_holdings": repeated,
    }
