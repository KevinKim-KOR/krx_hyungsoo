"""
Order Plan Generator (D-P.58)

Reco + Portfolio 기반으로 실제 주문안(매수/매도 수량) 생성
- Fail-Closed: Portfolio 또는 Reco 없으면 BLOCKED
- No External Send: 주문은 생성만, 실행 없음
"""

import json
import hashlib
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

BASE_DIR = Path(__file__).parent.parent

# Input paths
PORTFOLIO_LATEST = BASE_DIR / "state" / "portfolio" / "latest" / "portfolio_latest.json"
RECO_LATEST = BASE_DIR / "reports" / "live" / "reco" / "latest" / "reco_latest.json"

# Output paths
ORDER_PLAN_DIR = BASE_DIR / "reports" / "live" / "order_plan"
ORDER_PLAN_LATEST = ORDER_PLAN_DIR / "latest" / "order_plan_latest.json"
ORDER_PLAN_SNAPSHOTS = ORDER_PLAN_DIR / "snapshots"

# Constraints
MAX_SINGLE_WEIGHT_PCT = 30
MIN_ORDER_AMOUNT = 100000


def safe_load_json(path: Path) -> Optional[Dict]:
    """JSON 파일 안전 로드"""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def calculate_sha256(data: Any) -> str:
    """SHA256 해시 계산"""
    json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()


def generate_blocked_plan(reason: str) -> Dict[str, Any]:
    """BLOCKED 주문안 생성"""
    now = datetime.now()
    asof = now.isoformat()
    plan_id = str(uuid.uuid4())
    
    snapshot_filename = f"order_plan_{now.strftime('%Y%m%d_%H%M%S')}.json"
    snapshot_ref = f"reports/live/order_plan/snapshots/{snapshot_filename}"
    
    plan = {
        "schema": "ORDER_PLAN_V1",
        "asof": asof,
        "plan_id": plan_id,
        "decision": "BLOCKED",
        "reason": reason,
        "source_refs": {
            "reco_ref": "reports/live/reco/latest/reco_latest.json",
            "portfolio_ref": "state/portfolio/latest/portfolio_latest.json"
        },
        "orders": [],
        "summary": {
            "total_buy_amount": 0,
            "total_sell_amount": 0,
            "net_cash_change": 0,
            "estimated_cash_after": 0,
            "estimated_cash_ratio_pct": 0,
            "buy_count": 0,
            "sell_count": 0
        },
        "constraints_applied": {
            "max_single_weight_pct": MAX_SINGLE_WEIGHT_PCT,
            "min_order_amount": MIN_ORDER_AMOUNT
        },
        "snapshot_ref": snapshot_ref,
        "evidence_refs": ["reports/live/order_plan/latest/order_plan_latest.json"],
        "integrity": {
            "payload_sha256": calculate_sha256([])
        }
    }
    
    # Save
    _save_plan(plan, snapshot_filename)
    
    return {
        "result": "OK",
        "decision": "BLOCKED",
        "reason": reason,
        "plan_id": plan_id,
        "snapshot_ref": snapshot_ref
    }


def _save_plan(plan: Dict, snapshot_filename: str):
    """주문안 저장"""
    ORDER_PLAN_LATEST.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = ORDER_PLAN_LATEST.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(ORDER_PLAN_LATEST)
    
    ORDER_PLAN_SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    shutil.copy(ORDER_PLAN_LATEST, ORDER_PLAN_SNAPSHOTS / snapshot_filename)


