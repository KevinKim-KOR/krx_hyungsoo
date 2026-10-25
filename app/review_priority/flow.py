"""POC6-09 — 고정 08 입력(같은 바이트 · 해시) · 행 연결 · run(계산 전 protocol · 실패 기록 · 1회) · verify · 보고서.

```text
입력   08 정정 실행 6파일 — 한 번 읽은 바이트로 sha256 대조 → 그 바이트를 엄격 JSON 읽기(비유한 수 거절)로 파싱
연결   예측 (fold, ticker, date) ↔ 예제 (ticker, date) 일대일 · 예제 i ∈ folds[fold] · truth == y
       · P 순서 고정(둘째 = chg20)
       어긋나면 행 삭제 · 대체 없이 CHECK_REQUIRED · 개수(PLAN §2)도 계산 전에 대조
run    잠금 · 재실행 사유 → 입력 사전 대조 → 실행 ID → (여기부터 실패 기록) protocol → 계산 → rows · report · run.json
verify 고정 입력에서 다시 계산해 rows · report.json 전체 · report.md 대조 + protocol 조건 = 코드 계약 · 실행 ID · 상태 일치
```
"""

from __future__ import annotations

import contextlib
import math
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from app.feature_gain import protocol as FP
from app.ml_evidence import store
from app.review_priority import core as C
from app.review_priority import report as RP

PROTOCOL_ID = "poc6-09-v1"
ROOT = Path("state/ml/research/poc6_09")
LOCK_NAME = ".run.lock"
SRC = Path("state/ml/research/poc6_08/20261025T093029Z_9452f7e4")
RUN = SRC / "runs" / "20261025T093038Z_997ed8d7"
# PLAN §1 고정 입력(전체 sha256 · 2026-10-25 실측)
SPEC: dict[str, tuple[Path, str]] = {
    "protocol": (
        SRC / "protocol.json",
        "3eeba9144fb71d91141700c6bdcc5b861f1146cae9ce2cdb5934df644b097889",
    ),
    "run": (
        RUN / "run.json",
        "bce2e379da5693fe33f3bb6f97e2b0f79429eb1cf06519ce3c60207c329e5cb2",
    ),
    "examples": (
        RUN / "examples.json",
        "26ab93be550ae2d86ef2e1ff03685d5ca7d2ad43ce0177a5dc5f5d15078801bf",
    ),
    "predictions": (
        RUN / "predictions.json",
        "a109aa0205452f34a21226d5dac286a43524ca9cbd6e4948803f7ef985f99a2d",
    ),
    "report_json": (
        RUN / "report.json",
        "9dc02222034531ee6ebbdb3026975eac52b658ac652911d5532d8db495ffbb9e",
    ),
    "report_md": (
        RUN / "report.md",
        "95d47f664209dc749f0814e55977666552302772bcf67c64bd50a968783acafc",
    ),
}
P_ORDER = ["chg5", "chg20", "chg60", "vol20", "from_high60"]  # 20일 변화 = 둘째
CONFIG_OF = {"MEDIAN_P": "MEDIAN_P", "RIDGE_P": "RIDGE_P", "HGB_P": "HGB_P"}
SCOPES = ("G_ALL", "G_REVIEW")
# PLAN §2 개수 표(성과 열람 전 조사) — 계산 전에 대조
EXPECTED: dict[str, Any] = {
    "rows": 3969,
    "dates": 189,
    "folds": [
        ["2025-12-08", "2026-03-13", 63],
        ["2026-03-16", "2026-06-16", 63],
        ["2026-06-17", "2026-09-15", 63],
    ],
    "n_per_date": {"G_ALL": 21, "G_REVIEW": 15},
    "scope_rows": {"G_ALL": 3969, "G_REVIEW": 2835},
}
CODE_FILES = (
    "app/review_priority/__init__.py",
    "app/review_priority/core.py",
    "app/review_priority/flow.py",
    "app/review_priority/report.py",
    "scripts/run_review_priority.py",
    "app/feature_gain/protocol.py",
    "app/forward_compare/protocol.py",
    "app/ml_evidence/store.py",
)


