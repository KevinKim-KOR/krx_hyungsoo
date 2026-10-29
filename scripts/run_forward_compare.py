"""POC6-06 — 보유 독립 ETF 전향 ML 비교 · 기록 CLI(PC 수동 · 저장소 루트에서 실행).

    python scripts/run_forward_compare.py select-cohort            # cohort_v1 고정 · 이미 있으면 확인만
    python scripts/run_forward_compare.py bootstrap-fetch          # 초기 장기 가격 24 요청(사용자 승인 뒤 1회)
    python scripts/run_forward_compare.py run [--pull] [--archive] # 성숙 → 학습 결정 → 예측 기록 → 보고
    python scripts/run_forward_compare.py report                   # 파일 읽기만(쓰기 · 학습 · 예측 0)
    python scripts/run_forward_compare.py archive [--upload]       # 05 보관소 등록(+ OCI 업로드)

`--pull` · `--archive` · `--upload` 를 주지 않으면 SSH · 외부 조회 0(`bootstrap-fetch` 만 외부 조회).
과거 시각을 입력받는 인자는 없다. 마지막 줄 = `RESULT {json}` · 종료 코드는 05 CLI 와 같은 표.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.forward_compare import bootstrap as bootstrap_mod  # noqa: E402
from app.forward_compare import cohort as cohort_mod  # noqa: E402
from app.forward_compare import protocol as P  # noqa: E402
from app.ml_evidence import store  # noqa: E402

RC = {
    "OK": 0,
    "ALREADY": 0,
    "ALREADY_RECORDED": 0,
    "SKIPPED_NO_NEW": 0,
    "SKIPPED_TOO_LATE": 2,
    "PARTIAL": 2,
    "CHECK_REQUIRED": 2,
    "PENDING_CALENDAR": 2,
    "NO_INPUT": 2,
    "NO_MODEL": 2,
    "NO_EVIDENCE": 2,
    "FAILED": 1,
    "BUSY": 3,
}
DB_PATH = Path("state/market/market_data.sqlite")


def _emit(result: dict) -> int:
    print(
        "RESULT " + json.dumps(result, ensure_ascii=False, sort_keys=True, default=str)
    )
    return RC.get(result.get("status", "FAILED"), 1)


def _upload(ev: Path, run_ids: list[str]) -> dict:
    """업로드 작업 한 번에 OCI 목록 1회(POC6-13 PLAN 판정 §3 · 묶음별 판정은 기존 그대로)."""
    from app.ml_evidence import transfer

    return transfer.upload_research_many(
        root=ev, remote=transfer.default_remote(), run_ids=run_ids, now=store.utc_now()
    )


def _archive(root: Path, ev: Path, upload: bool, commit: Optional[str]) -> dict:
    from app.forward_compare import archive

    status, m = archive.register(root, ev, now=store.utc_now(), code_commit=commit)
    out = {
        "status": status,
        "run_id": m.get("run_id"),
        "files": len(m.get("files", [])),
    }
    out["detail"] = {
        k: m[k]
        for k in ("reason", "paths", "not_allowed", "not_allowed_paths")
        if k in m
    }
    if upload:
        _, ids = archive.registered(ev)
        out["uploads"] = _upload(ev, ids)
    out["local"] = archive.local_state(root, ev)
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="POC6-06 전향 ML 비교 · 기록")
    p.add_argument(
        "--root",
        type=Path,
        default=None,
        help="연구 폴더(기본 state/ml/research/poc6_06)",
    )
    p.add_argument(
        "--evidence", type=Path, default=None, help="05 보관소(기본 state/ml/evidence)"
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("select-cohort")
    sub.add_parser("bootstrap-fetch")
    r = sub.add_parser("run")
    r.add_argument("--pull", action="store_true", help="먼저 05 pull(SSH)")
    r.add_argument(
        "--archive", action="store_true", help="끝나고 등록 + OCI 업로드(SSH)"
    )
    sub.add_parser("report")
    a = sub.add_parser("archive")
    a.add_argument("--upload", action="store_true", help="등록 묶음을 OCI 로 올림(SSH)")
    args = p.parse_args(argv)
    root = args.root or P.ROOT
    ev = args.evidence or P.EVIDENCE_ROOT
    try:
        from app.ml_evidence import daily

        commit = daily.git_head()
        if args.cmd == "select-cohort":
            from app.forward_compare import cohort

            status, body = cohort.select(root, ev, DB_PATH, store.utc_now())
            return _emit(
                {
                    "status": status,
                    "tickers": body["tickers"],
                    "candidates": body["candidate_count"],
                }
            )
        if args.cmd == "bootstrap-fetch":
            from app.forward_compare import bootstrap, cohort, inputs

            c = cohort.load(root)
            e = inputs.Evidence(ev, store.utc_now())
            try:
                latest = e.latest()
                if latest is None:
                    return _emit({"status": "NO_EVIDENCE"})
                start = e.axis_inputs(latest)[0][0]
            finally:
                e.close()
            status, meta = bootstrap.fetch(root, c, start=start, clock=store.utc_now)
            return _emit(
                {
                    "status": status,
                    "id": meta["id"],
                    "counts": meta["counts"],
                    "range": meta["requested_range"],
                }
            )
        if args.cmd == "run":
            from app.forward_compare import forward

            pulled = None
            if args.pull:
                from app.ml_evidence import transfer

                pulled = transfer.pull(
                    root=ev, remote=transfer.default_remote(), now=store.utc_now()
                )
            out = forward.run(root, ev, code_commit=commit)
            res = {
                k: out.get(k)
                for k in (
                    "status",
                    "id",
                    "D",
                    "close_cutoff_at",
                    "input_ok",
                    "record_type",
                    "roles",
                    "prediction",
                    "publication_confirmed",
                    "confirmed_at",
                    "confirmed_earlier",
                    "report",
                )
            }
            res["training"] = {
                k: (out.get("training") or {}).get(k)
                for k in ("decision", "reason", "model_version")
            }
            res["maturity"] = (out.get("maturity") or {}).get("counts")
            res["pull"] = None if pulled is None else pulled.get("status")
            if args.archive:
                res["archive"] = _archive(root, ev, True, commit)
            else:
                from app.forward_compare import archive

                res["archive_local"] = archive.local_state(root, ev)
            return _emit(res)
        if args.cmd == "report":
            from app.forward_compare import cohort, report

            return _emit({"status": "OK", **report.build(root, cohort.load(root))})
        if args.cmd == "archive":
            return _emit(_archive(root, ev, args.upload, commit))
    except store.EvidenceError as e:
        return _emit({"status": "CHECK_REQUIRED", "error": str(e)})
    except P.Busy as e:
        return _emit({"status": "BUSY", "error": str(e)})
    except P.ClockBehind as e:
        return _emit({"status": "CHECK_REQUIRED", "error": f"ClockBehind: {e}"})
    except (cohort_mod.CohortError, bootstrap_mod.BootstrapRefused) as e:
        return _emit({"status": "CHECK_REQUIRED", "error": f"{type(e).__name__}: {e}"})
    except Exception as e:  # noqa: BLE001 — 실행 실패는 rc 1 + 원인 기록
        traceback.print_exc()
        return _emit(
            {"status": "FAILED", "error": f"{type(e).__name__}: {str(e)[:300]}"}
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
