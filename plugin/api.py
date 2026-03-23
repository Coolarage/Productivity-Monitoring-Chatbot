from __future__ import annotations

import csv
from html import escape
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
        html_body=_build_employee_email_html(payload, evaluation),
    )
    manager_email = EmailNotification(
        to=payload.manager_email,
        subject="Manager Review Required: Productivity Insight",
        body=_build_manager_email_body(payload, evaluation),
        html_body=_build_manager_email_html(payload, evaluation),
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
                html_body=_build_employee_email_html(payload, evaluation),
            )
            manager_email = EmailNotification(
                to=payload.manager_email,
                subject="Manager Review Required: Productivity Insight",
                body=_build_manager_email_body(payload, evaluation),
                html_body=_build_manager_email_html(payload, evaluation),
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
        html_body=_build_employee_post_review_email_html(record.evaluation, review),
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


def _email_html_shell(title: str, subtitle: str, body_html: str) -> str:
    return f"""
<html>
  <body style="margin:0;padding:0;background:#eef2ff;font-family:'Segoe UI',Arial,Helvetica,sans-serif;color:#1f2937;">
    <div style="max-width:860px;margin:24px auto;padding:0 14px;">
      <div style="background:linear-gradient(135deg,#0f766e,#0ea5e9);border-radius:16px 16px 0 0;padding:24px 26px;color:#ffffff;box-shadow:0 8px 24px rgba(15,118,110,0.25);">
        <div style="font-size:12px;letter-spacing:0.6px;text-transform:uppercase;opacity:0.9;">AI Productivity Monitor</div>
        <h1 style="margin:8px 0 4px;font-size:24px;line-height:1.2;">{escape(title)}</h1>
        <p style="margin:0;font-size:14px;opacity:0.95;">{escape(subtitle)}</p>
      </div>
      <div style="background:#ffffff;border-radius:0 0 16px 16px;padding:24px 26px;border:1px solid #dbeafe;border-top:none;box-shadow:0 12px 28px rgba(15,23,42,0.08);">
        {body_html}
      </div>
      <div style="padding:12px 4px 0;color:#6b7280;font-size:12px;text-align:center;">
        This message was generated by the proactive productivity monitoring assistant.
      </div>
    </div>
  </body>
</html>
""".strip()


def _html_key_value_table(items: List[tuple[str, str]]) -> str:
    blocks = "".join(
        f"""
<div style="background:#f8fafc;border:1px solid #e5e7eb;border-radius:12px;padding:12px 14px;">
  <div style="font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:0.4px;">{escape(k)}</div>
  <div style="margin-top:6px;font-size:16px;font-weight:600;color:#0f172a;">{escape(v)}</div>
</div>
""".strip()
        for k, v in items
    )
    return f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin:8px 0 18px;">{blocks}</div>'


def _html_list(items: List[str]) -> str:
    if not items:
        return '<div style="padding:10px 12px;border:1px dashed #cbd5e1;border-radius:10px;color:#64748b;">No items.</div>'
    li = "".join(
        f'<li style="margin:0 0 10px;">'
        f'<div style="padding:10px 12px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;">{escape(i)}</div>'
        f"</li>"
        for i in items
    )
    return f'<ol style="margin:8px 0 0 20px;padding:0;">{li}</ol>'


def _build_employee_email_html(
    payload: EmployeeKPIInput, evaluation: EvaluationResult
) -> str:
    s = evaluation.summary
    recs = [f"[{r.area}] {r.description}" for r in s.recommendations]
    metrics = [
        ("Employee ID", evaluation.employee_id),
        ("Result", s.label_human_readable),
        (
            "Decline risk confidence",
            "-" if s.confidence is None else f"{s.confidence:.2f}",
        ),
    ]
    body = f"""
<div style="padding:14px 16px;background:#ecfeff;border:1px solid #99f6e4;border-radius:12px;margin-bottom:16px;">
  <strong style="color:#115e59;">Evaluation completed</strong>
  <div style="margin-top:6px;font-size:14px;color:#134e4a;">Your latest productivity indicators have been reviewed. Use this output as decision support.</div>
</div>
{_html_key_value_table(metrics)}
<div style="margin:0 0 14px;padding:14px 16px;border:1px solid #e5e7eb;border-radius:12px;">
  <h3 style="margin:0 0 8px;font-size:16px;color:#0f172a;">Explanation</h3>
  <p style="margin:0;font-size:14px;line-height:1.6;">{escape(s.explanation)}</p>
</div>
<h3 style="margin:0 0 6px;font-size:16px;color:#0f172a;">Potential focus areas</h3>
{_html_list(s.weak_areas)}
<h3 style="margin:18px 0 6px;font-size:16px;color:#0f172a;">Recommended actions</h3>
{_html_list(recs)}
<p style="margin:18px 0 0;font-size:12px;color:#6b7280;">These insights should be combined with manager judgment and regular 1:1 discussions.</p>
""".strip()
    return _email_html_shell(
        "Productivity Insight",
        "Employee notification",
        body,
    )


def _build_manager_email_html(
    payload: EmployeeKPIInput, evaluation: EvaluationResult
) -> str:
    s = evaluation.summary
    recs = [f"[{r.area}] {r.description}" for r in s.recommendations]
    metrics = [
        ("Employee ID", evaluation.employee_id),
        ("Manager ID", evaluation.manager_id),
        ("Result", s.label_human_readable),
        (
            "Decline risk confidence",
            "-" if s.confidence is None else f"{s.confidence:.2f}",
        ),
    ]
    body = f"""
<div style="padding:14px 16px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:12px;margin-bottom:16px;">
  <strong style="color:#1d4ed8;">Manager action requested</strong>
  <div style="margin-top:6px;font-size:14px;color:#1e3a8a;">An employee productivity evaluation is complete and awaits your review.</div>
</div>
{_html_key_value_table(metrics)}
<div style="margin:0 0 14px;padding:14px 16px;border:1px solid #e5e7eb;border-radius:12px;">
  <h3 style="margin:0 0 8px;font-size:16px;color:#0f172a;">Explanation</h3>
  <p style="margin:0;font-size:14px;line-height:1.6;">{escape(s.explanation)}</p>
</div>
<h3 style="margin:0 0 6px;font-size:16px;color:#0f172a;">Potential weak areas</h3>
{_html_list(s.weak_areas)}
<h3 style="margin:18px 0 6px;font-size:16px;color:#0f172a;">Proposed actions</h3>
{_html_list(recs)}
<p style="margin:18px 0 0;font-size:12px;color:#6b7280;">Please review and approve, modify, or reject these actions in the manager workflow.</p>
""".strip()
    return _email_html_shell(
        "Manager Review Required",
        "Productivity evaluation alert",
        body,
    )


def _build_employee_post_review_email_html(
    evaluation: EvaluationResult, review
) -> str:
    metrics = [
        ("Employee ID", evaluation.employee_id),
        ("Manager decision", str(review.decision)),
    ]
    approved_actions = [f"[{r.area}] {r.description}" for r in review.final_recommendations]
    if review.decision == ManagerDecision.REJECT:
        decision_html = (
            "<div style='padding:14px 16px;background:#fff1f2;border:1px solid #fecdd3;border-radius:12px;margin-bottom:16px;'>"
            "<strong style='color:#9f1239;'>Plan not approved</strong>"
            "<div style='margin-top:6px;font-size:14px;color:#881337;'>Your manager did not approve the suggested plan in its current form. A direct follow-up may be provided.</div>"
            "</div>"
        )
    else:
        decision_html = (
            "<div style='padding:14px 16px;background:#ecfeff;border:1px solid #99f6e4;border-radius:12px;margin-bottom:16px;'>"
            "<strong style='color:#115e59;'>Plan reviewed</strong>"
            "<div style='margin-top:6px;font-size:14px;color:#134e4a;'>Your manager reviewed the suggested plan and confirmed the actions below.</div>"
            "</div>"
        )
    comment_html = ""
    if review.manager_comment:
        comment_html = f"""
<div style="margin:14px 0 0;padding:14px 16px;border:1px solid #e5e7eb;border-radius:12px;background:#f8fafc;">
  <h3 style="margin:0 0 8px;font-size:16px;color:#0f172a;">Manager comment</h3>
  <p style="margin:0;font-size:14px;line-height:1.6;">{escape(review.manager_comment)}</p>
</div>
""".strip()
    body = f"""
{decision_html}
{_html_key_value_table(metrics)}
<h3 style="margin:0 0 6px;font-size:16px;color:#0f172a;">Final actions</h3>
{_html_list(approved_actions)}
{comment_html}
<p style="margin:18px 0 0;font-size:12px;color:#6b7280;">If you face workload pressure, blockers, unclear tasks, or training needs, please share this in your next check-in.</p>
""".strip()
    return _email_html_shell(
        "Updated Support Plan",
        "Manager decision update",
        body,
    )

