# Repository structure

Where things are. The README has the short version.

```text
services/api/                      Python backend
  bionexus/
    contracts/                     typed data models: evidence, messages, projects, identity, errors
    agents/                        the roles that call a model: planner, literature, critic, verifier, synthesizer, plus the shared base
    specialists/                   source specialists that need no model: genetics, pathways, clinical
    messaging/                     message envelope builder and the allowlisted router
    workflow/                      LangGraph graph, step logic, the supervisor (coordinator), dispatcher, budget, run executor, events
    llm/                           model catalogue, configuration releases, gateway, LangChain client
    sources/                       guarded HTTP, live/ (one module per public source), fixtures/ (synthetic)
    evidence/                      eligibility gate (licence, cutoff) and the study-family matrix
    retrieval/                     full-text and vector search, rank fusion, evidence graph
    reporting/                     report builder, review and revision, Word export, next experiments
    jobs/                          durable job queue worker
    storage/                       ports, in-memory store, postgres/ (one module per store), SQL migrations
    auth/                          Cognito token verifier and authorisation rules
    api/                           FastAPI routes (runs, projects, admin) and dependencies
    application/                   the services behind the routes: investigations, projects, admin, UI shaping
    cli/                           entry points: worker, admin user tool, offline demo
    evals/                         baselines, ablations and metrics on a synthetic reference set
    container.py                   the one place everything is wired together
    bootstrap.py                   builds the production container (PostgreSQL, Cognito)
    config.py, params.py           settings, and the .env / SSM source they come from
    observability.py               structured logs with opaque ids only
  tests/                           365 tests in 25 files; most run against both stores
apps/web/                          Next.js app
  app/                             routes only: (scientist)/, (admin)/, login, access-denied, api/ (auth, proxy, session)
  components/                      grouped by feature: ui/, layout/, auth/, projects/, runs/, admin/, help/
  hooks/                           useApi, useProjects, useRunEvents
  lib/                             configuration, sessions, Cognito and PKCE, API types, plain-language wording
  tests/                           Vitest unit tests
  middleware.ts                    sends visitors without a session to the right sign-in page
skills/                            versioned, hashed instructions, one per role
config/                            example model list (prices must be verified before use)
infra/terraform/                   Lightsail, Cognito (with sign-in branding), SSM parameters, ECR, deploy role, budget alert
infra/lightsail/                   Docker Compose stack, MVP memory limits and the Caddy TLS proxy
scripts/                           init-env, install-hooks, ci-deploy, deploy (with rollback), backup, restore, host-update
docs/                              architecture, configuration, costs, runbooks/
.github/                           workflows/ci.yml (checks), workflows/deploy.yml (release on a tag), CODEOWNERS
```
