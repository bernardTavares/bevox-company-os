---
name: bevox-knowledge-contribute
description: |
  Use whenever the user asks to create, draft, migrate, or update a PRD, ADR,
  architecture document, runbook, spec, roadmap, release note, customer
  feedback artifact, or metrics doc. These artifacts are NOT written to local
  repo paths — they live in bevox-knowledge per ADR-010 (taxonomy) and
  ADR-011 (slots). This skill handles bootstrap, gap-report, migrate,
  propose, and status against the canonical bevox-knowledge slot for
  this project (openclaw, slot: openclaw).
project: openclaw
slot: openclaw
bevox_knowledge_path_default: $HOME/bevox-knowledge
helpers_subpath: 99_templates/skill-bevox-knowledge-contribute/lib
version: 1.0.0
---

# bevox-knowledge-contribute (project: openclaw)

This project's canonical documentation lives in `bevox-knowledge`,
slot `openclaw`. **NEVER** write PRDs, ADRs, architecture docs, specs,
roadmaps, runbooks, release-notes, customer-feedback, or metrics docs
to local repo paths inside openclaw.

## Pre-flight (run once per session)

```bash
BK_PATH="${BEVOX_KNOWLEDGE_PATH:-$HOME/bevox-knowledge}"
HELPERS="$BK_PATH/99_templates/skill-bevox-knowledge-contribute/lib"
[ -d "$HELPERS" ] || { echo "skill not installed in $BK_PATH; pull bevox-knowledge"; exit 1; }
```

If `BK_PATH` is not a git repo or helpers are missing, abort and
instruct the user to clone/pull bevox-knowledge before retrying.

## When to activate

- Creating/drafting new canonical doc (PRD, ADR, runbook, etc.)
- Migrating an existing local doc to canonical form
- Reporting what's missing or stale in canonical for openclaw
- Diff between local docs and canonical state

## Subcommands

### `bootstrap`

Trigger: "criar slot pra openclaw" / first activation.

Steps:
1. `$HELPERS/slot_resolve.sh openclaw` → fail-fast if non-canonical
2. For each canonical folder, check if `<bk>/<folder>/openclaw/` exists; skip if present (idempotent)
3. Ask user for branch name; default `draft/openclaw-bootstrap`
4. `WT=$($HELPERS/git_open_draft.sh <branch>)`
5. For each canonical folder missing the slot dir: `mkdir -p "$WT/<folder>/openclaw/" && touch "$WT/<folder>/openclaw/.gitkeep"`
6. `$HELPERS/git_commit_push.sh "$WT" "bootstrap(openclaw): cria 9 subpastas canônicas"`
7. Print branch URL for review.

### `gap-report` (read-only)

Trigger: "o que tá faltando em openclaw?".

Steps:
1. `$HELPERS/slot_resolve.sh openclaw` → 9 expected paths
2. For each: `ls` and count artifacts
3. List local docs in `<projeto>/docs/`, `<projeto>/README.md`, `<projeto>/CLAUDE.md`, etc., classifying via `$HELPERS/doc_classify.sh`
4. Identify "implicit decisions" without ADR (env vars, libs grandes, padrões em CLAUDE.md/README sem ADR escrita)
5. Format report: per slot folder, canonical count vs local count, action (MIGRATE / DRAFT FROM SCRATCH / RETIRE), estimated effort

No writes.

### `migrate <source_doc>`

Trigger: "migrar X pra canonical" / "trazer X de openclaw/docs/".

Steps:
1. `$HELPERS/doc_classify.sh <source_doc>` → suggested type + confidence
2. Confirm with user (type? naming? renumber if ADR?)
3. Ask branch name; default `draft/openclaw-<topic>-migration`
4. `WT=$($HELPERS/git_open_draft.sh <branch>)`
5. Read source, transform (renumber, frontmatter normalization, paths), write to canonical destination
6. `$HELPERS/frontmatter_validate.sh <new_doc> <type>` → on failure, `git -C "$WT" checkout HEAD -- <new_doc>` + surface error
7. `$HELPERS/git_commit_push.sh "$WT" "migrate(openclaw/<type>): <source> → <dest>"`
8. Print branch URL.

