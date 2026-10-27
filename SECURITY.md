# Security policy

## Reporting

Report suspected credential exposure, malicious commits, or dependency compromise privately to the repository owner. Do not open a public issue containing secrets or exploit payloads.

## Repository integrity

- Never commit `.env` files. Only sanitized `.env.example` templates are allowed.
- Repository-level VS Code tasks are not accepted because folder-open tasks can execute before review.
- Executable code must not be hidden in fonts, images, or other asset extensions.
- Pull requests must pass the `Security guard` workflow and receive review before merge.
- Maintainers should require branch protection, two-factor authentication, and reviewed/signed commits for `main`.

If a malicious commit is discovered, disable affected automation, revoke exposed credentials from a known-clean machine, preserve audit evidence, restore from a known-good revision, and require contributors to replace compromised clones.
