# Spec — Tester + Reaper resilience vs claude-cli bugs

> **Status:** design aprovado (pendente review do escrito + writing-plans)
> **Data:** 2026-04-29
> **Decisor:** Bernard
> **Escopo:** OpenClaw runtime (tester-agent + dispatcher-agent reaper)
> **Branch sugerida:** `~/.openclaw`: `feat/tester-reaper-resilience`
> **Origem:** smoke real T-0109 (sprint-33 bevox-site, 2026-04-29 00:25 UTC) + smoke real T-0111 (mesmo dia, 00:50 UTC) — 3 bugs encadeados confirmados em produção

---

## 1. Contexto

### 1.1 Smoke real T-0109 (Bug A + Bug B)

T-0109 ("Bootstrap Next.js + TypeScript + Tailwind") executou com sucesso:
- Claude criou 25+ arquivos em `~/code/bevox-site/`
- Build local funcionou (`pnpm build` 3.9s, `.next/standalone` OK)
- Última `assistant text` na sessão JSONL às 00:11:19: "Bootstrap concluído. ACs cumpridos."
- **MAS** subprocess `claude -p` ficou pendurado idle 14min (Bug A: claude-cli não exitou)
- Reaper viu service `active running` → `T-0109: not_yet_finished` em 3 ticks
- Operador (eu) `systemctl stop` → SIGTERM → exit 0 → reaper finalizou
- Tester rodou ACs, leu `execution.log` que tinha **só metadata header** (Bug B: stdout buffer perdido no SIGTERM)
- Tester verdict: `test_inconclusive: "Execution log contém apenas metadata"`
- Recovery manual: extrai última msg do JSONL → anexa em execution.log → re-move pra testing → tester passa

### 1.2 Smoke real T-0111 (Bug C — descoberto após T-0109 recovery)

T-0111 entrou em mesma armadilha (inconclusive forçado por execution.log fraca). Tentei re-mover pra testing manualmente. **Reaper NÃO re-invocou tester** (bug C novo).

Investigação no `dispatcher-agent/lib/reaper.py:115`:
```python
if status.get("post_action_applied"):
    return "already_reaped"   # → skip permanente
```

`post_action_applied` é flag **permanente** marcada quando reaper aplicou a 1ª transição "executor exit → kanban testing". Não tem reset. Se tester volta inconclusive E task volta pra testing, reaper enxerga `already_reaped` e pula PRA SEMPRE.

Workaround manual hoje: `~/.openclaw/tester-agent/cli.sh check T-XXX` invoca tester direto, bypassa reaper.

## 2. Causa raiz (3 bugs encadeados)

### Bug A — `claude -p` não fecha após última assistant msg

Conhecido upstream do Claude CLI. `claude -p` em modo headless OU com `--resume` fica idle após responder final. Sem nosso controle direto. **Workaround**: reaper detecta finalização via JSONL e mata gracefully.

### Bug B — Tester depende de execution.log (fonte fraca)

`tester-agent/lib/context_loader.py` lê `dispatcher-agent/executions/<task>.log` que é só `--property=StandardOutput=append:...` do systemd-run. Vulnerável a:
- Buffer não-flushado no SIGTERM/SIGKILL
- `claude -p` que escreve só na última msg (perde tool_use intermediários)
- Qualquer interrupção entre "trabalho" e "flush"

**Fonte canônica real**: `~/.claude/projects/<project_path>/<session-id>.jsonl` — Claude escreve TUDO em append-only (assistant, user, tool_use, tool_result, thinking). Imune a buffer.

### Bug C — Reaper `post_action_applied` é flag permanente

Marca `True` na 1ª invocação do tester e **nunca reseta**. Mesmo se task volta pra testing após inconclusive (manual recovery, retry humano, scheduler externo), reaper trata como already_reaped → skip.

**Solução**: classify_execution consulta kanban_state.json também; detecta "task=testing E test_overall=inconclusive E backoff expirou" → resetar post_action_applied → próximo tick re-invoca tester.

