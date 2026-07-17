# Urgency Scoring Rules (MVP v1)

This document defines the first version of BaladiGuard urgency scoring rules.

It is the contract for issue **#29** (implement the scoring function). This issue (**#28**)
documents the factors, numeric scale, level mapping, missing-data behavior, and manually scored
examples. It does not implement runtime scoring.

BaladiGuard urgency scoring supports municipal prioritization. It is **not** an emergency dispatch
system. Life-threatening situations should be directed to emergency services outside this product.

## Output Contract

The scoring function must return:

| Field | Type | Description |
| --- | --- | --- |
| `urgencyScore` | integer `0`–`100` | Weighted total after overrides. |
| `urgencyLevel` | enum | `low`, `medium`, `high`, or `critical`. |
| `urgencyReason` | string | Short staff-facing explanation of the main drivers. |
| `factorScores` | object | Optional breakdown of the five factor contributions. |

### Level mapping

| Score range | Level | Staff meaning |
| --- | --- | --- |
| `0`–`24` | `low` | Monitor / schedule routinely. |
| `25`–`49` | `medium` | Address in normal queue order. |
| `50`–`74` | `high` | Prioritize soon; noticeable risk or disruption. |
| `75`–`100` | `critical` | Treat first among open municipal tickets. |

### Compatibility note

Current ticket storage and UI types only allow `low | medium | high`. Issue **#29** must extend
backend, admin, and mobile priority enums to include `critical`, and update
`docs/database.md` / `docs/MVP_API_CONTRACT.md` in the same change set.

Until that lands, do not persist `critical` through the existing `priority` field without the type
extension.

## Factor Weights (sum = 100)

| Factor | Max points | Purpose |
| --- | --- | --- |
| Safety risk | 40 | Injury, collision, or acute public-health hazard. |
| Location sensitivity | 20 | How consequential the place is if the issue persists. |
| Duplicate count | 15 | How many nearby open reports corroborate the issue. |
| Time open | 15 | How long the ticket has waited without resolution. |
| Evidence strength | 10 | How reliable / actionable the report evidence is. |

Score formula (before overrides):

```text
urgencyScore = safety + location + duplicates + timeOpen + evidence
urgencyLevel = map(urgencyScore)
```

## Factor Rubrics

### 1. Safety risk (0–40)

Assess from category, cleaned/original description, and photo evidence when available.

| Tier | Points | Criteria | Examples |
| --- | --- | --- | --- |
| None / cosmetic | 0 | No realistic injury or acute hazard. | Mild litter; faded paint; quiet aesthetic damage. |
| Inconvenience | 10 | Disruption or discomfort without likely injury. | Overflowing bin with odor; moderate noise; small standing water away from traffic. |
| Possible injury / collision risk | 25 | Could cause trip, fall, vehicle damage, or secondary accident if ignored. | Mid-size pothole in travel lane; broken sidewalk tile; dark street on a used path. |
| Immediate danger | 40 | Clear acute hazard to people now. | Exposed live wires; collapsed sidewalk hole; failed traffic signal at a busy intersection; deep open trench. |

Category starting hints (always refine with description/evidence):

| Category | Typical safety floor | Notes |
| --- | --- | --- |
| `traffic_signal` | 25 | Raise to 40 when intersection is busy or signal is fully dark. |
| `road_damage` | 10–25 | Raise with size, depth, and traffic speed. |
| `sidewalk_damage` | 10–25 | Raise when pedestrians or accessibility are blocked. |
| `water_leak` | 10–25 | Raise if flooding a roadway or near electrical assets. |
| `drainage` | 10–25 | Raise during rain / flooding of streets. |
| `street_lighting` | 10 | Raise to 25 on major pedestrian corridors at night. |
| `waste` | 0–10 | Raise toward 25 only for biohazard / pest / severe public-health language with corroboration. |
| `noise` | 0–10 | Rarely above inconvenience unless tied to another hazard. |
| `public_facilities` | 0–25 | Raise when playground / seating creates injury risk. |
| `PENDING_CLASSIFICATION` | 10 | Neutral until staff/AI classify; do not invent a high floor. |

### 2. Location sensitivity (0–20)

| Tier | Points | Criteria | Examples |
| --- | --- | --- | --- |
| Ordinary | 0 | Quiet residential side street or low-traffic local area. | Narrow residential lane; quiet residential sidewalk. |
| Busy public | 10 | High foot or vehicle traffic everyday location. | Hamra commercial strip; Verdun; Corniche pedestrian areas. |
| Critical place | 20 | School, hospital/clinic, major arterial, transit hub, or dense downtown choke point. | Near AUB / hospital entrance; Ring Road / major signalized junction. |

If location labels are missing, use coordinates + known Beirut landmarks when available; otherwise score `0` and note uncertainty in `urgencyReason`.

### 3. Duplicate count (0–15)

Count **nearby open** tickets in the same or similar category (from duplicate detection when available).

