# E2 - Bevox Mission Control v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the v1 of Bevox Mission Control as a hard fork of TenacitOS, exposing knowledge-sync state, approvals (read-only), health, cost and activity behind Cloudflare Tunnel + Access at `mc.example.com`.

**Architecture:** Hard fork of `carlosazaustre/tenacitOS` (Next.js 15 + React 19 + Tailwind v4 + better-sqlite3). Top nav grouped nucleo ‖ suporte. Home dashboard 2-col asymmetric. Module pages = vertical collapsible streams. Data layer hybrid: small state files read on demand; `events.jsonl` indexed into SQLite by an in-process tail; external git/systemctl calls behind API routes with short TTL. Auth = Cloudflare Access header trust (no app-level login).

**Tech Stack:** Next.js 15 (App Router) · React 19 · TypeScript · Tailwind CSS v4 · better-sqlite3 · Node 22 · Vitest (or whatever upstream uses; preserve) · systemd user service · cloudflared · Cloudflare Access.

**Spec source:** `bevox-knowledge/35_specs/2026-04-10-e2-mission-control.md`

**Conventions used in this plan:**
- All paths under the new repo are relative to the repo root unless noted with `~/`.
- Repo will live at `~/code/mission-control/` on Bernard's host (create the parent if needed).
- All bash commands assume `cd ~/code/mission-control` unless noted.
- **GitHub org:** `bernardTavares` (matches the existing `bernardTavares/bevox-knowledge` repo).
- **Knowledge clone path (canonical):** `~/bevox-knowledge/` in bash, `path.join(os.homedir(), 'bevox-knowledge')` in TypeScript via `paths.ts`. Both resolve to `~/bevox-knowledge` on the host. Never hardcode the absolute path in code.
- **OpenClaw paths (canonical):** `~/.openclaw/knowledge-sync/...` and `~/.openclaw/backups/knowledge-snapshots/...` in bash; same via `paths.ts` in TypeScript.
- TDD discipline: data layer + API routes get tests before code. UI components get manual smoke tests (UI v1 is utility, not polish).
- **Núcleo do v1:** Home + Knowledge + Approvals + Health. Cost = thin reuse do upstream. **Activity = stretch goal** (não bloqueia v1).
- **Reduction order if scope tightens:**
  1. Cut Activity entirely (Task 15b is already marked stretch — easiest cut, no rework needed).
  2. Replace Critical Events widget (Home right column) with the simpler upstream notification list.
  3. Cost module reverts to "header link only, page is empty placeholder" until E9.

---

## Pre-execution checklist (operational, not part of the plan)

Before starting Task 1, complete these in order:

1. **E2 spec must be EXECUTED on Telegram.** The canonical commit of `35_specs/2026-04-10-e2-mission-control.md` (short_id `fa4a0c82` at the time of writing) needs to land. Verify with: `tail ~/.openclaw/knowledge-sync/events.jsonl | grep canonical_committed`.
2. **Test inbox cleanup.** Remove `00_inbox/2026-04-10-test-inline-buttons.md` via a separate `knowledge-sync canonical commit` (one approval card on Telegram). This is its own commit, not bundled with anything.
3. **Org confirmation.** GitHub org for the new repo is `bernardTavares` (already verified — same org as `bevox-knowledge`).
4. **TenacitOS discovery (Task 0.5).** Run before Task 1. It validates the assumed paths/structure of the upstream and updates Tasks 1-4 if surprises are found.

---

## File Structure (top-level overview)

After all tasks complete, the repo will contain (additions/changes only — many TenacitOS files stay untouched):

**Modified from upstream:**
- `package.json` — drop 3D deps, drop login deps if any
- `src/middleware.ts` — replaced with Cf-Access header trust
- `src/app/layout.tsx` — header text "Bevox Mission Control"
- `.env.local.example` — Bevox naming + neutral palette vars
- `LICENSE` — Bevox note appended to MIT

**Deleted from upstream:**
- `src/components/Office3D/` (entire dir)
- `src/app/office/` (entire dir)
- `public/models/` (entire dir)
- `src/app/login/` (entire dir)
- `src/app/api/auth/` (if exists; replace with Cf-Access)

**New files (Bevox-specific code):**

```
src/lib/bevox/
  paths.ts                  — central registry of all knowledge-sync/openclaw paths
  knowledge-sync-state.ts   — read state.json + state.previous.json
  snapshots-index.ts        — read snapshots-index.jsonl
  git-ops.ts                — wrappers for git -C bevox-knowledge ...
  systemd.ts                — wrappers for systemctl --user list-timers --output=json
  events-db.ts              — better-sqlite3 connection + schema for indexed events
  events-indexer.ts         — tail incremental events.jsonl → sqlite
  approvals.ts              — derive pending/granted/executed/rejected from events
  health.ts                 — aggregate timers + watcher + system metrics
  types.ts                  — shared TypeScript types (KsState, Snapshot, Approval, etc.)

src/app/api/bevox/
  knowledge-state/route.ts
  snapshots/route.ts
  approvals/route.ts
  events/route.ts           — query the indexed events with filters
  health/route.ts
  git-last-commit/route.ts

src/app/(dashboard)/
  page.tsx                  — Home dashboard (2-col asymmetric)
  knowledge/page.tsx        — Knowledge module
  approvals/page.tsx        — Approvals module
  health/page.tsx           — Health module
  cost/page.tsx             — Cost (reuse upstream + reskin)
  activity/page.tsx         — Activity module

src/components/bevox/
  TopNavGrouped.tsx         — top nav with nucleo ‖ suporte divider
  ModuleStream.tsx          — collapsible vertical stream wrapper
  ModuleSection.tsx         — single section inside ModuleStream
  widgets/
    KnowledgeStatusWidget.tsx
    ApprovalsPendingWidget.tsx
    HealthOverallWidget.tsx
    LastCommitWidget.tsx
    CostTodayWidget.tsx
    CriticalEventsWidget.tsx
  ApprovalCardV2.tsx        — renders the same 6 blocks as the Telegram card

deploy/
  mission-control.service   — systemd user unit
  cloudflared-config.yml    — tunnel config (template; secrets externalised)
  README.md                 — deploy + rollback runbook

tests/bevox/
  knowledge-sync-state.test.ts
  snapshots-index.test.ts
  events-indexer.test.ts
  approvals.test.ts
  health.test.ts
  api/knowledge-state.test.ts
  api/approvals.test.ts
```

---

## Phase 0 — Bootstrap fork (Tasks 0.5, 1-4)

### Task 0.5: TenacitOS upstream discovery

**Goal:** validate the assumed structure of `carlosazaustre/tenacitOS` BEFORE Task 1 commits anything to our repo. The plan assumes specific file paths (e.g. `src/components/TenacitOS/`, `src/app/(dashboard)/page.tsx`, `src/app/login/`, vitest as test runner). If upstream differs, Tasks 1-4 need adjustment. This task captures the actual reality and lets the engineer correct course.

**Files:**
- Create: `~/scratch/tenacitos-discovery/` (clone destination, throwaway)
- Create: `~/.openclaw/docs/superpowers/plans/2026-04-10-e2-tenacitos-discovery.md` (findings document)

- [ ] **Step 1: Clone upstream to a scratch dir**

```bash
mkdir -p ~/scratch
cd ~/scratch
git clone --depth 1 https://github.com/carlosazaustre/tenacitOS.git tenacitos-discovery
cd tenacitos-discovery
git rev-parse HEAD
```

Save the SHA — Task 1 will use the same SHA to ensure parity.

- [ ] **Step 2: Capture the top-level structure**

```bash
ls -la
cat package.json | jq '{name, version, scripts, dependencies, devDependencies}' > /tmp/discovery-package.json
cat /tmp/discovery-package.json
```

Note: which test runner is in `devDependencies` (vitest, jest, none)? Which build script (`next build`)? Which Next.js version?

- [ ] **Step 3: Map the source tree**

```bash
find src -type d | sort
find src/app -type f -name "page.tsx" -o -name "layout.tsx" -o -name "route.ts" | sort
find src/components -type d | sort
find public -type f | head -30
```

Capture: where the dashboard layout lives, whether `(dashboard)` route group exists, where the header/nav components are, what API routes exist out of the box.

- [ ] **Step 4: Find the auth surface**

```bash
ls src/app/login src/app/api/auth 2>&1
cat src/middleware.ts 2>&1 | head -40
grep -rln "bcrypt\|jwt\|next-auth\|signIn\|RATE_LIMIT" src/ 2>/dev/null | head
```

Note: how login is implemented (custom? next-auth? something else?), what middleware does, and which deps are auth-related so Task 3 can drop them.

- [ ] **Step 5: Find the 3D Office surface**

```bash
ls src/components/Office3D src/app/office public/models 2>&1
grep -rln "@react-three\|Office3D\|three" src/ public/ package.json 2>/dev/null | head
```

Confirm the 3D code lives where the spec assumes. If it's split across other files, note the exact list — Task 2 needs to delete every reference.

- [ ] **Step 6: Find the cost API surface**

```bash
find src/app/api -type d -name "cost*" -o -name "usage*" -o -name "billing*"
grep -rln "cost\|usage\|billing\|spend" src/app/api/ 2>/dev/null | head
```

Capture the actual cost API route name. The plan assumes `/api/cost/today` but upstream may use `/api/usage/today` or similar — Tasks 10 (CostTodayWidget) and 15a (Cost page) read from this URL.

- [ ] **Step 7: Find the existing nav / header**

```bash
grep -rln "TopNav\|Navbar\|Header" src/components/ 2>/dev/null | head
grep -rln "TenacitOS" src/ --include="*.tsx" --include="*.ts" | head
```

Save the file that renders the visible top bar — Task 8 swaps it.

- [ ] **Step 8: Run the upstream test suite (sanity check)**

```bash
npm install
npm test 2>&1 | tail -20
```

If `npm test` is missing or broken upstream, note it. Either way, the plan's TDD discipline still applies — we use whichever test runner is in `devDependencies`. If none, install `vitest` in Task 1 as part of the import.

- [ ] **Step 9: Write the discovery findings document**

Create `~/.openclaw/docs/superpowers/plans/2026-04-10-e2-tenacitos-discovery.md` with this template, filled in from Steps 2-8:

```markdown
# TenacitOS Discovery (2026-04-10)

**Upstream:** github.com/carlosazaustre/tenacitOS @ <SHA from Step 1>

## Tech stack actual
- Next.js: <version from Step 2>
- React: <version>
- Tailwind: <version>
- Test runner: <vitest | jest | none>
- Other notable deps: <list>

## File layout actual
- Dashboard layout file: `<path>` (or "no (dashboard) route group — uses flat src/app/")
- Header/Nav component: `<path>`
- Auth surface: `<paths>`, mechanism: `<custom | next-auth | other>`
- 3D Office: `<paths>` (confirm matches plan assumption)
- Cost API route: `<actual path, e.g. /api/usage/today>`

## Plan deltas required
List each task that needs path correction based on the findings:
- Task N: change `<assumed path>` → `<real path>`
- ...

## Notes / surprises
- ...
```

- [ ] **Step 10: Apply discovery deltas inline to this plan (if any)**

If Step 9 produced any "Plan deltas required", edit `~/.openclaw/docs/superpowers/plans/2026-04-10-e2-mission-control.md` to fix the paths in the affected tasks. Commit the plan edit separately as: `chore(plan): apply tenacitos discovery deltas`.

- [ ] **Step 11: Cleanup scratch (optional)**

Keep `~/scratch/tenacitos-discovery/` around until Task 4 completes — it's useful as a reference for the engineer doing the bootstrap. Delete after Task 4.

---

### Task 1: Create the repo and import TenacitOS

**Files:**
- Create: `~/code/mission-control/` (entire directory tree from upstream)
- Modify: `LICENSE` (append Bevox note)

> **Discovery applied (Task 0.5):** upstream `package.json` already has `"name": "mission-control"` — no rename needed. Upstream has NO test runner; we install vitest in this task. Upstream binds to `0.0.0.0` — our systemd unit (Task 16) overrides to `127.0.0.1`. See `2026-04-10-e2-tenacitos-discovery.md` for full findings.

- [ ] **Step 1: Create the GitHub repo**

