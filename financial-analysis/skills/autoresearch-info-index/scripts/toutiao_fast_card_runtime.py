#!/usr/bin/env python3
"""Build a toutiao-fast-card-package/v1 from a workflow result.

Consumes the same workflow_result + selected_topic that build_publish_package()
uses for WeChat, but produces a 7-segment short-form Fast Card for Toutiao.
"""
from __future__ import annotations

from typing import Any


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _extract_section(markdown: str, heading: str) -> str:
    """Extract the text under a markdown heading (## heading).

    Returns the text between the heading and the next heading of equal or
    higher level, stripped.  Returns "" if the heading is not found.
    """
    lines = markdown.split("\n")
    capture: list[str] = []
    capturing = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") and heading.lower() in stripped.lower():
            capturing = True
            continue
        if capturing:
            if stripped.startswith("## ") or stripped.startswith("# "):
                break
            capture.append(line)
    return "\n".join(capture).strip()


def _first_line(text: str) -> str:
    """Return the first non-empty line, stripping leading list markers."""
    for line in text.split("\n"):
        cleaned = line.strip().lstrip("-").lstrip("0123456789.").strip()
        if cleaned:
            return cleaned
    return ""


def _bullet_items(text: str, limit: int = 3) -> list[str]:
    """Return up to *limit* bullet items from a markdown section."""
    items: list[str] = []
    for line in text.split("\n"):
        cleaned = line.strip().lstrip("-").lstrip("0123456789.").strip()
        if cleaned and cleaned not in items:
            items.append(cleaned)
            if len(items) >= limit:
                break
    return items


def build_toutiao_fast_card_package(
    workflow_result: dict[str, Any],
    selected_topic: dict[str, Any],
    request: dict[str, Any],
) -> dict[str, Any]:
    """Build a ``toutiao-fast-card-package/v1`` contract.

    The 7 segments follow the Toutiao Fast Card Template:
      1. title — sharp question or concrete implication
      2. one-line takeaway
      3. confirmed vs unconfirmed
      4. one conflict point
      5. one next watch item
      6. CTA to WeChat
      7. boundary statement (if sensitive; else a standard disclaimer)
    """
    final_article = safe_dict(workflow_result.get("final_article_result"))
    body_md = str(
        final_article.get("body_markdown")
        or final_article.get("article_markdown")
        or ""
    )

    title = clean_text(selected_topic.get("title")) or clean_text(final_article.get("title"))

    # --- segment 2: one-line takeaway ---
    takeaway_section = _extract_section(body_md, "一句话结论")
    one_line_takeaway = _first_line(takeaway_section) or clean_text(selected_topic.get("summary"))

    # --- segment 3: confirmed / unconfirmed ---
    confirmed_section = _extract_section(body_md, "已确认")
    unconfirmed_section = _extract_section(body_md, "未确认")
    confirmed_items = _bullet_items(confirmed_section, limit=3)
    unconfirmed_items = _bullet_items(unconfirmed_section, limit=3)
    confirmed = " / ".join(confirmed_items) if confirmed_items else clean_text(selected_topic.get("summary"))
    unconfirmed = " / ".join(unconfirmed_items) if unconfirmed_items else "暂无明确未确认项"

    # --- segment 4: conflict point ---
    conflict_section = _extract_section(body_md, "冲突点") or _extract_section(body_md, "冲突")
    conflict_point = _first_line(conflict_section) or "多方信号尚未收敛"

    # --- segment 5: next watch ---
    watch_section = _extract_section(body_md, "要盯的") or _extract_section(body_md, "接下来")
    next_watch = _first_line(watch_section) or "关注后续数据验证"

    # --- segment 6: CTA ---
    cta = clean_text(request.get("wechat_cta_text")) or "👉 完整证据链 + 模板骨架，见公众号原文"

    # --- segment 7: boundary ---
    boundary = clean_text(request.get("boundary_statement")) or "以上判断基于截稿前公开信息，不构成投资建议"

    # --- assemble segments ---
    segments = [
        {"index": 1, "role": "title", "text": title},
        {"index": 2, "role": "one_line_takeaway", "text": one_line_takeaway},
        {"index": 3, "role": "confirmed_vs_unconfirmed", "text": f"✅ {confirmed}\n❓ {unconfirmed}"},
        {"index": 4, "role": "conflict_point", "text": conflict_point},
        {"index": 5, "role": "next_watch", "text": next_watch},
        {"index": 6, "role": "cta", "text": cta},
        {"index": 7, "role": "boundary", "text": boundary},
    ]

    plain_text = "\n\n".join(seg["text"] for seg in segments)

    return {
        "contract_version": "toutiao-fast-card-package/v1",
        "title": title,
        "one_line_takeaway": one_line_takeaway,
        "confirmed": confirmed,
        "unconfirmed": unconfirmed,
        "conflict_point": conflict_point,
        "next_watch": next_watch,
        "cta": cta,
        "boundary": boundary,
        "segments": segments,
        "plain_text": plain_text,
        "keywords": [clean_text(k) for k in safe_list(selected_topic.get("keywords")) if clean_text(k)],
        "author": clean_text(request.get("author")) or "Codex",
        "analysis_time": clean_text(request.get("analysis_time")),
    }


__all__ = ["build_toutiao_fast_card_package"]
