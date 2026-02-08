
import json
from pathlib import Path

path = Path("krx_hyungsoo/reports/ops/summary/ops_summary_latest.json")
if not path.exists():
    print("FILE_NOT_FOUND")
else:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        mode = data.get("manual_loop", {}).get("mode", "MISSING")
        print(f"MODE={mode}")
    except Exception as e:
        print(f"ERROR={e}")
