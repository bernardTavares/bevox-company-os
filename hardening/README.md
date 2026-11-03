# OpenClaw Hardening (E8/F5 wave 1)

Operational hardening tracker. **NEVER mutates the system. NEVER invokes sudo.**

**Canonical spec:** `bevox-knowledge/35_specs/2026-04-18-e8-f5-hardening-tracker-wave-1.md`
**Registry source of truth:** `bevox-knowledge/20_architecture/hardening-registry.yml`

## Files

- `runner.py` — single-file Python runner (5 check types + aggregation)
- `state.json` — projection derived from registry + check results (regenerable)
- `tests/` — unittest test suite

## Run a scan manually

    HARDENING_REGISTRY_PATH=~/bevox-knowledge/20_architecture/hardening-registry.yml \
        ~/.openclaw/health/health-venv/bin/python ~/.openclaw/hardening/runner.py --scan

Or use the systemd timer (cadence 1h):

    systemctl --user status openclaw-hardening-check.timer
    systemctl --user list-timers openclaw-hardening-check.timer

## CLI flags

- `--scan` (default) — read registry, eval all checks, write `state.json`
- `--status` — print human-readable summary of current `state.json`
- `--json` — print current `state.json` to stdout
- `--version` — print runner schema version + registry version

## Run tests

    cd ~/.openclaw/hardening
    ~/.openclaw/health/health-venv/bin/python -m unittest discover tests -v

(Reuses `health-venv` — no separate venv.)

## Adding a new hardening item

1. Edit `~/bevox-knowledge/20_architecture/hardening-registry.yml`
2. Bump `version` if shape changed
3. Run `~/bevox-knowledge/20_architecture/_tools/render-hardening-registry.py`
4. Commit both files via canonical commit (see `knowledge-sync` skill)

## Closed enums

- `check.type`: `systemd_active` · `command_output_match` · `file_mode_eq` · `file_content_match` · `apt_security_updates_max`
- `severity`: `info` · `warn` · `critical`
- item `status`: `ok` · `degraded` · `critical` · `unknown` · `not_applicable`
- `overall.level`: `ok` · `degraded` · `critical` · `unknown`

## Alert integration

`~/.openclaw/health/alert-notifier.py` reads `state.json` from this module
on each cycle (1min timer) and dispatches Telegram alerts via the same Bot
API used for health alerts. Hardening alerts are prefixed `[hardening]`
and use **silent first-run** to avoid deploy noise (per spec §5.7).

## MC integration

- Endpoint: `GET /api/hardening/state` (read-only)
- UI: section "Hardening Posture (E8/F5)" added to top of `/dashboard/health` page

## Invariants

1. `state.json` is **always** derived from `hardening-registry.yml` and **never** edited by hand
2. Runner **never** mutates the system (zero `systemctl start`, `apt install`, `chmod`)
3. Runner **never** invokes `sudo`
4. Atomic write: tmp file + `os.rename`
5. `not_applicable` items do NOT contribute to `overall.level`
6. Severity declared per-item; `failed` check → `critical` if `severity: critical`, else `degraded`
