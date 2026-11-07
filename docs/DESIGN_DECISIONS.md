# Key design decisions

## Layering

```
frontend (React SPA) ──HTTP/JSON──▶ routers/ ──▶ services/ ──▶ models/ ──▶ SQLite
                                      thin        rules.py: pure business rules (no DB)
                                                  claims.py: use-cases + transactions
                                                  queries.py: lists, summary, CSV
                                                  auth.py, throttle.py: sessions
```

Routers only parse input and shape output. All rules live in `services/`. The rules that need no
database (policy checks, the transition table, `allowed_actions`, the fingerprint) are in the pure
module `rules.py`, so they are easy to unit-test. The frontend never talks to SQLite, and the
backend never renders HTML. In dev, the Vite proxy forwards `/api/*` to FastAPI, so the browser only
ever sees one origin.

## Concurrency: conditional UPDATE plus `version`

Concurrent actions are a named edge case: two approvers deciding at once, a double-clicked
submit, or an employee withdrawing while an approver approves. A Python-side "load, check status,
save" sequence has a gap between the check and the save. Instead, every state change is **one**
statement:

```sql
UPDATE claims
   SET status = :new, …, version = version + 1, updated_at = now
 WHERE id = :id AND version = :seen_version AND status IN (:allowed_from) AND deleted_at IS NULL
```

plus the `claim_events` insert, in one transaction. If `rowcount != 1`, somebody else got there
first. We roll back and return `409 CONCURRENT_UPDATE`. SQLite serialises writers, so exactly one
of N racing requests wins. Tests cover this with real threads (`test_two_approvers_approving_at_once_only_one_wins`,
`test_double_click_submit_only_one_wins`, `test_withdraw_racing_with_approve_has_one_winner`).

On top of that, clients send `expected_version`, the version they *displayed*. That catches the
slower race where a user acts on a page that went stale minutes ago (`409 STALE_VERSION`). The UI
then reloads the claim and explains what happened, instead of silently applying an approval to an
amount the approver never saw.

SQLite runs in WAL mode with a busy timeout, so readers don't block the writer and short write
contention waits instead of failing.

## Duplicate rule

"Duplicate requests" can mean two things, and both are handled:

1. **The same request twice** (double click, retry): the state machine makes the second request a
   no-op failure. A claim that is already `SUBMITTED` cannot be submitted again (`409 INVALID_TRANSITION`).
2. **The same expense claimed twice**: two claims by the same employee with the same currency,
   category, amount, expense date and title (case- and whitespace-insensitive) cannot both be
   *live* (`SUBMITTED`, `APPROVED` or `PAID`). The rule is enforced by a partial unique index, so it
   holds under concurrent submits too (`test_duplicate_claims_submitted_at_once_only_one_wins`).

It is deliberately a heuristic. Drafts may look alike. A rejected claim does not block a corrected
re-claim. The same expense by two different employees is allowed, since colleagues can share a taxi.
Two genuinely different expenses with an identical title, amount and date would be refused. The
fix is to make the title more specific, which is acceptable for this scope.

## Server-computed `allowed_actions`

Every claim in every response carries `allowed_actions`, for example `["edit", "delete", "submit"]`. It is
computed by `rules.allowed_actions(user, claim)` from the same transition table the write path enforces. The
UI shows buttons only from this list, with no duplicated "if status is X and role is Y" logic in
React, so the buttons can't drift from the server's rules. The server still re-checks every action. An approver
never sees approve or reject on their own claim, and an employee never sees actions on someone else's claim.

## Money

Amounts are `Decimal` end to end in Python and strings in JSON (`"8000.00"`), so no binary
floating point is involved in validation or totals. Summary totals are added in Python with `Decimal`
rather than `SUM()` over `REAL`. SQLite stores them as `REAL` rounded to 2 decimals (see the
limitations section). The frontend converts to `Number` only for display.

## Authentication

The brief allows mocked login, and the first version had one (pick a user, get an opaque
token). It was replaced with real authentication.

