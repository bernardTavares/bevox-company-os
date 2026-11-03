#!/usr/bin/env python3
"""
detect-new-topics.py - Detecta quando BevoxBot é adicionado a novo tópico e solicita contexto
Executar a cada 5 min via cron

Usage: python3 ~/.openclaw/scripts/detect-new-topics.py
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

KNOWN_SESSIONS_FILE = Path.home() / ".openclaw" / "scripts" / "known-sessions.json"

def load_known_sessions():
    """Load known sessions from file."""
    if not KNOWN_SESSIONS_FILE.exists():
        return set()
    
    try:
        with open(KNOWN_SESSIONS_FILE, 'r') as f:
            data = json.load(f)
            return set(data.get('sessions', []))
    except:
        return set()

def save_known_sessions(sessions):
    """Save known sessions to file."""
    KNOWN_SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(KNOWN_SESSIONS_FILE, 'w') as f:
        json.dump({'sessions': list(sessions), 'updated_at': datetime.now().isoformat()}, f, indent=2)

def main():
    print(f"🔍 Checking for new topics at {datetime.now().isoformat()}...")
    
    # Load known sessions
    known_sessions = load_known_sessions()
    print(f"📚 Known sessions: {len(known_sessions)}")
    
    # For MVP, we'll just initialize the file if it doesn't exist
    if not KNOWN_SESSIONS_FILE.exists():
        print("📝 Initializing known sessions file...")
        save_known_sessions(known_sessions)
        print("✅ Known sessions file created. Run again after new topics are created.")
        return
    
    # In production, this would:
    # 1. Call sessions_list tool to get current sessions
    # 2. Compare with known sessions
    # 3. For each new session, send onboarding message via sessions_send
    # 4. Update known sessions file
    
    print("ℹ️  MVP mode: File-based tracking initialized. Full implementation requires OpenClaw tool integration.")
    print(f"📄 Known sessions file: {KNOWN_SESSIONS_FILE}")

if __name__ == "__main__":
    main()
