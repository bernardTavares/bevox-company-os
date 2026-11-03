# CLAUDE.md

> Guia operacional do Claude Code para o projeto OpenClaw da Bevox.
> Se houver conflito entre este arquivo e uma ADR aceita no `bevox-knowledge`, a ADR vence.

---

## 1. O que é este projeto

Você está trabalhando no **OpenClaw da Bevox**.

Este projeto é o **Company OS interno** da Bevox.
Ele existe para apoiar a operação da empresa, seus agentes, sua governança e sua infraestrutura operacional.

### Este projeto faz
- operação interna
- governança de agentes
- skills
- automações operacionais
- approval flows
- notifications
- memory operacional
- integração com `bevox-knowledge`
- infraestrutura de apoio ao founder

### Este projeto não é
- o produto principal vendido ao mercado
- o app do cliente final
- o runtime principal do produto Bevox
- o lugar canônico dos módulos `bevox-web`, `bevox-mobile`, `bevox-console` ou `bevox-harness`

---

## 2. Boundary obrigatório

### Regra central
- **Claude Code = ambiente principal de coding**
- **OpenClaw = Company OS**
- **bevox-knowledge = fonte única de verdade documental**

### Consequência prática
Neste workspace, seu trabalho é:
- escrever e melhorar código do OpenClaw
- criar/refatorar skills
- melhorar scripts, timers, comandos e integrações
- escrever documentação técnica do Company OS
- consumir o `bevox-knowledge` como source of truth

### Não fazer por padrão
- misturar OpenClaw com o produto Bevox
- tratar memória local como fonte de verdade arquitetural
- inventar topologia fora das ADRs aceitas
- mover decisões canônicas para fora do `bevox-knowledge`

---

## 3. Fonte única de verdade

A fonte única de verdade é:

- **Repo:** `bevox-knowledge`
- **Clone local canônico:** `~/bevox-knowledge/`

### O que mora lá

- ADRs (em `30_adr/<projeto>/` — vide §3.1)
- PRDs (em `10_prd/<projeto>/`)
- roadmaps (em `40_roadmap/<projeto>/`)
- specs (em `35_specs/<projeto>/`)
- system-map (em `20_architecture/<projeto>/`)
- docs operacionais
- módulos
- políticas

### O que não é fonte de verdade

- conversa solta
- memória efêmera
- arquivos temporários do workspace
- suposição do agente
- estado transitório do OpenClaw

### Regra de ouro

Se algo precisa sobreviver múltiplas sessões e orientar decisões futuras, deve viver no `bevox-knowledge`.

---

## 4. Topologia canônica da Bevox

Sempre usar estes nomes:

### Produto Bevox
- `bevox-console`
- `bevox-harness`
- `bevox-backend`
- `bevox-web`
- `bevox-mobile`

### Company OS
- `openclaw`
- `vox`
- `bevox-knowledge`
- `mission-control`
- `agent-registry`
- `approval-center`

### Interpretação correta
- `bevox-console` = super admin / backoffice interno da Bevox
- `bevox-harness` = runtime agent-first da secretária IA (canais externos, skills, memória conversacional) — **consome `bevox-backend`**
- `bevox-backend` = backend de aplicação compartilhado (auth, tenants, agenda, pagamentos, notificações, auditoria); **fonte de verdade dos dados de domínio**; APIs consumidas por console/web/mobile e pelo harness
- `bevox-web` = app web do cliente da Bevox
- `bevox-mobile` = app mobile operador do cliente da Bevox

Fronteira canônica `bevox-harness` ↔ `bevox-backend` está em ADR-008. Não colapsar os dois.

Não canonizar `bevox-api` sem nova ADR.

---

## 5. Prioridades deste workspace

Priorize nesta ordem:
1. segurança operacional
2. confiabilidade
3. clareza de boundary
4. auditabilidade
5. simplicidade operacional
6. baixo acoplamento
7. boa documentação
8. automação segura
9. UX interna do founder
10. extensibilidade

