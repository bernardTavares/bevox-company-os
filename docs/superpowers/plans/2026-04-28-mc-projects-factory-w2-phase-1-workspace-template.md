# MC Projects Factory Wave 2 — Phase 1: Workspace Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current `kanban-tasks/templates/workspace/*.tmpl` mechanism with a literal, functional `~/.openclaw/workspace-template/` directory that mirrors the canonical `~/.openclaw/workspace/`, enriched with embedded devops knowledge (`memory/integrations/{dispatcher,scrum-master,clarification,kanban,mcp}.md`). Rewrite `step_3_create_workspace` to use `cp -r` + sed substitution.

**Architecture:** New canonical template lives at `~/.openclaw/workspace-template/`, versioned in the `bernardTavares/openclaw` repo. Project factory clones it on `openclaw project create`. Variable fields use `{{PROJECT_NAME}}`, `{{SLUG}}`, `{{DOMAIN}}`, `{{DATE}}` markers; persona-rich files (IDENTITY/SOUL/MISSION) carry `<!-- PERSONA: PENDING -->` markers consumed by Phase 2.

**Tech Stack:** Python 3.13, pytest, bash. No new runtime deps.

**Spec:** `bevox-knowledge/35_specs/openclaw/2026-04-28-mc-projects-factory-wave-2-vox-clone.md` §2.3, §6 (Phase 1).

**Pre-requisites:** None. This is the foundation phase.

---

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `~/.openclaw/workspace-template/` | CREATE | Canonical template directory; literal workspace |
| `~/.openclaw/workspace-template/IDENTITY.md` | CREATE | Persona placeholder + PENDING marker |
| `~/.openclaw/workspace-template/SOUL.md` | CREATE | Persona placeholder + PENDING marker |
| `~/.openclaw/workspace-template/USER.md` | CREATE | Bernard profile (copied verbatim) |
| `~/.openclaw/workspace-template/AGENTS.md` | CREATE | Operational rules (with `{{...}}`) |
| `~/.openclaw/workspace-template/BOOT.md` | CREATE | Boot protocol (with `{{...}}`) |
| `~/.openclaw/workspace-template/HEARTBEAT.md` | CREATE | Heartbeat checklist |
| `~/.openclaw/workspace-template/TOOLS.md` | CREATE | Tool refs (mostly fixed) |
| `~/.openclaw/workspace-template/MEMORY.md` | CREATE | Memory index (with `{{...}}`) |
| `~/.openclaw/workspace-template/memory/MEMORY.md` | CREATE | Memory subsystem index |
| `~/.openclaw/workspace-template/memory/{decisions,lessons,people,pending,projects}.md` | CREATE | Memory file stubs |
| `~/.openclaw/workspace-template/memory/context/*.md` | CREATE | Context subsystem stubs |
| `~/.openclaw/workspace-template/memory/feedback/*.json` | CREATE | Feedback stubs |
| `~/.openclaw/workspace-template/memory/integrations/dispatcher.md` | CREATE | Devops doc — dispatcher loop |
| `~/.openclaw/workspace-template/memory/integrations/scrum-master.md` | CREATE | Devops doc — proposal/accept |
| `~/.openclaw/workspace-template/memory/integrations/clarification.md` | CREATE | Devops doc — clarification lifecycle |
| `~/.openclaw/workspace-template/memory/integrations/kanban.md` | CREATE | Devops doc — kanban CLI |
| `~/.openclaw/workspace-template/memory/integrations/mcp.md` | CREATE | Devops doc — MCP servers |
| `~/.openclaw/workspace-template/memory/{projects,sessions}/.keep` | CREATE | Empty dir markers |
| `~/.openclaw/scripts/sanitize-workspace-snapshot.py` | CREATE | One-shot script to blank personal memory from snapshot |
| `~/.openclaw/kanban-tasks/lib/project_factory.py` | MODIFY | Rewrite `step_3_create_workspace` (lines 286-342) |
| `~/.openclaw/kanban-tasks/lib/project_factory.py` | MODIFY | Drop `PERSONA_FILES`, `MEMORY_FILES`, `MEMORY_EMPTY_DIRS` constants (no longer needed) |
| `~/.openclaw/kanban-tasks/templates/workspace/` | DELETE | Move to `_retired/templates/workspace-2026-04-28/` |
| `~/.openclaw/kanban-tasks/tests/test_project_factory.py` | MODIFY | Rewrite tests for `step_3_create_workspace` to use template clone |

---

## Task 1: Setup branch + folder structure

**Files:**
- Create: `~/.openclaw/workspace-template/` (empty for now)

- [ ] **Step 1: Create feature branch**

```bash
cd ~/.openclaw
git checkout -b feat/mc-projects-factory-w2-phase-1-workspace-template
git status
```

Expected: clean working tree on new branch.

- [ ] **Step 2: Create empty `workspace-template/` skeleton**

```bash
cd ~/.openclaw
mkdir -p workspace-template/memory/{context,feedback,integrations,projects,sessions}
touch workspace-template/memory/projects/.keep
touch workspace-template/memory/sessions/.keep
```

- [ ] **Step 3: Verify structure**

```bash
find ~/.openclaw/workspace-template -type d | sort
```