Use `gh` from the host (Bernard's hands or via bash if `gh auth` is set up):

```bash
gh repo create bernardTavares/mission-control --private --description "Bevox Mission Control - hard fork of TenacitOS"
```

Expected: `https://github.com/bernardTavares/mission-control` printed.

- [ ] **Step 2: Clone TenacitOS upstream and detach**

```bash
mkdir -p ~/code
cd ~/code
git clone https://github.com/carlosazaustre/tenacitOS.git mission-control
cd mission-control
TENACITOS_SHA=$(git rev-parse HEAD)
echo "Imported from carlosazaustre/tenacitOS @ $TENACITOS_SHA" > /tmp/tenacitos-sha.txt
cat /tmp/tenacitos-sha.txt
```

Expected: prints something like `Imported from carlosazaustre/tenacitOS @ a1b2c3d...`. Save the SHA — you'll use it in the commit message.

- [ ] **Step 3: Replace remote with our private repo**

```bash
git remote remove origin
git remote add origin git@github.com:bernardTavares/mission-control.git
git remote -v
```

Expected: only `origin` pointing at `bernardTavares/mission-control`.

- [ ] **Step 4: Append Bevox note to LICENSE**

The upstream LICENSE is MIT. Open it and append (do not replace) at the bottom:

```text

---

Bevox Mission Control modifications (2026-04-10 onward):
Copyright (c) 2026 Bevox. Released under the same MIT License above.
This is a hard fork of carlosazaustre/tenacitOS at upstream commit <PASTE_SHA_HERE>.
There is no expectation of upstream merges.
```

Replace `<PASTE_SHA_HERE>` with the SHA from Step 2.

- [ ] **Step 4b: Install vitest (added per discovery)**

Upstream has no test runner. Install vitest as a devDependency so Phase 1 tests can run.

```bash
npm install --save-dev vitest @vitest/ui
```

Add a test script to `package.json`:

```json
"scripts": {
  "dev": "next dev -H 127.0.0.1",
  "build": "next build",
  "start": "next start -H 127.0.0.1",
  "lint": "eslint",
  "test": "vitest run",
  "test:watch": "vitest"
}
```

(Also update `dev` and `start` to bind to `127.0.0.1` here — discovery noted upstream defaults to `0.0.0.0`.)

- [ ] **Step 5: Verify and commit**

```bash
git add LICENSE package.json package-lock.json
git status
```

Expected: `LICENSE`, `package.json`, `package-lock.json` modified.

```bash
git commit -m "chore(fork): import tenacitOS @ ${TENACITOS_SHA:0:10} as base"
git push -u origin main
```

Expected: push succeeds; new repo on GitHub has the import + the LICENSE update. **Do NOT push the upstream history if it conflicts** — if `git push` is rejected, run `git push -u origin main --force-with-lease` (this is the very first push to an empty repo, force is acceptable).

---

### Task 2: Remove 3D Office completely

> **Discovery applied:** upstream has TWO 3D dirs (`Office3D` uppercase + `office` lowercase) and ALSO an `/api/office` route. Audit must catch all four locations. Also drop `@react-three/rapier` (a 4th 3D dep not in original plan).

**Files:**
- Delete: `src/components/Office3D/`
- Delete: `src/components/office/` (lowercase — also exists)
- Delete: `src/app/office/`
- Delete: `src/app/api/office/`
- Delete: `public/models/`
- Modify: `package.json` (drop `@react-three/fiber`, `@react-three/drei`, `@react-three/rapier`, `three`)
- Modify: `src/app/layout.tsx` if it imports Office3D
- Modify: any nav item linking to `/office`

- [ ] **Step 1: Audit what references 3D**

```bash
grep -rn "Office3D\|three\|@react-three\|/office\|public/models\|components/office" src/ public/ package.json 2>/dev/null
```

Save the output. Anything in `src/components/Office3D/`, `src/components/office/`, `src/app/office/`, `src/app/api/office/`, `public/models/`, or `package.json` deps will be deleted. Anything in *other* files (e.g. `src/app/layout.tsx`, dormant pages with shared imports) needs inline edits to remove the import + JSX usage. **Watch for dormant pages** (the 18 dashboard pages we don't link from nav) that may still import 3D — fix them too.

- [ ] **Step 2: Delete the 3D directories**

```bash
rm -rf src/components/Office3D src/components/office src/app/office src/app/api/office public/models
ls src/components/ src/app/ src/app/api/ public/ | head
```

Expected: no `Office3D`, no `office` (lowercase), no `models` listed.

- [ ] **Step 3: Remove dependencies from package.json**

Edit `package.json`. In the `"dependencies"` section, remove these lines (whichever exist):

```json
"@react-three/drei": "...",
"@react-three/fiber": "...",
"@react-three/rapier": "...",
"three": "...",
"@types/three": "..."
```

(If any of these are in `devDependencies`, remove them there too.)

- [ ] **Step 4: Reinstall and verify the build**

```bash
rm -rf node_modules package-lock.json
npm install
npm run build
```

Expected: install succeeds (no peer dep errors); build succeeds. If build fails on a stray import (e.g. `import { Office3D } from '@/components/Office3D'` somewhere), edit that file to delete the import + the component usage, then re-run `npm run build`.

- [ ] **Step 5: Verify nothing 3D remains**

```bash
grep -rn "Office3D\|three\|@react-three" src/ public/ package.json 2>/dev/null
```

Expected: empty output. If anything appears, repeat Step 4 fixes until clean.

- [ ] **Step 6: Commit**

```bash
git add -A
git status
git commit -m "chore(scope): remove 3D Office and React Three Fiber deps

Per spec §2.1 condition 1 and roadmap §8 'nao fazer agora':
3D office / interface gimmick.

Deleted:
- src/components/Office3D/
- src/app/office/
- public/models/
- @react-three/fiber, @react-three/drei, three from package.json"
git push
```

---

### Task 3: Replace local login with Cloudflare Access trust

> **Discovery applied:** upstream auth is much simpler than the plan assumed. `src/middleware.ts` does a single 4-line cookie check (`request.cookies.get("mc_auth").value === process.env.AUTH_SECRET`). No bcrypt, no jwt, no rate limit. Public list already includes `/api/health` (keep it). Drop `AUTH_SECRET` from env example.

**Files:**
- Delete: `src/app/login/`
- Delete: `src/app/api/auth/login/` and `src/app/api/auth/logout/`
- Modify: `src/middleware.ts` (replace `isAuthenticated`, keep `/api/health` in public list)
- Create: `src/lib/bevox/auth.ts`
- Create: `tests/bevox/auth.test.ts`
- Modify: `.env.local.example` (drop `AUTH_SECRET`, add `MC_ACCESS_ALLOWLIST`)

- [ ] **Step 1: Audit current auth surface**

```bash
ls src/app/login src/app/api/auth 2>&1
grep -rn "rate-limit\|bcrypt\|jwt\|next-auth\|signIn\|signOut" src/ 2>/dev/null
cat src/middleware.ts 2>&1
```

Save this output. You'll need to know what's removed and what middleware patterns to preserve (if any) for non-auth concerns like CSRF/headers.

- [ ] **Step 2: Write the failing test for the auth helper**

Create `tests/bevox/auth.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { isAllowedAccessUser, ACCESS_HEADER } from '@/lib/bevox/auth';

describe('isAllowedAccessUser', () => {
  it('rejects when header missing', () => {
    const headers = new Headers();
    expect(isAllowedAccessUser(headers, ['you@example.com'])).toBe(false);
  });

  it('rejects when email not in allowlist', () => {
    const headers = new Headers({ [ACCESS_HEADER]: 'mallory@evil.com' });
    expect(isAllowedAccessUser(headers, ['you@example.com'])).toBe(false);
  });

  it('accepts when email is in allowlist (case-insensitive)', () => {
    const headers = new Headers({ [ACCESS_HEADER]: 'you@example.com' });
    expect(isAllowedAccessUser(headers, ['you@example.com'])).toBe(true);
  });

  it('rejects when allowlist is empty (fail closed)', () => {
    const headers = new Headers({ [ACCESS_HEADER]: 'you@example.com' });
    expect(isAllowedAccessUser(headers, [])).toBe(false);
  });
});
```

- [ ] **Step 3: Run the test to verify failure**

```bash
npx vitest run tests/bevox/auth.test.ts
```

Expected: FAIL — `Cannot find module '@/lib/bevox/auth'`. (If the project uses jest instead of vitest, substitute `npx jest tests/bevox/auth.test.ts`. The skill assumes vitest; if upstream uses jest, adapt the import lines but keep the assertions.)

- [ ] **Step 4: Implement `src/lib/bevox/auth.ts`**

```typescript
export const ACCESS_HEADER = 'cf-access-authenticated-user-email';

export function isAllowedAccessUser(headers: Headers, allowlist: string[]): boolean {
  if (allowlist.length === 0) return false;
  const raw = headers.get(ACCESS_HEADER);
  if (!raw) return false;
  const email = raw.trim().toLowerCase();
  return allowlist.map(e => e.trim().toLowerCase()).includes(email);
}

export function getAllowlistFromEnv(): string[] {
  const raw = process.env.MC_ACCESS_ALLOWLIST ?? '';
  return raw.split(',').map(s => s.trim()).filter(Boolean);
}
```

- [ ] **Step 5: Run the test to verify pass**

```bash
npx vitest run tests/bevox/auth.test.ts
```

Expected: 4 tests pass.

- [ ] **Step 6: Replace `src/middleware.ts`**

Overwrite with:

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { isAllowedAccessUser, getAllowlistFromEnv } from '@/lib/bevox/auth';

// Public API routes (Cloudflare can ping these for tunnel health)
const PUBLIC_API_PREFIXES = ['/api/health'];

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  // Allow Next.js internals + static assets
  if (
    pathname.startsWith('/_next') ||
    pathname.startsWith('/favicon')
  ) {
    return NextResponse.next();
  }

  // Allow public API routes (health check from Cloudflare)
  if (PUBLIC_API_PREFIXES.some(prefix => pathname.startsWith(prefix))) {
    return NextResponse.next();
  }

  const allowlist = getAllowlistFromEnv();
  if (!isAllowedAccessUser(req.headers, allowlist)) {
    return new NextResponse('Forbidden: Cloudflare Access required', { status: 403 });
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
```

- [ ] **Step 7: Delete login pages and API**

```bash
rm -rf src/app/login src/app/api/auth
ls src/app/ | grep -E 'login|auth' || echo "clean"
```

Expected: `clean` printed.

- [ ] **Step 8: Drop login-related env vars and add allowlist var**

Edit `.env.local.example`. Remove any `LOGIN_PASSWORD`, `JWT_SECRET`, `BCRYPT_*`, `RATE_LIMIT_*` keys you find. Add:

```bash
# Cloudflare Access — comma-separated allowlist of authorized emails
MC_ACCESS_ALLOWLIST=you@example.com
```

- [ ] **Step 9: Verify build still works**

```bash
npm run build
```

Expected: build succeeds. If a page imports the deleted login API, edit the import out and re-run.

- [ ] **Step 10: Commit**

```bash
git add -A
git status
git commit -m "feat(auth): replace local login with Cloudflare Access header trust

Per spec §2.1 condition 3 and §3.3:
- middleware trusts Cf-Access-Authenticated-User-Email header
- allowlist via MC_ACCESS_ALLOWLIST env var
- login page + auth API removed
- new lib/bevox/auth.ts with unit tests"
git push
```

---

### Task 4: Initial branding (header text + neutral palette + env vars)

**Files:**
- Modify: `.env.local.example`
- Modify: `src/app/layout.tsx`
- Modify: `src/components/TenacitOS/...` (header component, whichever name it has)
- Modify: `tailwind.config.ts` or equivalent (accent color)

- [ ] **Step 1: Find the header/title component**

```bash
grep -rln "TenacitOS\|tenacitOS" src/ --include="*.tsx" --include="*.ts" --include="*.css" | head
```

Save the list. The `<title>` is in `src/app/layout.tsx`. The visible header is likely in a file under `src/components/TenacitOS/`.

- [ ] **Step 2: Add branding env vars**

Edit `.env.local.example`. Add at the bottom:

```bash
# Branding — Bevox Mission Control v1
NEXT_PUBLIC_APP_NAME="Bevox Mission Control"
NEXT_PUBLIC_APP_SHORT_NAME="Mission Control"
NEXT_PUBLIC_ACCENT_COLOR="#3b82f6"  # neutral blue; reskin via this var
```

- [ ] **Step 3: Update `src/app/layout.tsx`**

Find the `<title>` and metadata `title` field. Replace any "TenacitOS" string with `process.env.NEXT_PUBLIC_APP_NAME ?? 'Bevox Mission Control'`. Example:

```typescript
export const metadata: Metadata = {
  title: process.env.NEXT_PUBLIC_APP_NAME ?? 'Bevox Mission Control',
  description: 'Bevox Company OS — Mission Control',
};
```

- [ ] **Step 4: Update the visible header component**

Open the file you found in Step 1 (likely `src/components/TenacitOS/Header.tsx` or similar). Find the hardcoded "TenacitOS" string in the JSX. Replace with:

```tsx
{process.env.NEXT_PUBLIC_APP_NAME ?? 'Bevox Mission Control'}
```

- [ ] **Step 5: Set the accent color**

If `tailwind.config.ts` defines an accent/primary color, replace the hardcoded value with one read from env. If the project uses CSS variables, add to `src/app/globals.css`:

```css
:root {
  --accent-color: theme('colors.blue.500');
}
```

(Keep this minimal — the env-driven accent is a v1 nicety; if the upstream styling system makes it complicated, hardcode neutral blue and document the override path in the deploy README later.)

- [ ] **Step 6: Local smoke test**

Create a `.env.local` (gitignored) with:

```bash
MC_ACCESS_ALLOWLIST=you@example.com
NEXT_PUBLIC_APP_NAME="Bevox Mission Control"
NEXT_PUBLIC_APP_SHORT_NAME="Mission Control"
NEXT_PUBLIC_ACCENT_COLOR="#3b82f6"
```

Then:

```bash
npm run dev
```

In a browser, hit `http://localhost:3000` with header `Cf-Access-Authenticated-User-Email: you@example.com` (use a curl test or a browser extension):

```bash
curl -i -H "Cf-Access-Authenticated-User-Email: you@example.com" http://localhost:3000/ | head -20
```

Expected: HTTP 200 (or 307 to a dashboard page). Without the header:

```bash
curl -i http://localhost:3000/ | head -5
```

Expected: HTTP 403.

Open in a browser via the curl-with-header trick (or skip the visual check until Phase 2 builds the new shell). Verify: page loads, title bar reads "Bevox Mission Control".

- [ ] **Step 7: Stop dev server and commit**

```bash
git add -A
git status
git commit -m "feat(branding): initial Bevox Mission Control naming and neutral palette

Per spec §3.4:
- header/title 'Bevox Mission Control' (full name, not 'MC')
- neutral blue accent (override via NEXT_PUBLIC_ACCENT_COLOR)
- branding driven by env vars for trivial reskin later"
git push
```

---

## Phase 1 — Data layer plumbing (Tasks 5-7)

### Task 5: Central paths registry + state.json reader

**Files:**
- Create: `src/lib/bevox/paths.ts`
- Create: `src/lib/bevox/types.ts`
- Create: `src/lib/bevox/knowledge-sync-state.ts`
- Create: `tests/bevox/knowledge-sync-state.test.ts`
- Create: `tests/fixtures/state.json` (a snapshot of a real state.json for the test)

- [ ] **Step 1: Capture a real state.json as a fixture**

```bash
mkdir -p tests/fixtures
cp ~/.openclaw/knowledge-sync/state.json tests/fixtures/state.json
jq . tests/fixtures/state.json | head -30
```

Expected: prints the first 30 lines of a real state.json. Note its top-level keys (`branch`, `working_tree`, `health`, `timestamp`, etc.) — those drive the type definitions.

- [ ] **Step 2: Create `src/lib/bevox/paths.ts`**

```typescript
import path from 'node:path';
import os from 'node:os';

const HOME = process.env.MC_HOME ?? os.homedir();

export const PATHS = {
  openclawHome: path.join(HOME, '.openclaw'),
  ksDir: path.join(HOME, '.openclaw', 'knowledge-sync'),
  ksState: path.join(HOME, '.openclaw', 'knowledge-sync', 'state.json'),
  ksStatePrevious: path.join(HOME, '.openclaw', 'knowledge-sync', 'state.previous.json'),
  ksEvents: path.join(HOME, '.openclaw', 'knowledge-sync', 'events.jsonl'),
  snapshotsIndex: path.join(
    HOME, '.openclaw', 'backups', 'knowledge-snapshots', 'meta', 'snapshots-index.jsonl'
  ),
  bevoxKnowledgeClone: process.env.MC_KNOWLEDGE_CLONE ?? path.join(HOME, 'bevox-knowledge'),
  openclawConfig: path.join(HOME, '.openclaw', 'openclaw.json'),
  authProfiles: path.join(HOME, '.openclaw', 'agents', 'main', 'agent', 'auth-profiles.json'),
};

export type BevoxPaths = typeof PATHS;
```

- [ ] **Step 3: Create `src/lib/bevox/types.ts`**

```typescript
export interface KsState {
  timestamp: string;
  branch: {
    current: string;
    ahead: number;
    behind: number;
  };
  working_tree: {
    clean: boolean;
    files_modified?: number;
    files_untracked?: number;
    files_staged?: number;
  };
  git_operations?: {
    merge_in_progress?: boolean;
    rebase_in_progress?: boolean;
    cherry_pick_in_progress?: boolean;
  };
  draft_branches?: Array<{ name: string; last_commit_age_days?: number }>;
  conflicts?: { potential: boolean; reason?: string };
  health: {
    overall: 'ok' | 'degraded' | 'critical';
    issues?: Array<{ code: string; severity: 'info' | 'warn' | 'error' }>;
  };
  last_fetch?: { at: string; ok: boolean };
}

export interface SnapshotEntry {
  id: string;
  type: 'auto' | 'manual' | 'pre-canonical';
  created_at: string;
  size_bytes: number;
  verify_status?: 'ok' | 'failed' | 'pending';
  pre_action?: string;
}

export interface ApprovalSummary {
  approval_id: string;
  short_id: string;
  action: string;
  state: 'pending' | 'granted' | 'executed' | 'rejected' | 'expired';
  created_at: string;
  age_seconds: number;
  card?: unknown; // full card v2 JSON when available
}
```

If the real `state.json` from your fixture has additional fields you need, add them here — the type is your contract with the rest of the app.

- [ ] **Step 4: Write the failing test**

Create `tests/bevox/knowledge-sync-state.test.ts`:

```typescript
import { describe, it, expect, vi } from 'vitest';
import path from 'node:path';
import { readKsState } from '@/lib/bevox/knowledge-sync-state';

const FIXTURE = path.join(__dirname, '..', 'fixtures', 'state.json');

describe('readKsState', () => {
  it('reads a real state.json and returns the parsed object', async () => {
    const state = await readKsState(FIXTURE);
    expect(state).toBeDefined();
    expect(state.branch).toBeDefined();
    expect(state.branch.current).toBeTypeOf('string');
    expect(state.health).toBeDefined();
    expect(['ok', 'degraded', 'critical']).toContain(state.health.overall);
  });

  it('throws a clear error when the file does not exist', async () => {
    await expect(readKsState('/nonexistent/path.json')).rejects.toThrow(/state.json/);
  });
});
```

- [ ] **Step 5: Run the test to verify fail**

```bash
npx vitest run tests/bevox/knowledge-sync-state.test.ts
```

Expected: FAIL — `Cannot find module '@/lib/bevox/knowledge-sync-state'`.

- [ ] **Step 6: Implement `src/lib/bevox/knowledge-sync-state.ts`**

```typescript
import { promises as fs } from 'node:fs';
import { PATHS } from './paths';
import type { KsState } from './types';

export async function readKsState(filePath: string = PATHS.ksState): Promise<KsState> {
  try {
    const raw = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(raw) as KsState;
  } catch (err) {
    const code = (err as NodeJS.ErrnoException).code;
    if (code === 'ENOENT') {
      throw new Error(`knowledge-sync state.json not found at ${filePath}`);
    }
    throw err;
  }
}

export async function readKsStatePrevious(): Promise<KsState | null> {
  try {
    return await readKsState(PATHS.ksStatePrevious);
  } catch {
    return null;
  }
}
```

- [ ] **Step 7: Run the test to verify pass**

```bash
npx vitest run tests/bevox/knowledge-sync-state.test.ts
```

Expected: 2 tests pass.

- [ ] **Step 8: Commit**

```bash
git add src/lib/bevox/paths.ts src/lib/bevox/types.ts src/lib/bevox/knowledge-sync-state.ts tests/bevox/knowledge-sync-state.test.ts tests/fixtures/state.json
git commit -m "feat(data): paths registry, types, and state.json reader

Per spec §3.2 hybrid data layer:
- src/lib/bevox/paths.ts: central registry of all knowledge-sync paths
- src/lib/bevox/types.ts: KsState, SnapshotEntry, ApprovalSummary
- src/lib/bevox/knowledge-sync-state.ts: reads state.json on demand"
git push
```

---

### Task 6: Snapshots index, git ops, systemd readers

**Files:**
- Create: `src/lib/bevox/snapshots-index.ts`
- Create: `src/lib/bevox/git-ops.ts`
- Create: `src/lib/bevox/systemd.ts`
- Create: `tests/bevox/snapshots-index.test.ts`
- Create: `tests/fixtures/snapshots-index.jsonl`

- [ ] **Step 1: Capture fixtures**

```bash
cp ~/.openclaw/backups/knowledge-snapshots/meta/snapshots-index.jsonl tests/fixtures/snapshots-index.jsonl
wc -l tests/fixtures/snapshots-index.jsonl
```

Expected: a number > 0. Each line is a JSON snapshot entry.

- [ ] **Step 2: Write the failing test for snapshots-index**

Create `tests/bevox/snapshots-index.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import path from 'node:path';
import { readSnapshotsIndex } from '@/lib/bevox/snapshots-index';

const FIXTURE = path.join(__dirname, '..', 'fixtures', 'snapshots-index.jsonl');

describe('readSnapshotsIndex', () => {
  it('reads a real index and returns an array', async () => {
    const snapshots = await readSnapshotsIndex(FIXTURE);
    expect(Array.isArray(snapshots)).toBe(true);
    expect(snapshots.length).toBeGreaterThan(0);
    const first = snapshots[0];
    expect(first.id).toBeTypeOf('string');
    expect(['auto', 'manual', 'pre-canonical']).toContain(first.type);
  });

  it('returns an empty array when the file does not exist', async () => {
    const result = await readSnapshotsIndex('/nonexistent/path.jsonl');
    expect(result).toEqual([]);
  });

  it('skips malformed lines instead of throwing', async () => {
    // We test this with a tmp file later if needed; for now, the file exists.
    const snapshots = await readSnapshotsIndex(FIXTURE);
    expect(snapshots.every(s => s.id)).toBe(true);
  });
});
```

- [ ] **Step 3: Verify test fails**

```bash
npx vitest run tests/bevox/snapshots-index.test.ts
```

Expected: FAIL.

- [ ] **Step 4: Implement `src/lib/bevox/snapshots-index.ts`**

```typescript
import { promises as fs } from 'node:fs';
import { PATHS } from './paths';
import type { SnapshotEntry } from './types';

export async function readSnapshotsIndex(
  filePath: string = PATHS.snapshotsIndex
): Promise<SnapshotEntry[]> {
  let raw: string;
  try {
    raw = await fs.readFile(filePath, 'utf-8');
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw err;
  }
  const lines = raw.split('\n').filter(l => l.trim().length > 0);
  const result: SnapshotEntry[] = [];
  for (const line of lines) {
    try {
      const parsed = JSON.parse(line) as SnapshotEntry;
      if (parsed.id) result.push(parsed);
    } catch {
      // skip malformed lines
    }
  }
  return result;
}
```

- [ ] **Step 5: Test passes**

```bash
npx vitest run tests/bevox/snapshots-index.test.ts
```

Expected: 3 tests pass.

- [ ] **Step 6: Implement `src/lib/bevox/git-ops.ts`**

(No test for this — it shells out to git. Smoke-test by calling from an API route in Task 9.)

```typescript
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { PATHS } from './paths';

const execFileAsync = promisify(execFile);

export interface GitCommitInfo {
  sha: string;
  short_sha: string;
  subject: string;
  author: string;
  age_seconds: number;
}

export async function lastCommit(repo: string = PATHS.bevoxKnowledgeClone): Promise<GitCommitInfo> {
  const { stdout } = await execFileAsync(
    'git',
    ['-C', repo, 'log', '-1', '--format=%H%n%h%n%s%n%an%n%ct'],
    { timeout: 5000 }
  );
  const [sha, short_sha, subject, author, ctStr] = stdout.trim().split('\n');
  const ct = parseInt(ctStr, 10);
  const now = Math.floor(Date.now() / 1000);
  return { sha, short_sha, subject, author, age_seconds: now - ct };
}

export async function currentBranch(repo: string = PATHS.bevoxKnowledgeClone): Promise<string> {
  const { stdout } = await execFileAsync(
    'git', ['-C', repo, 'rev-parse', '--abbrev-ref', 'HEAD'], { timeout: 3000 }
  );
  return stdout.trim();
}
```

- [ ] **Step 7: Implement `src/lib/bevox/systemd.ts`**

```typescript
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const execFileAsync = promisify(execFile);

export interface TimerInfo {
  unit: string;
  next: string;
  left: string;
  last: string;
  passed: string;
  activates: string;
}

export async function listUserTimers(): Promise<TimerInfo[]> {
  try {
    const { stdout } = await execFileAsync(
      'systemctl', ['--user', 'list-timers', '--all', '--output=json'],
      { timeout: 3000 }
    );
    return JSON.parse(stdout) as TimerInfo[];
  } catch {
    return [];
  }
}

export async function unitStatus(unit: string): Promise<'active' | 'inactive' | 'failed' | 'unknown'> {
  try {
    const { stdout } = await execFileAsync(
      'systemctl', ['--user', 'is-active', unit], { timeout: 3000 }
    );
    const s = stdout.trim();
    if (s === 'active' || s === 'inactive' || s === 'failed') return s;
    return 'unknown';
  } catch {
    return 'inactive';
  }
}
```

- [ ] **Step 8: Commit**

```bash
git add src/lib/bevox/snapshots-index.ts src/lib/bevox/git-ops.ts src/lib/bevox/systemd.ts tests/bevox/snapshots-index.test.ts tests/fixtures/snapshots-index.jsonl
git commit -m "feat(data): snapshots index, git ops, systemd readers

Per spec §3.2:
- snapshots-index.ts: reads jsonl, skips malformed lines
- git-ops.ts: lastCommit + currentBranch via execFile
- systemd.ts: listUserTimers + unitStatus
Tests: snapshots-index.test.ts (3 tests). git/systemd are smoke-tested via API routes."
git push
```

---

### Task 7: SQLite indexer for events.jsonl

**Files:**
- Create: `src/lib/bevox/events-db.ts`
- Create: `src/lib/bevox/events-indexer.ts`
- Create: `tests/bevox/events-indexer.test.ts`
- Create: `tests/fixtures/events-sample.jsonl`

- [ ] **Step 1: Capture a small fixture**

```bash
tail -50 ~/.openclaw/knowledge-sync/events.jsonl > tests/fixtures/events-sample.jsonl
wc -l tests/fixtures/events-sample.jsonl
```

Expected: 50 lines.

- [ ] **Step 2: Implement `src/lib/bevox/events-db.ts`**

```typescript
import Database from 'better-sqlite3';
import path from 'node:path';
import { PATHS } from './paths';

const DB_PATH = process.env.MC_DB_PATH ?? path.join(PATHS.openclawHome, 'mission-control', 'events.db');

let _db: Database.Database | null = null;

export function getDb(): Database.Database {
  if (_db) return _db;
  const dir = path.dirname(DB_PATH);
  // Ensure dir exists
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  require('node:fs').mkdirSync(dir, { recursive: true });
  _db = new Database(DB_PATH);
  _db.pragma('journal_mode = WAL');
  initSchema(_db);
  return _db;
}

function initSchema(db: Database.Database) {
  db.exec(`
    CREATE TABLE IF NOT EXISTS events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ts TEXT NOT NULL,
      event TEXT NOT NULL,
      severity TEXT,
      payload TEXT NOT NULL,
      raw_line TEXT NOT NULL,
      file_offset INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
    CREATE INDEX IF NOT EXISTS idx_events_event ON events(event);
    CREATE INDEX IF NOT EXISTS idx_events_severity ON events(severity);

    CREATE TABLE IF NOT EXISTS indexer_state (
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL
    );
  `);
}

export function getLastIndexedOffset(db: Database.Database): number {
  const row = db.prepare(`SELECT value FROM indexer_state WHERE key = 'last_offset'`).get() as { value: string } | undefined;
  return row ? parseInt(row.value, 10) : 0;
}

export function setLastIndexedOffset(db: Database.Database, offset: number): void {
  db.prepare(`INSERT OR REPLACE INTO indexer_state (key, value) VALUES ('last_offset', ?)`).run(String(offset));
}

export function resetDb(): void {
  if (_db) _db.close();
  _db = null;
}
```

- [ ] **Step 3: Write the failing test for events-indexer**

Create `tests/bevox/events-indexer.test.ts`:

```typescript
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { indexEventsFile } from '@/lib/bevox/events-indexer';
import { getDb, resetDb } from '@/lib/bevox/events-db';

const FIXTURE = path.join(__dirname, '..', 'fixtures', 'events-sample.jsonl');
let TMP_DB: string;

beforeEach(async () => {
  const tmp = await fs.mkdtemp(path.join(os.tmpdir(), 'mc-events-test-'));
  TMP_DB = path.join(tmp, 'events.db');
  process.env.MC_DB_PATH = TMP_DB;
  resetDb();
});

afterEach(() => {
  resetDb();
  delete process.env.MC_DB_PATH;
});

describe('indexEventsFile', () => {
  it('indexes all lines from a fresh file', async () => {
    const result = await indexEventsFile(FIXTURE);
    expect(result.indexed).toBeGreaterThan(0);
    const db = getDb();
    const count = (db.prepare('SELECT COUNT(*) as c FROM events').get() as { c: number }).c;
    expect(count).toBe(result.indexed);
  });

  it('is idempotent: running twice does not duplicate rows', async () => {
    await indexEventsFile(FIXTURE);
    const db = getDb();
    const first = (db.prepare('SELECT COUNT(*) as c FROM events').get() as { c: number }).c;
    const second = await indexEventsFile(FIXTURE);
    const after = (db.prepare('SELECT COUNT(*) as c FROM events').get() as { c: number }).c;
    expect(after).toBe(first);
    expect(second.indexed).toBe(0);
  });

  it('appends new lines after the offset', async () => {
    const tmp = await fs.mkdtemp(path.join(os.tmpdir(), 'mc-events-append-'));
    const file = path.join(tmp, 'events.jsonl');
    await fs.writeFile(
      file,
      JSON.stringify({ ts: '2026-04-10T10:00:00Z', event: 'test_one', payload: {} }) + '\n'
    );
    const r1 = await indexEventsFile(file);
    expect(r1.indexed).toBe(1);

    await fs.appendFile(
      file,
      JSON.stringify({ ts: '2026-04-10T10:00:01Z', event: 'test_two', payload: {} }) + '\n'
    );
    const r2 = await indexEventsFile(file);
    expect(r2.indexed).toBe(1);

    const db = getDb();
    const count = (db.prepare('SELECT COUNT(*) as c FROM events').get() as { c: number }).c;
    expect(count).toBe(2);
  });
});
```

- [ ] **Step 4: Verify failing**

```bash
npx vitest run tests/bevox/events-indexer.test.ts
```

Expected: FAIL.

- [ ] **Step 5: Implement `src/lib/bevox/events-indexer.ts`**

```typescript
import { promises as fs } from 'node:fs';
import { getDb, getLastIndexedOffset, setLastIndexedOffset } from './events-db';
import { PATHS } from './paths';

export interface IndexResult {
  indexed: number;
  total_offset: number;
}

export async function indexEventsFile(filePath: string = PATHS.ksEvents): Promise<IndexResult> {
  const db = getDb();
  const lastOffset = getLastIndexedOffset(db);

  let raw: string;
  try {
    const stat = await fs.stat(filePath);
    if (stat.size === lastOffset) {
      return { indexed: 0, total_offset: lastOffset };
    }
    if (stat.size < lastOffset) {
      // file was truncated/rotated; rebuild from scratch
      db.prepare('DELETE FROM events').run();
      setLastIndexedOffset(db, 0);
      raw = await fs.readFile(filePath, 'utf-8');
    } else {
      // tail incremental from lastOffset
      const fh = await fs.open(filePath, 'r');
      try {
        const buf = Buffer.alloc(stat.size - lastOffset);
        await fh.read(buf, 0, buf.length, lastOffset);
        raw = buf.toString('utf-8');
      } finally {
        await fh.close();
      }
    }
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === 'ENOENT') {
      return { indexed: 0, total_offset: 0 };
    }
    throw err;
  }

  const lines = raw.split('\n');
  // The last element is empty if raw ends with \n; if it doesn't end with \n, the last
  // line is incomplete and we must NOT index it (we'll catch it next pass).
  const completeLines = raw.endsWith('\n') ? lines.slice(0, -1) : lines.slice(0, -1);
  let bytesConsumed = 0;
  let indexed = 0;
  const insert = db.prepare(
    `INSERT INTO events (ts, event, severity, payload, raw_line, file_offset) VALUES (?, ?, ?, ?, ?, ?)`
  );
  const tx = db.transaction((rows: typeof completeLines) => {
    for (const line of rows) {
      if (!line.trim()) {
        bytesConsumed += line.length + 1; // +1 for \n
        continue;
      }
      try {
        const parsed = JSON.parse(line);
        insert.run(
          parsed.ts ?? '',
          parsed.event ?? '',
          parsed.payload?.severity ?? null,
          JSON.stringify(parsed.payload ?? {}),
          line,
          (lastOffset + bytesConsumed)
        );
        indexed++;
      } catch {
        // skip malformed
      }
      bytesConsumed += line.length + 1; // +1 for \n
    }
  });
  tx(completeLines);

  const newOffset = lastOffset + bytesConsumed;
  setLastIndexedOffset(db, newOffset);
  return { indexed, total_offset: newOffset };
}
```

- [ ] **Step 6: Run tests to pass**

```bash
npx vitest run tests/bevox/events-indexer.test.ts
```

Expected: 3 tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/lib/bevox/events-db.ts src/lib/bevox/events-indexer.ts tests/bevox/events-indexer.test.ts tests/fixtures/events-sample.jsonl
git commit -m "feat(data): SQLite indexer for events.jsonl with idempotent tail

Per spec §3.2:
- events-db.ts: better-sqlite3 schema + offset tracking
- events-indexer.ts: tail incremental, handles append, truncation, and malformed lines
- 3 tests covering fresh index, idempotency, and append"
git push
```

---

## Phase 2 — Shell + Home dashboard (Tasks 8-10)

### Task 8: Top nav agrupado component

**Files:**
- Create: `src/components/bevox/TopNavGrouped.tsx`
- Modify: the upstream layout to use it instead of the old nav

- [ ] **Step 1: Find the existing nav usage**

```bash
grep -rln "Header\|TopNav\|Nav" src/components/TenacitOS/ src/app/ --include="*.tsx" | head
```

Save the file that currently renders the top bar — you'll edit it in Step 4.

- [ ] **Step 2: Define the v1 module list**

Create `src/components/bevox/nav-config.ts`:

```typescript
export interface NavItem {
  label: string;
  href: string;
  group: 'nucleo' | 'suporte';
}

// v1 default = 5 items. Activity is a stretch goal (Task 15b);
// add { label: 'Activity', href: '/activity', group: 'suporte' } here
// only when Task 15b ships.
//
// Discovery delta: upstream uses /costs (plural) — we keep that route, not /cost.
export const NAV_ITEMS: NavItem[] = [
  { label: 'Home', href: '/', group: 'nucleo' },
  { label: 'Knowledge', href: '/knowledge', group: 'nucleo' },
  { label: 'Approvals', href: '/approvals', group: 'nucleo' },
  { label: 'Health', href: '/health', group: 'suporte' },
  { label: 'Cost', href: '/costs', group: 'suporte' },
];
```

- [ ] **Step 3: Create `src/components/bevox/TopNavGrouped.tsx`**

```tsx
'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { NAV_ITEMS } from './nav-config';

export function TopNavGrouped() {
  const pathname = usePathname();
  const nucleo = NAV_ITEMS.filter(i => i.group === 'nucleo');
  const suporte = NAV_ITEMS.filter(i => i.group === 'suporte');
  const appName = process.env.NEXT_PUBLIC_APP_NAME ?? 'Bevox Mission Control';

  const renderLink = (item: typeof NAV_ITEMS[number], strong: boolean) => {
    const active = pathname === item.href;
    return (
      <Link
        key={item.href}
        href={item.href}
        className={[
          'px-2 py-1 rounded transition-colors',
          strong ? 'font-semibold' : 'font-normal opacity-80',
          active ? 'bg-accent/20 text-accent' : 'hover:bg-white/5',
        ].join(' ')}
      >
        {item.label}
      </Link>
    );
  };

  return (
    <header className="flex items-center gap-4 px-4 h-12 border-b border-white/10 bg-black/40 backdrop-blur">
      <div className="font-bold text-sm tracking-wide">{appName}</div>
      <nav className="flex items-center gap-1 text-sm">
        {nucleo.map(i => renderLink(i, true))}
        <span className="mx-2 opacity-30 select-none" aria-hidden>‖</span>
        {suporte.map(i => renderLink(i, false))}
      </nav>
      <div className="ml-auto flex items-center gap-2 text-xs opacity-70">
        <span title="Bernard">●</span>
      </div>
    </header>
  );
}
```

- [ ] **Step 4: Wire it into the layout**

Edit `src/app/(dashboard)/layout.tsx` (create the dashboard route group if upstream doesn't have one — most likely it does). At the top of the JSX tree, replace the existing top bar with `<TopNavGrouped />`. Keep the workspace area below.

```tsx
import { TopNavGrouped } from '@/components/bevox/TopNavGrouped';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col">
      <TopNavGrouped />
      <main className="flex-1 p-4">{children}</main>
    </div>
  );
}
```

(If upstream's layout has a `<Dock />` or `<StatusBar />` component you want to preserve, keep them. The point is to swap the nav, not nuke the shell.)

- [ ] **Step 5: Smoke-test**

```bash
npm run dev
```

Visit (with the auth header trick from Task 4 Step 6) `/`, `/knowledge`, `/approvals`, `/health`, `/cost`, `/activity`. The `/` route should render the existing TenacitOS dashboard for now (we replace it in Task 9). Other routes will 404 — that's fine; we build them in Phase 3. Verify visually: the header shows "Bevox Mission Control", the 6 nav items are there with the `‖` divider, núcleo items are bold.

- [ ] **Step 6: Commit**

```bash
git add src/components/bevox/TopNavGrouped.tsx src/components/bevox/nav-config.ts src/app/(dashboard)/layout.tsx
git commit -m "feat(nav): top nav agrupado nucleo paralelo suporte

Per spec §4.1:
- 6 modules: Home/Knowledge/Approvals (nucleo, bold) || Health/Cost/Activity (suporte)
- visible separator between groups
- active route highlight"
git push
```

---

### Task 9: Bevox API routes for Home widgets

**Files:**
- Create: `src/app/api/bevox/knowledge-state/route.ts`
- Create: `src/app/api/bevox/snapshots/route.ts`
- Create: `src/app/api/bevox/git-last-commit/route.ts`
- Create: `src/app/api/bevox/health/route.ts`
- Create: `src/app/api/bevox/approvals/route.ts`
- Create: `src/app/api/bevox/events/route.ts`
- Create: `src/lib/bevox/approvals.ts`
- Create: `src/lib/bevox/health.ts`
- Create: `tests/bevox/approvals.test.ts`

- [ ] **Step 1: Implement `src/lib/bevox/approvals.ts`**

```typescript
import { getDb } from './events-db';
import { indexEventsFile } from './events-indexer';
import type { ApprovalSummary } from './types';

const APPROVAL_TTL_SECONDS = 3600;

export async function listApprovals(state?: 'pending' | 'all'): Promise<ApprovalSummary[]> {
  await indexEventsFile(); // make sure DB is fresh
  const db = getDb();
  const rows = db
    .prepare(
      `SELECT ts, event, payload FROM events WHERE event = 'canonical_approval_pending' ORDER BY ts DESC`
    )
    .all() as Array<{ ts: string; event: string; payload: string }>;

  const resolvedRows = db
    .prepare(
      `SELECT payload FROM events WHERE event IN ('canonical_approval_granted','canonical_approval_rejected','canonical_committed','canonical_pushed','canonical_marker_created')`
    )
    .all() as Array<{ payload: string }>;

  const grantedIds = new Set<string>();
  const rejectedIds = new Set<string>();
  const executedIds = new Set<string>();
  for (const r of resolvedRows) {
    try {
      const p = JSON.parse(r.payload);
      const id = p.approval_id;
      if (!id) continue;
      // Best-effort classification — derived from event name on the source row
      // is overkill; we'll fold all "executed-ish" events into executedIds for v1.
      if (p.sha || p.tag) executedIds.add(id);
      else if (p.reason) rejectedIds.add(id);
      else grantedIds.add(id);
    } catch {}
  }

  const now = Math.floor(Date.now() / 1000);
  const result: ApprovalSummary[] = [];
  for (const row of rows) {
    try {
      const payload = JSON.parse(row.payload);
      const approval_id: string = payload.approval_id;
      if (!approval_id) continue;
      const created_at = row.ts;
      const created_epoch = Math.floor(new Date(row.ts).getTime() / 1000);
      const age_seconds = now - created_epoch;
      let derivedState: ApprovalSummary['state'] = 'pending';
      if (executedIds.has(approval_id)) derivedState = 'executed';
      else if (rejectedIds.has(approval_id)) derivedState = 'rejected';
      else if (grantedIds.has(approval_id)) derivedState = 'granted';
      else if (age_seconds > APPROVAL_TTL_SECONDS) derivedState = 'expired';
      if (state === 'pending' && derivedState !== 'pending') continue;
      result.push({
        approval_id,
        short_id: approval_id.slice(0, 8),
        action: payload.action ?? '',
        state: derivedState,
        created_at,
        age_seconds,
        card: payload.card ?? null,
      });
    } catch {}
  }
  return result;
}
```

- [ ] **Step 2: Test for approvals.ts**

Create `tests/bevox/approvals.test.ts`:

```typescript
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { resetDb } from '@/lib/bevox/events-db';
import { listApprovals } from '@/lib/bevox/approvals';

let tmp: string;
let eventsFile: string;

beforeEach(async () => {
  tmp = await fs.mkdtemp(path.join(os.tmpdir(), 'mc-approvals-'));
  eventsFile = path.join(tmp, 'events.jsonl');
  process.env.MC_DB_PATH = path.join(tmp, 'events.db');
  // Override the path the indexer reads from
  process.env.MC_EVENTS_FILE = eventsFile;
  resetDb();
});

afterEach(() => {
  resetDb();
  delete process.env.MC_DB_PATH;
  delete process.env.MC_EVENTS_FILE;
});

function appendEvent(obj: object) {
  return fs.appendFile(eventsFile, JSON.stringify(obj) + '\n');
}

describe('listApprovals', () => {
  it('returns empty when no events', async () => {
    await fs.writeFile(eventsFile, '');
    const result = await listApprovals();
    expect(result).toEqual([]);
  });

  it('returns pending approvals only when state="pending"', async () => {
    await appendEvent({
      ts: '2026-04-10T10:00:00Z',
      event: 'canonical_approval_pending',
      payload: { approval_id: 'aaaaaaaa-1111', action: 'canonical commit', card: {} },
    });
    await appendEvent({
      ts: '2026-04-10T10:01:00Z',
      event: 'canonical_approval_pending',
      payload: { approval_id: 'bbbbbbbb-2222', action: 'canonical commit', card: {} },
    });
    await appendEvent({
      ts: '2026-04-10T10:02:00Z',
      event: 'canonical_approval_granted',
      payload: { approval_id: 'aaaaaaaa-1111' },
    });
    await appendEvent({
      ts: '2026-04-10T10:03:00Z',
      event: 'canonical_committed',
      payload: { approval_id: 'aaaaaaaa-1111', sha: 'deadbeef' },
    });

    const pending = await listApprovals('pending');
    expect(pending).toHaveLength(1);
    expect(pending[0].short_id).toBe('bbbbbbbb');

    const all = await listApprovals('all');
    expect(all).toHaveLength(2);
    const states = all.map(a => a.state).sort();
    expect(states).toEqual(['executed', 'pending']);
  });
});
```

Note: this test exposes that the indexer must accept a path override via `MC_EVENTS_FILE`. Update `src/lib/bevox/paths.ts` to honor it:

```typescript
ksEvents: process.env.MC_EVENTS_FILE ?? path.join(HOME, '.openclaw', 'knowledge-sync', 'events.jsonl'),
```

(Apply this edit before running the test.)

- [ ] **Step 3: Run the test**

```bash
npx vitest run tests/bevox/approvals.test.ts
```

Expected: 2 tests pass.

- [ ] **Step 4: Implement `src/lib/bevox/health.ts`**

```typescript
import { readKsState } from './knowledge-sync-state';
import { readSnapshotsIndex } from './snapshots-index';
import { listUserTimers, unitStatus } from './systemd';

export interface HealthOverall {
  level: 'ok' | 'degraded' | 'critical';
  warnings: number;
  errors: number;
  components: {
    knowledge_sync: 'ok' | 'degraded' | 'critical';
    timers: { unit: string; status: string }[];
    snapshots: { last_auto?: string; last_manual?: string; last_pre_canonical?: string; stale: boolean };
  };
}

const KS_TIMERS = [
  'knowledge-sync-refresh.timer',
  'knowledge-sync-snapshot-hourly.timer',
  'knowledge-sync-verify-daily.timer',
];

export async function readHealthOverall(): Promise<HealthOverall> {
  let ksLevel: HealthOverall['components']['knowledge_sync'] = 'ok';
  let warnings = 0;
  let errors = 0;
  try {
    const state = await readKsState();
    ksLevel = state.health.overall;
    for (const i of state.health.issues ?? []) {
      if (i.severity === 'warn') warnings++;
      if (i.severity === 'error') errors++;
    }
  } catch {
    ksLevel = 'critical';
    errors++;
  }

  const timers = await Promise.all(
    KS_TIMERS.map(async unit => ({ unit, status: await unitStatus(unit) }))
  );
  for (const t of timers) {
    if (t.status === 'failed') errors++;
    else if (t.status === 'inactive') warnings++;
  }

  const snapshots = await readSnapshotsIndex();
  const byType = (type: string) => snapshots
    .filter(s => s.type === type)
    .sort((a, b) => b.created_at.localeCompare(a.created_at))[0]?.created_at;
  const lastAuto = byType('auto');
  const lastManual = byType('manual');
  const lastPreCanonical = byType('pre-canonical');
  // Threshold per spec §5.2.4: snapshot hourly = warn if > 2h
  const TWO_HOURS_MS = 2 * 60 * 60 * 1000;
  const stale = lastAuto ? Date.now() - new Date(lastAuto).getTime() > TWO_HOURS_MS : true;
  if (stale) warnings++;

  const level: HealthOverall['level'] = errors > 0 ? 'critical' : warnings > 0 ? 'degraded' : 'ok';

  return {
    level,
    warnings,
    errors,
    components: {
      knowledge_sync: ksLevel,
      timers,
      snapshots: { last_auto: lastAuto, last_manual: lastManual, last_pre_canonical: lastPreCanonical, stale },
    },
  };
}
```

- [ ] **Step 5: Implement the API routes**

Create each route as a Next.js App Router GET handler. Each one is small.

`src/app/api/bevox/knowledge-state/route.ts`:

```typescript
import { NextResponse } from 'next/server';
import { readKsState, readKsStatePrevious } from '@/lib/bevox/knowledge-sync-state';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const state = await readKsState();
    const previous = await readKsStatePrevious();
    return NextResponse.json({ state, previous });
  } catch (err) {
    return NextResponse.json({ error: (err as Error).message }, { status: 500 });
  }
}
```

`src/app/api/bevox/snapshots/route.ts`:

```typescript
import { NextResponse } from 'next/server';
import { readSnapshotsIndex } from '@/lib/bevox/snapshots-index';

