# AI Individual Project

> Repository: `Ar1mead/QQBOT`  
> Status: architecture and isolated CSD reference work in progress; not production-ready and not merged to main.

## Purpose

Build a persistent AI individual with continuity of identity and experience, durable memory, evolving preferences and emotional state, self-generated goals, autonomous activity, and safe interaction with external platforms.

The individual should be able to initiate activities from its own evolving interests and internal state, rather than requiring every activity to be assigned by the user or triggered by a fixed schedule. One explicit goal is **autonomous journaling**: it may independently develop the inclination to write, decide whether and when to write, choose what to record, and stop without being required to produce an entry. Journaling is an optional self-initiated activity, not a daily quota or user-imposed task.

The runtime, model, and platform adapters are replaceable infrastructure. The long-lived cognitive state must remain independent of any one runtime or platform.

## Core areas

- `core/csd/` — authoritative long-term cognitive state.
- `core/asm/` — action safety, attempt lifecycle, verification, retry, and recovery.
- `core/life_engine/` — drives, interests, goals, deliberation, planning, autonomous activity, and self-initiated activities such as journaling.
- `core/memory/` — memory formation, retrieval, revision, consolidation, and forgetting.
- `core/personality/` — identity, stable traits, self-model, and evolving preferences.
- `adapters/` — runtime and platform integrations such as DSH, SurfCore, Bilibili, and QQ.
- `docs/` — architecture, specifications, and technical decisions.
- `tests/` — automated tests.

## Current phase

1. Define the persistent-individual runtime model and module ownership.
2. Preserve and refine CSD/ASM specification status without promoting unresolved interpretations into rules.
3. Validate the isolated CSD persistence reference on the target Windows environment.
4. Implement the smallest useful cognitive state transitions, then memory, self-model, affect/drives, deliberation, and life-engine behavior.
5. Add platform capabilities behind explicit permission boundaries, starting with read-only Bilibili perception.

## Engineering principles

- Cognitive state is independent of the runtime and platform adapters.
- One authoritative path governs durable state transitions.
- Observations, interpretations, memories, preferences, affect, goals, commitments, and diary entries remain distinguishable.
- Autonomous activities must be possible without user prompts or rigid recurring schedules; the system must also be able to choose not to act.
- Journaling must not be reduced to scheduled report generation: the individual can self-initiate it, choose its content and timing, or choose not to write.
- External side effects must be traceable and recoverable; recovery must not replay them.
- Untrusted platform content must never gain local machine privileges.
- Permissions are least-privilege and progressively granted.
- Confirmed specifications, proposals, assumptions, and unresolved questions must be labelled separately.
- No destructive changes to existing local installations without explicit approval.

## Documentation index

- [Architecture overview](docs/architecture/overview.md)
- [Persistent individual runtime model](docs/architecture/individual-runtime-model.md)
- [CSD state authority and cognitive proposal boundary](docs/design/csd-state-authority-boundary.md)
- [CSD v0.1 and architecture reconciliation](docs/reports/csd-v0.1-architecture-reconciliation.md)
- [First cognitive-state vertical slice](docs/design/first-cognitive-state-vertical-slice.md)
- [First cognitive-state test contract](docs/design/first-cognitive-state-test-contract.md)
- [Vertical-slice storage and authority decision analysis](docs/design/vertical-slice-storage-decision-analysis.md)
- [CSD cognitive-slice implementation decisions](docs/design/csd-cognitive-slice-implementation-decision.md)
- [CSD cognitive-memory hosted test report 001](docs/reports/csd-cognitive-memory-hosted-test-report-001.md)
- [Grounded-memory v2 hosted test report 001](docs/reports/csd-grounded-memory-v2-hosted-test-report-001.md)
- [CSD cognitive slice hosted test report 002](docs/reports/csd-cognitive-slice-hosted-test-report-002.md)
- [Accepted-memory retrieval contract](docs/design/memory-retrieval-contract.md)
- [Memory proposal provider contract](docs/design/memory-proposal-provider-contract.md)
- [Claim-to-evidence grounding](docs/design/claim-to-evidence-grounding.md)
- [Grounded memory proposal v2](docs/design/grounded-memory-proposal-v2.md)
- [Accepted memory retrieval contract](docs/design/memory-retrieval-contract.md)
- [Semantic review boundary](docs/design/semantic-review-boundary.md)
- [Specification status register](docs/specifications/status.md)
- [Software baseline](docs/inventory/software-baseline.md)
- [SurfCore v0.8.8 capability assessment and integration plan](docs/inventory/surfcore-capability-assessment.md)
- [CSD minimal persistence vertical-slice proposal](docs/design/csd-minimal-persistence-proposal.md)
- [CSD persistence reference spike](core/csd/README.md)
- [CSD persistence spike test report 001](docs/reports/csd-persistence-spike-test-report-001.md)
- [CSD reference-prototype language decision](docs/decisions/0002-csd-reference-implementation-language.md)
- [Repository scope decision](docs/decisions/0001-repository-scope.md)

## Specification status

This repository does not declare CSD or ASM fully frozen. Previously confirmed ASM baselines remain confirmed; unresolved ASM-5.4 questions remain unresolved. See `docs/specifications/status.md`.
