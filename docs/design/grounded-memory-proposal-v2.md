# Grounded Memory Proposal v2 — Text Evidence First

> Status: **implementation design proposal; not a frozen CSD specification**  
> Depends on: [Claim-to-evidence grounding](claim-to-evidence-grounding.md), [Memory proposal provider contract](memory-proposal-provider-contract.md), [Semantic review boundary](semantic-review-boundary.md), [CSD cognitive-slice implementation decision](csd-cognitive-slice-implementation-decision.md).

## 1. Why v2 is needed

The current v1 proposal stores one free-form candidate paragraph and evidence event IDs. The deterministic evaluator can verify that an observation exists, but cannot verify that the paragraph is supported by that observation.

A real model provider must not be connected to that acceptance path. The next proposal format should preserve atomic claims and exact source spans.

This design introduces a new event type/version. It does not reinterpret or mutate existing v1 proposal events.

## 2. Scope

First implementation:
- observation records whose declared coverage modality is exactly `text`;
- one observation event per proposal;
- source-assertion claims with exactly one exact text span each;
- exactly one distinct observation event per proposal in this first version;
- source-assertion claim text equal to the exact quoted text (no unverified paraphrase);
- inference claims explicitly linked only to source-assertion claim IDs;
- deterministic validation of source spans and claim references;
- accepted memories preserve epistemic type and evidence provenance.

Out of scope:
- image/video/audio locators;
- perceptual claims;
- system-experience claims;
- cross-observation synthesis;
- semantic entailment scoring;
- automatic preference/personality/goal changes;
- production model integration.

## 3. New event type

Proposed event type:

`cognition.grounded_memory_candidate_proposed.v1`

The existing `cognition.memory_candidate_proposed.v1` remains a legacy synthetic persistence fixture. The v2 event must have its own strict schema and reducer path.

## 4. Proposed payload

    {
      "proposal_id": "grounded-proposal-001",
      "memory_kind": "episodic_candidate",
      "claims": [
        {
          "claim_id": "claim-source-001",
          "text": "A blue paper boat floated beside a stone bridge.",
          "epistemic_type": "source_assertion",
          "evidence": [
            {
              "event_id": "evt-observation-001",
              "locator": {
                "kind": "text_range",
                "unit": "unicode_codepoint",
                "start": 2,
                "end": 55
              },
              "quoted_text": "A blue paper boat floated beside a stone bridge."
            }
          ],
          "uncertainty": {
            "label": "directly_quoted",
            "confidence": null
          }
        },
        {
          "claim_id": "claim-inference-001",
          "text": "The source may be aiming for a quiet, reflective mood.",
          "epistemic_type": "inference",
          "derived_from_claim_ids": ["claim-source-001"],
          "reasoning_summary": "The description emphasizes a quiet setting and a small, delicate object.",
          "uncertainty": {
            "label": "tentative_inference",
            "confidence": 0.42
          }
        }
      ],
      "origin": {
        "component": "provider.identifier",
        "version": "0.1"
      },
      "based_on": {
        "state_version": 0
      },
      "operation": "create"
    }

The offsets above are illustrative only; the implementation must calculate and validate them against the exact stored Unicode string. Do not copy these example offsets blindly.

There is deliberately no free-form memory narrative field in this first v2 schema. A readable view can be rendered from the accepted claims. This avoids treating a model-written paragraph as a single verified fact.

## 5. Claim rules

### 5.1 source_assertion

Required:
- non-empty claim_id and text;
- exactly one evidence reference;
- each reference identifies an existing observation event whose declared coverage modality is exactly `text`;
- locator kind is `text_range`;
- unit is `unicode_codepoint`;
- start/end are non-negative integers with start less than end;
- quoted_text is non-empty;
- the source-assertion `text` exactly equals `quoted_text`;
- the stored observation content slice `content[start:end]` exactly equals `quoted_text`;
- uncertainty label is exactly `directly_quoted`; confidence is null.

This verifies that the quote exists in the source record. It does not prove the source's statement is true.

### 5.2 inference

Required:
- non-empty claim_id and text;
- epistemic_type is exactly `inference`;
- derived_from_claim_ids references one or more other claims in the same proposal;
- every referenced claim exists and is a `source_assertion` in this first version;
- non-empty reasoning_summary;
- uncertainty label is explicit;
- confidence is optional and constrained to 0 through 1, but is not treated as calibrated truth probability.

