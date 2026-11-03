# Knowledge Reorg Wave-0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar wave-0 da reorg do bevox-knowledge — fundação documental e estrutural, sem mover conteúdo canônico.

**Architecture:** Wave 100% docs/infra: cria ADR-010 canonicalizando a nova convenção, materializa a árvore de 72 subpastas vazias com `.gitkeep`, supersedes spec 2026-04-19, fixa tags de rollback em 4 repos, e atualiza docs operacionais do OpenClaw. Sem mudança de código — consumidores (knowledge-sync, mission-control) continuam lendo layout flat atual.

**Tech Stack:** bash, git, markdown. Nenhum runtime novo.

**Pré-requisito já concluído (pre-wave-0):** `.openclaw/` canonicalizado como `bernardTavares/openclaw` (private) em 2026-04-24.

**Spec canônica:** `bevox-knowledge/35_specs/2026-04-24-knowledge-reorg-company-os-separation.md` (branch `draft/knowledge-reorg-spec`, commit `6d676d4`)

**Branch de trabalho:** `draft/knowledge-reorg-wave-0` em bevox-knowledge (rename do `draft/knowledge-reorg-spec` existente — o commit da spec já é parte da wave-0). Outros repos (openclaw, knowledge-sync, mission-control) tocam `main` diretamente só para criar a tag `pre-knowledge-reorg` (tag não altera working tree). Edições em `.openclaw/CLAUDE.md` e memory entram via branch `draft/knowledge-reorg-wave-0` no repo openclaw.

---

## File Structure

**Criam-se em `bevox-knowledge/`:**
- `30_adr/_shared/ADR-010-knowledge-project-separation.md` — ADR canônica supersedes 2026-04-19
- 72 × `<folder>/<subpath>/.gitkeep` — materializa subpastas vazias

**Modificam-se em `bevox-knowledge/`:**
- `README.md` — documenta nova convenção
- `30_adr/README.md` — reflete projetificação com `_shared/`
- `40_roadmap/README.md` — alinha convenção de subpastas

**Movem-se em `bevox-knowledge/`:**
- `35_specs/2026-04-19-company-os-bevox-knowledge-domain-separation.md` → `_retired/`
- `35_specs/2026-04-24-knowledge-reorg-company-os-separation.md` → `35_specs/_shared/`

**Modificam-se em `~/.openclaw/`:**
- `CLAUDE.md` §§3, 3.1, 6.1 — reescritos pra refletir nova hierarquia
- `workspace-shared/memory/reference_bevox_knowledge.md` — atualizado com nova estrutura

**Tags git (4 repos):**
- `bevox-knowledge`, `~/code/knowledge-sync`, `~/.openclaw`, `~/code/mission-control` — tag `pre-knowledge-reorg` em `main`

---

## Task 1: Criar tags de segurança `pre-knowledge-reorg` nos 4 repos

**Files:**
- Tag em: `~/bevox-knowledge` main
- Tag em: `~/code/knowledge-sync` main
- Tag em: `~/.openclaw` main
- Tag em: `~/code/mission-control` main

**Motivo:** rollback catastrófico via `git reset --hard pre-knowledge-reorg` nos repos afetados.

- [ ] **Step 1: Confirmar que os 4 repos têm `main` limpo**

```bash
for d in ~/bevox-knowledge ~/code/knowledge-sync ~/.openclaw ~/code/mission-control; do
  echo "=== $d ==="
  git -C "$d" status --short
  git -C "$d" branch --show-current
done
```

Expected: todos em `main` (ou em branches limpas) sem arquivos modificados fora da spec/branches draft atuais. Se algo estiver sujo, stash ou resolver antes de taguear.

Nota: `bevox-knowledge` está hoje em `draft/knowledge-reorg-spec`. Fazer `git -C ~/bevox-knowledge checkout main` antes do passo 2 pra tag apontar pro main pre-reorg real.

- [ ] **Step 2: Criar as tags**

```bash
for d in ~/bevox-knowledge ~/code/knowledge-sync ~/.openclaw ~/code/mission-control; do
  git -C "$d" tag -a pre-knowledge-reorg -m "Baseline before bevox-knowledge reorg (2026-04-24). See bevox-knowledge/35_specs/2026-04-24-knowledge-reorg-company-os-separation.md"
done
```

Expected: cada comando sem output (tag criada silenciosamente).

- [ ] **Step 3: Pushar as tags pros remotes**

```bash
for d in ~/bevox-knowledge ~/code/knowledge-sync ~/.openclaw ~/code/mission-control; do
  echo "=== $d ==="
  git -C "$d" push origin pre-knowledge-reorg
done
```

Expected: 4 × `new tag pre-knowledge-reorg -> pre-knowledge-reorg`.

- [ ] **Step 4: Verificar tags remotas via gh**

```bash
for repo in bevox-knowledge knowledge-sync openclaw mission-control; do
  echo "=== $repo ==="
  gh api repos/bernardTavares/$repo/tags --jq '.[] | select(.name=="pre-knowledge-reorg") | {name, commit: .commit.sha}' 2>&1
done
```

Expected: 4 blocos JSON com a tag `pre-knowledge-reorg` em cada repo.

- [ ] **Step 5: Voltar para a branch de trabalho no bevox-knowledge**

```bash
git -C ~/bevox-knowledge branch -m draft/knowledge-reorg-spec draft/knowledge-reorg-wave-0
git -C ~/bevox-knowledge checkout draft/knowledge-reorg-wave-0
git -C ~/bevox-knowledge log --oneline -3
```

Expected: HEAD está em `draft/knowledge-reorg-wave-0`, último commit é `6d676d4 spec: knowledge-reorg 2026-04-24 (supersedes 2026-04-19)`.

