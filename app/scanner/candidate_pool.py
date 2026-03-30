# -*- coding: utf-8 -*-
"""
app/scanner/candidate_pool.py — Candidate Pool Layer (P205-STEP5B)

KRX ETF 시장에서 동적 후보군을 수집하고,
pre-filter / hard-exclusion을 적용한다.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# 레버리지/인버스 키워드 (ETF 이름 기반 판별)
_INVERSE_KEYWORDS = ["인버스", "inverse", "곰", "bear"]
_LEVERAGED_KEYWORDS = [
    "레버리지",
    "leverage",
    "2x",
    "2X",
    "3x",
    "3X",
    "불",
]
_SYNTHETIC_KEYWORDS = ["합성", "synthetic"]


def _name_contains(name: str, keywords: List[str]) -> bool:
    """ETF 이름에 키워드 포함 여부."""
    name_lower = name.lower()
    return any(kw.lower() in name_lower for kw in keywords)


def fetch_krx_etf_list() -> pd.DataFrame:
    """
    KRX ETF 전체 목록을 가져온다.

    Returns:
        DataFrame with columns: code, name, ...
        빈 DataFrame if fetch 실패.
    """
    try:
        import FinanceDataReader as fdr

        etf_list = fdr.StockListing("ETF/KR")
        if etf_list is None or etf_list.empty:
            logger.warning("[CANDIDATE_POOL] KRX ETF 목록이 비어있습니다.")
            return pd.DataFrame()

        # 컬럼 정규화
        col_map: Dict[str, str] = {}
        for c in etf_list.columns:
            cl = str(c).lower()
            if cl in ("code", "symbol", "종목코드", "ticker"):
                col_map[c] = "code"
            elif cl in ("name", "종목명", "종목이름"):
                col_map[c] = "name"
            elif cl in ("listingdate", "상장일"):
                col_map[c] = "listing_date"

        if col_map:
            etf_list = etf_list.rename(columns=col_map)

        if "code" not in etf_list.columns:
            etf_list = etf_list.reset_index()
            if "Symbol" in etf_list.columns:
                etf_list = etf_list.rename(columns={"Symbol": "code"})
            elif "Code" in etf_list.columns:
                etf_list = etf_list.rename(columns={"Code": "code"})

        etf_list["code"] = etf_list["code"].astype(str).str.zfill(6)

        logger.info("[CANDIDATE_POOL] KRX ETF 목록 수집 완료: " f"{len(etf_list)}종목")
        return etf_list

    except ImportError:
        logger.error(
            "[CANDIDATE_POOL] FinanceDataReader 미설치. "
            "pip install finance-datareader"
        )
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"[CANDIDATE_POOL] ETF 목록 수집 실패: {e}")
        return pd.DataFrame()


def classify_etf(name: str) -> Dict[str, bool]:
    """ETF 이름으로 인버스/레버리지/합성 여부 판별."""
    return {
        "is_inverse": _name_contains(name, _INVERSE_KEYWORDS),
        "is_leveraged": _name_contains(name, _LEVERAGED_KEYWORDS),
        "is_synthetic": _name_contains(name, _SYNTHETIC_KEYWORDS),
    }


def _check_listing_days(row: pd.Series, min_days: int, today: date) -> bool:
    """상장일 기준 min_listing_days 충족 여부 확인."""
    listing_date = row.get("listing_date")
    if listing_date is None or pd.isna(listing_date):
        # 상장일 정보가 없으면 보수적으로 통과 (나중에 데이터로 재필터)
        return True
    try:
        if isinstance(listing_date, str):
            ld = pd.to_datetime(listing_date).date()
        elif hasattr(listing_date, "date"):
            ld = listing_date.date()
        else:
            ld = pd.Timestamp(listing_date).date()
        days_since = (today - ld).days
        return days_since >= min_days
    except Exception:
        return True


def build_candidate_pool(
    config: Dict[str, Any],
) -> Tuple[List[str], Dict[str, str], List[Dict[str, Any]]]:
    """
    Candidate Pool을 구성한다.

    Args:
        config: CANDIDATE_POOL_CONFIG

    Returns:
        (eligible_tickers, ticker_name_map, excluded_with_reasons)
    """
    etf_list = fetch_krx_etf_list()
    if etf_list.empty:
        logger.error("[CANDIDATE_POOL] ETF 목록이 비어있어 후보군 생성 불가.")
        return (
            [],
            {},
            [{"ticker": "ALL", "reason": "ETF 목록 수집 실패"}],
        )

    today = date.today()
    min_listing = config.get("min_listing_days", 180)

    eligible: List[str] = []
    ticker_name_map: Dict[str, str] = {}
    excluded: List[Dict[str, Any]] = []

    for _, row in etf_list.iterrows():
        ticker = str(row.get("code", "")).strip()
        name = str(row.get("name", "")).strip()

        if not ticker or len(ticker) < 4:
            continue

        cls = classify_etf(name)

        # Hard exclusion: 인버스
        if config.get("exclude_inverse", True) and cls["is_inverse"]:
            excluded.append(
                {
                    "ticker": ticker,
                    "name": name,
                    "reason": "is_inverse",
                }
            )
            continue

        # Hard exclusion: 레버리지
        if config.get("exclude_leveraged", True) and cls["is_leveraged"]:
            excluded.append(
                {
                    "ticker": ticker,
                    "name": name,
                    "reason": "is_leveraged",
                }
            )
            continue

        # Hard exclusion: 합성
        if config.get("exclude_synthetic", True) and cls["is_synthetic"]:
            excluded.append(
                {
                    "ticker": ticker,
                    "name": name,
                    "reason": "is_synthetic",
                }
            )
            continue

        # Pre-filter: 상장일 >= min_listing_days
        if not _check_listing_days(row, min_listing, today):
            excluded.append(
                {
                    "ticker": ticker,
                    "name": name,
                    "reason": (f"listing_days < {min_listing}"),
                }
            )
            continue

        eligible.append(ticker)
        ticker_name_map[ticker] = name

    max_cand = config.get("max_candidates", 200)
    if len(eligible) > max_cand:
        cut = eligible[max_cand:]
        for t in cut:
            excluded.append(
                {
                    "ticker": t,
                    "name": ticker_name_map.get(t, ""),
                    "reason": (f"max_candidates({max_cand}) 초과"),
                }
            )
            # 절단된 종목은 name_map에서도 제거
            ticker_name_map.pop(t, None)
        eligible = eligible[:max_cand]

    logger.info(f"[CANDIDATE_POOL] 적격={len(eligible)}, " f"제외={len(excluded)}")
    return eligible, ticker_name_map, excluded
