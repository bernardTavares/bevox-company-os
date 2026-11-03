# MC Projects Factory Wave 2 — Phase 3: Mission Control UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the Phase 2 capability in the Mission Control UI. Extend `NewProjectModal` to accept a PRD (textarea or `.md` upload). Extend `POST /api/projects` to forward the PRD to the factory CLI. Show a loading state while the persona LLM runs. Show a banner on the project page when persona generation is pending.

**Architecture:** UI passes PRD as multipart form data. The Next.js route writes the PRD to a temp file, invokes `openclaw project create <slug> --prd <tmpfile>`, and returns the factory's JSON result (including `persona_status`). UI navigates to `/projects/<slug>` and reads `persona_status` to decide whether to show the banner.

**Tech Stack:** Next.js 15 (app router), TypeScript, React, Tailwind, Vitest, Playwright (already in repo).

**Spec:** `bevox-knowledge/35_specs/openclaw/2026-04-28-mc-projects-factory-wave-2-vox-clone.md` §2.1, §3.1, §6 (Phase 3).

**Pre-requisites:**
- Phases 1 & 2 merged
- `mission-control` repo at `~/code/mission-control/`
- `ANTHROPIC_API_KEY` set in the env where the MC backend runs (via `.env.local` or systemd unit)

---

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `mission-control/src/components/projects/NewProjectModal.tsx` | MODIFY | Add PRD textarea + upload + loading state |
| `mission-control/src/app/api/projects/route.ts` | MODIFY | Accept multipart, write PRD to tmp, invoke factory with `--prd` |
| `mission-control/src/app/projects/[id]/page.tsx` (or layout) | MODIFY | Show "persona pending" banner |
| `mission-control/src/components/projects/PersonaPendingBanner.tsx` | CREATE | Banner component |
| `mission-control/tests/components/projects/NewProjectModal.test.tsx` | MODIFY | Cover new fields |
| `mission-control/tests/api/projects/create.test.ts` (or similar) | MODIFY | Cover PRD multipart path |

---

## Task 1: Setup branch + audit current files

- [ ] **Step 1: Branch**

```bash
cd ~/code/mission-control
git checkout main && git pull
git checkout -b feat/mc-projects-factory-w2-phase-3-ui
```

- [ ] **Step 2: Read current modal & route**

```bash
sed -n '1,200p' src/components/projects/NewProjectModal.tsx
sed -n '1,200p' src/app/api/projects/route.ts
```

Note exact prop names, state hooks, and the way the route calls `openclaw project create`. The patches below assume conventional shape — adjust path/var names to match.

- [ ] **Step 3: Confirm CLI works from MC**

```bash
~/.openclaw/kanban-tasks/cli.sh project create --help | head -20
```

Expected: lists `--prd`, `--domain` flags (added in Phase 2). If absent, Phase 2 is not merged in this checkout.

---

## Task 2: Extend NewProjectModal — add PRD field

**Files:**
- Modify: `mission-control/src/components/projects/NewProjectModal.tsx`

The modal today has fields like `name`, `slug`, `description`, `domain` (some may already exist). Add a PRD field (textarea + file upload, mutually exclusive: file wins).

- [ ] **Step 1: Add state + handlers**

In `NewProjectModal.tsx`, inside the component, add:

```tsx
const [prdText, setPrdText] = useState("");
const [prdFile, setPrdFile] = useState<File | null>(null);
const [submitting, setSubmitting] = useState(false);
const [submitStage, setSubmitStage] = useState<"idle" | "creating" | "persona">("idle");

function onPrdFileChange(e: React.ChangeEvent<HTMLInputElement>) {
  const f = e.target.files?.[0] ?? null;
  setPrdFile(f);
  if (f) setPrdText("");  // file takes precedence
}

const prdValid = (prdFile !== null) || (prdText.trim().length >= 200);
```

- [ ] **Step 2: Add PRD section in the modal JSX**

Inside the modal form, after the existing description/domain fields, add:

```tsx
<div className="space-y-2">
  <label className="text-sm font-medium">
    PRD do projeto <span className="text-red-500">*</span>
  </label>
  <p className="text-xs text-muted-foreground">
    Cole o PRD ou faça upload de um arquivo .md. Mínimo 200 caracteres.
    Será usado pra gerar a persona Vox-like dedicada ao projeto.
  </p>

  <textarea
    rows={10}
    placeholder="Cole o PRD aqui..."
    value={prdText}
    disabled={prdFile !== null || submitting}
    onChange={(e) => setPrdText(e.target.value)}
    className="w-full rounded-md border px-3 py-2 font-mono text-sm"
  />

  <div className="flex items-center gap-2 text-sm">
    <span className="text-muted-foreground">ou</span>
    <input
      type="file"
      accept=".md,text/markdown,text/plain"
      onChange={onPrdFileChange}
      disabled={submitting}
      className="text-sm"
    />
    {prdFile && (
      <button
        type="button"
        onClick={() => setPrdFile(null)}
        className="text-xs text-blue-600 hover:underline"
      >
        remover
      </button>
    )}
  </div>

  {!prdValid && (prdText.length > 0 || prdFile !== null) && (
    <p className="text-xs text-red-500">
      PRD precisa ter ≥200 chars ou um arquivo .md selecionado.
    </p>
  )}
</div>
```

