# TenacitOS Discovery (2026-04-10)

> Findings from Phase 0 / Task 0.5 of the E2 Mission Control implementation plan.
> Validates upstream assumptions BEFORE Task 1 commits anything to our repo.

**Upstream:** github.com/carlosazaustre/tenacitOS @ `b0215064fe0678dcca8c68a30617a47312317086`
**Local clone:** `~/scratch/tenacitos-discovery/` (throwaway, delete after Task 4)

---

## Tech stack actual

- **Next.js**: 15.x (verified via `package.json`)
- **React**: 19.x
- **Tailwind**: v4 (`@tailwindcss/postcss`, `@tailwindcss/typography`)
- **Test runner**: **NONE** — no vitest, no jest, no test script in `package.json`. We will install vitest in Task 1 as part of the bootstrap.
- **TypeScript**: yes (devDependency)
- **better-sqlite3**: yes (already a dep — confirms reuse for our events indexer)
- **Other notable deps:**
  - `@react-three/drei`, `@react-three/fiber`, `@react-three/rapier`, `three` — 3D libs to delete in Task 2
  - `@monaco-editor/react` — for code/file editing (file browser deferred; dep stays dormant)
  - `react-markdown` — for memory browser (deferred)
  - `recharts` — charts library (used by Cost module)
  - `lucide-react` — icons
  - `date-fns` — date utilities

**`scripts` block:**
```json
{
  "dev": "next dev -H 0.0.0.0",
  "build": "next build",
  "start": "next start -H 0.0.0.0",
  "lint": "eslint"
}
```

> **Important:** dev/start bind to `0.0.0.0` by default. Our systemd unit (Task 16) MUST override this with `-H 127.0.0.1` so the app is only reachable via Cloudflare Tunnel, not the public network interface.

> **Coincidence:** the upstream `package.json` already has `"name": "mission-control"`. No package rename needed in Task 1.

---

## File layout actual

### Dashboard route group

`src/app/(dashboard)/` exists ✓ (plan assumption correct).

It contains **22 pages** out of the box:
```
about         actions       activity      agents        analytics
calendar      costs         cron          files         git
logs          memory        reports       search        sessions
settings      skills        system        terminal      workflows
```

**Mapping against our v1 nav (5 items: Home / Knowledge / Approvals / Health / Cost):**

| Our v1 module | Upstream page | Action |
|---|---|---|
| Home (`/`) | `(dashboard)/page.tsx` | **REPLACE** with our 2-col asymmetric Home (Task 10) |
| Knowledge (`/knowledge`) | does not exist | **CREATE** (Task 12) |
| Approvals (`/approvals`) | does not exist | **CREATE** (Task 13) |
| Health (`/health`) | does not exist; `(dashboard)/system` covers system stats | **CREATE** as `(dashboard)/health/page.tsx` (Task 14); aggregates from upstream `/api/system/*` and our timers |
| Cost (`/cost`) | `(dashboard)/costs/page.tsx` (plural) | **DECISION:** rename our route to `/costs` (plural) to match upstream and reuse the page (Task 15a). Update `nav-config.ts` accordingly. |
| Activity (stretch, `/activity`) | `(dashboard)/activity/page.tsx` | **REUSE or REPLACE** in Task 15b (stretch). Decide based on whether upstream's activity feed reads from `events.jsonl` (it does NOT — see API findings). |

### 18 pages NOT in our v1

`about, actions, agents, analytics, calendar, cron, files, git, logs, memory, reports, search, sessions, settings, skills, system, terminal, workflows`

**Decision:** **leave them in place, just don't link to them in `nav-config.ts`.** They remain accessible only by direct URL. Deleting all 18 in Phase 0 would balloon the work and risk breaking shared imports. Defer cleanup to a future v1.5 housekeeping pass.

This contradicts the spec's "shell util antes de dashboard bonito" principle slightly (we ship code we don't need), but is the lower-risk path. The pages are dormant; they cost nothing at runtime.

### API routes already present

```
/api/actions          /api/activities (+ /stats, /stream)
/api/agents (+ [id]/status)              /api/analytics
/api/auth/login       /api/auth/logout
/api/browse           /api/costs
/api/cron (+ /run, /runs)
/api/files (+ /delete, /download, /mkdir, /upload, /workspaces, /write)
/api/git              /api/health
/api/logs (+ /stream) /api/media/[...path]
/api/memory (+ /search)
/api/notifications    /api/office
/api/reports          /api/search
/api/sessions         /api/skills
/api/system (+ /monitor, /services, /stats)
/api/terminal         /api/weather
```

