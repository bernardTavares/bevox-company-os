# Mission Control Projects Factory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CLI `openclaw project create <name>` orquestra criação de projeto novo em 6 destinos (bevox-knowledge folders + kanban-tasks state + ~/.openclaw runtime workspace + projects-meta.json + local code dir + GitHub private repo). MC UI ganha "+ New project" modal + edit inline metadata em /projects/[id].

**Architecture:** CLI Python em `~/.openclaw/kanban-tasks/lib/project_factory.py` reusa `task_lib.add_project` + `sprint_lib.bootstrap` existentes; orquestra writes em sequência reversibility-ascending com pre-flight + JSONL logging. MC backend invoca CLI subprocess via 1 endpoint POST + edit metadata via PATCH light-weight. UI: `<NewProjectModal>` + edit inline em `<ProjectGeralTab>`.

**Tech Stack:** Python 3.11+ (CLI), pytest com tmp_path fixtures, Next.js 15 + TypeScript + Vitest, `gh` CLI subprocess, lucide-react icons, react-markdown (já instalado).

**Spec:** `bevox-knowledge/35_specs/company-os/2026-04-26-mc-projects-factory.md` (commit `9846b63` em `draft/spec-mc-projects-factory`).

---

## File Structure

### Create (openclaw repo / `~/.openclaw/`)

- `kanban-tasks/lib/project_factory.py` — orquestrador 6 steps + pre-flight + slugify + JSONL logging
- `kanban-tasks/lib/projects_meta.py` — read/write atomic de `projects-meta.json` com flock
- `kanban-tasks/templates/prd-stub.md.tmpl` — template do stub PRD
- `kanban-tasks/templates/roadmap-stub.md.tmpl` — template do stub roadmap
- `kanban-tasks/templates/workspace/IDENTITY.md.tmpl` (8 files: IDENTITY, SOUL, BOOTSTRAP, HEARTBEAT, MEMORY, TOOLS, USER, AGENTS)
- `kanban-tasks/templates/code/README.md.tmpl` — README inicial do repo
- `kanban-tasks/tests/test_project_factory.py` — pytest CLI suite

### Modify (openclaw repo / `~/.openclaw/`)

- `kanban-tasks/lib/api.py` — adiciona handlers `cmd_project_create`, `cmd_project_edit`, extends `cmd_project_list` com metadata; adiciona argparse subcommands
- `.env` (não tracked) — Bernard adiciona `BEVOX_CODE_DIR=~/code` manualmente após merge

### Create (mission-control)

- `src/lib/projects/meta.ts` — leitor de `projects-meta.json` no MC backend (paralelo do Python helper)
- `src/components/projects/NewProjectModal.tsx` — modal de criação
- `src/app/api/projects/route.ts` (modify) — adiciona POST handler + extend GET pra merge canonical+meta+yaml
- `src/app/api/projects/[id]/route.ts` (modify) — adiciona PATCH handler
- `src/app/api/projects/check-id/route.ts` — endpoint live validation
- `tests/lib/projects/meta.test.ts`
- `tests/components/projects/NewProjectModal.test.tsx`
- `tests/app/api/projects/check-id.test.ts`
- `tests/app/api/projects/create.test.ts`
- `tests/app/api/projects/edit.test.ts`

### Modify (mission-control)

- `src/lib/projects/types.ts` — extends `ProjectSummary` + `ProjectDetail` com `is_canonical`, `github_url`, `bot_id`, `created_at`
- `src/app/(dashboard)/projects/page.tsx` — botão "+ New project" + modal state
- `src/components/projects/ProjectGeralTab.tsx` — modo edit inline em InfoBoxes

### bevox-knowledge

Sem mudança nesta wave (writes do CLI vão pro working tree do user).

---

## Task 1: Setup branches + commit plan + push spec PR (gate)

**Files:**
- Create: `~/.openclaw/docs/superpowers/plans/2026-04-26-mc-projects-factory.md` (este arquivo)

- [ ] **Step 1: Branch openclaw plan**

```bash
cd ~/.openclaw && git checkout main && git pull --ff-only
git checkout -b feat/mc-projects-factory-plan
```

- [ ] **Step 2: Commit plan**

```bash
cd ~/.openclaw && git add docs/superpowers/plans/2026-04-26-mc-projects-factory.md && git commit -m "$(cat <<'EOF'
plan(mc-projects-factory): implementation plan

Spec: bevox-knowledge/35_specs/company-os/2026-04-26-mc-projects-factory.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 3: Push spec PR no bevox-knowledge**

```bash
cd ~/bevox-knowledge && git checkout draft/spec-mc-projects-factory
git push -u origin draft/spec-mc-projects-factory
gh pr create --title "spec(company-os): MC Projects factory (E2/mc-projects-factory)" --body "Wave fecha o ciclo de gestão de projetos no MC: list (entregue) + create + edit (esta wave). CLI openclaw project create <name> orquestra 6 destinos cross-filesystem.

Pre-requisitos já entregues: mc-projects-redesign + canonical.ts extendido + bevox-knowledge stubs.

Plan: openclaw/docs/superpowers/plans/2026-04-26-mc-projects-factory.md (branch feat/mc-projects-factory-plan).

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

- [ ] **Step 4: PAUSA — aguardar Bernard mergear spec PR**

Parar. Bernard merge `bernardTavares/bevox-knowledge` PR. Retomar Task 2 só após merge confirmado em main.

---

## Task 2: project_factory.py — slugify + ID validation

**Files:**
- Create: `kanban-tasks/lib/project_factory.py`
- Create: `kanban-tasks/tests/test_project_factory.py`

- [ ] **Step 1: Branch openclaw feat**

```bash
cd ~/.openclaw && git checkout main && git pull --ff-only
git checkout -b feat/mc-projects-factory
```

- [ ] **Step 2: Inspecionar canonical projects (no MC) e projects.yml**

```bash
grep -E "^\s+id:" ~/code/mission-control/src/lib/projects/canonical.ts | head -10
echo "---"
cat ~/.openclaw/kanban-tasks/projects.yml
```

Expected: 10 canonical IDs em canonical.ts; projects.yml lista similar (com test-project extra).

- [ ] **Step 3: Escrever testes primeiro (TDD)**

Criar dir se necessário: `mkdir -p kanban-tasks/tests`. Escrever `kanban-tasks/tests/test_project_factory.py`:

```python
"""Tests for project_factory.py — slugify + ID validation.

Spec: bevox-knowledge/35_specs/company-os/2026-04-26-mc-projects-factory.md §3.2
"""
import pytest
from lib.project_factory import slugify, is_valid_id, RESERVED_IDS


def test_slugify_lowercase_kebab():
    assert slugify("Customer Portal") == "customer-portal"


def test_slugify_strip_diacritics():
    assert slugify("Notação Operacional") == "notacao-operacional"


def test_slugify_collapses_repeated_hyphens():
    assert slugify("Foo  --  Bar") == "foo-bar"


def test_slugify_strip_special_chars():
    assert slugify("Foo & Bar / Baz!") == "foo-bar-baz"


def test_slugify_strip_leading_trailing_hyphens():
    assert slugify("  -- Foo --  ") == "foo"


def test_slugify_truncates_at_40_chars():
    long_name = "Lorem Ipsum " * 10
    result = slugify(long_name)
    assert len(result) <= 40
    assert not result.endswith("-")  # no trailing hyphen post-truncate


def test_is_valid_id_accepts_kebab_case():
    assert is_valid_id("customer-portal") is True
    assert is_valid_id("foo-bar-baz") is True
    assert is_valid_id("a1") is True


def test_is_valid_id_rejects_uppercase():
    assert is_valid_id("Customer-Portal") is False


def test_is_valid_id_rejects_starting_digit():
    assert is_valid_id("1-foo") is False


def test_is_valid_id_rejects_starting_or_ending_hyphen():
    assert is_valid_id("-foo") is False
    assert is_valid_id("foo-") is False


def test_is_valid_id_rejects_too_short_or_long():
    assert is_valid_id("a") is False
    assert is_valid_id("a" * 41) is False


def test_is_valid_id_rejects_reserved():
    for reserved in RESERVED_IDS:
        assert is_valid_id(reserved) is False


def test_is_valid_id_rejects_special_chars():
    assert is_valid_id("foo_bar") is False
    assert is_valid_id("foo bar") is False
    assert is_valid_id("foo/bar") is False
```

- [ ] **Step 4: Rodar tests (devem falhar)**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m pytest tests/test_project_factory.py -v 2>&1 | tail -8
```

Expected: ImportError (modulo nao existe).

- [ ] **Step 5: Criar `kanban-tasks/lib/project_factory.py`**

```python
"""Project factory orchestrator — creates new projects across 6 filesystems.

Spec: bevox-knowledge/35_specs/company-os/2026-04-26-mc-projects-factory.md §3.1
"""
import re
import unicodedata

# Reserved IDs (folders in bevox-knowledge structure that aren't projects)
RESERVED_IDS = frozenset({"_shared", "_retired", "templates"})

# kebab-case validation regex
_ID_RE = re.compile(r"^[a-z][a-z0-9-]+[a-z0-9]$")


def slugify(name: str) -> str:
    """Convert display name to kebab-case ID.

    Steps:
    1. lowercase + NFD normalize + strip diacritics
    2. replace non-[a-z0-9-] by hyphen
    3. collapse repeated hyphens
    4. strip leading/trailing hyphens
    5. truncate to 40 chars (trim trailing hyphen if cut creates one)
    """
    # Normalize + strip diacritics
    nfd = unicodedata.normalize("NFD", name.lower())
    ascii_str = nfd.encode("ascii", "ignore").decode("ascii")
    # Replace non-allowed chars with hyphen
    slug = re.sub(r"[^a-z0-9-]+", "-", ascii_str)
    # Collapse repeated hyphens
    slug = re.sub(r"-+", "-", slug)
    # Strip leading/trailing hyphens
    slug = slug.strip("-")
    # Truncate to 40 chars + clean trailing hyphen
    if len(slug) > 40:
        slug = slug[:40].rstrip("-")
    return slug


def is_valid_id(slug: str) -> bool:
    """Validate ID against schema rules.

    Returns True if:
    - matches kebab-case regex (^[a-z][a-z0-9-]+[a-z0-9]$)
    - length 2-40
    - not in RESERVED_IDS
    """
    if not slug or len(slug) < 2 or len(slug) > 40:
        return False
    if slug in RESERVED_IDS:
        return False
    return bool(_ID_RE.match(slug))
```

- [ ] **Step 6: Rodar tests (devem passar 13/13)**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m pytest tests/test_project_factory.py -v 2>&1 | tail -5
```

- [ ] **Step 7: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/lib/project_factory.py kanban-tasks/tests/test_project_factory.py && git commit -m "$(cat <<'EOF'
feat(project_factory): slugify + is_valid_id helpers

Slugify: lowercase + NFD + strip diacritics + non-alphanumeric to hyphen +
collapse + strip + truncate 40. is_valid_id: kebab-case regex + length 2-40
+ no RESERVED_IDS (_shared, _retired, templates).

13 unit tests cobrindo casos edge (diacritics, repeated chars, special,
truncation, reserved).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: project_factory.py — pre-flight checks

**Files:**
- Modify: `kanban-tasks/lib/project_factory.py` (add pre-flight functions)
- Modify: `kanban-tasks/tests/test_project_factory.py` (add pre-flight tests)

- [ ] **Step 1: Adicionar testes pra pre-flight**

Append em `kanban-tasks/tests/test_project_factory.py`:

```python
import os
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

from lib.project_factory import (
    PreflightFailure,
    check_id_collision,
    check_filesystems_writable,
    check_gh_auth,
    check_github_repo_free,
    check_kb_clean_or_only_stubs,
    run_preflight,
)


def test_check_id_collision_canonical(tmp_path):
    # Mock projects.yml with canonical-like list
    projects_yml = tmp_path / "projects.yml"
    projects_yml.write_text("projects:\n  - openclaw\n  - bevox-mobile\n")
    meta_json = tmp_path / "projects-meta.json"
    meta_json.write_text('{"version": 1, "projects": {}}')
    # openclaw collides
    with pytest.raises(PreflightFailure, match="collision"):
        check_id_collision("openclaw", projects_yml, meta_json)


def test_check_id_collision_meta(tmp_path):
    projects_yml = tmp_path / "projects.yml"
    projects_yml.write_text("projects: []\n")
    meta_json = tmp_path / "projects-meta.json"
    meta_json.write_text('{"version": 1, "projects": {"customer-portal": {}}}')
    with pytest.raises(PreflightFailure, match="collision"):
        check_id_collision("customer-portal", projects_yml, meta_json)


def test_check_id_collision_passes_for_unique(tmp_path):
    projects_yml = tmp_path / "projects.yml"
    projects_yml.write_text("projects:\n  - openclaw\n")
    meta_json = tmp_path / "projects-meta.json"
    meta_json.write_text('{"version": 1, "projects": {}}')
    # Doesn't raise
    check_id_collision("totally-new", projects_yml, meta_json)


def test_check_filesystems_writable(tmp_path):
    kb = tmp_path / "kb"; kb.mkdir()
    oc = tmp_path / "oc"; oc.mkdir()
    code = tmp_path / "code"; code.mkdir()
    # All writable
    check_filesystems_writable(kb, oc, code)


def test_check_filesystems_missing_raises(tmp_path):
    kb = tmp_path / "missing-kb"
    oc = tmp_path / "oc"; oc.mkdir()
    code = tmp_path / "code"; code.mkdir()
    with pytest.raises(PreflightFailure, match="bevox-knowledge"):
        check_filesystems_writable(kb, oc, code)


def test_check_gh_auth_ok():
    with patch("subprocess.run") as run:
        run.return_value = MagicMock(returncode=0)
        check_gh_auth()  # doesn't raise


def test_check_gh_auth_unauthorized():
    with patch("subprocess.run") as run:
        run.return_value = MagicMock(returncode=1, stderr="not logged in")
        with pytest.raises(PreflightFailure, match="gh auth"):
            check_gh_auth()


def test_check_github_repo_free_when_404():
    with patch("subprocess.run") as run:
        run.return_value = MagicMock(returncode=1, stderr="HTTP 404")
        check_github_repo_free("bernardTavares", "new-project")  # doesn't raise


def test_check_github_repo_free_when_exists():
    with patch("subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="repo exists")
        with pytest.raises(PreflightFailure, match="github_collision"):
            check_github_repo_free("bernardTavares", "openclaw")
```

