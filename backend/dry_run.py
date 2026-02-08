from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
import subprocess
import json
from pathlib import Path
from backend.main import BASE_DIR

router = APIRouter()

DRY_RUN_generator = BASE_DIR / "app" / "generate_dry_run_record.py"
LATEST_FILE = BASE_DIR / "reports" / "live" / "dry_run_record" / "latest" / "dry_run_record_latest.json"

@router.post("/api/dry_run_record/submit")
async def submit_dry_run(confirm: bool = Query(..., description="Must be true to execute")):
    if not confirm:
        raise HTTPException(status_code=400, detail="Confirmation required")
        
    try:
        # Run generator
        result = subprocess.run(
            ["python3", str(DRY_RUN_generator), "--confirm"],
            capture_output=True, text=True, check=True
        )
        # Trigger Ops Summary Regeneration
        subprocess.run(
            ["python3", str(BASE_DIR / "app" / "generate_ops_summary.py")],
            capture_output=True, text=True
        )
        
        return JSONResponse(content={"result": "OK", "detail": "Dry Run Submitted", "output": result.stdout})
        
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Generator Failed: {e.stderr}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/dry_run_record/latest")
async def get_latest_dry_run():
    if not LATEST_FILE.exists():
        raise HTTPException(status_code=404, detail="No dry run record found")
        
    try:
        data = json.loads(LATEST_FILE.read_text(encoding="utf-8"))
        return JSONResponse(content=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
