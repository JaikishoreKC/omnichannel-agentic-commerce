# analysis_prompt_engineering

## Prompt Assets
- `backend/app/infrastructure/prompts.py` contains planner/classifier prompts.
- General agent prompt in `backend/app/agents/general_agent.py` enforces concise commerce assistant behavior.

## Prompt Quality Findings
- Structured JSON response expectations are present for classification and planning.
- Planner output is post-validated by allow-list and parameter sanitization.
- General response path includes graceful fallback message if provider fails.

## Risk Notes
- Prompt text itself cannot fully prevent hallucinations; repo correctly combines prompt constraints with parser + allow-list enforcement.

## Cross-Review
- Prompt Engineer: PASS.
- Security Engineer: PASS (tool restriction through code-level validation, not prompt trust).