## 3. Decisões travadas (Bernard 2026-04-29 brainstorming session)

| # | Pergunta | Decisão |
|---|---|---|
| 1 | Escopo desta wave | **Spec completa**: combo A+C + adição do Bug 3 (não fazer phased separado) |
| 2 | Trigger semantics do re-invoke (Bug C) | **State-driven**: reaper consulta `kanban-state.json`; detecta `status=testing` + `last_test_overall=inconclusive` + `post_action_applied=True` |
| 3 | Limite de re-invocações | **Sem limite, backoff exponencial** (sem cap de retries) |
| 4 | Backoff schedule | **Geometric ratio 3x, cap 10min**: `30s → 90s → 5min → 10min → 10min ...` |
| 5 | Idle finalization threshold (Bug A) | **3min default conservador** (env override `OPENCLAW_REAPER_IDLE_THRESHOLD`) |
| 6 | JSONL reading strategy | **Full file read + parse a cada tick** (não tail-N; performance OK pra tasks 1-10 paralelas) |

## 4. Arquitetura

```
┌──────────────────────────────────────────────────────────────┐
│  3 fontes de verdade que reaper agora cruza:                  │
│                                                                │
│  ~/.claude/projects/<path>/<sess>.jsonl  ← Claude session    │
│       │ (full file read each tick)                            │
│       ▼                                                        │
│  ~/.openclaw/dispatcher-agent/executions/T-XXX.status.json   │
│       │ (post_action_applied flag, finished_at, pid)          │
│       ▼                                                        │
│  ~/.openclaw/kanban-tasks/state.json                         │
│       │ (task.status + dispatch_payload.test_result)         │
│       ▼                                                        │
│  reaper decision (classify_execution):                         │
│   • idle_finalize    → SIGINT→SIGTERM→SIGKILL ladder         │
│                        (NOVO — Bug A)                          │
│   • still_running    → skip                                   │
│   • needs_reap       → wait next tick                         │
│   • needs_lifecycle  → invoke tester (cli.sh check)          │
│   • needs_reinvoke   → reset post_action + invoke tester      │
│                        (NOVO — Bug C)                          │
│   • already_reaped   → skip (idempotência preservada)        │
└──────────────────────────────────────────────────────────────┘

         ┌────────────────────────────────┐
         │  tester-agent recheck via cli  │
         │  ↓                              │
         │  context_loader.load_evidence()│
         │   ├─ JSONL primeiro (NOVO)     │
         │   └─ execution.log fallback    │
         └────────────────────────────────┘
```

**Boundaries**:
- `reaper.py` — ganha 2 estados novos (`needs_reinvoke`, `idle_finalize`); lê kanban-state e jsonl além do execution.status
- `context_loader.py` — ganha `load_session_evidence()` que lê JSONL; existing `load_execution_evidence()` vira fallback
- `tester-agent` invocação interna — sem mudança de interface; muda só onde `evidence` é carregada
- `dispatcher-agent/lib/runner.py` — sem mudança (continua escrevendo `execution.status` igual)

**Componentes que NÃO mudam**: notifier, clarification-agent, plugin Node, scrum-master.

## 5. Componentes (mudanças concretas em arquivos)

### 5.1 `tester-agent/lib/context_loader.py` — função nova

