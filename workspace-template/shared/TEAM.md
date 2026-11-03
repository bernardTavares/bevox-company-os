# TEAM.md — Registry de Agentes da Bevox

> Registro central do time de agentes.
> O usuário fala com o hub. Agentes secundários existem para execução especializada, não para competir por interface.

## Estado atual

| Agente | Papel | Nível | Modelo | Status |
|--------|-------|-------|--------|--------|
| Vox | COO / Hub | L4 | Opus | Ativo |

---

## Política de arquitetura

- O agente principal da Bevox é o **Vox**.
- O Vox funciona como **hub** de coordenação.
- O usuário fala com o hub, não com uma malha de agentes concorrentes.
- Agentes secundários, quando existirem, terão papéis especializados e não terão binding principal com o usuário.
- O modelo recomendado é **Hub > Mesh**.

---

## Leveling System

| Nível | Nome | Autonomia | Revisão |
|------|------|-----------|---------|
| L1 | Observer | Zero — output sempre revisado | Cada entrega |
| L2 | Contributor | Baixa — pode sugerir, não executar | Semanal |
| L3 | Operator | Média — executa dentro de guidelines | Semanal |
| L4 | Trusted | Alta — autonomia quase total | Quinzenal |

### Regras de progressão

- todo agente novo começa em **L1**
- promoção acontece por histórico de qualidade e review
- rebaixamento é possível se a qualidade cair
- nunca promover rapidamente para L3+ sem histórico confiável

---

## Critérios para abrir novos agentes

Só faz sentido criar novo agente quando houver:

- volume recorrente de trabalho em um domínio claro
- contexto especializado que mereça soul/context próprios
- benefício real de separação de papel
- risco de sobrecarga do hub se tudo continuar centralizado

---

## Próximos agentes possíveis (quando fizer sentido)

- Content Agent
- Scraper Agent
- Operations Agent
- Product Agent
- Growth Agent

Nenhum deve ser criado apenas por estética de arquitetura.

---

## Economia de modelos

- Hub / decisões / interação principal: modelo mais forte
- Execução especializada / tarefas rotineiras: modelo mais econômico
- Heartbeats e checks leves: modelo econômico
- Regra central: **quem não precisa de modelo premium não deve usar modelo premium**

### Política de governança
- modelo premium fica reservado para interação principal, decisões mais complexas e tarefas de alta nuance
- automações recorrentes devem usar modelos econômicos
- watchdogs, consolidação de memória, revisões periódicas e checks operacionais devem usar modelos econômicos
- abrir exceção para modelo premium exige motivo claro
