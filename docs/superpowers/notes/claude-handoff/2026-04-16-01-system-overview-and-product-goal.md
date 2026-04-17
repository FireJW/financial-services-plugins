# System Overview And Product Goal

## What this system is

This repo is building a practical A-share trading analysis workflow with two
parallel lanes:

1. a structured shortlist / trading-plan lane for technically mature names
2. an event-driven discovery lane for names driven by earnings, orders, price
   hikes, supply-demand shifts, rumors, company responses, and X/community logic

The goal is not just to produce a filtered shortlist. The goal is to produce a
usable decision surface for active trading.

## What the user actually cares about

The user consistently values:

- expectation trading over purely backward-looking report summaries
- price reaction and consensus formation over clean-but-late formalism
- practical decision usefulness over raw field completeness

The system should help answer:

- what is actionable now
- why now
- what is already being priced
- what is still underappreciated
- where sell-the-fact or expectation-collapse risk is highest

## Current product shape

The product now already contains:

- shortlist wrapper recovery
- `Decision Factors`
- midday / post-close action summaries
- top-pick reporting control
- discovery lane reverse-injection
- X/community-driven event inputs
- rumor / company-response state machine
- multi-source event-card synthesis

This means the system is already beyond a simple filter. It is trying to become
a trader-readable analysis panel.

## The main product problem now

The current problem is no longer "we are missing too much data."

The main problem is:

- reports still read too much like structured dumps
- important points are not emphasized hard enough
- the system does not yet consistently tell the user what matters most
- grouping logic is still too close to industry coverage and not close enough to
  trading profile

## The most important live example

`中际旭创` is currently the best example of the gap.

The system already has enough inputs to say something meaningful:

- X/community reaction
- optical chain context
- Q1 interpretation from real posts
- pre-result expectation framing

But the report still does not foreground these well enough:

- what the Q1 takeaway really is
- whether the market is pricing beat / inline / miss / "pricing a beat"
- whether the reaction is convergent
- what is the actual trade framing from that reaction

So the work ahead is mostly about synthesis, emphasis, and presentation logic.

## Current user-confirmed direction

The user explicitly wants to move away from:

- `龙头 / 一线 / 二线`

and toward:

- `稳健核心`
- `高弹性`
- `补涨候选`
- `预期差最大`
- `兑现风险最高`

That is not a minor display tweak. It changes the way the decision surface
should be organized.
