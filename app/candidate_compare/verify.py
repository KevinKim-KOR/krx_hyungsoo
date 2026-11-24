"""독립 검산 — 실행 기록 ↔ 재계산 대조 · 검산 기록 쓰기(PLAN §2-3 · 판정 §3 · 검증자 r1 F1 · r2 F5 · F6).

재계산(`recompute_weeks.py` 주 기록 · 주 평가 · `recompute.py` 요약 · 판정)이 만든 **같은 모양**의 결과로
잠금 · 실행 표지 · weeks.json · report.json · report.md 의 **모든 칸**을 대조한다. 마지막 잠금 · 검산 기록 차례 ·
검산 지문 · 화면 표시 확인은 `verify_records.py`.

```text
잠금     설정(recipe) = 지금 설정 · 봉인 = 지금 봉인 · 주 기록 해시 = weeks.json 의 주 기록 · 분모 · 자리 수 = 재계산
표지     started.json · run.json · report.json 의 실행 · 잠금 ID = 폴더 · run.json 파일 해시 = 지금 파일
주 기록  모든 칸(기간 · 날짜 · 편입 · 청산일 · 분모 · 빠진 종목과 순위 · 선정 · 선정 근거 picks 전체 · 순서 앞부분)
주 평가  모든 칸(자리마다 편입 · 청산 · 사유 · 값 · 참고 평가일 · 수익률 · d · 낙폭 · KODEX · 교체)
보고     칸 목록 · 모든 값(판정 전체 · 문구 · 조건 포함) · report.md = 보고에서 다시 만든 글과 바이트 같음
꼴       잠금 · 시작 표지 · 실행 기록의 칸 목록 = 정해진 칸 · 실행 · 잠금 폴더 파일 = 정해진 파일(정리 못 한 임시 이름만 허용)
         · 시작 시각 = 실행 기록 시각 = 실행 ID 시각 · 잠금 만든 시각 = 잠금 ID 시각 · 잠금 이어짐 한 줄 · 검산한 잠금 = 끝
         · 정정 사유 ⇔ 앞 잠금 · 코드 해시 대상 = 정해진 14개 · 숫자 형(정수 ↔ 실수)까지 같음
깨진 기록 못 읽음 · JSON 아님 · 객체 아님 · 칸 형이 틀림 = 예외로 끝내지 않고 어긋남으로 기록(F5)
기록     차례 번호 · 검산한 파일 해시 · 검산 지문(검산이 가져다 쓰는 코드 전부 + 환경)을 남긴다
참고     잠금 뒤 바뀐 코드 파일 · 환경 차이 · 시각 ID 순서(실행 ≥ 잠금)는 기록만 한다(시계 · 독립 근거가 없는 값)
```
"""

from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.candidate_compare import report as RP
from app.candidate_compare import verify_records as VR
from app.candidate_compare.flow import roundtrip, run_lock, runs
from app.candidate_compare.protocol import (
    PROTOCOL_ID,
    SCHEMA,
    CheckRequired,
    Config,
    CODE_FILES,
    code_hashes,
    env,
    recipe,
)
from app.candidate_compare.recompute import rebuild
from app.entry_timing.protocol import RUN_ID, dumps, new_id, read_inside, write_once
from app.ml_evidence import store

REL, ABS = 1e-12, 1e-12
SHA = re.compile(r"[0-9a-f]{64}")
FILES = VR.FILES
JSON_FILES = ("lock.json", "started.json", "run.json", "weeks.json", "report.json")


# ── 대조 ─────────────────────────────────────────────────────────────────────


