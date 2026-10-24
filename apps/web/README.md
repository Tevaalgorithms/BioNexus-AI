# BioNexus web app (`apps/web`)

The Next.js app that scientists and administrators use. It also acts as the backend-for-frontend: it
handles sign-in with Cognito, keeps tokens on the server, and forwards API calls to `services/api`. The
browser never holds an access token.

## Where things live

| Path | What it holds |
| --- | --- |
| `app/` | Routes only. `(scientist)/` is the product, `(admin)/` the admin console, `login/` and `access-denied/` the entry pages. |
| `app/api/auth/` | Sign-in, callback and sign-out routes (the Cognito flow with PKCE). |
| `app/api/proxy/` | Forwards browser calls to the API with the user's token attached on the server. |
| `components/ui/` | Generic building blocks: tables, charts, icons, badges, `primitives.tsx`. No product logic. |
| `components/layout/` | The application shell: navigation, user card, theme toggle placement. |
| `components/auth/` | The sign-in card. |
| `components/projects/` | Project list, dashboard and the new-project dialog. |
| `components/runs/` | Starting an investigation and viewing its progress, evidence, report and review. |
| `components/admin/` | One file per admin screen (models, skills, sources, usage, audit, releases) plus diagrams. |
| `hooks/` | Data hooks: `useApi`, `useProjects`, `useRunEvents`. |
| `lib/` | Server and shared helpers: configuration, sessions, Cognito, PKCE, API types. |
| `middleware.ts` | Redirects visitors without a session to the right sign-in page. |

## Run, test, build

```bash
cd apps/web
npm ci
BIONEXUS_API_URL=http://localhost:8100 PUBLIC_BASE_URL=http://localhost:3100 npm run dev -- -p 3100
npm run typecheck
npm test
npm run build
```

Local settings come from the git-ignored `.env` that `scripts/init-env.sh` creates. The root
[README](../../README.md#run-it-locally) has the full local setup.

## Conventions

- Put a component in the folder of the feature that uses it. Move it to `components/ui/` only when a second
  feature needs it and it holds no product logic.
- One screen or one component per file. Name the file after what it exports.
- Redirects use the configured public address (`PUBLIC_BASE_URL`), never `request.url`: behind the proxy
  that is the container's internal address.
- No secrets in client code. Anything secret is read on the server in `lib/config.ts`.
- Plain-language descriptions of stages, skills and sources live in one place, `lib/explain.ts`, so wording stays consistent.
