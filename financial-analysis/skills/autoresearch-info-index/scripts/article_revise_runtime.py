#!/usr/bin/env python3
from __future__ import annotations

from article_revise_flow_runtime import build_article_revision, load_json, write_json


def run_article_revise(raw_payload):
    return build_article_revision(raw_payload)


__all__ = [
    "build_article_revision",
    "load_json",
    "run_article_revise",
    "write_json",
]
