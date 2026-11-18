"""POC6-32 — 마지막 기록의 AI 답 대조(PLAN V2 §4-3 · 판정 V2 §2 · Q5 · §9 I-14 · I-15).

규칙만 쓴다(자동 AI 호출 · 글 뜻 비교 없음 · AI 답은 의견 · KS-4).
- 질문 원문에서 근거 번호(`[근거 n]` 줄 머리)와 대상 ETF(`대상 ETF:` 줄)를 읽는다 — 그 기록이 실제로 보낸 글이 기준.
- 답마다(AI 칸마다):
  · 최신 확인 = `최신 확인:` 줄에서 같음 · 새 값 있음 · 확인 불가 중 정확히 하나 · 줄이 없거나 두 번 이상이거나
    하나로 읽을 수 없으면 '형식 없음'.
  · 확인한 항목 줄(`- 항목: … · 값: … · 기준일: … · 출처: … · 확인 시각: … · 달라지는 해석: …`)은 답마다 원문 그대로
    남기고, 이름 붙은 칸을 읽는다(칸 위치가 아니라 칸 이름으로 · I-15). 확인 시각이 비면 '확인 시각 미기재'
    (AI 가 적은 시각 · 저장 시각과 따로 · Q5). 칸 이름만 옮긴 형식 글('…')은 항목으로 세지 않는다.
- 붙여넣은 답을 `[ETF 코드]` 칸으로 나누고 상태 · 인용 근거 · 이유 · 다음 확인을 읽는다.
- 같은 ETF 의 **상태**와 **인용 근거 번호**를 대조한다 — 상태 같음/다름 · 번호는 모두 같은 번호(교집합)와 답마다 다른
  번호. 확인된 답이 하나면 '한 의견'. 상태가 셋 중 하나로 읽히지 않거나 인용 근거가 없거나 글에 없는 번호면 그 칸은
  '요약 확인 필요'. 답 칸이 비면 '답 없음'.
- 같은 ETF 칸 두 번 · 한 칸 안 같은 칸 이름 두 번 = '요약 확인 필요'(첫 칸을 조용히 고르지 않음 · V1 규칙 그대로).
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Mapping, Optional

from app.weekly_review_text import (
    FIELDS,
    ITEM_FIELDS,
    LATEST_STATES,
    STATES,
    TARGETS_HEAD,
)

AIS = (("gpt", "GPT"), ("gemini", "Gemini"), ("claude", "Claude"))
AI_LABEL = dict(AIS)
NO_RECORD = "이 화면에서 저장한 기록 없음"
NO_FORMAT = "형식 없음"
NO_TIME = "확인 시각 미기재"
ONE_OPINION = "한 의견"
NEEDS_CHECK = "요약 확인 필요"
SHORT_MAX = 140
_EVIDENCE_RE = re.compile(r"^\[근거 (\d+)\]", re.M)
_TICKER = r"[0-9A-Z]{6}"
# ETF 칸 머리 = 줄 머리(글머리 · 번호 · 제목 표시를 지운 뒤)가 'ETF' + 질문의 대상 코드 — 괄호 · 이름 · 콜론이 붙어도 됨.
# 지금 칸과 같은 코드면 머리가 아니라 이어진 글('ETF 476070 은 …'). 대상이 아닌 코드도 머리가 아님(검토 F1).
_HEAD_RE = re.compile(rf"^[\[【(]?\s*ETF\s*[:：]?\s*({_TICKER})(?![0-9A-Z])")
_FIELD_RE = re.compile(rf"^({'|'.join(FIELDS)})\s*(?:\([^)]*\))?\s*[:：]\s*(.*)$")
_LATEST_RE = re.compile(r"^최신\s*확인\s*[:：]\s*(.*)$")
_ITEM_RE = re.compile(r"^항목\s*[:：]")
# 항목 줄의 칸 이름 — 줄 처음이나 구분 글자 뒤에서만(값 속 'https:' · '10:05' 는 칸 이름이 아님)
_ITEM_LABEL_RE = re.compile(
    r"(?:^|(?<=[\s·|,;/]))("
    + "|".join(label.replace(" ", r"\s*") for label, _ in ITEM_FIELDS)
    + r")\s*[:：]"
)
_ITEM_KEY = {label.replace(" ", ""): key for label, key in ITEM_FIELDS}
_BLANK_RE = re.compile(r"^[\s\-–—·.…]*$")
_MARK_RE = re.compile(r"[*_`]")
_LEAD_RE = re.compile(r"^(?:[\s>#\-•·]+|\d+[.)]\s+)+")
_DUP_BLOCK = "\x00dup_block"
_DUP_FIELD = "\x00dup_field"
_CITE_SPLIT = re.compile(r"[,，、/·;]+")
_RANGE_MAX = 50


def _clean(line: str) -> str:
    return _LEAD_RE.sub("", _MARK_RE.sub("", line)).strip()


def parse_question(text: str) -> Optional[dict[str, Any]]:
    valid = {int(n) for n in _EVIDENCE_RE.findall(text or "")}
    head = next(
        (ln for ln in (text or "").splitlines() if ln.startswith(TARGETS_HEAD)), None
    )
    targets = re.findall(_TICKER, head.removeprefix(TARGETS_HEAD)) if head else []
    if not valid or not targets:
        return None
    return {"valid": valid, "targets": list(dict.fromkeys(targets))}


def _scan(
    answer: str, targets: list[str]
) -> tuple[dict[str, dict[str, str]], list[str], list[str]]:
    """답 글 → ({ETF 코드: {칸: 글}}, 최신 확인 줄 값들, 항목 줄 원문들).

    같은 ETF 칸이 두 번 · 한 칸 안에 같은 칸 이름이 두 번이면 표시만 남긴다(첫 칸을 조용히 고르지 않음 · 머리를 못 읽어
    다음 ETF 답이 앞 칸에 섞인 경우도 같은 칸 이름이 두 번이 됨). 최신 확인 · 항목 줄은 어디에 있어도 답 전체의 줄로
    읽고, 그 앞 칸의 이어진 글로 붙이지 않는다."""
    out: dict[str, dict[str, str]] = {}
    latest: list[str] = []
    items: list[str] = []
    cur_t: Optional[str] = None
    cur: Optional[dict[str, str]] = None
    field: Optional[str] = None
    for raw in answer.splitlines():
        line = _clean(raw)
        lm = _LATEST_RE.match(line)
        if lm:
            latest.append(lm.group(1).strip())
            field = None
            continue
        if _ITEM_RE.match(line):
            items.append(raw)
            field = None
            continue
        m = _HEAD_RE.match(line)
        if m and m.group(1) in targets and m.group(1) != cur_t:
            cur_t, cur, field = m.group(1), {}, None
            if cur_t in out:
                # 두 번째 칸은 읽기만 하고 버림(첫 칸도 쓰지 않음)
                out[cur_t][_DUP_BLOCK] = "1"
            else:
                out[cur_t] = cur
            continue
        if cur is None:
            continue
        f = _FIELD_RE.match(line)
        if f:
            field = f.group(1)
            if field in cur and _DUP_FIELD not in cur:
                cur[_DUP_FIELD] = field  # 처음 겹친 칸 이름
            cur[field] = f.group(2).strip()
        elif field and line:
            cur[field] = f"{cur[field]} {line}".strip()
    return out, latest, items


def parse_cited(value: str) -> Optional[list[int]]:
    """인용 근거 칸 → 번호 목록. '근거 2, 5' · '[근거 2] · [근거 5]' · '2번 5번' · '1 ~ 4'(범위)를 읽고,
    번호 밖 글(괄호 안 '6개월' 등)이 섞이면 None(요약 확인 필요 · 검토 F2)."""
    v = _MARK_RE.sub("", value or "")
    v = re.sub(r"[\[\]【】]", " ", v)
    v = re.sub(r"근거\s*", "", v)
    v = re.sub(r"(\d)\s*번", r"\1", v)
    nums: set[int] = set()
    for piece in _CITE_SPLIT.split(v):
        p = piece.strip()
        if not p:
            continue
        if re.fullmatch(r"\d+(?:\s+\d+)*", p):
            nums.update(int(x) for x in p.split())
            continue
        r = re.fullmatch(r"(\d+)\s*[~\-–]\s*(\d+)", p)
        if r and int(r.group(1)) <= int(r.group(2)) <= int(r.group(1)) + _RANGE_MAX:
            nums.update(range(int(r.group(1)), int(r.group(2)) + 1))
            continue
        return None
    return sorted(nums) or None


def _short(s: Optional[str]) -> Optional[str]:
    s = (s or "").strip()
    if not s:
        return None
    return s if len(s) <= SHORT_MAX else s[: SHORT_MAX - 1] + "…"


def parse_latest(values: list[str]) -> dict[str, Any]:
    """최신 확인 줄 → {state: 같음 | 새 값 있음 | 확인 불가 | 형식 없음, raw, reason}."""
    if not values:
        return {"state": NO_FORMAT, "raw": None, "reason": "최신 확인 줄 없음"}
    raw = _short(values[0])
    if len(values) > 1:
        return {
            "state": NO_FORMAT,
            "raw": raw,
            "reason": "최신 확인 줄이 두 번 이상 나옴",
        }
    flat = re.sub(r"\s+", "", values[0])
    found = [s for s in LATEST_STATES if s.replace(" ", "") in flat]
    if len(found) != 1:
        why = " · ".join(LATEST_STATES) + " 중 하나로 읽을 수 없음"
        return {"state": NO_FORMAT, "raw": raw, "reason": why}
    return {"state": found[0], "raw": raw, "reason": None}


def parse_item(raw: str) -> Optional[dict[str, Any]]:
    """확인 항목 줄 → 원문 그대로 + 이름 붙은 칸(I-15). 항목 칸이 비거나 '…'(형식 글을 옮김)이면 None.

    칸 값 = 그 칸 이름 뒤부터 다음 칸 이름 앞까지(같은 칸 이름이 다시 나오면 첫 번째만 칸으로 봄 · 값 속 글로 둠)."""
    line = _LEAD_RE.sub("", re.sub(r"[*`]", "", raw)).strip()
    marks: list[tuple[str, int, int]] = []
    for m in _ITEM_LABEL_RE.finditer(line):
        key = _ITEM_KEY[re.sub(r"\s+", "", m.group(1))]
        if all(key != k for k, _, _ in marks):
            marks.append((key, m.start(), m.end()))
    vals: dict[str, Optional[str]] = {key: None for _, key in ITEM_FIELDS}
    for i, (key, _start, end) in enumerate(marks):
        stop = marks[i + 1][1] if i + 1 < len(marks) else len(line)
        v = line[end:stop].strip(" \t·|,;")
        vals[key] = None if _BLANK_RE.match(v) else v
    if not vals["item"]:
        return None
    return {
        "line": raw.strip(),
        **vals,
        "checked_at_text": vals["checked_at"] or NO_TIME,
    }


def parse_cell(block: Optional[Mapping[str, str]], valid: set[int]) -> dict[str, Any]:
    if block is None:
        return {"status": "needs_check", "reason": "이 ETF 칸이 없음"}
    if _DUP_BLOCK in block:
        return {"status": "needs_check", "reason": "같은 ETF 칸이 두 번 나옴"}
    if _DUP_FIELD in block:
        return {
            "status": "needs_check",
            "reason": f"'{block[_DUP_FIELD]}' 칸이 두 번 나옴(다른 ETF 칸 머리를 읽지 못했을 수 있음)",
        }
    raw_state = block.get("상태", "")
    found = [s for s in STATES if s in raw_state]
    if len(found) != 1:
        return {"status": "needs_check", "reason": "상태를 셋 중 하나로 읽을 수 없음"}
    cited = parse_cited(block.get("인용 근거", ""))
    if not cited or any(n not in valid for n in cited):
        return {"status": "needs_check", "reason": "인용 근거 번호 확인 불가"}
    return {
        "status": "ok",
        "state": found[0],
        "cited": cited,
        "why": _short(block.get("이유")),
        "next_check": _short(block.get("다음 확인")),
    }


def _nos(ns: list[int]) -> str:
    return ", ".join(str(n) for n in ns)


def _row(t: str, name: Optional[str], cells: dict[str, dict]) -> dict[str, Any]:
    ok = [(k, c) for k, c in cells.items() if c["status"] == "ok"]
    row: dict[str, Any] = {
        "ticker": t,
        "name": name,
        "cells": cells,
        "ok_count": len(ok),
        "state_same": None,
        "cited_same": None,
        "cited_common": None,
        "cited_only": None,
        "cited_text": None,
    }
    if not ok:
        unread = any(c["status"] == "needs_check" for c in cells.values())
        row["state_text"] = NEEDS_CHECK if unread else "대조할 답 없음"
        return row
    if len(ok) == 1:
        row["state_text"] = ONE_OPINION
        return row
    cnt = Counter(c["state"] for _, c in ok)
    common = sorted(set.intersection(*(set(c["cited"]) for _, c in ok)))
    only = {k: sorted(set(c["cited"]) - set(common)) for k, c in ok}
    row["state_same"] = len(cnt) == 1
    row["cited_same"] = not any(only.values())
    row["cited_common"], row["cited_only"] = common, only
    row["state_text"] = (
        f"상태 같음({ok[0][1]['state']})"
        if row["state_same"]
        else "상태 다름(" + " · ".join(f"{s} {cnt[s]}" for s in STATES if cnt[s]) + ")"
    )
    row["cited_text"] = (
        "인용 근거 번호 일치"
        if row["cited_same"]
        else f"같은 번호 {_nos(common) or '없음'} · 다른 번호 "
        + " / ".join(f"{AI_LABEL[k]} {_nos(v)}" for k, v in only.items() if v)
    )
    return row


def compare(
    question_text: str, answers: Mapping[str, str], names: Mapping[str, str]
) -> dict[str, Any]:
    """질문 원문 + AI 답 3칸 → 답마다 최신 확인 · 항목 줄(질문 형식과 무관하게 읽음) + ETF 마다 대조 행."""
    q = parse_question(question_text)
    targets = q["targets"] if q else []
    scanned = {
        key: (
            _scan(answers.get(key) or "", targets)
            if (answers.get(key) or "").strip()
            else None
        )
        for key, _ in AIS
    }
    views: dict[str, dict[str, Any]] = {}
    for key, _ in AIS:
        sc = scanned[key]
        if sc is None:
            views[key] = {"status": "no_answer"}
            continue
        items = [it for it in (parse_item(r) for r in sc[2]) if it is not None]
        views[key] = {"status": "ok", "latest": parse_latest(sc[1]), "items": items}
    answered = [key for key, _ in AIS if scanned[key] is not None]
    n = len(answered)
    base = {
        "answers": views,
        "answer_count": n,
        "opinion_text": (
            "AI 답 없음" if n == 0 else (ONE_OPINION if n == 1 else f"AI 답 {n}개")
        ),
        "latest_text": " · ".join(
            f"{AI_LABEL[k]} {views[k]['latest']['state']}" for k in answered
        )
        or None,
    }
    if q is None:
        return {
            "status": "no_format",
            "message": f"질문 원문에서 근거 번호 · 대상 ETF 를 찾지 못했습니다 — {NEEDS_CHECK}(원문은 「AI 투자 세션」)",
            "rows": [],
            **base,
        }
    rows = []
    for t in q["targets"]:
        cells = {}
        for key, _ in AIS:
            sc = scanned[key]
            cells[key] = (
                {"status": "no_answer"}
                if sc is None
                else parse_cell(sc[0].get(t), q["valid"])
            )
        rows.append(_row(t, names.get(t), cells))
    return {"status": "ok", "message": None, "rows": rows, **base}


def _selected(rec: Mapping[str, Any]) -> dict[str, Any]:
    """저장한 고른 후보(`data_quality_snapshot.selected`) — ok(코드 · 이름) · none(고르지 않고 넘김) ·
    unknown(그 칸이 없거나 모양이 다른 기록 · '없음'으로 바꾸지 않음)."""
    dq = rec.get("data_quality_snapshot")
    if not isinstance(dq, Mapping) or "selected" not in dq:
        return {"status": "unknown"}
    sel = dq["selected"]
    if sel is None:
        return {"status": "none"}
    if not isinstance(sel, Mapping) or not isinstance(sel.get("ticker"), str):
        return {"status": "unknown"}
    name = sel.get("name")
    return {
        "status": "ok",
        "ticker": sel["ticker"],
        "name": name if isinstance(name, str) else None,
    }


def last_record_view(rec: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    """⑤ 마지막 기록(+ ④ 대조) — 없으면 '이 화면에서 저장한 기록 없음'. 고른 후보 · AI 답 수(목업 ⑤)."""
    if rec is None:
        return {"status": "none", "message": NO_RECORD}
    names = {
        c.get("ticker"): c.get("name") for c in rec.get("candidate_snapshot") or []
    }
    memo = (rec.get("user_memo") or "").strip()
    answers = [rec.get(f"{k}_answer_text") or "" for k, _ in AIS]
    return {
        "status": "ok",
        "message": None,
        "id": rec["id"],
        "saved_at": rec["created_at"],
        "asof": rec["asof"],
        "verdict": rec["user_verdict"],
        "memo": memo or None,
        "next_checks": [c for c in rec.get("next_checks") or [] if str(c).strip()],
        "candidate_count": len(rec.get("candidate_snapshot") or []),
        "selected": _selected(rec),
        "answer_count": sum(1 for a in answers if a.strip()),
        "compare": compare(
            rec.get("question_text") or "",
            {k: rec.get(f"{k}_answer_text") or "" for k, _ in AIS},
            names,
        ),
    }
