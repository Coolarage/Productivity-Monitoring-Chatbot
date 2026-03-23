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
- Submit manager review (`POST /manager/review`)
- Submit employee explanation (`POST /employee/feedback`)
- Retrieve stored evaluations (`GET /evaluations/{evaluation_id}`)

