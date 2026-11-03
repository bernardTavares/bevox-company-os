# OPERATING_RULES.md

> Princípios operacionais invioláveis da Bevox para operação com agentes em produção.
> Este documento existe para reduzir erro repetido, preservar memória institucional e proteger a operação contra falhas previsíveis.

## Propósito

Estas regras não existem por elegância teórica.
Elas existem porque certos erros parecem pequenos no momento, mas corroem confiança, continuidade, segurança e custo ao longo do tempo.

Quebrar uma regra pode não explodir o sistema imediatamente.
Mas aumenta a chance de:
- falha silenciosa
- perda de contexto
- autonomia sem controle
- custo desnecessário
- degradação de qualidade
- falsa sensação de que “está tudo funcionando”

---

## 1. Crons devem executar trabalho real, em contexto isolado e observável

### Regra
Todo cron que precise executar trabalho deve usar execução real em sessão isolada, com entrega observável do resultado.

### Implementação atual no OpenClaw
Usar:
- `sessionTarget: "isolated"`
- `payload.kind: "agentTurn"`
- `delivery: { mode: "announce" }`

### Por quê
Há cenários em que agendamentos podem reportar sucesso técnico sem executar trabalho útil.
A regra existe para impedir falso positivo operacional.

### Se quebrar
- cron aparenta estar saudável
- nada realmente acontece
- confiança no sistema se deteriora

---

## 2. Nunca hardcodar credenciais

### Regra
Todas as credenciais vivem fora de arquivos operacionais, preferencialmente em `.env`, secret store ou gerenciador dedicado.

### Por quê
Config exposta ou lida por terceiros vira comprometimento em cascata.
Uma credencial mal armazenada pode vazar todas as outras integrações por efeito dominó.

### Se quebrar
- comprometimento de contas
- rotação emergencial de segredos
- superfície de ataque ampliada

---

## 3. dmPolicy: allowlist desde o primeiro dia

### Regra
Todo canal com capacidade de comando direto deve começar fechado por allowlist.

### Por quê
A configuração aberta transforma o agente em superfície pública de execução.
Quem encontrar o bot pode tentar explorar arquivos, integrações e fluxos.

### Se quebrar
- terceiros podem interagir com o agente
- risco de acesso indevido a contexto, ferramentas e memória

---

## 4. Extrair lições antes de cada compactação

### Regra
Antes de cada compactação, extrair no mínimo:
- lições
- decisões
- pendências

Quando aplicável, também extrair:
- atualização de projetos
- contexto relacional
- notas relevantes da sessão

### Por quê
Compactação reduz contexto. Se a extração não acontecer antes, aprendizados e decisões desaparecem.

### Se quebrar
- repetição de erro
- perda de memória operacional
- regressão de qualidade entre sessões

---

## 5. Todo agente novo começa em L1

### Regra
Todo agente novo entra como **L1 Observer**, com revisão humana ou de hub até construir histórico confiável.

### Por quê
Agente novo tende a otimizar velocidade antes de consistência.
Sem supervisão inicial, erros passam silenciosamente.

### Se quebrar
- autonomia antes de maturidade
- decisões ruins sem visibilidade
- dano acumulado antes de inspeção

---

## 6. Fazer split de modelos por tipo de trabalho

### Regra
Separar modelos por criticidade e custo:
- interação estratégica e decisões sensíveis → modelo premium
- crons e execuções recorrentes → modelo médio
- heartbeats, checks e triagem → modelo econômico

### Por quê
Nem toda tarefa precisa do modelo mais caro.
Misturar tudo no mesmo nível aumenta custo e reduz disciplina operacional.

### Se quebrar
- custo desnecessário
- alocação ineficiente de capacidade
- premium gasto em trabalho rotineiro

### Observação
Exemplos de stack mudam ao longo do tempo. O princípio permanece.
A regra é sobre **classe de uso**, não apego a um vendor específico.

---

## 7. Backup antes de mudanças estruturais

### Regra
Antes de mudanças relevantes em configuração, gateway, arquitetura de agentes ou organização crítica do workspace:
- salvar estado anterior
- garantir reversão simples
- registrar rollback quando fizer sentido

