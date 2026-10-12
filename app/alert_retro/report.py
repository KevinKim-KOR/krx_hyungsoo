"""POC5-08 — 사후평가 실행 · 입력 digest · 연구 산출물 · 최신 조회(설계 §7 · §8 · PLAN §2-1 · §2-3 · 판정 §3-B).

```text
실행(POST)  종료일(없으면 04 default_end) → snapshot 획득 시각 1회 고정 → price_asof_date(그 시각까지
            종가가 끝난 마지막 거래일) → 04 load_snapshot(mode=ro) → 손상 = CHECK_REQUIRED · 사본 없음 = NO_COPY
            (둘 다 산출물 없음) → 모집단 · 가격 · ML → 임시 폴더에 report.json · input_snapshot.json → 이름 바꾸기
조회(GET)   완성된 최신 폴더만 읽는다 · 지금 사본의 입력 digest 를 원래 보고의 종료일 · price_asof_date 로
            다시 계산해 다르면 input_changed(재학습 · SSH · 쓰기 0)
쓰지 않음   원장 · 사본 · 보유 · 시세 · 운영 DB · 모델 파일 · latest 상태 파일 · 평가 action · 메모 · values_json 전체
```
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import time
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Optional

from app.alert_retro import features as F
from app.alert_retro import model, population
from app.ledger_copy import store as copy_store
from app.ledger_reports import dates
from app.ledger_reports.source import Snapshot, load_snapshot
from app.three_push_runtime import ledger_outcome_prices as px

RESEARCH_ROOT = Path(
    "state/ml/research/poc5_08"
)  # 호출 때 읽는다(테스트가 tmp 로 바꾼다)
SCHEMA = "alert_retro.v1"
KST = timezone(timedelta(hours=9))
NO_COPY, CHECK_REQUIRED, OK = "NO_COPY", "CHECK_REQUIRED", "OK"
NO_RESULT, ARTIFACT_UNREADABLE = "NO_RESULT", "ARTIFACT_UNREADABLE"
STATUS_TEXT = {
    NO_COPY: "PC 원장 사본이 없습니다 — 먼저 [원장 새로고침]",
    CHECK_REQUIRED: "원장 사본 확인 필요 — 산출물을 만들지 않았습니다",
    OK: "사후평가 완료",
    NO_RESULT: "아직 사후평가 결과가 없습니다",
    ARTIFACT_UNREADABLE: "최신 사후평가 파일을 읽을 수 없습니다",
}
NOTES = (
    "자동 가격 평가는 저장된 무조정 종가 비교입니다 — 배당 · 세금 · 수수료를 포함한 개인 손익이 아닙니다.",
    "+5 끝점의 상승 · 하락은 경로 전체의 계속 상승 · 하락을 뜻하지 않으며 신호의 성공 · 실패 판정이 아닙니다.",
    "과거 검증 추정은 보존된 원장 snapshot 으로 재구성한 연구 검증입니다 — 당시 운영에서 발행한 예측이 아닙니다.",
    "사용자 평가는 별도 근거입니다 — 표본 · 라벨 · 입력값에 쓰지 않습니다.",
    "computed_at 은 OCI 의 결과 기록 시각이며 그때 PC 에서 읽었다는 증거가 아닙니다.",
    "승인 · 확률 · 추천이 아니며 운영 모델로 저장 · 채택하지 않습니다.",
)
_FOLDER = re.compile(r"^\d{8}T\d{12}_[0-9a-f]{8}$")
_ITEM_FIELDS = (
    "event_id",
    "item_seq",
    "signal_date",
    "schedule_expected",
    "runtime_kst",
    "push_kind",
    "contract_version",
    "subject_kind",
    "subject_id",
    "held",
    "state",
    "event_type",
    "exposure",
    "disposition",
    "delivery_status",
)


class InvalidEndDate(ValueError):
    """종료일 입력 오류(422)."""


class ArtifactSaveError(RuntimeError):
    """연구 산출물 저장 실패(500) — 이전 산출물은 그대로 둔다."""


def _now() -> datetime:
    return datetime.now(KST)  # 시험이 바꿔 끼운다(종료일 · 획득 시각 · 생성 시각)


def _copy_path() -> Path:
    return Path(copy_store.DEFAULT_DB_PATH)  # 호출 때 읽는다(conftest 가 tmp 로 바꾼다)


def canonical_hash(payload: Any) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def price_asof_date(cal: px.Calendar, acquired: datetime) -> Optional[str]:
    """획득 시각까지 종가가 끝난 마지막 거래일 — 그날이 거래일이고 15:30 이후면 그날 · 아니면 직전 거래일."""
    local = acquired.astimezone(KST)
    day = local.date().isoformat()
    if cal.is_trading(day) and local >= dates.at_kst(day, model.CLOSE):
        return day
    return cal.previous(day)


def _resolve_end(cal: px.Calendar, end_date: Optional[str], today: str) -> str:
    if end_date is None:
        end = dates.default_end(cal, today)
        if end is None:
            raise InvalidEndDate("운영 캘린더로 기본 종료일을 정할 수 없습니다")
        return end
    try:
        return dates.validate_end(cal, end_date, today)
    except ValueError as e:
        raise InvalidEndDate(str(e)) from e


def _read(path: Path) -> tuple[Optional[Snapshot], Optional[list[str]]]:
    """(snapshot, 손상 사유) — 파일 없음 = (None, None)."""
    try:
        snap = load_snapshot(path)
    except FileNotFoundError:
        return None, None
    except sqlite3.Error as e:
        return None, [f"사본 읽기 오류: {type(e).__name__}"]
    return snap, population.check_copy(snap)


def input_snapshot(pop: dict[str, Any], end: str, asof: str) -> dict[str, Any]:
    """실제 쓴 입력만 — 허용 feature · 결과 · 연결 키 · 시각 · 계약 버전 · 평가 식별값 · recipe."""
    items, outcomes = [], []
    for r in pop["items"]:
        items.append(
            {
                **{k: r[k] for k in _ITEM_FIELDS},
                "numeric": r["numeric"],
                "series_count": r["series_count"],
                "expected_eval_dates": r["expected_eval_dates"],
            }
        )
        for s in r["slots"]:
            if s["series_id"] is not None:
                outcomes.append(
                    {
                        "event_id": r["event_id"],
                        "item_seq": r["item_seq"],
                        **{k: s[k] for k in population.OUTCOME_FIELDS},
                    }
                )
    return {
        "schema": SCHEMA,
        "end_date": end,
        "price_asof_date": asof,
        "recipe": model.RECIPE,
        "items": items,
        "outcomes": outcomes,
        "feedback": pop["feedback"],
        # 신호 기간 끝 뒤 건수는 기간 밖 — 새 알림이 들어온 것만으로 '입력 변경'이 되지 않게 뺀다.
        "exclusions": {k: v for k, v in pop["exclusions"].items() if k != "after_end"},
    }


def _item_views(
    pop: dict[str, Any], reasons: dict, ml_rows: dict
) -> list[dict[str, Any]]:
    out = []
    for r in pop["items"]:
        slots = []
        for n, s in enumerate(r["slots"]):
            view = {
                **s,
                "status_text": population.STATUS_TEXT.get(s["status"], s["status"]),
                "sign_text": population.SIGN_TEXT.get(s["sign"]) if s["sign"] else None,
                "ml": None,
            }
            key = (r["event_id"], r["item_seq"], n)
            if s["horizon"] == F.ML_HORIZON:
                got = ml_rows.get(key)
                code = reasons.get(key) or (
                    "OUTSIDE_TEST" if got is None else got.get("status")
                )
                if got is not None and got["status"] == "ESTIMATED":
                    view["ml"] = {**got, "reason": None, "reason_text": None}
                else:
                    view["ml"] = {
                        "status": "NONE",
                        "reason": code,
                        "reason_text": F.REASON_TEXT.get(code, code),
                        "block": (got or {}).get("block"),
                    }
            slots.append(view)
        out.append(
            {
                **{k: r[k] for k in _ITEM_FIELDS},
                "delivered": r["delivered"],
                "partial": r["partial"],
                "slots": slots,
            }
        )
    return out


def _versions() -> dict[str, Optional[str]]:
    out: dict[str, Optional[str]] = {}
    for dist in ("scikit-learn", "numpy"):
        try:
            out[dist] = metadata.version(dist)
        except metadata.PackageNotFoundError:
            out[dist] = None
    return out


def _short(status: str, end: Optional[str], **extra: Any) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": status,
        "status_text": STATUS_TEXT[status],
        "end_date": end,
        **extra,
    }


def run(end_date: Optional[str] = None) -> dict[str, Any]:
    """사후평가 1회 — 요약 + 산출물 위치. 사본 없음 · 손상은 산출물 없이 상태만."""
    started = time.perf_counter()
    cal = dates.calendar()
    end = _resolve_end(cal, end_date, _now().astimezone(KST).date().isoformat())
    acquired = _now()
    snap, problems = _read(_copy_path())
    if snap is None and problems is None:
        return _short(NO_COPY, end)
    asof = price_asof_date(cal, acquired)
    if asof is None:
        problems = (problems or []) + ["운영 캘린더로 가격 관측 기준일을 정할 수 없음"]
    if problems or snap is None or asof is None:
        return _short(CHECK_REQUIRED, end, problems=problems)
    pop = population.build(snap, cal, end=end, price_asof=asof)
    obs, reasons = F.observations(pop["items"])
    ml = model.evaluate(obs, cal, end)
    snapshot_doc = input_snapshot(pop, end, asof)
    digest = canonical_hash(snapshot_doc)
    scope = dict(sorted(Counter(reasons.values()).items()))
    created = _now()
    run_id = f"{created.strftime('%Y%m%dT%H%M%S%f')}_{uuid.uuid4().hex[:8]}"
    events = {r["event_id"] for r in pop["items"]}
    report = {
        **_short(OK, end),
        "run_id": run_id,
        "created_at": created.isoformat(timespec="seconds"),
        "snapshot_acquired_at": acquired.isoformat(timespec="seconds"),
        "price_asof_date": asof,
        "copy_sync": dict(snap.sync),
        "input_digest": digest,
        "summary": pop["summary"],
        "exclusions": pop["exclusions"],
        "ml": {
            "status": ml["status"],
            "reason": ml["reason"],
            "blocks": ml["blocks"],
            "overall": ml["overall"],
            "eligible_rows": len(obs),
            "not_eligible": scope,
        },
        "feedback_summary": {
            "events_with_feedback": len(pop["feedback"]),
            "events_without_feedback": len(events) - len(pop["feedback"]),
        },
        "feedback": pop["feedback"],
        "recipe": model.RECIPE,
        "libraries": _versions(),
        "notes": list(NOTES),
        "items": _item_views(pop, reasons, ml["rows"]),
    }
    report["runtime_seconds"] = round(time.perf_counter() - started, 3)
    _write(run_id, report, {"input_digest": digest, **snapshot_doc})
    return {
        **{k: v for k, v in report.items() if k not in ("items", "feedback")},
        "artifact": {"run_id": run_id, "files": "report.json · input_snapshot.json"},
    }


def _write(run_id: str, report: dict, snapshot_doc: dict) -> None:
    root = Path(RESEARCH_ROOT)
    folder = root / run_id
    staging = (
        root / f".{run_id}.partial"
    )  # 두 파일을 다 쓴 뒤에만 보이는 이름으로 바꾼다
    made = False
    try:
        root.mkdir(parents=True, exist_ok=True)
        staging.mkdir(exist_ok=False)
        made = True
        for fname, body in (
            ("report.json", report),
            ("input_snapshot.json", snapshot_doc),
        ):
            text = json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True)
            (staging / fname).write_text(text + "\n", encoding="utf-8")
        os.rename(staging, folder)
    except OSError as e:
        if made:  # 이 호출이 만든 임시 폴더만 지운다
            shutil.rmtree(staging, ignore_errors=True)
        raise ArtifactSaveError(f"연구 산출물 저장 실패: {type(e).__name__}") from e


def _latest_folder() -> Optional[Path]:
    root = Path(RESEARCH_ROOT)
    if not root.is_dir():
        return None
    done = [
        d
        for d in root.iterdir()
        if d.is_dir()
        and _FOLDER.match(d.name)
        and (d / "report.json").is_file()
        and (d / "input_snapshot.json").is_file()
    ]
    return max(done, key=lambda d: d.name) if done else None


def _input_check(report: dict[str, Any]) -> tuple[Optional[bool], str]:
    """지금 사본이 그 보고의 입력과 같은지 — 원래 종료일 · price_asof_date 로 digest 를 다시 잰다."""
    snap, problems = _read(_copy_path())
    if snap is None and problems is None:
        return None, "사본 없음 — 입력 변경을 확인할 수 없습니다"
    if problems or snap is None:
        return None, "사본 확인 필요 — 입력 변경을 확인할 수 없습니다"
    end, asof = report["end_date"], report["price_asof_date"]
    try:
        pop = population.build(snap, dates.calendar(), end=end, price_asof=asof)
        digest = canonical_hash(input_snapshot(pop, end, asof))
    except (
        TypeError,
        ValueError,
        KeyError,
    ) as e:  # 검사 밖 손상 — 조회는 기존 결과를 계속 보인다
        return (
            None,
            f"사본 확인 필요({type(e).__name__}) — 입력 변경을 확인할 수 없습니다",
        )
    changed = digest != report["input_digest"]
    return changed, ("입력이 변경됨 · 재실행 필요" if changed else "입력 변경 없음")


_REPORT_KEYS = {
    "end_date": str,
    "price_asof_date": str,
    "input_digest": str,
    "items": list,
    "feedback": dict,
}


def _load_report(folder: Path) -> Optional[dict[str, Any]]:
    """완성된 보고 파일 — 형식이 다르면 None(ARTIFACT_UNREADABLE)."""
    try:
        report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(report, dict):
        return None
    if report.get("schema") != SCHEMA or report.get("status") != OK:
        return None
    if not all(isinstance(report.get(k), t) for k, t in _REPORT_KEYS.items()):
        return None
    if not all(isinstance(i, dict) and "event_id" in i for i in report["items"]):
        return None
    return report


def latest(event_id: Optional[str] = None) -> dict[str, Any]:
    """완성된 최신 산출물 요약(+ 선택 알림의 항목 결과) · 입력 변경 표시. 쓰기 0."""
    folder = _latest_folder()
    if folder is None:
        return _short(NO_RESULT, None)
    report = _load_report(folder)
    if report is None:
        return _short(ARTIFACT_UNREADABLE, None, run_id=folder.name)
    changed, text = _input_check(report)
    out = {k: v for k, v in report.items() if k not in ("items", "feedback")}
    out.update(input_changed=changed, input_check=text)
    if event_id is not None:
        out["event"] = {
            "event_id": event_id,
            "items": [i for i in report["items"] if i["event_id"] == event_id],
            "feedback": report["feedback"].get(event_id),
        }
    return out
