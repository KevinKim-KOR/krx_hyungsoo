"""POC7-01 고정 입력 · 설정(recipe) · 잠금 기대값 · 파일 도구 — PLAN V1 §1 ~ §5 · 판정 2026-11-22.

```text
입력   봉인 KRX krx_etf_universe_v1(파일 · 내용 해시 고정) · 기본정보 CSV 2026-09-27(파일 해시 고정)
설정   1개월(끝 − 30일 이후 069500 첫 거래일) · 상위 30 · 문턱 0.5 · 분모 최소 30 · 비용 20 · 40bp
       본 구간 2021-01-01 ~ 2026-09-11 · 보조 2014-01-01 ~ 2020-12-31 · 13주 블록 · 2,000회 · seed 고정
판정   PLAN §4 숫자(유지 · 판정 Q4) — 결과를 보고 바꾸지 않는다
기대값 PLAN §1-4 분모(체결 가능 여부를 보기 전 수) — 다르면 CheckRequired · 결과를 보고 주를 넣거나 빼지 않는다
```
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import re
import stat
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app import krx_sealed_reader as K
from app.ml_evidence import store

PROTOCOL_ID = "poc7-01-v1"
SCHEMA = {
    "protocol": "poc7_01_protocol_v1",
    "run": "poc7_01_run_v1",
    "report": "poc7_01_report_v1",
    "verify": "poc7_01_verify_v1",
    "completed": "poc7_01_completed_v1",
    "budget_exceeded": "poc7_01_budget_exceeded_v1",
}
REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / "state" / "ml" / "research" / "poc7_01"
DB = K.DEFAULT_SEALED_DB
VERSION = K.SEALED_VERSION
FILE_SHA = "fe3022e98d861beb70ead529c7efc678f5197eb20a754af48541f221656dacf2"
CONTENT_SHA = "c1a877762b9b1f296365801030641c86bc4508f4c2643f1a6793e39119f9bb4c"
CSV_PATH = REPO / "state" / "market_meta" / "krx_etf_basic_20260927.csv"
CSV_SHA = "0f0c074240e66c6d7a3406861c287dc63b8137c7aa497e5db509fae9f8722314"
BENCH = K.BENCHMARK_CODE

LOOKBACK_DAYS = 30
TOP_N = 30
THRESHOLD = 0.5
MIN_VOTES = 30
BASE_COST, ALT_COST = 0.002, 0.004
SPANS = {"main": ("2021-01-01", "2026-09-11"), "aux": ("2014-01-01", "2020-12-31")}
SUBS = (
    ("2021-01-01", "2022-12-31"),
    ("2023-01-01", "2024-12-31"),
    ("2025-01-01", "2026-09-11"),
)
BLOCK_WEEKS, DRAWS, SEED = 13, 2000, 20261122
HOLD_GAIN_MIN = 0.002  # 0.20%p — 쓸모 기준(비용 상쇄와 별개 · 40bp 에서도 고정)
SUB_WINS_MIN = 2
HOLD_WEEKS_MIN = 26
EVAL_SHARE_MIN = 0.80
EXCLUDED_SHARE_MAX = 0.20
SHIFT_MAX = 5
TOP_EXCLUDE = 5
RELOOK_WEEKS = 26
BUDGET_S = 60 * 60
VARIANTS = (
    "MAIN",
    "OFFICIAL",
)  # MAIN = 공식 일치 + 명칭 추정 · OFFICIAL = 공식 일치만(§4 ⑦)
AVAILABILITY = "공개 일정상 D+1 08:00 · 과거 실제 수신 시각 미확인"
STATES = {"execution": "검산 대기(verify)", "adoption": "미채택(이 연구로 바뀌지 않음)"}
RUN_FILES = (
    "report.json",
    "report.md",
    "weeks.json",
)  # run.json 해시 목록에 있어야 할 파일(검증자 r1 F1)
# 성립한 실행 폴더에 있어야 하는 파일 전부(숨김 임시 파일 제외 · r3 F7 · F9)
RUN_DIR_FILES = ("completed.json", "report.json", "report.md", "run.json", "weeks.json")
FILL_NOTE = "D+1 시가는 자료를 개장 전에 이용했다고 가정한 모의 체결값"
PRICE_NOTE = (
    "봉인 KRX 기준가 연결 합성 가격지수의 모의 비교 · 분배금 미포함(가격 기준) · 실제 계좌 성과 아님 · "
    "회고 자료(독립 시험 아님) · 운영 채택 아님"
)

# PLAN §1-4 실측(2026-11-21 · 체결 가능 여부를 보기 전). 체결 가능 짝 수는 prepare 가 잠금에 새로 적는다.
EXPECTED: dict[str, dict[str, int]] = {
    "main": {
        "weeks": 297,
        "cand_weeks": 292,
        "cand_weeks_official": 292,
        "pairs_official": 5160,
        "pairs_estimated": 27,
        "unknown_rows": 270,
        "unknown_rows_delisted": 193,
        "votes_min": 134,
        "votes_official_min": 130,
        "est_cand_weeks": 23,
        "votes_official_median": 194,
        "votes_estimated_median": 1,
        "votes_estimated_max": 4,
    },
    "aux": {
        "weeks": 360,
        "cand_weeks": 354,
        "cand_weeks_official": 354,
        "pairs_official": 6103,
        "pairs_estimated": 229,
        "unknown_rows": 1379,
        "unknown_rows_delisted": 1379,
        "votes_min": 48,
        "votes_official_min": 43,
        "est_cand_weeks": 164,
        "votes_official_median": 78,
        "votes_estimated_median": 5,
        "votes_estimated_max": 11,
    },
    # PLAN §2-1 ④ · ⑦ — 봉인 판 전체에서 기본정보에 없는 지수명 213 = 추정 국내 17 · 추정 아님 108 · 미확인 88
    "classification": {
        "names_not_in_dictionary": 213,
        "ESTIMATED_DE": 17,
        "ESTIMATED_NOT": 108,
        "UNKNOWN": 88,
        "unknown_provider": 87,
        "unknown_conflict": 1,
    },
}
CODE_FILES = (
    "app/krx_sealed_reader.py",
    "app/ml_evidence/store.py",
    "app/entry_timing/__init__.py",
    "app/entry_timing/protocol.py",
    "app/entry_timing/classify.py",
    "app/entry_timing/data.py",
    "app/entry_timing/weekly.py",
    "app/entry_timing/study.py",
    "app/entry_timing/report.py",
    "app/entry_timing/flow.py",
    "app/entry_timing/verify.py",
    "app/entry_timing/verify_calc.py",
    "app/entry_timing/verify_records.py",
    "scripts/run_entry_timing.py",
    "app/ml_baseline_snapshot.py",  # 봉인 확인의 파일 해시
    "app/weekly_selection/data.py",  # verify 의 POC6 칸 대조
    "app/ml_pit_universe.py",
)
ENV_LIBS = ("numpy",)


class CheckRequired(Exception):
    """입력 · 잠금 · 분모 · 가격 관계가 고정과 다름 — 성과를 계산하지 않는다."""


class Busy(Exception):
    """같은 연구 폴더에서 다른 실행이 진행 중."""


@dataclass(frozen=True)
class Config:
    """경로 · 고정값 묶음. 시험은 tmp 경로와 자기 기대값을 넣는다(라이브 DB 를 열지 않는다)."""

    db: Path = DB
    version: str = VERSION
    file_sha: Optional[str] = FILE_SHA
    content_sha: Optional[str] = CONTENT_SHA
    csv_path: Path = CSV_PATH
    csv_sha: Optional[str] = CSV_SHA
    root: Path = ROOT
    repo: Path = REPO
    spans: dict = field(default_factory=lambda: dict(SPANS))
    subs: tuple = SUBS
    expected: Optional[dict] = field(default_factory=lambda: EXPECTED)
    budget_s: float = BUDGET_S
    cross_check_poc6: bool = True


def recipe(cfg: Config) -> dict[str, Any]:
    """결과 전 잠금 설정(PLAN §2 ~ §4) — 정정 잠금도 바꿀 수 없다."""
    from app.entry_timing import classify as CL

    return {
        "window": f"끝 − {LOOKBACK_DAYS}일 이후 {BENCH} 첫 거래일 ~ 신호일(운영 1개월 규칙)",
        "top_n": TOP_N,
        "name_filter": "그날 이름에 인버스 · 레버리지 · 2X · 2배 · 합성 · 선물(운영 규칙)",
        "classification": CL.rule_text(),
        "breadth": {
            "votes": "국내 주식형 · 이름 제외 통과 · 같은 1개월 · 지수명에 '선물' 없음 · 공식 지수명 하나 = 한 표",
            "representative": "그 지수 ETF 들의 1개월 연결 종가 수익률 중앙값",
            "up": "대표 변화 > 0",
            "threshold": THRESHOLD,
            "min_votes": MIN_VOTES,
            "decision": "B ≥ 0.5 → 즉시 · B < 0.5 → 보류 · 분모 < 30 → 즉시(규칙 없음)",
        },
        "fills": {
            "immediate": "D+1 합성 시가",
            "hold": "D'+1 합성 시가",
            "note": FILL_NOTE,
        },
        "availability": AVAILABILITY,
        "costs": [BASE_COST, ALT_COST],
        "cash_return": 0.0,
        "spans": cfg.spans,
        "subs": [list(s) for s in cfg.subs],
        "bootstrap": {
            "block_weeks": BLOCK_WEEKS,
            "draws": DRAWS,
            "seed": SEED,
            "slots": "본 구간 신호 주 달력 자리 · 빠진 주는 빈 자리 · 평균 = 유효 주",
        },
        "criteria": {
            "hold_gain_min": HOLD_GAIN_MIN,
            "sub_wins_min": SUB_WINS_MIN,
            "hold_weeks_min": HOLD_WEEKS_MIN,
            "eval_share_min": EVAL_SHARE_MIN,
            "excluded_share_max": EXCLUDED_SHARE_MAX,
            "order": "D → C → A → B",
        },
        "shift_max": SHIFT_MAX,
        "top_exclude": TOP_EXCLUDE,
        "relook_weeks": RELOOK_WEEKS,
        "budget_s": cfg.budget_s,
    }


def _clean(obj: Any) -> Any:
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise CheckRequired("기록할 수 없는 수(NaN · inf)")
        return obj
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    return obj


def dumps(obj: Any) -> bytes:
    text = json.dumps(
        _clean(obj), ensure_ascii=False, sort_keys=True, indent=1, allow_nan=False
    )
    return (text + "\n").encode("utf-8")


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _put(fh: Any, data: bytes) -> None:
    """임시 파일에 쓰기(시험이 쓰는 도중 중단을 흉내 내는 자리)."""
    fh.write(data)


def _link(src: Path, dst: Path) -> None:
    """이름 붙이기(시험이 늦어짐 · 실패를 흉내 내는 자리)."""
    os.link(src, dst)


def _unlink(path: Path) -> None:
    """임시 이름 지우기(시험이 실패를 흉내 내는 자리)."""
    os.unlink(path)


def real_root(root: Path) -> Path:
    """연구 폴더 = 심볼릭 링크 · '..' 없는 실제 경로(자신 · 상위 모두 · 검증자 r5 F12) · 없으면 만든다.

    '..' 를 글자로 지우지 않는다(링크 뒤 '..' 는 운영체제가 링크 너머에서 푼다). 확인은 만들기 전에
    (링크된 상위 밑에 폴더를 만들지 않게). 링크 고리도 거부. 어긋나면 아무것도 쓰지 않고 거부.
    돌려준 경로 하나로 모든 읽기 · 쓰기를 한다(flow.run_lock 이 돌려준다).
    """
    a = Path(root).absolute()
    try:
        real = a.resolve()
    except (OSError, RuntimeError) as e:  # 링크 고리 등
        raise CheckRequired(f"연구 폴더 경로를 풀 수 없음(링크 고리 등): {a}") from e
    if real != a:  # 링크 · '..' 가 있으면 실제 경로와 글자가 다르다
        raise CheckRequired(
            f"연구 폴더 경로에 심볼릭 링크 · '..' 가 있음 — 실제 경로로 지정: {a}"
        )
    a.mkdir(parents=True, exist_ok=True)
    return a


def inside(root: Path, d: Path, make: bool = False) -> Path:
    """연구 폴더 아래 실제 폴더만(검증자 r5 F12) — 모든 쓰기 직전 · 잠금 · runs · verify 를 읽기 전에 부른다.

    연구 폴더를 다시 확인한 뒤 그 아래 단계마다 심볼릭 링크가 아닌 실제 폴더인지 본다(링크를 따라가지 않음).
    make = 없는 단계를 한 단계씩 만든다(만든 뒤 같은 확인). 어긋나면 아무것도 쓰지 않고 CheckRequired.
    """
    base = real_root(root)
    a = Path(d).absolute()
    if ".." in a.parts:
        raise CheckRequired(f"경로에 '..' 가 있음: {a}")
    try:
        rel = a.relative_to(base)
    except ValueError:
        raise CheckRequired(f"연구 폴더 밖 경로: {a}") from None
    cur = base
    for part in rel.parts:
        cur = cur / part
        if make and not os.path.lexists(cur):
            cur.mkdir()
        if cur.is_symlink() or not cur.is_dir():
            raise CheckRequired(f"연구 폴더 안 실제 폴더가 아님: {rel}")
    return a


def stage_once(root: Path, path: Path, data: bytes) -> Path:
    """1단계 — 같은 폴더 임시 파일에 다 쓰고 fsync 한다(목표 이름은 아직 없음) · 반환 임시 경로.

    쓰기 전에 폴더가 연구 폴더 아래 실제 폴더인지 본다(r5 F12). 쓰는 도중 중단 · 실패면 임시 파일을 지운다.
    목표 이름이 이미 있으면 FileExistsError(한 번만 · 끊어진 링크 이름은 하드 링크가 거부).
    """
    path = inside(root, Path(path).parent, make=True) / Path(path).name
    if os.path.lexists(path):  # 링크를 따라가지 않고 이름만 본다(r6 검토)
        raise FileExistsError(str(path))
    tmp = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    done = False
    try:
        with open(tmp, "xb") as fh:
            _put(fh, data)
            fh.flush()
            os.fsync(fh.fileno())
        done = True
        return tmp
    finally:
        if not done:
            discard(root, tmp)


def _twin_ok(d: Path, name: str, st: os.stat_result) -> bool:
    """하드 링크가 모두 같은 폴더 안 · 그 이름과 그 이름의 프로그램 임시 이름뿐(밖 파일 연결 거부 · r6 검토).

    정리 실패로 임시 이름이 남으면 같은 파일에 이름이 둘이다(r3 F8) — 그 짝만 허용한다.
    """
    if st.st_nlink == 1:
        return True
    twin = re.compile(rf"\.{re.escape(name)}\.[0-9a-f]{{32}}\.tmp")
    same = 0
    for n in os.listdir(d):
        if n == name or twin.fullmatch(n):
            o = os.lstat(d / n)
            if stat.S_ISREG(o.st_mode) and (o.st_dev, o.st_ino) == (
                st.st_dev,
                st.st_ino,
            ):
                same += 1
    return same == st.st_nlink


def regular_inside(
    root: Path, path: Path, partner: Optional[str] = None
) -> os.stat_result:
    """연구 폴더 안 보통 파일 확인(내용은 읽지 않음 · r6 F13) — 폴더 사슬 실제 · 파일 링크 아님 · 하드 링크 안.

    partner = 프로그램 임시 이름이면 그 짝(목표 이름) 기준으로 하드 링크를 센다. 아니면 CheckRequired.
    """
    path = Path(path)
    d = inside(root, path.parent)
    st = os.lstat(d / path.name)  # 없으면 FileNotFoundError · 링크를 따라가지 않음
    if not stat.S_ISREG(st.st_mode):
        raise CheckRequired(f"보통 파일이 아님(링크 · 폴더 등): {path.name}")
    if not _twin_ok(d, partner or path.name, st):
        raise CheckRequired(f"연구 폴더 밖과 이어진 하드 링크: {path.name}")
    return st


def read_inside(root: Path, path: Path) -> bytes:
    """연구 폴더 안 보통 파일만 읽는다(검증자 r6 F13) — 확인을 통과한 파일만 연다(링크 따라가지 않음).

    확인(regular_inside) 뒤 링크를 따라가지 않고 열고, 연 파일이 확인한 그 파일인지 다시 본다.
    """
    st = regular_inside(root, path)
    fd = os.open(Path(path), os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as fh:
        got = os.fstat(fh.fileno())
        if (got.st_dev, got.st_ino) != (st.st_dev, st.st_ino):
            raise CheckRequired(f"확인한 파일과 연 파일이 다름: {Path(path).name}")
        return fh.read()


def read_json_inside(root: Path, path: Path) -> Any:
    return json.loads(read_inside(root, path).decode("utf-8"))


def link_name(root: Path, tmp: Path, path: Path) -> None:
    """이름 붙이기만(정리 없음 · 링크 오류는 올림) — 실행 완료 시각을 링크 직후에 재려고(검증자 r4 F10).

    붙이기 직전에 폴더 위치를 다시 본다(r5 F12).
    """
    _link(tmp, inside(root, Path(path).parent) / Path(path).name)


RUN_ID = re.compile(r"\d{8}T\d{6}Z_[0-9a-f]{8}")  # new_id 꼴(fullmatch 로 쓴다)
# 프로그램이 만드는 임시 이름(정리 실패로 남을 수 있는 유일한 숨김 파일 · r4 F11)
# fullmatch 로만 쓴다(이름 끝 줄바꿈 같은 꼴 밖 이름 거부 · r5 검토)
TMP_NAME = re.compile(
    r"\.(completed\.json|report\.json|report\.md|run\.json|weeks\.json)\.[0-9a-f]{32}\.tmp"
)


def commit_once(root: Path, tmp: Path, path: Path) -> None:
    """2단계 — 다 쓴 임시 파일에 하드 링크로 목표 이름을 붙인다(데이터 쓰기 없음 · 있으면 FileExistsError).

    링크 · 위치 오류는 그대로 올린다. 뒤 정리(임시 이름 지우기) 오류는 결과를 바꾸지 않게 넘긴다(r3 F8).
    """
    try:
        link_name(root, tmp, path)
    finally:
        discard(root, tmp)


def discard(root: Path, tmp: Path) -> None:
    """임시 파일 정리 — 실패해도 넘긴다(남은 숨김 임시 파일은 결과 · 검산에 쓰이지 않음 · r3 F8).

    폴더 위치가 확인될 때만 지운다(위치가 바뀌었으면 밖을 건드리지 않고 남겨 둔다 · r6 검토).
    """
    with contextlib.suppress(OSError, CheckRequired):
        _unlink(inside(root, Path(tmp).parent) / Path(tmp).name)


def write_once(root: Path, path: Path, data: bytes) -> str:
    """새 파일만 원자적으로 쓴다(검증자 r1 F4) · 반환 sha256 = stage_once → commit_once.

    쓰는 도중 중단되면 목표 이름은 생기지 않는다 — 읽을 수 없는 조각이 남지 않는다. 쓰는 곳은 연구 폴더
    아래 실제 폴더만(r5 F12 · 모든 쓰기가 이 함수 · stage_once · link_name 을 지나며 root 를 받는다).
    """
    commit_once(root, stage_once(root, path, data), Path(path))
    return store.sha256_bytes(data)


def new_id(now: datetime) -> str:
    return f"{now.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}_{uuid.uuid4().hex[:8]}"


def code_hashes(repo: Path) -> dict[str, str]:
    return {rel: store.sha256_file(Path(repo) / rel) for rel in CODE_FILES}


def env() -> dict[str, Any]:
    import importlib.metadata
    import sys

    out: dict[str, Any] = {"python": sys.version.split()[0]}
    for lib in ENV_LIBS:
        try:
            out[lib] = importlib.metadata.version(lib)
        except importlib.metadata.PackageNotFoundError:
            out[lib] = None
    return out
