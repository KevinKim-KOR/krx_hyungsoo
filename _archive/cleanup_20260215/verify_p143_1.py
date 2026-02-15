
import sys
from pathlib import Path
import json

# Add project root
BASE_DIR = Path(__file__).parent
sys.path.append(str(BASE_DIR))

from app.utils.portfolio_normalize import normalize_portfolio

def test_normalize():
    print("Testing normalize_portfolio...")
    
    # Case 1: Inconsistent Total Value
    test_pl = {
        "asof": "2026-02-14",
        "cash": 1000.0,
        "positions": [
            {"ticker": "A005930", "quantity": 10, "current_price": 500.0}
        ],
        "total_value": 99999999.0 # Wrong
    }
    
    normalized = normalize_portfolio(test_pl)
    expected_total = 1000.0 + (10 * 500.0)
    
    assert normalized['total_value'] == expected_total, f"Total Mismatch: {normalized['total_value']} vs {expected_total}"
    assert normalized['positions'][0]['weight_pct'] > 0, "Weight calc fail"
    
    print("PASS: Total Value Fixed")
    
    # Case 2: Missing Asof
    test_pl2 = {
        "cash": 100,
        "positions": []
    }
    norm2 = normalize_portfolio(test_pl2)
    assert norm2['asof'] is not None, "Asof not injected"
    print(f"PASS: Asof Injected ({norm2['asof']})")
    
if __name__ == "__main__":
    test_normalize()