| Nearby open duplicates | Points |
| --- | --- |
| 0 | 0 |
| 1–2 | 5 |
| 3–5 | 10 |
| 6+ | 15 |

If duplicate detection has not run yet, score `0` and state that duplicates were unavailable.

### 4. Time open (0–15)

Measured from `createdAt` until now, only while the ticket is still open
(`SUBMITTED`, `UNDER_REVIEW`, `ASSIGNED`, `IN_PROGRESS`).  
`RESOLVED` and `CLOSED` tickets do not accumulate further age points (score `0` for this factor).

| Age while open | Points |
| --- | --- |
| Under 24 hours | 0 |
| 1–3 days | 5 |
| 4–7 days | 10 |
| Over 7 days | 15 |

If `createdAt` is missing, score `0`.

### 5. Evidence strength (0–10)

| Tier | Points | Criteria |
| --- | --- | --- |
| Weak | 0 | Vague text only; no usable location; no photo. |
| Basic | 4 | Clear description **or** precise coordinates/address. |
| Strong | 7 | Clear description **and** precise location **and** at least one photo. |
| Corroborated | 10 | Strong evidence **plus** at least one nearby open duplicate, or multiple photos that clearly show the same hazard. |

## Overrides

Apply after the weighted sum, then remapping the level:

1. **Immediate danger override:** if safety tier is Immediate danger (`40`), set level to at least `critical` and raise score to `max(score, 75)`.
2. **Sensitive + serious safety override:** if safety ≥ `25` **and** location = Critical place (`20`), set level to at least `high` and raise score to `max(score, 50)`.
3. **Emergency disclaimer:** if description clearly requests police/ambulance/fire response, keep municipal scoring if an infrastructure issue is also present, but `urgencyReason` must say BaladiGuard is not an emergency channel.
4. Cap the final score at `100`.

## Missing Optional Fields

The function must still return a score when optional inputs are absent:

| Missing input | Behavior |
| --- | --- |
| Photo | Evidence capped at Basic (`4`) unless duplicates corroborate. |
| Coordinates / address | Location sensitivity `0`; mention uncertainty. |
| Category pending | Use safety hints for `PENDING_CLASSIFICATION`; prefer description keywords. |
| Duplicate count | Treat as `0`; note “duplicates unavailable”. |
| `createdAt` | Time open `0`. |
| Cleaned description | Fall back to original/raw description. |

Never fail the whole ticket pipeline solely because optional urgency inputs are missing.

## Urgency Reason Format

Keep `urgencyReason` to one or two sentences for staff, naming the top drivers:

```text
High (62): possible injury risk from mid-lane pothole on a busy public road; 2 nearby open duplicates; open 2 days.
```

Template:

```text
{Level} ({score}): {primary safety/location driver}; {optional duplicate/time/evidence notes}.
```

## Manually Scored Example Tickets

These examples are the v1 acceptance set for #28. Issue #29 should reproduce the same levels
(and scores within ±5 points unless an override forces a floor).

### Example 1 — Small pothole, quiet street

| Field | Value |
| --- | --- |
| Category | `road_damage` |
| Description | Small shallow pothole on a quiet residential side street in Achrafieh. |
| Location | Ordinary residential |
| Duplicates | 0 |
| Age | 6 hours |
| Evidence | Text + GPS, no photo |

| Factor | Points | Why |
| --- | --- | --- |
| Safety | 10 | Inconvenience / minor vehicle bump risk. |
| Location | 0 | Ordinary. |
| Duplicates | 0 | None. |
| Time open | 0 | Under 24h. |
| Evidence | 4 | Description + location. |
| **Total** | **14 → `low`** | |

### Example 2 — Large pothole on major road

| Field | Value |
| --- | --- |
| Category | `road_damage` |
| Description | Deep pothole in the travel lane on a busy Beirut arterial; cars swerve. |
| Location | Busy public / major arterial → treat as Critical place (`20`) |
| Duplicates | 1 |
| Age | 2 days |
| Evidence | Text + GPS + photo |

| Factor | Points | Why |
| --- | --- | --- |
| Safety | 25 | Possible collision / vehicle damage. |
| Location | 20 | Major arterial. |
| Duplicates | 5 | One nearby open report. |
| Time open | 5 | 1–3 days. |
| Evidence | 7 | Strong. |
| **Total** | **62 → `high`** | Override #2 also guarantees ≥ `high`. |

### Example 3 — Broken traffic light

| Field | Value |
| --- | --- |
| Category | `traffic_signal` |
| Description | Traffic light fully dark at a busy signalized intersection. |
| Location | Critical place (`20`) |
| Duplicates | 2 |
| Age | 8 hours |
| Evidence | Text + GPS + photo |

