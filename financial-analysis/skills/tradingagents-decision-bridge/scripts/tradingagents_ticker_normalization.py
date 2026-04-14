from __future__ import annotations

import re
from typing import Any


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def normalize_ticker(raw: str) -> str:
    text = clean_text(raw).upper()
    if not text:
        raise ValueError("Ticker is required.")

    if text.endswith(".US"):
        text = text[:-3]

    if re.fullmatch(r"\d{6}\.(SS|SH|SZ)", text):
        if text.endswith(".SH"):
            return text[:-3] + ".SS"
        return text

    if re.fullmatch(r"\d{1,5}\.HK", text):
        value = text.split(".", 1)[0]
        return f"{int(value):05d}.HK"

    if re.fullmatch(r"\d{6}", text):
        if text.startswith(("5", "6", "9")):
            return f"{text}.SS"
        if text.startswith(("0", "2", "3")):
            return f"{text}.SZ"
        raise ValueError(f"Unsupported mainland ticker prefix: {text}")

    if re.fullmatch(r"\d{1,5}", text):
        return f"{int(text):05d}.HK"

    if re.fullmatch(r"[A-Z][A-Z0-9.-]*", text):
        return text

    raise ValueError(f"Unsupported ticker format: {text}")


def detect_market(ticker: str) -> str:
    normalized = normalize_ticker(ticker)
    if normalized.endswith(".SS"):
        return "CN_SH"
    if normalized.endswith(".SZ"):
        return "CN_SZ"
    if normalized.endswith(".HK"):
        return "HK"
    return "US"


def ticker_to_tradingagents_format(normalized: str) -> str:
    return normalize_ticker(normalized)
