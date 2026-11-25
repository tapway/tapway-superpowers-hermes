#!/usr/bin/env python3
"""Re-split tapway/tapway-superpowers hermes/plugin into this mirror.

Runs nightly (and on demand). Silent when the source has not moved; otherwise
it replaces the mirrored files, updates ``SOURCE.json``, commits, tags the
plugin version and pushes. A hand-edit here is overwritten, never merged.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_mirror import (  # noqa: E402
    GENERATED_FILES,
    GENERATED_PREFIXES,
    SOURCE_SUBTREE,
    source_url as _source_url,
    verify,
)

SOURCE_REPO = os.environ.get("SOURCE_REPO", "tapway/tapway-superpowers")
SOURCE_REF = os.environ.get("SOURCE_REF", "master")


def _sh(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _is_generated(path: str) -> bool:
    return path in GENERATED_FILES or path.startswith(GENERATED_PREFIXES)


def _plugin_version(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError(f"{path} has no version field")


def _mirrored_paths(root: Path) -> set[str]:
    listed = _sh("git", "-C", str(root), "ls-files")
    on_disk = {
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(root).parts
    }
    return {p for p in set(listed.splitlines()) | on_disk if p and not _is_generated(p)}


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "source"
        _sh("git", "clone", "--quiet", "--depth", "1", "--branch", SOURCE_REF,
            _source_url(SOURCE_REPO), str(source))
        commit = _sh("git", "-C", str(source), "rev-parse", "HEAD")

        state_path = ROOT / "SOURCE.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("commit") == commit:
            print(f"mirror up to date: {SOURCE_REPO}@{commit[:7]}")
            return 0

        extracted = Path(tmp) / "plugin"
        extracted.mkdir()
        archive = subprocess.run(
            ["git", "-C", str(source), "archive", f"HEAD:{SOURCE_SUBTREE}"],
            capture_output=True, check=True,
        )
        subprocess.run(["tar", "-x", "-C", str(extracted)], input=archive.stdout, check=True)

        version = _plugin_version(extracted / "plugin.yaml")

        # Remove mirrored files the source no longer has, then overlay the new tree.
        for relative in sorted(_mirrored_paths(ROOT)):
            (ROOT / relative).unlink(missing_ok=True)
        for path in extracted.rglob("*"):
            if path.is_dir():
                continue
            target = ROOT / path.relative_to(extracted)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)

        state.update({
            "repo": SOURCE_REPO,
            "ref": SOURCE_REF,
            "commit": commit,
            "version": version,
            "tag": f"v{version}",
            "tree": _sh("git", "-C", str(source), "rev-parse", f"HEAD:{SOURCE_SUBTREE}"),
        })
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

        findings = verify(commit, ROOT)
        if findings:
            print("refusing to publish: mirror does not match the source subtree")
            for finding in findings:
                print(f"  - {finding}")
            return 1

        _sh("git", "-C", str(ROOT), "add", "-A")
        if not _sh("git", "-C", str(ROOT), "status", "--porcelain"):
            print("no content change; nothing to publish")
            return 0

        _sh("git", "-C", str(ROOT), "-c", "user.name=CodeMAX",
            "-c", "user.email=codemax@tapway.com",
            "commit", "-m", f"sync(mirror): {state['tag']} @ {commit[:7]}")

        tag = state["tag"]
        if not _sh("git", "-C", str(ROOT), "tag", "--list", tag):
            _sh("git", "-C", str(ROOT), "-c", "user.name=CodeMAX",
                "-c", "user.email=codemax@tapway.com",
                "tag", "-a", tag, "-m", f"{state['repo']} {tag} @ {commit[:7]}")

        _sh("git", "-C", str(ROOT), "push", "origin", "HEAD:main")
        _sh("git", "-C", str(ROOT), "push", "origin", tag)
        print(f"published {tag} from {SOURCE_REPO}@{commit[:7]}")
        return 0


if __name__ == "__main__":
    sys.exit(main())