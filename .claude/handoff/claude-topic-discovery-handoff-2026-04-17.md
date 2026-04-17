# Topic Discovery Handoff

Date: 2026-04-17  
Repo: `D:\Users\rickylu\dev\financial-services-plugins`  
Focus area: `international_first` topic discovery for article selection  

## TL;DR

The repo is no longer blocked on the original plumbing issues.

What now works:
- `international_first` mode exists and uses `Reddit + X` as primary sources, with domestic/news fallback no longer on the critical path for the latest offline replay.
- Queryless `Reddit` source-pool cleanup is working.
- Queryless `X` source-pool is working again and can be replayed offline from saved diagnostics.
- We added targeted filters for:
  - generic X civic/social/political noise
  - generic X commentary threads
  - generic X manifesto threads
  - generic Reddit research chatter
  - Reddit meta/live/archive threads
  - broad-market Reddit question threads
  - weak obituary / off-topic / exhibition / official commentary / non-SH-ZJ local filler

What is still weak:
- The shortlist is cleaner, but the tail is still not fully on-target.
- The current top-6 is better than before, but slots `5-6` are still weak:
  - `Squid Games but its with AI Agents ...`
  - `Amazon + Anthropic; Enterprise AI Flywheel`
- The next optimization target should be:
  - AI meme / prompt entertainment posts
  - generic enterprise-AI synthesis / flywheel summary posts

## Biggest Current Problems

### 1. Tail quality is still not editorial-grade

Current offline mixed shortlist:

1. `Netflix earnings beat by $0.44, revenue topped estimates`
2. `Douglas Dynamics (PLOW): 50% Market Share, Earnings Rebound, Clear Catalyst`
3. `Is an oil shock almost unavoidable?`
4. `AMD to bring back Ryzen 7 5800X3D as AM4 10th Anniversary Edition`
5. `Squid Games but its with AI Agents ...`
6. `Amazon + Anthropic; Enterprise AI Flywheel`

Interpretation:
- `1/2/4` are now clearly more in the desired zone.
- `3` is acceptable but still broad.
- `5/6` are the current weakest survivors and should be the next filters.

### 2. Platform candidates are still mostly single-source and thin-sample

Even the better survivors are still mostly:
- `source_count = 1`
- `risk_flags = ["single_source"]`
- `operator review = low priority | very_thin_comment_sample`

So the ranker is cleaner, but the source pool itself still needs stronger quality signals or stronger tail suppression.

### 3. There is one unrelated pre-existing failure outside this topic-discovery work

Running the full `test_article_publish.py` still hits an unrelated failing test:

- `test_article_publish_prefer_images_keeps_screenshot_cover_with_mixed_visual_candidates`

This is a cover-selection regression and is not caused by the current topic-discovery changes.

Do not waste time conflating that failure with ranking work.

### 4. Git/worktree state is still not trustworthy

Historically in this repo:
- `.git` has been corrupted
- branch state has not been treated as reliable

So assume:
- local file state is the source of truth
- do not over-trust branch metadata until verified independently

## Most Important Files

### Ranking and filtering
- `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\scripts\hot_topic_discovery_runtime.py`

This file now contains the main heuristics for:
- `international_first`
- platform-first floor
- Reddit/X candidate filters
- X commentary / manifesto suppression
- broad-market question suppression

### Platform ingestion / replay compatibility
- `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\scripts\agent_reach_bridge_runtime.py`

This file now contains:
- queryless Reddit feed/search logic
- queryless X query-pack execution
- wrapper-file replay compatibility through `channel_result_paths`
- X field fallbacks for `author.username`, `screen_name`, `id -> status URL`, `createdAt`

### Tests
- `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`
- `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_agent_reach_bridge.py`

These contain the latest contracts for:
- generic X commentary filtering
- X manifesto filtering
- broad-market Reddit question filtering
- wrapper replay through `channel_result_paths`

## Latest Important Behavioral Changes

### A. Generic X commentary now filters

Purpose:
- remove first-person “AI changed how I think” / “what excites me most” / “worth sitting with” style threads
- keep concrete company / market / supply-chain / semis / robotaxi / earnings cases

Effect:
- `Okay, something just shifted in how I think about AI agents` is now filtered.

### B. Generic X manifesto now filters

Purpose:
- remove ultra-long thesis/manifesto threads with ticker spam and “the bottom line / X wins / not a single-company story”
- keep concrete robotaxi/company headlines

Effect:
- `$NIO #NIO #TESLA ... Beyond Tesla: The Growing Army of Robotaxi Challengers ...` is now filtered.

