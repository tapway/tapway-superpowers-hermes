# tapway-superpowers-hermes

**Generated mirror — do not edit.**

This repository is the Hermes Agent plugin for
[`tapway/tapway-superpowers`](https://github.com/tapway/tapway-superpowers),
published as a standalone git repo because Hermes cannot update a
subdirectory install (it is copied without `.git`) and cannot install the
monorepo root (the scanner flags `codex/`, `hooks/` and `tests/`, a *dangerous*
verdict).

- Source of truth: [`hermes/plugin/`](https://github.com/tapway/tapway-superpowers/tree/master/hermes/plugin)
- Every file here other than this README, `SOURCE.json`, `scripts/` and
  `.github/` must match the source subtree blob-for-blob.
- `SOURCE.json` records the source commit, version and tree hash that this
  mirror was split from.

## Install

```bash
hermes plugins install tapway/tapway-superpowers-hermes --enable
hermes plugins auto-update on      # once per profile
```

## How it stays current

| Workflow | What it does |
|---|---|
| `Reconcile mirror` (nightly) | Clones the source `master`, re-splits `hermes/plugin`, replaces the mirrored files, updates `SOURCE.json`, commits, tags `v<plugin.yaml version>`, pushes. |
| `Mirror integrity` (push/PR) | Fails if any mirrored file differs from the source subtree at the recorded commit, or if `plugin.yaml` disagrees with `SOURCE.json`. |

A hand-edit here is overwritten by the next reconcile; open a PR against the
source repo instead.