'use client';

import { useEffect, useRef, useState } from 'react';
import { downloadFile } from '@/utils/download';
import { resolveProteinModel } from '@/services/api-client';

const SCRIPT_SRC = '/3Dmol-min.js';

function loadThreeDMol() {
    return new Promise((resolve, reject) => {
        if (typeof window !== 'undefined' && window.$3Dmol) {
            resolve();
            return;
        }
        const existing = document.querySelector(`script[src="${SCRIPT_SRC}"]`);
        if (existing) {
            existing.addEventListener('load', () => resolve());
            existing.addEventListener('error', reject);
            return;
        }
        const script = document.createElement('script');
        script.src = SCRIPT_SRC;
        script.async = true;
        script.onload = () => resolve();
        script.onerror = reject;
        document.body.appendChild(script);
    });
}

export default function ProteinStructureViewer3D({ proteinLabel, proteinSequence, className = '' }) {
    const containerRef = useRef(null);
    const viewerRef = useRef(null);
    const [status, setStatus] = useState('loading');
    const [errMsg, setErrMsg] = useState('');
    const [modelData, setModelData] = useState(null);

    useEffect(() => {
        if (!containerRef.current) return undefined;

        let cancelled = false;

        async function loadStructure() {
            setStatus('loading');
            setErrMsg('');

            try {
                await loadThreeDMol();
                if (cancelled || !containerRef.current) return;

                const model = await resolveProteinModel(proteinLabel, proteinSequence);
                if (cancelled || !containerRef.current) return;

                setModelData(model);

                const $3Dmol = window.$3Dmol;
                containerRef.current.innerHTML = '';
                const viewer = $3Dmol.createViewer(containerRef.current, {
                    backgroundColor: 'black',
                });
                viewerRef.current = viewer;

                viewer.addModel(model.model_data, model.format);
                viewer.setStyle({}, { cartoon: { color: 'spectrum' } });
                viewer.zoomTo();
                viewer.render();
                setStatus('ready');
            } catch (error) {
                if (cancelled) return;
                setStatus('error');
                setErrMsg(error?.message || 'Unable to render protein 3D model.');
            }
        }

        loadStructure();

        return () => {
            cancelled = true;
            if (viewerRef.current) {
                try {
                    viewerRef.current.clear();
                } catch {
                    // ignore
                }
                viewerRef.current = null;
            }
        };
    }, [proteinLabel, proteinSequence]);

    return (
        <div className={`relative rounded-xl overflow-hidden border border-gray-200 bg-black/60 ${className}`}>
            <div ref={containerRef} className="h-full w-full min-h-[240px]" />
            {status === 'loading' && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/80 backdrop-blur-sm z-10">
                    <svg className="animate-scientific-spin h-10 w-10 text-violet-400 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15m11.62-5.12l-8.24 10.24m0-10.24l8.24 10.24" opacity="0.4"/>
                        <circle cx="12" cy="12" r="3" fill="currentColor" opacity="0.8"/>
                        <circle cx="12" cy="4.5" r="1.5" fill="currentColor"/>
                        <circle cx="12" cy="19.5" r="1.5" fill="currentColor"/>
                        <circle cx="19.5" cy="12" r="1.5" fill="currentColor"/>
                        <circle cx="4.5" cy="12" r="1.5" fill="currentColor"/>
                        <circle cx="17.62" cy="6.88" r="1.5" fill="currentColor"/>
                        <circle cx="6.38" cy="17.12" r="1.5" fill="currentColor"/>
                        <circle cx="6.38" cy="6.88" r="1.5" fill="currentColor"/>
                        <circle cx="17.62" cy="17.12" r="1.5" fill="currentColor"/>
                    </svg>
                    <div className="text-xs text-violet-300 font-medium tracking-wide">Resolving Protein Structure</div>
                    <div className="text-[10px] text-violet-300/60 mt-1">Checking AlphaFold, PDB, and ESMFold...</div>
                </div>
            )}
            {status === 'error' && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/75 p-4 text-center text-sm text-amber-200/90 z-10">
                    <p>{errMsg}</p>
                    <p className="mt-2 text-xs text-gray-700">This protein could not be folded or found.</p>
                </div>
            )}

            {status === 'ready' && modelData && (
                <button
                    onClick={() => downloadFile(modelData.model_data, `${proteinLabel || 'protein'}.${modelData.format}`, 'text/plain')}
                    className="absolute top-3 right-3 text-[10px] text-gray-300 bg-[#111827]/80 hover:bg-gray-700/20 border border-gray-700/30 px-2.5 py-1.5 rounded flex items-center gap-1.5 transition-colors backdrop-blur-md"
                    title={`Download 3D Structure as ${modelData.format.toUpperCase()}`}
                >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    Export {modelData.format.toUpperCase()}
                </button>
            )}
        </div>
    );
}