- [ ] **Step 6: Commit (N/A — tags não geram commits)**

Tags anotadas não entram em histórico linear — apenas referenciam. Nada a commitar neste task.

---

## Task 2: Criar ADR-010 — Knowledge Project Separation

**Files:**
- Create: `~/bevox-knowledge/30_adr/_shared/ADR-010-knowledge-project-separation.md`

Nota: `30_adr/_shared/` ainda não existe; será criado implicitamente pelo `git add` deste arquivo. A criação das 72 subpastas vazias com `.gitkeep` é o Task 3, mas `_shared/` especificamente passa a existir já aqui.

- [ ] **Step 1: Criar diretório e arquivo**

```bash
mkdir -p ~/bevox-knowledge/30_adr/_shared
```

Expected: sem output.

- [ ] **Step 2: Escrever conteúdo da ADR-010**

Conteúdo completo (copiar literal para `~/bevox-knowledge/30_adr/_shared/ADR-010-knowledge-project-separation.md`):

```markdown
# ADR-010 — Knowledge Project Separation (uniforme)

**Data:** 2026-04-24
**Status:** aceito
**Supersedes:** spec `35_specs/2026-04-19-company-os-bevox-knowledge-domain-separation.md` (movida para `_retired/` nesta wave)
**Spec de execução:** `35_specs/_shared/2026-04-24-knowledge-reorg-company-os-separation.md`

## Contexto

A convenção aceita em 2026-04-19 subdividia apenas `10_prd/`, `35_specs/`, `40_roadmap/` e `50_releases/` por domínio, mantendo `30_adr/` e `20_architecture/` flat. Na prática isso criou dois padrões coexistindo no mesmo repo e manteve os 66 specs legados todos na raiz — sem melhoria de navegação pros consumidores (Mission Control, knowledge-sync, openclaw).

## Decisão

Adotar separação por projeto **uniforme** em todos os folders canônicos do `bevox-knowledge`.

### 1. Subpastas obrigatórias

Todo folder canônico (`00_inbox/`, `10_prd/`, `20_architecture/`, `30_adr/`, `35_specs/`, `40_roadmap/`, `50_releases/`, `60_customer-feedback/`, `70_metrics/`) recebe as mesmas 8 subpastas:

- `_shared/` — governança e infra transversal
- `bevox-backend/` — backend compartilhado de aplicação
- `bevox-console/` — super-admin / backoffice interno
- `bevox-harness/` — runtime agent-first da secretária IA
- `bevox-mobile/` — app mobile do operador
- `bevox-web/` — app web do cliente
- `openclaw/` — runtime Company OS (agentes, skills, delivery, kanban-tasks, gateway, finance, health, hardening)
- `company-os/` — capabilities Company OS não-OpenClaw (Mission Control, Vox, Knowledge-Sync, Agent Registry, Approval Center)

### 2. Exceções

- `99_templates/` permanece flat — templates são esquema, não conteúdo de projeto.
- `_retired/` permanece flat — archive layer por data, sem projeto.

### 3. Invariantes

- Nenhum `.md` fica solto na raiz de um folder canônico.
- Uma subpasta de projeto pode estar vazia (contém só `.gitkeep`) até receber o primeiro artefato.
- `_shared/` é **governança**, não catch-all. Se um artefato pertence ao runtime do Company OS, vai em `openclaw/` ou `company-os/` conforme escopo.

### 4. Regra de desempate `openclaw/` vs `company-os/`

| Vai em `openclaw/` | Vai em `company-os/` |
|---|---|
| Comportamento executado dentro de `~/.openclaw/` | Capabilities Company OS observáveis por fora |
| Agentes operacionais, kanban, gateway, runners | Mission Control (app), Vox, Knowledge-Sync, Agent Registry, Approval Center |

Se o artefato descreve comportamento **dentro** de `~/.openclaw/`, vai em `openclaw/`. Se descreve capability do Company OS observável por fora (dashboard, política, spine documental), vai em `company-os/`.

## Consequências

### Positivas

- Taxonomia uniforme; um padrão só.
- Navegação por projeto habilitada pros consumidores.
- `_shared/` dá endereço explícito a governança transversal (security, hardening, ADRs de boundary, delivery-tracker.yml).
- Expansão futura pros 5 produtos Bevox tem home pronta (subpastas vazias com `.gitkeep`).

### Negativas

- Migração dos 66 specs legados é mudança grande; exige wave dedicada (wave-1).
- Cross-refs internos (links markdown) precisam ser atualizados em ondas.
- Consumidores (`knowledge-sync/skill/lib/approval.sh`, parsers do OpenClaw, paths do Mission Control) precisam de regex/paths adaptados — feito atomicamente junto com cada wave de conteúdo.

## Plano de execução

Execução detalhada em 9 waves na spec `35_specs/_shared/2026-04-24-knowledge-reorg-company-os-separation.md`. Estratégia:

- **Pre-wave-0 (concluída):** `.openclaw/` canonicalizado como repo `bernardTavares/openclaw`.
- **Wave-0 (esta entrega):** fundação documental (esta ADR + 72 subpastas vazias + supersede da 2026-04-19 + docs do OpenClaw + tags de rollback).
- **Waves 1-7:** movimentação de conteúdo por folder, atomicamente com atualização dos consumidores. Sem compat layer.
- **Wave-8:** cleanup + release note.

Rollback catastrófico: `git reset --hard pre-knowledge-reorg` nos 4 repos tagged (bevox-knowledge, knowledge-sync, openclaw, mission-control).
```

- [ ] **Step 3: Verificar conteúdo**

