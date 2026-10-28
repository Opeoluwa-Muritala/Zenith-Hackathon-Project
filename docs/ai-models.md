This matrix records model compatibility evidence for Ask Your Money and insight wording. It is for developers choosing a demo configuration.
An unverified row is not a recommendation; run the synthetic eval suite before selecting a demo model.

# Model compatibility

| Groq model ID | Tool calls checked | Insight wording pass rate | Chat eval pass rate | Cost per 1,000 turns | Status / notes |
|---|---:|---:|---:|---:|---|
| `openai/gpt-oss-20b` | Groq lists tool support; live request passed | Unverified | Unverified | Unverified | Insight wording default |
| `openai/gpt-oss-120b` | Groq lists tool support; live request passed | Unverified | Unverified | Unverified | Chat default |

Both default models returned a live synthetic response; the chat model also returned a tool call. A full seeded evaluation is still required before a demo. Before demo, run `make ai-eval MODEL=<slug>` with synthetic seeded data, compare at least three supported models, and record actual pass rates and pricing from account-side usage. This repository has not measured a per-turn price.

## Related docs

- [AI boundary](ai.md)
- [Testing](testing.md)
