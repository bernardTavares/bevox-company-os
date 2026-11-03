# E10 Detached Reaper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar reaper periódico que fecha o loop spec→done **no modo detached** do dispatcher (que até agora parava em `testing`). Implementação = subcomando `vox dispatcher reap-detached --once` + systemd user timer 60s + persistência do flag `--no-tester` no `dispatch_payload.dispatch_flags`. Reusa 100% de `runner.reap_finished`, `lifecycle.process_finished_session` e `_invoke_tester` existentes (wave-2 + wave-3).

**Architecture:** Novo módulo `~/.openclaw/dispatcher-agent/lib/reaper.py` (Python stdlib + fcntl) implementando varredor sequencial idempotente sob lock global do lote (1 fcntl 1x por tick, ordem determinística por `started_at` ascendente com tie-break por filename). Delta mínimo no `lib/api.py` adicionando `cmd_reap_detached` + persistência `dispatch_flags.no_tester` em ambas branches do `cmd_next`. Templates systemd user units (timer + service oneshot) em `~/.openclaw/dispatcher-agent/systemd/` — **instalação manual pelo Bernard pós-push**, não automatizada. Audit append-only em `~/.openclaw/dispatcher-agent/reaper.jsonl`. Reaper é transparente: zero campo "reaped_by_reaper" no payload; auditoria fica no jsonl + status.json herdado.

**Tech Stack:**
- Python 3 stdlib puro (zero pip install; herda decisão arquitetural §4.1 wave-2)
- fcntl pra lock global (cleanup automático kernel; pattern já usado em F4 wave-3 kanban-tasks)
- systemd user units (.timer + .service) — pattern já usado em E1 knowledge-sync
- JSON append-only pra audit (todos agents anteriores)
- Reuso direto: `runner.reap_finished` + `lifecycle.process_finished_session` + `_invoke_tester` (zero refactor)

**Specs canônicas:**
- Wave-3.5 (esta): `bevox-knowledge/35_specs/2026-04-19-e10-detached-reaper.md` (commit `62923ae`)
- Dependência wave-3 PRD: `bevox-knowledge/35_specs/2026-04-19-e10-tester-agent.md`
- Dependência wave-2 PRD: `bevox-knowledge/35_specs/2026-04-19-e10-dispatcher-and-clarification-agents.md`
- Dependência F4 wave-3: `bevox-knowledge/35_specs/2026-04-19-e5-f4-kanban-dev-lifecycle.md`

**Plans pares (pattern reference):**
- Plan tester-agent: `~/.openclaw/docs/superpowers/plans/2026-04-19-e10-tester-agent-plan.md`

**Constraints operacionais:**
- **Zero pip install** (stdlib + claude CLI)
- Zero novo backend (kanban-tasks host-local + MC inalterados)
- Zero novo agent identitário (reaper é subcomando do dispatcher; ZERO entry no `registry.yml`)
- Zero refactor em `runner.py`/`lifecycle.py`/`_invoke_tester` (reuso direto)
- systemd habilitação = passo manual Bernard pós-push (NÃO automatizar enable/start)
- Single canonical commit cobrindo: delta playbook dispatcher + tracker (spec já canonizada em `62923ae`)
- Spike results wave-2+3 (6 spikes, 2026-04-19) são base técnica — não re-executar

**Guardrails críticos (não regredir):**
1. Reaper **sequencial** + **ordem determinística** (`started_at` ascendente; tie-break filename) sob **lock global do lote** (fcntl 1x por tick, NÃO per-execution)
2. **Idempotente**: `post_action_applied=true` skipa reprocessamento (triplo-check: lifecycle early-return + reaper checa antes + tester não re-invocado se `test_result` presente)
3. **Carve-out `dispatch_flags.no_tester` explícito**:
   - `no_tester=false` (default) → reaper invoca tester via `_invoke_tester`
   - `no_tester=true` → reaper para em `testing`, **NÃO** invoca tester
4. **Reaper transparente**: ZERO campo "reaped_by_reaper" no `dispatch_payload`; audit só em `reaper.jsonl` + `status.json` herdado
5. Lock fcntl com cleanup automático (kernel libera no exit do processo)
6. Segunda instância com `lock_skipped=true exit 0` (NÃO falha)
7. **Sem auto-relaunch**: Bernard sempre via `vox dispatcher relaunch`
8. **Sem auto-dispatch de novas `ready`** (cron-dispatcher wave-4 PRD original — wave separada futura)
9. **Sem multi-task parallel** (one-task-per-project mantido; sequencial dentro de tick)

---

## File Structure

### Host-local — dispatcher-agent (modifica + adiciona)

```
~/.openclaw/dispatcher-agent/
├── cli.sh                          # INALTERADO
├── lib/
│   ├── __init__.py                 # INALTERADO
│   ├── store.py                    # INALTERADO
│   ├── selector.py                 # INALTERADO
│   ├── briefing.py                 # INALTERADO
│   ├── runner.py                   # INALTERADO (reusa reap_finished)
│   ├── lifecycle.py                # INALTERADO (reusa process_finished_session)
│   ├── api.py                      # MODIFICA: cmd_reap_detached + persist dispatch_flags.no_tester
│   └── reaper.py                   # NOVO: scan + lock + sequential + audit
├── systemd/                        # NOVO dir: templates de unit
│   ├── openclaw-reaper.service     # NOVO (template; Bernard copia pra ~/.config/systemd/user/)
│   └── openclaw-reaper.timer       # NOVO (template; idem)
├── briefings/                      # INALTERADO (runtime)
├── executions/                     # INALTERADO (runtime; reaper LE)
├── reaper.jsonl                    # NOVO runtime (append-only audit)
├── reaper.lock                     # NOVO runtime (fcntl lock file)
├── playbook.md                     # MODIFICA: sync da delta canonical (Phase 8.5)
└── README.md                       # MODIFICA: seção "Reaper"
```

### Host-local — backup defensivo

```
~/.openclaw/dispatcher-agent/lib/api.py.pre-reaper.bak  # backup pre-Phase 4
```

### Canonical (bevox-knowledge)

```
bevox-knowledge/
├── 20_architecture/agents/
│   └── dispatcher-agent.md         # MODIFICA: nova seção `## Reaper (wave-3.5)`
├── 35_specs/
│   └── 2026-04-19-e10-detached-reaper.md  # JÁ CANONIZADA (commit 62923ae)
└── 40_roadmap/
    └── delivery-tracker.yml        # MODIFICA: nova wave em E10 (após tester-agent)
```

### Host-local — kanban-tasks + clarification-agent + scrum-master-agent + tester-agent (inalterados)

Nenhuma mudança. Reaper consome apenas:
- `runner.reap_finished` (wave-2; já existe)
- `lifecycle.process_finished_session` (wave-2; já existe; idempotente via `post_action_applied`)
- `_invoke_tester` (wave-3; helper foreground; reuso direto)
- `cli.sh task show <id> --json` (kanban; pra ler `dispatch_flags.no_tester`)

---

## Phase 0: Pre-flight + defensive backup

### Task 0.1: Verificar baseline

**Files:** none (read-only)

- [ ] **Step 1: Confirmar spec canonizada**

```bash
git -C ~/bevox-knowledge log --oneline -1 -- 35_specs/2026-04-19-e10-detached-reaper.md
```

Expected: commit `62923ae` listado.

- [ ] **Step 2: Confirmar wave-2+3 deps presentes**

```bash
ls ~/.openclaw/dispatcher-agent/lib/{runner,lifecycle,api}.py
ls ~/.openclaw/tester-agent/cli.sh
which claude && claude --version 2>&1 | head -2
```

Expected: 3 lib files dispatcher + tester cli.sh + claude CLI disponível.

- [ ] **Step 3: Confirmar reaper.py + cmd_reap_detached AINDA NÃO existem**

```bash
ls ~/.openclaw/dispatcher-agent/lib/reaper.py 2>/dev/null && echo "WARN existe" || echo "OK reaper.py: pendente"
~/.openclaw/dispatcher-agent/cli.sh reap-detached --help 2>&1 | head -3 || echo "OK cmd: pendente"
```

Expected: ambos pendentes.

- [ ] **Step 4: Confirmar `_invoke_tester` existe (heritage wave-3)**

```bash
grep -n "def _invoke_tester" ~/.openclaw/dispatcher-agent/lib/api.py
```

Expected: linha listada (~64).

- [ ] **Step 5: Confirmar `runner.reap_finished` + `lifecycle.process_finished_session` existem**

```bash
grep -n "def reap_finished\|def process_finished_session" ~/.openclaw/dispatcher-agent/lib/{runner,lifecycle}.py
```

Expected: 2 def listadas.

- [ ] **Step 6: systemd user disponível (sanity)**

```bash
systemctl --user --version 2>&1 | head -1 || echo "WARN: systemd user nao disponivel — instalacao manual fica off neste host"
```

Expected: version listada (não-bloqueante; smoke E2E não depende de systemd ativo, só do cmd manual `--once`).

### Task 0.2: Backup state defensivo

**Files:** snapshot

- [ ] **Step 1: Backup kanban + dispatcher api.py**

```bash
mkdir -p ~/.openclaw/backups/kanban-tasks
TS=$(date -Iseconds)
cp ~/.openclaw/kanban-tasks/state.json ~/.openclaw/backups/kanban-tasks/state.json.pre-reaper.$TS
cp ~/.openclaw/kanban-tasks/events.jsonl ~/.openclaw/backups/kanban-tasks/events.jsonl.pre-reaper.$TS
cp ~/.openclaw/dispatcher-agent/lib/api.py ~/.openclaw/dispatcher-agent/lib/api.py.pre-reaper.bak
ls -la ~/.openclaw/backups/kanban-tasks/ | tail -2
ls -la ~/.openclaw/dispatcher-agent/lib/api.py.pre-reaper.bak
```

Expected: 2 backup kanban files + 1 backup api.py.

---

## Phase 1: lib/reaper.py — skeleton + fcntl lock (TDD)

### Task 1.1: Criar systemd templates dir + reaper.py skeleton

**Files:**
- Create: `~/.openclaw/dispatcher-agent/systemd/` (dir vazio por agora)
- Create: `~/.openclaw/dispatcher-agent/lib/reaper.py` (Step 4)

- [ ] **Step 1: Mkdir systemd templates**

```bash
mkdir -p ~/.openclaw/dispatcher-agent/systemd
ls -la ~/.openclaw/dispatcher-agent/systemd
```

Expected: dir vazio listado.

### Task 1.2: TDD — fcntl lock acquire + lock_skipped path

**Files:**
- Create: `/tmp/test_reaper_lock.py` (test fail-first)
- Create: `~/.openclaw/dispatcher-agent/lib/reaper.py` (Step 3 implementação)

- [ ] **Step 1: Escrever testes fail-first**

```bash
cat > /tmp/test_reaper_lock.py <<'EOF'
"""Tests reaper.acquire_lock + LockSkipped behavior. Roda direto via python3."""
import sys, os, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".openclaw" / "dispatcher-agent"))
from lib import reaper


def test_lock_acquire_release(tmpdir):
    lockfile = Path(tmpdir) / "test.lock"
    with reaper.global_lock(lockfile) as acquired:
        assert acquired is True, "primary acquire should succeed"
    # apos saida do context, lock liberado (fcntl auto-release on close)
    print("  OK test_lock_acquire_release")