```bash
head -20 ~/bevox-knowledge/30_adr/_shared/ADR-010-knowledge-project-separation.md
wc -l ~/bevox-knowledge/30_adr/_shared/ADR-010-knowledge-project-separation.md
```

Expected: título "# ADR-010 — Knowledge Project Separation (uniforme)" e ~70-80 linhas.

- [ ] **Step 4: Commit**

```bash
cd ~/bevox-knowledge
git add 30_adr/_shared/ADR-010-knowledge-project-separation.md
git commit -m "$(cat <<'EOF'
adr(ADR-010): knowledge project separation uniforme

Canoniza separação por projeto em todos os folders canônicos do
bevox-knowledge. Supersedes spec 2026-04-19 (convenção parcial).

Supersedes: 35_specs/2026-04-19-company-os-bevox-knowledge-domain-separation.md
Spec de execução: 35_specs/_shared/2026-04-24-knowledge-reorg-company-os-separation.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git log --oneline -2
```

Expected: último commit é `adr(ADR-010): knowledge project separation uniforme`.

---

## Task 3: Materializar 72 subpastas vazias com `.gitkeep`

**Files:**
- Create: 72 × `~/bevox-knowledge/<folder>/<subpath>/.gitkeep`

**Cobre:** 9 folders canônicos × 8 subpastas cada = 72 `.gitkeep`. A subpasta `30_adr/_shared/` já existe do Task 2 (com ADR-010) — não precisa `.gitkeep` lá (pasta já populada). Então efetivamente 71 `.gitkeep`.

Folders canônicos: `00_inbox`, `10_prd`, `20_architecture`, `30_adr`, `35_specs`, `40_roadmap`, `50_releases`, `60_customer-feedback`, `70_metrics`.

Subpastas: `_shared`, `bevox-backend`, `bevox-console`, `bevox-harness`, `bevox-mobile`, `bevox-web`, `openclaw`, `company-os`.

- [ ] **Step 1: Criar todas as subpastas e `.gitkeep`**

```bash
cd ~/bevox-knowledge
FOLDERS=(00_inbox 10_prd 20_architecture 30_adr 35_specs 40_roadmap 50_releases 60_customer-feedback 70_metrics)
SUBS=(_shared bevox-backend bevox-console bevox-harness bevox-mobile bevox-web openclaw company-os)

for f in "${FOLDERS[@]}"; do
  for s in "${SUBS[@]}"; do
    mkdir -p "$f/$s"
    # criar .gitkeep só se a pasta estiver vazia
    if [ -z "$(ls -A "$f/$s" 2>/dev/null)" ]; then
      touch "$f/$s/.gitkeep"
    fi
  done
done
```

Expected: sem output. Pasta `30_adr/_shared/` não recebe `.gitkeep` porque tem ADR-010.

- [ ] **Step 2: Verificar contagem**

```bash
find 00_inbox 10_prd 20_architecture 30_adr 35_specs 40_roadmap 50_releases 60_customer-feedback 70_metrics -name .gitkeep -type f | wc -l
```

Expected: `71` (72 subpastas totais menos `30_adr/_shared/` que já tem ADR-010).

- [ ] **Step 3: Verificar estrutura**

```bash
for f in 00_inbox 10_prd 20_architecture 30_adr 35_specs 40_roadmap 50_releases 60_customer-feedback 70_metrics; do
  echo "=== $f ==="
  ls -d "$f"/*/ 2>/dev/null | awk -F/ '{print "  "$(NF-1)}'
done
```

Expected: cada folder canônico mostra as 8 subpastas (`_shared`, `bevox-backend`, `bevox-console`, `bevox-harness`, `bevox-mobile`, `bevox-web`, `openclaw`, `company-os`).

- [ ] **Step 4: Commit**

```bash
cd ~/bevox-knowledge
git add -A 00_inbox 10_prd 20_architecture 30_adr 35_specs 40_roadmap 50_releases 60_customer-feedback 70_metrics
git commit -m "$(cat <<'EOF'
chore(reorg): materializa 71 subpastas vazias com .gitkeep

Wave-0 da reorg. Conforme ADR-010, cada folder canônico passa a ter
8 subpastas fixas (_shared + 7 projetos). Conteúdo migra em ondas
posteriores; nesta wave só a estrutura vazia.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git log --oneline -3
```

Expected: commit "chore(reorg): materializa 71 subpastas vazias..." no topo.

---

## Task 4: Atualizar `bevox-knowledge/README.md`

**Files:**
- Modify: `~/bevox-knowledge/README.md`

Atualiza seção que descreve a estrutura do repo pra refletir convenção uniforme de ADR-010.

- [ ] **Step 1: Ler README atual**

```bash
cat ~/bevox-knowledge/README.md
```

Expected: README de ~3.5 KB com descrição dos folders e citação à spec 2026-04-19.

- [ ] **Step 2: Rewrite do README**

Conteúdo alvo (substituir inteiro):

