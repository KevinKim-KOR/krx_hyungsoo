"""PC 로컬에서 approved three_push_runtime_param.v1 snapshot 생성.

사용 예:
  python scripts/create_three_push_runtime_param.py --source manual_seed --approve
  python scripts/create_three_push_runtime_param.py --source manual_seed --approve \
      --description "초기 manual seed" --note "PARAM handoff 전환 1차 검증용"

기본 동작:
  - manual_seed PARAM 생성
  - --approve 옵션을 받으면 latest_runtime_param.json 으로 atomic write
  - --no-approve 또는 옵션 없음이면 history 폴더에만 저장
  - approved snapshot도 history에 함께 보존 (param_id 별 파일)

저장 경로:
  PC local latest: state/three_push/params/latest_runtime_param.json
  PC local history: state/three_push/params/history/<param_id>.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path 에 추가 (스크립트 직접 실행 지원).
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.three_push_runner_common import STATE_DIR  # noqa: E402
from app.three_push_runtime_param import (  # noqa: E402
    ALLOWED_PARAM_SOURCES,
    build_manual_seed_param,
    write_param_file,
)

_PARAM_DIR = STATE_DIR / "params"
_LATEST_PATH = _PARAM_DIR / "latest_runtime_param.json"
_HISTORY_DIR = _PARAM_DIR / "history"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="approved three_push_runtime_param.v1 snapshot 생성"
    )
    parser.add_argument(
        "--source",
        choices=list(ALLOWED_PARAM_SOURCES),
        default="manual_seed",
        help="param_source. 현재 ML 없음 — manual_seed/baseline_static 권장.",
    )
    parser.add_argument(
        "--approve",
        action="store_true",
        help="approve 후 latest_runtime_param.json 으로 승격",
    )
    parser.add_argument(
        "--description",
        default=None,
        help="param_description (선택)",
    )
    parser.add_argument(
        "--note",
        default=None,
        help="source_note (선택)",
    )
    parser.add_argument(
        "--enabled-push-kinds",
        default=None,
        help="쉼표로 구분된 push_kind 목록 (선택, 기본=3종 모두)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    enabled = None
    if args.enabled_push_kinds:
        enabled = [k.strip() for k in args.enabled_push_kinds.split(",") if k.strip()]

    if args.source != "manual_seed":
        # 본 STEP은 manual_seed 만 정식 지원. 다른 source 는 메타데이터만 변경.
        param = build_manual_seed_param(
            enabled_push_kinds=enabled,
            param_description=args.description,
            source_note=args.note,
        )
        param.param_source = args.source
    else:
        param = build_manual_seed_param(
            enabled_push_kinds=enabled,
            param_description=args.description,
            source_note=args.note,
        )

    history_path = _HISTORY_DIR / f"{param.param_id}.json"
    write_param_file(history_path, param)

    if args.approve:
        write_param_file(_LATEST_PATH, param)
        print(
            json.dumps(
                {
                    "status": "approved",
                    "param_id": param.param_id,
                    "param_source": param.param_source,
                    "latest_path": str(_LATEST_PATH),
                    "history_path": str(history_path),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(
            json.dumps(
                {
                    "status": "created_pending_approval",
                    "param_id": param.param_id,
                    "param_source": param.param_source,
                    "history_path": str(history_path),
                    "next": "검토 후 --approve 옵션으로 재실행해 latest 로 승격",
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
