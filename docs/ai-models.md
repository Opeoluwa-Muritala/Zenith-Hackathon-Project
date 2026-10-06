This matrix records model compatibility evidence for Ask Your Money and insight wording. It is for developers choosing a demo configuration.
An unverified row is not a recommendation; run the synthetic eval suite before selecting a demo model.

# Model compatibility

| OpenRouter model slug | Tool calls checked | Insight wording pass rate | Chat eval pass rate | Cost per 1,000 turns | Status / notes |
|---|---:|---:|---:|---:|---|
| `inclusionai/ling-3.1-flash` | Catalogue lists tool support; runtime unverified | Unverified | Unverified | Unverified | `.env.example` example only |
| `openai/gpt-6.1-sol` | Catalogue lists tool support; runtime unverified | Unverified | Unverified | Unverified | `.env.example` example only |
| `anthropic/claude-sonnet-5.5` | Catalogue lists tool support; runtime unverified | Unverified | Unverified | Unverified | Candidate only; not tested |

No demo default or fallback is selected. Before demo, run `make ai-eval MODEL=<slug>` with synthetic seeded data, compare at least three supported models, and record actual pass rates and pricing from account-side usage. This repository has not measured a per-turn price.

## Related docs

- [AI boundary](ai.md)
- [Testing](testing.md)