```markdown
# Bevox Knowledge — Fonte Única de Verdade

Este repositório é a **fonte única de verdade documental** do ecossistema Bevox: PRDs, ADRs, roadmaps, arquitetura e decisões aceitas vivem aqui. Runtime (Mission Control, OpenClaw, knowledge-sync) lê deste repo; nunca escreve canonicamente sem approval.

## Hierarquia canônica

ADR-010 define a convenção de organização. Todo folder canônico abaixo tem as **mesmas 8 subpastas**:

- `_shared/` — governança e infra transversal (ADRs de boundary, security-posture, delivery-tracker, etc.)
- `bevox-backend/`
- `bevox-console/`
- `bevox-harness/`
- `bevox-mobile/`
- `bevox-web/`
- `openclaw/` — runtime Company OS (agentes, kanban, gateway, runners)
- `company-os/` — capabilities Company OS não-OpenClaw (Mission Control, Vox, Knowledge-Sync, Agent Registry, Approval Center)

## Folders canônicos

| Folder | Propósito |
|---|---|
| `00_inbox/` | Fila de captura rápida; items aguardando classificação |
| `10_prd/` | Product Requirements Documents |
| `20_architecture/` | Documentação técnica e operacional; topologia, agentes, módulos |
| `30_adr/` | Architecture Decision Records aceitos |
| `35_specs/` | Specs de implementação (epic, wave, feature) |
| `40_roadmap/` | Roadmap estratégico e tracker de delivery |
| `50_releases/` | Release notes e changelog |
| `60_customer-feedback/` | Feedback e pesquisa de cliente |
| `70_metrics/` | Métricas de produto e operação |

## Exceções (permanecem flat)

- `99_templates/` — templates de documento por tipo de artefato
- `_retired/` — arquivo histórico; documentos retirados (por data)

## Regras

- Nenhum `.md` solto na raiz de um folder canônico (exceto templates e retired).
- `_shared/` **não é catch-all**. Se pertence ao Company OS runtime, vai em `openclaw/` ou `company-os/` conforme escopo.
- `main` = conteúdo aceito/canônico. `draft/*` = propostas/rascunhos/revisão.

## Referências principais

- **ADR-010** — `30_adr/_shared/ADR-010-knowledge-project-separation.md` — convenção uniforme de separação por projeto
- **ADR-001** — `30_adr/_shared/ADR-001-company-os-boundary.md` — boundary Company OS
- **ADR-002** — `30_adr/_shared/ADR-002-system-topology.md` — topologia canônica
- **ADR-005** — `30_adr/_shared/ADR-005-knowledge-source-of-truth.md` — este repo como SoT
- **Delivery tracker** — `40_roadmap/_shared/delivery-tracker.yml` — estado de execução dos epics (após wave-2)

## Reorg em andamento

A separação uniforme foi aprovada em 2026-04-24 via ADR-010. Migração em 9 waves; estado em `40_roadmap/delivery-tracker.yml` (epic correspondente) e spec `35_specs/_shared/2026-04-24-knowledge-reorg-company-os-separation.md`.

**Referências às localizações `30_adr/_shared/`, `40_roadmap/_shared/`, `20_architecture/_shared/` já refletem o estado alvo**; conteúdo migra para lá ao longo das waves. Durante a transição, alguns arquivos ainda estão flat — usar `find` ou `git grep` para localização atual.
```

Escrever com:

```bash
# (o conteúdo acima vai no README.md do bevox-knowledge via ferramenta de edição de arquivos)
```

- [ ] **Step 3: Verificar**

```bash
wc -l ~/bevox-knowledge/README.md
head -10 ~/bevox-knowledge/README.md
```

Expected: ~60-70 linhas; começa com "# Bevox Knowledge — Fonte Única de Verdade".

- [ ] **Step 4: Commit**

```bash
cd ~/bevox-knowledge
git add README.md
git commit -m "$(cat <<'EOF'
docs(readme): alinha com ADR-010 (separação uniforme por projeto)

README passa a documentar a convenção canônica de 8 subpastas por
folder + exceções (99_templates, _retired) + regras de ouro.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Expected: commit "docs(readme): alinha com ADR-010..." no topo.

---

## Task 5: Atualizar READMEs de `30_adr/` e `40_roadmap/`

**Files:**
- Modify: `~/bevox-knowledge/30_adr/README.md`
- Modify: `~/bevox-knowledge/40_roadmap/README.md`

- [ ] **Step 1: Ler estado atual dos dois READMEs**

```bash
echo "=== 30_adr/README.md ==="
cat ~/bevox-knowledge/30_adr/README.md
echo ""
echo "=== 40_roadmap/README.md ==="
cat ~/bevox-knowledge/40_roadmap/README.md
```

- [ ] **Step 2: Atualizar `30_adr/README.md`**

Conteúdo alvo (substituir inteiro):

```markdown
# Architecture Decision Records

ADRs canônicos do Bevox. Estrutura conforme **ADR-010** — subpastas por projeto + `_shared/` para decisões transversais.

## Convenção

- `_shared/` — ADRs cross-project (boundary, topology, naming, SoT, permissions, data, reorg)
- `bevox-backend/`, `bevox-console/`, `bevox-harness/`, `bevox-mobile/`, `bevox-web/` — ADRs específicos de cada módulo do produto Bevox
- `openclaw/` — ADRs específicos do runtime OpenClaw
- `company-os/` — ADRs de capabilities Company OS não-OpenClaw (Mission Control, Vox, etc.)

## Filename

`ADR-NNN-<slug>.md` — numeração global sequencial (não resetar por subpasta).

## Localização atual

| ADR | Destino |
|---|---|
| 001–007, 010 | `_shared/` (governança transversal) |
| 008 (bevox-backend module) | `bevox-backend/` (após wave-4) |
| 009 (clarification loop) | `company-os/` (após wave-4) |

Durante transição (waves 1-4), alguns ADRs ainda residem na raiz flat. Ver spec `35_specs/_shared/2026-04-24-knowledge-reorg-company-os-separation.md` para estado por wave.
```

- [ ] **Step 3: Atualizar `40_roadmap/README.md`**

Conteúdo alvo:

```markdown
# Roadmap

Roadmaps e tracker de execução. Estrutura conforme **ADR-010**.

## Convenção

- `_shared/` — artefatos cross-project (tracker de delivery, narrativas transversais)
- `bevox-backend/`, `bevox-console/`, `bevox-harness/`, `bevox-mobile/`, `bevox-web/` — roadmaps por módulo do produto
- `openclaw/` — roadmap do runtime OpenClaw
- `company-os/` — roadmap do Company OS (Mission Control, Vox, Knowledge-Sync, etc.)

## Artefatos canônicos

| Artefato | Destino (após wave-2) |
|---|---|
| `delivery-tracker.yml` | `_shared/` — tracker agregado cross-project |
| `2026-04-09-openclaw-company-os-roadmap.md` | `company-os/` — narrativa estratégica do Company OS |

Durante transição (pré-wave-2), `delivery-tracker.yml` e a narrativa ainda estão na raiz deste folder.

## Status convention do tracker

- `delivered` — entregue e mergeado em `main`
- `in_progress` — trabalho ativo
- `not_started` — aceito mas não iniciado
- `parked` — intencionalmente pausado (ver tag `parked-reason`)
- `blocked` — bloqueado por dependência externa
- `partial` — parcialmente entregue
```

- [ ] **Step 4: Verificar**

```bash
head -5 ~/bevox-knowledge/30_adr/README.md
head -5 ~/bevox-knowledge/40_roadmap/README.md
```

Expected: ambos começam com título + referência a "ADR-010".

- [ ] **Step 5: Commit**

```bash
cd ~/bevox-knowledge
git add 30_adr/README.md 40_roadmap/README.md
git commit -m "$(cat <<'EOF'
docs(readme): atualiza 30_adr/ e 40_roadmap/ para convenção ADR-010

Ambos documentam as 8 subpastas (_shared + 7 projetos) + onde cada
artefato residirá após as waves correspondentes.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Mover spec 2026-04-19 para `_retired/`

**Files:**
- Move: `~/bevox-knowledge/35_specs/2026-04-19-company-os-bevox-knowledge-domain-separation.md` → `~/bevox-knowledge/_retired/2026-04-19-company-os-bevox-knowledge-domain-separation.md`

- [ ] **Step 1: Verificar que `_retired/` existe**

```bash
ls -d ~/bevox-knowledge/_retired/ 2>&1
```

Expected: `~/bevox-knowledge/_retired/` (já existe; é exceção flat).

- [ ] **Step 2: `git mv`**

```bash
cd ~/bevox-knowledge
git mv 35_specs/2026-04-19-company-os-bevox-knowledge-domain-separation.md _retired/
```

Expected: sem output.

- [ ] **Step 3: Verificar**

```bash
ls ~/bevox-knowledge/_retired/ | grep 2026-04-19
ls ~/bevox-knowledge/35_specs/ | grep -c 2026-04-19
```

Expected: arquivo aparece em `_retired/`; count em `35_specs/` retorna `0`.

- [ ] **Step 4: Commit**

```bash
cd ~/bevox-knowledge
git commit -m "$(cat <<'EOF'
retire(spec): 2026-04-19 domain-separation → _retired/

Supersedida por ADR-010 + spec 2026-04-24-knowledge-reorg-company-os-separation.
Preservada em _retired/ para referência histórica.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Mover spec 2026-04-24 para `35_specs/_shared/`

**Files:**
- Move: `~/bevox-knowledge/35_specs/2026-04-24-knowledge-reorg-company-os-separation.md` → `~/bevox-knowledge/35_specs/_shared/2026-04-24-knowledge-reorg-company-os-separation.md`

- [ ] **Step 1: Remover `.gitkeep` se houver em `35_specs/_shared/`**

```bash
cd ~/bevox-knowledge
rm -f 35_specs/_shared/.gitkeep
```

Expected: sem output.

- [ ] **Step 2: `git mv`**

```bash
cd ~/bevox-knowledge
git mv 35_specs/2026-04-24-knowledge-reorg-company-os-separation.md 35_specs/_shared/
```

Expected: sem output.

- [ ] **Step 3: Verificar**

```bash
ls ~/bevox-knowledge/35_specs/_shared/
ls ~/bevox-knowledge/35_specs/ | grep -c 2026-04-24
```

Expected: em `_shared/` aparece `2026-04-24-knowledge-reorg-company-os-separation.md` (sem mais `.gitkeep`); count na raiz de `35_specs/` retorna `0`.

- [ ] **Step 4: Commit**

```bash
cd ~/bevox-knowledge
git add 35_specs/_shared/
git commit -m "$(cat <<'EOF'
chore(spec): move 2026-04-24-knowledge-reorg para 35_specs/_shared/

Canonicaliza localização da spec conforme ADR-010 (wave-0 entrega
final da spec já no layout alvo).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Reescrever `openclaw/CLAUDE.md` §§3, 3.1, 6.1

**Files:**
- Modify: `~/.openclaw/CLAUDE.md` — seções 3, 3.1 e 6.1

Branch de trabalho no openclaw: `draft/knowledge-reorg-wave-0`.

- [ ] **Step 1: Criar branch de trabalho em `.openclaw/`**

```bash
cd ~/.openclaw
git checkout -b draft/knowledge-reorg-wave-0
git branch --show-current
```

Expected: `draft/knowledge-reorg-wave-0`.

- [ ] **Step 2: Ler estado atual das seções**

```bash
sed -n '60,80p' ~/.openclaw/CLAUDE.md  # §3
sed -n '355,375p' ~/.openclaw/CLAUDE.md # §3.1
sed -n '395,425p' ~/.openclaw/CLAUDE.md # §6.1
```

Linhas aproximadas; confirmar com `grep -n '^## 3' CLAUDE.md` e `grep -n '^## 3.1\|^## 6.1' CLAUDE.md` antes da edição.

- [ ] **Step 3: Reescrever §3 (Fonte única de verdade)**

Substituir o bloco entre `## 3. Fonte única de verdade` e `## 3.1 Hierarquia canônica...` por:

```markdown
## 3. Fonte única de verdade

A fonte única de verdade é:

- **Repo:** `bevox-knowledge`
- **Clone local canônico:** `~/bevox-knowledge/`

### O que mora lá

- ADRs (em `30_adr/<projeto>/` — vide §3.1)
- PRDs (em `10_prd/<projeto>/`)
- roadmaps (em `40_roadmap/<projeto>/`)
- specs (em `35_specs/<projeto>/`)
- system-map (em `20_architecture/<projeto>/`)
- docs operacionais
- módulos
- políticas

### O que não é fonte de verdade

- conversa solta
- memória efêmera
- arquivos temporários do workspace
- suposição do agente
- estado transitório do OpenClaw

### Regra de ouro

Se algo precisa sobreviver múltiplas sessões e orientar decisões futuras, deve viver no `bevox-knowledge`.
```

- [ ] **Step 4: Reescrever §3.1 (Hierarquia canônica)**

Substituir a subseção `## 3.1 Hierarquia canônica dentro do bevox-knowledge` por:

```markdown
## 3.1 Hierarquia canônica dentro do bevox-knowledge

Conforme **ADR-010** (`30_adr/_shared/ADR-010-knowledge-project-separation.md`), todo folder canônico do `bevox-knowledge` é subdividido em **8 subpastas fixas**:

- `_shared/` — governança e infra transversal (ADRs de boundary, security-posture, delivery-tracker.yml)
- `bevox-backend/`, `bevox-console/`, `bevox-harness/`, `bevox-mobile/`, `bevox-web/` — os 5 módulos do produto Bevox
- `openclaw/` — runtime Company OS (agentes, skills, delivery, kanban-tasks, gateway, finance, health, hardening)
- `company-os/` — capabilities Company OS não-OpenClaw (Mission Control, Vox, Knowledge-Sync, Agent Registry, Approval Center)

### Folders canônicos

- `00_inbox/<projeto>/` — captura
- `10_prd/<projeto>/` — PRDs
- `20_architecture/<projeto>/` — arquitetura e docs técnicos
- `30_adr/<projeto>/` — ADRs
- `35_specs/<projeto>/` — specs de implementação por epic/wave
- `40_roadmap/<projeto>/` — roadmaps e tracker
- `50_releases/<projeto>/` — release notes
- `60_customer-feedback/<projeto>/` — feedback
- `70_metrics/<projeto>/` — métricas

### Exceções (permanecem flat)

- `99_templates/` — templates por tipo de artefato
- `_retired/` — histórico; documentos retirados

### Artefatos canônicos transversais

- `30_adr/_shared/` — ADRs globais (001-007, 010)
- `40_roadmap/_shared/delivery-tracker.yml` — tracker cross-project (a partir da wave-2)
- `20_architecture/_shared/` — security-posture, hardening-registry, health-registry, agents/registry.yml, content-backlog.yml (a partir da wave-3)

### Regra de desempate `openclaw/` vs `company-os/`

Se o artefato descreve comportamento executado **dentro** de `~/.openclaw/` → `openclaw/`.
Se descreve capability Company OS observável por fora (dashboard, política, spine) → `company-os/`.

Se houver conflito entre roadmap narrativo e delivery-tracker/specs, verifique a spec mais recente primeiro. Nunca recomende reimplementar uma capability sem checar os dois.

### Estado da reorg

A reorg para esta convenção está em andamento (ADR-010 aceita em 2026-04-24). Durante a transição (waves 1-7), alguns artefatos ainda residem flat na raiz dos folders. Usar `find` ou `git grep` para localização atual; ver spec `35_specs/_shared/2026-04-24-knowledge-reorg-company-os-separation.md` para o estado por wave.
```

- [ ] **Step 5: Reescrever §6.1 (Mandatory existing coverage preflight)**

Substituir a subseção `## 6.1 Mandatory existing coverage preflight` por:

```markdown
## 6.1 Mandatory existing coverage preflight

Antes de recomendar uma nova wave, spec, página, rota ou módulo, você deve provar que a capability não está já materialmente coberta.

Checklist mínimo (paths refletem convenção ADR-010; durante a transição, também checar raiz flat):

1. Checar o epic no roadmap narrativo (`40_roadmap/company-os/2026-04-09-openclaw-company-os-roadmap.md` após wave-2; raiz antes).
2. Checar `40_roadmap/_shared/delivery-tracker.yml` após wave-2; `40_roadmap/delivery-tracker.yml` antes.
3. Checar specs relevantes em `35_specs/<projeto>/` (após wave-1) ou na raiz flat (antes).
4. Checar surfaces existentes no repo alvo (API, page, tab, CLI, módulo host-local).
5. Se tocar `~/.openclaw/`, confirmar se aquilo é source canônico (agora versionado em `bernardTavares/openclaw`) ou runtime instalado de outro repo (ex: `knowledge-sync/` e `extensions/` são deploy de `~/code/knowledge-sync/`).

Se cobertura material já existir:
- não proponha nova wave
- proponha hygiene documental / tracker sync / refinement mínimo

Use explicitamente uma destas classificações no raciocínio:
- `delivered`
- `materialmente coberto, mas tracker/roadmap stale`
- `não implementado`
```

- [ ] **Step 6: Verificar edição**

```bash
grep -n '^## 3\|^## 3.1\|^## 6.1' ~/.openclaw/CLAUDE.md
wc -l ~/.openclaw/CLAUDE.md
```

Expected: 3 headers encontrados; arquivo com ~350-400 linhas.

- [ ] **Step 7: Commit**

```bash
cd ~/.openclaw
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
docs(claude.md): atualiza §§3, 3.1, 6.1 para ADR-010

§3 (Fonte única de verdade): reflete paths com <projeto>/ subfolder.
§3.1 (Hierarquia canônica): materializa as 8 subpastas + exceções
  + regra de desempate openclaw/ vs company-os/ + nota de transição.
§6.1 (Preflight): checklist ciente de transição (raiz flat ainda
  é válido pré-wave-correspondente).

Referencia ADR-010 em bevox-knowledge/30_adr/_shared/.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Atualizar `workspace-shared/memory/reference_bevox_knowledge.md`

**Files:**
- Modify: `~/.openclaw/workspace-shared/memory/reference_bevox_knowledge.md`

Nota: se a pasta `workspace-shared/` estiver no `.gitignore` do openclaw (via pattern `workspace-*/`), este arquivo não vai pro commit. Ajustar em caso positivo.

- [ ] **Step 1: Verificar se o path está sendo trackeado**

```bash
cd ~/.openclaw
git check-ignore -v workspace-shared/memory/reference_bevox_knowledge.md 2>&1
```

Expected (se ignorado): algo como `.gitignore:N:workspace-*/ workspace-shared/memory/reference_bevox_knowledge.md`.
Expected (se tracked): comando sai sem output.

- [ ] **Step 2a: Se ignorado — adicionar exceção no `.gitignore`**

```bash
cd ~/.openclaw
# adicionar linha no final do .gitignore
printf '\n# exceção: memory compartilhado É source (não runtime)\n!workspace-shared/\n' >> .gitignore
git check-ignore -v workspace-shared/memory/reference_bevox_knowledge.md
```

Expected: sem output (não mais ignorado).

- [ ] **Step 2b: Se já tracked — pular passo 2a**

- [ ] **Step 3: Reescrever o arquivo**

Conteúdo alvo (`~/.openclaw/workspace-shared/memory/reference_bevox_knowledge.md`):

```markdown
# Reference — bevox-knowledge

