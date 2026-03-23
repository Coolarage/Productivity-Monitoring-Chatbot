import pandas as pd
from typing import Dict, Any, List

# Features expected by the trained Random Forest model
MODEL_FEATURES: List[str] = [
    'planned_to_done_ratio',
    'absenteeism_rate',
    'output_quality_rate',
    'employee_utilization_rate',
    'engagement_score',
    'active_work_time_hours',
    'task_switching_frequency',
    'burnout_score',
    'job_satisfaction_score'
]

# Numeric columns cleaned in the notebook
NUMERIC_COLS: List[str] = [
    'targeted_productivity',
    'actual_productivity',
    'smv',
    'wip',
    'over_time',
    'incentive',
    'idle_time',
    'idle_men',
    'no_of_style_change',
    'no_of_workers'
]

# Medians taken from the cleaned training dataset.
# These are used when a raw input record has missing numeric values.
MEDIAN_DEFAULTS: Dict[str, float] = {
    'targeted_productivity': 0.75,
    'actual_productivity': 0.773333333,
    'smv': 26.16,
    'wip': 1039.0,
    'over_time': 3960.0,
    'incentive': 0.0,
    'idle_time': 0.0,
    'idle_men': 0.0,
    'no_of_style_change': 0.0,
    'no_of_workers': 57.0,
}

# Min/max values learned from the cleaned training dataset.
# They are needed because the notebook used dataset-level normalization.
NORMALIZATION_STATS: Dict[str, Dict[str, float]] = {
    'idle_time': {'min': 0.0, 'max': 300.0},
    'no_of_style_change': {'min': 0.0, 'max': 2.0},
    'actual_productivity': {'min': 0.233705476, 'max': 1.1204375},
    'incentive': {'min': 0.0, 'max': 3600.0},
    'over_time': {'min': 0.0, 'max': 25920.0},
}


def normalize_value(value: float, min_val: float, max_val: float) -> float:
    """Replicates the notebook normalization logic for a single value."""
    if pd.isna(value):
        return 0.0
    if max_val - min_val == 0:
        return 0.0
    return (float(value) - min_val) / (max_val - min_val)



def clean_raw_record(raw_record: Dict[str, Any]) -> Dict[str, Any]:
    """Apply the same record-level cleaning rules used in the notebook."""
    record = dict(raw_record)

    # 1) Clean department text
    if 'department' in record and record['department'] is not None:
        record['department'] = str(record['department']).strip().lower()
        if record['department'] == 'sweing':
            record['department'] = 'sewing'

    # 2) Parse date safely if present
    if 'date' in record and record['date'] not in (None, ''):
        parsed_date = pd.to_datetime(record['date'], errors='coerce', format='mixed')
        record['date'] = parsed_date if not pd.isna(parsed_date) else None

    # 3) Ensure numeric fields are numeric and fill missing with training medians
    for col in NUMERIC_COLS:
        value = pd.to_numeric(record.get(col), errors='coerce')
        if pd.isna(value):
            value = MEDIAN_DEFAULTS[col]
        record[col] = float(value)

    return record



def engineer_features(raw_record: Dict[str, Any]) -> pd.DataFrame:
    """
    Convert one raw employee record into the exact feature vector expected by the model.

    Important:
    - This mirrors the notebook logic used for the final 9 model features.
    - Features like productivity_trend_last_30_days were NOT used by the final model,
      so they are intentionally excluded here.
    """
    r = clean_raw_record(raw_record)

    targeted_productivity = max(r['targeted_productivity'], 1e-6)
    no_of_workers = max(r['no_of_workers'], 1e-6)

    # 1) planned_to_done_ratio
    planned_to_done_ratio = r['actual_productivity'] / targeted_productivity

    # 2) absenteeism_rate proxy
    scheduled_minutes = r['smv'] * no_of_workers
    if scheduled_minutes <= 0:
        absenteeism_rate = 0.0
    else:
        absenteeism_rate = r['idle_time'] / scheduled_minutes

    # 3) output_quality_rate proxy
    normalized_idle = normalize_value(
        r['idle_time'],
        NORMALIZATION_STATS['idle_time']['min'],
        NORMALIZATION_STATS['idle_time']['max'],
    )
    output_quality_rate = 1 - normalized_idle

    # 4) employee_utilization_rate
    regular_time = 480 * no_of_workers
    available_time = regular_time + r['over_time']
    productive_time = available_time - r['idle_time']
    if available_time <= 0:
        employee_utilization_rate = 0.0
    else:
        employee_utilization_rate = productive_time / available_time

    # 5) active_work_time_hours
    active_work_time_hours = (productive_time / 60) / no_of_workers

    # 6) task_switching_frequency
    task_switching_frequency = normalize_value(
        r['no_of_style_change'],
        NORMALIZATION_STATS['no_of_style_change']['min'],
        NORMALIZATION_STATS['no_of_style_change']['max'],
    )

    # 7) engagement_score
    norm_productivity = normalize_value(
        r['actual_productivity'],
        NORMALIZATION_STATS['actual_productivity']['min'],
        NORMALIZATION_STATS['actual_productivity']['max'],
    )
    norm_incentive = normalize_value(
        r['incentive'],
        NORMALIZATION_STATS['incentive']['min'],
        NORMALIZATION_STATS['incentive']['max'],
    )
    engagement_score = (
        0.5 * norm_productivity
        + 0.3 * (1 - normalized_idle)
        + 0.2 * norm_incentive
    )

    # 8) burnout_score
    norm_overtime = normalize_value(
        r['over_time'],
        NORMALIZATION_STATS['over_time']['min'],
        NORMALIZATION_STATS['over_time']['max'],
    )
    norm_style_change = task_switching_frequency
    burnout_score = (
        0.5 * norm_overtime
        + 0.3 * normalized_idle
        + 0.2 * norm_style_change
    )

    # 9) job_satisfaction_score
    job_satisfaction_score = (
        0.4 * norm_productivity
        + 0.3 * norm_incentive
        + 0.2 * (1 - normalized_idle)
        + 0.1 * (1 - norm_style_change)
    )

    # Match notebook clipping rules
    planned_to_done_ratio = min(max(planned_to_done_ratio, 0.0), 2.0)
    absenteeism_rate = min(max(absenteeism_rate, 0.0), 1.0)
    output_quality_rate = min(max(output_quality_rate, 0.0), 1.0)
    employee_utilization_rate = min(max(employee_utilization_rate, 0.0), 1.0)

    feature_row = {
        'planned_to_done_ratio': planned_to_done_ratio,
        'absenteeism_rate': absenteeism_rate,
        'output_quality_rate': output_quality_rate,
        'employee_utilization_rate': employee_utilization_rate,
        'engagement_score': engagement_score,
        'active_work_time_hours': active_work_time_hours,
        'task_switching_frequency': task_switching_frequency,
        'burnout_score': burnout_score,
        'job_satisfaction_score': job_satisfaction_score,
    }

    return pd.DataFrame([feature_row], columns=MODEL_FEATURES)


if __name__ == '__main__':
    # Example raw record similar to the original dataset schema
    example_raw_record = {
        'date': '2015-01-13',
        'department': 'sweing',
        'team': 8,
        'targeted_productivity': 0.8,
        'actual_productivity': 0.65,
        'smv': 26.16,
        'wip': 1100,
        'over_time': 4200,
        'incentive': 50,
        'idle_time': 30,
        'idle_men': 2,
        'no_of_style_change': 1,
        'no_of_workers': 57,
    }

    processed = engineer_features(example_raw_record)
    print(processed)
