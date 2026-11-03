# OH wave-7 Self-Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preparar artefatos sintéticos em `~/.openclaw/self-test-evidence/` para Bernard disparar self-test end-to-end (Telegram bevox-mobile → scrum-master-v2 → kanban → dispatcher → clarification-agent → tester → done) do bloco Operational Loop Hardening; observar resultado; executar closure commit + push das 4 branches condicional ao PASS.

**Architecture:** Wave-7 é preparação + execução observada + closure. Não é código novo. Artefatos sintéticos ficam isolados em `~/.openclaw/self-test-evidence/` (runtime descartável, fora do bevox-knowledge — evita sujeira documental). Spec sintética tem shape implementation plan convencional (writing-plans) com 2 tasks + `**Depends:** Task 1.1` em Task 2.1 para exercitar wave-5 blocked_by + wave-6 scrum-master-v2. Tasks criam arquivos evidenciais em `artifacts/`. Teardown archive tasks + snapshot events em `evidence/` + remove opt-in cron. Bernard dispara via Telegram natural → dogfooding puro (spec §1.2 "pipeline completo sem intervenção humana").

**Tech Stack:** Shell stdlib (bash), jq para JSON, markdown para spec. Zero código novo. Exercita: scrum-master-agent CLI (wave-6), kanban-tasks CLI (wave-4/5 gates + hooks), cron-dispatcher (pre-OH), clarification-agent (wave-1), telegram notifier (wave-2), bevox-mobile agent (routing), tester-agent + reaper (pre-OH).

**Spec canônica:** `bevox-knowledge/35_specs/2026-04-21-e10-scrum-master-self-test.md`
**ADR governante:** `bevox-knowledge/30_adr/ADR-009-clarification-loop-unified-local-first.md`
**Bloco narrativo:** Operational Loop Hardening 2026-04-21 (wave-7 de 8, ÚLTIMA)
**Artefatos runtime:** `~/.openclaw/self-test-evidence/` (NÃO git-tracked, descartável)
**Branch draft bevox-knowledge:** `draft/adr-009-clarification-daemon` (closure commit aqui)

**Ajustes pós-spec (refinados com Bernard 2026-04-22):**
1. **Spec do self-test é UMA** (não 7 plans como spec §3.2). Exercita happy path + blocked_by num único plan (2 tasks). Cobre cenários §4.1, §4.2 (se clarification ocorrer), §4.5 (blocked_by ordering).
2. **Artefatos fora do bevox-knowledge.** Spec sintética vive em `~/.openclaw/self-test-evidence/specs/` (runtime). Bevox-knowledge SÓ recebe release note + tracker closure PÓS-PASS — zero poluição documental.
3. **Projeto `test-project`** (existente) usado. Temporariamente adicionado ao `cron-projects.txt` via Task 6; teardown remove.
4. **Drafter modelo real: `qwen2.5-coder:14b`** (não `qwen3:14b-64k` que spec §4.3 menciona — wave-1 empirical rejeitou qwen3).
5. **Cenários unsafe (§4.3 + §4.6)** não fazem parte desta execução. Wave-2 live smoke 2026-04-22T09:58Z JÁ validou Telegram push end-to-end (3 msg_id 229/230/231). Re-validar sintético aqui é redundante. Se wave-7 auto PASS → bloco PASS.
6. **Dogfooding via Telegram natural** — Bernard dispara via topic `bevox-mobile`, agent processa + invoca scrum-master CLI. Exercita gateway + telegram + bevox-mobile + scrum-master + dispatcher em fluxo real.
7. **Push das 4 branches é CONDICIONAL** e explícito — Bernard confirma após PASS reportado; eu não pusho automaticamente.

---

## File Structure

**Arquivos a criar (runtime `~/.openclaw/self-test-evidence/`, NÃO git):**
- `~/.openclaw/self-test-evidence/README.md` — instruções Bernard (disparo + observação + PASS criteria + teardown)
- `~/.openclaw/self-test-evidence/specs/2026-04-22-self-test-sidecar.md` — spec sintética (2 tasks TDD shape + `**Depends:** Task 1.1`)
- `~/.openclaw/self-test-evidence/preflight.sh` — checklist pre-execução
- `~/.openclaw/self-test-evidence/teardown.sh` — archive tasks + snapshot events + remove opt-in
- `~/.openclaw/self-test-evidence/artifacts/.gitkeep` — onde tasks gravam (mkdir)
- `~/.openclaw/self-test-evidence/evidence/.gitkeep` — onde snapshots ficam (mkdir)

**Arquivos a modificar (runtime, temp):**
- `~/.openclaw/dispatcher-agent/cron-projects.txt` — adicionar linha `test-project` (comment indicando self-test; removido no teardown)

**Arquivos a criar PÓS-PASS (bevox-knowledge draft branch):**
- `50_releases/2026-04-22-operational-loop-hardening-closed.md` — release note bloco OH CLOSED
- Modificar `40_roadmap/delivery-tracker.yml` — entry `wave-7-self-test` delivered + `OH-closure` delivered
- Modificar `40_roadmap/2026-04-09-openclaw-company-os-roadmap.md` — seção "Operational Loop Hardening CLOSED"
- Modificar `35_specs/2026-04-21-e10-scrum-master-self-test.md` — status draft → delivered

**Git push PÓS-PASS (explícito Bernard go-ahead):**
- `bevox-knowledge/draft/adr-009-clarification-daemon` → `main`
- `knowledge-sync/feat/e10-clarification-commands-plugin` → `main`
- `mission-control/feat/e10-payload-completeness-gate` → `main`
- `mission-control/feat/e5-f4-kanban-blocked-by-schema` → `main`

---

## Phase 0 — Prep artefatos

### Task 1: Criar estrutura de diretórios em `~/.openclaw/self-test-evidence/`

**Files:**
- Create dirs: `~/.openclaw/self-test-evidence/{specs,artifacts,evidence}/`

- [ ] **Step 1: mkdir tree**

```bash
mkdir -p ~/.openclaw/self-test-evidence/specs
mkdir -p ~/.openclaw/self-test-evidence/artifacts
mkdir -p ~/.openclaw/self-test-evidence/evidence
ls -la ~/.openclaw/self-test-evidence/
```

Expected: 3 subdirs + dir `self-test-evidence/` root.

- [ ] **Step 2: Sanity — nenhuma contaminação** em runtime real