### Por quê
Mudança estrutural pode quebrar a operação inteira.
A reversibilidade precisa existir antes da mudança, não depois da falha.

### Se quebrar
- downtime evitável
- reversão improvisada
- perda de referência do último estado estável

---

## 8. Sub-agent nunca pode cair em limbo silencioso

### Regra
Todo sub-agent precisa de:
1. objetivo claro
2. follow-up esperado
3. verificação de resultado
4. resumo humano quando concluir
5. escalonamento após falha repetida

### Política mínima
- retry automático conservador
- se falhar repetidamente, avisar humano
- nunca “fire and forget”

### Por quê
Sub-agents podem travar, falhar ou simplesmente não produzir saída útil.
Sem follow-up, o sistema cria falsa percepção de execução.

### Se quebrar
- tarefas perdidas no limbo
- dependências invisíveis
- atraso descoberto tarde demais

---

## 9. SOUL.md genérico produz agente genérico

### Regra
A identidade operacional do agente deve ser específica, concreta e densa o suficiente para moldar comportamento real.

### O que precisa existir
- anti-patterns explícitos
- exemplos de bom vs ruim
- responsabilidades claras
- tom intencional
- contexto profundo no `USER.md`
- critérios de qualidade e de discordância

### Por quê
Agente sem identidade forte vira assistente genérico, sem opinião operacional, sem consistência e sem capacidade de agir como braço direito.

### Se quebrar
- respostas rasas
- falta de critério
- ausência de personalidade útil
- baixa continuidade comportamental

---

## 10. Creators são skills, não agentes separados

### Regra
Funções criativas recorrentes devem nascer primeiro como skills ou modos dentro de um agente, não como proliferação automática de agentes dedicados.

### Por quê
Cada agente novo adiciona:
- custo
- coordenação
- memória fragmentada
- pontos de falha
- overhead de governança

Na maioria dos casos, um agente com múltiplas skills compartilha melhor:
- contexto
- memória
- aprendizados
- consistência de execução

### Se quebrar
- explosão de complexidade
- coordenação caótica
- cold starts constantes
- fragmentação de aprendizado

---

# Regras operacionais complementares

## A. Espaçar crons para evitar colisão
Distribuir execuções com intervalo suficiente para reduzir rate limit, concorrência desnecessária e picos artificiais.

## B. Evitar mudanças de config em janelas de execução crítica
Alteração estrutural pode reiniciar serviços e interromper jobs em andamento.

## C. Não confiar em mecanismos que “parecem notificar” sem validar entrega real
Sempre validar comportamento observável, não apenas status técnico.

## D. Nunca prometer ingestão automática sem trilha observável
Se um agente ou notificador disser ao humano para responder em um canal, deve existir ao menos um destes caminhos:
- ingestão automática implementada e validada
- comando manual explícito e suportado para registrar a resposta
- operador intermediando conscientemente a resposta

Se isso não existir, a mensagem ao humano deve dizer claramente que o canal é apenas notificação.

Quebrar essa regra gera o pior tipo de falha: o humano acredita que respondeu certo, mas o sistema não muda de estado.

Para Telegram, o padrão recomendado deixa de ser opcional e passa a ser:
- persistir `message_id` da mensagem de clarification enviada
- aceitar `reply_to_message_id` como mecanismo de correlação
- aceitar também fallback por `clarification_id` no corpo da mensagem
- manter cursor persistente de `update_id` para ingestão idempotente

---

# Anti-patterns críticos

## ❌ Configuração “parece correta” sem teste observável
Se não houve validação real, ainda não está confiável.

## ❌ Autonomia concedida por entusiasmo
Agente não sobe de nível por promessa. Sobe por histórico.

## ❌ Memória tratada como detalhe
Sem memória operacional, todo erro volta.

## ❌ Criar agente para cada função
Se o problema é prompt, skill ou modo, não criar novo agente.

## ❌ Usar modelo premium para rotina por comodidade
Isso destrói governança de custo.

---

# Regras que devem virar sistema

Estas regras não devem viver só em texto.
Sempre que possível, virar:
- checklist
- watchdog
- validação automática
- padrão de criação
- auditoria operacional

