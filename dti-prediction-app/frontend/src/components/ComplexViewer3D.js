'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { getIllustrativeBindingRegion } from '@/components/ProteinSequencePanel';
import { resolveProteinModel, resolveLigandModel, dockComplex } from '@/services/api-client';
import { downloadFile } from '@/utils/download';

const SCRIPT_SRC = '/3Dmol-min.js';

function loadThreeDMol() {
    return new Promise((resolve, reject) => {
        if (typeof window !== 'undefined' && window.$3Dmol) return resolve();

        const existing = document.querySelector(`script[src="${SCRIPT_SRC}"]`);
        if (existing) {
            existing.addEventListener('load', resolve);
            existing.addEventListener('error', reject);
            return;
        }

        const s = document.createElement('script');
        s.src = SCRIPT_SRC;
        s.async = true;
        s.onload = resolve;
        s.onerror = reject;
        document.body.appendChild(s);
    });
}

function meanXYZ(atoms) {
    const out = { x: 0, y: 0, z: 0, count: 0 };
    for (const a of atoms) {
        if (typeof a?.x !== 'number') continue;
        out.x += a.x;
        out.y += a.y;
        out.z += a.z;
        out.count++;
    }
    if (!out.count) return null;
    return { x: out.x / out.count, y: out.y / out.count, z: out.z / out.count };
}

