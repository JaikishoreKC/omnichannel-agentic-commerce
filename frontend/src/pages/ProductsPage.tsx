import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Search, SlidersHorizontal, Grid3X3, List } from "lucide-react";
import { fetchProducts } from "../api";
import type { Product } from "../types";
import { ProductCard } from "../components/features/ProductCard";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Skeleton } from "../components/ui/Skeleton";
import { cn } from "../utils/cn";

const ProductsPage: React.FC = () => {
    const [searchParams, setSearchParams] = useSearchParams();
    const [products, setProducts] = useState<Product[]>([]);
    const [pagination, setPagination] = useState({ page: 1, total: 0, pages: 1 });
    const [isLoading, setIsLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState(searchParams.get("q") || "");
    const [viewMode, setViewMode] = useState<"grid" | "list">("grid");

    const categories = ["All", "Shoes", "Clothing", "Accessories", "Electronics", "Home"];
    const activeCategory = searchParams.get("category") || "All";
    const currentPage = parseInt(searchParams.get("page") || "1", 10);

    useEffect(() => {
        const load = async () => {
            try {
                setIsLoading(true);
                const data = await fetchProducts({
                    category: activeCategory,
                    query: searchQuery,
                    page: currentPage,
                    limit: 12
                });
                setProducts(data.products);
                setPagination(data.pagination);
            } finally {
                setIsLoading(false);
            }
        };
        load();
    }, [activeCategory, searchQuery, currentPage]);

    const setPage = (page: number) => {
        const params = new URLSearchParams(searchParams);
        params.set("page", page.toString());
        setSearchParams(params);
        window.scrollTo({ top: 0, behavior: "smooth" });
    };

    const toggleCategory = (cat: string) => {
        const params = new URLSearchParams(); // Reset all filters when changing category basically, or just category
        if (cat !== "All") params.set("category", cat.toLowerCase());
        if (searchQuery) params.set("q", searchQuery);
        params.set("page", "1");
        setSearchParams(params);
    };

    return (
        <div className="space-y-8 animate-fade-in">
            {/* Header & Search */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                <div>
                    <h1 className="text-4xl font-bold mb-2">Explore <span className="text-brand">Products</span></h1>
                    <p className="text-slate-500">{pagination.total} items found</p>
                </div>

                <div className="flex items-center gap-2 max-w-md w-full">
                    <div className="relative flex-1">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                        <Input
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            placeholder="Search products..."
                            className="pl-12 bg-white"
                        />
                    </div>
                    <Button
                        variant="secondary"
                        size="icon"
                        className="shrink-0 rounded-xl"
                        aria-label="Open filters"
                        title="Filters"
                    >
                        <SlidersHorizontal size={18} />
                    </Button>
                </div>
            </div>

            {/* Filters & View Switcher */}
            <div className="flex items-center justify-between border-b border-line pb-6">
                <div className="flex items-center gap-2 overflow-x-auto pb-2 md:pb-0 scrollbar-hide">
                    {categories.map((cat) => (
                        <button
                            key={cat}
                            onClick={() => toggleCategory(cat)}
                            className={cn(
                                "px-5 py-2 rounded-full text-sm font-medium transition-all whitespace-nowrap",
                                activeCategory.toLowerCase() === cat.toLowerCase() || (cat === "All" && activeCategory === "All")
                                    ? "bg-ink text-white shadow-premium"
                                    : "bg-surface-100 text-slate-600 hover:bg-surface-200"
                            )}
                        >
                            {cat}
                        </button>
                    ))}
                </div>

                <div className="hidden sm:flex items-center gap-1 bg-surface-100 p-1 rounded-xl border border-line">
                    <button
                        onClick={() => setViewMode("grid")}
                        className={cn("p-2 rounded-lg transition-all", viewMode === "grid" ? "bg-white shadow-sm text-brand" : "text-slate-400 hover:text-slate-600")}
                        aria-label="Grid view"
                        title="Grid view"
                    >
                        <Grid3X3 size={18} />
                    </button>
                    <button
                        onClick={() => setViewMode("list")}
                        className={cn("p-2 rounded-lg transition-all", viewMode === "list" ? "bg-white shadow-sm text-brand" : "text-slate-400 hover:text-slate-600")}
                        aria-label="List view"
                        title="List view"
                    >
                        <List size={18} />
                    </button>
                </div>
            </div>

            {/* Products Grid */}
            <div className={cn(
                "grid gap-6",
                viewMode === "grid" ? "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" : "grid-cols-1"
            )}>
                {isLoading ? (
                    Array(8).fill(0).map((_, i) => (
                        <div key={i} className="space-y-4">
                            <Skeleton className="aspect-square rounded-2xl" />
                            <Skeleton className="h-4 w-2/3" />
                            <Skeleton className="h-4 w-1/2" />
                        </div>
                    ))
                ) : products.length > 0 ? (
                    products.map((p) => (
                        <ProductCard key={p.id} product={p} />
                    ))
                ) : (
                    <div className="col-span-full py-24 flex flex-col items-center justify-center text-center space-y-4">
                        <div className="w-16 h-16 rounded-full bg-surface-100 flex items-center justify-center text-slate-400">
                            <Search size={32} />
                        </div>
                        <div className="space-y-1">
                            <h3 className="text-xl font-bold">No products found</h3>
                            <p className="text-slate-500">Try adjusting your search or filters to find what you're looking for.</p>
                        </div>
                        <Button variant="outline" onClick={() => { setSearchQuery(""); toggleCategory("All"); }}>
                            Clear all filters
                        </Button>
                    </div>
                )}
            </div>

            {/* Pagination */}
            {pagination.pages > 1 && (
                <div className="flex items-center justify-center gap-2 pt-8">
                    <Button
                        variant="ghost"
                        disabled={pagination.page <= 1}
                        onClick={() => setPage(pagination.page - 1)}
                        className="rounded-xl px-4"
                    >
                        Previous
                    </Button>

                    <div className="flex items-center gap-1">
                        {Array.from({ length: pagination.pages }, (_, i) => i + 1).map((p) => (
                            <Button
                                key={p}
                                variant={pagination.page === p ? "primary" : "ghost"}
                                onClick={() => setPage(p)}
                                className={cn(
                                    "w-10 h-10 p-0 rounded-xl transition-all",
                                    pagination.page === p ? "shadow-md scale-105" : "text-slate-600 hover:bg-surface-100"
                                )}
                            >
                                {p}
                            </Button>
                        ))}
                    </div>

                    <Button
                        variant="ghost"
                        disabled={pagination.page >= pagination.pages}
                        onClick={() => setPage(pagination.page + 1)}
                        className="rounded-xl px-4"
                    >
                        Next
                    </Button>
                </div>
            )}
        </div>
    );
};

export { ProductsPage };
