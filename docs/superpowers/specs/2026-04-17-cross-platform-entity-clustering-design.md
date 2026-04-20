# Cross-Platform Entity Clustering for Topic Discovery

Date: 2026-04-17
Status: Approved
Scope: `hot_topic_discovery_runtime.py` + `test_article_publish.py`

## Problem

All top-6 topics have `source_count=1` because Reddit and X items never cluster together. The clustering logic has two isolated paths:

- **Reddit path**: matches by `reddit_tokens` overlap + query match. X items never enter this path.
- **Non-Reddit path**: matches by `brand_tokens` (must be non-empty) + `story_tokens >= 2`. But `NON_REDDIT_BRAND_TOKENS` only contains 14 AI company names, so financial topics (oil, semiconductors, earnings) never match.

The only cross-platform bridge is `title_key` exact match, which almost never fires because Reddit and X have very different title styles.

## Solution

Extend the entity vocabulary and make story tokens universal (computed for all items, not just non-Reddit).

### 1. Rename and Expand Constants

| Old Name | New Name |
|----------|----------|
| `NON_REDDIT_BRAND_TOKENS` | `CROSS_PLATFORM_ENTITY_TOKENS` |
| `NON_REDDIT_STORY_KEYWORDS` | `CROSS_PLATFORM_STORY_KEYWORDS` |
| `NON_REDDIT_TOKEN_STOPWORDS` | `CROSS_PLATFORM_TOKEN_STOPWORDS` |

`CROSS_PLATFORM_ENTITY_TOKENS` adds financial/industry entities:

```
semiconductor, asml, tsmc, amd, intel, qualcomm, hbm, gpu, chip,
netflix, nflx, tesla, tsla, nio, amazon, amzn, apple, aapl,
microsoft, msft, google, meta,
oil, crude, opec, earnings, robotaxi, ev
```

### 2. Rename Functions

| Old Name | New Name |
|----------|----------|
| `non_reddit_story_tokens()` | `cross_platform_story_tokens()` |
| `non_reddit_brand_tokens()` | `cross_platform_entity_tokens()` |

Logic unchanged. The key change is that `cross_platform_story_tokens()` is now called for ALL items (including Reddit), not just non-Reddit.

### 3. Cluster Structure Change

`new_item_cluster` and `merge_item_into_cluster` now compute `story_tokens` and `entity_tokens` for every item:

```python
def new_item_cluster(title_key, item):
    story_tokens = cross_platform_story_tokens(item)
    return {
        "title_keys": ...,
        "reddit_outbound_urls": ...,
        "reddit_tokens": reddit_cluster_tokens(item) if is_reddit else set(),
        "story_tokens": story_tokens,
        "entity_tokens": cross_platform_entity_tokens(story_tokens),
        "items": [item],
    }
```

### 4. New Cross-Platform Match Path

In `cluster_discovered_items`, after `title_key` match, before platform-specific paths, add:

```python
# Cross-platform entity match (works for any item type)
shared_entities = item_entity_tokens & cluster["entity_tokens"]
shared_story = item_story_tokens & cluster["story_tokens"]
if shared_entities and len(shared_story) >= 2:
    matching_indexes.append(index)
    continue
```

This fires when:
1. At least 1 shared entity token (e.g., "oil", "amd", "netflix")
2. At least 2 shared story tokens (prevents spurious merges)

Platform-specific paths remain as fallback for same-platform clustering.

### 5. What Does NOT Change

- Reddit-to-Reddit clustering logic (reddit_tokens path)
- All existing filters
- Scoring/ranking logic
- `source_count` computation (naturally derived from cluster source_names)

### 6. Tests

New tests in `test_article_publish.py`:

1. `test_cluster_merges_reddit_and_x_oil_items` - Reddit "oil shock" + X "oil situation in Europe" -> same cluster, source_count=2
2. `test_cluster_merges_reddit_and_x_semiconductor_items` - Reddit "AMD" + X "semiconductor stack" -> same cluster
3. `test_cluster_does_not_merge_unrelated_cross_platform_items` - Reddit "Netflix earnings" + X "oil situation" -> separate clusters

### 7. Risk Assessment

- **Low risk**: Existing Reddit-Reddit clustering untouched
- **Low risk**: Entity list is conservative (well-known tickers and industry terms)
- **Testable**: Offline replay can verify before/after immediately
