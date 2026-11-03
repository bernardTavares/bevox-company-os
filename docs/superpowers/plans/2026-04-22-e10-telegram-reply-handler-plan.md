# Telegram Reply Handler (Clarification Commands) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar plugin OpenClaw `clarification-commands` em `~/code/knowledge-sync/plugins/clarification-commands/` que registra 5 slash commands `/clr_{pending,show,override,reject,redraft}` via `api.registerCommand` (bypassa LLM), cada um invoca `~/.openclaw/clarification-agent/cli.sh` via `execFile` e formata resposta no chat.

**Architecture:** Plugin ESM Node 22+. Camadas puras testáveis em `lib/`: `parse.js` (safeJsonParse + parseRejectArgs), `format.js` (5 formatters + truncate), `exec.js` (runCli com DI), `commands.js` (5 handlers — exec + format). `index.js` usa `definePluginEntry({register(api, {config})})` do SDK real e chama `api.registerCommand({requireAuth: true, handler})` 5x. Auth via SDK declarativo (gateway bloqueia não-autorizados via `elevated.allowFrom.telegram` em `openclaw.json`, já configurado). Testes unitários com `node:test` stdlib; DI de `runCli` permite mockar subprocess.

**Tech Stack:** Node.js ≥22, ESM, `openclaw/plugin-sdk/plugin-entry`, `node:child_process.execFile`, `node:test` + `node:assert/strict`. Zero npm install runtime (mesmo Plano B Spike-5 do bloco OH). Source em `~/code/knowledge-sync/` (git repo `main`), install em `~/.openclaw/extensions/clarification-commands/` (runtime não git).

**Spec canônica:** `bevox-knowledge/35_specs/2026-04-21-e10-telegram-reply-handler.md`
**ADR governante:** `bevox-knowledge/30_adr/ADR-009-clarification-loop-unified-local-first.md`
**Bloco narrativo:** Operational Loop Hardening 2026-04-21 (wave-3 de 8)
**Branch draft bevox-knowledge:** `draft/adr-009-clarification-daemon`
**Branch fonte knowledge-sync:** `feat/e10-clarification-commands-plugin` (a criar)

**Ajustes pós-spec (validados com Bernard 2026-04-22):**
1. **Reply-to-message inference dropado.** `PluginCommandContext` do SDK (`plugin-sdk/src/plugins/types.d.ts:1566`) não expõe `reply_to_message.message_id`. Bonus fica como follow-up §8 quando SDK suportar. Wave-2 continua gravando `telegram_message_id` no `notifier-state.json` para futura compatibilidade.
2. **Auth: `requireAuth: true` declarativo** em cada `registerCommand` (não `ctx.from.id` manual). Gateway usa `elevated.allowFrom.telegram: ["<TELEGRAM_USER_ID>"]` já em `openclaw.json`. Drop `lib/auth.js` proposto na spec §4.6/6.1.
3. **Plugin entry real: `definePluginEntry({id, name, register(api, {config})})`** (não `function extension(api)` da spec §5.2). Padrão alinhado com `knowledge-sync-commands/index.js` existente.
4. **Args via `ctx.args`** (string única; split manual com `.trim().split(/\s+/)`). Padrão do `ks_reject` existente.
5. **CLI naming**: `/clr_reject` → `cli.sh reject-task`. Translation no handler (explicita em `lib/commands.js`).
6. **Actor audit**: `--actor telegram:${ctx.senderId}` em override/reject-task/redraft para trilha auditável no clarification-agent.

---

## File Structure

**Arquivos a criar no repo `~/code/knowledge-sync/`:**
- `plugins/clarification-commands/package.json` — metadata + compat + engines
- `plugins/clarification-commands/openclaw.plugin.json` — plugin manifest
- `plugins/clarification-commands/index.js` — entry via `definePluginEntry`
- `plugins/clarification-commands/lib/parse.js` — safeJsonParse + parseRejectArgs
- `plugins/clarification-commands/lib/format.js` — 5 formatters + truncate
- `plugins/clarification-commands/lib/exec.js` — runCli com DI pra teste
- `plugins/clarification-commands/lib/commands.js` — 5 handlers
- `plugins/clarification-commands/tests/parse.test.js` — unit tests parse
- `plugins/clarification-commands/tests/format.test.js` — unit tests format
- `plugins/clarification-commands/tests/exec.test.js` — unit tests exec
- `plugins/clarification-commands/tests/commands.test.js` — handlers com mock runCli
- `plugins/clarification-commands/README.md` — doc operacional

**Arquivos a modificar (runtime não-git):**
- `~/.openclaw/openclaw.json` — adicionar entradas em `plugins.allow`, `plugins.entries`, `plugins.installs`

**Arquivos a modificar (bevox-knowledge, branch draft):**
- `35_specs/2026-04-21-e10-telegram-reply-handler.md` — status draft → delivered + ajustes §3.4/§4.6/§5.2 + §8 follow-up
- `40_roadmap/delivery-tracker.yml` — entry wave-3 delivered

**Runtime install (copy, não-git):**
- `~/.openclaw/extensions/clarification-commands/*` — mirror do sourcePath (igual `knowledge-sync-commands` instalado)

---

## Phase 0 — Setup + scaffold

### Task 1: Feature branch + dir scaffolding

**Files:**
- New branch: `feat/e10-clarification-commands-plugin` em `~/code/knowledge-sync/`
- Create dirs: `plugins/clarification-commands/{lib,tests}/`

- [ ] **Step 1: Criar feature branch**

```bash
cd ~/code/knowledge-sync
git checkout main && git pull --ff-only origin main
git checkout -b feat/e10-clarification-commands-plugin
```

Expected: estar na nova branch; `git status` clean.

- [ ] **Step 2: Criar estrutura de diretórios**

```bash
mkdir -p ~/code/knowledge-sync/plugins/clarification-commands/lib
mkdir -p ~/code/knowledge-sync/plugins/clarification-commands/tests
```

- [ ] **Step 3: Validar node ≥ 22 disponível no host**

```bash
node --version
```

Expected: `v22.x.x` ou superior. Se < 22, bloquear e reportar.

- [ ] **Step 4: Confirmar SDK helper resolve**

```bash
node -e "import('openclaw/plugin-sdk/plugin-entry').then(m => console.log(Object.keys(m)))" 2>&1 | head -3
```

Expected: `[ 'definePluginEntry' ]` (ou similar — pelo menos `definePluginEntry` listado).

- [ ] **Step 5: Nenhum commit nesta task** — só dirs vazios.

---

## Phase 1 — Pure helpers (TDD node:test)

### Task 2: `lib/parse.js` — safeJsonParse + parseRejectArgs (RED→GREEN)

**Files:**
- Create: `~/code/knowledge-sync/plugins/clarification-commands/tests/parse.test.js`
- Create: `~/code/knowledge-sync/plugins/clarification-commands/lib/parse.js`

- [ ] **Step 1: Escrever tests falhando em `tests/parse.test.js`**

