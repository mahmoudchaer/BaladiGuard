# Verified citizen rewards and contribution leaderboard

Issue #323. Recognition for verified civic value — not raw submission count, money, or government benefits.

## Research notes

Municipal reporting programs that count every submit invite farming, duplicate spam, and fabricated reports. BaladiGuard therefore:

- awards nothing confirmed at `SUBMITTED`
- treats automated content-safety as a **pending** signal only
- confirms points only after municipal staff workflow (assignment, work started, resolution) or a staff merge as supporting evidence
- records every grant and reversal in an append-only ledger with a stable event key

## Scoring rules (`rewards-v1`)

| Reason | Points | Credit | When |
| --- | ---: | --- | --- |
| `SAFETY_CLEARED` | 3 | pending | Enrolled ticket passes automated review |
| `MUNICIPALITY_ACCEPTED` | 10 | confirmed | Status is `ASSIGNED` or later on a verified path |
| `IN_PROGRESS` | 8 | confirmed | Status is `IN_PROGRESS` or later |
| `RESOLVED` | 20 | confirmed | `RESOLVED`, or `CLOSED` with `resolvedAt` |
| `SUPPORTING_EVIDENCE` | 4 | confirmed | Ticket is merged as a non-canonical duplicate |
| `OPS_CORRECTION` | ±1–200 | confirmed | Audited developer-operator correction only |

Submitting, auto-routing a municipality, or changing a category does not award confirmed points.

Recognition levels: Neighbor (0), Helper (25), Steward (50), Guardian (100), Civic Champion (200).

## Ledger

Each row has `eventId`, idempotent `eventKey`, ticket/source reference, `ruleVersion`, `delta`, `reasonCode`, `pending|confirmed`, timestamp, optional `reversesEventId`, and actor metadata.

Totals are projections rebuilt from the ledger. Retries and repeated status writes reuse the same `eventKey`.

## Reversals

| Trigger | Effect |
| --- | --- |
| `CLOSED` without `resolvedAt` (reject / cancel) | Reverse remaining awards for that ticket |
| Reopen from resolved to in progress | Reverse `RESOLVED` only |
| Merge as duplicate | Reverse the full path; award supporting credit |
| Automated safety reject / fail | Reverse pending review credit only — AI cannot permanently take confirmed staff-verified points |
| Account deletion / opt-out | Hide public attribution; keep justified ledger totals |

## Identity and privacy

- Public board is **opt-in**, default private (`leaderboardOptIn=false`)
- Requires a safe public display name and `publicNameVisible`
- Public rows expose only display name, points, rank, and level
- Duplicate names appear twice; user IDs are never appended
- Phone, email, address, private location, internal user ID, and ticket details never appear on the public board
- Citizens who do not opt in still see private progress, badges, and private rank
- Deletion / anonymization removes public attribution

Municipality / precise geo segmentation is intentionally omitted so rank cannot leak home area.

## Threat model

| Abuse | Control |
| --- | --- |
| Submit farming | No confirmed points at submit |
| Status-transition farming | Idempotent event keys; reopen reverses resolution |
| Near-duplicate farming | Merge converts extras to supporting credit only |
| Fabricated reports | Staff rejection reverses; ops correction is audited |
| Rapid confirmed awards | Cap of 8 confirmed awards / 24h (silent skip; no citizen-visible abuse flag) |
| Staff vanity grants | Municipality staff cannot grant points; only `POST /v1/ops/rewards/adjustments` |
| Identifier leakage | Public API never returns `userId`, contact, or ticket ids |
| Ranking employees | Staff accounts are not citizens and cannot appear |

## Operational correction

1. Confirm the citizen `userId` from a private support channel — never from the public board.
2. `GET /v1/ops/rewards/citizens/{userId}` and review the ledger.
3. `POST /v1/ops/rewards/adjustments` with a non-zero `delta` (−200…200) and a written reason (≥12 characters).
4. The correction is a new ledger row (`OPS_CORRECTION`) with operator actor metadata. Do not rewrite history.

Municipality staff keep normal ticket verification only. They do not have this route.

## Limitations

- Pending credit is informational and never ranks.
- Automated authenticity / moderation scores are not used as point values.
- Monthly windows are UTC calendar months.
- Recognition has no cash, wallet, or benefit value.
- Public rank is computed only among opted-in profiles with confirmed points.

## API

- `GET /v1/rewards/rules`
- `GET /v1/rewards/leaderboard?period=all-time|monthly`
- `GET /v1/citizen/me/rewards`
- `PATCH /v1/citizen/me/rewards-settings` (`leaderboardOptIn`)
- `GET /v1/ops/rewards/citizens/{userId}`
- `POST /v1/ops/rewards/adjustments`
