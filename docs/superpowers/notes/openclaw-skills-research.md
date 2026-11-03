# OpenClaw Skills - Research

Pesquisa feita em 2026-04-09 para Task 1 do plano E1 (Knowledge Spine).

## Localizacao no filesystem

### Skills bundled (OpenClaw)
```
~/.npm-global/lib/node_modules/openclaw/skills/
```
Contém 50+ skills como `weather/`, `healthcheck/`, `coding-agent/`, `skill-creator/`, etc.

### Skills managedSkillsDir (clawhub / openclaw instala)
```
~/.openclaw/skills/
```
(Nao existe ainda - seria criado pelo `openclaw skills install`)

### Skills pessoais (agentskit-compat)
```
~/.agents/skills/
```
(Nao existe ainda - formato alternativo compativel)

### Skills de workspace (projeto)
```
<workspaceDir>/skills/           -> ~/.openclaw/workspace/skills/
<workspaceDir>/.agents/skills/   -> ~/.openclaw/workspace/.agents/skills/
```
(Nao existe ainda)

### Extra dirs via config
```json
// openclaw.json - chave: skills.load.extraDirs
{ "skills": { "load": { "extraDirs": ["/caminho/custom/skills"] } } }
```

### Ordem de precedencia (a ultima sobrescreve)
1. extraSkills (extraDirs + plugin dirs)
2. bundledSkills (openclaw bundled)
3. managedSkills (~/.openclaw/skills)
4. personalAgentsSkills (~/.agents/skills)
5. projectAgentsSkills (<workspace>/.agents/skills)
6. workspaceSkills (<workspace>/skills)  ← maior precedencia

## Estrutura de uma skill (exemplo: weather)

```
weather/
└── SKILL.md          (unico arquivo obrigatorio)
```

Exemplo com mais recursos (tmux):
```
tmux/
├── SKILL.md
└── scripts/
    ├── wait-for-text.sh
    └── find-sessions.sh
```

Exemplo com referencias (himalaya):
```
himalaya/
├── SKILL.md
└── references/
    └── *.md
```

Estrutura completa possivel (skill-creator):
```
skill-creator/
├── SKILL.md
├── license.txt
└── scripts/
    ├── init_skill.py
    ├── package_skill.py
    ├── quick_validate.py
    ├── test_quick_validate.py
    └── test_package_skill.py
```

## Manifest

- Arquivo: `SKILL.md`
- Formato: **Markdown com YAML frontmatter**
- Campos obrigatorios no frontmatter: `name`, `description`
- Campos opcionais no frontmatter: `homepage`, `metadata` (para requisitos de binarios e instrucoes de instalacao)
- Corpo do arquivo: markdown livre com instrucoes para o agente

### Exemplo minimo (weather):
```yaml
---
name: weather
description: "Get current weather and forecasts via wttr.in or Open-Meteo. Use when: user asks about weather, temperature, or forecasts for any location. NOT for: historical weather data, severe weather alerts, or detailed meteorological analysis. No API key needed."
homepage: https://wttr.in/:help
metadata:
  {
    "openclaw":
      {
        "emoji": "☔",
        "requires": { "bins": ["curl"] },
        "install":
          [
            {
              "id": "brew",
              "kind": "brew",
              "formula": "curl",
              "bins": ["curl"],
              "label": "Install curl (brew)",
            },
          ],
      },
  }
---

# Weather Skill

[... corpo markdown com instrucoes ...]
```

### Exemplo com requires anyBins (coding-agent):
```yaml
---
name: coding-agent
description: 'Delegate coding tasks to Codex, Claude Code, or Pi agents via background process...'
metadata:
  {
    "openclaw":
      {
        "emoji": "🧩",
        "requires": { "anyBins": ["claude", "codex", "opencode", "pi"] },
        "install": [ ... ]
      },
  }
---
```

### Skill sem metadata (healthcheck):
```yaml
---
name: healthcheck
description: Host security hardening and risk-tolerance configuration for OpenClaw deployments...
---

# OpenClaw Host Hardening
[... corpo markdown ...]
```

**Conclusao**: `metadata` com `requires.bins` e `install` define o status "needs setup" vs "ready".
Skills sem `requires` ficam automaticamente como "ready".

## Linguagem dos scripts

- Scripts dentro de `scripts/` podem ser em **qualquer linguagem**: bash, Python, etc.
- Exemplos encontrados: `.sh` (bash), `.py` (Python)
- O SKILL.md instrui o agente quando e como usar esses scripts
- Scripts sao opcionais - muitas skills (healthcheck, weather, github) tem apenas SKILL.md

## Como subcomandos sao expostos

**NAO existem subcomandos no sentido CLI tradicional.**

Skills sao **documentos de contexto** (prompt engineering), nao executaveis com subcomandos.

O mecanismo e:
1. O agente (Codex/Claude) recebe no contexto uma lista `<available_skills>` com `name`, `description`, e `location` de cada skill
2. O agente decide qual skill usar baseado na `description` (triggering mechanism)
3. O agente usa `read tool` para carregar o SKILL.md quando necessario
4. O conteudo do SKILL.md instrui o agente sobre como executar a tarefa (pode incluir comandos bash, scripts Python, etc.)

Trecho real do codigo fonte que injeta as skills no contexto:
```
"Use the read tool to load a skill's file when the task matches its description."
"When a skill file references a relative path, resolve it against the skill directory..."
```

Os "subcomandos" do knowledge-sync (watcher, snapshot, notify) serao **secoes no SKILL.md** que instruem o agente sobre como usar os scripts correspondentes em `scripts/`.

## Como invocar

Skills nao sao invocadas diretamente via CLI.

