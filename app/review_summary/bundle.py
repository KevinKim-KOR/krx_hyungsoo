"""POC7-02 실행 묶음(PLAN §2-2 · §2-4 · 판정 Q3 · §1 · §3) — 사례의 입력 · 설정 · 실행기만(저장소 · DB · 보유 파일 · 키 없음).

```text
cases/<사례>/bundles/<묶음>/bundle.zip
    = run_summary.py · review_render.py · review_judge.py · review_ollama.py · review_files.py
      · run_summary.bat
      · README_KO.txt · bundle_input.json · manifest.json(파일 해시)
cases/<사례>/bundles/<묶음>/
    bundle_input.json · manifest.json · pack.json(맥북 사본 · merge 대조 · 개발자 작업 시간 ms)
```

새 묶음 규칙(첫 결과 보존 · 판정 Q3 '본 실행 전에 지시문 · 설정 고정'):
- 채점용 메모가 잠겨 있어야 한다(출력 전 잠금).
- 본 요약을 시작한 기록이 보관됐으면 새 묶음을 만들지 않는다(다시 실행 · 설정 변경은 설계자 판단).
- 첫 묶음 = 시작 설정 그대로(길이 설정 변경 없음). 두 번째부터 = 사유 필수 · 지시문(해시)은 첫 묶음과 같아야 함
  · 설정은 바로 앞 묶음 것을 이어받는다 · 앞 묶음은 모두 회수돼 있어야 한다(검증자 r1 F2 · 예외 없음)
  · 본 요약 시도가 하나라도 회수됐으면 새 묶음 없음(한 사례 한 번 · 다시 실행은 설계자 판단)
  · 길이 설정은 바로 앞 묶음의 회수한 결과가 합성 점검 · 본 요약 직전 확인의 '설정' 문제로 멈췄을 때만 바꾼다.
표지는 묶음마다 무작위.
"""

from __future__ import annotations

import io
import json
import os
import secrets
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Optional

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
from app.review_summary import prompt as PR
from app.review_summary import trial as TR
from app.review_summary.case import case_dir, iso, kst_now, load_case, read_lock

HERE = Path(__file__).resolve().parent
# 길이 변경 근거에서 빼는 기록 — 모델을 부르지 않은 다시 실행 · 묶음 바뀜
# (기록 미완은 결과 기록을 원값으로 대조한 것만 근거로 쓴다 · _ran)
SKIP_FOR_LENGTH = ("ALREADY_RAN", "BUNDLE_CHANGED")
SHIPPED = {  # 묶음 안 이름 → 저장소 원본
    "run_summary.py": HERE / "runner_win.py",
    "review_render.py": HERE / "render.py",
    "review_judge.py": HERE / "judge.py",
    "review_ollama.py": HERE / "ollama_io.py",
    "review_files.py": HERE / "runner_files.py",
}
# 실제로 도는 Python 을 고른 뒤 실행기는 한 번만(App 실행 별칭 python.exe 는 '-c' 가 실패해 건너뜀)
BAT = "\r\n".join(
    [
        "@echo off",
        "chcp 65001 > nul",
        'cd /d "%~dp0"',
        'set "PYTHONUTF8=1"',
        'set "PY="',
        'py -3 -c "import sys" >nul 2>nul && set "PY=py -3"',
        "if not defined PY (",
        '  python -c "import sys" >nul 2>nul && set "PY=python"',
        ")",
        "if not defined PY (",
        "  echo Python 3 을 찾지 못했습니다. 맥북 쪽에 알려 주세요.",
        "  pause",
        "  exit /b 1",
        ")",
        "%PY% run_summary.py",
        "pause",
        "",
    ]
)
README = """POC7-02 로컬 AI 요약 실행 묶음

1. USB 로 받은 bundle.zip 을 Windows PC 의 비어 있는 새 폴더에 풉니다(한 곳에만 · 다른 묶음을 푼 폴더에 덮어 풀지 않기).
2. 푼 폴더의 run_summary.bat 를 더블클릭합니다(한 번).
   - 환경 확인 → 합성 점검(실제 값 없음) → 실제 요약 순서로 돕니다. 몇 분 걸릴 수 있습니다.
   - 실행 중에는 창을 클릭하거나 닫지 마세요(클릭하면 멈춘 것처럼 보입니다 · 그럴 땐 Esc).
   - Ollama 나 모델이 없으면 설치 · 받기 없이 멈추고 이유를 보여 줍니다(설치는 형수님 승인 뒤 따로).
   - 같은 묶음은 한 번만 실제 요약을 합니다. 실제 요약을 시작한 뒤에는 다시 돌려도 모델을 부르지 않고 멈춥니다.
   - 환경 문제(Ollama · 드라이버 등)로 멈췄으면 고친 뒤 같은 폴더에서 다시 돌려도 됩니다. 그 밖의 멈춤은 결과 폴더를 맥북에 보내 주세요.
3. 같은 폴더에 생긴 result_1(멈춘 뒤 다시 돌렸으면 result_2 …) 폴더를 모두, 지우지 말고 복사해 맥북에 보내 주세요.
   - 결과 폴더는 고치지 말아 주세요(첫 결과를 그대로 대조합니다). zip 은 한 곳에만 풀어 주세요.
   - USB 에는 푼 폴더마다 따로 복사해 주세요(푼 폴더 이름으로 USB 에 폴더를 만들고 그 안에).
     '같은 이름이 이미 있음' 창이 뜨면 덮어쓰기 · 건너뛰기 · 둘 다 유지 중 아무것도 고르지 말고 취소한 뒤 알려 주세요.

필요한 것: Python 3 · Ollama(이 PC 안에서만 부름 · 프록시 안 씀) · 모델 qwen3.5:9b-q4_K_M.
저장소 · 시장 DB · 보유 파일 · 인증키 · 인터넷은 필요 없습니다.
"""


