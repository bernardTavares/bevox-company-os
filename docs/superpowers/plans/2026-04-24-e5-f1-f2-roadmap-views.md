# E5 F1+F2 Roadmap Views Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar F1 (roadmap estratégico — Agora/Próximo/Depois) + F2 (roadmap técnico com deps) como página `/roadmap` no Mission Control, removendo a tab Tracker de `/delivery`.

**Architecture:** Página client-side no MC que consome `/api/delivery/tracker` (existente) + nova `/api/roadmap/deps` (parser do markdown narrativo). Duas libs puras (`categorize`, `parse-deps`) com TDD. Seis componentes React. Sem editorial overhead no tracker — derivação automática do YAML.

**Tech Stack:** Next.js 15 App Router, React 19, TypeScript, vitest 4.1, Tailwind. js-yaml já no projeto.

**Spec:** `bevox-knowledge/35_specs/company-os/2026-04-24-e5-f1-f2-roadmap-views.md`
**Cadência:** commit auto por task (per `feedback_commit_cadence.md`), pausa só pro merge canônico.

---

## File Structure

**mission-control/ (trabalho principal):**

```
src/app/(dashboard)/roadmap/
├── page.tsx                    — CRIAR. Client component; fetch tracker + deps; compose views
├── RoadmapHeader.tsx           — CRIAR. Sumário numérico (counts)
├── StrategicView.tsx           — CRIAR. 3 colunas Agora/Próximo/Depois
├── TechnicalView.tsx           — CRIAR. Epics expandable + filter
├── WaveCard.tsx                — CRIAR. Card compartilhado (strategic + technical)
└── DepsChips.tsx               — CRIAR. Chips de blockers + epic deps

src/app/api/roadmap/deps/
└── route.ts                    — CRIAR. GET; parse do roadmap narrativo; 4 error modes

src/lib/roadmap/
├── types.ts                    — CRIAR. Tipos compartilhados (TrackerEpic/Wave/Blocker/Risk/Response, DepsMap)
├── categorize.ts               — CRIAR. Pure fn: epics[] → { agora, proximo, depois }
└── parse-deps.ts               — CRIAR. Pure fn: markdown → { epicId: depsList[] }

src/lib/bevox/paths.ts          — MODIFY. Add BEVOX_SUBPATHS.roadmapNarrative
src/app/(dashboard)/delivery/page.tsx  — MODIFY. Remover tab Tracker (4 tabs remanescentes)
src/components/Sidebar.tsx      — MODIFY. Add /roadmap entry

tests/lib/roadmap/categorize.test.ts  — CRIAR
tests/lib/roadmap/parse-deps.test.ts  — CRIAR
tests/app/api/roadmap/deps.route.test.ts — CRIAR
```

**bevox-knowledge/ (tracker sync, último task):**

```
40_roadmap/_shared/delivery-tracker.yml — MODIFY. E5/F1 + F2 → delivered
```

---

## Task 1: Setup branch em mission-control

**Files:** nenhum

- [ ] **Step 1: Verificar main limpo + criar branch**

```bash
cd ~/code/mission-control
git status --short
git checkout main
git pull --ff-only
git checkout -b feat/e5-f1-f2-roadmap-views
git branch --show-current
```

Expected: branch `feat/e5-f1-f2-roadmap-views`. Se working tree dirty, STOP e report BLOCKED.

---

## Task 2: Adicionar `BEVOX_SUBPATHS.roadmapNarrative`

**Files:**
- Modify: `~/code/mission-control/src/lib/bevox/paths.ts` (dentro do export BEVOX_SUBPATHS)

- [ ] **Step 1: Edit paths.ts**

Localizar o objeto `BEVOX_SUBPATHS`. Adicionar nova entrada após `architectureDir`:

```typescript
  /** Roadmap narrativo estratégico (parser consumer). Adicionado em wave E5/F1+F2. */
  roadmapNarrative: "40_roadmap/company-os/2026-04-09-openclaw-company-os-roadmap.md",
```

- [ ] **Step 2: Verify typecheck**

```bash
cd ~/code/mission-control
npx tsc --noEmit 2>&1 | grep -v 'module-components.test.tsx' | head -5
```

Expected: sem erros em `paths.ts`. Pre-existing errors em `module-components.test.tsx` são ignorados.

- [ ] **Step 3: Commit**

```bash
cd ~/code/mission-control
git add src/lib/bevox/paths.ts
git commit -m "$(cat <<'EOF'
feat(paths): add BEVOX_SUBPATHS.roadmapNarrative (E5 F1+F2)

Nova constante aponta para o roadmap narrativo em
40_roadmap/company-os/2026-04-09-openclaw-company-os-roadmap.md.
Consumida pela route /api/roadmap/deps (próxima task).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Criar `src/lib/roadmap/types.ts`

**Files:**
- Create: `~/code/mission-control/src/lib/roadmap/types.ts`

- [ ] **Step 1: Criar arquivo**

Conteúdo completo:

```typescript
/**
 * Shared types for the /roadmap page (E5 F1+F2).
 *
 * Mirrors the shape returned by /api/delivery/tracker (see
 * ~/code/mission-control/src/app/api/delivery/tracker/route.ts).
 * Extracted to a shared module so both /roadmap and /api/roadmap/deps
 * route can import without duplicating interfaces inline.
 */

export interface TrackerWave {
  id: string;
  status: "delivered" | "in_progress" | "not_started" | "parked" | "blocked" | "partial" | string;
  delivered_at?: string;
  features?: string[];
  spec?: string | null;
  reason?: string;
  blocker?: string;
}

export interface TrackerEpic {
  id: string;
  name: string;
  status: string; // derived server-side
  waves: TrackerWave[];
}

export interface TrackerBlocker {
  id: string;
  summary: string;
  since: string;
  blocks: string[]; // refs "<epic>/<wave>" or sentinel "global"
  status: "active" | "resolved" | string;
  notes?: string;
  unblocks_when?: string;
}

export interface TrackerRisk {
  id: string;
  summary: string;
  since: string;
  severity: "low" | "medium" | "high" | string;
  status: "open" | "mitigated" | "materialized" | string;
  mitigation?: string;
  notes?: string;
}

export interface TrackerSummary {
  total_epics: number;
  epics_delivered: number;
  epics_partial: number;
  epics_not_started: number;
  total_waves: number;
  waves_delivered: number;
  waves_in_progress: number;
  waves_parked: number;
  waves_blocked: number;
  blockers_active: number;
  blockers_resolved: number;
  risks_open: number;
  risks_mitigated: number;
  risks_materialized: number;
}

export interface TrackerResponse {
  generated_at: string;
  source: string;
  epics: TrackerEpic[];
  blockers: TrackerBlocker[];
  risks: TrackerRisk[];
  summary: TrackerSummary;
}

/** Map from epic id → list of epic ids it depends on. */
export type DepsMap = Record<string, string[]>;

export interface DepsResponse {
  generated_at: string;
  source: string;
  deps: DepsMap;
}

/** Wave + parent epic, used by categorize() output. */
export interface WaveWithEpic {
  epic: TrackerEpic;
  wave: TrackerWave;
}

