'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';
import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';

function LoginForm() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const { login, isAuthenticated } = useAuth();

    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (searchParams.get('registered') === 'true') {
            setSuccess('Welcome! Your account has been created. Please sign in below.');
        }
    }, [searchParams]);

    useEffect(() => {
        if (isAuthenticated) {
            const redirect = searchParams.get('redirect') || '/';
            router.push(redirect);
        }
    }, [isAuthenticated, router, searchParams]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setSuccess('');
        setLoading(true);

        try {
            await login(email, password);
            const redirect = searchParams.get('redirect') || '/';
            router.push(redirect);
        } catch (err) {
            const detail = err?.response?.data?.detail;
            const msg = err?.response?.data ? `Error ${err.response.status}: ${JSON.stringify(err.response.data)}` : err?.message;
            setError(detail || msg || 'Unable to sign in. Please check your credentials.');
            console.error('Login error:', err);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex flex-col relative overflow-hidden">
            <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-green-700/10 rounded-full blur-[140px] -z-10 pointer-events-none" />
            <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-cyan-500/8 rounded-full blur-[140px] -z-10 pointer-events-none" />

            <Navbar />

            <main className="flex-1 flex items-center justify-center p-6 animate-fade-in relative z-10">
                <div className="w-full max-w-md">
                    <div className="text-center mb-8">


                        <h1 className="text-3xl font-bold tracking-tight text-gray-900 mb-2">Sign In</h1>
                        <p className="text-gray-700 text-sm">
                            Access your drug target interaction prediction App
                        </p>
                    </div>

                    <form onSubmit={handleSubmit} className="glass-card p-8">
                        {success && (
                            <div className="mb-6 p-4 bg-green-700/10 border border-green-700/20 text-green-400 rounded-lg text-sm flex items-start gap-3">
                                <svg className="w-5 h-5 text-green-600 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                </svg>
                                <span>{success}</span>
                            </div>
                        )}

                        {error && (
                            <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-sm flex items-start gap-3">
                                <svg className="w-5 h-5 text-red-400 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                </svg>
                                <span>{error}</span>
                            </div>
                        )}

                        <div className="space-y-5">
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1.5">Email Address</label>
                                <input
                                    type="email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    required
                                    className="input-premium"
                                    placeholder="name@example.com"
                                />
                            </div>

                            <div>
                                <div className="flex items-center justify-between mb-1.5">
                                    <label className="block text-sm font-semibold text-gray-700">Password</label>
                                    <Link href="/forgot-password" className="text-xs text-green-800 hover:text-green-900 font-semibold">
                                        Forgot Password?
                                    </Link>
                                </div>
                                <input
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    required
                                    className="input-premium"
                                    placeholder="••••••••"
                                />
                            </div>

                            <button
                                type="submit"
                                disabled={loading}
                                className="w-full btn-premium mt-6 group"
                            >
                                {loading ? (
                                    <span className="flex items-center gap-2">
                                        <svg className="animate-scientific-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                        </svg>
                                        Authenticating…
                                    </span>
                                ) : (
                                    'Sign In'
                                )}
                            </button>
                        </div>

                        <div className="mt-6 text-center text-sm text-gray-700 border-t border-gray-100 pt-6">
                            Don't have an account?{' '}
                            <Link href="/signup" className="text-green-800 hover:text-green-900 font-semibold transition-colors">
                                Create an account
                            </Link>
                        </div>
                    </form>
                </div>
            </main>

            <Footer />
        </div>
    );
}

export default function LoginPage() {
    return (
        <Suspense
            fallback={
                <div className="min-h-screen bg-background flex items-center justify-center">
                    <svg className="animate-scientific-spin h-8 w-8 text-green-600" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                </div>
            }
        >
            <LoginForm />
        </Suspense>
    );
}
