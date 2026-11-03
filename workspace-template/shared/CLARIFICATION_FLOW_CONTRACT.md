# CLARIFICATION_FLOW_CONTRACT.md

> Contrato para qualquer agente presente ou futuro que abra clarifications para humanos.

## Regra central

Nenhum agente pode depender de "reply no chat" como mecanismo implícito.

Para um fluxo de clarification ser considerado válido, ele precisa ter:
- identificador opaco da clarification, por exemplo `T-0105-clr-1`
- mensagem enviada ao humano com esse ID visível
- caminho de ingestão real da resposta
- mudança de estado observável após ingestão
- fallback manual documentado

## Formato mínimo da mensagem ao humano

Toda clarification deve incluir:
- `task_id`
- `clarification_id`
- pergunta objetiva
- instrução de resposta com formato explícito
- fallback manual verificável

Exemplo aceitável:
- responda neste tópico citando `T-0105-clr-1`
- formato recomendado: swipe-reply na mensagem OU `T-0105-clr-1: Opção C`
- fallback: `cli.sh answer T-0105-clr-1 --answer "..."`

## Proibição

É proibido usar frases como:
- "o sistema processará automaticamente"
- "basta responder aqui"
- "isso destrava sozinho"

sem que exista ingestão implementada, testada e com evidência observável.

## Caminhos de ingestão canônicos (Telegram)

Reply de clarification em projetos conectados a Telegram tem **3 caminhos equivalentes**, todos servidos pelo plugin `clarification-commands` rodando no gateway do bot:

1. **Swipe-reply** — humano dá reply direto na mensagem da clarification. Plugin correlaciona via `reply_to_message_id` lookup em `notifier-state.json` schema v2.
2. **Slash command** — `/clr_override T-XXXX-clr-N <resposta>` ou `/clr_answer T-XXXX-clr-N <resposta>`. Útil quando humano viu a mensagem em outro contexto e não pode dar swipe-reply.
3. **CLI manual** — `~/.openclaw/clarification-agent/cli.sh answer <cid> --answer "..."`. Fallback verificável; sempre disponível.

Os 3 caminhos produzem o mesmo efeito observável: answer file gravado em `clarification-agent/answers/<cid>.md`, escalation removida (se havia), task desbloqueada, evento auditável emitido.

**Agente nunca implementa polling Telegram em código próprio.** Polling é responsabilidade exclusiva do plugin do gateway.

## Pré-condições do canal Telegram

Para os 3 caminhos acima funcionarem em um projeto, é necessário:

1. `init_telegram_topics.py --slug <project>` rodado — cria tópicos `clarifications` e `dispatcher`, popula `projects-meta.json:projects.<slug>.telegram.topics`
2. Plugin `clarification-commands` instalado no perfil do gateway daquele bot (default no `bootstrap-telegram-agent.sh`)
3. Gateway systemd unit ativo: `openclaw-telegram-gateway-<profile>.service`

Sem essas 3 condições, swipe-reply e slash command não funcionam — só o CLI manual continua disponível.

## SoT da clarification

`~/.openclaw/clarification-agent/notifier-state.json` schema v2 é a fonte canônica. Cada entry carrega:
- `token_alias` (qual bot enviou a question — usado pra rotear confirmação no MESMO bot)
- `chat_id`, `thread_id`, `message_id` (correlação Telegram)
- `clarification_id`, `task_id` (correlação OpenClaw)

Plugin usa esses campos pra cross-validar replies (rejeita reply de bot/chat errado).

## Requisitos de implementação (para novos canais ou agentes futuros)

Se for adicionar ingestão por outro canal, ela deve:
- correlacionar a resposta com `clarification_id` (preferido) ou identificador equivalente do canal
- persistir metadados da mensagem enviada ao humano (mínimo: identificador único da mensagem + clarification_id)
- registrar answer em storage durável (`clarification-agent/answers/<cid>.md`)
- limpar escalation pendente
- emitir evento auditável

## Guardrail de payload

Tasks que participam do fluxo devem carregar payload mínimo consistente.
No caso de tasks operacionais do kanban:
- `dispatch_payload.spec_refs` deve existir como lista canônica
- `dispatch_payload.spec_ref` deve existir como o primeiro item canônico

Campos críticos não devem depender de inferência tardia se puderem ser produzidos deterministicamente na origem.

## Princípio final

Notificação sem ingestão observável não é automação. É só mensagem.
