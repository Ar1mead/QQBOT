"""Provider-neutral Life Engine orchestration.

The engine reads an authoritative snapshot, asks a replaceable deliberator for
one proposal, validates references/admissibility, and submits the proposal to a
CSD-facing sink. It never executes the selected activity.
"""

from __future__ import annotations

from typing import Any, Protocol

from .contracts import (
    LifeSnapshot,
    DeliberationProposal,
    ValidatedLifeProposal,
    validate_life_proposal,
)


class SnapshotReader(Protocol):
    def get_life_snapshot(self) -> LifeSnapshot:
        """Return a consistent read-only snapshot and its authoritative version."""


class Deliberator(Protocol):
    def deliberate(self, snapshot: LifeSnapshot) -> DeliberationProposal:
        """Propose goals and one choice; do not mutate state or execute tools."""


class LifeProposalSink(Protocol):
    def submit_life_proposal(
        self,
        proposal: ValidatedLifeProposal,
        *,
        expected_state_version: int,
    ) -> Any:
        """Submit an untrusted proposal to CSD; do not execute its activity."""


class LifeEngine:
    """Coordinate one deliberation opportunity without imposing a task."""

    def __init__(
        self,
        snapshot_reader: SnapshotReader,
        deliberator: Deliberator,
        proposal_sink: LifeProposalSink,
    ) -> None:
        self.snapshot_reader = snapshot_reader
        self.deliberator = deliberator
        self.proposal_sink = proposal_sink

    def consider(self) -> Any:
        """Read, deliberate, validate, and submit one proposal.

        A no-op is an ordinary valid proposal. No timer, retry, tool call, or
        side-effecting adapter is invoked by this method.
        """
        snapshot = self.snapshot_reader.get_life_snapshot()
        proposal = self.deliberator.deliberate(snapshot)
        validated = validate_life_proposal(snapshot, proposal)
        return self.proposal_sink.submit_life_proposal(
            validated,
            expected_state_version=snapshot.state_version,
        )