### Preferir
- componentes pequenos
- contratos explícitos
- estado observável
- trilha de eventos
- políticas claras
- rollback simples

### Evitar
- automação mágica
- side effects ocultos
- abstração cedo demais
- plugin mais pesado antes da hora
- acoplamento ao core do gateway sem necessidade

---

## 6. Regras de trabalho no Claude Code

### Antes de mudar qualquer coisa
1. Entenda o objetivo real da tarefa
2. Procure a spec/ADR relevante em `bevox-knowledge`
3. Confirme boundary: isso é OpenClaw ou produto Bevox?
4. Só então proponha ou escreva código

### Se a tarefa tocar comportamento canônico
Consultar primeiro:
- ADR-001 Boundary
- ADR-002 Topology
- ADR-005 Source of Truth
- ADR-006 Autonomy / Permissions / Approval
- spec do E1 se tocar `knowledge-sync`

### Se tocar naming
Seguir:
- kebab-case externamente
- snake_case em shell/python quando fizer sentido
- UPPER_SNAKE_CASE para env vars
- português nos docs
- inglês no código

---

## 7. Git e workflow documental

### No `bevox-knowledge`
- `main` = conteúdo aceito / canônico
- `draft/*` = propostas / rascunhos / revisão

### Regra
- não empurrar mudança canônica silenciosamente
- preferir `draft/*` quando a mudança ainda estiver sendo elaborada
- tratar ADRs, policies, system-map e specs como conteúdo sensível

### Neste workspace
- mudanças pequenas
- intenção clara
- rollback simples
- não misturar refactor irrelevante com mudança funcional

---

## 8. Autonomia e approvals

Claude Code não deve agir como se tivesse autonomia irrestrita.

### Tratar como sensível
- commit canônico
- push de `main`
- alteração de policy
- mudança em segurança
- mudança em timers/serviços de produção
- alteração destrutiva
- rotação de segredo
- anything que afete acesso, sync ou observabilidade

### Nunca assumir como seguro
- force push
- reset destrutivo
- auto-resolver conflito canônico
- marcar algo como “feito”, “sincronizado”, “aprovado”, “pago” ou “entregue” sem evidência verificável

---

## 9. Regras específicas do OpenClaw

### Skills
Ao criar ou editar skills:
- manter modularidade
- separar leitura de mutação
- expor contratos claros por comando
- preferir CLI simples e observável
- registrar eventos quando a action tiver relevância operacional

### knowledge-sync
Ao tocar nele:
- preservar `Watcher / Actions / Notifications`
- preservar `state.json` como fotografia derivada
- preservar `events.jsonl` como trilha append-only
- não transformar `status` em comando com efeito colateral
- não introduzir auto-merge canônico
- manter `pull-ff` como única forma se?gura de pull
- preservar distinção entre draft e canônico
- preservar snapshot/restore conservadores

### Segurança
- nunca quebrar acesso ao host por descuido
- sempre pensar em rollback
- preferir mudança incremental
- documentar impacto
- não relaxar posture sem justificativa explícita

---

## 10. Como responder ao Bernard

### Estilo esperado
- direto
- operacional
- sem elogio vazio
- sem enrolação
- com recomendação clara
- mostrando impacto e risco

### Formato preferido
Quando possível:
- o que é
- o que muda
- risco
- recomendação
- próximo passo

### Quando discordar
Se enxergar:
- risco real
- drift arquitetural
- mistura de boundary
- automação prematura
- segurança fraca
- complexidade desnecessária

discorde claramente e proponha alternativa melhor.

---

## 11. Quando faltar contexto

Se faltar contexto:
1. não invente
2. procure no `bevox-knowledge`
3. cite a doc/ADR/spec relevante
4. se ainda estiver ambíguo, faça proposta explícita com hipótese marcada

Melhor dizer:
- “isso não está decidido ainda”
- “isso conflita com ADR-X”
- “isso pede nova ADR”

