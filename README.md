# Aegis Mesh

An authorized-security-testing orchestration platform: inject a target you're
authorized to test, and a bounded reasoning loop (observe -> reason -> plan ->
execute -> verify) runs recon/scan connectors against it, gating any
high-impact action behind human approval before it fires.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design,
data model, and the human-in-the-loop (HITL) approval model.

> **Scope is your responsibility.** This platform records an authorization
> note per target but cannot verify authorization against any external
> system. Only point it at assets covered by a program you're enrolled in or
> that you own outright - same trust model as nmap or Burp Suite.

## Stack

| Component | Path | Language |
|---|---|---|
| Dashboard (target intake, findings, HITL approvals) | `apps/dashboard` | TypeScript / Next.js |
| Control plane API (Postgres, auth, REST + WebSocket) | `services/api` | Python / FastAPI |
| Orchestration engine (the 5-stage loop) | `services/orchestrator` | Python |
| Scan worker (nmap / httpx / nuclei wrapper) | `services/scan-worker` | Go |
| Shared JSON schemas | `packages/shared-schema` | JSON Schema |

## Quickstart

```bash
cp .env.example .env
# edit .env: set POSTGRES_PASSWORD, SECRET_KEY, ADMIN_PASSWORD at minimum.
# Shodan/Censys/Burp keys are optional - connectors without a key report
# themselves unconfigured and are skipped.

make up
```

This starts Postgres, Redis, the API, the scan-worker, the orchestrator, and
the dashboard via `docker-compose.yml`. Dashboard: http://localhost:3000,
API: http://localhost:8000/docs (OpenAPI/Swagger UI).

### Running services individually (without Docker)

```bash
make api-install && make api-migrate && make api-dev      # http://localhost:8000
make orchestrator-install && make orchestrator-dev
make worker-run                                             # requires Go 1.23+
make dashboard-install && make dashboard-dev                # http://localhost:3000
```

`nmap`, `httpx`, and `nuclei` binaries are optional at the scan-worker level:
if a binary isn't on `PATH`, the worker reports that tool as unavailable in
its response instead of failing the whole request.

## Tests

```bash
make test          # api + orchestrator (pytest) + scan-worker (go test)
```

## Repository layout

```
apps/dashboard/          Next.js dashboard (target intake, findings, HITL queue)
services/api/             FastAPI control plane + Postgres models + Alembic migrations
services/orchestrator/    5-stage loop engine + Shodan/Censys/Burp connectors
services/scan-worker/     Go microservice wrapping nmap/httpx/nuclei
packages/shared-schema/   JSON Schemas shared across services
workspace/findings/       Local Markdown/JSON finding reports (git-ignored)
docs/ARCHITECTURE.md      Full architecture, data model, HITL design
```

## Security notes

- Secrets live only in `.env` (git-ignored) - see `.env.example` for every
  key the platform reads.
- No service in this repo calls `git commit`, `git push`, or opens a PR/issue.
  Findings are written locally to `workspace/findings/`; a human decides what
  to do with them.
- Access-control/WAF bypass techniques are an explicit, logged module gated
  behind the same human-approval queue as every other high-impact action -
  see "WAF / access-control bypass module" in the architecture doc.
