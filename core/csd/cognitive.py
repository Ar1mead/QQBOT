"""Typed, event-sourced cognitive-memory slice for the CSD prototype.

This module is an isolated reference implementation. It deliberately does not
call models, adapters, the network, a shell, or external action executors.
It is not a security boundary against hostile code in the same Python process.
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
OBSERVATION_EVENT = "experience.observation_recorded.v1"
PROPOSAL_EVENT = "cognition.memory_candidate_proposed.v1"
DECISION_EVENT = "cognition.memory_candidate_decided.v1"
DECISION_SOURCE = "csd.authority.v1"
POLICY_ID = "csd.memory-provenance-check"
POLICY_VERSION = "0.1"


class CognitiveStoreError(Exception):
    """Base error for the cognitive-memory reference slice."""


class CognitiveIdempotencyConflict(CognitiveStoreError):
    """An event identity was reused with different immutable content."""


class ProposalIdentityConflict(CognitiveStoreError):
    """A proposal identity was reused with different immutable content."""


class CognitiveIntegrityError(CognitiveStoreError):
    """Durable event history or its projections are inconsistent."""


@dataclass(frozen=True)
class CognitiveEvent:
    event_id: str
    occurred_at: str
    correlation_id: str
    event_type: str
    source: str
    payload: Mapping[str, Any]


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _timestamp(value: str, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone offset")


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


class CognitiveMemoryStore:
    """Single event stream with rebuildable proposal and accepted-memory views."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        busy_timeout_ms: int = 5000,
        journal_mode: str = "WAL",
        synchronous: str = "FULL",
    ) -> None:
        if busy_timeout_ms < 0:
            raise ValueError("busy_timeout_ms must be non-negative")
        if journal_mode not in {"WAL", "DELETE"}:
            raise ValueError("journal_mode must be WAL or DELETE")
        if synchronous not in {"FULL", "NORMAL"}:
            raise ValueError("synchronous must be FULL or NORMAL")

        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(
            str(self.database_path),
            timeout=busy_timeout_ms / 1000,
            isolation_level=None,
        )
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
        self._db.execute(f"PRAGMA journal_mode = {journal_mode}")
        self._db.execute(f"PRAGMA synchronous = {synchronous}")
        self._initialize()

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "CognitiveMemoryStore":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def _initialize(self) -> None:
        version = int(self._db.execute("PRAGMA user_version").fetchone()[0])
        if version > SCHEMA_VERSION:
            raise CognitiveIntegrityError(
                f"database schema {version} is newer than supported {SCHEMA_VERSION}"
            )
        if version == SCHEMA_VERSION:
            return
        if version != 0:
            raise CognitiveIntegrityError(f"unsupported schema version: {version}")

        self._db.executescript(
            """
            BEGIN IMMEDIATE;
            CREATE TABLE payloads (
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
                FOREIGN KEY(payload_ref) REFERENCES payloads(payload_ref)
            );
            CREATE TRIGGER events_no_update BEFORE UPDATE ON events
            BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
            CREATE TRIGGER events_no_delete BEFORE DELETE ON events
            BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
            CREATE TRIGGER payloads_no_update BEFORE UPDATE ON payloads
            BEGIN SELECT RAISE(ABORT, 'payloads are immutable'); END;
            CREATE TRIGGER payloads_no_delete BEFORE DELETE ON payloads
            BEGIN SELECT RAISE(ABORT, 'payloads are immutable'); END;

            CREATE TABLE proposals (
                proposal_id TEXT PRIMARY KEY,
                proposal_digest TEXT NOT NULL,
                proposal_event_id TEXT NOT NULL,
                proposal_json TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending','accepted','rejected','deferred','needs_more_evidence')),
                decision_event_id TEXT
            );
            CREATE TABLE accepted_memories (
                memory_id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL UNIQUE,
                transition_id TEXT NOT NULL UNIQUE,
                memory_json TEXT NOT NULL,
                FOREIGN KEY(proposal_id) REFERENCES proposals(proposal_id)
            );
            PRAGMA user_version = 1;
            COMMIT;
            """
        )

    class _Tx:
        def __init__(self, db: sqlite3.Connection) -> None:
            self.db = db

        def __enter__(self) -> sqlite3.Connection:
            self.db.execute("BEGIN IMMEDIATE")
            return self.db

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
            self.db.execute("COMMIT" if exc_type is None else "ROLLBACK")
            return False

    def _tx(self) -> "CognitiveMemoryStore._Tx":
        return self._Tx(self._db)

    @staticmethod
    def _event_digest(
        event: CognitiveEvent, payload_ref: str, received_at: str
    ) -> str:
        return _digest(_canonical({
            "event_id": event.event_id,
            "occurred_at": event.occurred_at,
            "received_at": received_at,
            "correlation_id": event.correlation_id,
            "event_type": event.event_type,
            "source": event.source,
            "payload_ref": payload_ref,
        }))

    def _validate_event(self, event: CognitiveEvent, *, internal: bool = False) -> str:
        _nonempty(event.event_id, "event_id")
        if not internal and event.event_id.startswith("csd-decision:"):
            raise ValueError("event_id uses a namespace reserved for CSD decisions")
        _nonempty(event.correlation_id, "correlation_id")
        _nonempty(event.event_type, "event_type")
        _nonempty(event.source, "source")
        _timestamp(event.occurred_at, "occurred_at")
        if not isinstance(event.payload, Mapping):
            raise ValueError("payload must be an object")
        if event.event_type == DECISION_EVENT and not internal:
            raise ValueError("CSD decision events are reserved for the internal authority path")
        if event.event_type not in {OBSERVATION_EVENT, PROPOSAL_EVENT, DECISION_EVENT}:
            raise ValueError(f"unsupported event type: {event.event_type}")
        if event.event_type == DECISION_EVENT and event.source != DECISION_SOURCE:
            raise ValueError("decision event source must identify CSD authority")
        return _canonical(dict(event.payload))

    def submit_event(self, event: CognitiveEvent) -> dict[str, Any]:
        """Public Event Submit path. It cannot submit CSD-reserved decisions."""
        payload_json = self._validate_event(event)
        return self._append_event(event, payload_json, internal=False)

    def _append_event(
        self, event: CognitiveEvent, payload_json: str, *, internal: bool
    ) -> dict[str, Any]:
        with self._tx() as db:
            return self._append_event_in_transaction(
                db, event, payload_json, internal=internal
            )

    def _append_event_in_transaction(
        self,
        db: sqlite3.Connection,
        event: CognitiveEvent,
        payload_json: str,
        *,
        internal: bool,
    ) -> dict[str, Any]:
        if event.event_type == DECISION_EVENT and not internal:
            raise ValueError("reserved decision event")
        payload_ref = "sha256:" + _digest(payload_json)
        received_at = datetime.now(timezone.utc).isoformat()
        event_digest = self._event_digest(event, payload_ref, received_at)

        prior = db.execute(
            "SELECT sequence, occurred_at, correlation_id, event_type, source, "
            "payload_ref, received_at FROM events WHERE event_id=?",
            (event.event_id,),
        ).fetchone()
        if prior is not None:
            same = (
                prior["occurred_at"] == event.occurred_at
                and prior["correlation_id"] == event.correlation_id
                and prior["event_type"] == event.event_type
                and prior["source"] == event.source
                and prior["payload_ref"] == payload_ref
            )
            if not same:
                raise CognitiveIdempotencyConflict(event.event_id)
            return {
                "status": "duplicate",
                "event_id": event.event_id,
                "sequence": int(prior["sequence"]),
                "received_at": prior["received_at"],
            }

        if event.event_type == PROPOSAL_EVENT:
            proposal_id = _nonempty(event.payload.get("proposal_id"), "proposal_id")
            proposal_digest = _digest(payload_json)
            existing = db.execute(
                "SELECT proposal_digest FROM proposals WHERE proposal_id=?",
                (proposal_id,),
            ).fetchone()
            if existing is not None and existing["proposal_digest"] != proposal_digest:
                raise ProposalIdentityConflict(proposal_id)

        db.execute(
            "INSERT OR IGNORE INTO payloads(payload_ref,payload_json) VALUES (?,?)",
            (payload_ref, payload_json),
        )
        stored = db.execute(
            "SELECT payload_json FROM payloads WHERE payload_ref=?", (payload_ref,)
        ).fetchone()
        if stored is None or stored["payload_json"] != payload_json:
            raise CognitiveIntegrityError("payload digest collision/corruption")

        cursor = db.execute(
            "INSERT INTO events(event_id,occurred_at,received_at,correlation_id,"
            "event_type,source,payload_ref,event_digest) VALUES (?,?,?,?,?,?,?,?)",
            (event.event_id, event.occurred_at, received_at, event.correlation_id,
             event.event_type, event.source, payload_ref, event_digest),
        )
        sequence = int(cursor.lastrowid)
        self._apply_projection_event(db, event, sequence, internal=internal)
        return {
            "status": "accepted",
            "event_id": event.event_id,
            "sequence": sequence,
            "received_at": received_at,
            "payload_ref": payload_ref,
        }

    @staticmethod
    def _validate_observation(payload: Mapping[str, Any]) -> None:
        allowed = {"observation_id", "observation_kind", "content", "source_ref", "observed_at", "coverage"}
        if set(payload) != allowed:
            raise ValueError("observation payload contains missing or unsupported fields")
        _nonempty(payload.get("observation_id"), "observation_id")
        _nonempty(payload.get("observation_kind"), "observation_kind")
        _nonempty(payload.get("content"), "content")
        _nonempty(payload.get("source_ref"), "source_ref")
        _timestamp(payload.get("observed_at"), "observed_at")
        coverage = payload.get("coverage")
        if not isinstance(coverage, Mapping) or set(coverage) != {"modality", "complete_for_fixture"}:
            raise ValueError("coverage must contain only modality and complete_for_fixture")
        _nonempty(coverage.get("modality"), "coverage.modality")
        if not isinstance(coverage.get("complete_for_fixture"), bool):
            raise ValueError("coverage.complete_for_fixture must be boolean")

    @staticmethod
    def _validate_proposal(payload: Mapping[str, Any]) -> None:
        allowed = {
            "proposal_id", "memory_kind", "candidate_content", "evidence_event_ids",
            "origin", "uncertainty", "based_on", "operation",
        }
        if set(payload) != allowed:
            raise ValueError("proposal payload contains missing or unsupported fields")
        _nonempty(payload.get("proposal_id"), "proposal_id")
        _nonempty(payload.get("memory_kind"), "memory_kind")
        _nonempty(payload.get("candidate_content"), "candidate_content")
        refs = payload.get("evidence_event_ids")
        if not isinstance(refs, list) or not refs or any(
            not isinstance(item, str) or not item.strip() for item in refs
        ):
            raise ValueError("evidence_event_ids must be a non-empty string list")
        if len(set(refs)) != len(refs):
            raise ValueError("evidence_event_ids must not contain duplicates")
        origin = payload.get("origin")
        if not isinstance(origin, Mapping) or set(origin) != {"component", "version"}:
            raise ValueError("origin must contain only component and version")
        _nonempty(origin.get("component"), "origin.component")
        _nonempty(origin.get("version"), "origin.version")
        based_on = payload.get("based_on")
        if not isinstance(based_on, Mapping) or set(based_on) != {"state_version"}:
            raise ValueError("based_on must contain only state_version")
        version = based_on.get("state_version")
        if not isinstance(version, int) or isinstance(version, bool) or version < 0:
            raise ValueError("based_on.state_version must be a non-negative integer")
        if payload.get("operation") != "create":
            raise ValueError("this slice only supports operation=create")
        uncertainty = payload.get("uncertainty")
        if not isinstance(uncertainty, Mapping) or set(uncertainty) - {"label", "confidence"}:
            raise ValueError("uncertainty contains unsupported fields")
        _nonempty(uncertainty.get("label"), "uncertainty.label")
        confidence = uncertainty.get("confidence")
        if confidence is not None and (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not 0.0 <= float(confidence) <= 1.0
        ):
            raise ValueError("uncertainty.confidence must be null or between 0 and 1")

    def _apply_projection_event(
        self,
        db: sqlite3.Connection,
        event: CognitiveEvent,
        sequence: int,
        *,
        internal: bool,
    ) -> None:
        if event.event_type == OBSERVATION_EVENT:
            self._validate_observation(event.payload)
            return
        if event.event_type == PROPOSAL_EVENT:
            self._validate_proposal(event.payload)
            proposal_id = str(event.payload["proposal_id"])
            proposal_json = _canonical(dict(event.payload))
            proposal_digest = _digest(proposal_json)
            existing = db.execute(
                "SELECT proposal_digest FROM proposals WHERE proposal_id=?",
                (proposal_id,),
            ).fetchone()
            if existing is None:
                db.execute(
                    "INSERT INTO proposals(proposal_id,proposal_digest,proposal_event_id,"
                    "proposal_json,status) VALUES (?,?,?,?, 'pending')",
                    (proposal_id, proposal_digest, event.event_id, proposal_json),
                )
            elif existing["proposal_digest"] != proposal_digest:
                raise ProposalIdentityConflict(proposal_id)
            return
        if event.event_type == DECISION_EVENT:
            if not internal or event.source != DECISION_SOURCE:
                raise CognitiveIntegrityError("non-authoritative decision event")
            self._apply_decision(db, event)
            return
        raise CognitiveIntegrityError(f"unhandled event type at sequence {sequence}")

    @staticmethod
    def _authoritative_state_version(
        db: sqlite3.Connection, *, exclude_event_id: str | None = None
    ) -> int:
        query = (
            "SELECT p.payload_json FROM events e "
            "JOIN payloads p ON p.payload_ref=e.payload_ref "
            "WHERE e.event_type=?"
        )
        params: list[Any] = [DECISION_EVENT]
        if exclude_event_id is not None:
            query += " AND e.event_id<>?"
            params.append(exclude_event_id)
        query += " ORDER BY e.sequence"
        version = 0
        for row in db.execute(query, params).fetchall():
            try:
                decision = json.loads(row["payload_json"])
            except json.JSONDecodeError as exc:
                raise CognitiveIntegrityError("invalid durable decision payload") from exc
            outcome = decision.get("outcome") if isinstance(decision, dict) else None
            if outcome not in {"accepted", "rejected", "deferred", "needs_more_evidence"}:
                raise CognitiveIntegrityError("invalid durable decision outcome")
            if outcome == "accepted":
                version += 1
        return version

    def _apply_decision(self, db: sqlite3.Connection, event: CognitiveEvent) -> None:
        payload = event.payload
        proposal_id = _nonempty(payload.get("proposal_id"), "decision.proposal_id")
        outcome = _nonempty(payload.get("outcome"), "decision.outcome")
        if outcome not in {"accepted", "rejected", "deferred", "needs_more_evidence"}:
            raise CognitiveIntegrityError("invalid decision outcome")
        proposal = db.execute(
            "SELECT proposal_json,status,decision_event_id FROM proposals WHERE proposal_id=?",
            (proposal_id,),
        ).fetchone()
        if proposal is None:
            raise CognitiveIntegrityError("decision references missing proposal")
        if proposal["decision_event_id"] is not None:
            raise CognitiveIntegrityError("proposal has more than one decision")
        proposal_data = json.loads(proposal["proposal_json"])
        if payload.get("policy") != {"id": POLICY_ID, "version": POLICY_VERSION}:
            raise CognitiveIntegrityError("unknown decision policy provenance")
        if payload.get("proposal_event_id") != self._proposal_event_id(db, proposal_id):
            raise CognitiveIntegrityError("decision proposal-event reference mismatch")
        if payload.get("evidence_event_ids") != proposal_data["evidence_event_ids"]:
            raise CognitiveIntegrityError("decision evidence references mismatch")
        if not isinstance(payload.get("reason"), str) or not payload["reason"].strip():
            raise CognitiveIntegrityError("decision reason is missing")

        # A decision is replayable only when its provenance is present in the
        # preceding event history. Missing evidence is permitted solely for a
        # needs_more_evidence outcome; it can never support acceptance.
        for evidence_id in proposal_data["evidence_event_ids"]:
            evidence = db.execute(
                "SELECT event_type FROM events WHERE event_id=?", (evidence_id,)
            ).fetchone()
            if evidence is None:
                if outcome not in {"needs_more_evidence", "rejected"}:
                    raise CognitiveIntegrityError("decision references missing evidence")
                continue
            if evidence["event_type"] != OBSERVATION_EVENT and outcome != "rejected":
                raise CognitiveIntegrityError("decision references disallowed evidence type")

        evaluated_version = payload.get("evaluated_state_version")
        current_version = self._authoritative_state_version(
            db, exclude_event_id=event.event_id
        )
        projection_version = int(db.execute(
            "SELECT COUNT(*) FROM accepted_memories"
        ).fetchone()[0])
        if projection_version != current_version:
            raise CognitiveIntegrityError("accepted-memory projection is out of sync with event history")
        if (not isinstance(evaluated_version, int)
                or isinstance(evaluated_version, bool)
                or evaluated_version != current_version):
            raise CognitiveIntegrityError("decision evaluated against a stale state version")

        db.execute(
            "UPDATE proposals SET status=?, decision_event_id=? WHERE proposal_id=?",
            (outcome, event.event_id, proposal_id),
        )
        if outcome == "accepted":
            transition_id = _nonempty(payload.get("transition_id"), "transition_id")
            memory_id = _nonempty(payload.get("memory_id"), "memory_id")
            memory = {
                "memory_id": memory_id,
                "memory_kind": proposal_data["memory_kind"],
                "content": proposal_data["candidate_content"],
                "evidence_event_ids": proposal_data["evidence_event_ids"],
                "proposal_id": proposal_id,
                "proposal_event_id": payload["proposal_event_id"],
                "decision_event_id": event.event_id,
                "transition_id": transition_id,
                "created_at": event.occurred_at,
                "status": "accepted",
                "policy": payload["policy"],
            }
            db.execute(
                "INSERT INTO accepted_memories(memory_id,proposal_id,transition_id,memory_json) "
                "VALUES (?,?,?,?)",
                (memory_id, proposal_id, transition_id, _canonical(memory)),
            )
        elif payload.get("transition_id") is not None or payload.get("memory_id") is not None:
            raise CognitiveIntegrityError("non-accepted decision must not contain transition or memory")

    @staticmethod
    def _proposal_event_id(db: sqlite3.Connection, proposal_id: str) -> str:
        row = db.execute(
            "SELECT proposal_event_id FROM proposals WHERE proposal_id=?", (proposal_id,)
        ).fetchone()
        if row is None:
            raise CognitiveIntegrityError("proposal is missing")
        return str(row["proposal_event_id"])

    def evaluate_proposal(self, proposal_id: str) -> dict[str, Any]:
        """CSD-owned deterministic provenance evaluation; never invokes a model."""
        _nonempty(proposal_id, "proposal_id")
        with self._tx() as db:
            row = db.execute(
                "SELECT proposal_json,status,decision_event_id,proposal_event_id "
                "FROM proposals WHERE proposal_id=?", (proposal_id,)
            ).fetchone()
            if row is None:
                raise KeyError(proposal_id)
            if row["decision_event_id"] is not None:
                decision = db.execute(
                    "SELECT payload_ref FROM events WHERE event_id=?",
                    (row["decision_event_id"],),
                ).fetchone()
                payload = json.loads(db.execute(
                    "SELECT payload_json FROM payloads WHERE payload_ref=?",
                    (decision["payload_ref"],),
                ).fetchone()["payload_json"])
                return {"status": "already_decided", "decision": payload}

            proposal = json.loads(row["proposal_json"])
            reason = "proposal and evidence references passed deterministic provenance checks"
            outcome = "accepted"
            for evidence_id in proposal["evidence_event_ids"]:
                evidence_record = self.get_event(evidence_id)
                evidence = {
                    "event_type": evidence_record["event_type"],
                    "payload_ref": evidence_record["payload_ref"],
                }
                if evidence is None:
                    outcome = "needs_more_evidence"
                    reason = f"referenced evidence event is missing: {evidence_id}"
                    break
                if evidence["event_type"] != OBSERVATION_EVENT:
                    outcome = "rejected"
                    reason = f"evidence event is not an allowed observation: {evidence_id}"
                    break
                evidence_payload = json.loads(db.execute(
                    "SELECT payload_json FROM payloads WHERE payload_ref=?",
                    (evidence["payload_ref"],),
                ).fetchone()["payload_json"])
                self._validate_observation(evidence_payload)

            current_state_version = self._authoritative_state_version(db)
            projection_version = int(db.execute(
                "SELECT COUNT(*) FROM accepted_memories"
            ).fetchone()[0])
            if projection_version != current_state_version:
                raise CognitiveIntegrityError(
                    "accepted-memory projection is out of sync; run Recovery before evaluation"
                )
            based_on_version = int(proposal["based_on"]["state_version"])
            if outcome == "accepted" and based_on_version != current_state_version:
                outcome = "deferred"
                reason = (
                    f"stale proposal state_version={based_on_version}; "
                    f"current state_version={current_state_version}"
                )

            decision_number = int(db.execute(
                "SELECT COUNT(*) FROM events WHERE event_type=?",
                (DECISION_EVENT,),
            ).fetchone()[0]) + 1
            decision_event_id = f"csd-decision:{proposal_id}:{decision_number}"
            transition_id = f"csd-transition:{proposal_id}" if outcome == "accepted" else None
            memory_id = f"csd-memory:{proposal_id}" if outcome == "accepted" else None
            decision_payload = {
                "proposal_id": proposal_id,
                "proposal_event_id": row["proposal_event_id"],
                "outcome": outcome,
                "policy": {"id": POLICY_ID, "version": POLICY_VERSION},
                "evidence_event_ids": proposal["evidence_event_ids"],
                "reason": reason,
                "evaluated_state_version": current_state_version,
                "transition_id": transition_id,
                "memory_id": memory_id,
            }
            decision_event = CognitiveEvent(
                event_id=decision_event_id,
                occurred_at=datetime.now(timezone.utc).isoformat(),
                correlation_id=f"proposal:{proposal_id}",
                event_type=DECISION_EVENT,
                source=DECISION_SOURCE,
                payload=decision_payload,
            )
            payload_json = self._validate_event(decision_event, internal=True)
            appended = self._append_event_in_transaction(
                db, decision_event, payload_json, internal=True
            )
            return {
                "status": outcome,
                "decision_event_id": decision_event_id,
                "sequence": appended["sequence"],
                "reason": reason,
            }

    def get_event(self, event_id: str) -> dict[str, Any]:
        """Read one immutable event with its content-addressed payload."""
        _nonempty(event_id, "event_id")
        row = self._db.execute(
            "SELECT e.sequence,e.event_id,e.occurred_at,e.received_at,e.correlation_id,"
            "e.event_type,e.source,e.payload_ref,e.event_digest,p.payload_json "
            "FROM events e JOIN payloads p ON p.payload_ref=e.payload_ref "
            "WHERE e.event_id=?",
            (event_id,),
        ).fetchone()
        if row is None:
            raise KeyError(event_id)
        payload_json = row["payload_json"]
        if "sha256:" + _digest(payload_json) != row["payload_ref"]:
            raise CognitiveIntegrityError(f"payload digest failure: {event_id}")
        try:
            payload = json.loads(payload_json)
        except json.JSONDecodeError as exc:
            raise CognitiveIntegrityError(f"invalid event payload: {event_id}") from exc
        if not isinstance(payload, dict):
            raise CognitiveIntegrityError(f"event payload is not an object: {event_id}")
        event = CognitiveEvent(
            event_id=row["event_id"],
            occurred_at=row["occurred_at"],
            correlation_id=row["correlation_id"],
            event_type=row["event_type"],
            source=row["source"],
            payload=payload,
        )
        _timestamp(row["received_at"], "received_at")
        if self._event_digest(event, row["payload_ref"], row["received_at"]) != row["event_digest"]:
            raise CognitiveIntegrityError(f"event envelope digest failure: {event_id}")
        return {
            "sequence": int(row["sequence"]),
            "event_id": row["event_id"],
            "occurred_at": row["occurred_at"],
            "received_at": row["received_at"],
            "correlation_id": row["correlation_id"],
            "event_type": row["event_type"],
            "source": row["source"],
            "payload_ref": row["payload_ref"],
            "payload": payload,
        }

    def get_memories(self) -> list[dict[str, Any]]:
        rows = self._db.execute(
            "SELECT memory_json FROM accepted_memories ORDER BY rowid"
        ).fetchall()
        return [json.loads(row["memory_json"]) for row in rows]

    def get_proposal(self, proposal_id: str) -> dict[str, Any]:
        row = self._db.execute(
            "SELECT proposal_json,status,decision_event_id FROM proposals WHERE proposal_id=?",
            (proposal_id,),
        ).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        return {
            "proposal": json.loads(row["proposal_json"]),
            "status": row["status"],
            "decision_event_id": row["decision_event_id"],
        }

    def get_state_snapshot(self) -> dict[str, Any]:
        state_version = self._authoritative_state_version(self._db)
        accepted_memory_count = int(self._db.execute(
            "SELECT COUNT(*) FROM accepted_memories"
        ).fetchone()[0])
        return {
            "event_count": int(self._db.execute("SELECT COUNT(*) FROM events").fetchone()[0]),
            "state_version": state_version,
            "proposal_count": int(self._db.execute("SELECT COUNT(*) FROM proposals").fetchone()[0]),
            "accepted_memory_count": accepted_memory_count,
            "projection_consistent": accepted_memory_count == state_version,
        }

    def recover(self) -> dict[str, int]:
        """Validate the event log and rebuild projections; never evaluate proposals."""
        integrity = self._db.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise CognitiveIntegrityError(f"SQLite integrity_check failed: {integrity}")
        if self._db.execute("PRAGMA foreign_key_check").fetchall():
            raise CognitiveIntegrityError("SQLite foreign_key_check failed")

        rows = self._db.execute(
            "SELECT e.sequence,e.event_id,e.occurred_at,e.received_at,e.correlation_id,e.event_type,"
            "e.source,e.payload_ref,e.event_digest,p.payload_json "
            "FROM events e LEFT JOIN payloads p ON p.payload_ref=e.payload_ref "
            "ORDER BY e.sequence"
        ).fetchall()

        parsed: list[tuple[int, CognitiveEvent]] = []
        expected = 1
        for row in rows:
            if int(row["sequence"]) != expected:
                raise CognitiveIntegrityError("event sequence gap")
            expected += 1
            payload_json = row["payload_json"]
            if payload_json is None or "sha256:" + _digest(payload_json) != row["payload_ref"]:
                raise CognitiveIntegrityError(f"payload integrity failure: {row['event_id']}")
            try:
                payload = json.loads(payload_json)
            except json.JSONDecodeError as exc:
                raise CognitiveIntegrityError("invalid payload JSON") from exc
            if not isinstance(payload, dict):
                raise CognitiveIntegrityError("event payload must be an object")
            event = CognitiveEvent(
                event_id=row["event_id"],
                occurred_at=row["occurred_at"],
                correlation_id=row["correlation_id"],
                event_type=row["event_type"],
                source=row["source"],
                payload=payload,
            )
            _nonempty(event.event_id, "event_id")
            _nonempty(event.correlation_id, "correlation_id")
            _nonempty(event.event_type, "event_type")
            _nonempty(event.source, "source")
            _timestamp(event.occurred_at, "occurred_at")
            _timestamp(row["received_at"], "received_at")
            if self._event_digest(event, row["payload_ref"], row["received_at"]) != row["event_digest"]:
                raise CognitiveIntegrityError(f"event envelope digest failure: {event.event_id}")
            parsed.append((expected - 1, event))

        with self._tx() as db:
            db.execute("DELETE FROM accepted_memories")
            db.execute("DELETE FROM proposals")
            for sequence, event in parsed:
                internal = event.event_type == DECISION_EVENT and event.source == DECISION_SOURCE
                if event.event_type == DECISION_EVENT and not internal:
                    raise CognitiveIntegrityError("forged decision event in durable history")
                if event.event_type not in {OBSERVATION_EVENT, PROPOSAL_EVENT, DECISION_EVENT}:
                    raise CognitiveIntegrityError(f"unknown event type: {event.event_type}")
                self._apply_projection_event(db, event, sequence, internal=internal)

        return {
            "events": len(parsed),
            "proposals": int(self._db.execute("SELECT COUNT(*) FROM proposals").fetchone()[0]),
            "accepted_memories": int(self._db.execute(
                "SELECT COUNT(*) FROM accepted_memories"
            ).fetchone()[0]),
        }
