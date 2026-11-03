# ADR-003: Cache strategy (Redis)

**Status:** Aceita
**Data:** 2026-05-09
**Aceita em:** 2026-05-09
**Decisor:** Bernard Tavares
**Origem:** Auto-generated greenfield bootstrap (Sonnet via claude -p) — review humano realizado 2026-05-09

## Contexto

O projeto `bevox-meta-api` é uma API Fastify com plugins de rate-limiting (`@fastify/rate-limit`),
autenticação JWT (`@fastify/jwt`) e observabilidade via OpenTelemetry. A presença de `redis` ou
`ioredis` nas dependências (sinal de detecção, confiança 0.75) indica intenção de uso de Redis como
camada de cache ou backing store.

O uso de `@fastify/rate-limit` é o driver mais concreto: em ambiente com múltiplas instâncias ou
reinicializações frequentes, contadores de rate-limit em memória são perdidos a cada restart. Redis
resolve isso com estado compartilhado e TTL nativo.

Como o projeto ainda não lista serviços principais identificados (`n/a`), esta ADR trata da
estratégia de adoção de Redis antes que padrões ad-hoc se consolidem no código.

## Decisão

Adotar Redis como backing store primário para:

1. **Rate limiting distribuído** — configurar `@fastify/rate-limit` com store Redis para garantir
contadores persistentes entre instâncias e restarts.
2. **Cache de curta duração** — respostas custosas ou lookups frequentes podem ser cacheados com TTL
explícito; sem cache implícito ou lazy invalidation.

O client Redis a usar é `ioredis` (detectado nas deps), com conexão configurada via variável de
ambiente (ver código-fonte para o nome exato da variável — não inferido aqui).

Sem Redis disponível, o sistema deve degradar para store em memória local (comportamento padrão do
`@fastify/rate-limit`) com log de aviso, nunca falha silenciosa.

## Alternativas consideradas

- `in-memory store` — rejeitada para rate-limit distribuído: estado se perde em restart e não é compartilhado entre réplicas; aceitável apenas como fallback local.
- `memcached` — sem evidência de adoção nas deps; `ioredis` já presente torna Memcached redundante sem ganho claro.

## Consequências

**Positivas:**
- Rate limiting correto em deploys multi-instância.
- TTL nativo do Redis simplifica invalidação de cache sem lógica customizada.
- `ioredis` já está nas deps — sem custo de onboarding de nova dependência.
- OpenTelemetry já presente facilita instrumentar latência de chamadas Redis.

**Negativas:**
- Redis passa a ser dependência de infraestrutura obrigatória para produção; ambiente de dev/test precisa de Redis local ou mock compatível (ex: `ioredis-mock`).
- Sem multi-tenancy (`organizationId: false`) não há isolamento por tenant via key prefix hoje — se multi-tenancy for introduzido depois, keys Redis precisarão ser migradas com prefixo de tenant.
- Confiança do sinal de detecção é 0.75; se `redis`/`ioredis` for dependência transitiva e não direta, o escopo desta ADR precisa ser revisado após auditoria do `package.json` completo.

---

> Aceita 2026-05-09 — review humano realizado, ioredis + @fastify/rate-limit confirmados em deps.
