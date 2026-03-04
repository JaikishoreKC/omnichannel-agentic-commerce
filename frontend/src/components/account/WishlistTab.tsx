import React from "react";
import { Heart, Search } from "lucide-react";
import { Button } from "../ui/Button";
import { useNavigate } from "react-router-dom";

export const WishlistTab: React.FC = () => {
    const navigate = useNavigate();

    return (
        <div className="space-y-6 animate-fade-in">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-pink-50 flex items-center justify-center text-pink-500">
                        <Heart size={20} fill="currentColor" />
                    </div>
                    <div>
                        <h3 className="text-lg font-bold">Your Wishlist</h3>
                        <p className="text-xs text-slate-500">Items you've saved for later</p>
                    </div>
                </div>
            </div>

            <div className="flex flex-col items-center justify-center py-16 text-center space-y-4 border-2 border-dashed border-line rounded-3xl bg-surface-50">
                <div className="w-16 h-16 rounded-full bg-pink-100 flex items-center justify-center text-pink-500 mb-2">
                    <Search size={32} />
                </div>
                <h4 className="text-lg font-bold text-slate-900">Your wishlist is empty</h4>
                <p className="text-sm text-slate-500 max-w-sm">
                    Discover something you love? Save it here so you easily find it later when you are ready to buy.
                </p>
                <Button onClick={() => navigate("/products")} className="rounded-xl mt-4 bg-ink hover:bg-slate-800">
                    Explore Products
                </Button>
            </div>
        </div>
    );
};
