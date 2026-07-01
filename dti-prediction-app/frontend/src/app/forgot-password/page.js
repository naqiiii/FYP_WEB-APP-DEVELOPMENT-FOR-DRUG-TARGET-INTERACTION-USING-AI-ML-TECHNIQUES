'use client';

import { useState } from 'react';
import Link from 'next/link';
import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';
import { forgotPassword } from '@/services/api-client';

export default function ForgotPasswordPage() {
    const [email, setEmail] = useState('');
    const [loading, setLoading] = useState(false);
    const [sent, setSent] = useState(false);
    const [error, setError] = useState('');

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError('');

        try {
            await forgotPassword(email);
            setSent(true);
        } catch (err) {
            setError(err?.response?.data?.detail || 'Failed to request password reset. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex flex-col relative overflow-hidden">
            <Navbar />
            <main className="flex-1 flex items-center justify-center p-6 animate-fade-in relative z-10">
                <div className="w-full max-w-md">
                    <div className="text-center mb-8">
                        <h1 className="text-3xl font-bold tracking-tight mb-2">Forgot Password</h1>
                        <p className="text-sm">
                            Enter your email to receive a password reset link.
                        </p>
                    </div>

                    <form onSubmit={handleSubmit} className="glass-card p-8">
                        {sent ? (
                            <div className="text-center">
                                <div className="mx-auto mb-4 w-12 h-12 rounded-xl bg-green-700/10 border border-green-600/20 flex items-center justify-center">
                                    <svg className="w-6 h-6 text-green-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                    </svg>
                                </div>
                                <h2 className="text-xl font-bold mb-3">Email Sent</h2>
                                <p className="text-sm mb-6">
                                    If an account exists for {email}, we have sent a password reset link.
                                </p>
                                <div className="flex justify-center">
                                    <Link href="/login" className="btn-premium px-4 py-2 text-center">
                                        Return to Login
                                    </Link>
                                </div>
                            </div>
                        ) : (
                            <>
                                {error && (
                                    <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 text-red-500 rounded-lg text-sm">
                                        {error}
                                    </div>
                                )}
                                <div className="space-y-5">
                                    <div>
                                        <label className="block text-sm font-semibold mb-1.5">Email Address</label>
                                        <input
                                            type="email"
                                            value={email}
                                            onChange={(e) => setEmail(e.target.value)}
                                            required
                                            className="input-premium"
                                            placeholder="name@example.com"
                                        />
                                    </div>
                                    <button
                                        type="submit"
                                        disabled={loading}
                                        className="w-full btn-premium mt-6"
                                    >
                                        {loading ? 'Sending link...' : 'Send Reset Link'}
                                    </button>
                                </div>
                                <div className="mt-6 text-center text-sm border-t border-black/5 dark:border-gray-200 pt-6">
                                    Remember your password?{' '}
                                    <Link href="/login" className="text-green-800 dark:text-green-600 hover:underline font-semibold">
                                        Sign in
                                    </Link>
                                </div>
                            </>
                        )}
                    </form>
                </div>
            </main>
            <Footer />
        </div>
    );
}
