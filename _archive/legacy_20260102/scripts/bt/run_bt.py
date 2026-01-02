import argparse, json, sys
from datetime import datetime
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

from scripts.bt.data_loader import load_benchmark, ExternalDataUnavailable

def max_drawdown(series: pd.Series) -> float:
    roll_max = series.cummax()
    dd = series / roll_max - 1.0
    return float(dd.min())

def run_strategy_ma200(kospi_close: pd.Series, kospi_ret: pd.Series) -> pd.Series:
    ma = kospi_close.rolling(200, min_periods=200).mean()
    regime = (kospi_close > ma).astype(float)
    return kospi_ret * regime

def main():
    ap = argparse.ArgumentParser(description="Backtest Runner (skip-on-external-errors)")
    ap.add_argument("--strategy", required=True)
    ap.add_argument("--benchmarks", default="KOSPI,S&P500")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--out_root", default="backtests")
    args = ap.parse_args()

    strategy = args.strategy
    benchmarks = [s.strip() for s in args.benchmarks.split(",") if s.strip()]
    start, end = args.start, args.end
    OUT_ROOT = Path(args.out_root)

    # 필수 데이터: KOSPI
    try:
        kospi = load_benchmark("KOSPI", start, end)
    except ExternalDataUnavailable:
        print("[SKIP] external-data-unavailable: KOSPI")
        sys.exit(0)

    if strategy.lower() == "krx_ma200":
        strat_ret = run_strategy_ma200(kospi["close"], kospi["ret"])
    else:
        print(f"[SKIP] unsupported strategy: {strategy}")
        sys.exit(0)

    returns = pd.DataFrame({"STRAT": strat_ret})
    loaded_bench = []
    for b in benchmarks:
        if b.upper() == "KOSPI":
            returns["KOSPI"] = kospi["ret"]; loaded_bench.append("KOSPI"); continue
        try:
            dfb = load_benchmark(b, start, end)
            returns[b.upper()] = dfb["ret"]; loaded_bench.append(b.upper())
        except ExternalDataUnavailable:
            print(f"[WARN] benchmark unavailable: {b} (skipped)")
            continue

    if returns.empty:
        print("[SKIP] no data rows after loading")
        sys.exit(0)

    equity = (1 + returns).cumprod()
    n_days = len(equity)
    summary = equity.iloc[-1] - 1.0
    final = float(summary["STRAT"])
    cagr = float(equity["STRAT"].iloc[-1]**(252/max(n_days,1)) - 1) if n_days > 0 else 0.0
    mdd  = max_drawdown(equity["STRAT"])

    metrics = {
        "strategy": strategy,
        "period": {"start": start, "end": end, "n_days": int(n_days)},
        "Final_Return": final,
        "CAGR_like": cagr,
        "MDD": mdd,
        "benchmarks": { b: float(summary[b]) for b in loaded_bench if b in summary.index },
    }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = OUT_ROOT / f"{ts}_{strategy}"
    run_dir.mkdir(parents=True, exist_ok=True)

    returns.to_csv(run_dir / "daily_returns.csv", encoding="utf-8-sig")
    equity.to_csv(run_dir / "equity_curve.csv", encoding="utf-8-sig")
    (run_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    plt.figure()
    equity.rename(columns={"STRAT": f"STRAT({strategy})"}).plot()
    plt.title(f"Equity Curve: {strategy}")
    plt.xlabel("Date"); plt.ylabel("Growth (×)")
    plt.tight_layout()
    plt.savefig(run_dir / "equity_curve.png", dpi=150)
    plt.close()

    print("[BT] done:", run_dir)

if __name__ == "__main__":
    main()
