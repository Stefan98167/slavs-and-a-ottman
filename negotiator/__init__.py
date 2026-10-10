"""Small, deterministic building blocks for evaluating negotiation term sheets."""

from .evaluator import EvaluationInputError, evaluate_deal

__all__ = ["EvaluationInputError", "evaluate_deal"]