def generate_order_plan() -> Dict[str, Any]:
    """
    주문안 생성
    
    Returns:
        {result, decision, reason, plan_id, snapshot_ref, ...}
    """
    now = datetime.now()
    
    # Load portfolio
    portfolio = safe_load_json(PORTFOLIO_LATEST)
    if not portfolio:
        return generate_blocked_plan("NO_PORTFOLIO")
    
    # Load reco
    reco = safe_load_json(RECO_LATEST)
    if not reco:
        return generate_blocked_plan("NO_RECO")
    
    reco_decision = reco.get("decision", "UNKNOWN")
    reco_reason = reco.get("reason", "")
    
    if reco_decision in ("BLOCKED", "EMPTY_RECO", "MISSING_RECO"):
        # Case 1: Reco itself is blocked or empty with a reason
        # Propagate reason for visibility (D-P.58 Enhanced)
        if reco_reason:
            # Avoid double prefix if already has it (unlikely but safe)
            prefix = "RECO_" if not reco_reason.startswith("RECO_") and not reco_reason.startswith("NO_") else ""
            return generate_blocked_plan(f"{prefix}{reco_reason}")
        return generate_blocked_plan("EMPTY_RECO")
    
    recommendations = reco.get("recommendations", [])
    if not recommendations:
        # Reco decision was OK/GENERATED but list is empty -> EMPTY_RECO
        return generate_blocked_plan("EMPTY_RECO")
    
    # Build current holdings map
    cash = portfolio.get("cash", 0)
    holdings = portfolio.get("holdings", [])
    total_value = portfolio.get("total_value", 0)
    
    if total_value <= 0:
        return generate_blocked_plan("INVALID_PORTFOLIO")
    
    # Check for NO_CASH case (Optional but helpful)
    # If cash is 0 and we need to buy, it might be an issue, but let's stick to INVALID_PORTFOLIO for now if total_value is bad.
    # If total_value > 0 but cash is 0, it's technically valid (fully invested), so don't block.
    
    holdings_map = {}
    for h in holdings:
        ticker = h.get("ticker", "")
        holdings_map[ticker] = {
            "quantity": h.get("quantity", 0),
            "market_value": h.get("market_value", 0),
            "current_price": h.get("current_price", 0),
            "current_weight_pct": round(h.get("market_value", 0) / total_value * 100, 2)
        }
    
    # Generate orders from recommendations
    orders = []
    total_buy_amount = 0
    total_sell_amount = 0
    
    for r in recommendations:
        action = r.get("action", "HOLD")
        ticker = r.get("ticker", "")
        name = r.get("name", "")
        target_weight_pct = r.get("weight_pct", 0)
        signal_score = r.get("signal_score", 0)
        estimated_price = r.get("price", 0) or 35000  # fallback price
        
        # Get current holding
        current = holdings_map.get(ticker, {"quantity": 0, "market_value": 0, "current_weight_pct": 0, "current_price": estimated_price})
        current_weight_pct = current.get("current_weight_pct", 0)
        current_price = current.get("current_price", estimated_price)
        
        if current_price <= 0:
            current_price = estimated_price
        
        # Calculate delta
        delta_weight_pct = target_weight_pct - current_weight_pct
        order_amount = round(delta_weight_pct / 100 * total_value)
        
        # Skip small orders
        if abs(order_amount) < MIN_ORDER_AMOUNT:
            continue
        
        # Cap at max single weight
        if target_weight_pct > MAX_SINGLE_WEIGHT_PCT:
            target_weight_pct = MAX_SINGLE_WEIGHT_PCT
            delta_weight_pct = target_weight_pct - current_weight_pct
            order_amount = round(delta_weight_pct / 100 * total_value)
        
        estimated_quantity = int(order_amount / current_price) if current_price > 0 else 0
        
        order = {
            "action": action,
            "ticker": ticker,
            "name": name,
            "target_weight_pct": target_weight_pct,
            "current_weight_pct": current_weight_pct,
            "delta_weight_pct": round(delta_weight_pct, 2),
            "order_amount": order_amount,
            "estimated_quantity": estimated_quantity,
            "signal_score": signal_score
        }
        orders.append(order)
        
        if action == "BUY":
            total_buy_amount += abs(order_amount)
        elif action == "SELL":
            total_sell_amount += abs(order_amount)
    
    # Calculate summary
    net_cash_change = total_sell_amount - total_buy_amount
    estimated_cash_after = cash + net_cash_change
    estimated_cash_ratio_pct = round(estimated_cash_after / total_value * 100, 1) if total_value > 0 else 0
    
    buy_count = len([o for o in orders if o["action"] == "BUY"])
    sell_count = len([o for o in orders if o["action"] == "SELL"])
    
    # Build plan
    asof = now.isoformat()
    plan_id = str(uuid.uuid4())
    snapshot_filename = f"order_plan_{now.strftime('%Y%m%d_%H%M%S')}.json"
    snapshot_ref = f"reports/live/order_plan/snapshots/{snapshot_filename}"
    
    plan = {
        "schema": "ORDER_PLAN_V1",
        "asof": asof,
        "plan_id": plan_id,
        "decision": "GENERATED" if orders else "EMPTY",
        "reason": "SUCCESS" if orders else "NO_ORDERS",
        "source_refs": {
            "reco_ref": "reports/live/reco/latest/reco_latest.json",
            "portfolio_ref": "state/portfolio/latest/portfolio_latest.json"
        },
        "orders": orders,
        "summary": {
            "total_buy_amount": total_buy_amount,
            "total_sell_amount": total_sell_amount,
            "net_cash_change": net_cash_change,
            "estimated_cash_after": estimated_cash_after,
            "estimated_cash_ratio_pct": estimated_cash_ratio_pct,
            "buy_count": buy_count,
            "sell_count": sell_count
        },
        "constraints_applied": {
            "max_single_weight_pct": MAX_SINGLE_WEIGHT_PCT,
            "min_order_amount": MIN_ORDER_AMOUNT
        },
        "snapshot_ref": snapshot_ref,
        "evidence_refs": ["reports/live/order_plan/latest/order_plan_latest.json"],
        "integrity": {
            "payload_sha256": calculate_sha256(orders)
        }
    }
    
    _save_plan(plan, snapshot_filename)
    
    return {
        "result": "OK",
        "decision": plan["decision"],
        "reason": plan["reason"],
        "plan_id": plan_id,
        "orders_count": len(orders),
        "total_buy_amount": total_buy_amount,
        "total_sell_amount": total_sell_amount,
        "snapshot_ref": snapshot_ref
    }


def get_order_plan_latest() -> Optional[Dict]:
    """최신 주문안 조회"""
    return safe_load_json(ORDER_PLAN_LATEST)


if __name__ == "__main__":
    result = generate_order_plan()
    print(json.dumps(result, indent=2, ensure_ascii=False))
