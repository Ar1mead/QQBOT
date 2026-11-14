"""A small, side-effect-free SQLite event store for the CSD prototype.

This module intentionally has no dependency on DSH, SurfCore, platform clients,
model APIs, or external action executors. It is a reference spike, not a
production-ready cognitive-state implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping
import uuid


SCHEMA_VERSION = 1


class CSDStoreError(Exception):
    """Base exception for CSD persistence errors."""


class IdempotencyConflict(CSDStoreError):
    """An event ID was reused for different immutable event content."""


class StorageIntegrityError(CSDStoreError):
    """Durable data failed integrity or consistency validation."""


@dataclass(frozen=True)
class Event:
    event_id: str
    occurred_at: str
    correlation_id: str
    event_type: str
    source: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class RecoveryResult:
    state: dict[str, Any]
    source_snapshot_id: str | None
    replayed_events: int
    rejected_snapshots: tuple[str, ...]


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _validate_timestamp(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone offset")


def _initial_state() -> dict[str, Any]:
    return {
        "accepted_event_count": 0,
        "event_counts": {},
        "last_event": None,
        "last_sequence": 0,
    }


class CSDStore:
    """Append-only event log plus a rebuildable deterministic projection."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        busy_timeout_ms: int = 5000,
        synchronous: str = "FULL",
    ) -> None:
        if busy_timeout_ms < 0:
            raise ValueError("busy_timeout_ms must be non-negative")
        if synchronous not in {"FULL", "NORMAL"}:
            raise ValueError("synchronous must be FULL or NORMAL")

        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(
            str(self.database_path),
            timeout=busy_timeout_ms / 1000,
            isolation_level=None,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
        # Prototype candidate only; not a production durability guarantee.
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.execute(f"PRAGMA synchronous = {synchronous}")
        self._initialize_schema()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "CSDStore":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def _initialize_schema(self) -> None:
        version = int(self._connection.execute("PRAGMA user_version").fetchone()[0])
        if version > SCHEMA_VERSION:
            raise StorageIntegrityError(
                f"database schema version {version} is newer than supported {SCHEMA_VERSION}"
            )
        if version == SCHEMA_VERSION:
            return
        if version != 0:
            raise StorageIntegrityError(f"unsupported database schema version: {version}")

        self._connection.executescript(
            """
            BEGIN IMMEDIATE;
            CREATE TABLE event_payloads (
                payload_ref TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            );

            CREATE TABLE events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                occurred_at TEXT NOT NULL,
                received_at TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                source TEXT NOT NULL,
                payload_ref TEXT NOT NULL,
                event_digest TEXT NOT NULL,
                FOREIGN KEY (payload_ref) REFERENCES event_payloads(payload_ref)
            );

            CREATE TRIGGER events_no_update
            BEFORE UPDATE ON events
            BEGIN
                SELECT RAISE(ABORT, 'events are append-only');
            END;

            CREATE TRIGGER events_no_delete
            BEFORE DELETE ON events
            BEGIN
                SELECT RAISE(ABORT, 'events are append-only');
            END;

            CREATE TRIGGER payloads_no_update
            BEFORE UPDATE ON event_payloads
            BEGIN
                SELECT RAISE(ABORT, 'event payloads are immutable');
            END;

            CREATE TRIGGER payloads_no_delete
            BEFORE DELETE ON event_payloads
            BEGIN
                SELECT RAISE(ABORT, 'event payloads are immutable');
            END;

            CREATE TABLE projection_state (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                state_json TEXT NOT NULL,
                updated_through_sequence INTEGER NOT NULL
            );

            CREATE TABLE snapshots (
                snapshot_id TEXT PRIMARY KEY,
                through_sequence INTEGER NOT NULL,
                state_json TEXT NOT NULL,
                state_digest TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            INSERT INTO projection_state(singleton, state_json, updated_through_sequence)
            VALUES (1, '{"accepted_event_count":0,"event_counts":{},"last_event":null,"last_sequence":0}', 0);

            PRAGMA user_version = 1;
            COMMIT;
            """
        )

    class _Transaction:
        def __init__(self, connection: sqlite3.Connection) -> None:
            self.connection = connection

        def __enter__(self) -> sqlite3.Connection:
            self.connection.execute("BEGIN IMMEDIATE")
            return self.connection

        def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
            if exc_type is None:
                self.connection.execute("COMMIT")
            else:
                self.connection.execute("ROLLBACK")
            return False

    def _transaction(self) -> "CSDStore._Transaction":
        return self._Transaction(self._connection)

    @staticmethod
    def _event_digest(
        *,
        event_id: str,
        occurred_at: str,
        correlation_id: str,
        event_type: str,
        source: str,
        payload_ref: str,
    ) -> str:
        immutable = {
            "event_id": event_id,
            "occurred_at": occurred_at,
            "correlation_id": correlation_id,
            "event_type": event_type,
            "source": source,
            "payload_ref": payload_ref,
        }
        return _sha256(_canonical_json(immutable))

    def submit_event(self, event: Event) -> dict[str, Any]:
        """Persist an event and its projection update in one transaction."""
        required = {
            "event_id": event.event_id,
            "correlation_id": event.correlation_id,
            "event_type": event.event_type,
            "source": event.source,
        }
        for name, value in required.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        _validate_timestamp(event.occurred_at, "occurred_at")
        if not isinstance(event.payload, Mapping):
            raise ValueError("payload must be a mapping/object")

        payload_json = _canonical_json(dict(event.payload))
        payload_ref = f"sha256:{_sha256(payload_json)}"
        event_digest = self._event_digest(
            event_id=event.event_id,
            occurred_at=event.occurred_at,
            correlation_id=event.correlation_id,
            event_type=event.event_type,
            source=event.source,
            payload_ref=payload_ref,
        )
        received_at = datetime.now(timezone.utc).isoformat()

        with self._transaction() as connection:
            existing = connection.execute(
                "SELECT occurred_at, correlation_id, event_type, source, payload_ref "
                "FROM events WHERE event_id = ?",
                (event.event_id,),
            ).fetchone()
            if existing is not None:
                same = (
                    existing["occurred_at"] == event.occurred_at
                    and existing["correlation_id"] == event.correlation_id
                    and existing["event_type"] == event.event_type
                    and existing["source"] == event.source
                    and existing["payload_ref"] == payload_ref
                )
                if not same:
                    raise IdempotencyConflict(
                        f"event_id {event.event_id!r} was already accepted with different content"
                    )
                row = connection.execute(
                    "SELECT sequence, received_at FROM events WHERE event_id = ?",
                    (event.event_id,),
                ).fetchone()
                return {
                    "status": "duplicate",
                    "event_id": event.event_id,
                    "sequence": int(row["sequence"]),
                    "received_at": row["received_at"],
                }

            connection.execute(
                "INSERT OR IGNORE INTO event_payloads(payload_ref, payload_json) VALUES (?, ?)",
                (payload_ref, payload_json),
            )
            stored_payload = connection.execute(
                "SELECT payload_json FROM event_payloads WHERE payload_ref = ?",
                (payload_ref,),
            ).fetchone()
            if stored_payload is None or stored_payload["payload_json"] != payload_json:
                raise StorageIntegrityError("content-addressed payload collision or corruption")

            cursor = connection.execute(
                "INSERT INTO events(event_id, occurred_at, received_at, correlation_id, "
                "event_type, source, payload_ref, event_digest) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event.event_id,
                    event.occurred_at,
                    received_at,
                    event.correlation_id,
                    event.event_type,
                    event.source,
                    payload_ref,
                    event_digest,
                ),
            )
            sequence = int(cursor.lastrowid)
            state_row = connection.execute(
                "SELECT state_json FROM projection_state WHERE singleton = 1"
            ).fetchone()
            if state_row is None:
                raise StorageIntegrityError("projection state row is missing")
            state = json.loads(state_row["state_json"])
            state = self._reduce(state, event, sequence)
            state_json = _canonical_json(state)
            connection.execute(
                "UPDATE projection_state SET state_json = ?, updated_through_sequence = ? "
                "WHERE singleton = 1",
                (state_json, sequence),
            )

        return {
            "status": "accepted",
            "event_id": event.event_id,
            "sequence": sequence,
            "received_at": received_at,
            "payload_ref": payload_ref,
        }

    @staticmethod
    def _reduce(state: dict[str, Any], event: Event, sequence: int) -> dict[str, Any]:
        """Pure deterministic reducer used only by this synthetic prototype."""
        updated = json.loads(_canonical_json(state))
        counts = updated.setdefault("event_counts", {})
        counts[event.event_type] = int(counts.get(event.event_type, 0)) + 1
        updated["accepted_event_count"] = int(updated.get("accepted_event_count", 0)) + 1
        updated["last_event"] = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "source": event.source,
        }
        updated["last_sequence"] = sequence
        return updated

    def get_state_snapshot(self) -> dict[str, Any]:
        row = self._connection.execute(
            "SELECT state_json, updated_through_sequence FROM projection_state WHERE singleton = 1"
        ).fetchone()
        if row is None:
            raise StorageIntegrityError("projection state row is missing")
        return {
            "state": json.loads(row["state_json"]),
            "through_sequence": int(row["updated_through_sequence"]),
        }

    def create_snapshot(self) -> str:
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT state_json, updated_through_sequence FROM projection_state WHERE singleton = 1"
            ).fetchone()
            if row is None:
                raise StorageIntegrityError("projection state row is missing")
            state_json = _canonical_json(json.loads(row["state_json"]))
            through_sequence = int(row["updated_through_sequence"])
            snapshot_id = str(uuid.uuid4())
            connection.execute(
                "INSERT INTO snapshots(snapshot_id, through_sequence, state_json, state_digest, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    snapshot_id,
                    through_sequence,
                    state_json,
                    _sha256(state_json),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        return snapshot_id

    @staticmethod
    def _validate_projection(state: Any, through_sequence: int) -> bool:
        if not isinstance(state, dict):
            return False
        required = {"accepted_event_count", "event_counts", "last_event", "last_sequence"}
        if required - set(state):
            return False
        if not isinstance(state["accepted_event_count"], int) or state["accepted_event_count"] < 0:
            return False
        if not isinstance(state["event_counts"], dict):
            return False
        if any(
            not isinstance(key, str) or not isinstance(value, int) or value < 0
            for key, value in state["event_counts"].items()
        ):
            return False
        if sum(state["event_counts"].values()) != state["accepted_event_count"]:
            return False
        if state["last_sequence"] != through_sequence:
            return False
        if through_sequence == 0 and state["last_event"] is not None:
            return False
        if through_sequence > 0 and not isinstance(state["last_event"], dict):
            return False
        return True

    def recover(self) -> RecoveryResult:
        """Rebuild the projection from validated durable records; never dispatch actions."""
        integrity = self._connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise StorageIntegrityError(f"SQLite integrity_check failed: {integrity}")
        fk_errors = self._connection.execute("PRAGMA foreign_key_check").fetchall()
        if fk_errors:
            raise StorageIntegrityError("SQLite foreign_key_check found violations")

        rows = self._connection.execute(
            "SELECT e.sequence, e.event_id, e.occurred_at, e.correlation_id, e.event_type, "
            "e.source, e.payload_ref, e.event_digest, p.payload_json "
            "FROM events AS e LEFT JOIN event_payloads AS p ON p.payload_ref = e.payload_ref "
            "ORDER BY e.sequence ASC"
        ).fetchall()

        events: list[tuple[int, Event]] = []
        expected_sequence = 1
        for row in rows:
            sequence = int(row["sequence"])
            if sequence != expected_sequence:
                raise StorageIntegrityError(
                    f"event sequence gap: expected {expected_sequence}, found {sequence}"
                )
            expected_sequence += 1
            payload_json = row["payload_json"]
            if payload_json is None:
                raise StorageIntegrityError(f"missing payload for event {row['event_id']}")
            if f"sha256:{_sha256(payload_json)}" != row["payload_ref"]:
                raise StorageIntegrityError(f"payload digest mismatch for event {row['event_id']}")
            try:
                payload = json.loads(payload_json)
            except json.JSONDecodeError as exc:
                raise StorageIntegrityError(f"invalid payload JSON for event {row['event_id']}") from exc
            if not isinstance(payload, dict):
                raise StorageIntegrityError(f"payload for event {row['event_id']} is not an object")
            computed_digest = self._event_digest(
                event_id=row["event_id"],
                occurred_at=row["occurred_at"],
                correlation_id=row["correlation_id"],
                event_type=row["event_type"],
                source=row["source"],
                payload_ref=row["payload_ref"],
            )
            if computed_digest != row["event_digest"]:
                raise StorageIntegrityError(f"event envelope digest mismatch for {row['event_id']}")
            events.append(
                (
                    sequence,
                    Event(
                        event_id=row["event_id"],
                        occurred_at=row["occurred_at"],
                        correlation_id=row["correlation_id"],
                        event_type=row["event_type"],
                        source=row["source"],
                        payload=payload,
                    ),
                )
            )

        snapshots = self._connection.execute(
            "SELECT snapshot_id, through_sequence, state_json, state_digest "
            "FROM snapshots ORDER BY through_sequence DESC, created_at DESC"
        ).fetchall()
        valid_snapshot: sqlite3.Row | None = None
        rejected: list[str] = []
        max_sequence = len(events)
        event_sequences = {sequence for sequence, _ in events}
        for snapshot in snapshots:
            snapshot_id = snapshot["snapshot_id"]
            through = int(snapshot["through_sequence"])
            state_json = snapshot["state_json"]
            try:
                state = json.loads(state_json)
            except json.JSONDecodeError:
                rejected.append(f"{snapshot_id}: invalid JSON")
                continue
            if _sha256(_canonical_json(state)) != snapshot["state_digest"]:
                rejected.append(f"{snapshot_id}: digest mismatch")
                continue
            if through < 0 or through > max_sequence:
                rejected.append(f"{snapshot_id}: invalid event offset")
                continue
            if through > 0 and through not in event_sequences:
                rejected.append(f"{snapshot_id}: event offset not present")
                continue
            if not self._validate_projection(state, through):
                rejected.append(f"{snapshot_id}: invalid projection shape")
                continue
            valid_snapshot = snapshot
            break

        if valid_snapshot is None:
            state = _initial_state()
            start_sequence = 0
            source_snapshot_id = None
        else:
            state = json.loads(valid_snapshot["state_json"])
            start_sequence = int(valid_snapshot["through_sequence"])
            source_snapshot_id = valid_snapshot["snapshot_id"]

        replayed = 0
        for sequence, event in events:
            if sequence <= start_sequence:
                continue
            state = self._reduce(state, event, sequence)
            replayed += 1

        with self._transaction() as connection:
            connection.execute(
                "UPDATE projection_state SET state_json = ?, updated_through_sequence = ? "
                "WHERE singleton = 1",
                (_canonical_json(state), int(state["last_sequence"])),
            )

        return RecoveryResult(
            state=state,
            source_snapshot_id=source_snapshot_id,
            replayed_events=replayed,
            rejected_snapshots=tuple(rejected),
        )
