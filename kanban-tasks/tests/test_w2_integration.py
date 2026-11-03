"""Integration test for provision_knowledge against a real git fixture.

Spec: bevox-knowledge/35_specs/openclaw/2026-05-07-project-lifecycle-w2-v1.md
§Test plan — `test_w2_integration.py` (marker `integration`).

Spins up a temp git repo mimicking the bevox-knowledge layout (with the
real skill helpers symlinked from the user's bevox-knowledge clone), runs
`provision_knowledge` end-to-end, and asserts:

- 9 ADR-010 folders are committed in the worktree
- bootstrap branch exists
- commit hash returned matches HEAD of branch

Skipped automatically when:
- bevox-knowledge clone with the V1 skill helpers is not available
- bash is not on PATH
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from lib.provisioners.knowledge import (
    CANONICAL_FOLDERS,
    provision_knowledge,
)


def _real_skill_lib_or_skip():
    """Return Path to real skill lib, or None if not available."""
    bk = Path(
        os.environ.get("BEVOX_KNOWLEDGE_DIR")
        or os.environ.get("BEVOX_KNOWLEDGE_PATH")
        or str(Path.home() / "bevox-knowledge")
    )
    skill_lib = (
        bk / "99_templates" / "skill-bevox-knowledge-contribute" / "lib"
    )
    if not skill_lib.is_dir():
        return None
    for h in ("slot_resolve.sh", "git_open_draft.sh", "git_commit_push.sh"):
        if not (skill_lib / h).is_file():
            return None
    return skill_lib


@unittest.skipIf(
    _real_skill_lib_or_skip() is None,
    "bevox-knowledge skill helpers (V1+) not present locally",
)
@unittest.skipIf(
    shutil.which("bash") is None,
    "bash not available",
)
class TestProvisionKnowledgeIntegration(unittest.TestCase):
    """End-to-end provision_knowledge against a temp bevox-knowledge fixture.

    Creates a self-contained git repo with origin pointing at a bare repo,
    so `git_commit_push.sh` can actually push. Mirrors the canonical
    `99_templates/skill-bevox-knowledge-contribute/lib/` directory.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="w2-integ-")
        self.bare = Path(self.tmp) / "origin.git"
        self.bk = Path(self.tmp) / "bk"
        self.bk.mkdir()
        # Bare origin
        subprocess.run(
            ["git", "init", "--bare", str(self.bare)],
            check=True, capture_output=True,
        )
        # Working clone seeded with one initial commit on main
        subprocess.run(
            ["git", "init", "-b", "main", str(self.bk)],
            check=True, capture_output=True,
        )
        # Configure local user (so commits work without global config)
        subprocess.run(
            ["git", "-C", str(self.bk), "config", "user.email", "test@example"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.bk), "config", "user.name", "Test"],
            check=True,
        )
        (self.bk / "README.md").write_text("# fixture\n")
        subprocess.run(
            ["git", "-C", str(self.bk), "add", "README.md"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(self.bk), "commit", "-q", "-m", "init"],
            check=True, capture_output=True,
        )
        subprocess.run(
            [
                "git", "-C", str(self.bk), "remote",
                "add", "origin", str(self.bare),
            ],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.bk), "push", "-u", "origin", "main"],
            check=True, capture_output=True,
        )
        # Mirror the skill helpers via symlinks (cheap; preserves shebang).
        real_lib = _real_skill_lib_or_skip()
        target = (
            self.bk / "99_templates" / "skill-bevox-knowledge-contribute" / "lib"
        )
        target.mkdir(parents=True)
        for f in real_lib.iterdir():
            if f.is_file():
                (target / f.name).symlink_to(f)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        # Clean up worktrees from /tmp/bevox-knowledge-worktrees if any
        # (helper writes there; removing the source repo invalidates them)
        wt_root = Path("/tmp/bevox-knowledge-worktrees")
        for wt in wt_root.glob("draft__openclaw-knowledge-bootstrap*"):
            shutil.rmtree(wt, ignore_errors=True)

    def test_end_to_end_creates_9_folders_and_pushes(self):
        # `openclaw` is in CANONICAL_SLOTS per slot_resolve.sh, so use it.
        result = provision_knowledge("openclaw", bk_path=self.bk)

        self.assertEqual(result.state, "provisioned")
        self.assertEqual(result.branch, "draft/openclaw-knowledge-bootstrap")
        self.assertIsNotNone(result.commit_hash)
        self.assertEqual(len(result.folders_created), 9)

        # Verify the bare repo received the branch
        check = subprocess.run(
            [
                "git", "-C", str(self.bare),
                "rev-parse", "draft/openclaw-knowledge-bootstrap",
            ],
            capture_output=True, text=True,
        )
        self.assertEqual(check.returncode, 0,
                         f"branch not pushed: {check.stderr}")
        pushed_hash = check.stdout.strip()
        self.assertEqual(pushed_hash, result.commit_hash)

        # Verify all 9 folders + .gitkeep exist on that branch
        ls_tree = subprocess.run(
            [
                "git", "-C", str(self.bare),
                "ls-tree", "-r", "--name-only",
                "draft/openclaw-knowledge-bootstrap",
            ],
            capture_output=True, text=True, check=True,
        )
        files = ls_tree.stdout.splitlines()
        for folder in CANONICAL_FOLDERS:
            self.assertIn(
                f"{folder}/openclaw/.gitkeep",
                files,
                f"missing {folder}/openclaw/.gitkeep on draft branch",
            )


if __name__ == "__main__":
    unittest.main()
