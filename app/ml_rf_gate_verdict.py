"""POC4-03 — 모델별 preflight · 판정 조건 C1~C10 · 판정 순서 (PLAN §2-7 · 설계자 확정 Q7).

판정 순서 (위에서 처음 맞는 것):

```text
1. INVALID_STOP        실행 무효 사유가 하나라도 있음 (선형 재현 · 봉인/라이브 · 누수 · 자원 · 결정성 …)
2. REJECT_CLOSED       C1 거짓 그리고 C3 거짓            (두 지표 모두 모멘텀 이하)
3. INCONCLUSIVE_CLOSED C1 · C3 중 하나만 거짓            (한 지표만 열위)
4. REJECT_CLOSED       C5 · C6 · C7 중 하나라도 거짓      (특정 기간·설정 의존)
5. INCONCLUSIVE_CLOSED C2 또는 C4 거짓                   (CI 가 0 포함)
6. PASS
```

값이 None 인 조건은 거짓(fail-closed). 코드는 판정만 낸다 — Track A 종료·POC4-04 개방은 설계자·사용자가 정한다.
"""

from __future__ import annotations

import hashlib
import json
from typing import Optional

from app import ml_rf_gate_models as rfm
from app import research_run_guard as guard
from app.ml_pit_bias_report import n1_control
from app.ml_pit_universe import ARM_CONTROL, ARM_PIT
from app.ml_rf_gate_eval import LIN, MODELS, MOM, RF_PRIMARY
from app.ml_rf_gate_models import CONFIG_ORDER
from app.ml_rf_gate_report import (
    BOOTSTRAP_BLOCK,
    BOOTSTRAP_ITERATIONS,
    BOOTSTRAP_SEED,
    model_block,
    model_series,
    paired,
    robustness,
    yearly_table,
)
from app.ml_score_validity_eval import COST_BPS_GRID
from app.ml_score_validity_report import now_iso, preflight_gate

# PLAN §1-5 — recipe(설정 밖 규칙 · 판정 조건 정의) canonical JSON sha256. 다르면 실행 거부.
FROZEN_RECIPE_SHA256 = (
    "00992e6eaa2394680e6d106ececf66f77857eb34b800ad938da3c99feaa11350"
)
TRACK = "POC4-03"
RESULT_SCHEMA = "poc4_03_rf_kill_gate.v1"
CANONICAL_EXCLUDED = ("generated_at",)
PASS = "PASS"
REJECT_CLOSED = "REJECT_CLOSED"
INCONCLUSIVE_CLOSED = "INCONCLUSIVE_CLOSED"
INVALID_STOP = "INVALID_STOP"
VERDICTS = (PASS, REJECT_CLOSED, INCONCLUSIVE_CLOSED, INVALID_STOP)
KILL_GATE = {
    PASS: "CONTROL 진단 뒤 POC4-04 개방 여부 판단 (자동 개방 아님)",
    REJECT_CLOSED: "POC4-04·05 미개방 · Track A 종료",
    INCONCLUSIVE_CLOSED: "POC4-04·05 미개방 · Track A 종료",
    INVALID_STOP: "결과 판정 금지 · 지정된 1회 재실행만 허용",
}


def model_preflight(records: list[dict]) -> dict:
    """E2·02A 와 같은 fail-closed 게이트 (coverage · L1~L3 누수 · N-1 셔플) — 모델마다."""
    n1 = n1_control(records)
    return {"gate": preflight_gate(records, n1), "n1_negative_control": n1}


def _gt0(value: Optional[float]) -> bool:
    return value is not None and value > 0


def _ci_low_gt0(block: dict) -> bool:
    band = block.get("bootstrap_ci_95")
    return band is not None and _gt0(band.get("low"))


