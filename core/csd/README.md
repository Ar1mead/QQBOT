# CSD persistence reference prototypes

This directory contains two isolated Python 3.12 / SQLite reference implementations:

- `store.py`: the original generic append-only persistence spike, with its original 16-test baseline preserved.
- `cognitive.py`: the typed cognitive-memory slice, using a separate SQLite database and a separate event/projection schema.
- `proposals.py`: a v1 provider-neutral interface that converts model/provider output into untrusted candidate events; it never accepts memory state.
- `grounded_proposals.py`: the v2 typed provider boundary for claim-level text evidence; it binds evidence and state provenance and submits pending proposals only.

Neither implementation integrates with DSH, SurfCore, models, network services, platform clients, or external-action executors.

Run tests from the repository root:

```powershell
py -3.12 -m unittest discover -s tests -p "test_csd_cognitive.py" -v
py -3.12 -m unittest discover -s tests -p "test_csd_proposal_pipeline.py" -v
py -3.12 -m unittest discover -s tests -p "test_csd_grounded_memory.py" -v
py -3.12 -m unittest discover -s tests -p "test_csd_grounded_proposal_pipeline.py" -v
py -3.12 -m unittest discover -s tests -p "test_csd_store.py" -v
```

The generic store's WAL/DELETE journal modes and FULL/NORMAL synchronous modes are test candidates, not production durability guarantees. The cognitive slice currently uses the same selectable SQLite settings but has not been validated for Windows power-loss behavior.

The cognitive-memory implementation and provider-neutral proposal pipeline are engineering prototypes only. See the [memory proposal provider contract](../../docs/design/memory-proposal-provider-contract.md). See [implementation decisions](../../docs/design/csd-cognitive-slice-implementation-decision.md) and the [vertical-slice design](../../docs/design/first-cognitive-state-vertical-slice.md).
