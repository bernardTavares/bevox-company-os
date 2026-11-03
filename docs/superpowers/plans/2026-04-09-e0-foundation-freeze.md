# E0 - Foundation Freeze Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar o repositorio `bevox-knowledge` no GitHub privado, scaffolding completo da estrutura E0 (9 pastas top-level + agents/), 6 ADRs redigidas, system-map, registry, decision-log, template MADR e migracao do spec atual.

**Architecture:** Documentation/scaffolding task. Toda a "logica" sao arquivos markdown criados em uma estrutura de pastas. O conteudo das ADRs ja esta redigido na spec - este plano apenas instrui o agente executor a transcrever as secoes corretas para os arquivos finais. Workflow git: clone -> scaffold -> commit -> push -> tag.

**Tech Stack:** Git, GitHub CLI (`gh`), bash, markdown.

**Spec source of truth:** `~/.openclaw/docs/superpowers/specs/2026-04-09-foundation-freeze-design.md`

**Repo path local:** `~/bevox-knowledge/`
**Repo path remote:** `github.com/${BEVOX_GITHUB_ORG}/bevox-knowledge` (privado)

> **Variavel `BEVOX_GITHUB_ORG`:** Bernard precisa decidir se usa conta pessoal ou cria uma org Bevox antes da Task 1. Esse valor sera usado em todos os comandos `gh` subsequentes. O agente executor deve perguntar a Bernard qual valor usar antes de iniciar a Task 1, ou ler de um env var `BEVOX_GITHUB_ORG`.

---

## Task 0: Pre-requisitos manuais (Bernard, BLOQUEANTE)

**Files:** Nenhum (acoes manuais do humano)

Esta task **bloqueia tudo o resto** ate ser concluida. O agente executor NAO deve prosseguir para a Task 1 ate Bernard confirmar todos os itens abaixo.

- [ ] **Step 1: Bernard decide entre conta pessoal ou org Bevox**

Bernard precisa decidir:
- Opcao A: Usar conta GitHub pessoal (rapido, mas migra depois)
- Opcao B: Criar org `bevox` ou similar agora (mais limpo)

Anotar a escolha em `BEVOX_GITHUB_ORG` (env var ou nota mental).

- [ ] **Step 2: Bernard cria conta/org se necessario**

Se Opcao B: ir em https://github.com/organizations/new e criar a org. Plano gratuito serve.

- [ ] **Step 3: Bernard executa `gh auth login`**

```bash
gh auth login
```

Seguir o fluxo:
- GitHub.com
- HTTPS
- Authenticate via web browser
- Aceitar o token

- [ ] **Step 4: Verificar autenticacao**

```bash
gh auth status
```

Expected output (deve mostrar "Logged in to github.com as <username>"):
```
github.com
  ✓ Logged in to github.com as <username>
  ✓ Git operations for github.com configured to use https protocol.
  ✓ Token: gho_************************************
```

- [ ] **Step 5: Verificar permissao para criar repo privado**

```bash
gh repo list --limit 1
```

Se nao retornar erro, ok. Se for usar org, testar:
```bash
gh repo list ${BEVOX_GITHUB_ORG} --limit 1
```

- [ ] **Step 6: Comunicar ao agente executor**

Bernard avisa o agente executor:
- "BEVOX_GITHUB_ORG=<valor>" (substituir pelo valor real)
- Pode prosseguir para Task 1

---

## Task 1: Criar repo no GitHub e clone local

**Files:**
- Create: `~/bevox-knowledge/` (clone local)
- Remote: `github.com/${BEVOX_GITHUB_ORG}/bevox-knowledge` (privado)

- [ ] **Step 1: Confirmar valor de BEVOX_GITHUB_ORG**

```bash
echo "BEVOX_GITHUB_ORG=${BEVOX_GITHUB_ORG}"
```

Se vazio, parar e perguntar a Bernard.

- [ ] **Step 2: Verificar que `~/bevox-knowledge/` nao existe**

```bash
ls ~/bevox-knowledge 2>/dev/null && echo "EXISTS" || echo "OK_NOT_EXISTS"
```

Expected: `OK_NOT_EXISTS`

Se existir, parar e perguntar a Bernard como proceder.

- [ ] **Step 3: Criar repo privado no GitHub**

```bash
gh repo create ${BEVOX_GITHUB_ORG}/bevox-knowledge \
  --private \
  --description "Fonte unica de verdade da Bevox: PRDs, ADRs, roadmaps, arquitetura e decisoes." \
  --clone=false
```

Expected output:
```
✓ Created repository <ORG>/bevox-knowledge on GitHub
```

- [ ] **Step 4: Clonar para `~/bevox-knowledge/`**

```bash
cd ~
gh repo clone ${BEVOX_GITHUB_ORG}/bevox-knowledge
```

Expected output:
```
Cloning into 'bevox-knowledge'...
warning: You appear to have cloned an empty repository.
```

- [ ] **Step 5: Verificar clone**

```bash
cd ~/bevox-knowledge && git status
```

Expected output:
```
On branch main
No commits yet
nothing to commit (create/copy files and use "git add" to track)
```

Nota: pode aparecer `master` em vez de `main` dependendo do git config global. Se for `master`, renomear:
```bash
cd ~/bevox-knowledge && git branch -m master main
```

---

## Task 2: Estrutura de pastas top-level

**Files:**
- Create: `~/bevox-knowledge/00_inbox/`
- Create: `~/bevox-knowledge/10_prd/`
- Create: `~/bevox-knowledge/20_architecture/`
- Create: `~/bevox-knowledge/30_adr/`
- Create: `~/bevox-knowledge/35_specs/`
- Create: `~/bevox-knowledge/40_roadmap/`
- Create: `~/bevox-knowledge/50_releases/`
- Create: `~/bevox-knowledge/60_customer-feedback/`
- Create: `~/bevox-knowledge/70_metrics/`

- [ ] **Step 1: Criar todas as 9 pastas top-level**

```bash
cd ~/bevox-knowledge
mkdir -p 00_inbox 10_prd 20_architecture 30_adr 35_specs 40_roadmap 50_releases 60_customer-feedback 70_metrics
```

- [ ] **Step 2: Verificar criacao**

```bash
ls -la ~/bevox-knowledge
```

Expected: 9 diretorios listados (alem de `.git/`).

---

## Task 3: Subpasta de agents

**Files:**
- Create: `~/bevox-knowledge/20_architecture/agents/`
- Create: `~/bevox-knowledge/20_architecture/agents/_retired/`

- [ ] **Step 1: Criar subpastas de agents**

```bash
cd ~/bevox-knowledge
mkdir -p 20_architecture/agents/_retired
```

- [ ] **Step 2: Verificar**

```bash
find ~/bevox-knowledge/20_architecture -type d
```

Expected:
```
~/bevox-knowledge/20_architecture
~/bevox-knowledge/20_architecture/agents
~/bevox-knowledge/20_architecture/agents/_retired
```

---

## Task 4: README raiz, .gitignore e decision-log

**Files:**
- Create: `~/bevox-knowledge/README.md`
- Create: `~/bevox-knowledge/.gitignore`
- Create: `~/bevox-knowledge/decision-log.md`

- [ ] **Step 1: Criar `.gitignore`**

```bash
cat > ~/bevox-knowledge/.gitignore <<'EOF'
# OS
.DS_Store
Thumbs.db

# Editor
*.swp
*.swo
*~
.idea/
.vscode/

# Obsidian (mantem so as configs versionadas se precisar)
.obsidian/workspace.json
.obsidian/workspace-mobile.json
.obsidian/cache
.obsidian/plugins/*/data.json

# Trash
.trash/
EOF
```

- [ ] **Step 2: Criar `README.md` raiz**

Conteudo extraido da spec, secao 2.3 (`### 2.3 Arquivo README.md raiz`). Transcrever literalmente o bloco markdown que comeca com `# bevox-knowledge` e termina antes da secao 2.4.

