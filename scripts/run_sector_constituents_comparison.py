"""POC6-30 — 섹터요약 보강 대조 실행(대조용 DB 사본 수집 · 대조표).

PLAN `docs/ai_plan/POC6/POC6_30_SECTOR_SUMMARY_CONSTITUENTS_PLAN_V1.md` §3 ·
판정 `…_PLAN_DECISION_2026-11-14.md`.

```text
collect  표본당 한 번(검증자 r1 F1 — 외부 호출 30회 상한은 실행 폴더가 아니라 표본 전체에 적용)
         보관 응답 해시 확인 → 같은 표본의 예전 수집 기록(연구 폴더 안 collect.json · 시작 표시)이 있으면 거절
         → 표본 수집 표시(<연구 폴더>/collect_claims/<보관 응답 SHA-256>.json)를 원자적으로 만듦(이미 있으면 거절)
         → 실행 폴더 시작 표시도 원자적으로 만듦 → 두 표시는 실패해도 지우지 않음(다시 수집 = 사용자 판단)
         → 운영 시장 DB 를 읽기 전용으로 열어 사본(<run_dir>/market_data_copy.sqlite)으로 백업
         → 기존 수집 기능(refresh_constituents)에 사본 경로 · 선정 순서 10개씩 · 외부 호출 합계 30회 이내
         → 시간 초과로 건너뛴 ETF 는 남은 한도에서 한 번 보충 → 운영 DB 구성종목 표 전후 같음 확인
report   외부 호출 0 · 사본 읽기 전용 · 대조 1 · 2 · 3 · 근거 · 범위 · Q5 재현 → <run_dir>/report.json + 대조표 HTML
```
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from app import sector_constituents_comparison as C  # noqa: E402
from app.api_etf_compare import _dictionary, _official  # noqa: E402
from app.etf_constituents_service import (  # noqa: E402
    DEFAULT_TOP_K,
    MAX_TICKERS_PER_REQUEST,
    refresh_constituents,
)
from app.etf_constituents_store import _utcnow_iso  # noqa: E402
from app.market_data_store import DEFAULT_DB_PATH  # noqa: E402
from app.pc_etf_compare_summary import build_summary  # noqa: E402
from app.sector_constituents_report import render_html  # noqa: E402

SNAPSHOT = (
    REPO
    / "state/ml/research/poc6_30/plan_snapshot_20261114T1437/summary_one_month_before.json"
)
SNAPSHOT_SHA256 = "b9119b1ccb4ac6d90346284dae2202d8eb6b852f167ce8b40934ba047bd5855a"
REQUEST_ASOF = (
    "2026-11-13"  # 화면과 같은 요청 기준일 = 목록 끝일(ListTransfer · draft.asof)
)
CALL_LIMIT = 30  # 판정 Q1 — 이번 표본 외부 호출 합계 상한
HTML_OUT = (
    REPO / "docs/ai_result/POC6/POC6_30_SECTOR_SUMMARY_CONSTITUENTS_COMPARISON.html"
)
COPY_NAME = "market_data_copy.sqlite"
STARTED_NAME = "collect_started.json"
RESEARCH_ROOT = (
    REPO / "state/ml/research/poc6_30"
)  # 보관 응답 · 실행 폴더 · 표본 수집 표시
CLAIMS_NAME = "collect_claims"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_snapshot(
    path: Path = SNAPSHOT, sha256: str = SNAPSHOT_SHA256
) -> dict[str, Any]:
    data = path.read_bytes()
    got = hashlib.sha256(data).hexdigest()
    if got != sha256:
        raise SystemExit(f"보관 응답 해시가 다릅니다: {got}")
    return json.loads(data)


def _ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def table_fingerprint(db: Path) -> dict[str, Any]:
    """구성종목 표 · 수집 기록 표의 행 수와 내용 해시(운영 DB 를 건드리지 않았는지 확인용)."""
    con = _ro(db)
    try:
        out: dict[str, Any] = {}
        for table, order in (
            ("etf_constituents", "etf_ticker, asof, source, rank"),
            ("etf_constituent_refresh_log", "etf_ticker, asof, created_at"),
        ):
            h = hashlib.sha256()
            n = 0
            for row in con.execute(f"SELECT * FROM {table} ORDER BY {order}"):
                h.update(repr(row).encode("utf-8"))
                n += 1
            out[table] = {"rows": n, "sha256": h.hexdigest()}
        return out
    finally:
        con.close()


def copy_db(src: Path, dst: Path) -> None:
    s, d = _ro(src), sqlite3.connect(str(dst))
    try:
        s.backup(d)
    finally:
        d.close()
        s.close()


def prior_collects(root: Path, sha256: str, tickers: list[str]) -> list[str]:
    """연구 폴더 안에서 같은 표본을 이미 수집(시작)한 기록 — 표본 수집 표시가 생기기 전 실행 폴더 포함.

    표본 = 보관 응답 SHA-256 이 같은 것(예전 시작 표시처럼 해시 칸이 없으면 ETF 목록이 같은 것).
    읽을 수 없는 기록은 수집한 것으로 본다(상한을 넘기지 않는 쪽).
    """
    found: list[str] = []
    if not root.exists():
        return found
    for name in ("collect.json", STARTED_NAME):
        for p in sorted(root.rglob(name)):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                found.append(str(p))
                continue
            if not isinstance(d, dict):
                found.append(str(p))
            elif d.get("snapshot_sha256") == sha256 or (
                d.get("snapshot_sha256") is None and d.get("tickers") == tickers
            ):
                found.append(str(p))
    return found


def create_once(path: Path, payload: Mapping[str, Any]) -> bool:
    """파일이 없을 때만 만든다(O_EXCL · 동시에 두 실행이 와도 하나만 성공)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False))
    return True


