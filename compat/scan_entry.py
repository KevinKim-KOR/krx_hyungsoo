#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compat entry for 'app.py scanner'
- Replaces scanner.load_cfg and scanner.get_effective_cfg to tolerate (asof, cfg)
- Safe for repeated imports and Python 3.8 environments
"""
import sys, os, inspect

def _ensure_dict(x):
    try:
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

def _install_scanner_patches():
    import scanner
    orig_load = getattr(scanner, "load_cfg", None)
    if not callable(orig_load):
        return

    def load_cfg_compat(*args, **kwargs):
        # Flexible signature (asof, cfg), (cfg), or ()
        if "cfg" in kwargs and kwargs["cfg"] is not None:
            return _ensure_dict(kwargs["cfg"])
        if len(args) >= 2 and args[1] is not None:
            return _ensure_dict(args[1])
        if len(args) >= 1 and isinstance(args[0], dict):
            return _ensure_dict(args[0])
        # fallback
        return _ensure_dict(_read_yaml_default())

    # Override load_cfg globally
    scanner.load_cfg = load_cfg_compat

    # Patch get_effective_cfg to call our version
    orig_get_eff = getattr(scanner, "get_effective_cfg", None)
    if callable(orig_get_eff):
        def get_effective_cfg_compat(*args, **kwargs):
            import pandas as pd
            asof = None
            cfg = None
            if len(args) >= 1:
                asof = args[0]
            if len(args) >= 2:
                cfg = args[1]
            if "cfg" in kwargs:
                cfg = kwargs["cfg"]
            # Normalize
            try:
                if asof is not None:
                    pd.to_datetime(asof)
            except Exception:
                asof = None
            # Return load_cfg(cfg) effectively
            return load_cfg_compat(cfg)
        scanner.get_effective_cfg = get_effective_cfg_compat

def main():
    import app  # triggers scanner import
    _install_scanner_patches()  # enforce patch AFTER import
    sys.argv = ["app.py", "scanner"]
    rc = app.main()
    sys.exit(rc if isinstance(rc, int) else 0)

if __name__ == "__main__":
    main()
