import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useStore } from '@/store/useStore';
import { StepNumber, ProductionData, CorrectiveAction, ShapData } from '@/types';
import { fetchProduction, fetchActions, fetchShap } from '@/lib/api';
import { MINE_CTX } from '@/lib/mines';
import { Step1Forecast } from '@/components/steps/Step1Forecast';
import { Step2Actions } from '@/components/steps/Step2Actions';
import { Step3XAI } from '@/components/steps/Step3XAI';
import { Step4WhatIf } from '@/components/steps/Step4WhatIf';
import { Step5Export } from '@/components/steps/Step5Export';
import { X, Check, ChevronRight } from 'lucide-react';

const STEPS_META = [
  { num: 1 as StepNumber, title: 'Forecast & Shortfall', shortTitle: 'Step 1' },
  { num: 2 as StepNumber, title: 'Corrective Actions', shortTitle: 'Actions' },
  { num: 3 as StepNumber, title: 'Explainable AI', shortTitle: 'SHAP XAI' },
  { num: 4 as StepNumber, title: 'What-If Simulator', shortTitle: 'What-If' },
  { num: 5 as StepNumber, title: 'Export Report', shortTitle: 'Export' },
];

export const AnalysisPanel: React.FC = () => {
  const { flow, layers, setStep, closeAnalysisPanel, selectedZoneData } = useStore();
  const { step, selectedZoneId } = flow;
  // Analytics operate at MINE level: clicked zones map to the Ukwa exploration block,
  // everything else defaults to the Balaghat operating mine.
  const mine = selectedZoneData?.zoneId === 'GUDMA' ? 'Ukwa'
    : selectedZoneData?.id?.startsWith('Z-') ? 'Ukwa'
    : MINE_CTX.defaultMine;

  const [production, setProduction] = useState<ProductionData | null>(null);
  const [actionsList, setActionsList] = useState<CorrectiveAction[]>([]);
  const [shap, setShap] = useState<ShapData | null>(null);
  const [loading, setLoading] = useState(true);

  // Fetch mine-specific analytics from the backend
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([
      fetchProduction(mine),
      fetchActions(mine),
      fetchShap(mine)
    ])
      .then(([prodRes, actRes, shapRes]) => {
        if (cancelled) return;
        setProduction(prodRes);
        setActionsList(actRes.actions);
        setShap(shapRes);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Error fetching analysis data:', err);
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [mine]);

  const handleNextStep = () => {
    if (step < 5) {
      setStep((step + 1) as StepNumber);
    } else {
      closeAnalysisPanel();
    }
  };

  const isPanelOpen = layers.panelOpen;

  return (
    <AnimatePresence>
      {isPanelOpen && (
        <motion.aside
          initial={{ x: '100%', opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: '100%', opacity: 0 }}
          transition={{ type: 'spring', damping: 25, stiffness: 200 }}
          className="analysis-panel fixed top-0 right-0 h-full w-full sm:w-[400px] lg:w-[30vw] lg:max-w-[430px] z-50 border-l flex flex-col overflow-hidden"
        >
          {/* Header */}
          <div className="analysis-panel-header p-4 border-b flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono uppercase tracking-wider text-sky-400 bg-sky-950/80 px-2 py-0.5 rounded border border-sky-500/30">
                  {mine} Analytics
                </span>
                <span className="text-xs font-semibold text-slate-300 truncate max-w-[180px]">
                  {selectedZoneData?.name || `${mine} Mine Operations`}
                </span>
              </div>
              <h2 className="text-sm font-bold text-slate-100 mt-1">
                Mine intelligence
              </h2>
              {selectedZoneData && (
                <p className="text-[10px] text-slate-500 mt-0.5 font-mono">
                  {selectedZoneData.areaHectares?.toLocaleString('en-IN', { maximumFractionDigits: 1 }) ?? '—'} ha
                  {' · '}{(selectedZoneData.estimatedReserveTons / 3.4 / 1000).toFixed(0)}k m³
                  {' · '}{selectedZoneData.avgGrade}
                </p>
              )}
            </div>
            <button
              onClick={closeAnalysisPanel}
              aria-label="Close analysis panel"
              className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-white/10 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Stepper Navigation */}
          <div className="analysis-panel-stepper px-4 py-3 border-b">
            <div className="flex items-center justify-between">
              {STEPS_META.map((item, index) => {
                const isActive = item.num === step;
                const isPassed = item.num < step;

                return (
                  <React.Fragment key={item.num}>
                    <button
                      onClick={() => setStep(item.num)}
                      className={`flex flex-col items-center gap-1 group transition-all ${
                        isActive ? 'scale-105' : 'opacity-70 hover:opacity-100'
                      }`}
                      title={item.title}
                    >
                      <div
                        className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-mono font-bold transition-all ${
                          isActive
                            ? 'bg-sky-500 text-slate-950 shadow-md shadow-sky-500/30'
                            : isPassed
                            ? 'bg-emerald-500 text-slate-950'
                            : 'bg-slate-800 text-slate-400 border border-white/10'
                        }`}
                      >
                        {isPassed ? <Check className="w-3.5 h-3.5 stroke-[3]" /> : item.num}
                      </div>
                      <span
                        className={`text-[9px] font-medium hidden md:block transition-colors ${
                          isActive ? 'text-sky-300 font-bold' : 'text-slate-400'
                        }`}
                      >
                        {item.shortTitle}
                      </span>
                    </button>

                    {index < STEPS_META.length - 1 && (
                      <div
                        className={`flex-1 h-[2px] mx-1 transition-colors ${
                          item.num < step ? 'bg-emerald-500/60' : 'bg-slate-800'
                        }`}
                      />
                    )}
                  </React.Fragment>
                );
              })}
            </div>
          </div>

          {/* Step Body Content */}
          <div className="analysis-panel-body flex-1 overflow-y-auto p-4 space-y-4">
            {loading ? (
              <div className="text-center py-20 text-slate-400">Loading analysis parameters...</div>
            ) : (
              <>
                {step === 1 && (
                  <Step1Forecast
                    production={production}
                    mine={mine}
                    onNext={handleNextStep}
                  />
                )}
                {step === 2 && (
                  <Step2Actions
                    actionsList={actionsList}
                    onNext={handleNextStep}
                  />
                )}
                {step === 3 && (
                  <Step3XAI
                    shap={shap}
                    onNext={handleNextStep}
                  />
                )}
                {step === 4 && (
                  <Step4WhatIf
                    production={production}
                    mine={mine}
                    onNext={handleNextStep}
                  />
                )}
                {step === 5 && (
                  <Step5Export
                    zone={selectedZoneData}
                    production={production}
                    mine={mine}
                    actionsList={actionsList}
                    shap={shap}
                    onDone={closeAnalysisPanel}
                  />
                )}
              </>
            )}
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
};