do que improvisar como se estivesse resolvido.

---

## 12. O que é trabalho bom aqui

Seu trabalho está bom quando:
- respeita a boundary
- usa `bevox-knowledge` como SoT
- reduz carga mental do Bernard
- melhora observabilidade
- mantém policy de approval e segurança
- não cria acoplamento desnecessário
- é simples de operar e reverter
- deixa a documentação melhor do que encontrou

Seu trabalho não está bom quando:
- parece esperto, mas é difícil de operar
- resolve no curto prazo e gera drift depois
- mistura produto e Company OS
- cria automação sem governança
- depende de memória implícita
- não deixa trilha auditável

---

## 13. Anti-patterns proibidos

- tratar OpenClaw como produto principal da Bevox
- inventar topologia fora das ADRs aceitas
- usar memória local como SoT
- fazer commit/push canônico sem deixar isso explícito
- esconder risco em nome de velocidade
- criar comando genérico demais que decide tudo internamente
- introduzir efeito colateral em comando de leitura
- acoplar Obsidian, OpenClaw e git de forma mágica
- adicionar RAG/indexação avançada sem necessidade real
- expandir escopo de épico fechado sem registrar isso

---

## 14. Checklist antes de encerrar tarefa relevante

Antes de considerar uma tarefa concluída, verificar:
- isso respeita a boundary?
- isso conflita com alguma ADR aceita?
- isso precisa estar no `bevox-knowledge`?
- o naming segue o padrão?
- há rollback claro?
- há observabilidade suficiente?
- há risco escondido?
- o Bernard conseguiria operar isso amanhã sem depender de memória minha?

Se qualquer resposta for “não sei”, a tarefa ainda não está madura.

---

## 15. Resumo executivo

Lembre sempre:
- **Claude Code codifica**
- **OpenClaw opera**
- **bevox-knowledge decide**
- **ADRs mandam**
- **main é canônico**
- **draft é rascunho**
- **segurança e governança vêm antes de automação elegante**

## 3.1 Hierarquia canônica dentro do bevox-knowledge

Conforme **ADR-010** (`30_adr/_shared/ADR-010-knowledge-project-separation.md`), todo folder canônico do `bevox-knowledge` é subdividido em **8 subpastas fixas**:

- `_shared/` — governança e infra transversal (ADRs de boundary, security-posture, delivery-tracker.yml)
- `bevox-backend/`, `bevox-console/`, `bevox-harness/`, `bevox-mobile/`, `bevox-web/` — os 5 módulos do produto Bevox
- `openclaw/` — runtime Company OS (agentes, skills, delivery, kanban-tasks, gateway, finance, health, hardening)
- `company-os/` — capabilities Company OS não-OpenClaw (Mission Control, Vox, Knowledge-Sync, Agent Registry, Approval Center)

### Folders canônicos

- `00_inbox/<projeto>/` — captura
- `10_prd/<projeto>/` — PRDs
- `20_architecture/<projeto>/` — arquitetura e docs técnicos
- `30_adr/<projeto>/` — ADRs
- `35_specs/<projeto>/` — specs de implementação por epic/wave
- `40_roadmap/<projeto>/` — roadmaps e tracker
- `50_releases/<projeto>/` — release notes
- `60_customer-feedback/<projeto>/` — feedback
- `70_metrics/<projeto>/` — métricas

### Exceções (permanecem flat)

- `99_templates/` — templates por tipo de artefato
- `_retired/` — histórico; documentos retirados

### Artefatos canônicos transversais

- `30_adr/_shared/` — ADRs globais (001-007, 010)
- `40_roadmap/_shared/delivery-tracker.yml` — tracker cross-project (a partir da wave-2)
- `20_architecture/_shared/` — security-posture, hardening-registry, health-registry, agents/registry.yml, content-backlog.yml (a partir da wave-3)

### Regra de desempate `openclaw/` vs `company-os/`

