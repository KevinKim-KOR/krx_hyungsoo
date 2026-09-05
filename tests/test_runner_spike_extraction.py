"""POC3-OPS-01A r2 — KS-10 분리로 뽑아낸 spike helper 의 **계약 등가성**.

검증자 r2 A-3 지적: 분리를 "판정 로직 변경 0건" 이라 보고했지만 중복 skip 의
`error` 가 `None` 에서 `""` 로 바뀌었다. 그런데 `duplicate_runtime` 경로를 덮는
테스트가 저장소에 **한 건도 없어서** 전체 회귀를 통과했다.

여기서는 분리된 함수의 반환 계약을 직접 고정한다. `_finish(status, reason, error)`
의 3번째 자리에 그대로 들어가므로 record 계약과 1:1 이다.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.three_push_runtime.registry_key import (
    registry_key,
    resolve_registry_date_field,
)
from app.three_push_runtime.runner_spike import (
    apply_spike_reevaluation,
    resolve_spike_duplicates,
)

PK = "spike_or_falling_alert"


def _evidence(fps, *, status="ok", extra_notes=None):
    # composer 계약: extra_notes[i] 는 fingerprints[i] 와 순서 대응.
    return SimpleNamespace(
        spike_signal_fingerprints=fps,
        extra_notes=(
            extra_notes if extra_notes is not None else [f"note-{f}" for f in fps]
        ),
        available_sources=[],
        diagnostics={"reevaluate_status": status},
    )


class _RecordingLogger:
    """러너가 넘기는 logger 를 helper 가 실제로 쓰는지 확인용."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def info(self, msg, *a):
        self.calls.append(("info", str(msg)))

    def error(self, msg, *a):
        self.calls.append(("error", str(msg)))

    def warning(self, msg, *a):
        self.calls.append(("warning", str(msg)))


def _call(record, evidence, *, already, logger=None):
    """`already` 에 든 fingerprint 는 기발송으로 본다.

    registry 헬퍼는 **스텁이 아니라 러너가 실제로 넘기는 함수**를 그대로 쓴다.
    스텁을 쓰면 date_field 가 fingerprint 를 반영하지 않아 중복 판정이 성립하지
    않는다(실제로 첫 작성에서 그 실수를 했다).
    """
    already_fields = {
        resolve_registry_date_field("2026-09-04", signal_fingerprint=f) for f in already
    }
    return resolve_spike_duplicates(
        record,
        evidence,
        push_kind=PK,
        param=SimpleNamespace(param_id="P1"),
        runtime_date_kst="2026-09-04",
        runtime_kst="2026-09-04T09:15:00+09:00",
        build_runtime_message=lambda **kw: "재조립본문",
        resolve_registry_date_field=resolve_registry_date_field,
        registry_key=registry_key,
        is_already_sent=lambda pk, pid, df: df in already_fields,
        logger=logger if logger is not None else _RecordingLogger(),
    )


def test_all_fingerprints_already_sent_skips_with_error_none():
    """중복 skip 의 `error` 는 **None** 이다 — 빈 문자열이 아니다.

    분리 전 러너는 `_finish("skipped", "duplicate_runtime")` 를 호출했고
    `error` 기본값이 `None` 이었다.
    """
    record: dict = {"spike_signal_fingerprints": ["fp1", "fp2"]}
    fail, rebuilt = _call(record, _evidence(["fp1", "fp2"]), already={"fp1", "fp2"})

    assert fail is not None
    status, reason, error = fail
    assert (status, reason) == ("skipped", "duplicate_runtime")
    assert error is None, f"분리 전 계약은 error=None 인데 {error!r} 이 됐다"
    assert rebuilt is None


def test_new_fingerprint_rebuilds_body_and_records_split():
    """신규 fingerprint 가 하나라도 있으면 그것만으로 본문을 재조립한다."""
    record: dict = {"spike_signal_fingerprints": ["fp1", "fp2"]}
    fail, rebuilt = _call(record, _evidence(["fp1", "fp2"]), already={"fp1"})

    assert fail is None
    assert rebuilt == "재조립본문"
    assert record["spike_new_fingerprints"] == ["fp2"]
    assert record["spike_already_sent_fingerprints"] == ["fp1"]
    assert record["message_text_length"] == len("재조립본문")


def test_registry_failure_is_reported_as_failed_with_detail():
    record: dict = {"spike_signal_fingerprints": ["fp1"]}

    def _boom(pk, pid, df):
        raise RuntimeError("DB 잠김")

    fail, rebuilt = resolve_spike_duplicates(
        record,
        _evidence(["fp1"]),
        push_kind=PK,
        param=SimpleNamespace(param_id="P1"),
        runtime_date_kst="2026-09-04",
        runtime_kst="2026-09-04T09:15:00+09:00",
        build_runtime_message=lambda **kw: "x",
        resolve_registry_date_field=resolve_registry_date_field,
        registry_key=registry_key,
        is_already_sent=_boom,
        logger=_RecordingLogger(),
    )
    assert fail is not None
    assert fail[0] == "failed" and fail[1] == "registry_corrupted"
    assert "DB 잠김" in fail[2]
    assert rebuilt is None


def test_reevaluation_ok_returns_none_and_fills_record():
    record: dict = {}
    fail = apply_spike_reevaluation(
        record, _evidence(["fp1"], status="ok"), logger=_RecordingLogger()
    )
    assert fail is None
    assert record["spike_signal_fingerprints"] == ["fp1"]
    assert record["reevaluate_status"] == "ok"


def test_reevaluation_failed_blocks_send():
    record: dict = {}
    fail = apply_spike_reevaluation(
        record, _evidence([], status="failed"), logger=_RecordingLogger()
    )
    assert fail is not None
    assert fail[0] == "failed"
    assert fail[1] == "reevaluate_missing_published_evidence"


def test_reevaluation_partial_blocks_send():
    record: dict = {}
    fail = apply_spike_reevaluation(
        record, _evidence([], status="partial"), logger=_RecordingLogger()
    )
    assert fail is not None
    assert fail[0] == "failed" and fail[1] == "reevaluate_partial"


def test_helper_logs_through_runner_logger_not_module_logger():
    """helper 는 **러너가 넘긴 logger** 로 기록한다.

    `setup_logging(name)` 은 그 이름의 logger 에만 파일 handler 를 붙인다. helper 가
    `getLogger(__name__)` 을 쓰면 분리 전에는 운영 로그 파일에 남던 줄이 사라진다
    (검증자 r3 A-3 지적 — "기계적 등가 분리가 아니다").
    """
    rec_logger = _RecordingLogger()
    record: dict = {"spike_signal_fingerprints": ["fp1"]}
    fail, _ = _call(record, _evidence(["fp1"]), already={"fp1"}, logger=rec_logger)

    assert fail[:2] == ("skipped", "duplicate_runtime")
    assert rec_logger.calls, "러너 logger 로 아무것도 기록하지 않았다"
    assert any("중복 발송 차단" in m for _, m in rec_logger.calls), rec_logger.calls


def test_module_defines_no_own_logger():
    """모듈 전역 logger 를 두면 다시 운영 로그 경로가 갈라진다."""
    import app.three_push_runtime.runner_spike as mod

    assert not hasattr(mod, "logger"), "모듈 전역 logger 가 다시 생겼다"
