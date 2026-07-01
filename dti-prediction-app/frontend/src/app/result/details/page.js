'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';
import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';
import MoleculeViewer3D from '@/components/MoleculeViewer3D';
import ProteinSequencePanel from '@/components/ProteinSequencePanel';
import ProteinStructureViewer3D from '@/components/ProteinStructureViewer3D';
import ComplexViewer3D from '@/components/ComplexViewer3D';
import { safeNum, formatFixed } from '@/utils/numbers';

export default function ResultDetailsPage() {
    const router = useRouter();
    const { isAuthenticated, loading: authLoading } = useAuth();
    const [batchState, setBatchState] = useState(null);
    const [selectedIndex, setSelectedIndex] = useState(0);

    const [activeTab, setActiveTab] = useState('overview');

    useEffect(() => {
        const storedResult = sessionStorage.getItem('predictionResult');
        if (storedResult) {
            try {
                setBatchState(JSON.parse(storedResult));
            } catch {
                sessionStorage.removeItem('predictionResult');
                setBatchState(null);
            }
        }
    }, []);

    useEffect(() => {
        if (!batchState?.data?.length) return;
        const storedIdx = sessionStorage.getItem('predictionSelectedIndex');
        const idx = storedIdx ? Number.parseInt(storedIdx, 10) : 0;
        if (!Number.isNaN(idx) && idx >= 0 && idx < batchState.data.length) {
            setSelectedIndex(idx);
        } else {
            setSelectedIndex(0);
        }
    }, [batchState?.data]);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) {
            router.push('/login');
        }
    }, [authLoading, isAuthenticated, router]);

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

    if (!authLoading && isAuthenticated && !batchState?.data) {
        return (
            <div className="min-h-screen flex flex-col">
                <Navbar />
                <main className="flex-1 flex items-center justify-center">
                    <div className="text-center glass-card p-10 max-w-sm">
                        <p className="text-muted-foreground mb-4 font-semibold">No analysis found in this session.</p>
                        <p className="text-sm text-muted-foreground mb-6">
                            Run a new prediction first, then open the details view from the results page.
                        </p>
                        <Link href="/dashboard" className="btn-premium inline-flex items-center gap-2">
                            New Prediction
                        </Link>
                    </div>
                </main>
            </div>
        );
    }

    if (!batchState?.data) return null;

    const { isBatch, data } = batchState;
    const rankedData = isBatch ? [...data].sort((a, b) => (b.log_affinity ?? 0) - (a.log_affinity ?? 0)) : data;
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
            ? `Protein (${selectedRow.protein_sequence.replace(/\s/g, '').length} residues)`
            : '');

    const getStrengthInfo = (pKd) => {
        const num = safeNum(pKd);
        if (num === null) return { label: 'Unavailable', bg: 'bg-secondary', border: 'border-border', text: 'text-muted-foreground' };

        const strong = selectedRow?.metadata?.threshold_strong ?? 7.0;
        const moderate = selectedRow?.metadata?.threshold_moderate ?? 6.0;

        if (num >= strong) return { label: 'Strong Binding', bg: 'bg-green-700/15', border: 'border-green-700/25', text: 'text-green-900 font-bold' };
        if (num >= moderate) return { label: 'Moderate Binding', bg: 'bg-amber-500/15', border: 'border-amber-500/25', text: 'text-amber-700 font-bold' };
        return { label: 'Weak Binding', bg: 'bg-red-500/15', border: 'border-red-500/25', text: 'text-red-700 font-bold' };
    };

    const strengthInfo = getStrengthInfo(selectedRow?.log_affinity);

    const getExplanation = (pKd) => {
        const num = safeNum(pKd);
        if (num === null) return 'Affinity score not available.';

        const strong = selectedRow?.metadata?.threshold_strong ?? 7.0;
        const moderate = selectedRow?.metadata?.threshold_moderate ?? 6.0;

        if (num >= strong) return 'Strong predicted binding: the model found high compatibility between the drug chemical structure and the protein sequence motifs.';
        if (num >= moderate) return 'Moderate predicted binding: some molecular compatibility detected. The drug may interact but is unlikely to be a top candidate.';
        return 'Weak predicted binding: the model found low compatibility. Useful as a negative comparison but unlikely to be a strong binder.';
    };

    const getNextSteps = (pKd, confidence) => {
        const confPct = Math.round((confidence || 0) * 100);
        const num = safeNum(pKd) ?? -Infinity;

        const strong = selectedRow?.metadata?.threshold_strong ?? 7.0;
        const moderate = selectedRow?.metadata?.threshold_moderate ?? 6.0;

        if (num >= strong) return `With ${confPct}% model confidence, this is a strong candidate. Validate with molecular docking (AutoDock Vina, DiffDock) or experimental binding assays (SPR, ITC).`;
        if (num >= moderate) return `With ${confPct}% confidence, consider testing structural analogs of this drug to find a stronger binder for this target.`;
        return `With ${confPct}% confidence and weak binding, this pair serves as a useful negative control. Focus on higher-ranked candidates.`;
    };

    return (
        <div className="min-h-screen flex flex-col relative overflow-hidden">
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-green-700/5 rounded-full blur-[140px] -z-10 pointer-events-none" />

            <Navbar />

            <main className="flex-1 flex flex-col items-center p-6 animate-fade-in relative z-10 py-10">
                <div className="w-full max-w-6xl">
                    <div className="flex flex-col sm:flex-row sm:items-end justify-between mb-6 gap-4">
                        <div>
                            <p className="text-xs uppercase tracking-[0.25em] text-green-600/70 mb-1">
                                Detailed Analysis
                            </p>
                            <h1 className="text-2xl md:text-3xl font-semibold tracking-tight text-foreground">
                                {drugDisplay || 'Drug'} - {proteinDisplay || 'Target'}
                            </h1>
                            <p className="text-xs text-muted-foreground mt-2">
                                Deep dive into molecular properties, 3D structures, and sequence-level interactions.
                            </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                            <Link href="/result" className="btn-ghost text-xs px-3 py-1.5 h-auto border border-border">
                                Back to Summary
                            </Link>
                            <Link href="/history" className="btn-premium text-xs px-3 py-1.5 h-auto">
                                View History
                            </Link>
                        </div>
                    </div>



                    <div className="flex flex-wrap border-b border-border mb-6 gap-2">
                        <button
                            onClick={() => setActiveTab('overview')}
                            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${activeTab === 'overview' ? 'border-green-700 text-green-800' : 'border-transparent text-gray-500 hover:text-muted-foreground hover:border-gray-300'}`}
                        >
                            Overview & Properties
                        </button>
                        <button
                            onClick={() => setActiveTab('3d')}
                            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${activeTab === '3d' ? 'border-green-700 text-green-800' : 'border-transparent text-gray-500 hover:text-muted-foreground hover:border-gray-300'}`}
                        >
                            3D Visualization
                        </button>
                        <button
                            onClick={() => setActiveTab('sequence')}
                            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${activeTab === 'sequence' ? 'border-green-700 text-green-800' : 'border-transparent text-gray-500 hover:text-muted-foreground hover:border-gray-300'}`}
                        >
                            Sequences & Details
                        </button>
                    </div>

                    <div className="min-h-[400px]">
                        {activeTab === 'overview' && (
                            <div className="animate-fade-in">
                                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
                                    <div className="glass-card p-5 flex flex-col justify-between">
                                        <div>
                                            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-3">
                                                Prediction Score
                                            </p>
                                            <div className="flex items-center justify-between mb-4">
                                                <div>
                                                    <p className="text-[10px] uppercase tracking-[0.25em] text-muted-foreground mb-1">
                                                        Binding Score (pKd)
                                                    </p>
                                                    <p className="text-3xl font-bold text-foreground">
                                                        {formatFixed(selectedRow?.log_affinity, 3, '—')}
                                                    </p>
                                                </div>
                                                <div className="text-right">
                                                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${strengthInfo.bg} ${strengthInfo.text} border ${strengthInfo.border}`}>
                                                        {strengthInfo.label}
                                                    </span>
                                                    <p className="text-[11px] text-muted-foreground mt-2">
                                                        {formatFixed(selectedRow?.confidence != null ? selectedRow.confidence * 100 : null, 1, '—')}% confidence
                                                    </p>
                                                </div>
                                            </div>
                                            <p className="text-xs text-muted-foreground">
                                                Binding affinity estimate:{' '}
                                                <span className="font-semibold text-muted-foreground">
                                                    {formatFixed(selectedRow?.affinity, 3, '—')}
                                                </span>
                                            </p>
                                        </div>
                                    </div>

                                    <div className="glass-card p-5 lg:col-span-2">
                                        <div className="space-y-3">
                                            <div>
                                                <p className="text-xs uppercase tracking-[0.25em] text-green-900 font-bold mb-1">
                                                    Interpretation
                                                </p>
                                                <p className="text-sm text-foreground leading-relaxed font-medium">
                                                    {getExplanation(selectedRow?.log_affinity)}
                                                </p>
                                            </div>
                                            <div className="p-3 rounded-lg bg-green-700/10 border border-green-700/20">
                                                <p className="text-xs uppercase tracking-[0.25em] text-green-900 font-bold mb-1">
                                                    Recommended Next Steps
                                                </p>
                                                <p className="text-sm text-gray-800 font-medium leading-relaxed">
                                                    {getNextSteps(selectedRow?.log_affinity, selectedRow?.confidence)}
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 gap-4">
                                    <div className="glass-card p-6">
                                        <h2 className="text-sm uppercase tracking-widest font-bold text-gray-800 mb-6 flex items-center gap-3">
                                            <span className="w-3 h-3 rounded-full bg-violet-500" />
                                            Target Biological Information
                                        </h2>
                                        {selectedRow?.protein_info ? (
                                            <div className="space-y-5 text-sm">
                                                <div className="flex justify-between items-center border-b border-gray-200 pb-3">
                                                    <p className="text-gray-700 font-semibold tracking-wide">Sequence Length</p>
                                                    <p className="text-green-900 text-xl font-black">{selectedRow.protein_info.length} <span className="text-sm font-semibold text-gray-500 uppercase tracking-wider ml-1">residues</span></p>
                                                </div>
                                                {selectedRow.protein_info.organism && selectedRow.protein_info.organism !== 'Unknown (Local DB)' && (
                                                    <div className="flex justify-between items-center border-b border-gray-200 pb-3">
                                                        <p className="text-gray-700 font-semibold tracking-wide">Organism</p>
                                                        <p className="text-slate-900 font-bold text-base text-right">{selectedRow.protein_info.organism}</p>
                                                    </div>
                                                )}
                                                {selectedRow.protein_info.protein_class && selectedRow.protein_info.protein_class !== 'Target Sequence' && (
                                                    <div className="flex justify-between items-center border-b border-gray-200 pb-3">
                                                        <p className="text-gray-700 font-semibold tracking-wide">Target Class</p>
                                                        <p className="text-slate-900 font-bold text-base text-right">{selectedRow.protein_info.protein_class}</p>
                                                    </div>
                                                )}
                                            </div>
                                        ) : (
                                            <p className="text-sm text-gray-600 font-medium italic mt-8 text-center">Biological information not available.</p>
                                        )}
                                    </div>
                                </div>
                            </div>
                        )}

                        {activeTab === '3d' && (
                            <div className="animate-fade-in grid grid-cols-1 lg:grid-cols-2 gap-6">
                                <div className="space-y-6">
                                    <div className="glass-card p-4">
                                        <h2 className="text-xs uppercase tracking-wider text-muted-foreground mb-3 flex items-center gap-2">
                                            <span className="w-2 h-2 rounded-full bg-cyan-400" />
                                            Drug (Ligand) — 3D Structure
                                        </h2>
                                        <MoleculeViewer3D
                                            smiles={selectedRow?.drug_smiles}
                                            className="h-[300px] rounded-lg overflow-hidden"
                                        />
                                        <p className="text-[10px] text-muted-foreground mt-2">
                                            Generated 3D ligand conformation.
                                        </p>
                                    </div>
                                    <div className="glass-card p-4">
                                        <h2 className="text-xs uppercase tracking-wider text-muted-foreground mb-3 flex items-center gap-2">
                                            <span className="w-2 h-2 rounded-full bg-violet-400" />
                                            Protein — 3D Structure
                                        </h2>
                                        <ProteinStructureViewer3D
                                            proteinLabel={selectedRow?.protein_label}
                                            className="h-[300px]"
                                        />
                                        <p className="text-[10px] text-muted-foreground mt-2">
                                            Predicted protein fold.
                                        </p>
                                    </div>
                                </div>

                                <div className="glass-card p-4 flex flex-col">
                                    <h2 className="text-xs uppercase tracking-wider text-muted-foreground mb-3 flex items-center gap-2">
                                        <span className="w-2 h-2 rounded-full bg-green-600" />
                                        Drug–Protein Complex
                                    </h2>
                                    <div className="flex-1 min-h-[400px]">
                                        <ComplexViewer3D
                                            proteinLabel={selectedRow?.protein_label}
                                            proteinSequence={selectedRow?.protein_sequence}
                                            smiles={selectedRow?.drug_smiles}
                                            className="h-full w-full"
                                        />
                                    </div>
                                    <p className="text-[10px] text-muted-foreground mt-2">
                                        Combined view: Illustrative representation unless rigorous docking has been performed.
                                    </p>
                                </div>
                            </div>
                        )}

                        {activeTab === 'sequence' && (
                            <div className="animate-fade-in grid grid-cols-1 lg:grid-cols-2 gap-6">
                                <div className="space-y-6">
                                    <div className="glass-card p-4">
                                        <h2 className="text-xs uppercase tracking-wider text-muted-foreground mb-3">
                                            Protein Sequence
                                        </h2>
                                        <ProteinSequencePanel
                                            sequence={selectedRow?.protein_sequence}
                                            mode="before"
                                            title="Full amino-acid sequence"
                                        />
                                    </div>
                                    <div className="glass-card p-4">
                                        <h2 className="text-xs uppercase tracking-wider text-muted-foreground mb-3">
                                            Predicted Binding Region
                                        </h2>
                                        <ProteinSequencePanel
                                            sequence={selectedRow?.protein_sequence}
                                            mode="after"
                                            title="Highlighted interface region"
                                        />
                                    </div>
                                </div>

                                <div className="glass-card p-4">
                                    <h2 className="text-xs uppercase tracking-wider text-muted-foreground mb-4 inline-block border-b border-border pb-1 w-full">
                                        Resolved Identifiers
                                    </h2>
                                    <p className="text-[11px] text-muted-foreground mb-4">
                                        SMILES + sequence used for this prediction
                                    </p>

                                    <div className="space-y-4">
                                        <div>
                                            <p className="text-[11px] uppercase text-muted-foreground mb-1 font-semibold">
                                                SMILES Used
                                            </p>
                                            <div className="bg-black/5 rounded-lg p-3 border border-border max-h-32 overflow-y-auto">
                                                <p className="font-mono text-sm text-gray-800 break-all">
                                                    {selectedRow?.drug_smiles}
                                                </p>
                                            </div>
                                        </div>
                                        <div>
                                            <p className="text-[11px] uppercase text-muted-foreground mb-1 font-semibold">
                                                Sequence Used
                                            </p>
                                            <div className="bg-black/5 rounded-lg p-3 border border-border max-h-64 overflow-y-auto">
                                                <p className="font-mono text-sm text-gray-800 break-all leading-relaxed">
                                                    {selectedRow?.protein_sequence}
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </main>

            <Footer />
        </div>
    );
}