```bash
cat > ~/bevox-knowledge/README.md <<'EOF'
# bevox-knowledge

Fonte unica de verdade da Bevox: produto, arquitetura, decisoes, roadmap, releases, feedback e metricas.

## Estrutura

| Pasta | Conteudo |
|---|---|
| `00_inbox/` | Capturas rapidas a serem organizadas |
| `10_prd/` | PRDs (Product Requirements Documents) |
| `20_architecture/` | Arquitetura tecnica e operacional, system-map, agents |
| `30_adr/` | Architecture Decision Records (decisoes formais) |
| `35_specs/` | Specs de implementacao (designs detalhados) |
| `40_roadmap/` | Roadmaps estrategicos e tecnicos |
| `50_releases/` | Notas de release e changelog |
| `60_customer-feedback/` | Feedback de clientes e pesquisas |
| `70_metrics/` | Metricas de produto e operacao |

## Convencoes

- **Idioma:** Portugues brasileiro
- **Formato:** Markdown puro (sem extensoes proprietarias)
- **Nomenclatura:** Veja `30_adr/ADR-004-naming-canonical.md`
- **Decisoes:** Sempre como ADR formal em `30_adr/`. Notas soltas nao contam.
- **Editor:** Qualquer um (VSCode, Obsidian, Vim) - markdown puro
- **Sync:** Manual via git push/pull. Automacao vira no E1.

## Quem le isso

- **Bernard** (humano)
- **Vox** (agente principal do OpenClaw, le via filesystem do clone local)
- **Claude Code** (assistente de coding, le quando esta fazendo trabalho relacionado)
- **Futuros agentes especializados** (Product, Delivery, etc.)

## Quem escreve isso

- **Bernard** sempre
- **Vox** quando autorizado, com revisao humana antes de commit
- **Claude Code** quando solicitado explicitamente, com revisao humana

## Regra de ouro

Se nao esta neste repo, nao e fonte de verdade. Documentacao em outros lugares (Notion, Google Docs, mensagens no Telegram) e rascunho ou comunicacao - nao decisao.
EOF
```

- [ ] **Step 3: Criar `decision-log.md`**

Conteudo extraido da spec, secao 10 (`## 10. decision-log.md`). Transcrever o bloco markdown.

```bash
cat > ~/bevox-knowledge/decision-log.md <<'EOF'
# Decision Log

> Indice cronologico de todas as ADRs da Bevox.
> Cada entrada linka para a ADR completa em `30_adr/`.

## 2026-04

| # | Titulo | Status | Tags | Data |
|---|---|---|---|---|
| ADR-001 | Company OS Boundary | proposta | boundary, scope, foundation | 2026-04-09 |
| ADR-002 | System Topology | proposta | topology, modules, foundation | 2026-04-09 |
| ADR-003 | Agent Governance | proposta | agents, governance, leveling | 2026-04-09 |
| ADR-004 | Naming Canonical | proposta | naming, conventions, foundation | 2026-04-09 |
| ADR-005 | Knowledge Source of Truth & Context Sync | proposta | knowledge, source-of-truth, sync | 2026-04-09 |
| ADR-006 | Autonomy, Permissions & Approval Policy | proposta | autonomy, permissions, approvals, security | 2026-04-09 |

## Status

- **proposta:** redigida, aguardando revisao do decisor
- **aceita:** revisada e aceita; e a politica oficial
- **descartada:** revisada e rejeitada; nao tem efeito
- **substituida-por-ADR-XXX:** foi substituida por outra ADR mais recente

## Como adicionar nova ADR

1. Copiar `30_adr/_template.md` para `30_adr/ADR-XXX-titulo.md`
2. Preencher contexto, opcoes, recomendacao
3. Status inicial: `proposta`
4. Adicionar linha nesta tabela
5. Commit em branch `adr/XXX-titulo`
6. PR para revisao
7. Apos aprovacao, status muda para `aceita` e merge
EOF
```

- [ ] **Step 4: Verificar arquivos criados**

```bash
ls ~/bevox-knowledge/{README.md,.gitignore,decision-log.md}
```

Expected: 3 arquivos listados.

---

## Task 5: README.md em cada pasta top-level

**Files:**
- Create: `~/bevox-knowledge/00_inbox/README.md`
- Create: `~/bevox-knowledge/10_prd/README.md`
- Create: `~/bevox-knowledge/20_architecture/README.md`
- Create: `~/bevox-knowledge/30_adr/README.md`
- Create: `~/bevox-knowledge/35_specs/README.md`
- Create: `~/bevox-knowledge/40_roadmap/README.md`
- Create: `~/bevox-knowledge/50_releases/README.md`
- Create: `~/bevox-knowledge/60_customer-feedback/README.md`
- Create: `~/bevox-knowledge/70_metrics/README.md`

- [ ] **Step 1: Criar README do `00_inbox/`**

```bash
cat > ~/bevox-knowledge/00_inbox/README.md <<'EOF'
# 00_inbox

Capturas rapidas, ideias soltas, rascunhos, anotacoes que ainda nao foram organizadas em outra pasta.

## Convencao

- Nada aqui e considerado fonte de verdade
- Itens devem ser revisados regularmente e movidos para a pasta certa, ou descartados
- Sem ADRs aqui (ADRs vivem em `30_adr/`)
- Sem PRDs aqui (PRDs vivem em `10_prd/`)

## Quando usar

Use o `00_inbox/` quando:
- Voce tem uma ideia mas nao sabe ainda onde ela mora
- Esta capturando contexto rapido durante uma sessao
- Tem rascunho que ainda nao esta pronto para ser canonico
EOF
```

- [ ] **Step 2: Criar README do `10_prd/`**

```bash
cat > ~/bevox-knowledge/10_prd/README.md <<'EOF'
# 10_prd

Product Requirements Documents da Bevox.

## O que vai aqui

- PRDs do produto Bevox (web, mobile, console, harness)
- PRDs do Company OS (Mission Control, Approval Center, etc.)
- Especificacoes de features que ainda nao viraram specs tecnicas

## Convencao de nomenclatura

`YYYY-MM-DD-{escopo}-{topico}.md`

Exemplos:
- `2026-04-15-bevox-console-user-management.md`
- `2026-05-01-mission-control-dashboard-v1.md`

## Status

PRDs tem ciclo de vida proprio:
- `draft` - em rascunho
- `review` - em revisao
- `approved` - aprovado
- `implemented` - virou codigo
- `deprecated` - obsoleto
EOF
```

- [ ] **Step 3: Criar README do `20_architecture/`**

```bash
cat > ~/bevox-knowledge/20_architecture/README.md <<'EOF'
# 20_architecture

Documentos tecnicos e operacionais sobre a arquitetura da Bevox.

## O que vai aqui

- `system-map.md` - Mapa canonico dos modulos da Bevox
- `agents/` - Definicoes formais de agentes do Company OS
- Diagramas de arquitetura
- Documentacao de integracoes
- Specs de protocolos internos

## Relacao com outras pastas

- `30_adr/` registra **decisoes** arquiteturais
- `20_architecture/` documenta o **estado** arquitetural resultante

Quando uma ADR e aceita, a documentacao em `20_architecture/` precisa ser atualizada para refletir.
EOF
```

- [ ] **Step 4: Criar README do `30_adr/`**

```bash
cat > ~/bevox-knowledge/30_adr/README.md <<'EOF'
# 30_adr

Architecture Decision Records (ADRs) da Bevox.

## O que e uma ADR

Uma ADR e o registro formal de uma decisao arquitetural significativa. Captura:
- O contexto que tornou a decisao necessaria
- As opcoes consideradas
- A decisao tomada
- As consequencias

## Formato

Usamos MADR (Markdown Architecture Decision Records). Veja `_template.md`.

## Convencao de nomenclatura

`ADR-XXX-titulo-curto.md`

- `XXX` = numero sequencial com 3 digitos
- `titulo-curto` = kebab-case, 2-5 palavras

## Status possiveis

- `proposta` - redigida, aguardando revisao
- `aceita` - aprovada, e a politica oficial
- `descartada` - rejeitada, nao tem efeito
- `substituida-por-ADR-YYY` - foi substituida por outra ADR

## Indice

Veja `../decision-log.md` para a tabela completa de ADRs.

## Como criar uma nova ADR

1. Copiar `_template.md` para `ADR-XXX-titulo.md` (proximo numero disponivel)
2. Preencher contexto, opcoes consideradas, recomendacao
3. Status inicial: `proposta`
4. Adicionar linha em `../decision-log.md`
5. Commit em branch `adr/XXX-titulo`
6. PR para revisao
7. Apos aprovacao do owner, status muda para `aceita` e merge na main
EOF
```

- [ ] **Step 5: Criar README do `35_specs/`**

```bash
cat > ~/bevox-knowledge/35_specs/README.md <<'EOF'
# 35_specs

Specs de implementacao - designs detalhados que orientam a construcao de features e epicos.

## O que vai aqui

- Specs de epicos do roadmap (E0 a E12)
- Specs de features individuais
- Designs tecnicos detalhados
- Especificacoes de interfaces internas

## Convencao de nomenclatura

`YYYY-MM-DD-{epico-ou-topico}.md`

Exemplos:
- `2026-04-09-e0-foundation-freeze.md`
- `2026-05-01-e1-knowledge-spine.md`
- `2026-06-15-mission-control-dashboard.md`

## Relacao com outras pastas

- `40_roadmap/` define **o que** fazer e **quando**
- `30_adr/` define **decisoes** estruturais que orientam o como
- `35_specs/` define **como** implementar features especificas

Cada spec referencia o epico/feature do roadmap e as ADRs relevantes.

## Workflow

1. Roadmap identifica um epico
2. Brainstorming gera o design
3. Spec e escrito em `35_specs/`
4. Spec passa por revisao
5. Plano de implementacao e gerado a partir do spec
6. Implementacao executa o plano
EOF
```

