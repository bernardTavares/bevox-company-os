# E2 / F-projects-dashboard W1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar `/projects` (list read-only) + `/projects/[id]` (drill-down) no Mission Control, consolidando visibilidade dos 6 projetos canônicos com 4 health checks filesystem-based.

**Architecture:** Página client-side em MC consumindo 2 API routes novas. Fonte de projetos hardcoded (alinhada com ADR-002 topology, não com `projects.yml` do kanban). Health checks puros (determinísticos, testáveis). Zero mutation (W1 é read-only; mutations ficam pra W2/W3/W4).

**Tech Stack:** Next.js 15 App Router, React 19, TypeScript, vitest 4.1, Tailwind, lucide-react. Sem novos pacotes.

**Spec:** `bevox-knowledge/35_specs/company-os/2026-04-24-e2-projects-dashboard-w1.md` (commit `b04ae24`)
**Cadência:** commit auto por task (feedback_commit_cadence); pausa só pro merge canônico.

---

## File Structure

**mission-control/ (trabalho único):**

```
src/lib/projects/
├── types.ts            — CRIAR. Dot, ProjectSummary, ProjectDetail, Sprint, Task
├── canonical.ts        — CRIAR. CANONICAL_PROJECTS (6 items)
└── health.ts           — CRIAR. checkBotHealth, checkWorkspaceHealth, checkKanbanHealth, checkKnowledgeHealth

src/app/api/projects/
├── route.ts            — CRIAR. GET /api/projects → ProjectSummary[]
└── [id]/route.ts       — CRIAR. GET /api/projects/[id] → ProjectDetail

src/app/(dashboard)/projects/
├── page.tsx            — CRIAR. List page (client)
├── ProjectCard.tsx     — CRIAR
├── HealthDots.tsx      — CRIAR
└── [id]/
    ├── page.tsx        — CRIAR. Detail page (client)
    ├── ProjectHeader.tsx    — CRIAR
    ├── HealthDetails.tsx    — CRIAR
    ├── ProjectLinks.tsx     — CRIAR
    ├── SprintList.tsx       — CRIAR
    └── TasksInFlight.tsx    — CRIAR

src/components/Sidebar.tsx  — MODIFY. Add /projects entry antes de /roadmap

tests/lib/projects/
└── health.test.ts      — CRIAR. 12+ casos (3 estados × 4 checks)

tests/app/api/projects/
├── list.route.test.ts  — CRIAR
└── detail.route.test.ts — CRIAR
```

**bevox-knowledge/ (tracker sync pós-merge):**

```
40_roadmap/_shared/delivery-tracker.yml  — MODIFY. E2 ganha entry F-projects-dashboard/W1 delivered
```

---

## Task 1: Branch setup

**Files:** nenhum

- [ ] **Step 1: Confirmar main limpo + criar branch**

```bash
cd ~/code/mission-control
git status --short
git checkout main
git pull --ff-only
git checkout -b feat/e2-projects-dashboard-w1
git branch --show-current
```

Expected: `feat/e2-projects-dashboard-w1`. Se dirty: STOP, report BLOCKED.

---

## Task 2: `src/lib/projects/types.ts`

**Files:**
- Create: `src/lib/projects/types.ts`

- [ ] **Step 1: Criar arquivo**

Conteúdo:

```typescript
/**
 * Shared types for /projects page (E2/F-projects-dashboard W1).
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-24-e2-projects-dashboard-w1.md
 */

export type Dot = "ok" | "partial" | "missing";

export interface ProjectHealth {
  bot: Dot;
  workspace: Dot;
  kanban: Dot;
  knowledge: Dot;
}

export interface ProjectCounts {
  sprints_active: number;
  tasks_in_progress: number;
}

export interface ProjectSummary {
  id: string;
  name: string;
  description: string;
  health: ProjectHealth;
  counts: ProjectCounts;
}

/** Sprint shape from kanban state.json. */
export interface Sprint {
  id: string;
  name: string;
  state: "current" | "next" | "closed" | string;
  project: string | null;
  created_at: string;
  closed_at: string | null;
  created_by?: string;
}

/** Task shape (subset relevant to /projects UI). */
export interface Task {
  id: string;
  title: string;
  status: string;
  project: string | null;
  sprint_id: string | null;
  blocked: boolean;
  blocked_reason?: string | null;
  updated_at: string;
}

export interface HealthDetails {
  bot: {
    present: boolean;
    envPath: string | null;
    systemdService: string | null;
  };
  workspace: {
    present: boolean;
    dir: string | null;
    files: string[];
  };
  kanban: {
    present: boolean;
    tasks_total: number;
  };
  knowledge: {
    present: boolean;
    specsCount: number;
    adrsCount: number;
    prdsCount: number;
  };
}

export interface ProjectLinks {
  telegram_bot_env: string | null;
  workspace_dir: string | null;
  knowledge_specs_dir: string | null;
  kanban_filter_url: string;
}

export interface ProjectDetail extends ProjectSummary {
  health_details: HealthDetails;
  links: ProjectLinks;
  sprints: {
    active: Sprint[];
    closed: Sprint[];
  };
  tasks_in_flight: Task[];
}
```

- [ ] **Step 2: Typecheck + commit**

```bash
cd ~/code/mission-control
npx tsc --noEmit 2>&1 | grep -v 'module-components.test.tsx\|deps.route.test.ts' | head -5
git add src/lib/projects/types.ts
git commit -m "$(cat <<'EOF'
feat(projects): shared types (E2/F-projects-dashboard W1)

Types for list + drill-down: Dot, ProjectSummary, ProjectDetail,
HealthDetails, ProjectLinks, Sprint, Task.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `src/lib/projects/canonical.ts`

**Files:**
- Create: `src/lib/projects/canonical.ts`

- [ ] **Step 1: Criar arquivo**

```typescript
/**
 * Canonical projects list aligned with ADR-002 topology.
 *
 * Hardcoded (stable by design — adding a project requires a new ADR).
 * Does NOT depend on kanban `projects.yml` which is a looser list
 * including transient entries like test-project, vox (agent), etc.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-24-e2-projects-dashboard-w1.md §3.1
 */

export interface CanonicalProject {
  readonly id: string;
  readonly name: string;
  readonly description: string;
}

export const CANONICAL_PROJECTS: readonly CanonicalProject[] = [
  {
    id: "bevox-backend",
    name: "Bevox Backend",
    description: "Backend compartilhado (auth, tenants, agenda, pagamentos, notificações, auditoria)",
  },
  {
    id: "bevox-console",
    name: "Bevox Console",
    description: "Super-admin / backoffice interno da Bevox",
  },
  {
    id: "bevox-harness",
    name: "Bevox Harness",
    description: "Runtime agent-first da secretária IA",
  },
  {
    id: "bevox-mobile",
    name: "Bevox Mobile",
    description: "App mobile operador do cliente",
  },
  {
    id: "bevox-web",
    name: "Bevox Web",
    description: "App web do cliente",
  },
  {
    id: "company-os",
    name: "Company OS",
    description: "Mission Control, Vox, Knowledge-Sync, Agent Registry, Approval Center",
  },
] as const;

export function isCanonicalProject(id: string): boolean {
  return CANONICAL_PROJECTS.some((p) => p.id === id);
}

export function getCanonicalProject(id: string): CanonicalProject | null {
  return CANONICAL_PROJECTS.find((p) => p.id === id) ?? null;
}
```

- [ ] **Step 2: Commit**

```bash
cd ~/code/mission-control
git add src/lib/projects/canonical.ts
git commit -m "$(cat <<'EOF'
feat(projects): canonical 6-project list (E2/F-projects-dashboard W1)

ADR-002 topology. Hardcoded (adding project = new ADR).
Helpers isCanonicalProject, getCanonicalProject.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `src/lib/projects/health.ts` + tests (TDD)

**Files:**
- Create: `src/lib/projects/health.ts`
- Create: `tests/lib/projects/health.test.ts`

- [ ] **Step 1: Write failing tests**

