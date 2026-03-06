# analysis_ai_pipeline

## Pipeline Trace
1. User input received via REST (`/v1/interactions/message`) or WS (`/ws`).
2. Session/user continuity ensured (`application/session_workflows.py`).
3. Intent classified (rules-first, optional LLM).
4. Context built (session/cart/preferences/recent interactions).
5. Actions extracted and agent routed.
6. Optional planner generates action plan with confidence and mode controls.
7. Agent(s) execute via services.
8. Interaction persisted; memory recorded async for authenticated users.
9. Response formatted and emitted (with stream envelopes for WS).

## Validation Controls
- Unknown intent handling mode (`clarify` or `fallback`).
- Planner canary and confidence floor.
- Max actions per request clamp.
- Atomic vs partial planner execution mode.

## Hallucination Defense Evidence
- Planned actions are sanitized against allow-listed action names and allowed params in `infrastructure/llm_client.py`.
- Unsupported planner actions are dropped and tracked.

## Cross-Review
- AI Orchestration Engineer: PASS.
- Prompt Engineer: PASS with recommendation to keep strict JSON schema constraints in prompts.