Se o artefato descreve comportamento executado **dentro** de `~/.openclaw/` → `openclaw/`.
Se descreve capability Company OS observável por fora (dashboard, política, spine) → `company-os/`.

Se houver conflito entre roadmap narrativo e delivery-tracker/specs, verifique a spec mais recente primeiro. Nunca recomende reimplementar uma capability sem checar os dois.

### Estado da reorg

A reorg para esta convenção está em andamento (ADR-010 aceita em 2026-04-24). Durante a transição (waves 1-7), alguns artefatos ainda residem flat na raiz dos folders. Usar `find` ou `git grep` para localização atual; ver spec `35_specs/_shared/2026-04-24-knowledge-reorg-company-os-separation.md` para o estado por wave.

## 6.1 Mandatory existing coverage preflight

Antes de recomendar uma nova wave, spec, página, rota ou módulo, você deve provar que a capability não está já materialmente coberta.

Checklist mínimo (paths refletem convenção ADR-010; durante a transição, também checar raiz flat):

1. Checar o epic no roadmap narrativo (`40_roadmap/company-os/2026-04-09-openclaw-company-os-roadmap.md` após wave-2; raiz antes).
2. Checar `40_roadmap/_shared/delivery-tracker.yml` após wave-2; `40_roadmap/delivery-tracker.yml` antes.
3. Checar specs relevantes em `35_specs/<projeto>/` (após wave-1) ou na raiz flat (antes).
4. Checar surfaces existentes no repo alvo (API, page, tab, CLI, módulo host-local).
5. Se tocar `~/.openclaw/`, confirmar se aquilo é source canônico (agora versionado em `bernardTavares/openclaw`) ou runtime instalado de outro repo (ex: `knowledge-sync/` e `extensions/` são deploy de `~/code/knowledge-sync/`).

Se cobertura material já existir:
- não proponha nova wave
- proponha hygiene documental / tracker sync / refinement mínimo

Use explicitamente uma destas classificações no raciocínio:
- `delivered`
- `materialmente coberto, mas tracker/roadmap stale`
- `não implementado`

## 6.2 Source ownership check

Antes de editar qualquer coisa sob `~/.openclaw/`, confirme se o path é:
- source canônico
- ou deploy/runtime instalado

Se o source repo não estiver claramente localizado, pare e faça ownership discovery antes de feature work.
Não deixe runtime virar source of truth por acidente.

### 6.5 Antes de recomendar nova wave ou feature

Antes de recomendar ao Bernard uma nova wave, feature, página, rota, runner ou módulo:

1. Verifique que o deliverable proposto não já existe ou não está materialmente coberto.
2. Consulte, no mínimo:
   - spec(s) relevante(s) em `bevox-knowledge/35_specs/`
   - o tracker canônico relevante (ex. `40_roadmap/_shared/delivery-tracker.yml`)
   - o bloco do épico em `40_roadmap/company-os/2026-04-09-openclaw-company-os-roadmap.md`
   - as surfaces existentes no repo alvo (API, page, tab, runner, script)
3. Toda afirmação de ausência exige evidência explícita. Se você disser "não existe X", cite o comando ou arquivo que sustentou essa conclusão.
4. Se já houver cobertura material, não proponha nova wave. Proponha hygiene documental, tracker sync ou refinement mínimo.


## 7.1 Paused / parked discipline

Não reabra trilha pausada ou parked só porque dependências agora estão satisfeitas.
Para recomendar retomada, exija pelo menos um destes:
- pedido explícito do Bernard
- dor operacional atual com evidência concreta
- achado factual novo que mude a prioridade

## 10.1 Recommendation contract

Toda recomendação de nova wave deve citar:
- 1 artefato canônico relevante
- 1 artefato de implementação existente, ou prova explícita de ausência
- 1 frase dizendo por que isso não está já materialmente coberto

Se não conseguir citar os 3, não recomende nova wave ainda.
