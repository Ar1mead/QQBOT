# AI Individual Project

> Repository: `Ar1mead/QQBOT`  
> Status: project bootstrap; implementation has not started.

## Purpose

Build a persistent AI individual with continuity of identity and experience, durable memory, evolving preferences and emotional state, self-generated goals, autonomous activity, and safe interaction with external platforms.

The individual should be able to initiate activities from its own evolving interests and internal state, rather than requiring every activity to be assigned by the user or triggered by a fixed schedule. One explicit goal is **autonomous journaling**: it may independently develop the inclination to write, decide whether and when to write, choose what to record, and stop without being required to produce an entry. Journaling is an optional self-initiated activity, not a daily quota or user-imposed task.

The runtime, model, and platform adapters are replaceable infrastructure. The long-lived cognitive state must remain independent of any one runtime or platform.

## Core areas

- `core/csd/` — authoritative long-term cognitive state.
- `core/asm/` — action safety, attempt lifecycle, verification, retry, and recovery.
- `core/life_engine/` — drives, interests, goals, planning, autonomous activity, and self-initiated activities such as journaling.
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
- Autonomous activities must be possible without user prompts or rigid recurring schedules; the system must also be able to choose not to act.
- Journaling must not be reduced to scheduled report generation: the individual can self-initiate it, choose its content and timing, or choose not to write.
- External side effects must be traceable and recoverable; recovery must not replay them.
- Untrusted platform content must never gain local machine privileges.
- Permissions are least-privilege and progressively granted.
- Confirmed specifications, proposals, assumptions, and unresolved questions must be labelled separately.
- No destructive changes to existing local installations without explicit approval.

## Documentation index

- [Architecture overview](docs/architecture/overview.md)
- [Specification status register](docs/specifications/status.md)
- [Software baseline](docs/inventory/software-baseline.md)
- [SurfCore v0.8.8 capability assessment and integration plan](docs/inventory/surfcore-capability-assessment.md)
- [Repository scope decision](docs/decisions/0001-repository-scope.md)

## Specification status

This repository bootstrap does not declare CSD or ASM fully frozen. Previously confirmed ASM baselines remain confirmed; unresolved ASM-5.4 questions remain unresolved. See `docs/specifications/status.md`.
