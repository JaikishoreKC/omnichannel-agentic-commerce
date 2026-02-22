from __future__ import annotations

from app.repositories.interaction_repository import InteractionRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.support_repository import SupportRepository
from app.services.voice_recovery_service import VoiceRecoveryService
from app.store.in_memory import InMemoryStore


class AdminService:
    def __init__(
        self,
        store: InMemoryStore,
        session_repository: SessionRepository,
        order_repository: OrderRepository,
        interaction_repository: InteractionRepository,
        support_repository: SupportRepository,
        product_repository: ProductRepository,
        voice_recovery_service: VoiceRecoveryService,
    ) -> None:
        self.store = store
        self.session_repository = session_repository
        self.order_repository = order_repository
        self.interaction_repository = interaction_repository
        self.support_repository = support_repository
        self.product_repository = product_repository
        self.voice_recovery_service = voice_recovery_service

    def stats(self) -> dict[str, object]:
        today = self.store.utc_now().date().isoformat()
        active_sessions = self.session_repository.count()
        orders = self.order_repository.list_all()
        orders_today_rows = [order for order in orders if str(order.get("createdAt", "")).startswith(today)]
        orders_today = len(orders_today_rows)
        revenue_today = round(sum(float(order["total"]) for order in orders_today_rows), 2)
        product_names = self.product_repository.name_map()

        by_product: dict[str, dict[str, object]] = {}
        for order in orders:
            for item in order["items"]:
                product_id = item["productId"]
                product_name = product_names.get(product_id, "Unknown")
                row = by_product.setdefault(
                    product_id,
                    {"id": product_id, "name": product_name, "sold": 0},
                )
                row["sold"] = int(row["sold"]) + int(item["quantity"])

        top_products = sorted(by_product.values(), key=lambda item: int(item["sold"]), reverse=True)[:5]

        interactions = self.interaction_repository.list_by_date(date_prefix=today)
        by_agent: dict[str, dict[str, object]] = {}
        for record in interactions:
            agent = str(record.get("agent", "unknown"))
            row = by_agent.setdefault(
                agent,
                {"agent": agent, "interactions": 0, "successfulInteractions": 0},
            )
            row["interactions"] = int(row["interactions"]) + 1
            metadata = (record.get("response") or {}).get("metadata", {})
            if bool(metadata.get("success")):
                row["successfulInteractions"] = int(row["successfulInteractions"]) + 1

        agent_performance = []
        for row in by_agent.values():
            interactions_count = int(row["interactions"])
            success_count = int(row["successfulInteractions"])
            success_rate = round(
                (success_count / interactions_count) * 100 if interactions_count else 0.0,
                2,
            )
            agent_performance.append(
                {
                    "agent": row["agent"],
                    "interactions": interactions_count,
                    "successRate": success_rate,
                }
            )
        agent_performance.sort(key=lambda item: int(item["interactions"]), reverse=True)

        open_tickets = self.support_repository.list_open()
        voice_stats = self.voice_recovery_service.stats()
        return {
            "activeSessions": active_sessions,
            "ordersToday": orders_today,
            "revenueToday": revenue_today,
            "topProducts": top_products,
            "messagesToday": len(interactions),
            "supportOpenTickets": len(open_tickets),
            "agentPerformance": agent_performance,
            "voiceRecovery": voice_stats,
        }
