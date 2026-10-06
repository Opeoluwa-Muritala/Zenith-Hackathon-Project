Backend tests use pytest and fake or mocked provider clients. This document is for contributors validating changes locally.

# Testing

Run backend tests with `cd backend; uv run pytest`. `test_detectors.py` checks registry completeness, trigger cases, a near miss and insufficient-data behaviour. `test_statement.py` rejects oversized and negative-value CSV data. `test_mono.py` mocks HTTP and never contacts Mono.

The React Native client uses Expo and TypeScript. Run `cd mobile; npm test` for its TypeScript check, or `npx expo export --platform android` to validate the Android JavaScript bundle. GitHub Actions performs these checks after `npm ci`. No automated UI/device test suite is configured yet.

## Related docs

- [Mobile architecture](mobile.md)
- [Detectors](detectors.md)
- [Known gaps](KNOWN_GAPS.md)
