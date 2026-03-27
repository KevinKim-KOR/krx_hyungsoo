"""Tuning result export helpers (CSV rows, validation metadata)."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

KST = timezone(timedelta(hours=9))


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _build_top_trial_rows(
    sorted_trials: List[Any], top_n: int = 20
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for rank, trial in enumerate(sorted_trials[:top_n], start=1):
        attrs = trial.user_attrs
        rows.append(
            {
                "rank": rank,
                "trial": trial.number,
                "score": round(_to_float(trial.value), 6),
                "momentum_period": trial.params.get("momentum_period"),
                "volatility_period": trial.params.get("volatility_period"),
                "entry_threshold": _to_float(trial.params.get("entry_threshold")),
                "stop_loss": _to_float(trial.params.get("stop_loss")),
                "max_positions": trial.params.get("max_positions"),
                "cagr_full": round(_to_float(attrs.get("cagr")), 6),
                "mdd_full": round(_to_float(attrs.get("mdd_pct")), 6),
                "sharpe_full": round(_to_float(attrs.get("sharpe")), 6),
                "cagr_agg": round(_to_float(attrs.get("cagr_agg")), 6),
                "mdd_agg": round(_to_float(attrs.get("mdd_agg")), 6),
                "sharpe_agg": round(_to_float(attrs.get("sharpe_agg")), 6),
                "overfit_penalty": round(_to_float(attrs.get("overfit_penalty")), 6),
                "worst_segment": attrs.get("worst_segment", "N/A"),
                "hard_penalty_triggered": bool(
                    attrs.get("hard_penalty_triggered", False)
                ),
            }
        )
    return rows


def _rows_to_csv(fieldnames: List[str], rows: List[Dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    return buffer.getvalue()


def _build_best_segment_rows(segment_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    full_metrics = segment_data.get("full_period_metrics", {})
    rows.append(
        {
            "segment": "FULL",
            "cagr": round(_to_float(full_metrics.get("cagr")), 6),
            "mdd": round(_to_float(full_metrics.get("mdd")), 6),
            "sharpe": round(_to_float(full_metrics.get("sharpe")), 6),
            "days": full_metrics.get("days", 0),
        }
    )
    segment_metrics = segment_data.get("segment_metrics", {})
    for segment_name in ["SEG_1", "SEG_2", "SEG_3"]:
        metrics = segment_metrics.get(segment_name, {})
        rows.append(
            {
                "segment": segment_name,
                "cagr": round(_to_float(metrics.get("cagr")), 6),
                "mdd": round(_to_float(metrics.get("mdd")), 6),
                "sharpe": round(_to_float(metrics.get("sharpe")), 6),
                "days": metrics.get("days", 0),
            }
        )
    return rows


def _format_file_timestamp(path: Path) -> str:
    modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=KST)
    return modified_at.strftime("%Y-%m-%dT%H:%M:%S+09:00")


def _build_validation_pack_metadata(
    paths: Dict[str, Path],
) -> Dict[str, Dict[str, Any]]:
    file_meta: Dict[str, Dict[str, Any]] = {}
    for key, path in paths.items():
        exists = path.exists()
        file_meta[key] = {
            "path": str(path),
            "exists": exists,
            "updated_at": _format_file_timestamp(path) if exists else None,
        }
    return file_meta
