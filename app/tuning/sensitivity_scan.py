"""P205-STEP2: 신규 2축 감도 스캔.

SSOT를 임시로 변경하면서 Full Backtest를 반복 실행하고
각 후보값의 cagr/mdd/sharpe/trades를 기록한다.
실행 후 SSOT는 원래 baseline으로 복원된다.
"""

import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SSOT_PATH = (
    PROJECT_ROOT
    / "state"
    / "params"
    / "latest"
    / "strategy_params_latest.json"
)
REPORTS_DIR = PROJECT_ROOT / "reports" / "tuning"

# 감도 판정 기준 (A3)
THRESHOLDS = {
    "cagr": 0.50,
    "mdd": 0.20,
    "sharpe": 0.05,
    "trades": 1,
}


def _load_ssot():
    return json.loads(SSOT_PATH.read_text(encoding="utf-8"))


def _save_ssot(data):
    SSOT_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _run_backtest():
    """현재 SSOT 기준으로 Full Backtest 실행, 결과 반환."""
    from app.run_backtest import main as backtest_main

    backtest_main()
    result_path = (
        PROJECT_ROOT
        / "reports"
        / "backtest"
        / "latest"
        / "backtest_result.json"
    )
    return json.loads(result_path.read_text(encoding="utf-8"))


def _extract_metrics(result):
    s = result.get("summary", {})
    m = result.get("meta", {})
    return {
        "cagr": float(s.get("cagr", 0)),
        "mdd": float(s.get("mdd", 0)),
        "sharpe": float(s.get("sharpe", 0)),
        "total_trades": int(
            m.get("total_trades", s.get("total_trades", 0))
        ),
    }


def _is_sensitive(delta):
    return (
        abs(delta["cagr"]) >= THRESHOLDS["cagr"]
        or abs(delta["mdd"]) >= THRESHOLDS["mdd"]
        or abs(delta["sharpe"]) >= THRESHOLDS["sharpe"]
        or abs(delta["trades"]) >= THRESHOLDS["trades"]
    )


def _is_dead_zone(metrics):
    return metrics["total_trades"] == 0 and metrics["cagr"] == 0.0


def scan_axis(axis_name, ssot_key_path, test_values, baseline_ssot):
    """단일 축 감도 스캔."""
    # baseline 측정
    _save_ssot(baseline_ssot)
    baseline_result = _run_backtest()
    baseline_metrics = _extract_metrics(baseline_result)

    # baseline에서 현재 값 추출
    keys = ssot_key_path.split(".")
    obj = baseline_ssot
    for k in keys:
        obj = obj[k]
    baseline_value = obj

    print(f"\n=== {axis_name} scan (baseline={baseline_value}) ===")
    print(
        f"  Baseline: cagr={baseline_metrics['cagr']:.4f}, "
        f"mdd={baseline_metrics['mdd']:.4f}, "
        f"sharpe={baseline_metrics['sharpe']:.4f}, "
        f"trades={baseline_metrics['total_trades']}"
    )

    rows = []
    for val in test_values:
        # SSOT 임시 변경
        ssot_copy = json.loads(json.dumps(baseline_ssot))
        obj = ssot_copy
        for k in keys[:-1]:
            obj = obj[k]
        obj[keys[-1]] = val

        _save_ssot(ssot_copy)
        result = _run_backtest()
        metrics = _extract_metrics(result)

        delta = {
            "cagr": metrics["cagr"] - baseline_metrics["cagr"],
            "mdd": metrics["mdd"] - baseline_metrics["mdd"],
            "sharpe": metrics["sharpe"] - baseline_metrics["sharpe"],
            "trades": metrics["total_trades"]
            - baseline_metrics["total_trades"],
        }

        sensitive = _is_sensitive(delta)
        dead = _is_dead_zone(metrics)

        row = {
            "axis": axis_name,
            "test_value": val,
            "baseline_value": baseline_value,
            "cagr": metrics["cagr"],
            "mdd": metrics["mdd"],
            "sharpe": metrics["sharpe"],
            "total_trades": metrics["total_trades"],
            "delta_cagr": delta["cagr"],
            "delta_mdd": delta["mdd"],
            "delta_sharpe": delta["sharpe"],
            "delta_total_trades": delta["trades"],
            "sensitive": sensitive,
            "dead_zone": dead,
        }
        rows.append(row)

        flag = ""
        if dead:
            flag = " [DEAD ZONE]"
        elif sensitive:
            flag = " [SENSITIVE]"
        print(
            f"  {axis_name}={val}: "
            f"cagr={metrics['cagr']:.4f} (Δ{delta['cagr']:+.4f}), "
            f"mdd={metrics['mdd']:.4f} (Δ{delta['mdd']:+.4f}), "
            f"sharpe={metrics['sharpe']:.4f} (Δ{delta['sharpe']:+.4f}), "
            f"trades={metrics['total_trades']} "
            f"(Δ{delta['trades']:+d}){flag}"
        )

    # SSOT 복원
    _save_ssot(baseline_ssot)

    return rows, baseline_metrics, baseline_value


