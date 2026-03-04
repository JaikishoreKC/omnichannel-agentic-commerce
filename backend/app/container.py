from __future__ import annotations

from copy import deepcopy
from threading import Lock

from app.core.config import Settings
from app.agents.cart_agent import CartAgent
from app.agents.memory_agent import MemoryAgent
from app.agents.order_agent import OrderAgent
from app.agents.product_agent import ProductAgent
from app.agents.support_agent import SupportAgent
from app.agents.general_agent import GeneralAgent
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
from app.repositories.admin_activity_repository import AdminActivityRepository
from app.repositories.auth_repository import AuthRepository
from app.repositories.cart_repository import CartRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.interaction_repository import InteractionRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.support_repository import SupportRepository
from app.repositories.voice_repository import VoiceRepository
from app.services.admin_service import AdminService
from app.services.admin_activity_service import AdminActivityService
from app.services.auth_service import AuthService
from app.services.cart_service import CartService
from app.services.category_service import CategoryService
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
from app.services.voice import settings as voice_settings
from app.store.in_memory import InMemoryStore

class Container:
    def __init__(self) -> None:
        self.settings = Settings.from_env()
        self.settings.validate_security()
        self.store = InMemoryStore()
        self._baseline_seeded = False
        self._baseline_seed_lock = Lock()
        self.mongo_manager = MongoClientManager(
            uri=self.settings.mongodb_uri, 
            enabled=self.settings.enable_external_services
        )
        self.redis_manager = RedisClientManager(
            url=self.settings.redis_url, 
            enabled=self.settings.enable_external_services
        )
        self.rate_limiter = SlidingWindowRateLimiter()
        self.metrics_collector = MetricsCollector()
        self.llm_client = LLMClient(settings=self.settings)
        self.state_persistence = StatePersistence(
            mongo_manager=self.mongo_manager,
            redis_manager=self.redis_manager,
        )

        self.auth_repository = AuthRepository(
            mongo_manager=self.mongo_manager,
            redis_manager=self.redis_manager,
        )
        self.auth_service = AuthService(
            settings=self.settings,
            auth_repository=self.auth_repository,
        )
        self.product_repository = ProductRepository(
            mongo_manager=self.mongo_manager,
            redis_manager=self.redis_manager,
        )
        self.category_repository = CategoryRepository(
            mongo_manager=self.mongo_manager,
            redis_manager=self.redis_manager,
        )
        self.inventory_repository = InventoryRepository(
            mongo_manager=self.mongo_manager,
            redis_manager=self.redis_manager,
        )
        self.notification_repository = NotificationRepository(
            mongo_manager=self.mongo_manager,
        )
        self.product_service = ProductService(
            product_repository=self.product_repository,
            category_repository=self.category_repository,
            inventory_repository=self.inventory_repository,
        )
        self.category_service = CategoryService(
            category_repository=self.category_repository,
            product_repository=self.product_repository,
        )
        self.session_repository = SessionRepository(
            mongo_manager=self.mongo_manager,
            redis_manager=self.redis_manager,
        )
        self.session_service = SessionService(
            session_repository=self.session_repository
        )
        self.cart_repository = CartRepository(
            mongo_manager=self.mongo_manager,
            redis_manager=self.redis_manager,
            store=self.store,
        )
        self.cart_service = CartService(
            settings=self.settings,
            cart_repository=self.cart_repository,
            product_repository=self.product_repository,
            session_repository=self.session_repository,
        )
        self.order_repository = OrderRepository(
            mongo_manager=self.mongo_manager
        )
        self.memory_repository = MemoryRepository(
            mongo_manager=self.mongo_manager,
            redis_manager=self.redis_manager,
        )
        self.interaction_repository = InteractionRepository(
            mongo_manager=self.mongo_manager,
            redis_manager=self.redis_manager,
        )
        self.support_repository = SupportRepository(
            mongo_manager=self.mongo_manager,
        )
        self.admin_activity_repository = AdminActivityRepository(
            mongo_manager=self.mongo_manager,
        )
        self.voice_repository = VoiceRepository(
            mongo_manager=self.mongo_manager,
            store=self.store,
        )
        self.inventory_service = InventoryService(
            inventory_repository=self.inventory_repository,
            product_repository=self.product_repository,
        )
        self.payment_service = PaymentService()
        self.notification_service = NotificationService(
            notification_repository=self.notification_repository,
        )
        self.superu_client = SuperUClient(settings=self.settings)
        self.order_service = OrderService(
            cart_service=self.cart_service,
            inventory_service=self.inventory_service,
            payment_service=self.payment_service,
            notification_service=self.notification_service,
            order_repository=self.order_repository,
        )
        self.memory_service = MemoryService(
            memory_repository=self.memory_repository
        )
        self.interaction_service = InteractionService(
            interaction_repository=self.interaction_repository,
        )
        self.support_service = SupportService(
            support_repository=self.support_repository,
        )
        self.admin_activity_service = AdminActivityService(
            settings=self.settings,
            admin_activity_repository=self.admin_activity_repository,
            store=self.store,
            enable_memory_mirror=True,
        )
        self.voice_recovery_service = VoiceRecoveryService(
            settings=self.settings,
            superu_client=self.superu_client,
            support_service=self.support_service,
            notification_service=self.notification_service,
            voice_repository=self.voice_repository,
            user_repository=self.auth_repository,
            cart_repository=self.cart_repository,
            order_repository=self.order_repository,
        )
        self.admin_service = AdminService(
            session_repository=self.session_repository,
            order_repository=self.order_repository,
            interaction_repository=self.interaction_repository,
            support_repository=self.support_repository,
            product_repository=self.product_repository,
            voice_recovery_service=self.voice_recovery_service,
        )

        self.product_agent = ProductAgent(product_service=self.product_service)
        self.cart_agent = CartAgent(
            cart_service=self.cart_service, 
            product_service=self.product_service
        )
        self.order_agent = OrderAgent(order_service=self.order_service)
        self.support_agent = SupportAgent(support_service=self.support_service)
        self.general_agent = GeneralAgent(llm_client=self.llm_client)
        self.memory_agent = MemoryAgent(memory_service=self.memory_service)

        self.orchestrator = Orchestrator(
            intent_classifier=IntentClassifier(llm_client=self.llm_client),
            context_builder=ContextBuilder(
                session_service=self.session_service,
                cart_service=self.cart_service,
                memory_service=self.memory_service,
            ),
            action_extractor=ActionExtractor(),
            router=AgentRouter(),
            formatter=ResponseFormatter(),
            llm_client=self.llm_client,
            interaction_service=self.interaction_service,
            memory_service=self.memory_service,
            agents={
                self.product_agent.name: self.product_agent,
                self.cart_agent.name: self.cart_agent,
                self.order_agent.name: self.order_agent,
                self.support_agent.name: self.support_agent,
                self.general_agent.name: self.general_agent,
                self.memory_agent.name: self.memory_agent,
            },
        )

    async def start(self) -> None:
        self.mongo_manager.connect()
        self.redis_manager.connect()
        self._seed_external_baseline_if_empty(force=True)

    async def stop(self) -> None:
        self.mongo_manager.disconnect()
        self.redis_manager.disconnect()

    def ensure_external_baseline(self) -> None:
        self._seed_external_baseline_if_empty()

    def _seed_external_baseline_if_empty(self, *, force: bool = False) -> None:
        if self._baseline_seeded and not force:
            return

        if not (self.mongo_manager.enabled or self.redis_manager.enabled):
            return
        if self.mongo_manager.client is None:
            return

        with self._baseline_seed_lock:
            if self._baseline_seeded and not force:
                return

            try:
                if not self.auth_repository.list_all_users(limit=1):
                    for user in self.store.users_by_id.values():
                        self.auth_repository.create_user(deepcopy(user))

                if not self.product_repository.list_all():
                    for product in self.store.products_by_id.values():
                        self.product_repository.create(deepcopy(product))

                if not self.category_repository.list_all():
                    for category in self.store.categories_by_id.values():
                        self.category_repository.create(deepcopy(category))

                for stock in self.store.inventory_by_variant.values():
                    self.inventory_repository.upsert(deepcopy(stock))

                voice_settings.ensure_defaults(self.voice_repository, self.settings)
                self._baseline_seeded = True
            except Exception:
                pass

