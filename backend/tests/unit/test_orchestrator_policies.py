from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from app.agents.base_agent import BaseAgent
from app.infrastructure.llm_client import LLMActionPlan
from app.orchestrator.orchestrator_core import Orchestrator
from app.orchestrator.types import AgentAction, AgentContext, AgentExecutionResult, AgentResponse, IntentResult
from app.orchestrator.response_formatter import ResponseFormatter


class _StubIntentClassifier:
    def __init__(self, result: IntentResult) -> None:
        self.result = result

    def classify(self, *, message: str, context: dict[str, Any] | None = None, allow_llm: bool = True) -> IntentResult:
        _ = (message, context, allow_llm)
        return self.result


class _StubContextBuilder:
    def __init__(self) -> None:
        self.session_service = SimpleNamespace(update_conversation=lambda **kwargs: None)

    def build(
        self,
        *,
        intent: IntentResult,
        session_id: str,
        user_id: str | None,
        channel: str,
        recent_messages: list[dict[str, Any]],
    ) -> AgentContext:
        _ = intent
        return AgentContext(
            session_id=session_id,
            user_id=user_id,
            channel=channel,
            session={},
            cart=None,
            preferences=None,
            memory=None,
            recent_messages=recent_messages,
        )


class _StubActionExtractor:
    def __init__(self, actions: list[AgentAction]) -> None:
        self.actions = actions

    def extract(self, intent: IntentResult) -> list[AgentAction]:
        _ = intent
        return list(self.actions)


class _StubRouter:
    def __init__(self, agent_name: str = "general") -> None:
        self.agent_name = agent_name

    def route(self, intent: IntentResult) -> str:
        _ = intent
        return self.agent_name


class _StubInteractionService:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def recent(self, *, session_id: str, limit: int) -> list[dict[str, Any]]:
        _ = (session_id, limit)
        return []

    def record(self, **kwargs: Any) -> None:
        self.records.append(kwargs)


class _StubMemoryService:
    def record_interaction(self, **kwargs: Any) -> None:
        _ = kwargs

    def get_history(self, *, user_id: str, limit: int) -> dict[str, Any]:
        _ = (user_id, limit)
        return {"history": []}


class _StubLLMClient:
    def __init__(self, **settings: Any) -> None:
        self.settings = SimpleNamespace(
            llm_decision_policy=settings.get("llm_decision_policy", "planner_first"),
            planner_feature_enabled=settings.get("planner_feature_enabled", False),
            llm_planner_enabled=settings.get("llm_planner_enabled", False),
            planner_canary_percent=settings.get("planner_canary_percent", 0),
            orchestrator_unknown_intent_mode=settings.get("orchestrator_unknown_intent_mode", "fallback"),
            chat_stream_non_general_enabled=settings.get("chat_stream_non_general_enabled", True),
            llm_planner_execution_mode=settings.get("llm_planner_execution_mode", "partial"),
            orchestrator_max_actions_per_request=settings.get("orchestrator_max_actions_per_request", 5),
        )

    def plan_actions(
        self,
        *,
        message: str,
        recent_messages: list[dict[str, Any]] | None = None,
        inferred_intent: str | None = None,
    ) -> LLMActionPlan | None:
        _ = (message, recent_messages, inferred_intent)
        return None


class _FixedAgent(BaseAgent):
    name = "fixed"

    def __init__(self, result: AgentExecutionResult) -> None:
        self.result = result

    def execute(self, action: AgentAction, context: AgentContext) -> AgentExecutionResult:
        _ = (action, context)
        return self.result


class _SequencedAgent(BaseAgent):
    name = "sequenced"

    def __init__(self, results: list[AgentExecutionResult]) -> None:
        self._results = list(results)

    def execute(self, action: AgentAction, context: AgentContext) -> AgentExecutionResult:
        _ = (action, context)
        if not self._results:
            raise RuntimeError("No more stubbed results")
        return self._results.pop(0)


def _build_orchestrator(
    *,
    intent: IntentResult,
    actions: list[AgentAction],
    agents: dict[str, BaseAgent],
    llm_settings: dict[str, Any] | None = None,
) -> Orchestrator:
    llm_client = _StubLLMClient(**(llm_settings or {}))
    return Orchestrator(
        intent_classifier=_StubIntentClassifier(intent),
        context_builder=_StubContextBuilder(),
        action_extractor=_StubActionExtractor(actions),
        router=_StubRouter(),
        formatter=ResponseFormatter(),
        llm_client=llm_client,
        interaction_service=_StubInteractionService(),
        memory_service=_StubMemoryService(),
        metrics_collector=None,
        agents=agents,
    )


def _context() -> AgentContext:
    return AgentContext(
        session_id="session_1",
        user_id="user_1",
        channel="web",
        session={},
        cart=None,
        preferences=None,
        memory=None,
        recent_messages=[],
    )


def test_unknown_intent_clarify_mode_returns_clarification() -> None:
    orchestrator = _build_orchestrator(
        intent=IntentResult(name="unknown_intent_x", confidence=0.4, entities={}),
        actions=[AgentAction(name="answer_question", params={}, target_agent="general")],
        agents={
            "general": _FixedAgent(
                AgentExecutionResult(success=True, message="handled", data={}, next_actions=[])
            )
        },
        llm_settings={"orchestrator_unknown_intent_mode": "clarify"},
    )

    payload = asyncio.run(
        orchestrator.process_message(
            message="do something unclear",
            session_id="session_1",
            user_id="user_1",
            channel="web",
        )
    )

    assert payload["agent"] == "orchestrator"
    assert payload["data"]["code"] == "UNKNOWN_INTENT"
    assert payload["metadata"]["intent"] == "unknown_intent_x"