def diff(theirs: Any, mine: Any, path: str = "") -> list[str]:
    """실행 기록 ↔ 재계산 — 칸 목록 · 값(실수는 상대 · 절대 1e-12) · 형 모두."""
    if isinstance(theirs, bool) or isinstance(mine, bool):
        same = type(theirs) is type(mine) and theirs == mine
        return [] if same else [f"{path} 다름"]
    if isinstance(theirs, (int, float)) and isinstance(mine, (int, float)):
        # 정수 ↔ 실수 바뀜도 다름(JSON 왕복 뒤라 형이 그대로 남음)
        if type(theirs) is not type(mine):
            return [f"{path} 형 다름 {type(theirs).__name__} ≠ {type(mine).__name__}"]
        if isinstance(theirs, int):
            return [] if theirs == mine else [f"{path} 다름 {theirs} ≠ {mine}"]
        close = math.isclose(theirs, mine, rel_tol=REL, abs_tol=ABS)
        return [] if close else [f"{path} 다름"]
    if isinstance(theirs, dict) and isinstance(mine, dict):
        if set(theirs) != set(mine):
            return [f"{path} 칸 목록 다름 {sorted(set(theirs) ^ set(mine))[:8]}"]
        out: list[str] = []
        for k in theirs:
            out += diff(theirs[k], mine[k], f"{path}.{k}" if path else str(k))
        return out
    if isinstance(theirs, list) and isinstance(mine, list):
        if len(theirs) != len(mine):
            return [f"{path} 길이 다름 {len(theirs)} ≠ {len(mine)}"]
        out = []
        for k, (x, y) in enumerate(zip(theirs, mine)):
            out += diff(x, y, f"{path}[{k}]")
        return out
    return (
        [] if theirs == mine else [f"{path} 다름 {str(theirs)[:40]} ≠ {str(mine)[:40]}"]
    )


LOCK_KEYS = {
    "schema",
    "protocol",
    "lock_id",
    "created_at",
    "recipe",
    "seal",
    "code_hashes",
    "env",
    "counts",
    "slot_counts",
    "weeks_sha256",
    "correction_reason",
    "previous_lock",
}
STARTED_KEYS = {"run_id", "lock_id", "at"}
RUN_KEYS = {"schema", "status", "run_id", "lock_id", "files", "at"}
RUN_DIR_FILES = {"started.json", "weeks.json", "report.json", "report.md", "run.json"}
TMP = re.compile(
    r"\.(started\.json|weeks\.json|report\.json|report\.md|run\.json|lock\.json)"
    r"\.[0-9a-f]{32}\.tmp"
)


def _id_time(text: Any) -> Optional[str]:
    """실행 · 잠금 ID 의 시각 부분(YYYYMMDDTHHMMSSZ) · 아니면 None."""
    return text[:16] if isinstance(text, str) and RUN_ID.fullmatch(text) else None


def _iso_id_time(text: Any) -> Optional[str]:
    """ISO 시각 칸 → ID 시각 꼴(UTC YYYYMMDDTHHMMSSZ) · 시간대 없음 · 꼴이 다름 = None(실행은 같은 now 로 둘을 만든다)."""
    if not isinstance(text, str):
        return None
    try:
        t = datetime.fromisoformat(text)
    except ValueError:
        return None
    return None if t.tzinfo is None else f"{t.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}"


def _folder(d: Path, allowed: set[str], dirs: set[str]) -> list[str]:
    """폴더에 정해진 파일 · 폴더 말고 다른 것이 있나(정리 실패로 남은 프로그램 임시 이름만 허용)."""
    out = []
    for e in sorted(os.listdir(d)):
        p = d / e
        if e in dirs and p.is_dir() and not p.is_symlink():
            continue
        if e in allowed and p.is_file() and not p.is_symlink():
            continue
        if TMP.fullmatch(e):
            continue
        out.append(e)
    return out


def _md_view(rep: dict[str, Any], mine: dict[str, Any]) -> dict[str, Any]:
    """report.md 다시 만들기용 보고 — 빠진 사유 dict 는 실행이 만난 순서(재계산 순서)로 둔다(반박 M1).

    report.json 은 키를 이름순으로 저장하지만 run 은 메모리의 만난 순서로 글을 만들었다. 값이 같을 때만
    재계산 순서로 바꾸고, 값이 다르면 그대로 둔다(칸 대조가 따로 잡는다).
    """
    view = json.loads(json.dumps(rep))
    for name in ("main", "alt"):
        sub, ours = view.get(name), mine[name]["dropped_reasons"]
        if isinstance(sub, dict) and sub.get("dropped_reasons") == ours:
            sub["dropped_reasons"] = dict(ours)
    return view


