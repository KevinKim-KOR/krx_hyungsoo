"""POC6-08 — 고정 입력 · 기준 · 구성 · 실행 잠금 · 1회 쓰기(PLAN §1 · §2 · §7 · 판정 §1 · §3-3).

입력은 경로와 **완전한** sha256 으로 고정한다(PLAN 표의 축약 해시로 대신하지 않음 · 판정 §1). 기대 개수는
PLAN §2 표(성과 열람 전 조사)이며 `lock` 이 08 구현으로 다시 세어 다르면 `CheckRequired` 로 멈춘다(판정 §4).
"""

from __future__ import annotations

import contextlib
import json
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.d20_pooled import study as S
from app.forward_compare import protocol as _p06
from app.ml_evidence import store
from app.reentry_review import model as m06

PROTOCOL_ID = "poc6-08-v1"
ROOT = Path("state/ml/research/poc6_08")
LOCK_NAME = ".run.lock"
# 06 과 같은 1회 쓰기(덮어쓰기 없음) · 같은 모양의 정렬 키 JSON — 단 비유한 수(NaN · ±inf)는 쓰지 않는다(r1 F2).
write_once = _p06.write_once


def dumps(obj: Any, *, compact: bool = False) -> bytes:
    """06 `dumps` 와 같은 바이트 모양 · `allow_nan=False`(비유한 수가 있으면 ValueError)."""
    if compact:
        text = json.dumps(
            obj,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    else:
        text = json.dumps(
            obj, ensure_ascii=False, sort_keys=True, indent=1, allow_nan=False
        )
    return (text + "\n").encode("utf-8")


def _reject_constant(name: str) -> Any:
    raise ValueError(f"비유한 수 {name}")


def _finite_float(text: str) -> float:
    v = float(text)
    if not math.isfinite(v):  # 1e999 같은 넘침 → inf
        raise ValueError(f"비유한 수 {text[:24]}")
    return v


def loads(text: str) -> Any:
    """08 산출물 읽기 — NaN · Infinity 토큰 · 넘치는 수를 거절(손상으로 본다 · r1 F2)."""
    return json.loads(text, parse_constant=_reject_constant, parse_float=_finite_float)


EVIDENCE_ROOT = store.EVIDENCE_ROOT

# ── 고정 입력(판정 §1) ─────────────────────────────────────────────────────────
COHORT_PATH = Path("state/ml/research/poc6_06/cohort_v1/cohort.json")
COHORT_SHA = "f11f45201d272c6ea4a3c0240e1ec2be7a1733ae57c8951942ce0c178b86f7d0"
PRICES_PATH = Path(
    "state/ml/research/poc6_06/bootstrap/20261023T011918Z_72843194/prices.json"
)
PRICES_SHA = "428f56a7e1f7a5b7d91ad53b5edba6404fa06d357ef69b12bcfd489d86fe8c8b"
BENCH_PATH = Path("state/ml/research/poc6_03/20261021T161446_3403e974/copy.sqlite")
BENCH_SHA = "276c29e74b0d100e97d9eaf33b59214ab896329d8e87004384a74503143bb088"
BENCH = "069500"
AXIS_RUN = "20261023T004002Z_9211e9fb"  # 06 초기 학습의 calendar_from_run
AXIS_KOSPI_OBJECT = "e5b359f5e9716677cbf2420aba4df4fa5921d20ff3318291b925ad63229cd6d1"
AXIS_CALENDAR_FILES = (
    (
        "krx_trading_days_2026.csv",
        "428c852fed8595002ed27bf7726a3ab4c197b1c46c58c237fcbb561cdeb3856d",
    ),
)
CAP = "2026-10-22"  # 자료 상한(설계 §2-2)
SOURCE = "FinanceDataReader"  # 두 사본 모두 FDR(네이버) · 06 `AxisSeries` 허용 출처

# ── 구간 · 적격 · 가용(설계 §2-2 · §5) ──────────────────────────────────────────
FOLDS = 3
FOLD_LEN = 63
TARGET_GAP = 20  # anchor = T 의 축 20거래일 전
MIN_TRAIN = 252
MIN_TEST = 42
MIN_ELIGIBLE = 5
COVERAGE = 0.80
REVIEW_OUT = ("458030", "130730", "114100", "488720", "447620", "271050", "282000")

# ── 구성 · 판정 기준(설계 §4 · §6 · 판정 §3-2) ────────────────────────────────────
P_NAMES = ("chg5", "chg20", "chg60", "vol20", "from_high60")  # 02/06 순서 그대로
EXTRA = {"HGB_P": (), "HGB_PV": ("V",), "HGB_PR": ("R",), "HGB_PVR": ("V", "R")}
CONFIGS = ("MEDIAN_P", "RIDGE_P", "HGB_P", "HGB_PV", "HGB_PR", "HGB_PVR")
CANDIDATES = ("HGB_PV", "HGB_PR", "HGB_PVR")
SCOPES = ("G_ALL", "G_REVIEW")
IMPROVE = S.IMPROVE  # 0.05
WIN_BLOCKS = S.WIN_BLOCKS  # 2
WORSE_LIMIT = S.WORSE_LIMIT  # 0.05
TAIL = -0.08  # 실제 D20 ≤ -8%
TAIL_MIN_DATES = 20
TAIL_MIN_TICKERS = 3
U_WORSE = 0.05
RESTORE_TOL = 1e-12

# ── PLAN §2 표(성과 열람 전 조사 · lock 이 다시 세어 대조) ─────────────────────────
# fmt: off
EXPECTED = {
    "T": "2026-10-19",
    "anchor": "2026-09-15",
    "folds": [
        ["2025-12-08", "2026-03-13"],
        ["2026-03-16", "2026-06-16"],
        ["2026-06-17", "2026-09-15"],
    ],
    "eligible": [
        "108450", "114100", "122090", "130730", "203780", "211900", "271050",
        "282000", "291890", "300640", "354500", "364960", "381180", "414780",
        "433220", "445690", "447620", "453660", "458030", "461950", "476260",
    ],
    "train_rows": [32073, 33396, 34719],
    "test_rows": {"G_ALL": [1323, 1323, 1323], "G_REVIEW": [945, 945, 945]},
    # 종목별 · 가용(판정 §4) — 제외 3종 1구간 학습 예제 · 적격 시험 날짜 · 제외 원인 · V/R 결측 수
    "excluded_fold1_train": {"0015K0": 117, "488720": 243, "494670": 195},
    "eligible_test_dates": [63, 63, 63],
    "exclusion_causes": ["BEFORE_FIRST_ROW"],
    "coverage_missing": 0,
    "coverage_denominators_match": True,
}
# fmt: on

# 실행 코드 근거(판정 §3-3) — 새 모듈 · CLI · 실제 재사용 계산 파일의 내용 해시.
CODE_FILES = (
    "app/feature_gain/__init__.py",
    "app/feature_gain/protocol.py",
    "app/feature_gain/inputs.py",
    "app/feature_gain/study.py",
    "app/feature_gain/report.py",
    "app/feature_gain/verify.py",
    "scripts/run_feature_gain.py",
    "app/reentry_review/prices.py",
    "app/reentry_review/model.py",
    "app/stored_volume_evidence.py",
    "app/d20_pooled/study.py",
    "app/forward_compare/protocol.py",
    "app/trading_day_lag.py",
    "app/market_briefing/calendar.py",
    "app/ml_evidence/store.py",
)
ENV_LIBS = ("numpy", "scikit-learn", "joblib", "threadpoolctl", "scipy")


class CheckRequired(Exception):
    """입력 손상 · 해시 불일치 · 읽기 실패 · 잠금과 다름 — 자료 결측으로 숨기지 않고 멈춘다."""


class Busy(Exception):
    """같은 연구 폴더에서 다른 실행이 진행 중 — 아무것도 쓰지 않았다."""


class Refused(Exception):
    """이미 있는 잠금 · 공식 결과를 다시 만들려 함(1회 규칙)."""


def locks(root: Path) -> dict[str, tuple[Path, dict[str, Any]]]:
    """잠금 전부 — lock_id → (폴더, protocol)."""
    out = {}
    for f in sorted(Path(root).glob("*/protocol.json")):
        try:
            doc = read_json(f)
            out[doc["lock_id"]] = (f.parent, doc)
        except (OSError, ValueError, KeyError, TypeError) as e:
            raise CheckRequired(f"protocol 읽기 실패: {f.parent.name}") from e
    return out


def active_lock(root: Path) -> tuple[Path, dict[str, Any]]:
    """지금 쓰는 잠금 — 정정 잠금 사슬의 끝(다른 잠금이 정정하지 않은 하나 · 판정 §3-3)."""
    found = locks(root)
    corrected = [
        d["corrects"]["lock_id"] for _, d in found.values() if d.get("corrects")
    ]
    if len(corrected) != len(set(corrected)) or not set(corrected) <= set(found):
        raise CheckRequired(
            "정정 잠금 사슬이 어긋남(같은 잠금을 둘이 정정 · 없는 잠금)"
        )
    heads = [k for k in found if k not in set(corrected)]
    if len(heads) != 1:
        raise CheckRequired(f"지금 쓰는 잠금 수 {len(heads)}(1이어야 함)")
    return found[heads[0]]


def new_id(now: datetime) -> str:
    return f"{now.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}_{uuid.uuid4().hex[:8]}"


@contextlib.contextmanager
def run_lock(root: Path) -> Iterator[None]:
    """연구 폴더 단일 실행 잠금(06 `run_lock` 과 같은 방식 · 기다리지 않음)."""
    Path(root).mkdir(parents=True, exist_ok=True)
    with store.file_lock(Path(root) / LOCK_NAME, wait_s=0.0) as ok:
        if not ok:
            raise Busy("같은 연구 폴더에서 다른 실행이 진행 중")
        yield


def read_json(path: Path) -> Any:
    return loads(Path(path).read_text(encoding="utf-8"))


def code_hashes(repo: Path) -> dict[str, str]:
    return {
        rel: store.sha256_bytes((Path(repo) / rel).read_bytes()) for rel in CODE_FILES
    }


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


def recipe() -> dict[str, Any]:
    """설계 §4 의 고정 설정(결과 전 잠금 · 결과를 보고 바꾸지 않음)."""
    return {
        "configs": list(CONFIGS),
        "candidates": list(CANDIDATES),
        "features": {
            "P": list(P_NAMES),
            "V": "volume_ratio_20d = V(t) / mean(V(t-20..t-1)) · POC5-09 함수 반올림 전",
            "R": "relative_return_20d = [C(t)/C(t-20)-1] - [B(t)/B(t-20)-1]",
            "order": {k: list(P_NAMES) + list(v) for k, v in EXTRA.items()},
        },
        "target": "D20(t) = min(0, min(C(t+h)/C(t)-1, h=1..20))",
        "HGB": {
            "params": dict(S.HGB_PARAMS),
            "resolved": S.hgb_resolved_params(),  # 설치 판의 나머지 기본값(설계 §4)
            "weights": "1/n_d(HGB 네 구성끼리만)",
        },
        "RIDGE": "종목별 StandardScaler -> Ridge(alpha=1, solver=svd, fit_intercept=True)",
        "MEDIAN": "종목별 학습 목표 중앙값(짝수 = 가운데 두 값 평균)",
        "clip": [-1.0, 0.0],
        "missing": "V · R 결측 = 보관 null + 사유 · HGB 입력에서만 NaN · 기본 행 유지",
        "criteria": {
            "A": {"improve": IMPROVE, "win_blocks": WIN_BLOCKS, "worse": WORSE_LIMIT},
            "B": {
                "ridge_improve": IMPROVE,
                "median": "후보 < MEDIAN_P",
                "tail": TAIL,
                "tail_min_dates": TAIL_MIN_DATES,
                "tail_min_tickers": TAIL_MIN_TICKERS,
                "u_worse": U_WORSE,
            },
            "coverage": COVERAGE,
            "min_eligible": MIN_ELIGIBLE,
        },
        "scopes": {"G_ALL": "적격 전체", "G_REVIEW": {"out": list(REVIEW_OUT)}},
        # 기간 · 적격 상수(설계 §2-2 · §5) — 정정 잠금이 바꿀 수 없게 recipe 에 둔다.
        "split": {
            "cap": CAP,
            "target_gap": TARGET_GAP,
            "folds": FOLDS,
            "fold_len": FOLD_LEN,
            "lookback": m06.LB,
            "horizon": m06.H,
            "min_train": MIN_TRAIN,
            "min_test": MIN_TEST,
            "train_rule": "목표 끝 axis[i+20] < 시험 시작(모든 종목 같은 날짜 경계)",
        },
    }
