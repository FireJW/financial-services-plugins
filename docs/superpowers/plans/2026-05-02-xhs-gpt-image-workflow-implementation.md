# XHS GPT Image Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the MVP Xiaohongshu workflow that turns benchmark posts plus local material into a reviewable XHS image-post package, with GPT Image generation available behind an explicit opt-in.

**Architecture:** Add a focused runtime module under the existing `autoresearch-info-index` scripts because this repo already keeps article, hot-topic, X, and publish workflows there. The first implementation is package-first: collect/import benchmarks, deconstruct patterns, map to local content, generate prompts/images through a configurable adapter, run QC, and write a self-contained artifact directory. Publishing remains documented and gated, not automatic.

**Tech Stack:** Python standard library, existing repo command markdown conventions, `unittest`, optional OpenAI Images API call through `urllib.request`, existing local social-card scripts as preview/fallback references only.

---

## File Structure

- Create: `financial-analysis/commands/xhs-workflow.md`
  - User-facing native command route and manual operating guide.
- Create: `financial-analysis/skills/autoresearch-info-index/scripts/xhs_workflow_runtime.py`
  - Pure runtime functions: request parsing, benchmark ranking, deconstruction, card planning, GPT Image adapter, package writing, QC report.
- Create: `financial-analysis/skills/autoresearch-info-index/scripts/xhs_workflow.py`
  - Thin CLI wrapper matching existing script style.
- Create: `tests/test_xhs_workflow_runtime.py`
  - Unit tests for ranking, package writing, dry-run image generation, QC, and CLI behavior.
- Modify: `routing-index.md`
  - Add native route for XHS image-post workflow.

## Task 1: Add Runtime Contract and Package Writer

**Files:**
- Create: `tests/test_xhs_workflow_runtime.py`
- Create: `financial-analysis/skills/autoresearch-info-index/scripts/xhs_workflow_runtime.py`

- [ ] **Step 1: Write failing tests for request parsing and package files**

```python
def test_run_xhs_workflow_writes_reviewable_package_without_external_calls(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        request = {
            "topic": "AI capex earnings",
            "local_material": {
                "title": "Big Tech capex signal",
                "summary": "Four large technology companies are raising AI infrastructure spend.",
                "key_points": ["capex acceleration", "power demand", "investor scrutiny"],
            },
            "benchmarks": [
                {
                    "url": "https://www.xiaohongshu.com/explore/demo",
                    "title": "3个信号，看懂AI投资主线",
                    "likes": 1200,
                    "collects": 800,
                    "comments": 96,
                    "posted_at": "2026-05-01",
                }
            ],
            "output_dir": temp_dir,
            "image_generation": {"mode": "dry_run"},
        }

        result = module_under_test.run_xhs_workflow(request)

    package_dir = pathlib.Path(result["package_dir"])
    self.assertEqual(result["status"], "ready_for_review")
    self.assertTrue((package_dir / "request.json").exists())
    self.assertTrue((package_dir / "benchmarks.json").exists())
    self.assertTrue((package_dir / "deconstruction.md").exists())
    self.assertTrue((package_dir / "card_plan.json").exists())
    self.assertTrue((package_dir / "generation" / "prompts.json").exists())
    self.assertTrue((package_dir / "qc_report.md").exists())
    self.assertIn("manual approval required", result["publish_gate"]["status"])
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```powershell
python -m unittest tests.test_xhs_workflow_runtime.XhsWorkflowRuntimeTests.test_run_xhs_workflow_writes_reviewable_package_without_external_calls -v
```

Expected: FAIL because `xhs_workflow_runtime.py` does not exist.

- [ ] **Step 3: Implement minimal runtime package writer**

Create `xhs_workflow_runtime.py` with:

```python
from __future__ import annotations

import base64
import datetime as dt
import json
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_IMAGE_MODEL = "gpt-image-2"
DEFAULT_CARD_COUNT = 7


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("JSON input must be an object")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip()).strip("-")
    return text[:48] or "xhs-package"


def resolve_package_dir(request: dict[str, Any]) -> Path:
    root = Path(request.get("output_dir") or "output/xhs-workflow").resolve()
    topic = str(request.get("topic") or request.get("title") or "xhs-package")
    stamp = str(request.get("run_id") or dt.datetime.now().strftime("%Y%m%d%H%M%S"))
    return root / f"{slugify(topic)}_{stamp}"