## Clone local

`~/bevox-knowledge/`

## Remote

`bernardTavares/bevox-knowledge` (private)

## Estrutura canônica (ADR-010)

Todo folder canônico tem 8 subpastas:
`_shared/`, `bevox-backend/`, `bevox-console/`, `bevox-harness/`, `bevox-mobile/`, `bevox-web/`, `openclaw/`, `company-os/`

Folders canônicos: `00_inbox/`, `10_prd/`, `20_architecture/`, `30_adr/`, `35_specs/`, `40_roadmap/`, `50_releases/`, `60_customer-feedback/`, `70_metrics/`.

Exceções flat: `99_templates/`, `_retired/`.

## Artefatos transversais (_shared/)

- `30_adr/_shared/` — ADRs 001-007, 010
- `40_roadmap/_shared/delivery-tracker.yml` — após wave-2
- `20_architecture/_shared/` — security-posture, hardening-registry, health-registry, agents/registry.yml, content-backlog.yml — após wave-3

## Durante transição

Waves 1-7 ainda em execução (ver `35_specs/_shared/2026-04-24-knowledge-reorg-company-os-separation.md`). Durante esse período, alguns artefatos residem na raiz flat dos folders. `find` ou `git grep` para localização atual.

## Regra de desempate

- `openclaw/` — comportamento executado dentro de `~/.openclaw/`
- `company-os/` — capabilities Company OS observáveis por fora (Mission Control, Vox, Knowledge-Sync, Agent Registry, Approval Center)

