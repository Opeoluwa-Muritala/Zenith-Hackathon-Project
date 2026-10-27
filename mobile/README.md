cashlens mobile is intended as a Compose Multiplatform client with shared UI, networking and MVI state. This file is for mobile contributors.

# Mobile development

The KMP conversion is incomplete: shared sources live under `composeApp/src/commonMain`, but the current Gradle project still targets the provisional Android `:app`. See `docs/KNOWN_GAPS.md` before attempting a build.

The Android backend URL is `http://10.0.2.2:8000`. Mono returns through `cashlens://mono/callback`; hosted URLs must be HTTPS and open in Custom Tabs.

## Related docs

- [Mobile architecture](../docs/mobile.md)
- [Known gaps](../docs/KNOWN_GAPS.md)
