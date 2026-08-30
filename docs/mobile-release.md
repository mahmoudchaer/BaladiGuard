# Mobile signed production builds and release process

Operator handoff for issue #192. This covers Expo Application Services (EAS)
profiles, signing credential handling, production configuration gates, internal
device validation, and rollback/hotfix steps for the citizen mobile app under
`mobile/`.

## Scope and launch platforms

| Platform | Status for MVP launch |
| --- | --- |
| Android (Play / internal APK+AAB) | **In scope** — signed production profile |
| iOS (TestFlight / App Store) | **Prepared in config** (`ios.bundleIdentifier`, privacy strings, EAS submit stub). Build/submit only when Apple Developer enrollment is approved for the municipality. |

Supported OS matrix for internal QA (Expo SDK 57 / React Native 0.86):

| Platform | Oldest supported | Newest supported |
| --- | --- | --- |
| Android | 8.0 (API 26) | Current stable (test on a recent Pixel/Samsung) |
| iOS | 15.1 (when Apple enrollment is approved) | Current stable |

Application identifiers (stable; do not change after first store listing):

- Android package: `com.baladiguard.citizen`
- iOS bundle ID: `com.baladiguard.citizen`
- Marketing version: `mobile/app.config.ts` → `version` (semver, currently `0.1.0`)
- Native build numbers: Android `versionCode` / iOS `buildNumber` start at `1` and
  auto-increment on EAS production builds (`eas.json` → `autoIncrement`)

## What must never be committed

Signing material and store credentials stay in Expo’s credential store (or the
municipality’s approved secret manager). The repository ignores:

- `*.jks`, `*.keystore`, `credentials.json`
- `google-services.json`, `GoogleService-Info.plist`
- All `.env` files (keep `mobile/.env.example` only)

`EXPO_PUBLIC_*` values are embedded in the binary — never put AWS keys, staff
passwords, or OTP secrets there.

## Production configuration gates

Runtime enforcement lives in `mobile/src/services/config.ts`:

- Public env vars are read through **literal** `process.env.EXPO_PUBLIC_*`
  references so Metro can inline them into release bundles. Do not read them
  through an `env` alias on the production path.
- `EXPO_PUBLIC_ENABLE_MOCK_API=true` is rejected when `EXPO_PUBLIC_APP_ENV` is
  `production` **or** the binary is a release build (`!__DEV__`).
- Release/production builds require an absolute **HTTPS** `EXPO_PUBLIC_API_BASE_URL`
  that is not localhost/loopback.
- `expo-image-picker` sets `microphonePermission: false` (still images only).

EAS production profile hard-codes:

```json
"EXPO_PUBLIC_APP_ENV": "production",
"EXPO_PUBLIC_ENABLE_MOCK_API": "false"
```

Set the approved API URL as an EAS secret / project env var named
`EXPO_PUBLIC_API_BASE_URL` (for example `https://api.example.gov/v1`). Optionally
set `EXPO_PUBLIC_PRIVACY_POLICY_URL` to the municipality-hosted privacy page;
otherwise the GitHub `docs/privacy-lifecycle.md` URL is used as a temporary
fallback for store metadata.

Static CI/local gate (no credentials required). This now resolves Expo config,
runs `expo-doctor` / `expo install --check`, and performs a production-like
`expo export` asserting the HTTPS API URL is embedded and localhost/mock are
absent:

```bash
cd mobile
npm run check:release
```

## One-time setup

1. Install EAS CLI globally (operators only; not required for CI):

   ```bash
   npm install -g eas-cli
   eas login
   ```

2. From `mobile/`, link the Expo project (writes `extra.eas.projectId`):

   ```bash
   eas init
   ```

   Commit the resulting `projectId` in `app.config.ts` / EAS project settings.
   Do **not** commit access tokens.

3. Create Android upload keystore and (when ready) iOS distribution certs via
   Expo — never generate committed keystores:

   ```bash
   eas credentials
   ```

   Prefer Expo-managed credentials. If the municipality requires a BYO
   keystore, import it through `eas credentials` and store the backup in the
   approved secret manager with dual-control access.

4. Configure EAS project environment for the `production` profile:

   - `EXPO_PUBLIC_API_BASE_URL=https://<approved-host>/v1`
   - `EXPO_PUBLIC_PRIVACY_POLICY_URL=https://<municipality-host>/privacy` (recommended)
   - Confirm mock remains `false` (profile default)

## Build profiles

Defined in `mobile/eas.json`:

| Profile | Distribution | Notes |
| --- | --- | --- |
| `development` | Internal dev client | For Expo dev-client debugging; mock forced off |
| `preview` | Internal APK | Device QA / stakeholder installs; HTTPS API required by runtime gate |
| `production` | Store AAB (+ iOS when enrolled) | Signed release; mock off; `APP_ENV=production`; autoIncrement |

