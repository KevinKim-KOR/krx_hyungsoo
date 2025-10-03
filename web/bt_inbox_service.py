"""
FastAPI 라우트 + 인박스 워커(통합)
- POST /bt/inbox/notify: 인박스 스캔 트리거
- 워커: inbox/* 패키지 → SHA256 검증 → processed/YYYYMMDD/ 이동 → index 갱신 → (옵션) 텔레그램 알림
경로 기준: 리포지토리 루트에서 실행 (OPERATIONS.md와 동일)
"""

import os
import re
import json
import logging
import shutil
import hashlib
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Dict, Optional

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse

try:
    import yaml, requests
except Exception:
    yaml = None
    requests = None

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
INBOX_DIR = os.path.join(REPO_ROOT, "reports", "backtests", "inbox")
PROC_DIR  = os.path.join(REPO_ROOT, "reports", "backtests", "processed")
INDEX_JSON = os.path.join(REPO_ROOT, "reports", "backtests", "index.json")

router = APIRouter(prefix="/bt", tags=["backtests"])
log = logging.getLogger(__name__)

def _read_config() -> Dict:
    cfg_path = os.environ.get("KRX_CONFIG", os.path.join(REPO_ROOT, "secret", "config.yaml"))
    if yaml and os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def _telegram_notify(msg: str) -> None:
    cfg = _read_config()
    try:
        token = cfg["notifications"]["telegram"]["token"]
        chat  = cfg["notifications"]["telegram"]["chat_id"]
    except Exception:
        return
    if requests is None:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat, "text": msg}, timeout=5)
    except Exception:
        pass

def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

def verify_sha256sums(pkg_dir: str) -> Tuple[bool, List[str]]:
    sums_path = os.path.join(pkg_dir, "SHA256SUMS")
    if not os.path.exists(sums_path):
        return False, ["missing: SHA256SUMS"]

    bad: List[str] = []
    with open(sums_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = re.match(r"([0-9a-fA-F]{64})\s+(.+)$", line)
            if not m:
                bad.append(f"malformed line: {line}")
                continue
            expected, fname = m.group(1), m.group(2)
            fpath = os.path.join(pkg_dir, fname)
            if not os.path.exists(fpath):
                bad.append(f"missing file: {fname}")
                continue
            actual = sha256_of(fpath)
            if actual.lower() != expected.lower():
                bad.append(f"mismatch: {fname}")
    return (len(bad) == 0), bad

def load_manifest(pkg_dir: str):
    return _load_json_tolerant(os.path.join(pkg_dir, "manifest.json"))

def load_summary(pkg_dir: str):
    return _load_json_tolerant(os.path.join(pkg_dir, "summary.json"))

def ensure_dirs() -> None:
    os.makedirs(INBOX_DIR, exist_ok=True)
    os.makedirs(PROC_DIR,  exist_ok=True)
    os.makedirs(os.path.dirname(INDEX_JSON), exist_ok=True)

def update_index(entry: Dict) -> None:
    idx: Dict[str, List[Dict]] = {}
    if os.path.exists(INDEX_JSON):
        try:
            with open(INDEX_JSON, "r", encoding="utf-8") as f:
                idx = json.load(f) or {}
        except Exception:
            idx = {}
    lst = idx.get("packages", [])
    lst.append(entry)
    idx["packages"] = lst
    with open(INDEX_JSON, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)

def move_to_processed(pkg_dir: str) -> str:
    # processed/YYYYMMDD/<pkg_basename>
    bname = os.path.basename(pkg_dir.rstrip("/\\"))
    kst = timezone(timedelta(hours=9))
    d = datetime.now(kst).strftime("%Y%m%d")
    out_dir = os.path.join(PROC_DIR, d, bname)
    os.makedirs(os.path.dirname(out_dir), exist_ok=True)
    shutil.move(pkg_dir, out_dir)
    return out_dir

def scan_inbox_once() -> Dict:
    ensure_dirs()
    pkgs = [os.path.join(INBOX_DIR, d) for d in os.listdir(INBOX_DIR) if os.path.isdir(os.path.join(INBOX_DIR, d))]
    if not pkgs:
        return {"status":"empty","processed":0}

    processed = 0
    quarantined = 0
    results: List[Dict] = []
    quarantine_dir = os.path.join(REPO_ROOT, "reports", "backtests", "quarantine")
    os.makedirs(quarantine_dir, exist_ok=True)

    for pkg in sorted(pkgs):
        ok, issues = verify_sha256sums(pkg)
        if not ok:
            # 격리
            qdst = os.path.join(quarantine_dir, os.path.basename(pkg))
            shutil.move(pkg, qdst)
            quarantined += 1
            _telegram_notify(f"[BT Inbox] SHA256 failed → quarantined: {os.path.basename(qdst)} | issues={issues}")
            results.append({"pkg": pkg, "status": "quarantined", "issues": issues})
            continue

        manifest = load_manifest(pkg)
        final_dir = move_to_processed(pkg)
        entry = {
            "final_dir": final_dir,
            "manifest": manifest,
            "indexed_at": datetime.now(timezone(timedelta(hours=9))).isoformat()
        }
        update_index(entry)
        processed += 1
        _telegram_notify(f"[BT Inbox] processed: {os.path.basename(final_dir)}")
        results.append({"pkg": pkg, "status": "processed", "final_dir": final_dir})

    return {"status":"ok","processed":processed,"quarantined":quarantined,"results":results}

@router.post("/inbox/notify")
def inbox_notify(payload: Optional[Dict] = None):
    """
    PC에서 업로드 완료 후 호출. payload는 선택사항.
    """
    res = scan_inbox_once()
    return JSONResponse(res)

# ---- FastAPI 애플리케이션에 라우터 등록 (단독 실행 가능)
def build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app

def _load_json_tolerant(path: str):
    """Allow UTF-8 and UTF-8 with BOM (utf-8-sig)."""
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception as e1:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e2:
            log.error("JSON load failed for %s: %s / %s", path, e1, e2)
            raise

app = build_app()

if __name__ == "__main__":
    # 단독 워커 실행 (예: python web/bt_inbox_service.py)
    print(json.dumps(scan_inbox_once(), ensure_ascii=False, indent=2))