Expected output:
```
~/.openclaw/workspace-template
~/.openclaw/workspace-template/memory
~/.openclaw/workspace-template/memory/context
~/.openclaw/workspace-template/memory/feedback
~/.openclaw/workspace-template/memory/integrations
~/.openclaw/workspace-template/memory/projects
~/.openclaw/workspace-template/memory/sessions
```

---

## Task 2: Snapshot canonical workspace into template (with sanitization)

**Files:**
- Create: `~/.openclaw/scripts/sanitize-workspace-snapshot.py`

This task copies content from `~/.openclaw/workspace/` into `workspace-template/`, then runs a sanitizer to remove personal memory entries and replace persona content with placeholders.

- [ ] **Step 1: Write sanitizer script**

Create `~/.openclaw/scripts/sanitize-workspace-snapshot.py`:

```python
#!/usr/bin/env python3
"""sanitize-workspace-snapshot.py — one-shot helper for Phase 1.

Reads files from ~/.openclaw/workspace/ and writes sanitized versions to
~/.openclaw/workspace-template/. Replaces persona-rich content with
placeholders and PENDING markers; truncates personal memory files to stubs;
adds {{PROJECT_NAME}}/{{SLUG}}/{{DOMAIN}}/{{DATE}} markers in operational
files.

Run once during Phase 1 setup. Re-running is safe (idempotent).
"""
from pathlib import Path

WORKSPACE = Path.home() / ".openclaw" / "workspace"
TEMPLATE = Path.home() / ".openclaw" / "workspace-template"

# Files copied verbatim (USER.md is the same Bernard profile across projects).
COPY_VERBATIM = ["USER.md"]

# Files replaced with placeholders + PENDING markers (filled by Phase 2 LLM).
PERSONA_PLACEHOLDERS = {
    "IDENTITY.md": """---
agent_name: voz-{{SLUG}}
project: {{SLUG}}
project_display_name: {{PROJECT_NAME}}
domain: {{DOMAIN}}
created: {{DATE}}
persona_status: pending
---

# Voz {{PROJECT_NAME}}

<!-- PERSONA: PENDING -->
<!-- This file will be regenerated by `openclaw project regenerate-persona {{SLUG}}` -->
<!-- using the project PRD as input. Until then, this is a placeholder. -->

Sou o Voz {{PROJECT_NAME}}, agente Chief of Staff dedicado ao projeto **{{SLUG}}** (domínio: {{DOMAIN}}).

Persona ainda não foi gerada. Rode o regenerate-persona para preencher.
""",
    "SOUL.md": """---
project: {{SLUG}}
persona_status: pending
---

# Soul — Voz {{PROJECT_NAME}}

<!-- PERSONA: PENDING -->

Persona ainda não foi gerada a partir do PRD do projeto.
""",
}

# Operational files: copy verbatim then add `{{...}}` markers in known places.
# For Phase 1, we use simple substitution rules (manual review will catch the rest).
OPERATIONAL_FILES = ["AGENTS.md", "BOOT.md", "HEARTBEAT.md", "TOOLS.md", "MEMORY.md"]

# Memory files: replace with stub indices (no personal content carried over).
MEMORY_STUBS = {
    "memory/MEMORY.md": """# Memory index — {{PROJECT_NAME}}

- [decisions](decisions.md) — decisões tomadas
- [lessons](lessons.md) — lições aprendidas
- [people](people.md) — pessoas relevantes
- [pending](pending.md) — pendências abertas
- [projects](projects/{{SLUG}}.md) — contexto deste projeto
- [integrations/dispatcher](integrations/dispatcher.md)
- [integrations/scrum-master](integrations/scrum-master.md)
- [integrations/clarification](integrations/clarification.md)
- [integrations/kanban](integrations/kanban.md)
- [integrations/mcp](integrations/mcp.md)
""",
    "memory/decisions.md": "# Decisions\n\n_Decisões tomadas neste projeto._\n",
    "memory/lessons.md": "# Lessons\n\n_Lições aprendidas durante a execução deste projeto._\n",
    "memory/people.md": "# People\n\n_Pessoas relevantes para este projeto._\n",
    "memory/pending.md": "# Pending\n\n_Pendências abertas que precisam de decisão ou input._\n",
    "memory/projects.md": "# Projects index\n\nProjeto único: [{{SLUG}}](projects/{{SLUG}}.md)\n",
    "memory/projects/{{SLUG}}.md": """---
project: {{SLUG}}
created: {{DATE}}
persona_status: pending
---

# {{PROJECT_NAME}}

<!-- PERSONA: PENDING -->

Resumo do projeto será gerado a partir do PRD.

PRD canônico: `bevox-knowledge/10_prd/{{SLUG}}/{{DATE}}-{{SLUG}}-prd.md`
""",
    "memory/context/decisions.md": "# Context — decisions\n\n_Decisões com contexto cruzado relevante para este projeto._\n",
    "memory/context/lessons.md": "# Context — lessons\n\n_Lições com aplicação cruzada._\n",
    "memory/context/people.md": "# Context — people\n\n_Pessoas em contextos não diretamente operacionais._\n",
    "memory/context/business-context.md": """---
project: {{SLUG}}
domain: {{DOMAIN}}
---

# Business context — {{PROJECT_NAME}}

<!-- PERSONA: PENDING -->

Contexto de negócio será preenchido a partir do PRD.
""",
    "memory/feedback/tone.json": "[]\n",
    "memory/feedback/content.json": "[]\n",
    "memory/feedback/tasks.json": "[]\n",
}


def copy_with_placeholder_pass(src: Path, dst: Path) -> None:
    """Copy file as-is. Manual review afterwards inserts {{...}} markers."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src.read_text(encoding="utf-8"))


def write_placeholder(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def main() -> int:
    if not WORKSPACE.is_dir():
        print(f"ERROR: source workspace not found: {WORKSPACE}")
        return 1
    if not TEMPLATE.is_dir():
        print(f"ERROR: template dir must exist (run Task 1 first): {TEMPLATE}")
        return 1

    # 1. Verbatim copies
    for name in COPY_VERBATIM:
        src = WORKSPACE / name
        if src.exists():
            copy_with_placeholder_pass(src, TEMPLATE / name)
            print(f"  verbatim: {name}")

    # 2. Operational files (copy now, manual marker insertion afterwards)
    for name in OPERATIONAL_FILES:
        src = WORKSPACE / name
        if src.exists():
            copy_with_placeholder_pass(src, TEMPLATE / name)
            print(f"  operational (review markers): {name}")

    # 3. Persona placeholders
    for name, content in PERSONA_PLACEHOLDERS.items():
        write_placeholder(TEMPLATE / name, content)
        print(f"  persona placeholder: {name}")

    # 4. Memory stubs
    for rel, content in MEMORY_STUBS.items():
        write_placeholder(TEMPLATE / rel, content)
        print(f"  memory stub: {rel}")

    print("\nDone. Manual review required:")
    print(f"  cd {TEMPLATE}")
    print("  # Audit AGENTS.md, BOOT.md, HEARTBEAT.md, TOOLS.md, MEMORY.md for")
    print("  # any personal content; insert {{PROJECT_NAME}}/{{SLUG}}/{{DOMAIN}}")
    print("  # markers where appropriate (project-specific references).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Make script executable and run it**

```bash
chmod +x ~/.openclaw/scripts/sanitize-workspace-snapshot.py
~/.openclaw/scripts/sanitize-workspace-snapshot.py
```

Expected output: list of files written, ending with `Done. Manual review required:`

- [ ] **Step 3: Verify file count**

```bash
find ~/.openclaw/workspace-template -type f | wc -l
```

Expected: at least 23 files (5 operational + USER.md + IDENTITY/SOUL + 14 memory stubs + 2 .keep files).

---

## Task 3: Manual sanitization review (HUMAN CHECKPOINT)

This task requires Bernard's review and is **not autonomous**. The agent must pause and request review.

- [ ] **Step 1: Pause for human review**

Print to user:

> Phase 1 Task 3 requires your manual review. The sanitizer copied AGENTS.md, BOOT.md, HEARTBEAT.md, TOOLS.md, MEMORY.md verbatim from your live workspace. Please:
>
> 1. Open `~/.openclaw/workspace-template/` and review each file
> 2. Insert `{{PROJECT_NAME}}` / `{{SLUG}}` / `{{DOMAIN}}` markers wherever the file references "this project" specifically
> 3. Remove any personal memory or session-specific content that should not propagate to new projects
> 4. Confirm USER.md is your canonical Bernard profile (it propagates verbatim to every clone)
>
> Once done, reply "approved" to continue.

Wait for user confirmation before proceeding.

- [ ] **Step 2: Verify no obvious personal markers remain**

```bash
cd ~/.openclaw/workspace-template
grep -rE "openclaw|bevox-mobile|bevox-app" \
  --include="*.md" --exclude-dir=integrations | head -20
