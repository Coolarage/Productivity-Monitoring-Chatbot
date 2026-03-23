from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any, Dict, List
import uuid

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .chatbot_logic import build_evaluation_summary
from .email_service import ConsoleEmailSender, EmailSender, SmtpEmailSender
from .model_pipeline import get_model_pipeline
from .repository import InMemoryEvaluationRepository
from .schemas import (
    CsvBatchEvaluationResponse,
    CsvRowEvaluationResult,
    EmailNotification,
    EmployeeFeedbackRecord,
    EmployeeFeedbackRequest,
    EmployeeKPIInput,
    EvaluationResult,
    ManagerDecision,
    ManagerReviewRequest,
)

app = FastAPI(
    title="Proactive Productivity Monitoring Chatbot Plugin",
    description=(
        "Chatbot-based AI module for predicting productivity declines and guiding "
        "employees and managers with actionable recommendations."
    ),
    version="1.0.0",
)

# Allow the React dev server to call this API from a different origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Dependency wiring (can be overridden by the host system) ---

_repo = InMemoryEvaluationRepository()

# For demo purposes we default to console logging. To test real emails,
# change this line locally to use SmtpEmailSender() and fill in the
# dummy credentials in SmtpEmailSender.
_email_sender: EmailSender = SmtpEmailSender()
_csv_output_dir = Path(__file__).resolve().parent.parent / "tmp_csv_outputs"
_csv_output_dir.mkdir(parents=True, exist_ok=True)


def get_repo() -> InMemoryEvaluationRepository:
    return _repo


def get_email_sender() -> EmailSender:
    return _email_sender


# --- API Endpoints ---


@app.post(
    "/evaluate",
    response_model=EvaluationResult,
    summary="Evaluate employee productivity risk",
)
def evaluate_employee(
    payload: EmployeeKPIInput,
    repo: InMemoryEvaluationRepository = Depends(get_repo),
    email_sender: EmailSender = Depends(get_email_sender),
) -> EvaluationResult:
    """
    Entry point for the host system to evaluate an employee.

    Workflow:
    - Accept raw KPI data.
    - Preprocess via preprocessing_pipeline.engineer_features.
    - Run model prediction.
    - Build chatbot explanation and recommendations.
    - Persist evaluation and send email notifications to employee and manager.
    """
    pipeline = get_model_pipeline()
    raw_record = payload.to_raw_record()
    prediction = pipeline.predict(raw_record)

    summary = build_evaluation_summary(
        label=prediction["label"],
        proba_decline=prediction["proba_decline"],
        features=prediction["features"],
    )

    evaluation_id = repo.generate_id()
    evaluation = EvaluationResult(
        evaluation_id=evaluation_id,
        employee_id=payload.employee_id,
        manager_id=payload.manager_id,
        summary=summary,
        raw_features=prediction["features"],
        model_output={
            "label": prediction["label"],
            "proba_decline": prediction["proba_decline"],
        },
    )
    repo.create_evaluation(evaluation)

    # Build email notifications
    employee_email = EmailNotification(
        to=payload.employee_email,
        subject="Productivity Insight and Recommended Actions",
        body=_build_employee_email_body(payload, evaluation),
    )
    manager_email = EmailNotification(
        to=payload.manager_email,
        subject="Manager Review Required: Productivity Insight",
        body=_build_manager_email_body(payload, evaluation),
    )
    email_sender.send_bulk([employee_email, manager_email])

    return evaluation


