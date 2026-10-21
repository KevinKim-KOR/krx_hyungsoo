"""POC6-02 — 실행 환경 · 자원 측정(설계 개정 2 §5-1 · PLAN §4). 새 의존성 0(psutil 없음).

- 메모리: POSIX = resource.ru_maxrss(macOS 바이트 · Linux KiB) · Windows = 실행 묶음 쪽에서 따로 잰다.
- CPU 병렬도: HGB 학습만(시험 예측 · 성과 0)을 스레드 {1, 논리 코어 절반, 전체} 로 3번씩 재 중앙값.
  자료가 작으면 스레드를 늘려도 빨라지지 않는다 — 그 사실을 그대로 기록한다(부하를 부풀리지 않음).
"""

from __future__ import annotations

import os
import platform
import sys
import time
from importlib import metadata
from typing import Any, Optional

LIBS = ("numpy", "scikit-learn", "scipy", "threadpoolctl", "joblib", "torch")


def library_versions() -> dict[str, Optional[str]]:
    out: dict[str, Optional[str]] = {}
    for dist in LIBS:
        try:
            out[dist] = metadata.version(dist)
        except metadata.PackageNotFoundError:
            out[dist] = None
    return out


def physical_memory_bytes() -> Optional[int]:
    try:
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
    except (AttributeError, ValueError, OSError):
        return None


def max_rss_mb() -> Optional[float]:
    try:
        import resource
    except ImportError:  # Windows
        return None
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    scale = 1.0 if sys.platform == "darwin" else 1024.0  # macOS 바이트 · Linux KiB
    return round(rss * scale / 1024 / 1024, 1)


def environment() -> dict[str, Any]:
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "python": platform.python_version(),
        "logical_cpus": os.cpu_count(),
        "memory_bytes": physical_memory_bytes(),
        "libraries": library_versions(),
        "cuda": None,  # 맥북 단계 — CUDA 는 RTX PC 실행 결과에 따로 적는다
    }


def thread_levels() -> list[int]:
    n = os.cpu_count() or 1
    return sorted({1, max(1, n // 2), n})


def hgb_thread_probe(X, y, w, fit) -> list[dict[str, Any]]:
    """같은 학습 자료 · 같은 설정의 HGB 학습 시간(스레드별 3회 중앙값). 예측 · 성과 계산 없음."""
    out = []
    for th in thread_levels():
        times = []
        for _ in range(3):
            t0 = time.perf_counter()
            fit(X, y, w, threads=th)
            times.append(time.perf_counter() - t0)
        times.sort()
        out.append(
            {"threads": th, "fit_seconds_median": times[1], "fit_seconds_min": times[0]}
        )
    return out
