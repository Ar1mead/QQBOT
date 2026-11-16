# CSD Observation Event v2 Contract

> Status: implemented reference contract for the current CSD slice. This document records the event shape and compatibility rules; it does not authorize a real platform connection.

## 1. Purpose

Observation v1 remains supported for historical fixtures and existing event logs. Observation v2 is the adapter-facing event envelope for richer source provenance and explicit coverage. It records what an adapter supplied or extracted; it does not convert external content into trusted facts, accepted memories, preferences, or goals.

Event type: `experience.observation_recorded.v2`.

## 2. Payload

The v2 payload has exactly these top-level fields:

| Field | Meaning |
|---|---|
| `observation_id` | Stable observation identity within the adapter |
| `adapter_id`, `adapter_version` | Adapter identity and version |
| `platform` | Source platform |
| `account_ref` | Optional opaque account reference; never a credential or display name |
| `external_ref` | Platform object/message reference |
| `observation_kind` | Kind of captured source material |
| `content_origin` | `source_provided` or `adapter_extracted` |
| `modality` | Text, audio, image, video, metadata, or another declared modality |
| `content` | Non-empty UTF-8 text representation captured by the adapter |
| `source_ref` | Stable source reference |
| `source_artifact_ref` | Optional reference to the source artifact; not the artifact bytes |
| `observed_at`, `received_at` | Source/observation time and local receipt time, separately retained |
| `extraction_method` | Method used to obtain the content |
| `content_digest` | `sha256:` plus SHA-256 of the exact UTF-8 bytes in `content` |
| `coverage` | Modality, extraction method, completeness, optional time bounds, missing ranges, and notes |
| `untrusted` | Must be the boolean `true` |

The coverage object has exactly these fields: `modality`, `extraction_method`, `complete`, `start_ms`, `end_ms`, `missing_ranges_ms`, and `notes`. Its modality and extraction method must match the top-level values. A complete coverage record cannot declare missing ranges. Time bounds and missing ranges are non-negative and ordered.

## 3. Content origin is provenance, not truth

- `source_provided` means the platform/source supplied the content, for example a title, subtitle, comment, or message.
- `adapter_extracted` means the adapter extracted or transcribed it, for example by ASR or OCR.

Neither value means that the content is true. A platform subtitle remains a source-provided claim; an ASR transcript remains an adapter-produced transcription. Model summaries and interpretations are not observation content. They belong in separate claim/proposal records.

Grounded-memory v2 may quote exact text spans from either v1 or v2 text observations. It still rejects non-text evidence for text-span grounding, and inference claims remain distinct from source assertions and subject to semantic review.

## 4. Stable event identity and mapping

The adapter-to-CSD mapper emits:

- event ID and correlation ID: `observation:{adapter_id}:{observation_id}`;
- source: `observation-adapter:{adapter_id}`;
- event-envelope `occurred_at`: `received_at`;
- payload: a lossless mapping of the adapter evidence and coverage fields.

This stable identity lets CSD treat an identical repeated delivery as an idempotent event and a conflicting reuse as an integrity conflict. The mapper does not make external calls or write platform state.

## 5. Backward compatibility

Observation v1 keeps its original event name and exact payload schema. CSD direct reads, proposal chronology checks, grounded-memory evidence checks, and Recovery accept both v1 and v2. Existing v1 events are not rewritten or migrated.

## 6. Limits and security boundary

- V2 stores a text representation plus references and metadata; it does not embed raw video/audio/image bytes in the event log.
- External evidence remains untrusted even when its digest and provenance validate.
- An opaque account reference is not authentication and must not contain cookies, tokens, or credentials.
- Partial coverage must remain partial; absent media segments, unavailable comments, and failed extractors must not be described as complete perception.
- This implementation does not connect to Bilibili, log into an account, install a DSH plugin, or authorize any external action.
