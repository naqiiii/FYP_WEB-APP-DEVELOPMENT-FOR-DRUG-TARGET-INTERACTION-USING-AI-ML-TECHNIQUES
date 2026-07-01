'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';
import { predict, predictBatch, predictProteinBatch } from '@/services/api-client';
import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';

export default function DashboardPage() {
    const router = useRouter();
    const { isAuthenticated, loading: authLoading } = useAuth();

    const [mode, setMode] = useState('single');
    const [drugName, setDrugName] = useState('');
    const [drugSmiles, setDrugSmiles] = useState('');
    const [proteinName, setProteinName] = useState('');
    const [proteinSequence, setProteinSequence] = useState('');

    // Uploaded lists are normalized into one item per line before sending to the API.
    const [drugFileList, setDrugFileList] = useState([]);
    const [drugFileName, setDrugFileName] = useState('');

    const [proteinFileList, setProteinFileList] = useState([]);
    const [proteinFileName, setProteinFileName] = useState('');

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');



    const handleFileUpload = (e) => {
        const file = e.target.files[0];
        if (!file) return;
        setDrugFileName(file.name);

        const reader = new FileReader();
        reader.onload = (event) => {
            const text = event.target.result;
            const items = text.split(/\r?\n/)
                .map(s => s.replace(/^"|"$/g, '').replace(/,/g, '').trim())
                .filter(s => s.length > 0);
            setDrugFileList(items);
        };
        reader.readAsText(file);
    };

    const handleProteinFileUpload = (e) => {
        const file = e.target.files[0];
        if (!file) return;
        setProteinFileName(file.name);

        const reader = new FileReader();
        reader.onload = (event) => {
            const text = event.target.result;
            const items = text.split(/\r?\n/)
                .map(s => s.replace(/^"|"$/g, '').replace(/,/g, '').trim())
                .filter(s => s.length > 0);
            setProteinFileList(items);
        };
        reader.readAsText(file);
    };

    const isValidSmiles = (str) => {
        if (!str) return true;
        return /^[CNOPSFIBrclosnpfib0-9=#@+\\/\-\[\]\(\)\.\s]+$/i.test(str);
    };

    const isValidSequence = (str) => {
        if (!str) return true;
        return /^[ACDEFGHIKLMNPQRSTVWY\s]+$/i.test(str);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            let results;
            const startTime = Date.now();

            if (mode === 'single') {
                // Single input mode: user provides one drug and one protein.
                if (!drugName?.trim() && !drugSmiles?.trim()) throw new Error("Please enter a Drug Name or SMILES string.");
                if (!proteinName?.trim() && !proteinSequence?.trim()) throw new Error("Please enter a Protein Name or Sequence.");

                if (!isValidSmiles(drugSmiles)) throw new Error("Invalid SMILES format detected.");
                if (!isValidSequence(proteinSequence)) throw new Error("Invalid Protein Sequence detected.");

                const res = await predict(
                    drugName?.trim(),
                    drugSmiles?.trim(),
                    proteinName?.trim(),
                    proteinSequence?.trim(),
                    null
                );
                results = [res];
            }
            else if (mode === 'batch' || mode === 'batch-drug') {
                // Batch drug mode: screen many drug candidates against one protein.
                if (!proteinName?.trim() && !proteinSequence?.trim()) throw new Error("Please enter a Target Protein Name or Sequence.");
                if (!isValidSequence(proteinSequence)) throw new Error("Invalid Protein Sequence detected.");

                const uniqueDrugs = Array.from(new Set([...drugFileList]));

                if (uniqueDrugs.length === 0) {
                    throw new Error('Please provide at least one drug name/SMILES.');
                }

                if (uniqueDrugs.length > 15) {
                    throw new Error(`Batch screening is limited to a maximum of 15 drugs to ensure fast response times. You have provided ${uniqueDrugs.length} drugs.`);
                }

                results = await predictBatch(
                    uniqueDrugs,
                    proteinName?.trim() || '',
                    proteinSequence?.trim() || '',
                    null
                );
            }
            else if (mode === 'batch-protein') {
                // Batch protein mode: test one drug against many targets.
                if (!drugName?.trim() && !drugSmiles?.trim()) throw new Error("Please enter a Drug Name or SMILES string.");
                if (!isValidSmiles(drugSmiles)) throw new Error("Invalid SMILES format detected.");

                const uniqueProteins = Array.from(new Set([...proteinFileList]));

                if (uniqueProteins.length === 0) {
                    throw new Error('Please provide at least one protein name/sequence.');
                }

                if (uniqueProteins.length > 15) {
                    throw new Error(`Batch screening is limited to a maximum of 15 proteins to ensure fast response times. You have provided ${uniqueProteins.length} proteins.`);
                }

                results = await predictProteinBatch(
                    drugName?.trim() || '',
                    drugSmiles?.trim() || '',
                    uniqueProteins,
                    null
                );
            }

            const executionTimeMs = Date.now() - startTime;
            sessionStorage.setItem('predictionResult', JSON.stringify({
                isBatch: mode !== 'single',
                data: results,
                executionTimeMs
            }));
            router.push('/result');

        } catch (err) {
            // Show backend validation messages when available; otherwise keep the local error.
            let errMsg = err.message || 'Prediction analysis failed.';
            if (err.response?.data?.detail) {
                const detail = err.response.data.detail;
                errMsg = typeof detail === 'string' ? detail : (detail[0]?.msg || errMsg);
            }
            setError(errMsg);
        } finally {
            setLoading(false);
        }
    };

    const fillExample = () => {
        setDrugName('Aspirin');
        setDrugSmiles('CC(=O)OC1=CC=CC=C1C(=O)O');
        setProteinName('EGFR');
        setProteinSequence('MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKRQQIA');
    };

    // Wait for the auth context to restore localStorage before deciding access.
    if (authLoading) {
        return (
            <div className="min-h-screen bg-background flex flex-col items-center justify-center">
                <svg className="animate-scientific-spin h-8 w-8 text-green-600 mb-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                <p className="text-muted-foreground animate-pulse">Initializing…</p>
            </div>
        );
    }

    if (!isAuthenticated) {
        if (typeof window !== 'undefined') router.push('/login');
        return null;
    }

    return (
        <div className="min-h-screen flex flex-col relative">
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-green-700/6 rounded-full blur-[140px] -z-10 pointer-events-none" />

            <Navbar />

            <main className="flex-1 flex items-center justify-center p-6 animate-fade-in relative z-10 py-12">
                <div className="w-full max-w-2xl">
                    <div className="text-center mb-8">
                        <p className="text-muted-foreground max-w-lg mx-auto">
                            Enter a drug and a protein target below. You'll receive a binding affinity estimate,
                            confidence score, and optional 3D structural visualization.
                        </p>
                    </div>

                    <div className="glass-card p-6 md:p-8">
                        <div className="flex bg-secondary/50 p-1 rounded-lg mb-8">
                            <button
                                type="button"
                                onClick={() => setMode('single')}
                                className={`flex-1 py-1.5 px-3 rounded-md text-sm font-semibold transition-all ${mode === 'single' ? 'bg-green-700 text-white shadow-sm' : 'text-muted-foreground hover:text-primary hover:bg-secondary'}`}
                            >
                                Single
                            </button>
                            <button
                                type="button"
                                onClick={() => setMode('batch-drug')}
                                className={`flex-1 py-1.5 px-3 rounded-md text-sm font-semibold transition-all ${mode === 'batch-drug' || mode === 'batch' ? 'bg-green-700 text-white shadow-sm' : 'text-muted-foreground hover:text-primary hover:bg-secondary'}`}
                            >
                                Drug Screening
                            </button>
                            <button
                                type="button"
                                onClick={() => setMode('batch-protein')}
                                className={`flex-1 py-1.5 px-3 rounded-md text-sm font-semibold transition-all ${mode === 'batch-protein' ? 'bg-green-700 text-white shadow-sm' : 'text-muted-foreground hover:text-primary hover:bg-secondary'}`}
                            >
                                Protein Screening
                            </button>
                        </div>

                        <form onSubmit={handleSubmit}>
                            {error && (
                                <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-sm flex items-start gap-3">
                                    <svg className="w-5 h-5 text-red-400 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                    </svg>
                                    <span>{error}</span>
                                </div>
                            )}

                            <div className="space-y-6">
                                {mode === 'single' && (
                                    <div className="space-y-4">
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                            <div>
                                                <label className="block text-sm font-semibold text-foreground mb-1.5">Drug Name</label>
                                                <input
                                                    type="text"
                                                    value={drugName}
                                                    onChange={(e) => setDrugName(e.target.value)}
                                                    className="input-premium"
                                                    placeholder="e.g. Aspirin"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-sm font-semibold text-foreground mb-1.5">Protein Name</label>
                                                <input
                                                    type="text"
                                                    value={proteinName}
                                                    onChange={(e) => setProteinName(e.target.value)}
                                                    className="input-premium"
                                                    placeholder="e.g. EGFR"
                                                />
                                            </div>
                                        </div>

                                        <div>
                                            <div className="flex justify-between items-baseline mb-1.5">
                                                <label className="block text-sm font-semibold text-foreground">SMILES String</label>
                                                <span className="text-xs text-muted-foreground">Optional if Name provided</span>
                                            </div>
                                            <textarea
                                                value={drugSmiles}
                                                onChange={(e) => setDrugSmiles(e.target.value)}
                                                rows={2}
                                                className="input-premium font-mono text-sm resize-y"
                                                placeholder="CC(=O)OC1=CC=CC=C1C(=O)O"
                                            />
                                        </div>

                                        <div>
                                            <div className="flex justify-between items-baseline mb-1.5">
                                                <label className="block text-sm font-semibold text-foreground">Protein Sequence</label>
                                                <span className="text-xs text-muted-foreground">Optional if Name provided</span>
                                            </div>
                                            <textarea
                                                value={proteinSequence}
                                                onChange={(e) => setProteinSequence(e.target.value)}
                                                rows={3}
                                                className="input-premium font-mono text-sm resize-y"
                                                placeholder="MKTAYIAKQRQISFVKSHFSRQLEERLGLI..."
                                            />
                                        </div>
                                    </div>
                                )}

                                {(mode === 'batch' || mode === 'batch-drug') && (
                                    <div className="space-y-6">
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                            <div>
                                                <label className="block text-sm font-semibold text-foreground mb-1.5">Target Protein Name</label>
                                                <input
                                                    type="text"
                                                    value={proteinName}
                                                    onChange={(e) => setProteinName(e.target.value)}
                                                    className="input-premium"
                                                    placeholder="e.g. EGFR"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-sm font-semibold text-foreground mb-1.5">Target Sequence</label>
                                                <input
                                                    type="text"
                                                    value={proteinSequence}
                                                    onChange={(e) => setProteinSequence(e.target.value)}
                                                    className="input-premium font-mono text-sm"
                                                    placeholder="Optional if Name provided"
                                                />
                                            </div>
                                        </div>

                                        <div className="border-2 border-dashed border-green-700/20 rounded-xl p-8 text-center bg-white hover:bg-gray-50/50 transition-colors relative cursor-pointer group">
                                            <input
                                                type="file"
                                                accept=".txt,.csv,.tsv"
                                                onChange={handleFileUpload}
                                                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                                            />
                                            <p className="text-sm font-bold text-black mb-1">
                                                {drugFileName ? `File selected: ${drugFileName}` : 'Click to upload drug list'}
                                            </p>
                                            <p className="text-xs text-black font-semibold">
                                                {drugFileList.length > 0
                                                    ? `Found ${drugFileList.length} items from file.`
                                                    : 'Optional: upload .txt, .csv, or .tsv (one item per line)'}
                                            </p>
                                        </div>
                                        {drugFileList.length > 15 && (
                                            <p className="text-xs text-red-500 font-semibold text-center mt-2 animate-pulse">
                                                ⚠️ Maximum limit of 15 items exceeded (found {drugFileList.length} items). Please upload a file with 15 or fewer items.
                                            </p>
                                        )}


                                    </div>
                                )}

                                {mode === 'batch-protein' && (
                                    <div className="space-y-6">
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                            <div>
                                                <label className="block text-sm font-semibold text-foreground mb-1.5">Target Drug Name</label>
                                                <input
                                                    type="text"
                                                    value={drugName}
                                                    onChange={(e) => setDrugName(e.target.value)}
                                                    className="input-premium"
                                                    placeholder="e.g. Aspirin"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-sm font-semibold text-foreground mb-1.5">Target SMILES</label>
                                                <input
                                                    type="text"
                                                    value={drugSmiles}
                                                    onChange={(e) => setDrugSmiles(e.target.value)}
                                                    className="input-premium font-mono text-sm"
                                                    placeholder="Optional if Name provided"
                                                />
                                            </div>
                                        </div>

                                        <div className="border-2 border-dashed border-green-700/20 rounded-xl p-8 text-center bg-white hover:bg-gray-50/50 transition-colors relative cursor-pointer group">
                                            <input
                                                type="file"
                                                accept=".txt,.csv,.tsv,.fasta"
                                                onChange={handleProteinFileUpload}
                                                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                                            />
                                            <p className="text-sm font-bold text-black mb-1">
                                                {proteinFileName ? `File selected: ${proteinFileName}` : 'Click to upload protein list'}
                                            </p>
                                            <p className="text-xs text-black font-semibold">
                                                {proteinFileList.length > 0
                                                    ? `Found ${proteinFileList.length} items from file.`
                                                    : 'Optional: upload .txt, .csv, .tsv, or .fasta (one item per line)'}
                                            </p>
                                        </div>
                                        {proteinFileList.length > 15 && (
                                            <p className="text-xs text-red-500 font-semibold text-center mt-2 animate-pulse">
                                                ⚠️ Maximum limit of 15 items exceeded (found {proteinFileList.length} items). Please upload a file with 15 or fewer items.
                                            </p>
                                        )}


                                    </div>
                                )}



                                <div className="flex flex-col sm:flex-row gap-3 pt-2">
                                    {mode === 'single' && (
                                        <button
                                            type="button"
                                            onClick={fillExample}
                                            className="btn-ghost flex-1 sm:flex-none border border-border"
                                        >
                                            Load Sample Data
                                        </button>
                                    )}
                                    <button
                                        type="submit"
                                        disabled={loading || (mode.startsWith('batch') && ((mode === 'batch-drug' || mode === 'batch') ? drugFileList.length > 15 : proteinFileList.length > 15))}
                                        className="btn-premium flex-1 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        {loading ? (
                                            <span className="flex items-center justify-center gap-2">
                                                <svg className="animate-scientific-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                                </svg>
                                                Running Analysis…
                                            </span>
                                        ) : (
                                            mode.startsWith('batch') ? 'Run Batch Screening' : 'Run Prediction'
                                        )}
                                    </button>
                                </div>
                            </div>
                        </form>
                    </div>
                </div>
            </main>

            <Footer />
        </div>
    );
}