- [ ] **Step 3: Update submit handler to send multipart**

Replace the existing submit handler with multipart POST:

```tsx
async function onSubmit() {
  if (!prdValid) return;
  setSubmitting(true);
  setSubmitStage("creating");

  const fd = new FormData();
  fd.append("name", name);
  if (slug) fd.append("slug", slug);
  fd.append("description", description);
  fd.append("domain", domain || "");
  if (prdFile) {
    fd.append("prd_file", prdFile);
  } else {
    fd.append("prd_text", prdText);
  }

  // Switch loading message after 4s — at this point step_4 (LLM) is running
  const t = setTimeout(() => setSubmitStage("persona"), 4000);

  try {
    const res = await fetch("/api/projects", { method: "POST", body: fd });
    clearTimeout(t);
    const json = await res.json();
    if (!res.ok || !json.success) {
      throw new Error(json.error_message ?? "create failed");
    }
    router.push(`/projects/${json.id}`);
  } catch (e: any) {
    setSubmitting(false);
    setSubmitStage("idle");
    setError(String(e.message ?? e));
  }
}
```

- [ ] **Step 4: Add loading state in submit button + body**

Replace the modal footer's submit button with:

```tsx
<button
  type="button"
  onClick={onSubmit}
  disabled={!prdValid || submitting}
  className="rounded-md bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
>
  {submitting ? (
    submitStage === "persona" ? "Forjando persona Vox..." : "Criando projeto..."
  ) : (
    "Criar projeto + agente"
  )}
</button>
```

- [ ] **Step 5: Type-check & lint**

```bash
cd ~/code/mission-control
npm run typecheck
npm run lint -- --fix src/components/projects/NewProjectModal.tsx
```

Expected: no errors.

---

## Task 3: Extend `POST /api/projects` route to accept PRD

**Files:**
- Modify: `mission-control/src/app/api/projects/route.ts`

- [ ] **Step 1: Update route to handle multipart**

Replace the body of `POST` with:

```ts
import { writeFile, mkdtemp, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { spawn } from "node:child_process";

export async function POST(req: Request) {
  const ct = req.headers.get("content-type") ?? "";
  if (!ct.includes("multipart/form-data")) {
    return Response.json(
      { success: false, error_message: "expected multipart/form-data" },
      { status: 400 },
    );
  }

  const fd = await req.formData();
  const name = String(fd.get("name") ?? "");
  const slug = String(fd.get("slug") ?? "");
  const description = String(fd.get("description") ?? "");
  const domain = String(fd.get("domain") ?? "");
  const prdFile = fd.get("prd_file");
  const prdText = String(fd.get("prd_text") ?? "");

  if (!name) {
    return Response.json(
      { success: false, error_message: "name is required" },
      { status: 400 },
    );
  }

  // Persist PRD to a tmp file
  let prdPath: string | null = null;
  let tmpDir: string | null = null;
  try {
    tmpDir = await mkdtemp(join(tmpdir(), "mc-prd-"));
    prdPath = join(tmpDir, "prd.md");
    if (prdFile instanceof File) {
      const buf = Buffer.from(await prdFile.arrayBuffer());
      await writeFile(prdPath, buf);
    } else if (prdText.trim().length >= 200) {
      await writeFile(prdPath, prdText, "utf-8");
    } else {
      return Response.json(
        { success: false, error_message: "PRD missing or too short" },
        { status: 400 },
      );
    }

    // Build CLI args
    const args = [
      "project", "create", name,
      "--description", description,
      "--domain", domain,
      "--prd", prdPath,
      "--json",
    ];
    if (slug) args.unshift("--id", slug);
    // (Above push --id ahead of `name`; rebuild more carefully:)
    const finalArgs = [
      "project", "create", name,
      ...(slug ? ["--id", slug] : []),
      "--description", description,
      "--domain", domain,
      "--prd", prdPath,
      "--json",
    ];

    const cli = process.env.OPENCLAW_CLI
      ?? "~/.openclaw/kanban-tasks/cli.sh";

    const result = await runCli(cli, finalArgs);
    return Response.json(result, { status: result.success ? 200 : 500 });
  } catch (e: any) {
    return Response.json(
      { success: false, error_message: String(e.message ?? e) },
      { status: 500 },
    );
  } finally {
    if (tmpDir) {
      await rm(tmpDir, { recursive: true, force: true }).catch(() => {});
    }
  }
}

function runCli(
  cli: string, args: string[],
): Promise<{ success: boolean; [k: string]: any }> {
  return new Promise((resolve, reject) => {
    const child = spawn(cli, args, {
      env: { ...process.env },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (d) => { stdout += d; });
    child.stderr.on("data", (d) => { stderr += d; });
    child.on("error", reject);
    child.on("close", (code) => {
      try {
        const parsed = JSON.parse(stdout);
        resolve(parsed);
      } catch {
        resolve({
          success: false,
          error_message: stderr.trim() || stdout.trim() || `exit ${code}`,
        });
      }
    });
  });
}
```