```python
def claude_project_dir(project_path: str) -> str:
    """~/code/bevox-site → -home-you-code-bevox-site"""
    p = os.path.expanduser(project_path or os.path.expanduser("~"))
    return p.replace("/", "-").rstrip("-")


def load_session_evidence(session_id: str, project_path: Optional[str] = None) -> Optional[dict]:
    """Lê ~/.claude/projects/<encoded_path>/<session_id>.jsonl (full file).

    Returns dict ou None se jsonl não encontrado/corrupto.
    {
      "session_id": str,
      "model": str | None,
      "started_at": str,
      "finished_at": str,
      "final_assistant_text": str,        # última msg type=text do assistant
      "tool_uses": list[dict],            # todos tool_use do assistant
      "tool_results": list[dict],         # todos tool_results
      "files_touched": list[str],         # extraídos de tool_use Write/Edit
      "raw_lines_count": int,
      "source": "jsonl",
    }
    """


def load_execution_evidence(task_id: str) -> dict:
    """EXISTING — reads execution.log (fallback path)."""


def load_evidence(task_id: str, session_id: Optional[str],
                  project_path: Optional[str]) -> dict:
    """Wrapper: tenta JSONL primeiro; cai pra execution.log se vazio.

    Returns dict com field `evidence_source` para audit ("jsonl"|"execution_log_fallback").
    """
```

### 5.2 Tester usa `load_evidence` (não direto load_execution)

Substituir `read_execution_log()` por `load_evidence(task_id, session_id, project_path)` onde tester monta contexto pra cada AC check. session_id e project_path vêm de:
- `session_id`: `task.dispatch_payload.execution_session_id`
- `project_path`: resolvido via projects-meta.json `local_repo_path` (depende spec irmã `local_repo_path`); fallback `$HOME` se ausente

### 5.3 `dispatcher-agent/lib/reaper.py` — 2 estados novos

```python
def classify_execution(status: dict, kanban_task: Optional[dict] = None,
                      session_jsonl_path: Optional[Path] = None) -> str:
    """
    Returns:
      'idle_finalize'    — alive + JSONL idle > 3min  (NOVO — Bug A)
      'still_running'    — alive + JSONL ativo
      'needs_reap'       — dead/no pid + sem finished_at
      'needs_lifecycle'  — finished_at + NÃO post_action_applied
      'needs_reinvoke'   — finished_at + post_action_applied + tester re-needed  (NOVO — Bug C)
      'already_reaped'   — finished_at + post_action_applied + tester OK
    """
    # 1. idle_finalize check (subprocess vivo mas Claude terminou)
    if status.get("finished_at") is None and status.get("pid") and _pid_alive(status["pid"]):
        if _detect_idle_finalize(session_jsonl_path):
            return "idle_finalize"
        return "still_running"

    if status.get("finished_at") is None:
        return "needs_reap"

    if not status.get("post_action_applied"):
        return "needs_lifecycle"

    # NOVO Bug C: needs_reinvoke
    if kanban_task and _needs_tester_reinvoke(kanban_task, status):
        return "needs_reinvoke"

    return "already_reaped"


def _detect_idle_finalize(jsonl_path: Optional[Path]) -> bool:
    """True se última msg = assistant text + sem tool_use + delta_t > 3min."""
    if not jsonl_path or not jsonl_path.exists():
        return False
    try:
        with open(jsonl_path) as f:
            lines = f.readlines()
    except OSError:
        return False
    last_assistant = None
    for line in reversed(lines):
        try:
            d = json.loads(line)
            msg = d.get("message", {})
            if msg.get("role") == "assistant":
                content = msg.get("content", [])
                has_tool_use = any(c.get("type") == "tool_use"
                                   for c in content if isinstance(c, dict))
                if has_tool_use:
                    return False  # ainda em tool chain
                last_assistant = d
                break
        except json.JSONDecodeError:
            continue
    if not last_assistant:
        return False
    ts = last_assistant.get("timestamp")
    if not ts:
        return False
    try:
        delta = (datetime.now(timezone.utc) - parse_iso(ts)).total_seconds()
    except (TypeError, ValueError):
        return False
    return delta > IDLE_FINALIZE_THRESHOLD_S


def _needs_tester_reinvoke(kanban_task: dict, exec_status: dict) -> bool:
    """True se kanban indica task voltou pra testing E último teste foi inconclusive
    E backoff window expirou.
    """
    if kanban_task.get("status") != "testing":
        return False
    tr = kanban_task.get("dispatch_payload", {}).get("test_result", {}) or {}
    if tr.get("last_test_overall") != "inconclusive":
        return False
    last_test_at = tr.get("last_test_finished_at")
    test_count = tr.get("test_run_count", 1)
    if not last_test_at:
        return True  # 1ª chance, sem record de "última"
    delay_seconds = _backoff_delay_for(test_count)
    try:
        elapsed = (datetime.now(timezone.utc) - parse_iso(last_test_at)).total_seconds()
    except (TypeError, ValueError):
        return False
    return elapsed >= delay_seconds


def _backoff_delay_for(retry_count: int) -> int:
    """Geometric ratio 3x, cap 10min (Bernard decisão #4)."""
    schedule = {1: 30, 2: 90, 3: 300, 4: 600}
    return schedule.get(retry_count, 600)


def _idle_finalize_action(task_id: str, status: dict) -> dict:
    """SIGINT → 15s grace → SIGTERM → 15s grace → SIGKILL.
    Marca exit_code=0 (workaround pro claude-cli não exitar).
    """
```

