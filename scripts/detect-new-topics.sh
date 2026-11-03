#!/bin/bash
# detect-new-topics.sh - Detecta quando BevoxBot é adicionado a novo tópico e solicita contexto
# Executar a cada 5 min via cron

set -euo pipefail

KNOWN_SESSIONS_FILE="$HOME/.openclaw/scripts/known-sessions.txt"
OPENCLAW_CLI="openclaw"

# Ensure known sessions file exists
if [ ! -f "$KNOWN_SESSIONS_FILE" ]; then
    echo "# Known sessions - auto-managed" > "$KNOWN_SESSIONS_FILE"
    # Populate with current sessions
    $OPENCLAW sessions list --json 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for session in data.get('sessions', []):
        print(session['key'])
except:
    pass
" >> "$KNOWN_SESSIONS_FILE"
    exit 0
fi

# Get current sessions
CURRENT_SESSIONS=$($OPENCLAW sessions list --json 2>/dev/null || echo '{"sessions": []}')

# Extract session keys
NEW_SESSIONS=$(echo "$CURRENT_SESSIONS" | python3 -c "
import sys, json

# Load known sessions
known = set()
try:
    with open('$KNOWN_SESSIONS_FILE', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                known.add(line)
except:
    pass

# Load current sessions
data = json.load(sys.stdin)
current = [s['key'] for s in data.get('sessions', [])]

# Find new sessions
new = [s for s in current if s not in known]
for s in new:
    print(s)
" 2>/dev/null)

if [ -z "$NEW_SESSIONS" ]; then
    exit 0  # No new sessions
fi

# For each new session, trigger onboarding
for SESSION_KEY in $NEW_SESSIONS; do
    echo "🆕 Novo tópico detectado: $SESSION_KEY"
    
    # Extract channel info from session key
    # Format: agent:main:telegram:group:<group_id>:topic:<topic_id>
    # or: agent:main:telegram:direct:<user_id>
    
    if echo "$SESSION_KEY" | grep -q "telegram:group"; then
        # This is a group topic
        GROUP_INFO=$(echo "$SESSION_KEY" | sed 's/.*telegram:group:\([^:]*\):topic:\(.*\)/Group: \1, Topic: \2/')
        
        # Send onboarding message to this session
        $OPENCLAW sessions send \
            --session-key "$SESSION_KEY" \
            --message "👋 Olá Bernard! Detectei que fui adicionado a este novo tópico.

**Para eu operar bem aqui, me conte:**
- Qual é o propósito deste tópico?
- Que tipo de discussões/conteúdo vai rolar aqui?
- Há algum contexto importante que eu deva saber?

Assim que você me der esse contexto, vou adaptarm eu comportamento para este espaço." \
            2>/dev/null || echo "⚠️ Falha ao enviar mensagem para $SESSION_KEY"
        
        # Add to known sessions
        echo "$SESSION_KEY" >> "$KNOWN_SESSIONS_FILE"
        
        echo "✅ Onboarding enviado para $SESSION_KEY"
    fi
done

echo "✅ Detecção de novos tópicos concluída"
