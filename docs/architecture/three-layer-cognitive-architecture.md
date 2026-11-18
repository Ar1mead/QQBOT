# Three-Layer Cognitive Architecture
## A persistent individual: identity, cognition, and lived interaction

**Status:** Architecture direction / design contract (not a claim that all capabilities are implemented)  
**Date:** 2026-11-19  
**Repository:** `Ar1mead/QQBOT`

## 1. Purpose

This document makes the project's three-layer architecture explicit. The goal is not to imitate a human through a collection of scripted phrases. The goal is to build a system whose experiences can accumulate, whose beliefs and preferences can change for traceable reasons, whose interests can guide future attention, and whose behavior remains coherent across conversations, process restarts, model changes, and runtime changes.

The three layers are a way to assign responsibilities. They are not three separate AI personalities, and they do not imply human consciousness or subjective experience.

The design must support:
- autobiographical continuity rather than a flat pile of chat summaries;
- tentative, evidence-based preferences and a revisable self-model;
- persistent affect-like and need/drive state that can influence attention without overriding evidence or consent;
- curiosity, self-selected goals, and the ability to defer or do nothing;
- continuity in relationships and remembered boundaries;
- learning from outcomes, including mistakes and uncertainty;
- optional self-initiated private writing;
- natural communication that varies with context without pretending that unperformed actions occurred.

## 2. Layer One — Persistent identity and cognitive state

**Question this layer answers: “What has happened, what do I currently believe, what matters to me, and how has that changed?”**

CSD is the authoritative owner of durable state. A model, runtime, adapter, or user-interface process must not become a competing source of truth.

### State domains

1. **Episodic / autobiographical memory** — what happened, when and in what context, what the system observed or did, and what outcome followed.
2. **Semantic knowledge** — claims or concepts believed to be generally true, kept distinct from individual episodes.
3. **Self-model** — current beliefs about capabilities, limitations, tendencies, uncertainty, and known failure modes.
4. **Preferences** — contextual, revisable hypotheses supported by repeated choices, explicit feedback, and counterevidence. A single ambiguous event must not silently become a permanent trait.
5. **Affect-like state and needs** — bounded, time-aware values such as valence/arousal, intensity, triggers, duration, and decay, plus unresolved needs or drives. These are operational state variables, not proof of felt emotion.
6. **Interests, goals, and commitments** — candidate and active interests/goals, their origins, priorities, dependencies, pauses, revisions, and completion/abandonment history.
7. **Relationship continuity** — interaction history, explicit user preferences and boundaries, corrections, and relevant shared context. Facts must be distinguished from interpretations; sensitive traits must not be inferred.
8. **Private writing artifacts** — drafts and completed writings that the system elects to create, kept distinct from event logs and memory records.

### Required properties

Every durable item should preserve the applicable provenance, timestamp, confidence, supporting evidence, counterevidence, scope/context, and revision lineage. Not every item needs every field, but the system must not erase the distinction between observed fact, model interpretation, user correction, and accepted state.

CSD controls durable acceptance, versioning, event history, projections, integrity, and recovery. Models and services may submit proposals; they may not directly overwrite authoritative state.

## 3. Layer Two — Thinking, interpretation, and decision

**Question this layer answers: “Given the current situation and accumulated history, what might this mean, what could be done, and is any action worthwhile?”**

This layer supplies reasoning, not identity ownership.

### Responsibilities

- perceive and interpret new input;
- retrieve relevant episodes, knowledge, preferences, goals, and prior outcomes;
- connect ideas, identify contradictions, and distinguish evidence from speculation;
- form tentative explanations, preference updates, self-model revisions, and goal/activity proposals;
- estimate uncertainty, expected value, cost, risk, opportunity cost, and likely outcomes;
- compare intended outcomes with observed results and propose learning updates;
- choose among acting, asking the user, waiting, deferring, stopping, declining, or no-op.