```typescript
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { mkdirSync, writeFileSync, rmSync } from "fs";
import path from "path";
import os from "os";

import {
  checkBotHealth,
  checkWorkspaceHealth,
  checkKanbanHealth,
  checkKnowledgeHealth,
} from "@/lib/projects/health";

const TMP_OPENCLAW = path.join(os.tmpdir(), `mc-projects-oc-${process.pid}`);
const TMP_KNOWLEDGE = path.join(os.tmpdir(), `mc-projects-kn-${process.pid}`);

function reset() {
  rmSync(TMP_OPENCLAW, { recursive: true, force: true });
  rmSync(TMP_KNOWLEDGE, { recursive: true, force: true });
  mkdirSync(TMP_OPENCLAW, { recursive: true });
  mkdirSync(TMP_KNOWLEDGE, { recursive: true });
}

beforeEach(reset);
afterEach(reset);

describe("checkBotHealth", () => {
  it("returns ok when bot env file exists", () => {
    mkdirSync(path.join(TMP_OPENCLAW, "gateway", "bots"), { recursive: true });
    writeFileSync(path.join(TMP_OPENCLAW, "gateway", "bots", "bevox-mobile.env"), "TOKEN=x\n");
    expect(checkBotHealth("bevox-mobile", TMP_OPENCLAW)).toBe("ok");
  });

  it("returns missing when bot env file absent", () => {
    expect(checkBotHealth("bevox-mobile", TMP_OPENCLAW)).toBe("missing");
  });

  it("returns missing when gateway dir absent", () => {
    expect(checkBotHealth("bevox-mobile", TMP_OPENCLAW)).toBe("missing");
  });
});

describe("checkWorkspaceHealth", () => {
  it("returns ok when workspace dir + IDENTITY.md exist", () => {
    const ws = path.join(TMP_OPENCLAW, "workspace-bevox-mobile");
    mkdirSync(ws, { recursive: true });
    writeFileSync(path.join(ws, "IDENTITY.md"), "# bevox-mobile\n");
    expect(checkWorkspaceHealth("bevox-mobile", TMP_OPENCLAW)).toBe("ok");
  });

  it("returns partial when workspace dir exists but no IDENTITY.md", () => {
    mkdirSync(path.join(TMP_OPENCLAW, "workspace-bevox-mobile"), { recursive: true });
    expect(checkWorkspaceHealth("bevox-mobile", TMP_OPENCLAW)).toBe("partial");
  });

  it("returns missing when workspace dir absent", () => {
    expect(checkWorkspaceHealth("bevox-mobile", TMP_OPENCLAW)).toBe("missing");
  });
});

describe("checkKanbanHealth", () => {
  it("returns ok when id in projects.yml", () => {
    mkdirSync(path.join(TMP_OPENCLAW, "kanban-tasks"), { recursive: true });
    writeFileSync(
      path.join(TMP_OPENCLAW, "kanban-tasks", "projects.yml"),
      "projects:\n  - bevox-mobile\n  - bevox-backend\n",
    );
    expect(checkKanbanHealth("bevox-mobile", TMP_OPENCLAW)).toBe("ok");
  });

  it("returns missing when id absent from projects.yml", () => {
    mkdirSync(path.join(TMP_OPENCLAW, "kanban-tasks"), { recursive: true });
    writeFileSync(
      path.join(TMP_OPENCLAW, "kanban-tasks", "projects.yml"),
      "projects:\n  - bevox-backend\n",
    );
    expect(checkKanbanHealth("bevox-mobile", TMP_OPENCLAW)).toBe("missing");
  });

  it("returns missing when projects.yml absent", () => {
    expect(checkKanbanHealth("bevox-mobile", TMP_OPENCLAW)).toBe("missing");
  });
});

describe("checkKnowledgeHealth", () => {
  it("returns ok when 35_specs/<id>/ has .md files (non-gitkeep)", () => {
    const dir = path.join(TMP_KNOWLEDGE, "35_specs", "bevox-mobile");
    mkdirSync(dir, { recursive: true });
    writeFileSync(path.join(dir, "2026-04-24-some-spec.md"), "# spec\n");
    expect(checkKnowledgeHealth("bevox-mobile", TMP_KNOWLEDGE)).toBe("ok");
  });

  it("returns missing when only .gitkeep", () => {
    const dir = path.join(TMP_KNOWLEDGE, "35_specs", "bevox-mobile");
    mkdirSync(dir, { recursive: true });
    writeFileSync(path.join(dir, ".gitkeep"), "");
    expect(checkKnowledgeHealth("bevox-mobile", TMP_KNOWLEDGE)).toBe("missing");
  });

  it("returns missing when subfolder absent", () => {
    mkdirSync(path.join(TMP_KNOWLEDGE, "35_specs"), { recursive: true });
    expect(checkKnowledgeHealth("bevox-mobile", TMP_KNOWLEDGE)).toBe("missing");
  });
});
```

- [ ] **Step 2: Run — verify fail**

```bash
cd ~/code/mission-control
NODE_OPTIONS='--experimental-require-module' npx vitest run tests/lib/projects/health.test.ts 2>&1 | tail -10
```

Expected: module not found.

- [ ] **Step 3: Implement `src/lib/projects/health.ts`**

```typescript
import { existsSync, readdirSync, readFileSync, statSync } from "fs";
import path from "path";

import type { Dot } from "@/lib/projects/types";

/**
 * Health checks for a canonical project.
 *
 * Each check is pure: given a projectId + base dirs, returns a Dot
 * ("ok" | "partial" | "missing"). No side effects. Graceful on filesystem
 * errors (returns "missing" rather than throwing).
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-24-e2-projects-dashboard-w1.md §3.2
 */

export function checkBotHealth(projectId: string, openclawDir: string): Dot {
  const envFile = path.join(openclawDir, "gateway", "bots", `${projectId}.env`);
  try {
    return existsSync(envFile) && statSync(envFile).isFile() ? "ok" : "missing";
  } catch {
    return "missing";
  }
}

export function checkWorkspaceHealth(projectId: string, openclawDir: string): Dot {
  const wsDir = path.join(openclawDir, `workspace-${projectId}`);
  try {
    if (!existsSync(wsDir) || !statSync(wsDir).isDirectory()) return "missing";
    const identity = path.join(wsDir, "IDENTITY.md");
    return existsSync(identity) && statSync(identity).isFile() ? "ok" : "partial";
  } catch {
    return "missing";
  }
}

export function checkKanbanHealth(projectId: string, openclawDir: string): Dot {
  const yml = path.join(openclawDir, "kanban-tasks", "projects.yml");
  try {
    if (!existsSync(yml)) return "missing";
    const raw = readFileSync(yml, "utf-8");
    // Simple line match — avoids adding yaml dep for this one check.
    // Looks for lines like "  - bevox-mobile" at any indent.
    const lines = raw.split(/\r?\n/);
    for (const line of lines) {
      const m = line.match(/^\s*-\s+(\S+)\s*$/);
      if (m && m[1] === projectId) return "ok";
    }
    return "missing";
  } catch {
    return "missing";
  }
}

export function checkKnowledgeHealth(projectId: string, bevoxKnowledgeDir: string): Dot {
  const dir = path.join(bevoxKnowledgeDir, "35_specs", projectId);
  try {
    if (!existsSync(dir) || !statSync(dir).isDirectory()) return "missing";
    const entries = readdirSync(dir)
      .filter((n) => n !== ".gitkeep")
      .filter((n) => n.endsWith(".md"));
    return entries.length > 0 ? "ok" : "missing";
  } catch {
    return "missing";
  }
}
```

- [ ] **Step 4: Run tests — verify all pass**

```bash
cd ~/code/mission-control
NODE_OPTIONS='--experimental-require-module' npx vitest run tests/lib/projects/health.test.ts 2>&1 | tail -10
```

Expected: 12 tests pass (3 per check × 4 checks).

- [ ] **Step 5: Commit**

```bash
cd ~/code/mission-control
git add src/lib/projects/health.ts tests/lib/projects/health.test.ts
git commit -m "$(cat <<'EOF'
feat(projects): 4 health checks + TDD (E2/F-projects-dashboard W1)

Pure fns checkBotHealth, checkWorkspaceHealth, checkKanbanHealth,
checkKnowledgeHealth. Graceful on filesystem errors (returns "missing"
never throws). Vocabulário ok|partial|missing.

- bot: env file em gateway/bots/<id>.env
- workspace: dir + IDENTITY.md (partial = dir sem IDENTITY)
- kanban: id in projects.yml via line regex (sem yaml dep)
- knowledge: 35_specs/<id>/ com ≥1 .md ≠ .gitkeep

12 tests: 3 estados × 4 checks.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `GET /api/projects` route + tests

**Files:**
- Create: `src/app/api/projects/route.ts`
- Create: `tests/app/api/projects/list.route.test.ts`

- [ ] **Step 1: Write failing test**

```typescript
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { writeFileSync, mkdirSync, rmSync } from "fs";
import path from "path";
import os from "os";

