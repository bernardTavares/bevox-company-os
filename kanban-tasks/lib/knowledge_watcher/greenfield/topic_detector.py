"""topic_detector.py — Heuristic ADR topic detection from SourceSignals."""
from __future__ import annotations

from typing import List

from lib.knowledge_watcher.greenfield import ADRTopic, SourceSignals


def _has_any(deps: dict, names: list[str]) -> bool:
    return any(n in deps for n in names)


def detect_adr_topics(signals: SourceSignals, *, max_topics: int = 7) -> List[ADRTopic]:
    """Detect candidate ADR topics from SourceSignals via deterministic heuristics.

    Returns up to max_topics, sorted by confidence desc. Dedups overlapping
    topics (e.g., stack-decisions absorbs database-choice + framework-choice).
    """
    topics: List[ADRTopic] = []
    deps = signals.deps

    has_stack = (
        len(signals.schema_models) >= 5
        or signals.has_schema_prisma
        or signals.has_orm
    )
    if has_stack:
        orm_label = (
            "Prisma" if signals.has_schema_prisma
            else "Drizzle" if signals.has_drizzle
            else "TypeORM" if signals.has_typeorm
            else "MikroORM" if signals.has_mikroorm
            else "Sequelize" if signals.has_sequelize
            else "Mongoose" if signals.has_mongoose
            else "no ORM"
        )
        topics.append(ADRTopic(
            slug="stack-decisions",
            title="Stack decisions (DB, ORM, framework, deps top)",
            rationale=f"detected {len(signals.schema_models)} schema models + ORM={orm_label} + {len(deps)} deps",
            confidence=0.85,
        ))

    has_pg = "pg" in deps or "postgres" in deps or signals.has_schema_prisma
    if has_pg and not has_stack:
        topics.append(ADRTopic(
            slug="database-choice",
            title="Escolha de Postgres como datastore primário",
            rationale="Postgres detected via deps OR schema.prisma",
            confidence=0.80,
        ))

    if _has_any(deps, ["pg-boss", "bullmq", "bull"]):
        topics.append(ADRTopic(
            slug="job-queue",
            title="Escolha de job queue library",
            rationale=f"queue lib in deps: {[n for n in ('pg-boss', 'bullmq', 'bull') if n in deps]}",
            confidence=0.85,
        ))

    if signals.has_auth_middleware:
        topics.append(ADRTopic(
            slug="auth-model",
            title="Auth model + middleware design",
            rationale="middleware/auth/ directory present",
            confidence=0.80,
        ))

    if signals.has_org_id_pattern:
        topics.append(ADRTopic(
            slug="tenancy-model",
            title="Multi-tenancy via organizationId shared schema",
            rationale="organizationId pattern detected in schema (>=3 occurrences)",
            confidence=0.85,
        ))

    has_external = (
        _has_any(deps, ["apify-client", "stripe", "whatsapp-web", "twilio"])
        or any("meta" in d.lower() for d in deps)
    )
    if has_external:
        external_deps = [
            d for d in deps
            if d in ("apify-client", "stripe", "whatsapp-web", "twilio")
            or "meta" in d.lower()
        ]
        topics.append(ADRTopic(
            slug="external-providers",
            title="Provider escolha externa (APIs terceiros)",
            rationale=f"external API clients in deps: {external_deps[:3]}",
            confidence=0.75,
        ))

    if _has_any(deps, ["redis", "ioredis"]):
        topics.append(ADRTopic(
            slug="cache-strategy",
            title="Cache strategy (Redis)",
            rationale="redis/ioredis in deps",
            confidence=0.75,
        ))

    has_framework = _has_any(deps, ["@nestjs/core", "fastify", "express", "next"])
    if has_framework and not has_stack:
        framework = next(
            (n for n in ("@nestjs/core", "fastify", "express", "next") if n in deps),
            "unknown",
        )
        topics.append(ADRTopic(
            slug="framework-choice",
            title="Framework backend/web choice",
            rationale=f"primary framework dep: {framework}",
            confidence=0.70,
        ))

    topics.sort(key=lambda t: t.confidence, reverse=True)
    return topics[:max_topics]
