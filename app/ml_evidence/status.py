"""POC6-05 — 보관 상태 읽기(설계 §7 · PLAN §4-4 · 읽기 전용).

보관 목록 · 자료원별 최신 관측일 · 받은 시각 · 실패 · 미확보 · 연구 실험의 입력 · 예측 · 정답 연결 ·
(원격 목록을 주면) 두 번째 사본이 없는 묶음을 보여 준다. 외부 조회 · 쓰기 없음.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.ml_evidence import store

RECENT = 30


def _max_observed(root: Path, sha: Optional[str]) -> Optional[str]:
    if not sha:
        return None
    try:
        lines = store.read_jsonl_gz(root, sha)
    except (OSError, ValueError, EOFError, store.EvidenceError):
        return "읽기 불가(손상)"
    got = [x["observed_at"] for x in lines if x.get("observed_at")]
    return max(got) if got else None


def _table(sec: dict) -> dict:
    keys = sorted(sec.get("map") or {})
    return {
        "status": sec.get("status"),
        "latest_key": keys[-1] if keys else None,
        "changed_keys": sec.get("changed_keys"),
        "repaired_keys": sec.get("repaired_keys"),
        "behind_target": sec.get("behind_target"),
        "time_meaning": "DB 마지막 쓰기 시각(최초 확보 아님)",
    }


def daily_detail(root: Path, m: dict) -> dict:
    src = m.get("sources", {})
    nw, lst = src.get("naver_etf_windows", {}), src.get("etf_list", {})
    fx, fl = src.get("fx_wti", {}), src.get("investor_flow", {})
    return {
        "run_id": m["run_id"],
        "status": m["status"],
        "published_at": m.get("published_at"),
        "integrity_error": m.get("integrity_error"),
        "etf_list": {
            "status": lst.get("status"),
            "effective": {
                k: (lst.get("effective") or {}).get(k)
                for k in ("list_date", "count", "stale", "from_run")
            },
            "reason": lst.get("reason"),
        },
        "naver_etf_windows": {
            "status": nw.get("status"),
            "target_day": nw.get("target_day"),
            "counts": nw.get("counts"),
            "have_total": nw.get("have_total"),
            "missing": (nw.get("missing") or [])[:50],
            "missing_count": len(nw.get("missing") or []),
            "stop_reason": nw.get("stop_reason"),
            "observed_at_latest": _max_observed(root, nw.get("object")),
        },
        "fx_wti": {
            sid: {
                "state": s.get("state"),
                "last": (s.get("received") or {}).get("last"),
                "observed_at": (s.get("received") or {}).get("observed_at"),
                "reason": s.get("reason"),
            }
            for sid, s in (fx.get("series") or {}).items()
        },
        "investor_flow": {
            "status": fl.get("status"),
            "latest_received": max(fl.get("received") or [None], key=str),
            "failed": fl.get("failed"),
            "not_attempted": fl.get("not_attempted"),
            "not_attempted_extra": fl.get("not_attempted_extra"),
            "reason": fl.get("reason"),
            "mismatch": fl.get("mismatch"),
        },
        "krx_etf_close": _table(src.get("krx_etf_close", {})),
        "krx_stock_close": _table(src.get("krx_stock_close", {})),
        "benchmarks": _table(src.get("benchmarks", {})),
        "batch_records": {"status": src.get("batch_records", {}).get("status")},
        "resources": m.get("resources"),
    }


def research_links(m: dict) -> list[dict]:
    out = []
    for e in m.get("experiments", []):
        links = e.get("links") or {}
        out.append(
            {
                "experiment_id": e.get("experiment_id"),
                "record_type": e.get("record_type"),
                "predictions": e.get("predictions"),
                "truth": e.get("truth"),
                "inputs": {
                    k: links.get(k)
                    for k in (
                        "input_digest",
                        "recipe_digest",
                        "targets",
                        "dependencies",
                    )
                    if k in links
                },
                "verdicts": links.get("verdicts"),
                "trained_artifact": e.get("trained_artifact"),
                "run_commit": e.get("run_commit"),
                "links_error": links.get("error"),
            }
        )
    return out


def summarize(root: Path, remote_rows: Optional[list[dict]] = None) -> dict:
    runs, problems = store.list_runs(root)
    by: dict[str, int] = {}
    for r in runs:
        key = f"{r.manifest['kind']}:{r.manifest['status']}"
        by[key] = by.get(key, 0) + 1
    daily = [r for r in runs if r.manifest["kind"] == "DAILY_COLLECTION"]
    research = [r for r in runs if r.manifest["kind"] == "RESEARCH_REGISTRATION"]
    out = {
        "status": "OK" if not problems else "CHECK_REQUIRED",
        "runs": len(runs),
        "by_kind_status": by,
        "recent_runs": [
            {
                "run_id": r.run_id,
                "kind": r.manifest["kind"],
                "status": r.manifest["status"],
                "published_at": r.manifest["published_at"],
                "site": r.manifest.get("site"),
                "receipt": r.receipt,
            }
            for r in runs[-RECENT:]
        ],
        "latest_daily": daily_detail(root, daily[-1].manifest) if daily else None,
        "research": [
            {"run_id": r.run_id, "status": r.manifest["status"]}
            | {"experiments": research_links(r.manifest)}
            for r in research
        ],
        "partial_dirs": store.partial_dirs(root),
        "damaged": {
            r.run_id: bad
            for r in runs
            if (bad := store.damaged_objects(root, r.manifest))
        },
        "problems": problems,
    }
    if out["damaged"]:
        out["status"] = "CHECK_REQUIRED"
    if remote_rows is not None:
        here = {r.run_id: r.manifest_sha256 for r in runs}
        there = {x["run_id"]: x["manifest_sha256"] for x in remote_rows}
        out["second_copy"] = {
            "remote_only(이 장소에 사본 없음)": sorted(set(there) - set(here)),
            "local_only(원격에 없음)": sorted(set(here) - set(there)),
            "hash_conflicts": sorted(
                k for k in set(here) & set(there) if here[k] != there[k]
            ),
        }
    return out
