#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compat entry to run 'app.py scanner' with a robust load_cfg adapter.
- Unconditionally replaces scanner.load_cfg with a tolerant adapter that accepts
  (asof, cfg) | (cfg) | () and returns a dict config.
"""
import sys, os, inspect, types

def _ensure_dict(x):
    try:
        # pandas/object-like config? Accept mapping-ish
        import collections
        if isinstance(x, dict):
            return x
        if isinstance(x, collections.abc.Mapping):
            return dict(x)
    except Exception:
        pass
    return {} if x is None else (x if isinstance(x, dict) else {})

def _read_yaml_default():
    import yaml
    # search order: config/config.yaml -> ./config.yaml
    paths = ["config/config.yaml", "config.yaml"]
    for p in paths:
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                return _ensure_dict(data)
            except Exception:
                continue
    return {}

def _install_load_cfg_adapter():
    import scanner  # scanner.py
    def load_cfg_compat(*args, **kwargs):
        """
        Accept:
          - load_cfg(asof, cfg)
          - load_cfg(cfg)
          - load_cfg()
        Rules to extract cfg:
          1) kwargs['cfg']
          2) second positional arg (args[1])
          3) first positional arg (args[0]) if dict-like
          4) fallback: read YAML (config/config.yaml or ./config.yaml)
        """
        # 1) kw
        if "cfg" in kwargs and kwargs["cfg"] is not None:
            return _ensure_dict(kwargs["cfg"])
        # 2) pos[1]
        if len(args) >= 2 and args[1] is not None:
            return _ensure_dict(args[1])
        # 3) pos[0] if dict-like
        if len(args) >= 1 and isinstance(args[0], dict):
            return _ensure_dict(args[0])
        # 4) fallback: YAML
        return _ensure_dict(_read_yaml_default())

    # 강제 바인딩(모듈 전역 치환)
    scanner.load_cfg = load_cfg_compat

def main():
    import app  # app.py defines main(); this import triggers scanner import
    _install_load_cfg_adapter()  # scanner가 로드된 직후 강제로 치환
    # emulate CLI: app.py scanner
    sys.argv = ["app.py", "scanner"]
    rc = app.main()
    sys.exit(rc if isinstance(rc, int) else 0)

if __name__ == "__main__":
    main()