- [ ] **Step 6: Criar README do `40_roadmap/`**

```bash
cat > ~/bevox-knowledge/40_roadmap/README.md <<'EOF'
# 40_roadmap

Roadmaps estrategicos e tecnicos da Bevox.

## O que vai aqui

- Roadmap mestre do Company OS
- Roadmaps de modulos especificos do produto (web, mobile, console, harness)
- Roadmaps estrategicos por trimestre/semestre
- OKRs e objetivos macro

## Convencao de nomenclatura

`YYYY-MM-DD-{escopo}-roadmap.md`

Exemplos:
- `2026-04-09-openclaw-company-os-roadmap.md`
- `2026-05-01-bevox-harness-roadmap.md`
- `2026-Q3-strategic-roadmap.md`

## Relacao com outras pastas

- Roadmap define **o que** + **quando**
- ADRs em `30_adr/` definem **decisoes** que orientam
- Specs em `35_specs/` definem **como** implementar
EOF
```

- [ ] **Step 7: Criar README do `50_releases/`**

```bash
cat > ~/bevox-knowledge/50_releases/README.md <<'EOF'
# 50_releases

Notas de release, changelogs e historico de versoes da Bevox.

## O que vai aqui

- Release notes de cada versao publicada
- Changelogs por modulo
- Migrations e breaking changes
- Hotfixes registrados

## Convencao de nomenclatura

`{modulo}-vX.Y.Z.md` ou `YYYY-MM-DD-{modulo}-release.md`

Exemplos:
- `bevox-web-v1.0.0.md`
- `2026-05-15-bevox-harness-release.md`

## Relacao com outras pastas

- Quando uma feature e released, mover/copiar resumo do PRD/spec aqui
- Tagear o repo de codigo com a versao correspondente
EOF
```

- [ ] **Step 8: Criar README do `60_customer-feedback/`**

```bash
cat > ~/bevox-knowledge/60_customer-feedback/README.md <<'EOF'
# 60_customer-feedback

Feedback de clientes, entrevistas, pesquisas e insights externos.

## O que vai aqui

- Notas de entrevistas com clientes (anonimizadas se necessario)
- Resultados de pesquisas
- Padroes de uso observados
- Reclamacoes e elogios estruturados
- Insights de discovery

## Convencao de nomenclatura

`YYYY-MM-DD-{tipo}-{topico}.md`

Exemplos:
- `2026-05-01-interview-client-onboarding.md`
- `2026-05-10-survey-mobile-vs-web.md`

## Privacidade

- Nao incluir dados pessoais identificaveis (PII) sem anonimizacao
- Nao incluir credenciais ou senhas mencionadas pelos clientes
- Em duvida, conferir com Bernard antes de commit
EOF
```

- [ ] **Step 9: Criar README do `70_metrics/`**

```bash
cat > ~/bevox-knowledge/70_metrics/README.md <<'EOF'
# 70_metrics

Metricas de produto, operacao e Company OS.

## O que vai aqui

- Definicao de metricas (o que medir e como)
- Snapshots periodicos de metricas
- Dashboards textuais de KPIs
- Analises de tendencias

## Convencao de nomenclatura

- Definicoes: `metric-{name}.md` (ex: `metric-dau.md`)
- Snapshots: `YYYY-MM-snapshot.md` (mensal) ou `YYYY-Wxx-snapshot.md` (semanal)

## O que NAO vai aqui

- Dados brutos (vivem em outro lugar - DB, planilhas, observability)
- Dados financeiros sensiveis (vivem em ledger separado, fora do bevox-knowledge)

Aqui entram apenas **definicoes e analises**, nao os dados em si.
EOF
```

- [ ] **Step 10: Verificar todos os READMEs**

```bash
find ~/bevox-knowledge -maxdepth 2 -name 'README.md' -type f | sort
```

Expected: 9 READMEs listados (raiz nao conta porque so as 9 pastas top-level).

Wait - nao conta o README.md raiz. So as pastas. Vai dar 9 READMEs em pastas top-level + 1 raiz = 10 total. Mas o find acima ja captura `2 niveis`, entao deve listar tudo.

Confirmar:
```bash
find ~/bevox-knowledge -maxdepth 2 -name 'README.md' | wc -l
```

Expected: `10` (1 raiz + 9 das pastas top-level).

---

## Task 6: README e files do `20_architecture/agents/`

**Files:**
- Create: `~/bevox-knowledge/20_architecture/agents/README.md`
- Create: `~/bevox-knowledge/20_architecture/agents/_retired/README.md`
- Create: `~/bevox-knowledge/20_architecture/agents/registry.md`

- [ ] **Step 1: Criar README do `agents/`**

```bash
cat > ~/bevox-knowledge/20_architecture/agents/README.md <<'EOF'
# Agents

Definicoes formais dos agentes do Company OS da Bevox.

## O que vai aqui

- Um arquivo `.md` por agente ativo
- `registry.md` - tabela canonica com todos os agentes ativos
- `_retired/` - agentes aposentados (preserva historico)

## Formato de definicao de agente

Cada agente tem um arquivo `[agent-name].md` com:

- Nome, owner, status, level
- Modelo padrao e fallback
- Missao (uma frase)
- Inputs e outputs
- Skills habilitadas
- Limites (o que NUNCA faz)
- Politica de approvals (referencia ADR-006)
- KPIs
- Playbook operacional
- Historico de levels

Veja `ADR-003` em `../../30_adr/` para o template completo.

## Convencao de nomenclatura

`{agent-name}.md` em kebab-case.

Exemplos:
- `vox.md`
- `product-agent.md`
- `github-admin.md`

## Levels

Veja `ADR-003` para a politica de leveling L1-L4 e ciclo de vida.

## Aposentar um agente

NAO apagar arquivos. Mover para `_retired/` e atualizar `registry.md`.

```bash
git mv [agent-name].md _retired/
# editar registry.md removendo a linha
git commit -m "agent({name}): retire (motivo)"
```
EOF
```

- [ ] **Step 2: Criar README do `_retired/`**

```bash
cat > ~/bevox-knowledge/20_architecture/agents/_retired/README.md <<'EOF'
# _retired

Cemiterio de agentes aposentados. Preserva o historico e o aprendizado.

## Por que existe

Agentes nao sao apagados quando aposentados - sao movidos para ca. O historico de cada agente fica acessivel para:

- Entender o que ja foi tentado
- Preservar contexto que pode ser util no futuro
- Evitar recriar agentes que falharam pelos mesmos motivos
- Auditoria

## O que ler aqui

Quando estiver pensando em criar um novo agente, valer a pena verificar se ja existe (ou existiu) um similar aqui. Pode haver licoes aprendidas relevantes.

## Estrutura

Cada arquivo aposentado mantem o conteudo original mais uma secao final:

```markdown
## Aposentadoria

- **Data:** YYYY-MM-DD
- **Motivo:** [breve]
- **Substituido por:** [outro agente, skill, ou nada]
- **Aprendizados:** [o que ficou para o futuro]
```
EOF
```

- [ ] **Step 3: Criar `registry.md` com Vox L4**

```bash
cat > ~/bevox-knowledge/20_architecture/agents/registry.md <<'EOF'
# Agent Registry

> Registry canonico dos agentes ativos do Company OS da Bevox.
> Atualizado manualmente. Promocoes/aposentadorias atualizam essa tabela.

## Agentes ativos

| Agente | Status | Level | Owner | Modelo padrao | Modelo fallback | Desde |
|---|---|---|---|---|---|---|
| vox | ativo | L4 | Bernard | openai-codex/gpt-5.4 | openrouter/healer-alpha | 2026-04-08 |

## Legenda

- **Status:** ativo, suspenso, aposentado
- **Level:** L1 Observer, L2 Contributor, L3 Operator, L4 Trusted (ver ADR-003)

## Como atualizar

### Promover um agente

1. Editar o arquivo do agente em `[agent-name].md` (campo `Level:`)
2. Adicionar entrada em "Historico de levels" do mesmo arquivo
3. Atualizar coluna `Level` nesta tabela
4. Commit: `agent({name}): promote L{X} -> L{Y}`

### Aposentar um agente

1. `git mv [agent-name].md _retired/`
2. Adicionar secao "Aposentadoria" no arquivo movido
3. Remover a linha desta tabela
4. Commit: `agent({name}): retire (motivo: {curto})`

### Criar um agente novo

1. Comecar SEMPRE em L1 (ver ADR-003)
2. Criar `[agent-name].md` com o template completo
3. Adicionar linha nesta tabela
4. Commit: `agent({name}): create (L1, owner: {nome})`

## Referencia

- Politica de governanca: `../../30_adr/ADR-003-agent-governance.md`
- Politica de autonomia/approvals: `../../30_adr/ADR-006-autonomy-permissions-approval.md`
EOF
```

