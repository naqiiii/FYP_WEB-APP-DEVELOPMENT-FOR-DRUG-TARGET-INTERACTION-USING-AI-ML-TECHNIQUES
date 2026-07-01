'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';
import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';
import ProteinSequencePanel from '@/components/ProteinSequencePanel';
import { safeNum, formatFixed } from '@/utils/numbers';

export default function ResultPage() {
    const router = useRouter();
    const { isAuthenticated, loading: authLoading } = useAuth();
    const [batchState, setBatchState] = useState(null);
    const [selectedIndex, setSelectedIndex] = useState(0);
    const [copied, setCopied] = useState(false);
    const [displayLimit, setDisplayLimit] = useState('All');

    useEffect(() => {
        const storedResult = sessionStorage.getItem('predictionResult');
        if (!storedResult) return;
        try {
            setBatchState(JSON.parse(storedResult));
        } catch {
            sessionStorage.removeItem('predictionResult');
            setBatchState(null);
        }
    }, []);

    useEffect(() => {
        if (!batchState?.data?.length) return;
        setSelectedIndex(0);
    }, [batchState?.data]);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) router.push('/login');
    }, [authLoading, isAuthenticated, router]);

    const rankedData = useMemo(() => {
        if (!batchState?.data) return [];
        if (!batchState.isBatch) return batchState.data;
        return [...batchState.data].sort((a, b) => {
            return (b.log_affinity ?? 0) - (a.log_affinity ?? 0);
        });
    }, [batchState]);

    const selectedRow = rankedData[selectedIndex] ?? rankedData[0];

    const drugDisplay =
        selectedRow?.drug_label ||
        (selectedRow?.drug_smiles
            ? selectedRow.drug_smiles.length > 56
                ? `${selectedRow.drug_smiles.slice(0, 56)}...`
                : selectedRow.drug_smiles
            : '');

    const proteinDisplay =
        selectedRow?.protein_label ||
        (selectedRow?.protein_sequence
            ? `Amino-acid sequence (${selectedRow.protein_sequence.replace(/\s/g, '').length} residues)`
            : '');

    // Calculate gauge percentage for binding affinity based on model-specific ranges
    const affinityGaugePct = (() => {
        const num = safeNum(selectedRow?.log_affinity);
        if (num === null) return 0;
        const min = selectedRow?.metadata?.gauge_min ?? 0.3;
        const max = selectedRow?.metadata?.gauge_max ?? 1.7;
        const range = max - min || 1;
        return Math.min(100, Math.max(0, ((num - min) / range) * 100));
    })();

    const getStrengthInfo = (pKd) => {
        const num = safeNum(pKd);
        if (num === null) return { label: 'Score unavailable', color: 'gray', bg: 'bg-secondary', border: 'border-border', text: 'text-muted-foreground' };

        const strong = selectedRow?.metadata?.threshold_strong ?? 7.0;
        const moderate = selectedRow?.metadata?.threshold_moderate ?? 6.0;

        if (num >= strong) return { label: 'Strong Binding', color: 'green', bg: 'bg-green-700/15', border: 'border-green-700/25', text: 'text-green-900 font-bold' };
        if (num >= moderate) return { label: 'Moderate Binding', color: 'amber', bg: 'bg-amber-500/15', border: 'border-amber-500/25', text: 'text-amber-700 font-bold' };
        return { label: 'Weak Binding', color: 'red', bg: 'bg-red-500/15', border: 'border-red-500/25', text: 'text-red-700 font-bold' };
    };

    const strengthInfo = getStrengthInfo(selectedRow?.log_affinity);



    const handleViewFullAnalysis = () => {
        sessionStorage.setItem('predictionSelectedIndex', String(selectedIndex ?? 0));
        router.push('/result/details');
    };

    const handleCopySmiles = () => {
        const smiles = selectedRow?.drug_smiles;
        if (!smiles) return;
        navigator.clipboard.writeText(smiles).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
        });
    };

    if (authLoading) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center">
                <svg className="animate-scientific-spin h-8 w-8 text-green-600 mb-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
            </div>
        );
    }

    if (!batchState?.data?.length) {
        return (
            <div className="min-h-screen flex flex-col">
                <Navbar />
                <main className="flex-1 flex items-center justify-center">
                    <div className="text-center glass-card p-10 max-w-sm">
                        <p className="text-muted-foreground mb-6 font-semibold">No recent analysis found.</p>
                        <Link href="/dashboard" className="btn-premium inline-flex items-center gap-2">
                            Start New Prediction
                        </Link>
                    </div>
                </main>
            </div>
        );
    }

    const isBatch = Boolean(batchState?.isBatch);

    return (
        <div className="min-h-screen flex flex-col relative">
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-green-700/5 rounded-full blur-[140px] -z-10 pointer-events-none" />

            <Navbar />

            <main className="flex-1 flex flex-col items-center p-6 animate-fade-in relative z-10 py-10">
                <div className="w-full max-w-6xl">
                    <div className="flex flex-col sm:flex-row sm:items-start justify-between mb-6 gap-4">
                        <div>
                            <p className="text-xs uppercase tracking-[0.25em] text-green-600/70 mb-1">
                                Prediction Results
                            </p>
                            <h1 className="text-2xl md:text-3xl font-semibold tracking-tight text-foreground">
                                {drugDisplay || 'Drug'} - {proteinDisplay || 'Protein target'}
                            </h1>
                            <p className="text-sm text-muted-foreground mt-2">
                                {isBatch ? `Top-ranked pair out of ${rankedData.length} screened.` : 'Single prediction run.'}{' '}
                                {batchState?.executionTimeMs ? `Completed in ${(batchState.executionTimeMs / 1000).toFixed(2)}s.` : ''}{' '}
                                Model confidence: {Math.round((selectedRow?.confidence ?? 0) * 100)}%.
                            </p>
                        </div>

                        <div className="flex flex-wrap gap-2">
                            <Link href="/dashboard" className="btn-ghost text-xs px-3 py-1.5 h-auto border border-border">
                                New Prediction
                            </Link>
                            <Link href="/history" className="btn-ghost text-xs px-3 py-1.5 h-auto border border-border">
                                View History
                            </Link>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
                        <div className="glass-card p-5">
                            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-3">
                                Binding Strength
                            </p>
                            <div className="flex items-center justify-between mb-4">
                                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${strengthInfo.bg} ${strengthInfo.text} border ${strengthInfo.border}`}>
                                    {strengthInfo.label}
                                </span>
                            </div>
                            <div className="mb-3">
                                <div className="h-2 w-full rounded-full bg-secondary overflow-hidden">
                                    <div
                                        className={`h-full rounded-full transition-all duration-700 ${strengthInfo.color === 'green' ? 'bg-gradient-to-r from-green-700 to-green-600' : strengthInfo.color === 'amber' ? 'bg-gradient-to-r from-amber-600 to-amber-400' : strengthInfo.color === 'red' ? 'bg-gradient-to-r from-red-600 to-red-400' : 'bg-gray-600'}`}
                                        style={{ width: `${affinityGaugePct}%` }}
                                    />
                                </div>
                                <div className="flex justify-between mt-1.5 text-[10px] text-muted-foreground">
                                    <span>Weak</span>
                                    <span>Strong</span>
                                </div>
                            </div>
                            <div className="text-xs text-muted-foreground">
                                Log affinity (pKd):{' '}
                                <span className="font-bold text-foreground">
                                    {formatFixed(selectedRow?.log_affinity)}
                                </span>
                                <span className="block mt-1 text-[10px] text-muted-foreground">
                                    Higher values indicate stronger predicted binding.
                                </span>
                            </div>
                        </div>

                        <div className="glass-card p-5 lg:col-span-2 flex flex-col justify-center">
                            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-3">
                                Actions
                            </p>

                            <div className="flex flex-wrap gap-2">
                                <button
                                    type="button"
                                    className="btn-premium text-xs px-3 py-1.5 h-auto"
                                    onClick={handleViewFullAnalysis}
                                >
                                    View 3D Structures & Details
                                </button>
                                {selectedRow?.drug_smiles && (
                                    <button
                                        type="button"
                                        className="btn-ghost text-xs px-3 py-1.5 h-auto border border-border flex items-center gap-1.5"
                                        onClick={handleCopySmiles}
                                    >
                                        {copied ? (
                                            <><svg className="w-3.5 h-3.5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg><span className="text-green-600">Copied!</span></>
                                        ) : (
                                            <><svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>Copy SMILES</>
                                        )}
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>

                    {isBatch ? (
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-start">
                            <div className="glass-card p-4 lg:col-span-1 h-fit sticky top-24">
                                <p className="text-xs uppercase tracking-widest text-green-600/80 mb-2">
                                    Selected Pair
                                </p>
                                <div className="grid md:grid-cols-1 gap-3">
                                    <div>
                                        <p className="text-[10px] uppercase text-muted-foreground mb-1">Drug</p>
                                        <p className="text-sm text-foreground font-bold truncate">{drugDisplay}</p>
                                    </div>
                                    <div>
                                        <p className="text-[10px] uppercase text-muted-foreground mb-1">Protein Target</p>
                                        <p className="text-sm text-foreground font-bold truncate">{proteinDisplay}</p>
                                    </div>
                                </div>
                            </div>

                            <div className="glass-card p-4 lg:col-span-2">
                                <div className="flex items-center justify-between mb-2">
                                    <p className="text-xs uppercase tracking-wider text-muted-foreground">
                                        Batch Screening Ranking
                                    </p>
                                    <div className="flex items-center gap-2">
                                        <label htmlFor="limit" className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Show top:</label>
                                        <select
                                            id="limit"
                                            value={displayLimit}
                                            onChange={(e) => setDisplayLimit(e.target.value)}
                                            className="text-xs border border-border rounded px-2 py-1 bg-card text-muted-foreground focus:outline-none focus:border-green-600"
                                        >
                                            <option value="2">2</option>
                                            <option value="5">5</option>
                                            <option value="10">10</option>
                                            <option value="20">20</option>
                                            <option value="50">50</option>
                                            <option value="All">All</option>
                                        </select>
                                    </div>
                                </div>
                                <p className="text-xs text-muted-foreground mb-3">
                                    Click a pair to view its prediction details above.
                                </p>

                                <div className="grid gap-2">
                                    {(displayLimit === 'All' ? rankedData : rankedData.slice(0, Number(displayLimit))).map((item, index) => {
                                        const isSelected = index === selectedIndex;
                                        const itemStrength = getStrengthInfo(item.log_affinity);
                                        return (
                                            <button
                                                key={`${item.drug_label || item.drug_smiles || 'drug'}-${index}`}
                                                type="button"
                                                onClick={() => setSelectedIndex(index)}
                                                className={`w-full text-left rounded-xl p-4 transition border ${isSelected
                                                    ? 'border-green-600 bg-green-700/10'
                                                    : 'border-border/30 bg-card/20'
                                                    } hover:border-green-600/50`}
                                            >
                                                <div className="flex items-start justify-between gap-4">
                                                    <div className="min-w-0">
                                                        <p className="text-[11px] uppercase tracking-[0.3em] text-muted-foreground mb-1.5">
                                                            Rank {index + 1}
                                                        </p>
                                                        <p className="text-sm font-bold text-foreground truncate">
                                                            {item.drug_label || item.drug_smiles || 'Unknown drug'}
                                                        </p>
                                                        <p className="text-xs text-muted-foreground truncate mt-1">
                                                            {item.protein_label ||
                                                                `Protein (${item.protein_sequence?.replace(/\s/g, '').length || 0} residues)`}
                                                        </p>
                                                    </div>
                                                    <div className="text-right shrink-0">
                                                        <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold ${itemStrength.bg} ${itemStrength.text} ${itemStrength.border} border mb-1`}>
                                                            {itemStrength.label}
                                                        </span>
                                                        <p className="text-xs text-muted-foreground">
                                                            {formatFixed(item.confidence != null ? item.confidence * 100 : null, 0, '—')}% conf.
                                                        </p>
                                                    </div>
                                                </div>
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="glass-card p-5">
                            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-2">
                                Protein Sequence Overview
                            </p>
                            <ProteinSequencePanel
                                sequence={selectedRow?.protein_sequence}
                                mode="before"
                                title="Input sequence"
                            />
                        </div>
                    )}
                </div>
            </main>

            <Footer />
        </div>
    );
}
