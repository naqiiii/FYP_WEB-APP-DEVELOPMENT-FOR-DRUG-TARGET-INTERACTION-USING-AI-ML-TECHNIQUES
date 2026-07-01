'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';
import Navbar from '@/components/Navbar';
import ComplexViewer3D from '@/components/ComplexViewer3D';
import { getIllustrativeBindingRegion } from '@/components/ProteinSequencePanel';

export default function ResultComplexPage() {
    const router = useRouter();
    const { isAuthenticated, loading: authLoading } = useAuth();
    const [batchState, setBatchState] = useState(null);
    const [selectedIndex, setSelectedIndex] = useState(0);
    const [dockingInsightsByPair, setDockingInsightsByPair] = useState({});

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
                <svg className="animate-scientific-spin h-8 w-8 text-primary mb-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    />
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
                        <p className="text-gray-700 mb-4 font-semibold">No analysis found in this session.</p>
                        <p className="text-sm text-muted-foreground mb-6">
                            Run a new prediction first, then open complex view from the summary/details screens.
                        </p>
                        <Link href="/" className="btn-premium inline-flex items-center gap-2">
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

    const selectedPairKey = `${selectedRow?.drug_smiles || ''}::${selectedRow?.protein_sequence || ''}`;
    const currentDockingInsight = dockingInsightsByPair[selectedPairKey];

    const logAffinityNum = typeof selectedRow?.log_affinity === 'number' ? selectedRow.log_affinity : Number(selectedRow?.log_affinity);
    const confidencePct = Math.round((selectedRow?.confidence ?? 0) * 100);
    const affinityLabel =
        Number.isFinite(logAffinityNum) && logAffinityNum >= 1.2 ? 'High' : Number.isFinite(logAffinityNum) && logAffinityNum >= 1.0 ? 'Medium' : 'Low';

    const { start, end } = getIllustrativeBindingRegion(selectedRow?.protein_sequence || '');
    const fromResid = start + 1;
    const toResid = end;
    const hasTrueDocking = currentDockingInsight?.mode === 'true_docking';
    const metadata = currentDockingInsight?.metadata || {};
    const hasDockingRationale = Boolean(metadata?.beginner_message) || (Array.isArray(metadata?.interaction_reasons) && metadata.interaction_reasons.length > 0);

    return (
        <div className="min-h-screen flex flex-col relative">
            <Navbar />

            <main className="flex-1 p-6 lg:p-12 animate-fade-in">
                <div className="max-w-5xl mx-auto">
                    <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-6">
                        <div>
                            <p className="text-xs uppercase tracking-[0.25em] text-muted-foreground mb-1">
                                Complex view
                            </p>
                            <h1 className="text-2xl md:text-3xl font-semibold tracking-tight text-slate-900">
                                {selectedRow?.drug_label || selectedRow?.drug_smiles || 'Drug'} →{' '}
                                {selectedRow?.protein_label || 'Target'}
                            </h1>
                            <p className="text-xs text-muted-foreground mt-2">
                                {hasTrueDocking ? 'Docked pose (true docking provider enabled).' : 'Illustrative pose (true docking provider not enabled).'}
                            </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                            <Link href="/result/details" className="btn-ghost text-xs px-3 py-1.5 h-auto border border-white/15">
                                Back
                            </Link>
                        </div>
                    </div>

                    <div className="glass-card p-5 mb-6">
                        <ComplexViewer3D
                            proteinLabel={selectedRow?.protein_label}
                            proteinSequence={selectedRow?.protein_sequence}
                            smiles={selectedRow?.drug_smiles}
                            className="h-[360px]"
                            onDockingInfo={(info) => {
                                setDockingInsightsByPair((prev) => ({
                                    ...prev,
                                    [selectedPairKey]: info,
                                }));
                            }}
                        />
                    </div>

                    <div className="glass-card p-5">
                        <h2 className="text-xs uppercase tracking-wider text-muted-foreground mb-3">
                            Interaction reasons from docking
                        </h2>

                        {currentDockingInsight ? (
                            <div className="space-y-3 text-sm text-gray-200">
                                {hasTrueDocking ? (
                                    <>
                                        <p>
                                            {metadata.beginner_message ||
                                                'Docking-based interaction rationale is available for this pair.'}
                                        </p>
                                        {!hasDockingRationale && (
                                            <p className="text-xs text-gray-700">
                                                Docking pose loaded, but no pose-level rationale was returned by the provider.
                                            </p>
                                        )}
                                    </>
                                ) : (
                                    <>
                                        <p>
                                            True docking pose-level explanations are not available right now (no docking provider
                                            configured on the backend). So we show model-level interaction reasons and an illustrative
                                            binding-site placement.
                                        </p>
                                        <p className="text-xs text-gray-700">
                                            Model signal: <span className="text-gray-100 font-semibold">{affinityLabel} affinity</span> (log
                                            affinity {Number.isFinite(logAffinityNum) ? logAffinityNum.toFixed(3) : 'n/a'}, {confidencePct}% confidence).
                                        </p>
                                        <p className="text-xs text-gray-700">
                                            Highlighted interface region used for placement: residues {fromResid}-{toResid}.
                                        </p>
                                    </>
                                )}

                                {Array.isArray(metadata.interaction_reasons) && metadata.interaction_reasons.length > 0 && (
                                    <div>
                                        <p className="text-[11px] uppercase tracking-wider text-gray-600 mb-1">
                                            Key reasons
                                        </p>
                                        <ul className="space-y-1 text-xs text-gray-700">
                                            {metadata.interaction_reasons.slice(0, 4).map((reason, idx) => (
                                                <li key={idx}>- {reason}</li>
                                            ))}
                                        </ul>
                                    </div>
                                )}

                                {!hasTrueDocking && (
                                    <div>
                                        <p className="text-[11px] uppercase tracking-wider text-gray-600 mb-1">
                                            What to interpret (model-level)
                                        </p>
                                        <ul className="space-y-1 text-xs text-gray-700">
                                            <li>- {affinityLabel} interaction signal between drug chemistry and protein sequence.</li>
                                            <li>- Ligand placement is illustrative, near the highlighted residue window.</li>
                                            <li>- Pose-level contacts may not match the actual binding mode.</li>
                                            <li>- Validate with true docking or experimental evidence.</li>
                                        </ul>
                                    </div>
                                )}

                                {Array.isArray(metadata.caveats) && metadata.caveats.length > 0 && (
                                    <div>
                                        <p className="text-[11px] uppercase tracking-wider text-gray-600 mb-1">
                                            Caveats
                                        </p>
                                        <ul className="space-y-1 text-xs text-gray-700">
                                            {metadata.caveats.slice(0, 3).map((caveat, idx) => (
                                                <li key={idx}>- {caveat}</li>
                                            ))}
                                        </ul>
                                    </div>
                                )}

                                {!hasTrueDocking && (
                                    <details className="pt-1">
                                        <summary className="cursor-pointer text-xs text-gray-700">
                                            How to enable true docking explanations
                                        </summary>
                                        <p className="text-xs text-gray-700 mt-2 leading-relaxed">
                                            The backend calls a docking provider using <span className="font-mono">DOCKING_PROVIDER_URL</span>.
                                            If that variable is not set (or the provider is offline), true docking pose + pose-level interaction rationale
                                            cannot be returned.
                                        </p>
                                    </details>
                                )}
                            </div>
                        ) : (
                            <p className="text-xs text-muted-foreground">
                                Waiting for complex pose to load... If docking is not configured, interaction reasons may appear after the mock/illustrative docking step finishes.
                            </p>
                        )}
                    </div>
                </div>
            </main>

        </div>
    );
}

