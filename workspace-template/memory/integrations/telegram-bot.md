# Integration: Telegram bot (per-project)

> Cada projeto OpenClaw pode ter seu próprio bot Telegram conectado a um
> grupo/supergrupo. O bot é configurado via Mission Control ("Connect bot")
> ou via script de bootstrap.

## Pré-requisitos

- Bot criado via @BotFather (token salvo em env `BOT_TOKEN_VOZ_<UPPER_SLUG>`,
  onde `<UPPER_SLUG>` é o slug do projeto em uppercase — ex: slug `voz-acme`
  vira `BOT_TOKEN_VOZ_VOZ_ACME`)
- Bot adicionado ao grupo Telegram pelo Bernard, com permissão admin
  (mínimo: `manage_topics` se grupo é fórum)
- Entry em `~/.openclaw/projects-meta.json` com `bot_id`, `bot_username`,
  `bot_port`, `telegram.chat_id`

## Como verificar se já está conectado

```bash
python3 -c "
import json
m = json.load(open('~/.openclaw/projects-meta.json'))
e = m['projects'].get('{{SLUG}}', {})
print('bot_id:', e.get('bot_id'))
print('bot_username:', e.get('bot_username'))
print('telegram:', e.get('telegram'))
"
```

## Bootstrap automatizado

Pra criar/conectar novo bot:

```bash
~/.openclaw/scripts/bootstrap-telegram-agent.sh \
    --token "$BOT_TOKEN" \
    --chat-id "$CHAT_ID" \
    --allow-from "user1,user2" \
    --skills "knowledge-sync-commands,clarification-commands" \
    --non-interactive --json \
    {{SLUG}} <port>
```

Output: 1 linha JSON com confirmação + (opcional) systemd unit habilitado.

## Tópicos canônicos do grupo

Quando o grupo é fórum, são criados tópicos:

- `clarifications` — clarification-agent posta perguntas e recebe respostas
- `dispatcher` — dispatcher-agent posta `task_done` / `task_failed`
- `general` (default Telegram)

`message_thread_id` por tópico fica em `projects-meta.json:
telegram.topics`. Iniciados via Mission Control (botão "Initialize topics"
na seção Telegram da Geral tab) ou via:

```bash
python3 ~/.openclaw/scripts/init_telegram_topics.py --slug {{SLUG}}
```

## Como o agente posta no tópico certo

```python
# Padrão usado por clarification-agent / dispatcher-agent notifiers
import json
meta = json.load(open("~/.openclaw/projects-meta.json"))
entry = meta["projects"]["{{SLUG}}"]
chat_id = entry["telegram"]["chat_id"]
thread_id = entry["telegram"].get("topics", {}).get("clarifications")  # ou "dispatcher"

payload = {"chat_id": chat_id, "text": "..."}
if thread_id:
    payload["message_thread_id"] = thread_id
# enviar via Bot API (requests.post a https://api.telegram.org/bot$TOKEN/sendMessage)
```

Sem `topics`, fallback é o tópico general.

## Pré-condições para clarification reply

Para reply de clarification funcionar via plugin (3 caminhos: swipe-reply, `/clr_override`, CLI manual), o projeto precisa:

1. `init_telegram_topics.py --slug {{SLUG}}` rodado — cria tópicos `clarifications` e `dispatcher`
2. Plugin `clarification-commands` instalado no perfil do gateway (default no bootstrap acima)
3. Gateway systemd unit ativo: `openclaw-telegram-gateway-<profile>.service`

Sem isso, só o CLI manual continua disponível como caminho de reply.

## Anti-patterns

- NÃO postar mensagens no general quando há tópico canônico configurado
  (polui canal principal de Bernard)
- NÃO criar tópicos novos pelo bot fora do escopo canônico (clarifications,
  dispatcher) — primeiro discutir com Bernard
- NÃO logar mensagens recebidas em arquivo committable (privacidade)
- NÃO implementar polling Telegram em código de agente — polling é responsabilidade
  exclusiva do plugin do gateway (vide `shared/CLARIFICATION_FLOW_CONTRACT.md`)