```javascript
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { safeJsonParse, parseRejectArgs } from '../lib/parse.js';

test('safeJsonParse returns parsed object for valid JSON', () => {
  const out = safeJsonParse('{"a":1}');
  assert.deepEqual(out, { a: 1 });
});

test('safeJsonParse returns null for empty string', () => {
  assert.equal(safeJsonParse(''), null);
  assert.equal(safeJsonParse(null), null);
  assert.equal(safeJsonParse(undefined), null);
});

test('safeJsonParse returns null for garbage', () => {
  assert.equal(safeJsonParse('not json'), null);
  assert.equal(safeJsonParse('{broken'), null);
});

test('parseRejectArgs extracts category and reason (colon separator)', () => {
  const out = parseRejectArgs('task_malformed: payload vazio');
  assert.deepEqual(out, { category: 'task_malformed', reason: 'payload vazio' });
});

test('parseRejectArgs trims whitespace around both parts', () => {
  const out = parseRejectArgs('  manual  :   cleanup teste  ');
  assert.deepEqual(out, { category: 'manual', reason: 'cleanup teste' });
});

test('parseRejectArgs returns null when no colon present', () => {
  assert.equal(parseRejectArgs('task_malformed sem colon'), null);
  assert.equal(parseRejectArgs(''), null);
});

test('parseRejectArgs preserves colons in reason body', () => {
  const out = parseRejectArgs('inexecutable: missing dep: foo::bar');
  assert.equal(out.category, 'inexecutable');
  assert.equal(out.reason, 'missing dep: foo::bar');
});
```

- [ ] **Step 2: Rodar e confirmar FAIL**

```bash
cd ~/code/knowledge-sync/plugins/clarification-commands
node --test tests/parse.test.js 2>&1 | tail -10
```

Expected: FAIL com `Error [ERR_MODULE_NOT_FOUND]: Cannot find module '.../lib/parse.js'`.

- [ ] **Step 3: Implementar `lib/parse.js`**

```javascript
// parse.js — pure helpers para parsear input de comandos e saída JSON do CLI.
//
// safeJsonParse: tolerante a stdout vazio / malformado (CLI pode falhar sem --json).
// parseRejectArgs: formato "<categoria>: <motivo>" — separador primeiro colon;
// demais colons preservados no reason.

export function safeJsonParse(raw) {
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function parseRejectArgs(input) {
  if (!input || typeof input !== 'string') return null;
  const idx = input.indexOf(':');
  if (idx < 0) return null;
  const category = input.slice(0, idx).trim();
  const reason = input.slice(idx + 1).trim();
  if (!category || !reason) return null;
  return { category, reason };
}
```

- [ ] **Step 4: Re-rodar e confirmar 7/7 PASS**

```bash
node --test tests/parse.test.js 2>&1 | tail -6
```

Expected: `# tests 7` + `# pass 7` + `# fail 0`.

### Task 3: `lib/format.js` — truncate + 5 formatters (RED→GREEN)

**Files:**
- Create: `~/code/knowledge-sync/plugins/clarification-commands/tests/format.test.js`
- Create: `~/code/knowledge-sync/plugins/clarification-commands/lib/format.js`

- [ ] **Step 1: Escrever tests em `tests/format.test.js`**

```javascript
import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  truncateForTelegram,
  formatPending,
  formatShow,
  formatOverride,
  formatReject,
  formatRedraft,
  formatError,
} from '../lib/format.js';

test('truncateForTelegram leaves short text alone', () => {
  assert.equal(truncateForTelegram('hello'), 'hello');
});

test('truncateForTelegram cuts at 4096 with suffix', () => {
  const big = 'x'.repeat(5000);
  const out = truncateForTelegram(big);
  assert.ok(out.length <= 4096);
  assert.ok(out.endsWith('(...)'));
});

test('truncateForTelegram honors custom hint suffix', () => {
  const big = 'x'.repeat(5000);
  const out = truncateForTelegram(big, { hint: ' ver mais: xxx' });
  assert.ok(out.length <= 4096);
  assert.ok(out.endsWith(' ver mais: xxx'));
});

test('formatPending with 3 escalations', () => {
  const result = { ok: true, stdout: JSON.stringify({
    escalations: [
      { clarification_id: 'T-0006-clr-2' },
      { clarification_id: 'T-0008-clr-1' },
      { clarification_id: 'T-0008-clr-2' },
    ],
  }) };
  const out = formatPending(result);
  assert.match(out, /📋 Escalations pendentes \(3\)/);
  assert.match(out, /• T-0006-clr-2/);
  assert.match(out, /• T-0008-clr-1/);
  assert.match(out, /• T-0008-clr-2/);
});

test('formatPending with 0 escalations shows empty state', () => {
  const result = { ok: true, stdout: JSON.stringify({ escalations: [] }) };
  assert.match(formatPending(result), /✅ Sem escalations pendentes/);
});

test('formatPending on CLI error falls back to error format', () => {
  const result = { ok: false, stderr: 'boom', code: 1 };
  const out = formatPending(result);
  assert.match(out, /❌/);
  assert.match(out, /boom/);
});

test('formatShow with cid returns question + answer snippets', () => {
  const result = { ok: true, stdout: JSON.stringify({
    clarification_id: 'T-0006-clr-2',
    question: 'Qual é a spec governante?',
    answer: 'Não posso responder. Confidence: unsafe.',
  }) };
  const out = formatShow(result);
  assert.match(out, /🔍 T-0006-clr-2/);
  assert.match(out, /Question:/);
  assert.match(out, /Answer:/);
  assert.match(out, /Qual é a spec/);
});

test('formatShow with task_id returns list of cids', () => {
  const result = { ok: true, stdout: JSON.stringify({
    clarification_ids: ['T-0006-clr-1', 'T-0006-clr-2'],
  }) };
  const out = formatShow(result);
  assert.match(out, /📋 T-0006/);
  assert.match(out, /• T-0006-clr-1/);
  assert.match(out, /• T-0006-clr-2/);
});

test('formatOverride success', () => {
  const result = { ok: true, stdout: JSON.stringify({
    clarification_id: 'T-0006-clr-2',
    task_id: 'T-0006',
    outcome: 'override_committed',
  }) };
  const out = formatOverride(result);
  assert.match(out, /✅ Override commit T-0006-clr-2/);
  assert.match(out, /Task T-0006 unblocked/);
});

test('formatOverride error with code', () => {
  const result = { ok: false, stdout: JSON.stringify({
    ok: false, error: 'nenhuma clarification pending pra T-XXXX',
    code: 'CLARIFICATION_NOT_FOUND',
  }), code: 2 };
  const out = formatOverride(result);
  assert.match(out, /❌ Override falhou/);
  assert.match(out, /CLARIFICATION_NOT_FOUND/);
  assert.match(out, /nenhuma clarification pending/);
});

test('formatReject success includes category + reason', () => {
  const result = { ok: true, stdout: JSON.stringify({
    task_id: 'T-0006',
    outcome: 'task_rejected',
    category: 'manual',
    reason: 'cleanup teste',
  }) };
  const out = formatReject(result);
  assert.match(out, /❌ Reject commit T-0006 \(manual\)/);
  assert.match(out, /cleanup teste/);
});

test('formatReject with INVALID_REJECT_CATEGORY error', () => {
  const result = { ok: false, stdout: JSON.stringify({
    ok: false, error: 'categoria foo invalida',
    code: 'INVALID_REJECT_CATEGORY',
  }) };
  const out = formatReject(result);
  assert.match(out, /❌ .*INVALID_REJECT_CATEGORY/);
});

test('formatRedraft with safe outcome', () => {
  const result = { ok: true, stdout: JSON.stringify({
    clarification_id: 'T-0006-clr-3', outcome: 'safe',
  }) };
  const out = formatRedraft(result, 'T-0006');
  assert.match(out, /🔄 Redraft T-0006/);
  assert.match(out, /T-0006-clr-3/);
  assert.match(out, /safe/);
});

test('formatRedraft with escalated outcome', () => {
  const result = { ok: true, stdout: JSON.stringify({
    clarification_id: 'T-0006-clr-3', outcome: 'escalated',
  }) };
  const out = formatRedraft(result, 'T-0006');
  assert.match(out, /🔄 Redraft T-0006.*escalated/s);
});

test('formatError generic fallback', () => {
  const result = { ok: false, stderr: 'timeout', code: 124, message: 'etimedout' };
  const out = formatError(result, 'test label');
  assert.match(out, /❌ test label FALHOU/);
  assert.match(out, /timeout/);
});
```

