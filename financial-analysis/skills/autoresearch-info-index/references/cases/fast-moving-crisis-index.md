# Case: Fast-Moving Crisis Index

Use this case when the topic is changing by the hour and the user cares about
the newest reliable picture, especially for war, negotiations, military
movements, sanctions, or shipping disruption.

## Default Routing

1. Start with `news-index`.
2. Use `mode=crisis`.
3. Use aggressive recency windows: `10m`, `1h`, `6h`, `24h`.
4. Pull in `x-index` only when X is a real part of the live tape, not as a
   substitute for stronger sources.
5. If ship or military movement is mentioned, keep wording at `last public
   indication` unless stronger evidence exists.

## Evidence Discipline

Always split:

- `confirmed`
- `not confirmed`
- `inference only`
- `latest signals first`
- `what would change the view`

Use the dual-track model:

- `core_verdict` for official, wire, major-news, or corroborated specialist
  evidence
- `live_tape` for fresh but weaker claims from social, public trackers, blogs,
  or single-source reports

## Source Priority

1. official or government
2. wire or major news
3. specialist outlet or public tracker
4. social or rumor

Fresh weak signals may change monitoring priority. They do not raise the main
confidence level by themselves.

## Military Or Shipping Claims

- Do not state exact current military truth.
- Say `last public location` or `last public indication`.
- Give ETA ranges, not fake precision.
- If the source is public AIS or a social post, label it plainly.

## Recommended Follow-On

- If the user asks for market implications, hand the verified fact pack to
  `macro-shock-analysis`.
- If the user asks for a note or article, hand the result to the article flow
  only after the evidence pack is clean enough to support writing.