```bash
ls ~/.openclaw/self-test-evidence/artifacts/ ~/.openclaw/self-test-evidence/evidence/
```

Expected: ambos vazios.

- [ ] **Step 3: Nenhum commit** (runtime não git).

### Task 2: Escrever spec sintética (2 tasks + blocked_by)

**Files:**
- Create: `~/.openclaw/self-test-evidence/specs/2026-04-22-self-test-sidecar.md`

- [ ] **Step 1: Escrever spec sintética com shape implementation plan**

Conteúdo exato:

```markdown
# Self-Test Evidence Sidecar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exercitar end-to-end o bloco OH (scrum-master-v2 → kanban gate+blocked_by → dispatcher → clarification-agent → tester) criando 2 arquivos evidenciais em `~/.openclaw/self-test-evidence/artifacts/` com dependência explícita entre eles.

**Architecture:** 2 tasks atômicas em 1 phase. Task 1.1 cria arquivo A com timestamp ISO. Task 2.1 (`**Depends:** Task 1.1`) cria arquivo B contendo conteúdo de A + linha `depends_resolved=true`. Exercita: scrum-master-v2 popula blocked_by via override; wave-4 gate aceita payload com spec_ref + AC; wave-5 mantém B blocked até A done + auto-release após A done; tester valida AC e transita done.

**Tech Stack:** Shell stdlib (bash + date + cat). Zero dependências externas.

**Epico:** E10/OH/wave-7-self-test

**Project:** test-project

**Specs:** `~/.openclaw/self-test-evidence/specs/2026-04-22-self-test-sidecar.md`

---

## File Structure

**Arquivos a criar:**
- `~/.openclaw/self-test-evidence/artifacts/_a-<timestamp>.md` — evidência task 1.1
- `~/.openclaw/self-test-evidence/artifacts/_b-<timestamp>.md` — evidência task 2.1 (depende de _a)

**Formato timestamp:** ISO 8601 UTC com Z (ex: `2026-04-22T12:00:00Z`), gerado via `date -u +%Y-%m-%dT%H:%M:%SZ`.

---

## Phase 1: Evidence sidecars

### Task 1.1: Criar arquivo A com timestamp

**Files:**
- Create: `~/.openclaw/self-test-evidence/artifacts/_a-<timestamp>.md`

- [ ] **Step 1: Gerar timestamp UTC + criar arquivo A**

```bash
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
ARTIFACTS=~/.openclaw/self-test-evidence/artifacts
mkdir -p "$ARTIFACTS"
cat > "$ARTIFACTS/_a-${TS}.md" <<EOF
# Self-test evidence A

timestamp=${TS}
source_task=Task 1.1 Self-Test Sidecar
EOF
ls "$ARTIFACTS"/_a-*.md
```

Expected: 1 arquivo criado tipo `_a-2026-04-22T12:00:00Z.md`.

- [ ] **Step 2: Verificar conteúdo**

```bash
cat "$ARTIFACTS"/_a-*.md | head -5
```

Expected: header `# Self-test evidence A` + linha `timestamp=<iso>` + linha `source_task=Task 1.1 Self-Test Sidecar`.

Expected: arquivo existe, `timestamp=` presente, source_task="Task 1.1 Self-Test Sidecar" presente.

### Task 2.1: Criar arquivo B herdando A

**Files:**
- Create: `~/.openclaw/self-test-evidence/artifacts/_b-<timestamp>.md`

**Depends:** Task 1.1

- [ ] **Step 1: Ler A mais recente + compor B**

```bash
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
ARTIFACTS=~/.openclaw/self-test-evidence/artifacts
A_FILE=$(ls -t "$ARTIFACTS"/_a-*.md | head -1)
if [ -z "$A_FILE" ]; then
  echo "FAIL: Task 1.1 arquivo A não encontrado"
  exit 1
fi
cat > "$ARTIFACTS/_b-${TS}.md" <<EOF
# Self-test evidence B

$(cat "$A_FILE")

---

depends_resolved=true
timestamp_b=${TS}
source_task=Task 2.1 Self-Test Sidecar
depends_from=$A_FILE
EOF
ls "$ARTIFACTS"/_b-*.md
```

Expected: 1 arquivo `_b-<ts>.md` criado contendo conteúdo de A + linha `depends_resolved=true`.

- [ ] **Step 2: Verificar conteúdo**

```bash
cat "$ARTIFACTS"/_b-*.md
```

Expected: conteúdo de A replicado + separador `---` + linhas `depends_resolved=true`, `timestamp_b=<iso>`, `source_task=Task 2.1 Self-Test Sidecar`, `depends_from=<path>`.

Expected: arquivo existe, `depends_resolved=true` presente, `timestamp=` herdado de A presente, `source_task=Task 2.1 Self-Test Sidecar` presente.
```

- [ ] **Step 2: Sanity — spec parseia com parser scrum-master**

```bash
python3 -c "
import sys
sys.path.insert(0, '~/.openclaw/scrum-master-agent')
from lib import parser
text = open('~/.openclaw/self-test-evidence/specs/2026-04-22-self-test-sidecar.md').read()
summary = parser.parse_plan_summary(text)
print('tasks:', [f'{t[\"phase_num\"]}.{t[\"task_num\"]}: {t[\"task_subject\"]}' for t in summary['tasks']])
print('task 2.1 depends:', parser.extract_depends(summary['tasks'][1]['body']))
"
```

Expected: `tasks: ['1.1: Criar arquivo A com timestamp', '2.1: Criar arquivo B herdando A']` + `task 2.1 depends: ['Task 1.1']`.

- [ ] **Step 3: Nenhum commit**.

### Task 3: Escrever `preflight.sh`

**Files:**
- Create: `~/.openclaw/self-test-evidence/preflight.sh`

- [ ] **Step 1: Criar script executável**

```bash
cat > ~/.openclaw/self-test-evidence/preflight.sh <<'SH'
#!/bin/bash
# Preflight: verifica prerequisites antes de disparar self-test wave-7 OH.
#
# Exit 0 = ready. Exit 1 = algum prereq falhou; mensagem indica qual.

set -uo pipefail

PASS=0
FAIL=0
FAILED=()

_ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
_fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); FAILED+=("$1"); }

echo "=== wave-7 OH self-test PREFLIGHT ==="
echo ""

