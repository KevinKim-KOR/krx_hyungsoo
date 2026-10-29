"""POC6-13 — 자동화 상태: 시도 기록 · 하루 상태 판정 · 문장 · 알림 1회 · latest 원자 교체(PLAN §3-3 ~ §3-5).

```text
예측(A)   BEFORE_WINDOW · DONE · RETRY_PENDING · NOT_CALLED · ATTEMPTS_EXHAUSTED
          · AUTO_WINDOW_CLOSED(15:20 뒤)
          · DEADLINE_PASSED(지금 ≥ 그 D 의 실제 close_cutoff_at 일 때만 · 판정 §5-3)
보관(B)   ARCHIVED · ARCHIVE_PENDING · NOT_TRIED — 예측과 따로 센다(판정 §5-2)
백업(C)   WAITING_TARGET · COPY_INCOMPLETE · COPY_HASH_OK · RESTORE_VERIFIED
```
시도 기록은 write once(시작 · 끝 따로). 끝 기록이 없고 그 pid 가 없으면 INTERRUPTED 로 읽는다(앞 기록을 고치지 않음).
"""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Optional

from app.forward_auto import schedule as S
from app.forward_auto import view
from app.forward_compare import protocol as P06
from app.ml_evidence import store

OPS_REL = Path("state/ml/operations/poc6_13")
PREDICT, ARCHIVE = "PREDICT", "ARCHIVE"
FAIL_OUTCOMES = {
    "CHECK_REQUIRED",
    "CALENDAR_UNKNOWN",
    "TOO_LATE",
    "CALL_FAILED",
    "CALL_TIMEOUT",
    "INTERRUPTED",
}
ARCHIVE_FAIL = {"ARCHIVE_FAILED", "ARCHIVE_PARTIAL", "ARCHIVE_TIMEOUT", "INTERRUPTED"}
LABEL = {
    "RECORDED_NEW": "새 기록 생김",
    "ALREADY_RECORDED": "이미 같은 D 기록",
    "INPUT_PENDING": "입력 아직 없음",
    "CALENDAR_UNKNOWN": "달력 확인 불가",
    "OTHER_RUN_BUSY": "다른 실행 중",
    "CHECK_REQUIRED": "확인 필요",
    "TOO_LATE": "마감 경과 진단 기록",
    "CALL_FAILED": "호출 실패",
    "CALL_TIMEOUT": "시간 초과",
    "INTERRUPTED": "중단 · 확인 필요",
    "ARCHIVED_OK": "보관 OK",
    "ARCHIVE_FAILED": "보관 실패",
    "ARCHIVE_PARTIAL": "보관 일부 실패",
    "ARCHIVE_TIMEOUT": "보관 시간 초과",
}
PAST_DAYS = 7


@dataclass(frozen=True)
class Paths:
    repo: Path
    research: Path
    evidence: Path
    ops: Path

    @classmethod
    def default(cls, repo: Path) -> "Paths":
        repo = Path(repo).resolve()
        return cls(repo, repo / P06.ROOT, repo / store.EVIDENCE_ROOT, repo / OPS_REL)


# ── 기록 ───────────────────────────────────────────────────────────────────


def write_once(path: Path, obj: Any) -> None:
    P06.write_once(path, P06.dumps(obj))