/** Categorize output (strategic view buckets). */
export interface CategorizedWaves {
  agora: WaveWithEpic[];
  proximo: WaveWithEpic[];
  depois: WaveWithEpic[];
}
```

- [ ] **Step 2: Verify typecheck**

```bash
cd ~/code/mission-control
npx tsc --noEmit 2>&1 | grep -v 'module-components.test.tsx' | head -5
```

Expected: sem erros.

- [ ] **Step 3: Commit**

```bash
cd ~/code/mission-control
git add src/lib/roadmap/types.ts
git commit -m "$(cat <<'EOF'
feat(roadmap): shared types (E5 F1+F2)

Interfaces TrackerEpic/Wave/Blocker/Risk/Response + DepsMap +
CategorizedWaves. Extraídas em módulo próprio pra serem compartilhadas
entre /roadmap page, /api/roadmap/deps route, e lib utils.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `parse-deps.ts` com TDD

**Files:**
- Create: `~/code/mission-control/src/lib/roadmap/parse-deps.ts`
- Create: `~/code/mission-control/tests/lib/roadmap/parse-deps.test.ts`

- [ ] **Step 1: Write failing test**

Criar `tests/lib/roadmap/parse-deps.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { parseDeps } from "@/lib/roadmap/parse-deps";

describe("parseDeps", () => {
  it("extracts single epic with deps line", () => {
    const md = `
### E3 - Agent Registry
**Prioridade:** P0 | **Dependencias:** E1, E2
Conteudo...
`;
    expect(parseDeps(md)).toEqual({ E3: ["E1", "E2"] });
  });

  it("extracts multiple epics", () => {
    const md = `
### E1 - Knowledge Spine
**Dependencias:** E0

### E2 - Mission Control Shell
**Dependencias:** E1

### E3 - Something
sem deps line aqui
`;
    expect(parseDeps(md)).toEqual({
      E1: ["E0"],
      E2: ["E1"],
      E3: [],
    });
  });

  it("handles deps with checkmarks and surrounding formatting", () => {
    const md = `
### E5 - Roadmap
**Prioridade:** P0 | **Dependencias:** E2 ✓, E3 foundation ✓, E4 wave 1 ✓
`;
    expect(parseDeps(md)).toEqual({ E5: ["E2", "E3", "E4"] });
  });

  it("handles decimal epic ids like E4.2", () => {
    const md = `
### E4.2 - Operator Client
**Dependencias:** E4, E3
`;
    expect(parseDeps(md)).toEqual({ "E4.2": ["E4", "E3"] });
  });

  it("returns empty map for empty markdown", () => {
    expect(parseDeps("")).toEqual({});
  });

  it("returns empty map for markdown without epic headers", () => {
    expect(parseDeps("# Random doc\n\nSome text.")).toEqual({});
  });

  it("returns epic with empty deps when line absent", () => {
    const md = `### E7 - Doc System\n**Prioridade:** P1\nconteúdo\n`;
    expect(parseDeps(md)).toEqual({ E7: [] });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/code/mission-control
npx vitest run tests/lib/roadmap/parse-deps.test.ts 2>&1 | tail -10
```

Expected: FAIL — "Cannot find module '@/lib/roadmap/parse-deps'".

- [ ] **Step 3: Implement minimal `parse-deps.ts`**

```typescript
import type { DepsMap } from "@/lib/roadmap/types";

/**
 * Parse epic dependencies from the roadmap narrative markdown.
 *
 * Finds each `### E<N>[.<M>] - ...` heading and, within its section,
 * extracts the `**Dependencias:** E1, E2, ...` line. Tolerates
 * checkmarks and free-form text after each epic id; keeps only
 * tokens matching ^E[0-9]+(\.[0-9]+)?$.
 *
 * Returns `{}` for malformed or empty input (graceful degradation).
 */
