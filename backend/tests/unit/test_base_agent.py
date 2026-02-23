from __future__ import annotations

import pytest

from app.agents.base_agent import BaseAgent
from app.orchestrator.types import AgentAction, AgentContext


class BrokenAgent(BaseAgent):
    name = "broken"

    def execute(self, action: AgentAction, context: AgentContext):
        return super().execute(action=action, context=context)


def test_base_agent_execute_raises_not_implemented() -> None:
    agent = BrokenAgent()
    action = AgentAction(name="noop")
    context = AgentContext(
        session_id="session_test",
        user_id=None,
        channel="web",
        session={},
        cart=None,
        preferences=None,
        memory=None,
        recent_messages=[],
    )

    with pytest.raises(NotImplementedError):
        agent.execute(action=action, context=context)
