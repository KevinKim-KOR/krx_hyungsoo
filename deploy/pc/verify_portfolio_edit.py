
import json
from pathlib import Path
import datetime
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))

PORTFOLIO_PATH = Path("state/portfolio/latest/portfolio_latest.json")

def verify_edit():
    print("Loading Portfolio...")
    if not PORTFOLIO_PATH.exists():
        print("Portfolio not found.")
        return

    data = json.loads(PORTFOLIO_PATH.read_text(encoding="utf-8"))
    print(f"Original Cash: {data.get('cash')}")
    
    # Simulate Edit
    new_cash = data.get("cash", 0) + 100
    data["cash"] = new_cash
    data["updated_at"] = datetime.datetime.now(KST).isoformat()
    
    print(f"Saving New Cash: {new_cash}")
    json.dumps(data, indent=2) # Check serialization
    
    # Write back (Simulation of UI Save)
    PORTFOLIO_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    
    # Reload
    reloaded = json.loads(PORTFOLIO_PATH.read_text(encoding="utf-8"))
    print(f"Reloaded Cash: {reloaded.get('cash')}")
    
    if reloaded.get("cash") == new_cash:
        print("SUCCESS: Portfolio Edit Persisted.")
    else:
        print("FAILURE: Value mismatch.")

if __name__ == "__main__":
    verify_edit()