def write_csv(rows, filename):
    path = REPORTS_DIR / filename
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "axis",
        "test_value",
        "baseline_value",
        "cagr",
        "mdd",
        "sharpe",
        "total_trades",
        "delta_cagr",
        "delta_mdd",
        "delta_sharpe",
        "delta_total_trades",
        "sensitive",
        "dead_zone",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nCSV saved: {path}")
    return path


def determine_range(rows, baseline_value):
    """감도 있는 값 + baseline 기반으로 최종 범위 결정."""
    sensitive_vals = [
        r["test_value"]
        for r in rows
        if r["sensitive"] and not r["dead_zone"]
    ]
    # baseline도 유효 범위에 포함
    all_valid = sorted(set(sensitive_vals + [baseline_value]))

    if len(all_valid) < 2:
        return None, True  # LOW_SENSITIVITY

    # baseline을 포함하는 연속 band 찾기
    # (test_values가 이산적이므로, all_valid의 min~max를 band로)
    return (min(all_valid), max(all_valid)), False


def write_summary(
    vol_rows,
    vol_baseline,
    vol_range,
    vol_low,
    et_rows,
    et_baseline,
    et_range,
    et_low,
    baseline_metrics,
    baseline_ssot,
):
    """sensitivity_summary.md 생성."""
    bp = {
        "momentum_period": baseline_ssot["params"]["lookbacks"][
            "momentum_period"
        ],
        "volatility_period": baseline_ssot["params"]["lookbacks"][
            "volatility_period"
        ],
        "entry_threshold": baseline_ssot["params"]["decision_params"][
            "entry_threshold"
        ],
        "stop_loss": baseline_ssot["params"]["decision_params"][
            "exit_threshold"
        ],
        "max_positions": baseline_ssot["params"]["position_limits"][
            "max_positions"
        ],
    }

    lines = [
        "# 감도 보정 결과 (Sensitivity Calibration)",
        "",
        f"실행 시각: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S KST')}",
        "",
        "## Baseline 5축",
        "",
    ]
    for k, v in bp.items():
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    lines.append(
        f"Baseline 성과: CAGR={baseline_metrics['cagr']:.4f}%, "
        f"MDD={baseline_metrics['mdd']:.4f}%, "
        f"Sharpe={baseline_metrics['sharpe']:.4f}, "
        f"Trades={baseline_metrics['total_trades']}"
    )

    # volatility_period
    lines.append("")
    lines.append("## volatility_period 감도 결과")
    lines.append("")
    vol_sensitive = [
        r for r in vol_rows if r["sensitive"] and not r["dead_zone"]
    ]
    vol_dead = [r for r in vol_rows if r["dead_zone"]]
    lines.append(
        f"- 스캔 값: {[r['test_value'] for r in vol_rows]}"
    )
    lines.append(
        f"- 감도 있음: {[r['test_value'] for r in vol_sensitive]}"
    )
    lines.append(
        f"- Dead Zone: {[r['test_value'] for r in vol_dead]}"
    )
    if vol_low:
        lines.append("- **LOW_SENSITIVITY**: 예")
        lines.append("- 최종 범위: 기존 유지 (12~24)")
    else:
        lines.append("- LOW_SENSITIVITY: 아니오")
        lines.append(f"- 최종 채택 범위: {vol_range[0]}~{vol_range[1]}")

    # entry_threshold
    lines.append("")
    lines.append("## entry_threshold 감도 결과")
    lines.append("")
    et_sensitive = [
        r for r in et_rows if r["sensitive"] and not r["dead_zone"]
    ]
    et_dead = [r for r in et_rows if r["dead_zone"]]
    lines.append(
        f"- 스캔 값: {[r['test_value'] for r in et_rows]}"
    )
    lines.append(
        f"- 감도 있음: {[r['test_value'] for r in et_sensitive]}"
    )
    lines.append(
        f"- Dead Zone: {[r['test_value'] for r in et_dead]}"
    )
    if et_low:
        lines.append("- **LOW_SENSITIVITY**: 예")
        lines.append("- 최종 범위: 기존 유지 (0.01~0.05)")
    else:
        lines.append("- LOW_SENSITIVITY: 아니오")
        lines.append(f"- 최종 채택 범위: {et_range[0]}~{et_range[1]}")

    # 한 줄 해석
    lines.append("")
    lines.append("## 해석")
    lines.append("")
    if vol_low and et_low:
        lines.append(
            "현재 데이터 창에서는 두 축 모두 감도가 낮으므로 "
            "범위를 보수적으로 유지합니다."
        )
    elif vol_low:
        lines.append(
            "volatility_period는 감도가 낮아 기존 범위를 유지하고, "
            "entry_threshold만 재설정합니다."
        )
    elif et_low:
        lines.append(
            "entry_threshold는 감도가 낮아 기존 범위를 유지하고, "
            "volatility_period만 재설정합니다."
        )
    else:
        lines.append(
            "두 축 모두 유효 감도 구간이 확인되어 범위를 재설정합니다."
        )

    path = REPORTS_DIR / "sensitivity_summary.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSummary saved: {path}")
    return path


