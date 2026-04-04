# Health Check Report Prompt

Analyze the knowledge base for issues.

## Input

- List of all wiki notes with frontmatter
- List of all raw notes with frontmatter

## Output Format

Return valid JSON only.

```json
{
  "orphan_wiki": [],
  "stale_wiki": [],
  "missing_source": [],
  "contract_violations": [],
  "dedup_conflicts": [],
  "summary": "One paragraph summary of KB health."
}
```

## Rules

1. Check every note in the provided input.
2. Report exact file paths for each issue.
3. Include severity for every finding.
4. Output valid JSON only.