container = Container()

# Re-export to avoid breaking imports in other modules
settings = container.settings
store = container.store
mongo_manager = container.mongo_manager
redis_manager = container.redis_manager
rate_limiter = container.rate_limiter
metrics_collector = container.metrics_collector
llm_client = container.llm_client
state_persistence = container.state_persistence
auth_repository = container.auth_repository
auth_service = container.auth_service
product_repository = container.product_repository
category_repository = container.category_repository
inventory_repository = container.inventory_repository
notification_repository = container.notification_repository
product_service = container.product_service
category_service = container.category_service
session_repository = container.session_repository
session_service = container.session_service
cart_repository = container.cart_repository
cart_service = container.cart_service
order_repository = container.order_repository
memory_repository = container.memory_repository
interaction_repository = container.interaction_repository
support_repository = container.support_repository
admin_activity_repository = container.admin_activity_repository
voice_repository = container.voice_repository
inventory_service = container.inventory_service
payment_service = container.payment_service
notification_service = container.notification_service
superu_client = container.superu_client
order_service = container.order_service
memory_service = container.memory_service
interaction_service = container.interaction_service
support_service = container.support_service
admin_activity_service = container.admin_activity_service
voice_recovery_service = container.voice_recovery_service
admin_service = container.admin_service
product_agent = container.product_agent
cart_agent = container.cart_agent
order_agent = container.order_agent
support_agent = container.support_agent
general_agent = container.general_agent
memory_agent = container.memory_agent
orchestrator = container.orchestrator
