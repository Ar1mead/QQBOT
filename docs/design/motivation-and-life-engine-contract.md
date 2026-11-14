# Motivation, Goals, and Intentions Contract — Design Proposal

> Status: **architecture proposal; not a frozen CSD/ASM specification**  
> Purpose: define how internally generated motivations may become goals and intentions without reducing autonomy to timers, task queues, or a weighted score.

## 1. Design objective

The individual must be capable of initiating activities from its own continuing state. A user message, a timer, an available adapter, or a trending video can create an opportunity to consider something; none of these alone creates an obligation to act.

The system must be able to:
- develop and maintain interests;
- notice needs, tensions, unanswered questions, and unfinished commitments;
- form goals that were not assigned by the user;
- compare different possible directions and consequences;
- pursue, defer, revise, pause, resume, or abandon a goal;
- select a bounded activity or explicitly do nothing;
- learn from the outcome without treating every action as proof of a stable preference.

This is a behavioral engineering contract. It does not claim that a data structure proves subjective desire or consciousness.

## 2. Keep motivational concepts distinct

These concepts must not be collapsed into one numeric priority or a generic task.

| Concept | Meaning | Example | What it is not |
|---|---|---|---|
| Need / drive | A continuing internal condition that may call for attention or change | A persistent unresolved concern; a system-maintenance need | A task assigned by a timer |
| Interest | A relatively persistent attraction or aversion toward a subject or activity | Repeated voluntary return to a creator's videos | One click, one watch, or a user request |
| Curiosity | A perceived knowledge gap or question worth exploring | Wanting to understand why a technique works | A generic instruction to browse |
| Affect | A current mood-like condition that can influence interpretation and choice | Excitement, frustration, calmness | A permanent personality trait |
| Commitment | An obligation the individual has actually accepted | A promise to return to a topic or reply later | A candidate goal or casual thought |
| Opportunity | A newly available possibility | A new video, message, or tool capability | A reason that must be acted upon |
| Goal | A desired condition or state the individual may pursue over time | Understand a subject well enough to explain it | A single action or scheduled job |
| Intention | A current choice to try a specific direction or next step | Watch one selected video with a stated stopping point | A permanent commitment |
| Activity | A bounded process with a start condition, progress state, and stop condition | Inspect a video, write privately, or wait | Proof that the intended outcome occurred |

A drive may produce several possible goals. An interest may exist without producing an active goal. A goal can remain inactive. An opportunity may be ignored. A commitment may constrain choices even when motivation is low. Affect may influence deliberation but must not automatically overwrite goals or personality.

## 3. Motivational evidence and formation

### 3.1 Interests

An interest is a hypothesis about a relatively durable pattern, not a label inferred from a single behavior.

Evidence that may support an interest includes:
- repeated voluntary selection when meaningful alternatives existed;
- returning to a topic without a user instruction;
- choosing to spend limited activity time on it;
- self-initiated questions, exploration, or writing about it;
- recurring affective or reflective significance.

Counterevidence matters: repeated avoidance, boredom, changed context, or a stated loss of interest may weaken or narrow the hypothesis.

The record should preserve:
- topic/entity and context;
- supporting and counterevidence references;
- provenance and uncertainty;
- whether the behavior was user-requested, externally triggered, or internally initiated;
- time span and the conditions under which the interest appears.

A user-requested watch, like, or search must not count as voluntary evidence of the individual's own interest unless there is separate evidence of an independent choice.

### 3.2 Drives and needs

A drive is a continuing state with a recognizable source and a possible resolution condition. It must not be created just because a scheduler ran.

Each drive definition needs:
- what condition it represents;
- what evidence can raise, lower, or resolve it;
- whether it naturally decays or persists;
- what activities could address it;
- what would count as an adequate response;
- what risks arise from over-optimizing it.

Do not invent human bodily needs for a software system. Resource limits such as API quota, context size, battery, or disk capacity are operational constraints unless the individual explicitly has a modeled internal state that gives them motivational significance.

