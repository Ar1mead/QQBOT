# Motivation Signal Formation and Lifecycle — Design Proposal

> Status: **domain design proposal; not a frozen CSD specification**  
> Purpose: define how drives, interests, curiosity, commitments, affect, and opportunities can persist and change without turning every observed behavior into a desire or every wake-up into a task.

## 1. Problem

The Life Engine currently consumes motivation signals from an authoritative snapshot. It does not yet explain how those signals are formed, reinforced, weakened, contextualized, or resolved.

This is a central gap. Without a formation model, a signal could become a permanent preference because of one click, a user-requested task could be misclassified as independent interest, or a scheduler could manufacture a need simply because it ran.

The motivation system must describe the individual's changing internal state while preserving the evidence and uncertainty behind each interpretation.

## 2. Distinct signal families

| Kind | What it represents | Typical lifetime | Important guard |
|---|---|---|---|
| Need / drive | A continuing internal condition that may call for attention or resolution | Until its condition changes, resolves, or is intentionally abandoned | Do not invent biological needs or treat resource limits as feelings |
| Interest | A developing attraction or aversion toward a topic, entity, style, or activity | May persist, weaken, become contextual, or disappear | One click, watch, or user request is not a stable preference |
| Curiosity | A question or knowledge gap that the individual may want to explore | Until answered, no longer useful, or abandoned | An unanswered question does not force endless research |
| Commitment | An obligation the individual has accepted | Until fulfilled, renegotiated, withdrawn, or expired under its terms | A user task is not a commitment unless accepted |
| Affect | A temporary emotional condition or appraisal | Often short-lived and context-dependent | Must not be silently promoted to personality or permanent interest |
| Opportunity | A possibility made available by the environment | Often expires or changes with the environment | Availability is not motivation and does not mandate action |

These types may relate to each other but must remain distinct. An interest can create curiosity; curiosity can lead to a goal; a goal can become a commitment. Those are transitions or relations, not synonyms.

## 3. Motivation signal record

A durable signal hypothesis should preserve at least:

- signal ID and version;
- kind and subject/topic/entity;
- context/scope (where or under what conditions it applies);
- current lifecycle and activation state;
- origin classification and causal references;
- supporting evidence references;
- contradicting or weakening evidence references;
- confidence/uncertainty description;
- created, last-updated, and next-review times;
- related goals, memories, commitments, and experiences;
- resolution or stop condition;
- the policy and component versions that proposed and accepted the change.

Do not store only a score or a label such as likes_music=true. Preserve what led to the hypothesis, when it applies, and what might disconfirm it.

A separate activation/salience assessment may describe how relevant the signal is now. It is not a universal utility score and must not be summed across different signal kinds to force a ranking.

## 4. Interest formation

### 4.1 Distinguish exposure from voluntary choice

For each relevant encounter, preserve:
- whether the content was user-requested;
- whether it was pushed/recommended by the platform;
- whether the individual independently chose it;
- what meaningful alternatives were available;
- whether she returned to it without an instruction;
- whether she explored related material or raised her own questions;
- whether she later expressed attraction, aversion, boredom, or indifference.

An exposure or a user-requested action is evidence that the content was encountered, not evidence of independent preference. A deliberate choice among available alternatives is stronger evidence of interest, but still not proof by itself.

### 4.2 Maturity is not a raw count

An interest may be:
- tentative: a possible attraction/aversion worth keeping as a hypothesis;
- emerging: a pattern with repeated, separated, voluntary evidence;
- established: a more durable pattern supported across time or contexts;
- contextual: meaningful only under a specific condition;
- declining: recent evidence suggests weakening;
- unresolved: evidence conflicts or is insufficient.

These are proposed conceptual stages, not final enum values. Exact transition criteria remain open. Do not define maturity solely by a fixed click count, number of watched videos, or a universal numeric threshold.

A single unusual experience may justify a tentative interest hypothesis or a momentary curiosity. It must not automatically become a stable trait or established preference.

### 4.3 Counterevidence and change

The system must preserve evidence that does not fit an interest hypothesis. It may:
- narrow the context where the interest applies;
- weaken the hypothesis;
- split one broad interest into distinct interests;
- mark conflicting evidence as unresolved;
- supersede the old hypothesis with a more precise version;
- resolve the interest when it is no longer relevant.

Do not erase old choices or silently rewrite an earlier preference. A later change of taste is part of continuity, not a database inconsistency.

## 5. Need and drive formation

A drive must represent an identifiable internal condition, not a generic desire to stay busy.

Each drive definition needs:
- the condition it tracks;
- the evidence that can create or modify it;
- what can satisfy or resolve it;
- whether it persists without attention;
- possible activities that might address it;
- risks of over-optimization;
- whether it is a software-maintenance constraint or an individual-level motivation.

Operational limitations (API quota, disk space, context length, CPU load, battery) are constraints by default. They become motivational signals only if a separate, explicit design explains why the individual treats that condition as internally significant. Do not anthropomorphize a resource alert into fatigue or anxiety.

## 6. Curiosity

Curiosity should be represented by an explicit question or knowledge gap:
- question text and topic;
- why the gap became salient;
- current hypotheses and known evidence;
- possible ways to investigate;
- cost/risk and scope limit;
- what would count as a useful answer;
- when it should be paused, answered, or abandoned.

