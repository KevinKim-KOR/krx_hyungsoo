"""
Contract Drift 검사 도구 (C-P.25.1)
실제 생성된 JSON과 계약 문서 간 필드 불일치 검출

규칙:
- No New Execution: 읽기 + 문서 수정 + 검사용 산출물 생성만 허용
- Strict Drift Rule: 실제 JSON 필드가 계약 Schema Fields 섹션에 없으면 위반
- Dotted Path 표기: nested는 a.b.c, 배열은 items[].field
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Set, Dict, List, Any

# Setup paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
STATE_DIR = BASE_DIR / "state"
REPORTS_PUSH_DIR = BASE_DIR / "reports" / "ops" / "push"
CONTRACTS_DIR = BASE_DIR / "docs" / "contracts"

# Input files
SEND_RECEIPTS_FILE = STATE_DIR / "push" / "send_receipts.jsonl"
POSTMORTEM_LATEST = REPORTS_PUSH_DIR / "postmortem" / "postmortem_latest.json"

# Output file
DRIFT_RESULT_FILE = REPORTS_PUSH_DIR / "postmortem" / "drift_fields_detected.json"

# Contract mapping
CONTRACT_MAPPING = {
    "PUSH_SEND_RECEIPT_V1": CONTRACTS_DIR / "contract_push_send_receipt_v1.md",
    "PUSH_DELIVERY_RECEIPT_V2": CONTRACTS_DIR / "contract_push_delivery_receipt_v2.md",
    "LIVE_FIRE_POSTMORTEM_V1": CONTRACTS_DIR / "contract_live_fire_postmortem_v1.md",
}


def flatten_json_keys(obj: Any, prefix: str = "") -> Set[str]:
    """
    JSON 객체의 모든 키를 dotted path로 수집
    배열은 items[].field 형태로 표현
    """
    keys = set()
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else key
            keys.add(path)
            keys.update(flatten_json_keys(value, path))
    elif isinstance(obj, list):
        if obj:
            # 배열의 첫 요소로 구조 파악
            sample = obj[0]
            if isinstance(sample, dict):
                for key, value in sample.items():
                    path = f"{prefix}[].{key}"
                    keys.add(path)
                    keys.update(flatten_json_keys(value, path))
    
    return keys


def parse_schema_fields_from_contract(contract_path: Path) -> Set[str]:
    """
    계약 문서의 ## Schema Fields 섹션에서 필드 목록 추출
    """
    if not contract_path.exists():
        return set()
    
    content = contract_path.read_text(encoding="utf-8")
    fields = set()
    
    # ## Schema Fields 또는 ## 3. 필드 정의 섹션 찾기
    patterns = [
        r"##\s*Schema Fields\s*\n(.*?)(?=\n##|\Z)",
        r"##\s*\d+\.\s*필드 정의\s*\n(.*?)(?=\n##|\Z)",
        r"##\s*\d+\.\s*스키마 정의\s*\n(.*?)(?=\n##|\Z)",
    ]
    
    section_content = None
    for pattern in patterns:
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            section_content = match.group(1)
            break
    
    if not section_content:
        # 테이블 형태에서 필드 추출 시도
        # | `field_name` | 형태 찾기
        table_matches = re.findall(r"\|\s*`([a-z_\.]+(?:\[\])?[a-z_\.]*)`\s*\|", content, re.IGNORECASE)
        for match in table_matches:
            if match and not match.startswith("schema"):
                fields.add(match)
        return fields
    
    # - field_name 형태 추출
    list_matches = re.findall(r"^-\s+([a-z_\.]+(?:\[\])?[a-z_\.]*)", section_content, re.MULTILINE | re.IGNORECASE)
    for match in list_matches:
        fields.add(match)
    
    # 테이블에서도 추출
    table_matches = re.findall(r"\|\s*`([a-z_\.]+(?:\[\])?[a-z_\.]*)`\s*\|", section_content, re.IGNORECASE)
    for match in table_matches:
        fields.add(match)
    
    return fields


def get_latest_receipt() -> Dict[str, Any]:
    """send_receipts.jsonl에서 최신 라인 로드"""
    if not SEND_RECEIPTS_FILE.exists():
        return None
    
    lines = SEND_RECEIPTS_FILE.read_text(encoding="utf-8").strip().split("\n")
    lines = [l for l in lines if l.strip()]
    
    if not lines:
        return None
    
    try:
        return json.loads(lines[-1])
    except Exception:
        return None


def get_postmortem() -> Dict[str, Any]:
    """postmortem_latest.json 로드"""
    if not POSTMORTEM_LATEST.exists():
        return None
    
    try:
        return json.loads(POSTMORTEM_LATEST.read_text(encoding="utf-8"))
    except Exception:
        return None


def check_drift_for_artifact(artifact: Dict, artifact_name: str) -> Dict:
    """단일 아티팩트에 대한 drift 검사"""
    if artifact is None:
        return {
            "artifact": artifact_name,
            "artifact_schema": None,
            "contract_path": None,
            "contract_schema": None,
            "missing_fields": [],
            "extra_fields_in_contract": [],
            "status": "SKIP",
            "reason": "Artifact not found"
        }
    
    schema = artifact.get("schema")
    if not schema:
        return {
            "artifact": artifact_name,
            "artifact_schema": None,
            "contract_path": None,
            "contract_schema": None,
            "missing_fields": [],
            "extra_fields_in_contract": [],
            "status": "FAIL",
            "reason": "No schema field in artifact"
        }
    
    contract_path = CONTRACT_MAPPING.get(schema)
    if not contract_path:
        return {
            "artifact": artifact_name,
            "artifact_schema": schema,
            "contract_path": None,
            "contract_schema": None,
            "missing_fields": [],
            "extra_fields_in_contract": [],
            "status": "FAIL",
            "reason": f"No contract found for schema {schema}"
        }
    
    # 아티팩트 필드 수집
    artifact_fields = flatten_json_keys(artifact)
    
    # 계약 필드 수집
    contract_fields = parse_schema_fields_from_contract(contract_path)
    
    # Drift 검사: 아티팩트에 있지만 계약에 없는 필드
    missing_in_contract = []
    for field in artifact_fields:
        # 기본 비교
        if field not in contract_fields:
            # nested path 체크 (a.b.c에서 a.b나 a가 있는지)
            found = False
            parts = field.split(".")
            for i in range(len(parts)):
                partial = ".".join(parts[:i+1])
                if partial in contract_fields:
                    found = True
                    break
            if not found:
                missing_in_contract.append(field)
    
    # 계약에 있지만 아티팩트에 없는 필드 (Extra)
    extra_in_contract = [f for f in contract_fields if f not in artifact_fields and not any(f.startswith(af.split(".")[0]) for af in artifact_fields)]
    
    status = "PASS" if len(missing_in_contract) == 0 else "FAIL"
    
    return {
        "artifact": artifact_name,
        "artifact_schema": schema,
        "contract_path": str(contract_path.relative_to(BASE_DIR)),
        "contract_schema": schema,
        "missing_fields": sorted(missing_in_contract),
        "extra_fields_in_contract": sorted(extra_in_contract),
        "status": status
    }


def run_drift_check() -> Dict:
    """전체 Drift 검사 실행"""
    asof = datetime.now().isoformat()
    
    # 1. Receipt 검사
    receipt = get_latest_receipt()
    receipt_result = check_drift_for_artifact(receipt, "send_receipts.jsonl")
    
    # 2. Postmortem 검사
    postmortem = get_postmortem()
    postmortem_result = check_drift_for_artifact(postmortem, "postmortem_latest.json")
    
    targets = [receipt_result, postmortem_result]
    
    # 전체 결과 계산
    all_pass = all(t["status"] == "PASS" for t in targets if t["status"] != "SKIP")
    missing_total = sum(len(t["missing_fields"]) for t in targets)
    
    result = {
        "schema": "CONTRACT_DRIFT_RESULT_V1",
        "asof": asof,
        "targets": targets,
        "result": "PASS" if all_pass and missing_total == 0 else "FAIL",
        "missing_total": missing_total
    }
    
    # Atomic write
    DRIFT_RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = DRIFT_RESULT_FILE.parent / "drift_fields_detected.json.tmp"
    tmp_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp_file), str(DRIFT_RESULT_FILE))
    
    return result


if __name__ == "__main__":
    result = run_drift_check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
