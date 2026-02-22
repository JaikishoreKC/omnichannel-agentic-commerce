from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=12)
    name: str = Field(min_length=1)
    phone: str | None = None
    timezone: str | None = None


class LoginRequest(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str


class RefreshRequest(BaseModel):
    refreshToken: str


class AuthUser(BaseModel):
    id: str
    email: str
    name: str
    role: str
    createdAt: str
    phone: str | None = None
    timezone: str | None = None


class AuthResponse(BaseModel):
    user: AuthUser
    accessToken: str
    refreshToken: str
    expiresIn: int
    sessionId: str | None = None


class ProductListQuery(BaseModel):
    query: str | None = None
    category: str | None = None
    minPrice: float | None = None
    maxPrice: float | None = None
    page: int = 1
    limit: int = 20


class AddCartItemRequest(BaseModel):
    productId: str
    variantId: str
    quantity: int = Field(ge=1, le=50)


class UpdateCartItemRequest(BaseModel):
    quantity: int = Field(ge=1, le=50)


class ApplyDiscountRequest(BaseModel):
    code: str


class ShippingAddress(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    line1: str = Field(min_length=1, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=2, max_length=100)
    postalCode: str = Field(min_length=3, max_length=16)
    country: str = Field(min_length=2, max_length=2)
    line2: str | None = None


class PaymentMethod(BaseModel):
    type: str = Field(min_length=2, max_length=30)
    token: str = Field(min_length=2, max_length=200)


class CreateOrderRequest(BaseModel):
    shippingAddress: ShippingAddress
    paymentMethod: PaymentMethod


class CancelOrderRequest(BaseModel):
    reason: str | None = None


class RefundOrderRequest(BaseModel):
    reason: str | None = None


class UpdateOrderAddressRequest(BaseModel):
    shippingAddress: ShippingAddress


class CreateSessionRequest(BaseModel):
    channel: str = "web"
    initialContext: dict[str, Any] = Field(default_factory=dict)


class UpdatePreferencesRequest(BaseModel):
    size: str | None = None
    brandPreferences: list[str] | None = None
    categories: list[str] | None = None
    stylePreferences: list[str] | None = None
    colorPreferences: list[str] | None = None
    priceRange: dict[str, float] | None = None


class InteractionMessageRequest(BaseModel):
    sessionId: str
    content: str = Field(min_length=1, max_length=2000)
    channel: str = "web"


class ProductVariantWrite(BaseModel):
    id: str
    size: str
    color: str
    inStock: bool = True
    inventory: dict[str, int] | None = None


class ProductWriteRequest(BaseModel):
    id: str | None = None
    name: str
    description: str = ""
    category: str
    price: float = Field(gt=0)
    currency: str = "USD"
    images: list[str] = Field(default_factory=list)
    variants: list[ProductVariantWrite] = Field(default_factory=list)
    rating: float = 0
    reviewCount: int = 0


class InventoryUpdateRequest(BaseModel):
    totalQuantity: int | None = Field(default=None, ge=0)
    availableQuantity: int | None = Field(default=None, ge=0)


class VoiceSettingsUpdateRequest(BaseModel):
    enabled: bool | None = None
    killSwitch: bool | None = None
    abandonmentMinutes: int | None = Field(default=None, ge=1)
    maxAttemptsPerCart: int | None = Field(default=None, ge=1)
    maxCallsPerUserPerDay: int | None = Field(default=None, ge=1)
    maxCallsPerDay: int | None = Field(default=None, ge=1)
    dailyBudgetUsd: float | None = Field(default=None, ge=0)
    estimatedCostPerCallUsd: float | None = Field(default=None, ge=0)
    quietHoursStart: int | None = Field(default=None, ge=0, le=23)
    quietHoursEnd: int | None = Field(default=None, ge=0, le=23)
    retryBackoffSeconds: list[int] | str | None = None
    scriptVersion: str | None = None
    scriptTemplate: str | None = None
    assistantId: str | None = None
    fromPhoneNumber: str | None = None
    defaultTimezone: str | None = None
    alertBacklogThreshold: int | None = Field(default=None, ge=1)
    alertFailureRatioThreshold: float | None = Field(default=None, ge=0.01, le=1.0)


class VoiceSuppressionRequest(BaseModel):
    userId: str = Field(min_length=1)
    reason: str = Field(default="manual_suppression", min_length=1)
