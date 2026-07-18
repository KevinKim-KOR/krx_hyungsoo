"""Universe Seed Bootstrap CLI (지시문 §10 / §12).

subcommand:
  propose      — active seed 를 저장하지 않음. sanitized JSON 으로 후보 제안만 출력.
  materialize  — 사용자 승인 후 승인 목록만 seed 로 저장.

CLI 는 SSH/SCP 미수행. 개인정보 (수량/평단/평가금액/account_group) 노출 X.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Optional

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _cmd_propose(_args) -> int:
    from app.universe_bootstrap import build_bootstrap_proposal

    r = build_bootstrap_proposal()
    out = {
        "command": "propose",
        "status": r.status,
        "publishable_proposal": bool(r.publishable_proposal),
        "holdings_asof": r.holdings_asof,
        "market_discovery_asof": r.market_discovery_asof,
        "holding_candidates_available": r.holding_candidates_available,
        "market_candidates_available": r.market_candidates_available,
        "proposal_count": r.proposal_count,
        "proposals": [asdict(p) for p in r.proposals],
        "error_reason": r.error_reason or "",
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if r.status == "ok" else 2


def _cmd_materialize(args) -> int:
    from app.universe_bootstrap.materialize import (
        ApprovedItem,
        UniverseApprovalError,
        materialize_seed,
    )

    approved_path = Path(args.approved)
    if not approved_path.exists():
        print(
            json.dumps(
                {
                    "command": "materialize",
                    "status": "failed",
                    "error_reason": "approved_file_missing",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    payload = json.loads(approved_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "items" not in payload:
        print(
            json.dumps(
                {
                    "command": "materialize",
                    "status": "failed",
                    "error_reason": "approved_payload_missing_items",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    items_raw = payload.get("items") or []
    approved_items: list[ApprovedItem] = []
    # 검증자 REJECTED r7 재정정: malformed 항목을 조용히 skip 금지.
    # 승인된 종목 제거 계약 위반 방지 — 하나라도 dict 아니면 전체 실패.
    for i, it in enumerate(items_raw):
        if not isinstance(it, dict):
            print(
                json.dumps(
                    {
                        "command": "materialize",
                        "status": "failed",
                        "error_reason": (f"approved_item_not_dict:index={i}"),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 2
        approved_items.append(
            ApprovedItem(
                ticker=str(it.get("ticker", "")).strip(),
                name=str(it.get("name", "")).strip(),
                universe_group=it.get("universe_group"),
                sector_or_theme=it.get("sector_or_theme"),
            )
        )
    try:
        seed_path = materialize_seed(
            approved_items,
            asof=payload.get("asof"),
        )
    except UniverseApprovalError as e:
        print(
            json.dumps(
                {
                    "command": "materialize",
                    "status": "failed",
                    "error_reason": f"approval_error:{e}",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    out = {
        "command": "materialize",
        "status": "ok",
        "seed_path": str(seed_path),
        "item_count": len(approved_items),
        "source": "manual",
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def _parse_args(argv: Optional[list[str]] = None):
    p = argparse.ArgumentParser(
        prog="run_universe_seed_bootstrap",
        description="Universe Seed Bootstrap — 후보 제안 (propose) / 승인 목록 저장 (materialize).",
    )
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("propose", help="후보 제안만 출력. seed write X.")
    sp_m = sub.add_parser("materialize", help="사용자 승인 목록 → manual seed 저장.")
    sp_m.add_argument(
        "--approved",
        required=True,
        help="승인 목록 JSON 파일 경로. schema: {asof?, items:[{ticker,name,...}]}.",
    )
    return p.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    if args.command == "propose":
        return _cmd_propose(args)
    if args.command == "materialize":
        return _cmd_materialize(args)
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