def test_unknown_intent_fallback_mode_routes_through_agent() -> None:
    orchestrator = _build_orchestrator(
        intent=IntentResult(name="unknown_intent_x", confidence=0.4, entities={}),
        actions=[AgentAction(name="answer_question", params={}, target_agent="general")],
        agents={
            "general": _FixedAgent(
                AgentExecutionResult(success=True, message="handled by general", data={}, next_actions=[])
            )
        },
        llm_settings={"orchestrator_unknown_intent_mode": "fallback"},
    )

    payload = asyncio.run(
        orchestrator.process_message(
            message="do something unclear",
            session_id="session_1",
            user_id="user_1",
            channel="web",
        )
    )

    assert payload["agent"] == "general"
    assert payload["message"] == "handled by general"
    assert payload["metadata"]["intent"] == "unknown_intent_x"


def test_apply_action_limit_truncates_and_reports_count() -> None:
    orchestrator = _build_orchestrator(
        intent=IntentResult(name="multi_status", confidence=0.9, entities={}),
        actions=[],
        agents={"general": _FixedAgent(AgentExecutionResult(success=True, message="ok", data={}, next_actions=[]))},
    )

    actions = [AgentAction(name=f"action_{idx}", params={}, target_agent="general") for idx in range(1, 8)]
    bounded, truncated = orchestrator._apply_action_limit(actions=actions, limit=5)

    assert len(bounded) == 5
    assert truncated == 2


def test_execution_metadata_includes_truncated_action_count() -> None:
    orchestrator = _build_orchestrator(
        intent=IntentResult(name="multi_status", confidence=0.9, entities={}),
        actions=[],
        agents={"general": _FixedAgent(AgentExecutionResult(success=True, message="ok", data={}, next_actions=[]))},
    )

    response = AgentResponse(
        message="ok",
        agent="orchestrator",
        data={},
        suggested_actions=[],
        metadata={},
    )

    orchestrator._apply_execution_metadata(
        response=response,
        decision_policy="planner_first",
        planner_enabled_for_request=True,
        planner_attempted=False,
        action_limit=5,
        truncated_action_count=2,
        planner_plan=None,
        planner_used=False,
        planner_steps=[],
    )

    policy = response.metadata["executionPolicy"]
    assert policy["maxActions"] == 5
    assert policy["truncatedActionCount"] == 2


def test_planner_atomic_mode_stops_after_first_failure() -> None:
    orchestrator = _build_orchestrator(
        intent=IntentResult(name="multi_status", confidence=0.9, entities={}),
        actions=[],
        agents={
            "general": _SequencedAgent(
                [
                    AgentExecutionResult(success=True, message="step1 ok", data={"a": 1}, next_actions=[]),
                    AgentExecutionResult(success=False, message="step2 failed", data={"code": "STEP_FAIL"}, next_actions=[]),
                    AgentExecutionResult(success=True, message="step3 ok", data={"b": 2}, next_actions=[]),
                ]
            )
        },
        llm_settings={"llm_planner_execution_mode": "atomic"},
    )

    actions = [
        AgentAction(name="one", params={}, target_agent="general"),
        AgentAction(name="two", params={}, target_agent="general"),
        AgentAction(name="three", params={}, target_agent="general"),
    ]

    result, agent_name, steps = asyncio.run(
        orchestrator._execute_planned_actions(
            route_agent_name="general",
            actions=actions,
            context=_context(),
            intent_name="multi_status",
        )
    )

    assert agent_name == "orchestrator"
    assert result.success is False
    assert len(steps) == 3
    assert steps[1]["success"] is False
    assert steps[2]["error"]["code"] == "SKIPPED_ATOMIC_MODE"


def test_planner_partial_mode_continues_after_failure() -> None:
    orchestrator = _build_orchestrator(
        intent=IntentResult(name="multi_status", confidence=0.9, entities={}),
        actions=[],
        agents={
            "general": _SequencedAgent(
                [
                    AgentExecutionResult(success=True, message="step1 ok", data={"a": 1}, next_actions=[]),
                    AgentExecutionResult(success=False, message="step2 failed", data={"code": "STEP_FAIL"}, next_actions=[]),
                    AgentExecutionResult(success=True, message="step3 ok", data={"b": 2}, next_actions=[]),
                ]
            )
        },
        llm_settings={"llm_planner_execution_mode": "partial"},
    )

    actions = [
        AgentAction(name="one", params={}, target_agent="general"),
        AgentAction(name="two", params={}, target_agent="general"),
        AgentAction(name="three", params={}, target_agent="general"),
    ]

    result, _agent_name, steps = asyncio.run(
        orchestrator._execute_planned_actions(
            route_agent_name="general",
            actions=actions,
            context=_context(),
            intent_name="multi_status",
        )
    )

    assert result.success is True
    assert result.data.get("partialFailure") is True
    assert len(steps) == 3
    assert steps[2]["success"] is True
