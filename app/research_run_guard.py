"""연구 러너 공통 실행 규율 — POC4-03 전용 (설계자 확정 Q12 · 02A·02B·conftest 사본은 그대로 둔다).

- 라이브 5경로 지문(파일 4개 sha256 + `state/runs` 이름 목록) · 배타 쓰기(`x`) · 실행 폴더 규칙 ·
  `guard_failed.json` 표식 · peak RSS · 자원 상한(perf_counter 4시간 · RSS 10×10^9 바이트) · 결정성 compare 규칙.
- 02A 러너(`scripts/run_poc4_02a_pit_bias.py`)와 같은 규칙을 그대로 옮겼다 — 02A 파일은 수정하지 않는다.
"""

from __future__ import annotations

import json
import os
import resource
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from app.ml_baseline_snapshot import (
    SnapshotIntegrityError,
    file_sha256,
    new_run_dir,
)
from app.ml_score_validity_report import canonical_sha256

# POC4-01 사고에서 전체 회귀가 실제로 쓴 라이브 경로 5곳 (tests/conftest.py 와 같은 목록).
LIVE_WATCH_FILES = (
    "state/market/market_data.sqlite",
    "state/market/nav_discount_refresh_latest.json",
    "logs/oci_market_data_batch.log",
    "logs/three_push_runtime_cron.log",
)
LIVE_WATCH_DIRS = ("state/runs",)
LEGACY_ROOT_REL = Path("state/ml/validity")
GUARD_FAILED = "guard_failed.json"
RUN_MANIFEST = "run_manifest.json"
RESULT = "result.json"
RUN_META = "run_meta.json"
MAX_SECONDS = 4 * 3600
MAX_RSS_BYTES = 10 * 10**9


class RunnerError(RuntimeError):
    """실행 규율 위반 — 재개 지문 불일치 · 라이브 경로 변경 · 완료된 폴더 재개 등."""