def conditions(comparisons: dict, robust: dict) -> dict:
    """PIT 기록으로 C1~C8 — comparisons[이름] = {ic, net25} paired · robust = RF_PRIMARY − MOM."""
    primary = comparisons["RF_PRIMARY_vs_MOM"]
    c1 = _gt0(primary["ic"]["mean_diff"])
    c3 = _gt0(primary["net25"]["mean_diff"])
    config_ok = {
        name: _gt0(comparisons[f"{name}_vs_MOM"]["ic"]["mean_diff"])
        and _gt0(comparisons[f"{name}_vs_MOM"]["net25"]["mean_diff"])
        for name in CONFIG_ORDER
    }
    loyo = robust["leave_one_year_out"]
    periods_ok = sum(1 for p in robust["periods"] if p["both_positive"])
    return {
        "C1_ic_point": c1,
        "C2_ic_ci_low": _ci_low_gt0(primary["ic"]),
        "C3_net25_point": c3,
        "C4_net25_ci_low": _ci_low_gt0(primary["net25"]),
        "C5_configs_both_positive": sum(config_ok.values()) >= 2,
        "C5_detail": config_ok,
        "C6_leave_one_year_out": bool(
            loyo["ic"]["complete"]
            and loyo["net25"]["complete"]
            and _gt0(loyo["ic"]["min"])
            and _gt0(loyo["net25"]["min"])
        ),
        "C7_periods_both_positive": periods_ok >= 2,
        "C7_detail": periods_ok,
        "C8_pit_advantage": c1 and c3,
    }


def decide(conds: dict, invalid_reasons: list[str]) -> dict:
    """판정 순서 1~6. `invalid_reasons` 가 있으면 INVALID_STOP (C9 결정성은 compare 가 넘긴다)."""
    if invalid_reasons:
        return _verdict(INVALID_STOP, "실행 무효", invalid_reasons)
    c1, c3 = conds["C1_ic_point"], conds["C3_net25_point"]
    if not c1 and not c3:
        return _verdict(REJECT_CLOSED, "IC 와 net25 모두 모멘텀 이하", ["C1", "C3"])
    if not (c1 and c3):
        failed = ["C1"] if not c1 else ["C3"]
        return _verdict(INCONCLUSIVE_CLOSED, "한 지표만 열위", failed)
    robust_failed = [
        c
        for c, key in (
            ("C5", "C5_configs_both_positive"),
            ("C6", "C6_leave_one_year_out"),
            ("C7", "C7_periods_both_positive"),
        )
        if not conds[key]
    ]
    if robust_failed:
        return _verdict(REJECT_CLOSED, "특정 기간·설정 의존", robust_failed)
    ci_failed = [
        c
        for c, key in (("C2", "C2_ic_ci_low"), ("C4", "C4_net25_ci_low"))
        if not conds[key]
    ]
    if ci_failed:
        return _verdict(INCONCLUSIVE_CLOSED, "CI 가 0 을 포함", ci_failed)
    return _verdict(PASS, "C1~C8 · C10 충족 (C9 결정성은 compare 에서)", [])


def _verdict(verdict: str, basis: str, failed: list[str]) -> dict:
    return {
        "verdict": verdict,
        "basis": basis,
        "failed": list(failed),
        "next": KILL_GATE[verdict],
    }


def final_verdict(candidate: Optional[dict], determinism_confirmed: bool) -> dict:
    """PIT 두 실행 compare 뒤 최종 판정 — 결정성 확인 실패(C9)를 먼저 본다."""
    if not determinism_confirmed:
        return _verdict(INVALID_STOP, "결정성 확인 실패", ["C9"])
    if candidate is None:
        return _verdict(INVALID_STOP, "판정 후보 없음", ["NO_CANDIDATE"])
    return dict(candidate)


# --- 결과 조립 ------------------------------------------------------------------------


