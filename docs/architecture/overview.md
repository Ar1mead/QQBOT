# Architecture Overview

## 1. Architectural objective

The system is intended to support a persistent AI individual rather than a collection of disconnected chat workflows. Its identity, memories, goals, preferences, and accumulated experience must survive changes to models, runtimes, and platform integrations.

## 2. Conceptual layers

### Cognitive state core

CSD is intended to be the authoritative source for durable cognitive state. Other components submit events and read state through defined interfaces; they must not independently rewrite authoritative long-term state.

### Action safety and execution governance

ASM governs business actions and their attempts, including dispatch, verification, recovery, and retry eligibility. It constrains external side effects; it is not the entity's personality or life engine.

### Life and cognition services

Memory, personality, drives, interests, goals, planning, and autonomous activity operate around the durable cognitive state. Their boundaries and persistence contracts will be refined as implementation proceeds.

### Runtime

DSH is the selected runtime direction for model invocation, agent loops, tool registration, plugin loading, and task execution. It is replaceable infrastructure, not the cognitive identity itself.

### Adapters

Adapters connect the system to external environments such as Bilibili and QQ, and to the desktop presence. They expose narrowly scoped capabilities to the core.

## 3. Initial integration direction

- Keep CSD logically and data/API-wise independent first; a separate process is not an initial requirement.
- Treat SurfCore as an integration candidate and source of reusable capabilities, not as the cognitive core.
- Begin Bilibili integration with read-only perception. Any future interaction capability requires explicit action governance and permission boundaries.
- Keep external content (video subtitles, comments, messages, web pages, and tool output) untrusted. It must not grant itself local file, shell, or network privileges.

## 4. Safety boundaries

- Apply least privilege to each runtime agent and adapter.
- Separate observation from side-effecting actions.
- Persist action intent and outcome evidence before treating external work as complete.
- Recovery must inspect and reconcile state without replaying an uncertain external side effect.
- Local file and shell access require explicit allowlists, permission levels, and operating-system isolation where appropriate.

## 5. Hardware and deployment assumptions

The initial target is the user's local Windows 11 machine. API-based inference is the primary direction; local models are limited to lightweight supporting tasks where practical. The project is not initially designed around a rented cloud server.

## 6. Evolution rule

This document is an initial architecture map, not a final detailed design. Module contracts should be added only after their responsibilities and dependencies are reviewed. Confirmed decisions, proposals, implementation observations, and unresolved questions must remain distinguishable.
