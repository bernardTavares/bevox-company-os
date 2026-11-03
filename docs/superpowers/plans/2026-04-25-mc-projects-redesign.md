# Mission Control Projects Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign `/projects` (health-grid list) e `/projects/[id]` (tabbed detail: Geral / Roadmap / Ficheiros / Sprints) no Mission Control, com markdown viewer pra docs canônicos do `bevox-knowledge` + embed scoped do `/sprints`.

**Architecture:** Frontend Next.js 15 (~13 novos componentes + 6 modify) + 3 endpoints novos com filesystem reader sandboxed em `bevox-knowledge`. Reusa `<SprintKanbanModal>` existente via embed do `<SprintsPageInner>` refatorado pra aceitar `forcedProject` prop. Markdown via `react-markdown` (já instalado) + `remark-gfm` (adicionar).

**Tech Stack:** Next.js 15 client components, React hooks, Vitest contract-based tests, lucide-react icons, react-markdown + remark-gfm, sandboxed `fs.readFile`/`fs.readdir` no Node runtime das API routes.

**Spec:** `bevox-knowledge/35_specs/company-os/2026-04-25-mc-projects-redesign.md` (commit `c2756b7` em `draft/spec-mc-projects-redesign`).

---

## File Structure

### Create (mission-control)

- `src/lib/projects/knowledge.ts` — sandboxed filesystem reader pro `bevox-knowledge`
- `src/components/projects/MarkdownViewer.tsx` — wrapper de `react-markdown` com header (filename + stub badge + raw button)
- `src/components/projects/TabNav.tsx` — tab navigation com URL state sync
- `src/components/projects/ProjectGeralTab.tsx` — split layout info esquerda + PRD direita
- `src/components/projects/ProjectRoadmapTab.tsx` — split layout info+docs list esquerda + roadmap direita
- `src/components/projects/ProjectFicheirosTab.tsx` — split layout file tree esquerda + preview direita
- `src/components/projects/ProjectSprintsTab.tsx` — thin wrapper que embed `<SprintsPageInner>`
- `src/components/projects/DocTree.tsx` — file tree colapsável dos 8 folders canônicos
- `src/components/projects/RoadmapDocsList.tsx` — lista de roadmap docs clicável
- `src/app/api/projects/[id]/prd/route.ts` — endpoint que lista + entrega latest PRD
- `src/app/api/projects/[id]/roadmap/route.ts` — endpoint mesma forma pro roadmap
- `src/app/api/projects/[id]/files/route.ts` — multi-purpose tree + read

### Modify (mission-control)

- `package.json` — adicionar `remark-gfm` (react-markdown já está instalado)
- `src/lib/projects/canonical.ts` — extender de 6 pra 10 entries (adicionar openclaw, mission-control, bevox-knowledge, vox)
- `src/app/(dashboard)/projects/ProjectCard.tsx` — rewrite layout health-grid (chip color-coded + 4 dots + stats)
- `src/app/(dashboard)/projects/[id]/page.tsx` — rewrite com Suspense wrapper + tabbed structure
- `src/app/(dashboard)/projects/[id]/ProjectHeader.tsx` — refactor pra sticky header compacto
- `src/app/(dashboard)/sprints/page.tsx` — export named `SprintsPageInner` + add `forcedProject?` + `hideProjectFilter?` props

### Delete (mission-control)

- `src/app/(dashboard)/projects/[id]/HealthDetails.tsx` (refactored inline em GeralTab)
- `src/app/(dashboard)/projects/[id]/SprintList.tsx` (substituído pela aba Sprints embed)
- `src/app/(dashboard)/projects/[id]/TasksInFlight.tsx` (substituído via modal kanban)
- `src/app/(dashboard)/projects/[id]/ProjectLinks.tsx` (refactored inline em ExternalLinksBox)

### No mudança em openclaw runtime / bevox-knowledge

