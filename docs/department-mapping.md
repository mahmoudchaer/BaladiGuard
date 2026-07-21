# Department Mapping Rules

This document defines the MVP department list and category→department routing rules for
BaladiGuard.

These departments are **functional routing domains** for the Beirut pilot municipality. They are
aligned with common municipal service types (roads, waste, lighting, water, noise, traffic,
drainage, public amenities), not a scrape of every Lebanese baladiye HR org chart. Municipality
partners should validate names and ownership before production rollout. Multi-municipality overlays
can reuse the same categories with different department IDs later.

## Scope Split

| Work | Owns |
| --- | --- |
| **Issue #31 (this document + seeds + routing module)** | Authoritative mapping rules and department responsibility docs |
| **Issue #33** | Apply the map after AI classification and save a suggested department on the ticket |
| **Issue #34** | Staff manual department override |
| **RAG / vector DB** | Deferred until multi-municipality or long policy corpora justify retrieval |

Urgency scoring does not choose a department. Classification chooses a category; this map resolves
the department for that category.

## Department List

Municipality: Beirut Municipality (`bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb`).

| Department ID | Name |
| --- | --- |
| `d1111111-1111-1111-1111-111111111111` | Road Maintenance |
| `d2222222-2222-2222-2222-222222222222` | Waste Management |
| `d3333333-3333-3333-3333-333333333333` | Street Lighting |
| `d4444444-4444-4444-4444-444444444444` | Water Services |
| `d5555555-5555-5555-5555-555555555555` | Noise Control |
| `d6666666-6666-6666-6666-666666666666` | Traffic Management |
| `d7777777-7777-7777-7777-777777777777` | Drainage |
| `d8888888-8888-8888-8888-888888888888` | Public Facilities |

## Category → Department Map

| Category | Department |
| --- | --- |
| `road_damage` | Road Maintenance |
| `sidewalk_damage` | Road Maintenance |
| `waste` | Waste Management |
| `street_lighting` | Street Lighting |
| `water_leak` | Water Services |
| `noise` | Noise Control |
| `traffic_signal` | Traffic Management |
| `drainage` | Drainage |
| `public_facilities` | Public Facilities |
| `PENDING_CLASSIFICATION` | None until classified or reviewed |

## Department Responsibilities

### Road Maintenance (`d1111111-1111-1111-1111-111111111111`)

**Mandate:** Public roadway and sidewalk surface repairs.

**Linked categories:** `road_damage`, `sidewalk_damage`

**In scope:** Potholes; cracked asphalt; damaged road surfaces; broken sidewalk tiles; raised
pavement; pedestrian trip hazards on municipal paths.

**Out of scope / handoff:** Private driveways; indoor flooring; stormwater flooding caused primarily
by blocked drains → Drainage.

### Waste Management (`d2222222-2222-2222-2222-222222222222`)

**Mandate:** Garbage collection, bins, and street cleanliness.

**Linked categories:** `waste`

**In scope:** Overflowing bins; garbage bags on sidewalks; litter piles; illegal dumping of
household trash; odor from accumulated waste.

**Out of scope / handoff:** Private indoor trash; specialized hazardous industrial waste;
construction debris whose primary issue is road obstruction → coordinate with Road Maintenance.

### Street Lighting (`d3333333-3333-3333-3333-333333333333`)

**Mandate:** Public street and plaza lighting infrastructure.

**Linked categories:** `street_lighting`

**In scope:** Non-working street lamps; flickering public lights; dark stretches from broken
municipal fixtures; damaged light poles for public lighting.

**Out of scope / handoff:** Private building lights; indoor lighting; traffic signal lamps →
Traffic Management.

### Water Services (`d4444444-4444-4444-4444-444444444444`)

**Mandate:** Public water infrastructure leaks and related surface water from pipes.

**Linked categories:** `water_leak`

**In scope:** Broken public pipes; continuous clean-water flow from pavement when it has not
rained; visible leaks from municipal water infrastructure.

**Out of scope / handoff:** Private apartment plumbing with no public impact; rainwater pooling
from blocked storm drains → Drainage.

### Noise Control (`d5555555-5555-5555-5555-555555555555`)

**Mandate:** Recurring public noise disturbances that municipalities can investigate.

**Linked categories:** `noise`

**In scope:** Late-night construction noise; loud generators in public areas; recurring outdoor
noise disturbances.

**Out of scope / handoff:** Private indoor neighbor disputes without a public nuisance angle;
emergency sirens; noise that is only secondary to another primary issue (for example trash odor →
Waste Management).

### Traffic Management (`d6666666-6666-6666-6666-666666666666`)

**Mandate:** Traffic signals and intersection control devices.

**Linked categories:** `traffic_signal`

**In scope:** Non-working traffic lights; signals stuck on one color; pedestrian crossing signal
failures; damaged signal heads.

**Out of scope / handoff:** General road surface damage without a signal issue → Road Maintenance;
street lighting that is not a traffic signal → Street Lighting.

### Drainage (`d7777777-7777-7777-7777-777777777777`)

**Mandate:** Stormwater drainage and flood prevention assets.

**Linked categories:** `drainage`

**In scope:** Blocked storm drains; clogged drainage channels; rainwater pooling after rain; street
flooding tied to drainage failure.

**Out of scope / handoff:** Continuous clean-water leaks unrelated to rain → Water Services; cracked
asphalt whose primary repair need is road surface work → Road Maintenance.

### Public Facilities (`d8888888-8888-8888-8888-888888888888`)

**Mandate:** Parks, benches, playgrounds, and other public amenities.

**Linked categories:** `public_facilities`

**In scope:** Broken public benches; damaged playground equipment; unsafe park fixtures; damaged
public amenity structures.

**Out of scope / handoff:** Private property amenities; roadway pavement → Road Maintenance; waste
piled in a park that is primarily a cleanliness issue → Waste Management.

## Source Of Truth

| Artifact | Role |
| --- | --- |
| `docs/department-mapping.md` | Human-readable rules and department docs (this file) |
| `docs/complaint-categories.md` | Category taxonomy and examples; includes department column |
| `backend/scripts/db/seeds/categories.json` | Seeded categories with `departmentId` |
| `backend/scripts/db/seeds/departments.json` | Seeded department list and descriptions |
| `backend/app/services/routing/department_map.py` | Runtime map loaded from seeds |
| `backend/app/services/complaints/ticket_read_mapper.py` | Resolves department display names via the routing module |

When adding or removing categories or departments, update this document, the category taxonomy doc,
and both seed files in the same PR. Runtime consumers (duplicate similarity today; ticket department
suggestion in #33) must use the routing module rather than hardcoding IDs.
