# AI Individual Project

> Repository: `Ar1mead/QQBOT`  
> Status: project bootstrap; implementation has not started.

## Purpose

Build a persistent AI individual with continuity of identity and experience, durable memory, evolving preferences and emotional state, self-generated goals, autonomous activity, and safe interaction with external platforms.

The runtime, model, and platform adapters are replaceable infrastructure. The long-lived cognitive state must remain independent of any one runtime or platform.

## Core areas

- `core/csd/` — authoritative long-term cognitive state.
- `core/asm/` — action safety, attempt lifecycle, verification, retry, and recovery.
- `core/life_engine/` — drives, interests, goals, planning, and autonomous activity.
- `core/memory/` — memory formation, retrieval, revision, and forgetting.
- `core/personality/` — identity, stable traits, and evolving preferences.
- `adapters/` — runtime and platform integrations such as DSH, SurfCore, Bilibili, and QQ.
- `docs/` — architecture, specifications, and technical decisions.
- `tests/` — automated tests.

## Current phase

1. Establish project documentation and preserve the status of existing specifications.
2. Inventory the actual local DSH and SurfCore versions and source trees.
3. Implement the smallest independently persistent and recoverable CSD core.
4. Integrate ASM and the autonomous life engine incrementally.
5. Add platform capabilities behind explicit permission boundaries, starting with read-only Bilibili access.

## Engineering principles

- Cognitive state is independent of the runtime and platform adapters.
- External side effects must be traceable and recoverable; recovery must not replay them.
- Untrusted platform content must never gain local machine privileges.
- Permissions are least-privilege and progressively granted.
- Confirmed specifications, proposals, assumptions, and unresolved questions must be labelled separately.
- No destructive changes to existing local installations without explicit approval.

## Specification status

This repository bootstrap does not declare CSD or ASM fully frozen. Previously confirmed ASM baselines remain confirmed; unresolved ASM-5.4 questions remain unresolved. See `docs/specifications/status.md`.