def collect(
    run_dir: Path,
    *,
    research_root: Path,
    live_db: Path = DEFAULT_DB_PATH,
    snapshot_path: Path = SNAPSHOT,
    snapshot_sha256: str = SNAPSHOT_SHA256,
    refresh: Callable[..., Any] = refresh_constituents,
) -> dict[str, Any]:
    """`research_root` 는 일부러 기본값이 없다(시험이 실제 연구 폴더에 표본 표시를 남기지 않게 · main 만 실제 경로)."""
    out_path = run_dir / "collect.json"
    marker = run_dir / STARTED_NAME
    if out_path.exists() or marker.exists():
        raise SystemExit(
            "이 실행 폴더는 이미 수집을 시작했습니다(collect.json · 시작 표시)."
        )
    snap = load_snapshot(snapshot_path, snapshot_sha256)
    tickers = [r["ticker"] for r in snap["top"]]
    copy = run_dir / COPY_NAME
    if copy.resolve() == Path(live_db).resolve():
        raise SystemExit("사본 경로가 운영 DB 와 같습니다.")
    # 검증자 r1 F1 — 외부 호출 30회 상한은 이 표본 전체에 적용된다. 다른 실행 폴더 · 겹친 실행도 막도록
    # 표본 수집 표시를 첫 백업 · 호출 전에 원자적으로 만들고, 실패해도 지우지 않는다.
    prior = prior_collects(research_root, snapshot_sha256, tickers)
    if prior:
        raise SystemExit(
            "이 표본은 이미 수집했습니다(외부 호출 상한은 표본 전체): "
            + ", ".join(prior)
        )
    claim = research_root / CLAIMS_NAME / f"{snapshot_sha256}.json"
    stamp = {
        "claimed_at": _utcnow_iso(),
        "snapshot_sha256": snapshot_sha256,
        "run_dir": str(run_dir.resolve()),
        "call_limit": CALL_LIMIT,
        "tickers": tickers,
    }
    if not create_once(claim, stamp):
        raise SystemExit(f"이 표본은 이미 수집을 시작했습니다(표본 수집 표시 {claim}).")
    run_dir.mkdir(parents=True, exist_ok=True)
    if not create_once(marker, stamp):
        raise SystemExit("이 실행 폴더는 이미 수집을 시작했습니다(시작 표시).")
    before = table_fingerprint(live_db)
    copy_db(live_db, copy)
    # 수집 기록 created_at 과 같은 형식이라 문자열 비교가 시각 비교와 같다
    started = _utcnow_iso()
    calls = 0
    batches: list[dict[str, Any]] = []
    items: dict[str, dict[str, Any]] = {}

    def run(chunk: list[str], label: str) -> None:
        nonlocal calls
        res = refresh(
            asof=REQUEST_ASOF,
            tickers=chunk,
            top_k=DEFAULT_TOP_K,
            force=False,
            db_path=copy,
        )
        calls += res.fetched_count
        batches.append(
            {
                "label": label,
                "tickers": chunk,
                "status": res.status,
                "reason": res.reason,
                "fetched": res.fetched_count,
                "cached": res.cached_count,
                "failed": res.fail_count,
                "skipped": res.skipped_count,
                "at": _now(),
            }
        )
        for it in res.items:
            items[it.ticker] = asdict(it)

    for i in range(0, len(tickers), MAX_TICKERS_PER_REQUEST):
        end = i + MAX_TICKERS_PER_REQUEST
        chunk = tickers[i:end][: max(0, CALL_LIMIT - calls)]
        if chunk:
            run(chunk, f"묶음 {i // MAX_TICKERS_PER_REQUEST + 1}")
    retry = [t for t in tickers if items.get(t, {}).get("status") == "skipped_timeout"]
    for i in range(0, len(retry), MAX_TICKERS_PER_REQUEST):
        end = i + MAX_TICKERS_PER_REQUEST
        chunk = retry[i:end][: max(0, CALL_LIMIT - calls)]
        if chunk:
            run(chunk, "보충")
    con = _ro(copy)
    try:
        for t in tickers:
            log = con.execute(
                "SELECT asof, status, created_at FROM etf_constituent_refresh_log "
                "WHERE etf_ticker = ? AND created_at >= ? ORDER BY created_at DESC LIMIT 1",
                (t, started),
            ).fetchone()
            if t in items and log:
                items[t]["saved_asof"] = log[0] if log[1] == "ok" else None
                items[t]["logged_at"] = log[2]
    finally:
        con.close()
    after = table_fingerprint(live_db)
    if after != before:
        raise SystemExit("운영 DB 구성종목 표가 실행 중 바뀌었습니다.")
    doc = {
        "started_at": started,
        "finished_at": _now(),
        "snapshot_sha256": snapshot_sha256,
        "sample_claim": str(claim),
        "request_asof": REQUEST_ASOF,
        "top_k": DEFAULT_TOP_K,
        "call_limit": CALL_LIMIT,
        "external_calls": calls,
        "batches": batches,
        "items": items,
        "live_before": before,
        "live_after": after,
    }
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc


