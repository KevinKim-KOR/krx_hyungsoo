"""판단 한 건 = 한 파일(PLAN §2-4 · Q1 = b) — 한 번만 쓰기 · 그때 화면 · 복사문 원문 고정 · 목록 · 다시 열기.

```text
쓰기     state/ml/research/poc7_04/reviews/<review_id>.json
         — entry_timing.protocol.write_once(새 파일만 · 원자적)
고정     snapshot = 서버가 그 화면을 만들 때 둔 자료(후보 · 기준일 · 조회 조건 · 자료 지문 · 화면 조각 · 복사문 원문)
         — 브라우저가 보낸 값으로 근거를 만들지 않는다(브라우저는 화면 번호 build_id 와 판단 입력만 보냄)
판단     verdict = continue(검토 계속) · hold(보류) · unrecorded(미기록 · 기본) · 이유 · 다음 확인 · 쓴 근거 · AI 답
AI 답    v2(PLAN V2 판정 2026-11-26 §3) = ais — GPT · Gemini · Claude 중 답을 넣은 칸만(답 · 붙인 시각 · 질문 복사 시각 ·
         질문 출처 · 판단에 도움 여부) + excerpt(판단에 쓴 대목) · 답 없는 칸의 '도움' = 거절
         v1(예전 기록) = ai 하나(이름 · 답 · 대목 · 시각 · 출처) — 그대로 읽음 · 도움 여부 = 미기록
읽기     목록 = 파일마다 형식 검사 · 못 읽는 파일은 건너뛰고 이름을 남김(다른 기록은 그대로 보임)
```
"""

from __future__ import annotations

import math
import re
import stat
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from app.entry_timing.protocol import CheckRequired, dumps, new_id, write_once
from app.weekly_decision.conditions import loads_unique, stored_filters, text_ok
from app.weekly_decision.records import sane_date, sane_time

SCHEMA = "poc7_04_review_v2"
SCHEMA_V1 = "poc7_04_review_v1"  # 예전 기록(AI 답 하나) — 읽기만
ID_RE = re.compile(r"^\d{8}T\d{6}Z_[0-9a-f]{8}\Z")  # \Z — 끝의 줄바꿈도 받지 않음
VERDICTS = ("continue", "hold", "unrecorded")
AI_BOXES = ("GPT", "Gemini", "Claude")  # ③ 고정 칸(이 순서로 저장 · 보임)
USED_KEYS = ("rank_flow", "peer", "previous", "weeks", "ai_answer")
LIMITS = {"reason": 500, "next_check": 500, "ai_answer": 60000, "ai_excerpt": 4000}
MIXED = "mixed"
# 칸 이름(거절 문구 · 쉬운 한국어 · 반박 검토 D4)
LABELS = {
    "reason": "이유",
    "next_check": "다음 확인",
    "ai_answer": "AI 답",
    "ai_excerpt": "판단에 쓴 대목",
}
# 브라우저 String.prototype.trim 이 지우는 글자와 같은 집합 — 화면 '답 있음' 판정과 서버 판정을 맞춤(반박 검토 D3 ·
# 파이썬 str.strip 은 \x1c ~ \x1f · \x85 도 지우고 BOM 은 지우지 않아 서로 다름)
JS_WS = (
    "\t\n\x0b\x0c\r \xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007"
    "\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
)


def js_trim(v: str) -> str:
    return v.strip(JS_WS)


SIG_RE = re.compile(r"^[0-9a-f]{8}\Z")


class InputError(ValueError):
    """저장 요청 입력이 맞지 않음(쓰기 전 거절 — 아무것도 쓰지 않음)."""


def _text(
    body: Mapping[str, Any], key: str, *, keep: bool = False, label: str = ""
) -> str:
    """글 칸 — keep=True(AI 답 원문)는 앞뒤 공백 · 줄바꿈을 그대로 보관(공백만이면 빈 글 · 검증 F16).

    공백 = 브라우저 trim 과 같은 글자(js_trim) · 거절 문구는 쉬운 칸 이름(label · 없으면 LABELS)."""
    name = f"「{label or LABELS[key]}」 칸"
    v = body.get(key, "")
    if v is None:
        v = ""
    if not isinstance(v, str):
        raise InputError(f"{name}은 글이어야 합니다")
    try:
        v.encode("utf-8")
    # 짝 없는 대리 문자 — 저장할 수 없음(반박 검토 D1 · 쓰기 전)
    except UnicodeEncodeError:
        raise InputError(f"{name}에 저장할 수 없는 문자가 있습니다") from None
    v = (v if js_trim(v) else "") if keep else js_trim(v)
    if len(v) > LIMITS[key]:
        raise InputError(f"{name}이 너무 깁니다(최대 {LIMITS[key]:,}자)")
    return v