import { GET } from "@/app/api/projects/route";

const TMP = path.join(os.tmpdir(), `mc-projects-list-${process.pid}`);
const OC = path.join(TMP, "openclaw");
const KN = path.join(TMP, "knowledge");

function reset() {
  rmSync(TMP, { recursive: true, force: true });
  mkdirSync(OC, { recursive: true });
  mkdirSync(KN, { recursive: true });
  process.env.MC_HOME = TMP;
  process.env.BEVOX_KNOWLEDGE_DIR = KN;
}

beforeEach(() => {
  reset();
});
afterEach(() => {
  rmSync(TMP, { recursive: true, force: true });
  delete process.env.MC_HOME;
  delete process.env.BEVOX_KNOWLEDGE_DIR;
});

describe("GET /api/projects", () => {
  it("returns 6 canonical projects with health defaults to missing when nothing setup", async () => {
    const res = await GET();
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.projects).toHaveLength(6);
    const ids = body.projects.map((p: any) => p.id).sort();
    expect(ids).toEqual([
      "bevox-backend",
      "bevox-console",
      "bevox-harness",
      "bevox-mobile",
      "bevox-web",
      "company-os",
    ]);
    const bm = body.projects.find((p: any) => p.id === "bevox-mobile");
    expect(bm.health).toEqual({
      bot: "missing",
      workspace: "missing",
      kanban: "missing",
      knowledge: "missing",
    });
    expect(bm.counts).toEqual({ sprints_active: 0, tasks_in_progress: 0 });
  });

  it("reports ok health when all 4 resources exist for a project", async () => {
    // bot
    mkdirSync(path.join(OC, "gateway", "bots"), { recursive: true });
    writeFileSync(path.join(OC, "gateway", "bots", "bevox-mobile.env"), "TOKEN=x\n");
    // workspace
    mkdirSync(path.join(OC, "workspace-bevox-mobile"), { recursive: true });
    writeFileSync(path.join(OC, "workspace-bevox-mobile", "IDENTITY.md"), "# id\n");
    // kanban
    mkdirSync(path.join(OC, "kanban-tasks"), { recursive: true });
    writeFileSync(
      path.join(OC, "kanban-tasks", "projects.yml"),
      "projects:\n  - bevox-mobile\n",
    );
    // knowledge
    mkdirSync(path.join(KN, "35_specs", "bevox-mobile"), { recursive: true });
    writeFileSync(path.join(KN, "35_specs", "bevox-mobile", "2026-04-24-foo.md"), "# foo\n");

    const res = await GET();
    const body = await res.json();
    const bm = body.projects.find((p: any) => p.id === "bevox-mobile");
    expect(bm.health).toEqual({
      bot: "ok",
      workspace: "ok",
      kanban: "ok",
      knowledge: "ok",
    });
  });

  it("derives counts from kanban state.json when present", async () => {
    mkdirSync(path.join(OC, "kanban-tasks"), { recursive: true });
    writeFileSync(
      path.join(OC, "kanban-tasks", "state.json"),
      JSON.stringify({
        schema_version: 1,
        sprints: [
          { id: "s1", name: "S1", state: "current", project: "bevox-mobile" },
          { id: "s2", name: "S2", state: "next", project: "bevox-mobile" },
          { id: "s3", name: "S3", state: "closed", project: "bevox-mobile" },
        ],
        tasks: [
          { id: "T-1", status: "in_progress", project: "bevox-mobile", title: "x", sprint_id: "s1", blocked: false, updated_at: "2026-04-24" },
          { id: "T-2", status: "ready", project: "bevox-mobile", title: "y", sprint_id: "s1", blocked: false, updated_at: "2026-04-24" },
          { id: "T-3", status: "in_progress", project: "bevox-backend", title: "z", sprint_id: null, blocked: false, updated_at: "2026-04-24" },
        ],
      }),
    );
    const res = await GET();
    const body = await res.json();
    const bm = body.projects.find((p: any) => p.id === "bevox-mobile");
    expect(bm.counts.sprints_active).toBe(2); // current + next
    expect(bm.counts.tasks_in_progress).toBe(1);
    const bb = body.projects.find((p: any) => p.id === "bevox-backend");
    expect(bb.counts.sprints_active).toBe(0);
    expect(bb.counts.tasks_in_progress).toBe(1);
  });

  it("handles missing state.json gracefully (counts=0)", async () => {
    const res = await GET();
    const body = await res.json();
    for (const p of body.projects) {
      expect(p.counts.sprints_active).toBe(0);
      expect(p.counts.tasks_in_progress).toBe(0);
    }
  });
});
```

- [ ] **Step 2: Run — expect fail**

```bash
cd ~/code/mission-control
NODE_OPTIONS='--experimental-require-module' npx vitest run tests/app/api/projects/list.route.test.ts 2>&1 | tail -10
```

- [ ] **Step 3: Implement `src/app/api/projects/route.ts`**

```typescript
import { NextResponse } from "next/server";
import { existsSync, readFileSync } from "fs";
import path from "path";
import os from "os";

import { PATHS } from "@/lib/bevox/paths";
import { CANONICAL_PROJECTS } from "@/lib/projects/canonical";
import {
  checkBotHealth,
  checkKanbanHealth,
  checkKnowledgeHealth,
  checkWorkspaceHealth,
} from "@/lib/projects/health";
import type { ProjectSummary, Sprint, Task } from "@/lib/projects/types";

export const dynamic = "force-dynamic";

/**
 * GET /api/projects
 *
 * Returns the 6 canonical projects (ADR-002) with 4 health checks
 * + derived counts from kanban state.json.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-24-e2-projects-dashboard-w1.md §3
 */

function resolveOpenclawDir(): string {
  // MC_HOME override (test friendly); else os.homedir()/.openclaw
  const mcHome = process.env.MC_HOME;
  return mcHome
    ? path.join(mcHome, "openclaw")
    : PATHS.openclawHome;
}

function resolveBevoxKnowledgeDir(): string {
  return process.env.BEVOX_KNOWLEDGE_DIR ?? path.join(os.homedir(), "bevox-knowledge");
}

function readKanbanState(openclawDir: string): { sprints: Sprint[]; tasks: Task[] } {
  const p = path.join(openclawDir, "kanban-tasks", "state.json");
  if (!existsSync(p)) return { sprints: [], tasks: [] };
  try {
    const data = JSON.parse(readFileSync(p, "utf-8"));
    return {
      sprints: Array.isArray(data.sprints) ? data.sprints : [],
      tasks: Array.isArray(data.tasks) ? data.tasks : [],
    };
  } catch {
    return { sprints: [], tasks: [] };
  }
}

export async function GET() {
  const openclawDir = resolveOpenclawDir();
  const knowledgeDir = resolveBevoxKnowledgeDir();
  const { sprints, tasks } = readKanbanState(openclawDir);

  const projects: ProjectSummary[] = CANONICAL_PROJECTS.map((p) => ({
    id: p.id,
    name: p.name,
    description: p.description,
    health: {
      bot: checkBotHealth(p.id, openclawDir),
      workspace: checkWorkspaceHealth(p.id, openclawDir),
      kanban: checkKanbanHealth(p.id, openclawDir),
      knowledge: checkKnowledgeHealth(p.id, knowledgeDir),
    },
    counts: {
      sprints_active: sprints.filter(
        (s) => s.project === p.id && (s.state === "current" || s.state === "next"),
      ).length,
      tasks_in_progress: tasks.filter(
        (t) => t.project === p.id && t.status === "in_progress",
      ).length,
    },
  }));

  return NextResponse.json({
    generated_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
    projects,
  });
}
```

Nota: `MC_HOME` já é padrão do MC (testável via env override). Em produção cai no `PATHS.openclawHome`.

- [ ] **Step 4: Run tests — verify pass**

```bash
cd ~/code/mission-control
NODE_OPTIONS='--experimental-require-module' npx vitest run tests/app/api/projects/list.route.test.ts 2>&1 | tail -10
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
cd ~/code/mission-control
git add src/app/api/projects/route.ts tests/app/api/projects/list.route.test.ts
git commit -m "$(cat <<'EOF'
feat(api): GET /api/projects (E2/F-projects-dashboard W1)

Returns 6 canonical projects with health (4 dots) + counts derived
from kanban state.json. Resolves openclawDir via MC_HOME override
(test) ou PATHS.openclawHome (prod/dev). Knowledge dir via
BEVOX_KNOWLEDGE_DIR.

