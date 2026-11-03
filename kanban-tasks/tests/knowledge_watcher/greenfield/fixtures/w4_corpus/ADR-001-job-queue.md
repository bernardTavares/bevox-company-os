# ADR-001: Escolha de job queue library

**Status:** Aceita
**Data:** 2026-05-09
**Aceita em:** 2026-05-09
**Decisor:** Bernard Tavares
**Origem:** Auto-generated greenfield bootstrap (Sonnet via claude -p) — review humano realizado 2026-05-09

## Contexto

O projeto `bevox-meta-api` é construído sobre Fastify e inclui instrumentação de observabilidade via
OpenTelemetry e Sentry. A presença de `bullmq` nas dependências indica que há necessidade de
processamento assíncrono de tarefas em background — tipicamente para desacoplar operações de longa
duração do ciclo request/response da API e garantir retries, persistência e rastreabilidade de jobs.

BullMQ é a evolução da biblioteca `bull`, mantida pelo mesmo autor (Taskforce.sh), e exige Redis
como backend de persistência e coordenação.

A decisão de qual library usar impacta:
- o runtime de infraestrutura necessário (Redis obrigatório com BullMQ)
- a semântica de jobs (filas, workers, eventos, retries, delays, prioridades)
- o modelo de observabilidade dos jobs (integração com OpenTelemetry existente)
- a superfície de manutenção a longo prazo

## Decisão

Adotar **BullMQ** como job queue library do `bevox-meta-api`.

A escolha é inferida da presença de `bullmq` nas dependências declaradas do projeto. BullMQ oferece
semântica de filas robusta sobre Redis, com suporte a workers concorrentes, retries com backoff
configurável, delayed jobs, eventos auditáveis e API TypeScript-first — alinhado com o stack
Fastify/Node.js do projeto.

## Alternativas consideradas

Nenhuma alternativa apresenta evidência nos sinais coletados. As opções abaixo são listadas apenas
como referência contextual, sem evidência de avaliação formal no projeto:

- `bull` — predecessor do BullMQ; descontinuado pelo mesmo autor em favor do BullMQ; migração seria regressão.
- `pg-boss` — queue sobre PostgreSQL; eliminaria a dependência de Redis, mas não há evidência de PostgreSQL no stack atual e perderia features de BullMQ.
<!-- low-confidence: review -->
- processamento in-process sem queue — inadequado para workloads que exigem persistência de estado e retry entre reinicializações.

## Consequências

**Positivas:**
- API TypeScript-first com tipagem forte, compatível com o stack existente.
- Suporte nativo a retries, backoff, delayed jobs e prioridades sem código customizado.
- Ecossistema ativo; BullMQ é o successor oficial do `bull` com manutenção contínua.
- Eventos de job (completed, failed, stalled) permitem integração com o pipeline OpenTelemetry já presente no projeto.
- Dashboard de inspeção disponível (Bull Board / BullMQ Board) para observabilidade operacional.

**Negativas:**
- Introduz Redis como dependência obrigatória de infraestrutura; se o projeto não já possuía Redis, adiciona complexidade operacional (provisionamento, HA, backups).
- Curva de configuração para workers, concorrência e sandboxed processors em produção.
- Jobs mal configurados (sem TTL, sem limite de tentativas) podem acumular estado no Redis indefinidamente — exige disciplina de configuração.
- Ausência de evidência de testes de carga nos sinais: capacidade de throughput não validada para o volume esperado do `bevox-meta-api`.

---

> Aceita 2026-05-09 — review humano realizado, Sonnet output cross-checked contra `package.json` (bullmq, fastify, OTel, Sentry).