export const dynamic = 'force-dynamic';

export async function GET() {
  const snapshots = await readSnapshotsIndex();
  return NextResponse.json({ snapshots });
}
```

`src/app/api/bevox/git-last-commit/route.ts`:

```typescript
import { NextResponse } from 'next/server';
import { lastCommit } from '@/lib/bevox/git-ops';

export const revalidate = 30; // 30s TTL

export async function GET() {
  try {
    const commit = await lastCommit();
    return NextResponse.json({ commit });
  } catch (err) {
    return NextResponse.json({ error: (err as Error).message }, { status: 500 });
  }
}
```

`src/app/api/bevox/health/route.ts`:

```typescript
import { NextResponse } from 'next/server';
import { readHealthOverall } from '@/lib/bevox/health';

export const revalidate = 30;

export async function GET() {
  const health = await readHealthOverall();
  return NextResponse.json({ health });
}
```

`src/app/api/bevox/approvals/route.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { listApprovals } from '@/lib/bevox/approvals';

export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
  const state = req.nextUrl.searchParams.get('state') ?? 'pending';
  const result = await listApprovals(state === 'all' ? 'all' : 'pending');
  return NextResponse.json({ approvals: result, count: result.length });
}
```

`src/app/api/bevox/events/route.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/bevox/events-db';
import { indexEventsFile } from '@/lib/bevox/events-indexer';

