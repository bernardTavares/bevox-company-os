#!/bin/bash
# cron-dispatcher.sh - Auto-dispatch de tasks ready
# Executar a cada 30 segundos via cron job interno do OpenClaw

echo "🔄 [$(date '+%H:%M:%S')] Cron-dispatcher cycle started"

KANBAN_CLI="$HOME/.openclaw/kanban-tasks/cli.sh"
DISPATCHER_CLI="$HOME/.openclaw/dispatcher-agent/cli.sh"

# Get all projects with ready tasks
READY_TASKS=$($KANBAN_CLI task list --json 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
tasks = data.get('tasks', [])
ready = [t for t in tasks if t['status'] == 'ready' and not t.get('blocked')]
projects = set(t['project'] for t in ready if t.get('project'))
for p in sorted(projects):
    print(p)
" 2>/dev/null)

if [ -z "$READY_TASKS" ]; then
    exit 0  # No ready tasks
fi

# For each project with ready tasks, launch next
for PROJECT in $READY_TASKS; do
    echo "🚀 Launching next ready task for project: $PROJECT"
    
    # Check if there's already an in_progress task for this project
    IN_PROGRESS=$($KANBAN_CLI task list --json 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
tasks = data.get('tasks', [])
in_progress = [t for t in tasks if t['status'] == 'in_progress' and t.get('project') == '$PROJECT']
print(len(in_progress))
" 2>/dev/null)
    
    if [ "$IN_PROGRESS" != "0" ]; then
        echo "⏸️  Project $PROJECT already has $IN_PROGRESS task(s) in_progress. Skipping."
        continue
    fi
    
    # Launch next task for this project
    $DISPATCHER_CLI next --launch --project "$PROJECT" 2>&1 || {
        echo "⚠️  Failed to launch task for project $PROJECT"
        continue
    }
    
    echo "✅ Task launched for project $PROJECT"
done

echo "✅ Cron-dispatcher cycle completed"
