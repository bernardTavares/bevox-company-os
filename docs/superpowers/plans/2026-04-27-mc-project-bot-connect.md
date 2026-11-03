# MC Project Bot Connect — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** UI no MC pra conectar bot Telegram a um projeto (botão em ProjectGeralTab).

**Architecture:** 4 routes MC backend (connect/disconnect/restart/status) → spawn `bootstrap-telegram-agent.sh` refatorado com `--non-interactive --json` → atualiza `projects-meta.json`. UI: `ConnectBotModal` + `BotPanel` na seção "Telegram bot" do tab Geral.

**Tech Stack:** bash + jq + python3 (script), Next.js 15 + TypeScript + vitest (MC), bats (script tests).

**Spec:** `bevox-knowledge/35_specs/company-os/2026-04-27-mc-project-bot-connect.md`

**Cross-repo:** openclaw (script refactor) + mission-control (UI/backend) — 2 PRs paralelos.

---

## File Structure

**openclaw:**
- Modify: `~/.openclaw/scripts/bootstrap-telegram-agent.sh` — adicionar flag-based non-interactive mode

**mission-control:**
- Create: `src/lib/bot/connect.ts` — validateToken, telegramGetMe, pickFreePort, runBootstrap
- Create: `src/lib/bot/audit.ts` — JSONL log helper (`~/.openclaw/projects-bot.jsonl`)
- Modify: `src/lib/projects/meta.ts` — adicionar `bot_username`, `bot_port` ao schema + readBotMeta/updateBotMeta
- Create: `src/app/api/projects/[id]/bot/connect/route.ts` (POST)
- Create: `src/app/api/projects/[id]/bot/route.ts` (DELETE + GET status helper)
- Create: `src/app/api/projects/[id]/bot/restart/route.ts` (POST)
- Create: `src/app/api/projects/[id]/bot/status/route.ts` (GET)
- Create: `src/components/projects/ConnectBotModal.tsx`
- Create: `src/components/projects/BotPanel.tsx`
- Modify: `src/components/projects/ProjectGeralTab.tsx` — adicionar seção entre metadata e DangerZone
- Test: `tests/app/api/projects/bot.test.ts` (vitest, contract shapes)
- Test: `tests/lib/bot/connect.test.ts` (vitest, helpers)
- Test (script): `tests/bash/bootstrap-telegram-agent.bats` (em openclaw repo)

---

## Task 1: Push spec PR + pause for merge

**Status:** Spec PR #27 já mergeado em main. Pular.

- [x] Skip (já completo)

---

## Task 2: bootstrap-telegram-agent.sh — flag-based non-interactive mode

**Files:**
- Modify: `~/.openclaw/scripts/bootstrap-telegram-agent.sh`

Adicionar parsing de flags antes do código existente. Modo `--non-interactive`:
1. Lê `--token`, `--chat-id`, `--allow-from`, `--skills` (CSV); falha se faltar.
2. Pula echos de checklist final.
3. Após escrever config, valida `systemctl --user is-active openclaw-gateway@<area>.service == active`; se não, exit 1 com stderr explícito.
4. Output final = JSON `{"port":N,"profile_dir":"...","systemd_unit":"...","success":true}` (single line).

Modo interactive (sem `--non-interactive`) = comportamento atual preservado intacto.

Modificações no Python embebido pra escrever:
- `c["channels"]["telegram"]["groups"] = {str(chat_id): {"requireMention": False}}`
- `c["channels"]["telegram"]["allowFrom"] = allow_from_list`
- `c["channels"]["telegram"]["botToken"] = token` (campo confirmado em bevox-mobile config)
- `c["plugins"]["allow"] = skills_list` (sempre inclui `knowledge-sync-commands`)

- [ ] **Step 1: Escrever bats tests** (ou shellspec se já existir no repo) cobrindo: happy path, faltando token, idempotência re-run, parsing CSV de skills.

