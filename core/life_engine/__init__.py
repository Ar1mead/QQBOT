"""Autonomous motivation and life-engine reference interfaces.

These modules define provider-neutral proposals. CSD goal-state persistence is connected through a narrow proposal sink; ASM-governed external execution remains separate and unwired.
"""

from .contracts import (
    ActiveActivityState,
    ActivityOption,
    ChoiceProposal,
    DeliberationProposal,
    GoalProposal,
    GoalState,
    LifeSnapshot,
    MotivationSignal,
    ValidatedLifeProposal,
    validate_life_proposal,
)
from .motivation import (
    MotivationEvidence,
    MotivationSignalState,
    MotivationSnapshot,
    MotivationUpdateProposal,
    ValidatedMotivationUpdate,
    validate_motivation_update,
)
from .csd_adapter import (
    CognitiveStoreLifeSnapshotReader,
    CognitiveStoreLifeProposalSink,
    motivation_signal_from_csd,
    motivation_signals_from_csd,
)
from .engine import LifeEngine

__all__ = [
    "ActiveActivityState",
    "ActivityOption",
    "ChoiceProposal",
    "DeliberationProposal",
    "GoalProposal",
    "GoalState",
    "LifeEngine",
    "CognitiveStoreLifeSnapshotReader",
    "CognitiveStoreLifeProposalSink",
    "motivation_signal_from_csd",
    "motivation_signals_from_csd",
    "MotivationEvidence",
    "MotivationSignalState",
    "MotivationSnapshot",
    "MotivationUpdateProposal",
    "ValidatedMotivationUpdate",
    "validate_motivation_update",
    "LifeSnapshot",
    "MotivationSignal",
    "ValidatedLifeProposal",
    "validate_life_proposal",
]
