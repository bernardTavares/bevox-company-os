"""Tests for greenfield/signals.py — factual repo reader."""
import json
import subprocess
from pathlib import Path

from lib.knowledge_watcher.greenfield import SourceSignals
from lib.knowledge_watcher.greenfield.signals import read_source_signals


def _init_git(repo: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)


def test_empty_repo_returns_defaults(tmp_path):
    repo = tmp_path / "p"
    repo.mkdir()
    sig = read_source_signals("p", repo)
    assert sig.slug == "p"
    assert sig.repo_root == repo
    assert sig.has_schema_prisma is False
    assert sig.schema_models == []
    assert sig.package_json == {}
    assert sig.deps == {}
    assert sig.main_services == []
    assert sig.env_vars == []
    assert sig.has_readme is False
    assert sig.has_claude_md is False
    assert sig.git_tags == []
    assert sig.services_count == 0
    assert sig.has_auth_middleware is False
    assert sig.has_org_id_pattern is False


def test_schema_prisma_models_extracted(tmp_path):
    repo = tmp_path / "p"
    (repo / "prisma").mkdir(parents=True)
    schema = repo / "prisma" / "schema.prisma"
    schema.write_text("""
model User {
  id String @id
  organizationId String
}

model Workspace {
  organizationId String
  organizationId2 String
}

model Campaign {
  organizationId String
}
""")
    sig = read_source_signals("p", repo)
    assert sig.has_schema_prisma is True
    assert set(sig.schema_models) == {"User", "Workspace", "Campaign"}
    assert sig.has_org_id_pattern is True  # 4 matches >= 3


def test_package_json_parsed(tmp_path):
    repo = tmp_path / "p"
    repo.mkdir()
    (repo / "package.json").write_text(json.dumps({
        "name": "myproj", "version": "1.0.0",
        "dependencies": {"express": "^4", "pg-boss": "^9"},
        "devDependencies": {"vitest": "^1"},
    }))
    sig = read_source_signals("p", repo)
    assert sig.package_json["name"] == "myproj"
    assert sig.deps == {"express": "^4", "pg-boss": "^9", "vitest": "^1"}


def test_main_services_globbed(tmp_path):
    repo = tmp_path / "p"
    services_dir = repo / "apps" / "api" / "src" / "services"
    services_dir.mkdir(parents=True)
    (services_dir / "auth.service.ts").write_text("export {}")
    (services_dir / "user.service.ts").write_text("export {}")
    sig = read_source_signals("p", repo)
    assert sig.services_count == 2
    assert any("auth.service.ts" in s for s in sig.main_services)


def test_env_vars_extracted_from_process_env(tmp_path):
    repo = tmp_path / "p"
    src = repo / "apps" / "api" / "src"
    src.mkdir(parents=True)
    (src / "config.ts").write_text("""
const dbUrl = process.env.DATABASE_URL
const apiKey = process.env.API_KEY
""")
    sig = read_source_signals("p", repo)
    assert "DATABASE_URL" in sig.env_vars
    assert "API_KEY" in sig.env_vars


def test_readme_and_claude_md_truncated(tmp_path):
    repo = tmp_path / "p"
    repo.mkdir()
    (repo / "README.md").write_text("readme content " * 1000)  # 15000 chars
    (repo / "CLAUDE.md").write_text("claude guidance")
    sig = read_source_signals("p", repo, readme_max_chars=100)
    assert sig.has_readme is True
    assert len(sig.readme_text) == 100
    assert sig.has_claude_md is True
    assert sig.claude_md_text == "claude guidance"