```bash
# tests/bash/bootstrap-telegram-agent.bats (new file)
@test "non-interactive happy path emits JSON + creates profile" {
  run scripts/bootstrap-telegram-agent.sh \
    --token "1234567890:AAFakeToken_FakeToken_FakeToken_xyz" \
    --chat-id "-100123456" --allow-from "111" --skills "knowledge-sync-commands" \
    --non-interactive --json testarea 18999
  [ "$status" -eq 0 ]
  echo "$output" | tail -1 | jq -e '.success == true and .port == 18999'
}
```

- [ ] **Step 2: Rodar tests** — esperam fail (modo --non-interactive não existe ainda).

```bash
bats tests/bash/bootstrap-telegram-agent.bats
```

Expected: 4 FAIL.

- [ ] **Step 3: Implementar flag parsing + non-interactive branch.**

Adicionar antes da linha `AREA="${1:-}"`:

```bash
TOKEN=""
CHAT_ID=""
ALLOW_FROM=""
SKILLS="knowledge-sync-commands"
NON_INTERACTIVE=0
JSON_OUTPUT=0

POSITIONAL=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --token) TOKEN="$2"; shift 2 ;;
    --chat-id) CHAT_ID="$2"; shift 2 ;;
    --allow-from) ALLOW_FROM="$2"; shift 2 ;;
    --skills) SKILLS="$2"; shift 2 ;;
    --non-interactive) NON_INTERACTIVE=1; shift ;;
    --json) JSON_OUTPUT=1; shift ;;
    *) POSITIONAL+=("$1"); shift ;;
  esac
done
set -- "${POSITIONAL[@]}"
```

Após validações de AREA/PORT, se `NON_INTERACTIVE=1`:

```bash
if [[ "$NON_INTERACTIVE" -eq 1 ]]; then
  [[ -n "$TOKEN" && -n "$CHAT_ID" && -n "$ALLOW_FROM" ]] || {
    echo "FAIL: --non-interactive requires --token --chat-id --allow-from" >&2
    exit 2
  }
fi
```

Trocar o bloco Python embebido (linhas 79-99) pra usar variáveis bash quando `NON_INTERACTIVE=1`:

```bash
python3 - <<PYEOF
import json, os
p = "$PROFILE_DIR/openclaw.json"
c = json.load(open(p))
c["agents"]["defaults"]["workspace"] = "$PROFILE_DIR/workspace"
c["agents"]["list"] = [{"id": "main", "workspace": "$PROFILE_DIR/workspace"}]
if "channels" not in c: c["channels"] = {}
non_int = ${NON_INTERACTIVE}
if non_int:
    chat_id = "$CHAT_ID"
    allow_from = "$ALLOW_FROM".split(",")
    c["channels"]["telegram"] = {
        "enabled": True,
        "groups": {chat_id: {"requireMention": False}},
        "dmPolicy": "allowlist",
        "allowFrom": allow_from,
        "botToken": "$TOKEN",
    }
else:
    c["channels"]["telegram"] = {
        "enabled": True,
        "groups": {"<POPULATE_CHAT_ID>": {"requireMention": False}},
        "dmPolicy": "allowlist",
        "allowFrom": ["<POPULATE_BERNARD_USER_ID>"],
    }
if "plugins" not in c: c["plugins"] = {}
c["plugins"]["allow"] = "$SKILLS".split(",")
json.dump(c, open(p, "w"), indent=2)
PYEOF
```

Após ENV_FILE write, se `NON_INTERACTIVE=1`:

```bash
if [[ "$NON_INTERACTIVE" -eq 1 ]]; then
  systemctl --user daemon-reload
  systemctl --user enable --now "openclaw-gateway@$AREA.service"
  sleep 2
  if ! systemctl --user is-active --quiet "openclaw-gateway@$AREA.service"; then
    echo "FAIL: systemd unit not active after enable" >&2
    journalctl --user -u "openclaw-gateway@$AREA.service" -n 20 --no-pager >&2
    exit 1
  fi
  if [[ "$JSON_OUTPUT" -eq 1 ]]; then
    printf '{"success":true,"port":%s,"profile_dir":"%s","systemd_unit":"openclaw-gateway@%s.service","area":"%s"}\n' \
      "$PORT" "$PROFILE_DIR" "$AREA" "$AREA"
  fi
  exit 0
fi
```

Bloco echo do checklist (linhas 114-128) só roda quando `NON_INTERACTIVE=0`.