class CheckRequired(Exception):
    """입력 해시 · 형식 · 연결 · 개수가 고정과 다름(계산 전 · 새 실행 폴더 없음)."""


class Busy(Exception):
    """같은 연구 폴더에서 다른 실행 중."""


class Refused(Exception):
    """이미 실행이 있음 — 코드 결함 정정 · 중단 뒤 재실행만 사유와 함께."""


@contextlib.contextmanager
def run_lock(root: Path) -> Iterator[None]:
    Path(root).mkdir(parents=True, exist_ok=True)
    with store.file_lock(Path(root) / LOCK_NAME, wait_s=0.0) as ok:
        if not ok:
            raise Busy("같은 연구 폴더에서 다른 실행이 진행 중")
        yield


def code_hashes(repo: Path) -> dict[str, str]:
    return {
        rel: store.sha256_bytes((Path(repo) / rel).read_bytes()) for rel in CODE_FILES
    }


# ── 입력 · 연결 ────────────────────────────────────────────────────────────────


def read_inputs(repo: Path, spec=None) -> dict[str, Any]:
    """파일마다 한 번 읽은 바이트로 해시 대조 → 같은 바이트를 엄격 읽기(판정 §3-1)."""
    spec = SPEC if spec is None else spec
    out: dict[str, Any] = {"_sha256": {}}
    for name, (rel, sha) in spec.items():
        try:
            data = (Path(repo) / rel).read_bytes()
        except OSError as e:
            raise CheckRequired(f"{name} 읽기 실패: {type(e).__name__}") from e
        got = store.sha256_bytes(data)
        if got != sha:
            raise CheckRequired(f"{name} 해시가 고정 값과 다름")
        out["_sha256"][name] = got
        try:
            text = data.decode("utf-8")
            out[name] = text if name == "report_md" else FP.loads(text)
        except (UnicodeDecodeError, ValueError) as e:
            raise CheckRequired(f"{name} 형식 손상(비유한 수 포함): {e}"[:200]) from e
    return out


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _iso(s: Any) -> bool:
    try:
        return isinstance(s, str) and date.fromisoformat(s).isoformat() == s
    except ValueError:
        return False


def build_table(inp: dict[str, Any], expected=None) -> dict[str, Any]:
    """시험 행 표(범위 · 날짜 · 종목 · 점수 4 · 실제 D20) — 연결 · 개수가 다르면 CheckRequired."""
    expected = EXPECTED if expected is None else expected
    try:
        return _build(inp, expected)
    except CheckRequired:
        raise
    except (KeyError, TypeError, ValueError, IndexError, AttributeError) as e:
        raise CheckRequired(f"입력 형식 손상: {type(e).__name__}: {e}"[:200]) from e


