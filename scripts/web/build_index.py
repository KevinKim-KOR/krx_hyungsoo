#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Thin wrapper to call web/build_index.py (kept for backward-compatible entrypoints).
"""
from __future__ import annotations
from pathlib import Path
import runpy, sys

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "web" / "build_index.py"

if __name__ == "__main__":
    sys.path.insert(0, str((ROOT / "web").resolve()))
    runpy.run_path(str(TARGET), run_name="__main__")
