"""POC6-17 — 시장 흐름의 '기간 비교 기준일' 설명 · 수급 연결 상태(서버 한 곳 · 네 출력 공통 · 설계 §5).

`GET /market/flow-context` 가 부른다(읽기 전용 연결 · 쓰기 · 외부 호출 0). 기존 D · 기간 계산은 그대로 두고
'왜 그 날짜에서 끝났는가'와 '수급을 마지막에 어떻게 받았는가'만 문장으로 만든다. 문장은 「시장 흐름 자세히」 ·
대시보드 · AI 복사문 · 판단 근거 미리보기가 그대로 쓴다.

- `end_basis.limited_by` = 공통 끝일 D 를 실제로 막은 자료: `flows`(수급이 코스피보다 이름) · `kospi`(반대) ·
  `gap`(D 가 두 최신일보다 이름 = 공통 날짜 결측 · 판정 §4-4) · `unknown`(공통 날짜 없음) · null(제한 없음).
- `flow_link` = 수급 기록(옛 키움 직접 조회 · OCI 가져오기 · 반영)의 가장 최근 결과. DB 기록이라 서버 재기동 뒤에도
  남는다. 가져오기 실패 뒤 반영 성공을 일반 '반영'으로 바꾸지 않는다(판정 §3). 뒤에 성공이 있으면 옛 실패는
  현재 상태로 쓰지 않는다. 사유는 고정된 짧은 한국어만(키 · 토큰 · IP · 원시 응답 없음).
- `retry_helps` = [최신 시장 데이터 갱신]을 다시 눌러 나아질 수 있는가(할 일 안내 근거). 확인된 OCI 수집 실패 ·
  가져오기 정상 뒤 새 자료 없음 · 보관본 형식 · 충돌 · 기록 확인 불가는 False.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from app.supply_fx_oil_calc import md
from app.supply_fx_oil_store import (
    FLOW_IMPORT_LOG_SOURCE,
    FLOW_LOG_SOURCE,
    FLOW_PULL_LOG_SOURCE,
)

KST = timezone(timedelta(hours=9))
RETRY_REASON_MARKS = (
    "손상",
    "PC 표 반영 실패",
)  # 다시 가져오면 되살아날 수 있는 반영 실패


def kst_stamp(iso: Optional[str]) -> str:
    """저장 시각(UTC ISO · 'Z' 가능) → 'M/D HH:MM KST'. 없거나 읽을 수 없으면 '—'."""
    if not iso:
        return "—"
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return "—"
    k = (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).astimezone(KST)
    return f"{k.month}/{k.day} {k:%H:%M} KST"


def end_basis(
    *,
    D: Optional[str],
    kospi_E: Optional[str],
    flows_E: Optional[str],
    common_ok: bool,
    others: list[tuple[str, Optional[str]]],
) -> dict:
    """기간 비교 기준일 D 가 그 날짜인 이유(실제 자료일로 · 수급만 탓하지 않음)."""
    out = {
        "D": D,
        "kospi_E": kospi_E,
        "flows_E": flows_E,
        "limited_by": None,
        "text": "",
    }
    if not D or not kospi_E:
        out["text"] = "코스피 저장 자료가 없어 기간 비교 기준일이 없습니다"
        return out
    if not flows_E:
        out["text"] = f"수급 자료가 없어 기간 비교는 코스피 {md(D)}까지입니다"
    elif not common_ok:
        out["limited_by"] = "unknown"
        out["text"] = (
            f"코스피({md(kospi_E)}까지)와 수급({md(flows_E)}까지)에 함께 있는 날짜가 없어 "
            "수급 기간 비교를 할 수 없습니다"
        )
    elif D < min(kospi_E, flows_E):
        out["limited_by"] = "gap"
        out["text"] = (
            f"코스피는 {md(kospi_E)}, 수급은 {md(flows_E)}까지 있지만 둘 다 있는 마지막 날이 {md(D)}라 "
            f"기간 비교는 {md(D)}까지입니다(중간 날짜 빠짐)"
        )
    elif flows_E < kospi_E:
        out["limited_by"] = "flows"
        out["text"] = (
            f"코스피는 {md(kospi_E)}, 수급은 {md(flows_E)}까지 있어 기간 비교는 {md(D)}까지입니다"
        )
    elif kospi_E < flows_E:
        out["limited_by"] = "kospi"
        out["text"] = (
            f"수급은 {md(flows_E)}, 코스피는 {md(kospi_E)}까지 있어 기간 비교는 {md(D)}까지입니다"
        )
    else:
        out["text"] = f"기간 비교 기준일 {md(D)} · 코스피 · 수급 모두 {md(D)}까지"
    later = [f"{label} {md(E)}" for label, E in others if E and E > D]
    if later:
        out[
            "text"
        ] += f" · {' · '.join(later)} 최근 값은 '최근 큰 변화'에 따로 보입니다"
    return out


def _latest(con: sqlite3.Connection, source: str) -> Optional[dict]:
    row = con.execute(
        "SELECT run_id, fail_count, success_count, error_summary, created_at "
        "FROM market_refresh_log WHERE source = ? ORDER BY created_at DESC, rowid DESC LIMIT 1",
        (source,),
    ).fetchone()
    if row is None:
        return None
    return dict(zip(("run_id", "fail", "success", "error", "at"), row))


def _has(con: sqlite3.Connection, table: str) -> bool:
    return (
        con.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
        ).fetchone()
        is not None
    )


def _link(state: str, at: Optional[str], text: str, retry: bool, oci=None) -> dict:
    return {
        "state": state,
        "at": at,
        "text": text,
        "retry_helps": retry,
        "oci_flow_status": oci,
    }


def read_flow_link(db_path: Path, flows_E: Optional[str]) -> dict:
    """가장 최근 수급 기록으로 연결 상태 문장을 만든다(읽기 전용 · 읽기 실패 = '확인 필요' · 추정 없음)."""
    keep = f"수급 {md(flows_E)}까지 사용 중" if flows_E else "PC 수급 자료 없음"
    try:
        if not Path(db_path).exists():
            return _link(
                "no_record", None, f"아직 OCI 수급을 반영한 기록 없음 · {keep}", True
            )
        uri = f"file:{Path(db_path).resolve()}?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as con:
            if not _has(con, "market_refresh_log"):
                legacy = imp = pull = None
            else:
                legacy = _latest(con, FLOW_LOG_SOURCE)
                imp = _latest(con, FLOW_IMPORT_LOG_SOURCE)
                pull = None
                if imp is not None:
                    pid = imp["run_id"].replace(
                        "market-flow-flowoci-", "market-flow-flowpull-"
                    )
                    row = con.execute(
                        "SELECT fail_count, error_summary FROM market_refresh_log "
                        "WHERE run_id = ? AND source = ?",
                        (pid, FLOW_PULL_LOG_SOURCE),
                    ).fetchone()
                    pull = {"fail": row[0], "error": row[1]} if row else None
            oci, applied_runs = None, 0
            if _has(con, "market_investor_flow_import"):
                oci = con.execute(
                    "SELECT flow_status, published_at FROM market_investor_flow_import "
                    "ORDER BY published_at DESC, evidence_run_id DESC LIMIT 1"
                ).fetchone()
                applied_runs = con.execute(
                    "SELECT COUNT(*) FROM market_investor_flow_import WHERE result = 'APPLIED'"
                ).fetchone()[0]
    except sqlite3.Error:
        return _link(
            "unknown", None, "수급 연결 상태 확인 필요(반영 기록을 읽지 못함)", False
        )
    oci_status = oci[0] if oci else None
    base = _base_link(legacy, imp, pull, oci, applied_runs, flows_E, keep)
    if oci_status not in (None, "OK", "PARTIAL"):
        # 확인된 OCI 최근 수집 실패가 다른 모든 상태보다 우선(판정 §4-4 · 검증자 r1 F1) — 반영 실패 ·
        # 가져오기 실패 · 옛 직접 조회 실패도 사실대로 함께 쓰고, '다시 누르기'는 만들지 않는다.
        text = (
            f"OCI의 최근 수급 수집이 실패했습니다({kst_stamp(oci[1])} 공개) · "
            f"다시 갱신해도 바뀌지 않을 수 있습니다 · {base['text']}"
        )
        return _link("oci_collect_failed", base["at"], text, False, oci_status)
    return base


def _base_link(legacy, imp, pull, oci, applied_runs, flows_E, keep) -> dict:
    """OCI 수집 실패 판단 전의 연결 상태(옛 직접 조회 · 반영 실패 · 가져오기 실패 · 반영 정상)."""
    oci_status = oci[0] if oci else None
    if (
        imp is None
    ):  # POC6-17 전 · 첫 반영 전(그 뒤 PC 는 키움 직접 조회 기록을 남기지 않음)
        if legacy is not None and legacy["fail"]:
            why = "키움 인증 실패" if "인증" in str(legacy["error"]) else "조회 실패"
            at = kst_stamp(legacy["at"])
            return _link(
                "legacy_direct_failed",
                at,
                f"아직 OCI 수급을 반영한 기록 없음 · 마지막 PC 직접 조회 실패({at} · {why}) · {keep}",
                True,
                oci_status,
            )
        return _link(
            "no_record",
            None,
            f"아직 OCI 수급을 반영한 기록 없음 · {keep}",
            True,
            oci_status,
        )
    at = kst_stamp(imp["at"])
    if imp["fail"]:
        reason = str(imp["error"] or "원인 미상")
        return _link(
            "apply_failed",
            at,
            f"수급 자료 반영 실패({at} · {reason}) · {keep}",
            any(m in reason for m in RETRY_REASON_MARKS),
            oci_status,
        )
    fe = md(flows_E) if flows_E else "없음"
    if pull is None or pull["fail"]:
        why = str((pull or {}).get("error") or "가져오기 기록 없음")
        head = why if why == "다른 가져오기 진행 중" else f"가져오기 실패({why})"
        if imp["success"]:
            text = f"{head} · PC에 이미 받은 {fe}까지의 수급 반영 완료 · 새 OCI 자료는 확인하지 못했습니다"
            return _link("applied_local", at, text, True, oci_status)
        text = (
            f"{head} · 기존 PC 수급({fe}까지) 유지 · 새 OCI 자료는 확인하지 못했습니다"
        )
        return _link("kept_local", at, text, True, oci_status)
    if (
        not applied_runs
    ):  # 가져오기는 정상인데 반영한 OCI 묶음이 없음 — 행은 PC 직접 조회 값
        return _link(
            "no_record",
            at,
            f"가져오기는 정상이지만 반영한 OCI 수급 묶음이 없습니다 · {keep}",
            False,
            oci_status,
        )
    text = (
        f"수급은 OCI 수집본을 PC에 반영({at} · {fe}까지)"
        if imp["success"]
        else f"수급은 OCI 수집본 기준({at} 확인 · 새 자료 없음 · {fe}까지)"
    )
    if oci_status == "PARTIAL":
        text += f" · OCI 최근 수급 수집 일부 날짜 실패({kst_stamp(oci[1])} 공개)"
    return _link("applied", at, text, False, oci_status)
