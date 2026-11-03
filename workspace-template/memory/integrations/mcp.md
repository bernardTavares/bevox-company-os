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

**Pré-requisito:** bot conectado ao projeto (ver `telegram-bot.md`). Se
`projects-meta.json:projects.{{SLUG}}.bot_id` é null, MCP telegram não
funciona — primeiro conectar via Mission Control ou bootstrap script.

## Drive (Google)

Acesso a docs/sheets se autenticado. Use pra ler PRDs/specs externas
que ainda não foram trazidas pro `bevox-knowledge`.

**Pré-requisito:** OAuth concluído. Se primeira vez na sessão, chamar
`mcp__claude_ai_Google_Drive__authenticate` antes de qualquer operação.
Se token expirou, repetir auth.

## Como descobrir MCPs disponíveis nesta sessão

A lista de MCP servers e suas tools varia por sessão (configurada em
`~/.claude/mcp.json` global ou no projeto). Pra descobrir:

```bash
# Lista todas tools deferred (inclui MCPs)
# Use ToolSearch tool com query "mcp" pra ver candidatos
```

Tools de MCP têm prefixo `mcp__<server>__<tool>`. Ex:
`mcp__codegraph__codegraph_search`, `mcp__claude_ai_Google_Drive__authenticate`.

## Quando NÃO usar MCP

- Operações simples de file/grep — use Read/Bash diretamente
- Investigações de 1-3 queries — Bash é mais rápido e barato
- Edição — use Edit tool, não MCP

## Adicionar MCP server novo

Edita `~/.claude/mcp.json` global ou `~/.claude/projects/<dir>/mcp.json`
local. Reinicia Claude Code session pra carregar.