def test_git_tags_listed(tmp_path):
    repo = tmp_path / "p"
    repo.mkdir()
    _init_git(repo)
    (repo / "f.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "first"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "tag", "v1.0.0"], cwd=repo, check=True)
    subprocess.run(["git", "tag", "v0.9.0"], cwd=repo, check=True)
    sig = read_source_signals("p", repo)
    assert "v1.0.0" in sig.git_tags
    assert "v0.9.0" in sig.git_tags


def test_has_auth_middleware_detected(tmp_path):
    repo = tmp_path / "p"
    auth_dir = repo / "apps" / "api" / "src" / "middleware" / "auth"
    auth_dir.mkdir(parents=True)
    (auth_dir / "jwt.ts").write_text("export {}")
    sig = read_source_signals("p", repo)
    assert sig.has_auth_middleware is True


def test_org_id_below_threshold_returns_false(tmp_path):
    repo = tmp_path / "p"
    (repo / "prisma").mkdir(parents=True)
    (repo / "prisma" / "schema.prisma").write_text("""
model A { organizationId String }
model B { foo String }
""")
    sig = read_source_signals("p", repo)
    # only 1 match → below threshold (3)
    assert sig.has_org_id_pattern is False


# --- W4.5-T1: non-Prisma ORM detection ---


def test_drizzle_detected_via_dep(tmp_path):
    repo = tmp_path / "p"
    repo.mkdir()
    (repo / "package.json").write_text(json.dumps({
        "name": "p", "dependencies": {"drizzle-orm": "^0.45"}
    }))
    sig = read_source_signals("p", repo)
    assert sig.has_drizzle is True
    assert sig.has_orm is True


def test_drizzle_detected_via_config_file(tmp_path):
    repo = tmp_path / "p"
    repo.mkdir()
    (repo / "drizzle.config.ts").write_text("export default {};")
    sig = read_source_signals("p", repo)
    assert sig.has_drizzle is True


def test_drizzle_detected_via_schema_dir(tmp_path):
    repo = tmp_path / "p"
    schema = repo / "db" / "schema"
    schema.mkdir(parents=True)
    (schema / "users.ts").write_text("import { pgTable } from 'drizzle-orm/pg-core';")
    sig = read_source_signals("p", repo)
    assert sig.has_drizzle is True


def test_drizzle_extracts_table_names_from_schema_files(tmp_path):
    repo = tmp_path / "p"
    schema = repo / "db" / "schema"
    schema.mkdir(parents=True)
    (schema / "users.ts").write_text(
        "export const users = pgTable('users', { id: serial('id').primaryKey() });\n"
        "export const userMeta = pgTable(\"user_meta\", { /* ... */ });"
    )
    (schema / "tenants.ts").write_text(
        "export const tenants = pgTable('tenants', {});"
    )
    sig = read_source_signals("p", repo)
    assert sig.has_drizzle is True
    assert "users" in sig.schema_models
    assert "user_meta" in sig.schema_models
    assert "tenants" in sig.schema_models


def test_typeorm_detected_via_dep(tmp_path):
    repo = tmp_path / "p"
    repo.mkdir()
    (repo / "package.json").write_text(json.dumps({"dependencies": {"typeorm": "^0.3"}}))
    sig = read_source_signals("p", repo)
    assert sig.has_typeorm is True
    assert sig.has_orm is True


def test_typeorm_detected_via_data_source(tmp_path):
    repo = tmp_path / "p"
    src = repo / "src"
    src.mkdir(parents=True)
    (src / "data-source.ts").write_text("export const AppDataSource = ...;")
    sig = read_source_signals("p", repo)
    assert sig.has_typeorm is True


def test_mikroorm_detected_via_dep(tmp_path):
    repo = tmp_path / "p"
    repo.mkdir()
    (repo / "package.json").write_text(json.dumps({
        "dependencies": {"@mikro-orm/core": "^6"},
    }))
    sig = read_source_signals("p", repo)
    assert sig.has_mikroorm is True
    assert sig.has_orm is True


def test_sequelize_detected_via_dep(tmp_path):
    repo = tmp_path / "p"
    repo.mkdir()
    (repo / "package.json").write_text(json.dumps({"dependencies": {"sequelize": "^6"}}))
    sig = read_source_signals("p", repo)
    assert sig.has_sequelize is True


def test_mongoose_detected_via_dep(tmp_path):
    repo = tmp_path / "p"
    repo.mkdir()
    (repo / "package.json").write_text(json.dumps({"dependencies": {"mongoose": "^8"}}))
    sig = read_source_signals("p", repo)
    assert sig.has_mongoose is True


def test_no_orm_when_only_express(tmp_path):
    repo = tmp_path / "p"
    repo.mkdir()
    (repo / "package.json").write_text(json.dumps({"dependencies": {"express": "^4"}}))
    sig = read_source_signals("p", repo)
    assert sig.has_drizzle is False
    assert sig.has_typeorm is False
    assert sig.has_mikroorm is False
    assert sig.has_sequelize is False
    assert sig.has_mongoose is False
    assert sig.has_orm is False


def test_has_orm_aggregate_true_when_prisma(tmp_path):
    repo = tmp_path / "p"
    (repo / "prisma").mkdir(parents=True)
    (repo / "prisma" / "schema.prisma").write_text("model X {}")
    sig = read_source_signals("p", repo)
    assert sig.has_schema_prisma is True
    assert sig.has_orm is True


def test_drizzle_detected_via_mjs_config(tmp_path):
    """`.mjs` config file variant per spec."""
    repo = tmp_path / "p"
    repo.mkdir()
    (repo / "drizzle.config.mjs").write_text("export default {};")
    sig = read_source_signals("p", repo)
    assert sig.has_drizzle is True


def test_sequelize_typescript_alone_does_not_trigger_sequelize(tmp_path):
    """`sequelize-typescript` without bare `sequelize` in deps must NOT fire has_sequelize."""
    repo = tmp_path / "p"
    repo.mkdir()
    (repo / "package.json").write_text(json.dumps({
        "dependencies": {"sequelize-typescript": "^2"},
    }))
    sig = read_source_signals("p", repo)
    assert sig.has_sequelize is False
    assert sig.has_orm is False


def test_multi_orm_signals_all_fire(tmp_path):
    """Drizzle + TypeORM both detected → both flags True; has_orm aggregate True."""
    repo = tmp_path / "p"
    repo.mkdir()
    (repo / "drizzle.config.ts").write_text("export default {};")
    (repo / "package.json").write_text(json.dumps({
        "dependencies": {"typeorm": "^0.3"},
    }))
    sig = read_source_signals("p", repo)
    assert sig.has_drizzle is True
    assert sig.has_typeorm is True
    assert sig.has_orm is True