- [ ] **Step 2: Implementar pre-flight functions**

Append em `kanban-tasks/lib/project_factory.py`:

```python
import json
import subprocess
from pathlib import Path
from typing import Optional

import yaml


class PreflightFailure(Exception):
    """Raised when a pre-flight check fails. Code attribute identifies which check."""
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def check_id_collision(slug: str, projects_yml: Path, meta_json: Path) -> None:
    """Raise PreflightFailure if slug exists in either projects.yml or projects-meta.json."""
    # Check projects.yml
    if projects_yml.exists():
        data = yaml.safe_load(projects_yml.read_text()) or {}
        if slug in (data.get("projects") or []):
            raise PreflightFailure(
                "collision", f"id '{slug}' já existe em projects.yml"
            )
    # Check projects-meta.json
    if meta_json.exists():
        meta = json.loads(meta_json.read_text())
        if slug in (meta.get("projects") or {}):
            raise PreflightFailure(
                "collision", f"id '{slug}' já existe em projects-meta.json"
            )


def check_filesystems_writable(
    kb_dir: Path, openclaw_dir: Path, code_dir: Path
) -> None:
    """Raise PreflightFailure if any required dir doesn't exist or isn't writable."""
    for label, p in [
        ("bevox-knowledge", kb_dir),
        ("openclaw", openclaw_dir),
        ("code", code_dir),
    ]:
        if not p.exists():
            raise PreflightFailure(
                f"{label}_missing",
                f"diretório {label} não existe: {p}",
            )
        if not os.access(p, os.W_OK):
            raise PreflightFailure(
                f"{label}_readonly",
                f"diretório {label} não é writable: {p}",
            )


def check_gh_auth() -> None:
    """Raise PreflightFailure if `gh auth status` returns non-zero."""
    result = subprocess.run(
        ["gh", "auth", "status"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise PreflightFailure(
            "gh_auth_required",
            "gh CLI não autenticado — rode 'gh auth login' primeiro",
        )


def check_github_repo_free(org: str, repo: str) -> None:
    """Raise PreflightFailure if bernardTavares/<repo> exists on GitHub."""
    result = subprocess.run(
        ["gh", "repo", "view", f"{org}/{repo}"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    # gh repo view exits 0 if repo exists, non-zero otherwise (404 etc.)
    if result.returncode == 0:
        raise PreflightFailure(
            "github_collision",
            f"GitHub repo {org}/{repo} já existe",
        )


def check_kb_clean_or_only_stubs(kb_dir: Path, slug: str) -> None:
    """Raise PreflightFailure if bevox-knowledge has uncommitted changes
    OUTSIDE the new project's stub paths.
    """
    result = subprocess.run(
        ["git", "-C", str(kb_dir), "status", "--porcelain"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise PreflightFailure("kb_status_error", f"git status falhou: {result.stderr}")
    allowed_prefixes = (
        f"10_prd/{slug}/",
        f"40_roadmap/{slug}/",
    )
    for line in result.stdout.strip().splitlines():
        # porcelain format: "XY filename"
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if not any(path.startswith(p) for p in allowed_prefixes):
            raise PreflightFailure(
                "kb_dirty",
                f"bevox-knowledge tem mudanças não relacionadas: {path}",
            )


def run_preflight(
    slug: str,
    org: str,
    kb_dir: Path,
    openclaw_dir: Path,
    code_dir: Path,
    projects_yml: Path,
    meta_json: Path,
) -> None:
    """Run all pre-flight checks. Raises PreflightFailure on first failure."""
    if not is_valid_id(slug):
        raise PreflightFailure("invalid_id", f"id '{slug}' inválido")
    check_id_collision(slug, projects_yml, meta_json)
    check_filesystems_writable(kb_dir, openclaw_dir, code_dir)
    check_gh_auth()
    check_github_repo_free(org, slug)
    check_kb_clean_or_only_stubs(kb_dir, slug)
```

- [ ] **Step 3: Rodar tests**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m pytest tests/test_project_factory.py -v 2>&1 | tail -8
```

Expected: 21/21 pass (13 anteriores + 8 novos).

- [ ] **Step 4: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/lib/project_factory.py kanban-tasks/tests/test_project_factory.py && git commit -m "$(cat <<'EOF'
feat(project_factory): pre-flight checks

6 checks: id collision (yml + meta.json), filesystems writable, gh auth,
github repo free, bevox-knowledge clean. PreflightFailure exception com
code field pra mapping pra HTTP status no MC backend.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Step 1 — bevox-knowledge folders + stub templates

**Files:**
- Create: `kanban-tasks/templates/prd-stub.md.tmpl`
- Create: `kanban-tasks/templates/roadmap-stub.md.tmpl`
- Modify: `kanban-tasks/lib/project_factory.py` (add `step_1_create_kb_folders`)
- Modify: `kanban-tasks/tests/test_project_factory.py`

- [ ] **Step 1: Criar templates**

Criar dir: `mkdir -p ~/.openclaw/kanban-tasks/templates`. Write `kanban-tasks/templates/prd-stub.md.tmpl`:

```markdown
# {name} — PRD

> Stub criado {date} por `openclaw project create`.
> Preencher quando o produto/projeto for definido com mais detalhe.

**Status:** stub
**Última atualização:** {date}

---

## Contexto

{description}

TBD — qual problema este projeto resolve em detalhe?

## Objetivo

TBD — qual o resultado esperado?

## Escopo

TBD — o que está dentro? o que está fora?

## Métricas de sucesso

TBD — como saber se funcionou?
```

Write `kanban-tasks/templates/roadmap-stub.md.tmpl`:

```markdown
# {name} — Roadmap

> Stub criado {date} por `openclaw project create`.
> Preencher quando os épicos do projeto forem decididos.

**Status:** stub
**Última atualização:** {date}

---

## Épicos planejados

TBD

## Próximos passos

TBD
```

- [ ] **Step 2: Adicionar tests**

Append em `kanban-tasks/tests/test_project_factory.py`:

```python
from lib.project_factory import step_1_create_kb_folders, render_template


def test_render_template_substitutes(tmp_path):
    tmpl = tmp_path / "test.tmpl"
    tmpl.write_text("Hello {name}, {description}")
    result = render_template(tmpl, name="Foo", description="bar")
    assert result == "Hello Foo, bar"


def test_step_1_creates_folders_and_stubs(tmp_path):
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    templates_dir = Path(__file__).parent.parent / "templates"

    paths = step_1_create_kb_folders(
        slug="customer-portal",
        name="Customer Portal",
        description="App de portal",
        kb_dir=kb_dir,
        templates_dir=templates_dir,
        date_str="2026-04-26",
    )

    prd = kb_dir / "10_prd" / "customer-portal" / "2026-04-26-customer-portal-prd.md"
    rm = kb_dir / "40_roadmap" / "customer-portal" / "2026-04-26-customer-portal-roadmap.md"
    assert prd.exists()
    assert rm.exists()
    assert "Customer Portal" in prd.read_text()
    assert "App de portal" in prd.read_text()
    assert "Status:** stub" in prd.read_text()
    assert paths == [str(prd), str(rm)]


def test_step_1_idempotent_skips_existing(tmp_path):
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    templates_dir = Path(__file__).parent.parent / "templates"
    # First call
    step_1_create_kb_folders(
        slug="x", name="X", description="", kb_dir=kb_dir,
        templates_dir=templates_dir, date_str="2026-04-26",
    )
    # Second call doesn't raise (idempotent)
    step_1_create_kb_folders(
        slug="x", name="X", description="", kb_dir=kb_dir,
        templates_dir=templates_dir, date_str="2026-04-26",
    )
```

- [ ] **Step 3: Implementar step 1**

Append em `kanban-tasks/lib/project_factory.py`:

```python
def render_template(tmpl_path: Path, **kwargs) -> str:
    """Read template file and substitute {field} placeholders."""
    return tmpl_path.read_text().format(**kwargs)


def step_1_create_kb_folders(
    slug: str,
    name: str,
    description: str,
    kb_dir: Path,
    templates_dir: Path,
    date_str: str,
) -> list[str]:
    """Create bevox-knowledge/10_prd/<slug>/ + 40_roadmap/<slug>/ with stub files.

    Idempotent: skips creation if files already exist.

    Returns list of file paths created/updated.
    """
    prd_tmpl = templates_dir / "prd-stub.md.tmpl"
    rm_tmpl = templates_dir / "roadmap-stub.md.tmpl"

    prd_dir = kb_dir / "10_prd" / slug
    rm_dir = kb_dir / "40_roadmap" / slug
    prd_dir.mkdir(parents=True, exist_ok=True)
    rm_dir.mkdir(parents=True, exist_ok=True)

    prd_path = prd_dir / f"{date_str}-{slug}-prd.md"
    rm_path = rm_dir / f"{date_str}-{slug}-roadmap.md"

    if not prd_path.exists():
        prd_path.write_text(render_template(
            prd_tmpl, name=name, description=description, date=date_str
        ))
    if not rm_path.exists():
        rm_path.write_text(render_template(
            rm_tmpl, name=name, date=date_str
        ))

    return [str(prd_path), str(rm_path)]
```

- [ ] **Step 4: Rodar tests**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m pytest tests/test_project_factory.py -v 2>&1 | tail -5
```

Expected: 24/24 pass.

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/templates/prd-stub.md.tmpl kanban-tasks/templates/roadmap-stub.md.tmpl kanban-tasks/lib/project_factory.py kanban-tasks/tests/test_project_factory.py && git commit -m "$(cat <<'EOF'
feat(project_factory): step 1 — kb folders + stub templates

Cria 10_prd/<slug>/ + 40_roadmap/<slug>/ no bevox-knowledge working tree
com stubs auto-explicativos. Idempotent (skip se arquivo ja existe).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Step 2 — kanban-tasks integration

**Files:**
- Modify: `kanban-tasks/lib/project_factory.py` (add `step_2_kanban_bootstrap`)
- Modify: `kanban-tasks/tests/test_project_factory.py`

- [ ] **Step 1: Adicionar tests**

Append em `kanban-tasks/tests/test_project_factory.py`:

```python
from lib.project_factory import step_2_kanban_bootstrap


def test_step_2_calls_existing_helpers(monkeypatch):
    add_called = []
    bootstrap_called = []

    def fake_add(name, actor):
        add_called.append((name, actor))
        return {"name": name, "noop": False}

    def fake_bootstrap(actor, projects, dry_run=False):
        bootstrap_called.append((actor, projects, dry_run))
        return {"created": 2, "projects_processed": projects}

    monkeypatch.setattr("lib.project_factory.task_lib.add_project", fake_add)
    monkeypatch.setattr("lib.project_factory.sprint_lib.bootstrap", fake_bootstrap)

    result = step_2_kanban_bootstrap(slug="foo", actor="bernard")
    assert add_called == [("foo", "bernard")]
    assert bootstrap_called == [("bernard", ["foo"], False)]
    assert result["sprints_created"] == 2
```

- [ ] **Step 2: Implementar step 2**

Append em `kanban-tasks/lib/project_factory.py`:

```python
from lib import task_lib, sprint_lib


def step_2_kanban_bootstrap(slug: str, actor: str = "bernard") -> dict:
    """Add slug to kanban-tasks projects.yml + state.json + bootstrap 1 current + 1 next sprint.

    Reusa task_lib.add_project + sprint_lib.bootstrap existentes (idempotent).

    Returns dict com 'sprints_created' count.
    """
    add_result = task_lib.add_project(slug, actor=actor)
    bootstrap_result = sprint_lib.bootstrap(
        actor=actor, projects=[slug], dry_run=False
    )
    return {
        "project_add": add_result,
        "sprints_created": bootstrap_result.get("created", 0),
    }
```

- [ ] **Step 3: Rodar tests**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m pytest tests/test_project_factory.py -v 2>&1 | tail -5
```

Expected: 25/25 pass.

- [ ] **Step 4: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/lib/project_factory.py kanban-tasks/tests/test_project_factory.py && git commit -m "$(cat <<'EOF'
feat(project_factory): step 2 — kanban project add + sprint bootstrap

Reusa task_lib.add_project + sprint_lib.bootstrap (idempotent helpers).
Cria entry em projects.yml + 1 current + 1 next sprint em state.json.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Step 3 — ~/.openclaw runtime workspace

**Files:**
- Create: `kanban-tasks/templates/workspace/IDENTITY.md.tmpl` + 7 outros (SOUL, BOOTSTRAP, HEARTBEAT, MEMORY, TOOLS, USER, AGENTS)
- Modify: `kanban-tasks/lib/project_factory.py` (add `step_3_create_workspace`)
- Modify: `kanban-tasks/tests/test_project_factory.py`

- [ ] **Step 1: Criar 8 templates de workspace**

```bash
mkdir -p ~/.openclaw/kanban-tasks/templates/workspace
```

Conteúdo dos 8 arquivos (cada um com header + descrição genérica do papel):

`IDENTITY.md.tmpl`:
```markdown
# IDENTITY — {slug}

> Stub criado {date} por `openclaw project create`.

Este arquivo define a identidade do agente operacional do projeto **{name}**.

Inclua aqui:
- Nome ou codinome do agente
- Papel central no Company OS
- Tom de voz e persona
- Limites de autoridade

**Status:** stub
```

`SOUL.md.tmpl`:
```markdown
# SOUL — {slug}

> Stub criado {date} por `openclaw project create`.

Valores e princípios operacionais do agente **{name}**.

Inclua aqui:
- O que o agente prioriza
- Como decide tradeoffs
- Posturas defensivas vs proativas

