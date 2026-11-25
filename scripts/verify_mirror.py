#!/usr/bin/env python3
"""Fail when this mirror drifts from tapway/tapway-superpowers hermes/plugin.

This repository is generated. The source of truth is
``tapway/tapway-superpowers``, subtree ``hermes/plugin``, at the commit
recorded in ``SOURCE.json``. Every file here must have the same git blob hash
as its source counterpart; the only files allowed to differ are this one, the
reconcile script, the workflows, ``README.md`` and ``SOURCE.json``.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
#: Paths this repo owns; everything else is mirrored content.
GENERATED_PREFIXES = (".github/", "scripts/")
GENERATED_FILES = {"README.md", "SOURCE.json"}
SOURCE_SUBTREE = "hermes/plugin"


def _sh(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _tree_hashes(repo: Path, rev: str) -> dict[str, str]:
    """path -> blob sha for a commit-ish (``git ls-tree -r``)."""
    hashes: dict[str, str] = {}
    for line in _sh("git", "-C", str(repo), "ls-tree", "-r", rev).splitlines():
        if not line.strip():
            continue
        meta, path = line.split("\t", 1)
        parts = meta.split()
        if len(parts) < 3 or parts[1] != "blob":
            continue
        hashes[path] = parts[2]
    return hashes


def _is_generated(path: str) -> bool:
    return path in GENERATED_FILES or path.startswith(GENERATED_PREFIXES)


def source_plugin_hashes(repo: str, commit: str) -> dict[str, str]:
    """Blob hashes of ``hermes/plugin`` at ``commit`` in the source repo."""
    with tempfile.TemporaryDirectory() as tmp:
        clone = Path(tmp) / "source"
        _sh(
            "git", "clone", "--quiet", "--filter=blob:none", "--no-checkout",
            f"https://github.com/{repo}.git", str(clone),
        )
        _sh("git", "-C", str(clone), "fetch", "--quiet", "--depth", "1", "origin", commit)
        hashes = _tree_hashes(clone, f"{commit}:{SOURCE_SUBTREE}")
    if not hashes:
        raise RuntimeError(f"{repo}:{commit} has no {SOURCE_SUBTREE}/ tree")
    return hashes


def mirror_hashes(root: Path = ROOT) -> dict[str, str]:
    tracked = _tree_hashes(root, "HEAD")
    return {path: sha for path, sha in tracked.items() if not _is_generated(path)}


def verify(commit: str | None = None, root: Path = ROOT) -> list[str]:
    """Return a list of human-readable drift findings (empty == in sync)."""
    source = json.loads((root / "SOURCE.json").read_text(encoding="utf-8"))
    commit = commit or source["commit"]
    expected = source_plugin_hashes(source["repo"], commit)
    actual = mirror_hashes(root)

    findings: list[str] = []
    for path in sorted(set(expected) - set(actual)):
        findings.append(f"missing: {path}")
    for path in sorted(set(actual) - set(expected)):
        findings.append(f"unexpected: {path} (not in the source subtree)")
    for path in sorted(set(expected) & set(actual)):
        if expected[path] != actual[path]:
            findings.append(f"differs: {path}")

    manifest = (root / "plugin.yaml").read_text(encoding="utf-8").splitlines()
    version = next(
        (line.split(":", 1)[1].strip() for line in manifest if line.startswith("version:")),
        "",
    )
    if version != source.get("version"):
        findings.append(f"plugin.yaml version {version!r} != SOURCE.json {source.get('version')!r}")
    return findings


def main() -> int:
    findings = verify()
    if findings:
        print("mirror integrity FAILED")
        for finding in findings:
            print(f"  - {finding}")
        print("Fix: run the Reconcile mirror workflow; never hand-edit this repo.")
        return 1
    source = json.loads((ROOT / "SOURCE.json").read_text(encoding="utf-8"))
    print(
        f"mirror OK: {source['repo']}@{source['commit'][:7]} "
        f"{SOURCE_SUBTREE} == v{source['version']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())