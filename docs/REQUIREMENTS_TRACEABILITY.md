# Requirement traceability

Every requirement, scenario and edge case in *Napho Engineering Assignment: Reimbursement
Management System*, with the code that implements it and the tests or checks that cover it.
Backend tests are in `backend/tests/` (138, pytest). Frontend tests sit next to the code in
`frontend/src/**/*.test.*` (51, Vitest). "Manual" means checked in a real browser (see the README
demo script). There are no automated end-to-end UI tests; that gap is listed under
"If I had more time" in [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md#if-i-had-more-time).

## Deliverables and technical requirements

| # | Requirement | Where | Covered by |
|---|---|---|---|
| D1 | Working application and Git repository | `backend/`, `frontend/`, one commit per phase | Clean-clone run of the README; manual demo |
| D2 | README with setup instructions, assumptions and known limitations | [`README.md`](../README.md) | Clean-clone run followed it command by command |
| D3 | Brief explanation of the data model and key design decisions | [`DATA_MODEL.md`](DATA_MODEL.md), [`DESIGN_DECISIONS.md`](DESIGN_DECISIONS.md) | — |
| D4 | Relevant tests | `backend/tests/`, `frontend/src/**/*.test.*` | 138 + 51 passing |
| D5 | AI usage disclosed | README → *AI usage disclosure* | — |
| T1 | Backend in Python | FastAPI app in `backend/app/` | All backend tests |
| T2 | Frontend in React | Vite + React 19 in `frontend/src/` | Frontend tests; manual |
| T3 | Database is SQLite | `app/database.py` (WAL, foreign keys, busy timeout) | All backend tests run on SQLite |
| T4 | Clear separation of frontend, backend and database | SPA ↔ JSON API (`/api/*`) ↔ SQLAlchemy models; routers → services → models | Layering in `DESIGN_DECISIONS.md` |

## Expected outcome: create → submit → review → approve/reject → view outcome

| # | Step | Where | Covered by |
|---|---|---|---|
| F1 | Create claim | `POST /api/claims`, `services/claims.create_claim`; `ClaimFormPage` | `test_lifecycle::test_full_flow_to_paid`; manual |
| F2 | Submit | `POST /claims/{id}/submit`; `EmployeeActions`, "Save & submit" | `test_full_flow_to_paid`; manual |
| F3 | Review | `ReviewQueuePage` (`scope=pending`, oldest first), `ClaimDetailPage` | `test_queries::test_pending_queue_oldest_first_and_reviewed_scope`; manual |
| F4 | Approve / reject | `/approve`, `/reject`; `ApproveDialog`, `RejectDialog` | `test_full_flow_to_paid`, `test_reject_edit_resubmit_approve`; `ApproveDialog.test.jsx` |
| F5 | View outcome | Status, approved amount, reviewer, comment and timeline on `ClaimDetailPage`; lists show badges | `test_full_flow_to_paid` (reviewer, amounts, events); `ClaimsTable.test.jsx`; manual |

## User roles

| # | Requirement | Where | Covered by |
|---|---|---|---|
| E1 | Employee: create, edit and delete **draft** claims | `create_claim`, `update_claim`, `delete_claim` (soft); `rules.EDITABLE_STATUSES`, `DELETABLE_STATUSES` | `test_lifecycle::test_edit_records_old_and_new_values`, `test_delete_draft_is_soft_and_hidden`, `test_edge_cases::test_cannot_edit_or_delete_after_submit` |
| E2 | Employee: submit claims for approval | `submit_claim` | `test_full_flow_to_paid`, `test_edge_cases::test_receipt_required_to_submit_large_claim` |
| E3 | Employee: view current and past claims | `GET /api/claims` (own only), `MyClaimsPage` with status tabs, search and filters | `test_queries::test_employee_sees_only_own_claims`, `test_filter_by_status_and_category`, `test_summary_for_employee_and_approver` |
| E4 | Employee: correct and resubmit rejected claims | Edit allowed in `REJECTED`; submit from `REJECTED` = resubmit (`resubmission_count`, review cleared, history kept) | `test_lifecycle::test_reject_edit_resubmit_approve`, `test_edge_cases::test_resubmission_count_increments_each_round`, `test_resubmit_still_checks_policy` |
| A1 | Approver: view and review submitted claims | `scope=pending` queue; drafts invisible | `test_queries::test_approver_sees_everyone_except_drafts`, `test_edge_cases::test_approver_cannot_see_drafts` |
| A2 | Approver: approve or reject **with comments** | `ApproveIn.comment` (required for partial), `RejectIn.comment` (required, 3–500) | `test_edge_cases::test_reject_requires_a_comment`, `test_partial_approval_requires_a_comment`; `validation.test.js` |
| A3 | Approver: view previously reviewed claims | `scope=reviewed` + `ReviewedClaimsPage` (filters, employee filter, sort, CSV) | `test_pending_queue_oldest_first_and_reviewed_scope`, `test_csv_export_for_approver`, `test_csv_respects_filters` |
| A4 | Approver: mark approved claims as paid | `/pay` (`APPROVED` → `PAID`), `PayDialog` | `test_full_flow_to_paid`, `test_edge_cases::test_cannot_pay_before_approval`, `test_cannot_pay_twice` |
| R1 | Roles are enforced (not just hidden in the UI) | `_require_owner`, `_require_reviewer`, `require_approver`; `allowed_actions` drives the buttons | `test_approver_cannot_create_claims`, `test_employee_cannot_review_or_pay`, `test_employee_cannot_see_or_touch_other_employees_claims`, `test_approver_cannot_edit_claims`, `test_approver_cannot_review_own_claim`, `test_rules::test_allowed_actions_*` |
| R2 | "A mocked login/user setup is sufficient" | Went beyond it: real email + password auth with JWT access tokens and rotating refresh cookies | `test_auth.py` (8), `test_auth_tokens.py` (38); `client.test.js`; manual auth passes |
| R3 | No real payment integration | Payment is a record (`paid_at`, `paid_by_id`, `payment_reference`) | `test_full_flow_to_paid` |

## Claim lifecycle and history

| # | Requirement | Where | Covered by |
|---|---|---|---|
| L1 | Draft → Submitted → Approved / Rejected → Paid | `rules.TRANSITIONS`; `_apply` | `test_full_flow_to_paid`, `test_reject_edit_resubmit_approve` |
| L2 | Maintain sufficient history to track changes and actions | Append-only `claim_events`, written in the same transaction (who, when, from/to, comment, field-level diffs); `Timeline` component | `test_full_flow_to_paid` (event sequence), `test_edit_records_old_and_new_values`, `test_partial_approval_8000_to_6500` (details), `test_reject_edit_resubmit_approve` (old review kept in events), `test_edit_with_no_changes_is_a_noop` |
| L3 | Decide fields, relationships, validations and business logic | `models.py`, `schemas.py`, `rules.py`; policy limits in `config.py` | `test_rules.py` (12), validation tests in `test_edge_cases.py` |

## Good to have: partial approval

| # | Requirement | Where | Covered by |
|---|---|---|---|
| P1 | Approve part of a claim (₹8,000 claimed, ₹6,500 approved) | `approved_amount` separate from `amount`; `is_partial`; event `partially_approved` with `{claimed, approved}` | `test_lifecycle::test_partial_approval_8000_to_6500` (the exact example) |
| P2 | Sensible guards | `0 < approved ≤ claimed`, 2 dp; comment required when reduced; equal to claimed = full approval | `test_approved_amount_cannot_exceed_claimed`, `test_approved_amount_must_be_positive_with_two_decimals`, `test_approved_amount_equal_to_claimed_counts_as_full_approval`, `test_partial_approval_requires_a_comment` |
| P3 | Visible in the UI | Live warning plus required comment in `ApproveDialog`; "Partial" badge and approved amount in lists and detail; paid amount = approved amount | `ApproveDialog.test.jsx`, `ClaimsTable.test.jsx`; `test_summary_for_employee_and_approver` |

## Edge cases named in the brief

| # | Edge case | Handling | Covered by |
|---|---|---|---|
| X1 | **Invalid state changes** | Transition table + `409 INVALID_TRANSITION`; the conditional UPDATE re-checks the status in SQL | `test_cannot_review_pay_or_withdraw_a_draft`, `test_cannot_pay_before_approval`, `test_cannot_approve_twice_or_reject_after_approve`, `test_cannot_pay_twice`, `test_cannot_edit_or_delete_after_submit`, `test_cannot_edit_or_withdraw_after_approval`, `test_cannot_delete_a_rejected_claim` |
| X2 | **Duplicate requests**: the same action twice | State machine rejects the second; the UI disables buttons while busy | `test_double_submit_second_call_is_rejected`, `test_double_click_submit_only_one_wins` (threads) |
| X3 | **Duplicate requests**: the same expense claimed twice | Partial unique index on the fingerprint among live claims → `409 DUPLICATE_CLAIM` | `test_duplicate_expense_blocked_on_submit`, `test_drafts_may_be_duplicates_until_submitted`, `test_different_amount_or_date_is_not_a_duplicate`, `test_same_expense_by_different_employees_is_fine`, `test_rejected_claim_does_not_block_a_fresh_claim`, `test_duplicate_claims_submitted_at_once_only_one_wins`, `test_rules::test_fingerprint_*` |
| X4 | **Resubmissions** | Same claim, counter, review cleared but kept in history, policy re-checked | `test_reject_edit_resubmit_approve`, `test_resubmission_count_increments_each_round`, `test_resubmit_still_checks_policy`, `test_withdraw_returns_to_draft_and_can_be_resubmitted` |
| X5 | **Incorrect amounts** | `> 0`, ≤ 2 dp, ≤ ₹1,00,000, no NaN/Infinity; `Decimal` everywhere; approved ≤ claimed | `test_invalid_amounts_rejected` (0, -5, abc, 12.345, empty, NaN, Infinity), `test_amount_over_cap_rejected`, `test_amount_at_cap_allowed`, `test_amounts_keep_two_decimals`, `test_summary_has_no_float_drift`; `validation.test.js` |
| X6 | **Missing information** | Per-field 422 errors (all reported at once); receipt required to submit above ₹1,000; reject reason required | `test_missing_required_fields_reported_per_field`, `test_title_too_short_and_unknown_category`, `test_whitespace_only_title_rejected`, `test_future_and_stale_dates_rejected`, `test_receipt_required_to_submit_large_claim`, `test_small_claim_needs_no_receipt`, `test_validation_failure_changes_nothing`, `test_rules::test_all_errors_reported_together` |
| X7 | **Concurrent actions** | Conditional UPDATE (`version` + status in the WHERE clause) → `409 CONCURRENT_UPDATE`; `expected_version` → `409 STALE_VERSION`; UI reloads and explains | `test_two_approvers_approving_at_once_only_one_wins`, `test_withdraw_racing_with_approve_has_one_winner`, `test_stale_version_is_rejected`, `test_approver_with_stale_page_cannot_approve_a_changed_claim`, `test_stale_edit_is_rejected`, `test_version_increases_with_every_change`; manual two-tab conflict (demo step 3) |

## Additional edge cases handled (not named in the brief)

| Case | Covered by |
|---|---|
| Expense date in the future or older than 90 days (re-checked on submit) | `test_future_and_stale_dates_rejected`, `test_rules::test_expense_age_boundary` |
| Approver cannot review their own claim | `test_approver_cannot_review_own_claim`, `test_rules::test_approver_cannot_act_on_own_claim` |
| Hidden claims return 404 rather than 403 (no existence leak) | `test_employee_cannot_see_or_touch_other_employees_claims`, `test_approver_cannot_see_drafts` |
| Search treats `%` and `_` literally | `test_search_treats_wildcards_literally` |
| CSV formula injection (`=`, `+`, `-`, `@`) | `test_csv_neutralises_formula_injection` |
| Invalid filter values → 422, not 500 | `test_invalid_filter_values_return_422` |
| Auth: enumeration-safe login, timing, tampered / expired / `alg: none` / wrong-algorithm tokens, refresh rotation and reuse, logout, CSRF header, throttle, password rules, old DB schema | `test_auth_tokens.py` (38 tests) |

## Gaps found and how they were resolved

| Gap | Resolution |
|---|---|
| The public `GET /api/auth/users` let anyone enumerate users | Removed; replaced by approver-only `GET /api/users` (`test_user_list_is_approver_only`, `test_public_user_list_is_gone`) |
| No UI-level automated tests for the full flow | Documented as a limitation; covered by unit and component tests plus the manual demo script |
| `backend/venv/` (about 2,400 files) and duplicate "Phase 2" commits were in history | History rewritten: virtualenv removed from every commit, Phase 2 squashed into one commit |
| `uvloop` in `requirements.txt` can't install on Windows | Marked `sys_platform != "win32"` |
| Unused `axios`, `lucide-react` and `ComingSoonPage.jsx` | Removed |