def test_lock_contention_returns_false(tmpdir):
    """Segunda instancia tentando adquirir = retorna False (lock_skipped)."""
    lockfile = Path(tmpdir) / "test.lock"
    with reaper.global_lock(lockfile) as first_acquired:
        assert first_acquired is True
        # Tenta adquirir de novo dentro do mesmo processo, mesmo lock
        # via fork-like simulado: subprocess
        import subprocess
        script = f"""
import sys
sys.path.insert(0, str({repr(str(Path.home() / '.openclaw' / 'dispatcher-agent'))}))
from lib import reaper
from pathlib import Path
with reaper.global_lock(Path({repr(str(lockfile))})) as acq:
    print('acquired' if acq else 'skipped')
"""
        r = subprocess.run([sys.executable, "-c", script],
                           capture_output=True, text=True, timeout=10)
        assert r.stdout.strip() == "skipped", (
            f"expected skipped, got: {r.stdout.strip()!r} "
            f"stderr: {r.stderr.strip()!r}"
        )
    print("  OK test_lock_contention_returns_false")


def test_lock_releases_on_context_exit(tmpdir):
    """Apos sair do context, lock pode ser readquirido."""
    lockfile = Path(tmpdir) / "test.lock"
    with reaper.global_lock(lockfile) as acq1:
        assert acq1 is True
    # Liberou; readquire deve funcionar
    with reaper.global_lock(lockfile) as acq2:
        assert acq2 is True
    print("  OK test_lock_releases_on_context_exit")


def main():
    tmp = tempfile.mkdtemp()
    try:
        test_lock_acquire_release(tmp)
        test_lock_contention_returns_false(tmp)
        test_lock_releases_on_context_exit(tmp)
        print("ALL OK")
    finally:
        import shutil; shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
EOF
```

- [ ] **Step 2: Rodar — deve FAIL (modulo nao existe)**

```bash
python3 /tmp/test_reaper_lock.py 2>&1 | tail -3 || true
```

Expected: `ImportError: cannot import name 'reaper'`.

- [ ] **Step 3: Implementar reaper.py com lock**

```bash
cat > ~/.openclaw/dispatcher-agent/lib/reaper.py <<'EOF'
"""Reaper: varredor periodico de executions detached.

Wave-3.5 do PRD orchestration. Fecha loop detached que para em testing
(limitacao §10.2 da spec do tester-agent).

Decisoes travadas (§2 da spec detached-reaper):
- Sequencial + ordem deterministica (started_at asc, tie-break filename)
- Lock global do lote (fcntl 1x por tick)
- Idempotente (post_action_applied=true skipa)
- Carve-out dispatch_flags.no_tester explicito
- Transparente (audit so em reaper.jsonl)
"""

import contextlib
import fcntl
import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from . import store

ROOT = Path(os.path.expanduser("~/.openclaw/dispatcher-agent"))
REAPER_JSONL = ROOT / "reaper.jsonl"
REAPER_LOCK = ROOT / "reaper.lock"
EXECUTIONS_DIR = ROOT / "executions"


class ReaperError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


@contextlib.contextmanager
def global_lock(lockfile: Path) -> Iterator[bool]:
    """fcntl exclusive lock. Yields True se adquirido, False se contention.

    fcntl libera automaticamente no close do file descriptor (kernel).
    Nao bloqueante (LOCK_NB): segunda instancia retorna False imediato.
    """
    lockfile.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lockfile), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield True
        except (BlockingIOError, OSError):
            yield False
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(fd)


def make_tick_id() -> str:
    return f"{store.now_iso()}-{uuid.uuid4().hex[:8]}"
EOF
```

- [ ] **Step 4: Rodar testes — devem passar**

```bash
python3 /tmp/test_reaper_lock.py
```

Expected: `ALL OK` com 3 OKs.

- [ ] **Step 5: Cleanup test**

```bash
rm /tmp/test_reaper_lock.py
```

---

## Phase 2: lib/reaper.py — scan + ordering determinístico (TDD)

### Task 2.1: TDD ordering por started_at + tie-break filename

**Files:**
- Create: `/tmp/test_reaper_scan.py`
- Modify: `~/.openclaw/dispatcher-agent/lib/reaper.py` (adiciona `scan_executions`)

- [ ] **Step 1: Escrever testes fail-first**

```bash
cat > /tmp/test_reaper_scan.py <<'EOF'
"""Tests reaper.scan_executions ordering deterministico."""
import sys, os, json, tempfile, shutil
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".openclaw" / "dispatcher-agent"))
from lib import reaper


def write_status(d: Path, task_id: str, started_at: str,
                 finished_at=None, post_action_applied=False):
    p = d / f"{task_id}.status.json"
    p.write_text(json.dumps({
        "task_id": task_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "post_action_applied": post_action_applied,
    }))
    return p


def test_scan_orders_by_started_at_asc(tmpdir):
    d = Path(tmpdir)
    write_status(d, "T-0003", "2026-04-19T10:00:30Z")
    write_status(d, "T-0001", "2026-04-19T10:00:10Z")
    write_status(d, "T-0002", "2026-04-19T10:00:20Z")
    result = reaper.scan_executions(d)
    ids = [e["task_id"] for e in result]
    assert ids == ["T-0001", "T-0002", "T-0003"], ids
    print("  OK test_scan_orders_by_started_at_asc")


def test_scan_tie_break_by_filename(tmpdir):
    """Mesmo started_at: tie-break pelo nome do arquivo (task_id alfabetico)."""
    d = Path(tmpdir)
    ts = "2026-04-19T10:00:00Z"
    write_status(d, "T-0099", ts)
    write_status(d, "T-0001", ts)
    write_status(d, "T-0050", ts)
    result = reaper.scan_executions(d)
    ids = [e["task_id"] for e in result]
    assert ids == ["T-0001", "T-0050", "T-0099"], ids
    print("  OK test_scan_tie_break_by_filename")


def test_scan_skips_corrupt_files(tmpdir):
    d = Path(tmpdir)
    write_status(d, "T-0001", "2026-04-19T10:00:00Z")
    (d / "T-CORRUPT.status.json").write_text("not json {{{")
    result = reaper.scan_executions(d)
    ids = [e["task_id"] for e in result]
    assert ids == ["T-0001"], ids
    print("  OK test_scan_skips_corrupt_files")


def test_scan_empty_dir(tmpdir):
    d = Path(tmpdir)
    result = reaper.scan_executions(d)
    assert result == []
    print("  OK test_scan_empty_dir")


def test_scan_missing_dir(tmpdir):
    d = Path(tmpdir) / "does_not_exist"
    result = reaper.scan_executions(d)
    assert result == []
    print("  OK test_scan_missing_dir")


def test_scan_ignores_non_status_json(tmpdir):
    d = Path(tmpdir)
    write_status(d, "T-0001", "2026-04-19T10:00:00Z")
    (d / "T-0001.log").write_text("logs")
    (d / "random.txt").write_text("x")
    result = reaper.scan_executions(d)
    ids = [e["task_id"] for e in result]
    assert ids == ["T-0001"], ids
    print("  OK test_scan_ignores_non_status_json")


def main():
    tmp = tempfile.mkdtemp()
    try:
        test_scan_orders_by_started_at_asc(tmp)
        test_scan_tie_break_by_filename(tmp)
        test_scan_skips_corrupt_files(tmp)
        test_scan_empty_dir(tmp)
        test_scan_missing_dir(tmp)
        test_scan_ignores_non_status_json(tmp)
        print("ALL OK")
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
EOF
```

- [ ] **Step 2: Rodar — FAIL (scan_executions nao existe)**

```bash
python3 /tmp/test_reaper_scan.py 2>&1 | tail -3 || true
```

Expected: `AttributeError: module 'lib.reaper' has no attribute 'scan_executions'`.

- [ ] **Step 3: Adicionar scan_executions em reaper.py**

```bash
cat >> ~/.openclaw/dispatcher-agent/lib/reaper.py <<'EOF'


def scan_executions(executions_dir: Path) -> List[Dict[str, Any]]:
    """Le todos os <task_id>.status.json sob executions_dir.

    Retorna lista ordenada deterministicamente:
    - primario: started_at ascendente (FIFO de quem comecou primeiro)
    - tie-break: nome do arquivo ascendente (alfabetico)

    Ignora corrupt files (JSON invalido). Dir inexistente -> [].
    """
    if not executions_dir.exists() or not executions_dir.is_dir():
        return []
    out: List[Dict[str, Any]] = []
    for p in executions_dir.iterdir():
        if not p.is_file() or not p.name.endswith(".status.json"):
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        data["_status_path"] = str(p)
        data["_status_filename"] = p.name
        out.append(data)
    # Sort: primary started_at, secondary filename
    out.sort(key=lambda d: (d.get("started_at") or "", d.get("_status_filename") or ""))
    return out
EOF
```

- [ ] **Step 4: Rodar testes — devem passar**

```bash
python3 /tmp/test_reaper_scan.py
```

Expected: `ALL OK` com 6 OKs.

- [ ] **Step 5: Cleanup**

```bash
rm /tmp/test_reaper_scan.py
```

---

## Phase 3: lib/reaper.py — process loop + audit jsonl

### Task 3.1: TDD classify_execution (already_reaped vs still_running vs needs_reap)

**Files:**
- Create: `/tmp/test_reaper_classify.py`
- Modify: `~/.openclaw/dispatcher-agent/lib/reaper.py` (adiciona `classify_execution`)

- [ ] **Step 1: Escrever testes fail-first**

```bash
cat > /tmp/test_reaper_classify.py <<'EOF'
import sys, tempfile, shutil
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".openclaw" / "dispatcher-agent"))
from lib import reaper


def make(finished_at=None, post_action_applied=False, pid=99999999):
    return {
        "task_id": "T-X",
        "pid": pid,
        "finished_at": finished_at,
        "post_action_applied": post_action_applied,
    }


def test_classify_already_reaped():
    s = make(finished_at="2026-04-19T10:00:00Z", post_action_applied=True)
    assert reaper.classify_execution(s) == "already_reaped"
    print("  OK test_classify_already_reaped")


def test_classify_finished_but_no_post_action():
    """finished_at set mas post_action nao aplicado: precisa lifecycle."""
    s = make(finished_at="2026-04-19T10:00:00Z", post_action_applied=False)
    assert reaper.classify_execution(s) == "needs_lifecycle"
    print("  OK test_classify_finished_but_no_post_action")


def test_classify_still_running():
    """finished_at=None + processo ainda alive -> still_running."""
    import os
    s = make(finished_at=None, pid=os.getpid())  # pid de python eh alive
    assert reaper.classify_execution(s) == "still_running"
    print("  OK test_classify_still_running")


def test_classify_needs_reap():
    """finished_at=None + processo morto -> needs_reap."""
    s = make(finished_at=None, pid=99999999)  # pid invalido
    assert reaper.classify_execution(s) == "needs_reap"
    print("  OK test_classify_needs_reap")


def test_classify_no_pid():
    """sem pid + sem finished_at -> needs_reap (defensivo)."""
    s = {"task_id": "T-X", "pid": None, "finished_at": None}
    assert reaper.classify_execution(s) == "needs_reap"
    print("  OK test_classify_no_pid")


