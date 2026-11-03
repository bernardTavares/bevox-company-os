# ADR-004: Framework backend/web choice

**Status:** Aceita
**Data:** 2026-05-09
**Aceita em:** 2026-05-09
**Decisor:** Bernard Tavares
**Origem:** Auto-generated greenfield bootstrap (Sonnet via claude -p) — review humano realizado 2026-05-09

## Contexto

O projeto bevox-meta-api é um serviço backend Node.js em estágio inicial (sem modelos de schema
definidos, sem middleware de auth implementado, sem multi-tenancy ativo). A escolha do framework web
determina a arquitetura de rotas, plugins, observabilidade e performance do serviço. O conjunto de
dependências declaradas no package.json revela que o ecossistema **Fastify** foi adotado como base,
com plugins oficiais cobrindo CORS, segurança HTTP (Helmet), autenticação JWT, OAuth2,
rate-limiting, utilitários (Sensible) e documentação OpenAPI (Swagger + Swagger UI). A stack de
observabilidade é baseada em OpenTelemetry com exportador OTLP-HTTP e instrumentação automática de
Node, complementada por Sentry para rastreamento de erros em produção.

## Decisão

Adotar **Fastify** como framework HTTP do bevox-meta-api, utilizando o ecossistema oficial de
plugins `@fastify/*` para funcionalidades transversais. A stack de observabilidade adota
OpenTelemetry SDK Node com auto-instrumentações e exporter OTLP-HTTP, mais `@sentry/node` para
rastreamento de erros. Documentação de API via `@fastify/swagger` + `@fastify/swagger-ui`.

## Alternativas consideradas

- `express` — não há evidência de dependência ou uso nos sinais; o ecossistema `@fastify/*` presente descarta esse caminho
- `nestjs` — não há evidência de decorators, módulos NestJS ou `@nestjs/*` nas dependências declaradas

## Consequências

**Positivas:**
- Performance: Fastify é consistentemente mais rápido que Express em benchmarks de throughput Node.js, relevante para uma API de suporte cross-projeto
- Ecossistema coeso: todos os concerns transversais (auth, rate-limit, CORS, Helmet, Swagger) cobertos por plugins oficiais `@fastify/*` com contrato de ciclo de vida integrado
- Observabilidade nativa: auto-instrumentações OpenTelemetry cobrem HTTP, rotas e erros sem instrumentação manual; Sentry complementa para alertas de exceção em produção
- Schema-first por padrão: Fastify valida e serializa via JSON Schema nativamente, preparando o terreno para performance e segurança quando modelos forem definidos
- Documentação automática: `@fastify/swagger` gera OpenAPI a partir dos schemas de rota sem duplicação

**Negativas:**
- Curva de aprendizado do sistema de plugins/decorators do Fastify difere de Express; onboarding de novos colaboradores exige atenção
- Ecossistema de plugins de terceiros menor que Express/NestJS para integrações menos comuns
- Auth middleware e multi-tenancy ainda não implementados (sinais indicam `False`): a escolha de Fastify não resolve esses gaps — eles precisam ser endereçados em ADRs ou specs subsequentes
- Confiança do sinal de detecção é 0.7 (heurística por dep primária); se houver camadas adicionais de framework não declaradas nas deps principais, esta ADR precisará ser revisada

---

> Aceita 2026-05-09 — review humano realizado, fastify + 7 @fastify/* plugins + OTel + Sentry confirmados em deps.
