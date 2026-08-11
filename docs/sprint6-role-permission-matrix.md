# Sprint 6 role-permission test matrix (issue #182)

Traceability matrix for Sprint 6 authorization coverage. This document **verifies**
what is allowed or rejected for each role; implementation fixes belong in the
related feature tickets (#168, #173, #174, #176, #178, #181, …), not here.

Contract sources: `docs/MVP_API_CONTRACT.md` (Sprint 6 identity + 401/403 rules),
`docs/privacy-lifecycle.md`, and `docs/sprint-plan.md` § Sprint 6.

## Roles

| Role | Principal | Notes |
| --- | --- | --- |
| **Guest / public** | No Bearer token | Unauthenticated browse/track only |
| **Citizen (incomplete)** | Active OTP session, no valid full name | May manage profile; cannot contribute |
| **Citizen (contribution-ready)** | Active session + verified phone + valid full name | Ticket submission + report photo uploads |
| **Municipal staff** | Staff token `role=municipal_staff` | Scoped to municipality + department list |
| **Administrator** | Staff token `role=administrator` | Global ticket scope (`departmentIds: null`) |

## HTTP status contract (401 vs 403 vs 404)

| Situation | Expected | Code |
| --- | --- | --- |
| Missing / invalid / expired / revoked / wrong-audience credentials | **401** | `UNAUTHORIZED` (+ `WWW-Authenticate: Bearer` on protected routes) |
| Valid principal without route permission (e.g. staff lacking department scope for assign) | **403** | `FORBIDDEN` (or contribution-specific `CONTRIBUTION_PROFILE_REQUIRED` / `ACCOUNT_INACTIVE`) |
| Ticket missing **or** ticket out of staff municipality/department scope | **404** | `TICKET_NOT_FOUND` (no existence leak) |

## How to re-run the automated matrix suite

From `backend/` (with project dependencies installed):

```bash
python -m pytest \
  tests/test_staff_authorization.py \
  tests/test_staff_accounts.py \
  tests/test_staff_password_reset.py \
  tests/test_citizen_otp_auth.py \
  tests/test_citizen_account.py \
  tests/test_citizen_privacy_lifecycle.py \
  tests/test_citizen_tracking_response.py \
  tests/test_public_ticket_browsing.py \
  tests/test_submit_ticket.py \
  -q
```

**Last run (issue #182):** all listed matrix suites **pass** locally (**144 passed**, 2026-08-06). See run notes at the bottom.

---

## Matrix

Legend for **Evidence**:

- `Auto` — automated pytest (module::test)
- `Manual` — manual/demo check with documented reason
- `Gap` — expected by contract but no dedicated automated or manual pass yet (defect note or follow-up issue; **not** fixed in #182)

### 1. Public browse & tracking

| ID | Area | Actor | Action | Expected | Evidence |
| --- | --- | --- | --- | --- | --- |
| P1 | Tracking | Guest | `GET /v1/tickets/track/{code}` for valid submission | 200, citizen-safe payload (no contact/ownerUserId/ticketId) | Auto: `test_staff_authorization::test_citizen_tracking_lookup_remains_public`; `test_citizen_tracking_response::test_tracking_code_lookup_returns_citizen_safe_ticket_response`; `test_submit_ticket::test_public_track_hides_owner_and_contact` |
| P2 | Tracking | Guest | Invalid code format | 400 `VALIDATION_ERROR` | Auto: `test_citizen_tracking_response::test_tracking_code_lookup_rejects_invalid_format` |
| P3 | Tracking | Guest | Unknown valid-format code | 404 `TICKET_NOT_FOUND` | Auto: `test_citizen_tracking_response::test_tracking_code_lookup_returns_404_for_unknown_code` |
| P4 | Public feed | Guest | `GET /v1/tickets/public` | 200 privacy-safe feed | Auto: `test_public_ticket_browsing::test_public_ticket_feed_is_guest_readable_and_privacy_safe` |
| P5 | Public detail | Guest | `GET /v1/tickets/public/{ticketNumber}` | 200 citizen-safe; unreviewed excluded | Auto: `test_public_ticket_browsing::test_public_ticket_detail_uses_ticket_number_and_name_opt_in`; `…_excludes_unreviewed_and_unapproved_reports` |

### 2. Citizen profile & session

| ID | Area | Actor | Action | Expected | Evidence |
| --- | --- | --- | --- | --- | --- |
| C1 | Profile | Guest | `GET /v1/citizen/me` | 401 | Auto: `test_citizen_account::test_unauthenticated_profile_returns_401` |
| C2 | Profile | Contribution-ready citizen | `GET /v1/citizen/me` | 200 with contributionReady true | Auto: `test_citizen_account::test_get_profile_returns_citizen_safe_fields_and_contribution_ready` |
| C3 | Profile | Incomplete citizen | `GET /v1/citizen/me` | 200, not contribution ready | Auto: `test_citizen_account::test_incomplete_profile_is_not_contribution_ready` |
| C4 | Profile | Staff token on citizen route | `GET /v1/citizen/me` | 401 wrong audience | Auto: `test_citizen_account::test_staff_token_cannot_access_citizen_profile`; `test_citizen_otp_auth::test_staff_token_cannot_authenticate_citizen_routes` |
| C5 | Profile update | Authenticated citizen | Partial profile update | 200 when valid | Auto: `test_citizen_account::test_partial_profile_update` |
| C6 | OTP auth | Guest | Login/signup OTP request+verify | 202/200 generic responses | Auto: `test_citizen_otp_auth::test_otp_request_returns_generic_202_without_code`; `…_verify_creates_new_citizen_and_session` |
| C7 | OTP auth | Inactive account | Verify OTP | 403 `ACCOUNT_INACTIVE`, no session | Auto: `test_citizen_otp_auth::test_otp_verify_inactive_account_returns_403_without_session` |
| C8 | Session | Citizen | Logout then reuse token | 401 on replay | Auto: `test_citizen_otp_auth::test_logout_revokes_presented_session_only`; `…_logout_replay_returns_401` |
| C9 | Session | Citizen | Expired session | 401 | Auto: `test_citizen_otp_auth::test_expired_session_returns_401` |
| C10 | Phone change | Guest | `CHANGE_PHONE` OTP request | 401 | Auto: `test_citizen_otp_auth::test_guest_change_phone_request_returns_401` |
| C11 | Cross-user | Citizen A | Export/delete/history for self only | Other users’ data not exposed | Auto: `test_citizen_privacy_lifecycle::test_cross_user_cannot_export_another_account`; `…_ticket_history_returns_owned_citizen_safe_tickets_only` |

### 3. Citizen ticket history & privacy exports

| ID | Area | Actor | Action | Expected | Evidence |
| --- | --- | --- | --- | --- | --- |
| H1 | History | Guest | Owned ticket history | 401 | Auto: `test_citizen_privacy_lifecycle::test_ticket_history_requires_citizen_auth` |
| H2 | History | Staff token | Citizen history route | 401 | Auto: `test_citizen_privacy_lifecycle::test_staff_token_cannot_read_citizen_ticket_history` |
| H3 | History | Contribution-ready | Own history list | 200 owned tickets only, citizen-safe fields | Auto: `test_citizen_privacy_lifecycle::test_ticket_history_returns_owned_citizen_safe_tickets_only` |
| H4 | History | Revoked session | History after logout/revoke | 401 | Auto: `test_citizen_privacy_lifecycle::test_revoked_session_cannot_read_ticket_history` |
| H5 | History | Expired session | History with expired session | 401 | Auto: `test_citizen_privacy_lifecycle::test_expired_session_cannot_read_ticket_history` |
| H6 | Export / delete | Guest | Privacy export/delete | 401 | Auto: `test_citizen_privacy_lifecycle::test_export_requires_citizen_auth`; `…_delete_requires_auth` |
| H7 | Export / delete | Staff token | Export/delete | 401 | Auto: `test_citizen_privacy_lifecycle::test_staff_token_cannot_export_or_delete` |
| H8 | Export / delete | Citizen | Delete account | Anonymize + revoke sessions; re-login 401 | Auto: `test_citizen_privacy_lifecycle::test_delete_anonymizes_pii_and_revokes_sessions` |

### 4. Report submission & photo upload

| ID | Area | Actor | Action | Expected | Evidence |
| --- | --- | --- | --- | --- | --- |
| S1 | Submit | Guest | `POST /v1/tickets` | 401 | Auto: `test_submit_ticket::test_guest_submit_requires_authentication`; `test_staff_authorization::test_citizen_submit_requires_contribution_ready_auth` |
| S2 | Submit | Incomplete citizen | `POST /v1/tickets` | 403 profile required | Auto: `test_submit_ticket::test_incomplete_citizen_submit_requires_contribution_profile` |
| S3 | Submit | Inactive / revoked citizen | Submit | 401 | Auto: `test_submit_ticket::test_inactive_citizen_session_rejected_on_submit` |
| S4 | Submit | Contribution-ready | Submit valid ticket | 201; owner derived server-side | Auto: `test_submit_ticket::test_submit_ticket_success`; `…_rejects_client_owner_user_id` |
| S5 | Submit | Contribution-ready | Client-supplied contact | Rejected / ignored per contract | Auto: `test_submit_ticket::test_submit_ticket_rejects_client_contact` |
| S6 | Upload | Guest / incomplete | `POST /v1/uploads/report-photo` | Contract: 401 guest / 403 incomplete | **Auto (#53):** guest `401` / incomplete `403` in `tests/test_upload_report_photo.py`; contribution-ready success path + upload-then-submit in `test_report_submission_flow.py`. Route uses `ContributionReadyCitizenDep`. |
| S7 | Upload | Authenticated flow | Upload then submit | 200 upload + 201 submit when S3 configured | Auto: `test_report_submission_flow::test_upload_then_submit_report_flow` (upload contribution-ready gated) |

### 5. Staff authentication & session hygiene

| ID | Area | Actor | Action | Expected | Evidence |
| --- | --- | --- | --- | --- | --- |
| A1 | Login | Guest | Valid staff credentials | 200 Bearer + role claims | Auto: `test_staff_authorization::test_staff_login_returns_bearer_token`; `test_staff_accounts::test_staff_login_returns_role_aware_claims` |
| A2 | Login | Guest | Bad password | 401 | Auto: `test_staff_authorization::test_staff_login_rejects_bad_password`; `test_staff_accounts::test_staff_login_rejects_invalid_credentials` |
| A3 | Login | Inactive staff | Login | 401 generic | Auto: `test_staff_accounts::test_inactive_staff_cannot_login` |
| A4 | Login | Admin | Login | role=administrator, null global scope | Auto: `test_staff_accounts::test_admin_login_returns_global_scope_sentinels` |
| A5 | Logout / revoke | Staff | Logout then staff route | 401 | Auto: `test_staff_accounts::test_logout_revokes_existing_token` |
| A6 | Expired session | Staff | Expired Bearer on `GET /v1/tickets` | 401 | Auto: `test_staff_authorization::test_expired_bearer_token_is_rejected`; `test_staff_accounts::test_expired_token_is_rejected` |
| A7 | Invalid token | Anyone | Garbage Bearer | 401 no ticket leak | Auto: `test_staff_authorization::test_invalid_bearer_token_is_rejected` |
| A8 | Audience | Citizen token | Staff routes | 401 | Auto: `test_staff_authorization::test_citizen_token_cannot_access_staff_routes` |
| A9 | Password reset | Guest | Staff reset flow | Generic request; confirms revoke other sessions | Auto: `test_staff_password_reset::*` especially `…_reset_revokes_existing_staff_sessions` |

### 6. Staff dashboard & ticket actions

| ID | Area | Actor | Action | Expected | Evidence |
| --- | --- | --- | --- | --- | --- |
| T1 | List | Guest | `GET /v1/tickets` | 401 | Auto: `test_staff_authorization::test_list_tickets_requires_staff_auth` |
| T2 | List | Staff / admin | `GET /v1/tickets` | 200 | Auto: `test_staff_authorization::test_list_tickets_succeeds_with_staff_token` |
| T3 | Detail | Guest | `GET /v1/tickets/{id}` | 401 (no existence leak) | Auto: `test_staff_authorization::test_get_ticket_requires_staff_auth_and_does_not_leak_existence` |
| T4 | Detail | Staff (in scope) | Get ticket | 200 | Auto: `test_staff_authorization::test_get_ticket_succeeds_with_staff_token` |
| T5 | Status | Guest | `PATCH …/status` | 401 | Auto: `test_staff_authorization::test_update_status_requires_staff_auth` |
| T6 | Status | Staff | Allow status change | 200 | Auto: `test_staff_authorization::test_update_status_succeeds_with_staff_token` |
| T7 | Category | Guest | `PATCH …/category` | 401 | Auto: `test_staff_authorization::test_category_review_requires_staff_auth` |
| T8 | Category | Staff | Review category | 200 | Auto: `test_staff_authorization::test_category_review_succeeds_with_staff_token` |
| T9 | Merge | Guest | `POST /v1/tickets/merge` | 401 | Auto: `test_staff_authorization::test_merge_requires_staff_auth` |
| T10 | Merge | Staff | Merge in-scope tickets | 200 | Auto: `test_staff_authorization::test_merge_succeeds_with_staff_token` |
| T11 | Actor spoof | Municipal staff | Spoofed `updatedBy` / `categoryReviewedBy` / `mergedBy` | Actor = verified principal | Auto: `test_staff_authorization::test_staff_mutation_actor_identity_uses_verified_principal`; `…_merge_actor_identity_uses_verified_principal` |
| T12 | Audit on staff detail | Staff | Ticket detail includes audit; public track does not | Staff-only auditHistory | Auto: `test_staff_audit_history::test_ticket_detail_exposes_audit_history_to_staff_only` |

### 7. Cross-department, cross-municipality, regular staff vs admin

| ID | Area | Actor | Action | Expected | Evidence |
| --- | --- | --- | --- | --- | --- |
| X1 | Cross-department list | Municipal staff | List tickets | Sees own municipality + own departments (and unassigned in mun.); not other dept | Auto: `test_staff_authorization::test_municipal_staff_list_is_scoped_by_municipality_and_departments` |
| X2 | Cross-municipality list | Municipal staff | List | Other municipality tickets excluded | Same as X1 |
| X3 | Cross-department detail | Municipal staff | Detail for other department ticket | 404 same shape as missing | Auto: `test_staff_authorization::test_municipal_staff_out_of_scope_detail_matches_missing_ticket` |
| X4 | Cross-department assign | Municipal staff | Assign unscoped dept | 403 `FORBIDDEN` | Auto: `test_staff_authorization::test_municipal_staff_cannot_assign_unscoped_department` |
| X5 | Category → dept | Municipal staff | Category that suggests unscoped dept | 403, no partial write | Auto: `test_staff_authorization::test_category_review_cannot_auto_assign_unscoped_department` |
| X6 | Admin dependency | Municipal staff | `require_admin` | 403 | Auto: `test_staff_authorization::test_admin_dependency_rejects_regular_staff` |
| X7 | Admin global ticket access | Administrator | Read ticket outside municipal demo scope | 200 (global) | **Manual / partial Auto:** default pytest `client` is admin and exercises ticket mutations successfully (`test_*_succeeds_with_staff_token`). No dedicated pairing test that **admin succeeds** where **municipal staff 404s** on the same out-of-scope id. Recommended manual: stamp waste-dept ticket as in X3; call detail as `staff` → 404; as `admin` → 200. Follow-up optional Auto under #176 if desired. |
| X8 | Admin-only account APIs | Administrator | HTTP staff-user admin CRUD | Admin-only when routes exist | **Gap / Manual:** `require_admin` is unit-tested; production admin HTTP staff-management routes are not mounted on this branch. Service-level admin helpers arrive with #181 (account audit). Manual once endpoints ship: municipal staff → 403, admin → 200. |

### 8. Administrator-only surface (non-ticket)

Issue #236 closes the previously documented X7/X8/M3 gaps: automated coverage
in `test_staff_authorization::test_out_of_scope_ticket_returns_404_to_municipal_staff_and_200_to_admin`
pairs the same ticket's municipal `404` with administrator `200`, while
`test_admin_staff_accounts_api` covers the administrator-only HTTP staff-account
surface (including safe responses, validation, duplicate handling, account audit,
deactivation/session effects, and authorization failures).

| ID | Area | Actor | Action | Expected | Evidence |
| --- | --- | --- | --- | --- | --- |
| M1 | Admin gate | Municipal staff vs admin | `require_admin` | 403 vs pass | Auto: `test_staff_authorization::test_admin_dependency_rejects_regular_staff` |
| M2 | Demo scope sentinels | Admin login response | `municipalityId`/`departmentIds` null | Claims accurate | Auto: `test_staff_accounts::test_admin_login_returns_global_scope_sentinels` |
| M3 | Staff account administration UI/API | Both | Create staff / change role | Admin only | **Manual** until dedicated admin REST is exposed (see X8). Reason: API surface incomplete; dependency unit tested only. |

---

## Gap / defect notes (not fixed in #182)

| Ref | Matrix IDs | Finding | Suggested home |
| --- | --- | --- | --- |
| G-UPLOAD | S6 | ~~Report photo upload not contribution-ready gated~~ **Fixed in #53** — `ContributionReadyCitizenDep` on `POST /v1/uploads/report-photo`. | — |
| G-ADMIN-PAIR | X7 | **Fixed in #236** — paired municipal `404` / administrator `200` test on the same out-of-scope ticket. | — |
| G-ADMIN-HTTP | X8, M3 | **Fixed in #236** — protected staff-account HTTP API backed by the existing memory/Dynamo stores. | — |

Failed matrix rows above are **documented gaps**, not merge blockers for #182 itself.

---

## Run notes (issue #182)

Command (from `backend/`):

```text
pytest tests/test_staff_authorization.py tests/test_staff_accounts.py \
  tests/test_staff_password_reset.py tests/test_citizen_otp_auth.py \
  tests/test_citizen_account.py tests/test_citizen_privacy_lifecycle.py \
  tests/test_citizen_tracking_response.py tests/test_public_ticket_browsing.py \
  tests/test_submit_ticket.py -q
```

**Result (2026-08-06):** `144 passed` (1 Starlette deprecation warning only).

When re-running before demo or PR, record the exit status here or in the PR body. If a previously green Auto row fails, open a focused defect against the owning feature ticket rather than expanding this matrix PR into a fix-all.
