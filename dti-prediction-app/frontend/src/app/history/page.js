'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';
import { getHistory } from '@/services/api-client';
import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';
import { formatFixed } from '@/utils/numbers';

const PAGE_SIZE = 10;

function CopyButton({ text }) {
    const [copied, setCopied] = useState(false);
    return (
        <button
            type="button"
            onClick={(e) => {
                e.preventDefault();
                navigator.clipboard.writeText(text);
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
            }}
            className="text-muted-foreground hover:text-green-600 transition-colors p-1"
            title="Copy SMILES and Sequence"
        >
            {copied ? (
                <svg className="w-4 h-4 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
            ) : (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
            )}
        </button>
    );
}

function ConfidenceBadge({ value }) {
    const pct = Math.round((value ?? 0) * 100);
    if (pct >= 80)
        return (
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-green-700/10 text-green-950 border border-green-700/20">
                {pct}%
            </span>
        );
    if (pct >= 60)
        return (
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-amber-500/10 text-amber-900 border border-amber-500/20">
                {pct}%
            </span>
        );
    return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-red-500/10 text-red-900 border border-red-500/20">
            {pct}%
        </span>
    );
}

function exportToCSV(data) {
    const headers = ['Drug', 'Protein', 'pKd (log)', 'Affinity', 'Confidence (%)', 'Model', 'Date'];
    const rows = data.map((item) => [
        item.drug_label || item.drug_smiles,
        item.protein_label || item.protein_sequence,
        (item.log_affinity ?? '').toString(),
        (item.affinity ?? '').toString(),
        Math.round((item.confidence ?? 0) * 100).toString(),
        item.model_name,
        new Date(item.created_at).toISOString().split('T')[0],
    ]);
    const csv = [headers, ...rows].map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `dti-history-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
}

export default function HistoryPage() {
    const router = useRouter();
    const { isAuthenticated, loading: authLoading } = useAuth();
    const [history, setHistory] = useState([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(0); // 0-indexed
    const [loading, setLoading] = useState(true);
    const [allRecords, setAllRecords] = useState([]); // for CSV export

    useEffect(() => {
        if (!authLoading && !isAuthenticated) {
            router.push('/login');
        }
    }, [authLoading, isAuthenticated, router]);

    const loadHistory = useCallback(async (pageIndex) => {
        setLoading(true);
        try {
            const data = await getHistory(PAGE_SIZE, pageIndex * PAGE_SIZE);
            setHistory(data.predictions);
            setTotal(data.total);
        } catch (err) {
            console.error('Failed to load history:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    // Load all records once for CSV export
    const loadAllForExport = useCallback(async () => {
        try {
            const data = await getHistory(100, 0);
            setAllRecords(data.predictions);
            exportToCSV(data.predictions);
        } catch (err) {
            console.error('CSV export failed:', err);
        }
    }, []);

    useEffect(() => {
        if (isAuthenticated) {
            loadHistory(page);
        }
    }, [isAuthenticated, page, loadHistory]);

    const totalPages = Math.ceil(total / PAGE_SIZE);

    if (authLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <svg className="animate-scientific-spin h-8 w-8 text-green-600" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
            </div>
        );
    }

    if (!isAuthenticated) return null;

    return (
        <div className="min-h-screen flex flex-col relative">
            <Navbar />

            <main className="flex-1 p-6 lg:p-12 animate-fade-in relative z-10">
                <div className="max-w-5xl mx-auto">
                    <div className="flex flex-col md:flex-row md:justify-between md:items-end mb-8 gap-4">
                        <div>
                            <h1 className="text-3xl font-bold tracking-tight text-foreground mb-2">Prediction History</h1>
                            <p className="text-muted-foreground text-sm">
                                Review and compare your past drug–target interaction predictions.
                                {total > 0 && <span className="ml-1 text-muted-foreground">({total} total)</span>}
                            </p>
                        </div>
                        <div className="flex items-center gap-3 flex-wrap self-start md:self-auto">
                            {total > 0 && (
                                <button
                                    type="button"
                                    onClick={loadAllForExport}
                                    className="btn-ghost text-sm border border-border flex items-center gap-2 py-2 px-4 h-auto"
                                >
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                    </svg>
                                    Export CSV
                                </button>
                            )}
                            <Link href="/dashboard" className="btn-premium inline-flex items-center gap-2 whitespace-nowrap self-start py-2 px-4 h-auto text-sm">
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                                </svg>
                                New Prediction
                            </Link>
                        </div>
                    </div>

                    {loading ? (
                        <div className="glass-card p-12 flex flex-col items-center justify-center">
                            <div className="w-full space-y-3">
                                {[...Array(5)].map((_, i) => (
                                    <div key={i} className="h-12 rounded-lg bg-secondary animate-pulse" />
                                ))}
                            </div>
                        </div>
                    ) : history.length === 0 ? (
                        <div className="glass-card p-16 text-center">
                            <svg className="w-16 h-16 mx-auto border-dashed border-2 border-gray-300 text-muted-foreground rounded-full p-4 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                            </svg>
                            <h3 className="text-lg font-semibold text-foreground mb-2">No predictions yet</h3>
                            <p className="text-muted-foreground text-sm mb-6 max-w-sm mx-auto">
                                Run your first analysis to see results here.
                            </p>
                            <Link href="/dashboard" className="btn-premium text-sm inline-block">Run prediction</Link>
                        </div>
                    ) : (
                        <div className="glass-card overflow-hidden">
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm text-left">
                                    <thead className="bg-secondary text-muted-foreground text-xs uppercase tracking-wider font-semibold border-b border-border">
                                        <tr>
                                            <th scope="col" className="py-4 px-6">Drug</th>
                                            <th scope="col" className="py-4 px-6">Protein Target</th>
                                            <th scope="col" className="py-4 px-6 text-right">pKd (log)</th>
                                            <th scope="col" className="py-4 px-6 text-right">Confidence</th>
                                            <th scope="col" className="py-4 px-6 text-right">Date</th>
                                            <th scope="col" className="py-4 px-4 text-center">Copy</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/5">
                                        {history.map((item) => {
                                            const drugDisplay = item.drug_label || (item.drug_smiles.length > 20 ? `${item.drug_smiles.substring(0, 20)}…` : item.drug_smiles);
                                            const proteinDisplay = item.protein_label || (item.protein_sequence.length > 20 ? `${item.protein_sequence.substring(0, 20)}…` : item.protein_sequence);
                                            return (
                                                <tr key={item.id} className="hover:bg-white/[0.02] transition-colors">
                                                    <td className="py-4 px-6 font-semibold text-foreground">
                                                        <div className="flex flex-col">
                                                            <span>{drugDisplay}</span>
                                                            {item.drug_label && item.drug_smiles && (
                                                                <span className="text-xs text-muted-foreground font-mono mt-0.5">
                                                                    {item.drug_smiles.length > 22 ? `${item.drug_smiles.substring(0, 22)}…` : item.drug_smiles}
                                                                </span>
                                                            )}
                                                        </div>
                                                    </td>
                                                    <td className="py-4 px-6 text-muted-foreground">{proteinDisplay}</td>
                                                    <td className="py-4 px-6 text-right font-semibold text-foreground">
                                                        {formatFixed(item.log_affinity ?? item.affinity)}
                                                    </td>
                                                    <td className="py-4 px-6 text-right">
                                                        <ConfidenceBadge value={item.confidence} />
                                                    </td>
                                                    <td className="py-4 px-6 text-right text-muted-foreground text-xs font-semibold tracking-wide">
                                                        {new Date(item.created_at).toLocaleDateString(undefined, {
                                                            year: 'numeric',
                                                            month: 'short',
                                                            day: 'numeric'
                                                        })}
                                                    </td>
                                                    <td className="py-4 px-4 text-center">
                                                        <CopyButton text={`SMILES: ${item.drug_smiles}\nSequence: ${item.protein_sequence}`} />
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>

                            {totalPages > 1 && (
                                <div className="flex items-center justify-between px-6 py-4 border-t border-border bg-white/[0.01]">
                                    <p className="text-xs text-muted-foreground">
                                        Page {page + 1} of {totalPages} &bull; {total} total
                                    </p>
                                    <div className="flex items-center gap-2">
                                        <button
                                            type="button"
                                            disabled={page === 0}
                                            onClick={() => setPage((p) => Math.max(0, p - 1))}
                                            className="btn-ghost text-xs px-3 py-1.5 h-auto border border-border disabled:opacity-30 disabled:cursor-not-allowed"
                                        >
                                            ← Previous
                                        </button>
                                        <button
                                            type="button"
                                            disabled={page >= totalPages - 1}
                                            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                                            className="btn-ghost text-xs px-3 py-1.5 h-auto border border-border disabled:opacity-30 disabled:cursor-not-allowed"
                                        >
                                            Next →
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </main>

            <Footer />
        </div>
    );
}