4 tests: 6 ids validation, all-ok scenario, counts derivation from
kanban state, graceful when state.json missing.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `GET /api/projects/[id]` route + tests

**Files:**
- Create: `src/app/api/projects/[id]/route.ts`
- Create: `tests/app/api/projects/detail.route.test.ts`

- [ ] **Step 1: Write failing test**

```typescript
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { writeFileSync, mkdirSync, rmSync } from "fs";
import path from "path";
import os from "os";

import { GET } from "@/app/api/projects/[id]/route";

const TMP = path.join(os.tmpdir(), `mc-projects-detail-${process.pid}`);
const OC = path.join(TMP, "openclaw");
const KN = path.join(TMP, "knowledge");

function reset() {
  rmSync(TMP, { recursive: true, force: true });
  mkdirSync(OC, { recursive: true });
  mkdirSync(KN, { recursive: true });
  process.env.MC_HOME = TMP;
  process.env.BEVOX_KNOWLEDGE_DIR = KN;
}

function buildParams(id: string) {
  return { params: Promise.resolve({ id }) };
}

beforeEach(reset);
afterEach(() => {
  rmSync(TMP, { recursive: true, force: true });
  delete process.env.MC_HOME;
  delete process.env.BEVOX_KNOWLEDGE_DIR;
});

describe("GET /api/projects/[id]", () => {
  it("404 when id is not canonical", async () => {
    const res = await GET({} as Request, buildParams("not-a-real-project"));
    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.error).toBe("project_not_canonical");
  });

  it("200 with health_details and empty sprints/tasks when nothing setup", async () => {
    const res = await GET({} as Request, buildParams("bevox-mobile"));
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.id).toBe("bevox-mobile");
    expect(body.health_details.bot.present).toBe(false);
    expect(body.health_details.workspace.present).toBe(false);
    expect(body.health_details.kanban.present).toBe(false);
    expect(body.health_details.knowledge.present).toBe(false);
    expect(body.sprints.active).toEqual([]);
    expect(body.sprints.closed).toEqual([]);
    expect(body.tasks_in_flight).toEqual([]);
    expect(body.links.kanban_filter_url).toBe("/kanban?project=bevox-mobile");
  });

  it("populates sprints and tasks_in_flight from state.json", async () => {
    mkdirSync(path.join(OC, "kanban-tasks"), { recursive: true });
    writeFileSync(
      path.join(OC, "kanban-tasks", "state.json"),
      JSON.stringify({
        sprints: [
          { id: "s1", name: "S1", state: "current", project: "bevox-mobile", created_at: "2026-04-01", closed_at: null },
          { id: "s2", name: "S2", state: "next", project: "bevox-mobile", created_at: "2026-04-02", closed_at: null },
          { id: "s3", name: "S3", state: "closed", project: "bevox-mobile", created_at: "2026-03-01", closed_at: "2026-03-15" },
          { id: "sX", name: "SX", state: "current", project: "other", created_at: "2026-04-01", closed_at: null },
        ],
        tasks: [
          { id: "T-1", title: "in-flight", status: "in_progress", project: "bevox-mobile", sprint_id: "s1", blocked: false, updated_at: "2026-04-24" },
          { id: "T-2", title: "blocked", status: "blocked", project: "bevox-mobile", sprint_id: "s1", blocked: true, updated_at: "2026-04-23" },
          { id: "T-3", title: "ready", status: "ready", project: "bevox-mobile", sprint_id: "s1", blocked: false, updated_at: "2026-04-24" },
          { id: "T-4", title: "other-proj", status: "in_progress", project: "other", sprint_id: null, blocked: false, updated_at: "2026-04-24" },
        ],
      }),
    );

    const res = await GET({} as Request, buildParams("bevox-mobile"));
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.sprints.active.map((s: any) => s.id)).toEqual(["s1", "s2"]);
    expect(body.sprints.closed.map((s: any) => s.id)).toEqual(["s3"]);
    expect(body.tasks_in_flight.map((t: any) => t.id).sort()).toEqual(["T-1", "T-2"]);
  });

  it("expands health_details paths when resources exist", async () => {
    mkdirSync(path.join(OC, "gateway", "bots"), { recursive: true });
    writeFileSync(path.join(OC, "gateway", "bots", "bevox-mobile.env"), "TOKEN=x\n");
    mkdirSync(path.join(OC, "workspace-bevox-mobile"), { recursive: true });
    writeFileSync(path.join(OC, "workspace-bevox-mobile", "IDENTITY.md"), "x");
    writeFileSync(path.join(OC, "workspace-bevox-mobile", "SOUL.md"), "x");

    const res = await GET({} as Request, buildParams("bevox-mobile"));
    const body = await res.json();
    expect(body.health_details.bot.present).toBe(true);
    expect(body.health_details.bot.envPath).toContain("gateway/bots/bevox-mobile.env");
    expect(body.health_details.workspace.present).toBe(true);
    expect(body.health_details.workspace.files.sort()).toEqual(["IDENTITY.md", "SOUL.md"]);
    expect(body.links.telegram_bot_env).toContain("bevox-mobile.env");
    expect(body.links.workspace_dir).toContain("workspace-bevox-mobile");
  });
});
```

- [ ] **Step 2: Run — expect fail**

```bash
cd ~/code/mission-control
NODE_OPTIONS='--experimental-require-module' npx vitest run tests/app/api/projects/detail.route.test.ts 2>&1 | tail -10
```

- [ ] **Step 3: Implement `src/app/api/projects/[id]/route.ts`**

```typescript
import { NextResponse } from "next/server";
import { existsSync, readFileSync, readdirSync, statSync } from "fs";
import path from "path";
import os from "os";

import { PATHS } from "@/lib/bevox/paths";
import { CANONICAL_PROJECTS, getCanonicalProject } from "@/lib/projects/canonical";
import {
  checkBotHealth,
  checkKanbanHealth,
  checkKnowledgeHealth,
  checkWorkspaceHealth,
} from "@/lib/projects/health";
import type {
  ProjectDetail,
  Sprint,
  Task,
} from "@/lib/projects/types";

export const dynamic = "force-dynamic";

/**
 * GET /api/projects/[id]
 *
 * Returns ProjectDetail: health_details expandido, sprints (active + closed top 5),
 * tasks_in_flight (in_progress + blocked), links.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-24-e2-projects-dashboard-w1.md §3 §4
 */

function resolveOpenclawDir(): string {
  const mcHome = process.env.MC_HOME;
  return mcHome
    ? path.join(mcHome, "openclaw")
    : PATHS.openclawHome;
}

function resolveBevoxKnowledgeDir(): string {
  return process.env.BEVOX_KNOWLEDGE_DIR ?? path.join(os.homedir(), "bevox-knowledge");
}

function readKanbanState(openclawDir: string): { sprints: Sprint[]; tasks: Task[] } {
  const p = path.join(openclawDir, "kanban-tasks", "state.json");
  if (!existsSync(p)) return { sprints: [], tasks: [] };
  try {
    const data = JSON.parse(readFileSync(p, "utf-8"));
    return {
      sprints: Array.isArray(data.sprints) ? data.sprints : [],
      tasks: Array.isArray(data.tasks) ? data.tasks : [],
    };
  } catch {
    return { sprints: [], tasks: [] };
  }
}

function workspaceFiles(dir: string): string[] {
  try {
    return readdirSync(dir)
      .filter((n) => !n.startsWith("."))
      .filter((n) => {
        try {
          return statSync(path.join(dir, n)).isFile();
        } catch {
          return false;
        }
      });
  } catch {
    return [];
  }
}

function countFiles(dir: string, ext: string = ".md"): number {
  if (!existsSync(dir)) return 0;
  try {
    return readdirSync(dir)
      .filter((n) => n !== ".gitkeep")
      .filter((n) => n.endsWith(ext)).length;
  } catch {
    return 0;
  }
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const canonical = getCanonicalProject(id);
  if (!canonical) {
    return NextResponse.json(
      { error: "project_not_canonical", detail: `${id} is not in CANONICAL_PROJECTS` },
      { status: 404 },
    );
  }

  const openclawDir = resolveOpenclawDir();
  const knowledgeDir = resolveBevoxKnowledgeDir();
  const { sprints, tasks } = readKanbanState(openclawDir);

  const botEnv = path.join(openclawDir, "gateway", "bots", `${id}.env`);
  const wsDir = path.join(openclawDir, `workspace-${id}`);
  const specsDir = path.join(knowledgeDir, "35_specs", id);
  const adrsDir = path.join(knowledgeDir, "30_adr", id);
  const prdsDir = path.join(knowledgeDir, "10_prd", id);

  const botOk = checkBotHealth(id, openclawDir);
  const wsOk = checkWorkspaceHealth(id, openclawDir);
  const kbOk = checkKanbanHealth(id, openclawDir);
  const knOk = checkKnowledgeHealth(id, knowledgeDir);

  const projectSprints = sprints.filter((s) => s.project === id);
  const active = projectSprints.filter(
    (s) => s.state === "current" || s.state === "next",
  );
  const closed = projectSprints
    .filter((s) => s.state === "closed")
    .sort((a, b) => (b.closed_at ?? "").localeCompare(a.closed_at ?? ""))
    .slice(0, 5);

  const tasksInFlight = tasks
    .filter((t) => t.project === id)
    .filter((t) => t.status === "in_progress" || t.status === "blocked")
    .sort((a, b) => (b.updated_at ?? "").localeCompare(a.updated_at ?? ""));

  const detail: ProjectDetail = {
    id,
    name: canonical.name,
    description: canonical.description,
    health: { bot: botOk, workspace: wsOk, kanban: kbOk, knowledge: knOk },
    counts: {
      sprints_active: active.length,
      tasks_in_progress: tasks.filter(
        (t) => t.project === id && t.status === "in_progress",
      ).length,
    },
    health_details: {
      bot: {
        present: botOk === "ok",
        envPath: botOk === "ok" ? botEnv : null,
        systemdService: botOk === "ok" ? `openclaw-gateway@${id}.service` : null,
      },
      workspace: {
        present: wsOk !== "missing",
        dir: wsOk !== "missing" ? wsDir : null,
        files: wsOk !== "missing" ? workspaceFiles(wsDir) : [],
      },
      kanban: {
        present: kbOk === "ok",
        tasks_total: tasks.filter((t) => t.project === id).length,
      },
      knowledge: {
        present: knOk === "ok",
        specsCount: countFiles(specsDir, ".md"),
        adrsCount: countFiles(adrsDir, ".md"),
        prdsCount: countFiles(prdsDir, ".md"),
      },
    },
    links: {
      telegram_bot_env: botOk === "ok" ? botEnv : null,
      workspace_dir: wsOk !== "missing" ? wsDir : null,
      knowledge_specs_dir: knOk === "ok" ? specsDir : null,
      kanban_filter_url: `/kanban?project=${encodeURIComponent(id)}`,
    },
    sprints: { active, closed },
    tasks_in_flight: tasksInFlight,
  };

  return NextResponse.json(detail);
}
```

