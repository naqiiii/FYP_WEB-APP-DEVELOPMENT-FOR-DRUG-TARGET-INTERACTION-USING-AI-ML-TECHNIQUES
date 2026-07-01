'use client';

import { useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';
import { resetPassword } from '@/services/api-client';

function getPasswordStrength(password) {
    if (!password) return { level: 0, label: '', color: '' };
    let score = 0;
    if (password.length >= 8) score++;
    if (password.length >= 12) score++;
    if (/[A-Z]/.test(password)) score++;
    if (/\d/.test(password)) score++;
    if (/[^A-Za-z0-9]/.test(password)) score++;

    if (score <= 2) return { level: 1, label: 'Weak', color: 'bg-red-500', textColor: 'text-red-500' };
    if (score <= 3) return { level: 2, label: 'Fair', color: 'bg-amber-500', textColor: 'text-amber-500' };
    if (score <= 4) return { level: 3, label: 'Good', color: 'bg-cyan-500', textColor: 'text-cyan-500' };
    return { level: 4, label: 'Strong', color: 'bg-green-700', textColor: 'text-green-700' };
}

function ResetPasswordForm() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const token = searchParams.get('token');

    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [success, setSuccess] = useState(false);
    const [loading, setLoading] = useState(false);

    const strength = getPasswordStrength(password);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');

        if (!token) {
            setError('Missing token. Make sure you used the full link from your email');
            return;
        }

        if (password.length < 8) {
            setError('Password must be at least 8 characters long');
            return;
        }
        if (!/[A-Z]/.test(password)) {
            setError('Password must contain at least one uppercase letter');
            return;
        }
        if (!/\d/.test(password)) {
            setError('Password must contain at least one digit');
            return;
        }

        setLoading(true);
        try {
            await resetPassword(token, password);
            setSuccess(true);
        } catch (err) {
            setError(err?.response?.data?.detail || 'Reset failed. Token might be invalid or expired');
        } finally {
            setLoading(false);
        }
    };

    if (success) {
        return (
            <div className="min-h-screen flex flex-col relative overflow-hidden">
                <Navbar />
                <main className="flex-1 flex items-center justify-center p-6 animate-fade-in relative z-10">
                    <div className="w-full max-w-md">
                        <div className="glass-card p-8 text-center">

                            <div className="mx-auto mb-4 w-12 h-12 rounded-xl bg-green-700/10 border border-green-600/20 flex items-center justify-center">
                                <svg className="w-6 h-6 text-green-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                </svg>
                            </div>

                            <h1 className="text-2xl font-bold tracking-tight mb-2">
                                Password Reset!
                            </h1>

                            <p className="mb-6">
                                Your password has been successfully updated
                            </p>

                            <div className="flex justify-center">
                                <Link href="/login" className="btn-premium px-4 py-2 text-center">
                                    Return to Login
                                </Link>
                            </div>

                        </div>
                    </div>
                </main>
                <Footer />
            </div>
        );
    }

    return (
        <div className="min-h-screen flex flex-col relative overflow-hidden">
            <Navbar />
            <main className="flex-1 flex items-center justify-center p-6 animate-fade-in relative z-10">
                <div className="w-full max-w-md">

                    <div className="text-center mb-8">
                        <h1 className="text-3xl font-bold tracking-tight mb-2">
                            Create New Password
                        </h1>
                        <p className="text-sm text-gray-600 dark:text-gray-600">
                            Please enter your new strong password below
                        </p>
                    </div>

                    <form onSubmit={handleSubmit} className="glass-card p-8">

                        {!token && (
                            <div className="mb-6 p-4 bg-amber-500/10 border border-amber-500/20 text-amber-600 rounded-lg text-sm">
                                No token found in URL — password reset might fail
                            </div>
                        )}

                        {error && (
                            <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 text-red-500 rounded-lg text-sm">
                                {error}
                            </div>
                        )}

                        <div className="space-y-5">
                            <div>
                                <label className="block text-sm font-semibold mb-1.5">
                                    New Password
                                </label>

                                <input
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    required
                                    minLength={8}
                                    className="input-premium"
                                    placeholder="••••••••"
                                />

                                {password.length > 0 && (
                                    <div className="mt-2">
                                        <div className="flex gap-1 mb-1.5">
                                            {[1, 2, 3, 4].map((lvl) => (
                                                <div
                                                    key={lvl}
                                                    className={`h-1 flex-1 rounded-full ${lvl <= strength.level ? strength.color : 'bg-black/10 dark:bg-white/10'}`}
                                                />
                                            ))}
                                        </div>

                                        <p className={`text-xs font-semibold ${strength.textColor}`}>
                                            {strength.label}
                                            <span className="text-gray-700 font-normal ml-1">
                                                — min 8 chars, one uppercase, one digit
                                            </span>
                                        </p>
                                    </div>
                                )}
                            </div>

                            <button
                                type="submit"
                                disabled={loading}
                                className="w-full btn-premium mt-6"
                            >
                                {loading ? 'Resetting...' : 'Reset Password'}
                            </button>
                        </div>
                    </form>
                </div>
            </main>
            <Footer />
        </div>
    );
}

export default function ResetPasswordPage() {
    return (
        <Suspense fallback={<div className="h-screen w-screen flex items-center justify-center">Loading...</div>}>
            <ResetPasswordForm />
        </Suspense>
    );
}