- [ ] **Step 4: Rodar tests + verificar todos passam.**

```bash
bats tests/bash/bootstrap-telegram-agent.bats
```

Expected: 4 PASS.

- [ ] **Step 5: Commit no openclaw repo.**

```bash
cd ~/code/openclaw  # ou onde fica o repo canônico
git checkout -b feat/bot-bootstrap-non-interactive
git add scripts/bootstrap-telegram-agent.sh tests/bash/bootstrap-telegram-agent.bats
git commit -m "feat(scripts): bootstrap-telegram-agent --non-interactive --json mode"
```

---

## Task 3: meta.ts extension — bot_username + bot_port

**Files:**
- Modify: `mission-control/src/lib/projects/meta.ts`

Schema extension:
```typescript
export interface ProjectMetaEntry {
  name: string;
  description: string;
  github_url: string | null;
  bot_id: string | null;
  bot_username: string | null;  // NEW
  bot_port: number | null;       // NEW
  created_at: string;
  source: "canonical" | "user_created";
}
```

Add helpers:
```typescript
export function setBotMeta(id: string, patch: { bot_id, bot_username, bot_port }): void
export function clearBotMeta(id: string): void
```

Both atomic via existing flock+rename pattern.

- [ ] **Step 1: Escrever vitest.** `tests/lib/projects/meta.test.ts` adicionar 2 cases: setBotMeta atomic update; clearBotMeta sets all 3 to null.

- [ ] **Step 2: Rodar test → FAIL** (helpers não existem).

- [ ] **Step 3: Implementar `setBotMeta` + `clearBotMeta` em meta.ts**, mirror estrutura de `update_project` existente.

- [ ] **Step 4: Test → PASS.**

- [ ] **Step 5: Commit.**

```bash
git add src/lib/projects/meta.ts tests/lib/projects/meta.test.ts
git commit -m "feat(meta): bot_username + bot_port fields + setBotMeta/clearBotMeta helpers"
```

---

## Task 4: lib/bot/connect.ts — helpers

**Files:**
- Create: `mission-control/src/lib/bot/connect.ts`
- Test: `mission-control/tests/lib/bot/connect.test.ts`

Helpers exportados:

```typescript
export function validateToken(t: string): boolean
  // regex /^\d+:[A-Za-z0-9_-]{30,}$/

export async function telegramGetMe(token: string, signal?: AbortSignal): Promise<{username: string}>
  // fetch https://api.telegram.org/bot<token>/getMe, timeout 5s, throw on !ok
  // returns {username} ou throw {code:"telegram_getme_failed", detail}

export function pickFreePort(): number
  // scan ~/.openclaw-*/openclaw.json files
  // extract gateway.port from each
  // return max(...) + 1 (mínimo 18790)
  // cap 18999 → throw {code:"port_pool_exhausted"}

export async function runBootstrap(args: {
  area: string;
  port: number;
  token: string;
  chatId: number;
  allowFrom: string[];
  skills: string[];
}): Promise<{port:number, profileDir:string, systemdUnit:string}>
  // spawn ~/.openclaw/scripts/bootstrap-telegram-agent.sh com flags
  // parseLastJsonLine (reaproveitar do delete handler)
  // throw {code:"bootstrap_failed", stderr} se exit != 0
```

- [ ] **Step 1: Escrever tests** — 4 cases: validateToken regex; pickFreePort scan; telegramGetMe mock fetch; runBootstrap spawn args (mock child_process).

```typescript
describe("validateToken", () => {
  it("accepts valid bot token", () => {
    expect(validateToken("1234567890:AAFakeToken_FakeToken_FakeToken_xyz")).toBe(true);
  });
  it("rejects malformed", () => {
    expect(validateToken("notatoken")).toBe(false);
  });
});
```

- [ ] **Step 2: Tests → FAIL.**

- [ ] **Step 3: Implementar connect.ts.** Reuse `parseLastJsonLine` de `src/lib/projects/spawn.ts` (existe da factory wave).

- [ ] **Step 4: Tests → PASS.**

- [ ] **Step 5: Commit.**

