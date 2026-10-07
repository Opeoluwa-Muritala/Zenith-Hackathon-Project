This matrix records model compatibility evidence for Ask Your Money and insight wording. It is for developers choosing a demo configuration.
An unverified row is not a recommendation; run the synthetic eval suite before selecting a demo model.

# Model compatibility

| Groq model ID | Tool calls checked | Insight wording pass rate | Chat eval pass rate | Cost per 1,000 turns | Status / notes |
|---|---:|---:|---:|---:|---|
| `llama-3.1-8b-instant` | Groq lists tool support; runtime unverified | Unverified | Unverified | Unverified | Insight wording default |
| `llama-3.3-70b-versatile` | Groq lists tool support; runtime unverified | Unverified | Unverified | Unverified | Chat default |

The default models require a live evaluation before a demo. Before demo, run `make ai-eval MODEL=<slug>` with synthetic seeded data, compare at least three supported models, and record actual pass rates and pricing from account-side usage. This repository has not measured a per-turn price.

## Related docs

- [AI boundary](ai.md)
- [Testing](testing.md)
