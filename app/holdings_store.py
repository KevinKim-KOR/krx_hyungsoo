"""POC5-05 개정 2 — 보유 문서 저장 경계(PC). 모든 PC 보유 쓰기는 commit() 하나를 지난다.

설계 §5 · PLAN §2-3:
- 정본 = state/holdings/holdings_latest.json 한 문서. 형식:
  {schema_version: 2, revision, holdings(계산 결과 · 호환용), personal_trade_history:
   {positions, records}}.
- 읽기 상태: NO_FILE / V1(기존 형식) / V2. 손상(JSON · 구조 · 검증 실패)은 예외 —
  빈 보유로 바꾸지 않고, 손상 파일 위에 쓰지 않는다.
- V1 은 revision 0 으로 읽는다. 줄 ID 는 '파일 내용 sha + 줄 순번' 에서 만든 결정적
  uuid5 이고, 기준잔고(BASELINE)는 저장하지 않은 '가상 기록' 이다. 첫 명시적 변경 때
  그대로 저장된다(조회 · 기동은 아무것도 쓰지 않는다).
- 쓰기: 프로세스 내 threading.Lock(PC backend = uvicorn 단일 프로세스) → 최신 문서 읽기 →
  변경 함수 → 같은 디렉터리 임시 파일 · fsync → os.replace. 교체 전 실패면 기존 파일 그대로.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Optional

from app import holdings as holdings_module
from app import holdings_book

SCHEMA_VERSION = 2
_LOCK = threading.Lock()
_KST = timezone(timedelta(hours=9))
_NS = uuid.UUID("6f1d3c52-7a43-4c39-9a51-2f0c0b5d5e05")


class DocumentCorrupt(Exception):
    """보유 파일을 읽을 수 없음(손상 · 구조 · 검증 실패) — 빈 보유로 바꾸지 않는다."""


def now_kst() -> str:
    return datetime.now(_KST).isoformat(timespec="seconds")


def today_kst() -> str:
    return datetime.now(_KST).date().isoformat()


def _path() -> Path:
    # 호출 때 해석 — conftest 가 holdings.HOLDINGS_FILE 을 tmp 로 바꿔 끼운다.
    return holdings_module.HOLDINGS_FILE


def _decimal_text(value: float) -> str:
    """기존 float 값을 읽은 그대로의 십진 문자열로(정밀도 손실 복원이 아님)."""
    return holdings_book.fmt(Decimal(repr(float(value))))


def _v1_view(raw: bytes, data: dict[str, Any]) -> dict[str, Any]:
    try:
        rows = holdings_module.validate_holdings(data["holdings"], allow_empty=True)
    except holdings_module.HoldingsValidationError as e:
        raise DocumentCorrupt(str(e)) from e
    sha = hashlib.sha256(raw).hexdigest()
    positions, records = [], []
    for i, h in enumerate(rows):
        pid = str(uuid.uuid5(_NS, f"{sha}:{i}:position"))
        cid = str(uuid.uuid5(_NS, f"{sha}:{i}:cycle"))
        positions.append(
            {
                "position_id": pid,
                "ticker": h.ticker,
                "account_group": h.account_group,
                "name": h.name,
            }
        )
        records.append(
            {
                "record_id": str(uuid.uuid5(_NS, f"{sha}:{i}:baseline")),
                "request_id": None,
                "request_hash": None,
                "recorded_at": None,
                "kind": "BASELINE",
                "position_id": pid,
                "cycle_id": cid,
                "supersedes_id": None,
                "payload": {
                    "quantity": _decimal_text(h.quantity),
                    "avg_buy_price": _decimal_text(h.avg_buy_price),
                },
                "virtual": True,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "revision": 0,
        "holdings": [],
        "personal_trade_history": {"positions": positions, "records": records},
    }


def read_document() -> dict[str, Any]:
    """{status: NO_FILE|V1|V2, doc}. 손상이면 DocumentCorrupt. 아무것도 쓰지 않는다."""
    path = _path()
    if not path.exists():
        empty = {
            "schema_version": SCHEMA_VERSION,
            "revision": 0,
            "holdings": [],
            "personal_trade_history": {"positions": [], "records": []},
        }
        return {"status": "NO_FILE", "doc": empty}
    raw = path.read_bytes()
    try:
        data = json.loads(raw.decode("utf-8"))
    except ValueError as e:
        raise DocumentCorrupt(f"보유 파일 JSON 손상: {e}") from e
    if not isinstance(data, dict) or not isinstance(data.get("holdings"), list):
        raise DocumentCorrupt(
            "보유 파일 구조가 올바르지 않습니다('holdings' 목록 없음)."
        )
    if not holdings_module.is_history_document(data):
        return {"status": "V1", "doc": _v1_view(raw, data)}
    hist = data.get("personal_trade_history")
    if (
        data.get("schema_version") != SCHEMA_VERSION
        or not isinstance(data.get("revision"), int)
        or not isinstance(hist, dict)
        or not isinstance(hist.get("positions"), list)
        or not isinstance(hist.get("records"), list)
    ):
        raise DocumentCorrupt("보유 · 이력 문서 형식이 올바르지 않습니다.")
    try:  # holdings = 이력으로 다시 계산한 결과여야 한다(아니면 손상 · 쓰기도 거절)
        holdings_module.holdings_from_document(data)
    except holdings_module.HoldingsValidationError as e:
        raise DocumentCorrupt(str(e)) from e
    return {"status": "V2", "doc": data}


def materialize(doc: dict[str, Any], at: str) -> None:
    """V1 가상 기준잔고를 저장할 기록으로 확정한다(첫 명시적 변경 때 · 제자리 수정)."""
    for r in doc["personal_trade_history"]["records"]:
        if r.pop("virtual", False):
            r["recorded_at"] = at


def _atomic_write(doc: dict[str, Any]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(doc, indent=2, ensure_ascii=False).encode("utf-8")
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".holdings-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(body)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def commit(
    change: Callable[[dict[str, Any]], tuple[Any, Optional[dict[str, Any]]]],
) -> Any:
    """잠금 안에서 최신 문서를 읽어 change(state) → (응답, 새 문서 | None). None 이면 쓰지 않음."""
    with _LOCK:
        state = read_document()
        result, new_doc = change(state)
        if new_doc is not None:
            try:  # 쓰기 직전 같은 판정 — 읽을 때 손상이 될 문서는 쓰지 않는다
                holdings_module.holdings_from_document(new_doc)
            except holdings_module.HoldingsValidationError as e:
                raise DocumentCorrupt(f"저장할 문서가 올바르지 않습니다: {e}") from e
            _atomic_write(new_doc)
        return result
