"""JSON I/O, 파라미터 저장, SSOT 적용 유틸리티."""

import json
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

from pc_cockpit.services.config import (
    KST,
    LATEST_PATH,
    SNAPSHOT_DIR,
    PORTFOLIO_PATH,
)


def load_json(path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def save_json(path, data):
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    path.write_text(json_str, encoding="utf-8")


def save_params(data):
    save_json(LATEST_PATH, data)
    KST_local = timezone(timedelta(hours=9))
    timestamp = datetime.now(KST_local).strftime("%Y%m%d_%H%M%S")
    snapshot_path = SNAPSHOT_DIR / f"strategy_params_{timestamp}.json"
    save_json(snapshot_path, data)
    return snapshot_path


def apply_tune_best_params_to_ssot(best_params):
    params_data = load_json(LATEST_PATH)
    if not params_data:
        raise ValueError("현재 SSOT 파라미터를 읽을 수 없습니다.")
    if not best_params:
        raise ValueError("튜닝 1등 파라미터가 없습니다.")

    target_params = params_data.setdefault("params", {})
    target_params.setdefault("lookbacks", {})["momentum_period"] = int(
        best_params["momentum_period"]
    )
    target_params.setdefault("lookbacks", {})["volatility_period"] = int(
        best_params["volatility_period"]
    )
    target_params.setdefault("decision_params", {})["entry_threshold"] = float(
        best_params["entry_threshold"]
    )
    target_params.setdefault("decision_params", {})["exit_threshold"] = float(
        best_params["stop_loss"]
    )
    target_params.setdefault("position_limits", {})["max_positions"] = int(
        best_params["max_positions"]
    )
    params_data["asof"] = datetime.now(KST).isoformat()
    save_params(params_data)
    return params_data


def load_portfolio():
    if PORTFOLIO_PATH.exists():
        try:
            return json.loads(PORTFOLIO_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def apply_reco(current_params, candidate):
    new_data = current_params.copy()
    KST_local = timezone(timedelta(hours=9))
    new_data["asof"] = datetime.now(KST_local).isoformat()

    cp = candidate["params"]
    target_p = new_data["params"]

    if "momentum_window" in cp:
        target_p["lookbacks"]["momentum_period"] = cp["momentum_window"]
    if "vol_window" in cp:
        target_p["lookbacks"]["volatility_period"] = cp["vol_window"]
    if "top_k" in cp:
        target_p["position_limits"]["max_positions"] = cp["top_k"]

    if "weights" in cp:
        target_p["decision_params"]["weight_momentum"] = cp["weights"]["mom"]
        target_p["decision_params"]["weight_volatility"] = cp["weights"]["vol"]

    new_data["params"] = target_p
    return new_data


def run_script(script_path):
    try:
        result = subprocess.run(
            ["powershell", "-File", str(script_path)], capture_output=True, text=True
        )
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        return "", str(e), -1