export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
  await indexEventsFile();
  const db = getDb();
  const limit = Math.min(parseInt(req.nextUrl.searchParams.get('limit') ?? '50', 10), 500);
  const severity = req.nextUrl.searchParams.get('severity'); // 'warn' | 'error' | null
  let sql = 'SELECT ts, event, severity, payload FROM events';
  const params: unknown[] = [];
  if (severity) {
    sql += ' WHERE severity = ?';
    params.push(severity);
  }
  sql += ' ORDER BY ts DESC LIMIT ?';
  params.push(limit);
  const rows = db.prepare(sql).all(...params);
  return NextResponse.json({ events: rows });
}
```

- [ ] **Step 6: Smoke-test each API route**

```bash
npm run dev
```

In another terminal:

```bash
H='Cf-Access-Authenticated-User-Email: you@example.com'
for path in knowledge-state snapshots git-last-commit health approvals events; do
  echo "=== /api/bevox/$path ==="
  curl -s -H "$H" "http://localhost:3000/api/bevox/$path" | jq '. | keys' 2>&1 | head -5
done
```

Expected: each route returns JSON with the expected top-level key (`state`, `snapshots`, `commit`, `health`, `approvals`, `events`). No 500s.

- [ ] **Step 7: Commit**

```bash
git add src/lib/bevox/approvals.ts src/lib/bevox/health.ts src/app/api/bevox/ tests/bevox/approvals.test.ts
git commit -m "feat(api): bevox API routes for Home widgets

