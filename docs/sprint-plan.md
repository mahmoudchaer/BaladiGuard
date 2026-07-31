# BaladiGuard Sprint Plan

Prepared by: Scrum Master  
Project: BaladiGuard  
Team size: 5 student developers  
Sprint length: 1 week each  
Planning target: about 20-30 story points per sprint

## Purpose

This document summarizes our sprint plan for BaladiGuard. The goal is to give the team a clear view of what we are building each week, how the work is balanced, and how we should think about the workload.

The plan is based on total story points, not the number of issues. Some sprints may have fewer issues but still carry enough work if those issues are larger. Likewise, some sprints may have more issues if the tasks are smaller and easier to split.

For our team, we are treating story points as a rough measure of effort, uncertainty, and complexity:

- 1 SP: very small task
- 2 SP: small task
- 3 SP: medium task
- 5 SP: larger or more uncertain task

## Sprint Overview

| Sprint | Focus | Issues | Total SP |
|---|---|---:|---:|
| Sprint 1 | Project foundation, architecture, citizen form base | 10 | 29 |
| Sprint 2 | Core report storage, dashboard base, CI and database setup | 13 | 30 |
| Sprint 3 | AI classification, AI cleanup, testing foundations | 10 | 30 |
| Sprint 4 | Map, location validation, duplicate detection | 6 | 24 |
| Sprint 5 | Urgency scoring and department routing | 7 | 21 |
| Sprint 6 | Citizen tracking, notifications, staff auth and authorization | 7 | 23 |
| Sprint 7 | Staff assistant features, analytics, demo sample data | 7 | 22 |
| Sprint 8 | Full testing, polish, deployment, observability | 8 | 25 |
| Sprint 9 | Final demo, documentation, handoff, backup smoke test | 7 | 22 |

## Sprint Goals

### Sprint 1: Foundation and MVP Shape

The first sprint sets the project direction. We define the system structure, prepare the first repo documentation, design the database, agree on the API contract, and start the citizen report form.

By the end of this sprint, the team should understand the product flow and have enough technical direction to work in parallel.

### Sprint 2: Core Ticket Flow

This sprint makes the basic ticket system real. Reports should be saved, ticket IDs should work, uploaded images should be handled, and the staff dashboard should start showing actual ticket data.

We also add early engineering setup such as CI and database migration/seed setup, so quality is not left until the end.

### Sprint 3: AI and Testing Foundations

This sprint adds the first AI value of the platform: classifying complaints and cleaning raw citizen descriptions into clearer municipal descriptions.

We also set up backend, frontend, API, and AI regression testing. This keeps the AI and ticket lifecycle safer as the project grows.

### Sprint 4: Location and Duplicate Intelligence

This sprint focuses on map and location behavior. Tickets should store coordinates correctly, the dashboard should show ticket locations, and the system should start detecting nearby duplicate reports.

This is important because municipalities need to understand where problems are happening, not only what the problem is.

### Sprint 5: Urgency and Department Routing

This sprint improves decision support. The system should score urgency, explain why a ticket is urgent, suggest the correct department, and let staff manually adjust the assignment if needed.

Department routing is split across issues: **#31** defines authoritative category→department rules and department docs (see `docs/department-mapping.md`); **#33** applies that map after AI classification and saves a suggested department on the ticket; **#34** allows staff override. RAG / vector-DB department matching is deferred.

The goal is to make the platform useful for prioritization, not just reporting.

### Sprint 6: Citizen Tracking, Notifications, and Security

Sprint 6 uses the phone-first citizen identity and privacy contract in issue #193 and
`docs/MVP_API_CONTRACT.md`. Public users may browse citizen-safe map/report data without an account,
but every new contribution requires an active authenticated citizen with a verified canonical phone
and valid full name. Citizen login is passwordless OTP. Email is optional notification data only;
citizens have no passwords or email recovery. Public attribution is anonymous by default and is
shown dynamically only when the citizen opts in. Staff authentication remains separate.

By the end of this sprint, citizens should be able to check ticket progress, and staff-only actions should be protected.

#### Required issue alignment after #193

The following wording is the implementation interpretation for the existing issue bodies. The issue
bodies should be updated with these replacements before work begins; if they are not yet edited,
this section and the API/database contracts take precedence over conflicting older text.