def main():
    print("P205-STEP2: Sensitivity Scan Start")

    baseline_ssot = _load_ssot()

    # volatility_period scan
    vol_values = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]
    vol_rows, baseline_metrics, vol_baseline = scan_axis(
        "volatility_period",
        "params.lookbacks.volatility_period",
        vol_values,
        baseline_ssot,
    )
    write_csv(vol_rows, "sensitivity_volatility_period.csv")
    vol_range, vol_low = determine_range(vol_rows, vol_baseline)

    # entry_threshold scan
    et_values = [0.01, 0.03, 0.05, 0.07, 0.10, 0.15, 0.20, 0.30]
    et_rows, _, et_baseline = scan_axis(
        "entry_threshold",
        "params.decision_params.entry_threshold",
        et_values,
        baseline_ssot,
    )
    write_csv(et_rows, "sensitivity_entry_threshold.csv")
    et_range, et_low = determine_range(et_rows, et_baseline)

    # Summary
    write_summary(
        vol_rows,
        vol_baseline,
        vol_range,
        vol_low,
        et_rows,
        et_baseline,
        et_range,
        et_low,
        baseline_metrics,
        baseline_ssot,
    )

    # 최종 SSOT 복원 확인
    restored = _load_ssot()
    assert (
        restored["params"]["lookbacks"]["volatility_period"]
        == vol_baseline
    )
    print("\nSSOT restored to baseline. Scan complete.")

    return {
        "vol_range": vol_range,
        "vol_low": vol_low,
        "et_range": et_range,
        "et_low": et_low,
    }


if __name__ == "__main__":
    main()