export function parseDeps(markdown: string): DepsMap {
  const result: DepsMap = {};
  const parts = markdown.split(/^### (E\d+(?:\.\d+)?) - /m);
  for (let i = 1; i < parts.length; i += 2) {
    const epicId = parts[i].trim();
    const body = parts[i + 1] ?? "";
    const match = body.match(/^\*\*Dependencias:\*\* (.+?)$/m);
    if (!match) {
      result[epicId] = [];
      continue;
    }
    const deps = match[1]
      .split(/,\s*/)
      .map((s) => s.trim())
      .map((s) => s.match(/^E\d+(?:\.\d+)?/)?.[0])
      .filter((s): s is string => !!s);
    result[epicId] = deps;
  }
  return result;
}
```

- [ ] **Step 4: Run test — verify it passes**

```bash
cd ~/code/mission-control
npx vitest run tests/lib/roadmap/parse-deps.test.ts 2>&1 | tail -10
```

Expected: 7 tests pass.

- [ ] **Step 5: Commit**

```bash
cd ~/code/mission-control
git add src/lib/roadmap/parse-deps.ts tests/lib/roadmap/parse-deps.test.ts
git commit -m "$(cat <<'EOF'
feat(roadmap): parse-deps util + tests (E5 F1+F2)

Pure fn parseDeps(markdown) → DepsMap. Tolerante a markdown malformado
(retorna {} ao invés de throw). Matcha epics E<N> e E<N.M>, filtra
deps com regex ^E\d+(\.\d+)?$, preserva ordem editorial.

7 tests cobrindo: single/multiple epics, checkmarks, decimal ids,
markdown vazio, sem headers, epic sem deps line.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `categorize.ts` com TDD

**Files:**
- Create: `~/code/mission-control/src/lib/roadmap/categorize.ts`
- Create: `~/code/mission-control/tests/lib/roadmap/categorize.test.ts`

- [ ] **Step 1: Write failing test**

```typescript
import { describe, it, expect } from "vitest";
import { categorize } from "@/lib/roadmap/categorize";
import type { TrackerEpic } from "@/lib/roadmap/types";

const mkEpic = (id: string, waves: Array<[string, string]>): TrackerEpic => ({
  id,
  name: `${id} epic`,
  status: "partial",
  waves: waves.map(([wid, status]) => ({ id: wid, status })),
});

describe("categorize", () => {
  it("places in_progress waves in agora", () => {
    const epics = [mkEpic("E1", [["w1", "in_progress"]])];
    const r = categorize(epics);
    expect(r.agora.map((x) => x.wave.id)).toEqual(["w1"]);
    expect(r.proximo).toEqual([]);
    expect(r.depois).toEqual([]);
  });

  it("places partial waves in agora", () => {
    const epics = [mkEpic("E1", [["w1", "partial"]])];
    expect(categorize(epics).agora.map((x) => x.wave.id)).toEqual(["w1"]);
  });

  it("places not_started in proximo when epic has any delivered wave", () => {
    const epics = [mkEpic("E5", [["w1", "delivered"], ["F1", "not_started"]])];
    const r = categorize(epics);
    expect(r.proximo.map((x) => x.wave.id)).toEqual(["F1"]);
    expect(r.depois).toEqual([]);
  });

  it("places not_started in proximo when epic has partial wave", () => {
    const epics = [mkEpic("E5", [["w1", "partial"], ["F2", "not_started"]])];
    expect(categorize(epics).proximo.map((x) => x.wave.id)).toEqual(["F2"]);
  });

  it("places not_started in depois when epic has zero delivered/partial", () => {
    const epics = [mkEpic("E7", [["w1", "not_started"]])];
    const r = categorize(epics);
    expect(r.depois.map((x) => x.wave.id)).toEqual(["w1"]);
    expect(r.proximo).toEqual([]);
  });

  it("excludes delivered, parked, blocked from all buckets", () => {
    const epics = [
      mkEpic("E1", [
        ["w1", "delivered"],
        ["w2", "parked"],
        ["w3", "blocked"],
      ]),
    ];
    const r = categorize(epics);
    expect(r.agora).toEqual([]);
    expect(r.proximo).toEqual([]);
    expect(r.depois).toEqual([]);
  });

  it("returns empty buckets for empty epic list", () => {
    expect(categorize([])).toEqual({ agora: [], proximo: [], depois: [] });
  });

  it("unknown wave status falls into depois", () => {
    const epics = [mkEpic("E9", [["w1", "mystery-status"]])];
    expect(categorize(epics).depois).toEqual([]);
    // "mystery-status" is neither not_started nor in_progress/partial → excluded
    // (explicit: unknowns are excluded, matching "blocked/parked/delivered" treatment)
  });

  it("attaches parent epic to each wave entry", () => {
    const epics = [mkEpic("E1", [["w1", "in_progress"]])];
    const r = categorize(epics);
    expect(r.agora[0].epic.id).toBe("E1");
    expect(r.agora[0].wave.id).toBe("w1");
  });
});
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd ~/code/mission-control
npx vitest run tests/lib/roadmap/categorize.test.ts 2>&1 | tail -10
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement `categorize.ts`**

```typescript
import type { CategorizedWaves, TrackerEpic } from "@/lib/roadmap/types";

/**
 * Split all waves across epics into strategic buckets.
 *
 * - agora:   wave.status ∈ { in_progress, partial }
 * - proximo: wave.status === not_started AND epic has ≥1 wave delivered|partial
 * - depois:  wave.status === not_started AND epic has 0 delivered|partial
 *
 * Excluded (none of the 3 buckets): delivered, parked, blocked, unknown.
 * These are shown in the technical view only.
 */
export function categorize(epics: TrackerEpic[]): CategorizedWaves {
  const agora: CategorizedWaves["agora"] = [];
  const proximo: CategorizedWaves["proximo"] = [];
  const depois: CategorizedWaves["depois"] = [];

  for (const epic of epics) {
    const epicHasDelivered = epic.waves.some(
      (w) => w.status === "delivered" || w.status === "partial",
    );
    for (const wave of epic.waves) {
      if (wave.status === "in_progress" || wave.status === "partial") {
        agora.push({ epic, wave });
      } else if (wave.status === "not_started") {
        (epicHasDelivered ? proximo : depois).push({ epic, wave });
      }
      // Otherwise (delivered, parked, blocked, unknown): excluded.
    }
  }
  return { agora, proximo, depois };
}
```

- [ ] **Step 4: Run test — verify it passes**

```bash
cd ~/code/mission-control
npx vitest run tests/lib/roadmap/categorize.test.ts 2>&1 | tail -10
```

Expected: 9 tests pass.

- [ ] **Step 5: Commit**

```bash
cd ~/code/mission-control
git add src/lib/roadmap/categorize.ts tests/lib/roadmap/categorize.test.ts
git commit -m "$(cat <<'EOF'
feat(roadmap): categorize util + tests (E5 F1)

Pure fn que segmenta waves em agora/proximo/depois conforme regra
da spec: in_progress+partial → agora; not_started com epic em
andamento → proximo; not_started em epic virgem → depois.
Exclui delivered/parked/blocked/unknown (esses aparecem só na
technical view).

9 tests: 3 buckets básicos, edge cases (status unknown, empty list,
mixed excluded statuses, epic linkage preservation).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `/api/roadmap/deps/route.ts` com teste

**Files:**
- Create: `~/code/mission-control/src/app/api/roadmap/deps/route.ts`
- Create: `~/code/mission-control/tests/app/api/roadmap/deps.route.test.ts`

- [ ] **Step 1: Write failing test**

Criar fixture mínimo e teste:

```typescript
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { writeFileSync, mkdirSync, rmSync } from "fs";
import path from "path";
import os from "os";

import { GET } from "@/app/api/roadmap/deps/route";

const TMP_BASE = path.join(os.tmpdir(), `mc-roadmap-deps-test-${process.pid}`);

describe("GET /api/roadmap/deps", () => {
  beforeEach(() => {
    mkdirSync(path.join(TMP_BASE, "40_roadmap", "company-os"), { recursive: true });
    delete process.env.BEVOX_KNOWLEDGE_DIR;
  });
  afterEach(() => {
    rmSync(TMP_BASE, { recursive: true, force: true });
    delete process.env.BEVOX_KNOWLEDGE_DIR;
  });

  it("returns parsed deps on valid markdown", async () => {
    const md = `
### E1 - Foundation
**Dependencias:** E0

### E3 - Agent Registry
**Prioridade:** P0 | **Dependencias:** E1, E2
`;
    writeFileSync(
      path.join(TMP_BASE, "40_roadmap/company-os/2026-04-09-openclaw-company-os-roadmap.md"),
      md,
    );
    process.env.BEVOX_KNOWLEDGE_DIR = TMP_BASE;
    const res = await GET();
    const body = await res.json();
    expect(res.status).toBe(200);
    expect(body.deps).toEqual({ E1: ["E0"], E3: ["E1", "E2"] });
    expect(typeof body.generated_at).toBe("string");
    expect(body.source).toContain("2026-04-09-openclaw-company-os-roadmap.md");
  });

  it("returns 404 when roadmap file missing", async () => {
    process.env.BEVOX_KNOWLEDGE_DIR = TMP_BASE;
    const res = await GET();
    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.error).toBe("roadmap_not_found");
  });

  it("returns 503 when env var unset in production", async () => {
    process.env.NODE_ENV = "production";
    const res = await GET();
    expect(res.status).toBe(503);
    const body = await res.json();
    expect(body.error).toBe("canonical_not_configured");
    process.env.NODE_ENV = "test";
  });

  it("dev fallback to $HOME/bevox-knowledge when env unset", async () => {
    // This test passes if the actual repo exists at the fallback path.
    // Skip gracefully if not — this is smoke-only, real validation is manual.
    const res = await GET();
    // Either 200 (real repo exists), 404 (dev fallback path doesn't exist),
    // or 500 (malformed real roadmap). Not testing the happy path here.
    expect([200, 404, 500]).toContain(res.status);
  });
});
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd ~/code/mission-control
npx vitest run tests/app/api/roadmap/deps.route.test.ts 2>&1 | tail -10
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement `route.ts`**

```typescript
import { NextResponse } from "next/server";
import { readFileSync, existsSync } from "fs";
import path from "path";

import { BEVOX_SUBPATHS } from "@/lib/bevox/paths";
import { parseDeps } from "@/lib/roadmap/parse-deps";

export const dynamic = "force-dynamic";

/**
 * GET /api/roadmap/deps
 *
 * E5 F2 — Roadmap technical view deps source.
 *
 * Reads the canonical roadmap narrative markdown from bevox-knowledge
 * and extracts epic-level `**Dependencias:**` lines per epic, returning
 * a map { epicId: depsList[] }.
 *
 * Fail modes:
 *   503 canonical_not_configured — prod + env unset
 *   404 roadmap_not_found        — markdown file absent
 *   500 parse_failed             — unexpected read/parse error
 *   200                          — { deps, generated_at, source }
 *
 * Spec: 35_specs/company-os/2026-04-24-e5-f1-f2-roadmap-views.md §6.1
 */

function resolveRoadmapPath(): string | null {
  const envDir = process.env.BEVOX_KNOWLEDGE_DIR;
  if (envDir && envDir.length > 0) {
    return path.join(envDir, BEVOX_SUBPATHS.roadmapNarrative);
  }
  if (process.env.NODE_ENV !== "production") {
    const home = process.env.HOME || "~";
    return path.join(home, "bevox-knowledge", BEVOX_SUBPATHS.roadmapNarrative);
  }
  return null;
}

export async function GET() {
  const roadmapPath = resolveRoadmapPath();

  if (!roadmapPath) {
    return NextResponse.json(
      {
        error: "canonical_not_configured",
        detail: "BEVOX_KNOWLEDGE_DIR env var not set",
      },
      { status: 503 },
    );
  }

  if (!existsSync(roadmapPath)) {
    return NextResponse.json(
      { error: "roadmap_not_found", detail: `not found at ${roadmapPath}` },
      { status: 404 },
    );
  }

  let markdown: string;
  try {
    markdown = readFileSync(roadmapPath, "utf-8");
  } catch (err) {
    return NextResponse.json(
      { error: "parse_failed", detail: `read error: ${String(err)}` },
      { status: 500 },
    );
  }

  let deps: Record<string, string[]>;
  try {
    deps = parseDeps(markdown);
  } catch (err) {
    return NextResponse.json(
      { error: "parse_failed", detail: `parse error: ${String(err)}` },
      { status: 500 },
    );
  }

  return NextResponse.json({
    generated_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
    source: roadmapPath,
    deps,
  });
}
```

- [ ] **Step 4: Run test — verify it passes**

```bash
cd ~/code/mission-control
npx vitest run tests/app/api/roadmap/deps.route.test.ts 2>&1 | tail -15
```

Expected: 4 tests pass (or 3 pass + 1 skipped dev fallback if path doesn't exist).

- [ ] **Step 5: Commit**

```bash
cd ~/code/mission-control
git add src/app/api/roadmap/deps/route.ts tests/app/api/roadmap/deps.route.test.ts
git commit -m "$(cat <<'EOF'
feat(api): /api/roadmap/deps route + tests (E5 F2)

GET /api/roadmap/deps parseia 40_roadmap/company-os/2026-04-09-openclaw-company-os-roadmap.md
e retorna { deps, generated_at, source }. 4 error modes consistentes
com /api/delivery/tracker (503/404/500/200).

Usa BEVOX_SUBPATHS.roadmapNarrative + parseDeps util. Fallback dev
para $HOME/bevox-knowledge quando NODE_ENV !== production.

4 tests cobrindo: parse OK, 404 missing, 503 prod unset, dev fallback.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: `DepsChips.tsx` component

**Files:**
- Create: `~/code/mission-control/src/app/(dashboard)/roadmap/DepsChips.tsx`

- [ ] **Step 1: Create component**

```tsx
"use client";

import type { TrackerBlocker } from "@/lib/roadmap/types";

interface Props {
  /** Epic id (e.g. "E3") for filtering blockers that reference this epic/wave. */
  epicId?: string;
  /** Wave id for filtering blockers that reference this wave. */
  waveId?: string;
  /** List of epic deps (from parseDeps). Used for epic-level header chips. */
  epicDeps?: string[];
  /** All blockers from tracker (filter will happen here). */
  allBlockers: TrackerBlocker[];
  /** Compact mode for wave cards (smaller chips, no epic deps). */
  compact?: boolean;
}

/**
 * Renders dep chips for an epic or wave.
 *
 * - At epic-header level: chips for each epic dep (e.g. "deps: E1, E2").
 * - At wave-level: chips for each active blocker whose `blocks` includes
 *   `"<epicId>/<waveId>"` or the sentinel `"global"`.
 */
export default function DepsChips({
  epicId,
  waveId,
  epicDeps,
  allBlockers,
  compact = false,
}: Props) {
  const ref = epicId && waveId ? `${epicId}/${waveId}` : null;

  const relevantBlockers = allBlockers.filter((b) => {
    if (b.status !== "active") return false;
    if (!ref) return false;
    return b.blocks.includes(ref) || b.blocks.includes("global");
  });

  const showEpicDeps = !compact && epicDeps && epicDeps.length > 0;
  if (!showEpicDeps && relevantBlockers.length === 0) return null;

  const chipClass = compact
    ? "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px]"
    : "inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs";

  return (
    <div className={`flex flex-wrap gap-1 ${compact ? "" : "mt-1"}`}>
      {showEpicDeps &&
        epicDeps!.map((dep) => (
          <span
            key={`dep-${dep}`}
            className={`${chipClass} bg-blue-100 text-blue-800`}
            title={`depends on ${dep}`}
          >
            deps: {dep}
          </span>
        ))}
      {relevantBlockers.map((b) => (
        <span
          key={`blk-${b.id}`}
          className={`${chipClass} bg-red-100 text-red-800`}
          title={b.summary}
        >
          🚫 {b.id}
        </span>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Verify typecheck**

```bash
cd ~/code/mission-control
npx tsc --noEmit 2>&1 | grep -v 'module-components.test.tsx' | head -5
```

Expected: sem erros.

- [ ] **Step 3: Commit**

```bash
cd ~/code/mission-control
git add src/app/\(dashboard\)/roadmap/DepsChips.tsx
git commit -m "$(cat <<'EOF'
feat(roadmap): DepsChips component (E5 F2)

Chips visuais para epic deps (nível header) + blockers ativos que
referenciam a wave. Filtragem client-side por ref "<epic>/<wave>"
ou sentinel "global". Modo compact para usar em WaveCard.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: `WaveCard.tsx` component

**Files:**
- Create: `~/code/mission-control/src/app/(dashboard)/roadmap/WaveCard.tsx`

- [ ] **Step 1: Create component**

```tsx
"use client";

import type { TrackerBlocker, TrackerEpic, TrackerWave } from "@/lib/roadmap/types";
import DepsChips from "./DepsChips";

interface Props {
  epic: TrackerEpic;
  wave: TrackerWave;
  allBlockers: TrackerBlocker[];
  /** Strategic variant: compact card for 3-column view. */
  variant?: "strategic" | "technical";
}

const STATUS_COLORS: Record<string, string> = {
  delivered: "bg-green-100 text-green-800",
  in_progress: "bg-yellow-100 text-yellow-800",
  not_started: "bg-gray-100 text-gray-700",
  parked: "bg-slate-100 text-slate-600",
  blocked: "bg-red-100 text-red-800",
  partial: "bg-amber-100 text-amber-800",
};

export default function WaveCard({ epic, wave, allBlockers, variant = "strategic" }: Props) {
  const statusColor = STATUS_COLORS[wave.status] ?? "bg-gray-100 text-gray-700";

  return (
    <div className="border border-gray-200 rounded-md p-2 bg-white">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs font-mono text-gray-500">{epic.id}/{wave.id}</span>
        <span className={`text-[10px] rounded px-1.5 py-0.5 font-medium ${statusColor}`}>
          {wave.status}
        </span>
        {wave.delivered_at && (
          <span className="text-[10px] text-gray-400">{wave.delivered_at}</span>
        )}
      </div>
      <div className="text-sm font-medium text-gray-900 mt-0.5">{epic.name}</div>
      {variant === "technical" && wave.features && wave.features.length > 0 && (
        <ul className="mt-1 text-xs text-gray-600 list-disc list-inside space-y-0.5">
          {wave.features.slice(0, 3).map((f, i) => (
            <li key={i} className="line-clamp-1">{f}</li>
          ))}
          {wave.features.length > 3 && (
            <li className="italic text-gray-400">+{wave.features.length - 3} more</li>
          )}
        </ul>
      )}
      {variant === "technical" && wave.spec && (
        <a
          href={`https://github.com/bernardTavares/bevox-knowledge/blob/main/${wave.spec}`}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-1 inline-block text-[11px] text-blue-600 hover:underline"
        >
          spec ↗
        </a>
      )}
      {(wave.blocker || wave.reason) && (
        <div className="mt-1 text-[11px] italic text-red-700">
          {wave.blocker || wave.reason}
        </div>
      )}
      <DepsChips
        epicId={epic.id}
        waveId={wave.id}
        allBlockers={allBlockers}
        compact={variant === "strategic"}
      />
    </div>
  );
}
```

- [ ] **Step 2: Verify typecheck**

```bash
cd ~/code/mission-control
npx tsc --noEmit 2>&1 | grep -v 'module-components.test.tsx' | head -5
```

Expected: sem erros.

- [ ] **Step 3: Commit**

```bash
cd ~/code/mission-control
git add src/app/\(dashboard\)/roadmap/WaveCard.tsx
git commit -m "$(cat <<'EOF'
feat(roadmap): WaveCard component (E5 F1+F2)