- [ ] **Step 4: Verificar arquivos criados**

```bash
ls ~/bevox-knowledge/20_architecture/agents/
ls ~/bevox-knowledge/20_architecture/agents/_retired/
```

Expected:
```
README.md  _retired/  registry.md
README.md
```

---

## Task 7: Template MADR

**Files:**
- Create: `~/bevox-knowledge/30_adr/_template.md`

- [ ] **Step 1: Criar `_template.md`**

Conteudo extraido da spec, secao 2.4 (`### 2.4 Template MADR`). Transcrever literalmente.

```bash
cat > ~/bevox-knowledge/30_adr/_template.md <<'EOF'
# ADR-XXX: [Titulo curto e ativo]

- **Status:** [proposta | aceita | descartada | substituida-por-ADR-YYY]
- **Data:** YYYY-MM-DD
- **Decisor:** Bernard
- **Tags:** [tag1, tag2]

## Contexto e Problema

Descreve a situacao que torna essa decisao necessaria. Por que precisamos decidir agora? O que esta em jogo se nao decidirmos? Que forcas competem?

## Opcoes Consideradas

- **Opcao A:** [nome curto]
  - Descricao: [...]
  - Pros: [...]
  - Contras: [...]

- **Opcao B:** [nome curto]
  - Descricao: [...]
  - Pros: [...]
  - Contras: [...]

## Recomendacao

Qual opcao recomendo e por que. Use evidencias do contexto ou da experiencia.

## Decisao

[Preenchido quando o status muda para "aceita". Registra qual opcao foi escolhida e qual a razao final.]

## Consequencias

### Positivas
- [...]

### Negativas
- [...]

### Neutras
- [...]

## Impacto em Specs Futuras

Liste epicos/specs do roadmap que dependem dessa decisao e como mudam com base nela.

## Notas

- Decisoes relacionadas: [links]
- Referencias externas: [links]
- Historico de mudancas: [...]
EOF
```

- [ ] **Step 2: Verificar**

```bash
ls ~/bevox-knowledge/30_adr/_template.md
wc -l ~/bevox-knowledge/30_adr/_template.md
```

Expected: arquivo existe, ~45 linhas.

---

## Task 8: ADR-001 Company OS Boundary

**Files:**
- Create: `~/bevox-knowledge/30_adr/ADR-001-company-os-boundary.md`

**Content source:** Spec secao 3 (`## 3. ADR-001: Company OS Boundary`).

- [ ] **Step 1: Ler a secao 3 da spec**

```bash
sed -n '/^## 3\. ADR-001/,/^## 4\. ADR-002/p' ~/.openclaw/docs/superpowers/specs/2026-04-09-foundation-freeze-design.md | head -n -1
```

Isso imprime todo o conteudo da secao 3 (excluindo a linha que comeca a secao 4).

- [ ] **Step 2: Criar o arquivo `ADR-001-company-os-boundary.md`**

O arquivo deve conter o conteudo completo extraido na Step 1, mas com tres ajustes:

1. Trocar o titulo da secao de `## 3. ADR-001: Company OS Boundary` para `# ADR-001: Company OS Boundary`
2. Ajustar a numeracao das subsecoes: `### 3.1`, `### 3.2`, etc. viram `## Contexto e Problema`, `## Opcoes Consideradas`, etc.
3. Manter os campos `Status proposto`, `Data`, `Decisor`, `Tags` no topo (apos titulo).

Comando:

```bash
cat > ~/bevox-knowledge/30_adr/ADR-001-company-os-boundary.md <<'EOF'
# ADR-001: Company OS Boundary

- **Status:** proposta
- **Data:** 2026-04-09
- **Decisor:** Bernard
- **Tags:** boundary, scope, foundation

## Contexto e Problema

A Bevox tem dois ambientes operacionais que o Bernard usa em paralelo: o **OpenClaw** (rodando como company OS interno com o agente Vox) e o **Claude Code** (CLI da Anthropic usado para coding). Sem uma fronteira formal, as duas ferramentas comecam a competir pelo mesmo proposito - quem documenta o que? quem executa o que? onde mora qual codigo? - e isso gera drift de contexto, duplicacao de esforco e decisoes operacionais inconsistentes.

A pergunta central: **o que cabe a cada ferramenta?**

## Opcoes Consideradas

**Opcao A: Boundary funcional clara (recomendada)**

- **OpenClaw** = Company OS. Cuida de operacao, governanca, agentes, memoria, coordenacao, dashboards internos, automacoes operacionais e comunicacao por canais (Telegram).
- **Claude Code** = Ambiente principal de coding. Usado para escrever/refatorar/debugar codigo do produto Bevox e projetos relacionados.
- **Sobreposicao permitida:** Claude Code pode editar configs do OpenClaw quando o Bernard precisar iterar (ex: editar `openclaw.json`, criar skills). OpenClaw pode invocar Claude Code via skill `coding-agent` para tarefas de coding maiores.
- **Pros:** Fronteira clara baseada em proposito, nao em tipo de arquivo. Permite handoff explicito.
- **Contras:** Requer disciplina para nao usar OpenClaw como editor de codigo improvisado.

**Opcao B: Boundary por tipo de arquivo**

- OpenClaw cuida de tudo em `~/.openclaw/` e `bevox-knowledge/`. Claude Code cuida de tudo em outros repositorios.
- **Pros:** Regra mecanica, dificil de violar.
- **Contras:** Frageis - quando o codigo do produto precisa ser referenciado pelo OpenClaw (ex: agentes lendo PRDs do bevox-knowledge), a regra trava.

**Opcao C: OpenClaw substitui Claude Code completamente**

- OpenClaw vira o ambiente unico de tudo, incluindo coding.
- **Pros:** Uma ferramenta so.
- **Contras:** OpenClaw nao foi feito para coding intensivo. Perderia features especificas do Claude Code (TUI, ferramentas de edicao avancadas, integracao com IDE). Quebra um dos principios do roadmap ("OpenClaw nao e ambiente principal de coding").

## Recomendacao

**Opcao A.** A separacao por proposito e a unica que escala. Claude Code e otimizado para edicao de codigo (rapido, focado, com TUI dedicada). OpenClaw e otimizado para orquestracao, memoria persistente, integracao com canais e operacao por agentes. Tentar fundir os dois cria atrito em ambos.

A regra operacional fica:

> **Coding do produto: Claude Code.**
> **Operacao da empresa: OpenClaw.**
> **Knowledge compartilhado: bevox-knowledge.**
> **Handoff entre os dois: explicito, via knowledge repo ou skill `coding-agent`.**

## Decisao

(Preenchido apos aprovacao do Bernard)

## Consequencias

### Positivas
- Cada ferramenta usada para o que faz melhor
- Memoria operacional fica no OpenClaw
- Memoria de codigo fica nos repos do produto + bevox-knowledge
- Sem competicao de propositos

### Negativas
- Bernard precisa lembrar qual ferramenta usar para qual tarefa (mitigacao: regra simples)
- Algumas tarefas hibridas (ex: editar config do OpenClaw enquanto trabalha no produto) exigem trocar de contexto

### Neutras
- O conceito de "agente" so existe no OpenClaw - Claude Code e ambiente sem agentes persistentes
- Toda automacao de operacao (cron, hooks, watchdogs) mora no OpenClaw

## Impacto em Specs Futuras

- **E1 (Knowledge Spine):** define que `bevox-knowledge` e o ponto de encontro entre OpenClaw e Claude Code
- **E2 (Mission Control):** Mission Control e UI do OpenClaw, nao do Claude Code
- **E3 (Agent Registry):** agentes existem so no OpenClaw
- **E6 (GitHub Operations):** integracao GitHub e do OpenClaw, mas Claude Code pode usar `gh CLI` quando esta editando codigo
- **E10 (Functional Agents):** todos os agentes pertencem ao OpenClaw

## Notas

- Decisoes relacionadas: ADR-005 (knowledge source of truth)
- Workspace atual ja segue essa intuicao informalmente - veja `~/.openclaw/workspace/AGENTS.md`
EOF
```

- [ ] **Step 3: Verificar**

```bash
wc -l ~/bevox-knowledge/30_adr/ADR-001-company-os-boundary.md
head -10 ~/bevox-knowledge/30_adr/ADR-001-company-os-boundary.md
```

