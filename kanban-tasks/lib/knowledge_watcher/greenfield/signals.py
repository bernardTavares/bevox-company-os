"""signals.py — read factual signals from repo root."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List

from lib.knowledge_watcher.greenfield import SourceSignals


_MODEL_RE = re.compile(r"^model\s+(\w+)\s*\{", re.MULTILINE)
_ENV_PROCESS_RE = re.compile(r"process\.env\.([A-Z][A-Z0-9_]+)")
_ENV_SCHEMA_RE = re.compile(r"^\s*([A-Z][A-Z0-9_]+):", re.MULTILINE)
_ORG_ID_RE = re.compile(r"organizationId", re.IGNORECASE)
_DRIZZLE_TABLE_RE = re.compile(
    r"\b(pgTable|mysqlTable|sqliteTable)\(['\"]([\w_]+)['\"]"
)


def _safe_read(path: Path, max_chars: int = 10000) -> str:
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except OSError:
        return ""


def _find_schema_prisma(repo_root: Path) -> Path:
    for candidate in (
        repo_root / "prisma" / "schema.prisma",
        repo_root / "apps" / "api" / "prisma" / "schema.prisma",
    ):
        if candidate.is_file():
            return candidate
    for p in repo_root.glob("apps/*/prisma/schema.prisma"):
        return p
    return repo_root / "prisma" / "schema.prisma"


def _find_package_json(repo_root: Path) -> Path:
    for candidate in (repo_root / "package.json", repo_root / "apps" / "api" / "package.json"):
        if candidate.is_file():
            return candidate
    return repo_root / "package.json"


def _read_package_json(path: Path) -> tuple[Dict[str, str], Dict[str, str]]:
    if not path.is_file():
        return ({}, {})
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ({}, {})
    pkg = {
        k: str(v)
        for k, v in data.items()
        if k in ("name", "version", "description") and isinstance(v, (str, int, float))
    }
    deps: Dict[str, str] = {}
    for key in ("dependencies", "devDependencies"):
        d = data.get(key, {})
        if isinstance(d, dict):
            for name, ver in d.items():
                deps[name] = str(ver)
    return (pkg, deps)


def _list_main_services(repo_root: Path) -> List[str]:
    services: List[str] = []
    for pattern in (
        "apps/*/src/services/*.ts",
        "apps/*/src/services/*.js",
        "lib/*/*.py",
        "src/services/*.ts",
    ):
        for p in repo_root.glob(pattern):
            try:
                services.append(str(p.relative_to(repo_root)))
            except ValueError:
                continue
    return sorted(set(services))


def _extract_env_vars(repo_root: Path) -> List[str]:
    vars_set: set[str] = set()
    src_dirs = [repo_root / "apps", repo_root / "src", repo_root / "lib"]
    for src in src_dirs:
        if not src.is_dir():
            continue
        for ext in ("*.ts", "*.js", "*.py"):
            for p in src.rglob(ext):
                if "node_modules" in p.parts or ".venv" in p.parts:
                    continue
                try:
                    txt = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for m in _ENV_PROCESS_RE.finditer(txt):
                    vars_set.add(m.group(1))
    env_ts = repo_root / "apps" / "api" / "src" / "config" / "env.ts"
    if env_ts.is_file():
        try:
            for m in _ENV_SCHEMA_RE.finditer(env_ts.read_text(encoding="utf-8")):
                vars_set.add(m.group(1))
        except OSError:
            pass
    return sorted(vars_set)


def _git_tags(repo_root: Path) -> List[str]:
    if not (repo_root / ".git").is_dir():
        return []
    try:
        out = subprocess.run(
            ["git", "tag", "-l", "--sort=-creatordate"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return []
    tags = [t.strip() for t in out.stdout.splitlines() if t.strip()]
    return tags[:10]


def _has_auth_middleware(repo_root: Path) -> bool:
    if not repo_root.is_dir():
        return False
    candidates = list(repo_root.glob("apps/*/src/middleware/auth/**"))
    candidates += list(repo_root.glob("apps/*/middleware/auth/**"))
    candidates += list(repo_root.glob("middleware/auth/**"))
    return any(p.is_file() for p in candidates)


def _has_org_id_pattern(schema_path: Path) -> bool:
    if not schema_path.is_file():
        return False
    try:
        txt = schema_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return len(_ORG_ID_RE.findall(txt)) >= 3


def _has_drizzle(repo_root: Path, deps: dict) -> bool:
    if "drizzle-orm" in deps:
        return True
    for cfg in ("drizzle.config.ts", "drizzle.config.js", "drizzle.config.mjs"):
        if (repo_root / cfg).is_file():
            return True
    schema_dir = repo_root / "db" / "schema"
    if schema_dir.is_dir() and any(schema_dir.glob("*.ts")):
        return True
    return False


def _has_typeorm(repo_root: Path, deps: dict) -> bool:
    if "typeorm" in deps:
        return True
    if any((repo_root / cfg).is_file() for cfg in ("ormconfig.json", "ormconfig.ts")):
        return True
    for pattern in ("src/data-source.ts", "apps/*/src/data-source.ts"):
        if list(repo_root.glob(pattern)):
            return True
    return False


def _has_mikroorm(repo_root: Path, deps: dict) -> bool:
    return (
        "@mikro-orm/core" in deps
        or (repo_root / "mikro-orm.config.ts").is_file()
    )


def _has_sequelize(deps: dict) -> bool:
    return "sequelize" in deps


def _has_mongoose(deps: dict) -> bool:
    return "mongoose" in deps


def _extract_drizzle_tables(repo_root: Path) -> List[str]:
    schema_dir = repo_root / "db" / "schema"
    if not schema_dir.is_dir():
        return []
    tables: set[str] = set()
    for ts in schema_dir.glob("*.ts"):
        try:
            txt = ts.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in _DRIZZLE_TABLE_RE.finditer(txt):
            tables.add(m.group(2))
    return sorted(tables)


def read_source_signals(
    slug: str,
    repo_root: Path,
    *,
    readme_max_chars: int = 5000,
    claude_md_max_chars: int = 5000,
) -> SourceSignals:
    """Read factual signals from repo. Best-effort: missing files → defaults."""
    schema_path = _find_schema_prisma(repo_root)
    has_schema = schema_path.is_file()
    schema_models: List[str] = []
    if has_schema:
        try:
            txt = schema_path.read_text(encoding="utf-8", errors="replace")
            schema_models = sorted(set(_MODEL_RE.findall(txt)))
        except OSError:
            pass

    pkg_path = _find_package_json(repo_root)
    package_json, deps = _read_package_json(pkg_path)

    has_drizzle = _has_drizzle(repo_root, deps)
    has_typeorm = _has_typeorm(repo_root, deps)
    has_mikroorm = _has_mikroorm(repo_root, deps)
    has_sequelize = _has_sequelize(deps)
    has_mongoose = _has_mongoose(deps)
    has_orm = (
        has_schema
        or has_drizzle
        or has_typeorm
        or has_mikroorm
        or has_sequelize
        or has_mongoose
    )

    if not schema_models and has_drizzle:
        schema_models = _extract_drizzle_tables(repo_root)

    main_services = _list_main_services(repo_root)
    env_vars = _extract_env_vars(repo_root)

    readme_path = repo_root / "README.md"
    has_readme = readme_path.is_file()
    readme_text = _safe_read(readme_path, max_chars=readme_max_chars)

    claude_md_path = repo_root / "CLAUDE.md"
    has_claude_md = claude_md_path.is_file()
    claude_md_text = _safe_read(claude_md_path, max_chars=claude_md_max_chars)

    return SourceSignals(
        slug=slug,
        repo_root=repo_root,
        has_schema_prisma=has_schema,
        schema_models=schema_models,
        package_json=package_json,
        deps=deps,
        main_services=main_services,
        env_vars=env_vars,
        has_readme=has_readme,
        readme_text=readme_text,
        has_claude_md=has_claude_md,
        claude_md_text=claude_md_text,
        git_tags=_git_tags(repo_root),
        services_count=len(main_services),
        has_auth_middleware=_has_auth_middleware(repo_root),
        has_org_id_pattern=_has_org_id_pattern(schema_path),
        has_drizzle=has_drizzle,
        has_typeorm=has_typeorm,
        has_mikroorm=has_mikroorm,
        has_sequelize=has_sequelize,
        has_mongoose=has_mongoose,
        has_orm=has_orm,
    )
