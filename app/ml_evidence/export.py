"""POC6-05 — 기준 시각 이하 공개 판 고르기(PC 연구 입력 · 외부 조회 · 학습 · DB 쓰기 0).

- 공개된 정상 묶음(OK · PARTIAL · SKIPPED_NO_NEW)만, 그리고 `published_at`(= available_at) ≤ as-of 만 쓴다.
  관측일이 앞이라는 이유로 나중에 공개된 정정 판을 넣지 않는다. FAILED · 미완료 · 손상 자료는 내보내지 않는다.
- 네이버 수신 창은 종목마다 가장 새 판 하나를 **그대로** 낸다(여러 판을 이어 붙이지 않는다 · 02 형식 호환 아님).
- KRX · 지수는 기준 시각 이하 마지막 묶음의 21거래일 지도(이전 판 참조 포함)를 따른다.
- PARTIAL 묶음의 실패 범위(미확보 종목 · 실패 날짜)는 export manifest 에 함께 적는다.
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.ml_evidence import store

EXPORT_ROOT = Path("state/ml/research/poc6_05_exports")
USABLE = ("OK", "PARTIAL", "SKIPPED_NO_NEW")
TABLE_SOURCES = ("krx_etf_close", "krx_stock_close", "benchmarks")


def parse_as_of(text: str) -> str:
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("as-of 에 시간대가 없음(UTC 'Z' 또는 +09:00 등)")
    return store.iso(dt.astimezone(timezone.utc))


def _lines(root: Path, sha: Optional[str], problems: list[str]) -> list[dict]:
    if not sha:
        return []
    try:
        return store.read_jsonl_gz(root, sha)
    except (OSError, ValueError, EOFError, store.EvidenceError) as e:
        problems.append(
            f"object {sha[:16]} 손상 · 읽기 불가({type(e).__name__}) — 제외"
        )
        return []


def _json(root: Path, sha: str, problems: list[str]) -> list[dict]:
    """받은 값 하나 = JSON object 하나(수급 날짜 · FX 계열)."""
    try:
        return [json.loads(store.read_object(root, sha).decode("utf-8"))]
    except (OSError, ValueError, UnicodeDecodeError, store.EvidenceError) as e:
        problems.append(
            f"object {sha[:16]} 손상 · 읽기 불가({type(e).__name__}) — 제외"
        )
        return []


def select(root: Path, as_of: str, tickers: Optional[set[str]] = None) -> dict:
    runs, list_problems = store.list_runs(root)
    limit = store.parse_iso(as_of)  # 문자열 비교가 아니라 실제 시각 비교
    eligible = [
        r
        for r in runs
        if r.manifest["kind"] == "DAILY_COLLECTION"
        and r.manifest["status"] in USABLE
        and store.parse_iso(r.manifest["published_at"]) <= limit
    ]
    eligible.sort(key=lambda r: (store.parse_iso(r.manifest["published_at"]), r.run_id))
    problems = list(list_problems)
    windows: dict[str, dict] = {}
    fx: dict[str, dict] = {}
    flows: dict[str, dict] = {}
    used = []
    for r in eligible:
        src = r.manifest["sources"]
        pub = r.manifest["published_at"]
        nw = src.get("naver_etf_windows", {})
        for line in _lines(root, nw.get("object"), problems):
            if line["status"] in ("OK", "NO_NEW_ROW") and (
                not tickers or line["ticker"] in tickers
            ):
                windows[line["ticker"]] = line | {
                    "run_id": r.run_id,
                    "published_at": pub,
                }
        for sha in src.get("fx_wti", {}).get("objects", []):
            for line in _json(root, sha, problems):
                fx[line["series_id"]] = line | {"run_id": r.run_id, "published_at": pub}
        for sha in src.get("investor_flow", {}).get("objects", []):
            for line in _json(root, sha, problems):
                flows[line["date"]] = line | {"run_id": r.run_id, "published_at": pub}
        used.append(
            {
                "run_id": r.run_id,
                "status": r.manifest["status"],
                "published_at": pub,
                "naver_missing": nw.get("missing", []),
                "flow_failed": src.get("investor_flow", {}).get("failed", {}),
            }
        )
    tables = {}
    if eligible:
        last = eligible[-1]
        for name in TABLE_SOURCES:
            mp = last.manifest["sources"].get(name, {}).get("map", {})
            by_obj: dict[str, list[str]] = {}
            for key, ref in mp.items():
                by_obj.setdefault(ref["obj"], []).append(key)
            rows = []
            for sha, keys in sorted(by_obj.items()):
                want = set(keys)
                rows += [x for x in _lines(root, sha, problems) if x["key"] in want]
            tables[name] = {
                "from_run": last.run_id,
                "rows": sorted(rows, key=lambda x: x["key"]),
            }
    return {
        "windows": windows,
        "fx": fx,
        "flows": flows,
        "tables": tables,
        "used": used,
        "problems": problems,
    }


def export(
    *,
    root: Path,
    as_of: str,
    now: datetime,
    out_root: Optional[Path] = None,
    tickers: Optional[set[str]] = None,
) -> tuple[str, Path]:
    out_root = out_root or EXPORT_ROOT
    root_r, out_r = root.resolve(), out_root.resolve()
    if out_r == root_r or root_r in out_r.parents:
        raise store.EvidenceError("export 출력이 보관소 안")
    sel = select(root, as_of, tickers)
    out_root.mkdir(parents=True, exist_ok=True)
    name = f"{now:%Y%m%dT%H%M%SZ}_{uuid.uuid4().hex[:8]}"
    staging = out_root / f".{name}.partial"
    staging.mkdir()
    try:
        files = {
            "naver_etf_windows.jsonl": [
                sel["windows"][t] for t in sorted(sel["windows"])
            ],
            "fx_wti.jsonl": [sel["fx"][k] for k in sorted(sel["fx"])],
            "investor_flow.jsonl": [sel["flows"][k] for k in sorted(sel["flows"])],
        }
        for tname, t in sel["tables"].items():
            files[f"{tname}.jsonl"] = t["rows"]
        counts = {}
        for fname, rows in files.items():
            with open(staging / fname, "x", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            counts[fname] = len(rows)
        manifest = {
            "schema": "poc6_05_export_v1",
            "as_of": as_of,
            "created_at": store.iso(now),
            "runs_used": sel["used"],
            "table_maps_from": {k: v["from_run"] for k, v in sel["tables"].items()},
            "counts": counts,
            "problems": sel["problems"],
            "rules": [
                "published_at(= available_at) ≤ as_of 인 공개된 OK · PARTIAL · SKIPPED_NO_NEW 묶음만",
                "네이버 수신 창 = 종목마다 가장 새 판 하나 그대로(판을 이어 붙이지 않음 · 02 형식 호환 아님 · 장기 이력 없음)",
                "KRX · 지수 = 마지막 묶음의 최근 21거래일 지도(그 밖 과거 정정 보존 주장 안 함)",
                "회고 자료 · 연구 입력 · 운영 사용 아님",
            ],
        }
        with open(staging / "export_manifest.json", "x", encoding="utf-8") as fh:
            fh.write(
                json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=1)
                + "\n"
            )
        final = out_root / name
        os.rename(staging, final)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return ("PARTIAL" if sel["problems"] else "OK"), final