- [ ] **Step 2: Rodar e confirmar FAIL**

```bash
node --test tests/format.test.js 2>&1 | tail -6
```

Expected: Cannot find module `../lib/format.js`.

- [ ] **Step 3: Implementar `lib/format.js`**

```javascript
// format.js — formatadores de resposta pro chat Telegram.
//
// Princípios:
// - Texto plano, sem markdown pesado (consistente com wave-2).
// - Fail-safe: CLI stdout vazio ou malformado ainda produz msg legível.
// - Respeita limite 4096 chars do Telegram via truncateForTelegram.

import { safeJsonParse } from './parse.js';

const TELEGRAM_LIMIT = 4096;

export function truncateForTelegram(text, { hint = '(...)' } = {}) {
  if (!text) return '';
  if (text.length <= TELEGRAM_LIMIT) return text;
  const budget = TELEGRAM_LIMIT - hint.length;
  return text.slice(0, Math.max(0, budget)) + hint;
}

export function formatError(result, label) {
  const parsed = safeJsonParse(result?.stdout);
  const codeFromJson = parsed?.code;
  const errFromJson = parsed?.error;
  const stderr = (result?.stderr || '').trim();
  const msg = errFromJson || stderr || result?.message || '(sem detalhe)';
  const codeNote = codeFromJson
    ? ` (${codeFromJson})`
    : (result?.code !== undefined ? ` (exit ${result.code})` : '');
  return truncateForTelegram(`❌ ${label} FALHOU${codeNote}\n${msg}`);
}

export function formatPending(result) {
  if (!result.ok) return formatError(result, 'pending');
  const json = safeJsonParse(result.stdout);
  const escalations = json?.escalations;
  if (!Array.isArray(escalations)) {
    return truncateForTelegram(`📋 pending (output nao parseavel)\n${result.stdout || ''}`);
  }
  if (escalations.length === 0) {
    return '✅ Sem escalations pendentes.';
  }
  const lines = escalations.map(e => `• ${e.clarification_id}`);
  return truncateForTelegram(
    `📋 Escalations pendentes (${escalations.length}):\n${lines.join('\n')}`
  );
}

export function formatShow(result) {
  if (!result.ok) return formatError(result, 'show');
  const json = safeJsonParse(result.stdout);
  if (!json) {
    return truncateForTelegram(`🔍 show (output nao parseavel)\n${result.stdout || ''}`);
  }
  // show <task_id> → retorna { clarification_ids: [...] }
  if (Array.isArray(json.clarification_ids)) {
    const taskId = json.clarification_ids[0]?.replace(/-clr-\d+$/, '') || '';
    const lines = json.clarification_ids.map(c => `• ${c}`);
    return truncateForTelegram(
      `📋 ${taskId} (${json.clarification_ids.length} clarifications):\n${lines.join('\n')}`
    );
  }
  // show <cid> → retorna { clarification_id, question, answer }
  const cid = json.clarification_id || '';
  const qSnippet = (json.question || '(sem question)').slice(0, 500);
  const aSnippet = (json.answer || '(sem answer)').slice(0, 500);
  const body = [
    `🔍 ${cid}`,
    'Question:',
    qSnippet,
    '',
    'Answer:',
    aSnippet,
  ].join('\n');
  return truncateForTelegram(
    body,
    { hint: `\n(...) Ver detalhe: vox clarification show ${cid}` }
  );
}

export function formatOverride(result) {
  if (!result.ok) return formatError(result, 'Override');
  const json = safeJsonParse(result.stdout);
  if (!json) return truncateForTelegram(`✅ Override (output nao parseavel)\n${result.stdout || ''}`);
  const cid = json.clarification_id || '(cid?)';
  const taskId = json.task_id || cid.replace(/-clr-\d+$/, '');
  return `✅ Override commit ${cid}\nTask ${taskId} unblocked.`;
}

export function formatReject(result) {
  if (!result.ok) return formatError(result, 'Reject');
  const json = safeJsonParse(result.stdout);
  if (!json) return truncateForTelegram(`❌ Reject (output nao parseavel)\n${result.stdout || ''}`);
  const taskId = json.task_id || '(task?)';
  const category = json.category || '(categoria?)';
  const reason = json.reason || '';
  return `❌ Reject commit ${taskId} (${category})\n  motivo: "${reason}"`;
}

export function formatRedraft(result, requestedTaskId) {
  if (!result.ok) return formatError(result, 'Redraft');
  const json = safeJsonParse(result.stdout);
  if (!json) return truncateForTelegram(`🔄 Redraft (output nao parseavel)\n${result.stdout || ''}`);
  const cid = json.clarification_id || '(cid?)';
  const outcome = json.outcome || '(outcome?)';
  return `🔄 Redraft ${requestedTaskId} → ${cid} (outcome: ${outcome})`;
}
```

- [ ] **Step 4: Re-rodar e confirmar 15/15 PASS**

```bash
node --test tests/format.test.js 2>&1 | tail -6
```

Expected: `# tests 15` + `# pass 15` + `# fail 0`.

---

## Phase 2 — Exec wrapper (DI-ready)

### Task 4: `lib/exec.js` — runCli (RED→GREEN)

**Files:**
- Create: `~/code/knowledge-sync/plugins/clarification-commands/tests/exec.test.js`
- Create: `~/code/knowledge-sync/plugins/clarification-commands/lib/exec.js`

- [ ] **Step 1: Escrever tests em `tests/exec.test.js`**

