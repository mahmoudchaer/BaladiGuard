# AI Intake Evaluation Dataset

The reusable multilingual AI intake dataset lives at:

```text
backend/tests/fixtures/ai_intake_multilingual_cases.json
```

It is intended for the Sprint 3 AI classification, description-cleaning, and later CI regression-test work.
The file is JSON so issue #70 can load it directly from backend tests without requiring live AI credentials.

## Format

Top-level fields:

| Field | Description |
| --- | --- |
| `schemaVersion` | Dataset schema version. Increment when the fixture shape changes. |
| `datasetId` | Stable dataset identifier for test output. |
| `categorySource` | Canonical category source used when creating the expected labels. |
| `uncategorizedCategory` | MVP fallback category for out-of-scope or uncategorized inputs. |
| `cases` | Array of multilingual evaluation cases. |

Each `cases[]` entry contains:

| Field | Description |
| --- | --- |
| `id` | Stable case identifier. Test failures should print this value. |
| `languageTags` | Language/script tags such as `en`, `ar`, `fr`, `arabizi`, or `mixed`. |
| `input` | Raw citizen report text as submitted by a user. |
| `expectedCategory` | Expected MVP category ID. Must match the category seed data. |
| `classificationNotes` | Human-readable reason for the expected category. |
| `cleaningExpectations.requiredProperties` | Properties the cleaned description should satisfy. These are intentionally not one exact sentence. |
| `cleaningExpectations.mustPreserve` | Important details that should remain present after cleaning. |
| `cleaningExpectations.mustNotInvent` | Details the cleaner must not add unless they are present in the input. |

## Category Coverage

The dataset covers every MVP category in `backend/scripts/db/seeds/categories.json`:

- `road_damage`
- `waste`
- `street_lighting`
- `water_leak`
- `noise`
- `sidewalk_damage`
- `traffic_signal`
- `drainage`
- `public_facilities`
- `PENDING_CLASSIFICATION`

The MVP taxonomy does not currently define a separate `other` category. Out-of-scope or uncategorized reports use
`PENDING_CLASSIFICATION`, matching the backend default before AI classification runs.

## Regression Test Guidance

Automated tests should:

1. Load the JSON fixture.
2. For classification tests, call the classifier with `input` and compare the returned category to `expectedCategory`.
3. For description-cleaning tests, check `requiredProperties` and `mustPreserve` semantically instead of matching one exact generated sentence.
4. Assert that cleaned descriptions do not introduce any `mustNotInvent` details.
5. Include each case `id` in assertion messages so failures clearly identify the failing report.
