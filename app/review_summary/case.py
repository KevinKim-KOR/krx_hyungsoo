"""POC7-02 사례 보관 · 채점 메모 잠금(PLAN §1-2 · §1-3 · 판정 Q1 (b)).

```text
archive   맥북 서버 「주간 ETF 점검」 읽기 조회(GET /weekly/etf-check?selected=…) 한 번의 응답을 그대로 보관
          → cases/<사례>/response.json(원본) · case.json(복사문 · 선택 정보 · 조건 · 끝 날짜 · 근거 번호 · 자료 상태 · 해시)
          · answers/<작성자>.txt(같은 건에 이미 받은 AI 답 · 있으면)
lock-key  채점용 메모를 출력 전에 잠근다 → answer_key.md · key_lock.json(해시 · 시각) — 한 번만
```

쓰기는 모두 POC7-01 위치 도구(`write_once` · 연구 폴더 밖 · 링크 거부 · 한 번만)로 한다. 읽기는 `read_inside`.
"""

from __future__ import annotations

import json
import math
import os
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from app.entry_timing.protocol import (
    RUN_ID,
    CheckRequired,
    dumps,
    inside,
    new_id,
    read_inside,
    read_json_inside,
    real_root,
    write_once,
)
from app.ml_evidence import store
from app.review_summary.ollama_io import check_local, local_opener
from app.review_summary.prompt import AUTHORS, MODEL

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / "state" / "ml" / "research" / "poc7_02"
DEFAULT_SERVER = "http://127.0.0.1:8000"
WEEKLY_PATH = "/weekly/etf-check"
KST = timezone(timedelta(hours=9))
MAX_ANSWER = 60000


def _finite(text: str) -> float:
    v = float(text)
    if not math.isfinite(v):
        raise ValueError(f"유한하지 않은 수: {text}")
    return v


def _no_constant(name: str) -> Any:
    raise ValueError(f"JSON 에 쓸 수 없는 값: {name}")


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:  # 같은 키가 두 번 — 어느 값을 쓸지 고르지 않는다
            raise ValueError(f"JSON 에 같은 키가 두 번: {k!r}")
        out[k] = v
    return out


def strict_loads(text: str) -> Any:
    """JSON — NaN · Infinity · 1e309 같은 유한하지 않은 수 · 같은 키 두 번 · 너무 깊은 중첩을 받지 않는다(검증자 r2 F8)."""
    try:
        return json.loads(
            text,
            parse_constant=_no_constant,
            parse_float=_finite,
            object_pairs_hook=_no_duplicates,
        )
    except RecursionError:
        raise ValueError("JSON 중첩이 너무 깊음") from None


def kst_now() -> datetime:
    return datetime.now(KST)


def iso(t: datetime) -> str:
    return t.astimezone(KST).isoformat(timespec="seconds")


def fetch_weekly(server: str, selected: str, timeout: float = 120) -> bytes:
    """맥북 서버의 「주간 ETF 점검」 조회(읽기 GET 한 번) — 응답 바이트 그대로."""
    try:
        base = check_local(server, ("127.0.0.1", "localhost"))
    except ValueError:
        raise CheckRequired(f"맥북 서버 주소만 받는다: {server}") from None
    q = urllib.parse.urlencode({"selected": selected})
    # 프록시 · 되돌림 없이(맥북 안에서만 · 판정 Q5 와 같은 원칙)
    with local_opener().open(f"{base}{WEEKLY_PATH}?{q}", timeout=timeout) as r:
        if r.status != 200:
            raise CheckRequired(f"조회 응답 {r.status}")
        return r.read()