def _canonical(raw: bytes, obj: dict) -> bool:
    try:
        return raw == dumps(obj)
    except Exception:  # 기록할 수 없는 수(NaN · inf) 등 — 실행이 쓴 꼴이 아님
        return False


def _dict(x: Any) -> dict:
    return x if isinstance(x, dict) else {}


def check(
    cfg: Config, root: Path, lock_dir: Path, run_dir: Path, mine: Optional[dict] = None
) -> tuple[list[str], dict[str, str], dict[str, Any]]:
    """(어긋난 칸, 검산한 파일 해시, 참고 정보) — 실행 하나를 잠금 · 재계산과 대조. 기록이 깨져도 예외 없이 어긋남(F5)."""
    tip, chain_probs, _dirs = VR.lock_chain(root)
    checks: list[str] = list(chain_probs)
    if not chain_probs and tip != lock_dir:
        checks.append("검산한 잠금이 잠금 이어짐의 끝(마지막 잠금)이 아님")
    hashes: dict[str, str] = {}
    raw: dict[str, bytes] = {}
    for n, p in VR.paths(lock_dir, run_dir).items():
        try:
            raw[n] = read_inside(root, p)
        except (OSError, CheckRequired) as e:
            checks.append(f"{n} 읽기 실패({type(e).__name__})")
            continue
        hashes[n] = store.sha256_bytes(raw[n])
    objs: dict[str, dict] = {}
    for n in JSON_FILES:
        if n in raw:
            obj, why = VR.parse_obj(raw[n])
            if obj is None:
                checks.append(f"{n} {why}")
                continue
            objs[n] = obj
            # 실행은 늘 dumps 로 쓴다 — 중복 칸 · 다른 꼴이면 사람이 보는 글이 다를 수 있음(반박 7)
            if not _canonical(raw[n], obj):
                checks.append(
                    f"{n} 이 실행이 쓰는 꼴(정규 JSON)이 아님 — 중복 칸 · 바뀐 꼴"
                )
    if len(objs) != len(JSON_FILES) or "report.md" not in raw:
        return checks, hashes, {}
    mine = mine if mine is not None else rebuild(cfg)
    info: dict[str, Any] = {}
    try:
        info = _compare(cfg, lock_dir, run_dir, objs, raw, hashes, mine, checks)
    except Exception as e:  # 칸 형이 틀린 기록 — 어긋남으로 남김(F5)
        checks.append(f"검산 중 형식 오류: {type(e).__name__}: {e}"[:200])
    return checks, hashes, info


