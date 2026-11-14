# ADR 0002 — Python Reference Prototype for the CSD Persistence Slice

- Status: **accepted for a disposable reference prototype only**
- Date: 2026-11-14
- Scope: first CSD event/persistence/recovery vertical slice
- Does not decide the final production language or process topology.

## Context

CSD must remain independent of DSH and any one runtime. The local environment has Python 3.12.14 and Node.js 24.21.0.

Python 3.12 provides the standard-library `sqlite3` module. Its transaction API supports explicit transaction control, including `BEGIN IMMEDIATE` through the documented transaction interface. This permits a first persistence prototype without adding a third-party database package.

Node.js 24.21.0 includes `node:sqlite`, but the official Node.js v24 documentation classifies the API as Stability 1.2 — Release candidate, not Stable (Stability 2). The API is promising and may be appropriate later, but it is not the conservative choice for the first durability-focused prototype.

References:
- Python 3.12 `sqlite3`: https://docs.python.org/3.12/library/sqlite3.html
- Node.js v24.21.0 API stability definitions: https://nodejs.org/download/release/v24.21.0/docs/api/all.html
- Node.js v24 SQLite API status: https://nodejs.org/download/release/v24.21.0/docs/api/sqlite.html

## Decision

Use Python 3.12 standard-library `sqlite3` for a **disposable, isolated reference implementation** of the CSD persistence vertical slice.

The prototype will:
- use synthetic events only;
- contain no model calls, external integrations, or side-effect executors;
- implement event idempotency, atomic projection updates, snapshots, and recovery;
- be independently testable from DSH and SurfCore;
- live on a dedicated feature branch, not in the documentation branch or main.

## Consequences

Positive:
- no external Python package is required for SQLite;
- transaction and recovery behavior can be tested without relying on Node's release-candidate SQLite API;
- the prototype is easy to discard or port if the final integration evidence favors another language.

Trade-offs:
- a later DSH integration will need an explicit process/API boundary or a port to another language;
- this decision does not establish Python as the permanent CSD language;
- Windows packaging, service lifecycle, and IPC remain untested.

## Revisit conditions

Reconsider the language/process decision after:
1. the Python prototype passes atomicity, idempotency, snapshot, and recovery tests;
2. the actual DSH integration boundary is tested;
3. Node.js `node:sqlite` reaches Stable status or a stable maintained alternative is selected;
4. deployment and process-lifecycle trade-offs are measured on the target Windows machine.

No production deployment or user-machine installation is authorized by this ADR.