### `propose <doc_type> <slug>`

Trigger: "vamos criar PRD/ADR/runbook/etc pra openclaw".

Steps:
1. Validate `<doc_type>` ∈ {prd, adr, architecture, spec, runbook, roadmap, release-note, customer-feedback, metrics}
2. `$HELPERS/slot_resolve.sh openclaw --folder <derived_folder>` → destination dir
3. Apply naming convention (see below) to produce filename
   - For ADR doc_type: NNN comes from `$HELPERS/adr_next_number.sh`
4. Pre-check: if destination file exists, ask user (overwrite? v2? abort?)
5. Ask branch name; default `draft/openclaw-<doc_type>-<slug>`
6. `WT=$($HELPERS/git_open_draft.sh <branch>)`
7. Copy `99_templates/<doc_type>.md` → destination, fill placeholders via conversation
8. `$HELPERS/frontmatter_validate.sh <new_doc> <doc_type>`
9. `$HELPERS/git_commit_push.sh "$WT" "propose(openclaw/<type>): <slug>"`
10. Print branch URL.

### `status` (read-only)

Trigger: "o que mudou entre openclaw local e canonical?".

Steps:
1. List local classifiable docs (`$HELPERS/doc_classify.sh` each)
2. For each, find canonical correspondence (slug or type+heading match)
3. Diff:
   - Absent in canonical → propose migration
   - Absent locally → canonical without clear origin
   - Stale (canonical out-of-date vs local)
4. Format report.

No writes.

## Authority and constraints

- Branch: `draft/openclaw-<topic>`, user-supplied; never write to `main`
- Never auto-open PR; print branch URL and let user decide review
- `frontmatter_validate.sh` mandatory before commit (rollback on fail)
- ADR numbering: global sequential — use `$HELPERS/adr_next_number.sh` to get next
- Worktree isolated in `/tmp/bevox-knowledge-worktrees/`; safe to abandon

## Naming conventions

| Doc type | Naming |
|---|---|
| PRD | `<YYYY-MM-DD>-openclaw-prd-v<N>.md` |
| ADR | `ADR-<NNN>-<slug>.md` (next available global) |
| Spec | `<YYYY-MM-DD>-<topic>.md` |
| Architecture | `<topic>.md` |
| Runbook | `<verb-noun>.md` (under `20_architecture/openclaw/runbooks/`) |
| Release note | `v<X.Y.Z>-<YYYY-MM-DD>.md` |
| Customer feedback | `<YYYY-MM-DD>-<source>-<topic>.md` |
| Metrics | `<metric-name>.md` |
| Inbox | `<YYYY-MM-DD>-<topic>.md` |

## Folder mapping (doc_type → bevox-knowledge folder)

| Doc type | Folder |
|---|---|
| PRD | `10_prd/openclaw/` |
| ADR | `30_adr/openclaw/` |
| Spec | `35_specs/openclaw/` |
| Architecture | `20_architecture/openclaw/` |
| Runbook | `20_architecture/openclaw/runbooks/` |
| Roadmap | `40_roadmap/openclaw/` |
| Release note | `50_releases/openclaw/` |
| Customer feedback | `60_customer-feedback/openclaw/` |
| Metrics | `70_metrics/openclaw/` |
| Inbox | `00_inbox/openclaw/` |

## Reference ADRs

- ADR-001 — Company OS Boundary
- ADR-002 — System Topology (amended by ADR-011)
- ADR-005 — Knowledge Source of Truth
- ADR-010 — Knowledge Project Separation
- ADR-011 — Topology amendment (bevox-direct, bevox-meta-api, bevox-site)
- ADR-012 — Meta consumption boundary
