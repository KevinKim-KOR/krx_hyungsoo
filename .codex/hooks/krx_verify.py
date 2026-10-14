"""검증 세션의 통과 보고 직전에 근거와 소스 일치를 확인하는 Codex 훅."""

import json
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / ".agents/skills/krx-verify/scripts"))
import verify_scope as scope  # noqa: E402

PASS_REPORT = re.compile(
    r"(?m)^\s*(?:\*\*)?(?:종합 판정\s*[:：]\s*)?"
    r"(VERIFIED_WITH_NOTES|PARTIALLY_VERIFIED|VERIFIED)(?:\*\*)?\s*$"
)


def evaluate(payload, repo=REPO, storage=None):
    event = payload.get("hook_event_name")
    if event == "SessionStart":
        return {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": (
                    "KRX 구현 검증 요청에는 $krx-verify를 사용하고 "
                    ".agents/skills/krx-verify/SKILL.md를 읽으세요. "
                    "문서 수치만 틀리면 실측 정정하며 코드 결함과 구분합니다. "
                    "일반 질문·개발 구현에는 검증 절차를 적용하지 않습니다."
                ),
            }
        }
    if event != "Stop" or payload.get("stop_hook_active"):
        return {}
    match = PASS_REPORT.search(payload.get("last_assistant_message", ""))
    if not match:
        return {}
    try:
        if scope.repo_root(payload["cwd"]) != repo:
            return {}
        path = scope.record_path(repo, payload["session_id"], storage)
        record = scope.read_record(path)
        if record is None:
            return {}
        record, current, changes = scope.check(repo, path)
        reason = None
        if record["phase"] != "finished":
            reason = "finish로 최종 판정과 근거를 기록하지 않았습니다."
        elif record.get("verdict") != match.group(1):
            reason = "보고 판정과 근거 기록의 판정이 다릅니다."
        elif changes or current["problems"]:
            reason = "최종 근거와 소스가 다릅니다: " + "; ".join(
                changes + current["problems"]
            )
        if reason:
            return {
                "decision": "block",
                "reason": (
                    "검증 종료 확인: "
                    + reason
                    + " 소스를 재확인하고 기준 변경을 보고하세요. "
                    "문서 수치 정정만 있다면 --accept-doc과 사유를 기록하세요. "
                    "이 훅은 기능 결함 또는 REJECTED 판정을 자동 결정하지 않습니다."
                ),
            }
        return {}
    except (
        scope.ScopeError,
        OSError,
        KeyError,
        TypeError,
        subprocess.TimeoutExpired,
    ) as error:
        return {"decision": "block", "reason": "검증 근거 확인 실패: " + str(error)}


def main():
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("훅 입력은 JSON 객체여야 합니다")
        result = evaluate(payload)
    except (ValueError, TypeError) as error:
        result = {"systemMessage": "KRX 검증 훅 입력 오류: " + str(error)}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
