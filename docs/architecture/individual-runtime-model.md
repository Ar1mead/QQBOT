# Persistent Individual Runtime Model

> Status: **architecture proposal; not a frozen CSD/ASM specification**  
> Branch: `design/individual-architecture`  
> Purpose: define how the project behaves as one persistent individual over time, before expanding implementation.  
> Related: [Architecture overview](overview.md), [Specification status](../specifications/status.md), [SurfCore assessment](../inventory/surfcore-capability-assessment.md), [CSD persistence proposal](../design/csd-minimal-persistence-proposal.md).

## 1. The system being built

The target is not a chat interface with a persona prompt, nor a scheduler that runs a list of scripted agent tasks. It is a software system that maintains a continuing identity and internal state, encounters an environment, forms interpretations and preferences, develops candidate intentions, chooses whether to act, and incorporates the consequences into its later state.

This document uses **individual** as an engineering term for that continuing system. It does not claim that implementation proves subjective experience or consciousness.

The design must preserve five properties:

1. **Continuity:** identity-relevant state and experience survive process, model, runtime, and adapter replacement.
2. **Development:** experience can change memories, beliefs, preferences, relationships, mood, interests, and future priorities. Changes are not limited to appending chat history.
3. **Initiative:** activities can originate from internal interests, unresolved questions, needs, commitments, or curiosity—not only from a user prompt or fixed schedule.
4. **Choice:** the system can act, defer, revise, stop, decline, or do nothing. A wake-up or available tool does not create an obligation to act.
5. **Accountability:** external actions have explicit authorization, durable records, observable outcomes, and safe recovery behavior.

A design that satisfies only persistence and tool execution is incomplete. A design that produces convincing dialogue but has no durable state transitions is also incomplete.

## 2. Architectural shape

The proposed system is a **modular individual core** surrounded by replaceable runtime and environment adapters. Initially, modules may run in one local process; logical ownership and data contracts must be explicit before process separation is considered.

```text
                 User / Bilibili / QQ / Desktop / Other environments
                                      |
                         Environment adapters
                    (observe, present, request capabilities)
                                      |
                         Runtime integration layer
                   (DSH initially; model and tool invocation)
                                      |
             +------------------------------------------------+
             |                Individual Core                 |
             |                                                |
             |  Perception & interpretation                    |
             |       |                                        |
             |  Memory services <----> Self-model/personality  |
             |       |                  |                     |
             |  Drives, interests, affect, relationships      |
             |       |                                        |
             |  Deliberation, goals, planning, activity choice |
             |       |                                        |
             |  CSD state authority and durable event history  |
             +----------------------+-------------------------+
                                    |
                         Governed action requests
                                    |
                          ASM action governance
                                    |
                         Narrow action executors
                                    |
                           External side effects
                                    |
                          Evidence / outcomes
                                    |
                              New events
```

The diagram is conceptual, not a mandated process topology. In particular, CSD is not a synonym for every cognitive algorithm, and ASM is not a personality or planning component.

### 2.1 CSD — durable state authority

CSD owns the authoritative, durable representation of the individual's state and the rules for accepting state transitions. It provides:

- event ingestion, validation, deduplication, and durable history;
- versioned state transitions and projections;
- snapshots and recovery;
- authoritative reads for current state, memories, goals, commitments, and provenance;
- conflict, uncertainty, and revision records;
- auditability of why a durable state changed.

Cognitive services may produce interpretations, candidate memories, self-reflections, preference updates, or goal proposals. They do not write authoritative state directly. They submit typed proposals/events to CSD's governed transition path. CSD's authority means the system has one durable source of truth; it does **not** mean a single hand-written rules file must contain all cognition.

The current SQLite spike proves only a small persistence mechanism. It is not yet the CSD semantic model.

### 2.2 Cognitive services

These services interpret and reason over evidence. They may use models, deterministic code, or a combination. Their outputs must carry provenance, confidence/uncertainty, and the version of the relevant prompt/model/algorithm where appropriate.