def _compare(
    cfg: Config,
    lock_dir: Path,
    run_dir: Path,
    objs: dict[str, dict],
    raw: dict[str, bytes],
    hashes: dict[str, str],
    mine: dict[str, Any],
    checks: list[str],
) -> dict[str, Any]:
    lock, started, run = objs["lock.json"], objs["started.json"], objs["run.json"]
    rec, rep = objs["weeks.json"], objs["report.json"]
    lock_id, run_id = lock_dir.name, run_dir.name
    # 폴더 · 표지 꼴(반박 m1 — 정해진 칸 · 파일만)
    checks += [
        f"실행 폴더에 다른 파일: {x}" for x in _folder(run_dir, RUN_DIR_FILES, set())
    ]
    checks += [
        f"잠금 폴더에 다른 것: {x}" for x in _folder(lock_dir, {"lock.json"}, {"runs"})
    ]
    for name, obj, keys in (
        ("lock.json", lock, LOCK_KEYS),
        ("started.json", started, STARTED_KEYS),
        ("run.json", run, RUN_KEYS),
    ):
        if set(obj) != keys:
            checks.append(f"{name} 칸 목록 다름 {sorted(set(obj) ^ keys)[:6]}")
    if (
        lock.get("lock_id") != lock_id
        or lock.get("schema") != SCHEMA["lock"]
        or lock.get("protocol") != PROTOCOL_ID
    ):
        checks.append("잠금 ID · 형식이 폴더와 다름")
    for name, obj in (
        ("started.json", started),
        ("run.json", run),
        ("report.json", rep),
    ):
        if obj.get("run_id") != run_id or obj.get("lock_id") != lock_id:
            checks.append(f"{name} 의 실행 · 잠금 ID 가 폴더와 다름")
    if started.get("at") != run.get("at"):
        checks.append("시작 표지와 실행 기록의 시각이 다름")
    lt, rt = _id_time(lock_id), _id_time(run_id)
    if _iso_id_time(lock.get("created_at")) != lt:
        checks.append("잠금 만든 시각이 잠금 ID 시각과 다름")
    if _iso_id_time(started.get("at")) != rt:
        checks.append("시작 시각이 실행 ID 시각과 다름")
    reason, prev = lock.get("correction_reason"), lock.get("previous_lock")
    if not (
        (prev is None and reason is None)
        or (isinstance(prev, str) and isinstance(reason, str) and reason.strip())
    ):
        checks.append("정정 사유 유무가 앞 잠금 유무와 다름(또는 꼴이 다름)")
    # 코드 해시 · 환경 값 자체는 맞춰 볼 독립 근거가 없어(실행 때 실행 코드가 확인) 꼴만 본다 · 차이는 참고
    lock_code = _dict(lock.get("code_hashes"))
    if (
        not isinstance(lock.get("code_hashes"), dict)
        or set(lock_code) != set(CODE_FILES)
        or not all(isinstance(v, str) and SHA.fullmatch(v) for v in lock_code.values())
    ):
        checks.append("잠금 코드 해시 대상 · 꼴이 정해진 것과 다름")
    lock_env = lock.get("env")
    if not (
        isinstance(lock_env, dict)
        and set(lock_env) == set(env())
        and all(v is None or isinstance(v, str) for v in lock_env.values())
    ):
        checks.append("잠금 환경 칸 꼴이 다름")
    if run.get("status") != "OK" or run.get("schema") != SCHEMA["run"]:
        checks.append(f"실행 상태 · 형식 {str(run.get('status'))[:20]}")
    files = _dict(run.get("files"))
    if not isinstance(run.get("files"), dict) or set(files) != {
        "weeks.json",
        "report.json",
        "report.md",
    }:
        checks.append("run.json 파일 목록 다름")
    for name, sha in files.items():
        if hashes.get(name) != sha:
            checks.append(f"{name} 해시가 run.json 과 다름")
    # 잠금 조건 = 지금 조건
    if lock.get("recipe") != roundtrip(recipe(cfg)):
        checks.append("잠금 설정(recipe)이 지금 설정과 다름")
    if store.sha256_bytes(dumps(rec.get("weeks"))) != lock.get("weeks_sha256"):
        checks.append("weeks.json 주 기록이 잠금 해시와 다름")
    if lock.get("seal") != roundtrip(mine["seal"]):
        checks.append("잠금 봉인 정보가 지금 봉인과 다름")
    for name in ("counts", "slot_counts"):
        checks += diff(lock.get(name), roundtrip(mine[name]), f"lock.{name}")
    # 주 기록 · 주 평가 · 보고 모든 칸
    if set(rec) != {"weeks", "rows"}:
        checks.append("weeks.json 칸 목록 다름")
    checks += diff(rec.get("weeks"), roundtrip(mine["weeks"]), "weeks")
    checks += diff(rec.get("rows"), roundtrip(mine["rows"]), "rows")
    keys = (
        "verdict",
        "main",
        "alt",
        "cost40",
        "aux",
        "counts",
        "slot_counts",
        "worked_case",
        "seal",
    )
    want = {
        "schema": SCHEMA["report"],
        "protocol": PROTOCOL_ID,
        "lock_id": lock_id,
        "run_id": run_id,
        **{k: mine[k] for k in keys},
    }
    checks += diff(rep, roundtrip(want), "report")
    # 보고 칸 형이 틀려 글을 다시 만들 수 없으면 그 사실을 남긴다(위 칸 대조가 이미 어긋남을 남김)
    try:
        md = RP.render(_md_view(rep, mine)).encode("utf-8")
    except Exception as e:
        checks.append(f"report.md 를 다시 만들 수 없음({type(e).__name__})")
    else:
        if raw["report.md"] != md:
            checks.append("report.md 가 보고에서 다시 만든 글과 다름")
    now_h = code_hashes(cfg.repo)
    return {
        # 참고(맞춰 볼 독립 근거가 없는 값) — 실행 뒤 바뀐 코드 파일 · 환경 · 시각 ID 순서(PC 시계에 따름)
        "code_changed_since_lock": sorted(
            k for k, v in lock_code.items() if now_h.get(k) != v
        ),
        "env_changed_since_lock": lock.get("env") != env(),
        "id_time_order_ok": lt is not None and rt is not None and lt <= rt,
    }