```javascript
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { runCli, DEFAULTS } from '../lib/exec.js';

// runCli é injetável via _execFile mock (3º argumento opcional pra teste)
test('runCli success returns ok=true with stdout/stderr', async () => {
  const mockExec = async (cmd, args, opts) => {
    assert.equal(cmd, '/fake/cli.sh');
    assert.deepEqual(args, ['show', 'T-0006', '--json']);
    return { stdout: '{"clarification_ids":[]}', stderr: '' };
  };
  const out = await runCli(['show', 'T-0006', '--json'], {
    cliPath: '/fake/cli.sh',
  }, mockExec);
  assert.equal(out.ok, true);
  assert.equal(out.stdout, '{"clarification_ids":[]}');
  assert.equal(out.stderr, '');
});

test('runCli failure captures stdout+stderr+code', async () => {
  const err = Object.assign(new Error('non-zero exit'), {
    code: 2, stdout: '{"ok":false,"code":"CLARIFICATION_NOT_FOUND"}', stderr: '',
  });
  const mockExec = async () => { throw err; };
  const out = await runCli(['override', 'T-XXX', '--answer', 'x', '--commit', '--json'], {
    cliPath: '/fake/cli.sh',
  }, mockExec);
  assert.equal(out.ok, false);
  assert.equal(out.code, 2);
  assert.ok(out.stdout.includes('CLARIFICATION_NOT_FOUND'));
});

test('runCli default timeout is DEFAULTS.timeoutMs', async () => {
  let capturedOpts;
  const mockExec = async (_cmd, _args, opts) => {
    capturedOpts = opts;
    return { stdout: '{}', stderr: '' };
  };
  await runCli(['escalations', '--json'], { cliPath: '/fake' }, mockExec);
  assert.equal(capturedOpts.timeout, DEFAULTS.timeoutMs);
  assert.equal(capturedOpts.encoding, 'utf-8');
});

test('runCli custom timeout overrides default', async () => {
  let capturedOpts;
  const mockExec = async (_cmd, _args, opts) => {
    capturedOpts = opts;
    return { stdout: '{}', stderr: '' };
  };
  await runCli(['escalations', '--json'], {
    cliPath: '/fake', timeoutMs: 5000,
  }, mockExec);
  assert.equal(capturedOpts.timeout, 5000);
});

test('runCli throws if cliPath missing', async () => {
  await assert.rejects(
    () => runCli(['x'], {}, async () => ({ stdout: '', stderr: '' })),
    /cliPath required/,
  );
});
```

- [ ] **Step 2: Rodar e confirmar FAIL**

```bash
node --test tests/exec.test.js 2>&1 | tail -6
```

Expected: Cannot find module `../lib/exec.js`.

- [ ] **Step 3: Implementar `lib/exec.js`**

```javascript
// exec.js — wrapper execFile com DI opcional pra testes.
//
// runCli(args, opts, _execFile?) — se _execFile passado, usa-o (testes mockam).
// Opts: cliPath (obrigatório), timeoutMs (default 30s).
//
// Retorno uniforme: { ok: bool, stdout: string, stderr: string, code?: number,
//   signal?: string, message?: string }.

import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const execFileP = promisify(execFile);

export const DEFAULTS = {
  timeoutMs: 30000,
  maxBuffer: 1024 * 1024, // 1MB
};

export async function runCli(args, opts = {}, _execFile = execFileP) {
  const { cliPath, timeoutMs = DEFAULTS.timeoutMs } = opts;
  if (!cliPath) {
    throw new Error('cliPath required in runCli opts');
  }
  try {
    const { stdout, stderr } = await _execFile(cliPath, args, {
      timeout: timeoutMs,
      encoding: 'utf-8',
      maxBuffer: DEFAULTS.maxBuffer,
    });
    return { ok: true, stdout: (stdout || '').trim(), stderr: (stderr || '').trim() };
  } catch (err) {
    return {
      ok: false,
      stdout: (err.stdout || '').toString().trim(),
      stderr: (err.stderr || '').toString().trim(),
      code: err.code,
      signal: err.signal,
      message: err.message,
    };
  }
}
```

- [ ] **Step 4: Re-rodar e confirmar 5/5 PASS**

```bash
node --test tests/exec.test.js 2>&1 | tail -6
```

Expected: `# tests 5` + `# pass 5`.

---

## Phase 3 — Command handlers

### Task 5: `lib/commands.js` — 5 handlers com mock runCli (RED→GREEN)

**Files:**
- Create: `~/code/knowledge-sync/plugins/clarification-commands/tests/commands.test.js`
- Create: `~/code/knowledge-sync/plugins/clarification-commands/lib/commands.js`

- [ ] **Step 1: Escrever tests em `tests/commands.test.js`**

