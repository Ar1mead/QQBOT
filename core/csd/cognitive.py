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

from .motivation import (
    CognitiveMotivationMixin,
    INTERACTION_EVENT,
    MOTIVATION_DECISION_EVENT,
    MOTIVATION_DECISION_SOURCE,
    MOTIVATION_PROPOSAL_EVENT,
)
from .goals import (
    CognitiveGoalMixin,
    CognitiveGoalLifecycleMixin,
    GOAL_BATCH_DECISION_EVENT,
    GOAL_BATCH_PROPOSAL_EVENT,
    GOAL_DECISION_SOURCE,
    GOAL_ACTIVATION_PROPOSAL_EVENT,
    GOAL_ACTIVATION_DECISION_EVENT,
    GOAL_PAUSE_RESUME_PROPOSAL_EVENT,
    GOAL_PAUSE_RESUME_DECISION_EVENT,
)


SCHEMA_VERSION = 5
OBSERVATION_EVENT = "experience.observation_recorded.v1"
PROPOSAL_EVENT = "cognition.memory_candidate_proposed.v1"
GROUNDED_PROPOSAL_EVENT = "cognition.grounded_memory_candidate_proposed.v1"
SEMANTIC_REVIEW_EVENT = "cognition.semantic_review_recorded.v1"
DECISION_EVENT = "cognition.memory_candidate_decided.v1"
DECISION_SOURCE = "csd.authority.v1"
POLICY_ID = "csd.memory-provenance-check"
GROUNDED_POLICY_ID = "csd.grounded-memory-text-evidence"
GROUNDED_POLICY_VERSION = "0.2"
POLICY_VERSION = "0.1"
SEMANTIC_REVIEW_CONTRACT_VERSION = "semantic-review.v1"


class CognitiveStoreError(Exception):
    """Base error for the cognitive-memory reference slice."""


class CognitiveIdempotencyConflict(CognitiveStoreError):
    """An event identity was reused with different immutable content."""


class ProposalIdentityConflict(CognitiveStoreError):
    """A proposal identity was reused with different immutable content."""


class SemanticReviewIdentityConflict(CognitiveStoreError):
    """A semantic review identity was reused with different immutable content."""


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


