"""POC7-04 — 저장 기록 읽기 · 형식 · 범위 검사 한 곳(검증 F22 · 반박 검토 · history 600줄 근접에서 나눔).

「AI 투자 세션」 저장 행(판단 근거 DB · 읽기 전용)과 내 판단 파일의 날짜 · 시각은 여기서 검사한다.
한 행 · 한 파일은 엄격한 형식을 모두 통과해야 쓴다. 하나라도 어긋나면 그 한 건만 '못 읽은 기록'이다
— 칸의 저장 종류(글 · 비어 있음) · UTF-8 · 짝 없는 대리 문자 · 같은 칸 충돌 · 날짜 표기와 범위 ·
시각의 시간대와 범위 · 판단 값.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from app.decision_evidence_store import ALLOWED_USER_VERDICTS, default_user_verdict
from app.weekly_decision.conditions import has_clash, loads, stored_filters, text_ok

KST = timezone(timedelta(hours=9))
# 이 도구가 다루는 기록 날짜 범위 — 밖이면 손상으로 봄(날짜 계산 넘침 방지 · 반박 검토 D1 · D2)
YEARS = (1990, 2100)
COLUMNS = (
    "id",
    "created_at",
    "asof",
    "source_screen",
    "filters_json",
    "candidate_snapshot_json",
    "user_verdict",
    "user_memo",
    "next_checks_json",
    "gpt_answer_text",
    "gemini_answer_text",
    "claude_answer_text",
)
REQUIRED = 7  # 앞 일곱 칸은 반드시 글 · 나머지는 글 또는 비어 있음
SESSION_SQL = (
    "SELECT "
    + ", ".join(f"typeof({c}), {c}" for c in COLUMNS)
    + " FROM ai_session_records ORDER BY created_at, id"
)


def sane_date(v: Any) -> Optional[str]:
    """'YYYY-MM-DD' 표기 그대로이고 범위 안인 날짜만(아니면 None)."""
    if not isinstance(v, str):
        return None
    try:
        d = dt.date.fromisoformat(v)
    except ValueError:
        return None
    return v if d.isoformat() == v and YEARS[0] <= d.year <= YEARS[1] else None


def sane_time(v: Any) -> Optional[datetime]:
    """시간대가 있는 ISO 시각 · 범위 안 · KST 로 바꿀 수 있는 것만 → KST 시각(아니면 None)."""
    if not isinstance(v, str):
        return None
    try:
        t = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if t.tzinfo is None or not YEARS[0] <= t.year <= YEARS[1]:
            return None
        return t.astimezone(KST)
    except (ValueError, OverflowError):
        return None


def num_or_none(v: Any) -> Optional[float]:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    try:
        f = float(v)
    except OverflowError:  # 아주 큰 정수
        return None
    return f if math.isfinite(f) else None


def int_or_none(v: Any) -> Optional[int]:
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _row(raw: tuple) -> tuple:
    """(저장 종류, 값) 쌍 → 값들 — 앞 일곱 칸은 글 · 나머지는 글 또는 비어 있음 · 글은 UTF-8 로 엄격하게 푼다.

    같은 값이라도 BLOB · 정수로 들어간 칸은 받지 않는다(같은 id 가 둘로 보이는 일 · 반박 검토 D3)."""
    out = []
    for i in range(len(COLUMNS)):
        kind, v = raw[2 * i], raw[2 * i + 1]
        kind = kind.decode("ascii") if isinstance(kind, bytes) else kind
        if kind == "null" and i >= REQUIRED:
            out.append(None)
        elif kind == "text":
            out.append(v.decode("utf-8"))
        else:
            raise ValueError(f"{COLUMNS[i]} 저장 종류 {kind}")
    return tuple(out)


def _session(r: tuple) -> dict[str, Any]:
    asof = sane_date(r[2])
    if asof is None:
        raise ValueError("asof")
    if sane_time(r[1]) is None:
        raise ValueError("created_at")
    # 손상된 판단 글을 '직접 고름'으로 보이지 않게(반박 검토 D4)
    if r[6] not in ALLOWED_USER_VERDICTS:
        raise ValueError("user_verdict")
    # 같은 칸이 서로 다른 값으로 두 번 있으면 마지막 값으로 덮지 않음(검증 F20 · conditions.loads)
    filters = loads(r[4])
    cands = loads(r[5])
    nexts = json.loads(r[8] or "[]")
    if not isinstance(filters, dict) or not isinstance(cands, list):
        raise ValueError("shape")
    # 후보 칸 충돌 · 원래 칸 어디든 짝 없는 대리 문자 — 원래 값을 알 수 없음(반박 검토 D5 · 검증 F22)
    if has_clash(cands) or not text_ok([filters, cands, nexts]):
        raise ValueError("candidate")
    items = []
    for c in cands:
        if not isinstance(c, dict):
            raise ValueError("item")
        spk = c.get("same_period_kodex200")
        k1 = spk.get("one_month") if isinstance(spk, dict) else None
        if not isinstance(k1, dict):
            k1 = {}
        items.append(
            {
                "ticker": c.get("ticker") if isinstance(c.get("ticker"), str) else None,
                "name": c.get("name") if isinstance(c.get("name"), str) else None,
                "rank": int_or_none(c.get("rank")),
                "one_month": num_or_none(c.get("one_month_return_pct")),
                "start": sane_date(k1.get("start_date")),
                "end": sane_date(k1.get("end_date")),
            }
        )
    # 같은 ETF 가 두 번 — 값이 모두 같으면 하나로(같은 칸 같은 값 두 번 = 그 값과 같은 규칙 · 반박 검토 L2) ·
    # 다르면 어느 항목인지 알 수 없어 그 행만 못 읽음
    by: dict[str, dict[str, Any]] = {}
    kept = []
    for it in items:
        t = it["ticker"]
        if t is not None and t in by:
            if by[t] != it:
                raise ValueError("duplicate ticker")
            continue
        if t is not None:
            by[t] = it
        kept.append(it)
    items = kept
    source = r[3]
    answers = [
        n
        for n, t in (("GPT", r[9]), ("Gemini", r[10]), ("Claude", r[11]))
        if (t or "").strip()
    ]
    rec = {
        "id": r[0],
        "created_at": r[1],
        "asof": asof,
        "source": source,
        # 참 · 거짓 판정은 filter_value 한 곳(검증 F18) · 원값 대신 표시만(반박 검토 D1)
        "filters": stored_filters(filters),
        "items": items,
        "verdict": r[6],
        "default_verdict": default_user_verdict(source),
        "memo": r[7] or "",
        "next_checks": (
            [x for x in nexts if isinstance(x, str)] if isinstance(nexts, list) else []
        ),
        "answers": answers,
    }
    # 글자를 쓸 수 없는 값(짝 없는 대리 문자) — 그 행만 못 읽음(검증 F22)
    if not text_ok(rec):
        raise ValueError("text")
    return rec


def read_sessions(path: Path) -> dict[str, Any]:
    """「AI 투자 세션」 저장 기록 전부(읽기 전용 연결) — 못 읽는 행은 건너뛰고 개수를 남긴다."""
    p = Path(path)
    if not p.exists():
        return {"state": "missing", "records": [], "broken": 0}
    try:
        uri = p.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as con:
            # 글은 바이트로 받아 행마다 푼다 — 한 행의 깨진 글자가 전체 조회를 막지 않게(검증 F22)
            con.text_factory = bytes
            rows = con.execute(SESSION_SQL).fetchall()
    except sqlite3.Error as e:
        return {"state": "error", "records": [], "broken": 0, "error": type(e).__name__}
    out, broken = [], 0
    for r in rows:
        try:
            out.append(_session(_row(r)))
        # 손상된 행 하나는 그 행만 못 읽은 기록(어떤 손상이든 화면 전체를 막지 않음)
        except Exception:
            broken += 1
    return {"state": "ok", "records": out, "broken": broken}