def _build(inp, expected) -> dict[str, Any]:
    lk, meta, ex, preds = (
        inp["protocol"],
        inp["run"],
        inp["examples"],
        inp["predictions"],
    )
    if lk["recipe"]["features"]["P"] != P_ORDER:
        raise CheckRequired("08 P 열 순서가 고정과 다름(20일 변화 = 둘째 chg20)")
    if meta["lock_id"] != lk["lock_id"] or meta["status"] != "OK":
        raise CheckRequired("08 실행 기록이 잠금 · 정상 상태와 다름")
    if meta["failed_configs"] or meta["restore_ok"] is not True:
        raise CheckRequired("08 실행에 실패 구성 · 복원 불일치가 있음")
    eligible, review = list(lk["plan"]["eligible"]), list(lk["plan"]["review"])
    want_n = expected["n_per_date"]
    if (
        not set(review) <= set(eligible)
        or len(set(eligible)) != len(eligible)
        or len(eligible) != want_n["G_ALL"]
        or len(set(review)) != len(review)
        or len(review) != want_n["G_REVIEW"]
    ):
        raise CheckRequired("08 적격 · G_REVIEW 목록이 고정 범위와 다름")
    folds = [set(f) for f in ex["folds"]]
    by_key: dict[tuple[str, str], dict] = {}
    for r in ex["rows"]:
        key = (r["ticker"], r["date"])
        if key in by_key:
            raise CheckRequired(f"예제 키 중복: {key}")
        by_key[key] = r
    rows, seen = [], set()
    for p in preds:
        key = (p["ticker"], p["date"])
        fold = p["fold"]
        if key in seen:
            raise CheckRequired(f"예측 키 중복: {key}")
        seen.add(key)
        e = by_key.get(key)
        if e is None:
            raise CheckRequired(f"예측 행에 맞는 예제 없음: {key}")
        if fold not in (0, 1, 2) or isinstance(fold, bool) or e["i"] not in folds[fold]:
            raise CheckRequired(f"예측 구간과 예제 시험 위치가 다름: {key}")
        if not _iso(p["date"]) or p["ticker"] not in eligible:
            raise CheckRequired(f"날짜 형식 · 종목이 고정과 다름: {key}")
        truth, pv = p["truth"], e["p"]
        if not _num(truth) or truth != e["y"] or not -1.0 <= truth <= 0.0:
            raise CheckRequired(f"실제 D20 이 예제 y 와 다르거나 범위 밖: {key}")
        if len(pv) != len(P_ORDER) or not _num(pv[1]):
            raise CheckRequired(f"예제 P 열 형식이 다름: {key}")
        scores = {"PRICE20_RULE": pv[1]}
        for method, cfg in CONFIG_OF.items():
            v = p["preds"][cfg]
            if not _num(v) or not -1.0 <= v <= 0.0:
                raise CheckRequired(f"{cfg} 제한 예측이 [-1, 0] 유한 수가 아님: {key}")
            scores[method] = v
        rows.append(
            {
                "fold": fold,
                "ticker": p["ticker"],
                "date": p["date"],
                "truth": truth,
                "scores": scores,
            }
        )
    rows.sort(key=lambda r: (r["date"], r["ticker"]))
    _check_counts(rows, review, expected)
    return {"rows": rows, "eligible": eligible, "review": review}


def _check_counts(rows, review, expected) -> None:
    rev = set(review)
    dates = sorted({r["date"] for r in rows})
    got_folds = []
    for k in range(C.FOLDS):
        ds = sorted({r["date"] for r in rows if r["fold"] == k})
        got_folds.append([ds[0], ds[-1], len(ds)] if ds else [None, None, 0])
    per = {"G_ALL": {}, "G_REVIEW": {}}
    for r in rows:
        per["G_ALL"][r["date"]] = per["G_ALL"].get(r["date"], 0) + 1
        if r["ticker"] in rev:
            per["G_REVIEW"][r["date"]] = per["G_REVIEW"].get(r["date"], 0) + 1
    got = {
        "rows": len(rows),
        "dates": len(dates),
        "folds": got_folds,
        "n_per_date": {s: sorted(set(v.values())) for s, v in per.items()},
        "scope_rows": {s: sum(v.values()) for s, v in per.items()},
    }
    want = {
        **expected,
        "n_per_date": {s: [n] for s, n in expected["n_per_date"].items()},
    }
    diffs = [f"{k}: PLAN {want[k]} ≠ {got[k]}" for k in want if got.get(k) != want[k]]
    if diffs or len(per["G_REVIEW"]) != len(dates):
        raise CheckRequired(
            "PLAN 개수와 다름: " + " · ".join(diffs or ["G_REVIEW 날짜"])
        )


# ── 계산 · 보고 ────────────────────────────────────────────────────────────────


