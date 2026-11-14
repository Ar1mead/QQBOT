# CSD persistence reference spike

This is a disposable Python 3.12 / SQLite reference implementation for the first CSD persistence vertical slice. It uses synthetic events only and has no DSH, SurfCore, model, network, platform, or external-action integration.

Run tests from this directory:

```powershell
py -3.12 -m unittest discover -s tests -v
```

The database file is created only at the path explicitly passed to CSDStore. The prototype currently uses SQLite WAL mode and synchronous FULL as a conservative test candidate; this is not a production durability guarantee. See the design proposal and ADR 0002.
