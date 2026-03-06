# analysis_conversational_flows

## Product Discovery
- User asks for products -> product intent -> product agent returns ranked items + suggested actions.
- Supports filter hints (price, color, size, brand) from intent entities.

## Progressive Narrowing
- Classifier supports follow-up refinements (price, style, search context).
- Chat suggested actions provide guided next utterances.

## Clarification Boundaries
- Variant ambiguity in cart add path returns clarification with top options.
- Unknown intent clarify mode supported by orchestrator setting.

## Example Flow Validation
- `show me running shoes` -> product list response path exists.
- `add option 1` style flows rely on suggestion utterance mapping in frontend `ChatContext`.

## Cross-Review
- Conversational UX Architect: PASS with mild recommendation to expand explicit comparative dialogue templates.
- AI Orchestration Engineer: PASS.