@app.post(
    "/evaluate/csv",
    response_model=CsvBatchEvaluationResponse,
    summary="Batch evaluate employees from CSV",
)
async def evaluate_employees_csv(
    file: UploadFile = File(...),
    repo: InMemoryEvaluationRepository = Depends(get_repo),
    email_sender: EmailSender = Depends(get_email_sender),
) -> CsvBatchEvaluationResponse:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please upload a CSV file.",
        )

    raw_bytes = await file.read()
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV must be UTF-8 encoded.",
        ) from exc

    reader = csv.DictReader(io.StringIO(text))
    rows_in = list(reader)
    if not rows_in:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV is empty.",
        )

    required_cols = {"employee_id", "employee_email", "manager_id", "manager_email"}
    missing_cols = required_cols - set(reader.fieldnames or [])
    if missing_cols:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV missing required columns: {', '.join(sorted(missing_cols))}",
        )

    job_id = str(uuid.uuid4())
    result_rows: List[CsvRowEvaluationResult] = []
    augmented_rows: List[Dict[str, Any]] = []

    successful_rows = 0
    failed_rows = 0
    pipeline = get_model_pipeline()

    for idx, csv_row in enumerate(rows_in, start=1):
        employee_id = str(csv_row.get("employee_id", "")).strip()
        row_augmented: Dict[str, Any] = dict(csv_row)
        try:
            payload = EmployeeKPIInput(**csv_row)
            raw_record = payload.to_raw_record()
            prediction = pipeline.predict(raw_record)
            summary = build_evaluation_summary(
                label=prediction["label"],
                proba_decline=prediction["proba_decline"],
                features=prediction["features"],
            )

            evaluation_id = repo.generate_id()
            evaluation = EvaluationResult(
                evaluation_id=evaluation_id,
                employee_id=payload.employee_id,
                manager_id=payload.manager_id,
                summary=summary,
                raw_features=prediction["features"],
                model_output={
                    "label": prediction["label"],
                    "proba_decline": prediction["proba_decline"],
                },
            )
            repo.create_evaluation(evaluation)

            employee_email = EmailNotification(
                to=payload.employee_email,
                subject="Productivity Insight and Recommended Actions",
                body=_build_employee_email_body(payload, evaluation),
            )
            manager_email = EmailNotification(
                to=payload.manager_email,
                subject="Manager Review Required: Productivity Insight",
                body=_build_manager_email_body(payload, evaluation),
            )
            email_sender.send_bulk([employee_email, manager_email])

            recommendations = [r.description for r in summary.recommendations]
            decline_probability = summary.confidence
            will_decline = summary.label.value == "decline_risk"
            result_rows.append(
                CsvRowEvaluationResult(
                    row_index=idx,
                    employee_id=payload.employee_id,
                    will_decline=will_decline,
                    decline_probability=decline_probability,
                    recommended_actions=recommendations,
                    status="success",
                )
            )
            row_augmented["will_decline"] = str(will_decline).lower()
            row_augmented["decline_probability"] = (
                "" if decline_probability is None else f"{decline_probability:.6f}"
            )
            row_augmented["recommended_actions"] = " ; ".join(recommendations)
            row_augmented["status"] = "success"
            row_augmented["error"] = ""
            successful_rows += 1
        except Exception as exc:
            err_msg = str(exc)
            result_rows.append(
                CsvRowEvaluationResult(
                    row_index=idx,
                    employee_id=employee_id or f"row_{idx}",
                    will_decline=None,
                    decline_probability=None,
                    recommended_actions=[],
                    status="error",
                    error=err_msg,
                )
            )
            row_augmented["will_decline"] = ""
            row_augmented["decline_probability"] = ""
            row_augmented["recommended_actions"] = ""
            row_augmented["status"] = "error"
            row_augmented["error"] = err_msg
            failed_rows += 1

        augmented_rows.append(row_augmented)

    output_path = _csv_output_dir / f"{job_id}.csv"
    output_fieldnames: List[str] = []
    for r in augmented_rows:
        for k in r.keys():
            if k not in output_fieldnames:
                output_fieldnames.append(k)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=output_fieldnames)
        writer.writeheader()
        writer.writerows(augmented_rows)

    return CsvBatchEvaluationResponse(
        job_id=job_id,
        total_rows=len(rows_in),
        successful_rows=successful_rows,
        failed_rows=failed_rows,
        rows=result_rows,
        download_url=f"/evaluate/csv/{job_id}/download",
    )


@app.get(
    "/evaluate/csv/{job_id}/download",
    summary="Download augmented CSV result",
)
def download_evaluated_csv(job_id: str) -> FileResponse:
    csv_path = _csv_output_dir / f"{job_id}.csv"
    if not csv_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CSV result not found for this job id.",
        )
    return FileResponse(
        path=csv_path,
        media_type="text/csv",
        filename=f"evaluated_{job_id}.csv",
    )


@app.post(
    "/manager/review",
    summary="Submit manager review decision",
)
def submit_manager_review(
    request: ManagerReviewRequest,
    repo: InMemoryEvaluationRepository = Depends(get_repo),
    email_sender: EmailSender = Depends(get_email_sender),
) -> dict:
    """
    Allows a manager to approve, reject, or modify recommendations.
    """
    record = repo.get_evaluation(request.evaluation_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation not found.",
        )

    base_recs = record.evaluation.summary.recommendations

    if request.decision == ManagerDecision.MODIFY:
        if not request.modified_recommendations:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="modified_recommendations must be provided when decision is 'modify'.",
            )
        final_recs = request.modified_recommendations
    elif request.decision == ManagerDecision.REJECT:
        # Manager rejects the proposed plan; send no recommendations.
        final_recs = []
    else:
        # APPROVE – keep the original recommendations.
        final_recs = list(base_recs)

    review = repo.save_manager_review(
        evaluation_id=request.evaluation_id,
        manager_id=request.manager_id,
        final_recommendations=final_recs,
        decision=request.decision,
        manager_comment=request.manager_comment,
    )

    # Notify employee if recommendations changed or confirmed
    employee_email = EmailNotification(
        to=record.evaluation.employee_id,  # Host system can map to email if needed
        subject="Updated Productivity Support Plan",
        body=_build_employee_post_review_email_body(record.evaluation, review),
    )
    email_sender.send_email(employee_email)

    return {"status": "ok", "review": review.model_dump()}


