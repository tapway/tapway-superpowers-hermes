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
GENERATED_FILES = {"README.md", "SOURCE.json", ".gitignore"}
SOURCE_SUBTREE = "hermes/plugin"


def source_url(repo: str) -> str:
    """Git URL for ``owner/name``; a local path or URL is used verbatim (tests)."""
    if repo.startswith(("/", "./", "../")) or "://" in repo:
        return repo
    return f"https://github.com/{repo}.git"


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
            source_url(repo), str(clone),
        )
        _sh("git", "-C", str(clone), "fetch", "--quiet", "--depth", "1", "origin", commit)
        hashes = _tree_hashes(clone, f"{commit}:{SOURCE_SUBTREE}")
    if not hashes:
        raise RuntimeError(f"{repo}:{commit} has no {SOURCE_SUBTREE}/ tree")
    return hashes


def mirror_hashes(root: Path = ROOT) -> dict[str, str]:
    """path -> blob sha for the *working tree* (not HEAD).

    Hashing the worktree rather than the committed tree catches a hand-edit
    before it is published, and lets the reconcile step verify the files it
    just wrote (its HEAD is still the previous mirror).
    """
    paths: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative.startswith(".git/") or _is_generated(relative):
            continue
        paths.append(relative)
    if not paths:
        return {}
    result = subprocess.run(
        ["git", "-C", str(root), "hash-object", "--stdin-paths"],
        input="\n".join(paths) + "\n",
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git hash-object failed: {result.stderr.strip()}")
    return dict(zip(paths, result.stdout.split()))


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