def normalize_benchmark(raw: dict[str, Any], index: int) -> dict[str, Any]:
    likes = int(raw.get("likes") or raw.get("like_count") or 0)
    collects = int(raw.get("collects") or raw.get("favorites") or raw.get("collect_count") or 0)
    comments = int(raw.get("comments") or raw.get("comment_count") or 0)
    shares = int(raw.get("shares") or raw.get("share_count") or 0)
    engagement_score = likes + collects * 1.4 + comments * 2.0 + shares * 1.2
    return {
        "rank": index + 1,
        "url": str(raw.get("url") or raw.get("note_url") or ""),
        "title": str(raw.get("title") or ""),
        "author": str(raw.get("author") or raw.get("nickname") or ""),
        "posted_at": str(raw.get("posted_at") or raw.get("created_at") or ""),
        "metrics": {
            "likes": likes,
            "collects": collects,
            "comments": comments,
            "shares": shares,
        },
        "engagement_score": round(engagement_score, 2),
        "source": raw,
    }


def rank_benchmarks(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = [normalize_benchmark(item, index) for index, item in enumerate(items)]
    ranked = sorted(normalized, key=lambda item: item["engagement_score"], reverse=True)
    for index, item in enumerate(ranked):
        item["rank"] = index + 1
    return ranked


def build_source_ledger(benchmarks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    captured_at = dt.datetime.now(dt.timezone.utc).isoformat()
    return [
        {
            "url": item["url"],
            "title": item["title"],
            "author": item["author"],
            "posted_at": item["posted_at"],
            "captured_at": captured_at,
            "collection_method": "manual_import",
            "metrics": item["metrics"],
        }
        for item in benchmarks
    ]


def run_xhs_workflow(request: dict[str, Any]) -> dict[str, Any]:
    package_dir = resolve_package_dir(request)
    benchmarks = rank_benchmarks(list(request.get("benchmarks") or []))
    source_ledger = build_source_ledger(benchmarks)
    package_dir.mkdir(parents=True, exist_ok=True)
    write_json(package_dir / "request.json", request)
    write_json(package_dir / "benchmarks.json", {"benchmarks": benchmarks})
    write_json(package_dir / "source_ledger.json", {"sources": source_ledger})
    result = {
        "status": "ready_for_review",
        "package_dir": str(package_dir),
        "benchmark_count": len(benchmarks),
        "publish_gate": {"status": "manual approval required before XHS publishing"},
    }
    write_json(package_dir / "meta.json", result)
    return result
```

- [ ] **Step 4: Run the test and keep implementing until GREEN**

Run:

```powershell
python -m unittest tests.test_xhs_workflow_runtime.XhsWorkflowRuntimeTests.test_run_xhs_workflow_writes_reviewable_package_without_external_calls -v
```

Expected: PASS after adding the remaining artifact writers introduced in Tasks 2-4.

- [ ] **Step 5: Commit**

```powershell
git add financial-analysis/skills/autoresearch-info-index/scripts/xhs_workflow_runtime.py tests/test_xhs_workflow_runtime.py
git commit -m "feat(xhs): add workflow package contract"
```

## Task 2: Add Benchmark Deconstruction and Card Planning

**Files:**
- Modify: `tests/test_xhs_workflow_runtime.py`
- Modify: `financial-analysis/skills/autoresearch-info-index/scripts/xhs_workflow_runtime.py`

- [ ] **Step 1: Write failing tests for deconstruction and card plan**

```python
def test_deconstructs_benchmarks_into_reusable_patterns_without_copying_source_text(self) -> None:
    benchmarks = module_under_test.rank_benchmarks([
        {"title": "3个信号，看懂AI投资主线", "likes": 100, "collects": 50, "comments": 20}
    ])

    patterns = module_under_test.deconstruct_benchmarks(benchmarks)

    self.assertEqual(patterns["count"], 1)
    self.assertEqual(patterns["patterns"][0]["title_formula"], "numbered_signal")
    self.assertIn("structure_only", patterns["reuse_policy"])


def test_build_card_plan_defaults_to_seven_xhs_cards(self) -> None:
    request = {
        "topic": "AI capex earnings",
        "local_material": {
            "title": "AI capex is becoming the earnings question",
            "summary": "Investors are checking whether large AI spend creates measurable returns.",
            "key_points": ["capex", "power", "ROI"],
        },
    }
    patterns = {"patterns": [{"title_formula": "numbered_signal", "card_sequence": ["cover", "why_now"]}]}

    card_plan = module_under_test.build_card_plan(request, patterns)

    self.assertEqual(len(card_plan["cards"]), 7)
    self.assertEqual(card_plan["cards"][0]["type"], "cover")
    self.assertEqual(card_plan["cards"][-1]["type"], "cta")
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m unittest tests.test_xhs_workflow_runtime.XhsWorkflowRuntimeTests.test_deconstructs_benchmarks_into_reusable_patterns_without_copying_source_text tests.test_xhs_workflow_runtime.XhsWorkflowRuntimeTests.test_build_card_plan_defaults_to_seven_xhs_cards -v
```

Expected: FAIL because `deconstruct_benchmarks` and `build_card_plan` are missing.

- [ ] **Step 3: Implement deconstruction and card plan functions**

Add:

```python
def classify_title_formula(title: str) -> str:
    if re.search(r"\d+\s*[个条点]", title):
        return "numbered_signal"
    if any(token in title for token in ["为什么", "怎么", "如何"]):
        return "question_hook"
    if any(token in title for token in ["避坑", "别再", "不要"]):
        return "risk_warning"
    return "statement_hook"


def deconstruct_benchmarks(benchmarks: list[dict[str, Any]]) -> dict[str, Any]:
    patterns = []
    for item in benchmarks:
        title = item.get("title", "")
        formula = classify_title_formula(title)
        patterns.append({
            "source_url": item.get("url", ""),
            "title_formula": formula,
            "cover_promise": "make the reader understand one concrete change quickly",
            "card_sequence": ["cover", "why_now", "key_signal", "proof", "implication", "action", "cta"],
            "reuse_boundary": "reuse structure and pacing only; do not copy source wording or media",
        })
    return {
        "count": len(patterns),
        "reuse_policy": "structure_only",
        "patterns": patterns,
    }


def build_card_plan(request: dict[str, Any], patterns: dict[str, Any]) -> dict[str, Any]:
    material = dict(request.get("local_material") or {})
    topic = str(request.get("topic") or material.get("title") or "XHS note")
    key_points = list(material.get("key_points") or [])
    while len(key_points) < 3:
        key_points.append(topic)
    cards = [
        {"index": 1, "type": "cover", "title": topic, "message": str(material.get("summary") or topic)},
        {"index": 2, "type": "why_now", "title": "为什么现在值得看", "message": key_points[0]},
        {"index": 3, "type": "signal", "title": "第一个信号", "message": key_points[0]},
        {"index": 4, "type": "proof", "title": "证据怎么落地", "message": key_points[1]},
        {"index": 5, "type": "implication", "title": "真正的变化", "message": key_points[2]},
        {"index": 6, "type": "action", "title": "可以怎么跟踪", "message": "把变化拆成可复查的指标。"},
        {"index": 7, "type": "cta", "title": "一句话收口", "message": "收藏这组信号，下次复盘直接对照。"},
    ]
    return {
        "topic": topic,
        "card_count": len(cards),
        "patterns_used": patterns.get("patterns", [])[:3],
        "cards": cards,
    }
```

- [ ] **Step 4: Write deconstruction markdown and plan JSON inside `run_xhs_workflow`**

Add artifact writes:

```python
patterns = deconstruct_benchmarks(benchmarks)
card_plan = build_card_plan(request, patterns)
write_json(package_dir / "patterns.json", patterns)
write_json(package_dir / "card_plan.json", card_plan)
(package_dir / "deconstruction.md").write_text(render_deconstruction_markdown(patterns), encoding="utf-8")
```

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
python -m unittest tests.test_xhs_workflow_runtime -v
```

Commit:

```powershell
git add financial-analysis/skills/autoresearch-info-index/scripts/xhs_workflow_runtime.py tests/test_xhs_workflow_runtime.py
git commit -m "feat(xhs): add benchmark deconstruction and card plan"
```

## Task 3: Add GPT Image Adapter with Dry-Run Default

**Files:**
- Modify: `tests/test_xhs_workflow_runtime.py`
- Modify: `financial-analysis/skills/autoresearch-info-index/scripts/xhs_workflow_runtime.py`

- [ ] **Step 1: Write failing tests for dry-run prompt metadata**

```python
def test_prepare_image_generation_prompts_uses_configurable_model_and_portrait_size(self) -> None:
    card_plan = {
        "cards": [
            {"index": 1, "type": "cover", "title": "AI capex", "message": "Watch the ROI question."},
            {"index": 2, "type": "why_now", "title": "Why now", "message": "Earnings pressure."},
        ]
    }

    generation = module_under_test.prepare_image_generation(
        card_plan,
        {"mode": "dry_run", "model": "gpt-image-2", "size": "1024x1536"},
    )

    self.assertEqual(generation["mode"], "dry_run")
    self.assertEqual(generation["model"], "gpt-image-2")
    self.assertEqual(len(generation["prompts"]), 2)
    self.assertIn("vertical 9:16", generation["prompts"][0]["prompt"])
```

- [ ] **Step 2: Run test to verify RED**

Run:

```powershell
python -m unittest tests.test_xhs_workflow_runtime.XhsWorkflowRuntimeTests.test_prepare_image_generation_prompts_uses_configurable_model_and_portrait_size -v
```

Expected: FAIL because `prepare_image_generation` is missing.

- [ ] **Step 3: Implement prompt builder and dry-run output**

Add:

```python
def build_image_prompt(card: dict[str, Any], style_profile: dict[str, Any] | None = None) -> str:
    style = style_profile or {}
    visual_style = style.get("visual_style", "premium Xiaohongshu editorial image post")
    return (
        f"{visual_style}. vertical 9:16 Xiaohongshu card. "
        f"Card type: {card.get('type')}. Title intent: {card.get('title')}. "
        f"Main message: {card.get('message')}. "
        "Use clear Chinese typography, strong hierarchy, clean composition, realistic material texture, "
        "and no copied competitor assets."
    )


def prepare_image_generation(card_plan: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or {}
    mode = str(config.get("mode") or "dry_run")
    model = str(config.get("model") or DEFAULT_IMAGE_MODEL)
    size = str(config.get("size") or "1024x1536")
    style_profile = dict(config.get("style_profile") or {})
    prompts = [
        {
            "card_index": card.get("index"),
            "card_type": card.get("type"),
            "model": model,
            "size": size,
            "prompt": build_image_prompt(card, style_profile),
        }
        for card in card_plan.get("cards", [])
    ]
    return {"mode": mode, "model": model, "size": size, "prompts": prompts, "results": []}
```

- [ ] **Step 4: Add real API function behind explicit mode**

Add a helper that only runs when `image_generation.mode == "openai"`:

```python
def generate_openai_image(prompt: str, config: dict[str, Any], output_path: Path) -> dict[str, Any]:
    api_key = config.get("api_key") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required when image_generation.mode=openai")
    payload = json.dumps({
        "model": config.get("model") or DEFAULT_IMAGE_MODEL,
        "prompt": prompt,
        "size": config.get("size") or "1024x1536",
        "quality": config.get("quality") or "medium",
        "n": 1,
    }).encode("utf-8")
    request = urllib.request.Request(
        "https://api.openai.com/v1/images/generations",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=int(config.get("timeout_seconds") or 180)) as response:
        body = json.loads(response.read().decode("utf-8"))
    b64 = body["data"][0].get("b64_json")
    if not b64:
        raise ValueError("OpenAI image response did not include b64_json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(base64.b64decode(b64))
    return {"status": "generated", "path": str(output_path), "model": config.get("model") or DEFAULT_IMAGE_MODEL}
```

Also import `os`.

- [ ] **Step 5: Write generation metadata during workflow run**

Write:

```python
generation = prepare_image_generation(card_plan, request.get("image_generation") or {})
write_json(package_dir / "generation" / "prompts.json", {"prompts": generation["prompts"]})
write_json(package_dir / "generation" / "model_run.json", generation)
```

- [ ] **Step 6: Run tests and commit**

Run:

```powershell
python -m unittest tests.test_xhs_workflow_runtime -v
```

Commit:

```powershell
git add financial-analysis/skills/autoresearch-info-index/scripts/xhs_workflow_runtime.py tests/test_xhs_workflow_runtime.py
git commit -m "feat(xhs): add gpt image generation adapter"
```

## Task 4: Add Draft, Caption, Hashtags, and QC

**Files:**
- Modify: `tests/test_xhs_workflow_runtime.py`
- Modify: `financial-analysis/skills/autoresearch-info-index/scripts/xhs_workflow_runtime.py`

- [ ] **Step 1: Write failing tests for QC report**

```python
def test_qc_report_requires_manual_publish_approval_and_source_ledger(self) -> None:
    card_plan = {"cards": [{"index": i, "type": "content", "title": str(i), "message": str(i)} for i in range(1, 8)]}
    generation = {"mode": "dry_run", "prompts": [{"card_index": i, "prompt": "vertical 9:16"} for i in range(1, 8)]}
    qc = module_under_test.build_qc_report(card_plan, generation, [{"url": "https://example.com"}])

    self.assertEqual(qc["status"], "needs_human_review")
    self.assertTrue(qc["checks"]["card_count"]["passed"])
    self.assertTrue(qc["checks"]["source_ledger"]["passed"])
    self.assertFalse(qc["checks"]["publish_approval"]["passed"])
```

- [ ] **Step 2: Run test to verify RED**

Run:

```powershell
python -m unittest tests.test_xhs_workflow_runtime.XhsWorkflowRuntimeTests.test_qc_report_requires_manual_publish_approval_and_source_ledger -v
```

Expected: FAIL because `build_qc_report` is missing.

- [ ] **Step 3: Implement draft, caption, hashtag, and QC helpers**

Add:

```python
def render_draft(card_plan: dict[str, Any]) -> str:
    lines = [f"# {card_plan.get('topic', 'XHS note')}", ""]
    for card in card_plan.get("cards", []):
        lines.append(f"## Card {card.get('index')}: {card.get('title')}")
        lines.append(str(card.get("message") or ""))
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_caption(request: dict[str, Any], card_plan: dict[str, Any]) -> str:
    topic = card_plan.get("topic") or request.get("topic") or "这组信号"
    return f"{topic}\n\n把这组图当作复盘清单：先看变化，再看证据，最后看后续验证。"


def render_hashtags(request: dict[str, Any]) -> str:
    base = ["#小红书图文", "#知识卡片", "#深度复盘"]
    topic = str(request.get("topic") or "").strip()
    if topic:
        base.insert(0, "#" + re.sub(r"\s+", "", topic)[:20])
    return "\n".join(base) + "\n"


def build_qc_report(card_plan: dict[str, Any], generation: dict[str, Any], source_ledger: list[dict[str, Any]]) -> dict[str, Any]:
    card_count = len(card_plan.get("cards", []))
    prompt_count = len(generation.get("prompts", []))
    checks = {
        "card_count": {"passed": 5 <= card_count <= 9, "value": card_count},
        "prompt_count": {"passed": prompt_count == card_count, "value": prompt_count},
        "source_ledger": {"passed": bool(source_ledger), "value": len(source_ledger)},
        "publish_approval": {"passed": False, "value": "manual approval required"},
    }
    return {
        "status": "needs_human_review",
        "checks": checks,
        "blocked_from_auto_publish": True,
    }
```

- [ ] **Step 4: Write markdown artifacts**

Inside `run_xhs_workflow`, write:

```python
(package_dir / "draft.md").write_text(render_draft(card_plan), encoding="utf-8")
(package_dir / "caption.md").write_text(render_caption(request, card_plan), encoding="utf-8")
(package_dir / "hashtags.txt").write_text(render_hashtags(request), encoding="utf-8")
qc = build_qc_report(card_plan, generation, source_ledger)
write_json(package_dir / "qc_report.json", qc)
(package_dir / "qc_report.md").write_text(render_qc_markdown(qc), encoding="utf-8")
```

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
python -m unittest tests.test_xhs_workflow_runtime -v
```

Commit:

```powershell
git add financial-analysis/skills/autoresearch-info-index/scripts/xhs_workflow_runtime.py tests/test_xhs_workflow_runtime.py
git commit -m "feat(xhs): add draft caption and qc outputs"
```

## Task 5: Add CLI Wrapper and Command Docs

**Files:**
- Create: `financial-analysis/skills/autoresearch-info-index/scripts/xhs_workflow.py`
- Create: `financial-analysis/commands/xhs-workflow.md`
- Modify: `routing-index.md`
- Modify: `tests/test_xhs_workflow_runtime.py`

- [ ] **Step 1: Write failing CLI test**

```python
def test_xhs_workflow_cli_writes_output_and_markdown(self) -> None:
    cli_path = SCRIPT_DIR / "xhs_workflow.py"
    cli_spec = importlib.util.spec_from_file_location("xhs_workflow_cli_under_test", cli_path)
    cli_module = importlib.util.module_from_spec(cli_spec)
    assert cli_spec and cli_spec.loader
    cli_spec.loader.exec_module(cli_module)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = pathlib.Path(temp_dir)
        input_path = temp_path / "request.json"
        output_path = temp_path / "result.json"
        input_path.write_text(json.dumps({
            "topic": "AI capex",
            "output_dir": str(temp_path / "out"),
            "benchmarks": [{"title": "3个信号", "likes": 10}],
            "image_generation": {"mode": "dry_run"},
        }), encoding="utf-8")

        with patch.object(sys, "argv", ["xhs_workflow.py", str(input_path), "--output", str(output_path), "--quiet"]):
            with self.assertRaises(SystemExit) as exit_context:
                cli_module.main()

    self.assertEqual(exit_context.exception.code, 0)
    self.assertTrue(output_path.exists())
    self.assertEqual(json.loads(output_path.read_text(encoding="utf-8"))["status"], "ready_for_review")
```

- [ ] **Step 2: Run test to verify RED**

Run:

```powershell
python -m unittest tests.test_xhs_workflow_runtime.XhsWorkflowRuntimeTests.test_xhs_workflow_cli_writes_output_and_markdown -v
```

Expected: FAIL because CLI wrapper does not exist.

- [ ] **Step 3: Implement CLI wrapper**

Create `xhs_workflow.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from xhs_workflow_runtime import load_json, run_xhs_workflow, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local Xiaohongshu GPT Image workflow package.")
    parser.add_argument("input", help="Path to xhs workflow request JSON")
    parser.add_argument("--output", help="Optional path to save summary JSON")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout JSON")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        result = run_xhs_workflow(load_json(Path(args.input).resolve()))
        if args.output:
            write_json(Path(args.output).resolve(), result)
        if not args.quiet:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)
    except Exception as exc:
        print(json.dumps({"status": "ERROR", "message": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Add command doc and routing entry**

`financial-analysis/commands/xhs-workflow.md` should document:

- benchmark-first workflow
- `xhs-writer-skill` as generation reference
- dry-run default
- OpenAI mode requirements
- local package outputs
- manual publish gate

`routing-index.md` should add an XHS route under the native retrieval fast map.

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
python -m unittest tests.test_xhs_workflow_runtime -v
```

Commit:

```powershell
git add financial-analysis/skills/autoresearch-info-index/scripts/xhs_workflow.py financial-analysis/commands/xhs-workflow.md routing-index.md tests/test_xhs_workflow_runtime.py
git commit -m "feat(xhs): add workflow cli and command route"
```

## Task 6: Final Verification

**Files:**
- All files above.

- [ ] **Step 1: Run focused tests**

```powershell
python -m unittest tests.test_xhs_workflow_runtime -v
```

Expected: all XHS workflow tests pass.

- [ ] **Step 2: Run a dry-run sample package**

Create a temp request manually or use the test fixture shape, then run:

```powershell
python financial-analysis/skills/autoresearch-info-index/scripts/xhs_workflow.py <request.json> --output <result.json> --quiet
```

Expected:

- `result.json` status is `ready_for_review`
- package directory contains `benchmarks.json`, `source_ledger.json`, `deconstruction.md`, `card_plan.json`, `generation/prompts.json`, `qc_report.md`, `caption.md`, and `hashtags.txt`
- no network call is made in dry-run mode

- [ ] **Step 3: Check git status**

```powershell
git status --short --branch
```

Expected: clean after commits.

- [ ] **Step 4: Summarize**

Report:

- branch and commits
- implemented files
- verification commands and results
- whether real OpenAI generation was tested
- next optional step: connect live `xiaohongshu-skills` import or run one real GPT Image package
