import React from 'react';
import { useStore } from '@/store/useStore';
import { 
  ArrowLeft, 
  Search, 
  Bell, 
  HelpCircle, 
  Settings, 
  User, 
  ChevronDown,
  BarChart3
} from 'lucide-react';

export const TopHeader: React.FC = () => {
  const { 
    flow, 
    backToOverview, 
    openAnalysisPanel, 
    layers
  } = useStore();

  const isZoomed = flow.stage === 'zoomed' || flow.stage === 'step';

  return (
    <>
      {/* 1. Top Global Navigation Bar (Matching Screenshot 1) */}
      <header className="fixed top-0 left-0 right-0 z-40 h-12 bg-[#0b0f19]/90 backdrop-blur-md border-b border-white/10 px-4 flex items-center justify-between text-slate-200">
        {/* Left: Brand Swirl Logo & Title */}
        <div className="flex items-center gap-2.5">
          <div className="w-6 h-6 rounded-full bg-gradient-to-tr from-cyan-400 via-blue-500 to-sky-300 p-0.5 flex items-center justify-center shadow-sm shadow-cyan-500/30">
            <div className="w-full h-full bg-[#0b0f19] rounded-full flex items-center justify-center">
              <span className="text-[10px] font-bold text-sky-400">◐</span>
            </div>
          </div>
          <span className="font-semibold text-sm tracking-tight text-white">MOIL Limited</span>
        </div>

        {/* Right: Search, Notifications, Help, Settings, Profile */}
        <div className="flex items-center gap-3">
          {/* Search for leases dropdown pill */}
          <div className="relative hidden sm:flex items-center bg-slate-800/80 hover:bg-slate-800 border border-white/10 rounded-full px-3 py-1 text-xs text-slate-300 cursor-pointer transition-colors gap-2 w-48">
            <Search className="w-3.5 h-3.5 text-slate-400" />
            <span className="truncate flex-1">Search for leases</span>
            <ChevronDown className="w-3 h-3 text-slate-400" />
          </div>

          <button
            onClick={openAnalysisPanel}
            className="flex items-center gap-1.5 px-2 sm:px-3 py-1.5 rounded-lg bg-sky-500 hover:bg-sky-400 text-slate-950 text-xs font-semibold shadow-sm shadow-sky-500/20 transition-colors"
            title="Open production dashboard"
            aria-label="Open production dashboard"
          >
            <BarChart3 className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Dashboard</span>
          </button>

          {/* Bell Icon with notification badge */}
          <button 
            title="Notifications" 
            className="relative p-1.5 rounded-full hover:bg-white/10 text-slate-300 transition-colors"
          >
            <Bell className="w-4 h-4" />
            <span className="absolute 1 top-1 right-1 w-3.5 h-3.5 bg-sky-500 text-[9px] font-bold text-slate-950 rounded-full flex items-center justify-center">
              1
            </span>
          </button>

          {/* Help Icon */}
          <button 
            title="Help & Documentation" 
            className="p-1.5 rounded-full hover:bg-white/10 text-slate-300 transition-colors"
          >
            <HelpCircle className="w-4 h-4" />
          </button>

          {/* Settings Icon */}
          <button 
            title="Settings" 
            className="p-1.5 rounded-full hover:bg-white/10 text-slate-300 transition-colors"
          >
            <Settings className="w-4 h-4" />
          </button>

          {/* User Profile Avatar */}
          <div 
            title="Mining Engineer Profile" 
            className="w-7 h-7 rounded-full bg-slate-700 border border-white/20 flex items-center justify-center cursor-pointer hover:border-sky-400 transition-colors"
          >
            <User className="w-4 h-4 text-slate-300" />
          </div>
        </div>
      </header>

      {/* 2. Floating Title Chip / Back to Overview Button (Below Header on Left) */}
      <div className="fixed top-[60px] left-5 z-40 flex items-center gap-3 pointer-events-auto">
        {!isZoomed ? (
          <div className="bg-[#0f172a]/90 backdrop-blur-md px-3.5 py-2 rounded-xl border border-white/15 shadow-xl flex items-center gap-2.5">
            <div className="w-5 h-5 rounded-full bg-amber-500/20 border border-amber-500/40 flex items-center justify-center">
              <span className="text-[9px] font-bold text-amber-400">ML</span>
            </div>
            <span className="text-xs font-bold text-white tracking-wide">MOIL Limited</span>
          </div>
        ) : (
          <button
            onClick={backToOverview}
            className="bg-[#0f172a]/95 hover:bg-slate-800 text-sky-300 hover:text-white px-4 py-2 rounded-xl border border-sky-400/40 shadow-2xl flex items-center gap-2 text-xs font-semibold transition-all hover:scale-105 active:scale-95"
          >
            <ArrowLeft className="w-3.5 h-3.5 text-sky-400" />
            Back to overview
          </button>
        )}

        {/* Quick Launch Analysis Panel if closed in zoomed mode */}
        {flow.stage === 'zoomed' && !layers.panelOpen && (
          <button
            onClick={openAnalysisPanel}
            className="bg-sky-600 hover:bg-sky-500 text-white px-3.5 py-2 rounded-xl shadow-xl flex items-center gap-2 text-xs font-bold transition-all hover:scale-105 active:scale-95"
          >
            <BarChart3 className="w-3.5 h-3.5" />
            Open Analysis Panel
          </button>
        )}
      </div>
    </>
  );
};