Expected: ~70 linhas, comeca com `# ADR-001: Company OS Boundary`.

---

## Task 9: ADR-002 System Topology

**Files:**
- Create: `~/bevox-knowledge/30_adr/ADR-002-system-topology.md`

**Content source:** Spec secao 4 (`## 4. ADR-002: System Topology`).

- [ ] **Step 1: Criar arquivo `ADR-002-system-topology.md`**

```bash
cat > ~/bevox-knowledge/30_adr/ADR-002-system-topology.md <<'EOF'
# ADR-002: System Topology

- **Status:** proposta
- **Data:** 2026-04-09
- **Decisor:** Bernard
- **Tags:** topology, modules, foundation

## Contexto e Problema

A Bevox tem multiplos modulos de produto e multiplos modulos de operacao, mas atualmente nao existe um mapa canonico que define **quais modulos existem, como se chamam e como se relacionam.** Esse vazio gera nomes inconsistentes (e.g., "console" vs "admin" vs "dashboard"), agentes que nao sabem qual produto referenciar, e PRDs que mencionam modulos sem precisao.

Esta ADR estabelece a topologia inicial e separa **Produto Bevox** (o que vendemos/oferecemos) de **Company OS** (como operamos a empresa).

## Sinais ja presentes no contexto

Olhando os artefatos atuais:
- O PRD de security hardening em `media/inbound/` lista as areas: `area:openclaw`, `area:console`, `area:harness`, `area:web`, `area:mobile`
- O `OPERATING_RULES.md` menciona "console/harness" como produtos
- O `AGENTS.md` menciona OpenClaw como company OS, separado do produto

Conclusao: existem 4 modulos canonicos de produto (console, harness, web, mobile) + Company OS (openclaw).

## Topologia Proposta

### Produto Bevox

Quatro modulos canonicos, organizados em duas camadas:

**Camada de runtime (backend):**

| Modulo | Proposito proposto | Status |
|---|---|---|
| **bevox-harness** | Runtime onde os agentes do produto Bevox rodam. Hospeda sessoes dos clientes finais, executa skills, gerencia memoria persistente, expoe capacidades para os clientes via os modulos de interface. E o "motor" do produto agent-first. | A confirmar |
| **bevox-console** | Painel administrativo onde operadores da Bevox (e o proprio Bernard) gerenciam usuarios, monitoram a operacao do harness, executam acoes internas e acessam logs/metricas. Interface para **operar** o produto, nao para **usa-lo**. | A confirmar |

**Camada de cliente (frontend):**

| Modulo | Proposito proposto | Status |
|---|---|---|
| **bevox-web** | Aplicacao web voltada ao cliente final. Interface principal pela qual usuarios interagem com os agentes Bevox via navegador. | A confirmar |
| **bevox-mobile** | App mobile (iOS/Android) voltado ao cliente final. Mesma proposta do bevox-web, com experiencia otimizada para celular e recursos nativos (notificacoes push, biometria, etc.). | A confirmar |

> **Nota:** propositos sao propostas baseadas no contexto que o Vox observou. Bernard valida/corrige na revisao desta ADR. Bevox-api **nao** e canonizado agora - se ele existir como modulo separado no futuro, vira ADR propria.

### Company OS

| Modulo | Proposito | Status atual |
|---|---|---|
| **openclaw** | Plataforma de agentes auto-hospedada (gateway, sessoes, hooks) | Ativo, v2026.4.8 |
| **vox** | Agente principal (chief of staff digital) | Ativo, level L4 |
| **bevox-knowledge** | Fonte unica de verdade (PRDs, ADRs, roadmaps, etc) | A criar (E0) |
| **mission-control** | UI executiva centralizada para operar a empresa | A criar (E2) |
| **agent-registry** | Cadastro formal de agentes com governanca | A criar (E3) |
| **approval-center** | Sistema de aprovacao de acoes sensiveis | A criar (E4) |

### Relacoes principais

```
                  +-------------------------+
                  |     bevox-knowledge     |
                  |  (fonte unica verdade)  |
                  +-------------------------+
                       ^              ^
                       | le/escreve   | le
                       |              |
              +--------+              +---------+
              |                                 |
   +----------+----------+            +---------+--------+
   |     OpenClaw        |            |    Claude Code   |
   |  (Company OS)       |            |  (Coding amb.)   |
   |                     |            |                  |
   |  - Vox              |            |  - Edicao codigo |
   |  - Memory           |            |  - Refactor      |
   |  - Mission Control  |            |  - Debug         |
   |  - Agents           |            |                  |
   |  - Cron/hooks       |            |                  |
   +--------+------------+            +--------+---------+
            |                                  |
            v                                  v
   +--------+---------+             +----------+----------+
   |  Telegram/Canais |             |  Repos do produto:  |
   |                  |             |  bevox-web          |
   |  Bernard         |             |  bevox-mobile       |
   |                  |             |  bevox-console      |
   +------------------+             |  bevox-harness      |
                                    +---------------------+
```

## Opcoes Consideradas

**Opcao A: Topologia formal (recomendada)**

Reconhecer 4 modulos de produto + Company OS como entidades nomeadas e versionadas. Cada um tem seu repositorio proprio.

**Opcao B: Monorepo do produto**

Um unico repo `bevox` contendo web, mobile, console, harness como subdiretorios.
- **Pros:** Refactors cross-module mais faceis, versionamento atomico
- **Contras:** CI/CD mais complexo, mais lento para builds parciais, nao reflete a realidade de mobile (apple/android tem ciclos proprios)

**Opcao C: So flagar o que ja existe sem criar topologia**

Esperar e documentar conforme as coisas surgem.
- **Contras:** Drift garantido. ADRs e specs precisam de nomes canonicos JA.

## Recomendacao

**Opcao A.** A topologia formal e necessaria para que todas as outras specs (E1 a E12) tenham vocabulario consistente. Mesmo que alguns modulos ainda nao existam como repositorios concretos, eles existem como conceitos no roadmap.

Quando o Bernard responder qual e o proposito real de cada modulo, esta ADR vira o mapa oficial.

## Decisao

(Preenchido apos revisao)

## Consequencias

### Positivas
- Vocabulario unico em todo Company OS
- Agentes referenciam modulos por nomes canonicos
- ADRs futuras podem ser categorizadas por area (`area:bevox-web`, `area:openclaw`, etc.)

### Negativas
- Renomear modulo no futuro custa propaganda em todos os documentos
- Decisao precisa ser feita com informacao incompleta (alguns modulos ainda nem existem)

## Impacto em Specs Futuras

- **E0-F4 (labels GitHub):** as labels `area:*` vem desta topologia
- **E1 (knowledge spine):** o `module-map.md` e a versao detalhada do system-map
- **E5 (Roadmap & Delivery):** items do backlog sao categorizados por area
- **E6 (GitHub Operations):** repos a sincronizar derivam desta topologia
- **E7 (Documentation System):** docs sao organizadas por modulo

## Acao requerida do Bernard antes da aceitacao

Preencher/confirmar para cada um dos 4 modulos canonicos:
1. Existe hoje? (sim/nao/em planejamento)
2. O proposito proposto esta correto? Editar se nao.
3. Qual a stack tecnica?
4. Tem repositorio? Se sim, qual a URL?
5. Qual o status atual (alpha/beta/producao/em desenho)?

Se um modulo precisa ser adicionado (ex: bevox-api futuro), abrir ADR substituidora desta.
EOF
```

- [ ] **Step 2: Verificar**

```bash
wc -l ~/bevox-knowledge/30_adr/ADR-002-system-topology.md
grep -c "bevox-api" ~/bevox-knowledge/30_adr/ADR-002-system-topology.md
```

Expected: ~120 linhas. `bevox-api` aparece 1 vez (na nota explicando que NAO e canonizado).

---

## Task 10: ADR-003 Agent Governance

**Files:**
- Create: `~/bevox-knowledge/30_adr/ADR-003-agent-governance.md`

**Content source:** Spec secao 6 (`## 6. ADR-003: Agent Governance`). Esta secao e LONGA. O agente executor deve abrir a spec, copiar a secao 6 inteira, e ajustar:
1. Titulo de `## 6. ADR-003: Agent Governance` para `# ADR-003: Agent Governance`
2. Subsecoes `### 6.X` viram `## ` sem numeracao
3. Manter os 4 campos de cabecalho (Status, Data, Decisor, Tags)

- [ ] **Step 1: Extrair conteudo da spec**

```bash
sed -n '/^## 6\. ADR-003/,/^## 7\. ADR-006/p' ~/.openclaw/docs/superpowers/specs/2026-04-09-foundation-freeze-design.md | head -n -1 > /tmp/adr-003-raw.md
wc -l /tmp/adr-003-raw.md
```