### 5.4 Reaper run loop — branches dos novos estados

Em `run()` do reaper, adicionar:

```python
elif cls == "idle_finalize":
    _idle_finalize_action(task_id, status)
    stats["idle_finalized_count"] = stats.get("idle_finalized_count", 0) + 1
    append_audit({"event": "idle_finalize_triggered", "task_id": task_id, ...})
    # próximo tick: status.finished_at será setado → cls=needs_lifecycle
elif cls == "needs_reinvoke":
    status["post_action_applied"] = False
    write_execution_status(task_id, status)
    stats["reinvoke_scheduled_count"] = stats.get("reinvoke_scheduled_count", 0) + 1
    append_audit({"event": "reinvoke_scheduled", "task_id": task_id,
                  "test_run_count": kanban_task.get("dispatch_payload", {})
                                              .get("test_result", {})
                                              .get("test_run_count")})
    # próximo tick: cls=needs_lifecycle (porque post_action=False) → invoca tester
```

### 5.5 Reaper main loop carrega kanban_state + jsonl_path por tick

```python
kanban_state = load_kanban_state()  # 1x/tick
for entry in execution_status_entries:
    task_id = entry["task_id"]
    task = next((t for t in kanban_state.get("tasks", []) if t.get("id") == task_id), None)
    sess_id = task.get("dispatch_payload", {}).get("execution_session_id") if task else None
    project = task.get("project") if task else None
    project_path = resolve_local_repo_path(project) if project else None  # spec irmã
    sess_path = (Path.home() / ".claude" / "projects"
                 / claude_project_dir(project_path or "~") / f"{sess_id}.jsonl") if sess_id else None
    cls = classify_execution(status, kanban_task=task, session_jsonl_path=sess_path)
    ...
```

### 5.6 Constantes ajustáveis

```python
# top of reaper.py
IDLE_FINALIZE_THRESHOLD_S = int(os.environ.get("OPENCLAW_REAPER_IDLE_THRESHOLD", "180"))
GRACE_SIGINT_SECONDS = 15
GRACE_SIGTERM_SECONDS = 15
REINVOKE_BACKOFF_SCHEDULE = {1: 30, 2: 90, 3: 300, 4: 600}  # geometric 3x, cap 10min
```

## 6. Data flow (3 cenários reais)

### 6.1 Cenário Bug A — proteção idle finalize

```
t=0       Cron-dispatcher pega T-0XXX → spawn claude-task subprocess
t=8min    Claude termina trabalho real, escreve "Concluído" no jsonl
          (mas subprocess fica idle, não exit)
t=8m+10s  Reaper tick: classify_execution()
          → finished_at=None, pid alive, _detect_idle_finalize: delta=10s < 180s → still_running
t=11min   Reaper tick: delta=3min na última msg
          → cls = idle_finalize
          → _idle_finalize_action: SIGINT
t=11m15s  Subprocess responde SIGINT → exit 0 → systemd marca finished_at
t=11m20s  Reaper tick: classify=needs_lifecycle → invoca tester via cli.sh check
t=11m45s  Tester rodou (lê JSONL primeiro) → pass → kanban=done
```