def main():
    test_classify_already_reaped()
    test_classify_finished_but_no_post_action()
    test_classify_still_running()
    test_classify_needs_reap()
    test_classify_no_pid()
    print("ALL OK")


if __name__ == "__main__":
    main()
EOF
```

- [ ] **Step 2: Rodar — FAIL**

```bash
python3 /tmp/test_reaper_classify.py 2>&1 | tail -3 || true
```

Expected: `AttributeError: module 'lib.reaper' has no attribute 'classify_execution'`.

- [ ] **Step 3: Adicionar classify_execution**

```bash
cat >> ~/.openclaw/dispatcher-agent/lib/reaper.py <<'EOF'


def classify_execution(status: Dict[str, Any]) -> str:
    """Classifica status entry pra decidir acao do reaper.

    Retornos:
    - 'already_reaped': finished_at != None E post_action_applied == True (skip)
    - 'needs_lifecycle': finished_at != None E post_action_applied == False
                        (ja foi reapado mas lifecycle nao aplicou — re-tenta)
    - 'still_running': finished_at == None E processo alive
    - 'needs_reap': finished_at == None E processo morto/sem pid
    """
    if status.get("finished_at") is not None:
        if status.get("post_action_applied"):
            return "already_reaped"
        return "needs_lifecycle"
    pid = status.get("pid")
    if pid and _pid_alive(pid):
        return "still_running"
    return "needs_reap"


def _pid_alive(pid: int) -> bool:
    """Check if pid esta alive via os.kill(pid, 0). Compat com runner.is_session_alive."""
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False
EOF
```

- [ ] **Step 4: Run tests — devem passar**

```bash
python3 /tmp/test_reaper_classify.py
```

Expected: `ALL OK` com 5 OKs.

- [ ] **Step 5: Cleanup**

```bash
rm /tmp/test_reaper_classify.py
```

### Task 3.2: Audit jsonl writer

**Files:**
- Modify: `~/.openclaw/dispatcher-agent/lib/reaper.py` (adiciona `append_audit`)

- [ ] **Step 1: Adicionar append_audit**

```bash
cat >> ~/.openclaw/dispatcher-agent/lib/reaper.py <<'EOF'


def append_audit(entry: Dict[str, Any]) -> None:
    """Append linha JSONL atomico em reaper.jsonl."""
    REAPER_JSONL.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    # O(append) atomico em POSIX pra writes <PIPE_BUF (4KB linux); nossas linhas <1KB
    with open(REAPER_JSONL, "a", encoding="utf-8") as f:
        f.write(line)
EOF
```

- [ ] **Step 2: Sanity import + smoke append**

```bash
cd ~/.openclaw/dispatcher-agent && PYTHONPATH=. python3 <<'PY'
from lib import reaper
import json, os
entry = {"tick_id": "smoke-test", "trigger": "test"}
reaper.append_audit(entry)
# Verify last line is our entry
with open(reaper.REAPER_JSONL, "r") as f:
    last = f.readlines()[-1]
parsed = json.loads(last)
assert parsed["tick_id"] == "smoke-test", parsed
print(f"OK audit: {parsed}")
# Cleanup smoke entry — truncate to drop last line
with open(reaper.REAPER_JSONL, "r") as f:
    lines = f.readlines()
with open(reaper.REAPER_JSONL, "w") as f:
    f.writelines(lines[:-1])
print(f"cleaned up; remaining {len(lines)-1} lines")
PY
```

Expected: `OK audit: {...}` + cleanup confirm.

### Task 3.3: process_executions — pipeline reap + lifecycle + tester (respeitando no_tester)

**Files:**
- Modify: `~/.openclaw/dispatcher-agent/lib/reaper.py` (adiciona `process_executions` + `run_tick`)

- [ ] **Step 1: Adicionar process_executions + run_tick**

```bash
cat >> ~/.openclaw/dispatcher-agent/lib/reaper.py <<'EOF'


