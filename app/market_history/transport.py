"""POC6-19 — 요청 기록 · 간격 · 재시도 · 중단 규칙(키움 · Yahoo 기존 어댑터에 넣는 전송).

- 같은 공급자 요청 시작 간격 = 1초(기존 0.25초 · 공식 숫자 제한 없음 · 설계 하한 1초 중 가장 긴 것).
- 연결 오류 · 시간 초과 · HTTP 5xx 만 같은 요청 1회 재시도(재시도도 요청 수에 셈).
- 호출 제한(키움 응답 코드 · 문구 안 사유 코드 1700 · 1701 · HTTP 429) = 그 공급자 즉시 중단.
  자료 요청의 인증 거절(사유 코드 8xxx · HTTP 401 · 403) = 키움 즉시 중단(ACCESS_BLOCKED · 코드만 기록).
- 구간(A · B) 요청 수 · 시간 상한(단조 시계와 벽시계 중 긴 쪽 — 맥북이 잠들어도 실제 경과로 셈) ·
  운영 작업 시간대(09:30 ~ 10:30 KST · OCI 05 수집 · 06 자동 실행)에 들어서면 새 요청 중단 · 메모리 4GiB ·
  새 파일 512MiB 상한.
- 응답을 받을 때마다 원시를 실행 폴더에 쓴다(줄 단위 flush + fsync). 토큰 요청은 HTTP 상태 · 응답 코드만
  남긴다(본문 · 메시지 · 요청 헤더 없음 — 키 · 토큰 · 접속 IP 가 실릴 수 있음). IP 처럼 보이는 글자는 가린다.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, time as dtime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import requests

from app import kiwoom_investor_flow as KW
from app import yahoo_daily_series as YH
from app.market_history import normalize as N
from app.market_history import report as R
from app.research_run_guard import is_under, peak_rss_bytes

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))
QUIET_KST = (dtime(9, 30), dtime(10, 30))
_RETRYABLE = (
    requests.ConnectionError,
    requests.Timeout,
    requests.exceptions.ChunkedEncodingError,
)


@dataclass(frozen=True)
class Limits:
    a_requests: int = 32
    a_seconds: float = 1800
    b_requests: int = 7000
    b_seconds: float = 7200
    auth_requests: int = 2
    gap_seconds: float = 1.0
    max_consecutive_failures: int = 3
    comm_backoff_seconds: float = (
        30.0  # 통신 실패(재시도 뒤) 다음 날짜까지 기다림 · 구간 시간에 포함
    )
    max_rss_bytes: int = 4 * 1024**3
    max_bytes: int = 512 * 1024**2


class _Stop(Exception):
    def __init__(self, reason: str, status: str = R.FETCH_FAILED):
        super().__init__(reason)
        self.reason, self.status = reason, status

    def as_dict(self) -> dict:
        return {"status": self.status, "reason": self.reason}


class ProviderStop(_Stop):
    """그 공급자만 멈춘다(인증 실패 · 호출 제한 · 인증 요청 상한)."""


class PhaseStop(_Stop):
    """그 구간(A · B)의 요청 수 · 시간 상한."""


class RunStop(_Stop):
    """실행 전체를 멈춘다(메모리 · 파일 용량 상한)."""


def _now_ms() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


class Recorder:
    """실행 폴더 안에만 쓴다 · 새 파일은 배타 생성 · 원시 줄은 받을 때마다 flush + fsync."""

    def __init__(self, run_dir: Path, max_bytes: int):
        self.run_dir, self.max_bytes, self.bytes = run_dir, max_bytes, 0

    def path(self, rel: str) -> Path:
        p = self.run_dir / rel
        if not is_under(p, self.run_dir):
            raise RunStop(f"실행 폴더 밖 쓰기 거부: {rel}")
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def new_text(self, rel: str, text: str) -> None:
        with open(self.path(rel), "x", encoding="utf-8") as fh:
            fh.write(text)
        self.bytes += len(text.encode("utf-8"))

    def new_json(self, rel: str, payload: Any) -> None:
        self.new_text(rel, R.render_json(payload))

    def append_line(self, rel: str, payload: dict) -> int:
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
        with open(self.path(rel), "a", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        size = len(text.encode("utf-8"))
        self.bytes += size
        return size


class Session:
    """구간 상한 · 공급자별 시작 간격 · 요청 · 재시도 수 · 메모리 · 용량 검사."""

    def __init__(
        self,
        rec: Recorder,
        limits: Limits,
        sleep: Callable,
        monotonic: Callable,
        wall: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self.rec, self.limits, self.sleep, self.mono = rec, limits, sleep, monotonic
        self.wall = wall
        self.phase: Optional[str] = None
        self.phase_started = 0.0
        self.phase_started_wall = wall()
        self.phase_requests = 0
        self.auth_requests = 0
        self.counts: dict[str, dict[str, dict[str, int]]] = {}
        self._last_start: dict[str, float] = {}

    def begin_phase(self, name: str) -> None:
        self.phase, self.phase_started, self.phase_requests = name, self.mono(), 0
        self.phase_started_wall = self.wall()
        logger.info("POC6-19 구간 %s 시작", name)

    def elapsed(self) -> float:
        wall = (self.wall() - self.phase_started_wall).total_seconds()
        return max(self.mono() - self.phase_started, wall)

    def _count(self, provider: str, key: str) -> None:
        bucket = self.counts.setdefault(provider, {}).setdefault(
            self.phase or "-", {"requests": 0, "retries": 0}
        )
        bucket[key] += 1

    def _pace(self, provider: str) -> None:
        last = self._last_start.get(provider)
        if last is not None:
            wait = last + self.limits.gap_seconds - self.mono()
            if wait > 0:
                self.sleep(wait)
        self._last_start[provider] = self.mono()

    def after_write(self) -> None:
        """응답을 쓴 직후 — 그 쓰기로 상한을 넘었으면 멈춘다(받은 원시는 지우지 않는다 · 검증자 r1 F2)."""
        if self.rec.bytes > self.limits.max_bytes:
            raise RunStop(
                f"파일 용량 상한 초과({self.rec.bytes} > {self.limits.max_bytes} 바이트)"
            )

    def _resources(self) -> None:
        if peak_rss_bytes() >= self.limits.max_rss_bytes:
            raise RunStop(f"메모리 상한 {self.limits.max_rss_bytes} 바이트")
        if self.rec.bytes >= self.limits.max_bytes:
            raise RunStop(f"파일 용량 상한 {self.limits.max_bytes} 바이트")

    def before_data(self, provider: str, retry: bool) -> None:
        cap_n, cap_s = (
            (self.limits.a_requests, self.limits.a_seconds)
            if self.phase == "A"
            else (self.limits.b_requests, self.limits.b_seconds)
        )
        if self.phase_requests >= cap_n:
            raise PhaseStop(f"{self.phase} 요청 상한 {cap_n}회")
        if self.elapsed() >= cap_s:
            raise PhaseStop(f"{self.phase} 시간 상한 {int(cap_s)}초")
        now = self.wall().astimezone(KST).time()
        if QUIET_KST[0] <= now < QUIET_KST[1]:
            raise PhaseStop(
                f"{self.phase} 운영 작업 시간대 진입({QUIET_KST[0]:%H:%M} ~ {QUIET_KST[1]:%H:%M} KST)"
            )
        self._resources()
        self._pace(provider)
        self.phase_requests += 1
        self._count(provider, "requests")
        if retry:
            self._count(provider, "retries")

    def before_auth(self) -> None:
        if self.auth_requests >= self.limits.auth_requests:
            raise ProviderStop(
                f"인증 요청 상한 {self.limits.auth_requests}회", R.ACCESS_BLOCKED
            )
        self._resources()
        self._pace("kiwoom")
        self.auth_requests += 1


def _transient(r) -> bool:
    return getattr(r, "status_code", 0) >= 500


def _header(r, name: str) -> Optional[str]:
    for k, v in (getattr(r, "headers", None) or {}).items():
        if str(k).lower() == name:
            return str(v)
    return None


class KiwoomTransport:
    """`KiwoomClient` 에 넣는 전송 — 토큰 요청은 상태 · 코드만, 자료 요청은 본문까지 줄 단위 보관."""

    def __init__(
        self, session: Session, rec: Recorder, post: Optional[Callable] = None
    ):
        self.s, self.rec, self._post = session, rec, post
        self.seq = 0
        self.final: dict[str, dict] = {}
        self.data_lines = self.data_bytes = 0
        self.latency_total = 0.0
        self.last_auth_code: Any = None

    def _send(self, url, json, headers, timeout):
        return (self._post or KW._default_post)(
            url, json=json, headers=headers, timeout=timeout
        )

    def __call__(self, url, json=None, headers=None, timeout=None):
        if url.endswith(KW.TOKEN_PATH):
            return self._auth(url, json, headers, timeout)
        return self._data(url, json, headers, timeout)

    def _auth(self, url, payload, headers, timeout):
        for attempt in (1, 2):
            self.s.before_auth()
            line = {"attempt": attempt, "requested_at": _now_ms()}
            try:
                r = self._send(url, payload, headers, timeout)
            except requests.RequestException as e:
                line.update(error=type(e).__name__, received_at=_now_ms())
                self._auth_line(line)
                if attempt == 1 and isinstance(e, _RETRYABLE):
                    continue
                raise ProviderStop(f"토큰 요청 통신 오류({type(e).__name__})") from e
            try:
                parsed = r.json()
            except ValueError:
                parsed = None
            code = parsed.get("return_code") if isinstance(parsed, dict) else None
            msg_code = N.message_code(parsed)
            self.last_auth_code = f"{code} · 사유 {msg_code}"
            line.update(
                http_status=r.status_code,
                return_code=code,
                msg_code=msg_code,
                received_at=_now_ms(),
            )
            self._auth_line(line)
            if _transient(r):
                if attempt == 1:
                    continue
                raise ProviderStop(f"토큰 요청 서버 오류(HTTP {r.status_code})")
            return r  # 거절(등록 IP · 앱키)은 KiwoomClient 가 KiwoomAuthError 로 올린다
        raise AssertionError("도달하지 않음")

    def _auth_line(self, line: dict) -> None:
        self.rec.append_line(N.KIWOOM_AUTH_RAW, line)
        self.s.after_write()

    def _data(self, url, payload, headers, timeout):
        base_dt = str((payload or {}).get("base_dt", ""))
        for attempt in (1, 2):
            self.s.before_data("kiwoom", retry=attempt > 1)
            self.seq += 1
            t0, requested_at = time.monotonic(), _now_ms()
            line: dict = {
                "seq": self.seq,
                "phase": self.s.phase,
                "base_dt": base_dt,
                "attempt": attempt,
                "params": {k: v for k, v in (payload or {}).items()},
                "requested_at": requested_at,
            }
            try:
                r = self._send(url, payload, headers, timeout)
            except requests.RequestException as e:
                line.update(error=type(e).__name__, received_at=_now_ms())
                self._keep(line)
                if attempt == 1 and isinstance(e, _RETRYABLE):
                    continue
                raise
            self.latency_total += time.monotonic() - t0
            body = N.redact(getattr(r, "text", "") or "")
            try:
                parsed = json.loads(body)
            except ValueError:
                parsed = None
            code = parsed.get("return_code") if isinstance(parsed, dict) else None
            msg_code = N.message_code(parsed)
            line.update(
                received_at=_now_ms(),
                http_status=r.status_code,
                return_code=code,
                msg_code=msg_code,
                cont_yn=_header(r, "cont-yn"),
                next_key=_header(r, "next-key"),
                body_sha256=_sha(body),
                body=body,
            )
            self._keep(line)
            kind = N.code_kind(code, msg_code)
            if r.status_code == 429 or kind == "호출 제한 응답":
                raise ProviderStop(
                    f"호출 제한 응답(HTTP {r.status_code} · 코드 {code} · 사유 {msg_code})"
                )
            if r.status_code in (401, 403) or kind == "인증 거절":
                raise ProviderStop(
                    f"자료 요청 인증 거절(HTTP {r.status_code} · 코드 {code} · 사유 {msg_code})",
                    R.ACCESS_BLOCKED,
                )
            if attempt == 1 and _transient(r):
                continue
            return r
        raise AssertionError("도달하지 않음")

    def _keep(self, line: dict) -> None:
        self.data_bytes += self.rec.append_line(N.KIWOOM_RAW, line)
        self.data_lines += 1
        self.final[N.iso(line["base_dt"])] = line
        self.s.after_write()
        if self.data_lines % 100 == 0:
            logger.info(
                "POC6-19 키움 %d줄 · 마지막 %s", self.data_lines, line["base_dt"]
            )


class YahooTransport:
    """`fetch_completed_daily` 에 넣는 전송 — 요청(시도)마다 파일 하나."""

    def __init__(self, session: Session, rec: Recorder, get: Optional[Callable] = None):
        self.s, self.rec, self._get = session, rec, get
        self.seq = 0
        self.current: dict = {}
        self.final: dict[str, dict] = {}
        self.bytes_by_window: dict[str, int] = {}

    def __call__(self, url, params=None, headers=None, timeout=None):
        cur = self.current
        for attempt in (1, 2):
            self.s.before_data("yahoo", retry=attempt > 1)
            self.seq += 1
            safe = cur["symbol"].replace("=", "_")
            rel = f"{N.YAHOO_RAW_DIR}/{self.seq:04d}_{safe}_{cur['window']}_a{attempt}.json"
            doc = {
                **cur,
                "seq": self.seq,
                "attempt": attempt,
                "file": rel,
                "url": url,
                "params": dict(params or {}),
                "requested_at": _now_ms(),
            }
            try:
                r = (self._get or YH._default_get)(
                    url, params=params, headers=headers, timeout=timeout
                )
            except requests.RequestException as e:
                doc.update(error=type(e).__name__, received_at=_now_ms())
                self._keep(rel, doc)
                if attempt == 1 and isinstance(e, _RETRYABLE):
                    continue
                raise
            body = N.redact(getattr(r, "text", "") or "")
            doc.update(
                received_at=_now_ms(),
                http_status=r.status_code,
                body_sha256=_sha(body),
                body=body,
            )
            self._keep(rel, doc)
            if r.status_code == 429:
                raise ProviderStop("호출 제한 응답(HTTP 429)")
            if attempt == 1 and _transient(r):
                continue
            return r
        raise AssertionError("도달하지 않음")

    def _keep(self, rel: str, doc: dict) -> None:
        before = self.rec.bytes
        self.rec.new_json(rel, doc)
        key = f"{doc['symbol']}|{doc['window']}"
        self.bytes_by_window[key] = (
            self.bytes_by_window.get(key, 0) + self.rec.bytes - before
        )
        self.final[key] = doc
        logger.info("POC6-19 Yahoo %s · HTTP %s", rel, doc.get("http_status"))
        self.s.after_write()


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
