# -*- coding: utf-8 -*-
"""
app/run_git_transport.py
Git Transport Automation (PC Only)
"""
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Any
import logging

# Setup Logger
logger = logging.getLogger("git_transport")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(h)
    logger.setLevel(logging.INFO)

BASE_DIR = Path(__file__).resolve().parent.parent

def run_cmd(cmd: List[str]) -> str:
    """Run shell command and return output"""
    try:
        res = subprocess.run(
            cmd, 
            cwd=BASE_DIR, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            encoding="utf-8", 
            check=True
        )
        return res.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {cmd} -> {e.stderr}")
        raise e

def sync_state_to_remote(confirm: bool = False) -> Dict[str, Any]:
    """
    Sync ONLY state changes to remote.
    Blocks if non-state files are dirty.
    """
    if not confirm:
        return {"result": "BLOCKED", "message": "Confirm required"}

    try:
        # 1. Check Status
        status_out = run_cmd(["git", "status", "--porcelain"])
        if not status_out:
            return {"result": "OK", "message": "Nothing to sync (Clean)"}

        lines = status_out.split("\n")
        allowed_files = []
        blocked_files = []

        for line in lines:
            # Format: " M path/to/file" or "?? path/to/file"
            path = line[3:].strip()
            
            # Allow logic: must be in state/ and end with .json and be in a 'latest' dir ideally
            # Strict: state/**/latest/*.json
            # Or just state/ for now? Let's use the strict 'state/' prefix + '.json' extension
            
            path_p = Path(path)
            # Check if path is inside 'state' folder
            is_state = "state/" in path.replace("\\", "/") 
            is_json = path.endswith(".json")
            
            if is_state and is_json:
                allowed_files.append(path)
            else:
                blocked_files.append(path)

        # 2. Safety Block
        if blocked_files:
            return {
                "result": "BLOCKED",
                "message": "코드가 변경되어 있습니다. 터미널을 사용하세요.",
                "blocked_files": blocked_files,
                "allowed_files": allowed_files
            }

        # 3. Execution
        if not allowed_files:
            return {"result": "OK", "message": "No state files to sync"}

        logger.info(f"Syncing {len(allowed_files)} files...")
        
        # Add specifically allowed files
        run_cmd(["git", "add"] + allowed_files)
        
        # Commit
        run_cmd(["git", "commit", "-m", "state: update via ui"])
        
        # Push
        run_cmd(["git", "push", "origin", "archive-rebuild"])
        
        return {
            "result": "OK",
            "message": f"Successfully synced {len(allowed_files)} files",
            "synced_files": allowed_files
        }

    except Exception as e:
        logger.error(f"Sync failed: {e}")
        return {
            "result": "FAILED",
            "message": str(e)
        }

if __name__ == "__main__":
    # Test run
    print(sync_state_to_remote(confirm=True))