def compute(table: dict[str, Any]) -> dict[str, Any]:
    """두 범위 · 날짜마다 독립 순위(G_REVIEW 를 G_ALL 선택에서 거르지 않음) → rows · 요약 · 판정."""
    out_rows: dict[str, list] = {}
    scopes: dict[str, Any] = {}
    for scope in SCOPES:
        members = set(table["eligible"] if scope == "G_ALL" else table["review"])
        by_date: dict[str, list] = {}
        for r in table["rows"]:
            if r["ticker"] in members:
                by_date.setdefault(r["date"], []).append(r)
        days, rows = [], []
        for d, rs in sorted(by_date.items()):
            dd = C.day(rs)
            days.append({"date": d, "fold": rs[0]["fold"], "day": dd})
            for r in rs:
                w = {m: dd["methods"][m]["weights"][r["ticker"]] for m in C.METHODS}
                rows.append({**r, "y": dd["y"][r["ticker"]], "w": w})
        summ, samp = C.summarize(days), C.sample(days)
        out_rows[scope] = C.to_json(rows)
        scopes[scope] = C.to_json(
            {
                "members": len(members),
                "sample": samp,
                "summary": summ,
                "per_ticker": C.per_ticker(days),
                "judge": {m: C.judge(summ, samp, m) for m in C.MODELS},
            }
        )
    return {"rows": out_rows, "scopes": scopes}


# ── run · verify ───────────────────────────────────────────────────────────────

NOTE = "08 목표 · 오차 · 큰 하락 요약은 이미 봄 — 사전 확증 실험 아님(설계 §7)"
ID_PREFIX = 22  # YYYYmmddTHHMMSSffffffZ — 이름 순서 = 시각 순서


def new_id(now: datetime) -> str:
    return f"{now.astimezone(timezone.utc):%Y%m%dT%H%M%S%fZ}_{uuid.uuid4().hex[:8]}"


def _runs(root: Path) -> list[Path]:
    return (
        sorted(d for d in Path(root).iterdir() if d.is_dir()) if root.exists() else []
    )


def _inputs(spec, hashes) -> dict[str, Any]:
    return {
        n: {"path": p.as_posix(), "sha256": hashes[n]}
        for n, (p, _) in (SPEC if spec is None else spec).items()
    }


def _protocol(run_id, created_at, inputs, table, expected, code, corrects, reason):
    """protocol 본문 — run 이 쓰고 verify 가 같은 함수로 다시 만들어 통째로 대조(검토 M1)."""
    return {
        "schema": "poc6_09_protocol_v1",
        "protocol_id": PROTOCOL_ID,
        "run_id": run_id,
        "created_at": created_at,
        "inputs": inputs,
        "conditions": C.conditions(),
        "scopes": {"G_ALL": table["eligible"], "G_REVIEW": table["review"]},
        "expected": EXPECTED if expected is None else expected,
        "code": code,
        "corrects": corrects,
        "correction_reason": reason,
        "note": NOTE,
    }


def run(
    root,
    repo,
    clock,
    correction_reason=None,
    base_commit=None,
    spec=None,
    expected=None,
    inputs_root=None,
) -> dict[str, Any]:
    """공식 계산 1회(판정 §3-2) — 사전 대조 실패는 새 실행 폴더 없음 · 실행 ID 뒤 실패는 run.json FAILED.

    `repo` = 실행 코드 해시를 읽는 저장소 · `inputs_root` = 고정 입력 경로의 기준(없으면 `repo`).
    """
    root, repo = Path(root), Path(repo)
    base = Path(inputs_root) if inputs_root is not None else repo
    with run_lock(root):
        prior = [d.name for d in _runs(root)]
        if prior and not correction_reason:
            raise Refused(
                "이미 실행이 있음 — 코드 결함 정정 · 중단 뒤 재실행만 사유와 함께"
            )
        inp = read_inputs(base, spec)
        table = build_table(inp, expected)
        code = {"base_commit": base_commit, "sha256": code_hashes(repo)}
        started = clock()
        run_id = new_id(started)
        if prior and run_id[:ID_PREFIX] <= max(p[:ID_PREFIX] for p in prior):
            raise CheckRequired(
                "시계가 이전 실행보다 이르거나 같음 — 실행 순서를 보장할 수 없음"
            )
        rdir = root / run_id
        meta: dict[str, Any] = {
            "schema": "poc6_09_run_v1",
            "protocol_id": PROTOCOL_ID,
            "run_id": run_id,
            "started_at": store.iso(started),
            "corrects": prior,
            "correction_reason": correction_reason,
        }
        try:
            meta["changed_code"] = _changed_code(root, prior, code["sha256"])
            protocol = _protocol(
                run_id,
                meta["started_at"],
                _inputs(spec, inp["_sha256"]),
                table,
                expected,
                code,
                prior,
                correction_reason,
            )
            # protocol 을 계산보다 먼저 남긴다(판정 §3-2).
            FP.write_once(rdir / "protocol.json", FP.dumps(protocol))
            result = compute(table)
            FP.write_once(rdir / "rows.json", FP.dumps(result["rows"], compact=True))
            rep = RP.report(
                run_id, protocol["inputs"], protocol["conditions"], result, PROTOCOL_ID
            )
            data = FP.dumps(rep)
            FP.write_once(rdir / "report.json", data)
            FP.write_once(rdir / "report.md", RP.markdown(FP.loads(data)).encode())
            meta.update(status="OK", finished_at=store.iso(clock()))
            FP.write_once(rdir / "run.json", FP.dumps(meta))
            return {"run_dir": rdir, "meta": meta, "report": rep}
        except BaseException as e:
            _record_failure(rdir, meta, e, clock)
            raise


