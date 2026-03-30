# Case: Evidence To Article

## Use When

- the user wants a sourced article or draft from current news flow
- the request includes image use, article revision, or publication formatting
- the output should preserve evidence boundaries instead of free-form writing

## Native Route

1. Build the evidence pack first through [`/news-index`](../../../commands/news-index.md)
   or [`/x-index`](../../../commands/x-index.md)
2. Run [`/article-workflow`](../../../commands/article-workflow.md)
3. If the output is a macro note instead of a public article, use
   [`/macro-note-workflow`](../../../commands/macro-note-workflow.md)
4. If the user gives revision feedback, continue through
   [`/article-revise`](../../../commands/article-revise.md)

## Required Output Shape

- source result
- analysis brief
- first draft
- review / rewrite result
- final draft with traceable citations and image references

## Anti-Patterns

- do not start drafting before the evidence pack is frozen
- do not let writing quality outrun evidence quality
- do not collapse image claims, post text, and verified facts into one layer
