# Complaint Categories

This document defines the MVP complaint taxonomy used by the AI classifier, staff dashboard filters,
staff review controls, seed data, and mock ticket fixtures.

The internal keys below are stable identifiers. User-facing labels may be translated or rewritten in
the UI without changing these keys.

## Category Reference

| Internal key | Display label | Department mapping | Representative examples |
| --- | --- | --- | --- |
| `road_damage` | Road damage | Road Maintenance (`d1111111-1111-1111-1111-111111111111`) | Potholes; cracked asphalt; damaged road surface; road hole causing cars to swerve. |
| `waste` | Waste | Waste Management (`d2222222-2222-2222-2222-222222222222`) | Overflowing bins; garbage bags on sidewalks; litter piles; strong odor from trash. |
| `street_lighting` | Street lighting | Street Lighting (`d3333333-3333-3333-3333-333333333333`) | Street light not working; flickering public light; dark street due to broken lamp. |
| `water_leak` | Water leak | Water Services (`d4444444-4444-4444-4444-444444444444`) | Broken pipe; water leaking from pavement; constant clean water flow; public water infrastructure leak. |
| `noise` | Noise | Noise Control (`d5555555-5555-5555-5555-555555555555`) | Late-night construction noise; loud generators; recurring public noise disturbance. |
| `sidewalk_damage` | Sidewalk damage | Road Maintenance (`d1111111-1111-1111-1111-111111111111`) | Broken sidewalk tiles; raised pavement causing trip hazards; blocked or unsafe pedestrian path. |
| `traffic_signal` | Traffic signal | Traffic Management (`d6666666-6666-6666-6666-666666666666`) | Traffic light not working; signal stuck on red; pedestrian crossing signal failure. |
| `drainage` | Drainage | Drainage (`d7777777-7777-7777-7777-777777777777`) | Blocked storm drain; rainwater pooling; flooded street after rain; clogged drainage channel. |
| `public_facilities` | Public facilities | Public Facilities (`d8888888-8888-8888-8888-888888888888`) | Broken public bench; damaged playground equipment; unsafe park fixture; damaged public amenity. |
| `power_outage` | Power outage | Power Distribution (municipality-specific) | Electrical outages, downed distribution lines, dark streets caused by grid failure. |
| `PENDING_CLASSIFICATION` | Pending classification | No department mapping until reviewed or classified | Newly submitted ticket before AI classification; ambiguous report needing staff review. |

## Translation Guidance

Only display labels should be translated. Internal keys must remain unchanged in API payloads,
database records, mock tickets, AI regression fixtures, and dashboard filter values.

Examples:

| Internal key | English label | Arabic label example | French label example |
| --- | --- | --- | --- |
| `road_damage` | Road damage | ضرر في الطريق | Dégâts routiers |
| `waste` | Waste | نفايات | Déchets |
| `street_lighting` | Street lighting | إنارة الشوارع | Éclairage public |
| `water_leak` | Water leak | تسرب مياه | Fuite d'eau |
| `noise` | Noise | ضجيج | Bruit |
| `sidewalk_damage` | Sidewalk damage | ضرر في الرصيف | Trottoir endommagé |
| `traffic_signal` | Traffic signal | إشارة سير | Feu de circulation |
| `drainage` | Drainage | تصريف مياه | Drainage |
| `public_facilities` | Public facilities | مرافق عامة | Équipements publics |
| `PENDING_CLASSIFICATION` | Pending classification | بانتظار التصنيف | Classification en attente |

## Ambiguous Examples

Use the primary issue and municipal routing need to choose a category:

| Input pattern | Expected category | Reason |
| --- | --- | --- |
| Pothole fills with rainwater, but asphalt is cracked around it. | `road_damage` | Road surface repair is the primary action. |
| Street floods only after heavy rain near a blocked grate. | `drainage` | Stormwater drainage is the primary action. |
| Water flows continuously from under the sidewalk when it has not rained. | `water_leak` | Likely public water infrastructure leak. |
| Garbage bags make noise when collection happens early, but main complaint is trash and odor. | `waste` | Waste issue is primary; noise is secondary. |
| Broken sidewalk tile beside a pothole, with pedestrian trip hazard emphasized. | `sidewalk_damage` | Pedestrian safety issue is primary. |
| Broken traffic light causes cars to honk at night. | `traffic_signal` | Signal repair is primary; noise is secondary. |

## Unsupported And Out-Of-Scope Examples

Unsupported or non-municipal reports should not be forced into a concrete category. Use
`PENDING_CLASSIFICATION` when the classifier cannot confidently map a report to the supported MVP
taxonomy and staff review is needed.

Examples:

| Input pattern | Expected category | Notes |
| --- | --- | --- |
| Asking about concert tickets, event schedules, or private venue information. | `PENDING_CLASSIFICATION` | Not an infrastructure complaint. |
| Reporting a private apartment plumbing issue with no public infrastructure impact. | `PENDING_CLASSIFICATION` | Private property issue unless public leak is described. |
| Medical, police, or emergency requests. | `PENDING_CLASSIFICATION` | Out of MVP scope; should be routed outside this classifier. |
| Complaint only says "there is a problem near my house" with no actionable detail. | `PENDING_CLASSIFICATION` | Too ambiguous for category assignment. |
| Political feedback or general dissatisfaction with municipality service. | `PENDING_CLASSIFICATION` | Not a concrete maintenance ticket. |

## Department Mapping

Category→department routing rules, per-department responsibilities, and the #31 / #33 / RAG scope
split are documented in [department-mapping.md](./department-mapping.md).

## Source Of Truth

The current codebase already stores this taxonomy in:

- `backend/scripts/db/seeds/categories.json` (includes `departmentId` for concrete categories)
- `backend/scripts/db/seeds/departments.json`
- `backend/app/services/routing/department_map.py` (runtime category→department map)
- `docs/department-mapping.md` (department responsibilities and routing rules)
- `admin/src/utils/labels.ts`
- `mock_tickets.json`

When adding or removing categories, update this document and all source files above in the same PR.
