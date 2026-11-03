---
name: spec-writer
description: Escreve specs melhores a partir de ideias, pedidos e frentes de produto, operação ou arquitetura. Use quando for preciso transformar algo ainda solto em spec clara, útil e revisável, especialmente para: (1) framing de problema e objetivo, (2) comparação breve de caminhos antes de decidir, (3) estruturação de escopo, não-escopo, riscos e definição de pronto, (4) converter conversa, áudio, backlog ou intenção em documento de especificação. Não use para debugging profundo, execução de código ou gestão de GitHub por si só.
---

# Spec Writer

Transformar ideia em spec não é só escrever bonito.
É reduzir ambiguidade, cortar excesso, explicitar trade-offs e produzir um documento que realmente guie execução.

Esta skill combina 3 movimentos:
- **explorar antes de decidir**
- **estruturar antes de escrever demais**
- **verificar antes de declarar pronta**

Além disso, toda spec precisa nascer organizada em torno de um **projeto/produto explícito** e com noção clara do seu **destino canônico**.

## Regra estrutural

Esta skill deve seguir o contrato definido em:
`~/.openclaw/workspace/shared/KNOWLEDGE_INTEGRATION_CONTRACT.md`

Toda spec deve responder, antes da escrita final:
- **A qual projeto/produto esta spec pertence?**
- **Que tipo de spec é esta?** (`produto`, `arquitetura`, `operação`, `refinement`)
- **Qual é o destino dela?** (`local-draft` ou `canonical`)
- **Se for `canonical`, ela precisa estar preparada para sincronização com o `bevox-knowledge`.**

Se o projeto ainda não estiver claro:
- inferir a melhor opção disponível
- explicitar a inferência
- ou marcar que o vínculo com projeto ainda está em aberto

Nunca produzir spec solta, sem pertencimento.

## Processo

### Etapa 1: Vincular a spec ao projeto certo
Antes de escrever a spec, identificar:
- nome do projeto/produto
- se ele já existe ou se ainda é uma frente nova
- tipo da spec
- se ela é `local-draft` ou `canonical`

Quando houver múltiplos produtos ou projetos ativos, escolher explicitamente um.
Não deixar a spec pairando entre frentes.

### Etapa 2: Clarificar o alvo
Explicitar em poucas linhas:
- qual problema está sendo resolvido
- para quem isso existe
- qual resultado precisa acontecer
- qual é o recorte desta entrega

Se o pedido estiver aberto demais, inferir a estrutura mais provável e marcar o que ainda é hipótese.

### Etapa 3: Explorar opções quando necessário
Se houver ambiguidade real, gerar **2 ou 3 caminhos possíveis**.

Para cada caminho, registrar brevemente:
- por que parece bom
- risco principal
- custo de contexto
- reversibilidade

Depois escolher **uma recomendação explícita**.
Não devolver só opções sem direção.

### Etapa 4: Estruturar a spec
Escrever a spec em formato claro e operacional.
Adaptar a profundidade ao caso, mas preferir esta espinha:

1. **Projeto / Produto**
   - a que frente esta spec pertence

2. **Tipo de spec**
   - produto, arquitetura, operação ou refinement

3. **Objetivo**
   - o que sucesso significa

4. **Contexto**
   - por que isso existe agora
   - qual problema ou oportunidade motivou a spec

5. **Escopo**
   - o que entra

6. **Não escopo**
   - o que explicitamente não entra agora

7. **Abordagem recomendada**
   - caminho escolhido
   - por que foi escolhido

8. **Riscos e trade-offs**
   - principais riscos
   - limites da abordagem

9. **Definição de pronto**
   - como saberemos que terminou

10. **Próximos passos**
   - sequência mínima para sair da spec para execução

11. **Destino canônico**
   - dizer se a spec fica como `local-draft` ou se deve ser tratada como `canonical` e preparada para sincronização com o `bevox-knowledge`

### Etapa 5: Fechamento de qualidade
Antes de considerar a spec pronta, verificar:

- [ ] a spec pertence explicitamente a um projeto/produto
- [ ] o tipo da spec está claro
- [ ] o objetivo está claro
- [ ] o escopo está delimitado
- [ ] existe recomendação, não apenas enumeração
- [ ] o não escopo foi explicitado
- [ ] riscos ou trade-offs foram nomeados
- [ ] a definição de pronto é verificável
- [ ] o destino canônico foi decidido
- [ ] a spec reduz ambiguidade em vez de ampliá-la

Se algo importante continuar implícito, não declarar pronta.
Dizer exatamente o que ainda está em aberto.

## Regras de qualidade

- Preferir clareza estrutural a volume
- Separar hipótese de decisão
- Cortar escopo quando a spec estiver tentando resolver coisas demais ao mesmo tempo
- Não confundir backlog com entrega atual
- Não usar linguagem vaga para esconder incerteza
- Não transformar a spec em texto comercial
- Não escrever spec sem vínculo de projeto
- Não tratar sync com `bevox-knowledge` como detalhe tardio quando a intenção já for canônica

## Compatibilidade com `bevox-knowledge`

Quando a spec for `canonical`:
- escrevê-la já em formato compatível com o repositório canônico
- nomear e estruturar de forma que facilite sincronização posterior
- explicitar de qual projeto ela faz parte
- seguir a distinção entre camada operacional e camada canônica definida no `KNOWLEDGE_INTEGRATION_CONTRACT.md`
- evitar conteúdo solto, sem classificação ou sem destino

Esta skill não precisa, por si só, executar o sync.
Mas precisa produzir a spec de modo que o sync faça sentido e não dependa de reorganização posterior.

## Quando aprofundar
Aprofundar mais quando a spec envolver:
- arquitetura
- app/fluxo de produto
- operação recorrente
- múltiplos stakeholders
- integração entre sistemas
- risco alto de desvio de escopo

## Quando manter leve
Ser mais conciso quando a spec for:
- pequena
- local
- reversível
- de baixo risco
- claramente contida

## Boundary
Esta skill escreve e estrutura specs.
Ela não substitui:
- debugging profundo
- implementação
- operação de GitHub
- execução técnica

Se for necessário contexto técnico externo, repo ou GitHub, isso entra como suporte ao processo, não como identidade principal da skill.
