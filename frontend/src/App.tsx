import { useEffect, useMemo, useRef, useState } from "react";

import {
  addToCart,
  checkout,
  connectChat,
  ensureSession,
  fetchChatHistory,
  fetchProduct,
  fetchCart,
  fetchProducts,
  login,
  type ChatResponsePayload,
  register,
  setSessionId as setStoredSessionId,
  setToken,
} from "./api";
import type { AuthUser, Cart, InteractionHistoryMessage, Product } from "./types";

const DEFAULT_CART: Cart = {
  id: "",
  userId: null,
  sessionId: "",
  items: [],
  subtotal: 0,
  tax: 0,
  shipping: 0,
  discount: 0,
  total: 0,
  itemCount: 0,
  currency: "USD",
};

function productIdFromPath(pathname: string): string | null {
  const match = pathname.match(/^\/products\/([^/]+)\/?$/);
  if (!match) {
    return null;
  }
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return match[1];
  }
}

type ChatEntry = { role: "user" | "assistant"; text: string; agent?: string; streamId?: string };

function historyToChatEntries(history: InteractionHistoryMessage[]): ChatEntry[] {
  const output: ChatEntry[] = [];
  for (const row of history) {
    const userText = row.message?.trim();
    if (userText) {
      output.push({ role: "user", text: userText });
    }
    const assistantText = String(row.response?.message ?? "").trim();
    if (assistantText) {
      output.push({
        role: "assistant",
        text: assistantText,
        agent: row.response?.agent ?? row.agent ?? "assistant",
      });
    }
  }
  return output;
}

