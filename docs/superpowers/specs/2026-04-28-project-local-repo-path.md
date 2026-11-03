# Spec — Project local_repo_path + cwd injection no executor

> **Status:** proposto
> **Data:** 2026-04-28
> **Decisor:** Bernard
> **Owner sugerido:** sessão paralela (terminal separado)
> **Escopo:** OpenClaw runtime (scrum-master + dispatcher) + Mission Control + projects-meta
> **Branch sugerida:**
> - `~/.openclaw`: `feat/local-repo-path-per-project`
> - `~/bevox-knowledge` (se ADR/spec): `draft/local-repo-path-spec`
> - `~/code/mission-control` (se houver): `feat/local-repo-path`
> **Origem:** smoke real T-0107 da sprint-33 bevox-site (2026-04-28) revelou que executor Claude Code roda com `cwd=$HOME` sem mapping `project → repo path`

---

## 1. Contexto

Investigação após smoke real:

1. `dispatcher-agent/lib/runner.py:84-95` invoca `systemd-run --user` SEM `--property=WorkingDirectory=...` → executor recebe `cwd=$HOME` (`!~`).
2. Briefings (`dispatcher-agent/briefings/T-XXXX.md`) NÃO mencionam working_directory ou repo path.
3. `projects-meta.json` tem `github_url` (URL remoto) mas **não** `local_repo_path`.
4. MC backend (`~/code/mission-control/`) lê `github_url` do meta e expõe na UI Geral tab; tem `/api/git` route que descobre repos por `find ~/.openclaw/workspace -maxdepth 2 -name .git` — mas isso é dashboard de workspace compartilhado, não mapping per-project.
5. Bernard já está organizando repos em `~/code/<slug>/` (vimos `bevox-site` e `mission-control` lá). Esta spec **adota essa convenção como canônica**.

**Pain real**: para tasks de implementação (não só specs em markdown), executor não sabe onde fazer `git clone`, `cd`, ou onde estão os arquivos do repo do projeto. Hoje tasks como T-0105/106/107 entregam markdown em `bevox-knowledge/35_specs/...` e funcionam por convenção implícita ($HOME + paths relativos resolvendo). Mas a próxima task que tocar código real do site (e.g. componente React) vai falhar silenciosamente ou precisar de explicação manual no briefing.

## 2. Decisões travadas no framing (2026-04-28)

| # | Decisão | Justificativa |
|---|---|---|
| 1 | **Convenção canônica `~/code/<project_slug>/`** | Bernard já organizando lá; uniforme entre projetos |
| 2 | **Override opcional em `projects-meta.json:projects.<slug>.local_repo_path`** | Casos especiais: `bevox-knowledge` em `~/bevox-knowledge`, `openclaw` em `~/.openclaw` |
| 3 | **Editável via Mission Control** (Geral tab, ao lado de github_url) | Bernard mantém controle visual |
| 4 | **Dispatcher injeta `cwd` no subprocess** via `--property=WorkingDirectory=<path>` no `systemd-run` | Executor já abre no path certo, sem precisar `cd` no Claude |
| 5 | **Briefing também menciona path** (seção `## Working directory`) | Redundância: se Bernard ler briefing, sabe onde executor está |
| 6 | **Validação no dispatcher antes de spawnar** | Se path não existe, falha cedo + escala clarification automática |

## 3. Arquitetura

```
projects-meta.json
  projects.<slug>.local_repo_path: "~/code/<slug>"
        │ (opcional override; default = ~/code/<slug>)
        ▼
scrum-master-agent.materializer
  lê projects-meta + resolve path
  injeta no briefing:
    ## Working directory
    `<resolved_path>`
        │
        ▼
dispatcher-agent.runner
  - lê path do dispatch_payload (passed via materializer)
  - valida dir existe (escala clarification se não)
  - systemd-run --user --property=WorkingDirectory=<path>
        │
        ▼
claude-task-T-XXXX.service
  ExecStart com cwd = <path>
  (executor já abre dentro do repo do projeto)
```

## 4. Componentes

### 4.1 `projects-meta.json` schema (host-local)

Campo novo opcional por projeto:

```json
{
  "projects": {
    "bevox-site": {
      "name": "Bevox Site",
      "github_url": "https://github.com/bernardTavares/bevox-site",
      "local_repo_path": "~/code/bevox-site",   // novo (opcional)
      ...
    }
  }
}
```

