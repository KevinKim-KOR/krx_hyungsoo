"""승격 판정 계산 (cockpit 로컬 I/O wrapper)."""

from datetime import datetime

from app.tuning.promotion_verdict_core import (
    compute_promotion_verdict,
    render_promotion_verdict_md,
)
from pc_cockpit.services.config import KST, BASE_DIR, LATEST_PATH
from pc_cockpit.services.json_io import load_json, save_json


def _promotion_verdict_paths():
    tuning_dir = BASE_DIR / "reports" / "tuning"
    return {
        "json": tuning_dir / "promotion_verdict.json",
        "md": tuning_dir / "promotion_verdict.md",
        "backtest": (
            BASE_DIR / "reports" / "backtest" / "latest" / "backtest_result.json"
        ),
    }


def refresh_promotion_verdict_local(tune_data):
    paths = _promotion_verdict_paths()
    backtest_data = load_json(paths["backtest"]) or {}
    params_data = load_json(LATEST_PATH) or {}

    verdict_payload = compute_promotion_verdict(
        tune_data=tune_data,
        backtest_data=backtest_data,
        params_data=params_data,
    )

    verdict_payload["asof"] = datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S+09:00")

    save_json(paths["json"], verdict_payload)
    paths["md"].write_text(
        render_promotion_verdict_md(verdict_payload), encoding="utf-8"
    )
    return verdict_payload
