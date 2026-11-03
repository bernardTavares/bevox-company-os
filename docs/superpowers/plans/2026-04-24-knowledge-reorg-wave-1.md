# Knowledge Reorg Wave-1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrar os 64 specs de `bevox-knowledge/35_specs/` para suas subpastas de projeto conforme ADR-010, atualizar cross-refs e tracker, sem quebrar consumidores.

**Architecture:** `git mv` em lote preservando history, em 4 grupos (openclaw/48, company-os/13, bevox-backend/1, _retired/2). Zero mudança de código em consumidores (verificado empiricamente: bash `case 35_specs/*` e regex `[^\s]+` aceitam subpaths). Atualizações limitadas a docstrings/docs em mission-control (2 arquivos), cross-refs em `20_architecture/` e campo `spec:` em `delivery-tracker.yml`.

**Tech Stack:** bash, git, python (one-liner), markdown/yaml.

**Pré-requisito:** wave-0 concluída. Branches `draft/knowledge-reorg-wave-0` em bevox-knowledge (tip `feebc75`) e em .openclaw (tip `30c0500`). Tag `pre-knowledge-reorg` em 4 repos.

**Spec canônica:** `bevox-knowledge/35_specs/_shared/2026-04-24-knowledge-reorg-company-os-separation.md` §4 wave-1.

**Branches desta wave:**
- `bevox-knowledge` — `draft/knowledge-reorg-wave-1` a partir do tip de `draft/knowledge-reorg-wave-0` (acumula)
- `mission-control` — `draft/knowledge-reorg-wave-1` a partir de `main` (Tasks 10)
- `knowledge-sync`, `.openclaw` — **sem branches novas** (wave-1 não exige mudanças de código)

---

## File Structure

**Movem-se em `bevox-knowledge/`:**
- 64 specs de `35_specs/*.md` → `35_specs/<projeto>/*.md` (ou `_retired/`).

**Modificam-se em `bevox-knowledge/`:**
- `40_roadmap/delivery-tracker.yml` — todos os campos `spec:` atualizados
- `20_architecture/` — ~30 arquivos com cross-refs para `35_specs/`:
  - `health-registry.md`, `hardening-registry.md`, `knowledge-spine.md`
  - `agents/*.md` (delivery-status-agent, tester-agent, telegram-bot-agent-pattern, dispatcher-agent, clarification-agent, delivery-agent, documentation-agent)
  - `modules/bevox-harness.md`, `modules/bevox-backend.md`
  - `agents/_retired/bevox-mobile-auto-unblock-status.md`
  - `content-backlog.yml`, `finance-snapshot.example.yml`, `cost-alerts.example.yml`
  - `_tools/render-hardening-registry.py`, `_tools/render-health-registry.py`

**Modificam-se em `mission-control/`:**
- `src/lib/kanban/paths.ts` — docstring ref (linha 7)
- `docs/OPERATING.md` — ref (linha ~70)

---

## Mapping: classificação dos 64 specs

### `openclaw/` (48 specs)

```
2026-04-09-e0-foundation-freeze.md
2026-04-10-e1.1-fix-plugin-commands.md
2026-04-10-e1.1-telegram-approval-mode.md
2026-04-11-e10-functional-agents-wave-1.md
2026-04-11-e10-functional-agents-wave-1-plan.md
2026-04-11-e3-agent-registry-foundation.md
2026-04-11-e3-agent-registry-foundation-plan.md
2026-04-12-e4-approval-center-wave-1.md
2026-04-12-e4-approval-center-wave-1-plan.md
2026-04-13-e4.2-approval-center-operator-wave-1.md
2026-04-13-e4.2-approval-center-operator-wave-1-plan.md
2026-04-14-e11-finance-runway-wave-1.md
2026-04-14-e11-finance-runway-wave-1-plan.md
2026-04-14-e6-github-operations-wave-1.md
2026-04-14-e6-github-operations-wave-1-plan.md
2026-04-14-e8-infra-health-backup-wave-1.md
2026-04-14-e8-infra-health-backup-wave-1-plan.md
2026-04-14-e9-cost-usage-wave-1.md
2026-04-14-e9-cost-usage-wave-1-plan.md
2026-04-15-e9-cost-usage-wave-2.md
2026-04-15-e9-cost-usage-wave-2-plan.md
2026-04-16-e10-infra-agent-wave-2.md
2026-04-16-e12-content-backlog-wave-1.md
2026-04-16-e8-backup-center-wave-2.md
2026-04-16-e8-f3-snapshot-cron.md
2026-04-16-e8-health-alerts-wave-3.md
2026-04-17-e10-delivery-status-agent.md
2026-04-17-e11-f1-receitas-despesas.md
2026-04-17-e5-f4-kanban-tasks-implementation-plan.md
2026-04-18-e6-f4-release-notes-wave-1.md
2026-04-18-e8-f5-hardening-tracker-wave-1.md
2026-04-19-e10-cron-dispatcher.md
2026-04-19-e10-detached-reaper.md
2026-04-19-e10-dispatcher-and-clarification-agents.md
2026-04-19-e10-scrum-master-agent.md
2026-04-19-e10-tester-agent.md
2026-04-19-e5-f4-kanban-dev-lifecycle.md
2026-04-21-e10-clarification-daemon-local-first.md
2026-04-21-e10-noise-reset-prereq.md
2026-04-21-e10-payload-completeness-gate.md
2026-04-21-e10-scrum-master-self-test.md
2026-04-21-e10-scrum-master-v2.md
2026-04-21-e10-telegram-push-escalations.md
2026-04-21-e10-telegram-reply-handler.md
2026-04-21-e5-f4-kanban-blocked-by-schema.md
2026-04-22-e10-oh-wave-8-fixes.md
2026-04-22-e10-telegram-multi-bot.md
2026-04-23-clarification-telegram-enhancement.md
```

### `company-os/` (13 specs)

```
2026-04-09-e1-knowledge-spine.md
2026-04-10-e2-mission-control.md
2026-04-13-e5-roadmap-delivery-os-wave-1.md
2026-04-13-e5-roadmap-delivery-os-wave-1-plan.md
2026-04-15-e2-canonical-agents-projection.md
2026-04-15-e2-canonical-agents-projection-plan.md
2026-04-16-e2-canonical-agents-detail-edit.md
2026-04-16-e2-canonical-agents-detail-edit-plan.md
2026-04-16-e5-delivery-tracker-wave-2.md
2026-04-17-e5-f4-kanban-rich-ui-wave-2.md
2026-04-17-e5-f4-sprint-planning-wave-1.md
2026-04-17-e5-refinement-blockers-risks.md
2026-04-23-mc-cron-management.md
```

### `bevox-backend/` (1 spec)

```
2026-04-23-e13-bevox-backend-init.md
```

### `_retired/` (2 specs)

```
bevox-app-v1-spec.md
2026-04-21-bevox-mobile-auto-unblock.md
```

### Mantém na raiz

- `README.md` — documenta o folder (exceção; consistente com `30_adr/README.md`, `40_roadmap/README.md`).

---

## Task 1: Setup branch wave-1 em bevox-knowledge

**Files:** nenhum — só git.

- [ ] **Step 1: Verificar estado atual**

```bash
cd ~/bevox-knowledge
git branch --show-current
git status --short
git log --oneline -1
```