def q5_reproduce(
    copy: Path, snap: dict[str, Any], official, ometa, dictionary, dmeta
) -> dict[str, Any]:
    """판정 Q5 — 사본으로 운영 요약을 만들어 공통 구성종목에 주식 외 행이 나오는지(보유 정보 없이)."""
    con = _ro(copy)
    try:
        etf = {r[0] for r in con.execute("SELECT ticker FROM etf_master")}
        every = [
            r[0]
            for r in con.execute("SELECT DISTINCT etf_ticker FROM etf_constituents")
        ]
        latest = C.read_latest_rows(con, every)
    finally:
        con.close()
    kind_by_key = {
        row["match_key"]: C.row_kind(row, etf)
        for d in latest.values()
        for row in d["top"]
        if row["match_key"]
    }
    out: dict[str, Any] = {}
    for basis in ("one_month", "three_month"):
        s = build_summary(
            db_path=copy,
            basis=basis,
            filters=snap["filters"],
            official=official,
            official_meta=ometa,
            dictionary=dictionary,
            dictionary_meta=dmeta,
            held_tickers=[],
            holdings_status="none",
        )
        found = []
        groups = [
            g for side in ("top", "bottom") for g in s.get("groups", {}).get(side, [])
        ]
        for side in ("top", "bottom"):
            for g in s.get("groups", {}).get(side, []):
                for c in g["constituents"]["common"]:
                    kind = kind_by_key.get(c["key"], C.UNKNOWN)
                    if kind not in C.STOCK_KINDS:
                        found.append(
                            {
                                "side": side,
                                "group": g["name"],
                                "name": c["name"],
                                "kind": kind,
                            }
                        )
        # 검증자 r1 F4 — 요약을 만들지 못했거나(status) 비교한 묶음이 없으면 '0건'이 아니다
        scope = C.group_scope(groups)
        out[basis] = {
            "status": s.get("status"),
            "message": s.get("message"),
            "end_date": s.get("end_date"),
            "top": [r["ticker"] for r in s.get("top", [])],
            "groups_total": scope["groups"],
            "groups_compared": scope["compared"],
            "common_checked": scope["common"],
            "non_stock_common": found,
        }
    return out


def source_key(official_meta: dict[str, Any], dictionary_meta: dict[str, Any]) -> tuple:
    return (
        official_meta.get("name"),
        official_meta.get("csv_asof"),
        official_meta.get("rows"),
        dictionary_meta.get("sha256"),
    )


