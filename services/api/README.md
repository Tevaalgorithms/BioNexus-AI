# BioNexus API (`services/api`)

The Python backend: FastAPI routes, the seven agents, the LangGraph investigation workflow, the model
gateway and PostgreSQL storage. The web app (`apps/web`) is the only client; it talks to this service
over HTTP and shares no code with it.

## How a request flows

```text
HTTP route (api/) → service (application/) → workflow (workflow/) → agents (agents/)
                                                                         ↓                    ↓
                                                                  storage (storage/)   sources (sources/) and models (llm/)
```

Routes stay thin. Anything with a rule in it lives in a service or in the workflow, so it can be tested
without HTTP.

## Where things live

| Folder | What it holds |
| --- | --- |
| `contracts/` | Typed data models (evidence, messages, projects, errors). No logic and no I/O. |
| `agents/` | One file per agent, plus `base.py` (shared behaviour) and `skills.py`. |
| `workflow/` | The LangGraph graph (`graph.py`), step logic (`nodes.py`), dispatcher, budget, events. |
| `llm/` | The model gateway, the approved-model catalogue, configuration releases, LangChain adapter. |
| `sources/` | Guarded HTTP and `live/` (one module per public data source); `fixtures/` is synthetic sample data. |
| `evidence/` | The eligibility gate (licence, date cut-off) and the study-family matrix. |
| `storage/` | Storage ports, the in-memory store and `postgres/` (one module per store), plus migrations. |
| `auth/` | Cognito token verification and authorisation rules. |
| `api/` | Routes and request dependencies. |
| `application/` | The services behind the routes: investigations, projects, admin, and shaping data for the UI. |
| `cli/` | Entry points: `worker` (the job worker), `admin` (user tool) and `demo`. Run with `python -m bionexus.cli.<name>`. |
| `container.py` | The one place everything is wired together. |

## Run, test, lint

```bash
cd services/api
../../.venv/bin/ruff check .              # lint, including the complexity limit (McCabe 5)
../../.venv/bin/ruff format --check .
../../.venv/bin/python -m pytest          # unit and API tests; most run against both stores
../../.venv/bin/python -m bionexus.cli.demo   # a full investigation on sample data
```

PostgreSQL test cases need a database; without `BIONEXUS_TEST_DSN` they skip and the in-memory ones still
run. The root [README](../../README.md#run-it-locally) has the full local setup.

## Conventions

- Cost and speed levers (call limits, prompt sizes, parallelism, the response cache) are named constants in `bionexus/agents/optimization.py`; change them there, not inline.
- Keep each function simple: the Ruff complexity limit is 5 and CI enforces it.
- One class or one concern per module, named after what it holds.
- No secret values in code. Secrets are looked up by name (`llm/secrets.py`, `params.py`).
- Source text reaches a model only as delimited data (`agents/base.py::evidence_block`), never as instructions.
- New behaviour needs a test next to the existing ones in `tests/`.