| Piece | Choice |
|---|---|
| Passwords | `bcrypt` (the package directly; `passlib` is unmaintained and breaks with bcrypt ≥ 4.1). Cost 12. Minimum 8 characters. Passwords over **72 bytes are rejected** rather than silently truncated, because bcrypt ignores everything after byte 72. |
| Access token | JWT, HS256, 15 minutes. Claims: `sub`, `iat`, `exp`, `jti`, `type`. Sent as `Authorization: Bearer`. |
| Decoding | `algorithms=["HS256"]` is pinned and `sub`/`iat`/`exp`/`jti` are required, so `alg: none`, HS512, wrong-key and tampered tokens all fail. |
| Authorisation | The token carries **no role**. The user is loaded from the DB on every request, so a role change or deactivation applies on the next request. That costs one primary-key lookup. |
| Refresh token | 384 random bits in an `HttpOnly; SameSite=Lax; Path=/api/auth` cookie, `Secure` when `COOKIE_SECURE=true`. The DB stores only its SHA-256. Lifetime 7 days, sliding. |
| Rotation | Every refresh revokes the presented token and issues a successor in the same *family*. Replaying a rotated token outside a **10 s grace window** revokes the whole family: whoever holds the stolen copy and the real user are both logged out of that device, and other devices are unaffected. Inside the window it is treated as a benign race (two tabs, StrictMode) and gets an access token without a new cookie. The rotation itself is a conditional UPDATE, so two simultaneous refreshes can't both rotate. |
| Login | One generic error for an unknown email, a wrong password and an inactive account. An unknown email still runs a bcrypt check against a dummy hash, so response time doesn't reveal whether the account exists (measured: both about 0.19 s). |
| Brute force | An in-memory counter per (email, IP), 5 failures in 15 min → 15 min lockout (`429` + `Retry-After`), and per IP (20). Per (email, IP) rather than per email, so an attacker can't lock a real user out from elsewhere. |
| CSRF | The access token is not a cookie, so the claims API can't be CSRF'd. The two cookie-authenticated endpoints (`/refresh`, `/logout`) require `X-Requested-With`. A cross-site form can't set it, and a cross-site `fetch` that sets it needs a CORS preflight, which only the configured origin passes (`allow_credentials` is limited to `CORS_ORIGINS`, never `*`). `SameSite=Lax` is the second layer. |
| Logout | Revokes the family and clears the cookie. Works with an expired access token. Other tabs are told through a `BroadcastChannel`. |
| Re-login in the same browser | Logging in while a refresh cookie is present revokes that cookie's family (it is about to be overwritten), and other tabs switch to the new user immediately through the same `BroadcastChannel`. |
| Change password | Revokes **all** of the user's refresh tokens (every device), then starts a fresh session for the current one. |
| Secrets | `JWT_SECRET` comes from the environment or `backend/.env`. Startup fails if it is missing or shorter than 32 characters outside `APP_ENV=dev`. In dev a random per-process secret is used, and sessions survive restarts through refresh. |
| Removed | The `user_id` login, the opaque-token `sessions` table, and the public `GET /api/auth/users`, which let anyone enumerate users. It is replaced by approver-only `GET /api/users?role=employee`. |

### Trade-offs

**Access token in memory instead of `localStorage`.** Anything in `localStorage` can be read by any
script that runs on the page, so one XSS bug would leak a long-lived credential. In memory, an XSS can
still act *as* the user while the page is open (nothing fully prevents that), but it can't
exfiltrate something that keeps working later: the access token dies within 15 minutes and the refresh
token is `HttpOnly`. The cost is that a reload loses the token. That is why `AuthProvider` calls
`/refresh` on start, and `ProtectedRoute` shows "Checking your session…" instead of flashing the
login page. A module-level shared promise makes StrictMode's double effect send one request.

**Rotation instead of a long-lived static refresh token.** Rotation turns a stolen refresh token into
a detectable event: the first time both the attacker and the user use the same token, the family is
revoked. The grace window gives up a few seconds of detection to avoid logging people out when
two tabs refresh at once. Rotation also means one DB write per refresh, every 15 minutes per active tab,
which is negligible here.

**Stateless access tokens.** Logout and password change revoke refresh tokens immediately, but an
already-issued access token stays valid until it expires (≤ 15 min). Deactivation and role changes
still apply instantly, because the user row is read on every request. A `jti` denylist would close
the remaining gap if needed.

**Why HS256 (symmetric) and not RS256/ES256.** One service both issues and verifies tokens, so there
is no third party that should verify without being able to sign. HMAC is simpler, with one secret and no key
pair or JWKS, and it's fast. Asymmetric keys become worth it once other services need to verify tokens. The usual
HS256 risks are covered: the algorithm is pinned on decode (so no `alg` confusion), and the secret must
be 32+ characters outside dev.

**In-memory throttle.** It is fine for a single process. It resets on restart, and with several workers each
keeps its own count. A real deployment would keep it in Redis or the database.

**No self-registration.** Approvers can only come from the seed or the CLI. Self-registration for
employees was optional. It was left out because it adds an email-enumeration surface ("email already
taken") and needs email verification to be meaningful.

## Frontend API client

`api/client.js` is a thin `fetch` wrapper. It attaches the in-memory token, sends `credentials: 'include'`,
normalises every failure into one `ApiError {status, code, message, fields}`, and on a 401 from
anything but login/refresh/logout runs a **single-flight** refresh (one shared promise for all callers)
and retries the original request once. If the refresh fails it ends the session with a "session
expired" toast, and `ProtectedRoute` sends the user to login with `state.from`, so they come back
to the same page afterwards.

## If I had more time

- **Migrations** with Alembic instead of `create_all` plus a refuse-to-start check on old schemas.
- **Integer minor units** (paise) or SQLite `TEXT` decimals for money, instead of rounded `REAL`.
- **Postgres** for real concurrent writers. The conditional-UPDATE design carries over unchanged.
- **Receipt uploads** (file storage with type and size checks) instead of a reference string.
- **Throttle and token denylist in Redis**, an absolute session lifetime cap, and "sign out other
  devices" plus a change-password screen in the UI (the API exists).
- **Approval policies**: amount-based approval chains, per-category limits, delegation.
- **Notifications** (email or in-app) when a claim is decided or paid.
- **Multi-currency** with conversion rates captured at submission (the schema already stores `currency`).
- **End-to-end tests** (Playwright) for the demo script, run in CI with both unit suites.
- **Observability**: structured request logs with a request id, plus an audit view across all claims.
