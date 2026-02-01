import subprocess
import sys

def run_verification():
    print("Running P93 Verification...")
    try:
        # Run Dashboard
        result = subprocess.run(
            [sys.executable, "-m", "app.utils.ops_dashboard"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            check=True
        )
        output = result.stdout
        
        # Criteria 1: Zero MISSING/UNKNOWN
        failures = []
        if "MISSING" in output:
            failures.append("Found 'MISSING' in output")
        if "UNKNOWN" in output and "UNKNOWN_RESPONSE" not in output: # UNKNOWN_RESPONSE is what we removed, but check if any UNKNOWN remains
             failures.append("Found 'UNKNOWN' in output")
        if "UNMAPPED_CASE" in output:
             failures.append("Found 'UNMAPPED_CASE'")
        
        # Criteria 2: Watcher Lines
        watchers = ["Spike Watch", "Holding Watch"]
        for w in watchers:
            if w not in output:
                failures.append(f"{w} line missing")
            else:
                # Find the line
                line = [l for l in output.split('\n') if w in l][0]
                print(f"[{w}] Line: {line.strip()}")
                
                # Check Source: FILE
                if "Source: FILE" not in line:
                    failures.append(f"{w} missing 'Source: FILE'")
                
                # Check Reason matches ENUM regex ^[A-Z0-9_]+$
                import re
                match = re.search(r"Reason=([A-Z0-9_]+)", line)
                if not match:
                    failures.append(f"{w} Reason not ENUM-compliant")
                else:
                    print(f"[{w}] Valid Reason: {match.group(1)}")

        if failures:
            print("\n❌ Verification FAILED:")
            for f in failures:
                print(f"- {f}")
            sys.exit(1)
        else:
            print("\n✅ Verification PASS: Zero MISSING/UNKNOWN, Source: FILE confirmed.")
            sys.exit(0)

    except Exception as e:
        print(f"Execution Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_verification()
