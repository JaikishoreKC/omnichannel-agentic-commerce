from __future__ import annotations

from typing import Callable

from fastapi import HTTPException

from app.agents.base_agent import BaseAgent
from app.orchestrator.types import AgentAction, AgentContext, AgentExecutionResult
from app.services.order_service import OrderService


class OrderAgent(BaseAgent):
    name = "order"

    def __init__(self, order_service: OrderService) -> None:
        self.order_service = order_service
        self._handlers: dict[str, Callable[[AgentAction, AgentContext], AgentExecutionResult]] = {
            "checkout_summary": self._handle_checkout_summary,
            "get_order_status": self._handle_order_status,
            "cancel_order": self._handle_cancel_order,
            "request_refund": self._handle_request_refund,
            "change_order_address": self._handle_change_order_address,
        }

    def execute(self, action: AgentAction, context: AgentContext) -> AgentExecutionResult:
        handler = self._handlers.get(action.name)
        if handler is None:
            raise HTTPException(status_code=400, detail=f"Unsupported order action: {action.name}")
        return handler(action, context)

    def _handle_checkout_summary(self, action: AgentAction, context: AgentContext) -> AgentExecutionResult:
        user_id = context.user_id
        if not user_id:
            return AgentExecutionResult(
                success=False,
                message="Login required before order creation. Your cart is preserved.",
                data={"code": "AUTH_REQUIRED"},
                next_actions=[
                    {"label": "Login", "action": "auth:login"},
                    {"label": "View cart", "action": "view_cart"},
                ],
            )
        if not context.cart or context.cart["itemCount"] == 0:
            return AgentExecutionResult(
                success=False,
                message="Your cart is empty. Add products before checkout.",
                data={},
            )

        idempotency_key = f"{context.session_id}:{len(context.recent_messages)}"
        order = self.order_service.create_order(
            user_id=user_id,
            shipping_address={
                "name": "Default Customer",
                "line1": "123 Main St",
                "city": "Austin",
                "state": "TX",
                "postalCode": "78701",
                "country": "US",
            },
            payment_method={"type": "card", "token": "pm_chat_default"},
            idempotency_key=idempotency_key,
        )
        return AgentExecutionResult(
            success=True,
            message=f"Checkout complete. Order {order['id']} confirmed.",
            data={"order": order},
            next_actions=[
                {"label": "Track order", "action": f"order_status:{order['id']}"},
                {"label": "Continue shopping", "action": "search:more"},
            ],
        )

    def _handle_order_status(self, action: AgentAction, context: AgentContext) -> AgentExecutionResult:
        user_id = context.user_id
        if not user_id:
            return AgentExecutionResult(
                success=False,
                message="Please log in to view order status.",
                data={"code": "AUTH_REQUIRED"},
            )

        order_id = action.params.get("orderId")
        if order_id:
            order = self.order_service.get_order(user_id=user_id, order_id=str(order_id))
            return AgentExecutionResult(
                success=True,
                message=f"Order {order['id']} is currently {order['status']}.",
                data={"order": order},
            )

        orders = self.order_service.list_orders(user_id=user_id)["orders"]
        if not orders:
            return AgentExecutionResult(
                success=True,
                message="No orders found yet.",
                data={"orders": []},
            )
        latest = orders[0]
        return AgentExecutionResult(
            success=True,
            message=f"Latest order {latest['id']} is {latest['status']}.",
            data={"orders": orders[:5]},
            next_actions=[{"label": "Track latest order", "action": f"order_status:{latest['id']}"}],
        )

    def _handle_cancel_order(self, action: AgentAction, context: AgentContext) -> AgentExecutionResult:
        user_id = self._require_user(context, "Please log in to cancel orders.")
        if user_id is None:
            return AgentExecutionResult(
                success=False,
                message="Please log in to cancel orders.",
                data={"code": "AUTH_REQUIRED"},
            )

        order_id = action.params.get("orderId")
        if not order_id:
            order_id = self._latest_order_id(user_id=user_id)
            if not order_id:
                return AgentExecutionResult(
                    success=False,
                    message="You have no order to cancel.",
                    data={},
                )

        result = self.order_service.cancel_order(
            user_id=user_id,
            order_id=str(order_id),
            reason=action.params.get("reason"),
        )
        return AgentExecutionResult(
            success=True,
            message=f"Order {result['orderId']} has been cancelled.",
            data=result,
            next_actions=[{"label": "Continue shopping", "action": "search:more"}],
        )

    def _handle_request_refund(self, action: AgentAction, context: AgentContext) -> AgentExecutionResult:
        user_id = self._require_user(context, "Please log in to request refunds.")
        if user_id is None:
            return AgentExecutionResult(
                success=False,
                message="Please log in to request refunds.",
                data={"code": "AUTH_REQUIRED"},
            )

        order_id = action.params.get("orderId")
        if not order_id:
            order_id = self._latest_order_id(user_id=user_id)
            if not order_id:
                return AgentExecutionResult(
                    success=False,
                    message="You have no order available for refund.",
                    data={},
                )

        result = self.order_service.request_refund(
            user_id=user_id,
            order_id=str(order_id),
            reason=action.params.get("reason"),
        )
        return AgentExecutionResult(
            success=True,
            message=f"Refund request completed for order {result['orderId']}.",
            data=result,
            next_actions=[{"label": "Track order", "action": f"order_status:{result['orderId']}"}],
        )

    def _handle_change_order_address(self, action: AgentAction, context: AgentContext) -> AgentExecutionResult:
        user_id = self._require_user(context, "Please log in to change order addresses.")
        if user_id is None:
            return AgentExecutionResult(
                success=False,
                message="Please log in to change order addresses.",
                data={"code": "AUTH_REQUIRED"},
            )

        order_id = action.params.get("orderId")
        if not order_id:
            order_id = self._latest_order_id(user_id=user_id)
            if not order_id:
                return AgentExecutionResult(
                    success=False,
                    message="You have no order available for address updates.",
                    data={},
                )

        shipping_address = action.params.get("shippingAddress")
        if not isinstance(shipping_address, dict):
            return AgentExecutionResult(
                success=False,
                message=(
                    "I can update shipping on eligible orders. Provide fields like "
                    "line1=500 Main St, city=Austin, state=TX, postalCode=78701, country=US."
                ),
                data={"orderId": str(order_id)},
            )

        result = self.order_service.update_shipping_address(
            user_id=user_id,
            order_id=str(order_id),
            shipping_address=shipping_address,
        )
        return AgentExecutionResult(
            success=True,
            message=f"Updated shipping address for order {result['orderId']}.",
            data=result,
            next_actions=[{"label": "Track order", "action": f"order_status:{result['orderId']}"}],
        )

    @staticmethod
    def _require_user(context: AgentContext, message: str) -> str | None:
        if context.user_id:
            return context.user_id
        return None

    def _latest_order_id(self, *, user_id: str) -> str | None:
        orders = self.order_service.list_orders(user_id=user_id)["orders"]
        if not orders:
            return None
        return str(orders[0]["id"])
