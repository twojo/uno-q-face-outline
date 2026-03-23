# Workspace

## Overview

pnpm workspace monorepo using TypeScript. Each package manages its own dependencies.

## Smart Mirror AI Photo Booth

Standalone Flask app at the workspace root. Prototype for Arduino Uno Q (QRB2210) deployment.

### Architecture

Single-step identity-preserving transformation via **InstantID** (`fal-ai/instantid`):
- Takes webcam capture as `face_image_url` reference
- `ip_adapter_scale=0.95` for maximum identity fidelity
- `controlnet_conditioning_scale=0.90` for strong facial structure preservation
- 20 inference steps (fast), guidance_scale=4.0
- Identity-anchored prompts: every prompt starts with "High-fidelity portrait of the exact person in the reference image"
- Strict negative prompt blocks generic/deformed/stylized output
- Rotating file logger: `mirror_debug.log` (5 MB x 3 backups)

### Features

- Single "Snap & Transform" button — no theme selection, always random
- 3-2-1 countdown with camera flash effect
- 6 themed prompt pools internally: Time Traveler, Action Hero, Fantasy Realm, Explorer, Pop Culture, Wild Card
- Side-by-side before/after reveal with animation
- Result metadata: theme, seed, prompt displayed
- Scrollable gallery strip of past transformations
- Fullscreen view on gallery thumbnail tap
- Rotating fun loading messages during generation
- Robust JSON parse error handling

### Key Files

| File | Purpose |
|------|---------|
| `app.py` | Flask HTTP backend for Replit (POST /transform) |
| `main.py` | Bricks SDK backend for Arduino Uno Q (Socket.IO events) |
| `main_free.py` | Free alternative using Hugging Face (no paid API key) |
| `templates/index.html` | Full photo booth UI — camera, face mesh, countdown, reveal, gallery |
| `arduino/` | Replit shim folder — mimics Arduino Bricks SDK for prototyping |
| `arduino/app_bricks/web_ui.py` | Shim for WebUI (Flask-SocketIO on Replit) |
| `arduino/app_utils.py` | Shim for App.run() |

### Dependencies

- Python: `flask`, `flask-socketio`, `requests`, `Pillow`, `fal-client`
- **Workflow**: "Smart Mirror" — `python3 app.py` on `PORT` (default 8000)
- **Secret**: `FAL_KEY` — fal.ai API key (paid); or `HF_TOKEN` for free version

### Deployment Targets

| Target | Entry Point | Env Var | Notes |
|--------|-------------|---------|-------|
| Replit | `app.py` | `FAL_KEY` | Flask HTTP, keep `arduino/` folder |
| Uno Q | `main.py` | `FAL_KEY` | Bricks SDK, DELETE `arduino/` folder |
| Free | `main_free.py` | `HF_TOKEN` | Hugging Face instruct-pix2pix |

### Deploying to the Uno Q

1. Copy entire project to Uno Q filesystem
2. `rm -rf arduino/` (real Bricks SDK is pre-installed on device)
3. `pip install requests Pillow fal-client`
4. `export FAL_KEY="your-key"`
5. `python main.py` (NOT app.py)
6. Real SDK handles: TLS, mDNS, QR-code pairing, iframe video streaming

### Tuning Knobs

- `ip_adapter_scale`: 0.85 (high fidelity to YOUR face; raise to 0.9 if still generic)
- `controlnet_conditioning_scale`: 0.8 (respects the POSE; raise to 0.9 for stronger structure)
- `guidance_scale`: 5.0 (lower = better blending with identity; raise for more prompt adherence)
- `enhance_face_region`: True (keeps eyes/mouth sharp)

## Stack

- **Monorepo tool**: pnpm workspaces
- **Node.js version**: 24
- **Package manager**: pnpm
- **TypeScript version**: 5.9
- **API framework**: Express 5
- **Database**: PostgreSQL + Drizzle ORM
- **Validation**: Zod (`zod/v4`), `drizzle-zod`
- **API codegen**: Orval (from OpenAPI spec)
- **Build**: esbuild (CJS bundle)

## Structure

