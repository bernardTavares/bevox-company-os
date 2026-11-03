---
name: project-framing
description: Enquadra novas ideias, frentes, superfícies e iniciativas da Bevox antes de virarem PRDs ou projetos canônicos. Use quando for preciso entender o que uma ideia realmente é dentro do ecossistema, decidir se ela merece existir como projeto separado, vinculá-la ao produto ou ecossistema correto e, quando houver maturidade suficiente, gerar um PRD inicial organizado por projeto e produto. Não use para escrever specs de execução detalhadas, debugging profundo ou implementação técnica.
---

# Project Framing

Nem toda ideia vira produto.
Nem todo produto merece um PRD agora.
Nem toda frente nova deve existir separada do ecossistema atual.

Esta skill existe para evitar inflar o sistema com projetos mal classificados, PRDs prematuros, frentes sem pertencimento claro e duplicação desnecessária no portfólio da Bevox.

## Regra estrutural

Esta skill deve seguir o contrato definido em:
`~/.openclaw/workspace/shared/KNOWLEDGE_INTEGRATION_CONTRACT.md`

Todo enquadramento precisa responder, antes de qualquer PRD:
- **O que isso é de fato?**
- **Isso deve existir como projeto separado?**
- **A qual produto, produto-mãe ou ecossistema pertence?**
- **Isso sobrepõe algo que já existe?**
- **Isso complementa, estende, substitui ou conflita com outra frente?**
- **Isso merece um PRD agora?**
- **Se merecer, esse PRD será `local-draft` ou `canonical`?**

Se essas respostas não estiverem claras, ainda não é hora de formalizar o artefato.

## Saídas válidas

A skill não deve forçar sempre um PRD.
Ela deve ser capaz de terminar em três estados:

### A. PRD inicial gerado
Usar quando houver clareza suficiente para formalizar o projeto.

### B. Ainda não deve virar PRD
Usar quando a ideia ainda estiver aberta, prematura ou mal classificada.

### C. Falta uma decisão-chave
Usar quando houver material suficiente para enquadramento, mas não para formalização completa.

## Processo

### Etapa 1: Classificar a iniciativa
Antes de tudo, classificar a ideia como uma destas opções:
- produto
- subproduto
- superfície
- canal de acesso
- feature
- ferramenta interna
- capability interna
- experimento
- projeto operacional

Se houver dúvida entre duas classes, explicitar a ambiguidade e recomendar uma.

### Etapa 2: Vincular ao ecossistema
Definir:
- a que produto, produto-mãe ou ecossistema a iniciativa pertence
- se esse produto já existe
- se a iniciativa é um projeto separado ou uma extensão do que já existe

Nunca deixar a iniciativa solta, sem pertencimento.

### Etapa 3: Verificar sobreposição de portfólio
Responder explicitamente:
- isso já está parcialmente coberto por outro projeto, produto, superfície ou ferramenta interna?
- isso complementa algo existente ou duplica algo existente?
- isso cria confusão de posicionamento dentro do ecossistema?
- isso deveria ser projeto novo, subprojeto ou apenas extensão de uma frente já aberta?

Se houver sobreposição relevante, recomendá-la claramente.

### Etapa 4: Fazer o framing
Explicitar em poucas linhas:
- qual problema está sendo resolvido
- para quem isso existe
- qual job principal resolve
- por que isso importa agora
- qual é o recorte inicial
- o que fica fora

### Etapa 5: Identificar maturidade da iniciativa
Classificar em um destes níveis:
- ideia
- oportunidade
- projeto em exploração
- projeto elegível para PRD
- projeto pronto para spec
- projeto pronto para roadmap

A skill deve ser capaz de dizer quando a iniciativa ainda está cedo demais.

### Etapa 6: Decidir o gate
Responder explicitamente:
- isso merece um PRD agora?
- se não, por quê?
- o que precisa estar claro antes de virar PRD?

### Etapa 7: Formalizar quando fizer sentido
Se a resposta for **A**, gerar um PRD inicial com esta espinha:

1. **Projeto**
   - nome da iniciativa

2. **Produto / Ecossistema**
   - a que produto ou camada maior ela pertence

3. **Classificação**
   - produto, superfície, ferramenta interna etc.

4. **Objetivo**
   - o que sucesso significa

5. **Contexto**
   - por que isso existe agora

6. **Problema / oportunidade**
   - o que motivou esse projeto

7. **Público / usuário**
   - para quem isso existe

8. **Job principal**
   - transformação esperada

9. **Escopo inicial**
   - o que entra na v1

10. **Não escopo**
   - o que fica fora agora

11. **Relação com o ecossistema**
   - o que isso complementa, estende, substitui ou tensiona no portfólio atual

12. **Riscos e trade-offs**
   - principais riscos e tensões

13. **Próximos passos**
   - o que precisa acontecer depois do PRD

14. **Destino canônico**
   - dizer se o PRD é `local-draft` ou `canonical`

## Regra de organização dos PRDs

Quando um PRD for criado, ele não deve nascer solto.
Ele deve deixar explícito:
- qual é o **projeto**
- qual é o **produto/ecossistema**
- como esse projeto se relaciona com os demais

A skill deve pensar PRDs organizados por:
1. **projeto**
2. **produto / produto-mãe / ecossistema**

## Compatibilidade com `bevox-knowledge`

Quando o PRD for `canonical`:
- prepará-lo para sincronização com o `bevox-knowledge`
- escrevê-lo já com vínculo claro de projeto e produto
- evitar conteúdo solto, sem classificação ou sem lugar claro na árvore de conhecimento

Esta skill não precisa executar o sync sozinha.
Mas precisa produzir um artefato que faça sentido dentro do canon da Bevox.

## Regras de qualidade

- Não chamar tudo de produto
- Não gerar PRD cedo demais
- Não confundir superfície com projeto independente
- Não inflar o ecossistema com frentes sem papel claro
- Não devolver apenas possibilidades sem recomendação
- Não perder o vínculo entre projeto e produto-mãe
- Não deixar a iniciativa sem destino canônico explícito
- Não permitir duplicação silenciosa de portfólio
- Não promover à camada canônica algo que ainda não tem pertencimento, maturidade e papel claros

## Boundary

Esta skill enquadra e formaliza projetos em nível de PRD.
Ela não substitui:
- `spec-writer` para specs operacionais de execução
- debugging
- implementação técnica
- priorização completa de roadmap
- design detalhado de UX

Se o projeto já estiver decidido e o próximo passo for detalhar execução, a skill correta passa a ser a `spec-writer`.
