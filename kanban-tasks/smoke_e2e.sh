#!/usr/bin/env bash
# E2E smoke test do CLI kanban-tasks. Cobre ciclo completo.
# Uso: bash ~/.openclaw/kanban-tasks/smoke_e2e.sh
set -euo pipefail
KT="$HOME/.openclaw/kanban-tasks/cli.sh"

echo "==> reset"
rm -f ~/.openclaw/kanban-tasks/state.json ~/.openclaw/kanban-tasks/events.jsonl

echo "==> bootstrap"
$KT sprint init

echo "==> sprint show current"
$KT sprint show

echo "==> set project on current"
$KT sprint set-project sprint-1 openclaw
$KT sprint show

echo "==> set name on next"
$KT sprint set-name sprint-2 "Sprint 2 (follow-up)"

echo "==> create 5 tasks"
$KT task add "primeira" --project openclaw --epic E5
$KT task add "segunda" --sprint current --project mission-control
$KT task add "terceira via vox" --actor vox --project bevox-mobile
$KT task add "quarta no next" --sprint next
$KT task add "quinta com wave_ref" --epic E8 --wave E8/F3-snapshot-cron

echo "==> list current"
$KT task list --sprint current

echo "==> move T-0001 backlog->ready->in_progress->testing->done (wave-3 lifecycle)"
$KT task move T-0001 ready
$KT task move T-0001 in_progress
$KT task move T-0001 testing
$KT task move T-0001 done

echo "==> update T-0002 (description + epic)"
$KT task update T-0002 --description "atualizada via smoke" --epic E10

echo "==> archive T-0003 + list archived"
$KT task archive T-0003
$KT task list --archived

echo "==> unarchive T-0003 -> backlog"
$KT task unarchive T-0003 --status backlog
$KT task show T-0003

echo "==> resprint T-0005 -> next"
$KT task resprint T-0005 next
echo "-- next sprint tasks --"
$KT task list --sprint next

echo "==> project add 'test-project'"
$KT project add test-project
$KT project list

echo "==> close current sprint (non-interactive: move_current for all pending)"
$KT sprint close --non-interactive

echo "==> sprint show (new current)"
$KT sprint show

echo "==> sprint history"
$KT sprint history

echo "==> events tail --n 30"
$KT events tail --n 30

echo "==> events filter by actor=vox"
$KT events tail --actor-filter vox --n 10

echo "==> events filter by type=task_moved"
$KT events tail --type task_moved --n 10

echo "==> status"
$KT status

echo "==> rebuild idempotency"
$KT task list --sprint current --json > /tmp/kt-before.json
$KT sprint show --json > /tmp/kt-sprint-before.json
$KT rebuild
$KT task list --sprint current --json > /tmp/kt-after.json
$KT sprint show --json > /tmp/kt-sprint-after.json

# generated_at muda, mas tasks/sprints devem ser idênticos
if diff <(jq 'del(.tasks[].updated_at)' /tmp/kt-before.json 2>/dev/null || cat /tmp/kt-before.json) \
        <(jq 'del(.tasks[].updated_at)' /tmp/kt-after.json  2>/dev/null || cat /tmp/kt-after.json) > /dev/null; then
  echo "REBUILD TASKS OK"
else
  echo "REBUILD TASKS MISMATCH"
  diff /tmp/kt-before.json /tmp/kt-after.json || true
  exit 1
fi

echo "==> events.jsonl linha count"
wc -l ~/.openclaw/kanban-tasks/events.jsonl

echo ""
echo "==> WAVE-3 smoke: dev lifecycle"

echo "==> create T-W3 in current"
W3_ID=$($KT task add "wave-3 smoke E2E" --project openclaw --sprint current --json | python3 -c "import json,sys; print(json.load(sys.stdin)['task']['id'])")
echo "task id: $W3_ID"

echo "==> move backlog -> ready"
$KT task move $W3_ID ready

echo "==> block + list --blocked"
$KT task block $W3_ID --reason "esperando aprovacao"
$KT task list --blocked
COUNT=$($KT task list --blocked --json | python3 -c "import json,sys; print(len(json.load(sys.stdin)['tasks']))")
test "$COUNT" -ge 1 || { echo "FAIL: list --blocked vazio"; exit 1; }

echo "==> unblock"
$KT task unblock $W3_ID
COUNT=$($KT task list --blocked --json | python3 -c "import json,sys; print(len(json.load(sys.stdin)['tasks']))")
test "$COUNT" -eq 0 || { echo "FAIL: list --blocked nao vazio apos unblock"; exit 1; }

echo "==> ready -> in_progress -> testing (satellite)"
$KT task move $W3_ID in_progress
$KT task move $W3_ID testing
$KT events tail --n 5 --task $W3_ID --json | python3 -c "
import json, sys
events = json.load(sys.stdin)['events']
types = [e['type'] for e in events]
assert 'task_entered_testing' in types, f'satellite missing: {types}'
print('satellite testing OK')
"

echo "==> testing -> rejected sem reason (deve falhar)"
$KT task move $W3_ID rejected 2>/dev/null && { echo "FAIL: rejected sem reason aceito"; exit 1; } || echo "OK rejected sem reason barrado"

