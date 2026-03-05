from __future__ import annotations
from typing import AsyncIterator
from app.agents.base_agent import BaseAgent
from app.orchestrator.types import AgentAction, AgentContext, AgentExecutionResult
from app.infrastructure.llm_client import LLMClient

class GeneralAgent(BaseAgent):
    name = "general"
    _FALLBACK_MESSAGE = "I'm sorry, I couldn't provide a detailed answer at the moment."

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client

    def execute(self, action: AgentAction, context: AgentContext) -> AgentExecutionResult:
        _ = context
        # Call the LLM for non-streaming requests
        query = str(action.params.get("query", "")).strip()
        if not query:
            # Fallback: try to get from action entities which may contain the message
            query = str(action.params.get("message", "")).strip()
        if not query:
            return AgentExecutionResult(
                success=True,
                message=self._FALLBACK_MESSAGE,
                data={},
            )
        
        system_prompt = (
            "You are a helpful commerce assistant for an Omnichannel Brand. "
            "Answer questions about products, orders, or general shopping advice. "
            "Keep it concise and friendly. "
            'Respond in JSON format: {"message": "your answer here"}'
        )
        
        response = self.llm_client.generate_response(
            user_prompt=query,
            system_prompt=system_prompt
        )
        if response:
            return AgentExecutionResult(
                success=True,
                message=response,
                data={},
            )
        return AgentExecutionResult(
            success=True,
            message=self._FALLBACK_MESSAGE,
            data={},
        )

    async def execute_stream(self, action: AgentAction, context: AgentContext) -> AsyncIterator[str]:
        _ = context
        query = str(action.params.get("query", "")).strip()
        if not query:
            query = str(action.params.get("message", "")).strip()
        if not query:
            yield self._FALLBACK_MESSAGE
            return

        system_prompt = (
            "You are a helpful commerce assistant for an Omnichannel Brand. "
            "Answer questions about products, orders, or general shopping advice. "
            "Keep it concise and friendly. "
            'Respond in JSON format: {"message": "your answer here"}'
        )

        streamed_any_chunk = False
        try:
            async for chunk in self.llm_client.stream_response(
                user_prompt=query,
                system_prompt=system_prompt,
            ):
                if chunk:
                    streamed_any_chunk = True
                    yield chunk
        except (RuntimeError, ValueError):
            streamed_any_chunk = False

        if not streamed_any_chunk:
            yield self._FALLBACK_MESSAGE