- [ ] **Step 2: Type-check**

```bash
npm run typecheck
```

Expected: clean.

---

## Task 4: Persona pending banner

**Files:**
- Create: `mission-control/src/components/projects/PersonaPendingBanner.tsx`
- Modify: project page (likely `mission-control/src/app/projects/[id]/page.tsx` or its layout)

- [ ] **Step 1: Create the banner component**

```tsx
// mission-control/src/components/projects/PersonaPendingBanner.tsx
"use client";

interface Props {
  slug: string;
}

export function PersonaPendingBanner({ slug }: Props) {
  return (
    <div className="rounded-md border-l-4 border-amber-500 bg-amber-50 p-3 text-sm">
      <div className="font-medium text-amber-900">
        Persona Vox ainda não foi gerada
      </div>
      <p className="mt-1 text-amber-800">
        A geração da persona LLM falhou ou foi adiada. Rode no terminal:
      </p>
      <pre className="mt-2 rounded bg-amber-100 px-2 py-1 font-mono text-xs">
        openclaw project regenerate-persona {slug}
      </pre>
    </div>
  );
}
```

- [ ] **Step 2: Detect persona pending in the project page**

In the project page (`src/app/projects/[id]/page.tsx`), after fetching the project metadata, check whether the persona is pending. The simplest signal is the existence of `~/.openclaw/workspace-<slug>/PERSONA_PENDING.md` — this requires a server action or API endpoint.

Add a helper in the existing project metadata API (probably `src/app/api/projects/[id]/route.ts`). In its handler, after building the response, add:

```ts
import { existsSync } from "node:fs";

// Inside GET handler, before returning:
const personaPendingPath =
  `~/.openclaw/workspace-${id}/PERSONA_PENDING.md`;
const personaPending = existsSync(personaPendingPath);

return Response.json({ ...meta, persona_pending: personaPending });
```

(Adjust path to match codebase env var conventions, e.g., `process.env.OPENCLAW_DIR ?? "~/.openclaw"`.)

Then in the page component:

```tsx
import { PersonaPendingBanner } from "@/components/projects/PersonaPendingBanner";

// Inside the JSX:
{project.persona_pending && <PersonaPendingBanner slug={project.id} />}
```

- [ ] **Step 3: Verify in dev**

```bash
cd ~/code/mission-control
npm run dev
```

Open `http://localhost:3000/projects/<some-existing-slug>`. If `PERSONA_PENDING.md` exists in that workspace, the banner shows. Test by manually creating/deleting that file and refreshing.

---

## Task 5: Update tests

**Files:**
- Modify: `mission-control/tests/components/projects/NewProjectModal.test.tsx`

- [ ] **Step 1: Add tests for new fields**

```tsx
it("disables submit until PRD has 200+ chars or file selected", async () => {
  render(<NewProjectModal open onClose={() => {}} />);
  const submit = screen.getByRole("button", { name: /criar projeto/i });
  expect(submit).toBeDisabled();

  // Fill name + slug + short PRD → still disabled
  fireEvent.change(screen.getByLabelText(/nome/i), { target: { value: "X" } });
  fireEvent.change(screen.getByPlaceholderText(/cole o prd/i),
                   { target: { value: "short" } });
  expect(submit).toBeDisabled();

  // Long PRD → enabled
  fireEvent.change(screen.getByPlaceholderText(/cole o prd/i),
                   { target: { value: "x".repeat(250) } });
  expect(submit).not.toBeDisabled();
});

it("posts multipart with prd_text or prd_file", async () => {
  const fetchMock = vi.spyOn(global, "fetch")
    .mockResolvedValue(new Response(
      JSON.stringify({ success: true, id: "x" }),
      { status: 200 }
    ));

  render(<NewProjectModal open onClose={() => {}} />);
  fireEvent.change(screen.getByLabelText(/nome/i), { target: { value: "X" } });
  fireEvent.change(screen.getByPlaceholderText(/cole o prd/i),
                   { target: { value: "x".repeat(250) } });
  fireEvent.click(screen.getByRole("button", { name: /criar projeto/i }));

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
  const [, init] = fetchMock.mock.calls[0];
  expect(init?.body).toBeInstanceOf(FormData);
  const fd = init!.body as FormData;
  expect(fd.get("prd_text")).toMatch(/^x{250}$/);
});
```