vs hoje: subprocess pendurado horas até alguém matar manualmente.

### 6.2 Cenário Bug B — JSONL primeiro

```
t=0       Tester invocado para T-0XXX
t=0+1s    load_evidence(task_id, session_id, project_path)
          → tenta load_session_evidence(session_id, project_path)
          → JSONL existe + parse OK
          → retorna evidence rica (final_assistant_text + tool_uses + files_touched)
t=0+30s   Tester valida ACs com contexto rico → pass
```

vs hoje: tester lia execution.log vazio (buffer perdido) → inconclusive forçado.

### 6.3 Cenário Bug C — re-invoke após inconclusive (T-0111 cenário real)

```
t=0       T-0YYY: tester run #1 → inconclusive → kanban move pra in_progress+blocked
          execution.status.post_action_applied=True
t=10s     Bernard ou recovery: kanban move T-0YYY de volta pra testing
t=20s     Reaper tick: classify_execution(status, kanban_task=T-0YYY)
          → finished_at exists + post_action_applied=True
          → _needs_tester_reinvoke check:
              kanban_task.status="testing" ✓
              last_test_overall="inconclusive" ✓
              elapsed = 20s; backoff_for(count=1) = 30s
              elapsed < delay → return False
          → cls = already_reaped → skip
t=35s     Reaper tick: elapsed = 35s ≥ 30s
          → _needs_tester_reinvoke = True → cls = needs_reinvoke
          → Reset post_action_applied=False, write_execution_status
          → audit: "reinvoke_scheduled" event
t=45s     Reaper tick: classify → needs_lifecycle (porque post_action=False)
          → invoca tester → tester run #2 → test_run_count=2
          → se ainda inconclusive: backoff_for(2)=90s, próxima janela em ≥90s
          → se pass: kanban=done; ciclo encerrado
```

vs hoje: após 1ª inconclusive, reaper pula pra sempre, tester só roda se Bernard chamar `cli.sh recheck` manual.

## 7. Error handling

| Falha | Resposta | Recovery |
|---|---|---|
| JSONL ausente | `load_session_evidence`: return None → `load_evidence` cai pra execution.log fallback | log info `evidence_source: execution_log_fallback` |
| JSONL corrupto | try/except json per-linha; pula linhas ruins; nenhuma válida → None | mesmo fallback |
| Path JSONL inferido errado | `claude_project_dir` tenta path conforme cwd inferido; 404 → None → fallback | audit `jsonl_path_not_found` |
| SIGINT ignorado | aguarda 15s → SIGTERM | próximo tick re-detecta → escala |
| SIGTERM ignorado | aguarda 15s → SIGKILL | systemd marca finished_at; reaper pega normal |
| SIGKILL falha (raríssimo) | log error crítico; NÃO marca finished_at | Bernard intervém manual |
| `_idle_finalize_action` mata subprocess que estava pensando entre tools | aceito: 3min é margem ampla; tester valida evidence parcial | se ACs cumpridos, pass; senão re-invoke loop |
| `kanban-state.json` corrupto/lock | try/except → log warning + degrade pra classify legado naquele tick | próximo tick (10s) tenta de novo |
| Reaper tick sobrepõe | systemd `--collect` + fcntl lock previne; warning `tick_skipped_lock` | N/A |
| Backoff: clock drift | usa `datetime.now(timezone.utc)` + NTP; drift <60s irrelevante | N/A |
| Tester crash em re-invoke | tester escreve `overall=error` → reaper vê `last_test_overall != inconclusive` → não re-invoca; task fica blocked | escalation flow normal |
| `test_run_count > 100` (loop patológico) | delay continua 600s cap; audit mostra count crescente | operador via `cli.sh recheck` ou `vox kanban task block` |
| Mesma task em status=testing por 2 caminhos paralelos | kanban-tasks tem fcntl lock interno; race não acontece na prática | N/A |