# 1. ollama up + modelo qwen2.5-coder:14b pullado
if systemctl --user is-active ollama.service >/dev/null 2>&1 || pgrep -x ollama >/dev/null 2>&1; then
  _ok "ollama process up"
else
  _fail "ollama nao esta rodando (systemd user OR pgrep)"
fi

if command -v ollama >/dev/null 2>&1 && ollama list 2>/dev/null | grep -q "qwen2.5-coder:14b"; then
  _ok "modelo qwen2.5-coder:14b disponivel"
else
  _fail "modelo qwen2.5-coder:14b NAO pullado (ollama pull qwen2.5-coder:14b)"
fi

# 2. claude CLI auth OK
if command -v claude >/dev/null 2>&1; then
  _ok "claude CLI instalado"
else
  _fail "claude CLI nao encontrado no PATH"
fi

# 3. kanban-tasks runtime acessivel
if [ -x ~/.openclaw/kanban-tasks/cli.sh ]; then
  _ok "kanban-tasks cli.sh executavel"
else
  _fail "kanban-tasks/cli.sh ausente ou nao-executavel"
fi

# 4. scrum-master-agent runtime
if [ -x ~/.openclaw/scrum-master-agent/cli.sh ]; then
  _ok "scrum-master-agent cli.sh executavel"
else
  _fail "scrum-master-agent/cli.sh ausente"
fi

# 5. test-project existe em kanban projects
if ~/.openclaw/kanban-tasks/cli.sh project list --json 2>/dev/null | grep -q "test-project"; then
  _ok "test-project existe em kanban"
else
  _fail "test-project NAO esta em kanban-tasks projects"
fi

# 6. systemd timers criticos
for timer in openclaw-clarification-daemon openclaw-clarification-notifier openclaw-cron-dispatcher openclaw-reaper; do
  if systemctl --user is-active "${timer}.timer" >/dev/null 2>&1; then
    _ok "timer ativo: ${timer}.timer"
  else
    _fail "timer NAO ativo: ${timer}.timer"
  fi
done

# 7. cron-dispatcher.txt contem test-project (opt-in temp)
if grep -q "^test-project$" ~/.openclaw/dispatcher-agent/cron-projects.txt 2>/dev/null; then
  _ok "test-project opt-in em cron-projects.txt"
else
  _fail "test-project NAO opt-in em cron-projects.txt (rodar: echo 'test-project' >> ~/.openclaw/dispatcher-agent/cron-projects.txt)"
fi

# 8. kanban clean state (no tasks em test-project)
TP_TASKS=$(~/.openclaw/kanban-tasks/cli.sh task list --project test-project --json 2>/dev/null | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('tasks',[])))" 2>/dev/null || echo "?")
if [ "$TP_TASKS" = "0" ]; then
  _ok "test-project clean (0 tasks)"
elif [ "$TP_TASKS" = "?" ]; then
  _fail "nao consegui enumerar tasks de test-project"
else
  _fail "test-project NAO clean (tem $TP_TASKS tasks; archive antes de rodar)"
fi

# 9. artifacts/ dir vazio (sem residuo prev run)
if [ -d ~/.openclaw/self-test-evidence/artifacts ] && [ -z "$(ls -A ~/.openclaw/self-test-evidence/artifacts 2>/dev/null | grep -v '.gitkeep')" ]; then
  _ok "artifacts/ dir vazio (sem residuo prev run)"
else
  _fail "artifacts/ NAO esta vazio; teardown.sh OR limpeza manual antes"
fi

echo ""
echo "== PREFLIGHT summary =="
echo "PASS=$PASS FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo ""
  echo "Failed checks:"
  for f in "${FAILED[@]}"; do echo "  - $f"; done
  exit 1
fi
echo "READY. Agora envie no Telegram bevox-mobile topic:"
echo "  (sugestao) 'scrum-master: propor e materializar o plan em"
echo "   ~/.openclaw/self-test-evidence/specs/2026-04-22-self-test-sidecar.md"
echo "   no project test-project. Pode aceitar e deixar o pipeline rodar.'"
exit 0
SH
chmod +x ~/.openclaw/self-test-evidence/preflight.sh
~/.openclaw/self-test-evidence/preflight.sh 2>&1 | tail -10
```

Expected: preflight roda; provavelmente 1-2 FAILs (test-project opt-in, eventualmente timer não ativo). OK pra esse momento — Task 6 resolve opt-in; Bernard ativa timers se ausentes.

- [ ] **Step 2: Nenhum commit**.

### Task 4: Escrever `teardown.sh`

**Files:**
- Create: `~/.openclaw/self-test-evidence/teardown.sh`

- [ ] **Step 1: Criar script executável**

```bash
cat > ~/.openclaw/self-test-evidence/teardown.sh <<'SH'
#!/bin/bash
# Teardown pós-self-test wave-7 OH.
# 1. Archive tasks em test-project.
# 2. Snapshot events slice + poll.jsonl slice pra evidence/.
# 3. Remove test-project de cron-projects.txt.
#
# Idempotente: pode rodar multiplas vezes sem efeito colateral.

set -uo pipefail

EVIDENCE=~/.openclaw/self-test-evidence/evidence
TS=$(date -u +%Y-%m-%dT%H-%M-%SZ)
SNAP_DIR="$EVIDENCE/snap-$TS"
mkdir -p "$SNAP_DIR"

echo "=== wave-7 OH self-test TEARDOWN ==="
echo ""

# 1. Snapshot events + poll slice ANTES de archive (preserva rastro ativo)
echo "[1/4] Snapshot state + events..."
cp ~/.openclaw/kanban-tasks/state.json "$SNAP_DIR/kanban-state.json" 2>/dev/null || echo "  (kanban state.json nao acessivel)"
tail -200 ~/.openclaw/kanban-tasks/events.jsonl 2>/dev/null > "$SNAP_DIR/kanban-events-tail.jsonl" || echo "  (events.jsonl nao acessivel)"
tail -100 ~/.openclaw/clarification-agent/poll.jsonl 2>/dev/null > "$SNAP_DIR/clarification-poll-tail.jsonl" || echo "  (poll.jsonl nao acessivel)"
tail -50 ~/.openclaw/clarification-agent/notifier.jsonl 2>/dev/null > "$SNAP_DIR/notifier-tail.jsonl" || echo "  (notifier.jsonl nao acessivel)"
cp -r ~/.openclaw/self-test-evidence/artifacts "$SNAP_DIR/artifacts-copy" 2>/dev/null || true
echo "  snapshot salvo em $SNAP_DIR"