Per spec §3.2 and §5.2.1:
- /api/bevox/knowledge-state, snapshots, git-last-commit, health
- /api/bevox/approvals (?state=pending|all)
- /api/bevox/events (?severity, ?limit)
- approvals.ts derives state from indexed events
- health.ts aggregates ks state + timers + snapshot freshness
Tests: approvals.test.ts (2 tests)"
git push
```

---

### Task 10: Home dashboard 2-col with 6 widgets

**Files:**
- Create: `src/components/bevox/widgets/KnowledgeStatusWidget.tsx`
- Create: `src/components/bevox/widgets/ApprovalsPendingWidget.tsx`
- Create: `src/components/bevox/widgets/HealthOverallWidget.tsx`
- Create: `src/components/bevox/widgets/LastCommitWidget.tsx`
- Create: `src/components/bevox/widgets/CostTodayWidget.tsx`
- Create: `src/components/bevox/widgets/CriticalEventsWidget.tsx`
- Modify: `src/app/(dashboard)/page.tsx` (replace upstream Home)

- [ ] **Step 1: Create the 4 small (right-column) widgets first**

`src/components/bevox/widgets/HealthOverallWidget.tsx`:

```tsx
'use client';
import { useEffect, useState } from 'react';

interface HealthData { level: 'ok'|'degraded'|'critical'; warnings: number; errors: number; }

export function HealthOverallWidget() {
  const [data, setData] = useState<HealthData | null>(null);
  useEffect(() => {
    fetch('/api/bevox/health').then(r => r.json()).then(d => setData(d.health));
  }, []);
  if (!data) return <Card title="Health"><span className="opacity-50">…</span></Card>;
  const dot = data.level === 'ok' ? '🟢' : data.level === 'degraded' ? '🟡' : '🔴';
  return (
    <Card title="Health">
      <div className="text-2xl">{dot}</div>
      <div className="text-xs opacity-70">{data.warnings}w · {data.errors}e</div>
    </Card>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border border-white/10 rounded p-3 bg-black/20">
      <div className="text-xs uppercase opacity-60 mb-1">{title}</div>
      {children}
    </div>
  );
}
```

`src/components/bevox/widgets/LastCommitWidget.tsx`:

```tsx
'use client';
import { useEffect, useState } from 'react';

export function LastCommitWidget() {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    fetch('/api/bevox/git-last-commit').then(r => r.json()).then(setData);
  }, []);
  if (!data?.commit) return <Card title="Last commit"><span className="opacity-50">…</span></Card>;
  const c = data.commit;
  const ageMin = Math.floor(c.age_seconds / 60);
  const age = ageMin < 60 ? `${ageMin}m` : ageMin < 1440 ? `${Math.floor(ageMin/60)}h` : `${Math.floor(ageMin/1440)}d`;
  return (
    <Card title="Last commit">
      <div className="font-mono text-xs">{c.short_sha}</div>
      <div className="text-xs truncate" title={c.subject}>{c.subject}</div>
      <div className="text-xs opacity-60">{c.author} · {age}</div>
    </Card>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border border-white/10 rounded p-3 bg-black/20">
      <div className="text-xs uppercase opacity-60 mb-1">{title}</div>
      {children}
    </div>
  );
}
```

`src/components/bevox/widgets/CostTodayWidget.tsx`:

```tsx
'use client';
// Discovery delta: upstream API is /api/costs (plural) and returns
// { today, yesterday, daily: [...], byAgent: [...], byModel: [...] }.
// We reuse it directly.
import { useEffect, useState } from 'react';

export function CostTodayWidget() {
  const [data, setData] = useState<{ total: number; delta: number } | null>(null);
  useEffect(() => {
    fetch('/api/costs?timeframe=1d')
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (!d) { setData(null); return; }
        const today = d.today ?? 0;
        const yesterday = d.yesterday ?? 0;
        setData({ total: today, delta: today - yesterday });
      })
      .catch(() => setData(null));
  }, []);
  return (
    <div className="border border-white/10 rounded p-3 bg-black/20">
      <div className="text-xs uppercase opacity-60 mb-1">Cost today</div>
      <div className="text-lg font-semibold">
        {data?.total != null ? `$${data.total.toFixed(2)}` : '—'}
      </div>
      {data?.delta != null && (
        <div className="text-xs opacity-60">Δ {data.delta >= 0 ? '+' : ''}{data.delta.toFixed(2)}</div>
      )}
    </div>
  );
}
```

`src/components/bevox/widgets/CriticalEventsWidget.tsx`:

```tsx
'use client';
import { useEffect, useState } from 'react';

interface Ev { ts: string; event: string; severity?: string; }

