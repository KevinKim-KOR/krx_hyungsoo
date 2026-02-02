# -*- coding: utf-8 -*-
"""
Holding Action Generator (P100-3-REV)

PC에서 포트폴리오 기준 보유 종목별 액션(HOLD/ADD/REDUCE/SELL) 생성.
- NO MOCK DATA IN APP CODE (RedTeam Hardening)
- Fail-Closed: PORTFOLIO_INCONSISTENT, INSUFFICIENT_PICKS safety modes
- ENUM-only reason, sanitized reason_detail
- Deterministic: 동일 입력 → 동일 결과 (ticker asc 정렬)

Usage:
    from app.scoring.holding_action import compute_actions
    result = compute_actions(portfolio, top_picks, regime_code)
"""

import json
import hashlib
import re
from typing import Dict, List, Any, Optional

# ENUM-only validation
ENUM_ONLY_PATTERN = re.compile(r"^[A-Z0-9_]+$")

# Action Enums
VALID_ACTIONS = {"HOLD", "ADD", "REDUCE", "SELL"}
VALID_CONFIDENCE = {"LOW", "MEDIUM", "HIGH"}

# Safety thresholds
MIN_TOP_PICKS_FOR_FULL_MODE = 4  # 4개 미만이면 안전모드


def sanitize_reason_detail(text: str, max_len: int = 240) -> str:
    """reason_detail sanitize: 개행 제거, 특수문자 escape, 길이 제한"""
    if not text:
        return ""
    clean = text.replace("\n", " ").replace("\r", "").replace("\t", " ")
    clean = clean.replace('"', "'")
    clean = " ".join(clean.split())
    return clean[:max_len]


def validate_enum_only(value: str) -> bool:
    """ENUM-only regex validation: ^[A-Z0-9_]+$"""
    return bool(ENUM_ONLY_PATTERN.match(value))


