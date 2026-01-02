# -*- coding: utf-8 -*-
"""
tools/run_phase30_final.py

Phase 3: Gate 3 - Final Test Unsealing
(Test 봉인 해제 및 최종 보고서 생성)
"""
import sys
import argparse
import json
import logging
from pathlib import Path
from datetime import date
import pandas as pd

# Force UTF-8 logging
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

try:
    from extensions.tuning.runner import run_backtest_for_final
    from extensions.tuning.types import BacktestRunResult, DEFAULT_COSTS, DataConfig
    from extensions.tuning.split import SplitConfig
    from extensions.tuning.split import SplitConfig
    from extensions.tuning.manifest import create_manifest, save_manifest
except Exception:
    import traceback
    traceback.print_exc()
    print("CRITICAL IMPORT ERROR")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_manifest(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def run_gate3(manifest_path: str, unseal_acknowledged: bool):
    print("="*60)
    print("Phase 3: Gate 3 - Final Test Unsealing")
    print("="*60)

    if not unseal_acknowledged:
        print("❌ ERROR: Test Data is SEALED.")
        print("To unseal, you must provide the flag: --i-acknowledge-test-unsealing")
        sys.exit(1)

    # 1. Manifest 로드
    print(f"Loading manifest: {manifest_path}")
    manifest = load_manifest(manifest_path)
    
    # Validation
    stage = manifest.get("stage")
    if stage not in ["gate2", "gate1"]: # Gate1에서 바로 올 수도 있음 (Analysis mode)
        print(f"⚠️ Warning: Manifest stage is '{stage}'. Expected 'gate2'.")

    # 2. 파라미터 및 설정 복원
    # Manifest 구조에 따라 다름. 여기서는 v4.1/v2.2 표준 가정
    # results -> best_trial -> params
    best_trial = manifest["results"]["best_trial"]
    params = best_trial["params"]
    
    # Data Config 복원
    data_conf_dict = manifest.get("data", {})
    data_config = DataConfig(
        data_version=data_conf_dict.get("data_version", ""),
        universe_version=data_conf_dict.get("universe_version", ""),
    )
    
    # Period 복원
    start_date = date.fromisoformat(manifest["period"]["start_date"])
    end_date = date.fromisoformat(manifest["period"]["end_date"])
    
    # Universe 복원 (해시 검증은 생략, 실제 실행 위해 코드 필요)
    # Manifest에는 sample만 있을 수 있음.
    # 실데이터 실행이면 Universe 로더 사용 필요.
    # 여기서는 data_config에 universe 정보가 충분치 않을 수 있으므로,
    # "실행 환경에서의 Universe 로드"를 시도.
    
    # 만약 mock이면?
    is_mock = "mock" in data_config.data_version
    if is_mock:
        universe_codes = ["005930", "000660", "035420", "005380", "051910"] # MOCK
        # Mock Calendar
        from datetime import timedelta
        trading_calendar = []
        curr = start_date
        while curr <= end_date:
            if curr.weekday() < 5:
                trading_calendar.append(curr)
            curr += timedelta(days=1)
    else:
        # Real Data
        from core.data.filtering import get_filtered_universe
        from infra.data.loader import load_trading_calendar
        
        universe_codes = get_filtered_universe()
        trading_calendar = load_trading_calendar(start_date, end_date)
        
    print(f"Restored Params: {params}")
    print(f"Period: {start_date} ~ {end_date}")
    
    # 3. Final Backtest 실행 (Test 포함)
    result = run_backtest_for_final(
        params=params,
        start_date=start_date,
        end_date=end_date,
        lookback_months=best_trial.get("debug", {}).get("min_lookback_months", 6), # Default 6
        trading_calendar=trading_calendar,
        split_config=SplitConfig(), # Default
        costs=DEFAULT_COSTS,
        data_config=data_config,
        universe_codes=universe_codes,
    )
    
    # 4. 결과 출력
    train_m = result.metrics["train"]
    val_m = result.metrics["val"]
    test_m = result.metrics["test"]
    
    print("\n" + "-"*60)
    print("FINAL RESULTS (UNSEALED)")
    print("-"*60)
    print(f"{'Metric':<15} {'Train':<10} {'Val':<10} {'Test (FINAL)':<15}")
    print("-"*60)
    print(f"{'Sharpe':<15} {train_m.sharpe:<10.2f} {val_m.sharpe:<10.2f} {test_m.sharpe:<15.2f}")
    print(f"{'CAGR':<15} {train_m.cagr*100:<10.1f}% {val_m.cagr*100:<10.1f}% {test_m.cagr*100:<15.1f}%")
    print(f"{'MDD':<15} {train_m.mdd*100:<10.1f}% {val_m.mdd*100:<10.1f}% {test_m.mdd*100:<15.1f}%")
    print("-"*60)
    
    # Overfitting Check
    degradation = (train_m.sharpe - test_m.sharpe) / abs(train_m.sharpe) if train_m.sharpe != 0 else 0
    print(f"Degradation (Train->Test): {degradation*100:.1f}%")
    if degradation > 0.3:
        print("⚠️ WARNING: Significant overfitting detected (>30% degradation)")
    else:
        print("✅ STABLE: Degradation within acceptable range")
        
    # 5. Manifest 생성 (Final Stage)
    # 기존 manifest 정보를 바탕으로 업데이트
    # create_manifest를 다시 호출하되, stage="final"
    
    # result를 최신으로 교체 (Test 포함)
    final_manifest = create_manifest(
        stage="final",
        start_date=start_date,
        end_date=end_date,
        lookbacks=[], # Not needed for final
        trials=1,
        split_config=SplitConfig(),
        costs=DEFAULT_COSTS,
        data_config=data_config,
        param_ranges={}, # Fixed
        best_result=result, # ✅ Updated result with test
        all_trials_count=1,
        random_seed=0,
        # WF info copy from old manifest if available
        # ... (생략 for brevity, but should copy)
        guardrail_preset=manifest.get("metadata", {}).get("guardrail_preset", "unknown")
    )
    
    # 기존 메타데이터 보존
    final_manifest.to_dict()["previous_stage_data"] = manifest
    
    output_dir = Path(manifest_path).parent
    saved_path = save_manifest(final_manifest, output_dir)
    print(f"\nSaved Final Manifest: {saved_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, help="Path to Gate 2 manifest")
    parser.add_argument("--i-acknowledge-test-unsealing", action="store_true", help="Ack required")
    
    args = parser.parse_args()
    
    import traceback
    try:
        run_gate3(args.manifest, args.i_acknowledge_test_unsealing)
    except Exception:
        traceback.print_exc()
