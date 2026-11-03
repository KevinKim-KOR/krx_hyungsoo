"""POC6-19 — 실행 폴더 검산(외부 재조회 0 · 원시에서 다시 계산해 대조).

1. files.json 의 모든 파일 바이트 수 · sha256 이 같고, 목록에 없는 파일이 없는가.
2. 원시 본문 sha256 이 본문과 같은가(키움 줄 · Yahoo 파일).
3. 원시 + 입력 사본에서 정규화 표를 다시 만들어 저장 CSV 와 바이트가 같은가(요약끼리만 비교하지 않음).
4. 다시 만든 정규화 표 + run_start · run_end 로 report.json · report.md 를 다시 만들어 같은가.
5. 입력 전제 · 상한(검증자 r1 F1 · F2): 입력 봉인 판 = SEALED · 실행 중 봉인 판 불변 · 새 파일 합계 · 메모리 ·
   후처리 시간 상한을 넘었다면 그 사실이 run_end 또는 postprocess.json 에 기록돼 있는가.

누군가 모든 파일을 서로 맞게 바꾼 위조까지 인증하지 않는다(설계 §7). 외부 공급자의 원래 과거 공개 판 ·
가격 정확성 전체도 보증하지 않는다.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.market_history import normalize as N
from app.market_history import report as R
from app.ml_baseline_snapshot import file_sha256

_SKIP = {"files.json"}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify_run(run_dir: Path) -> dict:
    run_dir = Path(run_dir)
    problems: list[str] = []
    listed = json.loads((run_dir / "files.json").read_text(encoding="utf-8"))["files"]
    names = {f["path"] for f in listed}
    for f in listed:
        p = run_dir / f["path"]
        if not p.is_file():
            problems.append(f"파일 없음: {f['path']}")
        elif p.stat().st_size != f["bytes"] or file_sha256(p) != f["sha256"]:
            problems.append(f"파일 바이트 · sha256 다름: {f['path']}")
    for p in sorted(run_dir.rglob("*")):
        rel = str(p.relative_to(run_dir))
        if p.is_file() and rel not in _SKIP and rel not in names:
            problems.append(f"목록에 없는 파일: {rel}")

    lines = N.read_jsonl(run_dir / N.KIWOOM_RAW)
    for ln in lines:
        if "body" in ln and _sha(ln["body"]) != ln.get("body_sha256"):
            problems.append(f"키움 원시 본문 sha256 다름: 순번 {ln['seq']}")
    for doc in N.load_yahoo_docs(run_dir):
        if "body" in doc and _sha(doc["body"]) != doc.get("body_sha256"):
            problems.append(f"Yahoo 원시 본문 sha256 다름: {doc['file']}")

    tables = N.build_tables(run_dir)
    for rel, text in N.rendered_files(tables).items():
        p = run_dir / rel
        if not p.is_file() or p.read_text(encoding="utf-8") != text:
            problems.append(f"정규화 다시 계산 결과가 다름: {rel}")
    run_start = json.loads((run_dir / "run_start.json").read_text(encoding="utf-8"))
    run_end = json.loads((run_dir / "run_end.json").read_text(encoding="utf-8"))
    pp_path = run_dir / "postprocess.json"
    post = json.loads(pp_path.read_text(encoding="utf-8")) if pp_path.is_file() else {}
    post_error = (
        post.get("error") if (post.get("error") or {}).get("type") == "LIMIT" else None
    )
    report = R.build_report(tables, run_start, run_end, post_error)
    for rel, text in (
        ("report.json", R.render_json(report)),
        ("report.md", R.render_md(report)),
    ):
        p = run_dir / rel
        if not p.is_file() or p.read_text(encoding="utf-8") != text:
            problems.append(f"보고 다시 계산 결과가 다름: {rel}")
    problems += _premise_problems(run_dir, listed, tables, run_start, run_end)
    return {
        "status": "OK" if not problems else "MISMATCH",
        "problems": problems,
        "checked": {
            "files": len(listed),
            "kiwoom_lines": len(lines),
            "flow_dates": len(tables["flow_dates"]),
            "macro_rows": len(tables["macro"]),
        },
    }


def _premise_problems(run_dir: Path, listed, tables, run_start, run_end) -> list[str]:
    out: list[str] = []
    status = tables["inputs"]["sealed"].get("status")
    if status != "SEALED":
        out.append(f"입력 봉인 판 상태가 SEALED 가 아님: {status}")
    if run_end.get("sealed_unchanged") is not True:
        out.append("실행 중 봉인 판 파일이 바뀌었거나 확인 기록이 없음")
    pp_path = run_dir / "postprocess.json"
    post = json.loads(pp_path.read_text(encoding="utf-8")) if pp_path.is_file() else {}
    recorded = " ".join(
        str((x or {}).get("message", ""))
        for x in (run_end.get("error"), post.get("error"))
    )
    limits = run_start.get("limits", {})
    total = sum(f["bytes"] for f in listed if f["path"] != "postprocess.json")
    if total > limits.get("max_bytes", total) and "파일 용량 상한" not in recorded:
        out.append(f"파일 용량 상한 초과가 기록되지 않음({total} 바이트)")
    rss = max(
        (run_end.get("resources") or {}).get("peak_rss_bytes") or 0,
        post.get("peak_rss_bytes") or 0,
    )
    if rss >= limits.get("max_rss_bytes", rss + 1) and "메모리 상한" not in recorded:
        out.append(f"메모리 상한 초과가 기록되지 않음({rss} 바이트)")
    elapsed, cap = post.get("elapsed_seconds"), post.get("limit_seconds")
    if elapsed and cap and elapsed > cap and "후처리 시간 상한" not in recorded:
        out.append(f"후처리 시간 상한 초과가 기록되지 않음({elapsed}초)")
    return out
