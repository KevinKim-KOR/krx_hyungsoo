"""POC7-02 로컬 AI 주간 ETF 검토 한 장 요약 — 맥북 CLI(PC 수동 연구 · cron 없음).

```text
archive   --selected <고른 ETF 코드> [--answer GPT=<파일> --answer Claude=<파일>]
          [--server http://127.0.0.1:8000]
lock-key  --case <사례> --key <채점용 메모 파일>          (모델 출력 전에)
pack      --case <사례> [--num-ctx N --num-predict N --reason "…"]   → 실행 묶음 zip(USB 로 Windows PC)
merge     --case <사례> --result <USB 의 result_<n> 폴더>             → 대조 · 보관
report    --case <사례> --score <채점 JSON> --usage <사용 기록 JSON>  → 비교표 · AC4 판정(화면에 출력)
```
마지막 줄 = `RESULT {json}` · rc 0 = 됨 · 2 = 확인 필요(CheckRequired · 이미 있음).
쓰기는 `state/ml/research/poc7_02/`(git 제외)에만 한다. 운영 화면 · API · 기록 DB 는 바꾸지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.entry_timing.protocol import CheckRequired  # noqa: E402
from app.review_summary import bundle, case, merge, report  # noqa: E402


def _answers(items: list[str]) -> list[tuple[str, bytes]]:
    out = []
    for it in items:
        author, sep, path = it.partition("=")
        if not sep:
            raise CheckRequired(f"--answer 는 작성자=파일 꼴: {it!r}")
        out.append((author.strip(), Path(path).read_bytes()))
    return out


class _Parser(argparse.ArgumentParser):
    """인자 오류도 마지막 줄 RESULT 로(rc 2) — 화면 오류로 끝내지 않는다."""

    def error(self, message: str) -> None:  # type: ignore[override]
        raise ValueError(f"인자 오류: {message}")


def run(argv: list[str]) -> dict:
    ap = _Parser(prog="run_review_summary")
    ap.add_argument("--root", default=str(case.ROOT))
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("archive")
    a.add_argument("--selected", required=True)
    a.add_argument("--answer", action="append", default=[])
    a.add_argument("--server", default=case.DEFAULT_SERVER)
    k = sub.add_parser("lock-key")
    k.add_argument("--case", required=True)
    k.add_argument("--key", required=True)
    p = sub.add_parser("pack")
    p.add_argument("--case", required=True)
    p.add_argument("--num-ctx", type=int)
    p.add_argument("--num-predict", type=int)
    p.add_argument("--reason", default="")
    m = sub.add_parser("merge")
    m.add_argument("--case", required=True)
    m.add_argument("--result", required=True)
    r = sub.add_parser("report")
    r.add_argument("--case", required=True)
    r.add_argument("--score", required=True)
    r.add_argument("--usage", required=True)
    args = ap.parse_args(argv)
    root = Path(args.root)
    if args.cmd == "archive":
        raw = case.fetch_weekly(args.server, args.selected)
        src = f"GET {args.server}{case.WEEKLY_PATH}?selected={args.selected}"
        d = case.archive(
            root,
            response=raw,
            selected=args.selected,
            answers=_answers(args.answer),
            source=src,
        )
        return {"status": "OK", "case": d.name, "dir": str(d)}
    if args.cmd == "lock-key":
        lock = case.lock_key(root, args.case, Path(args.key).read_bytes())
        return {"status": "OK", **lock}
    if args.cmd == "pack":
        lengths = {
            k2: v
            for k2, v in (("num_ctx", args.num_ctx), ("num_predict", args.num_predict))
            if v is not None
        }
        d = bundle.pack(root, args.case, lengths=lengths or None, reason=args.reason)
        return {"status": "OK", "bundle": d.name, "zip": str(d / "bundle.zip")}
    if args.cmd == "merge":
        d = merge.merge(root, args.case, Path(args.result))
        rec = json.loads((d / "merge.json").read_text(encoding="utf-8"))
        return {"status": "OK", "dir": str(d), "result_status": rec["checks"]["status"]}
    # NaN · Infinity · 1e309 는 실측이 아니다 — 읽을 때 거부(검증자 r2 F8)
    score = case.strict_loads(Path(args.score).read_text(encoding="utf-8"))
    usage = case.strict_loads(Path(args.usage).read_text(encoding="utf-8"))
    c = case.load_case(root, args.case)
    table, verdict = report.build(
        root, args.case, score, usage, answers=bool(c["answers"])
    )
    print(table)
    return {"status": "OK", **verdict}


def main(argv: list[str] | None = None) -> int:
    try:
        out = run(sys.argv[1:] if argv is None else argv)
        rc = 0
    except (  # 사람이 적은 기록의 모양 오류까지 RESULT 줄로(그 밖은 코드 결함 — 그대로 올림)
        CheckRequired,
        FileExistsError,
        ValueError,
        OSError,
        TypeError,
        AttributeError,
        OverflowError,
        RecursionError,
    ) as e:
        out = {"status": "CHECK_REQUIRED", "error": f"{type(e).__name__}: {e}"}
        rc = 2
    print("RESULT " + json.dumps(out, ensure_ascii=False))
    return rc


if __name__ == "__main__":
    sys.exit(main())