def _extract(resp: Mapping[str, Any], selected: str) -> dict[str, Any]:
    """응답에서 이번 사례에 쓸 칸만 — 모양이 다르면 보관하지 않는다(CheckRequired)."""
    if resp.get("status") != "ok":
        raise CheckRequired(f"조회 상태가 ok 가 아님: {resp.get('status')!r}")
    sel = resp.get("selected")
    if (
        not isinstance(sel, Mapping)
        or sel.get("ticker") != selected
        or resp.get("selected_missing")
    ):
        raise CheckRequired(f"고른 ETF 가 응답에 없음: {selected}")
    text = resp.get("copy_text")
    if not isinstance(text, str) or "[근거 1]" not in text:
        raise CheckRequired("복사문(copy_text)이 없거나 근거 번호가 없음")
    ev = resp.get("evidence")
    if not isinstance(ev, list) or not ev:
        raise CheckRequired("근거 목록(evidence)이 없음")
    cond = resp.get("condition") or {}
    mev = resp.get("market_evidence") or {}
    return {
        "selected": {k: sel.get(k) for k in ("ticker", "name", "rank")},
        "end_date": resp.get("end_date"),
        "condition": cond.get("line") if isinstance(cond, Mapping) else None,
        "generated_at": resp.get("generated_at"),
        "copy_text": text,
        "copy_sha256": store.sha256_bytes(text.encode("utf-8")),
        "evidence": [
            {"no": e.get("no"), "group": e.get("group"), "key": e.get("key")}
            for e in ev
        ],
        "data_status": (
            list(mev.get("data_status") or []) if isinstance(mev, Mapping) else []
        ),
        "market_status": mev.get("status") if isinstance(mev, Mapping) else None,
    }