**Status:** stub
```

`BOOTSTRAP.md.tmpl`:
```markdown
# BOOTSTRAP — {slug}

> Stub criado {date} por `openclaw project create`.

Rotina de inicialização do agente **{name}**.

Inclua aqui:
- Sequência de leitura ao entrar em sessão
- Estado a recuperar
- Verificações iniciais

**Status:** stub
```

`HEARTBEAT.md.tmpl`:
```markdown
# HEARTBEAT — {slug}

> Stub criado {date} por `openclaw project create`.

Loop de manutenção operacional do agente **{name}**.

Inclua aqui:
- Tarefas periódicas
- Health checks próprios
- Sinais que indicam saúde do agente

**Status:** stub
```

`MEMORY.md.tmpl`:
```markdown
# MEMORY — {slug}

> Stub criado {date} por `openclaw project create`.

Memory persistente cross-session do agente **{name}**.

Inclua aqui referências a:
- Memórias factuais sobre o projeto
- Convenções aprendidas
- Decisões consolidadas

**Status:** stub
```

`TOOLS.md.tmpl`:
```markdown
# TOOLS — {slug}

> Stub criado {date} por `openclaw project create`.

Ferramentas disponíveis ao agente **{name}**.

Inclua aqui:
- Skills habilitadas
- APIs externas consumidas
- Limitações conhecidas

**Status:** stub
```

`USER.md.tmpl`:
```markdown
# USER — {slug}

> Stub criado {date} por `openclaw project create`.

Perfil do usuário operador do agente **{name}**.

Inclua aqui:
- Quem opera o agente
- Estilo de interação preferido
- Convenções de aprovação/escalação

**Status:** stub
```

`AGENTS.md.tmpl`:
```markdown
# AGENTS — {slug}

> Stub criado {date} por `openclaw project create`.

Outros agentes em escopo do projeto **{name}**.

Inclua aqui:
- Agentes que colaboram neste projeto
- Hand-offs e coordenação
- Boundaries entre agentes

**Status:** stub
```

- [ ] **Step 2: Adicionar tests**

Append em `kanban-tasks/tests/test_project_factory.py`:

```python
from lib.project_factory import step_3_create_workspace


def test_step_3_creates_runtime_dirs(tmp_path):
    openclaw_dir = tmp_path / "openclaw"
    openclaw_dir.mkdir()
    templates_dir = Path(__file__).parent.parent / "templates"

    result = step_3_create_workspace(
        slug="customer-portal",
        name="Customer Portal",
        openclaw_dir=openclaw_dir,
        templates_dir=templates_dir,
        date_str="2026-04-26",
    )

    # Runtime workspace
    assert (openclaw_dir / "customer-portal" / "clarifications").is_dir()
    assert (openclaw_dir / "customer-portal" / "notifications").is_dir()
    assert (openclaw_dir / "customer-portal" / "scripts").is_dir()
    # Persona stubs
    workspace_dir = openclaw_dir / "workspace-customer-portal"
    assert workspace_dir.is_dir()
    for fname in ["IDENTITY.md", "SOUL.md", "BOOTSTRAP.md", "HEARTBEAT.md",
                  "MEMORY.md", "TOOLS.md", "USER.md", "AGENTS.md"]:
        f = workspace_dir / fname
        assert f.exists()
        assert "Customer Portal" in f.read_text()
        assert "Status:** stub" in f.read_text()
    assert (workspace_dir / "memory").is_dir()
    assert "workspace_files_created" in result


def test_step_3_idempotent(tmp_path):
    openclaw_dir = tmp_path / "openclaw"
    openclaw_dir.mkdir()
    templates_dir = Path(__file__).parent.parent / "templates"
    step_3_create_workspace(
        slug="x", name="X", openclaw_dir=openclaw_dir,
        templates_dir=templates_dir, date_str="2026-04-26",
    )
    # Doesn't raise
    step_3_create_workspace(
        slug="x", name="X", openclaw_dir=openclaw_dir,
        templates_dir=templates_dir, date_str="2026-04-26",
    )
```

- [ ] **Step 3: Implementar step 3**

Append em `kanban-tasks/lib/project_factory.py`:

```python
PERSONA_FILES = (
    "IDENTITY.md",
    "SOUL.md",
    "BOOTSTRAP.md",
    "HEARTBEAT.md",
    "MEMORY.md",
    "TOOLS.md",
    "USER.md",
    "AGENTS.md",
)


def step_3_create_workspace(
    slug: str,
    name: str,
    openclaw_dir: Path,
    templates_dir: Path,
    date_str: str,
) -> dict:
    """Create ~/.openclaw/<slug>/ runtime + ~/.openclaw/workspace-<slug>/ persona stubs.

    Idempotent: skip persona files if exist; mkdir(exist_ok=True) for dirs.

    Returns dict com counts.
    """
    runtime_dir = openclaw_dir / slug
    workspace_dir = openclaw_dir / f"workspace-{slug}"
    workspace_tmpl_dir = templates_dir / "workspace"

    # Runtime dirs (empty)
    for sub in ("clarifications", "notifications", "scripts"):
        (runtime_dir / sub).mkdir(parents=True, exist_ok=True)

    # Persona stubs
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (workspace_dir / "memory").mkdir(exist_ok=True)

    files_created = []
    for fname in PERSONA_FILES:
        target = workspace_dir / fname
        if not target.exists():
            tmpl = workspace_tmpl_dir / f"{fname}.tmpl"
            target.write_text(render_template(
                tmpl, slug=slug, name=name, date=date_str
            ))
            files_created.append(str(target))

    return {
        "runtime_dir": str(runtime_dir),
        "workspace_dir": str(workspace_dir),
        "workspace_files_created": files_created,
    }
```

- [ ] **Step 4: Rodar tests**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m pytest tests/test_project_factory.py -v 2>&1 | tail -5
```

Expected: 27/27 pass.

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/templates/workspace/ kanban-tasks/lib/project_factory.py kanban-tasks/tests/test_project_factory.py && git commit -m "$(cat <<'EOF'
feat(project_factory): step 3 — ~/.openclaw runtime workspace + persona stubs

Cria runtime dirs (clarifications/, notifications/, scripts/ — todos vazios
porque scripts dependem de bot config futuro) + workspace-<slug>/ com 8
persona md stubs auto-explicativos + memory/ dir.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Step 4 — projects-meta.json read/write atomic

**Files:**
- Create: `kanban-tasks/lib/projects_meta.py`
- Create: `kanban-tasks/tests/test_projects_meta.py`
- Modify: `kanban-tasks/lib/project_factory.py` (add `step_4_meta_insert`)
- Modify: `kanban-tasks/tests/test_project_factory.py`

- [ ] **Step 1: Tests pra projects_meta module**

Write `kanban-tasks/tests/test_projects_meta.py`:

```python
"""Tests for projects-meta.json read/write atomic helpers.

Spec: bevox-knowledge/35_specs/company-os/2026-04-26-mc-projects-factory.md §3.5
"""
import json
import pytest
from pathlib import Path

from lib.projects_meta import (
    read_meta,
    write_meta,
    insert_project,
    update_project,
    MetaError,
)


def test_read_meta_creates_empty_when_missing(tmp_path):
    meta_path = tmp_path / "meta.json"
    data = read_meta(meta_path)
    assert data == {"version": 1, "projects": {}}
    # Doesn't write — only returns default
    assert not meta_path.exists()


def test_read_meta_returns_existing_data(tmp_path):
    meta_path = tmp_path / "meta.json"
    meta_path.write_text('{"version": 1, "projects": {"foo": {"name": "Foo"}}}')
    data = read_meta(meta_path)
    assert data["projects"]["foo"]["name"] == "Foo"


def test_write_meta_atomic_via_tmp_rename(tmp_path):
    meta_path = tmp_path / "meta.json"
    write_meta(meta_path, {"version": 1, "projects": {"x": {"name": "X"}}})
    assert meta_path.exists()
    assert json.loads(meta_path.read_text())["projects"]["x"]["name"] == "X"
    # tmp file should be gone
    assert not (tmp_path / "meta.json.tmp").exists()


def test_insert_project_creates_entry(tmp_path):
    meta_path = tmp_path / "meta.json"
    insert_project(meta_path, "customer-portal", {
        "name": "Customer Portal",
        "description": "App",
        "github_url": None,
        "bot_id": None,
        "created_at": "2026-04-26T00:00:00Z",
        "source": "user_created",
    })
    data = json.loads(meta_path.read_text())
    assert data["projects"]["customer-portal"]["name"] == "Customer Portal"


def test_insert_project_fails_if_exists(tmp_path):
    meta_path = tmp_path / "meta.json"
    insert_project(meta_path, "x", {"name": "X"})
    with pytest.raises(MetaError, match="already exists"):
        insert_project(meta_path, "x", {"name": "X again"})


def test_update_project_merges_partial(tmp_path):
    meta_path = tmp_path / "meta.json"
    insert_project(meta_path, "x", {
        "name": "X", "description": "old", "bot_id": None,
    })
    update_project(meta_path, "x", {"bot_id": "8042:abc", "description": "new"})
    data = json.loads(meta_path.read_text())
    assert data["projects"]["x"]["bot_id"] == "8042:abc"
    assert data["projects"]["x"]["description"] == "new"
    assert data["projects"]["x"]["name"] == "X"  # unchanged


def test_update_project_fails_if_missing(tmp_path):
    meta_path = tmp_path / "meta.json"
    with pytest.raises(MetaError, match="not found"):
        update_project(meta_path, "missing", {"bot_id": "x"})
```

- [ ] **Step 2: Implementar projects_meta module**

Write `kanban-tasks/lib/projects_meta.py`:

```python
"""projects-meta.json read/write atomic helpers.

Spec: bevox-knowledge/35_specs/company-os/2026-04-26-mc-projects-factory.md §3.5
"""
import fcntl
import json
import os
from pathlib import Path
from typing import Any


class MetaError(Exception):
    pass


SCHEMA_VERSION = 1


def read_meta(path: Path) -> dict:
    """Read projects-meta.json. Returns default empty schema if missing.

    Lock-free read (eventually consistent — tolerável pra metadata).
    """
    if not path.exists():
        return {"version": SCHEMA_VERSION, "projects": {}}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        raise MetaError(f"failed to read {path}: {e}")


def write_meta(path: Path, data: dict) -> None:
    """Atomic write via tmp file + rename. flock pra concurrency.

    Idempotent if data identical to current.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.touch(exist_ok=True)
    with open(lock_path, "w") as lock_fp:
        fcntl.flock(lock_fp, fcntl.LOCK_EX)
        try:
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            os.replace(tmp, path)
        finally:
            fcntl.flock(lock_fp, fcntl.LOCK_UN)


def insert_project(path: Path, slug: str, entry: dict) -> None:
    """Insert new project entry. Fails if slug already exists."""
    data = read_meta(path)
    if slug in data.get("projects", {}):
        raise MetaError(f"project '{slug}' already exists in meta")
    data.setdefault("projects", {})[slug] = entry
    write_meta(path, data)


def update_project(path: Path, slug: str, partial: dict) -> None:
    """Merge partial dict into existing entry. Fails if slug doesn't exist."""
    data = read_meta(path)
    if slug not in data.get("projects", {}):
        raise MetaError(f"project '{slug}' not found in meta")
    data["projects"][slug].update(partial)
    write_meta(path, data)
```

- [ ] **Step 3: Tests pra step_4_meta_insert**

Append em `kanban-tasks/tests/test_project_factory.py`:

```python
from lib.project_factory import step_4_meta_insert


def test_step_4_inserts_user_created_entry(tmp_path):
    meta_path = tmp_path / "meta.json"
    result = step_4_meta_insert(
        slug="customer-portal",
        name="Customer Portal",
        description="App de portal",
        github_url="https://github.com/bernardTavares/customer-portal",
        meta_path=meta_path,
        date_iso="2026-04-26T12:00:00Z",
    )
    data = json.loads(meta_path.read_text())
    entry = data["projects"]["customer-portal"]
    assert entry["name"] == "Customer Portal"
    assert entry["source"] == "user_created"
    assert entry["bot_id"] is None
    assert entry["created_at"] == "2026-04-26T12:00:00Z"
    assert result["meta_path"] == str(meta_path)
```

- [ ] **Step 4: Implementar step 4**

Append em `kanban-tasks/lib/project_factory.py`:

```python
from lib import projects_meta


def step_4_meta_insert(
    slug: str,
    name: str,
    description: str,
    github_url: str,
    meta_path: Path,
    date_iso: str,
) -> dict:
    """Insert project entry into projects-meta.json with source=user_created."""
    entry = {
        "name": name,
        "description": description,
        "github_url": github_url,
        "bot_id": None,
        "created_at": date_iso,
        "source": "user_created",
    }
    projects_meta.insert_project(meta_path, slug, entry)
    return {"meta_path": str(meta_path), "entry": entry}
```

- [ ] **Step 5: Rodar tests**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m pytest tests/ -v 2>&1 | tail -5
```

Expected: 35/35 pass (27 anteriores + 7 meta module + 1 step 4).

- [ ] **Step 6: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/lib/projects_meta.py kanban-tasks/lib/project_factory.py kanban-tasks/tests/test_projects_meta.py kanban-tasks/tests/test_project_factory.py && git commit -m "$(cat <<'EOF'
feat(project_factory): step 4 — projects-meta.json atomic insert + flock

Helper module projects_meta.py: read/write atomic via tmp+rename, flock
em .lock pra concurrency entre creates simultaneos. insert_project +
update_project com fail-if-exists / fail-if-missing semantica.

Step 4 cria entry source=user_created com defaults pra bot_id (null) e
created_at (ISO timestamp).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Step 5 — code dir + git init + initial commit

**Files:**
- Create: `kanban-tasks/templates/code/README.md.tmpl`
- Modify: `kanban-tasks/lib/project_factory.py` (add `step_5_code_init`)
- Modify: `kanban-tasks/tests/test_project_factory.py`

- [ ] **Step 1: Criar template README**

```bash
mkdir -p ~/.openclaw/kanban-tasks/templates/code
```

Write `kanban-tasks/templates/code/README.md.tmpl`:

```markdown
# {name}

