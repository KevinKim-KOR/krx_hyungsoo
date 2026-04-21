from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
WEB_DIR = ROOT_DIR / "web"
PYTHON_BIN = ROOT_DIR / ".venv" / "bin" / "python"


def _ensure_python_exists() -> None:
    if not PYTHON_BIN.exists():
        raise FileNotFoundError("프로젝트 가상환경 Python을 찾을 수 없습니다: .venv/bin/python")


def _start_fastapi() -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    return subprocess.Popen(
        [
            str(PYTHON_BIN),
            "-m",
            "uvicorn",
            "fastapi_app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--reload",
        ],
        cwd=ROOT_DIR,
        env=env,
    )


def _start_next_dev() -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    env.setdefault("FASTAPI_INTERNAL_URL", "http://127.0.0.1:8000")
    env.setdefault("APP_BASE_URL", "http://localhost:3000")
    return subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=WEB_DIR,
        env=env,
    )


def _terminate_process(process: subprocess.Popen[bytes] | None, name: str) -> None:
    if process is None or process.poll() is not None:
        return

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        print(f"{name} 종료가 지연되어 강제 종료합니다.")
        process.kill()
        process.wait(timeout=5)


def main() -> int:
    _ensure_python_exists()

    fastapi_process: subprocess.Popen[bytes] | None = None
    next_process: subprocess.Popen[bytes] | None = None
    shutting_down = False

    def _shutdown(signum: int, _frame) -> None:
        nonlocal shutting_down
        if shutting_down:
            return
        shutting_down = True
        print(f"\n신호 {signum} 수신. 로컬 개발 서버를 종료합니다.")
        _terminate_process(next_process, "Next dev 서버")
        _terminate_process(fastapi_process, "FastAPI 서버")

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    print("FastAPI 서버를 시작합니다: http://127.0.0.1:8000")
    fastapi_process = _start_fastapi()
    time.sleep(1.0)
    if fastapi_process.poll() is not None:
        return fastapi_process.returncode or 1

    print("Next dev 서버를 시작합니다: http://localhost:3000")
    next_process = _start_next_dev()

    try:
        while True:
            if fastapi_process.poll() is not None:
                print("FastAPI 서버가 먼저 종료되었습니다. Next dev 서버도 함께 종료합니다.")
                _terminate_process(next_process, "Next dev 서버")
                return fastapi_process.returncode or 1

            if next_process.poll() is not None:
                print("Next dev 서버가 먼저 종료되었습니다. FastAPI 서버도 함께 종료합니다.")
                _terminate_process(fastapi_process, "FastAPI 서버")
                return next_process.returncode or 1

            time.sleep(0.5)
    finally:
        _terminate_process(next_process, "Next dev 서버")
        _terminate_process(fastapi_process, "FastAPI 서버")


if __name__ == "__main__":
    sys.exit(main())