```bash
git commit -m "feat(bot): lib/bot/connect.ts helpers (validate, getMe, port, runBootstrap)"
```

---

## Task 5: lib/bot/audit.ts — JSONL log

**Files:**
- Create: `mission-control/src/lib/bot/audit.ts`

```typescript
export type BotAuditAction = "bot_connected" | "bot_disconnected" | "bot_restarted" | "bot_connect_failed";

export function appendBotAudit(action: BotAuditAction, payload: {
  project_id: string;
  success: boolean;
  port?: number;
  error_code?: string;
}): void
  // path: process.env.OPENCLAW_DIR ?? ~/.openclaw / projects-bot.jsonl
  // flock + append (mirror projects-delete.jsonl pattern)
  // NEVER include token in payload
```

- [ ] **Step 1: Test** que verifica log written + token never appears in stringified entry.

- [ ] **Step 2: Test → FAIL.**

- [ ] **Step 3: Implementar.** Mirror `~/.openclaw/projects-delete.jsonl` pattern (flock + tmp+rename).

- [ ] **Step 4: Test → PASS.**

- [ ] **Step 5: Commit.**

---

## Task 6: POST /api/projects/[id]/bot/connect

**Files:**
- Create: `mission-control/src/app/api/projects/[id]/bot/connect/route.ts`

Fluxo (referenciar spec §4.1):
1. Read body, validate shape com zod (token, chat_id int, allow_from string[], skills string[])
2. Pre-flight (404 not_found / 409 already_connected / 400 invalid_*)
3. `telegramGetMe(token)` (5s timeout) → captura username; falha = 502
4. `pickFreePort()`
5. `runBootstrap({area:id, port, ...})` (60s timeout) → falha = 500 bootstrap_failed
6. `setBotMeta(id, {bot_id:id, bot_username:username, bot_port:port})`
7. `appendBotAudit("bot_connected", {project_id:id, success:true, port})`
8. Return 200 com shape do spec §4.1

Em qualquer erro pós-passo 4: rollback parcial não é possível (script já rodou). Auditar `bot_connect_failed` mas NÃO atualizar meta — script é idempotente, retry cobre.

- [ ] **Step 1: Test contract** em `tests/app/api/projects/bot.test.ts`: happy 200 shape; bot_already_connected 409; invalid_token 400.

- [ ] **Step 2: Tests → FAIL.**

- [ ] **Step 3: Implementar route handler.** Mock `runBootstrap` + `telegramGetMe` em testes via vi.mock.

- [ ] **Step 4: Tests → PASS.**

- [ ] **Step 5: Commit.**

```bash
git commit -m "feat(api): POST /api/projects/[id]/bot/connect"
```

---

## Task 7: DELETE /api/projects/[id]/bot

**Files:**
- Create: `mission-control/src/app/api/projects/[id]/bot/route.ts` (DELETE handler)

Fluxo:
1. `meta.projects[id]?.bot_id` existe? else 409 `bot_not_connected`
2. Spawn `systemctl --user stop openclaw-gateway@<bot_id>.service` (timeout 10s, exit code ignored — idempotente)
3. Spawn `systemctl --user disable openclaw-gateway@<bot_id>.service` (idem)
4. `clearBotMeta(id)`
5. `appendBotAudit("bot_disconnected", {project_id:id, success:true})`
6. Return 200 `{success:true, kept_profile_dir}`

Profile dir **NÃO** removido (soft disconnect).

- [ ] **Step 1: Test:** happy 200; bot_not_connected 409.
- [ ] **Step 2: FAIL.**
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: PASS.**
- [ ] **Step 5: Commit.**

---

## Task 8: POST /api/projects/[id]/bot/restart

**Files:**
- Create: `mission-control/src/app/api/projects/[id]/bot/restart/route.ts`

Fluxo:
1. bot_id != null else 409
2. `systemctl --user restart openclaw-gateway@<bot_id>.service`
3. `systemctl --user is-active openclaw-gateway@<bot_id>.service` capture stdout
4. `appendBotAudit("bot_restarted", ...)`
5. Return 200 `{success:true, active_state}`

- [ ] Steps 1-5 mesmo padrão (test → impl → commit).

---

## Task 9: GET /api/projects/[id]/bot/status

