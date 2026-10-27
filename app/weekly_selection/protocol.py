"""POC6-11 고정 입력 · 기준 · 잠금 사실(성과 없이 셀 수 있는 것) · 공용 도우미 — 설계 §9 · §11 · PLAN §1 · §2.

```text
고정     봉인 판(파일 · content 해시) · 기간 · 분기 · 비용 · 최소 표본 · 예산 · 실행 코드 목록
사실     자격 · 정답 '가용성' · 평가 주 · K 실행일 · 분기 학습 날짜/행 · 모델 배정(cutoff ≤ 신호 · 가장 최근 판)
대조     PLAN 표(EXPECTED)와 다르면 CheckRequired(prepare) · 잠금과 다르면 CheckRequired(run · verify)
```
"""

from __future__ import annotations

import gzip
from pathlib import Path
from typing import Any, Optional

from app import krx_sealed_reader as K
from app.feature_gain import protocol as P8
from app.ml_evidence import store
from app.weekly_selection import data as D
from app.weekly_selection import features as F
from app.weekly_selection import model as M
from app.weekly_selection import policy as PO
from app.weekly_selection import report as R

PROTOCOL_ID = "poc6-11-v1"
ROOT = Path("state/ml/research/poc6_11")
DB = K.DEFAULT_SEALED_DB
VERSION = K.SEALED_VERSION
FILE_SHA = "fe3022e98d861beb70ead529c7efc678f5197eb20a754af48541f221656dacf2"
CONTENT_SHA = "c1a877762b9b1f296365801030641c86bc4508f4c2643f1a6793e39119f9bb4c"
VAL_RANGE = ("2018-01-01", "2020-12-31")
TEST_RANGE = ("2021-01-01", "2026-09-21")
SUB_RANGES = (
    ("2021-01-01", "2022-12-31"),
    ("2023-01-01", "2024-12-31"),
    ("2025-01-01", "2026-09-21"),
)
VAL_Q = ((2018, 1), (2020, 4))
TEST_Q = ((2021, 1), (2026, 3))
BASE_COST, ALT_COST = 0.002, 0.004
MIN_WEEKS = {"val": 104, "test": 156, "sub": 52}
MIN_TRAIN_WEEKS, MIN_TRAIN_ROWS = 104, 5000
BUDGET_S = 90 * 60
RSS_MAX = 8 * 1024**3
CODE_FILES = (
    "app/weekly_selection/__init__.py",
    "app/weekly_selection/data.py",
    "app/weekly_selection/features.py",
    "app/weekly_selection/model.py",
    "app/weekly_selection/policy.py",
    "app/weekly_selection/report.py",
    "app/weekly_selection/protocol.py",
    "app/weekly_selection/flow.py",
    "app/weekly_selection/audit.py",
    "app/weekly_selection/evidence.py",
    "app/weekly_selection/verify.py",
    "scripts/run_weekly_selection.py",
    "requirements-research-ml.txt",
    "app/krx_sealed_reader.py",
    "app/ml_pit_universe.py",
    "app/market_topn_helpers.py",
    "app/ml_score_validity_eval.py",
    "app/ml_strategy_performance.py",
    "app/feature_gain/protocol.py",
    "app/forward_compare/protocol.py",
    "app/ml_evidence/store.py",
)
# PLAN §1 · §2 표(성과 열람 전 조사 · prepare 가 다시 세어 대조 · 다르면 CheckRequired)
EXPECTED = {
    "member_dates": 3122,
    "first_date": "20140102",  # 봉인 기록(member bas_dd) 표기
    "last_date": "20260921",
    "series": 1419,
    "rows": 1612728,
    "signals": 663,
    "first_signal": "2014-01-03",
    "last_signal": "2026-09-18",
    "reasons": {"name": 90098, "run126": 29572, "liquidity": 101157, "vol0": 262},
    "eligible_rows": 122186,
    "first_20": "2014-07-11",
    "label_rows": 113269,
    "signals_20": 636,
    "usable_dates": 621,
    "unusable_matured": ["2015-12-11", "2016-01-29"],
    "immature": 13,
    "val": {
        "start": "2018-01-02",
        "end": "2020-12-30",
        "weeks": 157,
        "first_signal": "2017-12-28",
        "k_exec": "2018-01-03",
        "eligible_min_med_max": [62, 108, 161],
    },
    "test": {
        "start": "2021-01-04",
        "end": "2026-09-21",
        "weeks": 298,
        "first_signal": "2020-12-30",
        "k_exec": "2021-01-05",
        "eligible_min_med_max": [139, 241, 717],
    },
    "sub_weeks": [104, 104, 90],
    "quarters": 35,
    "train_min_weeks": 165,
    "train_min_rows": 7593,
    "train_max_rows": 74307,
    "fits": 47,
    "quarter_spot": {
        "2018Q1": ["2017-12-28", 165, 7593, "2014-07-11", "2017-09-15"],
        "2020Q4": ["2020-09-29", 245, 19979, "2015-10-02", "2020-06-26"],
        "2021Q1": ["2020-12-30", 244, 21064, "2016-01-08", "2020-09-18"],
        "2026Q3": ["2026-06-30", 247, 74307, "2021-07-02", "2026-03-20"],
    },
}
CheckRequired = D.CheckRequired