An inference must never be rendered or stored as a direct observation. It remains an interpretation even when accepted into memory. The first implementation rejects inference-to-inference chains; every inference must point directly to one or more source_assertion claims.

### 5.3 Disallowed in v2

- `perception` claims without a modality-specific artifact locator;
- `system_experience` claims without internal runtime/action evidence;
- claims with no evidence or derivation path;
- claims that reference a different proposal's local claim IDs;
- unknown claim types or extra authority-like fields;
- executable instructions or tool/action payloads.

## 6. CSD evaluation behavior

The CSD-owned evaluator should produce a durable decision outcome:

- `accepted`: all source spans and claim links are structurally valid, and the proposal is current;
- `rejected`: quote text does not match the source, a locator is out of bounds, a claim type is invalid, or a derivation reference is invalid;
- `needs_more_evidence`: a referenced event/artifact is genuinely unavailable;
- `deferred`: the proposal's accepted-state version is stale.

The decision means "this structured memory item may be stored with these epistemic labels." It does **not** mean every inference is objectively true.

CSD must never silently rewrite a bad quote to make it pass. The original proposal remains in event history with a rejection reason.

## 6A. Prototype implementation status

The v2 event type `cognition.grounded_memory_candidate_proposed.v1` is implemented in the isolated `CognitiveMemoryStore` prototype. Non-text observations are rejected both before provider invocation and during CSD evaluation.

The CSD evaluator currently:
- checks the strict claim schema;
- binds each source assertion to exactly one text-range evidence item;
- verifies the observation event and its payload/envelope integrity;
- uses Python Unicode code-point offsets and checks the exact source substring;
- requires claim text to equal the quoted span;
- allows inference claims only when they reference existing source_assertion claims in the same proposal;
- preserves accepted claims, inference labels, locators, provider provenance, and evidence IDs in the accepted-memory projection.

The separate `GroundedMemoryProposalPipeline` accepts typed provider output, attaches the observation event ID, provider identity/version, and CSD state version, then submits a pending v2 proposal. It does not evaluate or accept the proposal. It currently accepts at most one candidate per call.

This is structural grounding only. It cannot prove that the quoted source itself is true, or that an inference is semantically reasonable. A real model provider is not connected.

## 7. Accepted memory projection

An accepted v2 memory contains:
- memory_id and memory_kind;
- proposal_id and proposal event ID;
- decision event ID and transition ID;
- the complete accepted claims array;
- all evidence event IDs and exact locators;
- provider identity/version;
- claim-schema and decision-policy versions;
- accepted-state creation time and status.

The normal memory read returns claims with their epistemic types and provenance. A UI may render a compact narrative, but the narrative is a view derived from claims and must not erase uncertainty labels.

## 8. Deterministic tests required before implementation is called complete

- exact text range and quoted text match;
- wrong start/end offsets rejected;
- out-of-bounds offsets rejected;
- quote mismatch rejected without partial accepted state;
- missing evidence deferred without fabricated evidence;
- duplicate claim IDs rejected;
- inference referencing missing claim rejected;
- inference referencing another inference rejected in v2.1's initial restricted graph;
- source assertions and inferences remain distinguishable after retrieval;
- recovery rebuilds identical claims and locators;
- recovery never reruns a model or semantic evaluator;
- malformed v2 event cannot mutate accepted memory;
- stale proposal defers even if all quote spans are valid.

## 9. Compatibility and migration

- Keep v1 proposal events readable and replayable as historical synthetic fixtures.
- Do not reinterpret v1 `candidate_content` as a fully grounded claim.
- v1 accepted memories must retain an explicit legacy/unverified provenance marker if ever migrated.
- v2 gets its own event type and strict schema version.
- A future migration may create a v2 proposal only after a provider reconstructs claim/evidence mapping; migration must not invent spans.

## 10. Readiness gate for a real model provider

Do not connect a real model provider to a path that accepts v1 free-form paragraphs as verified autobiographical memory.

A real provider may be used first in shadow mode:
1. receive a synthetic or non-sensitive observation;
2. produce candidate v2 claims;
3. run structural/source-span validation;
4. retain candidates as pending;
5. inspect rejection/defer behavior and provenance;
6. only then consider a narrowly scoped acceptance policy.

Semantic entailment, multimodal perception quality, and calibrated uncertainty remain separate evaluations. See the [semantic review boundary](semantic-review-boundary.md); no reviewer is implemented or connected.