export default function ComplexViewer3D({
    proteinLabel,
    proteinSequence,
    smiles,
    className = '',
    onDockingInfo,
}) {
    const containerRef = useRef(null);

    const [status, setStatus] = useState('loading');
    const [errMsg, setErrMsg] = useState('');
    const [dockMode, setDockMode] = useState('');
    const [dockScore, setDockScore] = useState(null);
    const [complexData, setComplexData] = useState(null);

    const seqClean = (proteinSequence || '').replace(/\s/g, '');

    const bindingRegion = useMemo(() => {
        const { start, end } = getIllustrativeBindingRegion(proteinSequence || '');
        const fromResid = start + 1;
        const toResid = Math.max(fromResid, end);
        return { fromResid, toResid };
    }, [proteinSequence]);

    useEffect(() => {
        if (!containerRef.current || !smiles?.trim() || !seqClean) return;

        let cancelled = false;

        async function run() {
            setStatus('loading');
            setErrMsg('');
            setDockMode('');
            setDockScore(null);

            try {
                await loadThreeDMol();
                if (cancelled) return;

                containerRef.current.innerHTML = '';

                const viewer = window.$3Dmol.createViewer(containerRef.current, {
                    backgroundColor: '#0b0f14',
                });

                const proteinResolved = await resolveProteinModel(proteinLabel, proteinSequence);
                const ligandResolved = await resolveLigandModel(smiles.trim());

                if (cancelled) return;

                let proteinData = proteinResolved.model_data;
                let proteinFormat = proteinResolved.format;
                let ligandData = ligandResolved.model_data;
                let ligandFormat = ligandResolved.format;

                let usedDocking = false;

                try {
                    const docked = await dockComplex({
                        protein_model_data: proteinData,
                        protein_format: proteinFormat,
                        ligand_model_data: ligandData,
                        ligand_format: ligandFormat,
                        protein_label: proteinLabel || null,
                        ligand_smiles: smiles || null,
                    });

                    if (docked?.ligand_pose_data) {
                        ligandData = docked.ligand_pose_data;
                        ligandFormat = docked.ligand_format || ligandFormat;

                        if (docked?.protein_model_data) {
                            proteinData = docked.protein_model_data;
                            proteinFormat = docked.protein_format || proteinFormat;
                        }

                        usedDocking = true;
                        setDockMode('true_docking');
                        setDockScore(docked.score ?? null);

                        onDockingInfo?.({
                            mode: 'true_docking',
                            score: docked.score ?? null,
                        });
                    }
                } catch {
                    setDockMode('illustrative');
                    onDockingInfo?.({ mode: 'illustrative' });
                }

                setComplexData({
                    protein: { data: proteinData, format: proteinFormat },
                    ligand: { data: ligandData, format: ligandFormat }
                });

                const proteinModel = viewer.addModel(proteinData, proteinFormat);
                const ligandModel = viewer.addModel(ligandData, ligandFormat);

                viewer.setStyle(
                    { model: proteinModel },
                    { cartoon: { color: 'spectrum' } }
                );

                viewer.setStyle(
                    { model: ligandModel },
                    {
                        stick: { radius: 0.35, colorscheme: 'cyanCarbon' },
                        sphere: { scale: 0.45 },
                    }
                );

                const { fromResid, toResid } = bindingRegion;

                viewer.setStyle(
                    { model: proteinModel, resi: `${fromResid}-${toResid}`, byres: true },
                    {
                        stick: { radius: 0.35, color: '#2dd4bf' },
                        sphere: { scale: 0.3, color: '#2dd4bf' },
                    }
                );

                if (!usedDocking) {
                    const proteinAtoms = proteinModel.selectedAtoms({ resi: `${fromResid}-${toResid}` });
                    const ligandAtoms = ligandModel.selectedAtoms({});

                    const pc = meanXYZ(proteinAtoms);
                    const lc = meanXYZ(ligandAtoms);

                    if (pc && lc) {
                        const dx = pc.x - lc.x;
                        const dy = pc.y - lc.y;
                        const dz = pc.z - lc.z;

                        ligandAtoms.forEach(a => {
                            a.x += dx;
                            a.y += dy;
                            a.z += dz;
                        });
                    }
                }

                viewer.zoomTo();
                viewer.render();

                if (!cancelled) setStatus('ready');
            } catch (e) {
                if (!cancelled) {
                    setStatus('error');
                    setErrMsg(e.message || 'Rendering failed');
                }
            }
        }

        run();
        return () => (cancelled = true);
    }, [proteinLabel, proteinSequence, smiles, bindingRegion]);

    return (
        <div className={`relative rounded-2xl overflow-hidden border border-gray-800 bg-[#0b0f14] shadow-lg ${className}`}>

            <div ref={containerRef} className="h-full w-full min-h-[320px]" />

            {dockMode === 'true_docking' && (
                <div className="absolute top-3 left-3 rounded-lg bg-black/80 border border-gray-700 px-3 py-2">
                    <p className="text-xs text-white font-semibold">Docked Pose</p>
                    {dockScore !== null && (
                        <p className="text-[10px] text-gray-400">Score: {dockScore}</p>
                    )}
                </div>
            )}

            {dockMode === 'illustrative' && (
                <div className="absolute bottom-12 left-3 right-3 rounded-lg bg-black/90 border border-amber-500/30 p-2.5 backdrop-blur-sm z-10">
                    <p className="text-[10px] sm:text-xs text-amber-400 font-semibold leading-relaxed">
                        ⚠️ Illustrative Pose: Geometric alignment based on predicted binding interface. Run offline molecular docking for energy-minimized orientations.
                    </p>
                </div>
            )}



            {status === 'ready' && (
                <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 via-black/40 to-transparent px-4 py-3">
                    <div className="flex flex-wrap gap-4 text-[11px] text-gray-300">
                        {proteinLabel && (
                            <span>
                                Protein: <span className="text-white">{proteinLabel}</span>
                            </span>
                        )}
                        <span>
                            Chain: <span className="text-white">{seqClean.length}</span>
                        </span>
                        <span>
                            Interface: <span className="text-white">
                                {bindingRegion.fromResid}–{bindingRegion.toResid}
                            </span>
                        </span>
                    </div>
                </div>
            )}

            {status === 'loading' && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#0b0f14] text-gray-300">
                    <div className="w-8 h-8 border-2 border-gray-500 border-t-transparent rounded-full animate-scientific-spin mb-3" />
                    Rendering complex...
                </div>
            )}

            {status === 'error' && (
                <div className="absolute inset-0 flex items-center justify-center bg-black text-red-400 text-sm">
                    {errMsg}
                </div>
            )}

            {status === 'ready' && complexData && (
                <>
                    <button
                        onClick={() => downloadFile(complexData.ligand.data, `ligand_${smiles ? smiles.slice(0, 10).replace(/[^a-z0-9]/gi, '') : 'pose'}.${complexData.ligand.format}`, 'chemical/x-mdl-molfile')}
                        className="absolute top-3 left-3 text-[10px] text-gray-300 bg-[#111827]/80 hover:bg-gray-700/20 border border-gray-700/30 px-2.5 py-1.5 rounded flex items-center gap-1.5 transition-colors backdrop-blur-md"
                        title="Download Ligand Pose"
                    >
                        <span>Export Ligand</span>
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                        </svg>
                    </button>
                    <button
                        onClick={() => downloadFile(complexData.protein.data, `protein_${proteinLabel ? proteinLabel.replace(/[^a-z0-9]/gi, '') : 'target'}.${complexData.protein.format}`, 'text/plain')}
                        className="absolute top-3 right-3 text-[10px] text-violet-300 bg-[#111827]/80 hover:bg-violet-500/20 border border-violet-500/30 px-2.5 py-1.5 rounded flex items-center gap-1.5 transition-colors backdrop-blur-md"
                        title="Download Protein Structure"
                    >
                        <span>Export Protein</span>
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                        </svg>
                    </button>
                </>
            )}
        </div>
    );
}
