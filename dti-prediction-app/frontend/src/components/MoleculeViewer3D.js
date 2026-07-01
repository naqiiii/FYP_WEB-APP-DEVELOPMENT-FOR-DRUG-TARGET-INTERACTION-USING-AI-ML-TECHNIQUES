/*3Dmol.js viewer for a drug SMILES*/

'use client';

import { useEffect, useRef, useState } from 'react';
import { downloadFile } from '@/utils/download';
import { resolveLigandModel } from '@/services/api-client';

const SCRIPT_SRC = 'https://3dmol.org/build/3Dmol-min.js';

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
        const s = document.createElement('script');
        s.src = SCRIPT_SRC;
        s.async = true;
        s.onload = () => resolve();
        s.onerror = reject;
        document.body.appendChild(s);
    });
}

export default function MoleculeViewer3D({ smiles, className = '' }) {
    const containerRef = useRef(null);
    const viewerRef = useRef(null);
    const [status, setStatus] = useState('loading');
    const [errMsg, setErrMsg] = useState('');
    const [sdfData, setSdfData] = useState(null);

    useEffect(() => {
        if (!smiles?.trim() || !containerRef.current) return undefined;

        let cancelled = false;

        async function run() {
            setStatus('loading');
            setErrMsg('');
            try {
                await loadThreeDMol();
                if (cancelled || !containerRef.current) return;

                const $3Dmol = window.$3Dmol;
                containerRef.current.innerHTML = '';
                const viewer = $3Dmol.createViewer(containerRef.current, {
                    backgroundColor: 'black',
                });
                viewerRef.current = viewer;

                const model = await resolveLigandModel(smiles.trim());
                if (cancelled || !viewerRef.current) return;

                const sdf = model.model_data;
                setSdfData(sdf);

                viewer.addModel(sdf, 'sdf');
                viewer.setStyle({}, { stick: { radius: 0.12 }, sphere: { scale: 0.2 } });
                viewer.zoomTo();
                viewer.render();
                setStatus('ready');
            } catch (e) {
                if (!cancelled) {
                    setStatus('error');
                    setErrMsg(e?.message || 'Load failed');
                }
            }
        }

        run();

        return () => {
            cancelled = true;
            if (viewerRef.current) {
                try {
                    viewerRef.current.clear();
                } catch {
                }
                viewerRef.current = null;
            }
        };
    }, [smiles]);

    return (
        <div className={`relative rounded-xl overflow-hidden border border-gray-200 bg-black/60 ${className}`}>
            <div ref={containerRef} className="h-full w-full min-h-[240px]" />
            {status === 'loading' && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/80 backdrop-blur-sm z-10">
                    <svg className="animate-scientific-spin h-10 w-10 text-cyan-400 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
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
                    <div className="text-xs text-cyan-300 font-medium tracking-wide">Resolving Ligand Structure</div>
                    <div className="text-[10px] text-cyan-300/60 mt-1">Generating 3D coordinates on-the-fly...</div>
                </div>
            )}
            {status === 'error' && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/75 p-4 text-center text-sm text-amber-200/90 z-10">
                    <p>3D viewer: {errMsg}</p>
                    <p className="mt-2 text-xs text-gray-700">Use the 2D structure below if available.</p>
                </div>
            )}

            {status === 'ready' && sdfData && (
                <button
                    onClick={() => downloadFile(sdfData, `ligand_${smiles.slice(0, 10)}.sdf`, 'chemical/x-mdl-molfile')}
                    className="absolute top-3 right-3 text-[10px] text-green-400 bg-[#111827]/80 hover:bg-green-700/20 border border-green-700/30 px-2.5 py-1.5 rounded flex items-center gap-1.5 transition-colors backdrop-blur-md"
                    title="Download 3D Structure as SDF format"
                >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    Export SDF
                </button>
            )}
        </div>
    );
}