@app.post(
    "/employee/feedback",
    summary="Capture employee explanation for predicted decline",
)
def submit_employee_feedback(
    request: EmployeeFeedbackRequest,
    repo: InMemoryEvaluationRepository = Depends(get_repo),
) -> dict:
    record = repo.get_evaluation(request.evaluation_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation not found.",
        )

    feedback = EmployeeFeedbackRecord(
        evaluation_id=request.evaluation_id,
        employee_id=request.employee_id,
        primary_reason=request.primary_reason,
        free_text_explanation=request.free_text_explanation,
    )
    repo.save_employee_feedback(feedback)

    return {"status": "ok", "feedback": feedback.model_dump()}


@app.get(
    "/evaluations/{evaluation_id}",
    summary="Retrieve full evaluation trace for auditing",
)
def get_evaluation_trace(
    evaluation_id: str,
    repo: InMemoryEvaluationRepository = Depends(get_repo),
) -> dict:
    record = repo.get_evaluation(evaluation_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation not found.",
        )

    return {
        "evaluation": record.evaluation.model_dump(),
        "manager_review": record.manager_review.model_dump()
        if record.manager_review
        else None,
        "employee_feedback": record.employee_feedback.model_dump()
        if record.employee_feedback
        else None,
    }


# --- Email content helpers ---


def _build_employee_email_body(
    payload: EmployeeKPIInput, evaluation: EvaluationResult
) -> str:
    s = evaluation.summary
    lines: List[str] = []
    lines.append(f"Employee ID: {evaluation.employee_id}")
    lines.append("")
    lines.append("Summary of analysis")
    lines.append("-------------------")
    lines.append(f"Result: {s.label_human_readable}")
    if s.confidence is not None:
        lines.append(f"Model confidence (decline risk): {s.confidence:.2f}")
    lines.append("")
    lines.append(s.explanation)
    lines.append("")
    if s.weak_areas:
        lines.append("Potential focus areas:")
        for area in s.weak_areas:
            lines.append(f"- {area}")
        lines.append("")
    if s.recommendations:
        lines.append("Initial recommended actions:")
        for r in s.recommendations:
            lines.append(f"- [{r.area}] {r.description}")
        lines.append("")
    lines.append(
        "These insights are provided as decision support and do not replace "
        "direct conversation with your manager."
    )
    return "\n".join(lines)


def _build_manager_email_body(
    payload: EmployeeKPIInput, evaluation: EvaluationResult
) -> str:
    s = evaluation.summary
    lines: List[str] = []
    lines.append(f"Employee ID: {evaluation.employee_id}")
    lines.append(f"Manager ID: {evaluation.manager_id}")
    lines.append("")
    lines.append("AI productivity insight")
    lines.append("----------------------")
    lines.append(f"Result: {s.label_human_readable}")
    if s.confidence is not None:
        lines.append(f"Model confidence (decline risk): {s.confidence:.2f}")
    lines.append("")
    lines.append(s.explanation)
    lines.append("")
    if s.weak_areas:
        lines.append("Potential weak areas identified:")
        for area in s.weak_areas:
            lines.append(f"- {area}")
        lines.append("")
    if s.recommendations:
        lines.append("Proposed recommended actions:")
        for r in s.recommendations:
            lines.append(f"- [{r.area}] {r.description}")
        lines.append("")
    lines.append(
        "Please review these recommendations in the manager interface and either "
        "approve them, modify them, or reject them. Your decision will be shared "
        "with the employee."
    )
    return "\n".join(lines)


def _build_employee_post_review_email_body(
    evaluation: EvaluationResult, review
) -> str:
    lines: List[str] = []
    lines.append(f"Employee ID: {evaluation.employee_id}")
    lines.append("")
    lines.append("Updated productivity support plan")
    lines.append("---------------------------------")
    if review.decision == ManagerDecision.REJECT:
        lines.append(
            "Your manager has reviewed the AI-generated recommendations and decided "
            "not to apply them in their current form. They may follow up with you "
            "directly to discuss an alternative approach."
        )
    else:
        lines.append(
            "Your manager has reviewed the AI-generated recommendations and confirmed "
            "the following actions as your current support plan."
        )
        lines.append("")
        if review.final_recommendations:
            lines.append("Agreed actions:")
            for r in review.final_recommendations:
                lines.append(f"- [{r.area}] {r.description}")
            lines.append("")
    if review.manager_comment:
        lines.append("Manager comment:")
        lines.append(review.manager_comment)
        lines.append("")
    lines.append(
        "If you are experiencing challenges such as workload pressure, unclear tasks, "
        "technical blockers, personal circumstances, or insufficient training, please "
        "share this information using the feedback option or in your next 1:1."
    )
    return "\n".join(lines)

