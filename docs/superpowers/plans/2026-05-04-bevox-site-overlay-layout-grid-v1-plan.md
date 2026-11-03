**Project:** bevox-site
**Epico:** e4/overlay-layout-grid-v1
**Goal:** implementar o grid editorial de 9 posições do CopyCard e a lógica de anti-colisão dos ChipCards, eliminando sobreposição visual no Step 1 e ampliando o controle de composição do overlay
**Spec:** `bevox-knowledge/35_specs/bevox-site/2026-05-04-overlay-layout-grid-v1.md`

## Phase 1: Base estrutural do grid editorial

### Task 1.1: Expandir o modelo de layout do CopyCard para 9 posições tipadas
- [ ] **Step 1: atualizar a tipagem canônica de layout em `types/scene.ts` para representar as 9 posições suportadas**
- [ ] **Step 2: criar o mapeamento único de `LayoutPosition` para classes/estilos de viewport com margens seguras desktop**
- [ ] **Step 3: preservar compatibilidade do componente editorial com a estrutura atual de steps e conteúdo**
Spec ref: `bevox-knowledge/35_specs/bevox-site/2026-05-04-overlay-layout-grid-v1.md`
Expected: `LayoutPosition` suporta explicitamente `top-left`, `top-center`, `top-right`, `middle-left`, `center`, `middle-right`, `bottom-left`, `bottom-center` e `bottom-right`.
Expected: o `CopyCard` passa a consumir um mapeamento único e rastreável de posição para viewport, sem hardcodes dispersos.
Expected: o sistema mantém margens seguras em desktop e não introduz erro de TypeScript nas propriedades de layout.

## Phase 2: Reposicionamento narrativo por step

### Task 2.1: Refatorar o CopyCard para animar transições suaves entre as 9 posições
- [ ] **Step 1: adaptar `components/overlay/CopyCard.tsx` para posicionamento por grid em vez de apenas center/left/right**
- [ ] **Step 2: integrar transições suaves com Framer Motion entre mudanças de step e de posição**
- [ ] **Step 3: garantir que a mudança de posição não produza teleporte brusco nem quebra de alinhamento editorial**
Spec ref: `bevox-knowledge/35_specs/bevox-site/2026-05-04-overlay-layout-grid-v1.md`
Expected: o `CopyCard` renderiza corretamente nas 9 posições previstas pelo novo grid editorial.
Expected: a troca de posição entre steps é animada de forma suave e perceptível, sem saltos bruscos.
Expected: a estrutura editorial do card continua legível e estável durante as transições.

### Task 2.2: Atualizar o mapeamento dos steps para as novas posições editoriais
- [ ] **Step 1: ajustar a fonte de dados canônica dos steps para aceitar a posição exata por step**
- [ ] **Step 2: aplicar o reposicionamento solicitado para Hero, O que fazemos, Sobre, Princípios, Processo e Contato**
- [ ] **Step 3: validar o alinhamento visual final das posições definidas no fluxo narrativo desktop**
Spec ref: `bevox-knowledge/35_specs/bevox-site/2026-05-04-overlay-layout-grid-v1.md`
Expected: a fonte de dados (`lib/scene-data.ts` ou `content/copy.json`, conforme arquitetura vigente) permite configurar a posição do CopyCard por step sem ambiguidade.
Expected: os steps ficam mapeados para as posições solicitadas na spec, com Step 2 em `bottom-right`, Step 4 em `top-right` e Step 5 em `top-left`.
Expected: o Hero e o Step 1 ficam posicionados à esquerda do viewport em uma configuração visual coerente com a composição aprovada.

## Phase 3: Anti-colisão dos chips ancorados aos nós

### Task 3.1: Implementar projeção 2D e lógica de anti-colisão dos ChipCards
- [ ] **Step 1: projetar a posição 3D dos nós para coordenadas 2D de overlay usando a câmera ativa**
- [ ] **Step 2: medir a área ocupada pelo CopyCard ativo e detectar risco de sobreposição visual com margem mínima configurável**
- [ ] **Step 3: inverter ou reposicionar o offset do ChipCard quando houver colisão, com foco no caso crítico do Step 1**
Spec ref: `bevox-knowledge/35_specs/bevox-site/2026-05-04-overlay-layout-grid-v1.md`
Expected: o `ChipCard` usa projeção 3D→2D e comparação com a área do `CopyCard` para decidir seu posicionamento final.
Expected: existe uma distância mínima configurável entre chip e CopyCard, com baseline operacional de 24px ou equivalente configurado no código.
Expected: no Step 1 o chip “projetos feitos sob medida” não se sobrepõe ao texto do CopyCard.

### Task 3.2: Validar o comportamento visual integrado do overlay editorial
- [ ] **Step 1: revisar o comportamento conjunto de CopyCard e ChipCards nos steps impactados pela nova lógica**
- [ ] **Step 2: ajustar offsets, margens e fallback de flip quando necessário para robustez visual desktop**
- [ ] **Step 3: registrar que o sistema atende os critérios funcionais e técnicos da spec de overlay grid**
Spec ref: `bevox-knowledge/35_specs/bevox-site/2026-05-04-overlay-layout-grid-v1.md`
Expected: o overlay editorial mantém composição visual estável nos steps reposicionados em desktop.
Expected: não há colisão visível entre CopyCard e ChipCards nos cenários cobertos pela spec, especialmente no Step 1.
Expected: a implementação final atende os critérios de posicionamento preciso, animação fluida, responsividade básica e tipagem correta descritos na spec.
