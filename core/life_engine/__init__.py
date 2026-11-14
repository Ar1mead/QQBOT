"""Autonomous motivation and life-engine reference interfaces.

These modules define provider-neutral proposals only. CSD persistence and
ASM-governed execution adapters are intentionally separate and not yet wired.
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
from .engine import LifeEngine

__all__ = [
    "ActiveActivityState",
    "ActivityOption",
    "ChoiceProposal",
    "DeliberationProposal",
    "GoalProposal",
    "GoalState",
    "LifeEngine",
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
