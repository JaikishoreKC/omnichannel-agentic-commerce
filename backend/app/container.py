from __future__ import annotations

from app.core.config import Settings
from app.agents.cart_agent import CartAgent
from app.agents.memory_agent import MemoryAgent
from app.agents.order_agent import OrderAgent
from app.agents.product_agent import ProductAgent
from app.agents.support_agent import SupportAgent
from app.orchestrator.action_extractor import ActionExtractor
from app.orchestrator.agent_router import AgentRouter
from app.orchestrator.context_builder import ContextBuilder
from app.orchestrator.intent_classifier import IntentClassifier
from app.orchestrator.orchestrator_core import Orchestrator
from app.orchestrator.response_formatter import ResponseFormatter
from app.infrastructure.superu_client import SuperUClient
from app.infrastructure.persistence_clients import MongoClientManager, RedisClientManager
from app.infrastructure.observability import MetricsCollector
from app.infrastructure.llm_client import LLMClient
from app.infrastructure.rate_limiter import SlidingWindowRateLimiter
from app.infrastructure.state_persistence import StatePersistence
from app.repositories.auth_repository import AuthRepository
from app.repositories.cart_repository import CartRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.interaction_repository import InteractionRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.support_repository import SupportRepository
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
from app.services.voice_recovery_service import VoiceRecoveryService
from app.store.in_memory import InMemoryStore

settings = Settings.from_env()
store = InMemoryStore()
mongo_manager = MongoClientManager(uri=settings.mongodb_uri, enabled=settings.enable_external_services)
redis_manager = RedisClientManager(url=settings.redis_url, enabled=settings.enable_external_services)
mongo_manager.connect()
redis_manager.connect()
rate_limiter = SlidingWindowRateLimiter()
metrics_collector = MetricsCollector()
llm_client = LLMClient(settings=settings)
state_persistence = StatePersistence(
    mongo_manager=mongo_manager,
    redis_manager=redis_manager,
)
state_persistence.load(store)

auth_repository = AuthRepository(
    store=store,
    mongo_manager=mongo_manager,
    redis_manager=redis_manager,
)
auth_service = AuthService(
    store=store,
    settings=settings,
    auth_repository=auth_repository,
)
product_repository = ProductRepository(
    store=store,
    mongo_manager=mongo_manager,
    redis_manager=redis_manager,
)
inventory_repository = InventoryRepository(
    store=store,
    mongo_manager=mongo_manager,
    redis_manager=redis_manager,
)
notification_repository = NotificationRepository(
    store=store,
    mongo_manager=mongo_manager,
)
product_service = ProductService(
    store=store,
    product_repository=product_repository,
    inventory_repository=inventory_repository,
)
session_repository = SessionRepository(
    store=store,
    mongo_manager=mongo_manager,
    redis_manager=redis_manager,
)
session_service = SessionService(store=store, session_repository=session_repository)
cart_repository = CartRepository(
    store=store,
    mongo_manager=mongo_manager,
    redis_manager=redis_manager,
)
cart_service = CartService(
    store=store,
    settings=settings,
    cart_repository=cart_repository,
    product_repository=product_repository,
)
order_repository = OrderRepository(store=store, mongo_manager=mongo_manager)
memory_repository = MemoryRepository(
    store=store,
    mongo_manager=mongo_manager,
    redis_manager=redis_manager,
)
interaction_repository = InteractionRepository(
    store=store,
    mongo_manager=mongo_manager,
    redis_manager=redis_manager,
)
support_repository = SupportRepository(
    store=store,
    mongo_manager=mongo_manager,
)
inventory_service = InventoryService(
    store=store,
    inventory_repository=inventory_repository,
    product_repository=product_repository,
)
payment_service = PaymentService(store=store)
notification_service = NotificationService(
    store=store,
    notification_repository=notification_repository,
)
superu_client = SuperUClient(settings=settings)
order_service = OrderService(
    store=store,
    cart_service=cart_service,
    inventory_service=inventory_service,
    payment_service=payment_service,
    notification_service=notification_service,
    order_repository=order_repository,
)
memory_service = MemoryService(store=store, memory_repository=memory_repository)
interaction_service = InteractionService(
    store=store,
    interaction_repository=interaction_repository,
)
support_service = SupportService(
    store=store,
    support_repository=support_repository,
)
voice_recovery_service = VoiceRecoveryService(
    store=store,
    settings=settings,
    superu_client=superu_client,
    support_service=support_service,
    notification_service=notification_service,
)
admin_service = AdminService(
    store=store,
    session_repository=session_repository,
    order_repository=order_repository,
    interaction_repository=interaction_repository,
    support_repository=support_repository,
    product_repository=product_repository,
    voice_recovery_service=voice_recovery_service,
)

product_agent = ProductAgent(product_service=product_service)
cart_agent = CartAgent(cart_service=cart_service, product_service=product_service)
order_agent = OrderAgent(order_service=order_service)
support_agent = SupportAgent(support_service=support_service)
memory_agent = MemoryAgent(memory_service=memory_service)

orchestrator = Orchestrator(
    intent_classifier=IntentClassifier(llm_client=llm_client),
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
        memory_agent.name: memory_agent,
    },
)
