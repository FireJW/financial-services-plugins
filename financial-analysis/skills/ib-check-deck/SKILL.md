---
name: ib-check-deck
description: Investment banking presentation quality checker. Reviews a pitch deck or client-ready presentation for number consistency, data-to-narrative alignment, language polish, and formatting QC.
---

# IB Deck Checker

Perform a comprehensive QC pass across four dimensions. Read every slide, then report findings.

## Environment Check

This workflow works in both environments:
- Add-in: inspect the live deck
- Chat: inspect the uploaded `.pptx`

This is a read-and-report workflow. Do not edit unless the user explicitly asks for fixes after review.

## Step 1: Read the Deck

Extract text from every slide and keep slide-level attribution.

Write the extracted text into a markdown-like structure:

```text
## Slide 1
[slide 1 text]

## Slide 2
[slide 2 text]
```

## Step 2: Number Consistency

Run:

```bash
python ../check-deck/scripts/extract_numbers.py deck_content.md --check
```

Beyond the script output, verify:
- key metrics reconcile across slides
- totals, percentages, and growth rates are correct
- units and date periods are consistent

## Step 3: Data-to-Narrative Alignment

Test whether slide claims are actually supported by the numbers and charts:
- trend statements
- market-position claims
- strategic or valuation claims

Flag contradictions explicitly.

## Step 4: Language Polish

Look for:
- casual or vague language
- contractions
- unsupported superlatives
- terminology drift

Use `../check-deck/references/ib-terminology.md` as the replacement guide.

## Step 5: Visual and Formatting QC

Check:
- missing chart sources
- missing labels or legends
- number-format drift
- font, date, or spacing inconsistencies
- footnote and disclaimer gaps

## Step 6: Report

Use `../check-deck/references/report-format.md` for the report structure.

Classify findings as:
- `Critical` for number mismatches, factual errors, and narrative contradictions
- `Important` for language or sourcing issues
- `Minor` for polish issues

Lead with critical findings. If none are found, say so explicitly.
