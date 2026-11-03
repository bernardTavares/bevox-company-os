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

Question vai pro tópico `clarifications` (se `telegram.topics.clarifications` presente em `projects-meta.json`).

Mensagem inclui `task_id`, `clarification_id`, pergunta completa, e instrução de resposta com formato explícito.

## Como Bernard responde

3 caminhos equivalentes, todos servidos pelo plugin `clarification-commands` no gateway:

1. **Swipe-reply** — reply direto na mensagem da clarification (Telegram correlaciona via `reply_to_message_id`)
2. **Slash command** — `/clr_override T-XXXX-clr-N <resposta>` (útil quando swipe-reply não foi possível)
3. **CLI manual** — `~/.openclaw/clarification-agent/cli.sh answer <cid> --answer "..."` (fallback)

Eu não preciso saber qual caminho o Bernard usou — todos resultam no mesmo answer file e desbloqueio da task. O efeito é observável via `cli.sh list --project {{SLUG}} --open` (deve sumir da lista) e via status do task no kanban (`blocked=False`).

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
