# Software Baseline

This file separates locally observed version metadata from upstream release information. A matching version string does not prove that the complete local working tree is identical to the upstream tag.

| Component | Local version evidence | Upstream reference | Status |
|---|---|---|---|
| DeepSeek Harness (DSH) | `0.2.2-rc.3` (owner-reported; local package metadata and Git HEAD not yet inspected) | Tag `dsh-v0.2.2-rc.3`, commit `38a6a5c965aa99ab525161efb7cc5cf1fe62fced` | Upstream release identity confirmed; local checkout identity and cleanliness remain to be verified |
| SurfCore | Local `package.json` reports `0.8.8`; local HEAD is `0deb8261afe4c31b3127759ee4de36a1439cf422`; `git describe` reports `v0.8.8`; status reports clean `main...origin/main` | Tag `v0.8.8`, commit `0deb8261afe4c31b3127759ee4de36a1439cf422` | Fully verified: local HEAD matches the upstream release tag and working tree is clean |

## Upstream facts checked

- DSH public repository: https://github.com/deepseek-ai/deepseek-harness
- The DSH tag `dsh-v0.2.2-rc.3` resolves to commit `38a6a5c965aa99ab525161efb7cc5cf1fe62fced`. The tag listing dates this release candidate to 2026-11-13.
- SurfCore public repository: https://github.com/Mieksido/surfcore
- The SurfCore `v0.8.8` tag resolves to commit `0deb8261afe4c31b3127759ee4de36a1439cf422`.
- SurfCore `v0.8.8` README states that DSH `0.2.1-rc.2` or newer is required and that `0.2.2-rc.3` can install, but its functionality had not completed full regression testing in that release's compatibility statement. Installation compatibility is not equivalent to verified functional compatibility.
- The public SurfCore `main` branch had moved to `0.8.9` at the time of the earlier check; it must not be confused with the user's local `0.8.8` installation.

## Remaining local verification

- Inspect the local DSH Git HEAD, package/build metadata, and working-tree status.
- Check whether the local DSH checkout corresponds to the upstream `dsh-v0.2.2-rc.3` commit.
- Record Node.js and relevant dependency/runtime versions before compatibility testing.
- After local DSH verification, perform targeted compatibility checks against SurfCore v0.8.8 rather than assuming the README's minimum-version statement guarantees full integration.

## Git ownership warning

The initial local SurfCore `git status` / `git log` commands were blocked by Git's `dubious ownership` safety check: the `.git` directory is owned by `S-1-5-32-544`, while the current PowerShell user has a different SID. No Git configuration was changed. A one-command inspection succeeded using the explicit path:
```powershell
git -c safe.directory='E:/deepseek（chajian）/SurfCore' -C 'E:/deepseek（chajian）/SurfCore' status --short --branch
```

Do not treat a version label alone as proof that the local source is identical to the upstream release.