O fluxo e:
1. Usuario envia mensagem para o agente via Telegram/Discord/chat
2. Gateway injeta lista de skills no contexto do agente
3. Agente le o SKILL.md relevante quando a tarefa bate com a description
4. Agente executa os comandos/scripts descritos no SKILL.md usando as ferramentas disponiveis (bash, read, write, etc.)

`openclaw skills` = apenas lista skills (nao executa)

## Como instalar uma nova skill

### Opcao 1: Diretorio de workspace (RECOMENDADA para knowledge-sync)
```bash
mkdir -p ~/.openclaw/workspace/skills/knowledge-sync
# criar SKILL.md e scripts/ dentro
# OpenClaw rescaneia automaticamente a cada sessao
```

### Opcao 2: Diretorio managed (~/.openclaw/skills/)
```bash
mkdir -p ~/.openclaw/skills/knowledge-sync
# criar SKILL.md e scripts/
```

### Opcao 3: ~/.agents/skills/ (formato alternativo)
```bash
mkdir -p ~/.agents/skills/knowledge-sync
```

### Opcao 4: Extra dirs via config (openclaw.json)
```json
{
  "skills": {
    "load": {
      "extraDirs": ["~/bevox-knowledge/skills"]
    }
  }
}
```

**Nao precisa de `openclaw skills install` para skills locais** - apenas criar o diretorio com SKILL.md e o OpenClaw detecta automaticamente.

`openclaw skills install` e para instalar do ClawHub (repositorio remoto de skills).

## Exemplo de skill MAIS SIMPLES (weather)

Conteudo completo do SKILL.md:

```markdown
---
name: weather
description: "Get current weather and forecasts via wttr.in or Open-Meteo. Use when: user asks about weather, temperature, or forecasts for any location. NOT for: historical weather data, severe weather alerts, or detailed meteorological analysis. No API key needed."
homepage: https://wttr.in/:help
metadata:
  {
    "openclaw":
      {
        "emoji": "☔",
        "requires": { "bins": ["curl"] },
        ...
      },
  }
---

# Weather Skill

Get current weather conditions and forecasts.

## When to Use

## Commands

### Current Weather
```bash
curl "wttr.in/London?format=3"
```

[... mais secoes markdown ...]
```

## Decisoes para a skill knowledge-sync

Com base nessa pesquisa:

- **A skill knowledge-sync deve usar**: bash (scripts em bash em `scripts/`)
- **Manifest format**: Markdown com YAML frontmatter (SKILL.md)
- **Sem `requires.bins`**: Para aparecer como "ready" sem dependencias externas (ou listar `git`, `jq` se quiser que fique como "needs setup" sem elas)
- **Estrutura proposta**:
```
knowledge-sync/
├── SKILL.md                    (manifest + instrucoes principais)
└── scripts/
    ├── watcher.sh              (monitora mudancas no repositorio)
    ├── snapshot.sh             (tira snapshot / pull-ff com guardrails)
    └── notify.sh               (envia notificacoes via openclaw system event)
```

- **Como sera instalada**: Criar diretorio em `~/.openclaw/workspace/skills/knowledge-sync/` - OpenClaw detecta automaticamente na proxima sessao
- **Como subcomandos serao expostos**: Secoes no SKILL.md (ex: `## Watcher`, `## Snapshot`, `## Notify`) que instruem o agente quando e como executar cada script
- **Alternativa de diretorio**: Tambem pode ficar em `~/.openclaw/skills/knowledge-sync/` (managedSkillsDir) ou via `skills.load.extraDirs` no openclaw.json apontando para dentro do repo bevox-knowledge

### Decisao de localizacao recomendada

**`~/bevox-knowledge/skills/knowledge-sync/`** com `extraDirs` no openclaw.json.

Vantagem: a skill fica dentro do repo bevox-knowledge (versionada junto com o conhecimento), e o openclaw.json aponta para la. Isso alinha com a proposta do plano de ter a skill dentro do projeto.

Configuracao necessaria em `~/.openclaw/openclaw.json`:
```json
{
  "skills": {
    "load": {
      "extraDirs": ["~/bevox-knowledge/skills"]
    }
  }
}
```

## Possiveis bloqueadores

### NENHUM bloqueador critico encontrado.

### Observacoes importantes:

1. **Skills sao documentos, nao executaveis**: A skill knowledge-sync nao sera um CLI com subcomandos. Sera um SKILL.md que instrui o agente sobre como usar os scripts bash em `scripts/`. O agente e quem decide quando chamar cada script. Isso muda levemente a arquitetura proposta no plano, mas e compativel.

2. **Sem subcomandos via `openclaw skills run`**: Esse comando nao existe. O plano menciona "3 componentes Watcher/Actions/Notifications" - esses serao scripts separados invocados pelo agente conforme instrucoes no SKILL.md.

3. **Cron para watcher**: Se o Watcher precisa rodar periodicamente sem interacao do agente, deve ser configurado como `openclaw cron add` (ja documentado no healthcheck skill). O SKILL.md pode instruir o agente a configurar esse cron.

4. **Status "ready" vs "needs setup"**: Se a skill nao listar `requires.bins`, ficara automaticamente como "ready". Se listar `git` e `jq` como dependencias, pode ficar como "needs setup" ate verificacao.

5. **Precedencia de skills**: Workspace skills sobrescrevem bundled skills. Isso e bom - a knowledge-sync custom nao conflita com nenhuma skill existente.

### Fallback se necessario

Se a abordagem via SKILL.md nao for suficiente para o caso de uso (ex: precisar de um CLI proprio que o agente possa chamar como ferramenta), o fallback seria:
- Criar um script bash `knowledge-sync` em algum diretorio do PATH
- Referenciar esse script no SKILL.md como o comando principal
- Configurar cron via `openclaw cron add` para execucoes periodicas do watcher
