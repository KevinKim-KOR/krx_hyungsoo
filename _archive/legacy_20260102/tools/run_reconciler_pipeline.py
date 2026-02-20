import subprocess
import sys
import json
import hashlib
import shutil
from pathlib import Path
from datetime import datetime
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))

BASE_DIR = Path(__file__).parent.parent
RECON_TOOL = BASE_DIR / "tools" / "reconcile_phase_c.py"
OUTPUT_DIR = BASE_DIR / "reports" / "phase_c"
SUMMARY_PATH = OUTPUT_DIR / "recon_summary.json"
DAILY_PATH = OUTPUT_DIR / "recon_daily.jsonl"
DETERMINISM_REPORT = OUTPUT_DIR / "recon_determinism_report.json"

def calculate_file_hash(path):
    if not path.exists(): return None
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(4096), b""):
            sha.update(b)
    return sha.hexdigest()

def run_reconciler(run_id):
    print(f">> Running Reconciler (Run {run_id})...")
    result = subprocess.run([sys.executable, str(RECON_TOOL)], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Reconciler Failed: {result.stderr}")
        return False
    
    # Snapshot
    s_hash = calculate_file_hash(SUMMARY_PATH)
    d_hash = calculate_file_hash(DAILY_PATH)
    
    # Load summary for detailed check
    try:
        with open(SUMMARY_PATH, "r", encoding="utf-8") as f:
            summary = json.load(f)
    except:
        summary = {}

    return {
        "success": True,
        "summary_hash": s_hash,
        "daily_hash": d_hash,
        "summary_content": summary
    }

def main():
    print(">>> Starting Phase C-R.5 Pipeline (Determinism & Provenance Check)")
    
    # Run 1
    r1 = run_reconciler(1)
    if not r1["success"]: sys.exit(1)
    shutil.copy(SUMMARY_PATH, OUTPUT_DIR / "recon_summary_r1.json")
    
    # Run 2
    r2 = run_reconciler(2)
    if not r2["success"]: sys.exit(1)
    shutil.copy(SUMMARY_PATH, OUTPUT_DIR / "recon_summary_r2.json")
    
    # Compare
    match = (r1["summary_hash"] == r2["summary_hash"])
    # Ignore Generated At? 
    # The summary contains "generated_at" and "provenance.generated_at" which change every run.
    # Therefore precise HASH match will FAIL naturally.
    # We must compare CONTENT excluding timestamps.
    
    s1 = r1["summary_content"]
    s2 = r2["summary_content"]
    
    def clean(d):
        c = d.copy()
        c.pop("generated_at", None)
        if "provenance" in c:
            c["provenance"] = c["provenance"].copy()
            c["provenance"].pop("generated_at", None)
            # Reconciler sources mtime might also change if we touched files? No, readonly.
        return c

    s1_clean = clean(s1)
    s2_clean = clean(s2)
    
    # Helper to hash dict
    def hash_obj(o):
        return hashlib.sha256(json.dumps(o, sort_keys=True).encode()).hexdigest()

    h1_clean = hash_obj(s1_clean)
    h2_clean = hash_obj(s2_clean)
    
    determinism_match = (h1_clean == h2_clean)
    
    report = {
        "phase": "C-R.5",
        "generated_at": datetime.now(KST).isoformat(),
        "determinism": {
            "run1_hash_clean": h1_clean,
            "run2_hash_clean": h2_clean,
            "match": determinism_match,
            "row_count_match": s1["counts"]["L1_actions"] == s2["counts"]["L1_actions"], # Approximate
        }
    }
    
    print(f"Determinism Check: {determinism_match} (R1={h1_clean[:8]} R2={h2_clean[:8]})")
    
    with open(DETERMINISM_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        
    if not determinism_match:
        # Critical Error Injection
        print("!!! DETERMINISM CHECK FAILED !!!")
        error_summary = {
            "status": "error",
            "schema": "RECON_SUMMARY_V1",
            "generated_at": datetime.now(KST).isoformat(),
            "error": {
                "code": "IC_RECON_NON_DETERMINISTIC",
                "message_ko": "심각: Reconciler 결과가 매 실행마다 다릅니다. (Determinism Check Failed)"
            },
            "provenance": s1.get("provenance", {}) # Keep provenance if available
        }
        with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
            json.dump(error_summary, f, indent=2)
        sys.exit(1)
        
    # Check Provenance Existence (Gate C-R.5.2)
    if "provenance" not in s1 or not s1["provenance"].get("sources"):
        print("!!! PROVENANCE MISSING !!!")
         # Critical Error Injection
        error_summary = {
            "status": "error",
            "schema": "RECON_SUMMARY_V1",
            "generated_at": datetime.now(KST).isoformat(),
            "error": {
                "code": "IC_PROVENANCE_MISSING",
                "message_ko": "심각: 리포트의 원본 출처(Provenance) 정보가 누락되었습니다."
            }
        }
        with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
            json.dump(error_summary, f, indent=2)
        sys.exit(1)
        
    print(">>> Pipeline Success. Restoring R1 as Truth (earlier timestamp).")
    # Restore R1 (Artifact of choice)
    shutil.copy(OUTPUT_DIR / "recon_summary_r1.json", SUMMARY_PATH)

if __name__ == "__main__":
    main()
