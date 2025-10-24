#!/usr/bin/env python3
from pathlib import Path
import os, yaml

def _candidates():
    return [
        os.environ.get("CONFIG_FILE"),
        "config/config.yaml",
        "secret/config.yaml",
        "config.yaml",
    ]

def load_config():
    tried = []
    for p in _candidates():
        if not p:
            continue
        tried.append(p)
        path = Path(p)
        if path.is_file():
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    raise FileNotFoundError(f"No config file found. Tried: {tried}")
