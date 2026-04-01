---
name: feedback-iteration-workflow
description: Reconstruct or operate AI-assisted feedback-to-iteration loops from interviews, talks, podcasts, support logs, customer calls, social posts, and product feedback archives. Use when the task is to collect attributable public material about how a team or product/design leader uses AI in feedback synthesis, or to turn messy feedback into a practical workflow, SOP, priorities artifact, research-preview loop, or visible iteration cadence. Trigger proactively when requests mention user feedback, design iteration, product priorities, support tickets, customer calls, social posts, founder/product/design interviews, or ask to convert public interviews into an operating workflow.
---

# Feedback Iteration Workflow

Use this skill when the request is about feedback operations, not just raw
research.

This skill covers two adjacent jobs:

1. reverse-engineering a team's feedback-to-iteration method from public
   interviews or talks
2. turning a live feedback corpus into a practical operating loop

## Use This When

- the user wants interviews, talks, podcasts, or public posts collected and
  converted into a workflow or SOP
- the user asks how a product, design, or AI team uses feedback in iteration
- the user wants messy feedback from support, calls, research notes, or social
  posts turned into priorities, principles, or a weekly artifact
- the user asks for direct quote vs summary vs inference separation
- the user wants a repeatable feedback loop for research preview, beta, or fast
  visible iteration

Do not use this skill when:

- the task is primarily equity, valuation, or macro analysis
- there is no traceable evidence layer behind the feedback claims
- the user only wants a generic brainstorming list with no sourcing discipline

## Core Rules

1. never blur `direct quote`, `summary/paraphrase`, and `inference`
2. anchor all time-sensitive claims to absolute dates
3. keep representative raw evidence; AI summaries do not replace rereading
4. do not claim a full SOP if the sources only support a partial reconstruction
5. if the workflow depends on a host recap or edited transcript, flag that in
   `Unconfirmed` or the equivalent risk section

## Native Routing Order

1. if the request needs the latest or moving facts, first read
   `financial-analysis/skills/autoresearch-info-index/SKILL.md`
2. if the task is "convert public interviews into workflow", gather:
   - official episode or talk page
   - transcript, edited transcript, or notes page
   - any host recap or episode preview
   - official company page only as supporting context
3. if the task is "turn live feedback into operating loop", gather:
   - feedback corpus or samples
   - source labels and dates
   - current decision question
   - delivery cadence target
4. then use this skill to produce the operating workflow

## Minimum Workflow

1. classify the request
   - `public-method reconstruction`
   - `live feedback operations`
   - `hybrid`
2. build the evidence board
3. extract attributable claims
4. map claims into workflow stages
5. produce the operating artifact
6. state what is confirmed vs inferred

## Evidence Board Requirements

Every run should maintain a source board with:

- source URL
- exact date
- source type
- access status
- evidence class:
  - `direct quote`
  - `direct-ish`
  - `summary`
  - `supporting`
  - `inference only`
- why the source matters

Read [references/evidence-and-output-template.md](references/evidence-and-output-template.md)
for the default table shapes.

## Workflow Mapping Rules

Map findings into these stages:

1. feedback collection
2. AI cleaning / clustering
3. human judgment and prioritization
4. release mode
5. user-visible response loop
6. cadence and artifact delivery

For each stage, state:

- input
- AI role
- human decision
- output artifact
- confidence level

## Required Output Shape

Unless the user asks for another format, include:

1. one-line thesis
2. source board
3. attributable claim inventory
4. workflow table
5. operating cadence
6. risks / overclaim guardrails
7. next action

## Guardrails

- do not upgrade a host summary into a direct quote
- do not let a translated transcript masquerade as verbatim original-language
  text
- do not mistake "AI helps compress feedback" for "AI replaces product or
  design judgment"
- if a weekly cadence or artifact format is only shown in notes or preview
  copy, keep it as a proposed operating pattern, not a verified quote

## Case Reference

If the request is similar to "collect Jenny Wen on Anthropic + feedback +
design iteration and turn it into workflow", use
[references/jenny-wen-pattern.md](references/jenny-wen-pattern.md) as the
baseline pattern.
