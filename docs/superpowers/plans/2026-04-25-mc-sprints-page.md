# Mission Control Sprints Page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nova rota `/sprints` no Mission Control: 3 colunas cross-project (Active | Next | Closed) com cards minimal por sprint; click em card abre modal centrado com kanban full editável daquela sprint específica.

**Architecture:** Client-side React component que consome `GET /api/kanban/state` (já entregue). Page client component em `(dashboard)/sprints/page.tsx`. 3 components novos em `components/sprints/`: SprintCard, SprintColumn, SprintKanbanModal. Modal reusa `<Board>` existing (que já aceita `tasks` filtered + `readOnly` prop). URL state deep-linkable (`?project=X&sprint=Y`). Sem mudanças backend.

**Tech Stack:** Next.js 15 client components + React hooks + lucide-react icons + Vitest (contract-based tests, sem renderToStaticMarkup pra components com hooks).

**Spec:** `bevox-knowledge/35_specs/company-os/2026-04-25-mc-sprints-page.md` (commit `8401647` em `draft/spec-mc-sprints-page`).

---

## File Structure

### Create (mission-control)

- `src/lib/projects/colors.ts` — `PROJECT_COLORS` map + `getProjectColors(project)` helper
- `src/components/sprints/SprintCard.tsx` — minimal card (project chip + sprint name + task count)
- `src/components/sprints/SprintColumn.tsx` — wrapper de uma coluna (Active/Next/Closed) com sort + show-all logic
- `src/components/sprints/SprintKanbanModal.tsx` — modal centrado embedando `<Board>`
- `src/app/(dashboard)/sprints/page.tsx` — page client component
- `tests/lib/projects/colors.test.ts` — 2 tests
- `tests/components/sprints/SprintCard.test.ts` — 3 contract tests
- `tests/components/sprints/SprintColumn.test.ts` — 3 contract tests
- `tests/components/sprints/SprintKanbanModal.test.ts` — 3 contract tests
- `tests/app/(dashboard)/sprints/page.test.ts` — 3 contract tests

### Modify (mission-control)

- `src/components/Sidebar.tsx` — adiciona entry `Sprints` entre Projects e Roadmap

### No mudança em openclaw runtime (este wave é frontend-puro)

---

## Task 1: Setup branches + commit plan + push spec PR (gate)

**Files:**
- Create: `~/.openclaw/docs/superpowers/plans/2026-04-25-mc-sprints-page.md` (este arquivo, commitado em `feat/mc-sprints-page-plan` em `~/.openclaw`)

- [ ] **Step 1: Branch openclaw plan**

```bash
cd ~/.openclaw && git checkout main && git pull --ff-only
git checkout -b feat/mc-sprints-page-plan
```

(Se branch já existe, faça `git checkout feat/mc-sprints-page-plan`.)

- [ ] **Step 2: Commit plan**

```bash
cd ~/.openclaw && git add docs/superpowers/plans/2026-04-25-mc-sprints-page.md && git commit -m "$(cat <<'EOF'
plan(mc-sprints-page): implementation plan for Mission Control Sprints page

Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-sprints-page.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 3: Push spec PR no bevox-knowledge**

```bash
cd ~/bevox-knowledge && git checkout draft/spec-mc-sprints-page
git push -u origin draft/spec-mc-sprints-page
gh pr create --title "spec(company-os): MC Sprints page (E2/mc-sprints-page)" --body "$(cat <<'EOF'
## Summary
Nova página /sprints no Mission Control: cross-project lista 3 colunas (Active | Next | Closed) com cards minimal + click → modal full kanban editável da sprint clicada.

6 escolhas brainstormadas 2026-04-25:
- Cross-project default + project filter opcional
- Three-column layout (Active | Next | Closed)
- Modal centrado on click (não drawer, não navigation)
- Minimal cards (project chip + sprint id + task count)
- Closed col top 10 + Show all
- Modal full editable + closed sprint banner

Backend 100% pronto (currentSprintByProject + sprints[] já em /api/kanban/state). Wave puramente frontend (~600 LOC + 14 vitest tests).

## Test plan
- [ ] Bernard revisa spec
- [ ] Approva pra implementação seguir
- [ ] mission-control PR abre só após este merge

## Plan
\`docs/superpowers/plans/2026-04-25-mc-sprints-page.md\` no openclaw branch \`feat/mc-sprints-page-plan\`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: PAUSA — aguardar Bernard mergear o spec PR**

Parar aqui. Bernard merge `bernardTavares/bevox-knowledge` PR. Retomar Task 2 só após confirmação de merge em main.

---

## Task 2: PROJECT_COLORS helper

**Files:**
- Create: `mission-control/src/lib/projects/colors.ts`
- Create: `mission-control/tests/lib/projects/colors.test.ts`

- [ ] **Step 1: Branch mission-control feat**

```bash
cd ~/code/mission-control && git checkout main && git pull --ff-only
git checkout -b feat/mc-sprints-page
```

- [ ] **Step 2: Escrever tests**

Write `~/code/mission-control/tests/lib/projects/colors.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { PROJECT_COLORS, getProjectColors } from "@/lib/projects/colors";

