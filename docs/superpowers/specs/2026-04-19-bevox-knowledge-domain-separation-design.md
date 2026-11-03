# Bevox Knowledge — separação por domínio

**Data:** 2026-04-19
**Status:** proposta (aguarda review do Bernard)
**Escopo:** convenção de organização do `bevox-knowledge` para acomodar os 4 produtos Bevox + Company OS
**Não é ADR.** ADR-002 (topology) permanece intacta. Este spec documenta convenção de estrutura documental, não decisão de arquitetura de sistema.

---

## 1. Problema

O `bevox-knowledge` hoje é organizado por tipo de documento (`10_prd/`, `20_architecture/`, `30_adr/`, `35_specs/`, `40_roadmap/`, `50_releases/`, etc.). Não há segunda dimensão clara por domínio/produto. Todo conteúdo atual é Company OS (OpenClaw + ecossistema); nenhum conteúdo dos 4 produtos Bevox (`bevox-console`, `bevox-harness`, `bevox-mobile`, `bevox-web`) foi escrito ainda.

Quando os produtos começarem a gerar PRDs, specs, roadmaps e releases, a taxonomia atual fica ambígua: onde vai um PRD de `bevox-harness`? Como distinguir um spec de produto de um spec de Company OS? A dor hoje é leve mas antecipada — já houve hesitação sobre classificação.

O objetivo desta wave é travar a convenção futura, não migrar o legado.

## 2. Decisão

Adicionar uma segunda dimensão **por domínio** apenas onde o volume e a natureza do artefato justificam, mantendo a taxonomia por tipo no topo.

**5 domínios válidos:**
- `bevox-console`
- `bevox-harness`
- `bevox-mobile`
- `bevox-web`
- `company-os` (guarda-chuva para OpenClaw, Vox, Mission Control, Agent Registry, Approval Center, knowledge-sync, delivery-tracker e demais capabilities internas do ecossistema Bevox conforme CLAUDE.md §4)

**Separação híbrida por natureza do artefato:**
- `10_prd/`, `40_roadmap/`, `50_releases/`: **subpasta por domínio**
- `35_specs/`: **flat + prefixo de domínio no filename**
- `30_adr/`, `20_architecture/`: **inalterados** — flat, cross-cutting por natureza

## 3. Estrutura final

```
bevox-knowledge/
├── 10_prd/
│   ├── README.md                  (atualizado)
│   └── <dominio>/                 (criado on-demand)
│       └── <topic>.md
├── 20_architecture/               INALTERADO
│   ├── modules/*.md               (âncora canônica dos 4 produtos)
│   ├── agents/
│   └── *.md                       (system-map, knowledge-spine, etc.)
├── 30_adr/                        INALTERADO (flat)
├── 35_specs/                      flat, prefixo de domínio no filename
│   └── YYYY-MM-DD-<dominio>-<topic>.md
├── 40_roadmap/
│   ├── README.md                  (atualizado)
│   ├── delivery-tracker.yml       (permanece no root — cross-domain)
│   ├── 2026-04-09-openclaw-company-os-roadmap.md   (LEGADO, fica flat)
│   └── <dominio>/                 (criado on-demand)
│       └── YYYY-MM-DD-<topic>.md
├── 50_releases/
│   ├── README.md                  (atualizado)
│   ├── 2026-04-11-company-os-e10-wave-1-release.md  (LEGADO, fica flat)
│   └── <dominio>/                 (criado on-demand)
│       └── YYYY-MM-DD-<topic>.md
├── 60_customer-feedback/          INALTERADO (vazio, convenção quando surgir conteúdo)
├── 70_metrics/                    INALTERADO (vazio, convenção quando surgir conteúdo)
└── 99_templates/                  INALTERADO
```

**Decisões estruturais:**
- Subpastas criadas on-demand, nunca pré-criadas vazias.
- `delivery-tracker.yml` permanece no root de `40_roadmap/` por ser cross-domain por design.
- Dois artefatos legados (roadmap OpenClaw + release E10 wave-1) ficam flat. Sem movimentação.
- `60_customer-feedback/` e `70_metrics/` ficam fora desta wave — convenção decidida quando aparecer conteúdo real.

## 4. Convenção de naming

| Tipo | Padrão | Exemplo |
|---|---|---|
| PRD | `10_prd/<dominio>/<topic>.md` | `10_prd/bevox-harness/telephony-v1.md` |
| Spec | `35_specs/YYYY-MM-DD-<dominio>-<topic>.md` | `35_specs/2026-05-01-bevox-harness-telephony-wave-1.md` |
| Roadmap | `40_roadmap/<dominio>/YYYY-MM-DD-<topic>.md` | `40_roadmap/bevox-harness/2026-05-01-roadmap.md` |
| Release | `50_releases/<dominio>/YYYY-MM-DD-<topic>.md` | `50_releases/bevox-harness/2026-05-01-telephony-v1.md` |