Expected: ~140 linhas extraidas.

- [ ] **Step 2: Transformar com sed e salvar**

```bash
sed \
  -e 's/^## 6\. ADR-003: Agent Governance$/# ADR-003: Agent Governance/' \
  -e 's/^### 6\.[0-9]\+ //' \
  -e 's/^\*\*Status proposto:\*\* proposta$/- **Status:** proposta/' \
  -e 's/^\*\*Data:\*\* /- **Data:** /' \
  -e 's/^\*\*Decisor:\*\* /- **Decisor:** /' \
  -e 's/^\*\*Tags:\*\* /- **Tags:** /' \
  /tmp/adr-003-raw.md > ~/bevox-knowledge/30_adr/ADR-003-agent-governance.md
```

- [ ] **Step 3: Verificar resultado**

```bash
head -10 ~/bevox-knowledge/30_adr/ADR-003-agent-governance.md
```

Expected output (cabecalho):
```
# ADR-003: Agent Governance

- **Status:** proposta
- **Data:** 2026-04-09
- **Decisor:** Bernard
- **Tags:** agents, governance, leveling
```

```bash
grep -c "Promocao NAO gera ADR nova" ~/bevox-knowledge/30_adr/ADR-003-agent-governance.md
```

Expected: `1` (frase critica deve estar presente).

```bash
wc -l ~/bevox-knowledge/30_adr/ADR-003-agent-governance.md
```

Expected: ~140 linhas.

- [ ] **Step 4: Limpar arquivo temporario**

```bash
rm /tmp/adr-003-raw.md
```

---

## Task 11: ADR-004 Naming Canonical

**Files:**
- Create: `~/bevox-knowledge/30_adr/ADR-004-naming-canonical.md`

**Content source:** Spec secao 8 (`## 8. ADR-004: Naming Canonical`).

- [ ] **Step 1: Extrair e transformar**

```bash
sed -n '/^## 8\. ADR-004/,/^## 9\. system-map/p' ~/.openclaw/docs/superpowers/specs/2026-04-09-foundation-freeze-design.md | head -n -1 > /tmp/adr-004-raw.md

sed \
  -e 's/^## 8\. ADR-004: Naming Canonical$/# ADR-004: Naming Canonical/' \
  -e 's/^### 8\.[0-9]\+\(\.[0-9]\+\)\? //' \
  -e 's/^\*\*Status proposto:\*\* proposta$/- **Status:** proposta/' \
  -e 's/^\*\*Data:\*\* /- **Data:** /' \
  -e 's/^\*\*Decisor:\*\* /- **Decisor:** /' \
  -e 's/^\*\*Tags:\*\* /- **Tags:** /' \
  /tmp/adr-004-raw.md > ~/bevox-knowledge/30_adr/ADR-004-naming-canonical.md
```

- [ ] **Step 2: Verificar**

```bash
head -10 ~/bevox-knowledge/30_adr/ADR-004-naming-canonical.md
grep -c "kebab-case" ~/bevox-knowledge/30_adr/ADR-004-naming-canonical.md
wc -l ~/bevox-knowledge/30_adr/ADR-004-naming-canonical.md
```

Expected:
- Cabecalho com `# ADR-004: Naming Canonical`, status proposta
- `kebab-case` aparece varias vezes (>5)
- ~110 linhas

- [ ] **Step 3: Cleanup**

```bash
rm /tmp/adr-004-raw.md
```

---

## Task 12: ADR-005 Knowledge Source of Truth & Context Sync

**Files:**
- Create: `~/bevox-knowledge/30_adr/ADR-005-knowledge-source-of-truth.md`

**Content source:** Spec secao 5 (`## 5. ADR-005: Knowledge Source of Truth & Context Sync`).

- [ ] **Step 1: Extrair e transformar**

```bash
sed -n '/^## 5\. ADR-005/,/^## 6\. ADR-003/p' ~/.openclaw/docs/superpowers/specs/2026-04-09-foundation-freeze-design.md | head -n -1 > /tmp/adr-005-raw.md

sed \
  -e 's/^## 5\. ADR-005: Knowledge Source of Truth & Context Sync$/# ADR-005: Knowledge Source of Truth \& Context Sync/' \
  -e 's/^### 5\.[0-9]\+ //' \
  -e 's/^\*\*Status proposto:\*\* proposta$/- **Status:** proposta/' \
  -e 's/^\*\*Data:\*\* /- **Data:** /' \
  -e 's/^\*\*Decisor:\*\* /- **Decisor:** /' \
  -e 's/^\*\*Tags:\*\* /- **Tags:** /' \
  /tmp/adr-005-raw.md > ~/bevox-knowledge/30_adr/ADR-005-knowledge-source-of-truth.md
```

- [ ] **Step 2: Verificar**

```bash
head -10 ~/bevox-knowledge/30_adr/ADR-005-knowledge-source-of-truth.md
grep -c "bevox-knowledge" ~/bevox-knowledge/30_adr/ADR-005-knowledge-source-of-truth.md
wc -l ~/bevox-knowledge/30_adr/ADR-005-knowledge-source-of-truth.md
```

Expected:
- Cabecalho `# ADR-005: Knowledge Source of Truth & Context Sync`
- `bevox-knowledge` aparece >10 vezes
- ~130 linhas

- [ ] **Step 3: Cleanup**

```bash
rm /tmp/adr-005-raw.md
```

---

## Task 13: ADR-006 Autonomy, Permissions & Approval Policy

**Files:**
- Create: `~/bevox-knowledge/30_adr/ADR-006-autonomy-permissions-approval.md`

**Content source:** Spec secao 7 (`## 7. ADR-006: Autonomy, Permissions & Approval Policy`).

- [ ] **Step 1: Extrair e transformar**

```bash
sed -n '/^## 7\. ADR-006/,/^## 8\. ADR-004/p' ~/.openclaw/docs/superpowers/specs/2026-04-09-foundation-freeze-design.md | head -n -1 > /tmp/adr-006-raw.md

sed \
  -e 's/^## 7\. ADR-006: Autonomy, Permissions & Approval Policy$/# ADR-006: Autonomy, Permissions \& Approval Policy/' \
  -e 's/^### 7\.[0-9]\+ //' \
  -e 's/^\*\*Status proposto:\*\* proposta$/- **Status:** proposta/' \
  -e 's/^\*\*Data:\*\* /- **Data:** /' \
  -e 's/^\*\*Decisor:\*\* /- **Decisor:** /' \
  -e 's/^\*\*Tags:\*\* /- **Tags:** /' \
  /tmp/adr-006-raw.md > ~/bevox-knowledge/30_adr/ADR-006-autonomy-permissions-approval.md
```

- [ ] **Step 2: Verificar**

```bash
head -10 ~/bevox-knowledge/30_adr/ADR-006-autonomy-permissions-approval.md
grep -c "write-knowledge-draft" ~/bevox-knowledge/30_adr/ADR-006-autonomy-permissions-approval.md
grep -c "write-knowledge-canonical" ~/bevox-knowledge/30_adr/ADR-006-autonomy-permissions-approval.md
grep -c "Hard Limits" ~/bevox-knowledge/30_adr/ADR-006-autonomy-permissions-approval.md
wc -l ~/bevox-knowledge/30_adr/ADR-006-autonomy-permissions-approval.md
```

Expected:
- Cabecalho correto
- `write-knowledge-draft` >= 2
- `write-knowledge-canonical` >= 2
- `Hard Limits` >= 1
- ~180 linhas

- [ ] **Step 3: Cleanup**

```bash
rm /tmp/adr-006-raw.md
```

---

## Task 14: system-map.md inicial

**Files:**
- Create: `~/bevox-knowledge/20_architecture/system-map.md`

**Content source:** Spec secao 9 (`## 9. system-map.md inicial`).

- [ ] **Step 1: Criar arquivo com conteudo extraido**

