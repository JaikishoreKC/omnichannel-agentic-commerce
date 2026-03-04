import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Star, ShoppingCart, ArrowLeft, ShieldCheck, Truck, RotateCcw, Plus, Minus } from "lucide-react";
import { fetchProduct, addProductReview } from "../api";
import type { Product, ProductVariant } from "../types";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Skeleton } from "../components/ui/Skeleton";
import { cn } from "../utils/cn";
import { useCart } from "../context/CartContext";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

const ProductDetailPage: React.FC = () => {
    const { productId } = useParams<{ productId: string }>();
    const navigate = useNavigate();
    const { addItem, updateItemQuantity, removeItem, cart } = useCart();
    const { user } = useAuth();
    const { addToast } = useToast();

    const [product, setProduct] = useState<Product | null>(null);
    const [selectedVariant, setSelectedVariant] = useState<ProductVariant | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isAdding, setIsAdding] = useState(false);
    const [activeImage, setActiveImage] = useState(0);

    // Review state
    const [reviewText, setReviewText] = useState("");
    const [reviewRating, setReviewRating] = useState(5);
    const [isSubmittingReview, setIsSubmittingReview] = useState(false);

    useEffect(() => {
        const load = async () => {
            if (!productId) return;
            try {
                setIsLoading(true);
                const data = await fetchProduct(productId);
                setProduct(data);
                const initialVariant = data.variants.find(v => v.inStock) || data.variants[0];
                setSelectedVariant(initialVariant);
            } finally {
                setIsLoading(false);
            }
        };
        load();
    }, [productId]);

    const cartItem = cart?.items.find((item: any) => item.productId === product?.id && item.variantId === selectedVariant?.id);
    const quantity = cartItem?.quantity || 0;

    const handleAddToCart = async () => {
        if (!product || !selectedVariant) return;
        setIsAdding(true);
        try {
            if (quantity > 0) {
                await updateItemQuantity(cartItem!.itemId, quantity + 1);
            } else {
                await addItem(product.id, selectedVariant.id, 1);
            }
        } finally {
            setIsAdding(false);
        }
    };

    const handleReviewSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!user) {
            addToast("You must be logged in to leave a review.", "warning");
            navigate("/login");
            return;
        }
        if (!reviewText.trim()) return;

        setIsSubmittingReview(true);
        try {
            await addProductReview(product!.id, {
                rating: reviewRating,
                comment: reviewText.trim()
            });
            addToast("Review submitted successfully", "success");
            setReviewText("");
            setReviewRating(5);
            // Reload product data to get the new review
            const updatedProduct = await fetchProduct(product!.id);
            setProduct(updatedProduct);
        } catch (err: any) {
            addToast(err.message || "Failed to submit review", "error");
        } finally {
            setIsSubmittingReview(false);
        }
    };

    if (isLoading) {
        return (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
                <Skeleton className="aspect-square rounded-3xl" />
                <div className="space-y-6">
                    <Skeleton className="h-10 w-3/4" />
                    <Skeleton className="h-6 w-1/4" />
                    <Skeleton className="h-32 w-full" />
                    <div className="flex gap-4">
                        <Skeleton className="h-14 flex-1 rounded-2xl" />
                        <Skeleton className="h-14 w-14 rounded-2xl" />
                    </div>
                </div>
            </div>
        );
    }

    if (!product) return <div className="text-center py-24">Product not found</div>;

    const reviews = product.reviews || [];

    return (
        <div className="space-y-12 animate-fade-in max-w-6xl mx-auto">
            {/* Breadcrumb / Back */}
            <button
                onClick={() => navigate(-1)}
                className="flex items-center gap-2 text-sm font-bold text-slate-500 hover:text-slate-900 transition-colors"
            >
                <ArrowLeft size={16} /> Back
            </button>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-12 lg:gap-16">
                {/* Images */}
                <div className="space-y-4">
                    <div className="aspect-square rounded-[40px] bg-surface-100 overflow-hidden border border-line flex items-center justify-center p-12">
                        <img
                            src={product.images[activeImage]}
                            alt={product.name}
                            className="w-full h-full object-contain"
                        />
                    </div>
                    <div className="flex gap-4 overflow-x-auto pb-2">
                        {product.images.map((img, idx) => (
                            <button
                                key={idx}
                                onClick={() => setActiveImage(idx)}
                                className={cn(
                                    "w-24 h-24 rounded-2xl border-2 transition-all p-4 bg-surface-50 shrink-0",
                                    activeImage === idx ? "border-brand shadow-sm" : "border-transparent opacity-60 hover:opacity-100"
                                )}
                            >
                                <img src={img} alt={`${product.name} ${idx}`} className="w-full h-full object-contain" />
                            </button>
                        ))}
                    </div>
                </div>

                {/* Info */}
                <div className="space-y-8">
                    <div className="space-y-4">
                        <div className="flex items-center gap-2">
                            <Badge variant="secondary">{product.category}</Badge>
                            <Badge variant="outline">{product.brand}</Badge>
                        </div>
                        <h1 className="text-5xl font-bold leading-tight">{product.name}</h1>
                        <div className="flex items-center gap-4">
                            <div className="flex items-center gap-1 text-amber-500">
                                <Star size={18} fill="currentColor" />
                                <span className="text-sm font-bold text-ink">{product.rating}</span>
                            </div>
                            <span className="text-sm text-slate-400 font-medium">({product.reviewCount} verified reviews)</span>
                        </div>
                    </div>

                    <div className="text-4xl font-display font-bold text-ink">
                        ${product.price.toFixed(2)}
                    </div>

                    <p className="text-lg text-slate-500 leading-relaxed">
                        {product.description}
                    </p>

                    {/* Variants */}
                    <div className="space-y-4">
                        <h4 className="font-bold">Select Style & Size</h4>
                        <div className="flex flex-wrap gap-3">
                            {product.variants.map((v) => (
                                <button
                                    key={v.id}
                                    onClick={() => setSelectedVariant(v)}
                                    disabled={!v.inStock}
                                    className={cn(
                                        "px-6 py-3 rounded-2xl border text-sm font-bold transition-all",
                                        selectedVariant?.id === v.id
                                            ? "border-brand bg-brand/5 text-brand shadow-sm"
                                            : "border-line text-slate-500 hover:border-brand/40",
                                        !v.inStock && "opacity-30 cursor-not-allowed grayscale"
                                    )}
                                >
                                    {v.color} - {v.size}
                                    {!v.inStock && " (Sold Out)"}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="flex gap-4 pt-4">
                        {quantity > 0 ? (
                            <div className="flex-1 flex items-center justify-between bg-surface-50 rounded-2xl h-16 px-6 gap-6 shadow-sm border border-line">
                                <Button
                                    variant="secondary"
                                    size="icon"
                                    className="w-10 h-10 rounded-xl bg-white shadow-sm hover:bg-surface-100"
                                    onClick={async () => {
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
                                    <Minus size={18} />
                                </Button>
                                <div className="text-xl font-bold text-ink w-8 text-center">{quantity}</div>
                                <Button
                                    variant="secondary"
                                    size="icon"
                                    className="w-10 h-10 rounded-xl bg-white shadow-sm hover:bg-surface-100"
                                    onClick={handleAddToCart}
                                    disabled={isAdding}
                                    data-testid={`increase-qty-${product.id}`}
                                >
                                    <Plus size={18} />
                                </Button>
                            </div>
                        ) : (
                            <Button
                                size="lg"
                                className="flex-1 rounded-2xl gap-3 shadow-lg h-16"
                                onClick={handleAddToCart}
                                isLoading={isAdding}
                            >
                                <ShoppingCart size={20} /> Add to Bag
                            </Button>
                        )}
                    </div>

                    {/* Features */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 pt-8 border-t border-line">
                        {[
                            { icon: ShieldCheck, label: "2 Year Warranty" },
                            { icon: Truck, label: "Express Shipping" },
                            { icon: RotateCcw, label: "30-Day Returns" }
                        ].map((f, i) => (
                            <div key={i} className="flex flex-col items-center text-center gap-2">
                                <div className="w-10 h-10 rounded-xl bg-surface-100 flex items-center justify-center text-slate-500">
                                    <f.icon size={20} />
                                </div>
                                <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">{f.label}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Reviews Section */}
            <div className="pt-12 border-t border-line space-y-12 pb-24">
                <div className="flex flex-col lg:flex-row gap-16">
                    {/* Left: Review Stats & Form */}
                    <div className="lg:w-1/3 space-y-8">
                        <div className="space-y-4">
                            <h3 className="text-3xl font-bold">Customer Reviews</h3>
                            <div className="flex items-center gap-6">
                                <div className="text-6xl font-black text-ink">{product.rating.toFixed(1)}</div>
                                <div>
                                    <div className="flex gap-0.5 text-amber-500 mb-1">
                                        {[1, 2, 3, 4, 5].map((s) => (
                                            <Star key={s} size={20} fill={s <= Math.round(product.rating) ? "currentColor" : "none"} />
                                        ))}
                                    </div>
                                    <p className="text-sm text-slate-500 font-bold">Based on {product.reviewCount} reviews</p>
                                </div>
                            </div>
                        </div>

                        {/* Submit Review Form */}
                        <div className="premium-card bg-surface-50 border-none shadow-none p-8 space-y-6">
                            <h4 className="font-bold text-xl">Leave a review</h4>
                            <form onSubmit={handleReviewSubmit} className="space-y-4">
                                <div className="flex gap-2">
                                    {[1, 2, 3, 4, 5].map((s) => (
                                        <button
                                            key={s}
                                            type="button"
                                            onClick={() => setReviewRating(s)}
                                            className={cn(
                                                "w-10 h-10 rounded-xl flex items-center justify-center transition-all",
                                                reviewRating >= s ? "bg-amber-100 text-amber-600 shadow-sm" : "bg-white text-slate-300 border border-line"
                                            )}
                                        >
                                            <Star size={20} fill={reviewRating >= s ? "currentColor" : "none"} />
                                        </button>
                                    ))}
                                </div>
                                <textarea
                                    className="w-full h-32 p-4 bg-white border border-line rounded-2xl focus:ring-2 focus:ring-brand focus:border-transparent transition-all outline-none resize-none text-sm"
                                    placeholder="Tell us what you liked (or didn't) about this product..."
                                    value={reviewText}
                                    onChange={(e) => setReviewText(e.target.value)}
                                    required
                                />
                                <Button
                                    type="submit"
                                    className="w-full rounded-xl gap-2 font-bold py-4"
                                    isLoading={isSubmittingReview}
                                    disabled={!reviewText.trim()}
                                >
                                    Submit Review
                                </Button>
                                {!user && <p className="text-[10px] text-center text-slate-400">You must be signed in to submit a review.</p>}
                            </form>
                        </div>
                    </div>

                    {/* Right: Reviews List */}
                    <div className="flex-1 space-y-8">
                        {reviews.length > 0 ? (
                            <div className="divide-y divide-line">
                                {reviews.map((r, i) => (
                                    <div key={i} className="py-8 first:pt-0 animate-fade-in" style={{ animationDelay: `${i * 100}ms` }}>
                                        <div className="flex items-center gap-4 mb-4">
                                            <div className="w-12 h-12 rounded-full bg-surface-200 border border-line flex items-center justify-center text-slate-500 font-bold">
                                                {r.userId.slice(-2).toUpperCase()}
                                            </div>
                                            <div>
                                                <div className="flex gap-0.5 text-amber-500 mb-1">
                                                    {[1, 2, 3, 4, 5].map((s) => (
                                                        <Star key={s} size={14} fill={s <= r.rating ? "currentColor" : "none"} />
                                                    ))}
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-sm font-bold text-ink">Verified Owner</span>
                                                    <span className="text-[10px] text-slate-400 uppercase tracking-widest font-black">• {new Date(r.createdAt).toLocaleDateString()}</span>
                                                </div>
                                            </div>
                                        </div>
                                        <p className="text-slate-600 leading-relaxed text-sm">{r.comment}</p>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="flex flex-col items-center justify-center py-24 text-center space-y-4 border-2 border-dashed border-line rounded-[40px] bg-surface-50">
                                <Star size={40} className="text-slate-200" />
                                <div className="space-y-1">
                                    <h4 className="font-bold text-slate-900">No reviews yet</h4>
                                    <p className="text-sm text-slate-500">Be the first to share your experience!</p>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};


export { ProductDetailPage };
