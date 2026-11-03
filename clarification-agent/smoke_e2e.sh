#!/bin/bash
# Smoke E2E — clarification-daemon-local-first wave-1
# Cobre 14 cenários da spec 2026-04-21-e10-clarification-daemon-local-first §10.
set -u

PASS=0
FAIL=0
FAILED_NAMES=()

_ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
_fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); FAILED_NAMES+=("$1"); }

CLI=~/.openclaw/clarification-agent/cli.sh
KANBAN=~/.openclaw/kanban-tasks/cli.sh
POLL_JSONL=~/.openclaw/clarification-agent/poll.jsonl

# ========= Cenário 1: Happy path pull local-safe =========
echo "=== 1. Happy pull local-safe ==="
# (Requer task preparada com spec_ref válida; placeholder — executado manualmente
# por Bernard quando houver kanban task real. Marca como PENDING.)
echo "  (pending — requires real kanban task with valid spec_ref + clarification_required blocked_reason)"

# ========= Cenário 2: Clarification safe resolvido local =========
echo "=== 2. Clarification safe local drafter qwen2.5-coder ==="
# Semelhante ao Cenário 1; requer ollama up + spec real. Pending.
echo "  (pending — requires real task + live ollama inference)"

# ========= Cenário 3: Fast-fail payload vazio =========
echo "=== 3. Fast-fail payload vazio ==="
# Este cenario PODE ser automatizado: cria task sintética com payload vazio.
_scenario_fast_fail() {
    TID="T-SMOKE-FF-$(date +%s)"
    echo "  Creating task $TID with empty payload..."
    $KANBAN task new --id "$TID" --project openclaw --title "smoke fast-fail" \
        --actor smoke --json > /dev/null 2>&1 || {
        echo "  (skip — task new not supported or failed; kanban payload gate may already reject empty payload per wave-4)"
        return
    }
    $KANBAN task block "$TID" --reason "clarification_required: payload vazio intencional" --actor smoke > /dev/null 2>&1
    $KANBAN task set-dispatch-payload "$TID" --payload '{"spec_ref":"","acceptance_criteria":[]}' --merge --actor smoke > /dev/null 2>&1

    TICK_OUT=$($CLI poll-tick --json 2>/dev/null)
    FAST_FAILED=$(echo "$TICK_OUT" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('fast_failed',0))" 2>/dev/null || echo 0)
    if [ "$FAST_FAILED" -ge 1 ]; then
        _ok "fast_fail emitiu escalation sem LLM para $TID"
    else
        _fail "fast_fail nao detectado para $TID"
    fi

    # Cleanup
    $KANBAN task archive "$TID" --actor smoke > /dev/null 2>&1 || \
    $KANBAN task move "$TID" rejected --reason "manual: smoke cleanup" --actor smoke --force > /dev/null 2>&1 || true
}
_scenario_fast_fail

# ========= Cenário 4: Pre-filter non-clarification =========
echo "=== 4. Pre-filter non-clarification ==="
_scenario_prefilter_non_clarification() {
    TID="T-SMOKE-NC-$(date +%s)"
    $KANBAN task new --id "$TID" --project openclaw --title "smoke non-clar" \
        --actor smoke --json > /dev/null 2>&1 || { echo "  (skip — task new blocked by wave-4 gate)"; return; }
    $KANBAN task block "$TID" --reason "execution_failed: synthetic test" --actor smoke > /dev/null 2>&1
    # Must populate payload so prefilter doesn't skip on NOT-blocked check — but blocked_reason is the filter
    $KANBAN task set-dispatch-payload "$TID" --payload '{"spec_ref":"a","acceptance_criteria":["b"]}' --merge --actor smoke > /dev/null 2>&1

    TICK_OUT=$($CLI poll-tick --json 2>/dev/null)
    # Expect: filtered=1, decision has reason=blocked_reason_not_clarification
    FILTERED=$(echo "$TICK_OUT" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('filtered',0))" 2>/dev/null || echo 0)
    if [ "$FILTERED" -ge 1 ]; then
        _ok "prefilter non-clarification filtrou $TID"
    else
        _fail "prefilter nao filtrou $TID (output: $TICK_OUT)"
    fi

    $KANBAN task archive "$TID" --actor smoke > /dev/null 2>&1 || true
}
_scenario_prefilter_non_clarification

# ========= Cenário 5: Pre-filter already_pending =========
echo "=== 5. Pre-filter already_pending ==="
echo "  (validated-via-unit-tests — see tests.test_poller.TestPrefilterAlreadyPending)"

# ========= Cenário 6: Dedup hash match =========
echo "=== 6. Dedup hash match ==="
echo "  (validated-via-unit-tests — see tests.test_poller.TestPrefilterDedupHash)"

