# Citizen web deployment (issue #265)

Production delivery for `citizen-web/`: HTTPS hosting, SPA deep-link fallback,
secure headers, cache rules, rollback, monitoring, and environment setup.

Language catalogs and RTL are owned by #259. This document does not replace
`docs/localization.md`.

## Environments

| Environment | `VITE_APP_ENV` | `VITE_API_BASE_URL` | `VITE_USE_MOCK_DATA` | Origin example |
| --- | --- | --- | --- | --- |
| Local | `local` | `http://localhost:8000` (default) | `false` (optional `true` for UI-only) | `http://localhost:5174` |
| Staging | `staging` | Required `https://` non-localhost API | Must be `false` | `https://citizen-staging.example` |
| Production | `production` | Required `https://` non-localhost API | Must be `false` | `https://citizen.example` |

`resolveCitizenWebConfig` fails closed if staging/production would use mock
data, HTTP, or localhost. Backend `CORS_ALLOWED_ORIGINS` must list the exact
https citizen-web origin. Prefer the same registrable site as the API so
`SameSite=Lax` cookies work.

Local setup: `docs/configuration.md` and `citizen-web/README.md`.
Cloud/API: `docs/cloud-setup.md`. Secrets: `docs/env-sync.md` — never bake AWS
credentials into the Vite bundle.

## Production build

```bash
cd citizen-web
set VITE_APP_ENV=production
set VITE_API_BASE_URL=https://api.example.test
set VITE_USE_MOCK_DATA=false
npm ci
npm run build
npm run check:production-build
```

The checker refuses source maps, mock mode, localhost API origins, demo
credentials, private-key PEM, and AWS access-key patterns. Vite is configured
with `build.sourcemap: false`.

CI runs the existing local compile (`npm run build`) plus a second production
bundle verification with the env vars above.

## Hosting requirements

Authoritative edge config is the CloudFormation template
`citizen-web/infra/cloudfront-spa.json`. `citizen-web/public/_headers` is only
a local/preview hint — CloudFront does not read it. CI validates the template
with `npm run check:cloudfront`.

| Requirement | How it is met |
| --- | --- |
| HTTPS only | CloudFront / host terminates TLS; HSTS on the SPA |
| SPA + `/t/{code}` fallback | 403/404 → `/index.html` so notification links reach the router |
| Secure headers | `nosniff`, `DENY` framing, strict referrer, limited permissions |
| Hashed assets | Long cache, immutable (`/assets/*`) |
| HTML shell | `Cache-Control: no-store` on `/index.html` |
| Authenticated API | Never cached at the edge; API must send `Cache-Control: no-store` on `/v1/citizen/**` and cookie-authenticated mutations |
| Env-specific API origin | Compile-time `VITE_API_BASE_URL` per stage; no runtime secret |

Do not cache `Set-Cookie` responses or `/v1/citizen/me*` at CloudFront. The SPA
is static; private data comes from the API with credentials included.

### Deploy the edge stack

The template creates a private S3 origin, origin access control, a CloudFront
distribution (`redirect-to-https`, SPA 403/404 → `/index.html`), managed cache
policies, and `AWS::CloudFront::ResponseHeadersPolicy` resources (HSTS, CSP,
`DENY` framing). It does not proxy `/v1/citizen/*`.

```bash
cd citizen-web
npm run check:cloudfront
aws cloudformation deploy --template-file infra/cloudfront-spa.json --stack-name baladiguard-citizen-web --parameter-overrides HostingBucketName=baladiguard-citizen-web-prod ApiOrigin=https://api.example.test AliasDomainName=citizen.example AcmCertificateArn=arn:aws:acm:us-east-1:ACCOUNT:certificate/ID --capabilities CAPABILITY_IAM
aws s3 sync dist/ s3://baladiguard-citizen-web-prod/ --delete
aws cloudfront create-invalidation --distribution-id DISTRIBUTION_ID --paths /index.html /t/*
```

Leave `AliasDomainName` and `AcmCertificateArn` empty to use the default
`*.cloudfront.net` certificate. ACM certificates for custom aliases must be in
`us-east-1`. After HTML deploys, invalidate `/index.html` only — hashed
`/assets/*` are immutable.

## Rollback

1. Keep the previous `dist/` artifact (or the prior S3 prefix / CloudFront
   invalidation target).
2. Restore that prefix as the origin default and invalidate `/index.html` plus
   `/t/*` (HTML only — hashed assets are immutable).
3. If the API contract moved, roll the API first or together; the SPA must not
   ship against an incompatible public projection (contract tests guard this).
4. Confirm `/health/ready` on the API and a guest `/reports` load on the SPA.

RPO/RTO for data stays on `docs/production-backup-restore.md`. The SPA has no
citizen datastore of its own besides ephemeral drafts in the browser.

## Monitoring ownership

| Signal | Owner | Source |
| --- | --- | --- |
| API liveness / readiness / 5xx | Ops | `docs/production-observability.md` |
| CORS / cookie auth failures | API + citizen-web | 401/403 on `/v1/citizen/**` |
| Public browse / track errors | Citizen-web + API | 5xx on `/v1/tickets/public*` and `/v1/tickets/track/*` |
| SPA origin 4xx after deploy | Platform | CloudFront 4xx on `/index.html` (should be near-zero after SPA fallback) |

Citizen-web does not emit its own CloudWatch metrics. Treat the SPA as a static
origin and page on API readiness plus edge 5xx.

## Supported browsers

Last two versions of Chrome, Edge, Firefox, and Safari on iOS/Android and
desktop. JavaScript required. Layouts are checked at 390 / 768 / 1024 CSS px.

Known limitations:

- No citizen web push; SMS/email remain the notification channels.
- A selected local photo may need to be chosen again after a browser restart
  (drafts store the uploaded object key, not the File).
- Maps stay LTR in Arabic; numbers and ticket codes stay Latin.
- Playwright Chromium is the CI browser runner (`npm run test:e2e`) against
  `vite preview` and `e2e-browser/mock-api.mjs`. jsdom flows stay in
  `citizen-web/src/e2e/` as `npm run test:integration`.

## Deep links

Notification bodies use `{CITIZEN_APP_BASE_URL}/t/{TRACKING_CODE}`
(`docs/notifications.md`). The web host must serve that path as the SPA. An
installed mobile build may claim the same HTTPS host via App Links; the website
is the fallback when the app is absent.
