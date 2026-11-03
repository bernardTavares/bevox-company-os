"""skill_config.json — runtime overrides for skill V2 thresholds (W8.P6).

Lives at `~/.openclaw/knowledge-watcher/skill_config.json`. Read by F4
scoring (DOC_TYPE_THRESHOLDS), updated by `/tune` Telegram/CLI command.

Schema v1:
{
  "version": 1,
  "f4_overrides": {
    "doc_type_thresholds": {
      "<doc_type>": <float>
    }
  }
}

Backward compat: missing file or malformed JSON → empty config (no overrides).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


_DEFAULT_PATH = Path(
    os.environ.get(
        "OPENCLAW_KNOWLEDGE_SKILL_CONFIG",
        str(Path.home() / ".openclaw" / "knowledge-watcher" / "skill_config.json"),
    )
)


def _path() -> Path:
    """Re-evaluated each call so tests can override via env."""
    return Path(
        os.environ.get(
            "OPENCLAW_KNOWLEDGE_SKILL_CONFIG",
            str(_DEFAULT_PATH),
        )
    )


def read_config(path: Optional[Path] = None) -> Dict[str, Any]:
    p = Path(path) if path else _path()
    if not p.exists():
        return {"version": 1, "f4_overrides": {}}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "f4_overrides": {}}


def write_config(data: Dict[str, Any], path: Optional[Path] = None) -> None:
    p = Path(path) if path else _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8",
    )
    tmp.replace(p)


def set_doc_type_threshold(doc_type: str, value: float) -> Dict[str, Any]:
    """Apply override + persist atomically. Returns the new config dict."""
    cfg = read_config()
    f4 = cfg.setdefault("f4_overrides", {})
    thresholds = f4.setdefault("doc_type_thresholds", {})
    thresholds[doc_type] = float(value)
    cfg["version"] = 1
    write_config(cfg)
    return cfg


def get_doc_type_thresholds() -> Dict[str, float]:
    return (
        read_config()
        .get("f4_overrides", {})
        .get("doc_type_thresholds", {})
        or {}
    )
