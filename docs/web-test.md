# Web test console

`/web-test` is a sandbox-only developer and QA console. It is a Vite/React website,
not the production Fetch client. It calls Fetch exclusively and never calls Mono or
collects bank credentials.

## Online preview

Deploy `web-test/` as a Vercel preview. Configure these build-time variables:

| Variable | Preview value |
|---|---|
| `VITE_CONSOLE_ENABLED` | `true` |
| `VITE_STAGING_API_URL` | `https://zenith-hackathon-project.vercel.app` |
| `VITE_LOCAL_API_URL` | `http://127.0.0.1:8000` |
| `VITE_MOCK_MODE` | `false` |
| `VITE_DENIED_HOSTS` | Comma-separated production hosts |

Enable Vercel Deployment Protection for the preview before sharing it. Client-side
environment variables are visible in the browser bundle and are not authentication.
Never put the demo inbox credential, Mono keys, JWT secrets, OTPs, BVNs or tokens in a
`VITE_` variable.

Without running tooling locally, import the GitHub repository at
<https://vercel.com/new>, set **Root Directory** to `web-test`, keep the detected Vite
build settings, add the variables above, and deploy as a preview. Vercel performs
`npm install` and `npm run build` remotely.

## Backend configuration

Set `CORS_ORIGINS` to the exact protected Vercel preview origin. Do not use a wildcard.
Set `MONO_REDIRECT_URL` to `<preview-origin>/link/callback`. The redirect only returns
the browser to the console; account status polling and webhooks remain authoritative.
Register the staging webhook as
`https://zenith-hackathon-project.vercel.app/webhooks/mono` in the Mono sandbox app.

## Unconfirmed Mono behavior

- Test institutions and credentials are supplied by the Mono sandbox experience and
  are not embedded in this repository.
- A redirect does not prove the account data is ready.
- Webhook delivery and the staging app's sandbox-key state require deployment checks.
- The current backend needs a gated `/dev/status` and per-user webhook-event endpoint
  for the complete preflight and event log.