describe("PROJECT_COLORS", () => {
  it("includes all 10 canonical projects", () => {
    const expected = [
      "bevox-mobile", "bevox-backend", "bevox-web", "bevox-console",
      "bevox-harness", "openclaw", "company-os", "mission-control",
      "bevox-knowledge", "vox",
    ];
    for (const p of expected) {
      expect(PROJECT_COLORS[p]).toBeDefined();
      expect(PROJECT_COLORS[p].bg).toMatch(/^#[0-9a-f]{6}$/i);
      expect(PROJECT_COLORS[p].fg).toMatch(/^#[0-9a-f]{6}$/i);
    }
  });

  it("getProjectColors returns fallback for unknown project", () => {
    const result = getProjectColors("unknown-project");
    expect(result.bg).toBe("#2a2f3e");
    expect(result.fg).toBe("#888");
  });
});
```

- [ ] **Step 3: Rodar tests (deve falhar — module não existe)**

```bash
cd ~/code/mission-control && npm test -- --run tests/lib/projects/colors.test.ts 2>&1 | tail -8
```

Expected: ERR (`Cannot find module '@/lib/projects/colors'`).

- [ ] **Step 4: Criar `src/lib/projects/colors.ts`**

```typescript
/**
 * Color palette per canonical project (10 entries from projects.yml).
 * Used by SprintCard's project chip + future visual surfaces.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-sprints-page.md §3.4
 */

export const PROJECT_COLORS: Record<string, { bg: string; fg: string }> = {
  "bevox-mobile":    { bg: "#1e3a5f", fg: "#6ec1e4" },
  "bevox-backend":   { bg: "#2a4f30", fg: "#7ec896" },
  "bevox-web":       { bg: "#5f1e3a", fg: "#e46e9b" },
  "bevox-console":   { bg: "#4a1e5f", fg: "#b06ee4" },
  "bevox-harness":   { bg: "#5f5f1e", fg: "#e4e46e" },
  "openclaw":        { bg: "#5f3a1e", fg: "#e4a06e" },
  "company-os":      { bg: "#1e5f5a", fg: "#6ee4dc" },
  "mission-control": { bg: "#3a1e5f", fg: "#a06ee4" },
  "bevox-knowledge": { bg: "#1e5f3a", fg: "#6ee4a0" },
  "vox":             { bg: "#5f1e1e", fg: "#e46e6e" },
};

export function getProjectColors(project: string): { bg: string; fg: string } {
  return PROJECT_COLORS[project] ?? { bg: "#2a2f3e", fg: "#888" };
}
```

- [ ] **Step 5: Rodar tests**

```bash
cd ~/code/mission-control && npm test -- --run tests/lib/projects/colors.test.ts 2>&1 | tail -5
```

Expected: 2/2 pass.

- [ ] **Step 6: Commit**

```bash
cd ~/code/mission-control && git add src/lib/projects/colors.ts tests/lib/projects/colors.test.ts && git commit -m "$(cat <<'EOF'
feat(lib/projects): PROJECT_COLORS map for 10 canonical projects

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: SprintCard component

**Files:**
- Create: `mission-control/src/components/sprints/SprintCard.tsx`
- Create: `mission-control/tests/components/sprints/SprintCard.test.ts`

- [ ] **Step 1: Escrever contract tests**

Write `~/code/mission-control/tests/components/sprints/SprintCard.test.ts`:

```typescript
/**
 * Contract tests for SprintCard.
 *
 * Pattern: type-level + props contract verification (sem renderToStaticMarkup
 * porque SprintCard usa hooks indiretamente via children).
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-sprints-page.md §3.1
 */
import { describe, it, expect } from "vitest";
import type { SprintCardProps } from "@/components/sprints/SprintCard";

describe("SprintCardProps contract", () => {
  it("requires sprint, taskCount, isClosed, onClick", () => {
    // Type-level check — assignment fail if interface drifts
    const props: SprintCardProps = {
      sprint: {
        id: "sprint-22",
        name: "Sprint 22",
        state: "current",
        project: "test-project",
        created_at: "2026-04-25T00:00:00Z",
        closed_at: null,
        created_by: "bernard",
      },
      taskCount: 5,
      isClosed: false,
      onClick: () => {},
    };
    expect(props.sprint.id).toBe("sprint-22");
    expect(props.taskCount).toBe(5);
    expect(props.isClosed).toBe(false);
  });

  it("formatTaskCount handles 0 / 1 / N tasks", () => {
    // Importing the helper directly to verify formatting logic
    // (helper is exported pra reuso em SprintColumn empty-states)
    const { formatTaskCount } = require("@/components/sprints/SprintCard");
    expect(formatTaskCount(0)).toBe("empty");
    expect(formatTaskCount(1)).toBe("1 task");
    expect(formatTaskCount(5)).toBe("5 tasks");
  });

  it("extractSprintNumber handles sprint-N format", () => {
    const { extractSprintNumber } = require("@/components/sprints/SprintCard");
    expect(extractSprintNumber("sprint-22")).toBe(22);
    expect(extractSprintNumber("sprint-3")).toBe(3);
    expect(extractSprintNumber("custom-id")).toBeNull();
  });
});
```

- [ ] **Step 2: Rodar tests (devem falhar)**

```bash
cd ~/code/mission-control && npm test -- --run tests/components/sprints/SprintCard.test.ts 2>&1 | tail -8
```

Expected: ERR (component não existe).

- [ ] **Step 3: Criar `src/components/sprints/SprintCard.tsx`**

```typescript
"use client";

import type { Sprint } from "@/lib/kanban/stateReader";
import { getProjectColors } from "@/lib/projects/colors";

export interface SprintCardProps {
  sprint: Sprint;
  taskCount: number;
  isClosed: boolean;
  onClick: () => void;
}

/** Format task count: 0 → "empty", 1 → "1 task", N → "N tasks". */
export function formatTaskCount(count: number): string {
  if (count === 0) return "empty";
  if (count === 1) return "1 task";
  return `${count} tasks`;
}

/** Extract numeric N from "sprint-N" id pra display "Sprint N". Returns null se formato custom. */
export function extractSprintNumber(id: string): number | null {
  const match = /^sprint-(\d+)$/.exec(id);
  return match ? parseInt(match[1], 10) : null;
}

/**
 * Minimal card pra Sprints page: project chip + sprint name + task count.
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-sprints-page.md §3.1
 */
export function SprintCard({ sprint, taskCount, isClosed, onClick }: SprintCardProps) {
  const project = sprint.project ?? "unknown";
  const colors = getProjectColors(project);
  const sprintNum = extractSprintNumber(sprint.id);
  const sprintName = sprintNum !== null ? `Sprint ${sprintNum}` : sprint.name;
  const opacity = isClosed ? 0.55 : 1;

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      className="sprint-card"
      style={{
        background: "#1a2230",
        borderLeft: `3px solid ${colors.fg}`,
        borderRadius: 4,
        padding: "0.55rem 0.7rem",
        cursor: "pointer",
        opacity,
        transition: "background-color 0.15s",
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = "#222b3c")}
      onMouseLeave={(e) => (e.currentTarget.style.background = "#1a2230")}
    >
      <div
        style={{
          display: "inline-block",
          background: colors.bg,
          color: colors.fg,
          padding: "0.1rem 0.45rem",
          borderRadius: 10,
          fontSize: "0.7rem",
          fontWeight: 600,
        }}
      >
        {project}
      </div>
      <div
        style={{
          color: "#e0e0e0",
          fontWeight: 600,
          fontSize: "0.9rem",
          margin: "0.25rem 0 0.1rem",
        }}
      >
        {sprintName}
      </div>
      <div style={{ color: "#888", fontSize: "0.72rem" }}>{formatTaskCount(taskCount)}</div>
    </div>
  );
}
```

- [ ] **Step 4: Rodar tests**

```bash
cd ~/code/mission-control && npm test -- --run tests/components/sprints/SprintCard.test.ts 2>&1 | tail -5
```

Expected: 3/3 pass.

- [ ] **Step 5: Commit**

```bash
cd ~/code/mission-control && git add src/components/sprints/SprintCard.tsx tests/components/sprints/SprintCard.test.ts && git commit -m "$(cat <<'EOF'
feat(components/sprints): SprintCard with minimal layout + project chip

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: SprintColumn component

**Files:**
- Create: `mission-control/src/components/sprints/SprintColumn.tsx`
- Create: `mission-control/tests/components/sprints/SprintColumn.test.ts`

- [ ] **Step 1: Escrever contract tests**

Write `~/code/mission-control/tests/components/sprints/SprintColumn.test.ts`:

```typescript
/**
 * Contract tests for SprintColumn.
 * Tests sort/filter helpers (pure functions) + props contract.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-sprints-page.md §3.1, §2.4
 */
import { describe, it, expect } from "vitest";
import type { SprintColumnProps } from "@/components/sprints/SprintColumn";

describe("SprintColumnProps contract", () => {
  it("requires state, sprints, tasksBySprint, showAllClosed, onToggleShowAll, onSelectSprint", () => {
    const props: SprintColumnProps = {
      state: "current",
      sprints: [],
      tasksBySprint: {},
      showAllClosed: false,
      onToggleShowAll: () => {},
      onSelectSprint: () => {},
    };
    expect(props.state).toBe("current");
  });
});

describe("sortSprintsForColumn helper", () => {
  it("sorts current/next by project name asc", () => {
    const { sortSprintsForColumn } = require("@/components/sprints/SprintColumn");
    const sprints = [
      { id: "sprint-3", state: "current", project: "openclaw", name: "S3", created_at: "", closed_at: null, created_by: "" },
      { id: "sprint-1", state: "current", project: "bevox-mobile", name: "S1", created_at: "", closed_at: null, created_by: "" },
      { id: "sprint-2", state: "current", project: "bevox-backend", name: "S2", created_at: "", closed_at: null, created_by: "" },
    ];
    const result = sortSprintsForColumn(sprints, "current");
    expect(result.map((s: any) => s.project)).toEqual([
      "bevox-backend", "bevox-mobile", "openclaw",
    ]);
  });

  it("sorts closed by closed_at desc", () => {
    const { sortSprintsForColumn } = require("@/components/sprints/SprintColumn");
    const sprints = [
      { id: "sprint-1", state: "closed", project: "x", name: "S1", created_at: "", closed_at: "2026-04-10T00:00:00Z", created_by: "" },
      { id: "sprint-2", state: "closed", project: "x", name: "S2", created_at: "", closed_at: "2026-04-25T00:00:00Z", created_by: "" },
      { id: "sprint-3", state: "closed", project: "x", name: "S3", created_at: "", closed_at: "2026-04-15T00:00:00Z", created_by: "" },
    ];
    const result = sortSprintsForColumn(sprints, "closed");
    expect(result.map((s: any) => s.id)).toEqual(["sprint-2", "sprint-3", "sprint-1"]);
  });
});
```

- [ ] **Step 2: Rodar tests (devem falhar)**

```bash
cd ~/code/mission-control && npm test -- --run tests/components/sprints/SprintColumn.test.ts 2>&1 | tail -5
```

Expected: ERR.

- [ ] **Step 3: Criar `src/components/sprints/SprintColumn.tsx`**

```typescript
"use client";

import type { Sprint, Task } from "@/lib/kanban/stateReader";
import { SprintCard } from "./SprintCard";

export interface SprintColumnProps {
  state: "current" | "next" | "closed";
  sprints: Sprint[];
  tasksBySprint: Record<string, Task[]>;
  showAllClosed: boolean;
  onToggleShowAll: () => void;
  onSelectSprint: (sprintId: string) => void;
}

const STATE_LABELS: Record<SprintColumnProps["state"], string> = {
  current: "Active",
  next: "Next",
  closed: "Closed",
};

const CLOSED_DEFAULT_LIMIT = 10;

/** Sort sprints for column rendering. Active/Next: by project asc. Closed: by closed_at desc. */
export function sortSprintsForColumn(
  sprints: Sprint[],
  state: "current" | "next" | "closed",
): Sprint[] {
  if (state === "closed") {
    return [...sprints].sort((a, b) =>
      (b.closed_at ?? "").localeCompare(a.closed_at ?? ""),
    );
  }
  return [...sprints].sort((a, b) =>
    (a.project ?? "").localeCompare(b.project ?? ""),
  );
}

/**
 * One column of the Sprints page (Active / Next / Closed).
 * Closed col limits to top 10 by default with "Show all" expand.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-sprints-page.md §2.3, §3.1
 */
export function SprintColumn({
  state,
  sprints,
  tasksBySprint,
  showAllClosed,
  onToggleShowAll,
  onSelectSprint,
}: SprintColumnProps) {
  const sorted = sortSprintsForColumn(sprints, state);
  const isClosed = state === "closed";
  const visible = isClosed && !showAllClosed
    ? sorted.slice(0, CLOSED_DEFAULT_LIMIT)
    : sorted;
  const hidden = isClosed && !showAllClosed
    ? Math.max(0, sorted.length - CLOSED_DEFAULT_LIMIT)
    : 0;

  return (
    <div
      className="sprint-column"
      style={{
        background: "#0d1117",
        borderRadius: 8,
        padding: "0.75rem",
        display: "flex",
        flexDirection: "column",
        gap: "0.5rem",
        minHeight: 200,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
          padding: "0.25rem 0",
          borderBottom: "1px solid #2a2f3e",
          marginBottom: "0.25rem",
        }}
      >
        <span style={{ color: "#e0e0e0", fontWeight: 600, fontSize: "0.95rem" }}>
          {STATE_LABELS[state]}
        </span>
        <span
          style={{
            background: "#2a2f3e",
            color: "#888",
            padding: "0.05rem 0.5rem",
            borderRadius: 10,
            fontSize: "0.72rem",
          }}
        >
          {sorted.length}
        </span>
      </div>
      {visible.length === 0 ? (
        <div style={{ color: "#555", fontSize: "0.8rem", fontStyle: "italic", padding: "1rem 0", textAlign: "center" }}>
          No {STATE_LABELS[state].toLowerCase()} sprints
        </div>
      ) : (
        visible.map((sp) => (
          <SprintCard
            key={sp.id}
            sprint={sp}
            taskCount={(tasksBySprint[sp.id] ?? []).length}
            isClosed={isClosed}
            onClick={() => onSelectSprint(sp.id)}
          />
        ))
      )}
      {hidden > 0 && (
        <button
          type="button"
          onClick={onToggleShowAll}
          style={{
            background: "transparent",
            border: "1px solid #2a2f3e",
            color: "#888",
            padding: "0.4rem 0.5rem",
            borderRadius: 4,
            cursor: "pointer",
            fontSize: "0.78rem",
            marginTop: "0.25rem",
          }}
        >
          Show all ({sorted.length})
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Rodar tests**

```bash
cd ~/code/mission-control && npm test -- --run tests/components/sprints/SprintColumn.test.ts 2>&1 | tail -5
```

Expected: 3/3 pass.

- [ ] **Step 5: Commit**

```bash
cd ~/code/mission-control && git add src/components/sprints/SprintColumn.tsx tests/components/sprints/SprintColumn.test.ts && git commit -m "$(cat <<'EOF'
feat(components/sprints): SprintColumn with sort + Show all expand

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: SprintKanbanModal component

**Files:**
- Create: `mission-control/src/components/sprints/SprintKanbanModal.tsx`
- Create: `mission-control/tests/components/sprints/SprintKanbanModal.test.ts`

- [ ] **Step 1: Escrever contract tests**

Write `~/code/mission-control/tests/components/sprints/SprintKanbanModal.test.ts`:

```typescript
/**
 * Contract tests for SprintKanbanModal.
 * Type-level + helpers (pure logic).
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-sprints-page.md §3.1, §4.4
 */
import { describe, it, expect } from "vitest";
import type { SprintKanbanModalProps } from "@/components/sprints/SprintKanbanModal";

describe("SprintKanbanModalProps contract", () => {
  it("requires sprintId, sprint, onClose; onMutate optional", () => {
    const props: SprintKanbanModalProps = {
      sprintId: "sprint-22",
      sprint: {
        id: "sprint-22",
        name: "Sprint 22",
        state: "current",
        project: "test-project",
        created_at: "2026-04-25",
        closed_at: null,
        created_by: "bernard",
      },
      tasks: [],
      onClose: () => {},
    };
    expect(props.sprintId).toBe("sprint-22");
  });
});

describe("buildKanbanLink helper", () => {
  it("constructs /kanban URL with sprint + project params", () => {
    const { buildKanbanLink } = require("@/components/sprints/SprintKanbanModal");
    const link = buildKanbanLink("sprint-22", "test-project");
    expect(link).toBe("/kanban?sprint=sprint-22&project=test-project");
  });

  it("handles null project gracefully", () => {
    const { buildKanbanLink } = require("@/components/sprints/SprintKanbanModal");
    const link = buildKanbanLink("sprint-22", null);
    expect(link).toBe("/kanban?sprint=sprint-22");
  });
});
```

- [ ] **Step 2: Rodar tests (devem falhar)**

```bash
cd ~/code/mission-control && npm test -- --run tests/components/sprints/SprintKanbanModal.test.ts 2>&1 | tail -5
```

Expected: ERR.

- [ ] **Step 3: Criar `src/components/sprints/SprintKanbanModal.tsx`**

```typescript
"use client";

import { useEffect } from "react";
import Link from "next/link";
import type { Sprint, Task, TaskStatus } from "@/lib/kanban/stateReader";
import { Board } from "@/components/kanban/Board";
import { extractSprintNumber } from "./SprintCard";

export interface SprintKanbanModalProps {
  sprintId: string;
  sprint: Sprint | undefined;
  tasks: Task[];
  onClose: () => void;
  onMutate?: () => void;
}

/** Build deep-link to /kanban scoped to a specific sprint + project. */
export function buildKanbanLink(sprintId: string, project: string | null): string {
  if (project) {
    return `/kanban?sprint=${sprintId}&project=${project}`;
  }
  return `/kanban?sprint=${sprintId}`;
}

/**
 * Modal centered overlay embedding kanban Board for a specific sprint.
 * Closed sprints render a yellow banner; mutations may fail server-side.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-sprints-page.md §3.1, §4.4
 */
export function SprintKanbanModal({
  sprintId,
  sprint,
  tasks,
  onClose,
  onMutate,
}: SprintKanbanModalProps) {
  // Esc handler
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  // Sprint not found state
  if (!sprint) {
    return (
      <div className="modal-backdrop" onClick={onClose} style={backdropStyle}>
        <div
          className="modal-box"
          onClick={(e) => e.stopPropagation()}
          style={{ ...modalBoxStyle, maxWidth: 480, padding: "2rem" }}
        >
          <div style={{ color: "#e46e6e", fontWeight: 600, marginBottom: "0.5rem" }}>
            Sprint not found
          </div>
          <div style={{ color: "#888", fontSize: "0.85rem", marginBottom: "1rem" }}>
            Sprint id <code>{sprintId}</code> não existe no kanban state.
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: "#2a2f3e",
              color: "#e0e0e0",
              border: "none",
              padding: "0.5rem 1rem",
              borderRadius: 4,
              cursor: "pointer",
            }}
          >
            Close
          </button>
        </div>
      </div>
    );
  }

  const isClosed = sprint.state === "closed";
  const sprintNum = extractSprintNumber(sprint.id);
  const sprintLabel = sprintNum !== null ? `Sprint ${sprintNum}` : sprint.name;
  const project = sprint.project ?? "?";

  // Stub handlers: mutations call API directly; refresh via onMutate callback.
  // In v1 these forward to /api/kanban/tasks/<id> (existing routes).
  const onMove = async (taskId: string, newStatus: TaskStatus) => {
    try {
      const r = await fetch(`/api/kanban/tasks/${taskId}/move`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        const detail = (j as Record<string, unknown>).detail;
        throw new Error(typeof detail === "string" ? detail : `HTTP ${r.status}`);
      }
      onMutate?.();
    } catch (err) {
      // V1: alert; future: toast
      alert(`Move failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  };
  const onArchive = async (taskId: string) => {
    try {
      const r = await fetch(`/api/kanban/tasks/${taskId}/archive`, { method: "POST" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      onMutate?.();
    } catch (err) {
      alert(`Archive failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  };
  const onOpenDetail = (_taskId: string) => {
    /* DetailDrawer integration deferred: v1 modal does not embed DetailDrawer.
       User clicks "Open in /kanban" pra acesso completo de detail editing. */
  };

  return (
    <div
      className="modal-backdrop"
      onClick={onClose}
      style={backdropStyle}
    >
      <div
        className="modal-box"
        onClick={(e) => e.stopPropagation()}
        style={modalBoxStyle}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "0.75rem 1rem",
            borderBottom: "1px solid #2a2f3e",
          }}
        >
          <div style={{ display: "flex", gap: "0.6rem", alignItems: "baseline" }}>
            <span style={{ color: "#4f9eff", fontWeight: 600 }}>{sprintLabel}</span>
            <span style={{ color: "#888", fontSize: "0.85rem" }}>· {project}</span>
          </div>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <Link
              href={buildKanbanLink(sprintId, sprint.project)}
              style={{
                background: "#2a2f3e",
                color: "#4f9eff",
                padding: "0.35rem 0.7rem",
                borderRadius: 4,
                fontSize: "0.8rem",
                textDecoration: "none",
              }}
            >
              Open in /kanban →
            </Link>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close modal"
              style={{
                background: "transparent",
                border: "none",
                color: "#888",
                fontSize: "1.4rem",
                cursor: "pointer",
                padding: "0 0.4rem",
                lineHeight: 1,
              }}
            >
              ×
            </button>
          </div>
        </div>

        {/* Closed banner */}
        {isClosed && (
          <div
            style={{
              background: "#5f5a1e",
              color: "#e4dc6e",
              padding: "0.5rem 1rem",
              fontSize: "0.85rem",
              borderBottom: "1px solid #2a2f3e",
            }}
          >
            ⚠ This sprint is closed (mutations may fail with kanban invariant errors)
          </div>
        )}

        {/* Body: kanban Board */}
        <div style={{ flex: 1, overflow: "auto", padding: "1rem" }}>
          <Board
            tasks={tasks}
            onMove={onMove}
            onArchive={onArchive}
            onOpenDetail={onOpenDetail}
          />
        </div>
      </div>
    </div>
  );
}

const backdropStyle: React.CSSProperties = {
  position: "fixed",
  inset: 0,
  background: "rgba(0,0,0,0.6)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  zIndex: 100,
};

const modalBoxStyle: React.CSSProperties = {
  background: "#161b22",
  borderRadius: 8,
  width: "90%",
  height: "85%",
  maxWidth: 1400,
  maxHeight: 900,
  display: "flex",
  flexDirection: "column",
  boxShadow: "0 8px 32px rgba(0,0,0,0.6)",
  border: "1px solid #2a2f3e",
};
```

- [ ] **Step 4: Rodar tests**

```bash
cd ~/code/mission-control && npm test -- --run tests/components/sprints/SprintKanbanModal.test.ts 2>&1 | tail -5
```

Expected: 3/3 pass.

- [ ] **Step 5: Commit**

```bash
cd ~/code/mission-control && git add src/components/sprints/SprintKanbanModal.tsx tests/components/sprints/SprintKanbanModal.test.ts && git commit -m "$(cat <<'EOF'
feat(components/sprints): SprintKanbanModal with Board embed + closed banner

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: SprintsPage page client component

**Files:**
- Create: `mission-control/src/app/(dashboard)/sprints/page.tsx`
- Create: `mission-control/tests/app/(dashboard)/sprints/page.test.ts`

- [ ] **Step 1: Escrever contract tests**

Write `~/code/mission-control/tests/app/(dashboard)/sprints/page.test.ts`:

```typescript
/**
 * Contract tests for SprintsPage.
 *
 * Page é client component com hooks; render-time tests não funcionam aqui (vide
 * NewTaskModal.test.ts pattern). Cobertura focada em pure helpers extraídos.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-sprints-page.md §4.2
 */
import { describe, it, expect } from "vitest";

describe("SprintsPage helpers", () => {
  it("groupTasksBySprintId groups correctly", () => {
    const { groupTasksBySprintId } = require("@/app/(dashboard)/sprints/page");
    const tasks = [
      { id: "T-1", sprint_id: "sprint-1" },
      { id: "T-2", sprint_id: "sprint-1" },
      { id: "T-3", sprint_id: "sprint-2" },
    ] as any[];
    const result = groupTasksBySprintId(tasks);
    expect(result["sprint-1"]).toHaveLength(2);
    expect(result["sprint-2"]).toHaveLength(1);
    expect(result["sprint-3"]).toBeUndefined();
  });

  it("filterSprintsByProject filters when project arg given", () => {
    const { filterSprintsByProject } = require("@/app/(dashboard)/sprints/page");
    const sprints = [
      { id: "s1", project: "bevox-mobile" },
      { id: "s2", project: "openclaw" },
      { id: "s3", project: "bevox-mobile" },
    ] as any[];
    expect(filterSprintsByProject(sprints, "bevox-mobile")).toHaveLength(2);
    expect(filterSprintsByProject(sprints, null)).toHaveLength(3);
    expect(filterSprintsByProject(sprints, "unknown")).toHaveLength(0);
  });

  it("groupSprintsByState groups into 3 buckets", () => {
    const { groupSprintsByState } = require("@/app/(dashboard)/sprints/page");
    const sprints = [
      { id: "s1", state: "current" },
      { id: "s2", state: "next" },
      { id: "s3", state: "closed" },
      { id: "s4", state: "current" },
    ] as any[];
    const grouped = groupSprintsByState(sprints);
    expect(grouped.current).toHaveLength(2);
    expect(grouped.next).toHaveLength(1);
    expect(grouped.closed).toHaveLength(1);
  });
});
```

- [ ] **Step 2: Rodar tests (devem falhar)**

```bash
cd ~/code/mission-control && npm test -- --run "tests/app/(dashboard)/sprints/page.test.ts" 2>&1 | tail -5
```

Expected: ERR.

- [ ] **Step 3: Criar `src/app/(dashboard)/sprints/page.tsx`**

Create directory first if needed: `mkdir -p src/app/\(dashboard\)/sprints`.

```typescript
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { Sprint, Task, State } from "@/lib/kanban/stateReader";
import { SprintColumn } from "@/components/sprints/SprintColumn";
import { SprintKanbanModal } from "@/components/sprints/SprintKanbanModal";

interface KanbanStateResponse {
  schema_version: number;
  projects: string[];
  currentSprintByProject: Record<string, string>;
  sprints: Sprint[];
  tasks: Task[];
}

/** Group tasks by sprint_id for fast lookup. */
export function groupTasksBySprintId(tasks: Task[]): Record<string, Task[]> {
  const map: Record<string, Task[]> = {};
  for (const t of tasks) {
    if (!map[t.sprint_id]) map[t.sprint_id] = [];
    map[t.sprint_id].push(t);
  }
  return map;
}

/** Filter sprints by project (null = all). */
export function filterSprintsByProject(
  sprints: Sprint[],
  project: string | null,
): Sprint[] {
  if (!project) return sprints;
  return sprints.filter((s) => s.project === project);
}

/** Group sprints by state (current / next / closed). */
export function groupSprintsByState(sprints: Sprint[]): {
  current: Sprint[];
  next: Sprint[];
  closed: Sprint[];
} {
  return {
    current: sprints.filter((s) => s.state === "current"),
    next: sprints.filter((s) => s.state === "next"),
    closed: sprints.filter((s) => s.state === "closed"),
  };
}

/**
 * /sprints — cross-project sprints list with 3 columns + click → modal.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-sprints-page.md
 */
export default function SprintsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectFilter = searchParams.get("project");
  const selectedSprintId = searchParams.get("sprint");

  const [state, setState] = useState<KanbanStateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showAllClosed, setShowAllClosed] = useState(false);

  const fetchState = useCallback(async () => {
    try {
      const r = await fetch("/api/kanban/state", { cache: "no-store" });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        const detail = (j as Record<string, unknown>).detail;
        throw new Error(typeof detail === "string" ? detail : `HTTP ${r.status}`);
      }
      const data = (await r.json()) as KanbanStateResponse;
      setState(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    fetchState();
  }, [fetchState]);

  const tasksBySprint = useMemo(
    () => (state ? groupTasksBySprintId(state.tasks) : {}),
    [state],
  );

  const filteredSprints = useMemo(
    () => (state ? filterSprintsByProject(state.sprints, projectFilter) : []),
    [state, projectFilter],
  );

  const grouped = useMemo(() => groupSprintsByState(filteredSprints), [filteredSprints]);

  const setSelectedSprint = useCallback(
    (sprintId: string | null) => {
      const params = new URLSearchParams(searchParams.toString());
      if (sprintId) {
        params.set("sprint", sprintId);
      } else {
        params.delete("sprint");
      }
      const qs = params.toString();
      router.replace(qs ? `/sprints?${qs}` : "/sprints", { scroll: false });
    },
    [router, searchParams],
  );

  const setProjectFilter = useCallback(
    (project: string | null) => {
      const params = new URLSearchParams(searchParams.toString());
      if (project) {
        params.set("project", project);
      } else {
        params.delete("project");
      }
      const qs = params.toString();
      router.replace(qs ? `/sprints?${qs}` : "/sprints", { scroll: false });
    },
    [router, searchParams],
  );

  const selectedSprint = useMemo(
    () => (selectedSprintId && state
      ? state.sprints.find((s) => s.id === selectedSprintId)
      : undefined),
    [selectedSprintId, state],
  );

  const selectedTasks = useMemo(
    () => (selectedSprintId ? tasksBySprint[selectedSprintId] ?? [] : []),
    [selectedSprintId, tasksBySprint],
  );

  if (error) {
    return (
      <div style={{ padding: "2rem" }}>
        <h1 style={{ color: "#e0e0e0" }}>Sprints</h1>
        <div style={{ color: "#e46e6e", padding: "1rem", background: "#3f1e1e", borderRadius: 4, marginTop: "1rem" }}>
          Failed to load: {error}
          <button
            type="button"
            onClick={fetchState}
            style={{
              marginLeft: "1rem",
              background: "#2a2f3e",
              color: "#e0e0e0",
              border: "none",
              padding: "0.3rem 0.7rem",
              borderRadius: 4,
              cursor: "pointer",
            }}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!state) {
    return (
      <div style={{ padding: "2rem", color: "#888" }}>Loading sprints...</div>
    );
  }

  return (
    <div style={{ padding: "1.5rem", color: "#e0e0e0" }}>
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "1.5rem",
        }}
      >
        <h1 style={{ fontSize: "1.5rem", fontWeight: 600, margin: 0 }}>Sprints</h1>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <label htmlFor="project-filter" style={{ color: "#888", fontSize: "0.85rem" }}>
            Project:
          </label>
          <select
            id="project-filter"
            value={projectFilter ?? ""}
            onChange={(e) => setProjectFilter(e.target.value || null)}
            style={{
              background: "#1a2230",
              color: "#e0e0e0",
              border: "1px solid #2a2f3e",
              padding: "0.35rem 0.6rem",
              borderRadius: 4,
              fontSize: "0.85rem",
            }}
          >
            <option value="">All projects</option>
            {state.projects.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>
      </header>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: "1rem",
        }}
      >
        <SprintColumn
          state="current"
          sprints={grouped.current}
          tasksBySprint={tasksBySprint}
          showAllClosed={showAllClosed}
          onToggleShowAll={() => setShowAllClosed((v) => !v)}
          onSelectSprint={(id) => setSelectedSprint(id)}
        />
        <SprintColumn
          state="next"
          sprints={grouped.next}
          tasksBySprint={tasksBySprint}
          showAllClosed={showAllClosed}
          onToggleShowAll={() => setShowAllClosed((v) => !v)}
          onSelectSprint={(id) => setSelectedSprint(id)}
        />
        <SprintColumn
          state="closed"
          sprints={grouped.closed}
          tasksBySprint={tasksBySprint}
          showAllClosed={showAllClosed}
          onToggleShowAll={() => setShowAllClosed((v) => !v)}
          onSelectSprint={(id) => setSelectedSprint(id)}
        />
      </div>

      {selectedSprintId && (
        <SprintKanbanModal
          sprintId={selectedSprintId}
          sprint={selectedSprint}
          tasks={selectedTasks}
          onClose={() => setSelectedSprint(null)}
          onMutate={fetchState}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 4: Rodar tests**

```bash
cd ~/code/mission-control && npm test -- --run "tests/app/(dashboard)/sprints/page.test.ts" 2>&1 | tail -5
```

Expected: 3/3 pass.

- [ ] **Step 5: Commit**

```bash
cd ~/code/mission-control && git add "src/app/(dashboard)/sprints/page.tsx" "tests/app/(dashboard)/sprints/page.test.ts" && git commit -m "$(cat <<'EOF'
feat(app/sprints): SprintsPage with 3 columns + project filter + modal

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Sidebar entry + Calendar icon

**Files:**
- Modify: `mission-control/src/components/Sidebar.tsx`

- [ ] **Step 1: Inspecionar Sidebar imports**

```bash
grep -n "from \"lucide-react\"\|import {" ~/code/mission-control/src/components/Sidebar.tsx | head -5
```

Confirma que `lucide-react` está sendo importado e ver se `Calendar` já está importado.

- [ ] **Step 2: Adicionar Calendar import + Sprints entry**

Editar `src/components/Sidebar.tsx`:

(a) Adicionar `Calendar` ao import de `lucide-react` se ainda não existir:

```typescript
import {
  // ... existing imports
  Calendar,  // NEW
  // ...
} from "lucide-react";
```

(b) Adicionar entry no array de items, entre Projects e Roadmap. Find:

```typescript
{ href: "/projects", label: "Projects", icon: LayoutGrid },
{ href: "/roadmap", label: "Roadmap", icon: Map },
```

Replace with:

```typescript
{ href: "/projects", label: "Projects", icon: LayoutGrid },
{ href: "/sprints", label: "Sprints", icon: Calendar },
{ href: "/roadmap", label: "Roadmap", icon: Map },
```

- [ ] **Step 3: Rodar typecheck (se script existe) + tests**

```bash
cd ~/code/mission-control && npm test -- --run 2>&1 | tail -5
```

Expected: todos os tests anteriores + os novos da feat continuam green. Suite total deve crescer com os tests adicionados.

- [ ] **Step 4: Smoke local — dev server (opcional pra verificar visual)**

```bash
cd ~/code/mission-control && timeout 30 npm run dev 2>&1 &
sleep 8
curl -s -H "Cf-Access-Authenticated-User-Email: you@example.com" http://localhost:3000/sprints 2>&1 | head -20
```

(Se Bernard quer visual confirmation antes de PR, pode browse `localhost:3000/sprints`.)

- [ ] **Step 5: Commit**

```bash
cd ~/code/mission-control && git add src/components/Sidebar.tsx && git commit -m "$(cat <<'EOF'
feat(sidebar): adicionar Sprints entry entre Projects e Roadmap

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Push openclaw plan PR + push mission-control feat PR + pause

- [ ] **Step 1: Push openclaw plan**

```bash
cd ~/.openclaw && git push -u origin feat/mc-sprints-page-plan
gh pr create --title "plan(mc-sprints-page): implementation plan" --body "Plan doc for spec bevox-knowledge/35_specs/company-os/2026-04-25-mc-sprints-page.md (PR #merged)."
```

(Pode mergeer direto — é só docs internas.)

- [ ] **Step 2: Verify mission-control branch + suite final**

```bash
cd ~/code/mission-control && git status --short
git log --oneline main..HEAD | head -10
npm test -- --run 2>&1 | tail -3
```

Expected: 6 commits novos (PROJECT_COLORS + SprintCard + SprintColumn + SprintKanbanModal + page + Sidebar). Suite com ~14 tests novos green.

- [ ] **Step 3: Push mission-control + open PR**

```bash
cd ~/code/mission-control && git push -u origin feat/mc-sprints-page
gh pr create --title "feat(mc): /sprints page with 3 columns + modal kanban (E2/mc-sprints-page)" --body "$(cat <<'EOF'
## Summary
Nova rota \`/sprints\` no Mission Control: cross-project lista 3 colunas (Active | Next | Closed) com cards minimal por sprint; click em card abre modal centrado com kanban full editável.

Backend 100% pronto (\`GET /api/kanban/state\` já entrega sprints[] + currentSprintByProject). Wave puramente frontend.

Spec: \`bevox-knowledge/35_specs/company-os/2026-04-25-mc-sprints-page.md\` (PR #merged)
Plano: \`openclaw/docs/superpowers/plans/2026-04-25-mc-sprints-page.md\`

## What's in this PR
6 commits TDD:
- PROJECT_COLORS helper (10 canonical projects)
- SprintCard component (minimal: chip + sprint name + task count)
- SprintColumn component (sort + Show all expand)
- SprintKanbanModal component (Board embed + closed banner + Open in /kanban)
- SprintsPage page (3 columns + URL state deep-link)
- Sidebar entry (Calendar icon between Projects e Roadmap)

## Test plan
- [x] Vitest novos: ~14 tests (helpers + props contracts)
- [ ] **Pós-merge:** pull + npm install + npm run build + systemctl restart mission-control
- [ ] Smoke E2E 6 cenários gating

## Rollback
Frontend-only, sem data risk. Tier 1: \`git revert <merge-sha> && git push && pull && rebuild && restart\`. URL /sprints volta a 404.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: PAUSA — aguardar Bernard mergear o MC PR**

Parar aqui. Bernard revisa + merge `bernardTavares/mission-control`. Retomar Task 9 só após merge confirmado em main.

---

## Task 9: Pull main + npm install + build + restart MC + verify

**Pré-requisito:** PR mergeada; main atualizada no GitHub.

- [ ] **Step 1: Pull main local**

```bash
cd ~/code/mission-control && git checkout main && git pull --ff-only
git log --oneline -3
```

Expected: merge commit visível.

- [ ] **Step 2: Install + build**

```bash
cd ~/code/mission-control && npm install 2>&1 | tail -3
npm run build 2>&1 | tail -10
```

Expected: build succeeds, Next.js mostra rota `/sprints` na lista (○ static OR ƒ dynamic).

- [ ] **Step 3: Restart service**

```bash
systemctl --user restart mission-control
sleep 3
systemctl --user is-active mission-control
```

Expected: `active`.

- [ ] **Step 4: Health probe localhost**

```bash
curl -sS -H "Cf-Access-Authenticated-User-Email: you@example.com" http://127.0.0.1:4310/sprints 2>&1 | head -5
```

Expected: HTTP response (200 + HTML, ou redirect to login se Cf-Access fail). NÃO 404.

```bash
curl -sS -H "Cf-Access-Authenticated-User-Email: you@example.com" http://127.0.0.1:4310/api/kanban/state 2>&1 | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print('schema_version:', d.get('schema_version'))
    print('sprints count:', len(d.get('sprints', [])))
    print('currentSprintByProject keys:', sorted(d.get('currentSprintByProject', {}).keys()))
except Exception as e:
    print('error:', e)
"
```

Expected: 200 + schema_version 4 + sprints array + currentSprintByProject map populated.

---

## Task 10: Smoke E2E (6 cenários gating)

**Pré-requisito:** Task 9 completa; serviço rodando código novo.

Smoke tests requerem browser interativo (Cloudflare Access cookie). Bernard abre `mc.example.com/sprints` e valida.

- [ ] **Cenário 1: Default page renders 3 columns + sidebar entry**

Bernard abre `mc.example.com/sprints`:
- Sidebar tem entry "Sprints" entre Projects e Roadmap (Calendar icon).
- Header mostra "Sprints" h1 + dropdown "Project: All ▼".
- 3 colunas renderizam: Active (~10), Next (~10), Closed (~24).
- Cards minimal: project chip colorido + Sprint N + N tasks.

Pass: ✓ se tudo isso visível. Fail: rollback Tier 1.

- [ ] **Cenário 2: Project filter funciona + URL deep-link**

- Selecionar "bevox-mobile" no dropdown → URL atualiza pra `?project=bevox-mobile`.
- Cards filtram (só sprints de bevox-mobile visíveis).
- Reload page com URL → filtro reaplicado.
- Selecionar "All projects" → filtro removido + URL clean.

- [ ] **Cenário 3: Click em card abre modal + URL deep-link**

- Click num SprintCard → modal abre centrado, URL ganha `?sprint=sprint-X`.
- Modal header mostra "Sprint N · project" + "Open in /kanban →" link + X button.
- Body mostra kanban Board com tasks dessa sprint.
- Esc fecha modal + URL clean.
- Click backdrop fecha modal.
- Click X fecha modal.

- [ ] **Cenário 4: Closed sprint banner + read-only experience**

- Click num card de sprint **closed** (e.g., sprint-22 ou sprint-21).
- Banner amarelo `⚠ This sprint is closed` aparece no topo do modal.
- Tentar mover task (drag) → API rejeita; alert/toast com erro.
- Card no fundo permanece sem mudança.

- [ ] **Cenário 5: Closed col Show all expansion**

- Closed col mostra top 10 + "Show all (24)" button.
- Click button → todos os 24 cards expandem.
- Performance OK (smooth scroll).

- [ ] **Cenário 6: "Open in /kanban" navigation**

- Modal aberto pra sprint específica → click "Open in /kanban →".
- Browser navega pra `/kanban?sprint=sprint-X&project=Y`.
- Kanban full page abre com filtro aplicado.
- Browser back → volta pra Sprints page com modal **fechado** (URL `/sprints` clean).

**Step 7 — Smoke gate:** 6/6 pass → wave delivered. Falha em qualquer cenário → rollback Tier 1 (git revert + rebuild).

---

## Task 11: Tracker entry — wave delivered

**Files:**
- Modify: `bevox-knowledge/40_roadmap/_shared/delivery-tracker.yml`

- [ ] **Step 1: Branch + add entry**

```bash
cd ~/bevox-knowledge && git checkout main && git pull --ff-only
git checkout -b draft/tracker-mc-sprints-page-delivered
```

Find E2 epic block in `40_roadmap/_shared/delivery-tracker.yml` (search `id: E2`). Identify last existing wave entry under E2 (likely `F-projects-dashboard` ou similar). Insert new entry below:

```yaml
      - id: mc-sprints-page
        status: delivered
        delivered_at: 2026-04-25
        spec: 35_specs/company-os/2026-04-25-mc-sprints-page.md
        pr_mc: https://github.com/bernardTavares/mission-control/pull/<N>
        pr_openclaw_plan: https://github.com/bernardTavares/openclaw/pull/<N>
        narrative: "MC ganha rota /sprints cross-project com 3 colunas Active/Next/Closed + click → modal kanban editável da sprint"
        features:
          - "Sub-projeto do PRD A (frontend redesign) — entrega só Sprints page focada; detail page redesign + Knowledge per-project view ficam pra waves futuras"
          - "Nova rota /sprints renderiza 3 colunas cross-project (Active | Next | Closed) com cards minimal (project chip color-coded + sprint id + task count)"
          - "Click em card abre modal centrado (90% × 85%) embedando <Board> existing com tasks dessa sprint; Esc/X/backdrop fecham"
          - "Closed sprints exibem banner amarelo no modal; mutations habilitadas mas API rejeita (invariant schema v4); UI surface educacional"
          - "Project filter dropdown no header + URL deep-link ?project=X; modal state via URL ?sprint=sprint-N (browser back natural)"
          - "Closed col scaling: top 10 by closed_at desc + 'Show all (N)' button expand"
          - "Sidebar nova entry 'Sprints' (Calendar icon) entre Projects e Roadmap"
          - "PROJECT_COLORS map com 10 projetos canônicos hardcoded em src/lib/projects/colors.ts"
          - "Reuso máximo de componentes existentes: <Board> (já tem readOnly prop + tasks pre-filtered pattern); zero mudança em /kanban"
          - "Sem mudança em backend: GET /api/kanban/state já entregava sprints[] + currentSprintByProject (delivered em waves anteriores sprint-per-project + same-session-reuse)"
          - "~14 vitest tests novos: contract-based + helper logic (pattern de NewTaskModal.test.ts pré-existente — sem renderToStaticMarkup pra components com hooks)"
          - "Smoke E2E pós-deploy validou 6 cenários gating: 3 cols renderizam + sidebar entry; project filter + URL; modal abre/fecha (Esc/X/backdrop); closed banner; Show all expand; Open in /kanban navigation"
          - "Frontend-only wave: sem schema migration, sem data risk; rollback Tier 1 = git revert + rebuild + restart (segundos)"
```

(Substituir `<N>` pelos PR numbers reais.)

- [ ] **Step 2: Validar YAML + commit + push + PR**

```bash
cd ~/bevox-knowledge && python3 -c "import yaml; yaml.safe_load(open('40_roadmap/_shared/delivery-tracker.yml')); print('valid')"
git add 40_roadmap/_shared/delivery-tracker.yml
git commit -m "$(cat <<'EOF'
tracker(E2/mc-sprints-page): delivered 2026-04-25

Mission Control ganha rota /sprints cross-project com 3 colunas + modal
kanban embedado. Sub-projeto do PRD A frontend redesign — detail page
e Knowledge view ficam pra waves futuras dedicadas.

PRs: mission-control #<N>, openclaw plan #<N>, bevox-knowledge spec #<N>
Spec: 35_specs/company-os/2026-04-25-mc-sprints-page.md
Smoke E2E 6 cenários gating todos pass.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git push -u origin draft/tracker-mc-sprints-page-delivered
gh pr create --title "tracker(E2/mc-sprints-page): delivered 2026-04-25" --body "## Summary
Entry no delivery-tracker registrando wave \`mc-sprints-page\` do E2 como delivered.

## Test plan
- [x] YAML válido
- [x] Smoke E2E 6 cenários executados (§8.2 spec)
- [x] PRs (spec + plan + impl) merged

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

- [ ] **Step 3: Aguardar Bernard mergear**

Bernard merge → wave fechada formalmente.

---

## Self-review

**Spec coverage:**
- §1 decisões → Tasks 2-7 implementam todas (cross-project ✓, 3-cols ✓, modal ✓, minimal cards ✓, Show all ✓, full editable ✓)
- §2 page architecture → Tasks 6 (page) + 7 (Sidebar)
- §3 components → Tasks 2-5 (cada um 1 component) + Task 6 (page assembly)
- §3.4 PROJECT_COLORS → Task 2
- §4 data flow → Task 6 (page state + URL sync + fetchState)
- §4.5 mutation refresh → Task 6 (onMutate callback in modal)
- §5 edge cases → Task 6 (error state, loading, sprint not found in modal)
- §6 arquivos → file structure section maps 1:1
- §7 ordem dos PRs → Tasks 1, 8, 9, 10, 11 implementam a sequência
- §8 testing → 14 vitest tests distribuídos (Tasks 2-6) + 6 smoke gating (Task 10)
- §9 DoD → 10 critérios cobertos pelos cenários da Task 10
- §10 rollback → Task 8 PR description menciona Tier 1 git revert
- §11 não-escopo → docs em spec; nenhum task vaza scope

**Placeholder scan:** zero TBD/TODO. Code blocks completos em todos os steps.

**Type consistency:**
- `SprintCardProps` (Task 3) usado consistentemente em SprintColumn (Task 4) que importa SprintCard.
- `SprintColumnProps.onSelectSprint: (sprintId: string) => void` (Task 4) bate com chamada em SprintsPage (Task 6).
- `SprintKanbanModalProps.tasks: Task[]` (Task 5) — SprintsPage passa `selectedTasks` array (Task 6) ✓.
- `Board` props (já existentes: tasks, onMove, onArchive, onOpenDetail, readOnly?) usados em Modal (Task 5) ✓.

Issues encontrados: nenhum.