class Refused(Exception):
    """이미 있는 잠금 · 공식 결과를 다시 만들려 함(1회 규칙)."""


class BudgetStop(Exception):
    """실행 자원 상한(90분 · 8GiB) 초과 — BUDGET_STOP."""


def _sha(obj: Any) -> str:
    return store.sha256_bytes(store.canonical(obj))


def code_hashes(repo: Path) -> dict[str, str]:
    return {
        rel: store.sha256_bytes((Path(repo) / rel).read_bytes()) for rel in CODE_FILES
    }


def recipe() -> dict[str, Any]:
    return {
        "price_basis": K.PRICE_BASIS,
        "price_note": R.PRICE_NOTE,
        "eligibility": {
            "run_rows": D.RUN_ROWS,
            "liq_days": D.LIQ_DAYS,
            "liq_window": "t-19..t",
            "liq_min_proxy": D.LIQ_MIN,
            "min_eligible": D.MIN_ELIGIBLE,
        },
        "columns": list(F.COLUMNS),
        "columns_sha256": _sha(list(F.COLUMNS)),
        "label": {
            "exec_lag": F.EXEC_LAG,
            "horizon": F.HORIZON,
            "usable_min": F.USABLE_MIN,
            "usable_share": F.USABLE_SHARE,
            "train_years": F.TRAIN_YEARS,
            "mature_gap": F.MATURE_GAP,
        },
        "model": {
            "common": M.COMMON,
            "structs": M.STRUCTS,
            "rounds": M.NUM_ROUNDS,
            "restore_tol": M.RESTORE_TOL,
        },
        "policy": {
            "slots": PO.SLOTS,
            "keep_rank": PO.KEEP_RANK,
            "entry_top": PO.ENTRY_TOP,
            "budget_share": PO.BUDGET_SHARE,
            "big_move": PO.BIG_MOVE,
            "protect": PO.PROTECT,
            "cooldown_reviews": PO.COOLDOWN_REVIEWS,
            "start_value": PO.START_VALUE,
        },
        "costs": [BASE_COST, ALT_COST],
        "ranges": {
            "val": VAL_RANGE,
            "test": TEST_RANGE,
            "subs": SUB_RANGES,
            "val_q": VAL_Q,
            "test_q": TEST_Q,
        },
        "judge": {
            "gap_min": R.GAP_MIN,
            "mdd_limit": R.MDD_LIMIT,
            "turnover_max": R.TURNOVER_MAX,
            "sub_win_min": R.SUB_WIN_MIN,
            "select_tie": R.SELECT_TIE,
        },
        "bootstrap": {
            "block": R.BLOCK_WEEKS,
            "draws": R.BOOT_DRAWS,
            "seed": R.BOOT_SEED,
        },
        "type_rules": R.TYPE_RULES,
        "budget": {"wall_s": BUDGET_S, "rss_bytes": RSS_MAX, "threads": M.THREADS},
    }


# ── 사실(성과 없이 셀 수 있는 것) ─────────────────────────────────────────────────