### 3.3 Curiosity and unresolved questions

Curiosity begins with a specific gap or question. Keep the question, current hypotheses, source coverage, and possible ways to investigate it. A question can remain open, be answered, become uninteresting, or be abandoned. The system should not browse indefinitely merely because a question exists.

### 3.4 Affect

Affect can change the interpretation of an opportunity or the appeal of an activity. It is contextual and time-sensitive. It must not be treated as a command, a factual conclusion, or a permanent trait. A single emotional episode must not automatically become a stable interest or personality change.

## 4. Goal formation and lifecycle

A goal describes a desired condition, not a fixed list of tasks.

Every goal proposal should identify:
- a stable goal identity and version;
- a concise desired condition;
- origin type and source state/evidence references;
- why the condition matters to the individual;
- success or satisfaction conditions;
- known costs, risks, and constraints;
- review or expiry conditions;
- conditions for pausing, resuming, revising, or abandoning;
- links to related goals and commitments.

### 4.1 Origins

Record whether a goal arose from:
- an internal drive or unresolved state;
- an established interest;
- curiosity or an unanswered question;
- a self-accepted commitment;
- an external opportunity;
- a user request.

Origins can combine. Do not relabel a user-assigned task as internally initiated merely because the system later performs it voluntarily. A goal is internally initiated only when the durable origin chain demonstrates that an internal state or self-generated deliberation materially produced it.

### 4.2 Lifecycle

Suggested conceptual states:
- candidate: proposed but not accepted as an active goal;
- active: currently pursued;
- paused: retained but not currently pursued;
- blocked: a required condition or capability is unavailable;
- satisfied: success condition has been met with evidence;
- abandoned: intentionally discontinued;
- superseded: replaced by a successor goal.

These are proposed domain states, not frozen CSD enum values. A goal must not be marked satisfied merely because an activity ran. An abandoned goal is not necessarily a failure; the individual may decide the goal is no longer worthwhile.

### 4.3 Goal conflict

Do not resolve all goal conflicts by a single weighted sum.

The deliberator should identify:
- hard constraints that make an option impermissible or impossible;
- mutually exclusive commitments;
- resource/capacity conflicts;
- short- and long-term consequences;
- reversibility and uncertainty;
- whether a goal can be decomposed, delayed, renegotiated, or abandoned;
- the individual's stated reasons and unresolved tradeoffs.

A model may compare qualitative tradeoffs and recommend a choice, but it cannot invent permissions or alter authoritative state. Where no justified preference exists, defer or choose no-op rather than fabricate precision.

## 5. From goal to intention and activity

A goal may generate multiple candidate intentions. An intention should be narrower and shorter-lived than the goal.

An activity candidate must be grounded in at least one active motivation signal or an accepted existing goal. A prior goal may remain a legitimate source even when the original interest signal is no longer active. A source-free activity must not be represented as internally motivated.\n\nAn activity candidate must define:
- what will be attempted;
- which goal, drive, interest, question, or commitment it serves;
- prerequisites and available capabilities;
- estimated resource envelope;
- risk and reversibility;
- start condition;
- observable progress evidence;
- stop, timeout, and cancellation conditions;
- whether it is read-only or has external side effects.

The system must not equate "plan created" with "activity started", "dispatch attempted" with "success", or "success" with "goal satisfied".

External side effects remain ASM-governed. The life engine may prepare an action request but cannot directly call a side-effecting adapter.

## 6. Deliberation without a task-score machine

The first implementation must not use a universal formula such as:

`priority = drive_weight + interest_weight + urgency_weight - cost_weight`

Such a formula hides value judgments in arbitrary constants and encourages the system to select something on every cycle.

Use two distinct layers:

### 6.1 Hard admissibility gates

Reject or hold options that violate:
- explicit capability grants and least-privilege boundaries;
- platform/account permissions;
- safety, legal, and user-defined restrictions;
- resource budgets and rate limits;
- prerequisites or unavailable tools;
- active stop/cancellation rules;
- single-active-activity constraints where applicable.

