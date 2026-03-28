"""backend 공유 유틸리티 — 파일 I/O, 로깅, 경로 상수."""

import json
import logging
import shutil
import sys
import tempfile
import yaml
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

KST = timezone(timedelta(hours=9))

# --- 경로 상수 ---
BASE_DIR = Path(".")
LOG_DIR = BASE_DIR / "logs"
STATE_DIR = BASE_DIR / "state"
REPORTS_DIR = BASE_DIR / "reports"
PAPER_DIR = REPORTS_DIR / "paper"
DASHBOARD_DIR = BASE_DIR / "dashboard"

# P146.3: Draft Generation Constants
PREP_LATEST_FILE = (
    REPORTS_DIR / "live" / "execution_prep" / "latest" / "execution_prep_latest.json"
)
TICKET_LATEST_FILE = (
    REPORTS_DIR
    / "live"
    / "manual_execution_ticket"
    / "latest"
    / "manual_execution_ticket_latest.json"
)
ORDER_PLAN_EXPORT_LATEST_FILE = (
    REPORTS_DIR
    / "live"
    / "order_plan_export"
    / "latest"
    / "order_plan_export_latest.json"
)
OPS_SUMMARY_PATH = (
    REPORTS_DIR / "ops" / "summary" / "latest" / "ops_summary_latest.json"
)
DRAFT_LATEST_FILE = (
    REPORTS_DIR
    / "live"
    / "manual_execution_record"
    / "draft"
    / "latest"
    / "manual_execution_record_draft_latest.json"
)

# Ensure dirs exist
DRAFT_LATEST_FILE.parent.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


# --- 로깅 ---
def setup_backend_logger():
    today_str = datetime.now(KST).strftime("%Y%m%d")
    log_file = LOG_DIR / f"backend_{today_str}.log"

    logger = logging.getLogger("backend")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s"))
    logger.addHandler(fh)

    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter("[BACKEND] %(message)s"))
    logger.addHandler(ch)

    return logger


logger = setup_backend_logger()


# --- 파일 I/O ---
def get_today_str() -> str:
    return datetime.now(KST).strftime("%Y%m%d")


def safe_read_text_advanced(path: Path) -> Dict[str, Any]:
    """안전한 텍스트 파일 읽기 (인코딩, 파일 잠금 대비) + 메타데이터 반환"""
    if not path.exists():
        return {"content": "", "encoding": "none", "quality": "failed"}

    # 1. UTF-8
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {
                "content": f.read(),
                "encoding": "utf-8",
                "quality": "perfect",
            }
    except UnicodeDecodeError:
        pass
    except Exception as e:
        logger.error(f"파일 읽기 실패(UTF-8): {path} - {e}")

    # 2. CP949
    try:
        with open(path, "r", encoding="cp949") as f:
            return {
                "content": f.read(),
                "encoding": "cp949",
                "quality": "perfect",
            }
    except UnicodeDecodeError:
        pass

    # 3. Shadow Copy Strategy (Windows Locking Fix)
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)

        shutil.copy2(path, tmp_path)

        content = ""
        encoding = "shadow-copy"

        try:
            with open(tmp_path, "r", encoding="utf-8") as f:
                content = f.read()
                encoding = "utf-8"
        except UnicodeDecodeError:
            with open(tmp_path, "r", encoding="cp949") as f:
                content = f.read()
                encoding = "cp949"

        try:
            tmp_path.unlink()
        except Exception:
            pass

        return {"content": content, "encoding": encoding, "quality": "perfect"}

    except Exception as e:
        logger.warning(f"Shadow Copy 읽기 실패: {path} - {e}")

    # 4. UTF-16
    try:
        with open(path, "r", encoding="utf-16") as f:
            return {
                "content": f.read(),
                "encoding": "utf-16",
                "quality": "perfect",
            }
    except UnicodeDecodeError:
        pass

    # 5. 최후의 수단
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return {
                "content": f.read(),
                "encoding": "forced-utf8",
                "quality": "partial",
            }
    except Exception as e:
        logger.error(f"파일 강제 읽기 완전 실패: {path} - {e}", exc_info=True)
        return {
            "content": "",
            "encoding": "failed",
            "quality": "failed",
            "error": str(e),
        }


def safe_read_text(path: Path) -> str:
    """기존 함수 호환용 (단순 content 반환)"""
    res = safe_read_text_advanced(path)
    if res["quality"] == "failed":
        raise IOError(f"파일 읽기 실패: {res.get('error')}")
    return res["content"]


def safe_read_json(path: Path) -> Dict[str, Any]:
    """JSON 파일 안전 읽기"""
    content = safe_read_text(path)
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"JSON 파싱 실패: {path} - {str(e)}")
        raise ValueError("잘못된 JSON 형식입니다.")


def safe_read_yaml(path: Path) -> Any:
    """YAML 파일 안전 읽기"""
    if not path.exists():
        return []
    content = safe_read_text(path)
    try:
        return yaml.safe_load(content)
    except yaml.YAMLError as e:
        logger.error(f"YAML 파싱 실패: {path} - {str(e)}")
        raise ValueError("잘못된 YAML 형식입니다.")


def load_json_or_none(path: Path) -> Optional[Dict]:
    """Helper for Draft Generation (Hotfix 172)"""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
