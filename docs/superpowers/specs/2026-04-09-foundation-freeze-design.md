# E0 - Foundation Freeze Design

> Spec do epico E0 do roadmap OpenClaw Company OS.
> Cria o repositorio `bevox-knowledge` e redige 6 ADRs canonicas com propostas reais para revisao.

**Data:** 2026-04-09
**Epico:** E0 - Foundation Freeze
**Prioridade:** P0
**Dependencias:** Nenhuma
**Roadmap mestre:** `docs/superpowers/roadmaps/2026-04-09-openclaw-company-os-roadmap.md`

---

## 1. Visao Geral

### 1.1 Objetivo

Travar nomenclatura, fronteiras e arquitetura operacional da Bevox antes de comecar qualquer outra implementacao do Company OS. Sem essas decisoes formalizadas, todos os epicos seguintes vao gerar drift e retrabalho.

### 1.2 Deliverables

1. Repositorio `bevox-knowledge` criado e versionado no GitHub privado
2. Estrutura de pastas completa (9 diretorios top-level + subdir `20_architecture/agents/`)
3. README com convencoes de uso
4. Template MADR para ADRs futuras
5. **6 ADRs com propostas redigidas** aguardando revisao do Bernard:
   - ADR-001: Company OS Boundary
   - ADR-002: System Topology
   - ADR-003: Agent Governance
   - ADR-004: Naming Canonical
   - ADR-005: Knowledge Source of Truth & Context Sync
   - ADR-006: Autonomy, Permissions & Approval Policy
6. `system-map.md` inicial alinhado com ADR-002 (4 modulos canonicos)
7. `agents/registry.md` inicial (com Vox L4 ja registrado)
8. `agents/_retired/` (vazio, com README explicando uso)
9. `decision-log.md` como indice das ADRs
10. `35_specs/` reservado como local canonico de specs futuras
11. Spec atual (este arquivo) migrado para `bevox-knowledge/35_specs/2026-04-09-e0-foundation-freeze.md` ao final do E0

### 1.3 Out of scope

- Implementacao de Mission Control (E2)
- Sync automatizado entre OpenClaw e bevox-knowledge (E1)
- Pipeline de snapshots (E1)
- Criacao de novos agentes (E3, E10)
- Integracao com GitHub Actions (E6)
- Aprovacao final das ADRs - elas saem do E0 com status `proposta`. A transicao para `aceita` e um processo separado de revisao com Bernard.

### 1.4 Premissas

- O Bernard tem (ou vai criar) conta GitHub com permissao para criar repos privados
- O `gh CLI` pode ser autenticado no host onde roda o OpenClaw
- O clone local de `bevox-knowledge` mora em `~/bevox-knowledge/`
- ADRs sao a forma canonica de registrar decisoes arquiteturais - notas soltas em `memory/` ou `workspace/` nao substituem ADRs

### 1.5 Pre-requisitos manuais (Bernard)

Antes da implementacao comecar:

1. Decidir entre conta pessoal vs org da Bevox no GitHub
2. Criar a org (se aplicavel)
3. `gh auth login` no terminal
4. Confirmar permissoes para criar repo privado

---

## 2. Estrutura do repositorio

### 2.1 Diretorio raiz

```
bevox-knowledge/
|-- README.md                    # Convencoes e como usar
|-- decision-log.md              # Indice de todas as ADRs
|-- .gitignore                   # Ignora .DS_Store, .obsidian/, etc.
|
|-- 00_inbox/                    # Capturas rapidas, antes de organizar
|   `-- README.md
|
|-- 10_prd/                      # PRDs do produto e do Company OS
|   `-- README.md
|
|-- 20_architecture/             # Arquitetura tecnica e operacional
|   |-- README.md
|   |-- system-map.md            # Mapa de modulos da Bevox (criado no E0)
|   `-- agents/                  # Definicoes formais de agentes
|       |-- README.md            # Como ler/escrever agentes aqui
|       |-- registry.md          # Registry central (tabela ativa)
|       `-- _retired/            # Agentes aposentados (preserva historico)
|           `-- README.md
|
|-- 30_adr/                      # Architecture Decision Records (foco do E0)
|   |-- README.md
|   |-- _template.md             # Template MADR para novas ADRs
|   |-- ADR-001-company-os-boundary.md
|   |-- ADR-002-system-topology.md
|   |-- ADR-003-agent-governance.md
|   |-- ADR-004-naming-canonical.md
|   |-- ADR-005-knowledge-source-of-truth.md
|   `-- ADR-006-autonomy-permissions-approval.md
|
|-- 35_specs/                    # Specs de implementacao (designs detalhados)
|   `-- README.md                # Convencao: YYYY-MM-DD-{epico}-{topico}.md
|
|-- 40_roadmap/                  # Roadmaps estrategicos e tecnicos
|   `-- README.md
|
|-- 50_releases/                 # Notas de release, changelog
|   `-- README.md
|
|-- 60_customer-feedback/        # Feedback de clientes, pesquisas
|   `-- README.md
|
`-- 70_metrics/                  # Metricas de produto e operacao
    `-- README.md
```

### 2.1.1 Local canonico das specs

A partir do E0, todas as specs de implementacao (atuais e futuras) vivem em `bevox-knowledge/35_specs/`. Isso inclui:

- Specs de epicos do roadmap (E0 a E12)
- Specs de features individuais
- Designs tecnicos detalhados

**Convencao de nomenclatura:** `YYYY-MM-DD-{epico-ou-topico}.md`

Exemplo: este proprio spec sera migrado para `bevox-knowledge/35_specs/2026-04-09-e0-foundation-freeze.md` apos o E0 ser implementado.

A pasta `docs/superpowers/specs/` no host atual e local **temporario** ate o `bevox-knowledge` existir. Ela serve como rascunho durante o E0, mas nao e a fonte de verdade canonica.

### 2.2 Por que essa estrutura

**Numeracao com prefixo (`00_`, `10_`, ...)**: ordena alfabeticamente da forma logica - inbox primeiro, metricas por ultimo. Saltos de 10 permitem inserir categorias futuras sem renumerar (ex: `35_specs/`).

**Pastas por proposito, nao por tipo de arquivo**: misturar markdown, json e yaml na mesma pasta e OK se eles servem o mesmo proposito. Quem busca por "decisoes" vai em `30_adr/`, nao precisa lembrar se decisao virou um .md ou .yaml.

**Numero singular nas pastas**: `30_adr` (nao `30_adrs`) - segue convencao de namespaces.

**README.md em cada pasta**: explica o que mora ali e como contribuir. Bootstrapping para humanos e agentes.

### 2.3 Arquivo README.md raiz

Conteudo proposto (sera escrito durante implementacao):

```markdown
# bevox-knowledge

Fonte unica de verdade da Bevox: produto, arquitetura, decisoes, roadmap, releases, feedback e metricas.

## Estrutura

| Pasta | Conteudo |
|---|---|
| `00_inbox/` | Capturas rapidas a serem organizadas |
| `10_prd/` | PRDs (Product Requirements Documents) |
| `20_architecture/` | Arquitetura tecnica e operacional, system-map |
| `30_adr/` | Architecture Decision Records (decisoes formais) |
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
- **Sync:** Manual via git push/pull. Automacao virá no E1.

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
```