def report(
    run_dir: Path,
    *,
    html_out: Path = HTML_OUT,
    snapshot_path: Path = SNAPSHOT,
    snapshot_sha256: str = SNAPSHOT_SHA256,
    sources: tuple | None = None,
) -> dict[str, Any]:
    """`sources` = (official, official_meta, dictionary, dictionary_meta) · 없으면 화면과 같은 곳에서 읽는다."""
    snap = load_snapshot(snapshot_path, snapshot_sha256)
    collected = json.loads((run_dir / "collect.json").read_text(encoding="utf-8"))
    copy = run_dir / COPY_NAME
    if sources is None:
        official, ometa = _official()
        dictionary, dmeta = _dictionary()
    else:
        official, ometa, dictionary, dmeta = sources
    # 보관 응답이 쓴 공식 기준정보 · 사전과 같아야 분류 · 근거가 표본과 맞는다(독립 검토 10)
    want = source_key(snap["sources"]["official_csv"], snap["sources"]["dictionary"])
    if source_key(ometa, dmeta) != want:
        raise SystemExit(f"공식 기준정보 · 사전이 보관 응답과 다릅니다: {want}")
    frozen = snap["top"]
    con = _ro(copy)
    try:
        etf_names = dict(con.execute("SELECT ticker, name FROM etf_master"))
        etf = set(etf_names)
        every = [
            r[0]
            for r in con.execute("SELECT DISTINCT etf_ticker FROM etf_constituents")
        ]
        latest_all = C.read_latest_rows(con, every)
        latest = {
            r["ticker"]: latest_all[r["ticker"]]
            for r in frozen
            if r["ticker"] in latest_all
        }
        kind_by_key = {
            row["match_key"]: C.row_kind(row, etf)
            for d in latest_all.values()
            for row in d["top"]
            if row["match_key"]
        }
        c2 = C.comparison_two(
            con, frozen, kind_by_key, snap.get("both_side_sectors", [])
        )
    finally:
        con.close()
    visible = {
        c["key"]
        for g in c2["groups"]
        for c in g["constituents"]["common"]
        if c["kind"] in C.STOCK_KINDS
    }
    c3 = C.comparison_three(frozen, latest, etf, visible)
    evidence = C.sector_evidence(
        latest_all, {x["key"] for x in c3}, official, dictionary, etf_names
    )
    cov = C.coverage(frozen, latest, collected["items"], etf, snap["end_date"])
    q5 = q5_reproduce(copy, snap, official, ometa, dictionary, dmeta)
    doc = {
        "generated_at": _now(),
        "snapshot": {
            "sha256": snapshot_sha256,
            "basis": snap["basis"],
            "period": snap["period"],
            "end_date": snap["end_date"],
            "filters": snap["filters"],
            "counts": snap["counts"],
            "price_state": snap["price_state"],
            "regime": {
                k: snap["regime"].get(k) for k in ("label", "asof", "streak_days")
            },
            "top": [
                {
                    "rank": r["rank"],
                    "ticker": r["ticker"],
                    "name": r["name"],
                    "return_pct": r["basis_return"]["value"],
                    "classification": r["classification"],
                }
                for r in frozen
            ],
        },
        # 사본으로 요약을 만들지 못하면 '다름'이 아니라 비교 못 함(None)
        "copy_top_matches_snapshot": (
            q5["one_month"]["top"] == [r["ticker"] for r in frozen]
            if q5["one_month"]["status"] == "ok"
            else None
        ),
        "collect": {
            k: collected[k]
            for k in (
                "started_at",
                "finished_at",
                "request_asof",
                "external_calls",
                "call_limit",
                "batches",
            )
        },
        "official": ometa,
        "dictionary": dmeta,
        "comparison_one": {
            "groups": snap["groups"]["top"],
            "overview": snap["overview"]["top"],
        },
        "comparison_one_scope": C.group_scope(snap["groups"]["top"]),
        "comparison_two": c2,
        "comparison_two_scope": C.group_scope(c2["groups"]),
        "comparison_three": c3,
        "comparison_three_scope": C.comparison_three_scope(frozen, latest, etf),
        "lead_case": C.lead_case(frozen, latest, etf),
        "evidence": evidence,
        "evidence_scope": C.sector_evidence_scope(
            latest_all, official, dictionary, etf_names
        ),
        "coverage": cov,
        "kind_labels": C.KIND_LABEL,
        "families": C.SAMPLE_FAMILIES,
        "q5": q5,
    }
    (run_dir / "report.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    html_out.write_text(render_html(doc), encoding="utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="POC6-30 섹터요약 보강 대조")
    ap.add_argument("step", choices=["collect", "report"])
    ap.add_argument("--run-dir", required=True, type=Path)
    a = ap.parse_args(argv)
    if a.step == "collect":
        d = collect(a.run_dir, research_root=RESEARCH_ROOT)
        print(
            json.dumps(
                {"external_calls": d["external_calls"], "batches": d["batches"]},
                ensure_ascii=False,
            )
        )
    else:
        d = report(a.run_dir)
        print(
            json.dumps(
                {"repeated": len(d["comparison_three"]), "html": str(HTML_OUT)},
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
