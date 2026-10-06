This record explains the boundary between deterministic finance logic and optional model output. It is for developers and reviewers.
It records the decision made for the first AI iteration and its trade-offs.

# ADR 0004: AI may phrase facts, never calculate them

## Context

Language models can produce fluent but unsupported financial figures. The app handles sensitive personal financial information and needs an auditable source for every number.

## Decision

Keep detectors and chat calculations in deterministic backend code. Send only allow-listed aggregates to a model through a central sanitizer. Verify every number and ISO date in model output against supplied facts. Keep AI opt-in and use templates or verified summaries on failure. Route model requests through OpenRouter using privacy filters configured by environment.

## Consequences

Answers may fall back more often when models format a valid amount differently than the verifier recognises. OpenRouter and the selected inference provider remain third parties. Tool calling and the budget/rate controls require more testing before production. No real user data should be sent until privacy, retention, legal and provider terms are reviewed.

## Related docs

- [AI boundary](../ai.md)
- [Known gaps](../KNOWN_GAPS.md)
