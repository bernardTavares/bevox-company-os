# Bevox Site Execution Plan

> Plan para materialização de tasks do `bevox-site` via `scrum-master-agent`, derivado da spec canônica e do backlog canônico já escritos no `bevox-knowledge`.

**Project:** bevox-site
**Epico:** site-v1/execution-spec-v1
**Goal:** Materializar no kanban do bevox-site as tasks derivadas da execution spec v1, preservando vínculo explícito com a spec canônica e critérios de aceite por task.
**Spec canônica:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**Tasks doc:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-tasks-v1.md`

## Phase 1: Readiness de execução

### Task 1.1: Revisar pendências abertas do PRD e classificar bloqueios da v1
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Reler o PRD do `bevox-site`, levantar todas as pendências ainda abertas e classificar cada uma como bloqueante da v1, relevante mas não bloqueante, ou pós-v1. Registrar impacto operacional de cada pendência para impedir execução baseada em ambiguidade silenciosa.

Expected: Lista explícita de pendências extraída do PRD
Expected: Cada pendência classificada como bloqueante, não bloqueante ou pós-v1
Expected: Impacto operacional de cada item registrado de forma objetiva

### Task 1.2: Congelar recorte inicial de idiomas da v1
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Definir operacionalmente como a v1 tratará idiomas para não deixar SEO, conteúdo, navegação e estrutura de rotas dependentes de interpretação futura. Se houver múltiplos idiomas, explicitar o comportamento mínimo esperado na v1.

Expected: Recorte de idiomas da v1 explicitado
Expected: Impacto em conteúdo, SEO e rotas documentado
Expected: Implementação futura não depende de adivinhação sobre multilíngue

### Task 1.3: Congelar CTA principal do hero e do contato
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Definir CTA principal do hero e da seção de contato, incluindo destinos finais, links e comportamento esperado, para remover placeholders de jornada e permitir implementação coerente do fluxo narrativo.

Expected: Hero com CTA principal definido
Expected: Contato com CTA principal definido
Expected: Destinos e comportamento dos CTAs registrados de forma clara

### Task 1.4: Confirmar política de fallback mobile e capacidade mínima suportada
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Fixar a política de fallback mobile como decisão explícita de produto e engenharia, incluindo critérios de viewport, capacidade gráfica e comportamento de redirecionamento ou estratégia equivalente.

Expected: Critérios de viewport e GPU definidos
Expected: Estratégia de fallback confirmada
Expected: Impacto em UX e arquitetura registrado

### Task 1.5: Confirmar decisões mínimas de infra para a v1
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Fechar o mínimo necessário de infraestrutura para orientar deploy e operação da v1, incluindo provider de VPS, registry da imagem e uso de Cloudflare Tunnel.

Expected: Provider de VPS definido ou explicitamente marcado
Expected: Registry de imagem definido ou explicitamente marcado
Expected: Conjunto mínimo de decisões operacionais da v1 registrado

## Phase 2: Foundation técnica e arquitetura de app

### Task 2.1: Bootstrap do projeto Next.js com TypeScript, Tailwind e App Router
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Inicializar a base do `bevox-site` com Next.js App Router, TypeScript e Tailwind, garantindo que o projeto suba localmente na stack canônica definida no PRD.

Expected: Projeto sobe localmente
Expected: Next.js App Router configurado
Expected: TypeScript e Tailwind integrados na base do app

### Task 2.2: Integrar React Three Fiber, Drei, Zustand e GSAP ScrollTrigger
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Instalar e integrar o conjunto base de runtime visual, estado compartilhado e narrativa por scroll para suportar a cena 3D e os steps do site.

Expected: R3F e Drei integrados
Expected: Zustand disponível para estado compartilhado
Expected: GSAP ScrollTrigger funcional na base do projeto

### Task 2.3: Implementar estrutura de diretórios canônica do projeto
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Criar a estrutura de pastas prevista no PRD para separar claramente cena, overlay, sections, conteúdo, tipos, utilitários e infra.

Expected: Estrutura principal de diretórios criada
Expected: Organização alinhada ao PRD
Expected: Sem drift arquitetural inicial por conveniência local

### Task 2.4: Criar base visual global e tokens iniciais
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Configurar `globals.css`, tokens de superfície, acento, tipografia e base visual global para impedir fragmentação de estilos desde o início do projeto.

Expected: Tokens visuais principais definidos
Expected: Base tipográfica preparada
Expected: Camada global pronta para suportar componentes futuros

### Task 2.5: Implementar healthcheck HTTP e build standalone
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Criar endpoint `/api/health` e configurar `output: 'standalone'` do Next para que o projeto nasça observável e preparado para containerização.

Expected: Healthcheck responde corretamente
Expected: Build standalone gera artefato válido
Expected: Base pronta para etapa posterior de containerização

## Phase 3: Modelo de dados e cena 3D principal

### Task 3.1: Definir tipos centrais de Node, Step e CTA
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Consolidar o modelo de dados central do site com tipos explícitos para nodes, steps e CTAs, alinhados ao PRD e reutilizáveis por cena e overlay.

Expected: Tipos centrais implementados
Expected: Naming e shape consistentes com o PRD
Expected: Cena e overlay podem consumir a mesma estrutura canônica

### Task 3.2: Montar dataset inicial do grafo e dos steps-base
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Materializar em dados explícitos o nó central, nós principais, filhos, relações pai-filho e a base dos steps que consumirão essa estrutura.

Expected: Fonte única de dados da cena criada
Expected: Nós e relações definidos explicitamente
Expected: Steps-base preparados para consumo posterior

### Task 3.3: Implementar layout hand-placed do grafo
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Definir as posições manuais dos nós para preservar legibilidade narrativa, composição visual intencional e previsibilidade entre seções.

Expected: Posições dos nós explícitas e estáveis
Expected: Legibilidade entre tiers validada
Expected: Composição coerente com o conceito do PRD

### Task 3.4: Implementar renderização base dos nós com hierarquia visual
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Construir a renderização dos nós respeitando distinção entre BEVOX, nós principais e filhos, incluindo escala, opacidade base e presença visual do root.

Expected: Todos os nós podem ser renderizados
Expected: Hierarquia visual perceptível
Expected: Base pronta para integração com reveal por step

### Task 3.5: Implementar conexões e pulsos do grafo
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Adicionar as linhas entre pai e filho e os pulsos que percorrem essas conexões para reforçar a leitura de sistema conectado e vivo.

Expected: Conexões entre nós implementadas
Expected: Pulsos funcionais nas arestas
Expected: Leitura do grafo reforçada sem poluição visual excessiva

### Task 3.6: Implementar atmosfera da cena com starfield, dust e glow
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Criar a atmosfera visual base da cena com starfield, partículas de proximidade e glow por nó para aproximar a experiência do feeling definido no PRD.

Expected: Starfield implementado
Expected: Dust implementado
Expected: Glow básico por nó funcionando

### Task 3.7: Implementar câmera com focus, distance, damping e drag orbit
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Preparar o comportamento de câmera que será controlado por estado e usado na narrativa por scroll e nas interações secundárias.

Expected: Câmera controlável por estado
Expected: Focus e distance implementados
Expected: Damping e drag orbit estáveis

### Task 3.8: Implementar estratégia inicial de bloom e performance por capacidade
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Estruturar a camada inicial de bloom no desktop e o caminho técnico para modular custo visual conforme a capacidade do dispositivo.

Expected: Bloom base no desktop funcional
Expected: Estratégia inicial de custo visual implementada
Expected: Caminho preparado para integração com fallback/capacidade

## Phase 4: Engine narrativa baseada em scroll

### Task 4.1: Implementar estrutura de 6 steps e sections de altura total
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Criar a espinha narrativa da página com seis steps e sections de 100vh para suportar a progressão hero até contato.

Expected: Seis steps definidos
Expected: Sections de altura total implementadas
Expected: Estrutura narrativa previsível pronta para scroll state

### Task 4.2: Integrar scroll com estado global
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Conectar a rolagem da página ao estado de step ativo de forma robusta, incluindo navegação para frente e para trás entre seções.

Expected: Step ativo responde ao scroll
Expected: Navegação ascendente e descendente estável
Expected: Estratégia de integração de scroll funcional

### Task 4.3: Implementar progressive disclosure cumulativo dos nós
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Traduzir a regra central do PRD para comportamento real da cena, garantindo que nós revelados permaneçam visíveis nas etapas seguintes.

Expected: RevealedIds por step funcionando
Expected: Nós já revelados permanecem visíveis
Expected: Crescimento cumulativo do grafo verificável

### Task 4.4: Integrar transições de câmera aos focus points de cada step
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Associar cada step a um foco e distância da câmera para que o enquadramento reforce a leitura narrativa da seção ativa.

Expected: Cada step possui focus point e distância
Expected: Câmera transiciona suavemente entre steps
Expected: Enquadramento coerente com o conteúdo de cada seção

### Task 4.5: Implementar navegações secundárias para steps relevantes
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Permitir saltos coerentes entre pontos importantes da jornada por meio de cliques em elementos de navegação e interações secundárias relevantes.

Expected: Navegação suave para step alvo implementada
Expected: Compatibilidade com nav e rail prevista
Expected: Narrativa continua consistente fora do scroll linear puro

## Phase 5: Overlay editorial e navegação

### Task 5.1: Implementar navbar institucional com comportamento de scroll
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Criar a navbar fixa com comportamento visual coerente ao rolar e integração com as seções narrativas do site.

Expected: Navbar fixa implementada
Expected: Estado visual em scroll funcionando
Expected: Links integrados à estrutura de steps

### Task 5.2: Implementar CopyCard com layouts center, left e right
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Construir o componente editorial principal que renderiza eyebrow, título, body e CTA nos três layouts previstos pela narrativa.

Expected: CopyCard suporta os 3 layouts
Expected: Conteúdo editorial por step renderiza corretamente
Expected: Troca de step produz transição legível e estável

### Task 5.3: Implementar ChipCards ancorados aos nós
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Fazer a projeção de posições 3D para overlay 2D e renderizar chips vinculados aos nós corretos em cada seção relevante.

Expected: Chips acompanham os nós corretos
Expected: Projeção 3D→2D funcional
Expected: Estratégia básica de anti-clipping implementada

### Task 5.4: Implementar ProgressRail e ScrollHint
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Adicionar os elementos de orientação que sinalizam progressão na jornada e reforçam a estrutura narrativa do hero ao contato.

Expected: ProgressRail implementada
Expected: Step ativo destacado
Expected: ScrollHint funcional no hero

### Task 5.5: Implementar hover e microinterações entre overlay e cena
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Adicionar feedback visual coerente a nós, chips e elementos navegáveis sem transformar a interface em ruído excessivo.

Expected: Hover em nós funcional
Expected: Hover em elementos editoriais funcional
Expected: Microinterações reforçam a leitura da experiência

## Phase 6: Conteúdo estruturado, SEO e acessibilidade

### Task 6.1: Estruturar content/copy.json e conectar conteúdo ao app
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Separar conteúdo da implementação criando uma fonte única de copy estruturada e conectando os steps e componentes editoriais a ela.

Expected: copy.json estruturado
Expected: Steps consomem a fonte única de conteúdo
Expected: Copy hardcoded espalhado foi evitado

### Task 6.2: Implementar camada semântica paralela para indexação e leitores de tela
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Criar representação HTML semântica da narrativa para garantir existência do conteúdo além do canvas.

Expected: Estrutura semântica paralela implementada
Expected: Conteúdo indexável em HTML
Expected: Base compatível com leitores de tela criada

### Task 6.3: Implementar meta tags, canonical, OG image e analytics
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Preparar a superfície para compartilhamento, indexação e observabilidade institucional básica.

Expected: Meta tags principais configuradas
Expected: Canonical e OG image definidos
Expected: Analytics básico integrado

### Task 6.4: Implementar navegação por teclado e requisitos mínimos de acessibilidade
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Garantir que a experiência possa ser percorrida sem depender exclusivamente de mouse, trackpad ou percepção visual plena.

Expected: Ordem de foco coerente
Expected: Elementos relevantes acessíveis por teclado
Expected: Requisitos mínimos de interação acessível implementados

### Task 6.5: Validar checklist mínimo de WCAG AA da v1
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Fechar acessibilidade como critério verificável revisando contraste, semântica, foco e navegação e registrando pendências residuais.

Expected: Checklist mínimo de acessibilidade validado
Expected: Pendências residuais documentadas
Expected: Condição mínima de WCAG AA avaliada explicitamente

## Phase 7: Estratégia mobile, fallback e comportamento por capacidade

### Task 7.1: Implementar detecção de viewport e capacidade gráfica
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Instrumentar o app para distinguir cenários desktop premium de cenários restritos e expor essa decisão à navegação e renderização.

Expected: Detecção de viewport implementada
Expected: Detecção de capacidade gráfica implementada
Expected: Decisão de servir 3D ou fallback centralizada

### Task 7.2: Implementar fallback para a versão 2D institucional
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Aplicar a política de fallback definida para direcionar usuários fora do cenário ideal para uma superfície institucional válida.

Expected: Fallback 2D implementado
Expected: Redirect ou comportamento equivalente funcional
Expected: Mobile degradado por omissão eliminado

### Task 7.3: Validar comportamento em mobile e tablet
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Verificar na prática se a política mobile e o fallback se comportam conforme planejado em cenários de viewport e capacidade diferentes.

Expected: Cenários mobile/tablet testados
Expected: Comportamento de fallback validado
Expected: Gaps entre intenção e resultado registrados

## Phase 8: Infra, deploy e operação

### Task 8.1: Criar Dockerfile multi-stage e validar build containerizável
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Transformar o projeto em artefato de deploy reproduzível por meio de um Dockerfile multi-stage alinhado ao build standalone.

Expected: Dockerfile multi-stage criado
Expected: Imagem/container builda corretamente
Expected: Build não depende de ajustes manuais frágeis

### Task 8.2: Criar docker-compose e base de runtime local/servidor
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Definir a forma operacional base de subir o site e seus serviços associados em ambiente local e de servidor.

Expected: docker-compose criado
Expected: Base de runtime definida
Expected: Preparação para integração com Cloudflare Tunnel estabelecida

### Task 8.3: Integrar Cloudflare Tunnel e requisitos de domínio
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Conectar a entrega técnica à forma real de publicação prevista no PRD, alinhando tunnel, token e domínio `example.com`.

Expected: Integração com Cloudflare Tunnel preparada
Expected: Requisitos operacionais externos explicitados
Expected: Caminho de publicação via Cloudflare definido

### Task 8.4: Criar pipeline inicial de CI/CD para build e deploy
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Automatizar o caminho básico entre código, imagem e publicação para reduzir dependência de operação manual tácita.

Expected: Workflow de build criado
Expected: Integração com registry implementada
Expected: Caminho básico de deploy/restart funcional

### Task 8.5: Escrever documentação operacional mínima e runbook de deploy
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Documentar como rodar, editar conteúdo, buildar, deployar e verificar a saúde básica da v1.

Expected: Documentação operacional mínima escrita
Expected: Runbook de deploy registrado
Expected: Operação básica não depende de memória implícita do implementador

## Phase 9: QA, performance e polish final

### Task 9.1: Executar QA cross-browser e registrar gaps críticos
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Verificar consistência da experiência nos navegadores-alvo principais e registrar gaps de rendering ou interação que afetem a v1.

Expected: Navegadores-alvo testados
Expected: Gaps críticos registrados
Expected: Estado cross-browser da v1 conhecido

### Task 9.2: Revisar a experiência contra o protótipo funcional de referência
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Comparar narrativa visual, ritmo de reveal, comportamento de câmera e atmosfera com o protótipo funcional que originou o PRD.

Expected: Comparação explícita com o protótipo realizada
Expected: Divergências relevantes registradas ou corrigidas
Expected: Feeling conceitual validado contra a referência

### Task 9.3: Ajustar motion, glow e performance para nível de apresentação
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Tunar transições, glow, bloom e custo visual para sair do estado funcional e atingir qualidade de apresentação comercial.

Expected: Motion refinado
Expected: Glow/bloom refinados
Expected: Equilíbrio aceitável entre performance e qualidade visual alcançado

### Task 9.4: Fazer revisão final de conteúdo e release readiness
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Fechar a camada editorial e de publicação revisando copy, CTAs, links, metadados e checklist final de publicação.

Expected: Copy aplicada revisada
Expected: CTAs e links revisados
Expected: Checklist final de publicação conferido

### Task 9.5: Validar release final da v1 do bevox-site
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
**spec_ref:** `bevox-knowledge/35_specs/bevox-site/2026-04-27-bevox-site-execution-spec-v1.md`
Concluir a cadeia PRD → roadmap → spec → tasks com validação explícita de que a v1 está pronta e rastreável ao backlog.

Expected: Marcos principais verificados
Expected: Blocos essenciais validados
Expected: Estado final da v1 explicitamente registrado
