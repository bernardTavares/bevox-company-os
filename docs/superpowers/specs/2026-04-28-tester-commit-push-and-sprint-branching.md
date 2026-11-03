# Spec — Tester commit+push e branching por sprint

> **Status:** proposto (investigativo + direção indicada)
> **Data:** 2026-04-28
> **Decisor:** Bernard
> **Owner sugerido:** sessão dedicada futura
> **Escopo:** OpenClaw runtime (kanban-tasks, scrum-master, dispatcher, tester) + Mission Control + projects-meta + bevox-knowledge
> **Branch sugerida:**
> - `~/.openclaw`: `feat/tester-commit-push-and-sprint-branching`
> - `~/bevox-knowledge`: `draft/sprint-branching-spec`
> - `~/code/mission-control`: `feat/sprint-branch-ui`
> **Origem:** smoke real T-0104..T-0107 (sprint-33 bevox-site, 2026-04-28) revelou que tester aprova mas deliverables ficam untracked indefinidamente

---

## 1. Contexto

Investigação após smoke real:

1. **4 specs canônicas escritas pelo executor** durante tasks T-0104..T-0107 ficaram **untracked em bevox-knowledge** (`status: ??`):
   - `35_specs/bevox-site/2026-04-27-bevox-site-prd-pendencias-v1.md`
   - `35_specs/bevox-site/2026-04-27-bevox-site-idiomas-v1.md`
   - `35_specs/bevox-site/2026-04-27-bevox-site-ctas-v1.md`
   - `35_specs/bevox-site/2026-04-27-bevox-site-fallback-mobile-v1.md`

2. **Tester aprovou** (`overall: pass`, `decision: done`) e tasks foram movidas para `done` no kanban.

3. **Ninguém commita**. Bernard precisa fazer manualmente. Não há gate operacional, alerta, ou enforcement.

4. Inventário do código (verificado em 2026-04-28):
   - `tester-agent/lib/`: ZERO git ops
   - `dispatcher-agent/lib/`: ZERO git ops
   - `scrum-master-agent/lib/`: ZERO git ops
   - `kanban-tasks/lib/`: ZERO git ops
   - `mission-control/src/`: ZERO `git checkout`/`git branch`
   - `kanban-state.json` task schema: nenhum field `branch`
   - `kanban-state.json` sprint schema: nenhum field `branch`
   - `bevox-knowledge/30_adr/`: ZERO ADR sobre git workflow / branch strategy

**Pain real**: O sistema gerencia decisões/specs completamente — kanban → dispatcher → executor → tester. Mas o **commit/push/branch lifecycle** é 100% manual e fora do loop. Tester pode aprovar 50 tasks num sprint e Bernard ter que rastrear o que foi feito e commitar tudo manualmente.

## 2. Direção indicada por Bernard (2026-04-28)

Bernard explicitou o modelo:
- **Tester deve fazer commit+push** após approve.
- **Branch é por sprint** (não por task).
- **Quando criamos uma sprint** (ou primeira task de um sprint), branch é criada/configurada.
- **Ao fim do sprint**, merge da branch na `main`.

Esta spec **adota essa direção como decisão** e investiga apenas:
- Como criar/registrar a branch da sprint sem fricção (auto-criar? manual via MC?)
- Como tester sabe qual branch usar (lê de sprint? task? meta?)
- Como tratar repos sem `local_repo_path` configurado (depende da spec irmã)
- Política de merge (manual via MC button? auto on sprint close? PR para review?)

## 3. Decisões travadas vs investigar

| # | Decisão (travada por Bernard) |
|---|---|
| 1 | Branch é por **sprint**, não por task |
| 2 | **Tester** é o agente que faz `git commit` + `git push` após approve |
| 3 | Merge para `main` é manual no **fim do sprint** (não automático) |
| 4 | Branch lives na **mesma working dir do projeto** (depende de `local_repo_path` — spec irmã `2026-04-28-project-local-repo-path.md`) |

