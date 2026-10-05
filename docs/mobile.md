The client is moving to Kotlin Multiplatform so state, models, networking and Compose UI can be shared. This document is for mobile contributors and reviewers.

# Mobile architecture

`commonMain` owns serialisable API models, MVI state, intents and pure reducers. Platform source sets own secure browser launch, deep-link reception and platform storage. Android is the first target and uses Custom Tabs for Mono links; it accepts `cashlens://mono/callback`.

The intended screens are onboarding, link accounts, home, transactions, subscriptions and bills, consent manager, grouped insights and insight detail. Each must represent loading, empty, error and content states. Financial values remain integer kobo until formatted at the UI edge.

The KMP Gradle conversion and live ViewModel/API wiring are not complete. The existing `:app` module is a provisional Android shell; `composeApp` contains the first shared source files. Do not treat the current mobile build as release-ready.

## Related docs

- [Architecture](architecture.md)
- [Known gaps](KNOWN_GAPS.md)
- [Mono integration](mono-integration.md)