### 2.4 Template MADR

Arquivo: `30_adr/_template.md`

```markdown
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
  - Prós: [...]
  - Contras: [...]

- **Opcao B:** [nome curto]
  - Descricao: [...]
  - Prós: [...]
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
```

---

## 3. ADR-001: Company OS Boundary

**Status proposto:** proposta
**Data:** 2026-04-09
**Decisor:** Bernard
**Tags:** boundary, scope, foundation

### 3.1 Contexto e Problema

A Bevox tem dois ambientes operacionais que o Bernard usa em paralelo: o **OpenClaw** (rodando como company OS interno com o agente Vox) e o **Claude Code** (CLI da Anthropic usado para coding). Sem uma fronteira formal, as duas ferramentas comecam a competir pelo mesmo proposito - quem documenta o que? quem executa o que? onde mora qual codigo? - e isso gera drift de contexto, duplicacao de esforco e decisoes operacionais inconsistentes.

A pergunta central: **o que cabe a cada ferramenta?**

### 3.2 Opcoes Consideradas

**Opcao A: Boundary funcional clara (recomendada)**

- **OpenClaw** = Company OS. Cuida de operacao, governanca, agentes, memoria, coordenacao, dashboards internos, automacoes operacionais e comunicacao por canais (Telegram).
- **Claude Code** = Ambiente principal de coding. Usado para escrever/refatorar/debugar codigo do produto Bevox e projetos relacionados.
- **Sobreposicao permitida:** Claude Code pode editar configs do OpenClaw quando o Bernard precisar iterar (ex: editar `openclaw.json`, criar skills). OpenClaw pode invocar Claude Code via skill `coding-agent` para tarefas de coding maiores.
- **Prós:** Fronteira clara baseada em proposito, nao em tipo de arquivo. Permite handoff explicito.
- **Contras:** Requer disciplina para nao usar OpenClaw como editor de codigo improvisado.

**Opcao B: Boundary por tipo de arquivo**

- OpenClaw cuida de tudo em `~/.openclaw/` e `bevox-knowledge/`. Claude Code cuida de tudo em outros repositorios.
- **Prós:** Regra mecanica, dificil de violar.
- **Contras:** Frageis - quando o codigo do produto precisa ser referenciado pelo OpenClaw (ex: agentes lendo PRDs do bevox-knowledge), a regra trava.

**Opcao C: OpenClaw substitui Claude Code completamente**

- OpenClaw vira o ambiente unico de tudo, incluindo coding.
- **Prós:** Uma ferramenta so.
- **Contras:** OpenClaw nao foi feito para coding intensivo. Perderia features especificas do Claude Code (TUI, ferramentas de edicao avancadas, integracao com IDE). Quebra um dos principios do roadmap ("OpenClaw nao e ambiente principal de coding").

### 3.3 Recomendacao

**Opcao A.** A separacao por proposito e a unica que escala. Claude Code e otimizado para edicao de codigo (rapido, focado, com TUI dedicada). OpenClaw e otimizado para orquestracao, memoria persistente, integracao com canais e operacao por agentes. Tentar fundir os dois cria atrito em ambos.

A regra operacional fica:

> **Coding do produto: Claude Code.**
> **Operacao da empresa: OpenClaw.**
> **Knowledge compartilhado: bevox-knowledge.**
> **Handoff entre os dois: explicito, via knowledge repo ou skill `coding-agent`.**

### 3.4 Decisao

(Preenchido apos aprovacao do Bernard)

### 3.5 Consequencias

**Positivas:**
- Cada ferramenta usada para o que faz melhor
- Memoria operacional fica no OpenClaw
- Memoria de codigo fica nos repos do produto + bevox-knowledge
- Sem competicao de propositos

**Negativas:**
- Bernard precisa lembrar qual ferramenta usar para qual tarefa (mitigacao: regra simples)
- Algumas tarefas hibridas (ex: editar config do OpenClaw enquanto trabalha no produto) exigem trocar de contexto

**Neutras:**
- O conceito de "agente" so existe no OpenClaw - Claude Code e ambiente sem agentes persistentes
- Toda automacao de operacao (cron, hooks, watchdogs) mora no OpenClaw

### 3.6 Impacto em Specs Futuras

- **E1 (Knowledge Spine):** define que `bevox-knowledge` e o ponto de encontro entre OpenClaw e Claude Code
- **E2 (Mission Control):** Mission Control e UI do OpenClaw, nao do Claude Code
- **E3 (Agent Registry):** agentes existem so no OpenClaw
- **E6 (GitHub Operations):** integracao GitHub e do OpenClaw, mas Claude Code pode usar `gh CLI` quando esta editando codigo
- **E10 (Functional Agents):** todos os agentes pertencem ao OpenClaw

### 3.7 Notas

- Decisoes relacionadas: ADR-005 (knowledge source of truth)
- Workspace atual ja segue essa intuicao informalmente - veja `~/.openclaw/workspace/AGENTS.md`

---

## 4. ADR-002: System Topology

**Status proposto:** proposta
**Data:** 2026-04-09
**Decisor:** Bernard
**Tags:** topology, modules, foundation

### 4.1 Contexto e Problema

A Bevox tem multiplos modulos de produto e multiplos modulos de operacao, mas atualmente nao existe um mapa canonico que define **quais modulos existem, como se chamam e como se relacionam.** Esse vazio gera nomes inconsistentes (e.g., "console" vs "admin" vs "dashboard"), agentes que nao sabem qual produto referenciar, e PRDs que mencionam modulos sem precisao.

Esta ADR estabelece a topologia inicial e separa **Produto Bevox** (o que vendemos/oferecemos) de **Company OS** (como operamos a empresa).

### 4.2 Sinais ja presentes no contexto

Olhando os artefatos atuais:
- O PRD de security hardening em `media/inbound/` lista as areas: `area:openclaw`, `area:console`, `area:harness`, `area:web`, `area:mobile`
- O `OPERATING_RULES.md` menciona "console/harness" como produtos
- O `AGENTS.md` menciona OpenClaw como company OS, separado do produto

Conclusao: existem 4 modulos canonicos de produto (console, harness, web, mobile) + Company OS (openclaw).

### 4.3 Topologia Proposta

#### Modelo de negocio relevante

A Bevox e uma plataforma de **secretaria IA** para profissionais, clinicas e negocios. Existem dois publicos distintos:

1. **Cliente da Bevox** - profissional/clinica/negocio que contrata. Paga, configura, opera.
2. **Cliente final do cliente** - paciente/lead que conversa com a IA. NAO usa interface propria - acessa via canais conectados (WhatsApp, Instagram, etc.) mediados pelo `bevox-harness`.

#### Produto Bevox

Quatro modulos canonicos, organizados por publico/funcao:

**Camada interna da Bevox (super admin):**

| Modulo | Proposito | Status |
|---|---|---|
| **bevox-console** | Super admin / backoffice interno da Bevox. Painel onde a equipe Bevox gerencia clientes, monitora a operacao do harness, executa acoes internas, acessa logs/metricas. NAO e usado por clientes da Bevox. | Canonizado |

**Camada de runtime do produto:**

| Modulo | Proposito | Status |
|---|---|---|
| **bevox-harness** | Runtime da secretaria IA. Orquestra conversas com clientes finais via canais conectados, gerencia memoria operacional, executa skills, aplica politicas. Motor do produto agent-first. Cliente final NAO acessa via interface propria - acessa via mensageria mediada. | Canonizado |

**Camada do cliente da Bevox (profissional/clinica/negocio):**

| Modulo | Proposito | Status |
|---|---|---|
| **bevox-web** | Aplicacao web do **cliente da Bevox**. Setup da secretaria IA, politicas, gerencia agenda, integracoes, operacao web. NAO e usada pelo cliente final do cliente. | Canonizado |
| **bevox-mobile** | App **operador** do cliente da Bevox para o dia a dia: inbox, handoff humano, agenda do dia, alertas, acoes rapidas. NAO e usada pelo cliente final do cliente. | Canonizado |

#### Quem usa o que

| Publico | Modulo principal | Como acessa |
|---|---|---|
| Equipe Bevox (interno) | bevox-console | Web admin |
| Cliente da Bevox - mesa | bevox-web | Browser |
| Cliente da Bevox - dia a dia | bevox-mobile | App nativo |
| Cliente final (paciente/lead) | bevox-harness (mediado) | WhatsApp, Instagram, outros canais |

> **Nota:** bevox-api **nao** e canonizado agora - se ele existir como modulo separado no futuro, vira ADR propria. Atualmente, comunicacao com canais externos passa pelo bevox-harness.

#### Company OS

| Modulo | Proposito | Status atual |
|---|---|---|
| **openclaw** | Plataforma de agentes auto-hospedada (gateway, sessoes, hooks) | Ativo, v2026.4.8 |
| **vox** | Agente principal (chief of staff digital) | Ativo, level L4 |
| **bevox-knowledge** | Fonte unica de verdade (PRDs, ADRs, roadmaps, etc) | A criar (E0) |
| **mission-control** | UI executiva centralizada para operar a empresa | A criar (E2) |
| **agent-registry** | Cadastro formal de agentes com governanca | A criar (E3) |
| **approval-center** | Sistema de aprovacao de acoes sensiveis | A criar (E4) |

#### Relacoes principais

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
                                    |  bevox-api          |
                                    +---------------------+
