# Integrações disponíveis

> Índice das integrações mapeadas para este workspace. Cada integração tem
> um doc próprio com escopo, CLI, lifecycle e padrões de uso.

## Hub dispatch (5 agentes externos)

- [dispatcher.md](dispatcher.md) — dispara próxima task `ready` (Claude Code background detached); auto-invoca tester em modo foreground
- [scrum-master.md](scrum-master.md) — converte plans em tasks no kanban via proposal/accept loop
- [clarification.md](clarification.md) — canal pra pedir input humano quando bloqueado
- [tester.md](tester.md) — gate de validação operacional pra tasks em `testing` (5 invariantes + LLM check por AC)
- [kanban.md](kanban.md) — backlog per-project (schema v4, sprints `current`/`next`)

## Skills e serviços

- [knowledge-sync.md](knowledge-sync.md) — skill local pra sincronizar com `bevox-knowledge` (source of truth canônica)
- [mcp.md](mcp.md) — MCP servers disponíveis (codegraph, telegram, drive); pré-requisitos e quando NÃO usar
- [telegram-bot.md](telegram-bot.md) — bot Telegram per-project (postar status, ler comandos, integração com tópicos)
- [mission-control.md](mission-control.md) — UI dashboard do OpenClaw em http://localhost:3000 (projetos, sprints, kanban, files)
- [gh-cli.md](gh-cli.md) — `gh` CLI pra PRs, issues, repos no GitHub

## Quando adicionar nova integração

Adicionar arquivo aqui quando:
- Uma ferramenta/serviço externo passa a ser usado de forma recorrente neste projeto
- Há um padrão de uso que vai além de "leia o man page"
- Outros agentes / sessões futuras vão precisar do contexto pra operar bem

Cada doc novo deve incluir: propósito, pré-requisitos, CLI cheatsheet (se houver), lifecycle/estado, anti-patterns.
