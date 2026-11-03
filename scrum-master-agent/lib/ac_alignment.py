"""Heuristica minima de alinhamento entre tipo operacional da task e
linguagem dos acceptance criteria.

Spec: bevox-knowledge/35_specs/openclaw/2026-05-07-task-ac-alignment-by-task-type-v1.md
T-0186 — Phase-1 Task 1.1.

Objetivo: reduzir falso negativo em testes operacionais detectando, ja na
proposal do scrum-master-agent, quando uma task com natureza documental
recebe acceptance criteria escritos em linguagem de runtime (`renderiza`,
`carrega`, `monta`, etc.). O caso motivador foi T-0174.

Escopo desta v1 (per spec §"Fora do escopo desta v1"):
- detectar de forma heuristica, NAO classificacao perfeita;
- nao bloqueia materializacao;
- saida estruturada que aponta task afetada + AC suspeito + sinais.

A integracao desta deteccao ao fluxo de proposal (warnings + rewrite
hints) sai em tasks subsequentes do mesmo epic (Phase-2 / Phase-3).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List


# ============================================================
# Sinais textuais (spec §"Regra minima para o scrum-master-agent v1")
# ============================================================

# Sinais que indicam NATUREZA DOCUMENTAL/CANONICA da task. Buscados no
# `task_subject` (heading da task) e no body extraido. Spec §"Sinais de
# task documental".
DOCUMENTAL_TASK_SIGNALS: List[str] = [
    "consolidar",
    "definir",
    "congelar",
    "modelar",
    "mapear",
    "documentar",
    "registrar",
    "alinhar canonicamente",
]

# Sinais que indicam linguagem FUNCIONAL/RUNTIME no AC, incompativel com
# task documental. Spec §"Sinais de AC funcional/observavel".
RUNTIME_AC_SIGNALS: List[str] = [
    "renderiza",
    "funciona",
    "carrega",
    "monta",
    "exibe",
    "nao regressa",  # variante sem acento
    "não regressa",
    "continua acessivel",
    "continua acessível",
    "seleciona em runtime",
    "valida visualmente",
]


def _normalize(s: str) -> str:
    """Lowercase + collapse de whitespace pra match heuristico estavel."""
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _signals_in_text(text: str, signals: List[str]) -> List[str]:
    """Retorna a lista de signals (lowercase) presentes em `text`.

    Match e por substring whole-word: o sinal e cercado por boundaries
    `\\b` quando ele e uma palavra simples, ou substring puro quando ele
    contem espacos (frase). Mantem heuristica permissiva conforme
    `v1 permanece heuristica e util, sem exigir classificacao perfeita`.
    """
    norm = _normalize(text)
    hits: List[str] = []
    for sig in signals:
        sig_n = sig.lower()
        if " " in sig_n:
            # Multi-palavra: substring direto
            if sig_n in norm:
                hits.append(sig_n)
            continue
        # Palavra simples: word boundary
        if re.search(rf"\b{re.escape(sig_n)}\w*\b", norm):
            hits.append(sig_n)
    return hits


# ============================================================
# Classificacao da task
# ============================================================

def classify_task_type(task: Dict[str, Any]) -> Dict[str, Any]:
    """Heuristica simples: olha task_subject + body p/ sinais documentais.

    Returns:
      {
        'task_type': 'documental' | 'unknown',
        'documental_signals': [str, ...],   # signals encontrados (lowercase)
      }

    v1 NAO tenta distinguir 'implementacao' vs 'qa'. Para o caso T-0174
    basta isolar 'documental': qualquer outra coisa fica `unknown` e nao
    dispara warning.
    """
    haystack_parts: List[str] = []
    if task.get("task_subject"):
        haystack_parts.append(str(task["task_subject"]))
    if task.get("body"):
        haystack_parts.append(str(task["body"]))
    haystack = " \n ".join(haystack_parts)

    signals = _signals_in_text(haystack, DOCUMENTAL_TASK_SIGNALS)
    return {
        "task_type": "documental" if signals else "unknown",
        "documental_signals": signals,
    }


# ============================================================
# Rewrite hints (T-0188)
# ============================================================

# Sinais que cheiram a VALIDACAO/QA (resultado observavel) — quando
# presentes na AC, sugerimos delegacao downstream para QA. Subset de
# RUNTIME_AC_SIGNALS focado em verificacao.
_QA_LIKE_SIGNALS = {
    "nao regressa",
    "não regressa",
    "continua acessivel",
    "continua acessível",
    "valida visualmente",
}

# Sinais que cheiram a COMPORTAMENTO DE RUNTIME (implementacao) —
# quando presentes, sugerimos delegacao p/ task de implementacao.
_IMPL_LIKE_SIGNALS = {
    "renderiza",
    "monta",
    "exibe",
    "carrega",
    "funciona",
    "seleciona em runtime",
}


def _delegation_target(runtime_signals: List[str]) -> str:
    """Decide alvo de delegacao downstream a partir dos sinais runtime
    detectados na AC.

    - Sinais QA-like presentes -> 'QA' (validacao observavel).
    - Senao, se ha sinais de implementacao -> 'implementacao'.
    - Caso ambos -> 'implementacao ou QA' (deixa autor escolher).
    - Default conservador -> 'implementacao ou QA'.
    """
    sigs = {s.lower() for s in runtime_signals}
    has_qa = bool(sigs & _QA_LIKE_SIGNALS)
    has_impl = bool(sigs & _IMPL_LIKE_SIGNALS)
    if has_qa and not has_impl:
        return "QA"
    if has_impl and not has_qa:
        return "implementação"
    return "implementação ou QA"


def suggest_rewrite_hint(
    ac_text: str, runtime_signals: List[str], task_subject: str = "",
) -> str:
    """Gera hint curto de rewrite p/ AC desalinhado em task documental.

    Spec §"Comportamento esperado do scrum-master-agent":
      §B — sugerir reescrita p/ linguagem canonica
        (ex: 'a spec congela que <regra>').
      §C — preservar delegacao downstream
        (ex: 'a validacao de regressao fica delegada a Task 5.1').

    Heuristica v1: nao reescreve a frase — emite template + alvo de
    delegacao escolhido a partir dos sinais runtime presentes. Mantem
    autor humano no loop conforme spec §"Fora do escopo desta v1"
    (sem reescrita automatica obrigatoria).
    """
    target = _delegation_target(runtime_signals or [])
    return (
        f"Reescreva em linguagem canônica "
        f"(ex.: 'a spec congela que <regra>', "
        f"'a política canônica declara <decisão>') "
        f"e delegue a validação observável para uma task downstream "
        f"de {target}."
    )


# ============================================================
# Deteccao de mismatch por AC
# ============================================================

def detect_ac_alignment(task: Dict[str, Any]) -> Dict[str, Any]:
    """Detecta mismatch AC-vs-task-type para uma task parseada.

    Input shape (compativel com `parser.parse_plan_summary` -> tasks[i]):
      {
        'task_num': '1.1',
        'task_subject': str,
        'body': str,                # opcional (usado p/ classificacao)
        'expected': [str, ...],     # acceptance criteria candidates
        ...
      }

    Output shape:
      {
        'task_num': '1.1',
        'task_subject': str,
        'task_type': 'documental' | 'unknown',
        'documental_signals': [str, ...],
        'mismatches': [
          {
            'ac_index': int,            # indice em task['expected']
            'ac_text': str,             # AC original
            'runtime_signals': [str],   # signals que dispararam o flag
            'reason': str,              # mensagem operacional curta
          },
          ...
        ],
        'has_mismatch': bool,
      }

    Apenas tasks classificadas como 'documental' produzem mismatches; a
    v1 nao avalia desalinhamento p/ task de implementacao ou QA (spec
    §"Fora do escopo desta v1": classificacao perfeita).
    """
    cls = classify_task_type(task)
    out: Dict[str, Any] = {
        "task_num": task.get("task_num", ""),
        "task_subject": task.get("task_subject", ""),
        "task_type": cls["task_type"],
        "documental_signals": cls["documental_signals"],
        "mismatches": [],
        "has_mismatch": False,
    }
    if cls["task_type"] != "documental":
        return out

    expected = task.get("expected") or []
    for idx, ac in enumerate(expected):
        ac_str = str(ac)
        runtime_hits = _signals_in_text(ac_str, RUNTIME_AC_SIGNALS)
        # Dedup mantendo ordem
        seen = set()
        runtime_hits = [
            s for s in runtime_hits if not (s in seen or seen.add(s))
        ]
        if not runtime_hits:
            continue
        out["mismatches"].append({
            "ac_index": idx,
            "ac_text": ac_str,
            "runtime_signals": runtime_hits,
            "reason": (
                f"task documental (sinais: {cls['documental_signals']}) "
                f"recebeu AC com linguagem de runtime (sinais: "
                f"{runtime_hits})"
            ),
            "rewrite_hint": suggest_rewrite_hint(
                ac_str, runtime_hits, task.get("task_subject", ""),
            ),
        })
    out["has_mismatch"] = bool(out["mismatches"])
    return out


def detect_ac_alignment_for_plan(parsed: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Roda `detect_ac_alignment` para cada task do plan parseado.

    Input: shape de `parser.parse_plan_summary(text)` (com chave 'tasks').
    Output: lista de dicts (1 por task) na ordem original.

    Helper conveniente p/ integracao com proposer/CLI sem repetir loop
    em quem consome.
    """
    tasks = parsed.get("tasks") or []
    return [detect_ac_alignment(t) for t in tasks]
