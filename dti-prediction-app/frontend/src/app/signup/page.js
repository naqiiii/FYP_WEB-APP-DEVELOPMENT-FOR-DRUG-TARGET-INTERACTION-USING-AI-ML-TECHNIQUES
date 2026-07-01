'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { signup } from '@/services/api-client';
import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';

// Helper to determine password complexity profile
function getPasswordStrength(password) {
    if (!password) return { level: 0, label: '', color: '' };
    let score = 0;
    if (password.length >= 8) score++;
    if (password.length >= 12) score++;
    if (/[A-Z]/.test(password)) score++;
    if (/\d/.test(password)) score++;
    if (/[^A-Za-z0-9]/.test(password)) score++;

    if (score <= 2) return { level: 1, label: 'Weak', color: 'bg-red-500', textColor: 'text-red-400' };
    if (score <= 3) return { level: 2, label: 'Fair', color: 'bg-amber-500', textColor: 'text-amber-400' };
    if (score <= 4) return { level: 3, label: 'Good', color: 'bg-cyan-500', textColor: 'text-cyan-400' };
    return { level: 4, label: 'Strong', color: 'bg-green-700', textColor: 'text-green-600' };
}

export default function SignupPage() {
    const router = useRouter();
    const [fullName, setFullName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const strength = getPasswordStrength(password);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');

        if (password !== confirmPassword) {
            setError('Passwords do not match.');
            return;
        }

        if (password.length < 8) {
            setError('Password must be at least 8 characters long.');
            return;
        }
        if (!/[A-Z]/.test(password)) {
            setError('Password must contain at least one uppercase letter.');
            return;
        }
        if (!/\d/.test(password)) {
            setError('Password must contain at least one digit.');
            return;
        }

        setLoading(true);
        try {
            await signup(email, password, fullName);
            router.push('/login?registered=true');
        } catch (err) {
            const detail = err?.response?.data?.detail;
            const msg = err?.response?.data
                ? `Error ${err.response.status}: ${JSON.stringify(err.response.data)}`
                : err?.message;
            setError(detail || msg || 'Registration failed. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex flex-col relative overflow-hidden">

            <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-green-700/10 rounded-full blur-[140px] -z-10 pointer-events-none" />
            <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-cyan-500/8 rounded-full blur-[140px] -z-10 pointer-events-none" />

            <Navbar />

            <main className="flex-1 flex items-center justify-center p-6 relative z-10 my-8">
                <div className="w-full max-w-md">

                    <div className="text-center mb-8">
                        <h1 className="text-3xl font-bold tracking-tight text-gray-900 mb-2">
                            Join DTI Predict
                        </h1>
                        <p className="text-gray-700 text-sm">
                            Create your account to start predicting drug–target interactions.
                        </p>
                    </div>

                    <form onSubmit={handleSubmit} className="glass-card p-8">

                        {error && (
                            <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-sm">
                                {error}
                            </div>
                        )}

                        <div className="space-y-5">

                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1.5">Full Name</label>
                                <input
                                    type="text"
                                    value={fullName}
                                    onChange={(e) => setFullName(e.target.value)}
                                    required
                                    className="input-premium"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1.5">Email Address</label>
                                <input
                                    type="email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    required
                                    className="input-premium"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1.5">Password</label>
                                <input
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    required
                                    className="input-premium"
                                />

                                {password.length > 0 && (
                                    <div className="mt-2">
                                        <div className="flex gap-1 mb-1.5">
                                            {[1, 2, 3, 4].map((lvl) => (
                                                <div key={lvl} className={`h-1 flex-1 rounded-full ${lvl <= strength.level ? strength.color : 'bg-white/10'}`} />
                                            ))}
                                        </div>
                                        <p className={`text-xs font-semibold ${strength.textColor}`}>
                                            {strength.label}
                                        </p>
                                    </div>
                                )}
                            </div>

                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1.5">Confirm Password</label>
                                <input
                                    type="password"
                                    value={confirmPassword}
                                    onChange={(e) => setConfirmPassword(e.target.value)}
                                    required
                                    className="input-premium"
                                />
                            </div>

                            <button
                                type="submit"
                                disabled={loading}
                                className="w-full btn-premium mt-6"
                            >
                                {loading ? 'Creating account…' : 'Create Account'}
                            </button>
                        </div>

                        <div className="mt-6 text-center text-sm text-gray-700 border-t border-gray-100 pt-6">
                            Already have an account?{' '}
                            <Link href="/login" className="text-green-800 hover:text-green-900 font-semibold">
                                Sign in instead
                            </Link>
                        </div>

                    </form>
                </div>
            </main>

            <Footer />
        </div>
    );
}