def _window(
    p: D.Panel, sig: list[int], cnt: dict[int, int], lo: str, hi: str
) -> dict[str, Any]:
    start, end = D.first_trading(p.axis, lo), D.last_trading(p.axis, hi)
    by_exec = [i for i in sig if start <= i + F.EXEC_LAG <= end]
    plan = [i for i in by_exec if cnt[i] >= D.MIN_ELIGIBLE]
    c = sorted(cnt[i] for i in by_exec)
    return {
        "start": p.axis[start],
        "end": p.axis[end],
        "weeks": len(plan),
        "first_signal": p.axis[plan[0]] if plan else None,
        "k_exec": p.axis[plan[0] + F.EXEC_LAG] if plan else None,
        "eligible_min_med_max": [c[0], c[len(c) // 2], c[-1]] if c else None,
        "plan_signals": [p.axis[i] for i in plan],
    }


def _quarters(p, members, count, usable, rng) -> list[dict]:
    out = []
    for c in F.quarter_cutoffs(p.axis, *rng):
        sigs = F.quarter_rows(p.axis, members, count, usable, c["cutoff_idx"])
        out.append(
            {
                "id": c["id"],
                "cutoff": c["cutoff"],
                "weeks": len(sigs),
                "rows": sum(count[i] for i in sigs),
                "first": p.axis[sigs[0]] if sigs else None,
                "last": p.axis[sigs[-1]] if sigs else None,
                "signals_sha256": _sha([p.axis[i] for i in sigs]),
            }
        )
    return out


def survey(
    p: D.Panel,
) -> tuple[dict[str, Any], D.Eligibility, dict[int, int], dict[int, bool]]:
    sig = D.weekly_signals(p.axis)
    el = D.eligibility(p, sig)
    count, usable = F.availability(p, el.members)
    cnt = {i: len(el.members[i]) for i in sig}
    n = len(p.axis)
    s20 = [i for i in sig if cnt[i] >= D.MIN_ELIGIBLE]
    last_q = F.EXEC_LAG + F.HORIZON - 1
    val = _window(p, sig, cnt, *VAL_RANGE)
    test = _window(p, sig, cnt, *TEST_RANGE)
    subs = [_window(p, sig, cnt, lo, hi)["weeks"] for lo, hi in SUB_RANGES]
    vq = _quarters(p, el.members, count, usable, VAL_Q)
    tq = _quarters(p, el.members, count, usable, TEST_Q)
    cuts = F.quarter_cutoffs(p.axis, *VAL_Q) + F.quarter_cutoffs(p.axis, *TEST_Q)
    assign = {}
    for tag, w, ids in (
        ("val", val, {q["id"] for q in vq}),
        ("test", test, {q["id"] for q in tq}),
    ):
        for d in w["plan_signals"]:
            m = F.model_for(p.axis.index(d), cuts)
            if m is None or m["id"] not in ids:
                raise CheckRequired(
                    f"{tag} 신호 {d} 의 모델 배정 이상: {m and m['id']}"
                )
            assign[d] = m["id"]
    members = {p.axis[i]: [p.codes[j] for j in el.members[i]] for i in sig}
    excluded = {
        p.axis[i]: {k: [p.codes[j] for j in v] for k, v in el.excluded[i].items()}
        for i in sig
    }
    qs = vq + tq
    fx = {
        **{k: p.seal[k] for k in ("member_dates", "first_date", "last_date")},
        "file_sha256": p.seal["file_sha256"],
        "content_sha256": p.seal["content_sha256"],
        "series": len(p.codes),
        "rows": int(p.has_row.sum()),
        "signals": len(sig),
        "first_signal": p.axis[sig[0]],
        "last_signal": p.axis[sig[-1]],
        "reasons": el.reasons,
        "eligible_rows": sum(cnt.values()),
        "first_20": p.axis[s20[0]],
        "label_rows": sum(count.values()),
        "signals_20": len(s20),
        "usable_dates": sum(1 for i in s20 if usable[i]),
        "unusable_matured": [
            p.axis[i] for i in s20 if i + last_q < n and not usable[i]
        ],
        "immature": sum(1 for i in s20 if i + last_q >= n),
        "val": val,
        "test": test,
        "sub_weeks": subs,
        "quarters": len(qs),
        "train_min_weeks": min(q["weeks"] for q in qs),
        "train_min_rows": min(q["rows"] for q in qs),
        "train_max_rows": max(q["rows"] for q in qs),
        "fits": 2 * len(vq) + len(tq),
        "quarter_spot": {
            q["id"]: [q["cutoff"], q["weeks"], q["rows"], q["first"], q["last"]]
            for q in qs
            if q["id"] in EXPECTED.get("quarter_spot", {})
        },
        "quarter_detail": {"val": vq, "test": tq},
        "assign": assign,
        "members_sha256": _sha(members),
        "excluded_sha256": _sha(excluded),
        "usable_sha256": _sha(
            {p.axis[i]: [count[i], usable[i]] for i in sorted(count)}
        ),
    }
    short = []
    if val["weeks"] < MIN_WEEKS["val"] or test["weeks"] < MIN_WEEKS["test"]:
        short.append("평가 주 부족")
    if min(subs) < MIN_WEEKS["sub"]:
        short.append("보조 구간 주 부족")
    if fx["train_min_weeks"] < MIN_TRAIN_WEEKS or fx["train_min_rows"] < MIN_TRAIN_ROWS:
        short.append("분기 학습 표본 부족")
    fx["data_short"] = short
    return fx, el, count, usable


def input_refs() -> dict[str, str]:
    """잠금 입력 고정값(경로 제외 — 검증 사본 경로가 달라도 같은 판 · 같은 해시면 같은 입력)."""
    return {"version": VERSION, "file_sha256": FILE_SHA, "content_sha256": CONTENT_SHA}


def lock_problems(lk: dict[str, Any]) -> list[str]:
    """잠금 문서 ↔ 지금 코드가 쓰는 계약(식별자 · 입력 · recipe). run 은 거부 · verify 는 불일치(검증 r1 F1)."""
    out = []
    if (
        lk.get("schema") != "poc6_11_protocol_v1"
        or lk.get("protocol_id") != PROTOCOL_ID
    ):
        out.append("잠금 식별자(schema · protocol_id) 다름")
    got = {k: (lk.get("inputs") or {}).get(k) for k in input_refs()}
    if got != input_refs():
        out.append("잠금 입력(판 · 파일 · content 해시) ≠ 코드 고정값")
    norm = P8.loads(P8.dumps(recipe(), compact=True).decode())
    if store.canonical(lk.get("recipe")) != store.canonical(norm):
        diff = sorted(
            k
            for k in norm
            if store.canonical((lk.get("recipe") or {}).get(k))
            != store.canonical(norm[k])
        )
        out.append(f"잠금 recipe ≠ 지금 코드의 설정({', '.join(diff) or '키 구성'})")
    return out


def compare(fx: dict[str, Any]) -> list[str]:
    diffs = []
    for k, exp in EXPECTED.items():
        got = fx.get(k)
        if k in ("val", "test"):
            got = {kk: got.get(kk) for kk in exp}
        if got != exp:
            diffs.append(f"{k}: PLAN {exp} · 실제 {got}")
    return diffs


def scores_for(t: F.Table, rows: list[int], col: str) -> dict[int, float]:
    k = F.COLUMNS.index(col)
    out = {t.rows[r][1]: t.X[r][k] for r in rows}
    if any(v is None for v in out.values()):
        raise CheckRequired(f"{col} 점수 결측(연속 126 자격이 창을 보장하지 못함)")
    return out


def trend_ok(t: F.Table, rows: list[int]) -> set[int]:
    k = F.COLUMNS.index("MA_GAP_60")
    return {t.rows[r][1] for r in rows if t.X[r][k] is not None and t.X[r][k] > 0}


def model_ids(assign: dict[str, str], struct: str) -> dict[str, str]:
    return {d: f"{q}_{struct}" for d, q in assign.items()}


def read_gz(path: Path) -> Any:
    return P8.loads(gzip.decompress(Path(path).read_bytes()).decode("utf-8"))


def latest_run(root: Path, run_id: Optional[str] = None) -> tuple[Path, dict, Path]:
    ldir, lk = P8.active_lock(Path(root))
    runs = (
        sorted(d for d in (ldir / "runs").iterdir() if d.is_dir())
        if (ldir / "runs").exists()
        else []
    )
    if run_id:
        runs = [d for d in runs if d.name == run_id]
    if not runs:
        raise CheckRequired("검증할 실행이 없음")
    return ldir, lk, runs[-1]


def load_json(path: Path) -> Any:
    return P8.loads(Path(path).read_text(encoding="utf-8"))


MISMATCH_SUFFIX = ".mismatch.json"  # 복원 차이 정지 근거(flow) — 모델 기록이 아니다


def model_files(rdir: Path) -> list[Path]:
    """모델 기록 `models/<id>.json` 만 — 복원 차이 정지 근거 `<id>.mismatch.json` 은 뺀다(검증 r4 F4)."""
    d = Path(rdir) / "models"
    if not d.exists():
        return []
    return [f for f in sorted(d.glob("*.json")) if not f.name.endswith(MISMATCH_SUFFIX)]


def schedule(axis: list[str], recs: list[dict]) -> list[dict]:
    """모델 적용 일정(판정 §4) — 신호 · 예정 실행일 · 모델 · cutoff(재생의 가상 정보 시각) · 실제 학습/예측 시각."""
    pos = {d: k for k, d in enumerate(axis)}
    out = []
    for r in recs:
        for d in r["signals"]:
            e = pos[d] + F.EXEC_LAG
            out.append(
                {
                    "signal": d,
                    "exec_date": axis[e] if e < len(axis) else None,
                    "model": r["id"],
                    "phase": r["phase"],
                    "cutoff": r["cutoff"],
                    "virtual_info_time": f"{r['cutoff']} 종가 뒤(재생 가정)",
                    "train_started_at": r["train_started_at"],
                    "trained_at": r["trained_at"],
                    "predicted_at": r["predicted_at"],
                }
            )
    return sorted(out, key=lambda x: (x["signal"], x["model"]))


def manifest(rdir: Path) -> dict[str, str]:
    """실행 폴더 산출물 해시(run.json 제외 · verify 기록은 실행 폴더 밖)."""
    return {
        str(f.relative_to(rdir)): store.sha256_file(f)
        for f in sorted(Path(rdir).rglob("*"))
        if f.is_file() and f.name != "run.json"
    }