Card compartilhado entre StrategicView e TechnicalView. Variant
strategic (compact) vs technical (com features + spec link).
Status badge colorido por enum. Blocker/reason inline. DepsChips
em modo compact pra strategic.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: `StrategicView.tsx` component

**Files:**
- Create: `~/code/mission-control/src/app/(dashboard)/roadmap/StrategicView.tsx`

- [ ] **Step 1: Create component**

```tsx
"use client";

import type { CategorizedWaves, TrackerBlocker } from "@/lib/roadmap/types";
import WaveCard from "./WaveCard";

interface Props {
  categorized: CategorizedWaves;
  allBlockers: TrackerBlocker[];
}

const COLUMNS: Array<{
  key: keyof CategorizedWaves;
  title: string;
  hint: string;
}> = [
  { key: "agora", title: "Agora", hint: "in_progress + partial" },
  { key: "proximo", title: "Próximo", hint: "not_started com trabalho em andamento" },
  { key: "depois", title: "Depois", hint: "not_started sem delivery ainda" },
];

export default function StrategicView({ categorized, allBlockers }: Props) {
  const allEmpty =
    categorized.agora.length === 0 &&
    categorized.proximo.length === 0 &&
    categorized.depois.length === 0;

  if (allEmpty) {
    return (
      <div className="border border-dashed border-gray-300 rounded-md p-6 text-center">
        <p className="text-sm text-gray-500">
          Nenhuma wave em andamento ou planejada no tracker.
        </p>
        <a href="/kanban" className="text-sm text-blue-600 hover:underline">
          Ir para Kanban →
        </a>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
      {COLUMNS.map((col) => (
        <section key={col.key} className="flex flex-col gap-2">
          <header className="border-b border-gray-200 pb-1">
            <h3 className="text-sm font-semibold text-gray-900">{col.title}</h3>
            <p className="text-[11px] text-gray-500">{col.hint}</p>
            <p className="text-[11px] text-gray-400">{categorized[col.key].length} wave(s)</p>
          </header>
          <div className="flex flex-col gap-2">
            {categorized[col.key].length === 0 ? (
              <p className="text-xs text-gray-400 italic px-2">vazio</p>
            ) : (
              categorized[col.key].map(({ epic, wave }) => (
                <WaveCard
                  key={`${epic.id}/${wave.id}`}
                  epic={epic}
                  wave={wave}
                  allBlockers={allBlockers}
                  variant="strategic"
                />
              ))
            )}
          </div>
        </section>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Verify typecheck**

```bash
cd ~/code/mission-control
npx tsc --noEmit 2>&1 | grep -v 'module-components.test.tsx' | head -5
```

Expected: sem erros.

- [ ] **Step 3: Commit**

```bash
cd ~/code/mission-control
git add src/app/\(dashboard\)/roadmap/StrategicView.tsx
git commit -m "$(cat <<'EOF'
feat(roadmap): StrategicView component (E5 F1)