Expected: em `draft/knowledge-reorg-wave-0`, working tree limpa, HEAD em `feebc75 chore(spec): move 2026-04-24-knowledge-reorg para 35_specs/_shared/`.

Se não estiver em wave-0 ou houver dirt, STOP e reportar BLOCKED.

- [ ] **Step 2: Criar branch wave-1 a partir da ponta da wave-0**

```bash
cd ~/bevox-knowledge
git checkout -b draft/knowledge-reorg-wave-1
git branch --show-current
```

Expected: `draft/knowledge-reorg-wave-1`.

- [ ] **Step 3: Commit (N/A — branch create não produz commit)**

---

## Task 2: `git mv` 48 specs para `openclaw/`

**Files:** 48 moves de `35_specs/*.md` para `35_specs/openclaw/`.

- [ ] **Step 1: Remover `.gitkeep` de `35_specs/openclaw/`**

```bash
cd ~/bevox-knowledge
rm -f 35_specs/openclaw/.gitkeep
```

- [ ] **Step 2: `git mv` em lote**

```bash
cd ~/bevox-knowledge
SPECS_OPENCLAW=(
  2026-04-09-e0-foundation-freeze.md
  2026-04-10-e1.1-fix-plugin-commands.md
  2026-04-10-e1.1-telegram-approval-mode.md
  2026-04-11-e10-functional-agents-wave-1.md
  2026-04-11-e10-functional-agents-wave-1-plan.md
  2026-04-11-e3-agent-registry-foundation.md
  2026-04-11-e3-agent-registry-foundation-plan.md
  2026-04-12-e4-approval-center-wave-1.md
  2026-04-12-e4-approval-center-wave-1-plan.md
  2026-04-13-e4.2-approval-center-operator-wave-1.md
  2026-04-13-e4.2-approval-center-operator-wave-1-plan.md
  2026-04-14-e11-finance-runway-wave-1.md
  2026-04-14-e11-finance-runway-wave-1-plan.md
  2026-04-14-e6-github-operations-wave-1.md
  2026-04-14-e6-github-operations-wave-1-plan.md
  2026-04-14-e8-infra-health-backup-wave-1.md
  2026-04-14-e8-infra-health-backup-wave-1-plan.md
  2026-04-14-e9-cost-usage-wave-1.md
  2026-04-14-e9-cost-usage-wave-1-plan.md
  2026-04-15-e9-cost-usage-wave-2.md
  2026-04-15-e9-cost-usage-wave-2-plan.md
  2026-04-16-e10-infra-agent-wave-2.md
  2026-04-16-e12-content-backlog-wave-1.md
  2026-04-16-e8-backup-center-wave-2.md
  2026-04-16-e8-f3-snapshot-cron.md
  2026-04-16-e8-health-alerts-wave-3.md
  2026-04-17-e10-delivery-status-agent.md
  2026-04-17-e11-f1-receitas-despesas.md
  2026-04-17-e5-f4-kanban-tasks-implementation-plan.md
  2026-04-18-e6-f4-release-notes-wave-1.md
  2026-04-18-e8-f5-hardening-tracker-wave-1.md
  2026-04-19-e10-cron-dispatcher.md
  2026-04-19-e10-detached-reaper.md
  2026-04-19-e10-dispatcher-and-clarification-agents.md
  2026-04-19-e10-scrum-master-agent.md
  2026-04-19-e10-tester-agent.md
  2026-04-19-e5-f4-kanban-dev-lifecycle.md
  2026-04-21-e10-clarification-daemon-local-first.md
  2026-04-21-e10-noise-reset-prereq.md
  2026-04-21-e10-payload-completeness-gate.md
  2026-04-21-e10-scrum-master-self-test.md
  2026-04-21-e10-scrum-master-v2.md
  2026-04-21-e10-telegram-push-escalations.md
  2026-04-21-e10-telegram-reply-handler.md
  2026-04-21-e5-f4-kanban-blocked-by-schema.md
  2026-04-22-e10-oh-wave-8-fixes.md
  2026-04-22-e10-telegram-multi-bot.md
  2026-04-23-clarification-telegram-enhancement.md
)
for s in "${SPECS_OPENCLAW[@]}"; do
  git mv "35_specs/$s" "35_specs/openclaw/$s"
done
```

Expected: sem output. 48 arquivos movidos.

- [ ] **Step 3: Verificar**

```bash
ls ~/bevox-knowledge/35_specs/openclaw/*.md | wc -l
ls ~/bevox-knowledge/35_specs/*.md 2>/dev/null | wc -l
```

Expected: primeiro comando → `48`. Segundo → count do restante na raiz (esperado 64 - 48 = 16 + README = 17, mas `*.md` não match README... na verdade 64 - 48 + README = 17; mas sem as 48 = 16 restantes específicas + README.md = 17 arquivos. Será atualizado em Tasks 3-5).

- [ ] **Step 4: Commit**

```bash
cd ~/bevox-knowledge
git add 35_specs/openclaw/ 35_specs/
git commit -m "$(cat <<'EOF'
reorg(wave-1): migra 48 specs para 35_specs/openclaw/

Conforme ADR-010, specs de runtime OpenClaw (agentes E10, kanban E5/F4,
cost E9, health/backup/hardening E8, approval E4, github-ops E6, finance
E11, content E12, foundation E0, e1.1 fixes, telegram clarification)
movem-se para 35_specs/openclaw/. Git mv preserva history.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `git mv` 13 specs para `company-os/`

- [ ] **Step 1: Remover `.gitkeep`**

```bash
cd ~/bevox-knowledge
rm -f 35_specs/company-os/.gitkeep
```

- [ ] **Step 2: `git mv` em lote**

```bash
cd ~/bevox-knowledge
SPECS_CO=(
  2026-04-09-e1-knowledge-spine.md
  2026-04-10-e2-mission-control.md
  2026-04-13-e5-roadmap-delivery-os-wave-1.md
  2026-04-13-e5-roadmap-delivery-os-wave-1-plan.md
  2026-04-15-e2-canonical-agents-projection.md
  2026-04-15-e2-canonical-agents-projection-plan.md
  2026-04-16-e2-canonical-agents-detail-edit.md
  2026-04-16-e2-canonical-agents-detail-edit-plan.md
  2026-04-16-e5-delivery-tracker-wave-2.md
  2026-04-17-e5-f4-kanban-rich-ui-wave-2.md
  2026-04-17-e5-f4-sprint-planning-wave-1.md
  2026-04-17-e5-refinement-blockers-risks.md
  2026-04-23-mc-cron-management.md
)
for s in "${SPECS_CO[@]}"; do
  git mv "35_specs/$s" "35_specs/company-os/$s"