def _answers(answers: Sequence[tuple[str, bytes]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out = []
    for author, blob in answers:
        if author not in AUTHORS:
            raise CheckRequired(f"작성자는 {' · '.join(AUTHORS)} 중 하나: {author!r}")
        if author in seen:
            raise CheckRequired(f"같은 작성자 답이 두 번: {author}")
        seen.add(author)
        try:
            text = blob.decode("utf-8")
        except UnicodeDecodeError:
            raise CheckRequired(f"{author} 답이 UTF-8 글이 아님") from None
        if not text.strip() or len(text) > MAX_ANSWER:
            raise CheckRequired(f"{author} 답이 비었거나 너무 김({len(text)}자)")
        out.append({"author": author, "text": text, "sha256": store.sha256_bytes(blob)})
    return out


def archive(
    root: Path,
    *,
    response: bytes,
    selected: str,
    answers: Sequence[tuple[str, bytes]] = (),
    source: str,
    now: Optional[datetime] = None,
) -> Path:
    """같은 조회 시점의 응답 · 선택 정보 · 답을 한 사례로 한 번만 쓴다(판정 Q1 (b)) · 반환 사례 폴더."""
    base = real_root(root)
    try:
        resp = json.loads(response.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise CheckRequired("조회 응답이 JSON 이 아님") from None
    body = _extract(resp, selected)
    ans = _answers(answers)
    t = now or kst_now()
    cid = new_id(t)
    d = inside(base, base / "cases" / cid, make=True)
    case = {
        "schema": "poc7-02-case-v1",
        "case_id": cid,
        "archived_at": iso(t),
        "source": source,
        "response_sha256": store.sha256_bytes(response),
        "model": MODEL,
        **body,
        "answers": [{k: a[k] for k in ("author", "sha256")} for a in ans],
    }
    write_once(base, d / "response.json", response)
    for a in ans:
        write_once(
            base, d / "answers" / f"{a['author']}.txt", a["text"].encode("utf-8")
        )
    write_once(base, d / "case.json", dumps(case))
    return d


def case_dir(root: Path, case_id: str) -> Path:
    if not RUN_ID.fullmatch(case_id or ""):
        raise CheckRequired(f"사례 id 꼴이 아님: {case_id!r}")
    base = real_root(root)
    return inside(base, base / "cases" / case_id)


def load_case(root: Path, case_id: str) -> dict[str, Any]:
    """보관한 사례를 다시 읽고 해시를 대조한다(응답 원본 · 복사문 · 답) — 어긋나면 CheckRequired."""
    base = real_root(root)
    d = case_dir(base, case_id)
    case = read_json_inside(base, d / "case.json")
    resp = read_inside(base, d / "response.json")
    if store.sha256_bytes(resp) != case.get("response_sha256"):
        raise CheckRequired("보관한 응답 원본 해시가 다름")
    again = _extract(json.loads(resp.decode("utf-8")), case["selected"]["ticker"])
    for k, v in again.items():  # 머리 줄 · 묶음에 쓰는 칸 전부를 응답 원본과 대조
        if case.get(k) != v:
            raise CheckRequired(f"보관한 사례의 '{k}' 가 응답 원본과 다름")
    authors = sorted(a["author"] for a in case.get("answers") or [])
    ad = d / "answers"
    if os.path.lexists(ad):
        inside(base, ad)
        files = sorted(
            n.removesuffix(".txt") for n in os.listdir(ad) if not n.startswith(".")
        )
    else:
        files = []
    if files != authors:
        raise CheckRequired(f"답 파일({files})과 사례의 답 목록({authors})이 다름")
    texts = []
    for a in case.get("answers") or []:
        blob = read_inside(base, d / "answers" / f"{a['author']}.txt")
        if store.sha256_bytes(blob) != a["sha256"]:
            raise CheckRequired(f"보관한 {a['author']} 답 해시가 다름")
        texts.append({"author": a["author"], "text": blob.decode("utf-8")})
    case["answer_texts"] = texts
    return case


def lock_key(
    root: Path, case_id: str, key: bytes, now: Optional[datetime] = None
) -> dict[str, Any]:
    """채점용 메모를 출력 전에 잠근다(PLAN §1-3) — 이미 잠겼으면 FileExistsError(고치지 않음)."""
    base = real_root(root)
    d = case_dir(base, case_id)
    load_case(base, case_id)
    if os.path.lexists(d / "bundles"):
        raise CheckRequired(
            "묶음을 만든 뒤에는 채점용 메모를 잠그지 않는다(출력 전 잠금)"
        )
    try:
        key.decode("utf-8")
    except UnicodeDecodeError:
        raise CheckRequired("채점용 메모가 UTF-8 글이 아님") from None
    if not key.strip():
        raise CheckRequired("채점용 메모가 비었음")
    lock = {
        "case_id": case_id,
        "key_sha256": store.sha256_bytes(key),
        "locked_at": iso(now or kst_now()),
    }
    # 메모를 쓴 뒤 잠금 기록 전에 끊김 — 같은 메모면 잠금만 마친다(다른 메모면 거부)
    if os.path.lexists(d / "answer_key.md") and not os.path.lexists(
        d / "key_lock.json"
    ):
        if read_inside(base, d / "answer_key.md") != key:
            raise CheckRequired("앞서 끊긴 잠금의 메모가 지금 메모와 다름 — 확인 필요")
    else:
        write_once(base, d / "answer_key.md", key)
    write_once(base, d / "key_lock.json", dumps(lock))
    return lock


def check_lock(root: Path, case_id: str, inp: Mapping[str, Any]) -> None:
    """잠근 채점용 메모가 묶음에 적힌 것과 같은가(출력 뒤 고침 · 다시 잠금 거부).

    '묶음보다 먼저 잠금'은 구조로 지킨다 — 묶음은 잠금이 있어야 만들고(pack) 묶음이 생기면 다시 잠그지 못한다
    (lock_key · 한 번 쓰기). 시각 비교는 맥북 시계를 맞추면 진짜 잠금을 거부해 쓰지 않는다(검증자 r3 F12 같은 종류)."""
    lock = read_lock(root, case_id)
    if lock.get("key_sha256") != inp.get("key_sha256"):
        raise CheckRequired(
            "잠근 채점용 메모가 묶음에 적힌 것과 다름(출력 뒤 다시 잠금)"
        )


def read_lock(root: Path, case_id: str) -> dict[str, Any]:
    base = real_root(root)
    d = case_dir(base, case_id)
    try:
        lock = read_json_inside(base, d / "key_lock.json")
        key = read_inside(base, d / "answer_key.md")
    except FileNotFoundError:
        raise CheckRequired("채점용 메모를 먼저 잠가야 함(lock-key)") from None
    if store.sha256_bytes(key) != lock.get("key_sha256"):
        raise CheckRequired("잠근 채점용 메모 해시가 다름")
    return lock