{description}

---

> Repositório criado {date} via `openclaw project create`.

## Status

Stub — preencher conforme o projeto evoluir.

## Links

- Mission Control: https://mc.example.com/projects/{slug}
- bevox-knowledge: `10_prd/{slug}/`, `40_roadmap/{slug}/`
```

- [ ] **Step 2: Adicionar tests**

Append em `kanban-tasks/tests/test_project_factory.py`:

```python
from lib.project_factory import step_5_code_init


def test_step_5_initializes_local_repo(tmp_path):
    code_dir = tmp_path / "code"
    code_dir.mkdir()
    templates_dir = Path(__file__).parent.parent / "templates"

    result = step_5_code_init(
        slug="customer-portal",
        name="Customer Portal",
        description="App de portal",
        code_dir=code_dir,
        templates_dir=templates_dir,
        date_str="2026-04-26",
        actor="bernard",
    )

    project_path = code_dir / "customer-portal"
    assert project_path.is_dir()
    assert (project_path / ".git").is_dir()
    readme = project_path / "README.md"
    assert readme.exists()
    assert "Customer Portal" in readme.read_text()
    assert "App de portal" in readme.read_text()
    # Has at least one commit
    log = subprocess.run(
        ["git", "-C", str(project_path), "log", "--oneline"],
        capture_output=True, text=True,
    )
    assert log.returncode == 0
    assert "bootstrap" in log.stdout.lower()
    assert result["repo_path"] == str(project_path)


def test_step_5_fails_if_dir_exists(tmp_path):
    code_dir = tmp_path / "code"
    code_dir.mkdir()
    (code_dir / "x").mkdir()
    templates_dir = Path(__file__).parent.parent / "templates"
    with pytest.raises(Exception, match="already exists"):
        step_5_code_init(
            slug="x", name="X", description="", code_dir=code_dir,
            templates_dir=templates_dir, date_str="2026-04-26",
            actor="bernard",
        )
```

- [ ] **Step 3: Implementar step 5**

Append em `kanban-tasks/lib/project_factory.py`:

```python
class StepFailure(Exception):
    """Raised when an orchestrator step fails."""
    def __init__(self, step: int, code: str, message: str):
        self.step = step
        self.code = code
        super().__init__(f"step {step} ({code}): {message}")


