#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/check_backtest_reliability.py — P181-R 백테스트 신뢰성 검증 스크립트

Usage:
  python tools/check_backtest_reliability.py --mode full --repeat 5 --seed 42 --provider both
  python tools/check_backtest_reliability.py --mode quick --repeat 3 --provider fdr

검증 항목:
  A) Determinism: 같은 입력으로 N회 반복 → 결과 동일성
  B) Cache/Network: 2회차에 download_count==0
  C) Provider 교차: fdr vs yfinance 결과 폭발 여부
"""

from __future__ import annotations
import argparse
import json
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("check_reliability")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SSOT_PATH = PROJECT_ROOT / "state" / "params" / "latest" / "strategy_params_latest.json"
RESULT_PATH = PROJECT_ROOT / "reports" / "backtest" / "latest" / "backtest_result.json"
REPORT_PATH = (
    PROJECT_ROOT / "reports" / "backtest" / "latest" / "reliability_check.json"
)


# ─── Helpers ──────────────────────────────────────────────────────────────
def _reset_telemetry():
    """Reset the module-level download/cache counters between runs."""
    from app.backtest.infra import data_loader

    data_loader.CACHE_TELEMETRY["download_count"] = 0
    data_loader.CACHE_TELEMETRY["cache_hit_count"] = 0


def _read_result() -> Dict[str, Any]:
    return json.loads(RESULT_PATH.read_text(encoding="utf-8"))


def _run_one_backtest(mode: str, data_source: str) -> Dict[str, Any]:
    """
    Run a single backtest by directly calling internal functions (Option A).
    Override data_source in-memory without touching SSOT on disk.
    """
    from app.utils.param_loader import load_params_strict
    from app.run_backtest import (
        load_price_data,
        run_backtest,
        format_result,
        atomic_write_result,
    )

    _reset_telemetry()

    params, param_source = load_params_strict()
    params["data_source"] = data_source  # in-memory override only

    today = date.today()
    if mode == "quick":
        start = today - timedelta(days=180)
    else:
        start = today - timedelta(days=365 * 3)
    end = today - timedelta(days=1)

    price_data = load_price_data(
        params["universe"], start, end, data_source=data_source
    )
    result = run_backtest(
        price_data, params, start, end, enable_regime=(mode == "full")
    )
    formatted = format_result(
        result, params, start, end, price_data=price_data, param_source=param_source
    )
    atomic_write_result(formatted)
    return _read_result()


def _extract_key_fields(r: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the specific fields needed for determinism comparison."""
    meta = r.get("meta", {})
    summary = r.get("summary", {})
    return {
        "sha256": (meta.get("param_source") or {}).get("sha256", ""),
        "universe": sorted(meta.get("universe", [])),
        "start_date": meta.get("start_date", ""),
        "end_date": meta.get("end_date", ""),
        "mode": meta.get("mode", ""),
        "total_trades": meta.get("total_trades", 0),
        "equity_curve_len": len(meta.get("equity_curve", [])),
        "total_return": summary.get("total_return", 0.0),
        "cagr": summary.get("cagr", 0.0),
        "mdd": summary.get("mdd", 0.0),
        "sharpe": summary.get("sharpe", 0.0),
        "download_count": meta.get("download_count", 0),
        "cache_hit_count": meta.get("cache_hit_count", 0),
        "fallback_count": meta.get("fallback_count", 0),
    }


# ─── Check A: Determinism ─────────────────────────────────────────────────
def check_determinism(
    results: List[Dict[str, Any]],
    tol_cagr: float,
    tol_mdd: float,
    tol_sharpe: float,
) -> Dict[str, Any]:
    """Compare N result snapshots for numeric + exact field equality."""
    if len(results) < 2:
        return {"verdict": "PASS", "note": "only 1 run, nothing to compare"}

    ref = results[0]
    mismatches = []

    exact_keys = [
        "sha256",
        "universe",
        "start_date",
        "end_date",
        "mode",
        "total_trades",
        "equity_curve_len",
    ]
    float_keys = {
        "total_return": tol_cagr,
        "cagr": tol_cagr,
        "mdd": tol_mdd,
        "sharpe": tol_sharpe,
    }

    for i, cur in enumerate(results[1:], start=2):
        for k in exact_keys:
            if ref[k] != cur[k]:
                mismatches.append(
                    {
                        "run": i,
                        "key": k,
                        "ref": ref[k],
                        "cur": cur[k],
                    }
                )
        for k, tol in float_keys.items():
            diff = abs(float(ref[k]) - float(cur[k]))
            if diff > tol:
                mismatches.append(
                    {
                        "run": i,
                        "key": k,
                        "ref": ref[k],
                        "cur": cur[k],
                        "diff": round(diff, 8),
                        "tol": tol,
                    }
                )

    verdict = "PASS" if not mismatches else "FAIL"
    out: Dict[str, Any] = {"verdict": verdict}
    if mismatches:
        out["mismatches"] = mismatches
    return out