### C. Generic broad-market Reddit question now filters

Purpose:
- remove vague “why is the market doing X?” threads
- keep more concrete macro-risk topics

Effect:
- `Why is the market reacting so positive to an indefinite US blockade?` is now filtered.
- `Is an oil shock almost unavoidable?` remains.

### D. Offline replay from full diagnostics now works

Before:
- `channel_result_paths` only worked if given raw channel payloads
- full `results_by_channel` wrappers did not replay correctly

Now:
- full diagnostic files can be replayed directly
- this is important because it lets us iterate on ranking without touching live network behavior every time

## Latest Offline Replay Inputs and Outputs

Replay request:
- `D:\Users\rickylu\dev\financial-services-plugins\.tmp\topic-top6-2026-04-17-mixed-offline-v32\hot-topic-request.json`

Latest replayed shortlist report:
- `D:\Users\rickylu\dev\financial-services-plugins\.tmp\topic-top6-2026-04-17-mixed-offline-v33\hot-topic-report.md`

Important filtered-out topics in latest replay:
- `Okay, something just shifted in how I think about AI agents`
- `Why is the market reacting so positive to an indefinite US blockade?`
- `$NIO #NIO #TESLA $TSLA Beyond Tesla ...`
- generic Reddit `[R]` / `[D]` chatter
- explicit off-topic platform post

## Verified Tests

Relevant focused verification that passed:

### Topic discovery / normalization subset
Command concept:
- `pytest test_article_publish.py -k "hot_topic_discovery or normalize_agent_reach_items"`

Result:
- `34 passed`

### Bridge / queryless / wrapper replay subset
Command concept:
- `pytest test_agent_reach_bridge.py -k "queryless or full_fetch_result_wrapper"`

Result:
- `15 passed`

### Important targeted tests now present

In `test_article_publish.py`:
- `test_hot_topic_discovery_filters_generic_x_commentary_but_keeps_concrete_x_industry_case`
- `test_hot_topic_discovery_filters_x_manifesto_but_keeps_concrete_robotaxi_headline`
- `test_hot_topic_discovery_filters_generic_broad_market_question_but_keeps_concrete_macro_case`

In `test_agent_reach_bridge.py`:
- `test_bridge_channel_result_path_accepts_full_fetch_result_wrapper`

## What Claude Should Focus On Next

Do not spend time re-debugging the same old plumbing.

The next best work is editorial-quality tail cleanup:

### Priority 1
Filter or heavily downrank:
- AI meme / prompt entertainment threads
- example current survivor:
  - `Squid Games but its with AI Agents ...`

### Priority 2
Filter or heavily downrank:
- generic enterprise-AI synthesis / flywheel summary posts
- example current survivor:
  - `Amazon + Anthropic; Enterprise AI Flywheel`

### Priority 3
If enough stronger topics exist, continue biasing toward:
- earnings
- semiconductors
- AI infra
- supply chain
- explicit deployment or market catalyst

### Priority 4
Avoid overcorrecting:
- do not break concrete robotaxi/company headlines
- do not break semis / earnings / guidance / chip-product cases
- do not revert wrapper replay compatibility

## Recommended Working Style For Claude

1. Do not touch article generation or WeChat code for this task.
2. Stay inside:
   - `hot_topic_discovery_runtime.py`
   - `agent_reach_bridge_runtime.py`
   - the two associated test files
3. Use TDD narrowly:
   - add one failing test for one bad tail type
   - implement minimal filter
   - rerun focused subsets
4. Prefer offline replay from the saved diagnostics over live fetch while tuning ranker behavior.

## Useful Current File Targets

- Ranking logic:
  - `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\scripts\hot_topic_discovery_runtime.py`
- Platform replay / ingestion:
  - `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\scripts\agent_reach_bridge_runtime.py`
- Ranking tests:
  - `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`
- Bridge tests:
  - `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_agent_reach_bridge.py`
- Latest replay shortlist:
  - `D:\Users\rickylu\dev\financial-services-plugins\.tmp\topic-top6-2026-04-17-mixed-offline-v33\hot-topic-report.md`

## Bottom Line

The main repo problem is no longer infrastructure.  
The main repo problem is editorial quality in the tail of the shortlist.

The system is now good enough that the next gains will come from:
- suppressing AI meme/prompt entertainment
- suppressing generic enterprise-AI summary threads
- continuing to favor concrete company / semis / earnings / AI-infra / supply-chain topics