def _changed_code(root: Path, prior: list[str], code: dict[str, str]) -> Any:
    """이전 시도 중 protocol 이 읽히는 가장 최근 것과 비교한 바뀐 코드 파일(검토 L3)."""
    if not prior:
        return None
    for name in reversed(prior):
        try:
            prev = FP.read_json(root / name / "protocol.json")["code"]["sha256"]
            if not isinstance(prev, dict):
                continue
            return {
                "previous_run": name,
                "files": sorted(f for f in code if code[f] != prev.get(f)),
            }
        except (OSError, ValueError, KeyError, TypeError, RecursionError):
            continue
    return {"previous_protocol": "없음 · 손상", "files": sorted(code)}


def _record_failure(rdir: Path, meta: dict[str, Any], e: BaseException, clock) -> None:
    if (rdir / "run.json").exists():
        return
    try:
        finished = store.iso(clock())
    except Exception:  # noqa: BLE001 — 시계 실패가 실패 기록을 막지 않게
        finished = None
    meta.update(
        status="FAILED", reason=f"{type(e).__name__}: {e}"[:300], finished_at=finished
    )
    try:
        FP.write_once(rdir / "run.json", FP.dumps(meta))
    except Exception as w:  # noqa: BLE001 — 원래 예외를 올리되 기록 실패를 붙인다
        e.add_note(f"실패 기록(run.json)도 쓰지 못함: {type(w).__name__}: {w}")


READ_ERRORS = (OSError, ValueError, RecursionError)


def verify(
    root, repo, run_id: Optional[str] = None, spec=None, expected=None
) -> dict[str, Any]:
    """판정 §3-3 — 같은 실행(protocol · run.json) · 고정 계약 · 고정 입력에서 다시 계산한 결과 대조.

    `repo` = 고정 입력 경로의 기준(코드는 다시 해시하지 않음 · 학습 · 모델 복원 없음).
    """
    root, base = Path(root), Path(repo)
    runs = _runs(root)
    rdir = (
        next((d for d in runs if d.name == run_id), None)
        if run_id
        else (runs[-1] if runs else None)
    )
    if rdir is None:
        return {"status": "CHECK_REQUIRED", "problems": ["실행 없음"]}

    def rd(name: str) -> Any:
        return FP.loads((rdir / name).read_text(encoding="utf-8"))

    try:
        meta = rd("run.json")
    except READ_ERRORS as e:
        return _vr("CHECK_REQUIRED", rdir, None, [f"run.json 없음 · 손상: {e}"[:200]])
    status = meta.get("status") if isinstance(meta, dict) else None
    if status != "OK":  # 실패 · 미완료는 protocol 이 없어도 실패로(검토 L5)
        return _vr("RUN_FAILED", rdir, status, [f"정상 완료 실행이 아님: {status}"])
    got: dict[str, Any] = {}
    for name in ("protocol.json", "rows.json", "report.json"):
        try:
            got[name] = rd(name)
        except READ_ERRORS as e:
            return _vr(
                "CHECK_REQUIRED", rdir, status, [f"{name} 없음 · 손상: {e}"[:200]]
            )
    try:
        problems = _compare(root, meta, got, rdir, base, spec, expected)
    except CheckRequired as e:
        return _vr(
            "CHECK_REQUIRED", rdir, status, [f"고정 입력 다시 읽기 실패: {e}"[:200]]
        )
    except (KeyError, TypeError, AttributeError, ValueError, IndexError) as e:
        problems = [f"저장 결과 형식 손상(대조 불가): {type(e).__name__}: {e}"[:200]]
    return _vr("OK" if not problems else "MISMATCH", rdir, status, problems)