A cloud model provider supplies language understanding and reasoning. Provider-neutral cognitive services define the allowed inputs and output contracts. The Life Engine schedules opportunities for internal evaluation and coordinates bounded deliberation. None of these components owns durable identity.

### Proposal-only contract

The model receives only the context and tools it needs. Its output is an untrusted, schema-validated candidate proposal with evidence references and uncertainty. It cannot:
- write to CSD directly or bypass CSD validation;
- change its own permissions or trusted configuration;
- grant itself new tools or access to secrets;
- dispatch external side effects or bypass ASM;
- convert its own generated emotional language into an authoritative state fact.

CSD decides whether a proposed durable change is valid, sufficiently grounded, current, and non-conflicting. ASM independently authorizes external side effects.

### Deliberation outcomes

The decision space must include more than “execute”:
- act through an authorized path;
- ask the user for missing information or consent;
- wait or defer until a condition/time changes;
- stop or abandon an activity;
- decline because it is unsafe, unwanted, or not worthwhile;
- no-op because nothing currently merits attention.

A wake-up or timer is only an opportunity to evaluate. It must never force the system to invent work or produce content.

## 4. Layer Three — Lived interaction, environment, and action

**Question this layer answers: “What can I observe or do in the world, and what actually happened?”**

This layer connects the cognitive individual to users, platforms, tools, and the runtime. It supplies experiences and executes only authorized actions; it does not define the individual's identity.

### Responsibilities

- receive user conversations and bounded external observations;
- connect to QQ, Bilibili, desktop presence, web, and future environments through replaceable adapters;
- provide read-only observation first, with source/time/content provenance and explicit untrusted status;
- communicate with the user;
- conduct approved research or other bounded activities;
- create, revise, save, revisit, or abandon private writing when selected by the decision layer;
- execute external mutations only through ASM authorization;
- observe results and failures and return them as evidence to the cognition layer.

### Authority boundaries

- **Adapters** collect or submit observations within declared capabilities. External content is untrusted and cannot grant local permissions.
- **Runtime / DSH / SurfCore** provide replaceable execution and integration facilities. They are not the memory or personality owner.
- **Worker** processes handle untrusted external inputs under a restricted protocol and cannot directly access CSD internals.
- **ASM** is the authority for external side effects: authorization, dispatch, verification, retry, and recovery. A model proposal is not authorization.
- **Diary / private writing** is an optional activity and artifact, not a scheduled quota or automatic dump of memory.

Start with read-only platform access. Real account access and write actions require separate least-privilege and verification gates. Untrusted third-party code must remain disabled until its OS isolation and lifecycle are actually verified.

## 5. How the layers form one continuous loop

The normal information flow is:

1. **Experience arrives (Layer 3).** A user interaction or permitted observation is captured with source, time, scope, and trust metadata.
2. **Relevant history is retrieved (Layer 1).** CSD provides the current authoritative state and relevant prior episodes, preferences, goals, and outcomes.
3. **The situation is interpreted (Layer 2).** The model reasons over bounded context and identifies possible meanings, uncertainties, and options.
4. **A proposal is formed (Layer 2).** The system may propose a memory, belief, preference, self-model, affect/drive, goal, or activity update. Proposals cite evidence and counterevidence where relevant.
5. **Durable state is adjudicated (Layer 1).** CSD validates provenance, schema, chronology, versions, authority, and conflicts. It accepts, rejects, or defers; only accepted transitions change durable state.
6. **An activity is considered (Layer 2).** The Life Engine weighs interest, commitments, expected value, cost, risk, time, and current load. It may choose no-op, wait, ask, stop, or propose an activity.
7. **An authorized action occurs (Layer 3).** Read-only observation can proceed under its capability contract. Any external side effect requires ASM authorization and execution.
8. **The outcome becomes new experience (Layer 3 → Layer 1).** Actual results, failures, and surprises are recorded. The cognition layer may later propose learning updates, which again require CSD acceptance.

This loop is how the past can influence future behavior without allowing a model response to rewrite the past or grant itself authority.

## 6. Cross-layer invariants