**Useful for our v1:**
- `/api/git` — multi-repo git status. **Caveat:** scans `OPENCLAW_DIR/workspace` for `.git` dirs. `bevox-knowledge` is at `~/bevox-knowledge` (NOT in workspace), so this API will not find it without configuration. **Decision:** create our own `/api/bevox/git-last-commit/route.ts` (per plan) targeting `bevox-knowledge` directly, do NOT depend on `/api/git`.
- `/api/system/monitor`, `/api/system/services`, `/api/system/stats` — system metrics + service control. **Reuse for the System sub-section of our Health module.** Note that `/api/system/services` already has `mission-control` in its allowlist! We can call it to show our own service status.
- `/api/health` — pings URLs (different concept from ours, which is timer/snapshot freshness). Use as ONE input among many in our Health page.
- `/api/costs` — reads from `data/usage-tracking.db` (SQLite at `process.cwd()/data/usage-tracking.db`). Returns `{ today, yesterday, daily: [...], byAgent: [...], byModel: [...], ... }`. **Reuse directly in our Cost page** (Task 15a). Plan currently calls `/api/cost/today` which is wrong — needs delta.
- `/api/activities` — reads from `@/lib/activities-db` (a SEPARATE SQLite, NOT `events.jsonl`). Schema: `{ id, timestamp, type, description, status, duration_ms, tokens_used, agent }`. **Decision:** for our Activity module (stretch), READ FROM `events.jsonl` via our own SQLite indexer (per plan §3.2), NOT from upstream's activities-db. The upstream activities are openclaw-side and orthogonal to our knowledge-sync focus.

### Auth surface (current upstream)

`src/middleware.ts` does:
```typescript
function isAuthenticated(request: NextRequest): boolean {
  const authCookie = request.cookies.get("mc_auth");
  return !!(authCookie && authCookie.value === process.env.AUTH_SECRET);
}
```