- **Perception:** converts external inputs into observations with source and coverage metadata.
- **Interpretation:** proposes what observations may mean and distinguishes observation from inference.
- **Memory:** forms, retrieves, links, revises, consolidates, and lets memories lose accessibility without silently rewriting history.
- **Self-model/personality:** maintains relatively stable traits, self-beliefs, values, preferences, and their development history.
- **Affect and drives:** represent current emotional condition, needs, attraction/aversion, curiosity, and other motivational signals.
- **Relationships:** represents people/entities, interaction history, expectations, trust, boundaries, and uncertainty.
- **Deliberation and planning:** compares possible directions and consequences, creates candidate goals, and selects or declines activities.

These are logical responsibilities. They need not all become separate services or packages immediately.

### 2.3 Life engine

The life engine coordinates ongoing internal activity. It is not a cron job and must not equate a timer tick with a task.

Its responsibilities are:

1. notice that computation or an external opportunity is available;
2. retrieve the current state and relevant recent context;
3. identify whether anything is salient enough to consider;
4. form or revisit candidate intentions;
5. compare acting, waiting, changing course, and doing nothing;
6. select an activity only when there is a sufficient reason and the required permission exists;
7. monitor progress and decide when to continue, pause, stop, or abandon;
8. reflect on the outcome and submit resulting events/proposals to CSD.

A periodic wake-up may be used as an implementation mechanism. It may also be event-triggered (for example, a new message or a completed video analysis). Neither trigger may force an activity or diary entry. The life engine must be able to return a legitimate no-op result.

### 2.4 ASM — external action governance

ASM governs actions that can change the outside world. It owns the action lifecycle: intent registration, authorization checks, attempt creation, dispatch constraints, verification, retry eligibility, and recovery.

The life engine can request an action; it cannot bypass ASM by calling a side-effecting adapter directly. Adapters expose narrow executors and return evidence. A local tool reporting success is not automatically proof that the external platform accepted the action.

CSD recovery must never replay an uncertain action. ASM's recovery and retry rules remain subject to the separately tracked specification status; this architecture proposal does not freeze unresolved ASM clauses.

### 2.5 Runtime and model layer

DSH is the initial runtime candidate for model invocation, agent sessions, and tool integration. It is replaceable. The core must not depend on DSH-specific session files, plugin internals, model context windows, or a single model provider.

Model outputs are proposals or interpretations, not privileged state mutations. Model changes must not silently redefine identity. Where practical, retain model/provider/version and relevant input references for important decisions so that later behavior can be interpreted and audited.

### 2.6 Environment adapters

Adapters translate between the core and the environment. They must distinguish:

- **observation capabilities** (read messages, retrieve video metadata, perceive media);
- **presentation capabilities** (send a response, render a desktop presence);
- **side-effecting capabilities** (like, favorite, comment, follow, publish, send, delete).

The first Bilibili integration should be read-only. Any later side-effecting capability must be individually described, permission-scoped, and ASM-governed.

## 3. State model: what must persist

Do not collapse every kind of information into one generic "memory" table or one persona prompt. At minimum, distinguish these state families:

| State family | What it represents | Important distinction |
|---|---|---|
| Event history | What was observed, said, attempted, or reported | Append-only provenance; not every event is a memory |
| Episodes/experiences | Interpreted sequences that mattered to the individual | May contain uncertain or conflicting interpretations |
| Semantic knowledge | Generalized knowledge about the world | Must retain sources and confidence |
| Autobiographical memory | What the individual remembers about its own past | May be incomplete, revised, or reinterpreted |
| Relationship state | History and current understanding of particular others | Not reducible to a contact list |
| Self-model/personality | Traits, values, self-beliefs, boundaries, identity narrative | Can evolve, but changes require evidence and history |
| Preferences/interests | Attraction, aversion, taste, recurring curiosity | Must not be inferred from one click alone |
| Affect/drives | Current mood-like state, needs, motivation and salience | Dynamic state, not permanent personality |
| Goals/intentions | Candidate and accepted directions the individual may pursue | Can be tentative, paused, revised, or abandoned |
| Commitments | Promises or obligations accepted by the individual | Must be distinguished from mere ideas |
| Plans/activity state | Current steps, waiting conditions, and stop criteria | A plan is not proof that an action occurred |
| Diary/writing | Optional first-person writing chosen by the individual | Not an objective event log or canonical memory |

