# E10/delivery-status-agent — Fase A Discovery Findings

> Read-only discovery per ajuste 1+3 do plano de execução.
> Pausado no Checkpoint A por ambiguidade real no modelo de on-approve.

**Data:** 2026-04-17
**Estado:** pausado, aguardando decisão do Bernard antes de seguir para Fase B

---

## A1 — Hub-dispatch pattern (fechado, sem ambiguidade)

**Conclusão:** Hub-dispatch é comportamental, não infra CLI.

### Como funciona hoje

Documentado em `~/.openclaw/workspace/shared/OPERATING_RULES.md` §291-368:

- O Vox é hub operacional único.
- Agentes secundários são **playbooks markdown** em
  `bevox-knowledge/20_architecture/agents/<name>.md`.
- Quando uma requisição cai no domínio de um agente, o Vox:
  1. Identifica o domínio (por conteúdo ou override explícito do Bernard)
  2. Lê o agent file antes de começar a trabalhar
  3. Opera sob o playbook (Missão, Inputs, Outputs, Skills, Limites,
     Approvals) durante a execução
  4. Registra o dispatch em
     `~/.openclaw/workspace/shared/outputs/agent-dispatch.jsonl` (append-only)

### Invocação

Explícita: Bernard diz `use o playbook do <agent-name>` ou `carregue <agent-name>`.
Automática: Vox reconhece domínio e carrega.

**Não existe CLI `hub-dispatch X --flag`.** A invocação é linguagem natural.

### Implicação para delivery-status-agent

O novo agente é um **arquivo .md** em `bevox-knowledge/20_architecture/agents/delivery-status-agent.md`. O Vox carrega quando Bernard pedir. O playbook instrui o Vox a ler YAML, montar proposta, emitir, e (on-approve) aplicar.

A1 não tem ambiguidade; a wave sai do Checkpoint A com modelo definido para este eixo: **playbook .md + Vox carrega + dispatch log**.

---

## A2 — exec-approvals: o que é vs o que a spec assumiu

**Conclusão:** **ambiguidade real.** A spec canonizada usa o nome "exec-approvals" como se fosse um mecanismo genérico de approval de propostas. Na realidade, exec-approvals tem um escopo estrito e diferente.

### O que é exec-approvals (factual, lido da spec E4 wave 1 + do código)

Fonte: `bevox-knowledge/35_specs/2026-04-12-e4-approval-center-wave-1.md` e os scripts em `~/.openclaw/exec-approvals/`.

É um **listener Unix socket** (`~/.openclaw/exec-approvals.sock`) que:

- Escuta requests do **gateway OpenClaw** quando o Vox tenta rodar **comandos shell** que não estão no allowlist.
- Avalia cada request contra **glob rules em plaintext** (`rules.txt`).
- Responde `allow-once`, `allow-always`, ou `deny` dentro de 15s.
- Registra em `pending.jsonl`.

O E4.2 wave 1 ("operator") é um cliente externo que consome eventos
`exec.approval.requested` e `plugin.approval.requested` do gateway e
surface via Telegram.

**Escopo: aprovação de comandos shell do Vox.** Não é um mecanismo
genérico para "agente emite proposta de mutação de artefato; humano
aprova; runtime aplica". Não há entrypoint pra emitir
proposta-arbitrária-de-mutação de um agente.

### Confirmação do gap no próprio WARMUP.md

Do `~/.openclaw/exec-approvals/WARMUP.md`:

