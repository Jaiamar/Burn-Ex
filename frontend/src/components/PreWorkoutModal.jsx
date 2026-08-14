/**
 * src/components/PreWorkoutModal.jsx
 * Burn-Ex — Pre-Workout Confirmation & Position Check Modal
 * 
 * Displays pre-start safety guidelines, exercise metadata, and confirmation
 * buttons before activating the workout start countdown.
 */

import React, { useEffect } from 'react';
import { Camera, ShieldCheck, Dumbbell, Play, X, Sparkles } from 'lucide-react';

export function PreWorkoutModal({
  isOpen,
  exerciseName = 'Push-Up',
  onClose,
  onConfirmStart
}) {
  // Keyboard Escape listener
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4 font-sans select-none animate-in fade-in duration-200">
      <div className="w-full max-w-md bg-white rounded-3xl shadow-2xl border border-slate-100 overflow-hidden scale-in">
        
        {/* Header Banner */}
        <div className="bg-gradient-to-r from-indigo-600 to-purple-600 p-6 text-white text-center relative">
          <button
            type="button"
            onClick={onClose}
            className="absolute top-4 right-4 p-2 bg-white/10 hover:bg-white/20 rounded-full text-white/80 hover:text-white transition"
          >
            <X size={18} />
          </button>

          <div className="w-14 h-14 bg-white/15 border border-white/20 rounded-2xl flex items-center justify-center mx-auto mb-3 backdrop-blur-md">
            <Dumbbell size={28} className="text-white" />
          </div>

          <span className="text-[10px] font-black uppercase tracking-widest bg-white/20 px-3 py-1 rounded-full inline-block mb-1">
            Pre-Workout Setup
          </span>
          <h2 className="text-xl font-black tracking-tight">Ready to Start?</h2>
          <p className="text-white/80 text-xs mt-1 font-medium">
            {exerciseName} Live AI Training Session
          </p>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-4">
          
          <div className="space-y-3">
            <div className="p-3.5 bg-slate-50 border border-slate-200/70 rounded-2xl flex items-start gap-3">
              <div className="w-8 h-8 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 flex-shrink-0 mt-0.5">
                <Camera size={16} />
              </div>
              <div>
                <strong className="text-xs font-bold text-slate-800 block">Full Body Visibility</strong>
                <p className="text-[11px] font-medium text-slate-500 mt-0.5 leading-relaxed">
                  Place device at waist level 4–5 meters away so your entire body is visible in the camera frame.
                </p>
              </div>
            </div>

            <div className="p-3.5 bg-slate-50 border border-slate-200/70 rounded-2xl flex items-start gap-3">
              <div className="w-8 h-8 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600 flex-shrink-0 mt-0.5">
                <ShieldCheck size={16} />
              </div>
              <div>
                <strong className="text-xs font-bold text-slate-800 block">Safety Clearance</strong>
                <p className="text-[11px] font-medium text-slate-500 mt-0.5 leading-relaxed">
                  Ensure 2 meters of clear floor space around you free from obstacles or hazards.
                </p>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-3 px-4 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-xl transition"
            >
              Cancel
            </button>

            <button
              type="button"
              onClick={onConfirmStart}
              className="flex-1 py-3 px-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white text-xs font-black rounded-xl shadow-lg shadow-indigo-600/20 transition active:scale-95 flex items-center justify-center gap-2"
            >
              <Play size={15} fill="currentColor" />
              Start Countdown
            </button>
          </div>

        </div>

      </div>
    </div>
  );
}

export default PreWorkoutModal;
