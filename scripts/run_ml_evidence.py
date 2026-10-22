"""POC6-05 — 지속 시장 자료 수집 · ML 연구 증거 보관 CLI(저장소 루트에서 실행).

OCI:
    python scripts/run_ml_evidence.py collect-daily [--limit-tickers N]   # cron 09:40 · 매일
    python scripts/run_ml_evidence.py list-runs                           # 읽기 전용 목록(PC pull 이 부름)
    python scripts/run_ml_evidence.py accept-upload --upload-id ID --expect-manifest-sha SHA
PC:
    python scripts/run_ml_evidence.py pull
    python scripts/run_ml_evidence.py register-research
    python scripts/run_ml_evidence.py upload-research --run-id RUN_ID
    python scripts/run_ml_evidence.py export --as-of 2026-10-23T00:00:00Z [--tickers 069500,...]
양쪽:
    python scripts/run_ml_evidence.py status [--remote] | verify
    python scripts/run_ml_evidence.py restore-check --run-id RUN_ID --to EMPTY_DIR

마지막 줄 = `RESULT {json}`. 종료 코드: 0 = OK · 새 자료 없음 · 2 = PARTIAL · 확인 필요 · 손상본 되살림(REPAIRED)
· 1 = 실패 · 3 = 이미 실행 중.
학습 · 추론 · 성과 계산 없음. 보유 · 원장 · AI 세션 DB 를 열지 않는다.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback
from pathlib import Path
from typing import Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml_evidence import store  # noqa: E402

RC = {
    "OK": 0,
    "SKIPPED_NO_NEW": 0,
    "ALREADY_REGISTERED": 0,
    "PARTIAL": 2,
    "REPAIRED": 2,
    "CHECK_REQUIRED": 2,
    "FAILED": 1,
    "BUSY": 3,
}


def _emit(result: dict) -> int:
    print("RESULT " + json.dumps(result, ensure_ascii=False, sort_keys=True))
    return RC.get(result.get("status", "FAILED"), 1)


def _summary(m: dict) -> dict:
    src = m.get("sources", {})
    return {
        "status": m.get("status"),
        "run_id": m.get("run_id"),
        "published_at": m.get("published_at"),
        "sources": {k: v.get("status") for k, v in src.items()},
        "naver": {
            k: src.get("naver_etf_windows", {}).get(k)
            for k in ("target_day", "counts", "stop_reason", "have_total")
        },
        "resources": m.get("resources"),
    }


def _verify(root: Path, run_id: Optional[str]) -> dict:
    runs, problems = store.list_runs(root)
    out = {}
    for r in runs:
        if run_id and r.run_id != run_id:
            continue
        bad = store.verify_run(root, r)
        if bad:
            out[r.run_id] = bad
    return {
        "status": "OK" if not (out or problems) else "CHECK_REQUIRED",
        "runs_checked": len(runs),
        "bad": out,
        "problems": problems,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    p = argparse.ArgumentParser(description="POC6-05 증거 보관")
    p.add_argument(
        "--root", type=Path, default=None, help="보관소(기본 state/ml/evidence)"
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect-daily")
    c.add_argument(
        "--limit-tickers", type=int, default=None, help="첫 실연결 RSS 확인용 소수 종목"
    )
    c.add_argument("--site", default="OCI")
    sub.add_parser("list-runs")
    a = sub.add_parser("accept-upload")
    a.add_argument("--upload-id", required=True)
    a.add_argument("--expect-manifest-sha", required=True)
    sub.add_parser("pull")
    sub.add_parser("register-research")
    u = sub.add_parser("upload-research")
    u.add_argument("--run-id", required=True)
    e = sub.add_parser("export")
    e.add_argument("--as-of", required=True)
    e.add_argument("--tickers", default=None)
    e.add_argument("--out-root", type=Path, default=None)
    st = sub.add_parser("status")
    st.add_argument(
        "--remote", action="store_true", help="OCI 목록과 대조(읽기 전용 ssh)"
    )
    v = sub.add_parser("verify")
    v.add_argument("--run-id", default=None)
    r = sub.add_parser("restore-check")
    r.add_argument("--run-id", required=True)
    r.add_argument("--to", type=Path, required=True)
    args = p.parse_args(argv)
    root = args.root or store.EVIDENCE_ROOT
    now = store.utc_now()
    try:
        if args.cmd == "collect-daily":
            from app.ml_evidence import daily

            status, m = daily.collect_daily(
                root=root, site=args.site, limit_tickers=args.limit_tickers
            )
            return _emit(_summary(m) if status != "BUSY" else m)
        if args.cmd == "list-runs":
            from app.ml_evidence import transfer

            for line in transfer.list_runs_lines(root):
                print(json.dumps(line, ensure_ascii=False, sort_keys=True))
            return 0
        if args.cmd == "accept-upload":
            from app.ml_evidence import transfer

            return _emit(
                transfer.accept_upload(
                    root=root,
                    upload_id=args.upload_id,
                    expect_sha=args.expect_manifest_sha,
                    now=now,
                )
            )
        if args.cmd == "pull":
            from app.ml_evidence import transfer

            return _emit(
                transfer.pull(root=root, remote=transfer.default_remote(), now=now)
            )
        if args.cmd == "register-research":
            from app.ml_evidence import daily, research

            repo = Path(__file__).resolve().parents[1]
            status, m = research.register_research(
                root=root, repo_root=repo, now=now, git_head=daily.git_head()
            )
            bad = [f for f in m.get("files", []) if f["status"] != "REGISTERED"]
            return _emit(
                {
                    "status": status,
                    "run_id": m["run_id"],
                    "files": len(m["files"]),
                    "check_required": bad,
                }
            )
        if args.cmd == "upload-research":
            from app.ml_evidence import transfer

            return _emit(
                transfer.upload_research(
                    root=root,
                    remote=transfer.default_remote(),
                    run_id=args.run_id,
                    now=now,
                )
            )
        if args.cmd == "export":
            from app.ml_evidence import export as ex

            tickers = set(args.tickers.split(",")) if args.tickers else None
            status, folder = ex.export(
                root=root,
                as_of=ex.parse_as_of(args.as_of),
                now=now,
                out_root=args.out_root,
                tickers=tickers,
            )
            return _emit({"status": status, "folder": str(folder)})
        if args.cmd == "status":
            from app.ml_evidence import status as st_mod

            rows = None
            if args.remote:
                from app.ml_evidence import transfer

                rows, _ = transfer._remote_list(transfer.default_remote())
            return _emit(st_mod.summarize(root, rows))
        if args.cmd == "verify":
            return _emit(_verify(root, args.run_id))
        if args.cmd == "restore-check":
            return _emit(store.restore_check(root, args.run_id, args.to))
    except store.EvidenceError as e:
        return _emit({"status": "CHECK_REQUIRED", "error": str(e)})
    except Exception as e:  # noqa: BLE001 — 실행 실패는 rc 1 + 원인 기록
        traceback.print_exc()
        return _emit(
            {"status": "FAILED", "error": f"{type(e).__name__}: {str(e)[:300]}"}
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