def recipe() -> dict:
    """결과·manifest·재개 지문(recipe sha)에 같은 값이 들어간다."""
    return {
        "recipe_id": "POC4-03_RF_VS_MOMENTUM_KILL_GATE_V1",
        "models": list(MODELS),
        "rf_config_json": rfm.config_json(),
        "rf_config_sha256": rfm.config_sha256(),
        "rf_rules": rfm.recipe_block(),
        "linear": "02A 선형 경로 그대로(train_walk_forward · S+V · ratio (|S|+0.5)/(|S|+|V|))",
        "scores": "여섯 모델 모두 normalize_to_display_scores",
        "basket": "경계 동점 부분 가중 (편입도 = 점수와 k 로만) · 02A 코드 순서 값은 민감도 비교값",
        "cost_bps_grid": list(COST_BPS_GRID),
        "bootstrap": {
            "method": "circular moving-block bootstrap",
            "block_length": BOOTSTRAP_BLOCK,
            "iterations": BOOTSTRAP_ITERATIONS,
            "seed": BOOTSTRAP_SEED,
            "ci_percentiles": [2.5, 97.5],
        },
        "verdict_order": "INVALID → C1∧C3 거짓 REJECT → 한쪽만 INCONCLUSIVE → C5~C7 REJECT → "
        "C2/C4 INCONCLUSIVE → PASS",
        "conditions": {
            "C1": "IC: RF_PRIMARY − MOM 날짜별 paired 평균 > 0",
            "C2": "IC paired 차이 95% CI 하한 > 0",
            "C3": "net25(부분 가중): RF_PRIMARY − MOM paired 평균 > 0",
            "C4": "net25 paired 차이 95% CI 하한 > 0",
            "C5": "RF_A·B·C 가운데 IC 차이 > 0 이고 net25 차이 > 0 인 설정 ≥ 2",
            "C6": "모든 해 y 에 대해 y 를 뺀 paired 평균의 최솟값 > 0 (IC·net25 모두 · 모든 해 계산 가능)",
            "C7": "시간순 3구간(앞 구간부터 한 개씩 더 · 146 → 49·49·48) 중 IC·net25 모두 > 0 인 구간 ≥ 2",
            "C8": "C1 ∧ C3 (PIT)",
            "none_rule": "평균·CI 가 None 이면 그 조건은 거짓",
        },
        "paired_rule": "날짜별 RF − MOM · 한쪽 값이 None 인 날은 빼고 n_paired·사유 기록 · 개별 CI 하한끼리 "
        "빼지 않는다 · 부분 구간은 전체 시계열의 날짜별 값을 자른다",
        "reporting_only": "연도별 · 2026 제외 · 고정 설정 개별 CI · 선택 빈도 · 02A 코드 순서 바스켓",
        "resource_limits": {
            "perf_counter_seconds": guard.MAX_SECONDS,
            "peak_rss_bytes": guard.MAX_RSS_BYTES,
        },
    }


