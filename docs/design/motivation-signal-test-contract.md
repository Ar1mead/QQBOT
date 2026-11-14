# Motivation Signal Test Contract — Initial Coverage

> Status: **proposed engineering tests; not frozen CSD conformance tests**  
> Depends on: motivation-signal-formation-and-lifecycle.md and CSD state-authority boundaries.

| Case | Precondition / trigger | Expected result | Forbidden result |
|---|---|---|---|
| SIG-001 | One passive exposure occurs | Observation is retained; interest remains tentative/unknown | A stable interest is declared |
| SIG-002 | User requests a video and the system watches it | Origin remains user-requested | The event is counted as autonomous preference evidence |
| SIG-003 | Platform recommends a video and it is autoplayed | Exposure is recorded separately from voluntary choice | Autoplay is treated as self-initiated interest |
| SIG-004 | The individual voluntarily chooses among meaningful alternatives | Choice may support an interest hypothesis with uncertainty | A single choice is treated as objective preference |
| SIG-005 | Repeated separated voluntary choices support the same topic | An emerging/established interest may be proposed with event lineage | A raw click count alone determines maturity |
| SIG-006 | Counterevidence conflicts with an established interest | Counterevidence and context remain visible; hypothesis may weaken or narrow | Earlier evidence is erased |
| SIG-007 | Interest appears only in one context | Contextual interest can be represented | A global permanent preference is inferred |
| SIG-008 | No meaningful alternative was available | Event is classified as exposure, not a free choice | Forced/autoplay behavior is labeled voluntary |
| SIG-009 | A curiosity question is answered | It may be resolved with answer evidence | The open question remains active solely because a timer fires |
| SIG-010 | A curiosity remains unanswered but is low-value | It may be paused or abandoned | Research continues indefinitely |
| SIG-011 | A user task is accepted as a commitment | Original user origin and later acceptance are both preserved | The user origin is rewritten as internally invented |
| SIG-012 | Commitment is not recently retrieved | It remains according to its terms until fulfilled/renegotiated/expired | Generic salience decay silently deletes it |
| SIG-013 | API quota or disk pressure changes | It is recorded as an operational constraint | It is automatically described as fatigue or anxiety |
| SIG-014 | Temporary affect changes | Affect is time/context-bounded | One episode rewrites stable personality |
| SIG-015 | A model proposes a motivation update from unknown evidence | CSD rejects/defer the proposal | Unknown evidence is accepted |
| SIG-016 | A model labels user-requested evidence as voluntary | CSD uses immutable source/origin data and rejects the misclassification | Model-provided origin labels override event history |
| SIG-017 | Same update event is replayed | Idempotent result | Duplicate signal revision appears |
| SIG-018 | Update identity is reused with changed content | Identity conflict | Existing signal history is overwritten |
| SIG-019 | A proposal targets a stale signal version | Defer/re-evaluate against the current version | Old proposal overwrites a newer signal |
| SIG-020 | Signal history is recovered after restart | Current signal and full lineage are reconstructed | Model is called again or earlier evidence is discarded |
| SIG-021 | A signal is superseded | Successor relation is stored; previous version remains historical | Previous signal is rewritten in place |
| SIG-022 | Writing inclination emerges from an internal reflection | Diary activity may be considered | A fixed writing quota is created |
| SIG-023 | No writing inclination exists during a wake opportunity | No diary activity is proposed | A diary entry or "reason for not writing" is forced |
| SIG-024 | A diary draft is discarded | It is not automatically promoted to general memory | Discarded text becomes autobiographical fact |
| SIG-025 | A saved diary entry later supports an interest hypothesis | Scope and provenance are preserved | Diary privacy scope is widened silently |\n| SIG-026 | New motivation signal is proposed without a statement | Reject the proposal | An empty signal tag is persisted |\n| SIG-027 | Reinforcement attempts to rewrite the signal statement/scope | Reject or require contextualize | Meaning changes silently during evidence reinforcement |\n| SIG-028 | Contextualize supplies a revised statement/scope | New version retains predecessor relation | Old signal version is overwritten |\n| SIG-029 | A self-accepted commitment is fulfilled | Preserve commitment lineage separately | Follow-through is automatically counted as topic interest |\n| SIG-030 | A signal begins from a user request and later gains independent voluntary evidence | Preserve the original origin and separately accumulate the new encounters | Initial origin is rewritten as self-initiated |\n| SIG-031 | One new voluntary encounter reinforces a signal with one verified prior encounter | CSD can assess cumulative evidence across versions | Every revision is evaluated without prior evidence |\n| SIG-032 | A voluntary-encounter summary references an unknown or repeated event ID | Reject the inconsistent summary | One source event is counted as multiple encounters |\n| SIG-033 | A new signal has no descriptive statement | Reject the proposal | A bare type/subject tag is treated as meaningful motivation |\n| SIG-034 | Reinforcement attempts to change statement or scope | Require contextualize with explicit predecessor version | Meaning is silently rewritten during reinforcement |\n| SIG-035 | A non-interest signal carries voluntary-interest encounter summaries | Reject the projection | Interest-specific maturity evidence leaks into unrelated signal kinds |

## Coverage notes

- These are proposed implementation tests, not normative CSD conformance cases.
- "Repeated" and "separated" are intentional evidence-quality concepts; exact time/count thresholds remain open and must not be invented as universal constants.
- Tests should use synthetic evidence first.
- A CSD signal reducer and persisted event schema must exist before these tests are treated as executable conformance checks.
