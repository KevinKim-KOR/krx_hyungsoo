import argparse, json
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np

from scripts.bt.data_loader import load_benchmark

def max_drawdown(series: pd.Series) -> float:
    roll_max = series.cummax()
    dd = series / roll_max - 1.0
    return float(dd.min())

def run_strategy_ma200(kospi_close: pd.Series, kospi_ret: pd.Series) -> pd.Series:
    ma = kospi_close.rolling(200, min_periods=200).mean()
    regime = (kospi_close > ma).astype(float)     # 위면 1, 아니면 0 (현금)
    strat_ret = kospi_ret * regime
    return strat_ret

def main():
    parser = argparse.ArgumentParser(description="Backtest Runner (real data)")
    parser.add_argument("--strategy", required=True, help="예: krx_ma200")
    parser.add_argument("--benchmarks", default="KOSPI,KOSDAQ", help="예: KOSPI,S&P500")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--data_root", default=r"\\192.168.0.18\homes\Hyungsoo\krx\krx_alertor_modular\data\cache\kr")
    parser.add_argument("--out_root",  default=r"\\192.168.0.18\homes\Hyungsoo\krx\krx_alertor_modular\backtests")
    args = parser.parse_args()

    strategy = args.strategy
    benchmarks = [s.strip() for s in args.benchmarks.split(",") if s.strip()]
    start, end = args.start, args.end
    OUT_ROOT = Path(args.out_root)

    # 1) 데이터 로드
    bench_data = { name: load_benchmark(name, start, end) for name in benchmarks }
    if "KOSPI" not in bench_data and strategy.lower().startswith("krx_ma200"):
        # 전략 계산을 위해 KOSPI가 필요
        bench_data["KOSPI"] = load_benchmark("KOSPI", start, end)

    # 2) 전략 수익률 계산
    if strategy.lower() == "krx_ma200":
        kospi_df = bench_data["KOSPI"]
        strat_ret = run_strategy_ma200(kospi_df["close"], kospi_df["ret"])
    else:
        raise ValueError(f"Unsupported strategy: {strategy}")

    # 3) 벤치마크 수익률/에퀴티
    returns = pd.DataFrame({"STRAT": strat_ret})
    for b, df in bench_data.items():
        returns[b] = df["ret"]

    equity = (1 + returns).cumprod()

    # 4) 메트릭
    n_days = len(equity)
    summary = equity.iloc[-1] - 1.0
    metrics = {
        "strategy": strategy,
        "period": {"start": start, "end": end, "n_days": int(n_days)},
        "Final_Return": float(summary["STRAT"]),
        "CAGR_like": float(equity["STRAT"].iloc[-1]**(252/max(n_days,1)) - 1) if n_days > 0 else 0.0,
        "MDD": max_drawdown(equity["STRAT"]),
        "benchmarks": { b: float(summary[b]) for b in benchmarks if b in summary.index },
    }

    # 5) 출력 저장
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = OUT_ROOT / f"{ts}_{strategy}"
    run_dir.mkdir(parents=True, exist_ok=True)

    returns.to_csv(run_dir / "daily_returns.csv", encoding="utf-8-sig")
    equity.to_csv(run_dir / "equity_curve.csv", encoding="utf-8-sig")
    (run_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    # 리포트
    lines = [
        f"[REPORT] strategy={strategy}",
        f"period={start}~{end} (N={n_days} days)",
        f"Final Return: {metrics['Final_Return']:.2%}",
        f"CAGR_like: {metrics['CAGR_like']:.2%}",
        f"MDD: {metrics['MDD']:.2%}",
        "Benchmarks:",
    ] + [f"  - {b}: {metrics['benchmarks'].get(b, float('nan')):.2%}" for b in benchmarks]
    (run_dir / "report.txt").write_text("\n".join(lines), encoding="utf-8")

    # 6) PNG 차트 저장
    import matplotlib.pyplot as plt
    plt.figure()
    (equity.rename(columns={"STRAT": f"STRAT({strategy})"})).plot()   # 색상 지정 X (기본값)
    plt.title(f"Equity Curve: {strategy}")
    plt.xlabel("Date"); plt.ylabel("Growth (×)")
    plt.tight_layout()
    plt.savefig(run_dir / "equity_curve.png", dpi=150)
    plt.close()

    print("[BT] done:", run_dir)

if __name__ == "__main__":
    main()
