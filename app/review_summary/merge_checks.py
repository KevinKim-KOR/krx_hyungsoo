"""POC7-02 회수 대조 하나하나(merge 가 부름) — USB 결과 기록의 원값끼리 대조 · 어긋나면 CheckRequired.

```text
받은 원문   본 요약 기록(본문 · 종료 이유 · 토큰 수 · 모델 · 호출 오류) = main_raw.json · 실행 id 같음
판          Ollama 판 · 모델 digest 있음 · 꼴 맞음 · 결과 · 본 요약 · 시작 표지가 서로 같음 · 세기 토큰 · 응답 모델
시작 표지   사례 · 묶음 · 결과 폴더 · 실행 id · 설정 · 판(검증자 r2 F7) — 시각은 두 기기 · 시간 맞춤의 차이로 거짓 거부가
            나므로 순서를 메모로만 남긴다(실행 id · 폴더 · 받은 원문 · 해시가 실행에 묶는다)
본 요약     '그 묶음에 들어간' judge 로 원값에서 다시 구분 · render 로 한 장을 다시 만들어 같은 바이트
합성 점검   다시 구분 · 통과 판단이 같음 · 통과 못 했으면 본 요약 없음
직전 관문   원값(처음 판 · 다시 읽은 판 · 토큰 세기)에서 다시 계산해 같음 · 못 넘었으면 본 요약 없음(검증자 r2 F6)
JSON        유한하지 않은 수(NaN · Infinity) 거부 · 객체만(검증자 r2 F8)
본문        완료 · 기록 미완 공통(_check_body) — 묶음 · 코드 해시 · 멈춤 종류 · 판 멈춤 · 본 요약 · 합성 점검 · 직전 관문
            (같은 함수라 두 경로가 늘 같다 · 검증자 r3 F10)
```
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from app.entry_timing.protocol import CheckRequired
from app.ml_evidence import store
from app.review_summary.bundle import SHIPPED
from app.review_summary.case import strict_loads

RUN = re.compile(r"\d{8}T\d{6}_[0-9a-f]{8}")
DIGEST = re.compile(r"(sha256:)?[0-9a-f]{64}")
MAIN_STARTED, MAIN_RAW = "main_started.json", "main_raw.json"
# 실행기가 중간에 멈춘 상태(본 요약이 있어도 결과 상태가 다를 수 있음)
STOPPED = ("INTERRUPTED", "RUNNER_ERROR")
PASS_THROUGH = (  # 본 요약 없이 멈춘 실행기 상태
    "NEED_OLLAMA",
    "NEED_MODEL",
    "NEED_ENV_RECORD",
    "TRIAL_STOPPED",
    "PRE_MAIN_STOPPED",
    "BUNDLE_CHANGED",
    "ALREADY_RAN",
    *STOPPED,
)
INCOMPLETE = "INCOMPLETE_RECORD"
RAW_FIELDS = (("content", ("message", "content")), ("done_reason", ("done_reason",)))
RAW_FIELDS += (
    ("prompt_eval_count", ("prompt_eval_count",)),
    ("eval_count", ("eval_count",)),
)
RAW_FIELDS += (("model_reported", ("model",)),)


def _rejudge(
    judge: Any, res: dict[str, Any], inp: dict[str, Any], part: str, counted: bool
) -> Any:
    return judge.classify(
        res[part],
        model=inp["model"],
        requested_ctx=inp["options"]["num_ctx"],
        marks=inp[part]["marks"],
        counted=counted,
    )


def _json(raw: bytes, name: str) -> dict[str, Any]:
    """USB 기록 JSON — 유한하지 않은 수(NaN · Infinity) 거부 · 객체만(검증자 r2 F8)."""
    try:
        v = strict_loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise CheckRequired(f"{name} 이 JSON 이 아님") from None
    if not isinstance(v, dict):
        raise CheckRequired(f"{name} 이 JSON 객체가 아님")
    return v


def _try_json(raw: Optional[bytes]) -> Optional[dict[str, Any]]:
    """다 쓰이지 않은 기록 — 읽히면 객체, 아니면 None(바이트는 그대로 보관)."""
    if raw is None:
        return None
    try:
        return _json(raw, "기록")
    except CheckRequired:
        return None


def _check_marker(
    marker: dict[str, Any], inp: dict[str, Any], case_id: str, rd_name: str
) -> None:
    """시작 표지가 이 묶음 · 이 결과 폴더의 것인가(검증자 r2 F7) — 다른 실행의 표지가 섞이면 거부."""
    if marker.get("case_id") != case_id:
        raise CheckRequired(f"다른 사례의 시작 표지: {marker.get('case_id')!r}")
    if not RUN.fullmatch(str(marker.get("run_id") or "")):
        raise CheckRequired("시작 표지의 실행 id 꼴이 다름")
    if marker.get("bundle_id") != inp.get("bundle_id"):
        raise CheckRequired("시작 표지의 묶음이 결과와 다름")
    if marker.get("result_dir") != rd_name:
        raise CheckRequired("시작 표지의 결과 폴더 이름이 다름")
    if _iso(marker.get("at")) is None:
        raise CheckRequired("시작 표지의 시각이 없거나 꼴이 다름")
    if marker.get("options") != inp.get("options"):
        raise CheckRequired("시작 표지의 설정이 묶음과 다름")
    v, d = marker.get("ollama_version"), marker.get("model_digest")
    if not isinstance(v, str) or not v.strip():
        raise CheckRequired("시작 표지에 Ollama 판 기록이 없음")
    if not isinstance(d, str) or not DIGEST.fullmatch(d):
        raise CheckRequired("시작 표지에 모델 digest 기록이 없거나 꼴이 다름")


def _check_marker_run(marker: dict[str, Any], res: dict[str, Any]) -> None:
    """완전한 결과 폴더 — 시작 표지가 이 실행(결과)의 것인가(검증자 r2 F7)."""
    if marker.get("run_id") != res.get("run_id"):
        raise CheckRequired("시작 표지의 실행 id 가 결과와 다름")


def clock_notes(
    marker: dict[str, Any],
    inp: dict[str, Any],
    res: Optional[dict[str, Any]],
    raw: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """시각 순서 메모(초) — 거부하지 않는다(맥북 · PC 시계 차이 · 실행 중 시간 맞춤 · 검토)."""
    at = _iso(marker.get("at"))
    main = (res or {}).get("main") or {}
    pairs = {
        "after_bundle_s": inp.get("created_at"),
        "after_run_start_s": (res or {}).get("started_at"),
        "before_main_call_s": main.get("started_at"),
        "before_raw_s": (raw or {}).get("received_at"),
    }
    out: dict[str, Any] = {}
    for k, v in pairs.items():
        t = _iso(v) if v is not None else None
        if at is not None and t is not None:
            d = (at - t).total_seconds()
            out[k] = d if k.startswith("after") else -d
    out["out_of_order"] = sorted(k for k, d in out.items() if d < 0)
    return out


def _check_pre_main(  # type: ignore[no-untyped-def]
    res: dict[str, Any], inp: dict[str, Any], judge
) -> Optional[dict[str, Any]]:
    """본 요약 직전 관문(검증자 r2 F6) — 원값에서 다시 계산해 실행기 기록과 같고, 못 넘었으면 본 요약이 없어야 한다."""
    pm, status, main = res.get("pre_main"), res.get("status"), res.get("main")
    stop = res.get("stop") or status
    if pm is None:
        if main is not None:
            raise CheckRequired("본 요약 직전 확인 없이 본 요약이 있음")
        if stop == "PRE_MAIN_STOPPED":
            raise CheckRequired("본 요약 직전 확인 기록 없이 그 멈춤으로 적힘")
        return None
    count, env = res.get("count"), res.get("env") or {}
    before = res.get("env_before_main")
    if not isinstance(count, dict) or not (before is None or isinstance(before, dict)):
        raise CheckRequired("본 요약 직전 확인의 토큰 세기 · 다시 읽은 판 기록이 없음")
    env0 = {
        "ollama_version": env.get("ollama_version"),
        "model_digest": (env.get("model") or {}).get("digest"),
    }
    unloads = {
        "trial": (res.get("trial") or {}).get("unload"),
        "count": count.get("unload"),
    }
    want = judge.pre_main_gate(env0, before, count, inp["options"], unloads)
    if want != pm:
        raise CheckRequired("본 요약 직전 확인을 원값에서 다시 하면 실행기 기록과 다름")
    if main is not None and not pm["ok"]:
        raise CheckRequired("본 요약 직전 확인을 넘지 않았는데 본 요약이 있음")
    if stop == "PRE_MAIN_STOPPED" and pm["ok"]:
        raise CheckRequired("본 요약 직전 확인을 넘었는데 그 멈춤으로 적힘")
    if not pm["ok"] and status not in ("PRE_MAIN_STOPPED", *STOPPED):
        raise CheckRequired("본 요약 직전 확인을 못 넘었는데 그 멈춤이 아님")
    return pm


def _check_raw(res: dict[str, Any], raw: Optional[dict[str, Any]]) -> None:
    """본 요약 기록이 받은 원문 그대로인가(검증자 r1 F1) — 시작 표지가 있는 본 요약은 원문 파일이 있어야 함."""
    main = res.get("main") or {}
    if raw is None:
        if "ended_at" in main and not main.get("raw_write_error"):
            raise CheckRequired(
                "본 요약을 받았다는 기록이 있는데 받은 원문(main_raw.json)이 없음"
            )
        return  # 받은 직후 멈춤 · 원문 쓰기 실패(받은 값은 결과에 · 실행기 기록)
    if raw.get("run_id") != res.get("run_id"):
        raise CheckRequired("받은 원문의 실행 id 가 결과와 다름")
    if "ended_at" not in main:
        return  # 받은 직후 멈춤 — 원문만 있는 경우
    if (raw.get("call_error") or None) != (main.get("call_error") or None):
        raise CheckRequired("본 요약의 호출 오류가 받은 원문과 다름")
    resp = raw.get("response") or {}
    for key, path in RAW_FIELDS:
        v: Any = resp
        for p in path:
            v = (v or {}).get(p) if isinstance(v, dict) else None
        if (v or None) != (main.get(key) or None):
            raise CheckRequired(f"본 요약의 '{key}' 가 받은 원문과 다름")


def _check_env(res: dict[str, Any], inp: dict[str, Any]) -> None:
    """본 요약이 있으면 판 정보가 있어야 하고 결과 안에서 같아야 한다(판정 Q3 · 검증자 r1 F3)."""
    main, env = res["main"], res.get("env") or {}
    version, digest = env.get("ollama_version"), (env.get("model") or {}).get("digest")
    if not isinstance(version, str) or not version.strip():
        raise CheckRequired("본 요약이 있는데 Ollama 판 기록이 없음")
    if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
        raise CheckRequired("본 요약이 있는데 모델 digest 기록이 없거나 꼴이 다름")
    if main.get("model_digest") != digest or main.get("ollama_version") != version:
        raise CheckRequired("본 요약의 Ollama 판 · 모델 digest 가 환경 기록과 다름")
    marker = res.get("_marker") or {}
    if marker and (marker.get("ollama_version"), marker.get("model_digest")) != (
        version,
        digest,
    ):
        raise CheckRequired("시작 표지의 Ollama 판 · 모델 digest 가 환경 기록과 다름")
    if main.get("count_tokens") != (res.get("count") or {}).get("prompt_eval_count"):
        raise CheckRequired("본 요약의 세기 토큰이 토큰 세기 기록과 다름")
    if (
        "ended_at" in main
        and not main.get("call_error")
        and main.get("model_reported") != inp["model"]
    ):
        raise CheckRequired(
            f"응답한 모델이 지정 모델과 다름: {main.get('model_reported')!r}"
        )


def _check_main(  # type: ignore[no-untyped-def]
    res, inp, judge, render, page, hashes, started
) -> dict[str, Any]:
    main, status = res["main"], res.get("status")
    if not started:
        raise CheckRequired("본 요약 기록이 있는데 시작 표지(main_started.json)가 없음")
    _check_env(res, inp)
    if res["meta"] != inp["main"]["meta"]:
        raise CheckRequired("한 장의 머리 정보가 묶음과 다름")
    if "judgement" not in main:
        if status not in STOPPED or page is not None or "ended_at" in main:
            raise CheckRequired("구분이 없는 본 요약은 받은 직후 멈춘 실행만")
        return {"main_status": None}
    if _rejudge(judge, res, inp, "main", True) != main.get("judgement"):
        raise CheckRequired("본 요약 구분을 원값에서 다시 하면 실행기 기록과 다름")
    if main["judgement"]["status"] != main.get("status"):
        raise CheckRequired("본 요약 구분과 본 요약 상태가 다름")
    if status not in STOPPED and status != main["status"]:
        raise CheckRequired("본 요약 구분과 결과 상태가 다름")
    if res.get("render_error"):
        if page is not None or hashes.get("one_page.html") is not None:
            raise CheckRequired("한 장 만들기 오류인데 한 장이 있음")
    else:
        if page is None:
            raise CheckRequired("결과 폴더에 one_page.html 이 없음")
        if store.sha256_bytes(page) != hashes.get("one_page.html"):
            raise CheckRequired("one_page.html 해시가 hashes.json 과 다름")
        if render.render_html(res["meta"], main).encode("utf-8") != page:
            raise CheckRequired(
                "result.json 으로 다시 만든 한 장이 one_page.html 과 다름"
            )
    return {"main_status": main["status"], "main": main["judgement"]}


def _check_trial(res, inp, judge) -> Optional[dict[str, Any]]:  # type: ignore[no-untyped-def]
    t, status = res.get("trial"), res.get("status")
    stop = res.get("stop") or status  # 멈춤 안내 중 중단돼도 원래 멈춤(검토 A)
    if t is None:
        if res.get("main") is not None:
            raise CheckRequired("합성 점검 없이 본 요약이 있음")
        if stop == "TRIAL_STOPPED":
            raise CheckRequired("합성 점검 기록 없이 합성 점검 멈춤으로 적힘")
        return None
    if "judgement" not in t:  # 합성 점검 중 멈춤
        if status not in STOPPED or res.get("main") is not None:
            raise CheckRequired("구분이 없는 합성 점검은 그 중 멈춘 실행만")
        if t.get("gate") is not None:
            raise CheckRequired("구분 없는 합성 점검에 통과 판단이 있음")
        return {"gate": None}
    tj = _rejudge(judge, res, inp, "trial", False)
    if tj != t.get("judgement"):
        raise CheckRequired("합성 점검 구분을 원값에서 다시 하면 실행기 기록과 다름")
    driver = ((res.get("env") or {}).get("gpu") or {}).get("driver")
    gate = judge.trial_gate(
        tj, content=t.get("content") or "", marks=inp["trial"]["marks"], driver=driver
    )
    # 구분 뒤 통과 판단 전에 멈춤(중단 · 오류) — 그 사이 다음 단계는 없어야 한다
    if "gate" not in t:
        if status not in STOPPED or res.get("main") is not None or res.get("count"):
            raise CheckRequired("통과 판단 없는 합성 점검은 그 사이 멈춘 실행만")
        return {"gate": None, "judgement": tj}
    if t.get("gate") != gate:
        raise CheckRequired("합성 점검 통과 판단이 다름")
    if res.get("main") is not None and not gate["ok"]:
        raise CheckRequired("합성 점검을 통과하지 않았는데 본 요약이 있음")
    if stop == "TRIAL_STOPPED" and gate["ok"]:
        raise CheckRequired("합성 점검을 통과했는데 멈춤으로 적힘")
    return {"gate": gate, "judgement": tj}


def _iso(v: Any) -> Optional[datetime]:
    try:
        t = datetime.fromisoformat(str(v))
    except ValueError:
        return None
    return t if t.tzinfo is not None else None


def _check_body(  # type: ignore[no-untyped-def]
    res: dict[str, Any],
    b: dict[str, Any],
    judge,
    render,
    page: Optional[bytes],
    hashes: Optional[dict[str, Any]],
    marker: Optional[dict[str, Any]],
    raw: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """완료 · 기록 미완 공통 원값 대조(해시 비교는 부르는 쪽) — 같은 함수라 두 경로가 늘 같다(검증자 r3 F10).

    hashes = 완료 경로의 해시 목록 · 기록 미완은 None(한 장 해시는 그 한 장 바이트로 대신)."""
    inp, files = b["input"], b["manifest"].get("files") or {}
    status = res.get("status")
    stop = res.get("stop") or status  # 멈춤 안내 중 중단돼도 무슨 멈춤이었는지(검토 A)
    no_call = all(x is None for x in (res.get("trial"), res.get("main"), marker, raw))
    changed = stop == "BUNDLE_CHANGED"
    if res.get("stop") and status != res["stop"] and status not in STOPPED:
        raise CheckRequired(
            "멈춤 종류와 결과 상태가 다름(안내 중 중단 · 오류만 다를 수 있음)"
        )
    if b["input_sha256"] != files.get("bundle_input.json"):
        raise CheckRequired("맥북 bundle_input.json 이 manifest 와 다름")
    if changed and not no_call:
        raise CheckRequired("묶음이 바뀐 실행인데 합성 점검 · 본 요약이 있음")
    # 묶음 확인 전에 멈춤(중단 · 오류) — 모델을 부르지 않았어야 한다
    if res.get("files") is None:
        if not (no_call and status in STOPPED):
            raise CheckRequired("묶음 확인 기록이 없는데 멈춤 전 기록이 아님")
    elif not changed:
        if res.get("files") != files:
            raise CheckRequired("실행기가 본 묶음 파일 해시가 맥북 manifest 와 다름")
        if res.get("code") != {n: files.get(n) for n in SHIPPED}:
            raise CheckRequired("실행 코드 해시가 묶음과 다름")
    gate = res.get("env_gate")
    if gate is not None and (
        stop != "NEED_ENV_RECORD"
        or res.get("trial") is not None
        or res.get("main") is not None
        or gate.get("categories") != ["MODEL"]
        or gate.get("ok") is not False
    ):
        raise CheckRequired("판 멈춤(앞 실행과 다른 digest) 기록이 어긋남")
    hs = (
        hashes
        if hashes is not None
        else {"one_page.html": store.sha256_bytes(page) if page else None}
    )
    checks: dict[str, Any] = {}
    if res.get("main") is not None:
        checks.update(
            _check_main(res, inp, judge, render, page, hs, marker is not None)
        )
    else:
        if status not in PASS_THROUGH:
            raise CheckRequired(f"본 요약이 없는데 상태가 멈춤이 아님: {status!r}")
        if hs.get("one_page.html") is not None or page is not None:
            raise CheckRequired("본 요약이 없는데 한 장(해시)이 있음")
        if (marker is not None or raw is not None) and status not in STOPPED:
            raise CheckRequired("본 요약을 시작했는데 멈춤 상태가 아님")
        checks["main_status"] = None
    checks["trial"] = _check_trial(res, inp, judge)
    checks["pre_main"] = _check_pre_main(res, inp, judge)
    return checks