- [ ] **Step 2: Run tests**

```bash
cd ~/code/mission-control
npm test -- NewProjectModal
```

Expected: green.

---

## Task 6: Smoke test E2E (dev server + manual)

- [ ] **Step 1: Set ANTHROPIC_API_KEY in .env.local**

```bash
cd ~/code/mission-control
grep -q ANTHROPIC_API_KEY .env.local 2>/dev/null \
    || echo "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY" >> .env.local
cat .env.local | grep -v "^[A-Z_]*=$" | head -5
```

- [ ] **Step 2: Run dev server**

```bash
npm run dev &
DEV_PID=$!
sleep 4
```

- [ ] **Step 3: Manual creation via UI**

Open `http://localhost:3000/` in a browser. Click "+ New Project". Fill:
- Name: "Smoke W2 P3"
- Slug: smoke-w2-p3 (auto-derived OK)
- Description: "Phase 3 UI smoke"
- Domain: "Tech"
- PRD: paste a 300+ char PRD, e.g. the body from Task 10 of Phase 2 plan

Click "Criar projeto + agente". Watch:
- After ~3s, button text should switch to "Forjando persona Vox..."
- After ~10-15s, modal should close and navigate to `/projects/smoke-w2-p3`
- IDENTITY.md, SOUL.md should be populated

- [ ] **Step 4: Verify on filesystem**

```bash
cat ~/.openclaw/workspace-smoke-w2-p3/IDENTITY.md
ls ~/.openclaw/workspace-smoke-w2-p3/PERSONA_PENDING.md 2>/dev/null \
    && echo "FAIL: pending should not exist on success" \
    || echo "OK"
```

Expected: persona generated, no PERSONA_PENDING.md.

- [ ] **Step 5: Test pending banner**

Manually create a fake pending state:

```bash
echo "fake pending" > ~/.openclaw/workspace-smoke-w2-p3/PERSONA_PENDING.md
```

Refresh `http://localhost:3000/projects/smoke-w2-p3`. The banner should appear.

```bash
rm ~/.openclaw/workspace-smoke-w2-p3/PERSONA_PENDING.md
```

Refresh; banner should disappear.

- [ ] **Step 6: Cleanup**

```bash
~/.openclaw/kanban-tasks/cli.sh project remove smoke-w2-p3 --skip-github
kill $DEV_PID
```

---

## Task 7: Commit + open PR

- [ ] **Step 1: Stage**

```bash
cd ~/code/mission-control
git add src/components/projects/NewProjectModal.tsx \
        src/components/projects/PersonaPendingBanner.tsx \
        src/app/api/projects/route.ts \
        src/app/api/projects/[id]/route.ts \
        src/app/projects/[id]/page.tsx \
        tests/components/projects/NewProjectModal.test.tsx
git status
```

- [ ] **Step 2: Commit**

```bash
git commit -m "feat(projects): PRD input + persona pending banner

Phase 3 of mc-projects-factory wave-2. NewProjectModal accepts a PRD
(textarea ≥200 chars or .md upload). POST /api/projects forwards the
PRD to 'openclaw project create --prd <tmp>'. Project page shows
PersonaPendingBanner when ~/.openclaw/workspace-<slug>/PERSONA_PENDING.md
exists, with regenerate command shown."
```

- [ ] **Step 3: Push + PR**

```bash
git push -u origin feat/mc-projects-factory-w2-phase-3-ui
gh pr create --title "feat: PRD input + persona pending UI (Phase 3)" \
  --body "$(cat <<'EOF'
## Summary
- NewProjectModal: PRD textarea (≥200 chars) OR .md upload, mutually exclusive
- POST /api/projects: multipart, writes PRD to temp file, invokes factory CLI with --prd
- "Forjando persona Vox..." loading state after 4s
- PersonaPendingBanner on /projects/[id] when PERSONA_PENDING.md exists

## Test plan
- [x] Component tests for modal validation + multipart submit
- [x] Manual smoke: create via UI, persona generated, banner appears/disappears

Spec: bevox-knowledge/35_specs/openclaw/2026-04-28-mc-projects-factory-wave-2-vox-clone.md
EOF
)"
```

---

## Phase 3 acceptance gate

- [ ] Modal accepts PRD (textarea or upload), validates ≥200 chars
- [ ] POST /api/projects routes PRD to factory `--prd`
- [ ] Loading state shows "Forjando persona..." after 4s
- [ ] Persona pending banner shows on /projects/[id] when expected
- [ ] Component tests + smoke green
- [ ] PR opened
