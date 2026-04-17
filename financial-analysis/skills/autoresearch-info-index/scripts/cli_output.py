#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from typing import Any, TextIO


def print_json(payload: Any, *, stream: TextIO | None = None) -> None:
    target = stream or sys.stdout
    try:
        target.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    except UnicodeEncodeError:
        target.write(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")
    target.flush()


__all__ = ["print_json"]
