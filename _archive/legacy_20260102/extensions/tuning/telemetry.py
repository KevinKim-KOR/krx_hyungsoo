# -*- coding: utf-8 -*-
"""
extensions/tuning/telemetry.py
구조화 이벤트 로그(JSONL) - Phase 1.6

UI/AI가 소비할 수 있는 구조화된 이벤트 로그를 JSONL 형식으로 저장한다.
저장 위치: data/telemetry/{run_id}.jsonl
"""
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class EventStage(str, Enum):
    """이벤트 발생 단계"""

    PHASE15 = "phase15"
    TUNING = "tuning"
    GATE1 = "gate1"
    GATE2 = "gate2"
    GATE3 = "gate3"
    FINAL = "final"
    ANALYSIS = "analysis"


class EventType(str, Enum):
    """이벤트 유형"""

    RUN_START = "RUN_START"
    RUN_CONFIG = "RUN_CONFIG"
    RUN_END = "RUN_END"
    DATA_PREFLIGHT = "DATA_PREFLIGHT"
    TRIAL_START = "TRIAL_START"
    TRIAL_END = "TRIAL_END"
    GATE1_DECISION = "GATE1_DECISION"
    GATE1_SUMMARY = "GATE1_SUMMARY"
    GATE2_DECISION = "GATE2_DECISION"
    GATE2_SUMMARY = "GATE2_SUMMARY"
    WF_WINDOW_END = "WF_WINDOW_END"
    MANIFEST_SAVED = "MANIFEST_SAVED"
    GUARDRAIL_DISTRIBUTION = "GUARDRAIL_DISTRIBUTION"
    ERROR = "ERROR"
    WARNING = "WARNING"


class Severity(str, Enum):
    """심각도"""

    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


@dataclass
class TelemetryEvent:
    """텔레메트리 이벤트"""

    ts: str  # ISO8601 timestamp
    run_id: str
    stage: str
    event: str
    severity: str
    payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


class TelemetryLogger:
    """
    텔레메트리 로거

    JSONL 형식으로 이벤트를 저장한다.
    """

    _instance: Optional["TelemetryLogger"] = None
    _initialized: bool = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        run_id: Optional[str] = None,
        base_dir: Optional[Path] = None,
    ):
        if self._initialized and run_id is None:
            return

        self.run_id = run_id or f"run_{datetime.now(KST).strftime('%Y%m%d_%H%M%S')}"
        self.base_dir = base_dir or Path("data/telemetry")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.filepath = self.base_dir / f"{self.run_id}.jsonl"
        self._events: list = []
        self._initialized = True

    def reset(self, run_id: str, base_dir: Optional[Path] = None):
        """새 run_id로 리셋"""
        self.run_id = run_id
        if base_dir:
            self.base_dir = base_dir
            self.base_dir.mkdir(parents=True, exist_ok=True)
        self.filepath = self.base_dir / f"{self.run_id}.jsonl"
        self._events = []

    def emit(
        self,
        event: str,
        stage: str,
        severity: str = Severity.INFO.value,
        payload: Optional[Dict[str, Any]] = None,
    ) -> TelemetryEvent:
        """
        이벤트 발행

        Args:
            event: 이벤트 유형 (EventType enum 값 권장)
            stage: 발생 단계 (EventStage enum 값 권장)
            severity: 심각도 (Severity enum 값 권장)
            payload: 이벤트별 추가 데이터

        Returns:
            생성된 TelemetryEvent
        """
        telemetry_event = TelemetryEvent(
            ts=datetime.now(KST).isoformat(),
            run_id=self.run_id,
            stage=stage,
            event=event,
            severity=severity,
            payload=payload or {},
        )

        self._events.append(telemetry_event)
        self._write_event(telemetry_event)

        return telemetry_event

    def _write_event(self, event: TelemetryEvent):
        """이벤트를 JSONL 파일에 추가"""
        try:
            with open(self.filepath, "a", encoding="utf-8") as f:
                f.write(event.to_json() + "\n")
        except Exception as e:
            logger.error(f"텔레메트리 쓰기 실패: {e}")

    def get_events(self) -> list:
        """현재 세션의 모든 이벤트 반환"""
        return self._events.copy()

    def get_filepath(self) -> Path:
        """JSONL 파일 경로 반환"""
        return self.filepath


# 전역 인스턴스
_telemetry: Optional[TelemetryLogger] = None


def init_telemetry(run_id: str, base_dir: Optional[Path] = None) -> TelemetryLogger:
    """
    텔레메트리 초기화

    Args:
        run_id: 실행 ID
        base_dir: 저장 디렉토리 (기본: data/telemetry)

    Returns:
        TelemetryLogger 인스턴스
    """
    global _telemetry
    _telemetry = TelemetryLogger(run_id=run_id, base_dir=base_dir)
    return _telemetry


def get_telemetry() -> TelemetryLogger:
    """전역 텔레메트리 인스턴스 반환"""
    global _telemetry
    if _telemetry is None:
        _telemetry = TelemetryLogger()
    return _telemetry


def emit_event(
    event: str,
    stage: str,
    severity: str = Severity.INFO.value,
    payload: Optional[Dict[str, Any]] = None,
) -> TelemetryEvent:
    """
    이벤트 발행 (편의 함수)

    Args:
        event: 이벤트 유형
        stage: 발생 단계
        severity: 심각도
        payload: 이벤트별 추가 데이터

    Returns:
        생성된 TelemetryEvent
    """
    return get_telemetry().emit(event, stage, severity, payload)


