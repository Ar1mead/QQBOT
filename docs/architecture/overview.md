# Architecture Overview

## 1. Architectural objective

The system is intended to support a persistent AI individual rather than a collection of disconnected chat workflows. Its identity, memories, goals, preferences, and accumulated experience must survive changes to models, runtimes, and platform integrations.

The detailed current proposal is [Persistent Individual Runtime Model](individual-runtime-model.md). This overview is a short map; the detailed document describes state families, the ongoing cognition/action cycle, autonomy, trust boundaries, and staged development. Both remain proposals, not frozen specifications.

## 2. Conceptual layers

### CSD — durable state authority

CSD is the authoritative path for durable cognitive state, event history, accepted state transitions, snapshots, and recovery. Cognitive services may propose interpretations or updates, but may not bypass CSD and directly rewrite authoritative state. CSD persistence mechanics and CSD's semantic state model are distinct design concerns.

### Cognitive services

Perception, interpretation, memory, self-model/personality, affect/drives, relationships, deliberation, and planning operate on evidence and current state. Their outputs are proposals with provenance and uncertainty; accepted durable changes pass through CSD.

### Life engine

The life engine coordinates ongoing internal activity: reviewing current state, identifying salient matters, forming or revisiting candidate intentions, choosing an activity, and reflecting on outcomes. A wake-up is only an opportunity to evaluate; it must not force a task. Acting, waiting, revising, stopping, declining, and doing nothing are valid outcomes.

### ASM — action governance

ASM governs external side effects and their lifecycle, including authorization, attempts, dispatch, verification, retry eligibility, and recovery. The life engine requests actions but cannot bypass ASM. ASM is not the individual's personality or planning system.

### Runtime

DSH is the initial runtime direction for model invocation, agent sessions, and tool integration. It is replaceable infrastructure, not the cognitive identity itself. Model output is evidence or a proposal, not privileged state mutation.

### Adapters

Adapters connect the core to environments such as Bilibili, QQ, and desktop presence. They expose narrowly scoped observation, presentation, and action capabilities. Side-effecting capabilities must be governed through ASM.

## 3. Initial integration direction

- Keep CSD logically and data/API-wise independent first; a separate process is not an initial requirement.
- Treat SurfCore as an integration candidate and source of reusable capabilities, not as the cognitive core.
- Begin Bilibili integration with read-only perception. Add audio perception before claiming broad video understanding.
- Treat diary writing as an optional, self-initiated activity, not a scheduled report or mandatory routine.
- Keep external content (video subtitles, comments, messages, web pages, and tool output) untrusted. It must not grant itself local file, shell, or network privileges.
- Distinguish event history, interpretations, memories, preferences, affect, goals, commitments, and diary artifacts.

## 4. Safety boundaries

- Apply least privilege to each runtime agent and adapter.
- Separate observation from side-effecting actions.
- Persist action intent and outcome evidence before treating external work as complete.
- Route all external side effects through ASM.
- Recovery must inspect and reconcile state without replaying an uncertain external side effect.
- Local file and shell access require explicit allowlists, permission levels, and operating-system isolation where appropriate.

## 5. Hardware and deployment assumptions

The initial target is the user's local Windows 11 machine. API-based inference is the primary direction; local models are limited to lightweight supporting tasks where practical. The project is not initially designed around a rented cloud server. Prefer a modular local application before introducing multiple processes or services.

## 6. Evolution rule

This document and the detailed runtime model are architecture proposals, not frozen CSD/ASM specifications. Module contracts should be refined only after responsibilities and dependencies are reviewed. Confirmed decisions, proposals, implementation observations, and unresolved questions must remain distinguishable.