**Files:**
- Create: `mission-control/src/app/api/projects/[id]/bot/status/route.ts`

Fluxo:
1. `meta.projects[id]` existe? else 404
2. Se `bot_id == null`: return `{connected:false}` 200
3. Se `bot_id != null`:
   - Read `~/.openclaw-<bot_id>/openclaw.json` → extrai `channels.telegram.groups` keys[0] = chat_id; `plugins.allow` = skills
   - `systemctl --user is-active openclaw-gateway@<bot_id>.service` → active_state
   - Return shape do spec §4.1

- [ ] Steps 1-5 mesmo padrão.

---

## Task 10: ConnectBotModal component

**Files:**
- Create: `mission-control/src/components/projects/ConnectBotModal.tsx`

Props: `{projectId, projectName, defaultAllowFrom, availableSkills, onClose, onSuccess}`.

Estados: form (default) → submitting → success(2s) → close. Erro inline com retry.

`availableSkills` vem prop pai (lê de openclaw.json plugins.installs). Default só `knowledge-sync-commands`.

Form fields conforme spec §5.2. CTAs: Cancel + Connect bot (disabled durante submit).

- [ ] **Step 1: Snapshot test renderiza fields.**
- [ ] **Step 2: Test → FAIL.**
- [ ] **Step 3: Implementar.** Mirror estrutural de `NewProjectModal.tsx` / `DeleteProjectModal.tsx`.
- [ ] **Step 4: PASS.**
- [ ] **Step 5: Commit.**

---

## Task 11: BotPanel component (estado connected)

**Files:**
- Create: `mission-control/src/components/projects/BotPanel.tsx`

Props: `{status: BotStatus, onRestart, onDisconnect}` onde `BotStatus = {connected:true, bot_username, chat_id, port, active_state, skills}`.

Render conforme spec §3.2: `●` color baseado em active_state, `@username`, chat_id mascarado (`-100•••••••••88` — primeiros 4 + dots + últimos 2), botões Restart/Disconnect com confirms simples.

Helper `maskChatId(n)`: `'-100' + '•'.repeat(8) + last2`.

- [ ] **Step 1: Test maskChatId + render active green.**
- [ ] **Step 2: FAIL.**
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: PASS.**
- [ ] **Step 5: Commit.**

---

## Task 12: ProjectGeralTab integration — Telegram bot section

**Files:**
- Modify: `mission-control/src/components/projects/ProjectGeralTab.tsx`

Adicionar entre metadata block e `<DangerZone>`:

```tsx
<section className="...">
  <h2>Telegram bot</h2>
  {botStatus === null && <Spinner />}
  {botStatus?.connected === false && (
    <NotConnectedState onConnect={() => setModalOpen(true)} />
  )}
  {botStatus?.connected === true && (
    <BotPanel status={botStatus} onRestart={handleRestart} onDisconnect={handleDisconnect} />
  )}
</section>

{modalOpen && (
  <ConnectBotModal
    projectId={project.id}
    projectName={project.name}
    defaultAllowFrom={voxAllowFrom}
    availableSkills={availableSkills}
    onClose={() => setModalOpen(false)}
    onSuccess={(payload) => { setModalOpen(false); refetchStatus(); }}
  />
)}
```

`useEffect` no mount fetch GET `/api/projects/[id]/bot/status`. `voxAllowFrom` e `availableSkills` vêm de prop pai (page.tsx fetch único). Decisão simples: page.tsx GET `/api/system/bot-defaults` que retorna `{vox_allow_from, available_skills}` lendo Vox config — task adicional incluída neste step (fast follow).

- [ ] **Step 1: Adicionar route minimal `/api/system/bot-defaults`** retornando default allow_from + available skills.
- [ ] **Step 2: Modificar page.tsx pra passar props.**
- [ ] **Step 3: Modificar ProjectGeralTab integrating section.**
- [ ] **Step 4: Build local + click-test manual no dev server.**
- [ ] **Step 5: Commit.**

---

## Task 13: Push openclaw + MC PRs + pause

- [ ] **Step 1: Push openclaw branch + open PR.**

