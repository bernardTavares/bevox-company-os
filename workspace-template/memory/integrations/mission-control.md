# Integration: Mission Control (UI dashboard)

> Mission Control é a UI dashboard do OpenClaw — Next.js app rodando em
> `http://localhost:3000`. Permite a Bernard inspecionar projetos, sprints,
> tasks no kanban, files do projeto, conectar bots Telegram, etc.

## Pré-requisitos

- Repo: `~/code/mission-control/`
- Dev server: `cd ~/code/mission-control && npm run dev`
- Backend lê `~/.openclaw/projects-meta.json`,
  `~/.openclaw/kanban-tasks/state.json`, etc.

## Páginas principais

- `/` — projects index
- `/projects/{{SLUG}}` — drill-down por projeto, com tabs:
  - **Geral** — metadata, GitHub repo, Telegram bot connect, danger zone
    (delete project)
  - **Roadmap** — markdown viewer pro `bevox-knowledge/40_roadmap/{{SLUG}}/`
  - **Ficheiros** — markdown viewer pra files do projeto
    (`bevox-knowledge/10_prd/{{SLUG}}/`, etc)
  - **Sprints** — kanban per-project
- `/sprints` — view cross-project com drag-drop entre projetos

## API routes relevantes

- `GET /api/projects` — lista projetos
- `POST /api/projects` — cria projeto novo (factory `openclaw project create`)
- `GET /api/projects/[id]` — metadata do projeto
- `PATCH /api/projects/[id]` — edita metadata (bot_id, github_url, etc)
- `DELETE /api/projects/[id]` — remove projeto (factory `openclaw project remove`)
- `POST /api/projects/[id]/bot/connect` — conecta bot Telegram
- `POST /api/projects/[id]/telegram/init-topics` — cria tópicos canônicos no grupo

## Como o agente usa MC

Geralmente NÃO uso MC diretamente — Bernard é o usuário primário da UI.
Mas posso:

- Sugerir a Bernard "abre `/projects/{{SLUG}}` pra inspecionar tasks"
- Verificar se MC reflete state correto após mudanças (smoke check pós-deploy)
- Ler API routes pra entender contratos quando trabalhar em código MC

## Anti-patterns

- NÃO chamar API routes de MC pra fazer mutação que tem CLI equivalente
  (`openclaw project create`, `kanban-tasks/cli.sh task move`, etc) — CLI
  é o caminho canônico, MC é UI on top
- NÃO assumir que MC está rodando (npm run dev pode estar parado)
