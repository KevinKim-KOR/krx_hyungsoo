# -*- coding: utf-8 -*-
"""
Compatibility shim for scanner.load_cfg signature mismatch.
- If scanner.load_cfg accepts <2 positional params but is called with 2,
  wrap it to accept (*args, **kwargs) and forward only the config object.
- Non-intrusive: imported automatically by Python if present in sys.path.
"""
import inspect

def _install():
    try:
        import scanner  # the module where load_cfg is defined
    except Exception:
        return
    orig = getattr(scanner, "load_cfg", None)
    if not callable(orig):
        return

    try:
        sig = inspect.signature(orig)
        param_count = sum(1 for p in sig.parameters.values()
                          if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD))
    except Exception:
        # If introspection fails, do nothing
        return

    # Only wrap when the original does not support two positional args
    if param_count >= 2:
        return

    def load_cfg_compat(*args, **kwargs):
        """
        Accepts (asof, cfg) or (cfg) or () and adapts to the original signature.
        Priority of extracting cfg:
          1) kwargs['cfg']
          2) second positional arg (args[1]) if present
          3) first positional arg (args[0]) if original accepts one positional
          4) no-arg call
        """
        # kwarg path
        if "cfg" in kwargs:
            return orig(kwargs["cfg"])

        # positional path
        if len(args) >= 2:
            # called like load_cfg(asof, cfg)
            return orig(args[1])
        elif len(args) == 1:
            # called like load_cfg(cfg) while original may accept one param
            try:
                return orig(args[0])
            except TypeError:
                # original expects 0-arg → fallback
                return orig()
        else:
            # no-arg call
            return orig()

    # install wrapper
    setattr(scanner, "load_cfg", load_cfg_compat)

try:
    _install()
except Exception:
    # Never block app startup due to shim errors
    pass
