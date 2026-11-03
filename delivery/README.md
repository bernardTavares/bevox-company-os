# OpenClaw Delivery (E5 wave 1)

Operational layer of the Roadmap & Delivery OS for OpenClaw.

**Canonical spec:** `bevox-knowledge/35_specs/2026-04-13-e5-roadmap-delivery-os-wave-1.md`

## Files

- `agent.py` — Delivery Agent: scan logic, parser, dedupe, event writer
- `cli.py` — `openclaw-delivery` subcommands
- `events.jsonl` — append-only event log (SoT operacional)
- `state.json` — projection derived from events.jsonl (regenerable, never edit by hand)
- `tests/` — unittest test suite

## Run tests

    cd ~/.openclaw/delivery
    delivery-venv/bin/python3 -m unittest discover tests -v

## CLI

    openclaw-delivery --help

### release-notes (E6/F4 wave 1)

Generate release notes for a supported repo. Default = stdout (zero
side-effect); `--publish-draft` opt-in creates a GitHub Release **draft**
(never published — operator clicks Publish manually on the GitHub UI).

    openclaw-delivery release-notes <repo> [--since <ref>] [--to <ref>]
                                           [--publish-draft] [--tag <name>]

Examples:

    # stdout-only against last tag
    openclaw-delivery release-notes knowledge-sync

    # explicit range, stdout-only
    openclaw-delivery release-notes knowledge-sync --since 83bed3c

    # create GitHub Release draft
    openclaw-delivery release-notes knowledge-sync --since 83bed3c \
        --publish-draft --tag v0.2.0-draft

Behavior:

- 1 command = 1 repo (no cross-repo aggregation).
- Merge commits are excluded (`git log --no-merges`).
- Commits grouped by conventional prefix: `feat`, `fix`, `docs`,
  `refactor`, `chore`, `test`, plus `other` for unmatched.
- Empty sections are omitted; "Referenced issues" lists deduped `#N`.
- Always emits `release_notes.drafted` on success (incl. stdout-only path
  and empty range with `commit_count=0`).
- `--publish-draft` failure emits `release_notes.draft_publish_failed`
  and exits 1 (markdown still printed to stdout).
- Idempotency: `--publish-draft` with a tag that already has a release
  fails with `tag_exists` (no silent overwrite).
- Tag default (when `--tag` omitted with `--publish-draft`):
  `draft-YYYY-MM-DD-HHMM` UTC.

Supported repos (hardcoded constant `SUPPORTED_REPOS` in `cli.py`):

- `bevox-knowledge` → `bernardTavares/bevox-knowledge`
- `knowledge-sync`  → `bernardTavares/knowledge-sync`

Spec: `bevox-knowledge/35_specs/2026-04-18-e6-f4-release-notes-wave-1.md`

## Service

    systemctl --user status exec-delivery-agent.timer
    journalctl --user -u exec-delivery-agent.service -n 20

## Invariants

1. `state.json` is **always** derived from `events.jsonl` and **never** edited by hand.
2. `events.jsonl` is append-only — never rewrite, never delete lines.
3. Dedupe is by `key` (stable hash), not by `proposal_id` (event UUID).
4. Validator rejects events whose `actor` doesn't match the type's allowed actor.