## Prioridades de automação
1. watchdog de saúde dos crons
2. checklist pré-compactação
3. follow-up obrigatório de sub-agents
4. validação de exposição de canais e allowlists
5. governança de modelos por tipo de workload
6. validação de promessas de automação em mensagens operacionais

---

# Princípio final

A operação com agentes só escala quando disciplina vira sistema.
Enquanto a disciplina depender só de lembrança humana, o erro volta.

Estas regras existem para transformar cicatriz em estrutura.

## Agent playbook dispatch

O Vox e o hub operacional unico do Company OS. Agentes secundarios sao
playbooks especializados que o Vox carrega quando uma requisicao cai
no dominio deles. Na primeira onda do E10, os agentes secundarios
operam via dispatch do Vox.

### Quando carregar um playbook

Quando uma requisicao (vinda do Telegram, slash channel, cron ou CLI)
cair no dominio coberto por um dos agent files em
`bevox-knowledge/20_architecture/agents/`, o Vox deve:

1. Identificar o dominio (ver tabela abaixo ou override explicito do
   Bernard).
2. Ler o agent file correspondente antes de comecar a trabalhar.
3. Operar sob o playbook (Missao, Inputs, Outputs, Skills, Limites,
   Approvals) daquele agente durante a execucao da tarefa.
4. Registrar o dispatch no log (ver §Log).

### Agentes ativos (primeira onda E10)

| Dominio | Playbook |
|---|---|
| Documentacao, ADR, summaries, drift entre docs | `agents/documentation-agent.md` |
| Criacao de agentes novos | `agents/agent-creator-agent.md` |
| Product, PRD, roadmap shaping, decomposicao de backlog | `agents/product-agent.md` |
| GitHub admin, repo map, PR queue, issue triage analitico | `agents/github-admin-agent.md` |
| Atualizar status de wave no `delivery-tracker.yml` (E5 wave 2) | `agents/delivery-status-agent.md` — invocacao explicita obrigatoria nesta primeira wave (ver spec 2026-04-17-e10-delivery-status-agent.md) |

### Override explicito

Bernard pode forcar um playbook especifico com a diretiva:
`use o playbook do <agent-name>` (ou `carregue <agent-name>`).
Neste caso, o Vox carrega exatamente aquele playbook, mesmo que o
dominio natural da requisicao nao bata.

### Log

Todo dispatch de playbook — automatico ou explicito — deve ser
registrado em `~/.openclaw/workspace/shared/outputs/agent-dispatch.jsonl`
como uma linha JSON append-only, no formato abaixo.

**Formato da linha (JSONL, uma por dispatch):**

```json
{
  "ts": "2026-04-11T14:23:10Z",
  "playbook": "documentation-agent",
  "source": "auto",
  "request_summary": "Bernard pediu resumo do ADR-003 secao Fase 3",
  "session_id": "tg-dm-2026-04-11T14:23:00Z"
}
```

**Campos:**

- `ts` — ISO-8601 UTC, momento em que o Vox decide carregar o playbook.
- `playbook` — nome canonico do agente, identico a chave em
  `registry.yml.agents.{name}` e ao nome do arquivo (sem `.md`).
  **Sem aliases.** Valores validos hoje: `documentation-agent`,
  `agent-creator-agent`, `product-agent`, `github-admin-agent`.
- `source` — enum:
  - `auto` — Vox decidiu sozinho pelo dominio
  - `explicit` — Bernard usou a diretiva de override
  - `synthetic` — execucao sintetica explicita para cumprir DoD
- `request_summary` — resumo curto, **uma linha**, **sem copiar input
  cru**, **sem segredos, tokens, credenciais ou conteudo sensivel
  desnecessario**.
- `session_id` — identificador opcional da sessao/canal de origem.
  Pode ser `null` quando nao houver ID natural. Exemplos validos:
  `tg-dm-2026-04-11T14:23:00Z`, `cli-local`, `cron-knowledge-sync-refresh`.

**Escrita:** append direto (bash `>>`) ou equivalente. Single-writer
(so o Vox escreve). Sem helper script, sem wrapper CLI, sem lock file.

**Bloqueio operacional:** Se o log nao puder ser escrito, o Vox deve
parar antes do dispatch e escalar para Bernard. Operar um playbook
sem trilha auditavel nao e aceitavel.