**Resolução** (função pura no scrum-master + dispatcher):

```python
def resolve_local_repo_path(project_slug: str, meta: dict) -> Optional[str]:
    """Resolve local_repo_path com fallback para convenção canônica.

    1. Lê meta.projects[slug].local_repo_path se existir → usa.
    2. Senão default: ~/code/<slug>.
    3. Retorna None se slug não está em meta E projeto não tem fallback aplicável
       (e.g. tasks sem campo project — caem no fallback $HOME atual).
    """
    if not project_slug:
        return None
    entry = meta.get("projects", {}).get(project_slug, {})
    if isinstance(entry, dict):
        path = entry.get("local_repo_path")
        if path:
            return os.path.expanduser(path)
    return f"~/code/{project_slug}"
```

### 4.2 `scrum-master-agent` — briefing builder

Onde está hoje: `~/.openclaw/scrum-master-agent/lib/materializer.py`.

Modificação: ao montar briefing, ler `local_repo_path` via resolver e adicionar 2 coisas:

(a) Seção nova logo abaixo de `**Epic/Wave:**`:

```markdown
## Working directory

`<resolved_path>`

(executor já será aberto neste path pelo dispatcher; comandos relativos devem ser relativos a este diretório)
```

(b) Persistir `local_repo_path` no `dispatch_payload` da task (para o dispatcher ler depois sem repetir resolução):

```python
dispatch_payload["local_repo_path"] = resolved_path  # ou None
```

### 4.3 `dispatcher-agent/lib/runner.py` — systemd-run injection

Atual (linha ~84-95):

```python
sd_cmd = [
    "systemd-run", "--user",
    f"--unit={unit_name}",
    "--collect",
    "--property=Type=exec",
    f"--property=StandardOutput=append:{log_path}",
    "--property=StandardError=inherit",
    "--",
    "claude", "-p", briefing_content,
    *claude_session_arg,
    "--allowedTools", allowed_tools,
]
```

Novo: ler `local_repo_path` do dispatch_payload (passado via parâmetro novo `local_repo_path: Optional[str]` ao `spawn_claude`); se não None E dir existe, adicionar:

```python
if local_repo_path and Path(local_repo_path).is_dir():
    sd_cmd.insert(-2, f"--property=WorkingDirectory={local_repo_path}")
```

Posição: **antes** do `--` (final dos --property).

### 4.4 Validação pré-spawn

Em `dispatcher-agent/lib/runner.py` (ou nivel acima em `lifecycle.py` que chama spawn_claude):

```python
if local_repo_path and not Path(local_repo_path).is_dir():
    # Escala clarification automática informando Bernard
    lifecycle_clarification.emit_payload_incomplete_escalation(
        task_id,
        missing_fields=[f"local_repo_path={local_repo_path} não é diretório existente"],
    )
    return  # NÃO spawna executor
```

Nota: reusar `emit_payload_incomplete_escalation` de `clarification-agent/lib/lifecycle.py` (já existe pra dispatch_payload incompleto). Adaptar mensagem.

### 4.5 Mission Control — UI + API

**Backend** (`~/code/mission-control/src/app/api/projects/route.ts` e `/api/projects/<slug>/edit/route.ts`):

- GET `/api/projects/<slug>`: retornar field `local_repo_path` (lendo de meta).
- PATCH `/api/projects/<slug>/edit`: aceitar body `{ local_repo_path: string | null }` e persistir em `projects-meta.json`.

**Frontend** (`~/code/mission-control/src/components/projects/ProjectGeralTab.tsx`):

- Adicionar campo editável "Local repo path" ao lado do github_url.
- Placeholder: `~/code/<slug>` (mostra default que será usado se vazio).
- Validação leve: warning se path começa com `~` (sugerir expandir).
- Indicador visual: ícone verde se diretório existe, vermelho se não (chamar endpoint `/api/git/check?path=...` opcional).

**Default behavior**: se campo vazio na UI, MC envia `null` ao PATCH; resolver retorna fallback `~/code/<slug>`. Bernard só preenche pra overrides.

### 4.6 Migração inicial

Script one-off: `~/.openclaw/scripts/migrate-projects-local-repo-path.py`