class CognitiveMemoryStore(CognitiveMotivationMixin, CognitiveGoalLifecycleMixin, CognitiveGoalMixin):
    """Single event stream with rebuildable proposal and accepted-memory views."""

    def _raise_cognitive_integrity(self, message: str) -> None:
        raise CognitiveIntegrityError(message)

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

        if version == 0:
            try:
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
    
            except Exception:
                # Match later migrations: never leave partial initial DDL open.
                if self._db.in_transaction:
                    self._db.rollback()
                raise
            version = 1

        if version == 1:
            try:
                self._db.executescript(
                    """
                    BEGIN IMMEDIATE;
                    CREATE TABLE motivation_proposals (
                        proposal_id TEXT PRIMARY KEY,
                        proposal_digest TEXT NOT NULL,
                        proposal_event_id TEXT NOT NULL,
                        proposal_json TEXT NOT NULL,
                        status TEXT NOT NULL CHECK(status IN ('pending','accepted','rejected','deferred','needs_more_evidence')),
                        decision_event_id TEXT
                    );
                    CREATE TABLE motivation_signal_versions (
                        signal_id TEXT NOT NULL,
                        signal_version INTEGER NOT NULL CHECK(signal_version > 0),
                        decision_event_id TEXT NOT NULL UNIQUE,
                        transition_id TEXT NOT NULL UNIQUE,
                        signal_json TEXT NOT NULL,
                        PRIMARY KEY(signal_id, signal_version)
                    );
                    CREATE TABLE motivation_signals (
                        signal_id TEXT PRIMARY KEY,
                        signal_version INTEGER NOT NULL CHECK(signal_version > 0),
                        decision_event_id TEXT NOT NULL,
                        transition_id TEXT NOT NULL UNIQUE,
                        signal_json TEXT NOT NULL
                    );
                    PRAGMA user_version = 2;
                    COMMIT;
                    """
                )
            except Exception:
                # sqlite3.executescript can leave its explicit transaction open
                # when a statement fails. Roll back partial DDL and user_version.
                if self._db.in_transaction:
                    self._db.rollback()
                raise
            version = 2

        if version == 2:
            try:
                self._db.executescript(
                    """
                    BEGIN IMMEDIATE;
                    CREATE TABLE goal_proposals (
                        proposal_id TEXT PRIMARY KEY,
                        proposal_digest TEXT NOT NULL,
                        proposal_event_id TEXT NOT NULL,
                        proposal_json TEXT NOT NULL,
                        status TEXT NOT NULL CHECK(status IN ('pending','accepted','rejected','deferred')),
                        decision_event_id TEXT
                    );
                    CREATE TABLE goal_versions (
                        goal_id TEXT NOT NULL,
                        goal_version INTEGER NOT NULL CHECK(goal_version > 0),
                        decision_event_id TEXT NOT NULL,
                        transition_id TEXT NOT NULL UNIQUE,
                        goal_json TEXT NOT NULL,
                        PRIMARY KEY(goal_id, goal_version)
                    );
                    CREATE TABLE goals (
                        goal_id TEXT PRIMARY KEY,
                        goal_version INTEGER NOT NULL CHECK(goal_version > 0),
                        decision_event_id TEXT NOT NULL,
                        transition_id TEXT NOT NULL UNIQUE,
                        goal_json TEXT NOT NULL
                    );
                    PRAGMA user_version = 3;
                    COMMIT;
                    """
                )
            except Exception:
                if self._db.in_transaction:
                    self._db.rollback()
                raise
            version = 3

        if version == 3:
            try:
                self._db.executescript(
                    """
                    BEGIN IMMEDIATE;
                    CREATE TABLE goal_activation_proposals (
                        proposal_id TEXT PRIMARY KEY,
                        proposal_digest TEXT NOT NULL,
                        proposal_event_id TEXT NOT NULL,
                        proposal_json TEXT NOT NULL,
                        status TEXT NOT NULL CHECK(status IN ('pending','accepted','rejected','deferred')),
                        decision_event_id TEXT
                    );
                    PRAGMA user_version = 4;
                    COMMIT;
                    """
                )
            except Exception:
                if self._db.in_transaction:
                    self._db.rollback()
                raise
            version = 4

        if version == 4:
            try:
                self._db.executescript(
                    """
                    BEGIN IMMEDIATE;
                    CREATE TABLE goal_pause_resume_proposals (
                        proposal_id TEXT PRIMARY KEY,
                        proposal_digest TEXT NOT NULL,
                        proposal_event_id TEXT NOT NULL,
                        proposal_json TEXT NOT NULL,
                        status TEXT NOT NULL CHECK(status IN ('pending','accepted','rejected','deferred')),
                        decision_event_id TEXT
                    );
                    PRAGMA user_version = 5;
                    COMMIT;
                    """
                )
            except Exception:
                if self._db.in_transaction:
                    self._db.rollback()
                raise
            version = 5

        if version != SCHEMA_VERSION:
            raise CognitiveIntegrityError(f"unsupported schema version: {version}")

    class _Tx:
        def __init__(self, db: sqlite3.Connection) -> None:
            self.db = db

        def __enter__(self) -> sqlite3.Connection:
            self.db.execute("BEGIN IMMEDIATE")
            return self.db

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
            if exc_type is not None:
                if self.db.in_transaction:
                    self.db.rollback()
                return False
            try:
                self.db.commit()
            except Exception:
                # SQLite may leave the transaction active when COMMIT itself fails
                # (for example, a deferred constraint or a transient lock error).
                if self.db.in_transaction:
                    self.db.rollback()
                raise
            return False

    class _ReadTx:
        def __init__(self, db: sqlite3.Connection) -> None:
            self.db = db

        def __enter__(self) -> sqlite3.Connection:
            self.db.execute("BEGIN")
            return self.db

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
            if exc_type is not None:
                if self.db.in_transaction:
                    self.db.rollback()
                return False
            try:
                self.db.commit()
            except Exception:
                if self.db.in_transaction:
                    self.db.rollback()
                raise
            return False

    def _tx(self) -> "CognitiveMemoryStore._Tx":
        return self._Tx(self._db)

    def _read_tx(self) -> "CognitiveMemoryStore._ReadTx":
        return self._ReadTx(self._db)

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
        if not internal and (
            event.event_id.startswith("csd-decision:")
            or event.event_id.startswith("csd-motivation-decision:")
            or event.event_id.startswith("csd-goal-decision:")
            or event.event_id.startswith("csd-goal-activation-decision:")
            or event.event_id.startswith("csd-goal-pause-resume-decision:")
        ):
            raise ValueError("event_id uses a namespace reserved for CSD decisions")
        _nonempty(event.correlation_id, "correlation_id")
        _nonempty(event.event_type, "event_type")
        _nonempty(event.source, "source")
        _timestamp(event.occurred_at, "occurred_at")
        if not isinstance(event.payload, Mapping):
            raise ValueError("payload must be an object")
        if event.event_type in {DECISION_EVENT, MOTIVATION_DECISION_EVENT, GOAL_BATCH_DECISION_EVENT, GOAL_ACTIVATION_DECISION_EVENT, GOAL_PAUSE_RESUME_DECISION_EVENT} and not internal:
            raise ValueError("CSD decision events are reserved for the internal authority path")
        if event.event_type not in {
            OBSERVATION_EVENT, PROPOSAL_EVENT, GROUNDED_PROPOSAL_EVENT,
            SEMANTIC_REVIEW_EVENT, DECISION_EVENT,
            INTERACTION_EVENT, MOTIVATION_PROPOSAL_EVENT, MOTIVATION_DECISION_EVENT,
            GOAL_BATCH_PROPOSAL_EVENT, GOAL_BATCH_DECISION_EVENT,
            GOAL_ACTIVATION_PROPOSAL_EVENT, GOAL_ACTIVATION_DECISION_EVENT,
            GOAL_PAUSE_RESUME_PROPOSAL_EVENT, GOAL_PAUSE_RESUME_DECISION_EVENT,
        }:
            raise ValueError(f"unsupported event type: {event.event_type}")
        if event.event_type in {DECISION_EVENT, MOTIVATION_DECISION_EVENT} and event.source != DECISION_SOURCE:
            raise ValueError("decision event source must identify CSD authority")
        if event.event_type == MOTIVATION_DECISION_EVENT and event.source != MOTIVATION_DECISION_SOURCE:
            raise ValueError("motivation decision event source must identify CSD authority")
        if event.event_type in {GOAL_BATCH_DECISION_EVENT, GOAL_ACTIVATION_DECISION_EVENT, GOAL_PAUSE_RESUME_DECISION_EVENT} and event.source != GOAL_DECISION_SOURCE:
            raise ValueError("goal decision event source must identify CSD authority")
        if event.event_type == SEMANTIC_REVIEW_EVENT:
            reviewer = event.payload.get("reviewer")
            if not isinstance(reviewer, Mapping) or not isinstance(reviewer.get("component"), str):
                raise ValueError("semantic review must include reviewer.component")
            if event.source != f"semantic-review.pipeline:{reviewer['component']}":
                raise ValueError("semantic review source/reviewer mismatch")
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

    def _validate_proposal_snapshot_chronology(
        self,
        db: sqlite3.Connection,
        event: CognitiveEvent,
        sequence: int,
        *,
        replay: bool = False,
    ) -> None:
        proposal_types = {
            PROPOSAL_EVENT, GROUNDED_PROPOSAL_EVENT, MOTIVATION_PROPOSAL_EVENT,
            GOAL_BATCH_PROPOSAL_EVENT, GOAL_ACTIVATION_PROPOSAL_EVENT,
            GOAL_PAUSE_RESUME_PROPOSAL_EVENT,
        }
        if event.event_type not in proposal_types:
            return
        based_on = event.payload.get("based_on")
        if not isinstance(based_on, Mapping) or set(based_on) != {"state_version"}:
            message = "proposal based_on must contain exactly state_version"
            if replay:
                raise CognitiveIntegrityError(message)
            raise ValueError(message)
        claimed = based_on.get("state_version")
        if not isinstance(claimed, int) or isinstance(claimed, bool) or claimed < 0:
            message = "proposal based_on.state_version must be a non-negative integer"
            if replay:
                raise CognitiveIntegrityError(message)
            raise ValueError(message)
        state_at_append = self._authoritative_state_version(
            db, through_sequence=sequence - 1
        )
        if claimed > state_at_append:
            message = (
                f"proposal claims future state_version={claimed}; "
                f"only {state_at_append} existed when its event was appended"
            )
            if replay:
                raise CognitiveIntegrityError(message)
            raise ValueError(message)

    def _validate_decision_event_history(
        self,
        db: sqlite3.Connection,
        event: CognitiveEvent,
        *,
        sequence: int,
    ) -> None:
        """Validate decision provenance against the immutable earlier event log."""
        proposal_families = {
            DECISION_EVENT: (PROPOSAL_EVENT, GROUNDED_PROPOSAL_EVENT),
            MOTIVATION_DECISION_EVENT: (MOTIVATION_PROPOSAL_EVENT,),
            GOAL_BATCH_DECISION_EVENT: (GOAL_BATCH_PROPOSAL_EVENT,),
            GOAL_ACTIVATION_DECISION_EVENT: (GOAL_ACTIVATION_PROPOSAL_EVENT,),
            GOAL_PAUSE_RESUME_DECISION_EVENT: (GOAL_PAUSE_RESUME_PROPOSAL_EVENT,),
        }
        expected_types = proposal_families.get(event.event_type)
        if expected_types is None:
            raise CognitiveIntegrityError("unknown durable decision family")

        proposal_id = _nonempty(
            event.payload.get("proposal_id"), "decision.proposal_id"
        )
        proposal_event_id = _nonempty(
            event.payload.get("proposal_event_id"), "decision.proposal_event_id"
        )
        evaluated_version = event.payload.get("evaluated_state_version")
        if (
            not isinstance(evaluated_version, int)
            or isinstance(evaluated_version, bool)
            or evaluated_version < 0
        ):
            raise CognitiveIntegrityError(
                "decision evaluated_state_version must be a non-negative integer"
            )

        authoritative_version = self._authoritative_state_version(
            db, through_sequence=sequence - 1
        )
        if evaluated_version != authoritative_version:
            raise CognitiveIntegrityError(
                "decision evaluated_state_version does not match authoritative history"
            )

        placeholders = ",".join("?" for _ in expected_types)
        params: list[Any] = [*expected_types, sequence, proposal_id]
        matching_proposals = db.execute(
            "SELECT e.event_id,e.sequence FROM events e "
            "JOIN payloads p ON p.payload_ref=e.payload_ref "
            f"WHERE e.event_type IN ({placeholders}) AND e.sequence<? "
            "AND CASE WHEN json_valid(p.payload_json) "
            "THEN json_extract(p.payload_json,'$.proposal_id') END=? "
            "ORDER BY e.sequence",
            params,
        ).fetchall()
        if (
            len(matching_proposals) != 1
            or matching_proposals[0]["event_id"] != proposal_event_id
        ):
            raise CognitiveIntegrityError(
                "decision proposal-event reference is missing, ambiguous, or mismatched"
            )

        proposal_sequence = int(matching_proposals[0]["sequence"])
        if proposal_sequence >= sequence:
            raise CognitiveIntegrityError(
                "decision proposal-event reference must point to an earlier event"
            )
        proposal_event = self.get_event(
            proposal_event_id, _validate_decision_context=False
        )
        if (
            proposal_event["event_type"] not in expected_types
            or proposal_event["payload"].get("proposal_id") != proposal_id
            or int(proposal_event["sequence"]) != proposal_sequence
        ):
            raise CognitiveIntegrityError(
                "decision proposal-event reference does not identify its historical proposal"
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
            # Idempotent delivery must not turn a corrupted prior envelope or
            # event-specific schema into a successful duplicate acknowledgement.
            stored_event = self.get_event(event.event_id)
            self._validate_event_local_shape(
                db, stored_event, sequence=int(prior["sequence"])
            )
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

        if event.event_type in {PROPOSAL_EVENT, GROUNDED_PROPOSAL_EVENT}:
            proposal_id = _nonempty(event.payload.get("proposal_id"), "proposal_id")
            proposal_digest = _digest(payload_json)
            existing = db.execute(
                "SELECT proposal_digest FROM proposals WHERE proposal_id=?",
                (proposal_id,),
            ).fetchone()
            if existing is not None and existing["proposal_digest"] != proposal_digest:
                raise ProposalIdentityConflict(proposal_id)

        if event.event_type == MOTIVATION_PROPOSAL_EVENT:
            proposal_id = _nonempty(event.payload.get("proposal_id"), "proposal_id")
            proposal_digest = _digest(payload_json)
            existing = db.execute(
                "SELECT proposal_digest FROM motivation_proposals WHERE proposal_id=?",
                (proposal_id,),
            ).fetchone()
            if existing is not None and existing["proposal_digest"] != proposal_digest:
                raise CognitiveIdempotencyConflict(
                    f"motivation proposal identity conflict: {proposal_id}"
                )

        if event.event_type == SEMANTIC_REVIEW_EVENT:
            review_id = _nonempty(event.payload.get("review_id"), "review_id")
            prior_reviews = db.execute(
                "SELECT event_id FROM events "
                "WHERE event_type=? ORDER BY sequence",
                (SEMANTIC_REVIEW_EVENT,),
            ).fetchall()
            for prior_review in prior_reviews:
                # Do not acknowledge a duplicate review from raw projection data:
                # validate the authoritative event payload and envelope first.
                stored_event = self.get_event(prior_review["event_id"])
                stored_payload = stored_event["payload"]
                prior_event = CognitiveEvent(
                    event_id=stored_event["event_id"],
                    occurred_at=stored_event["occurred_at"],
                    correlation_id=stored_event["correlation_id"],
                    event_type=stored_event["event_type"],
                    source=stored_event["source"],
                    payload=stored_payload,
                )
                try:
                    self._validate_semantic_review_shape(prior_event)
                except (TypeError, ValueError, KeyError, IndexError, RecursionError, OverflowError) as exc:
                    raise CognitiveIntegrityError(
                        f"invalid prior semantic review event: {prior_event.event_id}"
                    ) from exc
                if stored_payload.get("review_id") == review_id:
                    if stored_payload != dict(event.payload):
                        raise SemanticReviewIdentityConflict(review_id)
                    return {
                        "status": "duplicate_review",
                        "review_id": review_id,
                        "event_id": stored_event["event_id"],
                        "sequence": int(stored_event["sequence"]),
                        "received_at": stored_event["received_at"],
                    }

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
        self._validate_proposal_snapshot_chronology(db, event, sequence)
        self._apply_projection_event(db, event, sequence, internal=internal)
        return {
            "status": "accepted",
            "event_id": event.event_id,
            "sequence": sequence,
            "received_at": received_at,
            "payload_ref": payload_ref,
        }

    def _validate_event_local_shape(
        self,
        db: sqlite3.Connection,
        stored_event: Mapping[str, Any],
        *,
        sequence: int,
    ) -> None:
        """Recheck an immutable event's local and historical contract.

        Used by direct reads, duplicate acknowledgement, and Recovery. Contextual
        validation is bounded by the event's original sequence; later proposal or
        goal lifecycle state must not invalidate a legitimate historical event.
        """
        event = CognitiveEvent(
            event_id=stored_event["event_id"],
            occurred_at=stored_event["occurred_at"],
            correlation_id=stored_event["correlation_id"],
            event_type=stored_event["event_type"],
            source=stored_event["source"],
            payload=stored_event["payload"],
        )
        try:
            if event.event_type == OBSERVATION_EVENT:
                self._validate_observation(event.payload)
            elif event.event_type == PROPOSAL_EVENT:
                self._validate_proposal(event.payload)
            elif event.event_type == GROUNDED_PROPOSAL_EVENT:
                self._validate_grounded_proposal(event.payload)
            elif event.event_type == SEMANTIC_REVIEW_EVENT:
                self._validate_semantic_review_shape(event)
                self._validate_semantic_review_event_history(
                    db, event, sequence=sequence
                )
            elif event.event_type == INTERACTION_EVENT:
                self._validate_interaction_event(db, event, current_sequence=sequence)
            elif event.event_type == MOTIVATION_PROPOSAL_EVENT:
                self._validate_motivation_proposal(
                    db, event, current_sequence=sequence
                )
            elif event.event_type == GOAL_BATCH_PROPOSAL_EVENT:
                self._validate_goal_batch_proposal(event)
            elif event.event_type == GOAL_ACTIVATION_PROPOSAL_EVENT:
                from .goals import _validate_goal_activation_proposal
                _validate_goal_activation_proposal(event)
            elif event.event_type == GOAL_PAUSE_RESUME_PROPOSAL_EVENT:
                from .goals import _validate_goal_pause_resume_proposal
                _validate_goal_pause_resume_proposal(event)
            elif event.event_type in {
                DECISION_EVENT, MOTIVATION_DECISION_EVENT,
                GOAL_BATCH_DECISION_EVENT, GOAL_ACTIVATION_DECISION_EVENT,
                GOAL_PAUSE_RESUME_DECISION_EVENT,
            }:
                proposal_id = _nonempty(event.payload.get("proposal_id"), "decision.proposal_id")
                outcome = _nonempty(event.payload.get("outcome"), "decision.outcome")
                if outcome not in {"accepted", "rejected", "deferred", "needs_more_evidence"}:
                    raise ValueError("unsupported durable decision outcome")
                expected_identity = {
                    DECISION_EVENT: (
                        DECISION_SOURCE,
                        f"csd-decision:{proposal_id}:"
                        f"{int(db.execute('SELECT COUNT(*) FROM events WHERE event_type=? AND sequence<=?', (DECISION_EVENT, sequence)).fetchone()[0])}",
                        f"proposal:{proposal_id}",
                    ),
                    MOTIVATION_DECISION_EVENT: (
                        MOTIVATION_DECISION_SOURCE,
                        f"csd-motivation-decision:{proposal_id}:"
                        f"{int(db.execute('SELECT COUNT(*) FROM events WHERE event_type=? AND sequence<=?', (MOTIVATION_DECISION_EVENT, sequence)).fetchone()[0])}",
                        f"motivation-proposal:{proposal_id}",
                    ),
                    GOAL_BATCH_DECISION_EVENT: (
                        GOAL_DECISION_SOURCE,
                        f"csd-goal-decision:{proposal_id}",
                        f"goal-proposal:{proposal_id}",
                    ),
                    GOAL_ACTIVATION_DECISION_EVENT: (
                        GOAL_DECISION_SOURCE,
                        f"csd-goal-activation-decision:{proposal_id}",
                        f"goal-activation-proposal:{proposal_id}",
                    ),
                    GOAL_PAUSE_RESUME_DECISION_EVENT: (
                        GOAL_DECISION_SOURCE,
                        f"csd-goal-pause-resume-decision:{proposal_id}",
                        f"goal-pause-resume-proposal:{proposal_id}",
                    ),
                }[event.event_type]
                decision_fields = {
                    DECISION_EVENT: {
                        "proposal_id", "proposal_event_id", "outcome", "policy",
                        "evidence_event_ids", "semantic_review_event_ids",
                        "semantic_review_status", "semantic_review_applied", "reason",
                        "evaluated_state_version", "transition_id", "memory_id",
                    },
                    MOTIVATION_DECISION_EVENT: {
                        "proposal_id", "proposal_event_id", "outcome", "policy",
                        "evidence_event_ids", "signal", "transition_id", "reason",
                        "evaluated_state_version",
                    },
                    GOAL_BATCH_DECISION_EVENT: {
                        "proposal_id", "proposal_event_id", "outcome", "policy",
                        "evaluated_state_version", "transitions", "reason",
                    },
                    GOAL_ACTIVATION_DECISION_EVENT: {
                        "proposal_id", "proposal_event_id", "outcome", "policy",
                        "evaluated_state_version", "goal_id", "expected_goal_version",
                        "transition", "reason",
                    },
                    GOAL_PAUSE_RESUME_DECISION_EVENT: {
                        "proposal_id", "proposal_event_id", "outcome", "policy",
                        "evaluated_state_version", "goal_id", "expected_goal_version",
                        "operation", "transition", "reason",
                    },
                }[event.event_type]
                if set(event.payload) != decision_fields:
                    raise ValueError("durable decision contains missing or unsupported fields")
                if (
                    event.source != expected_identity[0]
                    or event.event_id != expected_identity[1]
                    or event.correlation_id != expected_identity[2]
                ):
                    raise ValueError("durable decision authority or identity mismatch")
            else:
                raise CognitiveIntegrityError(
                    f"unsupported durable event type: {event.event_type}"
                )

            # Proposal snapshots are historical claims. Validate them against
            # the authoritative state that existed immediately before this
            # event, not against today's later state.
            self._validate_proposal_snapshot_chronology(
                db, event, sequence, replay=True
            )
        except CognitiveIntegrityError:
            raise
        except (TypeError, ValueError, KeyError, IndexError, RecursionError, OverflowError) as exc:
            raise CognitiveIntegrityError(
                f"invalid durable event schema: {event.event_id}"
            ) from exc

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

    @staticmethod
    def _validate_grounded_proposal(payload: Mapping[str, Any]) -> None:
        allowed = {"proposal_id", "memory_kind", "claims", "origin", "based_on", "operation"}
        if set(payload) != allowed:
            raise ValueError("grounded proposal contains missing or unsupported fields")
        _nonempty(payload.get("proposal_id"), "proposal_id")
        _nonempty(payload.get("memory_kind"), "memory_kind")
        if payload.get("operation") != "create":
            raise ValueError("grounded memory v2 only supports operation=create")

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

        claims = payload.get("claims")
        if not isinstance(claims, list) or not claims:
            raise ValueError("claims must be a non-empty list")
        claim_ids: set[str] = set()
        source_event_ids: set[str] = set()
        for index, claim in enumerate(claims):
            if not isinstance(claim, Mapping):
                raise ValueError(f"claims[{index}] must be an object")
            claim_id = _nonempty(claim.get("claim_id"), f"claims[{index}].claim_id")
            if claim_id in claim_ids:
                raise ValueError(f"duplicate claim_id: {claim_id}")
            claim_ids.add(claim_id)
            _nonempty(claim.get("text"), f"claims[{index}].text")
            epistemic_type = claim.get("epistemic_type")

            if epistemic_type == "source_assertion":
                if set(claim) != {"claim_id", "text", "epistemic_type", "evidence", "uncertainty"}:
                    raise ValueError("source_assertion contains missing or unsupported fields")
                evidence_items = claim.get("evidence")
                if not isinstance(evidence_items, list) or len(evidence_items) != 1:
                    raise ValueError("v2 source_assertion requires exactly one text evidence span")
                uncertainty = claim.get("uncertainty")
                if not isinstance(uncertainty, Mapping) or set(uncertainty) != {"label", "confidence"}:
                    raise ValueError("source_assertion uncertainty schema is invalid")
                if uncertainty.get("label") != "directly_quoted" or uncertainty.get("confidence") is not None:
                    raise ValueError("source_assertion must use directly_quoted with null confidence")
                for evidence_index, evidence in enumerate(evidence_items):
                    if not isinstance(evidence, Mapping) or set(evidence) != {"event_id", "locator", "quoted_text"}:
                        raise ValueError(f"claims[{index}].evidence[{evidence_index}] schema is invalid")
                    event_id = _nonempty(evidence.get("event_id"), "evidence.event_id")
                    source_event_ids.add(event_id)
                    _nonempty(evidence.get("quoted_text"), "evidence.quoted_text")
                    locator = evidence.get("locator")
                    if not isinstance(locator, Mapping) or set(locator) != {"kind", "unit", "start", "end"}:
                        raise ValueError("text locator schema is invalid")
                    if locator.get("kind") != "text_range" or locator.get("unit") != "unicode_codepoint":
                        raise ValueError("v2 supports only unicode_codepoint text_range locators")
                    start = locator.get("start")
                    end = locator.get("end")
                    if (not isinstance(start, int) or isinstance(start, bool)
                            or not isinstance(end, int) or isinstance(end, bool)):
                        raise ValueError("text locator offsets must be integers")
                    if start < 0 or end < 0 or start >= end:
                        raise ValueError("text locator offsets must satisfy 0 <= start < end")
            elif epistemic_type == "inference":
                if set(claim) != {
                    "claim_id", "text", "epistemic_type", "derived_from_claim_ids",
                    "reasoning_summary", "uncertainty",
                }:
                    raise ValueError("inference contains missing or unsupported fields")
                refs = claim.get("derived_from_claim_ids")
                if not isinstance(refs, list) or not refs or any(
                    not isinstance(item, str) or not item.strip() for item in refs
                ):
                    raise ValueError("derived_from_claim_ids must be a non-empty string list")
                if len(set(refs)) != len(refs):
                    raise ValueError("derived_from_claim_ids must not contain duplicates")
                _nonempty(claim.get("reasoning_summary"), "reasoning_summary")
                uncertainty = claim.get("uncertainty")
                if not isinstance(uncertainty, Mapping) or set(uncertainty) - {"label", "confidence"}:
                    raise ValueError("inference uncertainty schema is invalid")
                _nonempty(uncertainty.get("label"), "inference uncertainty.label")
                confidence = uncertainty.get("confidence")
                if confidence is not None and (
                    not isinstance(confidence, (int, float))
                    or isinstance(confidence, bool)
                    or not 0.0 <= float(confidence) <= 1.0
                ):
                    raise ValueError("inference confidence must be null or between 0 and 1")
            else:
                raise ValueError(f"unsupported epistemic_type: {epistemic_type!r}")

        if not source_event_ids:
            raise ValueError("grounded proposal requires at least one source_assertion")
        if len(source_event_ids) != 1:
            raise ValueError("grounded memory v2 currently supports exactly one observation event")

    @staticmethod
    def _grounded_evidence_event_ids(payload: Mapping[str, Any]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for claim in payload["claims"]:
            if claim["epistemic_type"] != "source_assertion":
                continue
            for evidence in claim["evidence"]:
                event_id = evidence["event_id"]
                if event_id not in seen:
                    seen.add(event_id)
                    result.append(event_id)
        return result

    def _evaluate_grounded_claims(
        self, payload: Mapping[str, Any]
    ) -> tuple[str, str]:
        """Validate exact source spans and the restricted inference graph."""
        self._validate_grounded_proposal(payload)
        claim_by_id = {claim["claim_id"]: claim for claim in payload["claims"]}

        for claim in payload["claims"]:
            if claim["epistemic_type"] == "source_assertion":
                for evidence in claim["evidence"]:
                    try:
                        source_event = self.get_event(evidence["event_id"])
                    except KeyError:
                        return "needs_more_evidence", (
                            f"referenced observation is unavailable: {evidence['event_id']}"
                        )
                    if source_event["event_type"] != OBSERVATION_EVENT:
                        return "rejected", (
                            f"evidence is not an observation event: {evidence['event_id']}"
                        )
                    self._validate_observation(source_event["payload"])
                    if source_event["payload"]["coverage"]["modality"] != "text":
                        return "rejected", (
                            f"grounded memory v2 requires text evidence, got modality "
                            f"{source_event['payload']['coverage']['modality']!r}"
                        )
                    source_text = source_event["payload"]["content"]
                    locator = evidence["locator"]
                    start, end = locator["start"], locator["end"]
                    if claim["text"] != evidence["quoted_text"]:
                        return "rejected", (
                            f"source_assertion text must equal its quoted span for claim {claim['claim_id']}"
                        )
                    if end > len(source_text):
                        return "rejected", (
                            f"text locator is out of bounds for claim {claim['claim_id']}"
                        )
                    if source_text[start:end] != evidence["quoted_text"]:
                        return "rejected", (
                            f"quoted text does not match source span for claim {claim['claim_id']}"
                        )

            elif claim["epistemic_type"] == "inference":
                for source_claim_id in claim["derived_from_claim_ids"]:
                    source_claim = claim_by_id.get(source_claim_id)
                    if source_claim is None:
                        return "rejected", (
                            f"inference references missing claim: {source_claim_id}"
                        )
                    if source_claim["epistemic_type"] != "source_assertion":
                        return "rejected", (
                            f"inference may derive only from source_assertion claims: {source_claim_id}"
                        )

        return "accepted", (
            "all source spans match persisted observation text and inference references "
            "resolve to source_assertion claims"
        )

    def _semantic_review_summary(
        self,
        db: sqlite3.Connection,
        proposal_id: str,
        proposal: Mapping[str, Any],
        *,
        before_sequence: int | None = None,
    ) -> dict[str, Any]:
        """Summarize immutable review evidence; never makes a state decision."""
        inference_claims = [
            claim for claim in proposal.get("claims", [])
            if claim.get("epistemic_type") == "inference"
        ]
        if not inference_claims:
            return {
                "status": "not_applicable",
                "reason": "proposal contains no inference claims",
                "review_event_ids": [],
                "reviews_by_claim": {},
            }

        query = (
            "SELECT e.sequence,e.event_id FROM events e "
            "JOIN payloads p ON p.payload_ref=e.payload_ref "
            "WHERE e.event_type=?"
        )
        params: list[Any] = [SEMANTIC_REVIEW_EVENT]
        if before_sequence is not None:
            query += " AND e.sequence<?"
            params.append(before_sequence)
        query += " ORDER BY e.sequence"
        rows = db.execute(query, params).fetchall()

        expected_claims = {claim["claim_id"]: claim for claim in inference_claims}
        reviews_by_claim: dict[str, list[dict[str, Any]]] = {
            claim_id: [] for claim_id in expected_claims
        }
        for row in rows:
            review_event = self.get_event(row["event_id"])
            review = review_event["payload"]
            if review.get("proposal_id") != proposal_id:
                continue
            claim_id = review.get("claim_id")
            if claim_id not in expected_claims:
                raise CognitiveIntegrityError(
                    "semantic review history references a non-inference claim"
                )
            claim = expected_claims[claim_id]
            if review.get("proposal_digest") != "sha256:" + _digest(_canonical(dict(proposal))):
                raise CognitiveIntegrityError("semantic review proposal digest is stale")
            if review.get("claim_digest") != "sha256:" + _digest(_canonical(claim)):
                raise CognitiveIntegrityError("semantic review claim digest is stale")
            reviews_by_claim[claim_id].append({
                "review_event_id": review_event["event_id"],
                "sequence": review_event["sequence"],
                "review_id": review["review_id"],
                "outcome": review["outcome"],
                "reviewer": review["reviewer"],
                "reasoning_summary": review["reasoning_summary"],
            })

        all_review_ids: list[str] = []
        missing_claims: list[str] = []
        conflicting_claims: list[str] = []
        uncertain_claims: list[str] = []
        unsupported_claims: list[str] = []
        insufficient_claims: list[str] = []

        for claim_id, reviews in reviews_by_claim.items():
            if not reviews:
                missing_claims.append(claim_id)
                continue
            all_review_ids.extend(item["review_event_id"] for item in reviews)
            outcomes = {item["outcome"] for item in reviews}
            if len(outcomes) > 1:
                conflicting_claims.append(claim_id)
            elif "unsupported" in outcomes:
                unsupported_claims.append(claim_id)
            elif "insufficient_context" in outcomes:
                insufficient_claims.append(claim_id)
            elif "uncertain" in outcomes:
                uncertain_claims.append(claim_id)

        if unsupported_claims:
            status = "unsupported"
            reason = "one or more inference claims were reviewed as unsupported"
        elif missing_claims:
            status = "awaiting_review"
            reason = "one or more inference claims have no semantic review"
        elif insufficient_claims:
            status = "insufficient_context"
            reason = "one or more inference claims need additional context"
        elif conflicting_claims:
            status = "conflicting"
            reason = "reviewers returned conflicting outcomes for one or more inference claims"
        elif uncertain_claims:
            status = "uncertain"
            reason = "one or more inference claims remain uncertain"
        else:
            status = "supported"
            reason = "all inference claims have non-conflicting supported reviews"

        return {
            "status": status,
            "reason": reason,
            "review_event_ids": all_review_ids,
            "reviews_by_claim": reviews_by_claim,
            "missing_claim_ids": missing_claims,
        }

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
        if event.event_type in {PROPOSAL_EVENT, GROUNDED_PROPOSAL_EVENT}:
            if event.event_type == PROPOSAL_EVENT:
                self._validate_proposal(event.payload)
            else:
                self._validate_grounded_proposal(event.payload)
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
        if event.event_type == SEMANTIC_REVIEW_EVENT:
            self._validate_semantic_review_event(db, event, current_sequence=sequence)
            return
        if event.event_type == DECISION_EVENT:
            if not internal or event.source != DECISION_SOURCE:
                raise CognitiveIntegrityError("non-authoritative decision event")
            self._apply_decision(db, event)
            return
        if event.event_type in {
            INTERACTION_EVENT, MOTIVATION_PROPOSAL_EVENT, MOTIVATION_DECISION_EVENT,
        }:
            self._apply_motivation_projection_event(
                db, event, sequence, internal=internal
            )
            return
        if event.event_type in {
            GOAL_BATCH_PROPOSAL_EVENT, GOAL_BATCH_DECISION_EVENT,
            GOAL_ACTIVATION_PROPOSAL_EVENT, GOAL_ACTIVATION_DECISION_EVENT,
            GOAL_PAUSE_RESUME_PROPOSAL_EVENT, GOAL_PAUSE_RESUME_DECISION_EVENT,
        }:
            self._apply_goal_projection_event(db, event, internal=internal)
            return
        raise CognitiveIntegrityError(f"unhandled event type at sequence {sequence}")

    def _authoritative_state_version(
        self, db: sqlite3.Connection, *, through_sequence: int | None = None
    ) -> int:
        query = (
            "SELECT e.event_id FROM events e "
            "WHERE e.event_type IN (?,?,?,?,?)"
        )
        params: list[Any] = [DECISION_EVENT, MOTIVATION_DECISION_EVENT, GOAL_BATCH_DECISION_EVENT, GOAL_ACTIVATION_DECISION_EVENT, GOAL_PAUSE_RESUME_DECISION_EVENT]
        if through_sequence is not None:
            if not isinstance(through_sequence, int) or isinstance(through_sequence, bool):
                raise ValueError("through_sequence must be an integer or None")
            query += " AND e.sequence<=?"
            params.append(through_sequence)
        query += " ORDER BY e.sequence"
        version = 0
        for row in db.execute(query, params).fetchall():
            # State-version reads must not trust raw decision payload JSON:
            # verify its content and envelope digests before counting it.
            decision_event = self.get_event(
                row["event_id"], _validate_decision_context=False
            )
            decision = decision_event["payload"]
            outcome = decision.get("outcome")
            if outcome not in {"accepted", "rejected", "deferred", "needs_more_evidence"}:
                raise CognitiveIntegrityError("invalid durable decision outcome")
            if outcome == "accepted":
                version += 1
        return version

    def _apply_decision(self, db: sqlite3.Connection, event: CognitiveEvent) -> None:
        payload = event.payload
        allowed_payload_fields = {
            "proposal_id", "proposal_event_id", "outcome", "policy",
            "evidence_event_ids", "semantic_review_event_ids",
            "semantic_review_status", "semantic_review_applied", "reason",
            "evaluated_state_version", "transition_id", "memory_id",
        }
        if set(payload) != allowed_payload_fields:
            raise CognitiveIntegrityError(
                "memory decision contains missing or unsupported fields"
            )
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
        proposal_event_type = self._proposal_event_type(db, proposal_id)
        grounded = proposal_event_type == GROUNDED_PROPOSAL_EVENT
        expected_policy_id = GROUNDED_POLICY_ID if grounded else POLICY_ID
        policy = payload.get("policy")
        allowed_versions = (
            {POLICY_VERSION, GROUNDED_POLICY_VERSION}
            if grounded else {POLICY_VERSION}
        )
        if (
            not isinstance(policy, Mapping)
            or policy.get("id") != expected_policy_id
            or policy.get("version") not in allowed_versions
        ):
            raise CognitiveIntegrityError("unknown decision policy provenance")
        grounded_review_policy = grounded and policy.get("version") == GROUNDED_POLICY_VERSION
        if payload.get("proposal_event_id") != self._proposal_event_id(db, proposal_id):
            raise CognitiveIntegrityError("decision proposal-event reference mismatch")
        expected_evidence_ids = (
            self._grounded_evidence_event_ids(proposal_data)
            if grounded else proposal_data["evidence_event_ids"]
        )
        if payload.get("evidence_event_ids") != expected_evidence_ids:
            raise CognitiveIntegrityError("decision evidence references mismatch")
        if not isinstance(payload.get("reason"), str) or not payload["reason"].strip():
            raise CognitiveIntegrityError("decision reason is missing")

        # A decision is replayable only when its provenance is present in the
        # preceding event history. Missing evidence is permitted solely for a
        # needs_more_evidence outcome; it can never support acceptance.
        for evidence_id in expected_evidence_ids:
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
        event_sequence_row = db.execute(
            "SELECT sequence FROM events WHERE event_id=?", (event.event_id,)
        ).fetchone()
        if event_sequence_row is None:
            raise CognitiveIntegrityError("decision event is missing from durable history")
        event_sequence = int(event_sequence_row["sequence"])
        decision_number = int(db.execute(
            "SELECT COUNT(*) FROM events WHERE event_type=? AND sequence<?",
            (DECISION_EVENT, event_sequence),
        ).fetchone()[0]) + 1
        if (
            event.event_id != f"csd-decision:{proposal_id}:{decision_number}"
            or event.correlation_id != f"proposal:{proposal_id}"
        ):
            raise CognitiveIntegrityError("decision event identity or correlation_id mismatch")
        current_version = self._authoritative_state_version(
            db, through_sequence=event_sequence - 1
        )
        projection_version = self._accepted_transition_count(
            db, {DECISION_EVENT}, through_sequence=event_sequence - 1
        )
        projected_memories = int(db.execute(
            "SELECT COUNT(*) FROM accepted_memories"
        ).fetchone()[0])
        if projected_memories != projection_version:
            raise CognitiveIntegrityError("accepted-memory projection is out of sync with event history")
        if (not isinstance(evaluated_version, int)
                or isinstance(evaluated_version, bool)
                or evaluated_version != current_version):
            raise CognitiveIntegrityError("decision evaluated against a stale state version")

        semantic_review_event_ids = payload.get("semantic_review_event_ids", [])
        semantic_review_status = payload.get("semantic_review_status", "not_applicable")
        semantic_review_applied = payload.get("semantic_review_applied", False)
        if not isinstance(semantic_review_event_ids, list) or any(
            not isinstance(item, str) or not item.strip()
            for item in semantic_review_event_ids
        ):
            raise CognitiveIntegrityError("decision semantic_review_event_ids is invalid")
        if len(set(semantic_review_event_ids)) != len(semantic_review_event_ids):
            raise CognitiveIntegrityError("decision contains duplicate semantic review references")
        if not isinstance(semantic_review_applied, bool):
            raise CognitiveIntegrityError("decision semantic_review_applied must be boolean")

        if grounded_review_policy:
            has_inferences = any(
                claim.get("epistemic_type") == "inference"
                for claim in proposal_data.get("claims", [])
            )
            if semantic_review_applied:
                review_summary = self._semantic_review_summary(
                    db, proposal_id, proposal_data, before_sequence=event_sequence
                )
                if semantic_review_event_ids != review_summary["review_event_ids"]:
                    raise CognitiveIntegrityError("decision semantic review references mismatch")
                if semantic_review_status != review_summary["status"]:
                    raise CognitiveIntegrityError("decision semantic review status mismatch")
                if review_summary["status"] == "awaiting_review":
                    raise CognitiveIntegrityError("a decision cannot be committed while review is incomplete")
                required_outcomes = {
                    "unsupported": "rejected",
                    "insufficient_context": "needs_more_evidence",
                    "uncertain": "deferred",
                    "conflicting": "deferred",
                    "supported": None,
                    "not_applicable": None,
                }
                if review_summary["status"] not in required_outcomes:
                    raise CognitiveIntegrityError("unknown semantic review summary status")
                expected_outcome = required_outcomes[review_summary["status"]]
                if expected_outcome is not None and outcome != expected_outcome:
                    raise CognitiveIntegrityError("decision outcome conflicts with semantic review status")
                if outcome == "accepted" and review_summary["status"] not in {"supported", "not_applicable"}:
                    raise CognitiveIntegrityError("accepted inference lacks supported semantic review")
            else:
                if semantic_review_event_ids or semantic_review_status != "not_applicable":
                    raise CognitiveIntegrityError("decision omitted required semantic review provenance")
                if outcome == "accepted" and has_inferences:
                    raise CognitiveIntegrityError("inference memory cannot be accepted without semantic review")
        elif semantic_review_applied or semantic_review_event_ids or semantic_review_status != "not_applicable":
            raise CognitiveIntegrityError("decision references semantic reviews outside grounded policy v0.2")

        db.execute(
            "UPDATE proposals SET status=?, decision_event_id=? WHERE proposal_id=?",
            (outcome, event.event_id, proposal_id),
        )
        if outcome == "accepted":
            transition_id = _nonempty(payload.get("transition_id"), "transition_id")
            memory_id = _nonempty(payload.get("memory_id"), "memory_id")
            if grounded:
                grounding_outcome, grounding_reason = self._evaluate_grounded_claims(proposal_data)
                if grounding_outcome != "accepted":
                    raise CognitiveIntegrityError(
                        "accepted grounded decision failed deterministic evidence validation: "
                        + grounding_reason
                    )
                memory = {
                    "memory_id": memory_id,
                    "memory_kind": proposal_data["memory_kind"],
                    "claims": proposal_data["claims"],
                    "evidence_event_ids": expected_evidence_ids,
                    "proposal_id": proposal_id,
                    "proposal_event_id": payload["proposal_event_id"],
                    "decision_event_id": event.event_id,
                    "transition_id": transition_id,
                    "created_at": event.occurred_at,
                    "status": "accepted",
                    "origin": proposal_data["origin"],
                    "claim_schema": "grounded-memory-claims.v2",
                    "policy": payload["policy"],
                    "semantic_review_event_ids": semantic_review_event_ids,
                    "semantic_review_status": semantic_review_status,
                }
            else:
                memory = {
                    "memory_id": memory_id,
                    "memory_kind": proposal_data["memory_kind"],
                    "content": proposal_data["candidate_content"],
                    "evidence_event_ids": expected_evidence_ids,
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
    def _validate_semantic_review_shape(event: CognitiveEvent) -> dict[str, Any]:
        """Validate event-local semantic-review fields without consulting mutable state."""
        payload = event.payload
        allowed = {
            "review_id", "proposal_id", "proposal_event_id", "proposal_digest",
            "claim_id", "claim_digest", "reviewer", "contract_version", "outcome",
            "reasoning_summary", "supporting_claim_ids", "alternative_explanations",
            "limitations",
        }
        if set(payload) != allowed:
            raise ValueError("semantic review payload contains missing or unsupported fields")
        review_id = _nonempty(payload.get("review_id"), "review_id")
        proposal_id = _nonempty(payload.get("proposal_id"), "proposal_id")
        proposal_event_id = _nonempty(payload.get("proposal_event_id"), "proposal_event_id")
        proposal_digest = _nonempty(payload.get("proposal_digest"), "proposal_digest")
        claim_id = _nonempty(payload.get("claim_id"), "claim_id")
        claim_digest = _nonempty(payload.get("claim_digest"), "claim_digest")
        reviewer = payload.get("reviewer")
        if not isinstance(reviewer, Mapping) or set(reviewer) != {"component", "version"}:
            raise ValueError("reviewer must contain only component and version")
        reviewer_id = _nonempty(reviewer.get("component"), "reviewer.component")
        _nonempty(reviewer.get("version"), "reviewer.version")
        if event.source != f"semantic-review.pipeline:{reviewer_id}":
            raise ValueError("semantic review source/reviewer mismatch")
        if payload.get("contract_version") != SEMANTIC_REVIEW_CONTRACT_VERSION:
            raise ValueError("unsupported semantic review contract version")
        outcome = _nonempty(payload.get("outcome"), "review.outcome")
        if outcome not in {"supported", "uncertain", "unsupported", "insufficient_context"}:
            raise ValueError("unsupported semantic review outcome")
        _nonempty(payload.get("reasoning_summary"), "reasoning_summary")

        def validate_string_list(value: Any, name: str) -> list[str]:
            if not isinstance(value, list) or any(
                not isinstance(item, str) or not item.strip() for item in value
            ):
                raise ValueError(f"{name} must be a string list")
            if len(set(value)) != len(value):
                raise ValueError(f"{name} must not contain duplicates")
            return value

        supporting_ids = validate_string_list(
            payload.get("supporting_claim_ids"), "supporting_claim_ids"
        )
        validate_string_list(payload.get("alternative_explanations"), "alternative_explanations")
        validate_string_list(payload.get("limitations"), "limitations")
        return {
            "review_id": review_id,
            "proposal_id": proposal_id,
            "proposal_event_id": proposal_event_id,
            "proposal_digest": proposal_digest,
            "claim_id": claim_id,
            "claim_digest": claim_digest,
            "supporting_claim_ids": supporting_ids,
        }

    def _validate_semantic_review_event(
        self,
        db: sqlite3.Connection,
        event: CognitiveEvent,
        *,
        current_sequence: int,
    ) -> None:
        review = self._validate_semantic_review_shape(event)
        review_id = review["review_id"]
        proposal_id = review["proposal_id"]
        proposal_event_id = review["proposal_event_id"]
        proposal_digest = review["proposal_digest"]
        claim_id = review["claim_id"]
        claim_digest = review["claim_digest"]
        supporting_ids = review["supporting_claim_ids"]

        proposal = db.execute(
            "SELECT proposal_digest,proposal_event_id,proposal_json,status,decision_event_id "
            "FROM proposals WHERE proposal_id=?",
            (proposal_id,),
        ).fetchone()
        if proposal is None:
            raise CognitiveIntegrityError("semantic review references missing proposal")
        if proposal["decision_event_id"] is not None or proposal["status"] != "pending":
            raise ValueError("semantic review cannot be submitted after a terminal proposal decision")
        if proposal_event_id != proposal["proposal_event_id"]:
            raise ValueError("semantic review proposal_event_id mismatch")
        if proposal_digest != "sha256:" + proposal["proposal_digest"]:
            raise ValueError("semantic review proposal_digest mismatch")
        proposal_json = json.loads(proposal["proposal_json"])
        if self._proposal_event_type(db, proposal_id) != GROUNDED_PROPOSAL_EVENT:
            raise ValueError("semantic review applies only to grounded v2 proposals")
        claim_by_id = {claim["claim_id"]: claim for claim in proposal_json["claims"]}
        claim = claim_by_id.get(claim_id)
        if claim is None or claim.get("epistemic_type") != "inference":
            raise ValueError("semantic review target must be an inference claim in the proposal")
        if claim_digest != "sha256:" + _digest(_canonical(claim)):
            raise ValueError("semantic review claim_digest mismatch")
        derived_ids = claim["derived_from_claim_ids"]
        if not set(supporting_ids).issubset(set(derived_ids)):
            raise ValueError("supporting_claim_ids must be direct source claims for the inference")
        if event.payload.get("outcome") == "supported" and not supporting_ids:
            raise ValueError("supported review requires at least one supporting source claim")

        duplicate = db.execute(
            "SELECT e.event_id,p.payload_json FROM events e "
            "JOIN payloads p ON p.payload_ref=e.payload_ref "
            "WHERE e.event_type=? AND e.sequence<?",
            (SEMANTIC_REVIEW_EVENT, current_sequence),
        ).fetchall()
        for row in duplicate:
            prior = json.loads(row["payload_json"])
            if prior.get("review_id") == review_id:
                raise CognitiveIntegrityError("duplicate semantic review ID in durable history")

    @staticmethod
    def _proposal_event_type(db: sqlite3.Connection, proposal_id: str) -> str:
        row = db.execute(
            "SELECT event_type FROM events WHERE event_id=?",
            (CognitiveMemoryStore._proposal_event_id(db, proposal_id),),
        ).fetchone()
        if row is None:
            raise CognitiveIntegrityError("proposal event is missing from event history")
        return str(row["event_type"])

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
            proposal_event_type = self._proposal_event_type(db, proposal_id)
            grounded = proposal_event_type == GROUNDED_PROPOSAL_EVENT
            if grounded:
                outcome, reason = self._evaluate_grounded_claims(proposal)
                evidence_event_ids = self._grounded_evidence_event_ids(proposal)
                decision_policy_id = GROUNDED_POLICY_ID
                decision_policy_version = GROUNDED_POLICY_VERSION
            else:
                reason = "proposal and evidence references passed deterministic provenance checks"
                outcome = "accepted"
                evidence_event_ids = proposal["evidence_event_ids"]
                decision_policy_id = POLICY_ID
                decision_policy_version = POLICY_VERSION
                for evidence_id in evidence_event_ids:
                    try:
                        evidence_record = self.get_event(evidence_id)
                    except KeyError:
                        outcome = "needs_more_evidence"
                        reason = f"referenced evidence event is missing: {evidence_id}"
                        break
                    if evidence_record["event_type"] != OBSERVATION_EVENT:
                        outcome = "rejected"
                        reason = f"evidence event is not an allowed observation: {evidence_id}"
                        break
                    self._validate_observation(evidence_record["payload"])

            current_state_version = self._authoritative_state_version(db)
            self._assert_accepted_projection_consistent()
            self._assert_motivation_projection_consistent()
            based_on_version = int(proposal["based_on"]["state_version"])

            semantic_review_event_ids: list[str] = []
            semantic_review_status = "not_applicable"
            semantic_review_applied = False
            if grounded and outcome == "accepted":
                has_inferences = any(
                    claim.get("epistemic_type") == "inference"
                    for claim in proposal.get("claims", [])
                )
                if has_inferences:
                    review_summary = self._semantic_review_summary(db, proposal_id, proposal)
                    semantic_review_event_ids = review_summary["review_event_ids"]
                    semantic_review_status = review_summary["status"]
                    if semantic_review_status == "awaiting_review":
                        return {
                            "status": "awaiting_review",
                            "proposal_id": proposal_id,
                            "claim_ids": review_summary["missing_claim_ids"],
                            "reason": review_summary["reason"],
                        }
                    semantic_review_applied = True
                    if semantic_review_status == "unsupported":
                        outcome = "rejected"
                        reason = review_summary["reason"]
                    elif semantic_review_status == "insufficient_context":
                        outcome = "needs_more_evidence"
                        reason = review_summary["reason"]
                    elif semantic_review_status in {"uncertain", "conflicting"}:
                        outcome = "deferred"
                        reason = review_summary["reason"]

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
                "policy": {"id": decision_policy_id, "version": decision_policy_version},
                "evidence_event_ids": evidence_event_ids,
                "semantic_review_event_ids": semantic_review_event_ids,
                "semantic_review_status": semantic_review_status,
                "semantic_review_applied": semantic_review_applied,
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

    def get_event(
        self, event_id: str, *, _validate_decision_context: bool = True
    ) -> dict[str, Any]:
        """Read one immutable event with its content-addressed payload."""
        _nonempty(event_id, "event_id")
        row = self._db.execute(
            "SELECT e.sequence,e.event_id,e.occurred_at,e.received_at,e.correlation_id,"
            "e.event_type,e.source,e.payload_ref,e.event_digest,p.payload_json "
            "FROM events e LEFT JOIN payloads p ON p.payload_ref=e.payload_ref "
            "WHERE e.event_id=?",
            (event_id,),
        ).fetchone()
        if row is None:
            raise KeyError(event_id)
        try:
            payload_json = row["payload_json"]
            if payload_json is None:
                raise CognitiveIntegrityError(f"event payload is missing: {event_id}")
            if not isinstance(payload_json, str):
                raise CognitiveIntegrityError(f"event payload is not stored as text: {event_id}")
            _nonempty(row["event_id"], "event_id")
            _nonempty(row["correlation_id"], "correlation_id")
            _nonempty(row["event_type"], "event_type")
            _nonempty(row["source"], "source")
            _timestamp(row["occurred_at"], "occurred_at")
            if "sha256:" + _digest(payload_json) != row["payload_ref"]:
                raise CognitiveIntegrityError(f"payload digest failure: {event_id}")
            payload = json.loads(payload_json)
            if not isinstance(payload, dict):
                raise CognitiveIntegrityError(f"event payload is not an object: {event_id}")
            try:
                canonical_payload_json = _canonical(payload)
            except (TypeError, ValueError, RecursionError, OverflowError) as exc:
                raise CognitiveIntegrityError(
                    f"event payload cannot be canonically serialized: {event_id}"
                ) from exc
            if canonical_payload_json != payload_json:
                raise CognitiveIntegrityError(f"event payload is not canonically serialized: {event_id}")
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
            decision_types = {
                DECISION_EVENT, MOTIVATION_DECISION_EVENT,
                GOAL_BATCH_DECISION_EVENT, GOAL_ACTIVATION_DECISION_EVENT,
                GOAL_PAUSE_RESUME_DECISION_EVENT,
            }
            if event.event_type in decision_types:
                proposal_id = _nonempty(
                    payload.get("proposal_id"), "decision.proposal_id"
                )
                outcome = _nonempty(payload.get("outcome"), "decision.outcome")
                if outcome not in {"accepted", "rejected", "deferred", "needs_more_evidence"}:
                    raise CognitiveIntegrityError("invalid durable decision outcome")

                decision_fields = {
                    DECISION_EVENT: {
                        "proposal_id", "proposal_event_id", "outcome", "policy",
                        "evidence_event_ids", "semantic_review_event_ids",
                        "semantic_review_status", "semantic_review_applied", "reason",
                        "evaluated_state_version", "transition_id", "memory_id",
                    },
                    MOTIVATION_DECISION_EVENT: {
                        "proposal_id", "proposal_event_id", "outcome", "policy",
                        "evidence_event_ids", "signal", "transition_id", "reason",
                        "evaluated_state_version",
                    },
                    GOAL_BATCH_DECISION_EVENT: {
                        "proposal_id", "proposal_event_id", "outcome", "policy",
                        "evaluated_state_version", "transitions", "reason",
                    },
                    GOAL_ACTIVATION_DECISION_EVENT: {
                        "proposal_id", "proposal_event_id", "outcome", "policy",
                        "evaluated_state_version", "goal_id", "expected_goal_version",
                        "transition", "reason",
                    },
                    GOAL_PAUSE_RESUME_DECISION_EVENT: {
                        "proposal_id", "proposal_event_id", "outcome", "policy",
                        "evaluated_state_version", "goal_id", "expected_goal_version",
                        "operation", "transition", "reason",
                    },
                }[event.event_type]
                if set(payload) != decision_fields:
                    raise CognitiveIntegrityError(
                        "durable decision contains missing or unsupported fields"
                    )

                if event.event_type == DECISION_EVENT:
                    decision_number = int(self._db.execute(
                        "SELECT COUNT(*) FROM events WHERE event_type=? AND sequence<?",
                        (DECISION_EVENT, int(row["sequence"])),
                    ).fetchone()[0]) + 1
                    expected_event_id = f"csd-decision:{proposal_id}:{decision_number}"
                    expected_correlation_id = f"proposal:{proposal_id}"
                    expected_source = DECISION_SOURCE
                elif event.event_type == MOTIVATION_DECISION_EVENT:
                    decision_number = int(self._db.execute(
                        "SELECT COUNT(*) FROM events WHERE event_type=? AND sequence<?",
                        (MOTIVATION_DECISION_EVENT, int(row["sequence"])),
                    ).fetchone()[0]) + 1
                    expected_event_id = (
                        f"csd-motivation-decision:{proposal_id}:{decision_number}"
                    )
                    expected_correlation_id = f"motivation-proposal:{proposal_id}"
                    expected_source = MOTIVATION_DECISION_SOURCE
                else:
                    goal_identity = {
                        GOAL_BATCH_DECISION_EVENT: (
                            f"csd-goal-decision:{proposal_id}",
                            f"goal-proposal:{proposal_id}",
                        ),
                        GOAL_ACTIVATION_DECISION_EVENT: (
                            f"csd-goal-activation-decision:{proposal_id}",
                            f"goal-activation-proposal:{proposal_id}",
                        ),
                        GOAL_PAUSE_RESUME_DECISION_EVENT: (
                            f"csd-goal-pause-resume-decision:{proposal_id}",
                            f"goal-pause-resume-proposal:{proposal_id}",
                        ),
                    }[event.event_type]
                    expected_event_id, expected_correlation_id = goal_identity
                    expected_source = GOAL_DECISION_SOURCE

                if (
                    event.event_id != expected_event_id
                    or event.correlation_id != expected_correlation_id
                    or event.source != expected_source
                ):
                    raise CognitiveIntegrityError(
                        "decision event identity or correlation_id mismatch"
                    )

            # Every read path enforces the same event-local schema contract
            # as duplicate delivery and Recovery. Decision history checks are
            # skipped only for internal state-version scans to prevent recursion.
            self._validate_event_local_shape(
                self._db,
                {
                    "event_id": event.event_id,
                    "occurred_at": event.occurred_at,
                    "correlation_id": event.correlation_id,
                    "event_type": event.event_type,
                    "source": event.source,
                    "payload": event.payload,
                },
                sequence=int(row["sequence"]),
            )
            if event.event_type in decision_types and _validate_decision_context:
                self._validate_decision_event_history(
                    self._db, event, sequence=int(row["sequence"])
                )
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
        except CognitiveIntegrityError:
            raise
        except (TypeError, ValueError, RecursionError, OverflowError) as exc:
            raise CognitiveIntegrityError(
                f"invalid durable event envelope: {event_id}"
            ) from exc

    def _memory_projection_sources(
        self,
    ) -> tuple[
        dict[str, dict[str, Any]],
        dict[str, tuple[dict[str, Any], dict[str, Any]]],
    ]:
        proposal_rows = self._db.execute(
            "SELECT event_id FROM events WHERE event_type IN (?,?) ORDER BY sequence",
            (PROPOSAL_EVENT, GROUNDED_PROPOSAL_EVENT),
        ).fetchall()
        expected_proposals: dict[str, dict[str, Any]] = {}
        for row in proposal_rows:
            event = self.get_event(row["event_id"])
            payload = event["payload"]
            proposal_id = _nonempty(payload.get("proposal_id"), "proposal_id")
            proposal_json = _canonical(dict(payload))
            proposal_digest = _digest(proposal_json)
            prior = expected_proposals.get(proposal_id)
            if prior is None:
                expected_proposals[proposal_id] = {
                    "proposal_digest": proposal_digest,
                    "proposal_event_id": event["event_id"],
                    "proposal_json": proposal_json,
                    "proposal": payload,
                    "event_type": event["event_type"],
                }
            elif prior["proposal_digest"] != proposal_digest:
                raise CognitiveIntegrityError("memory proposal identity conflict in event history")

        decision_rows = self._db.execute(
            "SELECT event_id FROM events WHERE event_type=? ORDER BY sequence",
            (DECISION_EVENT,),
        ).fetchall()
        expected_decisions: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
        for row in decision_rows:
            event = self.get_event(row["event_id"])
            payload = event["payload"]
            proposal_id = _nonempty(payload.get("proposal_id"), "decision.proposal_id")
            if proposal_id in expected_decisions:
                raise CognitiveIntegrityError("memory proposal has multiple decision events")
            expected_decisions[proposal_id] = (event, payload)

        proposal_projection_rows = self._db.execute(
            "SELECT proposal_id,proposal_digest,proposal_event_id,proposal_json,status,decision_event_id "
            "FROM proposals"
        ).fetchall()
        if len(proposal_projection_rows) != len(expected_proposals):
            raise CognitiveIntegrityError("memory proposal projection row count differs from event history")
        for row in proposal_projection_rows:
            expected = expected_proposals.get(row["proposal_id"])
            if expected is None:
                raise CognitiveIntegrityError("memory proposal projection has no source event")
            decision = expected_decisions.get(row["proposal_id"])
            expected_status = decision[1].get("outcome") if decision else "pending"
            expected_decision_id = decision[0]["event_id"] if decision else None
            if (
                row["proposal_digest"] != expected["proposal_digest"]
                or row["proposal_event_id"] != expected["proposal_event_id"]
                or row["proposal_json"] != expected["proposal_json"]
                or row["status"] != expected_status
                or row["decision_event_id"] != expected_decision_id
            ):
                raise CognitiveIntegrityError("memory proposal projection differs from event history")
        if set(expected_decisions) - set(expected_proposals):
            raise CognitiveIntegrityError("memory decision references a missing proposal event")
        return expected_proposals, expected_decisions

    def _assert_proposal_projection_consistent(self) -> None:
        self._memory_projection_sources()

    def _assert_accepted_projection_consistent(self) -> None:
        # Validate accepted-memory content against the durable decision history.
        expected_proposals, expected_decisions = self._memory_projection_sources()
        expected_memories: dict[str, dict[str, Any]] = {}
        for proposal_id, (event, payload) in expected_decisions.items():
            outcome = payload.get("outcome")
            if outcome not in {"accepted", "rejected", "deferred", "needs_more_evidence"}:
                raise CognitiveIntegrityError("invalid memory decision outcome in event history")
            if outcome != "accepted":
                if payload.get("transition_id") is not None or payload.get("memory_id") is not None:
                    raise CognitiveIntegrityError("non-accepted memory decision contains a transition")
                continue

            proposal_record = expected_proposals[proposal_id]
            proposal_data = proposal_record["proposal"]
            proposal_event_id = proposal_record["proposal_event_id"]
            if payload.get("proposal_event_id") != proposal_event_id:
                raise CognitiveIntegrityError("memory decision proposal-event reference mismatch")
            memory_id = _nonempty(payload.get("memory_id"), "decision.memory_id")
            transition_id = _nonempty(payload.get("transition_id"), "decision.transition_id")
            grounded = proposal_record["event_type"] == GROUNDED_PROPOSAL_EVENT
            evidence_ids = (
                self._grounded_evidence_event_ids(proposal_data)
                if grounded else proposal_data["evidence_event_ids"]
            )
            if payload.get("evidence_event_ids") != evidence_ids:
                raise CognitiveIntegrityError("memory decision evidence references mismatch")

            if grounded:
                grounding_outcome, grounding_reason = self._evaluate_grounded_claims(proposal_data)
                if grounding_outcome != "accepted":
                    raise CognitiveIntegrityError(
                        "accepted grounded projection no longer passes evidence validation: "
                        + grounding_reason
                    )
                memory = {
                    "memory_id": memory_id,
                    "memory_kind": proposal_data["memory_kind"],
                    "claims": proposal_data["claims"],
                    "evidence_event_ids": evidence_ids,
                    "proposal_id": proposal_id,
                    "proposal_event_id": proposal_event_id,
                    "decision_event_id": event["event_id"],
                    "transition_id": transition_id,
                    "created_at": event["occurred_at"],
                    "status": "accepted",
                    "origin": proposal_data["origin"],
                    "claim_schema": "grounded-memory-claims.v2",
                    "policy": payload["policy"],
                    "semantic_review_event_ids": payload["semantic_review_event_ids"],
                    "semantic_review_status": payload["semantic_review_status"],
                }
            else:
                memory = {
                    "memory_id": memory_id,
                    "memory_kind": proposal_data["memory_kind"],
                    "content": proposal_data["candidate_content"],
                    "evidence_event_ids": evidence_ids,
                    "proposal_id": proposal_id,
                    "proposal_event_id": proposal_event_id,
                    "decision_event_id": event["event_id"],
                    "transition_id": transition_id,
                    "created_at": event["occurred_at"],
                    "status": "accepted",
                    "policy": payload["policy"],
                }
            if memory_id in expected_memories:
                raise CognitiveIntegrityError("duplicate accepted memory identity in event history")
            expected_memories[memory_id] = {
                "proposal_id": proposal_id,
                "transition_id": transition_id,
                "memory_json": _canonical(memory),
            }

        memory_projection_rows = self._db.execute(
            "SELECT memory_id,proposal_id,transition_id,memory_json FROM accepted_memories"
        ).fetchall()
        if len(memory_projection_rows) != len(expected_memories):
            raise CognitiveIntegrityError(
                "accepted-memory projection row count differs from accepted decisions; run Recovery"
            )
        for row in memory_projection_rows:
            expected = expected_memories.get(row["memory_id"])
            if expected is None or (
                row["proposal_id"] != expected["proposal_id"]
                or row["transition_id"] != expected["transition_id"]
                or row["memory_json"] != expected["memory_json"]
            ):
                raise CognitiveIntegrityError(
                    "accepted-memory projection differs from authoritative decision events; run Recovery"
                )

    def get_memories(
        self,
        *,
        query: str | None = None,
        memory_kind: str | None = None,
        epistemic_type: str | None = None,
        evidence_event_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Retrieve accepted memories with explicit prototype filters.

        query is a case-insensitive substring filter over stored memory/claim
        text. It is deliberately not described as semantic retrieval.
        """
        self._assert_accepted_projection_consistent()
        if query is not None:
            _nonempty(query, "query")
        if memory_kind is not None:
            _nonempty(memory_kind, "memory_kind")
        if epistemic_type is not None and (
            not isinstance(epistemic_type, str)
            or epistemic_type not in {"source_assertion", "inference"}
        ):
            raise ValueError("epistemic_type must be source_assertion or inference")
        if evidence_event_id is not None:
            _nonempty(evidence_event_id, "evidence_event_id")
        if limit is not None and (
            not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0
        ):
            raise ValueError("limit must be a positive integer or None")
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise ValueError("offset must be a non-negative integer")

        rows = self._db.execute(
            "SELECT memory_json FROM accepted_memories ORDER BY rowid"
        ).fetchall()
        memories = [json.loads(row["memory_json"]) for row in rows]
        if memory_kind is not None:
            memories = [m for m in memories if m.get("memory_kind") == memory_kind]
        if epistemic_type is not None:
            memories = [
                m for m in memories
                if any(
                    claim.get("epistemic_type") == epistemic_type
                    for claim in m.get("claims", [])
                )
            ]
        if evidence_event_id is not None:
            def has_evidence(memory: Mapping[str, Any]) -> bool:
                refs = set(memory.get("evidence_event_ids", []))
                for claim in memory.get("claims", []):
                    for evidence in claim.get("evidence", []):
                        event_id = evidence.get("event_id")
                        if isinstance(event_id, str):
                            refs.add(event_id)
                return evidence_event_id in refs
            memories = [m for m in memories if has_evidence(m)]
        if query is not None:
            needle = query.casefold()
            def contains_text(memory: Mapping[str, Any]) -> bool:
                parts: list[str] = []
                content = memory.get("content")
                if isinstance(content, str):
                    parts.append(content)
                for claim in memory.get("claims", []):
                    text = claim.get("text")
                    if isinstance(text, str):
                        parts.append(text)
                return any(needle in part.casefold() for part in parts)
            memories = [m for m in memories if contains_text(m)]

        selected = memories[offset:]
        if limit is not None:
            selected = selected[:limit]
        return selected

    def get_memory(self, memory_id: str) -> dict[str, Any]:
        """Retrieve one accepted memory by stable ID, with full provenance."""
        self._assert_accepted_projection_consistent()
        _nonempty(memory_id, "memory_id")
        row = self._db.execute(
            "SELECT memory_json FROM accepted_memories WHERE memory_id=?",
            (memory_id,),
        ).fetchone()
        if row is None:
            raise KeyError(memory_id)
        return json.loads(row["memory_json"])

    def get_proposal(self, proposal_id: str) -> dict[str, Any]:
        _nonempty(proposal_id, "proposal_id")
        self._assert_proposal_projection_consistent()
        row = self._db.execute(
            "SELECT proposal_json,proposal_digest,proposal_event_id,status,decision_event_id "
            "FROM proposals WHERE proposal_id=?",
            (proposal_id,),
        ).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        proposal = json.loads(row["proposal_json"])
        if _digest(_canonical(proposal)) != row["proposal_digest"]:
            raise CognitiveIntegrityError("proposal projection digest mismatch")
        return {
            "proposal": proposal,
            "proposal_digest": "sha256:" + row["proposal_digest"],
            "proposal_event_id": row["proposal_event_id"],
            "status": row["status"],
            "decision_event_id": row["decision_event_id"],
        }

    def get_semantic_reviews(self, proposal_id: str) -> list[dict[str, Any]]:
        """Return immutable proposal-bound review events in event order."""
        proposal = self.get_proposal(proposal_id)
        rows = self._db.execute(
            "SELECT event_id,sequence FROM events WHERE event_type=? ORDER BY sequence",
            (SEMANTIC_REVIEW_EVENT,),
        ).fetchall()
        reviews: list[dict[str, Any]] = []
        for row in rows:
            event = self.get_event(row["event_id"])
            payload = event["payload"]
            if payload.get("proposal_id") != proposal_id:
                continue
            if payload.get("proposal_event_id") != proposal["proposal_event_id"]:
                raise CognitiveIntegrityError("review references a different proposal event")
            if payload.get("proposal_digest") != proposal["proposal_digest"]:
                raise CognitiveIntegrityError("review proposal digest does not match stored proposal")
            reviews.append({
                "event_id": event["event_id"],
                "sequence": event["sequence"],
                "payload": payload,
            })
        return reviews

    def get_life_signal_snapshot(self) -> dict[str, Any]:
        """Return one integrity-checked, transactionally consistent Life Engine read.

        The snapshot contains accepted motivation signals, versioned goal
        projections, and the shared authoritative state_version. Activity
        options are omitted until a trusted capability-filtered source exists.
        """
        with self._read_tx() as db:
            state_version = self._authoritative_state_version(db)
            self._assert_accepted_projection_consistent()
            self._assert_motivation_projection_consistent()
            self._assert_goal_projection_consistent()
            rows = db.execute(
                "SELECT signal_json FROM motivation_signals ORDER BY rowid"
            ).fetchall()
            signals = [json.loads(row["signal_json"]) for row in rows]
            goals = self.get_goals()
            return {
                "state_version": state_version,
                "signals": signals,
                "goals": goals,
            }

    def get_state_snapshot(self) -> dict[str, Any]:
        """Return diagnostics and projection counts from one SQLite read snapshot."""
        with self._read_tx() as db:
            state_version = self._authoritative_state_version(db)
            accepted_memory_count = int(db.execute(
                "SELECT COUNT(*) FROM accepted_memories"
            ).fetchone()[0])
            motivation_signal_count = int(db.execute(
                "SELECT COUNT(*) FROM motivation_signals"
            ).fetchone()[0])
            motivation_signal_version_count = int(db.execute(
                "SELECT COUNT(*) FROM motivation_signal_versions"
            ).fetchone()[0])
            goal_count = int(db.execute("SELECT COUNT(*) FROM goals").fetchone()[0])
            goal_version_count = int(db.execute("SELECT COUNT(*) FROM goal_versions").fetchone()[0])
            memory_consistent = True
            try:
                self._assert_accepted_projection_consistent()
            except CognitiveIntegrityError:
                memory_consistent = False
            motivation_consistent = True
            try:
                self._assert_motivation_projection_consistent()
            except CognitiveIntegrityError:
                motivation_consistent = False
            goal_consistent = True
            try:
                self._assert_goal_projection_consistent()
            except CognitiveIntegrityError:
                goal_consistent = False
            return {
                "event_count": int(db.execute("SELECT COUNT(*) FROM events").fetchone()[0]),
                "state_version": state_version,
                "proposal_count": int(db.execute("SELECT COUNT(*) FROM proposals").fetchone()[0]),
                "accepted_memory_count": accepted_memory_count,
                "motivation_signal_count": motivation_signal_count,
                "motivation_signal_version_count": motivation_signal_version_count,
                "motivation_proposal_count": int(db.execute("SELECT COUNT(*) FROM motivation_proposals").fetchone()[0]),
                "goal_activation_proposal_count": int(db.execute("SELECT COUNT(*) FROM goal_activation_proposals").fetchone()[0]),
                "goal_pause_resume_proposal_count": int(db.execute("SELECT COUNT(*) FROM goal_pause_resume_proposals").fetchone()[0]),
                "goal_projection_consistent": goal_consistent,
                "projection_consistent": memory_consistent and motivation_consistent and goal_consistent,
            }

    def recover(self) -> dict[str, int]:
        """Validate and rebuild one stable event-log snapshot; never evaluate proposals."""
        # Acquire the writer reservation before reading the event stream. Otherwise a
        # concurrent append between SELECT and BEGIN IMMEDIATE could be omitted from
        # the parsed replay while remaining in the authoritative event table.
        with self._tx() as db:
            integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise CognitiveIntegrityError(f"SQLite integrity_check failed: {integrity}")
            if db.execute("PRAGMA foreign_key_check").fetchall():
                raise CognitiveIntegrityError("SQLite foreign_key_check failed")

            rows = db.execute(
                "SELECT e.sequence,e.event_id,e.occurred_at,e.received_at,e.correlation_id,e.event_type,"
                "e.source,e.payload_ref,e.event_digest,p.payload_json "
                "FROM events e LEFT JOIN payloads p ON p.payload_ref=e.payload_ref "
                "ORDER BY e.sequence"
            ).fetchall()

            parsed: list[tuple[int, CognitiveEvent, str]] = []
            expected = 1
            for row in rows:
                if int(row["sequence"]) != expected:
                    raise CognitiveIntegrityError("event sequence gap")
                expected += 1
                payload_json = row["payload_json"]
                if payload_json is None:
                    raise CognitiveIntegrityError(f"missing event payload: {row['event_id']}")
                if not isinstance(payload_json, str):
                    raise CognitiveIntegrityError(
                        f"event payload is not stored as text: {row['event_id']}"
                    )
                if "sha256:" + _digest(payload_json) != row["payload_ref"]:
                    raise CognitiveIntegrityError(f"payload integrity failure: {row['event_id']}")
                try:
                    payload = json.loads(payload_json)
                except (TypeError, ValueError, RecursionError, OverflowError) as exc:
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
                try:
                    _nonempty(event.event_id, "event_id")
                    _nonempty(event.correlation_id, "correlation_id")
                    _nonempty(event.event_type, "event_type")
                    _nonempty(event.source, "source")
                    _timestamp(event.occurred_at, "occurred_at")
                    _timestamp(row["received_at"], "received_at")
                    computed_event_digest = self._event_digest(
                        event, row["payload_ref"], row["received_at"]
                    )
                except (TypeError, ValueError, RecursionError, OverflowError) as exc:
                    raise CognitiveIntegrityError(
                        f"invalid durable event envelope: {row['event_id']}"
                    ) from exc
                if computed_event_digest != row["event_digest"]:
                    raise CognitiveIntegrityError(f"event envelope digest failure: {event.event_id}")
                parsed.append((expected - 1, event, payload_json))

            db.execute("DELETE FROM accepted_memories")
            db.execute("DELETE FROM proposals")
            db.execute("DELETE FROM motivation_signal_versions")
            db.execute("DELETE FROM motivation_signals")
            db.execute("DELETE FROM motivation_proposals")
            db.execute("DELETE FROM goal_versions")
            db.execute("DELETE FROM goals")
            db.execute("DELETE FROM goal_proposals")
            db.execute("DELETE FROM goal_activation_proposals")
            db.execute("DELETE FROM goal_pause_resume_proposals")
            for sequence, event, stored_payload_json in parsed:
                decision_types = {
                    DECISION_EVENT, MOTIVATION_DECISION_EVENT, GOAL_BATCH_DECISION_EVENT,
                    GOAL_ACTIVATION_DECISION_EVENT, GOAL_PAUSE_RESUME_DECISION_EVENT,
                }
                internal = event.event_type in decision_types and event.source == DECISION_SOURCE
                if event.event_type in decision_types and not internal:
                    raise CognitiveIntegrityError("forged decision event in durable history")
                try:
                    canonical_payload_json = self._validate_event(
                        event, internal=internal
                    )
                except (TypeError, ValueError, RecursionError, OverflowError) as exc:
                    raise CognitiveIntegrityError(
                        f"invalid durable event envelope: {event.event_id}"
                    ) from exc
                if canonical_payload_json != stored_payload_json:
                    raise CognitiveIntegrityError(
                        f"non-canonical durable event payload: {event.event_id}"
                    )
                if event.event_type not in {
                    OBSERVATION_EVENT, PROPOSAL_EVENT, GROUNDED_PROPOSAL_EVENT,
                    SEMANTIC_REVIEW_EVENT, DECISION_EVENT,
                    INTERACTION_EVENT, MOTIVATION_PROPOSAL_EVENT, MOTIVATION_DECISION_EVENT,
                    GOAL_BATCH_PROPOSAL_EVENT, GOAL_BATCH_DECISION_EVENT,
                    GOAL_ACTIVATION_PROPOSAL_EVENT, GOAL_ACTIVATION_DECISION_EVENT,
                    GOAL_PAUSE_RESUME_PROPOSAL_EVENT, GOAL_PAUSE_RESUME_DECISION_EVENT,
                }:
                    raise CognitiveIntegrityError(f"unknown event type: {event.event_type}")
                self._validate_proposal_snapshot_chronology(
                    db, event, sequence, replay=True
                )
                try:
                    self._apply_projection_event(
                        db, event, sequence, internal=internal
                    )
                except CognitiveIntegrityError:
                    raise
                except (
                    CognitiveStoreError, TypeError, ValueError, KeyError, IndexError,
                    RecursionError, OverflowError, sqlite3.IntegrityError,
                ) as exc:
                    raise CognitiveIntegrityError(
                        f"invalid durable event projection at sequence {sequence}: "
                        f"{event.event_id}"
                    ) from exc

            # Report counts from the same locked snapshot used for replay.
            return {
                "events": len(parsed),
                "proposals": int(db.execute("SELECT COUNT(*) FROM proposals").fetchone()[0]),
                "accepted_memories": int(db.execute(
                    "SELECT COUNT(*) FROM accepted_memories"
                ).fetchone()[0]),
                "motivation_proposals": int(db.execute(
                    "SELECT COUNT(*) FROM motivation_proposals"
                ).fetchone()[0]),
                "motivation_signals": int(db.execute(
                    "SELECT COUNT(*) FROM motivation_signals"
                ).fetchone()[0]),
                "motivation_signal_versions": int(db.execute(
                    "SELECT COUNT(*) FROM motivation_signal_versions"
                ).fetchone()[0]),
                "goal_proposals": int(db.execute("SELECT COUNT(*) FROM goal_proposals").fetchone()[0]),
                "goals": int(db.execute("SELECT COUNT(*) FROM goals").fetchone()[0]),
                "goal_versions": int(db.execute("SELECT COUNT(*) FROM goal_versions").fetchone()[0]),
                "goal_activation_proposals": int(db.execute("SELECT COUNT(*) FROM goal_activation_proposals").fetchone()[0]),
            }
