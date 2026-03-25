# Workspace

## Overview

pnpm workspace monorepo using TypeScript. Each package manages its own dependencies.

## Face Tracker

Standalone Flask app at the workspace root. Real-time face tracking using MediaPipe, branded for Qualcomm QRB2210.

### Architecture

Pure client-side face detection using **MediaPipe Face Landmarker** (v0.10.3):
- 478 facial landmarks tracked per face in real-time
- Supports up to 4 simultaneous faces with persistent ID tracking
- CPU delegate (primary, reliable) with GPU fallback
- All processing happens in the browser — backend only serves the HTML page
- Blendshapes enabled for expression detection and blink tracking

### Features

- Real-time face mesh tessellation overlay (all 478 landmarks)
- Face outline (jawline/oval) tracking
- Individual feature tracking: eyes, eyebrows, lips, iris
- Landmark dot visualization (1px dots per landmark)
- **Per-face persistent tracking**: faces get unique IDs and colors, with tracking duration shown
- Face matching uses sorted global-minimum distance with adaptive thresholds (scaled by face width)
- Tracks survive brief detection dropouts (800ms TTL)
- Each face gets a unique color (blue, orange, green, purple) for easy identification
- Floating label above each face showing "Face N · duration"
- Head pose estimation (yaw/pitch) for primary face
- 6 overlay presets: Full Mesh+Features (default), Outline+Features, Mesh Only, Dots Only, Minimal, Outline+Emojis
- 8 emoji expression indicators per face (smile, anger, surprise, brow raise, wink, pucker, squint, frown)
- Eye blink detection with hot pink flash on blink (threshold 0.45)
- **Device simulation toggle**: Uno Q (QRB2210, throttled) vs Ventuno (QCS6490, full speed 3x faster)
  - Uno Q: frame skipping (every 2/3 frames), 35ms throttle delay, max 2 faces
  - Ventuno: no throttling, full speed, max 4 faces
- Specs bar showing SoC, CPU, MCU (STM32H747), RAM, max faces, delegate — updates per device
- HUD panels: face count, FPS, latency, resolution, device, yaw/pitch, blink L/R, uptime, frame count, detect count — updated every 500ms
- Header links: buy link (Uno Q store / Ventuno announcement), Arduino AppLab, GitHub
- Qualcomm branding with logo in header and professional dark UI
- System diagnostics panel (hidden by default, kept for debugging)

### Key Files

| File | Purpose |
|------|---------|
| `app.py` | Flask backend — serves the HTML page and static files |
| `templates/index.html` | Full face tracker UI — camera, mesh overlay, tracking HUD, overlay controls |
| `static/qualcomm-logo.png` | Qualcomm brand logo |

### Dependencies

- Python: `flask`
- Client-side: MediaPipe Tasks Vision (CDN via skypack)
- WASM: MediaPipe via jsdelivr CDN
- Fonts: Inter + JetBrains Mono (Google Fonts)
- **Workflow**: "Smart Mirror" — `python3 app.py` on `PORT` (default 8000)

### Critical Implementation Notes

- Video uses `display: block; width: 100%` with `transform: scaleX(-1)` for mirror effect
- Canvas uses `position: absolute; top:0; left:0; width:100%; height:100%` with matching `scaleX(-1)`
- Canvas internal dimensions set to `video.videoWidth/Height` once (not every frame)
- DrawingUtils recreated only when canvas dimensions change
- Timestamps for `detectForVideo` use `requestAnimationFrame` callback time with guaranteed monotonic increment
- Model fails in headless/no-WebGL environments (Replit preview) — works in real browser with camera
- Stats update every 2 seconds to minimize DOM overhead

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
│   └── smart-mirror/       # Face tracker artifact config
├── lib/                    # Shared libraries
│   ├── api-spec/           # OpenAPI spec + Orval codegen config
│   ├── api-client-react/   # Generated React Query hooks
│   ├── api-zod/            # Generated Zod schemas from OpenAPI
│   └── db/                 # Drizzle ORM schema + DB connection
├── scripts/                # Utility scripts
├── app.py                  # Face Tracker Flask backend
├── templates/index.html    # Face Tracker UI
├── static/                 # Static assets (logo, etc.)
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
