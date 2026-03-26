import React from "react";
import { Link } from "react-router-dom";
import { ShoppingCart, Eye, Star, Plus, Minus } from "lucide-react";
import type { Product } from "../../types";
import type { CartItem } from "../../types";
import { Button } from "../ui/Button";
import { Badge } from "../ui/Badge";
import { useCart } from "../../context/CartContext";

interface ProductCardProps {
    product: Product;
}

const ProductCard: React.FC<ProductCardProps> = ({ product }) => {
    const { addItem, updateItemQuantity, removeItem, cart } = useCart();
    const [isAdding, setIsAdding] = React.useState(false);

    const defaultVariant = product.variants.find(v => v.inStock) || product.variants[0];
    const cartItem = cart?.items.find((item: CartItem) => item.productId === product.id && item.variantId === defaultVariant.id);
    const quantity = cartItem?.quantity || 0;

    const handleAddToCart = async (e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsAdding(true);
        try {
            if (quantity > 0) {
                await updateItemQuantity(cartItem!.itemId, quantity + 1);
            } else {
                await addItem(product.id, defaultVariant.id, 1);
            }
        } finally {
            setIsAdding(false);
        }
    };

    return (
        <div className="group h-full">
            <div className="premium-card flex flex-col h-full overflow-hidden p-0 group">
                <div className="relative aspect-square overflow-hidden bg-surface-100 p-8 flex items-center justify-center">
                    <img
                        src={product.images[0]}
                        alt={product.name}
                        className="h-full w-full object-contain transition-transform duration-500 group-hover:scale-110"
                    />
                    <div className="absolute top-4 left-4 flex flex-col gap-2">
                        <Badge variant="secondary" className="glass py-1">
                            {product.brand}
                        </Badge>
                        {product.reviewCount && product.reviewCount > 100 && (
                            <Badge variant="success" className="py-1">Bestseller</Badge>
                        )}
                    </div>

                    <div className="absolute inset-0 bg-ink/5 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-3">
                        {quantity > 0 ? (
                            <div className="flex items-center gap-2 bg-white rounded-full shadow-lg p-1" onClick={(e) => e.preventDefault()}>
                                <Button
                                    variant="secondary"
                                    size="icon"
                                    className="w-8 h-8 rounded-full bg-surface-50 hover:bg-surface-100"
                                    onClick={async (e) => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                        setIsAdding(true);
                                        try {
                                            if (quantity === 1) {
                                                await removeItem(cartItem!.itemId);
                                            } else {
                                                await updateItemQuantity(cartItem!.itemId, quantity - 1);
                                            }
                                        } finally {
                                            setIsAdding(false);
                                        }
                                    }}
                                    disabled={isAdding}
                                    data-testid={`decrease-qty-${product.id}`}
                                >
                                    <Minus size={14} />
                                </Button>
                                <span className="w-8 text-center font-bold text-sm text-ink">{quantity}</span>
                                <Button
                                    variant="secondary"
                                    size="icon"
                                    className="w-8 h-8 rounded-full bg-surface-50 hover:bg-surface-100"
                                    onClick={handleAddToCart}
                                    disabled={isAdding}
                                    data-testid={`increase-qty-${product.id}`}
                                >
                                    <Plus size={14} />
                                </Button>
                            </div>
                        ) : (
                            <Button
                                variant="primary"
                                size="icon"
                                className="rounded-full shadow-lg"
                                onClick={handleAddToCart}
                                isLoading={isAdding}
                                data-testid={`add-to-cart-${product.id}`}
                            >
                                <ShoppingCart size={18} />
                            </Button>
                        )}
                        <Button variant="secondary" size="icon" className="rounded-full shadow-lg">
                            <Eye size={18} />
                        </Button>
                    </div>
                </div>

                <div className="p-5 flex flex-col flex-1">
                    <div className="flex justify-between items-start mb-2">
                        <Link to={`/products/${product.id}`} className="group/title">
                            <h4 className="text-base font-bold text-ink line-clamp-1 group-hover:text-brand group-hover/title:text-brand transition-colors">
                                {product.name}
                            </h4>
                        </Link>
                    </div>

                    <div className="flex items-center gap-1 mb-4 text-amber-500">
                        <Star size={14} fill="currentColor" />
                        <span className="text-xs font-semibold text-slate-500">
                            {product.rating} ({product.reviewCount})
                        </span>
                    </div>

                    <div className="mt-auto flex items-center justify-between">
                        <span className="text-xl font-display font-bold text-ink">
                            ${product.price.toFixed(2)}
                        </span>
                        <span className="text-xs text-slate-400 font-medium tracking-wider uppercase">
                            {product.category}
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
};

export { ProductCard };