Commands:

```bash
cd mobile
npm run build:preview
npm run build:production
# or explicitly:
eas build --platform android --profile production
eas build --platform all --profile production   # when iOS is approved
```

Artifacts are tied to the git commit SHA shown in the EAS build page. Tag that
commit after a successful release:

```bash
git tag -a mobile-v0.1.0 -m "Citizen mobile 0.1.0"
git push origin mobile-v0.1.0
```

## Permissions and denial behavior

OS permission strings (camera, photo library, location when-in-use) are declared
in `app.config.ts` and Expo plugins. In-app denial handling:

- Photo: clear error + alternate gallery/camera path (`PhotoPickerField`)
- Location: non-blocking denial message; citizen can still pick a map placeholder
  / manual pin (`deviceLocation` + `LocationFields`)

Do not request background location.

## Internal release validation checklist

Before promoting a production artifact:

1. Install the **preview** or **production** build on at least two physical
   Android devices (and iOS when launched) covering the oldest and newest
   supported OS versions in the municipality matrix.
2. Cold start, resume from background, and airplane-mode → reconnect.
3. OTP sign-in, contribution-ready profile, photo (camera + library), location
   grant + denial paths, report submit, public feed, track-by-code.
4. Confirm mock banner never appears and network traffic goes only to the
   approved HTTPS API host.
5. Upgrade test: install previous internal build, then install the candidate over
   it; confirm session restore / re-login and no crash on launch.
6. Record device models, OS versions, build ID, git SHA, and API host in the
   release notes.

## Store submit (manual)

```bash
eas submit --platform android --profile production --latest
# iOS only after Apple enrollment:
eas submit --platform ios --profile production --latest
```

Complete Play Console / App Store Connect data-safety and privacy questionnaires
using `docs/privacy-lifecycle.md` plus the hosted privacy URL. Icons live under
`mobile/assets/`. Splash is set with the `expo-splash-screen` plugin in
`mobile/app.json` (SDK 57 does not use a top-level `splash` key). The New
Architecture is always enabled; do not set `newArchEnabled` in app config.

## Rollback and hotfix

1. **Store rollback:** halt rollout / publish the previous Play track artifact
   (or prior TestFlight build). Keep the previous EAS build page open — it is
   the source of truth for the last-known-good binary + commit.
2. **Hotfix:** branch from the release tag, land the minimal fix through normal
   review + green CI, bump marketing version if user-visible, then
   `eas build --profile production` and submit.
3. **Config-only incident** (wrong API URL): update EAS project env and rebuild;
   clients cannot be patched by server config alone because `EXPO_PUBLIC_*` is
   compiled in.
4. **Compromised signing key:** rotate via `eas credentials`, invalidate the old
   upload key in Play App Signing / Apple, rebuild, and document the rotation
   time in the incident log.

## Credential rotation

| Secret | Where | Rotation |
| --- | --- | --- |
| Android upload keystore | Expo credentials / secret manager | Rotate only with Play App Signing coordination |
| Apple distribution cert / profile | Expo credentials | Annual or on compromise |
| Expo access token (CI operators) | Expo account | Revoke + re-issue; never commit |
| `EXPO_PUBLIC_API_BASE_URL` | EAS project env | Change + rebuild (not a secret, but release-critical) |

After any credential rotation, run a fresh `preview` install smoke test before
shipping production.

## Regenerating store assets

Committed PNGs under `mobile/assets/` were generated with:

```bash
cd mobile
python scripts/generate_release_assets.py
```

Requires Pillow. Re-run only when intentionally changing brand artwork; then re-run
`npm run check:release`.

## Release evidence checklist (attach to the PR / ops store)

Automated (CI / `npm run check:release`):

- [ ] Resolved Expo config package / bundle IDs / privacy strings / no mic permission
- [ ] `expo-doctor` and `expo install --check` clean
- [ ] Production-like export embeds the HTTPS API URL and omits localhost/mock

Operator (requires Expo/Apple/Play access — store without secrets):

- [ ] Linked EAS `projectId` committed after `eas init`
- [ ] Credential store confirmation (Android keystore in Expo; iOS when enrolled)
- [ ] Signed installable artifact URL / build ID from `eas build --profile production`
- [ ] Physical-device matrix: model, OS, cold start, upgrade-from-previous, crash-free
- [ ] Traceable build record: git SHA, EAS build ID, API host, tester sign-off

## Related docs

- [`docs/configuration.md`](configuration.md) — env catalog + production checklist
- [`docs/privacy-lifecycle.md`](privacy-lifecycle.md) — privacy / retention
- [`docs/cloud-setup.md`](cloud-setup.md) — API hosting prerequisites
- [`docs/security-scanning.md`](security-scanning.md) — npm audit / release handoff