# ─── Check B: Cache/Network ───────────────────────────────────────────────
def check_cache(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Verify that the 2nd run (and beyond) has download_count == 0.
    If run1 already has download_count==0 (pre-warmed cache), that's also PASS.
    """
    if len(results) < 2:
        return {"verdict": "PASS", "note": "only 1 run"}

    counts = [
        {
            "run": i + 1,
            "download": r["download_count"],
            "cache_hit": r["cache_hit_count"],
        }
        for i, r in enumerate(results)
    ]
    # The 2nd run onward must have download_count == 0
    violations = [c for c in counts[1:] if c["download"] != 0]
    verdict = "PASS" if not violations else "FAIL"
    out: Dict[str, Any] = {"verdict": verdict, "counts": counts}
    if violations:
        out["violations"] = violations
    return out


# ─── Check C: Cross-provider ──────────────────────────────────────────────
def check_cross_provider(
    fdr_fields: Dict[str, Any],
    yf_fields: Dict[str, Any],
) -> Dict[str, Any]:
    """Compare fdr vs yfinance results; large deviations → FAIL."""
    diffs: Dict[str, Any] = {}
    warnings: List[str] = []
    fail = False

    # equity_curve length similarity (5% threshold)
    ec_fdr = fdr_fields["equity_curve_len"]
    ec_yf = yf_fields["equity_curve_len"]
    if ec_fdr > 0 and ec_yf > 0:
        ratio = abs(ec_fdr - ec_yf) / max(ec_fdr, ec_yf)
        diffs["equity_curve_len_ratio"] = round(ratio, 4)
        if ratio > 0.05:
            fail = True
            warnings.append(f"equity_curve_len differs by {ratio:.2%}")

    # date range
    if fdr_fields["start_date"] != yf_fields["start_date"]:
        warnings.append(
            f"start_date mismatch: fdr={fdr_fields['start_date']} vs yf={yf_fields['start_date']}"
        )
    if fdr_fields["end_date"] != yf_fields["end_date"]:
        warnings.append(
            f"end_date mismatch: fdr={fdr_fields['end_date']} vs yf={yf_fields['end_date']}"
        )

    # numeric diffs with dynamic scale detection
    def _threshold(key: str, fdr_val: float, yf_val: float):
        if key in ("cagr", "mdd"):
            # If values are in 0~1 ratio scale → threshold 0.03; else percentage → 3.0
            if abs(fdr_val) < 1 and abs(yf_val) < 1:
                return 0.03
            return 3.0
        if key == "sharpe":
            return 0.5
        return 999  # no threshold

    for key in ("cagr", "mdd", "sharpe"):
        fv = float(fdr_fields[key])
        yv = float(yf_fields[key])
        diff = abs(fv - yv)
        thresh = _threshold(key, fv, yv)
        diffs[key] = {
            "fdr": round(fv, 6),
            "yfinance": round(yv, 6),
            "diff": round(diff, 6),
            "threshold": thresh,
        }
        if diff > thresh:
            fail = True
            warnings.append(f"{key} diff {diff:.6f} exceeds threshold {thresh}")

    verdict = "FAIL" if fail else "PASS"
    out: Dict[str, Any] = {"verdict": verdict, "diffs": diffs}
    if warnings:
        out["warnings"] = warnings
    return out


# ─── Main Logic ───────────────────────────────────────────────────────────
def run_verification(
    mode: str = "full",
    repeat: int = 5,
    seed: int = 42,
    provider: str = "both",
    tol_cagr: float = 0.0001,
    tol_mdd: float = 0.0001,
    tol_sharpe: float = 0.0001,
) -> Dict[str, Any]:
    """Execute full P181-R reliability verification suite."""
    now_kst = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")
    report: Dict[str, Any] = {
        "asof": now_kst,
        "ssot_path": str(SSOT_PATH),
        "repeat": repeat,
        "mode": mode,
        "seed": seed,
        "tolerances": {"cagr": tol_cagr, "mdd": tol_mdd, "sharpe": tol_sharpe},
        "providers": {},
        "overall": "PASS",
    }

    providers_to_test = []
    if provider in ("fdr", "both"):
        providers_to_test.append("fdr")
    if provider in ("yfinance", "both"):
        providers_to_test.append("yfinance")

    provider_snapshots: Dict[str, Dict[str, Any]] = {}

    for prov in providers_to_test:
        log.info(f"{'=' * 60}")
        log.info(f"[PROVIDER: {prov}] Starting {repeat} repeat runs (mode={mode})")
        log.info(f"{'=' * 60}")

        run_fields: List[Dict[str, Any]] = []
        for i in range(1, repeat + 1):
            log.info(f"  [{prov}] Run {i}/{repeat}...")
            result = _run_one_backtest(mode, prov)
            fields = _extract_key_fields(result)
            run_fields.append(fields)
            log.info(
                f"  [{prov}] Run {i}: trades={fields['total_trades']}, "
                f"cagr={fields['cagr']:.6f}, mdd={fields['mdd']:.6f}, "
                f"sharpe={fields['sharpe']:.6f}, "
                f"dl={fields['download_count']}, cache={fields['cache_hit_count']}"
            )

        # A) Determinism
        det = check_determinism(run_fields, tol_cagr, tol_mdd, tol_sharpe)

        # B) Cache
        cache = check_cache(run_fields)

        prov_report: Dict[str, Any] = {
            "determinism": det,
            "cache": cache,
            "sample_run": {
                "total_trades": run_fields[0]["total_trades"],
                "cagr": run_fields[0]["cagr"],
                "mdd": run_fields[0]["mdd"],
                "sharpe": run_fields[0]["sharpe"],
                "equity_curve_len": run_fields[0]["equity_curve_len"],
            },
        }
        report["providers"][prov] = prov_report

        # Keep last run snapshot for cross-provider comparison
        provider_snapshots[prov] = run_fields[-1]

        if det["verdict"] == "FAIL":
            report["overall"] = "FAIL"
        if cache["verdict"] == "FAIL":
            report["overall"] = "FAIL"

    # C) Cross-provider comparison
    if len(provider_snapshots) == 2:
        log.info(f"{'=' * 60}")
        log.info("[CROSS-PROVIDER] Comparing fdr vs yfinance")
        log.info(f"{'=' * 60}")

        # Detect if fdr actually fell back to yfinance
        fdr_fallback = provider_snapshots["fdr"].get("fallback_count", 0)
        if fdr_fallback > 0:
            log.warning(
                f"  [SKIP] fdr provider had {fdr_fallback} fallback(s) to yfinance. "
                f"Cross-provider comparison is meaningless (both used yfinance)."
            )
            report["cross_provider"] = {
                "verdict": "SKIP",
                "reason": f"fdr had {fdr_fallback} fallback(s) to yfinance — comparison meaningless",
            }
        else:
            cross = check_cross_provider(
                provider_snapshots["fdr"],
                provider_snapshots["yfinance"],
            )
            report["cross_provider"] = cross
            if cross["verdict"] == "FAIL":
                report["overall"] = "FAIL"
            log.info(f"  Cross-provider verdict: {cross['verdict']}")

    # Write report
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info(f"{'=' * 60}")
    log.info(f"[REPORT] Written to {REPORT_PATH}")
    log.info(f"[OVERALL] {report['overall']}")
    log.info(f"{'=' * 60}")

    return report


def main():
    parser = argparse.ArgumentParser(
        description="P181-R: Backtest Reliability Verification"
    )
    parser.add_argument("--mode", choices=["quick", "full"], default="full")
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--provider", choices=["fdr", "yfinance", "both"], default="both"
    )
    parser.add_argument("--tolerance-cagr", type=float, default=0.0001)
    parser.add_argument("--tolerance-mdd", type=float, default=0.0001)
    parser.add_argument("--tolerance-sharpe", type=float, default=0.0001)
    args = parser.parse_args()

    report = run_verification(
        mode=args.mode,
        repeat=args.repeat,
        seed=args.seed,
        provider=args.provider,
        tol_cagr=args.tolerance_cagr,
        tol_mdd=args.tolerance_mdd,
        tol_sharpe=args.tolerance_sharpe,
    )

    if report["overall"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
