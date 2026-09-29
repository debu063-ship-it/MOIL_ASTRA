import React, { useEffect, useState } from 'react';
import { useStore } from '@/store/useStore';
import { ProductionData, CorrectiveAction, ShapData, ZoneProperties, WhatIfResult } from '@/types';
import { calculateSimulationAsync, baselineSimulation } from '@/lib/simulate';
import { exportToPdf, exportToExcel, exportToCsv } from '@/lib/export';
import { LAYER_REGISTRY } from '@/lib/layers';
import { SourceBadge } from '@/components/ui/Badge';
import { 
  FileText, 
  FileSpreadsheet, 
  Download, 
  CheckCircle2, 
  Layers, 
  Sparkles, 
  Loader2 
} from 'lucide-react';

interface Step5Props {
  zone: ZoneProperties | null;
  production: ProductionData | null;
  mine: string;
  actionsList: CorrectiveAction[];
  shap: ShapData | null;
  onDone: () => void;
}

export const Step5Export: React.FC<Step5Props> = ({ 
  zone, 
  production, 
  mine,
  actionsList, 
  shap, 
  onDone 
}) => {
  const { whatIf, actions, layers } = useStore();
  const [isExportingPdf, setIsExportingPdf] = useState(false);
  const [isExportingExcel, setIsExportingExcel] = useState(false);
  const [isExportingCsv, setIsExportingCsv] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Run the trained backend model for the current slider state
  const targetMT = production?.metadata.monthlyTargetMT ?? 40000;
  const baselineRatio = production?.metadata.shortfallPercent ?? 0.12;
  const [whatIfResult, setWhatIfResult] = useState<WhatIfResult>(
    () => baselineSimulation(targetMT, baselineRatio)
  );
  useEffect(() => {
    let cancelled = false;
    calculateSimulationAsync(whatIf, mine, production)
      .then((r) => { if (!cancelled) setWhatIfResult(r); })
      .catch(console.error);
    return () => { cancelled = true; };
  }, [whatIf, mine, production]);

  // Active layers
  const activeLayers = LAYER_REGISTRY.filter(l => layers.layers[l.id]?.visible);

  const getExportData = () => {
    // Try to get Cesium canvas
    const canvas = document.querySelector('.cesium-viewer canvas') as HTMLCanvasElement | null;
    return {
      zone,
      production,
      actions: actionsList,
      actionStatuses: actions,
      shap,
      whatIf,
      whatIfResult,
      activeLayers,
      mapCanvas: canvas
    };
  };

  const handlePdfExport = async () => {
    setIsExportingPdf(true);
    setSuccessMsg(null);
    try {
      await exportToPdf(getExportData());
      setSuccessMsg('PDF Report downloaded successfully!');
    } catch (e) {
      console.error('PDF export failed:', e);
    } finally {
      setIsExportingPdf(false);
    }
  };

  const handleExcelExport = () => {
    setIsExportingExcel(true);
    setSuccessMsg(null);
    try {
      exportToExcel(getExportData());
      setSuccessMsg('Excel Workbook downloaded successfully!');
    } catch (e) {
      console.error('Excel export failed:', e);
    } finally {
      setIsExportingExcel(false);
    }
  };

  const handleCsvExport = () => {
    setIsExportingCsv(true);
    setSuccessMsg(null);
    try {
      exportToCsv(getExportData());
      setSuccessMsg('CSV forecast data downloaded successfully!');
    } catch (e) {
      console.error('CSV export failed:', e);
    } finally {
      setIsExportingCsv(false);
    }
  };

  const acceptedCount = actionsList.filter(a => (actions[a.id] || a.status) === 'accepted').length;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h3 className="text-xs font-bold text-slate-100 uppercase tracking-wider flex items-center gap-1.5">
          <FileText className="w-4 h-4 text-sky-400" />
          Executive Decision Dossier
        </h3>
        <p className="text-[11px] text-slate-400">Generate compliance-grade exports with multi-modal satellite & AI provenance</p>
      </div>

      {/* Success Banner */}
      {successMsg && (
        <div className="p-3 rounded-xl bg-emerald-950/40 border border-emerald-500/40 text-emerald-300 text-xs flex items-center gap-2 animate-in fade-in">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Report Summary Card */}
      <div className="glass-card p-4 rounded-xl border border-white/10 space-y-3">
        <div className="flex items-center justify-between pb-2 border-b border-white/10">
          <span className="text-xs font-semibold text-slate-200">Dossier Contents</span>
          <span className="text-[10px] font-mono text-sky-400">IBM / JORC Protocol</span>
        </div>

        <div className="space-y-2 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-slate-400">Zone Profile:</span>
            <span className="font-semibold text-slate-200 font-mono">
              {zone?.id || 'GLOBAL'} ({((zone?.probability || 0.89) * 100).toFixed(0)}% Probability)
            </span>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-slate-400">Simulated Net Output:</span>
            <span className="font-semibold text-slate-200 font-mono">
              {whatIfResult.netProductionForecastMT.toLocaleString()} MT
            </span>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-slate-400">Mapped Zone Area:</span>
            <span className="font-semibold text-slate-200 font-mono">
              {zone?.areaHectares?.toLocaleString('en-IN', { maximumFractionDigits: 1 }) ?? 'N/A'} ha
            </span>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-slate-400">Operational Risk:</span>
            <span className="font-semibold font-mono" style={{ color: whatIfResult.adjustedRiskColor }}>
              {whatIfResult.adjustedRiskScore}/100 ({whatIfResult.adjustedRiskLevel})
            </span>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-slate-400">Accepted Actions:</span>
            <span className="font-semibold text-emerald-400 font-mono">
              {acceptedCount} of {actionsList.length} approved
            </span>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-slate-400">Active Map Layers Included:</span>
            <span className="font-semibold text-sky-300 font-mono">
              {activeLayers.length} layers
            </span>
          </div>
        </div>

        {/* Active Layers Pill List */}
        <div className="pt-2 border-t border-white/5 flex flex-wrap gap-1.5">
          {activeLayers.map(l => (
            <span key={l.id} className="text-[9px] font-mono px-2 py-0.5 rounded-full bg-slate-900 border border-white/10 text-slate-300 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-sky-400" />
              {l.label} {l.badge}
            </span>
          ))}
        </div>
      </div>

      {/* Export Action Buttons */}
      <div className="space-y-2.5 pt-1">
        {/* PDF Button */}
        <button
          onClick={handlePdfExport}
          disabled={isExportingPdf}
          className="w-full p-3 rounded-xl bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-slate-950 font-bold text-xs shadow-lg shadow-sky-500/25 flex items-center justify-between transition-all hover:scale-[1.01] active:scale-[0.99] disabled:opacity-50"
        >
          <div className="flex items-center gap-2.5">
            {isExportingPdf ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4 fill-slate-950" />}
            <span className="text-left font-bold">
              {isExportingPdf ? 'Compiling PDF with Map Capture...' : 'Download Official PDF Report'}
            </span>
          </div>
          <Download className="w-4 h-4" />
        </button>

        {/* Excel Button */}
        <button
          onClick={handleExcelExport}
          disabled={isExportingExcel}
          className="w-full p-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shadow-lg shadow-emerald-600/25 flex items-center justify-between transition-all hover:scale-[1.01] active:scale-[0.99] disabled:opacity-50"
        >
          <div className="flex items-center gap-2.5">
            {isExportingExcel ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileSpreadsheet className="w-4 h-4" />}
            <span className="text-left">Export Multi-Sheet Excel (.xlsx)</span>
          </div>
          <Download className="w-4 h-4" />
        </button>

        {/* CSV Button */}
        <button
          onClick={handleCsvExport}
          disabled={isExportingCsv}
          className="w-full p-2.5 rounded-xl bg-slate-200 hover:bg-slate-300 text-slate-700 font-medium text-xs border border-slate-300 flex items-center justify-between transition-all"
        >
          <div className="flex items-center gap-2">
            <FileSpreadsheet className="w-3.5 h-3.5 text-slate-500" />
            <span>Download Monthly Forecast (CSV)</span>
          </div>
          <Download className="w-3.5 h-3.5 text-slate-400" />
        </button>
      </div>

      {/* Done / Return Button */}
      <div className="pt-2">
        <button
          onClick={onDone}
          className="w-full py-2.5 rounded-xl border border-white/10 hover:bg-white/5 text-slate-300 font-medium text-xs transition-colors"
        >
          Done & Close Panel
        </button>
      </div>
    </div>
  );
};
