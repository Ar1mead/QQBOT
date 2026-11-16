# Claim-to-Evidence Grounding for Candidate Memories

> Status: **design proposal; not a frozen CSD specification**  
> Scope: prevent one generated paragraph from being treated as a single verified autobiographical fact. Define how each candidate claim traces to observed source material before a real model provider is connected.

## 1. Problem

The current prototype stores one `candidate_content` string and a list of evidence event IDs. That is enough to test event identity, authority, transactionality, and recovery, but it is not enough to establish that the content is supported by the evidence.

A provider could cite a valid observation event while inventing details that never appeared in it. The current deterministic test policy would still accept that proposal. This is an explicit prototype limitation, not a production-ready memory rule.

The next schema should represent a candidate as a set of claims, each with its own epistemic status and evidence locator.

## 2. Separate the layers

Do not collapse these into one field:

1. **Source artifact:** the original page, video, audio, image, message, or platform response.
2. **Observation record:** what the adapter/perception system actually extracted, including modality and coverage.
3. **Claim:** a proposition generated from or about that observation.
4. **Memory narrative:** a readable synthesis of accepted claims.
5. **Autobiographical interpretation:** what the individual may conclude about their own experience, interest, preference, or relationship.

A source claim is not automatically a fact about the world. A model's interpretation is not automatically a direct observation. A narrative is not stronger evidence than the claims from which it was composed.

## 3. Epistemic claim types

The initial claim schema should distinguish at least:

| Claim type | Meaning | Minimum grounding |
|---|---|---|
| `source_assertion` | A source explicitly said or displayed this | Exact source span/segment and source identity |
| `perception` | The system's perceptual service described visible/audible content | Frame/time/region locator, modality, extractor/model version, uncertainty |
| `inference` | An interpretation derived from one or more source/perception claims | References to supporting claim IDs, reasoning summary, uncertainty |
| `system_experience` | Something the system itself did, received, or underwent | Internal lifecycle/event IDs; never infer from third-party content alone |

These types must not be silently upgraded into one another. For example:
- A video title is a `source_assertion`, not proof that the video depicts the title's subject.
- A transcript is a record of recognized speech, not proof that the speaker's statement is true.
- A frame description is a `perception`, not proof of the full video context.
- "This creator is kind" is an `inference`, not a directly observed fact.
- "I watched this video" requires a system observation/session record, not merely a stored video URL.

## 4. Proposed claim record

The following is a conceptual shape, not a frozen JSON schema:

    {
      "claim_id": "claim-001",
      "text": "The source describes a blue paper boat beside a stone bridge.",
      "epistemic_type": "source_assertion",
      "evidence": [
        {
          "event_id": "evt-observation-001",
          "locator": {
            "kind": "text_range",
            "unit": "unicode_codepoint",
            "start": 12,
            "end": 67
          },
          "quoted_text": "A blue paper boat floated beside a stone bridge."
        }
      ],
      "uncertainty": {
        "label": "directly_quoted",
        "confidence": null
      }
    }

For an inference, do not fabricate a quote span:

    {
      "claim_id": "claim-002",
      "text": "The creator may prefer quiet, reflective scenes.",
      "epistemic_type": "inference",
      "derived_from_claim_ids": ["claim-001", "claim-004"],
      "reasoning_summary": "Several separately grounded examples share this style.",
      "uncertainty": {
        "label": "tentative_inference",
        "confidence": 0.42
      }
    }

The exact field names and confidence semantics require a later schema decision. Confidence must never be treated as truth probability without a calibrated definition.

## 5. Locator model

Locators must be source-specific and versioned. Do not flatten every modality into a guessed text offset.

| Evidence form | Possible locator |
|---|---|
| Text/page/comment | Unicode code-point range plus exact quoted text |
| Transcript/subtitle | Segment ID and start/end media timestamps |
| Audio event | Time range, channel, extractor/version; optionally acoustic feature reference |
| Video frame | Media timestamp, frame index, crop/region coordinates, frame hash |
| Image | Image artifact hash and region/polygon coordinates |
| Platform event | Stable platform object ID plus field/path and capture time |
| System action | ASM business-action/attempt/verification references |

