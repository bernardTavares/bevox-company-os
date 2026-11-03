# KNOWLEDGE_INTEGRATION_CONTRACT.md

> Contrato operacional entre o workspace do Vox e o repositório canônico `bevox-knowledge`.
> Objetivo: reduzir drift, evitar duplicação e tornar o destino dos artefatos previsível.

## Princípio central

**Pensar no workspace, consolidar no `bevox-knowledge`.**

O workspace do Vox existe para operação viva.
O `bevox-knowledge` existe para conhecimento e artefatos canônicos da Bevox.

---

## Camadas

### 1. Workspace operacional do Vox
**Path:** `~/.openclaw/workspace`

Função:
- memória operacional
- notas de sessão
- pendências
- rascunhos
- contexto vivo
- skills locais
- elaboração intermediária
- trabalho conversacional em andamento

Esta camada deve ser tratada como ambiente de operação, não como fonte canônica final de tudo.

### 2. Base canônica da Bevox
**Path:** `~/bevox-knowledge`

Função:
- specs oficiais
- PRDs
- arquitetura
- roadmap
- releases
- documentação institucional
- artefatos duráveis e reutilizáveis
- conhecimento estruturado que compõe o sistema Bevox

Esta camada deve ser tratada como fonte canônica geral.

---

## Regra de destino

Todo artefato novo deve nascer com uma decisão explícita:

- `local-draft`
- `canonical`

### `local-draft`
Usar quando o material ainda for:
- exploração
- rascunho
- pensamento intermediário
- backlog ainda imaturo
- contexto de sessão
- conteúdo que ainda pode mudar estruturalmente

### `canonical`
Usar quando o material já for:
- reaproveitável
- durável
- parte do sistema Bevox
- documento de referência
- spec/PRD/runbook/arquitetura que precisa sobreviver à sessão

---

## O que fica no workspace

- `memory/`
- notas de sessão
- pendências operacionais
- ideias em elaboração
- rascunhos não consolidados
- skills locais do Vox
- contexto intermediário de trabalho

## O que vai para o `bevox-knowledge`

- PRDs
- specs canônicas
- arquitetura
- roadmap
- release notes
- runbooks permanentes
- documentação institucional
- artefatos que pertencem ao ecossistema Bevox

---

## Regra anti-duplicação

Não manter duas versões “ativas” do mesmo artefato, uma no workspace e outra no `bevox-knowledge`, sem motivo explícito.

Se um documento foi promovido para canônico:
- o `bevox-knowledge` vira a referência principal
- o workspace pode manter apenas rascunho anterior, contexto de elaboração ou ponte curta

---

## Regra para skills

Skills de escrita, estruturação e framing devem ser **knowledge-aware**.

Isso significa que elas precisam decidir explicitamente:
1. a que projeto/produto/área o artefato pertence
2. se o artefato é `local-draft` ou `canonical`
3. se o destino natural é o `bevox-knowledge`
4. como preparar o conteúdo para sync posterior, quando aplicável

### Skills prioritariamente afetadas
- `spec-writer`
- `project-framing`
- futuras skills de PRD, arquitetura, roadmap ou release

---

## Regra de classificação antes de escrever

Antes de gerar artefato canônico, responder:

1. Isso é produto, projeto, superfície, feature, ferramenta interna ou operação?
2. A qual ecossistema/produto-mãe pertence?
3. Esse documento é rascunho ou referência canônica?
4. Onde ele deve viver depois de consolidado?

Se essas respostas não estiverem claras, o artefato não está pronto para promoção canônica.

---

## Regra de sync

O contrato assume que o `bevox-knowledge` é acessível localmente em:
`~/bevox-knowledge`

Este contrato **não obriga** que toda skill execute sync automaticamente.
Mas obriga que skills canônicas produzam artefatos já preparados para sincronização, em vez de gerar conteúdo solto que precise ser reorganizado depois.

---

## Princípio final

O workspace do Vox é a camada de pensamento e operação.
O `bevox-knowledge` é a camada de canon, memória estruturada e sistema durável.

Misturar as duas camadas gera drift.
Separá-las com clareza gera continuidade.
