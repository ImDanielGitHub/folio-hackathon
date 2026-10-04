# Nebius deployment source and release gates

Status: source prepared; **not provisioned, built as a container, deployed or live-verified**. No cloud resources, credentials, billing changes or paid inference were created. The web/API implementation and integration tests must pass before deployment is proposed.

## Intended topology

A modest Nebius CPU VM hosts the HTTPS gateway, containerised FastAPI service and a separate durable worker. Managed PostgreSQL is the authoritative cloud store for workspace state, runs, leases and outbox; private object storage holds approved attachments/exports. The SwiftUI client and limited synthetic web companion consume the same API. Token Factory provides the pinned Nemotron model. A Mac cache is not a second authoritative ledger.

This folder's runnable Compose source currently includes the gateway and API. It deliberately does **not** invent a worker process, queue, object-store adapter or owner authentication system that has not been integrated. Add the worker service only after its entrypoint, leases, retry policy and crash/idempotency tests exist. An unused PostgreSQL or bucket setting is not evidence that a feature is backed by it. Public demo isolation must remain distinct from any future real-owner environment.

CPU Serverless Endpoints/Jobs are an alternative deployment path, not a requirement of this topology. Before adopting them, verify SSE, execution duration, private database connectivity, user authentication, cold starts and cancellation. Never use their ephemeral filesystem as the authoritative database.

## Required decisions and access

1. Approve a Nebius project, region, CPU size, network/subnet, monthly spending cap and exact billable resources. Check current account availability, pricing, quotas and data-processing terms.
2. Provide an existing authorised infrastructure identity. Creating credentials or expanding persistent access is a separate approval step. Infrastructure authentication and Token Factory inference keys are distinct.
3. Provision Managed PostgreSQL with a private endpoint. Use a scoped database role, `sslmode=verify-full` and the official CA. Obtain exact endpoint/database/user values from the account, never guesses. Restrict port 5432 to the application network.
4. Provision a private object bucket in the selected region, scoped object access, lifecycle/retention policy and backups. Its endpoint has the form `https://storage.<region>.nebius.cloud`. Keep TLS enabled. Signed URL expiry, tenant-scoped object paths and authorisation need integration tests.
5. Approve a domain, DNS target and TLS termination. Public ingress should be HTTPS plus only the HTTP challenge/redirect needed for certificates. Keep API's 8080 port inside the Compose network.
6. Install the already-authorised inference credential only in backend secret storage. Never place it in a web bundle, Mac application, URL, repository or shell history. Verify quota/cost alerts and the pinned model with a synthetic smoke run.

Primary references: [CPU/container VMs](https://docs.nebius.com/compute/virtual-machines/containers), [Managed PostgreSQL setup](https://docs.nebius.com/postgresql/quickstart), [PostgreSQL TLS and private endpoints](https://docs.nebius.com/postgresql/databases/connect), [Object Storage setup](https://docs.nebius.com/object-storage/quickstart), [HTTPS default](https://docs.nebius.com/object-storage/http-access). The PostgreSQL quickstart includes a publicly accessible example; this application's proposed deployment uses private database access instead.

## Build and configuration

From the repository root, regenerate the hash-locked production Python requirements after an intentional dependency update:

```sh
uv export --project services/api --frozen --no-dev --no-emit-project \
  --format requirements-txt --output-file services/api/requirements.lock
```

After approval and source verification, build with:

```sh
docker build -f deploy/nebius/Dockerfile.api -t folio-api:<build-sha> .
```

The image runs as UID 10001, installs hash-locked dependencies and disables access logs. Before release, pin the Python and gateway base images to reviewed digests and record build SHA/configuration version. Docker was not available in the implementation environment; container build and runtime checks remain required.

The Compose file requires `FOLIO_DOMAIN`, `DATABASE_URL` and `POSTGRES_CA_FILE`. Use the PostgreSQL psycopg URL format with `sslmode=verify-full`; the CA is mounted read-only. Optional `NEBIUS_API_KEY` enables inference eligibility only. The source's empty example file contains no credentials. Use a protected runtime environment or managed secret injection, not a committed dotenv file. Build the web companion into `apps/web-demo/dist` before starting the gateway.

The `/health` probe proves process liveness only. Add/verify readiness checks for schema, database and worker before routing production traffic. A provider outage should not make deterministic views disappear; provider state is a separate capability.

## Release checklist

- Run fresh Python, web and native checks against the pinned commit; no legacy-repo code dependency.
- Verify two unrelated demo sessions cannot read/write each other's data, replay a mutation twice, test stale versions and unauthorised origins, and enforce public demo quotas.
- Migrate an empty disposable PostgreSQL environment explicitly. Never mutate schema inside a request.
- Test database backup/restore. Test a worker crash after commit and recovery without duplicate effects. Verify SSE reconnect from persisted events.
- Test signed object URLs for expiry, wrong workspace and missing permission before enabling exports.
- Exercise one real Nemotron question with typed tool calls; capture only run IDs, usage, timings and redacted errors. Do not log private prompts/responses.
- Verify observed financial results and source records match deterministic calculations. A passing mocked provider test is not live proof.
- Confirm no real bank connections or owner data can enter anonymous demo workspaces.
- Verify live TLS, domain, health/readiness, quota alerts and rollback image; then obtain approval to publish a demo/release.

Publication, cloud spend, resource creation and credential installation are not authorised merely by the existence of these files.