# 2. Archive tasks em test-project
echo ""
echo "[2/4] Archive tasks de test-project..."
TASK_IDS=$(~/.openclaw/kanban-tasks/cli.sh task list --project test-project --json 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for t in data.get('tasks', []):
        if t.get('status') != 'archived':
            print(t['id'])
except Exception:
    pass
" 2>/dev/null || true)

if [ -z "$TASK_IDS" ]; then
  echo "  nenhuma task ativa em test-project; skip archive"
else
  for tid in $TASK_IDS; do
    ~/.openclaw/kanban-tasks/cli.sh task archive "$tid" --reason "self-test teardown wave-7 $TS" --actor self-test --json >/dev/null 2>&1 \
      && echo "  archive $tid ok" \
      || echo "  archive $tid FAIL"
  done
fi

# 3. Remove test-project opt-in de cron-projects.txt (preservando outras linhas)
echo ""
echo "[3/4] Remove test-project de cron-projects.txt..."
CRON_FILE=~/.openclaw/dispatcher-agent/cron-projects.txt
if grep -q "^test-project$" "$CRON_FILE" 2>/dev/null; then
  grep -v "^test-project$" "$CRON_FILE" > "$CRON_FILE.tmp" && mv "$CRON_FILE.tmp" "$CRON_FILE"
  echo "  test-project removido; aplica no proximo tick"
else
  echo "  test-project ja ausente; skip"
fi

# 4. Limpa artifacts/ (ja snapshotado em evidence/)
echo ""
echo "[4/4] Limpa artifacts/ (snapshotado em evidence/)..."
rm -f ~/.openclaw/self-test-evidence/artifacts/_a-*.md
rm -f ~/.openclaw/self-test-evidence/artifacts/_b-*.md
echo "  artifacts/ limpo"

echo ""
echo "== TEARDOWN complete =="
echo "Evidence em: $SNAP_DIR"
echo ""
ls -la "$SNAP_DIR"
exit 0
SH
chmod +x ~/.openclaw/self-test-evidence/teardown.sh
~/.openclaw/self-test-evidence/teardown.sh 2>&1 | tail -10
```

Expected: teardown roda (provavelmente idempotente sem efeito na 1a run já que nada pra archive/remove). Cria snapshot vazio em `evidence/snap-<ts>/`.

- [ ] **Step 2: Limpar snapshot da execução de teste acima**

```bash
rm -rf ~/.openclaw/self-test-evidence/evidence/snap-*
echo "evidence/ limpo pra execução real"
```

- [ ] **Step 3: Nenhum commit**.

### Task 5: Escrever `README.md` com instruções de disparo

**Files:**
- Create: `~/.openclaw/self-test-evidence/README.md`

- [ ] **Step 1: Criar README**

```bash
cat > ~/.openclaw/self-test-evidence/README.md <<'MDEOF'
# Operational Loop Hardening — Self-Test (wave-7)

Dogfooding end-to-end do bloco OH (waves 1-6). Exercita a cadeia:

```
Telegram topic bevox-mobile
  ↓
bevox-mobile agent (Claude Code no workspace-bevox-mobile)
  ↓
scrum-master-agent CLI (propose plan + accept)
  ↓
kanban-tasks (wave-4 gate + wave-5 blocked_by + blocked/unblock hooks)
  ↓
cron-dispatcher (tick 300s; pega task ready de test-project)
  ↓
dispatcher-agent → claude CLI detached
  ↓
(clarification-agent local-first, se preciso)
  ↓
tester-agent + reaper → move para done
```

**Artefatos gerados:** 2 arquivos `_a-<ts>.md` e `_b-<ts>.md` em `artifacts/`.

---

## Pre-flight

```bash
~/.openclaw/self-test-evidence/preflight.sh
```

Exit 0 = ready. Se FAIL, corrigir o que indicar (modelo pullado, timers ativos, test-project opt-in — Task 6 do plan adiciona).

## Disparo via Telegram

No Telegram topic `bevox-mobile` envie mensagem pedindo ao agent para:
1. Propor o plan em `~/.openclaw/self-test-evidence/specs/2026-04-22-self-test-sidecar.md` via `scrum-master-agent/cli.sh propose --plan <path> --project-override test-project --dependency-mode hybrid`.
2. Aceitar a proposal gerada via `scrum-master-agent/cli.sh accept <proposal-id>`.
3. Deixar cron-dispatcher e pipeline rodar sozinhos (não precisa ação adicional — `make_ready` já resolve).

**Sugestão de texto:**

> Dispara o self-test wave-7 do bloco Operational Loop Hardening: invoca scrum-master propose + accept no plan em `~/.openclaw/self-test-evidence/specs/2026-04-22-self-test-sidecar.md` com `--project-override test-project --dependency-mode hybrid`. Depois deixa o cron-dispatcher pegar e executar. Me avisa quando as duas tasks fecharem `done`.

## Observação

Abrir `http://127.0.0.1:18789/kanban` OU via CLI:

```bash
watch -n 10 '~/.openclaw/kanban-tasks/cli.sh task list --project test-project --json | python3 -m json.tool'
```

Progressão esperada:
1. 2 tasks criadas (`backlog` status)
2. Task 1.1 (sem preds) move para `ready` (imediato)
3. Task 1.1 move para `in_progress` (dispatcher pega, <5min após ready)
4. Task 1.1 move para `testing` → `done` (executor + tester)
5. Hook auto-release: Task 2.1 move de `backlog` → `ready` (imediato após 1.1 done)
6. Task 2.1 move para `in_progress` → `testing` → `done`

## PASS criteria

1. Ambas tasks atingem `done` sem intervenção humana.
2. Arquivo `~/.openclaw/self-test-evidence/artifacts/_a-*.md` existe com linha `timestamp=<iso>`.
3. Arquivo `_b-*.md` existe com `depends_resolved=true` + timestamp herdado de A.
4. Task 2.1 NÃO saiu de `backlog` antes de Task 1.1 `done` (blocked_by wave-5 funcionando).
5. Zero Telegram escalations unsafe (task deveria ser happy-path determinístico).
6. `~/.openclaw/clarification-agent/poll.jsonl` sem eventos `drafter_escalated_to_cloud` em slice do período.

## FAIL handling

Se qualquer criterio falhar:
1. NÃO rodar teardown.sh ainda (preserva state pra investigação).
2. Rodar manualmente:
   ```bash
   mkdir -p ~/.openclaw/self-test-evidence/evidence/fail-$(date -u +%Y-%m-%dT%H-%M-%SZ)
   cp ~/.openclaw/kanban-tasks/state.json ~/.openclaw/self-test-evidence/evidence/fail-*/
   cp ~/.openclaw/kanban-tasks/events.jsonl ~/.openclaw/self-test-evidence/evidence/fail-*/
   cp ~/.openclaw/clarification-agent/poll.jsonl ~/.openclaw/self-test-evidence/evidence/fail-*/ 2>/dev/null || true
   ```
3. Reportar ao Claude: cenário específico + evidence dir + qualquer insight de onde falhou.
4. Abrir wave-8 para correção.

## Teardown

Após PASS confirmado:

```bash
~/.openclaw/self-test-evidence/teardown.sh
```

- Archive tasks test-project.
- Snapshot events + poll.jsonl + artifacts em `evidence/snap-<ts>/`.
- Remove test-project de cron-projects.txt (restaura estado pré).
- Limpa artifacts/ (já snapshotado).

## Close bloco OH

Apos teardown:
- Me (Claude) sinaliza PASS.
- Eu crio `50_releases/2026-04-22-operational-loop-hardening-closed.md`, update tracker + roadmap, commit draft.
- Push das 4 branches pra main COM SEU OK EXPLÍCITO.
MDEOF
echo "README criado:"
ls -la ~/.openclaw/self-test-evidence/README.md
```

Expected: README.md criado.

- [ ] **Step 2: Nenhum commit**.

### Task 6: Opt-in `test-project` em `cron-projects.txt`

**Files:**
- Modify: `~/.openclaw/dispatcher-agent/cron-projects.txt`

- [ ] **Step 1: Backup current**

```bash
cp ~/.openclaw/dispatcher-agent/cron-projects.txt ~/.openclaw/dispatcher-agent/cron-projects.txt.pre-wave7-selftest.bak
```

- [ ] **Step 2: Append test-project (temp, teardown remove)**

```bash
echo "test-project" >> ~/.openclaw/dispatcher-agent/cron-projects.txt
cat ~/.openclaw/dispatcher-agent/cron-projects.txt
```

Expected: `test-project` aparece na última linha.

- [ ] **Step 3: Rodar preflight novamente — deve passar 100% agora**

```bash
~/.openclaw/self-test-evidence/preflight.sh
echo "Exit: $?"
```

Expected: exit 0 + todos checks ✓. Se ainda FAIL em algum (ex: timer ativo ausente, ollama model), Bernard corrige antes do disparo.

- [ ] **Step 4: Nenhum commit**.

---

## Phase 1 — Execução observada (Bernard)

### Task 7: Bernard dispara + observa + reporta resultado

**Files:** nenhum (ação do Bernard).

- [ ] **Step 1: Bernard envia mensagem no Telegram topic `bevox-mobile`**

Texto sugerido (README §Disparo tem versão canônica):

> Dispara o self-test wave-7 do bloco Operational Loop Hardening: invoca scrum-master propose + accept no plan em `~/.openclaw/self-test-evidence/specs/2026-04-22-self-test-sidecar.md` com `--project-override test-project --dependency-mode hybrid`. Depois deixa o cron-dispatcher pegar e executar. Me avisa quando as duas tasks fecharem `done`.

- [ ] **Step 2: Observa MC kanban (filter project=test-project) OU CLI watch**

```bash
# Em terminal separado:
watch -n 10 '~/.openclaw/kanban-tasks/cli.sh task list --project test-project --json | python3 -m json.tool'
```

Expected: progressão conforme README §Observação (6 etapas).

- [ ] **Step 3: Valida PASS criteria (README §PASS criteria)**

Criteria 1: ambas tasks em `done`.
Criteria 2: `_a-*.md` existe + timestamp.
Criteria 3: `_b-*.md` existe + depends_resolved=true + timestamp herdado.
Criteria 4: Task 2.1 não saiu de backlog antes de 1.1 done.
Criteria 5: zero Telegram unsafe escalations.
Criteria 6: zero drafter_escalated_to_cloud.

- [ ] **Step 4: Reporta resultado ao Claude**

Formato sugerido:
- **PASS**: "Self-test PASS. Tasks T-XXXX e T-YYYY fecharam done. Arquivos A e B criados. Sem escalations. Duração total: X min."
- **FAIL**: "Self-test FAIL no criterio N. Evidence capturada em `~/.openclaw/self-test-evidence/evidence/fail-<ts>/`. Detalhe: <o que observou>."

---

## Phase 2 — Closure (condicional ao PASS)

### Task 8: Teardown + evidence capture

**Files:** nenhum (roda script existente).

**Precondição:** Bernard reportou PASS.

- [ ] **Step 1: Rodar teardown.sh**

```bash
~/.openclaw/self-test-evidence/teardown.sh 2>&1 | tail -20
```

Expected: snapshot criado, tasks arquivadas, test-project removido de cron-projects.txt, artifacts limpo.

- [ ] **Step 2: Verificar cron-projects.txt restaurado**

```bash
grep -c "^test-project$" ~/.openclaw/dispatcher-agent/cron-projects.txt
```

Expected: `0`.

- [ ] **Step 3: Verificar evidence snapshot salvo**

```bash
ls ~/.openclaw/self-test-evidence/evidence/snap-*/
```

Expected: diretório `snap-<ts>` com `kanban-state.json`, `kanban-events-tail.jsonl`, `clarification-poll-tail.jsonl`, `notifier-tail.jsonl`, `artifacts-copy/`.

- [ ] **Step 4: Nenhum commit** (runtime não git).

### Task 9: Criar release note em bevox-knowledge

**Files:**
- Create: `~/bevox-knowledge/50_releases/2026-04-22-operational-loop-hardening-closed.md`

- [ ] **Step 1: Confirmar branch draft ativa**

```bash
cd ~/bevox-knowledge
git branch --show-current
```

Expected: `draft/adr-009-clarification-daemon`.

- [ ] **Step 2: Criar release note**

Conteúdo (substituir `<…>` pelos dados reais do evidence snapshot + commits existentes):

```markdown
# Operational Loop Hardening — bloco CLOSED 2026-04-22

**Status:** delivered
**Data execucao self-test:** 2026-04-22
**Wave-7 resultado:** PASS (ou PARTIAL conforme spec §5.2)
**ADR governante:** `30_adr/ADR-009-clarification-loop-unified-local-first.md`

## Waves entregues

| Wave | Spec | Commit draft | Status |
|---|---|---|---|
| 0 noise-reset-prereq | 35_specs/2026-04-21-e10-noise-reset-prereq.md | 764b950 | delivered 2026-04-21 |
| 1 clarification-daemon-local-first | 35_specs/2026-04-21-e10-clarification-daemon-local-first.md | 707fa61 | delivered 2026-04-22 |
| 2 telegram-push-escalations | 35_specs/2026-04-21-e10-telegram-push-escalations.md | 8af3e6b | delivered + LIVE |
| 3 telegram-reply-handler | 35_specs/2026-04-21-e10-telegram-reply-handler.md | 3d5f226 + ac582ec | delivered + LIVE |
| 4 payload-completeness-gate | 35_specs/2026-04-21-e10-payload-completeness-gate.md | d3a70c1 + f525dfe | delivered |
| 5 kanban-blocked-by-schema | 35_specs/2026-04-21-e5-f4-kanban-blocked-by-schema.md | b04e64f + 3701881 | delivered + runtime migrated |
| 6 scrum-master-v2 | 35_specs/2026-04-21-e10-scrum-master-v2.md | 44580d9 | delivered (supersedes 2026-04-19-e10-scrum-master-agent) |
| 7 self-test | 35_specs/2026-04-21-e10-scrum-master-self-test.md | <esta entrada> | PASS self-test |

## Self-test evidence

- Spec sintetica: `~/.openclaw/self-test-evidence/specs/2026-04-22-self-test-sidecar.md`
- Snapshot evidence: `~/.openclaw/self-test-evidence/evidence/snap-<ts>/`
- Duracao total: <X minutos>
- Tasks materializadas: 2 (1.1 + 2.1 via blocked_by)
- Escalations: 0 (happy path)
- Cloud fallback: 0 (drafter local-only)

## Cadeia preventiva end-to-end validada

```
scrum-master-v2 gera task compliant
  → payload gate wave-4 passa (spec_ref + acceptance_criteria)
  → blocked_by schema wave-5 orquestra (phase-sequence + override)
  → clarification-daemon wave-1 processa (local-first qwen2.5-coder:14b)
  → notifier wave-2 pushes apenas escalations unsafe
  → reply-handler wave-3 resolve via /clr_{override,reject,redraft} no Telegram
```

## KPIs observados

- Latencia task-ready → task-done: <X min>
- Local drafter resolucoes safe: N/A (sem clarification no happy path)
- Cloud fallback count: 0
- Telegram push count: 0
- Reply-handler uso: 0 (spec §5.2 nao re-valida cenarios 4.3/4.6; ja provados em wave-2 live smoke 2026-04-22T09:58Z)

## Follow-ups pos-closure

- Writing-plans skill: adicionar convencao `**Depends:**` no template (fora bloco OH).
- openclaw runtime canonicalization: spec nova para migrar `~/.openclaw/` runtime pra repo git versionado (escopo grande, wave propria futura).
- UI Mission Control: visualizacao graph deps entre tasks (spec §1.3 wave-5 follow-up).
- AC estruturado: campo `acceptance_criteria` com itens tipados `{cmd, expected_exit, description}` (spec wave-4 §7 follow-up).
- Schedule self-test sprint-regression: 1x/sprint rodar este self-test como regression (candidato wave 8.X).

## Branches merged para main

- `bevox-knowledge/draft/adr-009-clarification-daemon`
- `knowledge-sync/feat/e10-clarification-commands-plugin`
- `mission-control/feat/e10-payload-completeness-gate`
- `mission-control/feat/e5-f4-kanban-blocked-by-schema`

Push executado apos PASS do self-test com go-ahead explicito do Bernard.

---

**Bloco OH fechado.** Operacao do Company OS retorna modo normal com preventive guards ativos + loop operacional completo.
```

Conteúdo final exato a inserir: substituir `<X minutos>`, `<ts>`, `<esta entrada>` pelos valores reais. Duration vem do report do Bernard; `<ts>` do snapshot dir; `<esta entrada>` fica depois do commit (referência circular; deixar placeholder e atualizar após).

- [ ] **Step 3: Commit do release note**

Será feito junto com tracker + roadmap updates na Task 11 (commit único de closure).

### Task 10: Update delivery-tracker + roadmap narrative

**Files:**
- Modify: `~/bevox-knowledge/40_roadmap/delivery-tracker.yml`
- Modify: `~/bevox-knowledge/40_roadmap/2026-04-09-openclaw-company-os-roadmap.md`
- Modify: `~/bevox-knowledge/35_specs/2026-04-21-e10-scrum-master-self-test.md` (status draft → delivered)

- [ ] **Step 1: Status spec wave-7 → delivered**

Editar `35_specs/2026-04-21-e10-scrum-master-self-test.md`: mudar `**Status:** draft` para `**Status:** delivered (2026-04-22)`.

- [ ] **Step 2: Adicionar entry delivery-tracker após wave-6**

Localizar `scrum-master-v2` entry em `40_roadmap/delivery-tracker.yml`. Inserir APÓS:

```yaml
      - id: self-test-e2e
        status: delivered
        delivered_at: 2026-04-22
        spec: 35_specs/2026-04-21-e10-scrum-master-self-test.md
        release_note: 50_releases/2026-04-22-operational-loop-hardening-closed.md
        narrative: "Operational Loop Hardening 2026-04-22 — wave-7 de 8 (dogfooding E2E)"
        features:
          - "spec sintetica em ~/.openclaw/self-test-evidence/specs/ (runtime, fora bevox-knowledge; evita poluicao)"
          - "preflight.sh + teardown.sh + README documentando disparo via Telegram bevox-mobile"
          - "test-project opt-in temporario em cron-projects.txt; teardown restaura"
          - "disparo dogfooding: Bernard envia mensagem Telegram topic bevox-mobile -> agent processa -> scrum-master-agent CLI propose + accept"
          - "pipeline exercitado end-to-end: scrum-master-v2 -> kanban (wave-4 gate + wave-5 blocked_by) -> cron-dispatcher -> dispatcher-agent -> tester-agent + reaper"
          - "PASS criteria: 2 tasks chegam done sem intervencao humana; arquivos evidenciais criados corretamente; zero Telegram unsafe; zero cloud fallback"
          - "cenarios 4.3 + 4.6 (Telegram reply) nao re-validados — wave-2 live smoke 2026-04-22T09:58Z ja provou com 3 msg_ids reais"
      - id: OH-closure
        status: delivered
        delivered_at: 2026-04-22
        release_note: 50_releases/2026-04-22-operational-loop-hardening-closed.md
        narrative: "Operational Loop Hardening 2026-04-21 — bloco CLOSED (8 waves delivered)"
        waves_delivered: "0, 1, 2, 3, 4, 5, 6, 7"
        branches_merged:
          - "bevox-knowledge/draft/adr-009-clarification-daemon"
          - "knowledge-sync/feat/e10-clarification-commands-plugin"
          - "mission-control/feat/e10-payload-completeness-gate"
          - "mission-control/feat/e5-f4-kanban-blocked-by-schema"
```

- [ ] **Step 3: Seção nova em roadmap narrative**

Editar `40_roadmap/2026-04-09-openclaw-company-os-roadmap.md`. Localizar bloco E10 (Functional Agents Pack) ou seção de bloco narrativo. Adicionar seção:

```markdown
### Operational Loop Hardening 2026-04-21 — CLOSED 2026-04-22

Bloco de 8 waves (0-7) que unificou clarification loop (push + pull canonicalizado), canonizou payload policy via gate upstream, introduziu `blocked_by` schema com AND semantics, evoluiu scrum-master para materializacao canonica, e provou o pipeline end-to-end via self-test dogfooding. Gerou ADR-009. Deprecou `bevox-mobile/scripts/*` (movidos para `_retired/` em Fase C).

**Waves delivered 2026-04-22** (todas no mesmo dia):
- wave-0 noise-reset-prereq
- wave-1 clarification-daemon-local-first (canonico, push+pull unificado, local-first qwen2.5-coder:14b)
- wave-2 telegram-push-escalations (systemd notifier 60s, LIVE since 2026-04-22T09:58Z)
- wave-3 telegram-reply-handler (plugin clarification-commands, 5 slash commands /clr_*, LIVE)
- wave-4 payload-completeness-gate (kanban CLI + HTTP 422 + TS mirror; zero bypass policy)
- wave-5 kanban-blocked-by-schema (AND semantics, hooks atomic, schema v2→v3 live migrated)
- wave-6 scrum-master-v2 (hybrid mode default, gate self-check, cycle detect, 2-step materialize)
- wave-7 self-test E2E (dogfooding PASS — ver release note 50_releases/2026-04-22-operational-loop-hardening-closed.md)

**Follow-ups registrados (fora do bloco):**
- Writing-plans skill: convencao `**Depends:**` no template
- openclaw runtime canonicalization (wave nova pra versionar `~/.openclaw/` em git)
- UI Mission Control graph deps visualization
- AC estruturado (spec wave-4 follow-up)
- Schedule self-test sprint-regression

**KPIs pos-closure:** ver release note.
```

- [ ] **Step 4: Validar YAML**

```bash
cd ~/bevox-knowledge
python3 -c "import yaml; yaml.safe_load(open('40_roadmap/delivery-tracker.yml'))" && echo OK 2>&1 | tail -3
```

Expected: `OK` (ou "No module named 'yaml'" em algumas sessões — nesse caso confiar em inspeção visual via `git diff --stat`).

### Task 11: Commit closure em bevox-knowledge draft

**Files:** git commit em `~/bevox-knowledge/`.

- [ ] **Step 1: Status + diff pre-commit**

```bash
cd ~/bevox-knowledge
git status --short
git diff --stat
```

Expected: 4 arquivos modificados/novos:
- `50_releases/2026-04-22-operational-loop-hardening-closed.md` (new)
- `40_roadmap/delivery-tracker.yml` (modified)
- `40_roadmap/2026-04-09-openclaw-company-os-roadmap.md` (modified)
- `35_specs/2026-04-21-e10-scrum-master-self-test.md` (modified)

- [ ] **Step 2: Stage + commit**

```bash
cd ~/bevox-knowledge
git add 50_releases/2026-04-22-operational-loop-hardening-closed.md \
        40_roadmap/delivery-tracker.yml \
        40_roadmap/2026-04-09-openclaw-company-os-roadmap.md \
        35_specs/2026-04-21-e10-scrum-master-self-test.md
git diff --cached --stat
git commit -m "$(cat <<'EOF'
delivery(E10): wave-7 self-test PASS — bloco OH CLOSED

Operational Loop Hardening 2026-04-21 fechado 2026-04-22. 8 waves
delivered no mesmo dia.

Self-test wave-7 PASS:
- Spec sintetica: ~/.openclaw/self-test-evidence/specs/2026-04-22-self-test-sidecar.md
- Disparo via Telegram bevox-mobile topic (dogfooding natural)
- Pipeline exercitado end-to-end: scrum-master-v2 -> kanban gates + blocked_by -> cron-dispatcher -> dispatcher-agent -> tester-agent + reaper -> done
- 2 tasks (Task 1.1 + Task 2.1 com **Depends:** override) atingiram done sem intervencao humana
- Artifacts evidenciais: _a-<ts>.md + _b-<ts>.md
- Zero Telegram unsafe escalations; zero cloud fallback

Release note: 50_releases/2026-04-22-operational-loop-hardening-closed.md
Tracker: entries self-test-e2e delivered + OH-closure delivered.
Roadmap narrative: seção "Operational Loop Hardening — CLOSED" sob E10.
Spec v7 status draft -> delivered.

Cenarios 4.3 + 4.6 (Telegram reply) nao re-validados; wave-2 live smoke
2026-04-22T09:58Z ja provou com 3 msg_ids reais (229/230/231).

Proximo passo: push das 4 branches para main com Bernard go-ahead:
- bevox-knowledge/draft/adr-009-clarification-daemon -> main
- knowledge-sync/feat/e10-clarification-commands-plugin -> main
- mission-control/feat/e10-payload-completeness-gate -> main
- mission-control/feat/e5-f4-kanban-blocked-by-schema -> main

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)" && git log --oneline -9
```

Expected: novo commit no topo, acima de `delivery(E10): wave-6 scrum-master-v2 delivered`. Mostra 9+ commits no histórico OH.

- [ ] **Step 3: NÃO pushar** nesta task. Push é Task 12 separada, com Bernard go-ahead explícito.

### Task 12: Push das 4 branches para main (CONDICIONAL + Bernard go-ahead explícito)

**Precondição:** Bernard confirmou explicitamente pra pushar as branches (não automático pós-Task 11).

**Files:** git push em 3 repos.

- [ ] **Step 1: Confirmar Bernard aprovou push**

Ação do Claude: pausar + perguntar Bernard "confirmas push das 4 branches pra main agora?" Esperar resposta afirmativa antes de prosseguir.

- [ ] **Step 2: Verificar estado pre-push das 3 branches**

```bash
# bevox-knowledge
cd ~/bevox-knowledge
git status --short  # deve estar clean
git log --oneline -1 draft/adr-009-clarification-daemon
git log --oneline -1 main