def _rebuild(cfg: Config) -> dict[str, Any]:
    try:
        return rebuild(cfg)
    except CheckRequired:
        raise
    except Exception as e:  # 봉인 자료 쪽 문제 — 기록 탓이 아니라 멈춤
        raise CheckRequired(f"재계산 실패: {type(e).__name__}: {e}"[:300]) from e


def verify(cfg: Config, now: datetime) -> dict[str, Any]:
    """마지막 잠금(이어짐)의 실행 하나를 검산해 기록을 남긴다.

    잠금이 하나라도 있으면 검산할 수 없는 상태(실행 없음 · 2개 이상 · 실행 기록 없음 · 폴더를 못 읽음 · 기록 손상)도
    어긋남 기록으로 남긴다(r2 F5 · 반박 8). 기록 없이 멈추는 것 = 잠금 없음 · 다른 실행이 진행 중 · 검산 기록 이어짐을
    확인할 수 없음(차례를 이을 수 없음) · 봉인 자료를 다시 계산할 수 없음.
    """
    with run_lock(cfg.root) as root:
        link = VR.next_link(root)
        tip, probs, dirs = VR.lock_chain(root)
        if not dirs and not probs:
            raise CheckRequired("잠금이 없음")
        subject = tip or (dirs[-1] if dirs else None)
        problems = list(probs)
        single = None
        if subject is not None:
            try:
                rds = runs(root, subject)
            except (OSError, CheckRequired) as e:
                rds = []
                problems.append(f"실행 목록을 읽을 수 없음({type(e).__name__})")
            if len(rds) == 1:
                single = rds[0]
            else:
                problems.append(f"이 잠금의 실행이 1개가 아님({len(rds)})")
        ready = single is not None and VR.exists(single / "run.json") is True
        if single is not None and not ready:
            problems.append("실행 기록(run.json)이 없거나 확인할 수 없음")
        seal = None
        if ready:
            mine = _rebuild(cfg)
            seal = mine["seal"]
            # 실행을 정했으면 남은 문제는 잠금 이어짐뿐 — check 가 같은 문제를 이미 넣는다
            checks, hashes, info = check(cfg, root, subject, single, mine)
        else:
            checks, hashes, info = problems, {}, {}
        code_sha, code_files = VR.verify_code()
        vid = new_id(now)
        out = {
            "schema": VR.VERIFY_SCHEMA,
            "verify_id": vid,
            **link,  # 차례 번호 · 앞 기록 ID · 앞 기록 해시 — '가장 최근' = 이어짐(시각 ID 아님 · F6)
            "lock_id": subject.name if subject is not None else None,
            "run_id": single.name if single is not None else None,
            "status": "VERIFIED_OK" if not checks else "MISMATCH",
            "checks": checks[:100],
            "n_checks": len(checks),
            "files": hashes,  # 검산한 파일 해시 — 화면은 지금 파일이 이 해시와 같을 때만(F2)
            "verify_code_sha256": code_sha,
            "verify_code_files": code_files,
            "env": env(),
            "seal": seal,
            **info,
            "at": now.isoformat(timespec="seconds"),
        }
        # 기록에서 온 글(깨진 유니코드 등)도 쓸 수 있게 — 쓰다가 예외로 끝내지 않음(반박 1)
        out = VR.safe(out)
        body = dumps(out)
        # 끝 표시를 기록보다 먼저 — 쓰다 멈추면 '끝 다음 기록 대기'(화면 숨김 · 다음 검산이 이어 씀)
        mark = VR.mark_of(
            vid, out["seq"], store.sha256_bytes(body), out["prev"], out["prev_sha"]
        )
        VR.write_last(root, mark)
        write_once(root, root / "verify" / f"{vid}.json", body)
        return out