def publish_dir(
    base: Path, parent: Path, name: str, files: Mapping[str, bytes]
) -> Path:
    """숨김 폴더(.stage-…)에 모두 쓴 뒤 이름을 바꾼다 — 중간에 끊겨도 반쪽 기록이 보이지 않는다(덮지 않음)."""
    stage = inside(base, parent / f".stage-{name}-{secrets.token_hex(4)}", make=True)
    for n, data in sorted(files.items()):
        write_once(base, stage / n, data)
    final = inside(base, parent) / name
    if os.path.lexists(final):
        raise FileExistsError(f"이미 있음: {name}")
    os.rename(stage, final)
    return final


def _marks() -> tuple[str, str]:
    return f"S-{secrets.token_hex(4)}", f"E-{secrets.token_hex(4)}"


def _zip(files: Mapping[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, files[name])
    return buf.getvalue()


def _listed(base: Path, d: Path) -> list[str]:
    if not os.path.lexists(d):
        return []
    inside(base, d)  # 링크 · 밖 폴더면 CheckRequired(목록을 읽기 전에)
    return sorted(os.listdir(d))


def bundles_of(root: Path, case_id: str) -> list[str]:
    """만든 순서의 묶음 — 각 묶음이 만들 때 적은 앞 묶음 수로 정렬(같은 초에 만들어도 순서가 정해짐)."""
    base = real_root(root)
    d = case_dir(base, case_id)
    names = [n for n in _listed(base, d / "bundles") if RUN_ID.fullmatch(n)]
    order = {
        n: len(
            read_json_inside(base, d / "bundles" / n / "pack.json").get("prior_bundles")
            or []
        )
        for n in names
    }
    return sorted(names, key=lambda n: (order[n], n))


def merged_runs(root: Path, case_id: str, every: bool = False) -> list[dict[str, Any]]:
    """회수해 보관한 실행 기록(runs/*/merge.json) — 묶음을 만든 순서 · 결과 폴더 번호 · 실행 id 순(시각 아님).

    같은 실행의 완전한 기록이 뒤에 오면 앞의 '기록 미완'은 빼고 하나로 센다(every=True 면 둘 다 · 검증자 r2 F5)."""
    base = real_root(root)
    d = case_dir(base, case_id)
    out = []
    for n in _listed(base, d / "runs"):
        if n.startswith("."):
            continue
        out.append(read_json_inside(base, d / "runs" / n / "merge.json"))

    # 같은 실행은 하나로 — 대신 받은 기록 미완 · 완전한 기록이 있는 기록 미완은 뺀다
    if not every:
        full = {r.get("run_id") for r in out if r.get("status") != "INCOMPLETE_RECORD"}
        gone = {r.get("replaces") for r in out if r.get("replaces")}
        out = [
            r
            for r in out
            if r.get("record_dir") not in gone
            and (r.get("status") != "INCOMPLETE_RECORD" or r.get("run_id") not in full)
        ]
    order = {b: i for i, b in enumerate(bundles_of(base, case_id))}

    # 묶음 순서 · 결과 폴더 번호 순(한 폴더 안에서는 번호 = 실행 순서) — 벽시계는 쓰지 않는다(검증자 r3 F12)
    # 마지막으로 돈 기록은 번호가 아니라 앞 결과 사슬로 고른다(_last_ran · 여러 곳에 풀면 번호가 겹침)
    def key(r: dict[str, Any]) -> tuple[int, int, str]:
        n = str(r.get("result_dir") or "").removeprefix("result_")
        rank = order.get(r.get("bundle_id"), len(order))
        return (rank, int(n) if n.isdigit() else 0, str(r.get("run_id")))

    return sorted(out, key=key)


def stop_kind(r: Mapping[str, Any]) -> Any:
    """회수 기록의 멈춤 종류 — 안내 중 중단돼도 · 기록 미완이어도 원래 멈춤(상태 글자 대신 · 검토 A)."""
    return r.get("stop_kind") or r.get("status")


def stop_categories(r: Mapping[str, Any]) -> set[str]:
    """멈춤 분류(합성 점검 · 본 요약 직전 관문 · 판 멈춤)를 합친 것."""
    out: set[str] = set()
    for k in ("trial_categories", "pre_main_categories", "env_gate_categories"):
        out |= set(r.get(k) or [])
    return out


def _ran(r: dict[str, Any]) -> bool:
    """실제로 돌아 멈춤 종류를 믿을 수 있는 기록 — 다시 실행 멈춤 · 묶음 바뀜 · 결과 기록 없는 기록 미완은 아님."""
    if stop_kind(r) in SKIP_FOR_LENGTH:
        return False
    if r.get("status") == "INCOMPLETE_RECORD":
        return bool((r.get("checks") or {}).get("claim_checked"))
    return True


def _last_ran(ran: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """실제로 돈 마지막 기록 — 나머지를 모두 자기 앞 결과로 본 기록(벽시계가 아니라 실행 순서 · 검증자 r3 F12).

    같은 폴더에서 차례로 돈 실행은 뒤 실행이 앞 실행을 모두 앞 결과로 적는다. 그런 기록이 없으면(여러 곳에 풀기 등)
    순서를 정할 수 없다(None)."""
    if not ran:
        return {}
    for r in ran:
        seen = set(r.get("prior_runs") or [])
        if all(o is r or o.get("run_id") in seen for o in ran):
            return r
    return None


def _plan(
    base: Path, case_id: str, lengths: Optional[Mapping[str, int]], reason: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """새 묶음 규칙을 확인하고 (설정, 기록) — 어긋나면 CheckRequired(검증자 r1 F2 · 반박 검토).

    - 한 사례에 본 요약 시도는 한 번: 본 요약을 시작한 기록이 하나라도 회수됐으면 새 묶음 없음
      (실행 실패여도 · 다시 실행 · 설정 변경은 설계자 판단 · PLAN §2-2 '고친 경우에만'의 가장 좁은 해석).
    - 앞 묶음은 모두 회수돼 있어야 한다(회수 전 새 묶음 = 뒤 결과를 먼저 보관할 수 있음 · 예외 없음).
    - 새 묶음은 앞 묶음의 실제로 돈 마지막 기록이 실행기가 같은 폴더 다시 실행을 막는 멈춤(설정 · 모델)일 때만 만든다.
      환경 · 설치 · 묶음 바뀜 · 중단 멈춤은 같은 폴더에서 다시 돌리는 것이라, 그 폴더에 첫 본 요약이 있을 수 있다
      (맥북이 모르는 채 두 번째 묶음을 판정하지 않게 · 검토 D · PLAN §2-2 '다시 실행은 … 앞 실행을 보존').
    - 길이 설정은 그 마지막 기록이 '설정' 문제로 멈췄을 때만 바꾼다.
    """
    runs = merged_runs(base, case_id)
    started = [r for r in runs if r.get("main_started")]
    if started:
        names = ", ".join(str(r.get("run_id")) for r in started)
        raise CheckRequired(
            f"본 요약 시도가 이미 보관됨({names}) — 새 묶음 없음(다시 실행은 설계자 판단)"
        )
    prior = bundles_of(base, case_id)
    if not prior:
        if lengths:
            raise CheckRequired(
                "첫 묶음은 시작 설정 그대로(길이 설정은 합성 점검이 설정 문제로 멈춘 뒤에만)"
            )
        return PR.options(), {"prior_bundles": [], "after_run": None}
    merged = {r.get("bundle_id") for r in runs if stop_kind(r) != "ALREADY_RAN"}
    missing = [b for b in prior if b not in merged]
    # 다시 실행 멈춤 기록만은 회수가 아니다(다른 창에서 아직 실행 중일 수 있음)
    if missing:
        raise CheckRequired(
            f"앞 묶음 결과를 먼저 회수해야 새 묶음을 만든다: {', '.join(missing)}"
        )
    if not reason.strip():
        raise CheckRequired("두 번째 묶음부터는 사유가 필요")
    first = read_bundle(base, case_id, prior[0])["input"]
    if first["prompt_sha256"] != PR.prompt_sha():
        raise CheckRequired(
            "지시문 · 설정 판이 첫 묶음과 다름(본 실행 전 고정 · 판정 Q3)"
        )
    last = read_bundle(base, case_id, prior[-1])["input"]
    keep = {k: last["options"][k] for k in PR.LENGTH_KEYS}
    after = [r for r in runs if r.get("bundle_id") == prior[-1]]
    ran = [r for r in after if _ran(r)]
    stopped = _last_ran(ran)
    if stopped is None:
        raise CheckRequired(
            "앞 묶음의 실제로 돈 기록들의 순서를 알 수 없음(여러 곳에 풀어 돌림 등) — 설계자 판단"
        )
    kinds = stop_categories(stopped)
    if not kinds & {"SETTINGS", "MODEL"}:
        raise CheckRequired(
            "앞 묶음의 마지막 기록이 같은 폴더에서 다시 돌리는 멈춤(환경 · 설치 · 묶음 바뀜 · 중단)으로 끝남"
            " — 새 묶음 없이 그 폴더를 다시 돌린 결과를 회수하세요(새 묶음은 설정 · 모델 멈춤 뒤에만)"
        )
    if lengths:
        if stopped.get("main_started") or "SETTINGS" not in kinds:
            raise CheckRequired(
                "길이 설정은 바로 앞 묶음의 실제로 돈 마지막 기록이 합성 점검 · 본 요약 직전 확인의 '설정' 문제로 멈췄을 때만"
            )
        keep.update(lengths)
    return PR.options(keep), {
        "prior_bundles": prior,
        "after_run": stopped.get("run_id"),
    }


def pack(
    root: Path,
    case_id: str,
    *,
    lengths: Optional[Mapping[str, int]] = None,
    reason: str = "",
    now: Optional[datetime] = None,
) -> Path:
    """실행 묶음 하나를 만든다 · 반환 묶음 폴더(맥북 사본)."""
    t0, m0 = now or kst_now(), time.monotonic()
    base = real_root(root)
    d = case_dir(base, case_id)
    case = load_case(base, case_id)
    lock = read_lock(base, case_id)
    opts, rule = _plan(base, case_id, lengths, reason)
    start, end = _marks()
    main_msgs = PR.build_messages(
        copy_text=case["copy_text"],
        archived_at=case["archived_at"],
        answers=case["answer_texts"],
        start_mark=start,
        end_mark=end,
    )
    syn = TR.build(PR.input_chars(main_msgs))
    ts, te = _marks()
    trial_msgs = PR.build_messages(
        copy_text=syn["copy_text"],
        archived_at="합성",
        answers=syn["answers"],
        start_mark=ts,
        end_mark=te,
    )
    bid = new_id(t0)
    meta = {
        "end_date": case["end_date"],
        "condition": case["condition"],
        "selected": case["selected"],
        "answer_authors": [a["author"] for a in case["answer_texts"]],
        "archived_at": case["archived_at"],
        "model": PR.MODEL,
    }
    inp = {
        "schema": "poc7-02-bundle-v2",
        "bundle_id": bid,
        "case_id": case_id,
        "created_at": iso(t0),
        "prompt_version": PR.PROMPT_VERSION,
        "prompt_sha256": PR.prompt_sha(),
        "model": PR.MODEL,
        "think": PR.THINK,
        "options": opts,
        "key_sha256": lock["key_sha256"],
        "copy_sha256": case["copy_sha256"],
        "main": {
            "meta": meta,
            "messages": main_msgs,
            "marks": [start, end],
            "input_chars": PR.input_chars(main_msgs),
        },
        "trial": {
            "meta": {**syn["meta"], "model": PR.MODEL},
            "messages": trial_msgs,
            "marks": [ts, te],
            "input_chars": PR.input_chars(trial_msgs),
        },
    }
    files: dict[str, bytes] = {n: p.read_bytes() for n, p in SHIPPED.items()}
    files["run_summary.bat"] = BAT.encode("utf-8")
    files["README_KO.txt"] = README.encode("utf-8")
    files["bundle_input.json"] = dumps(inp)
    manifest = {
        "bundle_id": bid,
        "case_id": case_id,
        "files": {n: store.sha256_bytes(b) for n, b in sorted(files.items())},
    }
    files["manifest.json"] = dumps(manifest)
    zipped = _zip(files)
    zip_sha = store.sha256_bytes(zipped)
    record = {
        "bundle_id": bid,
        "case_id": case_id,
        **rule,
        "reason": reason.strip(),
        "options": opts,
        "zip_sha256": zip_sha,
        "manifest_sha256": store.sha256_bytes(files["manifest.json"]),
        "dev_started_at": iso(t0),
        "dev_ms": round((time.monotonic() - m0) * 1000),
    }
    out = {  # 숨김 폴더에 다 쓴 뒤 이름을 바꾼다(끊겨도 반쪽 묶음이 보이지 않음 · 검토 · F5 같은 종류)
        "bundle_input.json": files["bundle_input.json"],
        "manifest.json": files["manifest.json"],
        "bundle.zip": zipped,
        "pack.json": dumps(record),
    }
    return publish_dir(base, inside(base, d / "bundles", make=True), bid, out)


def read_bundle(root: Path, case_id: str, bundle_id: str) -> dict[str, Any]:
    base = real_root(root)
    if not RUN_ID.fullmatch(bundle_id or ""):
        raise CheckRequired(f"묶음 id 꼴이 아님: {bundle_id!r}")
    bd = inside(base, case_dir(base, case_id) / "bundles" / bundle_id)
    raw_input = read_inside(base, bd / "bundle_input.json")
    with zipfile.ZipFile(io.BytesIO(read_inside(base, bd / "bundle.zip"))) as z:
        shipped = {n: z.read(n) for n in z.namelist()}
    return {
        "dir": bd,
        "input": json.loads(raw_input.decode("utf-8")),
        "input_sha256": store.sha256_bytes(raw_input),
        "manifest": read_json_inside(base, bd / "manifest.json"),
        "pack": read_json_inside(base, bd / "pack.json"),
        "shipped": shipped,
    }
