---
description: Refresh a deck with new numbers while preserving formatting
argument-hint: "[path to .pptx file]"
---

Load the `deck-refresh` skill and update the specified presentation with new numbers.

Treat this as a controlled replacement workflow:
- collect the old-to-new mapping first
- find every occurrence before editing
- show the full change plan
- edit only after user approval

If a file path is provided, use it. Otherwise ask the user for the deck to refresh.