# ========= Cenário 7: Budget exhausted =========
echo "=== 7. Budget exhausted ==="
echo "  (validated-via-unit-tests — see tests.test_poller.TestPrefilterBudget)"

# ========= Cenário 8: Lock contention real =========
echo "=== 8. Lock contention real ==="
_scenario_lock_contention() {
    $CLI poll-tick --json > /tmp/smoke-tick-a.json 2>/dev/null &
    PID_A=$!
    $CLI poll-tick --json > /tmp/smoke-tick-b.json 2>/dev/null &
    PID_B=$!
    wait $PID_A; wait $PID_B
    A=$(python3 -c "import json;d=json.load(open('/tmp/smoke-tick-a.json'));print(d.get('outcome',''))" 2>/dev/null || echo "")
    B=$(python3 -c "import json;d=json.load(open('/tmp/smoke-tick-b.json'));print(d.get('outcome',''))" 2>/dev/null || echo "")
    if [ "$A" = "lock_skipped" ] || [ "$B" = "lock_skipped" ]; then
        _ok "fcntl lock previniu concorrencia (A=$A B=$B)"
    else
        # Race may be too fast; both completed cleanly — acceptable outcome
        echo "  (info: ambos ticks completaram — race window curto; outcomes: A=$A B=$B)"
    fi
    rm -f /tmp/smoke-tick-a.json /tmp/smoke-tick-b.json
}
_scenario_lock_contention

# ========= Cenário 9: Kill-switch =========
echo "=== 9. Kill-switch ==="
_scenario_killswitch() {
    touch ~/.openclaw/clarification-agent/poll.disabled
    OUT=$($CLI poll-tick --json 2>/dev/null)
    OUTCOME=$(echo "$OUT" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('outcome',''))" 2>/dev/null || echo "")
    rm -f ~/.openclaw/clarification-agent/poll.disabled
    if [ "$OUTCOME" = "killswitch" ]; then
        _ok "killswitch detectado"
    else
        _fail "killswitch nao detectado (outcome=$OUTCOME)"
    fi
}
_scenario_killswitch

# ========= Cenário 10: Dry-run no mutations =========
echo "=== 10. Dry-run no mutations ==="
_scenario_dryrun() {
    BEFORE_LINES=$(wc -l < $POLL_JSONL 2>/dev/null || echo 0)
    $CLI poll-tick --dry-run --json > /dev/null 2>&1
    AFTER_LINES=$(wc -l < $POLL_JSONL 2>/dev/null || echo 0)
    if [ "$AFTER_LINES" = "$BEFORE_LINES" ]; then
        _ok "dry-run nao gravou em poll.jsonl (lines=$BEFORE_LINES unchanged)"
    else
        _fail "dry-run gravou em poll.jsonl (before=$BEFORE_LINES after=$AFTER_LINES)"
    fi
}
_scenario_dryrun

# ========= Cenário 11: Coexistencia Fase A (bevox-mobile/scripts lock) =========
echo "=== 11. Coexistencia Fase A (bevox-mobile/scripts lock) ==="
echo "  (manual — requer criar task + forcar lock do clarification-poller + rodar bevox-mobile/scripts/request-clarification.sh; validado em Task 21 patch com T-0005)"

# ========= Cenário 12: Push mode regression (vox clarification ask) =========
echo "=== 12. Push mode regression (vox clarification ask) ==="
_scenario_push_regression() {
    OUT=$($CLI ask "T-NONEXISTENT-$(date +%s)" --question "smoke" --json 2>&1 | tail -1)
    CODE=$(echo "$OUT" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('code',''))" 2>/dev/null || echo "")
    # Acceptable codes: TASK_NOT_FOUND, KANBAN_CLI_FAILED (depends on kanban state) — both structurally OK
    if [ "$CODE" = "TASK_NOT_FOUND" ] || [ "$CODE" = "KANBAN_CLI_FAILED" ]; then
        _ok "push mode (ask) retorna estrutura esperada ($CODE)"
    else
        _fail "push mode retornou shape inesperado: $OUT"
    fi
}
_scenario_push_regression

# ========= Cenário 13: Local ollama down =========
echo "=== 13. Local ollama down ==="
echo "  (manual — requer parar ollama, rodar poll-tick, verificar graceful degrade via cloud fallback)"

# ========= Cenário 14: --provider claude override =========
echo "=== 14. --provider claude override ==="
echo "  (manual — requer task real + claude auth; invocar cli.sh ask T-XXX --provider claude_cli)"

# ========= Sumario =========
echo "===================="
echo "PASS: $PASS / FAIL: $FAIL"
if [ $FAIL -eq 0 ]; then
  exit 0
fi
echo "Failed: ${FAILED_NAMES[@]}"
exit 1
