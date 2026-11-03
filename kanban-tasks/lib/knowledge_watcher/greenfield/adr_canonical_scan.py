"""adr_canonical_scan — pre-gen scan of 30_adr/<slug>/*.md.

Produces CanonicalAdrScan once per bootstrap run; consumed by workflow
(overlap filter) + ADR generator (prefix + numbering).

W5 spec: 35_specs/_shared/2026-05-09-skill-v2-W5-f3-quality-gates-core.md
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set


_ADR_FILENAME_RE = re.compile(r"^([A-Z]+)-(\d+)-")
_KEYWORD_RE = re.compile(r"\b([a-zA-Z][a-zA-Z0-9-]{3,})\b")
# Stop words (low-information common English/PT)
_STOP_WORDS = {
    "this", "that", "with", "from", "have", "been", "they", "their",
    "para", "como", "esta", "está", "essa", "esse", "isso", "será",
    "decision", "context", "status", "proposta", "aceita", "data",
    "decisor", "origem", "deciders", "title",
}


@dataclass
class CanonicalAdrScan:
    """Resultado do scan único de 30_adr/<slug>/*.md.

    existing_ids: lista de IDs no formato `<PREFIX>-<NNN>`.
    detected_prefix: prefix dominante (auto, config, ou fallback).
    prefix_source: "auto" | "config" | "fallback".
    next_free_number: próximo inteiro livre na sequência detected_prefix.
    topics_index: dict[topic_keyword] → list[adr_id] indexa keywords pra lookup rápido.
    """
    existing_ids: List[str]
    detected_prefix: str
    prefix_source: str
    next_free_number: int
    topics_index: Dict[str, List[str]] = field(default_factory=dict)


def scan_canonical_adrs(
    kb_root: Path,
    slug: str,
    override_prefix: Optional[str] = None,
) -> CanonicalAdrScan:
    """Lê 30_adr/<slug>/*.md uma vez, retorna CanonicalAdrScan.

    Auto-detect prefix:
    - Regex ^([A-Z]+)-(\\d+)- extrai pares (prefix, number) de filenames
    - Threshold majority: 2+ ADRs com mesmo prefix → use majority
    - Senão → fallback "ADR"
    - Override: se override_prefix não-None, sempre wins (source="config")
    """
    adr_dir = kb_root / "30_adr" / slug
    existing_ids: List[str] = []
    prefix_counts: Dict[str, int] = {}
    numbers_by_prefix: Dict[str, List[int]] = {}

    if adr_dir.is_dir():
        for p in sorted(adr_dir.glob("*.md")):
            m = _ADR_FILENAME_RE.match(p.name)
            if not m:
                continue
            prefix, num_str = m.group(1), m.group(2)
            try:
                num = int(num_str)
            except ValueError:
                continue
            adr_id = f"{prefix}-{num_str}"
            existing_ids.append(adr_id)
            prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1
            numbers_by_prefix.setdefault(prefix, []).append(num)

    # Decide prefix
    if override_prefix:
        detected = override_prefix
        source = "config"
    else:
        majority = [(p, c) for p, c in prefix_counts.items() if c >= 2]
        if majority:
            majority.sort(key=lambda x: (-x[1], x[0]))
            detected = majority[0][0]
            source = "auto"
        else:
            detected = "ADR"
            source = "fallback"

    nums = numbers_by_prefix.get(detected, [])
    next_free = (max(nums) + 1) if nums else 1

    return CanonicalAdrScan(
        existing_ids=existing_ids,
        detected_prefix=detected,
        prefix_source=source,
        next_free_number=next_free,
        topics_index=_build_topics_index(adr_dir),
    )


def _topic_keywords(topic_slug: str, topic_title: str) -> List[str]:
    """Derive keywords lower-case (len >= 4) do topic slug + title."""
    parts = re.split(r"[\s\-_/]+", f"{topic_slug} {topic_title}".lower())
    return [p for p in parts if len(p) >= 4 and p not in _STOP_WORDS]


def detect_overlap(
    scan: CanonicalAdrScan,
    topic_slug: str,
    topic_keywords: List[str],
) -> List[str]:
    """Detect overlap entre topic e ADRs canônicos via topics_index.

    Heurística:
    - Conta ocorrências de cada (keyword → ADR id) no topics_index
    - Match se ADR aparece em 2+ keywords distintas, OR
    - Match se 1 keyword 'ofensiva' (ADR aparece 3+ vezes na mesma keyword)

    Returns: ADR ids únicos com match, ordenados.
    """
    if not topic_keywords:
        return []
    matches: Dict[str, int] = {}
    offensive: Set[str] = set()
    for kw in topic_keywords:
        ids_at_kw = scan.topics_index.get(kw, [])
        if not ids_at_kw:
            continue
        unique_ids = set(ids_at_kw)
        for adr_id in unique_ids:
            matches[adr_id] = matches.get(adr_id, 0) + 1
        for adr_id in unique_ids:
            if ids_at_kw.count(adr_id) >= 3:
                offensive.add(adr_id)
    matched = {a for a, c in matches.items() if c >= 2} | offensive
    return sorted(matched)


def compose_adr_filename(
    scan: CanonicalAdrScan,
    topic_slug: str,
    used_numbers_in_run: Set[int],
) -> str:
    """Compose `<prefix>-<NNN>-<topic>.md` para single ADR.

    used_numbers_in_run: caller-tracked Set; mutated em-place pra reservar
    o número escolhido. Permite N topics em paralelo evitarem colisão.
    """
    candidate = scan.next_free_number
    while candidate in used_numbers_in_run:
        candidate += 1
    used_numbers_in_run.add(candidate)
    nnn = f"{candidate:03d}"
    safe_topic = re.sub(r"[^a-z0-9-]", "-", topic_slug.lower()).strip("-")
    return f"{scan.detected_prefix}-{nnn}-{safe_topic}.md"


def _extract_keywords(text: str) -> Set[str]:
    """Extrai keywords lower-case (4+ chars) excluindo stop words."""
    out: Set[str] = set()
    for m in _KEYWORD_RE.findall(text):
        kw = m.lower()
        if kw in _STOP_WORDS:
            continue
        out.add(kw)
    return out


def _build_topics_index(adr_dir: Path) -> Dict[str, List[str]]:
    """Read each ADR body; index keywords → ADR ids."""
    topics_index: Dict[str, List[str]] = {}
    if not adr_dir.is_dir():
        return topics_index
    for p in sorted(adr_dir.glob("*.md")):
        m = _ADR_FILENAME_RE.match(p.name)
        if not m:
            continue
        adr_id = f"{m.group(1)}-{m.group(2)}"
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        for kw in _extract_keywords(text):
            topics_index.setdefault(kw, []).append(adr_id)
    return topics_index
