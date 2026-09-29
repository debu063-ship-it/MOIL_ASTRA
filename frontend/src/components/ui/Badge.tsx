import React from 'react';
import { LayerSourceBadge } from '@/types';

interface BadgeProps {
  children: React.ReactNode;
  variant?: LayerSourceBadge | 'default' | 'success' | 'warning' | 'danger';
  className?: string;
}

export const SourceBadge: React.FC<{ badge: LayerSourceBadge; className?: string }> = ({ badge, className = '' }) => {
  let colorClasses = 'bg-blue-500/20 text-blue-300 border-blue-500/40';
  if (badge === '[MODELED]') {
    colorClasses = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';
  } else if (badge === '[SYNTHETIC]') {
    colorClasses = 'bg-purple-500/20 text-purple-300 border-purple-500/40';
  }

  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono tracking-wider font-semibold border ${colorClasses} ${className}`}>
      {badge}
    </span>
  );
};

export const StatusBadge: React.FC<{ status: 'Red' | 'Amber' | 'Green'; className?: string }> = ({ status, className = '' }) => {
  let colors = 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
  if (status === 'Red') {
    colors = 'bg-red-500/20 text-red-400 border-red-500/30';
  } else if (status === 'Amber') {
    colors = 'bg-amber-500/20 text-amber-400 border-amber-500/30';
  }

  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border ${colors} ${className}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${status === 'Red' ? 'bg-red-400 animate-pulse' : status === 'Amber' ? 'bg-amber-400' : 'bg-emerald-400'}`} />
      {status} Risk
    </span>
  );
};