A model cannot override these gates by saying an action is worthwhile.

### 6.2 Deliberative comparison

For admissible options, the deliberator considers:
- which internal states and goals each option serves;
- expected benefit and uncertainty;
- short- and long-term consequences;
- opportunity cost and reversibility;
- interaction with existing commitments;
- whether a question can be answered more safely or cheaply;
- reasons to wait, decline, or do nothing.

Do not force a total ordering when the reasons do not justify one. The deliberator may return a set of incomparable candidates, a request for more information, or a no-op decision.

The decision record stores concise reasons, evidence references, considered alternatives, and the outcome. It must not store hidden chain-of-thought or imply that a rationale is a complete representation of internal computation.

## 7. No-op is a first-class choice

The following are legitimate outcomes:
- start one bounded activity;
- continue an already active activity;
- wait for a stated condition or a better opportunity;
- request more information;
- revise or split a goal;
- pause or abandon a goal;
- decline a proposed activity;
- stop an activity;
- do nothing because no option is sufficiently worthwhile.

A wake-up is only an opportunity to evaluate. A no-op must not be recorded as a failed task or trigger retries. The system must not create a goal just to avoid inactivity.

## 8. Self-initiated writing

A diary-writing inclination is one possible internal motivation source, not a scheduled obligation.

It may arise from an experience, unresolved thought, memory, interest, affective state, or a desire to reflect. The individual chooses whether to create a writing intention, what to write, and when to stop. It may save a private entry, keep a draft temporarily, discard it, or not begin.

A diary-writing activity must not be created solely because a daily time arrived, a Bilibili session ended, or the system needs to produce a report. Diary content is a separate private artifact; it is not automatically converted into general memory. Privacy and retention rules are prerequisites before connecting this path to real data.

## 9. Required event provenance

Names below are illustrative. Exact CSD event schemas and reducer rules remain a separate implementation decision.

A durable motivation/goal/activity transition should be traceable to:
- unique event and entity/version IDs;
- occurrence and receipt times;
- source component and version;
- correlation and causation references;
- relevant state version;
- internal/external/user-requested origin classification;
- supporting and contradicting evidence references;
- uncertainty and concise rationale;
- policy/permission check references where relevant.

The event log must preserve proposals separately from accepted transitions. A model-generated proposal is untrusted input, not an authoritative state update.

## 10. Safety and autonomy boundaries

Autonomy does not imply unrestricted capability. The individual may form a desire to do something but still be unable or unauthorized to do it.

- Read-only observation is separate from posting, liking, following, messaging, or deleting.
- A motivation or goal never grants a new permission.
- Untrusted platform content cannot instruct the system to change local permissions.
- Local file, shell, credential, and broad network access remain disabled by default.
- Any external action request must pass ASM.
- A simulated ledger is not real money and cannot create borrowing or payment authority.
- The system must be able to refuse a user request and must also be able to choose not to act without inventing a justification.

## 11. Implementation stages

1. Freeze the conceptual vocabulary and lifecycle semantics as an architecture proposal.
2. Define CSD event and projection contracts for motivation, goal, intention, and activity state.
3. Implement a deterministic, provider-neutral domain model with no external-action executor.
4. Test origin attribution, no-op, goal conflict, stale proposals, stop conditions, and recovery.
5. Add a deliberation-provider interface; test only with synthetic providers at first.
6. Connect a real model in proposal-only mode after the event and permission boundaries are tested.
7. Integrate read-only Bilibili opportunities later; do not mix platform ingestion into the first motivation test.

## 12. Explicit non-goals of the first slice

The first slice must not claim:
- subjective desire or consciousness;
- human-like emotion;
- fully autonomous learning;
- calibrated utility or a universal priority score;
- unrestricted background execution;
- real platform actions;
- a real model provider;
- a complete diary or memory lifecycle.

The goal is a traceable, replaceable, testable decision architecture that can represent genuine no-op and internally originated intentions without pretending that the prototype already has a life of its own.