# knowledge-sync
cd ~/code/knowledge-sync
git status --short
git log --oneline -1 feat/e10-clarification-commands-plugin
git log --oneline -1 main

# mission-control
cd ~/code/mission-control
git status --short  # tem uncommitted unrelated; OK
git log --oneline -1 feat/e10-payload-completeness-gate
git log --oneline -1 feat/e5-f4-kanban-blocked-by-schema
git log --oneline -1 main
```

Expected: feat branches estão ahead de main; main não mudou desde o branching; status clean (exceto uncommitted unrelated em mission-control, esperado).

- [ ] **Step 3: Merge bevox-knowledge draft → main (local first, push depois)**

```bash
cd ~/bevox-knowledge
git checkout main
git pull --ff-only origin main
git merge --no-ff draft/adr-009-clarification-daemon -m "Merge draft/adr-009-clarification-daemon: Operational Loop Hardening bloco CLOSED (waves 0-7 delivered)"
git log --oneline -5
```

Expected: merge commit criado em main; 8 delivery commits presentes na historia.

- [ ] **Step 4: Push bevox-knowledge main**

```bash
cd ~/bevox-knowledge
git push origin main
```

Expected: remote atualizado.

- [ ] **Step 5: Merge + push knowledge-sync feat/e10-clarification-commands-plugin**

```bash
cd ~/code/knowledge-sync
git checkout main
git pull --ff-only origin main
git merge --no-ff feat/e10-clarification-commands-plugin -m "Merge feat/e10-clarification-commands-plugin (E10 OH wave-3): Telegram /clr_* plugin"
git push origin main
```

Expected: merge + push OK.

- [ ] **Step 6: Merge + push mission-control feat/e10-payload-completeness-gate**

```bash
cd ~/code/mission-control
git checkout main
# uncommitted unrelated (CLAUDE.md, health page, hardening) viajam com checkout; preservar
git pull --ff-only origin main
git merge --no-ff feat/e10-payload-completeness-gate -m "Merge feat/e10-payload-completeness-gate (E10 OH wave-4): payload gate on POST /api/kanban/tasks"
git push origin main
```

Expected: merge + push OK.

- [ ] **Step 7: Merge + push mission-control feat/e5-f4-kanban-blocked-by-schema**

```bash
cd ~/code/mission-control
# main ja atualizado pelo Step 6
git merge --no-ff feat/e5-f4-kanban-blocked-by-schema -m "Merge feat/e5-f4-kanban-blocked-by-schema (E5/F4 OH wave-5): blocked_by schema + HTTP route + UI deps display"
git push origin main
```

Expected: merge + push OK.

- [ ] **Step 8: Verificar historico remoto**

```bash
cd ~/bevox-knowledge && git log --oneline origin/main | head -5
cd ~/code/knowledge-sync && git log --oneline origin/main | head -3
cd ~/code/mission-control && git log --oneline origin/main | head -5
```

Expected: commits OH presentes em origin/main nos 3 repos.

- [ ] **Step 9: Feat branches local: manter ou limpar?**

Per CLAUDE.md §8 "Nunca assumir como seguro... alteracao destrutiva... force push... branch -D sem justificativa". Prefiro **manter** as branches locais pra rollback-historico. Bernard decide se delete depois (simples `git branch -d <branch>` não-destrutivo pra branches merged).

---

## Checklist final

- [ ] **Artefatos prep:** `~/.openclaw/self-test-evidence/{README.md, specs/2026-04-22-self-test-sidecar.md, preflight.sh, teardown.sh, artifacts/, evidence/}` criados.
- [ ] **Opt-in temp:** `test-project` adicionado em `cron-projects.txt` (Task 6); teardown.sh remove (Task 8).
- [ ] **Preflight PASS:** exit 0 com todos checks ✓ antes do Bernard disparar.
- [ ] **Bernard disparo:** mensagem Telegram topic `bevox-mobile` enviada; pipeline rodou.
- [ ] **Bernard report PASS:** 2 tasks done; arquivos A+B corretos; zero escalations.
- [ ] **Teardown executado:** snapshot evidence/snap-<ts>/; test-project removido de cron; artifacts/ limpo.
- [ ] **bevox-knowledge closure commit:** release note + tracker + roadmap narrative + spec status delivered; commit b04e64f-style em draft/adr-009-clarification-daemon.
- [ ] **Bernard explicit go-ahead PUSH.**
- [ ] **4 branches merged + pushed:** bevox-knowledge main + knowledge-sync main + mission-control main (2 merges).
- [ ] **Bloco OH CLOSED:** release note publico em main; tracker reflete closure.

---

## Próximos passos pós-bloco OH CLOSED

1. **`.openclaw` runtime canonicalization** — spec nova pra versionar `~/.openclaw/` em git (escopo grande, próxima sessão dedicada).
2. **Writing-plans skill update** — adicionar convenção `**Depends:**` no template canônico (fora bloco OH; follow-up skill).
3. **UI MC graph deps** — visualização graphviz entre cards (wave-5 spec §1.3 follow-up).
4. **AC estruturado** — campo `acceptance_criteria` com itens `{cmd, expected_exit, description}` (wave-4 spec §7 follow-up).
5. **Schedule self-test sprint-regression** — rodar este self-test 1x/sprint (wave nova futura).
6. **bevox-mobile/scripts deprecation Fase C** — dia 14 pós-ADR-009 (2026-05-06): mover pra `_retired/`. Wave ou hygiene task.