```bash
cat > ~/bevox-knowledge/20_architecture/system-map.md <<'EOF'
# System Map - Bevox

> Mapa canonico dos modulos da Bevox e como eles se relacionam.
> Esse documento e gerado a partir das decisoes em ADR-002 (System Topology).
> Ultima atualizacao: 2026-04-09

## Visao Geral

A Bevox tem dois grandes dominios:

1. **Produto Bevox** - o que oferecemos ao mercado
2. **Company OS** - como operamos a empresa

Os dois conversam via `bevox-knowledge` (fonte unica de verdade).

## Produto Bevox

| Modulo | Repo | Status | Stack | Owner |
|---|---|---|---|---|
| Bevox Web | `bevox-web` | TBD | TBD | Bernard |
| Bevox Mobile | `bevox-mobile` | TBD | TBD | Bernard |
| Bevox Console | `bevox-console` | TBD | TBD | Bernard |
| Bevox Harness | `bevox-harness` | TBD | TBD | Bernard |

> Os campos TBD serao preenchidos quando ADR-002 for aceita com o input do Bernard.

## Company OS

| Modulo | Localizacao | Status | Owner |
|---|---|---|---|
| OpenClaw | `~/.openclaw/` (host local) | Ativo (v2026.4.8) | Bernard |
| Vox | Agente principal do OpenClaw | Ativo (L4) | Bernard |
| bevox-knowledge | `github.com/[org]/bevox-knowledge` | Ativo (criado no E0) | Bernard |
| Mission Control | TBD (E2) | A criar | Bernard |
| Agent Registry | `bevox-knowledge/20_architecture/agents/` | Ativo (criado no E0) | Bernard |
| Approval Center | TBD (E4) | A criar | Bernard |

## Diagrama de Fluxo

```
                  +-------------------------+
                  |     bevox-knowledge     |
                  |  (fonte unica verdade)  |
                  +-------------------------+
                       ^              ^
                       | le/escreve   | le
                       |              |
              +--------+              +---------+
              |                                 |
   +----------+----------+            +---------+--------+
   |     OpenClaw        |            |    Claude Code   |
   |  (Company OS)       |            |  (Coding amb.)   |
   |                     |            |                  |
   |  - Vox              |            |  - Edicao codigo |
   |  - Memory           |            |  - Refactor      |
   |  - Mission Control  |            |  - Debug         |
   |  - Agents           |            |                  |
   |  - Cron/hooks       |            |                  |
   +--------+------------+            +--------+---------+
            |                                  |
            v                                  v
   +--------+---------+             +----------+----------+
   |  Telegram/Canais |             |  Repos do produto:  |
   |                  |             |  bevox-web          |
   |  Bernard         |             |  bevox-mobile       |
   |                  |             |  bevox-console      |
   +------------------+             |  bevox-harness      |
                                    +---------------------+
```

## Dependencias entre modulos

- **OpenClaw → bevox-knowledge:** leitura via filesystem
- **Claude Code → bevox-knowledge:** leitura via filesystem
- **bevox-knowledge → GitHub:** push/pull manual (E0), automatizado (E1+)
- **OpenClaw → Telegram:** comunicacao bidirecional via bot
- **Vox → outros agentes:** orquestracao via OpenClaw gateway (futuro)

## Relacao com ADRs

Este mapa e a representacao visual de:
- ADR-001 (boundary)
- ADR-002 (topologia)
- ADR-005 (knowledge spine)

Quando alguma dessas ADRs for atualizada, este mapa precisa ser atualizado tambem.
EOF
```

- [ ] **Step 2: Verificar**

```bash
ls ~/bevox-knowledge/20_architecture/system-map.md
grep -c "bevox-harness" ~/bevox-knowledge/20_architecture/system-map.md
grep -c "bevox-api" ~/bevox-knowledge/20_architecture/system-map.md
```

Expected:
- Arquivo existe
- `bevox-harness` >= 2 (uma na tabela, uma no diagrama)
- `bevox-api` = 0 (NAO deve aparecer)

---

## Task 15: Sanity check completo da estrutura

**Files:** Nenhum (apenas verificacao)

- [ ] **Step 1: Verificar arvore completa**

```bash
find ~/bevox-knowledge -type f ! -path '*/.git/*' | sort
```

Expected output (lista esperada de 22 arquivos):
```
~/bevox-knowledge/.gitignore
~/bevox-knowledge/00_inbox/README.md
~/bevox-knowledge/10_prd/README.md
~/bevox-knowledge/20_architecture/README.md
~/bevox-knowledge/20_architecture/agents/README.md
~/bevox-knowledge/20_architecture/agents/_retired/README.md
~/bevox-knowledge/20_architecture/agents/registry.md
~/bevox-knowledge/20_architecture/system-map.md
~/bevox-knowledge/30_adr/ADR-001-company-os-boundary.md
~/bevox-knowledge/30_adr/ADR-002-system-topology.md
~/bevox-knowledge/30_adr/ADR-003-agent-governance.md
~/bevox-knowledge/30_adr/ADR-004-naming-canonical.md
~/bevox-knowledge/30_adr/ADR-005-knowledge-source-of-truth.md
~/bevox-knowledge/30_adr/ADR-006-autonomy-permissions-approval.md
~/bevox-knowledge/30_adr/README.md
~/bevox-knowledge/30_adr/_template.md
~/bevox-knowledge/35_specs/README.md
~/bevox-knowledge/40_roadmap/README.md
~/bevox-knowledge/50_releases/README.md
~/bevox-knowledge/60_customer-feedback/README.md
~/bevox-knowledge/70_metrics/README.md
~/bevox-knowledge/README.md
~/bevox-knowledge/decision-log.md
```

Total: 23 arquivos.

```bash
find ~/bevox-knowledge -type f ! -path '*/.git/*' | wc -l
```

Expected: `23`

- [ ] **Step 2: Verificar que nenhuma ADR tem placeholders nao-intencionais**

```bash
grep -l "XXX\|titulo curto" ~/bevox-knowledge/30_adr/ADR-00*.md
```

Expected: nenhum arquivo retornado (so o `_template.md` deveria ter `XXX`, mas a Step 2 do filtro nao incluiu o template).

- [ ] **Step 3: Verificar status `proposta` em todas as 6 ADRs**

```bash
grep -c "Status:.* proposta" ~/bevox-knowledge/30_adr/ADR-00*.md
```

Expected output:
```
~/bevox-knowledge/30_adr/ADR-001-company-os-boundary.md:1
~/bevox-knowledge/30_adr/ADR-002-system-topology.md:1
~/bevox-knowledge/30_adr/ADR-003-agent-governance.md:1
~/bevox-knowledge/30_adr/ADR-004-naming-canonical.md:1
~/bevox-knowledge/30_adr/ADR-005-knowledge-source-of-truth.md:1
~/bevox-knowledge/30_adr/ADR-006-autonomy-permissions-approval.md:1
```

Se algum mostrar `0`, voltar para a task respectiva e investigar.

---

## Task 16: Primeiro commit (estrutura + ADRs + system-map + registry)

**Files:** Todos os arquivos criados nas Tasks 2-14 sao adicionados ao git.

- [ ] **Step 1: Verificar status do git**

```bash
cd ~/bevox-knowledge && git status
```

Expected: lista 23 arquivos como `Untracked files`.

- [ ] **Step 2: Adicionar tudo**

```bash
cd ~/bevox-knowledge && git add .
```

- [ ] **Step 3: Verificar que tudo foi staged**

```bash
cd ~/bevox-knowledge && git status
```

Expected: 23 arquivos como `Changes to be committed`.

- [ ] **Step 4: Configurar git user (se nao configurado)**

```bash
cd ~/bevox-knowledge
git config user.email 2>/dev/null || git config user.email "you@example.com"
git config user.name 2>/dev/null || git config user.name "Bernard Tavares"
```

- [ ] **Step 5: Commit**

```bash
cd ~/bevox-knowledge && git commit -m "$(cat <<'EOF'
chore: bootstrap bevox-knowledge with E0 foundation

Cria estrutura inicial do bevox-knowledge com:
- 9 pastas top-level (00_inbox a 70_metrics + 35_specs)
- README raiz com convencoes
- decision-log.md como indice das ADRs
- 6 ADRs redigidas como propostas (E0 - Foundation Freeze)
- system-map.md inicial com 4 modulos canonicos do produto
- agents/registry.md com Vox L4
- _template.md MADR para futuras ADRs

Spec source: docs/superpowers/specs/2026-04-09-foundation-freeze-design.md

Refs: roadmap E0
EOF
)"
```

Expected output:
```
[main (root-commit) <hash>] chore: bootstrap bevox-knowledge with E0 foundation
 23 files changed, XXXX insertions(+)
 ...
```

- [ ] **Step 6: Verificar commit**

```bash
cd ~/bevox-knowledge && git log --oneline
```

Expected: 1 commit listado.

---

## Task 17: Push para remote

**Files:** Nenhum (operacao git).

- [ ] **Step 1: Push para o remote `main`**

```bash
cd ~/bevox-knowledge && git push -u origin main
```

Expected output:
```
Enumerating objects: ...
Counting objects: ...
...
To github.com:<ORG>/bevox-knowledge.git
 * [new branch]      main -> main
branch 'main' set up to track 'origin/main' from 'origin'.
```

Se houver erro, possiveis causas:
- Branch local e `master` em vez de `main`: `git branch -m master main && git push -u origin main`
- Sem permissao: voltar para Task 0 e revalidar `gh auth status`
- Repo nao existe no remote: voltar para Task 1 Step 3