```python
"""Popular local_repo_path em projects-meta para casos especiais conhecidos."""
import json
from pathlib import Path

OVERRIDES = {
    "bevox-knowledge": "~/bevox-knowledge",
    "openclaw": "~/.openclaw",
}

meta_path = Path.home() / ".openclaw" / "projects-meta.json"
with open(meta_path, "r") as f:
    meta = json.load(f)
for slug, path in OVERRIDES.items():
    entry = meta.setdefault("projects", {}).setdefault(slug, {})
    if isinstance(entry, dict):
        entry["local_repo_path"] = path
with open(meta_path, "w") as f:
    json.dump(meta, f, indent=2, ensure_ascii=False)
print(f"Migrated overrides: {list(OVERRIDES.keys())}")
```

Rodar uma vez após deploy. Idempotente.

## 5. Data flow end-to-end

```
1. Bernard cria task no MC (project=bevox-site)
2. Scrum-master materializa briefing:
   - resolve local_repo_path = ~/code/bevox-site
   - injeta seção ## Working directory no briefing
   - persiste em dispatch_payload.local_repo_path
3. Cron-dispatcher pega task ready, lê dispatch_payload
4. runner.spawn_claude(local_repo_path=...):
   - valida dir existe (se não → escala + return)
   - systemd-run --user --property=WorkingDirectory=~/code/bevox-site
5. Claude subprocess executa COM cwd correto
6. Comandos relativos do executor (Read, Bash) operam no repo
7. cli.sh ask continua funcionando (paths absolutos pra clarification-agent)
```

## 6. Edge cases

| Caso | Comportamento |
|---|---|
| Task sem `project` | `local_repo_path = None` → não passa WorkingDirectory → cwd=$HOME (comportamento atual) |
| `local_repo_path` em meta mas dir não existe | Escala clarification automática "repo não clonado em <path>" |
| `local_repo_path` no meta usa `~` | Resolver expande `os.path.expanduser` antes de validar |
| Repo existe mas sem `.git` | Aceita (dir suficiente; warning leve no log) |
| 2 projetos com mesmo `local_repo_path` (override duplicado) | Aceita; cada task usa seu próprio resolution; sem chequinho de uniqueness |
| Bernard edita meta enquanto cron-dispatcher rodando | OK; meta é lido a cada tick |

## 7. Out of scope

- **Clone automático** se repo não existe (nesta wave; escala clarification é suficiente).
- **Branch management** (executor decide se faz commit/PR — fora do escopo).
- **Permissions check** (`os.access(path, os.R_OK)` etc.) — assume Bernard configurou direito.
- **Multi-repo workflows** (1 task tocando múltiplos repos) — seguir hoje com paths absolutos no briefing manualmente.
- **Cwd para `tester-agent` / `clarification-agent`** — esses são agentes Python locais que rodam em `~/.openclaw/...`, não relevantes.

## 8. Plano de delivery (sugerido)

| Phase | Conteúdo | Risco |
|---|---|---|
| 0 | Criar branch `feat/local-repo-path-per-project` em `~/.openclaw`; rodar migrate-projects script (popula overrides bevox-knowledge + openclaw) | baixo |
| 1 | Schema field + resolver function em `scripts/lib/projects_meta.py` (ou similar) + tests | baixo (TDD) |
| 2 | `scrum-master-agent/lib/materializer.py`: injeção de seção `## Working directory` + persistência em dispatch_payload | médio (briefing format change) |
| 3 | `dispatcher-agent/lib/runner.py`: `--property=WorkingDirectory` no systemd-run + validação pré-spawn + escala se ausente | médio (mudança runtime sensível) |
| 4 | MC backend: GET expor field + PATCH aceitar | baixo |
| 5 | MC frontend: campo editável + indicador visual | baixo |
| 6 | Smoke test: criar task em bevox-site, verificar executor abre em `~/code/bevox-site` | médio (E2E) |
| 7 | Smoke test edge: criar task em projeto sem repo clonado → escalation automática | baixo |
| 8 | Atualizar workspace-template `memory/integrations/dispatcher.md` + `AGENTS.md` para mencionar working directory | baixo |
| 9 | Atualizar bevox-knowledge: ADR (talvez ADR-012) ou extension annotation em ADR existente + spec canônica em `35_specs/openclaw/` | baixo (em branch draft) |

## 9. Critérios de aceitação