def compute_items_hash(items: List[Dict]) -> str:
    """Compute hash of items for determinism verification"""
    sorted_items = sorted(items, key=lambda x: x.get("ticker", ""))
    data = json.dumps(sorted_items, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def compute_actions(
    portfolio: Dict,
    top_picks: List[Dict],
    regime_code: str = "NEUTRAL"
) -> Dict:
    """
    포트폴리오 보유 종목별 액션 계산.
    
    Args:
        portfolio: Portfolio dict with cash, holdings, total_value
        top_picks: List of {ticker, score, reason, reason_detail} from scorer
        regime_code: RISK_ON | RISK_OFF | NEUTRAL | VOLATILE
    
    Returns:
        Dict with status, reason, reason_detail, items
    """
    result = {
        "status": "SKIPPED",
        "reason": "UNKNOWN_ERROR",
        "reason_detail": "",
        "items": [],
        "items_hash": ""
    }
    
    # =========================================================================
    # 1. Portfolio Validation (Fail-Closed)
    # =========================================================================
    if portfolio is None:
        result["reason"] = "PORTFOLIO_MISSING"
        result["reason_detail"] = sanitize_reason_detail("Portfolio data is None")
        return result
    
    holdings = portfolio.get("holdings", []) or []
    total_value = portfolio.get("total_value", 0) or 0
    cash = portfolio.get("cash", 0) or 0
    
    # 2-A. Portfolio Inconsistency Check (Fail-Closed)
    if len(holdings) > 0 and total_value <= 0:
        result["status"] = "SKIPPED"
        result["reason"] = "PORTFOLIO_INCONSISTENT"
        result["reason_detail"] = sanitize_reason_detail(
            f"holdings>0 ({len(holdings)}) but total_value<=0 ({total_value})"
        )
        return result
    
    # 3-A. NO_ACTION conditions
    if len(holdings) == 0:
        if total_value <= 0 or total_value == cash:
            result["status"] = "NO_ACTION"
            result["reason"] = "NO_ACTION_CASH_ONLY" if cash > 0 else "NO_ACTION_PORTFOLIO_EMPTY"
            result["reason_detail"] = sanitize_reason_detail(
                f"No holdings, cash={cash}, total_value={total_value}"
            )
            result["items"] = []
            result["items_hash"] = compute_items_hash([])
            return result
    
    # =========================================================================
    # 2. Top Picks Validation (Safety Mode)
    # =========================================================================
    top_picks = top_picks or []
    picks_count = len(top_picks)
    top_picks_tickers = {p.get("ticker") for p in top_picks if p.get("ticker")}
    
    # 2-B. Safety Mode Logic
    is_safe_mode = picks_count < MIN_TOP_PICKS_FOR_FULL_MODE
    is_insufficient = picks_count == 0
    
    if is_insufficient:
        # top_picks == 0: SKIPPED
        result["status"] = "SKIPPED"
        result["reason"] = "INSUFFICIENT_PICKS"
        result["reason_detail"] = sanitize_reason_detail(
            f"top_picks count is 0, cannot generate actions safely"
        )
        result["items"] = []
        result["items_hash"] = compute_items_hash([])
        return result
    
    # =========================================================================
    # 3. Calculate Actions
    # =========================================================================
    items = []
    held_tickers = set()
    
    # 3-1. Process holdings (보유O)
    for h in holdings:
        ticker = h.get("code") or h.get("ticker") or ""
        if not ticker:
            continue
        held_tickers.add(ticker)
        
        in_picks = ticker in top_picks_tickers
        
        if in_picks:
            # 보유O + 추천O
            if is_safe_mode:
                # 안전모드: HOLD만
                action = "HOLD"
                confidence = "LOW"
                reason = "DEGRADED_INPUT"
                detail = f"safe_mode: picks={picks_count}<{MIN_TOP_PICKS_FOR_FULL_MODE}"
            else:
                # 정상모드
                action = "HOLD"
                confidence = "MEDIUM"
                reason = "HOLD_TOP_PICK"
                detail = "in_top_picks"
                
                # RISK_ON에서만 ADD 고려 (매우 보수적)
                # 현재는 ADD 조건 비활성화 (안전 우선)
                # if regime_code == "RISK_ON":
                #     action = "ADD"
                #     confidence = "LOW"
                #     reason = "ADD_RISK_ON"
        else:
            # 보유O + 추천X
            if is_safe_mode:
                # 안전모드: HOLD만
                action = "HOLD"
                confidence = "LOW"
                reason = "DEGRADED_INPUT"
                detail = f"safe_mode: picks={picks_count}<{MIN_TOP_PICKS_FOR_FULL_MODE}"
            else:
                # 정상모드: REDUCE
                action = "REDUCE"
                confidence = "LOW"
                reason = "REDUCE_NOT_IN_PICKS"
                detail = "not_in_top_picks"
        
        items.append({
            "ticker": ticker,
            "action": action,
            "confidence": confidence,
            "reason": reason,
            "reason_detail": sanitize_reason_detail(detail)
        })
    
    # 3-2. Process NEW_ENTRY (보유X + 추천O)
    if not is_safe_mode:
        for pick in top_picks:
            ticker = pick.get("ticker")
            if ticker and ticker not in held_tickers:
                items.append({
                    "ticker": ticker,
                    "action": "ADD",
                    "confidence": "LOW",
                    "reason": "NEW_ENTRY",
                    "reason_detail": sanitize_reason_detail("not_held_but_recommended")
                })
    # In safe mode, skip NEW_ENTRY (ADD 금지)
    
    # =========================================================================
    # 4. Sort and Finalize
    # =========================================================================
    # Ticker asc 정렬 (결정성)
    items.sort(key=lambda x: x["ticker"])
    
    # Validate all reasons are ENUM-only
    for item in items:
        if not validate_enum_only(item["reason"]):
            item["reason"] = "ACTION_COMPUTED"
    
    result["status"] = "OK"
    result["reason"] = "DEGRADED_INPUT" if is_safe_mode else "SUCCESS"
    result["reason_detail"] = sanitize_reason_detail(
        f"holdings={len(holdings)} picks={picks_count} regime={regime_code}"
    )
    result["items"] = items
    result["items_hash"] = compute_items_hash(items)
    
    return result


# For testing only - NOT for production use
if __name__ == "__main__":
    # Test with sample data
    test_portfolio = {
        "cash": 10000000,
        "holdings": [
            {"code": "069500", "name": "KODEX200", "market_value": 5000000},
            {"code": "005930", "name": "Samsung", "market_value": 3000000}
        ],
        "total_value": 18000000
    }
    test_picks = [
        {"ticker": "069500", "score": 90, "reason": "RANK_SCORE"},
        {"ticker": "229200", "score": 85, "reason": "RANK_SCORE"},
        {"ticker": "114800", "score": 80, "reason": "RANK_SCORE"},
        {"ticker": "122630", "score": 75, "reason": "RANK_SCORE"}
    ]
    result = compute_actions(test_portfolio, test_picks, "NEUTRAL")
    print(json.dumps(result, indent=2, ensure_ascii=False))