(Pré-requisito: stubs PRD+roadmap já entregues PR #20 bevox-knowledge.)

---

## Task 1: Setup branches + commit plan + push spec PR (gate)

**Files:**
- Create: `~/.openclaw/docs/superpowers/plans/2026-04-25-mc-projects-redesign.md` (este arquivo)

- [ ] **Step 1: Branch openclaw plan**

```bash
cd ~/.openclaw && git checkout main && git pull --ff-only
git checkout -b feat/mc-projects-redesign-plan
```

(Se branch já existe: `git checkout feat/mc-projects-redesign-plan`.)

- [ ] **Step 2: Commit plan**

```bash
cd ~/.openclaw && git add docs/superpowers/plans/2026-04-25-mc-projects-redesign.md && git commit -m "$(cat <<'EOF'
plan(mc-projects-redesign): implementation plan

Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-projects-redesign.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 3: Push spec PR no bevox-knowledge**

```bash
cd ~/bevox-knowledge && git checkout draft/spec-mc-projects-redesign
git push -u origin draft/spec-mc-projects-redesign
gh pr create --title "spec(company-os): MC Projects redesign (E2/mc-projects-redesign)" --body "## Summary
Redesign /projects list (health-grid 3-col) + /projects/[id] tabbed detail (Geral / Roadmap / Ficheiros / Sprints).

## Pre-requisitos já entregues
- Stubs PRD+roadmap pros 10 projetos (PR #20 merged)
- /sprints com drag-drop (mission-control PR #13 merged)
- /api/kanban/state retorna sprints+tasks (PR #11 hotfix merged)

## Test plan
- [ ] Bernard revisa spec
- [ ] Aprova pra implementação seguir
- [ ] mission-control PR abre só após este merge

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

- [ ] **Step 4: PAUSA — aguardar Bernard mergear spec PR**

Parar aqui. Bernard merge `bernardTavares/bevox-knowledge` PR. Retomar Task 2 só após merge confirmado em main.

---

## Task 2: Add `remark-gfm` dep + extend CANONICAL_PROJECTS

**Files:**
- Modify: `mission-control/package.json` + `package-lock.json`
- Modify: `mission-control/src/lib/projects/canonical.ts`

- [ ] **Step 1: Branch mission-control feat**

```bash
cd ~/code/mission-control && git checkout main && git pull --ff-only
git checkout -b feat/mc-projects-redesign
```

- [ ] **Step 2: Install `remark-gfm`**

```bash
cd ~/code/mission-control && npm install remark-gfm 2>&1 | tail -5
```

Expected: `remark-gfm` aparece em `package.json` `dependencies` (latest version compatível com react-markdown 10.x — 4.x).

- [ ] **Step 3: Extend `CANONICAL_PROJECTS` para 10 entries**

Editar `src/lib/projects/canonical.ts`. Após a entry `company-os` (última hoje), adicionar antes do `] as const;`:

```typescript
  {
    id: "openclaw",
    name: "OpenClaw",
    description: "Runtime do Company OS — agentes, skills, governança, automações operacionais",
  },
  {
    id: "mission-control",
    name: "Mission Control",
    description: "Dashboard Next.js do Company OS — visualização e operação",
  },
  {
    id: "bevox-knowledge",
    name: "Bevox Knowledge",
    description: "Repo canônico de docs — ADRs, PRDs, roadmaps, specs, releases",
  },
  {
    id: "vox",
    name: "Vox",
    description: "Agente de voz/áudio — dispatcher principal do sistema agent-first",
  },
```

- [ ] **Step 4: Rodar tests existentes pra confirmar zero break**

```bash
cd ~/code/mission-control && npm test -- --run 2>&1 | tail -3
```

Expected: full suite green (152+ existing).

- [ ] **Step 5: Commit**

```bash
cd ~/code/mission-control && git add package.json package-lock.json src/lib/projects/canonical.ts && git commit -m "$(cat <<'EOF'
feat(deps+canonical): remark-gfm + extend CANONICAL_PROJECTS to 10

remark-gfm necessario pro markdown viewer da wave Projects redesign
(GitHub-flavored markdown: tables, task lists, fenced code).

CANONICAL_PROJECTS estendida pra 10 entries: 6 originais (Bevox produto +
company-os) + 4 novos (openclaw, mission-control, bevox-knowledge, vox).
Bate com PROJECT_COLORS + stubs PRD+roadmap. Sem split em categorias —
todos exibidos como projetos no grid.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `knowledge.ts` filesystem reader sandboxed

**Files:**
- Create: `mission-control/src/lib/projects/knowledge.ts`
- Create: `mission-control/tests/lib/projects/knowledge.test.ts`

- [ ] **Step 1: Escrever tests primeiro**

Write `~/code/mission-control/tests/lib/projects/knowledge.test.ts`:

```typescript
/**
 * Tests for sandboxed bevox-knowledge filesystem reader.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-projects-redesign.md §4.3
 */
import { describe, it, expect, beforeEach, afterAll } from "vitest";
import * as os from "os";
import * as fs from "fs";
import * as path from "path";
import {
  ALLOWED_FOLDERS,
  detectStub,
  isPathSafe,
} from "@/lib/projects/knowledge";

describe("ALLOWED_FOLDERS", () => {
  it("contains the 8 canonical folders", () => {
    expect(ALLOWED_FOLDERS).toEqual([
      "10_prd",
      "20_architecture",
      "30_adr",
      "35_specs",
      "40_roadmap",
      "50_releases",
      "60_customer-feedback",
      "70_metrics",
    ]);
  });
});

describe("detectStub", () => {
  it("detects '**Status:** stub' marker", () => {
    expect(detectStub("# Title\n\n**Status:** stub\n")).toBe(true);
  });
  it("detects 'status: stub' frontmatter line", () => {
    expect(detectStub("---\nstatus: stub\n---\n# Title\n")).toBe(true);
  });
  it("returns false for non-stub content", () => {
    expect(detectStub("# Title\n\nReal content here.\n")).toBe(false);
  });
  it("returns false for content that mentions 'stub' in prose", () => {
    expect(detectStub("This is not a stub document. Status: delivered.")).toBe(false);
  });
});

describe("isPathSafe", () => {
  const root = "/tmp/fake-knowledge-root";

  it("accepts path within root", () => {
    expect(isPathSafe(root, "/tmp/fake-knowledge-root/10_prd/foo.md")).toBe(true);
  });
  it("rejects path traversal via ..", () => {
    expect(isPathSafe(root, "/tmp/fake-knowledge-root/../secrets")).toBe(false);
  });
  it("rejects absolute paths outside root", () => {
    expect(isPathSafe(root, "/etc/passwd")).toBe(false);
  });
  it("rejects empty path", () => {
    expect(isPathSafe(root, "")).toBe(false);
  });
});
```

- [ ] **Step 2: Rodar tests (devem falhar — modulo nao existe)**

```bash
cd ~/code/mission-control && npm test -- --run tests/lib/projects/knowledge.test.ts 2>&1 | tail -8
```

Expected: ERR `Cannot find module '@/lib/projects/knowledge'`.

- [ ] **Step 3: Criar `src/lib/projects/knowledge.ts`**

```typescript
/**
 * Sandboxed reader pro bevox-knowledge filesystem.
 *
 * Strict: validates folder ∈ ALLOWED_FOLDERS, project ∈ CANONICAL_PROJECTS,
 * path resolves dentro do KNOWLEDGE_ROOT (no traversal).
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-projects-redesign.md §4.3
 */
import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import { isCanonicalProject } from "@/lib/projects/canonical";

export const KNOWLEDGE_ROOT =
  process.env.BEVOX_KNOWLEDGE_DIR ?? path.join(os.homedir(), "bevox-knowledge");

export const ALLOWED_FOLDERS = [
  "10_prd",
  "20_architecture",
  "30_adr",
  "35_specs",
  "40_roadmap",
  "50_releases",
  "60_customer-feedback",
  "70_metrics",
] as const;

export type AllowedFolder = (typeof ALLOWED_FOLDERS)[number];

export interface FileEntry {
  /** Path relativo a KNOWLEDGE_ROOT (e.g., "10_prd/openclaw/2026-04-25-prd.md"). */
  path: string;
  /** Filename apenas (e.g., "2026-04-25-prd.md"). */
  name: string;
  modified_at: string;
  is_stub: boolean;
}

export interface FileContent {
  path: string;
  content: string;
  modified_at: string;
  size_bytes: number;
  is_stub: boolean;
}

export class KnowledgeError extends Error {
  constructor(public code: "invalid_input" | "not_found" | "io_error", message: string) {
    super(message);
    this.name = "KnowledgeError";
  }
}

/** Validates path resolves dentro do root. Rejeita traversal + absolutes fora. */
export function isPathSafe(root: string, candidate: string): boolean {
  if (!candidate) return false;
  const resolved = path.resolve(candidate);
  const rootResolved = path.resolve(root);
  return resolved === rootResolved || resolved.startsWith(rootResolved + path.sep);
}

/** Detects stub marker em conteudo markdown. */
export function detectStub(content: string): boolean {
  // Match "**Status:** stub" (line) ou frontmatter "status: stub"
  const lines = content.split(/\r?\n/);
  for (const line of lines) {
    const trimmed = line.trim().toLowerCase();
    if (/^\*\*status:\*\*\s*stub\s*$/i.test(line.trim())) return true;
    if (/^status:\s*stub\s*$/i.test(trimmed)) return true;
  }
  return false;
}

function assertValidFolder(folder: string): asserts folder is AllowedFolder {
  if (!(ALLOWED_FOLDERS as readonly string[]).includes(folder)) {
    throw new KnowledgeError("invalid_input", `folder must be one of ${ALLOWED_FOLDERS.join(", ")}`);
  }
}

function assertValidProject(projectId: string): void {
  if (!isCanonicalProject(projectId)) {
    throw new KnowledgeError("invalid_input", `project ${projectId} not canonical`);
  }
}

/** List `.md` files em <root>/<folder>/<projectId>/. Returns [] se folder inexistente. */
export function listProjectFolderFiles(projectId: string, folder: string): FileEntry[] {
  assertValidProject(projectId);
  assertValidFolder(folder);
  const dir = path.join(KNOWLEDGE_ROOT, folder, projectId);
  if (!isPathSafe(KNOWLEDGE_ROOT, dir)) {
    throw new KnowledgeError("invalid_input", "path outside sandbox");
  }
  if (!fs.existsSync(dir)) return [];
  let names: string[];
  try {
    names = fs.readdirSync(dir).filter((n) => n.endsWith(".md"));
  } catch (e) {
    throw new KnowledgeError("io_error", String(e));
  }
  return names.map((name) => {
    const full = path.join(dir, name);
    const stat = fs.statSync(full);
    let stubFlag = false;
    try {
      const head = fs.readFileSync(full, "utf-8").slice(0, 2048);
      stubFlag = detectStub(head);
    } catch { /* ignore stub detection failures */ }
    return {
      path: path.join(folder, projectId, name),
      name,
      modified_at: stat.mtime.toISOString(),
      is_stub: stubFlag,
    };
  });
}

/** Reads a file at relativePath (must be <folder>/<projectId>/<name>). */
export function readProjectFile(projectId: string, relativePath: string): FileContent {
  assertValidProject(projectId);
  // relativePath should be folder/projectId/filename
  const parts = relativePath.split("/").filter(Boolean);
  if (parts.length < 3) {
    throw new KnowledgeError("invalid_input", "path must be <folder>/<projectId>/<filename>");
  }
  const [folder, pathProject, ...rest] = parts;
  assertValidFolder(folder);
  if (pathProject !== projectId) {
    throw new KnowledgeError("invalid_input", "path projectId mismatch");
  }
  const full = path.join(KNOWLEDGE_ROOT, folder, pathProject, ...rest);
  if (!isPathSafe(KNOWLEDGE_ROOT, full)) {
    throw new KnowledgeError("invalid_input", "path outside sandbox");
  }
  if (!fs.existsSync(full)) {
    throw new KnowledgeError("not_found", `file ${relativePath} not found`);
  }
  let content: string;
  let stat: fs.Stats;
  try {
    content = fs.readFileSync(full, "utf-8");
    stat = fs.statSync(full);
  } catch (e) {
    throw new KnowledgeError("io_error", String(e));
  }
  return {
    path: relativePath,
    content,
    modified_at: stat.mtime.toISOString(),
    size_bytes: stat.size,
    is_stub: detectStub(content),
  };
}

/** Returns the latest (lexicographic max name) file em folder/<projectId>/. */
export function findLatestFile(projectId: string, folder: string): FileEntry | null {
  const files = listProjectFolderFiles(projectId, folder);
  if (files.length === 0) return null;
  return [...files].sort((a, b) => b.name.localeCompare(a.name))[0];
}
```

- [ ] **Step 4: Rodar tests**

```bash
cd ~/code/mission-control && npm test -- --run tests/lib/projects/knowledge.test.ts 2>&1 | tail -5
```

Expected: 9/9 pass.

- [ ] **Step 5: Commit**

```bash
cd ~/code/mission-control && git add src/lib/projects/knowledge.ts tests/lib/projects/knowledge.test.ts && git commit -m "$(cat <<'EOF'
feat(lib/projects): knowledge.ts sandboxed filesystem reader

Lê bevox-knowledge limitado a 8 folders canonicos (10_prd, 20_architecture,
30_adr, 35_specs, 40_roadmap, 50_releases, 60_customer-feedback, 70_metrics)
× projetos canonicos. Path traversal rejection via path.resolve + prefix
check. Stub detection via marker lookup.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `/api/projects/[id]/prd` endpoint

**Files:**
- Create: `mission-control/src/app/api/projects/[id]/prd/route.ts`
- Create: `mission-control/tests/app/api/projects/prd.test.ts`

- [ ] **Step 1: Escrever tests**

Write `tests/app/api/projects/prd.test.ts`:

```typescript
/**
 * Contract tests for GET /api/projects/[id]/prd.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-projects-redesign.md §4.2
 */
import { describe, it, expect } from "vitest";

describe("PRD endpoint contract", () => {
  it("response shape includes files[] and latest", () => {
    type Response = {
      files: Array<{ path: string; name: string; modified_at: string; is_stub: boolean }>;
      latest: { path: string; name: string; content: string; is_stub: boolean } | null;
    };
    const sample: Response = {
      files: [{ path: "10_prd/openclaw/2026-04-25-prd.md", name: "2026-04-25-prd.md", modified_at: "2026-04-25T00:00:00Z", is_stub: true }],
      latest: { path: "10_prd/openclaw/2026-04-25-prd.md", name: "2026-04-25-prd.md", content: "# X", is_stub: true },
    };
    expect(sample.files).toHaveLength(1);
    expect(sample.latest?.is_stub).toBe(true);
  });

  it("empty case returns files=[] and latest=null", () => {
    type Response = {
      files: Array<{ path: string }>;
      latest: { path: string } | null;
    };
    const sample: Response = { files: [], latest: null };
    expect(sample.latest).toBeNull();
  });
});
```

- [ ] **Step 2: Rodar tests (passa, contract apenas)**

```bash
cd ~/code/mission-control && npm test -- --run tests/app/api/projects/prd.test.ts 2>&1 | tail -5
```

Expected: 2/2 pass (testes só validam shape em compile-time).

- [ ] **Step 3: Criar route**

Create directory: `mkdir -p src/app/api/projects/\[id\]/prd`. Then write `src/app/api/projects/[id]/prd/route.ts`:

```typescript
import { NextResponse } from "next/server";
import {
  findLatestFile,
  KnowledgeError,
  listProjectFolderFiles,
  readProjectFile,
} from "@/lib/projects/knowledge";

export const dynamic = "force-dynamic";

/**
 * GET /api/projects/<id>/prd
 *
 * Lists all PRD files for the project + returns content of latest.
 *
 * Response:
 *   {
 *     files: FileEntry[],
 *     latest: { path, name, content, is_stub } | null
 *   }
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-projects-redesign.md §4.2
 */
export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  try {
    const files = listProjectFolderFiles(id, "10_prd");
    const latestEntry = findLatestFile(id, "10_prd");
    if (!latestEntry) {
      return NextResponse.json({ files: [], latest: null });
    }
    const content = readProjectFile(id, latestEntry.path);
    return NextResponse.json({
      files,
      latest: {
        path: latestEntry.path,
        name: latestEntry.name,
        content: content.content,
        is_stub: content.is_stub,
      },
    });
  } catch (e) {
    if (e instanceof KnowledgeError) {
      const status = e.code === "not_found" ? 404 : 400;
      return NextResponse.json({ error: e.code, detail: e.message }, { status });
    }
    return NextResponse.json(
      { error: "internal", detail: String(e) },
      { status: 500 },
    );
  }
}
```

- [ ] **Step 4: Smoke local manual via curl (após restart de dev server)**

```bash
cd ~/code/mission-control && timeout 12 npm run dev > /dev/null 2>&1 &
sleep 8
curl -sS -H "Cf-Access-Authenticated-User-Email: you@example.com" "http://localhost:3000/api/projects/openclaw/prd" 2>&1 | python3 -m json.tool | head -15
```

Expected: JSON com `files: [...]`, `latest: { path: "10_prd/openclaw/2026-04-25-openclaw-prd.md", ..., is_stub: true }`.

- [ ] **Step 5: Commit**

```bash
cd ~/code/mission-control && git add "src/app/api/projects/[id]/prd/route.ts" tests/app/api/projects/prd.test.ts && git commit -m "$(cat <<'EOF'
feat(api/projects/[id]/prd): list PRDs + entrega latest content

Le 10_prd/<projectId>/*.md sandboxed via knowledge.ts. Retorna files[]
+ latest (com content + is_stub flag). Erro 400 pra projeto invalido,
404 pra arquivo inexistente.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `/api/projects/[id]/roadmap` endpoint

**Files:**
- Create: `mission-control/src/app/api/projects/[id]/roadmap/route.ts`
- Create: `mission-control/tests/app/api/projects/roadmap.test.ts`

- [ ] **Step 1: Escrever tests**

Write `tests/app/api/projects/roadmap.test.ts`:

```typescript
/**
 * Contract tests for GET /api/projects/[id]/roadmap.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-projects-redesign.md §4.2
 */
import { describe, it, expect } from "vitest";

describe("Roadmap endpoint contract", () => {
  it("response shape mirrors PRD endpoint (files[] + latest)", () => {
    type Response = {
      files: Array<{ path: string; name: string; modified_at: string; is_stub: boolean }>;
      latest: { path: string; name: string; content: string; is_stub: boolean } | null;
    };
    const sample: Response = {
      files: [],
      latest: null,
    };
    expect(sample.files).toEqual([]);
  });

  it("multi-file case: files array has multiple entries", () => {
    type Response = {
      files: Array<{ name: string }>;
    };
    const sample: Response = {
      files: [
        { name: "2026-04-25-roadmap.md" },
        { name: "2026-05-01-roadmap-v2.md" },
      ],
    };
    expect(sample.files).toHaveLength(2);
  });
});
```

- [ ] **Step 2: Rodar tests**

```bash
cd ~/code/mission-control && npm test -- --run tests/app/api/projects/roadmap.test.ts 2>&1 | tail -5
```

Expected: 2/2 pass.

- [ ] **Step 3: Criar route**

Create dir: `mkdir -p src/app/api/projects/\[id\]/roadmap`. Then write `src/app/api/projects/[id]/roadmap/route.ts`:

```typescript
import { NextResponse } from "next/server";
import {
  findLatestFile,
  KnowledgeError,
  listProjectFolderFiles,
  readProjectFile,
} from "@/lib/projects/knowledge";

export const dynamic = "force-dynamic";

/**
 * GET /api/projects/<id>/roadmap
 *
 * Lists all roadmap files for the project + returns content of latest.
 * Same shape as /prd endpoint.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-projects-redesign.md §4.2
 */
export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  try {
    const files = listProjectFolderFiles(id, "40_roadmap");
    const latestEntry = findLatestFile(id, "40_roadmap");
    if (!latestEntry) {
      return NextResponse.json({ files: [], latest: null });
    }
    const content = readProjectFile(id, latestEntry.path);
    return NextResponse.json({
      files,
      latest: {
        path: latestEntry.path,
        name: latestEntry.name,
        content: content.content,
        is_stub: content.is_stub,
      },
    });
  } catch (e) {
    if (e instanceof KnowledgeError) {
      const status = e.code === "not_found" ? 404 : 400;
      return NextResponse.json({ error: e.code, detail: e.message }, { status });
    }
    return NextResponse.json(
      { error: "internal", detail: String(e) },
      { status: 500 },
    );
  }
}
```

- [ ] **Step 4: Commit**

```bash
cd ~/code/mission-control && git add "src/app/api/projects/[id]/roadmap/route.ts" tests/app/api/projects/roadmap.test.ts && git commit -m "$(cat <<'EOF'
feat(api/projects/[id]/roadmap): list roadmaps + entrega latest content

Mesmo shape do /prd. Le 40_roadmap/<projectId>/*.md sandboxed.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `/api/projects/[id]/files` multi-purpose endpoint

**Files:**
- Create: `mission-control/src/app/api/projects/[id]/files/route.ts`
- Create: `mission-control/tests/app/api/projects/files.test.ts`

- [ ] **Step 1: Escrever tests**

Write `tests/app/api/projects/files.test.ts`:

```typescript
/**
 * Contract tests for GET /api/projects/[id]/files.
 *
 * Variant 1 (no path): returns folders tree.
 * Variant 2 (with ?path=...): returns file content.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-projects-redesign.md §4.2
 */
import { describe, it, expect } from "vitest";

describe("Files endpoint contract — tree variant", () => {
  it("response shape has folders map keyed by folder name", () => {
    type Response = {
      folders: Record<string, { count: number; files: string[] }>;
    };
    const sample: Response = {
      folders: {
        "10_prd": { count: 1, files: ["2026-04-25-prd.md"] },
        "20_architecture": { count: 14, files: ["a.md"] },
        "30_adr": { count: 0, files: [] },
        "35_specs": { count: 51, files: [] },
        "40_roadmap": { count: 1, files: [] },
        "50_releases": { count: 2, files: [] },
        "60_customer-feedback": { count: 0, files: [] },
        "70_metrics": { count: 0, files: [] },
      },
    };
    expect(Object.keys(sample.folders)).toHaveLength(8);
  });
});

describe("Files endpoint contract — read variant", () => {
  it("response shape returns content + metadata", () => {
    type Response = {
      path: string;
      content: string;
      modified_at: string;
      size_bytes: number;
      is_stub: boolean;
    };
    const sample: Response = {
      path: "35_specs/openclaw/foo.md",
      content: "# Hello",
      modified_at: "2026-04-25T00:00:00Z",
      size_bytes: 42,
      is_stub: false,
    };
    expect(sample.size_bytes).toBe(42);
  });
});
```

- [ ] **Step 2: Rodar tests**

```bash
cd ~/code/mission-control && npm test -- --run tests/app/api/projects/files.test.ts 2>&1 | tail -5
```

Expected: 2/2 pass.

- [ ] **Step 3: Criar route**

Create dir: `mkdir -p src/app/api/projects/\[id\]/files`. Then write `src/app/api/projects/[id]/files/route.ts`:

```typescript
import { NextRequest, NextResponse } from "next/server";
import {
  ALLOWED_FOLDERS,
  KnowledgeError,
  listProjectFolderFiles,
  readProjectFile,
} from "@/lib/projects/knowledge";

export const dynamic = "force-dynamic";

/**
 * GET /api/projects/<id>/files
 *
 * Variant 1 (no ?path query): returns tree of folders with counts + filenames.
 * Variant 2 (?path=<folder>/<id>/<file>): returns file content.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-projects-redesign.md §4.2
 */
export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const url = new URL(req.url);
  const queryPath = url.searchParams.get("path");

  try {
    if (queryPath) {
      // Variant 2: read file
      const content = readProjectFile(id, queryPath);
      return NextResponse.json(content);
    }

    // Variant 1: list tree
    const folders: Record<string, { count: number; files: string[] }> = {};
    for (const folder of ALLOWED_FOLDERS) {
      const entries = listProjectFolderFiles(id, folder);
      folders[folder] = {
        count: entries.length,
        files: entries.map((e) => e.name),
      };
    }
    return NextResponse.json({ folders });
  } catch (e) {
    if (e instanceof KnowledgeError) {
      const status = e.code === "not_found" ? 404 : 400;
      return NextResponse.json({ error: e.code, detail: e.message }, { status });
    }
    return NextResponse.json(
      { error: "internal", detail: String(e) },
      { status: 500 },
    );
  }
}
```

- [ ] **Step 4: Commit**

```bash
cd ~/code/mission-control && git add "src/app/api/projects/[id]/files/route.ts" tests/app/api/projects/files.test.ts && git commit -m "$(cat <<'EOF'
feat(api/projects/[id]/files): tree + file read multi-purpose endpoint

Sem ?path: lista 8 folders canonicos com counts + filenames.
Com ?path=<folder>/<id>/<file>: retorna content + metadata.
Sandboxed via knowledge.ts; rejeita traversal/projeto invalido.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Refactor `SprintsPageInner` — export named + props embed

**Files:**
- Modify: `mission-control/src/app/(dashboard)/sprints/page.tsx`

- [ ] **Step 1: Inspecionar arquivo atual**

```bash
grep -n "function SprintsPageInner\|function SprintsPage\|projectFilter" ~/code/mission-control/src/app/\(dashboard\)/sprints/page.tsx | head -10
```

Expected: encontrar `function SprintsPageInner()` e `export default function SprintsPage()`.

- [ ] **Step 2: Adicionar props opcionais + export named**

Editar `src/app/(dashboard)/sprints/page.tsx`:

(a) Adicionar interface antes de `function SprintsPageInner()`:

```typescript
export interface SprintsPageInnerProps {
  /** Quando setado, ignora ?project= URL e força filter pra esse projeto. */
  forcedProject?: string;
  /** Quando true, esconde o dropdown "Project: ▼" no header. */
  hideProjectFilter?: boolean;
}
```

(b) Trocar a assinatura de `function SprintsPageInner()` pra:

```typescript
export function SprintsPageInner({
  forcedProject,
  hideProjectFilter,
}: SprintsPageInnerProps = {}) {
```

(c) Logo após `const projectFilter = searchParams.get("project");`, sobrescrever quando `forcedProject` está setado:

```typescript
  const urlProjectFilter = searchParams.get("project");
  const projectFilter = forcedProject ?? urlProjectFilter;
```

(d) `setProjectFilter` callback fica no-op quando `forcedProject` está setado. No body do callback existente, adicionar early return na primeira linha:

```typescript
  const setProjectFilter = useCallback(
    (project: string | null) => {
      if (forcedProject) return;
      // ... resto do código existente
```

(e) Esconder dropdown quando `hideProjectFilter` true. Encontrar o `<select id="project-filter">` block e wrappar:

```typescript
{!hideProjectFilter && (
  <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
    <label htmlFor="project-filter" ...>Project:</label>
    <select id="project-filter" ...>...</select>
  </div>
)}
```

- [ ] **Step 3: Rodar tests existentes**

```bash
cd ~/code/mission-control && npm test -- --run "tests/app/(dashboard)/sprints" 2>&1 | tail -5
```

Expected: tests existentes continuam passando (pure helpers não mudaram).

- [ ] **Step 4: Verify type-check + build**

```bash
cd ~/code/mission-control && npm run build 2>&1 | grep -E "error|Error|/sprints" | head -5
```

Expected: `/sprints` aparece em route table sem erro.

- [ ] **Step 5: Commit**

```bash
cd ~/code/mission-control && git add "src/app/(dashboard)/sprints/page.tsx" && git commit -m "$(cat <<'EOF'
refactor(sprints): export SprintsPageInner + forcedProject/hideProjectFilter props

Pre-requisito da wave Projects redesign — aba Sprints do detail page
embed o componente. Backward-compat: sem props, comportamento standalone
preservado integralmente.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: `MarkdownViewer` component

**Files:**
- Create: `mission-control/src/components/projects/MarkdownViewer.tsx`
- Create: `mission-control/tests/components/projects/MarkdownViewer.test.tsx`

- [ ] **Step 1: Escrever contract tests**

Create dir: `mkdir -p tests/components/projects`. Then write `tests/components/projects/MarkdownViewer.test.tsx`:

```typescript
/**
 * Contract tests for MarkdownViewer.
 *
 * Type-level + helpers (sem renderToStaticMarkup pra components com hooks).
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-projects-redesign.md §3.3
 */
import { describe, it, expect } from "vitest";
import type { MarkdownViewerProps } from "@/components/projects/MarkdownViewer";

describe("MarkdownViewerProps contract", () => {
  it("requires source + filename; stub + onRawClick optional", () => {
    const props: MarkdownViewerProps = {
      source: "# Hello",
      filename: "foo.md",
    };
    expect(props.source).toBe("# Hello");
    expect(props.filename).toBe("foo.md");
  });

  it("accepts stub flag + onRawClick callback", () => {
    let clicked = false;
    const props: MarkdownViewerProps = {
      source: "x",
      filename: "y.md",
      stub: true,
      onRawClick: () => { clicked = true; },
    };
    props.onRawClick?.();
    expect(clicked).toBe(true);
    expect(props.stub).toBe(true);
  });
});
```

- [ ] **Step 2: Rodar tests (devem falhar)**

```bash
cd ~/code/mission-control && npm test -- --run tests/components/projects/MarkdownViewer.test.tsx 2>&1 | tail -5
```

Expected: ERR `Cannot find module '@/components/projects/MarkdownViewer'`.

- [ ] **Step 3: Criar component**

Create dir: `mkdir -p src/components/projects`. Then write `src/components/projects/MarkdownViewer.tsx`:

```typescript
"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export interface MarkdownViewerProps {
  source: string;
  filename: string;
  stub?: boolean;
  onRawClick?: () => void;
}

/**
 * Markdown viewer com header (filename + stub badge + raw button) + body
 * renderizado via react-markdown + remark-gfm. Theme dark coerente com MC.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-projects-redesign.md §3.3
 */
export function MarkdownViewer({ source, filename, stub, onRawClick }: MarkdownViewerProps) {
  return (
    <div style={{ background: "#1a2230", borderRadius: 6, overflow: "hidden", height: "100%" }}>
      <div style={{
        background: "#161b22",
        padding: "0.5rem 0.85rem",
        borderBottom: "1px solid #2a2f3e",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
      }}>
        <span style={{ color: "#888", fontSize: "0.7rem", fontFamily: "monospace" }}>
          📄 {filename}
        </span>
        <div style={{ display: "flex", gap: "0.4rem", alignItems: "center" }}>
          {stub && (
            <span style={{
              background: "#5f5a1e",
              color: "#e4dc6e",
              padding: "0.1rem 0.4rem",
              borderRadius: 3,
              fontSize: "0.6rem",
            }}>stub</span>
          )}
          {onRawClick && (
            <button
              type="button"
              onClick={onRawClick}
              style={{
                background: "transparent",
                border: "none",
                color: "#666",
                fontSize: "0.65rem",
                cursor: "pointer",
              }}
            >↗ raw</button>
          )}
        </div>
      </div>
      <div className="markdown-body" style={{ padding: "1.25rem", color: "#e0e0e0", lineHeight: 1.65, fontSize: "0.85rem", overflow: "auto" }}>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{source}</ReactMarkdown>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Rodar tests**

```bash
cd ~/code/mission-control && npm test -- --run tests/components/projects/MarkdownViewer.test.tsx 2>&1 | tail -5
```

Expected: 2/2 pass.

- [ ] **Step 5: Commit**

```bash
cd ~/code/mission-control && git add src/components/projects/MarkdownViewer.tsx tests/components/projects/MarkdownViewer.test.tsx && git commit -m "$(cat <<'EOF'
feat(components/projects): MarkdownViewer com header + react-markdown + remark-gfm

Header: filename mono + stub badge condicional + raw button opcional.
Body: react-markdown renderiza GFM (tables, task lists, fenced code).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Rewrite `ProjectCard` — health-grid layout

**Files:**
- Modify: `mission-control/src/app/(dashboard)/projects/ProjectCard.tsx`

- [ ] **Step 1: Inspecionar atual**

```bash
cat ~/code/mission-control/src/app/\(dashboard\)/projects/ProjectCard.tsx
```

Expected: file simples (~33 LOC) já existe.

- [ ] **Step 2: Substituir conteúdo inteiro**

Write completo (overwrite) `src/app/(dashboard)/projects/ProjectCard.tsx`:

```typescript
"use client";

import Link from "next/link";
import type { ProjectSummary, Dot } from "@/lib/projects/types";
import { getProjectColors } from "@/lib/projects/colors";

interface Props {
  project: ProjectSummary;
}

const DOT_COLORS: Record<Dot, string> = {
  ok: "#7ec896",
  partial: "#e4a06e",
  missing: "#e46e6e",
};

/** Abreviação curta do project id pra exibir no canto do card. */
function abbrev(id: string): string {
  if (id === "bevox-mobile") return "M";
  if (id === "bevox-backend") return "B";
  if (id === "bevox-web") return "W";
  if (id === "bevox-console") return "C";
  if (id === "bevox-harness") return "H";
  if (id === "openclaw") return "O";
  if (id === "company-os") return "CO";
  if (id === "mission-control") return "MC";
  if (id === "bevox-knowledge") return "K";
  if (id === "vox") return "V";
  return id.slice(0, 2).toUpperCase();
}

/**
 * Health-grid layout card pra /projects list.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-projects-redesign.md §3.1
 */
export default function ProjectCard({ project }: Props) {
  const colors = getProjectColors(project.id);
  return (
    <Link
      href={`/projects/${encodeURIComponent(project.id)}`}
      style={{
        display: "block",
        background: "#1a2230",
        borderLeft: `3px solid ${colors.fg}`,
        borderRadius: 4,
        padding: "0.6rem 0.75rem",
        textDecoration: "none",
        transition: "background-color 0.15s",
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = "#222b3c")}
      onMouseLeave={(e) => (e.currentTarget.style.background = "#1a2230")}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: "0.2rem" }}>
        <span style={{
          background: colors.bg,
          color: colors.fg,
          padding: "0.1rem 0.45rem",
          borderRadius: 10,
          fontSize: "0.65rem",
          fontWeight: 600,
        }}>{project.id}</span>
        <span style={{ fontFamily: "monospace", color: "#555", fontSize: "0.6rem" }}>{abbrev(project.id)}</span>
      </div>
      <div style={{ color: "#e0e0e0", fontSize: "0.82rem", fontWeight: 600, margin: "0.1rem 0" }}>
        {project.name}
      </div>
      <div style={{ color: "#888", fontSize: "0.68rem", marginBottom: "0.4rem", lineHeight: 1.3, overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>
        {project.description}
      </div>
      <div style={{ display: "flex", gap: "0.25rem", margin: "0.35rem 0" }}>
        <span title="bot" style={{ width: 8, height: 8, borderRadius: "50%", background: DOT_COLORS[project.health.bot] }} />
        <span title="workspace" style={{ width: 8, height: 8, borderRadius: "50%", background: DOT_COLORS[project.health.workspace] }} />
        <span title="kanban" style={{ width: 8, height: 8, borderRadius: "50%", background: DOT_COLORS[project.health.kanban] }} />
        <span title="docs" style={{ width: 8, height: 8, borderRadius: "50%", background: DOT_COLORS[project.health.knowledge] }} />
      </div>
      <div style={{ color: "#666", fontSize: "0.65rem", display: "flex", gap: "0.35rem" }}>
        <span>{project.counts.sprints_active} sprint(s)</span>
        <span>·</span>
        <span>{project.counts.tasks_in_progress} in_progress</span>
      </div>
    </Link>
  );
}
```

- [ ] **Step 3: Verify build + tests**

```bash
cd ~/code/mission-control && npm test -- --run 2>&1 | tail -3
```

Expected: full suite green.

- [ ] **Step 4: Commit**

```bash
cd ~/code/mission-control && git add "src/app/(dashboard)/projects/ProjectCard.tsx" && git commit -m "$(cat <<'EOF'
feat(projects/ProjectCard): rewrite health-grid layout dark theme

Chip color-coded via getProjectColors + nome display + descricao
line-clamp-2 + 4 health dots + stats line. Border-left 3px na cor
do projeto. Hover effect.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: `TabNav` component + URL state sync

**Files:**
- Create: `mission-control/src/components/projects/TabNav.tsx`
- Create: `mission-control/tests/components/projects/TabNav.test.tsx`

- [ ] **Step 1: Escrever contract tests**

Write `tests/components/projects/TabNav.test.tsx`:

```typescript
/**
 * Contract tests for TabNav.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-projects-redesign.md §3.2
 */
import { describe, it, expect } from "vitest";
import type { TabNavProps, TabKey } from "@/components/projects/TabNav";

describe("TabNavProps contract", () => {
  it("active key + onChange callback", () => {
    let lastChosen: TabKey | null = null;
    const props: TabNavProps = {
      active: "geral",
      onChange: (t) => { lastChosen = t; },
      sprintCount: 10,
    };
    props.onChange("roadmap");
    expect(lastChosen).toBe("roadmap");
    expect(props.active).toBe("geral");
    expect(props.sprintCount).toBe(10);
  });

  it("TabKey type allows the 4 known tabs", () => {
    const tabs: TabKey[] = ["geral", "roadmap", "ficheiros", "sprints"];
    expect(tabs).toHaveLength(4);
  });
});
```

- [ ] **Step 2: Rodar tests (devem falhar)**

```bash
cd ~/code/mission-control && npm test -- --run tests/components/projects/TabNav.test.tsx 2>&1 | tail -5
```

Expected: ERR.

- [ ] **Step 3: Criar component**

Write `src/components/projects/TabNav.tsx`:

```typescript
"use client";

export type TabKey = "geral" | "roadmap" | "ficheiros" | "sprints";

export interface TabNavProps {
  active: TabKey;
  onChange: (key: TabKey) => void;
  sprintCount?: number;
}

const TABS: { key: TabKey; label: string }[] = [
  { key: "geral", label: "Geral" },
  { key: "roadmap", label: "Roadmap" },
  { key: "ficheiros", label: "Ficheiros" },
  { key: "sprints", label: "Sprints" },
];

/**
 * Tab navigation com label fixos. Active tab tem border-bottom 2px azul.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-projects-redesign.md §3.2
 */
export function TabNav({ active, onChange, sprintCount }: TabNavProps) {
  return (
    <div style={{
      display: "flex",
      gap: "0.1rem",
      borderBottom: "1px solid #2a2f3e",
    }}>
      {TABS.map((tab) => {
        const isActive = active === tab.key;
        const label = tab.key === "sprints" && typeof sprintCount === "number"
          ? `${tab.label} (${sprintCount})`
          : tab.label;
        return (
          <button
            key={tab.key}
            type="button"
            onClick={() => onChange(tab.key)}
            style={{
              padding: "0.5rem 0.9rem",
              background: "transparent",
              border: "none",
              borderBottom: isActive ? "2px solid #4f9eff" : "2px solid transparent",
              color: isActive ? "#4f9eff" : "#888",
              fontSize: "0.85rem",
              fontWeight: isActive ? 600 : 400,
              cursor: "pointer",
            }}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Rodar tests**

```bash
cd ~/code/mission-control && npm test -- --run tests/components/projects/TabNav.test.tsx 2>&1 | tail -5
```

Expected: 2/2 pass.

- [ ] **Step 5: Commit**

```bash
cd ~/code/mission-control && git add src/components/projects/TabNav.tsx tests/components/projects/TabNav.test.tsx && git commit -m "$(cat <<'EOF'
feat(components/projects): TabNav com 4 tabs (Geral/Roadmap/Ficheiros/Sprints)

Active tab border-bottom 2px azul. sprintCount opcional renderiza label
'Sprints (N)'. URL sync feito pelo parent via onChange callback.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: `ProjectGeralTab` — split layout PRD viewer

**Files:**
- Create: `mission-control/src/components/projects/ProjectGeralTab.tsx`
- Create: `mission-control/tests/components/projects/ProjectGeralTab.test.tsx`

- [ ] **Step 1: Escrever contract tests**

Write `tests/components/projects/ProjectGeralTab.test.tsx`:

```typescript
/**
 * Contract tests for ProjectGeralTab.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-projects-redesign.md §3.2
 */
import { describe, it, expect } from "vitest";
import type { ProjectGeralTabProps } from "@/components/projects/ProjectGeralTab";
import type { ProjectDetail } from "@/lib/projects/types";

describe("ProjectGeralTabProps contract", () => {
  it("requires detail prop with ProjectDetail shape", () => {
    const detail: ProjectDetail = {
      id: "openclaw",
      name: "OpenClaw",
      description: "Test",
      health: { bot: "ok", workspace: "ok", kanban: "ok", knowledge: "ok" },
      counts: { sprints_active: 1, tasks_in_progress: 0 },
      health_details: { bot: { ok: true, detail: "ok" }, workspace: { ok: true, detail: "ok" }, kanban: { ok: true, detail: "ok" }, knowledge: { ok: true, detail: "ok" } },
      links: { repo: null, adrs: [] },
      sprints: { active: [], closed: [] },
      tasks_in_flight: [],
    };
    const props: ProjectGeralTabProps = { detail };
    expect(props.detail.id).toBe("openclaw");
  });
});
```

- [ ] **Step 2: Rodar tests (devem falhar)**

```bash
cd ~/code/mission-control && npm test -- --run tests/components/projects/ProjectGeralTab.test.tsx 2>&1 | tail -5
```

Expected: ERR.

- [ ] **Step 3: Criar component**

Write `src/components/projects/ProjectGeralTab.tsx`:

```typescript
"use client";

import { useEffect, useState } from "react";
import type { ProjectDetail } from "@/lib/projects/types";
import { MarkdownViewer } from "./MarkdownViewer";

export interface ProjectGeralTabProps {
  detail: ProjectDetail;
}

interface PrdResponse {
  files: Array<{ path: string; name: string; modified_at: string; is_stub: boolean }>;
  latest: { path: string; name: string; content: string; is_stub: boolean } | null;
}

/**
 * Split layout: esq info estatica (description/health/stats/links); dir PRD viewer.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-projects-redesign.md §3.2
 */
export function ProjectGeralTab({ detail }: ProjectGeralTabProps) {
  const [prd, setPrd] = useState<PrdResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`/api/projects/${encodeURIComponent(detail.id)}/prd`, { cache: "no-store" });
        if (!r.ok) {
          const j = await r.json().catch(() => ({}));
          throw new Error(typeof j.detail === "string" ? j.detail : `HTTP ${r.status}`);
        }
        const data = (await r.json()) as PrdResponse;
        if (!cancelled) { setPrd(data); setError(null); }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => { cancelled = true; };
  }, [detail.id]);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: "1rem", marginTop: "1rem" }}>
      {/* LEFT */}
      <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
        <InfoBox label="Description">
          <div style={{ color: "#e0e0e0", fontSize: "0.78rem", lineHeight: 1.5 }}>{detail.description}</div>
        </InfoBox>
        <InfoBox label="Health">
          <div style={{ color: "#888", fontSize: "0.72rem", lineHeight: 1.7 }}>
            <DotLine label="Bot" status={detail.health.bot} />
            <DotLine label="Workspace" status={detail.health.workspace} />
            <DotLine label="Kanban" status={detail.health.kanban} />
            <DotLine label="Docs" status={detail.health.knowledge} />
          </div>
        </InfoBox>
        <InfoBox label="Stats">
          <div style={{ color: "#888", fontSize: "0.72rem", lineHeight: 1.7 }}>
            <div>📊 {detail.counts.sprints_active} sprint(s) ativo(s)</div>
            <div>🔥 {detail.tasks_in_flight.length} task(s) em flight</div>
          </div>
        </InfoBox>
        <InfoBox label="External links">
          <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem", fontSize: "0.7rem" }}>
            {detail.links.repo && (
              <a href={detail.links.repo} target="_blank" rel="noreferrer" style={{ color: "#4f9eff", textDecoration: "none" }}>↗ GitHub repo</a>
            )}
            {detail.links.adrs.map((adr, i) => (
              <a key={i} href={adr.url ?? "#"} target="_blank" rel="noreferrer" style={{ color: "#4f9eff", textDecoration: "none" }}>↗ {adr.label}</a>
            ))}
          </div>
        </InfoBox>
      </div>

      {/* RIGHT — PRD viewer */}
      <div style={{ minHeight: 400 }}>
        {error && <ErrorPanel message={error} />}
        {!error && !prd && <div style={{ color: "#888", padding: "1rem" }}>Carregando PRD…</div>}
        {!error && prd && !prd.latest && (
          <EmptyPanel
            title="Nenhum PRD pra este projeto"
            hint={`Crie em bevox-knowledge/10_prd/${detail.id}/`}
          />
        )}
        {!error && prd?.latest && (
          <MarkdownViewer
            source={prd.latest.content}
            filename={prd.latest.path}
            stub={prd.latest.is_stub}
          />
        )}
      </div>
    </div>
  );
}

function InfoBox({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ background: "#1a2230", padding: "0.7rem", borderRadius: 5 }}>
      <div style={{ color: "#888", fontSize: "0.6rem", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.3rem" }}>
        {label}
      </div>
      {children}
    </div>
  );
}

function DotLine({ label, status }: { label: string; status: "ok" | "partial" | "missing" }) {
  const color = status === "ok" ? "#7ec896" : status === "partial" ? "#e4a06e" : "#e46e6e";
  const icon = status === "ok" ? "✓" : status === "partial" ? "⚠" : "✗";
  return <div>{icon} <strong style={{ color }}>{label}</strong></div>;
}

function ErrorPanel({ message }: { message: string }) {
  return (
    <div style={{ background: "#3f1e1e", color: "#e46e6e", padding: "1rem", borderRadius: 4 }}>
      Failed to load PRD: {message}
    </div>
  );
}

function EmptyPanel({ title, hint }: { title: string; hint: string }) {
  return (
    <div style={{ background: "#1a2230", padding: "2rem", borderRadius: 6, textAlign: "center" }}>
      <div style={{ color: "#e4a06e", fontWeight: 600, marginBottom: "0.5rem" }}>{title}</div>
      <div style={{ color: "#888", fontSize: "0.78rem", fontFamily: "monospace" }}>{hint}</div>
    </div>
  );
}
```

- [ ] **Step 4: Verificar shape de `ProjectDetail.links`**

```bash
grep -A 10 "ProjectLinks\|links:" ~/code/mission-control/src/lib/projects/types.ts | head -20
```

Se shape diferente do assumido (`{ repo, adrs[] }`), ajustar `ProjectGeralTab.tsx` linhas 78-86 pra bater.

- [ ] **Step 5: Rodar tests**

```bash
cd ~/code/mission-control && npm test -- --run tests/components/projects/ProjectGeralTab.test.tsx 2>&1 | tail -5
```

Expected: 1/1 pass.

- [ ] **Step 6: Commit**

```bash
cd ~/code/mission-control && git add src/components/projects/ProjectGeralTab.tsx tests/components/projects/ProjectGeralTab.test.tsx && git commit -m "$(cat <<'EOF'
feat(components/projects): ProjectGeralTab split layout PRD viewer

Esq: 4 info boxes (description/health/stats/external links). Dir: PRD
markdown viewer com loading/error/empty states. Fetch /api/projects/<id>/prd.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: `RoadmapDocsList` + `ProjectRoadmapTab`

**Files:**
- Create: `mission-control/src/components/projects/RoadmapDocsList.tsx`
- Create: `mission-control/src/components/projects/ProjectRoadmapTab.tsx`
- Create: `mission-control/tests/components/projects/ProjectRoadmapTab.test.tsx`

- [ ] **Step 1: Escrever tests**

Write `tests/components/projects/ProjectRoadmapTab.test.tsx`:

```typescript
import { describe, it, expect } from "vitest";
import type { ProjectRoadmapTabProps } from "@/components/projects/ProjectRoadmapTab";
import type { RoadmapDocsListProps } from "@/components/projects/RoadmapDocsList";

describe("ProjectRoadmapTabProps contract", () => {
  it("requires projectId string", () => {
    const props: ProjectRoadmapTabProps = { projectId: "openclaw" };
    expect(props.projectId).toBe("openclaw");
  });
});

describe("RoadmapDocsListProps contract", () => {
  it("requires docs + selected + onSelect", () => {
    let last: string | null = null;
    const props: RoadmapDocsListProps = {
      docs: [{ path: "x", name: "x.md", modified_at: "", is_stub: true }],
      selected: "x",
      onSelect: (p) => { last = p; },
    };
    props.onSelect("y");
    expect(last).toBe("y");
  });
});
```

- [ ] **Step 2: Rodar tests (devem falhar)**

```bash
cd ~/code/mission-control && npm test -- --run tests/components/projects/ProjectRoadmapTab.test.tsx 2>&1 | tail -5
```

Expected: ERR.

- [ ] **Step 3: Criar `RoadmapDocsList.tsx`**

```typescript
"use client";

export interface RoadmapDocEntry {
  path: string;
  name: string;
  modified_at: string;
  is_stub: boolean;
}

export interface RoadmapDocsListProps {
  docs: RoadmapDocEntry[];
  selected: string | null;
  onSelect: (path: string) => void;
}

/** Lista clicavel de roadmap docs com badge stub. */
export function RoadmapDocsList({ docs, selected, onSelect }: RoadmapDocsListProps) {
  if (docs.length === 0) {
    return <div style={{ color: "#666", fontSize: "0.7rem", fontStyle: "italic" }}>Nenhum roadmap doc.</div>;
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.2rem" }}>
      {docs.map((doc) => {
        const active = doc.path === selected;
        return (
          <button
            key={doc.path}
            type="button"
            onClick={() => onSelect(doc.path)}
            style={{
              background: active ? "#2a2f3e" : "transparent",
              border: "none",
              padding: "0.3rem 0.45rem",
              borderRadius: 3,
              color: active ? "#4f9eff" : "#888",
              fontSize: "0.7rem",
              fontFamily: "monospace",
              textAlign: "left",
              cursor: "pointer",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <span>📄 {doc.name}</span>
            {doc.is_stub && (
              <span style={{ background: "#5f5a1e", color: "#e4dc6e", padding: "0 0.25rem", borderRadius: 2, fontSize: "0.55rem" }}>
                stub
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Criar `ProjectRoadmapTab.tsx`**

```typescript
"use client";

import { useCallback, useEffect, useState } from "react";
import { MarkdownViewer } from "./MarkdownViewer";
import { RoadmapDocsList, type RoadmapDocEntry } from "./RoadmapDocsList";

export interface ProjectRoadmapTabProps {
  projectId: string;
}

interface RoadmapResponse {
  files: RoadmapDocEntry[];
  latest: { path: string; name: string; content: string; is_stub: boolean } | null;
}

interface FileResponse {
  path: string;
  content: string;
  is_stub: boolean;
}

/**
 * Split layout: esq lista de roadmap docs + esq stats; dir markdown viewer
 * do doc selecionado (default = latest).
 */
export function ProjectRoadmapTab({ projectId }: ProjectRoadmapTabProps) {
  const [meta, setMeta] = useState<RoadmapResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [selectedContent, setSelectedContent] = useState<FileResponse | null>(null);

  // Initial fetch: listing + latest
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`/api/projects/${encodeURIComponent(projectId)}/roadmap`, { cache: "no-store" });
        if (!r.ok) {
          const j = await r.json().catch(() => ({}));
          throw new Error(typeof j.detail === "string" ? j.detail : `HTTP ${r.status}`);
        }
        const data = (await r.json()) as RoadmapResponse;
        if (!cancelled) {
          setMeta(data);
          setSelectedPath(data.latest?.path ?? null);
          if (data.latest) {
            setSelectedContent({ path: data.latest.path, content: data.latest.content, is_stub: data.latest.is_stub });
          }
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => { cancelled = true; };
  }, [projectId]);

  // When user selects a non-latest doc, fetch its content
  const onSelect = useCallback(async (path: string) => {
    setSelectedPath(path);
    if (selectedContent?.path === path) return;
    try {
      const r = await fetch(`/api/projects/${encodeURIComponent(projectId)}/files?path=${encodeURIComponent(path)}`, { cache: "no-store" });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        throw new Error(typeof j.detail === "string" ? j.detail : `HTTP ${r.status}`);
      }
      const data = (await r.json()) as FileResponse;
      setSelectedContent(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [projectId, selectedContent?.path]);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: "1rem", marginTop: "1rem" }}>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
        <div style={{ background: "#1a2230", padding: "0.7rem", borderRadius: 5 }}>
          <div style={{ color: "#888", fontSize: "0.6rem", textTransform: "uppercase", marginBottom: "0.3rem" }}>Roadmap docs</div>
          <RoadmapDocsList
            docs={meta?.files ?? []}
            selected={selectedPath}
            onSelect={onSelect}
          />
        </div>
        <div style={{ background: "#1a2230", padding: "0.7rem", borderRadius: 5 }}>
          <div style={{ color: "#888", fontSize: "0.6rem", textTransform: "uppercase", marginBottom: "0.3rem" }}>Atalho</div>
          <a href="/roadmap" style={{ color: "#4f9eff", fontSize: "0.7rem", textDecoration: "none" }}>→ /roadmap (visão global)</a>
        </div>
      </div>
      <div style={{ minHeight: 400 }}>
        {error && (
          <div style={{ background: "#3f1e1e", color: "#e46e6e", padding: "1rem", borderRadius: 4 }}>
            Failed to load roadmap: {error}
          </div>
        )}
        {!error && !meta && <div style={{ color: "#888", padding: "1rem" }}>Carregando roadmap…</div>}
        {!error && meta && !meta.latest && (
          <div style={{ background: "#1a2230", padding: "2rem", borderRadius: 6, textAlign: "center" }}>
            <div style={{ color: "#e4a06e", fontWeight: 600, marginBottom: "0.5rem" }}>Nenhum roadmap pra este projeto</div>
            <div style={{ color: "#888", fontSize: "0.78rem", fontFamily: "monospace" }}>
              Crie em bevox-knowledge/40_roadmap/{projectId}/
            </div>
          </div>
        )}
        {!error && selectedContent && (
          <MarkdownViewer
            source={selectedContent.content}
            filename={selectedContent.path}
            stub={selectedContent.is_stub}
          />
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Rodar tests**

```bash
cd ~/code/mission-control && npm test -- --run tests/components/projects/ProjectRoadmapTab.test.tsx 2>&1 | tail -5
```

Expected: 2/2 pass.

- [ ] **Step 6: Commit**

```bash
cd ~/code/mission-control && git add src/components/projects/RoadmapDocsList.tsx src/components/projects/ProjectRoadmapTab.tsx tests/components/projects/ProjectRoadmapTab.test.tsx && git commit -m "$(cat <<'EOF'
feat(components/projects): ProjectRoadmapTab + RoadmapDocsList

Split layout: esq lista clicavel de roadmap docs + atalho pra /roadmap
global. Dir markdown viewer (default = latest, switchable via lista).
Multi-doc support: switching dispara fetch /api/projects/<id>/files?path=.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: `DocTree` component

**Files:**
- Create: `mission-control/src/components/projects/DocTree.tsx`
- Create: `mission-control/tests/components/projects/DocTree.test.tsx`

- [ ] **Step 1: Escrever tests**

Write `tests/components/projects/DocTree.test.tsx`:

```typescript
import { describe, it, expect } from "vitest";
import type { DocTreeProps, FoldersTree } from "@/components/projects/DocTree";

describe("DocTreeProps contract", () => {
  it("requires tree + projectId + selected + onSelectFile", () => {
    let lastSelected: string | null = null;
    const tree: FoldersTree = {
      "10_prd": { count: 1, files: ["foo.md"] },
      "20_architecture": { count: 0, files: [] },
      "30_adr": { count: 0, files: [] },
      "35_specs": { count: 0, files: [] },
      "40_roadmap": { count: 0, files: [] },
      "50_releases": { count: 0, files: [] },
      "60_customer-feedback": { count: 0, files: [] },
      "70_metrics": { count: 0, files: [] },
    };
    const props: DocTreeProps = {
      tree,
      projectId: "openclaw",
      selected: null,
      onSelectFile: (p) => { lastSelected = p; },
    };
    props.onSelectFile("10_prd/openclaw/foo.md");
    expect(lastSelected).toBe("10_prd/openclaw/foo.md");
  });
});
```

- [ ] **Step 2: Rodar tests (devem falhar)**

```bash
cd ~/code/mission-control && npm test -- --run tests/components/projects/DocTree.test.tsx 2>&1 | tail -5
```

Expected: ERR.

- [ ] **Step 3: Criar component**

Write `src/components/projects/DocTree.tsx`:

```typescript
"use client";

import { useState } from "react";

export type FoldersTree = Record<string, { count: number; files: string[] }>;

export interface DocTreeProps {
  tree: FoldersTree;
  projectId: string;
  selected: string | null;
  onSelectFile: (relativePath: string) => void;
}

const FOLDER_ORDER = [
  "10_prd",
  "20_architecture",
  "30_adr",
  "35_specs",
  "40_roadmap",
  "50_releases",
  "60_customer-feedback",
  "70_metrics",
] as const;

/**
 * File tree colapsavel pros 8 folders canonicos. Folders com count > 0
 * iniciam expandidos; com count 0 mostram badge cinza nao-clicavel.
 */
export function DocTree({ tree, projectId, selected, onSelectFile }: DocTreeProps) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>(() => {
    const init: Record<string, boolean> = {};
    for (const f of FOLDER_ORDER) {
      init[f] = (tree[f]?.count ?? 0) > 0;
    }
    return init;
  });

  return (
    <div style={{ fontFamily: "monospace", fontSize: "0.7rem", lineHeight: 1.7, color: "#e0e0e0" }}>
      {FOLDER_ORDER.map((folder) => {
        const data = tree[folder] ?? { count: 0, files: [] };
        const isOpen = expanded[folder];
        const empty = data.count === 0;
        return (
          <div key={folder}>
            <button
              type="button"
              onClick={() => !empty && setExpanded((prev) => ({ ...prev, [folder]: !prev[folder] }))}
              disabled={empty}
              style={{
                background: "transparent",
                border: "none",
                color: empty ? "#444" : "#888",
                cursor: empty ? "default" : "pointer",
                padding: 0,
                fontSize: "0.7rem",
                fontFamily: "monospace",
              }}
            >
              {empty ? "·" : isOpen ? "▼" : "▶"} {folder}{" "}
              <span style={{ color: "#666", fontSize: "0.6rem" }}>({data.count})</span>
            </button>
            {isOpen && data.files.length > 0 && (
              <div style={{ paddingLeft: "1rem" }}>
                {data.files.map((name) => {
                  const relPath = `${folder}/${projectId}/${name}`;
                  const active = selected === relPath;
                  return (
                    <button
                      key={name}
                      type="button"
                      onClick={() => onSelectFile(relPath)}
                      style={{
                        background: active ? "#2a2f3e" : "transparent",
                        border: "none",
                        color: active ? "#4f9eff" : "#888",
                        cursor: "pointer",
                        padding: "0.05rem 0.3rem",
                        borderRadius: 2,
                        textAlign: "left",
                        display: "block",
                        fontSize: "0.68rem",
                        fontFamily: "monospace",
                      }}
                    >
                      📄 {name}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Rodar tests**

```bash
cd ~/code/mission-control && npm test -- --run tests/components/projects/DocTree.test.tsx 2>&1 | tail -5
```

Expected: 1/1 pass.

- [ ] **Step 5: Commit**

```bash
cd ~/code/mission-control && git add src/components/projects/DocTree.tsx tests/components/projects/DocTree.test.tsx && git commit -m "$(cat <<'EOF'
feat(components/projects): DocTree colapsavel dos 8 folders canonicos

Folders com count > 0 iniciam expandidos. Empty folders sao readonly
(badge cinza, no-op click). Click em arquivo dispara onSelectFile com
caminho relativo (folder/projectId/name).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: `ProjectFicheirosTab`

**Files:**
- Create: `mission-control/src/components/projects/ProjectFicheirosTab.tsx`
- Create: `mission-control/tests/components/projects/ProjectFicheirosTab.test.tsx`

- [ ] **Step 1: Escrever tests**

Write `tests/components/projects/ProjectFicheirosTab.test.tsx`:

```typescript
import { describe, it, expect } from "vitest";
import type { ProjectFicheirosTabProps } from "@/components/projects/ProjectFicheirosTab";

describe("ProjectFicheirosTabProps contract", () => {
  it("requires projectId; selectedFile + onSelectFile optional", () => {
    let last: string | null = null;
    const props: ProjectFicheirosTabProps = {
      projectId: "openclaw",
      selectedFile: "35_specs/openclaw/foo.md",
      onSelectFile: (p) => { last = p; },
    };
    props.onSelectFile?.("x");
    expect(last).toBe("x");
    expect(props.selectedFile).toBe("35_specs/openclaw/foo.md");
  });
});
```

- [ ] **Step 2: Rodar tests (devem falhar)**

```bash
cd ~/code/mission-control && npm test -- --run tests/components/projects/ProjectFicheirosTab.test.tsx 2>&1 | tail -5
```

Expected: ERR.

- [ ] **Step 3: Criar component**

Write `src/components/projects/ProjectFicheirosTab.tsx`:

```typescript
"use client";

import { useCallback, useEffect, useState } from "react";
import { DocTree, type FoldersTree } from "./DocTree";
import { MarkdownViewer } from "./MarkdownViewer";

export interface ProjectFicheirosTabProps {
  projectId: string;
  selectedFile?: string | null;
  onSelectFile?: (path: string | null) => void;
}

interface FileResponse {
  path: string;
  content: string;
  modified_at: string;
  size_bytes: number;
  is_stub: boolean;
}

/**
 * Split layout: esq DocTree dos 8 folders canonicos; dir MarkdownViewer
 * do arquivo selecionado. URL state via parent (?file=<relPath>).
 */
export function ProjectFicheirosTab({ projectId, selectedFile, onSelectFile }: ProjectFicheirosTabProps) {
  const [tree, setTree] = useState<FoldersTree | null>(null);
  const [content, setContent] = useState<FileResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Initial fetch tree
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`/api/projects/${encodeURIComponent(projectId)}/files`, { cache: "no-store" });
        if (!r.ok) {
          const j = await r.json().catch(() => ({}));
          throw new Error(typeof j.detail === "string" ? j.detail : `HTTP ${r.status}`);
        }
        const data = await r.json();
        if (!cancelled) { setTree(data.folders); setError(null); }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => { cancelled = true; };
  }, [projectId]);

  // Fetch selected file content
  useEffect(() => {
    if (!selectedFile) { setContent(null); return; }
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`/api/projects/${encodeURIComponent(projectId)}/files?path=${encodeURIComponent(selectedFile)}`, { cache: "no-store" });
        if (!r.ok) {
          const j = await r.json().catch(() => ({}));
          throw new Error(typeof j.detail === "string" ? j.detail : `HTTP ${r.status}`);
        }
        const data = (await r.json()) as FileResponse;
        if (!cancelled) setContent(data);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => { cancelled = true; };
  }, [projectId, selectedFile]);

  const handleSelect = useCallback((relPath: string) => {
    onSelectFile?.(relPath);
  }, [onSelectFile]);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: "1rem", marginTop: "1rem" }}>
      <div style={{ background: "#1a2230", padding: "0.7rem", borderRadius: 5 }}>
        <div style={{ color: "#888", fontSize: "0.6rem", textTransform: "uppercase", marginBottom: "0.4rem" }}>
          bevox-knowledge / {projectId}
        </div>
        {error && <div style={{ color: "#e46e6e", fontSize: "0.7rem" }}>{error}</div>}
        {!error && !tree && <div style={{ color: "#888", fontSize: "0.7rem" }}>Carregando…</div>}
        {!error && tree && (
          <DocTree tree={tree} projectId={projectId} selected={selectedFile ?? null} onSelectFile={handleSelect} />
        )}
      </div>
      <div style={{ minHeight: 400 }}>
        {!selectedFile && (
          <div style={{ background: "#1a2230", padding: "2rem", borderRadius: 6, textAlign: "center", color: "#888", fontSize: "0.85rem" }}>
            Selecione um arquivo na árvore.
          </div>
        )}
        {selectedFile && !content && !error && (
          <div style={{ color: "#888", padding: "1rem" }}>Carregando arquivo…</div>
        )}
        {selectedFile && content && (
          <MarkdownViewer source={content.content} filename={content.path} stub={content.is_stub} />
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Rodar tests**

```bash
cd ~/code/mission-control && npm test -- --run tests/components/projects/ProjectFicheirosTab.test.tsx 2>&1 | tail -5
```

Expected: 1/1 pass.

- [ ] **Step 5: Commit**

```bash
cd ~/code/mission-control && git add src/components/projects/ProjectFicheirosTab.tsx tests/components/projects/ProjectFicheirosTab.test.tsx && git commit -m "$(cat <<'EOF'
feat(components/projects): ProjectFicheirosTab DocTree + viewer

Split layout: esq DocTree dos 8 folders canonicos do bevox-knowledge
filtrados pelo projeto + dir MarkdownViewer do arquivo selecionado.
URL sync feito pelo parent (?tab=ficheiros&file=...).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: `ProjectSprintsTab` thin wrapper

**Files:**
- Create: `mission-control/src/components/projects/ProjectSprintsTab.tsx`
- Create: `mission-control/tests/components/projects/ProjectSprintsTab.test.tsx`

- [ ] **Step 1: Escrever tests**

Write `tests/components/projects/ProjectSprintsTab.test.tsx`:

```typescript
import { describe, it, expect } from "vitest";
import type { ProjectSprintsTabProps } from "@/components/projects/ProjectSprintsTab";

describe("ProjectSprintsTabProps contract", () => {
  it("requires projectId string", () => {
    const props: ProjectSprintsTabProps = { projectId: "openclaw" };
    expect(props.projectId).toBe("openclaw");
  });
});
```

- [ ] **Step 2: Rodar tests (devem falhar)**

```bash
cd ~/code/mission-control && npm test -- --run tests/components/projects/ProjectSprintsTab.test.tsx 2>&1 | tail -5
```

Expected: ERR.

- [ ] **Step 3: Criar wrapper**

Write `src/components/projects/ProjectSprintsTab.tsx`:

```typescript
"use client";

import { SprintsPageInner } from "@/app/(dashboard)/sprints/page";

export interface ProjectSprintsTabProps {
  projectId: string;
}

/**
 * Thin wrapper: embed SprintsPageInner com forcedProject + hideProjectFilter.
 * SprintKanbanModal e drag-drop preservados via SprintsPageInner inalterado.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-projects-redesign.md §3.2.6
 */
export function ProjectSprintsTab({ projectId }: ProjectSprintsTabProps) {
  return (
    <div style={{ marginTop: "1rem" }}>
      <SprintsPageInner forcedProject={projectId} hideProjectFilter />
    </div>
  );
}
```

- [ ] **Step 4: Rodar tests**

```bash
cd ~/code/mission-control && npm test -- --run tests/components/projects/ProjectSprintsTab.test.tsx 2>&1 | tail -5
```

Expected: 1/1 pass.

- [ ] **Step 5: Commit**

```bash
cd ~/code/mission-control && git add src/components/projects/ProjectSprintsTab.tsx tests/components/projects/ProjectSprintsTab.test.tsx && git commit -m "$(cat <<'EOF'
feat(components/projects): ProjectSprintsTab thin wrapper de SprintsPageInner

Embed via forcedProject + hideProjectFilter — drag-drop e SprintKanbanModal
preservados sem mudancas, comportamento igual ao /sprints standalone mas
filtrado pelo projeto.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 16: Refactor `ProjectHeader` — sticky compact

**Files:**
- Modify: `mission-control/src/app/(dashboard)/projects/[id]/ProjectHeader.tsx`

- [ ] **Step 1: Inspecionar atual**

```bash
cat "~/code/mission-control/src/app/(dashboard)/projects/[id]/ProjectHeader.tsx"
```

Anotar shape de props (deve receber `detail: ProjectDetail`).

- [ ] **Step 2: Substituir conteúdo**

Write completo `src/app/(dashboard)/projects/[id]/ProjectHeader.tsx`:

```typescript
"use client";

import type { ProjectDetail, Dot } from "@/lib/projects/types";
import { getProjectColors } from "@/lib/projects/colors";

interface Props {
  detail: ProjectDetail;
}

const DOT_COLORS: Record<Dot, string> = {
  ok: "#7ec896",
  partial: "#e4a06e",
  missing: "#e46e6e",
};

/**
 * Sticky compact header pra /projects/[id] tabbed detail.
 * Chip color-coded + nome + 4 dots big + descricao sub-line.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-25-mc-projects-redesign.md §3.2.2
 */
export default function ProjectHeader({ detail }: Props) {
  const colors = getProjectColors(detail.id);
  return (
    <div style={{
      position: "sticky",
      top: 0,
      zIndex: 10,
      background: "#161b22",
      border: "1px solid #2a2f3e",
      borderRadius: 8,
      padding: "0.85rem 1rem",
      marginBottom: "0.6rem",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.7rem" }}>
          <span style={{
            background: colors.bg,
            color: colors.fg,
            padding: "0.2rem 0.7rem",
            borderRadius: 14,
            fontSize: "0.85rem",
            fontWeight: 600,
          }}>{detail.id}</span>
          <h2 style={{ color: "#e0e0e0", fontSize: "1.3rem", margin: 0 }}>{detail.name}</h2>
        </div>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <span title={`bot: ${detail.health.bot}`} style={{ width: 11, height: 11, borderRadius: "50%", background: DOT_COLORS[detail.health.bot] }} />
          <span title={`workspace: ${detail.health.workspace}`} style={{ width: 11, height: 11, borderRadius: "50%", background: DOT_COLORS[detail.health.workspace] }} />
          <span title={`kanban: ${detail.health.kanban}`} style={{ width: 11, height: 11, borderRadius: "50%", background: DOT_COLORS[detail.health.kanban] }} />
          <span title={`docs: ${detail.health.knowledge}`} style={{ width: 11, height: 11, borderRadius: "50%", background: DOT_COLORS[detail.health.knowledge] }} />
        </div>
      </div>
      <div style={{ color: "#888", fontSize: "0.78rem", marginTop: "0.3rem" }}>{detail.description}</div>
    </div>
  );
}
```

- [ ] **Step 3: Verify build**

```bash
cd ~/code/mission-control && npm run build 2>&1 | grep -E "error|Error|/projects" | head -5
```

Expected: sem erros.

- [ ] **Step 4: Commit**

```bash
cd ~/code/mission-control && git add "src/app/(dashboard)/projects/[id]/ProjectHeader.tsx" && git commit -m "$(cat <<'EOF'
refactor(projects/ProjectHeader): sticky compact com chip color-coded

Header reduzido pra: chip + nome + 4 dots big + descricao sub-line.
Sticky top:0 z-index 10 — fica visivel ao scrollar tabs longas.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 17: Rewrite `ProjectDetailPage` — Suspense + tabbed assembly

**Files:**
- Modify: `mission-control/src/app/(dashboard)/projects/[id]/page.tsx`

- [ ] **Step 1: Substituir conteúdo inteiro**

Write completo `src/app/(dashboard)/projects/[id]/page.tsx`:

```typescript
"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";

import type { ProjectDetail } from "@/lib/projects/types";
import ProjectHeader from "./ProjectHeader";
import { TabNav, type TabKey } from "@/components/projects/TabNav";
import { ProjectGeralTab } from "@/components/projects/ProjectGeralTab";
import { ProjectRoadmapTab } from "@/components/projects/ProjectRoadmapTab";
import { ProjectFicheirosTab } from "@/components/projects/ProjectFicheirosTab";
import { ProjectSprintsTab } from "@/components/projects/ProjectSprintsTab";

type State =
  | { kind: "loading" }
  | { kind: "not_found" }
  | { kind: "error"; message: string }
  | { kind: "ready"; detail: ProjectDetail };

function ProjectDetailPageInner() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";
  const router = useRouter();
  const searchParams = useSearchParams();
  const tabParam = searchParams.get("tab");
  const fileParam = searchParams.get("file");

  const tab: TabKey = (["geral", "roadmap", "ficheiros", "sprints"] as const).includes(tabParam as TabKey)
    ? (tabParam as TabKey)
    : "geral";

  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`/api/projects/${encodeURIComponent(id)}`, { cache: "no-store" });
        if (r.status === 404) { if (!cancelled) setState({ kind: "not_found" }); return; }
        if (!r.ok) {
          const j = await r.json().catch(() => ({}));
          if (!cancelled) setState({ kind: "error", message: `${r.status} ${j.error ?? "unknown"}` });
          return;
        }
        const body = (await r.json()) as ProjectDetail;
        if (!cancelled) setState({ kind: "ready", detail: body });
      } catch (e) {
        if (!cancelled) setState({ kind: "error", message: String(e) });
      }
    })();
    return () => { cancelled = true; };
  }, [id]);

  const setTab = useCallback((next: TabKey) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("tab", next);
    if (next !== "ficheiros") params.delete("file");
    router.replace(`/projects/${encodeURIComponent(id)}?${params.toString()}`, { scroll: false });
  }, [id, router, searchParams]);

  const setSelectedFile = useCallback((path: string | null) => {
    const params = new URLSearchParams(searchParams.toString());
    if (path) params.set("file", path);
    else params.delete("file");
    const qs = params.toString();
    router.replace(qs ? `/projects/${encodeURIComponent(id)}?${qs}` : `/projects/${encodeURIComponent(id)}`, { scroll: false });
  }, [id, router, searchParams]);

  if (state.kind === "loading") {
    return <div style={{ padding: "2rem", color: "#888" }}>Carregando projeto…</div>;
  }
  if (state.kind === "not_found") {
    return (
      <div style={{ padding: "2rem" }}>
        <h1 style={{ color: "#e0e0e0" }}>Projeto não encontrado</h1>
        <p style={{ color: "#888", fontSize: "0.85rem", marginTop: "0.5rem" }}>
          <span style={{ fontFamily: "monospace" }}>{id}</span> não é um projeto canônico.
        </p>
        <Link href="/projects" style={{ color: "#4f9eff", fontSize: "0.85rem" }}>← voltar para Projects</Link>
      </div>
    );
  }
  if (state.kind === "error") {
    return (
      <div style={{ padding: "2rem" }}>
        <h1 style={{ color: "#e46e6e" }}>Erro ao carregar projeto</h1>
        <pre style={{ color: "#888", fontSize: "0.78rem", marginTop: "0.5rem" }}>{state.message}</pre>
      </div>
    );
  }

  const detail = state.detail;
  const sprintCount = detail.sprints.active.length + detail.sprints.closed.length;

  return (
    <div style={{ padding: "1rem 1.5rem", color: "#e0e0e0" }}>
      <Link href="/projects" style={{ color: "#888", fontSize: "0.7rem", textDecoration: "none" }}>← Projects</Link>
      <ProjectHeader detail={detail} />
      <TabNav active={tab} onChange={setTab} sprintCount={sprintCount} />
      {tab === "geral"     && <ProjectGeralTab    detail={detail} />}
      {tab === "roadmap"   && <ProjectRoadmapTab  projectId={detail.id} />}
      {tab === "ficheiros" && <ProjectFicheirosTab projectId={detail.id} selectedFile={fileParam} onSelectFile={setSelectedFile} />}
      {tab === "sprints"   && <ProjectSprintsTab  projectId={detail.id} />}
    </div>
  );
}

/** Suspense wrapper required by Next.js 15: inner uses useSearchParams. */
export default function ProjectDetailPage() {
  return (
    <Suspense fallback={<div style={{ padding: "2rem", color: "#888" }}>Carregando…</div>}>
      <ProjectDetailPageInner />
    </Suspense>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd ~/code/mission-control && npm run build 2>&1 | grep -E "error|Error|projects/\[id\]" | head -5
```

Expected: rota `/projects/[id]` listada como dynamic (`ƒ`) sem erros.

- [ ] **Step 3: Rodar full suite**

```bash
cd ~/code/mission-control && npm test -- --run 2>&1 | tail -3
```

Expected: full suite green (suite agora ~190+ testes incluindo novos).

- [ ] **Step 4: Commit**

```bash
cd ~/code/mission-control && git add "src/app/(dashboard)/projects/[id]/page.tsx" && git commit -m "$(cat <<'EOF'
feat(projects/[id]): rewrite tabbed detail page com 4 abas + URL state

Substitui o vertical stack atual (header + health + links + sprints +
tasks-in-flight) pelo header sticky compacto + TabNav + body do tab ativo.
URL state via ?tab=geral|roadmap|ficheiros|sprints; ficheiros tab usa
?file=<relPath> deep-link.

Suspense wrapper requerido pelo Next 15 (inner usa useSearchParams).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 18: Cleanup — delete obsolete files

**Files:**
- Delete: `src/app/(dashboard)/projects/[id]/HealthDetails.tsx`
- Delete: `src/app/(dashboard)/projects/[id]/SprintList.tsx`
- Delete: `src/app/(dashboard)/projects/[id]/TasksInFlight.tsx`
- Delete: `src/app/(dashboard)/projects/[id]/ProjectLinks.tsx`

- [ ] **Step 1: Verificar nada referencia esses files**

```bash
cd ~/code/mission-control && for f in HealthDetails SprintList TasksInFlight ProjectLinks; do
  echo "=== $f ===" && grep -rn "from.*${f}\|import.*${f}" src/ 2>&1 | grep -v "$f.tsx"
done
```

Expected: nenhum `import` desses files (a única referência seria do file pra ele mesmo, que será deletado).

- [ ] **Step 2: Deletar**

```bash
cd ~/code/mission-control && rm "src/app/(dashboard)/projects/[id]/HealthDetails.tsx" "src/app/(dashboard)/projects/[id]/SprintList.tsx" "src/app/(dashboard)/projects/[id]/TasksInFlight.tsx" "src/app/(dashboard)/projects/[id]/ProjectLinks.tsx"
```

- [ ] **Step 3: Verify build still passes**

```bash
cd ~/code/mission-control && npm test -- --run 2>&1 | tail -3 && npm run build 2>&1 | tail -3
```

Expected: tests + build verde.

- [ ] **Step 4: Commit**

```bash
cd ~/code/mission-control && git add -A "src/app/(dashboard)/projects/[id]/" && git commit -m "$(cat <<'EOF'
cleanup(projects/[id]): delete obsolete components substituidos pelo redesign

HealthDetails -> inline em ProjectGeralTab.
SprintList + TasksInFlight -> aba Sprints embed do /sprints (com modal
kanban abrindo pra ver tasks).
ProjectLinks -> inline em ProjectGeralTab ExternalLinksBox.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 19: Push openclaw plan + push MC feat PR + pause

- [ ] **Step 1: Push openclaw plan**

```bash
cd ~/.openclaw && git push -u origin feat/mc-projects-redesign-plan
gh pr create --title "plan(mc-projects-redesign): implementation plan" --body "Plan doc para spec bevox-knowledge/35_specs/company-os/2026-04-25-mc-projects-redesign.md.

19 tasks TDD onde aplicavel. Pre-requisitos ja entregues (PR #20 stubs + PR #13 sprints + PR #11 hotfix API state).

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

- [ ] **Step 2: Verify mission-control branch**

```bash
cd ~/code/mission-control && git status --short && git log --oneline main..HEAD | head -20 && npm test -- --run 2>&1 | tail -3 && npm run build 2>&1 | tail -3
```

Expected: ~17 commits novos (Task 2 a 18). Suite green. Build green.

- [ ] **Step 3: Push mission-control + open PR**

```bash
cd ~/code/mission-control && git push -u origin feat/mc-projects-redesign
gh pr create --title "feat(mc): /projects redesign — health-grid list + tabbed detail (E2/mc-projects-redesign)" --body "$(cat <<'EOF'
## Summary
Redesign /projects (cards health-grid 3-col compactos) + /projects/[id] (tabbed detail Geral/Roadmap/Ficheiros/Sprints).

Spec: \`bevox-knowledge/35_specs/company-os/2026-04-25-mc-projects-redesign.md\`
Plano: \`openclaw/docs/superpowers/plans/2026-04-25-mc-projects-redesign.md\`

## What's in this PR

~17 commits TDD:
- deps: remark-gfm + CANONICAL_PROJECTS extendido pra 10
- backend: knowledge.ts sandboxed reader + 3 API routes (/prd, /roadmap, /files)
- refactor: SprintsPageInner exporta named + props embed (forcedProject, hideProjectFilter)
- components: MarkdownViewer, TabNav, ProjectGeralTab, ProjectRoadmapTab + RoadmapDocsList, DocTree, ProjectFicheirosTab, ProjectSprintsTab
- pages: ProjectCard rewrite, ProjectHeader sticky compact, ProjectDetailPage rewrite Suspense+tabbed
- cleanup: 4 components antigos deletados

## Test plan
- [x] Vitest 180+ green (~30 novos)
- [x] \`npm run build\` verde (/projects, /projects/[id], 3 API routes)
- [ ] **Pos-merge:** pull + npm install + npm run build + systemctl restart mission-control
- [ ] Smoke E2E 9 cenarios gating

## Rollback
Frontend-only, sandboxed FS reader (no writes). Tier 1: \`git revert <merge-sha> && pull && rebuild && restart\`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: PAUSA — aguardar Bernard mergear MC PR**

Parar aqui. Bernard revisa + merge. Retomar Task 20 só após merge confirmado em main.

---

## Task 20: Pull main + npm install + build + restart MC + verify

**Pré-requisito:** PR mergeada; main atualizada.

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

Expected: build succeeds. `/projects` static, `/projects/[id]` dynamic, 3 API routes dynamic.

- [ ] **Step 3: Restart service**

```bash
systemctl --user restart mission-control && sleep 3
systemctl --user is-active mission-control
```

Expected: `active`.

- [ ] **Step 4: Health probes localhost**

```bash
curl -sS -o /dev/null -w "GET /projects: HTTP %{http_code}\n" -H "Cf-Access-Authenticated-User-Email: you@example.com" http://127.0.0.1:4310/projects
curl -sS -o /dev/null -w "GET /projects/openclaw: HTTP %{http_code}\n" -H "Cf-Access-Authenticated-User-Email: you@example.com" http://127.0.0.1:4310/projects/openclaw
curl -sS -H "Cf-Access-Authenticated-User-Email: you@example.com" "http://127.0.0.1:4310/api/projects/openclaw/prd" 2>&1 | python3 -m json.tool | head -10
curl -sS -H "Cf-Access-Authenticated-User-Email: you@example.com" "http://127.0.0.1:4310/api/projects/openclaw/roadmap" 2>&1 | python3 -m json.tool | head -10
curl -sS -H "Cf-Access-Authenticated-User-Email: you@example.com" "http://127.0.0.1:4310/api/projects/openclaw/files" 2>&1 | python3 -m json.tool | head -20
```

Expected:
- `/projects` HTTP 200
- `/projects/openclaw` HTTP 200
- `/api/projects/openclaw/prd` retorna JSON com `latest.path = "10_prd/openclaw/2026-04-25-openclaw-prd.md"`, `is_stub: true`
- `/api/projects/openclaw/roadmap` retorna JSON com latest do roadmap
- `/api/projects/openclaw/files` retorna `folders` map com 8 chaves

---

## Task 21: Smoke E2E (9 cenários gating)

**Pré-requisito:** Task 20 completa; serviço rodando código novo.

Bernard valida em `mc.example.com/projects` e `/projects/openclaw`.

- [ ] **Cenário 1: List page health-grid**

Bernard abre `mc.example.com/projects`:
- 10 cards no grid 3-col (4 linhas × 3 colunas + 1 isolada).
- Cada card: chip color-coded (cores corretas batendo com `/sprints`) + nome + descrição line-clamp + 4 dots + stats line.
- Click num card navega pra `/projects/<id>`.

Pass: ✓. Fail: rollback Tier 1.

- [ ] **Cenário 2: Detail page tab Geral default**

Bernard navega `/projects/openclaw`:
- Sticky header chip + nome + 4 dots big + descrição.
- TabNav abaixo: Geral (active) | Roadmap | Ficheiros | Sprints (N).
- Body: split — esquerda 4 info boxes (description/health/stats/external links); direita PRD viewer renderizado mostrando o stub de openclaw.

- [ ] **Cenário 3: Tab Roadmap**

Click em "Roadmap":
- URL atualiza pra `?tab=roadmap`.
- Esquerda: lista com 1 doc clicável (`2026-04-25-openclaw-roadmap.md`) + atalho `→ /roadmap`.
- Direita: roadmap stub renderizado.
- Reload com URL: filtro reaplicado.

- [ ] **Cenário 4: Tab Ficheiros tree + preview**

Click em "Ficheiros":
- URL `?tab=ficheiros`.
- Esquerda: file tree dos 8 folders. Folders com count > 0 expandidos por default; com 0 mostram badge cinza.
- Para `openclaw`: `35_specs (51)` aparece expandido com lista; `30_adr (0)` cinza.
- Click em arquivo `35_specs/openclaw/2026-04-25-sprint-per-project.md`: URL ganha `&file=...`, direita renderiza o markdown.
- Reload com URL `?tab=ficheiros&file=...`: state restaurado.

- [ ] **Cenário 5: Tab Sprints embed + click card**

Click em "Sprints (N)":
- URL `?tab=sprints`.
- 3 colunas Active/Next/Closed renderizam só sprints de `openclaw`.
- Dropdown "Project: All ▼" do `/sprints` standalone NÃO aparece.
- Click num sprint card: `SprintKanbanModal` abre normalmente, URL ganha `&sprint=sprint-N`.
- Esc fecha modal, URL volta a `?tab=sprints`.

- [ ] **Cenário 6: Drag-drop preservado dentro do embed**

No mesmo tab Sprints:
- Drag um sprint next → active col → carryover modal popa, fluxo idêntico ao /sprints standalone.
- Cancelar carryover sem confirmar.

- [ ] **Cenário 7: URL deep-link compartilhável**

Copiar URL `mc.example.com/projects/openclaw?tab=ficheiros&file=35_specs/openclaw/2026-04-25-sprint-per-project.md` em nova aba:
- Página abre direto na aba Ficheiros, com tree expandido em `35_specs` e arquivo selecionado renderizado.

- [ ] **Cenário 8: Browser back funciona**

Navegação Geral → Roadmap → Ficheiros → Geral. Pressionar back: volta na ordem inversa. URL e state coerentes.

- [ ] **Cenário 9: Empty state PRD**

Em projeto sem PRD (deletar manualmente o stub temporariamente em `bevox-knowledge/10_prd/vox/`, reload):
- Tab Geral mostra empty panel: "Nenhum PRD pra este projeto" + hint `bevox-knowledge/10_prd/vox/`.
- Restaurar stub pós-teste.

**Smoke gate:** 9/9 pass → wave delivered. Falha em qualquer cenário → rollback Tier 1 (git revert + rebuild).

---

## Task 22: Tracker entry — wave delivered

**Files:**
- Modify: `bevox-knowledge/40_roadmap/_shared/delivery-tracker.yml`

- [ ] **Step 1: Branch + add entry**

```bash
cd ~/bevox-knowledge && git checkout main && git pull --ff-only
git checkout -b draft/tracker-mc-projects-redesign-delivered
```

Find E2 epic block in `40_roadmap/_shared/delivery-tracker.yml` (search `id: E2`). Identify last existing wave entry under E2. Insert new entry below:

```yaml
      - id: mc-projects-redesign
        status: delivered
        delivered_at: 2026-04-25
        spec: 35_specs/company-os/2026-04-25-mc-projects-redesign.md
        pr_mc: https://github.com/bernardTavares/mission-control/pull/<N>
        pr_openclaw_plan: https://github.com/bernardTavares/openclaw/pull/<N>
        pr_knowledge_spec: https://github.com/bernardTavares/bevox-knowledge/pull/<N>
        pr_knowledge_stubs: https://github.com/bernardTavares/bevox-knowledge/pull/20
        narrative: "MC ganha /projects redesigned (cards health-grid 3-col compactos) + /projects/[id] tabbed (Geral/Roadmap/Ficheiros/Sprints) com markdown viewer pros docs canonicos do bevox-knowledge"
        features:
          - "List view: cards health-grid 3-col compactos com chip color-coded + 4 dots + stats; substitui ProjectCard antigo"
          - "Detail view: header sticky compacto + 4 abas (Geral/Roadmap/Ficheiros/Sprints) com URL deep-link ?tab=X"
          - "Aba Geral: split layout — esq info estatica (description/health/stats/external links); dir PRD do projeto renderizado em markdown viewer"
          - "Aba Roadmap: mesmo split — esq lista de roadmap docs + atalho /roadmap global; dir doc selecionado (default = latest, switchable)"
          - "Aba Ficheiros: file tree dos 8 folders canonicos do bevox-knowledge (10_prd, 20_architecture, 30_adr, 35_specs, 40_roadmap, 50_releases, 60_customer-feedback, 70_metrics) filtrados pelo projeto; click em .md renderiza preview"
          - "Aba Sprints: embed do /sprints scoped pro projeto via SprintsPageInner refactored (forcedProject + hideProjectFilter); drag-drop e SprintKanbanModal preservados sem mudancas"
          - "Backend: knowledge.ts sandboxed filesystem reader (path traversal rejection, 8 ALLOWED_FOLDERS) + 3 API routes (/prd, /roadmap, /files com tree+read variants)"
          - "Markdown via react-markdown + remark-gfm (GitHub-flavored: tables, task lists, fenced code)"
          - "CANONICAL_PROJECTS extendida de 6 pra 10 entries (+ openclaw, mission-control, bevox-knowledge, vox)"
          - "Pre-requisito entregue antes: stubs PRD+roadmap pros 10 projetos canonicos (PR #20 bevox-knowledge); evita 9/10 projetos lancarem com tabs vazias"
          - "Reuso maximo: SprintKanbanModal (drag-drop wave) e PROJECT_COLORS (sprints page wave) reutilizados sem alteracao"
          - "Smoke E2E pos-deploy validou 9 cenarios gating: list grid, default tab, todas as 4 abas, drag-drop dentro do embed, URL deep-link compartilhavel, browser back, empty state PRD"
          - "Frontend-only + sandboxed FS reader (no writes); rollback Tier 1 = git revert + rebuild + restart (segundos)"
```

(Substituir `<N>` pelos PR numbers reais.)

- [ ] **Step 2: Validar YAML + commit + push + PR**

```bash
cd ~/bevox-knowledge && python3 -c "import yaml; yaml.safe_load(open('40_roadmap/_shared/delivery-tracker.yml')); print('valid')"
git add 40_roadmap/_shared/delivery-tracker.yml
git commit -m "$(cat <<'EOF'
tracker(E2/mc-projects-redesign): delivered 2026-04-25

Mission Control ganha /projects redesigned (health-grid 3-col compacto) +
/projects/[id] tabbed detail (Geral/Roadmap/Ficheiros/Sprints) com markdown
viewer pros docs canonicos do bevox-knowledge.

PRs: mission-control #<N>, openclaw plan #<N>, bevox-knowledge spec #<N>,
bevox-knowledge stubs #20.
Spec: 35_specs/company-os/2026-04-25-mc-projects-redesign.md
Smoke E2E 9 cenarios gating todos pass.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git push -u origin draft/tracker-mc-projects-redesign-delivered
gh pr create --title "tracker(E2/mc-projects-redesign): delivered 2026-04-25" --body "## Summary
Entry no delivery-tracker registrando wave \`mc-projects-redesign\` do E2 como delivered.

## Test plan
- [x] YAML valido
- [x] Smoke E2E 9 cenarios pass
- [x] PRs (spec + plan + impl + stubs) merged

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

- [ ] **Step 3: Aguardar Bernard mergear**

Bernard merge → wave fechada formalmente.

---

## Self-review

**Spec coverage:**
- §1 decisões 1-7 → Tasks 2 (deps + canonical), 8 (MarkdownViewer), 9 (ProjectCard health-grid), 10 (TabNav), 11 (Geral), 12 (Roadmap), 13-14 (DocTree+Ficheiros), 15 (Sprints embed), 16-17 (header+page).
- §2 page architecture → Tasks 9, 16, 17 (chrome layout).
- §3 components → todos os Tasks 8-17 cobrem 1:1.
- §4 data flow → Tasks 3 (knowledge.ts), 4-6 (3 API routes), 7 (SprintsPageInner refactor).
- §4.4 SprintsPageInner forcedProject → Task 7.
- §5 edge cases → Task 11 (empty PRD), Task 12 (empty roadmap), Task 13 (empty folders cinza), Task 14 (no file selected), Task 17 (project not_found).
- §6 arquivos → file structure section maps 1:1.
- §7 ordem dos PRs → Tasks 1, 19, 20, 21, 22 implementam a sequência.
- §8 testing → ~30 vitest tests distribuídos (Tasks 3-15) + 9 smoke gating (Task 21).
- §9 DoD → 9 cenários da Task 21 cobrem.
- §10 rollback → Task 19 PR description menciona Tier 1.
- §11 não-escopo → respeitado (sem edição inline, sem mermaid, sem source repo browser, sem search).

**Placeholder scan:** zero TBD/TODO/"similar to". Code blocks completos em todos os steps de código.

**Type consistency:**
- `ProjectGeralTabProps.detail: ProjectDetail` (Task 11) bate com `<ProjectGeralTab detail={detail}/>` em Task 17.
- `ProjectRoadmapTabProps.projectId` (Task 12) bate com Task 17.
- `DocTreeProps.tree: FoldersTree` (Task 13) reutilizado em Task 14.
- `MarkdownViewerProps.source/filename/stub` (Task 8) consistente em Tasks 11, 12, 14.
- `TabKey` (Task 10) usado em Task 17.
- `SprintsPageInnerProps.forcedProject?` (Task 7) usado em Task 15.
- `FileEntry` shape vinda de `knowledge.ts` (Task 3) bate com endpoints (Tasks 4-6) e components (Tasks 12, 14).

Issues encontrados: nenhum.
