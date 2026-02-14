
import json
import hashlib
import sys
import shutil
from pathlib import Path
from datetime import datetime
import sys

# Add project root to path
BASE_DIR = Path(__file__).parent.parent.parent
sys.path.append(str(BASE_DIR))

from app.utils.admin_utils import normalize_portfolio

# Config
BASE_DIR = Path(__file__).parent.parent.parent
BUNDLE_PATH = BASE_DIR / "state" / "strategy_bundle" / "latest" / "strategy_bundle_latest.json"
PORTFOLIO_PATH = BASE_DIR / "state" / "portfolio" / "latest" / "portfolio_latest.json"
SNAPSHOT_DIR = BASE_DIR / "state" / "portfolio" / "snapshots"
FORBIDDEN_KEYS = ["token", "secret", "password", "apikey", "key"]

def compute_sha256(data):
    json_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()

def scan_forbidden_keys(data, path=""):
    """Recursively check for forbidden keys"""
    if isinstance(data, dict):
        for k, v in data.items():
            if any(bad in k.lower() for bad in FORBIDDEN_KEYS):
                return f"Forbidden key found: {path}.{k}"
            err = scan_forbidden_keys(v, f"{path}.{k}")
            if err: return err
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            err = scan_forbidden_keys(item, f"{path}[{idx}]")
            if err: return err
    return None

def main():
    print("[ApplyPortfolioOverride] Starting...")
    
    # 1. Load Bundle
    if not BUNDLE_PATH.exists():
        print("[SKIP] No strategy bundle found.")
        sys.exit(0)
        
    try:
        bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[ERROR] Failed to load bundle: {e}")
        sys.exit(1)
        
    # 2. Check Override Section
    strategy = bundle.get("strategy", {})
    override = strategy.get("state_override", {})
    if not override:
        print("[SKIP] No state_override in bundle.")
        sys.exit(0)
        
    pf_override = override.get("portfolio", {})
    if not pf_override:
        print("[SKIP] No portfolio override in bundle.")
        sys.exit(0)
        
    # 3. Check Enabled
    if not pf_override.get("enabled", False):
        print("[SKIP] Portfolio override disabled (enabled!=true).")
        sys.exit(0)
        
    # 4. Validate Schema & Integrity
    payload = pf_override.get("payload")
    if not payload:
        print("[BLOCKED] Payload missing.")
        # We don't exit 1 here to avoid breaking the script flow, just block application
        sys.exit(0)
        
    expected_sha = pf_override.get("integrity", {}).get("payload_sha256")
    actual_sha = compute_sha256(payload)
    
    if expected_sha and expected_sha != actual_sha:
        print(f"[BLOCKED] Integrity mismatch! Expected={expected_sha[:8]}, Actual={actual_sha[:8]}")
        sys.exit(0)
        
    # 5. Security Scan
    err = scan_forbidden_keys(payload)
    if err:
        print(f"[BLOCKED] Security violation: {err}")
        sys.exit(0)
        
    # 6. Check Freshness (Optional: Don't apply if older than current?)
    # For now, we trust the bundle as "Master Intent". 
    # But checking if payload is identical to current prevents redundant writes.
    
    current_portfolio = None
    if PORTFOLIO_PATH.exists():
        try:
            current_portfolio = json.loads(PORTFOLIO_PATH.read_text(encoding="utf-8"))
        except: pass
        
    # Compare logic (ignoring 'source' field which we inject)
    # Actually, simpler to just checking if we already applied this SHA.
    # But let's just proceed with safe apply.
    
    # 7. Apply
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Inject Source Info into Payload before saving
    final_portfolio = payload.copy()
    final_portfolio["source"] = "BUNDLE_OVERRIDE"
    final_portfolio["applied_at"] = datetime.utcnow().isoformat() + "Z"
    final_portfolio["bundle_id"] = bundle.get("bundle_id")
    final_portfolio["integrity"] = {"payload_sha256": actual_sha}
    
    # P143: Normalize SSOT
    final_portfolio = normalize_portfolio(final_portfolio)
    
    # Backup
    if PORTFOLIO_PATH.exists():
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_path = SNAPSHOT_DIR / f"portfolio_backup_{ts}.json"
        shutil.copy(PORTFOLIO_PATH, backup_path)
        
    # Save Latest
    json_str = json.dumps(final_portfolio, indent=2, ensure_ascii=False)
    PORTFOLIO_PATH.write_text(json_str, encoding="utf-8")
    
    # Save Snapshot (as per requirement)
    # "state/portfolio/snapshots/portfolio_YYYYMMDD_HHMMSS.json"
    ts_now = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    snap_path = SNAPSHOT_DIR / f"portfolio_{ts_now}.json"
    snap_path.write_text(json_str, encoding="utf-8")
    
    print(f"PORTFOLIO_OVERRIDE_APPLIED source=BUNDLE sha={actual_sha[:8]} asof={pf_override.get('asof')}")

    # P139: Extract Auxiliary Holding Timing
    aux = strategy.get("auxiliary", {})
    timing_data = aux.get("holding_timing")
    
    if timing_data:
        TIMING_DIR = BASE_DIR / "reports" / "oci" / "holding_timing" / "latest"
        TIMING_DIR.mkdir(parents=True, exist_ok=True)
        TIMING_PATH = TIMING_DIR / "holding_timing_latest.json"
        
        try:
            TIMING_PATH.write_text(json.dumps(timing_data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"HOLDING_TIMING_EXTRACTED asof={timing_data.get('asof')}")
        except Exception as e:
            print(f"[WARN] Failed to save holding timing: {e}")
    else:
        print("[INFO] No holding timing data in bundle.")


if __name__ == "__main__":
    main()
