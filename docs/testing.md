Tests cover pure insight rules and provider input boundaries. This document is for contributors and reviewers.

# Testing

Run `cd backend && uv run pytest`. `test_detectors.py` checks registry completeness, trigger cases, a near miss and insufficient-data behaviour. `test_statement.py` rejects oversized and negative-value CSV data. `test_mono.py` mocks HTTP and never contacts Mono.

Android test scaffolding is not complete. CI intends to run `ktlintCheck`, unit tests and `assembleDebug` once the Gradle wrapper and remaining dependencies are present.

## Related docs

- [Detectors](detectors.md)
- [Known gaps](KNOWN_GAPS.md)
