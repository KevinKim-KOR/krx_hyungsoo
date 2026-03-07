import argparse
import sys
import json
from pathlib import Path
import math

# Add the project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.run_backtest import run_cli_backtest

def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def run_reliability_check(mode: str, repeat: int):
    print(f"Starting Reliability Check (mode={mode}, repeat={repeat})")
    
    results = []
    
    for i in range(repeat):
        print(f"\\n--- Run {i+1}/{repeat} ---")
        # Run directly without subprocess
        success = run_cli_backtest(mode=mode)
        if not success:
            print(f"Run {i+1} failed.")
            sys.exit(1)
            
        # Read the generated result
        result_path = Path("reports/backtest/latest/backtest_result.json")
        data = load_json(result_path)
        
        meta = data.get("meta", {})
        summary = data.get("summary", {})
        
        # Collect key metrics
        record = {
            "run": i + 1,
            "params_used": meta.get("params_used"),
            "sha256": meta.get("param_source", {}).get("sha256"),
            "universe": meta.get("universe"),
            "total_trades": meta.get("total_trades"),
            "equity_curve_length": len(meta.get("equity_curve", [])),
            "summary_cagr": summary.get("cagr"),
            "summary_mdd": summary.get("mdd"),
            "summary_total_return": summary.get("total_return")
        }
        
        # Sanity Checks
        equity_curve = meta.get("equity_curve", [])
        if equity_curve:
            initial_equity = equity_curve[0].get("equity")
            final_equity = equity_curve[-1].get("equity")
            
            # Check 1: Initial capital is 10,000,000
            sane_capital = math.isclose(initial_equity, 10_000_000, rel_tol=1e-5)
            
            # Check 2: total_return matches curve
            calc_return = ((final_equity / initial_equity) - 1) * 100 if initial_equity else 0
            sane_return = math.isclose(summary.get("total_return", 0), calc_return, abs_tol=0.1)
            
            record["sanity_initial_capital"] = sane_capital
            record["sanity_total_return"] = sane_return
        else:
            record["sanity_initial_capital"] = False
            record["sanity_total_return"] = False
            
        results.append(record)
        print(f"Run {i+1} summary: Trades={record['total_trades']}, Return={record['summary_total_return']:.2f}%")

    print("\\n=== Reliability Summary ===")
    
    # Check if all runs are perfectly identical
    first_run = results[0]
    keys_to_compare = [
        "params_used", "sha256", "universe", "total_trades",
        "equity_curve_length", "summary_cagr", "summary_mdd", "summary_total_return"
    ]
    
    is_identical = True
    for idx, r in enumerate(results[1:]):
        for k in keys_to_compare:
            if r[k] != first_run[k]:
                print(f"Mismatch in Run {idx+2} for key '{k}': {r[k]} != {first_run[k]}")
                is_identical = False

    sanity_pass = all(r.get("sanity_initial_capital") and r.get("sanity_total_return") for r in results)

    final_pass = is_identical and sanity_pass
    
    print(f"Identical Outputs: {'PASS' if is_identical else 'FAIL'}")
    print(f"Sanity Checks: {'PASS' if sanity_pass else 'FAIL'}")
    print(f"Overall Result: {'PASS' if final_pass else 'FAIL'}")
    
    output_data = {
        "mode": mode,
        "repeat": repeat,
        "is_identical": is_identical,
        "sanity_pass": sanity_pass,
        "runs": results
    }
    
    out_path = Path("reports/backtest/latest/reliability_check.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
        
    print(f"\\nDetails saved to: {out_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser("Backtest Reliability Checker")
    parser.add_argument("--mode", choices=["quick", "full"], default="quick", help="Backtest mode")
    parser.add_argument("--repeat", type=int, default=3, help="Number of times to run the backtest")
    args = parser.parse_args()
    
    run_reliability_check(args.mode, args.repeat)
