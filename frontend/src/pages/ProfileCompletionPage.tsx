import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Phone, MapPin } from "lucide-react";
import { Input } from "../components/ui/Input";
import { Button } from "../components/ui/Button";
import { useAuth } from "../context/AuthContext";

type AddressForm = {
    name: string;
    line1: string;
    line2: string;
    city: string;
    state: string;
    postalCode: string;
    country: string;
};

const ProfileCompletionPage: React.FC = () => {
    const navigate = useNavigate();
    const { user, isAuthenticated, updateProfile } = useAuth();
    const [phone, setPhone] = useState<string>(user?.phone ?? "");
    const [timezone, setTimezone] = useState<string>(user?.timezone ?? "UTC");
    const [address, setAddress] = useState<AddressForm>({
        name: user?.defaultShippingAddress?.name ?? user?.name ?? "",
        line1: user?.defaultShippingAddress?.line1 ?? "",
        line2: user?.defaultShippingAddress?.line2 ?? "",
        city: user?.defaultShippingAddress?.city ?? "",
        state: user?.defaultShippingAddress?.state ?? "",
        postalCode: user?.defaultShippingAddress?.postalCode ?? "",
        country: user?.defaultShippingAddress?.country ?? "US",
    });
    const [error, setError] = useState<string | null>(null);
    const [isSaving, setIsSaving] = useState(false);

    const isComplete = useMemo(() => {
        return [phone, address.name, address.line1, address.city, address.state, address.postalCode, address.country]
            .every((value) => String(value || "").trim().length > 0);
    }, [phone, address]);

    useEffect(() => {
        if (!isAuthenticated || !user) {
            navigate("/login", { replace: true });
            return;
        }
        if (user.profileComplete) {
            navigate("/", { replace: true });
        }
    }, [isAuthenticated, navigate, user]);

    if (!isAuthenticated || !user || user.profileComplete) {
        return null;
    }

    const onSubmit = async (event: React.FormEvent) => {
        event.preventDefault();
        if (!isComplete) {
            setError("Please complete phone and address fields to continue.");
            return;
        }
        setError(null);
        setIsSaving(true);
        try {
            const nextUser = await updateProfile({
                phone,
                timezone,
                defaultShippingAddress: {
                    name: address.name,
                    line1: address.line1,
                    line2: address.line2 || undefined,
                    city: address.city,
                    state: address.state,
                    postalCode: address.postalCode,
                    country: address.country,
                },
            });
            if (!nextUser.profileComplete) {
                setError("Profile is still incomplete. Please fill all required fields.");
                return;
            }
            navigate("/", { replace: true });
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to update profile.");
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <div className="min-h-[80vh] flex items-center justify-center p-4">
            <div className="w-full max-w-2xl space-y-8 animate-fade-in">
                <div className="text-center space-y-3">
                    <h1 className="text-3xl font-bold">Complete Your Profile</h1>
                    <p className="text-slate-500">
                        Add your mobile number and default shipping address to activate voice support and faster checkout.
                    </p>
                </div>

                <form onSubmit={onSubmit} className="premium-card space-y-6">
                    {error && (
                        <div className="p-3 rounded-xl bg-red-50 border border-red-100 text-red-600 text-sm font-medium">
                            {error}
                        </div>
                    )}

                    <div className="space-y-4">
                        <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                            <Phone size={16} /> Contact
                        </div>
                        <Input
                            label="Mobile Number"
                            placeholder="+1 555 123 4567"
                            value={phone}
                            onChange={(e) => setPhone(e.target.value)}
                            required
                            data-testid="profile-mobile-input"
                        />
                        <Input
                            label="Timezone"
                            placeholder="UTC"
                            value={timezone}
                            onChange={(e) => setTimezone(e.target.value)}
                        />
                    </div>

                    <div className="space-y-4">
                        <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                            <MapPin size={16} /> Default Shipping Address
                        </div>
                        <Input
                            label="Full Name"
                            value={address.name}
                            onChange={(e) => setAddress((prev) => ({ ...prev, name: e.target.value }))}
                            required
                        />
                        <Input
                            label="Address Line 1"
                            value={address.line1}
                            onChange={(e) => setAddress((prev) => ({ ...prev, line1: e.target.value }))}
                            required
                            data-testid="profile-line1-input"
                        />
                        <Input
                            label="Address Line 2 (Optional)"
                            value={address.line2}
                            onChange={(e) => setAddress((prev) => ({ ...prev, line2: e.target.value }))}
                        />
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <Input
                                label="City"
                                value={address.city}
                                onChange={(e) => setAddress((prev) => ({ ...prev, city: e.target.value }))}
                                required
                                data-testid="profile-city-input"
                            />
                            <Input
                                label="State"
                                value={address.state}
                                onChange={(e) => setAddress((prev) => ({ ...prev, state: e.target.value }))}
                                required
                                data-testid="profile-state-input"
                            />
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <Input
                                label="Postal Code"
                                value={address.postalCode}
                                onChange={(e) => setAddress((prev) => ({ ...prev, postalCode: e.target.value }))}
                                required
                                data-testid="profile-postal-input"
                            />
                            <Input
                                label="Country"
                                value={address.country}
                                onChange={(e) => setAddress((prev) => ({ ...prev, country: e.target.value }))}
                                required
                                data-testid="profile-country-input"
                            />
                        </div>
                    </div>

                    <Button type="submit" className="w-full h-12 rounded-2xl gap-2" isLoading={isSaving}>
                        Save And Continue <ArrowRight size={18} />
                    </Button>
                </form>
            </div>
        </div>
    );
};

export { ProfileCompletionPage };