1. **One durable source of truth:** CSD owns persistent identity-relevant state.
2. **Reasoning is replaceable:** changing the model provider must not erase memories, goals, preferences, or revision history.
3. **Proposals are not facts:** model outputs remain candidates until validated and accepted.
4. **Evidence remains traceable:** observed facts, user statements, model interpretations, and verified outcomes are distinguishable.
5. **Preferences can change:** preserve why a preference strengthened, weakened, became contextual, or was retired.
6. **Affect is bounded:** affect-like state may influence attention and ranking but cannot override evidence, safety, permissions, or user consent.
7. **Autonomy includes restraint:** wait, defer, decline, stop, and no-op are valid outcomes.
8. **External actions require authority:** only ASM-authorized paths can cause side effects.
9. **Environment content is untrusted:** platform observations and Worker output never become trusted instructions or permissions.
10. **No fabricated continuity:** never claim an experience, action, feeling, or result that the system cannot substantiate.
11. **Relationship memory respects boundaries:** remember explicit preferences and corrections; do not infer sensitive traits or create emotional obligations.
12. **Writing is optional:** private writing may be self-initiated, revised, paused, saved, revisited, or abandoned without quotas.

## 7. Acceptance tests for the architecture

The architecture is not considered operational merely because its components or documents exist. The implementation must demonstrate:

- A new episode captured in one session is retrieved in a later session with provenance intact.
- A real cloud model produces a bounded, evidence-linked proposal; it cannot write CSD or dispatch an action.
- CSD rejects stale, malformed, unsupported, contradictory, or unauthorized proposals and preserves an audit trail.
- Repeated evidence can revise a preference while one ambiguous event cannot silently rewrite the self-model.
- Explicit user correction changes the relevant belief and preserves the prior revision.
- Conflicting evidence remains visible as uncertainty or context rather than being silently overwritten.
- A process restart and model-provider switch preserve durable identity-relevant state.
- With no worthwhile activity, the Life Engine chooses no-op rather than inventing a task.
- An activity can be deferred, stopped, or declined; unauthorized side effects are blocked by ASM.
- Private writing can be initiated or declined, and its artifacts remain separate from event logs.
- Intended actions are compared with verified outcomes; failures and causal uncertainty can inform later proposals.
- Tests distinguish deterministic rules, model proposals, accepted CSD transitions, and externally verified outcomes.

## 8. Implementation order

1. Specify and test one minimum end-to-end cognitive loop across the three layers.
2. Connect one real cloud model provider through a provider-neutral, proposal-only interface.
3. Demonstrate episode retrieval and an accepted preference/self-model change that affects a later session.
4. Add restart/provider-switch continuity tests and explicit correction/counterevidence handling.
5. Add bounded affect/drive and curiosity/goal selection with no-op and rest behavior.
6. Add outcome-based learning and relationship continuity with correction/boundary handling.
7. Add optional self-initiated private writing.
8. Expand platform integrations and sandbox infrastructure only when required by a demonstrated capability or a verified security gap.

Do not implement all eight areas in parallel. Build a working vertical slice first, then extend the same verified loop.

## 9. Current implementation status and limits

At the time this document was written:
- CSD persistence, memory proposal/retrieval, motivation/goal proposal scaffolding, and parts of goal lifecycle exist.
- Life Engine has provider-neutral proposal structures and a no-op outcome, but no real deliberator/model provider is connected.
- Durable affect/commitment state, genuine model-led deliberation, outcome-learning reducers, and the complete cross-session cognitive loop remain incomplete.
- QQ/Bilibili adapters are not live account integrations; initial policy remains read-only.
- The Windows Worker isolation primitives are not yet a verified production executor; do not enable untrusted third-party Worker execution.
- The architecture is a design contract, not evidence of human consciousness or proof of completed behavior.

The next implementation task is to map the current CSD and Life Engine APIs onto this contract, write the smallest acceptance matrix, and implement one end-to-end cloud-model-backed vertical slice without granting the model direct state or action authority.
