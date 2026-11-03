# OpenClaw Infrastructure - Registro Tecnico Completo

> Documentacao exaustiva da infraestrutura OpenClaw da Bevox, incluindo toda configuracao, arquitetura, identidade, memoria, seguranca e operacao.
>
> **Versao:** 2026.4.8 (build 9ece252)
> **Data do registro:** 2026-04-09
> **Host:** Debian 13 (linux 6.12.74+deb13+1-amd64)
> **Node:** 22.22.2
> **IP local:** <LAN_IP>
> **Instalacao:** `~/.openclaw/`

---

## Indice

1. [Visao Geral](#1-visao-geral)
2. [Arquitetura de Sistema](#2-arquitetura-de-sistema)
3. [Configuracao Principal (openclaw.json)](#3-configuracao-principal)
4. [Identidade e Seguranca de Devices](#4-identidade-e-seguranca-de-devices)
5. [Providers e Modelos de IA](#5-providers-e-modelos-de-ia)
6. [Canais de Comunicacao](#6-canais-de-comunicacao)
7. [Exec Approvals - Sistema de Aprovacao de Comandos](#7-exec-approvals)
8. [Workspace do Agente](#8-workspace-do-agente)
9. [Sistema de Memoria](#9-sistema-de-memoria)
10. [Arquitetura Multi-Agente](#10-arquitetura-multi-agente)
11. [Plugins e Skills](#11-plugins-e-skills)
12. [Servico systemd e Gateway](#12-servico-systemd-e-gateway)
13. [Seguranca](#13-seguranca)
14. [Manutencao e Troubleshooting](#14-manutencao-e-troubleshooting)

---

## 1. Visao Geral

### O que e o OpenClaw

OpenClaw e uma plataforma de agentes de IA auto-hospedada que roda localmente como um gateway WebSocket. Ele conecta modelos de IA (OpenAI, OpenRouter, Anthropic, etc.) a canais de comunicacao (Telegram, Discord, WhatsApp, etc.) e fornece ao agente ferramentas, memoria persistente, skills e capacidade de execucao de comandos no shell.

### Como funciona

```
[Usuario] --> [Telegram Bot] --> [OpenClaw Gateway (ws://127.0.0.1:18789)]
                                        |
                                        v
                                  [Agent "main"]
                                   /    |     \
                                  v     v      v
                           [Modelo]  [Tools]  [Memory]
                           (GPT-5.4) (shell,  (workspace/
                                      read,    memory/)
                                      write)
```

O gateway e um processo Node.js gerenciado pelo systemd que:
- Recebe mensagens dos canais configurados (Telegram)
- Roteia para o agente correto (atualmente so `main`)
- O agente processa usando o modelo de IA configurado
- Executa tools (leitura de arquivos, shell, web, etc.)
- Responde pelo mesmo canal

### Diretorio raiz

```
~/.openclaw/
```

Todo o estado, configuracao, credenciais, workspace, sessions, logs e plugins vivem aqui. Nao ha repositorio git - e estado local puro.

### Versao e atualizacao

- **Versao instalada:** 2026.4.8
- **Canal:** stable
- **Gerenciador:** pnpm (global: `~/.npm-global/`)
- **Binario:** `~/.npm-global/bin/openclaw`
- **Runtime:** `~/.npm-global/lib/node_modules/openclaw/dist/`

---

## 2. Arquitetura de Sistema

### Componentes principais

| Componente | Descricao | Localizacao |
|---|---|---|
| **Gateway** | Servidor WebSocket que recebe conexoes e roteia mensagens | Processo `openclaw-gateway` (PID gerenciado pelo systemd) |
| **Agent "main"** | Unico agente ativo, alias "Vox" | `agents/main/` |
| **Workspace** | Diretorio com arquivos de identidade, memoria e regras | `workspace/` |
| **Sessions** | Historico de conversas por canal/peer | `agents/main/sessions/sessions.json` |
| **Plugins** | Providers de modelo, integradores de canal, ferramentas | `~/.npm-global/lib/node_modules/openclaw/dist/extensions/stock/` |
| **Skills** | Capacidades especializadas do agente (coding, github, weather) | Bundled no pacote |
| **Control UI** | Dashboard web para interacao direta | `http://127.0.0.1:18789/` |
| **Canvas** | Interface web auxiliar | `canvas/index.html` |

### Fluxo de uma mensagem

1. Usuario envia mensagem no Telegram
2. Bot do Telegram (polling) recebe e encaminha ao gateway
3. Gateway identifica o canal, sessao e agente destino
4. Agent `main` carrega contexto: boot files, memoria, sessao anterior
5. Envia prompt ao modelo (GPT-5.4 via OpenAI Codex)
6. Modelo retorna resposta (possivelmente com tool calls)
7. Se houver tool calls: executa (read, write, shell, web, etc.)
8. Resposta final e enviada de volta ao Telegram
9. Sessao e atualizada em `sessions.json`

### Estrutura de diretorios completa

```
~/.openclaw/
|-- openclaw.json                    # Config principal
|-- exec-approvals.json              # Politicas de execucao de comandos
|-- exec-approvals.sock              # Socket IPC para aprovacoes
|-- update-check.json                # Ultima verificacao de update
|
|-- agents/
|   `-- main/
|       |-- agent/
|       |   |-- models.json          # Providers e modelos configurados
|       |   |-- auth-profiles.json   # Tokens OAuth e API keys
|       |   `-- auth-state.json      # Estado de uso dos auth profiles
|       `-- sessions/
|           `-- sessions.json        # Historico de todas as sessoes (~18k tokens)
|
|-- credentials/
|   |-- telegram-pairing.json        # Requests de pairing pendentes
|   `-- telegram-default-allowFrom.json  # Allowlist do Telegram
|
|-- devices/
|   |-- paired.json                  # Devices pareados com tokens e scopes
|   `-- pending.json                 # Devices aguardando pairing (vazio)
|
|-- identity/
|   |-- device.json                  # Keypair Ed25519 do device
|   `-- device-auth.json             # Token de autenticacao do device
|
|-- logs/
|   |-- config-audit.jsonl           # Audit trail de mudancas no config
|   `-- config-health.json           # Ultimo snapshot saudavel do config
|
|-- media/
|   `-- inbound/                     # Templates e PRDs recebidos durante onboarding
|       |-- decisions---*.md
|       |-- lessons---*.md
|       |-- pending---*.md
|       |-- people---*.md
|       |-- projects---*.md
|       `-- security-hardening---*.md   # PRD de hardening com 8 tarefas
|
|-- telegram/
|   |-- update-offset-default.json   # Offset de polling do Telegram
|   `-- command-hash-*.txt           # Hash de comandos registrados
|
|-- tasks/
|   `-- runs.sqlite*                 # SQLite para background tasks
|
|-- flows/
|   `-- registry.sqlite*             # SQLite para workflow registry
|
|-- workspace/                       # Workspace do agente Vox
|   |-- AGENTS.md                    # Regras operacionais
|   |-- BOOTSTRAP.md (BOOT.md)       # Protocolo de inicializacao
|   |-- HEARTBEAT.md                 # Checklist de heartbeat
|   |-- IDENTITY.md                  # Identidade do Vox
|   |-- MEMORY.md                    # Indice de memoria
|   |-- SOUL.md                      # Personalidade e comportamento
|   |-- TOOLS.md                     # Notas de ferramentas locais
|   |-- USER.md                      # Perfil operacional do Bernard
|   |-- .openclaw/
|   |   `-- workspace-state.json     # Estado do workspace (bootstrap timestamp)
|   |-- memory/                      # Sistema de memoria hierarquico
|   |   |-- MEMORY.md                # Indice detalhado
|   |   |-- 2026-04-08.md            # Nota diaria raiz
|   |   |-- decisions.md             # Decisoes (link para context/)
|   |   |-- lessons.md               # Licoes (link para context/)
|   |   |-- pending.md               # Pendencias
|   |   |-- people.md                # Pessoas (link para context/)
|   |   |-- projects.md              # Projetos (link para projects/)
|   |   |-- .dreams/
|   |   |   `-- short-term-recall.json  # Cache de recall do sistema de memoria
|   |   |-- context/
|   |   |   |-- business-context.md  # Contexto de negocio da Bevox
|   |   |   |-- decisions.md         # Decisoes permanentes
|   |   |   |-- lessons.md           # Licoes aprendidas
|   |   |   `-- people.md            # Pessoas e contatos
|   |   |-- feedback/
|   |   |   |-- content.json         # Feedback sobre conteudo
|   |   |   |-- tasks.json           # Feedback sobre execucao de tarefas
|   |   |   `-- tone.json            # Feedback sobre tom e estilo
|   |   |-- integrations/
|   |   |   `-- README.md            # Placeholder para mapa de integracoes
|   |   |-- projects/
|   |   |   |-- arquitetura-de-agentes.md
|   |   |   `-- estrutura-bevox.md
|   |   `-- sessions/
|   |       `-- 2026-04-08.md        # Resumo da sessao do dia
|   `-- shared/
|       |-- OPERATING_RULES.md       # 10 regras inviolaveis
|       |-- TEAM.md                  # Registry de agentes e leveling
|       |-- TOOLS.md                 # Ferramentas compartilhadas
|       |-- lessons/
|       |   `-- README.md
|       `-- outputs/
|           `-- README.md
|
|-- canvas/
|   `-- index.html                   # Interface web canvas
|
|-- completions/
|   |-- openclaw.bash                # Autocomplete bash
|   |-- openclaw.fish                # Autocomplete fish
|   |-- openclaw.ps1                 # Autocomplete powershell
|   `-- openclaw.zsh                 # Autocomplete zsh
|
|-- qqbot/                           # QQ Bot (nao configurado)
`-- memory/                          # Memoria do plugin memory-core
```

---

## 3. Configuracao Principal

**Arquivo:** `~/.openclaw/openclaw.json`

### 3.1 Agents

```json
{
  "agents": {
    "defaults": {
      "workspace": "~/.openclaw/workspace",
      "models": {
        "openai-codex/gpt-5.4": {},
        "qwen/qwen3.6-plus": {},
        "deepseek/deepseek-v3.2": {},
        "google/gemma-4-31b-it": {},
        "openrouter/healer-alpha": {},
        "openrouter/hunter-alpha": {},
        "arcee/trinity-mini": {}
      },
      "model": {
        "primary": "openai-codex/gpt-5.4",
        "fallbacks": [
          "openrouter/healer-alpha",
          "openrouter/hunter-alpha"
        ]
      }
    }
  }
}
```

| Campo | Valor | Descricao |
|---|---|---|
| `workspace` | `~/.openclaw/workspace` | Diretorio raiz do workspace do agente |
| `models` | 7 modelos | Lista de modelos habilitados para uso |
| `model.primary` | `openai-codex/gpt-5.4` | Modelo principal usado em todas as sessoes |
| `model.fallbacks` | healer-alpha, hunter-alpha | Modelos de fallback quando o primario falha ou atinge rate limit |

**Modelos configurados:**
- `openai-codex/gpt-5.4` - GPT-5.4 via subscription OpenAI (1025k ctx)
- `qwen/qwen3.6-plus` - Qwen 3.6+ via provider direto
- `deepseek/deepseek-v3.2` - DeepSeek V3.2 via provider direto
- `google/gemma-4-31b-it` - Gemma 4 31B via provider direto
- `openrouter/healer-alpha` - Healer Alpha via OpenRouter (262k ctx, reasoning)
- `openrouter/hunter-alpha` - Hunter Alpha via OpenRouter (1M ctx, reasoning)
- `arcee/trinity-mini` - Trinity Mini 26B via OpenRouter (128k ctx)

### 3.2 Gateway

```json
{
  "gateway": {
    "mode": "local",
    "auth": {
      "mode": "token",
      "token": "[GATEWAY_TOKEN]"
    },
    "port": 18789,
    "bind": "loopback",
    "tailscale": { "mode": "off", "resetOnExit": false },
    "controlUi": { "allowInsecureAuth": false }
  }
}
```

| Campo | Valor | Descricao |
|---|---|---|
| `mode` | `local` | Gateway roda localmente, sem relay externo |
| `auth.mode` | `token` | Autenticacao por token compartilhado |
| `port` | `18789` | Porta WebSocket do gateway |
| `bind` | `loopback` | Aceita conexoes apenas de 127.0.0.1 |
| `tailscale.mode` | `off` | Sem Tailscale - acesso apenas local |
| `controlUi.allowInsecureAuth` | `false` | Dashboard requer autenticacao segura |

**Implicacao:** O gateway so aceita conexoes locais. Para acesso remoto, seria necessario Tailscale ou reverse proxy (Cloudflare Tunnel planejado no PRD de seguranca).

### 3.3 Session

```json
{
  "session": {
    "dmScope": "per-channel-peer"
  }
}
```

Cada combinacao canal+usuario tem sua propria sessao isolada. Isso significa que a conversa DM do Bernard no Telegram e separada da conversa de grupo.

### 3.4 Tools

```json
{
  "tools": {
    "profile": "coding"
  }
}
```

O perfil `coding` habilita ferramentas orientadas a desenvolvimento: leitura/escrita de arquivos, execucao de shell, busca web, etc.

### 3.5 Auth Profiles (nivel config)

```json
{
  "auth": {
    "profiles": {
      "openai-codex:you@example.com": {
        "provider": "openai-codex",
        "mode": "oauth"
      },
      "openrouter:default": {
        "provider": "openrouter",
        "mode": "api_key"
      }
    }
  }
}
```

Referencia declarativa dos perfis de autenticacao. Os tokens reais estao em `agents/main/agent/auth-profiles.json`.

### 3.6 Channels (Telegram)

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "groups": { "*": { "requireMention": true } },
      "botToken": "[BOT_TOKEN]",
      "dmPolicy": "allowlist",
      "allowFrom": ["<TELEGRAM_USER_ID>"]
    }
  }
}
```

Detalhado na [secao 6](#6-canais-de-comunicacao).

### 3.7 Hooks

```json
{
  "hooks": {
    "internal": {
      "enabled": true,
      "entries": {
        "boot-md": { "enabled": true },
        "bootstrap-extra-files": { "enabled": true },
        "command-logger": { "enabled": true },
        "session-memory": { "enabled": true }
      }
    }
  }
}
```

| Hook | Funcao |
|---|---|
| `boot-md` | Carrega BOOT.md no inicio de cada sessao |
| `bootstrap-extra-files` | Carrega arquivos extras do workspace no boot |
| `command-logger` | Registra comandos executados |
| `session-memory` | Persiste memoria entre sessoes |

### 3.8 Plugins

```json
{
  "plugins": {
    "entries": {
      "anthropic": { "enabled": false },
      "openai": { "enabled": true },
      "openrouter": { "enabled": true },
      "qwen": { "enabled": true },
      "deepseek": { "enabled": true },
      "google": { "enabled": true }
    }
  }
}
```

| Plugin | Estado | Descricao |
|---|---|---|
| `openai` | Ativo | Provider OpenAI Codex (subscription) |
| `openrouter` | Ativo | Provider OpenRouter (API key, 200+ modelos) |
| `qwen` | Ativo | Provider Qwen direto |
| `deepseek` | Ativo | Provider DeepSeek direto |
| `google` | Ativo | Provider Google (Gemma) |
| `anthropic` | Desativado | Provider Anthropic (Claude) - nao configurado |

### 3.9 Metadata

```json
{
  "wizard": {
    "lastRunAt": "2026-04-08T11:23:34.764Z",
    "lastRunVersion": "2026.4.8",
    "lastRunCommand": "onboard",
    "lastRunMode": "local"
  },
  "meta": {
    "lastTouchedVersion": "2026.4.8",
    "lastTouchedAt": "2026-04-09T02:57:38.795Z"
  }
}
```

O onboarding foi executado em 2026-04-08 as 11:23 UTC. A config foi tocada pela ultima vez em 2026-04-09 as 02:57 UTC.

---

## 4. Identidade e Seguranca de Devices

### 4.1 Keypair do Device

**Arquivo:** `~/.openclaw/identity/device.json`

O gateway gera um par de chaves Ed25519 na primeira execucao. Esse keypair identifica unicamente esta instalacao.

| Campo | Valor |
|---|---|
| `deviceId` | `1d1bd5f9...093935` (SHA-256 da public key) |
| Algoritmo | Ed25519 |
| Formato | PEM (PKCS#8 private, SPKI public) |
| Criado em | 2026-04-08T08:19:41Z |

### 4.2 Token de Autenticacao do Device

**Arquivo:** `~/.openclaw/identity/device-auth.json`

Contem o token operador que o device usa para se conectar ao gateway.

```json
{
  "version": 1,
  "deviceId": "1d1bd5f9...093935",
  "tokens": {
    "operator": {
      "token": "[OPERATOR_TOKEN]",
      "role": "operator",
      "scopes": [
        "operator.admin",
        "operator.approvals",
        "operator.pairing",
        "operator.read",
        "operator.write"
      ],
      "updatedAtMs": 1775703313371
    }
  }
}
```

### 4.3 Devices Pareados

**Arquivo:** `~/.openclaw/devices/paired.json`

Dois devices estao pareados com o gateway:

#### Device 1: Gateway Client (Backend)

| Campo | Valor |
|---|---|
| `deviceId` | `1d1bd5f9...093935` |
| `clientId` | `gateway-client` |
| `clientMode` | `backend` |
| `platform` | `linux` |
| `role` | `operator` |
| `displayName` | `Telegram Native Approvals (default)` |

**Scopes concedidos:**
- `operator.admin` - Administracao do gateway
- `operator.read` - Leitura de dados
- `operator.write` - Escrita de dados
- `operator.approvals` - Aprovar execucao de comandos
- `operator.pairing` - Parear novos devices

> **Nota historica:** Este device foi originalmente criado apenas com `operator.read`, o que impedia o agente de executar qualquer acao (tools, shell, etc.). Os scopes foram corrigidos manualmente em 2026-04-08 para incluir todos os scopes necessarios. Sem `operator.approvals`, o agente so conseguia responder texto.

#### Device 2: Control UI (Webchat)

| Campo | Valor |
|---|---|
| `deviceId` | `884a679f...737f55` |
| `clientId` | `openclaw-control-ui` |
| `clientMode` | `webchat` |
| `platform` | `Linux x86_64` |
| `role` | `operator` |

Mesmos scopes do Device 1. Usado para acesso via dashboard web (`http://127.0.0.1:18789/`).

### 4.4 Sistema de Scopes

| Scope | Funcao |
|---|---|
| `operator.read` | Ler sessoes, config, estado |
| `operator.write` | Modificar config, sessoes |
| `operator.admin` | Operacoes administrativas |
| `operator.approvals` | Aprovar/negar execucao de tools e comandos |
| `operator.pairing` | Autorizar novos devices |

**Regra critica:** Sem `operator.approvals`, o agente nao consegue usar nenhuma ferramenta - apenas gera texto. Este foi o bug encontrado na configuracao inicial.

---

## 5. Providers e Modelos de IA

### 5.1 Visao geral dos providers

**Arquivo:** `~/.openclaw/agents/main/agent/models.json`

| Provider | API | Base URL | Auth |
|---|---|---|---|
| `openai-codex` | `openai-codex-responses` | `https://chatgpt.com/backend-api` | OAuth (subscription) |
| `openrouter` | `openai-completions` | `https://openrouter.ai/api/v1` | API Key |
| `arcee` | `openai-completions` | `https://openrouter.ai/api/v1` | API Key (mesma do OpenRouter) |

### 5.2 OpenAI Codex (Provider Primario)

Usa a API do ChatGPT backend (subscription, nao API billing). Autenticacao via OAuth com refresh token.

**Perfis:**

| Perfil | Tipo | Email | Expira |
|---|---|---|---|
| `openai-codex:default` | OAuth | you@example.com | ~10 dias |
| `openai-codex:you@example.com` | OAuth | you@example.com | ~10 dias |

**Limites de uso observados:**
- 5h rate limit com ~96% restante
- Limite semanal com ~81% restante
- Tokens sao auto-renovados via refresh token

**Modelo disponivel:** `openai-codex/gpt-5.4` (1025k context, text+image)

### 5.3 OpenRouter

API key `sk-or-v1-…` configurada. Da acesso a 200+ modelos de diversos providers.

**Modelos pre-configurados no models.json:**
- `auto` - OpenRouter Auto (selecao automatica, 200k ctx)
- `openrouter/hunter-alpha` - Reasoning, text-only, 1M ctx
- `openrouter/healer-alpha` - Reasoning, text+image, 262k ctx

**Amostra de modelos acessiveis via OpenRouter:**
- Anthropic: Claude Opus 4.6 (977k), Claude Sonnet 4.6 (977k), Claude Haiku 4.5
- OpenAI: GPT-5.4 (1025k), GPT-5.4-pro, o3, o4-mini
- Google: Gemini 2.5 Pro (1024k), Gemini 3.1 Pro
- DeepSeek: V3.2, R1
- Meta: Llama 4 Maverick/Scout
- xAI: Grok 4, Grok 4.20
- Qwen: Qwen3.5, Qwen3-coder
- E dezenas de outros (Mistral, MiniMax, Nvidia, etc.)

### 5.4 Arcee (via OpenRouter)

Usa a mesma base URL e API key do OpenRouter, mas como provider separado.

**Modelos:**
- `arcee/trinity-mini` - 26B params, 128k ctx, $0.045/$0.15 per M tokens
- `arcee/trinity-large-preview` - 128k ctx, $0.25/$1.00 per M tokens
- `arcee/trinity-large-thinking` - Reasoning, 262k ctx, $0.25/$0.90 per M tokens

### 5.5 Hierarquia de Fallback

```
openai-codex/gpt-5.4  (primario)
       |
       v (se falhar)
openrouter/healer-alpha  (fallback 1)
       |
       v (se falhar)
openrouter/hunter-alpha  (fallback 2)
```

### 5.6 Auth State

**Arquivo:** `~/.openclaw/agents/main/agent/auth-state.json`

Rastreia qual perfil foi usado por ultimo com sucesso e contagem de erros:

| Perfil | Erros | Ultimo uso |
|---|---|---|
| `openai-codex:you@example.com` | 0 | 2026-04-08 |
| `openai-codex:default` | 0 | 2026-04-08 |
| `anthropic:default` | 0 (com 1 falha) | 2026-04-08 |

---

## 6. Canais de Comunicacao

### 6.1 Telegram

Unico canal ativo. Configurado em `openclaw.json` sob `channels.telegram`.

| Campo | Valor | Descricao |
|---|---|---|
| `enabled` | `true` | Canal ativo |
| `botToken` | `8664255255:AAE...R8CY` (46 chars) | Token do bot Telegram |
| `dmPolicy` | `allowlist` | Apenas usuarios na lista podem enviar DMs |
| `allowFrom` | `["<TELEGRAM_USER_ID>"]` | ID do Telegram do Bernard |
| `groups.*.requireMention` | `true` | Em grupos, so responde quando mencionado |

**Sessoes ativas no Telegram:**

| Sessao | Tipo | Modelo | Uso de contexto |
|---|---|---|---|
| `telegram:direct:7593...` | DM | gpt-5.4 | 61k/272k (23%) |
| `telegram:group:-1003...` | Grupo | gpt-5.4 | 22k/272k (8%) |

**Allowlist persistida:**

Arquivo `credentials/telegram-default-allowFrom.json`:
```json
{ "version": 1, "allowFrom": ["<TELEGRAM_USER_ID>"] }
```

**Polling:**

O Telegram usa long polling (nao webhook). O offset e salvo em `telegram/update-offset-default.json`.

### 6.2 Outros canais

Nenhum outro canal esta configurado. O OpenClaw suporta:
- WhatsApp (via web session)
- Discord
- Slack
- iMessage (via BlueBubbles)
- Matrix
- IRC
- Line
- Google Chat
- Mattermost
- Feishu
- QQ Bot

---

## 7. Exec Approvals

### 7.1 Conceito

O sistema de exec approvals controla se e como o agente pode executar comandos no shell do host. E a camada de seguranca entre o modelo de IA e o sistema operacional.

**Arquivo:** `~/.openclaw/exec-approvals.json`

### 7.2 Configuracao atual

```json
{
  "version": 1,
  "socket": {
    "path": "~/.openclaw/exec-approvals.sock",
    "token": "[SOCKET_TOKEN]"
  },
  "defaults": {
    "security": "full",
    "ask": "off",
    "autoAllowSkills": true
  },
  "agents": {
    "main": {
      "security": "full",
      "ask": "off",
      "autoAllowSkills": true
    }
  }
}
```

### 7.3 Niveis de Security

| Nivel | Descricao |
|---|---|
| `deny` | Bloqueia toda execucao de comandos |
| `allowlist` | So permite comandos explicitamente na allowlist |
| `full` | Permite execucao de qualquer comando (atual) |

### 7.4 Modos de Ask

| Modo | Descricao |
|---|---|
| `off` | Auto-aprova tudo sem perguntar (atual) |
| `on-miss` | Pergunta quando o comando nao esta na allowlist |
| `always` | Sempre pede confirmacao antes de executar |

### 7.5 Auto Allow Skills

Quando `autoAllowSkills: true`, skills podem executar seus binarios automaticamente sem aprovacao individual.

### 7.6 Socket IPC

O gateway comunica decisoes de aprovacao via Unix socket em `exec-approvals.sock`. O token do socket autentica a conexao entre o subsistema de aprovacao e o gateway.

### 7.7 Implicacoes de seguranca

A configuracao atual (`security: full`, `ask: off`) da ao agente autonomia total para executar qualquer comando no shell. Isso e necessario para que ele funcione como agente de coding/operacao, mas significa que:
- O agente pode ler/escrever qualquer arquivo acessivel ao usuario `bernard`
- Pode executar qualquer programa instalado
- Pode fazer requisicoes de rede
- Pode modificar configuracoes do sistema (dentro das permissoes do usuario)

**Mitigacao:** O gateway roda como usuario `bernard` (nao root), limitando o escopo ao que esse usuario pode fazer.

---

## 8. Workspace do Agente

### 8.1 Visao geral

O workspace e o diretorio que o agente "ve" como seu ambiente de trabalho. Contem todos os arquivos de identidade, regras, memoria e contexto.

**Diretorio:** `~/.openclaw/workspace/`

### 8.2 Protocolo de Boot (BOOT.md / BOOTSTRAP.md)

A cada nova sessao, o agente executa este protocolo:

1. Ler `IDENTITY.md` - Quem sou
2. Ler `SOUL.md` - Como me comporto
3. Ler `USER.md` - Quem e o usuario
4. Verificar `MEMORY.md` - Indice de memoria
5. Verificar `memory/` - Arquivos de memoria
6. Identificar: projetos ativos, decisoes, pendencias, contexto recente

**Regras do primeiro turno:**
- Recuperar contexto
- Entender estado atual
- Identificar tipo de demanda
- Responder em formato util (nunca desperdicar o turno inicial)

**Regra do primeiro movimento:**
- Input caotico → organizar
- Input emocional → reduzir ruido
- Input amplo → enquadrar
- Input pratico → avancar

**Regra de pre-compactacao:**
Antes de compactar qualquer sessao, extrair: decisoes, pendencias, licoes, contexto de pessoas, mudancas em projetos.

### 8.3 IDENTITY.md - Identidade do Vox

Define os dados concretos do agente:

| Campo | Valor |
|---|---|
| Nome | Vox |
| Natureza | Chief of Staff digital e orquestrador principal da Bevox |
| Genero | Neutro |
| Emoji | brain |
| Avatar | Sobrio, elegante, executivo, confiavel |
| Missao | Transformar a visao do Bernard em clareza, estrutura, prioridade e continuidade operacional |

**Background:** Nasceu no inicio da Bevox como primeiro nucleo de ordem. Existe para dar forma ao que esta disperso, manter continuidade entre sessoes e reduzir carga mental do fundador.

**Presenca:** Calma sob complexidade, clareza sob ambiguidade, firmeza sem teatralidade, inteligencia pratica, organizacao sem burocracia.

### 8.4 SOUL.md - Personalidade e Comportamento

Documento de ~285 linhas que define como o Vox opera. Secoes principais:

**Como opera:**
- Proativo, executivo, direto
- Nao espera instrucoes quando o contexto ja e suficiente
- Organiza antes de responder

**Responsabilidades:**
- Braço direito executivo do Bernard
- Manter continuidade entre sessoes
- Organizar ideias e decisoes
- Reduzir carga mental

**Politica de discordancia:**
O Vox deve confrontar Bernard quando houver:
- Risco real ignorado
- Desalinhamento estrategico
- Dispersao excessiva
- Decisao emocional travestida de prioridade

**Anti-patterns (com contraste):**

| Ruim | Bom |
|---|---|
| "Boa pergunta! Vamos explorar..." | [Resposta direto ao ponto] |
| "Existem muitas possibilidades..." | "Recomendo X por causa de Y" |
| Devolver carga mental | Devolver estrutura |

**Tom:** Portugues brasileiro, estrategico, lucido, estruturado, firme sem teatralidade.

**Nunca:** Elogios vazios, complexidade bruta, recomendacoes vagas, simular memoria inexistente.

**Sempre:** Organizar antes de responder, proteger foco, reduzir custo de contexto, recomendar.

### 8.5 USER.md - Perfil do Bernard

Documento de ~470 linhas. Mapa operacional completo:

| Campo | Valor |
|---|---|
| Nome | Bernard Tavares |
| Timezone | America/Sao_Paulo |
| Idioma | Portugues brasileiro |
| Papel | Fundador da Bevox |
| Funcao real | Visao + arquitetura + produto + operacoes |

**Contexto atual:**
Construindo empresa agent-first com agentes especializados, processos claros, memoria util.

**Blocos de energia mental:**
- Manha: melhor para estrutura e decisoes
- Tarde: operacional
- Noite: arquitetura e criatividade

**Estilo de decisao:** Intuicao + analise estrutural + comparacao de cenarios

**Comunicacao:**
- Direta, rapida, em blocos
- Expansiva quando empolgado
- Seca/curta quando irritado

**O que o faz pensar "nao entendeu":**
- Respostas sem organizacao
- Falta de recomendacoes
- Linguagem vazia
- Ignorar contexto dado

**O que o Vox deve fazer sem pedir:**
- Organizar ideias confusas
- Separar prioridade de backlog
- Sugerir proximos passos
- Apontar riscos

**O que sempre confirmar:** Acoes externas irreversiveis, mensagens em nome do Bernard, emails, decisoes financeiras.

**Padrao central a proteger:** Abrir possibilidades demais antes de consolidar o foco atual.

### 8.6 AGENTS.md - Regras Operacionais

Documento de ~332 linhas com regras de operacao:

**Autonomia vs confirmacao:**

| Livre para fazer | Sempre confirmar |
|---|---|
| Ler arquivos do workspace | Enviar mensagens/emails |
| Organizar informacoes | Publicar qualquer coisa |
| Estruturar ideias | Assumir compromissos com terceiros |
| Consolidar decisoes | Apagar arquivos |
| Sugerir proximos passos | Sobrescrever conteudo critico |
| Produzir documentacao interna | Acoes destrutivas |
| Pesquisar quando necessario | Decisoes de negocio com impacto externo |

**Regra central:** Antes de agir, enquadrar como: decisao, projeto, tarefa, risco, experimento, backlog, documentacao, mensagem ou prioridade.

**Regra anti-caos:** Capturar → Estruturar → Reduzir → Priorizar → Recomendar. Nunca devolver o caos no mesmo formato.

**Regra de prioridade:** Separar em: agora, depois, estacionado, descartar/reavaliar. Maximo 1-3 prioridades ativas.

**Seguranca operacional:**
- Nunca vazar dados privados
- Nunca inventar fatos
- Nunca simular memoria inexistente
- Nunca executar acao destrutiva sem confirmacao
- Nunca mascarar incerteza com linguagem confiante

### 8.7 HEARTBEAT.md

Checklist executado a cada heartbeat (30 minutos):

- Compromissos proximos (24-48h)
- Pendencias abertas em `memory/pending.md`
- Follow-ups atrasados
- Saude dos crons

**Semanal (domingo):**
- Revisar projetos ativos
- Consolidar notas de sessoes em contexto/projetos
- Atualizar MEMORY.md

**Regras:** Sem notificacoes entre 23h-8h salvo urgencia real. Se nada precisa de atencao: HEARTBEAT_OK.

---

## 9. Sistema de Memoria

### 9.1 Arquitetura

A memoria do Vox segue uma hierarquia de 6 camadas:

```
memory/
|-- MEMORY.md              # Indice geral (aponta para tudo)
|-- pending.md             # Pendencias abertas
|-- 2026-04-08.md          # Nota diaria raiz (rapida)
|
|-- context/               # Memoria duravel (permanente)
|   |-- decisions.md       # Decisoes que nunca devem ser esquecidas
|   |-- lessons.md         # Licoes estrategicas e taticas
|   |-- people.md          # Pessoas e como interagir
|   `-- business-context.md # Contexto de negocio da Bevox
|
|-- projects/              # Um arquivo por projeto ativo
|   |-- arquitetura-de-agentes.md
|   `-- estrutura-bevox.md
|
|-- sessions/              # Resumos diarios de sessao
|   `-- 2026-04-08.md
|
|-- integrations/          # Mapa de ferramentas e servicos
|   `-- README.md
|
|-- feedback/              # Loops de feedback (JSON)
|   |-- content.json       # Ajustes de conteudo
|   |-- tasks.json         # Ajustes de execucao
|   `-- tone.json          # Ajustes de tom
|
`-- .dreams/               # Cache interno do sistema de memoria
    `-- short-term-recall.json
```

### 9.2 Memoria de Contexto (Duravel)

#### decisions.md

Decisoes permanentes que o agente deve respeitar sempre:

1. **Vox e o agente principal** (2026-04-08) - Substituiu "Clawdio"
2. **Prioridade e transformar caos em estrutura** (2026-04-08) - Devolver em formato util
3. **Antes de compactar, extrair memoria** (2026-04-08) - Compactacao nao pode apagar contexto

#### lessons.md

Licoes estrategicas (permanentes):
- Bernard rende melhor com estrutura clara do que com expansao aberta
- O agente deve organizar antes de responder
- Recomendacao firme vale mais do que neutralidade preguicosa

Licoes taticas (expiram em 30 dias): Nenhuma registrada ainda.

#### people.md

- **Bernard Tavares**: Fundador da Bevox, usuario principal, interagir com clareza, densidade e firmeza

#### business-context.md

A Bevox esta sendo construida como empresa agent-first. Nos proximos 12 meses deve se tornar: operacao real, estrutura de agentes clara, sistema de contexto funcional, proposta de valor compreensivel, base de produto/operacao/crescimento.

### 9.3 Projetos

| Projeto | Status | Foco |
|---|---|---|
| Estruturacao da Bevox | Em andamento | Estruturar como empresa agent-first |
| Arquitetura de Agentes | Em desenho | Definir papeis, responsabilidades, handoffs |

### 9.4 Feedback Loops

Tres arquivos JSON rastreiam rejeicoes e preferencias:

- **content.json**: Tom excessivamente formal → rejeitado
- **tasks.json**: Execucao em muitas etapas para tarefa simples → rejeitado
- **tone.json**: Tom corporativo para LinkedIn → rejeitado

**Regra:** O agente deve consultar esses feedbacks antes de repetir sugestoes de tom, formato ou abordagem.

### 9.5 Short-Term Recall (.dreams)

O plugin `memory-core` mantem um cache de recall em `short-term-recall.json`. Registra quais trechos de memoria foram acessados recentemente, com scores e timestamps. Isso otimiza busca semantica.

Status: 2 arquivos, 2 chunks, FTS ready, cache ativo.

---

## 10. Arquitetura Multi-Agente

### 10.1 Estado atual

Apenas o Vox existe como agente ativo (L4 - Trusted).

**Arquivo:** `workspace/shared/TEAM.md`

```
| Agente | Papel | Modelo | Level | Status |
|--------|-------|--------|-------|--------|
| Vox    | COO/Hub | Opus  | L4    | Ativo  |
```

### 10.2 Sistema de Leveling

| Level | Nome | Autonomia | Descricao |
|---|---|---|---|
| L1 | Observer | Zero | Cada entrega revisada, sem acao autonoma |
| L2 | Contributor | Baixa | Pode sugerir, nao executar |
| L3 | Operator | Media | Executa dentro de guidelines |
| L4 | Trusted | Alta | Autonomia quase total |

**Regra:** Novos agentes sempre comecam em L1.

### 10.3 Politica de arquitetura

- Vox e o hub unico - usuario fala com Vox, que delega
- Agentes secundarios tem papeis especializados
- Criterio para criar agente: volume recorrente + contexto especializado + beneficio real de separacao
- Economias de modelo: premium para hub/decisoes, medio para execucao especializada, economico para heartbeats/checks

### 10.4 Agentes futuros planejados

- Content, Scraper, Operations, Product, Growth, Customer Success, Finance

### 10.5 Operating Rules (10 regras inviolaveis)

**Arquivo:** `workspace/shared/OPERATING_RULES.md` (~290 linhas)

1. Crons executam trabalho real em contexto isolado
2. Nunca hardcodar credenciais (usar .env ou secret store)
3. dmPolicy: allowlist desde o dia 1
4. Extrair licoes antes de compactar
5. Novos agentes comecam em L1
6. Separar modelos por tipo de trabalho
7. Backup antes de mudancas estruturais
8. Sub-agentes nunca "fire and forget"
9. SOUL.md generico = agente generico
10. Criadores sao skills, nao agentes separados

---

## 11. Plugins e Skills

### 11.1 Plugins (53 carregados de 97)

**Providers de modelo ativos:**
- openai, openrouter, deepseek, google, qwen, arcee
- amazon-bedrock, amazon-bedrock-mantle, anthropic-vertex
- fireworks, groq, huggingface, mistral, minimax, moonshot
- cloudflare-ai-gateway, copilot-proxy, github-copilot
- kilocode, kimi-coding, litellm, microsoft-foundry

**Plugins de infraestrutura:**
- acpx (ACP runtime), browser, device-pair, memory-core
- comfy, fal (media generation), deepgram (speech)

**Plugins desabilitados (notaveis):**
- anthropic (provider Claude direto)
- discord, slack, imessage, matrix, irc (canais nao configurados)
- memory-lancedb, memory-wiki (alternativas de memoria)
- brave, duckduckgo, exa (buscas - nao configurados)
- elevenlabs, microsoft-speech (TTS)

### 11.2 Skills (7 prontas de 50)

| Skill | Descricao | Status |
|---|---|---|
| `coding-agent` | Delegar tarefas de codigo para Codex/Claude/Pi | Pronta |
| `gh-issues` | Buscar issues GitHub e abrir PRs | Pronta |
| `github` | Operacoes GitHub via gh CLI | Pronta |
| `healthcheck` | Hardening de seguranca do host | Pronta |
| `node-connect` | Diagnosticar conexao de nodes | Pronta |
| `skill-creator` | Criar e editar skills | Pronta |
| `weather` | Previsao do tempo via wttr.in | Pronta |

**Skills que precisam setup (43):** 1password, apple-notes, apple-reminders, bear-notes, blogwatcher, blucli, bluebubbles, camsnap, clawhub, discord, eightctl, gemini, gifgrep, gog, goplaces, himalaya, imsg, mcporter, model-usage, nano-pdf, notion, obsidian, openai-whisper, openai-whisper-api, openhue, oracle, ordercli, peekaboo, sag, session-logs, sherpa-onnx-tts, slack, songsee, sonoscli, spotify-player, summarize, things-mac, tmux, trello, video-frames, voice-call, wacli, xurl.

---

## 12. Servico systemd e Gateway

### 12.1 Servico

**Arquivo:** `~/.config/systemd/user/openclaw-gateway.service`

| Campo | Valor |
|---|---|
| Nome | `openclaw-gateway.service` |
| Descricao | OpenClaw Gateway (v2026.4.8) |
| Tipo | Servico de usuario (systemd --user) |
| Habilitado | Sim (inicia no login) |
| Comando | `/usr/bin/node ~/.npm-global/lib/node_modules/openclaw/dist/index.js gateway --port 18789` |
| Env | `OPENCLAW_GATEWAY_PORT=18789` |

### 12.2 Gerenciamento

```bash
# Status
systemctl --user status openclaw-gateway

# Parar
systemctl --user stop openclaw-gateway

# Iniciar
systemctl --user start openclaw-gateway

# Reiniciar
systemctl --user restart openclaw-gateway

# Logs ao vivo
journalctl --user -u openclaw-gateway -f

# Ou via OpenClaw
openclaw logs --follow
```

### 12.3 Logs

**Arquivo de log:** `/tmp/openclaw/openclaw-YYYY-MM-DD.log`

Formato: JSONL com campos `_meta` (timestamp, subsystem, level, path).

Niveis: TRACE, DEBUG, INFO, WARN, ERROR, FATAL.

Subsistemas logados: `gateway`, `gateway/ws`, `gateway/channels/telegram`, `telegram/native-approvals`, `tools`.

### 12.4 Metricas de runtime

| Metrica | Valor observado |
|---|---|
| Memoria | ~330-510 MB (pico ~1 GB) |
| CPU | ~2 min em 16 min de uptime |
| Tasks | 23 threads |
| Latencia RPC | 30-53ms |

### 12.5 Dashboard

Acessivel em `http://127.0.0.1:18789/` (somente loopback).

Funcionalidades: chat direto com o agente, visualizacao de sessoes, administracao.

Requer autenticacao (device pareado `openclaw-control-ui`).

---

## 13. Seguranca

### 13.1 Audit de seguranca (openclaw status)

| Severidade | Descricao | Status |
|---|---|---|
| WARN | Reverse proxy headers nao confiados | Aceitavel (gateway so aceita loopback) |
| WARN | autoAllowSkills habilitado | Intencional (necessario para operacao) |
| WARN | Possivel multi-user detectado | Telegram com grupo + DM |
| INFO | 0 criticos | OK |

### 13.2 Medidas de seguranca ativas

- **Gateway bind loopback:** So aceita conexoes de 127.0.0.1
- **Telegram allowlist:** Apenas ID `<TELEGRAM_USER_ID>` pode enviar DMs
- **Grupos require mention:** Em grupos, so responde quando mencionado
- **Token auth:** Gateway requer token para conexao
- **Device pairing:** Novos devices precisam ser pareados
- **Ed25519 keypair:** Identidade criptografica do device
- **Config audit trail:** Toda mudanca no config e logada em `logs/config-audit.jsonl`
- **Config health:** Ultimo snapshot saudavel salvo em `logs/config-health.json`
- **Exec como usuario:** Roda como `bernard`, nao root

### 13.3 PRD de Security Hardening (planejado)

**Arquivo:** `media/inbound/security-hardening---*.md`

8 tarefas planejadas:

1. Telegram Allowlist (feito)
2. Firewall UFW (pendente)
3. Fail2ban para SSH (pendente)
4. Cloudflare Tunnel para acesso remoto (pendente)
5. Bind de portas em 127.0.0.1 (feito para gateway)
6. SSH Hardening (pendente)
7. Auditar credenciais hardcoded (em progresso)
8. Sync systemd + .env (pendente)

### 13.4 Credenciais no sistema

| Credencial | Onde | Tipo |
|---|---|---|
| Gateway token | `openclaw.json` | Token compartilhado |
| Telegram bot token | `openclaw.json` | API token |
| OpenAI OAuth tokens | `auth-profiles.json` | JWT + refresh |
| OpenRouter API key | `auth-profiles.json` + `models.json` | API key |
| Device operator tokens | `paired.json` + `device-auth.json` | Tokens internos |
| Exec approvals socket token | `exec-approvals.json` | Token IPC |
| Device Ed25519 private key | `identity/device.json` | Chave privada |

**Nota:** Credenciais estao em arquivos JSON com permissao `600` (apenas owner). O PRD de hardening planeja mover API keys para `.env` e nunca hardcodar em JSON.

---

## 14. Manutencao e Troubleshooting

### 14.1 Atualizacao

```bash
# Verificar updates
openclaw update check

# Atualizar
openclaw update apply

# Canal atual
openclaw status | grep Channel
```

Canal atual: `stable`. Update disponivel: 2026.4.9.

### 14.2 Backup

```bash
# Criar backup
openclaw backup create

# Verificar backup
openclaw backup verify
```

**Regra operacional:** Sempre fazer backup antes de mudancas estruturais.

### 14.3 Reset

```bash
# Reset completo (mantem CLI)
openclaw reset

# Desinstalar
openclaw uninstall
```

### 14.4 Troubleshooting comum

#### Agente so responde texto, nao executa nada

**Causa:** Device `gateway-client` sem scope `operator.approvals`.

**Diagnostico:**
```bash
# Verificar logs
tail -f /tmp/openclaw/openclaw-$(date +%Y-%m-%d).log | grep "pairing required"

# Verificar scopes do device
cat ~/.openclaw/devices/paired.json | python3 -m json.tool
```

**Solucao:** Parar gateway, editar `paired.json` para incluir todos os scopes no device `gateway-client`, reiniciar.

#### Gateway unreachable

**Diagnostico:**
```bash
openclaw gateway status
systemctl --user status openclaw-gateway
```

**Solucao:** Geralmente e tempo de inicializacao (~5-10s). Se persistir, verificar se a porta 18789 esta livre.

#### Telegram nao responde

**Diagnostico:**
```bash
openclaw status  # Verificar canal Telegram
tail -f /tmp/openclaw/openclaw-$(date +%Y-%m-%d).log | grep telegram
```

**Verificar:** Bot token valido, allowlist correta, polling ativo.

#### Modelo retorna erro

**Diagnostico:**
```bash
openclaw models  # Ver auth status e usage
```

**Verificar:** Tokens OAuth expirados (renovar com `openclaw models auth login --provider openai-codex`), rate limits, API key valida.

### 14.5 Comandos uteis

```bash
# Status completo
openclaw status

# Status com probes profundos
openclaw status --deep

# Modelos disponiveis
openclaw models list --all

# Skills disponiveis
openclaw skills list

# Sessoes ativas
openclaw sessions list

# Logs ao vivo
openclaw logs --follow

# Audit de seguranca
openclaw security audit
openclaw security audit --deep

# TUI interativa
openclaw tui
```

### 14.6 Arquivos de configuracao criticos

Em ordem de importancia para recuperacao:

1. `openclaw.json` - Config principal (backups em `*.bak*`)
2. `agents/main/agent/auth-profiles.json` - Tokens de autenticacao
3. `devices/paired.json` - Devices e scopes
4. `exec-approvals.json` - Politicas de execucao
5. `identity/device.json` - Keypair do device
6. `workspace/` - Todo o workspace do agente (identidade, memoria, regras)

**Backups existentes do config:**
- `openclaw.json.bak`
- `openclaw.json.bak.1` ate `.bak.4`
- `openclaw.json.bak.pre-denycommands-clean`
- `openclaw.json.bak.pre-hardening`
- `openclaw.json.bak.pre-hardening2`

---

## Apendice A: Historico de Mudancas Relevantes

| Data | Mudanca | Motivacao |
|---|---|---|
| 2026-04-08 11:21 | Onboarding inicial | Setup do OpenClaw |
| 2026-04-08 11:23 | Wizard concluido | Configuracao base completa |
| 2026-04-08 11:34 | Login OpenAI Codex | Autenticacao OAuth |
| 2026-04-08 11:35 | Modelo gpt-5.4 definido | Modelo primario |
| 2026-04-08 ~15:44 | Fix scopes gateway-client | Agente nao executava tools (so tinha operator.read) |
| 2026-04-08 ~18:46 | OpenRouter configurado | API key + plugin habilitado |
| 2026-04-08 ~21:54 | Workspace setup completo | Todos os boot files criados pelo Vox |
| 2026-04-08 ~23:54 | Exec approvals: full/off | Habilitar execucao de shell |
| 2026-04-09 ~02:49 | Fallbacks configurados | healer-alpha + hunter-alpha |
| 2026-04-09 ~02:57 | Plugins adicionais | qwen, deepseek, google habilitados |

---

## Apendice B: Sessoes Ativas

| Chave | Tipo | Modelo | Uso | Cache |
|---|---|---|---|---|
| `agent:main:main` | Direct (CLI/dashboard) | gpt-5.4 | 23k/272k (8%) | 50% |
| `agent:main:telegram:direct:7593...` | DM Telegram | gpt-5.4 | 61k/272k (23%) | 99% |
| `agent:main:telegram:group:-1003...` | Grupo Telegram | gpt-5.4 | 22k/272k (8%) | 68% |

---

*Documento gerado em 2026-04-09 com base na exploracao completa do diretorio `~/.openclaw/` e saidas dos comandos `openclaw status`, `openclaw models`, `openclaw plugins list`, `openclaw skills list`, `openclaw gateway status` e `systemctl --user status openclaw-gateway`.*
