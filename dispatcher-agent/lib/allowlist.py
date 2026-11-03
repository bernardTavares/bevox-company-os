"""Canonical allowlist of Bash tools concedida ao executor `claude -p`.

Único ponto de verdade — `api.py` e `cron.py` importam `default_tools()`.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-29-dispatcher-notifier-tester-decision-and-capability-gating.md §4

Critério pra inclusão: cada item passa em 3 testes:
  1. Reversibilidade — efeito desfeito por git/rm
  2. Sem egress externo (rede pública / API com side-effect / sock host)
  3. Sem privilege escalation efetiva (root, kernel, outros usuários)

NÃO incluir: docker run/exec/volume/network/cp/--privileged/save/load,
curl, wget, ssh, scp, rsync, gh, systemctl, kubectl, aws, gcloud,
terraform, Bash(./*), Bash(/*).
"""
from __future__ import annotations
from pathlib import Path

# File ops e tools básicos (cobertos pelos modelos via Read/Write/Edit/Glob/Grep,
# mas Bash equivalents são úteis quando o agente quer fazer composições shell).
_FILE_OPS = (
    "Read", "Write", "Edit", "Glob", "Grep",
    "Bash(ls:*)", "Bash(cat:*)", "Bash(echo:*)", "Bash(mkdir:*)",
    "Bash(touch:*)", "Bash(rm:*)", "Bash(mv:*)", "Bash(cp:*)",
    "Bash(chmod:*)", "Bash(find:*)", "Bash(realpath:*)",
    "Bash(diff:*)", "Bash(head:*)", "Bash(tail:*)", "Bash(wc:*)",
    "Bash(sort:*)", "Bash(uniq:*)", "Bash(jq:*)",
    "Bash(grep:*)", "Bash(rg:*)",
)

# Git
_GIT = ("Bash(git:*)",)

# Toolchain Node/TypeScript (bevox-site, MC, etc.)
_NODE = (
    "Bash(npm:*)", "Bash(pnpm:*)", "Bash(node:*)", "Bash(npx:*)",
    "Bash(tsc:*)", "Bash(eslint:*)", "Bash(prettier:*)",
)

# Toolchain Python (openclaw scripts, agentes)
_PYTHON = (
    "Bash(python3:*)", "Bash(pip:*)", "Bash(pytest:*)",
    "Bash(ruff:*)", "Bash(mypy:*)", "Bash(black:*)",
)

# Docker — apenas build/inspect (NÃO run/exec/volume/network)
_DOCKER = (
    "Bash(docker build:*)", "Bash(docker images:*)",
    "Bash(docker image:*)", "Bash(docker rmi:*)",
    "Bash(docker inspect:*)", "Bash(docker history:*)",
    "Bash(docker version:*)", "Bash(docker info:*)",
)

# Build
_BUILD = ("Bash(make:*)",)

# Internal CLIs autorizadas
_INTERNAL_CLIS = (
    f"Bash({Path.home()}/.openclaw/clarification-agent/cli.sh:*)",
)


def default_tools() -> str:
    """Retorna allowlist canônica como string CSV pra `claude -p --allowedTools`."""
    return ",".join(
        _FILE_OPS + _GIT + _NODE + _PYTHON + _DOCKER + _BUILD + _INTERNAL_CLIS
    )