- [ ] `projects-meta.json` aceita field `local_repo_path` opcional por projeto
- [ ] Resolver retorna `~/code/<slug>` por default; override quando setado
- [ ] Migração popular overrides bevox-knowledge + openclaw
- [ ] Briefing gerado contém seção `## Working directory` com path absoluto
- [ ] `systemd-run` recebe `--property=WorkingDirectory=<path>` quando aplicável
- [ ] `inspect_service` confirma `WorkingDirectory=<path>` (não mais `!~`)
- [ ] Validação: task com path inexistente escala clarification (não roda Claude)
- [ ] MC mostra + permite editar `local_repo_path` na Geral tab
- [ ] Smoke test: task de bevox-site executa com `cwd=~/code/bevox-site`
- [ ] Smoke edge: task de projeto sem clone gera clarification "repo não clonado"
- [ ] workspace-template docs atualizadas
- [ ] bevox-knowledge ADR/spec canônica em branch draft

## 10. Dependências e coordenação

### Sessão paralela (esta — clarification-reply-via-gateway-plugin)

Está em execução simultânea (terminal Bernard atual). Cuidados para evitar interferência:

| Tópico | Dela (clarif-reply, esta sessão) | Sua (local-repo-path) |
|---|---|---|
| Branch `~/.openclaw` | `main` | `feat/local-repo-path-per-project` |
| Branch `~/bevox-knowledge` | `draft/adr-011-clarification-reply-via-gateway-plugin` | `draft/local-repo-path-spec` (se for criar ADR) |
| Branch `~/code/mission-control` | não toca | `feat/local-repo-path` |
| Arquivos Python | `clarification-agent/lib/`, `dispatcher-agent/lib/notifier.py` (read-only pra você) | `scrum-master-agent/lib/`, `dispatcher-agent/lib/runner.py`, `dispatcher-agent/lib/materializer.py` |
| Arquivos MC | não toca | `src/app/api/projects/`, `src/components/projects/ProjectGeralTab.tsx` |
| Restart de runtime services | NÃO restart sem coordenar (smoke ativo) | Pode restart `dispatcher-agent` + `cron-dispatcher` ao final, mas avisar antes |
| Test tasks no kanban | Usa T-0150-T-0152 + T-TEST | Usa T-9000+ ou cria projeto `test-repo-path` separado |

### Resolução de conflito de meta

`projects-meta.json` é tocado por ambas? **Sim potencialmente**: clarif-reply pode ter mexido (vimos antes ao mapear bevox-mobile). Local-repo-path adiciona campos novos. Convenção:
- Sessão local-repo-path **lê** o estado atual e **adiciona** field `local_repo_path`.
- Não remover/sobrescrever campos existentes (`bot_id`, `telegram.topics`, etc.) que clarif-reply persistiu.
- Atomic write via fcntl (já é o padrão em `init_telegram_topics.py`).

Se conflito real surgir: sessão local-repo-path pausa, sincroniza com main de `~/.openclaw`, retoma.

## 11. Não-objetivos (anti-scope)

- ❌ Refazer `dispatcher-agent` arquitetura (manter shapes atuais)
- ❌ Mudar convenção do bevox-knowledge (continua em `~/bevox-knowledge`)
- ❌ Auto-clone de repos (escalação humana é suficiente)
- ❌ Suporte a múltiplos working directories por task (1 path por task; multi-repo via paths absolutos manuais)
- ❌ Resolver `local_repo_path` via consulta ao MC API (resolver é puro local read de projects-meta)

## 12. Referências

- **Origem**: smoke real T-0107 sprint-33 bevox-site (2026-04-28); investigação cwd em `dispatcher-agent/lib/runner.py:84-95`
- **Wave em curso (paralela)**: `~/.openclaw/docs/superpowers/specs/2026-04-28-clarification-reply-via-gateway-plugin-design.md`
- **Componentes existentes a reusar**:
  - `~/.openclaw/scripts/init_telegram_topics.py` — exemplo de atomic write fcntl em projects-meta
  - `~/.openclaw/clarification-agent/lib/lifecycle.py:emit_payload_incomplete_escalation` — pattern pra escalação automática
  - MC `src/app/api/projects/route.ts` — endpoint base pra estender
- **CLAUDE.md OpenClaw**: §3 (SoT), §6.2 (source ownership check antes de editar runtime)
