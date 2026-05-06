#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from typing import Any


ALL_PLATFORM_TARGETS = [
    "wechat_article",
    "toutiao_article",
    "xiaohongshu_cards",
    "douyin_short_video",
    "wechat_channels_script",
    "bilibili_long_video_outline",
    "x_thread",
    "linkedin_post",
    "substack_article",
]

PLATFORM_OUTPUT_FILES = {
    "wechat_article": "article.md",
    "toutiao_article": "article.md",
    "xiaohongshu_cards": "cards.md",
    "douyin_short_video": "script.md",
    "wechat_channels_script": "script.md",
    "bilibili_long_video_outline": "outline.md",
    "x_thread": "thread.md",
    "linkedin_post": "post.md",
    "substack_article": "article.md",
}

PLATFORM_LABELS = {
    "wechat_article": "WeChat article",
    "toutiao_article": "Toutiao article",
    "xiaohongshu_cards": "Xiaohongshu card copy",
    "douyin_short_video": "Douyin short video script",
    "wechat_channels_script": "WeChat Channels script",
    "bilibili_long_video_outline": "Bilibili long video outline",
    "x_thread": "X thread",
    "linkedin_post": "LinkedIn post",
    "substack_article": "Substack version",
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u200b", " ").split()).strip()


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def platform_title(platform: str, title: str) -> str:
    if platform == "toutiao_article":
        return f"What changes after {title}"
    if platform == "x_thread":
        return f"{title}: a build-in-public thread"
    if platform == "linkedin_post":
        return f"{title}: business implication"
    if platform == "substack_article":
        return f"{title}: context for international readers"
    return title


def platform_body(platform: str, title: str, thesis: str, caveats: list[str], citations: list[dict[str, str]]) -> str:
    caveat = caveats[0] if caveats else "No explicit caveat was supplied; mark this for editor review."
    source_line = ", ".join(item.get("citation_id", "") for item in citations[:3]) or "missing citation"
    if platform == "wechat_article":
        return f"# {title}\n\nThesis\n{thesis}\n\nFramework\n- What changed\n- Why the evidence boundary matters\n- What would change the view\n\nEvidence boundary\n{caveat}\n\nSources used: {source_line}\n"
    if platform == "toutiao_article":
        return f"# {platform_title(platform, title)}\n\nClear headline promise: explain who is affected and why it matters.\n\nWhat happened\n{thesis}\n\nWhat broad readers should not overread\n{caveat}\n\nSources used: {source_line}\n"
    if platform == "xiaohongshu_cards":
        return f"Card 1: Save this if you track the thesis.\nCard 2: {thesis}\nCard 3: What is already supported.\nCard 4: What is still weak evidence.\nCard 5: Practical checklist.\n- Verify the source.\n- Keep the caveat visible: {caveat}\n- Do not turn a signal into certainty.\nCard 6: Sources used: {source_line}\n"
    if platform == "douyin_short_video":
        return f"3-second hook: Everyone is watching the headline, but the real test is different.\n\nConflict: {thesis}\n\nPayoff: The viewer should separate repeated evidence from hype.\n\nScript beats:\n1. State the tension.\n2. Show the evidence boundary: {caveat}\n3. End with what to watch next.\nSources used: {source_line}\n"
    if platform == "wechat_channels_script":
        return f"Opening: I would not read this as a simple headline trade.\n\nTrust-building talk track: {thesis}\n\nBoundary to say out loud: {caveat}\n\nPrivate-domain CTA: Save this, then compare the next update against the same evidence checklist.\nSources used: {source_line}\n"
    if platform == "bilibili_long_video_outline":
        return f"# {title}\n\nChapter 1 - Setup: why the debate exists.\nChapter 2 - Core thesis: {thesis}\nChapter 3 - Case depth: what the evidence actually shows.\nChapter 4 - Caveats: {caveat}\nChapter 5 - What would change the view.\nSources used: {source_line}\n"
    if platform == "x_thread":
        return f"1/ The working thesis: {thesis}\n\n2/ What I would not overclaim: {caveat}\n\n3/ Build-in-public check: cite the evidence before tightening the conclusion.\n\n4/ Sources used: {source_line}\n"
    if platform == "linkedin_post":
        return f"{platform_title(platform, title)}\n\nProfessional insight: {thesis}\n\nBusiness implication: teams should ask what metric this changes, not only whether the story is popular.\n\nEvidence boundary: {caveat}\n\nSources used: {source_line}\n"
    return f"# {platform_title(platform, title)}\n\nContext\nFor an international audience, start with why this debate matters beyond the local platform cycle.\n\nThesis\n{thesis}\n\nEvidence boundary\n{caveat}\n\nSources used: {source_line}\n"


def build_what_not_to_say(platform: str, integrity: dict[str, Any]) -> list[str]:
    risks = [
        f"Do not present the {PLATFORM_LABELS[platform]} as newly sourced if it only repurposes the supplied source article.",
        "Do not add numbers, cases, or citations that are not in the input package.",
    ]
    if not _safe_list(integrity.get("citation_inventory")):
        risks.append("Do not imply source support where a missing citation is marked.")
    risks.extend(_clean(item) for item in _safe_list(integrity.get("key_caveats"))[:3] if _clean(item))
    risks.extend(_clean(item) for item in _safe_list(integrity.get("misread_risks"))[:3] if _clean(item))
    return list(dict.fromkeys([item for item in risks if item]))


def build_human_edit_required(platform: str, integrity: dict[str, Any]) -> list[str]:
    checks = [
        "Confirm the platform-native hook still preserves the core thesis.",
        "Verify every citation label against the supplied citation inventory.",
        "Keep the caveats visible before publishing or recording.",
    ]
    if platform in {"douyin_short_video", "wechat_channels_script", "bilibili_long_video_outline"}:
        checks.append("Read the script out loud and adjust spoken rhythm without adding claims.")
    if platform == "xiaohongshu_cards":
        checks.append("Check each card can stand alone and remains saveable.")
    if integrity.get("status") != "ok":
        checks.append("Resolve missing source integrity inputs before any external publish step.")
    return checks


def platform_citations_used(citations: list[dict[str, str]]) -> list[Any]:
    return deepcopy(citations[:5]) if citations else [{"status": "missing", "note": "No citations were supplied."}]


__all__ = [
    "ALL_PLATFORM_TARGETS",
    "PLATFORM_OUTPUT_FILES",
    "build_human_edit_required",
    "build_what_not_to_say",
    "platform_body",
    "platform_citations_used",
    "platform_title",
]