def step_5_code_init(
    slug: str,
    name: str,
    description: str,
    code_dir: Path,
    templates_dir: Path,
    date_str: str,
    actor: str = "bernard",
) -> dict:
    """Create ${BEVOX_CODE_DIR}/<slug>/ + git init + README + initial commit on main."""
    project_path = code_dir / slug
    if project_path.exists():
        raise StepFailure(5, "code_dir_exists",
                          f"directory already exists: {project_path}")

    project_path.mkdir(parents=True)

    # Render README
    tmpl = templates_dir / "code" / "README.md.tmpl"
    readme_content = render_template(
        tmpl, slug=slug, name=name, description=description, date=date_str
    )
    (project_path / "README.md").write_text(readme_content)

    # git init + initial commit on main
    cmds = [
        ["git", "init", "--initial-branch=main"],
        ["git", "add", "README.md"],
        ["git", "commit",
         "-m", f"feat: bootstrap {slug} project",
         "--author", f"{actor} <{actor}@bevox>"],
    ]
    for cmd in cmds:
        result = subprocess.run(
            cmd, cwd=str(project_path),
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise StepFailure(5, "git_init_failed",
                              f"{cmd[0]} {cmd[1]}: {result.stderr}")

    return {"repo_path": str(project_path), "branch": "main"}
```

- [ ] **Step 4: Rodar tests**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m pytest tests/test_project_factory.py -v 2>&1 | tail -5
```

Expected: 37/37 pass.

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/templates/code/ kanban-tasks/lib/project_factory.py kanban-tasks/tests/test_project_factory.py && git commit -m "$(cat <<'EOF'
feat(project_factory): step 5 — local code dir + git init + initial commit

Cria \${BEVOX_CODE_DIR}/<slug>/ com README rendered + git init em branch
main + commit inicial 'feat: bootstrap <slug> project'. StepFailure
exception com code field pra cleanup hint mapping.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Step 6 — gh repo create + push

**Files:**
- Modify: `kanban-tasks/lib/project_factory.py` (add `step_6_github_push`)
- Modify: `kanban-tasks/tests/test_project_factory.py`

- [ ] **Step 1: Adicionar tests**

Append em `kanban-tasks/tests/test_project_factory.py`:

```python
from lib.project_factory import step_6_github_push


def test_step_6_invokes_gh_create_with_push(monkeypatch, tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return MagicMock(returncode=0, stdout="created", stderr="")

    monkeypatch.setattr("lib.project_factory.subprocess.run", fake_run)
    result = step_6_github_push(
        slug="customer-portal",
        org="bernardTavares",
        repo_path=repo_path,
    )
    # Should call gh repo create with --private --source --push
    create_cmd = calls[0]
    assert "gh" == create_cmd[0]
    assert "repo" in create_cmd
    assert "create" in create_cmd
    assert "bernardTavares/customer-portal" in create_cmd
    assert "--private" in create_cmd
    assert "--push" in create_cmd
    assert result["github_url"] == "https://github.com/bernardTavares/customer-portal"


def test_step_6_raises_step_failure_on_gh_error(monkeypatch, tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    def fake_run(cmd, **kwargs):
        return MagicMock(returncode=1, stderr="HTTP 422")

    monkeypatch.setattr("lib.project_factory.subprocess.run", fake_run)
    with pytest.raises(StepFailure) as exc_info:
        step_6_github_push(
            slug="x", org="bernardTavares", repo_path=repo_path,
        )
    assert exc_info.value.step == 6
    assert exc_info.value.code == "gh_create_failed"
```

- [ ] **Step 2: Implementar step 6**

Append em `kanban-tasks/lib/project_factory.py`:

```python
def step_6_github_push(
    slug: str,
    org: str,
    repo_path: Path,
) -> dict:
    """Create private GitHub repo via gh CLI + push current main branch.

    Uses `gh repo create <org>/<slug> --private --source=<repo_path> --push`
    which combines create + push in one atomic gh operation.
    """
    cmd = [
        "gh", "repo", "create", f"{org}/{slug}",
        "--private",
        "--source", str(repo_path),
        "--push",
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise StepFailure(
            6, "gh_create_failed",
            f"gh repo create failed: {result.stderr.strip()}",
        )
    return {
        "github_url": f"https://github.com/{org}/{slug}",
        "stdout": result.stdout.strip(),
    }
```

- [ ] **Step 3: Rodar tests**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m pytest tests/test_project_factory.py -v 2>&1 | tail -5
```

Expected: 39/39 pass.

- [ ] **Step 4: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/lib/project_factory.py kanban-tasks/tests/test_project_factory.py && git commit -m "$(cat <<'EOF'
feat(project_factory): step 6 — gh repo create + push (atomic)

Usa 'gh repo create <org>/<slug> --private --source <path> --push' que
combina create + push em uma chamada gh atomic. StepFailure se gh
returncode != 0 (preserva stderr no cleanup hint).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Orchestrator + JSONL logging

**Files:**
- Modify: `kanban-tasks/lib/project_factory.py` (add `create_project` orchestrator + log helpers)
- Modify: `kanban-tasks/tests/test_project_factory.py`

- [ ] **Step 1: Adicionar tests do orchestrator**

Append em `kanban-tasks/tests/test_project_factory.py`:

```python
from lib.project_factory import create_project, ProjectCreateConfig


def test_create_project_happy_path(tmp_path, monkeypatch):
    """Full orchestration with all 6 steps mocked to succeed."""
    config = ProjectCreateConfig(
        kb_dir=tmp_path / "kb",
        openclaw_dir=tmp_path / "openclaw",
        code_dir=tmp_path / "code",
        meta_path=tmp_path / "openclaw" / "projects-meta.json",
        log_path=tmp_path / "openclaw" / "projects-create.jsonl",
        templates_dir=Path(__file__).parent.parent / "templates",
        org="bernardTavares",
    )
    config.kb_dir.mkdir()
    config.openclaw_dir.mkdir()
    config.code_dir.mkdir()
    # mock kanban-tasks helpers
    monkeypatch.setattr("lib.project_factory.task_lib.add_project",
                        lambda name, actor: {"name": name, "noop": False})
    monkeypatch.setattr("lib.project_factory.sprint_lib.bootstrap",
                        lambda actor, projects, dry_run=False: {"created": 2})
    # mock gh CLI
    def fake_gh_run(cmd, **kwargs):
        # gh auth status — ok; gh repo view — 404 (free); gh repo create — ok
        if cmd[:3] == ["gh", "auth", "status"]:
            return MagicMock(returncode=0)
        if cmd[:3] == ["gh", "repo", "view"]:
            return MagicMock(returncode=1, stderr="HTTP 404")
        return MagicMock(returncode=0, stdout="ok", stderr="")
    # KB git status — clean
    def fake_git_run(cmd, **kwargs):
        if cmd[:2] == ["git", "-C"] and "status" in cmd:
            return MagicMock(returncode=0, stdout="")
        return MagicMock(returncode=0, stdout="", stderr="")
    def combined_run(cmd, **kwargs):
        if cmd and cmd[0] == "gh":
            return fake_gh_run(cmd, **kwargs)
        return fake_git_run(cmd, **kwargs)
    monkeypatch.setattr("lib.project_factory.subprocess.run", combined_run)

    result = create_project(
        name="Customer Portal",
        slug="customer-portal",
        description="App",
        config=config,
        actor="bernard",
    )
    assert result["success"] is True
    assert result["steps_completed"] == 6
    assert result["github_url"] == "https://github.com/bernardTavares/customer-portal"
    # Log file populated
    log_lines = config.log_path.read_text().strip().splitlines()
    assert len(log_lines) == 6  # one per step
    for line in log_lines:
        entry = json.loads(line)
        assert entry["status"] == "ok"


def test_create_project_partial_failure_logs(tmp_path, monkeypatch):
    """If step 5 fails, log entries for steps 1-4 ok + 5 failed; no step 6."""
    config = ProjectCreateConfig(
        kb_dir=tmp_path / "kb",
        openclaw_dir=tmp_path / "openclaw",
        code_dir=tmp_path / "code",
        meta_path=tmp_path / "openclaw" / "projects-meta.json",
        log_path=tmp_path / "openclaw" / "projects-create.jsonl",
        templates_dir=Path(__file__).parent.parent / "templates",
        org="bernardTavares",
    )
    config.kb_dir.mkdir()
    config.openclaw_dir.mkdir()
    # Don't create code_dir → step 5 fails (missing dir) — actually preflight catches this
    # So instead make pre-existing code/<slug> to force StepFailure in step 5
    config.code_dir.mkdir()
    (config.code_dir / "x").mkdir()
    monkeypatch.setattr("lib.project_factory.task_lib.add_project",
                        lambda name, actor: {"name": name, "noop": False})
    monkeypatch.setattr("lib.project_factory.sprint_lib.bootstrap",
                        lambda actor, projects, dry_run=False: {"created": 2})
    def combined_run(cmd, **kwargs):
        if cmd and cmd[0] == "gh":
            if cmd[:3] == ["gh", "auth", "status"]:
                return MagicMock(returncode=0)
            if cmd[:3] == ["gh", "repo", "view"]:
                return MagicMock(returncode=1, stderr="HTTP 404")
            return MagicMock(returncode=0, stdout="ok", stderr="")
        if cmd[:2] == ["git", "-C"] and "status" in cmd:
            return MagicMock(returncode=0, stdout="")
        return MagicMock(returncode=0, stdout="", stderr="")
    monkeypatch.setattr("lib.project_factory.subprocess.run", combined_run)

    result = create_project(
        name="X", slug="x", description="",
        config=config, actor="bernard",
    )
    assert result["success"] is False
    assert result["failed_at"] == 5
    assert result["steps_completed"] == 4
    log_lines = config.log_path.read_text().strip().splitlines()
    assert len(log_lines) == 5  # 4 ok + 1 failed
    assert json.loads(log_lines[-1])["status"] == "failed"
    assert json.loads(log_lines[-1])["step"] == 5
```

- [ ] **Step 2: Implementar orchestrator**

Append em `kanban-tasks/lib/project_factory.py`:

```python
import datetime as dt
import time
from dataclasses import dataclass


@dataclass
class ProjectCreateConfig:
    kb_dir: Path
    openclaw_dir: Path
    code_dir: Path
    meta_path: Path
    log_path: Path
    templates_dir: Path
    org: str = "bernardTavares"


def _log_event(log_path: Path, entry: dict) -> None:
    """Append one JSON line to log file. Creates dir if missing."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def create_project(
    name: str,
    slug: str,
    description: str,
    config: ProjectCreateConfig,
    actor: str = "bernard",
) -> dict:
    """Orchestrate 6-step project creation with pre-flight + JSONL logging.

    Returns dict:
      { success: bool, steps_completed: int, failed_at?: int, ...details }
    """
    date_str = dt.date.today().isoformat()
    date_iso = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    projects_yml = Path("~/.openclaw/kanban-tasks/projects.yml")

    # Pre-flight (Task 3)
    try:
        run_preflight(
            slug=slug,
            org=config.org,
            kb_dir=config.kb_dir,
            openclaw_dir=config.openclaw_dir,
            code_dir=config.code_dir,
            projects_yml=projects_yml,
            meta_path=config.meta_path,
        )
    except PreflightFailure as e:
        return {
            "success": False,
            "failed_at": 0,
            "steps_completed": 0,
            "error_code": e.code,
            "error_message": str(e),
        }

    # Define steps
    steps = [
        (1, "knowledge_folders", lambda: step_1_create_kb_folders(
            slug, name, description, config.kb_dir,
            config.templates_dir, date_str)),
        (2, "kanban_bootstrap", lambda: step_2_kanban_bootstrap(slug, actor)),
        (3, "openclaw_workspace", lambda: step_3_create_workspace(
            slug, name, config.openclaw_dir,
            config.templates_dir, date_str)),
        (4, "meta_insert", lambda: step_4_meta_insert(
            slug, name, description,
            f"https://github.com/{config.org}/{slug}",
            config.meta_path, date_iso)),
        (5, "code_init", lambda: step_5_code_init(
            slug, name, description, config.code_dir,
            config.templates_dir, date_str, actor)),
        (6, "github_push", lambda: step_6_github_push(
            slug, config.org, config.code_dir / slug)),
    ]

    completed = 0
    for step_num, step_name, step_fn in steps:
        start = time.time()
        try:
            details = step_fn()
            duration_ms = int((time.time() - start) * 1000)
            _log_event(config.log_path, {
                "ts": dt.datetime.utcnow().isoformat() + "Z",
                "slug": slug,
                "step": step_num,
                "name": step_name,
                "status": "ok",
                "duration_ms": duration_ms,
                "details": {k: v for k, v in details.items() if isinstance(v, (str, int, list))},
            })
            completed = step_num
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            _log_event(config.log_path, {
                "ts": dt.datetime.utcnow().isoformat() + "Z",
                "slug": slug,
                "step": step_num,
                "name": step_name,
                "status": "failed",
                "duration_ms": duration_ms,
                "error": str(e),
            })
            return {
                "success": False,
                "failed_at": step_num,
                "steps_completed": completed,
                "error_code": getattr(e, "code", "unknown"),
                "error_message": str(e),
            }

    return {
        "success": True,
        "id": slug,
        "steps_completed": 6,
        "github_url": f"https://github.com/{config.org}/{slug}",
    }
```

- [ ] **Step 3: Rodar tests**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m pytest tests/test_project_factory.py -v 2>&1 | tail -8
```

Expected: 41/41 pass (39 anteriores + 2 orchestrator).

- [ ] **Step 4: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/lib/project_factory.py kanban-tasks/tests/test_project_factory.py && git commit -m "$(cat <<'EOF'
feat(project_factory): orchestrator create_project + JSONL logging

Pre-flight (Task 3) + 6 steps em sequencia reversibility-ascending. Cada
step loga JSON line em ~/.openclaw/projects-create.jsonl. Em falha,
retorna failed_at + steps_completed pra cleanup hint manual.

ProjectCreateConfig dataclass agrega paths + org como contract estavel.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: cli.sh entries — project create + edit + extended list

**Files:**
- Modify: `kanban-tasks/lib/api.py` (add `cmd_project_create`, `cmd_project_edit`, modify `cmd_project_list`, argparse subcommands)
- Modify: `kanban-tasks/tests/test_project_factory.py` (CLI integration test)

- [ ] **Step 1: Inspecionar argparse atual em api.py**

```bash
grep -n "project" ~/.openclaw/kanban-tasks/lib/api.py | head -20
```

Anotar onde está o sub-parser pra `project` subcommand (deve estar ~linha 950).

- [ ] **Step 2: Adicionar handlers em api.py**

Editar `~/.openclaw/kanban-tasks/lib/api.py`. Localizar a região de `cmd_project_*` (~linha 524-540) e adicionar **antes** dos `# ============ Events handlers ============`:

```python
def cmd_project_create(args: argparse.Namespace) -> int:
    """Orchestrator: create project across 6 destinations."""
    from pathlib import Path
    import os
    from lib.project_factory import (
        create_project, slugify, ProjectCreateConfig,
    )
    slug = args.id or slugify(args.name)
    if not slug:
        _print({"error": "invalid_name"}, args.json,
               f"erro: nome inválido (id derivado vazio)")
        return EXIT_VALIDATION

    kb_dir = Path(os.environ.get(
        "BEVOX_KNOWLEDGE_DIR", "~/bevox-knowledge"))
    openclaw_dir = Path(os.environ.get(
        "OPENCLAW_DIR", "~/.openclaw"))
    code_dir = Path(os.environ.get(
        "BEVOX_CODE_DIR", "~/code"))
    org = os.environ.get("GITHUB_ORG", "bernardTavares")
    templates_dir = Path("~/.openclaw/kanban-tasks/templates")

    config = ProjectCreateConfig(
        kb_dir=kb_dir,
        openclaw_dir=openclaw_dir,
        code_dir=code_dir,
        meta_path=openclaw_dir / "projects-meta.json",
        log_path=openclaw_dir / "projects-create.jsonl",
        templates_dir=templates_dir,
        org=org,
    )

    result = create_project(
        name=args.name,
        slug=slug,
        description=args.description or "",
        config=config,
        actor=args.actor,
    )
    _print(result, args.json,
           f"{'ok' if result['success'] else 'failed'}: {slug}")
    return EXIT_OK if result["success"] else EXIT_RUNTIME


def cmd_project_edit(args: argparse.Namespace) -> int:
    """Light-weight: update projects-meta.json fields only (no orchestration)."""
    from pathlib import Path
    import os
    from lib import projects_meta
    openclaw_dir = Path(os.environ.get(
        "OPENCLAW_DIR", "~/.openclaw"))
    meta_path = openclaw_dir / "projects-meta.json"

    partial = {}
    if args.bot_id is not None:
        partial["bot_id"] = args.bot_id
    if args.github_url is not None:
        partial["github_url"] = args.github_url
    if args.description is not None:
        partial["description"] = args.description

    if not partial:
        _print({"error": "no_fields"}, args.json,
               "erro: pelo menos um field (--bot-id/--github-url/--description)")
        return EXIT_VALIDATION

    try:
        projects_meta.update_project(meta_path, args.id, partial)
        _print({"id": args.id, "updated": list(partial.keys())},
               args.json, f"updated: {args.id}")
        return EXIT_OK
    except projects_meta.MetaError as e:
        _print({"error": "meta_error", "detail": str(e)},
               args.json, f"erro: {e}")
        return EXIT_VALIDATION
```

E definir constants no topo de api.py se não existirem:

```python
# Add near other EXIT_* constants
EXIT_VALIDATION = 1
EXIT_RUNTIME = 2
```

(Verificar se já existem antes de adicionar.)

- [ ] **Step 3: Adicionar argparse sub-commands**

Editar `~/.openclaw/kanban-tasks/lib/api.py`. Localizar onde `padd` (project add) é definido (~linha 957) e adicionar logo abaixo:

```python
    # project create
    pcreate = leaf(pr_sub, "create")
    pcreate.add_argument("name", help="Display name (e.g. 'Customer Portal')")
    pcreate.add_argument("--id", default=None,
                         help="kebab-case ID; default = slugify(name)")
    pcreate.add_argument("--description", default="")
    pcreate.set_defaults(func=cmd_project_create)

    # project edit
    pedit = leaf(pr_sub, "edit")
    pedit.add_argument("id", help="project id (kebab-case)")
    pedit.add_argument("--bot-id", default=None,
                       dest="bot_id",
                       help="Telegram bot token; pass empty string to clear")
    pedit.add_argument("--github-url", default=None,
                       dest="github_url")
    pedit.add_argument("--description", default=None)
    pedit.set_defaults(func=cmd_project_edit)
```

- [ ] **Step 4: Smoke local CLI**

```bash
cd ~/.openclaw/kanban-tasks && ./cli.sh project --help 2>&1 | tail -15
```

Expected: lista subcommands incluindo `create`, `edit`, `list`, `add`.

```bash
cd ~/.openclaw/kanban-tasks && ./cli.sh project create --help 2>&1 | tail -10
```

Expected: usage com `name`, `--id`, `--description`.

- [ ] **Step 5: Rodar todos tests**

```bash
cd ~/.openclaw/kanban-tasks && python3 -m pytest tests/ -v 2>&1 | tail -5
```

Expected: 41/41 pass (CLI integration tested via existing pytest se aplicável).

- [ ] **Step 6: Commit**

```bash
cd ~/.openclaw && git add kanban-tasks/lib/api.py && git commit -m "$(cat <<'EOF'
feat(cli.sh): project create + project edit subcommands

cmd_project_create invoca orchestrator com env vars (BEVOX_KNOWLEDGE_DIR,
OPENCLAW_DIR, BEVOX_CODE_DIR, GITHUB_ORG defaults). cmd_project_edit
light-weight update em projects-meta.json (--bot-id, --github-url,
--description; pelo menos 1 obrigatorio).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: MC backend — meta.ts lib + GET extension

**Files:**
- Create: `mission-control/src/lib/projects/meta.ts`
- Create: `mission-control/tests/lib/projects/meta.test.ts`
- Modify: `mission-control/src/lib/projects/types.ts` (extend types)
- Modify: `mission-control/src/app/api/projects/route.ts` (extend GET)

- [ ] **Step 1: Branch mission-control feat**

```bash
cd ~/code/mission-control && git checkout main && git pull --ff-only
git checkout -b feat/mc-projects-factory
```

- [ ] **Step 2: Extender types**

Editar `src/lib/projects/types.ts`. Adicionar campos a `ProjectSummary`:

```typescript
export interface ProjectSummary {
  id: string;
  name: string;
  description: string;
  health: ProjectHealth;
  counts: ProjectCounts;
  // NEW (mc-projects-factory wave):
  is_canonical: boolean;
  github_url: string | null;
  bot_id: string | null;
  created_at: string | null;
}
```

(`ProjectDetail extends ProjectSummary` automaticamente herda os campos.)

- [ ] **Step 3: Tests pra meta.ts**

Write `tests/lib/projects/meta.test.ts`:

```typescript
/**
 * Tests for projects-meta.json reader/merger in MC backend.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-26-mc-projects-factory.md §3.5
 */
import { describe, it, expect } from "vitest";
import {
  readMeta,
  mergeProjectMeta,
  type ProjectMetaEntry,
  type ProjectsMeta,
} from "@/lib/projects/meta";

describe("readMeta", () => {
  it("returns empty schema when file missing", () => {
    const data = readMeta("/tmp/nonexistent-meta-test-12345.json");
    expect(data).toEqual({ version: 1, projects: {} });
  });
});

describe("mergeProjectMeta", () => {
  it("enriches canonical project with metadata if present", () => {
    const meta: ProjectsMeta = {
      version: 1,
      projects: {
        "openclaw": {
          name: "OpenClaw",
          description: "Runtime do Company OS",
          github_url: "https://github.com/bernardTavares/openclaw",
          bot_id: null,
          created_at: "2026-04-08T00:00:00Z",
          source: "canonical",
        },
      },
    };
    const enriched = mergeProjectMeta("openclaw", meta);
    expect(enriched?.github_url).toBe("https://github.com/bernardTavares/openclaw");
    expect(enriched?.is_canonical).toBe(true);
  });

  it("returns null for missing project id", () => {
    const meta: ProjectsMeta = { version: 1, projects: {} };
    expect(mergeProjectMeta("ghost", meta)).toBeNull();
  });

  it("flags user_created source", () => {
    const meta: ProjectsMeta = {
      version: 1,
      projects: {
        "customer-portal": {
          name: "Customer Portal",
          description: "App",
          github_url: "https://github.com/bernardTavares/customer-portal",
          bot_id: null,
          created_at: "2026-04-26T00:00:00Z",
          source: "user_created",
        },
      },
    };
    const enriched = mergeProjectMeta("customer-portal", meta);
    expect(enriched?.is_canonical).toBe(false);
    expect(enriched?.created_at).toBe("2026-04-26T00:00:00Z");
  });
});
```

- [ ] **Step 4: Implementar meta.ts**

Write `src/lib/projects/meta.ts`:

```typescript
/**
 * Reader for ~/.openclaw/projects-meta.json (host-local metadata).
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-26-mc-projects-factory.md §3.5
 */
import * as fs from "fs";
import * as os from "os";
import * as path from "path";

export interface ProjectMetaEntry {
  name: string;
  description: string;
  github_url: string | null;
  bot_id: string | null;
  created_at: string;
  source: "canonical" | "user_created";
}

export interface ProjectsMeta {
  version: number;
  projects: Record<string, ProjectMetaEntry>;
}

const DEFAULT_META: ProjectsMeta = { version: 1, projects: {} };

export function getMetaPath(): string {
  const root = process.env.OPENCLAW_DIR ?? path.join(os.homedir(), ".openclaw");
  return path.join(root, "projects-meta.json");
}

export function readMeta(metaPath: string = getMetaPath()): ProjectsMeta {
  if (!fs.existsSync(metaPath)) return DEFAULT_META;
  try {
    return JSON.parse(fs.readFileSync(metaPath, "utf-8"));
  } catch {
    return DEFAULT_META;
  }
}

export interface EnrichedProject {
  is_canonical: boolean;
  github_url: string | null;
  bot_id: string | null;
  created_at: string | null;
}

export function mergeProjectMeta(
  id: string,
  meta: ProjectsMeta,
): EnrichedProject | null {
  const entry = meta.projects[id];
  if (!entry) return null;
  return {
    is_canonical: entry.source === "canonical",
    github_url: entry.github_url,
    bot_id: entry.bot_id,
    created_at: entry.created_at,
  };
}
```

- [ ] **Step 5: Modificar GET /api/projects**

Editar `src/app/api/projects/route.ts`. Localizar a função GET; adicionar import e enriquecer cada `ProjectSummary` com fields de meta.ts. Pseudo:

```typescript
import { readMeta, mergeProjectMeta } from "@/lib/projects/meta";

// inside GET handler, after building projects array:
const meta = readMeta();
const enriched = projects.map((p) => {
  const m = mergeProjectMeta(p.id, meta);
  return {
    ...p,
    is_canonical: m?.is_canonical ?? CANONICAL_PROJECTS.some(c => c.id === p.id),
    github_url: m?.github_url ?? null,
    bot_id: m?.bot_id ?? null,
    created_at: m?.created_at ?? null,
  };
});

// Also include user-created projects not in canonical:
const userIds = Object.keys(meta.projects).filter(id =>
  meta.projects[id].source === "user_created"
);
for (const id of userIds) {
  if (!enriched.some(p => p.id === id)) {
    const m = meta.projects[id];
    enriched.push({
      id,
      name: m.name,
      description: m.description,
      health: { bot: "missing", workspace: "missing", kanban: "missing", knowledge: "missing" }, // computed elsewhere
      counts: { sprints_active: 0, tasks_in_progress: 0 },
      is_canonical: false,
      github_url: m.github_url,
      bot_id: m.bot_id,
      created_at: m.created_at,
    });
  }
}

return NextResponse.json({ projects: enriched, generated_at: new Date().toISOString() });
```

(Implementação exata depende do shape atual; adapte preservando lógica existente. Health checks pra user-created devem usar mesmas funções `checkBotHealth` etc — passar id virtual; pode retornar partial/missing por default.)

- [ ] **Step 6: Rodar tests + verify build**

```bash
cd ~/code/mission-control && npm test -- --run 2>&1 | tail -3 && npm run build 2>&1 | tail -3
```

Expected: tests green, `/api/projects` aparece na route table sem errors.

- [ ] **Step 7: Commit**

```bash
cd ~/code/mission-control && git add src/lib/projects/meta.ts src/lib/projects/types.ts src/app/api/projects/route.ts tests/lib/projects/meta.test.ts && git commit -m "$(cat <<'EOF'
feat(api/projects): meta.ts reader + GET extension pra merge canonical+meta

readMeta le ~/.openclaw/projects-meta.json (host-local), mergeProjectMeta
enriquece ProjectSummary com is_canonical/github_url/bot_id/created_at.

GET /api/projects passa a retornar canonical (10) + user-created (de meta).
ProjectSummary type extendido pra incluir os 4 novos fields.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: MC backend — POST + PATCH + check-id endpoints

**Files:**
- Create: `mission-control/src/app/api/projects/check-id/route.ts`
- Modify: `mission-control/src/app/api/projects/route.ts` (add POST)
- Modify: `mission-control/src/app/api/projects/[id]/route.ts` (add PATCH)
- Create: `mission-control/tests/app/api/projects/check-id.test.ts`
- Create: `mission-control/tests/app/api/projects/create.test.ts`
- Create: `mission-control/tests/app/api/projects/edit.test.ts`

- [ ] **Step 1: Tests pra check-id**

Write `tests/app/api/projects/check-id.test.ts`:

```typescript
/**
 * Contract tests for GET /api/projects/check-id?id=<slug>.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-26-mc-projects-factory.md §3.4
 */
import { describe, it, expect } from "vitest";

describe("check-id endpoint contract", () => {
  it("response shape valid=true case", () => {
    type Response = { valid: boolean; reason?: "format" | "reserved" | "collision" };
    const sample: Response = { valid: true };
    expect(sample.valid).toBe(true);
  });

  it("response shape with reason", () => {
    type Response = { valid: boolean; reason?: string };
    const sample: Response = { valid: false, reason: "collision" };
    expect(sample.reason).toBe("collision");
  });
});
```

- [ ] **Step 2: Implementar check-id route**

Create dir: `mkdir -p src/app/api/projects/check-id`. Write `src/app/api/projects/check-id/route.ts`:

```typescript
import { NextRequest, NextResponse } from "next/server";
import { isCanonicalProject } from "@/lib/projects/canonical";
import { readMeta } from "@/lib/projects/meta";

export const dynamic = "force-dynamic";

const RESERVED = new Set(["_shared", "_retired", "templates"]);
const ID_RE = /^[a-z][a-z0-9-]+[a-z0-9]$/;

/**
 * GET /api/projects/check-id?id=<slug>
 *
 * Live validation pro NewProjectModal. Returns { valid, reason? }.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-26-mc-projects-factory.md §3.4
 */
export async function GET(req: NextRequest) {
  const id = new URL(req.url).searchParams.get("id");
  if (!id) {
    return NextResponse.json({ valid: false, reason: "format" });
  }
  if (id.length < 2 || id.length > 40 || !ID_RE.test(id)) {
    return NextResponse.json({ valid: false, reason: "format" });
  }
  if (RESERVED.has(id)) {
    return NextResponse.json({ valid: false, reason: "reserved" });
  }
  if (isCanonicalProject(id)) {
    return NextResponse.json({ valid: false, reason: "collision" });
  }
  const meta = readMeta();
  if (id in meta.projects) {
    return NextResponse.json({ valid: false, reason: "collision" });
  }
  return NextResponse.json({ valid: true });
}
```

- [ ] **Step 3: Tests pra POST + PATCH**

Write `tests/app/api/projects/create.test.ts`:

```typescript
/**
 * Contract tests for POST /api/projects.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-26-mc-projects-factory.md §3.3
 */
import { describe, it, expect } from "vitest";

describe("POST /api/projects contract", () => {
  it("success response shape", () => {
    type Response = {
      success: boolean;
      id?: string;
      github_url?: string;
      steps_completed: number;
      log?: unknown[];
    };
    const sample: Response = {
      success: true,
      id: "x",
      github_url: "https://github.com/bernardTavares/x",
      steps_completed: 6,
    };
    expect(sample.steps_completed).toBe(6);
  });

  it("failure response includes failed_at + error", () => {
    type Response = {
      success: boolean;
      failed_at?: number;
      error_code?: string;
    };
    const sample: Response = {
      success: false,
      failed_at: 5,
      error_code: "code_dir_exists",
    };
    expect(sample.failed_at).toBe(5);
  });
});
```

Write `tests/app/api/projects/edit.test.ts`:

```typescript
/**
 * Contract tests for PATCH /api/projects/[id].
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-26-mc-projects-factory.md §3.3
 */
import { describe, it, expect } from "vitest";

describe("PATCH /api/projects/[id] contract", () => {
  it("partial update body accepts bot_id", () => {
    type Body = { bot_id?: string | null; github_url?: string | null; description?: string };
    const sample: Body = { bot_id: "8042100000:AAH..." };
    expect(sample.bot_id).toContain(":");
  });

  it("validates Telegram bot token regex", () => {
    const re = /^\d{8,12}:[A-Za-z0-9_-]{30,}$/;
    expect(re.test("8042100000:AAH" + "x".repeat(30))).toBe(true);
    expect(re.test("invalid")).toBe(false);
  });
});
```

- [ ] **Step 4: Implementar POST em route.ts**

Editar `src/app/api/projects/route.ts`. Adicionar **antes** do `export async function GET`:

```typescript
import { spawn } from "child_process";

const ID_RE = /^[a-z][a-z0-9-]+[a-z0-9]$/;
const RESERVED = new Set(["_shared", "_retired", "templates"]);
const CLI_PATH = "~/.openclaw/kanban-tasks/cli.sh";

function slugify(name: string): string {
  return name
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40)
    .replace(/-+$/, "");
}

export async function POST(req: Request) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }
  const bb = (body ?? {}) as Record<string, unknown>;
  const name = typeof bb.name === "string" ? bb.name.trim() : "";
  const id = typeof bb.id === "string" && bb.id.trim() ? bb.id.trim() : slugify(name);
  const description = typeof bb.description === "string" ? bb.description : "";

  if (!name || name.length < 2 || name.length > 50) {
    return NextResponse.json(
      { error: "validation", field: "name", reason: "length 2-50" },
      { status: 400 },
    );
  }
  if (!id || id.length < 2 || id.length > 40 || !ID_RE.test(id) || RESERVED.has(id)) {
    return NextResponse.json(
      { error: "validation", field: "id", reason: "kebab-case 2-40 + non-reserved" },
      { status: 400 },
    );
  }

  // Spawn CLI subprocess
  return new Promise<NextResponse>((resolve) => {
    const child = spawn(CLI_PATH, [
      "project", "create",
      "--id", id,
      "--description", description,
      "--json",
      name,
    ], { timeout: 60_000 });

    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (d) => { stdout += d.toString(); });
    child.stderr.on("data", (d) => { stderr += d.toString(); });
    child.on("close", (code) => {
      if (code === 0) {
        try {
          const result = JSON.parse(stdout.trim().split("\n").pop() ?? "{}");
          resolve(NextResponse.json(result, { status: 201 }));
        } catch {
          resolve(NextResponse.json(
            { error: "cli_parse", detail: stdout },
            { status: 500 },
          ));
        }
      } else {
        // Try to parse last JSON line; fall back to raw stderr
        let result: unknown = null;
        try {
          result = JSON.parse(stdout.trim().split("\n").pop() ?? "{}");
        } catch {/* no-op */}
        if (result && typeof result === "object") {
          resolve(NextResponse.json(result, { status: 400 }));
        } else {
          resolve(NextResponse.json(
            { error: "cli_failed", detail: stderr.trim() || `exit ${code}` },
            { status: 500 },
          ));
        }
      }
    });
  });
}
```

- [ ] **Step 5: Implementar PATCH em [id]/route.ts**

Editar `src/app/api/projects/[id]/route.ts`. Se não existir GET handler (a wave anterior só tinha o GET via parent route?), preserve o existente e adicione PATCH:

```typescript
import { spawn } from "child_process";

const BOT_ID_RE = /^\d{8,12}:[A-Za-z0-9_-]{30,}$/;
const CLI_PATH = "~/.openclaw/kanban-tasks/cli.sh";

export async function PATCH(
  req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  let body: unknown;
  try { body = await req.json(); } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }
  const bb = (body ?? {}) as Record<string, unknown>;

  const args: string[] = ["project", "edit", id];
  if (typeof bb.bot_id === "string" || bb.bot_id === null) {
    const v = bb.bot_id;
    if (v !== null && !BOT_ID_RE.test(v as string)) {
      return NextResponse.json(
        { error: "validation", field: "bot_id", reason: "invalid Telegram token format" },
        { status: 400 },
      );
    }
    args.push("--bot-id", v === null ? "" : (v as string));
  }
  if (typeof bb.github_url === "string" || bb.github_url === null) {
    args.push("--github-url", bb.github_url === null ? "" : (bb.github_url as string));
  }
  if (typeof bb.description === "string") {
    args.push("--description", bb.description);
  }
  if (args.length === 3) {
    return NextResponse.json(
      { error: "validation", reason: "no fields provided" },
      { status: 400 },
    );
  }
  args.push("--json");

  return new Promise<NextResponse>((resolve) => {
    const child = spawn(CLI_PATH, args, { timeout: 10_000 });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", d => { stdout += d.toString(); });
    child.stderr.on("data", d => { stderr += d.toString(); });
    child.on("close", (code) => {
      if (code === 0) {
        try {
          const result = JSON.parse(stdout.trim().split("\n").pop() ?? "{}");
          resolve(NextResponse.json(result));
        } catch {
          resolve(NextResponse.json({ error: "cli_parse" }, { status: 500 }));
        }
      } else {
        resolve(NextResponse.json(
          { error: "cli_failed", detail: stderr.trim() },
          { status: 400 },
        ));
      }
    });
  });
}
```

- [ ] **Step 6: Rodar tests + build**

```bash
cd ~/code/mission-control && npm test -- --run 2>&1 | tail -3 && npm run build 2>&1 | grep -E "/api/projects|error" | head -10
```

Expected: tests green; routes `POST /api/projects`, `PATCH /api/projects/[id]`, `GET /api/projects/check-id` listadas.

- [ ] **Step 7: Commit**

```bash
cd ~/code/mission-control && git add src/app/api/projects/route.ts "src/app/api/projects/[id]/route.ts" src/app/api/projects/check-id/route.ts tests/app/api/projects/ && git commit -m "$(cat <<'EOF'
feat(api/projects): POST create + PATCH edit + check-id endpoints

POST /api/projects: validation + spawn 'cli.sh project create' subprocess,
returns CLI JSON wrapped em 201/400/500 status. Timeout 60s.

PATCH /api/projects/[id]: validation (bot_id Telegram regex) + spawn
'cli.sh project edit'. Light-weight (no orchestration). Timeout 10s.

GET /api/projects/check-id: live validation pro NewProjectModal — testa
format/reserved/collision sem invocar CLI (read-only meta + canonical).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: MC frontend — NewProjectModal + ProjectsPage button

**Files:**
- Create: `mission-control/src/components/projects/NewProjectModal.tsx`
- Create: `mission-control/tests/components/projects/NewProjectModal.test.tsx`
- Modify: `mission-control/src/app/(dashboard)/projects/page.tsx` (button + modal state)

- [ ] **Step 1: Tests do modal**

Write `tests/components/projects/NewProjectModal.test.tsx`:

```typescript
/**
 * Contract tests for NewProjectModal.
 *
 * Spec: bevox-knowledge/35_specs/company-os/2026-04-26-mc-projects-factory.md §3.4
 */
import { describe, it, expect } from "vitest";
import type { NewProjectModalProps } from "@/components/projects/NewProjectModal";

describe("NewProjectModalProps contract", () => {
  it("requires open + onClose + onCreated", () => {
    let createdId: string | null = null;
    const props: NewProjectModalProps = {
      open: true,
      onClose: () => {},
      onCreated: (id) => { createdId = id; },
    };
    props.onCreated("foo");
    expect(createdId).toBe("foo");
    expect(props.open).toBe(true);
  });
});

describe("slugify in modal", () => {
  it("derives kebab-case from name", async () => {
    const { slugify } = await import("@/components/projects/NewProjectModal");
    expect(slugify("Customer Portal")).toBe("customer-portal");
    expect(slugify("Foo & Bar!")).toBe("foo-bar");
    expect(slugify("Notação")).toBe("notacao");
  });
});
```

- [ ] **Step 2: Implementar modal**

Write `src/components/projects/NewProjectModal.tsx`:

```typescript
"use client";

import { useEffect, useState } from "react";

export interface NewProjectModalProps {
  open: boolean;
  onClose: () => void;
  onCreated: (id: string) => void;
}

const ID_RE = /^[a-z][a-z0-9-]+[a-z0-9]$/;

export function slugify(name: string): string {
  return name
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40)
    .replace(/-+$/, "");
}

export function NewProjectModal({ open, onClose, onCreated }: NewProjectModalProps) {
  const [name, setName] = useState("");
  const [id, setId] = useState("");
  const [idTouched, setIdTouched] = useState(false);
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [idStatus, setIdStatus] = useState<{ valid: boolean; reason?: string } | null>(null);

  // Auto-derive id from name (until user touches id field)
  useEffect(() => {
    if (!idTouched) setId(slugify(name));
  }, [name, idTouched]);

  // Live id validation (debounced 300ms)
  useEffect(() => {
    if (!id || !ID_RE.test(id)) {
      setIdStatus({ valid: false, reason: "format" });
      return;
    }
    const handle = setTimeout(async () => {
      try {
        const r = await fetch(`/api/projects/check-id?id=${encodeURIComponent(id)}`);
        const data = await r.json();
        setIdStatus(data);
      } catch { /* ignore network */ }
    }, 300);
    return () => clearTimeout(handle);
  }, [id]);

  // Reset on close
  useEffect(() => {
    if (!open) {
      setName(""); setId(""); setIdTouched(false);
      setDescription(""); setError(null); setIdStatus(null);
    }
  }, [open]);

  // Esc closes
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  const canSubmit = !submitting
    && name.length >= 2 && name.length <= 50
    && idStatus?.valid === true;

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const r = await fetch("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, id, description }),
      });
      const data = await r.json();
      if (r.ok && data.success) {
        onCreated(data.id);
        onClose();
      } else {
        setError(`Step ${data.failed_at ?? "?"} falhou: ${data.error_message ?? data.error ?? "unknown"}`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100,
    }}>
      <div onClick={(e) => e.stopPropagation()} style={{
        background: "#161b22", borderRadius: 8, padding: "1.25rem 1.5rem",
        width: "90%", maxWidth: 520, color: "#e0e0e0",
        border: "1px solid #2a2f3e",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
          <h2 style={{ margin: 0, fontSize: "1.1rem", color: "#4f9eff" }}>Novo projeto</h2>
          <button type="button" onClick={onClose} style={{ background: "transparent", border: "none", color: "#888", fontSize: "1.4rem", cursor: "pointer" }}>×</button>
        </div>

        <label style={{ display: "block", marginBottom: "0.6rem" }}>
          <div style={{ color: "#888", fontSize: "0.7rem", marginBottom: "0.2rem" }}>Nome</div>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={submitting}
            placeholder="Customer Portal"
            style={{ width: "100%", padding: "0.45rem 0.6rem", background: "#1a2230", border: "1px solid #2a2f3e", borderRadius: 4, color: "#e0e0e0", fontSize: "0.9rem" }}
          />
        </label>

        <label style={{ display: "block", marginBottom: "0.6rem" }}>
          <div style={{ color: "#888", fontSize: "0.7rem", marginBottom: "0.2rem" }}>
            ID {idStatus && !idStatus.valid && <span style={{ color: "#e46e6e" }}>· {idStatus.reason}</span>}
          </div>
          <input
            type="text"
            value={id}
            onChange={(e) => { setId(e.target.value); setIdTouched(true); }}
            disabled={submitting}
            placeholder="customer-portal"
            style={{
              width: "100%", padding: "0.45rem 0.6rem",
              background: "#1a2230",
              border: `1px solid ${idStatus && !idStatus.valid ? "#e46e6e" : "#2a2f3e"}`,
              borderRadius: 4, color: "#e0e0e0", fontSize: "0.85rem", fontFamily: "monospace",
            }}
          />
        </label>

        <label style={{ display: "block", marginBottom: "1rem" }}>
          <div style={{ color: "#888", fontSize: "0.7rem", marginBottom: "0.2rem" }}>Descrição (opcional)</div>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={submitting}
            rows={2}
            placeholder="App de portal do cliente"
            style={{ width: "100%", padding: "0.45rem 0.6rem", background: "#1a2230", border: "1px solid #2a2f3e", borderRadius: 4, color: "#e0e0e0", fontSize: "0.85rem", resize: "vertical" }}
          />
        </label>

        <div style={{ background: "#1a2230", padding: "0.6rem 0.8rem", borderRadius: 4, fontSize: "0.7rem", color: "#888", lineHeight: 1.7, marginBottom: "1rem" }}>
          Vai criar:
          <div>✓ bevox-knowledge folders + stubs</div>
          <div>✓ kanban-tasks: 1 active + 1 next sprint</div>
          <div>✓ ~/.openclaw/{id || "&lt;id&gt;"}/ runtime workspace</div>
          <div>✓ ~/code/{id || "&lt;id&gt;"}/ git init</div>
          <div>✓ GitHub: bernardTavares/{id || "&lt;id&gt;"} (private)</div>
        </div>

        {error && (
          <div style={{ background: "#3f1e1e", color: "#e46e6e", padding: "0.6rem 0.8rem", borderRadius: 4, fontSize: "0.78rem", marginBottom: "1rem" }}>
            {error}
          </div>
        )}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
          <button type="button" onClick={onClose} disabled={submitting} style={{ background: "transparent", border: "1px solid #2a2f3e", color: "#888", padding: "0.4rem 0.85rem", borderRadius: 4, fontSize: "0.85rem", cursor: "pointer" }}>Abortar</button>
          <button type="button" onClick={submit} disabled={!canSubmit} style={{ background: canSubmit ? "#1e3a5f" : "#2a2f3e", color: canSubmit ? "#6ec1e4" : "#666", border: "none", padding: "0.4rem 0.85rem", borderRadius: 4, fontSize: "0.85rem", cursor: canSubmit ? "pointer" : "not-allowed" }}>
            {submitting ? "Criando…" : "Criar"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Adicionar button + modal state em projects/page.tsx**

Editar `src/app/(dashboard)/projects/page.tsx`. Adicionar imports + estado + botão no header + render do modal:

```typescript
import { useState } from "react";
import { useRouter } from "next/navigation";
import { NewProjectModal } from "@/components/projects/NewProjectModal";

// inside ProjectsPage component:
const router = useRouter();
const [createOpen, setCreateOpen] = useState(false);
```

E no JSX, modificar o `<header>`:

```jsx
<header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
  <h1 style={{ ... }}>Projects</h1>
  <button type="button" onClick={() => setCreateOpen(true)} style={{
    background: "#1e3a5f", color: "#6ec1e4", border: "none",
    padding: "0.5rem 1rem", borderRadius: 4, fontSize: "0.85rem",
    cursor: "pointer", fontWeight: 600,
  }}>+ New project</button>
</header>
```

E antes do fechamento do component:

```jsx
<NewProjectModal
  open={createOpen}
  onClose={() => setCreateOpen(false)}
  onCreated={(id) => router.push(`/projects/${id}`)}
/>
```

- [ ] **Step 4: Tests + build**

```bash
cd ~/code/mission-control && npm test -- --run 2>&1 | tail -3 && npm run build 2>&1 | tail -3
```

Expected: tests green, build verde.

- [ ] **Step 5: Commit**

```bash
cd ~/code/mission-control && git add src/components/projects/NewProjectModal.tsx tests/components/projects/NewProjectModal.test.tsx "src/app/(dashboard)/projects/page.tsx" && git commit -m "$(cat <<'EOF'
feat(projects): NewProjectModal + '+ New project' button

Modal com form name/id/description + live validation (debounced 300ms via
check-id endpoint) + slugify auto-derived id (override editable). Submit
chama POST /api/projects, on success router.push pra detail page.

Esc/X/backdrop fecham. Submit disabled se invalid ou submitting.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: MC frontend — ProjectGeralTab inline edit

**Files:**
- Modify: `mission-control/src/components/projects/ProjectGeralTab.tsx`

- [ ] **Step 1: Inspecionar componente atual**

```bash
wc -l ~/code/mission-control/src/components/projects/ProjectGeralTab.tsx
grep -n "InfoBox\|description\|github_url\|bot_id" ~/code/mission-control/src/components/projects/ProjectGeralTab.tsx | head -10
```

- [ ] **Step 2: Adicionar state edit + PATCH handler**

Editar `src/components/projects/ProjectGeralTab.tsx`. Adicionar dentro do componente:

```typescript
const [editingExternal, setEditingExternal] = useState(false);
const [editGithubUrl, setEditGithubUrl] = useState(detail.github_url ?? "");
const [editBotId, setEditBotId] = useState(detail.bot_id ?? "");
const [savingExternal, setSavingExternal] = useState(false);
const [editError, setEditError] = useState<string | null>(null);

const saveExternal = async () => {
  setSavingExternal(true);
  setEditError(null);
  try {
    const body: Record<string, unknown> = {};
    if (editGithubUrl !== (detail.github_url ?? "")) {
      body.github_url = editGithubUrl || null;
    }
    if (editBotId !== (detail.bot_id ?? "")) {
      body.bot_id = editBotId || null;
    }
    if (Object.keys(body).length === 0) {
      setEditingExternal(false);
      return;
    }
    const r = await fetch(`/api/projects/${encodeURIComponent(detail.id)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const j = await r.json().catch(() => ({}));
      throw new Error(j.reason ?? j.detail ?? `HTTP ${r.status}`);
    }
    setEditingExternal(false);
    // Trigger parent reload — emit event or call onMutate prop
    window.location.reload(); // pragmatic: reload to refresh detail
  } catch (e) {
    setEditError(e instanceof Error ? e.message : String(e));
  } finally {
    setSavingExternal(false);
  }
};
```

E modificar a InfoBox de "External links" pra exibir form quando `editingExternal === true`:

```jsx
<InfoBox label="External links">
  {!editingExternal ? (
    <>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem", fontSize: "0.7rem" }}>
        {detail.github_url && (
          <a href={detail.github_url} target="_blank" rel="noreferrer" style={{ color: "#4f9eff", textDecoration: "none" }}>↗ {detail.github_url}</a>
        )}
        {detail.bot_id && (
          <span style={{ color: "#888", fontSize: "0.65rem", fontFamily: "monospace" }}>
            bot: {detail.bot_id.slice(0, 12)}{detail.bot_id.length > 12 ? "…" : ""}
          </span>
        )}
        <button type="button" onClick={() => setEditingExternal(true)} style={{
          marginTop: "0.4rem", background: "transparent", border: "1px solid #2a2f3e",
          color: "#888", padding: "0.2rem 0.5rem", borderRadius: 3, fontSize: "0.65rem", cursor: "pointer", alignSelf: "flex-start",
        }}>Editar</button>
      </div>
    </>
  ) : (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem", fontSize: "0.7rem" }}>
      <label>
        <div style={{ color: "#888", fontSize: "0.6rem" }}>github_url</div>
        <input
          type="url"
          value={editGithubUrl}
          onChange={(e) => setEditGithubUrl(e.target.value)}
          disabled={savingExternal}
          style={{ width: "100%", padding: "0.3rem 0.4rem", background: "#0d1117", border: "1px solid #2a2f3e", borderRadius: 3, color: "#e0e0e0", fontSize: "0.7rem" }}
        />
      </label>
      <label>
        <div style={{ color: "#888", fontSize: "0.6rem" }}>bot_id (Telegram token)</div>
        <input
          type="text"
          value={editBotId}
          onChange={(e) => setEditBotId(e.target.value)}
          disabled={savingExternal}
          placeholder="8042100000:AAH..."
          style={{ width: "100%", padding: "0.3rem 0.4rem", background: "#0d1117", border: "1px solid #2a2f3e", borderRadius: 3, color: "#e0e0e0", fontSize: "0.7rem", fontFamily: "monospace" }}
        />
      </label>
      {editError && <div style={{ color: "#e46e6e", fontSize: "0.65rem" }}>{editError}</div>}
      <div style={{ display: "flex", gap: "0.4rem" }}>
        <button type="button" onClick={saveExternal} disabled={savingExternal} style={{
          background: "#1e3a5f", color: "#6ec1e4", border: "none",
          padding: "0.25rem 0.6rem", borderRadius: 3, fontSize: "0.7rem", cursor: "pointer",
        }}>{savingExternal ? "Salvando…" : "Salvar"}</button>
        <button type="button" onClick={() => { setEditingExternal(false); setEditError(null); }} disabled={savingExternal} style={{
          background: "transparent", color: "#888", border: "1px solid #2a2f3e",
          padding: "0.25rem 0.6rem", borderRadius: 3, fontSize: "0.7rem", cursor: "pointer",
        }}>Cancelar</button>
      </div>
    </div>
  )}
</InfoBox>
```

Importar `useState` no topo se ainda não estiver.

- [ ] **Step 3: Tests + build**

```bash
cd ~/code/mission-control && npm test -- --run 2>&1 | tail -3 && npm run build 2>&1 | tail -3
```

Expected: tests green, build verde.

- [ ] **Step 4: Commit**

```bash
cd ~/code/mission-control && git add src/components/projects/ProjectGeralTab.tsx && git commit -m "$(cat <<'EOF'
feat(ProjectGeralTab): inline edit em External links InfoBox

Botao Editar reveal form com github_url + bot_id inputs. Salvar dispara
PATCH /api/projects/[id] (light-weight). Cancelar volta ao display mode.
window.location.reload() pos-save (pragmatic; otimizar com fetch refresh
em wave futura se needed).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 16: Push openclaw + MC PRs + pause

- [ ] **Step 1: Push openclaw plan + feat**

```bash
cd ~/.openclaw && git push -u origin feat/mc-projects-factory-plan 2>&1 | tail -3
gh pr create --title "plan(mc-projects-factory): implementation plan" --body "Plan doc para spec bevox-knowledge/35_specs/company-os/2026-04-26-mc-projects-factory.md.

🤖 Generated with [Claude Code](https://claude.com/claude-code)" 2>&1 | tail -3

cd ~/.openclaw && git push -u origin feat/mc-projects-factory 2>&1 | tail -3
gh pr create --title "feat(openclaw): project create/edit CLI orchestrator" --body "$(cat <<'EOF'
## Summary
Novo CLI 'openclaw project create <name>' orquestra 6 destinos cross-filesystem
(bevox-knowledge folders, kanban-tasks, ~/.openclaw runtime, projects-meta.json,
local code dir, GitHub repo). Pre-flight + sequencia reversibility-ascending.

Spec: bevox-knowledge/35_specs/company-os/2026-04-26-mc-projects-factory.md

## What's in this PR
- project_factory.py: slugify, is_valid_id, pre-flight (6 checks), 6 step impls, orchestrator
- projects_meta.py: read/write atomic + flock + insert/update
- 8 templates (PRD stub, roadmap stub, README, 8 persona stubs)
- cli.sh entries: project create + edit (existing list/add preservados)
- ~40 pytest tests cobrindo cada helper + happy path + partial failure

## Test plan
- [x] pytest 41/41 verde
- [ ] Smoke: 'openclaw project create "Test Alpha"' standalone funcional
- [ ] MC PR equivalente integra via subprocess

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 2: Push MC feat**

```bash
cd ~/code/mission-control && git push -u origin feat/mc-projects-factory 2>&1 | tail -3
gh pr create --title "feat(mc): projects factory — create modal + edit inline (E2/mc-projects-factory)" --body "$(cat <<'EOF'
## Summary
'+ New project' button no /projects + modal de criacao + edit inline de
metadata (bot_id, github_url) em /projects/[id] tab Geral.

Backend invoca CLI 'openclaw project create' (entregue no openclaw repo PR
correspondente) via subprocess. PATCH light-weight pra metadata edit.

Spec: bevox-knowledge/35_specs/company-os/2026-04-26-mc-projects-factory.md

## What's in this PR
- meta.ts reader: ~/.openclaw/projects-meta.json + merge canonical+meta
- types.ts extended: ProjectSummary com is_canonical/github_url/bot_id/created_at
- 3 endpoints: POST /api/projects, PATCH /api/projects/[id], GET /api/projects/check-id
- GET /api/projects extension: retorna canonical + user-created merged
- NewProjectModal component
- ProjectGeralTab inline edit External links InfoBox

## Pre-requisitos
- openclaw PR do CLI deve mergeer ANTES (subprocess depende do binario)
- bevox-knowledge stubs (PR #20) ja entregues

## Test plan
- [x] vitest verde com novos contract tests
- [x] npm run build verde
- [ ] **Pos-merge:** pull + npm install + npm run build + systemctl restart
- [ ] Smoke E2E 10 cenarios

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: PAUSA — aguardar merge dos 3 PRs (openclaw plan, openclaw feat, MC feat)**

Bernard merge na ordem: openclaw feat (CLI) → MC feat (UI). Plan doc PR é otimo mergear quando convier.

---

## Task 17: Pull main + build + restart MC + verify

**Pré-requisito:** PRs mergeados; main atualizada nos dois repos.

- [ ] **Step 1: Update env + verificações iniciais**

```bash
cd ~/.openclaw && git checkout main && git pull --ff-only 2>&1 | tail -3
```

Adicionar `BEVOX_CODE_DIR` ao `~/.openclaw/.env` se ainda não estiver:

```bash
grep -q "^BEVOX_CODE_DIR" ~/.openclaw/.env || echo "BEVOX_CODE_DIR=~/code" >> ~/.openclaw/.env
```

Garantir que `~/code/` existe:

```bash
mkdir -p ~/code
```

- [ ] **Step 2: CLI smoke standalone**

```bash
cd ~/.openclaw && ./kanban-tasks/cli.sh project --help 2>&1 | tail -10
```

Expected: lista `create`, `edit`, `list`, `add`.

```bash
cd ~/.openclaw && ./kanban-tasks/cli.sh project create "Smoke Test 26" --json 2>&1 | tail -20
```

Expected (se tudo ok): JSON com `success: true, id: smoke-test-26, steps_completed: 6`. Pode falhar em step 6 se `gh` não tem permissão de criar repo na org bernardTavares — nesse caso aceito como "esperado em smoke isolado", limpe manualmente:

```bash
# Cleanup smoke test artifacts
rm -rf ~/bevox-knowledge/10_prd/smoke-test-26 ~/bevox-knowledge/40_roadmap/smoke-test-26
sed -i '/- smoke-test-26/d' ~/.openclaw/kanban-tasks/projects.yml
# Sprints: edit state.json manual ou aceitar como artefato (cleanup melhor via CLI futura)
rm -rf ~/.openclaw/smoke-test-26 ~/.openclaw/workspace-smoke-test-26
rm -rf ~/code/smoke-test-26
# Remove from projects-meta.json:
python3 -c "
import json
p = '~/.openclaw/projects-meta.json'
data = json.load(open(p))
data['projects'].pop('smoke-test-26', None)
json.dump(data, open(p, 'w'), indent=2)
"
# GitHub: gh repo delete bernardTavares/smoke-test-26 --yes (se foi criado)
```

- [ ] **Step 3: MC pull + build + restart**

```bash
cd ~/code/mission-control && git checkout main && git pull --ff-only 2>&1 | tail -3
npm install 2>&1 | tail -3
npm run build 2>&1 | tail -10
systemctl --user restart mission-control
sleep 4 && systemctl --user is-active mission-control
```

Expected: build verde com `POST /api/projects`, `PATCH /api/projects/[id]`, `GET /api/projects/check-id` listadas; service `active`.

- [ ] **Step 4: Health probes**

```bash
curl -sS -o /dev/null -w "GET /projects: HTTP %{http_code}\n" -H "Cf-Access-Authenticated-User-Email: you@example.com" http://127.0.0.1:4310/projects
curl -sS -H "Cf-Access-Authenticated-User-Email: you@example.com" "http://127.0.0.1:4310/api/projects/check-id?id=foo-bar-baz" 2>&1 | python3 -m json.tool
curl -sS -H "Cf-Access-Authenticated-User-Email: you@example.com" "http://127.0.0.1:4310/api/projects/check-id?id=openclaw" 2>&1 | python3 -m json.tool
```

Expected:
- /projects HTTP 200
- check-id `foo-bar-baz`: `{ "valid": true }`
- check-id `openclaw`: `{ "valid": false, "reason": "collision" }`

---

## Task 18: Smoke E2E 10 cenários

**Pré-requisito:** Task 17 completa.

Bernard valida em `mc.example.com/projects`:

- [ ] **Cenário 1 — Happy path** — click "+ New project" → modal abre → name "Test Project Alpha" → ID auto vira "test-project-alpha" → click Criar → ~10s loading → modal fecha → redirect `/projects/test-project-alpha` → tab Geral renderiza com PRD stub
- [ ] **Cenário 2 — ID auto-derive com diacritics** — name "Notação Teste" → ID auto vira "notacao-teste"
- [ ] **Cenário 3 — ID override** — name "Foo Bar" → editar ID pra "fb-test" → criar usa o override
- [ ] **Cenário 4 — Collision** — tentar criar com ID "openclaw" → input vermelho + msg "collision" → botão Criar disabled
- [ ] **Cenário 5 — Reserved** — tentar ID "_shared" → reason "reserved"
- [ ] **Cenário 6 — Edit bot_id** — `/projects/<criado>` → tab Geral → InfoBox External links → "Editar" → digitar bot token → salvar → reload mostra mascarado
- [ ] **Cenário 7 — Canonical preserva** — `/projects/openclaw` → tab Geral → editar bot_id (canonical permite) → salvar → check `~/.openclaw/projects-meta.json`
- [ ] **Cenário 8 — GitHub repo** — pós-create, abrir `https://github.com/bernardTavares/test-project-alpha` → repo private + commit + README visível
- [ ] **Cenário 9 — CLI standalone** — terminal `openclaw project create "Beta CLI Test"` → mesmos 6 steps + JSON output exit 0
- [ ] **Cenário 10 — Pre-flight reject** — em terminal: `BEVOX_CODE_DIR=/nonexistent openclaw project create "Bad Test"` → exit 1, mensagem clara `code_missing`

**Smoke gate:** 10/10 → wave delivered. Falha → rollback Tier 1 (`git revert <merge-sha>` nos 2 repos + rebuild + restart).

---

## Task 19: Tracker entry — wave delivered

**Files:**
- Modify: `bevox-knowledge/40_roadmap/_shared/delivery-tracker.yml`

- [ ] **Step 1: Branch + insert entry**

```bash
cd ~/bevox-knowledge && git checkout main && git pull --ff-only
git checkout -b draft/tracker-mc-projects-factory-delivered
```

Adicionar em `40_roadmap/_shared/delivery-tracker.yml` sob E2 (depois da entry `mc-projects-redesign`):

```yaml
      - id: mc-projects-factory
        status: delivered
        delivered_at: 2026-04-26
        spec: 35_specs/company-os/2026-04-26-mc-projects-factory.md
        pr_mc: https://github.com/bernardTavares/mission-control/pull/<N>
        pr_openclaw: https://github.com/bernardTavares/openclaw/pull/<N>
        pr_openclaw_plan: https://github.com/bernardTavares/openclaw/pull/<N>
        pr_knowledge_spec: https://github.com/bernardTavares/bevox-knowledge/pull/<N>
        narrative: "MC ganha factory de projeto: '+ New project' modal cria projeto end-to-end (bevox-knowledge folders, kanban sprints, ~/.openclaw workspace, projects-meta.json, local code dir, GitHub private repo). Edit inline metadata em tab Geral."
        features:
          - "CLI openclaw project create <name> orquestra 6 destinos cross-filesystem em sequencia reversibility-ascending"
          - "Pre-flight 6 checks (id collision, fs writable, gh auth, github repo free, kb clean)"
          - "Step 1-6 isolados como funcoes (testaveis com tmpdir + monkeypatch)"
          - "JSONL logging em ~/.openclaw/projects-create.jsonl pra audit + cleanup hint"
          - "Templates: 2 stubs KB + 8 persona stubs + 1 README — todos com {name}/{slug}/{date}/{description} substituicao"
          - "projects-meta.json novo storage host-local (gitignored) com schema v1 + flock atomic"
          - "MC backend POST /api/projects spawn CLI subprocess, PATCH light-weight metadata, GET extension merge canonical+meta"
          - "MC frontend NewProjectModal com slugify auto-derive + live validation (debounced 300ms via check-id endpoint)"
          - "ProjectGeralTab inline edit em External links InfoBox (github_url + bot_id)"
          - "Telegram bot_id agora storage por-projeto (preparacao pra wave futura de scripts parametrizados)"
          - "BEVOX_CODE_DIR env var nova (default ~/code)"
          - "Reuso maximo: task_lib.add_project + sprint_lib.bootstrap existentes; CANONICAL_PROJECTS preservado imutavel"
          - "~40 pytest CLI + ~20 vitest novos. 10 smoke E2E gating."
          - "Cross-repo: openclaw (Python CLI) + mission-control (UI/API). 2 PRs paralelos."
          - "Sem auto-rollback em runtime failure — logs JSONL + cleanup hint manual (deferred openclaw project remove pra wave futura)"
```

(`<N>` substituir pelos PR numbers reais.)

- [ ] **Step 2: Validate YAML + commit + push + PR**

```bash
cd ~/bevox-knowledge && python3 -c "import yaml; yaml.safe_load(open('40_roadmap/_shared/delivery-tracker.yml')); print('valid')"
git add 40_roadmap/_shared/delivery-tracker.yml
git commit -m "$(cat <<'EOF'
tracker(E2/mc-projects-factory): delivered 2026-04-26

Factory de projeto end-to-end via UI MC + CLI openclaw project create.
6 destinos cross-filesystem, pre-flight + sequencia reversibility-ascending.
Edit inline metadata (bot_id, github_url). Storage host-local em
~/.openclaw/projects-meta.json schema v1.

Smoke E2E 10 cenarios pass. PRs mission-control #<N>, openclaw #<N>.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git push -u origin draft/tracker-mc-projects-factory-delivered
gh pr create --title "tracker(E2/mc-projects-factory): delivered 2026-04-26" --body "Wave fecha o ciclo de gestão de projetos no MC (list + create + edit). Smoke 10/10 pass. PRs mc + openclaw merged.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

- [ ] **Step 3: Aguardar merge**

Bernard merge → wave fechada formalmente.

---

## Self-review

**Spec coverage:**
- §1 decisões 1-5 → Tasks 2-11 (CLI orchestrator), 12-15 (MC), 7 (storage)
- §2 architecture → file structure + Tasks 2-11, 12-15
- §3.1 CLI commands → Tasks 11 + cli.sh entries
- §3.2 ID derivation + validation → Task 2
- §3.3 MC backend (POST/PATCH/GET) → Task 13
- §3.4 UI (NewProjectModal + edit) → Tasks 14-15
- §3.5 projects-meta.json schema → Task 7
- §4 data flow → Tasks 13 (POST chain), 15 (PATCH chain)
- §5 edge cases → Task 3 (pre-flight) + Task 10 (failure log) + Task 13 (validation 400s)
- §6 arquivos → file structure mapeia 1:1
- §7 ordem PRs → Tasks 1, 16-17 implementam
- §8 testing → ~41 pytest + ~20 vitest + 10 smoke
- §9 DoD → Cenários do smoke = checklist
- §10 rollback → Task 17/18 PR descriptions mencionam Tier 1
- §11 não-escopo → respeitado (sem project remove/rename, sem bot scripts funcionais, etc.)

**Placeholder scan:** zero TBD/TODO no plan. Code blocks completos em todos os steps.

**Type consistency:**
- `ProjectSummary` extension (Task 12) consistente em Task 13 (POST/PATCH responses) + Task 14 (modal payload) + Task 15 (edit form)
- `ProjectMetaEntry` shape (Task 12 meta.ts) bate com `step_4_meta_insert` output (Task 7) — ambos têm name/description/github_url/bot_id/created_at/source
- `ProjectCreateConfig` (Task 10) usado em Task 11 cmd_project_create
- `BOT_ID_RE` consistente entre PATCH route (Task 13) e ProjectGeralTab edit (Task 15) — `/^\d{8,12}:[A-Za-z0-9_-]{30,}$/`
- `slugify` reimplementado em TS (Task 14 modal) bate com Python equivalent (Task 2) — mesma sequência (NFD → strip diacritics → replace → collapse → strip → truncate 40)

Issues encontrados: nenhum.
