## Proactive Productivity Monitoring Chatbot Plugin

This module implements a **chatbot-based AI plugin** for the thesis project:

**“Proactive Performance Monitoring: Predicting Productivity Declines with AI Analytics.”**

It is designed to be embedded into a larger platform and exposes a clean API around:

- **Employee productivity risk evaluation**
- **Natural-language chatbot explanations and recommendations**
- **Manager review and approval flow**
- **Employee follow‑up and explanation capture**
- **Email notification hooks** for employees and managers

The plugin uses:

- `preprocessing_pipeline.py` (provided) to convert raw KPI data to model features
- `productivity_model.pkl` (provided Random Forest model) to predict productivity decline

### High-level architecture

- `plugin/schemas.py` – Pydantic models for all inputs/outputs.
- `plugin/model_pipeline.py` – Loads the Random Forest model and runs the full preprocessing + prediction pipeline.
- `plugin/chatbot_logic.py` – Turns model outputs into human-readable explanations and recommendations.
- `plugin/email_service.py` – Abstract email interface + console implementation (easy to swap for SMTP/API).
- `plugin/repository.py` – In-memory store for evaluations, manager actions, and employee feedback (can be replaced by a DB).
- `plugin/api.py` – FastAPI app exposing HTTP endpoints for integration into a host platform.

### Assumptions

- The host system will:
  - Provide raw KPI records matching the original dataset fields used in `preprocessing_pipeline.py`.
  - Mount or copy `preprocessing_pipeline.py` and `productivity_model.pkl` into the same environment as this plugin.
  - Configure a real email sender by implementing `EmailSender` (if console logging is not sufficient).

### Running for demo

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Ensure `preprocessing_pipeline.py` and `productivity_model.pkl` are placed in the **project root** (same folder as this `README.md`).

3. Start the FastAPI app:

```bash
uvicorn plugin.api:app --reload
```

4. Use the OpenAPI docs at `http://localhost:8000/docs` to:

- Submit an evaluation (`POST /evaluate`)
- Submit CSV batch evaluation (`POST /evaluate/csv`)
- Download augmented CSV (`GET /evaluate/csv/{job_id}/download`)
- Submit manager review (`POST /manager/review`)
- Submit employee explanation (`POST /employee/feedback`)
- Retrieve stored evaluations (`GET /evaluations/{evaluation_id}`)

### CSV upload format (batch mode)

Use `POST /evaluate/csv` with a `.csv` file where each row is one employee.

Required identity columns:

- `employee_id`
- `employee_email`
- `manager_id`
- `manager_email`

Recommended KPI columns (same schema used by preprocessing):

- `date`
- `department`
- `team`
- `targeted_productivity`
- `actual_productivity`
- `smv`
- `wip`
- `over_time`
- `incentive`
- `idle_time`
- `idle_men`
- `no_of_style_change`
- `no_of_workers`

Batch response includes row-level results and a download URL for an
augmented CSV containing original columns plus:

- `decline_probability`
- `recommended_actions`
- `status`
- `error`

