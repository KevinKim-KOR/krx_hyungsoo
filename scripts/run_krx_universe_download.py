"""POC4-01 — KRX 과거 ETF universe 연구 DB 적재 CLI (설계자 결정 2 — 2026-09-23).

  canary  최대 20개 기준일 (Gate 3)
  full    평일 전체 기간 계획 — 공식 한도(키당 10,000회/일) 확인 뒤에만 (Gate 5)
  resume  checkpoint 에서 이어받기
  status / verify / seal

연구 DB: state/ml/research/krx_etf_universe.sqlite (PC 전용 · 운영 DB·OCI 미접촉)
API 키는 `.env` 의 KRX_API_KEY 에서 읽고 **출력하지 않는다.**
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.market_briefing.krx_sync import read_api_key  # noqa: E402
from app.ml_research_krx_universe import (  # noqa: E402
    DEFAULT_RESEARCH_DB,
    batch_status,
    calls_today,
    connect,
    create_batch,
    run_batch,
    seal_version,
    verify_batch,
    weekdays,
)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="KRX universe 연구 DB 적재")
    parser.add_argument("--db", default=str(DEFAULT_RESEARCH_DB))
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("canary", "full", "resume"):
        p = sub.add_parser(name)
        p.add_argument("--batch-id", required=True)
        p.add_argument("--max-calls", type=int, default=20)
        p.add_argument("--pause", type=float, default=0.5)
        if name != "resume":
            p.add_argument("--version", required=True)
        if name == "canary":
            p.add_argument("--dates", required=True, help="YYYYMMDD,YYYYMMDD,...")
        if name == "full":
            p.add_argument("--start", required=True)
            p.add_argument("--end", required=True)
    for name in ("status", "verify"):
        sub.add_parser(name).add_argument("--batch-id", required=True)
    s = sub.add_parser("seal")
    s.add_argument("--version", required=True)
    s.add_argument("--note", default="")
    args = parser.parse_args(argv)

    con = connect(Path(args.db))
    try:
        if args.command in ("canary", "full"):
            dates = (
                args.dates.split(",")
                if args.command == "canary"
                else weekdays(args.start, args.end)
            )
            planned = create_batch(
                con,
                batch_id=args.batch_id,
                purpose=args.command.upper(),
                dates=dates,
                dataset_version=args.version,
            )
            print(json.dumps({"planned": planned}, ensure_ascii=False))
        if args.command in ("canary", "full", "resume"):
            key = read_api_key(_PROJECT_ROOT / ".env")
            if not key:
                print(json.dumps({"error": "KRX_API_KEY 없음"}, ensure_ascii=False))
                return 2
            out = run_batch(
                con,
                args.batch_id,
                key=key,
                max_calls=args.max_calls,
                pause_seconds=args.pause,
            )
            out["calls_today_kst"] = calls_today(con)
        elif args.command == "status":
            out = batch_status(con, args.batch_id)
        elif args.command == "verify":
            out = verify_batch(con, args.batch_id)
        else:
            out = seal_version(con, args.version, args.note)
    finally:
        con.close()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if out.get("ok") is False:
        return 1
    return 0 if out.get("stopped") in (None, "CALL_LIMIT") else 1


if __name__ == "__main__":
    raise SystemExit(main())
