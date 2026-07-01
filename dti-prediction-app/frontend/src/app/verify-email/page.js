'use client';

import { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';
import { verifyEmail } from '@/services/api-client';

function VerifyEmailForm() {
    const searchParams = useSearchParams();
    const token = searchParams.get('token');

    const [status, setStatus] = useState('verifying'); // verifying, success, error
    const [message, setMessage] = useState('');

    useEffect(() => {
        if (!token) {
            setStatus('error');
            setMessage('No verification token provided. Please check your email link.');
            return;
        }

        verifyEmail(token)
            .then(res => {
                setStatus('success');
                setMessage(res.message || 'Email verified successfully!');
            })
            .catch(err => {
                setStatus('error');
                const detail = err?.response?.data?.detail;
                setMessage(detail || 'Verification failed. The link might be expired or invalid.');
            });
    }, [token]);

    return (
        <div className="min-h-screen flex flex-col relative overflow-hidden">
            <Navbar />
            <main className="flex-1 flex items-center justify-center p-6 animate-fade-in relative z-10">
                <div className="w-full max-w-md">
                    <div className="glass-card p-8 text-center">
                        {status === 'verifying' && (
                            <>
                                <h1 className="text-2xl font-bold tracking-tight mb-4">Verifying your email...</h1>
                                <svg className="animate-scientific-spin h-8 w-8 text-green-700 mx-auto" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                </svg>
                            </>
                        )}

                        {status === 'success' && (
                            <>
                                <div className="text-center">

                                    <div className="mx-auto mb-4 w-12 h-12 rounded-xl bg-green-700/10 border border-green-600/20 flex items-center justify-center">
                                        <svg className="w-6 h-6 text-green-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                        </svg>
                                    </div>

                                    <h1 className="text-2xl font-bold tracking-tight mb-2">
                                        Verified!
                                    </h1>

                                    <p className="mb-6">
                                        {message}
                                    </p>

                                    <div className="flex justify-center mt-2">
                                        <Link
                                            href="/login"
                                            className="btn-premium px-8 py-2.5 text-center"
                                        >
                                            Go to Login
                                        </Link>
                                    </div>

                                </div>
                            </>
                        )}

                        {status === 'error' && (
                            <>
                                <div className="mx-auto mb-4 w-12 h-12 rounded-xl bg-red-500/10 border border-red-400/20 flex items-center justify-center">
                                    <svg className="w-6 h-6 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                    </svg>
                                </div>
                                <h1 className="text-2xl font-bold tracking-tight mb-2">Verification Failed</h1>
                                <p className="mb-6">{message}</p>
                                <Link href="/login" className="text-green-700 hover:underline">
                                    Return to Login
                                </Link>
                            </>
                        )}
                    </div>
                </div>
            </main>
            <Footer />
        </div>
    );
}

export default function VerifyEmailPage() {
    return (
        <Suspense fallback={<div className="h-screen w-screen flex items-center justify-center">Loading...</div>}>
            <VerifyEmailForm />
        </Suspense>
    );
}
