#!/bin/bash
# Extrai decisões do arquivo de sessão mais recente
set -e

WORKSPACE="$HOME/.openclaw/workspace"
SESSIONS_DIR="$WORKSPACE/memory/sessions"
DECISIONS_FILE="$WORKSPACE/memory/context/decisions.md"
LESSONS_FILE="$WORKSPACE/memory/context/lessons.md"

# Encontrar arquivo mais recente
LATEST_FILE=$(ls -t "$SESSIONS_DIR"/*.md 2>/dev/null | head -1)

if [ -z "$LATEST_FILE" ] || [ ! -f "$LATEST_FILE" ]; then
    echo "❌ Nenhum arquivo de sessão encontrado em $SESSIONS_DIR"
    exit 1
fi

echo "📄 Processando: $(basename "$LATEST_FILE")"

# Extrair decisões (padrões simples)
echo -e "\n## $(date '+%Y-%m-%d') - Extraído automaticamente" >> "$DECISIONS_FILE"
grep -i -E "(decisão|✓|•|importante|próximo passo|definir|escolher)" "$LATEST_FILE" | head -3 | while read line; do
    echo "- $line" >> "$DECISIONS_FILE"
done

# Extrair lições (padrões simples)
echo -e "\n## $(date '+%Y-%m-%d') - Extraído automaticamente" >> "$LESSONS_FILE"
grep -i -E "(lição|aprendi|percebi|nota|observação)" "$LATEST_FILE" | head -2 | while read line; do
    echo "- $line" >> "$LESSONS_FILE"
done

echo "✅ Extração concluída:"
echo "   Decisões: $(tail -5 "$DECISIONS_FILE" | grep -c "^-") adicionadas"
echo "   Lições: $(tail -5 "$LESSONS_FILE" | grep -c "^-") adicionadas"