```javascript
import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  handlePending,
  handleShow,
  handleOverride,
  handleReject,
  handleRedraft,
} from '../lib/commands.js';

function makeCtx({ args = '', senderId = '<TELEGRAM_USER_ID>' } = {}) {
  return { args, senderId, channel: 'telegram' };
}

test('handlePending invokes CLI with [escalations, --json]', async () => {
  let captured;
  const runCliMock = async (args, opts) => {
    captured = { args, opts };
    return { ok: true, stdout: JSON.stringify({ escalations: [] }), stderr: '' };
  };
  const out = await handlePending(makeCtx(), { runCli: runCliMock, cliPath: '/fake' });
  assert.deepEqual(captured.args, ['escalations', '--json']);
  assert.equal(captured.opts.cliPath, '/fake');
  assert.match(out.text, /✅ Sem escalations/);
});

test('handleShow requires arg', async () => {
  const runCliMock = async () => { throw new Error('should not be called'); };
  const out = await handleShow(makeCtx({ args: '' }), { runCli: runCliMock, cliPath: '/fake' });
  assert.match(out.text, /❌ Uso:.*\/clr_show/);
});

test('handleShow invokes CLI with [show, ARG, --json]', async () => {
  let captured;
  const runCliMock = async (args) => {
    captured = args;
    return { ok: true, stdout: JSON.stringify({ clarification_ids: ['T-X-clr-1'] }), stderr: '' };
  };
  await handleShow(makeCtx({ args: 'T-X' }), { runCli: runCliMock, cliPath: '/fake' });
  assert.deepEqual(captured, ['show', 'T-X', '--json']);
});

test('handleOverride requires task_id + answer', async () => {
  const runCliMock = async () => { throw new Error('should not be called'); };
  const out = await handleOverride(makeCtx({ args: '' }), { runCli: runCliMock, cliPath: '/fake' });
  assert.match(out.text, /❌ Uso:.*\/clr_override/);

  const out2 = await handleOverride(makeCtx({ args: 'T-X' }), { runCli: runCliMock, cliPath: '/fake' });
  assert.match(out2.text, /❌ Uso:.*\/clr_override/);
});

test('handleOverride invokes CLI with override + --answer + --commit + --json + --actor', async () => {
  let captured;
  const runCliMock = async (args) => {
    captured = args;
    return { ok: true, stdout: JSON.stringify({
      clarification_id: 'T-X-clr-1', task_id: 'T-X', outcome: 'override_committed',
    }), stderr: '' };
  };
  const out = await handleOverride(
    makeCtx({ args: 'T-X A resposta tem espacos e colon: detalhe', senderId: '<TELEGRAM_USER_ID>' }),
    { runCli: runCliMock, cliPath: '/fake' }
  );
  assert.equal(captured[0], 'override');
  assert.equal(captured[1], 'T-X');
  assert.ok(captured.includes('--answer'));
  const answerIdx = captured.indexOf('--answer');
  assert.equal(captured[answerIdx + 1], 'A resposta tem espacos e colon: detalhe');
  assert.ok(captured.includes('--commit'));
  assert.ok(captured.includes('--json'));
  const actorIdx = captured.indexOf('--actor');
  assert.equal(captured[actorIdx + 1], 'telegram:<TELEGRAM_USER_ID>');
  assert.match(out.text, /✅ Override commit T-X-clr-1/);
});

test('handleReject requires task_id + colon-formatted reason', async () => {
  const runCliMock = async () => { throw new Error('should not be called'); };
  const out = await handleReject(
    makeCtx({ args: 'T-X sem colon aqui' }),
    { runCli: runCliMock, cliPath: '/fake' }
  );
  assert.match(out.text, /❌ Uso:.*\/clr_reject/);
});

test('handleReject invokes CLI with reject-task + --reason + --commit + --json + --actor', async () => {
  let captured;
  const runCliMock = async (args) => {
    captured = args;
    return { ok: true, stdout: JSON.stringify({
      task_id: 'T-X', outcome: 'task_rejected', category: 'manual', reason: 'cleanup teste',
    }), stderr: '' };
  };
  const out = await handleReject(
    makeCtx({ args: 'T-X manual: cleanup teste', senderId: '<TELEGRAM_USER_ID>' }),
    { runCli: runCliMock, cliPath: '/fake' }
  );
  assert.equal(captured[0], 'reject-task');
  assert.equal(captured[1], 'T-X');
  const reasonIdx = captured.indexOf('--reason');
  assert.equal(captured[reasonIdx + 1], 'manual: cleanup teste');
  assert.ok(captured.includes('--commit'));
  assert.match(out.text, /❌ Reject commit T-X \(manual\)/);
});

test('handleRedraft invokes CLI with [redraft, ARG, --json, --actor]', async () => {
  let captured;
  const runCliMock = async (args) => {
    captured = args;
    return { ok: true, stdout: JSON.stringify({
      clarification_id: 'T-X-clr-3', outcome: 'safe',
    }), stderr: '' };
  };
  const out = await handleRedraft(
    makeCtx({ args: 'T-X', senderId: '<TELEGRAM_USER_ID>' }),
    { runCli: runCliMock, cliPath: '/fake' }
  );
  assert.equal(captured[0], 'redraft');
  assert.equal(captured[1], 'T-X');
  assert.ok(captured.includes('--json'));
  assert.match(out.text, /🔄 Redraft T-X.*outcome: safe/);
});

test('handleRedraft requires task_id', async () => {
  const runCliMock = async () => { throw new Error('should not be called'); };
  const out = await handleRedraft(makeCtx({ args: '' }), { runCli: runCliMock, cliPath: '/fake' });
  assert.match(out.text, /❌ Uso:.*\/clr_redraft/);
});

test('handler propagates CLI error via formatter', async () => {
  const runCliMock = async () => ({
    ok: false, code: 2,
    stdout: JSON.stringify({ ok: false, error: 'nao encontrada', code: 'CLARIFICATION_NOT_FOUND' }),
    stderr: '',
  });
  const out = await handleOverride(
    makeCtx({ args: 'T-X A resposta' }),
    { runCli: runCliMock, cliPath: '/fake' }
  );
  assert.match(out.text, /❌ Override FALHOU/);
  assert.match(out.text, /CLARIFICATION_NOT_FOUND/);
});
```

- [ ] **Step 2: Rodar e confirmar FAIL**

```bash
node --test tests/commands.test.js 2>&1 | tail -6
```

Expected: Cannot find module `../lib/commands.js`.

- [ ] **Step 3: Implementar `lib/commands.js`**

```javascript
// commands.js — 5 handlers para os slash commands /clr_*.
//
// Cada handler recebe (ctx, deps):
//   ctx — PluginCommandContext (SDK): { args, senderId, ... }
//   deps — { runCli, cliPath, timeoutMs? }
//
// Retorna { text } — PluginCommandResult do SDK.
//
// Translation de nomes:
//   /clr_pending  → cli.sh escalations --json
//   /clr_show     → cli.sh show <arg> --json
//   /clr_override → cli.sh override <task_id> --answer "<texto>" --commit --json --actor telegram:<id>
//   /clr_reject   → cli.sh reject-task <task_id> --reason "<cat>: <motivo>" --commit --json --actor telegram:<id>
//   /clr_redraft  → cli.sh redraft <task_id> --json --actor telegram:<id>

import {
  formatPending,
  formatShow,
  formatOverride,
  formatReject,
  formatRedraft,
} from './format.js';
import { parseRejectArgs } from './parse.js';

function actorOf(ctx) {
  const id = ctx.senderId || 'unknown';
  return `telegram:${id}`;
}

export async function handlePending(ctx, deps) {
  const result = await deps.runCli(['escalations', '--json'], {
    cliPath: deps.cliPath, timeoutMs: deps.timeoutMs,
  });
  return { text: formatPending(result) };
}

export async function handleShow(ctx, deps) {
  const arg = (ctx.args || '').trim();
  if (!arg) {
    return { text: '❌ Uso: /clr_show <task-id|clarification-id>' };
  }
  const result = await deps.runCli(['show', arg, '--json'], {
    cliPath: deps.cliPath, timeoutMs: deps.timeoutMs,
  });
  return { text: formatShow(result) };
}

export async function handleOverride(ctx, deps) {
  const raw = (ctx.args || '').trim();
  const firstSpace = raw.indexOf(' ');
  if (firstSpace < 0) {
    return { text: '❌ Uso: /clr_override <task-id> <texto da resposta>' };
  }
  const taskId = raw.slice(0, firstSpace).trim();
  const answer = raw.slice(firstSpace + 1).trim();
  if (!taskId || !answer) {
    return { text: '❌ Uso: /clr_override <task-id> <texto da resposta>' };
  }
  const result = await deps.runCli(
    ['override', taskId, '--answer', answer, '--commit', '--json',
     '--actor', actorOf(ctx)],
    { cliPath: deps.cliPath, timeoutMs: deps.timeoutMs }
  );
  return { text: formatOverride(result) };
}

export async function handleReject(ctx, deps) {
  const raw = (ctx.args || '').trim();
  const firstSpace = raw.indexOf(' ');
  if (firstSpace < 0) {
    return { text: '❌ Uso: /clr_reject <task-id> <categoria>: <motivo>' };
  }
  const taskId = raw.slice(0, firstSpace).trim();
  const rest = raw.slice(firstSpace + 1).trim();
  const parsed = parseRejectArgs(rest);
  if (!taskId || !parsed) {
    return { text: '❌ Uso: /clr_reject <task-id> <categoria>: <motivo>' };
  }
  const reason = `${parsed.category}: ${parsed.reason}`;
  const result = await deps.runCli(
    ['reject-task', taskId, '--reason', reason, '--commit', '--json',
     '--actor', actorOf(ctx)],
    { cliPath: deps.cliPath, timeoutMs: deps.timeoutMs }
  );
  return { text: formatReject(result) };
}

export async function handleRedraft(ctx, deps) {
  const taskId = (ctx.args || '').trim();
  if (!taskId) {
    return { text: '❌ Uso: /clr_redraft <task-id>' };
  }
  const result = await deps.runCli(
    ['redraft', taskId, '--json', '--actor', actorOf(ctx)],
    { cliPath: deps.cliPath, timeoutMs: deps.timeoutMs }
  );
  return { text: formatRedraft(result, taskId) };
}
```