| # | Investigar |
|---|---|
| A | Branch é criada quando? (a) ao criar sprint via MC; (b) ao primeira task da sprint ir pra `ready`; (c) ao primeiro tester pass; (d) outro |
| B | Naming convention da branch: `sprint-33`? `feat/sprint-33-bevox-site`? `<project>/sprint-<n>`? |
| C | Onde persistir branch name: `kanban-state.sprints[].branch`? `projects-meta`? Inferido pelo naming? |
| D | Multi-projeto na mesma sprint é possível? (Hoje sprints têm campo `project` único — então 1 sprint = 1 projeto = 1 repo = 1 branch.) |
| E | Como tester sabe qual repo+branch? Lê `local_repo_path` do projeto via spec irmã + `branch` da sprint |
| F | Política para tester se commit/push falhar (push rejected, conflict, etc.): escala clarification? Re-tenta? Marca task como `done_uncommitted`? |
| G | Como Bernard fecha o sprint via MC? Botão "Close sprint" → checa branch limpa + dispara merge wizard? |
| H | Como tratar repos com remote diferente (e.g. `bevox-knowledge` que NÃO está em `bernardTavares/`)? |
| I | Pre-existing changes não relacionadas à task: tester ignora? agrega? escala? |
| J | Múltiplas tasks da mesma sprint que mexem em arquivos sobrepostos: ordem de commit? |
| K | Co-author do commit: tester? executor? Bernard? |
| L | Tester deve rodar tests/lint antes do commit? (CI-like gate antes de push) |
| M | Como integrar com workflow de PR caso Bernard queira review humano (em vez de merge direto)? |

## 4. Estado atual mapeado

### 4.1 Schema atual

**Task** (`kanban-state.json:tasks[]`): 16 fields, **nenhum sobre git**.

**Sprint** (`kanban-state.json:sprints[]`): 7-8 fields (id, name, state, project, created_at, closed_at, created_by, opcional `execution_session_id`). **Nenhum sobre branch**.

**Project** (`projects-meta.json:projects.<slug>`): tem `github_url` (URL remoto). Sem `default_branch`, sem `branch_pattern`.

### 4.2 Agentes vs git

| Agente | Git ops hoje | Esperado pós-spec |
|---|---|---|
| scrum-master | nenhum | (talvez) registra branch ao criar sprint |
| dispatcher (cron + spawn) | nenhum | nenhum (executor já roda em cwd correto via spec local_repo_path) |
| executor (Claude Code) | nenhum (vimos transcript de T-104..107) | nenhum — só escreve arquivos; tester commita |
| tester | nenhum | **commit + push pra branch da sprint** |
| reaper | nenhum | nenhum |
| MC | nenhum | UI pra criar branch ao criar sprint + close sprint com merge wizard |

### 4.3 Workflow operacional atual (com gap)

```
1. Bernard cria sprint → kanban registra; ZERO ação git
2. Bernard adiciona tasks → ZERO ação git
3. Bernard move task pra ready
4. Cron-dispatcher pega task → spawn claude (cwd=$HOME hoje; cwd=local_repo_path pós-spec irmã)
5. Executor faz Write em paths absolutos → arquivo escrito mas UNTRACKED
6. Tester aprova → task=done; ZERO commit
7. Bernard precisa rastrear manualmente o que foi feito + git add + commit + push
8. Sprint fecha → ZERO automação merge
```

## 5. Workflow proposto (alvo)

```
1. Bernard cria sprint <N> em projeto <slug> via MC
   → MC API: POST /api/sprints
     - cria sprint no kanban
     - resolve local_repo_path do projeto (spec irmã)
     - executa em <local_repo_path>:
        git fetch origin
        git checkout -b sprint-<N> origin/main      (ou base configurável)
     - persiste sprint.branch = "sprint-<N>" em kanban
     - persiste sprint.base_branch = "main" (configurável)
   → Bernard vê na UI: "Sprint 33 · branch sprint-33 (de main, fresh)"

2. Bernard adiciona tasks na sprint → kanban; nada git

3. Cron-dispatcher pega task ready
   → spawn claude com cwd=local_repo_path (spec irmã)
   → executor faz Write/Edit; ZERO git ops por design

4. Tester aprova:
   → status=done; persiste test_result
   → NOVO: TesterCommitter sub-agente:
      a. cd local_repo_path
      b. git checkout sprint-<N>  (no-op se já estiver)
      c. git status --porcelain → identifica mudanças
      d. git add <arquivos do deliverable> (lista vem de tester evidence: paths citados em sources)
      e. git commit -m "<task_id>: <task_title>\n\nCo-Authored-By: openclaw-tester <noreply@example.com>"
      f. git push origin sprint-<N>
      g. persiste task.dispatch_payload.git_commit_sha + git_push_at em kanban
      h. emit_event "task_committed" em kanban-events
   → on git failure: escala clarification "commit_failed: <stderr>"; status fica done_uncommitted; Bernard intervém

5. Bernard fecha sprint via MC "Close Sprint"
   → MC API: POST /api/sprints/<N>/close
     - valida: todas tasks done|rejected|deferred?
     - valida: branch sprint-<N> tem N commits = M tasks done?
     - opções:
        a. merge direto: git checkout main && git merge --no-ff sprint-<N> && git push
        b. abrir PR via gh CLI: gh pr create --base main --head sprint-<N> --title "Sprint <N>" --body <auto-summary>
     - persiste sprint.merged_at + sprint.merged_via=("direct"|"pr") em kanban
     - opcional: deleta branch local após merge (mantém remote)
```