- Cookie: `mc_auth`
- Compares against `process.env.AUTH_SECRET`
- Public routes: `/login`, `/api/auth/*`, `/api/health`
- No bcrypt, no jwt, no rate limit (despite the spec's mention; the rate limit is **not** in this codebase as of the discovery SHA)

**Plan delta for Task 3:** the rewrite is even smaller than assumed. We replace `isAuthenticated` with our `isAllowedAccessUser` (reading the `Cf-Access-Authenticated-User-Email` header) and update `PUBLIC_ROUTES` / `PUBLIC_API_PREFIXES` to drop `/login` and `/api/auth/`. Delete `src/app/api/auth/{login,logout}/` and `src/app/login/`.

### 3D Office surface

Two directories:
- `src/components/Office3D/` (uppercase) — 3D scene components
- `src/components/office/` (lowercase) — also exists; needs inspection
- `src/app/office/` — page route
- `src/app/api/office/` — API route (probably scene state)
- `public/models/` — `.glb` files

**Plan delta for Task 2:** delete `src/components/office/` AND `src/components/Office3D/` AND `src/app/office/` AND `src/app/api/office/`. Audit step needs to find imports of all four locations.

### Header / Nav components

`src/components/TenacitOS/`:
- `ActivityRow.tsx`, `AgentRow.tsx`, `CronRow.tsx` — list row components
- `Dock.tsx` — bottom dock
- `MetricCard.tsx` — metric card (used in dashboards)
- `SectionHeader.tsx` — section header
- `StatusBar.tsx` — status bar
- **`TopBar.tsx`** — the visible top bar (this is what Task 8 swaps)
- `index.ts` — barrel export

**Reusable for v1:** `Dock`, `StatusBar`, `MetricCard`, `SectionHeader`, `ActivityRow` (for the Critical Events widget on Home).
**Replaced:** `TopBar.tsx` → our `TopNavGrouped`.
**Defer:** `AgentRow`, `CronRow` (need E3 / read-only Cron later).

### Cost API real shape

`src/app/api/costs/route.ts`:
```typescript
const DB_PATH = path.join(process.cwd(), "data", "usage-tracking.db");
// GET /api/costs?timeframe=30d
// Returns: { today, yesterday, daily: [...], byAgent: [...], byModel: [...], ... }
```

**Plan deltas:**
- The widget URL was `/api/cost/today` — wrong. Real URL: `/api/costs?timeframe=1d`.
- The response shape is different from what the plan stub assumed (`{ total, delta }`). Real fields: `today`, `yesterday`, `daily[]`, `byAgent[]`, `byModel[]`. Update `CostTodayWidget` and `CostPage` accordingly.
- The DB path is `process.cwd()/data/usage-tracking.db`. When we run via systemd (Task 16), `process.cwd()` will be the repo root, so we need to ensure `data/usage-tracking.db` exists there. If OpenClaw writes its tracking elsewhere, we may need a symlink or env override. **Open question — flag for Task 5/16.**

---

## Plan deltas required (apply BEFORE starting Tasks 1-15)

These deltas patch the plan inline before execution. Some are paths, some are decisions, some are added scope.

### Task 1 deltas

- **Add a step:** install vitest (`npm install -D vitest`) AFTER the `npm install` from upstream. The plan assumed vitest was already there.
- The upstream `package.json` already has `"name": "mission-control"` — **no rename needed**.
- Repo path: `~/code/mission-control/` ✓ (unchanged).

### Task 2 deltas

- Delete BOTH `src/components/Office3D/` AND `src/components/office/` (lowercase exists too).
- Delete `src/app/api/office/` in addition to `src/app/office/`.
- The audit grep in Step 1 needs to also catch `office` (lowercase), not just `Office3D`.

### Task 3 deltas

- Auth rewrite is **smaller** than assumed: the upstream `isAuthenticated` is a single 4-line function. Replace it inline; do not nuke the whole file.
- Public routes to keep clearing: `/api/health` should remain public (Cloudflare can ping it for health checks of the tunnel). Add `/api/health` to our public list.
- Delete `src/app/api/auth/login/` and `src/app/api/auth/logout/`.
- Delete `src/app/login/`.
- Drop `AUTH_SECRET` from `.env.local.example`; add `MC_ACCESS_ALLOWLIST` per plan.

### Task 5-7 deltas

- Confirm `src/lib/` exists in upstream and create `src/lib/bevox/` as a sibling (no conflict).
- Confirm `tests/` directory does NOT exist; we create it from scratch in Task 5.
- The `MC_DB_PATH` env var introduced in `events-db.ts` is fine; default `~/.openclaw/mission-control/events.db` is unchanged.

### Task 8 deltas

- The visible top bar to swap is `src/components/TenacitOS/TopBar.tsx` (confirmed). The layout file that uses it is in `src/app/(dashboard)/layout.tsx` — confirm this file's actual import statement before editing.
- `nav-config.ts` v1 default has 5 items (per plan revision). **Cost route is `/costs` (plural)**, not `/cost`. Update the entry:
  ```typescript
  { label: 'Cost', href: '/costs', group: 'suporte' },
  ```

### Task 9 deltas

- `git-last-commit/route.ts` ✓ — create our own targeting `bevox-knowledge`, do NOT depend on `/api/git`.
- `health/route.ts` ✓ — ours aggregates timers + snapshot freshness + KS state, distinct from upstream `/api/health`.
- `events/route.ts` ✓ — reads from our SQLite events index.

### Task 10 deltas

- `CostTodayWidget` — fetch URL is `/api/costs?timeframe=1d` (NOT `/api/cost/today`). Response shape: `{ today, yesterday, ... }`. Adjust the widget code accordingly:
  ```tsx
  fetch('/api/costs?timeframe=1d')
    .then(r => r.ok ? r.json() : null)
    .then(d => setData(d ? { total: d.today, delta: d.today - d.yesterday } : null))
  ```

### Task 12 deltas

- `(dashboard)/knowledge/page.tsx` — create new (does not exist upstream). No rename conflict.

### Task 13 deltas

- `(dashboard)/approvals/page.tsx` — create new. No conflict.

### Task 14 deltas

- `(dashboard)/health/page.tsx` — create new. The page can ALSO use upstream's `/api/system/monitor`, `/api/system/services`, `/api/system/stats` for the System sub-section, in addition to our `/api/bevox/health` for the timers/snapshots/watcher sub-sections.

### Task 15a deltas

- **Page route is `/costs` (plural)**, not `/cost`. The page already exists at `(dashboard)/costs/page.tsx` — instead of creating a new file, we EDIT the existing one to adopt our `ModuleStream` pattern, OR we leave it as-is and just link to it from the nav. Decision: **edit it to adopt the stream pattern** for visual consistency with the other modules.
- Fetch URL: `/api/costs?timeframe=1d` and `/api/costs?timeframe=7d` for the history section (timeframes are days; `timeframe=7d` gives the last 7 days of `daily[]`).

### Task 15b deltas (stretch)

- `(dashboard)/activity/page.tsx` already exists upstream and reads from `/api/activities` (which uses an internal `activities-db`, NOT `events.jsonl`).
- **Decision:** REPLACE the existing page with ours that reads from our SQLite index of `events.jsonl`. The upstream activities are openclaw-side and not aligned with our knowledge-sync focus. (Bernard can revisit later if he wants both feeds merged.)
- Or alternatively, ADD our route as `(dashboard)/ks-activity/` and leave the upstream untouched. **Recommended: replace.** Less surface, fewer concepts.

### Task 16 deltas

- The systemd unit's `ExecStart` should override the dev/start defaults to bind to `127.0.0.1`:
  ```
  ExecStart=/usr/bin/env node node_modules/next/dist/bin/next start -H 127.0.0.1 -p 4310
  ```
- The `/api/system/services` allowlist already includes `mission-control` — when our service is named `mission-control.service`, the upstream service control API will recognize it. (We don't expose mutation buttons in v1, but it's a nice future option.)

### Task 18 deltas

- Manual smoke test step "Force a fresh approval to test live integration" calls `bash ~/.openclaw/skills/knowledge-sync/scripts/canonical.sh commit ...`. **This will land in `events.jsonl` even if Bernard does not click the Telegram button** (because of the E1.1 bug — see `35_specs/2026-04-10-e1.1-fix-plugin-commands.md`). For the smoke test of MC v1, this is fine: the MC reads `events.jsonl` and shows the pending approval. To complete the flow, run `canonical approve` + `canonical execute` via CLI as we did in Plan B.

---

## Notes / surprises

1. **Upstream package name is already `mission-control`** — happy coincidence, no rename.
2. **Upstream auth is dramatically simpler than assumed** — single cookie check, no rate limit, no bcrypt.
3. **`/api/system/services` already lists `mission-control` in its allowlist** — fortuitous; it suggests the upstream author intended this to be deployed as a systemd service named exactly that.
4. **Upstream has 22 dashboard pages we don't need.** Decision: keep them dormant, don't link from our nav. Cleanup deferred to v1.5.
5. **No test runner in upstream.** vitest install added to Task 1.
6. **`/api/git` does multi-repo scanning under `OPENCLAW_DIR/workspace`** — does NOT cover `bevox-knowledge`. We build our own `bevox/git-last-commit` endpoint.
7. **`/api/activities` uses a separate SQLite (`activities-db`)**, not `events.jsonl`. Our Activity module reads from our own index — this is by design (knowledge-sync-focused), not a reuse opportunity.
8. **`process.cwd()/data/usage-tracking.db`** is the cost DB path. Open question: where does OpenClaw actually write its usage tracking? If our `process.cwd()` (the repo root) doesn't have `data/usage-tracking.db`, the Cost page will return zeros until we link/symlink/configure it. Flag for Task 5 (where we set up `paths.ts`).
9. **`dev/start` scripts bind to 0.0.0.0** — security risk if exposed without firewall. We override to `127.0.0.1` in the systemd unit. Add to deploy README explicitly.
10. **2 dirs of 3D code** (`Office3D` uppercase + `office` lowercase) instead of 1. Audit needs to catch both.

---

## Open questions (do not block Task 1, but resolve before relevant task)

| Question | Block | When to resolve |
|---|---|---|
| Where does OpenClaw write its `usage-tracking.db`? | Task 15a / Cost widget functionality | Before Task 10 (Home widget for cost) |
| Does upstream have a `src/lib/activities-db.ts` we should remove or leave dormant? | Task 15b | Before Task 15b (stretch — non-blocking) |
| Does the layout file at `src/app/(dashboard)/layout.tsx` exist or is the nav rendered elsewhere? | Task 8 | Before Task 8 (a quick `ls` check) |
| Do any of the 18 dormant pages have shared imports from `Office3D` or `office`? | Task 2 (3D removal might break dormant pages) | During Task 2 audit step |

---

## Next step

The findings above modify the path of multiple tasks but **not the structure of the plan**. Apply the deltas inline to `~/.openclaw/docs/superpowers/plans/2026-04-10-e2-mission-control.md` per Step 10 of Task 0.5, then proceed to Task 1.

Total deltas to apply: **~15 inline edits across Tasks 1-18**, all small (path corrections, URL strings, decision notes). No new tasks needed; no task removed.
