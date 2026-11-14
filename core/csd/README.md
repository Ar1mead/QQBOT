# CSD persistence reference spike

This is a disposable Python 3.12 / SQLite reference implementation for the first CSD persistence vertical slice. It uses synthetic events only and has no DSH, SurfCore, model, network, platform, or external-action integration.

Run tests from this directory:

```powershell
py -3.12 -m unittest discover -s tests -v
```

The database file is created only at the path explicitly passed to CSDStore. WAL/DELETE journal modes and FULL/NORMAL synchronous modes are selectable for the initial matrix test; defaults are WAL + FULL. These are test candidates, not production durability guarantees. See the design proposal and ADR 0002.

## Typed cognitive-memory slice

The isolated cognitive-memory prototype is implemented in `cognitive.py` and exported as `CognitiveMemoryStore`. It uses a separate SQLite database from the original generic persistence spike.

Run both suites from the repository root:

```powershell
py -3.12 -m unittest discover -s tests -p "test_csd_cognitive.py" -v
py -3.12 -m unittest discover -s tests -p "test_csd_store.py" -v
```

The cognitive-memory implementation is an engineering prototype only. See [implementation decisions](../../docs/design/csd-cognitive-slice-implementation-decision.md) and the [vertical-slice design](../../docs/design/first-cognitive-state-vertical-slice.md).
