"""OCI 3-PUSH **PARAM Runtime** Runner — 정식 운영 경로.

OCI 에서 crontab 으로 실행 (정식 운영 command):
  python scripts/run_three_push_runtime_oci.py --push-kind market_briefing --mode dry-run
  python scripts/run_three_push_runtime_oci.py --push-kind holdings_briefing --mode send

이 스크립트가 하는 것:
  - state/three_push/params/latest_runtime_param.json 로드
  - PARAM schema_version 검증
  - PARAM enabled_push_kinds 확인
  - OCI runtime timestamp 기록
  - app.three_push_runtime_message_builder 로 runtime 메시지 생성
    (PC package message_text 를 그대로 사용하지 않음)
  - 금지 문구 검사 / token/chat_id 비노출 검사
  - duplicate guard (key = push_kind + param_id + KST 날짜)
  - enable flag guard (PUSH_AUTOSEND_ENABLED + push_kind별)
  - Telegram 발송 (send 모드 + 모든 조건 충족 시)
  - 실행 결과 기록 (state/three_push/oci_runtime_status_latest.json + history.jsonl)

이 스크립트가 하지 않는 것:
  - PC package message_text 정식 사용 (package 경로는 scripts/run_three_push_oci.py 가 fallback 으로 유지)
  - 외부 API 직접 호출 (Naver/Yahoo/뉴스 등)
  - 매수/매도/비중조절/조정장/위험 threshold 판단
  - 신규 DB / scheduler framework / ML 학습
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# 프로젝트 루트를 sys.path 에 추가 (스크립트 직접 실행 지원).
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT_FOR_PATH = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT_FOR_PATH) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT_FOR_PATH))

# .env 자동 로드 (다른 import 가 환경변수를 읽기 전에 수행)
from app.three_push_runner_common import (  # noqa: E402
    PUSH_KIND_FLAG_ENVS,
    STATE_DIR,
    VALID_PUSH_KINDS,
    assert_no_sensitive_keys,
    check_forbidden_wording,
    check_raw_identifiers,
    env_bool,
    load_dotenv_file,
    setup_logging,
    telegram_send,
)

load_dotenv_file()

from app.runtime_execution_status_store import (  # noqa: E402
    insert_status_from_record,
)
from app.three_push_runtime.runner_diagnostics import (  # noqa: E402
    forward_diagnostics,
)
from app.three_push_runtime.runner_duplicate import (  # noqa: E402
    check_plain_duplicate,
)
from app.three_push_runtime.runner_evidence import (  # noqa: E402
    SKIP_EVIDENCE_KINDS,
    compose_evidence_and_message,
    record_send_success,
)
from app.three_push_runtime.runner_spike import (  # noqa: E402
    apply_spike_reevaluation,
    resolve_spike_duplicates,
)

# POC3-OPS-01A — 보유 브리핑 선별·그룹화·반복 억제.
from app.runtime_evidence.holdings_risk_flow import (  # noqa: E402
    assemble_holdings_risk_push,
)
from app.runtime_evidence.holdings_risk_state import (  # noqa: E402
    save_risk_state,
)
from app.runtime_evidence.holdings_selection_flow import (  # noqa: E402
    assemble_holdings_push,
)
from app.runtime_evidence.holdings_selection_state import (  # noqa: E402
    kst_today,
    save_state,
)

HOLDINGS_SELECTION_STATE_PATH = STATE_DIR / "holdings_selection_state_latest.json"
# POC3-OPS-02A — 위험 알림 상태(그날 도달한 최악 구간). 보유 브리핑과 별개 파일.
HOLDINGS_RISK_STATE_PATH = STATE_DIR / "holdings_risk_state_latest.json"
from app.runtime_param_store import read_active_param_dict  # noqa: E402
from app.runtime_sent_registry_store import (  # noqa: E402
    is_already_sent,
    mark_sent,
)
from app.runtime_evidence_composer import (  # noqa: E402
    compose_runtime_evidence,
)
from app.three_push_runtime_message_builder import (  # noqa: E402
    availability_summary,
    build_runtime_message,
    kst_now_iso,
    kst_today_date,
)
from app.three_push_runtime_param import from_dict as param_from_dict  # noqa: E402

# ── 경로 ─────────────────────────────────────────────────────────────────────

# Cutover v1: active PARAM · latest status · sent registry 는 runtime_state.sqlite
# 기준으로 전환. history JSONL 만 archive 로 유지.
_HISTORY_PATH = STATE_DIR / "oci_runtime_history.jsonl"


# ── 메인 runner ───────────────────────────────────────────────────────────────


# Low-Frequency Telegram Push Operation v1 A+ (E · KS-10):
# 아래 helper 는 app.three_push_runtime 로 분리 · 여기서는 re-export 로 기존 참조
# 경로 유지 (tests 및 외부 caller 호환).
from app.three_push_runtime.registry_key import (  # noqa: E402
    HOLDINGS_SLOT_IDS,
    registry_key as _registry_key,
    resolve_registry_date_field as _resolve_registry_date_field,
)
from app.three_push_runtime.target_tickers import (  # noqa: E402
    collect_target_tickers as _collect_target_tickers,
)


def run(
    push_kind: str,
    mode: str,
    slot_id: Optional[str] = None,
) -> dict[str, Any]:
    """3-PUSH runner.

    Low-Frequency Telegram Push Operation v1:
    - slot_id: holdings_briefing 에만 유효 (OPEN/MIDDAY/CLOSE). 다른 push_kind
      에 slot_id 를 넘기면 무시. holdings_briefing 에서 slot_id 미지정 시
      failed/slot_id_required.
    """
    logger = setup_logging(
        f"three_push_runtime_runner.{push_kind}",
        log_filename="three_push_runtime_cron.log",
    )
    started_at_utc = datetime.now(timezone.utc).isoformat()
    runtime_kst = kst_now_iso()
    runtime_date_kst = kst_today_date()

    record: dict[str, Any] = {
        "push_kind": push_kind,
        "mode": mode,
        "slot_id": None,
        "status": "failed",
        "reason": None,
        "started_at": started_at_utc,
        "finished_at": "",
        "runtime_kst": runtime_kst,
        "runtime_date_kst": runtime_date_kst,
        "param_id": "",
        "param_source": "",
        "message_text_length": 0,
        "availability": {},
        "contentful_fact_count": 0,
        "selection_result_count": 0,
        "unavailable_reasons": {},
        "duplicate_key": "",
        "telegram_attempted": False,
        "telegram_sent": False,
        "partial_delivery": False,
        "error": None,
    }

    def _finish(
        status: str, reason: Optional[str] = None, error: Optional[str] = None
    ) -> dict[str, Any]:
        record["status"] = status
        record["reason"] = reason
        record["error"] = error
        record["finished_at"] = datetime.now(timezone.utc).isoformat()
        # Refactor v1 Q9 (c): DB latest status + history JSONL 을 runner 에서 분리 호출.
        insert_status_from_record(record)
        _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _HISTORY_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        logger.info(
            "runtime runner 완료: push_kind=%s mode=%s status=%s reason=%s",
            push_kind,
            mode,
            status,
            reason,
        )
        return record

    logger.info(
        "runtime runner 시작: push_kind=%s mode=%s runtime_kst=%s",
        push_kind,
        mode,
        runtime_kst,
    )

    # ── 1. active PARAM 로드 (runtime_state.sqlite 기준) ─────────────────────
    try:
        param_dict = read_active_param_dict()
        param = param_from_dict(param_dict)
    except Exception as e:
        logger.error("active PARAM 로드/검증 실패: %s", e)
        return _finish("failed", "param_load_error", str(e)[:400])

    record["param_id"] = param.param_id
    record["param_source"] = param.param_source

    # PARAM 자체에 secret 포함 여부 점검 (정책상 금지지만 방어적)
    try:
        assert_no_sensitive_keys(param.to_dict(), path="param")
    except RuntimeError as e:
        logger.error("PARAM secret 노출: %s", e)
        return _finish("failed", "param_secret_exposed", str(e)[:400])

    # ── 1-b. slot_id 계약 검증 (holdings_briefing 만) ────────────────────────
    # Low-Frequency Telegram Push Operation v1: holdings_briefing 은 OPEN/MIDDAY/CLOSE
    # 세 슬롯으로 나뉜다. slot_id 는 registry key 문자열에 삽입되어 슬롯별 중복 차단.
    if push_kind == "holdings_briefing":
        if slot_id is None:
            logger.error("holdings_briefing 은 --slot-id 필수 (OPEN/MIDDAY/CLOSE)")
            return _finish("failed", "slot_id_required")
        if slot_id not in HOLDINGS_SLOT_IDS:
            logger.error("잘못된 slot_id=%s (허용값 %s)", slot_id, HOLDINGS_SLOT_IDS)
            return _finish("failed", "slot_id_invalid")
        record["slot_id"] = slot_id
    else:
        if slot_id is not None:
            logger.info(
                "slot_id=%s 는 push_kind=%s 에서 무시됨 (holdings_briefing 만 유효)",
                slot_id,
                push_kind,
            )

    # ── 2. PARAM에서 push_kind 활성화 확인 ────────────────────────────────────
    if not param.is_push_kind_enabled(push_kind):
        logger.info(
            "PARAM enabled_push_kinds 미포함: push_kind=%s param_id=%s",
            push_kind,
            param.param_id,
        )
        return _finish("skipped", "push_kind_not_in_param")

    # ── 3. Runtime 가격 조회 (Low-Frequency Telegram Push Operation v1 A+ 재정정) ──
    # Fail-Closed 계약 (사용자 확정):
    #   attempted == 0  → skip 대상 없음 (Market 등) · 정상 진행.
    #   loader 예외      → failed (ticker_loader_error) · 미발송 · registry 미기록.
    #   Naver 예외       → failed (runtime_price_refresh_error).
    #   전건 실패        → failed (runtime_price_all_failed).
    #   일부 실패        → failed (runtime_price_partial_failed) · 미발송.
    from app.three_push_runtime.price_refresh import (
        evaluate_price_refresh,
        refresh_runtime_quotes,
    )

    market_quotes, price_refresh_diag, price_refresh_error = refresh_runtime_quotes(
        push_kind, _collect_target_tickers
    )
    record["runtime_price_refresh"] = price_refresh_diag
    if price_refresh_error is not None:
        logger.error("runtime price refresh 실패: %s", price_refresh_error)
        return _finish(
            "failed",
            "runtime_price_refresh_error",
            price_refresh_error,
        )
    refresh_fail = evaluate_price_refresh(
        price_refresh_diag, push_kind=push_kind, logger=logger
    )
    if refresh_fail is not None:
        return _finish(*refresh_fail)

    holdings_selection_ctx: dict[str, Any] = {}
    evidence = None
    message_text = ""

    # ── 3-a2. Spike freshness guard (OCI Operational Market Data Refresh v1 · §4.3) ──
    # Spike 는 Universe 운영 artifact 의 Published 계약(validate_artifact) + freshness
    # 를 검증한다. 미달 시 Fail-Closed. helper 로 분리 (KS-10 억제). Market/Holdings 무관.
    if push_kind == "spike_or_falling_alert":
        from app.draft_three_push import _load_universe_artifact_for_spike
        from app.three_push_runtime.spike_freshness import check_spike_freshness

        art_for_fresh = _load_universe_artifact_for_spike()
        fresh = check_spike_freshness(art_for_fresh, runtime_date_kst=runtime_date_kst)
        record["freshness_ok"] = fresh.ok
        record["freshness_reason"] = fresh.reason
        record["price_data_as_of"] = fresh.price_data_as_of
        record["artifact_generated_at"] = fresh.artifact_generated_at
        if not fresh.ok:
            logger.error("Spike freshness/validation 미달: %s", fresh.reason)
            return _finish("failed", "freshness_stale", fresh.reason)

    # ── 3-b. Universe re-evaluator 준비 (Spike 만 · Unit 3 helper 연결) ──────
    reeval_fn = None
    if push_kind == "spike_or_falling_alert":
        from app.runtime_evidence.universe_reevaluator import (
            reevaluate_spike_signals,
        )
        from app.draft_three_push import _load_universe_artifact_for_spike

        def _reeval() -> list:
            art = _load_universe_artifact_for_spike()
            if not isinstance(art, dict):
                return []
            return reevaluate_spike_signals(
                art, market_quotes, runtime_date_kst=runtime_date_kst
            )

        reeval_fn = _reeval

    # ── 3-c. 보유 브리핑 선정 · 본문 조립 (POC3-OPS-01A) ────────────────────
    # 조립만 한다. **모든 skip·fail 결정은 enable flag guard(§6) 뒤(§6-c)** 다 —
    # 여기서 return 하면 push_kind 가 비활성인데도 `no_selection`·데이터 실패가
    # 기존 계약인 `push_kind_disabled` 를 가로챈다(실제로 겪은 결함).
    # 순서 계약은 `assemble_holdings_push` 안에 있다: 비거래일 판정 → 완전성
    # 가드 → 선정(휴장일엔 선정·이력조회를 아예 돌리지 않는다).
    holdings_outcome = None
    skip_ntd = False
    holdings_fail: Optional[tuple[str, str, str]] = None
    if push_kind == "holdings_briefing":
        from app.holdings import load as _load_holdings_for_selection
        from app.market_data_store import fetch_price_history as _fetch_history

        _asm = assemble_holdings_push(
            market_quotes=market_quotes or {},
            price_refresh_diag=price_refresh_diag,
            today_kst=kst_today(),
            state_path=HOLDINGS_SELECTION_STATE_PATH,
            slot_id=slot_id,
            runtime_kst=runtime_kst,
            holdings_loader=_load_holdings_for_selection,
            fetch_history=_fetch_history,
            logger=logger,
        )
        record.update(_asm.diagnostics)
        holdings_fail = _asm.fail  # 판정은 §6-c (위 주석 참조)
        skip_ntd = _asm.skip_non_trading_day
        holdings_outcome = _asm.outcome
        message_text = _asm.message_text

    # ── 3-d. 보유 위험 즉시 알림 조립 (POC3-OPS-02A) ─────────────────────────
    # 기존 spike 신호·본문을 재사용하지 않는다 (OPS-01C `REJECT`). 조립만 하고
    # **모든 skip·fail 결정은 §6-c** — flag guard 뒤다.
    risk_outcome = None
    if push_kind == "holdings_risk_alert":
        from app.holdings import load as _load_holdings_for_risk
        from app.market_data_store import fetch_price_history as _fetch_history_risk

        _rasm = assemble_holdings_risk_push(
            market_quotes=market_quotes or {},
            price_refresh_diag=price_refresh_diag,
            today_kst=kst_today(),
            state_path=HOLDINGS_RISK_STATE_PATH,
            runtime_kst=runtime_kst,
            holdings_loader=_load_holdings_for_risk,
            fetch_history=_fetch_history_risk,
            logger=logger,
        )
        record.update(_rasm.diagnostics)
        holdings_fail = _rasm.fail  # 판정은 §6-c
        skip_ntd = _rasm.skip_non_trading_day
        risk_outcome = _rasm.outcome
        message_text = _rasm.message_text

    # ── 4. runtime evidence 조립 (Runtime Evidence DB Connection v1) ─────────
    # 보유 브리핑은 §3-c 에서 본문을 이미 만들었다. evidence 조립·면책 문구 부착
    # 경로를 타지 않는다 (설계자 확정 — 보유 브리핑에 면책문구를 넣지 않는다).
    if push_kind not in SKIP_EVIDENCE_KINDS:
        # ── 4-b. runtime message 생성 ────────────────────────────────────────
        ev_fail, evidence, _msg = compose_evidence_and_message(
            record,
            push_kind=push_kind,
            param=param,
            runtime_kst=runtime_kst,
            market_quotes=market_quotes,
            reeval_fn=reeval_fn,
            compose_runtime_evidence=compose_runtime_evidence,
            build_runtime_message=build_runtime_message,
            availability_summary=availability_summary,
            logger=logger,
        )
        if ev_fail is not None:
            return _finish(*ev_fail)
        message_text = _msg or ""
    # FIX r3 · r4 (설계자 확정본 Q7): 진단 필드 record 전달.
    # 2026-09-04 KS-10 분리 — 키 목록은 `runner_diagnostics` 로 옮겼다.
    forward_diagnostics(record, evidence)

    # Low-Frequency Telegram Push Operation v1 A+ 재정정 (A):
    # Spike 재조건평가 결과 fingerprint 목록. 각 신규 signal 은 개별 registry.
    # Low-Frequency Telegram Push Operation v1 A+ 재정정 (A):
    # Spike 재조건평가 결과 fingerprint 목록. 각 신규 signal 은 개별 registry.
    # 2026-09-04 KS-10 분리 — 본문은 `runner_spike` 로 옮겼다.
    if push_kind == "spike_or_falling_alert":
        spike_fail = apply_spike_reevaluation(record, evidence, logger=logger)
        if spike_fail is not None:
            return _finish(*spike_fail)

    # ── 4-c. 금지 문구 검사 ──────────────────────────────────────────────────
    bad = check_forbidden_wording(message_text)
    if bad:
        logger.warning("금지 문구 감지: %r — 발송 차단", bad)
        return _finish("failed", "forbidden_wording", f"phrase={bad}")

    # ── 4-b. raw 기술 식별자 노출 차단 (지시문 §4.1 / AC-1) ─────────────────
    # PARAM runtime builder 는 사용자 메시지만 생성하지만 이중 안전망.
    raw_ident = check_raw_identifiers(message_text)
    if raw_ident:
        logger.warning(
            "raw 기술 식별자 감지: %r — 발송 차단 (사용자용 메시지 아님)", raw_ident
        )
        return _finish("failed", "raw_identifier_exposed", f"identifier={raw_ident}")

    # ── 5. dry-run 종료 ──────────────────────────────────────────────────────
    if mode == "dry-run":
        # dry-run 은 발송 경로가 아니므로 조립 실패를 그대로 알린다.
        if holdings_fail is not None:
            return _finish(*holdings_fail)
        logger.info(
            "dry-run 완료: push_kind=%s param_id=%s msg_len=%d",
            push_kind,
            param.param_id,
            len(message_text),
        )
        return _finish("dry_run_success")

    # ── 6. enable flag guard ─────────────────────────────────────────────────
    if not env_bool("PUSH_AUTOSEND_ENABLED"):
        logger.info("PUSH_AUTOSEND_ENABLED=false — 발송 skip")
        return _finish("skipped", "autosend_disabled")

    kind_flag_env = PUSH_KIND_FLAG_ENVS[push_kind]
    if not env_bool(kind_flag_env):
        logger.info("%s=false — 발송 skip", kind_flag_env)
        return _finish("skipped", "push_kind_disabled")

    # ── 6-b. no-signal guard (Spike · Conditional Send v1 + Low-Frequency v1) ──
    # 미발송 조건:
    #   (a) composer 진단 no_signal=True (universe candidates=0)
    #   (b) Runtime 재평가 결과 신규 falling signal 0건 이고 재평가 status=ok
    #       (partial/failed 는 상위 §4 이미 처리). ok+0건 만 no_signal.
    # Sender 미호출 · registry 미기록.
    if push_kind == "spike_or_falling_alert":
        if record.get("no_signal") is True:
            logger.info(
                "no-signal 발송 skip: universe candidate 0건 (param_id=%s)",
                param.param_id,
            )
            return _finish("skipped", "no_signal")
        fps_all = record.get("spike_signal_fingerprints") or []
        reeval_st = record.get("reevaluate_status")
        if not fps_all and reeval_st == "ok":
            logger.info(
                "no-signal 발송 skip: Runtime 재평가 결과 신규 falling 0건 "
                "(param_id=%s)",
                param.param_id,
            )
            return _finish("skipped", "no_signal")

    # POC3-OPS-01A — 선정·억제는 **enable flag guard(§6) 뒤**에 둔다.
    # 앞에 두면 push_kind 가 비활성인데도 선정 상태를 저장할 수 있다
    # (검증 회귀에서 `no_selection` 이 `push_kind_disabled` 를 가로챘다).
    # ── 6-c. 보유 브리핑 비거래일 가드 · skip 판정 (POC3-OPS-01A) ───────────
    # 조립은 §3-c 에서 끝났다. 여기서는 발송 여부만 정한다.
    # 비거래일 가드를 **flag guard(§6) 뒤**에 둔다 — 앞에 두면 push_kind 가
    # 비활성인데도 `non_trading_day` 가 기존 계약인 `push_kind_disabled` 를
    # 가로챈다 (검증자 지적).
    # 조립 단계에서 잡힌 실패를 **flag guard 뒤**에서 확정한다.
    if holdings_fail is not None:
        return _finish(*holdings_fail)

    if skip_ntd:
        # 판정·evidence 기록은 §3-c 에서 끝났다. 여기서는 발송 여부만 정한다.
        return _finish("skipped", "non_trading_day")

    if risk_outcome is not None and risk_outcome.skip_reason:
        # 신규·악화 없음 — 완화·해소·동일 구간은 발송하지 않는다.
        logger.info(
            "위험 알림 skip: %s (선정 %d건 · 억제 %d건)",
            risk_outcome.skip_reason,
            len(risk_outcome.selected),
            len(risk_outcome.changes.suppressed) if risk_outcome.changes else 0,
        )
        return _finish("skipped", risk_outcome.skip_reason)

    if risk_outcome is not None:
        holdings_selection_ctx = {"risk": risk_outcome}

    if holdings_outcome is not None:
        if holdings_outcome.skip_reason:
            if holdings_outcome.save_empty_state:
                save_state(HOLDINGS_SELECTION_STATE_PATH, selected=[], slot_id=slot_id)
            logger.info(
                "보유 브리핑 skip: %s (선정 %d건)",
                holdings_outcome.skip_reason,
                len(holdings_outcome.selected),
            )
            return _finish("skipped", holdings_outcome.skip_reason)
        holdings_selection_ctx = {
            "selected": holdings_outcome.selected,
            "slot_id": slot_id,
        }

    # ── 7. duplicate guard (Low-Frequency Push v1 A+) ────────────────────────
    # Holdings: slot_id 접미.
    # Spike: 각 fingerprint 별로 개별 registry entry. 모든 fingerprint 가 이미 sent
    #        면 duplicate_runtime skip. 하나라도 신규면 발송 후 신규 fingerprint 만
    #        각각 registry 에 기록.
    # spike 는 fingerprint 별 개별 키를 §8 에서 다시 만든다.
    registry_date_field: Optional[str] = None
    if push_kind == "spike_or_falling_alert":
        # 2026-09-04 KS-10 분리 — 본문은 `runner_spike.resolve_spike_duplicates`.
        spike_fail, rebuilt = resolve_spike_duplicates(
            record,
            evidence,
            push_kind=push_kind,
            param=param,
            runtime_date_kst=runtime_date_kst,
            runtime_kst=runtime_kst,
            build_runtime_message=build_runtime_message,
            resolve_registry_date_field=_resolve_registry_date_field,
            registry_key=_registry_key,
            is_already_sent=is_already_sent,
            logger=logger,
        )
        if spike_fail is not None:
            return _finish(*spike_fail)
        message_text = rebuilt
    else:
        dup_fail, registry_date_field = check_plain_duplicate(
            record,
            push_kind=push_kind,
            param=param,
            runtime_date_kst=runtime_date_kst,
            runtime_kst=runtime_kst,
            slot_id=slot_id,
            resolve_registry_date_field=_resolve_registry_date_field,
            registry_key=_registry_key,
            is_already_sent=is_already_sent,
            logger=logger,
        )
        if dup_fail is not None:
            return _finish(*dup_fail)

    # ── 8. Telegram 발송 ─────────────────────────────────────────────────────
    record["telegram_attempted"] = True
    sent, err, partial_delivery = telegram_send(message_text)
    record["telegram_sent"] = sent
    # A+ 재정정 (B-6): telegram chunk 전송의 부분 결과만 telegram_partial_delivery
    # 필드로 저장. 데이터 품질 partial 은 이미 상위에서 failed 로 처리되므로 여기에는
    # 섞지 않는다.
    record["telegram_partial_delivery"] = bool(partial_delivery)
    record["partial_delivery"] = bool(partial_delivery)

    if sent:
        record_send_success(
            record,
            push_kind=push_kind,
            param=param,
            runtime_date_kst=runtime_date_kst,
            runtime_kst=runtime_kst,
            registry_date_field=registry_date_field,
            partial_delivery=bool(partial_delivery),
            holdings_selection_ctx=holdings_selection_ctx,
            sent_at=datetime.now(timezone.utc).isoformat(),
            resolve_registry_date_field=_resolve_registry_date_field,
            mark_sent=mark_sent,
            save_state=save_state,
            save_risk_state=save_risk_state,
            holdings_state_path=HOLDINGS_SELECTION_STATE_PATH,
            risk_state_path=HOLDINGS_RISK_STATE_PATH,
        )
        return _finish("sent")
    else:
        logger.error("Telegram 발송 실패: %s", err)
        return _finish("failed", "telegram_send_error", (err or "")[:400])


# ── CLI ───────────────────────────────────────────────────────────────────────


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "OCI 3-PUSH PARAM Runtime Runner — latest PARAM snapshot 기반 "
            "runtime 메시지 생성 + Telegram 발송. "
            "PC-generated package message_text 를 정식 경로에서 사용하지 않는다."
        )
    )
    parser.add_argument(
        "--push-kind",
        required=True,
        choices=list(VALID_PUSH_KINDS),
        help="실행할 push_kind",
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["dry-run", "send"],
        help="dry-run: 검증/메시지 생성만 / send: Telegram 발송",
    )
    parser.add_argument(
        "--slot-id",
        required=False,
        default=None,
        choices=list(HOLDINGS_SLOT_IDS),
        help=(
            "holdings_briefing 전용 슬롯 식별자 (OPEN/MIDDAY/CLOSE). "
            "Low-Frequency Telegram Push Operation v1: 같은 날짜에 서로 다른 "
            "슬롯 발송 허용 · 동일 슬롯 재실행은 중복 차단."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = run(push_kind=args.push_kind, mode=args.mode, slot_id=args.slot_id)
    status = result.get("status", "failed")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if status in ("sent", "dry_run_success", "skipped"):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