## 6. Componentes a desenhar (preview, não-final)

### 6.1 Schema additions

**Sprint**:
```json
{
  "id": "sprint-33",
  "branch": "sprint-33",                  // novo
  "base_branch": "main",                   // novo
  "branch_created_at": "2026-04-28T...Z",  // novo
  "merged_at": null | "2026-04-...Z",      // novo
  "merged_via": null | "direct" | "pr",    // novo
  "pr_url": null | "https://...",          // novo (opcional)
  ...
}
```

**Task**:
```json
{
  "id": "T-0105",
  "dispatch_payload": {
    "git_commit_sha": "abc1234",          // novo (após tester commit)
    "git_committed_at": "2026-04-28T...",  // novo
    "git_pushed_at": "2026-04-28T...",     // novo
    ...
  }
}
```

### 6.2 Novo módulo: `tester-agent/lib/committer.py`

Função pura `commit_task_deliverable(task, sprint, local_repo_path) -> CommitResult`. Subprocess git ops. Retorna SHA + push status. Idempotente (skip se já commitado).

### 6.3 Novo subcomando: `tester-agent/cli.sh commit-deliverable <task_id>`

Manualmente reexecutar commit se falhou. Útil pra recovery.

### 6.4 MC backend novo

- `POST /api/sprints` aceita `{base_branch?: string}`; cria branch via subprocess git
- `POST /api/sprints/<id>/close` orquestra merge OR PR creation (gh CLI)
- `GET /api/sprints/<id>` retorna `branch`, `commits_count`, `merged_at`
- `POST /api/tasks/<id>/recommit` chama `cli.sh commit-deliverable` (recovery)

### 6.5 MC frontend novo

- Sprint Geral tab: card "Branch: sprint-33 · 4 commits · ahead 4 of main"
- "Close Sprint" wizard: 2 opções (merge direto / abrir PR)
- Task detail: mostra `git_commit_sha` clickable (link pro commit no GitHub)
- Indicador visual nas tasks: ✅ commitada / ⚠️ done_uncommitted

### 6.6 Configuração

Por projeto em `projects-meta.json`:
```json
"bevox-site": {
  "default_base_branch": "main",        // novo (default 'main')
  "merge_strategy": "direct" | "pr",    // novo (default 'pr')
  "pr_template": "..."                   // novo (opcional)
}
```

## 7. Edge cases

| Caso | Comportamento |
|---|---|
| Repo não clonado em `local_repo_path` | Bloquear via spec irmã (escala clarification antes mesmo de spawnar executor) |
| Branch já existe localmente quando criar sprint | `git checkout -B` (force; assume idempotência) ou erro? Investigar |
| Working tree dirty antes de criar sprint | Tester rejeita ou avisa? |
| 2 tasks da mesma sprint commitam o MESMO arquivo | OK — git lida; commits sequenciais |
| Conflict no commit (race entre 2 tasks paralelas) | Lock no `local_repo_path` durante tester commit; serializar |
| Push rejected (branch atrás do remote) | Tester puxa + rebase + retry; se conflict, escala |
| Tester quer commitar arquivo fora do projeto | Reject — só commita arquivos dentro de `local_repo_path` |
| Deliverable em outro repo (ex: spec em `bevox-knowledge` mas código em `bevox-site`) | Multi-repo commit: tester detecta e commita em CADA repo separadamente. Investigar política |
| Bernard quer pular commit (apenas spec didática) | Flag `--skip-commit` em task ou em payload? |
| Tasks rejeitadas/deferred no fim do sprint | Não commitam mas branch fica; merge ignora |

## 8. Integração com spec irmã `local_repo_path`

**Esta spec depende de `2026-04-28-project-local-repo-path.md` estar implementada.**

- Tester precisa saber onde está o repo do projeto → resolve via `local_repo_path`.
- Sem essa spec, tester não tem cwd correto pra fazer git ops.

**Ordem sugerida de implementação**:
1. Spec `local_repo_path` (irmã) → entregue primeiro
2. Esta spec → consume + adiciona git layer

## 9. Plano de delivery (sugerido)

