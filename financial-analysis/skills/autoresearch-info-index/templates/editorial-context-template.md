# Editorial Context Template

<!-- 
  PURPOSE: Capture editorial preferences that cannot be inferred from topic metadata alone.
  LOCATION: Place in the article output_dir before running article_publish.py.
  The workflow reads this file at the start of the draft stage.
  
  All sections are optional. Only fill in what you want to override.
-->

## Topic

<!-- The topic title. Usually auto-filled by discovery. Override here if the
     discovery title is misleading or too broad. -->

## Analytical Chain

<!-- The specific causal / logical chain the article must follow.
     Write numbered steps showing how facts connect to conclusions.
     This prevents the draft from substituting generic business variables. -->

1. [Starting fact or data point]
2. [Cause or mechanism]
3. [Downstream effect]
4. [Final implication for the reader]

## Market Relevance Override

<!-- Two bullet points replacing the auto-generated market_relevance_zh.
     Must be specific to THIS topic, not generic industry phrases. -->
- [First specific variable to watch]
- [Second specific variable to watch]

## Rejected Titles / Directions

<!-- Titles, angles, or phrases that have been considered and rejected.
     The draft stage must NOT regenerate any of these. -->
- [Rejected title or direction 1]
- [Rejected title or direction 2]

## Style Constraints

<!-- Specific writing rules beyond the global feedback profile.
     Examples: "no generic business talk", "every paragraph must advance the causal chain" -->
- [Constraint 1]
- [Constraint 2]

## Key Decisions

<!-- Operational decisions already made for this article. -->
- push_backend: [api | browser_session]
- cover_image: [path or description]
- source_strategy: [what sources to prioritize]

## Must-Include Facts

<!-- Specific numbers, quotes, or data points that MUST appear in the article. -->
- [Fact 1]
- [Fact 2]

## Cover Image

<!-- Cover image sourcing decisions. See cover-image-sourcing-guide.md for full process.
     Priority: Unsplash real photo > Pexels > news source screenshot > AI generated.
     Record what was tried and what was chosen so new sessions don't repeat the search. -->
- source: [unsplash | pexels | news_screenshot | ai_generated]
- chosen_file: [filename in output dir]
- unsplash_id: [photo ID if applicable]
- search_keywords: [what search terms worked]
- rejected_alternatives: [what was tried and why it didn't work]
- notes: [any lessons for similar topics in the future]

## Tone

<!-- Override tone for this specific article, if different from global profile. -->
