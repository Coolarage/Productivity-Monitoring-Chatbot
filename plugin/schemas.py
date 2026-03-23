from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ProductivityLabel(str, Enum):
    NO_DECLINE = "no_decline"
    DECLINE_RISK = "decline_risk"


class EmployeeKPIInput(BaseModel):
    """
    Raw KPI record as received from the host system.

    This mirrors the original dataset columns used in preprocessing_pipeline.py.
    Additional fields can be added without breaking the plugin, as long as the
    fields required by engineer_features() are present.
    """

    employee_id: str = Field(..., description="Unique identifier for the employee.")
    employee_email: str = Field(..., description="Employee email for notifications.")
    manager_id: str = Field(..., description="Unique identifier for the manager.")
    manager_email: str = Field(..., description="Manager email for notifications.")

    # Core KPI fields expected by preprocessing_pipeline.clean_raw_record/engineer_features
    date: Optional[str] = Field(None, description="Record date, e.g. '2015-01-13'.")
    department: Optional[str] = None
    team: Optional[int] = None
    targeted_productivity: Optional[float] = None
    actual_productivity: Optional[float] = None
    smv: Optional[float] = None
    wip: Optional[float] = None
    over_time: Optional[float] = None
    incentive: Optional[float] = None
    idle_time: Optional[float] = None
    idle_men: Optional[float] = None
    no_of_style_change: Optional[float] = None
    no_of_workers: Optional[float] = None

    # Allow host system to provide any extra KPI fields
    extra_fields: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional additional KPI fields from the host system.",
    )

    def to_raw_record(self) -> Dict[str, Any]:
        base = self.model_dump()
        base.update(base.pop("extra_fields", {}) or {})
        # Strip plugin-only metadata fields before feeding the preprocessing pipeline
        for k in ["employee_id", "employee_email", "manager_id", "manager_email"]:
            base.pop(k, None)
        return base


class RecommendationItem(BaseModel):
    area: str
    description: str


class EvaluationSummary(BaseModel):
    label: ProductivityLabel
    label_human_readable: str
    confidence: Optional[float] = Field(
        None,
        description="Optional model confidence for decline_risk class (0-1).",
    )
    explanation: str = Field(
        ...,
        description="Plain-language explanation of the prediction.",
    )
    weak_areas: List[str] = Field(
        default_factory=list,
        description="Short labels describing weaker performance dimensions.",
    )
    recommendations: List[RecommendationItem] = Field(
        default_factory=list,
        description="Actionable recommendations for employee and manager.",
    )


class EvaluationResult(BaseModel):
    evaluation_id: str
    employee_id: str
    manager_id: str
    summary: EvaluationSummary
    raw_features: Dict[str, Any] = Field(
        default_factory=dict,
        description="Engineered feature values passed into the model.",
    )
    model_output: Dict[str, Any] = Field(
        default_factory=dict,
        description="Low-level model output (predicted class, probabilities, etc.).",
    )


class EmailNotification(BaseModel):
    to: str
    subject: str
    body: str


class ManagerDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"


class ManagerReviewRequest(BaseModel):
    evaluation_id: str
    manager_id: str
    decision: ManagerDecision
    modified_recommendations: Optional[List[RecommendationItem]] = Field(
        default=None,
        description="Required when decision == MODIFY.",
    )
    manager_comment: Optional[str] = None


class ManagerReviewResult(BaseModel):
    evaluation_id: str
    manager_id: str
    final_recommendations: List[RecommendationItem]
    decision: ManagerDecision
    manager_comment: Optional[str] = None


class EmployeeFeedbackReason(str, Enum):
    WORKLOAD_PRESSURE = "workload_pressure"
    UNCLEAR_TASKS = "unclear_tasks"
    PERSONAL_CIRCUMSTANCES = "personal_circumstances"
    TECHNICAL_BLOCKERS = "technical_blockers"
    INSUFFICIENT_TRAINING = "insufficient_training"
    OTHER = "other"


class EmployeeFeedbackRequest(BaseModel):
    evaluation_id: str
    employee_id: str
    primary_reason: EmployeeFeedbackReason
    free_text_explanation: Optional[str] = Field(
        default=None,
        description="Optional narrative explanation from the employee.",
    )


class EmployeeFeedbackRecord(BaseModel):
    evaluation_id: str
    employee_id: str
    primary_reason: EmployeeFeedbackReason
    free_text_explanation: Optional[str] = None

