"""
Portfolio Snapshot Generator (D-P.58)

PC UI에서 입력한 보유자산(현금/보유종목) 저장
- Atomic Write + Snapshot
- Integrity: payload_sha256
"""

import json
import hashlib
import shutil
import uuid
from datetime import datetime
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
from pathlib import Path
from typing import Dict, Any, Optional, List

BASE_DIR = Path(__file__).parent.parent

# Output paths
PORTFOLIO_DIR = BASE_DIR / "state" / "portfolio"
PORTFOLIO_LATEST = PORTFOLIO_DIR / "latest" / "portfolio_latest.json"
PORTFOLIO_SNAPSHOTS = PORTFOLIO_DIR / "snapshots"


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


def get_portfolio_latest() -> Optional[Dict]:
    """최신 포트폴리오 조회"""
    return safe_load_json(PORTFOLIO_LATEST)


def upsert_portfolio(
    cash: float,
    holdings: List[Dict],
    updated_by: str = "api"
) -> Dict[str, Any]:
    """
    포트폴리오 저장/업데이트
    
    Args:
        cash: 현금 (원)
        holdings: 보유 종목 목록 [{ticker, name, quantity, avg_price, ...}]
        updated_by: ui / api / sync
    
    Returns:
        저장 결과
    """
    now = datetime.now(KST)
    asof = now.isoformat()
    portfolio_id = str(uuid.uuid4())
    
    # Calculate market values and totals
    processed_holdings = []
    total_holdings_value = 0
    
    for h in holdings:
        ticker = h.get("ticker", "")
        name = h.get("name", "")
        quantity = h.get("quantity", 0)
        avg_price = h.get("avg_price", 0)
        current_price = h.get("current_price", avg_price)  # default to avg_price if not provided
        market_value = quantity * current_price
        
        processed_holdings.append({
            "ticker": ticker,
            "name": name,
            "quantity": quantity,
            "avg_price": avg_price,
            "current_price": current_price,
            "market_value": market_value
        })
        total_holdings_value += market_value
    
    total_value = cash + total_holdings_value
    cash_ratio_pct = round((cash / total_value * 100) if total_value > 0 else 100, 1)
    
    # Build snapshot
    snapshot_filename = f"portfolio_{now.strftime('%Y%m%d_%H%M%S')}.json"
    snapshot_ref = f"state/portfolio/snapshots/{snapshot_filename}"
    
    portfolio = {
        "schema": "PORTFOLIO_SNAPSHOT_V1",
        "asof": asof,
        "portfolio_id": portfolio_id,
        "cash": cash,
        "holdings": processed_holdings,
        "total_value": total_value,
        "cash_ratio_pct": cash_ratio_pct,
        "updated_at": asof,
        "updated_by": updated_by,
        "snapshot_ref": snapshot_ref,
        "evidence_refs": ["state/portfolio/latest/portfolio_latest.json"],
        "integrity": {
            "payload_sha256": calculate_sha256(processed_holdings)
        }
    }
    
    # Atomic write to latest
    PORTFOLIO_LATEST.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = PORTFOLIO_LATEST.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(portfolio, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(PORTFOLIO_LATEST)
    
    # Copy to snapshot
    PORTFOLIO_SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    shutil.copy(PORTFOLIO_LATEST, PORTFOLIO_SNAPSHOTS / snapshot_filename)
    
    return {
        "result": "OK",
        "portfolio_id": portfolio_id,
        "total_value": total_value,
        "cash_ratio_pct": cash_ratio_pct,
        "holdings_count": len(processed_holdings),
        "saved_to": "state/portfolio/latest/portfolio_latest.json",
        "snapshot_ref": snapshot_ref
    }


if __name__ == "__main__":
    # Test with sample data
    result = upsert_portfolio(
        cash=10000000,
        holdings=[
            {"ticker": "069500", "name": "KODEX 200", "quantity": 100, "avg_price": 35000, "current_price": 36000},
            {"ticker": "229200", "name": "KODEX 코스닥150", "quantity": 50, "avg_price": 12000, "current_price": 12500}
        ],
        updated_by="test"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