| Phase | Conteúdo | Risco | Depende de |
|-------|---|---|---|
| 0 | Spec `local_repo_path` entregue + smoke validado | — | irmã |
| 1 | ADR canônica em `bevox-knowledge/30_adr/openclaw/`: "Branch-per-sprint, tester-commit, manual-merge-on-close" | baixo | — |
| 2 | Schema additions: sprint.branch, sprint.merged_*, task.git_commit_sha + migrations | baixo | — |
| 3 | `tester-agent/lib/committer.py` com tests + cli.sh commit-deliverable | médio | local_repo_path |
| 4 | Tester invoca committer no fim do flow approve | médio | 3 |
| 5 | MC: POST /api/sprints (cria branch via subprocess) | médio | — |
| 6 | MC: POST /api/sprints/<id>/close (merge OR PR) | alto | 5 |
| 7 | MC frontend: sprint card, task commit indicator, close wizard | médio | 5,6 |
| 8 | Smoke test: criar sprint nova, 2 tasks, executar, tester commit, fechar sprint, merge | alto | 3-7 |
| 9 | Atualizar workspace-template + bevox-knowledge ADR/spec aceitos | baixo | — |

## 10. Critérios de aceitação

- [ ] Sprint nova criada via MC inicia com `branch=sprint-<N>` em `local_repo_path`
- [ ] Branch criada a partir de `base_branch` (default `main`); persistida em kanban
- [ ] Tester após approve: commit + push (push pode falhar com retry; ver §7)
- [ ] task.dispatch_payload contém `git_commit_sha` + `git_pushed_at`
- [ ] MC mostra branch e commit count no sprint detail
- [ ] MC "Close Sprint" oferece merge direto OU PR (configurável por projeto)
- [ ] Repos com `local_repo_path` ausente: tester emite warning estruturado, task vira `done_uncommitted` (não falha task)
- [ ] Recovery: `cli.sh commit-deliverable <task>` reexecuta commit (idempotente)
- [ ] Multi-repo: detecta deliverables em mais de 1 repo; commita em cada (investigar política)
- [ ] Conflict/race: lock por repo; serializa commits da mesma sprint
- [ ] Smoke E2E: sprint do início ao merge, sem intervenção manual em git

## 11. Out of scope (anti-scope)

- ❌ CI/CD pipeline integration (tests/lint pre-commit) — futura wave
- ❌ Code review automatizado (tester já faz validação por AC; review ≠ test)
- ❌ Automatic conflict resolution
- ❌ Squash/rebase strategy decisions (mantém merge default; configurável depois)
- ❌ Multi-base-branch workflow (cada projeto tem 1 base; spec assume)
- ❌ Branch protection rules sync (GitHub side; manual via repo settings)
- ❌ Tag/release management (separado)
- ❌ Hotfix workflow (sprint dedicado serve)

## 12. Coordenação com waves em curso

### Wave em execução (esta sessão): clarification-reply-via-gateway-plugin

Tasks 12-13 da wave atual NÃO bloqueiam esta spec. Tasks 12 = workspace-template docs; 13 = bevox-knowledge docs. **Sem overlap em arquivos** com esta spec.

### Spec irmã: local_repo_path

Esta spec **depende** dela. Implementar local_repo_path **primeiro**.

### Sessão paralela (se aberta)

Mesmas regras da spec irmã (branch nova, sem overlap em runtime services, sem restart durante smoke ativo).

## 13. Perguntas-guia para o brainstorm de implementação

(Quem for implementar deve responder essas antes do plano detalhado)

1. Branch naming: `sprint-<N>` ou `<project>/sprint-<N>` ou outro?
2. Branch criação trigger: ao criar sprint, ao primeira task ready, ou outro?
3. Tester commit timing: imediatamente após approve, ou em batch?
4. Merge timing: fim do sprint apenas, ou opt-in por task?
5. Política de PR: Bernard escolhe por projeto, ou por sprint?
6. Co-author convention: incluir `Co-Authored-By: <executor-model>`?
7. Lock granularity: por repo, por sprint, ou nenhum (assume serial)?
8. Recovery UX: button MC, CLI, ambos?
9. Auditoria: events.jsonl novo `task_committed`, `sprint_merged`?
10. Pre-commit hooks: respeitar (gate) ou bypassar (`--no-verify` proibido por CLAUDE.md)?
11. Reaper futuro: detectar tasks `done_uncommitted` antigas e re-tentar?

## 14. Referências

- **Spec irmã (dependência)**: `~/.openclaw/docs/superpowers/specs/2026-04-28-project-local-repo-path.md`
- **Origem**: smoke real T-0104..T-0107 sprint-33 bevox-site (2026-04-28); investigação git ops em todos agentes (zero hits)
- **Wave atual**: `~/.openclaw/docs/superpowers/specs/2026-04-28-clarification-reply-via-gateway-plugin-design.md`
- **PRD correlato**: `~/bevox-knowledge/10_prd/_shared/2026-04-28-knowledge-as-living-system-investigation-prd.md` — gap doc untracked também aparece lá
- **CLAUDE.md OpenClaw**: §6 (regras de trabalho), §7 (git workflow), §8 (autonomia — git push é sensível, requer approval)
