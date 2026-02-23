from __future__ import annotations

import asyncio
import hashlib
from dataclasses import asdict
from typing import Any

from app.agents.base_agent import BaseAgent
from app.infrastructure.llm_client import LLMActionPlan, LLMClient
from app.orchestrator.action_extractor import ActionExtractor
from app.orchestrator.agent_router import AgentRouter
from app.orchestrator.context_builder import ContextBuilder
from app.orchestrator.intent_classifier import IntentClassifier
from app.orchestrator.response_formatter import ResponseFormatter
from app.orchestrator.types import AgentAction, AgentExecutionResult, AgentResponse
from app.services.interaction_service import InteractionService
from app.services.memory_service import MemoryService


class Orchestrator:
    def __init__(
        self,
        *,
        intent_classifier: IntentClassifier,
        context_builder: ContextBuilder,
        action_extractor: ActionExtractor,
        router: AgentRouter,
        formatter: ResponseFormatter,
        llm_client: LLMClient | None,
        interaction_service: InteractionService,
        memory_service: MemoryService,
        agents: dict[str, BaseAgent],
    ) -> None:
        self.intent_classifier = intent_classifier
        self.context_builder = context_builder
        self.action_extractor = action_extractor
        self.router = router
        self.formatter = formatter
        self.llm_client = llm_client
        self.interaction_service = interaction_service
        self.memory_service = memory_service
        self.agents = agents

    async def process_message(
        self,
        *,
        message: str,
        session_id: str,
        user_id: str | None,
        channel: str,
    ) -> dict[str, Any]:
        recent = self.interaction_service.recent(session_id=session_id, limit=12)
        if not recent and user_id:
            recent = self._recent_from_memory(user_id=user_id, limit=12)

        decision_policy = self._decision_policy()
        planner_enabled_for_request = self._planner_enabled_for_request(
            session_id=session_id,
            user_id=user_id,
        )
        allow_classifier_llm = decision_policy == "classifier_first" and not planner_enabled_for_request

        intent = self.intent_classifier.classify(
            message=message,
            context={"recent": recent},
            allow_llm=allow_classifier_llm,
        )
        context = self.context_builder.build(
            intent=intent,
            session_id=session_id,
            user_id=user_id,
            channel=channel,
            recent_messages=recent,
        )
        actions = self.action_extractor.extract(intent)
        route_agent_name = self.router.route(intent)

        planner_attempted = False
        planner_plan: LLMActionPlan | None = None
        should_try_planner = planner_enabled_for_request and (
            decision_policy == "planner_first" or len(actions) > 1
        )
        if should_try_planner:
            planner_attempted = True
            planner_plan = self._build_llm_action_plan(
                message=message,
                recent=recent,
                inferred_intent=intent.name,
            )

        planner_used = False
        planner_steps: list[dict[str, Any]] = []
        action_limit = self._max_actions_per_request()
        actions, truncated_action_count = self._apply_action_limit(actions=actions, limit=action_limit)

        if planner_plan and planner_plan.needs_clarification:
            planner_used = True
            planner_steps.append(
                {
                    "index": 1,
                    "action": "clarification",
                    "targetAgent": "orchestrator",
                    "success": False,
                    "message": planner_plan.clarification_question,
                }
            )
            result = AgentExecutionResult(
                success=False,
                message=planner_plan.clarification_question,
                data={"code": "CLARIFICATION_REQUIRED"},
                next_actions=[],
            )
            agent_name = "orchestrator"
        else:
            if planner_plan and planner_plan.actions:
                plan_actions = [
                    AgentAction(
                        name=action.name,
                        params=action.params,
                        target_agent=action.target_agent,
                    )
                    for action in planner_plan.actions
                ]
                actions, truncated_action_count = self._apply_action_limit(
                    actions=plan_actions,
                    limit=action_limit,
                )
                if actions:
                    route_agent_name = actions[0].target_agent or route_agent_name
                    planner_used = True

            if planner_used and actions:
                result, agent_name, planner_steps = await self._execute_planned_actions(
                    route_agent_name=route_agent_name,
                    actions=actions,
                    context=context,
                )
            elif len(actions) == 1:
                action = actions[0]
                agent_name = action.target_agent or route_agent_name
                agent = self.agents[agent_name]
                result = agent.execute(action=action, context=context)
            else:
                result, agent_name = await self._execute_multi_action(
                    route_agent_name=route_agent_name,
                    actions=actions,
                    context=context,
                    intent_name=intent.name,
                )

        response: AgentResponse = self.formatter.format(
            result=result,
            intent=intent,
            agent_name=agent_name,
        )
        response.metadata["executionPolicy"] = {
            "decisionPolicy": decision_policy,
            "plannerEnabled": planner_enabled_for_request,
            "plannerAttempted": planner_attempted,
            "mode": self._planner_execution_mode(),
            "maxActions": action_limit,
            "truncatedActionCount": truncated_action_count,
        }
        if planner_plan is not None:
            response.metadata["planner"] = {
                "used": planner_used,
                "confidence": planner_plan.confidence,
                "needsClarification": planner_plan.needs_clarification,
                "actionCount": len(planner_plan.actions),
                "executionMode": self._planner_execution_mode(),
                "stepCount": len(planner_steps),
                "steps": planner_steps,
            }
        elif planner_attempted:
            response.metadata["planner"] = {
                "used": False,
                "confidence": 0.0,
                "needsClarification": False,
                "actionCount": 0,
                "executionMode": self._planner_execution_mode(),
                "stepCount": 0,
                "steps": [],
            }
        payload = self._to_transport_payload(response)

        self.interaction_service.record(
            session_id=context.session_id,
            user_id=context.user_id,
            message=message,
            intent=intent.name,
            agent=agent_name,
            response=payload,
        )
        self.context_builder.session_service.update_conversation(
            session_id=context.session_id,
            last_intent=intent.name,
            last_agent=agent_name,
            last_message=message,
            entities=intent.entities,
        )
        asyncio.create_task(
            self._record_memory(
                user_id=context.user_id,
                intent=intent.name,
                message=message,
                response=payload,
            )
        )

        return payload

    async def _record_memory(
        self,
        *,
        user_id: str | None,
        intent: str,
        message: str,
        response: dict[str, Any],
    ) -> None:
        await asyncio.to_thread(
            self.memory_service.record_interaction,
            user_id=user_id,
            intent=intent,
            message=message,
            response=response,
        )

    def _build_llm_action_plan(
        self,
        *,
        message: str,
        recent: list[dict[str, Any]],
        inferred_intent: str,
    ) -> LLMActionPlan | None:
        if self.llm_client is None:
            return None
        try:
            return self.llm_client.plan_actions(
                message=message,
                recent_messages=recent,
                inferred_intent=inferred_intent,
            )
        except Exception:
            return None

    def _planner_execution_mode(self) -> str:
        if self.llm_client is None:
            return "partial"
        raw = str(self.llm_client.settings.llm_planner_execution_mode).strip().lower()
        if raw in {"strict", "atomic"}:
            return "atomic"
        if raw == "partial":
            return raw
        return "partial"

    def _decision_policy(self) -> str:
        if self.llm_client is None:
            return "planner_first"
        raw = str(self.llm_client.settings.llm_decision_policy).strip().lower()
        if raw in {"planner_first", "classifier_first"}:
            return raw
        return "planner_first"

    def _planner_enabled_for_request(self, *, session_id: str, user_id: str | None) -> bool:
        if self.llm_client is None:
            return False
        if not self.llm_client.settings.planner_feature_enabled:
            return False
        if not self.llm_client.settings.llm_planner_enabled:
            return False
        percent = int(self.llm_client.settings.planner_canary_percent)
        if percent <= 0:
            return False
        if percent >= 100:
            return True
        seed = f"{user_id or 'anonymous'}:{session_id}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        bucket = int(digest[:8], 16) % 100
        return bucket < percent

    def _max_actions_per_request(self) -> int:
        if self.llm_client is None:
            return 5
        configured = int(self.llm_client.settings.orchestrator_max_actions_per_request)
        return max(1, min(10, configured))

    def _apply_action_limit(self, *, actions: list[Any], limit: int) -> tuple[list[Any], int]:
        if len(actions) <= limit:
            return actions, 0
        return actions[:limit], len(actions) - limit

    async def _execute_planned_actions(
        self,
        *,
        route_agent_name: str,
        actions: list[Any],
        context: Any,
    ) -> tuple[AgentExecutionResult, str, list[dict[str, Any]]]:
        mode = self._planner_execution_mode()
        atomic = mode == "atomic"
        combined_data: dict[str, Any] = {}
        messages: list[str] = []
        suggested: list[dict[str, str]] = []
        steps: list[dict[str, Any]] = []
        any_success = False
        all_success = True

        for index, action in enumerate(actions, start=1):
            agent_name = action.target_agent or route_agent_name
            agent = self.agents[agent_name]
            result = await asyncio.to_thread(agent.execute, action, context)

            if agent_name in combined_data:
                existing = combined_data[agent_name]
                if isinstance(existing, list):
                    existing.append(result.data)
                    combined_data[agent_name] = existing
                else:
                    combined_data[agent_name] = [existing, result.data]
            else:
                combined_data[agent_name] = result.data

            messages.append(result.message)
            suggested.extend(result.next_actions)
            any_success = any_success or result.success
            all_success = all_success and result.success
            error: dict[str, Any] | None = None
            if not result.success:
                code = "ACTION_FAILED"
                if isinstance(result.data, dict):
                    raw_code = str(result.data.get("code", "")).strip()
                    if raw_code:
                        code = raw_code
                error = {"code": code, "message": result.message}
            steps.append(
                {
                    "index": index,
                    "action": action.name,
                    "targetAgent": agent_name,
                    "success": result.success,
                    "message": result.message,
                    "error": error,
                }
            )

            if atomic and not result.success:
                for skipped_index, skipped in enumerate(actions[index:], start=index + 1):
                    steps.append(
                        {
                            "index": skipped_index,
                            "action": skipped.name,
                            "targetAgent": skipped.target_agent or route_agent_name,
                            "success": False,
                            "message": "Skipped due to previous failure in atomic mode.",
                            "error": {
                                "code": "SKIPPED_ATOMIC_MODE",
                                "message": "Skipped due to previous failure in atomic mode.",
                            },
                        }
                    )
                break

        overall_success = all_success if atomic else any_success
        if not messages:
            messages = ["I couldn't execute the requested action plan."]
        if not all_success and not atomic:
            combined_data["partialFailure"] = True

        return (
            AgentExecutionResult(
                success=overall_success,
                message=" ".join(messages),
                data=combined_data,
                next_actions=suggested[:6],
            ),
            "orchestrator",
            steps,
        )

    async def _execute_multi_action(
        self,
        *,
        route_agent_name: str,
        actions: list[Any],
        context: Any,
        intent_name: str,
    ) -> tuple[AgentExecutionResult, str]:
        if intent_name == "search_and_add_to_cart":
            return await self._execute_search_add_sequence(
                route_agent_name=route_agent_name,
                actions=actions,
                context=context,
            )

        mode = self._planner_execution_mode()
        atomic = mode == "atomic"

        if atomic:
            combined_data: dict[str, Any] = {}
            messages: list[str] = []
            suggested: list[dict[str, str]] = []
            all_success = True
            for action in actions:
                agent_name = action.target_agent or route_agent_name
                agent = self.agents[agent_name]
                result = await asyncio.to_thread(agent.execute, action, context)
                combined_data[agent_name] = result.data
                messages.append(result.message)
                suggested.extend(result.next_actions)
                all_success = all_success and result.success
                if not result.success:
                    break
            return (
                AgentExecutionResult(
                    success=all_success,
                    message=" ".join(messages),
                    data=combined_data,
                    next_actions=suggested[:6],
                ),
                "orchestrator",
            )

        async def run_action(action: Any) -> tuple[str, AgentExecutionResult]:
            agent_name = action.target_agent or route_agent_name
            agent = self.agents[agent_name]
            result = await asyncio.to_thread(agent.execute, action, context)
            return agent_name, result

        pairs = await asyncio.gather(*(run_action(action) for action in actions))
        combined_data: dict[str, Any] = {}
        messages: list[str] = []
        suggested: list[dict[str, str]] = []
        success = True
        for agent_name, result in pairs:
            combined_data[agent_name] = result.data
            messages.append(result.message)
            suggested.extend(result.next_actions)
            success = success and result.success

        return (
            AgentExecutionResult(
                success=success,
                message=" ".join(messages),
                data=combined_data,
                next_actions=suggested[:6],
            ),
            "orchestrator",
        )

    async def _execute_search_add_sequence(
        self,
        *,
        route_agent_name: str,
        actions: list[Any],
        context: Any,
    ) -> tuple[AgentExecutionResult, str]:
        combined_data: dict[str, Any] = {}
        messages: list[str] = []
        suggested: list[dict[str, str]] = []
        success = True
        previous_result: AgentExecutionResult | None = None

        for action in actions:
            effective_action = action
            if action.name == "add_item":
                inferred = self._infer_product_selection(previous_result)
                enriched_params = {**action.params}
                if not enriched_params.get("productId") and inferred.get("productId"):
                    enriched_params["productId"] = inferred["productId"]
                if not enriched_params.get("variantId") and inferred.get("variantId"):
                    enriched_params["variantId"] = inferred["variantId"]
                if not enriched_params.get("quantity"):
                    enriched_params["quantity"] = 1
                effective_action = AgentAction(
                    name=action.name,
                    params=enriched_params,
                    target_agent=action.target_agent,
                )

            agent_name = effective_action.target_agent or route_agent_name
            agent = self.agents[agent_name]
            result = await asyncio.to_thread(agent.execute, effective_action, context)
            previous_result = result

            combined_data[agent_name] = result.data
            messages.append(result.message)
            suggested.extend(result.next_actions)
            success = success and result.success

        return (
            AgentExecutionResult(
                success=success,
                message=" ".join(messages),
                data=combined_data,
                next_actions=suggested[:6],
            ),
            "orchestrator",
        )

    def _infer_product_selection(
        self, result: AgentExecutionResult | None
    ) -> dict[str, str]:
        if result is None:
            return {}
        products = result.data.get("products")
        if not isinstance(products, list) or not products:
            return {}
        first = products[0]
        if not isinstance(first, dict):
            return {}
        variants = first.get("variants")
        if not isinstance(variants, list) or not variants:
            return {}
        first_variant = variants[0]
        if not isinstance(first_variant, dict):
            return {}
        product_id = str(first.get("id", "")).strip()
        variant_id = str(first_variant.get("id", "")).strip()
        if not product_id or not variant_id:
            return {}
        return {"productId": product_id, "variantId": variant_id}

    def _to_transport_payload(self, response: AgentResponse) -> dict[str, Any]:
        payload = asdict(response)
        return {
            "message": payload["message"],
            "agent": payload["agent"],
            "data": payload["data"],
            "suggestedActions": payload["suggested_actions"],
            "metadata": payload["metadata"],
        }

    def _recent_from_memory(self, *, user_id: str, limit: int) -> list[dict[str, Any]]:
        history = self.memory_service.get_history(user_id=user_id, limit=limit).get("history", [])
        if not isinstance(history, list):
            return []
        recovered: list[dict[str, Any]] = []
        for row in history:
            if not isinstance(row, dict):
                continue
            summary = row.get("summary", {})
            if not isinstance(summary, dict):
                continue
            query = str(summary.get("query", "")).strip()
            response_text = str(summary.get("response", "")).strip()
            if not query and not response_text:
                continue
            recovered.append(
                {
                    "id": f"memory_{len(recovered)+1}",
                    "sessionId": "memory",
                    "userId": user_id,
                    "message": query,
                    "intent": str(row.get("type", "")),
                    "agent": "memory",
                    "response": {"message": response_text, "agent": "memory"},
                    "timestamp": str(row.get("timestamp", "")),
                }
            )
        return recovered[-limit:]