- [ ] **Step 4: Re-rodar e confirmar 10/10 PASS**

```bash
node --test tests/commands.test.js 2>&1 | tail -6
```

Expected: `# tests 10` + `# pass 10`.

- [ ] **Step 5: Rodar a suite inteira pra baseline**

```bash
node --test tests/ 2>&1 | tail -6
```

Expected: `# tests 37` + `# pass 37` + `# fail 0`.

---

## Phase 4 — Plugin entry + metadata

### Task 6: `index.js` — definePluginEntry + register 5 commands

**Files:**
- Create: `~/code/knowledge-sync/plugins/clarification-commands/index.js`

- [ ] **Step 1: Escrever `index.js`**

```javascript
// clarification-commands — OpenClaw plugin entry point.
//
// Registra 5 slash commands que invocam `cli.sh` da skill clarification-agent
// via execFile, sem passar pelo LLM. Pattern identico ao knowledge-sync-commands.
//
// Spec: bevox-knowledge/35_specs/2026-04-21-e10-telegram-reply-handler.md
// ADR: bevox-knowledge/30_adr/ADR-009-clarification-loop-unified-local-first.md

import { definePluginEntry } from 'openclaw/plugin-sdk/plugin-entry';
import os from 'node:os';
import path from 'node:path';

import { runCli } from './lib/exec.js';
import {
  handlePending,
  handleShow,
  handleOverride,
  handleReject,
  handleRedraft,
} from './lib/commands.js';

const DEFAULT_CLI_PATH = path.join(
  os.homedir(), '.openclaw', 'clarification-agent', 'cli.sh'
);
const DEFAULT_TIMEOUT_MS = 30000;

export default definePluginEntry({
  id: 'clarification-commands',
  name: 'Clarification Commands',
  description:
    'Telegram /clr_* commands wiring clarification-agent CLI to Bernard chat.',

  register(api, { config } = {}) {
    const cliPath = config?.cliPath || DEFAULT_CLI_PATH;
    const timeoutMs = config?.execTimeoutMs || DEFAULT_TIMEOUT_MS;
    const deps = { runCli, cliPath, timeoutMs };

    api.registerCommand({
      name: 'clr_pending',
      nativeNames: { default: 'clr_pending' },
      description: 'List open clarification escalations.',
      acceptsArgs: false,
      requireAuth: true,
      handler: (ctx) => handlePending(ctx, deps),
    });

    api.registerCommand({
      name: 'clr_show',
      nativeNames: { default: 'clr_show' },
      description: 'Show a clarification. Args: <task-id|clarification-id>.',
      acceptsArgs: true,
      requireAuth: true,
      handler: (ctx) => handleShow(ctx, deps),
    });

    api.registerCommand({
      name: 'clr_override',
      nativeNames: { default: 'clr_override' },
      description: 'Override a clarification. Args: <task-id> <texto da resposta>.',
      acceptsArgs: true,
      requireAuth: true,
      handler: (ctx) => handleOverride(ctx, deps),
    });

    api.registerCommand({
      name: 'clr_reject',
      nativeNames: { default: 'clr_reject' },
      description: 'Reject a task via clarification. Args: <task-id> <categoria>: <motivo>.',
      acceptsArgs: true,
      requireAuth: true,
      handler: (ctx) => handleReject(ctx, deps),
    });

    api.registerCommand({
      name: 'clr_redraft',
      nativeNames: { default: 'clr_redraft' },
      description: 'Re-run drafter for a task. Args: <task-id>.',
      acceptsArgs: true,
      requireAuth: true,
      handler: (ctx) => handleRedraft(ctx, deps),
    });
  },
});
```

- [ ] **Step 2: Sanity syntax check**

```bash
cd ~/code/knowledge-sync/plugins/clarification-commands
node --check index.js && echo OK
```

Expected: `OK`.

- [ ] **Step 3: Smoke de import (não executa handler real)**

```bash
cd ~/code/knowledge-sync/plugins/clarification-commands
node -e "import('./index.js').then(m => console.log('default:', typeof m.default))" 2>&1 | head -3
```

Expected: `default: object` (ou `function`, depending on SDK). Sem erros.

### Task 7: `package.json` + `openclaw.plugin.json` + `README.md`

**Files:**
- Create: `~/code/knowledge-sync/plugins/clarification-commands/package.json`
- Create: `~/code/knowledge-sync/plugins/clarification-commands/openclaw.plugin.json`
- Create: `~/code/knowledge-sync/plugins/clarification-commands/README.md`

- [ ] **Step 1: Criar `package.json`**

```json
{
  "name": "@bevox/clarification-commands",
  "version": "0.1.0",
  "private": true,
  "description": "OpenClaw plugin: Telegram /clr_* commands for clarification-agent (E10 OH wave-3).",
  "type": "module",
  "main": "./index.js",
  "files": [
    "index.js",
    "lib/",
    "openclaw.plugin.json",
    "README.md"
  ],
  "openclaw": {
    "extensions": ["./index.js"],
    "compat": {
      "pluginApi": ">=2026.4.0",
      "minGatewayVersion": "2026.4.0"
    },
    "build": {
      "openclawVersion": "2026.4.8",
      "pluginSdkVersion": "2026.4.8"
    }
  },
  "scripts": {
    "test": "node --test tests/"
  },
  "engines": {
    "node": ">=22"
  }
}
```

- [ ] **Step 2: Criar `openclaw.plugin.json`**

```json
{
  "name": "clarification-commands",
  "displayName": "Clarification Commands",
  "description": "Telegram /clr_* commands wiring clarification-agent CLI to Bernard chat.",
  "version": "0.1.0",
  "compat": {
    "pluginApi": ">=2026.4.0",
    "minGatewayVersion": "2026.4.0"
  }
}
```

- [ ] **Step 3: Criar `README.md`**

