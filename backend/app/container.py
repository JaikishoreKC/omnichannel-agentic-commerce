from __future__ import annotations

from app.core.config import Settings
from app.agents.cart_agent import CartAgent
from app.agents.order_agent import OrderAgent
from app.agents.product_agent import ProductAgent
from app.agents.support_agent import SupportAgent
from app.orchestrator.action_extractor import ActionExtractor
from app.orchestrator.agent_router import AgentRouter
from app.orchestrator.context_builder import ContextBuilder
from app.orchestrator.intent_classifier import IntentClassifier
from app.orchestrator.orchestrator_core import Orchestrator
from app.orchestrator.response_formatter import ResponseFormatter
from app.infrastructure.persistence_clients import MongoClientManager, RedisClientManager
from app.infrastructure.observability import MetricsCollector
from app.infrastructure.rate_limiter import SlidingWindowRateLimiter
from app.infrastructure.state_persistence import StatePersistence
from app.repositories.session_repository import SessionRepository
from app.services.admin_service import AdminService
from app.services.auth_service import AuthService
from app.services.cart_service import CartService
from app.services.inventory_service import InventoryService
from app.services.interaction_service import InteractionService
from app.services.memory_service import MemoryService
from app.services.notification_service import NotificationService
from app.services.order_service import OrderService
from app.services.payment_service import PaymentService
from app.services.product_service import ProductService
from app.services.session_service import SessionService
from app.services.support_service import SupportService
from app.store.in_memory import InMemoryStore

settings = Settings.from_env()
store = InMemoryStore()
mongo_manager = MongoClientManager(uri=settings.mongodb_uri, enabled=settings.enable_external_services)
redis_manager = RedisClientManager(url=settings.redis_url, enabled=settings.enable_external_services)
mongo_manager.connect()
redis_manager.connect()
rate_limiter = SlidingWindowRateLimiter()
metrics_collector = MetricsCollector()
state_persistence = StatePersistence(
    mongo_manager=mongo_manager,
    redis_manager=redis_manager,
)
state_persistence.load(store)

auth_service = AuthService(store=store, settings=settings)
product_service = ProductService(store=store)
session_repository = SessionRepository(
    store=store,
    mongo_manager=mongo_manager,
    redis_manager=redis_manager,
)
session_service = SessionService(store=store, session_repository=session_repository)
cart_service = CartService(store=store, settings=settings)
inventory_service = InventoryService(store=store)
payment_service = PaymentService(store=store)
notification_service = NotificationService(store=store)
order_service = OrderService(
    store=store,
    cart_service=cart_service,
    inventory_service=inventory_service,
    payment_service=payment_service,
    notification_service=notification_service,
)
memory_service = MemoryService(store=store)
admin_service = AdminService(store=store)
interaction_service = InteractionService(store=store)
support_service = SupportService(store=store)

product_agent = ProductAgent(product_service=product_service)
cart_agent = CartAgent(cart_service=cart_service)
order_agent = OrderAgent(order_service=order_service)
support_agent = SupportAgent(support_service=support_service)

orchestrator = Orchestrator(
    intent_classifier=IntentClassifier(),
    context_builder=ContextBuilder(
        session_service=session_service,
        cart_service=cart_service,
        memory_service=memory_service,
    ),
    action_extractor=ActionExtractor(),
    router=AgentRouter(),
    formatter=ResponseFormatter(),
    interaction_service=interaction_service,
    memory_service=memory_service,
    agents={
        product_agent.name: product_agent,
        cart_agent.name: cart_agent,
        order_agent.name: order_agent,
        support_agent.name: support_agent,
    },
)