echo "==> testing -> rejected com reason"
$KT task move $W3_ID rejected --reason "scope cut"
$KT events tail --n 5 --task $W3_ID --json | python3 -c "
import json, sys
events = json.load(sys.stdin)['events']
types = [e['type'] for e in events]
assert 'task_rejected_with_reason' in types, f'satellite missing: {types}'
print('rejected satellite OK')
"
$KT task list --status rejected | grep -q "$W3_ID" || { echo "FAIL: rejected list missing"; exit 1; }

echo "==> reopen rejected -> in_progress"
$KT task reopen $W3_ID --to in_progress --reason "regression flagged"
$KT events tail --n 3 --task $W3_ID --json | python3 -c "
import json, sys
events = json.load(sys.stdin)['events']
types = [e['type'] for e in events]
assert 'task_reopened' in types, f'reopen missing: {types}'
print('reopen OK')
"

echo "==> force move (in_progress -> done sem testing)"
$KT task move $W3_ID done 2>/dev/null && { echo "FAIL: nao-whitelist aceito sem force"; exit 1; } || echo "OK barrado sem force"
$KT task move $W3_ID done --force --reason "demo skip testing"
$KT events tail --n 1 --task $W3_ID --json | python3 -c "
import json, sys
ev = json.load(sys.stdin)['events'][0]
assert ev.get('forced') is True, f'forced flag missing: {ev}'
print('forced flag OK')
"

echo "==> blocked task barrada de ir pra terminal (mesmo com --force --reason)"
$KT task reopen $W3_ID --to in_progress --reason "reopen pra teste blocked->terminal"
$KT task block $W3_ID --reason "esperando algo"
$KT task move $W3_ID done --force --reason "tentativa" 2>/dev/null && { echo "FAIL: blocked->terminal aceito"; exit 1; } || echo "OK blocked barrou terminal"
$KT task unblock $W3_ID

echo "==> archive auto-unblock"
$KT task block $W3_ID --reason "test archive auto-unblock"
$KT task archive $W3_ID
$KT events tail --n 3 --task $W3_ID --json | python3 -c "
import json, sys
events = json.load(sys.stdin)['events']
types = [e['type'] for e in events]
assert 'task_unblocked' in types, f'auto-unblock missing: {types}'
assert 'task_archived' in types
print('auto-unblock OK')
"

echo "==> set-dispatch-payload (replace + shallow merge top-level)"
$KT task add "dispatch test" --project openclaw --sprint current >/dev/null
DP_ID=$($KT task list --sprint current --json | python3 -c "
import json, sys
tasks = json.load(sys.stdin)['tasks']
for t in reversed(tasks):
    if t.get('title') == 'dispatch test':
        print(t['id']); break
")
$KT task set-dispatch-payload $DP_ID --payload '{"goal": "x", "spec_refs": ["a.md"]}'
# Shallow merge: goal preservado (key nao presente no payload novo),
# spec_refs substituido inteiro (NAO concatenado), ac adicionado.
$KT task set-dispatch-payload $DP_ID --payload '{"spec_refs": ["y.md"], "acceptance_criteria": ["z"]}' --merge
$KT task show $DP_ID --json | python3 -c "
import json, sys
t = json.load(sys.stdin)['task']
dp = t['dispatch_payload']
assert dp.get('goal') == 'x', f'goal perdido no merge: {dp}'
assert dp.get('spec_refs') == ['y.md'], f'spec_refs nao foi substituido por inteiro (shallow merge top-level): {dp}'
assert dp.get('acceptance_criteria') == ['z'], dp
print('dispatch_payload shallow merge OK')
"
echo "==> replay reconstroi dispatch_payload via events.jsonl"
# Snapshot pre-rebuild pra comparar apos
$KT task show $DP_ID --json > /tmp/kt-dp-before-rebuild.json
$KT rebuild >/dev/null
$KT task show $DP_ID --json > /tmp/kt-dp-after-rebuild.json
diff <(jq '.task.dispatch_payload' /tmp/kt-dp-before-rebuild.json 2>/dev/null || python3 -c "
import json; print(json.dumps(json.load(open('/tmp/kt-dp-before-rebuild.json'))['task']['dispatch_payload'], sort_keys=True, indent=2))
") \
     <(jq '.task.dispatch_payload' /tmp/kt-dp-after-rebuild.json 2>/dev/null || python3 -c "
import json; print(json.dumps(json.load(open('/tmp/kt-dp-after-rebuild.json'))['task']['dispatch_payload'], sort_keys=True, indent=2))
") > /dev/null && echo 'dispatch_payload replay OK' || { echo 'FAIL: payload drift apos rebuild'; exit 1; }
$KT task archive $DP_ID >/dev/null

echo "==> rebuild idempotente + schema_version=2"
$KT rebuild
python3 -c "
import json
s = json.load(open('$HOME/.openclaw/kanban-tasks/state.json'))
assert s.get('schema_version') == 2, f'schema_version={s.get(\"schema_version\")}'
print('schema_version=2 OK')
"
$KT status

echo ""
echo "==> WAVE-3 smoke PASSED"
echo ""
echo "==> ALL E2E PASSED"
