"""POC7-02 결과 구분 · 한 장 형식(PLAN §2-2 · §2-4 · §3-1 · 판정 §3) — 표준 라이브러리만.

실행 묶음에 `review_judge.py` 사본으로 들어간다. Windows PC 실행기와 맥북 merge 가 같은 코드로 구분한다
(merge 는 '그 묶음에 들어간' 이 코드로 원값에서 다시 구분해 실행기 기록과 대조).

```text
기술 실패    호출 오류 · 빈 출력 · 종료 이유 ≠ stop(length = 출력 길이 초과) · 실행 중 판 · digest 바뀜(본 요약)
             · 받은 뒤 실행이 끝나지 않음(중단 · 실행기 오류 · PLAN §2-4 ①)
입력 미확인  두 번 센 입력 토큰이 다름(본 요약) · 토큰 수 없음 · 입력 + 출력 > 문맥 · 할당 문맥 < 요청 · 할당 문맥 미기록
             · server.log 에 이번 호출 기록 없음(못 읽음) · 잘림 기록  — 표지 복창 한 값으로 정하지 않는다
표지         본 요약의 앞뒤 표지 복창은 따로 적는다(표지만 빠지면 '입력 확인 · 표지 누락' · 답을 버리지 않음)
GPU          /api/ps size_vram 대 size: GPU · MIXED · CPU_ONLY
             · ps 없음 = PS_MISSING · 둘 다 없음 = GPU_MEASURE_MISSING
합성 점검    통과해야 본 요약 — 설정(문맥 · 출력 길이 · 잘림) · 모델(한글 · 형식 · 표지 · 깨진 글자)
             · 환경(드라이버 551.61 미만 · 못 읽음 · GPU 아님 · 측정 공백 · 호출 오류) 로 나눠 멈춘다
             · 메모리 부족 호출 오류 · CPU 단독은 설정 문제이기도 하다(PLAN §2-2 '설정 문제(문맥 · 출력 길이 · 메모리)')
직전 관문    토큰 세기 뒤 본 요약 호출 직전 — 판 · digest 를 다시 읽어 처음과 같고, 세기가 성공해 로그가 읽히고 잘림이
             없으며, 입력 + 출력 여유(num_predict)가 문맥 안이고, 합성 점검 · 세기 뒤 모델이 내려가 있어야 본 요약을
             부른다(정해진 실패로 한 번뿐인 시도를 쓰지 않게 · 검증자 r2 F6 · 판정 §3 '입력 토큰과 출력 여유')
형식         네 칸(답이 없으면 세 칸)이 정한 순서로만 · 첫 칸 앞 · 확인 표지 뒤에 글이 있으면 형식 다름
```
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional, Sequence

TECHNICAL_FAILURE = "TECHNICAL_FAILURE"
INPUT_UNCONFIRMED = "INPUT_UNCONFIRMED"
COMPLETED = "COMPLETED"
GPU, MIXED, CPU_ONLY = "GPU", "MIXED", "CPU_ONLY"
PS_MISSING, GPU_MEASURE_MISSING = "PS_MISSING", "GPU_MEASURE_MISSING"
SETTINGS, MODEL, ENV = "SETTINGS", "MODEL", "ENV"
LABELS = ("시장", "선택한 ETF", "AI 의견", "최신 자료와 다음 확인")
MARK_LABEL = "확인 표지"
AI_LABEL = "AI 의견"
MIN_DRIVER = (551, 61)
MIN_HANGUL = 20
DIGEST = re.compile(r"(sha256:)?[0-9a-f]{64}")
_MEMORY = re.compile(r"memory|out of memory|\boom\b|cuda|alloc", re.IGNORECASE)


def memory_error(text: Any) -> bool:
    """메모리 부족으로 모델을 못 올린 호출 오류인가(문맥이 커서 · PLAN §2-2 '설정 문제 … 메모리')."""
    return isinstance(text, str) and bool(_MEMORY.search(text))


_CONTEXT_COL = re.compile(r"^\s*CONTEXT\s*$", re.IGNORECASE)
_HEAD = re.compile(
    r"^[#>\-\*\s]*\**\s*(?P<h>[^:：*]+?)\s*\**\s*[:：]\s*\**\s*(?P<rest>.*)$"
)


def _int(v: Any) -> Optional[int]:
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else None


def expected_heads(with_ai: bool) -> list[str]:
    return [h for h in LABELS if with_ai or h != AI_LABEL]


def parse_sections(
    text: str, with_ai: bool
) -> tuple[Optional[dict[str, str]], Optional[str], Optional[str]]:
    """(칸 · 확인 표지 줄 · 형식이 다른 사유). 칸은 원문 줄 그대로(머리 글자만 뗌 · 줄바꿈 유지).

    정한 칸이 정한 순서로 한 번씩 · 첫 칸 앞에 글 없음 · 확인 표지 줄은 맨 끝(있으면)."""
    want = expected_heads(with_ai)
    heads = set(LABELS) | {MARK_LABEL}
    got: dict[str, list[str]] = {}
    cur: Optional[str] = None
    mark: Optional[str] = None
    lines = (text or "").splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    for raw in lines:
        if not raw.strip():
            if cur is not None:
                got[cur].append("")
            continue
        if mark is not None:
            return None, None, "확인 표지 뒤에 글이 있음"
        m = _HEAD.match(raw.strip())
        head = m.group("h").strip() if m and m.group("h").strip() in heads else None
        if head == MARK_LABEL:
            mark = m.group("rest").strip()  # type: ignore[union-attr]
            continue
        if head is not None:
            if len(got) >= len(want) or head != want[len(got)]:
                return None, None, f"칸 순서 · 이름이 다름('{head}')"
            cur = head
            got[cur] = [m.group("rest").strip()]  # type: ignore[union-attr]
        elif cur is None:
            return None, None, "첫 칸 앞에 글이 있음"
        else:
            got[cur].append(raw.rstrip())
    if len(got) != len(want):
        return None, None, "칸이 빠짐"
    return {k: "\n".join(v).strip() for k, v in got.items()}, mark, None


def ps_context_from_text(text: Optional[str], model: str) -> Optional[int]:
    """`ollama ps` 글에서 그 모델 줄의 CONTEXT 칸(있는 판만) — 칸이 없거나 못 읽으면 None."""
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return None
    head = re.split(r"\s{2,}", lines[0].strip())
    idx = next((i for i, h in enumerate(head) if _CONTEXT_COL.match(h)), None)
    if idx is None:
        return None
    for ln in lines[1:]:
        cols = re.split(r"\s{2,}", ln.strip())
        if cols and cols[0] == model and idx < len(cols):
            digits = re.sub(r"\D", "", cols[idx])
            return int(digits) if digits else None
    return None


def allocated_context(run: Mapping[str, Any], model: str) -> Optional[int]:
    """실제 할당 문맥 — /api/ps 의 context_length, 없으면 `ollama ps` 글의 CONTEXT 칸."""
    ps = run.get("ps") or {}
    got = _int(ps.get("context_length")) if isinstance(ps, Mapping) else None
    return got if got is not None else ps_context_from_text(run.get("ps_text"), model)


def gpu_status(run: Mapping[str, Any]) -> dict[str, Any]:
    ps = run.get("ps")
    samples = run.get("gpu_samples") or []
    util = [s.get("util") for s in samples if _int(s.get("util")) is not None]
    mem = [s.get("mem_mb") for s in samples if _int(s.get("mem_mb")) is not None]
    out: dict[str, Any] = {
        "samples": len(samples),
        "util_max": max(util) if util else None,
        "mem_mb_max": max(mem) if mem else None,
    }
    size = _int(ps.get("size")) if isinstance(ps, Mapping) else None
    vram = _int(ps.get("size_vram")) if isinstance(ps, Mapping) else None
    if size and vram is not None:
        out["vram_share"] = round(vram / size, 4)
        out["status"] = GPU if vram >= size else (CPU_ONLY if vram == 0 else MIXED)
    else:
        out["vram_share"] = None
        out["status"] = PS_MISSING if samples else GPU_MEASURE_MISSING
    return out


def marks_echoed(content: str, start_mark: str, end_mark: str) -> bool:
    """출력의 '확인 표지' 줄에 두 표지가 다 있는가(본 요약에서는 따로 적는 값 · 이것만으로 버리지 않음)."""
    for ln in reversed((content or "").splitlines()):
        if MARK_LABEL in ln:
            return start_mark in ln and end_mark in ln
    return False


def classify(
    run: Mapping[str, Any],
    *,
    model: str,
    requested_ctx: int,
    marks: Sequence[str],
    counted: bool,
) -> dict[str, Any]:
    """원값에서 구분한다(실행기 · merge 같은 코드). counted = 토큰 세기 호출을 한 실행(본 요약)."""
    tech: list[str] = []
    err = run.get("call_error")
    content = run.get("content") or ""
    if err:
        tech.append(f"호출 오류: {err}")
    else:
        reason = run.get("done_reason")
        if reason == "length":
            tech.append("출력 길이 초과(done_reason = length)")
        elif reason != "stop":
            tech.append(f"종료 이유가 정상이 아님: {reason!r}")
        if not content.strip():
            tech.append("빈 출력")
    aborted = run.get("aborted")
    # 받은 뒤라도 실행이 끝나지 않으면 기술 실패(PLAN §2-4 ① '중단' · 검증자 r3 F11)
    if aborted:
        tech.append(f"실행이 끝나지 않음({aborted}) — 중단 · 실행기 오류는 기술 실패")
    after = run.get("env_after", "없음")
    if isinstance(after, Mapping) and (
        after.get("ollama_version") != run.get("ollama_version")
        or after.get("model_digest") != run.get("model_digest")
    ):
        tech.append(
            "실행 중 Ollama 판 · 모델 digest 가 바뀜(판정 Q3 '본 실행 전 고정')"
        )
    pe, ec = _int(run.get("prompt_eval_count")), _int(run.get("eval_count"))
    alloc = allocated_context(run, model)
    inp: list[str] = []
    if counted:
        cnt = _int(run.get("count_tokens"))
        if cnt is None or pe is None or cnt != pe:
            inp.append(f"두 번 센 입력 토큰이 다름(세기 {cnt} · 본 호출 {pe})")
    if pe is None or ec is None:
        inp.append("토큰 수 없음")
    if alloc is None:
        inp.append("할당 문맥 미기록")
    elif alloc < requested_ctx:
        inp.append(f"할당 문맥 {alloc} < 요청 {requested_ctx}")
    ctx = alloc if alloc is not None else requested_ctx
    if pe is not None and ec is not None and pe + ec > ctx:
        inp.append(f"입력 + 출력 토큰 {pe + ec} > 문맥 {ctx}")
    trunc = run.get("trunc_log")
    if trunc is None:
        inp.append("server.log 에 이번 호출 기록 없음(못 읽음)")
    elif trunc:
        inp.append(f"server.log 잘림 기록 {len(trunc)}줄")
    echoed = marks_echoed(content, marks[0], marks[1]) if not err else False
    status = TECHNICAL_FAILURE if tech else (INPUT_UNCONFIRMED if inp else COMPLETED)
    cached = _int(run.get("prompt_eval_cached_count"))
    notes = []
    if status == COMPLETED and not echoed:
        notes.append("입력 확인 · 표지 누락(답을 버리지 않음)")
    # 진단 실패 — 상태는 바꾸지 않고 적는다(PLAN §2-4 입력 확인 항목이 아님)
    if after is None:
        notes.append("본 요약 뒤 Ollama 판 · 모델 digest 를 다시 읽지 못함(기록만)")
    if cached:
        notes.append(
            f"입력 일부를 캐시에서 읽음({cached} 토큰 · 읽기 시간은 캐시 포함)"
        )
    return {
        "status": status,
        "technical": tech,
        "input": inp,
        "marks_echoed": echoed,
        "note": " · ".join(notes),
        "tokens": {
            "prompt": pe,
            "output": ec,
            "allocated_ctx": alloc,
            "cached": cached,
        },
        "gpu": gpu_status(run),
    }


def driver_ok(driver: Any) -> Optional[bool]:
    """NVIDIA 드라이버 판이 551.61 이상인가 — 못 읽으면 None."""
    m = re.match(r"^\s*(\d+)\.(\d+)", str(driver or ""))
    return None if not m else (int(m.group(1)), int(m.group(2))) >= MIN_DRIVER


def model_problems(content: str, marks: Sequence[str], with_ai: bool) -> list[str]:
    """합성 점검 출력의 모델 문제 — 한글이 거의 없음 · 깨진 글자 · 형식 다름 · 표지 복창 안 함."""
    out = []
    if sum("가" <= c <= "힣" for c in content or "") < MIN_HANGUL:
        out.append("한글 출력이 거의 없음")
    if "�" in (content or ""):
        out.append("깨진 글자(�)가 있음")
    why = parse_sections(content, with_ai)[2]
    if why:
        out.append(f"형식 다름: {why}")
    if not marks_echoed(content, marks[0], marks[1]):
        out.append("확인 표지를 복창하지 않음")
    return out


def trial_gate(
    j: Mapping[str, Any], *, content: str, marks: Sequence[str], driver: Any
) -> dict[str, Any]:
    """합성 점검 통과 = 본 요약으로 간다. 하나라도 걸리면 멈추고 종류(설정 · 모델 · 환경)를 남긴다.

    설정 = 길이 설정만 고친 새 묶음으로 다시(판정 Q3) · 모델 = 설계자에게 보고 · 환경 = 형수님께 확인."""
    why: list[tuple[str, str]] = []
    for r in j.get("technical") or []:
        kind = (
            SETTINGS
            if r.startswith("출력 길이")
            or (r.startswith("호출 오류") and memory_error(r))
            else (MODEL if r == "빈 출력" else ENV)
        )
        why.append((kind, r))
    for r in j.get("input") or []:
        settings = r.startswith(("입력 + 출력", "server.log 잘림")) or (
            r.startswith("할당 문맥 ") and "미기록" not in r
        )
        why.append((SETTINGS if settings else ENV, r))
    if not j.get("technical"):
        why += [(MODEL, r) for r in model_problems(content, marks, True)]
    gs = (j.get("gpu") or {}).get("status")
    if gs not in (GPU, MIXED):
        why.append((ENV, f"GPU 실행을 확인하지 못함({gs})"))
    # 문맥이 커서 GPU 메모리에 못 올렸을 수 있다(길이 설정으로 고칠 수 있게)
    if gs == CPU_ONLY:
        why.append((SETTINGS, "CPU 단독 — 문맥이 GPU 메모리에 들지 않았을 수 있음"))
    ok = driver_ok(driver)
    if ok is None:
        why.append((ENV, "NVIDIA 드라이버 판을 읽지 못함"))
    elif not ok:
        why.append((ENV, f"NVIDIA 드라이버 {driver} < 551.61"))
    return {
        "ok": not why,
        "reasons": [r for _k, r in why],
        "categories": sorted({k for k, _r in why}),
    }


def env_problem(version: Any, digest: Any) -> Optional[str]:
    """본 실행 전에 고정할 판 정보(판정 Q3) — 없거나 꼴이 틀리면 사유(검증자 r1 F3)."""
    if not isinstance(version, str) or not version.strip():
        return f"Ollama 판을 읽지 못함({version!r})"
    if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
        return f"모델 digest 가 없거나 꼴이 다름({digest!r})"
    return None


def pre_main_gate(
    env0: Mapping[str, Any],
    env1: Optional[Mapping[str, Any]],
    count: Mapping[str, Any],
    options: Mapping[str, Any],
    unloads: Mapping[str, Any],
) -> dict[str, Any]:
    """본 요약 호출 직전 관문(검증자 r2 F6) — 불러도 결과가 정해진 실패면 부르지 않는다(시도를 쓰지 않음).

    env0 = 합성 점검 전에 읽은 판 · digest · env1 = 토큰 세기 뒤 다시 읽은 값(None = 못 읽음).
    count = 토큰 세기 기록(prompt_eval_count · call_error · trunc_log). unloads = {합성 점검 · 토큰 세기 뒤 내림 기록}.
    환경 = 다시 못 읽음 · 판이 바뀜 · 세기 호출 오류 · 세기 값 없음 · 세기 로그 못 읽음 · 모델이 안 내려감(캐시)
    / 모델 = digest 가 바뀌거나 빠짐(모델 교체 여부는 설계자 판단) / 설정 = 세기에서 잘림 · 입력이 문맥 이상 ·
    입력 + 출력 여유(num_predict)가 문맥 초과(판정 §3 '출력 여유') · 메모리 부족 호출 오류(PLAN §2-2)."""
    why: list[tuple[str, str]] = []
    if env1 is None:
        why.append((ENV, "본 요약 직전 Ollama 판 · 모델 digest 를 다시 읽지 못함"))
    else:
        v1, d1 = env1.get("ollama_version"), env1.get("model_digest")
        if not isinstance(v1, str) or not v1.strip():
            why.append((ENV, f"본 요약 직전 Ollama 판을 읽지 못함({v1!r})"))
        elif v1 != env0.get("ollama_version"):
            why.append((ENV, "본 요약 직전 Ollama 판이 처음 읽은 값과 다름"))
        if not isinstance(d1, str) or not DIGEST.fullmatch(d1):
            why.append((MODEL, f"본 요약 직전 모델 digest 가 없거나 꼴이 다름({d1!r})"))
        elif d1 != env0.get("model_digest"):
            why.append((MODEL, "본 요약 직전 모델 digest 가 처음 읽은 값과 다름"))
    pe, num_ctx = count.get("prompt_eval_count"), options.get("num_ctx")
    room = options.get("num_predict")
    err = count.get("call_error")
    if err:
        kind = SETTINGS if memory_error(err) else ENV
        why.append((kind, f"토큰 세기 호출 오류: {err}"))
    elif not isinstance(pe, int) or isinstance(pe, bool) or pe <= 0:
        why.append((ENV, f"토큰 세기 값 없음({pe!r})"))
    elif pe >= num_ctx:
        why.append((SETTINGS, f"입력 토큰 {pe} ≥ 문맥 {num_ctx}"))
    elif pe + room > num_ctx:
        why.append(
            (SETTINGS, f"출력 여유 부족(입력 {pe} + 출력 {room} > 문맥 {num_ctx})")
        )
    trunc = count.get("trunc_log")
    if trunc is None and not err:
        why.append((ENV, "토큰 세기의 server.log 기록을 읽지 못함"))
    elif trunc:
        why.append((SETTINGS, f"토큰 세기의 server.log 잘림 기록 {len(trunc)}줄"))
    for label, key in (("합성 점검", "trial"), ("토큰 세기", "count")):
        u = unloads.get(key)
        if not isinstance(u, Mapping) or u.get("gone") is not True:
            why.append(
                (
                    ENV,
                    f"{label} 뒤 모델이 내려가지 않음 — 본 호출이 캐시를 읽을 수 있음",
                )
            )
    return {
        "ok": not why,
        "reasons": [r for _k, r in why],
        "categories": sorted({k for k, _r in why}),
    }