```

Expected: only mentions of `bevox-` topology that are generic (not project-specific).

If specific project names appear in non-integration files, surface them to the user before continuing.

---

## Task 4: Add embedded devops knowledge — dispatcher.md

**Files:**
- Create: `~/.openclaw/workspace-template/memory/integrations/dispatcher.md`

- [ ] **Step 1: Write dispatcher integration doc**

```bash
cat > ~/.openclaw/workspace-template/memory/integrations/dispatcher.md <<'EOF'
# Integration: dispatcher-agent

> O **dispatcher-agent** seleciona a próxima task `ready` do meu projeto e
> dispara um Claude Code em background detached para executá-la.

## Como ele decide a próxima task

1. Lê `~/.openclaw/kanban-tasks/state.json`
2. Filtra tasks com `status=ready` e `project={{SLUG}}`
3. Respeita `WORK_IN_PROGRESS_LIMIT` (default 1 in_progress por projeto)
4. Ordena por `priority` desc, `created_at` asc
5. Dispara a primeira

## CLI cheatsheet

```bash
# Ver próxima task que seria escolhida (sem disparar)
~/.openclaw/dispatcher-agent/cli.sh next --project {{SLUG}} --dry-run

# Disparar próxima ready
~/.openclaw/dispatcher-agent/cli.sh next --launch --project {{SLUG}}

# Listar dispatches em andamento
~/.openclaw/dispatcher-agent/cli.sh list-active --project {{SLUG}}

# Marcar manualmente uma task como done (escape hatch)
~/.openclaw/dispatcher-agent/cli.sh complete <task-id> --actor {{SLUG}}
```

## Briefing format

Briefings ficam em `~/.openclaw/dispatcher-agent/briefings/<task-id>.md`.
Contêm: task title, description, payload (acceptance criteria, spec_ref),
project context, and operational instructions.

## Lifecycle

```
ready → in_progress → testing → done
                  ↓
               blocked (clarification opened)
```