export default function App(): JSX.Element {
  const [products, setProducts] = useState<Product[]>([]);
  const [cart, setCart] = useState<Cart>(DEFAULT_CART);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [message, setMessage] = useState("Guest mode: browse and build your cart.");
  const [busy, setBusy] = useState(false);
  const [sessionId, setSessionId] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatEntry[]>([]);
  const [chatActions, setChatActions] = useState<Array<{ label: string; action: string }>>([]);
  const [chatReady, setChatReady] = useState(false);
  const [assistantTyping, setAssistantTyping] = useState(false);
  const [path, setPath] = useState(() => window.location.pathname);
  const [detailProduct, setDetailProduct] = useState<Product | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailVariantId, setDetailVariantId] = useState("");
  const [detailQuantity, setDetailQuantity] = useState(1);
  const [catalogQuery, setCatalogQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const socketRef = useRef<WebSocket | null>(null);
  const connectSocketRef = useRef<(session: string) => void>(() => undefined);
  const reconnectTimerRef = useRef<number | null>(null);
  const intentionalSocketCloseRef = useRef(false);

  const totalItems = useMemo(() => cart.itemCount, [cart.itemCount]);
  const selectedProductId = useMemo(() => productIdFromPath(path), [path]);
  const selectedDetailVariant = useMemo(
    () => detailProduct?.variants.find((variant) => variant.id === detailVariantId) ?? null,
    [detailProduct, detailVariantId],
  );
  const categories = useMemo(() => {
    const names = new Set<string>();
    for (const product of products) {
      names.add(product.category);
    }
    return Array.from(names).sort((left, right) => left.localeCompare(right));
  }, [products]);
  const filteredProducts = useMemo(() => {
    const query = catalogQuery.trim().toLowerCase();
    return products.filter((product) => {
      if (categoryFilter !== "all" && product.category !== categoryFilter) {
        return false;
      }
      if (!query) {
        return true;
      }
      return (
        product.name.toLowerCase().includes(query) ||
        product.description.toLowerCase().includes(query) ||
        product.category.toLowerCase().includes(query)
      );
    });
  }, [products, catalogQuery, categoryFilter]);

  async function reloadData(): Promise<void> {
    const [productList, cartData] = await Promise.all([fetchProducts(), fetchCart()]);
    setProducts(productList);
    setCart(cartData);
  }

  async function reloadChatHistory(targetSessionId: string): Promise<void> {
    try {
      const payload = await fetchChatHistory({ sessionId: targetSessionId, limit: 80 });
      let resolvedSessionId = payload.sessionId || targetSessionId;
      if (payload.sessionId && payload.sessionId !== targetSessionId) {
        setStoredSessionId(payload.sessionId);
        setSessionId(payload.sessionId);
      }
      let resolvedMessages = payload.messages ?? [];
      for (let attempt = 0; resolvedMessages.length === 0 && attempt < 4; attempt += 1) {
        try {
          await new Promise((resolve) => window.setTimeout(resolve, 200 * (attempt + 1)));
          const retryPayload = await fetchChatHistory({ sessionId: resolvedSessionId, limit: 80 });
          if (retryPayload.sessionId && retryPayload.sessionId !== resolvedSessionId) {
            resolvedSessionId = retryPayload.sessionId;
            setStoredSessionId(retryPayload.sessionId);
            setSessionId(retryPayload.sessionId);
          }
          resolvedMessages = retryPayload.messages ?? resolvedMessages;
        } catch {
          // Keep retrying with backoff for eventual consistency.
        }
      }
      setChatMessages(historyToChatEntries(resolvedMessages));
    } catch {
      // Keep existing chat state when history endpoint is unavailable.
    }
  }

  function navigateTo(pathname: string): void {
    if (window.location.pathname === pathname) {
      return;
    }
    window.history.pushState({}, "", pathname);
    setPath(pathname);
  }

  function handleChatResponse(payload: ChatResponsePayload, streamId?: string): void {
    setAssistantTyping(false);
    setChatMessages((previous) => {
      if (!streamId) {
        return [...previous, { role: "assistant", text: payload.message, agent: payload.agent }];
      }
      const hasExisting = previous.some(
        (entry) => entry.role === "assistant" && entry.streamId === streamId,
      );
      if (!hasExisting) {
        return [
          ...previous,
          {
            role: "assistant",
            text: payload.message,
            agent: payload.agent,
            streamId,
          },
        ];
      }
      return previous.map((entry) =>
        entry.role === "assistant" && entry.streamId === streamId
          ? { ...entry, text: payload.message, agent: payload.agent }
          : entry,
      );
    });
    setChatActions(payload.suggestedActions ?? []);

    const cartPayload = payload.data?.cart as Cart | undefined;
    if (cartPayload) {
      setCart(cartPayload);
    }
    const multiCart = (payload.data?.cart as { cart?: Cart } | undefined)?.cart;
    if (multiCart) {
      setCart(multiCart);
    }
    const productsPayload = payload.data?.products as Product[] | undefined;
    if (productsPayload && productsPayload.length > 0) {
      setProducts(productsPayload);
    }
  }

  function handleStreamStart(payload: { streamId: string; agent?: string }): void {
    setChatMessages((previous) => {
      const exists = previous.some(
        (entry) => entry.role === "assistant" && entry.streamId === payload.streamId,
      );
      if (exists) {
        return previous;
      }
      return [...previous, { role: "assistant", text: "", agent: payload.agent, streamId: payload.streamId }];
    });
  }

  function handleStreamDelta(payload: { streamId: string; delta: string }): void {
    setChatMessages((previous) =>
      previous.map((entry) =>
        entry.role === "assistant" && entry.streamId === payload.streamId
          ? { ...entry, text: `${entry.text}${payload.delta}` }
          : entry,
      ),
    );
  }

  function handleStreamEnd(payload: { streamId: string }): void {
    setChatMessages((previous) =>
      previous.map((entry) =>
        entry.role === "assistant" && entry.streamId === payload.streamId
          ? { ...entry, text: entry.text.trimEnd() }
          : entry,
      ),
    );
  }

  useEffect(() => {
    let active = true;
    let currentSessionId = "";

    const connectSocket = (nextSessionId: string) => {
      if (!active) {
        return;
      }
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (socketRef.current) {
        intentionalSocketCloseRef.current = true;
        socketRef.current.close();
      }
      setChatReady(false);
      const socket = connectChat({
        sessionId: nextSessionId,
        onOpen: () => {
          if (socketRef.current !== socket) {
            return;
          }
          if (!active) {
            return;
          }
          setChatReady(true);
        },
        onMessage: (payload, streamId) => {
          if (socketRef.current !== socket) {
            return;
          }
          if (!active) {
            return;
          }
          handleChatResponse(payload, streamId);
        },
        onTyping: (payload) => {
          if (socketRef.current !== socket) {
            return;
          }
          if (!active) {
            return;
          }
          if (payload.actor === "assistant") {
            setAssistantTyping(payload.isTyping);
          }
        },
        onStreamStart: (payload) => {
          if (socketRef.current !== socket) {
            return;
          }
          if (!active) {
            return;
          }
          handleStreamStart(payload);
        },
        onStreamDelta: (payload) => {
          if (socketRef.current !== socket) {
            return;
          }
          if (!active) {
            return;
          }
          handleStreamDelta(payload);
        },
        onStreamEnd: (payload) => {
          if (socketRef.current !== socket) {
            return;
          }
          if (!active) {
            return;
          }
          handleStreamEnd(payload);
        },
        onSession: (resolvedSessionId) => {
          if (!active) {
            return;
          }
          currentSessionId = resolvedSessionId;
          setStoredSessionId(resolvedSessionId);
          setSessionId(resolvedSessionId);
          void reloadChatHistory(resolvedSessionId);
        },
        onError: (errorMessage) => {
          if (socketRef.current !== socket) {
            return;
          }
          if (!active) {
            return;
          }
          setAssistantTyping(false);
          setChatReady(false);
          setMessage(errorMessage);
        },
        onClose: () => {
          if (socketRef.current !== socket) {
            if (intentionalSocketCloseRef.current) {
              intentionalSocketCloseRef.current = false;
            }
            return;
          }
          socketRef.current = null;
          if (intentionalSocketCloseRef.current) {
            intentionalSocketCloseRef.current = false;
            return;
          }
          if (!active) {
            return;
          }
          setAssistantTyping(false);
          setChatReady(false);
          setMessage("Chat disconnected. Reconnecting...");
          reconnectTimerRef.current = window.setTimeout(() => {
            connectSocket(currentSessionId || nextSessionId);
          }, 1200);
        },
      });
      socketRef.current = socket;
    };
    connectSocketRef.current = connectSocket;

    (async () => {
      try {
        const createdSessionId = await ensureSession();
        if (!active) {
          return;
        }
        currentSessionId = createdSessionId;
        setSessionId(createdSessionId);
        await reloadData();
        await reloadChatHistory(createdSessionId);
        connectSocket(createdSessionId);
      } catch (err) {
        setMessage((err as Error).message);
      }
    })();
    return () => {
      active = false;
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (socketRef.current) {
        intentionalSocketCloseRef.current = true;
        socketRef.current.close();
        socketRef.current = null;
      }
      setChatReady(false);
      setAssistantTyping(false);
      connectSocketRef.current = () => undefined;
    };
  }, []);

  useEffect(() => {
    const onPopState = () => {
      setPath(window.location.pathname);
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    if (!selectedProductId) {
      setDetailProduct(null);
      setDetailVariantId("");
      setDetailQuantity(1);
      setDetailLoading(false);
      return;
    }
    let active = true;
    setDetailLoading(true);
    (async () => {
      try {
        const product = await fetchProduct(selectedProductId);
        if (!active) {
          return;
        }
        setDetailProduct(product);
        const firstInStock = product.variants.find((variant) => variant.inStock);
        setDetailVariantId(firstInStock?.id ?? product.variants[0]?.id ?? "");
      } catch (err) {
        if (!active) {
          return;
        }
        setDetailProduct(null);
        setDetailVariantId("");
        setMessage((err as Error).message);
      } finally {
        if (active) {
          setDetailLoading(false);
        }
      }
    })();
    return () => {
      active = false;
    };
  }, [selectedProductId]);

  async function onRegister(): Promise<void> {
    setBusy(true);
    setMessage("Creating account...");
    try {
      const payload = await register({ email, password, name });
      const resolvedSessionId = payload.sessionId || sessionId;
      setToken(payload.accessToken);
      if (resolvedSessionId) {
        setStoredSessionId(resolvedSessionId);
        setSessionId(resolvedSessionId);
      }
      setUser(payload.user);
      await reloadData();
      if (resolvedSessionId) {
        await reloadChatHistory(resolvedSessionId);
      }
      if (resolvedSessionId) {
        connectSocketRef.current(resolvedSessionId);
      }
      setMessage("Account created. Guest cart has been attached.");
    } catch (err) {
      setMessage((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function onLogin(): Promise<void> {
    setBusy(true);
    setMessage("Signing in...");
    try {
      const payload = await login({ email, password });
      const resolvedSessionId = payload.sessionId || sessionId;
      setToken(payload.accessToken);
      if (resolvedSessionId) {
        setStoredSessionId(resolvedSessionId);
        setSessionId(resolvedSessionId);
      }
      setUser(payload.user);
      await reloadData();
      if (resolvedSessionId) {
        await reloadChatHistory(resolvedSessionId);
      }
      if (resolvedSessionId) {
        connectSocketRef.current(resolvedSessionId);
      }
      setMessage("Signed in. You can now checkout.");
    } catch (err) {
      setMessage((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function onAddProduct(product: Product): Promise<void> {
    setBusy(true);
    try {
      const defaultVariant = product.variants.find((variant) => variant.inStock);
      if (!defaultVariant) {
        setMessage("No in-stock variant for this product.");
        return;
      }
      await addToCart({
        productId: product.id,
        variantId: defaultVariant.id,
        quantity: 1,
      });
      const updated = await fetchCart();
      setCart(updated);
      setMessage(`Added ${product.name} to cart.`);
    } catch (err) {
      setMessage((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function onAddProductFromDetail(): Promise<void> {
    if (!detailProduct) {
      return;
    }
    if (!detailVariantId) {
      setMessage("No selectable variant for this product.");
      return;
    }
    setBusy(true);
    try {
      await addToCart({
        productId: detailProduct.id,
        variantId: detailVariantId,
        quantity: Math.max(1, detailQuantity),
      });
      const updated = await fetchCart();
      setCart(updated);
      setMessage(`Added ${detailProduct.name} to cart.`);
    } catch (err) {
      setMessage((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function onCheckout(): Promise<void> {
    setBusy(true);
    try {
      const payload = await checkout({
        shippingAddress: {
          name: user?.name ?? "Guest User",
          line1: "123 Main St",
          city: "Austin",
          state: "TX",
          postalCode: "78701",
          country: "US",
        },
        paymentMethod: {
          type: "card",
          token: "pm_demo_token",
        },
      });
      await reloadData();
      setMessage(`Order created: ${payload.order.id}`);
    } catch (err) {
      setMessage((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function onSendChat(): void {
    const text = chatInput.trim();
    if (!text || !chatReady || !socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
      return;
    }
    setChatInput("");
    setChatMessages((previous) => [...previous, { role: "user", text }]);
    socketRef.current.send(
      JSON.stringify({
        type: "message",
        payload: { content: text, timestamp: new Date().toISOString(), stream: true, typing: true },
      }),
    );
  }

  function onSuggestedAction(action: string): void {
    let messageText = action;
    if (action.startsWith("search:")) {
      messageText = action.replace("search:", "").replace(/_/g, " ");
    }
    if (action.startsWith("add_to_cart:")) {
      const [, productId, variantId] = action.split(":");
      messageText = `add ${productId} ${variantId} to cart`;
    }
    if (action.startsWith("order_status:")) {
      const [, orderId] = action.split(":");
      messageText = `order status ${orderId}`;
    }
    setChatInput(messageText);
  }

  function onLogout(): void {
    setToken(null);
    setUser(null);
    setMessage("Logged out. You are back in guest mode.");
  }

  return (
    <div className="relative min-h-screen overflow-x-clip pb-10">
      <div
        aria-hidden
        className="pointer-events-none absolute -left-28 -top-28 h-72 w-72 rounded-full bg-[#f8d4a8]/70 blur-3xl"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -right-24 top-10 h-72 w-72 rounded-full bg-[#acd7cc]/70 blur-3xl"
      />
      <div className="mx-auto max-w-[1320px] px-4 py-6 sm:px-6 lg:px-8">
        <header className="panel-surface relative overflow-hidden p-6 sm:p-7">
          <div className="absolute -right-14 -top-16 h-44 w-44 rounded-full bg-[#ffedd0]/70 blur-2xl" />
          <p className="relative text-xs font-semibold uppercase tracking-[0.17em] text-cedar">
            Omnichannel Agentic Commerce
          </p>
          <h1 className="relative mt-2 max-w-3xl text-2xl font-bold sm:text-3xl lg:text-[2.2rem]">
            Conversational shopping that starts as guest and checks out as authenticated.
          </h1>
          <p className="relative mt-3 text-sm text-[#5f554a]" data-testid="status-message">
            {message}
          </p>
          <p className="relative mt-1 text-sm text-[#7a6f62]" data-testid="session-id">
            Session: {sessionId || "initializing..."}
          </p>
          <div className="relative mt-4 flex flex-wrap gap-2">
            <span className="chip">{user ? `Signed in: ${user.email}` : "Guest mode"}</span>
            <span className="chip">{totalItems} items in cart</span>
            <span className="chip">{chatReady ? "Assistant connected" : "Assistant connecting"}</span>
          </div>
        </header>

        <main className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-12">
          <section className="panel-surface animate-rise p-4 lg:col-span-3" data-testid="auth-panel">
            <h2 className="text-base font-bold text-[#1f1d1b]">
              {user ? `Signed in as ${user.name}` : "Sign in for checkout"}
            </h2>
            {!user ? (
              <div className="mt-4 space-y-3">
                <label className="block text-sm font-medium text-[#4f473e]">
                  Name
                  <input
                    data-testid="name-input"
                    className="mt-1 w-full rounded-xl border border-line bg-white/90 px-3 py-2 text-sm outline-none ring-clay/30 transition focus:ring-2"
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                  />
                </label>
                <label className="block text-sm font-medium text-[#4f473e]">
                  Email
                  <input
                    data-testid="email-input"
                    type="email"
                    className="mt-1 w-full rounded-xl border border-line bg-white/90 px-3 py-2 text-sm outline-none ring-clay/30 transition focus:ring-2"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                  />
                </label>
                <label className="block text-sm font-medium text-[#4f473e]">
                  Password
                  <input
                    data-testid="password-input"
                    type="password"
                    className="mt-1 w-full rounded-xl border border-line bg-white/90 px-3 py-2 text-sm outline-none ring-clay/30 transition focus:ring-2"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                  />
                </label>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
                  <button className="btn-primary" data-testid="register-button" disabled={busy} onClick={onRegister}>
                    Register
                  </button>
                  <button className="btn-quiet" data-testid="login-button" disabled={busy} onClick={onLogin}>
                    Login
                  </button>
                </div>
                <p className="text-xs text-[#73685c]">Use any email + 12+ char password for demo registration.</p>
              </div>
            ) : (
              <div className="mt-4 space-y-3">
                <div className="rounded-xl border border-line bg-white/80 p-3 text-sm text-[#4e453c]">
                  Checkout and order APIs are unlocked for authenticated users.
                </div>
                <button className="btn-quiet w-full" data-testid="logout-button" disabled={busy} onClick={onLogout}>
                  Logout
                </button>
              </div>
            )}
          </section>

          <section className="panel-surface animate-rise p-4 lg:col-span-5" data-testid="catalog-panel">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-base font-bold text-[#1f1d1b]">{selectedProductId ? "Product Details" : "Catalog"}</h2>
              <span className="chip">{selectedProductId ? selectedProductId : `${filteredProducts.length} products`}</span>
            </div>

            {!selectedProductId ? (
              <>
                <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-[1fr,170px]">
                  <input
                    value={catalogQuery}
                    onChange={(event) => setCatalogQuery(event.target.value)}
                    placeholder="Search by name, category, description..."
                    className="w-full rounded-xl border border-line bg-white/90 px-3 py-2 text-sm outline-none ring-cedar/25 transition focus:ring-2"
                  />
                  <select
                    value={categoryFilter}
                    onChange={(event) => setCategoryFilter(event.target.value)}
                    className="w-full rounded-xl border border-line bg-white px-3 py-2 text-sm outline-none ring-cedar/25 transition focus:ring-2"
                  >
                    <option value="all">All categories</option>
                    {categories.map((category) => (
                      <option key={category} value={category}>
                        {category}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="mt-4 grid gap-3">
                  {filteredProducts.map((product) => (
                    <article
                      className="rounded-2xl border border-line bg-gradient-to-r from-[#fff7ea] to-[#fffdf7] p-4 transition hover:-translate-y-0.5 hover:shadow-md"
                      key={product.id}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#6f665b]">
                            {product.category}
                          </p>
                          <h3 className="mt-1 text-lg font-semibold text-[#1d1b18]">{product.name}</h3>
                        </div>
                        <p className="rounded-full bg-white px-3 py-1 text-sm font-semibold text-[#2f3d4d]">
                          ${product.price.toFixed(2)}
                        </p>
                      </div>
                      <p className="mt-2 text-sm text-[#5f5447]">{product.description}</p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <button
                          className="btn-primary"
                          data-testid={`add-to-cart-${product.id}`}
                          disabled={busy}
                          onClick={() => void onAddProduct(product)}
                        >
                          Add to Cart
                        </button>
                        <button
                          type="button"
                          className="btn-quiet"
                          data-testid={`view-product-${product.id}`}
                          onClick={() => navigateTo(`/products/${encodeURIComponent(product.id)}`)}
                        >
                          View details
                        </button>
                      </div>
                    </article>
                  ))}
                  {filteredProducts.length === 0 && (
                    <p className="rounded-xl border border-dashed border-line bg-white/60 p-4 text-sm text-[#6e6254]">
                      No products match your search/filter.
                    </p>
                  )}
                </div>
              </>
            ) : (
              <div className="mt-3" data-testid="product-detail-page">
                <button
                  type="button"
                  className="text-sm font-semibold text-cedar underline underline-offset-4"
                  data-testid="back-to-catalog"
                  onClick={() => navigateTo("/")}
                >
                  Back to catalog
                </button>
                {detailLoading && <p className="mt-3 text-sm text-[#72675b]">Loading product details...</p>}
                {!detailLoading && !detailProduct && (
                  <p className="mt-3 text-sm text-[#72675b]" data-testid="product-detail-missing">
                    Product not found.
                  </p>
                )}
                {!detailLoading && detailProduct && (
                  <>
                    <p className="mt-4 text-[11px] font-semibold uppercase tracking-[0.14em] text-[#6f665b]">
                      {detailProduct.category}
                    </p>
                    <h3 className="mt-1 text-2xl font-bold text-[#1a1816]" data-testid="product-detail-name">
                      {detailProduct.name}
                    </h3>
                    <p className="mt-2 flex flex-wrap gap-2 text-sm text-[#5d5347]">
                      <span className="rounded-full bg-white px-3 py-1 font-semibold" data-testid="product-detail-price">
                        ${detailProduct.price.toFixed(2)} {detailProduct.currency}
                      </span>
                      <span className="rounded-full bg-[#edf5f2] px-3 py-1" data-testid="product-detail-rating">
                        Rating {detailProduct.rating.toFixed(1)} / 5
                      </span>
                    </p>
                    <p className="mt-3 text-sm text-[#5f5448]" data-testid="product-detail-description">
                      {detailProduct.description}
                    </p>
                    <p className="mt-2 text-xs text-[#7a6f62]">Product ID: {detailProduct.id}</p>
                    {detailProduct.images[0] && (
                      <p className="text-xs text-[#7a6f62]">Image URL: {detailProduct.images[0]}</p>
                    )}

                    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                      <label className="block text-sm font-medium text-[#4f473e]">
                        Variant
                        <select
                          data-testid="detail-variant-select"
                          value={detailVariantId}
                          onChange={(event) => setDetailVariantId(event.target.value)}
                          className="mt-1 w-full rounded-xl border border-line bg-white px-3 py-2 text-sm outline-none ring-cedar/25 transition focus:ring-2"
                        >
                          {detailProduct.variants.map((variant) => (
                            <option key={variant.id} value={variant.id}>
                              {variant.size} / {variant.color} ({variant.inStock ? "In stock" : "Out of stock"})
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="block text-sm font-medium text-[#4f473e]">
                        Quantity
                        <input
                          data-testid="detail-quantity-input"
                          type="number"
                          min={1}
                          max={20}
                          value={detailQuantity}
                          onChange={(event) => {
                            const parsed = Number.parseInt(event.target.value, 10);
                            setDetailQuantity(Number.isFinite(parsed) && parsed > 0 ? parsed : 1);
                          }}
                          className="mt-1 w-full rounded-xl border border-line bg-white/90 px-3 py-2 text-sm outline-none ring-cedar/25 transition focus:ring-2"
                        />
                      </label>
                    </div>

                    <ul className="mt-3 grid gap-2" data-testid="product-detail-variants">
                      {detailProduct.variants.map((variant) => (
                        <li
                          key={variant.id}
                          className="grid gap-1 rounded-xl border border-dashed border-line bg-[#fffdf8] p-3 text-sm text-[#4f4539] sm:grid-cols-[120px,1fr,auto]"
                        >
                          <strong>{variant.id}</strong>
                          <span>
                            {variant.size} / {variant.color}
                          </span>
                          <span className={variant.inStock ? "text-cedar" : "text-[#a54520]"}>
                            {variant.inStock ? "In stock" : "Out of stock"}
                          </span>
                        </li>
                      ))}
                    </ul>

                    <button
                      className="btn-primary mt-4"
                      data-testid="detail-add-to-cart"
                      disabled={busy || !selectedDetailVariant?.inStock}
                      onClick={() => void onAddProductFromDetail()}
                    >
                      Add to Cart
                    </button>
                    {!selectedDetailVariant?.inStock && (
                      <p className="mt-2 text-xs text-[#9b4b2a]">Selected variant is out of stock.</p>
                    )}
                  </>
                )}
              </div>
            )}
          </section>

          <section className="panel-surface animate-rise p-4 lg:col-span-4" data-testid="cart-panel">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-base font-bold text-[#1f1d1b]">Cart</h2>
              <span className="chip" data-testid="cart-item-count">
                {totalItems} items
              </span>
            </div>
            <ul className="mt-3 space-y-2" data-testid="cart-list">
              {cart.items.map((item) => (
                <li
                  key={item.itemId}
                  className="grid grid-cols-[1fr,auto] items-center gap-2 rounded-xl border border-line bg-white/70 p-3"
                >
                  <strong className="text-sm font-semibold text-[#1f1c19]">{item.name}</strong>
                  <span className="text-sm text-[#4f463d]">
                    {item.quantity} x ${item.price.toFixed(2)}
                  </span>
                </li>
              ))}
              {cart.items.length === 0 && (
                <li className="rounded-xl border border-dashed border-line bg-white/50 p-3 text-sm text-[#786e63]">
                  Cart is empty.
                </li>
              )}
            </ul>
            <dl className="mt-4 space-y-1 text-sm text-[#4f463d]">
              <div className="flex items-center justify-between">
                <dt>Subtotal</dt>
                <dd>${cart.subtotal.toFixed(2)}</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt>Tax</dt>
                <dd>${cart.tax.toFixed(2)}</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt>Shipping</dt>
                <dd>${cart.shipping.toFixed(2)}</dd>
              </div>
              <div className="mt-2 flex items-center justify-between border-t border-line pt-2 text-base font-bold text-[#1d1b18]">
                <dt>Total</dt>
                <dd>${cart.total.toFixed(2)}</dd>
              </div>
            </dl>
            <button
              className="btn-emerald mt-4 w-full"
              data-testid="checkout-button"
              disabled={busy || cart.itemCount === 0}
              onClick={onCheckout}
            >
              Checkout
            </button>
            {!user && <p className="mt-2 text-xs text-[#7d6d5c]">Login is required before order creation.</p>}
          </section>

          <section className="panel-surface animate-rise p-4 lg:col-span-12" data-testid="chat-panel">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base font-bold text-[#1f1d1b]">Assistant Chat</h2>
              <div className="flex items-center gap-2">
                <span className="chip" data-testid="chat-message-count">
                  {chatMessages.length} msgs
                </span>
                <span
                  className={chatReady ? "chip border-emerald-200 bg-emerald-50 text-emerald-700" : "chip"}
                  data-testid="chat-ready"
                >
                  {chatReady ? "connected" : "connecting"}
                </span>
              </div>
            </div>

            <div className="mt-3 grid gap-4 lg:grid-cols-[1fr,260px]">
              <div
                className="scroll-calm min-h-[260px] max-h-[360px] space-y-2 overflow-auto rounded-2xl border border-line bg-[#fffdf8] p-3"
                data-testid="chat-log"
              >
                {chatMessages.length === 0 && (
                  <p className="rounded-xl border border-dashed border-line bg-white/80 p-3 text-sm text-[#6f655a]">
                    Ask: "show me running shoes", "add to cart", "checkout", "order status".
                  </p>
                )}
                {chatMessages.map((entry, index) => (
                  <div
                    key={`${entry.role}-${entry.streamId ?? index}`}
                    className={
                      entry.role === "user"
                        ? "ml-auto max-w-[85%] rounded-2xl bg-[#efe5d4] px-3 py-2 text-sm text-[#312a22]"
                        : "mr-auto max-w-[90%] rounded-2xl bg-[#e8f2ef] px-3 py-2 text-sm text-[#21342d]"
                    }
                  >
                    <strong>{entry.role === "user" ? "You" : entry.agent ?? "Assistant"}:</strong> {entry.text}
                  </div>
                ))}
                {assistantTyping && <p className="text-xs text-[#7b6f61]">Assistant is typing...</p>}
              </div>

              <div className="space-y-3">
                <p className="text-xs uppercase tracking-[0.12em] text-[#7b6f62]">Quick actions</p>
                {chatActions.length > 0 ? (
                  <div className="grid gap-2">
                    {chatActions.map((action) => (
                      <button
                        key={action.action}
                        type="button"
                        className="btn-quiet w-full text-left"
                        onClick={() => onSuggestedAction(action.action)}
                      >
                        {action.label}
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="rounded-xl border border-dashed border-line bg-white/70 p-3 text-xs text-[#72675b]">
                    Suggested actions will appear after assistant responses.
                  </p>
                )}
              </div>
            </div>

            <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-[1fr,auto]">
              <input
                data-testid="chat-input"
                value={chatInput}
                onChange={(event) => setChatInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    onSendChat();
                  }
                }}
                placeholder="Type a shopping request..."
                className="w-full rounded-xl border border-line bg-white px-3 py-2 text-sm outline-none ring-cedar/25 transition focus:ring-2"
              />
              <button
                className="btn-primary"
                data-testid="chat-send-button"
                type="button"
                disabled={busy || !chatReady}
                onClick={onSendChat}
              >
                Send
              </button>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}