class ResourceLimitError(RunnerError):
    """자원 상한 초과 (perf_counter 경과 · peak RSS) — INVALID_STOP(RESOURCE_LIMIT)."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_new(path: Path, payload: dict) -> str:
    """배타 생성(`x`) — 이미 있으면 `FileExistsError`. 쓴 텍스트를 돌려준다."""
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    with open(path, "x", encoding="utf-8") as fh:
        fh.write(text)
    return text


def live_fingerprint(root: Path) -> dict:
    out: dict = {}
    for rel in LIVE_WATCH_FILES:
        path = root / rel
        out[rel] = file_sha256(path) if path.is_file() else None
    for rel in LIVE_WATCH_DIRS:
        path = root / rel
        out[rel] = sorted(os.listdir(path)) if path.is_dir() else None
    return out


def live_changes(after: dict, *befores: dict) -> list[str]:
    keys = sorted(set(after).union(*befores))
    return [k for k in keys if any(b.get(k) != after.get(k) for b in befores)]


def peak_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def is_under(path: Path, root: Path) -> bool:
    """path 가 root 이거나 그 아래인지 — resolve 비교 + 있는 조상 samefile(대소문자·별칭 경로)."""
    path, root = path.resolve(), root.resolve()
    if path == root or path.is_relative_to(root):
        return True
    if not root.exists():
        return False
    return any(a.exists() and os.path.samefile(a, root) for a in (path, *path.parents))


def check_out_dir(out_dir: Path, root: Path, extra: tuple = ()) -> None:
    """legacy 결과 폴더 · 라이브 5경로 · 추가 금지 폴더(기준 산출물 등) 아래에는 쓰지 않는다."""
    if is_under(out_dir, root / LEGACY_ROOT_REL):
        raise SnapshotIntegrityError("기존(legacy) 결과 폴더와 그 하위에는 쓰지 않는다")
    for rel in (*LIVE_WATCH_FILES, *LIVE_WATCH_DIRS):
        if is_under(out_dir, root / rel):
            raise RunnerError(f"감시 대상 라이브 경로 아래에는 쓰지 않는다: {rel}")
    for path in extra:
        if is_under(out_dir, Path(path)):
            raise RunnerError(f"기준 산출물 폴더 아래에는 쓰지 않는다: {path}")


def open_run_dir(out_dir: Path, root: Path, *, resume: bool, extra: tuple = ()) -> Path:
    """새 실행은 새 폴더만 · 재개는 manifest 가 있고 guard_failed·result 가 없는 폴더만."""
    check_out_dir(out_dir, root, extra)
    if not resume:
        out = new_run_dir(out_dir, forbidden_root=root / LEGACY_ROOT_REL)
        out.mkdir(parents=True)
        return out
    out = out_dir.resolve()
    if not (out / RUN_MANIFEST).is_file():
        raise RunnerError(f"재개할 {RUN_MANIFEST} 가 없다: {out}")
    if (out / GUARD_FAILED).exists():
        raise RunnerError(f"가드가 결과를 거부한 폴더다 — 재개하지 않는다: {out}")
    if (out / RESULT).exists():
        raise RunnerError(f"이미 끝난 실행이다 — 최종 결과는 덮어쓰지 않는다: {out}")
    return out


def mark_guard_failed(out_dir: Path, track: str, guard: str, detail) -> None:
    """가드가 결과를 거부한 폴더 표식(배타 생성) — 재개·compare 가 이 폴더를 거부한다."""
    payload = {"schema_version": "guard_failed.v1", "track": track, "guard": guard}
    write_new(out_dir / GUARD_FAILED, {**payload, "detail": detail, "at": utc_now()})


class ResourceGuard:
    """perf_counter 경과 · peak RSS 상한 — 신호일마다 `check()` (Q11 확정)."""

    def __init__(
        self, max_seconds: float = MAX_SECONDS, max_rss_bytes: int = MAX_RSS_BYTES
    ):
        self.max_seconds = max_seconds
        self.max_rss_bytes = max_rss_bytes
        self.started_perf = time.perf_counter()
        self.started_utc = utc_now()

    def elapsed(self) -> float:
        return time.perf_counter() - self.started_perf

    def check(self) -> dict:
        state = {
            "elapsed_seconds": round(self.elapsed(), 2),
            "peak_rss_bytes": peak_rss_bytes(),
            "max_seconds": self.max_seconds,
            "max_rss_bytes": self.max_rss_bytes,
            "started_utc": self.started_utc,
            "checked_utc": utc_now(),
        }
        if state["elapsed_seconds"] > self.max_seconds:
            raise ResourceLimitError(f"perf_counter 경과 상한 초과: {state}")
        if state["peak_rss_bytes"] >= self.max_rss_bytes:
            raise ResourceLimitError(f"peak RSS 상한 초과: {state}")
        return state


def compare_side(folder: Path, exclude: tuple[str, ...], schema: str) -> dict:
    """결과 canonical 재계산 · 저장값 대조 · 재개 여부 (guard_failed 폴더 · 다른 결과 형식은 거부)."""
    if (folder / GUARD_FAILED).exists():
        raise RunnerError(f"가드가 결과를 거부한 폴더는 비교하지 않는다: {folder}")
    payload = json.loads((folder / RESULT).read_text(encoding="utf-8"))
    if payload.get("schema_version") != schema:
        raise RunnerError(f"결과 형식이 다르다: {payload.get('schema_version')}")
    stored = payload.get("determinism", {}).get("canonical_sha256")
    recomputed = canonical_sha256(payload, exclude=exclude)
    meta_path = folder / RUN_META
    meta = (
        json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
    )
    return {
        "dir": str(folder),
        "stored": stored,
        "recomputed": recomputed,
        "stored_matches": stored == recomputed,
        "official": payload.get("official"),
        "arm": payload.get("arm"),
        "resumed": meta.get("resumed"),
        "progress_reused": meta.get("progress_reused"),
        "payload": payload,
    }


def determinism(first: Path, second: Path, a: dict, b: dict) -> dict:
    """결정성 확인 = 두 쪽 저장값 일치 · 재계산 동일 · 둘 다 처음부터(재개 0) · 서로 다른 폴더 · 둘 다 공식."""
    identical = (
        a["stored_matches"]
        and b["stored_matches"]
        and a["recomputed"] == b["recomputed"]
    )
    fresh = all(s["resumed"] is False and s["progress_reused"] == 0 for s in (a, b))
    eligible = fresh and not os.path.samefile(first, second)
    official = a["official"] is True and b["official"] is True
    return {
        "identical": identical,
        "both_official": official,
        "determinism_eligible": eligible,
        "determinism_confirmed": bool(identical and eligible and official),
    }