Quando a task é dispatched, o dispatcher escreve `dispatcher_session_id`
no payload e move pra `in_progress`. O reaper periódico verifica se a
sessão Claude Code terminou e move pra `testing`. O tester-agent valida
e move pra `done` ou volta pra `ready` com feedback.

## Notificação

Em caso de `task_done` ou `task_failed`, o dispatcher posta no tópico
Telegram `dispatcher` (se `telegram.topics.dispatcher` presente em
`projects-meta.json` para este projeto). Senão, posta no general.
EOF
```

- [ ] **Step 2: Verify file**

```bash
ls -la ~/.openclaw/workspace-template/memory/integrations/dispatcher.md
wc -l ~/.openclaw/workspace-template/memory/integrations/dispatcher.md
```

Expected: file present, 40-50 lines.

---

## Task 5: Add embedded devops knowledge — scrum-master.md

**Files:**
- Create: `~/.openclaw/workspace-template/memory/integrations/scrum-master.md`

- [ ] **Step 1: Write scrum-master integration doc**

```bash
cat > ~/.openclaw/workspace-template/memory/integrations/scrum-master.md <<'EOF'
# Integration: scrum-master-agent

> O **scrum-master-agent** converte plans (`docs/superpowers/plans/`) em
> tasks no kanban-tasks via proposal/accept loop.

## Fluxo

1. Eu (ou Bernard) escrevo um plan em `~/.openclaw/docs/superpowers/plans/`
2. `scrum-master propose --plan <plan.md> --project {{SLUG}}` lê o plan e gera
   uma proposal JSON em `~/.openclaw/scrum-master-agent/proposals/`
3. Bernard revisa: `scrum-master review <proposal-id>` (mostra diff)
4. Bernard aceita: `scrum-master accept <proposal-id> [--ready]`
5. Tasks são materializadas no kanban; com `--ready` vão pra `ready`

## CLI cheatsheet

```bash
# Propor tasks a partir de um plan
~/.openclaw/scrum-master-agent/cli.sh propose \
    --plan ~/.openclaw/docs/superpowers/plans/<plan>.md \
    --project {{SLUG}}

# Listar proposals abertos
~/.openclaw/scrum-master-agent/cli.sh list-proposals --project {{SLUG}}

# Aceitar (move pra `next` por default; --ready pra `ready`)
~/.openclaw/scrum-master-agent/cli.sh accept <proposal-id> --ready

# Rejeitar (com motivo)
~/.openclaw/scrum-master-agent/cli.sh reject <proposal-id> --reason "..."
```

## Plan → task extraction

Scrum-master parseia headers `## Phase N: <title>` (sprint) e `### Task N.M:
<title>` (task). Cada `### Task` vira uma entry no kanban com:

- `title`: o título da task
- `description`: corpo até o próximo `### Task` ou `##`
- `payload.spec_ref`: referência da spec (extraída do header do plan)
- `payload.acceptance_criteria`: array de checkboxes encontrados na task
- `project`: passado via `--project`

## Lifecycle de proposal

```
draft → reviewed → accepted (tasks no kanban)
              ↓
           rejected
```
EOF
```

- [ ] **Step 2: Verify**

```bash
wc -l ~/.openclaw/workspace-template/memory/integrations/scrum-master.md
```

Expected: 40-50 lines.

---

## Task 6: Add embedded devops knowledge — clarification.md

**Files:**
- Create: `~/.openclaw/workspace-template/memory/integrations/clarification.md`

- [ ] **Step 1: Write clarification integration doc**

```bash
cat > ~/.openclaw/workspace-template/memory/integrations/clarification.md <<'EOF'
# Integration: clarification-agent

> O **clarification-agent** é o canal pra eu pedir input humano quando
> bloqueio em ambiguidade ou decisão fora do meu escopo.

## Quando criar uma question

Crie quando:
- Ambiguidade no spec/PRD que afeta a task atual e não posso resolver lendo
  bevox-knowledge ou ADRs
- Decisão arquitetural com trade-off real (não default óbvio)
- Spec contradiz código existente
- Falta info externa (credencial, link, decisão de negócio)

NÃO crie quando:
- O default razoável existe e dá pra documentar a escolha
- A questão é "como faço X" (skill issue, não clarificação)

## CLI cheatsheet

```bash
# Criar question (do dentro de uma task em execução)
~/.openclaw/clarification-agent/cli.sh ask \
    --task <task-id> \
    --question "Pergunta clara, com alternativas se houver" \
    --options "A,B,C"   # opcional

# Bernard responde:
~/.openclaw/clarification-agent/cli.sh answer <cid> --answer "..."

# Lista questions abertas para meu projeto
~/.openclaw/clarification-agent/cli.sh list --project {{SLUG}} --open
```

## Lifecycle

```
ask → notify (telegram) → answer → close → unblock task
```

Quando question é criada, task associada vai pra `blocked`. Quando
respondida, volta pra `ready` automaticamente; dispatcher re-executa.

## Notificação Telegram

Question vai pro tópico `clarifications` (se
`telegram.topics.clarifications` presente). Mensagem inclui ID, pergunta
completa, e instrução de resposta. Resposta via Telegram (reply) ou via
CLI são equivalentes.

## Format de answer file

Salvo em `~/.openclaw/clarification-agent/answers/<cid>.md`:

```markdown
---
cid: <cid>
task_id: <task-id>
project: {{SLUG}}
answered_at: <ts>
---

<resposta livre, markdown>
```
EOF
```

- [ ] **Step 2: Verify**

```bash
wc -l ~/.openclaw/workspace-template/memory/integrations/clarification.md
```

---

## Task 7: Add embedded devops knowledge — kanban.md

**Files:**
- Create: `~/.openclaw/workspace-template/memory/integrations/kanban.md`

- [ ] **Step 1: Write kanban integration doc**

```bash
cat > ~/.openclaw/workspace-template/memory/integrations/kanban.md <<'EOF'
# Integration: kanban-tasks

> O **kanban-tasks** é o sistema de tasks per-project (schema v4). Cada
> projeto tem seus próprios sprints (`current` + `next`).

## CLI cheatsheet

```bash
KANBAN=~/.openclaw/kanban-tasks/cli.sh

# Listar tasks deste projeto
$KANBAN task list --project {{SLUG}}

# Filtrar por status
$KANBAN task list --project {{SLUG}} --status ready

# Adicionar task ao sprint `next`
$KANBAN task add "Título da task" \
    --project {{SLUG}} \
    --sprint sprint-next \
    --description "Descrição" \
    --payload '{"spec_ref": "...", "acceptance_criteria": [...]}'

# Mover task entre states (idempotent)
$KANBAN task move <task-id> ready --actor {{SLUG}}
$KANBAN task move <task-id> in_progress --actor dispatcher
$KANBAN task move <task-id> testing --actor reaper
$KANBAN task move <task-id> done --actor tester

# Bloquear/desbloquear
$KANBAN task block <task-id> --reason "..."
$KANBAN task unblock <task-id>

# Listar sprints
$KANBAN sprint list --project {{SLUG}}

# Fechar sprint atual
$KANBAN sprint close-current --project {{SLUG}} --carryover
```

## Estados válidos

```
draft → next → ready → in_progress → testing → done
                 ↓
              blocked  (via clarification ou tester reject)
```

## Payload format

```json
{
  "spec_ref": "35_specs/openclaw/2026-04-NN-...md",
  "acceptance_criteria": [
    "Criterio 1",
    "Criterio 2"
  ],
  "branch": "feat/...",
  "dispatcher_session_id": null
}
```

## Eventos

`events.jsonl` é append-only. Cada transição emite um event com `seq`,
`ts`, `type`, `actor`, `task_id`/`project`, `snapshot`. Snapshot pre-delete
é preservado mesmo após `project remove`.
EOF
```

- [ ] **Step 2: Verify**

```bash
wc -l ~/.openclaw/workspace-template/memory/integrations/kanban.md
```

---

## Task 8: Add embedded devops knowledge — mcp.md

**Files:**
- Create: `~/.openclaw/workspace-template/memory/integrations/mcp.md`

- [ ] **Step 1: Write MCP integration doc**

```bash
cat > ~/.openclaw/workspace-template/memory/integrations/mcp.md <<'EOF'
# Integration: MCP servers

> Quais MCP servers eu posso usar e quando.

## codegraph

Análise estrutural de codebases — callers/callees, impact analysis,
search por símbolo. Útil quando trabalhando em código pra mapear quem
chama o quê antes de mudar.

```
mcp__codegraph__codegraph_search
mcp__codegraph__codegraph_callers
mcp__codegraph__codegraph_callees
mcp__codegraph__codegraph_impact
```

## telegram

Acesso ao bot Telegram do meu projeto (se conectado). Útil pra postar
status, ler mensagens recentes, reagir a comandos. Configurado via
`bootstrap-telegram-agent.sh` per-project.

## Drive (Google)

Acesso a docs/sheets se autenticado. Use pra ler PRDs/specs externas
que ainda não foram trazidas pro `bevox-knowledge`.

## Quando NÃO usar MCP

- Operações simples de file/grep — use Read/Bash diretamente
- Investigações de 1-3 queries — Bash é mais rápido e barato
- Edição — use Edit tool, não MCP

## Adicionar MCP server novo

Edita `~/.claude/mcp.json` global ou `~/.claude/projects/<dir>/mcp.json`
local. Reinicia Claude Code session pra carregar.
EOF
```

- [ ] **Step 2: Verify**

```bash
wc -l ~/.openclaw/workspace-template/memory/integrations/mcp.md
```

- [ ] **Step 3: Verify all 5 integrations exist**

```bash
ls ~/.openclaw/workspace-template/memory/integrations/
```

Expected output:
```
clarification.md
dispatcher.md
kanban.md
mcp.md
scrum-master.md
```

---

## Task 9: Audit final do template e commit inicial

- [ ] **Step 1: Run final structural audit**

```bash
cd ~/.openclaw/workspace-template
find . -type f -not -path "./.keep" | sort
```

Expected: ~25 files covering AGENTS.md, BOOT.md, HEARTBEAT.md, IDENTITY.md, MEMORY.md, SOUL.md, TOOLS.md, USER.md, memory/ subtree (with 5 integration files).

- [ ] **Step 2: Verify all PERSONA: PENDING markers are in place**

```bash
grep -rl "PERSONA: PENDING" ~/.openclaw/workspace-template/
```

Expected output (exact list):
```
.../IDENTITY.md
.../SOUL.md
.../memory/projects/{{SLUG}}.md
.../memory/context/business-context.md
```

- [ ] **Step 3: Verify all `{{...}}` markers**

```bash
grep -rohE "\{\{[A-Z_]+\}\}" ~/.openclaw/workspace-template/ | sort -u
```

Expected output (exactly these markers, no others):
```
{{DATE}}
{{DOMAIN}}
{{PROJECT_NAME}}
{{SLUG}}
```

If extra markers appear, fix them before continuing.

- [ ] **Step 4: Stage and commit template**

```bash
cd ~/.openclaw
git add workspace-template/ scripts/sanitize-workspace-snapshot.py
git status
git commit -m "feat(workspace-template): add canonical template directory

