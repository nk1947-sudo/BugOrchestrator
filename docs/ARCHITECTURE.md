# BugOrchestrator - Architecture

BugOrchestrator is an authorized-security-testing orchestration platform. An operator
injects a target (a domain, host, or API base URL they are authorized to test)
through the dashboard or API; the orchestrator runs a bounded reasoning loop
against it, using pluggable connectors to recon/scan tooling; any action
classified as high-impact stops for a human approval before it executes.

**The platform never selects or authorizes targets on its own.** Authorization
is an operator responsibility recorded per-target (see "Scope & authorization"
below) - the same trust model as nmap, Burp Suite, or nuclei.

## Services

```
                         ┌─────────────────────┐
                         │   apps/dashboard     │  Next.js / TypeScript
                         │  (target intake, ​    │  - inject target URL + scope
                         │   findings, HITL)    │  - approve/reject queue
                         └──────────┬───────────┘
                                    │ REST + WebSocket
                                    ▼
                         ┌──────────────────────┐
                         │    services/api       │  FastAPI (Python)
                         │  control plane        │  - Postgres persistence
                         │                        │  - JWT auth
                         │  targets / scans /     │  - approvals queue
                         │  findings / approvals  │  - WS push to dashboard
                         └──────────┬───────────┘
                                    │ REST (internal)
                                    ▼
                         ┌──────────────────────┐        ┌───────────────────┐
                         │  services/orchestrator│──REST─▶│ services/scan-worker│  Go
                         │  Observe→Reason→Plan→ │        │  wraps nmap /       │
                         │  Execute→Verify loop  │◀──JSON─│  httpx / nuclei     │
                         └──────────┬───────────┘        └───────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              Shodan API      Censys API      Burp Suite REST API
              (connector)     (connector)     (connector)
```

