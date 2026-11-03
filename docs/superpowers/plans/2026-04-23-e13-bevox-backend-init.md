# bevox-backend: Inicialização do Repositório

**Epico:** E13/backend-init

> **Objetivo:** Criar e configurar o repositório `bevox-backend` como fonte de verdade dos dados de domínio da Bevox, conforme definido na ADR-008.
>
> **Fronteira canônica:** `bevox-backend` = dados de domínio + APIs síncronas (auth, tenants, agenda, serviços, pagamentos, notificações, auditoria). `bevox-harness` = runtime IA + canais + sessões (consome backend).
>
> **Data:** 2026-04-23
> **Prioridade:** P0

---

## Phase 1: Criação do Repositório e Estrutura

### Task 1.1: Criar repositório no GitHub
- Criar `bevox-backend` na organização `bernardTavares`
- Configurar visibilidade (private)
- Adicionar descrição e tags

### Task 1.2: Inicializar estrutura de diretórios
- Criar `src/`, `tests/`, `docs/`, `docker/`
- Criar subpastas conforme arquitetura (api/, core/, models/, services/, repositories/)
- Criar `.gitignore` para Python/Node
- Criar `LICENSE` (MIT ou Apache 2.0)

### Task 1.3: Criar README.md inicial
- Visão geral do projeto
- Stack tecnológica
- Link para docs
- Badge de status CI

## Phase 2: Setup de Desenvolvimento Local

### Task 2.1: Criar Dockerfile
- Base image (Python 3.13 ou Node 22)
- Instalar dependências
- Configurar entrypoint
- Multi-stage build (se aplicável)

### Task 2.2: Criar docker-compose.yml
- Serviço backend
- Serviço PostgreSQL 16
- Volumes persistentes
- Network config
- .env integration

### Task 2.3: Configurar ambiente local
- Criar `.env.example` com variáveis necessárias
- Documentar em `docs/DEVELOPMENT.md`
- Testar `docker-compose up` completo

## Phase 3: Configuração de CI/CD

### Task 3.1: Configurar GitHub Actions CI
- Workflow em `.github/workflows/ci.yml`
- Steps: checkout, install deps, lint, test
- Trigger: push + PR para main
- Badge no README

### Task 3.2: Configurar linting
- Python: pylint/black OU Node: eslint/prettier
- Config file no repo root
- GitHub Action integrado

## Phase 4: Implementação de Domínios Básicos

### Task 4.1: Health Check Endpoint
- Endpoint: `GET /health`
- Response: `{"status": "ok", "timestamp": "..."}`
- Test unitário

### Task 4.2: Auth Endpoint
- Endpoint: `POST /api/v1/auth/login`
- Payload: `{"email": "...", "password": "..."}`
- Response: JWT token
- Config de secret key em .env
- Test integration

### Task 4.3: Tenants CRUD
- Endpoints:
  - `GET /api/v1/tenants` (list)
  - `POST /api/v1/tenants` (create)
  - `GET /api/v1/tenants/:id` (get)
  - `PUT /api/v1/tenants/:id` (update)
  - `DELETE /api/v1/tenants/:id` (delete)
- Model Tenant (id, name, slug, created_at)
- Migration inicial
- Testes integration

## Phase 5: Documentação Canônica

### Task 5.1: Module Overview em bevox-knowledge
- Criar/atualizar `bevox-knowledge/20_architecture/modules/bevox-backend.md`
- Fronteira com bevox-harness
- APIs canônicas (lista inicial)

### Task 5.2: API Documentation
- OpenAPI/Swagger auto-gerado
- Documentar endpoints em `docs/API.md`
- Exemplos de request/response

---

## Critérios de Aceitação

- [ ] Repositório criado em `github.com/bernardTavares/bevox-backend`
- [ ] README.md com setup local
- [ ] Module overview em bevox-knowledge
- [ ] Docker Compose funcional
- [ ] CI pipeline rodando
- [ ] Endpoints `/health`, `/api/v1/auth/login`, `/api/v1/tenants` funcionais
- [ ] OpenAPI/Swagger documentado