## Rollback catastrófico

Tag `pre-knowledge-reorg` em `bernardTavares/bevox-knowledge`, `bernardTavares/knowledge-sync`, `bernardTavares/openclaw`, `bernardTavares/mission-control`. `git reset --hard pre-knowledge-reorg` nos 4 repos reverte.
```

- [ ] **Step 4: Verificar**

```bash
head -10 ~/.openclaw/workspace-shared/memory/reference_bevox_knowledge.md
```

Expected: começa com "# Reference — bevox-knowledge".

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw
git add workspace-shared/memory/reference_bevox_knowledge.md .gitignore
git commit -m "$(cat <<'EOF'
docs(memory): atualiza reference_bevox_knowledge para ADR-010

Reflete convenção canônica das 8 subpastas + paths alvo de artefatos
transversais em _shared/ + regra de desempate openclaw vs company-os
+ rollback catastrófico via tag pre-knowledge-reorg nos 4 repos.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Smoke test de wave-0

**Files:** nenhum — só verificação.

- [ ] **Step 1: Estrutura do bevox-knowledge correta**

```bash
cd ~/bevox-knowledge
echo "=== folders × subpastas (esperado: 8 em cada) ==="
for f in 00_inbox 10_prd 20_architecture 30_adr 35_specs 40_roadmap 50_releases 60_customer-feedback 70_metrics; do
  count=$(ls -d "$f"/*/ 2>/dev/null | wc -l)
  echo "$f: $count subpastas"
done
```

Expected: cada folder mostra `8 subpastas`.

- [ ] **Step 2: ADR-010 existe e está commitada**

```bash
cd ~/bevox-knowledge
git log --oneline --all | grep -c "ADR-010"
ls 30_adr/_shared/ADR-010-knowledge-project-separation.md
```

Expected: `git log` com >=1 match; `ls` retorna o arquivo.

- [ ] **Step 3: Specs nos destinos corretos**

```bash
cd ~/bevox-knowledge
ls _retired/2026-04-19-company-os-bevox-knowledge-domain-separation.md
ls 35_specs/_shared/2026-04-24-knowledge-reorg-company-os-separation.md
ls 35_specs/2026-04-19-company-os-bevox-knowledge-domain-separation.md 2>&1
ls 35_specs/2026-04-24-knowledge-reorg-company-os-separation.md 2>&1
```

Expected: primeiros 2 `ls` retornam o arquivo; últimos 2 retornam "No such file".

- [ ] **Step 4: Tags em 4 repos**

```bash
for d in ~/bevox-knowledge ~/code/knowledge-sync ~/.openclaw ~/code/mission-control; do
  echo "=== $d ==="
  git -C "$d" tag -l pre-knowledge-reorg
done
```

Expected: 4 × `pre-knowledge-reorg`.

- [ ] **Step 5: Consumidores ainda funcionam (nenhum conteúdo canônico moveu)**

```bash
# mission-control resolve tracker?
curl -fsS http://localhost:3000/api/delivery/tracker 2>&1 | head -c 200 || echo "(mission-control não está rodando — tudo bem, check manual)"

# knowledge-sync status funciona?
cd ~/bevox-knowledge && bash ~/code/knowledge-sync/skill/scripts/status.sh 2>&1 | head -5
```

Expected: tracker retorna JSON válido (ou mensagem de serviço não rodando, ok). Status sai sem erro de parsing.

Nota: conteúdo canônico (`delivery-tracker.yml`, `registry.yml`, todos os specs) ainda está em layout flat nesta wave — consumidores não precisam ter mudado ainda.

- [ ] **Step 6: Commit (N/A — só verificação)**

---

## Task 11: Atualizar memória de projeto (wave-0 done)

**Files:**
- Modify: `~/.claude/projects/-home-you--openclaw/memory/project_knowledge_reorg.md`

- [ ] **Step 1: Substituir linha de status da wave-0**

Edit em `project_knowledge_reorg.md`: trocar

```
- ⏭️ **Wave-0** — próxima. ADR-010 + ...
```

por

```
- ✅ **Wave-0** (AAAA-MM-DD) — ADR-010 aceita, 71 .gitkeep criados, spec 2026-04-19 em _retired/, spec 2026-04-24 em 35_specs/_shared/, tags pre-knowledge-reorg nos 4 repos, openclaw/CLAUDE.md §§3, 3.1, 6.1 atualizados. Branch draft/knowledge-reorg-wave-0 em bevox-knowledge (pendente merge canônico) e em .openclaw.
```

E atualizar a linha de próximo passo:
```
- ⏭️ **Wave-1** — próxima: 35_specs/ classificação + git mv + consumidores.
```

Substituir `AAAA-MM-DD` pela data real de execução.

- [ ] **Step 2: Verificar MEMORY.md index**

Se necessário, ajustar descrição one-liner em `MEMORY.md` para refletir "wave-0 done".

- [ ] **Step 3: Não commitar (memory é fora de git)**

Memória fica em `~/.claude/projects/-home-you--openclaw/memory/` — não é git-tracked. Apenas salvar.

---

## Post-wave: approval canônico

Wave-0 fica em branches `draft/knowledge-reorg-wave-0` nos 2 repos afetados (`bevox-knowledge` e `.openclaw`). Para **aprovar canonicamente** (merge em `main`):

1. Bernard revisa o branch.
2. Bernard decide merge para main (por CLAUDE.md §8, commit/push canônico é sensível — requer aprovação explícita).
3. Push opcional do draft antes de merge (para PR de review no GitHub).

Rollback em caso de arrependimento: `git reset --hard pre-knowledge-reorg` nos repos afetados.

---

## Self-Review

**Spec coverage check:**
- ✅ ADR-010 criada (Task 2) — spec §2, §3
- ✅ 72 subpastas vazias (Task 3) — spec §4 wave-0 item 2
- ✅ README principal atualizado (Task 4) — spec §4 wave-0 item 3
- ✅ READMEs de 30_adr/ e 40_roadmap/ (Task 5) — spec §4 wave-0 item 4
- ✅ Tags pre-knowledge-reorg em 4 repos (Task 1) — spec §4 wave-0 item 5
- ✅ openclaw/CLAUDE.md §§3, 3.1, 6.1 (Task 8) — spec §4 wave-0 item 6
- ✅ reference_bevox_knowledge.md (Task 9) — spec §4 wave-0 item 7
- ✅ Spec 2026-04-19 → _retired/ (Task 6) — spec §4 wave-0 implícito + §7 risco 7
- ✅ Spec 2026-04-24 → 35_specs/_shared/ (Task 7) — spec §4.4 design decision A
- ✅ Smoke-test wave-0 (Task 10) — spec §4 wave-0 smoke

**Placeholder check:** nenhum "TBD/TODO/later"; todos os conteúdos de markdown, comandos e edits têm texto literal. Única exceção: Task 11 usa "AAAA-MM-DD" como placeholder para data real (explicitamente instruído a substituir).

**Consistency check:** ADR-010, spec de 2026-04-24, READMEs, CLAUDE.md e reference_bevox_knowledge citam os mesmos paths canônicos (`_shared/`, `openclaw/`, `company-os/` + 5 módulos) e as mesmas exceções (`99_templates/`, `_retired/`). Regra de desempate openclaw/company-os idêntica em todos.

---

## Execution Handoff

Plan completo e salvo em `~/.openclaw/docs/superpowers/plans/2026-04-24-knowledge-reorg-wave-0.md`. Duas opções de execução:

1. **Subagent-Driven (recomendada)** — dispatch subagent fresh por task, revisão entre tasks, iteração rápida.
2. **Inline Execution** — executar tasks nesta sessão com executing-plans, batch execution com checkpoints.

Qual abordagem?