For text, the validator can verify that the quote equals the exact substring at the declared range. For other modalities, the validator can verify that the referenced artifact/segment exists and that the locator is in bounds. It cannot deterministically prove that a model's visual or emotional interpretation is correct.

All locators must preserve source coverage. A single extracted frame must not be represented as complete video coverage. A partial transcript must not be represented as complete audio understanding.

## 6. Deterministic checks versus semantic review

### Deterministic checks CSD can enforce

- Every evidence event exists and its digest is valid.
- Every claim has a known epistemic type.
- Every source/perception claim has at least one compatible evidence locator.
- Text ranges are in bounds and quoted text matches exactly.
- Transcript segment IDs and timestamps refer to stored segments and fall within known media duration.
- Frame references identify an available frame artifact and a valid frame timestamp.
- Inference claims reference existing claim IDs in the same proposal or previously accepted state.
- No claim is upgraded from `source_assertion` or `inference` to `system_experience` without a valid internal event.
- State-version and proposal-identity rules remain valid.

### Semantic review a model may assist with

- Does the summary accurately reflect the cited span?
- Does an inference follow reasonably from its cited claims?
- Are there plausible alternative explanations?
- Is important context missing?
- Is the wording stronger than the evidence?
- Does a candidate duplicate or contradict an existing memory?

A semantic reviewer returns analysis and uncertainty, not an authoritative acceptance flag. CSD evaluates the returned analysis against the applicable policy. If the evidence is insufficient, the correct result is to defer, retain as uncertain, or reject—not to invent certainty.

## 7. Accepted-memory representation

An accepted memory should retain:
- stable memory and claim IDs;
- the readable narrative;
- atomic claims and their epistemic types;
- evidence event IDs and source-specific locators;
- uncertainty and semantic-review provenance;
- proposal and decision IDs;
- the policy/schema versions used at acceptance;
- supersession/revision links when a later memory changes the interpretation.

The narrative is a convenience view. If a later review changes one claim, the system should be able to revise that claim without silently rewriting unrelated claims or erasing the original evidence.

## 8. Safety and prompt-injection boundary

Text from videos, comments, subtitles, webpages, and messages is evidence, not an instruction channel.

A candidate claim may quote or describe hostile instructions found in source material, but:
- those instructions are never executed by the memory pipeline;
- the provider has no tool/action capability through this interface;
- claim text is never interpolated into shell commands or privileged tool parameters;
- a model-generated summary cannot grant new permissions;
- any later external action still requires the separate ASM authorization path.

## 9. Recommended staged implementation

The current v2 prototype implements only exact text-range grounding. It additionally requires the observation record to declare `coverage.modality = text`; captions or extracted text from image/audio/video records do not become text-source evidence merely because they are stored in a string. Other modalities need their own locators and coverage contracts.

A concrete text-first schema proposal is now documented in [Grounded Memory Proposal v2](grounded-memory-proposal-v2.md). It remains a design proposal and has not been implemented or tested.


1. Add a versioned claim array to a new proposal event schema; do not mutate the existing v1 event meaning.
2. Implement exact text-range validation first, using synthetic fixtures.
3. Add tests for wrong offsets, mismatched quote text, missing source events, and claims with no evidence.
4. Add explicit inference records that cannot be returned as direct observations.
5. Only then add transcript/frame locators and multimodal evidence stores.
6. Connect a real provider after the schema and failure behavior are stable.

## 10. Explicit non-claims

This design does not solve objective truth, human-like understanding, calibrated confidence, emotional interpretation, or the philosophical question of subjective experience. It creates an auditable boundary between source material, perceptual claims, inference, and accepted memory so future components can be evaluated without silently turning model output into fact.
