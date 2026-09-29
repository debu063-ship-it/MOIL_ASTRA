import React, { useEffect } from 'react';
import { useStore } from '@/store/useStore';
import { TIMELINE_MARKS } from '@/lib/layers';
import { Play, Pause, FastForward } from 'lucide-react';

export const TimeSlider: React.FC = () => {
  const { layers, setTimeIndex, togglePlay } = useStore();
  const { timeIndex, isPlaying } = layers;

  // Auto-play interval
  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setTimeIndex((timeIndex + 1) % TIMELINE_MARKS.length);
    }, 2000);
    return () => clearInterval(interval);
  }, [isPlaying, timeIndex, setTimeIndex]);

  const handleFastForward = () => {
    setTimeIndex((timeIndex + 1) % TIMELINE_MARKS.length);
  };

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-40 pointer-events-auto">
      <div className="bg-[#0f172a]/95 backdrop-blur-md rounded-xl px-4 py-2 border border-white/10 shadow-2xl w-[580px] max-w-[90vw] text-slate-200">
        <div className="flex items-center gap-3">
          {/* Play/Pause Button */}
          <button
            onClick={togglePlay}
            title={isPlaying ? "Pause" : "Play Timeline"}
            className="w-7 h-7 rounded-full bg-slate-800 hover:bg-slate-700 border border-white/15 flex items-center justify-center text-white transition-colors shrink-0"
          >
            {isPlaying ? (
              <Pause className="w-3.5 h-3.5 fill-current" />
            ) : (
              <Play className="w-3.5 h-3.5 fill-current ml-0.5" />
            )}
          </button>

          {/* Time Scrubber Track */}
          <div className="flex-1 relative flex flex-col justify-center">
            {/* Timestamp label above scrubber */}
            <div className="flex justify-between items-center text-[9px] font-mono text-slate-400 mb-0.5">
              <span>{TIMELINE_MARKS[timeIndex]?.season}</span>
              <span>{TIMELINE_MARKS[timeIndex]?.label}</span>
            </div>

            <input
              type="range"
              min={0}
              max={TIMELINE_MARKS.length - 1}
              step={1}
              value={timeIndex}
              onChange={(e) => setTimeIndex(Number(e.target.value))}
              className="w-full h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-sky-400"
            />

            {/* Step Date Ticks */}
            <div className="flex justify-between items-center mt-1 text-[9px] font-mono text-slate-400">
              {TIMELINE_MARKS.map((step, idx) => (
                <button
                  key={step.key}
                  onClick={() => setTimeIndex(idx)}
                  className={`hover:text-white transition-colors ${
                    idx === timeIndex ? 'text-sky-400 font-bold underline' : ''
                  }`}
                >
                  {step.label.split(' ')[0]}
                </button>
              ))}
            </div>
          </div>

          {/* Fast Forward / Loop Button */}
          <button
            onClick={handleFastForward}
            title="Next Frame"
            className="p-1 rounded text-slate-400 hover:text-white transition-colors shrink-0"
          >
            <FastForward className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
