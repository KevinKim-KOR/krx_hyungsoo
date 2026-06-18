"""OCI 측에서 latest_runtime_param.json 을 검증하는 stand-alone 스크립트.

PC sync_three_push_runtime_param.py 가 OCI /tmp 로 업로드 후 실행한다.
의존성: Python 3 표준 라이브러리만 사용 (app/* import 없음 — OCI 일시 환경에서도 동작).

검증 항목:
  - 파일 존재
  - JSON 파싱
  - schema_version == "three_push_runtime_param.v1"
  - 필수 필드 (param_id / created_at / approved_at / approved_by /
    param_source / enabled_push_kinds / runtime_policy / evidence_policy / safety_policy)
  - param_source 허용값
  - enabled_push_kinds 허용값
  - 금지 키 (message_text / buy_candidates / token / chat_id 등) 부재

종료 코드:
  0: PASS
  1: 검증 실패 (stderr 에 사유)
  2: 파일 부재 / 인자 오류
"""

from __future__ import annotations

import argparse
import json
import sys

SCHEMA_VERSION = "three_push_runtime_param.v1"
ALLOWED_PUSH_KINDS = (
    "market_briefing",
    "holdings_briefing",
    "spike_or_falling_alert",
)
ALLOWED_PARAM_SOURCES = (
    "manual_seed",
    "baseline_static",
    "future_ml_placeholder",
    "ml_export",
)
FORBIDDEN_KEYS = frozenset(
    {
        "message_text",
        "telegram_text",
        "buy_candidates",
        "sell_candidates",
        "cash_allocation",
        "regime_confirmation",
        "risk_threshold_confirmation",
        "etf_ranking",
        "token",
        "chat_id",
        "bot_token",
        "telegram_token",
        "telegram_chat_id",
    }
)


def main() -> int:
    parser = argparse.ArgumentParser(description="OCI PARAM verify")
    parser.add_argument("--path", required=True)
    args = parser.parse_args()

    try:
        with open(args.path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"파일 없음: {args.path}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print(f"JSON 파싱 실패: {e}", file=sys.stderr)
        return 1

    errors = []
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version 불일치: got={data.get('schema_version')!r}")
    for f in (
        "param_id",
        "created_at",
        "approved_at",
        "approved_by",
        "param_source",
        "enabled_push_kinds",
        "runtime_policy",
        "evidence_policy",
        "safety_policy",
    ):
        if f not in data:
            errors.append(f"필수 필드 누락: {f}")
    ps = data.get("param_source")
    if ps is not None and ps not in ALLOWED_PARAM_SOURCES:
        errors.append(f"param_source 허용값 위반: {ps!r}")
    epk = data.get("enabled_push_kinds")
    if isinstance(epk, list):
        for k in epk:
            if k not in ALLOWED_PUSH_KINDS:
                errors.append(f"enabled_push_kinds 허용값 위반: {k!r}")
    elif epk is not None:
        errors.append("enabled_push_kinds 는 list 이어야 함")

    # 금지 키 — top-level 뿐 아니라 중첩 dict/list 내부도 거부 (fail-closed).
    # 대소문자 무관 매칭.
    def _collect_forbidden(obj, path=""):
        hits = []
        if isinstance(obj, dict):
            for kk, vv in obj.items():
                cp = f"{path}.{kk}" if path else kk
                if isinstance(kk, str) and kk.lower() in FORBIDDEN_KEYS:
                    hits.append(cp)
                hits.extend(_collect_forbidden(vv, cp))
        elif isinstance(obj, list):
            for ii, item in enumerate(obj):
                cp = f"{path}[{ii}]"
                hits.extend(_collect_forbidden(item, cp))
        return hits

    for p in _collect_forbidden(data):
        errors.append(f"금지 키 포함: {p!r} (중첩 포함)")

    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "status": "ok",
                "param_id": data.get("param_id"),
                "param_source": data.get("param_source"),
                "enabled_push_kinds": data.get("enabled_push_kinds"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