**Specs do Company OS a partir da data de corte:** novos specs Company OS ganham prefixo explícito `company-os` no filename. Exemplo: próxima spec Company OS seria `2026-05-01-company-os-e<N>-<topic>.md`. O padrão atual (sem prefixo) fica reservado ao legado.

Justificativa: consistência > familiaridade. Manter Company OS sem prefixo criaria assimetria (regra especial para Company OS). O custo de adicionar `company-os-` em cada filename novo é baixo; o benefício é que a convenção fica uniforme.

## 5. Regra de classificação

Aplicar em ordem, decidir no primeiro "sim":

1. **Existe um produto principal** (`bevox-console`, `bevox-harness`, `bevox-mobile`, `bevox-web`) ao qual este artefato pertence? → domínio é esse produto.
2. **É governança, coordenação ou capability interna do ecossistema** (OpenClaw, Vox, Mission Control, Agent Registry, Approval Center, knowledge-sync, delivery-tracker, demais capabilities Company OS)? → `company-os`.
3. **Não se encaixa claramente em nenhum?** → pare, decida explicitamente antes de criar. Não criar bucket genérico `shared/`. Se o padrão recorrer, vira follow-up para reabrir a convenção.

Sem fallback `shared/` nesta wave. Decisão consciente.

## 6. Data de corte e compatibilidade

**Data de corte: 2026-04-19** (data deste spec).

- Todo artefato **novo** a partir desta data, nos tipos `10_prd/`, `35_specs/`, `40_roadmap/`, `50_releases/`, segue a convenção acima.
- Todo artefato **existente** anterior a esta data permanece válido exatamente onde está, com o nome que tem. Não é necessário renomear nem mover.
- Legado e convenção nova coexistem no mesmo tipo sem conflito — subpastas `<dominio>/` ficam lado a lado com arquivos flat legados até uma eventual migração futura.

**Compatibilidade declarada:**
- Consumidores do `bevox-knowledge` (Mission Control via `/api/delivery/tracker`, leitura do `knowledge-sync`, referências em `CLAUDE.md`, refs entre specs) continuam funcionando sem alteração. Nenhum path existente muda.
- Novos consumidores podem resolver paths por convenção (subpasta) para artefatos pós-corte, e por referência explícita (path completo) para legado.

## 7. Escopo desta wave

**Entra nesta wave:**
1. Canonização deste spec em `bevox-knowledge/35_specs/2026-04-19-company-os-bevox-knowledge-domain-separation.md` (conteúdo copiado do rascunho em `~/.openclaw/docs/superpowers/specs/`; filename já obedece a convenção nova, serve de primeiro exemplo).
2. Update dos 4 READMEs em `bevox-knowledge/`:
   - `README.md` (raiz)
   - `10_prd/README.md`
   - `40_roadmap/README.md`
   - `50_releases/README.md`
3. Nenhum arquivo de conteúdo novo de produto. Nenhuma movimentação de legado. Nenhum arquivo de outro tipo alterado.

**Não entra nesta wave:**
- Migração do legado (nenhum arquivo movido ou renomeado)
- Criação de subpastas stub vazias
- Convenção para `60_customer-feedback/` e `70_metrics/`
- Tooling de validação (linter de paths, pre-commit hook)
- ADR nova — esta é convenção documental, não decisão arquitetural

## 8. Inventário de referências (não-destrutivo)

Mapa do que seria afetado por uma eventual migração futura. **Nada é tocado nesta wave.**

| Categoria | Volume | Localização | Impacto de migração |
|---|---|---|---|
| Specs legados flat | 44 arquivos | `bevox-knowledge/35_specs/*.md` | rename em massa (add prefixo `company-os-`) + update de todas as refs |
| Roadmap legado | 1 arquivo | `bevox-knowledge/40_roadmap/2026-04-09-openclaw-company-os-roadmap.md` | move para `40_roadmap/company-os/` + update refs em `CLAUDE.md`, specs |
| Release legado | 1 arquivo | `bevox-knowledge/50_releases/2026-04-11-company-os-e10-wave-1-release.md` | move para `50_releases/company-os/` + update refs |
| `delivery-tracker.yml` | 1 arquivo | `bevox-knowledge/40_roadmap/delivery-tracker.yml` | **não migra** (cross-domain por design) |
| Refs em `CLAUDE.md` do OpenClaw | 8 refs | `~/.openclaw/CLAUDE.md` | update de 8 strings |
| Refs em `delivery-tracker.yml` | 27 refs | `bevox-knowledge/40_roadmap/delivery-tracker.yml` | update de 27 paths de spec |
| Refs entre specs | ≥20 arquivos | dentro de `bevox-knowledge/` | update em cascata |
| Refs em `20_architecture/*.md` | a investigar | ex.: `hardening-registry.md`, `health-registry.md` | update pontual |
| Mission Control (app Next.js) | 0 refs hardcoded verificadas | `~/.openclaw/mission-control/` | resiliente; usa `/api/delivery/tracker` que resolve via tracker |