### 7.1 Resilience properties

1. **Idempotência preservada**: tasks done existentes não regridem (kanban.status≠testing)
2. **Sem loop infinito**: backoff cap 10min; custo controlado
3. **Sem dependência circular**: reaper lê kanban (RO); tester escreve test_runs; kanban escreve state
4. **Backwards compatible**: tasks com `post_action_applied=True` antigas (T-0008, T-0049) ficam intocadas (já em done/blocked terminal)
5. **Failure-isolated**: erro em qualquer dos 3 reads degrada graciosamente

## 8. Testing strategy

### 8.1 Unit tests (TDD)

| Componente | Tests críticos |
|---|---|
| `claude_project_dir(path)` | `~/code/bevox-site` → `-home-you-code-bevox-site`; `~` expansion; trailing `/` |
| `load_session_evidence(sess, path)` | jsonl válido → evidence rica; ausente → None; corrupto → None; empty → None; só user → final_text=""; tool_use extraction; files_touched |
| `load_evidence(task, sess, path)` | usa JSONL primeiro; fallback execution_log; `evidence_source` correto |
| `_detect_idle_finalize(jsonl)` | text + idle >180s → True; tool_use → False; idle <180s → False; missing → False; corrupt → False |
| `_needs_tester_reinvoke(task, status)` | testing+inconclusive+post_action+backoff_expired → True; status≠testing → False; pass → False; backoff window → False; sem last_test_finished_at → True (1ª) |
| `_backoff_delay_for(count)` | 1→30, 2→90, 3→300, 4→600, 5→600, 100→600 |
| `classify_execution(status, task, jsonl)` | matriz: 6 outcomes × várias combinações |

### 8.2 Integration tests

| Cenário | Setup | Expected |
|---|---|---|
| Idle finalize lifecycle | mock subprocess alive + jsonl c/ last text 4min atrás | reaper SIGINT → exit → next tick: needs_lifecycle |
| Re-invoke flow | seed kanban c/ status=testing+inconclusive+post_action+last_test 35s atrás | classify=needs_reinvoke → post_action reset → audit event |
| Backoff respect | seed kanban c/ inconclusive 10s atrás | classify=already_reaped (não re-invoca) |
| JSONL fallback | jsonl 404 + execution.log com conteúdo | tester usa execution_log; source field marcado |

### 8.3 Smoke E2E

```
1. Forçar task com idle artificial (sleep no executor) → reaper detecta + finaliza graceful
2. Forçar tester inconclusive (mock evidence vazia) → reaper re-invoca dentro de backoff
3. Forçar 5 inconclusives consecutivas → backoff escala até cap; sem crash
```

## 9. Plano de delivery (8 phases)

| Phase | Conteúdo | Risco | Reversível? |
|---|---|---|---|
| 0 | Branch `feat/tester-reaper-resilience` em `~/.openclaw` | baixo | sim |
| 1 | `claude_project_dir` + tests | baixo (TDD) | sim |
| 2 | `load_session_evidence` + tests (parsing edge cases) | médio | sim |
| 3 | `load_evidence` wrapper + integration tests | médio | sim |
| 4 | Tester usa load_evidence; smoke parcial mock | médio | sim |
| 5 | `_needs_tester_reinvoke` + `_backoff_delay_for` + tests; classify_execution ganha needs_reinvoke branch | médio | sim |
| 6 | Reaper run loop branch needs_reinvoke (reset post_action + audit) | alto (modifica runtime sensível) | sim (revert commit) |
| 7 | `_detect_idle_finalize` + `_idle_finalize_action` + tests; classify ganha idle_finalize branch + run loop trata | alto (mata processos) | sim |
| 8 | Smoke E2E real: criar task com idle artificial; criar task que força inconclusive | alto | sim |

