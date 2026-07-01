import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';

export default function AboutPage() {
    return (
        <div className="min-h-screen flex flex-col relative overflow-hidden">

            <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-green-700/8 rounded-full blur-[150px] -z-10 pointer-events-none" />

            <Navbar />

            <main className="flex-1 p-6 md:p-12 overflow-auto relative z-10">
                <div className="max-w-3xl mx-auto space-y-6">

                    <div>
                        <h1 className="text-3xl md:text-4xl font-bold text-slate-900 mb-3">
                            Drug Target Interaction Prediction System
                        </h1>
                        <p className="text-gray-600 leading-relaxed">
                            A deep learning based system for predicting binding affinity between drug molecules and protein targets,
                            enabling large-scale screening across thousands of compounds as well as single drug protein pair analysis.
                            Developed as a Final Year Project at PIEAS by Syed Hassan Raza and Muhammad Asim Nawaz, supervised by Dr. Abdul Majid.
                        </p>
                    </div>

                    <details className="glass-card p-5 rounded-xl group">
                        <summary className="cursor-pointer text-lg font-semibold text-slate-900 flex justify-between items-center">
                            Problem Overview
                            <span className="transition-transform group-open:rotate-180">⌄</span>
                        </summary>

                        <p className="mt-4 text-sm text-gray-700 leading-relaxed">
                            Identifying interactions between drug compounds and biological targets is a fundamental step in drug discovery.
                            Traditional wet-lab screening is expensive, time-consuming, and not scalable across large chemical spaces.
                            This system addresses the problem by learning interaction patterns computationally and predicting binding affinity
                            before experimental validation.
                        </p>
                    </details>

                    <details className="glass-card p-5 rounded-xl group" open>
                        <summary className="cursor-pointer text-lg font-semibold text-slate-900 flex justify-between items-center">
                            Technical Approach
                            <span className="transition-transform group-open:rotate-180">⌄</span>
                        </summary>

                        <ul className="mt-4 text-sm text-gray-700 space-y-3">
                            <li>
                                <strong>Drug Representation:</strong> Molecular structures are converted into graph representations
                                and processed using a <strong>GNN (Graph Neural Network)</strong>.
                            </li>
                            <li>
                                <strong>Protein Representation:</strong> Encoded using <strong>Transformer-based embeddings</strong>.
                            </li>
                            <li>
                                <strong>Feature Merging:</strong> Integrates both modalities using a combination of <strong>cross-attention</strong> and <strong>gated attention</strong> mechanisms.
                            </li>
                            <li>
                                <strong>Prediction Task:</strong> Regression to estimate <strong>pKd</strong>.
                            </li>
                        </ul>
                    </details>

                    <details className="glass-card p-5 rounded-xl group">
                        <summary className="cursor-pointer text-lg font-semibold text-slate-900 flex justify-between items-center">
                            Data & Evaluation
                            <span className="transition-transform group-open:rotate-180">⌄</span>
                        </summary>

                        <p className="mt-4 text-sm text-gray-700 leading-relaxed">
                            The model is trained and evaluated using the <strong>BindingDB</strong> dataset, adopting a <strong>drug-cold split strategy</strong> to ensure robust evaluation on unseen compounds.
                        </p>
                    </details>

                    <details className="glass-card p-5 rounded-xl group">
                        <summary className="cursor-pointer text-lg font-semibold text-slate-900 flex justify-between items-center">
                            Model Outputs
                            <span className="transition-transform group-open:rotate-180">⌄</span>
                        </summary>

                        <ul className="mt-4 text-sm text-gray-700 space-y-2">
                            <li>
                                <strong>pKd Value:</strong> Higher values indicate stronger binding.
                            </li>
                            <li>
                                <strong>Binding Strength:</strong> Interpreted from pKd.
                            </li>
                        </ul>
                    </details>

                    <details className="glass-card p-5 rounded-xl group">
                        <summary className="cursor-pointer text-lg font-semibold text-slate-900 flex justify-between items-center">
                            Practical Impact
                            <span className="transition-transform group-open:rotate-180">⌄</span>
                        </summary>

                        <p className="mt-4 text-sm text-gray-700 leading-relaxed">
                            Helps prioritize promising drug candidates and reduce the search space before laboratory testing.
                        </p>
                    </details>

                    <details className="glass-card p-5 rounded-xl group">
                        <summary className="cursor-pointer text-lg font-semibold text-slate-900 flex justify-between items-center">
                            Implementation
                            <span className="transition-transform group-open:rotate-180">⌄</span>
                        </summary>

                        <p className="mt-4 text-sm text-gray-700">
                            Built using Next.js (frontend), FastAPI (backend), and deep learning frameworks for inference.
                        </p>
                    </details>

                </div>
            </main>

            <Footer />
        </div>
    );
}