def _read_dispatch_flags_no_tester(task_id: str) -> bool:
    """Le dispatch_payload.dispatch_flags.no_tester via kanban CLI.

    Retorna False (default) se ausente ou erro.
    """
    import subprocess
    KANBAN_CLI = "~/.openclaw/kanban-tasks/cli.sh"
    try:
        r = subprocess.run(
            [KANBAN_CLI, "task", "show", task_id, "--json"],
            capture_output=True, text=True, check=False, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if r.returncode != 0:
        return False
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return False
    task = data.get("task") or {}
    dp = task.get("dispatch_payload") or {}
    flags = dp.get("dispatch_flags") or {}
    return bool(flags.get("no_tester"))


def process_executions(
    entries: List[Dict[str, Any]], dry_run: bool = False,
) -> Dict[str, Any]:
    """Processa lote sequencialmente. Retorna stats agregados pra audit.

    Reusa runner.reap_finished + lifecycle.process_finished_session +
    api._invoke_tester (todos existentes wave-2+3).
    """
    from . import runner, lifecycle
    from .api import _invoke_tester  # heritage wave-3

    stats = {
        "considered_executions": len(entries),
        "skipped_already_reaped": 0,
        "skipped_still_running": 0,
        "reaped_count": 0,
        "tester_invoked_count": 0,
        "actions_per_task": [],
    }

    for entry in entries:
        task_id = entry.get("task_id")
        if not task_id:
            continue
        cls = classify_execution(entry)
        actions: List[Dict[str, Any]] = []

        if cls == "already_reaped":
            stats["skipped_already_reaped"] += 1
            continue
        if cls == "still_running":
            stats["skipped_still_running"] += 1
            continue

        if dry_run:
            actions.append({
                "task_id": task_id, "stage": "dry_run",
                "outcome": f"would_handle_{cls}",
                "test_run_id": None,
            })
            stats["actions_per_task"].extend(actions)
            continue

        # needs_reap: chama runner.reap_finished pra detectar exit + atualizar status.json
        if cls == "needs_reap":
            try:
                reaped_status = runner.reap_finished(task_id)
            except Exception as e:
                actions.append({
                    "task_id": task_id, "stage": "reaped",
                    "outcome": f"reap_error:{type(e).__name__}",
                    "test_run_id": None,
                })
                stats["actions_per_task"].extend(actions)
                continue
            if reaped_status is None or reaped_status.get("finished_at") is None:
                # Ainda esperando exit; tenta proximo tick
                actions.append({
                    "task_id": task_id, "stage": "reaped",
                    "outcome": "not_yet_finished",
                    "test_run_id": None,
                })
                stats["actions_per_task"].extend(actions)
                continue
            stats["reaped_count"] += 1
            actions.append({
                "task_id": task_id, "stage": "reaped",
                "outcome": "exit_detected",
                "test_run_id": None,
            })

        # needs_lifecycle (incl. fall-through de needs_reap acima): roda lifecycle
        try:
            lc_result = lifecycle.process_finished_session(task_id)
            post_action = lc_result.get("post_action") or "unknown"
            actions.append({
                "task_id": task_id, "stage": "lifecycle_applied",
                "outcome": post_action,
                "test_run_id": None,
            })
        except Exception as e:
            actions.append({
                "task_id": task_id, "stage": "lifecycle_applied",
                "outcome": f"lifecycle_error:{type(e).__name__}",
                "test_run_id": None,
            })
            stats["actions_per_task"].extend(actions)
            continue

        # Se virou testing E no_tester=False, invoca tester
        if "auto_moved_to_testing" in post_action:
            no_tester = _read_dispatch_flags_no_tester(task_id)
            if no_tester:
                actions.append({
                    "task_id": task_id, "stage": "tester_invoked",
                    "outcome": "skipped_no_tester_flag",
                    "test_run_id": None,
                })
            else:
                invoked, summary = _invoke_tester(task_id, json_mode=True)
                if invoked:
                    stats["tester_invoked_count"] += 1
                actions.append({
                    "task_id": task_id, "stage": "tester_invoked",
                    "outcome": (summary.get("decision") or "tester_no_decision")
                    if invoked else "tester_invoke_failed",
                    "test_run_id": summary.get("test_run_id"),
                })

        stats["actions_per_task"].extend(actions)

    return stats


def run_tick(
    trigger: str = "manual", dry_run: bool = False,
    executions_dir: Optional[Path] = None,
    lockfile: Optional[Path] = None,
) -> Dict[str, Any]:
    """Tick completo do reaper: lock + scan + process + audit.

    Returns audit entry dict (tambem appended em reaper.jsonl).
    """
    if executions_dir is None:
        executions_dir = EXECUTIONS_DIR
    if lockfile is None:
        lockfile = REAPER_LOCK

    tick_id = make_tick_id()
    started_at = store.now_iso()

    with global_lock(lockfile) as acquired:
        if not acquired:
            entry = {
                "tick_id": tick_id, "tick_started_at": started_at,
                "tick_finished_at": store.now_iso(), "trigger": trigger,
                "considered_executions": 0,
                "skipped_already_reaped": 0,
                "skipped_still_running": 0,
                "reaped_count": 0,
                "tester_invoked_count": 0,
                "actions_per_task": [],
                "lock_acquired": False,
                "lock_skipped": True,
                "dry_run": dry_run,
            }
            append_audit(entry)
            return entry

        entries = scan_executions(executions_dir)
        stats = process_executions(entries, dry_run=dry_run)
        entry = {
            "tick_id": tick_id, "tick_started_at": started_at,
            "tick_finished_at": store.now_iso(), "trigger": trigger,
            "lock_acquired": True, "lock_skipped": False,
            "dry_run": dry_run,
            **stats,
        }
        append_audit(entry)
        return entry
EOF
```

- [ ] **Step 2: Sanity import + smoke run_tick (sem executions reais)**

```bash
cd ~/.openclaw/dispatcher-agent && PYTHONPATH=. python3 <<'PY'
from lib import reaper
import tempfile, json
from pathlib import Path

# Empty executions dir
tmp = tempfile.mkdtemp()
exec_dir = Path(tmp) / "executions"
exec_dir.mkdir()
lockfile = Path(tmp) / "test.lock"

result = reaper.run_tick(
    trigger="smoke", dry_run=False,
    executions_dir=exec_dir, lockfile=lockfile,
)
assert result["lock_acquired"] is True
assert result["considered_executions"] == 0
assert result["reaped_count"] == 0
print(f"OK empty tick: {result['tick_id'][:30]}...")

# Cleanup tmp
import shutil; shutil.rmtree(tmp)
PY
```

Expected: `OK empty tick: ...`.

- [ ] **Step 3: Verificar audit foi appended em reaper.jsonl global (smoke)**

```bash
ls -la ~/.openclaw/dispatcher-agent/reaper.jsonl 2>/dev/null && echo "(exists)" || echo "(no global audit; smoke usou tmp)"
```

Expected: arquivo pode ou não existir (smoke acima rodou audit no global path mesmo com lockfile tmp; isso é esperado pois `append_audit` usa REAPER_JSONL global).

---

## Phase 4: dispatcher api.py delta — cmd_reap_detached + persist dispatch_flags.no_tester

### Task 4.1: Adicionar persistência dispatch_flags.no_tester em cmd_next

**Files:**
- Modify: `~/.openclaw/dispatcher-agent/lib/api.py`

- [ ] **Step 1: Localizar bloco metadata em cmd_next**

```bash
grep -n "metadata = {" ~/.openclaw/dispatcher-agent/lib/api.py
```

Expected: linha listada (~93).

- [ ] **Step 2: Adicionar dispatch_flags ao metadata initial**

Edita `~/.openclaw/dispatcher-agent/lib/api.py` localizando o bloco `metadata = { ... }` em `cmd_next` (após `lifecycle_lib.move_to_in_progress(task["id"])`):

```python
    ts = store.now_iso()
    metadata = {
        "dispatched_at": ts, "dispatcher_actor": "dispatcher",
        "briefing_path": str(bpath),
        "dispatch_mode": "foreground" if args.foreground else "detach",
        "dispatch_flags": {
            "no_tester": bool(args.no_tester),
        },
    }
```

Use Edit tool.

### Task 4.2: Adicionar cmd_reap_detached + subparser reap-detached

**Files:**
- Modify: `~/.openclaw/dispatcher-agent/lib/api.py`

- [ ] **Step 1: Adicionar cmd_reap_detached antes de build_parser**

Localiza `def build_parser():` em `~/.openclaw/dispatcher-agent/lib/api.py`. Insere ANTES dele:

```python
def cmd_reap_detached(args: argparse.Namespace) -> int:
    """Wave-3.5: reap loop unico (--once). Sem daemon mode."""
    from . import reaper as reaper_lib
    trigger = "manual"
    # Detecta se foi disparado pelo systemd (env INVOCATION_ID setado)
    if os.environ.get("INVOCATION_ID"):
        trigger = "systemd_timer"
    try:
        result = reaper_lib.run_tick(trigger=trigger, dry_run=args.dry_run)
    except reaper_lib.ReaperError as e:
        return _err(e.detail, e.code, args.json)
    if args.json:
        _print(result, True)
    else:
        if result.get("lock_skipped"):
            print(f"reap-detached: lock_skipped (other instance running) tick={result['tick_id'][:30]}")
        else:
            n = result["considered_executions"]
            r = result["reaped_count"]
            t = result["tester_invoked_count"]
            sa = result["skipped_already_reaped"]
            sr = result["skipped_still_running"]
            mode = "DRY-RUN" if args.dry_run else "applied"
            print(f"reap-detached [{mode}]: considered={n} reaped={r} tester_invoked={t} skipped_already={sa} skipped_running={sr}")
            for a in result.get("actions_per_task", []):
                print(f"  {a['task_id']}: {a['stage']} -> {a['outcome']}")
    return EXIT_OK
```

E precisa importar `os` no topo se ainda não. Verificar:

```bash
grep "^import os" ~/.openclaw/dispatcher-agent/lib/api.py
```

Se não aparecer, adicionar `import os` ao bloco de imports.

- [ ] **Step 2: Adicionar subparser em build_parser**

Localiza dentro de `build_parser()` (após o subparser `relaunch`):

```python
    rp = leaf(sub, "reap-detached")
    rp.add_argument("--once", action="store_true",
                    help="Roda uma passada e sai (default; usado pelo systemd timer).")
    rp.add_argument("--dry-run", action="store_true",
                    help="Lista o que faria, sem agir.")
    rp.set_defaults(func=cmd_reap_detached)
```

Use Edit tool.

- [ ] **Step 3: Sanity CLI help**

```bash
~/.openclaw/dispatcher-agent/cli.sh reap-detached --help 2>&1 | head -10
```

Expected: usage com `--once`, `--dry-run`, `--json`.

- [ ] **Step 4: Smoke reap-detached --dry-run em sandbox vazio**

```bash
~/.openclaw/dispatcher-agent/cli.sh reap-detached --dry-run 2>&1 | head -3
```

Expected: `reap-detached [DRY-RUN]: considered=N ...` (N depende de quantas executions já existem do trabalho passado).

- [ ] **Step 5: Verify persist dispatch_flags via parse_args sanity**

```bash
cd ~/.openclaw/dispatcher-agent && PYTHONPATH=. python3 <<'PY'
from lib.api import build_parser
p = build_parser()
# verify reap-detached parses
args = p.parse_args(["reap-detached", "--dry-run"])
assert args.dry_run is True
assert hasattr(args, "func")
# verify cmd_next still has --no-tester
args = p.parse_args(["next", "--launch", "--no-tester"])
assert args.no_tester is True
print("OK parser")
PY
```

Expected: `OK parser`.

---

## Phase 5: systemd unit templates (NÃO instalados; só shipped)

### Task 5.1: Criar templates .timer + .service

**Files:**
- Create: `~/.openclaw/dispatcher-agent/systemd/openclaw-reaper.service`
- Create: `~/.openclaw/dispatcher-agent/systemd/openclaw-reaper.timer`

- [ ] **Step 1: Criar service template**

```bash
cat > ~/.openclaw/dispatcher-agent/systemd/openclaw-reaper.service <<'EOF'
[Unit]
Description=OpenClaw dispatcher reaper (detached completion, wave-3.5)
After=default.target

[Service]
Type=oneshot
ExecStart=%h/.openclaw/dispatcher-agent/cli.sh reap-detached --once
Nice=5
EOF
```

- [ ] **Step 2: Criar timer template**

```bash
cat > ~/.openclaw/dispatcher-agent/systemd/openclaw-reaper.timer <<'EOF'
[Unit]
Description=OpenClaw reaper timer (60s tick, wave-3.5)

[Timer]
OnBootSec=30s
OnUnitActiveSec=60s
AccuracySec=5s
Unit=openclaw-reaper.service

[Install]
WantedBy=timers.target
EOF
```

- [ ] **Step 3: Verificar templates**

```bash
ls -la ~/.openclaw/dispatcher-agent/systemd/
cat ~/.openclaw/dispatcher-agent/systemd/openclaw-reaper.service
echo "---"
cat ~/.openclaw/dispatcher-agent/systemd/openclaw-reaper.timer
```

Expected: 2 files listados; conteúdo conforme acima.

**IMPORTANTE:** estes templates **NÃO são instalados** automaticamente. Bernard copia pra `~/.config/systemd/user/` e habilita manualmente pós-push (Phase 8 README documenta os comandos).

---

## Phase 6: README atualizado com seção Reaper

### Task 6.1: Append seção Reaper no README

**Files:**
- Modify: `~/.openclaw/dispatcher-agent/README.md`

- [ ] **Step 1: Append seção**

```bash
cat >> ~/.openclaw/dispatcher-agent/README.md <<'EOF'

---

## Reaper (wave-3.5)

Subcomando `reap-detached` fecha o loop **detached** que para em
`testing` (limitacao §10.2 spec do tester-agent). Reusa
`runner.reap_finished` + `lifecycle.process_finished_session` +
`_invoke_tester` (zero refactor).

```bash
vox dispatcher reap-detached --once          # roda uma passada
vox dispatcher reap-detached --once --json   # output estruturado
vox dispatcher reap-detached --dry-run       # lista o que faria, sem agir
```

**Garantias (§2 da spec detached-reaper):**
- Sequencial + ordem deterministica (`started_at` asc, tie-break filename)
- Lock global do lote (fcntl 1x por tick — segunda instancia exit 0
  com `lock_skipped=true`)
- Idempotente (`post_action_applied=true` skipa)
- Carve-out `dispatch_flags.no_tester`:
  - `false` (default) → reaper invoca tester
  - `true` → reaper para em testing, NAO invoca tester
- Transparente: zero campo "reaped_by_reaper" no payload; audit em
  `reaper.jsonl`

**Habilitacao systemd (manual pos-push):**

```bash
# 1. Copia templates
mkdir -p ~/.config/systemd/user
cp ~/.openclaw/dispatcher-agent/systemd/openclaw-reaper.{service,timer} \
   ~/.config/systemd/user/

# 2. Reload + enable + start
systemctl --user daemon-reload
systemctl --user enable --now openclaw-reaper.timer

# 3. Verificar
systemctl --user list-timers | grep reaper
journalctl --user -u openclaw-reaper -f       # tail logs

# Desabilitar (se precisar):
systemctl --user disable --now openclaw-reaper.timer
```

**NAO eh cron-dispatcher.** Reaper SO age sobre executions ja
lancadas via `dispatcher next --launch`. Auto-dispatch de novas tasks
`ready` continua fora desta wave (cron-dispatcher = wave-4 PRD original,
separada).

**Audit:** `~/.openclaw/dispatcher-agent/reaper.jsonl` (append-only;
uma linha por tick).

**Spec canonica:**
- `bevox-knowledge/35_specs/2026-04-19-e10-detached-reaper.md`
EOF
```

- [ ] **Step 2: Verificar tail do README**

```bash
tail -50 ~/.openclaw/dispatcher-agent/README.md
```

Expected: seção `## Reaper (wave-3.5)` presente.

---

## Phase 7: Smoke E2E — 6 cenários DoD §11.3

### Task 7.1: Baseline + helpers

**Files:** none (prep)

- [ ] **Step 1: Baseline snapshot**

```bash
cd ~/.openclaw/kanban-tasks
BASELINE_EVENTS=$(wc -l < events.jsonl)
cp state.json /tmp/state.ph7-baseline.json
cp events.jsonl /tmp/events.ph7-baseline.jsonl
echo "$BASELINE_EVENTS" > /tmp/ph7-baseline-count
echo "BASELINE_EVENTS=$BASELINE_EVENTS"
# Snapshot reaper.jsonl pra restore (se existir)
[ -f ~/.openclaw/dispatcher-agent/reaper.jsonl ] && cp ~/.openclaw/dispatcher-agent/reaper.jsonl /tmp/reaper.jsonl.ph7-baseline || touch /tmp/reaper.jsonl.ph7-baseline
echo "(reaper.jsonl baseline saved)"
```

- [ ] **Step 2: Helper criar fixture**

```bash
cat > /tmp/ph7-create-fixture.sh <<'BASH'
#!/usr/bin/env bash
# Cria task fixture com AC explicit (Expected: line é o AC pelo scrum-master parser)
set -euo pipefail
SUFFIX="$1"; AC="$2"
PLAN=/tmp/ph7-plan-${SUFFIX}.md
cat > "$PLAN" <<EOF
# Plan ph7-${SUFFIX}
**Goal:** smoke ph7 ${SUFFIX}
**Epico:** E10/scrum-master-agent
**Project:** openclaw
**Specs canonicas:**
- \`bevox-knowledge/35_specs/2026-04-19-e10-detached-reaper.md\`
## Phase 0: x
### Task 0.1: ph7 ${SUFFIX}
Smoke fixture cenario ${SUFFIX}.
**Files:**
- Create: \`/tmp/ph7-out-${SUFFIX}.txt\`
- [ ] **Step 1: stub**
Expected: ${AC}
EOF
~/.openclaw/scrum-master-agent/cli.sh propose --plan "$PLAN" --target-sprint current >/dev/null 2>&1
PID=$(~/.openclaw/scrum-master-agent/cli.sh list --status pending --json | python3 -c "import json,sys; print(json.load(sys.stdin)['proposals'][-1]['proposal_id'])")
~/.openclaw/scrum-master-agent/cli.sh accept "$PID" --ready >/dev/null 2>&1
TID=$(~/.openclaw/scrum-master-agent/cli.sh show "$PID" --json | python3 -c "import json,sys; print(json.load(sys.stdin)['state']['materialized_task_ids'][0])")
echo "$TID"
BASH
chmod +x /tmp/ph7-create-fixture.sh
```

- [ ] **Step 3: Helper fake execution detached (sem invocar Claude real)**

```bash
cat > /tmp/ph7-fake-detached.sh <<'BASH'
#!/usr/bin/env bash
# Simula dispatcher detached: cria log + status.json com pid morto + finished_at=null
# Move ready -> in_progress (NAO move pra testing — reaper que faz)
set -euo pipefail
TID="$1"; LOG_CONTENT="$2"; EXIT=${3:-0}; NO_TESTER=${4:-false}
mkdir -p ~/.openclaw/dispatcher-agent/executions
echo -e "$LOG_CONTENT" > ~/.openclaw/dispatcher-agent/executions/${TID}.log
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
# pid 99999999 = invalido (processo morto)
cat > ~/.openclaw/dispatcher-agent/executions/${TID}.status.json <<EOF
{
  "task_id": "${TID}",
  "session_id": "fake-${TID}",
  "pid": 99999999,
  "log_path": "$(echo ~)/.openclaw/dispatcher-agent/executions/${TID}.log",
  "started_at": "${TS}",
  "finished_at": null,
  "exit_code": null,
  "run_mode": "detach"
}
EOF
~/.openclaw/kanban-tasks/cli.sh task move "$TID" in_progress --actor dispatcher >/dev/null 2>&1 || true
# Persist dispatch_flags.no_tester via set-dispatch-payload --merge
~/.openclaw/kanban-tasks/cli.sh task set-dispatch-payload "$TID" \
  --payload "{\"dispatch_flags\": {\"no_tester\": ${NO_TESTER}}, \"dispatch_mode\": \"detach\", \"_fake_exit_code\": ${EXIT}}" \
  --merge >/dev/null
# Trick: para que reap_finished detecte exit_code via _parse_exit_code_from_log,
# o log precisa terminar limpo (sem "error", "traceback", "failed", "abort") pra dar 0.
# Se quiser exit != 0, log precisa conter um desses markers.
echo "fake detached: $TID (no_tester=${NO_TESTER}, exit=${EXIT})"
BASH
chmod +x /tmp/ph7-fake-detached.sh
```

### Task 7.2: Cenario 1 — happy detached + reaper → done (real claude haiku)

- [ ] **Step 1: Criar fixture + fake detached + reap tick**

```bash
TID1=$(/tmp/ph7-create-fixture.sh c1 "arquivo /tmp/ph7-out-c1.txt deve conter a string reaper-happy")
echo "$TID1" > /tmp/ph7-tid1
echo "=== Cenario 1: $TID1 ==="
# Cria arquivo que satisfaz AC
echo "reaper-happy" > /tmp/ph7-out-c1.txt
# Fake detached com log clean (exit 0)
/tmp/ph7-fake-detached.sh "$TID1" "starting...\nfile created at /tmp/ph7-out-c1.txt with reaper-happy\ncomplete" 0 false
echo ""
echo "=== reaper tick (real claude haiku no tester) ==="
~/.openclaw/dispatcher-agent/cli.sh reap-detached --once 2>&1 | tail -10
```

Expected: tick mostra reaped + tester_invoked + decisão = `done`. (Tester invoca haiku, ~30-60s.)

- [ ] **Step 2: Verificar state final**

```bash
TID1=$(cat /tmp/ph7-tid1)
~/.openclaw/kanban-tasks/cli.sh task show $TID1 --json | python3 -c "
import json, sys
t = json.load(sys.stdin)['task']
dp = t.get('dispatch_payload') or {}
tr = dp.get('test_result') or {}
print(f'status={t[\"status\"]}  blocked={t.get(\"blocked\")}')
print(f'test_overall={tr.get(\"last_test_overall\")}  decision={tr.get(\"last_test_decision\")}')
print(f'dispatch_flags={dp.get(\"dispatch_flags\")}')
assert t['status'] == 'done', f'expected done, got {t[\"status\"]}'
assert tr.get('last_test_decision') == 'done'
assert dp.get('dispatch_flags', {}).get('no_tester') is False
print('OK cenario 1: detached + reaper -> done (1 touch)')"
```

Expected: `OK cenario 1`.

- [ ] **Step 3: Verificar audit jsonl**

```bash
tail -1 ~/.openclaw/dispatcher-agent/reaper.jsonl | python3 -c "
import json, sys
e = json.loads(sys.stdin.read())
print(f'tick_id={e[\"tick_id\"][:30]}...')
print(f'lock_acquired={e[\"lock_acquired\"]}  reaped={e[\"reaped_count\"]}  tester_invoked={e[\"tester_invoked_count\"]}')
acts = [a for a in e['actions_per_task']]
for a in acts:
    print(f'  {a[\"task_id\"]}: {a[\"stage\"]} -> {a[\"outcome\"]}')
"
```

Expected: tick mostra reaped_count=1 + tester_invoked_count=1 + 3 stages do task (reaped, lifecycle_applied, tester_invoked → done).

- [ ] **Step 4: Cleanup c1**

```bash
TID1=$(cat /tmp/ph7-tid1)
~/.openclaw/kanban-tasks/cli.sh task archive $TID1 >/dev/null 2>&1 || true
rm -f /tmp/ph7-out-c1.txt ~/.openclaw/dispatcher-agent/executions/$TID1.{log,status.json}
echo "cenario 1 cleanup OK"
```

### Task 7.3: Cenario 2 — fail detached + reaper → in_progress blocked test_failed

- [ ] **Step 1: Fixture com AC + fake detached log que CONTRADIZ AC**

```bash
TID2=$(/tmp/ph7-create-fixture.sh c2 "log do executor deve mostrar BUILD SUCCESS explicito")
echo "$TID2" > /tmp/ph7-tid2
echo "=== Cenario 2: $TID2 ==="
# Log clean (sem markers de fail) pra reap_finished dar exit 0,
# mas conteudo que CONTRADIZ AC (tester decide fail)
/tmp/ph7-fake-detached.sh "$TID2" "starting build\nbuilding modules\nshipping artifacts\ncomplete cleanly without success message" 0 false
echo ""
~/.openclaw/dispatcher-agent/cli.sh reap-detached --once 2>&1 | tail -10
```

Expected: reaper aplica reap + lifecycle (testing) + tester invoca; tester decide fail.

- [ ] **Step 2: Verificar**

```bash
TID2=$(cat /tmp/ph7-tid2)
~/.openclaw/kanban-tasks/cli.sh task show $TID2 --json | python3 -c "
import json, sys
t = json.load(sys.stdin)['task']
dp = t.get('dispatch_payload') or {}
tr = dp.get('test_result') or {}
print(f'status={t[\"status\"]}  blocked={t.get(\"blocked\")}  reason={t.get(\"blocked_reason\", \"?\")[:80]}')
print(f'decision={tr.get(\"last_test_decision\")}')
assert t['status'] == 'in_progress'
assert t.get('blocked') is True
assert tr.get('last_test_decision') in ('in_progress_test_failed', 'in_progress_test_inconclusive')
print('OK cenario 2: detached + reaper -> in_progress + blocked')"
```

Expected: `OK cenario 2`.

- [ ] **Step 3: Cleanup c2**

```bash
TID2=$(cat /tmp/ph7-tid2)
~/.openclaw/kanban-tasks/cli.sh task unblock $TID2 >/dev/null 2>&1
~/.openclaw/kanban-tasks/cli.sh task archive $TID2 >/dev/null 2>&1
rm -f ~/.openclaw/dispatcher-agent/executions/$TID2.{log,status.json}
echo "cenario 2 cleanup OK"
```

### Task 7.4: Cenario 3 — --no-tester detached → reaper para em testing, test_result null

- [ ] **Step 1: Fixture + fake detached com no_tester=true + reap tick**

```bash
TID3=$(/tmp/ph7-create-fixture.sh c3 "arquivo /tmp/ph7-out-c3.txt deve existir")
echo "$TID3" > /tmp/ph7-tid3
echo "=== Cenario 3: $TID3 (no_tester=true) ==="
echo "x" > /tmp/ph7-out-c3.txt
/tmp/ph7-fake-detached.sh "$TID3" "starting\nfile created\ncomplete" 0 true
echo ""
~/.openclaw/dispatcher-agent/cli.sh reap-detached --once 2>&1 | tail -10
```

Expected: reaper aplica reap + lifecycle (testing) mas tester `skipped_no_tester_flag`.

- [ ] **Step 2: Verificar test_result nulo + reaper.jsonl mostra skip**

```bash
TID3=$(cat /tmp/ph7-tid3)
~/.openclaw/kanban-tasks/cli.sh task show $TID3 --json | python3 -c "
import json, sys
t = json.load(sys.stdin)['task']
dp = t.get('dispatch_payload') or {}
tr = dp.get('test_result')
print(f'status={t[\"status\"]}  test_result={tr}')
print(f'no_tester={dp.get(\"dispatch_flags\", {}).get(\"no_tester\")}')
assert t['status'] == 'testing', f'expected testing, got {t[\"status\"]}'
assert tr is None, f'expected NO test_result (no_tester=true), got {tr}'
assert dp.get('dispatch_flags', {}).get('no_tester') is True
print('OK cenario 3: --no-tester detached -> reaper para em testing')"
echo ""
echo "=== reaper.jsonl tail ==="
tail -1 ~/.openclaw/dispatcher-agent/reaper.jsonl | python3 -c "
import json, sys
e = json.loads(sys.stdin.read())
print(f'tester_invoked_count={e[\"tester_invoked_count\"]}')
for a in e['actions_per_task']:
    if a['stage'] == 'tester_invoked':
        print(f'  {a[\"task_id\"]}: outcome={a[\"outcome\"]}')
        assert a['outcome'] == 'skipped_no_tester_flag', a
print('OK reaper.jsonl mostra skipped_no_tester_flag')
"
```

Expected: 2 OKs.

- [ ] **Step 3: Cleanup c3**

```bash
TID3=$(cat /tmp/ph7-tid3)
~/.openclaw/kanban-tasks/cli.sh task archive $TID3 >/dev/null 2>&1 || true
rm -f /tmp/ph7-out-c3.txt ~/.openclaw/dispatcher-agent/executions/$TID3.{log,status.json}
echo "cenario 3 cleanup OK"
```

### Task 7.5: Cenario 4 — lock contention (2 instâncias paralelas)

- [ ] **Step 1: Spawn instance A em background, instance B em foreground**

```bash
echo "=== Cenario 4: lock contention ==="
# Instance A: roda em background, segura lock por ~3s artificialmente
# Como reap_tick é rapido sem executions pendentes, vamos usar sleep wrapper
# Trick: criar lockfile temporário diferente pra teste isolado
LOCKFILE_TEST=/tmp/ph7-test-lock
rm -f $LOCKFILE_TEST
# Cria executions vazio em sandbox? Não — vamos usar python direto pra testar lock
cd ~/.openclaw/dispatcher-agent && PYTHONPATH=. python3 <<'PY' &
from lib import reaper
from pathlib import Path
import time
lockfile = Path("/tmp/ph7-test-lock")
with reaper.global_lock(lockfile) as acq1:
    print(f"A acquired={acq1}")
    time.sleep(3)
    print("A releasing")
PY
# Pequeno delay pra A começar
sleep 0.5
# Instance B: tenta adquirir o mesmo lockfile
cd ~/.openclaw/dispatcher-agent && PYTHONPATH=. python3 <<'PY'
from lib import reaper
from pathlib import Path
lockfile = Path("/tmp/ph7-test-lock")
with reaper.global_lock(lockfile) as acq2:
    if acq2:
        print("B acquired=True (UNEXPECTED — should have been skipped)")
    else:
        print("B acquired=False (lock_skipped=true OK)")
PY
wait
rm -f /tmp/ph7-test-lock
```

Expected: `A acquired=True` + `B acquired=False (lock_skipped=true OK)` + `A releasing`.

- [ ] **Step 2: Validar via run_tick (manual + simulated timer)**

```bash
# Simula 2 invocacoes back-to-back (segunda dentro do mesmo tick da primeira)
echo "=== run_tick paralelos no lockfile real (rapido) ==="
cd ~/.openclaw/dispatcher-agent && PYTHONPATH=. python3 <<'PY' &
from lib import reaper
import time
# Garante atraso simulado: como nao temos executions reais, força sleep dentro do lock
from contextlib import contextmanager
import os, fcntl
# Workaround: adquire lock direto, segura, depois roda tick
fd = os.open(str(reaper.REAPER_LOCK), os.O_RDWR | os.O_CREAT)
fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
print("A holding real lock for 3s")
time.sleep(3)
fcntl.flock(fd, fcntl.LOCK_UN)
os.close(fd)
print("A released real lock")
PY
sleep 0.5
# B: roda reap-detached (deve detectar lock_skipped)
~/.openclaw/dispatcher-agent/cli.sh reap-detached --once --json 2>&1 | python3 -c "
import json, sys
result = json.loads(sys.stdin.read())
print(f'B result: lock_skipped={result.get(\"lock_skipped\")} considered={result.get(\"considered_executions\")}')
assert result.get('lock_skipped') is True, f'expected skipped, got {result}'
print('OK cenario 4: lock contention -> B exit 0 com lock_skipped=true')
"
wait
echo ""
echo "=== reaper.jsonl tail (last 2 entries) ==="
tail -2 ~/.openclaw/dispatcher-agent/reaper.jsonl | python3 -c "
import json, sys
for line in sys.stdin:
    e = json.loads(line)
    print(f'tick={e[\"tick_id\"][-12:]} lock_acquired={e[\"lock_acquired\"]} lock_skipped={e[\"lock_skipped\"]}')
"
```

Expected: `OK cenario 4` + tail mostra ao menos 1 entry com lock_skipped=true.

### Task 7.6: Cenario 5 — idempotência (3x sobre mesma execution já reapada)

- [ ] **Step 1: Fixture + 3 ticks consecutivos**

```bash
TID5=$(/tmp/ph7-create-fixture.sh c5 "log deve conter a string IDEMPOTENT")
echo "$TID5" > /tmp/ph7-tid5
echo "=== Cenario 5: $TID5 (idempotencia) ==="
/tmp/ph7-fake-detached.sh "$TID5" "starting\nIDEMPOTENT marker present\ncomplete" 0 true
echo ""
echo "=== Tick 1 (primeiro reap; deve agir) ==="
~/.openclaw/dispatcher-agent/cli.sh reap-detached --once --json 2>&1 | python3 -c "
import json, sys
e = json.loads(sys.stdin.read())
print(f'reaped={e[\"reaped_count\"]}  skipped_already={e[\"skipped_already_reaped\"]}')
"
echo ""
echo "=== Tick 2 (idempotente; nao deve reagir) ==="
~/.openclaw/dispatcher-agent/cli.sh reap-detached --once --json 2>&1 | python3 -c "
import json, sys
e = json.loads(sys.stdin.read())
print(f'reaped={e[\"reaped_count\"]}  skipped_already={e[\"skipped_already_reaped\"]}')
assert e['reaped_count'] == 0, f'tick 2 nao deveria reapar nada, got reaped={e[\"reaped_count\"]}'
"
echo ""
echo "=== Tick 3 (idempotente confirma) ==="
~/.openclaw/dispatcher-agent/cli.sh reap-detached --once --json 2>&1 | python3 -c "
import json, sys
e = json.loads(sys.stdin.read())
print(f'reaped={e[\"reaped_count\"]}  skipped_already={e[\"skipped_already_reaped\"]}')
assert e['reaped_count'] == 0
print('OK cenario 5: idempotencia confirmada (tick 2+3 nao reapam)')
"
```

Expected: tick 1 reapa 1, tick 2/3 reaped=0 + skipped_already incrementa.

- [ ] **Step 2: Cleanup c5**

```bash
TID5=$(cat /tmp/ph7-tid5)
~/.openclaw/kanban-tasks/cli.sh task archive $TID5 >/dev/null 2>&1 || true
rm -f ~/.openclaw/dispatcher-agent/executions/$TID5.{log,status.json}
echo "cenario 5 cleanup OK"
```

### Task 7.7: Cenario 6 — dry-run (zero side-effect)

- [ ] **Step 1: Fixture 2 executions pendentes + dry-run**

```bash
TID6A=$(/tmp/ph7-create-fixture.sh c6a "AC dry-run a")
TID6B=$(/tmp/ph7-create-fixture.sh c6b "AC dry-run b")
echo "$TID6A" > /tmp/ph7-tid6a
echo "$TID6B" > /tmp/ph7-tid6b
/tmp/ph7-fake-detached.sh "$TID6A" "log a clean" 0 true
/tmp/ph7-fake-detached.sh "$TID6B" "log b clean" 0 true
echo "=== Cenario 6: 2 fixtures pendentes; dry-run ==="
~/.openclaw/dispatcher-agent/cli.sh reap-detached --dry-run --json 2>&1 | python3 -c "
import json, sys
e = json.loads(sys.stdin.read())
print(f'considered={e[\"considered_executions\"]}  reaped={e[\"reaped_count\"]}  tester_invoked={e[\"tester_invoked_count\"]}')
print(f'dry_run={e[\"dry_run\"]}')
assert e['dry_run'] is True
assert e['considered_executions'] >= 2
assert e['reaped_count'] == 0, f'dry-run NAO deveria reapar: {e[\"reaped_count\"]}'
assert e['tester_invoked_count'] == 0
acts = [a for a in e['actions_per_task'] if a['outcome'].startswith('would_')]
print(f'would_handle entries: {len(acts)}')
assert len(acts) >= 2
print('OK cenario 6: dry-run zero side-effect, would_reap >= 2')
"
echo ""
echo "=== Confirma que executions NAO foram modificadas ==="
TID6A=$(cat /tmp/ph7-tid6a)
~/.openclaw/kanban-tasks/cli.sh task show $TID6A --json | python3 -c "
import json, sys
t = json.load(sys.stdin)['task']
print(f'{t[\"id\"]}: status={t[\"status\"]} (esperado in_progress, NAO testing)')
assert t['status'] == 'in_progress'
print('OK dry-run nao moveu kanban')
"
```

Expected: `OK cenario 6` + dry-run não modificou kanban.

- [ ] **Step 2: Cleanup c6**

```bash
for TID in $(cat /tmp/ph7-tid6a /tmp/ph7-tid6b); do
  ~/.openclaw/kanban-tasks/cli.sh task archive $TID >/dev/null 2>&1 || true
  rm -f ~/.openclaw/dispatcher-agent/executions/$TID.{log,status.json}
done
echo "cenario 6 cleanup OK"
```

### Task 7.8: Restore baseline

- [ ] **Step 1: Restaurar kanban + reaper.jsonl**

```bash
cd ~/.openclaw/kanban-tasks
cp /tmp/state.ph7-baseline.json state.json
cp /tmp/events.ph7-baseline.jsonl events.jsonl
./cli.sh rebuild >/dev/null 2>&1 || true
FINAL_EVENTS=$(wc -l < events.jsonl)
BASELINE_EVENTS=$(cat /tmp/ph7-baseline-count)
if [ "$FINAL_EVENTS" = "$BASELINE_EVENTS" ]; then
  echo "OK kanban restored ($FINAL_EVENTS == $BASELINE_EVENTS)"
else
  echo "WARN events differ: final=$FINAL_EVENTS baseline=$BASELINE_EVENTS"
fi
# Restore reaper.jsonl
cp /tmp/reaper.jsonl.ph7-baseline ~/.openclaw/dispatcher-agent/reaper.jsonl
echo ""
echo "=== fixtures cleanup ==="
rm -f /tmp/ph7-plan-*.md /tmp/ph7-tid* /tmp/ph7-out-*.txt /tmp/ph7-create-fixture.sh /tmp/ph7-fake-detached.sh
rm -f /tmp/state.ph7-baseline.json /tmp/events.ph7-baseline.jsonl /tmp/ph7-baseline-count /tmp/reaper.jsonl.ph7-baseline
echo "cleanup OK"
```

Expected: `OK kanban restored ...` + cleanup confirm.

- [ ] **Step 2: Sumário 6 cenários**

```bash
cat <<EOF
Smoke E2E reaper validado:
  ✓ Cenario 1: happy detached + reaper -> done (real claude haiku, 1 touch)
  ✓ Cenario 2: fail detached + reaper -> in_progress blocked test_failed
  ✓ Cenario 3: --no-tester detached -> reaper para em testing (test_result null)
  ✓ Cenario 4: lock contention -> instancia B exit 0 com lock_skipped=true
  ✓ Cenario 5: idempotencia -> tick 2+3 nao reapam (skipped_already incrementa)
  ✓ Cenario 6: dry-run -> zero side-effect, would_reap >= 2
EOF
```

---

## Phase 8: Canonical artifacts

### Task 8.1: Delta playbook dispatcher-agent.md

**Files:**
- Modify: `~/bevox-knowledge/20_architecture/agents/dispatcher-agent.md`

- [ ] **Step 1: Append seção `## Reaper (wave-3.5)`**

Localiza o final do arquivo (após `## Historico de levels`) e insere uma seção nova ANTES dela (ou após `## Boundary`). Use Edit tool.

Texto a adicionar (após `## Boundary com outros agents` block, antes de `## Volume minimo`):

```markdown

## Reaper (wave-3.5)

Subcomando `reap-detached` fecha o loop **detached** que para em
`testing` (limitacao §10.2 spec do tester-agent). NAO eh
cron-dispatcher (auto-dispatch de novas tasks `ready`). Reaper SO age
sobre executions ja lancadas pelo Bernard via `dispatcher next
--launch`.

### Operacao

```bash
vox dispatcher reap-detached --once          # uma passada (default; usado pelo systemd timer)
vox dispatcher reap-detached --once --json   # output estruturado
vox dispatcher reap-detached --dry-run       # lista o que faria, sem agir
```

### Garantias (§2 spec detached-reaper)

- **Sequencial**: dentro do tick, executions processadas uma a uma.
- **Ordem deterministica**: lote ordenado por `started_at` ascendente
  com tie-break por filename. NAO eh scheduler sofisticado; objetivo
  eh evitar comportamento implicito/instavel entre ticks.
- **Lock global do lote**: fcntl 1x por tick (NAO per-execution).
  Segunda instancia exit 0 com `lock_skipped=true` (sem falha).
- **Idempotente**: `post_action_applied=true` skipa reprocessamento
  (triplo-check: lifecycle early-return + reaper checa antes + tester
  nao re-invocado se `test_result` presente).
- **Carve-out `dispatch_flags.no_tester`**:
  - `false` (default) → reaper invoca tester via `_invoke_tester`
  - `true` → reaper para em `testing`, NAO invoca tester (touch extra
    manual de `vox tester check` continua existindo por design)
- **Transparente**: zero campo "reaped_by_reaper" no `dispatch_payload`;
  audit so em `~/.openclaw/dispatcher-agent/reaper.jsonl` + `status.json`
  herdado.

### Habilitacao systemd (manual pos-push)

Templates shipped em `~/.openclaw/dispatcher-agent/systemd/`. Bernard
copia + habilita explicit:

```bash
cp ~/.openclaw/dispatcher-agent/systemd/openclaw-reaper.{service,timer} \
   ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now openclaw-reaper.timer
systemctl --user list-timers | grep reaper
journalctl --user -u openclaw-reaper -f
```

### Touch model atualizado

Detached default (`no_tester=false`) **+ reaper habilitado** iguala
foreground em touches no happy path (1 touch ate done), com latencia
+60-120s. Detached + `no_tester=true` **+ reaper habilitado** para em
`testing` por design (touch extra manual de `tester check` continua).
Ver §10 da spec detached-reaper.

```

Use Edit tool com o old_string sendo o trecho exato antes do ponto de inserção (ex: `## Volume minimo`).

- [ ] **Step 2: Verificar diff**

```bash
cd ~/bevox-knowledge && git diff 20_architecture/agents/dispatcher-agent.md | head -50
```

Expected: chunk com nova seção `## Reaper (wave-3.5)`.

### Task 8.2: Tracker entry

**Files:**
- Modify: `~/bevox-knowledge/40_roadmap/delivery-tracker.yml`

- [ ] **Step 1: Adicionar wave após tester-agent**

Localizar bloco `id: tester-agent` em `delivery-tracker.yml` e adicionar abaixo (antes de `id: finance-agent`):

```yaml
      - id: detached-reaper
        status: delivered
        delivered_at: 2026-04-XX  # preencher no push gate
        features:
          - "reaper periodico fecha loop detached que parava em testing (limitacao wave-3 §10.2): subcomando 'vox dispatcher reap-detached --once' + systemd user timer 60s; reusa runner.reap_finished + lifecycle.process_finished_session + _invoke_tester de wave-2+3 (zero refactor)"
          - "sequencial + ordem deterministica (started_at ascendente + tie-break filename) sob lock global do lote (fcntl 1x por tick, NAO per-execution); segunda instancia exit 0 com lock_skipped=true (nao falha)"
          - "idempotente: post_action_applied=true skipa reprocessamento (triplo-check: lifecycle early-return + reaper checa antes + tester nao re-invocado se test_result presente)"
          - "carve-out explicito dispatch_flags.no_tester no touch model: no_tester=false (default) -> reaper invoca tester; no_tester=true -> reaper para em testing por design"
          - "reaper transparente: zero campo 'reaped_by_reaper' no dispatch_payload; audit so em ~/.openclaw/dispatcher-agent/reaper.jsonl + status.json herdado"
          - "reaper = subcomando do dispatcher-agent (zero novo agent identitario, zero entry novo no registry.yml); cmd_next ganha persistencia dispatch_flags.no_tester em ambas branches"
          - "systemd user units (timer + service oneshot) shipped como templates em ~/.openclaw/dispatcher-agent/systemd/; instalacao manual pelo Bernard pos-push (NAO automatizada)"
          - "smoke E2E validou 6 cenarios DoD §11.3: happy detached real claude haiku -> done (1 touch); fail detached -> in_progress blocked test_failed; --no-tester detached -> reaper para em testing; lock contention 2 instancias -> B lock_skipped=true exit 0; idempotencia 3 ticks -> tick 2+3 nao reagem; dry-run -> zero side-effect"
          - "fora desta wave (preservado): cron-dispatcher wave-4 PRD original (auto-dispatch de novas tasks ready), daemon persistente, wrapper bash no claude -p, inotify, multi-task parallel, auto-merge, auto-close de spec/wave, auto-relaunch (Bernard sempre via dispatcher relaunch), notificacao push, UI MC dedicada, multi-host, tuning prompt drafter (heritage wave-3 follow-up)"
        spec: 35_specs/2026-04-19-e10-detached-reaper.md
```

Use Edit tool localizando o ponto de inserção.

- [ ] **Step 2: Verificar diff stat**

```bash
cd ~/bevox-knowledge && git diff --stat 40_roadmap/delivery-tracker.yml
echo ""
grep "id: detached-reaper" -A2 40_roadmap/delivery-tracker.yml | head -3
```

Expected: tracker shows `detached-reaper` com `2026-04-XX` placeholder.

### Task 8.3: Sync playbook canonical → host-local

- [ ] **Step 1: Não há sync do dispatcher (playbook permanece canonical apenas)**

Diferente do tester-agent (que tinha `~/.openclaw/tester-agent/playbook.md` cópia local sync'd), o dispatcher-agent não mantém playbook copy local. Confirmar:

```bash
ls ~/.openclaw/dispatcher-agent/playbook.md 2>&1 | head -1
```

Se existir, sync:

```bash
[ -f ~/.openclaw/dispatcher-agent/playbook.md ] && cp ~/bevox-knowledge/20_architecture/agents/dispatcher-agent.md ~/.openclaw/dispatcher-agent/playbook.md && echo "synced" || echo "(no host-local playbook to sync; canonical only)"
```

Expected: `synced` ou `(no host-local playbook to sync...)`.

### Task 8.4: Canonical commit (single-gate)

- [ ] **Step 1: Stage + status**

```bash
cd ~/bevox-knowledge
git add \
  20_architecture/agents/dispatcher-agent.md \
  40_roadmap/delivery-tracker.yml
git status -s | grep -E "(dispatcher|delivery-tracker)"
```

Expected: 2 files staged.

- [ ] **Step 2: Commit**

```bash
cd ~/bevox-knowledge && git commit -m "$(cat <<'EOF'
feat(E10): detached-reaper wave delivered

Wave-3.5 do PRD "OpenClaw Task-Orchestrated Development for Claude
Code". Fecha o loop detached que parava em testing (limitacao wave-3
§10.2): subcomando 'vox dispatcher reap-detached --once' + systemd
user timer 60s.

Reusa runner.reap_finished + lifecycle.process_finished_session +
_invoke_tester de wave-2+3 (zero refactor). Reaper = subcomando do
dispatcher-agent (zero novo agent identitario, zero entry novo no
registry.yml).

Garantias travadas:
- sequencial + ordem deterministica (started_at asc, tie-break filename)
  sob lock global do lote (fcntl 1x por tick, NAO per-execution)
- idempotente (post_action_applied=true skipa reprocessamento)
- carve-out dispatch_flags.no_tester explicito:
  - no_tester=false (default) -> reaper invoca tester
  - no_tester=true -> reaper para em testing por design
- transparente (zero campo "reaped_by_reaper"; audit em reaper.jsonl)
- segunda instancia exit 0 com lock_skipped=true (nao falha)

Delta minimo dispatcher api.py: cmd_reap_detached + persistencia
dispatch_flags.no_tester em cmd_next ambas branches.

systemd user units shipped como templates em
~/.openclaw/dispatcher-agent/systemd/; instalacao manual pelo Bernard
pos-push (NAO automatizada).

Modulo operacional em ~/.openclaw/dispatcher-agent/lib/reaper.py
(host-local, Python stdlib + fcntl, zero pip install).

Smoke E2E validou 6 cenarios DoD §11.3: happy detached real claude
haiku -> done; fail; --no-tester; lock contention; idempotencia;
dry-run.

Spec: 35_specs/2026-04-19-e10-detached-reaper.md (commit 62923ae)
Plan: ~/.openclaw/docs/superpowers/plans/2026-04-19-e10-detached-reaper-plan.md

Boundary: cron-dispatcher (wave-4 PRD original, auto-dispatch de novas
ready), daemon persistente, wrapper claude, inotify, multi-task
parallel, auto-merge, auto-close, auto-relaunch, push notifications,
UI dedicada, multi-host, tuning prompt drafter explicitamente fora.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git log --oneline -3
```

Expected: novo commit listado + spec `62923ae` + tester `eabaa8d`.

---

## Phase 9: Push gate humano + backfill + memory

### Task 9.1: Show diff vs origin + gate humano

- [ ] **Step 1: Summary pré-push**

```bash
cd ~/bevox-knowledge
echo '=== commits ahead de origin/main ==='
git log --oneline origin/main..HEAD
echo ''
echo '=== git status fora do escopo ==='
git status -s | head -10
```

Expected: 2 commits ahead (spec `62923ae` + delivery `<NEW>`); pré-existentes fora do escopo não staged.

- [ ] **Step 2: Bernard decide push**

Instruções pro operador:

```
Backfill primeiro (Phase 9.2), depois push:

  cd ~/bevox-knowledge && git push origin main

Pause e revisa:
  git log --oneline origin/main..HEAD
  git show HEAD

Rollback (cuidado):
  git reset --soft HEAD~1
```

**Não automatizar push.** Gate humano explícito.

### Task 9.2: Backfill `delivered_at` + amend (sem commit cosmético)

- [ ] **Step 1: Substituir placeholder + amend**

```bash
cd ~/bevox-knowledge
sed -i "s|delivered_at: 2026-04-XX  # preencher no push gate|delivered_at: $(date +%Y-%m-%d)|" \
    40_roadmap/delivery-tracker.yml
git add 40_roadmap/delivery-tracker.yml
git commit --amend --no-edit
git log --oneline -1
```

Expected: commit amended com data real (sem commit extra).

### Task 9.3: Push após Bernard aprovar

- [ ] **Step 1: Push**

```bash
cd ~/bevox-knowledge && git push origin main 2>&1 | tail -5
```

Expected: push OK.

- [ ] **Step 2: Verificar ahead/behind 0/0**

```bash
cd ~/bevox-knowledge
git fetch origin 2>&1 | tail -2
echo "=== local HEAD ==="
git rev-parse HEAD
echo "=== remote HEAD ==="
git rev-parse origin/main
echo "=== ahead/behind ==="
git rev-list --left-right --count origin/main...HEAD
```

Expected: hashes batem + ahead/behind = `0  0`.

### Task 9.4: systemd habilitação manual (passo Bernard pós-push)

**Não bloqueante pré-push; Bernard executa quando quiser ativar.**

- [ ] **Step 1: Documentar comandos no terminal pra Bernard**

```bash
cat <<'EOF'

==================== HABILITACAO SYSTEMD (manual Bernard) ====================

Apos push aprovado, pra ativar reaper periodico (60s tick):

  mkdir -p ~/.config/systemd/user
  cp ~/.openclaw/dispatcher-agent/systemd/openclaw-reaper.{service,timer} \
     ~/.config/systemd/user/
  systemctl --user daemon-reload
  systemctl --user enable --now openclaw-reaper.timer

Verificar:
  systemctl --user list-timers | grep reaper
  journalctl --user -u openclaw-reaper -f       # tail logs

Desabilitar (se precisar):
  systemctl --user disable --now openclaw-reaper.timer

Manual sempre disponivel mesmo sem timer:
  vox dispatcher reap-detached --once

==============================================================================

EOF
```

### Task 9.5: Memory file

**Files:**
- Create: `~/.claude/projects/-home-you--openclaw/memory/e10_detached_reaper_state.md`

- [ ] **Step 1: Write memory**

```bash
cat > ~/.claude/projects/-home-you--openclaw/memory/e10_detached_reaper_state.md <<'EOF'
---
name: E10/detached-reaper — execution state
description: Wave-3.5 PRD orchestration — reaper periodico fecha loop detached (1 touch happy path com no_tester=false; 2 touches com no_tester=true). Delivered + pushed 2026-04-XX.
type: project
---

## Checkpoint (2026-04-XX)

**DELIVERED + PUSHED.** Wave-3.5 PRD em produção em main remoto.

- Spec canonizada: `35_specs/2026-04-19-e10-detached-reaper.md` (commit `62923ae`)
- Wave commit: `<SHA>` em main remoto (delta playbook dispatcher + tracker)
- Modulo host-local operavel via `~/.openclaw/dispatcher-agent/cli.sh reap-detached`
- ahead/behind origin/main = 0/0

## Modulo host-local

- `~/.openclaw/dispatcher-agent/lib/reaper.py` — Python stdlib + fcntl
  - global_lock (LOCK_NB; segunda instancia retorna False sem falha)
  - scan_executions (ordenacao deterministica started_at asc + tie-break filename)
  - classify_execution (already_reaped | needs_lifecycle | still_running | needs_reap)
  - process_executions (sequencial; reusa runner+lifecycle+_invoke_tester)
  - run_tick (lock + scan + process + audit jsonl)
- Delta dispatcher: `lib/api.py` ganha cmd_reap_detached + persiste dispatch_flags.no_tester em cmd_next
  - Backup: `lib/api.py.pre-reaper.bak`
- Templates systemd: `~/.openclaw/dispatcher-agent/systemd/openclaw-reaper.{service,timer}`

## Decisões travadas

- Tigger = systemd user timer 60s + cmd manual `--once` (Q1 framing travada em opcao a)
- Sequencial + ordem deterministica (started_at asc; tie-break filename) sob lock global do lote (fcntl 1x por tick)
- Idempotente (post_action_applied=true skipa)
- Carve-out dispatch_flags.no_tester explicito:
  - no_tester=false (default) -> reaper invoca tester
  - no_tester=true -> reaper para em testing por design
- Reaper transparente (audit so em reaper.jsonl + status.json herdado)
- Reaper = subcomando do dispatcher (zero novo agent identitario, zero entry no registry.yml)
- Sem auto-relaunch (Bernard sempre via dispatcher relaunch)
- Sem auto-dispatch de novas tasks ready (cron-dispatcher = wave-4 PRD original, separada)

## Touch model atualizado

| Modo | no_tester | Touches happy path |
|---|---|---|
| foreground (--launch --foreground) | false | 1 |
| detached (--launch) + reaper habilitado | false | **1** (reaper fecha em ~60-120s) |
| detached (--launch --no-tester) + reaper habilitado | true | 2 (kick + tester check manual) |
| detached + reaper desabilitado | qualquer | 2 (igual pre-wave-3.5) |

## Smoke E2E validado (6 cenarios DoD §11.3)

1. Happy detached + reaper -> done (1 touch real claude haiku)
2. Fail detached + reaper -> in_progress blocked test_failed
3. --no-tester detached -> reaper para em testing (test_result null; reaper.jsonl mostra skipped_no_tester_flag)
4. Lock contention 2 instancias -> B exit 0 com lock_skipped=true; reaper.jsonl 2 linhas
5. Idempotencia tick 1+2+3 -> tick 2+3 reaped=0, skipped_already incrementa
6. Dry-run -> zero side-effect; would_reap >= 2

Baseline kanban + reaper.jsonl restaurados.

## Habilitacao systemd (passo Bernard manual)

```bash
mkdir -p ~/.config/systemd/user
cp ~/.openclaw/dispatcher-agent/systemd/openclaw-reaper.{service,timer} \
   ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now openclaw-reaper.timer
systemctl --user list-timers | grep reaper
journalctl --user -u openclaw-reaper -f
```

Manual sempre disponivel mesmo sem timer:
`vox dispatcher reap-detached --once`

## Proximas waves PRD (fora desta spec)

- E10/cron-dispatcher (wave-4 PRD original): auto-dispatch de novas tasks ready; depende de tester+reaper estaveis
- Daemon persistente com inotify se 60s latencia virar dor
- Notificacao push (Telegram/email) de done/failed/proposed_rejected
- UI MC pra reaper status (card em tab dispatcher)
- Multi-host coordination
- Tuning prompt drafter (heritage wave-3 follow-up)
- Auto-relaunch com retry budget

## Push gate

`bevox-knowledge/main` PUSHED em 2026-04-XX. Local + remoto = `<SHA>`.
Modulo host-local (reaper + dispatcher delta + systemd templates) nao precisa push.
EOF
```

- [ ] **Step 2: Adicionar ao MEMORY.md index**

```bash
echo '- [E10/detached-reaper — execution state](e10_detached_reaper_state.md) — wave-3.5 PRD orchestration; reaper periodico fecha loop detached; delivered + pushed 2026-04-XX' >> ~/.claude/projects/-home-you--openclaw/memory/MEMORY.md
tail -3 ~/.claude/projects/-home-you--openclaw/memory/MEMORY.md
```

Expected: nova entry visível.

---

## Self-review (executado durante writing)

### Spec coverage

- §1 Visão (objetivo + resultado esperado + out of scope): Phase 1-7 (implementação) + Phase 8 (canonical)
- §2 Decisões travadas (8 itens):
  - #1 Trigger systemd timer + cmd manual: Phase 4 (cmd_reap_detached) + Phase 5 (templates) + Phase 9.4 (habilitação manual documentada)
  - #2 Sequencial + ordem deterministica + lock global do lote + idempotente: Phase 1.2 (TDD lock) + Phase 2.1 (TDD ordering) + Phase 3.1 (TDD classify) + Phase 3.3 (run_tick)
  - #3 fcntl lock global: Phase 1.2 + Phase 7.5 (smoke contention)
  - #4 Persistir no_tester: Phase 4.1 (delta cmd_next metadata)
  - #5 Audit reaper.jsonl: Phase 3.2 (append_audit)
  - #6 Reaper transparente: garantia em Phase 3.3 (zero campo "reaped_by_reaper" no payload merge — apenas em audit local)
  - #7 _invoke_tester reusado: Phase 3.3 (process_executions importa de api)
  - #8 Sem auto-relaunch: garantia estrutural (reaper não chama relaunch)
- §3 Arquitetura: file structure Phase 1.1 + Phase 5 (systemd templates)
- §4 Sem novos spikes: documentado plan header
- §5 I/O models: Phase 3.2 (audit shape) + Phase 3.3 (process pipeline)
- §6 State machine: Phase 3.3 (run_tick orquestra fluxo) + Phase 7.2-7.4 cenarios validam
- §7 Commands surface: Phase 4.2 (cmd_reap_detached + subparser)
- §8 Flows E2E: Phase 7 cobre 6 cenarios (happy, fail, --no-tester, lock, idempotencia, dry-run)
- §9 Boundary: documentado plan header guardrails + Phase 8.1 playbook delta
- §10 Touch model: Phase 8.1 playbook delta + Phase 9.5 memory
- §11 DoD: 11.1 canonical Phase 8 / 11.2 host-local Phases 1-6 / 11.3 smoke Phase 7 / 11.4 systemd nao-bloqueante Phase 9.4 / 11.5 push gate Phase 9
- §12 Riscos: hallucination guard (heritage wave-3); lock contention Phase 7.5; idempotencia Phase 7.6
- §13 Follow-ups: documentado plan header + Phase 9.5 memory

### Placeholder scan

- `delivered_at: 2026-04-XX`: intencional; gate humano Phase 9.2 backfill
- `<SHA>` em memory: intencional; substituído pós-push
- Nenhum TBD/TODO/"implement later" técnico

### Type consistency

- `dispatch_flags.no_tester` (boolean): consistent Phase 4.1 (cmd_next merge), Phase 3.3 (`_read_dispatch_flags_no_tester`), Phase 7.4 (smoke c3 verifica), Phase 8.1+8.2 (playbook+tracker)
- `classify_execution` returns: `already_reaped | needs_lifecycle | still_running | needs_reap` consistent Phase 3.1 TDD + Phase 3.3 process_executions handling
- `actions_per_task[].stage` values: `reaped | lifecycle_applied | tester_invoked | dry_run` consistent Phase 3.3 + Phase 7 smoke asserts
- `actions_per_task[].outcome` values: `exit_detected | not_yet_finished | auto_moved_to_testing | execution_failed | tester_done | tester_blocked_test_failed | tester_blocked_test_inconclusive | tester_proposed_rejected | skipped_no_tester_flag | tester_invoke_failed | reap_error:* | lifecycle_error:* | would_handle_*` consistent process_executions + smoke asserts (note: spec §5.2 lista versão idealizada; implementação flexível)
- `lock_acquired` / `lock_skipped` (booleans): consistent Phase 1.2 TDD + Phase 3.3 run_tick + Phase 7.5 smoke
- Exit codes `0` (sempre, mesmo lock_skipped) + `1` (erro infrastrutural via _err): consistent Phase 4.2 + spec §7.1

Nenhum drift identificado.

---

## Notas operacionais

- **Push gate humano (Phase 9.1):** Bernard decide timing.
- **Módulo host-local:** `~/.openclaw/dispatcher-agent/lib/reaper.py` é host-local; não há commits pra código Python (mesmo pattern wave-1+2+3).
- **Delta dispatcher api.py:** modificado in-place; backup `.pre-reaper.bak` preservado pra rollback.
- **systemd templates:** shipped em `~/.openclaw/dispatcher-agent/systemd/` mas **NÃO instalados** automaticamente. Bernard copia + habilita manualmente pós-push (Phase 9.4 lista comandos).
- **Smoke E2E (Phase 7) toca Claude Code real apenas no cenário 1** (~$0.001-0.005 por invocação haiku). Total estimado: ~$0.01 pra cenário 1; outros são fake-execution sem invocar haiku (cenários 2 invoca haiku também via tester real). Total: ~$0.02-0.03. Baseline kanban+reaper.jsonl restaurados ao final.
- **Cenário 2 (fail) usa fake exec com log clean (exit 0) mas conteúdo que contradiz AC** — drafter haiku decide fail/inconclusive baseado no contraste log×AC.
- **Out of scope explícito (mencionar quando relevante):** cron-dispatcher (wave-4 PRD original), daemon persistente, wrapper bash no claude -p, inotify, multi-task parallel, auto-merge, auto-close spec/wave, auto-relaunch, push notifications, UI dedicada, multi-host, tuning prompt drafter (heritage wave-3 follow-up).
- **Reaper invoca tester com mesmo helper `_invoke_tester` da wave-3** — zero edit em tester. Se tester evoluir (ex: novos exit codes), reaper herda automaticamente.
- **Reaper NÃO altera comportamento de `cmd_next`** além de adicionar `dispatch_flags` no metadata. Foreground continua invocando tester via `_invoke_tester` direto na mesma linha de execução; detached agora delega esse mesmo helper pro reaper rodar depois.