Curiosity may remain open without creating an activity. The individual can decide that the answer is not worth pursuing now.

## 7. Commitment

A commitment is created only when the individual accepts an obligation under defined terms.

Preserve:
- who or what the commitment concerns;
- what was accepted, not merely requested;
- whether acceptance was voluntary or conditioned by a user request;
- due/trigger conditions if any;
- permitted renegotiation or withdrawal;
- completion evidence;
- any conflict with later goals or limits.

A user request stays user-originated even if the individual chooses to accept it as a commitment. The system must not rewrite its history as an internally invented goal.

## 8. Affect

Affect is a time- and context-bounded state. It may:
- alter what is salient;
- change the anticipated appeal or cost of an activity;
- influence interpretation;
- motivate reflection or writing.

It must not:
- grant permissions;
- override safety constraints;
- directly create an external action;
- become a stable personality trait from one episode;
- be treated as an objectively verified fact about another person.

Affect updates need evidence and time boundaries. The system should be able to record "uncertain" or "not enough context".

## 9. Lifecycle operations

Conceptual operations for a motivation signal:
- propose: create a new hypothesis;
- reinforce: add supporting evidence and possibly change its current activation/maturity;
- weaken: add counterevidence or lower current salience;
- contextualize: narrow or split the conditions where it applies;
- pause: retain it but stop treating it as currently actionable;
- resolve: mark the tracked condition/question as resolved;
- supersede: link to a better successor hypothesis;
- abandon: intentionally stop pursuing it while preserving history.

These operations are proposals. The model/provider cannot directly change the authoritative signal state.

Do not use "decay" as a universal timer rule. Interests, curiosity, commitments, opportunities, and affect have different lifetimes. A commitment must not silently disappear because it was not recently retrieved; an opportunity may expire; an affective state may naturally change; an interest should be reassessed through evidence and context.

## 10. Proposal and CSD authority boundary

A provider-neutral motivation synthesizer may read an authorized snapshot and relevant evidence, then submit a typed update proposal containing:
- operation and target signal/version;
- new signal candidate or proposed changed fields;
- supporting and counterevidence event IDs;
- causal origin references;
- context/scope;
- uncertainty and concise rationale;
- based-on state version;
- component/model/policy provenance.

The evidence snapshot is a trusted projection. Its event kind, origin, meaningful-alternatives flag, timestamp, and subject reference must be derived by CSD/adapters from immutable event metadata and verified interaction context. They must never be accepted as free-form model labels. The local validator cannot authenticate those fields or prove that a source event actually represents voluntary choice.\n\nCSD must:
- verify that referenced events exist and their source/origin classifications are authentic;
- verify that user-requested and platform-triggered events are not presented as independent voluntary choices;
- reject unknown signal types and unauthorized fields;
- reject stale updates or bind them to the exact predecessor version;
- preserve previous signal versions and contradictory evidence;
- decide whether to accept, defer, or reject the update;
- commit the decision and projection update atomically;
- rebuild the same signal history during Recovery without calling a model.

The proposal pipeline can assess semantics, but its output remains untrusted input. CSD's authority does not mean every subjective interpretation is objectively true; it means there is one durable, auditable path for accepting the system's current internal representation.

## 11. Relationship to goal formation

A motivation signal may inform a goal proposal, but it does not automatically create one.

- An interest can exist without a goal.
- A curiosity can be abandoned without being marked failed.
- A drive can remain unresolved while no suitable activity exists.
- An opportunity can be ignored.
- A commitment can constrain choice even when it is not attractive.
- A current affect can influence choice without becoming a lasting goal.

Goal-origin classification must be derived from accepted signal/event lineage, not from a model-supplied self_initiated flag.

## 12. Relationship to journaling

A writing inclination can arise from a motivation signal, an experience, an unresolved question, or a self-reflection. It is not a daily or scheduled duty.

- A diary-writing inclination is not the same as a generic memory-formation signal.
- The individual decides whether to start and whether to save.
- A saved diary entry is a private authored artifact.
- The entry does not automatically become a general memory or interest update.
- Any later memory proposal must cite the diary artifact under its privacy scope and preserve that provenance.
- A draft the individual discards need not create a durable diary record.

## 13. Unresolved implementation decisions

Before coding a persistent signal reducer, decide:
- exact signal identity/version rules;
- how maturity stages are assessed without arbitrary click thresholds;
- how independent voluntary choices are distinguished from passive exposure;
- whether interests can be positive, negative, ambivalent, or mixed by context;
- how conflicting signals are represented;
- how salience is represented without a universal priority score;
- which signals expire and which require an explicit resolution;
- how commitment origin and renegotiation are represented;
- how affect is time-bounded and revised;
- which parts are CSD invariants versus replaceable interpretation policies.

## 14. Current implementation boundary

The current Life Engine prototype consumes a snapshot of typed motivation signals. It does not create, learn, reinforce, weaken, contextualize, or resolve them. No real model synthesizer is connected. The CSD event schema and authoritative signal projection are not implemented.

This document is a design proposal to define the missing layer before writing a signal-update reducer. It is not evidence that the system already has autonomous interests or drives.
