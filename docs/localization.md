# Localization and accessibility

BaladiGuard product UI is available in **English**, **Arabic**, and **French**. This document is the localization approach for issue #259.

## Scope

Translated catalogs cover **product UI strings** only:

- Citizen mobile and citizen web: complete phone OTP, report creation, validation and core errors, tracking, history, profile, public browsing, and navigation workflows.
- Staff dashboard: login, ticket list/map/detail chrome, review and status actions, department and field assignment, work-order and evidence workflow, category and duplicate handling, feedback, activity, comments, workforce directory, assistant, and image redaction review.

**Not translated** (and must stay in the original language):

- Citizen-written descriptions, addresses, and comments
- Staff comments and free-text assistant answers from live records
- Department names and other operational identifiers that come from the API
- Tracking codes, ticket numbers, phone numbers, and map geography

## Runtime

Each app ships its own JSON catalogs and a small `t(key)` helper:

| App | Catalogs | Persistence | RTL |
| --- | --- | --- | --- |
| `mobile/` | `src/i18n/locales/{en,ar,fr}.json` | Expo SecureStore key `baladiguard.locale` | Root `direction` + `I18nManager` (skipped under Vitest) |
| `citizen-web/` | `src/i18n/locales/{en,ar,fr}.json` | `localStorage` key `baladiguard.locale` | `document.documentElement.dir` / `lang` |
| `admin/` | `src/i18n/locales/{en,ar,fr}.json` | Same `localStorage` key | Same document `dir` / `lang` |

Stored values are **allowlisted** to `en | ar | fr`. Anything else, including empty or hostile strings, falls back to English.

Missing keys fall back to the English catalog, then to the key itself. Development builds log a warning for unknown keys.

## Arabic / RTL

- Arabic sets `dir="rtl"` (web) or `direction: 'rtl'` (mobile) so alignment, navigation chevrons, and reading order flip.
- Ticket numbers, phone numbers, and tracking codes use `ltr` isolation (`unicode-bidi: isolate`) so mixed digits stay readable.
- Maps (`react-native-maps`, Leaflet) stay **geographically LTR**. Pins and tiles are not mirrored.

## Accessibility

- Language controls are a radiogroup with named options and a minimum 44–48pt target.
- Status and urgency always include a text label (`formatStatus` / `formatPriority` / `formatStatusLabel`). Color is reinforcement only.
- Essential actions stay in normal document flow so text scaling and keyboard focus do not hide them. Web controls use visible `:focus-visible` rings already defined in global CSS.

## Ownership

| Role | Owns |
| --- | --- |
| Product / design | Source English copy and which flows are in scope |
| Engineering | Catalog keys, fallback behavior, CI parity check, RTL layout |
| Reviewers (Arabic / French) | Naturalness of translated product strings before release |

Limitations: catalogs are reviewed engineering translations for the agreed critical flows, not a certified legal translation. Citizen content is never auto-translated. Adding a fourth locale requires a new JSON file with the same keys plus an allowlist update.

## CI

`scripts/check-i18n.mjs` fails when locale files drift (missing, extra, or empty keys). `scripts/check-hardcoded-ui.mjs` fails when critical-flow screens still contain user-facing English literals that never entered a catalog. Each frontend `npm test` runs both checks first so GitHub Actions detects catalog gaps and untranslated JSX without a new workflow job. Automated accessibility tests cover representative citizen and staff workflows in English, Arabic, and French.

```bash
node scripts/check-i18n.mjs mobile/src/i18n/locales
node scripts/check-i18n.mjs admin/src/i18n/locales
node scripts/check-i18n.mjs citizen-web/src/i18n/locales
node scripts/check-hardcoded-ui.mjs admin/src
node scripts/check-hardcoded-ui.mjs citizen-web/src
node scripts/check-hardcoded-ui.mjs mobile
```