Phases ordenadas por valor primeiro, risco depois: Bug 2 fix (1-4) sozinho já reduz inconclusives. Bug 3 fix (5-6) destrava re-invoke. Bug 1 fix (7-8) último porque mais arriscado e bug mais raro.

## 10. Acceptance criteria

- [ ] `claude_project_dir` codifica corretamente paths com `/`, `~`, trailing slash
- [ ] `load_session_evidence` retorna evidence rica em jsonl válido (T-0109 sample)
- [ ] `load_session_evidence` retorna None graciosamente em jsonl ausente/corrupto
- [ ] `load_evidence` usa JSONL primeiro; documenta `evidence_source` no test_run.json
- [ ] Tester com JSONL OK + execution.log vazio: passa nos ACs (cenário T-0109)
- [ ] `_detect_idle_finalize`: 4 cenários cobertos (idle/active/missing/corrupt)
- [ ] `_needs_tester_reinvoke`: matriz state-driven correta + backoff respeitado
- [ ] Reaper detecta `needs_reinvoke` e reseta `post_action_applied` → próximo tick re-invoca tester
- [ ] Reaper detecta `idle_finalize` e dispara SIGINT (audit registrado)
- [ ] Reaper escala SIGINT → SIGTERM → SIGKILL se ladder anterior falha
- [ ] env var `OPENCLAW_REAPER_IDLE_THRESHOLD` ajusta threshold
- [ ] Smoke E2E: task com inconclusive forçado → reaper re-invoca em ≤30s; backoff escala em re-invokes seguidos

## 11. Out of scope (anti-scope)

- ❌ Mudar `claude -p` upstream (fora do nosso controle)
- ❌ Refator do tester (continua chamado via `cli.sh check`)
- ❌ MC UI mostrando idle finalize / re-invoke timeline (vai pro inbox MC drill-down task)
- ❌ Métricas/dashboard de re-invoke rate (separado, observability wave)
- ❌ Notificação Telegram quando idle finalize dispara (separado, alert wave)
- ❌ Resilience pra outros providers além claude-cli
- ❌ Mudar tester-agent CLI interface (subcomando `check`/`recheck` permanecem)

## 12. Coordenação com waves em curso

Spec independente. NÃO bloqueia:
- Wave clarification-reply (Tasks 12-13 docs ainda pending)
- Spec local_repo_path (esta spec USA `local_repo_path` se disponível, fallback $HOME se não)
- Spec tester-commit-push-and-sprint-branching

Beneficia diretamente: smoke real em curso (T-0111+ destravam automaticamente).

## 13. Referências

- **Smoke origem 1**: T-0109 sprint-33 bevox-site (2026-04-29 00:11-00:25 UTC) — Bug A + Bug B
- **Smoke origem 2**: T-0111 sprint-33 bevox-site (2026-04-29 00:50 UTC) — Bug C confirmado
- **Session jsonl exemplo**: `~/.claude/projects/-home-you-code-bevox-site/9b6d9a04-ffa7-4e08-94fc-336abf6b784b.jsonl` (832KB, demonstra estrutura)
- **Tester atual**: `~/.openclaw/tester-agent/lib/context_loader.py:read_execution_log`
- **Reaper atual**: `~/.openclaw/dispatcher-agent/lib/reaper.py` (`classify_execution` + `run`)
- **Specs paralelas**:
  - `2026-04-28-clarification-reply-via-gateway-plugin-design.md` (em execução, Tasks 12-13 pending)
  - `2026-04-28-project-local-repo-path.md` (pronta, hotfix interim aplicado)
  - `2026-04-28-tester-commit-push-and-sprint-branching.md` (pronta, futuro)
- **CLAUDE.md OpenClaw**: §6 (regras de trabalho), §8 (autonomia — kill processes é sensível)
