"""POC2 — ML Baseline Evidence Draft Integration (2026-06-11).

GenerateDraft 가 저장된 ML baseline v0 룩백 report 를 보조 evidence 로 읽어
draft_payload 의 `ml_baseline_evidence_snapshot` 키에 채워 넣는다.

본 모듈은 **읽기 전용** 이다. 다음을 절대 수행하지 않는다:
- baseline 재계산 / feature 재생성 / ML 학습 / 외부 source 호출.
- 매수/매도/현금비중/조정장/위험 threshold 판단.

사용자 결정 (2026-06-11):
- report 경로는 `state/ml/ml_baseline_v0_report_latest.json` 직접 read
  (HTTP self-call 사용 안 함).
- stale 기준 = `feature_asof_range.end` 가 오늘(KST) 대비 7일 초과.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

BASELINE_REPORT_PATH = Path("state/ml/ml_baseline_v0_report_latest.json")
STALE_DAYS_THRESHOLD = 7
JUDGMENT_LABEL = "ML baseline 룩백 evidence"

EXTERNAL_CONTEXT_CHECKLIST: list[str] = [
    "CNN Fear & Greed 현재 수준",
    "VIX 또는 VKOSPI 유사 변동성 지표",
    "원유 가격 급등 여부",
    "USD/KRW 환율 급등 여부",
    "미국장 / 미국 선물 흐름",
    "중동 / 이란 / 트럼프 관련 지정학 이벤트",
    "한국장 영향 업종 (에너지 / 방산 / 항공 / 해운 / 반도체)",
]

DEFAULT_LIMITATION = "평가 기간이 짧을 수 있어 장기 안정성 검증은 아닙니다."


def _load_report(path: Path = BASELINE_REPORT_PATH) -> tuple[Optional[dict], str]:
    """저장된 report 를 read. baseline 재계산 / 외부 호출 X.

    Returns: (report_dict | None, load_status)
      load_status ∈ {"ok", "unavailable", "error"}.
    """
    if not path.exists():
        return None, "unavailable"
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"ml_baseline report 읽기 실패: {e}")
        return None, "error"
    if not isinstance(data, dict):
        return None, "error"
    return data, "ok"


def _today_kst() -> date:
    kst = timezone(timedelta(hours=9))
    return datetime.now(kst).date()


def _is_stale(feature_end: Any, today: Optional[date] = None) -> bool:
    """feature_asof_range.end 가 오늘 대비 STALE_DAYS_THRESHOLD 일 초과면 stale."""
    if not isinstance(feature_end, str) or not feature_end.strip():
        return False
    try:
        end = date.fromisoformat(feature_end)
    except ValueError:
        return False
    ref = today or _today_kst()
    return (ref - end).days > STALE_DAYS_THRESHOLD


def _candidate_summary(cand: dict[str, Any]) -> dict[str, Any]:
    top_ret = cand.get("top_group_avg_future_return") or {}
    median = cand.get("universe_median_future_return") or {}
    hit = cand.get("hit_rate") or {}
    rank = cand.get("rank_correlation") or {}

    def _g(d, k):
        v = d.get(k) if isinstance(d, dict) else None
        return v if isinstance(v, (int, float)) else None

    return {
        "status": cand.get("status"),
        "evaluated_days": cand.get("evaluated_days"),
        "evaluated_ticker_count": cand.get("evaluated_ticker_count"),
        "top_group_quantile": cand.get("top_group_quantile"),
        "top_group_avg_future_return": {
            "5d": _g(top_ret, "5d"),
            "10d": _g(top_ret, "10d"),
            "20d": _g(top_ret, "20d"),
        },
        "universe_median_future_return": {
            "5d": _g(median, "5d"),
            "10d": _g(median, "10d"),
            "20d": _g(median, "20d"),
        },
        "hit_rate": {
            "5d": _g(hit, "5d"),
            "10d": _g(hit, "10d"),
            "20d": _g(hit, "20d"),
        },
        "rank_correlation": {
            "5d": _g(rank, "5d"),
            "10d": _g(rank, "10d"),
            "20d": _g(rank, "20d"),
        },
    }


def _risk_summary(risk: dict[str, Any]) -> dict[str, Any]:
    high_dd = risk.get("high_risk_group_future_drawdown") or {}
    low_dd = risk.get("low_risk_group_future_drawdown") or {}
    capture = risk.get("drawdown_capture_rate") or {}

    def _g(d, k):
        v = d.get(k) if isinstance(d, dict) else None
        return v if isinstance(v, (int, float)) else None

    return {
        "status": risk.get("status"),
        "evaluated_days": risk.get("evaluated_days"),
        "high_risk_group_future_drawdown": {
            "5d": _g(high_dd, "5d"),
            "10d": _g(high_dd, "10d"),
        },
        "low_risk_group_future_drawdown": {
            "5d": _g(low_dd, "5d"),
            "10d": _g(low_dd, "10d"),
        },
        "drawdown_capture_rate": {
            "5d": _g(capture, "5d"),
            "10d": _g(capture, "10d"),
        },
    }


def _leakage_summary(leakage: dict[str, Any]) -> dict[str, Any]:
    return {
        "future_data_leakage_detected": bool(
            leakage.get("feature_future_data_leakage_detected")
        ),
        "tail_excluded": bool(leakage.get("target_horizon_short_tail_excluded")),
        "time_order_preserved": bool(leakage.get("time_order_preserved")),
    }


def build_ml_baseline_evidence_snapshot(
    *,
    report_path: Optional[Path] = None,
    today: Optional[date] = None,
) -> dict[str, Any]:
    """draft_payload.ml_baseline_evidence_snapshot 본문 생성.

    실패해도 draft 생성은 실패하지 않는다 — 항상 dict 반환.

    status 결정:
    - unavailable: report 파일 없음.
    - error: report 손상 또는 report.status="error" / errors 존재.
    - stale: feature_asof_range.end 가 STALE_DAYS_THRESHOLD 초과.
    - warn: report.status="warn" / "insufficient_history".
    - ok: 그 외.
    """
    # report_path 를 매번 모듈 속성에서 lookup — monkeypatch 호환.
    effective_path = report_path if report_path is not None else BASELINE_REPORT_PATH
    report, load_status = _load_report(effective_path)
    report_path = effective_path

    base_external = list(EXTERNAL_CONTEXT_CHECKLIST)
    if load_status == "unavailable":
        return {
            "status": "unavailable",
            "report_status": "unavailable",
            "report_path": str(report_path),
            "report_generated_at": None,
            "feature_asof_range": None,
            "evaluated_asof_range": None,
            "candidate_summary": None,
            "risk_summary": None,
            "leakage_summary": None,
            "limitations": [
                "ML baseline 룩백 report 가 아직 생성되지 않았습니다 "
                "(CLI 'python scripts/run_ml_baseline_v0.py' 미실행).",
                DEFAULT_LIMITATION,
            ],
            "external_context_checklist": base_external,
            "message": "ML baseline evidence 는 현재 사용할 수 없습니다.",
        }
    if load_status == "error" or report is None:
        return {
            "status": "error",
            "report_status": "error",
            "report_path": str(report_path),
            "report_generated_at": None,
            "feature_asof_range": None,
            "evaluated_asof_range": None,
            "candidate_summary": None,
            "risk_summary": None,
            "leakage_summary": None,
            "limitations": [
                "ML baseline report 파일이 손상되어 읽을 수 없습니다.",
                DEFAULT_LIMITATION,
            ],
            "external_context_checklist": base_external,
            "message": "ML baseline report 파일 손상.",
        }

    report_status = report.get("status") or "ok"
    feature_range = (
        report.get("feature_asof_range")
        if isinstance(report.get("feature_asof_range"), dict)
        else None
    )
    evaluated_range = (
        report.get("evaluated_asof_range")
        if isinstance(report.get("evaluated_asof_range"), dict)
        else None
    )

    cand = (
        report.get("candidate_baseline")
        if isinstance(report.get("candidate_baseline"), dict)
        else {}
    )
    risk = (
        report.get("risk_baseline")
        if isinstance(report.get("risk_baseline"), dict)
        else {}
    )
    leak = (
        report.get("leakage_checks")
        if isinstance(report.get("leakage_checks"), dict)
        else {}
    )

    candidate_summary = _candidate_summary(cand)
    risk_summary = _risk_summary(risk)
    leakage_summary = _leakage_summary(leak)

    # status 판정.
    feature_end = feature_range.get("end") if isinstance(feature_range, dict) else None
    stale = _is_stale(feature_end, today=today)
    errors = report.get("errors") or []
    if isinstance(errors, list) and errors:
        status = "error"
    elif report_status == "error":
        status = "error"
    elif stale:
        status = "stale"
    elif report_status in ("warn", "insufficient_history"):
        status = "warn"
    else:
        status = "ok"

    limitations: list[str] = []
    if stale:
        limitations.append(
            "ML baseline report 가 최신 시장 데이터보다 7거래일 이상 오래되었습니다 — "
            "해석 시 주의가 필요합니다."
        )
    eval_days = (
        evaluated_range.get("evaluated_days")
        if isinstance(evaluated_range, dict)
        else None
    )
    if isinstance(eval_days, int) and eval_days < 60:
        limitations.append(
            f"평가 거래일이 {eval_days}일로 짧아 장기 안정성 검증은 아닙니다."
        )
    if not limitations:
        limitations.append(DEFAULT_LIMITATION)

    return {
        "status": status,
        "report_status": report_status,
        "report_path": str(report_path),
        "report_generated_at": report.get("generated_at"),
        "feature_asof_range": feature_range,
        "evaluated_asof_range": evaluated_range,
        "candidate_summary": candidate_summary,
        "risk_summary": risk_summary,
        "leakage_summary": leakage_summary,
        "limitations": limitations,
        "external_context_checklist": base_external,
        "message": None,
    }


def _fmt_pct(v: Any) -> Optional[str]:
    if not isinstance(v, (int, float)):
        return None
    return f"{v * 100:+.2f}%"


def _candidate_evidence_line(snapshot: dict[str, Any]) -> Optional[str]:
    cand = snapshot.get("candidate_summary")
    if not isinstance(cand, dict):
        return None
    eval_days = cand.get("evaluated_days")
    top20 = cand.get("top_group_avg_future_return", {}).get("20d")
    med20 = cand.get("universe_median_future_return", {}).get("20d")
    rc20 = cand.get("rank_correlation", {}).get("20d")
    parts = []
    if isinstance(eval_days, int) and eval_days > 0:
        parts.append(f"평가 {eval_days}거래일")
    top_str = _fmt_pct(top20)
    med_str = _fmt_pct(med20)
    if top_str and med_str:
        parts.append(
            f"후보 발굴 baseline: 과거 top group 의 이후 20d 평균 {top_str} "
            f"vs universe median {med_str}"
        )
    elif top_str:
        parts.append(f"후보 발굴 baseline: 과거 top group 의 이후 20d 평균 {top_str}")
    if isinstance(rc20, (int, float)):
        parts.append(f"rank correlation {rc20:+.3f}")
    if not parts:
        return None
    return "; ".join(parts)


def _risk_evidence_line(snapshot: dict[str, Any]) -> Optional[str]:
    risk = snapshot.get("risk_summary")
    if not isinstance(risk, dict):
        return None
    high10 = risk.get("high_risk_group_future_drawdown", {}).get("10d")
    low10 = risk.get("low_risk_group_future_drawdown", {}).get("10d")
    cap10 = risk.get("drawdown_capture_rate", {}).get("10d")
    parts = []
    high_str = _fmt_pct(high10)
    low_str = _fmt_pct(low10)
    if high_str and low_str:
        parts.append(
            f"위험 baseline: 과거 high-risk bucket 의 이후 10d drawdown {high_str} "
            f"vs low-risk {low_str}"
        )
    if isinstance(cap10, (int, float)):
        parts.append(f"drawdown_capture_rate {cap10:.2f}")
    if not parts:
        return None
    return "; ".join(parts)


def _leakage_evidence_line(snapshot: dict[str, Any]) -> Optional[str]:
    leak = snapshot.get("leakage_summary")
    if not isinstance(leak, dict):
        return None
    if leak.get("future_data_leakage_detected"):
        return "leakage check: future data leakage 감지 — 해석 주의"
    return "leakage check: future data leakage 없음"


def build_ml_baseline_evidence_bullet(snapshot: Any) -> Optional[str]:
    """draft_message 의 [판단 사유] 섹션에 들어갈 1줄.

    snapshot 이 unavailable/error 면 안내 문구 1줄 (조용히 빠지지 않음).
    """
    if not isinstance(snapshot, dict):
        return None
    status = snapshot.get("status")
    report_status = snapshot.get("report_status")
    if status == "unavailable":
        return f"- {JUDGMENT_LABEL}: 현재 사용할 수 없습니다 (report 미생성)."
    if status == "error":
        return f"- {JUDGMENT_LABEL}: report 파일이 손상되어 해석할 수 없습니다."
    parts: list[str] = []
    parts.append(f"상태 {status}")
    if report_status and report_status != status:
        parts.append(f"report_status={report_status}")
    cand_line = _candidate_evidence_line(snapshot)
    if cand_line:
        parts.append(cand_line)
    risk_line = _risk_evidence_line(snapshot)
    if risk_line:
        parts.append(risk_line)
    leak_line = _leakage_evidence_line(snapshot)
    if leak_line:
        parts.append(leak_line)
    limitations = snapshot.get("limitations")
    if isinstance(limitations, list) and limitations:
        parts.append(f"한계: {limitations[0]}")
    body = " | ".join(parts)
    return f"- {JUDGMENT_LABEL}: {body}"


def build_ml_baseline_evidence_factor_signal(
    snapshot: Any,
    *,
    asof_iso: str,
) -> Optional[dict[str, Any]]:
    """draft_payload.factor_signals 에 추가할 signal 1건.

    scope="ml_baseline_evidence". snapshot status 와 관계없이 항상 signal 생성
    (지시문 §4.7: "조용히 빠지면 안 된다").
    """
    if not isinstance(snapshot, dict):
        return None
    bullet = build_ml_baseline_evidence_bullet(snapshot)
    if bullet is None:
        return None
    sep = ": "
    reason_text = bullet.split(sep, 1)[1] if sep in bullet else bullet
    is_available = snapshot.get("status") not in ("unavailable", "error")
    return {
        "factor_id": "ml_baseline_evidence",
        "factor_name": JUDGMENT_LABEL,
        "scope": "ml_baseline_evidence",
        "is_available": is_available,
        "value": None,
        "unit": "",
        "reason_text": reason_text if is_available else None,
        "fallback_text": reason_text if not is_available else None,
        "input_basis": {
            "report_status": snapshot.get("report_status"),
            "report_path": snapshot.get("report_path"),
            "report_generated_at": snapshot.get("report_generated_at"),
            "feature_asof_range": snapshot.get("feature_asof_range"),
            "evaluated_asof_range": snapshot.get("evaluated_asof_range"),
        },
        "computed_at": asof_iso,
    }


def render_ml_baseline_evidence_bullet(payload: Any) -> Optional[str]:
    """draft_message 가 호출 — factor_signals 에서 scope="ml_baseline_evidence"
    signal 의 reason_text/fallback_text 를 추출해 [판단 사유] bullet 1줄로 반환.
    """
    if not isinstance(payload, dict):
        return None
    factor_signals = payload.get("factor_signals")
    if not isinstance(factor_signals, list):
        return None
    for sig in factor_signals:
        if not isinstance(sig, dict):
            continue
        if sig.get("scope") != "ml_baseline_evidence":
            continue
        label = sig.get("factor_name") or JUDGMENT_LABEL
        if sig.get("is_available"):
            text = sig.get("reason_text")
        else:
            text = sig.get("fallback_text")
        if not isinstance(text, str) or not text.strip():
            continue
        return f"- {label}: {text}"
    return None