def _time_or_none(v: Any, what: str) -> Any:
    v = v or None
    if v is not None and not _is_time(v):
        raise InputError(f"{what} 형식이 올바르지 않습니다")
    return v


def _answer(x: Any) -> dict[str, Any]:
    """AI 답 칸 하나 — 형식이 틀리면 InputError(쓰기 전)."""
    if not isinstance(x, dict):
        raise InputError("AI 답 칸 형식이 올바르지 않습니다")
    if x.get("name") not in AI_BOXES:
        raise InputError("AI 이름 값이 올바르지 않습니다")
    answer = _text(
        {"ai_answer": x.get("answer", "")},
        "ai_answer",
        keep=True,
        label=f"{x['name']} 답",
    )
    helpful = x.get("helpful", False)
    if not isinstance(helpful, bool):
        raise InputError("'판단에 도움이 된 답' 값이 올바르지 않습니다")
    if helpful and not answer:
        raise InputError(
            f"{x['name']} 칸은 답이 없어 '판단에 도움이 된 답'으로 고를 수 없습니다"
        )
    # 답을 붙일 때 마지막으로 복사한 화면 번호 · 'mixed'(출처를 하나로 정할 수 없음) · 없음
    src = x.get("answer_from")
    if (
        src is not None
        and src != MIXED
        and not (isinstance(src, str) and ID_RE.match(src))
    ):
        raise InputError("AI 답의 질문 화면 번호 형식이 올바르지 않습니다")
    # 그 질문 원문의 지문(서버를 다시 켜 화면 번호를 모를 때 같은 질문인지 대조용)
    sig = x.get("answer_sig")
    if sig is not None and not (isinstance(sig, str) and SIG_RE.match(sig)):
        raise InputError("AI 답의 질문 지문 형식이 올바르지 않습니다")
    return {
        "name": x["name"],
        "answer": answer,
        "pasted_at": _time_or_none(x.get("pasted_at"), "붙인 시각"),
        # 답을 붙일 때 쓴 질문 복사의 시각(다시 열기에서 보임)
        "copied_at": _time_or_none(x.get("answer_copied_at"), "질문 복사 시각"),
        "answer_from": src,
        "answer_sig": sig,
        "helpful": helpful,
    }


def clean_decision(body: Mapping[str, Any]) -> dict[str, Any]:
    """브라우저 입력 → 저장할 판단(형식이 틀리면 InputError · 쓰기 전)."""
    verdict = body.get("verdict", "unrecorded")
    if verdict not in VERDICTS:
        raise InputError("판단 값이 올바르지 않습니다")
    used = body.get("used", [])
    if not isinstance(used, list) or any(u not in USED_KEYS for u in used):
        raise InputError("판단에 쓴 근거 값이 올바르지 않습니다")
    raw = body.get("ais", [])
    if not isinstance(raw, list) or len(raw) > len(AI_BOXES):
        raise InputError("AI 답 칸 형식이 올바르지 않습니다")
    got = [_answer(x) for x in raw]
    names = [a["name"] for a in got]
    if len(set(names)) != len(names):
        raise InputError("같은 AI 칸이 두 번 왔습니다")
    by = {a["name"]: a for a in got if a["answer"]}  # 답을 넣은 칸만 · 고정 순서
    return {
        "verdict": verdict,
        "reason": _text(body, "reason"),
        "next_check": _text(body, "next_check"),
        "used": [u for u in USED_KEYS if u in used],
        "ais": [by[n] for n in AI_BOXES if n in by],
        "excerpt": _text(body, "ai_excerpt"),
    }


def _unrecordable_why(e: Exception) -> str:
    if isinstance(e, CheckRequired):
        return "기록할 수 없는 수(NaN · 무한대)가 있음"
    if isinstance(e, UnicodeError):
        return "저장할 수 없는 문자가 있음"
    if isinstance(e, RecursionError):
        return "너무 깊게 중첩된 값이 있음"
    return f"저장할 수 없는 값이 있음({type(e).__name__})"


class Unrecordable(Exception):
    """저장할 글을 만들지 못함(NaN · 무한대 · 쓸 수 없는 문자 · 깊은 중첩) — 쓰기 전 거절(파일 0건 · 폴더 문제와 따로 · 검증 F21)."""