```bash
cd ~/code/openclaw  # ou path canonical
git push -u origin feat/bot-bootstrap-non-interactive
gh pr create --title "feat(scripts): bot bootstrap --non-interactive mode" --body "Spec: bevox-knowledge §4.2"
```

- [ ] **Step 2: Push MC branch + open PR.**

```bash
cd ~/code/mission-control
git checkout -b feat/project-bot-connect
# tudo deve ter sido committed em tasks 3-12 nesta branch
git push -u origin feat/project-bot-connect
gh pr create --title "feat(projects): bot connect UI + 4 routes" --body "Spec: bevox-knowledge §4-5. Depends openclaw PR #X"
```

- [ ] **Step 3: PAUSE — esperar Bernard mergear ambos PRs.**

---

## Task 14: Pull main + build + restart MC

Após Bernard mergear:

- [ ] **Step 1: openclaw pull main + redeploy script.**

```bash
cd ~/code/openclaw && git checkout main && git pull
cp scripts/bootstrap-telegram-agent.sh ~/.openclaw/scripts/
chmod +x ~/.openclaw/scripts/bootstrap-telegram-agent.sh
```

- [ ] **Step 2: MC pull main + build + restart.**

```bash
cd ~/code/mission-control && git checkout main && git pull
npm run build
systemctl --user restart mission-control
sleep 2 && systemctl --user is-active mission-control
```

---

## Task 15: Smoke E2E 5 cenários

Bernard executa manualmente:

- [ ] **Cenário 1: Connect bot novo** — criar projeto teste via UI, gerar TOKEN BotFather + grupo + add bot admin → UI tab Geral → seção Telegram bot → Connect → preencher → submit → 200 + status active no painel → mensagem no grupo responde.

- [ ] **Cenário 2: Disconnect** — botão Disconnect → confirma → systemd inactive → meta `bot_id=null` → workspace `~/.openclaw-<id>/` ainda existe.

- [ ] **Cenário 3: Reconnect mesmo projeto** — Connect novamente com mesmo TOKEN/CHAT_ID → 200 → bot ativo (profile dir reaproveitado).

- [ ] **Cenário 4: Token inválido** — Connect com token aleatório → 502 erro inline → meta intocado → systemd não criou unit.

- [ ] **Cenário 5: Restart** — bot active → botão Restart → confirma → continua active → `journalctl --user -u openclaw-gateway@<id>` mostra restart.

Após smoke: deletar projeto teste via UI (delete flow já entregue) — confirma cleanup integral.

---

## Task 16: Tracker entry + memory close

- [ ] **Step 1: Adicionar entry em `bevox-knowledge/40_roadmap/_shared/delivery-tracker.yml`** sob `company-os` epic:

```yaml
- id: mc-project-bot-connect
  date: 2026-04-27
  status: delivered
  spec: 35_specs/company-os/2026-04-27-mc-project-bot-connect.md
  prs:
    - openclaw#XX
    - mission-control#YY
  closes: ciclo create+delete+connect-bot por projeto
```

- [ ] **Step 2: Commit + push tracker entry em main.**

```bash
cd ~/bevox-knowledge
git add 40_roadmap/_shared/delivery-tracker.yml
git commit -m "tracker: mc-project-bot-connect delivered 2026-04-27"
git push
```

- [ ] **Step 3: Atualizar memory** em `~/.claude/projects/-home-you--openclaw/memory/`:
- New file `e2_mc_project_bot_connect_2026_04_27.md` (project type)
- Add line em `MEMORY.md`

---

## Self-review notes

- **Spec coverage:** §1-13 cobertos (motivação T1; routes T6-T9; UI T10-T12; refactor script T2; meta T3; helpers T4-T5; smoke T15; observabilidade T5; rollout T13-T16).
- **Decisões D1-D8 do spec:** todas implementadas.
- **Riscos do spec §9:** token nunca logado (T5 audit), token via stdin **NÃO** implementado (follow-up opcional anotado), DBUS_SESSION verificar antes de spawn `systemctl --user` (assumo OK porque existing routes já fazem; se quebrar = hotfix).
- **Cap LOC:** ~530 mantido (script ~80, helpers ~150, routes ~200, UI ~200).