Phase 1 of mc-projects-factory wave-2. Adds ~/.openclaw/workspace-template/
as a literal, functional reference workspace. Includes embedded devops
knowledge in memory/integrations/ for dispatcher, scrum-master,
clarification, kanban, MCP. Persona files (IDENTITY, SOUL,
memory/projects/{{SLUG}}.md, business-context) carry <!-- PERSONA: PENDING -->
markers, populated by Phase 2 LLM extractor.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-28-mc-projects-factory-wave-2-vox-clone.md"
```

---

## Task 10: TDD — Write failing test for new step_3_create_workspace

**Files:**
- Modify: `~/.openclaw/kanban-tasks/tests/test_project_factory.py`

- [ ] **Step 1: Read current test file location and structure**

```bash
grep -n "def test.*step_3\|def test.*workspace\|def test.*create_workspace" \
  ~/.openclaw/kanban-tasks/tests/test_project_factory.py
```

Note line numbers of any existing `step_3` tests — they will be replaced.

- [ ] **Step 2: Add new failing test**

Append to `~/.openclaw/kanban-tasks/tests/test_project_factory.py`:

```python
def test_step_3_clones_workspace_template_and_substitutes_markers(tmp_path):
    """step_3_create_workspace must cp -r workspace-template/ then sed markers."""
    from lib.project_factory import step_3_create_workspace

    # Arrange: build a minimal workspace-template fixture under tmp_path
    openclaw_dir = tmp_path / ".openclaw"
    template_dir = openclaw_dir / "workspace-template"
    template_dir.mkdir(parents=True)
    (template_dir / "memory").mkdir()
    (template_dir / "memory" / "integrations").mkdir()
    (template_dir / "memory" / "projects").mkdir()
    (template_dir / "IDENTITY.md").write_text(
        "Voz {{PROJECT_NAME}} para slug {{SLUG}} (domínio {{DOMAIN}}).\n"
    )
    (template_dir / "memory" / "projects" / "{{SLUG}}.md").write_text(
        "Projeto {{PROJECT_NAME}}\n"
    )

    # Act: clone for slug=foo
    result = step_3_create_workspace(
        slug="foo",
        name="Foo Project",
        openclaw_dir=openclaw_dir,
        templates_dir=tmp_path / "unused",  # legacy arg, kept for signature
        date_str="2026-04-28",
        domain="Produto",
    )

    # Assert: workspace-foo exists with substituted content
    workspace_foo = openclaw_dir / "workspace-foo"
    assert workspace_foo.is_dir()
    identity = (workspace_foo / "IDENTITY.md").read_text()
    assert "Voz Foo Project para slug foo (domínio Produto)." in identity
    assert "{{PROJECT_NAME}}" not in identity
    assert "{{SLUG}}" not in identity
    assert "{{DOMAIN}}" not in identity

    # Filename substitution: {{SLUG}}.md → foo.md
    project_file = workspace_foo / "memory" / "projects" / "foo.md"
    assert project_file.is_file()
    assert (workspace_foo / "memory" / "projects" / "{{SLUG}}.md").exists() is False

    assert result["workspace_dir"] == str(workspace_foo)


def test_step_3_idempotent_skip_if_exists(tmp_path):
    """step_3 must skip cloning if workspace-<slug>/ already exists."""
    from lib.project_factory import step_3_create_workspace

    openclaw_dir = tmp_path / ".openclaw"
    template_dir = openclaw_dir / "workspace-template"
    template_dir.mkdir(parents=True)
    (template_dir / "IDENTITY.md").write_text("from template\n")

    workspace_foo = openclaw_dir / "workspace-foo"
    workspace_foo.mkdir(parents=True)
    (workspace_foo / "IDENTITY.md").write_text("pre-existing\n")

    result = step_3_create_workspace(
        slug="foo", name="Foo",
        openclaw_dir=openclaw_dir,
        templates_dir=tmp_path / "unused",
        date_str="2026-04-28",
        domain="Produto",
    )

    # Pre-existing content preserved
    assert (workspace_foo / "IDENTITY.md").read_text() == "pre-existing\n"
    assert result["already_existed"] is True


def test_step_3_fails_when_template_missing(tmp_path):
    """step_3 must raise StepFailure if workspace-template/ is absent."""
    import pytest
    from lib.project_factory import step_3_create_workspace, StepFailure

    openclaw_dir = tmp_path / ".openclaw"
    openclaw_dir.mkdir()
    # NOTE: no workspace-template/ created

    with pytest.raises(StepFailure) as exc:
        step_3_create_workspace(
            slug="foo", name="Foo",
            openclaw_dir=openclaw_dir,
            templates_dir=tmp_path / "unused",
            date_str="2026-04-28",
            domain="Produto",
        )
    assert exc.value.code == "template_missing"
