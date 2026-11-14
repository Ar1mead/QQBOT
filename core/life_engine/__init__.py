"""Autonomous motivation and life-engine reference interfaces.

These modules define provider-neutral proposals only. CSD persistence and
ASM-governed execution adapters are intentionally separate and not yet wired.
"""

from .contracts import (
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
from .engine import LifeEngine

__all__ = [
    "ActivityOption",
    "ChoiceProposal",
    "DeliberationProposal",
    "GoalProposal",
    "GoalState",
    "LifeEngine",
    "LifeSnapshot",
    "MotivationSignal",
    "ValidatedLifeProposal",
    "validate_life_proposal",
]
