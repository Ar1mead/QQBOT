# Software Baseline

This file separates locally observed version metadata from upstream release information. A matching version string does not prove that the complete local working tree is identical to the upstream tag.

| Component | Local version evidence | Upstream reference | Status |
|---|---|---|---|
| DeepSeek Harness (DSH) | `0.2.2-rc.3` (owner-reported) | SurfCore v0.8.8 README says DSH rc.3 can install, but feature regression is incomplete | Local DSH package/version still to be independently inspected |
| SurfCore | `package.json` reports `0.8.8` (checked in local PowerShell output) | Tag `v0.8.8`, commit `0deb8261afe4c31b3127759ee4de36a1439cf422` | Version string matches; local Git HEAD and working-tree identity still unverified |

## Upstream facts checked

- Public repository: https://github.com/Mieksido/surfcore
- The public `v0.8.8` tag resolves to commit `0deb8261afe4c31b3127759ee4de36a1439cf422`.
- The `v0.8.8` tag's `package.json` declares version `0.8.8`.
- The public `main` branch has moved to `0.8.9`; it must not be confused with the user's local `0.8.8` installation.
- The v0.8.8 README states that DSH `0.2.1-rc.2` or newer is required and that `0.2.2-rc.3` can install, but its functionality has not completed full regression testing. Installation compatibility is not equivalent to verified functional compatibility.

## Remaining local verification

- Inspect the local SurfCore Git HEAD and compare it with the upstream `v0.8.8` commit.
- Check whether the local working tree contains uncommitted or untracked changes.
- Independently inspect the installed DSH version and build/commit metadata if available.
- Record Node.js and relevant dependency/runtime versions before compatibility testing.

## Git ownership warning

The initial local `git status` / `git log` commands were blocked by Git's `dubious ownership` safety check: the `.git` directory is owned by `S-1-5-32-544`, while the current PowerShell user has a different SID. No Git configuration was changed. For a one-command inspection, use `git -c safe.directory='<path>' ...` rather than adding a persistent global exception before the ownership is understood.

Do not treat a version label alone as proof that the local source is identical to the upstream release.