# Municipality provisioning and ticket ownership routing (issue #322)

BaladiGuard is no longer a single-pilot Beirut assumption. Developer operators
provision municipality responsibility profiles; AI routing then assigns tickets
by **geography + service domain**. Name/category text alone never creates an
owner.

## Roles

| Role | After #322 |
| --- | --- |
| `developer_operator` | Platform only. Creates municipalities and the **first** administrator. May override ticket ownership via `/v1/ops/tickets/{id}/municipality/override`. Still not a day-to-day ticket workspace user. |
| `administrator` | Municipality-scoped. Requires `municipalityId`. Manages staff **inside that municipality only**. Cannot create `developer_operator` or other `administrator` accounts. |
| `municipal_staff` | Unchanged shape: one municipality plus departments. Sees assigned tickets in those departments, plus the shared unassigned queue. |

Demo `admin` is scoped to Beirut Municipality
(`bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb`).

## Routing

Routing runs inside `process_ticket_ai` after classification.

1. Eligible municipalities must be **active**, cover the point (bbox, optional
   polygon), and include the category's service domain.
2. Exactly one eligible municipality → auto-assign with confidence `1.0`.
3. Zero or many eligible → **unassigned** shared queue.
4. Optional Bedrock tool-call (`MUNICIPALITY_ROUTING_USE_MODEL=true`) may break
   ties only from the allowlist. Default is **off** (CI-safe).
5. Fail closed: placeholder location, missing coordinates, inactive profile, or
   provider failure → unassigned. Never invent a municipality id.
6. AI completion is conditional on the municipality/routing version it read. A
   staff claim during processing is preserved; classification still saves.
7. Staff category review reruns routing and selects that municipality's
   department, so a new category can move ownership when the mandate changes.

Citizen location validation accepts any point covered by an **active**
municipality profile (Beirut and Tripoli in the seed set). It no longer treats
one Beirut bounding box as the only service area.

Authenticity and content-safety stay independent. Routing confidence is not
authorization.

## Claim / reject / override

- `POST /v1/tickets/{id}/municipality/claim` — atomic (`municipalityId` must
  still be absent). Competing claims return `409`.
- `POST /v1/tickets/{id}/municipality/reject` — requires a reason; history is
  kept; ticket returns to the unassigned queue.
- `POST /v1/ops/tickets/{id}/municipality/override` — developer operators only.

Unassigned staff GET responses omit citizen contact. Assigned tickets in another
municipality return `404`.

## Operator UI

`/ops/municipalities` lists profiles, creates/edits them, provisions the first
administrator, previews routing, and overrides a ticket id.

## Config

| Variable | Default | Notes |
| --- | --- | --- |
| `MUNICIPALITY_ROUTING_ENABLED` | `true` | Disable only for emergency rollback |
| `MUNICIPALITY_ROUTING_USE_MODEL` | `false` | Keep false in CI |
| `MUNICIPALITY_ROUTING_MODEL_ID` | `BEDROCK_MODEL_ID` | Structured municipality tool |
| `MUNICIPALITY_ROUTING_HIGH_CONFIDENCE` | `0.85` | Model-path assign threshold |