- [ ] **Step 4: Run — verify 4 pass**

```bash
cd ~/code/mission-control
NODE_OPTIONS='--experimental-require-module' npx vitest run tests/app/api/projects/detail.route.test.ts 2>&1 | tail -10
```

- [ ] **Step 5: Commit**

```bash
cd ~/code/mission-control
git add src/app/api/projects/\[id\]/route.ts tests/app/api/projects/detail.route.test.ts
git commit -m "$(cat <<'EOF'
feat(api): GET /api/projects/[id] (E2/F-projects-dashboard W1)

ProjectDetail response: health_details expandido (paths completos +
systemd service name), sprints {active, closed top 5}, tasks_in_flight
(in_progress + blocked ordenados por updated_at desc), links condicionais.
404 para id não canônico.

4 tests: 404 não canônico, 200 empty, sprints+tasks populated,
health_details expanded paths.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: `HealthDots.tsx` + `ProjectCard.tsx`

**Files:**
- Create: `src/app/(dashboard)/projects/HealthDots.tsx`
- Create: `src/app/(dashboard)/projects/ProjectCard.tsx`

- [ ] **Step 1: Create `HealthDots.tsx`**

```tsx
"use client";

import type { Dot, ProjectHealth } from "@/lib/projects/types";

interface Props {
  health: ProjectHealth;
  compact?: boolean;
}

const DOT_COLOR: Record<Dot, string> = {
  ok: "bg-green-500",
  partial: "bg-yellow-500",
  missing: "bg-red-400",
};

const LABELS = {
  bot: "Bot",
  workspace: "Workspace",
  kanban: "Kanban",
  knowledge: "Docs",
} as const;

