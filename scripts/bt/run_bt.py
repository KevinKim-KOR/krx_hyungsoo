import argparse, json, time
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np

# === 1) 인자 파싱 ===
parser = argparse.ArgumentParser(description="Simple Backtest Runner (skeleton)")
parser.add_argument("--strategy", required=True, help="전략명 (예: krx_ma200)")
parser.add_argument("--benchmarks", default="KOSPI,KOSDAQ", help="쉼표구분 벤치마크 (예: KOSPI,S&P500)")
parser.add_argument("--start", required=True, help="YYYY-MM-DD")
parser.add_argument("--end", required=True, help="YYYY-MM-DD")
parser.add_argument("--data_root", default=r"\\192.168.0.18\homes\Hyungsoo\krx\krx_alertor_modular\data\cache\kr")
parser.add_argument("--out_root", default=r"\\192.168.0.18\homes\Hyungsoo\krx\krx_alertor_modular\backtests")
args = parser.parse_args()

strategy = args.strategy
benchmarks = [s.strip() for s in args.benchmarks.split(",") if s.strip()]
start, end = args.start, args.end
DATA_ROOT = Path(args.data_root)
OUT_ROOT = Path(args.out_root)

# === 2) 출력 디렉토리 만들기 ===
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
run_dir = OUT_ROOT / f"{ts}_{strategy}"
run_dir.mkdir(parents=True, exist_ok=True)

# === 3) (데이터 로딩: 스켈레톤) ===
# 실제로는 티커/지수별 CSV/Parquet/DB에서 읽어옵니다.
# 여기서는 샘플 난수 수익률로 러너 흐름만 검증합니다.
dates = pd.date_range(start=start, end=end, freq="B")  # 영업일 가정(평일)
np.random.seed(42)
returns = pd.DataFrame({ "STRAT": np.random.normal(0.0005, 0.01, len(dates)) }, index=dates)
for b in benchmarks:
    returns[b] = np.random.normal(0.0003, 0.008, len(dates))

# === 4) 전략/벤치마크 누적수익 계산 ===
equity = (1 + returns).cumprod()
summary = equity.iloc[-1] - 1.0  # 기간 누적수익률

# 간단 지표
def max_drawdown(series: pd.Series) -> float:
    roll_max = series.cummax()
    dd = series/roll_max - 1.0
    return dd.min()

metrics = {
    "strategy": strategy,
    "period": {"start": start, "end": end, "n_days": len(dates)},
    "CAGR_like": (equity["STRAT"].iloc[-1]**(252/len(dates))) - 1 if len(dates) > 0 else 0,
    "MDD": float(max_drawdown(equity["STRAT"])),
    "Final_Return": float(summary["STRAT"]),
    "benchmarks": { b: float(summary[b]) for b in benchmarks },
}

# === 5) 저장 ===
equity.to_csv(run_dir / "equity_curve.csv", encoding="utf-8-sig")
returns.to_csv(run_dir / "daily_returns.csv", encoding="utf-8-sig")
(Path(run_dir / "metrics.json")).write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

# 간단 리포트 텍스트
report = [
    f"[REPORT] strategy={strategy}",
    f"period={start}~{end} (N={len(dates)} days)",
    f"Final Return: {metrics['Final_Return']:.2%}",
    f"CAGR_like: {metrics['CAGR_like']:.2%}",
    f"MDD: {metrics['MDD']:.2%}",
    "Benchmarks:",
] + [f"  - {b}: {metrics['benchmarks'][b]:.2%}" for b in benchmarks]
(Path(run_dir / "report.txt")).write_text("\n".join(report), encoding="utf-8")

print("[BT] done:", run_dir)
