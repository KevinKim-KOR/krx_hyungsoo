"""POC7-02 Windows PC 실행기(실행 묶음의 `run_summary.py`) — 표준 라이브러리만(PLAN §2-4 · 판정 §1 · §3).

```text
순서   묶음 파일 해시 확인 → 앞 결과 확인(본 요약 시작 · 합성 점검 설정 · 모델 멈춤 · 다른 창 실행 중이면 멈춤 · 호출 없음)
       → 환경(Python · nvidia-smi · Ollama 판 · 지정 모델 digest — 없거나 꼴이 틀리면 멈춤 · 판정 Q3 '본 실행 전 고정')
       → 합성 점검(설정 · 모델 · 환경으로 나눠 멈춤) → 토큰 세기 → 직전 관문(판 · digest 다시 읽기 · 세기 성공
       · 잘림 없음 · 문맥 안 — 못 넘으면 본 요약을 부르지 않음 · 검증자 r2 F6) → 실제 요약 → 판 다시 읽기
첫 결과 본 호출 직전 main_started.json · 응답을 받은 즉시 main_raw.json(fsync) — 그 뒤 진단 · 한 장 · 기록이
       실패하거나 중단 · 꺼져도 원문이 남는다(검증자 r1 F1). 본 응답을 기다리는 동안 Ctrl+C 는 원문을 쓴 뒤로 미룬다.
       진단 실패는 기록만 하고 계속한다. 실행 내내 running.lock 을 열어 둔다(끝에 지움 · 남은 빈 폴더는 다시 실행 가능).
기록   result_<n>/result.json · one_page.html · hashes.json(시작 표지 · 받은 원문 해시 포함)
       — 실행 id · 폴더 이름 · 앞 결과
       시작 표지 · 한 장 · 결과 · 해시는 임시 이름에 다 쓴 뒤 이름을 바꾼다(다 쓴 파일이거나 없거나 · 검증자 r2 F5)
       · 받은 원문만 바로 쓴다(남은 바이트라도 지킴) · 이미 있는 파일은 덮지 않는다 · 중단 · 오류에도 결과를 쓴다
API    Ollama 는 이 PC 안만 · 프록시 끔(review_ollama) · 설치 · 모델 받기는 하지 않는다(형수님 승인 뒤 따로)
```
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import secrets
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

try:  # 실행 묶음 안(같은 폴더의 사본)
    import review_judge as judge  # type: ignore[import-not-found]
    import review_ollama as io  # type: ignore[import-not-found]
    import review_render as render  # type: ignore[import-not-found]
    from review_files import (  # type: ignore[import-not-found]
        LOCK,
        MAIN_RAW,
        MAIN_STARTED,
        dump,
        now,
        prior_results,
        sha_bytes,
        new_result_dir,
        write_new,
        write_x,
    )
except ImportError:  # 저장소 안(맥북 시험)
    from app.review_summary import judge, render
    from app.review_summary import ollama_io as io
    from app.review_summary.runner_files import (
        LOCK,
        MAIN_RAW,
        MAIN_STARTED,
        dump,
        now,
        prior_results,
        sha_bytes,
        new_result_dir,
        write_new,
        write_x,
    )

SCHEMA = "poc7-02-result-v4"
MANIFEST, INPUT = "manifest.json", "bundle_input.json"
CODE_FILES = (
    "run_summary.py",
    "review_render.py",
    "review_judge.py",
    "review_ollama.py",
    "review_files.py",
)
DEFAULT_OLLAMA = "http://127.0.0.1:11434"
KEEP = "5m"
NEED_OLLAMA, NEED_MODEL, NEED_ENV = "NEED_OLLAMA", "NEED_MODEL", "NEED_ENV_RECORD"
ALREADY_RAN, TRIAL_STOPPED, BUNDLE_CHANGED = (
    "ALREADY_RAN",
    "TRIAL_STOPPED",
    "BUNDLE_CHANGED",
)
RUNNER_ERROR, INTERRUPTED = "RUNNER_ERROR", "INTERRUPTED"
PRE_MAIN_STOPPED = (
    "PRE_MAIN_STOPPED"  # 본 요약 직전 관문에서 멈춤(본 요약은 부르지 않음)
)


def _say(res: dict[str, Any], text: str) -> None:
    """안내 — 기록에 먼저 넣고, 화면 출력이 실패해도(인코딩 · 닫힌 창) 실행을 멈추지 않는다."""
    res["messages_ko"].append(text)
    try:
        print(text, flush=True)
    except (UnicodeError, OSError, ValueError):
        pass


def _defer_sigint(hits: list[int]) -> Any:
    """본 응답을 기다리는 동안 Ctrl+C 를 미룬다(원문을 쓴 뒤 멈춤 · Windows 는 기다리는 중 깨지 않음)."""
    try:
        return signal.signal(signal.SIGINT, lambda *_: hits.append(1))
    except (ValueError, OSError):  # 주 스레드가 아니면 미루지 못함(그대로)
        return None


def _restore_sigint(old: Any) -> None:
    if old is not None:
        signal.signal(signal.SIGINT, old)


def _diag(rec: dict[str, Any], name: str, fn: Any) -> Any:
    """진단 하나 — 실패해도(중단 제외) 기록만 하고 계속한다(받은 원문을 잃지 않게 · 검증자 r1 F1)."""
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        rec.setdefault("diag_errors", {})[name] = io.describe(e)
        return None


def generate(
    ol: io.Ollama,
    inp: dict[str, Any],
    part: dict[str, Any],
    tools: dict[str, Any],
    rec: dict[str, Any],
    raw: Optional[dict[str, Any]] = None,
    deferred: Optional[tuple[list[int], Any]] = None,
) -> dict[str, Any]:
    """한 번 실행 — rec 에 받은 값부터 채운다. raw = {path, run_id} 면 응답을 받은 즉시 원문 파일을 쓴다.

    deferred = (눌린 Ctrl+C 목록, 원래 처리기) — 본 요약은 부르는 쪽이 시작 표지 전에 Ctrl+C 를 미뤄 두고, 여기서
    받은 원문 · 받은 값(본문 · 토큰 · 종료 시각)을 다 채운 뒤에 풀고 멈춘다(그 사이에 중단돼도 구분 · 한 장이 남게)."""
    model, opts = inp["model"], inp["options"]
    rec.update(
        started_at=now(),
        request={"options": opts, "keep_alive": KEEP, "think": inp["think"]},
    )
    start = io.log_size(tools["log"])
    smp = io.Sampler(tools["smi"])
    _diag(rec, "gpu_sampler", smp.start)  # 표본을 못 떠도 본 호출은 한다(기록만)
    t0 = time.monotonic()
    got: dict[str, Any] = {}
    hits, old = deferred if deferred is not None else ([], None)
    try:
        try:
            r = ol.chat(
                {
                    "model": model,
                    "messages": part["messages"],
                    "stream": False,
                    "think": inp["think"],
                    "options": opts,
                    "keep_alive": KEEP,
                }
            )
            got = {"response": r}
        # 끊긴 응답(IncompleteRead 등)도 기술 실패로 남긴다(진단 보존)
        except Exception as e:  # noqa: BLE001
            got = {"call_error": io.describe(e)}
        if raw is not None:  # 다른 무엇보다 먼저 — 받은 원문을 디스크에(검증자 r1 F1)
            body = {"run_id": raw["run_id"], "received_at": now(), **got}
            try:
                rec["raw_sha256"] = write_x(raw["path"], dump(body))
            except OSError as e:  # 원문을 못 써도 받은 값은 결과 기록에 남긴다
                rec["raw_write_error"] = io.describe(e)
        rec["gpu_samples"] = _diag(rec, "gpu_samples", smp.finish)
        _received(rec, got, t0)
    finally:
        _restore_sigint(old)
    # 기다리는 동안 누른 Ctrl+C — 원문 · 받은 값을 다 쓴 뒤에 멈춘다(진단은 건너뜀)
    if hits:
        raise KeyboardInterrupt
    rec["ps"], rec["ps_error"] = _diag(rec, "ps", lambda: ol.loaded(model)) or (
        None,
        "읽기 실패",
    )
    rec["ps_text"] = _diag(rec, "ps_text", lambda: io.run_cmd([tools["cli"], "ps"]))
    seg = _diag(rec, "log", lambda: io.log_segment(tools["log"], start)) or {
        "trunc": None
    }
    rec["trunc_log"], rec["log_evidence"] = seg.pop("trunc"), seg
    _diag(rec, "unload", lambda: ol.unload(model))
    rec["unload"] = _diag(rec, "unload_wait", lambda: ol.wait_unloaded(model))
    return rec


def _received(rec: dict[str, Any], got: dict[str, Any], t0: float) -> None:
    """받은 값을 기록에 — 원문을 쓴 직후 · Ctrl+C 를 풀기 전(중단돼도 구분 · 한 장을 만들 수 있게)."""
    r = got.get("response") or {}
    msg = r.get("message") or {}
    rec.update(
        call_error=got.get("call_error"),
        content=msg.get("content") or "",
        thinking=msg.get("thinking") or "",
        done_reason=r.get("done_reason"),
        prompt_eval_count=r.get("prompt_eval_count"),
        prompt_eval_cached_count=r.get("prompt_eval_cached_count"),
        eval_count=r.get("eval_count"),
        model_reported=r.get("model"),
        durations={
            k: r.get(k)
            for k in (
                "total_duration",
                "load_duration",
                "prompt_eval_duration",
                "eval_duration",
            )
        },
    )
    rec["wall_s"] = round(time.monotonic() - t0, 3)
    rec["ended_at"] = now()


def count_tokens(
    ol: io.Ollama, inp: dict[str, Any], part: dict[str, Any], log: Optional[Path]
) -> dict[str, Any]:
    """같은 모델 · 템플릿으로 입력 토큰만 센다(출력 1토큰 · 버림) → 모델이 빠질 때까지 기다린다.

    같은 설정이라 본 요약과 똑같이 잘린다 — 이 호출의 server.log 잘림 기록도 남긴다(직전 관문 · 검증자 r2 F6)."""
    opts = dict(inp["options"], num_predict=1)
    out: dict[str, Any] = {"prompt_eval_count": None, "call_error": None}
    start = io.log_size(log)
    try:
        r = ol.chat(
            {
                "model": inp["model"],
                "messages": part["messages"],
                "stream": False,
                "think": inp["think"],
                "options": opts,
                "keep_alive": 0,
            }
        )
        out["prompt_eval_count"] = r.get("prompt_eval_count")
    except Exception as e:  # noqa: BLE001
        out["call_error"] = io.describe(e)
    out["unload"] = _diag(out, "unload_wait", lambda: ol.wait_unloaded(inp["model"]))
    # 내림을 기다린 뒤 — 로그 줄이 응답보다 늦게 붙을 수 있다
    seg = _count_log(out, log, start)
    out["trunc_log"], out["log_evidence"] = seg.pop("trunc"), seg
    return out


def _count_log(out: dict[str, Any], log: Optional[Path], start: Any) -> dict[str, Any]:
    """토큰 세기의 server.log 구간 — 이번 호출 줄이 보일 때까지 최대 5초 다시 읽는다(못 읽으면 직전 관문이 멈춤)."""
    for _ in range(10):
        seg = _diag(out, "log", lambda: io.log_segment(log, start)) or {"trunc": None}
        if seg.get("live") or log is None or start is None:
            return seg
        time.sleep(0.5)
    return seg


def judged(
    rec: dict[str, Any], inp: dict[str, Any], part: dict[str, Any], counted: bool
) -> Any:
    return judge.classify(
        rec,
        model=inp["model"],
        requested_ctx=inp["options"]["num_ctx"],
        marks=part["marks"],
        counted=counted,
    )


def check_bundle(bdir: Path) -> tuple[Optional[str], dict[str, str]]:
    """묶음 파일 해시가 manifest 와 같은가 — 다르면 (사유, 읽은 해시)."""
    try:
        man = json.loads((bdir / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return f"manifest.json 을 읽지 못함: {io.describe(e)}", {}
    listed = man.get("files") if isinstance(man, dict) else None
    if not isinstance(listed, dict):
        return "manifest.json 꼴이 다름", {}
    got: dict[str, str] = {}
    bad: list[str] = []
    for name, want in listed.items():  # 다 센다(바뀐 파일 목록을 정확히)
        try:
            got[name] = sha_bytes((bdir / name).read_bytes())
        except OSError:
            got[name] = "없음"
        if got[name] != want:
            bad.append(name)
    if bad:
        return f"묶음 파일이 없거나 바뀜: {', '.join(sorted(bad))}", got
    if INPUT not in got or not all(c in got for c in CODE_FILES):
        return "manifest 에 실행 파일이 다 없음", got
    return None, got


def _identity(bdir: Path, res: dict[str, Any]) -> None:
    """무엇보다 먼저 사례 · 묶음 id 를 남긴다(묶음 입력을 못 읽거나 곧 중단돼도 맥북이 받을 수 있게 · manifest 먼저)."""
    for name in (MANIFEST, INPUT):
        try:
            d = json.loads((bdir / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict) and d.get("bundle_id") and d.get("case_id"):
            res.update(bundle_id=d["bundle_id"], case_id=d["case_id"])
            return


def _claimed(bdir: Path, res: dict[str, Any]) -> Optional[dict[str, Any]]:
    """묶음 입력을 읽어 사례 · 묶음 id 를 남긴다(해시가 어긋나도 · 맥북이 어느 묶음인지 알 수 있게)."""
    try:
        inp = json.loads((bdir / INPUT).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(inp, dict):
        return None
    res.update(bundle_id=inp.get("bundle_id"), case_id=inp.get("case_id"))
    return inp


def _stop(res: dict[str, Any], status: str, text: str) -> None:
    # 멈춤 종류는 따로 남긴다 — 안내 중 Ctrl+C 로 상태가 '중단'이 돼도 무슨 멈춤이었는지 남게
    res["status"] = res["stop"] = status
    _say(res, text)


def _blocks(p: dict[str, Any]) -> bool:
    """같은 폴더 다시 실행을 막는 앞 결과 — 본 요약 시작 · 다른 창 실행 중 · 합성 점검 · 직전 관문의 설정 · 모델 멈춤.

    환경 문제(설치 · 드라이버 · 기록)로만 멈췄거나 본 요약 전에 멈췄으면(창 닫힘 포함) 같은 폴더로 다시 돌 수 있다."""
    kinds = set(p.get("stop_categories") or [])
    blocked = kinds & {"SETTINGS", "MODEL"}
    return bool(p["main_started"] or p.get("running") or p.get("unreadable") or blocked)


def _env_now(ol: io.Ollama, model: str) -> dict[str, Any]:
    v = ol.call("GET", "/api/version", timeout=5).get("version")
    tags = ol.call("GET", "/api/tags", timeout=10)
    found = next((m for m in tags.get("models") or [] if m.get("name") == model), None)
    return {
        "ollama_version": v,
        "model_digest": (found or {}).get("digest"),
        "found": found,
    }


def execute(args: argparse.Namespace, res: dict[str, Any], out: Path) -> None:
    bdir = Path(args.bundle_dir)
    # 첫 줄 — 곧 중단 · 오류여도 맥북이 받을 정체가 남게(중단도 결과로 기록됨)
    _identity(bdir, res)
    why, hashes = check_bundle(bdir)
    # 실행 코드 해시는 확인한 그 순간 값(끝에 다시 읽지 않음 · 못 읽어 비는 일이 없게)
    res.update(files=hashes, code={c: hashes.get(c) for c in CODE_FILES})
    inp = _claimed(bdir, res)
    res["prior_results"] = prior_results(bdir, out, (inp or {}).get("bundle_id"))
    if why or inp is None:
        msg = f"멈춤 — {why or '입력을 읽지 못함'}. 맥북에서 묶음을 다시 받아 주세요."
        return _stop(res, BUNDLE_CHANGED, msg)
    res["meta"] = inp["main"]["meta"]
    res["_inp"] = inp  # 중단 때 받은 원문을 구분하려고(기록 전에 뺀다)
    busy = [p["dir"] for p in res["prior_results"] if p.get("running")]
    blind = [p["dir"] for p in res["prior_results"] if p.get("unreadable")]
    done = [p["dir"] for p in res["prior_results"] if _blocks(p)]
    if busy:  # 같은 묶음을 두 창에서 동시에 돌리지 않는다
        msg = f"멈춤 — 다른 창에서 이 묶음이 아직 실행 중입니다({', '.join(busy)}). 그 창이 끝나기를 기다려 주세요."
        return _stop(res, ALREADY_RAN, msg)
    if blind:  # 앞 결과를 읽지 못함 — 무슨 멈춤이었는지 모르므로 다시 돌리지 않는다
        msg = f"멈춤 — 앞 결과({', '.join(blind)})를 읽지 못했습니다. 잠시 뒤 다시 하거나 결과 폴더를 맥북에 보내 주세요."
        return _stop(res, ALREADY_RAN, msg)
    # 같은 묶음으로 다시 하지 않는다(첫 결과 보존 · PLAN §2-2) — 앞 폴더를 먼저 맥북에
    if done:
        names = ", ".join(done)
        msg = f"멈춤 — 이 묶음은 다시 돌리지 않습니다. 앞 폴더({names})를 먼저 맥북에 보내 주세요."
        return _stop(res, ALREADY_RAN, msg)
    res["env"] = {
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "gpu": io.gpu_info(args.nvidia_smi),
        "proxies": "꺼짐(이 PC 안 직접 연결)",
    }
    ol = io.Ollama(args.ollama, args.timeout)
    try:
        env = _env_now(ol, inp["model"])
    except Exception as e:  # noqa: BLE001
        msg = f"멈춤 — Ollama 에 닿지 않음({io.describe(e)}). 설치 · 실행은 형수님 승인 뒤."
        return _stop(res, NEED_OLLAMA, msg)
    found = env.pop("found")
    res["env"]["ollama_version"] = env["ollama_version"]
    if found is None:
        msg = f"멈춤 — 모델 {inp['model']} 이 없음. 받기는 형수님 승인 뒤 따로 합니다."
        return _stop(res, NEED_MODEL, msg)
    res["env"]["model"] = {
        k: found.get(k) for k in ("name", "digest", "size", "modified_at")
    }
    bad_env = judge.env_problem(env["ollama_version"], env["model_digest"])
    if bad_env:
        return _stop(
            res, NEED_ENV, f"멈춤 — {bad_env}. 본 실행 전에 판을 고정할 수 없습니다."
        )
    # 같은 묶음 앞 실행(합성 점검까지 간 것)과 다른 모델 — 교체는 설계자 판단(모델 멈춤 · 같은 폴더 다시 실행 막음)
    seen = {p["model_digest"] for p in res["prior_results"] if p.get("model_digest")}
    if seen and env["model_digest"] not in seen:
        why_digest = "앞 실행과 모델 digest 가 다름(모델 교체는 설계자 판단)"
        res["env_gate"] = {
            "ok": False,
            "categories": ["MODEL"],
            "reasons": [why_digest],
        }
        msg = f"멈춤 — {why_digest}. 결과 폴더를 맥북에 보내 주세요."
        return _stop(res, NEED_ENV, msg)
    tools = {
        "smi": args.nvidia_smi,
        "cli": args.ollama_cli,
        "log": Path(args.server_log) if args.server_log else None,
    }
    _say(res, "합성 점검을 시작합니다(실제 값 없음).")
    trial = res["trial"] = {}
    generate(ol, inp, inp["trial"], tools, trial)
    tj = judged(trial, inp, inp["trial"], counted=False)
    gate = judge.trial_gate(
        tj,
        content=trial.get("content") or "",
        marks=inp["trial"]["marks"],
        driver=res["env"]["gpu"].get("driver"),
    )
    # 구분 · 통과 판단을 한 번에(사이에 멈춰 한쪽만 남지 않게)
    trial.update(judgement=tj, gate=gate)
    pe = trial.get("prompt_eval_count")
    ok_pe = isinstance(pe, int) and pe > 0
    trial["chars_per_token"] = (
        round(inp["trial"]["input_chars"] / pe, 4) if ok_pe else None
    )
    if not trial["gate"]["ok"]:
        kinds = " · ".join(trial["gate"]["categories"])
        msg = f"멈춤 — 합성 점검 통과 못 함({kinds}): " + " · ".join(
            trial["gate"]["reasons"]
        )
        return _stop(res, TRIAL_STOPPED, msg)
    _say(res, "합성 점검 통과. 실제 요약의 입력 토큰을 셉니다.")
    count = res["count"] = count_tokens(ol, inp, inp["main"], tools["log"])
    try:  # 직전 관문 — 정해진 실패로 한 번뿐인 시도를 쓰지 않는다(검증자 r2 F6)
        again = _env_now(ol, inp["model"])
        env1: Optional[dict[str, Any]] = {
            k: again[k] for k in ("ollama_version", "model_digest")
        }
    except Exception as e:  # noqa: BLE001
        env1, res["env_before_main_error"] = None, io.describe(e)
    res["env_before_main"] = env1
    unloads = {"trial": trial.get("unload"), "count": count.get("unload")}
    gate = res["pre_main"] = judge.pre_main_gate(
        env, env1, count, inp["options"], unloads
    )
    if not gate["ok"]:
        kinds = " · ".join(gate["categories"])
        msg = f"멈춤 — 본 요약 직전 확인 통과 못 함({kinds}): " + " · ".join(
            gate["reasons"]
        )
        return _stop(res, PRE_MAIN_STOPPED, msg + " · 본 요약은 부르지 않았습니다.")
    _say(res, "실제 요약을 시작합니다. 몇 분 걸립니다 — 창을 닫거나 클릭하지 마세요.")
    _say(res, "(Ctrl+C 를 누르면 응답을 받아 기록한 뒤에 멈춥니다.)")
    marker = {  # 이 뒤로 이 묶음은 본 요약을 다시 하지 않는다 · 고정한 판 · 설정을 함께 남긴다
        "run_id": res["run_id"],
        "bundle_id": inp["bundle_id"],
        "case_id": inp["case_id"],
        "result_dir": out.name,
        "at": now(),
        "ollama_version": env["ollama_version"],
        "model_digest": env["model_digest"],
        "options": inp["options"],
    }
    hits: list[int] = []
    # 시작 표지 앞부터 — 표지와 본 호출 사이에 멈춰 시도만 쓰는 일이 없게
    old = _defer_sigint(hits)
    try:
        write_new(out / MAIN_STARTED, dump(marker))
        main = res["main"] = {
            "count_tokens": count["prompt_eval_count"],
            "model_digest": env["model_digest"],
            "ollama_version": env["ollama_version"],
        }
        raw = {"path": out / MAIN_RAW, "run_id": res["run_id"]}
        generate(ol, inp, inp["main"], tools, main, raw=raw, deferred=(hits, old))
    finally:
        _restore_sigint(old)
    after = _diag(main, "env_after", lambda: _env_now(ol, inp["model"]))
    main["env_after"] = (
        None
        if after is None
        else {k: after[k] for k in ("ollama_version", "model_digest")}
    )
    finalize_main(res)
    res["status"] = main["status"]


def _aborted(res: dict[str, Any]) -> None:
    """본 요약을 받은 뒤 실행이 끝나지 않음 — 기술 실패로 다시 구분하게 표시한다(검증자 r3 F11 · PLAN §2-4 ①)."""
    main = res.get("main")
    if main and "ended_at" in main:
        main["aborted"] = res["status"]
        main.pop("judgement", None)
        main.pop("status", None)


def finalize_main(res: dict[str, Any]) -> None:
    """받은 본 요약을 구분한다(정상 · 중단 · 실행기 오류 모두 · 이미 했으면 그대로)."""
    main, inp = res.get("main"), res.get("_inp")
    if not main or inp is None or "judgement" in main or "ended_at" not in main:
        return
    main.setdefault("env_after", None)
    main["judgement"] = judged(main, inp, inp["main"], counted=True)
    main["status"] = main["judgement"]["status"]


def write_results(out: Path, res: dict[str, Any]) -> None:
    files: dict[str, Optional[str]] = {"one_page.html": None}
    # 시작 표지 · 받은 원문도 해시에 — 다른 실행의 파일이 섞이지 않게(검증자 r2 F7)
    for name in (MAIN_STARTED, MAIN_RAW):
        if (out / name).exists():
            files[name] = sha_bytes((out / name).read_bytes())
    if (res.get("main") or {}).get("judgement") is not None:
        try:
            page = render.render_html(res["meta"], res["main"]).encode("utf-8")
        # noqa: BLE001 — 한 장을 못 만들어도 결과 · 원문은 남긴다(F1)
        except Exception as e:
            res["render_error"] = io.describe(e)
        else:
            try:
                files["one_page.html"] = write_new(out / "one_page.html", page)
            # 한 장을 못 써도 결과 · 해시는 남긴다(검토 · F1 같은 종류)
            except OSError as e:
                res["render_error"] = f"한 장 쓰기 실패: {io.describe(e)}"
    files["result.json"] = write_new(out / "result.json", dump(res))
    write_new(out / "hashes.json", dump(files))


def parse(argv: Optional[list[str]]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="POC7-02 로컬 AI 요약 실행기")
    ap.add_argument("--bundle-dir", default=str(Path(__file__).resolve().parent))
    ap.add_argument("--ollama", default=DEFAULT_OLLAMA)
    ap.add_argument("--ollama-cli", default="ollama")
    ap.add_argument("--nvidia-smi", default="nvidia-smi")
    local = os.environ.get("LOCALAPPDATA")
    log = str(Path(local) / "Ollama" / "server.log") if local else ""
    ap.add_argument("--server-log", default=log)
    ap.add_argument("--timeout", type=float, default=3600.0)
    return ap.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse(argv)
    bdir = Path(args.bundle_dir)
    out = new_result_dir(bdir)
    lock = open(out / LOCK, "xb")  # noqa: SIM115 — 실행 내내 열어 둔다(끝에 닫고 지움)
    m0 = time.monotonic()  # 실행 시간(벽시계 맞춤과 상관없음 · 전체 경과 대조)
    started = datetime.now().astimezone()
    res: dict[str, Any] = {
        "schema": SCHEMA,
        "run_id": f"{started:%Y%m%dT%H%M%S}_{secrets.token_hex(4)}",
        "result_dir": out.name,
        "started_at": started.isoformat(timespec="seconds"),
        "messages_ko": [],
        "main": None,
    }
    stop: Optional[BaseException] = None
    try:
        execute(args, res, out)
    except KeyboardInterrupt as e:  # 중단도 첫 결과로 남긴다(판정 §3 · PLAN §2-4 ①)
        res["status"], res["error"], stop = INTERRUPTED, "중단(Ctrl+C)", e
        _aborted(res)
    except Exception as e:  # noqa: BLE001 — 실행기 자체 오류도 첫 결과로 남긴다
        res["status"], res["error"] = RUNNER_ERROR, io.describe(e)
        _aborted(res)
    _diag(res, "finalize", lambda: finalize_main(res))
    res.pop("_inp", None)
    res["ended_at"] = now()
    res["run_wall_s"] = round(time.monotonic() - m0, 3)
    final = f"끝 — 결과 {res.get('status')} · 폴더 {out.name} 를 지우지 말고 USB 로 맥북에 복사해 주세요."
    res["messages_ko"].append(final)
    try:
        write_results(out, res)
    finally:
        lock.close()
        _diag(res, "unlock", lambda: (out / LOCK).unlink())
    _say({"messages_ko": []}, final)
    if stop is not None:
        raise stop
    return 0 if res.get("status") == judge.COMPLETED else 2


if __name__ == "__main__":
    sys.exit(main())