- [ ] **Step 2: Verificar no GitHub**

```bash
gh repo view ${BEVOX_GITHUB_ORG}/bevox-knowledge --web
```

Isso abre o repo no navegador. Confirmar visualmente que os 23 arquivos estao la.

Alternativamente, verificar via CLI:

```bash
gh api repos/${BEVOX_GITHUB_ORG}/bevox-knowledge/contents | jq -r '.[].name' | sort
```

Expected: lista de pastas e arquivos top-level.

---

## Task 18: Tag v0.0-bootstrap

**Files:** Nenhum (operacao git).

- [ ] **Step 1: Criar tag**

```bash
cd ~/bevox-knowledge && git tag -a v0.0-bootstrap -m "Bootstrap inicial do bevox-knowledge (E0 - Foundation Freeze). 6 ADRs em estado proposta, aguardando revisao."
```

- [ ] **Step 2: Push da tag**

```bash
cd ~/bevox-knowledge && git push origin v0.0-bootstrap
```

Expected output:
```
To github.com:<ORG>/bevox-knowledge.git
 * [new tag]         v0.0-bootstrap -> v0.0-bootstrap
```

- [ ] **Step 3: Verificar**

```bash
cd ~/bevox-knowledge && git tag -l
```

Expected: `v0.0-bootstrap`

---

## Task 19: Migrar a spec do E0 para `bevox-knowledge/35_specs/`

**Files:**
- Source: `~/.openclaw/docs/superpowers/specs/2026-04-09-foundation-freeze-design.md`
- Destination: `~/bevox-knowledge/35_specs/2026-04-09-e0-foundation-freeze.md`

- [ ] **Step 1: Copiar spec para `35_specs/`**

```bash
cp ~/.openclaw/docs/superpowers/specs/2026-04-09-foundation-freeze-design.md \
   ~/bevox-knowledge/35_specs/2026-04-09-e0-foundation-freeze.md
```

- [ ] **Step 2: Verificar**

```bash
ls -la ~/bevox-knowledge/35_specs/
diff ~/.openclaw/docs/superpowers/specs/2026-04-09-foundation-freeze-design.md \
     ~/bevox-knowledge/35_specs/2026-04-09-e0-foundation-freeze.md
```

Expected: arquivo presente, `diff` retorna sem output (arquivos identicos).

- [ ] **Step 3: Adicionar e commitar**

```bash
cd ~/bevox-knowledge && git add 35_specs/2026-04-09-e0-foundation-freeze.md
git commit -m "$(cat <<'EOF'
docs(specs): migrate E0 foundation freeze spec to canonical location

A partir deste commit, 35_specs/ e o local canonico de specs.
A copia em ~/.openclaw/docs/superpowers/specs/ permanece como rascunho temporario
ate ser arquivada ou apagada em sessao de cleanup futura.

Refs: ADR-005 (knowledge source of truth)
EOF
)"
```

- [ ] **Step 4: Push**

```bash
cd ~/bevox-knowledge && git push
```

Expected:
```
To github.com:<ORG>/bevox-knowledge.git
   <hash>..<hash>  main -> main
```

---

## Task 20: Validacao final e notificacao

**Files:** Nenhum (validacao + notificacao).

- [ ] **Step 1: Verificar todos os arquivos finais**

```bash
find ~/bevox-knowledge -type f ! -path '*/.git/*' | wc -l
```

Expected: `24` (23 do bootstrap + 1 da migracao do spec).

- [ ] **Step 2: Verificar git history limpo**

```bash
cd ~/bevox-knowledge && git log --oneline
```

Expected:
```
<hash> docs(specs): migrate E0 foundation freeze spec to canonical location
<hash> chore: bootstrap bevox-knowledge with E0 foundation
```

- [ ] **Step 3: Verificar tag e remote em sync**

```bash
cd ~/bevox-knowledge
git status
git tag -l
gh repo view ${BEVOX_GITHUB_ORG}/bevox-knowledge --json defaultBranchRef,name
```

Expected:
- `git status` mostra `nothing to commit, working tree clean`
- `git tag -l` mostra `v0.0-bootstrap`
- `gh repo view` retorna JSON com `bevox-knowledge` e `main`

- [ ] **Step 4: Checklist final do DoD**

Marcar cada item conforme verifica:

```
[x] Conta GitHub configurada com gh auth login
[x] Permissao para criar repos privados confirmada
[x] Repo bevox-knowledge criado como privado no GitHub
[x] Clone local em ~/bevox-knowledge/
[x] .gitignore com entradas padrao
[x] README.md raiz com convencoes
[x] decision-log.md criado e populado com as 6 ADRs
[x] 9 pastas top-level (00_inbox a 70_metrics, incluindo 35_specs)
[x] README.md em cada uma das 9 pastas
[x] 20_architecture/agents/README.md
[x] 20_architecture/agents/registry.md (com Vox L4)
[x] 20_architecture/agents/_retired/README.md
[x] 20_architecture/system-map.md
[x] 30_adr/_template.md
[x] ADR-001-company-os-boundary.md (status: proposta)
[x] ADR-002-system-topology.md (status: proposta)
[x] ADR-003-agent-governance.md (status: proposta)
[x] ADR-004-naming-canonical.md (status: proposta)
[x] ADR-005-knowledge-source-of-truth.md (status: proposta)
[x] ADR-006-autonomy-permissions-approval.md (status: proposta)
[x] Primeiro commit feito
[x] Push para o remote bem-sucedido
[x] Tag v0.0-bootstrap aplicada e pushed
[x] Spec migrada para 35_specs/
```

- [ ] **Step 5: Notificar Bernard**

Mensagem proposta (enviar via Telegram ou diretamente, conforme contexto):

```
E0 - Foundation Freeze concluido com sucesso.

Repositorio bevox-knowledge criado e pushado:
github.com/${BEVOX_GITHUB_ORG}/bevox-knowledge

23 arquivos no bootstrap + 1 spec migrado.
6 ADRs em estado "proposta" aguardando sua revisao:

- ADR-001: Company OS Boundary
- ADR-002: System Topology
- ADR-003: Agent Governance
- ADR-004: Naming Canonical
- ADR-005: Knowledge Source of Truth & Context Sync
- ADR-006: Autonomy, Permissions & Approval Policy

Tag aplicada: v0.0-bootstrap

Proximo passo: revisar as ADRs em sequencia (ordem recomendada: 001, 002, 005, 003, 006, 004)
e marcar status para "aceita" (com ou sem edicoes) antes de iniciar o E1.

Quando estiver pronto para a revisao, me chame.
```

---

## Resumo de commits do plano

| # | Commit | Tasks cobertas |
|---|---|---|
| 1 | `chore: bootstrap bevox-knowledge with E0 foundation` | 1-15 |
| 2 | `docs(specs): migrate E0 foundation freeze spec to canonical location` | 19 |

E uma tag: `v0.0-bootstrap` (Task 18).

---

## Estimativas

- **Tasks executaveis pelo agente:** 1-20 (Task 0 e manual)
- **Tempo estimado total:** 30-45 minutos para um agente, dependendo da velocidade de transcricao das ADRs
- **Pontos de checkpoint para revisao humana:**
  - Apos Task 15 (estrutura completa, antes do commit)
  - Apos Task 17 (push feito, antes da tag)
  - Apos Task 19 (spec migrado)

---

## Dependencias externas

- `gh` CLI instalado (`gh --version` deve retornar)
- `git` instalado (vem com qualquer Linux)
- Conta GitHub ativa
- Conexao com internet (para push)

---

## O que NAO esta neste plano (out of scope)

- Aceitacao das ADRs (processo separado, fora do E0)
- Configuracao do Obsidian (E1)
- Sync automatizado entre clone e remote (E1)
- Hooks do OpenClaw apontando para o clone (E1)
- Cleanup do `~/.openclaw/docs/superpowers/specs/` (sessao futura)

---

## Self-review checklist (executor)

Antes de entregar o E0 como concluido:

- [ ] Todos os 23+1 arquivos foram criados (verificado em Task 15 e Task 20 Step 1)
- [ ] Nenhuma ADR contem `XXX` ou texto de placeholder de template (verificado em Task 15 Step 2)
- [ ] Todas as 6 ADRs tem status `proposta` (verificado em Task 15 Step 3)
- [ ] Push para remote bem-sucedido (Task 17)
- [ ] Tag aplicada (Task 18)
- [ ] Spec migrado e segundo commit feito (Task 19)
- [ ] Bernard notificado (Task 20 Step 5)

Se qualquer item falhar, voltar para a task respectiva antes de declarar concluido.