| Issue | Replace conflicting wording with this exact requirement |
|---|---|
| #168 | “Phone is the canonical citizen identity. Citizens use passwordless phone OTP and opaque server-side sessions; citizen and staff identities/credentials are separate. Public browsing and tracking remain unauthenticated, while contributions require an active citizen with a verified canonical phone and valid full name. Ticket ownership uses stable `userId`; contact is an immutable submission-time snapshot; public-name visibility is dynamic and anonymous by default.” |
| #169 | “Persist citizen `userId`, canonical phone, `phoneVerifiedAt`, full name, nullable non-unique email, notification preferences, `publicNameVisible`, active state, and timestamps. Enforce phone uniqueness with a transactional phone-claim record; a GSI is not the uniqueness authority. Do not persist citizen password/reset metadata and do not create an email identity index.” |
| #170 | “Implement phone OTP request/verify, opaque 30-day server-side citizen sessions, logout/revocation, current-user, and safe expiry/error behavior. Replace password signup/login and invalid-password tests with OTP challenge, attempt-limit, single-use, expiry, generic response, session audience, and revocation tests.” |
| #171 | “Build phone OTP request/verification and first-time full-name collection. Persist the citizen session securely, return to the intended screen, and handle invalid/expired codes, resend, throttling, offline state, session restore, and logout. Do not add citizen password or email-login/recovery screens.” |
| #172 | “Profile displays verified phone, full name, optional email, notification preferences, and public-name visibility. Phone changes require a newly verified OTP and atomic claim transfer. Email is non-unique and cannot log in or recover the account; public visibility changes apply dynamically to existing reports.” |
| #173 | “`POST /v1/tickets` requires a contribution-ready citizen, derives immutable `ownerUserId` from the session, and snapshots profile contact at submission. Reject guests and revoked inactive-account sessions with `401`, and active but incomplete citizens with `403`; keep public browse and tracking routes unauthenticated. Never accept a client-supplied owner ID.” |
| #174 | “Citizen history is protected and derives stable `userId` from the verified session. It returns only citizen-safe fields for that owner. Public list/detail and possession-based tracking remain separate public contracts and expose no account/contact identifiers.” |
| #178 | “Limit this issue to staff password recovery and staff UI entry points. Citizens are passwordless; email cannot recover a phone identity. Remove citizen forgot-password/reset endpoints, forms, dependencies, and tests unless a separate exceptional-recovery design is approved.” |

### Sprint 7: Staff Assistant and Analytics

This sprint adds higher-level dashboard support. The staff assistant should summarize important tickets and repeated area problems, while analytics cards and charts help staff understand the overall situation.

We also prepare demo data so we can test the platform with realistic examples.

### Sprint 8: Testing, Polish, and Deployment

Sprint 8 is the main stabilization sprint. We test the full flow, multilingual cases, duplicate detection, urgency scoring, UI, backend APIs, deployment, logging, and environment setup.

The goal is that the MVP should already be working by the end of Sprint 8.

### Sprint 9: Final Demo and Handoff

Sprint 9 is intentionally lighter. It is reserved for final demo preparation, final presentation, backup demo video, README updates, final handoff checklist, and an end-to-end smoke test.

We should avoid adding major new features in Sprint 9 unless absolutely necessary.

## How We Should Use This Plan

The sprint plan is a guide, not a rigid contract. During each sprint planning meeting, we should review the current sprint issues, confirm priorities, and divide the work between team members.

We are not assigning work per student inside this document. The team will divide the tickets at the start of each sprint.

If a sprint becomes too heavy, we should move lower-priority work to a later sprint. If a sprint becomes too light, we should pull in the next most useful ticket, not just add random work.

## Definition of Done

For a ticket to be considered done, it should meet these expectations:

- Acceptance criteria are completed.
- Code is committed and pushed.
- The feature or fix was tested locally.
- Related UI/API behavior is checked if applicable.
- The ticket status is updated in GitHub.
- Any important notes, limitations, or setup steps are documented.
- Unit tests are added or updated for the implemented logic, where applicable. If unit testing is not practical, the reason should be documented.

## Final Note

The most important milestone is to have the working MVP ready by the end of Sprint 8, then use Sprint 9 for final polish, demo preparation, and handoff.
