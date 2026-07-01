'use client';

import Link from 'next/link';
import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';
import { useAuth } from '@/context/AuthContext';

export default function LandingPage() {
    const { isAuthenticated, loading } = useAuth();

    return (
        <div className="min-h-screen flex flex-col relative overflow-hidden">
            {/* Soft decorative background glows */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-green-700/8 rounded-full blur-[160px] -z-10 pointer-events-none" />
            <div className="absolute bottom-0 right-0 w-[500px] h-[500px] bg-cyan-500/6 rounded-full blur-[140px] -z-10 pointer-events-none" />

            <Navbar />

            <section className="flex-1 flex items-center justify-center px-6 py-20 animate-fade-in">
                <div className="max-w-3xl text-center">

                    <h1 className="text-4xl md:text-5xl font-bold tracking-tight text-foreground mb-4 leading-tight">
                        Predict Drug Target Interactions For Screening
                        Of Drugs
                    </h1>

                    <p className="text-muted-foreground text-lg md:text-xl max-w-2xl mx-auto mb-10 leading-relaxed">
                        Our advanced deep learning architecture enables powerful single-pair DTI predictions,
                        rapid drug candidate screening, and vast protein target screening for drug repurposing.
                    </p>

                    {!loading && (
                        isAuthenticated ? (
                            <div className="flex flex-col sm:flex-row gap-3 justify-center mb-16">
                                <Link href="/dashboard" className="btn-premium px-8 py-3 text-base">
                                    Go to Dashboard
                                </Link>
                            </div>
                        ) : (
                            <div className="flex flex-col sm:flex-row gap-3 justify-center mb-16">
                                <Link href="/signup" className="btn-premium px-8 py-3 text-base">
                                    Get Started — Free
                                </Link>
                                <Link href="/login" className="btn-ghost px-8 py-3 text-base border border-border">
                                    Sign In
                                </Link>
                            </div>
                        )
                    )}

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-left mt-8">
                        {[
                            {
                                id: '01',
                                title: 'Single Pair Prediction',
                                desc: 'Test a single drug candidate against a single protein target for an immediate, high-fidelity binding affinity estimation.',
                            },
                            {
                                id: '02',
                                title: 'Batch Drug Screening',
                                desc: 'Accelerate discovery by screening multiple drug candidate SMILES simultaneously against a specific protein sequence.',
                            },
                            {
                                id: '03',
                                title: 'Batch Protein Screening',
                                desc: 'Support drug repurposing by testing a known drug against a vast library of protein targets to identify new interactions.',
                            },
                        ].map((item) => (
                            <div key={item.id} className="glass-card p-6 group hover:border-green-700/30 transition-all duration-300">
                                <h3 className="text-foreground font-bold mb-3 text-lg">{item.title}</h3>
                                <p className="text-sm text-muted-foreground leading-relaxed">{item.desc}</p>
                            </div>
                        ))}
                    </div>

                </div>
            </section>

            <Footer />
        </div>
    );
}
