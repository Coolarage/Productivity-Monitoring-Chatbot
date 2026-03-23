from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .schemas import EvaluationSummary, ProductivityLabel, RecommendationItem


def _infer_weak_areas(features: Dict[str, float]) -> List[str]:
    """
    Simple heuristic interpretation layer on top of engineered features.
    Uses realistic cutoffs to detect weaker areas.
    """
    weak_areas: List[str] = []

    if features.get("planned_to_done_ratio", 1.0) < 0.9:
        weak_areas.append("meeting planned productivity targets")
    if features.get("absenteeism_rate", 0.0) > 0.15:
        weak_areas.append("attendance and presence")
    if features.get("output_quality_rate", 1.0) < 0.8:
        weak_areas.append("output quality and rework")
    if features.get("employee_utilization_rate", 1.0) < 0.75:
        weak_areas.append("effective use of available time")
    if features.get("engagement_score", 1.0) < 0.5:
        weak_areas.append("engagement and motivation")
    if features.get("burnout_score", 0.0) > 0.6:
        weak_areas.append("workload balance and burnout risk")
    if features.get("job_satisfaction_score", 1.0) < 0.6:
        weak_areas.append("job satisfaction and sentiment")

    return weak_areas


def _build_recommendations(
    label: ProductivityLabel, features: Dict[str, float], weak_areas: List[str]
) -> List[RecommendationItem]:
    recs: List[RecommendationItem] = []

    if label == ProductivityLabel.NO_DECLINE:
        recs.append(
            RecommendationItem(
                area="recognition_and_continuity",
                description=(
                    "Maintain current working patterns and recognize recent positive "
                    "performance in 1:1s or team meetings to reinforce effective habits."
                ),
            )
        )
        recs.append(
            RecommendationItem(
                area="development_planning",
                description=(
                    "Discuss medium-term development goals with the employee and agree "
                    "on at least one skill-building activity over the next quarter."
                ),
            )
        )
        return recs

    # For decline risk, tailor recommendations by weak area
    for area in weak_areas or ["general_productivity"]:
        if "workload" in area or "burnout" in area:
            recs.append(
                RecommendationItem(
                    area="workload_balance",
                    description=(
                        "Review the employee's task load for the next 2–3 weeks and "
                        "rebalance high-intensity tasks across the team where possible. "
                        "Agree on clear priorities and de-prioritize non-critical work."
                    ),
                )
            )
            recs.append(
                RecommendationItem(
                    area="wellbeing_and_burnout_prevention",
                    description=(
                        "Schedule a short 1:1 check-in focused on wellbeing, confirm "
                        "breaks are being taken, and encourage the employee to flag any "
                        "early signs of fatigue or overload."
                    ),
                )
            )
        elif "attendance" in area:
            recs.append(
                RecommendationItem(
                    area="attendance_and_presence",
                    description=(
                        "Clarify attendance expectations, understand reasons behind recent "
                        "absences, and where appropriate agree on a support plan (e.g. "
                        "temporary flexibility, clearer handover processes)."
                    ),
                )
            )
        elif "quality" in area:
            recs.append(
                RecommendationItem(
                    area="training_and_quality",
                    description=(
                        "Pair the employee with an experienced colleague for a short "
                        "shadowing or review period focused on quality standards, and "
                        "provide timely feedback on a sample of recent work items."
                    ),
                )
            )
        elif "engagement" in area or "satisfaction" in area:
            recs.append(
                RecommendationItem(
                    area="engagement_and_coaching",
                    description=(
                        "Use the next 1:1 to explore what motivates the employee, which "
                        "tasks they find most meaningful, and identify one area where "
                        "their responsibilities can better align with their strengths."
                    ),
                )
            )
        elif "time" in area or "utilization" in area:
            recs.append(
                RecommendationItem(
                    area="time_management_and_prioritization",
                    description=(
                        "Review how the employee structures their day, remove unnecessary "
                        "meetings or administrative tasks, and agree on a simple daily "
                        "prioritization routine (e.g. top three outcomes per day)."
                    ),
                )
            )
        else:
            recs.append(
                RecommendationItem(
                    area="general_productivity_support",
                    description=(
                        "Hold a brief performance discussion to understand blockers, "
                        "clarify expectations, and agree on 2–3 specific, achievable "
                        "actions for the next two weeks."
                    ),
                )
            )

    # Add at least one recommendation for operational blockers and training
    recs.append(
        RecommendationItem(
            area="operational_blockers",
            description=(
                "Ask the employee to list any tools, approvals, or process issues that "
                "slow their work, and coordinate with relevant teams to resolve the top "
                "one or two items."
            ),
        )
    )
    recs.append(
        RecommendationItem(
            area="training_and_skill_development",
            description=(
                "Identify one targeted training opportunity (e.g. short course, "
                "guides, or peer coaching session) directly linked to the employee's "
                "current tasks."
            ),
        )
    )

    # De-duplicate by (area, description)
    unique: Dict[Tuple[str, str], RecommendationItem] = {}
    for r in recs:
        unique[(r.area, r.description)] = r
    return list(unique.values())


def build_evaluation_summary(
    label: ProductivityLabel, proba_decline: float | None, features: Dict[str, float]
) -> EvaluationSummary:
    weak_areas = _infer_weak_areas(features)
    recs = _build_recommendations(label, features, weak_areas)

    if label == ProductivityLabel.NO_DECLINE:
        label_text = "No productivity decline predicted"
        explanation = (
            "Based on the recent performance indicators, the system does not predict "
            "a near-term decline in productivity for this employee. Key indicators "
            "such as output quality, utilization, and engagement are within a "
            "healthy range. This insight should be used as decision support rather "
            "than a guarantee; ongoing observation and regular check-ins remain important."
        )
    else:
        label_text = "Elevated risk of productivity decline"
        explanation = (
            "Recent performance indicators suggest an increased risk of productivity "
            "decline. Factors such as workload balance, utilization of working time, "
            "and engagement may require additional attention. This is an analytical "
            "signal to support management judgment, not a definitive conclusion about "
            "the employee's performance."
        )

    return EvaluationSummary(
        label=label,
        label_human_readable=label_text,
        confidence=proba_decline,
        explanation=explanation,
        weak_areas=weak_areas,
        recommendations=recs,
    )

