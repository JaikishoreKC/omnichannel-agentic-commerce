from __future__ import annotations

import asyncio
from typing import Any, cast

from app.agents.general_agent import GeneralAgent
from app.orchestrator.types import AgentAction, AgentContext


class _FakeLLMClient:
    def __init__(self, *, generated: str | None = None, stream_chunks: list[str] | None = None, stream_error: Exception | None = None) -> None:
        self._generated = generated
        self._stream_chunks = stream_chunks or []
        self._stream_error = stream_error

    def generate_response(self, *, user_prompt: str, system_prompt: str) -> str | None:
        _ = (user_prompt, system_prompt)
        return self._generated

    async def stream_response(self, *, user_prompt: str, system_prompt: str):
        _ = (user_prompt, system_prompt)
        if self._stream_error is not None:
            raise self._stream_error
        for chunk in self._stream_chunks:
            yield chunk


class _PartialThenErrorLLMClient:
    def generate_response(self, *, user_prompt: str, system_prompt: str) -> str | None:
        _ = (user_prompt, system_prompt)
        return None

    async def stream_response(self, *, user_prompt: str, system_prompt: str):
        _ = (user_prompt, system_prompt)
        yield "Hello"
        raise RuntimeError("stream interrupted")


def _context() -> AgentContext:
    return AgentContext(
        session_id="session_test",
        user_id=None,
        channel="web",
        session={},
        cart=None,
        preferences=None,
        memory=None,
        recent_messages=[],
    )


def test_execute_stream_yields_fallback_when_query_missing() -> None:
    agent = GeneralAgent(llm_client=cast(Any, _FakeLLMClient()))
    action = AgentAction(name="general_help", params={})

    chunks = asyncio.run(_collect_chunks(agent=agent, action=action))

    assert chunks == ["I'm sorry, I couldn't provide a detailed answer at the moment."]


def test_execute_stream_yields_llm_chunks_when_available() -> None:
    agent = GeneralAgent(llm_client=cast(Any, _FakeLLMClient(stream_chunks=["Hello", " world"])))
    action = AgentAction(name="general_help", params={"query": "help"})

    chunks = asyncio.run(_collect_chunks(agent=agent, action=action))

    assert chunks == ["Hello", " world"]


def test_execute_stream_falls_back_when_stream_raises() -> None:
    agent = GeneralAgent(llm_client=cast(Any, _FakeLLMClient(stream_error=RuntimeError("rate limited"))))
    action = AgentAction(name="general_help", params={"query": "help"})

    chunks = asyncio.run(_collect_chunks(agent=agent, action=action))

    assert chunks == ["I'm sorry, I couldn't provide a detailed answer at the moment."]


def test_execute_stream_falls_back_when_stream_empty() -> None:
    agent = GeneralAgent(llm_client=cast(Any, _FakeLLMClient(stream_chunks=[])))
    action = AgentAction(name="general_help", params={"query": "help"})

    chunks = asyncio.run(_collect_chunks(agent=agent, action=action))

    assert chunks == ["I'm sorry, I couldn't provide a detailed answer at the moment."]


def test_execute_stream_does_not_append_fallback_after_partial_output() -> None:
    agent = GeneralAgent(llm_client=cast(Any, _PartialThenErrorLLMClient()))
    action = AgentAction(name="general_help", params={"query": "help"})

    chunks = asyncio.run(_collect_chunks(agent=agent, action=action))

    assert chunks == ["Hello"]


async def _collect_chunks(*, agent: GeneralAgent, action: AgentAction) -> list[str]:
    output: list[str] = []
    async for chunk in agent.execute_stream(action=action, context=_context()):
        output.append(chunk)
    return output