```markdown
# clarification-commands (OpenClaw plugin)

Telegram slash commands para o clarification-agent (E10 Operational Loop
Hardening wave-3). Registra 5 comandos `/clr_*` via SDK OpenClaw e invoca
`~/.openclaw/clarification-agent/cli.sh` via `execFile`, bypassando LLM.

## Comandos

- `/clr_pending` — lista escalations abertas.
- `/clr_show <task-id | clarification-id>` — mostra question + answer.
- `/clr_override <task-id> <texto>` — aplica override + unblock.
- `/clr_reject <task-id> <categoria>: <motivo>` — rejeita a task.
- `/clr_redraft <task-id>` — re-invoca drafter local-first.

## Auth

`requireAuth: true` declarativo. Gateway valida contra
`elevated.allowFrom.telegram` em `openclaw.json`.

## Instalação (deploy local)

Plugin é consumido via `path` no `openclaw.json` (mesmo pattern do
`knowledge-sync-commands`). Fluxo:

1. Comitar fonte em `bernardTavares/knowledge-sync` (`plugins/clarification-commands/`).
2. Em `~/.openclaw/openclaw.json` adicionar:

```json
"plugins": {
  "allow": ["knowledge-sync-commands", "clarification-commands", ...],
  "entries": {
    "clarification-commands": { "enabled": true }
  },
  "installs": {
    "clarification-commands": {
      "source": "path",
      "sourcePath": "~/code/knowledge-sync/plugins/clarification-commands",
      "installPath": "~/.openclaw/extensions/clarification-commands",
      "version": "0.1.0",
      "installedAt": "<ISO timestamp>"
    }
  }
}
```

3. Copiar (ou symlink) a pasta pro `installPath`.
4. Gateway reload.

## Tests

```bash
node --test tests/
```

37 unit tests (parse + format + exec + commands). Zero npm install runtime.

## Rollback

- Desabilitar: `openclaw.json` → `plugins.entries.clarification-commands.enabled: false` + gateway reload.
- Desinstalar: remover `plugins.installs.clarification-commands` + `rm -rf ~/.openclaw/extensions/clarification-commands`.
- CLI direto continua funcionando: `vox clarification override T-XXX --answer "..." --commit`.

## Source

Mirror de `~/code/knowledge-sync/plugins/clarification-commands/`. Spec canônica
em `bevox-knowledge/35_specs/2026-04-21-e10-telegram-reply-handler.md`.
```

- [ ] **Step 4: Rodar suite completa de testes pré-commit**

```bash
cd ~/code/knowledge-sync/plugins/clarification-commands
node --test tests/ 2>&1 | tail -6
```

Expected: `# tests 37` + `# pass 37` + `# fail 0`.

---

## Phase 5 — Install + openclaw.json

### Task 8: Commit plugin source em feature branch

**Files:** git commit em `~/code/knowledge-sync/`

- [ ] **Step 1: Confirmar working tree**

```bash
cd ~/code/knowledge-sync
git status --short
```

Expected: 10 arquivos novos todos sob `plugins/clarification-commands/`.

- [ ] **Step 2: Git add + diff stat**

```bash
cd ~/code/knowledge-sync
git add plugins/clarification-commands/
git diff --cached --stat
```

