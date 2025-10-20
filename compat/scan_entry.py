#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compat entry to run 'app.py scanner' with a load_cfg(asof, cfg) → load_cfg(cfg) adapter.
- Patches scanner.load_cfg ONLY when its signature doesn't accept 2 positional args.
- Then invokes app.main() for subcommand 'scanner'.
"""
import sys, inspect

def _patch_load_cfg_if_needed():
    try:
        import scanner  # scanner.py
    except Exception:
        return
    orig = getattr(scanner, "load_cfg", None)
    if not callable(orig):
        return
    try:
        sig = inspect.signature(orig)
        # count positional-accepting params (excludes VAR_POSITIONAL/VAR_KEYWORD)
        pos_params = [p for p in sig.parameters.values()
                      if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        accepts_two = len(pos_params) >= 2
    except Exception:
        accepts_two = False

    if accepts_two:
        # already can accept (asof, cfg) → no patch
        return

    def load_cfg_compat(*args, **kwargs):
        """
        Accepts any of: (), (cfg), (asof, cfg), and forwards ONLY cfg to original.
        Priority to extract cfg:
          - kwargs['cfg']
          - second positional arg (args[1]) if present
          - first positional arg (args[0]) if original accepted one positional
          - otherwise, no-arg call to original
        """
        if "cfg" in kwargs:
            return orig(kwargs["cfg"])
        if len(args) >= 2:
            return orig(args[1])
        if len(args) == 1:
            try:
                return orig(args[0])
            except TypeError:
                return orig()
        return orig()

    setattr(scanner, "load_cfg", load_cfg_compat)

def main():
    _patch_load_cfg_if_needed()
    import app  # app.py defines main()
    # emulate CLI: app.py scanner
    sys.argv = ["app.py", "scanner"]
    rc = app.main()
    sys.exit(rc if isinstance(rc, int) else 0)

if __name__ == "__main__":
    main()
