# OpenClaw Health (E8 wave 1)

Operational layer of the Infra/Health/Backup Center for OpenClaw.

**Canonical spec:** `bevox-knowledge/35_specs/2026-04-14-e8-infra-health-backup-wave-1.md`

## Files

- `runner.py` — single-file health runner; reads registry, runs checks, writes state.json
- `state.json` — operational snapshot derived from each scan; regenerable, never edited by hand
- `tests/` — unittest suite (stdlib + pyyaml + mocks)
- `health-venv/` — isolated venv with pyyaml

## Registry

Source of truth: `~/bevox-knowledge/20_architecture/health-registry.yml`

Path is fixed in wave 1 — no env var override.

## Run tests

    cd ~/.openclaw/health
    health-venv/bin/python3 -m unittest discover tests -v

## CLI

    openclaw-health-check           # default: scan
    openclaw-health-check --scan    # run scan now
    openclaw-health-check --status  # human summary
    openclaw-health-check --json    # raw state.json
    openclaw-health-check --version # version

## Service

    systemctl --user status openclaw-health-check.timer
    journalctl --user -u openclaw-health-check.service -n 20

## Invariants

1. `state.json` is always JSON-valid, even in degraded scenarios.
2. Runner never raises to systemd — always exit 0.
3. `state.json` is a snapshot derived from runtime reality; not SoT.
4. Registry (`bevox-knowledge/20_architecture/health-registry.yml`) is the canonical inventory SoT.