done
```

- [ ] **Step 3: Verificar**

```bash
ls ~/bevox-knowledge/35_specs/company-os/*.md | wc -l
```

Expected: `13`.

- [ ] **Step 4: Commit**

```bash
cd ~/bevox-knowledge
git add 35_specs/company-os/ 35_specs/
git commit -m "$(cat <<'EOF'
reorg(wave-1): migra 13 specs para 35_specs/company-os/

Conforme ADR-010, specs de capabilities Company OS observáveis por fora
(E1 knowledge-spine, E2 Mission Control + canonical agents, E5 tracker/
roadmap views + sprint-planning + kanban UI, mc-cron-management) movem-se
para 35_specs/company-os/.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `git mv` 1 spec para `bevox-backend/`

- [ ] **Step 1: Remover `.gitkeep`**

```bash
cd ~/bevox-knowledge
rm -f 35_specs/bevox-backend/.gitkeep
```

- [ ] **Step 2: `git mv`**

```bash
cd ~/bevox-knowledge
git mv 35_specs/2026-04-23-e13-bevox-backend-init.md 35_specs/bevox-backend/
```

- [ ] **Step 3: Verificar**

```bash
ls ~/bevox-knowledge/35_specs/bevox-backend/
```

Expected: `2026-04-23-e13-bevox-backend-init.md` (sem `.gitkeep`).

- [ ] **Step 4: Commit**

```bash
cd ~/bevox-knowledge
git add 35_specs/bevox-backend/ 35_specs/
git commit -m "$(cat <<'EOF'
reorg(wave-1): migra E13 spec para 35_specs/bevox-backend/

Spec do E13 (bevox-backend init) vai pra subpasta do próprio módulo.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `git mv` 2 specs para `_retired/`

- [ ] **Step 1: `git mv`**

```bash
cd ~/bevox-knowledge
git mv 35_specs/bevox-app-v1-spec.md _retired/
git mv 35_specs/2026-04-21-bevox-mobile-auto-unblock.md _retired/
```

- [ ] **Step 2: Verificar**

```bash
ls ~/bevox-knowledge/_retired/ | grep -E 'bevox-app|bevox-mobile-auto-unblock'
ls ~/bevox-knowledge/35_specs/*.md 2>/dev/null
```

Expected: primeiro mostra os 2 arquivos em `_retired/`; segundo mostra apenas `README.md` (raiz final limpa).

- [ ] **Step 3: Commit**

```bash
cd ~/bevox-knowledge
git commit -m "$(cat <<'EOF'
retire(wave-1): bevox-app-v1 + bevox-mobile-auto-unblock → _retired/

bevox-app-v1-spec.md: produto bevox-app archived desde 2026-04-15.
2026-04-21-bevox-mobile-auto-unblock.md: feature cancelada (ver auto-unblock-status já retired).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Atualizar cross-refs em `20_architecture/`

**Files modified (~15 arquivos):**
- `20_architecture/health-registry.md`
- `20_architecture/hardening-registry.md`
- `20_architecture/knowledge-spine.md`
- `20_architecture/content-backlog.yml`
- `20_architecture/finance-snapshot.example.yml`
- `20_architecture/cost-alerts.example.yml`
- `20_architecture/agents/delivery-status-agent.md`
- `20_architecture/agents/tester-agent.md`
- `20_architecture/agents/telegram-bot-agent-pattern.md`
- `20_architecture/agents/dispatcher-agent.md`
- `20_architecture/agents/clarification-agent.md`
- `20_architecture/agents/delivery-agent.md`
- `20_architecture/agents/documentation-agent.md`
- `20_architecture/modules/bevox-harness.md`
- `20_architecture/modules/bevox-backend.md`
- `20_architecture/agents/_retired/bevox-mobile-auto-unblock-status.md`
- `20_architecture/_tools/render-hardening-registry.py`
- `20_architecture/_tools/render-health-registry.py`

**Mapeamento completo de path antigo → novo:**

| Path antigo | Path novo |
|---|---|
| `35_specs/2026-04-09-e1-knowledge-spine.md` | `35_specs/company-os/2026-04-09-e1-knowledge-spine.md` |
| `35_specs/2026-04-10-e1.1-fix-plugin-commands.md` | `35_specs/openclaw/2026-04-10-e1.1-fix-plugin-commands.md` |
| `35_specs/2026-04-10-e1.1-telegram-approval-mode.md` | `35_specs/openclaw/2026-04-10-e1.1-telegram-approval-mode.md` |
| `35_specs/2026-04-13-e5-roadmap-delivery-os-wave-1.md` | `35_specs/company-os/2026-04-13-e5-roadmap-delivery-os-wave-1.md` |
| `35_specs/2026-04-14-e8-infra-health-backup-wave-1.md` | `35_specs/openclaw/2026-04-14-e8-infra-health-backup-wave-1.md` |
| `35_specs/2026-04-14-e11-finance-runway-wave-1.md` | `35_specs/openclaw/2026-04-14-e11-finance-runway-wave-1.md` |
| `35_specs/2026-04-15-e9-cost-usage-wave-2.md` | `35_specs/openclaw/2026-04-15-e9-cost-usage-wave-2.md` |
| `35_specs/2026-04-16-e12-content-backlog-wave-1.md` | `35_specs/openclaw/2026-04-16-e12-content-backlog-wave-1.md` |
| `35_specs/2026-04-17-e10-delivery-status-agent.md` | `35_specs/openclaw/2026-04-17-e10-delivery-status-agent.md` |
| `35_specs/2026-04-18-e8-f5-hardening-tracker-wave-1.md` | `35_specs/openclaw/2026-04-18-e8-f5-hardening-tracker-wave-1.md` |
| `35_specs/2026-04-19-e10-cron-dispatcher.md` | `35_specs/openclaw/2026-04-19-e10-cron-dispatcher.md` |
| `35_specs/2026-04-19-e10-detached-reaper.md` | `35_specs/openclaw/2026-04-19-e10-detached-reaper.md` |
| `35_specs/2026-04-19-e10-dispatcher-and-clarification-agents.md` | `35_specs/openclaw/2026-04-19-e10-dispatcher-and-clarification-agents.md` |
| `35_specs/2026-04-19-e10-tester-agent.md` | `35_specs/openclaw/2026-04-19-e10-tester-agent.md` |
| `35_specs/2026-04-22-e10-telegram-multi-bot.md` | `35_specs/openclaw/2026-04-22-e10-telegram-multi-bot.md` |
| `35_specs/2026-04-21-bevox-mobile-auto-unblock.md` | `_retired/2026-04-21-bevox-mobile-auto-unblock.md` |
| `35_specs/bevox-app-v1-spec.md` | `_retired/bevox-app-v1-spec.md` |

- [ ] **Step 1: Validar inventory de refs atuais**

```bash
cd ~/bevox-knowledge
grep -rn '35_specs/[^/]*\.md' 20_architecture/ | grep -v '/openclaw/\|/company-os/\|/bevox-backend/\|/bevox-mobile/\|/bevox-web/\|/bevox-console/\|/bevox-harness/\|/_shared/' | wc -l
```

Expected: ~35-40 refs (linhas com refs flat a migrar).

- [ ] **Step 2: Rodar script de substituição em massa**

```bash
cd ~/bevox-knowledge
python3 << 'EOF'
import re
from pathlib import Path

MAPPING = {
    "35_specs/2026-04-09-e1-knowledge-spine.md": "35_specs/company-os/2026-04-09-e1-knowledge-spine.md",
    "35_specs/2026-04-10-e1.1-fix-plugin-commands.md": "35_specs/openclaw/2026-04-10-e1.1-fix-plugin-commands.md",
    "35_specs/2026-04-10-e1.1-telegram-approval-mode.md": "35_specs/openclaw/2026-04-10-e1.1-telegram-approval-mode.md",
    "35_specs/2026-04-10-e2-mission-control.md": "35_specs/company-os/2026-04-10-e2-mission-control.md",
    "35_specs/2026-04-11-e10-functional-agents-wave-1.md": "35_specs/openclaw/2026-04-11-e10-functional-agents-wave-1.md",
    "35_specs/2026-04-11-e10-functional-agents-wave-1-plan.md": "35_specs/openclaw/2026-04-11-e10-functional-agents-wave-1-plan.md",
    "35_specs/2026-04-11-e3-agent-registry-foundation.md": "35_specs/openclaw/2026-04-11-e3-agent-registry-foundation.md",
    "35_specs/2026-04-11-e3-agent-registry-foundation-plan.md": "35_specs/openclaw/2026-04-11-e3-agent-registry-foundation-plan.md",
    "35_specs/2026-04-12-e4-approval-center-wave-1.md": "35_specs/openclaw/2026-04-12-e4-approval-center-wave-1.md",
    "35_specs/2026-04-12-e4-approval-center-wave-1-plan.md": "35_specs/openclaw/2026-04-12-e4-approval-center-wave-1-plan.md",
    "35_specs/2026-04-13-e4.2-approval-center-operator-wave-1.md": "35_specs/openclaw/2026-04-13-e4.2-approval-center-operator-wave-1.md",
    "35_specs/2026-04-13-e4.2-approval-center-operator-wave-1-plan.md": "35_specs/openclaw/2026-04-13-e4.2-approval-center-operator-wave-1-plan.md",
    "35_specs/2026-04-13-e5-roadmap-delivery-os-wave-1.md": "35_specs/company-os/2026-04-13-e5-roadmap-delivery-os-wave-1.md",
    "35_specs/2026-04-13-e5-roadmap-delivery-os-wave-1-plan.md": "35_specs/company-os/2026-04-13-e5-roadmap-delivery-os-wave-1-plan.md",
    "35_specs/2026-04-14-e11-finance-runway-wave-1.md": "35_specs/openclaw/2026-04-14-e11-finance-runway-wave-1.md",
    "35_specs/2026-04-14-e11-finance-runway-wave-1-plan.md": "35_specs/openclaw/2026-04-14-e11-finance-runway-wave-1-plan.md",
    "35_specs/2026-04-14-e6-github-operations-wave-1.md": "35_specs/openclaw/2026-04-14-e6-github-operations-wave-1.md",
    "35_specs/2026-04-14-e6-github-operations-wave-1-plan.md": "35_specs/openclaw/2026-04-14-e6-github-operations-wave-1-plan.md",
    "35_specs/2026-04-14-e8-infra-health-backup-wave-1.md": "35_specs/openclaw/2026-04-14-e8-infra-health-backup-wave-1.md",
    "35_specs/2026-04-14-e8-infra-health-backup-wave-1-plan.md": "35_specs/openclaw/2026-04-14-e8-infra-health-backup-wave-1-plan.md",
    "35_specs/2026-04-14-e9-cost-usage-wave-1.md": "35_specs/openclaw/2026-04-14-e9-cost-usage-wave-1.md",
    "35_specs/2026-04-14-e9-cost-usage-wave-1-plan.md": "35_specs/openclaw/2026-04-14-e9-cost-usage-wave-1-plan.md",
    "35_specs/2026-04-15-e2-canonical-agents-projection.md": "35_specs/company-os/2026-04-15-e2-canonical-agents-projection.md",
    "35_specs/2026-04-15-e2-canonical-agents-projection-plan.md": "35_specs/company-os/2026-04-15-e2-canonical-agents-projection-plan.md",
    "35_specs/2026-04-15-e9-cost-usage-wave-2.md": "35_specs/openclaw/2026-04-15-e9-cost-usage-wave-2.md",
    "35_specs/2026-04-15-e9-cost-usage-wave-2-plan.md": "35_specs/openclaw/2026-04-15-e9-cost-usage-wave-2-plan.md",
    "35_specs/2026-04-16-e10-infra-agent-wave-2.md": "35_specs/openclaw/2026-04-16-e10-infra-agent-wave-2.md",
    "35_specs/2026-04-16-e12-content-backlog-wave-1.md": "35_specs/openclaw/2026-04-16-e12-content-backlog-wave-1.md",
    "35_specs/2026-04-16-e2-canonical-agents-detail-edit.md": "35_specs/company-os/2026-04-16-e2-canonical-agents-detail-edit.md",
    "35_specs/2026-04-16-e2-canonical-agents-detail-edit-plan.md": "35_specs/company-os/2026-04-16-e2-canonical-agents-detail-edit-plan.md",
    "35_specs/2026-04-16-e5-delivery-tracker-wave-2.md": "35_specs/company-os/2026-04-16-e5-delivery-tracker-wave-2.md",
    "35_specs/2026-04-16-e8-backup-center-wave-2.md": "35_specs/openclaw/2026-04-16-e8-backup-center-wave-2.md",
    "35_specs/2026-04-16-e8-f3-snapshot-cron.md": "35_specs/openclaw/2026-04-16-e8-f3-snapshot-cron.md",
    "35_specs/2026-04-16-e8-health-alerts-wave-3.md": "35_specs/openclaw/2026-04-16-e8-health-alerts-wave-3.md",
    "35_specs/2026-04-17-e10-delivery-status-agent.md": "35_specs/openclaw/2026-04-17-e10-delivery-status-agent.md",
    "35_specs/2026-04-17-e11-f1-receitas-despesas.md": "35_specs/openclaw/2026-04-17-e11-f1-receitas-despesas.md",
    "35_specs/2026-04-17-e5-f4-kanban-rich-ui-wave-2.md": "35_specs/company-os/2026-04-17-e5-f4-kanban-rich-ui-wave-2.md",
    "35_specs/2026-04-17-e5-f4-kanban-tasks-implementation-plan.md": "35_specs/openclaw/2026-04-17-e5-f4-kanban-tasks-implementation-plan.md",
    "35_specs/2026-04-17-e5-f4-sprint-planning-wave-1.md": "35_specs/company-os/2026-04-17-e5-f4-sprint-planning-wave-1.md",
    "35_specs/2026-04-17-e5-refinement-blockers-risks.md": "35_specs/company-os/2026-04-17-e5-refinement-blockers-risks.md",
    "35_specs/2026-04-18-e6-f4-release-notes-wave-1.md": "35_specs/openclaw/2026-04-18-e6-f4-release-notes-wave-1.md",
    "35_specs/2026-04-18-e8-f5-hardening-tracker-wave-1.md": "35_specs/openclaw/2026-04-18-e8-f5-hardening-tracker-wave-1.md",
    "35_specs/2026-04-19-e10-cron-dispatcher.md": "35_specs/openclaw/2026-04-19-e10-cron-dispatcher.md",
    "35_specs/2026-04-19-e10-detached-reaper.md": "35_specs/openclaw/2026-04-19-e10-detached-reaper.md",
    "35_specs/2026-04-19-e10-dispatcher-and-clarification-agents.md": "35_specs/openclaw/2026-04-19-e10-dispatcher-and-clarification-agents.md",
    "35_specs/2026-04-19-e10-scrum-master-agent.md": "35_specs/openclaw/2026-04-19-e10-scrum-master-agent.md",
    "35_specs/2026-04-19-e10-tester-agent.md": "35_specs/openclaw/2026-04-19-e10-tester-agent.md",
    "35_specs/2026-04-19-e5-f4-kanban-dev-lifecycle.md": "35_specs/openclaw/2026-04-19-e5-f4-kanban-dev-lifecycle.md",
    "35_specs/2026-04-21-bevox-mobile-auto-unblock.md": "_retired/2026-04-21-bevox-mobile-auto-unblock.md",
    "35_specs/2026-04-21-e10-clarification-daemon-local-first.md": "35_specs/openclaw/2026-04-21-e10-clarification-daemon-local-first.md",
    "35_specs/2026-04-21-e10-noise-reset-prereq.md": "35_specs/openclaw/2026-04-21-e10-noise-reset-prereq.md",
    "35_specs/2026-04-21-e10-payload-completeness-gate.md": "35_specs/openclaw/2026-04-21-e10-payload-completeness-gate.md",
    "35_specs/2026-04-21-e10-scrum-master-self-test.md": "35_specs/openclaw/2026-04-21-e10-scrum-master-self-test.md",
    "35_specs/2026-04-21-e10-scrum-master-v2.md": "35_specs/openclaw/2026-04-21-e10-scrum-master-v2.md",
    "35_specs/2026-04-21-e10-telegram-push-escalations.md": "35_specs/openclaw/2026-04-21-e10-telegram-push-escalations.md",
    "35_specs/2026-04-21-e10-telegram-reply-handler.md": "35_specs/openclaw/2026-04-21-e10-telegram-reply-handler.md",
    "35_specs/2026-04-21-e5-f4-kanban-blocked-by-schema.md": "35_specs/openclaw/2026-04-21-e5-f4-kanban-blocked-by-schema.md",
    "35_specs/2026-04-22-e10-oh-wave-8-fixes.md": "35_specs/openclaw/2026-04-22-e10-oh-wave-8-fixes.md",
    "35_specs/2026-04-22-e10-telegram-multi-bot.md": "35_specs/openclaw/2026-04-22-e10-telegram-multi-bot.md",
    "35_specs/2026-04-23-clarification-telegram-enhancement.md": "35_specs/openclaw/2026-04-23-clarification-telegram-enhancement.md",
    "35_specs/2026-04-23-e13-bevox-backend-init.md": "35_specs/bevox-backend/2026-04-23-e13-bevox-backend-init.md",
    "35_specs/2026-04-23-mc-cron-management.md": "35_specs/company-os/2026-04-23-mc-cron-management.md",
    "35_specs/bevox-app-v1-spec.md": "_retired/bevox-app-v1-spec.md",
}

# Sort by descending length so longer paths match first (prevents partial overlap)
sorted_keys = sorted(MAPPING.keys(), key=len, reverse=True)

targets = list(Path("20_architecture").rglob("*.md")) + \
          list(Path("20_architecture").rglob("*.yml")) + \
          list(Path("20_architecture").rglob("*.py"))

total_changed = 0
for fpath in targets:
    try:
        content = fpath.read_text(encoding="utf-8")
    except Exception:
        continue
    new = content
    for old in sorted_keys:
        new = new.replace(old, MAPPING[old])
    if new != content:
        fpath.write_text(new, encoding="utf-8")
        total_changed += 1
        print(f"updated: {fpath}")

print(f"\nTotal arquivos modificados: {total_changed}")
EOF
```

Expected: lista de ~10-15 arquivos modificados; contagem final no final.

- [ ] **Step 3: Verificar zero refs flat residuais em `20_architecture/`**

```bash
cd ~/bevox-knowledge
grep -rn '35_specs/[^/]*\.md' 20_architecture/ | grep -v '/openclaw/\|/company-os/\|/bevox-backend/\|/bevox-mobile/\|/bevox-web/\|/bevox-console/\|/bevox-harness/\|/_shared/' | head
```

Expected: vazio (ou matches que sejam falsos positivos — e.g., menções genéricas como `35_specs/` sem nome específico).

- [ ] **Step 4: Commit**

```bash
cd ~/bevox-knowledge
git add 20_architecture/
git commit -m "$(cat <<'EOF'
docs(cross-ref): atualiza refs para novas localizações de 35_specs/

Wave-1: todos os cross-refs em 20_architecture/ (MD + YAML + Python
tools) migrados das localizações flat para subpasta de projeto
(openclaw/, company-os/, bevox-backend/) ou _retired/.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Atualizar `delivery-tracker.yml`

**Files modified:**
- `40_roadmap/delivery-tracker.yml` — todos os campos `spec:` que referenciam `35_specs/*.md` são atualizados pra novas localizações.

- [ ] **Step 1: Inventário de refs atuais**

```bash
cd ~/bevox-knowledge
grep -cE '^\s+spec: 35_specs/[^/]+\.md$' 40_roadmap/delivery-tracker.yml
```

Expected: ~20-30 (número de waves com spec field).

- [ ] **Step 2: Script de update**

```bash
cd ~/bevox-knowledge
python3 << 'EOF'
from pathlib import Path

# Mesmo mapping do Task 6
MAPPING = {
    "35_specs/2026-04-09-e1-knowledge-spine.md": "35_specs/company-os/2026-04-09-e1-knowledge-spine.md",
    "35_specs/2026-04-10-e1.1-fix-plugin-commands.md": "35_specs/openclaw/2026-04-10-e1.1-fix-plugin-commands.md",
    "35_specs/2026-04-10-e1.1-telegram-approval-mode.md": "35_specs/openclaw/2026-04-10-e1.1-telegram-approval-mode.md",
    "35_specs/2026-04-10-e2-mission-control.md": "35_specs/company-os/2026-04-10-e2-mission-control.md",
    "35_specs/2026-04-11-e10-functional-agents-wave-1.md": "35_specs/openclaw/2026-04-11-e10-functional-agents-wave-1.md",
    "35_specs/2026-04-11-e10-functional-agents-wave-1-plan.md": "35_specs/openclaw/2026-04-11-e10-functional-agents-wave-1-plan.md",
    "35_specs/2026-04-11-e3-agent-registry-foundation.md": "35_specs/openclaw/2026-04-11-e3-agent-registry-foundation.md",
    "35_specs/2026-04-11-e3-agent-registry-foundation-plan.md": "35_specs/openclaw/2026-04-11-e3-agent-registry-foundation-plan.md",
    "35_specs/2026-04-12-e4-approval-center-wave-1.md": "35_specs/openclaw/2026-04-12-e4-approval-center-wave-1.md",
    "35_specs/2026-04-12-e4-approval-center-wave-1-plan.md": "35_specs/openclaw/2026-04-12-e4-approval-center-wave-1-plan.md",
    "35_specs/2026-04-13-e4.2-approval-center-operator-wave-1.md": "35_specs/openclaw/2026-04-13-e4.2-approval-center-operator-wave-1.md",
    "35_specs/2026-04-13-e4.2-approval-center-operator-wave-1-plan.md": "35_specs/openclaw/2026-04-13-e4.2-approval-center-operator-wave-1-plan.md",
    "35_specs/2026-04-13-e5-roadmap-delivery-os-wave-1.md": "35_specs/company-os/2026-04-13-e5-roadmap-delivery-os-wave-1.md",
    "35_specs/2026-04-13-e5-roadmap-delivery-os-wave-1-plan.md": "35_specs/company-os/2026-04-13-e5-roadmap-delivery-os-wave-1-plan.md",
    "35_specs/2026-04-14-e11-finance-runway-wave-1.md": "35_specs/openclaw/2026-04-14-e11-finance-runway-wave-1.md",
    "35_specs/2026-04-14-e11-finance-runway-wave-1-plan.md": "35_specs/openclaw/2026-04-14-e11-finance-runway-wave-1-plan.md",
    "35_specs/2026-04-14-e6-github-operations-wave-1.md": "35_specs/openclaw/2026-04-14-e6-github-operations-wave-1.md",
    "35_specs/2026-04-14-e6-github-operations-wave-1-plan.md": "35_specs/openclaw/2026-04-14-e6-github-operations-wave-1-plan.md",
    "35_specs/2026-04-14-e8-infra-health-backup-wave-1.md": "35_specs/openclaw/2026-04-14-e8-infra-health-backup-wave-1.md",
    "35_specs/2026-04-14-e8-infra-health-backup-wave-1-plan.md": "35_specs/openclaw/2026-04-14-e8-infra-health-backup-wave-1-plan.md",
    "35_specs/2026-04-14-e9-cost-usage-wave-1.md": "35_specs/openclaw/2026-04-14-e9-cost-usage-wave-1.md",
    "35_specs/2026-04-14-e9-cost-usage-wave-1-plan.md": "35_specs/openclaw/2026-04-14-e9-cost-usage-wave-1-plan.md",
    "35_specs/2026-04-15-e2-canonical-agents-projection.md": "35_specs/company-os/2026-04-15-e2-canonical-agents-projection.md",
    "35_specs/2026-04-15-e2-canonical-agents-projection-plan.md": "35_specs/company-os/2026-04-15-e2-canonical-agents-projection-plan.md",
    "35_specs/2026-04-15-e9-cost-usage-wave-2.md": "35_specs/openclaw/2026-04-15-e9-cost-usage-wave-2.md",
    "35_specs/2026-04-15-e9-cost-usage-wave-2-plan.md": "35_specs/openclaw/2026-04-15-e9-cost-usage-wave-2-plan.md",
    "35_specs/2026-04-16-e10-infra-agent-wave-2.md": "35_specs/openclaw/2026-04-16-e10-infra-agent-wave-2.md",
    "35_specs/2026-04-16-e12-content-backlog-wave-1.md": "35_specs/openclaw/2026-04-16-e12-content-backlog-wave-1.md",
    "35_specs/2026-04-16-e2-canonical-agents-detail-edit.md": "35_specs/company-os/2026-04-16-e2-canonical-agents-detail-edit.md",
    "35_specs/2026-04-16-e2-canonical-agents-detail-edit-plan.md": "35_specs/company-os/2026-04-16-e2-canonical-agents-detail-edit-plan.md",
    "35_specs/2026-04-16-e5-delivery-tracker-wave-2.md": "35_specs/company-os/2026-04-16-e5-delivery-tracker-wave-2.md",
    "35_specs/2026-04-16-e8-backup-center-wave-2.md": "35_specs/openclaw/2026-04-16-e8-backup-center-wave-2.md",
    "35_specs/2026-04-16-e8-f3-snapshot-cron.md": "35_specs/openclaw/2026-04-16-e8-f3-snapshot-cron.md",
    "35_specs/2026-04-16-e8-health-alerts-wave-3.md": "35_specs/openclaw/2026-04-16-e8-health-alerts-wave-3.md",
    "35_specs/2026-04-17-e10-delivery-status-agent.md": "35_specs/openclaw/2026-04-17-e10-delivery-status-agent.md",
    "35_specs/2026-04-17-e11-f1-receitas-despesas.md": "35_specs/openclaw/2026-04-17-e11-f1-receitas-despesas.md",
    "35_specs/2026-04-17-e5-f4-kanban-rich-ui-wave-2.md": "35_specs/company-os/2026-04-17-e5-f4-kanban-rich-ui-wave-2.md",
    "35_specs/2026-04-17-e5-f4-kanban-tasks-implementation-plan.md": "35_specs/openclaw/2026-04-17-e5-f4-kanban-tasks-implementation-plan.md",
    "35_specs/2026-04-17-e5-f4-sprint-planning-wave-1.md": "35_specs/company-os/2026-04-17-e5-f4-sprint-planning-wave-1.md",
    "35_specs/2026-04-17-e5-refinement-blockers-risks.md": "35_specs/company-os/2026-04-17-e5-refinement-blockers-risks.md",
    "35_specs/2026-04-18-e6-f4-release-notes-wave-1.md": "35_specs/openclaw/2026-04-18-e6-f4-release-notes-wave-1.md",
    "35_specs/2026-04-18-e8-f5-hardening-tracker-wave-1.md": "35_specs/openclaw/2026-04-18-e8-f5-hardening-tracker-wave-1.md",
    "35_specs/2026-04-19-e10-cron-dispatcher.md": "35_specs/openclaw/2026-04-19-e10-cron-dispatcher.md",
    "35_specs/2026-04-19-e10-detached-reaper.md": "35_specs/openclaw/2026-04-19-e10-detached-reaper.md",
    "35_specs/2026-04-19-e10-dispatcher-and-clarification-agents.md": "35_specs/openclaw/2026-04-19-e10-dispatcher-and-clarification-agents.md",
    "35_specs/2026-04-19-e10-scrum-master-agent.md": "35_specs/openclaw/2026-04-19-e10-scrum-master-agent.md",
    "35_specs/2026-04-19-e10-tester-agent.md": "35_specs/openclaw/2026-04-19-e10-tester-agent.md",
    "35_specs/2026-04-19-e5-f4-kanban-dev-lifecycle.md": "35_specs/openclaw/2026-04-19-e5-f4-kanban-dev-lifecycle.md",
    "35_specs/2026-04-21-bevox-mobile-auto-unblock.md": "_retired/2026-04-21-bevox-mobile-auto-unblock.md",
    "35_specs/2026-04-21-e10-clarification-daemon-local-first.md": "35_specs/openclaw/2026-04-21-e10-clarification-daemon-local-first.md",
    "35_specs/2026-04-21-e10-noise-reset-prereq.md": "35_specs/openclaw/2026-04-21-e10-noise-reset-prereq.md",
    "35_specs/2026-04-21-e10-payload-completeness-gate.md": "35_specs/openclaw/2026-04-21-e10-payload-completeness-gate.md",
    "35_specs/2026-04-21-e10-scrum-master-self-test.md": "35_specs/openclaw/2026-04-21-e10-scrum-master-self-test.md",
    "35_specs/2026-04-21-e10-scrum-master-v2.md": "35_specs/openclaw/2026-04-21-e10-scrum-master-v2.md",
    "35_specs/2026-04-21-e10-telegram-push-escalations.md": "35_specs/openclaw/2026-04-21-e10-telegram-push-escalations.md",
    "35_specs/2026-04-21-e10-telegram-reply-handler.md": "35_specs/openclaw/2026-04-21-e10-telegram-reply-handler.md",
    "35_specs/2026-04-21-e5-f4-kanban-blocked-by-schema.md": "35_specs/openclaw/2026-04-21-e5-f4-kanban-blocked-by-schema.md",
    "35_specs/2026-04-22-e10-oh-wave-8-fixes.md": "35_specs/openclaw/2026-04-22-e10-oh-wave-8-fixes.md",
    "35_specs/2026-04-22-e10-telegram-multi-bot.md": "35_specs/openclaw/2026-04-22-e10-telegram-multi-bot.md",
    "35_specs/2026-04-23-clarification-telegram-enhancement.md": "35_specs/openclaw/2026-04-23-clarification-telegram-enhancement.md",
    "35_specs/2026-04-23-e13-bevox-backend-init.md": "35_specs/bevox-backend/2026-04-23-e13-bevox-backend-init.md",
    "35_specs/2026-04-23-mc-cron-management.md": "35_specs/company-os/2026-04-23-mc-cron-management.md",
    "35_specs/bevox-app-v1-spec.md": "_retired/bevox-app-v1-spec.md",
}

sorted_keys = sorted(MAPPING.keys(), key=len, reverse=True)
p = Path("40_roadmap/delivery-tracker.yml")
content = p.read_text(encoding="utf-8")
new = content
for old in sorted_keys:
    new = new.replace(old, MAPPING[old])
p.write_text(new, encoding="utf-8")
print("done" if new != content else "no changes")
EOF
```

- [ ] **Step 3: Verificar zero refs flat residuais**

```bash
cd ~/bevox-knowledge
grep -cE '^\s+spec: 35_specs/[^/]+\.md$' 40_roadmap/delivery-tracker.yml
```

Expected: `0` (todos os `spec:` agora com subpath de projeto ou em `_retired/`).

- [ ] **Step 4: Commit**

```bash
cd ~/bevox-knowledge
git add 40_roadmap/delivery-tracker.yml
git commit -m "$(cat <<'EOF'
tracker(wave-1): atualiza campo spec para novas localizações

Todos os entries do delivery-tracker agora apontam para subpasta de
projeto (openclaw/, company-os/, bevox-backend/) ou _retired/.
Mission Control /api/delivery/tracker continua funcionando sem
mudança de código (apenas lê o YAML e renderiza).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Validação global — zero refs flat residuais

**Files:** nenhum — só verificação.

- [ ] **Step 1: Grep global em todo o bevox-knowledge**

```bash
cd ~/bevox-knowledge
grep -rnE '\b35_specs/[^/]*\.md\b' . \
  --include='*.md' --include='*.yml' --include='*.yaml' --include='*.py' \
  --exclude-dir=.git --exclude-dir=_retired \
  | grep -v '/openclaw/\|/company-os/\|/bevox-backend/\|/bevox-mobile/\|/bevox-web/\|/bevox-console/\|/bevox-harness/\|/_shared/'
```

Expected: 0 matches (ou apenas matches em `35_specs/README.md` menções, que são legítimas — `README.md` não é um spec de projeto).

Se houver refs residuais a specs migradas, voltar a Tasks 6-7 para corrigir e refazer.

---

## Task 9: Atualizar `mission-control/src/lib/kanban/paths.ts`

**Files:**
- Modify: `~/code/mission-control/src/lib/kanban/paths.ts` — docstring linha 7.

- [ ] **Step 1: Criar branch wave-1**

```bash
cd ~/code/mission-control
git status --short
git checkout -b draft/knowledge-reorg-wave-1
```

Expected: working tree limpa, em `draft/knowledge-reorg-wave-1`.

- [ ] **Step 2: Edit linha 7**

Substituir a linha:
```
 * Spec: bevox-knowledge/35_specs/2026-04-17-e5-f4-sprint-planning-wave-1.md
```

por:
```
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-17-e5-f4-sprint-planning-wave-1.md
```

- [ ] **Step 3: Verificar**

```bash
grep -n 'Spec:' ~/code/mission-control/src/lib/kanban/paths.ts
```

Expected: linha mostra `35_specs/company-os/2026-04-17-...`.

- [ ] **Step 4: Commit**

```bash
cd ~/code/mission-control
git add src/lib/kanban/paths.ts
git commit -m "$(cat <<'EOF'
docs(kanban): update spec path ref (wave-1 reorg)

Sprint-planning spec moved to 35_specs/company-os/ per ADR-010.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Atualizar `mission-control/docs/OPERATING.md`

**Files:**
- Modify: `~/code/mission-control/docs/OPERATING.md` — linha com ref à spec E9.

- [ ] **Step 1: Localizar linha**

```bash
grep -n '35_specs/2026-04-14-e9-cost-usage-wave-1' ~/code/mission-control/docs/OPERATING.md
```

Expected: 1 linha encontrada.

- [ ] **Step 2: Edit**

Substituir:
```
  `bevox-knowledge/35_specs/2026-04-14-e9-cost-usage-wave-1.md`
```

por:
```
  `bevox-knowledge/35_specs/openclaw/2026-04-14-e9-cost-usage-wave-1.md`
```

- [ ] **Step 3: Verificar**

```bash
grep -n 'e9-cost-usage' ~/code/mission-control/docs/OPERATING.md
```

Expected: linha mostra `35_specs/openclaw/2026-04-14-e9-cost-usage-wave-1.md`.

- [ ] **Step 4: Commit**

```bash
cd ~/code/mission-control
git add docs/OPERATING.md
git commit -m "$(cat <<'EOF'
docs(operating): update E9 spec path ref (wave-1 reorg)

E9 cost-usage spec moved to 35_specs/openclaw/ per ADR-010.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Smoke test end-to-end

**Files:** nenhum — só verificação.

- [ ] **Step 1: bevox-knowledge — raiz de 35_specs limpa**

```bash
cd ~/bevox-knowledge
ls 35_specs/*.md 2>/dev/null
```

Expected: só `35_specs/README.md`.

- [ ] **Step 2: Contagens por subpasta**

```bash
cd ~/bevox-knowledge
echo "openclaw: $(ls 35_specs/openclaw/*.md 2>/dev/null | wc -l)"
echo "company-os: $(ls 35_specs/company-os/*.md 2>/dev/null | wc -l)"
echo "bevox-backend: $(ls 35_specs/bevox-backend/*.md 2>/dev/null | wc -l)"
echo "_shared: $(ls 35_specs/_shared/*.md 2>/dev/null | wc -l)"
echo "_retired (bevox-app + bevox-mobile-auto-unblock): $(ls _retired/bevox-app-v1-spec.md _retired/2026-04-21-bevox-mobile-auto-unblock.md 2>/dev/null | wc -l)"
```

Expected:
```
openclaw: 48
company-os: 13
bevox-backend: 1
_shared: 1
_retired (bevox-app + bevox-mobile-auto-unblock): 2
```

- [ ] **Step 3: knowledge-sync status — aceita subpaths sem erro**

```bash
bash ~/code/knowledge-sync/skill/scripts/status.sh 2>&1 | head -15
```

Expected: status mostra `draft/knowledge-reorg-wave-1` como branch, working tree clean (ou mostra os commits da wave-1 como ahead), sem erro de classificação.

- [ ] **Step 4: Mission Control tracker API responde**

Se Mission Control estiver rodando em localhost:3000:
```bash
curl -fsS http://localhost:3000/api/delivery/tracker | python3 -m json.tool | head -20 2>&1 || echo "(MC offline — ignorar se dev server não está up)"
```

Expected: JSON válido com epics/waves. Não precisa estar rodando — basta que o YAML seja parseável.

Verificação alternativa (sem MC rodando):
```bash
python3 -c "
import yaml
with open('~/bevox-knowledge/40_roadmap/delivery-tracker.yml') as f:
    data = yaml.safe_load(f)
print('epics:', len(data.get('epics', [])))
# pick one wave with spec field and print it
for epic in data['epics'][:3]:
    for wave in epic.get('waves', []):
        if wave.get('spec'):
            print(f'{epic[\"id\"]}/{wave[\"id\"]}: {wave[\"spec\"]}')
            break
"
```

Expected: YAML parsea sem erro; spec paths mostram subpath de projeto (ex: `35_specs/company-os/2026-04-09-e1-knowledge-spine.md`).

- [ ] **Step 5: scrum-master-agent reconhece novos paths**

```bash
python3 -c "
import re
# Regex de scrum-master-agent/lib/parser.py:68
pat = re.compile(r'\`(bevox-knowledge/(?:35_specs|30_adr|20_architecture)/[^\s\`]+\.md)\`')
test = '\`bevox-knowledge/35_specs/openclaw/2026-04-19-e10-scrum-master-agent.md\`'
m = pat.search(test)
assert m, 'Regex nao matchou subpath de openclaw'
print('scrum-master-agent regex OK:', m.group(1))
"
```

Expected: `scrum-master-agent regex OK: bevox-knowledge/35_specs/openclaw/2026-04-19-e10-scrum-master-agent.md`.

- [ ] **Step 6: bash case (approval.sh) classifica subpaths**

```bash
bash -c '
f="35_specs/openclaw/2026-04-19-e10-scrum-master-agent.md"
case "$f" in
  30_adr/ADR-*.md) echo adr-aceita-or-canonical ;;
  20_architecture/system-map.md|20_architecture/knowledge-spine.md) echo core ;;
  00_inbox/*) echo inbox ;;
  20_architecture/*|10_prd/*|30_adr/*|35_specs/*|40_roadmap/*|50_releases/*|60_customer-feedback/*|70_metrics/*) echo canonical-other ;;
  *) echo other ;;
esac
'
```

Expected: `canonical-other` (subpath matcha).

- [ ] **Step 7: Commit (N/A — só verificação)**

Se QUALQUER smoke-check falhar: **STOP**, reportar BLOCKED, não prosseguir pra Task 12.

---

## Task 12: Atualizar memória `project_knowledge_reorg.md`

**Files:**
- Modify: `~/.claude/projects/-home-you--openclaw/memory/project_knowledge_reorg.md`

- [ ] **Step 1: Substituir linha de status wave-1 e próximo passo**

No arquivo, localizar a seção `## Status das waves` e substituir:

```
- ⏭️ **Wave-1** — próxima. `35_specs/` (66 specs classificados + git mv + consumidores atomicamente atualizados).
```

por:

```
- ✅ **Wave-1** (AAAA-MM-DD) — 64 specs migrados: 48 → openclaw/, 13 → company-os/, 1 → bevox-backend/, 2 → _retired/. README.md mantido na raiz (exceção documental). Cross-refs em 20_architecture/ (15+ arquivos) e delivery-tracker.yml atualizados. Mission-control: 2 docstrings (kanban/paths.ts + OPERATING.md) atualizadas. Consumidores knowledge-sync/openclaw: zero mudança de código necessária (bash case e Python regex aceitam subpaths — testado). Branches: `draft/knowledge-reorg-wave-1` em bevox-knowledge (acumula wave-0+wave-1) e em mission-control.
- ⏭️ **Wave-2** — próxima: `40_roadmap/` (delivery-tracker.yml → `_shared/`; mission-control/paths.ts estendido com BEVOX_SUBPATHS).
```

Substituir `AAAA-MM-DD` pela data real de execução.

Também substituir a linha:
```
- 🔜 **Wave-2** — `40_roadmap/` (delivery-tracker.yml → `_shared/`; mission-control/paths.ts estendido com BEVOX_SUBPATHS).
```

por (remover — já está acima como ⏭️ próxima).

- [ ] **Step 2: Verificar**

```bash
grep -c "Wave-1" ~/.claude/projects/-home-you--openclaw/memory/project_knowledge_reorg.md
grep -c "Wave-2" ~/.claude/projects/-home-you--openclaw/memory/project_knowledge_reorg.md
```

Expected: Wave-1 `1`, Wave-2 `1`.

- [ ] **Step 3: N/A (memory não é git-tracked)**

---

## Post-wave: decisões pendentes para Bernard

Wave-1 fica em branches `draft/knowledge-reorg-wave-1`:
- `bevox-knowledge` — acumula wave-0 + wave-1
- `mission-control` — draft exclusivo

Para aprovação canônica:
1. Bernard revisa cada branch.
2. Push do draft opcional (gera PR de review no GitHub).
3. Merge canônico em `main` de ambos, em ordem: bevox-knowledge primeiro (source of truth), depois mission-control.

Rollback: `git reset --hard pre-knowledge-reorg` nos 2 repos afetados.

---

## Self-Review

**Spec coverage check (§4 wave-1 da spec canônica):**
- ✅ Classificação dos 66 specs em PR de review (foi feito em preflight no chat) — Task 2-5 executam
- ✅ `git mv` em massa — Tasks 2-5
- ✅ Update de 25+ cross-refs internos em `20_architecture/*.md` — Task 6
- ✅ Update `delivery-tracker.yml` campo `spec:` — Task 7
- ✅ Consumidores atomicamente atualizados:
  - ✅ `knowledge-sync/skill/lib/approval.sh` — VERIFICADO (bash case matcha subpath; sem mudança necessária); Task 11 step 6 valida
  - ✅ `openclaw/delivery/cli.py` — sem mudança (Python `.relative_to()` trabalha com qualquer profundidade)
  - ✅ `openclaw/scrum-master-agent/lib/parser.py` — sem mudança; Task 11 step 5 valida
  - ✅ `openclaw/clarification-agent/lib/context_loader.py` — sem mudança (wave-1 não toca ADR; prefix check aceita subpath)
  - ✅ `openclaw/tester-agent/lib/context_loader.py` — idem
- ✅ `mission-control/src/lib/kanban/paths.ts` — Task 9
- ✅ `mission-control/docs/OPERATING.md` — Task 10
- ✅ Smoke (knowledge-sync status, Mission Control não precisa estar rodando, spec resolution via regex) — Task 11
- ✅ Validação: grep retorna 0 refs flat residuais — Task 8

**Placeholder check:** nenhum "TBD/TODO/later". Task 12 usa `AAAA-MM-DD` como placeholder explicitamente instruído a substituir.

**Consistency check:** mapping MAPPING em Tasks 6 e 7 é idêntico (contém as 64 migrações + bevox-app-v1-spec). Commit messages coerentes com os paths alvo. Branch naming uniforme (`draft/knowledge-reorg-wave-1`).

---

## Execution Handoff

Plan completo e salvo em `~/.openclaw/docs/superpowers/plans/2026-04-24-knowledge-reorg-wave-1.md`. Duas opções de execução:

1. **Subagent-Driven (recomendada)** — 12 tasks, dispatch fresh por task, revisão entre tasks, iteração rápida. Tarefas 2-5 (git mv) são quase idênticas em estrutura — posso agrupar em 1 dispatch se preferir.

2. **Inline Execution** — executo nesta sessão com executing-plans, batch com checkpoints.

Qual abordagem?