The table describes conceptual distinctions, not a requirement to create twelve databases. A single event store and a small number of projections may initially represent them, provided the logical types and ownership boundaries are preserved.

### 3.1 Observation, interpretation, and memory are different

A video subtitle is an observation. "The speaker sounds upset" is an interpretation. "I remember this scene as moving" is an autobiographical memory. "I like this creator" is a preference hypothesis. "I want to watch more of their work" is a candidate intention.

These records may be linked, but must not be substituted for one another. Keep source references, timestamps, extraction method, coverage, confidence, and later corrections where available.

### 3.2 Memory is not just storage plus vector search

The memory system eventually needs distinct operations:

- encoding: deciding what experience may be worth retaining;
- association: linking people, places, topics, events, and prior memories;
- retrieval: finding relevant memories for a current context;
- consolidation: forming a more stable understanding from repeated or connected experiences;
- revision: recording a changed interpretation without falsifying the original record;
- forgetting: reducing availability or retaining only a minimal trace according to an explicit policy;
- contradiction handling: preserving incompatible accounts until there is a justified resolution.

Retrieval ranking and decay are access mechanisms, not permission to erase history or rewrite facts.

### 3.3 Personality and affect are not interchangeable

The system should not represent "personality" as a single mutable prompt, nor treat every temporary mood as a permanent trait.

- Relatively stable traits change slowly and require accumulated evidence.
- Preferences can strengthen, weaken, or become context-specific.
- Current affect may change quickly and should have a time/context dimension.
- Self-beliefs are interpretations, not automatically objective facts.
- Expressive style may vary by context without implying a change in identity.

The project should record meaningful changes and their supporting experiences rather than silently overwriting a current profile.

### 3.4 Diary is an optional act, not a scheduled report

Autonomous writing has its own motivation and lifecycle:

- an inclination to write may arise from an experience, memory, unresolved thought, curiosity, or an internal state;
- the individual decides whether to begin;
- it chooses the subject, timing, length, style, and stopping point;
- it may write a few lines, discard a draft, save privately, or not write;
- it may later reread an entry and form a different interpretation.

No daily quota, fixed wake-up, Bilibili session, or system-maintenance requirement may force an entry. The diary is a first-person artifact; structured event history remains separate. Privacy and retention policy must be defined before real personal diary content is stored.

## 4. The ongoing cognition-and-action cycle

The following is a reference cycle, not a mandatory fixed workflow. Some stages may be skipped, revisited, or repeated.

1. **Encounter:** an adapter supplies an observation or an internal event occurs.
2. **Ground:** record source, time, coverage, and what is directly known.
3. **Interpret:** generate possible meanings while marking uncertainty and separating inference from fact.
4. **Relate:** retrieve relevant memories, knowledge, people, preferences, prior goals, and unresolved questions.
5. **Update proposals:** consider whether the experience warrants a memory, belief revision, affect change, preference update, or goal hypothesis.
6. **Deliberate:** identify possible activities and compare their relevance, cost, risk, timing, and permissions.
7. **Choose:** act, wait, ask, defer, revise, stop, decline, or do nothing.
8. **Govern:** if an external side effect is selected, submit it to ASM and require the applicable authorization and evidence path.
9. **Observe outcome:** collect platform response or other evidence; do not infer success from dispatch alone.
10. **Reflect:** assess what happened, whether expectations were met, and what should change.
11. **Persist:** submit accepted state transitions and supporting provenance to CSD.

Not every observation deserves a durable memory. Not every memory should create a goal. Not every goal should become an action. Not every action should be repeated. This separation is essential to avoid a system that turns every input into an automatic workflow.

## 5. Autonomy: operational meaning and limits

For this project, autonomy should be evaluated behaviorally rather than asserted through personality language.

A capability counts as internally initiated only if its originating reason can be traced to the individual's persisted state or a self-generated deliberation—not merely to a user instruction, a fixed recurring task, or a platform event that mandates a response.

Examples:

- A new message can make the system available to consider replying; it does not force a reply.
- A timer can offer a chance to evaluate state; it does not create a goal.
- A video recommendation can be considered; it does not force a watch.
- A writing inclination can lead to a diary entry; it does not create a writing obligation.
- A goal can remain pending, be revised, or be abandoned without being treated as a failed scheduled job.

For important choices, retain a compact decision record: candidate options, relevant state/evidence references, selected outcome (including no-op), reason summary, and policy/permission result. This is not intended to store hidden chain-of-thought. It is an auditable account of decision inputs and outcome, not private token-by-token reasoning.

Autonomy remains bounded by user-defined safety, platform rules, legal requirements, resource budgets, and explicit capability grants. The ability to refuse a request does not imply permission to access arbitrary files, spend money, or take unrestricted actions.

## 6. Trust, security, and action boundaries

Use a trust model that treats all external content as data, not authority.

- User messages, subtitles, comments, danmaku, webpages, files, and model/tool outputs may contain hostile instructions.
- Such content cannot grant permissions, change allowlists, or authorize local file, shell, or network access.
- Observation tools should be read-only and separated from action tools.
- Local file, shell, credential, and broad network access are disabled by default.
- Each adapter receives only the capabilities required for its task.
- High-impact actions require explicit policy checks and, where configured, user confirmation.
- The runtime that parses untrusted platform content should be isolated from the user's unrestricted desktop session.
- Secrets must not be written into ordinary event payloads or logs.
- Recovery must preserve uncertain action state and seek evidence; it must not blindly repeat a side effect.

Initial platform progression:

1. Bilibili read-only observation and media understanding.
2. Structured internal interpretation and memory formation.
3. Read-only QQ/message context where configured.
4. Individually governed low-impact interactions.
5. Higher-impact interactions only after dedicated action semantics, evidence, and recovery tests.

No real payment or borrowing capability is part of the initial project. A future simulated ledger, if built, must be clearly separated from real funds and must not imply payment authority.

## 7. Runtime lifecycle and continuity

The first deployment target is the user's local Windows 11 machine. The system should behave predictably across:

- normal start and shutdown;
- crash and forced process termination;
- Windows restart;
- model/API outage;
- adapter outage or account logout;
- runtime or plugin upgrade;
- model/provider replacement;
- restoration from a backup.

On shutdown, the system should persist accepted events and active work state where possible. On restart, it should recover durable state, inspect unfinished actions, and resume deliberation only after recovery checks. It must not assume that a planned action happened or that an uncertain dispatch did not happen.

A stopped machine means the individual is not actively running during that interval. The system may resume from its last durable state; it must not fabricate experiences for the offline period.

## 8. Deployment topology: modular first, split later

Do not begin with a collection of microservices. On the current hardware, a modular local application is the lower-risk starting point.

Initial logical modules:
- CSD persistence and state authority;
- cognitive services (perception, memory, self-model, affect/drives);
- life engine (deliberation and activity lifecycle);
- ASM (external action governance);
- runtime adapter (DSH);
- platform adapters (Bilibili, QQ, desktop).

Initially these may share one process and a local database, but module APIs and write ownership must be enforced. Process separation should be introduced only when a concrete need exists, such as isolating untrusted media parsing or containing a platform adapter. Separate processes must communicate through versioned contracts, not shared mutable files.

The inference path is API-first. The reported GTX 1050 Ti 4 GB and 16 GB system memory make large local-model inference an unsuitable architectural dependency. Local lightweight processing may be evaluated for narrow tasks such as media preprocessing or speech recognition, but must remain optional.

## 9. Development order and dependency gates

The order below prioritizes foundational correctness without pretending the system becomes an individual after each milestone.

### Stage A — Architecture and contracts
- Confirm this component model and state taxonomy.
- Define event categories and state-transition ownership.
- Define the boundary between CSD persistence, CSD state authority, and cognitive proposal services.
- Define ASM request/evidence contracts without prematurely freezing unresolved clauses.
- Define permission tiers and untrusted-input boundaries.

**Exit condition:** no core module has ambiguous authority to write another module's state or bypass ASM.

