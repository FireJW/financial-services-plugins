# Case: Latest Event Verification

## Use When

- the user says `latest`, `today`, `current`, `still`, or asks whether a claim,
  negotiation, speech, military movement, or rumor is reliable
- the topic is moving quickly and source timing matters
- confidence needs to be separated into confirmed, likely, and inference only

## Native Route

1. Start with [`autoresearch-info-index`](../../autoresearch-info-index/SKILL.md)
2. If X posts or threads are central evidence, run [`/x-index`](../../../commands/x-index.md) first
3. If the event is macro or geopolitical and the user also wants market impact,
   chain into [`macro-shock-analysis`](../../macro-shock-analysis/SKILL.md)

## Required Output Shape

- one-line judgment
- exact `as of` timestamp
- confirmed / not confirmed / inference only
- latest signals first
- what would change the view

## Anti-Patterns

- do not let a fresh weak social post overrule stronger official or wire sources
- do not use relative dates without absolute timestamps
- do not mix negotiation chatter with confirmed meetings
