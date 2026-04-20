# financial-services-plugins Topic Discovery Handoff

Date: 2026-04-17  
Repo: `D:\Users\rickylu\dev\financial-services-plugins`

## Git / Repo State

- Local branch: `main`
- Current HEAD: `2a512d2`
- HEAD summary: `feat(autoresearch): restore local work + add ai-meme and enterprise-ai-synthesis tail filters`
- Remote:
  - `origin https://github.com/FireJW/financial-services-plugins.git`
- Current local tracking view:
  - `main...origin/main [ahead 33]`

Important caveat:
- This session did **not** re-fetch from GitHub, so tracking state is only whatever local metadata currently says.
- A previous session reported that force-push was needed because remote had commits not present locally and a normal push was rejected.
- That remote divergence status has **not** been freshly revalidated here.

## Scope of Current Work

The active workstream is **topic discovery quality**, not article generation or WeChat publishing.

Main focus:
- `international_first` discovery profile
- `Reddit + X` as primary source family
- suppress low-value platform noise
- bias shortlist toward:
  - earnings
  - semis
  - AI infra
  - supply chain
  - concrete deployment/catalyst topics

## What Is Already Working

### Platform plumbing

- Queryless `Reddit` is working with cleaner source-pool logic.
- Queryless `X` is working again and contributes real items.
- Offline replay is now possible directly from full `agent-reach` diagnostic wrapper files through `channel_result_paths`.

This means ranker iteration no longer has to depend on live network each time.

### Filters already in place

The following classes are now filtered or heavily suppressed:

- generic X civic/social/political news
- generic X commentary threads
- generic X manifesto threads
- generic Reddit research chatter
- Reddit meta/live/archive threads
- broad-market Reddit question threads
- weak obituary
- off-topic platform posts
- exhibition promo
- official commentary
- diplomatic protocol filler
- non-SH/ZJ local filler

## Current Best Offline Replay

Latest replay input:
- `.tmp/topic-top6-2026-04-17-mixed-offline-v32/hot-topic-request.json`

Latest replay output:
- `.tmp/topic-top6-2026-04-17-mixed-offline-v33/hot-topic-report.md`

Current top 6:
1. `Netflix earnings beat by $0.44, revenue topped estimates`
2. `Douglas Dynamics (PLOW): 50% Market Share, Earnings Rebound, Clear Catalyst`
3. `Is an oil shock almost unavoidable?`
4. `AMD to bring back Ryzen 7 5800X3D as AM4 10th Anniversary Edition`
5. `Squid Games but its with AI Agents ...`
6. `Amazon + Anthropic; Enterprise AI Flywheel`

Recent important filtered-out items:
- `Okay, something just shifted in how I think about AI agents`
- `Why is the market reacting so positive to an indefinite US blockade?`
- `$NIO ... Beyond Tesla ...`
- generic Reddit `[R] / [D]` chatter
- explicit off-topic platform posts

## Biggest Remaining Problems

### 1. Tail quality is still not editorial-grade

The shortlist is much cleaner than before, but the tail still contains weak survivors:

- `Squid Games but its with AI Agents ...`
- `Amazon + Anthropic; Enterprise AI Flywheel`

These are the next two obvious suppression targets:
- AI meme / prompt entertainment
- generic enterprise-AI synthesis / flywheel summary

### 2. Strong candidates are still mostly single-source

Even the cleaner shortlist is still mostly:
- `source_count = 1`
- `risk_flags` include `single_source`
- operator review remains `very_thin_comment_sample`

So the next gains will come from either:
- stricter tail suppression
- or better platform source-pool breadth

### 3. There is one unrelated pre-existing test failure outside topic-discovery work

Full `test_article_publish.py` still hits an unrelated failure:

- `test_article_publish_prefer_images_keeps_screenshot_cover_with_mixed_visual_candidates`

This is a cover-selection regression, not a ranking/discovery regression.
Do not mix it into topic-discovery debugging.

## Important Files

### Ranking / filtering
- `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py`

### Platform ingestion / replay compatibility
- `financial-analysis/skills/autoresearch-info-index/scripts/agent_reach_bridge_runtime.py`

### Ranking tests
- `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`

### Bridge tests
- `financial-analysis/skills/autoresearch-info-index/tests/test_agent_reach_bridge.py`

## Recently Added / Important Contracts

### In `test_article_publish.py`

- `test_hot_topic_discovery_filters_generic_x_commentary_but_keeps_concrete_x_industry_case`
- `test_hot_topic_discovery_filters_x_manifesto_but_keeps_concrete_robotaxi_headline`
- `test_hot_topic_discovery_filters_generic_broad_market_question_but_keeps_concrete_macro_case`

### In `test_agent_reach_bridge.py`

- `test_bridge_channel_result_path_accepts_full_fetch_result_wrapper`

## Verified Status

Focused ranking-related regression subset:
- `test_article_publish.py -k "hot_topic_discovery or normalize_agent_reach_items"`
- Result: `34 passed`

Focused bridge/queryless/replay subset:
- `test_agent_reach_bridge.py -k "queryless or full_fetch_result_wrapper"`
- Result: `15 passed`

## Recommended Next Steps For Claude

Do **not** spend time re-debugging the same plumbing that is already fixed.

Best next targets:

1. Filter or heavily downrank `AI meme / prompt entertainment` posts
   - example current survivor:
     - `Squid Games but its with AI Agents ...`

2. Filter or heavily downrank `generic enterprise-AI synthesis / flywheel summary` posts
   - example current survivor:
     - `Amazon + Anthropic; Enterprise AI Flywheel`

3. Continue preserving concrete winners:
   - earnings
   - semis
   - robotaxi deployment
   - chip product / supply chain / macro transmission

4. Keep using offline replay from saved diagnostics when tuning ranker behavior.

## Bottom Line

The repo is no longer mainly blocked on platform plumbing.

The main current problem is now **editorial quality in the shortlist tail**.

If Claude continues from here, the highest-value work is:
- kill AI meme / prompt entertainment survivors
- kill generic enterprise-AI synthesis survivors
- keep concrete company / semis / earnings / AI-infra / supply-chain topics alive

