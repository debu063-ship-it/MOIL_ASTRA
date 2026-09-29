import React from 'react';
import { useStore } from '@/store/useStore';
import { CorrectiveAction, ActionStatus } from '@/types';
import { SourceBadge } from '@/components/ui/Badge';
import { Check, X, ShieldAlert, Sparkles, Clock, DollarSign, TrendingUp } from 'lucide-react';

interface Step2Props {
  actionsList: CorrectiveAction[];
  onNext: () => void;
}

export const Step2Actions: React.FC<Step2Props> = ({ actionsList, onNext }) => {
  const { actions, setActionStatus } = useStore();

  const handleToggle = (actionId: string, targetStatus: ActionStatus) => {
    const current = actions[actionId] || 'pending';
    if (current === targetStatus) {
      setActionStatus(actionId, 'pending');
    } else {
      setActionStatus(actionId, targetStatus);
    }
  };

  // Calculate cumulative recovery from accepted actions
  const acceptedActions = actionsList.filter(a => (actions[a.id] || a.status) === 'accepted');
  const totalRecoveredMT = acceptedActions.reduce((sum, a) => sum + a.expectedImpactMT, 0);
  const totalRiskReductionPct = acceptedActions.reduce((sum, a) => sum + a.riskReductionPct, 0);

  return (
    <div className="space-y-4">
      {/* Top Impact Banner */}
      <div className="glass-card p-3 rounded-xl border border-emerald-500/30 bg-emerald-950/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-emerald-400" />
            <span className="text-xs font-bold text-slate-100 uppercase tracking-wider">
              Optimization Plan
            </span>
          </div>
          <SourceBadge badge="[MODELED]" />
        </div>

        <div className="grid grid-cols-2 gap-2 mt-2 pt-2 border-t border-emerald-500/20">
          <div>
            <span className="text-[10px] text-emerald-300/80 block">Accepted Recovery</span>
            <span className="text-base font-bold font-mono text-emerald-400">
              +{totalRecoveredMT.toLocaleString()} MT
            </span>
          </div>
          <div>
            <span className="text-[10px] text-emerald-300/80 block">Risk Mitigation</span>
            <span className="text-base font-bold font-mono text-emerald-400">
              -{totalRiskReductionPct.toFixed(1)}% Risk
            </span>
          </div>
        </div>
      </div>

      {/* Ranked Action Cards */}
      <div className="space-y-3">
        <div className="flex items-center justify-between text-xs text-slate-400 px-1">
          <span>AI-Ranked Operational Interventions</span>
          <span className="font-mono">{actionsList.length} Options</span>
        </div>

        {actionsList.map((action, index) => {
          const currentStatus = actions[action.id] || action.status || 'pending';
          const isAccepted = currentStatus === 'accepted';
          const isIgnored = currentStatus === 'ignored';

          return (
            <div
              key={action.id}
              className={`p-3.5 rounded-xl transition-all duration-200 border ${
                isAccepted
                  ? 'glass-card border-emerald-500/40 bg-emerald-950/20 shadow-lg shadow-emerald-950/40'
                  : isIgnored
                  ? 'glass-card border-white/5 opacity-50 bg-slate-900/30'
                  : 'glass-card border-white/10 hover:border-sky-500/30 bg-slate-900/50'
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-sky-500/20 text-sky-400 font-mono text-xs font-bold flex items-center justify-center border border-sky-500/30">
                    {index + 1}
                  </span>
                  <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wide">
                    {action.category}
                  </span>
                </div>
                <SourceBadge badge={action.source as any} />
              </div>

              <h4 className="text-xs font-semibold text-slate-100 mt-1.5 leading-snug">
                {action.title}
              </h4>
              <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
                {action.description}
              </p>

              {/* Metrics */}
              <div className="grid grid-cols-3 gap-2 mt-2.5 pt-2 border-t border-white/5 text-[10px]">
                <div className="bg-slate-900/60 p-1.5 rounded border border-white/5">
                  <span className="text-slate-400 block">Production Gain</span>
                  <span className="font-mono font-bold text-emerald-400">+{action.expectedImpactMT} MT</span>
                </div>
                <div className="bg-slate-900/60 p-1.5 rounded border border-white/5">
                  <span className="text-slate-400 block">Risk Reduction</span>
                  <span className="font-mono font-bold text-sky-400">-{action.riskReductionPct}%</span>
                </div>
                <div className="bg-slate-900/60 p-1.5 rounded border border-white/5">
                  <span className="text-slate-400 block">Est. Cost & Time</span>
                  <span className="font-mono text-slate-300">{action.leadTimeDays}d / {action.costEstimateINR}</span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-2 mt-3 pt-2 border-t border-white/5">
                <button
                  onClick={() => handleToggle(action.id, 'ignored')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all ${
                    isIgnored
                      ? 'bg-slate-700 text-slate-300 border border-slate-600'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                  }`}
                >
                  <X className="w-3.5 h-3.5" />
                  {isIgnored ? 'Ignored' : 'Ignore'}
                </button>

                <button
                  onClick={() => handleToggle(action.id, 'accepted')}
                  className={`px-3.5 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-all ${
                    isAccepted
                      ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/25'
                      : 'bg-slate-800 hover:bg-emerald-600 hover:text-white text-emerald-300 border border-emerald-500/30'
                  }`}
                >
                  <Check className="w-3.5 h-3.5" />
                  {isAccepted ? 'Accepted' : 'Accept Action'}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* CTA Button */}
      <div className="pt-2">
        <button
          onClick={onNext}
          className="w-full py-3 rounded-xl bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold text-sm shadow-lg shadow-sky-500/25 flex items-center justify-center gap-2 transition-all hover:scale-[1.01] active:scale-[0.99]"
        >
          Explainable AI &rarr;
        </button>
      </div>
    </div>
  );
};