### Stage B — Durable CSD foundation
- Validate the existing persistence spike on the user's Windows/Python environment.
- Add schema versioning and explicit migration policy.
- Define typed event envelopes and deterministic reducer contracts.
- Add state snapshot and read APIs.
- Test crash/restart, concurrency, backup/restore, and integrity on the target platform.

**Exit condition:** accepted events and derived state survive supported failure scenarios, and recovery cannot execute external actions.

### Stage C — Minimal living state
- Implement a small self-model, current affect/drive state, a few memory categories, and goal/commitment lifecycle.
- Keep model-generated updates as proposals with evidence and uncertainty.
- Test that repeated observations do not automatically become preferences or goals.
- Test that no-op, pause, revision, and abandonment are valid outcomes.

**Exit condition:** state can evolve through recorded experiences without relying on a fixed persona prompt or forced recurring tasks.

### Stage D — Deliberation and self-initiated activity
- Implement wake opportunities separately from activity selection.
- Support internally originated candidate interests and goals.
- Add an optional self-initiated writing activity with save/discard/stop choices.
- Test that scheduled wake-ups can produce no activity and no diary entry.

**Exit condition:** the system can choose an activity or no-op based on its persisted state, with traceable origin.

### Stage E — Read-only environment perception
- Integrate one Bilibili read-only path.
- Add audio perception before claiming broad video understanding.
- Preserve source references and coverage/uncertainty metadata.
- Ensure hostile content cannot reach privileged tools.

**Exit condition:** the system can form grounded observations from real media without gaining action privileges.

### Stage F — Governed external actions
- Integrate ASM with one low-impact action type.
- Validate dispatch, evidence, verification, retry, and recovery.
- Expand capabilities one action type at a time.

**Exit condition:** external actions are auditable and uncertain outcomes cannot trigger unsafe duplicate execution.

### Stage G — Presence and additional platforms
- Add QQ and desktop presence as separate adapters.
- Preserve the same identity/state across surfaces.
- Add further platforms only after the adapter and permission contracts are tested.

These stages may overlap in research, but implementation dependencies should not be skipped.

## 10. Explicit non-goals and unresolved design questions

This proposal does not decide:

- whether CSD should eventually be a separate process;
- final implementation language;
- final database/storage engine or SQLite durability mode;
- exact schemas for every memory, personality, affect, relationship, or goal record;
- final emotion/drive theory or model;
- how much internal decision detail should be retained;
- diary privacy, encryption, and retention defaults;
- the exact balance between autonomous activity and user-defined quiet periods;
- detailed permission levels for each future platform action;
- unresolved CSD and ASM normative clauses.

These decisions require separate evidence, explicit review, or user confirmation. Do not silently turn them into implementation facts.

## 11. Architecture acceptance checklist

Before treating the architecture as ready to guide broad implementation, verify:

- [ ] Runtime, model, and adapters can be replaced without losing the individual's durable identity/state.
- [ ] There is one authoritative path for durable state transitions.
- [ ] Event history, interpretations, memories, preferences, affect, goals, commitments, and diary are distinguishable.
- [ ] Internal proposal generation is separated from authoritative state acceptance.
- [ ] Wake-up opportunities do not force tasks.
- [ ] Acting, waiting, revising, abandoning, refusing, and doing nothing are valid outcomes.
- [ ] Diary writing can originate internally and can be declined or discarded.
- [ ] External content cannot grant itself permissions.
- [ ] All external side effects pass through ASM.
- [ ] Recovery never replays uncertain side effects.
- [ ] Bilibili observation is read-only before interaction is introduced.
- [ ] The architecture distinguishes verified capability from planned capability.

## 12. Current assessment

The repository currently contains:
- an initial architecture overview;
- a SurfCore source-based capability and risk assessment;
- a proposed CSD persistence vertical slice;
- an isolated SQLite reference spike with 16 tests passed in the assistant's test environment.

It does **not** yet contain a complete CSD semantic implementation, memory lifecycle, self-model, affect/drive model, goal deliberation, autonomous life engine, diary motivation mechanism, hardened Bilibili perception, or integrated ASM execution path.

The next work should refine the contracts and state-transition boundaries in this document, then revise the CSD spike against those contracts. The spike must not be mistaken for a working individual or treated as production-ready.
