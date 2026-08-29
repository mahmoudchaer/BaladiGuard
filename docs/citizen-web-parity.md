# Citizen web parity matrix (issues #265 / #314)

Behavioral parity with the mobile citizen app through the **same backend
contracts**, not pixel-for-pixel native UI. Language, RTL, and translated
validation copy are owned by [#259](https://github.com/mahmoudchaer/BaladiGuard/issues/259)
(`docs/localization.md`). This issue consumes that allowlist (`en` / `ar` / `fr`)
and does not fork catalogs.

Sprint 8 issue [#314](https://github.com/mahmoudchaer/BaladiGuard/issues/314)
owns production-readiness refinement of the already-shipped web client: shared
terminology and status meaning, navigation completeness, empty/retry states,
localized chrome, contribution gating, and removal of leftover stub surfaces.
The codebases remain independent; mobile is the product reference.

Agreed responsive widths: **phone 390px**, **tablet 768px**, **desktop 1024px**.
Agreed browser E2E subset: Playwright against the **built/served SPA** and a
controlled backend (CORS + cookie session) covering guest browse/track,
notification deep-link SPA fallback, the public map, authenticated OTP restore,
and the 390 / 768 / 1024 viewports. CI runs that subset as
`npm run test:e2e` in `citizen-web/`. Fast jsdom flows stay in
`npm run test:integration`.

## Capability matrix

| Capability | Mobile | Citizen web | Notes |
| --- | --- | --- | --- |
| Public browse (paginated list) | Yes | Yes — `/reports` | Citizen-safe projection only |
| Public map + clustering | Yes | Yes — `/map` | Viewport fetch; list alternative linked |
| Public detail | Yes | Yes — `/public/:ticketNumber` | 404 for unpublished |
| Public redacted photo / placeholder | Yes | Yes — `PublicPhoto` | Fail-closed; never original `imageObjectKey` |
| Tracking by code | Yes | Yes — `/track` | Possession-based; no account required |
| Phone OTP sign-in / create | Yes | Yes — `/login` | Cookie session (`X-Citizen-Session-Mode: cookie`) |
| Restore intended route after OTP | Yes | Yes — `sanitizeReturnTo` | Allowlisted paths only; `/t/{code}` included |
| Contribution readiness | Yes | Yes | Guest drafts; OTP required before submit |
| Report submission | Yes | Yes — `/report` | Idempotency key + draft retry |
| Profile / preferences | Yes | Yes — `/profile` | Optional name/email; ticket-update channel |
| Phone change | Yes | Yes — `/profile` | Separate `CHANGE_PHONE` OTP; re-auth after |
| Account-linked history | Yes | Yes — `/history` | Protected; paginated |
| Notification deep links | Yes — `/t/{code}` | Yes — `/t/:code` | Same possession rules as mobile (#257) |
| Drafts / retries | Yes | Yes — IndexedDB + memory fallback | Guest draft 24h; migrate after OTP |
| Resolution feedback | Yes | Yes — history row actions | `CONFIRMED_FIXED` / `STILL_UNRESOLVED` |
| Privacy copy | Yes | Yes — `/privacy` | Public projection boundaries |
| Logout | Yes | Yes — profile | Clears cookie session; optional draft retain via in-page dialog |
| Status meaning / next action | Yes — track | Yes — `/track` | Shared `statusMeaning` / `nextAction` copy |
| Contribution-ready gate | Yes | Yes — `/report` | Blocks submit when `contributionReady` is false |
| Explore while signed in | Yes — tab | Yes — header Explore | Web also keeps map/list as separate routes |

## Intentionally deferred native-only capabilities

These remain mobile-only on purpose. They are not web gaps.

| Deferred capability | Why it stays native |
| --- | --- |
| Device camera capture + EXIF pipeline | Browsers expose a file picker; original capture/orientation stays on-device |
| Background GPS / always-on location | Web asks only on explicit “Use my current location”; no background tracking |
| SecureStore / Keychain session | Web uses HttpOnly cookie scoped to `/v1`; never stores a bearer token |
| Universal Links / App Links OS handoff | OS claims `https://<host>/t/*` for the installed app; the SPA still serves the same path as fallback |
| Push notification permission + device token | Web has no equivalent citizen push channel in this MVP |
| Offline queue beyond one-tab drafts | IndexedDB draft + idempotency retry only; no background sync worker |
| Custom URL scheme `baladiguard://t/{code}` | Browser deep links are HTTPS `/t/{code}` only |

## Accessibility (critical flows)

Verified on home, public browse/map/detail, track, login OTP, report, history,
profile, and `/t/:code`:

- Skip link to `#main-content` (localized), landmarks (`banner` / `navigation` / `main` / `contentinfo`), one `h1` per page
- Compact disclosure navigation below 768px; 44×44px minimum targets on primary controls
- Visible `:focus-visible` rings and 44×44px minimum targets on primary controls
- Status and urgency use text labels, not color alone
- Public map stays geographically LTR under Arabic RTL (#259)
- Text zoom / `text-size-adjust` allowed; layouts use rem and wrap instead of clipping

## Image and staff-only boundaries

Public list, map, and detail expose `photoUrl` only when staff set
`publicImageObjectKey`. Clients must never request or display `imageObjectKey`,
`imageUrl` (staff), or unredacted originals. Missing or broken public URLs
render the `PublicPhoto` placeholder. Contract tests in
`citizen-web/src/contracts/` fail if those staff-only keys appear on public
projections.

## Related issues

#253 (redaction), #255 (staff review), #256 (public projection), #257
(notification links), #258 (resolution feedback), #259 (i18n / RTL),
#312 (production integration), #314 (Sprint 8 web production-readiness).