def replace_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.{uuid.uuid4().hex[:8]}.tmp"
    try:
        with open(tmp, "xb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def attempt_dir(ops: Path, day: str) -> Path:
    return ops / "attempts" / day


def tick_running(ops: Path) -> bool:
    """다른 tick 이 자동 잠금을 쥐고 있는가 — 읽기 전용으로 열어 공유 잠금만 시도(쓰기 0).

    pid 생존 확인은 쓰지 않는다(재부팅 뒤 pid 재사용으로 중단을 실행 중으로 잘못 볼 수 있음).
    """
    p = ops / ".auto.lock"
    if not p.is_file():
        return False
    fd = os.open(p, os.O_RDONLY)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except OSError:
            return True
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def load_attempts(
    ops: Path, day: str, *, in_tick: bool = False
) -> list[dict[str, Any]]:
    """그날 시도(시작 기록 기준) + 끝 기록. 끝이 없으면 — 지금 다른 tick 이 잠금을 쥐고 있으면
    RUNNING, 아니면 INTERRUPTED(잠금을 쥔 tick 안에서 읽으면 남의 미완료는 모두 INTERRUPTED)."""
    base = attempt_dir(ops, day)
    out = []
    running: Optional[bool] = False if in_tick else None
    for f in sorted(base.glob("*.start.json")) if base.is_dir() else []:
        try:
            st = P06.read_json(f)
        except (OSError, ValueError):
            continue
        end_f = f.with_name(f.name.replace(".start.json", ".end.json"))
        end = None
        if end_f.is_file():
            try:
                end = P06.read_json(end_f)
            except (OSError, ValueError):
                end = None
        a = dict(st, end=end)
        if end is not None:
            a["outcome"] = end.get("outcome")
        else:
            if running is None:
                running = tick_running(ops)
            a["outcome"] = "RUNNING" if running else "INTERRUPTED"
        out.append(a)
    out.sort(key=lambda a: (str(a.get("started_at")), str(a.get("id"))))
    return out


def confirmed_uploads(ops: Path) -> set[str]:
    """자동화 보관 시도에서 업로드 OK 를 받은 06 묶음 run_id(모든 날)."""
    ids: set[str] = set()
    for f in (ops / "attempts").glob("*/*.end.json") if ops.is_dir() else []:
        try:
            e = P06.read_json(f)
        except (OSError, ValueError):
            continue
        if e.get("kind") != ARCHIVE:
            continue
        for rid, rep in ((e.get("result") or {}).get("uploads") or {}).items():
            if isinstance(rep, dict) and rep.get("status") == "OK":
                ids.add(rid)
    return ids


# ── 판정 ───────────────────────────────────────────────────────────────────


def _predict_state(now, win, atts, runs, need, comp) -> str:
    if comp and comp.get("done"):
        return "DONE"
    cutoff = view.parse_time((need or {}).get("close_cutoff_at"))
    if cutoff is not None and now >= cutoff:
        return "DEADLINE_PASSED"
    if win == S.CLOSED:
        return "AUTO_WINDOW_CLOSED"
    if win == S.BEFORE or (not atts and not runs and not S.first_slot_passed(now)):
        return "BEFORE_WINDOW"
    if not atts and not runs:
        return "NOT_CALLED"
    if len(atts) >= S.MAX_PREDICT:
        return "ATTEMPTS_EXHAUSTED"
    return "RETRY_PENDING"


def day_view(
    paths: Paths, now: datetime, day: str, *, in_tick: bool = False
) -> dict[str, Any]:
    """그날의 예측 상태 — 지난 날이면 그날이 끝난 시점(창 닫힘)으로 본다. 실제 마감 비교는 지금 시각."""
    atts = load_attempts(paths.ops, day, in_tick=in_tick)
    pred = [a for a in atts if a.get("kind") == PREDICT]
    runs = view.runs_on(paths.research, day)
    need = view.needed_d(runs)
    comp, error = None, None
    if need:
        try:
            comp = view.completion(paths.research, need["D"])
        except Exception as e:  # noqa: BLE001 — 06 기록 읽기 실패는 미완료 + 사유
            error = f"{type(e).__name__}: {str(e)[:200]}"
    is_today = day == S.day(now)
    win = S.window(now) if is_today else S.CLOSED
    state = _predict_state(now, win, pred, runs, need, comp)
    last = pred[-1] if pred else None
    return {
        "day": day,
        "state": state,
        "attempts": len(pred),
        "last": (
            None
            if last is None
            else {k: last.get(k) for k in ("id", "started_at", "reason", "outcome")}
            | {"end": last.get("end")}
        ),
        "runs_today": len(runs),
        "need": need,
        "completion": comp,
        "read_error": error,
        "outcomes": [a.get("outcome") for a in pred],
    }


def evaluate(
    paths: Paths,
    now: datetime,
    *,
    launchd: Optional[dict] = None,
    in_tick: bool = False,
) -> dict[str, Any]:
    today = S.day(now)
    pv = day_view(paths, now, today, in_tick=in_tick)
    atts = load_attempts(paths.ops, today, in_tick=in_tick)
    arch = [a for a in atts if a.get("kind") == ARCHIVE]
    confirmed = confirmed_uploads(paths.ops)
    try:
        pending = view.archive_pending(paths.research, paths.evidence, confirmed)
    except Exception as e:  # noqa: BLE001
        pending = {"pending": True, "error": f"{type(e).__name__}: {str(e)[:200]}"}
    if not pending.get("pending"):
        a_state = "ARCHIVED"
    elif not confirmed and not arch and not _any_archive_attempt(paths.ops):
        a_state = "NOT_TRIED"
    else:
        a_state = "ARCHIVE_PENDING"
    past = []
    first = _first_day(paths.ops)
    if first and first < today:
        t = date.fromisoformat(today)
        lo = max(date.fromisoformat(first), t - timedelta(days=PAST_DAYS))
        for i in range((t - lo).days):
            d = (lo + timedelta(days=i)).isoformat()
            past.append(day_view(paths, now, d, in_tick=in_tick))
    return {
        "schema": "poc6_13_status_v1",
        "evaluated_at": store.iso(now),
        "day": today,
        "window": S.window(now),
        "next_slot": store.iso(S.next_slot(now)),
        "predict": pv,
        "archive": {
            "state": a_state,
            "attempts": len(arch),
            "last": (
                None
                if not arch
                else {k: arch[-1].get(k) for k in ("id", "started_at", "outcome")}
                | {"error": (arch[-1].get("end") or {}).get("error")}
            ),
            **pending,
        },
        "backup": backup_state(paths.ops),
        "past": past,
        "launchd": launchd,
    }


def _any_archive_attempt(ops: Path) -> bool:
    for f in (ops / "attempts").glob("*/*.start.json") if ops.is_dir() else []:
        try:
            if P06.read_json(f).get("kind") == ARCHIVE:
                return True
        except (OSError, ValueError):
            continue
    return False


def _first_day(ops: Path) -> Optional[str]:
    """자동화 기록이 처음 생긴 날(이 날 전은 '지난 날' 요약 대상이 아님 · 설치 전 공백을 만들지 않음)."""
    base = ops / "attempts"
    days = []
    for p in base.iterdir() if base.is_dir() else []:
        try:
            days.append(date.fromisoformat(p.name).isoformat())
        except ValueError:
            continue
    return min(days, default=None)


def backup_state(ops: Path) -> dict[str, Any]:
    """가장 늦은 백업 단계 기록 — 없으면 WAITING_TARGET(목적지 확인 전 · 완료 · 제외 아님).
    읽지 못한 기록이 하나라도 있으면 CHECK_REQUIRED(그보다 앞선 단계를 마지막 단계로 보이지 않게)."""
    recs, bad = [], 0
    for f in (ops / "backup").glob("*.json") if (ops / "backup").is_dir() else []:
        try:
            r = P06.read_json(f)
        except (OSError, ValueError):
            r = None
        if isinstance(r, dict):
            recs.append(r)
        else:
            bad += 1
    if bad:
        return {
            "state": "CHECK_REQUIRED",
            "detail": f"백업 기록 {bad}개를 읽지 못함 — 마지막 단계 확인 불가",
        }
    if not recs:
        return {"state": "WAITING_TARGET", "detail": "목적지 장치 확인 전"}
    r = max(recs, key=lambda r: (str(r.get("recorded_at")), int(r.get("seq") or 0)))
    return {
        "state": r.get("stage"),
        "backup_id": r.get("backup_id"),
        "recorded_at": r.get("recorded_at"),
        "detail": r.get("detail"),
    }


# ── 문장 · 알림 ────────────────────────────────────────────────────────────


def _kst_text(text: Any) -> str:
    t = view.parse_time(text)
    return "-" if t is None else S.kst(t).strftime("%m-%d %H:%M:%S")


def predict_line(pv: dict[str, Any]) -> str:
    need, comp, last = pv.get("need") or {}, pv.get("completion"), pv.get("last")
    parts = [pv["state"]]
    parts.append(f"D={need['D']}" if need.get("D") else "필요 기준일 확인 불가")
    if comp:
        parts.append(f"주 기록 {comp['recorded']}/{comp['total']}")
        if comp["method_failed"]:
            parts.append(f"방법 실패 {len(comp['method_failed'])}종목")
        if comp["last_visible"]:
            parts.append(f"공개 확인 ~{_kst_text(comp['last_visible'])}")
    if need.get("close_cutoff_at"):
        parts.append(f"실제 마감 {_kst_text(need['close_cutoff_at'])}")
    if last:
        parts.append(f"마지막 시도 {LABEL.get(last['outcome'], last['outcome'])}")
    if pv.get("read_error"):
        parts.append(f"06 기록 읽기 실패 {pv['read_error']}")
    if pv["state"] == "AUTO_WINDOW_CLOSED":
        parts.append("수동 실행은 실제 마감 전까지 가능")
    if pv["state"] == "NOT_CALLED":
        parts.append("오늘 06 기록 · 자동 호출 0(꺼짐 · 잠듦 여부는 알 수 없음)")
    return " · ".join(parts)


def render(ev: dict[str, Any]) -> str:
    pv, ar, bk = ev["predict"], ev["archive"], ev["backup"]
    ld = ev.get("launchd") or {}
    # None = launchd 조회 확인 불가('활성 아님'과 구분)
    loaded = ld.get("loaded", False)
    lines = [
        f"전향 기록 자동 실행 — {_kst_text(ev['evaluated_at'])} KST 기준 ({ev['day']})"
    ]
    lines.append(
        f"일정    {'설치됨' if ld.get('plist') else '미설치'}"
        f"{' · 활성' if loaded else ' · 등록 확인 불가' if loaded is None else ''}"
        f"{' · 마지막 종료 코드 ' + str(ld['last_exit']) if ld.get('last_exit') else ''}"
        f" · 다음 {_kst_text(ev['next_slot'])}"
    )
    lines.append(f"예측    {predict_line(pv)}")
    lines.append(
        f"시도    예측 {pv['attempts']}/{S.MAX_PREDICT} · 보관 {ar['attempts']}/{S.MAX_ARCHIVE}"
    )
    a = [ar["state"], f"미등록 {ar.get('unregistered', '?')}"]
    a.append(f"미확인 묶음 {len(ar.get('unconfirmed') or [])}")
    if ar.get("last"):
        a.append(f"마지막 {LABEL.get(ar['last']['outcome'], ar['last']['outcome'])}")
        if ar["last"].get("error"):
            a.append(str(ar["last"]["error"])[:120])
    if ar.get("error"):
        a.append(ar["error"])
    lines.append("보관    " + " · ".join(a))
    lines.append(f"백업    {bk['state']} · {bk.get('detail') or ''}".rstrip(" ·"))
    for p in ev.get("past") or []:
        txt = (
            "자동 호출 기록 없음"
            if not p["attempts"] and not p["runs_today"]
            else predict_line(p)
        )
        lines.append(f"지난 날 {p['day']} {txt}")
    return "\n".join(lines) + "\n"


def _past_items(ev: dict[str, Any]) -> list[tuple[str, str]]:
    """지난 날 중 알릴 것: 기록이 있는데 미완료인 날 · 기록 0 인 평일(거래일 여부는 확인하지 않음)."""
    out = []
    for p in ev.get("past") or []:
        if p["attempts"] or p["runs_today"]:
            if p["state"] != "DONE":
                out.append(
                    (f"PAST:{p['day']}:{p['state']}", f"{p['day']} {p['state']}")
                )
        elif date.fromisoformat(p["day"]).weekday() < 5:
            out.append(
                (
                    f"PAST:{p['day']}:NO_RECORD",
                    f"{p['day']} 자동 호출 기록 없음(거래일 여부 미확인)",
                )
            )
    return out


def notifications(
    ev: dict[str, Any], seen: frozenset = frozenset()
) -> list[tuple[list[str], str]]:
    """(키들, 문장) — 키마다 한 번. 입력 지연은 시도가 남아 있으면 알리지 않는다. 지난 날은 한 문장으로."""
    out: list[tuple[list[str], str]] = []
    pv, ar = ev["predict"], ev["archive"]
    d = (pv.get("need") or {}).get("D")
    dt = f"D={d}" if d else "D 확인 불가"
    tail = " · 확인 run_forward_auto.py status"
    if pv["state"] in ("ATTEMPTS_EXHAUSTED", "AUTO_WINDOW_CLOSED", "DEADLINE_PASSED"):
        out.append(
            ([f"{ev['day']}:P:{pv['state']}"], f"전향 기록 {dt} {pv['state']}{tail}")
        )
    elif (
        pv["state"] == "RETRY_PENDING"
        and (pv.get("last") or {}).get("outcome") in FAIL_OUTCOMES
    ):
        o = pv["last"]["outcome"]
        nxt = _kst_text(ev["next_slot"])
        out.append(
            ([f"{ev['day']}:PA:{o}"], f"전향 기록 {dt} {LABEL[o]} · 다음 {nxt}{tail}")
        )
    last = ar.get("last") or {}
    if last.get("outcome") in ARCHIVE_FAIL:
        key = f"{ev['day']}:A:{last['outcome']}"
        out.append(([key], f"전향 기록 {LABEL[last['outcome']]}{tail}"))
    past = [(k, t) for k, t in _past_items(ev) if k not in seen]
    if past:
        text = ", ".join(t for _, t in past)
        out.append(([k for k, _ in past], f"지난 자동 점검 — {text}{tail}"))
    return [(keys, msg) for keys, msg in out if not set(keys) <= seen]


def osascript_notify(message: str, runner: Callable = subprocess.run) -> str:
    """알림 요청만 한다 — 실제로 보였는지는 알 수 없다(판정 §5-4)."""
    esc = message.replace("\\", "\\\\").replace('"', '\\"')
    try:
        r = runner(
            [
                "/usr/bin/osascript",
                "-e",
                f'display notification "{esc}" with title "전향 기록"',
            ],
            capture_output=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "NOTIFY_FAILED"
    return "REQUESTED_DELIVERY_UNKNOWN" if r.returncode == 0 else "NOTIFY_FAILED"


def send_new(
    paths: Paths, ev: dict[str, Any], notify: Callable[[str], str]
) -> list[dict]:
    path = paths.ops / "notified.json"
    try:
        seen = set(json.loads(path.read_text(encoding="utf-8")).get("keys", []))
    except (OSError, ValueError, AttributeError):
        seen = set()
    sent = []
    for keys, msg in notifications(ev, frozenset(seen)):
        sent.append({"keys": keys, "message": msg, "result": notify(msg)})
        # 실패는 '보냄'으로 적지 않음 → 다음 tick 에 다시
        if sent[-1]["result"] != "NOTIFY_FAILED":
            seen.update(keys)
    if sent:
        replace_atomic(path, P06.dumps({"keys": sorted(seen)}))
    return sent


def save_latest(paths: Paths, ev: dict[str, Any]) -> None:
    replace_atomic(paths.ops / "latest.json", P06.dumps(ev))
    replace_atomic(paths.ops / "latest.txt", render(ev).encode("utf-8"))
