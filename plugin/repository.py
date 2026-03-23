from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional

from .schemas import (
    EmployeeFeedbackRecord,
    EvaluationResult,
    ManagerDecision,
    ManagerReviewResult,
    RecommendationItem,
)


@dataclass
class EvaluationRecord:
    evaluation: EvaluationResult
    manager_review: Optional[ManagerReviewResult] = None
    employee_feedback: Optional[EmployeeFeedbackRecord] = None


class InMemoryEvaluationRepository:
    """
    Simple in-memory repository for demo and testing.

    The host system can replace this with a database-backed implementation
    by mirroring the public methods.
    """

    def __init__(self) -> None:
        self._store: Dict[str, EvaluationRecord] = {}

    def create_evaluation(self, evaluation: EvaluationResult) -> EvaluationResult:
        self._store[evaluation.evaluation_id] = EvaluationRecord(evaluation=evaluation)
        return evaluation

    def generate_id(self) -> str:
        return str(uuid.uuid4())

    def get_evaluation(self, evaluation_id: str) -> Optional[EvaluationRecord]:
        return self._store.get(evaluation_id)

    def save_manager_review(
        self,
        evaluation_id: str,
        manager_id: str,
        final_recommendations: list[RecommendationItem],
        decision: ManagerDecision,
        manager_comment: str | None = None,
    ) -> ManagerReviewResult:
        record = self._store.get(evaluation_id)
        if not record:
            raise KeyError(f"Evaluation '{evaluation_id}' not found.")

        review = ManagerReviewResult(
            evaluation_id=evaluation_id,
            manager_id=manager_id,
            final_recommendations=final_recommendations,
            decision=decision,
            manager_comment=manager_comment,
        )
        record.manager_review = review
        return review

    def save_employee_feedback(
        self, feedback: EmployeeFeedbackRecord
    ) -> EmployeeFeedbackRecord:
        record = self._store.get(feedback.evaluation_id)
        if not record:
            raise KeyError(f"Evaluation '{feedback.evaluation_id}' not found.")
        record.employee_feedback = feedback
        return feedback

