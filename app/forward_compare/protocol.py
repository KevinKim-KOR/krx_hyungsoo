"""POC6-06 — 고정 상수 · 경로 · 파일 쓰기(설계 V1 · PLAN 판정 2026-10-22).

모든 산출물은 `state/ml/research/poc6_06/` 아래에 추가만 한다(같은 이름 덮어쓰기 없음 · 임시 파일 → os.link).
시각은 05 증거와 같은 UTC 마이크로초 `…Z` 형식(`app.ml_evidence.store.iso` · `parse_iso`)만 쓴다.
"""

from __future__ import annotations

import contextlib
import functools
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

from app.ml_evidence import forward_artifacts as FA
from app.ml_evidence import store
from app.three_push_runtime import ledger_outcome

PROTOCOL_ID = FA.PROTOCOL_ID
COHORT_ID = "cohort_v1"
ROOT = Path(FA.ROOT_REL)
SCHEMAS = FA.SCHEMAS  # 파일 유형 → schema(05 받기 검사와 같은 표)
LOCK_NAME = ".run.lock"  # 연구 폴더 단일 실행 잠금(점 파일 = 보관 대상 아님)
EVIDENCE_ROOT = store.EVIDENCE_ROOT
# "15:30" KST — 목표 첫 종가 확정 경계(설계 §6 · 기존 상수 그대로)
CLOSE_CUTOFF = ledger_outcome.CLOSE_CUTOFF
KST = timezone(timedelta(hours=9))
METHODS = ("MEDIAN", "RIDGE", "HGB", "MLP_CPU")
MIN_DAYS = 365  # 후보 조건(장기 자료 가능성 확인일 뿐)
MIN_EXAMPLES = 252  # initial_trainable
COHORT_SIZE = 24
# PLAN §1 표(2026-10-22 실측 · 판정 §0 에서 해시 · 순서 재계산 일치) — 다시 뽑지 않는다.
# fmt: off
EXPECTED_COHORT = (
    "364960", "381180", "445690", "122090", "271050", "458030",
    "447620", "354500", "114100", "211900", "108450", "461950",
    "203780", "291890", "476260", "414780", "453660", "282000",
    "300640", "488720", "0015K0", "130730", "433220", "494670",
)
# fmt: on
# 판정 §3-1 사전 고정 보조 묶음(유형 판정이 아니라 관찰한 이름의 분리 관측)
AUX_GROUPS = {
    "bond_cash_mixed_5": ("458030", "130730", "114100", "488720", "447620"),
    "inverse_2": ("271050", "282000"),
}
SOURCE = (
    "FinanceDataReader"  # 06 허용 출처(FDR → 네이버 fchart · change 일관성 검사 대상)
)


def cohort_rank_key(ticker: str) -> tuple[str, str]:
    """선정 규칙: SHA-256("poc6-06-v1:" + ticker) 오름차순 · 동률 ticker 순(원래 6자 식별자 그대로)."""
    return (store.sha256_bytes(f"{PROTOCOL_ID}:{ticker}".encode("utf-8")), ticker)


def aux_groups(cohort: list[str]) -> dict[str, list[str]]:
    used = {t for g in AUX_GROUPS.values() for t in g}
    out = {k: [t for t in v if t in cohort] for k, v in AUX_GROUPS.items()}
    out["rest_17"] = [t for t in cohort if t not in used]
    return out


def kst_day(dt: datetime) -> str:
    return dt.astimezone(KST).date().isoformat()


def new_id(now: datetime) -> str:
    return f"{now.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}_{uuid.uuid4().hex[:8]}"


def doc(file_type: str, /, **body: Any) -> dict[str, Any]:
    """산출물 JSON 머리(schema · protocol_id) + 본문(본문에 kind 칸이 있어도 됨)."""
    return {"schema": SCHEMAS[file_type], "protocol_id": PROTOCOL_ID, **body}


def dumps(obj: Any, *, compact: bool = False) -> bytes:
    """정렬 키 JSON. 큰 행 목록(초기 가격 · 예제)은 compact = 공백 없는 한 줄."""
    if compact:
        text = json.dumps(
            obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    else:
        text = json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=1)
    return (text + "\n").encode("utf-8")


def write_once(
    path: Path, data: bytes, before_link: Optional[Callable[[], bool]] = None
) -> Optional[str]:
    """같은 이름이 있으면 실패(덮어쓰기 없음). 돌려주는 값 = sha256.

    `before_link` 를 주면 임시 파일 쓰기 · fsync 가 모두 끝난 뒤 · 공개(os.link) 바로 앞에서 부른다.
    False 면 공개하지 않고 None(느린 쓰기 동안 마감이 지난 경우 · F1).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.{uuid.uuid4().hex[:8]}.tmp"
    try:
        with open(tmp, "xb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if before_link is not None and not before_link():
            return None
        os.link(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    return store.sha256_bytes(data)


class Busy(Exception):
    """같은 연구 폴더에서 다른 실행이 진행 중 — 아무것도 쓰지 않았다."""


class ClockBehind(Exception):
    """지금 시각이 연구 폴더에 이미 남은 기록 시각보다 이르다(시계 역행) — 아무것도 쓰지 않았다."""


@contextlib.contextmanager
def run_lock(root: Path) -> Iterator[bool]:
    """연구 폴더 단일 실행 잠금(기다리지 않음). 잡으면 True · 다른 실행 중이면 False(검증자 r1 F2)."""
    with store.file_lock(Path(root) / LOCK_NAME, wait_s=0.0) as ok:
        yield ok


def exclusive(fn: Callable) -> Callable:
    """첫 인자 = 연구 폴더. 그 폴더에 쓰는 명령(run · 초기 조회 · 표본 확정 · 보관 등록)을 한 번에 하나만."""

    @functools.wraps(fn)
    def wrapped(root: Path, *args: Any, **kwargs: Any) -> Any:
        with run_lock(root) as ok:
            if not ok:
                raise Busy("같은 연구 폴더에서 다른 실행이 진행 중")
            return fn(root, *args, **kwargs)

    return wrapped


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rel_in(root: Path, path: Path) -> str:
    """연구 폴더 기준 상대 경로(POSIX) — 기록 안의 참조."""
    return Path(path).relative_to(root).as_posix()
