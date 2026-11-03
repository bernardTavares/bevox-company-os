# Integration: knowledge-sync

> Skill local em `~/.openclaw/skills/knowledge-sync/` que opera o
> `bevox-knowledge` como fonte única de verdade ativa do Company OS.
> Spec canônica: `bevox-knowledge/35_specs/2026-04-09-e1-knowledge-spine.md`.

## Quando usar

Acionar a skill quando Bernard pedir:
- "qual o estado do bevox-knowledge?" / "tem algo pendente?"
- "tem mudanças locais no knowledge?" / "working tree limpa?"
- "commitar as mudanças" / "fazer push" / "pull do remote"
- "criar branch draft" / "criar ADR" / "aceitar ADR"
- "snapshot do knowledge" / "backup" / "restaurar"
- "health do knowledge" / "status do repo"
- "eventos recentes" / "histórico de sync"

## NÃO usar para

- Edição livre fora de `bevox-knowledge`
- Trabalho de coding em outros repos
- Configuração do OpenClaw em si

## Componentes

### Watcher (read-only)

Observa o clone, deriva estado, persiste em `state.json`. **Nunca muta.**
Ciclo: `git fetch` (rate-limited) → branch/ahead/behind → working tree →
operações pendentes (MERGE_HEAD/REBASE_HEAD) → branches `draft/*` →
detecção conservadora de conflito → health (ok/degraded/critical).

### Actions (mutations)

Cada ação é atômica e respeita ADR-006. Princípios hard:
- `pull-ff` é a ÚNICA forma de pull (nunca `git pull` direto)
- Nenhum `git merge` automático em conteúdo canônico
- `canonical commit/push/create-marker` exigem **approval explícito** mesmo em L4
- `draft commit/push` são **auto** em L4
- Operações destrutivas (`reset --hard`, force push, merge, rebase, cherry-pick)
  **NÃO** estão no catálogo

### Notifications

Detecta mudança relevante de estado comparando `state.json` vs
`state.previous.json`. Política de severidade/persistência/dedup.
Telegram como canal principal.

## Comandos comuns

```bash
# Estado operacional completo
cat ~/.openclaw/knowledge-sync/state.json | jq .

# Health summary
cat ~/.openclaw/knowledge-sync/state.json | jq .health

# Rodar watcher (atualiza state.json)
SKILL_DIR=~/.openclaw/skills/knowledge-sync
bash -c "
  source '$SKILL_DIR/lib/common.sh'
  source '$SKILL_DIR/lib/state.sh'
  source '$SKILL_DIR/lib/events.sh'
  source '$SKILL_DIR/lib/git-ops.sh'
  source '$SKILL_DIR/lib/watcher.sh'
  ks_watcher_run fetch
  ks_state_read | jq .
"
```

## Como eu uso

Antes de propor mudança canônica em `bevox-knowledge`:
1. Rodar watcher pra confirmar working tree limpa + sync OK
2. Criar branch `draft/<feature>` se mudança ainda em rascunho
3. Pra mudança canônica em `main`: pedir approval explícito ao Bernard
4. Nunca empurrar canônico silenciosamente