Expected: 10 arquivos (index.js, package.json, openclaw.plugin.json, README.md, 4 lib/*.js, 4 tests/*.test.js).

- [ ] **Step 3: Commit**

```bash
cd ~/code/knowledge-sync
git commit -m "$(cat <<'EOF'
feat(plugins): add clarification-commands (E10 OH wave-3)

5 Telegram slash commands (/clr_{pending,show,override,reject,redraft})
que bypassam o LLM via api.registerCommand SDK e invocam
~/.openclaw/clarification-agent/cli.sh via execFile.

Layout:
- index.js: definePluginEntry + registerCommand 5x
- lib/parse.js, lib/format.js, lib/exec.js, lib/commands.js
- tests/*.test.js: 37 unit tests node:test (zero npm install)

Auth: requireAuth: true declarativo (gateway valida elevated.allowFrom.telegram).
Reply-to-message inference dropado (SDK nao expoe reply_to_message em
PluginCommandContext; virou follow-up ate SDK suportar).

Spec: bevox-knowledge/35_specs/2026-04-21-e10-telegram-reply-handler.md
ADR: bevox-knowledge/30_adr/ADR-009-clarification-loop-unified-local-first.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git log --oneline -1
```

Expected: novo commit no topo, mensagem completa.

- [ ] **Step 4: Não pushar agora.** Push depois que Bernard validar smoke Telegram live.

### Task 9: Install runtime + update openclaw.json

**Files:**
- Create: `~/.openclaw/extensions/clarification-commands/` (cópia do source)
- Modify: `~/.openclaw/openclaw.json`

- [ ] **Step 1: Copiar plugin pro installPath**

```bash
mkdir -p ~/.openclaw/extensions/clarification-commands
cp -r ~/code/knowledge-sync/plugins/clarification-commands/. ~/.openclaw/extensions/clarification-commands/
ls ~/.openclaw/extensions/clarification-commands/
```

Expected: `index.js`, `lib/`, `tests/`, `package.json`, `openclaw.plugin.json`, `README.md`.

- [ ] **Step 2: Backup openclaw.json antes de editar**

```bash
cp ~/.openclaw/openclaw.json ~/.openclaw/openclaw.json.pre-wave-3.bak
```

- [ ] **Step 3: Editar `~/.openclaw/openclaw.json` adicionando 3 entradas no bloco `plugins`**

Usar Edit tool para (1) inserir `"clarification-commands",` em `plugins.allow` (após `"knowledge-sync-commands",`), (2) acrescentar `"clarification-commands": { "enabled": true }` em `plugins.entries` (após a entrada `knowledge-sync-commands`), (3) acrescentar entry completo em `plugins.installs`:

```json
      "clarification-commands": {
        "source": "path",
        "sourcePath": "~/code/knowledge-sync/plugins/clarification-commands",
        "installPath": "~/.openclaw/extensions/clarification-commands",
        "version": "0.1.0",
        "installedAt": "2026-04-22T10:00:00Z"
      }
```

Substituir `installedAt` timestamp pela hora UTC real no momento da edição.

- [ ] **Step 4: Validar JSON**

```bash
python3 -m json.tool ~/.openclaw/openclaw.json > /dev/null && echo "JSON OK"
```

Expected: `JSON OK` (sem erros de parse).

- [ ] **Step 5: Confirmar as 3 entradas estão presentes**

```bash
grep -c "clarification-commands" ~/.openclaw/openclaw.json
```

Expected: `3` (em allow, entries, installs) ou `4` se contar description em comment.

### Task 10: Gateway reload + verificar registro dos 5 comandos

**Files:** nenhum.

- [ ] **Step 1: Descobrir como reload — consultar modo do gateway**

```bash
grep -A 2 '"mode"' ~/.openclaw/openclaw.json | head -5
```

Expected: `"mode": "local"`.

- [ ] **Step 2: Reload (opções — escolher a que serve este gateway)**

Se gateway roda via systemd user:
```bash
systemctl --user list-units "openclaw-gateway*" --no-pager 2>/dev/null | head -5
```
Se unit existe e ativa: `systemctl --user restart openclaw-gateway.service` (ou equivalente).

Se gateway roda via processo ad-hoc no terminal (modo dev):
- Pedir ao Bernard para `Ctrl+C` + re-invocar (plugin só carrega no startup).

Se gateway tem endpoint admin reload:
```bash
curl -s -H "Authorization: Bearer $(grep -oP '(?<="token": ")[^"]+' ~/.openclaw/openclaw.json | head -1)" \
  http://127.0.0.1:18789/admin/plugins/reload 2>&1 | head -5
```

- [ ] **Step 3: Smoke de registro — consultar lista de comandos registrados**

Via gateway admin endpoint (se existe) OU via Telegram:
```bash
# Opção A: admin endpoint
curl -s -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:18789/admin/plugins/commands 2>&1 | grep -c "clr_"
```

Expected: `5`. Se endpoint não existe ou reload não aconteceu, reportar a Bernard e marcar esta etapa como bloqueada pedindo reload manual.

- [ ] **Step 4: Smoke E2E manual (Bernard executa via Telegram)**

Bernard envia no tópico `clarifications`:
1. `/clr_pending` — expected: lista dos 3 cids pendentes (T-0006-clr-2, T-0008-clr-1, T-0008-clr-2).
2. `/clr_show T-0006-clr-2` — expected: question + answer snippet.
3. Criar escalation sintética OU usar uma real + testar `/clr_override` e `/clr_redraft`.

Documentar resultados como comentário nesta Task na task tracker.

---

## Phase 6 — Delivery commit bevox-knowledge

### Task 11: Spec update + tracker + commit draft

**Files:**
- Modify: `~/bevox-knowledge/35_specs/2026-04-21-e10-telegram-reply-handler.md`
- Modify: `~/bevox-knowledge/40_roadmap/delivery-tracker.yml`

- [ ] **Step 1: Confirmar branch draft**

```bash
cd ~/bevox-knowledge
git branch --show-current
```

Expected: `draft/adr-009-clarification-daemon`.

- [ ] **Step 2: Atualizar status + 3 deltas na spec**

Editar `35_specs/2026-04-21-e10-telegram-reply-handler.md`:

De `**Status:** draft` para `**Status:** delivered (2026-04-22)`.

Adicionar nota em §3.4 (Reply-to-message inference):

```markdown
> **Delivery note 2026-04-22:** SDK `PluginCommandContext` (plugin-sdk/src/plugins/types.d.ts:1566) nao expoe `reply_to_message.message_id` em inbound commands. Bonus dropado; virou follow-up §8. Wave-2 continua gravando `telegram_message_id` em `notifier-state.json` para habilitar quando SDK expor.
```

Adicionar nota em §4.6 (Auth):

```markdown
> **Delivery note 2026-04-22:** substituido `ctx.from.id` manual por `requireAuth: true` declarativo em cada `registerCommand`. Gateway valida contra `elevated.allowFrom.telegram` em `openclaw.json` (ja configurado). `lib/auth.js` nao criado.
```

Adicionar nota em §5.2 (index.js entry):

```markdown
> **Delivery note 2026-04-22:** entry real usa `definePluginEntry({id, name, register(api, {config})})` do SDK (mesmo pattern do `knowledge-sync-commands/index.js`), nao `function extension(api)` como no snippet ilustrativo acima.
```

Acrescentar em §8 (Follow-ups):

```markdown
- **Reply-to-message inference** (originalmente spec §3.4): reativar quando `PluginCommandContext` do SDK expor campo `replyToMessageId` ou equivalente. Dados ja persistidos pela wave-2 em `notifier-state.json` (`telegram_message_id` por cid).
```

- [ ] **Step 3: Acrescentar entry no delivery-tracker.yml**

Abrir `40_roadmap/delivery-tracker.yml` e localizar a entry `telegram-push-escalations` (wave-2, id `telegram-push-escalations`). Inserir logo após ela, no mesmo nível:

```yaml
      - id: telegram-reply-handler
        status: delivered
        delivered_at: 2026-04-22
        spec: 35_specs/2026-04-21-e10-telegram-reply-handler.md
        adr: 30_adr/ADR-009-clarification-loop-unified-local-first.md
        narrative: "Operational Loop Hardening 2026-04-22 — wave-3 de 8"
        features:
          - "plugin clarification-commands em bernardTavares/knowledge-sync/plugins/ (source) + ~/.openclaw/extensions/ (install)"
          - "5 slash commands via api.registerCommand SDK (bypassa LLM): /clr_pending, /clr_show, /clr_override, /clr_reject, /clr_redraft"
          - "auth declarativa: requireAuth: true; gateway valida elevated.allowFrom.telegram"
          - "handlers invocam ~/.openclaw/clarification-agent/cli.sh via execFile com --actor telegram:<sender_id>"
          - "pure helpers testaveis com DI: lib/parse.js + lib/format.js + lib/exec.js + lib/commands.js"
          - "37 unit tests node:test (zero npm install runtime)"
          - "reply-to-message inference dropado (SDK limitation); virou follow-up §8 ate SDK expor PluginCommandContext.replyToMessageId"
```

- [ ] **Step 4: Validar YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('~/bevox-knowledge/40_roadmap/delivery-tracker.yml'))" && echo OK
```

Expected: `OK`.

- [ ] **Step 5: Commit na branch draft**

```bash
cd ~/bevox-knowledge
git add 35_specs/2026-04-21-e10-telegram-reply-handler.md \
        40_roadmap/delivery-tracker.yml
git diff --cached --stat
git commit -m "$(cat <<'EOF'
delivery(E10): wave-3 telegram-reply-handler delivered

Operational Loop Hardening 2026-04-22 wave-3 completa. Plugin
clarification-commands em bernardTavares/knowledge-sync/plugins/ com 5
slash commands /clr_*. 37/37 unit tests node:test PASS.

Deltas da spec documentados inline:
- §3.4 reply-to-message dropado (SDK limitation), virou follow-up §8
- §4.6 auth via requireAuth: true (gateway valida; sem lib/auth.js)
- §5.2 entry via definePluginEntry (SDK real) nao function extension(api)

Loop operacional agora fechado: escalation unsafe -> wave-2 push Telegram
-> Bernard responde /clr_override no mesmo topico -> wave-1 daemon
resolve. Zero SSH necessario.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git log --oneline -3
```

Expected: novo commit acima do `delivery(E10): wave-2 telegram-push-escalations delivered`.

- [ ] **Step 6: NAO pushar.** Merge condicional ao bloco OH completo (wave-7 self-test pass).

---

## Checklist final

- [ ] **Testes suite completa** (Phase 1-3): 37/37 PASS.
- [ ] **Plugin source commitado** na branch `feat/e10-clarification-commands-plugin` do knowledge-sync (NÃO pushada).
- [ ] **Install runtime**: `~/.openclaw/extensions/clarification-commands/` tem espelho do source.
- [ ] **openclaw.json atualizado**: 3 entradas (allow, entries, installs); JSON valido.
- [ ] **Gateway reload**: 5 comandos `clr_*` aparecem no registro.
- [ ] **Smoke manual**: Bernard executou pelo menos `/clr_pending` e `/clr_show` com retorno correto.
- [ ] **Delivery commit bevox-knowledge**: spec status delivered + 3 delivery notes + tracker entry; branch draft ainda NÃO pushada.
- [ ] **Rollback plan**: `openclaw.json` backup em `.bak`; `plugins.entries.enabled: false` desativa sem remover files.

---

## Próximos passos pós-delivery wave-3

1. Bernard testa `/clr_*` live e reporta qualquer ajuste fino (formatação, truncation cutoffs, mensagens de erro).
2. Quando loop estiver estável (~1 semana), considerar push da feature branch em knowledge-sync → PR → merge em main.
3. **Wave-4 (payload-completeness-gate)** próxima — gate em nível de kanban que exige `spec_ref` + `acceptance_criteria` em toda nova task (wave-0 §3 → wave-4 enforcement universal).
4. Eventualmente reativar reply-to-message inference (§8 follow-up) quando/se SDK expor `replyToMessageId` em `PluginCommandContext`.