def save(
    root: Path,
    now: datetime,
    snapshot: Mapping[str, Any],
    decision: Mapping[str, Any],
    reopen: Optional[Callable[[Mapping[str, Any]], Any]] = None,
) -> dict[str, Any]:
    """판단 한 건 저장 — 쓰기 전에 목록 · 다시 열기와 똑같은 검사를 그 글에 돌려 보고 통과한 것만 쓴다.

    저장 성공 = 목록에 보이고 다시 열림(검증 F23 · 쓰기와 읽기가 같은 약속). reopen = 다시 열기 화면 만들기
    (서버가 넘김 · 화면 모듈을 여기서 가져오지 않음). 통과 못 하면 Unrecordable(쓰기 전 · 파일 0건)."""
    rid = new_id(now)
    doc = {
        "schema": SCHEMA,
        "review_id": rid,
        "saved_at": now.isoformat(timespec="seconds"),
        "decision": dict(decision),
        "snapshot": dict(snapshot),
    }
    path = Path(root) / "reviews" / f"{rid}.json"
    # 값 검사만 — 폴더 확인 · 쓰기(write_once)의 CheckRequired 와 섞지 않음(검증 F21)
    try:
        data = dumps(doc)
    except (CheckRequired, ValueError, TypeError, RecursionError, OverflowError) as e:
        raise Unrecordable(_unrecordable_why(e)) from e
    # 왕복 검사 — 쓸 글을 목록 · 다시 열기가 읽는 그대로 읽어 본다(같은 함수 · 같은 순서)
    try:
        # 목록 요약(summary)은 _checked 가 검사한 칸만 쓰므로 _checked 통과 = 목록에 보임
        back = _checked(loads_unique(data.decode("utf-8")), rid)
        if reopen is not None:
            reopen(back)
    except Exception as e:
        raise Unrecordable(
            f"저장해도 다시 열 수 없는 기록이라 저장하지 않음({type(e).__name__}: {e})"
        ) from e
    sha = write_once(Path(root), path, data)
    return {"review_id": rid, "sha256": sha, "path": str(path)}


def _need(ok: bool, what: str) -> None:
    if not ok:
        raise ValueError(what)


def _is_date(v: Any) -> bool:
    return sane_date(v) is not None  # 'YYYY-MM-DD' 그대로 · 범위 안


def _is_time(v: Any) -> bool:
    return (
        sane_time(v) is not None
    )  # 시간대 있음 · 범위 안 · KST 로 바꿀 수 있음(반박 검토 D2 · D7)


def _read(path: Path) -> str:
    """보통 파일만 읽음 — FIFO · 장치 파일을 읽다 서버가 멈추지 않게(반박 검토 D6).

    크기 상한은 두지 않는다 — 저장할 때 상한이 없으므로(「AI 투자 세션」 메모 길이에 상한이 없어 정상 저장도
    10MiB 를 넘을 수 있음) 읽을 때만 막으면 저장한 기록을 못 연다(검증 F23 · 쓰기와 읽기가 같은 약속)."""
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("보통 파일이 아님")
    return path.read_text(encoding="utf-8")


def shown_name(name: str) -> str:
    """화면에 보일 파일 이름 — UTF-8 로 쓸 수 없는 글자는 \\x.. 표기로(목록 화면이 실패하지 않게)."""
    return name.encode("utf-8", "backslashreplace").decode("utf-8")


def _checked(doc: Any, rid: str) -> dict[str, Any]:
    """다시 열기 · 목록이 쓰는 칸을 형까지 검사(틀리면 ValueError → 그 파일만 '읽지 못한 기록')."""
    _need(isinstance(doc, dict) and doc.get("schema") in (SCHEMA, SCHEMA_V1), "schema")
    # 글자를 쓸 수 없는 값(짝 없는 대리 문자)이 어디든 있으면 그 파일만 못 읽음(검증 F22)
    _need(text_ok(doc), "text")
    _need(doc.get("review_id") == rid, "review_id")
    _need(_is_time(doc.get("saved_at")), "saved_at")
    snap, dec = doc.get("snapshot"), doc.get("decision")
    _need(isinstance(snap, dict) and isinstance(dec, dict), "shape")
    _need(isinstance(snap.get("ticker"), str) and _is_date(snap.get("end")), "snapshot")
    _need(isinstance(snap.get("name"), (str, type(None))), "name")
    _need(
        isinstance(snap.get("filters", {}), dict) and isinstance(snap.get("copy"), str),
        "copy",
    )
    screen = snap.get("screen")
    _need(
        isinstance(screen, dict)
        and all(isinstance(screen.get(k), str) for k in ("sub", "one", "weeks", "ask")),
        "screen",
    )
    rv = snap.get("review", {})
    _need(isinstance(rv, dict), "review")
    rank = rv.get("rank")
    _need(
        rank is None or (isinstance(rank, int) and not isinstance(rank, bool)), "rank"
    )
    one = rv.get("one_month")
    _need(
        one is None
        or (
            isinstance(one, dict)
            and isinstance(one.get("value"), (int, float))
            and not isinstance(one.get("value"), bool)
            and math.isfinite(
                one["value"]
            )  # 아주 큰 정수 = OverflowError → 그 파일만 못 읽음
            and _is_date(one.get("start"))
            and _is_date(one.get("end"))
        ),
        "one_month",
    )
    _need(dec.get("verdict") in VERDICTS, "verdict")
    _need(
        all(isinstance(dec.get(k), str) for k in ("reason", "next_check"))
        and isinstance(dec.get("used"), list)
        and all(u in USED_KEYS for u in dec["used"]),
        "decision",
    )
    if doc["schema"] == SCHEMA_V1:
        ai = dec.get("ai")
        _need(
            isinstance(ai, dict)
            and all(isinstance(ai.get(k), str) for k in ("name", "answer", "excerpt"))
            and _time_ok(ai, "pasted_at")
            and _time_ok(ai, "copied_at")
            and isinstance(ai.get("asked", {}), dict),
            "ai",
        )
        return doc
    ais = dec.get("ais")
    _need(isinstance(ais, list) and isinstance(dec.get("excerpt"), str), "ais")
    names = []
    for a in ais:
        _need(
            isinstance(a, dict)
            and a.get("name") in AI_BOXES
            and isinstance(a.get("answer"), str)
            # 저장할 때와 같은 '답 있음' 규칙(왕복 검사가 찾은 비대칭)
            and bool(js_trim(a["answer"]))
            and isinstance(a.get("helpful"), bool)
            and _time_ok(a, "pasted_at")
            and _time_ok(a, "copied_at")
            and isinstance(a.get("asked"), dict),
            "ai",
        )
        names.append(a["name"])
    _need(len(set(names)) == len(names), "ai")
    return doc