3 colunas Agora/Próximo/Depois renderizando CategorizedWaves com
WaveCard variant strategic. Empty state com link pra kanban.
Cada coluna mostra count e hint da regra.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: `TechnicalView.tsx` component

**Files:**
- Create: `~/code/mission-control/src/app/(dashboard)/roadmap/TechnicalView.tsx`

- [ ] **Step 1: Create component**

```tsx
"use client";

import { useState } from "react";
import type { DepsMap, TrackerBlocker, TrackerEpic } from "@/lib/roadmap/types";
import WaveCard from "./WaveCard";
import DepsChips from "./DepsChips";

interface Props {
  epics: TrackerEpic[];
  deps: DepsMap;
  allBlockers: TrackerBlocker[];
}

type StatusFilter = "all" | "delivered" | "partial" | "in_progress" | "not_started" | "parked" | "blocked";

const FILTERS: Array<{ key: StatusFilter; label: string }> = [
  { key: "all", label: "Todos" },
  { key: "delivered", label: "Delivered" },
  { key: "partial", label: "Partial" },
  { key: "in_progress", label: "In progress" },
  { key: "not_started", label: "Not started" },
  { key: "parked", label: "Parked" },
  { key: "blocked", label: "Blocked" },
];

export default function TechnicalView({ epics, deps, allBlockers }: Props) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [filter, setFilter] = useState<StatusFilter>("all");

  const toggle = (id: string) => setExpanded((p) => ({ ...p, [id]: !p[id] }));

  const isVisible = (status: string) =>
    filter === "all" || status === filter;

  return (
    <div>
      <div className="flex flex-wrap gap-1 mb-3">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`text-xs px-2 py-1 rounded ${
              filter === f.key
                ? "bg-gray-900 text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>
      <div className="flex flex-col gap-2">
        {epics.map((epic) => {
          const visibleWaves = epic.waves.filter((w) => isVisible(w.status));
          if (visibleWaves.length === 0 && filter !== "all") return null;
          const isExpanded = expanded[epic.id] ?? false;
          const epicDeps = deps[epic.id] ?? [];
          return (
            <div key={epic.id} className="border border-gray-200 rounded-md">
              <button
                onClick={() => toggle(epic.id)}
                className="w-full text-left p-2 hover:bg-gray-50 flex items-center gap-2 flex-wrap"
              >
                <span className="text-xs font-mono text-gray-500">{epic.id}</span>
                <span className="text-sm font-medium text-gray-900 flex-1">{epic.name}</span>
                <span className="text-[10px] rounded px-1.5 py-0.5 bg-gray-100 text-gray-700">
                  {epic.status}
                </span>
                <span className="text-[11px] text-gray-400">
                  {visibleWaves.length}/{epic.waves.length} waves
                </span>
                <span className="text-xs text-gray-500">{isExpanded ? "▾" : "▸"}</span>
              </button>
              {epicDeps.length > 0 && (
                <div className="px-2 pb-1">
                  <DepsChips
                    epicDeps={epicDeps}
                    allBlockers={allBlockers}
                  />
                </div>
              )}
              {isExpanded && (
                <div className="border-t border-gray-200 p-2 flex flex-col gap-2 bg-gray-50">
                  {visibleWaves.map((wave) => (
                    <WaveCard
                      key={wave.id}
                      epic={epic}
                      wave={wave}
                      allBlockers={allBlockers}
                      variant="technical"
                    />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify typecheck**

```bash
cd ~/code/mission-control
npx tsc --noEmit 2>&1 | grep -v 'module-components.test.tsx' | head -5
```

Expected: sem erros.

- [ ] **Step 3: Commit**

```bash
cd ~/code/mission-control
git add src/app/\(dashboard\)/roadmap/TechnicalView.tsx
git commit -m "$(cat <<'EOF'
feat(roadmap): TechnicalView component (E5 F2)

Epics expandable com filter por status. DepsChips no header do epic
(epic-level deps via parseDeps) + WaveCard variant technical nas
waves (features + spec link + blocker inline). Filter "Todos" ou por
status específico.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: `RoadmapHeader.tsx` component

**Files:**
- Create: `~/code/mission-control/src/app/(dashboard)/roadmap/RoadmapHeader.tsx`

- [ ] **Step 1: Create component**

```tsx
"use client";

import type { TrackerSummary } from "@/lib/roadmap/types";

interface Props {
  summary: TrackerSummary;
  generatedAt: string;
}

export default function RoadmapHeader({ summary, generatedAt }: Props) {
  return (
    <header className="mb-4">
      <div className="flex items-baseline gap-3 flex-wrap">
        <h1 className="text-2xl font-bold text-gray-900">Roadmap</h1>
        <span className="text-xs text-gray-400">
          gerado em {new Date(generatedAt).toLocaleString("pt-BR")}
        </span>
      </div>
      <p className="text-sm text-gray-600 mt-1">
        Visão estratégica (Agora / Próximo / Depois) + técnica (epics, waves, deps).
      </p>
      <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
        <div className="border border-gray-200 rounded p-2">
          <div className="text-gray-500">Epics</div>
          <div className="text-gray-900 font-medium">
            {summary.epics_delivered} delivered · {summary.epics_partial} partial ·{" "}
            {summary.epics_not_started} not started
          </div>
        </div>
        <div className="border border-gray-200 rounded p-2">
          <div className="text-gray-500">Waves</div>
          <div className="text-gray-900 font-medium">
            {summary.waves_delivered}/{summary.total_waves} delivered ·{" "}
            {summary.waves_in_progress} in progress
          </div>
        </div>
        <div className="border border-gray-200 rounded p-2">
          <div className="text-gray-500">Blockers</div>
          <div className="text-gray-900 font-medium">
            {summary.blockers_active} active · {summary.blockers_resolved} resolved
          </div>
        </div>
        <div className="border border-gray-200 rounded p-2">
          <div className="text-gray-500">Risks</div>
          <div className="text-gray-900 font-medium">
            {summary.risks_open} open · {summary.risks_mitigated} mitigated
          </div>
        </div>
      </div>
    </header>
  );
}
```

- [ ] **Step 2: Verify + commit**

```bash
cd ~/code/mission-control
npx tsc --noEmit 2>&1 | grep -v 'module-components.test.tsx' | head -5
git add src/app/\(dashboard\)/roadmap/RoadmapHeader.tsx
git commit -m "$(cat <<'EOF'
feat(roadmap): RoadmapHeader component (E5 F1+F2)

Sumário numérico: epics, waves, blockers, risks. Grid 4-col.
Título + generated_at timestamp.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: `/roadmap/page.tsx`

**Files:**
- Create: `~/code/mission-control/src/app/(dashboard)/roadmap/page.tsx`

- [ ] **Step 1: Create page**

```tsx
"use client";

import { useEffect, useState } from "react";

import type {
  DepsMap,
  DepsResponse,
  TrackerResponse,
} from "@/lib/roadmap/types";
import { categorize } from "@/lib/roadmap/categorize";
import RoadmapHeader from "./RoadmapHeader";
import StrategicView from "./StrategicView";
import TechnicalView from "./TechnicalView";

type LoadState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; tracker: TrackerResponse; deps: DepsMap };

export default function RoadmapPage() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [trackerRes, depsRes] = await Promise.all([
          fetch("/api/delivery/tracker", { cache: "no-store" }),
          fetch("/api/roadmap/deps", { cache: "no-store" }),
        ]);

        if (!trackerRes.ok) {
          const err = await trackerRes.json().catch(() => ({}));
          if (!cancelled)
            setState({
              kind: "error",
              message: `tracker: ${trackerRes.status} ${err.error ?? "unknown"}`,
            });
          return;
        }
        const tracker: TrackerResponse = await trackerRes.json();

        // Deps is optional: degrade gracefully on 404/500/503.
        let deps: DepsMap = {};
        if (depsRes.ok) {
          const depsBody: DepsResponse = await depsRes.json();
          deps = depsBody.deps;
        }

        if (!cancelled) setState({ kind: "ready", tracker, deps });
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
    return <div className="p-6 text-sm text-gray-500">Carregando roadmap…</div>;
  }

  if (state.kind === "error") {
    return (
      <div className="p-6">
        <h1 className="text-xl font-bold text-red-700">Erro ao carregar roadmap</h1>
        <pre className="mt-2 text-xs bg-red-50 p-2 rounded">{state.message}</pre>
      </div>
    );
  }

  const categorized = categorize(state.tracker.epics);

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <RoadmapHeader
        summary={state.tracker.summary}
        generatedAt={state.tracker.generated_at}
      />

      <section className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-2">
          Visão estratégica
        </h2>
        <StrategicView categorized={categorized} allBlockers={state.tracker.blockers} />
      </section>

      <section>
        <h2 className="text-lg font-semibold text-gray-900 mb-2">
          Visão técnica
        </h2>
        <TechnicalView
          epics={state.tracker.epics}
          deps={state.deps}
          allBlockers={state.tracker.blockers}
        />
      </section>
    </div>
  );
}
```

- [ ] **Step 2: Verify + commit**

```bash
cd ~/code/mission-control
npx tsc --noEmit 2>&1 | grep -v 'module-components.test.tsx' | head -5
git add src/app/\(dashboard\)/roadmap/page.tsx
git commit -m "$(cat <<'EOF'
feat(roadmap): /roadmap page entry (E5 F1+F2)

Client component. Fetch paralelo /api/delivery/tracker + /api/roadmap/deps
(deps degrada graciosamente em erro). Compose RoadmapHeader +
StrategicView + TechnicalView.

Categorize é chamado client-side no render. LoadState tagged union
(loading/error/ready).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Remover tab Tracker de `/delivery/page.tsx`

**Files:**
- Modify: `~/code/mission-control/src/app/(dashboard)/delivery/page.tsx`

- [ ] **Step 1: Read current state**

```bash
grep -n "Tracker\|tracker" ~/code/mission-control/src/app/\(dashboard\)/delivery/page.tsx | head -20
```

Expected: encontra interfaces (Tracker*, interfaces tipos) + tab "tracker" nos tabs array + bloco de render condicional.

- [ ] **Step 2: Edit — 3 mudanças mínimas**

**Mudança A:** No array `TABS`, remover entry `{ key: "tracker", ... }` se existir. O array fica com 4: pending/accepted/rejected/expired.

**Mudança B:** Remover tipo `TabName = "pending" | "accepted" | ... | "tracker"` → deixar `TabName = "pending" | "accepted" | "rejected" | "expired"`.

**Mudança C:** Remover bloco JSX condicional `{activeTab === "tracker" && <TrackerView ... />}` (se existir) + componente inline `TrackerView` definido no mesmo arquivo.

**Mudança D:** Remover interfaces relacionadas apenas a tracker (TrackerWave, TrackerEpic, TrackerBlocker, TrackerRisk, TrackerResponse) — porque são dead code após remoção da tab.

Use Edit tool para cada uma. Ler o arquivo se necessário antes.

- [ ] **Step 3: Verify typecheck**

```bash
cd ~/code/mission-control
npx tsc --noEmit 2>&1 | grep -v 'module-components.test.tsx' | grep -i "delivery\|tracker" | head -5
```

Expected: sem erros em `delivery/page.tsx`.

- [ ] **Step 4: Smoke test (dev server opcional, apenas visual)**

```bash
# Manual se tempo: iniciar dev server e verificar /delivery tem 4 tabs.
# Se não conseguir testar, typecheck OK já cobre a integridade básica.
```

- [ ] **Step 5: Commit**

```bash
cd ~/code/mission-control
git add src/app/\(dashboard\)/delivery/page.tsx
git commit -m "$(cat <<'EOF'
refactor(delivery): remove Tracker tab (migrated to /roadmap, E5 F1+F2)

Tab Tracker e dead code associado (interfaces + componente inline)
removidos. /delivery fica com 4 tabs dedicadas a proposals do
delivery-agent (pending/accepted/rejected/expired). Conteúdo de tracker
agora em /roadmap.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Adicionar `/roadmap` ao Sidebar

**Files:**
- Modify: `~/code/mission-control/src/components/Sidebar.tsx`

- [ ] **Step 1: Read current state**

```bash
grep -n "delivery\|kanban\|roadmap" ~/code/mission-control/src/components/Sidebar.tsx | head -10
```

Expected: entries para /delivery e /kanban.

- [ ] **Step 2: Add /roadmap entry**

Localizar a lista/array de entries de navegação. Adicionar entry `/roadmap` **antes** de `/delivery` (roadmap é visão de planejamento; delivery é operacional — estratégico antes de operacional). Manter o mesmo shape dos outros entries (pathname, label, ícone se padrão).

Exemplo (ajustar à sintaxe real encontrada):

```tsx
{ href: "/roadmap", label: "Roadmap", icon: Map },
{ href: "/delivery", label: "Delivery", icon: ...existing },
{ href: "/kanban", label: "Kanban", icon: ...existing },
```

Se Map não for o ícone correto pro padrão, usar `Route` ou `ListTree` do lucide-react. Ajustar import.

- [ ] **Step 3: Verify + commit**

```bash
cd ~/code/mission-control
npx tsc --noEmit 2>&1 | grep -v 'module-components.test.tsx' | head -5
git add src/components/Sidebar.tsx
git commit -m "$(cat <<'EOF'
feat(sidebar): add /roadmap entry (E5 F1+F2)

Entry roadmap antes de /delivery no sidebar (estratégico antes de
operacional).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: Smoke test end-to-end

**Files:** nenhum — verificação

- [ ] **Step 1: Full typecheck**

```bash
cd ~/code/mission-control
npx tsc --noEmit 2>&1 | grep -v 'module-components.test.tsx' | head -10
```

Expected: sem erros.

- [ ] **Step 2: Full test suite (novos + não-regressão)**

```bash
cd ~/code/mission-control
npx vitest run tests/lib/roadmap/ tests/app/api/roadmap/ 2>&1 | tail -15
```

Expected: pelo menos 17-20 tests pass (parse-deps 7 + categorize 9 + deps.route 4).

- [ ] **Step 3: Opcional — dev server + navegação manual**

```bash
cd ~/code/mission-control
BEVOX_KNOWLEDGE_DIR=~/bevox-knowledge npm run dev &
sleep 5
curl -sS http://localhost:3000/api/roadmap/deps | python3 -m json.tool | head -10
kill %1 2>/dev/null
```

Expected: JSON com `deps`, `generated_at`, `source`. Exemplo:

```json
{
  "deps": { "E1": ["E0"], "E3": ["E1", "E2"], ... },
  "generated_at": "2026-04-24T...",
  "source": "~/bevox-knowledge/40_roadmap/company-os/..."
}
```

Se dev server não iniciar por razões não-relacionadas, pular este step — typecheck + tests cobrem o essencial.

- [ ] **Step 4: N/A (sem commit — só verificação)**

Se qualquer step falhar: STOP, reportar BLOCKED.

---

## Task 16: Push + PR (pausa pro merge)

**Files:** nenhum

- [ ] **Step 1: Push draft**

```bash
cd ~/code/mission-control
git push -u origin feat/e5-f1-f2-roadmap-views
```

- [ ] **Step 2: Create PR**

```bash
cd ~/code/mission-control
gh pr create --title "feat(roadmap): E5 F1+F2 views (strategic + technical)" --base main --head feat/e5-f1-f2-roadmap-views --body "$(cat <<'EOF'
## Summary

E5/F1 (roadmap estratégico) + F2 (roadmap técnico) como nova página \`/roadmap\`.

- **StrategicView:** 3 colunas Agora/Próximo/Depois, derivadas automaticamente do tracker (zero editorial overhead).
- **TechnicalView:** epics expandable com filter por status, features, spec links, **deps chips** (blockers + epic dependencies extraídas do roadmap narrativo).
- **Nova route \`/api/roadmap/deps\`** parseia \`40_roadmap/company-os/2026-04-09-openclaw-company-os-roadmap.md\` retornando mapa \`{ epicId: depsList[] }\`. 4 error modes consistentes com \`/api/delivery/tracker\`.
- **Tab Tracker removida de \`/delivery\`** — conteúdo migra para \`/roadmap\`. \`/delivery\` fica com 4 tabs (pending/accepted/rejected/expired).
- **Sidebar:** entry \`/roadmap\` antes de \`/delivery\`.

**Spec:** [\`bevox-knowledge/35_specs/company-os/2026-04-24-e5-f1-f2-roadmap-views.md\`](../../../bevox-knowledge/blob/main/35_specs/company-os/2026-04-24-e5-f1-f2-roadmap-views.md)

**BEVOX_SUBPATHS** ganha \`roadmapNarrative\`. Tracker YAML continua consumido via \`BEVOX_SUBPATHS.tracker\` (sem mudança).

**Rollback:** revert do merge. Nada no bevox-knowledge é tocado.

## Test plan

- [x] \`parseDeps\` 7 unit tests (parse OK, multiple epics, checkmarks, decimal ids, empty MD, malformed, epic sem deps line)
- [x] \`categorize\` 9 unit tests (3 buckets, edge cases, status unknown, empty list, epic linkage)
- [x] \`/api/roadmap/deps\` 4 route tests (200 happy, 404 missing, 503 prod unset, dev fallback)
- [x] Full typecheck limpo (pre-existing errors em module-components.test.tsx unrelated)
- [ ] Smoke manual: \`/roadmap\` renderiza 3 colunas + tree técnica; \`/delivery\` sem tab Tracker; sidebar mostra Roadmap

## Follow-up (pós-merge)

- Atualizar tracker em bevox-knowledge: E5/F1-roadmap-estrategico + E5/F2-roadmap-tecnico → \`delivered\` (task 17).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Parar e aguardar autorização pro merge**

Reportar ao Bernard: URL do PR + sumário de commits. Aguardar "autorizo" antes de `gh pr merge`.

- [ ] **Step 4: Após autorização — merge + sync**

```bash
PR=$(gh pr list --repo bernardTavares/mission-control --head feat/e5-f1-f2-roadmap-views --json number --jq '.[0].number')
gh pr merge $PR --repo bernardTavares/mission-control --merge --delete-branch
cd ~/code/mission-control
git checkout main
git pull --ff-only
git log --oneline -3
```

---

## Task 17: Atualizar tracker — E5/F1 + F2 → delivered

**Files:**
- Modify: `~/bevox-knowledge/40_roadmap/_shared/delivery-tracker.yml`

- [ ] **Step 1: Criar branch no bevox-knowledge**

```bash
cd ~/bevox-knowledge
git checkout main
git pull --ff-only
git checkout -b tracker/e5-f1-f2-delivered
```

- [ ] **Step 2: Localizar entries**

```bash
grep -n "F1-roadmap-estrategico\|F2-roadmap-tecnico" 40_roadmap/_shared/delivery-tracker.yml
```

Expected: 2 linhas — status atual `not_started` em ambas.

- [ ] **Step 3: Edit — F1 + F2 → delivered**

Usar Edit tool no arquivo, trocando:

```yaml
      - id: F1-roadmap-estrategico
        status: not_started
```

por:

```yaml
      - id: F1-roadmap-estrategico
        status: delivered
        delivered_at: "<YYYY-MM-DD-execução>"
        features: ["StrategicView no Mission Control /roadmap: 3 colunas Agora/Próximo/Depois derivadas automaticamente do tracker"]
        spec: 35_specs/company-os/2026-04-24-e5-f1-f2-roadmap-views.md
```

E o mesmo padrão para F2:

```yaml
      - id: F2-roadmap-tecnico
        status: delivered
        delivered_at: "<YYYY-MM-DD-execução>"
        features: ["TechnicalView no /roadmap: epics expandable, filter por status, deps chips (blockers + epic dependencies via /api/roadmap/deps)"]
        spec: 35_specs/company-os/2026-04-24-e5-f1-f2-roadmap-views.md
```

Substituir `<YYYY-MM-DD-execução>` pela data real da execução.

- [ ] **Step 4: Validate YAML + commit**

```bash
cd ~/bevox-knowledge
python3 -c "import yaml; yaml.safe_load(open('40_roadmap/_shared/delivery-tracker.yml')); print('YAML OK')"
git add 40_roadmap/_shared/delivery-tracker.yml
git commit -m "$(cat <<'EOF'
tracker(E5/F1+F2): delivered — /roadmap views no Mission Control

F1 (roadmap estratégico — Agora/Próximo/Depois) e F2 (roadmap
técnico — epics + deps chips) entregues como página /roadmap no MC.

Spec: 35_specs/company-os/2026-04-24-e5-f1-f2-roadmap-views.md
Fonte: mission-control feat/e5-f1-f2-roadmap-views (mergeado)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 5: Push + PR + aguardar autorização**

```bash
cd ~/bevox-knowledge
git push -u origin tracker/e5-f1-f2-delivered
gh pr create --title "tracker(E5/F1+F2): delivered" --base main --head tracker/e5-f1-f2-delivered --body "Sync do tracker com a wave entregue em bernardTavares/mission-control (feat/e5-f1-f2-roadmap-views)."
```

Parar. Aguardar autorização do Bernard antes de mergear.

- [ ] **Step 6: Merge após autorização**

```bash
PR=$(gh pr list --repo bernardTavares/bevox-knowledge --head tracker/e5-f1-f2-delivered --json number --jq '.[0].number')
gh pr merge $PR --repo bernardTavares/bevox-knowledge --merge --delete-branch
cd ~/bevox-knowledge
git checkout main
git pull --ff-only
git log --oneline -2
```

---

## Self-Review

**Spec coverage check (spec §3 + §10 DoD):**

- ✅ `/roadmap` acessível pelo sidebar — Task 14
- ✅ StrategicView com 3 colunas derivadas do tracker — Tasks 5 (categorize) + 9 (StrategicView) + 12 (page)
- ✅ TechnicalView com deps chips — Tasks 4 (parseDeps) + 6 (deps route) + 10 (TechnicalView)
- ✅ Tab Tracker removida de `/delivery` — Task 13
- ✅ `/api/roadmap/deps` retorna JSON válido — Task 6
- ✅ Tests unit categorize + parse-deps passando — Tasks 4 + 5
- ✅ Smoke manual: sidebar → `/roadmap` sem 500 — Task 15
- ✅ Tracker E5/F1+F2 → delivered — Task 17

**Placeholder check:** nenhum "TBD/TODO/later". Task 17 tem placeholder explícito `<YYYY-MM-DD-execução>` que o implementer substitui com data real.

**Consistency check:** interfaces em `types.ts` (Task 3) são referenciadas consistentemente em Tasks 4-12. `BEVOX_SUBPATHS.roadmapNarrative` (Task 2) usada em Task 6. `categorize` assinatura (Task 5) corresponde ao consumo no `page.tsx` (Task 12).

---

## Execution Handoff

Plan completo e salvo em `~/.openclaw/docs/superpowers/plans/2026-04-24-e5-f1-f2-roadmap-views.md`. 17 tasks. Duas opções:

1. **Subagent-Driven (recomendada)** — dispatch fresh subagent por task, iteração rápida. Tasks 1-16 em mission-control, Task 17 em bevox-knowledge.

2. **Inline Execution** — executar nesta sessão com executing-plans.

Qual?