def recipe_sha256() -> str:
    blob = json.dumps(
        recipe(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def assert_frozen_recipe() -> None:
    got = recipe_sha256()
    if got != FROZEN_RECIPE_SHA256:
        raise rfm.RfContractError(f"recipe 가 동결값과 다르다: {got}")


def per_date(unit: dict, series: dict) -> dict:
    models, day = unit["models"], unit["signal_date"]
    return {
        "signal_date": day,
        "linear_canonical_sha256": unit.get("linear_canonical_sha256"),
        "rf": unit["rf"],
        "models": {
            m: {
                "ic_filter": models[m]["record"]["ic_filter"],
                "basket_mean": models[m]["basket"]["mean"],
                "net25": series[m]["net25"].get(day),
                "n": models[m]["basket"]["n"],
                "k": models[m]["basket"]["k"],
                "above": models[m]["basket"]["above"],
                "tie_group": models[m]["basket"]["tie_group"],
                "boundary_tie": models[m]["basket"]["boundary_tie"],
                "unique_scores": models[m]["basket"]["unique_scores"],
            }
            for m in MODELS
        },
    }


def build_payload(arm, official, dates, units, closes, source, ref_digest) -> dict:
    """arm 한 실행의 결과 — PIT 공식 실행에만 판정 후보를 쓴다 (CONTROL 은 진단)."""
    entries = {m: [u["models"][m] for u in units] for m in MODELS}
    blocks = {m: model_block(entries[m], closes) for m in MODELS}
    preflight = {m: model_preflight([e["record"] for e in entries[m]]) for m in MODELS}
    series = {m: model_series(entries[m]) for m in MODELS}
    comparisons = {
        f"{m}_vs_MOM": {
            key: paired(
                series[m][key],
                series[MOM][key],
                series[m][f"{key}_why"],
                series[MOM][f"{key}_why"],
            )
            for key in ("ic", "net25")
        }
        for m in (RF_PRIMARY, *CONFIG_ORDER, LIN)
    }
    robust = robustness(series[RF_PRIMARY], series[MOM], dates)
    invalid = [
        f"PREFLIGHT_{m}:{p['gate']['status']}"
        for m, p in preflight.items()
        if p["gate"]["status"] != "OK"
    ]
    conds = conditions(comparisons, robust)
    rf_meta = [u["rf"] for u in units]
    ok = [r for r in rf_meta if r.get("status") == "OK"]
    selected = [r["selected"] for r in ok]
    reasons = [r["selection_reason"] for r in ok]
    return {
        "schema_version": RESULT_SCHEMA,
        "track": TRACK,
        "arm": arm,
        "official": official,
        "generated_at": now_iso(),
        "recipe": recipe(),
        "source": {"before": source[0], "after": source[1], "same": True},
        "reference_02a": ref_digest,
        "calendar": {"evaluated": len(dates), "first": dates[0], "last": dates[-1]},
        "models": blocks,
        "preflight": preflight,
        "comparisons": comparisons,
        "robustness_rf_primary_vs_mom": robust,
        "yearly_by_model": {m: yearly_table(series[m], dates) for m in MODELS},
        "rf_selection": {
            "frequency": {n: selected.count(n) for n in CONFIG_ORDER},
            "reasons": {r: reasons.count(r) for r in sorted(set(reasons))},
            "excluded_overlap_rows_total": sum(
                r.get("excluded_overlap_rows", 0) for r in rf_meta
            ),
        },
        "per_date": [per_date(u, series) for u in units],
        "linear_reproduction": {
            "dates": len(units),
            "all_equal": True,
            "reference": "02A run1 progress record · canonical 텍스트 일치",
        },
        "conditions": conds,
        "invalid_reasons": invalid,
        "verdict_candidate": (
            decide(conds, invalid) if arm == ARM_PIT and official else None
        ),
        "verdict_role": _role(arm, official),
        "determinism": {
            "canonical_sha256": None,
            "excluded_fields": list(CANONICAL_EXCLUDED),
        },
    }


def _role(arm: str, official: bool) -> str:
    if not official:
        return "비공식 스모크 — 판정 후보 없음"
    if arm == ARM_PIT:
        return "PIT 판정 후보 — 최종 판정은 PIT 두 실행 compare 뒤"
    return "CONTROL 진단 — 판정 후보 없음 · PIT 판정을 뒤집지 않는다"


def pit_control_summary(
    pit: dict, ctl: dict, pit_final: dict, control_valid: bool
) -> dict:
    """PIT·CONTROL 진단 결합 — PIT 최종 판정이 PASS 일 때만 · PIT 판정을 뒤집지 않는다."""
    if pit["arm"] != ARM_PIT or ctl["arm"] != ARM_CONTROL:
        raise guard.RunnerError("summarize 는 PIT 결과와 CONTROL 결과를 받는다")
    if not (pit["official"] and ctl["official"]):
        raise guard.RunnerError("summarize 는 공식 실행 결과만 받는다")
    if pit_final.get("verdict") != PASS:
        raise guard.RunnerError(
            "PIT 최종 판정이 PASS 가 아니다 — CONTROL 진단 대상 아님"
        )
    table = {
        m: {
            arm_name: {
                "ic_mean": blk["models"][m]["ic_filter"]["mean"],
                "net25_mean": blk["models"][m]["top_decile_net_by_cost_bp"]["25"][
                    "mean"
                ],
            }
            for arm_name, blk in ((ARM_PIT, pit), (ARM_CONTROL, ctl))
        }
        for m in MODELS
    }
    pc = pit["comparisons"]["RF_PRIMARY_vs_MOM"]
    cc = ctl["comparisons"]["RF_PRIMARY_vs_MOM"]
    gap = {
        key: {
            "pit_mean_diff": pc[key]["mean_diff"],
            "control_mean_diff": cc[key]["mean_diff"],
            "control_minus_pit": (
                None
                if pc[key]["mean_diff"] is None or cc[key]["mean_diff"] is None
                else cc[key]["mean_diff"] - pc[key]["mean_diff"]
            ),
        }
        for key in ("ic", "net25")
    }
    return {
        "schema_version": "poc4_03_pit_control_summary.v1",
        "track": TRACK,
        "role": "진단 — PIT 판정을 뒤집지 않는다",
        "pit_final_verdict": pit_final,
        "control_diagnostic_valid": control_valid,
        "control_invalid_reasons": ctl.get("invalid_reasons", []),
        "pit_canonical_sha256": pit["determinism"]["canonical_sha256"],
        "control_canonical_sha256": ctl["determinism"]["canonical_sha256"],
        "models": table,
        "rf_primary_vs_mom": {ARM_PIT: pc, ARM_CONTROL: cc},
        "pit_control_gap": gap,
    }