```text
artifacts-monorepo/
├── artifacts/              # Deployable applications
│   └── api-server/         # Express API server
│   └── smart-mirror/       # AI photo booth artifact config
├── lib/                    # Shared libraries
│   ├── api-spec/           # OpenAPI spec + Orval codegen config
│   ├── api-client-react/   # Generated React Query hooks
│   ├── api-zod/            # Generated Zod schemas from OpenAPI
│   └── db/                 # Drizzle ORM schema + DB connection
├── scripts/                # Utility scripts
├── app.py                  # Smart Mirror Flask backend
├── templates/index.html    # Smart Mirror UI
├── pnpm-workspace.yaml
├── tsconfig.base.json
├── tsconfig.json
└── package.json
```

## TypeScript & Composite Projects

Every package extends `tsconfig.base.json` which sets `composite: true`. The root `tsconfig.json` lists all packages as project references. This means:

- **Always typecheck from the root** — run `pnpm run typecheck` (which runs `tsc --build --emitDeclarationOnly`). This builds the full dependency graph so that cross-package imports resolve correctly. Running `tsc` inside a single package will fail if its dependencies haven't been built yet.
- **`emitDeclarationOnly`** — we only emit `.d.ts` files during typecheck; actual JS bundling is handled by esbuild/tsx/vite...etc, not `tsc`.
- **Project references** — when package A depends on package B, A's `tsconfig.json` must list B in its `references` array. `tsc --build` uses this to determine build order and skip up-to-date packages.

## Root Scripts

- `pnpm run build` — runs `typecheck` first, then recursively runs `build` in all packages that define it
- `pnpm run typecheck` — runs `tsc --build --emitDeclarationOnly` using project references

## Packages

### `artifacts/api-server` (`@workspace/api-server`)

Express 5 API server. Routes live in `src/routes/` and use `@workspace/api-zod` for request and response validation and `@workspace/db` for persistence.

- Entry: `src/index.ts` — reads `PORT`, starts Express
- App setup: `src/app.ts` — mounts CORS, JSON/urlencoded parsing, routes at `/api`
- Routes: `src/routes/index.ts` mounts sub-routers; `src/routes/health.ts` exposes `GET /health` (full path: `/api/health`)
- Depends on: `@workspace/db`, `@workspace/api-zod`
- `pnpm --filter @workspace/api-server run dev` — run the dev server
- `pnpm --filter @workspace/api-server run build` — production esbuild bundle (`dist/index.cjs`)
- Build bundles an allowlist of deps (express, cors, pg, drizzle-orm, zod, etc.) and externalizes the rest

### `lib/db` (`@workspace/db`)

Database layer using Drizzle ORM with PostgreSQL. Exports a Drizzle client instance and schema models.

- `src/index.ts` — creates a `Pool` + Drizzle instance, exports schema
- `src/schema/index.ts` — barrel re-export of all models
- `src/schema/<modelname>.ts` — table definitions with `drizzle-zod` insert schemas (no models definitions exist right now)
- `drizzle.config.ts` — Drizzle Kit config (requires `DATABASE_URL`, automatically provided by Replit)
- Exports: `.` (pool, db, schema), `./schema` (schema only)

Production migrations are handled by Replit when publishing. In development, we just use `pnpm --filter @workspace/db run push`, and we fallback to `pnpm --filter @workspace/db run push-force`.

### `lib/api-spec` (`@workspace/api-spec`)

Owns the OpenAPI 3.1 spec (`openapi.yaml`) and the Orval config (`orval.config.ts`). Running codegen produces output into two sibling packages:

1. `lib/api-client-react/src/generated/` — React Query hooks + fetch client
2. `lib/api-zod/src/generated/` — Zod schemas

Run codegen: `pnpm --filter @workspace/api-spec run codegen`

### `lib/api-zod` (`@workspace/api-zod`)

Generated Zod schemas from the OpenAPI spec (e.g. `HealthCheckResponse`). Used by `api-server` for response validation.

### `lib/api-client-react` (`@workspace/api-client-react`)

Generated React Query hooks and fetch client from the OpenAPI spec (e.g. `useHealthCheck`, `healthCheck`).

### `scripts` (`@workspace/scripts`)

Utility scripts package. Each script is a `.ts` file in `src/` with a corresponding npm script in `package.json`. Run scripts via `pnpm --filter @workspace/scripts run <script>`. Scripts can import any workspace package (e.g., `@workspace/db`) by adding it as a dependency in `scripts/package.json`.