| Factor | Points | Why |
| --- | --- | --- |
| Safety | 40 | Immediate danger at intersection. |
| Location | 20 | Critical junction. |
| Duplicates | 5 | 1–2 nearby. |
| Time open | 0 | Under 24h. |
| Evidence | 7 | Strong. |
| Weighted sum | 72 | |
| **After override #1** | **75 → `critical`** | Floor raised to critical. |

### Example 4 — Water leak near a hospital

| Field | Value |
| --- | --- |
| Category | `water_leak` |
| Description | Continuous clean water flooding the sidewalk and curb near a hospital entrance. |
| Location | Critical place (`20`) |
| Duplicates | 0 |
| Age | 1 day |
| Evidence | Text + GPS + photo |

| Factor | Points | Why |
| --- | --- | --- |
| Safety | 25 | Slip / access / secondary traffic risk. |
| Location | 20 | Hospital. |
| Duplicates | 0 | None. |
| Time open | 5 | 1–3 days. |
| Evidence | 7 | Strong. |
| **Total** | **57 → `high`** | Override #2 applies. |

### Example 5 — Overflowing garbage with several duplicates

| Field | Value |
| --- | --- |
| Category | `waste` |
| Description | Overflowing bins and garbage bags piled on a busy Hamra sidewalk; strong odor. |
| Location | Busy public (`10`) |
| Duplicates | 4 |
| Age | 5 days |
| Evidence | Text + GPS + photo + duplicates |

| Factor | Points | Why |
| --- | --- | --- |
| Safety | 10 | Public hygiene inconvenience (no biohazard claimed). |
| Location | 10 | Busy commercial strip. |
| Duplicates | 10 | 3–5 nearby. |
| Time open | 10 | 4–7 days. |
| Evidence | 10 | Corroborated. |
| **Total** | **50 → `high`** | |

### Example 6 — Broken streetlight, weak evidence

| Field | Value |
| --- | --- |
| Category | `street_lighting` |
| Description | Light not working near my house. |
| Location | Unknown / missing precise place → `0` |
| Duplicates | unavailable → `0` |
| Age | 3 days |
| Evidence | Vague text only |

| Factor | Points | Why |
| --- | --- | --- |
| Safety | 10 | Dark path inconvenience default. |
| Location | 0 | Missing. |
| Duplicates | 0 | Unavailable. |
| Time open | 5 | 1–3 days. |
| Evidence | 0 | Weak. |
| **Total** | **15 → `low`** | |

### Example 7 — Blocked drain open over seven days

| Field | Value |
| --- | --- |
| Category | `drainage` |
| Description | Storm drain blocked; street floods whenever it rains. |
| Location | Busy public (`10`) |
| Duplicates | 2 |
| Age | 9 days (still `IN_PROGRESS`) |
| Evidence | Text + address, no photo |

| Factor | Points | Why |
| --- | --- | --- |
| Safety | 25 | Flooding creates traffic / slip risk. |
| Location | 10 | Busy public. |
| Duplicates | 5 | 1–2. |
| Time open | 15 | Over 7 days. |
| Evidence | 4 | Basic (no photo). |
| **Total** | **59 → `high`** | |

### Example 8 — Exposed electrical hazard near a school

| Field | Value |
| --- | --- |
| Category | `public_facilities` *(or pending if unclassified)* |
| Description | Exposed electrical wires hanging from a damaged public light pole beside a school gate. |
| Location | Critical place (`20`) |
| Duplicates | 1 |
| Age | 4 hours |
| Evidence | Text + GPS + photo |

| Factor | Points | Why |
| --- | --- | --- |
| Safety | 40 | Immediate electrocution / fire risk. |
| Location | 20 | School. |
| Duplicates | 5 | One nearby. |
| Time open | 0 | Under 24h. |
| Evidence | 7 | Strong. |
| Weighted sum | 72 | |
| **After override #1** | **75 → `critical`** | |

## Worked Summary Table

| # | Scenario | Score | Level |
| --- | --- | --- | --- |
| 1 | Small residential pothole | 14 | `low` |
| 2 | Deep arterial pothole | 62 | `high` |
| 3 | Dark traffic signal at busy junction | 75 | `critical` |
| 4 | Water leak near hospital | 57 | `high` |
| 5 | Overflowing waste with duplicates | 50 | `high` |
| 6 | Vague broken streetlight | 15 | `low` |
| 7 | Blocked drain open 9 days | 59 | `high` |
| 8 | Exposed wires near school | 75 | `critical` |

## Out Of Scope For #28

- Implementing `score_urgency()` / Bedrock prompts → issue **#29**
- Persisting `urgencyScore` on `AiOutput` or updating ticket `priority` → issue **#29**
- Nearby duplicate detection algorithm → issue **#25**
- Department routing → later Sprint 5 issues

## Source Of Truth

- This file: `docs/urgency-scoring.md`
- Planned consumers: urgency scoring service (#29), ticket AI fields (`urgencyScore`, `urgencyReason`), admin urgency badges

When changing weights or rubrics, update this document first, then adjust #29 implementation and its unit tests in the same PR.
