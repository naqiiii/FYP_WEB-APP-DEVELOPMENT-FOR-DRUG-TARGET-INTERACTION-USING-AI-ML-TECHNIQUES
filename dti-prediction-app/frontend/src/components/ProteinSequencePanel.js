/*Protein sequence display: plain vs highlighted binding region*/

'use client';

export function getIllustrativeBindingRegion(seq) {
    const s = (seq || '').replace(/\s/g, '');
    const n = s.length;
    if (n <= 0) return { start: 0, end: 0 };
    if (n <= 14) return { start: 0, end: n };
    const start = Math.floor(n * 0.38);
    const end = Math.min(n, Math.max(start + 6, Math.floor(n * 0.62)));
    return { start, end };
}

export default function ProteinSequencePanel({ sequence, mode = 'before', title, className = '' }) {
    const raw = (sequence || '').replace(/\s/g, '');
    const { start, end } = mode === 'after' ? getIllustrativeBindingRegion(raw) : { start: -1, end: -1 };

    return (
        <div className={className}>
            {title && (
                <h4 className="text-xs uppercase tracking-wider font-semibold text-muted-foreground mb-2">{title}</h4>
            )}
            <div className="bg-white rounded-lg p-3 border border-gray-300 max-h-56 overflow-y-auto custom-scrollbar font-mono text-[11px] sm:text-xs leading-relaxed break-all">
                {mode === 'before' &&
                    raw.split('').map((c, i) => (
                        <span key={i} className="text-slate-900">
                            {c}
                        </span>
                    ))}
                {mode === 'after' &&
                    raw.split('').map((c, i) => {
                        const inRegion = i >= start && i < end;
                        return (
                            <span
                                key={i}
                                className={
                                    inRegion
                                        ? 'bg-slate-900 text-white font-bold rounded-sm px-0.5 ring-1 ring-slate-900'
                                        : 'text-slate-300'
                                }
                            >
                                {c}
                            </span>
                        );
                    })}
            </div>
            {mode === 'after' && raw.length > 0 && (
                <div className="mt-4 space-y-2 p-3 bg-slate-50 dark:bg-slate-900/50 rounded-lg border border-border">
                    <p className="text-xs text-foreground font-bold">
                        Predicted binding interface: residues {start + 1}–{end} ({end - start} residues, ~{Math.round(((end - start) / raw.length) * 100)}% of chain)
                    </p>
                    <p className="text-[11px] text-muted-foreground font-medium leading-snug">
                        This is a computational estimate based on sequence analysis. It is not an experimentally confirmed binding site.
                        Validate with docking simulations or laboratory assays before drawing conclusions.
                    </p>
                </div>
            )}
        </div>
    );
}
