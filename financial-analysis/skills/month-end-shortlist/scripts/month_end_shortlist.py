#!/usr/bin/env python3
from __future__ import annotations

from importlib.machinery import SourcelessFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path


PYC_PATH = (
    Path(__file__).resolve().parents[2]
    / "short-horizon-shortlist"
    / "scripts"
    / "__pycache__"
    / "month_end_shortlist.cpython-312.pyc"
)


def load_compiled_module():
    if not PYC_PATH.exists():
        raise ModuleNotFoundError(f"Compiled month_end_shortlist artifact is missing: {PYC_PATH}")
    loader = SourcelessFileLoader(__name__ + "._compiled", str(PYC_PATH))
    spec = spec_from_loader(__name__ + "._compiled", loader)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to create an import spec for {PYC_PATH}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_compiled = load_compiled_module()
__doc__ = getattr(_compiled, "__doc__", None)

for _name in dir(_compiled):
    if _name.startswith("__") and _name not in {"__all__"}:
        continue
    globals()[_name] = getattr(_compiled, _name)

if "__all__" not in globals():
    __all__ = [name for name in dir(_compiled) if not name.startswith("_")]


if __name__ == "__main__":
    raise SystemExit(main())
