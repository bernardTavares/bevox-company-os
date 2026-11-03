"""greenfield/ — F3 greenfield doc generator modules.

Spec: bevox-knowledge/35_specs/_shared/2026-05-08-bevox-knowledge-contribute-skill-v2.md §9
Plan: bevox-knowledge/35_specs/_shared/plans/2026-05-09-skill-v2-W4-f3-greenfield-generator-plan.md

Bootstrap completo de documentação canonical pra um projeto. Tiered strategy:
MECÂNICO (factual, $0) → SEMI-AUTO (Haiku) → JUDGMENT (Sonnet paralelo via
claude -p subprocess). 4 hallucination guardrails. Aceite humano sempre via
draft branch + Telegram digest.
"""
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


class Tier(Enum):
    MECANICO = "mecanico"
    SEMI_AUTO = "semi-auto"
    JUDGMENT = "judgment"


@dataclass
class SourceSignals:
    """Factual signals extraídos do repo, sem inferência."""
    slug: str
    repo_root: Path
    has_schema_prisma: bool
    schema_models: List[str]
    package_json: Dict[str, str]
    deps: Dict[str, str]
    main_services: List[str]
    env_vars: List[str]
    has_readme: bool
    readme_text: str
    has_claude_md: bool
    claude_md_text: str
    git_tags: List[str]
    services_count: int
    has_auth_middleware: bool
    has_org_id_pattern: bool
    has_drizzle: bool = False
    has_typeorm: bool = False
    has_mikroorm: bool = False
    has_sequelize: bool = False
    has_mongoose: bool = False
    has_orm: bool = False


@dataclass
class ADRTopic:
    slug: str
    title: str
    rationale: str
    confidence: float


@dataclass
class DocGenResult:
    tier: Tier
    doc_type: str
    relative_path: str
    content: str
    cost_usd: float
    warnings: List[str] = field(default_factory=list)


@dataclass
class BootstrapResult:
    slug: str
    docs_generated: List[DocGenResult]
    total_cost_usd: float
    duration_seconds: float
    skipped_reason: Optional[str] = None
    draft_branch: Optional[str] = None
