# -*- coding: utf-8 -*-
"""
app/lint_active_surface.py
Active Surface 규칙 검증 스크립트 (Phase C-S.0)
"""
import json
import re
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent
REPORTS_DIR = BASE_DIR / "reports"
LATEST_DIR = REPORTS_DIR / "phase_c" / "latest"

REQUIRED_LATEST_FILES = [
    "recon_summary.json",
    "recon_daily.jsonl",
    "report_human.json",
    "report_ai.json"
]

VERSION_SUFFIX_PATTERN = re.compile(r"_[vV]\d+\.json$|_[vV]\d+_.*\.json$")

def check_archive_dependencies():
    """_archive/ 의존성 체크 (active 코드에서 import/경로 사용 금지)"""
    hits = []
    active_code_dirs = ["backend", "dashboard", "config"]
    
    for dir_name in active_code_dirs:
        dir_path = BASE_DIR / dir_name
        if not dir_path.exists():
            continue
        for file_path in dir_path.rglob("*"):
            if file_path.is_file() and file_path.suffix in [".py", ".html", ".js"]:
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    # 실제 import나 경로 사용 체크
                    if "from _archive" in content or "import _archive" in content:
                        hits.append(str(file_path.relative_to(BASE_DIR)))
                    elif "_archive/" in content and ("open(" in content or "Path(" in content):
                        hits.append(str(file_path.relative_to(BASE_DIR)))
                except:
                    pass
    return hits

def check_external_report_paths():
    """backend/main.py와 dashboard/index.html이 latest/ 외부 경로를 읽는지 체크"""
    hits = []
    files_to_check = [
        BASE_DIR / "backend" / "main.py",
        BASE_DIR / "dashboard" / "index.html"
    ]
    
    for file_path in files_to_check:
        if not file_path.exists():
            continue
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            # reports/phase_c/ 경로가 있지만 latest가 없는 경우
            if "phase_c" in content:
                # latest 경로를 사용하는지 확인
                if 'phase_c" / "latest"' not in content and "phase_c/latest" not in content:
                    if 'phase_c"' in content or "phase_c/" in content:
                        hits.append(str(file_path.relative_to(BASE_DIR)))
        except:
            pass
    return hits

def check_version_suffix_in_latest():
    """reports/phase_c/latest/ 내 버전 접미사 파일 체크"""
    hits = []
    if not LATEST_DIR.exists():
        return hits
    
    for file_path in LATEST_DIR.iterdir():
        if file_path.is_file():
            if VERSION_SUFFIX_PATTERN.search(file_path.name):
                hits.append(file_path.name)
    return hits

def check_latest_files_present():
    """필수 4개 파일 존재 여부"""
    missing = []
    for fname in REQUIRED_LATEST_FILES:
        if not (LATEST_DIR / fname).exists():
            missing.append(fname)
    return len(missing) == 0, missing

def run_lint():
    """메인 린트 실행"""
    archive_hits = check_archive_dependencies()
    external_path_hits = check_external_report_paths()
    version_suffix_hits = check_version_suffix_in_latest()
    latest_present, missing_files = check_latest_files_present()
    
    overall = "PASS"
    if archive_hits or external_path_hits or version_suffix_hits or not latest_present:
        overall = "FAIL"
    
    result = {
        "lint_date": datetime.now().isoformat(),
        "phase": "C-S.0",
        "checks": {
            "archive_dependency": {
                "hits_count": len(archive_hits),
                "hits_samples": archive_hits[:10],
                "status": "PASS" if not archive_hits else "FAIL"
            },
            "external_report_path": {
                "hits_count": len(external_path_hits),
                "hits_samples": external_path_hits[:10],
                "status": "PASS" if not external_path_hits else "FAIL"
            },
            "latest_version_suffix": {
                "hits_count": len(version_suffix_hits),
                "hits_samples": version_suffix_hits[:10],
                "status": "PASS" if not version_suffix_hits else "FAIL"
            },
            "latest_files_present": {
                "present": latest_present,
                "missing": missing_files,
                "status": "PASS" if latest_present else "FAIL"
            }
        },
        "overall": overall
    }
    
    # 결과 저장
    output_path = REPORTS_DIR / "active_surface_lint_result.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"Lint result: {overall}")
    print(f"Saved to: {output_path}")
    return result

if __name__ == "__main__":
    run_lint()