Checagem usada: `grep -c` em `CLAUDE.md` e `delivery-tracker.yml`, `ls` em `35_specs/`, `grep -r` leve em Mission Control source.

## 9. Impacto de eventual migração futura

Se no futuro o Bernard decidir migrar o legado para a convenção nova:

**Custo técnico:**
- Rename de 44 specs em 1 PR (scriptável: `for f in 35_specs/*.md; do git mv "$f" "${f/35_specs\/2026/35_specs\/2026-}-company-os-..." ; done` — script real precisa de regex por nome)
- Move de 2 arquivos (roadmap + release)
- Update de ~60 refs em paths (CLAUDE.md + delivery-tracker.yml + specs entre si)
- Regenerar `delivery-tracker.yml` consumers (render tools no `20_architecture/_tools/` se houver)

**Risco:**
- Breakage de URLs externas (issues GitHub linkando paths específicos)
- Breakage de ADR refs (ADRs referenciando specs por path)
- Bookmarks/notas operacionais do Bernard

**Mitigação recomendada quando e se a migração acontecer:**
- Fazer num único commit atômico para preservar git blame
- Script determinístico, revisável
- PR draft primeiro, só merge depois de smoke de MC e sync canônico
- `knowledge-sync` pull-ff em todos os clones
- Atualizar `CLAUDE.md` no mesmo commit

**Gatilho para considerar migração:**
- Assimetria começa a confundir navegação (Bernard ou Claude Code perdendo tempo para achar algo)
- Ferramenta automatizada assumir convenção uniforme e quebrar em legado
- Volume de legado Company OS se torna pequeno relativo ao conteúdo novo

**Posição default enquanto não houver esse gatilho:** não migrar.

## 10. Updates de README (detalhe)

### `bevox-knowledge/README.md`
Adicionar seção "Domínios":
- Lista os 5 domínios.
- Nota na tabela de estrutura: "alguns tipos usam subpasta por domínio — ver README do tipo".
- Link ao spec.

Adicionar seção "Classificação por domínio" com a regra de 3 passos.

### `bevox-knowledge/10_prd/README.md`
- Propósito: PRDs por produto/domínio.
- Convenção: `<dominio>/<topic>.md`.
- Lista domínios válidos.
- Ref à regra de classificação no README root.

### `bevox-knowledge/40_roadmap/README.md`
- Propósito.
- Convenção: `<dominio>/YYYY-MM-DD-<topic>.md`.
- Exceções explícitas:
  - `delivery-tracker.yml` fica no root (cross-domain).
  - `2026-04-09-openclaw-company-os-roadmap.md` fica no root (legado pré-2026-04-19).
- Ref à regra de classificação.

### `bevox-knowledge/50_releases/README.md`
- Propósito.
- Convenção: `<dominio>/YYYY-MM-DD-<topic>.md`.
- Exceção: `2026-04-11-company-os-e10-wave-1-release.md` fica no root (legado).
- Ref à regra de classificação.

## 11. Follow-ups (não nesta wave)

- Primeiro PRD/roadmap/release real de um dos 4 produtos (gatilho: produto começar a desenvolver)
- Convenção para `60_customer-feedback/` e `70_metrics/` (gatilho: conteúdo real)
- Migração do legado (gatilho: assimetria virar dor concreta)
- Se padrão multi-produto sem owner claro emergir: reabrir discussão sobre bucket `shared/` ou equivalente
- Tooling de validação de paths (ex.: pre-commit hook) — só se drift começar a acontecer

## 12. Gaps aceitos

- Assimetria temporária: legado flat + convenção nova com subpastas coexistem sem resolução
- `company-os` como guarda-chuva único, sem sub-divisão para OpenClaw/Vox/MC/etc. — aceito até volume justificar
- Ausência de `shared/`: artefatos multi-produto sem owner claro exigem decisão caso-a-caso

## 13. Fora de escopo

- ADR-002 (topology) permanece intacta
- Reorganização de `20_architecture/` ou `30_adr/`
- Movimentação ou rename de qualquer arquivo existente
- Tooling automatizado
- Alteração em repos fora do `bevox-knowledge` (exceto refs em `CLAUDE.md` do OpenClaw no update do README raiz — se necessário; resolvo no plan)