```

### 4.4 Opcoes Consideradas

**Opcao A: Topologia formal (recomendada)**

Reconhecer 4-5 modulos de produto + Company OS como entidades nomeadas e versionadas. Cada um tem seu repositorio proprio.

**Opcao B: Monorepo do produto**

Um unico repo `bevox` contendo web, mobile, console, harness, api como subdiretorios.
- **Prós:** Refactors cross-module mais faceis, versionamento atomico
- **Contras:** CI/CD mais complexo, mais lento para builds parciais, nao reflete a realidade de mobile (apple/android tem ciclos proprios)

**Opcao C: So flagar o que ja existe sem criar topologia**

Esperar e documentar conforme as coisas surgem.
- **Contras:** Drift garantido. ADRs e specs precisam de nomes canonicos JA.

### 4.5 Recomendacao

**Opcao A.** A topologia formal e necessaria para que todas as outras specs (E1 a E12) tenham vocabulario consistente. Mesmo que alguns modulos ainda nao existam como repositorios concretos, eles existem como conceitos no roadmap.

Quando o Bernard responder qual e o proposito real de cada modulo, esta ADR vira o mapa oficial.

### 4.6 Decisao

(Preenchido apos revisao)

### 4.7 Consequencias

**Positivas:**
- Vocabulario unico em todo Company OS
- Agentes referenciam modulos por nomes canonicos
- ADRs futuras podem ser categorizadas por area (`area:bevox-web`, `area:openclaw`, etc.)

**Negativas:**
- Renomear modulo no futuro custa propaganda em todos os documentos
- Decisao precisa ser feita com informacao incompleta (alguns modulos ainda nem existem)

### 4.8 Impacto em Specs Futuras

- **E0-F4 (labels GitHub):** as labels `area:*` vem desta topologia
- **E1 (knowledge spine):** o `module-map.md` e a versao detalhada do system-map
- **E5 (Roadmap & Delivery):** items do backlog sao categorizados por area
- **E6 (GitHub Operations):** repos a sincronizar derivam desta topologia
- **E7 (Documentation System):** docs sao organizadas por modulo

### 4.9 Acao requerida do Bernard antes da aceitacao

Preencher/confirmar para cada um dos 4 modulos canonicos:
1. Existe hoje? (sim/nao/em planejamento)
2. O proposito proposto esta correto? Editar se nao.
3. Qual a stack tecnica?
4. Tem repositorio? Se sim, qual a URL?
5. Qual o status atual (alpha/beta/producao/em desenho)?

Se um modulo precisa ser adicionado (ex: bevox-api futuro), abrir ADR substituidora desta.

---

## 5. ADR-005: Knowledge Source of Truth & Context Sync

**Status proposto:** proposta
**Data:** 2026-04-09
**Decisor:** Bernard
**Tags:** knowledge, source-of-truth, sync

### 5.1 Contexto e Problema

Bernard escreve documentos em multiplos lugares: workspace do OpenClaw (`~/.openclaw/workspace/memory/`), conversas com Claude Code (que ficam em historico mas nao em arquivos), media inbound do OpenClaw (`media/inbound/`), e provavelmente Notion/Obsidian/Google Docs em outros contextos. Cada lugar tem sua propria copia do "contexto da Bevox" e nenhum e oficial.

O resultado e drift: uma decisao tomada no Telegram nao chega ao Claude Code; um PRD escrito no Notion nao e visivel ao Vox; uma licao aprendida via Claude Code nao volta para o `memory/lessons.md`.

Esta ADR estabelece **uma unica fonte de verdade** e define como todos os ambientes se sincronizam com ela.

### 5.2 Opcoes Consideradas

**Opcao A: bevox-knowledge como SoT, git como mecanismo de sync (recomendada)**

- `bevox-knowledge` (repo git no GitHub) e a unica fonte de verdade
- Clone local em `~/bevox-knowledge/`
- OpenClaw le via filesystem do clone local
- Claude Code le via filesystem (mesmo clone)
- Sync entre local e remote: `git push` / `git pull` manual (E0); automatizar em E1
- Conflitos: resolvidos por git merge tradicional
- Workspace do OpenClaw (`~/.openclaw/workspace/memory/`) continua existindo, mas como **memoria operacional** (sessoes diarias, recall, feedback) - NAO como fonte de verdade arquitetural

**Opcao B: Notion como SoT**

- Tudo vive no Notion, OpenClaw e Claude Code consomem via API
- **Prós:** UI rica, colaboracao multi-usuario nativa
- **Contras:** Vendor lock-in, dependencia de internet, API com rate limits, dificil versionar arquitetura como codigo, nao funciona offline, nao se beneficia de ferramentas git

**Opcao C: Workspace do OpenClaw como SoT**

- Manter tudo em `~/.openclaw/workspace/`
- **Prós:** Ja existe, nada para configurar
- **Contras:** Nao e versionado em git (atualmente), Claude Code teria que navegar dentro do diretorio do OpenClaw, mistura memoria operacional com decisoes permanentes

**Opcao D: Multi-source com sync inteligente**

- Cada ambiente (Notion, OpenClaw workspace, repos) e canonico para um tipo de coisa, com sync entre eles.
- **Contras:** Complexidade enorme, conflitos frequentes, regras dificeis de manter

### 5.3 Recomendacao

**Opcao A.** Git e a tecnologia certa para versionar conhecimento textual. Bevox-knowledge como repo dedicado:
- E neutro (nao pertence ao OpenClaw nem ao Claude Code)
- E versionado (historico completo, blame, branches)
- E offline-first (clone local funciona sem internet)
- E portavel (qualquer ferramenta abre markdown)
- E auditavel (cada commit e uma decisao registrada)

A separacao entre "fonte de verdade" (bevox-knowledge) e "memoria operacional" (workspace do OpenClaw) e crucial:
- **bevox-knowledge** = decisoes permanentes, arquitetura, PRDs, roadmaps, ADRs
- **OpenClaw workspace memory** = sessoes diarias, recall de curto prazo, feedback loops, contexto efemero

Se uma informacao precisa sobreviver multiplas sessoes e ser referenciada por agentes diferentes, ela vai para `bevox-knowledge`. Se e contexto temporario de uma conversa, fica na memory do workspace.

### 5.4 Decisao

(Preenchido apos revisao)

### 5.5 Politica de Leitura/Escrita

| Quem | Le | Escreve | Como |
|---|---|---|---|
| **Bernard** | Tudo | Tudo | Editor preferido (VSCode, Vim, Obsidian) |
| **Vox** | Tudo | Sob aprovacao | OpenClaw filesystem tools + commit explicito |
| **Claude Code** | Tudo | Sob solicitacao | Edicao direta + commit local; push manual |
| **Outros agentes** | Tudo | Sob aprovacao com escopo limitado | Definido em ADR-006 |

**Regra de commit:**
- Bernard pode commitar livremente
- Vox/Claude Code propoem commit; Bernard aprova
- Mensagens de commit em portugues, formato `tipo: descricao curta` (ex: `adr: aceita ADR-001 boundary`)
- Push para o remote so apos commit aprovado

**Regra de branch:**
- `main` para conteudo aceito
- `draft/*` para propostas em revisao
- ADRs novas comecam em branch `draft/adr-XXX-titulo`, viram PR, sao aceitas via merge

### 5.6 Sync entre ambientes

**Fase atual (E0):** Manual.

```bash
# No diretorio do clone
cd ~/bevox-knowledge

# Atualizar
git pull

# Apos editar
git add .
git commit -m "tipo: descricao"
git push
```

**Fase E1 (Knowledge Spine):** Automatizar com:
- Hook do OpenClaw que faz `git pull` periodicamente
- Hook do OpenClaw que detecta mudancas no clone e oferece commit
- Notificacao quando ha conflito

**Fase futura:** Watchdog que mantem clones de Bernard, Vox e Claude Code sincronizados em tempo real.

### 5.7 Consequencias

**Positivas:**
- Drift de informacao acabou
- Toda decisao tem historico versionado
- Trabalha offline
- Backup natural via GitHub
- Markdown puro = sem lock-in

**Negativas:**
- Bernard precisa aprender git (se ainda nao sabe)
- Conflitos de merge sao possiveis quando varias edicoes acontecem em paralelo (mitigacao: workflow por branches)
- Nao tem UI de busca rica como Notion (mitigacao: grep + Vox indexando)

### 5.8 Impacto em Specs Futuras

- **E1 (Knowledge Spine):** spec define mecanismos de sync automatizado
- **E2 (Mission Control):** dashboard tem widget mostrando ultimo commit do bevox-knowledge
- **E3 (Agent Registry):** registry vive em `bevox-knowledge/30_adr/` ou `20_architecture/`
- **E5 (Roadmap & Delivery):** roadmaps e specs vivem em `40_roadmap/`
- **E7 (Documentation System):** documentation pipeline gera arquivos em `bevox-knowledge/`
- **E11 (Finance OS):** dados financeiros NAO vao em bevox-knowledge (privados); ficam em ledger separado

### 5.9 Notas

- ADR relacionada: ADR-001 (boundary OpenClaw vs Claude Code)
- A memoria do workspace do OpenClaw (`workspace/memory/`) continua existindo e sera reorganizada em ADR-006

---

## 6. ADR-003: Agent Governance

**Status proposto:** proposta
**Data:** 2026-04-09
**Decisor:** Bernard
**Tags:** agents, governance, leveling

### 6.1 Contexto e Problema

Hoje a Bevox tem um unico agente formalizado (Vox, L4) e um documento informal de leveling em `~/.openclaw/workspace/shared/TEAM.md`. O roadmap planeja 9+ agentes especializados (Product, Delivery, GitHub Admin, etc.). Sem regras formais sobre **como criar, promover, operar e aposentar agentes**, a expansao vai gerar inconsistencia, agentes orfaos e zero accountability.

Esta ADR formaliza o ciclo de vida e a politica de governanca dos agentes do Company OS.

### 6.2 Estado atual a aproveitar

`workspace/shared/TEAM.md` ja define:
- 4 niveis (L1-L4)
- Premissa "novos agentes comecam em L1"
- Regra de modelo por tipo de trabalho
- Lista preliminar de agentes futuros

ADR-003 pega isso, formaliza, e adiciona o que falta: criterios objetivos, processo de promocao, papel do owner, retiro de agentes.

### 6.3 Modelo de Leveling

Mantem L1-L4 como ja existe:

| Level | Nome | Autonomia | Operacao | Caracteristicas |
|---|---|---|---|---|
| **L1** | Observer | Zero | Cada acao revisada por Bernard antes de executar | Novo agente. Esta em "shadow mode" - so sugere |
| **L2** | Contributor | Baixa | Pode executar acoes na lista branca, fora dela so sugere | Provou que entende o contexto |
| **L3** | Operator | Media | Executa autonomamente dentro de guidelines, pede aprovacao para excecoes | Ja tem track record de entregas confiaveis |
| **L4** | Trusted | Alta | Autonomia ampla, aprovacao so para acoes irreversiveis ou externas | Hub-level. Atualmente so o Vox |

**Regra fundamental:** todo novo agente comeca em L1. Nao ha excecao.

### 6.4 Ciclo de vida de um agente

**Fase 1: Concepcao**
- Bernard ou outro agente identifica a necessidade
- Resposta a 3 perguntas:
  1. Existe volume recorrente que justifique um agente especifico?
  2. O contexto e suficientemente especializado para nao caber no Vox?
  3. Quais sao os 3-5 outputs mensuraveis que esse agente vai produzir?
- Se sim para todas: prossegue. Se nao: nao cria agente; vira skill ou cron.

**Fase 2: Definicao (template obrigatorio)**

Cada agente e definido por um arquivo em `bevox-knowledge/20_architecture/agents/[agent-name].md`:

```markdown
# Agent: [name]

- **Owner:** Bernard (ou nome de outro humano quando houver equipe)
- **Status:** ativo | suspenso | aposentado
- **Level:** L1 (sempre comeca aqui)
- **Modelo padrao:** [provider/model]
- **Modelo fallback:** [provider/model]
- **Criado em:** YYYY-MM-DD

## Missao

Uma frase. O que esse agente existe para fazer.

## Inputs

- O que o agente recebe (canais, comandos, eventos)

## Outputs

- O que o agente entrega (artefatos, mensagens, mudancas no sistema)

## Skills

- Lista de skills habilitadas

## Limites

- O que esse agente NUNCA faz
- Acoes fora do escopo
- Quando escalar para Bernard

## Approvals

- Politica de approvals (referencia ADR-006)

## KPIs

- Como medimos se esse agente e util
- Frequencia de revisao

## Playbook operacional

- Como o agente opera no dia a dia
- Heartbeats, crons, gatilhos

## Historico de levels

- L1 desde YYYY-MM-DD
- (depois) L2 desde YYYY-MM-DD com aprovacao de [decisor]
```

**Fase 3: Operacao em L1**
- Agente roda por minimo 7 dias
- Toda acao passa por aprovacao
- Bernard avalia: o agente faz o que diz que faz? Os outputs sao uteis? Tem proposta de valor real?

**Fase 4: Promocao**

Criterios para subir de level:

| De → Para | Tempo minimo | Criterios |
|---|---|---|
| L1 → L2 | 7 dias | 90% das acoes propostas foram aceitas; zero acoes inseguras |
| L2 → L3 | 14 dias adicionais | 95% das acoes na allowlist executadas sem incidente; zero outputs incorretos materiais |
| L3 → L4 | 30 dias adicionais | Track record consistente; necessidade real de autonomia ampla; aprovacao explicita do Bernard |

**Promocao NAO gera ADR nova.** Promocoes e aposentadorias sao mudancas operacionais, nao decisoes arquiteturais. O registro acontece em tres lugares:

1. **Arquivo do agente** (`bevox-knowledge/20_architecture/agents/[name].md`):
   - Atualizar campo `Level:`
   - Adicionar entrada em "Historico de levels"
2. **Registry** (`bevox-knowledge/20_architecture/agents/registry.md`):
   - Atualizar coluna `Level` na tabela
3. **Historico operacional** (`bevox-knowledge/20_architecture/agents/[name].md`, secao "Historico de levels"):
   - Linha com data, level anterior, novo level, decisor, motivo

Commit messages padronizados: `agent({name}): promote L{X} -> L{Y}` ou `agent({name}): retire`. Esses commits ja sao trilha auditavel suficiente - nao precisam virar ADR.

ADRs continuam sendo o lugar para mudancas **estruturais** na governanca em si (ex: alterar criterios de promocao, adicionar level L5, etc.) - nao para aplicacao da governanca a agentes individuais.

**Fase 5: Manutencao**
- Heartbeat semanal: agente reporta o que fez
- Review mensal: Bernard avalia continuidade
- KPIs sao re-avaliados trimestralmente

**Fase 6: Aposentadoria**

Um agente e aposentado quando:
- Os outputs nao sao mais usados
- Foi substituido por outro agente ou skill
- O custo nao justifica o beneficio
- Tem comportamento erratico que nao e corrigivel

Aposentar (operacao, NAO gera ADR):
1. Atualizar status do agente para `aposentado` no proprio arquivo
2. Mover arquivo para `bevox-knowledge/20_architecture/agents/_retired/`
3. Remover linha do registry (`registry.md`)
4. Registrar motivo + data no arquivo do agente, secao "Historico"
5. Commit: `agent({name}): retire (motivo: {curto})`

O `_retired/` preserva o historico - agentes nunca sao apagados, so movidos para o cemiterio.

### 6.5 Owner

Todo agente tem um **owner humano** responsavel por:
- Definir e ajustar a missao
- Aprovar promocoes
- Decidir aposentadoria
- Assinar mudancas significativas no comportamento

Hoje o owner de todos os agentes e Bernard. No futuro, agentes podem ter owners diferentes (ex: Content Agent owned por alguem da equipe de marketing).

### 6.6 Registry central

Local: `bevox-knowledge/20_architecture/agents/registry.md`

Formato proposto: tabela markdown manual (simples) ou YAML (estruturado). Recomendacao: comecar com tabela markdown e migrar para YAML so quando o numero de agentes justificar.

```markdown
| Agente | Status | Level | Owner | Modelo | Desde |
|---|---|---|---|---|---|
| vox | ativo | L4 | Bernard | openai-codex/gpt-5.4 | 2026-04-08 |
```

### 6.7 Decisao

(Preenchido apos revisao)

### 6.8 Consequencias

**Positivas:**
- Cada agente tem accountability clara
- Promocoes sao decisoes registradas, nao "aconteceu"
- Aposentadoria e processo, nao abandono
- Volume controlado: cria agente so quando justifica

**Negativas:**
- Mais burocracia para criar agentes
- Tempo minimo de 7 dias em L1 atrasa value de novos agentes (mitigacao: necessario para confianca)

### 6.9 Impacto em Specs Futuras

- **E3 (Agent Registry):** implementa o registry conforme essa ADR
- **E4 (Approval Center):** approvals respeitam o level do agente
- **E10 (Functional Agents Pack):** cada agente do pack segue esse template

---

## 7. ADR-006: Autonomy, Permissions & Approval Policy

**Status proposto:** proposta
**Data:** 2026-04-09
**Decisor:** Bernard
**Tags:** autonomy, permissions, approvals, security

### 7.1 Contexto e Problema

O OpenClaw atualmente esta configurado com `security: full` e `ask: off` no `exec-approvals.json`, ou seja, o Vox tem autonomia total no shell do host. Isso e necessario para ele ser util como operador, mas nao se traduz em politica formal: nao ha matriz documentando o que cada agente pode fazer, em que contexto, e o que precisa de aprovacao.

Quando novos agentes forem criados, essa ausencia de politica formal vai ser perigosa - um novo agente em L1 nao pode herdar a autonomia do Vox.

Esta ADR formaliza a **matriz de autonomia, permissoes e approvals** do Company OS.

### 7.2 Princípios

1. **Autonomia segue level.** L1 nao tem; L4 tem amplo.
2. **Acoes externas exigem aprovacao mais alta que acoes internas.**
3. **Acoes irreversiveis exigem aprovacao mais alta que reversiveis.**
4. **Aprovacao tem trilha auditavel.** Toda aprovacao gera log com timestamp, requisitor, decisor, motivo.
5. **Bernard pode sobrescrever qualquer politica em runtime** (override explicito).
6. **Hard limits sao absolutos.** Algumas acoes nunca sao automatizadas, nem em L4.

### 7.3 Categorias de Acao

| Categoria | Exemplos | Reversibilidade |
|---|---|---|
| **read-internal** | Ler arquivos do workspace, queries em memory | Total (so leitura) |
| **write-internal** | Editar arquivos do workspace, atualizar memory, criar notas | Alta (versionado em git) |
| **write-knowledge-draft** | Criar/editar arquivos em `bevox-knowledge/00_inbox/`, drafts em branch `draft/*`, anotacoes nao-canonicas | Alta (git, branch separada, nao toca main) |
| **write-knowledge-canonical** | Commit em `main` de `bevox-knowledge` afetando ADRs aceitas, PRDs oficiais, system-map, policies, registry de agentes | Media (git history, mas ja e publico interno) |
| **read-external** | API calls de leitura (GitHub read, fetch web) | Total |
| **write-external-soft** | Comentar em issue, criar branch, abrir PR draft | Media (revertivel) |
| **write-external-hard** | Merge PR, deploy, push para main, enviar email | Baixa (impacto externo) |
| **publish** | Postar em redes sociais, publicar release notes externas | Baixa (publico) |
| **financial** | Operacoes que envolvem dinheiro (APIs pagas alem do orcado, compras) | Variavel |
| **infra-critical** | Modificar configs do gateway, criar/destruir devices, mudar scopes | Baixa (pode quebrar sistema) |
| **destructive** | Deletar arquivos, dropar dados, force push | Zero (irreversivel) |
| **comms-direct** | Mensagens diretas a usuarios externos (Telegram, email) | Baixa (visivel ao recipiente) |

**Distincao critica:**

- **write-knowledge-draft** = pensamento em voz alta. Vox/agentes podem rascunhar, anotar, propor sem pedir aprovacao. Vive em `00_inbox/` ou em branches `draft/*`.
- **write-knowledge-canonical** = decisao formalizada. Mexer em ADR aceita, PRD oficial, system-map, registry de agentes, policies. Aprovacao do owner humano e obrigatoria.

A regra simples: **se afeta `main` em arquivo canonico, e canonico**. Se vive em inbox, draft ou rascunho, e draft.

### 7.4 Matriz de Autonomia por Level

| Categoria | L1 Observer | L2 Contributor | L3 Operator | L4 Trusted |
|---|---|---|---|---|
| read-internal | auto | auto | auto | auto |
| write-internal | propose | auto (allowlist) | auto | auto |
| write-knowledge-draft | propose | auto | auto | auto + push branch |
| write-knowledge-canonical | propose | propose | propose | approve |
| read-external | propose | auto (whitelist) | auto | auto |
| write-external-soft | propose | propose | auto (allowlist) | auto |
| write-external-hard | propose | propose | propose | approve |
| publish | propose | propose | propose | approve |
| financial | NEVER | NEVER | propose | approve |
| infra-critical | NEVER | propose | propose | approve |
| destructive | NEVER | NEVER | NEVER | approve |
| comms-direct | propose | propose | approve | approve |

**Legenda:**
- `auto` = executa sem interacao
- `propose` = sugere, espera aprovacao do Bernard
- `approve` = executa apenas apos aprovacao explicita (mesmo em L4)
- `NEVER` = bloqueado, sem possibilidade de aprovacao em runtime
- `allowlist` = limitado a uma lista pre-aprovada
- `own area` = limitado ao escopo do proprio agente

### 7.5 Hard Limits (nunca automaticos, em nenhum level)

Acoes que **NUNCA** podem ser executadas sem aprovacao humana explicita, mesmo no L4:

1. **Apagar dados que nao sao reversiveis** (ex: `rm -rf` fora de areas temp; `git push --force` em branches compartilhadas)
2. **Compras/pagamentos automatizados** alem de servicos pre-autorizados (OpenAI subscription, OpenRouter)
3. **Envio de emails/mensagens em nome do Bernard** sem revisao do conteudo
4. **Publicar conteudo externo** (blog, redes sociais, releases publicas)
5. **Modificar credenciais de seguranca** (rotacao automatica e OK; mudanca manual exige aprovacao)
6. **Criar/destruir devices ou parear novos hosts**
7. **Conceder novos scopes a devices existentes**
8. **Push para `main` de qualquer repositorio do produto** (so via PR aprovada)
9. **Deploy para producao** (sempre via humano)
10. **Acessar dados pessoais do Bernard fora do escopo de trabalho** (familia, financeiro pessoal)

### 7.6 Approval Center (visao alto-nivel)

Toda acao categoria `propose` ou `approve` gera uma entrada em fila de aprovacao com:

```yaml
approval_id: uuid
created_at: timestamp
agent: vox
agent_level: L4
action_category: write-external-hard
action_description: "Merge PR #42 em bevox-web"
context: "PR aprovado em review, CI passou, autor confirmou estar pronto"
risk_assessment: "Baixo - mudanca em area de testes"
proposed_command: "gh pr merge 42 --squash"
status: pending | approved | rejected
decided_by: Bernard
decided_at: timestamp
decision_reason: "OK, executar"
```

A UI completa do Approval Center vem em E4. Por enquanto (E0+E1), aprovacoes vao por mensagem no Telegram com botoes inline.

### 7.7 Override do Bernard

Bernard pode em qualquer momento:
- Aprovar uma acao bloqueada por hard limit (com confirmacao dupla)
- Bloquear permanentemente uma categoria para um agente especifico
- Suspender um agente (status: suspenso)
- Modificar a matriz desta ADR (gera uma ADR substituidora)

### 7.8 Implementacao no OpenClaw

A configuracao atual de `~/.openclaw/exec-approvals.json` (`security: full, ask: off, autoAllowSkills: true`) corresponde implicitamente ao perfil **L4 Trusted**. Vai ser mantida para o Vox.

Quando novos agentes forem criados (E3), cada um tera entrada propria em `exec-approvals.json` com configuracao apropriada ao seu level:

```json
{
  "agents": {
    "main": {
      "security": "full",
      "ask": "off",
      "autoAllowSkills": true
    },
    "product-agent": {
      "security": "allowlist",
      "ask": "on-miss",
      "autoAllowSkills": false
    },
    "github-admin-agent": {
      "security": "allowlist",
      "ask": "always",
      "autoAllowSkills": false
    }
  }
}
```

### 7.9 Decisao

(Preenchido apos revisao)

### 7.10 Consequencias

**Positivas:**
- Politica clara e auditavel
- Novos agentes podem ser criados com seguranca
- Bernard pode delegar sem medo
- Trilha de aprovacao para incidentes

**Negativas:**
- Mais friction para acoes externas (mitigacao: necessario para seguranca)
- Bernard fica como bottleneck para approves (mitigacao: aprovar em batch quando possivel; aceitar L4 em agentes maduros)
- Manter a matriz atualizada exige disciplina

### 7.11 Impacto em Specs Futuras

- **E3 (Agent Registry):** registry inclui o level e a politica de approval
- **E4 (Approval Center):** implementa fila de aprovacoes e UI
- **E6 (GitHub Operations):** GitHub Agent respeita matriz para PRs/merges
- **E10 (Functional Agents Pack):** cada agente do pack vem com level inicial L1 e matriz aplicada
- **E12 (Content & Distribution OS):** publicacao externa e categoria `publish` - sempre approve

### 7.12 Notas

- Estado atual ja segue informalmente a categoria L4 para o Vox
- ADR relacionada: ADR-003 (governanca, levels)
- Fonte: `~/.openclaw/workspace/AGENTS.md` (autonomia vs confirmacao) + `OPERATING_RULES.md` (10 regras)

---

## 8. ADR-004: Naming Canonical

**Status proposto:** proposta
**Data:** 2026-04-09
**Decisor:** Bernard
**Tags:** naming, conventions, foundation

### 8.1 Contexto e Problema

Sem convencao formal, mesmo Bernard sozinho gera nomes inconsistentes em poucas semanas: `bevox-knowledge`, `bevoxKnowledge`, `Bevox_Knowledge`, `bevox.knowledge`. Quando agentes especializados existirem, o problema explode - cada um vai gerar nomes no estilo que aprendeu.

Esta ADR define convencao unica para tudo que e nomeado dentro do Company OS da Bevox.

### 8.2 Convencoes Propostas

#### 8.2.1 Repositorios

- **Padrao:** `bevox-{purpose}` em kebab-case
- **Exemplos:** `bevox-knowledge`, `bevox-web`, `bevox-mobile`, `bevox-console`, `bevox-harness`, `bevox-api`
- **Excecoes:** `openclaw` (e ferramenta upstream, nao pertence a Bevox)

#### 8.2.2 Branches

- **Padrao:** `tipo/escopo-descricao-curta`
- **Tipos validos:** `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `infra`, `adr`
- **Exemplos:**
  - `feat/agents-product-create`
  - `fix/openclaw-telegram-allowlist`
  - `adr/001-company-os-boundary`
  - `docs/system-map-update`

#### 8.2.3 Arquivos

- **Markdown geral:** kebab-case (`system-map.md`, `module-overview.md`)
- **ADRs:** `ADR-XXX-titulo-curto.md` (3 digitos + kebab-case)
- **Documentos com data:** `YYYY-MM-DD-topico-tipo.md` (ex: `2026-04-09-foundation-freeze-design.md`)
- **Configs JSON:** kebab-case (`agent-registry.json`)
- **Config TOML/YAML:** kebab-case (`mission-control.yaml`)

#### 8.2.4 Diretorios

- **Padrao:** kebab-case
- **Excecao:** prefixo numerico para ordenacao (`00_inbox/`, `30_adr/`)
- **Excecao 2:** diretorios de ferramentas com convencoes proprias (`.git/`, `.openclaw/`, `node_modules/`)

#### 8.2.5 Agentes

- **Padrao geral:** substantivo curto, kebab-case (`vox`, `product`, `delivery`)
- **Quando precisar de qualificador:** `{escopo}-agent` (`github-admin`, `agent-creator`)
- **Arquivo de definicao:** `agents/[name].md`
- **Identificador interno (no codigo):** snake_case (`product_agent`)

#### 8.2.6 Skills

- **Padrao:** lowercase, kebab-case quando composto (`weather`, `github`, `healthcheck`, `node-connect`)
- **Sem prefixo de namespace nos arquivos do user**

#### 8.2.7 Modulos do Produto

- **Padrao:** `bevox-{nome}` (alinha com nome de repo)
- **Como referencia em texto:** "Bevox Web", "Bevox Mobile" (com inicial maiuscula)
- **Como label do GitHub:** `area:bevox-web`

#### 8.2.8 Variaveis e Codigo

- **JavaScript/TypeScript:** camelCase para variaveis, PascalCase para tipos/classes
- **Python:** snake_case
- **Shell scripts:** snake_case
- **JSON keys:** camelCase (compatibilidade com OpenClaw e maioria das APIs)
- **YAML keys:** kebab-case OU camelCase, consistente dentro do arquivo
- **Env vars:** UPPER_SNAKE_CASE (`OPENROUTER_API_KEY`)

#### 8.2.9 IDs e UUIDs

- **UUIDs:** lowercase com hifens (formato padrao)
- **IDs custom:** kebab-case com prefixo de tipo (`agent-vox`, `adr-001`, `epic-e0`)

#### 8.2.10 Ambientes

- **Padrao:** `dev`, `staging`, `prod`
- **Por enquanto:** apenas `dev` e `prod`. Adicionar `staging` quando o produto Bevox estiver em fase de pre-release publico.

#### 8.2.11 Idioma

- **Documentos da Bevox:** Portugues brasileiro
- **Codigo:** Ingles (variaveis, comentarios em codigo, commit messages)
- **Commit messages:** Portugues OU ingles, consistente dentro de cada repo. Recomendacao: portugues em `bevox-knowledge`, ingles nos repos de codigo (web, mobile, etc.)
- **ADRs:** Portugues (publico-alvo e o time interno da Bevox)

### 8.3 Decisao

(Preenchido apos revisao)

### 8.4 Consequencias

**Positivas:**
- Drift eliminado
- Agentes geram nomes consistentes
- Buscas funcionam (grep simples encontra)
- Onboarding de novos colaboradores e mais rapido

**Negativas:**
- Renomear coisas existentes que ja violam a convencao (mitigacao: aplicar gradualmente; nao quebrar URLs publicas)
- Sempre vai ter uma excecao questionavel

### 8.5 Impacto em Specs Futuras

- **Todas as specs** seguem essa convencao de nomenclatura para arquivos, repos, branches
- **E0 mesmo** ja segue: este spec e `2026-04-09-foundation-freeze-design.md`
- **E6 (GitHub Operations):** labels seguem `area:bevox-*`, `type:*`, `priority:p*`
- **E3 (Agent Registry):** nomes de agentes seguem essa convencao

### 8.6 Notas

- Decisao deliberadamente conservadora: kebab-case e a opcao mais legivel e amigavel para terminais/URLs
- Quando houver conflito entre conveniencia e consistencia, escolher consistencia

---

## 9. system-map.md inicial

**Localizacao:** `bevox-knowledge/20_architecture/system-map.md`

**Conteudo proposto** (a ser ajustado quando ADR-002 for aceita):

```markdown
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
| Bevox API | `bevox-api` | TBD | TBD | Bernard |

> Os campos TBD serao preenchidos quando ADR-002 for aceita com o input do Bernard.

## Company OS

| Modulo | Localizacao | Status | Owner |
|---|---|---|---|
| OpenClaw | `~/.openclaw/` (host local) | Ativo (v2026.4.8) | Bernard |
| Vox | Agente principal do OpenClaw | Ativo (L4) | Bernard |
| bevox-knowledge | `github.com/[org]/bevox-knowledge` | A criar (E0) | Bernard |
| Mission Control | TBD (E2) | A criar | Bernard |
| Agent Registry | `bevox-knowledge/20_architecture/agents/` | A criar (E3) | Bernard |
| Approval Center | TBD (E4) | A criar | Bernard |

## Diagrama de Fluxo

[Inserir diagrama ASCII similar ao do ADR-002]

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
```

---

## 10. decision-log.md

**Localizacao:** `bevox-knowledge/decision-log.md`

**Conteudo proposto:**

```markdown
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
```

---

## 11. Workflow de Aprovacao das ADRs

### 11.1 Como Bernard revisa

Apos o E0 ser implementado (todos os arquivos criados e commitados), Bernard executa este workflow:

1. **Ler todas as 6 ADRs** em sequencia recomendada: 001, 002, 005, 003, 006, 004
2. **Para cada uma:**
   - Marcar inline o que aceita como esta
   - Marcar o que quer alterar (com nota explicando)
   - Marcar o que rejeita
3. **Sentar com Vox** para revisar pontos questionados
4. **Atualizar status:**
   - `proposta` → `aceita` (sem mudancas)
   - `proposta` → `aceita` apos edicoes
   - `proposta` → `descartada` (raro, requer ADR alternativa)

### 11.2 Modelo de revisao por ADR

Para cada ADR, Bernard responde 4 perguntas:

1. **A descricao do problema esta correta?**
2. **As opcoes consideradas sao suficientes?**
3. **A recomendacao faz sentido?**
4. **Algum impacto nas specs futuras precisa de ajuste?**

### 11.3 Quando todas estiverem aceitas

- Mover arquivos para status `aceita`
- Atualizar `decision-log.md`
- Tag git: `v0.1-foundation-freeze`
- Iniciar brainstorming do E1 (Knowledge Spine completo) usando as ADRs como base

---

## 12. Definition of Done do E0

### Pre-requisitos
- [ ] Conta GitHub (pessoal ou org Bevox) configurada com `gh auth login`
- [ ] Permissao para criar repos privados confirmada

### Repo e estrutura
- [ ] Repo `bevox-knowledge` criado como privado no GitHub
- [ ] Clone local em `~/bevox-knowledge/`
- [ ] `.gitignore` com entradas padrao (`.DS_Store`, `.obsidian/`, `*.swp`, etc.)
- [ ] `README.md` raiz com convencoes
- [ ] `decision-log.md` criado e populado com as 6 ADRs

### Pastas top-level (9 pastas, todas com README.md)
- [ ] `00_inbox/`
- [ ] `10_prd/`
- [ ] `20_architecture/`
- [ ] `30_adr/`
- [ ] `35_specs/`
- [ ] `40_roadmap/`
- [ ] `50_releases/`
- [ ] `60_customer-feedback/`
- [ ] `70_metrics/`

### Subpastas de agentes
- [ ] `20_architecture/agents/README.md`
- [ ] `20_architecture/agents/registry.md` (tabela com Vox L4)
- [ ] `20_architecture/agents/_retired/README.md`

### system-map
- [ ] `20_architecture/system-map.md` criado com a topologia proposta (4 modulos canonicos + Company OS)

### ADRs (todas como `proposta`)
- [ ] `30_adr/_template.md` (template MADR)
- [ ] `30_adr/ADR-001-company-os-boundary.md`
- [ ] `30_adr/ADR-002-system-topology.md`
- [ ] `30_adr/ADR-003-agent-governance.md`
- [ ] `30_adr/ADR-004-naming-canonical.md`
- [ ] `30_adr/ADR-005-knowledge-source-of-truth.md`
- [ ] `30_adr/ADR-006-autonomy-permissions-approval.md`

### Git
- [ ] Primeiro commit feito: `chore: bootstrap bevox-knowledge with E0 foundation`
- [ ] Push para o remote bem-sucedido
- [ ] Tag `v0.0-bootstrap` aplicada (marca o estado pre-revisao)

### Notificacao
- [ ] Bernard notificado para iniciar revisao das ADRs

**Out of scope para o E0 (vai para E1 ou depois):**
- Aceitacao final das ADRs (processo separado, fora do E0)
- Sync automatizado entre clone local e remote
- Hooks do OpenClaw para detectar mudancas
- Index/search no bevox-knowledge
- Configuracao do Obsidian como editor (E1)
- Migracao do spec atual (`docs/superpowers/specs/2026-04-09-foundation-freeze-design.md`) para `bevox-knowledge/35_specs/` (faz parte da execucao do E0, ultima task)

---

## 13. Riscos

| Risco | Impacto | Mitigacao |
|---|---|---|
| Bernard nao tem GitHub configurado | Bloqueia E0 inteiro | Task 0 do plano e configurar GitHub |
| Bernard discorda das propostas das ADRs | Atraso na aceitacao, retrabalho de redacao | Propostas claras sao mais faceis de discordar de pontualmente do que templates vazios; cada secao da ADR pode ser editada isoladamente |
| Modulos do produto Bevox sao diferentes do que assumi | ADR-002 precisa ser reescrita | Marquei explicitamente "a confirmar" nos campos onde nao tenho contexto; Bernard preenche na revisao |
| O repo `bevox-knowledge` cresce rapido demais e perde estrutura | Drift que essa ADR mesma busca evitar | Convencoes em ADR-004 + revisao trimestral da estrutura |
| Conflito git entre Bernard e Vox em commits paralelos | Frustracao operacional | E1 vai automatizar; por enquanto regra simples: Bernard commita, Vox propoe via mensagem |

---

## 14. Out of Scope (explicito)

Estas coisas **NAO** fazem parte do E0 e devem ser ignoradas durante a implementacao:

- Mission Control UI (E2)
- Agent Registry como sistema executavel (E3)
- Approval Center funcional (E4)
- Sync automatizado bevox-knowledge ↔ OpenClaw (E1)
- Implementacao dos agentes do pacote funcional (E10)
- Migracao de conteudo existente do `~/.openclaw/workspace/memory/` para `bevox-knowledge` (decidir em E1)
- Setup de Obsidian como editor (decidir em E1)
- Pipeline de backups (E8)
- Cost tracking (E9)

---

## 15. Proximos passos apos o E0

1. **Bernard revisa as 6 ADRs** (processo separado, fora do E0)
2. **ADRs sao aceitas** (status muda para `aceita`, commit, tag `v0.1-foundation-freeze`)
3. **Iniciar brainstorming do E1** (Knowledge Spine completo) usando as decisoes aceitas como base
4. **Em paralelo, iniciar brainstorming do E2** (Mission Control Shell) ja que so depende do E0

---

*Spec do E0 - Foundation Freeze. Gerado em 2026-04-09 com base no roadmap em `docs/superpowers/roadmaps/2026-04-09-openclaw-company-os-roadmap.md`.*