# 편의 함수들
def emit_run_start(
    stage: str,
    run_id: str,
    config: Dict[str, Any],
) -> TelemetryEvent:
    """RUN_START 이벤트"""
    return emit_event(
        EventType.RUN_START.value,
        stage,
        Severity.INFO.value,
        {"run_id": run_id, "config": config},
    )


def emit_run_end(
    stage: str,
    run_id: str,
    success: bool,
    summary: Dict[str, Any],
) -> TelemetryEvent:
    """RUN_END 이벤트"""
    return emit_event(
        EventType.RUN_END.value,
        stage,
        Severity.INFO.value if success else Severity.WARN.value,
        {"run_id": run_id, "success": success, "summary": summary},
    )


def emit_data_preflight(
    stage: str,
    ok: bool,
    fail_count: int,
    failures: list,
    sample_stats: Dict[str, Any],
) -> TelemetryEvent:
    """DATA_PREFLIGHT 이벤트"""
    return emit_event(
        EventType.DATA_PREFLIGHT.value,
        stage,
        Severity.INFO.value if ok else Severity.ERROR.value,
        {
            "ok": ok,
            "fail_count": fail_count,
            "failures": failures,
            "sample_stats": sample_stats,
        },
    )


def emit_trial_end(
    stage: str,
    trial_number: int,
    params: Dict[str, Any],
    score: float,
    passed_guardrails: bool,
    fail_reasons: list,
) -> TelemetryEvent:
    """TRIAL_END 이벤트"""
    return emit_event(
        EventType.TRIAL_END.value,
        stage,
        Severity.INFO.value,
        {
            "trial_number": trial_number,
            "params": params,
            "score": score,
            "passed_guardrails": passed_guardrails,
            "fail_reasons": fail_reasons,
        },
    )


def emit_gate1_summary(
    stage: str,
    total_trials: int,
    passed_count: int,
    top_n: int,
    fail_reason_distribution: Dict[str, int],
) -> TelemetryEvent:
    """GATE1_SUMMARY 이벤트"""
    return emit_event(
        EventType.GATE1_SUMMARY.value,
        stage,
        Severity.INFO.value,
        {
            "total_trials": total_trials,
            "passed_count": passed_count,
            "top_n": top_n,
            "fail_reason_distribution": fail_reason_distribution,
        },
    )


def emit_guardrail_distribution(
    stage: str,
    total_trials: int,
    distribution: Dict[str, int],
    top5: list,
) -> TelemetryEvent:
    """GUARDRAIL_DISTRIBUTION 이벤트"""
    return emit_event(
        EventType.GUARDRAIL_DISTRIBUTION.value,
        stage,
        Severity.INFO.value,
        {
            "total_trials": total_trials,
            "distribution": distribution,
            "top5": top5,
        },
    )


def emit_manifest_saved(
    stage: str,
    filepath: str,
    manifest_stage: str,
    data_version: str,
    universe_hash: str,
) -> TelemetryEvent:
    """MANIFEST_SAVED 이벤트"""
    return emit_event(
        EventType.MANIFEST_SAVED.value,
        stage,
        Severity.INFO.value,
        {
            "filepath": filepath,
            "manifest_stage": manifest_stage,
            "data_version": data_version,
            "universe_hash": universe_hash,
        },
    )


def emit_error(
    stage: str,
    error_type: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> TelemetryEvent:
    """ERROR 이벤트"""
    return emit_event(
        EventType.ERROR.value,
        stage,
        Severity.ERROR.value,
        {
            "error_type": error_type,
            "message": message,
            "details": details or {},
        },
    )


def emit_run_config(
    stage: str,
    use_mock: bool,
    test_mode: bool,
    analysis_mode: bool,
    skip_logic_check: bool,
    skip_mdd_check: bool,
    data_version: str,
    requested_hash: str,
    effective_hash: str,
    period_start: str,
    period_end: str,
    wf_preset: str = "default",
) -> TelemetryEvent:
    """
    RUN_CONFIG 이벤트 - 실행 설정 기록

    "실제로 real로 돌았는지"를 로그만 봐도 1초만에 확인 가능하도록 함.
    """
    return emit_event(
        EventType.RUN_CONFIG.value,
        stage,
        Severity.INFO.value,
        {
            "use_mock": use_mock,
            "test_mode": test_mode,
            "analysis_mode": analysis_mode,
            "skip_logic_check": skip_logic_check,
            "skip_mdd_check": skip_mdd_check,
            "data_version": data_version,
            "requested_hash": requested_hash,
            "effective_hash": effective_hash,
            "period_start": period_start,
            "period_end": period_end,
            "wf_preset": wf_preset,
        },
    )


def emit_gate2_summary(
    stage: str,
    total_candidates: int,
    passed_count: int,
    wf_windows: int,
    best_stability_score: float,
) -> TelemetryEvent:
    """GATE2_SUMMARY 이벤트"""
    return emit_event(
        EventType.GATE2_SUMMARY.value,
        stage,
        Severity.INFO.value,
        {
            "total_candidates": total_candidates,
            "passed_count": passed_count,
            "wf_windows": wf_windows,
            "best_stability_score": best_stability_score,
        },
    )