> **Achado do caller runtime (gap #8):** `requestExecApprovalViaSocket`
> **não tem caller runtime no OpenClaw**... o listener **não vai
> receber tráfego natural** — o caminho do socket de approval não é
> exercitado pelo runtime em nenhuma combinação security×ask.

Ou seja: mesmo para o escopo pretendido (aprovação de shell commands),
o exec-approvals ainda **não é chamado organicamente** pelo runtime do
OpenClaw. E não tem sidecar que o alimente para outros casos de uso
(mutação de artefato, propostas de agente, etc.).

### Pattern existente RELEVANTE que a discovery achou

O delivery-agent runtime do E5 wave 1 **já tem um pattern próprio de
proposta→accept/reject** (documentado em
`bevox-knowledge/35_specs/2026-04-13-e5-roadmap-delivery-os-wave-1.md`
§157-171, código em `~/.openclaw/delivery/`):

- Agent emite evento `task.proposed` em `~/.openclaw/delivery/events.jsonl`
- CLI `openclaw-delivery proposals` lista pendências
- CLI `openclaw-delivery accept <proposal-id>` emite `task.created`
- CLI `openclaw-delivery reject <proposal-id> --reason "..."` emite `task.rejected`

**É o pattern mais próximo do que a nova wave precisa.** Não é
exec-approvals — é um canal jsonl + CLI accept/reject **dedicado ao
domínio delivery**.

---

## A3 — Applicator hook: opções reais (ambiguidade presente)

A spec canonizada (já renomeada para `delivery-status-agent`) descreve:

> **Single-gate via exec-approvals (E4.1/E4.2).** On approve, runtime
> aciona `knowledge-sync canonical commit` com o payload da proposta.

Isso **não é executável como descrito** porque exec-approvals não
emite eventos de "proposta de agente aprovada" pra nenhum applicator
consumir. Só emite decisões sobre comandos shell.

Três opções reais para o single-gate, cada uma com trade-offs:

### Opção Alpha — canonical approval do knowledge-sync é o único gate

- Vox (sob playbook) lê YAML, monta proposta mentalmente, **edita
  YAML no working tree** com o `after` state
- Vox chama `knowledge-sync canonical commit -m "feat(delivery-status-agent): update <wave> ..." --files 40_roadmap/delivery-tracker.yml`
- Approval card aparece no Telegram (inline buttons quebrados — gap
  E1.1-fix) OU Bernard aprova via CLI fallback
- On approve: `canonical execute` → commit lands; normal push flow

**Prós:**
- Zero infra nova. Usa 100% do que já funciona.
- Canonical trail já auditável (events.jsonl da knowledge-sync).
- Diff no card Telegram IS o before/after do YAML.
- Bernard tem fallback CLI comprovado.

**Contras:**
- Perde a estrutura rica da proposta (evidence, advisory, before/after
  JSON estruturado) — fica tudo no commit message como texto.
- Optimistic lock fica implícito: se Bernard editar YAML entre Vox ler
  e Vox chamar `canonical commit`, o `git add` pega o diff atual, não
  o esperado.
- Telegram inline buttons quebrados (dor já conhecida, E1.1-fix spec
  canonizada mas não executada).

### Opção Delta — canal próprio no padrão do E5 wave 1 runtime

- Criar `~/.openclaw/agents/delivery-status-agent/events.jsonl`
- Vox (sob playbook) emite evento `status_update.proposed` com payload
  estruturado completo (target_ref, before, after, evidence, advisory)
- Criar CLI `delivery-status-agent proposals / accept / reject`
  espelhando `openclaw-delivery`
- Bernard roda `delivery-status-agent accept <proposal-id>` via
  terminal
- No accept, o CLI aplica a mutação (YAML edit + knowledge-sync
  canonical commit + execute)

**Prós:**
- Preserva integralmente a estrutura da proposta (§3.4 da spec).
- Optimistic lock explícito: payload tem `before`, CLI valida antes
  de aplicar.
- Reusa um pattern já provado (delivery-agent runtime E5).
- Trail dedicado, não misturado com outros eventos.

**Contras:**
- Cria infra nova: jsonl + CLI + scripts em
  `~/.openclaw/agents/delivery-status-agent/`.
- Duplica parcialmente o CLI do `openclaw-delivery` (padrão parecido,
  escopo diferente).
- Mais código, maior superfície de manutenção.

### Opção Epsilon — approval inline na conversa Vox↔Bernard

- Vox (sob playbook) lê YAML, monta proposta, mostra em texto
  estruturado na conversa
- Bernard responde `aprovo` ou `rejeito` na mesma conversa
- Se `aprovo`: Vox aplica (YAML edit + knowledge-sync canonical commit
  + execute no canonical → approve canonical via CLI fallback ou
  outro card)
- Sem jsonl próprio, sem CLI dedicado

**Prós:**
- Zero infra nova.
- UX mais fluida (conversa, não CLI).
- Estrutura da proposta fica no texto da mensagem.

**Contras:**
- Zero trail estruturado da proposta — só o texto da conversa (sessão
  jsonl do Vox).
- Difícil de auditar / reexecutar posteriormente.
- Approval dupla: "aprovo a proposta" na conversa + aprovar o canonical
  commit no Telegram/CLI. Isso **não é single-gate**.
- Pode não funcionar via Telegram DM (Vox sem tools neste canal — bug
  conhecido E1.1-fix).

---

## Recomendação preliminar (ajuste 3 impõe pausa pra Bernard decidir)

**Opção Alpha** parece a mais coerente com:
- "Zero infra nova"
- "Reusa primitives existentes"
- "Single-gate"
- O pattern já estabelecido no projeto para canonical mutations

O preço é perder a proposta estruturada (before/after/evidence/advisory
como JSON durável). Isso pode ser aceitável se o **diff YAML no card
canônico** + o **commit message estruturado** forem evidência
suficiente.

**Mas esta é decisão arquitetural.** Per ajuste 3:

> Se o on-approve hook ou o modelo Hub-dispatch continuarem ambíguos,
> você pausa. Sem workaround, sem protocolo inventado, sem 'vamos
> assumindo e ajustando depois'.

**Ambiguidade é:** a spec canonizada literalmente diz "single-gate via
exec-approvals" mas exec-approvals não suporta esse caso de uso. Qual
opção real Bernard escolhe? Alpha, Delta, Epsilon, ou uma 4ª que
Bernard já tem em mente?

Qualquer decisão aqui muda a Fase B (arquitetura do playbook + scripts
auxiliares), e potencialmente exige **update da spec canonizada** para
refletir o caminho real (§3.5 da spec fala "single-gate via exec-approvals
(E4.1/E4.2)" — essa linha precisa ser atualizada para o mecanismo
escolhido).

---

## Estado atual

- Zero código novo escrito
- Zero arquivo criado em `~/.openclaw/agents/`
- Zero mudança em mission-control, registry.yml, exec-approvals
- Zero mutação em qualquer YAML/spec canônico
- Working trees limpos nos 2 repos
- Aguardando decisão do Bernard entre Alpha / Delta / Epsilon / outra

---

## Sumário TL;DR

| Eixo | Estado | Resultado |
|---|---|---|
| **A1 Hub-dispatch** | resolvido | playbook .md + Vox carrega + dispatch log |
| **A2 exec-approvals** | resolvido com surpresa | exec-approvals é sobre shell commands, não propostas genéricas |
| **A3 applicator hook** | **ambíguo** | 3 opções reais (Alpha/Delta/Epsilon), cada uma implica edits à spec |