def _hex(v: Any, n: int) -> bool:
    return (
        isinstance(v, str) and len(v) == n and all(c in "0123456789abcdef" for c in v)
    )


def _compare(root, meta, got, rdir, base, spec, expected) -> list[str]:
    """protocol · run.json 을 고정 계약 · 폴더 목록에서 다시 만들어 통째로 대조 + 결과 전체 재계산."""
    problems: list[str] = []
    proto = got["protocol.json"]
    spec_now = SPEC if spec is None else spec
    inputs = _inputs(spec, {n: s for n, (_, s) in spec_now.items()})
    corrects = [
        d.name for d in _runs(root) if d.name < rdir.name
    ]  # 이 실행 전의 시도 전부
    code = proto["code"]
    if not (
        isinstance(code, dict)
        and set(code) == {"base_commit", "sha256"}
        and (code["base_commit"] is None or _hex(code["base_commit"], 40))
        and isinstance(code["sha256"], dict)
        and set(code["sha256"]) == set(CODE_FILES)
        and all(_hex(v, 64) for v in code["sha256"].values())
    ):
        problems.append("protocol 코드 근거 형식이 다름")
    table = build_table(read_inputs(base, spec), expected)
    want_proto = _protocol(
        rdir.name,
        meta["started_at"],
        inputs,
        table,
        expected,
        code,
        corrects,
        meta["correction_reason"],
    )
    if store.canonical(proto) != store.canonical(want_proto):
        problems.append(
            "protocol ≠ 고정 계약(입력 해시 · 조건 · 범위 · 개수 표 · 실행 ID · 정정 관계)"
        )
    want_meta = {
        "schema": "poc6_09_run_v1",
        "protocol_id": PROTOCOL_ID,
        "run_id": rdir.name,
        "started_at": proto["created_at"],
        "corrects": corrects,
        "correction_reason": proto["correction_reason"],
        "changed_code": _changed_code(root, corrects, code["sha256"]),
        "status": "OK",
        "finished_at": meta["finished_at"],
    }
    if store.canonical(meta) != store.canonical(want_meta) or not (
        store.parse_iso(meta["finished_at"]) >= store.parse_iso(meta["started_at"])
    ):
        problems.append(
            "run.json ≠ 같은 실행의 기록(실행 ID · 정정 관계 · 바뀐 코드 · 상태)"
        )
    result = compute(table)
    if store.canonical(result["rows"]) != store.canonical(got["rows.json"]):
        problems.append("rows.json ≠ 고정 입력에서 다시 계산한 행 · 선택 비중")
    # 보고서는 저장 protocol 이 아니라 고정 계약(실행 ID · 입력 · 조건)으로 다시 만든다.
    again = RP.report(rdir.name, inputs, C.conditions(), result, PROTOCOL_ID)
    if store.canonical(again) != store.canonical(got["report.json"]):
        problems.append("report.json ≠ 고정 계약 · 입력에서 다시 계산한 보고서")
    try:
        md = (rdir / "report.md").read_text(encoding="utf-8")
    except OSError:
        md = None
    if md is None or md != RP.markdown(got["report.json"]):
        problems.append("report.md ≠ report.json 에서 다시 만든 글")
    return problems


def _vr(status, rdir, run_status, problems) -> dict[str, Any]:
    return {
        "status": status,
        "run_id": rdir.name,
        "run_status": run_status,
        "problems": problems,
    }
