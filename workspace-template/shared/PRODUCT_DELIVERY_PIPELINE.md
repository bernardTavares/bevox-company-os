# PRODUCT_DELIVERY_PIPELINE.md

> Contrato operacional do fluxo de produto e delivery da Bevox.
> Este documento não substitui `OPERATING_RULES.md`.
> Ele detalha um pipeline específico: de framing até dispatch e fechamento do ciclo.

## Propósito

Este pipeline existe para impedir quatro tipos de drift:
- PRD sem pertencimento
- spec sem destino
- task sem contexto autoral
- execução sem vínculo claro com o artefato que a originou

A regra central é simples:

**projeto primeiro, spec depois, task depois, dispatch por último**

---

## Camadas do fluxo

### 1. `project-framing`
Função:
- enquadrar a iniciativa
- classificar corretamente o que ela é
- vinculá-la ao produto/ecossistema certo
- decidir se merece PRD agora
- gerar PRD inicial quando houver maturidade

Saídas válidas:
- **A**: PRD inicial gerado
- **B**: ainda não deve virar PRD
- **C**: falta uma decisão-chave antes do PRD

Regra:
nenhuma iniciativa deve virar PRD canônico sem classificação, pertencimento e recorte claro.

---

### 2. `spec-writer`
Função:
- transformar um projeto já enquadrado em specs de execução
- detalhar escopo, abordagem, riscos, critérios e estrutura de implementação

Regra:
`spec-writer` entra **depois** do `project-framing`.
Ela não existe para decidir o que o projeto é.
Ela existe para especificar como uma parte do trabalho deve ser executada.

Toda spec deve nascer com:
- projeto/produto explícito
- tipo da spec
- destino explícito (`local-draft` ou `canonical`)

---

### 3. Materialização em task
Função:
- transformar PRD/spec/plan em task operacional do kanban
- decidir se algo entra em backlog, sprint atual, sprint futura ou se ainda não entra

Regra:
nenhuma spec deve ser tratada como automaticamente executável.
Ela precisa ser materializada em task com recorte operacional adequado.

A task deve carregar contexto autoral suficiente para execução posterior.
Quando aplicável, isso deve acontecer via `dispatch_payload`.

---

### 4. Kanban como gate operacional
Função:
- funcionar como sistema de estados do trabalho real
- separar backlog de ready, in_progress, testing, done e rejected

Regra:
**spec não é dispatchável; task em `ready` é dispatchável.**

Isso significa:
- PRD não vai direto para execução
- spec não vai direto para o Claude Code
- a unidade de dispatch é a task do kanban

---

### 5. `dispatcher-agent`
Função:
- selecionar task `ready`
- gerar briefing a partir do `dispatch_payload`
- lançar execução no Claude Code
- mover ciclo para `testing` ou marcar `blocked` em falha

Regra:
o dispatcher despacha **task**, não despacha PRD nem spec diretamente.

O vínculo com PRD/spec existe por meio do contexto materializado na task e no briefing.

---

### 6. Fechamento do ciclo
Função:
- reaper/tester/fluxo de validação fecham o trabalho após execução
- o kanban reflete a realidade operacional do trabalho entregue, bloqueado ou rejeitado

Regra:
dispatch não é fim do fluxo.
O ciclo só se fecha quando o trabalho passa por validação e chega ao estado correto no lifecycle.

---

## Fluxo recomendado

### Happy path
1. ideia ou iniciativa entra em `project-framing`
2. se houver maturidade, nasce um PRD
3. `spec-writer` produz uma ou mais specs de execução
4. specs/plans relevantes são materializados em tasks
5. tasks entram no kanban com contexto autoral suficiente
6. quando uma task estiver `ready`, ela pode ser selecionada pelo `dispatcher-agent`
7. Claude Code executa
8. fluxo segue por `testing` / reaper / tester / done ou blocked

---

## Regras obrigatórias

### 1. Não pular o enquadramento
Não usar spec para substituir PRD quando o problema real ainda é framing.

### 2. Não pular a materialização
Não tratar spec como unidade direta de dispatch.

### 3. Não perder pertencimento
Todo PRD e toda spec devem manter vínculo claro com:
- projeto
- produto/ecossistema
- destino canônico quando aplicável

### 4. Não perder contexto autoral no handoff
Ao virar task, o trabalho precisa preservar contexto suficiente para que o dispatcher gere briefing útil.

### 5. Não confundir canon com operação
- workspace = operação viva
- `bevox-knowledge` = artefato canônico
- kanban = sistema operacional do trabalho em execução

---

## Relação com outros documentos

### Documento-base de regras gerais
- `shared/OPERATING_RULES.md`

### Contrato de separação entre operação e canon
- `shared/KNOWLEDGE_INTEGRATION_CONTRACT.md`

### Skills diretamente afetadas
- `project-framing`
- `spec-writer`

---

## Princípio final

A Bevox não deve operar no salto entre ideia e execução.

O caminho correto é:
**framing -> PRD -> spec -> task -> ready -> dispatch -> validation -> done**