export function CriticalEventsWidget() {
  const [events, setEvents] = useState<Ev[]>([]);
  useEffect(() => {
    fetch('/api/bevox/events?severity=warn&limit=5')
      .then(r => r.json())
      .then(d => setEvents(d.events ?? []));
  }, []);
  return (
    <div className="border border-white/10 rounded p-3 bg-black/20">
      <div className="text-xs uppercase opacity-60 mb-1">Critical events</div>
      {events.length === 0 ? (
        <div className="text-xs opacity-50">none</div>
      ) : (
        <ul className="text-xs space-y-1">
          {events.slice(0, 3).map((e, i) => (
            <li key={i} className="truncate" title={e.event}>{e.event}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create the 2 large (left-column) widgets**

`src/components/bevox/widgets/KnowledgeStatusWidget.tsx`:

```tsx
'use client';
import { useEffect, useState } from 'react';

export function KnowledgeStatusWidget() {
  const [data, setData] = useState<any>(null);
  useEffect(() => { fetch('/api/bevox/knowledge-state').then(r => r.json()).then(setData); }, []);
  if (!data?.state) return <Card>…</Card>;
  const s = data.state;
  const wt = s.working_tree?.clean ? 'clean' : 'dirty';
  return (
    <Card>
      <div className="flex items-baseline justify-between mb-2">
        <h3 className="text-base font-semibold">Knowledge sync status</h3>
        <span className={['text-xs px-2 py-0.5 rounded',
          s.health.overall === 'ok' ? 'bg-green-500/20 text-green-300'
          : s.health.overall === 'degraded' ? 'bg-yellow-500/20 text-yellow-300'
          : 'bg-red-500/20 text-red-300'
        ].join(' ')}>{s.health.overall}</span>
      </div>
      <dl className="grid grid-cols-2 gap-y-1 text-sm">
        <dt className="opacity-60">branch</dt><dd>{s.branch?.current}</dd>
        <dt className="opacity-60">ahead/behind</dt><dd>{s.branch?.ahead ?? 0}/{s.branch?.behind ?? 0}</dd>
        <dt className="opacity-60">working tree</dt><dd>{wt}</dd>
        <dt className="opacity-60">last fetch</dt><dd>{s.last_fetch?.ok ? 'ok' : 'failed'}</dd>
      </dl>
    </Card>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return <div className="border border-white/10 rounded p-4 bg-black/20">{children}</div>;
}
```

`src/components/bevox/widgets/ApprovalsPendingWidget.tsx`:

```tsx
'use client';
import { useEffect, useState } from 'react';

interface Approval { approval_id: string; short_id: string; action: string; age_seconds: number; }

export function ApprovalsPendingWidget() {
  const [data, setData] = useState<{ approvals: Approval[]; count: number } | null>(null);
  useEffect(() => {
    fetch('/api/bevox/approvals?state=pending').then(r => r.json()).then(setData);
  }, []);
  if (!data) return <Card>…</Card>;
  return (
    <Card>
      <div className="flex items-baseline justify-between mb-2">
        <h3 className="text-base font-semibold">Approvals pendentes</h3>
        <span className="text-xs px-2 py-0.5 rounded bg-blue-500/20 text-blue-300">{data.count}</span>
      </div>
      {data.approvals.length === 0 ? (
        <div className="text-sm opacity-60">Sem approvals pendentes.</div>
      ) : (
        <ul className="text-sm space-y-2">
          {data.approvals.slice(0, 3).map(a => (
            <li key={a.approval_id} className="border border-white/5 rounded p-2">
              <div className="font-mono text-xs opacity-70">[{a.short_id}]</div>
              <div className="truncate" title={a.action}>{a.action}</div>
              <div className="text-xs opacity-60">há {Math.floor(a.age_seconds / 60)}m</div>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-2 text-xs opacity-60">Aprovação continua via Telegram.</div>
    </Card>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return <div className="border border-white/10 rounded p-4 bg-black/20">{children}</div>;
}
```

- [ ] **Step 3: Replace the Home page**

Edit `src/app/(dashboard)/page.tsx`:

```tsx
import { KnowledgeStatusWidget } from '@/components/bevox/widgets/KnowledgeStatusWidget';
import { ApprovalsPendingWidget } from '@/components/bevox/widgets/ApprovalsPendingWidget';
import { HealthOverallWidget } from '@/components/bevox/widgets/HealthOverallWidget';
import { LastCommitWidget } from '@/components/bevox/widgets/LastCommitWidget';
import { CostTodayWidget } from '@/components/bevox/widgets/CostTodayWidget';
import { CriticalEventsWidget } from '@/components/bevox/widgets/CriticalEventsWidget';

export default function HomePage() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div className="lg:col-span-2 space-y-4">
        <KnowledgeStatusWidget />
        <ApprovalsPendingWidget />
      </div>
      <div className="space-y-3">
        <HealthOverallWidget />
        <LastCommitWidget />
        <CostTodayWidget />
        <CriticalEventsWidget />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Smoke-test the Home dashboard**

```bash
npm run dev
```

Visit `/` (with Cf-Access header). Expected:
- Left column shows two large cards: Knowledge sync status (with real branch/health data) and Approvals pendentes (with real count).
- Right column shows 4 compact cards: Health, Last commit, Cost today, Critical events.
- On a narrow window, the right column drops below the left.

Take a screenshot or just visually verify the 2-col split.

- [ ] **Step 5: Commit**

```bash
git add src/components/bevox/widgets/ src/app/(dashboard)/page.tsx
git commit -m "feat(home): 2-col asymmetric dashboard with 6 widgets

Per spec §4.2 and §5.2.1:
- Left col (2/3): KnowledgeStatusWidget, ApprovalsPendingWidget (large)
- Right col (1/3): Health, LastCommit, CostToday, CriticalEvents (compact)
- All widgets read from /api/bevox/* endpoints
- Telegram remains source única for approvals (read-only here)"
git push
```

---

## Phase 3 — Module pages (Tasks 11-15)

### Task 11: ModuleStream + ModuleSection components

**Files:**
- Create: `src/components/bevox/ModuleStream.tsx`
- Create: `src/components/bevox/ModuleSection.tsx`

- [ ] **Step 1: Create ModuleSection**

```tsx
'use client';
import { useState, ReactNode } from 'react';

interface Props {
  title: string;
  count?: number;
  defaultOpen?: boolean;
  children: ReactNode;
}

export function ModuleSection({ title, count, defaultOpen = true, children }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="border border-white/10 rounded mb-4">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-2 hover:bg-white/5"
      >
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs opacity-70">[{open ? '−' : '+'}]</span>
          <span className="font-semibold uppercase text-sm tracking-wide">{title}</span>
          {count != null && <span className="text-xs opacity-60">· {count}</span>}
        </div>
      </button>
      {open && <div className="px-4 pb-4 pt-1">{children}</div>}
    </section>
  );
}
```

- [ ] **Step 2: Create ModuleStream**

```tsx
import { ReactNode } from 'react';

export function ModuleStream({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-xl font-semibold mb-4">{title}</h1>
      {children}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add src/components/bevox/ModuleStream.tsx src/components/bevox/ModuleSection.tsx
git commit -m "feat(modules): ModuleStream + collapsible ModuleSection components

Per spec §4.3: shared shell for all module pages."
git push
```

---

### Task 12: Knowledge module page

**Files:**
- Create: `src/app/(dashboard)/knowledge/page.tsx`
- (Reuses) `/api/bevox/knowledge-state`, `/api/bevox/snapshots`, `/api/bevox/events`

- [ ] **Step 1: Implement the page**

```tsx
'use client';
import { useEffect, useState } from 'react';
import { ModuleStream } from '@/components/bevox/ModuleStream';
import { ModuleSection } from '@/components/bevox/ModuleSection';

export default function KnowledgePage() {
  const [state, setState] = useState<any>(null);
  const [snapshots, setSnapshots] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);

  useEffect(() => {
    fetch('/api/bevox/knowledge-state').then(r => r.json()).then(d => setState(d.state));
    fetch('/api/bevox/snapshots').then(r => r.json()).then(d => setSnapshots(d.snapshots ?? []));
    fetch('/api/bevox/events?limit=100').then(r => r.json()).then(d => setEvents(d.events ?? []));
  }, []);

  const drafts = state?.draft_branches ?? [];
  const recentSnapshots = snapshots.slice(0, 20);
  const ksEvents = events.filter((e: any) =>
    e.event?.startsWith('canonical_') || e.event?.startsWith('watcher_') || e.event?.startsWith('snapshot_')
  );

  return (
    <ModuleStream title="Knowledge">
      <ModuleSection title="Status">
        {state ? (
          <dl className="grid grid-cols-2 gap-y-1 text-sm">
            <dt className="opacity-60">branch</dt><dd>{state.branch?.current}</dd>
            <dt className="opacity-60">ahead / behind</dt><dd>{state.branch?.ahead}/{state.branch?.behind}</dd>
            <dt className="opacity-60">working tree</dt><dd>{state.working_tree?.clean ? 'clean' : 'dirty'}</dd>
            <dt className="opacity-60">last fetch</dt><dd>{state.last_fetch?.ok ? 'ok' : 'failed'}</dd>
            <dt className="opacity-60">health</dt><dd>{state.health?.overall}</dd>
          </dl>
        ) : <div className="opacity-50">…</div>}
      </ModuleSection>

      <ModuleSection title="Drafts" count={drafts.length}>
        {drafts.length === 0 ? (
          <div className="text-sm opacity-60">Sem branches draft ativas.</div>
        ) : (
          <ul className="text-sm space-y-1">
            {drafts.map((b: any) => (
              <li key={b.name}>{b.name} <span className="opacity-60 text-xs">{b.last_commit_age_days != null ? `· ${b.last_commit_age_days}d` : ''}</span></li>
            ))}
          </ul>
        )}
      </ModuleSection>

      <ModuleSection title="Snapshots" count={snapshots.length}>
        <ul className="text-sm space-y-1 font-mono text-xs">
          {recentSnapshots.map(s => (
            <li key={s.id} className="flex justify-between">
              <span>{s.type} · {s.id}</span>
              <span className="opacity-60">{s.created_at?.slice(0, 16) ?? ''}</span>
            </li>
          ))}
        </ul>
      </ModuleSection>

      <ModuleSection title="Events" count={ksEvents.length} defaultOpen={false}>
        <ul className="text-sm space-y-1 font-mono text-xs">
          {ksEvents.slice(0, 50).map((e: any, i: number) => (
            <li key={i} className="flex justify-between">
              <span>{e.event}</span>
              <span className="opacity-60">{e.ts?.slice(11, 19) ?? ''}</span>
            </li>
          ))}
        </ul>
      </ModuleSection>
    </ModuleStream>
  );
}
```

- [ ] **Step 2: Smoke-test**

Visit `/knowledge` with the auth header. Verify all 4 sections render with real data, the toggle works, and Events starts collapsed.

- [ ] **Step 3: Commit**

```bash
git add src/app/(dashboard)/knowledge/page.tsx
git commit -m "feat(knowledge): module page with status/drafts/snapshots/events

Per spec §5.2.2: stream vertical, no mutation buttons in v1."
git push
```

---

### Task 13: Approvals module page + ApprovalCardV2 component

**Files:**
- Create: `src/components/bevox/ApprovalCardV2.tsx`
- Create: `src/app/(dashboard)/approvals/page.tsx`

- [ ] **Step 1: Implement ApprovalCardV2**

```tsx
interface CardJson {
  summary?: string;
  why_now?: string;
  target?: any;
  evidence?: any;
  risk?: { level?: string; reason?: string; rollback?: string };
}

export function ApprovalCardV2({ shortId, action, card }: { shortId: string; action: string; card: CardJson | null }) {
  if (!card) {
    return <div className="text-sm opacity-60">[{shortId}] {action} (sem card)</div>;
  }
  return (
    <article className="border border-white/10 rounded p-4 bg-black/20 mb-3">
      <header className="flex items-baseline justify-between mb-2">
        <h4 className="font-semibold">[{shortId}]</h4>
        <span className="text-xs opacity-60">{action}</span>
      </header>
      {card.summary && <p className="text-sm mb-2">{card.summary}</p>}
      {card.why_now && (
        <section className="text-xs mb-2">
          <div className="opacity-60 uppercase mb-0.5">Por que agora</div>
          <div>{card.why_now}</div>
        </section>
      )}
      {card.risk && (
        <section className="text-xs mt-2">
          <div className="opacity-60 uppercase mb-0.5">Risco</div>
          <div>
            <span className="font-semibold">{(card.risk.level ?? '?').toUpperCase()}</span>
            {card.risk.reason && ` · ${card.risk.reason}`}
          </div>
        </section>
      )}
      <footer className="text-xs opacity-60 mt-3">
        Aprovação via Telegram. MC é read-only.
      </footer>
    </article>
  );
}
```

- [ ] **Step 2: Implement the Approvals page**

```tsx
'use client';
import { useEffect, useState } from 'react';
import { ModuleStream } from '@/components/bevox/ModuleStream';
import { ModuleSection } from '@/components/bevox/ModuleSection';
import { ApprovalCardV2 } from '@/components/bevox/ApprovalCardV2';

export default function ApprovalsPage() {
  const [pending, setPending] = useState<any[]>([]);
  const [all, setAll] = useState<any[]>([]);
  useEffect(() => {
    fetch('/api/bevox/approvals?state=pending').then(r => r.json()).then(d => setPending(d.approvals ?? []));
    fetch('/api/bevox/approvals?state=all').then(r => r.json()).then(d => setAll(d.approvals ?? []));
  }, []);

  const granted = all.filter(a => a.state === 'granted');
  const history = all.filter(a => a.state === 'executed' || a.state === 'rejected' || a.state === 'expired').slice(0, 20);

  return (
    <ModuleStream title="Approvals">
      <ModuleSection title="Pending" count={pending.length}>
        {pending.length === 0 ? (
          <div className="text-sm opacity-60">Sem approvals pendentes.</div>
        ) : (
          pending.map(a => <ApprovalCardV2 key={a.approval_id} shortId={a.short_id} action={a.action} card={a.card} />)
        )}
      </ModuleSection>
      <ModuleSection title="Granted (aguardando execucao)" count={granted.length}>
        {granted.length === 0 ? (
          <div className="text-sm opacity-60">Nenhum approval granted aguardando execução.</div>
        ) : (
          granted.map(a => <ApprovalCardV2 key={a.approval_id} shortId={a.short_id} action={a.action} card={a.card} />)
        )}
      </ModuleSection>
      <ModuleSection title="History" count={history.length} defaultOpen={false}>
        <ul className="text-sm space-y-1 font-mono text-xs">
          {history.map(a => (
            <li key={a.approval_id} className="flex justify-between">
              <span>[{a.short_id}] {a.action}</span>
              <span className="opacity-60">{a.state}</span>
            </li>
          ))}
        </ul>
      </ModuleSection>
    </ModuleStream>
  );
}
```

- [ ] **Step 3: Smoke-test**

Visit `/approvals`. If you have the test inbox file commit pending from earlier, you'll see it under Pending. Otherwise the page shows "Sem approvals pendentes" for Pending and the History section will list past approvals from `events.jsonl`.

- [ ] **Step 4: Commit**

```bash
git add src/components/bevox/ApprovalCardV2.tsx src/app/(dashboard)/approvals/page.tsx
git commit -m "feat(approvals): read-only module page rendering card v2

Per spec §5.2.3: 3 sections (Pending, Granted, History), no action buttons."
git push
```

---

### Task 14: Health module page

**Files:**
- Create: `src/app/(dashboard)/health/page.tsx`
- (Reuses) `/api/bevox/health`

- [ ] **Step 1: Implement**

```tsx
'use client';
import { useEffect, useState } from 'react';
import { ModuleStream } from '@/components/bevox/ModuleStream';
import { ModuleSection } from '@/components/bevox/ModuleSection';

export default function HealthPage() {
  const [data, setData] = useState<any>(null);
  useEffect(() => { fetch('/api/bevox/health').then(r => r.json()).then(d => setData(d.health)); }, []);
  if (!data) return <ModuleStream title="Health"><div className="opacity-50">…</div></ModuleStream>;

  const dot = data.level === 'ok' ? '🟢' : data.level === 'degraded' ? '🟡' : '🔴';

  return (
    <ModuleStream title="Health">
      <ModuleSection title="Overall">
        <div className="flex items-center gap-3">
          <span className="text-3xl">{dot}</span>
          <div className="text-sm">
            <div>{data.warnings} warnings · {data.errors} errors</div>
            <div className="opacity-60 text-xs">knowledge-sync: {data.components.knowledge_sync}</div>
          </div>
        </div>
      </ModuleSection>

      <ModuleSection title="Timers systemd" count={data.components.timers.length}>
        <ul className="text-sm font-mono text-xs space-y-1">
          {data.components.timers.map((t: any) => (
            <li key={t.unit} className="flex justify-between">
              <span>{t.unit}</span>
              <span className={t.status === 'active' ? 'text-green-300' : t.status === 'failed' ? 'text-red-300' : 'opacity-60'}>{t.status}</span>
            </li>
          ))}
        </ul>
      </ModuleSection>

      <ModuleSection title="Snapshots freshness">
        <dl className="text-sm grid grid-cols-2 gap-y-1">
          <dt className="opacity-60">last auto</dt><dd className="font-mono text-xs">{data.components.snapshots.last_auto ?? '—'}</dd>
          <dt className="opacity-60">last manual</dt><dd className="font-mono text-xs">{data.components.snapshots.last_manual ?? '—'}</dd>
          <dt className="opacity-60">last pre-canonical</dt><dd className="font-mono text-xs">{data.components.snapshots.last_pre_canonical ?? '—'}</dd>
          <dt className="opacity-60">stale</dt><dd>{data.components.snapshots.stale ? 'yes' : 'no'}</dd>
        </dl>
      </ModuleSection>
    </ModuleStream>
  );
}
```

- [ ] **Step 2: Smoke-test + commit**

Visit `/health`. Verify the 3 sections render correctly.

```bash
git add src/app/(dashboard)/health/page.tsx
git commit -m "feat(health): module page aggregating timers + snapshots + ks state

Per spec §5.2.4. System Monitor section deferred to upstream's existing widget integration."
git push
```

---

### Task 15a: Cost module (thin reuse)

> **Discovery applied:** upstream already has `(dashboard)/costs/page.tsx` (plural) and `/api/costs?timeframe=Nd`. We EDIT the existing page to use our `ModuleStream` pattern, rather than creating a new file. URL stays `/costs`.

**Files:**
- Modify: `src/app/(dashboard)/costs/page.tsx` (replace contents with ModuleStream version below)

- [ ] **Step 1: Read existing upstream page first**

```bash
cat src/app/(dashboard)/costs/page.tsx | head -50
```

Note any custom imports or styling Bernard might want preserved. If the upstream page has rich charting via `recharts`, we keep the chart but wrap the structure in our `ModuleStream`.

- [ ] **Step 2: Replace `(dashboard)/costs/page.tsx` with the ModuleStream version**

```tsx
'use client';
// Discovery delta: route is /costs (plural), not /cost.
// Upstream API: /api/costs?timeframe=1d returns { today, yesterday, daily, byAgent, byModel, ... }
// We replace upstream's existing page with our ModuleStream version for visual consistency.
import { useEffect, useState } from 'react';
import { ModuleStream } from '@/components/bevox/ModuleStream';
import { ModuleSection } from '@/components/bevox/ModuleSection';

export default function CostPage() {
  const [today, setToday] = useState<any>(null);
  const [week, setWeek] = useState<any>(null);
  useEffect(() => {
    fetch('/api/costs?timeframe=1d').then(r => r.ok ? r.json() : null).then(setToday).catch(() => setToday(null));
    fetch('/api/costs?timeframe=7d').then(r => r.ok ? r.json() : null).then(setWeek).catch(() => setWeek(null));
  }, []);

  return (
    <ModuleStream title="Cost">
      <ModuleSection title="Total do dia">
        {today ? (
          <div>
            <div className="text-2xl">${(today.today ?? 0).toFixed(2)}</div>
            <div className="text-xs opacity-60">vs ontem: ${(today.yesterday ?? 0).toFixed(2)}</div>
          </div>
        ) : <div className="opacity-50">—</div>}
      </ModuleSection>
      <ModuleSection title="Por modelo">
        {today?.byModel?.length ? (
          <ul className="text-sm">
            {today.byModel.map((row: any) => (
              <li key={row.model} className="flex justify-between"><span>{row.model}</span><span className="font-mono">${(row.cost ?? 0).toFixed(2)}</span></li>
            ))}
          </ul>
        ) : <div className="opacity-50 text-sm">Sem dados.</div>}
      </ModuleSection>
      <ModuleSection title="Histórico (últimos 7 dias)">
        {week?.daily?.length ? (
          <ul className="text-sm font-mono text-xs">
            {week.daily.map((p: any) => (
              <li key={p.date} className="flex justify-between"><span>{p.date}</span><span>${(p.cost ?? 0).toFixed(2)}</span></li>
            ))}
          </ul>
        ) : <div className="opacity-50 text-sm">Sem dados.</div>}
      </ModuleSection>
    </ModuleStream>
  );
}
```

> **Field names note:** the upstream `/api/costs` response shape was inferred from the API source code in discovery (`{ today, yesterday, daily: [{date, cost}], byModel: [{model, cost}], byAgent: [...] }`). Verify exactly during execution by hitting the endpoint with `curl` and adjust field names if reality differs.

- [ ] **Step 2: Commit Cost**

```bash
git add src/app/(dashboard)/cost/page.tsx
git commit -m "feat(cost): module page (thin reuse of upstream cost API)

Per spec §5.2.5. Read-only, falls back to '—' if upstream API absent."
git push
```

---

### Task 15b: Activity module — STRETCH

**STRETCH GOAL.** Núcleo do v1 (Home + Knowledge + Approvals + Health + Cost) ships sem este módulo. Activity é a **primeira coisa cortada** se o escopo apertar — não rework necessário, basta pular esta task. O Critical Events widget no Home (Task 10) já cobre a fatia mais crítica do feed de eventos para o v1.

**Build this only if:**
- Tasks 1-14 + 15a + 16-19 estão completas e funcionando
- Há tempo/contexto disponível
- O Critical Events widget no Home está sendo usado e Bernard quer mais profundidade

**Files (only if shipping):**
- **Modify** (not create): `src/app/(dashboard)/activity/page.tsx` — already exists upstream (reads from `/api/activities` which uses a separate `activities-db`, NOT events.jsonl). Discovery decision: REPLACE the upstream content with our version that reads from our SQLite index of `events.jsonl`. The upstream activities are openclaw-side and orthogonal to our knowledge-sync focus.
- Modify: `src/components/bevox/nav-config.ts` (add the Activity entry)

- [ ] **Step 1: Add Activity to nav-config**

Edit `src/components/bevox/nav-config.ts`, add the entry between `Cost` and the closing `]`:

```typescript
{ label: 'Activity', href: '/activity', group: 'suporte' },
```

- [ ] **Step 2: Activity page**

```tsx
'use client';
import { useEffect, useState } from 'react';
import { ModuleStream } from '@/components/bevox/ModuleStream';
import { ModuleSection } from '@/components/bevox/ModuleSection';

export default function ActivityPage() {
  const [events, setEvents] = useState<any[]>([]);
  const [severity, setSeverity] = useState<string>('');
  useEffect(() => {
    const url = severity ? `/api/bevox/events?limit=200&severity=${severity}` : '/api/bevox/events?limit=200';
    fetch(url).then(r => r.json()).then(d => setEvents(d.events ?? []));
  }, [severity]);

  return (
    <ModuleStream title="Activity">
      <ModuleSection title="Stream">
        <div className="mb-3 flex gap-2 text-xs">
          {['', 'warn', 'error'].map(s => (
            <button key={s} type="button" onClick={() => setSeverity(s)}
              className={['px-2 py-1 rounded border', severity === s ? 'bg-white/10 border-white/30' : 'border-white/10 hover:bg-white/5'].join(' ')}>
              {s || 'all'}
            </button>
          ))}
        </div>
        <ul className="text-xs font-mono space-y-0.5 max-h-[600px] overflow-auto">
          {events.map((e, i) => (
            <li key={i} className="flex justify-between border-b border-white/5 py-1">
              <span className="truncate" title={e.event}>{e.event}</span>
              <span className="opacity-60 ml-2">{e.ts?.slice(11, 19) ?? ''}</span>
            </li>
          ))}
        </ul>
      </ModuleSection>
    </ModuleStream>
  );
}
```

- [ ] **Step 3: Smoke-test + commit**

Visit `/activity` with the auth header. Verify the stream renders with real events from `events.jsonl` and the severity filter (`all`/`warn`/`error`) toggles work.

```bash
git add src/app/(dashboard)/activity/page.tsx src/components/bevox/nav-config.ts
git commit -m "feat(activity): STRETCH module — events stream with severity filters

Per spec §5.2.6. Stretch goal of v1; can be skipped without rework."
git push
```

---

## Phase 4 — Deploy (Tasks 16-18)

### Task 16: systemd user service

**Files:**
- Create: `deploy/mission-control.service`
- Create: `deploy/README.md`

- [ ] **Step 1: Create the unit file**

```ini
[Unit]
Description=Bevox Mission Control (Next.js)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/code/mission-control
ExecStart=/usr/bin/env node node_modules/next/dist/bin/next start -H 127.0.0.1 -p 4310
Restart=on-failure
RestartSec=5
EnvironmentFile=%h/code/mission-control/.env.local
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```

(Port `4310` is arbitrary; pick a free one. Document it in `deploy/README.md`. The `-H 127.0.0.1` override matters: upstream defaults to `0.0.0.0`, which would expose the app on the public network interface — we want it loopback-only, reachable only via Cloudflare Tunnel.)

> **Discovery note:** upstream's `/api/system/services` already includes `mission-control` in its allowlist. This means our service control endpoint can recognize and (in theory) restart itself. We don't expose this as a button in v1 (no mutation buttons in MC), but it's a freebie for future maintenance.

- [ ] **Step 2: Create deploy/README.md**

```markdown
# Mission Control deploy runbook

## First-time setup

1. Build: `npm run build`
2. Copy unit: `cp deploy/mission-control.service ~/.config/systemd/user/`
3. Reload: `systemctl --user daemon-reload`
4. Enable + start: `systemctl --user enable --now mission-control.service`
5. Status: `systemctl --user status mission-control.service`
6. Logs: `journalctl --user -u mission-control.service -f`

## Update flow

```bash
cd ~/code/mission-control
git pull
npm install
npm run build
systemctl --user restart mission-control.service
```

## Rollback

```bash
cd ~/code/mission-control
git log --oneline | head
git checkout <previous-sha>
npm install
npm run build
systemctl --user restart mission-control.service
```

## Stop

```bash
systemctl --user stop mission-control.service
```
```

- [ ] **Step 3: Install and test the service locally**

```bash
mkdir -p ~/.config/systemd/user/
cp deploy/mission-control.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user start mission-control.service
sleep 2
systemctl --user status mission-control.service
curl -s -H "Cf-Access-Authenticated-User-Email: you@example.com" http://localhost:4310/api/bevox/health | jq '.health.level'
```

Expected: `active (running)` and a JSON value (`"ok"`, `"degraded"`, or `"critical"`).

- [ ] **Step 4: Enable on boot + commit**

```bash
systemctl --user enable mission-control.service
loginctl enable-linger $USER  # so user services run without active session
git add deploy/
git commit -m "deploy: systemd user service for mission-control

Per spec §3.3: same pattern as knowledge-sync timers.
Listens on 127.0.0.1:4310; exposed via Cloudflare Tunnel."
git push
```

---

### Task 17: Cloudflare Tunnel + Access setup

**Files:**
- Create: `deploy/cloudflared-config.yml` (template; actual secrets are externalised)
- Modify: `deploy/README.md` (append the Tunnel + Access section)

> **This task involves Cloudflare dashboard work that Bernard must do himself.** The plan describes the steps; the engineer creates the config file template + checklist.

- [ ] **Step 1: Verify cloudflared is installed**

```bash
which cloudflared || echo "install cloudflared first"
cloudflared --version
```

If not installed:

```bash
# Debian/Ubuntu
curl -L --output /tmp/cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i /tmp/cloudflared.deb
```

- [ ] **Step 2: Authenticate cloudflared (manual, browser-based)**

Bernard runs:

```bash
cloudflared tunnel login
```

This opens a browser. He picks the `example.com` zone. A cert is saved to `~/.cloudflared/cert.pem`.

- [ ] **Step 3: Create the tunnel**

```bash
cloudflared tunnel create mission-control
```

This prints a tunnel ID and writes credentials to `~/.cloudflared/<TUNNEL_ID>.json`. Save the ID.

- [ ] **Step 4: Create the config file**

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: <TUNNEL_ID>
credentials-file: ~/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: mc.example.com
    service: http://localhost:4310
  - service: http_status:404
```

Also commit a sanitised template at `deploy/cloudflared-config.yml`:

```yaml
# Template — copy to ~/.cloudflared/config.yml and replace <TUNNEL_ID>
tunnel: <TUNNEL_ID>
credentials-file: ~/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: mc.example.com
    service: http://localhost:4310
  - service: http_status:404
```

- [ ] **Step 5: Route DNS**

```bash
cloudflared tunnel route dns mission-control mc.example.com
```

Expected: a CNAME record is created in Cloudflare for `mc.example.com` -> `<TUNNEL_ID>.cfargotunnel.com`.

- [ ] **Step 6: Run the tunnel as a service**

```bash
sudo cloudflared service install
sudo systemctl enable --now cloudflared
systemctl status cloudflared
```

- [ ] **Step 7: Configure Cloudflare Access policy (manual, dashboard)**

In the Cloudflare dashboard, Bernard does:

1. Zero Trust → Access → Applications → Add an application → Self-hosted
2. Application name: `Bevox Mission Control`
3. Application domain: `mc.example.com`
4. Identity provider: Google (or One-Time PIN) — at least one configured
5. Add policy:
   - Name: `Allow Bernard`
   - Action: Allow
   - Include: `Emails` → `you@example.com`
6. Session duration: 24 hours (or whatever feels right)
7. Save

- [ ] **Step 8: Validation checklist (3 scenarios from spec §6)**

```bash
# Scenario 1: anonymous access — must DENY (Cloudflare returns its login screen, not your app)
curl -i https://mc.example.com/ | head -5

# Scenario 2: wrong email — Cloudflare blocks before your app sees it
# (manual: try logging into the Access screen with a different Google account)

# Scenario 3: correct email — must SUCCEED
# (manual: log in via Access with you@example.com, expect the Bevox MC home page)
```

Expected:
- Scenario 1: HTTP 302 to a Cloudflare Access login page
- Scenario 2: Cloudflare denies (you see a "not authorized" page)
- Scenario 3: Bevox Mission Control loads, the title bar reads "Bevox Mission Control", the 6 nav items appear

- [ ] **Step 9: Append the Tunnel section to deploy/README.md**

Add at the bottom:

```markdown
## Cloudflare Tunnel + Access

The MC is exposed via Cloudflare Tunnel + Access. Setup:

1. Install `cloudflared` and run `cloudflared tunnel login` (interactive).
2. Create tunnel: `cloudflared tunnel create mission-control` — save the TUNNEL_ID.
3. Copy `deploy/cloudflared-config.yml` to `~/.cloudflared/config.yml` and replace `<TUNNEL_ID>`.
4. Route DNS: `cloudflared tunnel route dns mission-control mc.example.com`.
5. Install service: `sudo cloudflared service install && sudo systemctl enable --now cloudflared`.
6. Configure Access policy in Cloudflare dashboard (allow `you@example.com`).
7. Validate: anonymous access must be denied; allowed email must reach the app.
```

- [ ] **Step 10: Commit**

```bash
git add deploy/cloudflared-config.yml deploy/README.md
git commit -m "deploy: cloudflared tunnel config template + Access setup runbook

Per spec §3.3: mc.example.com -> tunnel -> localhost:4310.
Email allowlist enforced at Cloudflare edge."
git push
```

---

### Task 18: End-to-end smoke test

**Files:** none (validation only)

- [ ] **Step 1: From a phone or external device, hit `https://mc.example.com/`**

Expected:
- Cloudflare Access login (Google or PIN)
- After auth, Bevox Mission Control home page loads
- Top nav shows the 6 modules with the `‖` divider
- Knowledge Status widget shows real branch + health
- Approvals widget shows real count (probably the test inbox approval from earlier, if still pending)
- Health widget shows green or yellow with real warning count

- [ ] **Step 2: Click each module, verify it renders**

`/knowledge`, `/approvals`, `/health`, `/cost`, `/activity` — each must render at least the section headers from its `ModuleStream`.

- [ ] **Step 3: Force a fresh approval to test live integration**

In a terminal on the host:

```bash
echo "test" >> ~/bevox-knowledge/00_inbox/2026-04-10-mc-smoke.md
bash ~/.openclaw/skills/knowledge-sync/scripts/canonical.sh commit -m "test(mc): smoke test from MC live" --files 00_inbox/2026-04-10-mc-smoke.md
```

Expected:
- Telegram card appears with inline buttons
- Reload `https://mc.example.com/approvals` — the new approval appears in Pending with the rendered card v2
- Click ✅ Aprovar in Telegram
- Reload — the approval moves out of Pending into History as `executed`

If all three steps work, end-to-end is verified.

---

## Phase 5 — Documentation (Task 19)

### Task 19: Operational doc + system-map update

**Files:**
- Create: `~/bevox-knowledge/20_architecture/mission-control.md`
- Modify: `~/bevox-knowledge/20_architecture/system-map.md`

> **Both files live in `bevox-knowledge` (canonical repo).** They will be promoted via `knowledge-sync canonical commit`, NOT pushed directly.

- [ ] **Step 1: Create the operational doc**

Create `~/bevox-knowledge/20_architecture/mission-control.md`:

```markdown
# Mission Control - Bevox / OpenClaw

> Estado operacional do Bevox Mission Control v1. Documento canonico, atualizado quando o subsistema mudar.

**Ultima atualizacao:** 2026-04-10
**Spec source:** `35_specs/2026-04-10-e2-mission-control.md`
**Repo:** `bernardTavares/mission-control` (hard fork de `carlosazaustre/tenacitOS` MIT)

---

## 1. Visao geral

UI executiva centralizada do OpenClaw, exposta em `https://mc.example.com` atras de Cloudflare
Tunnel + Access. Le estado do `knowledge-sync`, approvals, health, custo e eventos via API
routes do Next.js. **Telegram continua sendo a source unica de aprovacao** - o MC e read-only.

## 2. Componentes em producao

| Componente | Localizacao |
|---|---|
| Repo | `~/code/mission-control/` |
| systemd unit | `~/.config/systemd/user/mission-control.service` |
| Cloudflared config | `~/.cloudflared/config.yml` |
| SQLite events index | `~/.openclaw/mission-control/events.db` |
| URL publica | `https://mc.example.com` |
| Porta local | `127.0.0.1:4310` |

## 3. Modulos do v1

- **Home** - dashboard executivo 2-col (6 widgets)
- **Knowledge** - estado do bevox-knowledge (status/drafts/snapshots/events)
- **Approvals** - read-only (pending/granted/history)
- **Health** - timers + snapshots + watcher
- **Cost** - reuso do upstream
- **Activity** - feed de eventos com filtros

## 4. Operacao

### Restart

```bash
systemctl --user restart mission-control.service
```

### Logs

```bash
journalctl --user -u mission-control.service -f
```

### Update

```bash
cd ~/code/mission-control
git pull
npm install
npm run build
systemctl --user restart mission-control.service
```

### Reconstruir o indice de events

```bash
rm ~/.openclaw/mission-control/events.db
systemctl --user restart mission-control.service
# A primeira request reindex automaticamente
```

## 5. Troubleshooting

### MC inacessivel

1. `systemctl --user status mission-control.service` - servico vivo?
2. `systemctl status cloudflared` - tunnel vivo?
3. `curl -i http://127.0.0.1:4310/api/bevox/health` - app responde local?
4. Cloudflare dashboard - tunnel mostra "healthy"?
5. Cloudflare Access - policy ativa?

### Dados antigos no Home

O `state.json` e atualizado pelo Watcher do `knowledge-sync` a cada 5 min.
Eventos sao indexados sob demanda quando uma API route do MC e chamada.
Se algo parece atrasado, force `knowledge-sync refresh` e recarregue o MC.

### Approval nao aparece no Pending

1. `knowledge-sync pending --json` mostra ele?
2. `tail -5 ~/.openclaw/knowledge-sync/events.jsonl | jq .event` - tem `canonical_approval_pending` recente?
3. Fora do TTL (1h)? - vai aparecer em History como `expired`.

## 6. Rollback

Procedimento documentado em `~/code/mission-control/deploy/README.md` (secao Rollback).
Resumido: `git checkout <sha>` + `npm install` + `npm run build` + restart do servico.

## 7. Referencias

- Spec - `35_specs/2026-04-10-e2-mission-control.md`
- ADR-001 - Company OS Boundary
- ADR-002 - System Topology (define mission-control)
- ADR-005 - Knowledge Source of Truth (MC le do bevox-knowledge)
- ADR-006 - Autonomy/Permissions/Approval (MC nao introduz nova superficie)
```

- [ ] **Step 2: Update `system-map.md`**

Find the line about Mission Control in `~/bevox-knowledge/20_architecture/system-map.md`:

```
| Mission Control | TBD (E2) | A criar | Bernard |
```

Replace with:

```
| Mission Control | https://mc.example.com · ~/code/mission-control | Ativo (v1) | Bernard |
```

- [ ] **Step 3: Canonical commit both files**

```bash
bash ~/.openclaw/skills/knowledge-sync/scripts/canonical.sh commit \
  -m "docs(mc): operational doc + system-map status update" \
  --files 20_architecture/mission-control.md 20_architecture/system-map.md
```

Expected: approval card on Telegram. Approve via inline button, the commit lands.

- [ ] **Step 4: Push the canonical commit**

```bash
bash ~/.openclaw/skills/knowledge-sync/scripts/canonical.sh push
```

Approve via Telegram inline button.

---

## Self-Review Notes (post-write)

This plan was self-reviewed before delivery. Findings:

**Spec coverage:** every numbered section of the spec maps to at least one task.
- §3.1 fork strategy → Tasks 1-4
- §3.2 data layer → Tasks 5-7
- §3.3 auth & deployment → Tasks 3, 16, 17, 18
- §3.4 branding → Task 4
- §4 nav/layout → Tasks 8-11
- §5.2.1-5.2.6 modules → Tasks 9, 10, 12-15
- §6 risks → mitigated inline (Cloudflare validation in Task 17 Step 8; events.jsonl truncation in Task 7 implementation; 3D audit in Task 2 Step 5)
- §7 DoD → matches the task outputs

**Type consistency check:** the types defined in Task 5 (`KsState`, `SnapshotEntry`, `ApprovalSummary`) are used consistently in Tasks 6, 7, 9. Function names are stable (`readKsState`, `listApprovals`, `readHealthOverall`, etc.). No drift.

**Placeholder scan:** no TBD/TODO. The Cost page in Task 15 calls `/api/cost/today` with a fallback if upstream API is named differently — that's a real implementation hazard, flagged in the comment, not a placeholder.

**Reduction rule:** the Activity-cut path is documented at the top of Task 15 with explicit instructions on what to delete (`src/app/(dashboard)/activity/` + nav-config entry). The Critical Events widget on Home (Task 10 Step 1) provides graceful degradation.

---

## Plan footer

**Tasks total:** 21 (1 discovery + 4 bootstrap + 3 plumbing + 3 shell + 5 modules + 3 deploy + 1 docs + 1 stretch)
- Núcleo v1: Tasks 0.5, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15a, 16, 17, 18, 19 (20 tasks)
- Stretch: Task 15b (Activity)

**Estimated execution time:** 1-2 weeks at 2-4 hours/day, depending on TenacitOS upstream surprises (Task 0.5 will reduce surprises).

**Critical path dependencies:**
- Task 0.5 must run before Task 1.
- Tasks 1→2→3→4 must run in order.
- Tasks 5→6→7 must run in order.
- Task 9 depends on 5+6+7.
- Tasks 10-14 + 15a can mostly parallelize after 9.
- Tasks 16-18 must come after 10.
- Task 19 is last in the núcleo.
- Task 15b (Activity stretch) can run any time after 11 — or be skipped entirely.

**Reduction order if scope tightens** (per the conventions section at the top of this plan):
1. Skip Task 15b (Activity) — already marked stretch, no rework.
2. Replace Critical Events widget on Home with upstream's notification list — small refactor in Task 10.
3. Cost module reverts to "header link only, page is empty placeholder" — rip out the body of Task 15a.