```

- [ ] **Step 3: Run new tests, verify they fail**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m pytest tests/test_project_factory.py::test_step_3_clones_workspace_template_and_substitutes_markers tests/test_project_factory.py::test_step_3_idempotent_skip_if_exists tests/test_project_factory.py::test_step_3_fails_when_template_missing -v
```

Expected: 3 FAILED tests (the new logic isn't implemented yet — current `step_3` uses `.tmpl` files, not `workspace-template/` clone).

---

## Task 11: Rewrite step_3_create_workspace

**Files:**
- Modify: `~/.openclaw/kanban-tasks/lib/project_factory.py:255-342` (replace `PERSONA_FILES`, `MEMORY_FILES`, `MEMORY_EMPTY_DIRS` constants and `step_3_create_workspace`)

- [ ] **Step 1: Replace constants and step_3 function**

Open `~/.openclaw/kanban-tasks/lib/project_factory.py`. Replace lines 255-342 (the `PERSONA_FILES = (...)` constant block through the end of `step_3_create_workspace`) with:

```python
def _substitute_markers(
    text: str, *, slug: str, name: str, domain: str, date_str: str
) -> str:
    """Replace {{PROJECT_NAME}}, {{SLUG}}, {{DOMAIN}}, {{DATE}} in text."""
    return (
        text.replace("{{PROJECT_NAME}}", name)
        .replace("{{SLUG}}", slug)
        .replace("{{DOMAIN}}", domain)
        .replace("{{DATE}}", date_str)
    )


def step_3_create_workspace(
    slug: str,
    name: str,
    openclaw_dir: Path,
    templates_dir: Path,  # kept for signature compat; unused now
    date_str: str,
    domain: str = "",
) -> dict:
    """Clone ~/.openclaw/workspace-template/ → ~/.openclaw/workspace-<slug>/.

    Substitutes {{PROJECT_NAME}}, {{SLUG}}, {{DOMAIN}}, {{DATE}} in file
    contents AND filenames (e.g., memory/projects/{{SLUG}}.md → memory/projects/<slug>.md).

    Idempotent: returns {"already_existed": True} if workspace-<slug>/ exists.

    Raises StepFailure(code="template_missing") if workspace-template/ absent.
    """
    template_dir = openclaw_dir / "workspace-template"
    if not template_dir.is_dir():
        raise StepFailure(
            3, "template_missing",
            f"workspace-template not found at {template_dir}",
        )

    runtime_dir = openclaw_dir / slug
    workspace_dir = openclaw_dir / f"workspace-{slug}"

    # Runtime dirs (always create)
    for sub in ("clarifications", "notifications", "scripts"):
        (runtime_dir / sub).mkdir(parents=True, exist_ok=True)

    if workspace_dir.exists():
        return {
            "runtime_dir": str(runtime_dir),
            "workspace_dir": str(workspace_dir),
            "already_existed": True,
        }

    # Clone tree, substituting markers in both file CONTENT and PATH
    files_written = []
    for src in template_dir.rglob("*"):
        rel = src.relative_to(template_dir)
        # Substitute path
        rel_str = _substitute_markers(
            str(rel), slug=slug, name=name, domain=domain, date_str=date_str,
        )
        dst = workspace_dir / rel_str

        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue

        dst.parent.mkdir(parents=True, exist_ok=True)
        # Substitute content (text files only — JSON memory/feedback/*.json
        # carry no markers but are valid UTF-8 anyway)
        try:
            content = src.read_text(encoding="utf-8")
            content = _substitute_markers(
                content, slug=slug, name=name, domain=domain, date_str=date_str,
            )
            dst.write_text(content, encoding="utf-8")
        except UnicodeDecodeError:
            # Binary file — copy bytes
            dst.write_bytes(src.read_bytes())
        files_written.append(str(dst))

    return {
        "runtime_dir": str(runtime_dir),
        "workspace_dir": str(workspace_dir),
        "files_written": files_written,
        "already_existed": False,
    }
```

- [ ] **Step 2: Update create_project caller to pass `domain` to step_3**

Find in `project_factory.py` (around line 525-527, the steps tuple inside `create_project`):

Old:
```python
        (3, "openclaw_workspace", lambda: step_3_create_workspace(
            slug, name, config.openclaw_dir,
            config.templates_dir, date_str)),
```

New (pass `domain` as kwarg, falling back to empty string for backward compat — `domain` will become a real param in Phase 2):
```python
        (3, "openclaw_workspace", lambda: step_3_create_workspace(
            slug, name, config.openclaw_dir,
            config.templates_dir, date_str,
            domain="")),
```

- [ ] **Step 3: Run the failing tests, verify they now pass**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m pytest tests/test_project_factory.py::test_step_3_clones_workspace_template_and_substitutes_markers tests/test_project_factory.py::test_step_3_idempotent_skip_if_exists tests/test_project_factory.py::test_step_3_fails_when_template_missing -v
```

Expected: 3 PASSED.

- [ ] **Step 4: Run full test suite, verify nothing else broke**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m pytest -v
```

Expected: all tests pass, including pre-existing tests for create_project orchestrator.

---

## Task 12: Retire old `.tmpl` workspace templates

**Files:**
- Delete: `~/.openclaw/kanban-tasks/templates/workspace/`

- [ ] **Step 1: Move templates to retired location**

```bash
cd ~/.openclaw/kanban-tasks/templates
mkdir -p _retired
git mv workspace _retired/workspace-2026-04-28-pre-w2
git status
```

Expected: workspace/ directory shown as renamed.

- [ ] **Step 2: Remove unused imports/refs in project_factory.py**

```bash
grep -n "templates_dir.*workspace\|workspace_tmpl_dir\|memory_tmpl_dir" \
  ~/.openclaw/kanban-tasks/lib/project_factory.py
```

Expected: only the `templates_dir` parameter in `step_3_create_workspace` signature remains. If other refs found in dead code, remove them (the tests in Task 10 + 11 cover the remaining behavior).

- [ ] **Step 3: Re-run full test suite**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m pytest -v
```

Expected: all tests pass.

---

## Task 13: Smoke test — create real test project via CLI

- [ ] **Step 1: Run smoke creation**

```bash
cd ~/.openclaw/kanban-tasks
./cli.sh project create "Smoke Test W2 Phase 1" \
    --id "smoke-w2-p1" \
    --description "Smoke test for workspace-template phase 1"
```

Expected: success, all 6 steps complete.

- [ ] **Step 2: Inspect generated workspace**

```bash
ls -la ~/.openclaw/workspace-smoke-w2-p1/
cat ~/.openclaw/workspace-smoke-w2-p1/IDENTITY.md
cat ~/.openclaw/workspace-smoke-w2-p1/memory/integrations/dispatcher.md | head -10
ls ~/.openclaw/workspace-smoke-w2-p1/memory/projects/
```

Expected:
- `IDENTITY.md` references "Smoke Test W2 Phase 1" and "smoke-w2-p1"
- `dispatcher.md` is the embedded devops doc with `{{SLUG}}` replaced by `smoke-w2-p1`
- `memory/projects/smoke-w2-p1.md` exists (filename was substituted)
- IDENTITY.md still contains `<!-- PERSONA: PENDING -->` (Phase 2 will fill it)

- [ ] **Step 3: Verify no `{{...}}` markers leaked**

```bash
grep -rn "{{" ~/.openclaw/workspace-smoke-w2-p1/ | head
```

Expected: empty output (no markers leaked).

- [ ] **Step 4: Cleanup smoke project**

```bash
cd ~/.openclaw/kanban-tasks
./cli.sh project remove smoke-w2-p1 --skip-github
```

Expected: success, all 5 destinations cleaned (no GitHub since smoke didn't push).

- [ ] **Step 5: Verify cleanup**

```bash
ls ~/.openclaw/ | grep smoke || echo "OK — no smoke residue"
ls ~/bevox-knowledge/10_prd/ | grep smoke || echo "OK — no smoke residue in kb"
```

Expected: "OK — no smoke residue" in both.

---

## Task 14: Commit Phase 1 implementation work

- [ ] **Step 1: Stage all changes**

```bash
cd ~/.openclaw
git add kanban-tasks/lib/project_factory.py \
        kanban-tasks/tests/test_project_factory.py \
        kanban-tasks/templates/_retired/workspace-2026-04-28-pre-w2/
git status
```

Expected: modifications + retire move staged.

- [ ] **Step 2: Commit**

```bash
git commit -m "feat(project-factory): rewrite step_3 to clone workspace-template

Phase 1 of mc-projects-factory wave-2. step_3_create_workspace now
cp -r the canonical ~/.openclaw/workspace-template/ directory and
substitutes {{PROJECT_NAME}}, {{SLUG}}, {{DOMAIN}}, {{DATE}} markers
in both file content and filenames. Old .tmpl mechanism retired to
templates/_retired/workspace-2026-04-28-pre-w2/.

Tests cover happy path, idempotence, and missing-template failure."
```

- [ ] **Step 3: Push branch**

```bash
git push -u origin feat/mc-projects-factory-w2-phase-1-workspace-template
```

- [ ] **Step 4: Open PR**

```bash
gh pr create --title "feat: workspace-template (Phase 1 of factory wave-2)" \
  --body "$(cat <<'EOF'
## Summary
- Adds canonical `~/.openclaw/workspace-template/` (literal, functional reference workspace)
- Embedded devops knowledge in `memory/integrations/` (dispatcher, scrum-master, clarification, kanban, mcp)
- Persona files carry `<!-- PERSONA: PENDING -->` markers (filled by Phase 2)
- Rewrites `step_3_create_workspace` to clone via `cp -r` + sed substitution
- Retires old `.tmpl` mechanism

## Test plan
- [x] Unit tests cover happy path, idempotence, missing-template
- [x] Smoke: created and removed `smoke-w2-p1` via CLI; verified workspace structure

Spec: `bevox-knowledge/35_specs/openclaw/2026-04-28-mc-projects-factory-wave-2-vox-clone.md`
EOF
)"
```

---

## Phase 1 acceptance gate

Before declaring Phase 1 complete:

- [ ] `~/.openclaw/workspace-template/` versioned and committed
- [ ] All 5 `memory/integrations/*.md` present
- [ ] All `<!-- PERSONA: PENDING -->` markers in correct files
- [ ] All `{{...}}` markers limited to the 4 canonical ones
- [ ] `step_3_create_workspace` rewritten + tested
- [ ] Old `.tmpl` directory retired
- [ ] Smoke test passed
- [ ] PR opened
