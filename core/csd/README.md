# CSD persistence reference prototypes

This directory contains two isolated Python 3.12 / SQLite reference implementations:

- `store.py`: the original generic append-only persistence spike, with its original 16-test baseline preserved.
- `cognitive.py`: the typed cognitive-memory slice, using a separate SQLite database and a separate event/projection schema.
- `proposals.py`: a v1 provider-neutral interface that converts model/provider output into untrusted candidate events; it never accepts memory state.
- `grounded_proposals.py`: the v2 typed provider boundary for claim-level text evidence; it binds evidence and state provenance and submits pending proposals only.

No real model-provider adapter is included. These reference prototypes do not integrate with DSH, SurfCore, network services, platform clients, or external-action executors. Provider interfaces are tested only with synthetic providers.

Run tests from the repository root:

```powershell
py -3.12 -m unittest discover -s tests -p "test_csd_cognitive.py" -v
py -3.12 -m unittest discover -s tests -p "test_csd_proposal_pipeline.py" -v
py -3.12 -m unittest discover -s tests -p "test_csd_grounded_memory.py" -v
py -3.12 -m unittest discover -s tests -p "test_csd_grounded_proposal_pipeline.py" -v
py -3.12 -m unittest discover -s tests -p "test_csd_memory_retrieval.py" -v
py -3.12 -m unittest discover -s tests -p "test_csd_store.py" -v
```

The generic store's WAL/DELETE journal modes and FULL/NORMAL synchronous modes are test candidates, not production durability guarantees. The cognitive slice currently uses the same selectable SQLite settings but has not been validated for Windows power-loss behavior.

The cognitive-memory implementation, both provider-neutral pipelines, and filtered Memory Retrieval API are engineering prototypes only. Retrieval currently supports exact substring/filter/pagination operations, not semantic search. The v1 free-form candidate pipeline is retained for compatibility; a real provider should target the grounded v2 path in pending-only mode. See the [memory proposal provider contract](../../docs/design/memory-proposal-provider-contract.md) and [grounded-memory v2 design](../../docs/design/grounded-memory-proposal-v2.md). See [implementation decisions](../../docs/design/csd-cognitive-slice-implementation-decision.md) and the [vertical-slice design](../../docs/design/first-cognitive-state-vertical-slice.md).