export default function HealthDots({ health, compact = false }: Props) {
  const entries: Array<[keyof ProjectHealth, Dot]> = [
    ["bot", health.bot],
    ["workspace", health.workspace],
    ["kanban", health.kanban],
    ["knowledge", health.knowledge],
  ];
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1">
      {entries.map(([key, dot]) => (
        <span
          key={key}
          className="inline-flex items-center gap-1 text-[11px] text-gray-600"
          title={`${LABELS[key]}: ${dot}`}
        >
          <span className={`inline-block w-2 h-2 rounded-full ${DOT_COLOR[dot]}`} />
          {!compact && <span>{LABELS[key]}</span>}
        </span>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Create `ProjectCard.tsx`**

```tsx
"use client";

import Link from "next/link";
import type { ProjectSummary } from "@/lib/projects/types";
import HealthDots from "./HealthDots";

interface Props {
  project: ProjectSummary;
}

export default function ProjectCard({ project }: Props) {
  return (
    <Link
      href={`/projects/${encodeURIComponent(project.id)}`}
      className="block border border-gray-200 rounded-lg p-4 hover:border-gray-400 hover:bg-gray-50 transition-colors"
    >
      <div className="flex items-start justify-between gap-2 mb-1">
        <h3 className="text-sm font-semibold text-gray-900">{project.name}</h3>
        <span className="text-[10px] font-mono text-gray-400">{project.id}</span>
      </div>
      <p className="text-xs text-gray-600 mb-3 line-clamp-2">{project.description}</p>
      <div className="mb-2">
        <HealthDots health={project.health} />
      </div>
      <div className="text-[11px] text-gray-500 flex gap-3">
        <span>{project.counts.sprints_active} sprint(s) ativos</span>
        <span>•</span>
        <span>{project.counts.tasks_in_progress} em execução</span>
      </div>
    </Link>
  );
}
```

- [ ] **Step 3: Typecheck + commit**

```bash
cd ~/code/mission-control
npx tsc --noEmit 2>&1 | grep -v 'module-components.test.tsx\|deps.route.test.ts' | head -5
git add src/app/\(dashboard\)/projects/HealthDots.tsx src/app/\(dashboard\)/projects/ProjectCard.tsx
git commit -m "$(cat <<'EOF'
feat(projects): HealthDots + ProjectCard (E2/F-projects-dashboard W1)

HealthDots renderiza 4 dots (bot/workspace/kanban/docs) com cores
verde/amarelo/vermelho por Dot status. Modo compact omite labels.

ProjectCard é Link clicável pra /projects/[id] com name + id + description
+ HealthDots + counts.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: `/projects/page.tsx` (list)

**Files:**
- Create: `src/app/(dashboard)/projects/page.tsx`

- [ ] **Step 1: Create page**

```tsx
"use client";

import { useEffect, useState } from "react";
import type { ProjectSummary } from "@/lib/projects/types";
import ProjectCard from "./ProjectCard";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; projects: ProjectSummary[]; generatedAt: string };

export default function ProjectsPage() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch("/api/projects", { cache: "no-store" });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          if (!cancelled)
            setState({
              kind: "error",
              message: `${res.status} ${err.error ?? "unknown"}`,
            });
          return;
        }
        const body = await res.json();
        if (!cancelled)
          setState({
            kind: "ready",
            projects: body.projects,
            generatedAt: body.generated_at,
          });
      } catch (err) {
        if (!cancelled) setState({ kind: "error", message: String(err) });
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.kind === "loading") {
    return <div className="p-6 text-sm text-gray-500">Carregando projetos…</div>;
  }
  if (state.kind === "error") {
    return (
      <div className="p-6">
        <h1 className="text-xl font-bold text-red-700">Erro ao carregar projetos</h1>
        <pre className="mt-2 text-xs bg-red-50 p-2 rounded">{state.message}</pre>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <header className="mb-4">
        <div className="flex items-baseline gap-3 flex-wrap">
          <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
          <span className="text-xs text-gray-400">
            gerado em {new Date(state.generatedAt).toLocaleString("pt-BR")}
          </span>
        </div>
        <p className="text-sm text-gray-600 mt-1">
          6 projetos canônicos (ADR-002). Cada card mostra health (bot, workspace,
          kanban, docs) e contagens ativas.
        </p>
      </header>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {state.projects.map((p) => (
          <ProjectCard key={p.id} project={p} />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck + commit**

```bash
cd ~/code/mission-control
npx tsc --noEmit 2>&1 | grep -v 'module-components.test.tsx\|deps.route.test.ts' | head -5
git add src/app/\(dashboard\)/projects/page.tsx
git commit -m "$(cat <<'EOF'
feat(projects): /projects list page (E2/F-projects-dashboard W1)

Client page. Fetch /api/projects, grid 1-3 cols responsivo de ProjectCard.
LoadState tagged union (loading/error/ready).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Detail sub-components

**Files:**
- Create: `src/app/(dashboard)/projects/[id]/ProjectHeader.tsx`
- Create: `src/app/(dashboard)/projects/[id]/HealthDetails.tsx`
- Create: `src/app/(dashboard)/projects/[id]/ProjectLinks.tsx`

- [ ] **Step 1: Create `ProjectHeader.tsx`**

```tsx
"use client";

import type { ProjectDetail } from "@/lib/projects/types";

interface Props {
  detail: ProjectDetail;
}

function overallLabel(health: ProjectDetail["health"]): { label: string; color: string } {
  const vals = [health.bot, health.workspace, health.kanban, health.knowledge];
  if (vals.every((v) => v === "ok")) return { label: "Second Brain completo", color: "text-green-700" };
  if (vals.every((v) => v === "missing")) return { label: "Não iniciado", color: "text-red-700" };
  return { label: "Setup parcial", color: "text-yellow-700" };
}

export default function ProjectHeader({ detail }: Props) {
  const overall = overallLabel(detail.health);
  return (
    <header className="mb-6">
      <div className="flex items-baseline gap-3 flex-wrap">
        <h1 className="text-2xl font-bold text-gray-900">{detail.name}</h1>
        <span className="text-sm font-mono text-gray-400">{detail.id}</span>
        <span className={`text-xs font-medium ${overall.color}`}>
          {overall.label}
        </span>
      </div>
      <p className="text-sm text-gray-600 mt-1">{detail.description}</p>
    </header>
  );
}
```

- [ ] **Step 2: Create `HealthDetails.tsx`**

```tsx
"use client";

import type { Dot, ProjectDetail } from "@/lib/projects/types";

interface Props {
  detail: ProjectDetail;
}

const DOT_COLOR: Record<Dot, string> = {
  ok: "bg-green-500",
  partial: "bg-yellow-500",
  missing: "bg-red-400",
};

function row(label: string, dot: Dot, body: React.ReactNode) {
  return (
    <li className="flex items-start gap-3 py-2 border-b border-gray-100 last:border-0">
      <span className={`inline-block w-2 h-2 rounded-full mt-2 ${DOT_COLOR[dot]}`} />
      <div className="flex-1 text-xs text-gray-700">
        <div className="font-medium text-gray-900">{label}</div>
        <div className="text-gray-600">{body}</div>
      </div>
    </li>
  );
}

export default function HealthDetails({ detail }: Props) {
  const h = detail.health_details;
  return (
    <section className="border border-gray-200 rounded p-3 mb-4">
      <h2 className="text-sm font-semibold text-gray-900 mb-1">Health</h2>
      <ul>
        {row(
          "Bot Telegram",
          detail.health.bot,
          h.bot.present ? (
            <>
              env: <span className="font-mono text-[11px]">{h.bot.envPath}</span>
              <br />
              systemd: <span className="font-mono text-[11px]">{h.bot.systemdService}</span>
            </>
          ) : (
            "bot env não configurado"
          ),
        )}
        {row(
          "Workspace",
          detail.health.workspace,
          h.workspace.present ? (
            <>
              dir: <span className="font-mono text-[11px]">{h.workspace.dir}</span>
              <br />
              files: {h.workspace.files.join(", ") || "(nenhum)"}
            </>
          ) : (
            "workspace não scaffolded"
          ),
        )}
        {row(
          "Kanban project",
          detail.health.kanban,
          h.kanban.present
            ? `${h.kanban.tasks_total} task(s) no projeto`
            : "projeto não listado em kanban-tasks/projects.yml",
        )}
        {row(
          "Knowledge docs",
          detail.health.knowledge,
          h.knowledge.present ? (
            <>
              specs: {h.knowledge.specsCount} · adrs: {h.knowledge.adrsCount} · prds: {h.knowledge.prdsCount}
            </>
          ) : (
            "nenhum artefato em bevox-knowledge/*/<project>/"
          ),
        )}
      </ul>
    </section>
  );
}
```

- [ ] **Step 3: Create `ProjectLinks.tsx`**

```tsx
"use client";

import type { ProjectLinks as Links } from "@/lib/projects/types";

interface Props {
  links: Links;
}

export default function ProjectLinks({ links }: Props) {
  const buttons: Array<{ href: string; label: string; external?: boolean }> = [];
  if (links.telegram_bot_env) {
    buttons.push({
      href: `file://${links.telegram_bot_env}`,
      label: "Bot env",
      external: true,
    });
  }
  if (links.workspace_dir) {
    buttons.push({
      href: `file://${links.workspace_dir}`,
      label: "Workspace",
      external: true,
    });
  }
  if (links.knowledge_specs_dir) {
    buttons.push({
      href: `file://${links.knowledge_specs_dir}`,
      label: "Knowledge",
      external: true,
    });
  }
  buttons.push({ href: links.kanban_filter_url, label: "Kanban ↗" });

  if (buttons.length === 0) return null;
  return (
    <section className="mb-4">
      <div className="flex flex-wrap gap-2">
        {buttons.map((b) => (
          <a
            key={b.label}
            href={b.href}
            target={b.external ? "_blank" : undefined}
            rel={b.external ? "noopener noreferrer" : undefined}
            className="inline-flex items-center px-3 py-1.5 text-xs border border-gray-300 rounded hover:bg-gray-50"
          >
            {b.label}
          </a>
        ))}
      </div>
    </section>
  );
}
```

Nota: `file://` links só abrem externamente quando o browser permite. Em produção (MC deployed), esses paths podem não ser acessíveis diretamente; ok como hint textual. Kanban link usa rota relativa (funciona sempre).

- [ ] **Step 4: Typecheck + commit**

```bash
cd ~/code/mission-control
npx tsc --noEmit 2>&1 | grep -v 'module-components.test.tsx\|deps.route.test.ts' | head -5
git add src/app/\(dashboard\)/projects/\[id\]/ProjectHeader.tsx \
        src/app/\(dashboard\)/projects/\[id\]/HealthDetails.tsx \
        src/app/\(dashboard\)/projects/\[id\]/ProjectLinks.tsx
git commit -m "$(cat <<'EOF'
feat(projects): detail sub-components (E2/F-projects-dashboard W1)

ProjectHeader: nome + id + label overall (completo/parcial/não iniciado).
HealthDetails: 4 rows expandidos com paths + systemd name + file list.
ProjectLinks: botões condicionais (bot env, workspace, knowledge,
kanban filter). file:// links externos; kanban link interno.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: `SprintList.tsx` + `TasksInFlight.tsx`

**Files:**
- Create: `src/app/(dashboard)/projects/[id]/SprintList.tsx`
- Create: `src/app/(dashboard)/projects/[id]/TasksInFlight.tsx`

- [ ] **Step 1: Create `SprintList.tsx`**

```tsx
"use client";

import Link from "next/link";
import type { Sprint } from "@/lib/projects/types";

interface Props {
  projectId: string;
  active: Sprint[];
  closed: Sprint[];
}

function sprintRow(s: Sprint) {
  return (
    <Link
      key={s.id}
      href={`/kanban/history/${encodeURIComponent(s.id)}`}
      className="flex items-center justify-between py-1.5 px-2 text-xs hover:bg-gray-50 rounded"
    >
      <span className="font-mono text-gray-700">{s.id}</span>
      <span className="flex-1 ml-2 text-gray-600">{s.name}</span>
      <span className="text-gray-400 text-[11px]">
        {s.state} · {s.closed_at ? `closed ${s.closed_at.slice(0, 10)}` : `since ${s.created_at.slice(0, 10)}`}
      </span>
    </Link>
  );
}

export default function SprintList({ projectId, active, closed }: Props) {
  return (
    <section className="mb-4">
      <h2 className="text-sm font-semibold text-gray-900 mb-1">Sprints ativos</h2>
      {active.length === 0 ? (
        <p className="text-xs text-gray-400 italic px-2 py-1">
          Nenhum sprint current ou next para este projeto.
        </p>
      ) : (
        <div className="border border-gray-200 rounded divide-y divide-gray-100">
          {active.map(sprintRow)}
        </div>
      )}
      <h2 className="text-sm font-semibold text-gray-900 mb-1 mt-4">
        Histórico (últimos 5)
      </h2>
      {closed.length === 0 ? (
        <p className="text-xs text-gray-400 italic px-2 py-1">
          Nenhum sprint fechado ainda.
        </p>
      ) : (
        <div className="border border-gray-200 rounded divide-y divide-gray-100">
          {closed.map(sprintRow)}
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Create `TasksInFlight.tsx`**

```tsx
"use client";

import type { Task } from "@/lib/projects/types";

interface Props {
  tasks: Task[];
}

export default function TasksInFlight({ tasks }: Props) {
  return (
    <section className="mb-4">
      <h2 className="text-sm font-semibold text-gray-900 mb-1">Tasks in-flight</h2>
      {tasks.length === 0 ? (
        <p className="text-xs text-gray-400 italic px-2 py-1">
          Nenhuma task em andamento ou bloqueada.
        </p>
      ) : (
        <div className="border border-gray-200 rounded divide-y divide-gray-100">
          {tasks.map((t) => (
            <div key={t.id} className="py-1.5 px-2 flex items-center gap-2 text-xs">
              <span className="font-mono text-gray-700">{t.id}</span>
              <span
                className={`text-[10px] rounded px-1.5 py-0.5 font-medium ${
                  t.status === "blocked"
                    ? "bg-red-100 text-red-800"
                    : "bg-yellow-100 text-yellow-800"
                }`}
              >
                {t.status}
              </span>
              <span className="flex-1 text-gray-700 truncate">{t.title}</span>
              <span className="text-gray-400 text-[10px]">
                {(t.updated_at || "").slice(0, 10)}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 3: Typecheck + commit**

```bash
cd ~/code/mission-control
npx tsc --noEmit 2>&1 | grep -v 'module-components.test.tsx\|deps.route.test.ts' | head -5
git add src/app/\(dashboard\)/projects/\[id\]/SprintList.tsx \
        src/app/\(dashboard\)/projects/\[id\]/TasksInFlight.tsx
git commit -m "$(cat <<'EOF'
feat(projects): SprintList + TasksInFlight (E2/F-projects-dashboard W1)

SprintList: 2 seções (ativos + histórico top 5), cada row link pra
/kanban/history/<sprint_id>. TasksInFlight: lista tasks in_progress +
blocked com status badge colorido.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: `/projects/[id]/page.tsx`

**Files:**
- Create: `src/app/(dashboard)/projects/[id]/page.tsx`

- [ ] **Step 1: Create page**

```tsx
"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

import type { ProjectDetail } from "@/lib/projects/types";
import ProjectHeader from "./ProjectHeader";
import HealthDetails from "./HealthDetails";
import ProjectLinks from "./ProjectLinks";
import SprintList from "./SprintList";
import TasksInFlight from "./TasksInFlight";

type State =
  | { kind: "loading" }
  | { kind: "not_found" }
  | { kind: "error"; message: string }
  | { kind: "ready"; detail: ProjectDetail };

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch(`/api/projects/${encodeURIComponent(id)}`, {
          cache: "no-store",
        });
        if (res.status === 404) {
          if (!cancelled) setState({ kind: "not_found" });
          return;
        }
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          if (!cancelled)
            setState({
              kind: "error",
              message: `${res.status} ${err.error ?? "unknown"}`,
            });
          return;
        }
        const body: ProjectDetail = await res.json();
        if (!cancelled) setState({ kind: "ready", detail: body });
      } catch (err) {
        if (!cancelled) setState({ kind: "error", message: String(err) });
      }
    }
    if (id) load();
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (state.kind === "loading") {
    return <div className="p-6 text-sm text-gray-500">Carregando projeto…</div>;
  }
  if (state.kind === "not_found") {
    return (
      <div className="p-6">
        <h1 className="text-xl font-bold text-gray-900">Projeto não encontrado</h1>
        <p className="text-sm text-gray-600 mt-2">
          <span className="font-mono">{id}</span> não é um projeto canônico (ADR-002).
        </p>
        <Link href="/projects" className="text-sm text-blue-600 hover:underline">
          ← voltar para Projects
        </Link>
      </div>
    );
  }
  if (state.kind === "error") {
    return (
      <div className="p-6">
        <h1 className="text-xl font-bold text-red-700">Erro ao carregar projeto</h1>
        <pre className="mt-2 text-xs bg-red-50 p-2 rounded">{state.message}</pre>
      </div>
    );
  }

  const { detail } = state;
  return (
    <div className="p-6 max-w-4xl mx-auto">
      <Link href="/projects" className="text-xs text-blue-600 hover:underline">
        ← Projects
      </Link>
      <ProjectHeader detail={detail} />
      <HealthDetails detail={detail} />
      <ProjectLinks links={detail.links} />
      <SprintList projectId={detail.id} active={detail.sprints.active} closed={detail.sprints.closed} />
      <TasksInFlight tasks={detail.tasks_in_flight} />
    </div>
  );
}
```

- [ ] **Step 2: Typecheck + commit**

```bash
cd ~/code/mission-control
npx tsc --noEmit 2>&1 | grep -v 'module-components.test.tsx\|deps.route.test.ts' | head -5
git add src/app/\(dashboard\)/projects/\[id\]/page.tsx
git commit -m "$(cat <<'EOF'
feat(projects): /projects/[id] detail page (E2/F-projects-dashboard W1)

Client component. Fetch /api/projects/[id] (not_found para 404).
Compõe ProjectHeader + HealthDetails + ProjectLinks + SprintList +
TasksInFlight. Back-link pra /projects.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Adicionar `/projects` ao Sidebar

**Files:**
- Modify: `src/components/Sidebar.tsx`

- [ ] **Step 1: Read + edit**

Inspecionar o array de NAV_ITEMS (ou equivalente) na Sidebar.tsx. Adicionar entry `/projects` **antes** de `/roadmap` (roadmap está na posição 2 após Dashboard).

Usar ícone `LayoutGrid` de `lucide-react` (se não importado, adicionar import).

Exemplo de edit (ajustar à sintaxe real encontrada):

```tsx
// import line: garantir LayoutGrid
import {
  LayoutDashboard,
  LayoutGrid,  // <-- adicionar se faltar
  Map,
  // ...
} from "lucide-react";

// NAV_ITEMS array: inserir ANTES de Roadmap
const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/projects", label: "Projects", icon: LayoutGrid },  // <-- NOVA entry
  { href: "/roadmap", label: "Roadmap", icon: Map },
  // ... resto inalterado
];
```

- [ ] **Step 2: Typecheck + commit**

```bash
cd ~/code/mission-control
npx tsc --noEmit 2>&1 | grep -v 'module-components.test.tsx\|deps.route.test.ts' | head -5
git add src/components/Sidebar.tsx
git commit -m "$(cat <<'EOF'
feat(sidebar): add /projects entry (E2/F-projects-dashboard W1)

Entry antes de /roadmap. Ícone LayoutGrid. Projects é âncora
operacional (agentes, bots, sprints por projeto); roadmap é view
derivada.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Smoke test

**Files:** nenhum.

- [ ] **Step 1: Typecheck**

```bash
cd ~/code/mission-control
npx tsc --noEmit 2>&1 | grep -v 'module-components.test.tsx\|deps.route.test.ts' | head -10
```

Expected: empty (ou somente pre-existing).

- [ ] **Step 2: Rodar testes projects**

```bash
cd ~/code/mission-control
NODE_OPTIONS='--experimental-require-module' npx vitest run \
  tests/lib/projects/ tests/app/api/projects/ 2>&1 | tail -15
```

Expected: 20 tests pass (12 health + 4 list + 4 detail).

- [ ] **Step 3: Opcional — dev server + curl**

```bash
cd ~/code/mission-control
BEVOX_KNOWLEDGE_DIR=~/bevox-knowledge npm run dev &
DEV_PID=$!
sleep 8
curl -sS http://localhost:3000/api/projects | python3 -m json.tool | head -30
echo "---"
curl -sS http://localhost:3000/api/projects/bevox-mobile | python3 -m json.tool | head -30
kill $DEV_PID 2>/dev/null
```

Expected: 200 retornos com estrutura do ProjectSummary / ProjectDetail. Se dev server não inicia por razões externas, pular — typecheck + tests cobrem.

- [ ] **Step 4: N/A (só verificação)**

Se qualquer step falhar: STOP, reportar BLOCKED.

---

## Task 14: Push + PR (pausa pro merge)

**Files:** nenhum.

- [ ] **Step 1: Push**

```bash
cd ~/code/mission-control
git push -u origin feat/e2-projects-dashboard-w1
```

- [ ] **Step 2: Create PR**

```bash
cd ~/code/mission-control
gh pr create --title "feat(projects): E2/F-projects-dashboard W1 (read-only list + drill-down)" --base main --head feat/e2-projects-dashboard-w1 --body "$(cat <<'EOF'
## Summary

Primeira wave da feature E2/F-projects-dashboard. Read-only \`/projects\` + \`/projects/[id]\` no Mission Control.

### Highlights

- **6 projetos canônicos** hardcoded (ADR-002) em \`src/lib/projects/canonical.ts\` — não depende de \`kanban-tasks/projects.yml\`.
- **4 health checks** puros filesystem-based: bot (\`gateway/bots/<id>.env\`), workspace (\`workspace-<id>/IDENTITY.md\`), kanban (\`projects.yml\`), knowledge (\`35_specs/<id>/*.md\` non-gitkeep).
- Vocabulário \`ok | partial | missing\` — \`partial\` flaga bootstrap interrompido (ex: workspace dir sem IDENTITY.md).
- **2 API routes novas:** \`/api/projects\` (lista) + \`/api/projects/[id]\` (detalhe).
- **10 componentes React novos:** ProjectCard, HealthDots, ProjectHeader, HealthDetails, ProjectLinks, SprintList, TasksInFlight + 2 pages + types.
- **Sidebar:** entry \`/projects\` antes de \`/roadmap\`.

### Não-escopo W1 (deferred)

- Actions (criar sprint/task/archive) → **W2**
- Edit bot config via UI → **W3**
- Criar novo projeto via UI (wizard/bootstrap) → **W4**

**Spec:** \`bevox-knowledge/35_specs/company-os/2026-04-24-e2-projects-dashboard-w1.md\`

**Rollback:** revert do merge; \`/projects\` some, sidebar entry some, APIs 404. Zero impacto em outras surfaces.

## Test plan

- [x] \`health.ts\` 12 unit tests (3 estados × 4 checks)
- [x] \`/api/projects\` 4 route tests (6 ids, all-ok, counts derivation, graceful missing)
- [x] \`/api/projects/[id]\` 4 route tests (404 não-canônico, empty health_details, sprints+tasks, expanded paths)
- [x] **20/20 tests passing**
- [x] Full typecheck limpo nos arquivos novos
- [ ] Smoke manual pós-merge: \`/projects\` renderiza 6 cards; clicar abre detail; link Kanban filtra.

## Follow-up

- Tracker sync: add \`E2 / F-projects-dashboard / W1\` entry como \`delivered\` em \`40_roadmap/_shared/delivery-tracker.yml\` (PR separado no bevox-knowledge).
- W2/W3/W4 specs/planos quando prioridade subir.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Parar + aguardar autorização do Bernard**

Reportar URL do PR. Aguardar "autorizo" antes de mergear.

- [ ] **Step 4: Após autorização — merge + sync**

```bash
PR=$(gh pr list --repo bernardTavares/mission-control --head feat/e2-projects-dashboard-w1 --json number --jq '.[0].number')
gh pr merge $PR --repo bernardTavares/mission-control --merge --delete-branch
cd ~/code/mission-control
git checkout main
git pull --ff-only
git log --oneline -3
```

---

## Task 15: Tracker sync (bevox-knowledge)

**Files:**
- Modify: `~/bevox-knowledge/40_roadmap/_shared/delivery-tracker.yml`

- [ ] **Step 1: Criar branch**

```bash
cd ~/bevox-knowledge
git checkout main
git pull --ff-only
git checkout -b tracker/e2-projects-dashboard-w1
```

- [ ] **Step 2: Localizar E2 + waves**

```bash
grep -nA 2 "^  - id: E2" 40_roadmap/_shared/delivery-tracker.yml | head -20
```

- [ ] **Step 3: Edit — adicionar wave F-projects-dashboard/W1**

Abrir o arquivo no editor. Dentro do bloco `- id: E2` (epic Mission Control Shell), no array `waves:`, adicionar nova entry após as existentes:

```yaml
      - id: F-projects-dashboard-w1
        status: delivered
        delivered_at: "<YYYY-MM-DD-execução>"
        features:
          - "/projects list page (6 canonical projects)"
          - "/projects/[id] drill-down (health details, sprints, tasks in-flight)"
          - "4 health checks filesystem-based (bot/workspace/kanban/knowledge) com vocabulário ok|partial|missing"
          - "2 API routes novas: /api/projects, /api/projects/[id]"
          - "Sidebar entry /projects antes de /roadmap"
        spec: 35_specs/company-os/2026-04-24-e2-projects-dashboard-w1.md
```

Substituir `<YYYY-MM-DD-execução>` pela data real.

- [ ] **Step 4: Validate YAML + commit**

```bash
cd ~/bevox-knowledge
python3 -c "import yaml; yaml.safe_load(open('40_roadmap/_shared/delivery-tracker.yml')); print('YAML OK')"
git add 40_roadmap/_shared/delivery-tracker.yml
git commit -m "$(cat <<'EOF'
tracker(E2/F-projects-dashboard/W1): delivered

/projects read-only + drill-down entregue em mission-control.
4 health checks + 2 API routes + 10 componentes + sidebar entry.
Plano: docs/superpowers/plans/2026-04-24-e2-projects-dashboard-w1.md
Spec: 35_specs/company-os/2026-04-24-e2-projects-dashboard-w1.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 5: Push + PR + aguardar autorização**

```bash
cd ~/bevox-knowledge
git push -u origin tracker/e2-projects-dashboard-w1
gh pr create --title "tracker(E2/F-projects-dashboard/W1): delivered" --base main --head tracker/e2-projects-dashboard-w1 --body "Sync do tracker com a wave entregue em bernardTavares/mission-control."
```

Reportar PR URL; aguardar autorização pra merge.

- [ ] **Step 6: Merge após autorização**

```bash
PR=$(gh pr list --repo bernardTavares/bevox-knowledge --head tracker/e2-projects-dashboard-w1 --json number --jq '.[0].number')
gh pr merge $PR --repo bernardTavares/bevox-knowledge --merge --delete-branch
cd ~/bevox-knowledge
git checkout main
git pull --ff-only
```

---

## Self-Review

**Spec coverage check (§3-§8 da spec):**

- ✅ 6 projetos canônicos hardcoded — Task 3
- ✅ 4 health checks ok|partial|missing — Task 4
- ✅ Counts (sprints_active, tasks_in_progress) — Task 5
- ✅ `/api/projects` + `/api/projects/[id]` — Tasks 5, 6
- ✅ Hardcoded fonte (não depende projects.yml) — Task 3
- ✅ ProjectCard + HealthDots + list page — Tasks 7, 8
- ✅ ProjectHeader + HealthDetails + ProjectLinks + SprintList + TasksInFlight + detail page — Tasks 9, 10, 11
- ✅ Sidebar entry — Task 12
- ✅ Error handling: 404 não-canônico, 503 graceful (na prática: empty states quando env missing) — implementados
- ✅ Testing: 12 unit health + 8 integration routes = 20 tests — Tasks 4, 5, 6
- ✅ Tracker sync pós-merge — Task 15

**Placeholder check:** zero "TBD/TODO". Task 15 usa placeholder explícito `<YYYY-MM-DD-execução>` instruído a substituir.

**Consistency check:**
- Types em `types.ts` (Task 2) referenciados em todos os componentes e routes
- `CANONICAL_PROJECTS` (Task 3) usado em routes (Tasks 5, 6) e via `getCanonicalProject` / `isCanonicalProject`
- 4 health checks (Task 4) chamados em ambas routes (Tasks 5, 6)
- `ProjectSummary` assinatura em Task 2 é a mesma consumida em Task 5 e Task 7
- `ProjectDetail` definido em Task 2 consumido em Task 6 + Tasks 9-11
- Vocabulary `ok|partial|missing` consistente em todos os componentes e tests

---

## Execution Handoff

Plan completo salvo em `~/.openclaw/docs/superpowers/plans/2026-04-24-e2-projects-dashboard-w1.md`. 15 tasks.

Duas opções:

1. **Subagent-Driven (recomendada)** — fresh subagent por task, iteração rápida.
2. **Inline Execution** — nesta sessão.

Qual?
