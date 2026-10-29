"""POC6-13 — 전향 비교 정기 실행 · 보관 연결 · 연구 자산 외장 백업 CLI(맥북 · 저장소 루트 기준).

    python scripts/run_forward_auto.py tick              # launchd 가 부름(창 안 · 06 run · archive)
    python scripts/run_forward_auto.py status            # 파일 읽기만(06 · SSH · 업로드 0)
    python scripts/run_forward_auto.py install [--apply]    # 자기 LaunchAgent(없으면 dry-run)
    python scripts/run_forward_auto.py uninstall [--apply]  # bootout + 자기 plist 만 삭제
    python scripts/run_forward_auto.py backup plan [--target DIR]        # 목록 · 목적지 검사(쓰기 0)
    python scripts/run_forward_auto.py backup run --target DIR --apply   # 외장 장치 사본(C)
    python scripts/run_forward_auto.py backup verify --target DIR --backup-id ID --apply  # 복원 확인

과거 시각을 받는 인자는 없다. 마지막 줄 = `RESULT {json}`.
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import traceback
from pathlib import Path
from typing import Optional, Sequence

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from app.forward_auto import launchd  # noqa: E402
from app.forward_auto import status as ST  # noqa: E402
from app.ml_evidence import store  # noqa: E402


def _emit(result: dict, rc: int = 0) -> int:
    print(
        "RESULT " + json.dumps(result, ensure_ascii=False, sort_keys=True, default=str)
    )
    return rc


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="POC6-13 전향 비교 정기 실행 · 보관 · 백업")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("tick")
    sub.add_parser("status")
    for name in ("install", "uninstall"):
        sub.add_parser(name).add_argument("--apply", action="store_true")
    b = sub.add_parser("backup").add_subparsers(dest="bcmd", required=True)
    bp = b.add_parser("plan")
    bp.add_argument("--target", type=Path, default=None)
    br = b.add_parser("run")
    br.add_argument("--target", type=Path, required=True)
    br.add_argument("--apply", action="store_true")
    bv = b.add_parser("verify")
    bv.add_argument("--target", type=Path, required=True)
    bv.add_argument("--backup-id", required=True)
    bv.add_argument("--apply", action="store_true")
    args = p.parse_args(argv)
    paths = ST.Paths.default(REPO)
    try:
        if args.cmd == "tick":
            from app.forward_auto import runner

            def _term(signum, frame):  # bootout · 로그아웃 — 자식 그룹 정리 뒤 끝냄
                raise SystemExit(128 + signum)

            signal.signal(signal.SIGTERM, _term)
            info = launchd.check(sys.executable, REPO)
            return _emit(runner.tick(paths, launchd=info))
        if args.cmd == "status":
            ev = ST.evaluate(
                paths, store.utc_now(), launchd=launchd.check(sys.executable, REPO)
            )
            print(ST.render(ev), end="")
            return _emit(
                {
                    "predict": ev["predict"]["state"],
                    "archive": ev["archive"]["state"],
                    "backup": ev["backup"]["state"],
                }
            )
        if args.cmd == "install":
            out = launchd.install(sys.executable, REPO, apply=args.apply)
            if not args.apply:
                print(out["plist"])
            return _emit(out, 0 if out["status"] in ("OK", "DRY_RUN") else 2)
        if args.cmd == "uninstall":
            out = launchd.uninstall(apply=args.apply)
            return _emit(out, 0 if out["status"] in ("OK", "DRY_RUN") else 2)
        from app.forward_auto import backup, backup_source

        if args.bcmd == "plan":
            return _emit(backup_source.plan(REPO, args.target))
        if not args.apply:
            return _emit(
                {
                    "status": "DRY_RUN",
                    "note": "--apply 없이 쓰지 않음",
                    "plan": backup_source.plan(REPO, args.target),
                }
            )
        if args.bcmd == "run":
            out = backup.run(REPO, args.target)
        else:
            out = backup.verify(REPO, args.target, args.backup_id)
        return _emit(
            out, 0 if out["status"] in ("COPY_HASH_OK", "RESTORE_VERIFIED") else 2
        )
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        return _emit(
            {"status": "FAILED", "error": f"{type(e).__name__}: {str(e)[:300]}"}, 1
        )


if __name__ == "__main__":
    sys.exit(main())
