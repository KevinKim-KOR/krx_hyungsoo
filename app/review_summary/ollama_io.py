"""POC7-02 Windows PC 쪽 도구(실행 묶음의 `review_ollama.py`) — 표준 라이브러리만.

```text
Ollama    이 PC 안(127.0.0.1 · localhost · ::1)만 · 프록시 끔(환경 변수 · Windows 레지스트리 프록시 모두) · 되돌림 거부
GPU       nvidia-smi(이름 · 드라이버 · 메모리 / 실행 중 1초마다 사용률 · 메모리)
server.log  이번 호출 동안 새로 붙은 부분만 · '/api/chat' 줄이 있어야 '읽음'(없으면 None = 못 읽음)
            · 잘림 = 'truncating input prompt' · 'truncated = 1 이상' · 'context shift'
            (정상 'truncated = 0' 은 잘림이 아님)
내림      /api/generate keep_alive 0 은 비동기 — /api/ps 에서 모델이 빠질 때까지 기다리고 걸린 시간을 남긴다
```
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")
TRUNC = re.compile(
    r"truncating input prompt|truncated\s*=\s*[1-9]|context shift", re.IGNORECASE
)
RELEASE_OK = re.compile(r"truncated\s*=\s*0\b")
CHAT_LINE = "/api/chat"


def describe(e: BaseException) -> str:
    if isinstance(e, urllib.error.HTTPError):
        try:
            body = e.read().decode("utf-8", "replace")[:300]
        except OSError:
            body = ""
        return f"HTTP {e.code}: {body}"
    if isinstance(e, TimeoutError) or "timed out" in str(e):
        return "시간 초과"
    return f"{type(e).__name__}: {str(e)[:300]}"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, *a: Any, **k: Any
    ) -> None:  # 되돌림 = 이 PC 밖으로 갈 수 있음
        raise urllib.error.URLError("되돌림(redirect)은 따라가지 않음")


def local_opener() -> urllib.request.OpenerDirector:
    """프록시를 쓰지 않는 연결(ProxyHandler({}) · 환경 변수 · 레지스트리 프록시 무시) · 되돌림 거부."""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


def check_local(url: str, hosts: tuple[str, ...] = LOCAL_HOSTS) -> str:
    host = urllib.parse.urlparse(url).hostname
    if host not in hosts:
        raise ValueError(f"이 PC 안 주소만 부른다(받은 주소: {url})")
    return url.rstrip("/")


class Ollama:
    def __init__(self, base: str, timeout: float) -> None:
        self.base, self.timeout = check_local(base), timeout
        self.opener = local_opener()

    def call(self, method: str, path: str, body: Any = None, timeout: float = 0) -> Any:
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            self.base + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with self.opener.open(req, timeout=timeout or self.timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def chat(self, body: dict[str, Any]) -> Any:
        return self.call("POST", "/api/chat", body)

    def unload(self, model: str) -> None:
        self.call("POST", "/api/generate", {"model": model, "keep_alive": 0}, 120)

    def loaded(self, model: str) -> tuple[Optional[dict[str, Any]], Optional[str]]:
        try:
            got = self.call("GET", "/api/ps", timeout=10)
        except Exception as e:  # noqa: BLE001 — 기록만
            return None, describe(e)
        for m in got.get("models") or []:
            if model in (m.get("name"), m.get("model")):
                return m, None
        return None, "실행 중 모델 목록에 없음"

    def wait_unloaded(self, model: str, limit: float = 60.0) -> dict[str, Any]:
        """모델이 /api/ps 에서 빠질 때까지(최대 limit 초) — {gone, waited_s}."""
        t0 = time.monotonic()
        while True:
            m, err = self.loaded(model)
            if m is None and err == "실행 중 모델 목록에 없음":
                return {"gone": True, "waited_s": round(time.monotonic() - t0, 2)}
            if time.monotonic() - t0 >= limit:
                return {
                    "gone": False,
                    "waited_s": round(time.monotonic() - t0, 2),
                    "error": err,
                }
            time.sleep(0.5)


def run_cmd(cmd: list[str], timeout: float = 10) -> Optional[str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return p.stdout if p.returncode == 0 else None


def gpu_info(smi: str) -> dict[str, Any]:
    q = "--query-gpu=name,driver_version,memory.total"
    out = run_cmd([smi, q, "--format=csv,noheader,nounits"])
    if not out or not out.strip():
        return {"error": "nvidia-smi 를 실행하지 못함"}
    cols = [c.strip() for c in out.strip().splitlines()[0].split(",")]
    return {
        "name": cols[0],
        "driver": cols[1] if len(cols) > 1 else None,
        "mem_total_mb": cols[2] if len(cols) > 2 else None,
    }


def gpu_sample(smi: str) -> Optional[dict[str, Any]]:
    q = "--query-gpu=utilization.gpu,memory.used"
    out = run_cmd([smi, q, "--format=csv,noheader,nounits"], 5)
    try:
        first = (out or "").strip().splitlines()[0]
        util, mem = (int(c.strip()) for c in first.split(",")[:2])
    except (ValueError, IndexError):
        return None
    return {"util": util, "mem_mb": mem}


class Sampler(threading.Thread):
    """실행 중 1초마다 nvidia-smi(사용률 · 메모리)."""

    def __init__(self, smi: str, every: float = 1.0) -> None:
        super().__init__(daemon=True)
        self.smi, self.every = smi, every
        self.samples: list[dict[str, Any]] = []
        self.halt = threading.Event()

    def run(self) -> None:
        t0 = time.monotonic()
        while not self.halt.is_set():
            s = gpu_sample(self.smi)
            if s is not None:
                s["t"] = round(time.monotonic() - t0, 1)
                self.samples.append(s)
            self.halt.wait(self.every)

    def finish(self) -> list[dict[str, Any]]:
        self.halt.set()
        self.join(timeout=10)
        return self.samples


def log_size(path: Optional[Path]) -> Optional[int]:
    try:
        return path.stat().st_size if path else None
    except OSError:
        return None


def log_segment(path: Optional[Path], start: Optional[int]) -> dict[str, Any]:
    """이번 호출 동안 server.log 에 새로 붙은 부분.

    {live, trunc(None = 못 읽음), chat_lines, release_ok, bytes}."""
    out: dict[str, Any] = {
        "live": False,
        "trunc": None,
        "chat_lines": 0,
        "release_ok": 0,
        "bytes": 0,
    }
    if path is None or start is None:
        return out
    try:
        with open(path, "rb") as fh:
            size = os.fstat(fh.fileno()).st_size
            fh.seek(start if size >= start else 0)
            text = fh.read().decode("utf-8", "replace")
    except OSError:
        return out
    lines = text.splitlines()
    out["bytes"] = len(text.encode("utf-8"))
    out["chat_lines"] = sum(CHAT_LINE in ln for ln in lines)
    out["release_ok"] = sum(bool(RELEASE_OK.search(ln)) for ln in lines)
    out["live"] = out["chat_lines"] > 0
    if out["live"]:
        out["trunc"] = [ln[:300] for ln in lines if TRUNC.search(ln)][:20]
    return out