Each box is an independently deployable service with its own Dockerfile;
`docker-compose.yml` wires them together for local/dev use. In a real
deployment each service scales independently (the scan-worker is the one
that benefits most from horizontal scaling / Go's concurrency).

## The five-stage loop (services/orchestrator)

Implemented in `services/orchestrator/src/orchestrator/loop.py` as an explicit
state machine (`ScanRun`), not an implicit chain - every transition is logged
and persisted via the API so the dashboard can show exactly where a run is at
any moment.

1. **OBSERVE** (`connectors/`) - pull passive/active recon data for the target:
   Shodan/Censys host data, and an httpx/nmap probe via the scan-worker. Builds
   an `ObservedState`: stack fingerprint, auth scheme, discovered routes,
   privilege tiers if multiple credentials are configured for the target.
2. **REASON** (`hypothesis.py`) - a rule-based hypothesis generator looks for
   parameter/route anomalies (IDOR-shaped IDs, privilege-tier mismatches,
   suspicious internal headers) and emits ranked `Hypothesis` objects with a
   confidence score and category. No hypothesis is executed automatically.
3. **PLAN** (`loop.py::plan_actions`) - turns a hypothesis into one or more
   minimal, non-destructive `PlannedAction`s (e.g. one differential HTTP
   request) plus the diffing criteria that will count as confirmation. Every
   `PlannedAction` carries a `category`; categories listed in
   `HITL_REQUIRED_CATEGORIES` (.env) force a human approval gate.
4. **EXECUTE** (`connectors/scan_worker_connector.py`, `connectors/burp_connector.py`)
   - if the action's category requires approval, the orchestrator creates an
     `Approval` via the API and **blocks** (up to `HITL_APPROVAL_TIMEOUT_SECONDS`)
     until a human approves/rejects it in the dashboard.
   - otherwise it dispatches directly (still fully logged).
5. **VERIFY & REPORT** (`reporting.py`) - compares the response delta against
   the hypothesis's confirmation criteria. Confirmed findings are written to
   `workspace/findings/CONFIRMED_<TYPE>_<TARGET>_<TIMESTAMP>.md` (git-ignored,
   local-only - the platform never commits or pushes on its own) and posted to
   the API so they show up in the dashboard. Unconfirmed results update the
   per-endpoint audit record and the loop advances to the next candidate.

## Scope & authorization

Every `Target` row requires an `authorization_note` (free text: program name,
ticket link, or a statement that the operator owns the asset) before the
orchestrator will schedule a run against it - enforced in
`services/api/src/api/routers/targets.py`. This does not verify authorization
against any external source (there is no such general-purpose API); it exists
so scope is recorded and auditable, and so a target can't be scheduled by
accident with no scope note at all. Operators are responsible for only
injecting targets they are actually authorized to test.

`Target.passive_only` (default `true` for every new target) is a second,
independent gate: while set, the orchestrator never sends a single request
to the target - `loop.py::_observe` skips the scan-worker `httpx` probe and
`loop.py::_execute_and_verify` refuses to dispatch any planned action,
regardless of what OBSERVE/REASON/PLAN produced. Only third-party OSINT
(Shodan/Censys, which query their own databases, never the target) still
runs. This exists because "I have authorization to test this" and "this
program permits *automated* scanning" are different questions - many bug
bounty VDPs explicitly prohibit automated scanners while still permitting
(and rewarding) manual testing. An operator must explicitly flip a target to
`passive_only: false` - via the dashboard's "Enable active scanning" toggle,
with a confirmation prompt - only once they've confirmed the target's actual
authorization covers automated tooling, not just manual testing.

## Human-in-the-loop (HITL) gate

Categories in `HITL_REQUIRED_CATEGORIES` (.env) always pause for approval:

- `admin_access` - request paths matching admin/internal route patterns
- `destructive_state_change` - non-idempotent methods (POST/PUT/PATCH/DELETE)
  against anything other than a scoped, pre-approved test object
- `aggressive_payload` - anything beyond a single differential/read-only probe
- `waf_bypass` - header spoofing, path mutation, or method-override techniques
  used to test access-control/origin restrictions (see below)

Approvals are visible in `apps/dashboard/app/approvals` and are backed by
`services/api`'s `approvals` table, so the audit trail survives restarts.

## WAF / access-control bypass module

`services/orchestrator/src/orchestrator/bypass.py` exposes a small set of
documented access-control bypass techniques (origin header spoofing, a
double-slash path mutation, HTTP method override) used to test whether an
access restriction is enforced only at one layer (e.g. a WAF rule that a
direct-to-origin request bypasses). It is only invoked from
`loop.py::_run_access_control_check` after a baseline request to a
suspected admin/internal route returns `403` - never unconditionally. This
is a legitimate, commonly in-scope bug-bounty finding class (broken access
control), not a general detection-evasion feature: each variant it produces
is always categorized `waf_bypass` and always routed through the HITL gate
above.

Note: a dot-segment mutation (`/admin/./panel`) was deliberately rejected in
favor of a double-slash mutation - `httpx` (and most conforming HTTP
clients) performs RFC 3986 dot-segment removal before a request reaches the
wire, so a `./` mutation would silently collapse back to the original path
and test nothing when dispatched through `target_client.py`. A doubled
slash is not a dot-segment and survives unnormalized.

## Local artifacts, no auto-git

Findings, raw request/response captures, and run state live under
`workspace/` (git-ignored). No service in this repo runs `git commit`,
`git push`, or opens PRs/issues - that stays a human action.

## Data model (services/api)

- `targets` - injected target + scope/authorization note + credentials refs
- `scans` - one row per orchestrator run against a target, with current stage
- `findings` - confirmed/unconfirmed results, severity, raw evidence
- `approvals` - pending/approved/rejected HITL gate requests
- `users` - dashboard operators (JWT auth)

## Rate limiting & backoff

`services/orchestrator/src/orchestrator/ratelimit.py` tracks per-target,
per-endpoint cooldowns in Redis. A `429` sets a cooldown (default from
`RATE_LIMIT_DEFAULT_COOLDOWN_SECONDS`) and the loop moves to the next
candidate instead of retrying in place. A `403` is treated as a normal
observation that may itself become a `waf_bypass` hypothesis - it does not
trigger silent evasion.
