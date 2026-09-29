import React, { useEffect, useState } from 'react';
import { useStore } from '@/store/useStore';
import { fetchDataSources } from '@/lib/api';
import { DataSourceItem } from '@/types';
import { SourceBadge } from '@/components/ui/Badge';
import { X, Database, ShieldCheck, CheckCircle2 } from 'lucide-react';

export const DataSourcesModal: React.FC = () => {
  const { dataSourcesModalOpen, setDataSourcesModalOpen } = useStore();
  const [datasets, setDatasets] = useState<DataSourceItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!dataSourcesModalOpen) return;
    fetchDataSources()
      .then(res => {
        setDatasets(res.sources);
        setLoading(false);
      })
      .catch(err => {
        console.error('Error fetching data sources:', err);
        setLoading(false);
      });
  }, [dataSourcesModalOpen]);

  if (!dataSourcesModalOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="glass-panel w-full max-w-4xl max-h-[85vh] rounded-2xl p-6 shadow-2xl border border-white/10 flex flex-col text-slate-100">
        {/* Header */}
        <div className="flex items-start justify-between pb-4 border-b border-white/10">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-sky-500/20 text-sky-400 border border-sky-500/30">
                <Database className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-slate-100 tracking-tight">Data Provenance & Sensor Catalog</h2>
                <p className="text-xs text-slate-400">Strict transparency protocol distinguishing empirical ground measurements from AI inferences.</p>
              </div>
            </div>
          </div>
          <button
            onClick={() => setDataSourcesModalOpen(false)}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-white/10 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Legend Classification Badges Info */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 my-4">
          <div className="p-3 rounded-xl bg-blue-950/30 border border-blue-500/30 flex items-start gap-2.5">
            <span className="p-1 rounded bg-blue-500/20 text-blue-400">
              <CheckCircle2 className="w-4 h-4" />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-xs text-blue-300">REAL</span>
                <SourceBadge badge="[REAL]" />
              </div>
              <p className="text-[11px] text-slate-300 mt-1">
                Empirical physical measurements: core drill logs, assay lab grades, IBM statutory lease boundaries, and GSI quadrangle maps.
              </p>
            </div>
          </div>

          <div className="p-3 rounded-xl bg-emerald-950/30 border border-emerald-500/30 flex items-start gap-2.5">
            <span className="p-1 rounded bg-emerald-500/20 text-emerald-400">
              <CheckCircle2 className="w-4 h-4" />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-xs text-emerald-300">MODELED</span>
                <SourceBadge badge="[MODELED]" />
              </div>
              <p className="text-[11px] text-slate-300 mt-1">
                Calibrated AI & geostatistical outputs: 3D kriging block grades, Sentinel-2 spectral indices, CHIRPS rainfall, and machine learning shortfall models.
              </p>
            </div>
          </div>

          <div className="p-3 rounded-xl bg-purple-950/30 border border-purple-500/30 flex items-start gap-2.5">
            <span className="p-1 rounded bg-purple-500/20 text-purple-400">
              <CheckCircle2 className="w-4 h-4" />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-xs text-purple-300">SYNTHETIC</span>
                <SourceBadge badge="[SYNTHETIC]" />
              </div>
              <p className="text-[11px] text-slate-300 mt-1">
                Generated proxy simulations: downscaled SMAP soil moisture and Landsat thermal data for demonstration and offline air-gapped demo fidelity.
              </p>
            </div>
          </div>
        </div>

        {/* Datasets Table/Cards */}
        <div className="flex-1 overflow-y-auto pr-2 space-y-3">
          {loading ? (
            <div className="text-center py-12 text-slate-400">Loading catalog metadata...</div>
          ) : (
            datasets.map((item) => (
              <div
                key={item.id}
                className="p-3.5 rounded-xl bg-slate-900/60 border border-white/5 hover:border-sky-500/30 transition-colors"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm text-slate-200">{item.title}</span>
                    <SourceBadge badge={item.badge} />
                  </div>
                  <span className="text-[11px] font-mono text-sky-400 bg-sky-950/60 px-2 py-0.5 rounded border border-sky-500/20 self-start sm:self-auto">
                    {item.organization}
                  </span>
                </div>

                <p className="text-xs text-slate-300 mt-1.5 leading-relaxed">{item.description}</p>

                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mt-3 pt-2 border-t border-white/5 text-[11px] text-slate-400">
                  <div>
                    <span className="text-slate-500 block text-[10px] uppercase">Spatial Resolution</span>
                    <span className="font-mono text-slate-300">{item.resolution}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px] uppercase">Temporal Cadence</span>
                    <span className="font-mono text-slate-300">{item.cadence}</span>
                  </div>
                  <div className="col-span-2 sm:col-span-1">
                    <span className="text-slate-500 block text-[10px] uppercase">Compliance & Protocol</span>
                    <span className="font-mono text-slate-300 truncate">{item.license}</span>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="pt-4 mt-3 border-t border-white/10 flex items-center justify-between text-xs text-slate-400">
          <div className="flex items-center gap-1.5">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>MOIL Ltd Data Governance & Transparency Guidelines</span>
          </div>
          <button
            onClick={() => setDataSourcesModalOpen(false)}
            className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