def _time_ok(x: Mapping[str, Any], key: str) -> bool:
    return x.get(key) is None or _is_time(x.get(key))


def load(root: Path, rid: str) -> dict[str, Any]:
    """다시 열기 — 이름 형식 · 내용 형식이 맞을 때만(아니면 KeyError · ValueError)."""
    if not ID_RE.match(rid or ""):
        raise KeyError(rid)
    path = Path(root) / "reviews" / f"{rid}.json"
    if not path.is_file():
        raise KeyError(rid)
    return _checked(loads_unique(_read(path)), rid)


def summary(doc: Mapping[str, Any]) -> dict[str, Any]:
    snap, dec = doc["snapshot"], doc["decision"]
    rv = snap.get("review") or {}
    return {
        "review_id": doc["review_id"],
        "saved_at": doc["saved_at"],
        "ticker": snap["ticker"],
        "name": snap.get("name"),
        "end": snap["end"],
        # 칸마다 불리언만 그대로 — 손으로 고친 NaN 등이 새 스냅숏에 들어가지 않게(반박 검토 D2)
        "filters": stored_filters(snap.get("filters") or {}),
        "verdict": dec["verdict"],
        "reason": dec.get("reason") or "",
        **ai_summary(doc),
        "rank": rv.get("rank"),
        # 검사한 세 칸만 — 원값(덧붙은 칸 · 깊은 중첩 · NaN)이 새 스냅숏에 들어가지 않게(반박 검토 D2)
        "one_month": (
            {k: rv["one_month"][k] for k in ("value", "start", "end")}
            if rv.get("one_month")
            else None
        ),
    }


def ai_summary(doc: Mapping[str, Any]) -> dict[str, Any]:
    """저장 목록 한 줄의 AI 답 요약 — 답 개수 · 판단에 도움이 된 답(예전 기록 = None · 미기록)."""
    dec = doc["decision"]
    if doc["schema"] == SCHEMA_V1:
        # 다시 열기와 같은 '답 있음' 규칙(js_trim · 반박 검토 L5)
        return {"ai_count": 1 if js_trim(dec["ai"]["answer"]) else 0, "helpful": None}
    return {
        "ai_count": len(dec["ais"]),
        "helpful": [a["name"] for a in dec["ais"] if a["helpful"]],
    }


def list_reviews(root: Path) -> dict[str, Any]:
    """저장한 판단 목록(최근 저장 먼저) · 못 읽은 파일 이름."""
    d = Path(root) / "reviews"
    items, broken = [], []
    if d.is_dir():
        for p in sorted(d.glob("*.json")):
            rid = p.stem
            try:
                if not ID_RE.match(rid):
                    raise ValueError("name")
                items.append(summary(_checked(loads_unique(_read(p)), rid)))
            # 손상된 파일 하나는 그 파일만(어떤 손상이든 목록 · 화면 전체를 막지 않음)
            except Exception:
                broken.append(shown_name(p.name))
    # 글자 순 말고 시각 순(표기가 달라도 · 반박 검토 D5) — 검사를 통과한 시각만 남아 있음
    items.sort(key=lambda s: (sane_time(s["saved_at"]), s["review_id"]), reverse=True)
    return {"items": items, "broken": broken}
